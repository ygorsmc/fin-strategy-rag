"""Download do corpus a partir do manifesto (seção 5.2; etapa 2 do AGENTS.md).

O `corpus/metadados.csv` é a fonte de verdade, não os binários: este script
re-obtém cada PDF pela URL registrada e valida o hash SHA-256. URL morta ou
hash divergente é DETECTADO E REPORTADO, nunca re-raspado silenciosamente.
Linha com hash vazio (primeira coleta) tem o hash preenchido e o manifesto
reescrito.

Uso:
    python scripts/baixar_corpus.py [--amostra] [--forcar]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.config import (  # noqa: E402
    CAMINHO_METADADOS_CORPUS,
    Config,
    DIR_CORPUS_RAW,
)
from src.ingestao import COLUNAS_METADADOS_CORPUS  # noqa: E402

TIMEOUT_CONEXAO_S = 10
TIMEOUT_LEITURA_S = 60
MAX_PDF_BYTES = 100 * 1024 * 1024
PADRAO_DOCUMENTO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
PADRAO_HASH_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
STATUS_RETRY = (429, 500, 502, 503, 504)
STATUS_REDIRECT = frozenset({301, 302, 303, 307, 308})
MAX_REDIRECTS = 5
MAX_ESPERA_RETRY_S = 10
HOSTS_PERMITIDOS = frozenset(
    {
        "d169uzu5o4xu1k.cloudfront.net",
        "api.mziq.com",
        "filemanager-cdn.mziq.com",
        # RAD/CVM: fonte dos 7 emissores novos de 2026-08-27 (enriquecimento
        # de corpus, becos_sem_saida.md §E/Rank 5 — precisa de ≥10 emissores).
        "www.rad.cvm.gov.br",
    }
)


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _criar_sessao() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1.0,
        backoff_max=MAX_ESPERA_RETRY_S,
        status_forcelist=STATUS_RETRY,
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        retry_after_max=MAX_ESPERA_RETRY_S,
    )
    sessao = requests.Session()
    sessao.mount("https://", HTTPAdapter(max_retries=retry))
    return sessao


def _validar_url(url: str) -> None:
    partes = urlsplit(url)
    if (
        partes.scheme != "https"
        or not partes.hostname
        or partes.username
        or partes.password
    ):
        raise ValueError("URL deve ser HTTPS, sem credenciais embutidas")
    try:
        porta = partes.port
    except ValueError as exc:
        raise ValueError("URL contém porta inválida") from exc
    if porta not in (None, 443) or partes.fragment:
        raise ValueError("URL deve usar a porta HTTPS padrão e não conter fragmento")
    host = partes.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("URL de loopback não é permitida no manifesto")
    if host not in HOSTS_PERMITIDOS:
        raise ValueError(f"host fora da allowlist do corpus: {host!r}")
    try:
        endereco = ipaddress.ip_address(host)
    except ValueError:
        return
    if not endereco.is_global:
        raise ValueError("URL com endereço IP não público não é permitida")


def _validar_linha(linha: dict[str, str], numero: int) -> None:
    if None in linha or set(linha) != set(COLUNAS_METADADOS_CORPUS):
        raise ValueError(
            f"linha {numero}: quantidade de campos diferente do cabeçalho"
        )
    vazios = [
        campo
        for campo in ("empresa", "trimestre", "documento", "url")
        if not linha[campo].strip()
    ]
    if vazios:
        raise ValueError(f"linha {numero}: campos obrigatórios vazios: {vazios}")
    documento = linha["documento"]
    if PADRAO_DOCUMENTO.fullmatch(documento) is None:
        raise ValueError(f"linha {numero}: documento inseguro: {documento!r}")
    _validar_url(linha["url"])
    if not linha["empresa"].strip():
        raise ValueError(f"linha {numero}: empresa vazia")
    if re.fullmatch(r"[1-4]T\d{4}", linha["trimestre"]) is None:
        raise ValueError(f"linha {numero}: trimestre inválido")
    hash_esperado = linha["hash_sha256"].strip()
    if hash_esperado and PADRAO_HASH_SHA256.fullmatch(hash_esperado) is None:
        raise ValueError(f"linha {numero}: hash_sha256 inválido")
    data_coleta = linha["data_coleta"].strip()
    if hash_esperado and not data_coleta:
        raise ValueError(f"linha {numero}: hash preenchido sem data_coleta")
    if data_coleta:
        try:
            date.fromisoformat(data_coleta)
        except ValueError as exc:
            raise ValueError(f"linha {numero}: data_coleta inválida") from exc


def _validar_manifesto(
    linhas: list[dict[str, str]],
    fieldnames: list[str] | None,
) -> None:
    if tuple(fieldnames or ()) != COLUNAS_METADADOS_CORPUS:
        raise ValueError(
            f"esquema inesperado: {fieldnames!r}; "
            f"esperado={COLUNAS_METADADOS_CORPUS!r}"
        )
    if not linhas:
        raise ValueError("manifesto vazio")
    # O manifesto é um contrato versionado do projeto. Variáveis do `.env`
    # não podem afrouxar sua cardinalidade nem trocar silenciosamente os bancos.
    config = Config()
    for numero, linha in enumerate(linhas, start=2):
        _validar_linha(linha, numero)
    empresas = {linha["empresa"] for linha in linhas}
    esperadas = set(config.bancos)
    if empresas != esperadas:
        raise ValueError(f"empresas={sorted(empresas)}; esperado={sorted(esperadas)}")
    pares = {(linha["empresa"], linha["trimestre"]) for linha in linhas}
    documentos = {linha["documento"] for linha in linhas}
    urls = {linha["url"] for linha in linhas}
    for rotulo, valores in (
        ("pares empresa/trimestre", pares),
        ("documentos", documentos),
        ("URLs", urls),
    ):
        if len(valores) != len(linhas):
            raise ValueError(f"manifesto contém {rotulo} duplicados")
    trimestres_por_empresa = {
        empresa: {r["trimestre"] for r in linhas if r["empresa"] == empresa}
        for empresa in empresas
    }
    if any(len(ts) != config.n_trimestres for ts in trimestres_por_empresa.values()):
        raise ValueError("cada empresa deve ter exatamente N_TRIMESTRES")
    if len({frozenset(ts) for ts in trimestres_por_empresa.values()}) != 1:
        raise ValueError("empresas devem compartilhar a mesma interseção de trimestres")


def _destino_seguro(documento: str) -> Path:
    raiz = DIR_CORPUS_RAW.resolve()
    destino = (DIR_CORPUS_RAW / f"{documento}.pdf").resolve(strict=False)
    if destino.parent != raiz:
        raise ValueError(f"destino escaparia de corpus/raw: {documento!r}")
    return destino


def _validar_pdf(caminho: Path) -> None:
    tamanho = caminho.stat().st_size
    if tamanho <= 0 or tamanho > MAX_PDF_BYTES:
        raise ValueError(f"tamanho de PDF inválido: {tamanho} bytes")
    with open(caminho, "rb") as arquivo:
        assinatura = arquivo.read(5)
    if assinatura != b"%PDF-":
        raise ValueError("conteúdo baixado não começa com %PDF-")
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho), strict=False)
    if leitor.is_encrypted:
        raise ValueError("PDF criptografado não é aceito no corpus")
    if len(leitor.pages) < 1:
        raise ValueError("PDF sem páginas")


def _baixar_para_temporario(
    url: str,
    destino: Path,
    sessao: requests.Session,
) -> Path:
    fd, nome = tempfile.mkstemp(prefix=f".{destino.name}.", suffix=".part", dir=destino.parent)
    os.close(fd)
    temporario = Path(nome)
    try:
        url_atual = url
        resposta: requests.Response | None = None
        for salto in range(MAX_REDIRECTS + 1):
            _validar_url(url_atual)
            resposta = sessao.get(
                url_atual,
                timeout=(TIMEOUT_CONEXAO_S, TIMEOUT_LEITURA_S),
                stream=True,
                allow_redirects=False,
            )
            if resposta.status_code not in STATUS_REDIRECT:
                break
            local = resposta.headers.get("Location")
            resposta.close()
            resposta = None
            if not local:
                raise ValueError("redirecionamento sem cabeçalho Location")
            if salto >= MAX_REDIRECTS:
                raise ValueError(
                    f"download excedeu o limite de {MAX_REDIRECTS} redirecionamentos"
                )
            url_atual = urljoin(url_atual, local)
        if resposta is None:
            raise RuntimeError("download terminou sem resposta HTTP final")

        with resposta:
            resposta.raise_for_status()
            tamanho_declarado = resposta.headers.get("Content-Length", "0") or "0"
            try:
                declarado = int(tamanho_declarado)
            except (TypeError, ValueError) as exc:
                raise ValueError("Content-Length inválido") from exc
            if declarado < 0:
                raise ValueError("Content-Length não pode ser negativo")
            if declarado > MAX_PDF_BYTES:
                raise ValueError(f"Content-Length excede {MAX_PDF_BYTES} bytes")
            total = 0
            with open(temporario, "wb") as arquivo:
                for bloco in resposta.iter_content(1 << 20):
                    if not bloco:
                        continue
                    total += len(bloco)
                    if total > MAX_PDF_BYTES:
                        raise ValueError(f"download excede {MAX_PDF_BYTES} bytes")
                    arquivo.write(bloco)
                arquivo.flush()
                os.fsync(arquivo.fileno())
        _validar_pdf(temporario)
        return temporario
    except Exception:
        temporario.unlink(missing_ok=True)
        raise


def _salvar_manifesto_atomico(linhas: list[dict[str, str]]) -> None:
    pasta = CAMINHO_METADADOS_CORPUS.parent
    fd, nome = tempfile.mkstemp(prefix=".metadados.", suffix=".tmp", dir=pasta)
    os.close(fd)
    temporario = Path(nome)
    try:
        with open(temporario, "w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_METADADOS_CORPUS)
            escritor.writeheader()
            escritor.writerows(linhas)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, CAMINHO_METADADOS_CORPUS)
    except Exception:
        temporario.unlink(missing_ok=True)
        raise


def baixar_corpus(amostra: bool = False, forcar: bool = False) -> bool:
    """Devolve True se todos os documentos do manifesto estão íntegros."""
    with open(CAMINHO_METADADOS_CORPUS, newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        linhas = list(leitor)
        fieldnames = leitor.fieldnames
    try:
        _validar_manifesto(linhas, fieldnames)
    except ValueError as exc:
        print(f"Manifesto inválido — {exc}")
        return False
    linhas_alvo = linhas[:1] if amostra else linhas

    DIR_CORPUS_RAW.mkdir(parents=True, exist_ok=True)
    problemas: list[str] = []
    manifesto_mudou = False
    sessao = _criar_sessao()
    try:
        for linha in linhas_alvo:
            destino = _destino_seguro(linha["documento"])
            rotulo = (
                f"{linha['empresa']} {linha['trimestre']} "
                f"({linha['documento']})"
            )

            hash_esperado = linha["hash_sha256"].strip().lower()
            hash_local: str | None = None
            # Sem hash pinado ainda não existe âncora de confiança. Uma cópia
            # preexistente pode ter vindo de qualquer origem e, portanto, nunca
            # deve ser promovida silenciosamente a hash oficial (TOFU local).
            # A primeira coleta sempre baixa para um temporário validado antes
            # da substituição atômica e do registro no manifesto.
            if destino.exists() and not forcar and not hash_esperado:
                print(
                    f"  hash ainda não pinado para {rotulo}; "
                    "ignorando cópia local e coletando da URL"
                )
            elif destino.exists() and not forcar:
                try:
                    _validar_pdf(destino)
                    hash_local = _sha256(destino)
                except Exception as exc:
                    print(
                        f"  cópia local inválida para {rotulo}: {exc}; rebaixando"
                    )
                    hash_local = None
                else:
                    if hash_esperado and hash_local != hash_esperado:
                        print(
                            f"  hash local divergente para {rotulo}; "
                            "tentando recuperação atômica"
                        )
                        hash_local = None
                    else:
                        print(f"  ok: {rotulo}")

            if hash_local is None:
                temporario: Path | None = None
                try:
                    print(f"Baixando {rotulo} ...")
                    temporario = _baixar_para_temporario(
                        linha["url"], destino, sessao
                    )
                    hash_baixado = _sha256(temporario)
                    if hash_esperado and hash_baixado != hash_esperado:
                        raise ValueError(
                            f"HASH DIVERGENTE — esperado={hash_esperado[:12]}… "
                            f"baixado={hash_baixado[:12]}…"
                        )
                    os.replace(temporario, destino)
                    temporario = None
                    hash_local = hash_baixado
                except Exception as exc:
                    if temporario is not None:
                        temporario.unlink(missing_ok=True)
                    problemas.append(
                        f"{rotulo}: falha de download/validação — {exc}"
                    )
                    continue
            if not hash_esperado:
                linha["hash_sha256"] = hash_local
                linha["data_coleta"] = date.today().isoformat()
                manifesto_mudou = True
                print(f"  hash registrado para {rotulo}: {hash_local[:12]}…")
            else:
                print(f"  hash confirmado: {rotulo}")
    finally:
        sessao.close()
    if manifesto_mudou:
        try:
            _salvar_manifesto_atomico(linhas)
        except OSError as exc:
            problemas.append(f"falha ao atualizar manifesto atomicamente — {exc}")
        else:
            print(f"Manifesto atualizado: {CAMINHO_METADADOS_CORPUS}")

    for p in problemas:
        print(f"PROBLEMA: {p}")
    return not problemas


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--amostra", action="store_true", help="só o 1º documento (smoke test)"
    )
    parser.add_argument(
        "--forcar", action="store_true", help="re-baixa mesmo se o PDF já existe"
    )
    args = parser.parse_args()
    sys.exit(0 if baixar_corpus(amostra=args.amostra, forcar=args.forcar) else 1)
