from __future__ import annotations

import pandas as pd
import pytest

from scripts.auditar_alvo_c1 import (
    LIMIAR_T1,
    _juntar_lag_exato,
    resumir_t1,
)


def test_lag_exato_nao_pula_trimestre_ausente():
    historico = pd.DataFrame(
        {
            "cd_cvm": ["A", "A"],
            "ordem": [1, 3],
            "valor": [10.0, 30.0],
        }
    )
    atual = pd.DataFrame({"cd_cvm": ["A"], "ordem": [3]})
    unido = _juntar_lag_exato(
        atual,
        historico,
        coluna="valor",
        lag=1,
        nome="valor_anterior",
        como="left",
    )
    assert pd.isna(unido.loc[0, "valor_anterior"])


def _amostra_sintetica(taxas: list[float]) -> pd.DataFrame:
    linhas = []
    for quintil, taxa in enumerate(taxas):
        for i in range(100):
            linhas.append(
                {
                    "cd_cvm": f"C{i:03d}",
                    "ordem": quintil,
                    "sd8": float(quintil + 1),
                    "rotulo": int(i < round(taxa * 100)),
                    "escore_menos_sd8": -float(quintil + 1),
                }
            )
    return pd.DataFrame(linhas)


def test_t1_reprova_quando_amplitude_excede_limiar():
    resumo = resumir_t1(_amostra_sintetica([0.30, 0.25, 0.20, 0.10, 0.05]))
    assert resumo["amplitude_t1"] == pytest.approx(0.25)
    assert resumo["amplitude_t1"] > LIMIAR_T1
    assert resumo["falha_t1"] is True
    assert resumo["veredito"].startswith("REJEITAR C1")


def test_t1_nao_reprova_amplitude_abaixo_do_limiar():
    resumo = resumir_t1(_amostra_sintetica([0.20, 0.18, 0.16, 0.14, 0.10]))
    assert resumo["amplitude_t1"] == pytest.approx(0.10)
    assert resumo["amplitude_t1"] < LIMIAR_T1
    assert resumo["falha_t1"] is False
    assert "não falha T1" in resumo["veredito"]
