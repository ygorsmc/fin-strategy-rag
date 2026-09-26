"""Contraprovas do executor de G0/G1 sobre o painel de pesquisa (G1-pp a G7-pp)."""

from __future__ import annotations

import csv
import inspect
import json
import re
from datetime import date, timedelta

import pytest

from scripts import auditar_rank03b_consumo_operacional as auditor
from scripts import gates_painel_pesquisa_rank03b as gates
from scripts import painel_pesquisa_rank03b as pp
from tests.test_painel_pesquisa_rank03b import Base
from tests.fixtures_rank03b_crf import prova_v4


def _colunas_do_select(funcao) -> set[str]:
    """Nomes que o SELECT de um carregador do auditor devolve."""
    sql = inspect.getsource(funcao)
    corpo = sql.split("SELECT", 2)[-1].split("FROM fatos_contabeis")[0]
    nomes = set()
    for parte in corpo.split(","):
        parte = parte.strip()
        m = re.search(r"AS\s+(\w+)\s*$", parte)
        nomes.add(m.group(1) if m else parte.split(".")[-1].strip())
    return nomes


def _serie(b, cd, anos, escala="MIL"):
    """Anos civis completos com recepção 40 dias após cada fim."""
    for ano in anos:
        for i, fim in enumerate([date(ano, 3, 31), date(ano, 6, 30), date(ano, 9, 30),
                                 date(ano, 12, 31)]):
            b.doc(cd, "dfp" if i == 3 else "itr", str(fim), str(fim + timedelta(days=40)),
                  fco=[(f"{ano}-01-01", str(fim), 100 * (i + 1))], ativo=5000 + i,
                  escala=escala)
    return b


class TestFormas:
    def test_fco_tem_as_chaves_do_carregador_do_auditor(self):
        p = pp.construir(_serie(Base(), "A", [2020]).con())
        assert set(gates.linhas_fco(p)[0]) == _colunas_do_select(auditor.carregar_fco)

    def test_ativo_tem_as_chaves_do_carregador_do_auditor(self):
        p = pp.construir(_serie(Base(), "A", [2020]).con())
        esperado = _colunas_do_select(auditor.carregar_ativo)
        assert set(gates.linhas_ativo(p)[0]) == esperado | {"dt_fim"}
        assert "dt_fim" in esperado, "H2.1: o carregador do auditor também traz dt_fim"

    def test_so_linhas_validas_entram(self):
        b = _serie(Base(), "A", [2020])
        b.doc("A", "itr", "2021-06-30", "2021-08-10", fco=[("2021-01-01", "2021-06-30", 1)],
              ativo=0.5)
        p = pp.construir(b.con())
        assert len(gates.linhas_fco(p)) == 4
        assert len(gates.linhas_ativo(p)) == 4
        assert len(gates.linhas_ativo(p, incluir_nao_informativo=True)) == 5

    def test_duracao_e_recomputada_das_datas(self):
        """G2-pp: G0.2 verifica a regra do construtor, não confia na coluna."""
        p = pp.construir(_serie(Base(), "A", [2020]).con())
        for t in p.fco_trimestral:
            t["dias"] = 999
        assert {d["dias"] for d in gates.duracoes(p)} <= set(range(80, 101))

    def test_nulos_contam_todos_os_candidatos(self):
        b = _serie(Base(), "A", [2020])
        b.doc("A", "itr", "2021-03-31", "2021-05-10", fco=[("2021-01-01", "2021-03-31", None)])
        b.ativo_nulo("A", "itr", "2021-06-30", "2021-08-10")
        n = gates.nulos(pp.construir(b.con()))
        assert n == {"fco": {"linhas": 5, "nulos": 1}, "ativo": {"linhas": 5, "nulos": 1}}


