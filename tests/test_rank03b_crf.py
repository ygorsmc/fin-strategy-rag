"""Contraprovas de fechamento CRF-01/02/03, exclusivamente sintéticas."""
import json
from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from scripts import adjudicar_escala_rank03b as adj
from scripts import fonte_rad_cvm as rad
from scripts import gates_painel_pesquisa_rank03b as gates
from scripts import painel_pesquisa_rank03b as pp
from scripts import auditar_rank03b_consumo_operacional as auditor
from tests.fixtures_rank03b_crf import formulario_v4
from tests.test_gates_painel_pesquisa_rank03b import TestProvaDeEscalaNoTempo as _ProvaFixture


def adjudicar(f):
    return adj.adjudicar_formulario(f, "UNIDADE", "2025-09-30")


class TestEscopoTabularV4:
    def test_regra_vigente_e_controle_positivo(self):
        assert adj.REGRA_VIGENTE == "v4"
        r = adjudicar(formulario_v4())
        assert r["veredito"] == "corrigida"
        c = r["numerica"]["casamentos"][0]
        assert (c["conta"], c["coluna"], c["dt_fim"]) == ("1", 1, "2025-09-30")
        assert c["regra"] == "v4" and "1.234.567" not in c["trecho"]

    def test_reais_continuam_reais(self):
        r = adjudicar(formulario_v4(["Ativo total 1.234.567 900.000"],
            [("1", None, date(2025, 9, 30), 1234567000)]))
        assert (r["veredito"], r["escala_do_formulario"]) == ("confirmada", "UNIDADE")

    @pytest.mark.parametrize("linha", [
        "Caixa e equivalentes de caixa 900       Fornecedores 900.000",
        "Caixa e equivalentes de caixa 900 Fornecedores 900.000 800",
        "Ajuste de variação cambial 900.000 700",
        "Total do ativo não-circulante 900.000 700",
        "Total do ativo nao circulante 900.000 700",
        "Total do ativo por acoes 900.000 700",
        "Ativo total 900.000", "Ativo total 900.000 700 600",
    ])
    def test_outra_conta_subtotal_ou_celula_perdida_nao_decide(self, linha):
        f = formulario_v4([linha], [
            ("1", None, date(2025, 9, 30), 900000),
            ("1.01.01", None, date(2025, 9, 30), 900000),
            ("6.04", date(2025, 1, 1), date(2025, 9, 30), 900000)])
        assert adjudicar(f)["veredito"] == "indecidivel"

    def test_mesma_linha_contraprova_v3_e_controle_separado(self):
        valores = [("1.01.01", None, date(2025, 9, 30), 900000)]
        f = formulario_v4(["Caixa e equivalentes de caixa 900 Fornecedores 900.000"], valores)
        assert adj.adjudicar_formulario(f, "UNIDADE", "2025-09-30", regra="v3")["veredito"] == "corrigida"
        assert adjudicar(f)["veredito"] == "indecidivel"
        f = formulario_v4(["Caixa e equivalentes de caixa 900 800", "Fornecedores 900.000 700"], valores)
        assert adjudicar(f)["veredito"] == "indecidivel"

    @pytest.mark.parametrize("antes,depois", [
        ("Consolidado", "Controladora"),
        ("Consolidado", "Controladora Consolidado"),
        ("Consolidado", "Investimento em subsidiária"),
        ("(Em milhares de reais)", "(Em reais)"),
        ("(Em milhares de reais)", "(Em milhões de reais)"),
        ("(Em milhares de reais)", ""),
        ("30/09/2025 31/12/2024", "2025 2024"),
        ("30/09/2025 31/12/2024", "31/12/2024 31/12/2023"),
        ("30/09/2025 31/12/2024", "30/09/2025 30/09/2025"),
        ("30/09/2025 31/12/2024", "30/09/2025 31/02/2024"),
        ("30/09/2025 31/12/2024", "Outra tabela\n30/09/2025 31/12/2024"),
        ("Ativo total", "Ações"),
    ])
    def test_cabecalho_nao_identifica_coluna(self, antes, depois):
        f = formulario_v4()
        f.anexos[0][1][0] = f.anexos[0][1][0].replace(antes, depois)
        assert adjudicar(f)["veredito"] == "indecidivel"

    def test_coluna_comparativa_nao_decide(self):
        assert adjudicar(formulario_v4(["Ativo total 800 1.234.567"]))["veredito"] == "indecidivel"

    def test_coluna_invertida_e_varias_linhas(self):
        f = formulario_v4(["Fornecedores 400 500", "Ativo total 900.000 1.234.567"])
        f.anexos[0][1][0] = f.anexos[0][1][0].replace("30/09/2025 31/12/2024", "31/12/2024 30/09/2025")
        r = adjudicar(f)
        assert r["veredito"] == "corrigida"
        assert r["numerica"]["casamentos"][0]["coluna"] == 2

    @pytest.mark.parametrize("interrupcao", ["", "10 Investimento", "Em reais", "Controladora"])
    def test_contexto_nao_atravessa_outra_tabela(self, interrupcao):
        assert adjudicar(formulario_v4([interrupcao, "Ativo total 1.234.567 900.000"]))["veredito"] == "indecidivel"

    def test_fluxo_sem_intervalo_nao_decide(self):
        f = formulario_v4(["Caixa líquido das atividades operacionais 1.234.567 900.000"],
                         [("6.01", date(2025, 1, 1), date(2025, 9, 30), 1234567)])
        assert adjudicar(f)["veredito"] == "indecidivel"

    def test_ambiguidade_da_mesma_conta_permanece_recusada(self):
        f = formulario_v4(individuais=[("1", None, date(2025, 9, 30), 1234.567)])
        assert adjudicar(f)["veredito"] == "indecidivel"

    def test_valores_distintos_para_mesmo_saldo_nao_sao_escolhidos(self):
        f = formulario_v4(valores=[("1", None, date(2025, 9, 30), 1234567),
                                  ("1", None, date(2025, 9, 30), 7654321)])
        assert adjudicar(f)["veredito"] == "indecidivel"

    def test_mascarar_todos_os_numeros_do_casamento(self):
        r = adjudicar(formulario_v4())
        assert not any(c.isdigit() for c in r["numerica"]["casamentos"][0]["trecho"])

    def test_sinais_opostos_sao_dois_valores_antes_do_modulo(self):
        f = formulario_v4(valores=[("1", None, date(2025, 9, 30), 1234567),
                                  ("1", None, date(2025, 9, 30), -1234567)])
        assert adjudicar(f)["veredito"] == "indecidivel"

    @pytest.mark.parametrize("traco", ["-", "–", "—"])
    def test_consumidor_recusa_traco_corrente_mas_aceita_comparativo(self, traco):
        from tests.fixtures_rank03b_crf import prova_v4
        p = prova_v4()
        p["trecho"] = "ativo total " + traco
        with pytest.raises(AssertionError, match="vazia"):
            rad.validar_escopo_numerico_v4(p, p["dt_fim"])
        p["datas_colunas"] += " 2024-12-31"
        p["trecho"] = "ativo total [valor omitido] " + traco
        rad.validar_escopo_numerico_v4(p, p["dt_fim"])

    @pytest.mark.parametrize("campo,valor", [
        ("regra", "v3"), ("perimetro", "individual"), ("unidade", "UNIDADE"),
        ("dt_fim", "2024-12-31"), ("coluna", 2), ("linha", 0),
        ("cabecalho_local", ["consolidado", "em reais"]),
        ("datas_colunas", "2025"), ("trecho", "fornecedores [valor omitido]"),
        ("trecho", "ativo total 1.234"), ("trecho", "ativo total [valor omitido] [valor omitido]"),
    ])
    def test_consumidor_recusa_prova_fora_do_escopo(self, campo, valor, tmp_path):
        from tests.test_gates_painel_pesquisa_rank03b import TestManifestoDeCorrecoes
        t = TestManifestoDeCorrecoes()
        linha = t._linha()
        prova = json.loads(linha["evidencia_numerica"])[0]
        prova[campo] = valor
        linha["evidencia_numerica"] = json.dumps([prova])
        caminho = tmp_path / "correcoes.csv"
        t._gravar(caminho, [linha])
        with pytest.raises(AssertionError):
            gates.carregar_correcoes(caminho, aquisicao=t._aquisicao(tmp_path))


