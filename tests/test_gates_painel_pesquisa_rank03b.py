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
                "evidencia_trecho": "x" * 60, "pontas": ""}
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
        assert d["com_escalas_declaradas_diferentes"] == 1
        assert d["sem_veredito_em_algum_operando"] == 1
        assert d["governa_este_lote"] is False

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
