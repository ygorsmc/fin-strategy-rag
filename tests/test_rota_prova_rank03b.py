"""Contraprovas da ROTA-1 (contrato de 27/09, parte B, cláusula B10, com a emenda
pós-auditoria do mesmo dia, anterior a qualquer execução em dado real).

Formulário e páginas sintéticos: cada caso exercita uma decisão da regra — o
que prova, o que não prova e o que não pode sair do registro (O1).

**Substituição declarada (emenda A2 de 27/09).** Na primeira versão,
`test_classificacao_de_unidade` fixava "lucro por ação (em reais)" como neutro
(`None`). A auditoria mostrou que a neutralidade "por ação" anulava também
declarações da própria tabela, inclusive de milhões. Agora só é neutra a menção de
reais numa linha que declara milhares; sozinha, ela veta (`OUTRA`). O caso ficou
com a expectativa nova, e as variantes que a auditoria achou ganharam contraprova.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import zipfile
from datetime import date
from decimal import Decimal

import duckdb
import pytest

from scripts import rota_prova_rank03b as rota

CORRENTE = date(2020, 9, 30)
ANTERIOR = date(2019, 12, 31)
#: Um id que não é de desenho nem da GEOM-1 (a marca é recalculada das fontes).
DOC = "555555"


def formulario(ativo=19_358, ativo_ant=19_572, caixa=None, caixa_ant=None,
               individual=None, extra=None):
    cons = {("1", None, CORRENTE): Decimal(ativo), ("1", None, ANTERIOR): Decimal(ativo_ant)}
    if caixa is not None:
        cons[("1.01.01", None, CORRENTE)] = Decimal(caixa)
        cons[("1.01.01", None, ANTERIOR)] = Decimal(caixa_ant)
    cons.update(extra or {})
    indiv = {}
    if individual is not None:
        indiv[("1", None, CORRENTE)] = Decimal(individual)
    return rota.Formulario("xml_unico", "x.xml", cons, indiv)


def anexo(*paginas, grupo="193", indice=0):
    return rota.Anexo(indice, grupo, "notas.pdf", list(paginas))


BALANCO_EM_MILHARES = """Companhia X — Demonstrações financeiras
                         Ativo
                    Em Milhares de Reais
                         30/09/2020     31/12/2019
