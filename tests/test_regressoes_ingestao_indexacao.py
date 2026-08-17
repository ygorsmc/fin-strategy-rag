"""Regressões para falhas silenciosas encontradas na auditoria de execução."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import tiktoken

from src import indexacao, ingestao, recuperacao
from src.config import Config
from src.ingestao import Chunk, DocumentoCorpus, PaginaExtraida
from tests.fixtures.cache_ocr import escrever_cache_ocr
from tests.fixtures.pdf_sintetico import criar_pdf


def _chunk(numero: int, texto: str = "conteúdo financeiro") -> Chunk:
    return Chunk(
        id=f"doc_release_1T2026_{numero:04d}",
        empresa="BB",
        trimestre="1T2026",
        documento="doc_release_1T2026",
        pagina_inicio=numero,
        pagina_fim=numero,
        posicao_no_documento=numero,
        texto=f"[BB | doc_release_1T2026 | 1T2026 | pág. {numero}]\n{texto}",
    )


class _EmbeddingsFake(indexacao.ProvedorEmbeddings):
    nome = "fake"
    modelo = "fake-v1"
    dimensao = 2

    def embedar(self, textos: list[str]) -> np.ndarray:
        return np.asarray(
            [[1.0, 0.0] if i % 2 == 0 else [0.0, 1.0] for i in range(len(textos))],
            dtype=np.float32,
        )


_IDENTIDADE_BIBLIOTECA = indexacao.IdentidadeExtracaoIndice(modo="pdfplumber")


def _config_biblioteca(**campos) -> Config:
    """Config do extrator por biblioteca.

    O default de `EXTRATOR` é `mistral_ocr` (o cache é versionado, o corpus/raw
    não). Os índices sintéticos deste arquivo são construídos com
    `_IDENTIDADE_BIBLIOTECA`, e a guarda RNF09 exige que a consulta declare o
    mesmo extrator — declarar aqui é o que mantém os testes falando do modo que
    eles de fato exercitam.
    """
    campos.setdefault("extrator", "pdfplumber")
    return Config(**campos)


def _fixar_insumos_fingerprint_ocr(monkeypatch) -> dict[str, str]:
    versoes = {
        "pdfplumber": "1.0.0",
        "pypdf": "2.0.0",
        "tiktoken": "3.0.0",
    }
    monkeypatch.setattr(indexacao, "_sha256_arquivo", lambda *_: "a" * 64)
    monkeypatch.setattr(
        indexacao.importlib.metadata,
        "version",
        lambda pacote: versoes[pacote],
    )
    monkeypatch.setattr(
        "src.ocr_corpus.hash_cache_ocr", lambda *_: "c" * 64
    )
    return versoes


def _manifesto_de(tmp_path, doc: DocumentoCorpus):
    """Manifesto de uma linha só, apontando para o documento recebido."""
    caminho = tmp_path / "metadados.csv"
    caminho.write_text(
        ",".join(ingestao.COLUNAS_METADADOS_CORPUS)
        + "\n"
        + ",".join(
            (
                doc.empresa,
                doc.trimestre,
                doc.documento,
                doc.url,
                doc.data_coleta,
                doc.hash_sha256,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return caminho


def _maior_overlap_tokens(a: list[int], b: list[int]) -> int:
    for tamanho in range(min(len(a), len(b)), 0, -1):
        if a[-tamanho:] == b[:tamanho]:
            return tamanho
    return 0


class TestRegressoesChunking:
    def test_extrator_mistral_ocr_e_offline_e_le_o_cache_versionado(
        self, documento_exemplo, monkeypatch, tmp_path
    ):
        """Sucessor de `test_overlay_ocr_e_offline_e_substitui_so_paginas_congeladas`.

        A propriedade central é a mesma — a ingestão nunca chama a API e a
        proveniência material acompanha cada página —, mas agora o cache é o
        documento inteiro (`corpus/ocr/<hash>.json`), não uma sobreposição.
        """
        monkeypatch.setattr(
            "src.ocr_mistral.OCRMistral",
            lambda *_, **__: pytest.fail("ingestão não pode instanciar cliente OCR"),
            raising=False,
        )
        caminho = escrever_cache_ocr(
            tmp_path,
            documento_exemplo,
            ["# Página um\n\nLucro de R$ 2 milhões.", "Página dois."],
        )
        extrator = ingestao.fabricar_extrator(
            _config_biblioteca(extrator="mistral_ocr"), tmp_path
        )
        paginas = extrator.extrair(
            tmp_path / "pdf_inexistente.pdf", documento_exemplo
        )
        assert extrator.nome == "mistral_ocr"
        assert [pagina.numero for pagina in paginas] == [1, 2]
        assert paginas[0].texto.startswith("# Página um")
        assert all(pagina.provedor_extracao == "mistral" for pagina in paginas)
        assert all(
            pagina.modelo_extracao == "mistral-ocr-4-0" for pagina in paginas
        )
        digest = hashlib.sha256(caminho.read_bytes()).hexdigest()
        assert all(
            pagina.hash_artefato_extracao == digest for pagina in paginas
        )
        # O cache real não traz `confidence_scores`: a ausência é declarada.
        assert all(pagina.confianca_media_ocr is None for pagina in paginas)

    def test_extrator_mistral_ocr_dispensa_o_pdf(
        self, documento_exemplo, tmp_path
    ):
        """O cache versionado é endereçado pelo hash do manifesto (RNF10).

        É o que permite reconstruir o índice num clone sem `corpus/raw/` —
        propriedade nova, que o modo de sobreposição não tinha.
        """
        escrever_cache_ocr(tmp_path, documento_exemplo, ["Conteúdo do release."])
        chunks = ingestao.ingerir_corpus(
            _config_biblioteca(extrator="mistral_ocr"),
            caminho_metadados=_manifesto_de(tmp_path, documento_exemplo),
            dir_raw=tmp_path / "raw_inexistente",
            caminho_ancoras_sentinela=None,
            dir_cache_ocr=tmp_path,
            exigir_todos_documentos=True,
        )
        assert chunks
        assert all(c.provedores_extracao == "mistral" for c in chunks)

    def test_extrator_pdfplumber_nao_toca_o_cache_ocr(
        self, documento_exemplo, monkeypatch, tmp_path
    ):
        """Sucessor de `test_modo_local_nem_consulta_o_cache_ocr`."""
        monkeypatch.setattr(
            "src.ocr_corpus.carregar_documento_ocr",
            lambda **_: pytest.fail("extrator por biblioteca não lê cache OCR"),
        )
        extrator = ingestao.fabricar_extrator(_config_biblioteca(), tmp_path)
        assert extrator.nome == "pdfplumber"
        pdf = criar_pdf(tmp_path / "doc.pdf", ["Texto local do release."])
        paginas = extrator.extrair(pdf, documento_exemplo)
        assert [pagina.provedor_extracao for pagina in paginas] == ["local"]

    def test_chunk_agrega_proveniencia_das_paginas(self, documento_exemplo):
        config = Config(chunk_tamanho_tokens=180, chunk_sobreposicao_tokens=20)
        paginas = [
            PaginaExtraida(
                documento_exemplo,
                1,
                "texto local " * 40,
                provedor_extracao="local",
                modelo_extracao="pypdf@teste",
            ),
            PaginaExtraida(
                documento_exemplo,
                2,
                "tabela OCR " * 40,
                provedor_extracao="mistral",
                modelo_extracao="mistral-ocr-4-0",
                hash_artefato_extracao="a" * 64,
                confianca_media_ocr=0.98,
                confianca_minima_ocr=0.2,
            ),
        ]
        chunks = ingestao.gerar_chunks(paginas, config)
        chunks_ocr = [c for c in chunks if "mistral" in c.provedores_extracao]
        assert chunks_ocr
        assert all("mistral-ocr-4-0" in c.modelos_extracao for c in chunks_ocr)
        assert all("a" * 64 in c.hashes_artefatos_extracao for c in chunks_ocr)
        assert all(c.confianca_media_ocr == 0.98 for c in chunks_ocr)
        assert all(c.confianca_minima_ocr == 0.2 for c in chunks_ocr)

    @pytest.mark.parametrize(
        "escore",
        [
            (float("nan"), 0.2),
            (-0.01, 0.2),
            (1.01, 0.2),
            (0.30, 0.90),  # mínimo acima da média: artefato incoerente
        ],
    )
    def test_cache_ocr_falha_fechado_com_confianca_estruturalmente_invalida(
        self, documento_exemplo, tmp_path, escore
    ):
        """Metade do antigo `test_overlay_ocr_falha_fechado_sem_confianca_media_suficiente`.

        Escore presente e malformado continua sendo falha dura: é adulteração
        do artefato ou mudança de contrato do provedor.
        """
        escrever_cache_ocr(
            tmp_path, documento_exemplo, ["Texto OCR."], confiancas=[escore]
        )
        extrator = ingestao.fabricar_extrator(
            _config_biblioteca(extrator="mistral_ocr"), tmp_path
        )
        with pytest.raises(
            ingestao.ErroCacheOCR,
            match="confidence|média|entre 0 e 1|constante inválida",
        ):
            extrator.extrair(tmp_path / "doc.pdf", documento_exemplo)

    @pytest.mark.parametrize("escore", [None, (0.949, 0.2)])
    def test_confianca_ausente_ou_abaixo_do_limiar_e_reportada_sem_bloquear(
        self, documento_exemplo, tmp_path, escore
    ):
        """Outra metade do teste antigo, com o limiar reclassificado.

        A spec 5.4 é explícita: confiança baixa **lista** a página no relatório
        de qualidade e não bloqueia a indexação. O gate duro de 0,95 existia
        porque a sobreposição misturava páginas de duas fontes na mesma
        extração; sem mistura, manter o bloqueio seria incoerente com aceitar
        artefato sem escore nenhum — que é o caso do cache real. O que não pode
        acontecer é silêncio: por isso o aviso é obrigatório e conferido aqui.
        """
        escrever_cache_ocr(
            tmp_path,
            documento_exemplo,
            ["Lucro liquido de R$ 2,3 bilhoes no trimestre."],
            confiancas=None if escore is None else [escore],
        )
        config = _config_biblioteca(extrator="mistral_ocr")
        extrator = ingestao.fabricar_extrator(config, tmp_path)
        paginas = extrator.extrair(tmp_path / "doc.pdf", documento_exemplo)
        chunks = ingestao.gerar_chunks(paginas, config)
        relatorio = ingestao.validar_qualidade(
            chunks,
            [documento_exemplo],
            paginas_extraidas=paginas,
            limiar_confianca_ocr=config.mistral_ocr_limiar_confianca_media,
        )
        assert relatorio.aprovado
        esperado = "sem escore" if escore is None else "abaixo do limiar"
        assert any(esperado in aviso for aviso in relatorio.avisos), relatorio.avisos

    @pytest.mark.parametrize(
        "config,mensagem",
        [
            (Config(chunk_tamanho_tokens=0), "TAMANHO"),
            (Config(chunk_sobreposicao_tokens=-1), "SOBREPOSICAO"),
            (
                Config(chunk_tamanho_tokens=100, chunk_sobreposicao_tokens=100),
                "menor",
            ),
        ],
    )
    def test_config_invalida_falha_cedo(self, documento_exemplo, config, mensagem):
        pagina = PaginaExtraida(documento_exemplo, 1, "texto válido")
        with pytest.raises(ValueError, match=mensagem):
            ingestao.gerar_chunks([pagina], config)

    def test_overlap_zero_nao_reutiliza_corpo_inteiro(self, documento_exemplo):
        config = Config(chunk_tamanho_tokens=200, chunk_sobreposicao_tokens=0)
        texto = " ".join(f"item_unico_{i:04d}" for i in range(900))
        chunks = ingestao.gerar_chunks(
            [PaginaExtraida(documento_exemplo, 1, texto)], config
        )
        encoder = tiktoken.get_encoding("cl100k_base")
        assert len(chunks) > 10
        assert all(len(encoder.encode(c.texto)) <= 200 for c in chunks)
        corpos = [encoder.encode(c.texto.split("\n", 1)[1]) for c in chunks]
        assert all(
            _maior_overlap_tokens(anterior, seguinte) < 5
            for anterior, seguinte in zip(corpos, corpos[1:])
        )

    def test_linha_longa_recebe_overlap_uma_vez_so(self, documento_exemplo):
        overlap = 30
        config = Config(
            chunk_tamanho_tokens=180, chunk_sobreposicao_tokens=overlap
        )
        texto = " ".join(f"marcador_{i:04d}" for i in range(700))
        chunks = ingestao.gerar_chunks(
            [PaginaExtraida(documento_exemplo, 1, texto)], config
        )
        encoder = tiktoken.get_encoding("cl100k_base")
        corpos = [encoder.encode(c.texto.split("\n", 1)[1]) for c in chunks]
        overlaps = [
            _maior_overlap_tokens(anterior, seguinte)
            for anterior, seguinte in zip(corpos, corpos[1:])
        ]
        assert overlaps
        assert all(overlap - 2 <= n <= overlap + 1 for n in overlaps)

    def test_overlap_preserva_pagina_de_origem(self, documento_exemplo):
        config = Config(chunk_tamanho_tokens=150, chunk_sobreposicao_tokens=25)
        pagina_1 = " ".join(f"p1_{i:03d}" for i in range(55))
        pagina_2 = "INICIO_PAGINA_DOIS resultado financeiro consolidado"
        chunks = ingestao.gerar_chunks(
            [
                PaginaExtraida(documento_exemplo, 1, pagina_1),
                PaginaExtraida(documento_exemplo, 2, pagina_2),
            ],
            config,
        )
        cruzados = [
            c
            for c in chunks
            if "INICIO_PAGINA_DOIS" in c.texto and c.pagina_inicio == 1
        ]
        assert cruzados
        assert all(c.pagina_fim == 2 for c in cruzados)


class TestRegressoesManifestoEQualidade:
    def test_manifesto_rejeita_path_traversal_hash_e_duplicata(self, tmp_path):
        cabecalho = ",".join(ingestao.COLUNAS_METADADOS_CORPUS) + "\n"
        casos = [
            "BB,1T2026,../fora,https://x,2026-07-15," + "a" * 64,
            "BB,1T2026,doc,https://x,2026-07-15,hash-invalido",
            (
                "BB,1T2026,doc,https://x,2026-07-15,"
                + "a" * 64
                + "\nBB,2T2026,doc,https://y,2026-07-15,"
                + "b" * 64
            ),
        ]
        for i, linhas in enumerate(casos):
            caminho = tmp_path / f"manifesto_{i}.csv"
            caminho.write_text(cabecalho + linhas + "\n", encoding="utf-8")
            with pytest.raises(ValueError):
                ingestao.carregar_metadados_corpus(caminho)

    def test_hash_canonico_independe_da_ordem(self):
        docs = [
            DocumentoCorpus("BB", "1T2026", "b", "https://b", "2026-07-15", "b" * 64),
            DocumentoCorpus("ITAU", "1T2026", "a", "https://a", "2026-07-15", "a" * 64),
        ]
        assert ingestao.calcular_hash_corpus(docs) == ingestao.calcular_hash_corpus(
            list(reversed(docs))
        )
        assert ingestao.calcular_hash_corpus(docs) != ingestao.calcular_hash_corpus(
            [replace(docs[0], hash_sha256="c" * 64), docs[1]]
        )

    def test_sentinela_nao_aprova_lista_vazia_cabecalho_ou_valor_sem_escala(self):
        chunk = _chunk(10, "O lucro foi de R$ 2,3 bilhões.")
        with pytest.raises(ValueError, match="âncora"):
            ingestao.teste_sentinela([chunk], [])
        assert not ingestao.teste_sentinela([chunk], [10.0])
        assert not ingestao.teste_sentinela([chunk], [2.3])
        assert ingestao.teste_sentinela([chunk], [2_300_000_000.0])

    def test_arquivo_de_ancoras_tem_contrato_independente_e_cobertura_explicita(
        self, tmp_path
    ):
        doc = DocumentoCorpus(
            "BB", "1T2026", "doc_release_1T2026", "https://x", "2026-07-15", "a" * 64
        )
        caminho = tmp_path / "ancoras_sentinela.csv"
        caminho.write_text(
            "documento,valor_ancora\n"
            "doc_release_1T2026,2300000000\n"
            "doc_release_1T2026,0.266\n",
            encoding="utf-8",
        )
        assert ingestao.carregar_ancoras_sentinela(caminho, [doc]) == {
            "doc_release_1T2026": [2_300_000_000.0, 0.266]
        }

    def test_modo_estrito_falha_quando_fonte_de_ancoras_nao_existe(self, tmp_path):
        manifesto = tmp_path / "metadados.csv"
        manifesto.write_text(
            ",".join(ingestao.COLUNAS_METADADOS_CORPUS)
            + "\nBB,1T2026,doc,https://x,2026-07-15,"
            + "a" * 64
            + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="não terá cobertura completa"):
            ingestao.ingerir_corpus(
                _config_biblioteca(),
                caminho_metadados=manifesto,
                dir_raw=tmp_path,
                caminho_ancoras_sentinela=None,
                exigir_cobertura_sentinela=True,
            )

    def test_rf03_detecta_paginas_extraidas_duplicadas(self):
        doc = DocumentoCorpus(
            "BB", "1T2026", "doc_release_1T2026", "https://x", "2026-07-15", "a" * 64
        )
        paginas = [
            PaginaExtraida(doc, 1, "Página financeira exatamente igual."),
            PaginaExtraida(doc, 2, "Página financeira exatamente igual."),
        ]
        relatorio = ingestao.validar_qualidade(
            [_chunk(1)], [doc], paginas_extraidas=paginas
        )
        assert "página duplicada na extração" in relatorio.documentos_falhos[doc.documento]

    def test_hash_ruim_isola_documento_sem_interromper_os_demais(
        self, tmp_path, capsys
    ):
        raw = tmp_path / "raw"
        raw.mkdir()
        ruim = criar_pdf(raw / "ruim.pdf", ["Lucro de R$ 1,0 bilhão.\n" * 4])
        bom = criar_pdf(raw / "bom.pdf", ["Lucro de R$ 2,0 bilhões.\n" * 4])
        digest_bom = hashlib.sha256(bom.read_bytes()).hexdigest()
        manifesto = tmp_path / "metadados.csv"
        manifesto.write_text(
            ",".join(ingestao.COLUNAS_METADADOS_CORPUS)
            + "\nBB,1T2026,ruim,https://x,2026-07-15,"
            + "0" * 64
            + "\nITAU,1T2026,bom,https://y,2026-07-15,"
            + digest_bom
            + "\n",
            encoding="utf-8",
        )
        assert ruim.exists()
        chunks = ingestao.ingerir_corpus(
            _config_biblioteca(), caminho_metadados=manifesto, dir_raw=raw
        )
        assert chunks and {c.documento for c in chunks} == {"bom"}
        with pytest.raises(RuntimeError, match="corpus parcial"):
            ingestao.ingerir_corpus(
                _config_biblioteca(),
                caminho_metadados=manifesto,
                dir_raw=raw,
                exigir_todos_documentos=True,
            )
        assert "SHA-256 divergente" in capsys.readouterr().out


class TestRegressoesPersistenciaIndice:
    @staticmethod
    def _chunk_ocr() -> Chunk:
        return replace(
            _chunk(1),
            provedores_extracao="mistral",
            modelos_extracao="mistral-ocr-4-0",
            hashes_artefatos_extracao="b" * 64,
            confianca_media_ocr=0.98,
            confianca_minima_ocr=0.2,
        )

    @staticmethod
    def _identidade_ocr() -> indexacao.IdentidadeExtracaoIndice:
        return indexacao.IdentidadeExtracaoIndice(
            modo="mistral_ocr",
            hash_cache_ocr="c" * 64,
            fingerprint_derivacao_ocr="d" * 64,
        )

    def test_identidade_local_nao_toca_cache_nem_codigo_ocr(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            "src.ocr_corpus.hash_cache_ocr",
            lambda *_: pytest.fail("modo local não consulta manifesto OCR"),
        )
        monkeypatch.setattr(
            indexacao,
            "_fingerprint_derivacao_ocr",
            lambda *_: pytest.fail("modo local não deriva fingerprint OCR"),
        )
        assert indexacao.calcular_identidade_extracao(
            _config_biblioteca(), tmp_path / "cache_ausente"
        ) == indexacao.IdentidadeExtracaoIndice("pdfplumber")

    def test_fingerprint_derivacao_ocr_e_json_canonico_com_config_e_dependencias(
        self, tmp_path, monkeypatch
    ):
        hashes = {
            "ingestao.py": "a" * 64,
            "ocr_corpus.py": "b" * 64,
        }
        monkeypatch.setattr(
            indexacao,
            "_sha256_arquivo",
            lambda caminho: hashes[caminho.name],
        )
        monkeypatch.setattr(
            indexacao.importlib.metadata,
            "version",
            lambda pacote: {
                "pdfplumber": "1.2.3",
                "pypdf": "4.5.6",
                "tiktoken": "9.8.7",
            }[pacote],
        )
        monkeypatch.setattr(
            "src.ocr_corpus.hash_cache_ocr", lambda *_: "c" * 64
        )
        config = _config_biblioteca(extrator="mistral_ocr")
        componentes = {
            "arquivos": {
                "src/ingestao.py": "a" * 64,
                "src/ocr_corpus.py": "b" * 64,
            },
            "configuracao_material": {
                "chunk_sobreposicao_tokens": config.chunk_sobreposicao_tokens,
                "chunk_tamanho_tokens": config.chunk_tamanho_tokens,
                "mistral_ocr_confidence_granularity": (
                    config.mistral_ocr_confidence_granularity
                ),
                "mistral_ocr_endpoint": config.mistral_ocr_endpoint,
                "mistral_ocr_include_blocks": config.mistral_ocr_include_blocks,
                "mistral_ocr_limiar_confianca_media": (
                    config.mistral_ocr_limiar_confianca_media
                ),
                "mistral_ocr_modelo": config.mistral_ocr_modelo,
                "mistral_ocr_table_format": config.mistral_ocr_table_format,
            },
            "dependencias": {
                "pdfplumber": "1.2.3",
                "pypdf": "4.5.6",
                "tiktoken": "9.8.7",
            },
            "versao_identidade": 3,
        }
        esperado = hashlib.sha256(
            json.dumps(
                componentes,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        identidade = indexacao.calcular_identidade_extracao(
            config, tmp_path
        )
        assert identidade == indexacao.IdentidadeExtracaoIndice(
            "mistral_ocr", "c" * 64, esperado
        )

    @pytest.mark.parametrize(
        "campo,valor_alterado",
        [
            ("mistral_ocr_modelo", "mistral-ocr-4-0-2026"),
            ("mistral_ocr_endpoint", "https://api.mistral.ai:443/v1/ocr"),
            ("mistral_ocr_table_format", "markdown"),
            ("mistral_ocr_include_blocks", False),
            ("mistral_ocr_confidence_granularity", "word"),
            ("mistral_ocr_limiar_confianca_media", 0.91),
            ("chunk_tamanho_tokens", 601),
            ("chunk_sobreposicao_tokens", 101),
        ],
    )
    def test_cada_config_material_muda_identidade_e_recusa_indice(
        self, tmp_path, monkeypatch, campo, valor_alterado
    ):
        _fixar_insumos_fingerprint_ocr(monkeypatch)
        base = _config_biblioteca(extrator="mistral_ocr")
        identidade_base = indexacao.calcular_identidade_extracao(base, tmp_path)
        config_alterada = replace(base, **{campo: valor_alterado})
        identidade_alterada = indexacao.calcular_identidade_extracao(
            config_alterada, tmp_path
        )
        assert identidade_alterada != identidade_base

        destino = tmp_path / campo
        indexacao.construir_indice_chroma(
            [self._chunk_ocr()],
            _EmbeddingsFake(),
            "a" * 64,
            destino,
            identidade_extracao=identidade_base,
        )
        with pytest.raises(
            indexacao.ErroConsistenciaIndice,
            match="fingerprint_derivacao_ocr",
        ):
            indexacao.carregar_indice_bm25(
                config=config_alterada,
                dir_indice=destino,
                dir_ocr=tmp_path,
            )

    @pytest.mark.parametrize(
        "campo,valor_alterado",
        [
            ("mistral_ocr_api_key", "segredo-nao-material"),
            ("mistral_ocr_timeout_s", 999.0),
            ("mistral_ocr_max_retries", 3),
            ("mistral_ocr_preco_usd_mil_paginas", 99.0),
            ("mistral_ocr_orcamento_teto_usd", 99.0),
        ],
    )
    def test_config_operacional_nao_muda_identidade_ocr(
        self, tmp_path, monkeypatch, campo, valor_alterado
    ):
        _fixar_insumos_fingerprint_ocr(monkeypatch)
        base = _config_biblioteca(extrator="mistral_ocr")
        alterada = replace(base, **{campo: valor_alterado})
        assert indexacao.calcular_identidade_extracao(
            alterada, tmp_path
        ) == indexacao.calcular_identidade_extracao(base, tmp_path)

    @pytest.mark.parametrize("pacote", ["pdfplumber", "pypdf", "tiktoken"])
    def test_versao_de_cada_dependencia_local_muda_fingerprint(
        self, tmp_path, monkeypatch, pacote
    ):
        versoes = _fixar_insumos_fingerprint_ocr(monkeypatch)
        config = _config_biblioteca(extrator="mistral_ocr")
        antes = indexacao.calcular_identidade_extracao(config, tmp_path)
        versoes[pacote] = "999.0.0"
        depois = indexacao.calcular_identidade_extracao(config, tmp_path)
        assert depois != antes

    def test_rnf09_registra_proveniencia_ocr_no_indice(
        self, tmp_path, monkeypatch
    ):
        destino = tmp_path / "indice"
        identidade_ocr = self._identidade_ocr()
        chunk_ocr = self._chunk_ocr()
        metadados = indexacao.construir_indice_chroma(
            [chunk_ocr],
            _EmbeddingsFake(),
            "a" * 64,
            destino,
            identidade_extracao=identidade_ocr,
        )
        assert metadados.provedores_extracao == "mistral"
        assert metadados.modelos_extracao == "mistral-ocr-4-0"
        assert metadados.n_artefatos_extracao == 1
        assert metadados.extrator == "mistral_ocr"
        assert metadados.hash_cache_ocr == "c" * 64
        assert metadados.fingerprint_derivacao_ocr == "d" * 64
        assert metadados.hash_artefatos_extracao == hashlib.sha256(
            json.dumps(["b" * 64], separators=(",", ":")).encode()
        ).hexdigest()
        monkeypatch.setattr(
            indexacao,
            "calcular_identidade_extracao",
            lambda *_: identidade_ocr,
        )

        caminho_metadados = destino / indexacao.ARQUIVO_METADADOS_INDICE
        original = json.loads(caminho_metadados.read_text(encoding="utf-8"))
        adulteracoes = {
            "provedores_extracao": "local+mistral",
            "modelos_extracao": "modelo-inventado",
            "hash_artefatos_extracao": "0" * 64,
            "n_artefatos_extracao": 2,
        }
        for campo, valor in adulteracoes.items():
            bruto = {**original, campo: valor}
            caminho_metadados.write_text(json.dumps(bruto), encoding="utf-8")
            with pytest.raises(
                indexacao.ErroConsistenciaIndice,
                match="Proveniência de extração",
            ):
                indexacao.carregar_indice_bm25(
                    config=_config_biblioteca(extrator="mistral_ocr"),
                    dir_indice=destino,
                )

    @pytest.mark.parametrize("modo_indice", ["pdfplumber", "mistral_ocr"])
    @pytest.mark.parametrize("loader", ["chroma", "bm25"])
    def test_mismatch_de_modo_falha_antes_de_cache_modelo_e_indice(
        self, tmp_path, monkeypatch, modo_indice, loader
    ):
        destino = tmp_path / f"indice_{modo_indice}_{loader}"
        identidade = (
            _IDENTIDADE_BIBLIOTECA
            if modo_indice == "pdfplumber"
            else self._identidade_ocr()
        )
        chunks = (
            [_chunk(1)] if modo_indice == "pdfplumber" else [self._chunk_ocr()]
        )
        indexacao.construir_indice_chroma(
            chunks,
            _EmbeddingsFake(),
            "a" * 64,
            destino,
            identidade_extracao=identidade,
        )

        monkeypatch.setattr(
            "src.ocr_corpus.hash_cache_ocr",
            lambda *_: pytest.fail("mismatch de modo não pode tocar o cache OCR"),
        )

        class ProvedorSemConsulta(_EmbeddingsFake):
            def identidade_modelo(self):
                pytest.fail("mismatch OCR deve preceder identidade_modelo")

        monkeypatch.setattr(
            indexacao,
            "_abrir_colecao_chroma",
            lambda *_: pytest.fail(
                "mismatch OCR deve preceder a abertura da coleção Chroma"
            ),
        )
        config = Config(
            extrator=(
                "mistral_ocr" if modo_indice == "pdfplumber" else "pdfplumber"
            )
        )
        with pytest.raises(indexacao.ErroConsistenciaIndice, match="Modo de extração"):
            if loader == "chroma":
                indexacao.carregar_indice_chroma(
                    ProvedorSemConsulta(), config=config, dir_indice=destino
                )
            else:
                indexacao.carregar_indice_bm25(
                    config=config, dir_indice=destino
                )

    @pytest.mark.parametrize(
        "campo,valor_atual",
        [
            ("hash_cache_ocr", "e" * 64),
            ("fingerprint_derivacao_ocr", "f" * 64),
        ],
    )
    def test_manifesto_ou_codigo_ocr_alterado_invalida_indice(
        self, tmp_path, monkeypatch, campo, valor_atual
    ):
        destino = tmp_path / campo
        registrada = self._identidade_ocr()
        indexacao.construir_indice_chroma(
            [self._chunk_ocr()],
            _EmbeddingsFake(),
            "a" * 64,
            destino,
            identidade_extracao=registrada,
        )
        atual = replace(registrada, **{campo: valor_atual})
        monkeypatch.setattr(
            indexacao, "calcular_identidade_extracao", lambda *_: atual
        )
        with pytest.raises(indexacao.ErroConsistenciaIndice, match=campo):
            indexacao.carregar_indice_bm25(
                config=_config_biblioteca(extrator="mistral_ocr"),
                dir_indice=destino,
            )

    @pytest.mark.parametrize(
        "identidade,chunks",
        [
            (
                indexacao.IdentidadeExtracaoIndice(
                    "mistral_ocr", "c" * 64, "d" * 64
                ),
                [_chunk(1)],
            ),
            (_IDENTIDADE_BIBLIOTECA, [
                replace(
                    _chunk(1),
                    provedores_extracao="mistral",
                    modelos_extracao="mistral-ocr-4-0",
                    hashes_artefatos_extracao="b" * 64,
                    confianca_media_ocr=0.98,
                    confianca_minima_ocr=0.2,
                )
            ]),
        ],
    )
    def test_builder_recusa_identidade_cruzada_antes_de_embeddings(
        self, tmp_path, identidade, chunks
    ):
        class EmbeddingsSemChamada(_EmbeddingsFake):
            def identidade_modelo(self):
                pytest.fail("identidade cruzada deve preceder identidade_modelo")

            def embedar(self, textos):
                pytest.fail("identidade cruzada deve preceder embeddings")

        with pytest.raises(ValueError, match="proveniência OCR"):
            indexacao.construir_indice_chroma(
                chunks,
                EmbeddingsSemChamada(),
                "a" * 64,
                tmp_path / "indice",
                identidade_extracao=identidade,
            )

    def test_indice_local_legado_carrega_somente_em_modo_local(
        self, tmp_path, monkeypatch
    ):
        destino = tmp_path / "legado"
        indexacao.construir_indice_chroma(
            [_chunk(1)],
            _EmbeddingsFake(),
            "a" * 64,
            destino,
            identidade_extracao=_IDENTIDADE_BIBLIOTECA,
        )
        caminho = destino / indexacao.ARQUIVO_METADADOS_INDICE
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        for campo in (
            "extrator",
            "hash_cache_ocr",
            "fingerprint_derivacao_ocr",
        ):
            bruto.pop(campo)
        caminho.write_text(json.dumps(bruto), encoding="utf-8")

        monkeypatch.setattr(
            "src.ocr_corpus.hash_cache_ocr",
            lambda *_: pytest.fail("índice local não consulta cache OCR"),
        )
        _, chunks = indexacao.carregar_indice_bm25(
            config=_config_biblioteca(), dir_indice=destino
        )
        assert [chunk.id for chunk in chunks] == [_chunk(1).id]
        with pytest.raises(indexacao.ErroConsistenciaIndice, match="Modo de extração"):
            indexacao.carregar_indice_bm25(
                config=_config_biblioteca(extrator="mistral_ocr"),
                dir_indice=destino,
            )

    @pytest.mark.parametrize("modo", ["pdfplumber", "mistral_ocr"])
    def test_indice_ocr_legado_sem_identidade_nunca_e_aceito(
        self, tmp_path, modo
    ):
        destino = tmp_path / f"ocr_legado_{modo}"
        indexacao.construir_indice_chroma(
            [self._chunk_ocr()],
            _EmbeddingsFake(),
            "a" * 64,
            destino,
            identidade_extracao=self._identidade_ocr(),
        )
        caminho = destino / indexacao.ARQUIVO_METADADOS_INDICE
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        for campo in (
            "extrator",
            "hash_cache_ocr",
            "fingerprint_derivacao_ocr",
        ):
            bruto.pop(campo)
        caminho.write_text(json.dumps(bruto), encoding="utf-8")
        with pytest.raises(
            indexacao.ErroConsistenciaIndice, match="declarado sem OCR"
        ):
            indexacao.carregar_indice_bm25(
                config=_config_biblioteca(extrator=modo), dir_indice=destino
            )

    def test_metadados_ocr_estruturalmente_invalidos_falham_fechado(
        self, tmp_path
    ):
        destino = tmp_path / "invalido"
        indexacao.construir_indice_chroma(
            [_chunk(1)],
            _EmbeddingsFake(),
            "a" * 64,
            destino,
            identidade_extracao=_IDENTIDADE_BIBLIOTECA,
        )
        caminho = destino / indexacao.ARQUIVO_METADADOS_INDICE
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        bruto["extrator"] = "mistral_ocr"
        caminho.write_text(json.dumps(bruto), encoding="utf-8")
        with pytest.raises(
            indexacao.ErroConsistenciaIndice, match="hash_cache_ocr"
        ):
            indexacao.carregar_indice_bm25(
                config=_config_biblioteca(extrator="mistral_ocr"),
                dir_indice=destino,
            )

    @pytest.mark.parametrize(
        "campos,mensagem",
        [
            ({"tipo_bloco": "planilha"}, "Tipo de bloco"),
            ({"tipo_bloco": ""}, "Tipo de bloco"),
            (
                {"confianca_media_ocr": 0.9, "confianca_minima_ocr": 0.1},
                "Scores de confiança",
            ),
            (
                {"confianca_media_ocr": 0.9, "confianca_minima_ocr": None},
                "Scores de confiança",
            ),
        ],
    )
    def test_builder_recusa_metadado_de_bloco_ou_confianca_invalido(
        self, tmp_path, campos, mensagem
    ):
        """Chunk sem OCR exibindo confiança é proveniência inventada; tipo de
        bloco fora do contrato quebra o diagnóstico de origem (5.4)."""
        with pytest.raises(ValueError, match=mensagem):
            indexacao.construir_indice_chroma(
                [replace(_chunk(1), **campos)],
                _EmbeddingsFake(),
                "a" * 64,
                tmp_path / "indice",
                identidade_extracao=_IDENTIDADE_BIBLIOTECA,
            )

    def test_builder_aceita_chunk_de_ocr_sem_escore_de_confianca(self, tmp_path):
        """O cache real veio da Batch API sem `confidence_scores`.

        A ausência é registrada como ausência (`None`) e não impede indexar —
        o que a RNF09 protege é a identidade do índice, não a existência de um
        escore que o provedor não devolveu.
        """
        chunk = replace(
            self._chunk_ocr(), confianca_media_ocr=None, confianca_minima_ocr=None
        )
        metadados = indexacao.construir_indice_chroma(
            [chunk],
            _EmbeddingsFake(),
            "a" * 64,
            tmp_path / "indice",
            identidade_extracao=self._identidade_ocr(),
        )
        assert metadados.provedores_extracao == "mistral"

    def test_rejeita_vazio_e_ids_duplicados(self, tmp_path):
        with pytest.raises(ValueError, match="vazia"):
            indexacao.construir_indice_chroma(
                [],
                _EmbeddingsFake(),
                "a" * 64,
                tmp_path / "indice",
                identidade_extracao=_IDENTIDADE_BIBLIOTECA,
            )
        duplicados = [_chunk(1), replace(_chunk(2), id=_chunk(1).id)]
        with pytest.raises(ValueError, match="duplicado"):
            indexacao.construir_indice_chroma(
                duplicados,
                _EmbeddingsFake(),
                "a" * 64,
                tmp_path / "indice",
                identidade_extracao=_IDENTIDADE_BIBLIOTECA,
            )

    def test_build_falho_preserva_conjunto_anterior(self, tmp_path, monkeypatch):
        destino = tmp_path / "indice"
        provedor = _EmbeddingsFake()
        indexacao.construir_indice_chroma(
            [_chunk(1), _chunk(2)],
            provedor,
            "a" * 64,
            destino,
            identidade_extracao=_IDENTIDADE_BIBLIOTECA,
        )
        antes = {
            nome: (destino / nome).read_bytes()
            for nome in (
                indexacao.ARQUIVO_CHUNKS,
                indexacao.ARQUIVO_SQLITE_CHROMA,
                indexacao.ARQUIVO_METADADOS_INDICE,
            )
        }

        def falhar_validacao(*args, **kwargs):
            raise RuntimeError("falha injetada no staging")

        monkeypatch.setattr(indexacao, "_carregar_conjunto_persistido", falhar_validacao)
        with pytest.raises(RuntimeError, match="falha injetada"):
            indexacao.construir_indice_chroma(
                [_chunk(1, "novo 1"), _chunk(2, "novo 2")],
                provedor,
                "b" * 64,
                destino,
                identidade_extracao=_IDENTIDADE_BIBLIOTECA,
            )
        assert all((destino / nome).read_bytes() == conteudo for nome, conteudo in antes.items())
        assert not list(tmp_path.glob(".indice.staging-*"))
        # Além dos bytes: o conjunto anterior continua CARREGÁVEL — digest,
        # identidade da coleção e chunks batem entre si depois da falha.
        monkeypatch.undo()
        _, chunks = indexacao.carregar_indice_chroma(
            provedor, config=_config_biblioteca(), dir_indice=destino
        )
        assert [c.texto for c in chunks] == [_chunk(1).texto, _chunk(2).texto]

    def test_checksum_de_chunks_detecta_adulteracao(self, tmp_path):
        destino = tmp_path / "indice"
        provedor = _EmbeddingsFake()
        indexacao.construir_indice_chroma(
            [_chunk(1), _chunk(2)],
            provedor,
            "a" * 64,
            destino,
            identidade_extracao=_IDENTIDADE_BIBLIOTECA,
        )
        caminho = destino / indexacao.ARQUIVO_CHUNKS
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        dados[0]["texto"] += " adulterado"
        caminho.write_text(json.dumps(dados), encoding="utf-8")
        with pytest.raises(indexacao.ErroConsistenciaIndice, match="Checksum"):
            indexacao.carregar_indice_chroma(
                provedor, config=_config_biblioteca(), dir_indice=destino
            )

    def test_dimensao_fisica_dos_vetores_e_validada(self, tmp_path):
        """A dimensão real dos vetores tem de bater com a declarada.

        A coleção é recriada com vetores de dimensão 3 preservando ids,
        documentos, metadados e identidade RNF09, e o digest é republicado —
        assim o único desvio que resta é a dimensão, e é ela que precisa
        derrubar a carga.
        """
        destino = tmp_path / "indice"
        chunks = [_chunk(1), _chunk(2)]
        provedor = _EmbeddingsFake()
        metadados = indexacao.construir_indice_chroma(
            chunks, provedor, "a" * 64, destino,
            identidade_extracao=_IDENTIDADE_BIBLIOTECA,
        )
        cliente = indexacao._abrir_cliente_chroma(destino)
        cliente.delete_collection(indexacao.COLECAO_CHROMA)
        colecao = cliente.create_collection(
            name=indexacao.COLECAO_CHROMA,
            configuration={
                "hnsw": {
                    "space": indexacao.ESPACO_DISTANCIA_CHROMA,
                    "ef_search": indexacao._ef_busca(len(chunks)),
                }
            },
            metadata=indexacao._metadados_para_colecao(metadados),
        )
        colecao.add(
            ids=[c.id for c in chunks],
            embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            documents=[c.texto for c in chunks],
            metadatas=[
                {campo: getattr(c, campo)
                 for campo in indexacao.CAMPOS_METADADOS_CHROMA}
                for c in chunks
            ],
        )
        digest, dimensao, _ = indexacao._digest_colecao(
            indexacao._abrir_colecao_chroma(destino)
        )
        assert dimensao == 3 and metadados.dimensao == 2
        indexacao.salvar_metadados_indice(
            replace(metadados, hash_indice_vetorial=digest), destino
        )
        with pytest.raises(indexacao.ErroConsistenciaIndice, match="Dimensão física"):
            indexacao.carregar_indice_chroma(
                provedor, config=_config_biblioteca(), dir_indice=destino
            )

    def test_bm25_nao_sobrescreve_chunks_do_indice_vetorial(self, tmp_path):
        destino = tmp_path / "indice"
        indexacao.construir_indice_chroma(
            [_chunk(1), _chunk(2)],
            _EmbeddingsFake(),
            "a" * 64,
            destino,
            identidade_extracao=_IDENTIDADE_BIBLIOTECA,
        )
        caminho = destino / indexacao.ARQUIVO_CHUNKS
        antes = caminho.read_bytes()
        indexacao.construir_indice_bm25(
            [_chunk(1, "conteúdo diferente")], destino
        )
        assert caminho.read_bytes() == antes

    def test_manifesto_atual_invalida_indice_e_recuperador_propaga_hash(
        self, tmp_path, monkeypatch
    ):
        destino = tmp_path / "indice"
        doc = DocumentoCorpus(
            "BB",
            "1T2026",
            "doc_release_1T2026",
            "https://x",
            "2026-07-15",
            "a" * 64,
        )
        hash_original = ingestao.calcular_hash_corpus([doc])
        provedor = _EmbeddingsFake()
        indexacao.construir_indice_chroma(
            [_chunk(1), _chunk(2)],
            provedor,
            hash_original,
            destino,
            identidade_extracao=_IDENTIDADE_BIBLIOTECA,
        )
        manifesto = tmp_path / "metadados.csv"
        manifesto.write_text(
            ",".join(ingestao.COLUNAS_METADADOS_CORPUS)
            + "\nBB,1T2026,doc_release_1T2026,https://x,2026-07-15,"
            + "a" * 64
            + "\n",
            encoding="utf-8",
        )
        esperado = indexacao.calcular_hash_corpus_atual_para_indice(
            destino, manifesto
        )
        indexacao.carregar_indice_chroma(
            provedor,
            config=_config_biblioteca(),
            dir_indice=destino,
            hash_corpus_esperado=esperado,
        )
        manifesto.write_text(
            manifesto.read_text(encoding="utf-8").replace("a" * 64, "b" * 64),
            encoding="utf-8",
        )
        atual = indexacao.calcular_hash_corpus_atual_para_indice(destino, manifesto)
        with pytest.raises(indexacao.ErroConsistenciaIndice, match="Corpus atual diverge"):
            indexacao.carregar_indice_chroma(
                provedor,
                config=_config_biblioteca(),
                dir_indice=destino,
                hash_corpus_esperado=atual,
            )

        chamadas = []
        monkeypatch.setattr(
            recuperacao,
            "calcular_hash_corpus_atual_para_indice",
            lambda: "c" * 64,
        )
        monkeypatch.setattr(
            recuperacao,
            "carregar_indice_bm25",
            lambda **kwargs: chamadas.append(kwargs) or (object(), [_chunk(1)]),
        )
        recuperacao.Recuperador(_config_biblioteca())._garantir_bm25()
        assert chamadas == [
            {"config": _config_biblioteca(), "hash_corpus_esperado": "c" * 64}
        ]


class _EmbeddingsPorEmpresa(indexacao.ProvedorEmbeddings):
    """Vetor determinístico por instituição — sem rede, sem modelo real."""

    nome = "fake"
    modelo = "fake-v1"
    dimensao = 2
    _POR_EMPRESA = {"ITAU": [1.0, 0.0], "BB": [0.8, 0.6], "BTG": [0.6, 0.8]}

    def embedar(self, textos: list[str]) -> np.ndarray:
        vetores = []
        for texto in textos:
            escolhido = next(
                (v for e, v in self._POR_EMPRESA.items() if e in texto),
                [1.0, 0.0],
            )
            vetores.append(escolhido)
        return np.asarray(vetores, dtype=np.float32)


def _chunk_de(empresa: str, numero: int) -> Chunk:
    return replace(
        _chunk(numero),
        id=f"{empresa}_1T2026_{numero:04d}",
        empresa=empresa,
        documento=f"{empresa.lower()}_release_1T2026",
        texto=f"[{empresa} | {empresa.lower()}_release_1T2026 | 1T2026 | "
        f"pág. {numero}]\nlucro líquido de {empresa}",
    )


class TestMigracaoChromaRNF09:
    """Garantias que nasceram da troca de FAISS por ChromaDB (spec 5.6)."""

    @staticmethod
    def _construir(destino, chunks=None, provedor=None):
        return indexacao.construir_indice_chroma(
            chunks or [_chunk_de("ITAU", 1), _chunk_de("BB", 2)],
            provedor or _EmbeddingsPorEmpresa(),
            "a" * 64,
            destino,
            identidade_extracao=_IDENTIDADE_BIBLIOTECA,
        )

    def test_where_nativo_restringe_antes_do_ranqueamento(self, tmp_path):
        """RF06: o trecho de outro banco pontua mais e ainda assim não entra.

        Com FAISS era preciso rankear a coleção inteira e descartar depois;
        aqui a restrição vai na consulta. O chunk do ITAU tem similaridade
        1,0 contra 0,8 do BB, então se o filtro fosse aplicado *depois* de um
        top-k de 1 o resultado do BB viria vazio.
        """
        destino = tmp_path / "indice"
        provedor = _EmbeddingsPorEmpresa()
        self._construir(destino)
        colecao, chunks = indexacao.carregar_indice_chroma(
            provedor, config=_config_biblioteca(), dir_indice=destino
        )
        recuperador = recuperacao.Recuperador(
            _config_biblioteca(), indice_chroma=(colecao, chunks), provedor_embeddings=provedor
        )
        sem_filtro = recuperador.recuperar(
            "Qual o lucro de ITAU?", recuperacao.Estrategia.SEMANTICA, top_k=1
        )
        assert [r.chunk.empresa for r in sem_filtro] == ["ITAU"]

        so_bb = recuperador.recuperar(
            "Qual o lucro de BB?", recuperacao.Estrategia.SEMANTICA, top_k=1
        )
        assert [r.chunk.empresa for r in so_bb] == ["BB"]

    def test_tipo_de_bloco_e_filtravel_na_colecao(self, tmp_path):
        """`tipo_bloco` acompanha o vetor, como empresa/trimestre (5.3).

        É o que permite, depois, separar erro de extração de tabela de erro de
        recuperação sem reabrir o corpus — e só vale se o metadado for
        consultável do lado do armazenamento, não recalculado na leitura.
        """
        destino = tmp_path / "indice"
        self._construir(
            destino,
            chunks=[
                replace(_chunk_de("ITAU", 1), tipo_bloco="tabela"),
                replace(_chunk_de("BB", 2), tipo_bloco="texto"),
            ],
        )
        colecao = indexacao._abrir_colecao_chroma(destino)
        assert "tipo_bloco" in indexacao.CAMPOS_METADADOS_CHROMA
        so_tabela = colecao.get(where={"tipo_bloco": "tabela"})
        assert so_tabela["ids"] == ["ITAU_1T2026_0001"]

    def test_score_semantico_e_o_produto_interno_dos_vetores(self, tmp_path):
        """1 - distância cosseno == produto interno, como no IndexFlatIP."""
        destino = tmp_path / "indice"
        provedor = _EmbeddingsPorEmpresa()
        self._construir(destino)
        colecao, chunks = indexacao.carregar_indice_chroma(
            provedor, config=_config_biblioteca(), dir_indice=destino
        )
        recuperador = recuperacao.Recuperador(
            _config_biblioteca(), indice_chroma=(colecao, chunks), provedor_embeddings=provedor
        )
        # Pergunta sem banco citado: nenhum `where`, os dois trechos disputam.
        resultados = recuperador.recuperar(
            "Qual foi o lucro líquido reportado?",
            recuperacao.Estrategia.SEMANTICA,
            top_k=2,
        )
        esperado = {"ITAU": 1.0, "BB": 0.8}
        assert {r.chunk.empresa: round(r.score, 4) for r in resultados} == esperado

    def test_carregar_duas_vezes_seguidas_continua_valendo(self, tmp_path):
        """Abrir a coleção reescreve os arquivos do Chroma.

        Verificado em laboratório: `chroma.sqlite3` e os segmentos HNSW mudam
        de conteúdo só por consultar. Um checksum FÍSICO do armazenamento
        passaria na primeira carga e falharia na segunda; por isso o digest
        publicado é sobre o conteúdo lógico da coleção.
        """
        destino = tmp_path / "indice"
        provedor = _EmbeddingsPorEmpresa()
        self._construir(destino)
        antes = (destino / indexacao.ARQUIVO_SQLITE_CHROMA).read_bytes()
        colecao, _ = indexacao.carregar_indice_chroma(
            provedor, config=_config_biblioteca(), dir_indice=destino
        )
        colecao.query(
            query_embeddings=[[1.0, 0.0]], n_results=1, include=["distances"]
        )
        assert (destino / indexacao.ARQUIVO_SQLITE_CHROMA).read_bytes() != antes
        _, chunks = indexacao.carregar_indice_chroma(
            provedor, config=_config_biblioteca(), dir_indice=destino
        )
        assert {c.empresa for c in chunks} == {"ITAU", "BB"}

    def test_metadados_rnf09_ficam_gravados_na_colecao(self, tmp_path):
        """Provedor, modelo, dimensão, data e hash do corpus na coleção."""
        destino = tmp_path / "indice"
        metadados = self._construir(destino)
        colecao = indexacao._abrir_colecao_chroma(destino)
        gravados = colecao.metadata
        assert gravados["provedor"] == "fake"
        assert gravados["modelo"] == "fake-v1"
        assert gravados["dimensao"] == 2
        assert gravados["data_construcao"] == metadados.data_construcao
        assert gravados["hash_corpus"] == "a" * 64
        assert gravados["n_chunks"] == 2
        # Os digests descrevem os artefatos e não moram dentro deles.
        assert "hash_indice_vetorial" not in gravados
        assert "hash_chunks" not in gravados

    @pytest.mark.parametrize(
        "campo,valor",
        [
            ("provedor", "ollama"),
            ("modelo", "bge-m3"),
            ("dimensao", 1024),
            ("hash_corpus", "b" * 64),
        ],
    )
    def test_descritor_editado_a_mao_diverge_da_colecao(
        self, tmp_path, campo, valor
    ):
        """O JSON e a coleção são gravados juntos; divergir é adulteração."""
        destino = tmp_path / "indice"
        self._construir(destino)
        caminho = destino / indexacao.ARQUIVO_METADADOS_INDICE
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        bruto[campo] = valor
        caminho.write_text(json.dumps(bruto), encoding="utf-8")

        class ProvedorDoDescritor(_EmbeddingsPorEmpresa):
            nome = bruto["provedor"]
            modelo = bruto["modelo"]
            dimensao = bruto["dimensao"]

        with pytest.raises(
            indexacao.ErroConsistenciaIndice, match="divergem do descritor"
        ):
            indexacao.carregar_indice_chroma(
                ProvedorDoDescritor(), config=_config_biblioteca(), dir_indice=destino
            )

    def test_digest_detecta_vetor_adulterado_na_colecao(self, tmp_path):
        """Sucessor do checksum do binário FAISS, agora sobre o conteúdo.

        Trocar um vetor sem tocar em id, documento ou metadados é exatamente
        a corrupção que não produz erro nenhum na consulta — só similaridade
        sem sentido.
        """
        destino = tmp_path / "indice"
        self._construir(destino)
        colecao = indexacao._abrir_colecao_chroma(destino)
        colecao.update(ids=["BB_1T2026_0002"], embeddings=[[0.0, 1.0]])
        with pytest.raises(
            indexacao.ErroConsistenciaIndice, match="Digest do conteúdo"
        ):
            indexacao.carregar_indice_chroma(
                _EmbeddingsPorEmpresa(), config=_config_biblioteca(), dir_indice=destino
            )

    def test_digest_detecta_metadado_de_filtro_adulterado(self, tmp_path):
        """Trocar a empresa de um chunk mudaria a quem o `where` o entrega."""
        destino = tmp_path / "indice"
        self._construir(destino)
        colecao = indexacao._abrir_colecao_chroma(destino)
        colecao.update(
            ids=["BB_1T2026_0002"],
            metadatas=[{"empresa": "ITAU"}],
        )
        with pytest.raises(
            indexacao.ErroConsistenciaIndice, match="Digest do conteúdo"
        ):
            indexacao.carregar_indice_chroma(
                _EmbeddingsPorEmpresa(), config=_config_biblioteca(), dir_indice=destino
            )

    def test_reconstruir_no_mesmo_diretorio_nao_serve_colecao_obsoleta(
        self, tmp_path
    ):
        """O Chroma memoriza a instância por diretório.

        Sem limpar essa memória, a carga seguinte devolve a coleção ANTERIOR
        sem erro nenhum — o índice diria estar atualizado servindo vetores
        velhos. É o modo de falha silenciosa que a RNF09 existe para matar.
        """
        destino = tmp_path / "indice"
        provedor = _EmbeddingsPorEmpresa()
        self._construir(destino, [_chunk_de("ITAU", 1), _chunk_de("BB", 2)])
        _, primeiros = indexacao.carregar_indice_chroma(
            provedor, config=_config_biblioteca(), dir_indice=destino
        )
        assert {c.empresa for c in primeiros} == {"ITAU", "BB"}

        self._construir(destino, [_chunk_de("BTG", 3)])
        colecao, segundos = indexacao.carregar_indice_chroma(
            provedor, config=_config_biblioteca(), dir_indice=destino
        )
        assert [c.id for c in segundos] == ["BTG_1T2026_0003"]
        assert colecao.count() == 1
        assert colecao.get(include=[])["ids"] == ["BTG_1T2026_0003"]

    def test_ef_search_rebaixado_e_recusado(self, tmp_path):
        """`ef_search` menor que a coleção volta a tornar a busca aproximada.

        O FAISS anterior era IndexFlatIP — exato. Com ef_search padrão (100)
        mediu-se recall@5 de 0,51 contra a busca exata em 5.244 vetores, e o
        índice é fixado no tamanho da coleção para reaver o recall 1,000.
        Rebaixar esse parâmetro degrada a recuperação sem erro visível.
        """
        destino = tmp_path / "indice"
        chunks = [_chunk_de("ITAU", 1), _chunk_de("BB", 2)]
        metadados = self._construir(destino, chunks)
        cliente = indexacao._abrir_cliente_chroma(destino)
        cliente.delete_collection(indexacao.COLECAO_CHROMA)
        colecao = cliente.create_collection(
            name=indexacao.COLECAO_CHROMA,
            configuration={
                "hnsw": {
                    "space": indexacao.ESPACO_DISTANCIA_CHROMA,
                    "ef_search": indexacao.EF_BUSCA_MINIMA - 1,
                }
            },
            metadata=indexacao._metadados_para_colecao(metadados),
        )
        colecao.add(
            ids=[c.id for c in chunks],
            embeddings=_EmbeddingsPorEmpresa().embedar(
                [c.texto for c in chunks]
            ).tolist(),
            documents=[c.texto for c in chunks],
            metadatas=[
                {campo: getattr(c, campo)
                 for campo in indexacao.CAMPOS_METADADOS_CHROMA}
                for c in chunks
            ],
        )
        with pytest.raises(indexacao.ErroConsistenciaIndice, match="ef_search"):
            indexacao.carregar_indice_chroma(
                _EmbeddingsPorEmpresa(), config=_config_biblioteca(), dir_indice=destino
            )

    def test_colecao_ausente_falha_com_mensagem_clara(self, tmp_path):
        destino = tmp_path / "indice"
        self._construir(destino)
        cliente = indexacao._abrir_cliente_chroma(destino)
        cliente.delete_collection(indexacao.COLECAO_CHROMA)
        with pytest.raises(
            indexacao.ErroConsistenciaIndice, match="ausente|reconstrua"
        ):
            indexacao.carregar_indice_chroma(
                _EmbeddingsPorEmpresa(), config=_config_biblioteca(), dir_indice=destino
            )


class TestIndiceFaissLegado:
    """Diretório do armazenamento antigo: falhar alto, nunca responder."""

    def test_arquivo_faiss_no_diretorio_manda_reconstruir(self, tmp_path):
        destino = tmp_path / "indice"
        TestMigracaoChromaRNF09._construir(destino)
        (destino / indexacao.ARQUIVO_INDICE_FAISS_LEGADO).write_bytes(b"legado")
        for carregar in (
            lambda: indexacao.carregar_indice_chroma(
                _EmbeddingsPorEmpresa(), config=_config_biblioteca(), dir_indice=destino
            ),
            lambda: indexacao.carregar_indice_bm25(
                config=_config_biblioteca(), dir_indice=destino
            ),
            lambda: indexacao.carregar_metadados_indice(destino),
        ):
            with pytest.raises(
                indexacao.ErroConsistenciaIndice, match="FAISS anterior"
            ) as erro:
                carregar()
            assert "reconstrua o índice" in str(erro.value).lower()

    def test_descritor_com_campo_faiss_manda_reconstruir(self, tmp_path):
        """Descritor legado: `hash_indice_faiss` em vez de campo desconhecido.

        Sem esta guarda o erro seria um TypeError genérico de construtor, que
        não diz ao operador o que fazer.
        """
        destino = tmp_path / "indice"
        destino.mkdir()
        (destino / indexacao.ARQUIVO_METADADOS_INDICE).write_text(
            json.dumps(
                {
                    "provedor": "ollama",
                    "modelo": "bge-m3",
                    "dimensao": 1024,
                    "data_construcao": "2026-07-15T00:00:00+00:00",
                    "hash_corpus": "a" * 64,
                    "n_chunks": 5244,
                    "hash_chunks": "b" * 64,
                    "hash_indice_faiss": "c" * 64,
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(
            indexacao.ErroConsistenciaIndice, match="FAISS anterior"
        ):
            indexacao.carregar_metadados_indice(destino)

    def test_diretorio_legado_nao_ganha_banco_chroma_vazio(self, tmp_path):
        """A recusa precede qualquer escrita.

        Abrir um `PersistentClient` num diretório legado criaria um
        `chroma.sqlite3` vazio e deixaria o índice num terceiro estado, nem
        FAISS nem Chroma.
        """
        destino = tmp_path / "indice"
        destino.mkdir()
        (destino / indexacao.ARQUIVO_INDICE_FAISS_LEGADO).write_bytes(b"legado")
        with pytest.raises(indexacao.ErroConsistenciaIndice):
            indexacao._abrir_colecao_chroma(destino)
        assert not (destino / indexacao.ARQUIVO_SQLITE_CHROMA).exists()
        assert sorted(p.name for p in destino.iterdir()) == ["indice.faiss"]

    def test_salvar_chunks_recusa_sobrescrever_indice_legado(self, tmp_path):
        destino = tmp_path / "indice"
        destino.mkdir()
        (destino / indexacao.ARQUIVO_INDICE_FAISS_LEGADO).write_bytes(b"legado")
        with pytest.raises(
            indexacao.ErroConsistenciaIndice, match="Recusado sobrescrever"
        ):
            indexacao.salvar_chunks([_chunk(1)], destino)


class TestIdentidadeExtracaoNoOrquestrador:
    def test_mudanca_durante_ingestao_descarta_chunks(
        self, monkeypatch
    ):
        import executar_pipeline

        antes = indexacao.IdentidadeExtracaoIndice("pdfplumber")
        depois = indexacao.IdentidadeExtracaoIndice(
            "mistral_ocr", "a" * 64, "b" * 64
        )
        identidades = iter((antes, depois))
        monkeypatch.setattr(
            indexacao,
            "calcular_identidade_extracao",
            lambda *_: next(identidades),
        )
        monkeypatch.setattr(ingestao, "ingerir_corpus", lambda *_, **__: [_chunk(1)])
        monkeypatch.setattr(
            executar_pipeline,
            "_CHUNKS_DA_EXECUCAO",
            (_config_biblioteca(), False, [_chunk(99)], antes),
        )
        with pytest.raises(RuntimeError, match="mudou durante a ingestão"):
            executar_pipeline.etapa_ingestao(_config_biblioteca(), amostra=False)
        assert executar_pipeline._CHUNKS_DA_EXECUCAO is None

    def test_mudanca_antes_dos_embeddings_impede_criar_provedor(
        self, monkeypatch
    ):
        import executar_pipeline

        identidade_chunks = indexacao.IdentidadeExtracaoIndice("pdfplumber")
        identidade_atual = indexacao.IdentidadeExtracaoIndice(
            "mistral_ocr", "a" * 64, "b" * 64
        )
        config = _config_biblioteca()
        monkeypatch.setattr(
            executar_pipeline,
            "_CHUNKS_DA_EXECUCAO",
            (config, False, [_chunk(1)], identidade_chunks),
        )
        monkeypatch.setattr(
            indexacao,
            "calcular_identidade_extracao",
            lambda *_: identidade_atual,
        )
        monkeypatch.setattr(
            indexacao,
            "fabricar_provedor_embeddings",
            lambda *_: pytest.fail("mismatch deve preceder o provedor"),
        )
        with pytest.raises(RuntimeError, match="mudou antes dos embeddings"):
            executar_pipeline.etapa_indexacao(config, amostra=False)


class TestNovosAdaptadoresEmbeddings:
    @pytest.mark.parametrize("classe", [indexacao.EmbeddingsOpenAI, indexacao.EmbeddingsAzureOpenAI])
    def test_sdk_preserva_ordem_e_normaliza(self, classe):
        if classe is indexacao.EmbeddingsOpenAI:
            provedor = classe(Config(openai_api_key="chave-teste"))
            modelo_esperado = "text-embedding-3-small"
        else:
            provedor = classe(
                Config(
                    azure_openai_endpoint="https://exemplo.openai.azure.com",
                    azure_openai_api_key="chave-teste",
                    azure_openai_api_version="2025-01-01-preview",
                    azure_openai_deployment_embedding="deployment-teste",
                )
            )
            modelo_esperado = "deployment-teste"
        chamadas = []

        class Embeddings:
            def create(self, **kwargs):
                chamadas.append(kwargs)
                return SimpleNamespace(
                    data=[
                        SimpleNamespace(index=1, embedding=[0.0, 4.0, 0.0]),
                        SimpleNamespace(index=0, embedding=[3.0, 0.0, 0.0]),
                    ]
                )

        provedor.dimensao = 3
        provedor._cliente = SimpleNamespace(embeddings=Embeddings())
        matriz = provedor.embedar(["primeiro", "segundo"])
        assert chamadas == [{"model": modelo_esperado, "input": ["primeiro", "segundo"]}]
        np.testing.assert_allclose(matriz, [[1, 0, 0], [0, 1, 0]])
        assert matriz.dtype == np.float32

    def test_local_carrega_sob_demanda_e_valida_dimensao(self):
        chamadas = []

        class Modelo:
            def get_sentence_embedding_dimension(self):
                return 3

            def encode(self, textos, **kwargs):
                chamadas.append((textos, kwargs))
                return [[3.0, 0.0, 0.0] for _ in textos]

        provedor = indexacao.EmbeddingsLocal()
        provedor.dimensao = 3
        provedor._modelo_carregado = Modelo()
        matriz = provedor.embedar(["texto"])
        np.testing.assert_allclose(matriz, [[1, 0, 0]])
        assert chamadas[0][1]["normalize_embeddings"] is True

    def test_azure_exige_api_version(self):
        with pytest.raises(ValueError, match="AZURE_OPENAI_API_VERSION"):
            indexacao.EmbeddingsAzureOpenAI(
                Config(
                    azure_openai_endpoint="https://exemplo.openai.azure.com",
                    azure_openai_api_key="chave-teste",
                    azure_openai_deployment_embedding="deployment-teste",
                )
            )

    def test_azure_rejeita_endpoint_nao_oficial_antes_de_criar_cliente(self):
        with pytest.raises(ValueError, match="chave não será enviada"):
            indexacao.EmbeddingsAzureOpenAI(
                Config(
                    azure_openai_endpoint="https://coletor.exemplo.invalid",
                    azure_openai_api_key="chave-teste",
                    azure_openai_api_version="2025-01-01-preview",
                    azure_openai_deployment_embedding="deployment-teste",
                )
            )
