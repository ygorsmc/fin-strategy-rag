"""Etapa 10 — treina o classificador de prejuízo em T+1 e publica as métricas.

Custo zero de API: lê o DuckDB local e treina em CPU. Não escreve no painel
(conexão somente-leitura) e não toca em nada do caminho interativo.

    python -m scripts.treinar_modelo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import Config
from src.dados_estruturados import abrir_conexao_somente_leitura
from src.modelo.construir_painel import COLUNAS_DESCARTADAS, construir_painel
from src.modelo.prever import contrastar_corpus_e_painel
from src.modelo.treinar import (
    GRUPO_SAZONAL,
    ablacao_walk_forward,
    avaliar_walk_forward,
    treinar_e_avaliar,
)

SAIDA_PADRAO = Path("artefatos/modelo/metricas.json")


def principal() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    analisador.add_argument("--painel", type=Path, default=None)
    analisador.add_argument(
        "--sem-walk-forward", action="store_true",
        help="pula a validação por fold (rápido, mas sem intervalo de confiança)",
    )
    argumentos = analisador.parse_args()

    config = Config()
    con = abrir_conexao_somente_leitura(config, argumentos.painel)
    try:
        painel = construir_painel(con)
        relatorio = treinar_e_avaliar(painel)
        relatorio.analises["contraste_corpus_painel"] = contrastar_corpus_e_painel(
            con
        ).como_dict()
        if not argumentos.sem_walk_forward:
            print("rodando walk-forward (um fold por trimestre)...")
            relatorio.analises["walk_forward"] = avaliar_walk_forward(painel)
            print("medindo a contribuição das features sazonais...")
            relatorio.analises["ablacao_sazonal"] = ablacao_walk_forward(
                painel, GRUPO_SAZONAL
            )
    finally:
        con.close()

    relatorio.analises["trimestres_usados"] = list(painel.trimestres_usados)
    relatorio.analises["trimestres_descartados"] = painel.trimestres_descartados
    relatorio.analises["colunas_descartadas"] = COLUNAS_DESCARTADAS
    relatorio.observacoes = [
        "Split temporal; o limiar sai da validação, nunca do teste.",
        "Métrica prioritária é recall (5.10); limiar escolhido por F2.",
        "RN07: nenhuma saída por companhia nomeada é publicada.",
    ]
    relatorio.gravar(argumentos.saida)

    wf = relatorio.analises.get("walk_forward")
    if wf:
        print(f"\nWALK-FORWARD — {wf['n_folds']} folds (um por trimestre)")
        print(f"{'modelo':28s} {'AUC médio':>10s} {'desvio':>8s}")
        for nome, d in sorted(
            wf["resumo"].items(), key=lambda x: -x[1]["auc_medio"]
        ):
            print(f"{nome:28s} {d['auc_medio']:10.3f} {d['auc_desvio']:8.3f}")

    print(f"\nmétricas em {argumentos.saida}")
    print(json.dumps(relatorio.divisao, ensure_ascii=False, indent=2))
    print()
    cabecalho = f"{'modelo':32s} {'conj':10s} {'lim':>5s} {'rec':>6s} {'prec':>6s} {'F1':>6s} {'AUC':>6s}"
    print(cabecalho)
    for m in relatorio.metricas:
        auc = f"{m['roc_auc']:.3f}" if m["roc_auc"] is not None else "    -"
        print(
            f"{m['nome']:32s} {m['conjunto']:10s} {m['limiar']:5.2f} "
            f"{m['recall']:6.3f} {m['precisao']:6.3f} {m['f1']:6.3f} {auc:>6s}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(principal())
