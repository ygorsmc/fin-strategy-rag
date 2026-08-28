"""Audita o alvo do Rank 3 — deterioração de conversão de caixa — antes de ML.

As constantes aqui são as do pré-registro
`resultados/pre_registro_rank03_conversao_caixa_2026-08-27.md`, congeladas
ANTES de qualquer medição de desempenho. Mexer nelas depois de ver o resultado
cria o Rank 3-B, com pré-registro próprio — não é ajuste desta rodada.

O alvo marca a companhia cujo **Δaccrual em um ano** cai no quintil superior do
próprio trimestre, onde `accrual = ROA_ttm − FCO_ttm/ativo_médio` — quanto do
lucro **não** virou caixa. O quintil é transversal de propósito: um
normalizador da própria companhia (como o `sd8` do C1) é atributo dela e pode
fabricar baseline no nível da companhia, que foi o que reprovou T1 lá.

T1 roda PRIMEIRO e sozinho, sobre os QUATRO componentes que definem
mecanicamente o rótulo. Se reprovar, o script para sem treinar nada — é a
ordem que o pré-registro exige.

Uso::

    python -m scripts.auditar_rank03_conversao_caixa \
      --painel artefatos/cvm_treino.duckdb \
      --saida artefatos/rank03/auditoria_alvo.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from src.modelo.treinar import auc_within_companhia  # noqa: E402
from src.normalizacao import ordinal_trimestre  # noqa: E402

# --- constantes do pré-registro (congeladas) ------------------------------- #
LIMIAR_T1 = 0.15
LIMIAR_T2 = 0.12
GANHO_MINIMO_T3 = 0.02
CORTE_ATIVO_REAIS = 1_000_000_000.0
QUINTIS = 5
HORIZONTE = 4  # trimestres
CONTA_FCO = "6.01"

#: Os quatro componentes que definem mecanicamente o rótulo. TODOS vão a T1 —
#: a lição do C1 é que testar só o que parece o baseline é insuficiente.
COMPONENTES_T1 = ("accrual", "roa", "conversao", "ativo_medio")

#: Baselines triviais declarados antes de medir. B0 é o candidato a vencer:
#: accrual reverte à média por construção contábil.
BASELINES = {
    "B0_accrual_nivel": "accrual",
    "B1_conversao_negativa": "conversao_neg",
    "B2_roa": "roa",
    "B3_persistencia": "delta_accrual_passado",
    "B4_porte": "log_ativo",
}


def _carregar_base(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Lucro, ativo e FCO por companhia–trimestre, só não financeiras.

    O FCO vem de `fatos_contabeis` porque `indicadores` não tem fluxo de caixa.
    Usa-se o trimestre ISOLADO (`tipo_periodo='trimestral'`), que é o que soma
    corretamente em janela móvel — acumulado somaria o mesmo caixa várias vezes.

    `DFC_MI` e `DFC_MD` são somados com `max` por companhia–trimestre, não com
    `sum`: 5 companhia–trimestres publicam pelos dois métodos (§3.13) e somá-los
    duplicaria o caixa. Os dois métodos medem a mesma grandeza.
    """
    quadro = con.execute(
        f"""
        WITH fco AS (
            SELECT cd_cvm, trimestre, max(valor_reais) AS fco
            FROM fatos_contabeis
            WHERE demonstrativo LIKE 'DFC%'
              AND cd_conta = '{CONTA_FCO}'
              AND tipo_periodo = 'trimestral'
            GROUP BY 1, 2
        )
        SELECT
            i.cd_cvm,
            i.trimestre,
            i.lucro_liquido_consolidado AS lucro,
            i.ativo_total,
            f.fco
        FROM indicadores AS i
        JOIN companhias AS c USING (cd_cvm)
        JOIN fco AS f ON f.cd_cvm = i.cd_cvm AND f.trimestre = i.trimestre
        WHERE i.lucro_liquido_consolidado IS NOT NULL
          AND i.ativo_total IS NOT NULL
          AND NOT c.is_banco
        """
    ).df()
    quadro["ordem"] = quadro["trimestre"].map(ordinal_trimestre)
    return quadro.dropna(subset=["ordem"]).sort_values(["cd_cvm", "ordem"])


