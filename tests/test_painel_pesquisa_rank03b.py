"""Contraprovas do painel de pesquisa do Rank 3-B (lote C, parte 1).

Contrato: `resultados/contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md`.
Cada caso exercita uma regra de construção — e as condições de falsificação da
parte 1 têm caso próprio.
"""

from __future__ import annotations

import json
import random
from datetime import date

import duckdb
import pytest

from scripts import painel_pesquisa_rank03b as pp


class Base:
    """Monta `declaracoes`, `cadastro` e `universo` sintéticos."""

    def __init__(self):
        self.decl = []
        self.cad = []
        self._ids = 1000

    def doc(self, cd, conjunto, dt_refer, receb, versao=1, escala="MIL", receb_v1=None,
            fco=(), ativo=None, metodo="DFC_MI"):
        """`fco`: [(dt_ini, dt_fim, valor)]; `ativo`: valor na data `dt_refer`."""
        for ini, fim, vl in fco:
            self.decl.append((conjunto, metodo, cd, dt_refer, versao, "ÚLTIMO", ini, fim,
                              "6.01", escala, vl))
        if ativo is not None:
            self.decl.append((conjunto, "BPA", cd, dt_refer, versao, "ÚLTIMO", None, dt_refer,
                              "1", escala, ativo))
        if receb_v1 is not None:
            self._ids += 1
            self.cad.append((conjunto, cd, dt_refer, versao - 1, str(self._ids), receb_v1))
        self._ids += 1
        self.cad.append((conjunto, cd, dt_refer, versao, str(self._ids), receb))
        return self

    def ativo_nulo(self, cd, conjunto, dt_refer, receb):
        self.decl.append((conjunto, "BPA", cd, dt_refer, 1, "ÚLTIMO", None, dt_refer, "1", "MIL", None))
        self._ids += 1
        self.cad.append((conjunto, cd, dt_refer, 1, str(self._ids), receb))
        return self

    def con(self, ordem=None):
        con = duckdb.connect(":memory:")
        con.execute("""CREATE TABLE declaracoes (conjunto VARCHAR, demonstrativo VARCHAR,
            cd_cvm VARCHAR, dt_refer DATE, versao INT, ordem VARCHAR, dt_ini DATE, dt_fim DATE,
            cd_conta VARCHAR, escala VARCHAR, vl DOUBLE)""")
        con.execute("""CREATE TABLE cadastro (conjunto VARCHAR, cd_cvm VARCHAR, dt_refer DATE,
            versao INT, id_doc VARCHAR, dt_receb DATE)""")
        decl, cad = list(self.decl), list(self.cad)
        if ordem is not None:
            ordem.shuffle(decl)
            ordem.shuffle(cad)
        for linha in decl:
            con.execute("INSERT INTO declaracoes VALUES (?,?,?,?,?,?,?,?,?,?,?)", list(linha))
        for linha in cad:
            con.execute("INSERT INTO cadastro VALUES (?,?,?,?,?,?)", list(linha))
        cias = sorted({d[2] for d in self.decl} | {c[1] for c in self.cad})
        con.execute("CREATE TABLE universo (cd_cvm VARCHAR, plano_contas VARCHAR)")
        for c in cias:
            con.execute("INSERT INTO universo VALUES (?, 'll3_11_x')", [c])
        return con


def _ano_civil(b, cd="A", ano=2020, valores=(10, 25, 45, 70), metodo="DFC_MI", escala="MIL"):
    fins = [f"{ano}-03-31", f"{ano}-06-30", f"{ano}-09-30", f"{ano}-12-31"]
    for i, (fim, v) in enumerate(zip(fins, valores)):
        conj = "dfp" if i == 3 else "itr"
        b.doc(cd, conj, fim, f"{ano + (1 if i == 3 else 0)}-{(i + 1) * 3 % 12 + 1:02d}-10",
              fco=[(f"{ano}-01-01", fim, v)], ativo=1000 + i, metodo=metodo, escala=escala)
    return b


def _validos(painel):
    return [t for t in painel.fco_trimestral if t["estado"] == "valido"]


