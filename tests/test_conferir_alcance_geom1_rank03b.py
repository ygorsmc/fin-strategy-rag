"""Revisão do alcance GEOM-1 (R3): busca exata sem publicar valor nem sinal de FCO."""
from datetime import date
from decimal import Decimal
import hashlib
import json
import re
import sys
from types import SimpleNamespace
import unicodedata
import xml.etree.ElementTree as ET

import pytest

from scripts import conferir_alcance_geom1_rank03b as c
from scripts.inventariar_alcance_geom1_rank03b import inventariar_texto


@pytest.mark.parametrize("texto,esperado", [("1.234.567", 1234567), ("-99.999", -99999),
                                            ("9,5", Decimal("9.5")), ("0", 0), ("123", 123),
                                            ("-1.234,56", Decimal("-1234.56"))])
def test_numero_do_xml_em_ptbr(texto, esperado):
    assert c.decimal_ptbr(texto) == esperado


@pytest.mark.parametrize("texto", ["98.765.43x", "", "1.23", "12.3456", None, "--5"])
def test_numero_invalido_derruba_sem_repetir_o_valor(texto):
    with pytest.raises(ValueError) as erro:
        c.decimal_ptbr(texto)
    assert not any(ch.isdigit() for ch in str(erro.value))


def _tokens(linha):
    return [(t.coluna, t.modulo, t.sinal) for t in c.tokens_da_linha(linha)]


def test_tokens_da_linha_sinal_colado_vale_e_sinal_separado_e_ambiguo():
    """**Substitui, declaradamente, `test_numeros_da_linha_com_sinal_por_parenteses_e_por_traco_unicode`**
    (24/09), que fixava `− 1.000` → −1.000 e `‐ 5` → −5: sinal separado do
    número por um espaço. No `-raw`, o traço de "sem valor" de uma coluna
    seguido do valor da coluna seguinte aparece exatamente assim, e ler como
    negativo apagaria um ativo positivo sem sinal nenhum. Pelo contrato da
    correção RAG (C2), passa a ambíguo (`None`). A mesma linha continua
    verificada inteira, e o sinal colado segue negativo — inclusive com os
    mesmos dois caracteres."""
    linha = "Total dos ativos 123.456 (7.890) − 1.000 ‐ 5 +12 2.345.678,5"
    assert _tokens(linha) == [(1, 123456, 1), (2, 7890, -1), (3, 1000, None), (4, 5, None), (5, 12, 1),
                              (6, Decimal("2345678.5"), 1)]
    assert _tokens("Total −1.000 ‐5") == [(1, 1000, -1), (2, 5, -1)]


def test_valor_em_outra_coluna_e_localizado_na_coluna_certa():
    paginas = ["Cabeçalho\nTotal 111.111 222.222 333.333\n", "Outra 333.333"]
    achados = c.ocorrencias(paginas, {"alvo": Decimal(333333)}, por_modulo=False)["alvo"]
    assert [(a["pagina"], a["linha"], a["coluna"], a["tokens"]) for a in achados] == [(1, 2, 3, 3), (2, 1, 1, 1)]


def test_com_sinal_parenteses_nao_casa_positivo_mas_por_modulo_casa():
    paginas = ["Linha (7.890)"]
    assert c.ocorrencias(paginas, {"a": Decimal(7890)}, por_modulo=False)["a"] == []
    assert len(c.ocorrencias(paginas, {"a": Decimal(7890)}, por_modulo=True)["a"]) == 1


def test_zero_nunca_e_procurado():
    assert c.ocorrencias(["0 0,0 (0)"], {"zero": Decimal(0)}, por_modulo=True) == {"zero": []}


def test_fco_publica_so_paginas():
    achados = c.ocorrencias(["x\nCaixa aplicado (1.234.567)", "1.234.567"], {"f": Decimal(-1234567)},
                            por_modulo=True)
    publicado = c.publicar_fco(achados)
    assert publicado == {"f": [1, 2]}
    assert "aplicado" not in str(publicado) and "1.234" not in str(publicado)


def test_ativo_publica_posicao_e_trecho_mascarado():
    achados = c.ocorrencias(["Total dos ativos 1.234.567"], {"a": Decimal(1234567)}, por_modulo=False)
    assert c.publicar_ativo(achados) == {"a": [{"pagina": 1, "linha": 1, "coluna": 1, "tokens": 1,
                                                "trecho": "Total dos ativos [valor omitido]"}]}


@pytest.mark.parametrize("saida", [
    {"trecho": "Total 1.234.567"},
    {"trecho": "Total 12"},
    {"x": {"y": [1234567]}},
    {"nota": "o valor era 1234567 em junho"},
    {"nota": "o valor era 1.234.567,5"},
    {"lista": [{"campo": Decimal("1234.5")}]},
])
def test_autoverificacao_recusa_valor_publicado(saida):
    with pytest.raises(c.VazamentoDeValor) as erro:
        c.verificar_sem_valores(saida, [Decimal("-1234567"), Decimal("1234567.5")])
    assert "1234" not in str(erro.value) and "1.234" not in str(erro.value)


def test_autoverificacao_isenta_hash_e_data_pela_forma():
    """**Substitui, declaradamente, `test_autoverificacao_isenta_so_hash_e_data`** (25/09),
    que por sua vez substituíra `test_autoverificacao_aceita_identidade_e_numeros_pequenos`
    (24/09). A versão de 25/09 usava hashes falsos — `"1234567"` sob
    `codigo_sha256` — e `"1234567"` sob `dt_refer`, isentos só pelo nome do
    campo. Pelo contrato da correção RAG (C3), a isenção é pela forma: hash de
    verdade (64 hexadecimais) e data de verdade (`AAAA-MM-DD`). Os falsos viraram
    contraprova em `test_isencao_nao_cobre_o_que_nao_tem_a_forma`. Hash, data,
    números pequenos e trecho mascarado continuam aceitos."""
    hash_com_valor = "a1234567" * 8
    saida = {"pdf_sha256": hash_com_valor, "codigo_sha256": {"a.py": "b1234567" * 8},
             "fontes": [{"id_doc": "12", "sha256": "c1234567" * 8, "dt_refer": "2024-06-30"}],
             "data": "2026-09-24", "pagina": 42, "coluna": 5, "ok": True, "vazio": None,
             "trecho": "Total dos ativos [valor omitido]", "limite": "sem número"}
    c.verificar_sem_valores(saida, [Decimal("1234567"), Decimal("140867"), Decimal(2024), Decimal(2026)])
    # O mesmo hash fora de campo de hash é varrido: a isenção é que o protegia.
    with pytest.raises(c.VazamentoDeValor):
        c.verificar_sem_valores({"nota": hash_com_valor}, [Decimal("1234567")])


@pytest.mark.parametrize("saida", [{"id_doc": "1234567"}, {"nome_xml": "x1234567.xml"},
                                   {"contrato": "resultados/1.234.567.md"}])
def test_identidade_de_documento_nao_e_isenta(saida):
    with pytest.raises(c.VazamentoDeValor):
        c.verificar_sem_valores(saida, [Decimal("1234567")])


@pytest.mark.parametrize("saida", [{"1234567": True}, {"total 1.234.567": []},
                                   {"nota": "1 234 567"}, {"nota": "1\u00a0234\u00a0567"},
                                   {"nota": "1,234,567"}, {"nota": "1\u202f234\u202f567"}])
def test_autoverificacao_varre_chaves_e_milhar_com_espaco(saida):
    with pytest.raises(c.VazamentoDeValor):
        c.verificar_sem_valores(saida, [Decimal("-1234567")])


def test_valor_abaixo_de_mil_nao_bloqueia_metadado():
    """Página 42 não pode ser confundida com um valor comparado de módulo < 1.000."""
    c.verificar_sem_valores({"pagina": 42}, [Decimal(42)])


def test_fonte_com_hash_divergente_derruba(tmp_path):
    (tmp_path / "1.zip").write_bytes(b"conteudo")
    certo = hashlib.sha256(b"conteudo").hexdigest()
    c.conferir_fontes([{"id_doc": "1", "sha256": certo}], tmp_path)
    with pytest.raises(AssertionError, match="fonte diferente"):
        c.conferir_fontes([{"id_doc": "1", "sha256": "0" * 64}], tmp_path)


@pytest.mark.parametrize("existente", ["pin_revisao.json", "conferencia_revisao.json"])
def test_destino_existente_recusa_antes_de_ler_qualquer_fonte(tmp_path, monkeypatch, existente):
    (tmp_path / existente).write_text("{}")
    monkeypatch.setattr(c, "BASE", tmp_path / "inexistente")  # qualquer leitura falharia de outro jeito
    with pytest.raises(FileExistsError):
        c.executar(tmp_path)


def _pagina(mencoes, unidades=()):
    return {"pagina": 1, "declaracoes_de_unidade": list(unidades), "mencoes": list(mencoes)}


def test_reinventario_so_admite_retirar_trecho_de_fluxo():
    antigo = [_pagina([{"tipo": "mencao_dfc", "linha": 3, "trecho": "hedge de fluxo de caixa"},
                       {"tipo": "ativo_total", "linha": 9, "trecho": "Total do ativo [valor omitido]"}])]
    novo = [_pagina([{"tipo": "mencao_dfc", "linha": 3, "trecho_omitido": "linha_de_fluxo"},
                     {"tipo": "ativo_total", "linha": 9, "trecho": "Total do ativo [valor omitido]"}])]
    assert c.comparar_inventarios(antigo, novo) == {
        "registros_comparados": 2, "trechos_retirados_por_fluxo": 1, "diferencas_inesperadas": 0}


