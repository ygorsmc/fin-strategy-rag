"""GEOM-1: controles de célula em layouts observados, sem dados/valores reais."""
from copy import deepcopy
from datetime import date

import pytest

from scripts import fonte_rad_cvm as rad
from scripts import provas_geometricas_rank03b as g
from scripts.reconhecer_geometria_rank03b import escolher, mascarar


def w(t, x, y, largura=50):
    return dict(texto=t, xMin=x, xMax=x + largura, yMin=y, yMax=y + 9)


def fixture(forma="bruto", negativo=False, inversa=False, unico=False):
    datas = ["30/09/2024", "31/12/2023"]
    valores = [3456000, 3333000, 2345000, 2222000]
    if inversa:
        datas.reverse()
        valores = [3333000, 3456000, 2222000, 2345000]
    fator = 1000 if forma == "dividido" else 1
    celulas = [format(v // fator, ",").replace(",", ".") for v in valores]
    if negativo:
        celulas = [f"({v})" for v in celulas]
    xs = [250, 320, 400, 470]
    per = [w("Controladora", 290, 100, 65), w("Consolidado", 440, 100, 65)]
    ds = datas * 2
    if unico:
        xs, celulas, ds, per = xs[2:], celulas[2:], ds[2:], per[1:]
    row = [w("Caixa e equivalentes de caixa", 50, 138, 160)]
    row += [w(v, x + 20, 138, 30) for x, v in zip(xs, celulas)]
    pagina = dict(largura=595, altura=842, linhas=[
        [w("(Em milhares de reais)", 50, 50, 180)], per,
        [w(d, x, 112) for d, x in zip(ds, xs)], row])
    sinal = -1 if negativo else 1
    form = rad.Formulario("fixture", "1", {}, [
        ("1.01.01", None, date(2024, 9, 30), 2345000 * sinal),
        ("1.01.01", None, date(2023, 12, 31), 2222000 * sinal)],
        valores_individuais=[("1.01.01", None, date(2024, 9, 30), 3456000 * sinal)])
    return form, pagina


def medir(form, p):
    return g.evidencia(form, [(1, "a" * 64, [p])], "2024-09-30")


@pytest.mark.parametrize("forma", ["bruto", "dividido"])
@pytest.mark.parametrize("negativo", [False, True])
@pytest.mark.parametrize("inversa", [False, True])
@pytest.mark.parametrize("unico", [False, True])
def test_celula_identificada_antes_do_match(forma, negativo, inversa, unico):
    f, p = fixture(forma, negativo, inversa, unico)
    r = medir(f, p)
    assert r["classe"] == forma
    assert len(r["provas"]) == 1
    prova = r["provas"][0]
    assert prova["datas"][prova["coluna"] - 1] == "2024-09-30"
    assert prova["perimetro"] == "consolidado"
    assert all(not any(c.isdigit() for c in v["texto"]) for v in prova["linha_saldo"])


@pytest.mark.parametrize("mutacao", [
    "conta_vizinha", "subtotal", "fluxo", "caixa_com_aplicacoes", "saldo_inicial",
    "sem_unidade", "unidade_rodape", "unidade_contraria", "moeda_contraria",
    "sem_perimetro", "so_controladora", "perimetro_desalinhado", "data_invalida",
    "comparativo", "data_repetida", "grupos_desiguais", "celula_ausente",
    "celula_outra_conta", "numero_entre_celulas", "zero", "traco", "novo_cabecalho",
    "prosa_entre_tabelas", "outra_pagina", "alinhamento_ambiguo", "coordenada_invalida",
    "oposto_na_unicidade", "multiplicador_ambiguo", "distancia_grande",
])
def test_nao_certifica_falsa_prova(mutacao):
    f, p = fixture()
    ls = p["linhas"]
    row = ls[-1]
    nomes = {"conta_vizinha": "Fornecedores", "subtotal": "Total do ativo circulante",
             "fluxo": "Efeito cambial sobre investimento", "caixa_com_aplicacoes":
             "Caixa e equivalentes de caixa e aplicações financeiras",
             "saldo_inicial": "Caixa e equivalentes de caixa no início do período"}
    if mutacao in nomes:
        row[0]["texto"] = nomes[mutacao]
    elif mutacao == "sem_unidade": ls.pop(0)
    elif mutacao == "unidade_rodape": ls[0][0].update(yMin=750, yMax=759)
    elif mutacao in ("unidade_contraria", "moeda_contraria"):
        ls.insert(1, [w("Em milhões de reais" if mutacao == "unidade_contraria" else "US$", 50, 80)])
    elif mutacao == "sem_perimetro": ls.pop(1)
    elif mutacao == "so_controladora": ls[1][1]["texto"] = "Individual"
    elif mutacao == "perimetro_desalinhado": ls[1][1].update(xMin=530, xMax=590)
    elif mutacao == "data_invalida": ls[2][2]["texto"] = "31/09/2024"
    elif mutacao == "comparativo": ls[2][2]["texto"] = "30/09/2023"
    elif mutacao == "data_repetida": ls[2][3]["texto"] = "30/09/2024"
    elif mutacao == "grupos_desiguais": ls[2].pop()
    elif mutacao == "celula_ausente": row.pop(3)
    elif mutacao == "celula_outra_conta": row.insert(3, w("Fornecedores", 355, 138, 60))
    elif mutacao == "numero_entre_celulas": row.insert(3, w("999.999", 360, 138, 25))
    elif mutacao == "zero": row[3]["texto"] = "0"
    elif mutacao == "traco": row[3]["texto"] = "-"
    elif mutacao == "novo_cabecalho": ls.insert(3, [w("Controladora", 440, 124, 65)])
    elif mutacao == "prosa_entre_tabelas": ls.insert(3, [w("Texto que inicia outra seção", 50, 125, 200)])
    elif mutacao == "outra_pagina": p["linhas"] = ls[2:]
    elif mutacao == "alinhamento_ambiguo": row.append(w("2.345.000", 418, 138, 30))
    elif mutacao == "coordenada_invalida": row[3]["xMin"] = float("nan")
    elif mutacao == "oposto_na_unicidade": f.valores.append(("1.01.01", None, date(2024, 9, 30), -2345000))
    elif mutacao == "multiplicador_ambiguo": f.valores_individuais.append(("1.01.01", None, date(2024, 9, 30), 2345))
    elif mutacao == "distancia_grande":
        for v in row: v.update(yMin=500, yMax=509)
    assert medir(f, p)["classe"] == "nenhum"


def test_valor_certo_na_controladora_nao_salva_coluna_errada():
    f, p = fixture()
    p["linhas"][-1][1]["texto"] = "2.345.000"
    p["linhas"][-1][3]["texto"] = "9.999.999"
    assert medir(f, p)["classe"] == "nenhum"


def test_multiplas_provas_conflitantes_nao_ocultadas():
    f, p = fixture()
    _, q = fixture(forma="dividido")
    r = g.evidencia(f, [(1, "a" * 64, [p, q])], "2024-09-30")
    assert r["classe"] == "conflitante"
    assert len(r["provas"]) == 2


@pytest.mark.parametrize("campo,valor", [("conta", "1"), ("coluna", 1), ("pagina", 2),
                                      ("sha256_pdf", "b" * 64), ("forma", "dividido")])
def test_consumidor_recusa_prova_alterada(monkeypatch, campo, valor):
    f, p = fixture()
    r = medir(f, p)
    monkeypatch.setattr(g, "extrair_documento", lambda *args: r)
    prova = deepcopy(r["provas"][0])
    assert g.conferir_prova(prova, "fonte", "2024-09-30", "hash")
    prova[campo] = valor
    with pytest.raises(AssertionError, match="não reproduzida"):
        g.conferir_prova(prova, "fonte", "2024-09-30", "hash")


def test_hash_errado_bloqueia_antes_da_leitura(monkeypatch, tmp_path):
    p = tmp_path / "arquivo"
    p.write_bytes(b"fonte")
    monkeypatch.setattr(rad, "ler", lambda *args, **kwargs: pytest.fail("leitura indevida"))
    with pytest.raises(AssertionError, match="fonte pinada"):
        g.extrair_documento(p, "2024-09-30", "errado")


@pytest.mark.parametrize("classe", ["nenhum", "conflitante"])
def test_consumidor_nao_aprova_so_por_prova_presente(monkeypatch, classe):
    f, p = fixture()
    r = medir(f, p)
    prova = r["provas"][0]
    r["classe"] = classe
    monkeypatch.setattr(g, "extrair_documento", lambda *args: r)
    with pytest.raises(AssertionError, match="fonte conflitante"):
        g.conferir_prova(prova, "fonte", "2024-09-30", "hash")


@pytest.mark.parametrize("valor,celula,esperado", [
    (2345000.49, "2.345.000", "bruto"),
    (2345000.51, "2.345.000", "nenhum"),
    (2345000.5, "2.345.000", "bruto"),
    (2345001.5, "2.345.002", "bruto"),
    (2345000.5, "2.345.000,50", "bruto"),
    (2345000.5, "2.345.000,49", "nenhum"),
    (999000, "999", "nenhum"),
])
def test_arredondamento_decimal_e_piso(valor, celula, esperado):
    f, p = fixture()
    f.valores[0] = ("1.01.01", None, date(2024, 9, 30), valor)
    p["linhas"][-1][3]["texto"] = celula
    assert medir(f, p)["classe"] == esperado


def test_coluna_de_nota_explicita_e_datas_pontuadas():
    f, p = fixture()
    for v in p["linhas"][2]:
        v["texto"] = v["texto"].replace("/", ".")
    p["linhas"][2].insert(0, w("Nota", 215, 112, 20))
    p["linhas"][-1].insert(1, w("3", 230, 138, 5))
    assert medir(f, p)["classe"] == "bruto"
    p["linhas"][2].pop(0)
    assert medir(f, p)["classe"] == "nenhum"


@pytest.mark.parametrize("unidade", [
    "(Em milhares de reais, exceto caixa e equivalentes de caixa em reais)",
    "(Em milhares de reais, exceto valores do caixa em milhões)",
    "Em unidades de reais", "Valores em centavos", "Em milhares de libras esterlinas",
])
@pytest.mark.parametrize("local", ["propria_unidade", "intermediaria"])
def test_ressalva_e_unidade_desconhecida_nao_certificam_caixa(unidade, local):
    f, p = fixture()
    if local == "propria_unidade":
        p["linhas"][0][0]["texto"] = unidade
    else:
        p["linhas"].insert(1, [w(unidade, 50, 80, 450)])
    assert medir(f, p)["classe"] == "nenhum"


@pytest.mark.parametrize("dimensao", ["largura", "altura"])
@pytest.mark.parametrize("valor", [float("inf"), float("nan"), -1, 0])
def test_dimensoes_invalidas_nao_certificam(dimensao, valor):
    f, p = fixture()
    p[dimensao] = valor
    assert medir(f, p)["classe"] == "nenhum"


@pytest.mark.parametrize("modo", ["completo", "absoluto_adulterado", "ausente"])
def test_pin_exige_manifesto_absoluto_e_cobertura_integral(monkeypatch, modo):
    from scripts import piloto_geometria_rank03b as piloto
    nomes = ["artefatos/painel_pesquisa_rank03b/adjudicacao/evidencias.jsonl",
             "artefatos/cvm.duckdb", "artefatos/cvm_treino.duckdb",
             "corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv",
             "artefatos/painel_pesquisa_rank03b/painel.duckdb",
             "artefatos/painel_pesquisa_rank03b/gates_g0_g1.json", str(rad.MANIFESTO)]
    pin = {"entradas_sha256": {n: "hash" for n in nomes}}
    monkeypatch.setattr(rad, "sha256", lambda p: "hash")
    if modo == "completo":
        assert len(piloto.conferir_protegidos(pin)) == 7
    else:
        if modo == "absoluto_adulterado": pin["entradas_sha256"][str(rad.MANIFESTO)] = "errado"
        else: del pin["entradas_sha256"][str(rad.MANIFESTO)]
        with pytest.raises(AssertionError):
            piloto.conferir_protegidos(pin)


def test_selecao_deterministica_sem_emissor_compartilhado():
    registros = [dict(id_doc=str(i), cd_cvm=str(i // 2), conjunto="ITR", dt_refer="2024-09-30",
                      versao=1, formato="xml_unico" if i % 2 else "formulario_zip",
                      escala_declarada="MIL" if i % 4 < 2 else "UNIDADE", sha256="a" * 64)
                 for i in range(100)]
    s = escolher(registros)
    assert escolher(list(reversed(registros))) == s
    assert len(s["desenho"]) == 8 and len(s["verificacao"]) == 12
    assert not ({r["cd_cvm"] for r in s["desenho"]} & {r["cd_cvm"] for r in s["verificacao"]})


def test_mascara_preserva_so_data_completa():
    t = mascarar("30/09/2024 7.456.123 (123,45) Caixa")
    assert t == "30/09/2024 [n] ([n]) Caixa"
