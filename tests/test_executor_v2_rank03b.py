"""Contraprovas do executor v2 do Rank 3-B (contrato de 27/09, parte C).

Cada classe segue uma seção do rascunho v2 e exercita as contraprovas que ela
lista. Os painéis são construídos pelo construtor REAL a partir de declarações
sintéticas: linhagem, operandos, escalas e disponibilidade são os que o
executor verá no dado real.
"""

from __future__ import annotations

import calendar
import json
import random
import unicodedata
from datetime import date, timedelta

import pytest

from scripts import auditar_rank03b_consumo_operacional as auditor
from scripts import executor_v2_rank03b as ex
from scripts import painel_pesquisa_rank03b as pp
from tests.test_painel_pesquisa_rank03b import Base

NENHUM = {"ativo": set(), "fco": set()}
SEM_PROVAS = {"ativo": {}, "fco": {}}


def fim_do_trimestre(ano: int, k: int) -> date:
    return date(ano, 3 * k, calendar.monthrange(ano, 3 * k)[1])


def empresa(b: Base, cd: str, inicio=2015, fim=2021, fco=lambda ano, k: 100 + k,
            escala=lambda ano, k: "MIL", receb=None, ativo=lambda ano, k: 50_000,
            metodo=lambda ano, k: "DFC_MI", pular=frozenset()):
    """Exercício civil: ITR no 1T–3T e DFP no 4T, FCO acumulado no exercício.
    `pular`: trimestres (ano, k) sem documento nenhum."""
    receb = receb or (lambda ano, k: fim_do_trimestre(ano, k) + timedelta(days=80 if k == 4 else 40))
    for ano in range(inicio, fim + 1):
        acumulado = 0
        for k in range(1, 5):
            acumulado += fco(ano, k)
            fim_tri = fim_do_trimestre(ano, k)
            if (ano, k) in pular:
                continue
            b.doc(cd, "dfp" if k == 4 else "itr", fim_tri.isoformat(), receb(ano, k).isoformat(),
                  escala=escala(ano, k), fco=[(f"{ano}-01-01", fim_tri.isoformat(), acumulado)],
                  ativo=ativo(ano, k), metodo=metodo(ano, k))
    return b


def painel(b: Base, planos=None, por_conta=None):
    con = b.con()
    for cd, plano in (planos or {}).items():
        con.execute("UPDATE universo SET plano_contas = ? WHERE cd_cvm = ?", [plano, cd])
    return pp.construir(con, correcoes_por_conta=por_conta), con


#: Registro de congelamento SINTÉTICO: só os testes somam rótulo sem o pré-registro
#: congelado, e o fazem passando-o explicitamente (C10).
CONGELAMENTO_SINTETICO = ex.Congelamento.de_teste()


def amostra(p, decididos=NENHUM, rotulo=False):
    pop = ex.populacao_v2(p.ativo, p.fco_trimestral)
    return ex.construir_amostra_v2(p.fco_trimestral, p.ativo, decididos, pop["incluidas"],
                                   calcular_rotulo=rotulo,
                                   congelamento=CONGELAMENTO_SINTETICO if rotulo else None)


def chave(cd, ano, k, conj=None):
    conj = conj or ("dfp" if k == 4 else "itr")
    return (cd, conj, fim_do_trimestre(ano, k).isoformat(), 1)


# --- §3.2 -------------------------------------------------------------------------------

class TestPopulacao:
    def test_seguradora_conhecida_sai_e_o_efeito_no_g0_3_e_publicado(self):
        b = empresa(empresa(Base(), "A"), "S")
        p, _ = painel(b, {"S": "ll3_13_48e4cd07"})
        pop = ex.populacao_v2(p.ativo, p.fco_trimestral)
        assert pop["excluidas"] == ["S"] and "A" in pop["incluidas"]
        obs, _ = amostra(p)
        assert {o["cd_cvm"] for o in obs} == {"A"}
        g0 = ex.g0_v2(p.ativo, p.fco_trimestral, _nulos(p), pop)
        assert g0["efeito_do_3_2"]["linhas_de_ativo_validas_nas_excluidas"] == 28

    def test_plano_ll3_11_fica(self):
        p, _ = painel(empresa(Base(), "A"), {"A": "ll3_11_qualquer"})
        assert "A" in ex.populacao_v2(p.ativo, p.fco_trimestral)["incluidas"]

    def test_outro_plano_ll3_13_interrompe(self):
        p, _ = painel(empresa(Base(), "S"), {"S": "ll3_13_outro"})
        with pytest.raises(ex.PlanoDesconhecido):
            ex.populacao_v2(p.ativo, p.fco_trimestral)


def _nulos(p):
    from scripts import gates_painel_pesquisa_rank03b as gates
    return gates.nulos(p)


# --- §5.1 -------------------------------------------------------------------------------

class TestG01:
    def test_md_e_mi_do_mesmo_periodo_somados_reprova(self):
        p, _ = painel(empresa(Base(), "A"))
        t = next(t for t in p.fco_trimestral if t["estado"] == "valido" and t["origem"] == "derivado")
        ops = json.loads(t["operandos"])
        ops[0] = dict(ops[1])  # dois acumulados do MESMO período
        t["operandos"] = json.dumps(ops, sort_keys=True)
        pop = ex.populacao_v2(p.ativo, p.fco_trimestral)
        g0 = ex.g0_v2(p.ativo, p.fco_trimestral, _nulos(p), pop)
        assert g0["g0_1_v2"]["trimestres_que_combinam_o_mesmo_periodo"] == 1
        assert not g0["aprovado"]

    def test_dois_valores_para_o_mesmo_trimestre_reprova(self):
        p, _ = painel(empresa(Base(), "A"))
        valido = next(t for t in p.fco_trimestral if t["estado"] == "valido")
        p.fco_trimestral.append(dict(valido))
        pop = ex.populacao_v2(p.ativo, p.fco_trimestral)
        g0 = ex.g0_v2(p.ativo, p.fco_trimestral, _nulos(p), pop)
        assert g0["g0_1_v2"]["trimestres_validos_repetidos"] == 1 and not g0["aprovado"]

    def test_derivacao_entre_metodos_e_aceita_e_contada(self):
        b = empresa(Base(), "A", metodo=lambda ano, k: "DFC_MD" if (ano, k) == (2018, 1) else "DFC_MI")
        p, _ = painel(b)
        pop = ex.populacao_v2(p.ativo, p.fco_trimestral)
        g0 = ex.g0_v2(p.ativo, p.fco_trimestral, _nulos(p), pop)
        assert g0["g0_1_v2"]["aprovado"]
        assert g0["g0_1_v2"]["trimestres_validos_derivados_entre_metodos"] == 1


# --- §5.5 -------------------------------------------------------------------------------

def _estados(p, decididos=NENHUM):
    pop = ex.populacao_v2(p.ativo, p.fco_trimestral)
    prep = ex.preparar_trimestres(p.fco_trimestral, decididos, pop["incluidas"])
    return {(t["cd_cvm"], t["trimestre"]): t["estado_v2"] for ts in prep.values() for t in ts}


def _u_no(ano_k):
    return lambda ano, k: "UNIDADE" if (ano, k) == ano_k else "MIL"


class TestRegra1:
    def test_heterogeneo_com_operando_sem_veredito_e_censurado(self):
        p, _ = painel(empresa(Base(), "A", escala=_u_no((2018, 2))))
        e = _estados(p)
        assert e[("A", "2T2018")] == ex.ESTADO_REGRA_1 and e[("A", "3T2018")] == ex.ESTADO_REGRA_1
        assert e[("A", "1T2018")] == "valido"

    def test_os_dois_operandos_decididos_para_o_fco_e_usado(self):
        p, _ = painel(empresa(Base(), "A", escala=_u_no((2018, 2))))
        decididos = {"ativo": set(), "fco": {chave("A", 2018, 1), chave("A", 2018, 2),
                                            chave("A", 2018, 3)}}
        e = _estados(p, decididos)
        assert e[("A", "2T2018")] == "valido" and e[("A", "3T2018")] == "valido"

    def test_operando_confirmado_so_por_saldo_conta_como_nao_decidido(self):
        p, _ = painel(empresa(Base(), "A", escala=_u_no((2018, 2))))
        decididos = {"ativo": {chave("A", 2018, 1), chave("A", 2018, 2)}, "fco": {chave("A", 2018, 1)}}
        assert _estados(p, decididos)[("A", "2T2018")] == ex.ESTADO_REGRA_1

    def test_declaradas_diferentes_e_aplicadas_iguais_e_usado(self, ):
        """O documento do meio corrigido com prova do FCO; o vizinho sem veredito."""
        b = empresa(Base(), "A", escala=_u_no((2018, 2)))
        con = b.con()
        por_conta = _correcao_fco(con, chave("A", 2018, 2))
        p = pp.construir(con, correcoes_por_conta=por_conta)
        decididos = {"ativo": set(), "fco": {chave("A", 2018, 2)}}
        e = _estados(p, decididos)
        assert e[("A", "2T2018")] == "valido" and e[("A", "3T2018")] == "valido"

    def test_declaradas_iguais_e_aplicadas_diferentes_com_um_sem_veredito_e_censurado(self):
        b = empresa(Base(), "A")
        con = b.con()
        por_conta = _correcao_fco(con, chave("A", 2018, 2), declarada="MIL", aplicada="UNIDADE")
        p = pp.construir(con, correcoes_por_conta=por_conta)
        decididos = {"ativo": set(), "fco": {chave("A", 2018, 2)}}
        assert _estados(p, decididos)[("A", "3T2018")] == ex.ESTADO_REGRA_1


