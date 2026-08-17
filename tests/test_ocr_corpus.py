"""Contrato do cache de OCR versionado (`corpus/ocr/`) — spec 5.3, RNF10.

Nenhum teste toca rede, chave ou o cache real: tudo é fixture. O que se cobre
aqui é a fronteira em que um artefato deixa de corresponder ao manifesto —
ponto exato em que um índice "reprodutível" passaria a ser uma ficção.
"""

from __future__ import annotations

import json

import pytest

from src import ocr_corpus
from src.ingestao import DocumentoCorpus
from tests.fixtures.cache_ocr import escrever_cache_ocr


def _doc(**campos) -> DocumentoCorpus:
    valores = dict(
        empresa="BB",
        trimestre="1T2026",
        documento="bb_release_1T2026",
        url="https://exemplo.invalido/bb.pdf",
        data_coleta="2026-08-11",
        hash_sha256="a" * 64,
    )
    valores.update(campos)
    return DocumentoCorpus(**valores)


def _carregar(doc: DocumentoCorpus, dir_cache, **campos):
    argumentos = dict(
        documento=doc.documento,
        empresa=doc.empresa,
        trimestre=doc.trimestre,
        sha256_pdf=doc.hash_sha256,
        modelo_esperado="mistral-ocr-4-0",
        dir_cache=dir_cache,
    )
    argumentos.update(campos)
    return ocr_corpus.carregar_documento_ocr(**argumentos)


class TestLeituraDoCache:
    def test_le_paginas_em_markdown_com_numeracao_1_indexada(self, tmp_path):
        doc = _doc()
        caminho = escrever_cache_ocr(
            tmp_path, doc, ["# Capa", "| a | b |\n| --- | --- |\n| 1 | 2 |"]
        )
        carregado = _carregar(doc, tmp_path)
        assert [p.numero for p in carregado.paginas] == [1, 2]
        assert [p.indice for p in carregado.paginas] == [0, 1]
        assert carregado.paginas[1].markdown.startswith("| a | b |")
        assert carregado.modelo == "mistral-ocr-4-0"
        assert carregado.hash_artefato == ocr_corpus._sha256_arquivo(caminho)

    def test_arquivo_e_endereçado_pelo_hash_do_pdf_no_manifesto(self, tmp_path):
        doc = _doc()
        escrever_cache_ocr(tmp_path, doc, ["Conteúdo."])
        assert (tmp_path / f"{doc.hash_sha256}.json").is_file()
        assert ocr_corpus.caminho_documento_ocr(doc.hash_sha256, tmp_path) == (
            tmp_path / f"{doc.hash_sha256}.json"
        )

    def test_cache_ausente_diz_o_que_fazer(self, tmp_path):
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="Cache de OCR ausente"):
            _carregar(_doc(), tmp_path)

    def test_sha_invalido_nao_vira_caminho(self, tmp_path):
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="hexadecimais"):
            ocr_corpus.caminho_documento_ocr("../../etc/passwd", tmp_path)


class TestCacheContraManifesto:
    @pytest.mark.parametrize(
        "campo,valor",
        [
            ("documento", "outro_release_1T2026"),
            ("empresa", "ITAU"),
            ("trimestre", "4T2025"),
        ],
    )
    def test_divergencia_de_identificacao_falha_fechado(
        self, tmp_path, campo, valor
    ):
        """Cache com identificação diferente do manifesto indexaria o release
        de um banco sob o rótulo de outro — sem erro visível na consulta."""
        doc = _doc()
        escrever_cache_ocr(tmp_path, doc, ["Conteúdo."])
        with pytest.raises(ocr_corpus.ErroCacheOCR, match=campo):
            _carregar(doc, tmp_path, **{campo: valor})

    def test_hash_pdf_interno_precisa_bater_com_o_nome_do_arquivo(self, tmp_path):
        doc = _doc()
        caminho = escrever_cache_ocr(tmp_path, doc, ["Conteúdo."])
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        bruto["hash_pdf"] = "b" * 64
        caminho.write_text(json.dumps(bruto), encoding="utf-8")
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="hash_pdf"):
            _carregar(doc, tmp_path)

    def test_modelo_diferente_do_configurado_falha(self, tmp_path):
        doc = _doc()
        escrever_cache_ocr(
            tmp_path, doc, ["Conteúdo."], modelo="mistral-ocr-3-9"
        )
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="outro modelo"):
            _carregar(doc, tmp_path)

    def test_modelo_da_resposta_diferente_do_declarado_falha(self, tmp_path):
        doc = _doc()
        escrever_cache_ocr(
            tmp_path,
            doc,
            ["Conteúdo."],
            modelo_resposta="modelo-que-ninguem-pediu",
        )
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="Modelo da resposta"):
            _carregar(doc, tmp_path)

    def test_campo_novo_no_artefato_e_mudanca_de_contrato(self, tmp_path):
        doc = _doc()
        escrever_cache_ocr(
            tmp_path, doc, ["Conteúdo."], campos_extras={"job_id": "0eb6eab2"}
        )
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="Esquema inesperado"):
            _carregar(doc, tmp_path)