@pytest.mark.parametrize("novo", [
    [_pagina([{"tipo": "ativo_total", "linha": 9, "trecho": "outro texto"}])],
    [_pagina([{"tipo": "ativo_total", "linha": 9, "trecho_omitido": "linha_de_fluxo"}])],
    [_pagina([])],
    [{**_pagina([]), "pagina": 2}],
])
def test_reinventario_acusa_qualquer_outra_diferenca(novo):
    antigo = [_pagina([{"tipo": "ativo_total", "linha": 9, "trecho": "Total do ativo [valor omitido]"}])]
    assert c.comparar_inventarios(antigo, novo)["diferencas_inesperadas"] >= 1


# --- Adendo de 25/09 (B1/B2): política de trecho na busca e guardas sem contraprova ---

def test_ativo_em_linha_de_fluxo_ou_polaridade_nao_publica_trecho():
    achados = c.ocorrencias(["Caixa líquido aplicado nas atividades operacionais 1.234.567",
                             "Resultado negativo de 1.234.567"], {"a": Decimal(1234567)}, por_modulo=False)
    publicado = c.publicar_ativo(achados)["a"]
    assert [a.get("trecho_omitido") for a in publicado] == ["linha_de_fluxo", "vocabulario_de_caixa"]
    assert "aplicado" not in str(publicado) and "negativo" not in str(publicado)


def _formulario(*contas):
    corpo = "".join(f"<Conta><CodigoConta>{cod}</CodigoConta>{campos}</Conta>" for cod, campos in contas)
    return ET.fromstring(f"<Formulario><DfConsolidadas><BalancoPatrimonialAtivo>{corpo}"
                         "</BalancoPatrimonialAtivo></DfConsolidadas></Formulario>")


def test_valor_xml_le_a_conta_unica():
    form = _formulario(("1", "<TrimestreAtual>1.234</TrimestreAtual>"), ("1.01", "<TrimestreAtual>9</TrimestreAtual>"))
    assert c.valor_xml(form, c.CONS, c.BP, "1", "TrimestreAtual") == 1234


@pytest.mark.parametrize("contas,campo", [
    ((("1", "<TrimestreAtual>1</TrimestreAtual>"), ("1", "<TrimestreAtual>2</TrimestreAtual>")), "TrimestreAtual"),
    ((("1.01", "<TrimestreAtual>1</TrimestreAtual>"),), "TrimestreAtual"),
    ((("1", "<ExercicioAnterior>1</ExercicioAnterior>"),), "TrimestreAtual"),
    ((("1", "<TrimestreAtual></TrimestreAtual>"),), "TrimestreAtual"),
])
def test_conta_duplicada_ausente_ou_sem_campo_derruba(contas, campo):
    with pytest.raises(ValueError):
        c.valor_xml(_formulario(*contas), c.CONS, c.BP, "1", campo)


def test_paginacao_divergente_derruba(monkeypatch):
    class Feito:
        def __init__(self, stdout=b"", stderr=b""):
            self.stdout, self.stderr = stdout, stderr

    def falso(args, **_):
        return Feito(b"Pages:          2\n") if args[0] == "pdfinfo" else Feito("A\fB\fC\f".encode())

    monkeypatch.setattr(c.subprocess, "run", falso)
    with pytest.raises(AssertionError, match="paginação"):
        c.paginas_pdf(b"%PDF", "-layout")


@pytest.mark.parametrize("pagina", ["Total (cid:12)(cid:7) 1.234", "Total \ufffd\ufffd 1.234"])
def test_texto_ilegivel_derruba_sem_publicar_o_texto(pagina):
    with pytest.raises(AssertionError) as erro:
        c.exigir_texto_legivel(["Página boa " * 5, pagina])
    assert "[2]" in str(erro.value) and "1.234" not in str(erro.value)


def test_pagina_com_pouco_texto_e_publicada():
    assert c.paginas_com_pouco_texto(["x" * 60, "   \n  ", "curta"]) == [2, 3]


def test_modos_so_concordam_com_mesmas_paginas_e_colunas():
    base = {"ativo": {"a": [{"pagina": 42, "coluna": 5}]}, "fco_paginas": {"f": []}}
    outra_coluna = {"ativo": {"a": [{"pagina": 42, "coluna": 4}]}, "fco_paginas": {"f": []}}
    outra_pagina_fco = {"ativo": {"a": [{"pagina": 42, "coluna": 5}]}, "fco_paginas": {"f": [3]}}
    assert c._posicoes(base) == c._posicoes(json.loads(json.dumps(base)))
    assert c._posicoes(base) != c._posicoes(outra_coluna)
    assert c._posicoes(base) != c._posicoes(outra_pagina_fco)


def _base_falsa(tmp_path, inventario=b"{}"):
    base = tmp_path / "base"
    base.mkdir()
    (base / "pin.json").write_text('{"fontes": []}')
    (base / "inventario_textual.json").write_bytes(inventario)
    return base


def test_inventario_publicado_diferente_derruba_antes_de_gravar_pin(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "BASE", _base_falsa(tmp_path))
    with pytest.raises(AssertionError, match="inventário publicado"):
        c.executar(tmp_path / "revisao")
    assert not (tmp_path / "revisao" / "pin_revisao.json").exists()


def test_codigo_congelado_alterado_derruba_antes_de_gravar_pin(tmp_path, monkeypatch):
    """**Pré-condição atualizada, declaradamente, na correção RAG (C1):** o pin de
    execução e o pin de alcance passaram a ser conferidos por hash antes de
    qualquer uso; o teste fixa os hashes dos seus pins falsos para continuar
    exercitando a guarda do código congelado. Asserções intactas."""
    base = _base_falsa(tmp_path, b"inventario")
    (base / "pin_execucao.json").write_text(
        '{"codigo_sha256": {' + ", ".join(f'"{p}": "{"0" * 64}"' for p in c.CODIGO_CONGELADO) + "}}")
    monkeypatch.setattr(c, "BASE", base)
    monkeypatch.setattr(c, "INVENTARIO_PUBLICADO_SHA256", hashlib.sha256(b"inventario").hexdigest())
    monkeypatch.setattr(c, "PIN_EXECUCAO_SHA256", c.rad.sha256(base / "pin_execucao.json"))
    monkeypatch.setattr(c, "PIN_ALCANCE_SHA256", c.rad.sha256(base / "pin.json"))
    with pytest.raises(AssertionError, match="código GEOM-1"):
        c.executar(tmp_path / "revisao")
    assert not (tmp_path / "revisao" / "pin_revisao.json").exists()


@pytest.mark.parametrize("alterada", ["conferencia_revisao.json", "pin_revisao.json", "inventario_textual.json"])
def test_reconferencia_recusa_entrada_diferente_da_publicada(tmp_path, monkeypatch, alterada):
    """N1: cada entrada da reconferência tem de ser a versão publicada, antes de qualquer leitura."""
    base, revisao = tmp_path / "base", tmp_path / "revisao"
    base.mkdir()
    revisao.mkdir()
    conteudos = {revisao / "conferencia_revisao.json": b"conferencia", revisao / "pin_revisao.json": b"pin",
                 base / "inventario_textual.json": b"inventario"}
    for caminho, conteudo in conteudos.items():
        caminho.write_bytes(conteudo if caminho.name != alterada else b"adulterado")
    monkeypatch.setattr(c, "BASE", base)
    monkeypatch.setattr(c, "DESTINO", revisao)
    monkeypatch.setattr(c, "CONFERENCIA_REVISAO_SHA256", hashlib.sha256(b"conferencia").hexdigest())
    monkeypatch.setattr(c, "PIN_REVISAO_SHA256", hashlib.sha256(b"pin").hexdigest())
    monkeypatch.setattr(c, "INVENTARIO_PUBLICADO_SHA256", hashlib.sha256(b"inventario").hexdigest())
    destino = tmp_path / "reconferencia.json"
    with pytest.raises(AssertionError, match=alterada):
        c.reconferir_publicados(destino)
    assert not destino.exists()


def test_reconferencia_recusa_sobrescrever(tmp_path):
    destino = tmp_path / "reconferencia.json"
    destino.write_text("{}")
    with pytest.raises(FileExistsError):
        c.reconferir_publicados(destino)


def _registro(tipo, linha, **trecho):
    return {"tipo": tipo, "linha": linha, **trecho}


def test_efeito_da_politica_conta_cada_destino():
    antigo = [_pagina([_registro("mencao_dfc", 1, trecho="hedge de fluxo de caixa"),
                       _registro("ativo_total", 2, trecho="Total do ativo [valor omitido]"),
                       _registro("ativo_total", 3, trecho="Total do ativo (R$ [valor omitido] mil)"),
                       _registro("ativo_total", 4, trecho="Ativo total negativo [valor omitido]")])]
    novo = [_pagina([_registro("mencao_dfc", 1, trecho_omitido="linha_de_fluxo"),
                     _registro("ativo_total", 2, trecho="Total do ativo [valor omitido]"),
                     _registro("ativo_total", 3, trecho="Total do ativo [valor omitido] mil"),
                     _registro("ativo_total", 4, trecho_omitido="vocabulario_de_caixa")])]
    assert c.efeito_da_politica(antigo, novo) == {
        "registros": 4, "trecho_identico": 1, "trecho_alterado": 1, "omitido_por_fluxo": 1,
        "omitido_por_vocabulario": 1, "estrutura_diferente": 0}


def test_efeito_da_politica_acusa_estrutura_diferente():
    antigo = [_pagina([_registro("ativo_total", 2, trecho="x")])]
    assert c.efeito_da_politica(antigo, [_pagina([_registro("ativo_total", 9, trecho="x")])])["estrutura_diferente"] == 1
    assert c.efeito_da_politica(antigo, [{**_pagina([]), "pagina": 2}])["estrutura_diferente"] == 1


