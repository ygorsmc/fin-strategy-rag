"""Contratos do modelo final do CAND-02-P (`scripts/cand02p_modelo_final.py`)."""

from __future__ import annotations

from scripts import cand02p_modelo_final as mf
from scripts import cand02p_piloto as p


def test_um_nome_para_cada_atributo_do_m():
    ev = {"mudancas_numericas": [], "operacao": "alteracao", "tipo": "texto", "b1_nivel1": 0, "b1_nivel2": 0,
          "b1_nivel3": 0, "categorias": [], "reapresentacao": False, "negacao_modal": False, "moeda": False,
          "massa": 1, "distancia": 0.0, "pagina_relativa": 0.0, "pagina_depois": 1, "pagina_antes": 1,
          "antes": "a", "depois": "b"}
    c = {"sims": [0.0] * len(mf.ANCORAS_CURTAS), "score_c": 0.0}
    assert len(mf.NOMES) == len(p.features(ev, c)) and len(set(mf.NOMES)) == len(mf.NOMES)


def test_grupos_cobrem_cada_atributo_exatamente_uma_vez():
    nos_grupos = [n for nomes in mf.GRUPOS.values() for n in nomes]
    assert sorted(nos_grupos) == sorted(mf.NOMES)


def test_modelo_final_usa_os_tres_pilotos_com_treino_e_teste():
    assert [(d.name, papeis) for d, papeis in mf.PILOTOS] == [
        ("cand02p", ("treino", "teste")), ("cand02p_v2", ("treino", "teste")), ("cand02p_v3", ("treino", "teste"))]


def test_demo_reconhece_par_rotulado_e_libera_par_novo():
    """O modo "novo" da demonstração recusa par do treino do modelo final:
    mostrá-lo num par visto seria memória, não funcionamento."""
    from scripts import cand02p_demo as demo
    rotulados = demo._pares_rotulados()
    assert ("SANTANDER", "4T2022", "1T2023") in rotulados
    assert ("SANTANDER", "3T2025", "4T2025") not in rotulados
