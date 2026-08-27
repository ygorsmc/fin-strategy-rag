"""Audita se o alvo C1 fabrica seu próprio baseline antes de treinar ML.

C1 marca uma companhia quando a queda futura de ROA TTM supera ``k`` vezes
o desvio-padrão móvel das próprias variações anuais de ROA. O protocolo T1 do
projeto exige que a taxa do evento não varie mecanicamente mais de 15 pontos
percentuais entre quintis de um componente que define o próprio corte.

Este script mede o adversário trivial ``-sd8``. Ele não treina modelo e não
alega desempenho confirmatório: o painel local conserva números reapresentados
e não contém a data de primeira recepção de cada demonstração. A pergunta é
anterior: o rótulo é válido o bastante para merecer um modelo?

Uso::

    python -m scripts.auditar_alvo_c1 \
      --painel artefatos/cvm_treino.duckdb
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from src.modelo.treinar import auc_within_companhia
from src.normalizacao import ordinal_trimestre

K_C1 = 1.25
JANELA_SD = 8
MIN_PERIODOS_SD = 6
LIMIAR_T1 = 0.15
CORTE_ATIVO_REAIS = 1_000_000_000.0
TOP_N = 20


def _carregar_base(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    quadro = con.execute(
        """
        SELECT
            i.cd_cvm,
            i.trimestre,
            i.lucro_liquido_consolidado AS lucro,
            i.ativo_total,
            c.is_banco
        FROM indicadores AS i
        JOIN companhias AS c USING (cd_cvm)
        WHERE i.lucro_liquido_consolidado IS NOT NULL
          AND i.ativo_total IS NOT NULL
          AND NOT c.is_banco
        """
    ).fetchdf()
    quadro["cd_cvm"] = quadro["cd_cvm"].astype(str)
    quadro["ordem"] = quadro["trimestre"].map(ordinal_trimestre)
    return quadro.sort_values(["cd_cvm", "ordem"]).reset_index(drop=True)


def _juntar_lag_exato(
    atual: pd.DataFrame,
    historico: pd.DataFrame,
    *,
    coluna: str,
    lag: int,
    nome: str,
    como: str = "inner",
) -> pd.DataFrame:
    """Junta ``t-lag`` sem deixar trimestre ausente virar a linha anterior."""
    anterior = historico[["cd_cvm", "ordem", coluna]].copy()
    anterior["ordem"] = anterior["ordem"] + lag
    anterior = anterior.rename(columns={coluna: nome})
    return atual.merge(anterior, on=["cd_cvm", "ordem"], how=como)


def construir_roa_ttm(base: pd.DataFrame) -> pd.DataFrame:
    atual = base[["cd_cvm", "trimestre", "ordem", "ativo_total"]].copy()
    for lag in range(4):
        atual = _juntar_lag_exato(
            atual,
            base,
            coluna="lucro",
            lag=lag,
            nome=f"lucro_t_menos_{lag}",
        )
    atual = _juntar_lag_exato(
        atual,
        base,
        coluna="ativo_total",
        lag=4,
        nome="ativo_t_menos_4",
    )
    lucros = [f"lucro_t_menos_{lag}" for lag in range(4)]
    ativo_medio = (atual["ativo_total"] + atual["ativo_t_menos_4"]) / 2.0
    atual["roa_ttm"] = atual[lucros].sum(axis=1) / ativo_medio.replace(0, np.nan)
    return atual.replace([np.inf, -np.inf], np.nan).dropna(subset=["roa_ttm"])


def _winsorizar_por_ordem(quadro: pd.DataFrame, coluna: str) -> pd.Series:
    def limitar(grupo: pd.Series) -> pd.Series:
        inferior, superior = grupo.quantile([0.01, 0.99])
        return grupo.clip(lower=inferior, upper=superior)

    return quadro.groupby("ordem", group_keys=False)[coluna].transform(limitar)


def _sd_movel_exata(quadro: pd.DataFrame, coluna: str) -> pd.DataFrame:
    partes: list[pd.DataFrame] = []
    for cd_cvm, grupo in quadro.groupby("cd_cvm"):
        grupo = grupo.sort_values("ordem")
        ordens = range(int(grupo["ordem"].min()), int(grupo["ordem"].max()) + 1)
        serie = grupo.set_index("ordem")[coluna].reindex(ordens)
        sd = serie.rolling(JANELA_SD, min_periods=MIN_PERIODOS_SD).std(ddof=1)
        partes.append(
            pd.DataFrame(
                {"cd_cvm": str(cd_cvm), "ordem": list(ordens), "sd8": sd.values}
            )
        )
    if not partes:
        return pd.DataFrame(columns=["cd_cvm", "ordem", "sd8"])
    return pd.concat(partes, ignore_index=True)


def construir_amostra(
    con: duckdb.DuckDBPyConnection,
    *,
    winsorizacao: str = "delta_por_trimestre",
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Constrói C1 com três sensibilidades declaradas de winsorização.

    ``delta_por_trimestre`` é a operacionalização primária pré-declarada na
    replicação cega. ``sd_por_trimestre`` é a leitura alternativa da frase
    "sd8 winsorizada". ``nenhuma`` mede se a conclusão depende do tratamento.
    """
    if winsorizacao not in {"delta_por_trimestre", "sd_por_trimestre", "nenhuma"}:
        raise ValueError(f"winsorização desconhecida: {winsorizacao}")

    base = _carregar_base(con)
    roa = construir_roa_ttm(base)
    delta = _juntar_lag_exato(
        roa,
        roa,
        coluna="roa_ttm",
        lag=4,
        nome="roa_ttm_t_menos_4",
    )
    delta["delta_roa_anual"] = delta["roa_ttm"] - delta["roa_ttm_t_menos_4"]
    coluna_sd = "delta_roa_anual"
    if winsorizacao == "delta_por_trimestre":
        delta["delta_roa_w"] = _winsorizar_por_ordem(delta, "delta_roa_anual")
        coluna_sd = "delta_roa_w"

    sd = _sd_movel_exata(delta, coluna_sd)
    origens = delta.merge(sd, on=["cd_cvm", "ordem"], how="left")
    if winsorizacao == "sd_por_trimestre":
        origens["sd8"] = _winsorizar_por_ordem(origens, "sd8")
    origens = origens[
        (origens["ativo_total"] > CORTE_ATIVO_REAIS)
        & origens["sd8"].notna()
        & (origens["sd8"] > 0)
    ].copy()

    futuro = roa[["cd_cvm", "ordem", "roa_ttm"]].copy()
    futuro["ordem"] = futuro["ordem"] - 4
    futuro = futuro.rename(columns={"roa_ttm": "roa_ttm_t_mais_4"})
    origens = origens.merge(futuro, on=["cd_cvm", "ordem"], how="left")
    n_origens = int(len(origens))
    n_censuradas = int(origens["roa_ttm_t_mais_4"].isna().sum())
    amostra = origens.dropna(subset=["roa_ttm_t_mais_4"]).copy()
    amostra["rotulo"] = (
        amostra["roa_ttm_t_mais_4"] - amostra["roa_ttm"]
        < -K_C1 * amostra["sd8"]
    ).astype(int)
    amostra["escore_menos_sd8"] = -amostra["sd8"]
    return amostra, {"n_origens": n_origens, "n_censuradas_t_mais_4": n_censuradas}