# --- Correção RAG (25/09) — C2: token inteiro e sinal explícito (RAG-02) ---

def _sinal_de(linha, modulo=1234):
    (sinal,) = [t.sinal for t in c.tokens_da_linha(linha) if t.modulo == modulo]
    return sinal


@pytest.mark.parametrize("texto,alvo", [("Total 1.234.5678", 1234567), ("Total -  1.234", 1234),
                                        ("Total (R$ 1.234)", 1234)])
def test_casos_da_conferencia_nao_casam_positivo(texto, alvo):
    """RAG-02: os três casos sintéticos da conferência de 25/09 casavam +alvo."""
    assert c.ocorrencias([texto], {"a": Decimal(alvo)}, por_modulo=False) == {"a": []}


def test_parenteses_com_moeda_casa_o_negativo():
    assert c.ocorrencias(["Total (R$ 1.234)"], {"a": Decimal(-1234)}, por_modulo=False)["a"]


@pytest.mark.parametrize("alvo", [1234567, 1234568, 8, 12345678, 5678])
def test_token_malformado_nao_casa_por_prefixo_nem_por_modulo(alvo):
    for por_modulo in (False, True):
        assert c.ocorrencias(["Total 1.234.5678"], {"a": Decimal(alvo)}, por_modulo=por_modulo) == {"a": []}


@pytest.mark.parametrize("linha,esperado", [
    ("Total 1.234", 1), ("+1.234", 1), ("＋1.234", 1), ("R$ 1.234", 1), ("R$1.234", 1), ("US$     1.234", 1),
    ("USD1.234", 1), ("(i) 1.234", 1), ("Total 1.234.", 1), ("1.234 -", 1), ("1.234 (nota)", 1),
    ("(1.234)", -1), ("( 1.234 )", -1), ("(     1.234)", -1), ("(R$ 1.234)", -1), ("R$ (1.234)", -1),
    ("R$(1.234)", -1), ("(USD 1.234)", -1), ("EUR (1.234)", -1), ("（1.234）", -1), ("﹙R$ 1.234﹚", -1),
    ("-1.234", -1), ("Total -1.234", -1), ("−R$ 1.234", -1), ("R$ -1.234", -1), ("US$ -1.234", -1),
    ("−USD 1.234", -1), ("−USD1.234", -1),
])
def test_formas_aceitas_de_sinal(linha, esperado):
    assert _sinal_de(linha) == esperado


@pytest.mark.parametrize("linha", [
    "- 1.234", "Total -  1.234", "−   1.234", "- R$ 1.234", "+ 1.234", "±1.234", "­1.234",
    "1.234-", "1.234−", "(1.234", "1.234)", "-(1.234)", "(-1.234)", "(+1.234)", "(1.234)-", "--1.234",
    "Total(1.234)", "x-1.234", "2024-1.234", "-   -   1.234", "(Nota 1.234)", "Ativo total – 1.234",
])
def test_formas_ambiguas_sao_recusa_explicita(linha):
    """C2: nenhuma leitura de sinal — não casa com sinal, aparece como ambíguo, e
    por módulo (FCO) continua casando."""
    assert _sinal_de(linha) is None
    for alvo in (1234, -1234):
        assert c.ocorrencias([linha], {"a": Decimal(alvo)}, por_modulo=False) == {"a": []}
    assert len(c.ocorrencias_de_sinal_ambiguo([linha], {"a": Decimal(1234)})["a"]) == 1
    assert len(c.ocorrencias([linha], {"a": Decimal(-1234)}, por_modulo=True)["a"]) == 1


# A3 (adendo): expectativas construídas SEM a implementação, a partir da tabela
# Unicode. A classe de sinais é a regra do R4 (Pd, ou nome com HYPHEN, DASH, MINUS,
# PLUS SIGN ou PARENTHESIS, fora de letra e número); dentro dela, nega o que é Pd ou
# se normaliza (NFKC) no MINUS SIGN; afirma o que se normaliza em `+`; parêntese é
# o que se normaliza em `(` ou `)`; o resto é "outro sinal".
def _nome(ch):
    return unicodedata.name(ch, "")


def _nfkc(ch):
    return unicodedata.normalize("NFKC", ch)


_CLASSE_DE_SINAIS = [ch for ch in map(chr, range(sys.maxunicode + 1))
                     if unicodedata.category(ch)[0] not in "LN"
                     and (unicodedata.category(ch) == "Pd"
                          or any(n in _nome(ch) for n in ("HYPHEN", "DASH", "MINUS", "PLUS SIGN", "PARENTHESIS")))]
_NEGAM = [ch for ch in _CLASSE_DE_SINAIS if unicodedata.category(ch) == "Pd" or _nfkc(ch) == "−"]
_AFIRMAM = [ch for ch in _CLASSE_DE_SINAIS if _nfkc(ch) == "+"]
_ABREM = [ch for ch in _CLASSE_DE_SINAIS if _nfkc(ch) == "("]
_FECHAM = [ch for ch in _CLASSE_DE_SINAIS if _nfkc(ch) == ")"]
_FECHAM_QUALQUER = [ch for ch in _CLASSE_DE_SINAIS if "PARENTHESIS" in _nome(ch) and "RIGHT" in _nome(ch)]
_ABREM_QUALQUER = [ch for ch in _CLASSE_DE_SINAIS if "PARENTHESIS" in _nome(ch) and "LEFT" in _nome(ch)]
_OUTROS = [ch for ch in _CLASSE_DE_SINAIS
           if ch not in _NEGAM + _AFIRMAM + _ABREM + _FECHAM + _FECHAM_QUALQUER]
_ID = {"ids": lambda ch: f"U+{ord(ch):04X}"}


def test_classes_da_tabela_tem_o_tamanho_esperado():
    """Controle das expectativas: 26 Pd + MINUS SIGN, SUPERSCRIPT e SUBSCRIPT MINUS."""
    assert len(_NEGAM) == 29 and "−" in _NEGAM and "⁻" in _NEGAM and "₋" in _NEGAM
    assert "❖" not in _NEGAM and "➖" not in _NEGAM and "\U000e002d" not in _NEGAM
    assert sorted(_ABREM) == sorted("(⁽₍︵﹙（") and len(_FECHAM) == 6
    assert _OUTROS and "±" in _OUTROS and "➖" in _OUTROS


@pytest.mark.parametrize("traco", _NEGAM, **_ID)
def test_todo_traco_ou_menos_colado_nega_e_separado_e_ambiguo(traco):
    """**Ajuste declarado (adendo A3):** a versão desta onda testava ainda `➖` (HEAVY
    MINUS SIGN) e `˗` (MODIFIER LETTER MINUS SIGN) como negativos. Pela definição do
    adendo, eles não se normalizam no MINUS SIGN e passam a "outro sinal"
    (`test_outro_sinal_nunca_da_sinal`). Os demais continuam, agora com a lista
    inteira derivada da tabela."""
    assert _sinal_de(f"Total {traco}1.234") == -1
    assert _sinal_de(f"Total {traco} 1.234") is None
    assert _sinal_de(f"Total {traco}R$ 1.234") == -1


@pytest.mark.parametrize("mais", _AFIRMAM, **_ID)
def test_mais_colado_e_positivo_e_separado_e_ambiguo(mais):
    """**Ajuste declarado (adendo A3):** `➕` (HEAVY PLUS SIGN) saiu daqui; não se
    normaliza em `+` e virou "outro sinal"."""
    assert _sinal_de(f"Total {mais}1.234") == 1
    assert _sinal_de(f"Total {mais} 1.234") is None


@pytest.mark.parametrize("outro", _OUTROS, **_ID)
def test_outro_sinal_nunca_da_sinal(outro):
    """A3: ❖, ∖, ⊖, setas, combinantes, TAG, `±`, parênteses ornamentais… colados
    antes ou depois do número: ambíguo. Antes, ❖ negava e o ativo sumia calado."""
    assert _sinal_de(f"Total {outro}1.234") is None
    if outro not in _ABREM_QUALQUER:  # parêntese de abertura depois do número começa outra coisa
        assert _sinal_de(f"Total 1.234{outro}") is None
    assert c.ocorrencias([f"Total {outro}1.234"], {"a": Decimal(1234)}, por_modulo=False) == {"a": []}
    assert len(c.ocorrencias_de_sinal_ambiguo([f"Total {outro}1.234"], {"a": Decimal(1234)})["a"]) == 1


@pytest.mark.parametrize("abre", _ABREM, **_ID)
def test_todo_parentese_de_abertura_normalizado_fecha_negativo(abre):
    assert _sinal_de(f"Total {abre}1.234)") == -1
    assert _sinal_de(f"Total {abre} 1.234 )") == -1


@pytest.mark.parametrize("fecha", _FECHAM, **_ID)
def test_todo_parentese_de_fechamento_normalizado_fecha_negativo(fecha):
    assert _sinal_de(f"Total (1.234{fecha}") == -1
    assert _sinal_de(f"Total 1.234{fecha}") is None


@pytest.mark.parametrize("fecha", _FECHAM_QUALQUER, **_ID)
def test_parentese_de_fechamento_a_esquerda_e_de_algo_anterior(fecha):
    """Encerra o contexto à esquerda (o número depois dele é limpo), e depois do
    número, se não é o `)` normalizado, é sinal colado: ambíguo."""
    assert _sinal_de(f"(nota{fecha} 1.234") == 1
    if fecha not in _FECHAM:
        assert _sinal_de(f"Total 1.234{fecha}") is None