class TestIntegridadeDasPaginas:
    def test_pagina_vazia_falha_fechado(self, tmp_path):
        doc = _doc()
        escrever_cache_ocr(tmp_path, doc, ["Conteúdo.", "   \n"])
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="vazia"):
            _carregar(doc, tmp_path)

    def test_indice_duplicado_falha_fechado(self, tmp_path):
        doc = _doc()
        escrever_cache_ocr(tmp_path, doc, ["Um.", "Dois."], indices=[0, 0])
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="duplicada"):
            _carregar(doc, tmp_path)

    def test_paginas_faltando_no_meio_falham_fechado(self, tmp_path):
        """Buraco na numeração viraria citação de página errada (RN01)."""
        doc = _doc()
        escrever_cache_ocr(tmp_path, doc, ["Um.", "Três."], indices=[0, 2])
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="contíguas"):
            _carregar(doc, tmp_path)

    def test_contagem_declarada_diferente_das_paginas_presentes_falha(
        self, tmp_path
    ):
        doc = _doc()
        escrever_cache_ocr(tmp_path, doc, ["Um.", "Dois."], pages_processed=3)
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="pages_processed"):
            _carregar(doc, tmp_path)

    def test_confianca_ausente_e_aceita_e_declarada_como_ausente(self, tmp_path):
        doc = _doc()
        escrever_cache_ocr(tmp_path, doc, ["Conteúdo."], confiancas=None)
        pagina = _carregar(doc, tmp_path).paginas[0]
        assert pagina.confianca_media is None
        assert pagina.confianca_minima is None

    def test_confianca_presente_e_preservada(self, tmp_path):
        doc = _doc()
        escrever_cache_ocr(
            tmp_path, doc, ["Conteúdo."], confiancas=[(0.98, 0.44)]
        )
        pagina = _carregar(doc, tmp_path).paginas[0]
        assert (pagina.confianca_media, pagina.confianca_minima) == (0.98, 0.44)

    def test_confianca_incoerente_falha_fechado(self, tmp_path):
        doc = _doc()
        escrever_cache_ocr(
            tmp_path, doc, ["Conteúdo."], confiancas=[(0.30, 0.90)]
        )
        with pytest.raises(ocr_corpus.ErroCacheOCR, match="mínimo maior"):
            _carregar(doc, tmp_path)


class TestHashDoCache:
    def test_hash_muda_ao_editar_acrescentar_ou_remover_documento(self, tmp_path):
        """É a metade OCR da identidade RNF09: cache diferente, índice inválido."""
        doc = _doc()
        escrever_cache_ocr(tmp_path, doc, ["Conteúdo."])
        original = ocr_corpus.hash_cache_ocr(tmp_path)

        escrever_cache_ocr(tmp_path, doc, ["Conteúdo editado."])
        editado = ocr_corpus.hash_cache_ocr(tmp_path)
        assert editado != original

        outro = _doc(
            documento="itau_release_1T2026", empresa="ITAU", hash_sha256="b" * 64
        )
        escrever_cache_ocr(tmp_path, outro, ["Outro release."])
        assert ocr_corpus.hash_cache_ocr(tmp_path) not in {original, editado}

        (tmp_path / f"{outro.hash_sha256}.json").unlink()
        assert ocr_corpus.hash_cache_ocr(tmp_path) == editado

    def test_hash_e_estavel_e_independente_da_ordem_de_criacao(self, tmp_path):
        doc = _doc()
        escrever_cache_ocr(tmp_path, doc, ["Conteúdo."])
        assert ocr_corpus.hash_cache_ocr(tmp_path) == ocr_corpus.hash_cache_ocr(
            tmp_path
        )

    def test_cache_ausente_devolve_digest_do_conjunto_vazio(self, tmp_path):
        vazio = ocr_corpus.hash_cache_ocr(tmp_path / "nao_existe")
        assert len(vazio) == 64
        assert vazio == ocr_corpus.hash_cache_ocr(tmp_path)
