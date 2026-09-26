"""Contraprovas da adjudicação de escala (lote C, parte 2: S1–S10)."""

from __future__ import annotations

import json

import duckdb
import pytest

from scripts import adjudicar_escala_rank03b as adj
from scripts import fonte_rad_cvm as rad


def _form(cabecalho_texto, valores, grupo="193"):
    """Notas com o cabeçalho no título da página 2 (posição aceita pela RC1)."""
    from datetime import date
    return rad.Formulario(
        "f", "2", {}, [("1", None, date(2020, 9, 30), v) for v in valores],
        anexos=[(0, ["capa", cabecalho_texto + " contexto operacional " * 20])],
        grupos_anexos={0: grupo},
    )


class TestTabelaS2:
    """Tabela S2 na forma da ressalva RC1-bis (mudança declarada no contrato:
    as linhas com cabeçalho `UNIDADE` saíram — "em reais" declara moeda)."""

    @pytest.mark.parametrize("cab,num,declarada,esperado", [
        ("MIL", "bruto", "MIL", ("MIL", "confirmada")),
        ("MIL", "bruto", "UNIDADE", ("MIL", "corrigida")),
        ("MIL", "dividido", "UNIDADE", ("UNIDADE", "confirmada")),
        ("MIL", "dividido", "MIL", ("UNIDADE", "corrigida")),
    ])
    def test_os_pares_da_tabela(self, cab, num, declarada, esperado):
        assert adj.veredito(cab, num, declarada) == esperado

    @pytest.mark.parametrize("cab,num", [
        ("MIL", "nenhum"), ("MIL", "conflitante"), ("MIL", "multiplicado"),
        ("UNIDADE", "bruto"), ("UNIDADE", "multiplicado"), ("UNIDADE", "dividido"),
        ("contraditorio", "bruto"), ("ausente", "bruto"), ("sem_notas", "sem_notas"),
    ])
    def test_fora_da_tabela_nao_decide(self, cab, num):
        """RC1-bis: cabeçalho "em reais" não prova escala; sem as duas evidências, nada."""
        assert adj.veredito(cab, num, "UNIDADE") == (None, "indecidivel")

    def test_tabela_fechada_e_execucao_1_preservada(self):
        assert adj.TABELA_S2 == {("MIL", "bruto"): "MIL", ("MIL", "dividido"): "UNIDADE"}
        assert len(adj.TABELA_S2_EXECUCAO_1) == 4