@pytest.mark.parametrize("abre", _ABREM_QUALQUER, **_ID)
def test_parentese_de_abertura_depois_do_numero_comeca_outra_coisa(abre):
    assert _sinal_de(f"Total 1.234 {abre}nota") == 1
    assert _sinal_de(f"Total 1.234{abre}nota") == 1


# A2 (adendo): invisível = formatação (Cf) ou controle (Cc) que não é espaço nem sinal.
_INVISIVEIS = [ch for ch in map(chr, range(sys.maxunicode + 1))
               if unicodedata.category(ch) in ("Cf", "Cc") and not ch.isspace() and ch not in _CLASSE_DE_SINAIS]


@pytest.mark.parametrize("invisivel", _INVISIVEIS, **_ID)
def test_invisivel_perto_de_sinal_ou_dentro_do_numero_e_recusa(invisivel):
    """A2 (achado 2 da conferência da correção): `−\\u200b1.234` casava positivo."""
    for linha in (f"Total −{invisivel}1.234", f"Total ({invisivel}1.234{invisivel})",
                  f"Total (1.234{invisivel})", f"Total 1.234{invisivel}-", f"Total -{invisivel} 1.234"):
        assert _sinal_de(linha) is None, linha
        assert c.ocorrencias([linha], {"a": Decimal(1234)}, por_modulo=False) == {"a": []}
    assert _sinal_de(f"Total {invisivel}1.234") == 1  # sem sinal nem parêntese, nada muda
    assert [(t.modulo, t.motivo) for t in c.tokens_da_linha(f"Total 1.{invisivel}234")] == [
        (None, "invisivel_no_token")]


def test_colunas_vizinhas_nao_contaminam_o_sinal():
    """**Ajuste declarado (adendo A4a):** a versão desta onda fixava `2024-2025` com
    2024 positivo. Sinal colado depois do token passa a ambíguo, qualquer que seja o
    caractere seguinte — a letra do C2."""
    assert _tokens("(1.234)  5.678  -9.012") == [(1, 1234, -1), (2, 5678, 1), (3, 9012, -1)]
    assert _tokens("1.234 -5.678") == [(1, 1234, 1), (2, 5678, -1)]
    assert _tokens("-  1.234   5.678") == [(1, 1234, None), (2, 5678, 1)]
    assert _tokens("2024-2025") == [(1, 2024, None), (2, 2025, None)]


@pytest.mark.parametrize("linha", ["Total 1.234.567-8", "Total 1.234.567–89", "Total (1.234.567)-8",
                                   "Total 1.234.567+1", "Total 1.234.567­"])
def test_sinal_colado_depois_do_token_e_ambiguo_mesmo_seguido_de_digito(linha):
    """A4a (achado 4a): `1.234.567-8` casava +1234567 — um número de registro, não o ativo."""
    assert _sinal_de(linha, 1234567) is None
    for alvo in (1234567, -1234567):
        assert c.ocorrencias([linha], {"a": Decimal(alvo)}, por_modulo=False) == {"a": []}


def test_menos_colado_a_moeda_separada_do_numero_e_negativo():
    """A4b (leitura declarada): `-R$ 1.234,00` é o formato de valor negativo em reais.
    O menos vale colado ao que o segue; entre a moeda e o número o espaço é livre."""
    for linha in ("-R$ 1.234", "−R$     1.234", "-US$ 1.234", "−USD 1.234", "R$ -1.234"):
        assert _sinal_de(linha) == -1, linha
    for linha in ("- R$ 1.234", "-  R$ 1.234", "R$ - 1.234"):
        assert _sinal_de(linha) is None, linha


def test_motivo_de_cada_token():
    linha = "(1.234) a -5 b - 6 c 7- d (8 e 9) f 31.12.2024 g ,5 h ❖10 i --11 j x-12 k 13"
    assert [t.motivo for t in c.tokens_da_linha(linha)] == [
        "parenteses", "menos_colado", "sinal_seguido_de_espaco", "sinal_depois_do_token", "abre_sem_fecha",
        "fecha_sem_abre", "fora_da_gramatica", "separador_a_esquerda", "outro_sinal", "varios_sinais",
        "colado_a_palavra", "limpo"]


@pytest.mark.parametrize("linha", ["1.234.5678", "31.12.2024", "1,234,567", "1.23.456", "12.34", "1.234,56,7",
                                   ".5", ",50", "3,1.234"])
def test_forma_fora_da_gramatica_e_recusada(linha):
    assert _tokens(linha) == [(1, None, None)]


def test_coluna_conta_tambem_o_token_recusado():
    assert _tokens("Em 31.12.2024 1.234") == [(1, None, None), (2, 1234, 1)]
    (achado,) = c.ocorrencias(["Em 31.12.2024 1.234"], {"a": Decimal(1234)}, por_modulo=False)["a"]
    assert (achado["coluna"], achado["tokens"]) == (2, 2)


def test_contagem_por_pagina_independe_do_alvo():
    paginas = ["1.234.5678 x\n31.12.2024 5\n1.234", "- 7\n(8"]
    assert c.contagem_de_tokens(paginas) == {"tokens_fora_da_gramatica_por_pagina": {"1": 2},
                                              "tokens_com_sinal_ambiguo_por_pagina": {"2": 2}}


def test_ausencia_falsa_vira_ambiguo_publicado():
    """O traço de pontuação ou de coluna vazia antes de um ativo positivo: a versão
    conferida lia negativo com um espaço e o ativo sumia sem sinal nenhum."""
    paginas = ["Ativo total – 1.234.567", "Total do ativo - 1.234.567"]
    alvo = {"a": Decimal(1234567)}
    assert c.ocorrencias(paginas, alvo, por_modulo=False) == {"a": []}
    publicado = c.publicar_ativo(c.ocorrencias_de_sinal_ambiguo(paginas, alvo))["a"]
    assert [(p["pagina"], p["coluna"]) for p in publicado] == [(1, 1), (2, 1)]
    assert not re.search(r"\d", "".join(p.get("trecho", "") for p in publicado))


def test_fco_por_modulo_casa_qualquer_sinal_e_publica_so_paginas():
    paginas = ["Linha - 2.345.678", "(2.345.678)", "2.345.678", "-2.345.678"]
    achados = c.ocorrencias(paginas, {"f": Decimal(-2345678)}, por_modulo=True)
    assert c.publicar_fco(achados) == {"f": [1, 2, 3, 4]}


def test_modos_tambem_concordam_nos_ambiguos():
    base = {"ativo": {"a": []}, "ativo_modulo_com_sinal_ambiguo": {"a": [{"pagina": 3, "coluna": 1}]},
            "fco_paginas": {"f": []}}
    outro = {**base, "ativo_modulo_com_sinal_ambiguo": {"a": []}}
    assert c._posicoes(base) != c._posicoes(outro)


# --- C3: autoverificação por equivalência numérica (RAG-03) ---

_OITO_DA_CONFERENCIA = [("1.234.567,00", "1234567"), ("1234567.00", "1234567"), ("1 234 567,00", "1234567"),
                        ("1.234.567,50", "1234567.5")]


@pytest.mark.parametrize("local", ["texto", "chave"])
@pytest.mark.parametrize("texto,valor", _OITO_DA_CONFERENCIA)
def test_casos_da_conferencia_sao_barrados_sem_repetir_o_valor(texto, valor, local):
    saida = {"nota": texto} if local == "texto" else {texto: True}
    with pytest.raises(c.VazamentoDeValor) as erro:
        c.verificar_sem_valores(saida, [Decimal(valor)])
    assert not re.search(r"\d", str(erro.value))


@pytest.mark.parametrize("texto,valor", [
    ("1234567.0", "1234567"), ("1.234.567,000", "1234567"), ("1234567E0", "1234567"), ("1.234567E+6", "1234567"),
    ("12345.67e2", "1234567"), ("-1.234.567,00", "1234567"), ("(1.234.567,00)", "-1234567"),
    ("1.234.568", "1234567.5"), ("1.234.567", "1234567.5"), ("1 234 567", "1234567"),
    ("1.234,567", "1234.567"), ("0001234567", "1234567"), ("valor: 1234567,0.", "1234567"),
])
def test_representacao_equivalente_e_barrada(texto, valor):
    for saida in ({"nota": texto}, {texto: 1}, {"lista": [{"x": texto}]}):
        with pytest.raises(c.VazamentoDeValor):
            c.verificar_sem_valores(saida, [Decimal(valor)])


def test_mensagem_nunca_repete_chave_com_digito():
    with pytest.raises(c.VazamentoDeValor) as erro:
        c.verificar_sem_valores({"campo_2024": 1234567}, [Decimal(1)])
    assert "2024" not in str(erro.value) and "campo_####" in str(erro.value)


@pytest.mark.parametrize("saida", [
    {"pdf_sha256": "1234567"}, {"pdf_sha256": "hash 1234567"}, {"codigo_sha256": {"a.py": "1234567"}},
    {"codigo_sha256": {"a.py": {"b": "1234567"}}}, {"codigo_sha256": {"1.234.567": "a" * 64}},
    {"data": "1.234.567"}, {"dt_refer": "1234567"}, {"data": "2024-06-30 1234567"},
])
def test_isencao_nao_cobre_o_que_nao_tem_a_forma(saida):
    with pytest.raises(c.VazamentoDeValor):
        c.verificar_sem_valores(saida, [Decimal("1234567")])


@pytest.mark.parametrize("saida", [{"x": {1, 2}}, {"x": object()}, {"x": b"1234567"}])
def test_tipo_nao_previsto_derruba(saida):
    with pytest.raises(TypeError):
        c.verificar_sem_valores(saida, [Decimal("1234567")])


