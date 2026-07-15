"""Avaliação das estratégias E0–E3 no conjunto-padrão — seções 5.8–5.10 (RF09).

Honestidade de avaliação (AGENTS.md §3): Recall@5, exatidão numérica e taxa de
recusa são RESULTADOS medidos a temperatura 0 sobre as 45 perguntas congeladas,
logados em `artefatos/logs_execucoes/` (JSONL, RNF08) e expostos no README —
nunca "testes que passam".
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.config import DIR_LOGS_EXECUCOES, DIR_RESULTADOS_AVALIACAO, Config
from src.geracao import (
    VERSAO_PROMPT,
    Citacao,
    ProvedorLLM,
    RespostaGerada,
    gerar_resposta,
)
from src.normalizacao import (
    extrair_bancos_citados,
    normalizar_numero_ptbr,
    valores_equivalentes,
)
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
    top = recuperados[:k]
    if pergunta.categoria == "comparativa":
        exigidas = set(extrair_bancos_citados(pergunta.pergunta))
        presentes = {r.chunk.empresa for r in top}
        return bool(exigidas) and exigidas <= presentes
    for local in pergunta.locais_aceitos.split(";"):
        local = local.strip()
        if not local or ":" not in local:
            continue
        documento, _, pagina_txt = local.rpartition(":")
        try:
            pagina = int(pagina_txt)
        except ValueError:
            continue
        for r in top:
            if (
                r.chunk.documento == documento
                and r.chunk.pagina_inicio <= pagina <= r.chunk.pagina_fim
            ):
                return True
    return False


def avaliar_exatidao_numerica(
    pergunta: PerguntaPadrao, resposta: RespostaGerada, config: Config
) -> bool:
    """Compara via `normalizacao.normalizar_numero_ptbr` +
    `valores_equivalentes` (tolerância TOLERANCIA_NUMERICA_PCT)."""
    if resposta.recusa or resposta.resposta is None:
        return False
    esperado = normalizar_numero_ptbr(pergunta.resposta_esperada)
    obtido = normalizar_numero_ptbr(resposta.resposta)
    if esperado is None or obtido is None:
        return False
    return valores_equivalentes(
        esperado, obtido, tolerancia_pct=config.tolerancia_numerica_pct
    )


def avaliar_recusa(pergunta: PerguntaPadrao, resposta: RespostaGerada) -> bool:
    """Adversarial: correta se recusa=True. Premissa falsa aceita recusa OU
    correção fundamentada com citação (campo comportamento_aceito, 5.8)."""
    aceitos = {
        c.strip()
        for c in pergunta.comportamento_aceito.split("|")
        if c.strip()
    } or {"recusa"}
    if resposta.json_invalido:
        return False  # lixo conta como erro da estratégia, nunca como recusa
    if resposta.recusa:
        return "recusa" in aceitos
    return (
        "correcao_fundamentada" in aceitos
        and bool(resposta.resposta)
        and bool(resposta.citacoes)
    )


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
    perguntas = [
        p for p in carregar_conjunto_padrao(config) if p.conjunto == conjunto
    ]
    if not perguntas:
        raise ValueError(f"Nenhuma pergunta com conjunto={conjunto!r} no gabarito.")

    dir_checkpoint.mkdir(parents=True, exist_ok=True)
    caminho_checkpoint = dir_checkpoint / f"checkpoint_{conjunto}.jsonl"
    itens = _carregar_checkpoint(caminho_checkpoint)
    feitos = {(i.pergunta_id, i.estrategia) for i in itens}
    custo_acumulado = sum(i.custo_usd for i in itens)

    for estrategia in estrategias:
        for pergunta in perguntas:
            if (pergunta.id, estrategia) in feitos:
                continue  # checkpoint: nunca re-executado nem pago 2× (5.9)
            if custo_acumulado >= config.orcamento_teto_usd:
                raise CustoExcedidoError(
                    f"Gasto acumulado US$ {custo_acumulado:.4f} atingiu o teto "
                    f"ORCAMENTO_TETO_USD={config.orcamento_teto_usd} — execução "
                    f"pausada; checkpoint em {caminho_checkpoint} permite retomar."
                )
            item = _avaliar_item(
                config, recuperador, provedor_llm, pergunta, estrategia
            )
            custo_acumulado += item.custo_usd
            itens.append(item)
            _anexar_checkpoint(caminho_checkpoint, item)
            registrar_execucao(
                {
                    "pergunta_id": pergunta.id,
                    "conjunto": conjunto,
                    "estrategia": estrategia.value,
                    "provedor": provedor_llm.nome,
                    "versao_prompt": VERSAO_PROMPT,
                    "temperatura": config.temperatura,
                    "recusa": item.resposta.recusa if item.resposta else None,
                    "recall_ok": item.recall_ok,
                    "exatidao_ok": item.exatidao_ok,
                    "recusa_correta": item.recusa_correta,
                    "custo_usd": item.custo_usd,
                    "custo_acumulado_usd": custo_acumulado,
                    "latencia_s": item.latencia_s,
                    "erro": item.erro,
                }
            )

    metricas = consolidar_metricas(itens)
    _salvar_metricas(metricas, dir_checkpoint / f"metricas_{conjunto}.json")
    _salvar_cache_demo(config, perguntas, itens, provedor_llm.nome, dir_checkpoint)
    return metricas


def _avaliar_item(
    config: Config,
    recuperador: Recuperador,
    provedor_llm: ProvedorLLM,
    pergunta: PerguntaPadrao,
    estrategia: Estrategia,
    tentativas: int = 3,
) -> ResultadoItem:
    """Uma pergunta em uma estratégia, com retry/backoff (429/rede)."""
    erro: str | None = None
    for tentativa in range(tentativas):
        try:
            recuperados = recuperador.recuperar(pergunta.pergunta, estrategia)
            resposta, uso = gerar_resposta(
                pergunta.pergunta,
                [r.chunk for r in recuperados],
                provedor_llm,
                config,
            )
            item = ResultadoItem(
                pergunta_id=pergunta.id,
                estrategia=estrategia,
                resposta=resposta,
                recuperados=recuperados,
                custo_usd=uso.custo_usd,
                latencia_s=uso.latencia_s,
            )
            if pergunta.categoria in ("factual", "comparativa"):
                if estrategia != Estrategia.CLOSED_BOOK:
                    item.recall_ok = avaliar_recall_at_k(
                        pergunta, recuperados, k=config.top_k
                    )
                if pergunta.categoria == "factual":
                    item.exatidao_ok = avaliar_exatidao_numerica(
                        pergunta, resposta, config
                    )
            elif pergunta.categoria == "adversarial":
                item.recusa_correta = avaliar_recusa(pergunta, resposta)
            return item
        except Exception as exc:  # noqa: BLE001 — loop resiliente da 5.9
            erro = f"{type(exc).__name__}: {exc}"
            if tentativa < tentativas - 1:
                time.sleep(2**tentativa)
    return ResultadoItem(
        pergunta_id=pergunta.id,
        estrategia=estrategia,
        resposta=None,
        erro=erro,
    )


def _anexar_checkpoint(caminho: Path, item: ResultadoItem) -> None:
    registro = {
        "pergunta_id": item.pergunta_id,
        "estrategia": item.estrategia.value,
        "recall_ok": item.recall_ok,
        "exatidao_ok": item.exatidao_ok,
        "recusa_correta": item.recusa_correta,
        "custo_usd": item.custo_usd,
        "latencia_s": item.latencia_s,
        "erro": item.erro,
        "resposta": None
        if item.resposta is None
        else {
            "resposta": item.resposta.resposta,
            "recusa": item.resposta.recusa,
            "motivo_recusa": item.resposta.motivo_recusa,
            "citacoes": [vars(c) for c in item.resposta.citacoes],
            "json_reparado": item.resposta.json_reparado,
            "json_invalido": item.resposta.json_invalido,
        },
        "fontes": [
            f"{r.chunk.empresa} · {r.chunk.documento} · "
            f"págs. {r.chunk.pagina_inicio}–{r.chunk.pagina_fim}"
            for r in item.recuperados
        ],
    }
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _carregar_checkpoint(caminho: Path) -> list[ResultadoItem]:
    if not caminho.exists():
        return []
    itens: list[ResultadoItem] = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        registro = json.loads(linha)
        resposta = None
        if registro.get("resposta") is not None:
            r = registro["resposta"]
            resposta = RespostaGerada(
                resposta=r["resposta"],
                recusa=r["recusa"],
                motivo_recusa=r["motivo_recusa"],
                citacoes=tuple(Citacao(**c) for c in r["citacoes"]),
                json_reparado=r["json_reparado"],
                json_invalido=r["json_invalido"],
            )
        itens.append(
            ResultadoItem(
                pergunta_id=registro["pergunta_id"],
                estrategia=Estrategia(registro["estrategia"]),
                resposta=resposta,
                recall_ok=registro["recall_ok"],
                exatidao_ok=registro["exatidao_ok"],
                recusa_correta=registro["recusa_correta"],
                custo_usd=registro["custo_usd"],
                latencia_s=registro["latencia_s"],
                erro=registro["erro"],
            )
        )
    return itens


def _media_binaria(valores: list[bool | None]) -> float | None:
    definidos = [v for v in valores if v is not None]
    if not definidos:
        return None
    return sum(definidos) / len(definidos)


def consolidar_metricas(
    itens: list[ResultadoItem],
) -> dict[Estrategia, MetricasEstrategia]:
    """Agrega os ResultadoItem em MetricasEstrategia (tabela da seção 5.10)."""
    metricas: dict[Estrategia, MetricasEstrategia] = {}
    for estrategia in {i.estrategia for i in itens}:
        do_grupo = [i for i in itens if i.estrategia == estrategia]
        latencias = sorted(i.latencia_s for i in do_grupo)
        p95 = latencias[max(0, round(0.95 * len(latencias)) - 1)] if latencias else 0.0
        metricas[estrategia] = MetricasEstrategia(
            estrategia=estrategia,
            recall_at_5=_media_binaria([i.recall_ok for i in do_grupo]),
            exatidao_numerica=_media_binaria([i.exatidao_ok for i in do_grupo]),
            taxa_recusa_correta=_media_binaria(
                [i.recusa_correta for i in do_grupo]
            ),
            custo_medio_usd=sum(i.custo_usd for i in do_grupo) / len(do_grupo),
            latencia_media_s=sum(i.latencia_s for i in do_grupo) / len(do_grupo),
            latencia_p95_s=p95,
            n_json_invalido=sum(
                1 for i in do_grupo if i.resposta and i.resposta.json_invalido
            ),
        )
    return metricas


def _salvar_metricas(
    metricas: dict[Estrategia, MetricasEstrategia], caminho: Path
) -> None:
    serializavel = {
        estrategia.value: {
            "recall_at_5": m.recall_at_5,
            "exatidao_numerica": m.exatidao_numerica,
            "taxa_recusa_correta": m.taxa_recusa_correta,
            "custo_medio_usd": m.custo_medio_usd,
            "latencia_media_s": m.latencia_media_s,
            "latencia_p95_s": m.latencia_p95_s,
            "n_json_invalido": m.n_json_invalido,
        }
        for estrategia, m in metricas.items()
    }
    caminho.write_text(
        json.dumps(serializavel, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _salvar_cache_demo(
    config: Config,
    perguntas: list[PerguntaPadrao],
    itens: list[ResultadoItem],
    provedor: str,
    dir_saida: Path,
) -> None:
    """Respostas da estratégia padrão viram o cache do modo demonstração
    (formato consumido por `app_streamlit.carregar_cache_demo`)."""
    estrategia_demo = Estrategia(config.estrategia_padrao)
    caminho_checkpoint = dir_saida / "respostas_cacheadas.json"
    por_id = {p.id: p for p in perguntas}
    cache: dict[str, dict] = {}
    checkpoint = dir_saida / f"checkpoint_{perguntas[0].conjunto}.jsonl"
    fontes_por_item: dict[tuple[str, str], list[str]] = {}
    if checkpoint.exists():
        for linha in checkpoint.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                registro = json.loads(linha)
                fontes_por_item[
                    (registro["pergunta_id"], registro["estrategia"])
                ] = registro.get("fontes", [])
    for item in itens:
        pergunta = por_id.get(item.pergunta_id)
        if (
            pergunta is None
            or item.estrategia != estrategia_demo
            or item.resposta is None
        ):
            continue
        if item.resposta.recusa:
            conteudo = (
                "**Recusa (RN02):** "
                + (item.resposta.motivo_recusa or "sem evidência no corpus.")
            )
        else:
            conteudo = item.resposta.resposta or "—"
        cache[pergunta.pergunta] = {
            "resposta": conteudo,
            "fontes": fontes_por_item.get(
                (item.pergunta_id, item.estrategia.value), []
            ),
            "provedor": provedor,
            "gabarito": pergunta.resposta_esperada,
        }
    caminho_checkpoint.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )
