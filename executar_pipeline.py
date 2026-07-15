"""Orquestrador único do pipeline (RNF01) — `python executar_pipeline.py`.

Etapas, na ordem do AGENTS.md: testes (pytest) -> ingestão/qualidade ->
indexação -> avaliação (E0–E3) -> consolidação para o README. A flag
`--amostra` roda 1 banco × 1 trimestre para validar ponta a ponta em minutos.

Enquanto o boilerplate não é implementado, etapas pendentes são reportadas
como PENDENTE (NotImplementedError) sem derrubar o orquestrador — o resumo
final mostra exatamente o que falta.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

from src.config import Config, carregar_config  # noqa: E402


def etapa_testes(config: Config, amostra: bool) -> str:
    """Roda o pytest (regras de formatação/chunking — passa/falha).
    Métricas de avaliação NÃO vivem aqui (honestidade de avaliação, AGENTS §3)."""
    resultado = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=RAIZ, check=False
    )
    if resultado.returncode != 0:
        raise RuntimeError("pytest falhou — corrija antes de seguir")
    return "pytest ok"


def etapa_ingestao(config: Config, amostra: bool) -> str:
    from src.ingestao import ingerir_corpus

    chunks = ingerir_corpus(config, amostra=amostra)
    return f"{len(chunks)} chunks gerados e validados"


def etapa_indexacao(config: Config, amostra: bool) -> str:
    from src.indexacao import (
        construir_indice_bm25,
        construir_indice_faiss,
        fabricar_provedor_embeddings,
    )
    from src.ingestao import ingerir_corpus

    chunks = ingerir_corpus(config, amostra=amostra)
    provedor = fabricar_provedor_embeddings(config)
    construir_indice_bm25(chunks)
    metadados = construir_indice_faiss(chunks, provedor, hash_corpus="")
    return f"índices construídos ({metadados.n_chunks} chunks, {metadados.modelo})"


def etapa_avaliacao(config: Config, amostra: bool) -> str:
    from src.avaliacao import executar_avaliacao
    from src.geracao import fabricar_provedor_llm
    from src.recuperacao import Estrategia, Recuperador

    estrategias = [Estrategia.CLOSED_BOOK, Estrategia.KEYWORD, Estrategia.SEMANTICA]
    metricas = executar_avaliacao(
        config,
        Recuperador(config),
        fabricar_provedor_llm(config),
        estrategias,
        conjunto="dev" if amostra else "teste",
    )
    return f"avaliação concluída: {len(metricas)} estratégias"


ETAPAS = {
    "testes": etapa_testes,
    "ingestao": etapa_ingestao,
    "indexacao": etapa_indexacao,
    "avaliacao": etapa_avaliacao,
}


def principal() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--amostra",
        action="store_true",
        help="smoke test: 1 banco × 1 trimestre, conjunto dev (RNF01)",
    )
    parser.add_argument(
        "--etapa",
        choices=sorted(ETAPAS),
        action="append",
        help="roda só a(s) etapa(s) indicada(s); padrão: todas, em ordem",
    )
    args = parser.parse_args()

    config = carregar_config()
    nomes = args.etapa or list(ETAPAS)
    resumo: list[tuple[str, str, str]] = []

    for nome in nomes:
        print(f"\n=== Etapa: {nome} {'(amostra)' if args.amostra else ''} ===")
        try:
            detalhe = ETAPAS[nome](config, args.amostra)
            resumo.append((nome, "OK", detalhe))
        except NotImplementedError as exc:
            resumo.append((nome, "PENDENTE", str(exc)))
            print(f"PENDENTE: {exc}")
        except Exception as exc:
            resumo.append((nome, "FALHOU", f"{type(exc).__name__}: {exc}"))
            print(f"FALHOU: {exc}")

    print("\n=== Resumo do pipeline ===")
    for nome, status, detalhe in resumo:
        print(f"  {status:8s} {nome:12s} {detalhe}")
    return 1 if any(s == "FALHOU" for _, s, _ in resumo) else 0


if __name__ == "__main__":
    sys.exit(principal())
