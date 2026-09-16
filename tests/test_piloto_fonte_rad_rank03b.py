"""Contraprovas do piloto de fonte do lote B (contrato P1 e O1)."""

from __future__ import annotations

import duckdb
import pytest

from scripts import piloto_fonte_rad_rank03b as piloto


def _painel(tmp_path, companhias):
    caminho = tmp_path / "painel.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute("CREATE TABLE companhias (cd_cvm VARCHAR, plano_contas VARCHAR, is_banco BOOLEAN)")
    con.executemany("INSERT INTO companhias VALUES (?,?,?)", companhias)
    con.close()
    return caminho


def _base(tmp_path, documentos, versoes_extras=()):
    """`documentos`: (cd_cvm, conjunto, dt_refer, escala, ativo)."""
    con = duckdb.connect(":memory:")
    con.execute("""CREATE TABLE declaracoes (cd_cvm VARCHAR, conjunto VARCHAR, dt_refer DATE,
        versao INT, ordem VARCHAR, cd_conta VARCHAR, dt_ini DATE, dt_fim DATE, escala VARCHAR, vl DOUBLE)""")
    con.execute("""CREATE TABLE cadastro (cd_cvm VARCHAR, conjunto VARCHAR, dt_refer DATE,
        versao INT, id_doc VARCHAR, dt_receb DATE)""")
    for i, (cd, cj, dt, esc, ativo) in enumerate(documentos):
        con.execute("INSERT INTO declaracoes VALUES (?,?,?,?, 'ÚLTIMO','1',NULL,?,?,?)",
                    [cd, cj, dt, 2 if (cd, cj, dt) in versoes_extras else 1, dt, esc, ativo])
        v = 2 if (cd, cj, dt) in versoes_extras else 1
        con.execute("INSERT INTO cadastro VALUES (?,?,?,?,?,?)", [cd, cj, dt, v, str(1000 + i), dt])
        if v == 2:
            con.execute("INSERT INTO cadastro VALUES (?,?,?,?,?,?)", [cd, cj, dt, 1, str(5000 + i), dt])
    empresas = sorted({d[0] for d in documentos})
    piloto.preparar(con, _painel(tmp_path, [(c, "ll3_11_x", False) for c in empresas]
                                 + [("BANCO1", "ll3_09_x", False)]))
    return con


