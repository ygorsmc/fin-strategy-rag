"""Configuração central do pipeline (seção 5.14 da especificacao.md).

Toda leitura de variável de ambiente acontece aqui — os demais módulos recebem
um objeto `Config` imutável, nunca leem `os.environ` diretamente. Isso mantém
o contrato do `.env.example` num único lugar e torna os defaults testáveis.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

DIR_CORPUS_RAW = RAIZ_PROJETO / "corpus" / "raw"
CAMINHO_METADADOS_CORPUS = RAIZ_PROJETO / "corpus" / "metadados.csv"
DIR_INDICE_VETORIAL = RAIZ_PROJETO / "artefatos" / "indice_vetorial"
DIR_OCR_MISTRAL = RAIZ_PROJETO / "artefatos" / "ocr_mistral"
DIR_LOGS_EXECUCOES = RAIZ_PROJETO / "artefatos" / "logs_execucoes"
DIR_RESULTADOS_AVALIACAO = RAIZ_PROJETO / "artefatos" / "resultados_avaliacao"
DIR_CVM_BRUTO = RAIZ_PROJETO / "corpus" / "cvm"
DIR_MODELO = RAIZ_PROJETO / "artefatos" / "modelo"

# Tabelas que a ferramenta ``consultar_cvm`` pode citar (lista branca da RN04).
# ``fatos_contabeis`` fica DELIBERADAMENTE fora: o agente consulta a visão
# semântica, nunca a tabela crua, porque ``cd_conta`` não identifica o conceito
# contábil entre companhias (RN09).
# `correcoes_contabeis` entra na lista porque a correção precisa ser AUDITÁVEL
# por quem consulta: a visão já marca a célula como corrigida, e quem quiser
# ver a procedência (documento, página, evidência) tem de conseguir lê-la.
# Esconder a tabela deixaria a marca `corrigido=true` sem como ser verificada.
TABELAS_PERMITIDAS_SQL: frozenset[str] = frozenset(
    {
        "companhias",
        "correcoes_contabeis",
        "fatos_semanticos",
        "indicadores",
        "mapa_contas",
    }
)

GUARDRAILS_CONHECIDOS: frozenset[str] = frozenset(
    {"injection", "topico_proibido", "pii"}
)


@dataclass(frozen=True)
class Config:
    """Espelho tipado do `.env` — defaults idênticos aos do `.env.example`."""

    # Corpus
    bancos: tuple[str, ...] = ("BTG", "ITAU", "BRADESCO", "SANTANDER", "BB")
    n_trimestres: int = 4

    # Chunking (seção 5.3)
    chunk_tamanho_tokens: int = 600
    chunk_sobreposicao_tokens: int = 100

    # Extração de PDF (spec 5.3/5.20). ``mistral_ocr`` é o extrator primário e
    # NUNCA chama a API durante a ingestão: ele lê o cache versionado em
    # `corpus/ocr/` (RNF10). ``pdfplumber`` é o extrator por biblioteca, mantido
    # atrás da mesma interface como alternativa — inclusive como fallback do
    # teste-sentinela (5.4) —, não como código morto.
    # O default é o primário porque o cache de OCR é versionado e o
    # `corpus/raw/` não é: num clone limpo, só `mistral_ocr` roda.
    extrator: str = "mistral_ocr"
    mistral_ocr_api_key: str = field(default="", repr=False)
    mistral_ocr_endpoint: str = "https://api.mistral.ai/v1/ocr"
    mistral_ocr_modelo: str = "mistral-ocr-4-0"
    mistral_ocr_timeout_s: float = 180.0
    # Sem idempotency key documentada, repetir timeout/5xx pode cobrar duas
    # vezes. O default conservador é zero; qualquer retry futuro deve provar
    # que a requisição anterior não foi processada.
    mistral_ocr_max_retries: int = 0
    mistral_ocr_table_format: str = "html"
    mistral_ocr_include_blocks: bool = True
    mistral_ocr_confidence_granularity: str = "page"
    # Gate automático aplicado individualmente a cada página congelada.
    # O mínimo por palavra é auditado, mas não bloqueia por padrão porque uma
    # única palavra difícil não deve invalidar uma página de alta confiança.
    mistral_ocr_limiar_confianca_media: float = 0.95
    mistral_ocr_preco_usd_mil_paginas: float = 4.0
    mistral_ocr_orcamento_teto_usd: float = 1.0

    # Dados estruturados — painel contábil da CVM (seção 5.5)
    duckdb_path: Path = RAIZ_PROJETO / "artefatos" / "cvm.duckdb"
    # Painel casado com a janela do corpus (2T2025–1T2026), não com o histórico
    # completo do portal. Motivo: o sistema não promete cobertura que a
    # avaliação não mede — um painel que respondesse 2020 tornaria meia-errada
    # a recusa congelada de `TSTA006`, que é exatamente o erro que o par de
    # contraste Nubank × Inter existe para expor. Consequência assumida: o
    # modelo preditivo (5.10) perde volume amostral, e isso é limitação
    # declarada, não descoberta depois.
    cvm_ano_inicial: int = 2025
    # O resultado é reinjetado no contexto do agente; 200 estourava o pior caso.
    sql_limite_linhas: int = 50
    sql_timeout_s: float = 10.0

    # Recuperação (seções 5.6–5.7)
    top_k: int = 5
    estrategia_padrao: str = "semantica"
    chroma_path: Path = RAIZ_PROJETO / "artefatos" / "indice_vetorial"

    # Provedores (plugável — RNF06). Gemini é o perfil ativo no .env; Ollama
    # permanece como fallback e Azure só entra no gate de pré-deploy.
    embedding_provider: str = "ollama"
    llm_provider: str = "ollama"
    temperatura: float = 0.0
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_modelo_llm: str = "qwen2.5:14b"
    ollama_modelo_embedding: str = "bge-m3"
    ollama_embedding_dimensao: int = 1024
    ollama_timeout_s: float = 180.0
    ollama_max_tokens: int = 512
    ollama_embedding_batch_size: int = 4
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_api_key: str = field(default="", repr=False)
    # gemini-3.5-flash-lite venceu o comparativo contra 3.1-flash-lite e
    # DeepSeek V4 Flash com o prompt a3 (2026-08-15): acerto 0,933 x 0,400 x
    # 0,600, com menor latência — n pequeno (2-3 reps), confirmação agendada.
    gemini_modelo_llm: str = "gemini-3.5-flash-lite"
    gemini_timeout_s: float = 120.0
    gemini_max_tokens: int = 512
    gemini_reasoning_effort: str = "low"
    # Preço do gemini-3.5-flash-lite (ver comentário em gemini_modelo_llm).
    gemini_preco_entrada_usd_milhao: float = 0.30
    gemini_preco_saida_usd_milhao: float = 2.50
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = field(default="", repr=False)
    azure_openai_api_version: str = ""
    azure_openai_deployment_llm: str = ""
    azure_openai_deployment_embedding: str = ""
    openai_api_key: str = field(default="", repr=False)
    openai_modelo: str = "gpt-4o-mini"
    deepseek_api_key: str = field(default="", repr=False)
    deepseek_modelo: str = "deepseek-chat"
    # DeepSeek cobra entrada em DUAS faixas, e a API informa o split em
    # `prompt_cache_hit_tokens`/`prompt_cache_miss_tokens` — por isso cada
    # faixa tem preço próprio aqui, em vez de tudo no pior caso. O cache é
    # automático (sem parâmetro) e casa por PREFIXO: medido em 2026-08-14,
    # 2.048 de 2.103 tokens vieram de cache na segunda chamada com o mesmo
    # começo de prompt. Sem a telemetria, o adaptador cai no preço de miss
    # (conservador).
    #
    # A DeepSeek anunciou tabela nova, com faturamento peak/off-peak, vigente
    # a partir de 2026-08-16 16:00 UTC (peak: 01h–04h e 06h–10h UTC; fora
    # disso é off-peak, à metade do preço peak). Nenhum dos dois períodos
    # novos é mais barato que o preço único atual — off-peak já é ~57% mais
    # caro na entrada de cache-miss e ~136% mais caro na saída; peak dobra
    # isso. Os defaults abaixo usam PEAK: são os únicos três números fixos que
    # não subestimam o teto em NENHUM horário, e o contrato de `Config` é de
    # preço único, sem relógio — inventar uma troca automática por horário UTC
    # dentro do adaptador tornaria o custo por chamada não reproduzível a
    # partir só da configuração, o que fura a auditabilidade da RNF03. Quem
    # quiser orçar peak/off-peak separadamente sobrescreve via `.env` por
    # execução.
    deepseek_preco_entrada_usd_milhao: float = 0.44
    deepseek_preco_entrada_cache_hit_usd_milhao: float = 0.014
    deepseek_preco_saida_usd_milhao: float = 1.32
    # deepseek-v4-flash é modelo de raciocínio: gasta completion_tokens em
    # `reasoning_content` interno ANTES do `content` visível, e os dois saem
    # do mesmo teto. 512 (o valor que serve ao Gemini) esgota pensando e
    # devolve conteúdo vazio — medido em 2026-08-13 (847 completion_tokens
    # numa chamada isolada; no laço ReAct de múltiplos turnos, mesmo 4000
    # não bastou em várias perguntas). O preço por token é baixo o bastante
    # para um teto folgado não pesar no orçamento.
    deepseek_max_tokens: int = 20_000
    # "high" e "max" existem (a DeepSeek recomenda "max" para agente com
    # ferramentas); sem o parâmetro, o modelo roda em algum modo padrão não
    # documentado — omitido não é "baixo", é desconhecido.
    deepseek_reasoning_effort: str = "max"

    # Agentes (seção 5.9) — teto de passos: estourou, a resposta sai marcada
    # como parcial; nunca um laço aberto pagando token.
    agentes_max_iteracoes: int = 6
    agentes_max_chamadas_ferramenta: int = 8

    # Segurança (seção 5.11)
    guardrails_ativos: tuple[str, ...] = ("injection", "topico_proibido", "pii")
    guardrails_usar_onnx: bool = True
    guardrails_limiar_injection: float = 0.85
    # Desligado por padrão: exige requirements-guardrails.txt E os pesos
    # baixados no build com HF_TOKEN (RNF12 — runtime carrega com
    # local_files_only, confirmado que não precisa de token depois de
    # baixado). Ligar sem os pesos no cache falha fechado no primeiro uso
    # (RNF03) — ver `src.prompt_guard`.
    prompt_guard_habilitado: bool = False
    prompt_guard_modelo: str = "meta-llama/Llama-Prompt-Guard-2-86M"
    # SHA pinado em 2026-08-21 (RNF01: pinar ao que foi medido). Vazio =
    # build não reprodutível. Os pesos do Prompt Guard 2 são embutidos na
    # imagem no build; HF_TOKEN é segredo de BUILD, nunca de runtime (RNF12).
    guardrails_modelo_injecao_revision: str = (
        "a8ded8e697ce7c355e395a0df51f94adb4a2fd27"
    )
    presidio_idioma: str = "pt"
    presidio_modelo_spacy: str = "pt_core_news_md"
    # Desligado por padrão: exige requirements-guardrails.txt instalado
    # (presidio-analyzer + modelo spaCy, ~40 MB) — o modo demonstração sobe
    # sem ele (RNF12). Ligar sem o pacote instalado falha fechado no primeiro
    # uso, não silenciosamente (RNF03) — ver `src.reconhecedor_presidio`.
    presidio_habilitado: bool = False

    # Observabilidade (seção 5.12)
    langfuse_public_key: str = field(default="", repr=False)
    langfuse_secret_key: str = field(default="", repr=False)
    langfuse_host: str = "https://cloud.langfuse.com"

    # Avaliação (seções 5.13–5.15)
    conjunto_padrao_path: Path = RAIZ_PROJETO / "conjunto_padrao" / "perguntas.csv"
    tolerancia_numerica_pct: float = 1.0
    # Vazio faz o DeepEval cair no gpt-4.1 com chave própria, furando RNF06 e
    # RNF03 sem erro visível. A exigência é cobrada no ponto de uso por
    # `exigir_modelo_juiz_deepeval` — não no carregamento, para não quebrar a
    # RNF12 (o modo demonstração abre sem nenhum segredo configurado).
    deepeval_modelo_juiz: str = ""
    orcamento_teto_usd: float = 25.0

    # Exposição pública (Fase 3, seção 5.13)
    limite_perguntas_livres_por_sessao: int = 5
    limite_caracteres_pergunta: int = 2_000
    habilitar_perguntas_livres: bool = False
    modo_demonstracao_cacheado: bool = True


def _env(nome: str, padrao: str) -> str:
    return os.environ.get(nome, padrao).strip()


def _env_bool(nome: str, padrao: bool) -> bool:
    bruto = _env(nome, "true" if padrao else "false").lower()
    verdadeiros = {"1", "true", "sim", "yes", "on"}
    falsos = {"0", "false", "nao", "não", "no", "off"}
    if bruto in verdadeiros:
        return True
    if bruto in falsos:
        return False
    raise ValueError(
        f"{nome} deve ser booleano "
        f"({sorted(verdadeiros | falsos)}); recebido={bruto!r}"
    )


def endpoint_azure_openai_e_oficial(endpoint: str) -> bool:
    """Aceita somente endpoints HTTPS oficiais, sem credenciais na URL.

    A validação é independente do provedor ativo: o gate pode selecionar
    Azure depois de carregar um perfil Ollama/Gemini e nunca deve encaminhar
    uma chave para um host arbitrário.
    """
    if not isinstance(endpoint, str) or not endpoint.strip():
        return False
    try:
        partes = urlsplit(endpoint.strip())
        porta = partes.port
    except ValueError:
        return False
    hostname = (partes.hostname or "").lower()
    return (
        partes.scheme == "https"
        and hostname.endswith(".openai.azure.com")
        and hostname != ".openai.azure.com"
        and not partes.username
        and not partes.password
        and porta in (None, 443)
    )


def endpoint_gemini_e_oficial(endpoint: str) -> bool:
    """Aceita somente a compatibilidade OpenAI oficial do Gemini."""
    if not isinstance(endpoint, str) or not endpoint.strip():
        return False
    try:
        partes = urlsplit(endpoint.strip())
        porta = partes.port
    except ValueError:
        return False
    return (
        partes.scheme == "https"
        and (partes.hostname or "").lower()
        == "generativelanguage.googleapis.com"
        and not partes.username
        and not partes.password
        and porta in (None, 443)
    )


def endpoint_mistral_ocr_e_oficial(endpoint: str) -> bool:
    """Aceita somente o endpoint OCR HTTPS oficial, sem credenciais na URL."""
    if not isinstance(endpoint, str) or not endpoint.strip():
        return False
    try:
        partes = urlsplit(endpoint.strip())
        porta = partes.port
    except ValueError:
        return False
    return (
        partes.scheme == "https"
        and (partes.hostname or "").lower() == "api.mistral.ai"
        and partes.path.rstrip("/") == "/v1/ocr"
        and not partes.query
        and not partes.fragment
        and not partes.username
        and not partes.password
        and porta in (None, 443)
    )


def endpoint_langfuse_e_https(endpoint: str) -> bool:
    """Aceita somente HTTPS sem credenciais na URL.

    O host não é fixado: o Langfuse é MIT e auto-hospedável (5.12), então
    prender o hostname impediria o uso legítimo de uma instância própria. O que
    não se aceita é trafegar segredo de trace em texto claro.
    """
    if not isinstance(endpoint, str) or not endpoint.strip():
        return False
    try:
        partes = urlsplit(endpoint.strip())
        porta = partes.port
    except ValueError:
        return False
    return (
        partes.scheme == "https"
        and bool(partes.hostname)
        and not partes.username
        and not partes.password
        and (porta is None or 0 < porta < 65536)
    )


def exigir_modelo_juiz_deepeval(config: Config) -> str:
    """Devolve o modelo-juiz ou falha — nunca deixa o DeepEval escolher sozinho.

    Com `DEEPEVAL_MODELO_JUIZ` vazio a biblioteca cai num default próprio, com
    chave própria: furaria a arquitetura plugável (RNF06) e o teto de custo
    (RNF03) sem nenhum erro visível. A exigência mora aqui, e não em
    `_validar_config`, porque o modo demonstração deve abrir sem segredo algum
    (RNF12) — só quem for de fato rodar a suíte precisa do juiz nomeado.
    """
    if not config.deepeval_modelo_juiz.strip():
        raise ValueError(
            "DEEPEVAL_MODELO_JUIZ é obrigatório para rodar a suíte automatizada "
            "(5.15): sem modelo nomeado o DeepEval usa um default próprio, "
            "furando RNF06 (provedor plugável) e RNF03 (teto de custo) sem erro "
            "visível. O modelo usado como juiz é registrado no relatório."
        )
    return config.deepeval_modelo_juiz.strip()


# Variáveis retiradas do contrato. Aceitá-las como alias seria pior que
# recusá-las: `EXTRACAO_PDF_MODO=local` mapearia para `pdfplumber`, mas
# `mistral_overlay` não tem sucessor — o modo de sobreposição página a página
# deixou de existir quando o cache passou a ser o extrator inteiro (5.3). Um
# alias parcial escolheria silenciosamente um extrator diferente do pedido e
# produziria um índice com proveniência que ninguém autorizou. Falha explícita.
VARIAVEIS_APOSENTADAS: dict[str, str] = {
    "EXTRACAO_PDF_MODO": (
        "substituída por EXTRATOR=mistral_ocr|pdfplumber (spec 5.20). "
        "`local` corresponde a `pdfplumber`; `mistral_overlay` foi retirado — "
        "a ingestão agora lê o cache versionado em corpus/ocr/ por documento "
        "inteiro, não por sobreposição de páginas."
    ),
}


def _recusar_variaveis_aposentadas() -> None:
    """Falha alto quando o ambiente ainda usa o contrato antigo."""
    encontradas = [
        f"{nome}: {motivo}"
        for nome, motivo in VARIAVEIS_APOSENTADAS.items()
        if os.environ.get(nome) is not None
    ]
    if encontradas:
        raise ValueError(
            "Variáveis de ambiente aposentadas ainda definidas (remova-as do "
            ".env): " + "; ".join(encontradas)
        )


def _validar_config(config: Config) -> Config:
    """Falha cedo para configurações que produziriam execução ambígua ou insegura."""
    erros: list[str] = []

    bancos_esperados = Config().bancos
    if config.bancos != bancos_esperados:
        erros.append(
            "BANCOS deve preservar exatamente o corpus canônico e sua ordem: "
            f"{bancos_esperados}"
        )
    for nome, valor in (
        ("N_TRIMESTRES", config.n_trimestres),
        ("CHUNK_TAMANHO_TOKENS", config.chunk_tamanho_tokens),
        ("TOP_K", config.top_k),
        ("OLLAMA_EMBEDDING_DIMENSAO", config.ollama_embedding_dimensao),
        ("OLLAMA_MAX_TOKENS", config.ollama_max_tokens),
        ("OLLAMA_EMBEDDING_BATCH_SIZE", config.ollama_embedding_batch_size),
        ("GEMINI_MAX_TOKENS", config.gemini_max_tokens),
        ("LIMITE_CARACTERES_PERGUNTA", config.limite_caracteres_pergunta),
        ("SQL_LIMITE_LINHAS", config.sql_limite_linhas),
        ("AGENTES_MAX_ITERACOES", config.agentes_max_iteracoes),
        (
            "AGENTES_MAX_CHAMADAS_FERRAMENTA",
            config.agentes_max_chamadas_ferramenta,
        ),
    ):
        if valor <= 0:
            erros.append(f"{nome} deve ser positivo")
    if config.chunk_sobreposicao_tokens < 0:
        erros.append("CHUNK_SOBREPOSICAO_TOKENS não pode ser negativo")
    elif config.chunk_sobreposicao_tokens >= config.chunk_tamanho_tokens:
        erros.append(
            "CHUNK_SOBREPOSICAO_TOKENS deve ser menor que CHUNK_TAMANHO_TOKENS"
        )
    if config.limite_perguntas_livres_por_sessao < 0:
        erros.append("LIMITE_PERGUNTAS_LIVRES_POR_SESSAO não pode ser negativo")
    if (
        isinstance(config.mistral_ocr_max_retries, bool)
        or not isinstance(config.mistral_ocr_max_retries, int)
        or config.mistral_ocr_max_retries < 0
        or config.mistral_ocr_max_retries > 5
    ):
        erros.append("MISTRAL_OCR_MAX_RETRIES deve estar entre 0 e 5")

    if config.extrator not in {"mistral_ocr", "pdfplumber"}:
        erros.append(f"EXTRATOR desconhecido: {config.extrator!r}")
    if config.mistral_ocr_table_format not in {"html", "markdown"}:
        erros.append("MISTRAL_OCR_TABLE_FORMAT deve ser html ou markdown")
    if config.mistral_ocr_confidence_granularity not in {"page", "word"}:
        erros.append(
            "MISTRAL_OCR_CONFIDENCE_GRANULARITY deve ser page ou word"
        )
    if (
        isinstance(config.mistral_ocr_limiar_confianca_media, bool)
        or not isinstance(
            config.mistral_ocr_limiar_confianca_media, (int, float)
        )
        or not math.isfinite(config.mistral_ocr_limiar_confianca_media)
        or not 0.0 <= config.mistral_ocr_limiar_confianca_media <= 1.0
    ):
        erros.append(
            "MISTRAL_OCR_LIMIAR_CONFIANCA_MEDIA deve ser finito entre 0 e 1"
        )
    if (
        not config.mistral_ocr_modelo
        or config.mistral_ocr_modelo.endswith("-latest")
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}",
            config.mistral_ocr_modelo,
        )
        is None
    ):
        erros.append(
            "MISTRAL_OCR_MODELO deve ser uma versão pinada; aliases *-latest "
            "não são aceitos"
        )

    # O ITR/DFP só existe no portal a partir de 2011 (5.5, verificado); ano
    # anterior baixaria 404 em silêncio e produziria painel vazio.
    if not 2011 <= config.cvm_ano_inicial <= 2100:
        erros.append("CVM_ANO_INICIAL deve estar entre 2011 e 2100")
    # O resultado do SQL é reinjetado no contexto do agente. Teto rígido para
    # que uma consulta larga não estoure a janela e vire truncamento silencioso.
    if config.sql_limite_linhas > 200:
        erros.append("SQL_LIMITE_LINHAS não pode exceder 200")

    desconhecidos = set(config.guardrails_ativos) - GUARDRAILS_CONHECIDOS
    if desconhecidos:
        erros.append(
            "GUARDRAILS_ATIVOS contém scanner desconhecido: "
            f"{sorted(desconhecidos)}; conhecidos={sorted(GUARDRAILS_CONHECIDOS)}"
        )
    if (
        isinstance(config.guardrails_limiar_injection, bool)
        or not isinstance(config.guardrails_limiar_injection, (int, float))
        or not math.isfinite(config.guardrails_limiar_injection)
        or not 0.0 <= config.guardrails_limiar_injection <= 1.0
    ):
        erros.append("GUARDRAILS_LIMIAR_INJECTION deve ser finito entre 0 e 1")
    if not config.presidio_idioma.strip():
        erros.append("PRESIDIO_IDIOMA não pode ser vazio")
    if not config.presidio_modelo_spacy.strip():
        erros.append("PRESIDIO_MODELO_SPACY não pode ser vazio")

    if config.estrategia_padrao not in {
        "closed_book", "keyword", "semantica", "hibrida", "fatos"
    }:
        erros.append(f"ESTRATEGIA_PADRAO desconhecida: {config.estrategia_padrao!r}")
    if config.embedding_provider not in {
        "ollama", "local", "azure_openai", "openai"
    }:
        erros.append(f"EMBEDDING_PROVIDER desconhecido: {config.embedding_provider!r}")
    if config.llm_provider not in {
        "gemini", "ollama", "azure_openai", "openai", "deepseek"
    }:
        erros.append(f"LLM_PROVIDER desconhecido: {config.llm_provider!r}")

    for nome, valor in (
        ("TEMPERATURA", config.temperatura),
        ("OLLAMA_TIMEOUT_S", config.ollama_timeout_s),
        ("GEMINI_TIMEOUT_S", config.gemini_timeout_s),
        ("MISTRAL_OCR_TIMEOUT_S", config.mistral_ocr_timeout_s),
        (
            "MISTRAL_OCR_PRECO_USD_MIL_PAGINAS",
            config.mistral_ocr_preco_usd_mil_paginas,
        ),
        ("MISTRAL_OCR_ORCAMENTO_TETO_USD", config.mistral_ocr_orcamento_teto_usd),
        ("GEMINI_PRECO_ENTRADA_USD_MILHAO", config.gemini_preco_entrada_usd_milhao),
        ("GEMINI_PRECO_SAIDA_USD_MILHAO", config.gemini_preco_saida_usd_milhao),
        ("TOLERANCIA_NUMERICA_PCT", config.tolerancia_numerica_pct),
        ("ORCAMENTO_TETO_USD", config.orcamento_teto_usd),
        ("SQL_TIMEOUT_S", config.sql_timeout_s),
    ):
        if not math.isfinite(valor):
            erros.append(f"{nome} deve ser finito")
    if config.sql_timeout_s <= 0:
        erros.append("SQL_TIMEOUT_S deve ser positivo")
    if config.temperatura < 0:
        erros.append("TEMPERATURA não pode ser negativa")
    elif config.temperatura > 2:
        erros.append("TEMPERATURA não pode exceder 2")
    if (
        config.ollama_timeout_s <= 0
        or config.gemini_timeout_s <= 0
        or config.mistral_ocr_timeout_s <= 0
    ):
        erros.append("timeouts devem ser positivos")
    if config.mistral_ocr_preco_usd_mil_paginas <= 0:
        erros.append("MISTRAL_OCR_PRECO_USD_MIL_PAGINAS deve ser positivo")
    if config.mistral_ocr_orcamento_teto_usd <= 0:
        erros.append("MISTRAL_OCR_ORCAMENTO_TETO_USD deve ser positivo")
    if (
        config.gemini_preco_entrada_usd_milhao < 0
        or config.gemini_preco_saida_usd_milhao < 0
    ):
        erros.append("preços Gemini não podem ser negativos")
    if (
        config.llm_provider == "gemini"
        and config.gemini_preco_entrada_usd_milhao
        + config.gemini_preco_saida_usd_milhao
        <= 0
    ):
        erros.append("preços Gemini não podem ser ambos zero")
    if config.tolerancia_numerica_pct < 0:
        erros.append("TOLERANCIA_NUMERICA_PCT não pode ser negativa")
    if config.orcamento_teto_usd <= 0:
        erros.append("ORCAMENTO_TETO_USD deve ser positivo")

    if "ollama" in {config.llm_provider, config.embedding_provider}:
        from src.ollama import endpoint_ollama_e_loopback

        if not endpoint_ollama_e_loopback(config.ollama_base_url):
            erros.append(
                "OLLAMA_BASE_URL deve apontar exclusivamente para loopback"
            )
    if config.llm_provider == "gemini":
        if not endpoint_gemini_e_oficial(config.gemini_base_url):
            erros.append(
                "GEMINI_BASE_URL deve usar o endpoint HTTPS oficial do Google"
            )
    if not endpoint_mistral_ocr_e_oficial(config.mistral_ocr_endpoint):
        erros.append(
            "MISTRAL_OCR_ENDPOINT deve ser exatamente o endpoint HTTPS "
            "oficial api.mistral.ai/v1/ocr"
        )
    if config.azure_openai_endpoint and not endpoint_azure_openai_e_oficial(
        config.azure_openai_endpoint
    ):
        erros.append(
            "AZURE_OPENAI_ENDPOINT deve ser um endpoint HTTPS *.openai.azure.com"
        )
    # Só cobra o host quando há segredo para trafegar: sem chave, o Langfuse
    # fica desligado e a RNF12 exige que isso não impeça a aplicação de abrir.
    if (
        config.langfuse_public_key or config.langfuse_secret_key
    ) and not endpoint_langfuse_e_https(config.langfuse_host):
        erros.append(
            "LANGFUSE_HOST deve ser HTTPS, sem credenciais embutidas na URL"
        )

    if erros:
        raise ValueError("Configuração inválida: " + "; ".join(erros))
    return config


def carregar_config(env_file: Path | None = None) -> Config:
    """Carrega o `.env` (se existir) e materializa a `Config`.

    Falta de chave obrigatória NÃO falha aqui: cada provedor valida as suas
    próprias credenciais ao ser instanciado, com mensagem clara (critério de
    "pronto", seção 7).
    """
    load_dotenv(env_file or RAIZ_PROJETO / ".env")
    _recusar_variaveis_aposentadas()
    padrao = Config()
    config = Config(
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
        extrator=_env("EXTRATOR", padrao.extrator),
        mistral_ocr_api_key=_env("MISTRAL_API_KEY", ""),
        mistral_ocr_endpoint=_env(
            "MISTRAL_OCR_ENDPOINT", padrao.mistral_ocr_endpoint
        ),
        mistral_ocr_modelo=_env(
            "MISTRAL_OCR_MODELO", padrao.mistral_ocr_modelo
        ),
        mistral_ocr_timeout_s=float(
            _env("MISTRAL_OCR_TIMEOUT_S", str(padrao.mistral_ocr_timeout_s))
        ),
        mistral_ocr_max_retries=int(
            _env("MISTRAL_OCR_MAX_RETRIES", str(padrao.mistral_ocr_max_retries))
        ),
        mistral_ocr_table_format=_env(
            "MISTRAL_OCR_TABLE_FORMAT", padrao.mistral_ocr_table_format
        ),
        mistral_ocr_include_blocks=_env_bool(
            "MISTRAL_OCR_INCLUDE_BLOCKS", padrao.mistral_ocr_include_blocks
        ),
        mistral_ocr_confidence_granularity=_env(
            "MISTRAL_OCR_CONFIDENCE_GRANULARITY",
            padrao.mistral_ocr_confidence_granularity,
        ),
        mistral_ocr_limiar_confianca_media=float(
            _env(
                "MISTRAL_OCR_LIMIAR_CONFIANCA_MEDIA",
                str(padrao.mistral_ocr_limiar_confianca_media),
            )
        ),
        mistral_ocr_preco_usd_mil_paginas=float(
            _env(
                "MISTRAL_OCR_PRECO_USD_MIL_PAGINAS",
                str(padrao.mistral_ocr_preco_usd_mil_paginas),
            )
        ),
        mistral_ocr_orcamento_teto_usd=float(
            _env(
                "MISTRAL_OCR_ORCAMENTO_TETO_USD",
                str(padrao.mistral_ocr_orcamento_teto_usd),
            )
        ),
        duckdb_path=RAIZ_PROJETO / _env("DUCKDB_PATH", "artefatos/cvm.duckdb"),
        cvm_ano_inicial=int(_env("CVM_ANO_INICIAL", str(padrao.cvm_ano_inicial))),
        sql_limite_linhas=int(
            _env("SQL_LIMITE_LINHAS", str(padrao.sql_limite_linhas))
        ),
        sql_timeout_s=float(_env("SQL_TIMEOUT_S", str(padrao.sql_timeout_s))),
        top_k=int(_env("TOP_K", str(padrao.top_k))),
        estrategia_padrao=_env("ESTRATEGIA_PADRAO", padrao.estrategia_padrao),
        chroma_path=RAIZ_PROJETO
        / _env("CHROMA_PATH", "artefatos/indice_vetorial"),
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
        gemini_base_url=_env("GEMINI_BASE_URL", padrao.gemini_base_url),
        gemini_api_key=_env(
            "GEMINI_API_KEY",
            _env("GOOGLE_API_KEY", padrao.gemini_api_key),
        ),
        gemini_modelo_llm=_env("GEMINI_MODELO_LLM", padrao.gemini_modelo_llm),
        gemini_timeout_s=float(
            _env("GEMINI_TIMEOUT_S", str(padrao.gemini_timeout_s))
        ),
        gemini_max_tokens=int(
            _env("GEMINI_MAX_TOKENS", str(padrao.gemini_max_tokens))
        ),
        gemini_reasoning_effort=_env(
            "GEMINI_REASONING_EFFORT", padrao.gemini_reasoning_effort
        ),
        gemini_preco_entrada_usd_milhao=float(
            _env(
                "GEMINI_PRECO_ENTRADA_USD_MILHAO",
                str(padrao.gemini_preco_entrada_usd_milhao),
            )
        ),
        gemini_preco_saida_usd_milhao=float(
            _env(
                "GEMINI_PRECO_SAIDA_USD_MILHAO",
                str(padrao.gemini_preco_saida_usd_milhao),
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
        deepseek_preco_entrada_usd_milhao=float(
            _env(
                "DEEPSEEK_PRECO_ENTRADA_USD_MILHAO",
                str(padrao.deepseek_preco_entrada_usd_milhao),
            )
        ),
        deepseek_preco_entrada_cache_hit_usd_milhao=float(
            _env(
                "DEEPSEEK_PRECO_ENTRADA_CACHE_HIT_USD_MILHAO",
                str(padrao.deepseek_preco_entrada_cache_hit_usd_milhao),
            )
        ),
        deepseek_preco_saida_usd_milhao=float(
            _env(
                "DEEPSEEK_PRECO_SAIDA_USD_MILHAO",
                str(padrao.deepseek_preco_saida_usd_milhao),
            )
        ),
        deepseek_max_tokens=int(
            _env("DEEPSEEK_MAX_TOKENS", str(padrao.deepseek_max_tokens))
        ),
        deepseek_reasoning_effort=_env(
            "DEEPSEEK_REASONING_EFFORT", padrao.deepseek_reasoning_effort
        ),
        agentes_max_iteracoes=int(
            _env("AGENTES_MAX_ITERACOES", str(padrao.agentes_max_iteracoes))
        ),
        agentes_max_chamadas_ferramenta=int(
            _env(
                "AGENTES_MAX_CHAMADAS_FERRAMENTA",
                str(padrao.agentes_max_chamadas_ferramenta),
            )
        ),
        guardrails_ativos=tuple(
            g.strip().lower()
            for g in _env(
                "GUARDRAILS_ATIVOS", ",".join(padrao.guardrails_ativos)
            ).split(",")
            if g.strip()
        ),
        guardrails_usar_onnx=_env_bool(
            "GUARDRAILS_USAR_ONNX", padrao.guardrails_usar_onnx
        ),
        guardrails_limiar_injection=float(
            _env(
                "GUARDRAILS_LIMIAR_INJECTION",
                str(padrao.guardrails_limiar_injection),
            )
        ),
        prompt_guard_habilitado=_env_bool(
            "PROMPT_GUARD_HABILITADO", padrao.prompt_guard_habilitado
        ),
        prompt_guard_modelo=_env(
            "PROMPT_GUARD_MODELO", padrao.prompt_guard_modelo
        ),
        guardrails_modelo_injecao_revision=_env(
            "GUARDRAILS_MODELO_INJECAO_REVISION",
            padrao.guardrails_modelo_injecao_revision,
        ),
        presidio_idioma=_env("PRESIDIO_IDIOMA", padrao.presidio_idioma),
        presidio_modelo_spacy=_env(
            "PRESIDIO_MODELO_SPACY", padrao.presidio_modelo_spacy
        ),
        presidio_habilitado=_env_bool(
            "PRESIDIO_HABILITADO", padrao.presidio_habilitado
        ),
        langfuse_public_key=_env("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=_env("LANGFUSE_SECRET_KEY", ""),
        langfuse_host=_env("LANGFUSE_HOST", padrao.langfuse_host),
        deepeval_modelo_juiz=_env("DEEPEVAL_MODELO_JUIZ", ""),
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
        limite_caracteres_pergunta=int(
            _env(
                "LIMITE_CARACTERES_PERGUNTA",
                str(padrao.limite_caracteres_pergunta),
            )
        ),
        habilitar_perguntas_livres=_env_bool(
            "HABILITAR_PERGUNTAS_LIVRES", padrao.habilitar_perguntas_livres
        ),
        modo_demonstracao_cacheado=_env_bool(
            "MODO_DEMONSTRACAO_CACHEADO", padrao.modo_demonstracao_cacheado
        ),
    )
    return _validar_config(config)
