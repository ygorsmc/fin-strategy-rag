"""Contraprovas da correção por conta (contrato de 27/09, parte A, cláusula A6).

Duas frentes: o manifesto (esquema fechado; a mesma validação no produtor e no
consumidor, com evidência e conferência) e o construtor (a correção de uma
conta não toca a outra; a guarda de republicação continua valendo).
"""

from __future__ import annotations

import csv
import hashlib
import json

import pytest

from scripts import auditar_rank03b_consumo_operacional as auditor
from scripts import correcoes_por_conta_rank03b as pc
from scripts import gates_painel_pesquisa_rank03b as gates
from scripts import painel_pesquisa_rank03b as pp
from scripts import rota_prova_rank03b as rota
from tests.test_painel_pesquisa_rank03b import Base
from tests.test_rota_prova_rank03b import DOC, conferencia, pares_que_passam_no_b6, registro


# --- manifesto -----------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _sem_fontes_de_marcas(monkeypatch):
    """As marcas de GEOM-1 e controle vêm de arquivos reais; os registros aqui são
    sintéticos e não pertencem a eles (os testes de controle substituem a fonte)."""
    monkeypatch.setattr(rota, "documentos_geom1", lambda: frozenset())
    monkeypatch.setattr(rota, "controles", lambda: {})


def _linha(**mudar):
    linha = {"id_correcao": "ESCC-0001", "cd_cvm": "003549", "conjunto": "itr",
             "dt_refer": "2020-09-30", "versao": "1", "id_doc": DOC, "sha256_pacote": "a" * 64,
             "conta": "1", "escala_declarada": "UNIDADE", "escala_aplicada": "MIL",
             "base": "corrigida_conta", "prova": "celula_propria",
             "id_prova": rota.id_prova(DOC, "1"), "regra": rota.REGRA,
             "sha256_evidencias": "e" * 64, "sha256_conferencia": "c" * 64,
             "impressao_digital": "f" * 64}
    linha.update(mudar)
    return linha


def _registros():
    return pares_que_passam_no_b6() + [registro(conta="1"), registro(conta="1.01.01"),
                                       registro(conta="6.01")]


def _conferencia(registros, sha="e" * 64, resultado="aprovada"):
    return conferencia(registros, sha=sha, resultado=resultado)


INTEGROS = {DOC: {"a" * 64}}


def validar(linhas, registros=None, conferencia=None, **kw):
    registros = registros if registros is not None else _registros()
    conferencia = conferencia if conferencia is not None else _conferencia(registros)
    pc.validar_linhas(linhas, registros, "e" * 64, conferencia, "c" * 64,
                      kw.pop("integros", INTEGROS), **kw)