class TestIsolamentoPorDatas:
    def test_ano_civil_da_quatro_trimestres_com_valor_e_linhagem(self):
        p = pp.construir(_ano_civil(Base()).con())
        v = _validos(p)
        assert [t["trimestre"] for t in v] == ["1T2020", "2T2020", "3T2020", "4T2020"]
        assert [t["valor_reais"] for t in v] == [10_000, 15_000, 20_000, 25_000]
        assert [t["origem"] for t in v] == ["arquivado", "derivado", "derivado", "derivado"]
        assert v[1]["dt_ini"] == date(2020, 4, 1) and v[1]["dt_fim"] == date(2020, 6, 30)
        assert len(json.loads(v[3]["operandos"])) == 2

    def test_disponivel_em_e_o_operando_mais_tardio(self):
        """P1: o trimestre só existe completo quando o último operando chegou."""
        b = Base()
        b.doc("A", "itr", "2020-09-30", "2020-11-10", fco=[("2020-01-01", "2020-09-30", 45)])
        b.doc("A", "dfp", "2020-12-31", "2021-03-20", fco=[("2020-01-01", "2020-12-31", 70)])
        t = [t for t in pp.construir(b.con()).fco_trimestral if t["trimestre"] == "4T2020"][0]
        assert t["disponivel_em"] == date(2021, 3, 20)

    def test_disponibilidade_usa_a_versao_numerica_e_mede_o_intervalo_cego(self):
        """P1/P2: a v1 chegou antes, mas o número em mãos é o da v2."""
        b = Base()
        b.doc("A", "itr", "2020-03-31", "2020-09-01", versao=2, receb_v1="2020-05-10",
              fco=[("2020-01-01", "2020-03-31", 10)])
        t = pp.construir(b.con()).fco_trimestral[0]
        assert t["disponivel_em"] == date(2020, 9, 1)
        assert t["disponivel_em_v1"] == date(2020, 5, 10)

    def test_troca_de_metodo_nao_quebra_o_isolamento(self):
        """F2: o caixa operacional é o mesmo pelos dois métodos."""
        b = Base()
        b.doc("A", "itr", "2020-03-31", "2020-05-10", fco=[("2020-01-01", "2020-03-31", 10)],
              metodo="DFC_MD")
        b.doc("A", "itr", "2020-06-30", "2020-08-10", fco=[("2020-01-01", "2020-06-30", 25)],
              metodo="DFC_MI")
        v = _validos(pp.construir(b.con()))
        assert len(v) == 2 and v[1]["metodos"] == "DFC_MD+DFC_MI"

    def test_primeiro_acumulado_semestral_nao_e_trimestre_mas_serve_de_operando(self):
        b = Base()
        b.doc("A", "itr", "2020-06-30", "2020-08-10", fco=[("2020-01-01", "2020-06-30", 25)])
        b.doc("A", "itr", "2020-09-30", "2020-11-10", fco=[("2020-01-01", "2020-09-30", 45)])
        estados = [(t["trimestre"], t["estado"]) for t in pp.construir(b.con()).fco_trimestral]
        assert estados == [("2T2020", "primeiro_periodo_nao_trimestral"), ("3T2020", "valido")]

    def test_documento_faltando_no_meio_e_lacuna_nao_semestre_rotulado_trimestre(self):
        """O defeito dos 183 dias: aqui ele vira perda, nunca linha trimestral."""
        b = Base()
        b.doc("A", "itr", "2020-03-31", "2020-05-10", fco=[("2020-01-01", "2020-03-31", 10)])
        b.doc("A", "itr", "2020-09-30", "2020-11-10", fco=[("2020-01-01", "2020-09-30", 45)])
        t = pp.construir(b.con()).fco_trimestral[1]
        assert (t["estado"], t["dias"]) == ("lacuna", 183)

    def test_periodo_curto_e_perda(self):
        b = Base()
        b.doc("A", "itr", "2020-03-31", "2020-05-10", fco=[("2020-01-01", "2020-03-31", 10)])
        b.doc("A", "itr", "2020-05-11", "2020-06-10", fco=[("2020-01-01", "2020-05-11", 12)])
        assert pp.construir(b.con()).fco_trimestral[1]["estado"] == "curto"

    def test_nunca_subtrai_entre_exercicios(self):
        """Falsificação #4: operandos de um derivado compartilham o início do exercício."""
        b = _ano_civil(Base(), ano=2020)
        _ano_civil(b, ano=2021)
        for t in pp.construir(b.con()).fco_trimestral:
            inicios = {o["dt_ini"] for o in json.loads(t["operandos"])}
            assert inicios == {str(t["dt_ini_exercicio"])}

    def test_exercicio_nao_civil_da_rotulos_civis_consecutivos(self):
        """T2: exercício de abril a março."""
        b = Base()
        for i, fim in enumerate(["2020-06-30", "2020-09-30", "2020-12-31", "2021-03-31"]):
            b.doc("A", "itr" if i < 3 else "dfp", fim, f"2021-0{i + 1}-15",
                  fco=[("2020-04-01", fim, 10 * (i + 1))])
        assert [t["trimestre"] for t in _validos(pp.construir(b.con()))] == [
            "2T2020", "3T2020", "4T2020", "1T2021"]


