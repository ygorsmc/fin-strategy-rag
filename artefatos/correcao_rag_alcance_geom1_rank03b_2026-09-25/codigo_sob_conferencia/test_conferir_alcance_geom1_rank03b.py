"""Revisão do alcance GEOM-1 (R3): busca exata sem publicar valor nem sinal de FCO."""
from decimal import Decimal
import hashlib
import json
import xml.etree.ElementTree as ET

import pytest

from scripts import conferir_alcance_geom1_rank03b as c


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


def test_numeros_da_linha_com_sinal_por_parenteses_e_por_traco_unicode():
    linha = "Total dos ativos 123.456 (7.890) − 1.000 ‐ 5 +12 2.345.678,5"
    assert c.numeros_da_linha(linha) == [(1, 123456), (2, -7890), (3, -1000), (4, -5), (5, 12),
                                         (6, Decimal("2345678.5"))]


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


def test_autoverificacao_isenta_so_hash_e_data():
    """**Substitui, declaradamente, `test_autoverificacao_aceita_identidade_e_numeros_pequenos`**
    (24/09), que fixava também a isenção de `id_doc` e de outros campos de
    identidade. O contrato R3 só isenta hash e data; a auditoria de 25/09 (B1)
    apontou o desvio. Hash, data, números pequenos e trecho mascarado continuam
    aceitos — o que mudou foi só a lista de isentos."""
    saida = {"pdf_sha256": "1234567" * 9, "codigo_sha256": {"a.py": "1234567"},
             "data": "2026-09-24", "dt_refer": "1234567", "pagina": 42, "coluna": 5, "ok": True,
             "vazio": None, "trecho": "Total dos ativos [valor omitido]", "limite": "sem número"}
    c.verificar_sem_valores(saida, [Decimal("1234567"), Decimal("140867")])


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
    base = _base_falsa(tmp_path, b"inventario")
    (base / "pin_execucao.json").write_text(
        '{"codigo_sha256": {' + ", ".join(f'"{p}": "{"0" * 64}"' for p in c.CODIGO_CONGELADO) + "}}")
    monkeypatch.setattr(c, "BASE", base)
    monkeypatch.setattr(c, "INVENTARIO_PUBLICADO_SHA256", hashlib.sha256(b"inventario").hexdigest())
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