def painel_com_duas_provas():
    con, correcoes = _ProvaFixture()._montar("2019-01-15")
    chave = ("A", "itr", "2017-03-31", 1)
    con.execute("UPDATE declaracoes SET escala = 'UNIDADE' WHERE dt_refer = '2017-03-31'")
    brutos = con.execute("SELECT cd_conta, ordem, dt_ini, dt_fim, vl FROM declaracoes WHERE dt_refer = '2017-03-31'").fetchall()
    id_doc = con.execute("SELECT id_doc FROM cadastro WHERE dt_refer = '2017-03-31'").fetchone()[0]
    correcoes[chave] = {"escala_declarada": "UNIDADE", "escala_aplicada": "MIL",
        "base": "corrigida_documento", "id_correcao": "H2", "id_doc": id_doc,
        "impressao_digital": pp.impressao_digital(brutos)}
    return con, correcoes, chave


class TestCoberturaIntegralDeProvas:
    @pytest.mark.parametrize("entrada", ["medir", "falsificar", "g1", "g1_4"])
    @pytest.mark.parametrize("defeito", ["parcial", "vazio", "nulo", "nat", "string"])
    def test_recusa_antes_de_aprovar(self, entrada, defeito, monkeypatch):
        con, cor, chave = painel_com_duas_provas()
        try:
            painel = pp.construir(con, cor)
            provas = gates.datas_das_provas(con, cor)
            chave_futura = _ProvaFixture.CORRIGIDO
            if defeito == "parcial":
                provas.pop(chave_futura)
            elif defeito == "vazio":
                provas = {}
            else:
                provas[chave_futura] = {"nulo": None, "nat": pd.NaT, "string": "data inválida"}[defeito]
            monkeypatch.setattr(auditor, "_somas_do_rotulo", lambda *a: pytest.fail("y proibido"))
            chamadas = {
                "medir": lambda: gates.medir(painel, provas=provas),
                "falsificar": lambda: gates.verificar_falsificacoes(painel, con, provas),
                "g1": lambda: gates.g1_cego(gates.linhas_fco(painel), gates.linhas_ativo(painel), painel, provas),
                "g1_4": lambda: gates.g1_provas_depois_de_d([], painel, provas),
            }
            with pytest.raises(gates.ProvasAusentes):
                chamadas[entrada]()
        finally:
            con.close()

    def test_completo_aceita_bom_e_detecta_sabotagem(self):
        con, cor, _ = painel_com_duas_provas()
        try:
            provas = gates.datas_das_provas(con, cor)
            bom = pp.construir(con, cor)
            assert gates.medir(bom, provas=provas)["cadeia"][1]["aprovado"]
            with patch.object(pp.Documento, "disponivel_em", property(lambda d: d.dt_receb)), \
                 patch.object(pp.Documento, "disponivel_em_v1", property(lambda d: d.dt_receb_v1)):
                ruim = pp.construir(con, cor)
            g1 = gates.medir(ruim, provas=provas)["cadeia"][1]
            assert not g1["aprovado"]
            assert g1["g1_4_prova_de_escala_publicada_depois_de_D"] == 2
            with pytest.raises(gates.PainelViolaContrato, match="c3"):
                gates.verificar_falsificacoes(ruim, con, provas)
        finally:
            con.close()

    def test_g1_sem_painel_nao_certifica(self):
        with pytest.raises(gates.ProvasAusentes, match="painel"):
            gates.g1_cego([], [])

    def test_cadastro_com_recepcao_nula_nao_gera_prova(self):
        con, cor, _ = painel_com_duas_provas()
        try:
            con.execute("UPDATE cadastro SET dt_receb=NULL WHERE id_doc='ponta_fim'")
            with pytest.raises(gates.ProvasAusentes):
                gates.datas_das_provas(con, cor)
        finally:
            con.close()