class TestValidacaoDasLinhas:
    def test_linhas_boas_passam(self):
        validar([_linha(), _linha(id_correcao="ESCC-0002", conta="6.01", prova="cadeia_dfc",
                                  id_prova=rota.id_prova(DOC, "6.01"))])

    @pytest.mark.parametrize("mudanca,motivo", [
        ({"conta": "1.01.01"}, "conta"), ({"escala_aplicada": "UNIDADE"}, "só leva"),
        ({"escala_aplicada": "MILHAO"}, "vocabulário"), ({"base": "corrigida_documento"}, "base"),
        ({"regra": "v4"}, "regra"), ({"prova": "cadeia_dfc"}, "prova"),
        ({"sha256_evidencias": "0" * 64}, "hash"), ({"sha256_conferencia": "0" * 64}, "hash"),
        ({"sha256_pacote": "b" * 64}, "pacote"), ({"id_prova": "ROTA-1-1-1"}, "outro documento"),
        ({"dt_refer": "2020-06-30"}, "outro documento"), ({"versao": "x"}, "versão")])
    def test_linha_fora_do_contrato_e_recusada(self, mudanca, motivo):
        with pytest.raises(pc.ManifestoPorContaInvalido, match=motivo):
            validar([_linha(**mudanca)])

    @pytest.mark.parametrize("veredito_da_prova", ["confirmada", "indecidivel"])
    def test_prova_que_nao_corrige_nao_sustenta_a_linha(self, veredito_da_prova):
        regs = _registros()
        escala = "UNIDADE" if veredito_da_prova == "confirmada" else None
        regs[-3] = registro(conta="1", escala=escala)
        # Sem a correção da conta 1, o caixa e o FCO corrigidos do mesmo documento
        # ficam sem âncora da mesma escala: o arquivo inteiro é recusado antes.
        regs[-2] = registro(conta="1.01.01", escala=escala)
        regs[-1] = registro(conta="6.01", escala=escala)
        with pytest.raises(pc.ManifestoPorContaInvalido, match="não sustenta"):
            validar([_linha()], registros=regs)

    def test_escala_da_prova_diferente_da_linha(self):
        with pytest.raises(pc.ManifestoPorContaInvalido, match="não sustenta"):
            validar([_linha(escala_declarada="MIL", escala_aplicada="UNIDADE")])

    def test_duas_linhas_do_mesmo_documento_e_conta(self):
        with pytest.raises(pc.ManifestoPorContaInvalido, match="mesmo documento"):
            validar([_linha(), _linha(id_correcao="ESCC-0002")])

    def test_id_correcao_repetido(self):
        with pytest.raises(pc.ManifestoPorContaInvalido, match="repetido"):
            validar([_linha(), _linha(conta="6.01", prova="cadeia_dfc",
                                      id_prova=rota.id_prova(DOC, "6.01"))])

    def test_documento_tambem_no_manifesto_por_documento(self):
        with pytest.raises(pc.ManifestoPorContaInvalido, match="por documento"):
            validar([_linha()], chaves_do_legado={("003549", "itr", "2020-09-30", 1)})

    def test_prova_sem_aprovacao_na_conferencia(self):
        regs = _registros()
        conf = _conferencia(regs)
        conf["correcoes"][rota.id_prova(DOC, "1")] = {"resultado": "pendente"}
        with pytest.raises(pc.ManifestoPorContaInvalido):
            validar([_linha()], registros=regs, conferencia=conf)

    def test_conferencia_que_recusou_outra_correcao_para_tudo(self):
        regs = _registros()
        conf = _conferencia(regs)
        conf["correcoes"][rota.id_prova(DOC, "6.01")] = {"resultado": "recusada"}
        with pytest.raises(pc.ManifestoPorContaInvalido, match="recusou"):
            validar([_linha()], registros=regs, conferencia=conf)

    def test_controle_corrigido_para_tudo(self, monkeypatch):
        chave = ("003549", "itr", "2019-09-30", 1)
        monkeypatch.setattr(rota, "controles", lambda: {chave: "777777"})
        regs = _registros() + [registro("777777", "1", papeis=("controle",), dt_refer="2019-09-30")]
        with pytest.raises(pc.ManifestoPorContaInvalido, match="parada"):
            validar([_linha()], registros=regs)


