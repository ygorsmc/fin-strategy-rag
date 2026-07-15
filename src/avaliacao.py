"""Avaliação das estratégias E0–E3 no conjunto-padrão — seções 5.8–5.10 (RF09).

Honestidade de avaliação (AGENTS.md §3): Recall@5, exatidão numérica e taxa de
recusa são RESULTADOS medidos a temperatura 0 sobre as 45 perguntas congeladas,
logados em `artefatos/logs_execucoes/` (JSONL, RNF08) e expostos no README —
nunca "testes que passam".
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.config import DIR_LOGS_EXECUCOES, DIR_RESULTADOS_AVALIACAO, Config
from src.geracao import ProvedorLLM, RespostaGerada
from src.recuperacao import Estrategia, Recuperador, ResultadoRecuperacao

# Esquema do gabarito (seção 5.8) — validado por teste.
COLUNAS_CONJUNTO_PADRAO = (
    "id",
    "conjunto",              # teste | dev (anti-overfitting, 5.8)
    "categoria",             # factual | comparativa | qualitativa | adversarial
    "subtipo_adversarial",   # fora_do_corpus | periodo_ausente | metrica_nao_divulgada | premissa_falsa | conhecimento_pretreino
    "pergunta",
    "resposta_esperada",
    "classe_verificacao",    # cvm | release_gerencial | n/a
    "unidade",
    "origem",                # tabela | texto (diagnóstico do modo de falha nº 2)
    "locais_aceitos",        # "documento:pagina;documento:pagina" — base do recall@k
    "pontos_chave",          # checklist das qualitativas ("cobre >= N e não contradiz")
    "comportamento_aceito",  # premissa falsa: recusa | correcao_fundamentada
)

CATEGORIAS = ("factual", "comparativa", "qualitativa", "adversarial")


class CustoExcedidoError(RuntimeError):
    """Gasto acumulado atingiu ORCAMENTO_TETO_USD — a execução pausa e reporta
    em vez de estourar o orçamento (RNF03, seção 5.9)."""


@dataclass(frozen=True)
class PerguntaPadrao:
    """Uma linha do `conjunto_padrao/perguntas.csv`."""

    id: str
    conjunto: str
    categoria: str
    subtipo_adversarial: str
    pergunta: str
    resposta_esperada: str
    classe_verificacao: str
    unidade: str
    origem: str
    locais_aceitos: str
    pontos_chave: str
    comportamento_aceito: str


@dataclass
class ResultadoItem:
    """Resultado de UMA pergunta em UMA estratégia — unidade do checkpoint."""

    pergunta_id: str
    estrategia: Estrategia
    resposta: RespostaGerada | None
    recuperados: list[ResultadoRecuperacao] = field(default_factory=list)
    recall_ok: bool | None = None       # None p/ qualitativas/adversariais/E0
    exatidao_ok: bool | None = None     # None fora das factuais
    recusa_correta: bool | None = None  # None fora das adversariais
    custo_usd: float = 0.0
    latencia_s: float = 0.0
    erro: str | None = None


@dataclass
class MetricasEstrategia:
    """Linha da tabela comparativa da seção 5.10 (metas na 5.9)."""

    estrategia: Estrategia
    recall_at_5: float | None       # None para E0 (não recupera)
    exatidao_numerica: float | None
    taxa_recusa_correta: float | None  # E0: diagnóstico, não meta
    custo_medio_usd: float
    latencia_media_s: float
    latencia_p95_s: float
    n_json_invalido: int


def carregar_conjunto_padrao(config: Config) -> list[PerguntaPadrao]:
    """Lê e valida o esquema do gabarito. As 45 de `conjunto=teste` são
    congeladas após a construção (etapa 3 do AGENTS.md)."""
    with open(config.conjunto_padrao_path, newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        if tuple(leitor.fieldnames or ()) != COLUNAS_CONJUNTO_PADRAO:
            raise ValueError(
                f"Esquema inesperado em {config.conjunto_padrao_path}: "
                f"{leitor.fieldnames!r}"
            )
        return [PerguntaPadrao(**linha) for linha in leitor]


def registrar_execucao(
    registro: dict, dir_logs: Path = DIR_LOGS_EXECUCOES, arquivo: str | None = None
) -> Path:
    """Anexa uma linha ao log JSONL da execução (RNF08): modelo, versão,
    parâmetros, prompt (versão), custo e timestamp UTC."""
    dir_logs.mkdir(parents=True, exist_ok=True)
    nome = arquivo or f"execucao_{datetime.now(timezone.utc):%Y%m%d}.jsonl"
    caminho = dir_logs / nome
    registro = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), **registro}
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
    return caminho


def avaliar_recall_at_k(
    pergunta: PerguntaPadrao, recuperados: list[ResultadoRecuperacao], k: int = 5
) -> bool:
    """Definições operacionais da seção 5.9:
      - factual: acerto se algum chunk do top-k cobre uma das páginas-fonte
        aceitas no gabarito (comparação POR PÁGINA);
      - comparativa: exige TODAS as instituições da pergunta representadas
        no top-k."""
    raise NotImplementedError("Etapa 9 do AGENTS.md — recall@k")


def avaliar_exatidao_numerica(
    pergunta: PerguntaPadrao, resposta: RespostaGerada, config: Config
) -> bool:
    """Compara via `normalizacao.normalizar_numero_ptbr` +
    `valores_equivalentes` (tolerância TOLERANCIA_NUMERICA_PCT)."""
    raise NotImplementedError("Etapa 9 do AGENTS.md — exatidão numérica")


def avaliar_recusa(pergunta: PerguntaPadrao, resposta: RespostaGerada) -> bool:
    """Adversarial: correta se recusa=True. Premissa falsa aceita recusa OU
    correção fundamentada com citação (campo comportamento_aceito, 5.8)."""
    raise NotImplementedError("Etapa 9 do AGENTS.md — taxa de recusa")


def executar_avaliacao(
    config: Config,
    recuperador: Recuperador,
    provedor_llm: ProvedorLLM,
    estrategias: list[Estrategia],
    conjunto: str = "teste",
    dir_checkpoint: Path = DIR_RESULTADOS_AVALIACAO,
) -> dict[Estrategia, MetricasEstrategia]:
    """Loop resiliente da seção 5.9:
      - checkpoint POR PERGUNTA (retomável após 429/queda de rede);
      - retry com backoff; custo logado por chamada;
      - levanta CustoExcedidoError ao atingir ORCAMENTO_TETO_USD;
      - grava métricas por estratégia + respostas cacheadas do demo em
        `artefatos/resultados_avaliacao/` e o log JSONL em
        `artefatos/logs_execucoes/` (RNF08)."""
    raise NotImplementedError("Etapa 9 do AGENTS.md — avaliação em lote")


def consolidar_metricas(
    itens: list[ResultadoItem],
) -> dict[Estrategia, MetricasEstrategia]:
    """Agrega os ResultadoItem em MetricasEstrategia (tabela da seção 5.10)."""
    raise NotImplementedError("Etapa 9 do AGENTS.md — consolidação")