class TestAdjudicarFormulario:
    """Mudança declarada (17/09, contrato E1): a regra v3 exige `dt_refer` e o
    rótulo da conta na linha do número. Os textos sintéticos ganharam o rótulo
    onde o caso quer que o número decida; nenhuma asserção foi retirada."""

    def test_rotulo_unidade_com_notas_em_milhares_e_numero_bruto_e_corrigido(self):
        """O caso da Chesf, 3T2020."""
        f = _form("(valores expressos em milhares de reais, exceto quando indicado)",
                  [29020618.0], )
        f.anexos[0][1][1] += " ativo total 29.020.618 "
        r = adj.adjudicar_formulario(f, "UNIDADE", "2020-09-30")
        assert (r["escala_do_formulario"], r["veredito"]) == ("MIL", "corrigida")
        assert r["evidencia"]["pagina"] == 2 and len(r["evidencia"]["trecho"]) >= 60

    def test_sem_trecho_literal_vira_indecidivel(self, monkeypatch):
        f = _form("(em milhares de reais)", [29020618.0])
        f.anexos[0][1][1] += " ativo total 29.020.618 "
        monkeypatch.setattr(rad, "evidencia_de_cabecalho", lambda *a: None)
        r = adj.adjudicar_formulario(f, "UNIDADE", "2020-09-30")
        assert r["veredito"] == "indecidivel"
        assert r["motivo"] == "sem_trecho_literal_do_cabecalho"

    def test_so_o_anexo_de_notas_conta(self):
        f = _form("(em milhares de reais) ativo total 29.020.618", [29020618.0], grupo="192")
        r = adj.adjudicar_formulario(f, "UNIDADE", "2020-09-30")
        assert r["veredito"] == "indecidivel" and r["motivo"].startswith("par_fora_da_tabela")

    def test_valor_de_fco_nao_e_publicado(self):
        """O1.3. O número fica DENTRO da janela do trecho — do contrário o teste
        passaria por acaso (auditoria de 16/09, M4)."""
        from datetime import date
        f = rad.Formulario("f", "2", {}, [
            ("6.01", date(2020, 1, 1), date(2020, 9, 30), -153918.0)],
            anexos=[(0, ["caixa líquido das atividades operacionais 153.918 "
                         "(em milhares de reais) nota 1 " + "x " * 50])],
            grupos_anexos={0: "193"})
        r = adj.adjudicar_formulario(f, "MIL", "2020-09-30")
        assert r["numerica"]["casamentos"], "o número tem de ter decidido"
        assert r["evidencia"] is not None and r["evidencia"]["pagina"] == 1
        # Mudança declarada (auditoria de 16/09): a versão anterior tirava
        # `evidencia` da verificação — exatamente o campo que carregava o valor.
        assert "153" not in json.dumps(r, default=str)
        assert rad.VALOR_DE_CAIXA_OMITIDO in r["evidencia"]["trecho"]

    @pytest.mark.parametrize("impresso", ["153.918", "153.918.000", "153.918.000.000"])
    def test_valor_de_caixa_mascarado_nas_tres_escalas(self, impresso):
        from datetime import date
        f = rad.Formulario("f", "2", {}, [
            ("6.01", date(2020, 1, 1), date(2020, 9, 30), -153918000.0)], anexos=[])
        saida = rad.mascarar_valores_de_caixa(f"fluxo {impresso} fim", f)
        assert "153" not in saida and rad.VALOR_DE_CAIXA_OMITIDO in saida

    def test_mascara_nao_apaga_o_que_nao_e_caixa(self):
        from datetime import date
        f = rad.Formulario("f", "2", {}, [
            ("1", None, date(2020, 9, 30), 153918.0),
            ("6.01", date(2020, 1, 1), date(2020, 9, 30), 250.0)], anexos=[])
        texto = "ativo 153.918, nota 250, (em milhares de reais)"
        assert rad.mascarar_valores_de_caixa(texto, f) == texto


def _e10(cd, trecho, escalas):
    return [{"cd_cvm": cd, "trecho": trecho, "dt_refer": f"2020-0{i + 1}-28", "conjunto": "itr",
             "escala_do_formulario": e} for i, e in enumerate(escalas)]