def _correcao_fco(con, doc, declarada="UNIDADE", aplicada="MIL"):
    cd, conj, dt, v = doc
    brutos = con.execute(
        "SELECT cd_conta, ordem, dt_ini, dt_fim, vl FROM declaracoes WHERE cd_cvm=? AND conjunto=? "
        "AND dt_refer = CAST(? AS DATE) AND versao=?", [cd, conj, dt, v]).fetchall()
    id_doc = con.execute("SELECT id_doc FROM cadastro WHERE cd_cvm=? AND conjunto=? "
                         "AND dt_refer = CAST(? AS DATE) AND versao=?", [cd, conj, dt, v]).fetchone()[0]
    return {doc: {"6.01": {"escala_declarada": declarada, "escala_aplicada": aplicada,
                           "base": "corrigida_conta", "id_correcao": "ESCC-1", "id_doc": id_doc,
                           "impressao_digital": pp.impressao_digital(brutos)}}}


def _obs(obs, cd="A"):
    return {o["D"]: o for o in obs if o["cd_cvm"] == cd}


class TestJanelaEQ1ComCensura:
    def test_d_logo_depois_de_um_trimestre_censurado_nao_desloca_a_janela(self):
        """O trimestre censurado ocupa o seu lugar: a janela o inclui e a observação sai."""
        p, _ = painel(empresa(Base(), "A", escala=_u_no((2018, 2))))
        obs, inv = amostra(p)
        # D = recepção do 1T2019 (40 dias depois de 31/03/2019): a janela 2T2017–1T2019
        # contém 2T2018 e 3T2018 censurados.
        d = (fim_do_trimestre(2019, 1) + timedelta(days=40)).isoformat()
        assert d not in _obs(obs)
        assert inv["descartes"]["janela_com_trimestre_do_5_5"] > 0

    def test_q1_censurado_perde_a_chave(self):
        """D = recepção do 4T2017 (DFP): q1 = 2T2018, censurado — Y indefinido."""
        p, _ = painel(empresa(Base(), "A", escala=_u_no((2018, 2))))
        obs, inv = amostra(p)
        assert all(o["q1"] not in ("2T2018", "3T2018") for o in obs)
        assert inv["descartes"]["rotulo_com_trimestre_do_5_5"] > 0

    def test_q1_censurado_e_q1_e_nao_vira_sem_q1(self):
        """Achado M6: pular o censurado ao procurar q1 levaria essa data ao motivo 1
        (o 4T2018 começa depois de D + 3 meses). Ela tem de sair no motivo 7."""
        d = (fim_do_trimestre(2017, 4) + timedelta(days=80)).isoformat()
        base, _ = painel(empresa(Base(), "A"))
        obs_b, inv_b = amostra(base)
        assert _obs(obs_b)[d]["q1"] == "2T2018", "sem censura, a data vira observação"
        censurado, _ = painel(empresa(Base(), "A", escala=_u_no((2018, 2))))
        obs_c, inv_c = amostra(censurado)
        assert d not in _obs(obs_c)
        assert inv_c["descartes"]["sem_q1_identificavel"] == inv_b["descartes"]["sem_q1_identificavel"]
        assert inv_c["descartes"]["rotulo_com_trimestre_do_5_5"] >= 1

    def test_q1_censurado_em_exercicio_irregular(self):
        """Exercício de julho a junho: o trimestre censurado ainda é q1 pelas datas."""
        b = Base()
        for ano in range(2015, 2021):
            acumulado = 0
            inicio = date(ano, 7, 1)
            for k, (m, d_fim) in enumerate([(9, 30), (12, 31), (3, 31), (6, 30)], start=1):
                a = ano if m >= 7 else ano + 1
                fim_tri = date(a, m, d_fim)
                acumulado += 100 + k
                esc = "UNIDADE" if (ano, k) == (2018, 2) else "MIL"
                b.doc("A", "dfp" if k == 4 else "itr", fim_tri.isoformat(),
                      (fim_tri + timedelta(days=80 if k == 4 else 40)).isoformat(), escala=esc,
                      fco=[(inicio.isoformat(), fim_tri.isoformat(), acumulado)], ativo=50_000)
        p, _ = painel(b)
        obs, inv = amostra(p)
        assert all(o["q1"] not in ("4T2018", "1T2019") for o in obs)
        assert inv["descartes"]["rotulo_com_trimestre_do_5_5"] > 0


class TestOrdemDosMotivos:
    def test_janela_com_censurado_e_lacuna_sai_no_motivo_4(self):
        """Achado M6: a data cuja janela tem trimestre do §5.5 E lacuna conta no 4."""
        pular = {(2017, 3)}  # sem 3T2017: o 3T some e o 4T vira lacuna de 184 dias
        so_lacuna, _ = painel(empresa(Base(), "A", pular=pular))
        _, inv_l = amostra(so_lacuna)
        ambos, _ = painel(empresa(Base(), "A", pular=pular, escala=_u_no((2018, 2))))
        _, inv_a = amostra(ambos)
        assert inv_a["descartes"]["janela_com_lacuna"] < inv_l["descartes"]["janela_com_lacuna"]
        assert inv_a["descartes"]["janela_com_trimestre_do_5_5"] > 0


class TestRegra2:
    def test_janela_com_1t_isolado_de_outra_escala_e_da_regra_2_nao_da_1(self):
        p, _ = painel(empresa(Base(), "A", escala=_u_no((2019, 1))))
        e = _estados(p)
        assert e[("A", "1T2019")] == "valido", "arquivado: a regra 1 não o vê"
        assert e[("A", "2T2019")] == ex.ESTADO_REGRA_1
        _, inv = amostra(p)
        assert inv["descartes"]["regra_2_do_5_5"] > 0

    def test_s2_com_4t_e_1t_de_escalas_diferentes_e_censurado(self):
        """q3 = 4T2019 (MIL), q4 = 1T2020 (UNIDADE, arquivado): a soma S2 mistura."""
        b = empresa(Base(), "A", escala=lambda ano, k: "UNIDADE" if ano >= 2020 else "MIL",
                    fco=lambda ano, k: (100 + k) * (1000 if ano >= 2020 else 1))
        p, _ = painel(b)
        obs, inv = amostra(p)
        assert all(not (o["q1"] == "2T2019") for o in obs), "S2 = 4T2019 + 1T2020"
        assert inv["descartes"]["regra_2_do_5_5"] > 0

    def test_s1_numa_escala_e_s2_noutra_homogeneos_nao_sao_censurados(self):
        """Redenominação real no começo de 2020: S1 = 3T+4T 2019 (MIL), S2 = 1T+2T 2020
        (UNIDADE). Cada parte é homogênea; a janela também."""
        b = empresa(Base(), "A", escala=lambda ano, k: "UNIDADE" if ano >= 2020 else "MIL",
                    fco=lambda ano, k: (100 + k) * (1000 if ano >= 2020 else 1),
                    ativo=lambda ano, k: 50_000 * (1000 if ano >= 2020 else 1))
        p, _ = painel(b)
        obs, _ = amostra(p)
        assert any(o["q1"] == "3T2019" for o in obs)


def _fco_provado_ativo_nao():
    """O 2T2019 declara UNIDADE; o FCO dele foi corrigido com prova (decidido) e o
    ativo não tem veredito. As regras 1 e 2 não veem nada — o FCO é homogêneo —,
    mas o ativo em D sai mil vezes menor."""
    b = empresa(Base(), "A", escala=_u_no((2019, 2)))
    con = b.con()
    doc = chave("A", 2019, 2)
    p = pp.construir(con, correcoes_por_conta=_correcao_fco(con, doc))
    return p, doc


def _ativo_fora_do_ttm():
    """A DFP e o 3T de 2019 só ficam disponíveis em 10/05/2020 (o 3T foi
    reapresentado); o 1T2020, que declara UNIDADE, traz ativo válido mas FCO de um
    período de 60 dias — sem trimestre utilizável. Em D = 10/05/2020 o ativo vem do
    1T2020, documento que não opera no TTM (1T–4T de 2019)."""
    b = empresa(Base(), "A", pular={(2019, 3), (2020, 1)})
    b.doc("A", "itr", "2019-09-30", "2020-05-10", versao=2, receb_v1="2019-11-09",
          fco=[("2019-01-01", "2019-09-30", 101 + 102 + 103)], ativo=50_000)
    b.doc("A", "itr", "2020-03-31", "2020-05-10", escala="UNIDADE",
          fco=[("2020-02-01", "2020-03-31", 50)], ativo=50_000)
    return painel(b)[0]


