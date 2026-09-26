"""Conferência RF02 somente sintética; não lê painéis nem calcula y real.

Da raiz do repositório:
  PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/reproduzir_provas_parciais.py

Reusa a fixture sintética P6/P7 e acrescenta uma segunda correção, para que
um mapa INCOMPLETO de provas continue não vazio. Toda escrita ocorre numa
conexão DuckDB :memory:; o cálculo de rótulo é proibido por dublê.
"""

import json
from unittest.mock import patch

from scripts import auditar_rank03b_consumo_operacional as auditor
from scripts import gates_painel_pesquisa_rank03b as gates
from scripts import painel_pesquisa_rank03b as pp
from tests.test_gates_painel_pesquisa_rank03b import TestProvaDeEscalaNoTempo


def resumir(g1):
    return {
        "aprovado": g1["aprovado"],
        "provas_posteriores_a_D": g1["g1_4_prova_de_escala_publicada_depois_de_D"],
    }


def main():
    fixture = TestProvaDeEscalaNoTempo()
    con, correcoes = fixture._montar("2019-01-15")
    segunda = ("A", "itr", "2017-03-31", 1)
    con.execute("UPDATE declaracoes SET escala = 'UNIDADE' WHERE dt_refer = '2017-03-31'")
    brutos = con.execute(
        "SELECT cd_conta, ordem, dt_ini, dt_fim, vl FROM declaracoes "
        "WHERE dt_refer = '2017-03-31'"
    ).fetchall()
    id_doc = con.execute(
        "SELECT id_doc FROM cadastro WHERE dt_refer = '2017-03-31'"
    ).fetchone()[0]
    correcoes[segunda] = {
        "escala_declarada": "UNIDADE",
        "escala_aplicada": "MIL",
        "base": "corrigida_documento",
        "id_correcao": "H2",
        "id_doc": id_doc,
        "impressao_digital": pp.impressao_digital(brutos),
    }
    provas = gates.datas_das_provas(con, correcoes)
    parciais = {segunda: provas[segunda]}
    with patch.object(auditor, "_somas_do_rotulo", side_effect=AssertionError("y proibido")):
        bom = pp.construir(con, correcoes)
        controle_bom = gates.medir(bom, provas=provas)["cadeia"][1]
        assert controle_bom["aprovado"]
        assert not any(gates.verificar_falsificacoes(bom, con, provas).values())
        with patch.object(pp.Documento, "disponivel_em", property(lambda d: d.dt_receb)), \
             patch.object(pp.Documento, "disponivel_em_v1", property(lambda d: d.dt_receb_v1)):
            ruim = pp.construir(con, correcoes)
        completo = gates.medir(ruim, provas=provas)["cadeia"][1]
        incompleto = gates.medir(ruim, provas=parciais)["cadeia"][1]
        direto = gates.g1_cego(gates.linhas_fco(ruim), gates.linhas_ativo(ruim), ruim)
        falsificacoes_parciais = gates.verificar_falsificacoes(ruim, con, parciais)
        assert not completo["aprovado"]
        assert completo["g1_4_prova_de_escala_publicada_depois_de_D"] == 2
        assert incompleto["aprovado"]
        assert incompleto["g1_4_prova_de_escala_publicada_depois_de_D"] == 0
        assert direto["aprovado"]
        assert not any(falsificacoes_parciais.values())
        try:
            gates.verificar_falsificacoes(ruim, con, provas)
        except gates.PainelViolaContrato as erro:
            c3_completo = str(erro)
        else:
            raise AssertionError("Controle com provas completas deveria recusar c3")
        try:
            gates.medir(ruim, provas={})
        except gates.ProvasAusentes:
            vazio_recusado = True
        else:
            raise AssertionError("Controle de mapa vazio deveria levantar")
    con.close()
    print(json.dumps({
        "dados": "exclusivamente sinteticos",
        "documentos_corrigidos": 2,
        "provas_completas": len(provas),
        "provas_parciais": len(parciais),
        "construtor_correto_e_provas_completas": resumir(controle_bom),
        "construtor_sabotado_e_provas_completas": resumir(completo),
        "construtor_sabotado_e_provas_parciais": resumir(incompleto),
        "g1_cego_direto_sem_provas": resumir(direto),
        "mapa_vazio_recusado": vazio_recusado,
        "falsificacoes_com_provas_completas": c3_completo,
        "falsificacoes_com_provas_parciais": falsificacoes_parciais,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