class TestPremissaDoTrecho:
    def test_trecho_homogeneo_permite_heranca(self):
        p = adj.premissa_do_trecho(_e10("A", 2, ["MIL"] * 4))
        assert p["heranca_permitida"] is True and p["trechos_testados"] == [["A", 2]]

    def test_um_interior_discordante_proibe_heranca_em_todo_lugar(self):
        registros = _e10("A", 2, ["MIL"] * 4) + _e10("B", 3, ["MIL", "UNIDADE", "MIL"])
        p = adj.premissa_do_trecho(registros)
        assert p["heranca_permitida"] is False
        assert p["trechos_com_interior_discordante"] == [["B", 3]]

    def test_pontas_que_discordam_tambem_refutam(self):
        p = adj.premissa_do_trecho(_e10("A", 2, ["MIL", "MIL", "UNIDADE"]))
        assert p["heranca_permitida"] is False

    def test_trecho_com_indecidivel_nao_testa_nada(self):
        p = adj.premissa_do_trecho(_e10("A", 2, ["MIL", None, "MIL"]))
        assert p["trechos_nao_testaveis"] == [["A", 2]]
        assert p["heranca_permitida"] is False, "nenhum trecho testado não é premissa aceita"

    def test_sem_piloto_nao_ha_premissa(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            adj._registros_e10(tmp_path / "nao.jsonl", None)


def _con_trecho(escalas):
    con = duckdb.connect(":memory:")
    con.execute("""CREATE TABLE docs (cd_cvm VARCHAR, trecho INT, dt_refer DATE, conjunto VARCHAR,
        versao INT, id_doc VARCHAR, escala VARCHAR, posicao INT)""")
    for i, e in enumerate(escalas):
        con.execute("INSERT INTO docs VALUES ('A', 2, ?, 'itr', 1, ?, ?, ?)",
                    [f"2020-0{i + 1}-28", f"d{i}", e, i + 1])
    return con


def _ponta(papel, id_doc, escala, veredito="corrigida"):
    return {"cd_cvm": "A", "trecho": 2, "papel": papel, "id_doc": id_doc,
            "escala_do_formulario": escala, "veredito": veredito}


class TestHeranca:
    def test_interior_herda_das_pontas_concordantes(self):
        con = _con_trecho(["UNIDADE"] * 4)
        adjudicados = {"d0": _ponta("ponta_inicial", "d0", "MIL"),
                       "d3": _ponta("ponta_final", "d3", "MIL")}
        h = adj.herdar(con, adjudicados, heranca_permitida=True)
        assert [x["id_doc"] for x in h] == ["d1", "d2"]
        assert {x["veredito"] for x in h} == {"corrigida"}
        assert h[0]["pontas"] == ["d0", "d3"]

    def test_sem_premissa_nao_herda(self):
        con = _con_trecho(["UNIDADE"] * 4)
        adjudicados = {"d0": _ponta("ponta_inicial", "d0", "MIL"),
                       "d3": _ponta("ponta_final", "d3", "MIL")}
        assert adj.herdar(con, adjudicados, heranca_permitida=False) == []

    @pytest.mark.parametrize("fim", [
        _ponta("ponta_final", "d3", "UNIDADE", "confirmada"),
        _ponta("ponta_final", "d3", None, "indecidivel"),
    ])
    def test_pontas_diferentes_ou_indecidiveis_nao_transmitem(self, fim):
        con = _con_trecho(["UNIDADE"] * 4)
        adjudicados = {"d0": _ponta("ponta_inicial", "d0", "MIL"), "d3": fim}
        assert adj.herdar(con, adjudicados, heranca_permitida=True) == []

    def test_interior_com_veredito_proprio_nao_herda(self):
        con = _con_trecho(["UNIDADE"] * 4)
        adjudicados = {"d0": _ponta("ponta_inicial", "d0", "MIL"),
                       "d3": _ponta("ponta_final", "d3", "MIL"),
                       "d1": {**_ponta("piloto", "d1", "MIL"), "papel": "piloto"}}
        assert [x["id_doc"] for x in adj.herdar(con, adjudicados, True)] == ["d2"]


SHA = "a" * 64


def _linha(**mudar):
    base = {"id_correcao": "ESC-0001", "base": "corrigida_documento", "id_doc": "10",
            "sha256_pacote": SHA, "cabecalho_classe": "MIL", "numerica_classe": "bruto",
            "escala_declarada": "UNIDADE", "escala_aplicada": "MIL",
            "evidencia_anexo": 0, "evidencia_pagina": 3, "evidencia_trecho": "x" * 60,
            "pontas": "", "evidencia_numerica": json.dumps(
                [{"conta": "1", "forma": "bruto", "anexo": 0, "pagina": 3,
                  "trecho": "total do ativo 1.234"}])}
    base.update(mudar)
    return base


def _pontas(*pares):
    return json.dumps([{"id_doc": str(i), "sha256_pacote": SHA, "veredito": v,
                        "escala_do_formulario": e} for i, (v, e) in enumerate(pares)])


class TestValidacaoDoManifesto:
    """Mudança declarada (auditoria de 16/09, M1/M2): o validador passou a exigir
    anexo, pacote de origem e a escala das pontas — e a rodar no consumidor."""

    def test_linha_boa_passa(self):
        adj.validar_manifesto([_linha()])

    @pytest.mark.parametrize("mudar", [
        {"numerica_classe": "nenhum"},
        {"cabecalho_classe": "UNIDADE"},
        {"escala_aplicada": "UNIDADE", "escala_declarada": "MIL"},
        {"evidencia_pagina": ""},
        {"evidencia_anexo": ""},
        {"evidencia_trecho": "curto"},
        {"escala_aplicada": "UNIDADE"},
        {"escala_aplicada": "MILHAO"},
        {"sha256_pacote": ""},
        {"base": "outra"},
        # E3 (17/09): a correção precisa dizer ONDE está o número que decidiu.
        {"evidencia_numerica": ""},
        {"evidencia_numerica": "[]"},
        {"evidencia_numerica": json.dumps([{"conta": "1", "forma": "bruto", "trecho": "t"}])},
    ])
    def test_falsificacoes_11_e_14(self, mudar):
        with pytest.raises(AssertionError):
            adj.validar_manifesto([_linha(**mudar)])

    def test_heranca_exige_duas_pontas_decididas_e_da_mesma_escala(self):
        """Condição 12. A versão anterior deste teste ACEITAVA corrigida+confirmada —
        num trecho de rótulo único isso é escala diferente nas pontas."""
        casos_ruins = [
            _pontas(("corrigida", "MIL"), ("indecidivel", None)),
            _pontas(("corrigida", "MIL"), ("confirmada", "UNIDADE")),
        ]
        for pontas in casos_ruins:
            with pytest.raises(AssertionError):
                adj.validar_manifesto([_linha(base="herdada_trecho", pontas=pontas)])
        boas = _pontas(("corrigida", "MIL"), ("corrigida", "MIL"))
        adj.validar_manifesto([_linha(base="herdada_trecho", pontas=boas)])

    def test_manifesto_da_execucao_1_se_rele_com_a_tabela_dele(self):
        linha = _linha(cabecalho_classe="UNIDADE", escala_declarada="MIL", escala_aplicada="UNIDADE")
        with pytest.raises(AssertionError):
            adj.validar_manifesto([linha])
        adj.validar_manifesto([linha], tabela=adj.TABELA_S2_EXECUCAO_1)

    def test_execucoes_anteriores_se_releem_sem_a_coluna_nova(self):
        linha = _linha(evidencia_numerica="")
        with pytest.raises(AssertionError, match="localizada"):
            adj.validar_manifesto([linha])
        adj.validar_manifesto([linha], exigir_evidencia_numerica=False)

    def test_pacote_citado_tem_de_constar_integro(self):
        adj.conferir_pacotes([_linha()], {"10": {SHA}})
        with pytest.raises(AssertionError, match="não consta"):
            adj.conferir_pacotes([_linha()], {"10": {"b" * 64}})
        herdada = _linha(base="herdada_trecho", pontas=_pontas(("corrigida", "MIL"), ("corrigida", "MIL")))
        with pytest.raises(AssertionError):
            adj.conferir_pacotes([herdada], {"0": {SHA}})


class TestEscopo:
    def test_pontas_e_controles(self):
        con = duckdb.connect(":memory:")
        con.execute("""CREATE TABLE docs (cd_cvm VARCHAR, trecho INT, dt_refer DATE, conjunto VARCHAR,
            versao INT, id_doc VARCHAR, escala VARCHAR, posicao INT, rotulos INT,
            rotulo_da_companhia VARCHAR)""")
        linhas = [("A", 1, "2020-03-31", "d1", "MIL", 1, 2), ("A", 2, "2020-06-30", "d2", "UNIDADE", 2, 2),
                  ("A", 2, "2020-09-30", "d3", "UNIDADE", 3, 2), ("A", 2, "2020-12-31", "d4", "UNIDADE", 4, 2),
                  ("B", 1, "2020-03-31", "d5", "UNIDADE", 1, 1), ("C", 1, "2020-03-31", "d6", "MIL", 1, 1),
                  ("C", 1, "2020-06-30", "d7", "MIL", 2, 1)]
        for cd, t, dt, i, e, pos, rot in linhas:
            rotulo = "UNIDADE" if cd == "B" else "MIL"
            con.execute("INSERT INTO docs VALUES (?,?,?, 'itr', 1, ?,?,?,?,?)",
                        [cd, t, dt, i, e, pos, rot, rotulo])
        docs = {d["id_doc"]: d for d in adj.escopo(con)}
        assert docs["d1"]["papel"] == "unica"
        assert (docs["d2"]["papel"], docs["d4"]["papel"]) == ("ponta_inicial", "ponta_final")
        assert "d3" not in docs, "interior não é adquirido"
        assert docs["d5"]["perfil"] == "so_UNIDADE"
        controles = [d for d in docs.values() if d["papel"] == "controle"]
        assert len(controles) == 1 and controles[0]["cd_cvm"] == "C"


class TestAquisicaoParalela:
    def test_cada_documento_uma_vez_e_sessoes_separadas(self):
        import threading
        chamadas, trava = [], threading.Lock()

        def adquirir(doc, cookies):
            with trava:
                chamadas.append((doc["id_doc"], cookies.name))
            return {"estado": "integro"}
        docs = [{"id_doc": str(i)} for i in range(7)] + [{"id_doc": "3"}]
        estados = adj.pre_adquirir(docs, trabalhadores=3, adquirir=adquirir)
        assert sorted(estados) == [str(i) for i in range(7)]
        assert sorted(c[0] for c in chamadas) == sorted(str(i) for i in range(7))
        assert {c[1] for c in chamadas} == {".cookies_cvm_0", ".cookies_cvm_1", ".cookies_cvm_2"}

    def test_manifesto_nao_intercala_linhas_sob_concorrencia(self, tmp_path):
        from concurrent.futures import ThreadPoolExecutor
        manifesto = tmp_path / "m.jsonl"
        registro = {"id_doc": "1", "texto": "x" * 3000}
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(lambda _: rad.registrar(registro, manifesto), range(200)))
        linhas = manifesto.read_text().splitlines()
        assert len(linhas) == 200
        assert all(json.loads(linha) == registro for linha in linhas)