class TestRegra3:
    def test_ativo_de_documento_fora_do_ttm_sem_veredito_torna_a_razao_ausente(self):
        p = _ativo_fora_do_ttm()
        obs, _ = amostra(p)
        o = _obs(obs)["2020-05-10"]
        doc_ativo = tuple(o["linhagem"]["ativo"]["doc"])
        docs_ttm = {tuple(x[:4]) for t in o["linhagem"]["janela"][-4:] for x in t["docs"]}
        assert doc_ativo == ("A", "itr", "2020-03-31", 1) and doc_ativo not in docs_ttm
        assert o["fco_ttm_sobre_ativo"] is None
        assert o["ativo_total_em_D"] > 0 and o["fco_ttm_sobre_sd8"] is not None
        assert ex.gate_g0_5(obs, NENHUM)["violacoes"]["regra_3"] == 0


    def test_ativo_sem_veredito_em_escala_diferente_do_ttm_torna_a_razao_ausente(self):
        p, doc = _fco_provado_ativo_nao()
        decididos = {"ativo": set(), "fco": {doc}}
        obs, inv = amostra(p, decididos)
        d = (fim_do_trimestre(2019, 2) + timedelta(days=40)).isoformat()
        o = _obs(obs)[d]
        assert o["fco_ttm_sobre_ativo"] is None
        assert o["ativo_total_em_D"] > 0 and o["fco_ttm_sobre_sd8"] is not None, \
            "a observação continua nos outros componentes"
        assert inv["regra_3_fco_ttm_sobre_ativo_ausente"] == sum(
            1 for x in obs if x["fco_ttm_sobre_ativo"] is None)

    def test_os_dois_lados_decididos_mantem_a_razao(self):
        """Ativo em D com veredito e o FCO de TODOS os documentos do TTM com veredito:
        as escalas diferentes estão adjudicadas, e a razão fica."""
        p, doc = _fco_provado_ativo_nao()
        todos = {(a["cd_cvm"], a["conjunto"], a["dt_refer"], a["versao"]) for a in p.ativo}
        obs, inv = amostra(p, {"ativo": {doc}, "fco": todos})
        d = (fim_do_trimestre(2019, 2) + timedelta(days=40)).isoformat()
        assert _obs(obs)[d]["fco_ttm_sobre_ativo"] is not None
        assert inv["regra_3_fco_ttm_sobre_ativo_ausente"] == 0

    def test_um_documento_do_ttm_sem_veredito_basta_para_a_ausencia(self):
        """A regra compara o ativo com CADA documento do TTM (§5.5, regra 3)."""
        p, doc = _fco_provado_ativo_nao()
        obs, _ = amostra(p, {"ativo": {doc}, "fco": {doc}})
        d = (fim_do_trimestre(2019, 2) + timedelta(days=40)).isoformat()
        assert _obs(obs)[d]["fco_ttm_sobre_ativo"] is None


class TestG05:
    def test_construtor_que_usa_o_censurado_reprova(self):
        p, _ = painel(empresa(Base(), "A", escala=_u_no((2018, 2))))
        obs, _ = amostra(p)
        assert ex.gate_g0_5(obs, NENHUM)["aprovado"]
        # Sabotagem: a linhagem de uma observação passa a ter o trimestre censurado.
        prep = ex.preparar_trimestres(p.fco_trimestral, NENHUM, frozenset({"A"}))
        censurado = next(t for t in prep["A"] if t["estado_v2"] == ex.ESTADO_REGRA_1)
        obs[0]["linhagem"]["janela"][0] = ex._procedencia(censurado)
        g = ex.gate_g0_5(obs, NENHUM)
        assert not g["aprovado"] and g["violacoes"]["regra_1"] == 1

    def test_construtor_que_usa_janela_heterogenea_reprova_pela_regra_2(self):
        """Achado M6: o G0.5 recalcula a regra 2, não só a 1."""
        p, _ = painel(empresa(Base(), "A"))
        obs, _ = amostra(p)
        assert ex.gate_g0_5(obs, NENHUM)["aprovado"]
        o = next(o for o in obs if any(len(t["docs"]) == 1 for t in o["linhagem"]["janela"]))
        arquivado = next(t for t in o["linhagem"]["janela"] if len(t["docs"]) == 1)
        arquivado["docs"][0][4] = "UNIDADE"
        g = ex.gate_g0_5(obs, NENHUM)
        assert g["violacoes"]["regra_2"] >= 1 and g["violacoes"]["regra_1"] == 0
        assert not g["aprovado"]

    def test_amostra_vazia_reprova(self):
        """Achado B1: amostra vazia não aprova G0.5 (C5)."""
        assert not ex.gate_g0_5([], NENHUM)["aprovado"]

    def test_razao_presente_no_caso_da_regra_3_reprova(self):
        p, doc = _fco_provado_ativo_nao()
        decididos = {"ativo": set(), "fco": {doc}}
        obs, _ = amostra(p, decididos)
        assert ex.gate_g0_5(obs, decididos)["aprovado"]
        o = next(o for o in obs if o["fco_ttm_sobre_ativo"] is None)
        o["fco_ttm_sobre_ativo"] = 0.5
        g = ex.gate_g0_5(obs, decididos)
        assert g["violacoes"]["regra_3"] == 1 and not g["aprovado"]


# --- §6.1 -------------------------------------------------------------------------------

class TestGrade:
    def test_duas_datas_com_o_mesmo_q1_fica_a_maior(self):
        """3T2019 chega em 15/02/2020 e a DFP em 20/03/2020: as duas datas têm q1 = 2T2020."""
        b = empresa(Base(), "A", receb=lambda ano, k: (
            date(2020, 2, 15) if (ano, k) == (2019, 3) else
            fim_do_trimestre(ano, k) + timedelta(days=80 if k == 4 else 40)))
        p, _ = painel(b)
        obs, inv = amostra(p)
        com_q1 = [o for o in obs if o["q1"] == "2T2020"]
        assert [o["D"] for o in com_q1] == ["2020-03-20"]
        assert inv["q1_repetido_chaves_afetadas"] >= 1
        assert inv["descartes"]["q1_repetido_mantido_o_maior_D"] >= 1

    def test_maior_data_censurada_perde_a_chave_sem_reposicao(self):
        """A DFP de 2019 chega em 15/04/2020 (q1 = 3T2020) e o 1T2020, UNIDADE e
        arquivado, em 10/05/2020 (q1 = 3T2020). Fica 10/05, que cai na regra 2."""
        b = empresa(Base(), "A", escala=_u_no((2020, 1)),
                    receb=lambda ano, k: (date(2020, 4, 15) if (ano, k) == (2019, 4) else
                                          fim_do_trimestre(ano, k) + timedelta(days=80 if k == 4 else 40)))
        p, _ = painel(b)
        obs, inv = amostra(p)
        assert not [o for o in obs if o["q1"] == "3T2020"]
        assert inv["descartes"]["regra_2_do_5_5"] >= 1

    def test_maior_data_inelegivel_perde_a_chave_sem_reposicao(self):
        """Mesmo par de datas; o FCO TTM na maior data não é positivo."""
        fco = lambda ano, k: -1000 if (ano, k) == (2020, 1) else 100 + k  # noqa: E731
        b = empresa(Base(), "A", fco=fco,
                    receb=lambda ano, k: (date(2020, 4, 15) if (ano, k) == (2019, 4) else
                                          fim_do_trimestre(ano, k) + timedelta(days=80 if k == 4 else 40)))
        p, _ = painel(b)
        obs, inv = amostra(p)
        assert not [o for o in obs if o["q1"] == "3T2020"]
        assert inv["descartes"]["fco_ttm_nao_positivo"] >= 1

    def test_data_que_falha_em_dois_motivos_conta_so_no_primeiro(self):
        """Histórico insuficiente E sem ativo: conta só no 3."""
        b = empresa(Base(), "A", inicio=2019, fim=2020, ativo=lambda ano, k: 0)
        p, _ = painel(b)
        obs, inv = amostra(p)
        assert not obs
        assert inv["descartes"]["sem_ativo_disponivel"] == 0
        assert inv["descartes"]["historico_insuficiente"] > 0
        assert sum(inv["descartes"].values()) == inv["grade"]

    def test_toda_data_da_grade_sai_em_exatamente_um_motivo_ou_fica(self):
        p, _ = painel(empresa(empresa(Base(), "A", escala=_u_no((2018, 2))), "B"))
        obs, inv = amostra(p)
        assert sum(inv["descartes"].values()) + len(obs) == inv["grade"]


# --- G1 ----------------------------------------------------------------------------------