class TestCadeia:
    def test_painel_limpo_aprova_g0_e_mede_g1(self):
        b = Base()
        for cd in ("A", "B", "C"):
            _serie(b, cd, range(2015, 2021))
        r = gates.medir(pp.construir(b.con()))
        g0, g1 = r["cadeia"]
        assert g0["aprovado"] is True
        assert g1["observacoes"] > 0
        assert g1["aprovado"] is True, {k: v for k, v in g1.items() if k.startswith(("g1_", "r2_5"))}
        assert r["primeiro_reprovado"] is None and r["veredito"] == "G0 E G1 APROVADOS"

    def test_nulo_reprova_g0_pela_medicao_de_todos_os_candidatos(self):
        b = _serie(Base(), "A", range(2015, 2021))
        b.doc("A", "itr", "2021-03-31", "2021-05-10", fco=[("2021-01-01", "2021-03-31", None)])
        g0 = gates.medir(pp.construir(b.con()))["cadeia"][0]
        assert g0["aprovado"] is False and g0["g0_4_nulos_nas_contas_usadas"] == 1

    def test_salto_de_escala_nao_corrigido_reprova_g0(self):
        """G4-pp: o documento suspeito fica com o rótulo declarado e o G0.3 julga."""
        b = _serie(Base(), "A", range(2015, 2021))
        b.doc("A", "itr", "2021-03-31", "2021-05-10", ativo=5000, escala="UNIDADE",
              fco=[("2021-01-01", "2021-03-31", 100)])
        g0 = gates.medir(pp.construir(b.con()))["cadeia"][0]
        assert g0["g0_3_saltos_de_escala"] == 1
        assert g0["aprovado"] is False, "1 salto em 25 posições excede 0,5%"

    def test_trimestre_repetido_reprova_g0(self, monkeypatch):
        p = pp.construir(_serie(Base(), "A", [2020]).con())
        original = gates.linhas_fco
        monkeypatch.setattr(gates, "linhas_fco", lambda painel: original(painel) + original(painel)[:1])
        g0 = gates.medir(p)["cadeia"][0]
        assert g0["g3_pp_trimestres_repetidos"] == 1 and g0["aprovado"] is False

    def test_rotulo_nunca_e_somado_pelo_executor(self, monkeypatch):
        """G6-pp, depois da auditoria (A1): nem calculado, não só apagado."""
        def proibido(*_):
            raise AssertionError("o executor somou o rótulo")
        monkeypatch.setattr(auditor, "_somas_do_rotulo", proibido)
        vistos = []
        original = auditor.gate_g1

        def espiao(amostra, descarte):
            vistos.extend(amostra)
            return original(amostra, descarte)
        monkeypatch.setattr(auditor, "gate_g1", espiao)
        b = Base()
        for cd in ("A", "B"):
            _serie(b, cd, range(2015, 2021))
        r = gates.medir(pp.construir(b.con()))
        assert vistos, "a amostra precisa existir para o teste valer"
        assert all("y" not in o for o in vistos)
        gates._sem_chave_proibida(r)

    def test_contagem_de_ttm_nao_positivo_nao_e_publicada(self):
        """O1.1: agregado de sinal de FCO não sai antes do pré-registro."""
        b = Base()
        for cd in ("A", "B"):
            _serie(b, cd, range(2015, 2021))
        g1 = gates.medir(pp.construir(b.con()))["cadeia"][1]
        assert g1["descartes"]["fco_ttm_nao_positivo"] == "omitido por O1"
        assert all(isinstance(v, int) for k, v in g1["descartes"].items()
                   if k not in gates.DESCARTES_NAO_PUBLICADOS)

    def test_efeito_da_regra_a2_e_publicado_sem_governar(self):
        b = _serie(Base(), "A", range(2015, 2021))
        b.doc("A", "itr", "2021-03-31", "2021-05-10", ativo=1.0,
              fco=[("2021-01-01", "2021-03-31", 100)])
        g0 = gates.medir(pp.construir(b.con()))["cadeia"][0]
        assert g0["diagnostico_a2"] == {"ativos_nao_informativos": 1,
                                        "saltos_de_escala_se_fossem_incluidos": 1}
        assert g0["g0_3_saltos_de_escala"] == 0