class TestAdjudicacaoEmLote:
    def test_um_resultado_por_documento_em_ordem(self):
        docs = [{"id_doc": i} for i in ("3", "1", "2", "1")]
        r = adj.adjudicar_documentos(docs, leitores=1,
                                     adjudicar_um=lambda d: {"id_doc": d["id_doc"], "veredito": "x"})
        assert list(r) == ["1", "2", "3"]

    def test_falha_de_aquisicao_e_indecidivel_com_motivo(self, monkeypatch):
        monkeypatch.setattr(rad, "adquirir", lambda doc: {"estado": "falha_de_acesso"})
        r = adj._adjudicar_um({"id_doc": "9", "escala": "MIL"})
        assert r["veredito"] == "indecidivel" and r["motivo"] == "aquisicao:falha_de_acesso"

    def test_leitura_restrita_as_notas(self, monkeypatch, tmp_path):
        vistos = {}
        monkeypatch.setattr(rad, "adquirir", lambda doc: {"estado": "integro", "sha256": "h"})

        def ler(caminho, grupos=None):
            vistos["grupos"] = grupos
            raise rad.PacoteInvalido("teste")
        monkeypatch.setattr(rad, "ler", ler)
        r = adj._adjudicar_um({"id_doc": "9", "escala": "MIL"})
        assert vistos["grupos"] == rad.GRUPOS_NOTAS
        assert r["motivo"].startswith("leitura:")