class TestG1:
    def test_amostra_limpa_aprova(self):
        p, _ = painel(empresa(Base(), "A"))
        obs, inv = amostra(p)
        g1 = ex.gate_g1_v2(obs, ex.descartes_publicaveis(inv), SEM_PROVAS)
        assert g1["aprovado"] and g1["q1_repetido"] == 0

    def test_q1_repetido_reprova(self):
        p, _ = painel(empresa(Base(), "A"))
        obs, inv = amostra(p)
        copia = dict(obs[0], D=(date.fromisoformat(obs[0]["D"]) - timedelta(days=1)).isoformat())
        g1 = ex.gate_g1_v2(obs + [copia], ex.descartes_publicaveis(inv), SEM_PROVAS)
        assert g1["q1_repetido"] == 1 and not g1["aprovado"]

    def test_prova_de_escala_do_fco_publicada_depois_de_d_reprova(self):
        p, _ = painel(empresa(Base(), "A"))
        obs, inv = amostra(p)
        doc = tuple(obs[0]["linhagem"]["janela"][-1]["docs"][-1][:4])
        provas = {"ativo": {}, "fco": {doc: date.fromisoformat(obs[0]["D"]) + timedelta(days=1)}}
        g1 = ex.gate_g1_v2(obs, ex.descartes_publicaveis(inv), provas)
        assert g1["g1_4_prova_de_escala_publicada_depois_de_D"] >= 1 and not g1["aprovado"]

    def test_prova_de_escala_do_ativo_publicada_depois_de_d_reprova(self):
        """Achado M6: o G1.4 confere também a prova do ativo."""
        p, _ = painel(empresa(Base(), "A"))
        obs, inv = amostra(p)
        doc = tuple(obs[0]["linhagem"]["ativo"]["doc"])
        provas = {"ativo": {doc: date.fromisoformat(obs[0]["D"]) + timedelta(days=1)}, "fco": {}}
        g1 = ex.gate_g1_v2(obs, ex.descartes_publicaveis(inv), provas)
        assert g1["g1_4_prova_de_escala_publicada_depois_de_D"] >= 1 and not g1["aprovado"]

    def test_amostra_vazia_reprova(self):
        assert not ex.gate_g1_v2([], {}, SEM_PROVAS)["aprovado"]


# --- rótulo --------------------------------------------------------------------------------

class TestRotulo:
    def test_rotulo_sem_congelamento_levanta(self):
        """C10: pedir o rótulo sem o registro do congelamento é recusado."""
        p, _ = painel(empresa(Base(), "A"))
        pop = ex.populacao_v2(p.ativo, p.fco_trimestral)
        with pytest.raises(ex.NaoCongelado):
            ex.construir_amostra_v2(p.fco_trimestral, p.ativo, NENHUM, pop["incluidas"],
                                    calcular_rotulo=True)
        with pytest.raises(ex.NaoCongelado):
            ex.construir_amostra_v2(p.fco_trimestral, p.ativo, NENHUM, pop["incluidas"],
                                    calcular_rotulo=True, congelamento={})

    def test_estrutural_nunca_soma_o_rotulo(self, monkeypatch):
        p, _ = painel(empresa(Base(), "A"))
        obs, _ = amostra(p)
        assert obs and all("y" not in o for o in obs)

    def test_com_rotulo_as_chaves_sao_as_mesmas(self):
        p, _ = painel(empresa(Base(), "A", fco=lambda ano, k: -50 if ano == 2020 else 100 + k))
        sem, _ = amostra(p)
        com, _ = amostra(p, rotulo=True)
        assert [(o["cd_cvm"], o["D"]) for o in sem] == [(o["cd_cvm"], o["D"]) for o in com]
        assert {o["y"] for o in com} == {0, 1}


# --- §8.1 -------------------------------------------------------------------------------

def observacoes_t2(companhias: int, n_por=8, sinal=0.0, semente=1, dois_rotulos=None):
    """Observações sintéticas: escore B1 = −fco_ttm_sobre_sd8; `sinal` puxa o evento
    para os escores maiores. `dois_rotulos` limita quantas companhias têm os dois."""
    rng = random.Random(semente)
    saida = []
    for c in range(companhias):
        for i in range(n_por):
            x = rng.gauss(0, 1)
            y = 1 if rng.random() < 1 / (1 + pow(2.718, -(sinal * -x))) else 0
            if dois_rotulos is not None:
                if c >= dois_rotulos:
                    y = 0
                elif i == 0:
                    y = 1
                elif i == 1:
                    y = 0
            saida.append({"cd_cvm": f"{c:06d}", "fco_ttm_sobre_sd8": x, "y": y})
    return saida


class TestT2:
    def test_29_companhias_com_os_dois_rotulos_e_indecidivel(self):
        r = ex.teste_t2_v2(observacoes_t2(40, dois_rotulos=29))
        assert r["companhias_com_os_dois_rotulos"] == 29
        assert r["indecidivel"] and not r["aprovado"] and not r["reprova_numericamente"]

    def test_30_companhias_segue_para_o_limiar(self):
        r = ex.teste_t2_v2(observacoes_t2(40, dois_rotulos=30))
        assert r["companhias_com_os_dois_rotulos"] == 30 and "lacuna" in r
        assert r["reamostragens_validas"] == auditor.REAMOSTRAGENS, \
            "reamostragem com menos de 30 companhias de dois rótulos, mas AUCs calculáveis, vale"

    def test_lacuna_abaixo_do_limiar_com_frequencia_alta_e_indecidivel(self):
        """32 companhias ordenadas por risco (entre companhias, não no tempo), poucas
        observações cada: a lacuna fica abaixo de 0,12 e instável no bootstrap."""
        rng = random.Random(5)
        obs = []
        for c in range(32):
            b = c / 32
            ys = [1 if rng.random() < 0.25 + 0.3 * (b - 0.5) else 0 for _ in range(6)]
            ys[0], ys[1] = 1, 0
            obs += [{"cd_cvm": f"{c:06d}", "fco_ttm_sobre_sd8": -(b + rng.gauss(0, 0.05)), "y": y}
                    for y in ys]
        r = ex.teste_t2_v2(obs)
        # Pré-condição da fixture, conferida — não pulada: ela tem de cair na zona.
        assert r["lacuna"] < auditor.T2_LACUNA
        assert r["frequencia_bootstrap_de_lacuna_no_limiar"] > ex.FREQUENCIA_MAXIMA_T2
        assert r["indecidivel"] and not r["aprovado"] and not r["reprova_numericamente"]

    def test_menos_de_40_reamostragens_validas_e_indecidivel(self, monkeypatch):
        monkeypatch.setattr(auditor, "REAMOSTRAGENS", 39)
        r = ex.teste_t2_v2(observacoes_t2(40, dois_rotulos=35))
        assert r["indecidivel"] and r["reamostragens_validas"] == 39

    def test_mesma_amostra_mesma_frequencia(self):
        obs = observacoes_t2(40, dois_rotulos=35, sinal=1.0)
        assert ex.teste_t2_v2(obs) == ex.teste_t2_v2(list(obs))

    def test_ordem_da_amostra_nao_muda_o_bootstrap(self):
        """Achado M6: as companhias são ordenadas por `cd_cvm` antes do sorteio."""
        obs = observacoes_t2(40, dois_rotulos=35, sinal=1.0)
        embaralhadas = list(obs)
        random.Random(11).shuffle(embaralhadas)
        assert ex.teste_t2_v2(obs) == ex.teste_t2_v2(embaralhadas)

    def test_escore_constante_levanta(self):
        obs = [{"cd_cvm": f"{c:06d}", "fco_ttm_sobre_sd8": 1.0, "y": c % 2} for c in range(40)]
        with pytest.raises(auditor.EscoreDegenerado):
            ex.teste_t2_v2(obs)

    def test_lacuna_no_limiar_rejeita(self):
        """Ordenação só de emissor: o escore separa companhias, não o tempo."""
        obs = []
        for c in range(40):
            risco = c / 40
            for i in range(10):
                obs.append({"cd_cvm": f"{c:06d}", "fco_ttm_sobre_sd8": -risco + (i % 2) * 1e-3,
                            "y": 1 if (i < 10 * risco or i == 0) and i != 9 else 0})
        r = ex.teste_t2_v2(obs)
        assert r["lacuna"] >= auditor.T2_LACUNA and r["reprova_numericamente"]


# --- veredito, publicação e congelamento ---------------------------------------------------

class TestVeredito:
    def test_vocabulario(self):
        ok = {"aprovado": True}
        assert ex.veredito_v2({"aprovado": False}, ok, ok, None, None, None) == "REPROVADO EM G0/G1"
        assert ex.veredito_v2(ok, {"aprovado": False}, ok, None, None, None) == "REPROVADO EM G0/G1"
        assert ex.veredito_v2(ok, ok, ok, {"reprova_numericamente": True}, {}, {}) == "REJEITADO"
        assert ex.veredito_v2(ok, ok, ok, {"aprovado": True}, {"reprova_numericamente": True},
                              {"todos_completos": True}) == "REJEITADO"
        assert ex.veredito_v2(ok, ok, ok, {"aprovado": True}, {"aprovado": False, "indecidivel": True},
                              {"todos_completos": True}) == "INDECIDIVEL"
        assert ex.veredito_v2(ok, ok, ok, {"aprovado": True}, {"aprovado": True},
                              {"todos_completos": False}) == "INDECIDIVEL"
        assert ex.veredito_v2(ok, ok, ok, {"aprovado": True}, {"aprovado": True},
                              {"todos_completos": True}) == "PRONTO PARA CHALLENGER"


