"""Configuração central do pipeline (seção 5.14 da especificacao.md).

Toda leitura de variável de ambiente acontece aqui — os demais módulos recebem
um objeto `Config` imutável, nunca leem `os.environ` diretamente. Isso mantém
o contrato do `.env.example` num único lugar e torna os defaults testáveis.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

DIR_CORPUS_RAW = RAIZ_PROJETO / "corpus" / "raw"
CAMINHO_METADADOS_CORPUS = RAIZ_PROJETO / "corpus" / "metadados.csv"
DIR_INDICE_VETORIAL = RAIZ_PROJETO / "artefatos" / "indice_vetorial"
DIR_LOGS_EXECUCOES = RAIZ_PROJETO / "artefatos" / "logs_execucoes"
DIR_RESULTADOS_AVALIACAO = RAIZ_PROJETO / "artefatos" / "resultados_avaliacao"


@dataclass(frozen=True)
class Config:
    """Espelho tipado do `.env` — defaults idênticos aos do `.env.example`."""

    # Corpus
    bancos: tuple[str, ...] = ("BTG", "ITAU", "BRADESCO", "SANTANDER", "BB")
    n_trimestres: int = 4

    # Chunking (seção 5.3)
    chunk_tamanho_tokens: int = 600
    chunk_sobreposicao_tokens: int = 100

    # Recuperação (seção 5.6)
    top_k: int = 5
    estrategia_padrao: str = "semantica"

    # Provedores (plugável — RNF06). Desenvolvimento é local-first; Azure só
    # entra no gate de pré-deploy, depois do pipeline local estar validado.
    embedding_provider: str = "ollama"
    llm_provider: str = "ollama"
    temperatura: float = 0.0
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_modelo_llm: str = "qwen2.5:14b"
    ollama_modelo_embedding: str = "bge-m3"
    ollama_embedding_dimensao: int = 1024
    ollama_timeout_s: float = 180.0
    ollama_max_tokens: int = 1024
    ollama_embedding_batch_size: int = 32
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = ""
    azure_openai_deployment_llm: str = ""
    azure_openai_deployment_embedding: str = ""
    openai_api_key: str = ""
    openai_modelo: str = "gpt-4o-mini"
    deepseek_api_key: str = ""
    deepseek_modelo: str = "deepseek-chat"

    # Avaliação (seções 5.8–5.9)
    conjunto_padrao_path: Path = RAIZ_PROJETO / "conjunto_padrao" / "perguntas.csv"
    tolerancia_numerica_pct: float = 1.0
    orcamento_teto_usd: float = 10.0

    # Exposição pública (Fase 3, seção 5.13)
    limite_perguntas_livres_por_sessao: int = 5
    modo_demonstracao_cacheado: bool = True


def _env(nome: str, padrao: str) -> str:
    return os.environ.get(nome, padrao).strip()


def carregar_config(env_file: Path | None = None) -> Config:
    """Carrega o `.env` (se existir) e materializa a `Config`.

    Falta de chave obrigatória NÃO falha aqui: cada provedor valida as suas
    próprias credenciais ao ser instanciado, com mensagem clara (critério de
    "pronto", seção 7).
    """
    load_dotenv(env_file or RAIZ_PROJETO / ".env")
    padrao = Config()
    return Config(
        bancos=tuple(
            b.strip().upper()
            for b in _env("BANCOS", ",".join(padrao.bancos)).split(",")
            if b.strip()
        ),
        n_trimestres=int(_env("N_TRIMESTRES", str(padrao.n_trimestres))),
        chunk_tamanho_tokens=int(
            _env("CHUNK_TAMANHO_TOKENS", str(padrao.chunk_tamanho_tokens))
        ),
        chunk_sobreposicao_tokens=int(
            _env("CHUNK_SOBREPOSICAO_TOKENS", str(padrao.chunk_sobreposicao_tokens))
        ),
        top_k=int(_env("TOP_K", str(padrao.top_k))),
        estrategia_padrao=_env("ESTRATEGIA_PADRAO", padrao.estrategia_padrao),
        embedding_provider=_env("EMBEDDING_PROVIDER", padrao.embedding_provider),
        llm_provider=_env("LLM_PROVIDER", padrao.llm_provider),
        temperatura=float(_env("TEMPERATURA", str(padrao.temperatura))),
        ollama_base_url=_env("OLLAMA_BASE_URL", padrao.ollama_base_url),
        ollama_modelo_llm=_env("OLLAMA_MODELO_LLM", padrao.ollama_modelo_llm),
        ollama_modelo_embedding=_env(
            "OLLAMA_MODELO_EMBEDDING", padrao.ollama_modelo_embedding
        ),
        ollama_embedding_dimensao=int(
            _env(
                "OLLAMA_EMBEDDING_DIMENSAO",
                str(padrao.ollama_embedding_dimensao),
            )
        ),
        ollama_timeout_s=float(
            _env("OLLAMA_TIMEOUT_S", str(padrao.ollama_timeout_s))
        ),
        ollama_max_tokens=int(
            _env("OLLAMA_MAX_TOKENS", str(padrao.ollama_max_tokens))
        ),
        ollama_embedding_batch_size=int(
            _env(
                "OLLAMA_EMBEDDING_BATCH_SIZE",
                str(padrao.ollama_embedding_batch_size),
            )
        ),
        azure_openai_endpoint=_env("AZURE_OPENAI_ENDPOINT", ""),
        azure_openai_api_key=_env("AZURE_OPENAI_API_KEY", ""),
        azure_openai_api_version=_env("AZURE_OPENAI_API_VERSION", ""),
        azure_openai_deployment_llm=_env("AZURE_OPENAI_DEPLOYMENT_LLM", ""),
        azure_openai_deployment_embedding=_env("AZURE_OPENAI_DEPLOYMENT_EMBEDDING", ""),
        openai_api_key=_env("OPENAI_API_KEY", ""),
        openai_modelo=_env("OPENAI_MODELO", padrao.openai_modelo),
        deepseek_api_key=_env("DEEPSEEK_API_KEY", ""),
        deepseek_modelo=_env("DEEPSEEK_MODELO", padrao.deepseek_modelo),
        conjunto_padrao_path=RAIZ_PROJETO
        / _env("CONJUNTO_PADRAO_PATH", "conjunto_padrao/perguntas.csv"),
        tolerancia_numerica_pct=float(
            _env("TOLERANCIA_NUMERICA_PCT", str(padrao.tolerancia_numerica_pct))
        ),
        orcamento_teto_usd=float(
            _env("ORCAMENTO_TETO_USD", str(padrao.orcamento_teto_usd))
        ),
        limite_perguntas_livres_por_sessao=int(
            _env(
                "LIMITE_PERGUNTAS_LIVRES_POR_SESSAO",
                str(padrao.limite_perguntas_livres_por_sessao),
            )
        ),
        modo_demonstracao_cacheado=_env(
            "MODO_DEMONSTRACAO_CACHEADO", "true"
        ).lower()
        in ("1", "true", "sim"),
    )
