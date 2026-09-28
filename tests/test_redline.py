"""Contratos do redline do piloto CAND-02-P (`src/redline.py`).

Os falsificadores do pré-registro do CAND-02 viram contraprovas aqui: número e
período rolados não podem virar mudança de texto, texto movido não é remoção
mais adição, cabeçalho e rodapé não fabricam evento, coluna de variação não é
período, e o B1 é lexicográfico na ordem registrada.
"""

from __future__ import annotations

import pytest

from src import redline as rl


def _doc(paginas: list[str], trimestre: str = "2T2025", nome: str = "d") -> rl.Documento:
    return rl.documento_de_paginas(nome, "X", trimestre, paginas)


def _eventos(antes: list[str], depois: list[str], ta="2T2025", td="3T2025"):
    return rl.gerar_eventos("X_par", _doc(antes, ta, "a"), _doc(depois, td, "b"))


# --- números e períodos ----------------------------------------------------------

@pytest.mark.parametrize("texto, valor, pct", [
    ("4.337,4", 4337.4, False), ("(1.040)", -1040.0, False), ("-18%", -18.0, True),
    ("28,1%", 28.1, True), ("11.423.711", 11423711.0, False), ("0,6 p.p.", 0.6, True),
])
def test_ler_numero_ptbr(texto, valor, pct):
    n = rl.ler_numero(texto)
    assert n is not None and n.valor == pytest.approx(valor) and n.percentual is pct


@pytest.mark.parametrize("texto", ["–", "-", "n.a.", "Receitas", "1.5", ""])
def test_ler_numero_recusa_o_que_nao_e_numero(texto):
    assert rl.ler_numero(texto) is None


@pytest.mark.parametrize("celula, esperado", [
    ("3T 2024", "3T2024"), ("3T24", "3T2024"), ("9M 2025", "9M2025"), ("2025", "A2025"),
    ("30/09/2025", "2025-09-30"), ("30.06.2025", "2025-06-30"), ("set/25", "2025-09"),
])
def test_periodo_canonico(celula, esperado):
    assert rl.periodo_canonico(celula) == esperado


@pytest.mark.parametrize("rotulo, esperado", [
    ("Trimestre 3T 2024", "3T2024"),
    ("Acumulado no ano 9M 2025", "9M2025"),
    ("Variação % para 3T 2025 2T 2025", None),
    ("4T25 x 3T25", None),
    ("Δ", None),
])
def test_periodo_da_coluna_nao_toma_variacao_por_periodo(rotulo, esperado):
    assert rl.periodo_da_coluna(rotulo) == esperado


def test_esqueleto_mascara_periodo_e_numero():
    a = "O lucro líquido atingiu R$4.337,4 milhões no 3T25, alta de 8,2%."
    b = "O lucro líquido atingiu R$4.539,1 milhões no 4T25, alta de 4,6%."
    assert rl.esqueleto(a) == rl.esqueleto(b)


def test_chave_tira_dolar_do_latex_e_mantem_moeda():
    assert rl.chave("Margem com clientes$$ – R$ milhões") == "margem com clientes – r$ milhoes"


# --- triagem do B1 ----------------------------------------------------------------

def test_triagem_em_bp_geral_e_de_credito():
    a, b = rl.Numero(15.5, True, 1), rl.Numero(15.9, True, 1)  # 40 bp
    assert not rl.mudanca_numerica(a, b, credito=False)["acima_da_triagem"]
    assert rl.mudanca_numerica(a, b, credito=True)["acima_da_triagem"]


def test_triagem_relativa_de_valor():
    base = rl.Numero(100.0, False, 0)
    assert not rl.mudanca_numerica(base, rl.Numero(109.0, False, 0), False)["acima_da_triagem"]
    assert rl.mudanca_numerica(base, rl.Numero(110.0, False, 0), False)["acima_da_triagem"]


def test_mudanca_de_sinal_passa_mesmo_pequena():
    m = rl.mudanca_numerica(rl.Numero(1.0, False, 0), rl.Numero(-1.0, False, 0), False)
    assert m["sinal"] and m["acima_da_triagem"]


