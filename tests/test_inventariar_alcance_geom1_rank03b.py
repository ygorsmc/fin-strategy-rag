"""Inventário lexical não é decisão contábil; trechos não expõem valores/sinais."""
import sys
import unicodedata

import pytest

from scripts.inventariar_alcance_geom1_rank03b import (classe_de_moedas, classe_de_sinais, inventariar_texto,
                                                       mascarar, trecho_publicavel)


@pytest.mark.parametrize("celula", ["123.456", "(123.456)", "-123.456", "−123.456", "+123.456", "123.456,78",
                                  "–123", "—123", "123-", "-(123)", "- (123)", "(123)-", "123−"])
def test_mascara_valor_e_sinal(celula):
    assert mascarar("FCO " + celula) == "FCO [valor omitido]"


@pytest.mark.parametrize("termo,tipo", [("ATIVO TOTAL", "ativo_total"),
                                     ("Total do Ativo", "ativo_total"),
                                     ("Ativos totais", "ativo_total"),
                                     ("Atividades operacionais", "atividades_operacionais"),
                                     ("Demonstração dos fluxos de caixa", "mencao_dfc")])
def test_mencoes_mascaradas_sem_adjudicar(termo, tipo):
    r = inventariar_texto("(Em milhares de reais)\n" + termo + " (123.456)\f")
    assert len(r) == 1 and r[0]["pagina"] == 1
    assert r[0]["declaracoes_de_unidade"]
    assert r[0]["mencoes"][0]["tipo"] == tipo
    assert "123" not in str(r)
    assert "veredito" not in r[0]


def test_mencao_nao_garante_conta():
    r = inventariar_texto("Máquinas para atividades operacionais da empresa\fOutra página\f")
    assert len(r) == 2
    assert r[0]["mencoes"][0]["tipo"] == "atividades_operacionais"
    assert not r[1]["mencoes"]
    assert "escala" not in r[0]


def test_pagina_vazia_interna_nao_desaparece():
    assert [p["pagina"] for p in inventariar_texto("A\f\fB\f")] == [1, 2, 3]


# --- R4 (revisão de 24/09): sinal é classe, e linha de fluxo não publica trecho ---

# Expectativa construída SEM a implementação: toda a categoria Pd do Unicode
# mais os sinais de menos/mais/parêntese que não são Pd. Se a classe da máscara
# perder um deles, o caso correspondente falha.
_TRACOS_PD = [c for c in map(chr, range(sys.maxunicode + 1)) if unicodedata.category(c) == "Pd"]
_OUTROS_SINAIS = ["−", "⁻", "₋", "➖", "˗", "﹢", "＋",
                  "（", "）", "﹙", "﹚", "⁽", "⁾"]


@pytest.mark.parametrize("sinal", _TRACOS_PD + _OUTROS_SINAIS,
                         ids=lambda c: f"U+{ord(c):04X}")
def test_todo_traco_ou_menos_colado_ao_numero_sai_com_ele(sinal):
    assert mascarar(f"FCO {sinal}123.456") == "FCO [valor omitido]"
    assert mascarar(f"FCO 123.456{sinal}") == "FCO [valor omitido]"


@pytest.mark.parametrize("celula", ["(R$ 123.456)", "R$ (123.456)", "US$ -123.456", "( 123 )",
                                  "（123）", "﹙R$ 1.234﹚", "R$1,5"])
def test_moeda_dentro_do_numero_nao_deixa_parentese(celula):
    assert mascarar("FCO " + celula) == "FCO [valor omitido]"


def test_classe_nao_contem_letra_nem_digito():
    assert classe_de_sinais()
    assert not [c for c in classe_de_sinais() if unicodedata.category(c)[0] in "LN"]


@pytest.mark.parametrize("texto", ["em R$ milhões", "Total do ativo", "caixa - equivalentes"])
def test_texto_sem_numero_permanece(texto):
    """Controle: a classe não apaga texto que não tem número."""
    assert mascarar(texto) == texto


@pytest.mark.parametrize("linha", ["Caixa líquido aplicado nas atividades operacionais (123.456)",
                                   "O fluxo de caixa operacional foi negativo em 123.456",
                                   "Caixa gerado nas atividades operacionais"])
