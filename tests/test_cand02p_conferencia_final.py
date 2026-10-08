"""Contratos da conferência final da rubrica v2 (`scripts/cand02p_conferencia_final.py`)."""

from __future__ import annotations

import math

import pytest

from scripts import cand02p_conferencia_final as f


def _disp(n0=50, n1=40, n2=35):
    return {0: [("A", f"E{i:03d}") for i in range(n0)], 1: [("B", f"E{i:03d}") for i in range(n1)],
            2: [("C", f"E{i:03d}") for i in range(n2)]}


def test_estratifica_exatamente_n_por_nota_e_e_deterministico():
    d = _disp()
    x = f.estratificar(d, 30, 1)
    assert x == f.estratificar(d, 30, 1) and len(x) == 90 and len(set(x)) == 90
    assert sum(1 for par, _ in x if par == "C") == 30


def test_nota_sem_itens_suficientes_levanta():
    with pytest.raises(ValueError, match="nota 2"):
        f.estratificar(_disp(n2=29), 30, 1)


def test_prioridade_reconhecida_conta_so_os_itens_de_nota_2_do_claude():
    assert f.prioridade_reconhecida([(0, 2), (1, 2), (2, 2), (2, 0), (0, 1)]) == pytest.approx(2 / 3)
    assert f.prioridade_reconhecida([(0, 0), (1, 1)]) is None


@pytest.mark.parametrize("alfa,prio", [(0.70, 0.69), (0.66, 0.90), (None, 0.90), (0.80, None),
                                        (math.nan, 0.90), (0.80, math.nan)])
def test_os_dois_portoes_precisam_passar_e_ausencia_reprova(alfa, prio):
    assert f.decidir(alfa, prio) == "RUBRICA_V2_REPROVADA"


def test_aprova_nos_limiares():
    assert f.decidir(0.67, 0.70) == "RUBRICA_V2_APROVADA"


def test_simulacao_ao_acaso_nao_aprova():
    """Contraprova do poder: leitor que concorda ao acaso não passa."""
    assert f.simular(f.CENARIOS["acaso"], 30, 300, 7)["p_aprovar"] == 0.0