def test_valor_dentro_de_sequencia_mais_longa_nao_e_representacao_dele():
    """Controle: lê-se o token inteiro, como antes; `91234567` não diz `1234567`."""
    c.verificar_sem_valores({"nota": "91234567", "outra": "12345678"}, [Decimal("1234567")])


_ESPACOS_ZS = [ch for ch in map(chr, range(sys.maxunicode + 1)) if unicodedata.category(ch) == "Zs"]


@pytest.mark.parametrize("espaco", _ESPACOS_ZS, **_ID)
def test_todo_espaco_zs_entre_grupos_e_separador_de_milhar(espaco):
    """A5 (achado 5): o espaço de algarismo (U+2007), U+2008, U+3000 e outros passavam."""
    for saida in ({"nota": f"1{espaco}234{espaco}567"}, {f"1{espaco}234{espaco}567": True}):
        with pytest.raises(c.VazamentoDeValor):
            c.verificar_sem_valores(saida, [Decimal(1234567)])


@pytest.mark.parametrize("separador", ["'", "’", "ʼ", "_", "·", "‧", "，", "．",
                                       "-", "/", ":", "′"])
def test_qualquer_separador_nao_alfanumerico_entre_grupos_e_milhar(separador):
    """A5: separador de milhar é qualquer não alfanumérico (ou sublinhado), não uma lista."""
    with pytest.raises(c.VazamentoDeValor):
        c.verificar_sem_valores({"nota": f"1{separador}234{separador}567"}, [Decimal(1234567)])


@pytest.mark.parametrize("invisivel", _INVISIVEIS, **_ID)
def test_invisivel_no_numero_publicado_nao_esconde_o_valor(invisivel):
    for texto in (f"1{invisivel}234{invisivel}567", f"12{invisivel}34567", f"1.234.{invisivel}567"):
        with pytest.raises(c.VazamentoDeValor):
            c.verificar_sem_valores({"nota": texto}, [Decimal(1234567)])


@pytest.mark.parametrize("texto", ["1234567e2024", "1234567E-1", "1234567e+999", "1.234.567E5", "１２３４５６７",
                                   "1234567e"])
def test_mantissa_e_lida_tambem_sem_o_expoente(texto):
    """A5: `1234567e2024` só era lido com o expoente, e passava."""
    with pytest.raises(c.VazamentoDeValor):
        c.verificar_sem_valores({"nota": texto}, [Decimal(1234567)])


@pytest.mark.parametrize("texto", ["¹²³⁴⁵⁶⁷", "①②③④⑤⑥⑦", "₁₂₃₄₅₆₇", "1²³⁴⁵⁶⁷"])
def test_digitos_de_compatibilidade_sao_lidos_pela_normalizacao(texto):
    """A5: sobrescrito, circulado e subscrito não são `\\d` — só a NFKC os lê como
    algarismos. Acrescentado depois da rodada 1 das mutações, em que retirar a NFKC
    não derrubava teste nenhum."""
    with pytest.raises(c.VazamentoDeValor):
        c.verificar_sem_valores({"nota": texto}, [Decimal(1234567)])


def test_data_nao_vira_grupo_de_milhar():
    """Controle: `2024-06-30` não junta grupos (06 e 30 não têm três dígitos)."""
    c.verificar_sem_valores({"nota": "em 2024-06-30"}, [Decimal(20240630), Decimal(202406), Decimal(24063)])


@pytest.mark.parametrize("valores", [[], [Decimal(0)], [Decimal(999), Decimal("-999.9")]])
def test_autoverificacao_sem_valor_verificavel_nao_certifica(valores):
    with pytest.raises(AssertionError, match="sem valor verificável"):
        c._autoverificar({"pagina": 1}, valores)


# --- C4: limite da forma dividida por mil ---

def test_formas_que_so_casam_com_decimais():
    alvos = {"a": Decimal("1234.567"), "b": Decimal(1234), "c": Decimal("1234.000"), "d": Decimal("-5.5")}
    assert c.formas_que_so_casam_com_decimais(alvos) == ["a", "d"]


def test_limite_declara_a_forma_e_nao_tem_digito():
    """Sem dígito: texto fixo com número poderia coincidir com valor comparado."""
    assert "dividida por mil" in c.LIMITE and "arredondados" in c.LIMITE
    assert not re.search(r"\d", c.LIMITE)


# --- C1: toda entrada vinculada, universo do pin, pelo caminho inteiro (RAG-01) ---

_PAGINAS = {
    "900001": ["(Em milhares de reais)\nTotal dos ativos 1.234.567 1.111.111\nAtivo anterior – 1.111.111\n",
               "Notas explicativas com texto suficiente para não ser página vazia.\n"],
    "900002": ["(Em milhares de reais)\nTotal do ativo 4.444.444\n",
               "Outra página de notas, também com texto suficiente para a busca.\n"],
}


def _formulario_sintetico(ativo, fco):
    bp = (f"<Conta><CodigoConta>1</CodigoConta><TrimestreAtual>{ativo}</TrimestreAtual>"
          "<ExercicioAnterior>1.111.111</ExercicioAnterior></Conta>"
          "<Conta><CodigoConta>1.01.01</CodigoConta><TrimestreAtual>50.000</TrimestreAtual></Conta>")
    dfc = (f"<Conta><CodigoConta>6.01</CodigoConta><AcumuladoAtualExercicio>{fco}</AcumuladoAtualExercicio>"
           "<AcumuladoExercicioAnterior>-3.456.789</AcumuladoExercicioAnterior></Conta>"
           "<Conta><CodigoConta>6.05.02</CodigoConta><AcumuladoAtualExercicio>50.000</AcumuladoAtualExercicio></Conta>")
    ind_bp = ("<Conta><CodigoConta>1</CodigoConta><TrimestreAtual>999.999</TrimestreAtual>"
              "<ExercicioAnterior>888.888</ExercicioAnterior></Conta>")
    ind_dfc = "<Conta><CodigoConta>6.01</CodigoConta><AcumuladoAtualExercicio>77.777</AcumuladoAtualExercicio></Conta>"
    return ET.fromstring(
        f"<Formulario><DfConsolidadas><BalancoPatrimonialAtivo>{bp}</BalancoPatrimonialAtivo>"
        f"<DemonstracaoFluxoCaixa>{dfc}</DemonstracaoFluxoCaixa></DfConsolidadas><DfIndividuais>"
        f"<BalancoPatrimonialAtivo>{ind_bp}</BalancoPatrimonialAtivo>"
        f"<DemonstracaoFluxoCaixa>{ind_dfc}</DemonstracaoFluxoCaixa></DfIndividuais></Formulario>")


_FORMULARIOS = {"900001": ("1.234.567", "2.345.678"), "900002": ("4.444.444", "-5.555.555")}


def _sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _subprocess_falso(args, input=None, **_):
    if args[:2] == ["pdftotext", "-v"]:
        return SimpleNamespace(stdout=b"", stderr=b"pdftotext version sintetica\n")
    if args[:2] == ["pdftotext", "-layout"]:
        return SimpleNamespace(stdout=("\f".join(_PAGINAS[input.decode()]) + "\f").encode(), stderr=b"")
    raise AssertionError(f"chamada não prevista: {args}")


def _ambiente(tmp_path, monkeypatch):
    """Duas fontes sintéticas, entradas fixadas por hash, E/S de PDF e XML falsas.
    Contratos e código congelado são os reais: a conferência deles também roda."""
    brutos, base, geom = tmp_path / "brutos", tmp_path / "base", tmp_path / "geom"
    for pasta in (brutos, base, geom):
        pasta.mkdir()
    fontes = []
    for id_doc in _PAGINAS:
        pacote = f"pacote {id_doc}".encode()
        (brutos / f"{id_doc}.zip").write_bytes(pacote)
        fontes.append({"id_doc": id_doc, "cd_cvm": "000001", "dt_refer": "2024-06-30", "sha256": _sha(pacote)})
    pin = json.dumps({"fontes": fontes}).encode()
    execucao = json.dumps({"pin_sha256": _sha(pin), "codigo_sha256": {
        p: c.rad.sha256(c.rad.RAIZ / p) for p in c.CODIGO_CONGELADO}}).encode()
    # Como o inventário real: os campos da fonte do pin, o hash do PDF e as páginas.
    inventario = json.dumps({"registros": [
        {**f, "sha256_pdf": _sha(f["id_doc"].encode()),
         "paginas": inventariar_texto("\f".join(_PAGINAS[f["id_doc"]]) + "\f")} for f in fontes]}).encode()
    selecao = b'{"sintetica": true}'
    for caminho, dados in ((base / "pin.json", pin), (base / "pin_execucao.json", execucao),
                           (base / "inventario_textual.json", inventario), (geom / "selecao.json", selecao)):
        caminho.write_bytes(dados)
    for constante, dados in (("PIN_ALCANCE_SHA256", pin), ("PIN_EXECUCAO_SHA256", execucao),
                             ("INVENTARIO_PUBLICADO_SHA256", inventario), ("SELECAO_SHA256", selecao)):
        monkeypatch.setattr(c, constante, _sha(dados))
    monkeypatch.setattr(c, "BASE", base)
    monkeypatch.setattr(c, "GEOM", geom)
    monkeypatch.setattr(c, "DESTINO", tmp_path / "revisao")
    monkeypatch.setattr(c.rad, "BRUTOS", brutos)
    lidos = []  # (caminho aberto, hash dos bytes no momento da leitura) — para o A6b

    def formulario(pacote):
        lidos.append((pacote, _sha(pacote.read_bytes())))
        return "f.xml", "0" * 64, _formulario_sintetico(*_FORMULARIOS[pacote.stem]), "UNIDADE"

    def anexos(pacote):
        lidos.append((pacote, _sha(pacote.read_bytes())))
        return [(1, 193, pacote.stem.encode())]
    monkeypatch.setattr(c, "formulario", formulario)
    monkeypatch.setattr(c, "anexos_pdf", anexos)
    monkeypatch.setattr(c, "paginas_pdf", lambda pdf, modo: _PAGINAS[pdf.decode()])
    monkeypatch.setattr(c, "conferir_protegidos", lambda selecao: {"protegido_sintetico": True})
    monkeypatch.setattr(c.subprocess, "run", _subprocess_falso)
    return SimpleNamespace(base=base, geom=geom, revisao=tmp_path / "revisao", fontes=fontes, tmp=tmp_path,
                           brutos=brutos, lidos=lidos)