class TestManifestoDeCorrecoes:
    def test_ausente_e_erro_nao_vazio(self, tmp_path):
        with pytest.raises(gates.ManifestoDeCorrecoesAusente):
            gates.carregar_correcoes(tmp_path / "nao_existe.csv")

    @staticmethod
    def _gravar(caminho, linhas):
        from scripts import adjudicar_escala_rank03b as adj
        with open(caminho, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=adj.COLUNAS_MANIFESTO)
            w.writeheader()
            w.writerows(linhas)

    @staticmethod
    def _aquisicao(tmp_path, id_doc="10", sha="a" * 64):
        caminho = tmp_path / "aquisicao.jsonl"
        caminho.write_text(json.dumps({"id_doc": id_doc, "estado": "integro", "sha256": sha}) + "\n")
        return caminho

    @staticmethod
    def _linha(**mudar):
        base = {"id_correcao": "ESC-0001", "cd_cvm": "A", "conjunto": "itr",
                "dt_refer": "2020-03-31", "versao": "1", "id_doc": "10",
                "sha256_pacote": "a" * 64, "escala_declarada": "UNIDADE",
                "escala_aplicada": "MIL", "base": "corrigida_documento",
                "impressao_digital": "h", "cabecalho_classe": "MIL", "cabecalho_contagem": "{}",
                "numerica_classe": "bruto", "numerica_contagem": "{}", "trecho": "1",
                "evidencia_anexo": "0", "evidencia_pagina": "2",
                "evidencia_trecho": "x" * 60, "pontas": "",
                "evidencia_numerica": json.dumps([{"conta": "1", "forma": "bruto", "anexo": 0,
                                                   "pagina": 2, "trecho": "total do ativo 1"}])}
        # CRF-01: fixture positiva carrega a coluna e o contexto da prova v4.
        base["evidencia_numerica"] = json.dumps([prova_v4(base["dt_refer"])])
        base.update(mudar)
        return base

    def test_duplicada_e_erro(self, tmp_path):
        caminho = tmp_path / "c.csv"
        self._gravar(caminho, [self._linha(), self._linha()])
        with pytest.raises(ValueError, match="duplicada"):
            gates.carregar_correcoes(caminho, aquisicao=self._aquisicao(tmp_path))

    def test_linha_valida_e_carregada(self, tmp_path):
        caminho = tmp_path / "c.csv"
        self._gravar(caminho, [self._linha()])
        c = gates.carregar_correcoes(caminho, aquisicao=self._aquisicao(tmp_path))
        assert list(c) == [("A", "itr", "2020-03-31", 1)]
        assert isinstance(c, gates.CorrecoesValidadas)
        assert c.origem_sha256 == gates._sha256(caminho)

    def test_correcao_sem_evidencia_numerica_localizada_e_recusada(self, tmp_path):
        """E3 (17/09), no consumidor."""
        caminho = tmp_path / "c.csv"
        self._gravar(caminho, [self._linha(evidencia_numerica="")])
        with pytest.raises(AssertionError, match="localizada"):
            gates.carregar_correcoes(caminho, aquisicao=self._aquisicao(tmp_path))

    def test_executor_recusa_correcoes_montadas_a_mao(self):
        """V1 (17/09): antes, só a CLI validava."""
        with pytest.raises(gates.CorrecoesNaoValidadas):
            gates.executar({("A", "itr", "2020-03-31", 1): self._linha()}, None)

    def test_executor_recusa_manifesto_alterado_depois_de_validado(self, tmp_path):
        caminho = tmp_path / "c.csv"
        self._gravar(caminho, [self._linha()])
        c = gates.carregar_correcoes(caminho, aquisicao=self._aquisicao(tmp_path))
        caminho.write_text(caminho.read_text() + "\n")
        with pytest.raises(gates.CorrecoesNaoValidadas, match="mudou"):
            gates.executar(c, caminho)

    def test_sonda_do_auditor_milhao_sem_evidencia_e_recusada(self, tmp_path):
        """M1: com a impressão digital certa, uma escala sem evidência era aplicada."""
        caminho = tmp_path / "c.csv"
        self._gravar(caminho, [self._linha(base="qualquer_coisa", escala_aplicada="MILHAO",
                                           cabecalho_classe="", numerica_classe="",
                                           evidencia_trecho="")])
        with pytest.raises(AssertionError):
            gates.carregar_correcoes(caminho, aquisicao=self._aquisicao(tmp_path))

    def test_pacote_desconhecido_e_recusado(self, tmp_path):
        caminho = tmp_path / "c.csv"
        self._gravar(caminho, [self._linha()])
        with pytest.raises(AssertionError, match="não consta"):
            gates.carregar_correcoes(caminho, aquisicao=self._aquisicao(tmp_path, sha="b" * 64))

    def test_cli_exige_escolha_explicita(self):
        with pytest.raises(SystemExit):
            gates.principal([])
        with pytest.raises(SystemExit):
            gates.principal(["--sem-correcoes", "--correcoes", "x.csv"])
        with pytest.raises(SystemExit):
            gates.principal(["--diagnostico-execucao-1", "--sem-correcoes"])