class TestSelecao:
    def test_criterios_sao_os_do_contrato(self):
        """P1.1/P1.3 fixados antes do código: mudar exige mudar o contrato.

        A soma passou de 47 para 50 com o estrato E10, acrescentado pela
        ressalva RA4 antes da segunda execução — declarado no contrato.
        """
        assert piloto.PISO_DOWNLOAD_INTEGRO == 0.90
        assert piloto.PISO_EVIDENCIA_E1_E4 == 0.70
        assert piloto.ESTRATOS["E7_varias_versoes"] == 8
        assert piloto.ESTRATOS["E10_trecho_completo"] == 3
        assert piloto.TAMANHO_DO_TRECHO_COMPLETO == (3, 10)
        assert sum(piloto.ESTRATOS.values()) == 50

    def test_fronteira_e_interior_sao_separados(self, tmp_path):
        docs = [("A", "itr", f"2020-0{m}-28", e, 10.0)
                for m, e in zip(range(1, 6), ["MIL", "MIL", "UNIDADE", "MIL", "MIL"])]
        con = _base(tmp_path, docs)
        e1 = piloto._membros_do_estrato(con, "E1_fronteira_UNIDADE")
        e2 = {m["dt_refer"] for m in piloto._membros_do_estrato(con, "E2_fronteira_MIL")}
        e3 = {m["dt_refer"] for m in piloto._membros_do_estrato(con, "E3_interior_de_mista")}
        assert [m["dt_refer"] for m in e1] == ["2020-03-28"]
        assert e2 == {"2020-02-28", "2020-04-28"}
        assert e3 == {"2020-01-28", "2020-05-28"}

    def test_companhia_financeira_fica_fora(self, tmp_path):
        con = _base(tmp_path, [("A", "itr", "2020-03-31", "MIL", 1.0)])
        con.execute("INSERT INTO declaracoes VALUES ('BANCO1','itr','2020-03-31',1,'ÚLTIMO','1',NULL,'2020-03-31','MIL',1)")
        assert {r[0] for r in con.execute("SELECT cd_cvm FROM universo").fetchall()} == {"A"}

    def test_uma_por_companhia_e_ordem_pelo_hash(self, tmp_path):
        docs = [(c, "itr", f"2020-0{m}-28", "UNIDADE", 10.0)
                for c in "ABCDEFGH" for m in (1, 2)]
        con = _base(tmp_path, docs)
        sel = [d for d in piloto.selecionar(con) if "E4_companhia_so_UNIDADE" in d["estratos"]]
        assert len(sel) == 5
        assert len({d["cd_cvm"] for d in sel}) == 5
        esperado = sorted(piloto._membros_do_estrato(con, "E4_companhia_so_UNIDADE"),
                          key=lambda m: m["ordem"])
        vistos, ordem = set(), []
        for m in esperado:
            if m["cd_cvm"] not in vistos and len(ordem) < 5:
                vistos.add(m["cd_cvm"])
                ordem.append(m["id_doc"])
        assert sorted(d["id_doc"] for d in sel) == sorted(ordem)

    def test_selecao_e_deterministica_e_nao_olha_o_valor(self, tmp_path):
        """Trocar os valores não pode mudar quem é selecionado."""
        docs = [(c, "itr", "2020-03-31", "UNIDADE", 10.0) for c in "ABCDEFG"]
        a = [d["id_doc"] for d in piloto.selecionar(_base(tmp_path, docs))]
        outros = [(c, j, d, e, 99999.0) for c, j, d, e, _ in docs]
        (tmp_path / "painel.duckdb").unlink()
        b = [d["id_doc"] for d in piloto.selecionar(_base(tmp_path, outros))]
        assert a == b

    def test_trecho_completo_entra_inteiro_e_so_de_3_a_10(self, tmp_path):
        """RA4/E10: o interior só testa a premissa se o trecho vier inteiro."""
        rotulos = (["MIL"] * 2 + ["UNIDADE"] * 4 + ["MIL"] * 11 + ["UNIDADE"] * 2)
        docs = [("A", "itr", f"20{10 + i // 4}-{3 * (i % 4) + 3:02d}-28", e, 10.0)
                for i, e in enumerate(rotulos)]
        con = _base(tmp_path, docs)
        trechos = piloto._trechos_completos(con, 3)
        assert len(trechos) == 1, "só o trecho de 4 cabe em 3–10; um por companhia"
        assert [d["escala"] for d in trechos[0]] == ["UNIDADE"] * 4
        datas = [d["dt_refer"] for d in trechos[0]]
        assert datas == sorted(datas)
        sel = [d for d in piloto.selecionar(con) if "E10_trecho_completo" in d["estratos"]]
        assert len(sel) == 4

    def test_trecho_completo_nao_vem_de_companhia_de_um_rotulo(self, tmp_path):
        docs = [("B", "itr", f"2020-0{m}-28", "UNIDADE", 10.0) for m in range(1, 6)]
        assert piloto._trechos_completos(_base(tmp_path, docs), 3) == []

    def test_varias_versoes_traz_o_par_v1(self, tmp_path):
        docs = [("A", "itr", "2020-03-31", "MIL", 10.0)]
        con = _base(tmp_path, docs, versoes_extras={("A", "itr", "2020-03-31")})
        sel = piloto.selecionar(con)
        papeis = {d["papel"]: d for d in sel if "E7_varias_versoes" in d["estratos"]}
        assert set(papeis) == {"vmax", "v1"}
        assert papeis["v1"]["versao"] == 1 and papeis["v1"]["par_de"] == papeis["vmax"]["id_doc"]


def _reg(estratos, aquisicao="integro", leitura="ok", classe="declara_MIL",
         escala="MIL", x13=(10, 10), adjudicado=False):
    r = {"id_doc": "1", "cd_cvm": "A", "dt_refer": "2020-03-31", "conjunto": "itr",
         "estratos": estratos, "aquisicao": aquisicao,
         "escala_declarada": escala, "adjudicado_pelo_inventario": adjudicado}
    if aquisicao == "integro":
        r.update(leitura=leitura)
        if leitura == "ok":
            # Campos da ressalva RA3, acrescentados à fixture com ela.
            r.update(classe_unidade=classe, codigo_escala_moeda="2",
                     x13={"linhas_no_zip": x13[0], "iguais": x13[1]},
                     formato="xml_unico",
                     cabecalho_notas={"classe": "MIL"},
                     evidencia_numerica={"classe": "bruto"})
    return r