def resumir_t1(amostra: pd.DataFrame, *, top_n: int = TOP_N) -> dict[str, object]:
    if amostra.empty or amostra["rotulo"].nunique() < 2:
        raise ValueError("amostra sem as duas classes necessárias para auditar T1")

    quintil = pd.qcut(amostra["sd8"], 5, labels=False, duplicates="drop")
    taxas = amostra.assign(quintil_sd8=quintil).groupby("quintil_sd8")["rotulo"].mean()
    amplitude = float(taxas.max() - taxas.min())

    precisoes = []
    prevalencias = []
    for _, grupo in amostra.groupby("ordem"):
        prevalencias.append(float(grupo["rotulo"].mean()))
        n = min(top_n, len(grupo))
        topo = grupo.nlargest(n, "escore_menos_sd8")
        precisoes.append(float(topo["rotulo"].mean()))

    pontuado = amostra[["cd_cvm", "rotulo", "escore_menos_sd8"]].rename(
        columns={"escore_menos_sd8": "escore"}
    )
    dentro = auc_within_companhia(pontuado)
    falha = amplitude >= LIMIAR_T1
    return {
        "n_observacoes": int(len(amostra)),
        "n_companhias": int(amostra["cd_cvm"].nunique()),
        "n_trimestres": int(amostra["ordem"].nunique()),
        "n_eventos": int(amostra["rotulo"].sum()),
        "taxa_evento": float(amostra["rotulo"].mean()),
        "taxa_evento_por_quintil_crescente_de_sd8": [float(x) for x in taxas],
        "amplitude_t1": amplitude,
        "limiar_t1": LIMIAR_T1,
        "falha_t1": falha,
        "auc_menos_sd8_agregada": float(
            roc_auc_score(amostra["rotulo"], amostra["escore_menos_sd8"])
        ),
        "auc_menos_sd8_intra_companhia": dentro,
        "top_n": int(top_n),
        "precisao_media_top_n_menos_sd8": float(np.mean(precisoes)),
        "prevalencia_media_trimestral": float(np.mean(prevalencias)),
        "veredito": (
            "REJEITAR C1: o alvo falha T1 antes do treino."
            if falha
            else "C1 não falha T1 nesta operacionalização; outros gates seguem pendentes."
        ),
    }


def auditar(con: duckdb.DuckDBPyConnection) -> dict[str, object]:
    resultados: dict[str, object] = {}
    for modo in ("delta_por_trimestre", "sd_por_trimestre", "nenhuma"):
        amostra, cobertura = construir_amostra(con, winsorizacao=modo)
        resultados[modo] = {**cobertura, **resumir_t1(amostra)}
    primario = resultados["delta_por_trimestre"]
    return {
        "candidato": "C1 — queda de ROA TTM em T+4 < -1,25 × sd8 própria",
        "natureza": "auditoria de validade do alvo; não é backtest confirmatório",
        "limitacao_point_in_time": (
            "o DuckDB não contém data de primeira recepção e usa números que podem "
            "ter sido reapresentados"
        ),
        "operacionalizacao_primaria": "delta_por_trimestre",
        "sensibilidades": resultados,
        "veredito": primario["veredito"],
    }


def principal() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--painel", type=Path, default=Path("artefatos/cvm_treino.duckdb")
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=Path("artefatos/modelo/auditoria_alvo_c1.json"),
    )
    args = parser.parse_args()

    con = duckdb.connect(str(args.painel), read_only=True)
    try:
        resultado = auditar(con)
    finally:
        con.close()

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    print(f"\n→ {args.saida}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(principal())
