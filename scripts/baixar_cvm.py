"""Download dos conjuntos ITR/DFP da CVM com manifesto pinado por hash (spec 5.5).

O portal de dados abertos da CVM é atualizado **semanalmente** e republica
versões do mesmo ano. Sem hash registrado, o gabarito das perguntas da classe
`cvm` muda sozinho depois do congelamento do conjunto-padrão — o risco 15d. Por
isso este script mantém `corpus/cvm/manifesto_cvm.csv` com **URL, data de
download, tamanho e SHA-256 de cada ZIP**, e trata divergência de hash como
problema a reportar, nunca como atualização automática.

Os ZIPs não vão para o Git (são regeneráveis); o manifesto vai.

Uso:
    python scripts/baixar_cvm.py --anos 2025,2026 --conjuntos itr,dfp
    python scripts/baixar_cvm.py --somente-verificar
    python scripts/baixar_cvm.py --anos 2025 --conjuntos itr --aceitar-republicacao
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.config import DIR_CVM_BRUTO  # noqa: E402

BASE_CVM = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC"
HOST_PERMITIDO = "dados.cvm.gov.br"
CONJUNTOS = ("itr", "dfp")
# ITR desde 2011, DFP desde 2010 (verificado no portal); o limite superior é só
# uma sanidade contra ano digitado errado.
ANO_MINIMO = 2010
ANO_MAXIMO = 2100

CAMINHO_MANIFESTO = DIR_CVM_BRUTO / "manifesto_cvm.csv"
COLUNAS_MANIFESTO = (
    "conjunto",
    "ano",
    "arquivo",
    "url",
    "data_download",
    "tamanho_bytes",
    "hash_sha256",
)

TIMEOUT_CONEXAO_S = 10
TIMEOUT_LEITURA_S = 120
MAX_ZIP_BYTES = 500 * 1024 * 1024
# Um ZIP anual descompacta ~325 MB em 19 CSVs; o teto protege contra zip bomb.
MAX_BYTES_DESCOMPACTADOS = 4 * 1024 * 1024 * 1024
STATUS_RETRY = (429, 500, 502, 503, 504)
MAX_ESPERA_RETRY_S = 15

PADRAO_MEMBRO = re.compile(r"^(itr|dfp)_cia_aberta_[A-Za-z_]*\d{4}\.csv$")
PADRAO_HASH_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def url_do_conjunto(conjunto: str, ano: int) -> str:
    """Monta a URL oficial do ZIP anual — única forma de endereçar o portal."""
    conjunto = conjunto.strip().lower()
    if conjunto not in CONJUNTOS:
        raise ValueError(f"conjunto desconhecido: {conjunto!r}; use {CONJUNTOS}")
    if not isinstance(ano, int) or isinstance(ano, bool):
        raise ValueError(f"ano deve ser inteiro: {ano!r}")
    if not ANO_MINIMO <= ano <= ANO_MAXIMO:
        raise ValueError(f"ano fora da faixa {ANO_MINIMO}–{ANO_MAXIMO}: {ano}")
    return f"{BASE_CVM}/{conjunto.upper()}/DADOS/{nome_do_arquivo(conjunto, ano)}"


def nome_do_arquivo(conjunto: str, ano: int) -> str:
    return f"{conjunto.strip().lower()}_cia_aberta_{ano}.zip"


def validar_url(url: str) -> None:
    """Só o host oficial da CVM, HTTPS, sem credenciais nem porta exótica."""
    partes = urlsplit(url)
    if partes.scheme != "https":
        raise ValueError("URL deve ser HTTPS")
    if partes.username or partes.password:
        raise ValueError("URL não pode conter credenciais embutidas")
    try:
        porta = partes.port
    except ValueError as exc:
        raise ValueError("URL contém porta inválida") from exc
    if porta not in (None, 443):
        raise ValueError("URL deve usar a porta HTTPS padrão")
    if (partes.hostname or "").lower() != HOST_PERMITIDO:
        raise ValueError(f"host fora da allowlist da CVM: {partes.hostname!r}")
    if not partes.path.startswith("/dados/CIA_ABERTA/DOC/"):
        raise ValueError(f"caminho fora do conjunto CIA_ABERTA: {partes.path!r}")
    if partes.query or partes.fragment:
        raise ValueError("URL não deve conter query nem fragmento")


def sha256_do_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def validar_zip(caminho: Path) -> list[str]:
    """Confere que é um ZIP legítimo da CVM e devolve os membros.

    Recusa nome de membro que escape do diretório (zip slip) e conteúdo
    descompactado desproporcional (zip bomb).
    """
    if not zipfile.is_zipfile(caminho):
        raise ValueError("arquivo baixado não é um ZIP")
    with zipfile.ZipFile(caminho) as pacote:
        membros = pacote.namelist()
        if not membros:
            raise ValueError("ZIP vazio")
        total = 0
        for info in pacote.infolist():
            nome = info.filename
            if nome.endswith("/"):
                raise ValueError(f"ZIP contém diretório inesperado: {nome!r}")
            if os.path.isabs(nome) or ".." in Path(nome).parts or "\\" in nome:
                raise ValueError(f"nome de membro inseguro no ZIP: {nome!r}")
            if PADRAO_MEMBRO.fullmatch(nome) is None:
                raise ValueError(f"membro fora do padrão da CVM: {nome!r}")
            total += info.file_size
        if total > MAX_BYTES_DESCOMPACTADOS:
            raise ValueError(
                f"conteúdo descompactado excede {MAX_BYTES_DESCOMPACTADOS} bytes"
            )
    return sorted(membros)


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


def _baixar_para_temporario(
    url: str, destino: Path, sessao: requests.Session
) -> Path:
    validar_url(url)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(
        prefix=f".{destino.name}.", suffix=".part", dir=destino.parent
    )
    os.close(fd)
    temporario = Path(nome)
    try:
        with sessao.get(
            url,
            timeout=(TIMEOUT_CONEXAO_S, TIMEOUT_LEITURA_S),
            stream=True,
            allow_redirects=False,
        ) as resposta:
            resposta.raise_for_status()
            declarado = int(resposta.headers.get("Content-Length", "0") or "0")
            if declarado > MAX_ZIP_BYTES:
                raise ValueError(f"Content-Length excede {MAX_ZIP_BYTES} bytes")
            total = 0
            with open(temporario, "wb") as arquivo:
                for bloco in resposta.iter_content(1 << 20):
                    if not bloco:
                        continue
                    total += len(bloco)
                    if total > MAX_ZIP_BYTES:
                        raise ValueError(f"download excede {MAX_ZIP_BYTES} bytes")
                    arquivo.write(bloco)
                arquivo.flush()
                os.fsync(arquivo.fileno())
        validar_zip(temporario)
        return temporario
    except Exception:
        temporario.unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------- #
# Manifesto
# --------------------------------------------------------------------------- #


def ler_manifesto(caminho: Path = CAMINHO_MANIFESTO) -> list[dict[str, str]]:
    if not caminho.is_file():
        return []
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        if tuple(leitor.fieldnames or ()) != COLUNAS_MANIFESTO:
            raise ValueError(
                f"esquema inesperado do manifesto: {leitor.fieldnames!r}; "
                f"esperado={list(COLUNAS_MANIFESTO)}"
            )
        linhas = list(leitor)
    for numero, linha in enumerate(linhas, start=2):
        validar_linha_manifesto(linha, numero)
    chaves = {(linha["conjunto"], linha["ano"]) for linha in linhas}
    if len(chaves) != len(linhas):
        raise ValueError("manifesto contém conjunto/ano duplicados")
    return linhas


def validar_linha_manifesto(linha: dict[str, str], numero: int) -> None:
    faltando = [c for c in COLUNAS_MANIFESTO if not (linha.get(c) or "").strip()]
    if faltando:
        raise ValueError(f"linha {numero}: campos vazios: {faltando}")
    if linha["conjunto"] not in CONJUNTOS:
        raise ValueError(f"linha {numero}: conjunto inválido: {linha['conjunto']!r}")
    ano = int(linha["ano"])
    if not ANO_MINIMO <= ano <= ANO_MAXIMO:
        raise ValueError(f"linha {numero}: ano fora da faixa: {ano}")
    if linha["arquivo"] != nome_do_arquivo(linha["conjunto"], ano):
        raise ValueError(f"linha {numero}: nome de arquivo incoerente")
    validar_url(linha["url"])
    if PADRAO_HASH_SHA256.fullmatch(linha["hash_sha256"]) is None:
        raise ValueError(f"linha {numero}: hash_sha256 inválido")
    if int(linha["tamanho_bytes"]) <= 0:
        raise ValueError(f"linha {numero}: tamanho_bytes deve ser positivo")
    date.fromisoformat(linha["data_download"])


def salvar_manifesto(
    linhas: list[dict[str, str]], caminho: Path = CAMINHO_MANIFESTO
) -> None:
    """Grava de forma atômica, ordenado por conjunto e ano (diff estável)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    ordenadas = sorted(linhas, key=lambda linha: (linha["conjunto"], int(linha["ano"])))
    fd, nome = tempfile.mkstemp(
        prefix=".manifesto_cvm.", suffix=".tmp", dir=caminho.parent
    )
    os.close(fd)
    temporario = Path(nome)
    try:
        with open(temporario, "w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_MANIFESTO)
            escritor.writeheader()
            escritor.writerows(ordenadas)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    except Exception:
        temporario.unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------- #
# Extração
# --------------------------------------------------------------------------- #


def membros_desejados(
    membros: list[str], demonstrativos: tuple[str, ...] = ("DRE", "BPA", "BPP")
) -> list[str]:
    """Seleciona só as demonstrações consolidadas (`_con_`) de interesse."""
    escolhidos = [
        nome
        for nome in membros
        if any(f"_{d}_con_" in nome for d in demonstrativos)
    ]
    return sorted(escolhidos)


def extrair_csvs(
    caminho_zip: Path,
    destino: Path,
    demonstrativos: tuple[str, ...] = ("DRE", "BPA", "BPP"),
) -> list[Path]:
    """Extrai os CSVs consolidados de interesse, com proteção contra zip slip."""
    membros = validar_zip(caminho_zip)
    alvos = membros_desejados(membros, demonstrativos)
    if not alvos:
        raise ValueError(
            f"{caminho_zip.name}: nenhum CSV consolidado de {demonstrativos}"
        )
    destino.mkdir(parents=True, exist_ok=True)
    raiz = destino.resolve()
    extraidos: list[Path] = []
    with zipfile.ZipFile(caminho_zip) as pacote:
        for nome in alvos:
            saida = (destino / Path(nome).name).resolve()
            if saida.parent != raiz:
                raise ValueError(f"membro escaparia do destino: {nome!r}")
            with pacote.open(nome) as origem, open(saida, "wb") as arquivo:
                while bloco := origem.read(1 << 20):
                    arquivo.write(bloco)
            extraidos.append(saida)
    return extraidos


# --------------------------------------------------------------------------- #
# Fluxo principal
# --------------------------------------------------------------------------- #


def baixar_cvm(
    anos: list[int],
    conjuntos: list[str],
    *,
    forcar: bool = False,
    aceitar_republicacao: bool = False,
    somente_verificar: bool = False,
    caminho_manifesto: Path = CAMINHO_MANIFESTO,
    dir_destino: Path = DIR_CVM_BRUTO,
) -> bool:
    """Devolve True se todos os ZIPs pedidos estão presentes e íntegros."""
    try:
        linhas = ler_manifesto(caminho_manifesto)
    except ValueError as exc:
        print(f"Manifesto inválido — {exc}")
        return False
    indice = {(linha["conjunto"], int(linha["ano"])): linha for linha in linhas}

    problemas: list[str] = []
    mudou = False
    sessao = _criar_sessao()
    try:
        for conjunto in conjuntos:
            for ano in anos:
                chave = (conjunto, ano)
                url = url_do_conjunto(conjunto, ano)
                destino = dir_destino / nome_do_arquivo(conjunto, ano)
                registrado = indice.get(chave)
                rotulo = f"{conjunto.upper()} {ano}"
                hash_pinado = (
                    registrado["hash_sha256"].strip().lower() if registrado else ""
                )

                if destino.is_file() and not forcar:
                    try:
                        validar_zip(destino)
                        local = sha256_do_arquivo(destino)
                    except Exception as exc:
                        print(f"  cópia local inválida de {rotulo}: {exc}")
                    else:
                        if not hash_pinado:
                            problemas.append(
                                f"{rotulo}: ZIP local sem hash no manifesto — "
                                "origem não comprovável; rode com --forcar para "
                                "recoletar da URL oficial"
                            )
                            continue
                        if local != hash_pinado:
                            problemas.append(
                                f"{rotulo}: HASH LOCAL DIVERGENTE — "
                                f"manifesto={hash_pinado[:12]}… local={local[:12]}…"
                            )
                            continue
                        print(f"  ok: {rotulo} (hash confirmado)")
                        continue

                if somente_verificar:
                    problemas.append(f"{rotulo}: ZIP ausente em {destino}")
                    continue

                temporario: Path | None = None
                try:
                    print(f"Baixando {rotulo} de {url} ...")
                    temporario = _baixar_para_temporario(url, destino, sessao)
                    baixado = sha256_do_arquivo(temporario)
                    if hash_pinado and baixado != hash_pinado:
                        if not aceitar_republicacao:
                            raise ValueError(
                                "HASH DIVERGENTE do manifesto — o portal "
                                "republicou o pacote. Isso muda o gabarito da "
                                "classe `cvm` depois do congelamento (risco 15d). "
                                "Confira o que mudou e rode com "
                                f"--aceitar-republicacao. manifesto="
                                f"{hash_pinado[:12]}… baixado={baixado[:12]}…"
                            )
                        print(
                            f"  republicação ACEITA explicitamente para {rotulo}: "
                            f"{hash_pinado[:12]}… -> {baixado[:12]}…"
                        )
                    tamanho = temporario.stat().st_size
                    os.replace(temporario, destino)
                    temporario = None
                except Exception as exc:
                    if temporario is not None:
                        temporario.unlink(missing_ok=True)
                    problemas.append(f"{rotulo}: {exc}")
                    continue

                registro = {
                    "conjunto": conjunto,
                    "ano": str(ano),
                    "arquivo": destino.name,
                    "url": url,
                    "data_download": date.today().isoformat(),
                    "tamanho_bytes": str(tamanho),
                    "hash_sha256": baixado,
                }
                if registrado != registro:
                    indice[chave] = registro
                    mudou = True
                print(f"  hash registrado para {rotulo}: {baixado[:12]}…")
    finally:
        sessao.close()

    if mudou:
        try:
            salvar_manifesto(list(indice.values()), caminho_manifesto)
        except OSError as exc:
            problemas.append(f"falha ao gravar o manifesto — {exc}")
        else:
            print(f"Manifesto atualizado: {caminho_manifesto}")

    for problema in problemas:
        print(f"PROBLEMA: {problema}")
    return not problemas


def _lista_de_anos(bruto: str) -> list[int]:
    anos = sorted({int(parte.strip()) for parte in bruto.split(",") if parte.strip()})
    if not anos:
        raise argparse.ArgumentTypeError("informe ao menos um ano")
    for ano in anos:
        if not ANO_MINIMO <= ano <= ANO_MAXIMO:
            raise argparse.ArgumentTypeError(f"ano fora da faixa: {ano}")
    return anos


def _lista_de_conjuntos(bruto: str) -> list[str]:
    conjuntos = [parte.strip().lower() for parte in bruto.split(",") if parte.strip()]
    desconhecidos = sorted(set(conjuntos) - set(CONJUNTOS))
    if desconhecidos:
        raise argparse.ArgumentTypeError(f"conjunto desconhecido: {desconhecidos}")
    return sorted(set(conjuntos))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--anos",
        type=_lista_de_anos,
        default=[2025, 2026],
        help="anos separados por vírgula (padrão: 2025,2026)",
    )
    parser.add_argument(
        "--conjuntos",
        type=_lista_de_conjuntos,
        default=list(CONJUNTOS),
        help="itr, dfp ou ambos (padrão: itr,dfp)",
    )
    parser.add_argument("--forcar", action="store_true", help="re-baixa mesmo se existe")
    parser.add_argument(
        "--aceitar-republicacao",
        action="store_true",
        help="aceita hash diferente do manifesto (decisão explícita, risco 15d)",
    )
    parser.add_argument(
        "--somente-verificar",
        action="store_true",
        help="confere hashes locais sem baixar nada",
    )
    args = parser.parse_args()
    sys.exit(
        0
        if baixar_cvm(
            args.anos,
            args.conjuntos,
            forcar=args.forcar,
            aceitar_republicacao=args.aceitar_republicacao,
            somente_verificar=args.somente_verificar,
        )
        else 1
    )