class TestPublicacao:
    def _estrutura(self):
        b = empresa(empresa(Base(), "A", escala=_u_no((2018, 2))), "B")
        p, _ = painel(b)
        return ex.estrutura(p.ativo, p.fco_trimestral, _nulos(p), NENHUM, SEM_PROVAS, {}), p

    def test_artefato_sem_rotulo_sem_grade_e_sem_motivo_11(self):
        e, _ = self._estrutura()
        art = ex.artefato_estrutural(e)
        texto = json.dumps(art, default=str)
        assert '"y"' not in texto and '"grade"' not in texto
        assert ex.MOTIVO_OMITIDO not in art["amostra_sem_rotulo"]["descartes_por_motivo"]
        assert "fco_ttm_nao_positivo\": " not in texto.replace('"omitido', "")

    def test_numeros_publicados_nao_recompoem_o_motivo_11(self):
        """Achado da auditoria: sem colisão de disponibilidade, linhas válidas de FCO
        da população − regra 1 − motivos publicados − observações finais = motivo 11.
        O fixture tem motivo 11 > 0 e nenhuma colisão; o número das linhas válidas
        da população não pode estar no artefato."""
        fco = lambda ano, k: -500 if ano == 2019 else 100 + k  # noqa: E731
        b = empresa(empresa(Base(), "A", fim=2022, fco=fco, escala=_u_no((2016, 2))), "B")
        p, _ = painel(b)
        e = ex.estrutura(p.ativo, p.fco_trimestral, _nulos(p), NENHUM, SEM_PROVAS, {})
        inv = e["inventario"]
        assert inv["descartes"][ex.MOTIVO_OMITIDO] > 0
        validas = e["g0"]["observacoes_de_fco"]
        regra_1 = sum(e["publicacao_5_5"]["regra_1_trimestres_por_companhia"].values())
        publicados = sum(n for m, n in inv["descartes"].items() if m != ex.MOTIVO_OMITIDO)
        assert validas - regra_1 - publicados - len(e["amostra"]) == inv["descartes"][ex.MOTIVO_OMITIDO], \
            "a recomposição seria exata com o número das linhas válidas"
        art = ex.artefato_estrutural(e)
        assert "observacoes_de_fco" not in art["g0"]
        with pytest.raises(AssertionError, match="O1"):
            ex.verificar_publicavel({"g0": {"observacoes_de_fco": validas}})

    def test_chave_proibida_em_qualquer_nivel_derruba(self):
        with pytest.raises(AssertionError, match="O1"):
            ex.verificar_publicavel({"g1": {"x": [{"taxa_do_evento": 0.05}]}})

    def test_mesma_saida_em_processos_com_hash_diferente(self):
        """Achado M6: o determinismo tem de valer entre processos."""
        import os
        import subprocess
        import sys
        codigo = ("import json;from tests.test_executor_v2_rank03b import TestPublicacao as T;"
                  "from scripts import executor_v2_rank03b as ex;"
                  "print(json.dumps(ex.artefato_estrutural(T()._estrutura()[0]),"
                  "sort_keys=True,default=str))")
        saidas = []
        for semente in ("1", "2"):
            ambiente = {**os.environ, "PYTHONHASHSEED": semente, "PYTHONPATH": "."}
            r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                               env=ambiente, cwd=str(ex.RAIZ), timeout=300)
            assert r.returncode == 0, r.stderr[-2000:]
            saidas.append(r.stdout)
        assert saidas[0] == saidas[1]

    def test_mesma_entrada_mesma_saida(self):
        a = json.dumps(ex.artefato_estrutural(self._estrutura()[0]), sort_keys=True, default=str)
        b = json.dumps(ex.artefato_estrutural(self._estrutura()[0]), sort_keys=True, default=str)
        assert a == b


class TestCongelamento:
    PINS = {"digest_do_painel": "d" * 64, "manifesto_por_conta": "m" * 64,
            "evidencias_da_rota": "e" * 64, "conferencia_da_rota": "c" * 64,
            "adendo_o1": "a" * 64, "executor_v2": "x" * 64}

    #: AF1 (28/09): o sintético ganhou a linha de status que o congelado real terá;
    #: as asserções dos casos já existentes não mudaram.
    STATUS = "**Status: CONGELADO em 2026-10-01, por ato do responsável.**"

    def _arquivo(self, tmp_path, nome="pre_registro_rank03b_v2_2026-10-01.md",
                 titulo="# Pré-registro v2", pins=None, status=STATUS):
        pins = self.PINS if pins is None else pins
        caminho = tmp_path / nome
        cabecalho = titulo + "\n\n" + (status + "\n\n" if status is not None else "")
        caminho.write_text(cabecalho + "\n".join(f"- {k}: `{v}`" for k, v in pins.items()),
                           encoding="utf-8")
        return caminho, ex.sha256(caminho)

    @pytest.mark.parametrize("status", [
        "**Status: RASCUNHO — NÃO CONGELADO. O congelamento aguarda ato explícito.**",
        "**Status: NÃO CONGELADO.**",
        "**Status: em revisão.**",
    ])
    def test_status_que_nao_declara_congelamento_recusa(self, tmp_path, status):
        caminho, sha = self._arquivo(tmp_path, status=status)
        with pytest.raises(ex.NaoCongelado, match="status"):
            ex.verificar_congelamento(caminho, sha, self.PINS)

    def test_sem_linha_de_status_recusa(self, tmp_path):
        caminho, sha = self._arquivo(tmp_path, status=None)
        with pytest.raises(ex.NaoCongelado, match="status"):
            ex.verificar_congelamento(caminho, sha, self.PINS)

    def _copia_do_rascunho_real(self, tmp_path, status=None):
        texto = ex.PRE_REGISTRO_RASCUNHO.read_text(encoding="utf-8")
        if status is not None:
            linha = next(l for l in texto.splitlines() if l.startswith("**Status:"))
            texto = texto.replace(linha, status, 1)
        caminho = tmp_path / "pre_registro_rank03b_v2_2026-09-16.md"
        caminho.write_text(texto + "\n" + "\n".join(f"- {k}: `{v}`" for k, v in self.PINS.items())
                           + "\n", encoding="utf-8")
        return caminho, ex.sha256(caminho)

    def test_copia_do_rascunho_real_so_com_o_nome_trocado_recusa(self, tmp_path):
        """Achado B1 da auditoria final: a primeira linha do rascunho real nunca teve
        RASCUNHO, e a cópia só renomeada passava como congelada."""
        assert "RASCUNHO" not in ex.PRE_REGISTRO_RASCUNHO.read_text(encoding="utf-8").splitlines()[0]
        caminho, sha = self._copia_do_rascunho_real(tmp_path)
        with pytest.raises(ex.NaoCongelado, match="status"):
            ex.verificar_congelamento(caminho, sha, self.PINS)

    def test_linha_congelado_acrescentada_sem_trocar_a_do_rascunho_recusa(self, tmp_path):
        """Ressalva 1 da verificação de 28/09: acrescentar uma linha CONGELADO antes
        da linha RASCUNHO, sem trocá-la, passava. Toda linha de status tem de
        declarar congelamento."""
        texto = ex.PRE_REGISTRO_RASCUNHO.read_text(encoding="utf-8")
        linhas = texto.splitlines()
        linhas.insert(2, self.STATUS)
        caminho = tmp_path / "pre_registro_rank03b_v2_2026-09-16.md"
        caminho.write_text("\n".join(linhas) + "\n"
                           + "\n".join(f"- {k}: `{v}`" for k, v in self.PINS.items()) + "\n",
                           encoding="utf-8")
        with pytest.raises(ex.NaoCongelado, match="status"):
            ex.verificar_congelamento(caminho, ex.sha256(caminho), self.PINS)

    @pytest.mark.parametrize("variante", [
        "**Status: NAO CONGELADO.**",
        "**Status: não está congelado.**",
        "**Status: a ser congelado.**",
        "**Status: DESCONGELADO.**",
        "**Status: CONGELADO.**",
        "**Status: CONGELADO em breve.**",
        "**Status: CONGELADO em 2026-10-01**",
        unicodedata.normalize("NFD", "**Status: NÃO CONGELADO em 2026-10-01.**"),
    ])
    def test_variantes_de_status_que_nao_declaram_congelamento_com_data(self, tmp_path, variante):
        """Ressalva 1: casamento POSITIVO com `**Status: CONGELADO em AAAA-MM-DD`,
        depois de normalizar para NFC. O penúltimo caso, sem ponto final, passa;
        os outros recusam."""
        caminho, sha = self._arquivo(tmp_path, status=variante)
        if variante == "**Status: CONGELADO em 2026-10-01**":
            assert ex.verificar_congelamento(caminho, sha, self.PINS)["sha256"] == sha
            return
        with pytest.raises(ex.NaoCongelado, match="status"):
            ex.verificar_congelamento(caminho, sha, self.PINS)

    @pytest.mark.parametrize("segunda", [
        "status: rascunho", "> **Status: RASCUNHO — NÃO CONGELADO.**", "- **Status:** rascunho",
    ])
    def test_segunda_linha_de_status_em_qualquer_forma_tambem_conta(self, tmp_path, segunda):
        """Minúsculas, sem negrito, em citação ou em lista: toda linha de status
        tem de declarar congelamento com data."""
        caminho, sha = self._arquivo(tmp_path, status=self.STATUS + "\n\n" + segunda)
        with pytest.raises(ex.NaoCongelado, match="status"):
            ex.verificar_congelamento(caminho, sha, self.PINS)

    def test_copia_do_rascunho_real_com_o_status_trocado_passa(self, tmp_path):
        """O procedimento do M1: cópia com nome novo, linha de status trocada e pins."""
        caminho, sha = self._copia_do_rascunho_real(tmp_path, status=self.STATUS)
        assert ex.verificar_congelamento(caminho, sha, self.PINS)["sha256"] == sha

    def test_congelado_passa(self, tmp_path):
        caminho, sha = self._arquivo(tmp_path)
        assert ex.verificar_congelamento(caminho, sha, self.PINS)["sha256"] == sha

    def test_nome_com_rascunho_recusa(self, tmp_path):
        caminho, sha = self._arquivo(tmp_path, nome="pre_registro_v2_RASCUNHO.md")
        with pytest.raises(ex.NaoCongelado, match="nome"):
            ex.verificar_congelamento(caminho, sha, self.PINS)

    def test_titulo_com_rascunho_recusa(self, tmp_path):
        caminho, sha = self._arquivo(tmp_path, titulo="# Pré-registro v2 — RASCUNHO")
        with pytest.raises(ex.NaoCongelado, match="título"):
            ex.verificar_congelamento(caminho, sha, self.PINS)

    def test_hash_diferente_recusa(self, tmp_path):
        caminho, _ = self._arquivo(tmp_path)
        with pytest.raises(ex.NaoCongelado, match="SHA-256"):
            ex.verificar_congelamento(caminho, "0" * 64, self.PINS)

    @pytest.mark.parametrize("falta", sorted(PINS))
    def test_pin_ausente_recusa(self, tmp_path, falta):
        caminho, sha = self._arquivo(tmp_path, pins={k: v for k, v in self.PINS.items() if k != falta})
        with pytest.raises(ex.NaoCongelado, match=falta):
            ex.verificar_congelamento(caminho, sha, self.PINS)

    def test_medicao_sem_pre_registro_recusa_na_linha_de_comando(self):
        with pytest.raises(ex.NaoCongelado):
            ex.principal(["--medir"])

    def test_rascunho_vigente_nao_mede(self):
        with pytest.raises(ex.NaoCongelado):
            ex.verificar_congelamento(ex.PRE_REGISTRO_RASCUNHO, ex.sha256(ex.PRE_REGISTRO_RASCUNHO),
                                      self.PINS)


