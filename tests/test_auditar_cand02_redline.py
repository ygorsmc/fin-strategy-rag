from __future__ import annotations

import csv
import inspect

import pytest

from scripts import auditar_cand02_redline as cand02
from src.ingestao import DocumentoCorpus


def _documentos() -> list[DocumentoCorpus]:
    documentos = []
    for empresa in ("A", "B", "C", "D", "E"):
        for trimestre in ("2T2025", "3T2025", "4T2025", "1T2026"):
            nome = f"{empresa}_{trimestre}"
            documentos.append(
                DocumentoCorpus(
                    empresa=empresa,
                    trimestre=trimestre,
                    documento=nome,
                    url=f"https://example.test/{nome}.pdf",
                    data_coleta="2026-08-27",
                    hash_sha256="a" * 64,
                )
            )
    return documentos


def test_split_temporal_nao_compartilha_pdf_entre_dev_e_teste():
    pares = cand02.construir_pares(_documentos())
    por_papel = {
        papel: [par for par in pares if par.papel == papel]
        for papel in ("desenvolvimento", "embargo", "teste")
    }
    assert all(len(por_papel[papel]) == 5 for papel in por_papel)
    docs_dev = {
        doc
        for par in por_papel["desenvolvimento"]
        for doc in (par.documento_anterior, par.documento_atual)
    }
    docs_teste = {
        doc
        for par in por_papel["teste"]
        for doc in (par.documento_anterior, par.documento_atual)
    }
    assert docs_dev.isdisjoint(docs_teste)


def test_cinco_emissores_sao_cinco_clusters_nao_centenas_de_eventos():
    resultado = cand02.auditar(_documentos())
    corpus = resultado["corpus"]
    assert corpus["n_pares_adjacentes"] == 15
    assert corpus["clusters_independentes_no_teste"] == 5


def test_sem_dupla_leitura_e_tempo_falha_antes_de_carregar_ml():
    resultado = cand02.auditar(_documentos())
    assert resultado["estado_cientifico"] == "INDECIDIVEL"
    assert resultado["decisao_de_implementacao_ml"] == "NAO_IMPLEMENTAR_AGORA"
    assert set(resultado["razoes"]) == {
        "gabarito_duplo_insuficiente_ou_ausente",
        "leitura_completa_e_adjudicacao_ausentes",
        "estudo_humano_de_tempo_ausente",
    }
    fonte = inspect.getsource(cand02)
    assert "sentence_transformers" not in fonte
    assert "src.indexacao" not in fonte


def test_alpha_ordinal_perfeito_e_um_quadro_discordante():
    perfeito = cand02.alpha_krippendorff_ordinal([(0, 0), (1, 1), (2, 2)])
    discordante = cand02.alpha_krippendorff_ordinal(
        [(0, 2), (2, 0), (1, 1), (0, 2)]
    )
    assert perfeito == pytest.approx(1.0)
    assert discordante < 0.67


def test_trimestre_ausente_nao_vira_par_adjacente():
    documentos = [
        doc
        for doc in _documentos()
        if not (doc.empresa == "A" and doc.trimestre == "3T2025")
    ]
    with pytest.raises(ValueError, match="não adjacentes"):
        cand02.construir_pares(documentos)


def test_manifesto_de_cinco_pares_nao_finge_cobrir_os_quinze(tmp_path):
    pares = cand02.construir_pares(_documentos())
    caminho = tmp_path / "leitura.csv"
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=cand02.COLUNAS_LEITURA)
        escritor.writeheader()
        for par in pares:
            if par.papel == "teste":
                escritor.writerow(
                    {
                        "pair_id": par.pair_id,
                        "reader_a": "analista_a",
                        "reader_b": "analista_b",
                        "adjudicator": "analista_c",
                        "leitura_completa": "1",
                    }
                )
    resultado = cand02.auditar_leitura_completa(caminho, pares)
    assert len(resultado["pares_com_dupla_leitura_completa"]) == 5
    assert resultado["gate_aprovado"] is False
