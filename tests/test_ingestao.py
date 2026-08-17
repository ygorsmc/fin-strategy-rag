"""Testes de ingestão/chunking e qualidade de dados (seções 5.3 e 5.4).

Cobre o formato do cabeçalho contextual, os esquemas dos CSVs versionados e —
como contratos pendentes — as regras estruturais de qualidade (RF03).
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import replace

import pytest
import tiktoken

from src import ingestao
from src.config import CAMINHO_METADADOS_CORPUS, Config, carregar_config
from src.ingestao import Chunk, PaginaExtraida
from tests.fixtures.cache_ocr import escrever_cache_ocr
from tests.fixtures.pdf_sintetico import criar_pdf


def _chunk_de(doc, posicao: int, corpo: str, pagina: int = 1, **campos) -> Chunk:
    """Chunk bem formado a partir do documento de exemplo, com overrides."""
    valores = dict(
        id=f"{doc.empresa}_{doc.trimestre}_release_{posicao:04d}",
        empresa=doc.empresa,
        trimestre=doc.trimestre,
        documento=doc.documento,
        pagina_inicio=pagina,
        pagina_fim=pagina,
        posicao_no_documento=posicao,
    )
    valores.update(campos)
    cabecalho = ingestao.montar_cabecalho_contextual(
        valores["empresa"],
        valores["documento"],
        valores["trimestre"],
        valores["pagina_inicio"],
        valores["pagina_fim"],
    )
    return Chunk(texto=f"{cabecalho}\n{corpo}", **valores)


# --- Já implementado (deve passar) -------------------------------------------


class TestCabecalhoContextual:
    def test_pagina_unica(self):
        assert (
            ingestao.montar_cabecalho_contextual(
                "ITAU", "itau_release_4T2025", "4T2025", 12, 12
            )
            == "[ITAU | itau_release_4T2025 | 4T2025 | pág. 12]"
        )

    def test_chunk_que_cruza_paginas_registra_intervalo(self):
        # Seção 5.3: a citação herda o intervalo (ex.: págs. 12–13)
        assert (
            ingestao.montar_cabecalho_contextual(
                "BB", "bb_release_1T2026", "1T2026", 12, 13
            )
            == "[BB | bb_release_1T2026 | 1T2026 | págs. 12–13]"
        )


class TestEsquemaMetadadosCorpus:
    def test_manifesto_existe_com_esquema_correto(self):
        # O metadados.csv é a fonte de verdade do corpus (seção 5.2)
        with open(CAMINHO_METADADOS_CORPUS, newline="", encoding="utf-8") as f:
            cabecalho = tuple(next(csv.reader(f)))
        assert cabecalho == ingestao.COLUNAS_METADADOS_CORPUS

    def test_carregar_metadados_valida_esquema(self, tmp_path):
        ruim = tmp_path / "metadados.csv"
        ruim.write_text("empresa,url\nITAU,x\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Esquema inesperado"):
            ingestao.carregar_metadados_corpus(ruim)


class TestChunkDataclass:
    def test_campos_de_citacao_obrigatorios(self, chunks_exemplo):
        # RN01 depende destes 5 metadados em todo chunk
        for chunk in chunks_exemplo:
            for campo in (
                "empresa",
                "trimestre",
                "documento",
                "pagina_inicio",
                "posicao_no_documento",
            ):
                assert getattr(chunk, campo) not in ("", None)

    def test_texto_comeca_com_cabecalho_contextual(self, chunks_exemplo):
        for chunk in chunks_exemplo:
            assert chunk.texto.startswith(
                ingestao.montar_cabecalho_contextual(
                    chunk.empresa,
                    chunk.documento,
                    chunk.trimestre,
                    chunk.pagina_inicio,
                    chunk.pagina_fim,
                )
            )


class TestConfigPadrao:
    def test_defaults_de_chunking_da_secao_5_14(self, config_padrao: Config):
        assert config_padrao.chunk_tamanho_tokens == 600
        assert config_padrao.chunk_sobreposicao_tokens == 100

    def test_env_sobrescreve_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CHUNK_TAMANHO_TOKENS", "300")
        config = carregar_config(env_file=tmp_path / "inexistente.env")
        assert config.chunk_tamanho_tokens == 300


# --- Contratos pendentes (etapa 4) -------------------------------------------


class TestGerarChunks:
    def test_tamanho_aproximado_e_overlap(self, config_padrao, documento_exemplo):
        """Nenhum chunk excede ~600 tokens e chunks consecutivos do mesmo
        documento compartilham ~100 tokens de sobreposição (seção 5.3)."""
        paragrafos = [
            f"Paragrafo {i}: " + "a receita liquida cresceu no periodo " * 8
            for i in range(40)
        ]
        pagina = PaginaExtraida(documento_exemplo, 1, "\n".join(paragrafos))
        chunks = ingestao.gerar_chunks([pagina], config_padrao)
        assert len(chunks) > 1

        enc = tiktoken.get_encoding("cl100k_base")
        for chunk in chunks:
            assert len(enc.encode(chunk.texto)) <= config_padrao.chunk_tamanho_tokens

        for anterior, seguinte in zip(chunks, chunks[1:]):
            corpo_anterior = anterior.texto.split("\n", 1)[1]
            corpo_seguinte = seguinte.texto.split("\n", 1)[1]
            prefixo = corpo_seguinte[:80]
            assert prefixo and prefixo in corpo_anterior

    def test_respeita_limite_de_paragrafo_quando_possivel(self, documento_exemplo):
        config = Config(chunk_tamanho_tokens=200, chunk_sobreposicao_tokens=40)
        paragrafos = [
            f"Frase inteira numero {i} sobre o resultado do trimestre." for i in range(30)
        ]
        pagina = PaginaExtraida(documento_exemplo, 1, "\n".join(paragrafos))
        chunks = ingestao.gerar_chunks([pagina], config)
        assert len(chunks) > 1
        corpos = [c.texto.split("\n", 1)[1] for c in chunks]
        for paragrafo in paragrafos:
            assert any(paragrafo in corpo for corpo in corpos)

    def test_ids_unicos_e_posicao_sequencial(self, config_padrao, documento_exemplo):
        texto = "\n".join(
            f"Linha {i}: " + "resultado operacional recorrente do banco " * 6
            for i in range(40)
        )
        chunks = ingestao.gerar_chunks(
            [PaginaExtraida(documento_exemplo, 1, texto)], config_padrao
        )
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))
        assert [c.posicao_no_documento for c in chunks] == list(
            range(1, len(chunks) + 1)
        )


def _tabela_markdown(n_linhas: int) -> str:
    return "| Métrica | 1T26 | 4T25 |\n| --- | --- | --- |\n" + "\n".join(
        f"| Linha {i} | {i}.000 | {i}.100 |" for i in range(n_linhas)
    )


def _paragrafos(n: int) -> str:
    return "\n".join(
        f"Paragrafo {i} sobre o resultado do trimestre, com extensão razoável."
        for i in range(n)
    )


class TestChunkingPorBloco:
    """Limite de bloco (5.3) — a razão declarada de ter trocado o extrator."""

    def test_segmentacao_separa_tabela_de_texto_e_acha_o_cabecalho(self):
        blocos = ingestao.segmentar_blocos(
            "Introdução do capítulo.\n\n" + _tabela_markdown(2) + "\n\nRodapé."
        )
        assert [bloco.tipo for bloco in blocos] == ["texto", "tabela", "texto"]
        assert blocos[1].cabecalho == (
            "| Métrica | 1T26 | 4T25 |",
            "| --- | --- | --- |",
        )

    def test_separador_depois_da_linha_de_dados_ainda_e_cabecalho(self):
        """O OCR às vezes emite a linha de dados antes do `| --- |`."""
        bloco = ingestao.segmentar_blocos(
            "| Margem | 31.506 | 31.717 |\n| --- | --- | --- |\n| Total | 1 | 2 |"
        )[0]
        assert bloco.tipo == "tabela"
        assert len(bloco.cabecalho) == 2

    def test_tabela_que_cabe_nunca_e_dividida(self, documento_exemplo):
        config = Config(chunk_tamanho_tokens=220, chunk_sobreposicao_tokens=40)
        tabela = _tabela_markdown(4)
        pagina = PaginaExtraida(
            documento_exemplo,
            1,
            f"{_paragrafos(10)}\n\n{tabela}\n\n{_paragrafos(10)}",
        )
        chunks = ingestao.gerar_chunks([pagina], config)
        inteiros = [
            chunk
            for chunk in chunks
            if all(linha in chunk.texto for linha in tabela.splitlines())
        ]
        assert len(inteiros) == 1, "a tabela precisa sobreviver íntegra em um chunk"

    def test_tabela_grande_e_dividida_com_o_cabecalho_em_cada_parte(
        self, documento_exemplo
    ):
        config = Config(chunk_tamanho_tokens=220, chunk_sobreposicao_tokens=40)
        tabela = _tabela_markdown(40)
        linhas = tabela.splitlines()
        cabecalho, corpo = linhas[:2], linhas[2:]
        pagina = PaginaExtraida(documento_exemplo, 1, tabela)
        chunks = ingestao.gerar_chunks([pagina], config)
        partes = [chunk for chunk in chunks if "tabela" in chunk.tipo_bloco]
        assert len(partes) > 1, "a tabela deveria ter sido dividida"
        for parte in partes:
            assert all(linha in parte.texto for linha in cabecalho), (
                "número sem o rótulo da coluna é número inútil para citação"
            )
        for linha in corpo:
            assert any(linha in parte.texto for parte in partes)

    def test_tipo_bloco_registra_o_que_o_chunk_contem(self, documento_exemplo):
        config = Config(chunk_tamanho_tokens=200, chunk_sobreposicao_tokens=0)
        so_texto = ingestao.gerar_chunks(
            [PaginaExtraida(documento_exemplo, 1, _paragrafos(3))], config
        )
        assert {chunk.tipo_bloco for chunk in so_texto} == {"texto"}

        so_tabela = ingestao.gerar_chunks(
            [PaginaExtraida(documento_exemplo, 1, _tabela_markdown(2))], config
        )
        assert {chunk.tipo_bloco for chunk in so_tabela} == {"tabela"}

        misto = ingestao.gerar_chunks(
            [
                PaginaExtraida(
                    documento_exemplo,
                    1,
                    f"Frase de abertura.\n{_tabela_markdown(2)}",
                )
            ],
            config,
        )
        assert {chunk.tipo_bloco for chunk in misto} == {"tabela+texto"}

    def test_cabecalho_do_tamanho_de_um_paragrafo_nao_e_repetido(
        self, documento_exemplo
    ):
        """Regressão medida no corpus (Bradesco 2T2025, pág. 174).

        Páginas em duas colunas voltam do OCR como tabela cuja primeira linha é
        um parágrafo inteiro. Repeti-la em cada parte não rotula coluna nenhuma:
        enche as partes de texto duplicado e chega a produzir chunks idênticos,
        que a validação RF03 então reprova — jogando o documento inteiro no
        extrator alternativo por um artefato de layout.
        """
        config = Config(chunk_tamanho_tokens=220, chunk_sobreposicao_tokens=40)
        paragrafo = (
            "|   | " + "texto corrido do relatório do comitê de auditoria " * 40
            + " |"
        )
        tabela = (
            f"{paragrafo}\n| --- | --- |\n"
            + "\n".join(f"|  Item {i}  | valor {i} |" for i in range(8))
        )
        chunks = ingestao.gerar_chunks(
            [PaginaExtraida(documento_exemplo, 1, tabela)], config
        )
        corpos = [chunk.texto.split("\n", 1)[1] for chunk in chunks]
        assert len(corpos) == len(set(corpos)), "chunks idênticos gerados"
        relatorio = ingestao.validar_qualidade(chunks, [documento_exemplo])
        assert relatorio.aprovado, relatorio.documentos_falhos

    def test_chunk_nunca_excede_o_teto_mesmo_com_tabela(self, documento_exemplo):
        config = Config(chunk_tamanho_tokens=220, chunk_sobreposicao_tokens=40)
        pagina = PaginaExtraida(
            documento_exemplo,
            1,
            f"{_paragrafos(5)}\n\n{_tabela_markdown(40)}\n\n{_paragrafos(5)}",
        )
        enc = tiktoken.get_encoding("cl100k_base")
        for chunk in ingestao.gerar_chunks([pagina], config):
            assert len(enc.encode(chunk.texto)) <= config.chunk_tamanho_tokens


class TestValidarQualidade:
    def test_rejeita_chunk_vazio_ou_so_controle(self, documento_exemplo):
        # RF03: nenhum chunk vazio ou só com caracteres de controle
        chunks = [_chunk_de(documento_exemplo, 1, "\x00\x01  \x1f")]
        relatorio = ingestao.validar_qualidade(chunks, [documento_exemplo])
        assert not relatorio.aprovado
        assert "vazio" in relatorio.documentos_falhos[documento_exemplo.documento]

    def test_rejeita_chunk_com_metadado_faltando(self, documento_exemplo):
        chunks = [
            _chunk_de(documento_exemplo, 1, "Lucro de R$ 1,0 bilhao.", empresa="")
        ]
        relatorio = ingestao.validar_qualidade(chunks, [documento_exemplo])
        assert not relatorio.aprovado
        assert "metadado" in relatorio.documentos_falhos[documento_exemplo.documento]

    @pytest.mark.parametrize(
        "tipo_bloco", ["", "planilha", "texto+tabela", "tabela+tabela"]
    )
    def test_rejeita_tipo_de_bloco_fora_do_contrato(
        self, documento_exemplo, tipo_bloco
    ):
        """`tipo_bloco` é metadado de citação/diagnóstico (5.3/5.4): valor
        inventado ou fora da ordem canônica não pode entrar no índice."""
        chunks = [
            _chunk_de(
                documento_exemplo,
                1,
                "Lucro de R$ 1,0 bilhao.",
                tipo_bloco=tipo_bloco,
            )
        ]
        relatorio = ingestao.validar_qualidade(chunks, [documento_exemplo])
        assert not relatorio.aprovado
        assert "tipo de bloco" in relatorio.documentos_falhos[
            documento_exemplo.documento
        ]

    def test_documento_sem_chunks_minimos_e_marcado(self, documento_exemplo):
        # limiar mínimo de chunks por página (seção 5.4): 2 chunks para um
        # documento cuja última página é a 10 fica abaixo de 0.5/pág.
        chunks = [
            _chunk_de(documento_exemplo, 1, "Primeiro trecho do release."),
            _chunk_de(documento_exemplo, 2, "Trecho final do release.", pagina=10),
        ]
        relatorio = ingestao.validar_qualidade(
            chunks, [documento_exemplo], minimo_chunks_por_pagina=0.5
        )
        assert not relatorio.aprovado
        assert documento_exemplo.documento in relatorio.documentos_falhos

    def test_pagina_duplicada_no_mesmo_documento_e_marcada(self, documento_exemplo):
        corpo = "O lucro liquido atingiu R$ 2,3 bilhoes."
        chunks = [
            _chunk_de(documento_exemplo, 1, corpo),
            _chunk_de(documento_exemplo, 2, corpo),
        ]
        relatorio = ingestao.validar_qualidade(chunks, [documento_exemplo])
        assert not relatorio.aprovado
        assert "duplicada" in relatorio.documentos_falhos[documento_exemplo.documento]

    def test_bloco_repetido_em_paginas_diferentes_e_aviso_e_nao_falha(
        self, documento_exemplo
    ):
        """Medido no corpus (BB 2T2025, págs. 206 e 209).

        Um release repete o mesmo bloco de notas de rodapé sob tabelas de
        páginas distintas. Isso não é página duplicada — a regra normativa da
        5.4 é sobre página, e ela continua dura no teste acima e na checagem de
        `paginas_extraidas`. Aqui o correto é registrar, não reprovar.
        """
        corpo = "1 - Refere-se ao saldo inicial ajustado no periodo."
        chunks = [
            _chunk_de(documento_exemplo, 1, corpo, pagina=206),
            _chunk_de(documento_exemplo, 2, corpo, pagina=209),
        ]
        relatorio = ingestao.validar_qualidade(
            chunks, [documento_exemplo], minimo_chunks_por_pagina=0
        )
        assert relatorio.aprovado
        assert any("bloco repetido" in aviso for aviso in relatorio.avisos)

    def test_falha_em_um_documento_nao_derruba_o_pipeline(self, documento_exemplo):
        # continueOnFail: documento falho é marcado, execução segue (5.4)
        from src.ingestao import DocumentoCorpus

        doc_bom = DocumentoCorpus(
            empresa="BB",
            trimestre="1T2026",
            documento="bb_release_1T2026",
            url="https://exemplo.invalido/bb.pdf",
            data_coleta="2026-07-15",
            hash_sha256="0" * 64,
        )
        chunks = [
            _chunk_de(documento_exemplo, 1, "\x00"),  # falho: vazio/controle
            _chunk_de(doc_bom, 1, "A carteira de credito cresceu 8,2% no ano."),
        ]
        relatorio = ingestao.validar_qualidade(chunks, [documento_exemplo, doc_bom])
        assert documento_exemplo.documento in relatorio.documentos_falhos
        assert relatorio.documentos_ok == [doc_bom.documento]


class TestTesteSentinela:
    def test_valor_ancora_presente_aprova_documento(self, chunks_exemplo):
        # "R$ 10,9 bilhões" no fixture -> âncora 10.9e9 conferida após
        # normalização numérica pt-BR
        assert ingestao.teste_sentinela(chunks_exemplo, [10_900_000_000.0])

    def test_valor_ancora_ausente_reprova_e_aciona_parser_alternativo(
        self, tmp_path, documento_exemplo
    ):
        # A âncora ausente reprova a extração (gatilho do fallback); o parser
        # alternativo pdfplumber extrai o mesmo conteúdo (pypdf ↔ pdfplumber, 5.4)
        assert not ingestao.teste_sentinela(
            [_chunk_de(documento_exemplo, 1, "Lucro de R$ 2,3 bilhoes.")],
            [9_870_000_000.0],
        )
        pdf = criar_pdf(
            tmp_path / "doc.pdf", ["Lucro liquido de R$ 2,3 bilhoes no 4T2025."]
        )
        paginas = ingestao.extrair_paginas(
            pdf, documento_exemplo, parser="pdfplumber"
        )
        assert len(paginas) == 1
        assert "2,3 bilhoes" in paginas[0].texto


class TestIngestaoComCacheOCR:
    """Fluxo de `EXTRATOR=mistral_ocr` (spec 5.3/5.4)."""

    @staticmethod
    def _manifesto(tmp_path, documentos):
        caminho = tmp_path / "metadados.csv"
        caminho.write_text(
            ",".join(ingestao.COLUNAS_METADADOS_CORPUS)
            + "\n"
            + "\n".join(
                ",".join(
                    (
                        d.empresa,
                        d.trimestre,
                        d.documento,
                        d.url,
                        d.data_coleta,
                        d.hash_sha256,
                    )
                )
                for d in documentos
            )
            + "\n",
            encoding="utf-8",
        )
        return caminho

    @staticmethod
    def _doc(empresa, trimestre, digest):
        return ingestao.DocumentoCorpus(
            empresa=empresa,
            trimestre=trimestre,
            documento=f"{empresa.lower()}_release_{trimestre}",
            url=f"https://exemplo.invalido/{empresa.lower()}.pdf",
            data_coleta="2026-08-11",
            hash_sha256=digest,
        )

    def test_sentinela_reprovado_no_cache_cai_para_a_biblioteca(
        self, tmp_path, capsys
    ):
        """Fallback OCR → pdfplumber da spec 5.4, com a troca declarada."""
        config = replace(Config(), extrator="mistral_ocr")
        raw = tmp_path / "raw"
        raw.mkdir()
        bom = self._doc("BB", "1T2026", "a" * 64)
        ruim = self._doc("ITAU", "1T2026", "b" * 64)
        escrever_cache_ocr(
            tmp_path, bom, ["Lucro liquido de R$ 2,3 bilhoes no trimestre."]
        )
        escrever_cache_ocr(
            tmp_path, ruim, ["Página sem nenhum valor financeiro reconhecível."]
        )
        pdf = criar_pdf(
            raw / f"{ruim.documento}.pdf",
            ["Lucro liquido de R$ 9,9 bilhoes no trimestre."],
        )
        ruim = replace(
            ruim, hash_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest()
        )
        escrever_cache_ocr(
            tmp_path, ruim, ["Página sem nenhum valor financeiro reconhecível."]
        )
        chunks = ingestao.ingerir_corpus(
            config,
            caminho_metadados=self._manifesto(tmp_path, [bom, ruim]),
            dir_raw=raw,
            dir_cache_ocr=tmp_path,
            valores_ancora_por_documento={
                bom.documento: [2_300_000_000.0],
                ruim.documento: [9_900_000_000.0],
            },
            exigir_todos_documentos=True,
        )
        por_documento = {
            documento: {
                chunk.provedores_extracao
                for chunk in chunks
                if chunk.documento == documento
            }
            for documento in (bom.documento, ruim.documento)
        }
        assert por_documento[bom.documento] == {"mistral"}
        assert por_documento[ruim.documento] == {"local"}
        assert "tentando o extrator alternativo" in capsys.readouterr().out

    def test_cache_reprovado_sem_pdf_local_reprova_o_documento(
        self, tmp_path, capsys
    ):
        """Sem PDF não há alternativa conferível — inventar seria pior."""
        config = replace(Config(), extrator="mistral_ocr")
        doc = self._doc("BB", "1T2026", "a" * 64)
        escrever_cache_ocr(tmp_path, doc, ["Página sem valor financeiro."])
        with pytest.raises(RuntimeError, match="corpus parcial"):
            ingestao.ingerir_corpus(
                config,
                caminho_metadados=self._manifesto(tmp_path, [doc]),
                dir_raw=tmp_path / "raw_inexistente",
                dir_cache_ocr=tmp_path,
                valores_ancora_por_documento={doc.documento: [9_900_000_000.0]},
                exigir_todos_documentos=True,
            )
        assert "não está em" in capsys.readouterr().out

    def test_indice_que_se_diz_ocr_sem_nenhuma_pagina_de_ocr_falha(
        self, tmp_path
    ):
        """Todos os documentos caindo na biblioteca com EXTRATOR=mistral_ocr
        produziria um índice que se apresenta como OCR sem ser."""
        config = replace(Config(), extrator="mistral_ocr")
        raw = tmp_path / "raw"
        raw.mkdir()
        doc = self._doc("BB", "1T2026", "a" * 64)
        pdf = criar_pdf(
            raw / f"{doc.documento}.pdf",
            ["Lucro liquido de R$ 9,9 bilhoes no trimestre."],
        )
        doc = replace(
            doc, hash_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest()
        )
        escrever_cache_ocr(tmp_path, doc, ["Página sem valor financeiro."])
        with pytest.raises(RuntimeError, match="nenhuma página indexada"):
            ingestao.ingerir_corpus(
                config,
                caminho_metadados=self._manifesto(tmp_path, [doc]),
                dir_raw=raw,
                dir_cache_ocr=tmp_path,
                valores_ancora_por_documento={doc.documento: [9_900_000_000.0]},
            )


class TestIngerirCorpusAmostra:
    def test_amostra_processa_1_banco_1_trimestre(self, tmp_path, config_padrao):
        # RNF01: smoke test de ponta a ponta em minutos
        raw = tmp_path / "raw"
        raw.mkdir()
        linhas = []
        for empresa in ("ITAU", "BB"):
            for trimestre in ("3T2025", "4T2025"):
                nome = f"{empresa.lower()}_release_{trimestre}"
                caminho_pdf = criar_pdf(
                    raw / f"{nome}.pdf",
                    [
                        f"Lucro de {empresa} no {trimestre}: R$ 1,0 bilhao.\n"
                        + "Linha adicional do release gerencial.\n" * 3
                    ],
                )
                linhas.append(
                    f"{empresa},{trimestre},{nome},"
                    f"https://exemplo.invalido/{nome}.pdf,2026-07-15,"
                    f"{hashlib.sha256(caminho_pdf.read_bytes()).hexdigest()}"
                )
        manifesto = tmp_path / "metadados.csv"
        manifesto.write_text(
            "empresa,trimestre,documento,url,data_coleta,hash_sha256\n"
            + "\n".join(linhas)
            + "\n",
            encoding="utf-8",
        )
        chunks = ingestao.ingerir_corpus(
            replace(config_padrao, extrator="pdfplumber"),
            amostra=True,
            caminho_metadados=manifesto,
            dir_raw=raw,
        )
        assert chunks
        assert {c.empresa for c in chunks} == {"ITAU"}
        assert {c.trimestre for c in chunks} == {"3T2025"}