class TestEntradas:
    """Achados M1, M2 e M3 da auditoria de 27/09."""

    def test_decidido_sem_a_escala_aplicada_e_incoerente(self):
        """M1: a prova decide MIL para o FCO, mas o manifesto não trouxe a linha."""
        b = empresa(Base(), "A", escala=_u_no((2018, 2)))
        p, con = painel(b)
        doc = chave("A", 2018, 2)
        with pytest.raises(ex.EntradaIncoerente, match="decide MIL"):
            ex.conferir_decididos_aplicados(p, {(doc, "fco"): "MIL"})
        corrigido = pp.construir(con, correcoes_por_conta=_correcao_fco(con, doc))
        assert ex.conferir_decididos_aplicados(corrigido, {(doc, "fco"): "MIL"}) == 1

    def test_confirmacao_contrariada_por_correcao_e_incoerente(self):
        b = empresa(Base(), "A")
        p, con = painel(b)
        doc = chave("A", 2018, 2)
        corrigido = pp.construir(con, correcoes_por_conta=_correcao_fco(
            con, doc, declarada="MIL", aplicada="UNIDADE"))
        with pytest.raises(ex.EntradaIncoerente):
            ex.conferir_decididos_aplicados(corrigido, {(doc, "fco"): "MIL"})

    @pytest.mark.parametrize("rota,manifesto", [(True, False), (False, True)])
    def test_rota_e_manifesto_entram_juntos(self, tmp_path, rota, manifesto):
        """M2: um sem o outro seria ignorado em silêncio."""
        with pytest.raises(ex.EntradaIncoerente):
            ex.carregar_entradas(tmp_path if rota else None,
                                 tmp_path / "m.csv" if manifesto else None)

    def test_pin_cobre_o_codigo_de_medicao_e_rele_o_adendo(self):
        """M3: T1, AUC, baselines e limiares vivem no auditor de 11/09."""
        assert "scripts/auditar_rank03b_consumo_operacional.py" in ex.CODIGO_DE_MEDICAO
        assert "src/normalizacao.py" in ex.CODIGO_DE_MEDICAO
        assert all((ex.RAIZ / a).is_file() for a in ex.CODIGO_DE_MEDICAO)
        pins = ex.pins_do_congelamento()
        assert pins["codigo_de_medicao"] == ex.digest_do_codigo()
        assert pins["adendo_o1"] == "7f51ab27aff2604e8ec2b3a46f7e39cc12dd8aa82d52a44b2bb47dd158414b0f"

    def test_pin_fixa_a_conferencia_pelos_dois_caminhos(self, tmp_path):
        """§13 (27/09): o registro da conferência entra no congelamento por nome.
        Pelos arquivos e pela entrada carregada, o pin é o mesmo hash, e um
        pré-registro sem ele é recusado."""
        (tmp_path / "evidencias.jsonl").write_text("{}\n", encoding="utf-8")
        (tmp_path / "conferencia.json").write_text("{}", encoding="utf-8")
        manifesto = tmp_path / "m.csv"
        manifesto.write_text("x", encoding="utf-8")
        por_arquivo = ex.pins_do_congelamento(manifesto_por_conta=manifesto, pasta_rota=tmp_path)
        assert por_arquivo["conferencia_da_rota"] == ex.sha256(tmp_path / "conferencia.json")
        entrada = {"painel": type("P", (), {"digest": {"conjunto": "d" * 64}})(),
                   "entradas": {"correcoes_por_conta": {"sha256": ex.sha256(manifesto)},
                                "rota": {"sha256_evidencias": ex.sha256(tmp_path / "evidencias.jsonl"),
                                         "sha256_conferencia": ex.sha256(tmp_path / "conferencia.json")}}}
        pela_entrada = ex.pins_do_congelamento(entrada)
        assert {k: v for k, v in pela_entrada.items() if k != "digest_do_painel"} == por_arquivo
        sem = {k: v for k, v in pela_entrada.items() if k != "conferencia_da_rota"}
        caminho = tmp_path / "pre_registro.md"
        # AF1 (28/09): o fixture ganhou a linha de status, para a recusa vir do pin.
        caminho.write_text("# Pré-registro\n\n" + TestCongelamento.STATUS + "\n\n"
                           + "\n".join(sem.values()) + "\n", encoding="utf-8")
        with pytest.raises(ex.NaoCongelado, match="conferencia_da_rota"):
            ex.verificar_congelamento(caminho, ex.sha256(caminho), pela_entrada)

    def test_medicao_nao_sobrescreve(self, tmp_path):
        (tmp_path / "medicao.json").write_text("{}", encoding="utf-8")
        with pytest.raises(FileExistsError):
            ex.executar_medicao(tmp_path / "x.md", "0" * 64, tmp_path, tmp_path / "m.csv",
                                destino=tmp_path)


class TestReconferencia:
    def test_dict_comum_nao_destrava_o_rotulo(self):
        """B-a: só o objeto emitido pela verificação do congelamento destrava."""
        p, _ = painel(empresa(Base(), "A"))
        pop = ex.populacao_v2(p.ativo, p.fco_trimestral)
        with pytest.raises(ex.NaoCongelado):
            ex.construir_amostra_v2(p.fco_trimestral, p.ativo, NENHUM, pop["incluidas"],
                                    calcular_rotulo=True, congelamento={"sha256": "x" * 64})

    def test_janela_com_lacuna_sempre_tem_o_censurado_e_o_motivo_5_fica_zero(self):
        """T3: a lacuna (3T e 4T de 2018) vem logo depois do 2T2018 censurado; toda
        janela que atravessa a lacuna contém o censurado. Na ordem certa, o motivo 5
        não recebe nenhuma data."""
        p, _ = painel(empresa(Base(), "A", pular={(2018, 3)}, escala=_u_no((2018, 2))))
        _, inv = amostra(p)
        assert inv["descartes"]["janela_com_trimestre_do_5_5"] > 0
        assert inv["descartes"]["janela_com_lacuna"] == 0

    def test_folga_do_motivo_11(self):
        """B-b: sem colisão e sem companhia excluída, a folga é zero; uma seguradora
        excluída com FCO válido dá folga."""
        p, _ = painel(empresa(Base(), "A"))
        pop = ex.populacao_v2(p.ativo, p.fco_trimestral)
        assert ex.folga_do_motivo_11(p.fco_trimestral, NENHUM, pop) == 0
        p2, _ = painel(empresa(empresa(Base(), "A"), "S"), {"S": "ll3_13_48e4cd07"})
        pop2 = ex.populacao_v2(p2.ativo, p2.fco_trimestral)
        assert ex.folga_do_motivo_11(p2.fco_trimestral, NENHUM, pop2) > 0

    def test_folga_conta_colisoes_de_disponibilidade(self):
        """O 1T chega junto do 2T: duas linhas utilizáveis com a mesma data."""
        b = empresa(Base(), "A", receb=lambda ano, k: (
            fim_do_trimestre(ano, 2) + timedelta(days=40) if (ano, k) == (2018, 1)
            else fim_do_trimestre(ano, k) + timedelta(days=80 if k == 4 else 40)))
        p, _ = painel(b)
        pop = ex.populacao_v2(p.ativo, p.fco_trimestral)
        assert ex.folga_do_motivo_11(p.fco_trimestral, NENHUM, pop) >= 1


