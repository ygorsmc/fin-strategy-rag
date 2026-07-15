"""Recuperação top-k com filtro de metadados e subconsulta por banco.

Seção 5.6 (RF06) + estratégias E0–E3 da seção 5.10. A decomposição por
instituição nas perguntas comparativas evita o modo de falha nº 6 (top-k
dominado por um único banco).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.config import Config
from src.ingestao import Chunk


class Estrategia(str, Enum):
    """Vocabulário idêntico ao aceito em ESTRATEGIA_PADRAO no .env (5.14)."""

    CLOSED_BOOK = "closed_book"  # E0 — diagnóstico, não candidata
    KEYWORD = "keyword"          # E1 — BM25
    SEMANTICA = "semantica"      # E2 — embeddings (estratégia-alvo)
    HIBRIDA = "hibrida"          # E3 — RRF de E1+E2 (Fase 2)


@dataclass(frozen=True)
class FiltroMetadados:
    """Restrições extraídas da pergunta (vocabulário fechado — sem NER)."""

    empresas: tuple[str, ...] = ()  # canônicas; vazio = sem filtro
    trimestre: str | None = None    # ex.: "1T2026"

    @property
    def comparativa(self) -> bool:
        """2+ bancos citados => decompor em subconsultas por instituição."""
        return len(self.empresas) >= 2


@dataclass(frozen=True)
class ResultadoRecuperacao:
    chunk: Chunk
    score: float
    origem: Estrategia  # qual índice produziu este hit (relevante na híbrida)


def extrair_filtro_metadados(pergunta: str) -> FiltroMetadados:
    """Correspondência de texto simples sobre a tabela de apelidos e o padrão
    de trimestre (`normalizacao.extrair_bancos_citados` /
    `extrair_trimestre_citado`) — suficiente para o vocabulário fechado de
    5 bancos e 4 trimestres (seção 5.6)."""
    raise NotImplementedError("Etapa 7 do AGENTS.md — extração de filtro")


def fusao_reciprocal_rank(
    rankings: list[list[ResultadoRecuperacao]], k: int = 60
) -> list[ResultadoRecuperacao]:
    """Reciprocal Rank Fusion para a estratégia E3 (seção 5.10)."""
    raise NotImplementedError("Etapa 7 do AGENTS.md — RRF (Fase 2)")


class Recuperador:
    """Fachada única de recuperação usada pela geração, avaliação e interface.

    Recebe os índices já carregados (a carga valida RNF09 em
    `indexacao.carregar_indice_faiss`).
    """

    def __init__(self, config: Config, indice_faiss=None, indice_bm25=None):
        self.config = config
        self._faiss = indice_faiss
        self._bm25 = indice_bm25

    def recuperar(
        self,
        pergunta: str,
        estrategia: Estrategia,
        top_k: int | None = None,
    ) -> list[ResultadoRecuperacao]:
        """Top-k trechos para a pergunta, conforme a estratégia.

        Contrato (seção 5.6):
          - CLOSED_BOOK devolve lista vazia (E0 não recupera nada);
          - filtro por empresa/trimestre é aplicado ANTES de rankear;
          - pergunta comparativa: top-k POR banco detectado, depois fusão —
            garante todas as instituições representadas no resultado.
        """
        raise NotImplementedError("Etapa 7 do AGENTS.md — recuperação top-k")
