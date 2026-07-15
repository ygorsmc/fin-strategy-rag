"""Geração com citação obrigatória e recusa — seção 5.7 (RF07, RF08, RN01–RN02).

Prompt fixo + arquitetura de provedor plugável (RNF06) + contrato de saída
JSON que torna RN01–RN02 verificáveis por código: recusa é campo booleano e
toda citação deve referenciar um chunk realmente recuperado naquela consulta.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from time import perf_counter

from openai import OpenAI

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


class LLMOllama(ProvedorLLM):
    """Inferência local via endpoint OpenAI-compatible do Ollama."""

    nome = "ollama"

    def __init__(self, config: Config):
        faltando = [
            nome
            for nome, valor in (
                ("OLLAMA_BASE_URL", config.ollama_base_url),
                ("OLLAMA_MODELO_LLM", config.ollama_modelo_llm),
            )
            if not valor
        ]
        if faltando:
            raise ValueError(f"Variáveis Ollama ausentes: {faltando}")
        if config.ollama_timeout_s <= 0:
            raise ValueError("OLLAMA_TIMEOUT_S deve ser positivo.")
        if config.ollama_max_tokens <= 0:
            raise ValueError("OLLAMA_MAX_TOKENS deve ser positivo.")
        self._config = config
        self._cliente = OpenAI(
            base_url=config.ollama_base_url,
            api_key="ollama-local",
            timeout=config.ollama_timeout_s,
            max_retries=0,
        )

    def gerar(
        self, prompt_sistema: str, prompt_usuario: str, temperatura: float = 0.0
    ) -> RespostaBrutaLLM:
        inicio = perf_counter()
        resposta = self._cliente.chat.completions.create(
            model=self._config.ollama_modelo_llm,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
            temperature=temperatura,
            max_tokens=self._config.ollama_max_tokens,
            response_format={"type": "json_object"},
        )
        latencia_s = perf_counter() - inicio
        uso_api = resposta.usage
        uso = UsoLLM(
            tokens_entrada=int(getattr(uso_api, "prompt_tokens", 0) or 0),
            tokens_saida=int(getattr(uso_api, "completion_tokens", 0) or 0),
            custo_usd=0.0,
            latencia_s=latencia_s,
        )
        return RespostaBrutaLLM(
            texto=resposta.choices[0].message.content or "",
            uso=uso,
            modelo=str(resposta.model or self._config.ollama_modelo_llm),
        )


class LLMGemini(ProvedorLLM):
    """Geração via Gemini API usando a compatibilidade OpenAI oficial."""

    nome = "gemini"

    def __init__(self, config: Config):
        faltando = [
            nome
            for nome, valor in (
                ("GEMINI_API_KEY/GOOGLE_API_KEY", config.gemini_api_key),
                ("GEMINI_MODELO_LLM", config.gemini_modelo_llm),
                ("GEMINI_BASE_URL", config.gemini_base_url),
            )
            if not valor
        ]
        if faltando:
            raise ValueError(f"Variáveis Gemini ausentes: {faltando}")
        if config.gemini_timeout_s <= 0:
            raise ValueError("GEMINI_TIMEOUT_S deve ser positivo.")
        if config.gemini_max_tokens <= 0:
            raise ValueError("GEMINI_MAX_TOKENS deve ser positivo.")
        if (
            config.gemini_preco_entrada_usd_milhao < 0
            or config.gemini_preco_saida_usd_milhao < 0
        ):
            raise ValueError("Preços Gemini não podem ser negativos.")
        self._config = config
        self._cliente = OpenAI(
            api_key=config.gemini_api_key,
            base_url=config.gemini_base_url,
            timeout=config.gemini_timeout_s,
            max_retries=0,
        )

    def gerar(
        self, prompt_sistema: str, prompt_usuario: str, temperatura: float = 0.0
    ) -> RespostaBrutaLLM:
        inicio = perf_counter()
        argumentos = {
            "model": self._config.gemini_modelo_llm,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
            "temperature": temperatura,
            "max_tokens": self._config.gemini_max_tokens,
            "response_format": {"type": "json_object"},
        }
        if self._config.gemini_reasoning_effort:
            argumentos["reasoning_effort"] = self._config.gemini_reasoning_effort
        resposta = self._cliente.chat.completions.create(**argumentos)
        latencia_s = perf_counter() - inicio
        uso_api = resposta.usage
        tokens_entrada = int(getattr(uso_api, "prompt_tokens", 0) or 0)
        tokens_saida = int(getattr(uso_api, "completion_tokens", 0) or 0)
        custo_usd = (
            tokens_entrada * self._config.gemini_preco_entrada_usd_milhao
            + tokens_saida * self._config.gemini_preco_saida_usd_milhao
        ) / 1_000_000
        uso = UsoLLM(
            tokens_entrada=tokens_entrada,
            tokens_saida=tokens_saida,
            custo_usd=custo_usd,
            latencia_s=latencia_s,
        )
        return RespostaBrutaLLM(
            texto=resposta.choices[0].message.content or "",
            uso=uso,
            modelo=str(resposta.model or self._config.gemini_modelo_llm),
        )


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
    """Provedor pago opcional; não é usado no ramo local-first."""

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
        "ollama": LLMOllama,
        "gemini": LLMGemini,
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
    if chunks:
        trechos = "\n\n---\n\n".join(chunk.texto for chunk in chunks)
        contexto = f"Trechos recuperados dos documentos:\n\n{trechos}"
    else:
        contexto = (
            "Nenhum trecho de documento foi recuperado para esta consulta "
            "(sem contexto disponível)."
        )
    return f"{contexto}\n\nPergunta: {pergunta}"


def _resposta_invalida(bruto: str, motivo: str, reparado: bool) -> RespostaGerada:
    return RespostaGerada(
        resposta=None,
        recusa=True,  # conservador: lixo conta como erro, nunca como resposta
        motivo_recusa=motivo,
        citacoes=(),
        bruto=bruto,
        json_reparado=reparado,
        json_invalido=True,
    )


def parsear_resposta_llm(texto: str) -> RespostaGerada:
    """Parse estrito do contrato JSON com UMA tentativa de reparo
    (seção 5.7, modo de falha nº 7). Persistindo o erro, devolve
    RespostaGerada(json_invalido=True, recusa=True) — conta como erro da
    estratégia naquele item, NUNCA re-tentado até passar."""
    reparado = False
    try:
        objeto = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        # Reparo único: descarta cercas de markdown/texto fora do objeto.
        reparado = True
        inicio, fim = texto.find("{"), texto.rfind("}")
        if inicio < 0 or fim <= inicio:
            return _resposta_invalida(texto, "LLM não devolveu JSON.", reparado)
        try:
            objeto = json.loads(texto[inicio : fim + 1])
        except json.JSONDecodeError:
            return _resposta_invalida(
                texto, "JSON inválido mesmo após uma tentativa de reparo.", reparado
            )
    if not isinstance(objeto, dict):
        return _resposta_invalida(texto, "JSON não é um objeto.", reparado)
    try:
        citacoes = tuple(
            Citacao(
                empresa=str(c["empresa"]),
                documento=str(c["documento"]),
                trimestre=str(c["trimestre"]),
                pagina=int(c["pagina"]),
            )
            for c in (objeto.get("citacoes") or [])
        )
    except (KeyError, TypeError, ValueError):
        return _resposta_invalida(
            texto, "Citação fora do contrato (empresa/documento/trimestre/pagina).",
            reparado,
        )
    resposta = objeto.get("resposta")
    motivo = objeto.get("motivo_recusa")
    return RespostaGerada(
        resposta=None if resposta is None else str(resposta),
        recusa=bool(objeto.get("recusa", False)),
        motivo_recusa=None if motivo is None else str(motivo),
        citacoes=citacoes,
        bruto=texto,
        json_reparado=reparado,
        json_invalido=False,
    )


def gerar_resposta(
    pergunta: str,
    chunks: list[Chunk],
    provedor: ProvedorLLM,
    config: Config,
) -> tuple[RespostaGerada, UsoLLM]:
    """Ponta a ponta da geração: prompt fixo -> LLM (temperatura da config,
    0 em avaliação) -> parse -> checagem RN01 (`citacoes_sao_subconjunto`;
    citação órfã rebaixa a resposta a inválida)."""
    bruta = provedor.gerar(
        PROMPT_SISTEMA,
        montar_prompt_usuario(pergunta, chunks),
        temperatura=config.temperatura,
    )
    resposta = parsear_resposta_llm(bruta.texto)
    if not resposta.recusa:
        if not resposta.citacoes:
            resposta = RespostaGerada(
                resposta=None,
                recusa=True,
                motivo_recusa="Rebaixada por RN01: afirmação sem citação.",
                citacoes=(),
                bruto=resposta.bruto,
                json_reparado=resposta.json_reparado,
                json_invalido=resposta.json_invalido,
            )
        elif not citacoes_sao_subconjunto(list(resposta.citacoes), chunks):
            resposta = RespostaGerada(
                resposta=None,
                recusa=True,
                motivo_recusa=(
                    "Rebaixada por RN01: citação órfã (não corresponde a "
                    "nenhum chunk recuperado nesta consulta)."
                ),
                citacoes=(),
                bruto=resposta.bruto,
                json_reparado=resposta.json_reparado,
                json_invalido=resposta.json_invalido,
            )
    return resposta, bruta.uso
