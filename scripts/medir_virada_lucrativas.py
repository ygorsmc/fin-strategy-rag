"""O modelo antecipa QUANDO uma companhia lucrativa vira? Medição em CPU.

O relatório da Etapa 2 registra o ponto fraco: no painel inteiro o AUC
dentro da companhia é 0,663, então o modelo separa QUAIS companhias vivem em
prejuízo, não o trimestre em que uma lucrativa vira. O ajuste proposto foi
medir à parte as companhias hoje lucrativas, onde a regra de persistência é
muda e a virada é o único evento possível.

O recorte já tinha AUC agregado (0,8315, alvo do produto, `robustez.json`).
Faltava o que responde à pergunta: o AUC dentro da companhia no recorte, e o
mesmo número para os baselines triviais, nas mesmas linhas.

**Regra de leitura, fixada antes de rodar.** Alvo do produto (prejuízo em
T+1 e T+2), recorte `prejuizo_em_t == 0`, walk-forward com purga. O modelo
"antecipa o momento da virada" só se o IC95% do AUC intra-companhia
(bootstrap por companhia, §4.4 regra 8) ficar inteiro acima de 0,5 **e**
acima do AUC intra-companhia pontual de `taxa_prejuizos_4t`, o melhor
baseline do projeto. Qualquer outro desfecho se lê como "ordena companhias,
não o momento" também no recorte.

    python -m scripts.medir_virada_lucrativas --painel artefatos/cvm_treino.duckdb

Custo de API: zero.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.modelo.construir_painel import COLUNAS_FEATURES, construir_painel  # noqa: E402
from src.modelo.treinar import (  # noqa: E402
    SEMENTE,
    comparar_pareado,
    construir_gradient_boosting,
    dividir_walk_forward,
    escore_identidade_implementavel,
    metricas_de_ranqueamento,
)

ESCORES = ("modelo", "taxa_prejuizos_4t", "identidade_implementavel")
MINIMO_POSITIVOS_FOLD = 5
N_BOOTSTRAP = 2000


def pontuar(painel) -> pd.DataFrame:
    """Teste de todos os folds, com o modelo e os dois baselines lado a lado."""
    colunas = list(COLUNAS_FEATURES)
    partes = []
    for indice, divisao in enumerate(dividir_walk_forward(painel)):
        modelo = construir_gradient_boosting()
        modelo.fit(divisao.treino[colunas], divisao.treino["rotulo"].to_numpy(int))
        parte = divisao.teste.copy()
        parte["fold"] = indice
        parte["modelo"] = modelo.predict_proba(divisao.teste[colunas])[:, 1]
        parte["identidade_implementavel"] = escore_identidade_implementavel(
            divisao.treino, divisao.teste
        )
        parte["taxa_prejuizos_4t"] = divisao.teste["taxa_prejuizos_4t"].astype(float)
        partes.append(parte)
    return pd.concat(partes, ignore_index=True)


def _pares_por_companhia(dados: pd.DataFrame, coluna: str) -> dict:
    """(concordantes + ½ empates, total de pares) por companhia com as duas classes."""
    saida = {}
    for cd_cvm, grupo in dados.groupby("cd_cvm"):
        y = grupo["rotulo"].to_numpy(dtype=int)
        if len(np.unique(y)) < 2:
            continue
        escore = grupo[coluna].to_numpy(dtype=float)
        escore = np.nan_to_num(escore, nan=-1.0)
        diferenca = escore[y == 1][:, None] - escore[y == 0][None, :]
        saida[cd_cvm] = (
            float((diferenca > 0).sum() + 0.5 * (diferenca == 0).sum()),
            int(diferenca.size),
        )
    return saida


def auc_intra(dados: pd.DataFrame, coluna: str, rng: np.random.Generator) -> dict:
    pares = _pares_por_companhia(dados, coluna)
    if not pares:
        return {"auc": None, "n_companhias": 0, "n_pares": 0}
    companhias = list(pares)
    acertos = np.array([pares[c][0] for c in companhias])
    totais = np.array([pares[c][1] for c in companhias])
    pontual = float(acertos.sum() / totais.sum())
    amostras = []
    for _ in range(N_BOOTSTRAP):
        sorteio = rng.integers(0, len(companhias), len(companhias))
        amostras.append(acertos[sorteio].sum() / totais[sorteio].sum())
    return {
        "auc": pontual,
        "ic95": [float(np.quantile(amostras, 0.025)), float(np.quantile(amostras, 0.975))],
        "n_companhias": len(companhias),
        "n_pares": int(totais.sum()),
    }


def agregado(dados: pd.DataFrame, coluna: str) -> dict:
    y = dados["rotulo"].to_numpy(dtype=int)
    escore = np.nan_to_num(dados[coluna].to_numpy(dtype=float), nan=-1.0)
    rank = metricas_de_ranqueamento(y, escore)
    return {
        "roc_auc": float(roc_auc_score(y, escore)),
        "lift_topo_10pct": rank["lift_topo_10pct"],
    }


def por_fold(dados: pd.DataFrame) -> list[dict]:
    linhas = []
    for fold, grupo in dados.groupby("fold"):
        y = grupo["rotulo"].to_numpy(dtype=int)
        if min(int(y.sum()), int(len(y) - y.sum())) < MINIMO_POSITIVOS_FOLD:
            continue
        linhas.append(
            {
                coluna: float(
                    roc_auc_score(y, np.nan_to_num(grupo[coluna].to_numpy(float), nan=-1.0))
                )
                for coluna in ESCORES
            }
        )
    return linhas


def medir(pontuado: pd.DataFrame) -> dict:
    rng = np.random.default_rng(SEMENTE)
    lucrativas = pontuado[pontuado["prejuizo_em_t"] == 0]
    estaveis = lucrativas[lucrativas["taxa_prejuizos_4t"] == 0]
    folds = por_fold(lucrativas)
    intra = {coluna: auc_intra(lucrativas, coluna, rng) for coluna in ESCORES}
    ic_modelo = intra["modelo"].get("ic95") or [None, None]
    referencia = intra["taxa_prejuizos_4t"]["auc"]
    antecipa = (
        ic_modelo[0] is not None
        and referencia is not None
        and ic_modelo[0] > 0.5
        and ic_modelo[0] > referencia
    )
    return {
        "recorte": "prejuizo_em_t == 0 (hoje lucrativas), alvo T+1 e T+2",
        "n_observacoes": int(len(lucrativas)),
        "n_eventos": int(lucrativas["rotulo"].sum()),
        "taxa_base": float(lucrativas["rotulo"].mean()),
        "agregado_empilhado": {c: agregado(lucrativas, c) for c in ESCORES},
        "por_fold": {
            "n_folds_com_eventos_suficientes": len(folds),
            "minimo_por_classe": MINIMO_POSITIVOS_FOLD,
            "modelo_menos_taxa_prejuizos_4t": comparar_pareado(
                folds, "modelo", "taxa_prejuizos_4t"
            ),
            "modelo_menos_identidade": comparar_pareado(
                folds, "modelo", "identidade_implementavel"
            ),
        },
        "intra_companhia": intra,
        "sem_prejuizo_no_ultimo_ano": {
            "n_observacoes": int(len(estaveis)),
            "n_eventos": int(estaveis["rotulo"].sum()),
            "taxa_base": float(estaveis["rotulo"].mean()) if len(estaveis) else None,
            "agregado_modelo": agregado(estaveis, "modelo")
            if estaveis["rotulo"].nunique() == 2
            else None,
            "intra_companhia_modelo": auc_intra(estaveis, "modelo", rng),
        },
        "regra_de_leitura": (
            "antecipa o momento só se o IC95% do AUC intra-companhia do modelo "
            "ficar inteiro acima de 0,5 e acima do AUC intra-companhia pontual "
            "de taxa_prejuizos_4t"
        ),
        "veredito": (
            "antecipa o momento da virada no recorte"
            if antecipa
            else "ordena companhias, não o momento, também no recorte"
        ),
    }


def principal() -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--painel", type=Path, required=True)
    analisador.add_argument(
        "--saida", type=Path, default=Path("artefatos/modelo/virada_lucrativas.json")
    )
    argumentos = analisador.parse_args()
    con = duckdb.connect(str(argumentos.painel), read_only=True)
    try:
        painel = construir_painel(con, trimestres_consecutivos=2)
    finally:
        con.close()
    resultado = medir(pontuar(painel))
    resultado["_meta"] = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "painel": argumentos.painel.name,
        "n_bootstrap": N_BOOTSTRAP,
        "semente": SEMENTE,
        "custo_usd": 0.0,
    }
    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    argumentos.saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in resultado.items() if k != "_meta"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(principal())