def test_linha_de_fluxo_nao_publica_trecho(linha):
    r = inventariar_texto(linha + "\f")
    assert r[0]["mencoes"]
    for m in r[0]["mencoes"]:
        assert "trecho" not in m and m["trecho_omitido"] == "linha_de_fluxo"
    for palavra in ("aplicado", "negativo", "gerado", "123"):
        assert palavra not in str(r)


def test_restricao_e_da_linha_nao_do_tipo():
    """Linha com ativo total E fluxo: nenhuma menção dela publica trecho."""
    r = inventariar_texto("Total do ativo e fluxos de caixa aplicados (123)\f")
    assert {m["tipo"] for m in r[0]["mencoes"]} == {"ativo_total", "mencao_dfc"}
    assert all("trecho" not in m for m in r[0]["mencoes"])
    assert "aplicados" not in str(r)


def test_declaracao_de_unidade_em_linha_de_fluxo_nao_publica_trecho():
    r = inventariar_texto("Fluxo de caixa consumido (em milhares de reais)\f")
    assert r[0]["declaracoes_de_unidade"] == [{"linha": 1, "trecho_omitido": "linha_de_fluxo"}]
    assert "consumido" not in str(r)


def test_linha_sem_fluxo_continua_com_trecho_mascarado():
    """Controle positivo: fora de fluxo o trecho segue publicado, sem dígitos."""
    r = inventariar_texto("(Em milhares de reais)\nTotal do ativo (123.456)\f")
    assert r[0]["mencoes"] == [{"tipo": "ativo_total", "linha": 2,
                                "trecho": "Total do ativo [valor omitido]"}]
    assert r[0]["declaracoes_de_unidade"][0]["trecho"] == "(Em milhares de reais)"


# --- Adendo de 25/09 (B1): moeda é classe, parêntese órfão sai, vocabulário de caixa ---

_MOEDAS_SC = [c for c in map(chr, range(sys.maxunicode + 1)) if unicodedata.category(c) == "Sc"]


def test_classe_de_moedas_e_a_categoria_sc_inteira():
    assert set(classe_de_moedas()) == set(_MOEDAS_SC)


@pytest.mark.parametrize("moeda", _MOEDAS_SC, ids=lambda c: f"U+{ord(c):04X}")
def test_menos_antes_de_qualquer_simbolo_de_moeda_sai_com_o_numero(moeda):
    assert mascarar(f"FCO \u2212{moeda} 123") == "FCO [valor omitido]"
    assert mascarar(f"FCO ({moeda} 1.234,5)") == "FCO [valor omitido]"


@pytest.mark.parametrize("celula", ["(USD 123)", "\u2212USD 123", "- BRL 1.000", "EUR (1.234)", "(US$ 12)"])
def test_codigo_iso_4217_colado_ao_numero_sai_com_ele(celula):
    assert mascarar("FCO " + celula) == "FCO [valor omitido]"


@pytest.mark.parametrize("texto,esperado", [("CDI 100%", "CDI [valor omitido] %"),
                                            ("IPCA 4,5", "IPCA [valor omitido]"),
                                            ("FCO 123", "FCO [valor omitido]")])
def test_sigla_que_nao_e_moeda_permanece(texto, esperado):
    """Controle: três maiúsculas não bastam — só a lista ISO 4217 é moeda."""
    assert mascarar(texto) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("FCO (R$ 1,2 milhão)", "FCO [valor omitido] milhão"),
    ("FCO (queda de R$ 5 mil)", "FCO queda de [valor omitido] mil"),
])
def test_parentese_orfao_sai_quando_ha_numero(texto, esperado):
    assert mascarar(texto) == esperado


@pytest.mark.parametrize("linha", ["Geração de caixa operacional negativa (em milhares de reais)",
                                   "Resultado positivo de 123", "Consumo de 1.234 no período",
                                   "Déficit de 12"])
def test_vocabulario_de_caixa_ou_polaridade_nao_publica_trecho(linha):
    assert trecho_publicavel(linha) == {"trecho_omitido": "vocabulario_de_caixa"}


def test_declaracao_de_unidade_com_polaridade_nao_publica_trecho():
    r = inventariar_texto("Geração de caixa operacional negativa (em milhares de reais)\f")
    assert r[0]["declaracoes_de_unidade"] == [{"linha": 1, "trecho_omitido": "vocabulario_de_caixa"}]
    assert "negativa" not in str(r)
