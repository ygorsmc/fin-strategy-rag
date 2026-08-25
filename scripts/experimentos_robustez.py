"""Segunda onda da etapa 10 — os apontamentos de robustez, todos medidos.

Cada bloco aqui existe porque uma crítica ao módulo ficou sem resposta
empírica. Nenhum deles altera `COLUNAS_FEATURES` por conta própria: medem, e a
promoção (ou a rejeição) fica registrada por escrito, como já aconteceu com as
features do O-score.

    python -m scripts.experimentos_robustez --painel artefatos/cvm_treino.duckdb

Custo de API: zero. Roda em CPU.
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
    GRUPO_SAZONAL,
    SEMENTE,
    avaliar,
    comparar_pareado,
    construir_gradient_boosting,
    desempenho_por_estado,
    desempenho_por_recorte,
    dividir_walk_forward,
    metricas_de_calibracao,
    pontuar_walk_forward,
)

#: Feature de controle setorial, computada pelo painel mas ainda FORA de
#: `COLUNAS_FEATURES`. A promoção depende do resultado deste script.
FEATURE_SETOR = "instituicao_financeira"


def _auc_por_fold(divisoes, colunas, fabrica=construir_gradient_boosting, rotulo="a"):
    """AUC de um modelo em cada fold, na ordem dos folds."""
    saida = []
    for divisao in divisoes:
        modelo = fabrica()
        modelo.fit(divisao.treino[colunas], divisao.treino["rotulo"].to_numpy(int))
        escore = modelo.predict_proba(divisao.teste[colunas])[:, 1]
        auc = avaliar(rotulo, divisao.teste["rotulo"].to_numpy(int), escore, limiar=0.5)
        saida.append(auc.roc_auc)
    return saida


def _emparelhar(nome_a, valores_a, nome_b, valores_b):
    """Monta o `por_fold` que `comparar_pareado` espera, alinhando por posição."""
    return [
        {nome_a: a, nome_b: b}
        for a, b in zip(valores_a, valores_b)
        if a is not None and b is not None
    ]


# --------------------------------------------------------------------------- #
# 1. Purga / embargo
# --------------------------------------------------------------------------- #


def medir_purga(painel, colunas):
    """Quanto o rótulo que atravessa a fronteira do fold estava inflando o AUC.

    Para alvo de 1 trimestre a purga é inócua por construção — e o resultado
    idêntico é justamente a contraprova de que ela não mexe no que não deve.
    """
    com = dividir_walk_forward(painel, purgar=True)
    sem = dividir_walk_forward(painel, purgar=False)
    # os folds são os mesmos trimestres nos dois casos; só o treino difere
    auc_com = _auc_por_fold(com, colunas, rotulo="com_purga")
    auc_sem = _auc_por_fold(sem, colunas, rotulo="sem_purga")
    pares = _emparelhar("com_purga", auc_com, "sem_purga", auc_sem)
    return {
        "n_folds": len(pares),
        "auc_com_purga": float(np.mean([p["com_purga"] for p in pares])),
        "auc_sem_purga": float(np.mean([p["sem_purga"] for p in pares])),
        "n_treino_medio_com": float(np.mean([len(d.treino) for d in com])),
        "n_treino_medio_sem": float(np.mean([len(d.treino) for d in sem])),
        "comparacao": comparar_pareado(pares, "com_purga", "sem_purga"),
    }


# --------------------------------------------------------------------------- #
# 2. Controle setorial
# --------------------------------------------------------------------------- #


def medir_importancia_permutacao(painel, colunas, *, n_repeticoes=15):
    """Quanto ESTE modelo já ajustado depende de cada feature.

    Não confundir com ablação: a permutação quebra a feature mantendo o modelo
    treinado com ela; a ablação retreina sem ela. Sob colinearidade as duas
    discordam de propósito — `taxa_prejuizos_4t` domina a permutação e, quando
    removida de verdade, é parcialmente substituída por `taxa_prejuizos_ate_t`.
    Medir só uma das duas leva a conclusão errada.

    Existe aqui porque o relatório de 2026-08-24 citava estes números vindos de
    um script descartável — exatamente a lacuna de reprodutibilidade que o
    projeto já corrigiu uma vez.
    """
    from sklearn.inspection import permutation_importance

    divisoes = dividir_walk_forward(painel)
    if not divisoes:
        return {}
    divisao = divisoes[-1]
    modelo = construir_gradient_boosting()
    modelo.fit(divisao.treino[colunas], divisao.treino["rotulo"].to_numpy(int))
    resultado = permutation_importance(
        modelo,
        divisao.teste[colunas],
        divisao.teste["rotulo"].to_numpy(int),
        n_repeats=n_repeticoes,
        random_state=SEMENTE,
        scoring="roc_auc",
    )
    return {
        "trimestre": divisao.trimestre_teste,
        "n_repeticoes": n_repeticoes,
        "aviso": (
            "fold único; mede dependência do modelo ajustado, não informação "
            "insubstituível — para isso use ablacao_walk_forward"
        ),
        "por_feature": {
            coluna: {
                "delta_auc_medio": float(resultado.importances_mean[indice]),
                "delta_auc_desvio": float(resultado.importances_std[indice]),
            }
            for indice, coluna in enumerate(colunas)
        },
    }


def medir_separacao_setorial(con):
    """`alavancagem` separa banco de não-banco por acidente? Quanto?

    Sustenta a conclusão de que o controle setorial explícito não acrescentou
    nada: o modelo já distinguia os dois grupos por essa via.
    """
    linhas = con.execute(
        """
        SELECT c.is_banco, count(*),
               median(i.alavancagem),
               quantile_cont(i.alavancagem, 0.25),
               quantile_cont(i.alavancagem, 0.75)
        FROM indicadores i JOIN companhias c USING (cd_cvm)
        WHERE i.alavancagem IS NOT NULL AND i.alavancagem BETWEEN 0 AND 100
        GROUP BY 1
        """
    ).fetchall()
    return {
        ("instituicao_financeira" if is_banco else "demais"): {
            "n": int(n),
            "mediana_alavancagem": float(mediana),
            "p25": float(p25),
            "p75": float(p75),
        }
        for is_banco, n, mediana, p25, p75 in linhas
    }


def medir_setor(painel, colunas):
    """`instituicao_financeira` acrescenta algo, ou `alavancagem` já dá conta?

    A hipótese veio de uma medição descritiva: porte é quase um interruptor em
    instituição financeira (0,6% de prejuízo acima de R$500 bi contra 29,6%
    abaixo de R$10 bi) e quase irrelevante nas demais (21,0% contra 37,5%).
    Isso é uma INTERAÇÃO porte × setor, e o modelo não tinha o setor. O que ele
    tinha era `alavancagem`, que separa os dois grupos por acidente (mediana
    8,8 contra 2,5) — daí a dúvida valer medição em vez de palpite.
    """
    divisoes = dividir_walk_forward(painel)
    sem = _auc_por_fold(divisoes, colunas, rotulo="sem_setor")
    com = _auc_por_fold(divisoes, [*colunas, FEATURE_SETOR], rotulo="com_setor")
    pares = _emparelhar("com_setor", com, "sem_setor", sem)
    return {
        "n_folds": len(pares),
        "auc_com_setor": float(np.mean([p["com_setor"] for p in pares])),
        "auc_sem_setor": float(np.mean([p["sem_setor"] for p in pares])),
        "comparacao": comparar_pareado(pares, "com_setor", "sem_setor"),
    }


# --------------------------------------------------------------------------- #
# 3. Calibração isotônica
# --------------------------------------------------------------------------- #


def medir_calibracao(painel, colunas):
    """Recalibra no trimestre de VALIDAÇÃO e mede no de teste.

    O trimestre de validação já é o conjunto reservado do desenho — é de onde
    sai o limiar. Recalibrar nele mantém a fronteira temporal: nada do teste
    entra no ajuste do calibrador. Usar validação cruzada interna sobre o
    treino misturaria trimestres e devolveria um calibrador de época errada.
    """
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.frozen import FrozenEstimator

    linhas = []
    for divisao in dividir_walk_forward(painel):
        y_teste = divisao.teste["rotulo"].to_numpy(int)
        modelo = construir_gradient_boosting()
        modelo.fit(divisao.treino[colunas], divisao.treino["rotulo"].to_numpy(int))
        cru = modelo.predict_proba(divisao.teste[colunas])[:, 1]

        linha = {
            "cru_brier": metricas_de_calibracao(y_teste, cru)["brier"],
            "cru_erro": metricas_de_calibracao(y_teste, cru)["erro_calibracao_esperado"],
            "cru_auc": avaliar("cru", y_teste, cru, limiar=0.5).roc_auc,
        }
        for metodo in ("isotonic", "sigmoid"):
            calibrador = CalibratedClassifierCV(
                FrozenEstimator(modelo), method=metodo
            )
            calibrador.fit(
                divisao.validacao[colunas],
                divisao.validacao["rotulo"].to_numpy(int),
            )
            escore = calibrador.predict_proba(divisao.teste[colunas])[:, 1]
            calib = metricas_de_calibracao(y_teste, escore)
            linha[f"{metodo}_brier"] = calib["brier"]
            linha[f"{metodo}_erro"] = calib["erro_calibracao_esperado"]
            linha[f"{metodo}_auc"] = avaliar(metodo, y_teste, escore, limiar=0.5).roc_auc
        linhas.append(linha)

    resumo = {
        chave: float(np.mean([linha[chave] for linha in linhas if linha[chave] is not None]))
        for chave in linhas[0]
    }
    resumo["n_folds"] = len(linhas)
    for metodo in ("isotonic", "sigmoid"):
        resumo[f"{metodo}_vs_cru_erro"] = comparar_pareado(
            linhas, f"{metodo}_erro", "cru_erro"
        )
        resumo[f"{metodo}_vs_cru_auc"] = comparar_pareado(
            linhas, f"{metodo}_auc", "cru_auc"
        )
    return resumo


# --------------------------------------------------------------------------- #
# 4. Biblioteca alternativa
# --------------------------------------------------------------------------- #


def _construir_lightgbm():
    from lightgbm import LGBMClassifier

    return LGBMClassifier(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=15,
        min_child_samples=20,
        reg_lambda=1.0,
        random_state=SEMENTE,
        verbose=-1,
    )


def medir_lightgbm(painel, colunas):
    """Troca de biblioteca rende alguma coisa, ou o teto é da tarefa?

    Com boosting e logística empatados e a busca de hiperparâmetros rendendo
    zero fora dos folds de ajuste, a expectativa era de ganho baixo. Expectativa
    não é medição — este bloco existe para fechar o buraco.
    """
    divisoes = dividir_walk_forward(painel)
    sk = _auc_por_fold(divisoes, colunas, rotulo="sklearn")
    lgb = _auc_por_fold(divisoes, colunas, _construir_lightgbm, rotulo="lightgbm")
    pares = _emparelhar("lightgbm", lgb, "sklearn", sk)
    return {
        "n_folds": len(pares),
        "auc_lightgbm": float(np.mean([p["lightgbm"] for p in pares])),
        "auc_sklearn": float(np.mean([p["sklearn"] for p in pares])),
        "comparacao": comparar_pareado(pares, "lightgbm", "sklearn"),
    }


# --------------------------------------------------------------------------- #
# 5. Confirmação do conjunto de features em folds não vistos
# --------------------------------------------------------------------------- #


def confirmar_features(painel, colunas, n_folds_decisao):
    """A decisão sobre as features valeu nos folds que ela NÃO viu?

    As sazonais foram mantidas e as do O-score removidas medindo os 47 folds —
    e o resultado foi publicado nesses mesmos 47. Isso é a mesma circularidade
    que a busca de hiperparâmetros teve, e lá a conferência em folds reservados
    mostrou que o ganho aparente era ruído de seleção. Aqui a decisão é
    reconferida nos folds recentes, que ficam de fora da parte "de decisão".
    """
    divisoes = dividir_walk_forward(painel)
    reduzido = [c for c in colunas if c not in set(GRUPO_SAZONAL)]
    blocos = {}
    for rotulo, recorte in (
        ("folds_da_decisao", divisoes[:n_folds_decisao]),
        ("folds_nao_vistos", divisoes[n_folds_decisao:]),
    ):
        if len(recorte) < 3:
            continue
        completo = _auc_por_fold(recorte, colunas, rotulo="completo")
        sem = _auc_por_fold(recorte, reduzido, rotulo="reduzido")
        pares = _emparelhar("completo", completo, "reduzido", sem)
        blocos[rotulo] = {
            "n_folds": len(pares),
            "auc_completo": float(np.mean([p["completo"] for p in pares])),
            "auc_sem_sazonais": float(np.mean([p["reduzido"] for p in pares])),
            "comparacao": comparar_pareado(pares, "completo", "reduzido"),
        }
    return blocos


# --------------------------------------------------------------------------- #


def principal() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--painel", type=Path, required=True)
    analisador.add_argument(
        "--saida", type=Path, default=Path("artefatos/modelo/robustez.json")
    )
    analisador.add_argument("--folds-decisao", type=int, default=20)
    argumentos = analisador.parse_args()

    con = duckdb.connect(str(argumentos.painel), read_only=True)
    colunas = list(COLUNAS_FEATURES)
    saida: dict[str, object] = {}

    try:
        bancos = {
            linha[0]
            for linha in con.execute(
                "SELECT cd_cvm FROM companhias WHERE is_banco"
            ).fetchall()
        }
        porte = dict(
            con.execute(
                "SELECT cd_cvm, avg(ativo_total) FROM indicadores "
                "WHERE ativo_total IS NOT NULL GROUP BY 1"
            ).fetchall()
        )

        for n_consecutivos in (1, 2):
            rotulo = f"alvo_{n_consecutivos}t"
            print(f"\n=== {rotulo} ===")
            painel = construir_painel(con, trimestres_consecutivos=n_consecutivos)
            bloco: dict[str, object] = {
                "n_observacoes": painel.n_observacoes,
                "taxa_positivos": painel.taxa_positivos,
            }

            print("  purga/embargo...")
            bloco["purga"] = medir_purga(painel, colunas)
            print("  controle setorial...")
            bloco["setor"] = medir_setor(painel, colunas)
            bloco["separacao_setorial_por_alavancagem"] = medir_separacao_setorial(
                con
            )
            print("  importância por permutação...")
            bloco["importancia_permutacao"] = medir_importancia_permutacao(
                painel, colunas
            )
            print("  calibração...")
            bloco["calibracao"] = medir_calibracao(painel, colunas)
            print("  lightgbm...")
            bloco["lightgbm"] = medir_lightgbm(painel, colunas)
            print("  confirmação das features...")
            bloco["features_em_folds_nao_vistos"] = confirmar_features(
                painel, colunas, argumentos.folds_decisao
            )

            print("  desempenho por recorte...")
            pontuado = pontuar_walk_forward(painel)
            bloco["por_estado"] = desempenho_por_estado(pontuado)
            e_banco = pontuado["cd_cvm"].isin(bancos)
            ativo = pontuado["cd_cvm"].map(porte)
            lucrativa = pontuado["prejuizo_em_t"] == 0
            bloco["por_recorte"] = desempenho_por_recorte(
                pontuado,
                {
                    "painel_inteiro": pontuado["rotulo"].notna(),
                    "instituicoes_financeiras": e_banco,
                    "financeiras_acima_100bi": e_banco & (ativo >= 1e11),
                    "financeiras_abaixo_100bi": e_banco & (ativo < 1e11),
                    "nao_financeiras": ~e_banco,
                    "financeiras_lucrativas_hoje": e_banco & lucrativa,
                    "nao_financeiras_lucrativas_hoje": (~e_banco) & lucrativa,
                },
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
