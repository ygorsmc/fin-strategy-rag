"""Baixa as demonstrações financeiras consolidadas em IFRS — evidência do G4.

**Por que estes documentos existem separados do corpus.** O gate G4 compara o
lucro que o mapa semântico resolve no painel da CVM contra uma linha contábil
publicada. Para Itaú e Bradesco a âncora está dentro do próprio corpus: o
relatório gerencial deles publica a ponte BRGAAP→IFRS. Para **BB, BTG e
Santander** não está — o relatório gerencial parte do BRGAAP/COSIF, e o arquivo
da CVM está em IFRS (Resolução CMN 4.818/2020). Comparar as duas seria comparar
bases diferentes, e foi por isso que esses três ficaram **sem âncora** na
primeira execução do gate.

A CMN 4.818/2020 obriga cada um deles a publicar demonstrações consolidadas em
IFRS **em separado**, e é isso que este script baixa: a mesma base contábil do
arquivo da CVM, impressa por uma peça que não é o release.

**Estes PDFs NÃO entram em `corpus/metadados.csv`.** O corpus está congelado em
20 documentos e o hash dele entra na identidade do índice vetorial (RNF09):
acrescentar linha ali invalidaria índice, fingerprint e cache de avaliação sem
que uma só resposta mudasse. Eles são evidência de gate e vivem em manifesto
próprio, `corpus/ifrs/manifesto_ifrs.csv`, com a mesma disciplina do resto —
URL, data de download e SHA-256 por documento. Os PDFs ficam fora do Git.

O 1T2025 é baixado junto com a janela do corpus **de propósito**: as
demonstrações intermediárias publicam o acumulado do exercício, e o 2T isolado
só existe como `1S25 − 1T25`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import RAIZ_PROJETO  # noqa: E402

DIR_IFRS = RAIZ_PROJETO / "corpus" / "ifrs"
DIR_PDF = DIR_IFRS / "raw"
MANIFESTO = DIR_IFRS / "manifesto_ifrs.csv"

CABECALHO_MANIFESTO: tuple[str, ...] = (
    "empresa",
    "cd_cvm",
    "periodo",
    "documento",
    "titulo_publicado",
    "arquivo",
    "url",
    "data_download",
    "tamanho_bytes",
    "hash_sha256",
)

# Períodos baixados: a janela do corpus mais o 1T2025, que é a base do 2T
# isolado. `4T2025` é o exercício completo — a peça anual —, e o trimestre
# isolado sai da diferença contra o 3T, exatamente como o painel deriva o dele.
PERIODOS: tuple[str, ...] = ("1T2025", "2T2025", "3T2025", "4T2025", "1T2026")

CABECALHOS_HTTP = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
}


@dataclass(frozen=True)
class FonteIFRS:
    """Um documento IFRS a baixar, já resolvido para URL direta."""

    empresa: str
    cd_cvm: str
    periodo: str
    titulo_publicado: str
    url: str

    @property
    def documento(self) -> str:
        return f"{self.empresa.lower()}_ifrs_{self.periodo}"

    @property
    def arquivo(self) -> str:
        return f"{self.documento}.pdf"


# --------------------------------------------------------------------------- #
# Descoberta — cada banco publica por uma via diferente
# --------------------------------------------------------------------------- #

# Portal de RI da MZiQ (BB e Santander): o catálogo responde a um POST público,
# sem chave. `language` é `pt_BR` — `pt-BR` é recusado pela validação do serviço.
API_MZIQ = "https://apicatalog.mziq.com/filemanager/company/{empresa}/filter/categories/year/meta"

MZIQ: dict[str, tuple[str, str]] = {
    # empresa -> (id da companhia no catálogo, nome interno da categoria)
    "BB": (
        "5760dff3-15e1-4962-9e81-322a0b3d0bbd",
        "downloads-demonstracoes-contabeis-em-ifrs",
    ),
    "SANTANDER": (
        "a2595886-9fbb-4339-8a38-71d6ce7c7d36",
        "divulgacao_de_resultados_demonstracoes_financeiras_ifrs",
    ),
}

# Portal de RI do BTG, em outra plataforma. A categoria devolve todos os
# documentos financeiros do ano; o filtro por título vem depois.
API_BTG = "https://api.solutions-ir.com/v2/files/{sitio}"
SITIO_BTG = "78a5a309-f13a-41ed-a7d1-814e37b63259"
CATEGORIA_BTG = "informacoes_financeiras"

CD_CVM: dict[str, str] = {"BB": "001023", "BTG": "022616", "SANTANDER": "020532"}


def _periodo_de(trimestre: int, ano: int) -> str:
    return f"{trimestre}T{ano}"


def _json_http(url: str, corpo: dict | None = None) -> dict:
    dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
    cabecalhos = dict(CABECALHOS_HTTP)
    if dados is not None:
        cabecalhos["Content-Type"] = "application/json"
    requisicao = urllib.request.Request(url, data=dados, headers=cabecalhos)
    with urllib.request.urlopen(requisicao, timeout=120) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def descobrir_mziq(empresa: str) -> tuple[FonteIFRS, ...]:
    """Lista as demonstrações em IFRS publicadas no portal de RI (MZiQ)."""
    identificador, categoria = MZIQ[empresa]
    fontes: list[FonteIFRS] = []
    for ano in (2025, 2026):
        resposta = _json_http(
            API_MZIQ.format(empresa=identificador),
            {
                "year": ano,
                "categories": [categoria],
                "language": "pt_BR",
                "published": True,
            },
        )
        for meta in resposta["data"]["document_metas"]:
            periodo = _periodo_de(int(meta["file_quarter"]), int(meta["file_year"]))
            if periodo not in PERIODOS:
                continue
            fontes.append(
                FonteIFRS(
                    empresa=empresa,
                    cd_cvm=CD_CVM[empresa],
                    periodo=periodo,
                    titulo_publicado=meta["file_name_original"].strip(),
                    url=meta["file_url"],
                )
            )
    return tuple(fontes)


def descobrir_btg() -> tuple[FonteIFRS, ...]:
    """Lista as demonstrações consolidadas em IFRS publicadas pelo BTG.

    O catálogo do BTG traz, no mesmo trimestre, a peça em BRGAAP (`- Completa`)
    e a consolidada em IFRS. Só a segunda serve de âncora, e o filtro é pelo
    título publicado: pegar a errada devolveria número plausível e de outra base.
    """
    fontes: list[FonteIFRS] = []
    vistos: set[str] = set()
    for ano in (2025, 2026):
        url = (
            f"{API_BTG.format(sitio=SITIO_BTG)}?language=pt"
            f"&categories={CATEGORIA_BTG}&date={ano}-01-02"
        )
        resposta = _json_http(url)
        for itens in resposta.get("categories", {}).values():
            for item in itens:
                titulo = " ".join(item["title"].split())
                if "IFRS" not in titulo.upper() or not titulo.lower().endswith("ifrs"):
                    continue
                referencia = item["refDate"][:10]
                mes = int(referencia[5:7])
                periodo = _periodo_de((mes - 1) // 3 + 1, int(referencia[:4]))
                if periodo not in PERIODOS or periodo in vistos:
                    continue
                vistos.add(periodo)
                fontes.append(
                    FonteIFRS(
                        empresa="BTG",
                        cd_cvm=CD_CVM["BTG"],
                        periodo=periodo,
                        titulo_publicado=titulo,
                        url=item["url"],
                    )
                )
    return tuple(fontes)


def descobrir_todas() -> tuple[FonteIFRS, ...]:
    fontes = list(descobrir_mziq("BB")) + list(descobrir_btg())
    fontes += list(descobrir_mziq("SANTANDER"))
    return tuple(sorted(fontes, key=lambda f: (f.empresa, f.periodo)))


# --------------------------------------------------------------------------- #
# Download e manifesto
# --------------------------------------------------------------------------- #


def sha256_do_arquivo(caminho: Path) -> str:
    digestor = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            digestor.update(bloco)
    return digestor.hexdigest()


def baixar(fonte: FonteIFRS, destino: Path, tentativas: int = 4) -> None:
    """Baixa o PDF, com repetição em falha transitória do portal.

    O conteúdo é conferido como PDF **antes** de tocar o disco: um HTML de erro
    gravado com extensão `.pdf` viraria depois um documento sem número, e o
    diagnóstico apareceria a três etapas de distância da causa.
    """
    ultimo: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        try:
            requisicao = urllib.request.Request(fonte.url, headers=CABECALHOS_HTTP)
            with urllib.request.urlopen(requisicao, timeout=300) as resposta:
                conteudo = resposta.read()
            if not conteudo.startswith(b"%PDF"):
                raise RuntimeError(
                    f"{fonte.documento}: resposta não é PDF ({fonte.url})"
                )
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(conteudo)
            return
        except (urllib.error.URLError, TimeoutError, RuntimeError) as erro:
            ultimo = erro
            print(f"  tentativa {tentativa}/{tentativas} falhou: {erro}")
            time.sleep(3 * tentativa)
    raise RuntimeError(f"{fonte.documento}: download falhou — {ultimo}")


def ler_manifesto(caminho: Path = MANIFESTO) -> list[dict[str, str]]:
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def escrever_manifesto(linhas: list[dict[str, str]], caminho: Path = MANIFESTO) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(CABECALHO_MANIFESTO))
        escritor.writeheader()
        for linha in sorted(linhas, key=lambda x: (x["empresa"], x["periodo"])):
            escritor.writerow(linha)


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--forcar",
        action="store_true",
        help="rebaixa mesmo se o PDF já existir com o hash do manifesto",
    )
    argumentos = analisador.parse_args()

    fontes = descobrir_todas()
    faltando = {
        (empresa, periodo)
        for empresa in CD_CVM
        for periodo in PERIODOS
    } - {(f.empresa, f.periodo) for f in fontes}

    manifesto = {(l["empresa"], l["periodo"]): l for l in ler_manifesto()}
    hoje = date.today().isoformat()
    for fonte in fontes:
        destino = DIR_PDF / fonte.arquivo
        anterior = manifesto.get((fonte.empresa, fonte.periodo))
        if destino.exists() and anterior and not argumentos.forcar:
            atual = sha256_do_arquivo(destino)
            if atual == anterior["hash_sha256"]:
                print(f"= {fonte.documento} (hash confere, não rebaixa)")
                continue
            print(f"! {fonte.documento}: hash local diverge do manifesto — rebaixando")
        baixar(fonte, destino)
        digest = sha256_do_arquivo(destino)
        if anterior and anterior["hash_sha256"] != digest:
            # O portal republica: registrar em vez de sobrescrever em silêncio.
            print(
                f"! {fonte.documento}: publicação mudou "
                f"({anterior['hash_sha256'][:12]} → {digest[:12]})"
            )
        manifesto[(fonte.empresa, fonte.periodo)] = {
            "empresa": fonte.empresa,
            "cd_cvm": fonte.cd_cvm,
            "periodo": fonte.periodo,
            "documento": fonte.documento,
            "titulo_publicado": fonte.titulo_publicado,
            "arquivo": fonte.arquivo,
            "url": fonte.url,
            "data_download": hoje,
            "tamanho_bytes": str(destino.stat().st_size),
            "hash_sha256": digest,
        }
        print(f"+ {fonte.documento} · {destino.stat().st_size} B · {digest[:12]}")

    escrever_manifesto(list(manifesto.values()))
    print(f"\nManifesto: {MANIFESTO} ({len(manifesto)} documentos)")
    for empresa, periodo in sorted(faltando):
        print(f"AUSENTE: {empresa} {periodo} — não publicado no portal de RI")
    return 1 if faltando else 0


if __name__ == "__main__":
    raise SystemExit(main())