class TestDeclaracoesRepetidasENulas:
    def test_mesmo_periodo_mesmo_valor_vale_a_recepcao_mais_antiga(self):
        """F3: medido em 58 casos ITR + DFP, todos iguais."""
        b = Base()
        b.doc("A", "dfp", "2020-03-31", "2020-06-01", fco=[("2020-01-01", "2020-03-31", 10)])
        b.doc("A", "itr", "2020-03-31", "2020-05-10", fco=[("2020-01-01", "2020-03-31", 10)])
        p = pp.construir(b.con())
        assert len(p.fco_acumulado) == 1
        assert p.fco_acumulado[0]["conjunto"] == "itr"
        assert p.fco_acumulado[0]["declaracoes"] == 2
        assert p.fco_trimestral[0]["disponivel_em"] == date(2020, 5, 10)

    def test_mesmo_periodo_com_valores_diferentes_e_conflito_e_contamina_o_seguinte(self):
        b = Base()
        b.doc("A", "dfp", "2020-03-31", "2020-06-01", fco=[("2020-01-01", "2020-03-31", 11)])
        b.doc("A", "itr", "2020-03-31", "2020-05-10", fco=[("2020-01-01", "2020-03-31", 10)])
        b.doc("A", "itr", "2020-06-30", "2020-08-10", fco=[("2020-01-01", "2020-06-30", 25)])
        estados = [t["estado"] for t in pp.construir(b.con()).fco_trimestral]
        assert estados == ["conflito_de_declaracoes", "operando_indisponivel"]

    def test_valor_nulo_e_estado_proprio_e_contamina_o_seguinte(self):
        b = Base()
        b.doc("A", "itr", "2020-03-31", "2020-05-10", fco=[("2020-01-01", "2020-03-31", None)])
        b.doc("A", "itr", "2020-06-30", "2020-08-10", fco=[("2020-01-01", "2020-06-30", 25)])
        p = pp.construir(b.con())
        assert [t["estado"] for t in p.fco_trimestral] == ["valor_nulo", "operando_indisponivel"]
        assert all(t["valor_reais"] is None for t in p.fco_trimestral)

    def test_colisao_de_rotulo_tira_os_dois(self):
        """T3: o N3 — dois períodos válidos sob o mesmo rótulo não se desempatam."""
        b = Base()
        b.doc("A", "itr", "2020-03-31", "2020-05-10", fco=[("2020-01-01", "2020-03-31", 10)])
        b.doc("A", "itr", "2020-02-29", "2020-04-10", fco=[("2019-12-01", "2020-02-29", 7)])
        estados = sorted(t["estado"] for t in pp.construir(b.con()).fco_trimestral)
        assert estados == ["ambiguo_exercicio", "ambiguo_exercicio"]