class TestCabecalhoDeApresentacaoRC1:
    """Os dois textos reais que expuseram o defeito da primeira execução."""

    RODAPE_BRF = ("a movimentação das opções outorgadas em aberto é demonstrada a seguir: "
                  "(1) valores expressos em reais. voltar brf s.a.")
    RODAPE_TIM = ("25% do lucro ajustado 148.664 dividendos por ação "
                  "(valores expressos em reais) 0,06 o saldo em 30 de setembro")
    CABECALHO_BRF = ("base de preparação as demonstrações financeiras individuais e "
                     "consolidadas da companhia estão expressas em milhares de reais (r$), "
                     "exceto se mencionado")

    def _doc(self, *paginas):
        return rad.Formulario("f", "2", {}, [], anexos=[(0, list(paginas))], grupos_anexos={0: "412"})

    def _meio(self, texto):
        """Texto longe do início da página e sem objeto da apresentação antes."""
        return "outras informações " * 30 + texto

    def test_rodape_por_acao_nao_decide(self):
        for rodape in (self.RODAPE_BRF, self.RODAPE_TIM):
            f = self._doc(self._meio(rodape))
            assert rad.classificar_cabecalho_de_apresentacao(f)["classe"] == "ausente"
            # A regra v1 — a da primeira execução — aceitava:
            assert rad.classificar_cabecalho(rad.texto_das_notas(f))["classe"] == "UNIDADE"

    def test_rodape_no_titulo_da_pagina_tambem_nao_decide(self):
        """RC1-bis: o rodapé da TIM caía nos 300 primeiros caracteres."""
        f = self._doc(self.RODAPE_TIM + " " + "x" * 400)
        c = rad.classificar_cabecalho_de_apresentacao(f)
        assert c["classe"] == "ausente" and c["contagem"]["UNIDADE"] == 1

    def test_moeda_funcional_nao_contradiz_milhares(self):
        """RC1-bis: 'apresentadas em reais' é moeda, e não pode anular o MIL."""
        moeda = ("moeda funcional. tais demonstrações financeiras são apresentadas em reais, "
                 "que é a moeda funcional da companhia")
        f = self._doc(self._meio(self.CABECALHO_BRF), self._meio(moeda))
        c = rad.classificar_cabecalho_de_apresentacao(f)
        assert c["classe"] == "MIL" and c["contagem"]["UNIDADE"] == 1

    def test_flexao_feminina_e_reconhecida(self):
        f = self._doc(self._meio(self.CABECALHO_BRF))
        c = rad.classificar_cabecalho_de_apresentacao(f)
        assert c["classe"] == "MIL"
        assert rad.evidencia_de_cabecalho(f, "MIL")["por"] == "objeto"
        # A regra v1 não reconhecia "expressas":
        assert rad.classificar_cabecalho(rad.texto_das_notas(f))["classe"] == "ausente"

    def test_brf_inteira_sai_mil(self):
        f = self._doc(self._meio(self.CABECALHO_BRF), self._meio(self.RODAPE_BRF))
        assert rad.classificar_cabecalho_de_apresentacao(f)["classe"] == "MIL"

    def test_titulo_da_pagina_conta(self):
        f = self._doc("(valores expressos em milhares de reais, exceto quando indicado) 1 - contexto")
        e = rad.evidencia_de_cabecalho(f, "MIL")
        assert e["por"] == "titulo" and e["pagina"] == 1

    def test_limites_de_posicao_e_janela(self):
        frase = "(em milhares de reais)"
        dentro = self._doc("x" * (rad.INICIO_DE_PAGINA - 2) + " " + frase)
        fora = self._doc("x" * rad.INICIO_DE_PAGINA + " " + frase)
        assert rad.classificar_cabecalho_de_apresentacao(dentro)["classe"] == "MIL"
        assert rad.classificar_cabecalho_de_apresentacao(fora)["classe"] == "ausente"
        frase = "valores expressos em milhares de reais"
        longe = self._doc("y" * 400 + "demonstrações financeiras" + " z" * 120 + " " + frase)
        perto = self._doc("y" * 400 + "demonstrações financeiras " + frase)
        assert rad.classificar_cabecalho_de_apresentacao(longe)["classe"] == "ausente"
        assert rad.classificar_cabecalho_de_apresentacao(perto)["classe"] == "MIL"

    def test_so_notas_e_sem_notas(self):
        f = rad.Formulario("f", "2", {}, [], anexos=[(0, ["(em milhares de reais)"])],
                           grupos_anexos={0: "1653"})
        assert rad.classificar_cabecalho_de_apresentacao(f)["classe"] == "sem_notas"

    def test_adjudicacao_usa_a_regra_rc1(self):
        from datetime import date
        f = self._doc(self._meio(self.CABECALHO_BRF) + " ativo total 29.020.618",
                      self._meio(self.RODAPE_BRF))
        f.valores.append(("1", None, date(2022, 12, 31), 29020618.0))
        r = adj.adjudicar_formulario(f, "MIL", "2022-12-31")
        assert (r["veredito"], r["escala_do_formulario"]) == ("confirmada", "MIL")

    def test_v1_preservado_para_reproduzir_o_piloto(self):
        assert rad.CABECALHOS is rad.CABECALHOS_V1
        assert "expressos? em milhares de reais" in rad.CABECALHOS_V1["MIL"]


