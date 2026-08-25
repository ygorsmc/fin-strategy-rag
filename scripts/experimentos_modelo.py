"""Matriz de experimentos da etapa 10 — as sete revisões, SMOTE e o alvo novo.

Roda tudo sob o MESMO walk-forward (um fold por trimestre, treino sempre no
passado) para que as comparações sejam pareadas. Custo de API: zero.

    python -m scripts.experimentos_modelo --painel artefatos/cvm_treino.duckdb
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.modelo.construir_painel import COLUNAS_FEATURES, construir_painel  # noqa: E402
from src.modelo.treinar import (  # noqa: E402
    avaliar,
    comparar_pareado,
    construir_gradient_boosting,
    construir_gradient_boosting_com_smote,
    construir_gradient_boosting_imputado,
    construir_regressao_logistica,
    dividir_walk_forward,
    escolher_limiar_por_f2,
    escore_passeio_sazonal,
    escore_persistencia,
    metricas_de_calibracao,
    metricas_de_ranqueamento,
)

#: Grade pequena e declarada de antemão. A busca roda nos folds ANTIGOS e o
#: resultado é reportado nos RECENTES — separação temporal também no ajuste,
#: senão o "melhor" hiperparâmetro é escolhido olhando o que será reportado.
GRADE = (
    {"max_leaf_nodes": 15, "learning_rate": 0.05, "min_samples_leaf": 20},
    {"max_leaf_nodes": 31, "learning_rate": 0.05, "min_samples_leaf": 20},
    {"max_leaf_nodes": 15, "learning_rate": 0.10, "min_samples_leaf": 20},
    {"max_leaf_nodes": 63, "learning_rate": 0.05, "min_samples_leaf": 50},
    {"max_leaf_nodes": 31, "learning_rate": 0.02, "min_samples_leaf": 50},
)

CONSTRUTORES = {
    "boosting": construir_gradient_boosting,
    "boosting_imputado": construir_gradient_boosting_imputado,
    "boosting_smote": construir_gradient_boosting_com_smote,
    "logistica": construir_regressao_logistica,
}


def _por_fold(divisoes, colunas, somente_rotulo_arquivado=False):
    """AUC, ranqueamento e calibração de cada modelo em cada fold."""
    linhas = []
    for divisao in divisoes:
        teste = divisao.teste
        if somente_rotulo_arquivado:
            teste = teste[teste["origem_rotulo"] == "arquivado"]
            if len(teste) < 30 or teste["rotulo"].nunique() < 2:
                continue
        y_treino = divisao.treino["rotulo"].to_numpy(dtype=int)
        y_teste = teste["rotulo"].to_numpy(dtype=int)
        linha: dict[str, object] = {
            "trimestre_teste": divisao.trimestre_teste,
            "n_teste": len(teste),
        }

        for nome, escore in (
            ("baseline_persistencia", escore_persistencia(teste)),
            ("baseline_passeio_sazonal", escore_passeio_sazonal(teste)),
        ):
            metrica = avaliar(nome, y_teste, escore, limiar=0.5)
            if metrica.roc_auc is not None:
                linha[nome] = metrica.roc_auc

        for nome, fabrica in CONSTRUTORES.items():
            modelo = fabrica()
            modelo.fit(divisao.treino[colunas], y_treino)
            escore = modelo.predict_proba(teste[colunas])[:, 1]
            metrica = avaliar(nome, y_teste, escore, limiar=0.5)
            if metrica.roc_auc is None:
                continue
            linha[nome] = metrica.roc_auc
            rank = metricas_de_ranqueamento(y_teste, escore)
            calib = metricas_de_calibracao(y_teste, escore)
            linha[f"{nome}__precisao_topo_10pct"] = rank["precisao_topo_10pct"]
            linha[f"{nome}__lift_topo_10pct"] = rank["lift_topo_10pct"]
            linha[f"{nome}__recall_topo_20pct"] = rank["recall_topo_20pct"]
            linha[f"{nome}__brier"] = calib["brier"]
            linha[f"{nome}__erro_calibracao"] = calib["erro_calibracao_esperado"]
            # ponto de operação por F2, para medir quanto da base ele sinaliza
            escore_validacao = modelo.predict_proba(divisao.validacao[colunas])[:, 1]
            limiar = escolher_limiar_por_f2(
                divisao.validacao["rotulo"].to_numpy(dtype=int), escore_validacao
            )
            operacao = avaliar(nome, y_teste, escore, limiar=limiar)
            sinalizados = operacao.verdadeiro_positivo + operacao.falso_positivo
            linha[f"{nome}__fracao_sinalizada_f2"] = sinalizados / max(1, len(y_teste))
            linha[f"{nome}__recall_f2"] = operacao.recall
        linhas.append(linha)
    return linhas


def _resumir(por_fold, chaves):
    resumo = {}
    for chave in chaves:
        valores = [
            float(linha[chave]) for linha in por_fold if linha.get(chave) is not None
        ]
        if valores:
            resumo[chave] = {
                "media": float(np.mean(valores)),
                "desvio": float(np.std(valores, ddof=1)) if len(valores) > 1 else 0.0,
                "n_folds": len(valores),
            }
    return resumo


def _buscar_hiperparametros(divisoes, colunas, n_folds_ajuste):
    """Ajusta nos folds ANTIGOS e confere nos RECENTES.

    Reportar o vencedor da busca nos mesmos folds em que ele foi escolhido é
    circular: qualquer grade suficientemente grande "melhora" o número por
    seleção. A conferência nos folds que a busca não viu é o que separa ganho
    real de ruído de seleção.
    """
    ajuste = divisoes[:n_folds_ajuste]
    placar = []
    for config in GRADE:
        aucs = []
        for divisao in ajuste:
            modelo = construir_gradient_boosting()
            modelo.set_params(**config)
            modelo.fit(
                divisao.treino[colunas], divisao.treino["rotulo"].to_numpy(dtype=int)
            )
            escore = modelo.predict_proba(divisao.teste[colunas])[:, 1]
            metrica = avaliar("busca", divisao.teste["rotulo"].to_numpy(int), escore,
                              limiar=0.5)
            if metrica.roc_auc is not None:
                aucs.append(metrica.roc_auc)
        placar.append({"config": config, "auc_medio_ajuste": float(np.mean(aucs))})
    placar.sort(key=lambda x: -x["auc_medio_ajuste"])

    melhor = placar[0]["config"]
    padrao = {"max_leaf_nodes": 15, "learning_rate": 0.05, "min_samples_leaf": 20}
    por_fold = []
    for divisao in divisoes[n_folds_ajuste:]:
        y_treino = divisao.treino["rotulo"].to_numpy(dtype=int)
        y_teste = divisao.teste["rotulo"].to_numpy(dtype=int)
        linha = {}
        for rotulo, config in (("padrao", padrao), ("ajustado", melhor)):
            modelo = construir_gradient_boosting()
            modelo.set_params(**config)
            modelo.fit(divisao.treino[colunas], y_treino)
            escore = modelo.predict_proba(divisao.teste[colunas])[:, 1]
            metrica = avaliar(rotulo, y_teste, escore, limiar=0.5)
            if metrica.roc_auc is not None:
                linha[rotulo] = metrica.roc_auc
        if len(linha) == 2:
            por_fold.append(linha)

    return {
        "placar_nos_folds_de_ajuste": placar,
        "config_escolhida": melhor,
        "conferencia_em_folds_nao_vistos": {
            "n_folds": len(por_fold),
            "auc_padrao": float(np.mean([x["padrao"] for x in por_fold])),
            "auc_ajustado": float(np.mean([x["ajustado"] for x in por_fold])),
            "comparacao": comparar_pareado(por_fold, "ajustado", "padrao"),
        },
    }


def principal() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--painel", type=Path, required=True)
    analisador.add_argument(
        "--saida", type=Path, default=Path("artefatos/modelo/experimentos.json")
    )
    analisador.add_argument("--folds-ajuste", type=int, default=20)
    argumentos = analisador.parse_args()

    con = duckdb.connect(str(argumentos.painel), read_only=True)
    colunas = list(COLUNAS_FEATURES)
    saida: dict[str, object] = {}

    try:
        for n_consecutivos in (1, 2):
            rotulo = f"alvo_{n_consecutivos}t"
            print(f"\n=== {rotulo}: prejuízo em T+1..T+{n_consecutivos} ===")
            painel = construir_painel(
                con, trimestres_consecutivos=n_consecutivos
            )
            divisoes = dividir_walk_forward(painel)
            print(f"    {painel.n_observacoes} obs · {painel.taxa_positivos:.3f} "
                  f"positivos · {len(divisoes)} folds")

            por_fold = _por_fold(divisoes, colunas)
            nomes = list(CONSTRUTORES) + [
                "baseline_persistencia",
                "baseline_passeio_sazonal",
            ]
            chaves = list(nomes) + [
                f"{n}__{s}"
                for n in CONSTRUTORES
                for s in (
                    "precisao_topo_10pct", "lift_topo_10pct", "recall_topo_20pct",
                    "brier", "erro_calibracao", "fracao_sinalizada_f2", "recall_f2",
                )
            ]
            bloco: dict[str, object] = {
                "n_observacoes": painel.n_observacoes,
                "taxa_positivos": painel.taxa_positivos,
                "fracao_rotulo_derivado": float(
                    (painel.quadro["origem_rotulo"] == "derivado").mean()
                ),
                "n_folds": len(divisoes),
                "resumo": _resumir(por_fold, chaves),
                "comparacoes_pareadas": {},
            }
            for a, b in (
                ("boosting", "baseline_persistencia"),
                ("boosting", "logistica"),
                ("boosting_smote", "boosting_imputado"),
                ("boosting", "boosting_imputado"),
            ):
                teste = comparar_pareado(por_fold, a, b)
                if teste is not None:
                    bloco["comparacoes_pareadas"][f"{a} - {b}"] = teste

            # sensibilidade ao rótulo derivado (revisão 3)
            print("    sensibilidade ao rótulo derivado...")
            por_fold_arquivado = _por_fold(
                divisoes, colunas, somente_rotulo_arquivado=True
            )
            bloco["somente_rotulo_arquivado"] = {
                "n_folds": len(por_fold_arquivado),
                "resumo": _resumir(por_fold_arquivado, nomes),
            }

            if n_consecutivos == 1:
                print("    busca de hiperparâmetros (folds antigos)...")
                bloco["busca_hiperparametros"] = _buscar_hiperparametros(
                    divisoes, colunas, argumentos.folds_ajuste
                )
            saida[rotulo] = bloco
    finally:
        con.close()

    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    argumentos.saida.write_text(
        json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nescrito em {argumentos.saida}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(principal())
