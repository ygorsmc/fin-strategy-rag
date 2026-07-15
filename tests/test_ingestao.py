"""Testes de ingestão/chunking e qualidade de dados (seções 5.3 e 5.4).

Cobre o formato do cabeçalho contextual, os esquemas dos CSVs versionados e —
como contratos pendentes — as regras estruturais de qualidade (RF03).
"""

from __future__ import annotations

import csv

import pytest

from src import ingestao
from src.config import CAMINHO_METADADOS_CORPUS, Config, carregar_config

pendente = pytest.mark.skip(
    reason="Boilerplate: implementação pendente — AGENTS.md etapa 4 (ingestão)"
)


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


@pendente
class TestGerarChunks:
    def test_tamanho_aproximado_e_overlap(self, config_padrao):
        """Nenhum chunk excede ~600 tokens e chunks consecutivos do mesmo
        documento compartilham ~100 tokens de sobreposição (seção 5.3)."""
        raise AssertionError("implementar com PDF sintético em tests/fixtures/")

    def test_respeita_limite_de_paragrafo_quando_possivel(self):
        raise AssertionError("implementar: não cortar frase ao meio")

    def test_ids_unicos_e_posicao_sequencial(self):
        raise AssertionError("implementar")


@pendente
class TestValidarQualidade:
    def test_rejeita_chunk_vazio_ou_so_controle(self):
        # RF03: nenhum chunk vazio ou só com caracteres de controle
        raise AssertionError("implementar")

    def test_rejeita_chunk_com_metadado_faltando(self):
        raise AssertionError("implementar")

    def test_documento_sem_chunks_minimos_e_marcado(self):
        # limiar mínimo de chunks por página (seção 5.4)
        raise AssertionError("implementar")

    def test_pagina_duplicada_no_mesmo_documento_e_marcada(self):
        raise AssertionError("implementar")

    def test_falha_em_um_documento_nao_derruba_o_pipeline(self):
        # continueOnFail: documento falho é marcado, execução segue (5.4)
        raise AssertionError("implementar")


@pendente
class TestTesteSentinela:
    def test_valor_ancora_presente_aprova_documento(self):
        raise AssertionError("implementar: âncora conferida após normalização pt-BR")

    def test_valor_ancora_ausente_reprova_e_aciona_parser_alternativo(self):
        # pypdf ↔ pdfplumber antes de marcar o documento como falho (5.4)
        raise AssertionError("implementar")


@pendente
class TestIngerirCorpusAmostra:
    def test_amostra_processa_1_banco_1_trimestre(self):
        # RNF01: smoke test de ponta a ponta em minutos
        raise AssertionError("implementar")