class TestCriterioParaEstender:
    def test_tudo_bom_estende(self):
        regs = [_reg(["E1_fronteira_UNIDADE"]) for _ in range(10)]
        assert piloto.resumir(regs)["estender"] is True

    def test_uma_linha_divergente_do_zip_impede(self):
        """X1.3: um erro de mapeamento invalida tudo o que vem depois."""
        regs = [_reg(["E1_fronteira_UNIDADE"]) for _ in range(9)] + [
            _reg(["E1_fronteira_UNIDADE"], x13=(10, 9))]
        r = piloto.resumir(regs)
        assert r["criterios_P1_3"]["c2_parser_igual_ao_zip"]["atendido"] is False
        assert r["estender"] is False

    def test_nenhum_documento_lido_nao_aprova(self):
        """§4.4 regra 4: 0 de 0 não é 100%."""
        regs = [_reg(["E1_fronteira_UNIDADE"], aquisicao="falha_de_acesso")]
        r = piloto.resumir(regs)
        assert r["criterios_P1_3"]["c2_parser_igual_ao_zip"]["atendido"] is False
        assert r["criterios_P1_3"]["c3_evidencia_de_unidade_E1_E4"]["atendido"] is False
        assert r["estender"] is False

    def test_documento_sem_linha_no_zip_nao_conta_como_identico(self):
        r = piloto.resumir([_reg(["E1_fronteira_UNIDADE"], x13=(0, 0))])
        assert r["criterios_P1_3"]["c2_parser_igual_ao_zip"]["atendido"] is False

    def test_download_abaixo_do_piso_impede(self):
        regs = [_reg(["E1_fronteira_UNIDADE"]) for _ in range(8)] + [
            _reg(["E1_fronteira_UNIDADE"], aquisicao="falha_de_acesso") for _ in range(2)]
        assert piloto.resumir(regs)["criterios_P1_3"]["c1_download_integro"]["atendido"] is False

    def test_evidencia_ausente_demais_impede_e_so_conta_E1_a_E4(self):
        regs = ([_reg(["E1_fronteira_UNIDADE"], classe="ausente") for _ in range(4)]
                + [_reg(["E1_fronteira_UNIDADE"]) for _ in range(6)]
                + [_reg(["E5_companhia_so_MIL"]) for _ in range(20)])
        c3 = piloto.resumir(regs)["criterios_P1_3"]["c3_evidencia_de_unidade_E1_E4"]
        assert c3["medido"] == 0.6 and c3["atendido"] is False

    def test_formato_nao_reconhecido_conta_como_nao_integro(self):
        regs = [_reg(["E9_exercicio_2011_2012"], aquisicao="formato_nao_reconhecido")] + [
            _reg(["E1_fronteira_UNIDADE"]) for _ in range(9)]
        assert piloto.resumir(regs)["criterios_P1_3"]["c1_download_integro"]["medido"] == 0.9

    def test_concordancia_separa_rotulo_e_notas(self):
        regs = [_reg(["E1_fronteira_UNIDADE"], escala="UNIDADE", classe="declara_MIL",
                     adjudicado=True)]
        r = piloto.resumir(regs)
        assert r["concordancia_com_rotulo_por_estrato"]["E1_fronteira_UNIDADE"] == {"discorda": 1}
        assert r["inventario_x_notas"] == {"adjudicado=True|notas_concordam_com_rotulo=False": 1}


class TestMedidasDaRessalvaRA3:
    def test_cabecalho_e_numerica_saem_por_estrato_sem_mudar_P1_3(self):
        regs = [_reg(["E1_fronteira_UNIDADE"]) for _ in range(3)]
        r = piloto.resumir(regs)
        assert r["cabecalho_e_numerica_por_estrato"]["E1_fronteira_UNIDADE"] == {"MIL|bruto": 3}
        assert set(r["criterios_P1_3"]) == {"c1_download_integro", "c2_parser_igual_ao_zip",
                                            "c3_evidencia_de_unidade_E1_E4"}

    def test_trecho_completo_sai_em_ordem_com_as_falhas(self):
        regs = [
            {**_reg(["E10_trecho_completo"]), "dt_refer": "2020-06-30"},
            {**_reg(["E10_trecho_completo"], aquisicao="falha_de_acesso"), "dt_refer": "2020-03-31"},
        ]
        trecho = piloto.resumir(regs)["trechos_completos"]["A"]
        assert [t["dt_refer"] for t in trecho] == ["2020-03-31", "2020-06-30"]
        assert trecho[0]["cabecalho"] is None and trecho[1]["numerica"] == "bruto"


class TestCegueiraAoDesfecho:
    @pytest.mark.parametrize("chave", sorted(piloto.CHAVES_PROIBIDAS))
    def test_chave_de_rotulo_em_qualquer_nivel_derruba(self, chave):
        with pytest.raises(AssertionError, match="O1"):
            piloto._sem_chave_proibida([{"ok": {"lista": [{chave: 1}]}}])

    def test_resumo_nao_carrega_chave_de_rotulo(self):
        piloto._sem_chave_proibida(piloto.resumir([_reg(["E1_fronteira_UNIDADE"])]))

    def test_divergencia_publica_so_a_chave_nunca_o_valor(self, monkeypatch, tmp_path):
        """O1.3: valor de FCO só é lido para testar igualdade."""
        from datetime import date

        from scripts import fonte_rad_cvm as rad
        doc = {"id_doc": "1", "cd_cvm": "A", "conjunto": "itr", "dt_refer": "2020-09-30",
               "versao": 1, "estratos": ["E1_fronteira_UNIDADE"], "papel": "vmax",
               "escala": "MIL"}
        chave = ("6.01", date(2020, 1, 1), date(2020, 9, 30))
        monkeypatch.setattr(rad, "adquirir", lambda *a, **k: {"estado": "integro"})
        monkeypatch.setattr(rad, "ler", lambda *a, **k: rad.Formulario("f", "2", {}, []))
        monkeypatch.setattr(rad, "por_chave", lambda f: {chave: 123456.0})
        monkeypatch.setattr(piloto, "_zip_do_documento", lambda con, d: {chave: 654321.0})
        saida = piloto.medir_documento(None, doc, set(), brutos=tmp_path)
        texto = repr(saida)
        assert "123456" not in texto and "654321" not in texto
        assert saida["x13"]["divergentes"] == [["6.01", "2020-01-01", "2020-09-30"]]
