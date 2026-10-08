"""Contratos da calibração da rubrica v2 (`scripts/cand02p_calibracao.py`)."""

from __future__ import annotations

import math

import pytest

from scripts import cand02p_calibracao as cal

PARES = [f"{e}_{t}" for e in ("ABC", "BANESTES", "BB", "BMG", "BRADESCO", "BTG", "ITAU", "SANTANDER")
         for t in ("4T2021_1T2022", "4T2022_1T2023")]


def test_pares_sao_quatro_emissores_distintos_e_deterministicos():
    a = cal.escolher_pares(PARES, 1)
    assert a == cal.escolher_pares(PARES, 1)
    assert len(a) == 4 and len({x.split("_")[0] for x in a}) == 4 and set(a) <= set(PARES)


def test_itens_ja_vistos_pelo_humano_nunca_voltam():
    pools = {p: [f"E{n:03d}" for n in range(1, 121)] for p in PARES[:4]}
    vistos = {(p, f"E{n:03d}") for p in pools for n in range(1, 101)}
    itens = cal.escolher_itens(pools, vistos, 1)
    assert len(itens) == 60 and not set(itens) & vistos
    assert itens == cal.escolher_itens(pools, vistos, 1)


def test_par_sem_itens_novos_suficientes_levanta():
    pools = {p: [f"E{n:03d}" for n in range(1, 121)] for p in PARES[:4]}
    vistos = {(PARES[0], f"E{n:03d}") for n in range(1, 110)}
    with pytest.raises(ValueError, match="não vistos"):
        cal.escolher_itens(pools, vistos, 1)


@pytest.mark.parametrize("alfa", [None, math.nan, 0.6699])
def test_portao_nao_aprova_sem_medida_ou_abaixo(alfa):
    """NaN >= 0,67 é falso, mas NaN < 0,67 também; a guarda não pode aprovar por ausência."""
    assert cal.decidir(alfa) == "RUBRICA_V2_NAO_BASTA"


def test_portao_aprova_no_limiar():
    assert cal.decidir(0.67) == "RUBRICA_V2_APROVADA"
