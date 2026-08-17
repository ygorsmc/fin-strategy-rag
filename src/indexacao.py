"""Indexação vetorial (ChromaDB) e por palavra-chave (BM25) — seção 5.6, RF05.

O armazenamento vetorial é uma coleção Chroma persistida no diretório do índice.
A troca de FAISS por Chroma é de **simplicidade estrutural, não de desempenho**:
a RF06 exige filtrar por empresa/trimestre ANTES de rankear, e FAISS indexa
vetores e nada mais — o filtro exigiria um índice de metadados paralelo,
sincronizado à mão, que é estado duplicado e fonte de bug silencioso. Chroma
guarda documento, metadados e vetor juntos e filtra nativamente (``where``).
FAISS seguiria tecnicamente válido, com mais código de sustentação.

Inclui a guarda de consistência RNF09: provedor/modelo/dimensão/data/hash do
corpus são gravados nos metadados da própria coleção *e* no descritor JSON, e
consultar com configuração diferente falha com erro explícito — nunca
similaridade silenciosamente sem sentido (modo de falha nº 5).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import re
import shutil
import tempfile
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import TYPE_CHECKING

from src.bloqueio import bloqueio_exclusivo
from src.config import (
    DIR_INDICE_VETORIAL,
    Config,
    endpoint_azure_openai_e_oficial,
)
from src.ingestao import TIPOS_BLOCO, Chunk
from src.ocr_corpus import DIR_CACHE_OCR
from src.ollama import resolver_identidade_modelo_ollama

if TYPE_CHECKING:
    import numpy as np

ARQUIVO_METADADOS_INDICE = "metadados_construcao.json"
ARQUIVO_CHUNKS = "chunks.json"
ARQUIVO_SQLITE_CHROMA = "chroma.sqlite3"
# Só existe para RECUSAR explicitamente um diretório do armazenamento antigo.
ARQUIVO_INDICE_FAISS_LEGADO = "indice.faiss"
CAMPO_METADADOS_FAISS_LEGADO = "hash_indice_faiss"
COLECAO_CHROMA = "chunks_release"

# Chaves do Chunk copiadas para os metadados da coleção. São exatamente as
# usadas em `where` (RF06) mais as que identificam a origem do trecho.
CAMPOS_METADADOS_CHROMA = (
    "empresa",
    "trimestre",
    "documento",
    "posicao_no_documento",
    "tipo_bloco",
)

# O FAISS usado antes era IndexFlatIP — busca EXATA. O HNSW do Chroma é
# aproximado, e com os parâmetros padrão (ef_search=100) mediu-se recall@5 de
# 0,51 contra a busca exata em 5.244 vetores de 1024 dimensões. Trocar o
# armazenamento não pode degradar silenciosamente a recuperação que a avaliação
# de estratégias mede, então `ef_search` é fixado no tamanho da coleção: a
# varredura passa a ser exaustiva e o recall@5 medido volta a 1,000 (custo
# medido: 4,9 ms por consulta contra 2,0 ms). A carga revalida esse parâmetro.
EF_BUSCA_MINIMA = 10
EF_BUSCA_MAXIMA = 100_000
ESPACO_DISTANCIA_CHROMA = "cosine"


class ErroConsistenciaIndice(RuntimeError):
    """Índice construído com um embedding e consultado com outro (RNF09)."""


@dataclass(frozen=True)
class IdentidadeExtracaoIndice:
    """Snapshot material da extração que precisa acompanhar os vetores.

    O extrator por biblioteca não depende do cache de OCR. Em ``mistral_ocr``,
    tanto o cache versionado quanto o código que transforma suas páginas em
    chunks participam da identidade do índice: trocar qualquer um dos dois muda
    os vetores e tem de invalidar o índice construído com o anterior (RNF09).
    """

    modo: str  # valores de EXTRATOR: "mistral_ocr" | "pdfplumber"
    hash_cache_ocr: str = ""
    fingerprint_derivacao_ocr: str = ""


@dataclass(frozen=True)
class MetadadosIndice:
    """Gravados junto do índice na construção (seção 5.5)."""

    provedor: str
    modelo: str
    dimensao: int
    data_construcao: str  # ISO 8601
    hash_corpus: str  # hash do metadados.csv congelado
    n_chunks: int
    hash_chunks: str = ""  # integridade e ordem do mapeamento posição->chunk
    # Digest do CONTEÚDO da coleção Chroma (ids, documentos, metadados e
    # vetores). Não é o hash dos arquivos: abrir a coleção para leitura já
    # reescreve `chroma.sqlite3` e os segmentos HNSW, então um checksum físico
    # falharia na segunda carga. O digest lógico cobre exatamente o que a
    # RNF09 precisa proteger — os vetores e seus metadados.
    hash_indice_vetorial: str = ""
    provedores_extracao: str = "local"
    modelos_extracao: str = ""
    hash_artefatos_extracao: str = ""
    n_artefatos_extracao: int = 0
    # O default aqui descreve ARTEFATO legado (descritor sem o campo), que só
    # pode ter vindo do extrator por biblioteca — e por isso difere do default
    # de `Config.extrator`, que descreve a CONFIGURAÇÃO atual e é o primário.
    # Um índice antigo com proveniência Mistral falha no confronto estrutural.
    extrator: str = "pdfplumber"
    hash_cache_ocr: str = ""
    fingerprint_derivacao_ocr: str = ""


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

    def __init__(self):
        self._modelo_carregado = None

    def embedar(self, textos: list[str]) -> "np.ndarray":
        import numpy as np

        if not textos:
            return np.empty((0, self.dimensao), dtype=np.float32)
        if self._modelo_carregado is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers não está instalado; instale as "
                    "dependências de requirements-local.txt antes de usar "
                    "EMBEDDING_PROVIDER=local."
                ) from exc
            self._modelo_carregado = SentenceTransformer(self.modelo)
            dimensao_real = self._modelo_carregado.get_sentence_embedding_dimension()
            if dimensao_real is not None and dimensao_real != self.dimensao:
                raise RuntimeError(
                    "Dimensão inesperada no modelo local: "
                    f"esperado={self.dimensao}, recebido={dimensao_real}"
                )
        vetores = self._modelo_carregado.encode(
            textos,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return _validar_e_normalizar_matriz(
            vetores, len(textos), self.dimensao, "local"
        )


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
        from src.ollama import endpoint_ollama_e_loopback

        if not endpoint_ollama_e_loopback(config.ollama_base_url):
            raise ValueError(
                "OLLAMA_BASE_URL deve apontar para loopback, sem credenciais."
            )
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
        from openai import OpenAI

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
        return _embedar_api_compativel(
            self._cliente,
            self.modelo,
            textos,
            self.dimensao,
            self._batch_size,
            "Ollama",
        )


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
        from openai import OpenAI

        self._cliente = OpenAI(api_key=config.openai_api_key, max_retries=0)

    def embedar(self, textos: list[str]) -> "np.ndarray":
        return _embedar_api_compativel(
            self._cliente,
            self.modelo,
            textos,
            self.dimensao,
            128,
            "OpenAI",
        )


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
                ("AZURE_OPENAI_API_VERSION", config.azure_openai_api_version),
                ("AZURE_OPENAI_DEPLOYMENT_EMBEDDING", config.azure_openai_deployment_embedding),
            )
            if not v
        ]
        if faltando:
            raise ValueError(f"Variáveis Azure ausentes no .env: {faltando}")
        if not endpoint_azure_openai_e_oficial(config.azure_openai_endpoint):
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT deve ser um endpoint HTTPS "
                "*.openai.azure.com; a chave não será enviada."
            )
        from openai import AzureOpenAI

        # Em Azure, o parâmetro ``model`` é o nome do deployment. Persisti-lo
        # na identidade impede consultar um índice após trocar de deployment.
        self.modelo = config.azure_openai_deployment_embedding
        self._cliente = AzureOpenAI(
            azure_endpoint=config.azure_openai_endpoint,
            api_key=config.azure_openai_api_key,
            api_version=config.azure_openai_api_version,
            max_retries=0,
        )

    def embedar(self, textos: list[str]) -> "np.ndarray":
        return _embedar_api_compativel(
            self._cliente,
            self.modelo,
            textos,
            self.dimensao,
            128,
            "Azure OpenAI",
        )


def _embedar_api_compativel(
    cliente,
    modelo: str,
    textos: list[str],
    dimensao: int,
    tamanho_lote: int,
    nome_provedor: str,
) -> "np.ndarray":
    """Implementação comum para endpoints compatíveis com o SDK OpenAI."""
    import numpy as np

    if not textos:
        return np.empty((0, dimensao), dtype=np.float32)
    vetores: list[list[float]] = []
    for inicio in range(0, len(textos), tamanho_lote):
        lote = textos[inicio : inicio + tamanho_lote]
        resposta = cliente.embeddings.create(model=modelo, input=lote)
        dados_recebidos = list(resposta.data)
        indices = [item.index for item in dados_recebidos]
        esperados = list(range(len(lote)))
        if sorted(indices) != esperados:
            raise RuntimeError(
                f"{nome_provedor} devolveu índices de embeddings inválidos: "
                f"esperado={esperados}, recebido={indices}"
            )
        dados = sorted(dados_recebidos, key=lambda item: item.index)
        if len(dados) != len(lote):
            raise RuntimeError(
                f"{nome_provedor} devolveu quantidade inesperada de embeddings: "
                f"esperado={len(lote)}, recebido={len(dados)}"
            )
        vetores.extend(item.embedding for item in dados)
    return _validar_e_normalizar_matriz(
        vetores, len(textos), dimensao, nome_provedor
    )


def _validar_e_normalizar_matriz(
    vetores, n_textos: int, dimensao: int, nome_provedor: str
) -> "np.ndarray":
    import numpy as np

    try:
        matriz = np.asarray(vetores, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Embedding {nome_provedor} não forma uma matriz numérica regular."
        ) from exc
    esperado = (n_textos, dimensao)
    if matriz.shape != esperado:
        raise RuntimeError(
            f"Dimensão inesperada no embedding {nome_provedor}: "
            f"esperado={esperado}, recebido={matriz.shape}"
        )
    if not np.isfinite(matriz).all():
        raise RuntimeError(
            f"Embedding {nome_provedor} contém valor não finito."
        )
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    if np.any(normas == 0):
        raise RuntimeError(
            f"Embedding {nome_provedor} devolveu vetor de norma zero."
        )
    return (matriz / normas).astype(np.float32, copy=False)


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


def _fingerprint_derivacao_ocr(config: Config) -> str:
    """Fingerprint canônico de tudo que pode alterar os chunks vindos do OCR.

    Segredos, política de retry, timeout e custos ficam deliberadamente fora:
    mudá-los afeta a operação da chamada explícita, não o texto já congelado.
    `pdfplumber` e `pypdf` continuam dentro mesmo no modo OCR porque o fallback
    do teste-sentinela (5.4) pode materializar páginas de biblioteca dentro de
    um índice `mistral_ocr` — sobre-invalidar custa uma reconstrução, e
    sub-invalidar custa um índice errado sem sintoma.
    """

    arquivos = {
        "src/ingestao.py": Path(__file__).with_name("ingestao.py"),
        "src/ocr_corpus.py": Path(__file__).with_name("ocr_corpus.py"),
    }
    dependencias: dict[str, str] = {}
    for pacote in ("pdfplumber", "pypdf", "tiktoken"):
        try:
            dependencias[pacote] = importlib.metadata.version(pacote)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError(
                f"Não foi possível resolver a versão instalada de {pacote}."
            ) from exc
    componentes = {
        "versao_identidade": 3,
        "arquivos": {
            nome: _sha256_arquivo(caminho)
            for nome, caminho in sorted(arquivos.items())
        },
        "configuracao_material": {
            "chunk_sobreposicao_tokens": config.chunk_sobreposicao_tokens,
            "chunk_tamanho_tokens": config.chunk_tamanho_tokens,
            "mistral_ocr_confidence_granularity": (
                config.mistral_ocr_confidence_granularity
            ),
            "mistral_ocr_endpoint": config.mistral_ocr_endpoint.strip(),
            "mistral_ocr_include_blocks": config.mistral_ocr_include_blocks,
            "mistral_ocr_limiar_confianca_media": float(
                config.mistral_ocr_limiar_confianca_media
            ),
            "mistral_ocr_modelo": config.mistral_ocr_modelo,
            "mistral_ocr_table_format": config.mistral_ocr_table_format,
        },
        "dependencias": dependencias,
    }
    canonico = json.dumps(
        componentes,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonico).hexdigest()


def calcular_identidade_extracao(
    config: Config,
    dir_ocr: Path = DIR_CACHE_OCR,
) -> IdentidadeExtracaoIndice:
    """Calcula a identidade material sem tocar o cache no modo biblioteca."""

    if not isinstance(config, Config):
        raise TypeError("config deve ser uma instância de Config.")
    modo = config.extrator
    if modo == "pdfplumber":
        return IdentidadeExtracaoIndice(modo="pdfplumber")
    if modo != "mistral_ocr":
        raise ValueError(f"EXTRATOR inválido: {modo!r}.")

    # Import deliberadamente tardio: o caminho por biblioteca não consulta nem
    # sequer precisa carregar o módulo que lê o cache de OCR.
    from src.ocr_corpus import hash_cache_ocr

    return IdentidadeExtracaoIndice(
        modo=modo,
        hash_cache_ocr=hash_cache_ocr(Path(dir_ocr)),
        fingerprint_derivacao_ocr=_fingerprint_derivacao_ocr(config),
    )


def _identidade_dos_metadados(
    metadados: MetadadosIndice,
) -> IdentidadeExtracaoIndice:
    return IdentidadeExtracaoIndice(
        modo=metadados.extrator,
        hash_cache_ocr=metadados.hash_cache_ocr,
        fingerprint_derivacao_ocr=metadados.fingerprint_derivacao_ocr,
    )


def _validar_estrutura_identidade_extracao(
    identidade: IdentidadeExtracaoIndice,
    *,
    erro: type[Exception] = ErroConsistenciaIndice,
) -> None:
    if not isinstance(identidade, IdentidadeExtracaoIndice):
        raise erro("Identidade de extração ausente ou inválida; reconstrua o índice.")
    if identidade.modo == "pdfplumber":
        if identidade.hash_cache_ocr or identidade.fingerprint_derivacao_ocr:
            raise erro(
                "Identidade de extração por biblioteca contém hashes OCR; "
                "reconstrua o índice."
            )
        return
    if identidade.modo != "mistral_ocr":
        raise erro(
            f"Modo de extração do índice inválido: {identidade.modo!r}; "
            "reconstrua o índice."
        )
    for campo, valor in (
        ("hash_cache_ocr", identidade.hash_cache_ocr),
        ("fingerprint_derivacao_ocr", identidade.fingerprint_derivacao_ocr),
    ):
        if type(valor) is not str or re.fullmatch(r"[0-9a-f]{64}", valor) is None:
            raise erro(f"{campo} ausente ou inválido; reconstrua o índice.")


def validar_compatibilidade_extracao(
    metadados: MetadadosIndice,
    config: Config,
    dir_ocr: Path = DIR_CACHE_OCR,
) -> None:
    """Falha antes de embeddings/Chroma/BM25 se extração e índice divergirem."""

    if not isinstance(config, Config):
        raise TypeError("config deve ser uma instância de Config.")
    modo_indice = metadados.extrator
    modo_config = config.extrator
    if type(modo_indice) is not str or modo_indice not in {
        "mistral_ocr",
        "pdfplumber",
    }:
        raise ErroConsistenciaIndice(
            f"Modo de extração do índice inválido: {modo_indice!r}."
        )
    if type(modo_config) is not str or modo_config not in {
        "mistral_ocr",
        "pdfplumber",
    }:
        raise ErroConsistenciaIndice(
            f"Modo de extração configurado inválido: {modo_config!r}."
        )
    # O modo é comparado antes de qualquer leitura do cache. Isso também
    # garante que consultar um índice OCR no perfil de biblioteca não toque
    # artefatos que o operador não habilitou.
    if modo_indice != modo_config:
        raise ErroConsistenciaIndice(
            "Modo de extração incompatível com o índice (RNF09): "
            f"índice={modo_indice!r}, consulta={modo_config!r}. Reconstrua-o."
        )

    registrada = _identidade_dos_metadados(metadados)
    _validar_estrutura_identidade_extracao(registrada)
    if modo_config == "pdfplumber":
        return
    atual = calcular_identidade_extracao(config, dir_ocr)
    if registrada != atual:
        divergencias = [
            campo
            for campo in ("hash_cache_ocr", "fingerprint_derivacao_ocr")
            if getattr(registrada, campo) != getattr(atual, campo)
        ]
        raise ErroConsistenciaIndice(
            "Cache/código OCR atual diverge do usado na construção do índice "
            f"(RNF09): {', '.join(divergencias)}. Reconstrua-o."
        )


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


# --- Armazenamento vetorial: coleção Chroma persistida --------------------


def _campos_identidade_colecao() -> tuple[str, ...]:
    """Campos do descritor replicados nos metadados da coleção.

    Ficam de fora apenas os digests, que são *sobre* os artefatos e por isso
    não podem morar dentro do artefato que descrevem.
    """
    return tuple(
        campo.name
        for campo in fields(MetadadosIndice)
        if campo.name not in {"hash_chunks", "hash_indice_vetorial"}
    )


def _metadados_para_colecao(metadados: MetadadosIndice) -> dict:
    """Identidade RNF09 gravada nos metadados da própria coleção (5.6)."""
    return {campo: getattr(metadados, campo) for campo in _campos_identidade_colecao()}


def _ef_busca(n_chunks: int) -> int:
    """`ef_search` que torna o HNSW exaustivo para uma coleção deste tamanho."""
    return max(EF_BUSCA_MINIMA, min(int(n_chunks), EF_BUSCA_MAXIMA))


def recusar_indice_faiss_legado(
    dir_indice: Path, metadados_brutos: dict | None = None
) -> None:
    """Falha explícita ao encontrar o armazenamento FAISS antigo.

    Um diretório com `indice.faiss` (ou com o campo `hash_indice_faiss` no
    descritor) foi construído antes da migração. Abrir um `PersistentClient`
    ali criaria um `chroma.sqlite3` VAZIO e a coleção simplesmente não
    existiria — ou, pior, uma coleção parcial responderia consultas. Este é o
    modo de falha silenciosa que a RNF09 existe para matar, então o legado é
    recusado antes de qualquer escrita.
    """
    legado = Path(dir_indice) / ARQUIVO_INDICE_FAISS_LEGADO
    tem_campo_legado = (
        isinstance(metadados_brutos, dict)
        and CAMPO_METADADOS_FAISS_LEGADO in metadados_brutos
    )
    if legado.exists() or tem_campo_legado:
        raise ErroConsistenciaIndice(
            f"O índice em {dir_indice} é do armazenamento FAISS anterior "
            f"({ARQUIVO_INDICE_FAISS_LEGADO}/{CAMPO_METADADOS_FAISS_LEGADO}) e "
            "não pode ser consultado pela coleção Chroma: os vetores não são "
            "migráveis sem reembedar o corpus. Apague o diretório e reconstrua "
            "o índice (executar_pipeline.py, etapa de indexação)."
        )


def _abrir_cliente_chroma(dir_indice: Path):
    """Cliente persistente sem telemetria e sem cache de sistema obsoleto.

    O Chroma memoriza a instância de sistema por diretório. Depois de uma
    reconstrução que promove um diretório novo sobre o mesmo caminho, um
    cliente reaproveitado da memória continua servindo a coleção ANTIGA sem
    erro nenhum — verificado em laboratório. Limpar a memória antes de abrir é
    obrigatório, e objetos `Collection` já obtidos seguem funcionando.
    """
    import chromadb
    from chromadb.api.shared_system_client import SharedSystemClient
    from chromadb.config import Settings

    SharedSystemClient.clear_system_cache()
    return chromadb.PersistentClient(
        path=str(dir_indice),
        settings=Settings(anonymized_telemetry=False, allow_reset=False),
    )


def _abrir_colecao_chroma(dir_indice: Path):
    """Abre a coleção persistida, com erro explícito se ela não existir."""
    from chromadb.errors import ChromaError

    dir_indice = Path(dir_indice)
    recusar_indice_faiss_legado(dir_indice)
    if not (dir_indice / ARQUIVO_SQLITE_CHROMA).is_file():
        raise FileNotFoundError(
            f"{dir_indice / ARQUIVO_SQLITE_CHROMA} não existe — construa o "
            "índice primeiro (executar_pipeline.py, etapa de indexação)."
        )
    cliente = _abrir_cliente_chroma(dir_indice)
    try:
        return cliente.get_collection(COLECAO_CHROMA)
    except ChromaError as exc:
        raise ErroConsistenciaIndice(
            f"Coleção {COLECAO_CHROMA!r} ausente em {dir_indice} "
            f"({type(exc).__name__}); reconstrua o índice."
        ) from exc


def _digest_colecao(colecao) -> tuple[str, int, list[str]]:
    """Digest determinístico do conteúdo da coleção (ordem canônica por id).

    Devolve `(digest, dimensao_observada, ids_na_ordem_lida)`. Os vetores
    entram como float32 little-endian explícito para o digest não depender da
    arquitetura da máquina.
    """
    import numpy as np

    dados = colecao.get(include=["embeddings", "metadatas", "documents"])
    ids = list(dados["ids"] or [])
    documentos = list(dados["documents"] or [])
    metadados = list(dados["metadatas"] or [])
    if len(documentos) != len(ids) or len(metadados) != len(ids):
        raise ErroConsistenciaIndice(
            "Coleção Chroma devolveu documentos/metadados em quantidade "
            "diferente dos ids; reconstrua o índice."
        )
    if not ids:
        raise ErroConsistenciaIndice(
            "Coleção Chroma está vazia; reconstrua o índice."
        )
    matriz = np.asarray(dados["embeddings"], dtype=np.float32)
    if matriz.ndim != 2 or matriz.shape[0] != len(ids):
        raise ErroConsistenciaIndice(
            f"Vetores da coleção com formato inesperado: {matriz.shape} para "
            f"{len(ids)} registros. Reconstrua o índice."
        )
    if not np.isfinite(matriz).all():
        raise ErroConsistenciaIndice(
            "Coleção Chroma contém vetor com valor não finito; reconstrua-o."
        )
    digest = hashlib.sha256()
    for posicao in sorted(range(len(ids)), key=lambda i: ids[i]):
        registro = {
            "id": ids[posicao],
            "documento": documentos[posicao],
            "metadados": metadados[posicao] or {},
        }
        digest.update(
            json.dumps(
                registro,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )
        digest.update(b"\x00")
        digest.update(matriz[posicao].astype("<f4", copy=False).tobytes())
    return digest.hexdigest(), int(matriz.shape[1]), ids


def _validar_configuracao_hnsw(colecao, metadados: MetadadosIndice) -> None:
    """Espaço de distância e exaustividade da busca são parte do contrato."""
    configuracao = (colecao.configuration_json or {}).get("hnsw") or {}
    espaco = configuracao.get("space")
    if espaco != ESPACO_DISTANCIA_CHROMA:
        raise ErroConsistenciaIndice(
            f"Coleção Chroma usa espaço de distância {espaco!r}, mas o score "
            f"de similaridade assume {ESPACO_DISTANCIA_CHROMA!r} (RNF09). "
            "Reconstrua o índice."
        )
    ef_search = configuracao.get("ef_search")
    esperado = _ef_busca(metadados.n_chunks)
    if not isinstance(ef_search, int) or ef_search < esperado:
        raise ErroConsistenciaIndice(
            f"Coleção Chroma com ef_search={ef_search!r}, abaixo do mínimo "
            f"{esperado} que mantém a busca exaustiva para {metadados.n_chunks} "
            "vetores (RNF09). Reconstrua o índice."
        )


def _validar_identidade_da_colecao(colecao, metadados: MetadadosIndice) -> None:
    """Cruza os metadados da coleção com o descritor JSON publicado.

    Os dois são gravados na mesma transação; divergir significa que um dos
    lados foi editado à mão depois da construção.
    """
    gravados = colecao.metadata or {}
    divergencias = [
        f"{campo}: coleção={gravados.get(campo)!r} vs descritor={esperado!r}"
        for campo, esperado in _metadados_para_colecao(metadados).items()
        if gravados.get(campo) != esperado
    ]
    if divergencias:
        raise ErroConsistenciaIndice(
            "Metadados da coleção Chroma divergem do descritor publicado "
            "(RNF09); reconstrua o índice. Divergências: "
            + "; ".join(divergencias)
        )


def salvar_metadados_indice(
    metadados: MetadadosIndice, dir_indice: Path = DIR_INDICE_VETORIAL
) -> Path:
    dir_indice = Path(dir_indice)
    dir_indice.mkdir(parents=True, exist_ok=True)
    caminho = dir_indice / ARQUIVO_METADADOS_INDICE
    _escrever_bytes_atomico(
        caminho,
        json.dumps(asdict(metadados), ensure_ascii=False, indent=2).encode("utf-8"),
    )
    return caminho


def carregar_metadados_indice(
    dir_indice: Path = DIR_INDICE_VETORIAL,
) -> MetadadosIndice:
    caminho = Path(dir_indice) / ARQUIVO_METADADOS_INDICE
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} não existe — construa o índice primeiro "
            "(executar_pipeline.py, etapa de indexação)."
        )
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ErroConsistenciaIndice(
            f"Metadados do índice inválidos em {caminho}: {exc}"
        ) from exc
    # Antes de tentar materializar o descritor: um índice FAISS antigo tem de
    # dizer "reconstrua", não "campo inesperado".
    recusar_indice_faiss_legado(Path(dir_indice), bruto)
    try:
        return MetadadosIndice(**bruto)
    except TypeError as exc:
        raise ErroConsistenciaIndice(
            f"Metadados do índice inválidos em {caminho}: {exc}"
        ) from exc


def construir_indice_chroma(
    chunks: list[Chunk],
    provedor: ProvedorEmbeddings,
    hash_corpus: str,
    dir_saida: Path = DIR_INDICE_VETORIAL,
    *,
    identidade_extracao: IdentidadeExtracaoIndice,
) -> MetadadosIndice:
    """Bloqueia o namespace antes de calcular e promover o conjunto."""
    dir_saida = Path(dir_saida)
    with bloqueio_exclusivo(
        dir_saida.parent / f".{dir_saida.name}.lock",
        f"o índice {dir_saida}",
    ):
        return _construir_indice_chroma_bloqueado(
            chunks,
            provedor,
            hash_corpus,
            dir_saida,
            identidade_extracao=identidade_extracao,
        )


def _construir_indice_chroma_bloqueado(
    chunks: list[Chunk],
    provedor: ProvedorEmbeddings,
    hash_corpus: str,
    dir_saida: Path = DIR_INDICE_VETORIAL,
    *,
    identidade_extracao: IdentidadeExtracaoIndice,
) -> MetadadosIndice:
    """Constrói e promove atomicamente coleção Chroma + chunks + metadados.

    Todo o conjunto é primeiro escrito e reaberto em um diretório de staging.
    O diretório ativo só é substituído depois de digests, dimensão e contagens
    passarem. Uma falha de embedding/escrita nunca mistura chunks novos com uma
    coleção antiga (RNF09).
    """
    import numpy as np

    from datetime import datetime, timezone

    _validar_chunks_para_indice(chunks)
    _validar_sha256(hash_corpus, "hash_corpus")
    (
        provedores_extracao,
        modelos_extracao,
        hash_artefatos_extracao,
        n_artefatos_extracao,
    ) = _proveniencia_extracao_dos_chunks(chunks)
    _validar_identidade_contra_proveniencia(
        identidade_extracao,
        provedores_extracao,
        hash_artefatos_extracao,
        n_artefatos_extracao,
        erro=ValueError,
    )
    if not provedor.nome or not provedor.modelo or provedor.dimensao <= 0:
        raise ValueError("Provedor de embeddings possui identidade inválida.")
    identidade_modelo = provedor.identidade_modelo()
    if not identidade_modelo:
        raise ValueError("identidade_modelo do provedor não pode ser vazia.")

    matriz = _validar_e_normalizar_matriz(
        provedor.embedar([c.texto for c in chunks]),
        len(chunks),
        provedor.dimensao,
        provedor.nome,
    )
    matriz = np.ascontiguousarray(matriz, dtype=np.float32)

    dir_saida = Path(dir_saida)
    if dir_saida.is_symlink() or (dir_saida.exists() and not dir_saida.is_dir()):
        raise ValueError(f"Diretório de índice inválido: {dir_saida}")
    dir_saida.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{dir_saida.name}.staging-", dir=str(dir_saida.parent)
        )
    )
    try:
        caminho_chunks = _gravar_chunks(chunks, staging)
        metadados_parciais = MetadadosIndice(
            provedor=provedor.nome,
            modelo=identidade_modelo,
            dimensao=provedor.dimensao,
            data_construcao=datetime.now(timezone.utc).isoformat(),
            hash_corpus=hash_corpus.lower(),
            n_chunks=len(chunks),
            hash_chunks=_sha256_arquivo(caminho_chunks),
            provedores_extracao=provedores_extracao,
            modelos_extracao=modelos_extracao,
            hash_artefatos_extracao=hash_artefatos_extracao,
            n_artefatos_extracao=n_artefatos_extracao,
            extrator=identidade_extracao.modo,
            hash_cache_ocr=identidade_extracao.hash_cache_ocr,
            fingerprint_derivacao_ocr=(
                identidade_extracao.fingerprint_derivacao_ocr
            ),
        )
        digest = _gravar_colecao_chroma(chunks, matriz, staging, metadados_parciais)
        metadados = replace(metadados_parciais, hash_indice_vetorial=digest)
        salvar_metadados_indice(metadados, staging)
        _carregar_conjunto_persistido(staging, metadados)
        _promover_diretorio(staging, dir_saida)
        return metadados
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _gravar_colecao_chroma(
    chunks: list[Chunk],
    matriz,
    dir_saida: Path,
    metadados: MetadadosIndice,
) -> str:
    """Cria a coleção com documento, metadados e vetor juntos (spec 5.6).

    Devolve o digest do conteúdo gravado, já relido do disco: o valor
    publicado no descritor nunca vem da memória do processo que escreveu.
    """
    cliente = _abrir_cliente_chroma(dir_saida)
    colecao = cliente.create_collection(
        name=COLECAO_CHROMA,
        configuration={
            "hnsw": {
                "space": ESPACO_DISTANCIA_CHROMA,
                "ef_search": _ef_busca(len(chunks)),
            }
        },
        metadata=_metadados_para_colecao(metadados),
    )
    # `add` faz upsert silencioso em id repetido; a unicidade já foi validada
    # em `_validar_chunks_para_indice` e a contagem é reconferida abaixo.
    tamanho_lote = 1000
    for inicio in range(0, len(chunks), tamanho_lote):
        lote = chunks[inicio : inicio + tamanho_lote]
        colecao.add(
            ids=[chunk.id for chunk in lote],
            embeddings=matriz[inicio : inicio + len(lote)].tolist(),
            documents=[chunk.texto for chunk in lote],
            metadatas=[
                {campo: getattr(chunk, campo) for campo in CAMPOS_METADADOS_CHROMA}
                for chunk in lote
            ],
        )
    if colecao.count() != len(chunks):
        raise ErroConsistenciaIndice(
            f"Coleção Chroma ficou com {colecao.count()} registros para "
            f"{len(chunks)} chunks; reconstrua o índice."
        )
    digest, _, _ = _digest_colecao(_abrir_colecao_chroma(dir_saida))
    return digest


def salvar_chunks(chunks: list[Chunk], dir_saida: Path = DIR_INDICE_VETORIAL) -> Path:
    """Grava chunks isolados apenas quando ainda não há conjunto ativo.

    Atualizar este arquivo dentro de um índice completo seria corrupção; para
    reconstruções use :func:`construir_indice_chroma`, que promove os três
    artefatos juntos.
    """
    dir_saida = Path(dir_saida)
    if any(
        (dir_saida / nome).exists()
        for nome in (
            ARQUIVO_METADADOS_INDICE,
            ARQUIVO_SQLITE_CHROMA,
            ARQUIVO_INDICE_FAISS_LEGADO,
        )
    ):
        raise ErroConsistenciaIndice(
            "Recusado sobrescrever chunks de um índice existente sem "
            "reconstruir a coleção Chroma completa."
        )
    return _gravar_chunks(chunks, dir_saida)


def carregar_chunks(dir_indice: Path = DIR_INDICE_VETORIAL) -> list[Chunk]:
    caminho = Path(dir_indice) / ARQUIVO_CHUNKS
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} não existe — construa o índice primeiro "
            "(executar_pipeline.py, etapa de indexação)."
        )
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(bruto, list):
            raise TypeError("a raiz de chunks.json deve ser uma lista")
        chunks = [Chunk(**item) for item in bruto]
        _validar_chunks_para_indice(chunks)
        return chunks
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        if isinstance(exc, ErroConsistenciaIndice):
            raise
        raise ErroConsistenciaIndice(
            f"Mapeamento de chunks inválido em {caminho}: {exc}"
        ) from exc


def calcular_hash_corpus_atual_para_indice(
    dir_indice: Path = DIR_INDICE_VETORIAL,
    caminho_metadados_corpus: Path | None = None,
    *,
    integral: bool = False,
    bancos: tuple[str, ...] | None = None,
) -> str:
    """Calcula o hash esperado usando os documentos referidos pelos chunks.

    Funciona tanto para o índice integral quanto para namespaces de amostra: o
    subconjunto é derivado dos próprios chunks persistidos, e as linhas atuais
    vêm do manifesto. O loader ainda valida o checksum de ``chunks.json`` antes
    de devolver o índice; esta função serve apenas para descobrir o subconjunto
    cujo hash deve ser comparado.
    """
    from src.config import CAMINHO_METADADOS_CORPUS
    from src.ingestao import (
        calcular_hash_corpus,
        carregar_metadados_corpus,
        validar_manifesto_canonico,
    )

    chunks = carregar_chunks(dir_indice)
    nomes_usados = {chunk.documento for chunk in chunks}
    documentos = carregar_metadados_corpus(
        caminho_metadados_corpus or CAMINHO_METADADOS_CORPUS
    )
    por_nome = {documento.documento: documento for documento in documentos}
    ausentes = nomes_usados - set(por_nome)
    if ausentes:
        raise ErroConsistenciaIndice(
            "Índice referencia documentos ausentes do manifesto atual: "
            f"{sorted(ausentes)}. Reconstrua o índice."
        )
    if integral:
        bancos_esperados = bancos or Config().bancos
        validar_manifesto_canonico(documentos, bancos_esperados)
        nomes_manifesto = set(por_nome)
        if nomes_usados != nomes_manifesto:
            raise ErroConsistenciaIndice(
                "Índice integral não cobre exatamente o manifesto atual: "
                f"ausentes={sorted(nomes_manifesto - nomes_usados)}, "
                f"extras={sorted(nomes_usados - nomes_manifesto)}. Reconstrua-o."
            )
        return calcular_hash_corpus(documentos)
    return calcular_hash_corpus([por_nome[nome] for nome in nomes_usados])


def construir_indice_bm25(chunks: list[Chunk], dir_saida: Path = DIR_INDICE_VETORIAL):
    """Índice BM25 sobre os mesmos chunks, tokenizados por
    `normalizacao.normalizar_texto_bm25` (estratégia E1).

    O BM25 não grava ``chunks.json``: a persistência pertence à transação da
    coleção Chroma. Isso elimina a janela em que BM25/chunks novos apontavam
    para vetores antigos. ``dir_saida`` é mantido apenas por compatibilidade."""
    from rank_bm25 import BM25Okapi

    from src.normalizacao import normalizar_texto_bm25

    _validar_chunks_para_indice(chunks)
    return BM25Okapi([normalizar_texto_bm25(c.texto) for c in chunks])


def carregar_indice_bm25(
    *,
    config: Config,
    dir_indice: Path = DIR_INDICE_VETORIAL,
    hash_corpus_esperado: str | None = None,
    dir_ocr: Path = DIR_CACHE_OCR,
):
    """Reconstrói o BM25 a partir dos chunks persistidos, na mesma ordem."""
    metadados = carregar_metadados_indice(dir_indice)
    _validar_metadados_artefatos(metadados, hash_corpus_esperado)
    validar_compatibilidade_extracao(metadados, config, dir_ocr)
    chunks = _validar_arquivos_e_carregar_chunks(
        Path(dir_indice), metadados, hash_corpus_esperado
    )

    from rank_bm25 import BM25Okapi

    from src.normalizacao import normalizar_texto_bm25

    return BM25Okapi([normalizar_texto_bm25(c.texto) for c in chunks]), chunks


def carregar_indice_chroma(
    provedor_consulta: ProvedorEmbeddings,
    *,
    config: Config,
    dir_indice: Path = DIR_INDICE_VETORIAL,
    hash_corpus_esperado: str | None = None,
    dir_ocr: Path = DIR_CACHE_OCR,
):
    """Carrega a coleção E valida a consistência (RNF09) antes de devolver.

    Devolve `(colecao_chroma, chunks)` com os chunks na mesma ordem em que
    foram indexados."""
    metadados = carregar_metadados_indice(dir_indice)
    _validar_metadados_artefatos(metadados, hash_corpus_esperado)
    validar_compatibilidade_extracao(metadados, config, dir_ocr)
    validar_consistencia(metadados, provedor_consulta)
    colecao, chunks = _carregar_conjunto_persistido(
        Path(dir_indice), metadados, hash_corpus_esperado
    )
    return colecao, chunks


def _serializar_chunks(chunks: list[Chunk]) -> bytes:
    return json.dumps(
        [asdict(c) for c in chunks],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _proveniencia_extracao_dos_chunks(
    chunks: list[Chunk],
) -> tuple[str, str, str, int]:
    provedores: set[str] = set()
    modelos: set[str] = set()
    hashes: set[str] = set()
    for chunk in chunks:
        provedores.update(chunk.provedores_extracao.split("+"))
        if chunk.modelos_extracao:
            modelos.update(chunk.modelos_extracao.split("+"))
        if chunk.hashes_artefatos_extracao:
            hashes.update(chunk.hashes_artefatos_extracao.split(";"))
    provedores_serializados = "+".join(sorted(provedores))
    modelos_serializados = "+".join(sorted(modelos))
    hashes_ordenados = sorted(hashes)
    hash_agregado = (
        hashlib.sha256(
            json.dumps(
                hashes_ordenados,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if hashes_ordenados
        else ""
    )
    return (
        provedores_serializados,
        modelos_serializados,
        hash_agregado,
        len(hashes_ordenados),
    )


def _validar_identidade_contra_proveniencia(
    identidade: IdentidadeExtracaoIndice,
    provedores_extracao: str,
    hash_artefatos_extracao: str,
    n_artefatos_extracao: int,
    *,
    erro: type[Exception] = ErroConsistenciaIndice,
) -> None:
    """Impede declarar um modo diferente do que os chunks comprovam."""

    _validar_estrutura_identidade_extracao(identidade, erro=erro)
    if identidade.modo == "pdfplumber":
        # "local" é o token de proveniência da família de extratores por
        # biblioteca (pypdf/pdfplumber): a distinção é local × serviço externo,
        # e o parser exato fica em `modelos_extracao`.
        if (
            provedores_extracao != "local"
            or hash_artefatos_extracao
            or n_artefatos_extracao != 0
        ):
            raise erro(
                "Índice declarado sem OCR possui proveniência OCR; "
                "reconstrua o índice com a identidade correta."
            )
        return

    provedores = set(provedores_extracao.split("+"))
    if (
        "mistral" not in provedores
        or n_artefatos_extracao <= 0
        or re.fullmatch(r"[0-9a-f]{64}", hash_artefatos_extracao) is None
    ):
        raise erro(
            "Índice mistral_ocr não contém proveniência OCR material "
            "válida; reconstrua o índice."
        )


def _validar_chunks_para_indice(chunks: list[Chunk]) -> None:
    if not chunks:
        raise ValueError("Não é permitido construir índice com lista de chunks vazia.")
    ids: set[str] = set()
    for posicao, chunk in enumerate(chunks):
        for campo in ("id", "empresa", "trimestre", "documento", "texto"):
            valor = getattr(chunk, campo)
            if not isinstance(valor, str) or not valor.strip():
                raise ValueError(
                    f"Chunk na posição {posicao} possui {campo} vazio ou inválido."
                )
        if chunk.id in ids:
            raise ValueError(f"ID de chunk duplicado: {chunk.id}")
        ids.add(chunk.id)
        if (
            isinstance(chunk.pagina_inicio, bool)
            or isinstance(chunk.pagina_fim, bool)
            or not isinstance(chunk.pagina_inicio, int)
            or not isinstance(chunk.pagina_fim, int)
            or chunk.pagina_inicio <= 0
            or chunk.pagina_fim < chunk.pagina_inicio
        ):
            raise ValueError(f"Intervalo de páginas inválido no chunk {chunk.id}.")
        if (
            isinstance(chunk.posicao_no_documento, bool)
            or not isinstance(chunk.posicao_no_documento, int)
            or chunk.posicao_no_documento <= 0
        ):
            raise ValueError(f"Posição inválida no chunk {chunk.id}.")
        if not isinstance(chunk.provedores_extracao, str) or re.fullmatch(
            r"[a-z0-9_.+-]+", chunk.provedores_extracao
        ) is None:
            raise ValueError(
                f"Provedores de extração inválidos no chunk {chunk.id}."
            )
        if not isinstance(chunk.modelos_extracao, str) or any(
            ord(char) < 32 for char in chunk.modelos_extracao
        ):
            raise ValueError(f"Modelos de extração inválidos no chunk {chunk.id}.")
        if not isinstance(chunk.hashes_artefatos_extracao, str):
            raise ValueError(
                f"Hashes de extração inválidos no chunk {chunk.id}."
            )
        hashes_extracao = (
            chunk.hashes_artefatos_extracao.split(";")
            if chunk.hashes_artefatos_extracao
            else []
        )
        if (
            hashes_extracao != sorted(set(hashes_extracao))
            or any(re.fullmatch(r"[0-9a-f]{64}", h) is None for h in hashes_extracao)
            or (
                "mistral" in chunk.provedores_extracao.split("+")
                and not hashes_extracao
            )
        ):
            raise ValueError(
                f"Hashes de extração inválidos no chunk {chunk.id}."
            )
        tipos_bloco = (
            chunk.tipo_bloco.split("+")
            if isinstance(chunk.tipo_bloco, str) and chunk.tipo_bloco
            else []
        )
        if (
            not tipos_bloco
            or tipos_bloco != sorted(set(tipos_bloco))
            or any(tipo not in TIPOS_BLOCO for tipo in tipos_bloco)
        ):
            raise ValueError(f"Tipo de bloco inválido no chunk {chunk.id}.")
        usa_mistral = "mistral" in chunk.provedores_extracao.split("+")
        scores_ocr = (
            chunk.confianca_media_ocr,
            chunk.confianca_minima_ocr,
        )
        sem_score = scores_ocr == (None, None)
        scores_validos = all(
            not isinstance(score, bool)
            and isinstance(score, (int, float))
            and math.isfinite(score)
            and 0.0 <= float(score) <= 1.0
            for score in scores_ocr
        ) and (
            not all(isinstance(score, (int, float)) for score in scores_ocr)
            or float(scores_ocr[1]) <= float(scores_ocr[0])
        )
        # Mesma regra da ingestão: escore ausente é limitação declarada do
        # artefato de OCR (5.4); escore presente e incoerente é adulteração; e
        # chunk sem OCR jamais pode exibir escore.
        if (usa_mistral and not (sem_score or scores_validos)) or (
            not usa_mistral and not sem_score
        ):
            raise ValueError(
                f"Scores de confiança OCR inválidos no chunk {chunk.id}."
            )


def _gravar_chunks(chunks: list[Chunk], dir_saida: Path) -> Path:
    _validar_chunks_para_indice(chunks)
    dir_saida.mkdir(parents=True, exist_ok=True)
    caminho = dir_saida / ARQUIVO_CHUNKS
    _escrever_bytes_atomico(caminho, _serializar_chunks(chunks))
    return caminho


def _escrever_bytes_atomico(caminho: Path, conteudo: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descritor, nome_temporario = tempfile.mkstemp(
        prefix=f".{caminho.name}.tmp-", dir=str(caminho.parent)
    )
    temporario = Path(nome_temporario)
    try:
        with os.fdopen(descritor, "wb") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        if temporario.exists():
            temporario.unlink()


def _sincronizar_arquivo(caminho: Path) -> None:
    with caminho.open("rb") as arquivo:
        os.fsync(arquivo.fileno())


def _sha256_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _validar_sha256(valor: str, campo: str) -> None:
    if not isinstance(valor, str) or re.fullmatch(r"[0-9a-fA-F]{64}", valor) is None:
        raise ErroConsistenciaIndice(
            f"{campo} ausente ou inválido; esperado SHA-256 hexadecimal. "
            "Reconstrua o índice."
        )


def _validar_metadados_artefatos(
    metadados: MetadadosIndice, hash_corpus_esperado: str | None = None
) -> None:
    if (
        not metadados.provedor
        or not metadados.modelo
        or metadados.dimensao <= 0
        or metadados.n_chunks <= 0
    ):
        raise ErroConsistenciaIndice(
            "Metadados de construção incompletos; reconstrua o índice."
        )
    _validar_sha256(metadados.hash_corpus, "hash_corpus")
    _validar_sha256(metadados.hash_chunks, "hash_chunks")
    _validar_sha256(metadados.hash_indice_vetorial, "hash_indice_vetorial")
    if not isinstance(metadados.provedores_extracao, str) or re.fullmatch(
        r"[a-z0-9_.+-]+", metadados.provedores_extracao
    ) is None:
        raise ErroConsistenciaIndice(
            "provedores_extracao ausente ou inválido; reconstrua o índice."
        )
    if not isinstance(metadados.modelos_extracao, str) or any(
        ord(char) < 32 for char in metadados.modelos_extracao
    ):
        raise ErroConsistenciaIndice(
            "modelos_extracao inválido; reconstrua o índice."
        )
    if (
        isinstance(metadados.n_artefatos_extracao, bool)
        or not isinstance(metadados.n_artefatos_extracao, int)
        or metadados.n_artefatos_extracao < 0
    ):
        raise ErroConsistenciaIndice(
            "n_artefatos_extracao inválido; reconstrua o índice."
        )
    _validar_identidade_contra_proveniencia(
        _identidade_dos_metadados(metadados),
        metadados.provedores_extracao,
        metadados.hash_artefatos_extracao,
        metadados.n_artefatos_extracao,
    )
    if hash_corpus_esperado is not None:
        _validar_sha256(hash_corpus_esperado, "hash_corpus_esperado")
        if metadados.hash_corpus.lower() != hash_corpus_esperado.lower():
            raise ErroConsistenciaIndice(
                "Corpus atual diverge do usado na construção do índice (RNF09). "
                f"índice={metadados.hash_corpus}, atual={hash_corpus_esperado}"
            )


def _validar_checksum(caminho: Path, esperado: str, rotulo: str) -> None:
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} não existe — construa o índice primeiro "
            "(executar_pipeline.py, etapa de indexação)."
        )
    obtido = _sha256_arquivo(caminho)
    if obtido != esperado.lower():
        raise ErroConsistenciaIndice(
            f"Checksum de {rotulo} divergente (RNF09): "
            f"esperado={esperado.lower()}, obtido={obtido}. Reconstrua o índice."
        )


def _validar_arquivos_e_carregar_chunks(
    dir_indice: Path,
    metadados: MetadadosIndice,
    hash_corpus_esperado: str | None = None,
) -> list[Chunk]:
    _validar_metadados_artefatos(metadados, hash_corpus_esperado)
    recusar_indice_faiss_legado(dir_indice)
    caminho_chunks = dir_indice / ARQUIVO_CHUNKS
    _validar_checksum(caminho_chunks, metadados.hash_chunks, "chunks.json")
    chunks = carregar_chunks(dir_indice)
    if len(chunks) != metadados.n_chunks:
        raise ErroConsistenciaIndice(
            f"Foram carregados {len(chunks)} chunks, mas os metadados registram "
            f"n_chunks={metadados.n_chunks} (RNF09)."
        )
    proveniencia_obtida = _proveniencia_extracao_dos_chunks(chunks)
    proveniencia_registrada = (
        metadados.provedores_extracao,
        metadados.modelos_extracao,
        metadados.hash_artefatos_extracao,
        metadados.n_artefatos_extracao,
    )
    if proveniencia_obtida != proveniencia_registrada:
        raise ErroConsistenciaIndice(
            "Proveniência de extração dos chunks diverge dos metadados "
            "publicados (RNF09); reconstrua o índice."
        )
    return chunks


def _carregar_conjunto_persistido(
    dir_indice: Path,
    metadados: MetadadosIndice,
    hash_corpus_esperado: str | None = None,
):
    chunks = _validar_arquivos_e_carregar_chunks(
        dir_indice, metadados, hash_corpus_esperado
    )
    colecao = _abrir_colecao_chroma(dir_indice)
    _validar_identidade_da_colecao(colecao, metadados)
    _validar_configuracao_hnsw(colecao, metadados)
    digest, dimensao, ids = _digest_colecao(colecao)
    if dimensao != metadados.dimensao:
        raise ErroConsistenciaIndice(
            f"Dimensão física dos vetores da coleção é {dimensao}, mas os "
            f"metadados registram {metadados.dimensao} (RNF09)."
        )
    if len(ids) != len(chunks) or len(ids) != metadados.n_chunks:
        raise ErroConsistenciaIndice(
            f"Coleção Chroma com {len(ids)} vetores, {len(chunks)} chunks "
            f"persistidos e n_chunks={metadados.n_chunks} nos metadados (RNF09)."
        )
    if sorted(ids) != sorted(chunk.id for chunk in chunks):
        raise ErroConsistenciaIndice(
            "Ids da coleção Chroma não correspondem aos chunks persistidos "
            "(RNF09); reconstrua o índice."
        )
    if digest != metadados.hash_indice_vetorial.lower():
        raise ErroConsistenciaIndice(
            "Digest do conteúdo da coleção Chroma divergente (RNF09): "
            f"esperado={metadados.hash_indice_vetorial.lower()}, obtido={digest}. "
            "Reconstrua o índice."
        )
    return colecao, chunks


def _promover_diretorio(staging: Path, destino: Path) -> None:
    """Troca o conjunto completo com rollback se a promoção falhar."""
    backup = destino.with_name(f".{destino.name}.backup-{uuid.uuid4().hex}")
    havia_destino = destino.exists()
    try:
        if havia_destino:
            os.replace(destino, backup)
        os.replace(staging, destino)
    except Exception:
        if havia_destino and backup.exists() and not destino.exists():
            os.replace(backup, destino)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