def _juntar_lag(base: pd.DataFrame, coluna: str, lag: int) -> pd.Series:
    """Defasagem por junção EXATA de trimestre, nunca por `shift`.

    `shift` trataria a linha anterior do quadro como o trimestre anterior, o
    que é falso quando a companhia tem lacuna. A junção por `ordem - lag` só
    casa quando o trimestre existe de fato.
    """
    esquerda = base[["cd_cvm", "ordem"]].copy()
    esquerda["alvo_ordem"] = esquerda["ordem"] - lag
    direita = base[["cd_cvm", "ordem", coluna]].rename(
        columns={"ordem": "alvo_ordem", coluna: f"{coluna}_lag{lag}"}
    )
    juntado = esquerda.merge(direita, on=["cd_cvm", "alvo_ordem"], how="left")
    return juntado[f"{coluna}_lag{lag}"].to_numpy()


def construir_amostra(base: pd.DataFrame) -> pd.DataFrame:
    """Monta accrual TTM e o rótulo por quintil transversal do trimestre."""
    quadro = base.copy()
    # Somas móveis de 4 trimestres por junção exata — não `rolling`, pelo mesmo
    # motivo da defasagem: lacuna não pode virar vizinho.
    for coluna in ("lucro", "fco"):
        partes = [quadro[coluna].to_numpy(dtype=float)]
        for lag in (1, 2, 3):
            partes.append(_juntar_lag(quadro, coluna, lag))
        quadro[f"{coluna}_ttm"] = np.sum(partes, axis=0)

    quadro["ativo_lag4"] = _juntar_lag(quadro, "ativo_total", 4)
    quadro["ativo_medio"] = (quadro["ativo_total"] + quadro["ativo_lag4"]) / 2.0

    validos = (
        np.isfinite(quadro["lucro_ttm"])
        & np.isfinite(quadro["fco_ttm"])
        & np.isfinite(quadro["ativo_medio"])
        & (quadro["ativo_medio"] > 0)
        & (quadro["ativo_total"] > CORTE_ATIVO_REAIS)
    )
    quadro = quadro[validos].copy()

    quadro["roa"] = quadro["lucro_ttm"] / quadro["ativo_medio"]
    quadro["conversao"] = quadro["fco_ttm"] / quadro["ativo_medio"]
    quadro["accrual"] = quadro["roa"] - quadro["conversao"]
    quadro["conversao_neg"] = -quadro["conversao"]
    quadro["log_ativo"] = np.log(quadro["ativo_total"])

    # Restrição de estado do pré-registro: a pergunta é sobre lucro que deixa
    # de virar caixa, então quem já dá prejuízo não tem lucro para converter.
    quadro = quadro[quadro["lucro_ttm"] > 0].copy()

    quadro["accrual_lag4"] = _juntar_lag(quadro, "accrual", HORIZONTE)
    quadro["delta_accrual_passado"] = quadro["accrual"] - quadro["accrual_lag4"]

    # Futuro: accrual em t+4, por junção exata (lag negativo).
    futuro = quadro[["cd_cvm", "ordem", "accrual"]].rename(
        columns={"ordem": "ordem_futura", "accrual": "accrual_futuro"}
    )
    quadro["ordem_futura"] = quadro["ordem"] + HORIZONTE
    quadro = quadro.merge(futuro, on=["cd_cvm", "ordem_futura"], how="left")

    elegiveis = len(quadro)
    censurados = int(quadro["accrual_futuro"].isna().sum())
    quadro = quadro.dropna(subset=["accrual_futuro"]).copy()
    quadro["delta_accrual"] = quadro["accrual_futuro"] - quadro["accrual"]

    # Rótulo: quintil SUPERIOR de Δaccrual dentro do trimestre. Trimestre com
    # menos de 25 observações não sustenta quintil e sai.
    grupos = quadro.groupby("ordem")["delta_accrual"]
    quadro["n_no_trimestre"] = grupos.transform("size")
    quadro = quadro[quadro["n_no_trimestre"] >= 25].copy()
    quadro["alvo"] = (
        quadro.groupby("ordem")["delta_accrual"]
        .transform(lambda s: s >= s.quantile(1 - 1 / QUINTIS))
        .astype(int)
    )
    quadro.attrs["elegiveis"] = elegiveis
    quadro.attrs["censurados"] = censurados
    return quadro


#: Mínimo para T1 significar alguma coisa. Abaixo disso o auditor FALHA em vez
#: de aprovar: amostra vazia produzia "T1 aprovado" com amplitude NaN, porque
#: `NaN >= 0.15` é False. Guarda que aprova por ausência de dado é pior que
#: guarda nenhuma — foi o defeito que esta constante fecha.
MINIMO_PARA_T1 = 500