class TestAtivo:
    def _estado(self, valor):
        b = Base().doc("A", "itr", "2020-03-31", "2020-05-10", ativo=valor)
        return pp.construir(b.con()).ativo[0]["estado"]

    @pytest.mark.parametrize("valor,estado", [
        (1.0, "nao_informativo"), (0.5, "nao_informativo"), (-1.0, "valido"),
        (0.0, "valido"), (-500.0, "valido"), (1.5, "valido"), (29_020_618.0, "valido"),
    ])
    def test_piso_de_valor_nao_informativo(self, valor, estado):
        """A2: valor em (0, 1] na unidade declarada; zero e negativo seguem.

        Mudança declarada (auditoria de 16/09, B3): este caso esperava
        `-1.0 → nao_informativo`, contra o próprio contrato.
        """
        assert self._estado(valor) == estado

    def test_ativo_nulo_e_estado_proprio(self):
        b = Base().ativo_nulo("A", "itr", "2020-03-31", "2020-05-10")
        assert pp.construir(b.con()).ativo[0]["estado"] == "valor_nulo"

    def test_mesma_data_com_valores_diferentes_e_conflito(self):
        b = Base()
        b.doc("A", "itr", "2020-12-31", "2021-02-10", ativo=100)
        b.doc("A", "dfp", "2020-12-31", "2021-03-10", ativo=101)
        assert pp.construir(b.con()).ativo[0]["estado"] == "conflito_de_declaracoes"

    def test_escala_e_aplicada_e_saldo_nao_tem_inicio(self):
        b = Base().doc("A", "itr", "2020-03-31", "2020-05-10", ativo=7, escala="MIL")
        a = pp.construir(b.con()).ativo[0]
        assert a["valor_reais"] == 7000.0 and a["trimestre"] == "1T2020"
        assert "dt_ini" not in a

    def test_duas_posicoes_no_mesmo_trimestre_civil_sao_ambiguas(self):
        b = Base()
        b.doc("A", "itr", "2020-02-29", "2020-04-10", ativo=100)
        b.doc("A", "itr", "2020-03-31", "2020-05-10", ativo=101)
        assert {a["estado"] for a in pp.construir(b.con()).ativo} == {"ambiguo_exercicio"}


class TestEscalaEFonte:
    def test_escala_mista_no_documento_derruba(self):
        """Premissa medida (0 de 22.486): se deixar de valer, a construção para."""
        b = Base().doc("A", "itr", "2020-03-31", "2020-05-10", ativo=1,
                       fco=[("2020-01-01", "2020-03-31", 10)])
        b.decl[0] = b.decl[0][:9] + ("UNIDADE",) + b.decl[0][10:]
        with pytest.raises(pp.DefeitoDeFonte):
            pp.construir(b.con())

    def test_escala_desconhecida_derruba(self):
        b = Base().doc("A", "itr", "2020-03-31", "2020-05-10", ativo=5, escala="BILHAO")
        with pytest.raises(pp.DefeitoDeFonte):
            pp.construir(b.con())

    def _correcao(self, con, **mudar):
        brutos = con.execute(
            "SELECT cd_conta, ordem, dt_ini, dt_fim, vl FROM declaracoes").fetchall()
        c = {"escala_declarada": "UNIDADE", "escala_aplicada": "MIL",
             "base": "corrigida_documento", "id_correcao": "C1",
             "impressao_digital": pp.impressao_digital(brutos)}
        c.update(mudar)
        return {("A", "itr", "2020-03-31", 1): c}

    def _base_unidade(self):
        return Base().doc("A", "itr", "2020-03-31", "2020-05-10", ativo=7, escala="UNIDADE",
                          fco=[("2020-01-01", "2020-03-31", 10)])

    def test_correcao_valida_e_aplicada_com_procedencia(self):
        con = self._base_unidade().con()
        p = pp.construir(con, self._correcao(con))
        a = p.ativo[0]
        assert (a["valor_reais"], a["escala_declarada"], a["escala_aplicada"]) == (7000.0, "UNIDADE", "MIL")
        assert (a["base_escala"], a["id_correcao"]) == ("corrigida_documento", "C1")
        assert p.fco_trimestral[0]["escalas_aplicadas"] == "MIL"
        assert p.fco_trimestral[0]["escalas_declaradas"] == "UNIDADE"

    def test_correcao_para_outro_rotulo_nao_se_aplica(self):
        """Guarda anti-porta-dos-fundos (§3.3): a fonte mudou, a correção para."""
        con = self._base_unidade().con()
        with pytest.raises(pp.CorrecaoObsoleta):
            pp.construir(con, self._correcao(con, escala_declarada="MIL"))

    def test_correcao_com_impressao_digital_diferente_nao_se_aplica(self):
        con = self._base_unidade().con()
        with pytest.raises(pp.CorrecaoObsoleta):
            pp.construir(con, self._correcao(con, impressao_digital="0" * 64))

    def test_correcao_sem_documento_derruba(self):
        con = self._base_unidade().con()
        correcoes = self._correcao(con)
        correcoes[("B", "itr", "2020-03-31", 1)] = dict(correcoes[("A", "itr", "2020-03-31", 1)])
        with pytest.raises(pp.CorrecaoObsoleta, match="sem documento"):
            pp.construir(con, correcoes)

    def test_sem_correcao_o_rotulo_declarado_fica(self):
        """G4-pp: documento suspeito não adjudicado NÃO sai do painel."""
        p = pp.construir(self._base_unidade().con())
        assert p.ativo[0]["estado"] == "valido"
        assert p.ativo[0]["valor_reais"] == 7.0

    def test_cadastro_com_versao_repetida_usa_a_recepcao_mais_tardia(self):
        b = Base().doc("A", "itr", "2020-03-31", "2020-05-10", ativo=5)
        b.cad.append(("itr", "A", "2020-03-31", 1, "9999", "2020-06-01"))
        a = pp.construir(b.con()).ativo[0]
        assert a["disponivel_em"] == date(2020, 6, 1)
        assert "9999" in a["id_doc"]


