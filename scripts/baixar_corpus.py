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
import sys
from datetime import date
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.config import CAMINHO_METADADOS_CORPUS, DIR_CORPUS_RAW  # noqa: E402
from src.ingestao import COLUNAS_METADADOS_CORPUS  # noqa: E402

TIMEOUT_S = 60


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _baixar(url: str, destino: Path) -> None:
    resposta = requests.get(url, timeout=TIMEOUT_S, stream=True)
    resposta.raise_for_status()
    with open(destino, "wb") as f:
        for bloco in resposta.iter_content(1 << 20):
            f.write(bloco)


def baixar_corpus(amostra: bool = False, forcar: bool = False) -> bool:
    """Devolve True se todos os documentos do manifesto estão íntegros."""
    with open(CAMINHO_METADADOS_CORPUS, newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    if not linhas:
        print(
            "Manifesto vazio — preencha corpus/metadados.csv com os releases "
            "(etapa 2 do AGENTS.md: 5 bancos × 4 trimestres, regra da interseção)."
        )
        return False
    if amostra:
        linhas_alvo = linhas[:1]  # 1 banco × 1 trimestre (smoke test, RNF01)
    else:
        linhas_alvo = linhas

    DIR_CORPUS_RAW.mkdir(parents=True, exist_ok=True)
    problemas: list[str] = []
    manifesto_mudou = False

    for linha in linhas_alvo:
        destino = DIR_CORPUS_RAW / f"{linha['documento']}.pdf"
        rotulo = f"{linha['empresa']} {linha['trimestre']} ({linha['documento']})"

        if not destino.exists() or forcar:
            try:
                print(f"Baixando {rotulo} ...")
                _baixar(linha["url"], destino)
            except requests.RequestException as exc:
                problemas.append(f"{rotulo}: falha de download — {exc}")
                continue

        hash_local = _sha256(destino)
        if not linha["hash_sha256"]:
            linha["hash_sha256"] = hash_local
            linha["data_coleta"] = linha["data_coleta"] or date.today().isoformat()
            manifesto_mudou = True
            print(f"  hash registrado para {rotulo}: {hash_local[:12]}…")
        elif linha["hash_sha256"] != hash_local:
            problemas.append(
                f"{rotulo}: HASH DIVERGENTE — manifesto={linha['hash_sha256'][:12]}… "
                f"local={hash_local[:12]}… (documento mudou na origem?)"
            )
        else:
            print(f"  ok: {rotulo}")

    if manifesto_mudou:
        with open(CAMINHO_METADADOS_CORPUS, "w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=list(COLUNAS_METADADOS_CORPUS))
            escritor.writeheader()
            escritor.writerows(linhas)
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