def _fixar_publicados(amb, monkeypatch):
    """Fixa as duas saídas da busca como "publicadas", como o N1 fixou as de 24/09."""
    for nome, constante in (("conferencia_revisao.json", "CONFERENCIA_REVISAO_SHA256"),
                            ("pin_revisao.json", "PIN_REVISAO_SHA256")):
        monkeypatch.setattr(c, constante, _sha((amb.revisao / nome).read_bytes()))


def _publicar_revisao(amb, monkeypatch):
    c.executar(amb.revisao)
    _fixar_publicados(amb, monkeypatch)


def _refixar(monkeypatch, caminho, conteudo, constante):
    dados = json.dumps(conteudo).encode()
    caminho.write_bytes(dados)
    monkeypatch.setattr(c, constante, _sha(dados))


def _rodar(entrada, amb):
    if entrada == "executar":
        return c.executar(amb.tmp / "nova")
    return c.reconferir_publicados(amb.tmp / "reconferencia.json")


def _nada_gravado(amb):
    return not (amb.tmp / "nova").exists() and not (amb.tmp / "reconferencia.json").exists()


def test_controle_positivo_examina_exatamente_as_duas_fontes_nas_duas_entradas(tmp_path, monkeypatch):
    amb = _ambiente(tmp_path, monkeypatch)
    busca = c.executar(amb.revisao)
    assert [d["id_doc"] for d in busca["documentos"]] == ["900001", "900002"]
    identidade = json.loads((amb.revisao / "pin_revisao.json").read_text())
    assert identidade["data"] == date.today().isoformat()
    assert identidade["contrato_correcao_sha256"] == c.CONTRATO_CORRECAO_SHA256
    assert identidade["fontes"] == amb.fontes
    doc = busca["documentos"][0]
    modo = doc["modos"]["-layout"]
    assert [(a["pagina"], a["linha"], a["coluna"]) for a in modo["ativo"]["consolidado_corrente"]] == [(1, 2, 1)]
    assert [(a["pagina"], a["linha"]) for a in modo["ativo"]["consolidado_comparativo"]] == [(1, 2)]
    assert [(a["pagina"], a["linha"]) for a in modo["ativo_modulo_com_sinal_ambiguo"]["consolidado_comparativo"]
            ] == [(1, 3)]
    assert all(not v for v in modo["fco_paginas"].values())
    assert modo["tokens_com_sinal_ambiguo_por_pagina"] == {"1": 1}
    assert doc["ativo_formas_que_so_casam_com_decimais"] == ["consolidado_corrente_sobre_mil"]
    assert doc["modos_concordam"] and doc["identidade_saldo_final_dfc_igual_caixa_bp"]
    assert busca["limite"] == c.LIMITE and busca["sentido_de_coluna"] == c.SENTIDO_DE_COLUNA
    assert identidade["adendo_correcao_sha256"] == c.ADENDO_CORRECAO_SHA256
    assert identidade["adendo2_correcao_sha256"] == c.ADENDO2_CORRECAO_SHA256
    assert identidade["adendo3_correcao_sha256"] == c.ADENDO3_CORRECAO_SHA256

    _fixar_publicados(amb, monkeypatch)
    reconferencia = c.reconferir_publicados(tmp_path / "reconferencia.json")
    assert [d["id_doc"] for d in reconferencia["documentos"]] == ["900001", "900002"]
    assert reconferencia["autoverificacao_estrita_nos_publicados"] == {
        "conferencia_revisao.json": True, "pin_revisao.json": True}
    assert reconferencia["data"] == date.today().isoformat()
    assert (tmp_path / "reconferencia.json").exists()


@pytest.mark.parametrize("entrada", ["executar", "reconferir"])
def test_pin_de_fontes_vazio_do_parecer_e_recusado(tmp_path, monkeypatch, entrada):
    """O cenário exato da conferência de 25/09: `fontes: []`, hash diferente do
    fixado, demais entradas íntegras. Antes: zero documentos e autoverificação
    `true`, gravada."""
    amb = _ambiente(tmp_path, monkeypatch)
    _publicar_revisao(amb, monkeypatch)
    (amb.base / "pin.json").write_text('{"fontes": []}')
    with pytest.raises(AssertionError, match=r"pin\.json"):
        _rodar(entrada, amb)
    assert _nada_gravado(amb)


_PINS_MALFORMADOS = {
    "vazio": lambda f: {"fontes": []},
    "sem_fontes": lambda f: {"outra_chave": f},
    "id_repetido": lambda f: {"fontes": [f[0], {**f[1], "id_doc": f[0]["id_doc"]}]},
    "hash_repetido": lambda f: {"fontes": [f[0], {**f[1], "sha256": f[0]["sha256"]}]},
    "hash_malformado": lambda f: {"fontes": [f[0], {**f[1], "sha256": "xyz"}]},
    "id_com_caminho": lambda f: {"fontes": [f[0], {**f[1], "id_doc": "../900002"}]},
    "fonte_sem_hash": lambda f: {"fontes": [f[0], {k: v for k, v in f[1].items() if k != "sha256"}]},
}


_MENSAGEM_ESTRUTURAL = {"vazio": "pin sem fontes", "sem_fontes": "pin sem fontes",
                        "id_repetido": r"fonte repetida no pin \(id_doc\)",
                        "hash_repetido": r"fonte repetida no pin \(sha256\)", "hash_malformado": "fonte do pin malformada",
                        "id_com_caminho": "fonte do pin malformada", "fonte_sem_hash": "fonte do pin malformada"}


def _espelhar_pin(amb, monkeypatch, pin):
    """A1: todas as outras referências concordam com o pin — pin de execução,
    inventário e, se houver revisão publicada, o pin dela e a conferência —, para
    que só a regra estrutural possa recusar."""
    dados = json.dumps(pin).encode()
    (amb.base / "pin.json").write_bytes(dados)
    monkeypatch.setattr(c, "PIN_ALCANCE_SHA256", _sha(dados))
    fontes = pin["fontes"] if isinstance(pin.get("fontes"), list) else []
    execucao = json.loads((amb.base / "pin_execucao.json").read_text())
    execucao["pin_sha256"] = _sha(dados)
    _refixar(monkeypatch, amb.base / "pin_execucao.json", execucao, "PIN_EXECUCAO_SHA256")
    inventario = json.loads((amb.base / "inventario_textual.json").read_text())
    registros = {r["id_doc"]: r for r in inventario["registros"]}
    inventario["registros"] = [{**registros.get(f["id_doc"], registros["900001"]), **f} for f in fontes]
    _refixar(monkeypatch, amb.base / "inventario_textual.json", inventario, "INVENTARIO_PUBLICADO_SHA256")
    if amb.revisao.exists():
        pin_revisao = json.loads((amb.revisao / "pin_revisao.json").read_text())
        pin_revisao.update(pin_alcance_sha256=_sha(dados), fontes=pin.get("fontes"))
        _refixar(monkeypatch, amb.revisao / "pin_revisao.json", pin_revisao, "PIN_REVISAO_SHA256")
        conferencia = json.loads((amb.revisao / "conferencia_revisao.json").read_text())
        documentos = {d["id_doc"]: d for d in conferencia["documentos"]}
        conferencia["documentos"] = [{**documentos.get(f["id_doc"], documentos["900001"]), "id_doc": f["id_doc"]}
                                     for f in fontes]
        _refixar(monkeypatch, amb.revisao / "conferencia_revisao.json", conferencia, "CONFERENCIA_REVISAO_SHA256")


@pytest.mark.parametrize("caso", sorted(_PINS_MALFORMADOS))
@pytest.mark.parametrize("entrada", ["executar", "reconferir"])
def test_pin_malformado_e_recusado_pela_estrutura(tmp_path, monkeypatch, entrada, caso):
    """**Substitui, declaradamente, `test_pin_malformado_com_hash_conferido_e_recusado`**
    (primeira execução desta onda). Aquele refixava só o hash do pin e casava
    `match="pin"`: a vinculação do pin de execução e do pin da revisão recusava
    antes, e o teste passava mesmo sem a regra estrutural (achado 1 da conferência
    da correção). Agora as outras referências espelham o pin malformado e cada caso
    casa a própria mensagem estrutural."""
    amb = _ambiente(tmp_path, monkeypatch)
    if entrada == "reconferir":
        _publicar_revisao(amb, monkeypatch)
    _espelhar_pin(amb, monkeypatch, _PINS_MALFORMADOS[caso](amb.fontes))
    with pytest.raises(AssertionError, match=_MENSAGEM_ESTRUTURAL[caso]):
        _rodar(entrada, amb)
    assert _nada_gravado(amb)