def test_arredondamento_de_uma_unidade_nao_e_reapresentacao():
    a, b = rl.Numero(4009.0, False, 0), rl.Numero(4010.0, False, 0)
    assert rl.mudanca_numerica(a, b, False, unidades_de_tolerancia=1.0)["igual"]
    assert not rl.mudanca_numerica(a, b, False)["igual"]


# --- documento → blocos -----------------------------------------------------------

def test_cabecalho_e_rodape_repetidos_e_numero_de_pagina_saem():
    paginas = [f"Banco X | Relações com Investidores\n\n{n}\n\nO banco manteve a estratégia de "
               f"crescimento em crédito no segmento {n}." for n in range(1, 11)]
    doc = _doc(paginas)
    assert "Banco X | Relações com Investidores" in doc.ruido
    assert all("Relações com Investidores" not in s.texto for s in doc.sentencas)
    assert all(not s.texto.strip().isdigit() for s in doc.sentencas)


TABELA = """## Resumo

| Indicadores (em R$ milhões) | Trimestre |   |   | Variação % para 3T 2025 |   |
| --- | --- | --- | --- | --- | --- |
|   | 3T 2024 | 2T 2025 | 3T 2025 | 3T 2024 | 2T 2025 |
| Lucro líquido | 3.068 | 4.009 | 4.337 | 41% | 8% |
| Receitas | Taxa |  |  |  |  |
"""


def test_tabela_com_cabecalho_mesclado_e_variacao():
    doc = _doc([TABELA], trimestre="3T2025")
    (linha,) = doc.linhas
    assert linha.rotulo == "Lucro líquido"
    assert linha.periodos == ("3T2024", "2T2025", "3T2025")
    assert linha.celulas == ("3.068", "4.009", "4.337")


def test_sub_cabecalho_sem_numero_nao_e_linha_de_dado():
    doc = _doc([TABELA], trimestre="3T2025")
    assert all(l.rotulo != "Receitas" for l in doc.linhas)


# --- par → eventos ----------------------------------------------------------------

def test_texto_identico_em_outra_posicao_e_movimento():
    s1 = "O banco manteve a estratégia de crescimento em crédito consignado."
    s2 = "A inadimplência acima de 90 dias ficou estável no segmento de varejo."
    assert _eventos([f"{s1}\n\n{s2}"], [f"{s2}\n\n{s1}"]) == []


def test_movimento_e_resolvido_antes_do_pareamento_por_esqueleto():
    """Duas frases de mesmo esqueleto: uma só muda de lugar, a outra muda de
    número. Sem a etapa de identidade, o esqueleto pareava a movida com a
    alterada e fabricava 16,2% → 15,0% (mutante que sobreviveu à primeira
    versão desta suíte)."""
    alterada_antes = "O índice de Basileia do conglomerado encerrou o período em 16,2%."
    movida = "O índice de Basileia do conglomerado encerrou o período em 15,0%."
    alterada_depois = "O índice de Basileia do conglomerado encerrou o período em 15,5%."
    enchimento = "\n\n".join(f"Parágrafo de contexto número {n} sobre a estratégia de varejo." for n in "abcdef")
    antes = [f"{alterada_antes}\n\n{enchimento}\n\n{movida}"]
    depois = [f"{movida}\n\n{enchimento}\n\n{alterada_depois}"]
    (ev,) = _eventos(antes, depois)
    assert ev.antes == alterada_antes and ev.depois == alterada_depois


def test_so_o_periodo_rolou_nao_e_evento():
    a = "Os resultados do 2T25 refletem a estratégia de rentabilidade do banco."
    b = "Os resultados do 3T25 refletem a estratégia de rentabilidade do banco."
    assert _eventos([a], [b]) == []


def test_numero_rolado_e_alteracao_com_triagem():
    a = "O índice de Basileia encerrou o trimestre em 16,2% no consolidado prudencial."
    b = "O índice de Basileia encerrou o trimestre em 15,5% no consolidado prudencial."
    (ev,) = _eventos([a], [b])
    assert ev.operacao == "alteracao" and ev.tipo == "texto"
    assert ev.nivel1 and "capital_liquidez" in ev.categorias