Circulante                    3.489          2.389
Total do Ativo               19.358         19.572
"""


def provar(form, *anexos, conta="1", csv=None):
    valor = form.saldo("consolidado", conta, CORRENTE)
    return rota.provar_celula(form, list(anexos), conta, CORRENTE,
                              csv if csv is not None else valor)


class TestProvaPorCelula:
    def test_tabela_em_milhares_com_os_digitos_do_formulario_prova_MIL(self):
        r = provar(formulario(), anexo(BALANCO_EM_MILHARES))
        assert r["escala_do_formulario"] == "MIL"
        linha = r["linhas"][0]
        assert linha["forma"] == "bruto" and linha["unidade"]["origem"] == "local"
        assert linha["ancora"] == "consolidado:2019-12-31"
        assert not re.search(r"\d", linha["trecho"]), "trecho publicado sem dígito"

    def test_ESC_0101_formulario_em_reais_e_notas_em_milhares_confirma_UNIDADE(self):
        """O caso real de 17/09: 5.073.000 no formulário, 5.073 no comentário em milhares."""
        form = formulario(ativo=5_073_000, ativo_ant=4_120_000)
        pagina = ("Balanço patrimonial (Em milhares de reais)\n"
                  "Total do ativo        5.073     4.120\n")
        r = provar(form, anexo(pagina, grupo="192"))
        assert r["escala_do_formulario"] == "UNIDADE"
        assert r["linhas"][0]["forma"] == "dividido"

    def test_numero_em_linha_de_acoes_nao_prova(self):
        """ESC-0101 original: o número casado era quantidade de ações."""
        pagina = ("(Em milhares de reais)\n"
                  "Total do ativo dividido em 19.358 ações e 19.572 ações\n")
        r = provar(formulario(), anexo(pagina))
        assert r["escala_do_formulario"] is None
        assert r["motivo"] == "linha_de_acoes"

    def test_sem_ancora_na_linha_nao_prova(self):
        pagina = "(Em milhares de reais)\nTotal do ativo      19.358\n"
        r = provar(formulario(), anexo(pagina))
        assert r["escala_do_formulario"] is None
        assert r["motivo"] == "sem_linha_com_os_dois_numeros"

    def test_sem_rotulo_nao_prova(self):
        pagina = "(Em milhares de reais)\nOutros valores     19.358    19.572\n"
        assert provar(formulario(), anexo(pagina))["motivo"] == "sem_rotulo"

    def test_total_do_ativo_circulante_nao_e_o_ativo_total(self):
        pagina = "(Em milhares de reais)\nTotal do ativo circulante   19.358   19.572\n"
        assert provar(formulario(), anexo(pagina))["motivo"] == "sem_rotulo"

    def test_rotulo_com_letras_espacadas_pelo_extrator_confere(self):
        pagina = "(Em milhares de reais)\nTOTA L DO A TIV O    19.358    19.572\n"
        assert provar(formulario(), anexo(pagina))["escala_do_formulario"] == "MIL"

    @pytest.mark.parametrize("unidade", [
        "(Em reais)", "Em reais", "Em R$", "(R$)", "Valores em R$", "(Valores expressos em R$)",
        "Em unidades de reais", "(Em milhões de reais)", "R$ milhões", "Valores expressos em reais",
        "(Em milhões de reais, exceto lucro por ação)", "(Em reais, exceto o lucro por ação)"])
    def test_unidade_local_contraria_nao_prova(self, unidade):
        pagina = f"(Em milhares de reais)\n{unidade}\nTotal do ativo  19.358  19.572\n"
        r = provar(formulario(), anexo(pagina))
        assert r["escala_do_formulario"] is None
        assert r["motivo"] == "unidade_local_nao_mil"

    def test_a_declaracao_mais_proxima_acima_decide(self):
        pagina = "(Em reais)\nTabela seguinte\n(Em milhares de reais)\nTotal do ativo 19.358 19.572\n"
        assert provar(formulario(), anexo(pagina))["escala_do_formulario"] == "MIL"

    def test_balanco_em_reais_abaixo_de_tabela_em_milhares_nao_prova(self):
        """Achado A2 da auditoria: "Em reais" sem parêntese tem de vetar."""
        pagina = ("Tabela 1 (Em milhares de reais)\nReceita   1.234   1.111\n\n"
                  "Balanço — Em reais\nTotal do ativo 19.358 19.572\n")
        assert provar(formulario(), anexo(pagina))["escala_do_formulario"] is None

    def test_ressalva_por_acao_na_linha_de_milhares_nao_veta(self):
        pagina = ("(Em milhares de reais, exceto o lucro por ação, expresso em reais)\n"
                  "Total do ativo 19.358 19.572\n")
        assert provar(formulario(), anexo(pagina))["escala_do_formulario"] == "MIL"

    def test_tabela_em_milhoes_com_ressalva_por_acao_nao_prova_unidade(self):
        """Achado A2: a ressalva por ação não pode neutralizar "milhões". Formulário em
        milhares, tabela em milhões imprimindo ÷1.000: seria um ESC-0101 invertido."""
        form = formulario(ativo=19_358_000, ativo_ant=19_572_000)
        pagina = ("(Em milhões de reais, exceto lucro por ação)\n"
                  "Total do ativo 19.358 19.572\n")
        r = provar(form, anexo(pagina))
        assert r["escala_do_formulario"] is None and r["motivo"] == "unidade_local_nao_mil"

    def test_apresentacao_do_anexo_vale_sem_cabecalho_local(self):
        capa = "Notas explicativas às informações trimestrais\n(Valores expressos em milhares de reais)\n"
        pagina = "4 - Caixa\nTotal do ativo   19.358   19.572\n"
        r = provar(formulario(), anexo(capa, pagina))
        assert r["escala_do_formulario"] == "MIL"
        assert r["linhas"][0]["unidade"] == {"origem": "apresentacao"}

    @pytest.mark.parametrize("veto", ["Outra tabela (em reais)", "Outra tabela em reais",
                                      "Valores em R$", "Quadro (R$)", "em milhões"])
    def test_pagina_com_outra_unidade_sem_cabecalho_local_nao_prova(self, veto):
        capa = "Notas explicativas às informações trimestrais\n(Valores expressos em milhares de reais)\n"
        pagina = f"Total do ativo   19.358   19.572\n{veto}\n"
        r = provar(formulario(), anexo(capa, pagina))
        assert r["escala_do_formulario"] is None
        assert r["motivo"] == "sem_unidade_de_milhares"

    def test_anexo_com_apresentacao_em_duas_unidades_nao_vale(self):
        capa = ("Demonstrações financeiras (em milhares de reais)\n"
                "Notas explicativas — valores expressos em reais\n")
        pagina = "Total do ativo   19.358   19.572\n"
        assert provar(formulario(), anexo(capa, pagina))["escala_do_formulario"] is None

    def test_bruto_e_dividido_no_mesmo_documento_e_indecidivel(self):
        form = formulario(ativo=19_358_000, ativo_ant=19_572_000)
        bruto = "(Em milhares de reais)\nTotal do ativo 19.358.000 19.572.000\n"
        dividido = "(Em milhares de reais)\nTotal do ativo 19.358 19.572\n"
        r = provar(form, anexo(bruto), anexo(dividido, indice=1))
        assert r["escala_do_formulario"] is None and r["motivo"] == "conflitante"

    @pytest.mark.parametrize("linha", ["Total do ativo 119.358 19.572",
                                       "Total do ativo 19.358,00 19.572,00",
                                       "Total do ativo 19.3581 19.572",
                                       "Total do ativo (19.358) (19.572)"])
    def test_numero_colado_decimal_ou_de_sinal_trocado_nao_casa(self, linha):
        r = provar(formulario(), anexo(f"(Em milhares de reais)\n{linha}\n"))
        assert r["escala_do_formulario"] is None

    def test_formulario_diferente_do_csv_e_indecidivel(self):
        r = provar(formulario(), anexo(BALANCO_EM_MILHARES), csv=19_359)
        assert r["motivo"] == "formulario_diferente_do_csv"

    def test_valor_abaixo_do_minimo_nao_prova(self):
        form = formulario(ativo=999, ativo_ant=1_500)
        assert provar(form, anexo("(Em milhares de reais)\nTotal do ativo 999 1.500\n"))["motivo"] \
            == "valor_abaixo_do_minimo"

    def test_ancora_individual_serve_quando_nao_ha_comparativo_na_linha(self):
        form = formulario(individual=19_266)
        pagina = "(Em milhares de reais)\nTotal do Ativo   19.266   19.358\n"
        r = provar(form, anexo(pagina))
        assert r["escala_do_formulario"] == "MIL"
        assert r["linhas"][0]["ancora"] == "individual:2020-09-30"

    def test_caixa_pela_linha_total_sob_o_titulo_da_nota(self):
        form = formulario(caixa=104_575, caixa_ant=118_001)
        pagina = ("4 - CAIXA E EQUIVALENTES DE CAIXA\n"
                  "            Consolidado\n"
                  "     30/09/2020   31/12/2019\n"
                  "Aplicações      95.765     76.160\n"
                  "Total          104.575    118.001\n")
        capa = "Notas explicativas às informações trimestrais (valores expressos em milhares de reais)\n"
        r = provar(form, anexo(capa, pagina), conta="1.01.01")
        assert r["escala_do_formulario"] == "MIL"

    def test_linha_total_sem_titulo_de_caixa_nao_prova_o_caixa(self):
        form = formulario(caixa=104_575, caixa_ant=118_001)
        pagina = "(Em milhares de reais)\n4 - FORNECEDORES\nTotal   104.575   118.001\n"
        assert provar(form, anexo(pagina), conta="1.01.01")["motivo"] == "sem_rotulo"

    def test_linha_total_vale_so_pelo_titulo_mais_proximo(self):
        """Achado B5: a nota de caixa acima de OUTRA nota não empresta o título."""
        form = formulario(caixa=104_575, caixa_ant=118_001)
        pagina = ("4 - CAIXA E EQUIVALENTES DE CAIXA\n"
                  "Aplicações      95.765     76.160\n"
                  "5 - FORNECEDORES\n"
                  "Total          104.575    118.001\n")
        assert provar(form, anexo(pagina), conta="1.01.01")["motivo"] == "sem_rotulo"

    def test_anexo_ilegivel_e_contado_e_nao_prova(self):
        r = provar(formulario(), rota.Anexo(0, "193", "x.pdf", None))
        assert r["escala_do_formulario"] is None and r["recusas"]["anexo_ilegivel"] == 1


class TestVocabularios:
    def test_formas(self):
        assert rota.representacoes(Decimal(19_358), "bruto") == {"19.358"}
        assert rota.representacoes(Decimal(5_073_500), "dividido") == {"5.074"}
        assert rota.representacoes(Decimal(5_072_500), "dividido") == {"5.073", "5.072"}
        assert rota.representacoes(Decimal(999), "bruto") == set()
        assert rota.representacoes(Decimal("19358.5"), "bruto") == set()

    def test_tokens_exigem_parenteses_fechados(self):
        assert [t.digitos for t in rota.tokens("a 1.234 (5.678) (9.999")] == ["1.234", "5.678"]
        assert [t.negativo for t in rota.tokens("a 1.234 (5.678) -2.000")] == [False, True, True]

    @pytest.mark.parametrize("texto,classe", [
        ("(em milhares de reais)", "MIL"), ("valores em r$ mil", "MIL"), ("em r$ mil", "MIL"),
        ("(valores expressos em milhares de reais – r$, exceto quando indicado de outra forma)", "MIL"),
        ("(em milhares de reais, exceto o lucro por ação, em reais)", "MIL"),
        ("(em reais)", "OUTRA"), ("em reais", "OUTRA"), ("em r$", "OUTRA"), ("(r$)", "OUTRA"),
        ("valores em r$", "OUTRA"), ("em unidades de reais", "OUTRA"),
        ("r$ milhões", "OUTRA"), ("em r$ milhões", "OUTRA"),
        ("(em milhões de reais, exceto lucro por ação)", "OUTRA"),
        ("(em reais, exceto o lucro por ação)", "OUTRA"),
        # Substituição declarada (emenda A2): era None.
        ("lucro por ação (em reais)", "OUTRA"),
        ("informações gerais", None), ("em milhares de toneladas", None)])
    def test_classificacao_de_unidade(self, texto, classe):
        assert rota.classificar_unidade(texto) == classe

    def test_selecao_geom1_tem_os_22_ids_e_nao_dicionarios(self):
        """Achado A1: o conjunto tomava o dicionário inteiro como id."""
        ids = rota.documentos_geom1()
        assert len(ids) == 22 and "98282" in ids and "142900" in ids
        assert all(re.fullmatch(r"\d+", i) for i in ids)

    def test_controles_sao_os_30_do_escopo_v4(self):
        assert len(rota.controles()) == 30


# --- pacotes sintéticos (XML único) --------------------------------------------------------

def _conta(codigo, **colunas):
    return ("<Conta><ContaFixa>True</ContaFixa>"
            f"<CodigoConta>{codigo}</CodigoConta><DescricaoConta>x</DescricaoConta>"
            + "".join(f"<{k}>{v}</{k}>" for k, v in colunas.items()) + "</Conta>")


def _xml_itr(bpa, dfc="", anexos=""):
    return (
        "<?xml version='1.0' encoding='utf-8'?><XmlInformacoesTrimestraisFinanceiras>"
        "<DadosEmpresa/><Documento/><DadosITR>"
        "<DataReferencia>30/09/2020</DataReferencia><DtInicioTrimestreAtual>01/07/2020</DtInicioTrimestreAtual>"
        "<DtFimTrimestreAtual>30/09/2020</DtFimTrimestreAtual>"
        "<DtInicioExercicioSocialCurso>01/01/2020</DtInicioExercicioSocialCurso>"
        "<DtFimExercicioSocialCurso>31/12/2020</DtFimExercicioSocialCurso>"
        "<DtInicioExercicioSocialAnterior>01/01/2019</DtInicioExercicioSocialAnterior>"
        "<DtFimExercicioSocialAnterior>31/12/2019</DtFimExercicioSocialAnterior>"
        "<EscalaMoeda>1</EscalaMoeda><Formulario><DfConsolidadas>"
        f"<BalancoPatrimonialAtivo>{bpa}</BalancoPatrimonialAtivo>"
        f"<DemonstracaoFluxoCaixa>{dfc}</DemonstracaoFluxoCaixa>"
        "</DfConsolidadas></Formulario>"
        f"<AnexosDocumento>{anexos}</AnexosDocumento></DadosITR></XmlInformacoesTrimestraisFinanceiras>"
    )


def _pacote(tmp_path, xml, nome="p.zip"):
    caminho = tmp_path / nome
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("003549ITR30-09-2020v1.xml", xml)
    return caminho


def _bpa(total="1.935.800", circ="348.900", nao_circ="1.586.900", caixa="3.600", outros="345.300"):
    """Fecha: 348.900 + 1.586.900 = 1.935.800; 3.600 + 345.300 = 348.900."""
    return (_conta("1", TrimestreAtual=total, ExercicioAnterior="1.957.200")
            + _conta("1.01", TrimestreAtual=circ) + _conta("1.02", TrimestreAtual=nao_circ)
            + _conta("1.01.01", TrimestreAtual=caixa) + _conta("1.01.02", TrimestreAtual=outros))


def _dfc(fco="-150.000", fci="-20.000", fcf="166.000", var="-4.000", inicial="7.600", final="3.600"):
    """Fecha: -150.000 - 20.000 + 166.000 = -4.000; 7.600 - 4.000 = 3.600 = caixa."""
    return (_conta("6.01", Metodo="Indireto", AcumuladoAtualExercicio=fco)
            + _conta("6.02", AcumuladoAtualExercicio=fci) + _conta("6.03", AcumuladoAtualExercicio=fcf)
            + _conta("6.05", AcumuladoAtualExercicio=var)
            + _conta("6.05.01", AcumuladoAtualExercicio=inicial)
            + _conta("6.05.02", AcumuladoAtualExercicio=final))


CHAVE = ("003549", "itr", "2020-09-30", 1)
PERIODO = (date(2020, 1, 1), date(2020, 9, 30))


def _csv(fco_no_csv=-150000.0):
    """A `declaracoes` que o construtor lê, só com a 6.01 corrente do documento."""
    con = duckdb.connect(":memory:")
    con.execute("""CREATE TABLE declaracoes (conjunto VARCHAR, demonstrativo VARCHAR,
        cd_cvm VARCHAR, dt_refer DATE, versao INT, ordem VARCHAR, dt_ini DATE, dt_fim DATE,
        cd_conta VARCHAR, escala VARCHAR, vl DOUBLE)""")
    con.execute("INSERT INTO declaracoes VALUES ('itr','DFC_MI','003549','2020-09-30',1,'ÚLTIMO',"
                "'2020-01-01','2020-09-30','6.01','UNIDADE',?)", [fco_no_csv])
    return con


class TestEloDoBalanco:
    def test_identidades_fechadas_dao_o_elo(self, tmp_path):
        form = rota.ler_formulario(_pacote(tmp_path, _xml_itr(_bpa())), rota.contas_do_balanco)
        assert rota.elo_balanco(form, CORRENTE) == {"b1": True, "b2": True}

    def test_soma_dos_filhos_aberta_nao_da_elo(self, tmp_path):
        form = rota.ler_formulario(_pacote(tmp_path, _xml_itr(_bpa(outros="345.000"))),
                                   rota.contas_do_balanco)
        assert rota.elo_balanco(form, CORRENTE)["b2"] is False

    def test_total_diferente_das_partes_nao_da_elo(self, tmp_path):
        form = rota.ler_formulario(_pacote(tmp_path, _xml_itr(_bpa(total="1.935.900"))),
                                   rota.contas_do_balanco)
        assert rota.elo_balanco(form, CORRENTE)["b1"] is False

    def test_caixa_abaixo_de_mil_nao_ancora(self, tmp_path):
        """Achado B4: com tolerância 1, um caixa de módulo pequeno não distingue bases."""
        bpa = _bpa(circ="345.336", caixa="36", outros="345.300", total="1.932.236")
        form = rota.ler_formulario(_pacote(tmp_path, _xml_itr(bpa)), rota.contas_do_balanco)
        assert rota.elo_balanco(form, CORRENTE) == {"b1": True, "b2": False}

    def test_prova_por_celula_nao_le_conta_6(self, tmp_path):
        form = rota.ler_formulario(_pacote(tmp_path, _xml_itr(_bpa(), _dfc())), rota.contas_do_balanco)
        assert not any(c.startswith("6") for c, _, _ in form.consolidado)


class TestCadeiaDaDfc:
    def test_cadeia_fechada(self, tmp_path):
        caminho = _pacote(tmp_path, _xml_itr(_bpa(), _dfc()))
        assert rota.cadeia_dfc(caminho, PERIODO, _csv(), CHAVE) == {
            "d1": True, "d2": True, "d3": True, "igual_ao_csv": True}

    def test_saldo_final_diferente_do_caixa_do_balanco_abre_D3(self, tmp_path):
        caminho = _pacote(tmp_path, _xml_itr(_bpa(), _dfc(fcf="166.002", final="3.602", var="-3.998")))
        assert rota.cadeia_dfc(caminho, PERIODO, _csv(), CHAVE) == {
            "d1": True, "d2": True, "d3": False, "igual_ao_csv": True}

    def test_fco_em_outra_base_abre_D1(self, tmp_path):
        """O FCO digitado ×1.000 não reconstitui a variação do caixa."""
        caminho = _pacote(tmp_path, _xml_itr(_bpa(), _dfc(fco="-150.000.000")))
        assert rota.cadeia_dfc(caminho, PERIODO, _csv(-150000000.0), CHAVE)["d1"] is False

    def test_formulario_diferente_do_csv(self, tmp_path):
        caminho = _pacote(tmp_path, _xml_itr(_bpa(), _dfc()))
        assert rota.cadeia_dfc(caminho, PERIODO, _csv(-150001.0), CHAVE)["igual_ao_csv"] is False

    def test_caixa_abaixo_de_mil_nao_fecha_D3(self, tmp_path):
        bpa = _bpa(circ="345.336", caixa="36", outros="345.300", total="1.932.236")
        caminho = _pacote(tmp_path, _xml_itr(bpa, _dfc(fcf="162.436", var="-7.564", final="36")))
        assert rota.cadeia_dfc(caminho, PERIODO, _csv(), CHAVE)["d3"] is False

    def test_saida_so_booleana(self, tmp_path):
        caminho = _pacote(tmp_path, _xml_itr(_bpa(), _dfc()))
        r = rota.cadeia_dfc(caminho, PERIODO, _csv(), CHAVE)
        assert all(type(v) is bool for v in r.values())


# --- registros, arquivo e parada ---------------------------------------------------------

def registro(id_doc=DOC, conta="1", escala="MIL", declarada="UNIDADE", prova=None,
             papeis=("T_A",), **extra):
    prova = prova or rota.PROVAS_DA_CONTA[conta][0]
    base = {"id_prova": rota.id_prova(id_doc, conta), "regra": rota.REGRA, "cd_cvm": "003549",
            "conjunto": "itr", "dt_refer": "2020-09-30", "versao": 1, "id_doc": id_doc,
            "sha256_pacote": "a" * 64, "papeis": list(papeis), "desenho": id_doc in rota.DESENHO,
            "geom1": False, "conta": conta, "prova": prova, "escala_declarada": declarada,
            "escala_do_formulario": escala,
            "veredito": "indecidivel" if escala is None else
            ("confirmada" if escala == declarada else "corrigida"),
            "motivo": None if escala else "sem_linha_com_os_dois_numeros"}
    forma = {"MIL": "bruto", "UNIDADE": "dividido"}.get(escala)
    if prova == "celula_propria" and escala:
        base.update(linhas=[{"anexo": 0, "grupo": "193", "arquivo": "n.pdf", "pagina": 4,
                             "linha": 29, "forma": forma, "ancora": "consolidado:2019-12-31",
                             "posicoes": [2, 3], "unidade": {"origem": "apresentacao"},
                             "trecho": "Total do Ativo ##.### ##.###"}],
                    contagem={"bruto": int(forma == "bruto"), "dividido": int(forma == "dividido")},
                    recusas={})
    if prova == "elo_balanco":
        base["elo"] = {"b1": True, "b2": True, "ancora": rota.id_prova(id_doc, "1")}
    if prova == "cadeia_dfc":
        base["cadeia"] = {"d1": True, "d2": True, "d3": True, "igual_ao_csv": True,
                          "ancora": rota.id_prova(id_doc, "1.01.01")}
    base.update(extra)
    return base


def pares_que_passam_no_b6(n=10):
    saida = []
    for i in range(n):
        d = f"9{i:04d}"
        saida += [registro(d, "1", "MIL", "MIL"), registro(d, "1.01.01", "MIL", "MIL")]
    return saida


#: As marcas são recalculadas das fontes; nos testes, sem GEOM-1 e sem controle.
SEM_MARCAS = {"geom1": frozenset(), "chaves_de_controle": set()}


def conferencia(registros, sha="x" * 64, resultado="aprovada", confirmacoes="aprovada"):
    return {"regra": rota.REGRA, "sha256_evidencias": sha,
            "correcoes": {i: {"resultado": resultado} for i in rota.correcoes_exigidas(registros)},
            "confirmacoes": {i: {"resultado": confirmacoes}
                             for i in rota.amostra_de_confirmacoes(registros)}}


class TestValidacaoDoRegistro:
    def test_registro_bom_passa(self):
        rota.validar_registro(registro())

    @pytest.mark.parametrize("mudanca", [
        {"veredito": "confirmada"}, {"escala_do_formulario": "BILHAO"},
        {"prova": "cadeia_dfc"}, {"regra": "v4"}, {"id_prova": "ROTA-1-1-1"},
        {"motivo": "qualquer"}])
    def test_registro_incoerente_e_recusado(self, mudanca):
        r = registro()
        r.update(mudanca)
        with pytest.raises(rota.EvidenciaInvalida):
            rota.validar_registro(r)

    def test_trecho_com_digito_e_recusado(self):
        r = registro()
        r["linhas"][0]["trecho"] = "Total do Ativo 19.358 19.572"
        with pytest.raises(rota.EvidenciaInvalida):
            rota.validar_registro(r)

    def test_forma_que_nao_implica_a_escala_e_recusada(self):
        r = registro()
        r["linhas"][0]["forma"] = "dividido"
        with pytest.raises(rota.EvidenciaInvalida):
            rota.validar_registro(r)

    def test_decisao_com_contagem_da_outra_forma_e_conflito(self):
        """Achado M4: um registro conflitante rotulado como decidido passava."""
        r = registro()
        r["contagem"]["dividido"] = 1
        with pytest.raises(rota.EvidenciaInvalida, match="só da forma"):
            rota.validar_registro(r)

    def test_formas_misturadas_nas_linhas_sao_recusadas(self):
        r = registro()
        r["linhas"].append(dict(r["linhas"][0], forma="dividido"))
        r["contagem"]["bruto"] = 2
        with pytest.raises(rota.EvidenciaInvalida):
            rota.validar_registro(r)

    def test_cadeia_com_identidade_aberta_e_recusada(self):
        r = registro(conta="6.01")
        r["cadeia"]["d3"] = False
        with pytest.raises(rota.EvidenciaInvalida):
            rota.validar_registro(r)


class TestArquivo:
    def test_cadeia_exige_ancora_da_mesma_escala(self):
        regs = pares_que_passam_no_b6() + [registro(conta="1"), registro(conta="1.01.01"),
                                           registro(conta="6.01")]
        assert rota.validar_arquivo(regs, **SEM_MARCAS)["b6"]["aprovado"]
        regs[-2] = registro(conta="1.01.01", escala="UNIDADE", declarada="UNIDADE")
        with pytest.raises(rota.EvidenciaInvalida, match="âncora"):
            rota.validar_arquivo(regs, **SEM_MARCAS)

    def test_b6_reprovado_anula_elo_e_cadeia(self):
        """Nove pares por célula; o décimo documento tem o caixa pelo elo, que não conta."""
        regs = pares_que_passam_no_b6(9) + [registro(conta="1"),
                                            registro(conta="1.01.01", prova="elo_balanco"),
                                            registro(conta="6.01")]
        b6 = rota.aplicar_b6(regs)
        assert not b6["aprovado"]
        assert regs[-1]["veredito"] == "indecidivel" and regs[-1]["motivo"] == "teste_b6_reprovado"
        assert regs[-2]["veredito"] == "indecidivel", "o elo também não prova"
        rota.validar_arquivo(regs, **SEM_MARCAS)

    def test_consumidor_recusa_cadeia_decidida_com_b6_reprovado(self):
        """Achado M4: sem `aplicar_b6`, o consumidor tem de recusar sozinho."""
        regs = pares_que_passam_no_b6(9) + [registro(conta="1"),
                                            registro(conta="1.01.01", prova="elo_balanco"),
                                            registro(conta="6.01")]
        with pytest.raises(rota.EvidenciaInvalida, match="B6"):
            rota.validar_arquivo(regs, **SEM_MARCAS)

    def test_discordancia_ativo_caixa_reprova_o_b6(self):
        regs = pares_que_passam_no_b6(12)
        regs[1] = registro("90000", "1.01.01", "UNIDADE", "MIL")
        assert rota.teste_b6(regs)["discordancias"] == 1
        assert not rota.teste_b6(regs)["aprovado"]

    def test_desenho_e_geom1_nao_contam_no_b6(self):
        regs = [dict(r, geom1=True) for r in pares_que_passam_no_b6(12)]
        assert rota.teste_b6(regs)["documentos"] == 0

    def test_marca_de_geom1_adulterada_e_recusada(self):
        """Achado B7: o consumidor recalcula as marcas das fontes fixadas."""
        regs = [registro("98282", "1")]  # 98282 é da verificação GEOM-1 (arquivo real)
        with pytest.raises(rota.EvidenciaInvalida, match="adulterada"):
            rota.conferir_marcas(regs, chaves_de_controle=set())
        rota.conferir_marcas([registro("98282", "1", geom1=True)], chaves_de_controle=set())

    def test_marca_de_desenho_e_de_controle_sao_recalculadas(self):
        with pytest.raises(rota.EvidenciaInvalida):
            rota.conferir_marcas([registro("98645", "1", desenho=False)], frozenset(), set())
        with pytest.raises(rota.EvidenciaInvalida):
            rota.conferir_marcas([registro(papeis=("controle",))], frozenset(), set())

    def test_controle_corrigido_para_tudo(self):
        controle = registro("777777", "1", papeis=("controle",), dt_refer="2019-09-30")
        regs = pares_que_passam_no_b6() + [controle]
        chave = ("003549", "itr", "2019-09-30", 1)
        assert rota.validar_arquivo(regs, frozenset(), {chave})["parada"] is True

    def test_documento_e_conta_repetidos(self):
        with pytest.raises(rota.EvidenciaInvalida, match="repetidos"):
            rota.validar_arquivo([registro(), registro()], **SEM_MARCAS)


class TestConferencia:
    def test_conferencia_cobre_toda_correcao(self):
        regs = [registro()]
        rota.validar_conferencia(conferencia(regs), regs, "x" * 64)
        sem = conferencia(regs)
        sem["correcoes"] = {}
        with pytest.raises(rota.EvidenciaInvalida, match="sem conferência"):
            rota.validar_conferencia(sem, regs, "x" * 64)

    def test_uma_recusa_para_tudo(self):
        regs = [registro()]
        with pytest.raises(rota.EvidenciaInvalida, match="recusou"):
            rota.validar_conferencia(conferencia(regs, resultado="recusada"), regs, "x" * 64)

    def test_conferencia_de_outras_evidencias(self):
        regs = [registro()]
        with pytest.raises(rota.EvidenciaInvalida, match="outras"):
            rota.validar_conferencia(conferencia(regs), regs, "y" * 64)

    def test_amostra_de_confirmacoes_e_exigida_e_recusa_para_tudo(self):
        """Achado M5: a amostra da B8 passa a ter efeito."""
        regs = pares_que_passam_no_b6(12)
        assert len(rota.amostra_de_confirmacoes(regs)) == 10
        sem = conferencia(regs)
        del sem["confirmacoes"]
        with pytest.raises(rota.EvidenciaInvalida, match="confirmacoes"):
            rota.validar_conferencia(sem, regs, "x" * 64)
        faltando = conferencia(regs)
        faltando["confirmacoes"].pop(next(iter(faltando["confirmacoes"])))
        with pytest.raises(rota.EvidenciaInvalida, match="sem conferência"):
            rota.validar_conferencia(faltando, regs, "x" * 64)
        with pytest.raises(rota.EvidenciaInvalida, match="recusou"):
            rota.validar_conferencia(conferencia(regs, confirmacoes="recusada"), regs, "x" * 64)

    def test_amostra_e_recalculavel_e_nao_depende_da_ordem(self):
        regs = pares_que_passam_no_b6(12)
        embaralhados = list(regs)
        random.Random(3).shuffle(embaralhados)
        assert rota.amostra_de_confirmacoes(regs) == rota.amostra_de_confirmacoes(embaralhados)


class TestVereditosPorConta:
    """Achado M4: a função que dá os decididos ao executor não tinha teste."""

    def _pasta(self, tmp_path, regs, conf=None):
        texto = "".join(json.dumps(r, sort_keys=True) + "\n" for r in regs)
        (tmp_path / "evidencias.jsonl").write_text(texto, encoding="utf-8")
        sha = hashlib.sha256(texto.encode()).hexdigest()
        (tmp_path / "conferencia.json").write_text(
            json.dumps(conf if conf is not None else conferencia(regs, sha=sha)), encoding="utf-8")
        return tmp_path

    @pytest.fixture(autouse=True)
    def _sem_marcas(self, monkeypatch):
        monkeypatch.setattr(rota, "documentos_geom1", lambda: frozenset())
        monkeypatch.setattr(rota, "controles", lambda: {})

    def test_prova_de_saldo_nao_decide_o_fco(self, tmp_path):
        regs = pares_que_passam_no_b6() + [registro(conta="1"), registro(conta="1.01.01")]
        v = rota.vereditos_por_conta(self._pasta(tmp_path, regs))
        assert CHAVE in v["ativo"] and CHAVE not in v["fco"]

    def test_cadeia_decide_o_fco_com_a_escala(self, tmp_path):
        regs = pares_que_passam_no_b6() + [registro(conta="1"), registro(conta="1.01.01"),
                                           registro(conta="6.01")]
        v = rota.vereditos_por_conta(self._pasta(tmp_path, regs))
        assert CHAVE in v["fco"] and v["escalas"][(CHAVE, "fco")] == "MIL"

    def test_parada_b7_levanta(self, tmp_path, monkeypatch):
        chave = ("003549", "itr", "2019-09-30", 1)
        monkeypatch.setattr(rota, "controles", lambda: {chave: "777777"})
        regs = pares_que_passam_no_b6() + [registro("777777", "1", papeis=("controle",),
                                                    dt_refer="2019-09-30")]
        with pytest.raises(rota.EvidenciaInvalida, match="parada"):
            rota.vereditos_por_conta(self._pasta(tmp_path, regs))

    def test_conferencia_ausente_ou_recusada_levanta(self, tmp_path):
        regs = pares_que_passam_no_b6() + [registro(conta="1")]
        with pytest.raises(rota.EvidenciaInvalida):
            rota.vereditos_por_conta(self._pasta(tmp_path, regs, {"regra": rota.REGRA}))
        texto = "".join(json.dumps(r, sort_keys=True) + "\n" for r in regs)
        sha = hashlib.sha256(texto.encode()).hexdigest()
        with pytest.raises(rota.EvidenciaInvalida, match="recusou"):
            rota.vereditos_por_conta(self._pasta(tmp_path, regs,
                                                 conferencia(regs, sha=sha, resultado="recusada")))


class TestDocumentoInteiro:
    def _doc(self, **mudar):
        doc = {"cd_cvm": "003549", "conjunto": "itr", "dt_refer": "2020-09-30", "versao": 1,
               "id_doc": "123", "sha256_pacote": "a" * 64, "papeis": ["T_A"], "desenho": False,
               "geom1": False, "escala_declarada": "UNIDADE", "sem_pacote": False,
               "csv": {"1": 1935800.0, "1.01.01": 3600.0}}
        doc.update(mudar)
        return doc

    def test_documento_sem_pacote_vira_tres_indecisoes(self):
        doc = self._doc(sem_pacote=True, id_doc="1", sha256_pacote=None)
        regs = rota.adjudicar_saldos(doc) + [rota.adjudicar_fco(doc, None, None)]
        assert [r["conta"] for r in regs] == ["1", "1.01.01", "6.01"]
        assert {r["motivo"] for r in regs} == {"sem_pacote"}
        for r in regs:
            rota.validar_registro(r)

    def test_ponta_a_ponta_com_elo_e_cadeia_sem_valor_de_6_no_registro(self, tmp_path, monkeypatch):
        """Ativo provado por célula, caixa pelo elo, FCO pela cadeia — e nenhum número
        das contas 6.x no registro nem no resumo, em nenhuma forma (O1)."""
        pagina = ("Demonstrações financeiras (Em milhares de reais)\n"
                  "Total do Ativo     1.935.800     1.957.200\n")
        _pacote(tmp_path, _xml_itr(_bpa(), _dfc()), "123.zip")
        monkeypatch.setattr(rota.rad, "BRUTOS", tmp_path)
        monkeypatch.setattr(rota, "ler_anexos", lambda c: [anexo(pagina)])
        doc = self._doc()
        saldos = rota.adjudicar_saldos(doc)
        fco = rota.adjudicar_fco(doc, saldos[1], _csv())
        regs = saldos + [fco]
        por_conta = {r["conta"]: r for r in regs}
        assert por_conta["1"]["veredito"] == "corrigida"
        assert por_conta["1.01.01"]["prova"] == "elo_balanco"
        assert por_conta["6.01"]["veredito"] == "corrigida"
        texto = json.dumps(regs, ensure_ascii=False) + json.dumps(
            rota.resumir(regs, {"b6": {}, "controles_corrigidos": [], "parada": False}))
        # As formas com quatro dígitos ou mais; a ÷1.000 de um fluxo pequeno ("20")
        # coincide com qualquer data, e os trechos já não têm dígito nenhum.
        for valor in (150000, 20000, 166000, 4000, 7600):
            for forma in (f"{valor}", f"{valor:,}".replace(",", ".")):
                assert forma not in texto, f"número de conta 6.x ({forma}) no que se publica"
        for r in regs:
            rota.validar_registro(r)

    def test_sem_ancora_do_caixa_a_conta_6_nem_e_lida(self, monkeypatch):
        chamadas = []
        monkeypatch.setattr(rota, "cadeia_dfc", lambda *a: chamadas.append(a) or {})
        r = rota.adjudicar_fco(self._doc(), registro("123", "1.01.01", None), None)
        assert chamadas == []
        assert r["motivo"] == "sem_ancora_do_caixa"
        assert set(r["cadeia"].values()) == {None, rota.id_prova("123", "1.01.01")}

    def test_erro_de_um_documento_nao_derruba_a_execucao(self, tmp_path, monkeypatch):
        """Achado B8: o erro vira indecisão do documento, com o tipo e sem a mensagem."""
        monkeypatch.setattr(rota.rad, "BRUTOS", tmp_path)
        (tmp_path / "123.zip").write_bytes(b"isto nao e um zip")
        regs = rota.adjudicar_saldos(self._doc())
        assert {r["motivo"].split(":")[0] for r in regs} == {"leitura"}
        for r in regs:
            rota.validar_registro(r)


class TestConjunto:
    def _linha(self, cd, tri, valor, escala, dt_refer, conj="itr"):
        return {"cd_cvm": cd, "trimestre": tri, "valor_reais": valor, "escala_declarada": escala,
                "estado": "valido", "conjunto": conj, "dt_refer": dt_refer, "versao": 1,
                "plano_contas": "ll3_11_x"}

    def test_trecho_minoritario_e_as_pontas_dos_saltos(self):
        ativo = [self._linha("A", "1T2020", 1e9, "MIL", "2020-03-31"),
                 self._linha("A", "2T2020", 1e6, "UNIDADE", "2020-06-30"),
                 self._linha("A", "3T2020", 1e9, "MIL", "2020-09-30"),
                 self._linha("A", "4T2020", 1e9, "MIL", "2020-12-31", "dfp")]
        painel = rota.pp.Painel(ativo, [], [], {}, {})
        alvos = rota.conjunto_alvo(painel)
        assert alvos[("A", "itr", "2020-06-30", 1)] == {"T_A", "T_B"}
        assert alvos[("A", "itr", "2020-03-31", 1)] == {"T_B"}
        assert ("A", "dfp", "2020-12-31", 1) not in alvos

    def test_seguradora_fica_fora_do_conjunto(self):
        ativo = [dict(self._linha("S", "1T2020", 1e9, "MIL", "2020-03-31"), plano_contas="ll3_13_x"),
                 dict(self._linha("S", "2T2020", 1e6, "UNIDADE", "2020-06-30"), plano_contas="ll3_13_x")]
        assert rota.conjunto_alvo(rota.pp.Painel(ativo, [], [], {}, {})) == {}


class TestReconferenciaN1:
    """Reconferência de 27/09, achado N1 — as formas em que uma tabela em reais
    ainda passava como milhares. Falso veto é aceitável; falsa prova, não."""

    CAPA = "Notas explicativas às informações trimestrais\n(Valores expressos em milhares de reais)\n"

    @pytest.mark.parametrize("quebrada", [
        "Balanço patrimonial (Valores expressos em\nreais)",
        "(Em\nreais)",
        "Balanço (Valores\nem R$)"])
    def test_declaracao_quebrada_entre_duas_linhas_veta(self, quebrada):
        pagina = f"{quebrada}\nTotal do ativo   19.358   19.572\n"
        r = provar(formulario(), anexo(self.CAPA, pagina))
        assert r["escala_do_formulario"] is None

    def test_declaracao_quebrada_na_apresentacao_torna_o_anexo_misto(self):
        capa = self.CAPA + "Balanço patrimonial (Valores expressos em\nreais)\n"
        assert rota.apresentacao_do_anexo([capa]) == "misto"

    @pytest.mark.parametrize("cabecalho", ["                 R$              R$",
                                           "Balanço (Reais)", "Valores (R$)"])
    def test_simbolo_ou_reais_sozinho_como_cabecalho_veta(self, cabecalho):
        pagina = f"(Em milhares de reais)\n{cabecalho}\nTotal do ativo   19.358   19.572\n"
        assert provar(formulario(), anexo(pagina))["escala_do_formulario"] is None

    def test_dois_cabecalhos_lado_a_lado_vetam(self):
        pagina = ("(Em reais)                    Em milhares de reais, exceto lucro por ação\n"
                  "Total do ativo   19.358   19.572\n")
        assert provar(formulario(), anexo(pagina))["escala_do_formulario"] is None

    def test_simbolo_como_moeda_da_propria_declaracao_de_milhares_vale(self):
        pagina = ("(Valores expressos em milhares de reais – R$, exceto quando indicado)\n"
                  "Total do ativo   19.358   19.572\n")
        assert provar(formulario(), anexo(pagina))["escala_do_formulario"] == "MIL"

    def test_valor_em_reais_no_texto_nao_e_unidade(self):
        assert rota.classificar_unidade("pagou r$ 1.234 em dividendos") is None

    def test_trecho_de_unidade_publicado_guarda_as_colunas(self):
        assert rota.segmentos_publicaveis("(Em reais)      (Em milhares de reais)") == \
            "(Em reais) | (Em milhares de reais)"
        assert rota.classificar_trecho("(Em reais) | (Em milhares de reais)") == "OUTRA"

    def test_veto_da_pagina_depois_do_titulo_e_sem_objeto_ainda_vale(self):
        """Reconferência T1: o veto da PÁGINA (não o da apresentação) tem de valer."""
        pagina = ("x" * 400 + "\n" + "Total do ativo   19.358   19.572\n"
                  + "Quadro auxiliar — valores em reais\n")
        r = provar(formulario(), anexo(self.CAPA, pagina))
        assert r["escala_do_formulario"] is None and r["motivo"] == "sem_unidade_de_milhares"


class TestReconferenciaBaixas:
    def test_validar_arquivo_confere_as_marcas(self):
        """T1: marca adulterada é recusada por `validar_arquivo`, não só pela função."""
        regs = pares_que_passam_no_b6() + [registro("98282", "1")]
        with pytest.raises(rota.EvidenciaInvalida, match="adulterada"):
            rota.validar_arquivo(regs, geom1=frozenset({"98282"}), chaves_de_controle=set())

    def test_controle_ausente_das_evidencias_e_recusado(self):
        """B-d: os 30 controles têm de estar nas evidências."""
        with pytest.raises(rota.EvidenciaInvalida, match="controles ausentes"):
            rota.validar_arquivo(pares_que_passam_no_b6(), frozenset(),
                                 {("009999", "itr", "2019-03-31", 1)})

    def test_erro_de_logica_derruba_e_nao_vira_indecisao(self, tmp_path, monkeypatch):
        """B-c: só erro de LEITURA vira indecisão."""
        _pacote(tmp_path, _xml_itr(_bpa(), _dfc()), "123.zip")
        monkeypatch.setattr(rota.rad, "BRUTOS", tmp_path)
        monkeypatch.setattr(rota, "ler_anexos", lambda c: [])

        def quebrada(*a, **k):
            raise ZeroDivisionError("defeito da regra")
        monkeypatch.setattr(rota, "provar_celula", quebrada)
        doc = TestDocumentoInteiro()._doc()
        with pytest.raises(ZeroDivisionError):
            rota.adjudicar_saldos(doc)


class TestVerificacaoCurta:
    def test_trecho_de_unidade_com_valor_em_reais_passa_no_consumidor(self):
        """N2: "Capital R$ 1.000" ao lado da declaração de milhares. O produtor decide
        MIL; o consumidor, sobre o trecho mascarado, tem de concordar."""
        pagina = ("(Em milhares de reais)        Capital R$ 1.000\n"
                  "Total do ativo   19.358   19.572\n")
        r = provar(formulario(), anexo(pagina))
        assert r["escala_do_formulario"] == "MIL"
        rota.validar_registro(rota.registro(
            {"cd_cvm": "003549", "conjunto": "itr", "dt_refer": "2020-09-30", "versao": 1,
             "id_doc": DOC, "sha256_pacote": "a" * 64, "papeis": ["T_A"], "desenho": False,
             "geom1": False, "escala_declarada": "UNIDADE"},
            "1", "celula_propria", r.pop("escala_do_formulario"), r.pop("motivo"), **r))

    def test_erro_de_logica_na_cadeia_derruba(self, tmp_path, monkeypatch):
        """B-c: só a leitura da cadeia vira identidade não fechada."""
        caminho = _pacote(tmp_path, _xml_itr(_bpa(), _dfc()))

        def quebrada(*a, **k):
            raise ZeroDivisionError
        monkeypatch.setattr(rota, "_decimal_ptbr", quebrada)
        with pytest.raises(ZeroDivisionError):
            rota.cadeia_dfc(caminho, PERIODO, _csv(), CHAVE)


class TestRota2:
    """ROTA-2 (27/09): a conferência B8 da ROTA-1 recusou 60719 — a unidade da
    página de prova não estava demonstrada; a regra tinha tomado legendas "(R$ mil)"
    de OUTRAS tabelas, no topo das páginas, como declaração de apresentação."""

    def test_caso_60719_comentario_com_legendas_de_outras_tabelas_nao_prova(self):
        legenda = "Receita líquida (R$ mil)\nReceita   1.234   1.111\n"
        pagina_da_prova = "Balanço patrimonial resumido\nTotal do ativo   19.358   19.572\n"
        r = provar(formulario(), anexo(legenda, legenda, pagina_da_prova, grupo="192"))
        assert r["escala_do_formulario"] is None and r["motivo"] == "sem_unidade_de_milhares"

    def test_legenda_no_topo_das_notas_sem_objeto_nao_e_apresentacao(self):
        assert rota.apresentacao_do_anexo(["Receita líquida (R$ mil)\nx\n"], "193") is None
        assert rota.apresentacao_do_anexo(
            ["Notas explicativas às informações trimestrais\n(Em milhares de reais)\n"], "193") == "MIL"

    @pytest.mark.parametrize("grupo", ["192", "1653", "194"])
    def test_so_notas_e_demonstracoes_tem_apresentacao(self, grupo):
        capa = "Notas explicativas às informações trimestrais\n(Valores expressos em milhares de reais)\n"
        assert rota.apresentacao_do_anexo([capa], grupo) is None
        pagina = "Total do ativo   19.358   19.572\n"
        assert provar(formulario(), anexo(capa, pagina, grupo=grupo))["escala_do_formulario"] is None

    def test_cabecalho_local_continua_valendo_no_comentario(self):
        pagina = "Balanço (Em milhares de reais)\nTotal do ativo   19.358   19.572\n"
        assert provar(formulario(), anexo(pagina, grupo="192"))["escala_do_formulario"] == "MIL"

    def test_veto_no_titulo_continua_contando(self):
        capa = ("(Em reais)\nNotas explicativas às informações trimestrais\n"
                "(Valores expressos em milhares de reais)\n")
        assert rota.apresentacao_do_anexo([capa], "193") == "misto"

    def test_codigos_de_escala_do_pacote_sao_so_informacao(self, tmp_path):
        caminho = _pacote(tmp_path, _xml_itr(_bpa(), _dfc()))
        assert rota.escalas_do_pacote(caminho) == {"envelope": None, "formulario": "1"}


class TestRota2Consumidor:
    def test_apresentacao_fora_de_notas_e_demonstracoes_e_recusada_no_consumidor(self):
        r = registro()
        r["linhas"][0]["grupo"] = "192"
        with pytest.raises(rota.EvidenciaInvalida):
            rota.validar_registro(r)
        r["linhas"][0]["grupo"] = "412"
        rota.validar_registro(r)