def _gravar(caminho, colunas, linhas=()):
    with open(caminho, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(colunas)
        for linha in linhas:
            w.writerow([linha.get(c, "") for c in colunas])


class TestEsquemaFechado:
    @pytest.mark.parametrize("colunas", [
        pc.COLUNAS + ["extra"], pc.COLUNAS[:-1], pc.COLUNAS + [pc.COLUNAS[0]],
        [pc.COLUNAS[1], pc.COLUNAS[0], *pc.COLUNAS[2:]]])
    @pytest.mark.parametrize("com_linhas", [False, True])
    def test_cabecalho_diferente_e_recusado_antes_de_aplicar(self, tmp_path, colunas, com_linhas):
        caminho = tmp_path / "m.csv"
        _gravar(caminho, colunas, [_linha()] if com_linhas else [])
        with pytest.raises(pc.ManifestoPorContaInvalido, match="esquema"):
            pc._ler_e_validar_esquema(caminho)

    def test_arquivo_sem_linhas_com_cabecalho_certo(self, tmp_path):
        caminho = tmp_path / "m.csv"
        _gravar(caminho, pc.COLUNAS)
        assert pc._ler_e_validar_esquema(caminho)[0] == []

    def test_aspas_soltas_sao_recusadas(self, tmp_path):
        caminho = tmp_path / "m.csv"
        caminho.write_text(",".join(pc.COLUNAS) + "\n" + 'x"y' + "," * 16 + "\n", encoding="utf-8")
        with pytest.raises(pc.ManifestoPorContaInvalido, match="sintaxe"):
            pc._ler_e_validar_esquema(caminho)

    def test_ausente_e_erro(self, tmp_path):
        with pytest.raises(pc.ManifestoPorContaInvalido, match="não existe"):
            pc._ler_e_validar_esquema(tmp_path / "nao.csv")


class TestConsumidorPontaAPonta:
    def _pasta(self, tmp_path):
        pasta = tmp_path / "rota"
        pasta.mkdir()
        regs = _registros()
        texto = "".join(json.dumps(r, sort_keys=True) + "\n" for r in regs)
        (pasta / "evidencias.jsonl").write_text(texto, encoding="utf-8")
        sha_ev = hashlib.sha256(texto.encode()).hexdigest()
        conf = json.dumps(_conferencia(regs, sha=sha_ev))
        (pasta / "conferencia.json").write_text(conf, encoding="utf-8")
        sha_conf = hashlib.sha256(conf.encode()).hexdigest()
        aquisicao = tmp_path / "aq.jsonl"
        aquisicao.write_text(json.dumps({"id_doc": DOC, "estado": "integro",
                                         "sha256": "a" * 64}) + "\n", encoding="utf-8")
        return pasta, sha_ev, sha_conf, aquisicao

    def test_carrega_so_depois_de_validar_tudo(self, tmp_path):
        pasta, sha_ev, sha_conf, aquisicao = self._pasta(tmp_path)
        caminho = tmp_path / "m.csv"
        _gravar(caminho, pc.COLUNAS, [_linha(sha256_evidencias=sha_ev, sha256_conferencia=sha_conf)])
        c = pc.carregar(caminho, pasta, aquisicao)
        assert isinstance(c, pc.CorrecoesPorConta)
        assert list(c) == [("003549", "itr", "2020-09-30", 1)]
        assert list(c[("003549", "itr", "2020-09-30", 1)]) == ["1"]

    def test_evidencia_alterada_depois_do_manifesto_e_recusada(self, tmp_path):
        pasta, sha_ev, sha_conf, aquisicao = self._pasta(tmp_path)
        caminho = tmp_path / "m.csv"
        _gravar(caminho, pc.COLUNAS, [_linha(sha256_evidencias=sha_ev, sha256_conferencia=sha_conf)])
        with open(pasta / "evidencias.jsonl", "a", encoding="utf-8") as fh:
            fh.write("\n")
        with pytest.raises(pc.ManifestoPorContaInvalido):
            pc.carregar(caminho, pasta, aquisicao)

    def test_produtor_usa_a_mesma_validacao(self, tmp_path):
        pasta, sha_ev, sha_conf, _ = self._pasta(tmp_path)
        regs, _ = rota.ler_evidencias(pasta / "evidencias.jsonl")
        conf, _ = rota.ler_conferencia(pasta / "conferencia.json")
        with pytest.raises(pc.ManifestoPorContaInvalido):
            pc.escrever(tmp_path / "m.csv", [_linha(escala_aplicada="UNIDADE",
                                                    sha256_evidencias=sha_ev,
                                                    sha256_conferencia=sha_conf)],
                        regs, sha_ev, conf, sha_conf, INTEGROS)
        assert not (tmp_path / "m.csv").exists(), "nada é gravado quando a validação falha"


# --- construtor --------------------------------------------------------------------------

def _serie_M_U_M():
    """Três ITRs de 2020; o do meio declara UNIDADE com os dígitos contínuos."""
    b = Base()
    b.doc("A", "itr", "2020-03-31", "2020-05-10", escala="MIL", ativo=1_000,
          fco=[("2020-01-01", "2020-03-31", 10)])
    b.doc("A", "itr", "2020-06-30", "2020-08-10", escala="UNIDADE", ativo=1_010,
          fco=[("2020-01-01", "2020-06-30", 25)])
    b.doc("A", "itr", "2020-09-30", "2020-11-10", escala="MIL", ativo=1_020,
          fco=[("2020-01-01", "2020-09-30", 45)])
    return b


def _correcao_da_conta(con, conta, **mudar):
    chave = ("A", "itr", "2020-06-30", 1)
    brutos = con.execute(
        "SELECT cd_conta, ordem, dt_ini, dt_fim, vl FROM declaracoes "
        "WHERE dt_refer = DATE '2020-06-30'").fetchall()
    id_doc = con.execute(
        "SELECT id_doc FROM cadastro WHERE dt_refer = DATE '2020-06-30'").fetchone()[0]
    linha = {"escala_declarada": "UNIDADE", "escala_aplicada": "MIL", "base": "corrigida_conta",
             "id_correcao": f"ESCC-{conta}", "id_doc": id_doc,
             "impressao_digital": pp.impressao_digital(brutos)}
    linha.update(mudar)
    return {chave: {conta: linha}}


def _g0_3(painel):
    linhas = gates.linhas_ativo(painel)
    return auditor.gate_g0(gates.linhas_fco(painel), linhas, gates.duracoes(painel),
                           gates.nulos(painel))["g0_3_saltos_de_escala"]


class TestConstrutorPorConta:
    def test_prova_do_ativo_muda_so_o_ativo(self):
        con = _serie_M_U_M().con()
        sem = pp.construir(con)
        com = pp.construir(con, correcoes_por_conta=_correcao_da_conta(con, "1"))
        assert [a["valor_reais"] for a in sem.ativo] == [1_000_000, 1_010, 1_020_000]
        assert [a["valor_reais"] for a in com.ativo] == [1_000_000, 1_010_000, 1_020_000]
        assert com.ativo[1]["base_escala"] == "corrigida_conta"
        assert com.ativo[1]["escala_aplicada"] == "MIL"
        # O FCO sai idêntico, valor a valor, e continua heterogêneo sem veredito.
        chave = lambda t: (t["dt_ini"], t["dt_fim"], t["valor_reais"], t["escalas_aplicadas"])  # noqa: E731
        assert [chave(t) for t in com.fco_trimestral] == [chave(t) for t in sem.fco_trimestral]
        assert com.fco_trimestral[1]["escalas_aplicadas"] == "MIL+UNIDADE"
        assert _g0_3(sem) == 2 and _g0_3(com) == 0

    def test_prova_do_fco_muda_so_o_fco(self):
        con = _serie_M_U_M().con()
        sem = pp.construir(con)
        com = pp.construir(con, correcoes_por_conta=_correcao_da_conta(con, "6.01"))
        assert [a["valor_reais"] for a in com.ativo] == [a["valor_reais"] for a in sem.ativo]
        assert [t["escalas_aplicadas"] for t in com.fco_trimestral] == ["MIL", "MIL+MIL", "MIL+MIL"]
        assert [t["valor_reais"] for t in com.fco_trimestral] == [10_000, 15_000, 20_000]
        assert _g0_3(com) == 2, "a prova do FCO não mexe no detector do ativo"

    def test_republicacao_derruba(self):
        con = _serie_M_U_M().con()
        with pytest.raises(pp.CorrecaoObsoleta):
            pp.construir(con, correcoes_por_conta=_correcao_da_conta(
                con, "1", impressao_digital="0" * 64))

    def test_rotulo_declarado_diferente_derruba(self):
        con = _serie_M_U_M().con()
        with pytest.raises(pp.CorrecaoObsoleta):
            pp.construir(con, correcoes_por_conta=_correcao_da_conta(con, "1", escala_declarada="MIL"))

    def test_por_documento_e_por_conta_no_mesmo_documento_derruba(self):
        con = _serie_M_U_M().con()
        por_conta = _correcao_da_conta(con, "1")
        por_documento = {k: {**v["1"], "base": "corrigida_documento"} for k, v in por_conta.items()}
        with pytest.raises(pp.CorrecaoObsoleta, match="por documento e por conta"):
            pp.construir(con, por_documento, por_conta)

    def test_correcao_sem_documento_derruba(self):
        con = _serie_M_U_M().con()
        por_conta = _correcao_da_conta(con, "1")
        por_conta[("B", "itr", "2020-06-30", 1)] = por_conta[("A", "itr", "2020-06-30", 1)]
        with pytest.raises(pp.CorrecaoObsoleta, match="sem documento"):
            pp.construir(con, correcoes_por_conta=por_conta)

    def test_conta_fora_do_contrato_derruba(self):
        con = _serie_M_U_M().con()
        por_conta = _correcao_da_conta(con, "1")
        por_conta[("A", "itr", "2020-06-30", 1)] = {"1.01.01": por_conta[("A", "itr", "2020-06-30", 1)]["1"]}
        with pytest.raises(pp.DefeitoDeFonte):
            pp.construir(con, correcoes_por_conta=por_conta)

    def test_prova_publicada_depois_atrasa_so_a_conta_provada(self):
        """P4 por conta: a data da prova do ativo não atrasa o FCO do mesmo documento."""
        b = _serie_M_U_M()
        b.cad.append(("itr", "Z", "2021-01-31", 1, "prova_tardia", "2021-02-01"))
        con = b.con()
        com = pp.construir(con, correcoes_por_conta=_correcao_da_conta(con, "1", id_doc="prova_tardia"))
        from datetime import date
        assert com.ativo[1]["disponivel_em"] == date(2021, 2, 1)
        assert com.fco_trimestral[1]["disponivel_em"] == date(2020, 8, 10)