def test_frase_nova_e_adicao_e_frase_retirada_e_remocao():
    fica = "O banco manteve a estratégia de crescimento em crédito consignado."
    sai = "Esperamos crescimento da carteira entre 8% e 12% no ano de 2025."
    entra = "Aprovamos programa de recompra de até 5% das ações em circulação."
    ev = _eventos([f"{fica}\n\n{sai}"], [f"{fica}\n\n{entra}"])
    assert sorted(e.operacao for e in ev) == ["adicao", "remocao"]


def test_linha_de_tabela_compara_o_trimestre_do_documento():
    antes = TABELA
    depois = TABELA.replace("3T 2024 | 2T 2025 | 3T 2025", "4T 2024 | 3T 2025 | 4T 2025").replace(
        "3.068 | 4.009 | 4.337", "3.500 | 4.337 | 4.539")
    ev = rl.gerar_eventos("X", _doc([antes], "3T2025", "a"), _doc([depois], "4T2025", "b"))
    (e,) = ev
    principal = [m for m in e.mudancas_numericas if m.get("coluna") == "principal"]
    assert principal and principal[0]["antes"] == 4337 and principal[0]["depois"] == 4539
    assert not e.reapresentacao


def test_mesmo_periodo_com_valor_diferente_e_reapresentacao():
    depois = TABELA.replace("3T 2024 | 2T 2025 | 3T 2025", "4T 2024 | 3T 2025 | 4T 2025").replace(
        "3.068 | 4.009 | 4.337", "3.500 | 4.100 | 4.539")
    ev = rl.gerar_eventos("X", _doc([TABELA], "3T2025", "a"), _doc([depois], "4T2025", "b"))
    (e,) = ev
    assert e.reapresentacao and e.nivel1
    assert any(m.get("coluna") == "mesmo_periodo:3T2025" for m in e.mudancas_numericas)


def test_tabela_identica_nao_gera_evento():
    assert rl.gerar_eventos("X", _doc([TABELA], "3T2025", "a"), _doc([TABELA], "3T2025", "b")) == []


def test_ids_sao_deterministicos():
    a = ["Esperamos crescimento da carteira entre 8% e 12% no ano de 2025."]
    b = ["Esperamos crescimento da carteira entre 9% e 13% no ano de 2025."]
    assert [e.id for e in _eventos(a, b)] == [e.id for e in _eventos(a, b)]


# --- B0, B1 e nDCG ----------------------------------------------------------------

def _ev(**kw) -> rl.Evento:
    base = dict(id="x", par="p", operacao="alteracao", tipo="texto", pagina_antes=1,
                pagina_depois=1, secao="", antes="a", depois="b")
    base.update(kw)
    return rl.Evento(**base)


def test_b1_e_lexicografico_na_ordem_registrada():
    numero = _ev(id="n", mudancas_numericas=[{"acima_da_triagem": True}], massa=1)
    categoria = _ev(id="c", categorias=["credito"], massa=50)
    adicao = _ev(id="a", operacao="adicao", massa=100)
    massa = _ev(id="m", massa=500)
    assert [e.id for e in rl.ordenar_b1([massa, adicao, categoria, numero])] == ["n", "c", "a", "m"]


def test_b0_ordena_por_massa_com_desempate_por_pagina():
    e1, e2, e3 = _ev(id="1", massa=5, pagina_depois=9), _ev(id="2", massa=5, pagina_depois=2), _ev(id="3", massa=9)
    assert [e.id for e in rl.ordenar_b0([e1, e2, e3])] == ["3", "2", "1"]


def test_ndcg():
    ganhos = {"a": 3.0, "b": 1.0, "c": 0.0}
    assert rl.ndcg(["a", "b", "c"], ganhos, 10) == pytest.approx(1.0)
    assert rl.ndcg(["c", "b", "a"], ganhos, 10) < 1.0
    assert rl.ndcg(["x"], {"x": 0.0}, 10) is None