@pytest.mark.parametrize("entrada", ["executar", "reconferir"])
def test_espelhar_o_pin_valido_nao_recusa(tmp_path, monkeypatch, entrada):
    """Controle do teste acima: o espelhamento sozinho não derruba nada — quem recusa
    lá é a estrutura."""
    amb = _ambiente(tmp_path, monkeypatch)
    if entrada == "reconferir":
        _publicar_revisao(amb, monkeypatch)
    _espelhar_pin(amb, monkeypatch, {"fontes": amb.fontes, "comentario": "outro hash, mesmo universo"})
    assert [d["id_doc"] for d in _rodar(entrada, amb)["documentos"]] == ["900001", "900002"]


@pytest.mark.parametrize("pin,mensagem", [
    ({"fontes": []}, "pin sem fontes"), ({}, "pin sem fontes"), ([], "pin sem fontes"),
    ({"fontes": "900001"}, "pin sem fontes"),
    ({"fontes": [{"id_doc": "1", "sha256": "a" * 64}, {"id_doc": "1", "sha256": "b" * 64}]},
     r"repetida no pin \(id_doc\)"),
    ({"fontes": [{"id_doc": "1", "sha256": "a" * 64}, {"id_doc": "2", "sha256": "a" * 64}]},
     r"repetida no pin \(sha256\)"),
    ({"fontes": [{"id_doc": "1", "sha256": "A" * 64}]}, "malformada"),
    ({"fontes": [{"id_doc": "1", "sha256": "a" * 63}]}, "malformada"),
    ({"fontes": [{"id_doc": "../1", "sha256": "a" * 64}]}, "malformada"),
    ({"fontes": [{"id_doc": "１", "sha256": "a" * 64}]}, "malformada"),
    ({"fontes": [{"id_doc": 1, "sha256": "a" * 64}]}, "malformada"),
    ({"fontes": [{"sha256": "a" * 64}]}, "malformada"),
    ({"fontes": ["1"]}, "malformada"),
])
def test_validar_fontes_recusa_cada_regra(pin, mensagem):
    with pytest.raises(AssertionError, match=mensagem):
        c.validar_fontes(pin)


def test_validar_fontes_aceita_pin_bem_formado():
    fontes = [{"id_doc": "1", "sha256": "a" * 64, "extra": "x"}, {"id_doc": "2", "sha256": "b" * 64}]
    assert c.validar_fontes({"fontes": fontes}) == fontes


_RECUSA_DE_UNIVERSO = {"repetido": "documento repetido", "diferente": "documentos diferentes das fontes do pin"}


@pytest.mark.parametrize("mudanca,recusa", [("documento_a_menos", "diferente"), ("documento_a_mais", "diferente"),
                                            ("documento_repetido", "repetido"), ("ordem_trocada", "diferente")])
def test_reconferencia_recusa_conferencia_de_outro_universo(tmp_path, monkeypatch, mudanca, recusa):
    """Mensagem específica desde a rodada 1 das mutações (adendo, A1): casando só o
    prefixo, retirar a checagem de repetição não derrubava teste nenhum."""
    amb = _ambiente(tmp_path, monkeypatch)
    _publicar_revisao(amb, monkeypatch)
    conferencia = json.loads((amb.revisao / "conferencia_revisao.json").read_text())
    docs = conferencia["documentos"]
    conferencia["documentos"] = {"documento_a_menos": docs[:1],
                                 "documento_a_mais": docs + [{**docs[1], "id_doc": "900003"}],
                                 "documento_repetido": docs + docs[1:], "ordem_trocada": docs[::-1]}[mudanca]
    _refixar(monkeypatch, amb.revisao / "conferencia_revisao.json", conferencia, "CONFERENCIA_REVISAO_SHA256")
    with pytest.raises(AssertionError, match=f"conferência publicada: {_RECUSA_DE_UNIVERSO[recusa]}"):
        _rodar("reconferir", amb)
    assert _nada_gravado(amb)


@pytest.mark.parametrize("mudanca", ["outro_pin", "outras_fontes"])
def test_reconferencia_recusa_pin_da_revisao_de_outro_universo(tmp_path, monkeypatch, mudanca):
    amb = _ambiente(tmp_path, monkeypatch)
    _publicar_revisao(amb, monkeypatch)
    pin_revisao = json.loads((amb.revisao / "pin_revisao.json").read_text())
    if mudanca == "outro_pin":
        pin_revisao["pin_alcance_sha256"] = "0" * 64
    else:
        pin_revisao["fontes"] = pin_revisao["fontes"][:1]
    _refixar(monkeypatch, amb.revisao / "pin_revisao.json", pin_revisao, "PIN_REVISAO_SHA256")
    with pytest.raises(AssertionError, match="pin da revisão"):
        _rodar("reconferir", amb)
    assert _nada_gravado(amb)


@pytest.mark.parametrize("mudanca", ["registro_a_menos", "registro_repetido"])
@pytest.mark.parametrize("entrada", ["executar", "reconferir"])
def test_inventario_de_outro_universo_e_recusado(tmp_path, monkeypatch, entrada, mudanca):
    amb = _ambiente(tmp_path, monkeypatch)
    _publicar_revisao(amb, monkeypatch)
    inventario = json.loads((amb.base / "inventario_textual.json").read_text())
    registros = inventario["registros"]
    inventario["registros"] = registros[:1] if mudanca == "registro_a_menos" else registros + registros[1:]
    _refixar(monkeypatch, amb.base / "inventario_textual.json", inventario, "INVENTARIO_PUBLICADO_SHA256")
    recusa = _RECUSA_DE_UNIVERSO["diferente" if mudanca == "registro_a_menos" else "repetido"]
    with pytest.raises(AssertionError, match=f"inventário publicado: {recusa}"):
        _rodar(entrada, amb)
    assert _nada_gravado(amb)


def test_executar_recusa_pin_de_execucao_que_aponta_para_outro_pin(tmp_path, monkeypatch):
    amb = _ambiente(tmp_path, monkeypatch)
    execucao = json.loads((amb.base / "pin_execucao.json").read_text())
    execucao["pin_sha256"] = "0" * 64
    _refixar(monkeypatch, amb.base / "pin_execucao.json", execucao, "PIN_EXECUCAO_SHA256")
    with pytest.raises(AssertionError, match="pin de execução não aponta"):
        _rodar("executar", amb)
    assert _nada_gravado(amb)


@pytest.mark.parametrize("entrada,arquivo", [("executar", "pin_execucao.json"), ("executar", "selecao.json"),
                                             ("reconferir", "selecao.json")])
def test_referencia_alterada_e_recusada(tmp_path, monkeypatch, entrada, arquivo):
    """Referências do código congelado e dos protegidos, lidas sem conferência
    antes. A reconferência não usa o pin de execução."""
    amb = _ambiente(tmp_path, monkeypatch)
    _publicar_revisao(amb, monkeypatch)
    pasta = amb.geom if arquivo == "selecao.json" else amb.base
    (pasta / arquivo).write_text('{"alterado": true}')
    with pytest.raises(AssertionError, match=arquivo.replace(".", r"\.")):
        _rodar(entrada, amb)
    assert _nada_gravado(amb)


@pytest.mark.parametrize("entrada,constante", [("executar", "CONTRATO_SHA256"), ("executar", "CONTRATO_CORRECAO_SHA256"),
                                               ("executar", "ADENDO_CORRECAO_SHA256"),
                                               ("executar", "ADENDO2_CORRECAO_SHA256"),
                                               ("executar", "ADENDO3_CORRECAO_SHA256"),
                                               ("reconferir", "ADENDO_SHA256"),
                                               ("reconferir", "CONTRATO_CORRECAO_SHA256"),
                                               ("reconferir", "ADENDO_CORRECAO_SHA256"),
                                               ("reconferir", "ADENDO2_CORRECAO_SHA256"),
                                               ("reconferir", "ADENDO3_CORRECAO_SHA256")])
def test_documento_governante_diferente_do_fixado_e_recusado(tmp_path, monkeypatch, entrada, constante):
    amb = _ambiente(tmp_path, monkeypatch)
    _publicar_revisao(amb, monkeypatch)
    monkeypatch.setattr(c, constante, "0" * 64)
    with pytest.raises(AssertionError, match="diferente da versão fixada"):
        _rodar(entrada, amb)
    assert _nada_gravado(amb)


def test_identidade_com_valor_comparado_nao_e_gravada(tmp_path, monkeypatch):
    """C3: a identidade também é publicada. Um metadado do pin que coincida com um
    valor comparado derruba a execução antes de gravar QUALQUER arquivo."""
    amb = _ambiente(tmp_path, monkeypatch)
    fontes = [{**amb.fontes[0], "cd_cvm": "1.234.567"}, amb.fontes[1]]
    _refixar(monkeypatch, amb.base / "pin.json", {"fontes": fontes}, "PIN_ALCANCE_SHA256")
    execucao = json.loads((amb.base / "pin_execucao.json").read_text())
    execucao["pin_sha256"] = c.PIN_ALCANCE_SHA256
    _refixar(monkeypatch, amb.base / "pin_execucao.json", execucao, "PIN_EXECUCAO_SHA256")
    with pytest.raises(c.VazamentoDeValor):
        _rodar("executar", amb)
    assert _nada_gravado(amb)


# --- Adendo da correção (A6, A7): versão da fonte, leitura única, nada gravado antes da recusa ---

@pytest.mark.parametrize("campo", ["sha256", "sha256_pdf"])
@pytest.mark.parametrize("entrada", ["executar", "reconferir"])
def test_inventario_de_outra_versao_da_fonte_e_recusado(tmp_path, monkeypatch, entrada, campo):
    """A6a (achado 6): mesmo `id_doc`, outra versão — antes a execução concluía."""
    amb = _ambiente(tmp_path, monkeypatch)
    _publicar_revisao(amb, monkeypatch)
    inventario = json.loads((amb.base / "inventario_textual.json").read_text())
    inventario["registros"][1][campo] = "e" * 64
    _refixar(monkeypatch, amb.base / "inventario_textual.json", inventario, "INVENTARIO_PUBLICADO_SHA256")
    with pytest.raises(AssertionError, match="inventário publicado: outra versão"):
        _rodar(entrada, amb)
    assert _nada_gravado(amb)


