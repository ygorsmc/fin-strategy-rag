"""Recuperação top-k com filtro de metadados e subconsulta por banco.

Seção 5.6 (RF06) + estratégias E0–E3 da seção 5.10. A decomposição por
instituição nas perguntas comparativas evita o modo de falha nº 6 (top-k
dominado por um único banco).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.config import Config
from src.indexacao import (
    ProvedorEmbeddings,
    carregar_indice_bm25,
    carregar_indice_faiss,
    fabricar_provedor_embeddings,
)
from src.ingestao import Chunk
from src.normalizacao import (
    extrair_bancos_citados,
    extrair_trimestre_citado,
    normalizar_texto_bm25,
)


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
    return FiltroMetadados(
        empresas=tuple(extrair_bancos_citados(pergunta)),
        trimestre=extrair_trimestre_citado(pergunta),
    )


def fusao_reciprocal_rank(
    rankings: list[list[ResultadoRecuperacao]], k: int = 60
) -> list[ResultadoRecuperacao]:
    """Reciprocal Rank Fusion para a estratégia E3 (seção 5.10)."""
    acumulado: dict[str, float] = {}
    primeiro: dict[str, ResultadoRecuperacao] = {}
    for ranking in rankings:
        for posicao, resultado in enumerate(ranking, start=1):
            chave = resultado.chunk.id
            acumulado[chave] = acumulado.get(chave, 0.0) + 1.0 / (k + posicao)
            primeiro.setdefault(chave, resultado)
    return [
        ResultadoRecuperacao(primeiro[chave].chunk, score, primeiro[chave].origem)
        for chave, score in sorted(acumulado.items(), key=lambda kv: -kv[1])
    ]


def _passa_filtro(chunk: Chunk, filtro: FiltroMetadados) -> bool:
    if filtro.empresas and chunk.empresa not in filtro.empresas:
        return False
    if filtro.trimestre and chunk.trimestre != filtro.trimestre:
        return False
    return True


def _intercalar_por_banco(
    rankings: list[list[ResultadoRecuperacao]], top_k: int
) -> list[ResultadoRecuperacao]:
    """Round-robin por posição de ranking: garante todas as instituições
    representadas no top-k final (modo de falha nº 6)."""
    resultado: list[ResultadoRecuperacao] = []
    vistos: set[str] = set()
    maior = max((len(r) for r in rankings), default=0)
    for posicao in range(maior):
        for ranking in rankings:
            if posicao < len(ranking) and ranking[posicao].chunk.id not in vistos:
                vistos.add(ranking[posicao].chunk.id)
                resultado.append(ranking[posicao])
    return resultado[:top_k]


class Recuperador:
    """Fachada única de recuperação usada pela geração, avaliação e interface.

    Recebe os índices já carregados (a carga valida RNF09 em
    `indexacao.carregar_indice_faiss`).
    """

    def __init__(
        self,
        config: Config,
        indice_faiss=None,
        indice_bm25=None,
        provedor_embeddings: ProvedorEmbeddings | None = None,
    ):
        self.config = config
        self._faiss = indice_faiss  # (faiss.Index, list[Chunk])
        self._bm25 = indice_bm25    # (BM25Okapi, list[Chunk])
        self._provedor = provedor_embeddings

    def _garantir_provedor(self) -> ProvedorEmbeddings:
        if self._provedor is None:
            self._provedor = fabricar_provedor_embeddings(self.config)
        return self._provedor

    def _garantir_faiss(self):
        if self._faiss is None:
            self._faiss = carregar_indice_faiss(self._garantir_provedor())
        return self._faiss

    def _garantir_bm25(self):
        if self._bm25 is None:
            self._bm25 = carregar_indice_bm25()
        return self._bm25

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
        top_k = top_k or self.config.top_k
        if estrategia == Estrategia.CLOSED_BOOK:
            return []
        filtro = extrair_filtro_metadados(pergunta)
        if filtro.comparativa:
            por_banco = [
                self._recuperar_filtrado(
                    pergunta,
                    estrategia,
                    FiltroMetadados((empresa,), filtro.trimestre),
                    top_k,
                )
                for empresa in filtro.empresas
            ]
            return _intercalar_por_banco(por_banco, top_k)
        return self._recuperar_filtrado(pergunta, estrategia, filtro, top_k)

    def _recuperar_filtrado(
        self,
        pergunta: str,
        estrategia: Estrategia,
        filtro: FiltroMetadados,
        top_k: int,
    ) -> list[ResultadoRecuperacao]:
        if estrategia == Estrategia.KEYWORD:
            return self._top_bm25(pergunta, filtro, top_k)
        if estrategia == Estrategia.SEMANTICA:
            return self._top_faiss(pergunta, filtro, top_k)
        if estrategia == Estrategia.HIBRIDA:
            return fusao_reciprocal_rank(
                [
                    self._top_bm25(pergunta, filtro, top_k),
                    self._top_faiss(pergunta, filtro, top_k),
                ]
            )[:top_k]
        raise ValueError(f"Estratégia sem recuperação definida: {estrategia!r}")

    def _top_bm25(
        self, pergunta: str, filtro: FiltroMetadados, top_k: int
    ) -> list[ResultadoRecuperacao]:
        bm25, chunks = self._garantir_bm25()
        scores = bm25.get_scores(normalizar_texto_bm25(pergunta))
        permitidos = [
            i for i, chunk in enumerate(chunks) if _passa_filtro(chunk, filtro)
        ]
        melhores = sorted(permitidos, key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            ResultadoRecuperacao(chunks[i], float(scores[i]), Estrategia.KEYWORD)
            for i in melhores
            if scores[i] > 0.0
        ]

    def _top_faiss(
        self, pergunta: str, filtro: FiltroMetadados, top_k: int
    ) -> list[ResultadoRecuperacao]:
        indice, chunks = self._garantir_faiss()
        consulta = self._garantir_provedor().embedar([pergunta])
        restrito = bool(filtro.empresas or filtro.trimestre)
        # Busca exata (IndexFlatIP): rankear tudo e filtrar equivale a rankear
        # só o subconjunto permitido — os scores são independentes entre si.
        k_busca = indice.ntotal if restrito else min(top_k, indice.ntotal)
        scores, posicoes = indice.search(consulta, k_busca)
        resultados: list[ResultadoRecuperacao] = []
        for score, posicao in zip(scores[0], posicoes[0]):
            if posicao < 0:
                continue
            chunk = chunks[int(posicao)]
            if not _passa_filtro(chunk, filtro):
                continue
            resultados.append(
                ResultadoRecuperacao(chunk, float(score), Estrategia.SEMANTICA)
            )
            if len(resultados) == top_k:
                break
        return resultados