class AmostraInsuficienteError(RuntimeError):
    """A amostra não sustenta o teste. Nunca vira aprovação."""


def medir_t1(amostra: pd.DataFrame) -> dict[str, object]:
    """T1 sobre TODOS os componentes que definem mecanicamente o rótulo."""
    if len(amostra) < MINIMO_PARA_T1:
        raise AmostraInsuficienteError(
            f"amostra com {len(amostra)} linha(s), mínimo {MINIMO_PARA_T1}: "
            "T1 não é calculável e NÃO pode ser reportado como aprovado"
        )
    resultado: dict[str, object] = {}
    for componente in COMPONENTES_T1:
        try:
            faixas = pd.qcut(amostra[componente], QUINTIS, labels=False,
                             duplicates="drop")
        except ValueError:  # pragma: no cover - componente degenerado
            resultado[componente] = {"erro": "quintis não formáveis"}
            continue
        taxas = amostra.groupby(faixas)["alvo"].mean()
        amplitude = float(taxas.max() - taxas.min())
        resultado[componente] = {
            "taxas_por_quintil": [round(float(t), 4) for t in taxas],
            "amplitude": round(amplitude, 4),
            "reprova": bool(amplitude >= LIMIAR_T1),
        }
    resultado["limiar"] = LIMIAR_T1
    resultado["algum_reprova"] = any(
        isinstance(v, dict) and v.get("reprova") for v in resultado.values()
    )
    return resultado


def medir_baselines(amostra: pd.DataFrame) -> dict[str, object]:
    """AUC de cada baseline trivial — todos publicados, não só o melhor."""
    saida: dict[str, object] = {}
    for nome, coluna in BASELINES.items():
        valores = amostra[coluna].to_numpy(dtype=float)
        finito = np.isfinite(valores)
        if finito.sum() < 100 or amostra["alvo"][finito].nunique() < 2:
            saida[nome] = {"erro": "amostra insuficiente"}
            continue
        agregada = float(roc_auc_score(amostra["alvo"][finito], valores[finito]))
        pontuado = pd.DataFrame(
            {
                "cd_cvm": amostra["cd_cvm"][finito].to_numpy(),
                "y": amostra["alvo"][finito].to_numpy(),
                "escore": valores[finito],
            }
        )
        intra = auc_within_companhia(pontuado)
        saida[nome] = {
            "auc_agregada": round(agregada, 4),
            "auc_intra_companhia": round(float(intra), 4) if intra else None,
            "lacuna_t2": (
                round(agregada - float(intra), 4) if intra else None
            ),
        }
    return saida


def auditar(con: duckdb.DuckDBPyConnection) -> dict[str, object]:
    base = _carregar_base(con)
    amostra = construir_amostra(base)
    t1 = medir_t1(amostra)
    relatorio: dict[str, object] = {
        "pre_registro": (
            "resultados/pre_registro_rank03_conversao_caixa_2026-08-27.md"
        ),
        "amostra": {
            "n": int(len(amostra)),
            "companhias": int(amostra["cd_cvm"].nunique()),
            "trimestres": int(amostra["ordem"].nunique()),
            "eventos": int(amostra["alvo"].sum()),
            "prevalencia": round(float(amostra["alvo"].mean()), 4),
            "elegiveis_antes_da_censura": int(amostra.attrs["elegiveis"]),
            "censurados_sem_t_mais_4": int(amostra.attrs["censurados"]),
        },
        "t1": t1,
    }
    if t1["algum_reprova"]:
        relatorio["veredito"] = (
            "REPROVA T1 — o alvo fabrica o próprio baseline. Encerrado antes "
            "de treinar, como o pré-registro exige."
        )
        return relatorio
    relatorio["baselines"] = medir_baselines(amostra)
    relatorio["veredito"] = (
        "T1 aprovado — seguir para baselines, modelo, T2 e T3."
    )
    return relatorio


def principal() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--painel", type=Path, required=True)
    analisador.add_argument("--saida", type=Path, required=True)
    argumentos = analisador.parse_args()

    con = duckdb.connect(str(argumentos.painel), read_only=True)
    try:
        relatorio = auditar(con)
    finally:
        con.close()

    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    argumentos.saida.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(principal())