@pytest.mark.parametrize("campo", ["xml_sha256", "pdf_sha256"])
def test_conferencia_de_outra_versao_da_fonte_e_recusada(tmp_path, monkeypatch, campo):
    amb = _ambiente(tmp_path, monkeypatch)
    _publicar_revisao(amb, monkeypatch)
    conferencia = json.loads((amb.revisao / "conferencia_revisao.json").read_text())
    conferencia["documentos"][0][campo] = "e" * 64
    _refixar(monkeypatch, amb.revisao / "conferencia_revisao.json", conferencia, "CONFERENCIA_REVISAO_SHA256")
    with pytest.raises(AssertionError, match="conferência publicada: outra versão"):
        _rodar("reconferir", amb)
    assert _nada_gravado(amb)


@pytest.mark.parametrize("entrada", ["executar", "reconferir"])
def test_leitores_abrem_a_copia_conferida_e_nao_o_pacote_original(tmp_path, monkeypatch, entrada):
    """A6b (achado 6): o pacote era conferido e depois relido do disco. Agora os
    leitores abrem uma cópia privada com os mesmos bytes, apagada no fim."""
    amb = _ambiente(tmp_path, monkeypatch)
    _publicar_revisao(amb, monkeypatch)
    amb.lidos.clear()
    _rodar(entrada, amb)
    hashes = {f["id_doc"]: f["sha256"] for f in amb.fontes}
    assert sorted({caminho.stem for caminho, _ in amb.lidos}) == ["900001", "900002"]
    assert all(caminho.parent != amb.brutos and sha == hashes[caminho.stem] for caminho, sha in amb.lidos)
    assert not any(caminho.exists() for caminho, _ in amb.lidos)


def test_pacote_trocado_depois_da_conferencia_nao_e_lido(tmp_path, monkeypatch):
    """A6b: se o arquivo em disco muda entre a conferência e a leitura, lê-se a
    cópia conferida — não o arquivo novo."""
    amb = _ambiente(tmp_path, monkeypatch)
    original = c.conferir_fontes

    def conferir_e_trocar(fontes, brutos, copiar_para=None):
        copias = original(fontes, brutos, copiar_para)
        for fonte in fontes:
            (brutos / f"{fonte['id_doc']}.zip").write_bytes(b"trocado depois do hash")
        return copias
    monkeypatch.setattr(c, "conferir_fontes", conferir_e_trocar)
    c.executar(amb.tmp / "nova")
    hashes = {f["id_doc"]: f["sha256"] for f in amb.fontes}
    assert amb.lidos and all(sha == hashes[caminho.stem] for caminho, sha in amb.lidos)


@pytest.mark.parametrize("falha", ["texto_ilegivel", "paginacao", "anexo_duplo", "vazamento_no_resultado"])
def test_nenhuma_recusa_da_busca_deixa_arquivo(tmp_path, monkeypatch, falha):
    """A7 (observação do parecer): estas recusas vinham depois de gravar a
    identidade, e esse estado não tinha contraprova. Agora nada é gravado."""
    amb = _ambiente(tmp_path, monkeypatch)
    if falha == "texto_ilegivel":
        monkeypatch.setattr(c, "paginas_pdf", lambda pdf, modo: [*_PAGINAS[pdf.decode()], "Total (cid:3) 1.234"])
        erro, mensagem = AssertionError, "texto ilegível"
    elif falha == "paginacao":
        def paginas(pdf, modo):
            raise AssertionError("paginação textual não coincide com o PDF")
        monkeypatch.setattr(c, "paginas_pdf", paginas)
        erro, mensagem = AssertionError, "paginação"
    elif falha == "anexo_duplo":
        monkeypatch.setattr(c, "anexos_pdf", lambda pacote: [(1, 193, pacote.stem.encode())] * 2)
        erro, mensagem = ValueError, "too many values"
    else:
        monkeypatch.setattr(c, "trecho_publicavel", lambda linha: {"trecho": "Total 1.234.567"})
        erro, mensagem = c.VazamentoDeValor, "dígito em trecho"
    with pytest.raises(erro, match=mensagem):
        c.executar(amb.tmp / "nova")
    assert not (amb.tmp / "nova").exists()


# --- Adendo 2 (26/09): ressalvas da reconferência ---

_ABREM_ORNAMENTAIS = [ch for ch in _ABREM_QUALQUER if ch not in _ABREM]
_FECHAM_ORNAMENTAIS = [ch for ch in _FECHAM_QUALQUER if ch not in _FECHAM]


@pytest.mark.parametrize("abre", _ABREM_ORNAMENTAIS, **_ID)
def test_parentese_ornamental_de_abertura_nao_fecha_negativo(abre):
    """B1 (achado 1 da reconferência): só o que se normaliza em `(` abre negativo.
    Pela definição por nome, `❨1.234)` sairia −1; a mutação sobrevivia."""
    assert _sinal_de(f"Total {abre}1.234)") is None
    assert c.ocorrencias([f"Total {abre}1.234)"], {"a": Decimal(-1234)}, por_modulo=False) == {"a": []}


@pytest.mark.parametrize("fecha", _FECHAM_ORNAMENTAIS, **_ID)
def test_parentese_ornamental_de_fechamento_nao_fecha_negativo(fecha):
    """B1: `(1.234❩` não é negativo — o ornamental depois do número é sinal colado."""
    assert _sinal_de(f"Total (1.234{fecha}") is None
    assert c.ocorrencias([f"Total (1.234{fecha}"], {"a": Decimal(-1234)}, por_modulo=False) == {"a": []}


def test_parenteses_ornamentais_dos_dois_lados_tambem_sao_ambiguos():
    for linha in ("Total \u2768" "1.234\u2769", "Total \ufd3e" "1.234\ufd3f", "Total \u2985" "1.234\u2986"):
        assert _sinal_de(linha) is None, linha


def test_limite_declara_o_residuo_do_sinal():
    """B2: combinante, seletores de variação e moeda com espaço interno ficam declarados."""
    assert "seletores de variação" in c.LIMITE and "moeda com espaço interno" in c.LIMITE


@pytest.mark.parametrize("texto,barrado", [("1\n234\n567", True), ("valor\n1.234.567\nfim", True),
                                           ("9\n999", False), ("linha\ncom texto", False)])
def test_quebra_de_linha_nao_derruba_a_autoverificacao(texto, barrado):
    """B3 (achado 3 da reconferência): `1\\n234` levantava TypeError em vez de decidir."""
    if barrado:
        with pytest.raises(c.VazamentoDeValor):
            c.verificar_sem_valores({"nota": texto}, [Decimal(1234567)])
    else:
        c.verificar_sem_valores({"nota": texto}, [Decimal(1234567)])


def test_reconferencia_registra_publicado_com_quebra_de_linha(tmp_path, monkeypatch):
    """B3: a reconferência registra `false`, não aborta."""
    amb = _ambiente(tmp_path, monkeypatch)
    _publicar_revisao(amb, monkeypatch)
    conferencia = json.loads((amb.revisao / "conferencia_revisao.json").read_text())
    conferencia["nota"] = "1\n234\n567"
    _refixar(monkeypatch, amb.revisao / "conferencia_revisao.json", conferencia, "CONFERENCIA_REVISAO_SHA256")
    resultado = _rodar("reconferir", amb)
    assert resultado["autoverificacao_estrita_nos_publicados"] == {
        "conferencia_revisao.json": False, "pin_revisao.json": True}


def test_campo_que_nao_e_json_nao_deixa_a_identidade_sozinha(tmp_path, monkeypatch):
    """B4 (achado 4 da reconferência): passava na autoverificação (Decimal < 1.000) e
    quebrava a serialização do resultado depois de gravar o pin."""
    amb = _ambiente(tmp_path, monkeypatch)
    monkeypatch.setattr(c, "formas_que_so_casam_com_decimais", lambda alvos: [Decimal("5")])
    with pytest.raises(TypeError, match="JSON serializable"):
        c.executar(amb.tmp / "nova")
    assert not (amb.tmp / "nova").exists()


# --- Adendo 3 (26/09): o limite declarado, dito inteiro e preso ao comportamento ---

def test_limite_declarado_descreve_o_comportamento_atual():
    """C2 do adendo 3 — teste de CARACTERIZAÇÃO de um limite declarado, não aprovação
    do defeito: prende o comportamento atual junto com a frase que o declara. Quem
    corrigir o limite tem de mudar este teste e o texto do `limite` juntos."""
    alvo = {"a": Decimal(1234)}
    for linha in ("Total \u2212\u034f1.234", "Total (\ufe00" "1.234\ufe00)", "Total -\u3164" "1.234",
                  "Total -R $ 1.234"):
        assert c.ocorrencias([linha], alvo, por_modulo=False)["a"], linha  # sinal perdido: casa positivo
        assert not c.ocorrencias_de_sinal_ambiguo([linha], alvo)["a"], linha
    assert c.ocorrencias(["Total 1.234.\u034f567"], alvo, por_modulo=False)["a"]  # prefixo casa
    for efeito in ("se perde, e o número pode casar como positivo", "dentro do número parte o token",
                   "o prefixo pode casar", "pré-condição para usar o instrumento em notas de outros emissores"):
        assert efeito in c.LIMITE, efeito