class TestDiagnosticoG05:
    def _painel(self):
        b = _serie(Base(), "A", [2020])
        # 2T2021 derivado de 1T (UNIDADE) e 1S (MIL): escalas declaradas diferentes.
        b.doc("A", "itr", "2021-03-31", "2021-05-10", fco=[("2021-01-01", "2021-03-31", 1)],
              escala="UNIDADE")
        b.doc("A", "itr", "2021-06-30", "2021-08-10", fco=[("2021-01-01", "2021-06-30", 2)])
        return pp.construir(b.con())

    def test_operando_sem_veredito_conta(self):
        d = gates.diagnostico_g0_5(self._painel(), decididos=set())
        # G5.1 (17/09): o nome da contagem mudou com a população.
        assert d["com_escalas_heterogeneas"] == 1
        assert d["por_configuracao"]["declaradas_diferentes|aplicadas_diferentes"] == {
            "trimestres": 1, "sem_veredito": 1}
        assert d["sem_veredito_em_algum_operando"] == 1
        assert d["governa_este_lote"] is False
        assert "DECIDIR" in d["limiar"]

    def _painel_com_correcao_parcial(self):
        """Declaradas iguais (UNIDADE+UNIDADE), um operando corrigido para MIL."""
        b = _serie(Base(), "A", [2020])
        b.doc("A", "itr", "2021-03-31", "2021-05-10", fco=[("2021-01-01", "2021-03-31", 1)],
              escala="UNIDADE")
        b.doc("A", "itr", "2021-06-30", "2021-08-10", fco=[("2021-01-01", "2021-06-30", 2)],
              escala="UNIDADE")
        con = b.con()
        chave = ("A", "itr", "2021-06-30", 1)
        brutos = con.execute(
            "SELECT cd_conta, ordem, dt_ini, dt_fim, vl FROM declaracoes "
            "WHERE cd_cvm = 'A' AND dt_refer = '2021-06-30'").fetchall()
        id_doc = con.execute("SELECT id_doc FROM cadastro WHERE dt_refer = '2021-06-30'").fetchone()[0]
        correcoes = {chave: {"escala_declarada": "UNIDADE", "escala_aplicada": "MIL",
                             "base": "corrigida_documento", "id_correcao": "C1",
                             "id_doc": id_doc, "impressao_digital": pp.impressao_digital(brutos)}}
        return pp.construir(con, correcoes), chave

    def test_correcao_parcial_entra_na_populacao(self):
        """RF-04: 003549, 025461 e 027570 ficavam fora — declaradas iguais."""
        painel, corrigido = self._painel_com_correcao_parcial()
        d = gates.diagnostico_g0_5(painel, decididos={corrigido})
        assert d["por_configuracao"]["declaradas_iguais|aplicadas_diferentes"] == {
            "trimestres": 1, "sem_veredito": 1}
        tudo = {corrigido, ("A", "itr", "2021-03-31", 1)}
        assert gates.diagnostico_g0_5(painel, decididos=tudo)["sem_veredito_em_algum_operando"] == 0

    def test_homogeneo_nao_conta_mesmo_sem_veredito(self):
        d = gates.diagnostico_g0_5(pp.construir(_serie(Base(), "A", [2020]).con()), set())
        assert d["sem_veredito_em_algum_operando"] == 0
        assert list(d["por_configuracao"]) == ["declaradas_iguais|aplicadas_iguais"]

    def test_operandos_decididos_nao_contam(self):
        decididos = {("A", "itr", "2021-03-31", 1), ("A", "itr", "2021-06-30", 1)}
        d = gates.diagnostico_g0_5(self._painel(), decididos)
        assert d["sem_veredito_em_algum_operando"] == 0

    def test_nao_entra_na_cadeia(self):
        r = gates.medir(self._painel(), decididos=set())
        g0 = r["cadeia"][0]
        assert "diagnostico_g0_5_proposto" in g0
        # a aprovação de G0 não depende do diagnóstico
        sem = gates.medir(self._painel())
        assert sem["cadeia"][0]["aprovado"] == g0["aprovado"]

    def test_decididos_exige_a_adjudicacao(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            gates.documentos_decididos(tmp_path)

    def test_indecidivel_nao_e_decidido(self, tmp_path):
        import json as _json
        (tmp_path / "evidencias.jsonl").write_text(
            _json.dumps({"cd_cvm": "A", "conjunto": "itr", "dt_refer": "2021-03-31",
                         "versao": 1, "veredito": "indecidivel"}) + "\n"
            + _json.dumps({"cd_cvm": "A", "conjunto": "itr", "dt_refer": "2021-06-30",
                           "versao": 1, "veredito": "confirmada"}) + "\n")
        (tmp_path / "herdados.jsonl").write_text("")
        assert gates.documentos_decididos(tmp_path) == {("A", "itr", "2021-06-30", 1)}


class TestFalsificacoesSobreOPainel:
    def _painel(self):
        b = Base()
        for cd in ("A", "B"):
            _serie(b, cd, range(2019, 2021))
        con = b.con()
        return pp.construir(con), con

    def test_painel_correto_nao_viola(self):
        painel, con = self._painel()
        assert set(gates.verificar_falsificacoes(painel, con).values()) == {0}

    def test_disponibilidade_adiantada_derruba(self):
        """Condição 3: usar o número antes do operando mais tardio é vazamento."""
        painel, con = self._painel()
        derivado = next(t for t in painel.fco_trimestral if t["origem"] == "derivado")
        derivado["disponivel_em"] = derivado["disponivel_em_v1"].replace(year=2000)
        with pytest.raises(gates.PainelViolaContrato, match="c3"):
            gates.verificar_falsificacoes(painel, con)

    def test_valido_fora_da_banda_derruba(self):
        painel, con = self._painel()
        t = next(t for t in painel.fco_trimestral if t["estado"] == "valido")
        t["dt_ini"] = t["dt_ini"].replace(day=1, month=1) if t["dt_ini"].month > 6 else t["dt_ini"]
        t["dt_fim"] = t["dt_fim"].replace(year=t["dt_fim"].year + 1)
        with pytest.raises(gates.PainelViolaContrato, match="c1"):
            gates.verificar_falsificacoes(painel, con)

    def test_candidato_sumido_derruba(self):
        painel, con = self._painel()
        painel.fco_trimestral.pop()
        with pytest.raises(gates.PainelViolaContrato, match="c5"):
            gates.verificar_falsificacoes(painel, con)

    def test_linha_de_ativo_excluida_derruba(self):
        """M4: excluir uma LINHA, não só um documento, também é falsificação."""
        painel, con = self._painel()
        painel.ativo.pop()
        with pytest.raises(gates.PainelViolaContrato, match="c8_linha_de_ativo"):
            gates.verificar_falsificacoes(painel, con)

    def test_declaracao_de_fco_sumida_derruba(self):
        painel, con = self._painel()
        painel.fco_acumulado[0]["declaracoes"] = 0
        with pytest.raises(gates.PainelViolaContrato, match="c8_linha_de_fco"):
            gates.verificar_falsificacoes(painel, con)

    def test_documento_excluido_derruba(self):
        """Condição 8: documento de escala suspeita não pode sair do painel."""
        painel, con = self._painel()
        painel.documentos.pop(next(iter(painel.documentos)))
        with pytest.raises(gates.PainelViolaContrato, match="c8"):
            gates.verificar_falsificacoes(painel, con)

    def test_subtracao_entre_exercicios_derruba(self):
        painel, con = self._painel()
        t = next(t for t in painel.fco_trimestral if t["origem"] == "derivado")
        operandos = json.loads(t["operandos"])
        operandos[0]["dt_ini"] = "2018-01-01"
        t["operandos"] = json.dumps(operandos)
        with pytest.raises(gates.PainelViolaContrato, match="c4"):
            gates.verificar_falsificacoes(painel, con)


class TestProvaDeEscalaNoTempo:
    """P6/P7 (17/09): a correção herdada só existe quando a última ponta existe.

    Os valores e as datas dos documentos da companhia são sempre os mesmos;
    só muda a recepção da ponta que prova a escala.
    """

    CORRIGIDO = ("A", "itr", "2018-06-30", 1)

    def _montar(self, receb_ponta):
        b = _serie(Base(), "A", range(2015, 2021))
        for i, linha in enumerate(b.decl):
            if linha[3] == "2018-06-30":
                b.decl[i] = linha[:9] + ("UNIDADE",) + linha[10:]
        b.cad.append(("itr", "Z", "2014-12-31", 1, "ponta_ini", "2015-02-01"))
        b.cad.append(("itr", "Z", "2022-12-31", 1, "ponta_fim", receb_ponta))
        con = b.con()
        brutos = con.execute(
            "SELECT cd_conta, ordem, dt_ini, dt_fim, vl FROM declaracoes "
            "WHERE dt_refer = '2018-06-30'").fetchall()
        id_doc = con.execute(
            "SELECT id_doc FROM cadastro WHERE dt_refer = '2018-06-30'").fetchone()[0]
        correcoes = {self.CORRIGIDO: {
            "escala_declarada": "UNIDADE", "escala_aplicada": "MIL", "base": "herdada_trecho",
            "id_correcao": "H1", "id_doc": id_doc,
            "impressao_digital": pp.impressao_digital(brutos),
            "pontas": json.dumps([{"id_doc": "ponta_ini"}, {"id_doc": "ponta_fim"}])}}
        return con, correcoes

    #: Trimestres cujo valor vem do documento corrigido: o 2T2018 (o próprio
    #: acumulado) e o 3T2018 (que o subtrai como antecedente), e o ativo de 30/06.
    DEPENDENTES = {"2018-06-30", "2018-09-30"}

    def _usos(self, painel):
        """Datas D em que algo que depende do documento corrigido foi usado."""
        amostra, _ = auditor.construir_amostra(
            gates.linhas_fco(painel), gates.linhas_ativo(painel), calcular_rotulo=False)
        usos = [o["D"] for o in amostra
                if {str(r["dt_fim"]) for r in o["linhagem"]["janela"]} & self.DEPENDENTES
                or str(o["linhagem"]["ativo"]["dt_fim"]) == "2018-06-30"]
        return amostra, usos

    def test_ponta_tardia_adia_o_uso_e_g1_aprova(self):
        con, correcoes = self._montar("2019-01-15")
        painel = pp.construir(con, correcoes)
        amostra, usos = self._usos(painel)
        assert usos and min(usos) >= "2019-01-15", "antes da ponta, o valor corrigido não existe"
        provas = gates.datas_das_provas(con, correcoes)
        assert provas[self.CORRIGIDO] == date(2019, 1, 15)
        assert gates.g1_provas_depois_de_d(amostra, painel, provas) == 0
        assert gates.verificar_falsificacoes(painel, con, provas)["c3_disponibilidade_diferente_do_operando_mais_tardio"] == 0

    def test_ponta_cedo_nao_adia(self):
        con, correcoes = self._montar("2015-03-01")
        _, usos = self._usos(pp.construir(con, correcoes))
        assert "2018-08-09" in usos, "com a prova publicada antes, o uso na recepção vale"

    def test_g1_independente_pega_construtor_que_ignora_a_prova(self, monkeypatch):
        con, correcoes = self._montar("2019-01-15")
        monkeypatch.setattr(pp.Documento, "disponivel_em", property(lambda d: d.dt_receb))
        monkeypatch.setattr(pp.Documento, "disponivel_em_v1", property(lambda d: d.dt_receb_v1))
        painel = pp.construir(con, correcoes)
        provas = gates.datas_das_provas(con, correcoes)
        amostra, usos = self._usos(painel)
        assert min(usos) < "2019-01-15", "a sabotagem tem de produzir uso antecipado"
        assert gates.g1_provas_depois_de_d(amostra, painel, provas) > 0
        g1 = gates.medir(painel, provas=provas)["cadeia"][1]
        assert g1["g1_4_prova_de_escala_publicada_depois_de_D"] > 0
        assert g1["aprovado"] is False
        with pytest.raises(gates.PainelViolaContrato, match="c3"):
            gates.verificar_falsificacoes(painel, con, provas)

    def test_sem_correcoes_nao_ha_prova_a_conferir(self):
        con, _ = self._montar("2019-01-15")
        assert gates.datas_das_provas(con, {}) == {}

    def test_ponta_fora_do_cadastro_derruba(self):
        con, correcoes = self._montar("2019-01-15")
        correcoes[self.CORRIGIDO]["pontas"] = json.dumps([{"id_doc": "x"}, {"id_doc": "y"}])
        with pytest.raises(gates.PainelViolaContrato, match="c9"):
            gates.datas_das_provas(con, correcoes)


class TestTravasDaAuditoria17_09:
    """M1 e M2 do auditor de conformidade (17/09)."""

    def test_medir_sem_provas_com_escala_corrigida_levanta(self):
        con, correcoes = TestProvaDeEscalaNoTempo()._montar("2019-01-15")
        painel = pp.construir(con, correcoes)
        with pytest.raises(gates.ProvasAusentes):
            gates.medir(painel)
        with pytest.raises(gates.ProvasAusentes):
            gates.verificar_falsificacoes(painel, con)
        # Sem correção, não há prova a exigir.
        assert gates.medir(pp.construir(con))["cadeia"][1]["g1_4_prova_de_escala_publicada_depois_de_D"] == 0

    def test_correcoes_sem_caminho_sao_recusadas(self):
        c = gates.CorrecoesValidadas({("A", "itr", "2020-03-31", 1): {"x": 1}}, "h")
        with pytest.raises(gates.CorrecoesNaoValidadas, match="caminho"):
            gates.executar(c, None)

    def test_correcoes_alteradas_em_memoria_sao_recusadas(self, tmp_path):
        t = TestManifestoDeCorrecoes()
        caminho = tmp_path / "c.csv"
        t._gravar(caminho, [t._linha()])
        c = gates.carregar_correcoes(caminho, aquisicao=t._aquisicao(tmp_path))
        next(iter(c.values()))["escala_aplicada"] = "MILHAO"
        with pytest.raises(gates.CorrecoesNaoValidadas, match="memória"):
            gates.executar(c, caminho)