class TestReprodutibilidadeEInventario:
    def _base(self):
        b = _ano_civil(Base(), "A", 2020)
        _ano_civil(b, "B", 2020, valores=(1, 2, 3, 4))
        b.doc("A", "itr", "2021-06-30", "2021-08-10", fco=[("2021-01-01", "2021-06-30", 5)])
        return b

    def test_digest_igual_entre_construcoes_e_sob_reordenacao(self):
        """R2/R3."""
        b = self._base()
        d1 = pp.construir(b.con()).digest
        d2 = pp.construir(b.con()).digest
        d3 = pp.construir(b.con(ordem=random.Random(7))).digest
        assert d1 == d2 == d3

    def test_digest_muda_quando_um_valor_muda(self):
        b = self._base()
        d1 = pp.construir(b.con()).digest["conjunto"]
        b.decl[0] = b.decl[0][:10] + (b.decl[0][10] + 1,)
        assert pp.construir(b.con()).digest["conjunto"] != d1

    def test_todo_acumulado_vira_exatamente_um_candidato(self):
        """Falsificação #5: nada some sem estar nas válidas ou no inventário."""
        p = pp.construir(self._base().con())
        assert len(p.fco_trimestral) == len(p.fco_acumulado)
        total = sum(v["linhas"] for v in p.inventario["fco_trimestral_por_estado"].values())
        assert total == len(p.fco_trimestral)

    def test_estados_sao_do_vocabulario_fechado(self):
        p = pp.construir(self._base().con())
        assert {t["estado"] for t in p.fco_trimestral} <= set(pp.ESTADOS_FCO)
        assert {a["estado"] for a in p.ativo} <= set(pp.ESTADOS_ATIVO)

    def test_validos_estao_na_banda_e_sao_unicos_por_rotulo(self):
        """Falsificações #1 e #2."""
        p = pp.construir(self._base().con())
        v = _validos(p)
        assert all(80 <= (t["dt_fim"] - t["dt_ini"]).days + 1 <= 100 for t in v)
        chaves = [(t["cd_cvm"], t["trimestre"]) for t in v]
        assert len(chaves) == len(set(chaves))

    def test_dois_paineis_no_mesmo_diretorio_nao_trocam_de_manifesto(self, tmp_path):
        """Com nome fixo, gravar o painel sem correções depois do governante
        deixava ao lado de `painel.duckdb` o manifesto do outro."""
        p = pp.construir(self._base().con())
        pp.gravar(p, tmp_path / "painel.duckdb", {"quem": "governante"})
        pp.gravar(p, tmp_path / "painel_sem_correcoes.duckdb", {"quem": "sem"})
        ler = lambda n: json.loads((tmp_path / n).read_text(encoding="utf-8"))["quem"]
        assert ler("manifesto_painel.json") == "governante"
        assert ler("manifesto_painel_sem_correcoes.json") == "sem"

    def test_nada_de_rotulo_do_alvo_no_painel(self):
        """O1: o painel não calcula `y`, S1, S2 nem taxa."""
        from scripts.piloto_fonte_rad_rank03b import _sem_chave_proibida
        p = pp.construir(self._base().con())
        _sem_chave_proibida(p.inventario)
        _sem_chave_proibida(p.fco_trimestral + p.ativo + p.fco_acumulado)