class TestLigacoesDeCarregarEntradas:
    """Reconferência T2: as ligações de `carregar_entradas` com contraprova, sobre um
    painel sintético (as fontes reais são substituídas)."""

    def _preparar(self, monkeypatch, tmp_path, escalas, por_conta=None, provas_legado=None,
                  construir=None, planos=None):
        from scripts import correcoes_por_conta_rank03b as pc
        from scripts import fonte_zip_cvm as fz
        from scripts import gates_painel_pesquisa_rank03b as gates
        from scripts import rota_prova_rank03b as rota

        b = construir() if construir else empresa(Base(), "A", escala=_u_no((2018, 2)))
        con = b.con()
        for cd, plano in (planos or {}).items():
            con.execute("UPDATE universo SET plano_contas = ? WHERE cd_cvm = ?", [plano, cd])
        manifesto = tmp_path / "m.csv"
        manifesto.write_text("x", encoding="utf-8")
        correcoes = pc.CorrecoesPorConta(por_conta(con) if por_conta else {}, ex.sha256(manifesto))
        import duckdb
        conectar = duckdb.connect
        # Só a conexão em memória do carregador vira o painel sintético; a gravação
        # do painel em arquivo (`pp.gravar`) usa a conexão real.
        monkeypatch.setattr("duckdb.connect", lambda *a, **k: con if a[:1] in ((), (":memory:",))
                            else conectar(*a, **k))
        monkeypatch.setattr(fz, "extrair", lambda c: {})
        monkeypatch.setattr(pp, "preparar_universo", lambda c: "h")
        monkeypatch.setattr(gates, "carregar_correcoes",
                            lambda c: gates.CorrecoesValidadas({}, "x" * 64))
        monkeypatch.setattr(gates, "datas_das_provas", lambda c, l: dict(provas_legado or {}))
        monkeypatch.setattr(gates, "verificar_falsificacoes", lambda *a: {})
        monkeypatch.setattr(rota, "vereditos_por_conta", lambda pasta: {
            "ativo": set(), "fco": {k for (k, c) in escalas if c == "fco"}, "escalas": escalas,
            "sha256_evidencias": "e" * 64, "sha256_conferencia": "c" * 64})
        monkeypatch.setattr(pc, "carregar", lambda *a, **k: correcoes)
        return manifesto

    def test_decidido_sem_aplicacao_e_recusado_na_carga(self, monkeypatch, tmp_path):
        doc = chave("A", 2018, 2)
        manifesto = self._preparar(monkeypatch, tmp_path, {(doc, "fco"): "MIL"})
        with pytest.raises(ex.EntradaIncoerente, match="decide MIL"):
            ex.carregar_entradas(tmp_path, manifesto)

    def test_decidido_aplicado_passa_e_conta(self, monkeypatch, tmp_path):
        doc = chave("A", 2018, 2)
        manifesto = self._preparar(monkeypatch, tmp_path, {(doc, "fco"): "MIL"},
                                   por_conta=lambda con: _correcao_fco(con, doc))
        e = ex.carregar_entradas(tmp_path, manifesto)
        assert e["entradas"]["decididos_conferidos_contra_o_painel"] == 1

    def test_prova_legada_entra_nas_duas_contas(self, monkeypatch, tmp_path):
        doc = chave("A", 2017, 1)
        manifesto = self._preparar(monkeypatch, tmp_path, {},
                                   provas_legado={doc: date(2019, 1, 1)})
        e = ex.carregar_entradas(tmp_path, manifesto)
        assert e["provas"]["ativo"][doc] == e["provas"]["fco"][doc] == date(2019, 1, 1)

    def test_estrutural_publica_o_inventario_com_o_estado_lacuna(self, monkeypatch, tmp_path):
        """Achado da primeira execução real (27/09): o inventário do painel conta o
        estado `lacuna` do FCO, e a guarda O1 derrubava a publicação pela colisão de
        nome com a estatística do T2. `executar_estrutural` não tinha teste nenhum;
        este o exercita de ponta a ponta sobre um painel sintético, com o 2T2017
        ausente (o 3T2017 sai com 183 dias, estado `lacuna`) e uma companhia do
        plano `ll3_13` excluída (folga do motivo 11 positiva)."""
        def construir():
            return empresa(empresa(Base(), "A", escala=_u_no((2018, 2)), pular={(2017, 2)}), "S")
        manifesto = self._preparar(monkeypatch, tmp_path, {}, construir=construir,
                                   planos={"S": "ll3_13_48e4cd07"})
        cru = ex.carregar_entradas(tmp_path, manifesto)["painel"].inventario
        assert "lacuna" in cru["fco_trimestral_por_estado"], "pré-condição: o estado existe"
        with pytest.raises(AssertionError, match="O1"):
            ex.verificar_publicavel({"inventario_do_painel": cru})
        saida = ex.executar_estrutural(tmp_path, manifesto, destino=tmp_path / "saida",
                                       destino_painel=tmp_path / "painel")
        gravado = json.loads((tmp_path / "saida" / "estrutural.json").read_text(encoding="utf-8"))
        publicado = gravado["inventario_do_painel"]["fco_trimestral_por_estado"]
        assert {x["estado"]: x["linhas"] for x in publicado} == \
            {k: v["linhas"] for k, v in cru["fco_trimestral_por_estado"].items()}
        assert saida["inventario_do_painel"]["fco_trimestral_por_estado"] == publicado
        assert (tmp_path / "painel" / "painel.duckdb").exists()

    def test_folga_zero_do_motivo_11_nao_publica_nem_grava(self, monkeypatch, tmp_path):
        """Achado B2 da auditoria final: o mutante sem a guarda da folga sobrevivia.
        Uma companhia só, sem colisão de disponibilidade e sem excluída: os números
        publicados recomporiam o motivo 11 exatamente."""
        manifesto = self._preparar(monkeypatch, tmp_path, {})
        e = ex.carregar_entradas(tmp_path, manifesto)
        pop = ex.populacao_v2(e["painel"].ativo, e["painel"].fco_trimestral)
        assert not pop["excluidas"], "pré-condição: nenhuma companhia excluída"
        assert ex.folga_do_motivo_11(e["painel"].fco_trimestral, e["decididos"], pop) == 0
        destino, destino_painel = tmp_path / "saida", tmp_path / "painel"
        with pytest.raises(ex.PublicacaoInsegura, match="motivo 11"):
            ex.executar_estrutural(tmp_path, manifesto, destino=destino, destino_painel=destino_painel)
        assert not destino.exists() and not destino_painel.exists()

    def test_medicao_confere_o_pre_registro_antes_de_ler_o_painel(self, monkeypatch, tmp_path):
        def nao_pode(*a, **k):
            raise AssertionError("leu o painel antes de conferir o congelamento")
        monkeypatch.setattr(ex, "carregar_entradas", nao_pode)
        rascunho = tmp_path / "pre_registro_RASCUNHO.md"
        rascunho.write_text("# x\n", encoding="utf-8")
        manifesto = tmp_path / "m.csv"
        manifesto.write_text("x", encoding="utf-8")
        (tmp_path / "evidencias.jsonl").write_text("", encoding="utf-8")
        # 27/09: o registro da conferência também é pin (§13); a pasta da rota o tem.
        (tmp_path / "conferencia.json").write_text("{}", encoding="utf-8")
        with pytest.raises(ex.NaoCongelado):
            ex.executar_medicao(rascunho, ex.sha256(rascunho), tmp_path, manifesto,
                                destino=tmp_path / "saida")


