"""Geração com citação obrigatória e recusa — seção 5.7 (RF07, RF08, RN01–RN02).

Prompt fixo + arquitetura de provedor plugável (RNF06) + contrato de saída
JSON que torna RN01–RN02 verificáveis por código: recusa é campo booleano e
toda citação deve referenciar um chunk realmente recuperado naquela consulta.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.config import Config
from src.ingestao import Chunk

# Prompt fixo (seção 5.7). Alterações aqui invalidam comparações anteriores —
# a versão do prompt entra no log JSONL de cada execução (RNF08).
PROMPT_SISTEMA = """\
Você é um assistente de research financeiro. Responda à pergunta do usuário \
usando EXCLUSIVAMENTE os trechos de documentos fornecidos abaixo.

Regras invioláveis:
1. NUNCA use conhecimento próprio: se a informação não estiver literalmente \
nos trechos fornecidos, recuse — mesmo que você "saiba" a resposta.
2. Toda afirmação numérica deve citar a fonte: empresa, documento, trimestre \
e página (esses dados estão no cabeçalho entre colchetes de cada trecho).
3. Responda SOMENTE com um objeto JSON válido, sem texto fora dele, no formato:
{
  "resposta": "<texto da resposta, ou null se recusar>",
  "recusa": <true|false>,
  "motivo_recusa": "<por que os trechos não bastam, ou null>",
  "citacoes": [
    {"empresa": "...", "documento": "...", "trimestre": "...", "pagina": <int>}
  ]
}
4. Se recusar: "recusa" = true, "resposta" = null e "citacoes" = [].
5. Não invente números, não extrapole, não arredonde além do que está escrito.
"""

VERSAO_PROMPT = "v1"


@dataclass(frozen=True)
class Citacao:
    empresa: str
    documento: str
    trimestre: str
    pagina: int


@dataclass(frozen=True)
class RespostaGerada:
    """Contrato de saída estruturada (RF07)."""

    resposta: str | None
    recusa: bool
    motivo_recusa: str | None
    citacoes: tuple[Citacao, ...]
    # Rastreabilidade (RNF08 / auditoria):
    bruto: str = ""                 # texto cru devolvido pelo LLM
    json_reparado: bool = False     # True se a 1ª tentativa de parse falhou
    json_invalido: bool = False     # True se nem o reparo salvou (conta erro)


@dataclass(frozen=True)
class UsoLLM:
    """Medição por chamada — alimenta custo/latência no log JSONL (RNF08)."""

    tokens_entrada: int
    tokens_saida: int
    custo_usd: float
    latencia_s: float


@dataclass
class RespostaBrutaLLM:
    texto: str
    uso: UsoLLM
    modelo: str


class ProvedorLLM(ABC):
    """Contrato plugável de inferência (RNF06) — mesmo padrão do projeto do
    corretor de redação: troca de provedor por variável de ambiente."""

    nome: str

    @abstractmethod
    def gerar(
        self, prompt_sistema: str, prompt_usuario: str, temperatura: float = 0.0
    ) -> RespostaBrutaLLM: ...


class LLMAzureOpenAI(ProvedorLLM):
    """Ramo A do gate G1 (seção 5.7)."""

    nome = "azure_openai"

    def __init__(self, config: Config):
        faltando = [
            n
            for n, v in (
                ("AZURE_OPENAI_ENDPOINT", config.azure_openai_endpoint),
                ("AZURE_OPENAI_API_KEY", config.azure_openai_api_key),
                ("AZURE_OPENAI_API_VERSION", config.azure_openai_api_version),
                ("AZURE_OPENAI_DEPLOYMENT_LLM", config.azure_openai_deployment_llm),
            )
            if not v
        ]
        if faltando:
            raise ValueError(f"Variáveis Azure ausentes no .env: {faltando}")
        self._config = config

    def gerar(self, prompt_sistema, prompt_usuario, temperatura=0.0):
        raise NotImplementedError("Etapa 8 do AGENTS.md — adaptador Azure OpenAI")


class LLMOpenAI(ProvedorLLM):
    """Fallback primário se o gate G1 falhar (cenário esperado — 5.7)."""

    nome = "openai"

    def __init__(self, config: Config):
        if not config.openai_api_key:
            raise ValueError("OPENAI_API_KEY ausente — configure o .env.")
        self._config = config

    def gerar(self, prompt_sistema, prompt_usuario, temperatura=0.0):
        raise NotImplementedError("Etapa 8 do AGENTS.md — adaptador OpenAI")


class LLMDeepSeek(ProvedorLLM):
    """Fallback de custo baixo (API compatível com OpenAI)."""

    nome = "deepseek"

    def __init__(self, config: Config):
        if not config.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY ausente — configure o .env.")
        self._config = config

    def gerar(self, prompt_sistema, prompt_usuario, temperatura=0.0):
        raise NotImplementedError("Etapa 8 do AGENTS.md — adaptador DeepSeek")


def fabricar_provedor_llm(config: Config) -> ProvedorLLM:
    """Dispatch por LLM_PROVIDER (RNF06)."""
    fabricas = {
        "azure_openai": LLMAzureOpenAI,
        "openai": LLMOpenAI,
        "deepseek": LLMDeepSeek,
    }
    if config.llm_provider not in fabricas:
        raise ValueError(
            f"LLM_PROVIDER desconhecido: {config.llm_provider!r} "
            f"(aceitos: {sorted(fabricas)})"
        )
    return fabricas[config.llm_provider](config)


def citacoes_sao_subconjunto(
    citacoes: tuple[Citacao, ...] | list[Citacao], chunks_recuperados: list[Chunk]
) -> bool:
    """Checagem mecânica de RN01 (seção 5.7): toda citação deve referenciar um
    chunk realmente recuperado NAQUELA consulta — empresa/documento/trimestre
    idênticos e página dentro do intervalo do chunk. Citação órfã = violação.
    """
    return all(
        any(
            c.empresa == ch.empresa
            and c.documento == ch.documento
            and c.trimestre == ch.trimestre
            and ch.pagina_inicio <= c.pagina <= ch.pagina_fim
            for ch in chunks_recuperados
        )
        for c in citacoes
    )


def montar_prompt_usuario(pergunta: str, chunks: list[Chunk]) -> str:
    """Concatena os trechos recuperados (cada um já traz o cabeçalho
    contextual) + a pergunta. E0 (closed-book) passa chunks=[] e o prompt
    declara a ausência de contexto."""
    raise NotImplementedError("Etapa 8 do AGENTS.md — montagem do prompt")


def parsear_resposta_llm(texto: str) -> RespostaGerada:
    """Parse estrito do contrato JSON com UMA tentativa de reparo
    (seção 5.7, modo de falha nº 7). Persistindo o erro, devolve
    RespostaGerada(json_invalido=True, recusa=True) — conta como erro da
    estratégia naquele item, NUNCA re-tentado até passar."""
    raise NotImplementedError("Etapa 8 do AGENTS.md — parse + reparo de JSON")


def gerar_resposta(
    pergunta: str,
    chunks: list[Chunk],
    provedor: ProvedorLLM,
    config: Config,
) -> tuple[RespostaGerada, UsoLLM]:
    """Ponta a ponta da geração: prompt fixo -> LLM (temperatura da config,
    0 em avaliação) -> parse -> checagem RN01 (`citacoes_sao_subconjunto`;
    citação órfã rebaixa a resposta a inválida)."""
    raise NotImplementedError("Etapa 8 do AGENTS.md — geração ponta a ponta")
