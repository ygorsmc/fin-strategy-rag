"""Executa as 10 perguntas fixas 3× sem publicar métricas finais parciais."""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.auditoria import (  # noqa: E402
    consolidar_estabilidade,
    validar_plano_estabilidade,
)
from src.avaliacao import (  # noqa: E402
    _calcular_fingerprint,
    _carregar_checkpoint,
    executar_avaliacao,
)
from src.bloqueio import bloqueio_exclusivo  # noqa: E402
from src.config import (  # noqa: E402
    DIR_INDICE_VETORIAL,
    DIR_LOGS_EXECUCOES,
    DIR_RESULTADOS_AVALIACAO,
    carregar_config,
)
from src.geracao import fabricar_provedor_llm  # noqa: E402
from src.indexacao import (  # noqa: E402
    calcular_hash_corpus_atual_para_indice,
    carregar_indice_bm25,
    carregar_indice_chroma,
    fabricar_provedor_embeddings,
)
from src.recuperacao import Estrategia, Recuperador  # noqa: E402


def _custo_checkpoint(caminho: Path, fingerprint: str) -> float:
    itens = _carregar_checkpoint(caminho, fingerprint)
    if any(item.custo_usd is None for item in itens):
        raise ValueError("Checkpoint contém custo não auditável.")
    return sum(float(item.custo_usd) for item in itens)


def _perguntas_na_ordem_canonica(perguntas, pergunta_ids: list[str]):
    """Replica a ordem do CSV usada por ``executar_avaliacao``."""
    ids_selecionados = set(pergunta_ids)
    return [
        pergunta for pergunta in perguntas if pergunta.id in ids_selecionados
    ]


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--permitir-api-paga", action="store_true")
    parser.add_argument(
        "--dir-resultados",
        type=Path,
        default=DIR_RESULTADOS_AVALIACAO,
    )
    parser.add_argument("--dir-logs", type=Path, default=DIR_LOGS_EXECUCOES)
    args = parser.parse_args(argv)
    config = carregar_config()
    if config.llm_provider != "ollama" and not args.permitir_api_paga:
        print(
            "FALHOU: provedor externo exige --permitir-api-paga após revisão "
            "do escopo 10×3 e do teto agregado."
        )
        return 1
    if config.embedding_provider in {"openai", "azure_openai"}:
        print(
            "FALHOU: embeddings externos não integram o journal/teto da "
            "avaliação."
        )
        return 1
    try:
        perguntas_teste, fingerprint_base, estrategia, pergunta_ids = (
            validar_plano_estabilidade(config, args.dir_resultados)
        )
        perguntas = _perguntas_na_ordem_canonica(
            perguntas_teste, pergunta_ids
        )

        caminho_lock = (
            DIR_INDICE_VETORIAL.parent
            / f".{DIR_INDICE_VETORIAL.name}.lock"
        )
        with bloqueio_exclusivo(
            caminho_lock, "o snapshot integral durante estabilidade"
        ):
            embeddings = fabricar_provedor_embeddings(config)
            hash_corpus = calcular_hash_corpus_atual_para_indice(
                DIR_INDICE_VETORIAL,
                integral=True,
                bancos=config.bancos,
            )
            indice_vetorial = carregar_indice_chroma(
                embeddings,
                config=config,
                dir_indice=DIR_INDICE_VETORIAL,
                hash_corpus_esperado=hash_corpus,
            )
            bm25 = carregar_indice_bm25(
                config=config,
                dir_indice=DIR_INDICE_VETORIAL,
                hash_corpus_esperado=hash_corpus,
            )
            recuperador = Recuperador(
                config,
                indice_chroma=indice_vetorial,
                indice_bm25=bm25,
                provedor_embeddings=embeddings,
                hash_corpus_esperado=hash_corpus,
            )
            provedor = fabricar_provedor_llm(config)
            fingerprints_rep = {
                repeticao: _calcular_fingerprint(
                    config,
                    perguntas,
                    provedor,
                    DIR_INDICE_VETORIAL,
                    repeticao_estabilidade=repeticao,
                )[0]
                for repeticao in (1, 2, 3)
            }
            custo_base = _custo_checkpoint(
                args.dir_resultados / "checkpoint_teste.jsonl",
                fingerprint_base,
            )
            custos_rep = {
                repeticao: _custo_checkpoint(
                    args.dir_resultados
                    / f"checkpoint_estabilidade_{repeticao}.jsonl",
                    fingerprint,
                )
                for repeticao, fingerprint in fingerprints_rep.items()
            }
            for repeticao in (1, 2, 3):
                gasto_fora_da_repeticao = custo_base + sum(
                    custo
                    for outra, custo in custos_rep.items()
                    if outra != repeticao
                )
                teto_desta_repeticao = (
                    config.orcamento_teto_usd - gasto_fora_da_repeticao
                )
                if (
                    not math.isfinite(teto_desta_repeticao)
                    or teto_desta_repeticao <= 0
                ):
                    raise ValueError(
                        "Teto agregado esgotado antes das três repetições."
                    )
                executar_avaliacao(
                    replace(
                        config,
                        orcamento_teto_usd=teto_desta_repeticao,
                    ),
                    recuperador,
                    provedor,
                    [estrategia],
                    conjunto="teste",
                    dir_checkpoint=args.dir_resultados,
                    dir_logs=args.dir_logs,
                    pergunta_ids=pergunta_ids,
                    dir_indice_identidade=DIR_INDICE_VETORIAL,
                    repeticao_estabilidade=repeticao,
                )
                custos_rep[repeticao] = _custo_checkpoint(
                    args.dir_resultados
                    / f"checkpoint_estabilidade_{repeticao}.jsonl",
                    fingerprints_rep[repeticao],
                )
        caminho = consolidar_estabilidade(config, args.dir_resultados)
        print(f"Estabilidade 10×3 consolidada em {caminho}")
        return 0
    except Exception as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(principal())
