"""Indexação vetorial (FAISS) e por palavra-chave (BM25) — seção 5.5, RF05.

Inclui a guarda de consistência RNF09: o índice grava provedor/modelo/dimensão
de construção e consultar com configuração diferente falha com erro explícito
— nunca similaridade silenciosamente sem sentido (modo de falha nº 5).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from openai import OpenAI

from src.config import DIR_INDICE_VETORIAL, Config
from src.ingestao import Chunk
from src.ollama import resolver_identidade_modelo_ollama

if TYPE_CHECKING:
    import numpy as np

ARQUIVO_METADADOS_INDICE = "metadados_construcao.json"


class ErroConsistenciaIndice(RuntimeError):
    """Índice construído com um embedding e consultado com outro (RNF09)."""


@dataclass(frozen=True)
class MetadadosIndice:
    """Gravados junto do índice na construção (seção 5.5)."""

    provedor: str
    modelo: str
    dimensao: int
    data_construcao: str  # ISO 8601
    hash_corpus: str  # hash do metadados.csv congelado
    n_chunks: int


class ProvedorEmbeddings(ABC):
    """Contrato plugável de embeddings (RNF06)."""

    nome: str
    modelo: str
    dimensao: int

    @abstractmethod
    def embedar(self, textos: list[str]) -> "np.ndarray":
        """Matriz (len(textos), dimensao), float32, L2-normalizada."""

    def identidade_modelo(self) -> str:
        """Identidade persistida no índice; provedores mutáveis sobrescrevem."""
        return self.modelo


class EmbeddingsLocal(ProvedorEmbeddings):
    """Modelo local multilíngue — custo zero, padrão em desenvolvimento.

    NUNCA usado na instância publicada (seção 5.13: nada de carregar centenas
    de MB de modelo em nuvem de 1 GB de RAM)."""

    nome = "local"
    modelo = "paraphrase-multilingual-MiniLM-L12-v2"
    dimensao = 384

    def embedar(self, textos: list[str]) -> "np.ndarray":
        raise NotImplementedError("Etapa 6 do AGENTS.md — embeddings locais")


class EmbeddingsOllama(ProvedorEmbeddings):
    """Embeddings locais pelo endpoint OpenAI-compatible do Ollama."""

    nome = "ollama"

    def __init__(self, config: Config):
        faltando = [
            nome
            for nome, valor in (
                ("OLLAMA_BASE_URL", config.ollama_base_url),
                ("OLLAMA_MODELO_EMBEDDING", config.ollama_modelo_embedding),
            )
            if not valor
        ]
        if faltando:
            raise ValueError(f"Variáveis Ollama ausentes: {faltando}")
        if config.ollama_embedding_dimensao <= 0:
            raise ValueError("OLLAMA_EMBEDDING_DIMENSAO deve ser positiva.")
        if config.ollama_embedding_batch_size <= 0:
            raise ValueError("OLLAMA_EMBEDDING_BATCH_SIZE deve ser positivo.")
        if config.ollama_timeout_s <= 0:
            raise ValueError("OLLAMA_TIMEOUT_S deve ser positivo.")
        self.modelo = config.ollama_modelo_embedding
        self.dimensao = config.ollama_embedding_dimensao
        self._batch_size = config.ollama_embedding_batch_size
        self._base_url = config.ollama_base_url
        self._timeout_s = config.ollama_timeout_s
        self._identidade_modelo: str | None = None
        self._cliente = OpenAI(
            base_url=config.ollama_base_url,
            api_key="ollama-local",
            timeout=config.ollama_timeout_s,
            max_retries=0,
        )

    def identidade_modelo(self) -> str:
        if self._identidade_modelo is None:
            self._identidade_modelo = resolver_identidade_modelo_ollama(
                self._base_url, self.modelo, self._timeout_s
            )
        return self._identidade_modelo

    def embedar(self, textos: list[str]) -> "np.ndarray":
        import numpy as np

        if not textos:
            return np.empty((0, self.dimensao), dtype=np.float32)

        vetores: list[list[float]] = []
        for inicio in range(0, len(textos), self._batch_size):
            lote = textos[inicio : inicio + self._batch_size]
            resposta = self._cliente.embeddings.create(model=self.modelo, input=lote)
            indices = [item.index for item in resposta.data]
            if sorted(indices) != list(range(len(lote))):
                raise RuntimeError(
                    "Ollama devolveu índices de embeddings inválidos: "
                    f"esperado={list(range(len(lote)))}, recebido={indices}"
                )
            dados = sorted(resposta.data, key=lambda item: item.index)
            if len(dados) != len(lote):
                raise RuntimeError(
                    "Ollama devolveu quantidade inesperada de embeddings: "
                    f"esperado={len(lote)}, recebido={len(dados)}"
                )
            vetores.extend(item.embedding for item in dados)

        matriz = np.asarray(vetores, dtype=np.float32)
        esperado = (len(textos), self.dimensao)
        if matriz.shape != esperado:
            raise RuntimeError(
                "Dimensão inesperada no embedding Ollama: "
                f"esperado={esperado}, recebido={matriz.shape}"
            )
        if not np.isfinite(matriz).all():
            raise RuntimeError("Embedding Ollama contém valor não finito.")
        normas = np.linalg.norm(matriz, axis=1, keepdims=True)
        if np.any(normas == 0):
            raise RuntimeError("Embedding Ollama devolveu vetor de norma zero.")
        return (matriz / normas).astype(np.float32, copy=False)


class EmbeddingsOpenAI(ProvedorEmbeddings):
    nome = "openai"
    modelo = "text-embedding-3-small"
    dimensao = 1536

    def __init__(self, config: Config):
        if not config.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY ausente — configure o .env (ver .env.example) "
                "ou use EMBEDDING_PROVIDER=local em desenvolvimento."
            )
        self._config = config

    def embedar(self, textos: list[str]) -> "np.ndarray":
        raise NotImplementedError("Etapa 6 do AGENTS.md — embeddings OpenAI")


class EmbeddingsAzureOpenAI(ProvedorEmbeddings):
    """Ramo A do gate G1 (seção 5.7) — só ativo se o gate passar."""

    nome = "azure_openai"
    modelo = "text-embedding-3-small"
    dimensao = 1536

    def __init__(self, config: Config):
        faltando = [
            n
            for n, v in (
                ("AZURE_OPENAI_ENDPOINT", config.azure_openai_endpoint),
                ("AZURE_OPENAI_API_KEY", config.azure_openai_api_key),
                ("AZURE_OPENAI_DEPLOYMENT_EMBEDDING", config.azure_openai_deployment_embedding),
            )
            if not v
        ]
        if faltando:
            raise ValueError(f"Variáveis Azure ausentes no .env: {faltando}")
        self._config = config

    def embedar(self, textos: list[str]) -> "np.ndarray":
        raise NotImplementedError("Etapa 6 do AGENTS.md — embeddings Azure")


def fabricar_provedor_embeddings(config: Config) -> ProvedorEmbeddings:
    """Dispatch por EMBEDDING_PROVIDER (RNF06)."""
    fabricas = {
        "local": lambda: EmbeddingsLocal(),
        "ollama": lambda: EmbeddingsOllama(config),
        "openai": lambda: EmbeddingsOpenAI(config),
        "azure_openai": lambda: EmbeddingsAzureOpenAI(config),
    }
    if config.embedding_provider not in fabricas:
        raise ValueError(
            f"EMBEDDING_PROVIDER desconhecido: {config.embedding_provider!r} "
            f"(aceitos: {sorted(fabricas)})"
        )
    return fabricas[config.embedding_provider]()


def validar_consistencia(
    metadados: MetadadosIndice, provedor: ProvedorEmbeddings
) -> None:
    """Guarda RNF09: falha com mensagem explícita se o par índice/consulta
    divergir em provedor, modelo ou dimensão."""
    divergencias = [
        f"{campo}: índice={valor_indice!r} vs consulta={valor_consulta!r}"
        for campo, valor_indice, valor_consulta in (
            ("provedor", metadados.provedor, provedor.nome),
            ("modelo", metadados.modelo, provedor.identidade_modelo()),
            ("dimensao", metadados.dimensao, provedor.dimensao),
        )
        if valor_indice != valor_consulta
    ]
    if divergencias:
        raise ErroConsistenciaIndice(
            "Índice vetorial incompatível com o provedor de consulta (RNF09). "
            "Reconstrua o índice ou ajuste EMBEDDING_PROVIDER. Divergências: "
            + "; ".join(divergencias)
        )


def salvar_metadados_indice(
    metadados: MetadadosIndice, dir_indice: Path = DIR_INDICE_VETORIAL
) -> Path:
    caminho = dir_indice / ARQUIVO_METADADOS_INDICE
    caminho.write_text(
        json.dumps(asdict(metadados), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return caminho


def carregar_metadados_indice(
    dir_indice: Path = DIR_INDICE_VETORIAL,
) -> MetadadosIndice:
    caminho = dir_indice / ARQUIVO_METADADOS_INDICE
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} não existe — construa o índice primeiro "
            "(executar_pipeline.py, etapa de indexação)."
        )
    return MetadadosIndice(**json.loads(caminho.read_text(encoding="utf-8")))


def construir_indice_faiss(
    chunks: list[Chunk],
    provedor: ProvedorEmbeddings,
    hash_corpus: str,
    dir_saida: Path = DIR_INDICE_VETORIAL,
) -> MetadadosIndice:
    """Embeda os chunks, grava o índice FAISS + mapeamento id->chunk +
    metadados de construção. Reconstrução é determinística a partir do corpus
    (seção 5.5 — sem estado oculto). O metadado de modelo deve usar
    `provedor.identidade_modelo()`, nunca apenas uma tag Ollama mutável."""
    raise NotImplementedError("Etapa 6 do AGENTS.md — construção FAISS")


def construir_indice_bm25(chunks: list[Chunk], dir_saida: Path = DIR_INDICE_VETORIAL):
    """Índice BM25 sobre os mesmos chunks, tokenizados por
    `normalizacao.normalizar_texto_bm25` (estratégia E1)."""
    raise NotImplementedError("Etapa 6 do AGENTS.md — construção BM25")


def carregar_indice_faiss(
    provedor_consulta: ProvedorEmbeddings, dir_indice: Path = DIR_INDICE_VETORIAL
):
    """Carrega o índice E valida a consistência (RNF09) antes de devolver."""
    validar_consistencia(carregar_metadados_indice(dir_indice), provedor_consulta)
    raise NotImplementedError("Etapa 6 do AGENTS.md — carga FAISS")