class TestIdentidadesEPlano:
    def test_plano_de_contas_vai_para_as_linhas(self):
        p = pp.construir(_ano_civil(Base()).con())
        assert {t["plano_contas"] for t in p.fco_trimestral} == {"ll3_11_x"}
        assert {a["plano_contas"] for a in p.ativo} == {"ll3_11_x"}

    def test_identidade_ativo_passivo_e_contada_sem_excluir(self):
        """A3: publicada, nunca usada para remover linha."""
        b = Base().doc("A", "itr", "2020-03-31", "2020-05-10", ativo=100)
        b.decl.append(("itr", "BPP", "A", "2020-03-31", 1, "ÚLTIMO", None, "2020-03-31", "2", "MIL", 90.0))
        p = pp.construir(b.con())
        assert p.inventario["a3_identidades_contabeis"]["documentos_com_ativo_diferente_do_passivo"] == 1
        assert p.ativo[0]["estado"] == "valido"

    def test_linha_duplicada_na_fonte_nao_quebra_a_identidade(self):
        """A fonte repete linhas; somá-las dobraria o fluxo e acusaria falsa quebra."""
        b = Base().doc("A", "itr", "2020-03-31", "2020-05-10", fco=[("2020-01-01", "2020-03-31", 10)])
        b.decl.append(b.decl[0])
        b.decl.append(("itr", "DFC_MI", "A", "2020-03-31", 1, "ÚLTIMO", "2020-01-01", "2020-03-31", "6.05", "MIL", 10.0))
        ids = pp.construir(b.con()).inventario["a3_identidades_contabeis"]
        assert ids["periodos_dfc_em_que_a_soma_nao_fecha"] == 0

    def test_identidade_de_caixa_e_contada(self):
        b = Base().doc("A", "itr", "2020-03-31", "2020-05-10", fco=[("2020-01-01", "2020-03-31", 10)])
        for conta, vl in (("6.02", 5.0), ("6.05", 99.0), ("6.05.01", 0.0), ("6.05.02", 15.0)):
            b.decl.append(("itr", "DFC_MI", "A", "2020-03-31", 1, "ÚLTIMO", "2020-01-01", "2020-03-31", conta, "MIL", vl))
        ids = pp.construir(b.con()).inventario["a3_identidades_contabeis"]
        assert ids["periodos_dfc_em_que_a_soma_nao_fecha"] == 1
        assert ids["periodos_dfc_em_que_o_saldo_nao_fecha"] == 1


class TestInventarioP2eF6:
    """Contraprovas que a auditoria apontou como ausentes (M4)."""

    def test_intervalo_cego_e_decisoes_dentro_dele(self):
        b = Base()
        b.doc("A", "itr", "2020-03-31", "2020-09-01", versao=2, receb_v1="2020-05-10",
              fco=[("2020-01-01", "2020-03-31", 10)])
        b.doc("A", "itr", "2020-06-30", "2020-08-10", fco=[("2020-01-01", "2020-06-30", 25)])
        inv = pp.construir(b.con()).inventario
        assert inv["p2_trimestres_validos_com_intervalo_cego"] == 2
        # Decisões da companhia: 05-10 (v1 do 1T), 08-10 (2T) e 09-01 (v2 do 1T).
        # 1T: cego em [05-10, 09-01) → 05-10 e 08-10.
        # 2T: operandos 1T (v1 05-10, vmax 09-01) e 2T (08-10); cego em
        #     [max(05-10, 08-10), max(09-01, 08-10)) = [08-10, 09-01) → 08-10.
        assert inv["p2_decisoes_da_mesma_companhia_no_intervalo_cego"] == 3

    def test_penultimo_nunca_e_operando_mas_e_contado(self):
        """F6: o PENÚLTIMO que fecharia a lacuna é contado e não usado."""
        b = Base()
        b.doc("A", "itr", "2020-03-31", "2020-05-10", fco=[("2020-01-01", "2020-03-31", 10)])
        b.doc("A", "itr", "2020-09-30", "2020-11-10", fco=[("2020-01-01", "2020-09-30", 45)])
        # documento de 2021 traz o 6M de 2020 como comparativo
        b.decl.append(("itr", "DFC_MI", "A", "2021-06-30", 1, "PENÚLTIMO", "2020-01-01", "2020-06-30", "6.01", "MIL", 25.0))
        b.cad.append(("itr", "A", "2021-06-30", 1, "777", "2021-08-10"))
        p = pp.construir(b.con())
        estados = [t["estado"] for t in p.fco_trimestral]
        assert "lacuna" in estados and "valido" not in estados[1:]
        assert p.inventario["f6_periodos_so_como_penultimo"] == 1
        assert p.inventario["f6_perdas_que_um_penultimo_fecharia"] == 1
        assert all("PENÚLTIMO" not in t["operandos"] for t in p.fco_trimestral)