class TestInventarioPublicavel:
    """Emenda C8 (27/09): o estado do painel é dado, não chave de resultado."""

    @staticmethod
    def _inventario():
        inv = {chave: {e: {"linhas": 10 + i, "companhias": 1 + i} for i, e in enumerate(voc)}
               for chave, voc in ex.ESTADOS_DO_INVENTARIO.items()}
        inv["escala_por_base"] = {b: 0 for b in pp.BASES_DE_ESCALA}
        inv["f6_periodos_so_como_penultimo"] = 3
        return inv

    def test_vocabulario_inteiro_passa_na_guarda_sem_perder_contagem(self):
        cru = self._inventario()
        with pytest.raises(AssertionError, match="O1"):
            ex.verificar_publicavel(cru)
        pub = ex.inventario_publicavel(cru)
        ex.verificar_publicavel(pub)
        for chave, voc in ex.ESTADOS_DO_INVENTARIO.items():
            assert [x["estado"] for x in pub[chave]] == list(voc)
            assert {x["estado"]: (x["linhas"], x["companhias"]) for x in pub[chave]} == \
                {e: (v["linhas"], v["companhias"]) for e, v in cru[chave].items()}
        assert pub["escala_por_base"] == cru["escala_por_base"]
        assert pub["f6_periodos_so_como_penultimo"] == 3

    def test_estado_fora_do_vocabulario_derruba(self):
        cru = self._inventario()
        cru["fco_trimestral_por_estado"]["estado_novo"] = {"linhas": 1, "companhias": 1}
        with pytest.raises(ex.PublicacaoInsegura, match="estado_novo"):
            ex.inventario_publicavel(cru)

    def test_estado_ausente_nao_vira_zero(self):
        cru = self._inventario()
        del cru["ativo_por_estado"]["valor_nulo"]
        pub = ex.inventario_publicavel(cru)
        assert "valor_nulo" not in {x["estado"] for x in pub["ativo_por_estado"]}

    def test_o_trimestral_herda_os_estados_nao_ok_do_acumulado(self):
        """O trimestre copia o estado do acumulado quando ele não é `ok` (F5):
        o vocabulário do acumulado, menos `ok`, tem de estar no do trimestral."""
        acumulado = set(ex.ESTADOS_DO_INVENTARIO["fco_acumulado_por_estado"]) - {"ok"}
        assert acumulado <= set(pp.ESTADOS_FCO)

    def test_a_guarda_continua_recusando_lacuna_como_chave(self):
        with pytest.raises(AssertionError, match="O1"):
            ex.verificar_publicavel({"t2": {"x": 1}})
        with pytest.raises(AssertionError, match="O1"):
            ex.verificar_publicavel({"resultado": {"lacuna": 0.03}})


class TestErrosDemonstrados:
    """Emenda AF3 (28/09): erro demonstrado pendente usado na amostra reprova G0.5."""

    @staticmethod
    def _base():
        b = empresa(empresa(Base(), "A", escala=_u_no((2018, 2))), "B")
        p, _ = painel(b)
        return p

    @staticmethod
    def _estrutura(p, erros, monkeypatch, correcoes=None):
        monkeypatch.setattr(ex, "ERROS_DEMONSTRADOS", tuple(erros))
        return ex.estrutura(p.ativo, p.fco_trimestral, _nulos(p), NENHUM, SEM_PROVAS,
                            correcoes or {})

    @staticmethod
    def _ativo_usado(p, e):
        doc = tuple(e["amostra"][0]["linhagem"]["ativo"]["doc"])
        return next(a for a in p.ativo if ex._doc(a["cd_cvm"], a) == doc)

    def _erro(self, linha, conta="1"):
        return {"id_doc": linha["id_doc"], "cd_cvm": linha["cd_cvm"], "conta": conta,
                "dt_refer": str(linha["dt_refer"]), "fonte": "sintético"}

    def test_sem_erro_aprova(self, monkeypatch):
        e = self._estrutura(self._base(), [], monkeypatch)
        assert e["g0_5"]["aprovado"] and e["g0_5"]["violacoes"]["erro_demonstrado_pendente"] == 0

    def test_ativo_com_erro_pendente_usado_em_D_reprova(self, monkeypatch):
        p = self._base()
        usado = self._ativo_usado(p, self._estrutura(p, [], monkeypatch))
        e = self._estrutura(p, [self._erro(usado)], monkeypatch)
        erro = e["g0"]["erros_demonstrados"][0]
        assert erro["estado"] == "pendente" and erro["observacoes_que_usam"] >= 1
        assert e["g0_5"]["violacoes"]["erro_demonstrado_pendente"] == erro["observacoes_que_usam"]
        assert not e["g0_5"]["aprovado"]

    def test_erro_corrigido_pelo_manifesto_nao_reprova(self, monkeypatch):
        p = self._base()
        usado = self._ativo_usado(p, self._estrutura(p, [], monkeypatch))
        corrigido = {("X",): {"1": {"id_doc": usado["id_doc"]}}}
        e = self._estrutura(p, [self._erro(usado)], monkeypatch, correcoes=corrigido)
        erro = e["g0"]["erros_demonstrados"][0]
        assert erro["estado"] == "corrigido_pelo_manifesto_por_conta"
        assert erro["observacoes_que_usam"] >= 1
        assert e["g0_5"]["aprovado"]

    def test_erro_pendente_em_documento_nao_usado_conta_zero(self, monkeypatch):
        p = self._base()
        base = self._estrutura(p, [], monkeypatch)
        usados = {tuple(o["linhagem"]["ativo"]["doc"]) for o in base["amostra"]}
        fora = next(a for a in p.ativo if ex._doc(a["cd_cvm"], a) not in usados)
        e = self._estrutura(p, [self._erro(fora)], monkeypatch)
        assert e["g0"]["erros_demonstrados"][0]["observacoes_que_usam"] == 0
        assert e["g0_5"]["aprovado"]

    def test_fco_com_erro_pendente_na_janela_reprova(self, monkeypatch):
        p = self._base()
        base = self._estrutura(p, [], monkeypatch)
        doc = tuple(base["amostra"][0]["linhagem"]["janela"][-1]["docs"][-1][:4])
        t = next(t for t in p.fco_trimestral for o in json.loads(t["operandos"])
                 if ex._doc(t["cd_cvm"], o) == doc)
        id_doc = next(o["id_doc"] for o in json.loads(t["operandos"]) if ex._doc(t["cd_cvm"], o) == doc)
        erro = {"id_doc": id_doc, "cd_cvm": t["cd_cvm"], "conta": "6.01", "dt_refer": doc[2],
                "fonte": "sintético"}
        e = self._estrutura(p, [erro], monkeypatch)
        assert e["g0"]["erros_demonstrados"][0]["observacoes_que_usam"] >= 1
        assert not e["g0_5"]["aprovado"]

    def test_conta_sem_regra_de_uso_derruba(self, monkeypatch):
        p = self._base()
        erro = {"id_doc": "1", "cd_cvm": "A", "conta": "1.01.01", "dt_refer": "2018-06-30",
                "fonte": "sintético"}
        with pytest.raises(pp.DefeitoDeFonte, match="sem regra de uso"):
            self._estrutura(p, [erro], monkeypatch)


class TestUsoDosErrosDemonstrados:
    """Ressalva 2 da verificação de 28/09: dois ramos da AF3 sem contraprova —
    `id_doc` composto e FCO usado só no rótulo. Entradas mínimas, montadas à mão."""

    DOC = ("A", "itr", "2020-06-30", 1)
    OUTRO = ("A", "itr", "2020-09-30", 1)

    @staticmethod
    def _obs(ativo, janela=(), rotulo=()):
        def proc(d):
            return {"docs": [list(d) + ["MIL"]]}
        return {"fco_ttm_sobre_ativo": None,
                "linhagem": {"ativo": {"doc": list(ativo)},
                             "janela": [proc(d) for d in janela],
                             "rotulo": [proc(d) for d in rotulo]}}

    @staticmethod
    def _ativo(doc, id_doc):
        cd, cj, dt, v = doc
        return {"cd_cvm": cd, "conjunto": cj, "dt_refer": dt, "versao": v, "id_doc": id_doc}

    @staticmethod
    def _tri(doc, id_doc):
        cd, cj, dt, v = doc
        return {"cd_cvm": cd, "operandos": json.dumps([
            {"conjunto": cj, "dt_refer": dt, "versao": v, "id_doc": id_doc}])}

    @staticmethod
    def _erro(id_doc, conta):
        return {"id_doc": id_doc, "cd_cvm": "A", "conta": conta, "dt_refer": "2020-06-30",
                "fonte": "sintético", "estado": "pendente"}

    def test_id_doc_composto_do_ativo_conta_por_pertinencia(self):
        ativos = [self._ativo(self.DOC, "140867,140999")]
        amostra = [self._obs(self.DOC)]
        usos = ex.uso_dos_erros_demonstrados(
            [self._erro("140999", "1"), self._erro("14099", "1")], amostra, ativos, [])
        assert [u["observacoes_que_usam"] for u in usos] == [1, 0]

    def test_id_doc_composto_do_fco_conta_por_pertinencia(self):
        amostra = [self._obs(self.OUTRO, janela=[self.DOC])]
        usos = ex.uso_dos_erros_demonstrados(
            [self._erro("140999", "6.01"), self._erro("14099", "6.01")], amostra,
            [self._ativo(self.OUTRO, "1")], [self._tri(self.DOC, "140867,140999")])
        assert [u["observacoes_que_usam"] for u in usos] == [1, 0]

    def test_fco_usado_so_no_rotulo_conta_e_reprova(self):
        amostra = [self._obs(self.OUTRO, rotulo=[self.DOC])]
        usos = ex.uso_dos_erros_demonstrados(
            [self._erro("140867", "6.01")], amostra,
            [self._ativo(self.OUTRO, "1")], [self._tri(self.DOC, "140867")])
        assert usos[0]["observacoes_que_usam"] == 1
        g = ex.gate_g0_5(amostra, NENHUM, usos)
        assert g["violacoes"] == {"regra_1": 0, "regra_2": 0, "regra_3": 0,
                                  "erro_demonstrado_pendente": 1}
        assert g["aprovado"] is False
        # A mesma amostra, sem uso do erro, aprova: a decisão vem só da AF3.
        assert ex.gate_g0_5(amostra, NENHUM, [{**usos[0], "observacoes_que_usam": 0}])["aprovado"]