class TestEvidenciaNumericaLocalizada:
    """Contrato E6 (17/09): o número só decide na linha, página, período e
    perímetro certos. O primeiro caso é a forma de ESC-0101."""

    CABECALHO = "(valores expressos em milhares de reais, exceto indicado)"
    CORRENTE = "2025-09-30"

    def _doc(self, *linhas, valores=None, individuais=(), cabecalho=CABECALHO):
        from datetime import date
        valores = valores if valores is not None else [
            ("1", None, date(2025, 9, 30), 5073000.0),
            ("6.05.01", date(2024, 1, 1), date(2024, 9, 30), 1000.0),
        ]
        pagina = "\n".join([cabecalho, "1. contexto operacional", *linhas])
        return rad.Formulario("f", "1", {}, list(valores), anexos=[(0, [pagina])],
                              grupos_anexos={0: "193"}, valores_individuais=list(individuais))

    def _classe(self, f):
        return rad.evidencia_numerica_localizada(f, self.CORRENTE)

    def test_numero_em_linha_de_acoes_nao_decide(self):
        """ESC-0101: "1.000" era o saldo inicial de caixa de 2024."""
        f = self._doc("capital social de R$ 1.000,00 (mil reais), dividido em 1.000 (mil) "
                      "ações ordinárias")
        assert self._classe(f)["classe"] == "nenhum"
        assert adj.adjudicar_formulario(f, "UNIDADE", self.CORRENTE)["veredito"] == "indecidivel"

    def test_capital_com_quantidade_igual_ao_ativo_nao_decide(self):
        """A fixture do parecer: `1 = 1.234.567` e só 'capital ... 1.234.567 ações'."""
        from datetime import date
        f = self._doc("capital social dividido em 1.234.567 ações",
                      valores=[("1", None, date(2025, 9, 30), 1234567.0)])
        r = self._classe(f)
        assert r["classe"] == "nenhum"
        assert r["recusas"]["sem_rotulo"] == 1

    def test_linha_de_ativo_com_acoes_nao_decide(self):
        from datetime import date
        f = self._doc("total do ativo por ações 1.234.567",
                      valores=[("1", None, date(2025, 9, 30), 1234567.0)])
        r = self._classe(f)
        assert r["classe"] == "nenhum" and r["recusas"]["linha_de_acoes"] == 1

    def test_numero_de_outra_conta_nao_decide(self):
        f = self._doc("obras por administração 5.073.000 2.000")
        assert self._classe(f)["classe"] == "nenhum"

    def test_total_do_ativo_circulante_nao_e_o_ativo(self):
        f = self._doc("total do ativo circulante 5.073.000")
        assert self._classe(f)["classe"] == "nenhum"

    def test_valor_comparativo_nao_e_testado(self):
        """Só o período corrente decide; o 6.05.01 de 2024 não entra."""
        f = self._doc("caixa e equivalentes de caixa no início do período 1.000")
        r = self._classe(f)
        assert r["valores_testados"] == 1 and r["classe"] == "nenhum"

    def test_coincidencia_com_a_coluna_individual_nao_decide(self):
        """Individual 5.073 (em milhares) = consolidado 5.073.000 ÷ 1.000? Não:
        aqui o individual em milhares vale 5.073.000, e o número impresso casa as
        duas leituras — bruto do consolidado e ×1.000 do individual."""
        from datetime import date
        f = self._doc("total do ativo 5.073.000 5.073.000.000",
                      individuais=[("1", None, date(2025, 9, 30), 5073.0)])
        r = self._classe(f)
        assert r["recusas"]["ambiguo"] >= 1
        assert r["contagem"]["bruto"] == 0

    def test_pagina_sem_milhares_nao_decide(self):
        f = self._doc("total do ativo 5.073", cabecalho="notas explicativas")
        r = self._classe(f)
        assert r["classe"] == "nenhum" and r["recusas"]["pagina_sem_milhares"] == 1

    def test_pagina_intitulada_em_reais_nao_decide(self):
        f = self._doc("total do ativo 5.073", cabecalho="(em reais) (em milhares de reais)")
        assert self._classe(f)["classe"] == "nenhum"

    def test_documento_em_reais_com_notas_em_milhares_continua_em_reais(self):
        """A correção certa de ESC-0101: o balanço em milhares mostra 5.073."""
        f = self._doc("total do ativo 5.073 4.100",
                      "capital social dividido em 1.000 (mil) ações")
        r = adj.adjudicar_formulario(f, "UNIDADE", self.CORRENTE)
        assert (r["numerica"]["classe"], r["escala_do_formulario"], r["veredito"]) == (
            "dividido", "UNIDADE", "confirmada")
        c = r["numerica"]["casamentos"][0]
        assert (c["conta"], c["forma"], c["pagina"]) == ("1", "dividido", 1)
        assert "total do ativo" in c["trecho"]

    def test_linha_de_caixa_publicada_sem_numero(self):
        from datetime import date
        f = self._doc("caixa líquido das atividades operacionais 153.918 (12.345)",
                      valores=[("6.01", date(2025, 1, 1), date(2025, 9, 30), 153918.0)])
        c = self._classe(f)["casamentos"][0]
        assert "153" not in c["trecho"] and "12.345" not in c["trecho"]
        assert rad.VALOR_DE_CAIXA_OMITIDO in c["trecho"]

    def test_regra_v3_exige_dt_refer_e_v2_segue_disponivel(self):
        f = self._doc("capital social dividido em 1.000 (mil) ações")
        with pytest.raises(ValueError, match="dt_refer"):
            adj.adjudicar_formulario(f, "UNIDADE")
        # A v2 reproduz a execução 2 — e o defeito dela.
        r = adj.adjudicar_formulario(f, "UNIDADE", regra="v2")
        assert (r["veredito"], r["escala_do_formulario"]) == ("corrigida", "MIL")

    def test_evidencia_publicada_limitada(self):
        f = self._doc(*["total do ativo 5.073"] * 9)
        r = self._classe(f)
        assert len(r["casamentos"]) == rad.CASAMENTOS_PUBLICADOS

    def test_rede_bloqueada_para_alto(self, monkeypatch, tmp_path):
        monkeypatch.setenv(rad.SEM_REDE, "1")
        with pytest.raises(rad.RedeBloqueada):
            rad.baixar("123", tmp_path / "x.zip", executar=lambda *a, **k: None)
