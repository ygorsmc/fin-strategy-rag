from __future__ import annotations

import inspect
from pathlib import Path

from scripts import auditar_rank05_divergencia_gerencial_contabil as rank05


def test_termo_lajida_exige_palavra_inteira():
    assert rank05.TERMOS_L.search("A companhia divulgou LAJIDA ajustado.")
    assert rank05.TERMOS_L.search("EBITDA")
    assert rank05.TERMOS_L.search("EBIT")
    assert not rank05.TERMOS_L.search("DEBITADO")
    assert not rank05.TERMOS_L.search("prelajida")


def test_ponte_explicita_exige_tabela_larga_e_numerica():
    indice = "| Reconciliação contábil e gerencial | 20 |"
    narrativa = "A companhia explica a diferença contábil e gerencial."
    ponte = """
| R$ milhões | Contábil | Ajustes | Gerencial |
| --- | ---: | ---: | ---: |
| Lucro líquido | 100 | 7 | 107 |
"""
    assert rank05.detectar_ponte_explicita(indice) is False
    assert rank05.detectar_ponte_explicita(narrativa) is False
    assert rank05.detectar_ponte_explicita(ponte) is True


def test_ponte_ajustada_detecta_formato_btg():
    ponte = """
| R$ milhões | 1T 2026 Contábil | Itens não recorrentes | 1T 2026 Ajustado |
| --- | ---: | ---: | ---: |
| Lucro líquido | 4.570,4 | 237,7 | 4.808,1 |
"""
    assert rank05.detectar_ponte_resultado_ajustado(ponte) is True


def test_ponte_ajustada_detecta_fechamento_em_tres_linhas():
    ponte = """
| R$ milhões | 4T25 | 4T24 |
| --- | ---: | ---: |
| Lucro Líquido Ajustado | 10.000 | 9.000 |
| Itens Extraordinários | 200 | -100 |
| Lucro Líquido | 9.800 | 9.100 |
"""
    assert rank05.detectar_ponte_resultado_ajustado(ponte) is True


def test_mencao_generica_a_resultado_ajustado_nao_vira_ponte():
    narrativa = "O lucro líquido ajustado cresceu 10% no trimestre."
    tabela_sem_fechamento = """
| R$ milhões | 4T25 | 4T24 |
| --- | ---: | ---: |
| Lucro Líquido Ajustado | 10.000 | 9.000 |
"""
    assert rank05.detectar_ponte_resultado_ajustado(narrativa) is False
    assert rank05.detectar_ponte_resultado_ajustado(tabela_sem_fechamento) is False


def test_corpus_congelado_mede_observabilidade_sem_fabricar_gold():
    documentos, colunas = rank05.carregar_metadados(Path("corpus/metadados.csv"))
    resultado = rank05.auditar(
        documentos,
        colunas,
        diretorio_ocr=Path("corpus/ocr"),
    )
    observabilidade = resultado["observabilidade"]
    assert resultado["corpus"]["n_documentos"] == 20
    assert resultado["corpus"]["n_empresas"] == 5
    assert resultado["corpus"]["n_paginas"] == 2790
    assert observabilidade["L_lajida_lajir"]["documentos"] == 0
    assert observabilidade["K_ponte_explicita_contabil_gerencial"] == {
        "documentos": 12,
        "empresas": ["BRADESCO", "ITAU", "SANTANDER"],
        "paginas": 16,
    }
    assert observabilidade["K_ponte_resultado_ajustado"]["documentos"] == 20
    assert observabilidade["K_ponte_resultado_ajustado"]["empresas"] == [
        "BB",
        "BRADESCO",
        "BTG",
        "ITAU",
        "SANTANDER",
    ]
    assert resultado["evidencia_humana"]["gold_presente"] is False
    assert resultado["gates"]["G0_K_observabilidade_ponte_bancaria"] is True
    assert resultado["gates"]["G1_procedencia_point_in_time"] is False
    assert resultado["gates"]["G4_amostra_minima_30_releases_10_emissores"] is False
    assert resultado["estado_cientifico_ml"] == "INDECIDIVEL"
    assert resultado["decisao_de_engenharia_ml"] == "NAO_IMPLEMENTAR_ML_AGORA"
    assert resultado["modelo_carregado"] is False


def test_auditor_nao_importa_stack_de_modelagem():
    fonte = inspect.getsource(rank05)
    for proibido in (
        "sklearn",
        "torch",
        "transformers",
        "sentence_transformers",
        "src.modelo",
        "src.indexacao",
    ):
        assert proibido not in fonte
