"""Investigador e Auditor por **isolamento de contexto** (spec 5.9.1 · 5.9.5).

O eixo desta camada não é fonte de dado — é isolamento. Um agente investiga e
registra **como** chegou lá; o segundo recebe **apenas a afirmação e as citações
— jamais o rastro de raciocínio** — e tenta derrubá-la reexecutando as consultas
com as mesmas ferramentas, por conta própria. O Auditor acrescenta informação
justamente porque **não pode ver** o que o primeiro pensou; se visse, tenderia a
concordar, e a segunda chamada de modelo viraria repetição paga (risco 12a).

## O que este módulo garante por código, não por prompt

1. **O isolamento é filtragem explícita da mensagem** (`montar_contexto_auditor`),
   montada por **lista de permissão** — `pergunta`, `afirmacao`, `citacoes`, e
   nada mais. Nunca a instrução "ignore o raciocínio anterior": instrução no
   prompt degrada em silêncio, e o braço B degeneraria no braço A sem ninguém
   ver. `conferir_isolamento` é uma guarda de execução que **recusa** enviar ao
   Auditor uma mensagem em que sobrou fragmento do rastro.
2. **RN01 e RN02 continuam verificadas por código sobre o JSON de saída**
   (`verificar_regras_agente`). Um agente que "esquece" de citar não produz
   resposta sem citação — produz **recusa registrada**
   (`converter_em_recusa_agente`), com a saída original preservada para
   auditoria.
3. **Teto de iterações e de chamadas de ferramenta** (`config.agentes_max_*`).
   Estourou, a resposta é a melhor evidência reunida até ali, **marcada como
   parcial**. Nunca um laço aberto pagando token.
4. **Quando o Auditor contesta, o sistema não elege vencedor**: publica as duas
   evidências e marca a resposta como **não conciliada** (5.9.5). Quando não
   consegue reproduzir, a afirmação vira **resposta parcial marcada** — não é
   falsa, mas também não é publicável (5.9.1).
5. **`prever_risco` não existe** (RN07). A caixa de ferramentas é a de
   `src.ferramentas`, e a fábrica recusa qualquer nome de
   `FERRAMENTAS_PROIBIDAS`. No produto, e só nele, entra
   `consultar_modelo_prejuizo`: o modelo lido do artefato agregado, que na
   instância pública não recebe companhia nem devolve escore (AGENTS §3.16).
   O conjunto de ferramentas viaja em `FerramentasDoAgente.nomes`; o padrão
   continua sendo as quatro do experimento.
6. **Gate de dado com uma rodada corretiva** (`precisa_correcao_de_dado`).
   Publicar valor, base ou citação sem ter chamado `buscar_trechos`,
   `consultar_cvm` ou `calcular_indicadores` é responder de memória, mesmo que o
   agente tenha chamado `verificar_cobertura` — que não devolve valor nenhum.
   Antes de converter em recusa, o código reinjeta a regra violada e reexecuta
   **uma** vez, dentro do mesmo teto e com a chamada extra na contabilidade
   normal. Falhou de novo, é recusa registrada como antes.
7. **O Auditor só recebe afirmação de fato** (`dispensa_auditoria`). Pergunta de
   desambiguação (RN11) não afirma nada e não tem evidência a reproduzir: vai
   direto ao usuário, sem rodada de Auditor e sem `veredito_auditor`. O
   roteamento é por código — `montar_contexto_auditor` **recusa** montar
   contexto para esse comportamento, em vez de deixar o desvio degenerar em uma
   chamada paga que carimba `nao_reproduz` sobre uma pergunta.

## O achado que motivou o gate (2026-08-12)

No braço A, 14 das 15 perguntas chamaram **só** `verificar_cobertura` e pularam
para `Final Answer` com número e citação inventados; RN01/RN02 converteram 11 em
recusa. Nada errado chegou ao usuário — e é justamente esse o problema de
medição: a rede de segurança fazia o trabalho da disciplina do agente, e A, B e C
empatavam porque **nenhum braço com LLM chegava a usar as ferramentas de dado**.
A resposta foi em duas frentes, ambas neste módulo: prompt com regra mecânica e
exemplo ReAct completo (`EXEMPLO_REACT`), e o gate de correção por código.

## Divergência de dependência, declarada

A spec manda CrewAI, e é CrewAI: `Agent`, `Task`, `Crew` e `Process.sequential`.
A versão **1.15.x** exige `chromadb~=1.1.0` e arrasta `lancedb` — ou seja, o
framework passaria a ditar a versão do banco vetorial que o projeto inteiro roda
(o índice em `artefatos/indice_vetorial/` foi construído com `chromadb==1.4.0`,
e rebaixá-lo é mexer no índice para instalar um agente). A linha **0.193.x**
declara `chromadb>=0.5.23` e resolve sem tocar em nada do projeto — foi a
escolhida, e o motivo está registrado em `requirements.txt`. É a mesma decisão
que já foi tomada com o `mistralai`: fixar a versão que convive, em vez de
deixar a dependência nova reescrever o ambiente.

O laço de ferramentas do CrewAI é textual (`Thought:` / `Action:` /
`Final Answer:`), e por isso o provedor é chamado por `gerar_texto` — o mesmo
provedor plugável da RNF06, com a mesma temperatura e os mesmos preços da
configuração, para que custo e tokens sejam auditáveis (RNF08).

**RNF11:** nada aqui entra no caminho de avaliação E0–E3. Os dois caminhos
compartilham ferramentas e prompt; só a orquestração difere.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterator, Mapping, Sequence

from pydantic import BaseModel, Field

from src.avaliacao import (
    _eh_erro_transitorio,
    _retry_after_s,
    registrar_execucao,
)
from src.config import DIR_LOGS_EXECUCOES, Config
from src.ferramentas import (
    FERRAMENTA_MODELO,
    FERRAMENTAS_DISPONIVEIS,
    FERRAMENTAS_DO_PRODUTO,
    FERRAMENTAS_PROIBIDAS,
    CaixaDeFerramentas,
    ErroFerramenta,
    TetoChamadasExcedidoError,
)
from src import observabilidade
from src.geracao import (
    _GRUPOS_METRICAS,
    ProvedorLLM,
    _tokens_metrica_grounding,
    dividir_em_clausulas,
    fabricar_provedor_llm,
    fatos_numericos_do_chunk,
)
from src.normalizacao import extrair_numeros_ptbr_tipados

registrador = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Ambiente do CrewAI — silenciado antes de qualquer import do framework
# --------------------------------------------------------------------------- #


def configurar_ambiente_crewai() -> None:
    """Desliga telemetria e o prompt interativo de traces do framework.

    Três motivos, todos de contenção: (1) a primeira execução do CrewAI abre um
    `input()` de 20 s perguntando se o usuário quer ver traces — numa execução em
    lote isso trava o experimento esperando stdin; (2) a telemetria do framework
    é chamada externa não declarada, e chamada externa neste projeto é sempre
    opt-in; (3) o exportador OTLP do CrewAI compete com o Langfuse (5.12).

    **`OTEL_SDK_DISABLED` saiu da lista em 2026-10-19.** Ele desligava o
    OpenTelemetry do processo inteiro, e o Langfuse é OpenTelemetry: importar
    este módulo apagava os traces do chat sem erro nenhum. A telemetria do
    CrewAI já fica desligada só com `CREWAI_DISABLE_TELEMETRY`
    (`Telemetry._is_telemetry_disabled` no 0.193.2), e
    `tests/test_observabilidade.py` trava as duas coisas. `CREWAI_DISABLE_TRACKING`
    é a segunda trava, no lugar da que saiu: o próprio CrewAI a lê, e ela não
    desliga o OpenTelemetry dos outros.

    Só define o que ainda não estiver definido: a decisão continua sendo do
    ambiente, não deste módulo.
    """
    for chave, valor in (
        ("CREWAI_DISABLE_TELEMETRY", "true"),
        ("CREWAI_DISABLE_TRACKING", "true"),
        ("CREWAI_TRACING_ENABLED", "false"),
        # Chave que o próprio framework usa para não abrir o prompt de traces.
        ("CREWAI_TESTING", "true"),
    ):
        os.environ.setdefault(chave, valor)


configurar_ambiente_crewai()

from crewai import Agent, Crew, Process, Task  # noqa: E402
from crewai.llms.base_llm import BaseLLM  # noqa: E402
from crewai.tools import BaseTool  # noqa: E402

# --------------------------------------------------------------------------- #
# Vocabulário
# --------------------------------------------------------------------------- #

PAPEL_INVESTIGADOR = "investigador"
PAPEL_AUDITOR = "auditor"
PAPEL_AGENTE_UNICO = "agente_unico"
PAPEIS: frozenset[str] = frozenset(
    {PAPEL_INVESTIGADOR, PAPEL_AUDITOR, PAPEL_AGENTE_UNICO}
)

# A lista de permissão do contexto do Auditor. É **lista de permissão**, não de
# bloqueio: um campo novo em `SaidaInvestigador` fica de fora por construção, e
# não por alguém ter lembrado de adicioná-lo a uma lista de proibidos.
CAMPOS_CONTEXTO_AUDITOR: tuple[str, ...] = ("pergunta", "afirmacao", "citacoes")

# Marcadores do protocolo de ferramentas do CrewAI. Se algum deles aparecer no
# texto que iria ao Auditor, é rastro vazando — o Investigador copiou o próprio
# laço para dentro da afirmação.
MARCADORES_RASTRO: tuple[str, ...] = (
    "thought:",
    "action:",
    "action input:",
    "observation:",
    "final answer:",
)

# Tamanho mínimo para tratar um trecho de rastro como impressão digital. Abaixo
# disso o casamento seria acidental ("o lucro", "no painel") e a guarda passaria
# a reprovar afirmação legítima.
MIN_FRAGMENTO_RASTRO = 24

# Vocabulário de comportamento — o mesmo do conjunto e do braço C. Escrito aqui
# como literal, e não importado de `src.braco_determinista`, para manter a
# orquestração independente do arnês de medição: quem publica a resposta não
# depende de quem apura o experimento.
COMPORTAMENTO_PARCIAL_MARCADO = "resposta_parcial_marcada"
COMPORTAMENTO_RECUSA = "recusa"
COMPORTAMENTO_DESAMBIGUACAO = "pergunta_de_desambiguacao"

# Comportamentos que **não são afirmação de fato** e, por isso, não têm o que
# ser falsificado por uma conferência independente. Uma pergunta de
# desambiguação (RN11) não apresenta valor, não cita fonte e não conclui nada:
# ela devolve a escolha ao usuário. Mandá-la ao Auditor é pedir que ele
# reproduza uma evidência que não existe — o desfecho mecânico é
# `nao_reproduz`, que aqui significaria "não se aplica" e mesmo assim rebaixa a
# resposta correta a parcial (achado da rodada B `a2`, AGTC003).
COMPORTAMENTOS_SEM_AUDITORIA: frozenset[str] = frozenset(
    {COMPORTAMENTO_DESAMBIGUACAO}
)

VIOLACAO_RN01_SEM_CITACAO = "rn01_valor_sem_citacao"
VIOLACAO_RN01_CITACAO_SEM_LASTRO = "rn01_citacao_sem_lastro_em_ferramenta"
VIOLACAO_RN02_SEM_LASTRO = "rn02_valor_sem_lastro"
VIOLACAO_RN02_RECUSA_COM_VALOR = "rn02_recusa_apresenta_valor"
VIOLACAO_RN02_ROTULO_TROCADO = "rn02_valor_sob_outro_rotulo"
VIOLACAO_RN02_ROTULO_NAO_VERIFICAVEL = "rn02_rotulo_nao_verificavel"
VIOLACAO_SAIDA_ILEGIVEL = "saida_fora_do_contrato_json"

VEREDITO_CONFIRMA = "confirma"
VEREDITO_CONTESTA = "contesta"
VEREDITO_NAO_REPRODUZ = "nao_reproduz"
VEREDITOS: frozenset[str] = frozenset(
    {VEREDITO_CONFIRMA, VEREDITO_CONTESTA, VEREDITO_NAO_REPRODUZ}
)

# Tolerância relativa mínima do lastro numérico. Um número escrito com poucas
# casas ("R$ 6,2 bilhões") não é erro perante 6.234.000.000: é arredondamento.
# A tolerância real é a maior entre esta e a meia-casa do último dígito escrito.
TOLERANCIA_RELATIVA_MINIMA = 1e-4

# Escalas aceitas na conferência de lastro. O painel devolve reais; o texto
# costuma dizer "milhões". Sem isto, toda resposta correta seria acusada de
# alucinar — e o experimento mediria a régua, não o agente.
ESCALAS_LASTRO: tuple[float, ...] = (1.0, 1e3, 1e6, 1e9)


class VazamentoDeRastroError(RuntimeError):
    """A mensagem destinada ao Auditor ainda contém rastro do Investigador.

    É erro de programação, não de modelo: significa que a filtragem por código
    deixou passar algo. Falhar alto aqui é o que impede o braço B de degenerar
    silenciosamente no braço A (spec 5.9.5).
    """


class AuditoriaNaoAplicavelError(RuntimeError):
    """Pediu-se contexto de Auditor para uma saída que não afirma fato nenhum.

    Também é erro de programação: quem roteia deve consultar `dispensa_auditoria`
    **antes** de montar o contexto. A exceção existe para que o desvio falhe
    alto em qualquer caminho — produção, arnês de medição ou teste — em vez de
    gastar uma chamada de LLM para carimbar `nao_reproduz` sobre uma pergunta.
    """


class OrcamentoAgentesExcedidoError(RuntimeError):
    """O gasto acumulado atingiu `ORCAMENTO_TETO_USD`; a execução para."""


class TetoIteracoesExcedidoError(RuntimeError):
    """O teto rígido de chamadas de modelo por pergunta foi atingido.

    Não é falha de infraestrutura: é a contenção da 5.9.5 funcionando. Quem
    chamou monta a resposta com a evidência reunida até ali e a marca como
    parcial.
    """


# Margem sobre `agentes_max_iteracoes` antes de o teto rígido cortar.
#
# **Por que existe um teto próprio, se o CrewAI já tem `max_iter`.** O `max_iter`
# do framework não interrompe o laço: ao atingi-lo, ele anexa ao histórico um
# pedido de "resposta final" e **continua** iterando, na expectativa de que o
# modelo obedeça (`crewai/utilities/agent_utils.py::handle_max_iterations_exceeded`).
# Com um modelo que ignore o pedido — saída malformada, provedor de fallback,
# mau dia do modelo —, o laço não termina. Isso é exatamente o "laço aberto
# pagando token" que a 5.9.5 proíbe, e um teto que depende da cooperação do
# modelo não é teto. A margem de 1 existe para deixar o pedido de resposta final
# acontecer uma vez; a chamada seguinte é cortada por código.
MARGEM_PEDIDO_RESPOSTA_FINAL = 1

# Piso de tokens de saída na camada de agentes. Ver `config_para_agentes`.
AGENTES_MIN_TOKENS_SAIDA = 1536

# Tentativas por chamada de modelo, contando a primeira. Só erro transitório
# (429/5xx/timeout) reespera; erro de contrato sobe na hora.
TENTATIVAS_POR_CHAMADA = 4


# --------------------------------------------------------------------------- #
# Contabilidade de custo e journal write-ahead
# --------------------------------------------------------------------------- #


@dataclass
class UsoAgente:
    """Acumulador de custo de um papel dentro de uma pergunta (RNF03/RNF08)."""

    chamadas_llm: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    latencia_s: float = 0.0
    modelo: str = ""
    sem_telemetria: int = 0
    # Parcelas de diagnóstico: quanto da saída foi raciocínio e quanto da
    # entrada o provedor serviu de cache. Zero significa "não reportado pelo
    # provedor", não "não houve" — o Gemini, por exemplo, não expõe o split de
    # cache pela compatibilidade OpenAI.
    tokens_raciocinio: int = 0
    tokens_entrada_cache_hit: int = 0
    # Raciocínio textual por chamada, quando o provedor o devolve em campo
    # próprio. Existe para comparar COMO cada modelo reage ao prompt; nunca é
    # reinjetado em prompt nenhum — em particular, não chega ao Auditor, cujo
    # isolamento é verificado por `conferir_isolamento`.
    raciocinios: tuple[str, ...] = ()

    def somar(self, outro: "UsoAgente") -> "UsoAgente":
        return UsoAgente(
            chamadas_llm=self.chamadas_llm + outro.chamadas_llm,
            tokens_entrada=self.tokens_entrada + outro.tokens_entrada,
            tokens_saida=self.tokens_saida + outro.tokens_saida,
            custo_usd=self.custo_usd + outro.custo_usd,
            latencia_s=self.latencia_s + outro.latencia_s,
            modelo=self.modelo or outro.modelo,
            sem_telemetria=self.sem_telemetria + outro.sem_telemetria,
            tokens_raciocinio=self.tokens_raciocinio + outro.tokens_raciocinio,
            tokens_entrada_cache_hit=(
                self.tokens_entrada_cache_hit + outro.tokens_entrada_cache_hit
            ),
            raciocinios=self.raciocinios + outro.raciocinios,
        )

    def como_dicionario(self) -> dict:
        return {
            "chamadas_llm": self.chamadas_llm,
            "tokens_entrada": self.tokens_entrada,
            "tokens_saida": self.tokens_saida,
            "custo_usd": self.custo_usd,
            "latencia_s": self.latencia_s,
            "modelo": self.modelo,
            "sem_telemetria": self.sem_telemetria,
            "tokens_raciocinio": self.tokens_raciocinio,
            "tokens_entrada_cache_hit": self.tokens_entrada_cache_hit,
            "raciocinios": list(self.raciocinios),
        }


class ControleOrcamento:
    """Teto de gasto com journal write-ahead (RNF03 · §4.3 do plano).

    A ordem é sempre a mesma: grava a **intenção** com a estimativa conservadora
    antes de chamar, checa o teto contra `acumulado + estimativa`, chama, e grava
    a **conclusão** com o custo observado. Um processo morto no meio deixa a
    intenção registrada — o gasto órfão é visível, que é o ponto do journal.
    """

    def __init__(
        self,
        teto_usd: float,
        *,
        caminho_journal: Path | None = None,
        acumulado_inicial: float = 0.0,
    ) -> None:
        if not (teto_usd > 0):
            raise ValueError("teto de orçamento deve ser positivo")
        self.teto_usd = float(teto_usd)
        self.caminho_journal = caminho_journal
        self.acumulado_usd = float(acumulado_inicial)
        self.chamadas = 0

    @property
    def restante_usd(self) -> float:
        return max(0.0, self.teto_usd - self.acumulado_usd)

    def _anotar(self, evento: dict) -> None:
        if self.caminho_journal is None:
            return
        self.caminho_journal.parent.mkdir(parents=True, exist_ok=True)
        linha = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            **evento,
        }
        with self.caminho_journal.open("a", encoding="utf-8") as destino:
            destino.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
            destino.flush()
            os.fsync(destino.fileno())

    def autorizar(self, papel: str, estimativa_usd: float | None) -> int:
        """Registra a intenção e recusa a chamada que não cabe no teto."""
        self.chamadas += 1
        identificador = self.chamadas
        estimativa = float(estimativa_usd or 0.0)
        self._anotar(
            {
                "evento": "intencao",
                "chamada": identificador,
                "papel": papel,
                "estimativa_usd": estimativa,
                "acumulado_usd": self.acumulado_usd,
                "teto_usd": self.teto_usd,
            }
        )
        if self.acumulado_usd + estimativa > self.teto_usd:
            self._anotar(
                {
                    "evento": "bloqueio_por_teto",
                    "chamada": identificador,
                    "papel": papel,
                    "estimativa_usd": estimativa,
                    "acumulado_usd": self.acumulado_usd,
                }
            )
            raise OrcamentoAgentesExcedidoError(
                f"chamada do {papel} recusada: acumulado US$ "
                f"{self.acumulado_usd:.6f} + estimativa US$ {estimativa:.6f} "
                f"passa do teto ORCAMENTO_TETO_USD={self.teto_usd}"
            )
        return identificador

    def confirmar(self, identificador: int, papel: str, custo_usd: float) -> None:
        self.acumulado_usd += float(custo_usd or 0.0)
        self._anotar(
            {
                "evento": "conclusao",
                "chamada": identificador,
                "papel": papel,
                "custo_usd": float(custo_usd or 0.0),
                "acumulado_usd": self.acumulado_usd,
            }
        )


# --------------------------------------------------------------------------- #
# Ponte entre o provedor plugável do projeto e o executor do CrewAI
# --------------------------------------------------------------------------- #


def achatar_mensagens(mensagens: str | Sequence[Mapping[str, str]]) -> tuple[str, str]:
    """Converte o histórico do CrewAI no par (sistema, usuário) do provedor.

    O contrato `ProvedorLLM.gerar_texto` é de dois blocos, e o executor do
    CrewAI mantém um histórico de papéis. As mensagens de sistema viram o bloco
    de sistema; o resto vira transcrição rotulada, preservando **ordem e
    autoria** — que é o que o protocolo `Thought/Action/Observation` precisa
    para continuar de onde parou.
    """
    if isinstance(mensagens, str):
        return "", mensagens
    sistema: list[str] = []
    conversa: list[str] = []
    for mensagem in mensagens:
        papel = str(mensagem.get("role", "user"))
        conteudo = str(mensagem.get("content", ""))
        if papel == "system":
            sistema.append(conteudo)
        elif papel == "assistant":
            conversa.append(conteudo)
        else:
            conversa.append(conteudo)
    return "\n\n".join(sistema), "\n\n".join(conversa)


# A parada registrada pelo executor é o literal `Observation:`. Um modelo que
# escreve o protocolo em OUTRA notação escapa dela e fabrica o retorno da
# ferramenta sem que nada corte.
#
# Medido em 2026-08-14, DeepSeek v4-flash em `reasoning_effort=max`, AGTC004: o
# modelo emitiu `<Thought>`, `<Action>` e `<Observation>` em tags XML e escreveu
# dentro da própria `<Observation>` um resultado completo de `verificar_cobertura`
# — CD_CVM, razão social e trimestres — que nenhuma ferramenta devolveu. Como
# `<Observation>` não casa com `Observation:`, o corte não disparou.
#
# A guarda é de CÓDIGO e não de prompt de propósito: pedir ao modelo que use a
# notação certa é orientação, e o projeto não confia regra verificável a
# julgamento de modelo (§4.2). O casamento é por início de linha, tolerando
# decoração (`<`, `*`, `#`, `-`) e as grafias em português, para não cortar a
# palavra "observação" no meio de uma frase legítima.
_PADRAO_OBSERVACAO_FABRICADA = re.compile(
    r"^[ \t]*[<\[\*_`#>\-]{0,3}[ \t]*observa(?:tion|ção|cao)[ \t]*"
    r"[>\]\*_`]{0,3}(?:[ \t]*:|\s|$)",
    re.IGNORECASE | re.MULTILINE,
)


def cortar_em_parada(texto: str, paradas: Sequence[str] | None) -> str:
    """Trunca a saída na primeira sequência de parada (o `stop` do executor).

    O CrewAI registra `Observation:` como parada porque a observação é o que a
    **ferramenta** devolve, não o que o modelo escreve. Sem o corte, o modelo
    escreve os dois no mesmo turno e a "consulta" nunca acontece — o resultado é
    uma transcrição inteira de evidência inexistente, com código CVM e valor
    plausíveis. As regras de RN01/RN02 pegam isso depois e convertem em recusa,
    mas aí já se pagou a chamada e o experimento mediu o prompt, não a
    orquestração.
    """
    if not texto:
        return texto
    corte = len(texto)
    for parada in paradas or ():
        if not parada:
            continue
        posicao = texto.find(parada)
        if posicao != -1:
            corte = min(corte, posicao)
    achado = _PADRAO_OBSERVACAO_FABRICADA.search(texto)
    if achado is not None:
        corte = min(corte, achado.start())
    return texto[:corte].rstrip()


class LLMPonte(BaseLLM):
    """`BaseLLM` do CrewAI implementado sobre o provedor plugável do projeto.

    Existe para que a camada de agentes **não** ganhe um segundo caminho de
    inferência: o mesmo provedor da RNF06, a mesma temperatura da configuração e
    os mesmos preços por 1M de tokens que tornam o teto auditável. Sem isso, o
    custo do braço B viria da contabilidade do framework e não seria comparável
    com o do braço C nem com o caminho determinístico.

    Não anuncia *function calling*: o executor usa o protocolo textual, que é o
    que os provedores deste projeto sabem produzir.
    """

    def __init__(
        self,
        provedor: ProvedorLLM,
        *,
        papel: str,
        temperatura: float = 0.0,
        orcamento: ControleOrcamento | None = None,
    ) -> None:
        super().__init__(model=getattr(provedor, "nome", "desconhecido"),
                         temperature=temperatura)
        if papel not in PAPEIS:
            raise ValueError(f"papel desconhecido: {papel!r}")
        self.provedor = provedor
        self.papel = papel
        self.orcamento = orcamento
        self.uso = UsoAgente()

    def supports_function_calling(self) -> bool:  # pragma: no cover - trivial
        return False

    def supports_stop_words(self) -> bool:
        """Sim — e é o que impede o agente de inventar a saída da ferramenta.

        Sem parada em `Observation:`, o modelo escreve a **ação e o resultado
        dela** no mesmo turno: uma transcrição inteira de consultas que nunca
        aconteceram, com `CD_CVM` e valores plausíveis. Medido no Gemini em
        2026-08-12, na primeira execução real: zero chamadas de ferramenta e
        três violações de RN01/RN02 numa pergunta só.

        A parada é aplicada aqui, sobre o texto devolvido, porque o contrato
        `ProvedorLLM.gerar_texto` não tem parâmetro de `stop` — o efeito no laço
        é o mesmo, ao custo dos tokens já gerados depois do corte.
        """
        return True

    def _gerar_com_reespera(self, sistema: str, usuario: str):
        """Chama o provedor, reesperando **só** em erro transitório.

        Motivo medido: na primeira execução do braço B (2026-08-12) duas das 15
        perguntas morreram com HTTP 429 do provedor. Erro de cota não é
        comportamento de agente, e deixá-lo no resultado transformaria uma falha
        de infraestrutura em "o agente não respondeu" — que é justamente a
        confusão que a 5.9.4 existe para desfazer.

        A classificação de transitório e o intervalo de espera são os **mesmos**
        do caminho de avaliação (`src.avaliacao`), reusados em vez de
        reescritos: duas políticas de reespera divergiriam, e a divergência
        apareceria como diferença entre os caminhos.
        """
        ultimo: Exception | None = None
        for tentativa in range(TENTATIVAS_POR_CHAMADA):
            try:
                return self.provedor.gerar_texto(
                    sistema, usuario, self.temperature or 0.0
                )
            except Exception as erro:
                if not _eh_erro_transitorio(erro):
                    raise
                ultimo = erro
                if tentativa == TENTATIVAS_POR_CHAMADA - 1:
                    break
                espera = _retry_after_s(erro, tentativa)
                registrador.warning(
                    "agentes: erro transitório do provedor (%s); reesperando "
                    "%.1fs (tentativa %d/%d)",
                    type(erro).__name__,
                    espera,
                    tentativa + 1,
                    TENTATIVAS_POR_CHAMADA,
                )
                time.sleep(espera)
        assert ultimo is not None
        raise ultimo

    def call(
        self,
        messages: str | list[dict[str, str]],
        tools: list[dict] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Any | None = None,
        from_agent: Any | None = None,
    ) -> str:
        sistema, usuario = achatar_mensagens(messages)
        identificador = None
        if self.orcamento is not None:
            estimativa = None
            estimar = getattr(self.provedor, "estimar_custo_maximo", None)
            if callable(estimar):
                estimativa = estimar(sistema, usuario)
            identificador = self.orcamento.autorizar(self.papel, estimativa)
        bruta = self._gerar_com_reespera(sistema, usuario)
        uso = bruta.uso
        custo = getattr(uso, "custo_usd", None)
        if custo is None:
            # Provedor sem preço configurado: o custo não é zero, é
            # desconhecido. Registrar zero seria medição falsa (§4.3).
            self.uso.sem_telemetria += 1
            custo = 0.0
        self.uso.chamadas_llm += 1
        self.uso.tokens_entrada += int(getattr(uso, "tokens_entrada", 0) or 0)
        self.uso.tokens_saida += int(getattr(uso, "tokens_saida", 0) or 0)
        self.uso.custo_usd += float(custo)
        self.uso.latencia_s += float(getattr(uso, "latencia_s", 0.0) or 0.0)
        self.uso.modelo = str(getattr(bruta, "modelo", "") or self.uso.modelo)
        self.uso.tokens_raciocinio += int(
            getattr(uso, "tokens_raciocinio", 0) or 0
        )
        self.uso.tokens_entrada_cache_hit += int(
            getattr(uso, "tokens_entrada_cache_hit", 0) or 0
        )
        raciocinio = getattr(bruta, "raciocinio", "") or ""
        if raciocinio.strip():
            self.uso.raciocinios += (raciocinio,)
        if self.orcamento is not None and identificador is not None:
            self.orcamento.confirmar(identificador, self.papel, float(custo))
        return cortar_em_parada(bruta.texto, self.stop)


class LLMComTetoRigido(BaseLLM):
    """Envelope que **corta** o laço do agente por contagem de chamadas.

    Fica entre o executor do CrewAI e o modelo, e é a única garantia de que o
    teto de passos é teto. Envolve qualquer `BaseLLM` — inclusive os duplos dos
    testes —, porque a contenção não pode depender de qual provedor está atrás:
    é regra do sistema, não propriedade do modelo.

    Tudo o que não é a contagem é delegado ao envolvido: `uso` (a contabilidade
    de custo continua a do provedor real), suporte a *function calling* e janela
    de contexto. Um envelope que reimplementasse a contabilidade criaria dois
    números de custo, e um deles ficaria errado.
    """

    def __init__(self, interno: BaseLLM, teto_chamadas: int) -> None:
        if teto_chamadas <= 0:
            raise ValueError("teto de chamadas deve ser positivo")
        # Antes do `super().__init__`, que atribui `self.stop` — e o setter de
        # `stop` delega ao envolvido.
        self.interno = interno
        super().__init__(
            model=getattr(interno, "model", "desconhecido"),
            temperature=getattr(interno, "temperature", 0.0),
        )
        self.teto_chamadas = teto_chamadas
        self.chamadas = 0
        self.teto_atingido = False

    @property
    def uso(self) -> UsoAgente:
        return getattr(self.interno, "uso", UsoAgente())

    @property
    def stop(self) -> list[str]:
        """Delegada ao envolvido: o executor configura a parada no envelope.

        Sem a delegação, o `Observation:` seria registrado aqui e o provedor
        nunca o veria — o corte não aconteceria e o agente voltaria a inventar a
        saída da própria ferramenta.
        """
        return getattr(self.interno, "stop", []) or []

    @stop.setter
    def stop(self, valor) -> None:
        if isinstance(valor, str):
            valor = [valor]
        self.interno.stop = list(valor or [])

    def supports_function_calling(self) -> bool:
        metodo = getattr(self.interno, "supports_function_calling", None)
        return bool(metodo()) if callable(metodo) else False

    def supports_stop_words(self) -> bool:
        metodo = getattr(self.interno, "supports_stop_words", None)
        return bool(metodo()) if callable(metodo) else False

    def get_context_window_size(self) -> int:
        metodo = getattr(self.interno, "get_context_window_size", None)
        if callable(metodo):
            return metodo()
        return super().get_context_window_size()

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
    ):
        if self.chamadas >= self.teto_chamadas:
            self.teto_atingido = True
            raise TetoIteracoesExcedidoError(
                f"teto rígido de {self.teto_chamadas} chamadas de modelo "
                "atingido nesta pergunta; a resposta é a evidência reunida até "
                "aqui, marcada como parcial (spec 5.9.5)"
            )
        self.chamadas += 1
        return self.interno.call(
            messages,
            tools=tools,
            callbacks=callbacks,
            available_functions=available_functions,
            from_task=from_task,
            from_agent=from_agent,
        )


# --------------------------------------------------------------------------- #
# Ferramentas: registro de resultado e evidência disponível
# --------------------------------------------------------------------------- #

# Limite de texto por trecho devolvido ao agente. O trecho inteiro custaria
# token sem acrescentar evidência: a citação exige empresa, documento,
# trimestre e página, todos fora do corpo do texto.
MAX_CARACTERES_TRECHO = 900
MAX_TRECHOS = 4


@dataclass(frozen=True)
class ChamadaFerramenta:
    """Uma chamada, com resultado — a base do lastro de RN01/RN02."""

    papel: str
    ferramenta: str
    argumentos: Mapping[str, Any]
    resumo: str = ""
    erro: str | None = None
    resultado: Any = None

    def como_dicionario(self) -> dict:
        return {
            "papel": self.papel,
            "ferramenta": self.ferramenta,
            "argumentos": dict(self.argumentos),
            "resumo": self.resumo,
            "erro": self.erro,
        }


#: Quem acompanha as ferramentas enquanto o agente trabalha (a interface).
#: Recebe papel, ferramenta e estado: "inicio", "ok" ou "falhou".
ObservadorDeFerramenta = Callable[[str, str, str], None]


class FerramentasDoAgente:
    """Envelope da `CaixaDeFerramentas` que guarda o **resultado** de cada chamada.

    A caixa registra a chamada e um resumo; a verificação de RN01/RN02 por
    código precisa do conteúdo devolvido — quais documentos existiram, quais
    números o painel entregou. Sem isso, "citação sem lastro" e "valor sem
    lastro" não são verificáveis e as regras migrariam para dentro do agente,
    que é justamente o que a 5.9.5 proíbe.
    """

    def __init__(
        self,
        caixa: CaixaDeFerramentas,
        papel: str,
        nomes: Sequence[str] = FERRAMENTAS_DISPONIVEIS,
        ao_chamar: ObservadorDeFerramenta | None = None,
    ) -> None:
        if papel not in PAPEIS:
            raise ValueError(f"papel desconhecido: {papel!r}")
        proibidas = sorted(set(nomes) & set(FERRAMENTAS_PROIBIDAS))
        if proibidas:
            raise ValueError(f"ferramenta proibida na caixa do agente (RN07): {proibidas}")
        desconhecidas = sorted(set(nomes) - set(FERRAMENTAS_DO_PRODUTO))
        if desconhecidas:
            raise ValueError(f"ferramenta sem implementação: {desconhecidas}")
        self.caixa = caixa
        self.papel = papel
        # Quais ferramentas este agente pode chamar. O padrão são as quatro do
        # experimento; o produto passa `FERRAMENTAS_DO_PRODUTO` (§3.16).
        self.nomes: tuple[str, ...] = tuple(nomes)
        self.chamadas: list[ChamadaFerramenta] = []
        self.teto_atingido = False
        # A interface mostra cada ferramenta enquanto o agente trabalha: uma
        # pergunta aos agentes leva até 50 s, e um spinner mudo pelo tempo
        # todo parecia travamento (traces de 19/10).
        self._ao_chamar = ao_chamar

    def _avisar(self, nome: str, estado: str) -> None:
        """Avisa o observador; falha dele nunca chega ao agente."""
        if self._ao_chamar is None:
            return
        try:
            self._ao_chamar(self.papel, nome, estado)
        except Exception as exc:  # noqa: BLE001 - exibição não decide nada
            registrador.warning(
                "observador de ferramenta falhou (tipo=%s).", type(exc).__name__
            )

    # -- execução ----------------------------------------------------------- #

    def executar(self, nome: str, **argumentos: Any) -> Any:
        """Executa uma ferramenta da caixa, nunca uma proibida (RN07)."""
        if nome in FERRAMENTAS_PROIBIDAS:
            raise ErroFerramenta(
                f"{nome} não é ferramenta desta camada (RN07): o modelo "
                "preditivo não é exposto como resposta sobre companhia nomeada"
            )
        if nome not in self.nomes:
            raise ErroFerramenta(f"ferramenta desconhecida: {nome!r}")
        metodo = getattr(self.caixa, nome)
        self._avisar(nome, "inicio")
        # Span de ferramenta (5.12). Os argumentos vêm do LLM e podem trazer o
        # texto da pergunta: passam pela regra de texto livre (RN06).
        with observabilidade.etapa(
            f"ferramenta.{nome}",
            tipo="tool",
            entrada=lambda: {
                "papel": self.papel,
                "argumentos": observabilidade.texto_livre(_serializar(dict(argumentos))),
            },
        ) as etapa:
            try:
                resultado = metodo(**argumentos)
            except TetoChamadasExcedidoError:
                self.teto_atingido = True
                self._avisar(nome, "falhou")
                raise
            except Exception:
                self._avisar(nome, "falhou")
                raise
            registro = self.caixa.registro[-1] if self.caixa.registro else None
            etapa.atualizar(
                saida=lambda: {
                    "resumo": observabilidade.texto_livre(registro.resumo if registro else ""),
                    "falhou": bool(registro and registro.erro),
                }
            )
        self.chamadas.append(
            ChamadaFerramenta(
                papel=self.papel,
                ferramenta=nome,
                argumentos=dict(argumentos),
                resumo=registro.resumo if registro else "",
                erro=registro.erro if registro else None,
                resultado=resultado,
            )
        )
        self._avisar(nome, "falhou" if registro and registro.erro else "ok")
        return resultado

    def registrar_falha(self, nome: str, argumentos: Mapping[str, Any], erro: str) -> None:
        self.chamadas.append(
            ChamadaFerramenta(
                papel=self.papel,
                ferramenta=nome,
                argumentos=dict(argumentos),
                resumo="",
                erro=erro,
            )
        )

    # -- lastro ------------------------------------------------------------- #

    def rotulos_de_evidencia(self) -> frozenset[str]:
        """Identificadores que uma citação pode legitimamente invocar.

        Documento, empresa e trimestre vindos de `buscar_trechos`; `CD_CVM`,
        razão social, conceito e trimestre vindos do painel. Uma citação que não
        casa com **nenhum** deles nomeia fonte que ferramenta alguma devolveu —
        é citação inventada, e vira recusa registrada (RN01).

        A coleta é por **chave conhecida**, não por varredura de todas as
        cadeias: se qualquer texto do resultado virasse rótulo, as próprias
        chaves do JSON ("trimestre", "empresa") casariam com qualquer citação e
        a verificação viraria carimbo.
        """
        rotulos: set[str] = set()
        for chamada in self.chamadas:
            _coletar_evidencias(chamada.resultado, rotulos, [])
        return frozenset(r for r in rotulos if len(r) >= 4)

    def valores_de_evidencia(self) -> tuple[float, ...]:
        """Números que as ferramentas devolveram, em reais e em texto recuperado."""
        valores: list[float] = []
        for chamada in self.chamadas:
            _coletar_evidencias(chamada.resultado, set(), valores)
        return tuple(valores)

    def fatos_rotulados(self) -> tuple["FatoRotulado", ...]:
        """Os mesmos números, cada um com a métrica que o governa na fonte.

        É o que a RN02 por rótulo compara (`valores_com_rotulo_trocado`):
        saber que 17,2 bilhões existe no trecho não diz se é margem ou
        despesa.
        """
        return tuple(
            FatoRotulado(valor, tokens, chamada.ferramenta)
            for chamada in self.chamadas
            if chamada.erro is None
            for valor, tokens in _fatos_rotulados(chamada.resultado)
        )


# Chaves cujo valor textual identifica uma fonte citável.
CHAVES_DE_ROTULO: frozenset[str] = frozenset(
    {
        "cd_cvm",
        "conceito",
        "denom_social",
        "documento",
        "ds_conta",
        "empresa",
        "estado",
        "id",
        "trimestre",
        "trimestres_corpus",
        "trimestres_painel",
    }
)

# Números que existem no resultado mas não são evidência de valor financeiro.
# Sem esta lista, a página 5 de um trecho "lastraria" R$ 5 milhões — e a
# verificação de RN02 passaria a aprovar alucinação por coincidência de dígito.
CHAVES_SEM_VALOR: frozenset[str] = frozenset(
    {
        "derivado",
        "is_banco",
        "n",
        "pagina_fim",
        "pagina_inicio",
        "score",
        "top_k",
        "total_linhas",
        # Saída de `consultar_modelo_prejuizo`: contagens, percentuais e AUC.
        # Nenhuma é dinheiro, e sem isto "21.119 observações" lastrearia um
        # "R$ 21,1 mil" inventado.
        #
        # `ativo_total_reais` é o ECO do argumento que o próprio agente passou
        # (`faixa_do_ativo_informado`). Contá-lo como evidência deixava um ativo
        # inventado se lastrear sozinho: o agente chama o modelo com
        # 73,4 bilhões e escreve 73,4 bilhões (achado da auditoria de 20/10). O
        # ativo real tem de vir do painel, que o devolve em `valor_reais`.
        "ativo_total_reais",
        "auc_walk_forward",
        "escore_pct",
        "fracao_nao_financeira_treino_pct",
        "limiar_pct",
        "n_acima_do_dobro_da_base",
        "n_acima_do_limiar",
        "n_companhias_avaliadas",
        "n_hoje_lucrativas",
        "n_ja_em_prejuizo",
        "n_observacoes",
        "n_observacoes_treino",
        "taxa_base_painel_pct",
        "taxa_historica_prejuizo_pct",
    }
)


def _coletar_evidencias(
    objeto: Any, rotulos: set[str], valores: list[float], chave: str | None = None
) -> None:
    """Percorre o resultado de uma ferramenta separando rótulo de valor.

    Conhece as quatro formas que as ferramentas devolvem: triagem de cobertura,
    lista de trechos, resultado de SQL (`colunas`/`linhas`) e indicadores. O
    texto do trecho recuperado entra apenas como **fonte de números** — é lá que
    mora o valor gerencial do release, que o painel não tem.
    """
    if objeto is None or isinstance(objeto, bool):
        return
    if isinstance(objeto, (int, float)):
        if chave not in CHAVES_SEM_VALOR:
            valores.append(float(objeto))
        return
    if isinstance(objeto, str):
        if chave in CHAVES_DE_ROTULO and objeto.strip():
            rotulos.add(_normalizar(objeto))
        if chave in ("texto", "sql") or chave is None:
            for numero in extrair_numeros_ptbr_tipados(objeto[:8000]):
                valores.append(numero.valor)
        return
    if isinstance(objeto, Mapping):
        for nome, valor in objeto.items():
            _coletar_evidencias(valor, rotulos, valores, str(nome))
        return
    if isinstance(objeto, (list, tuple, set)):
        if chave == "linhas":
            # Linhas de SQL são listas de células sem chave. Cada célula de
            # texto é rótulo citável — é ali que aparecem `cd_cvm`, trimestre e
            # conceito quando o agente monta a própria consulta. Sem este ramo,
            # uma resposta construída só por `consultar_cvm` teria **nenhum**
            # rótulo, e toda citação legítima dela seria acusada de inventada.
            for linha in objeto:
                celulas = linha if isinstance(linha, (list, tuple)) else [linha]
                for celula in celulas:
                    if isinstance(celula, str) and celula.strip():
                        rotulos.add(_normalizar(celula))
                    _coletar_evidencias(celula, rotulos, valores, None)
            return
        for item in objeto:
            _coletar_evidencias(item, rotulos, valores, chave)
        return


# --------------------------------------------------------------------------- #
# Números com rótulo: a métrica que governa cada valor devolvido
# --------------------------------------------------------------------------- #

_NOMES_GRUPOS: frozenset[str] = frozenset(_GRUPOS_METRICAS)

# Unidades que o tokenizador do caminho livre mantém e que aqui casariam rótulo
# por acaso. Medido na rodada real de 19/10: o trecho do Itaú abre em
# "juros\nR$ 17,2 bi", o rótulo "Despesas não decorrentes de" ficou no chunk
# anterior, e o único token do número era "bi". Uma resposta que escrevesse
# "17,2 bi" o casaria pela unidade.
_TOKENS_DE_UNIDADE: frozenset[str] = frozenset(
    {"bi", "bn", "brl", "mi", "mil", "mm", "reais", "tri"}
)


@dataclass(frozen=True)
class FatoRotulado:
    """Um número devolvido por ferramenta e os tokens da métrica dele."""

    valor: float
    tokens: frozenset[str]
    ferramenta: str = ""


def _tokens_do_rotulo(texto: str) -> frozenset[str]:
    """Tokens de métrica do caminho livre, lendo `lucro_liquido` como duas palavras."""
    return frozenset(
        _tokens_metrica_grounding(str(texto or "").replace("_", " "))
        - _TOKENS_DE_UNIDADE
    )


def _fatos_rotulados(
    objeto: Any, caminho: tuple[str, ...] = ()
) -> Iterator[tuple[float, frozenset[str]]]:
    """Percorre o resultado de uma ferramenta pareando número e rótulo.

    Três formas, cada uma com o rótulo onde ele mora:

    * **texto de trecho** (`buscar_trechos`): o parser de fatos do caminho
      livre (`fatos_numericos_do_chunk`), que já pareia célula e rótulo de
      linha, título de seção e legenda de unidade. Um segundo interpretador
      divergiria da guarda do caminho livre;
    * **resultado de SQL** (`consultar_cvm`): as células de texto da linha e o
      nome da coluna do número; quando a linha não nomeia métrica nenhuma
      (`SELECT valor_reais ... WHERE conceito = 'lucro_liquido'`), os literais
      do próprio SQL;
    * **dicionário** (`calcular_indicadores`, o modelo): o caminho de chaves
      até o número, como `regime_por_porte ativo_minimo_reais`.

    Contagens e percentuais de `CHAVES_SEM_VALOR` ficam de fora, como em
    `_coletar_evidencias`.
    """
    chave = caminho[-1] if caminho else None
    if objeto is None or isinstance(objeto, bool):
        return
    if isinstance(objeto, (int, float)):
        if chave not in CHAVES_SEM_VALOR:
            yield float(objeto), _tokens_do_rotulo(" ".join(caminho))
        return
    if isinstance(objeto, str):
        if chave == "texto":
            for numero, tokens, _ in fatos_numericos_do_chunk(
                SimpleNamespace(texto=objeto)
            ):
                yield numero.valor, frozenset(set(tokens) - _TOKENS_DE_UNIDADE)
            yield from _fatos_de_linha_de_tabela(objeto)
            yield from _fatos_de_prosa(objeto)
        return
    if isinstance(objeto, Mapping):
        if "colunas" in objeto and "linhas" in objeto:
            yield from _fatos_rotulados_de_sql(objeto)
            return
        for nome, valor in objeto.items():
            yield from _fatos_rotulados(valor, caminho + (str(nome),))
        return
    if isinstance(objeto, (list, tuple)):
        for item in objeto:
            yield from _fatos_rotulados(item, caminho)


def _fatos_de_linha_de_tabela(texto: str) -> Iterator[tuple[float, frozenset[str]]]:
    """Segunda leitura das linhas de tabela: todas as células de texto rotulam.

    O parser do caminho livre elege como rótulo a PRIMEIRA célula com letra, e
    o OCR às vezes põe ali um marcador de nota. Medido na reexecução das
    rodadas gravadas: `| A4 | Resultado Recorrente Gerencial | 12.317 |` dava
    ao 12.317 o rótulo "A4", sem métrica, e a resposta certa era acusada.
    Mexer no parser mudaria o caminho livre, medido nas 45 congeladas; por isso
    a leitura extra fica aqui e só ACRESCENTA candidatos. Prosa não entra: lá
    o rótulo por oração do parser é mais fino que a linha inteira.
    """
    for linha in texto.splitlines():
        # Linha de tabela markdown, não o cabeçalho contextual do chunk
        # ("[ITAU | itau_release_3T2025 | 3T2025 | págs. 8–10]").
        if not linha.lstrip().startswith("|"):
            continue
        celulas = linha.split("|")
        if len(celulas) < 3:
            continue
        rotulo = " ".join(
            c for c in celulas if c.strip() and not extrair_numeros_ptbr_tipados(c)
        )
        tokens = _tokens_do_rotulo(rotulo)
        if not tokens:
            continue
        for celula in celulas:
            for numero in extrair_numeros_ptbr_tipados(celula):
                yield numero.valor, tokens


def _fatos_de_prosa(texto: str) -> Iterator[tuple[float, frozenset[str]]]:
    """Leitura de rótulo das linhas que o parser do caminho livre pula.

    O parser descarta a oração "modal" e o título markdown, por uma razão de
    lastro: valor hipotético ("meta", "projeção", "não") não fundamenta
    resposta. Mas o regex modal inclui "não", e o nome de métrica do caso que
    criou esta guarda é "Despesas não decorrentes de juros". Em
    "Despesas não decorrentes de juros: R$ 17,2 bi" o número ficava sem fato
    rotulado nenhum, e a guarda aprovava a "margem" de 17,2 bilhões (achado
    A1 da auditoria de 20/10). Aqui a oração rotula os números dela, sem
    filtro modal: o que se pergunta é DE QUE MÉTRICA é o número, não se ele
    sustenta a resposta (isso continua com a RN02 de lastro).

    Mesma granularidade do parser: uma oração por vez, e linha de tabela
    fica com `_fatos_de_linha_de_tabela`.
    """
    for linha in texto.splitlines():
        if linha.lstrip().startswith("|"):
            continue
        for oracao in dividir_em_clausulas(linha, quebrar_linha=False):
            numeros = extrair_numeros_ptbr_tipados(oracao)
            if not numeros:
                continue
            tokens = _tokens_do_rotulo(oracao)
            for numero in numeros:
                yield numero.valor, tokens


def _fatos_rotulados_de_sql(
    resultado: Mapping[str, Any],
) -> Iterator[tuple[float, frozenset[str]]]:
    colunas = [str(c) for c in resultado.get("colunas") or ()]
    literais = " ".join(re.findall(r"'([^']*)'", str(resultado.get("sql") or "")))
    for linha in resultado.get("linhas") or ():
        celulas = linha if isinstance(linha, (list, tuple)) else [linha]
        texto_da_linha = " ".join(c for c in celulas if isinstance(c, str))
        for indice, celula in enumerate(celulas):
            if isinstance(celula, bool) or not isinstance(celula, (int, float)):
                continue
            coluna = colunas[indice] if indice < len(colunas) else ""
            if coluna in CHAVES_SEM_VALOR:
                continue
            tokens = _tokens_do_rotulo(f"{texto_da_linha} {coluna}")
            if not tokens & _NOMES_GRUPOS:
                # O rótulo está no filtro, não na linha. Só neste caso: com
                # `conceito IN ('lucro…', 'ativo_total')` e o conceito na linha,
                # somar os literais daria à linha do lucro o rótulo do ativo.
                tokens = tokens | _tokens_do_rotulo(literais)
            yield float(celula), tokens


def _normalizar(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", str(texto or ""))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


# --------------------------------------------------------------------------- #
# Ferramentas no formato do CrewAI
# --------------------------------------------------------------------------- #


def _serializar(objeto: Any) -> str:
    return json.dumps(objeto, ensure_ascii=False, default=str)


class _FerramentaBase(BaseTool):
    """Base das quatro ferramentas expostas ao agente.

    Erro de ferramenta **não** derruba o laço: vira texto de observação. Um
    agente que recebe "esta consulta foi recusada porque…" corrige a consulta;
    uma exceção propagada perderia as 14 perguntas seguintes por causa de uma.
    """

    ferramentas: Any = None

    def _chamar(self, nome: str, **argumentos: Any) -> str:
        try:
            resultado = self.ferramentas.executar(nome, **argumentos)
        except TetoChamadasExcedidoError as erro:
            return _serializar(
                {
                    "erro": "teto_de_chamadas_atingido",
                    "detalhe": str(erro),
                    "instrucao": (
                        "Não há mais orçamento de ferramenta para esta "
                        "pergunta. Responda AGORA com a melhor evidência já "
                        "reunida e marque a resposta como parcial."
                    ),
                }
            )
        except Exception as erro:  # erro de uso, não de infraestrutura
            self.ferramentas.registrar_falha(
                nome, argumentos, f"{type(erro).__name__}: {erro}"
            )
            return _serializar(
                {"erro": f"{type(erro).__name__}", "detalhe": str(erro)}
            )
        return _serializar(resultado)


class _ArgsVerificarCobertura(BaseModel):
    entidade: str = Field(
        ..., description="nome, apelido, CD_CVM ou a pergunta inteira"
    )
    trimestre: str | None = Field(default=None, description="ex.: 1T2026")


class _ArgsBuscarTrechos(BaseModel):
    pergunta: str = Field(..., description="o que procurar nos releases")
    top_k: int | None = Field(default=None, description="quantos trechos")


class _ArgsConsultarCVM(BaseModel):
    sql: str = Field(..., description="SELECT com LIMIT obrigatório")


class _ArgsCalcularIndicadores(BaseModel):
    cd_cvm: str = Field(..., description="código CVM da companhia")
    trimestre: str | None = Field(default=None, description="ex.: 1T2026")


class FerramentaVerificarCobertura(_FerramentaBase):
    # Esquema declarado à mão porque o inferido a partir da assinatura marca
    # todo parâmetro como obrigatório — inclusive os que têm padrão. O efeito
    # era mudo e caro: a chamada sem `trimestre` era **recusada na validação**,
    # o agente recebia um erro de argumento em vez do dado, e a ferramenta
    # sumia da contagem de custo sem sumir da conta de tokens.
    args_schema: type[BaseModel] = _ArgsVerificarCobertura
    name: str = "verificar_cobertura"
    description: str = (
        "Resolve a companhia por CD_CVM e devolve o estado de cobertura: "
        "'ambas' (corpus e painel), 'so_painel' (arquiva na CVM, sem release "
        "indexado) ou 'nenhuma'. Nome que designa mais de uma companhia devolve "
        "'desambiguacao' preenchido — nesse caso PERGUNTE ao usuário qual delas, "
        "nunca escolha. Argumentos: entidade (texto), trimestre (opcional, "
        "ex.: '1T2026')."
    )

    def _run(self, entidade: str, trimestre: str | None = None) -> str:
        return self._chamar(
            "verificar_cobertura", entidade=entidade, trimestre=trimestre
        )


class FerramentaBuscarTrechos(_FerramentaBase):
    args_schema: type[BaseModel] = _ArgsBuscarTrechos
    name: str = "buscar_trechos"
    description: str = (
        "Recupera trechos do corpus documental (releases dos cinco bancos) com "
        "empresa, documento, trimestre e páginas — os metadados que a citação "
        "obrigatória exige. Argumentos: pergunta (texto), top_k (opcional)."
    )

    def _run(self, pergunta: str, top_k: int | None = None) -> str:
        limite = MAX_TRECHOS if top_k is None else min(int(top_k), MAX_TRECHOS)
        bruto = self._chamar("buscar_trechos", pergunta=pergunta, top_k=limite)
        try:
            trechos = json.loads(bruto)
        except json.JSONDecodeError:
            return bruto
        if not isinstance(trechos, list):
            return bruto
        for trecho in trechos:
            texto = str(trecho.get("texto", ""))
            if len(texto) > MAX_CARACTERES_TRECHO:
                trecho["texto"] = texto[:MAX_CARACTERES_TRECHO] + " […]"
        return _serializar(trechos)


class FerramentaConsultarCVM(_FerramentaBase):
    args_schema: type[BaseModel] = _ArgsConsultarCVM
    name: str = "consultar_cvm"
    description: str = (
        "Executa SELECT somente-leitura sobre a camada semântica do painel da "
        "CVM. Tabelas: fatos_semanticos(cd_cvm, denom_social, trimestre, "
        "conceito, valor_reais, origem), companhias, indicadores, mapa_contas. "
        "Conceitos: lucro_liquido_consolidado, lucro_liquido_controladores, "
        "patrimonio_liquido, ativo_total, receita_intermediacao_financeira. "
        "LIMIT é obrigatório e cd_conta é bloqueado. Argumento: sql (texto)."
    )

    def _run(self, sql: str) -> str:
        return self._chamar("consultar_cvm", sql=sql)


class FerramentaCalcularIndicadores(_FerramentaBase):
    args_schema: type[BaseModel] = _ArgsCalcularIndicadores
    name: str = "calcular_indicadores"
    description: str = (
        "Indicadores materializados (ROE, margem líquida, alavancagem) de uma "
        "companhia, sempre por CD_CVM — nunca por nome. Argumentos: cd_cvm "
        "(texto), trimestre (opcional)."
    )

    def _run(self, cd_cvm: str, trimestre: str | None = None) -> str:
        return self._chamar(
            "calcular_indicadores", cd_cvm=cd_cvm, trimestre=trimestre
        )


class _ArgsConsultarModelo(BaseModel):
    ativo_total_reais: float | None = Field(
        default=None,
        description="ativo total em reais, obtido antes com consultar_cvm (opcional)",
    )
    cd_cvm: str | None = Field(
        default=None,
        description="código CVM; o escore da companhia só existe no modo local (opcional)",
    )


class FerramentaConsultarModelo(_FerramentaBase):
    """O modelo preditivo de prejuízo, lido do artefato agregado (§3.16)."""

    args_schema: type[BaseModel] = _ArgsConsultarModelo
    name: str = FERRAMENTA_MODELO
    description: str = (
        "Consulta o modelo preditivo de prejuízo do projeto (classificador "
        "treinado offline no painel da CVM). Devolve o AUC de validação, o "
        "panorama agregado do mercado e a taxa HISTÓRICA de prejuízo por porte "
        "de ativo. Se receber ativo_total_reais (obtenha antes com "
        "consultar_cvm, conceito 'ativo_total'), diz em que faixa de porte esse "
        "valor cai. Escore de companhia nomeada só no modo local; na instância "
        "pública ele não é exposto (RN07). Argumentos: ativo_total_reais "
        "(número, opcional), cd_cvm (texto, opcional)."
    )

    def _run(
        self, ativo_total_reais: float | None = None, cd_cvm: str | None = None
    ) -> str:
        return self._chamar(
            FERRAMENTA_MODELO, ativo_total_reais=ativo_total_reais, cd_cvm=cd_cvm
        )


CLASSES_DE_FERRAMENTA: Mapping[str, type[_FerramentaBase]] = {
    "verificar_cobertura": FerramentaVerificarCobertura,
    "buscar_trechos": FerramentaBuscarTrechos,
    "consultar_cvm": FerramentaConsultarCVM,
    "calcular_indicadores": FerramentaCalcularIndicadores,
    FERRAMENTA_MODELO: FerramentaConsultarModelo,
}


def construir_ferramentas(
    ferramentas: FerramentasDoAgente,
    nomes: Sequence[str] | None = None,
) -> list[BaseTool]:
    """Instancia as ferramentas do CrewAI a partir da caixa do projeto.

    Sem `nomes`, usa o conjunto do próprio envelope (`ferramentas.nomes`): as
    quatro do experimento, ou as cinco do produto. A fábrica é a porta única, e
    ela recusa `FERRAMENTAS_PROIBIDAS` por nome (RN07). Um nome sem classe
    também não passa: só existem classes para `FERRAMENTAS_DO_PRODUTO`.
    """
    nomes = ferramentas.nomes if nomes is None else tuple(nomes)
    proibidas = sorted(set(nomes) & set(FERRAMENTAS_PROIBIDAS))
    if proibidas:
        raise ValueError(
            f"ferramenta proibida na caixa do agente (RN07): {proibidas}"
        )
    desconhecidas = sorted(set(nomes) - set(CLASSES_DE_FERRAMENTA))
    if desconhecidas:
        raise ValueError(f"ferramenta sem implementação: {desconhecidas}")
    return [CLASSES_DE_FERRAMENTA[nome](ferramentas=ferramentas) for nome in nomes]


# --------------------------------------------------------------------------- #
# Prompts — os mesmos para o braço A e para o Investigador do braço B
# --------------------------------------------------------------------------- #

# a1 → a2 (2026-08-12): a regra do lastro numérico virou **mecânica** e o prompt
# ganhou um exemplo completo do protocolo ReAct. Motivo medido no braço A: em 14
# das 15 perguntas o agente chamou só `verificar_cobertura` — que não devolve
# valor nenhum — e pulou para `Final Answer` com número e citação inventados.
#
# a3 → a4 (2026-10-19): o prompt do Auditor ganhou a regra "confirmar é
# conferir cada fonte citada", verificada em código (`fontes_sem_reconsulta`),
# e a RN02 dos agentes passou a conferir o rótulo do número
# (`valores_com_rotulo_trocado`). Dois achados da rodada real do chat: um
# `confirma` do modelo sem consultar o modelo, e uma "margem financeira" que
# era despesa. O prompt do Investigador não mudou. Muda o braço B (e a RN02 do
# A): as rodadas `a3` em `artefatos/resultados_agentes/` ficam históricas.
VERSAO_PROMPT_AGENTES = "a4"

ESQUEMA_INVESTIGADOR = """{
  "cobertura": "ambas | so_painel | nenhuma | ambigua",
  "comportamento": "resposta_completa | resposta_parcial_marcada | recusa | pergunta_de_desambiguacao | divergencia_registrada | registro_sem_juizo",
  "motivo_recusa": "n/a | fora_do_corpus | periodo_ausente",
  "bases": ["contabil_consolidado", "contabil_controladores", "gerencial"],
  "afirmacao": "a resposta ao usuário, em português, sem raciocínio",
  "citacoes": ["CVM · RAZÃO SOCIAL (CD_CVM 000000) · 1T2026 · conceito", "release itau_release_2T2025 · ITAU · 2T2025 · p. 5"],
  "rastro": ["passo 1: o que consultei e por quê", "passo 2: ..."]
}"""

REGRAS_COMUNS = """REGRAS INVIOLÁVEIS (verificadas por código depois da sua resposta):
- RN01: todo valor apresentado carrega citação com companhia/documento, trimestre e origem. Resposta com número e sem citação é descartada e vira recusa registrada.
- RN02: nada de memória própria. Se a evidência recuperada não sustenta, diga que não sustenta.
- REGRA MECÂNICA DO LASTRO (a mais violada, e a que mais custa): 'verificar_cobertura' NÃO devolve valor nenhum — ela só informa em qual camada a companhia existe. Portanto, SEMPRE que a sua resposta final tiver 'bases' não vazio, 'citacoes' não vazio, ou qualquer número na 'afirmacao', você precisa ter executado ANTES, nesta mesma execução, PELO MENOS UMA ação 'consultar_cvm' (número contábil arquivado), 'buscar_trechos' (número gerencial ou frase da administração) ou 'calcular_indicadores' — e ter lido a linha 'Observation:' que a ferramenta devolveu. Uma execução que chamou SÓ 'verificar_cobertura' pode produzir apenas: recusa, pergunta de desambiguação, ou uma resposta sem número e sem citação.
- Ir de 'verificar_cobertura' direto para 'Final Answer' com um número é o erro que o código detecta e descarta: a resposta inteira vira recusa registrada e todo o seu trabalho é perdido. Se você perceber que escreveu um número que nenhuma 'Observation:' desta conversa devolveu, volte e chame a ferramenta.
- Nunca escreva você mesmo a linha 'Observation:' — a observação é o que a ferramenta responde, não o que você imagina que ela responderia.
- NOTAÇÃO OBRIGATÓRIA: os marcadores são exatamente 'Thought:', 'Action:', 'Action Input:' e 'Final Answer:', em texto puro, cada um no começo da própria linha, com dois-pontos. NÃO use tags XML ('<Thought>', '<Action>'), não use negrito ('**Action:**'), não use cerca de código e não traduza os marcadores. Outra notação não é lida pelo executor: a ação não acontece, e o que você escrever depois dela é tratado como evidência inventada e descartado.
- RN05: proibido recomendar investimento, sugerir compra/venda, projetar preço ou qualificar uma decisão como boa ou ruim. O verbo é registrar, nunca avaliar.
- RN10: valor de 4º trimestre é derivado (DFP anual menos ITR acumulado do 3T). Se a origem vier 'derivado', diga isso na afirmação.
- RN11: nome que resolve para mais de uma companhia gera PERGUNTA de desambiguação com as razões sociais e os CD_CVM. Nunca escolha a mais provável e não apresente valor antes da escolha.
- RN12: 'não sei' tem três valores. 'ambas' responde completo; 'so_painel' dá o número contábil E diz explicitamente que não há release indexado, logo nada pode ser dito sobre o que a administração declarou; 'nenhuma' recusa NOMEANDO a ausência nas duas camadas (painel da CVM e corpus de releases).
- O número gerencial do release e o número arquivado na CVM são definições diferentes. Apresente os dois com o rótulo de cada um; não eleja um como 'o' lucro.

CONTENÇÃO: você tem um teto de chamadas de ferramenta e de iterações. Se uma
ferramenta responder que o teto foi atingido, responda imediatamente com a
evidência já reunida e use comportamento 'resposta_parcial_marcada'."""

# Exemplo em contexto do protocolo textual do CrewAI.
#
# **Por que um exemplo, e não mais uma frase de regra.** O executor do CrewAI é
# textual (`Thought:` / `Action:` / `Observation:` / `Final Answer:`) porque
# `ProvedorLLM.gerar_texto` não expõe *function calling* — ver
# `LLMPonte.supports_function_calling`. Protocolo textual depende de o modelo
# escolher segui-lo, e um modelo de tier barato segue muito melhor com **um
# turno completo em contexto** do que com a descrição da regra. Medido no braço
# A de 2026-08-12: com regra sem exemplo, 14 das 15 perguntas pularam de
# `verificar_cobertura` direto para `Final Answer`.
#
# A companhia, o código e o valor são **fictícios de propósito** (999999, "Banco
# Exemplo"): um exemplo com número real vazaria resposta para as perguntas do
# conjunto e o experimento passaria a medir o exemplo. O contraexemplo no fim é
# tão importante quanto o exemplo — é o erro concreto que se quer evitar.
EXEMPLO_REACT = """EXEMPLO DO FORMATO CORRETO (companhia e números FICTÍCIOS — jamais reutilize estes valores; servem só para fixar o formato):

Thought: primeiro preciso saber em quais camadas essa companhia existe.
Action: verificar_cobertura
Action Input: {"entidade": "Banco Exemplo", "trimestre": "2T2025"}
Observation: {"entidades": [{"termo": "Banco Exemplo", "cobertura": {"estado": "ambas", "cd_cvm": "999999", "denom_social": "BANCO EXEMPLO S.A.", "trimestres_painel": ["2T2025"], "trimestres_corpus": ["2T2025"]}}], "desambiguacao": []}
Thought: estado 'ambas' e CD_CVM 999999. A cobertura NÃO me deu valor nenhum, então ainda não posso escrever número: preciso consultar o painel.
Action: consultar_cvm
Action Input: {"sql": "SELECT trimestre, conceito, valor_reais FROM fatos_semanticos WHERE cd_cvm = '999999' AND trimestre = '2T2025' AND conceito = 'patrimonio_liquido' LIMIT 5"}
Observation: {"colunas": ["trimestre", "conceito", "valor_reais"], "linhas": [["2T2025", "patrimonio_liquido", 12345678.0]], "total_linhas": 1}
Thought: agora existe um valor devolvido por ferramenta nesta conversa, e é ele que eu posso escrever.
Final Answer: {"cobertura": "ambas", "comportamento": "resposta_completa", "motivo_recusa": "n/a", "bases": ["contabil_consolidado"], "afirmacao": "O patrimônio líquido contábil do BANCO EXEMPLO S.A. (CD_CVM 999999) no 2T2025 foi de R$ 12,3 milhões.", "citacoes": ["CVM · BANCO EXEMPLO S.A. (CD_CVM 999999) · 2T2025 · patrimonio_liquido"], "rastro": ["passo 1: verifiquei a cobertura", "passo 2: consultei fatos_semanticos e li o valor devolvido pela ferramenta"]}

CONTRAEXEMPLO — é exatamente isto que o código descarta:

Thought: primeiro a cobertura.
Action: verificar_cobertura
Action Input: {"entidade": "Banco Exemplo"}
Observation: {"entidades": [{"termo": "Banco Exemplo", "cobertura": {"estado": "ambas", "cd_cvm": "999999"}}], "desambiguacao": []}
Final Answer: {"afirmacao": "O patrimônio líquido foi de R$ 12,3 milhões.", "citacoes": ["CVM · ... · patrimonio_liquido"], ...}

Está errado porque nenhuma 'Observation:' desta conversa devolveu 12,3 milhões: o número veio da memória do modelo. A resposta inteira é descartada e vira recusa registrada."""

OBJETIVO_INVESTIGADOR = (
    "Responder à pergunta usando exclusivamente as ferramentas, e registrar "
    "em 'rastro' como você chegou lá."
)

HISTORIA_INVESTIGADOR = (
    "Você é analista de research financeiro. Trabalha só com o que as "
    "ferramentas devolvem: o painel contábil da CVM e o corpus de releases de "
    "cinco bancos brasileiros. Você sabe que o mesmo 'lucro líquido' tem "
    "leituras diferentes (gerencial do release, consolidado arquivado, "
    "atribuível aos controladores) e nunca apresenta um número sem dizer de "
    "qual definição ele é."
)

OBJETIVO_AUDITOR = (
    "Tentar FALSIFICAR a afirmação recebida, reexecutando as consultas por "
    "conta própria, e emitir um dos três vereditos."
)

HISTORIA_AUDITOR = (
    "Você audita afirmações financeiras. Você recebe a afirmação e as citações "
    "— e nada mais: não sabe como quem a produziu chegou lá, e é justamente por "
    "isso que a sua conferência acrescenta informação. Você não reescreve a "
    "resposta e não julga estilo; você verifica se a evidência existe e se ela "
    "diz o que a afirmação diz."
)

ESQUEMA_AUDITOR = """{
  "veredito": "confirma | contesta | nao_reproduz",
  "justificativa": "por que, em uma ou duas frases",
  "contraevidencia": ["obrigatório quando o veredito é 'contesta': o que você achou e onde"],
  "citacoes": ["as fontes que VOCÊ consultou"]
}"""


# Bloco ESTÁVEL da instrução do Investigador: idêntico byte a byte em todas as
# perguntas. Fica separado — e vem ANTES da pergunta em `instrucao_investigador`
# — porque o cache de prompt dos provedores casa por PREFIXO.
#
# Medido em 2026-08-14: na ordem antiga a pergunta ocupava os primeiros ~56
# caracteres e empurrava 5.441 caracteres estáveis (83% do bloco, ~1.360 tokens)
# para depois dela; como o prefixo divergia no primeiro token, NADA era
# reaproveitado entre perguntas. Com o estável na frente, essa fatia passa a ser
# cacheável nas 15 perguntas — na DeepSeek o cache-hit custa US$0,0028/M contra
# US$0,14/M de miss (50×), e ele é automático, sem parâmetro.
#
# Consequência ao editar: qualquer texto variável (pergunta, contexto, data)
# colocado aqui dentro derruba o cache de todas as chamadas seguintes. O que
# varia entra DEPOIS deste bloco.
INSTRUCAO_INVESTIGADOR_ESTAVEL = (
    "Use as ferramentas para responder. Comece SEMPRE por "
    "verificar_cobertura, porque o que existe em cada camada muda o tipo da "
    "resposta — e depois, se a resposta for trazer qualquer número, SIGA com "
    "consultar_cvm (contábil) e/ou buscar_trechos (gerencial). A cobertura "
    "sozinha nunca basta para dar um valor.\n\n"
    f"{REGRAS_COMUNS}\n\n"
    f"{EXEMPLO_REACT}\n\n"
    "FORMATO DA RESPOSTA FINAL (a falha mais frequente depois do lastro):\n"
    "- Depois de 'Final Answer:' vem UM objeto JSON e nada mais: sem cerca de "
    "código, sem ```json, sem comentário antes ou depois, sem texto de "
    "despedida. O primeiro caractere é '{' e o último é '}'.\n"
    "- Todas as chaves do esquema são obrigatórias, mesmo vazias: 'bases' e "
    "'citacoes' viram [] quando não há número; 'motivo_recusa' vira 'n/a'.\n"
    "- Os valores de 'cobertura' e 'comportamento' são exatamente um dos "
    "listados no esquema, em minúsculas, sem inventar variante.\n"
    "- Aspas duplas em todas as chaves e strings; nada de vírgula sobrando "
    "antes de '}' ou ']'.\n\n"
    "Responda com UM objeto JSON, e nada fora dele, neste formato:\n"
    f"{ESQUEMA_INVESTIGADOR}\n\n"
    "Como preencher os campos de classificação:\n"
    "- 'cobertura': 'ambigua' quando o nome designa mais de uma companhia; "
    "senão o estado devolvido por verificar_cobertura.\n"
    "- 'motivo_recusa': 'fora_do_corpus' quando falta o release (inclusive "
    "no estado 'so_painel', que responde e não recusa); 'periodo_ausente' "
    "quando a companhia existe e o trimestre pedido não; 'n/a' quando nada "
    "falta.\n"
    "- 'bases': quais bases o seu número usa — 'contabil_consolidado', "
    "'contabil_controladores' (as duas do arquivado na CVM) e 'gerencial' "
    "(a do release). Lista vazia quando a resposta não traz número.\n\n"
    "'afirmacao' é o que o usuário lê: sem 'Thought', sem descrição de "
    "passos. 'rastro' é o registro interno de como você chegou lá."
)


# Parágrafo só do produto, quando a caixa tem o modelo (§3.16). Fica DEPOIS do
# bloco estável, para não mexer no prefixo cacheável nem no prompt do
# experimento, que segue byte a byte igual.
INSTRUCAO_MODELO = (
    "FERRAMENTA DO MODELO PREDITIVO — 'consultar_modelo_prejuizo':\n"
    "- Use-a quando a pergunta pedir o que o modelo de prejuízo do projeto diz: "
    "o panorama do mercado, o desempenho do modelo ou o regime histórico de "
    "prejuízo por porte de ativo.\n"
    "- Para situar uma companhia num porte, PRIMEIRO obtenha o ativo total "
    "dela com consultar_cvm (conceito 'ativo_total'), DEPOIS passe esse valor "
    "em reais como 'ativo_total_reais'. São duas ações, nessa ordem.\n"
    "- A taxa por porte é a frequência histórica de prejuízo de TODAS as "
    "companhias da faixa. Nunca a escreva como chance, risco ou previsão de "
    "prejuízo de uma companhia nomeada (RN07). Escreva, por exemplo: "
    "'companhias com ativo nessa faixa tiveram prejuízo em X% dos trimestres "
    "do painel'.\n"
    "- Cite como: 'Modelo preditivo · panorama <trimestre> · regime por "
    "porte'. Os percentuais vêm da ferramenta; não os arredonde para outro "
    "valor."
)


def instrucao_investigador(pergunta: str, *, com_modelo: bool = False) -> str:
    """A tarefa do Investigador (e do agente único do braço A).

    A pergunta vem no FIM, depois do bloco estável — ver
    `INSTRUCAO_INVESTIGADOR_ESTAVEL` para o porquê (cache por prefixo).
    `com_modelo` acrescenta `INSTRUCAO_MODELO`, só quando a caixa do agente
    tem a ferramenta do modelo (o produto, nunca o experimento).
    """
    extra = f"{INSTRUCAO_MODELO}\n\n" if com_modelo else ""
    return (
        f"{INSTRUCAO_INVESTIGADOR_ESTAVEL}\n\n"
        f"{extra}"
        "=== A PERGUNTA A RESPONDER ===\n"
        f"PERGUNTA DO USUÁRIO: {pergunta}"
    )


def instrucao_auditor(contexto: "ContextoAuditor", *, com_modelo: bool = False) -> str:
    """A tarefa do Auditor — montada **por código** a partir do contexto filtrado.

    Nada de "ignore o raciocínio anterior": o raciocínio simplesmente não está
    aqui. O texto abaixo é construído campo a campo a partir de
    `CAMPOS_CONTEXTO_AUDITOR`, e é o único caminho pelo qual algo do
    Investigador chega ao Auditor.

    `com_modelo` nomeia a ferramenta do modelo entre as de dado, só quando a
    caixa do Auditor a tem (o produto, nunca o experimento).
    """
    citacoes = "\n".join(f"- {c}" for c in contexto.citacoes) or "- (nenhuma)"
    de_dado = (
        "consultar_cvm, buscar_trechos, calcular_indicadores ou "
        "consultar_modelo_prejuizo"
        if com_modelo
        else "consultar_cvm, buscar_trechos ou calcular_indicadores"
    )
    regra_modelo = (
        "; citação do modelo preditivo → consultar_modelo_prejuizo"
        if com_modelo
        else ""
    )
    return (
        "Uma afirmação foi produzida por outro analista, a partir das MESMAS "
        "ferramentas que você tem. Você recebe a afirmação e as citações — e "
        "mais nada. Você não tem acesso ao caminho que ele percorreu, e não "
        "deve supô-lo.\n\n"
        f"PERGUNTA ORIGINAL: {contexto.pergunta}\n\n"
        f"AFIRMAÇÃO A AUDITAR:\n{contexto.afirmacao}\n\n"
        f"CITAÇÕES APRESENTADAS:\n{citacoes}\n\n"
        "Reexecute as consultas por conta própria e emita um veredito:\n"
        "- 'confirma': você reproduziu a evidência e ela sustenta a afirmação;\n"
        "- 'contesta': você achou evidência que a contradiz — cite-a;\n"
        "- 'nao_reproduz': você não conseguiu reproduzir (a evidência citada "
        "não apareceu, a consulta falhou, o teto foi atingido). Não é o mesmo "
        "que 'contesta': é ausência de confirmação, não presença de "
        "contradição.\n\n"
        # ATENÇÃO ao editar: nenhum literal de `MARCADORES_RASTRO` pode entrar
        # neste texto. A mensagem inteira que vai ao Auditor passa por
        # `conferir_isolamento`, e um marcador de protocolo aqui — mesmo escrito
        # como exemplo didático — é indistinguível de rastro do Investigador
        # vazando. Por isso o Auditor **não** recebe o `EXEMPLO_REACT`: a regra
        # abaixo é descrita em prosa, sem citar o protocolo textualmente.
        "REGRA MECÂNICA DA CONFERÊNCIA: verificar_cobertura não devolve valor "
        "nenhum — ela só diz em que camada a companhia existe. Para emitir "
        "'confirma' ou 'contesta' você PRECISA ter executado pelo menos uma "
        f"consulta de dado ({de_dado}) e ter lido o que ela devolveu. Sem "
        "nenhuma consulta de dado, o único veredito honesto é 'nao_reproduz' — "
        "e é ele que o código registrará no seu lugar.\n\n"
        "CONFIRMAR É CONFERIR CADA FONTE CITADA: para emitir 'confirma', "
        "reconsulte cada tipo de fonte que aparece nas citações — citação de "
        "release (com página) → buscar_trechos; citação da CVM (com CD_CVM) → "
        f"consultar_cvm ou calcular_indicadores{regra_modelo}. Confirmar uma "
        "parte da afirmação sem reconsultar a fonte dela é carimbar, e o código "
        "registrará 'nao_reproduz' no seu lugar.\n\n"
        "Não reescreva a resposta e não recomende nada (RN05).\n\n"
        "Responda com UM objeto JSON, e nada fora dele:\n"
        f"{ESQUEMA_AUDITOR}"
    )


# --------------------------------------------------------------------------- #
# Gate de correção: o agente que publica dado sem ter consultado dado (5.9.5)
# --------------------------------------------------------------------------- #

# As três ferramentas que devolvem **valor**. `verificar_cobertura` fica de fora
# de propósito: ela responde "em qual camada a companhia existe" e nunca um
# número. Foi essa confusão que produziu o achado do braço A — o agente lia a
# cobertura, concluía que "sabia" e escrevia o valor de memória.
FERRAMENTAS_DE_DADO: frozenset[str] = frozenset(
    # O modelo devolve valores (taxas, contagens, AUC) e é dado no mesmo
    # sentido: uma resposta só sobre o panorama do modelo não respondeu de
    # memória. No experimento ele nunca é chamado, então nada muda lá.
    {"buscar_trechos", "consultar_cvm", "calcular_indicadores", FERRAMENTA_MODELO}
)

# Desfechos da rodada corretiva, registrados na saída para a RNF08.
CORRECAO_NAO_NECESSARIA = "nao_necessaria"
CORRECAO_BEM_SUCEDIDA = "corrigida"
CORRECAO_FALHOU = "falhou"
CORRECAO_CORTADA_POR_TETO = "cortada_por_teto"

# Comportamentos que, por definição, não publicam dado — e portanto não exigem
# consulta de dado. Recusar ou pedir desambiguação depois de só verificar a
# cobertura é o comportamento **correto**, e cobrar uma consulta aqui gastaria
# uma chamada para confirmar uma ausência já estabelecida.
COMPORTAMENTOS_SEM_DADO: frozenset[str] = frozenset(
    {COMPORTAMENTO_RECUSA, COMPORTAMENTO_DESAMBIGUACAO}
)


def consultou_ferramenta_de_dado(ferramentas: "FerramentasDoAgente") -> bool:
    """Houve, nesta execução, pelo menos uma consulta de dado bem-sucedida?

    Chamada que **falhou** não conta: uma consulta recusada pela lista branca da
    RN04 não devolveu valor algum, e tratá-la como lastro reabriria exatamente a
    porta que este gate fecha.
    """
    return any(
        c.ferramenta in FERRAMENTAS_DE_DADO and c.erro is None
        for c in ferramentas.chamadas
    )


def declara_dado(saida: "SaidaInvestigador") -> bool:
    """A saída publica dado — número, base contábil ou citação de fonte?

    Três sinais, em ordem de força: valor monetário no texto, `bases` declarada,
    e citação apresentada. Recusa e pergunta de desambiguação **sem** valor e
    **sem** base não contam, mesmo que citem a triagem de cobertura: são as duas
    respostas que a cobertura sozinha já sustenta.
    """
    tem_valor = bool(valores_monetarios_do_texto(saida.afirmacao))
    if tem_valor or saida.bases:
        return True
    if saida.comportamento in COMPORTAMENTOS_SEM_DADO:
        return False
    return bool(saida.citacoes)


def precisa_correcao_de_dado(
    saida: "SaidaInvestigador", ferramentas: "FerramentasDoAgente"
) -> bool:
    """O agente publicou dado sem ter consultado nenhuma ferramenta de dado?

    Este é o gate de 5.9.5 que **antecede** a conversão em recusa. O achado do
    braço A (2026-08-12) é que RN01/RN02 pegavam 11 de 15 respostas e as
    convertiam em recusa registrada — a rede de segurança fazia o trabalho que a
    disciplina do agente deveria fazer, e A, B e C empatavam porque nenhum braço
    com LLM chegava a usar as ferramentas de dado. Converter direto em recusa é
    correto do ponto de vista do usuário e **inútil** do ponto de vista da
    medição: mede o prompt, não a orquestração.

    Quando o teto já foi atingido não há correção a fazer: não sobrou orçamento,
    e a resposta correta é a parcial marcada — não um segundo tiro sem munição.
    """
    if saida.teto_iteracoes or saida.teto_ferramenta:
        return False
    if not declara_dado(saida):
        return False
    return not consultou_ferramenta_de_dado(ferramentas)


PREAMBULO_CORRETIVO = (
    "CORREÇÃO OBRIGATÓRIA — LEIA ANTES DE QUALQUER COISA.\n\n"
    "Na sua tentativa anterior você apresentou valor, base ou citação sem ter "
    "chamado NENHUMA ferramenta de dado. 'verificar_cobertura' não devolve "
    "valor: ela só diz em que camada a companhia existe. O número que você "
    "escreveu, portanto, veio da sua memória — e o código o descartou.\n\n"
    "Nesta tentativa, antes de escrever 'Final Answer', execute pelo menos uma "
    "ação 'consultar_cvm' (número contábil arquivado na CVM) ou 'buscar_trechos' "
    "(número gerencial ou frase da administração no release) e use SOMENTE os "
    "valores que aparecerem na linha 'Observation:' devolvida pela ferramenta.\n\n"
    "Se, depois de consultar, a evidência não sustentar um número, então a "
    "resposta correta é recusa ou resposta sem número — e ela será aceita. O que "
    "não será aceito é número sem consulta.\n\n"
    "Esta é a sua ÚLTIMA tentativa: não haverá uma terceira.\n\n"
)


def instrucao_corretiva_investigador(pergunta: str, *, com_modelo: bool = False) -> str:
    """A mesma tarefa, precedida da correção — **um** segundo tiro, nunca laço.

    O texto corretivo é montado por código e não repete o rastro anterior: o que
    se reinjeta é a *regra violada*, não o raciocínio da tentativa fracassada.
    """
    return PREAMBULO_CORRETIVO + instrucao_investigador(pergunta, com_modelo=com_modelo)


# --------------------------------------------------------------------------- #
# Confirmar é conferir cada fonte citada (achado da rodada real de 19/10)
# --------------------------------------------------------------------------- #

FONTE_PAINEL = "painel"
FONTE_RELEASE = "release"
FONTE_MODELO = "modelo"
# Citação fora dos três formatos. Nenhuma ferramenta a reconsulta, então um
# `confirma` que a inclua não se sustenta (regra 4 da §4.4: fonte que não se
# classifica não pode isentar a exigência).
FONTE_FORA_DO_FORMATO = "fora_do_formato"

# Que ferramenta reconsulta cada tipo de fonte citável.
FERRAMENTAS_POR_FONTE: dict[str, frozenset[str]] = {
    FONTE_PAINEL: frozenset({"consultar_cvm", "calcular_indicadores"}),
    FONTE_RELEASE: frozenset({"buscar_trechos"}),
    FONTE_MODELO: frozenset({FERRAMENTA_MODELO}),
    FONTE_FORA_DO_FORMATO: frozenset(),
}

DESCRICAO_FONTE: dict[str, str] = {
    FONTE_PAINEL: "painel da CVM (consultar_cvm ou calcular_indicadores)",
    FONTE_RELEASE: "release (buscar_trechos)",
    FONTE_MODELO: "modelo preditivo (consultar_modelo_prejuizo)",
    FONTE_FORA_DO_FORMATO: "citação fora dos formatos reconhecidos",
}

# A ordem decide a citação que casaria com dois padrões: o modelo antes do
# painel, porque o panorama fala "do painel da CVM" e não é o painel.
_PADROES_FONTE: tuple[tuple[str, re.Pattern[str]], ...] = (
    (FONTE_MODELO, re.compile(r"\bmodelo preditivo\b|\bpanorama\b")),
    (FONTE_RELEASE, re.compile(r"\brelease\b|\bp\.\s*\d|\bpag(?:ina)?\.?\s*\d")),
    (FONTE_PAINEL, re.compile(r"\bcvm\b|\bcd_cvm\b|\bfatos_semanticos\b|\bitr\b|\bdfp\b")),
)


def fonte_da_citacao(citacao: str) -> str | None:
    """O tipo de fonte de uma citação, pelos formatos que o prompt fixa.

    `ESQUEMA_INVESTIGADOR` e `INSTRUCAO_MODELO` ditam três formas: "CVM ·
    RAZÃO SOCIAL (CD_CVM …) · trimestre · conceito", "release <documento> ·
    EMPRESA · trimestre · p. N" e "Modelo preditivo · panorama <trimestre> ·
    regime por porte". Devolve o primeiro tipo pela ordem de
    `_PADROES_FONTE`, ou `None`. Quem decide é `fontes_da_citacao`, que
    devolve todos.
    """
    normalizada = _normalizar(citacao)
    for fonte, padrao in _PADROES_FONTE:
        if padrao.search(normalizada):
            return fonte
    return None


def fontes_da_citacao(citacao: str) -> frozenset[str]:
    """Todos os tipos de fonte que uma citação invoca.

    Citação mista ("release … p. 8 e CVM … CD_CVM …") exige as duas
    reconsultas, não a primeira que casar. A exceção é o modelo, cuja citação
    fala "do painel da CVM" sem ser o painel. Citação que não casa com formato
    nenhum vira `FONTE_FORA_DO_FORMATO`, que nenhuma ferramenta reconsulta.
    """
    normalizada = _normalizar(citacao)
    casadas = {f for f, padrao in _PADROES_FONTE if padrao.search(normalizada)}
    if FONTE_MODELO in casadas:
        return frozenset({FONTE_MODELO})
    return frozenset(casadas or {FONTE_FORA_DO_FORMATO})


def fontes_citadas(citacoes: Sequence[str]) -> frozenset[str]:
    return frozenset(
        fonte
        for citacao in citacoes
        if str(citacao).strip()
        for fonte in fontes_da_citacao(citacao)
    )


def fontes_reconsultadas(ferramentas: "FerramentasDoAgente") -> frozenset[str]:
    """Os tipos de fonte que esta caixa consultou com sucesso."""
    feitas = {c.ferramenta for c in ferramentas.chamadas if c.erro is None}
    return frozenset(
        fonte for fonte, nomes in FERRAMENTAS_POR_FONTE.items() if feitas & nomes
    )


def fontes_sem_reconsulta(
    contexto: "ContextoAuditor", ferramentas: "FerramentasDoAgente"
) -> frozenset[str]:
    """Fontes citadas na afirmação que o Auditor não reconsultou.

    Lê só o que o Auditor tem: as citações do `ContextoAuditor` e as chamadas
    da caixa dele. Nada do rastro do Investigador entra na decisão.
    """
    return fontes_citadas(contexto.citacoes) - fontes_reconsultadas(ferramentas)


def _fontes_que_ele_pode_reconsultar(
    fontes: frozenset[str], ferramentas: "FerramentasDoAgente"
) -> frozenset[str]:
    """Das fontes faltantes, as que a caixa do Auditor alcança.

    No experimento a caixa não tem o modelo: uma citação do modelo ali é
    citação que nenhuma ferramenta reconsulta, e pedir a rodada corretiva
    seria pagar por um tiro impossível.
    """
    disponiveis = set(ferramentas.nomes)
    return frozenset(f for f in fontes if FERRAMENTAS_POR_FONTE[f] & disponiveis)


def instrucao_corretiva_auditor(
    contexto: "ContextoAuditor",
    *,
    faltantes: frozenset[str] = frozenset(),
    com_modelo: bool = False,
) -> str:
    """Idem para o Auditor — que também não pode confirmar sem reexecutar.

    Dois motivos de correção, cada um com o próprio texto: veredito sem
    nenhuma consulta de dado, ou `confirma` sem reconsultar alguma fonte
    citada (`faltantes`). Os dois textos nomeiam só o que o próprio Auditor
    vê: as citações do contexto e as ferramentas dele.

    Vale aqui a mesma restrição de `instrucao_auditor`: nenhum literal de
    `MARCADORES_RASTRO` no texto, porque a mensagem inteira ainda é uma mensagem
    destinada ao Auditor e passa pela mesma guarda de isolamento.
    """
    if faltantes:
        lista = "; ".join(DESCRICAO_FONTE[f] for f in sorted(faltantes))
        motivo = (
            "Na sua tentativa anterior você confirmou a afirmação sem "
            "reconsultar todas as fontes que ela cita. Faltou reconsultar: "
            f"{lista}.\n\n"
            "Nesta tentativa, reconsulte cada fonte que falta antes de emitir o "
            "veredito. "
        )
    else:
        motivo = (
            "Na sua tentativa anterior você emitiu um veredito sem ter executado "
            "nenhuma consulta de dado. Conferência sem reexecução não é "
            "conferência: verificar_cobertura não devolve valor nenhum.\n\n"
            "Nesta tentativa, execute pelo menos uma consulta com consultar_cvm, "
            "buscar_trechos ou calcular_indicadores antes de emitir o veredito. "
        )
    return (
        "CORREÇÃO OBRIGATÓRIA — LEIA ANTES DE QUALQUER COISA.\n\n"
        f"{motivo}"
        "Se você não conseguir reproduzir a evidência citada, o veredito correto "
        "é 'nao_reproduz' — e ele é um resultado legítimo, não uma falha.\n\n"
        "Esta é a sua ÚLTIMA tentativa: não haverá uma terceira.\n\n"
    ) + instrucao_auditor(contexto, com_modelo=com_modelo)


# --------------------------------------------------------------------------- #
# Saída dos agentes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SaidaInvestigador:
    """O que o Investigador produziu — **com** o rastro.

    Este objeto nunca é entregue ao Auditor. O que vai adiante é o
    `ContextoAuditor`, montado por `montar_contexto_auditor`.
    """

    pergunta: str
    afirmacao: str = ""
    citacoes: tuple[str, ...] = ()
    rastro: tuple[str, ...] = ()
    cobertura: str = ""
    comportamento: str = ""
    motivo_recusa: str = "n/a"
    bases: tuple[str, ...] = ()
    bruto: str = ""
    json_valido: bool = True
    parcial: bool = False
    teto_ferramenta: bool = False
    teto_iteracoes: bool = False
    chamadas: tuple[ChamadaFerramenta, ...] = ()
    uso: UsoAgente = field(default_factory=UsoAgente)
    erro: str | None = None
    # Rodada corretiva do gate de dado (5.9.5). `correcao_aplicada` diz se o
    # segundo tiro foi disparado; `correcao_resultado` diz no que deu. Os dois
    # ficam **fora** de `CAMPOS_CONTEXTO_AUDITOR` por construção — a lista de
    # permissão do isolamento não muda porque um campo novo nasceu aqui.
    correcao_aplicada: bool = False
    correcao_resultado: str = CORRECAO_NAO_NECESSARIA

    def como_dicionario(self) -> dict:
        return {
            "pergunta": self.pergunta,
            "afirmacao": self.afirmacao,
            "citacoes": list(self.citacoes),
            "rastro": list(self.rastro),
            "cobertura": self.cobertura,
            "comportamento": self.comportamento,
            "motivo_recusa": self.motivo_recusa,
            "bases": list(self.bases),
            "json_valido": self.json_valido,
            "parcial": self.parcial,
            "teto_ferramenta": self.teto_ferramenta,
            "teto_iteracoes": self.teto_iteracoes,
            "uso": self.uso.como_dicionario(),
            "erro": self.erro,
            "correcao_aplicada": self.correcao_aplicada,
            "correcao_resultado": self.correcao_resultado,
        }


@dataclass(frozen=True)
class ContextoAuditor:
    """**Tudo** o que o Auditor recebe do Investigador. Três campos, e só.

    Os campos são exatamente `CAMPOS_CONTEXTO_AUDITOR`. Acrescentar um quarto
    aqui é acrescentar um canal de vazamento, e o teste de isolamento existe
    para que isso não passe despercebido.
    """

    pergunta: str
    afirmacao: str
    citacoes: tuple[str, ...] = ()

    def como_dicionario(self) -> dict:
        return {
            "pergunta": self.pergunta,
            "afirmacao": self.afirmacao,
            "citacoes": list(self.citacoes),
        }


@dataclass(frozen=True)
class VereditoAuditor:
    """Resultado da segunda passagem — um dos três vereditos de 5.9.1."""

    veredito: str = VEREDITO_NAO_REPRODUZ
    justificativa: str = ""
    contraevidencia: tuple[str, ...] = ()
    citacoes: tuple[str, ...] = ()
    bruto: str = ""
    json_valido: bool = True
    chamadas: tuple[ChamadaFerramenta, ...] = ()
    uso: UsoAgente = field(default_factory=UsoAgente)
    teto_ferramenta: bool = False
    teto_iteracoes: bool = False
    erro: str | None = None
    correcao_aplicada: bool = False
    correcao_resultado: str = CORRECAO_NAO_NECESSARIA

    def __post_init__(self) -> None:
        if self.veredito not in VEREDITOS:
            raise ValueError(f"veredito desconhecido: {self.veredito!r}")

    def como_dicionario(self) -> dict:
        return {
            "veredito": self.veredito,
            "justificativa": self.justificativa,
            "contraevidencia": list(self.contraevidencia),
            "citacoes": list(self.citacoes),
            "json_valido": self.json_valido,
            "uso": self.uso.como_dicionario(),
            "erro": self.erro,
            "correcao_aplicada": self.correcao_aplicada,
            "correcao_resultado": self.correcao_resultado,
        }


# --------------------------------------------------------------------------- #
# O filtro de contexto — o coração do braço B
# --------------------------------------------------------------------------- #


def fragmentos_de_rastro(saida: SaidaInvestigador) -> tuple[str, ...]:
    """Trechos que **não podem** aparecer no que o Auditor recebe.

    Três origens, todas do lado do Investigador: o rastro declarado, os resumos
    das chamadas de ferramenta e as linhas do texto bruto marcadas pelo
    protocolo (`Thought:`, `Observation:`…).

    O texto bruto **não** entra inteiro de propósito: ele contém o próprio JSON
    final, e portanto a afirmação. Tratá-lo como impressão digital faria a
    guarda acusar a afirmação legítima de ser rastro — e uma guarda que reprova
    o caso correto é desligada na primeira execução ruim.

    Fragmentos curtos também ficam de fora (`MIN_FRAGMENTO_RASTRO`): casariam
    por acaso ("o lucro", "no painel") e produziriam o mesmo ruído.
    """
    candidatos: list[str] = list(saida.rastro)
    for linha in (saida.bruto or "").splitlines():
        if _normalizar(linha).startswith(MARCADORES_RASTRO):
            candidatos.append(linha)
    for chamada in saida.chamadas:
        candidatos.append(chamada.resumo or "")
    fragmentos = {
        _normalizar(c) for c in candidatos if len(_normalizar(c)) >= MIN_FRAGMENTO_RASTRO
    }
    return tuple(sorted(fragmentos))


def conferir_isolamento(mensagem: str, saida: SaidaInvestigador) -> tuple[str, ...]:
    """Vazamentos encontrados na mensagem destinada ao Auditor.

    Duas famílias: fragmento literal do rastro e marcador do protocolo de
    ferramentas. Devolve o que achou — vazio quer dizer isolamento íntegro.
    """
    normalizada = _normalizar(mensagem)
    achados = [f for f in fragmentos_de_rastro(saida) if f and f in normalizada]
    achados.extend(m for m in MARCADORES_RASTRO if m in normalizada)
    return tuple(sorted(set(achados)))


def _limpar_marcadores(texto: str) -> str:
    """Remove linhas do protocolo ReAct que o modelo tenha copiado na afirmação."""
    linhas = []
    for linha in (texto or "").splitlines():
        if _normalizar(linha).startswith(MARCADORES_RASTRO):
            continue
        linhas.append(linha)
    return "\n".join(linhas).strip()


def dispensa_auditoria(saida: SaidaInvestigador) -> bool:
    """A saída do Investigador é do tipo que o Auditor não tem como auditar?

    O papel do Auditor é **falsificar uma afirmação de fato** reexecutando as
    consultas por conta própria. Uma pergunta de desambiguação (RN11) não é
    afirmação: não traz valor, não traz citação e não conclui — devolve a
    escolha ao usuário, que é a resposta certa. Não há o que reproduzir, e os
    três vereditos não têm célula para isso: o que sai é `nao_reproduz`, cujo
    significado publicado ("a conferência não conseguiu reproduzir a evidência
    desta afirmação") é falso aqui e ainda rebaixa a resposta a parcial.

    Medido em 2026-08-13 (AGTC003, "BTG"): o braço A acertava e o B errava
    **só** por esse roteamento. A decisão é de código e não de prompt — é o
    mesmo princípio do isolamento: nada que dependa de o modelo se comportar.
    """
    return saida.comportamento in COMPORTAMENTOS_SEM_AUDITORIA


def montar_contexto_auditor(saida: SaidaInvestigador) -> ContextoAuditor:
    """Monta, **por código**, a única mensagem que atravessa do 1º ao 2º agente.

    Lista de permissão (`CAMPOS_CONTEXTO_AUDITOR`), não lista de bloqueio: o
    contexto é construído campo a campo a partir da afirmação e das citações. Um
    campo novo em `SaidaInvestigador` — rastro, transcrição, chamadas de
    ferramenta, texto bruto — fica de fora **por construção**.

    Depois da cópia, duas limpezas, porque a lista de permissão sozinha não
    cobre o caso em que o próprio modelo despeja o raciocínio dentro da
    afirmação:

    1. linhas com marcador do protocolo (`Thought:`, `Observation:`…) são
       removidas;
    2. fragmento do rastro que ainda apareça literalmente na afirmação é
       recortado.

    Se depois disso ainda houver vazamento, é defeito de código e a função
    **falha alto** (`VazamentoDeRastroError`) em vez de seguir chamando o
    Auditor — o braço B sem isolamento é o braço A pagando o dobro.

    Pelo mesmo motivo, saída que `dispensa_auditoria` não chega aqui: esta
    função é o **único** ponto de passagem do Investigador para o Auditor, e
    barrar nela faz o roteamento errado falhar alto em qualquer caminho, em vez
    de degenerar em uma chamada paga que carimba `nao_reproduz` sobre uma
    pergunta.
    """
    if dispensa_auditoria(saida):
        raise AuditoriaNaoAplicavelError(
            "saída com comportamento "
            f"{saida.comportamento!r} não é afirmação de fato e não vai ao "
            "Auditor; verifique `dispensa_auditoria` antes de montar o contexto"
        )
    fragmentos = fragmentos_de_rastro(saida)
    afirmacao = _remover_fragmentos(_limpar_marcadores(saida.afirmacao), fragmentos)
    citacoes = tuple(
        limpa
        for limpa in (
            _remover_fragmentos(_limpar_marcadores(c), fragmentos)
            for c in saida.citacoes
            if str(c).strip()
        )
        if limpa
    )
    if not afirmacao.strip():
        # O modelo pôs só o raciocínio na afirmação e o filtro levou tudo. O
        # texto abaixo é gerado por código e não carrega nada do Investigador —
        # o Auditor vai concluir `nao_reproduz`, que é o desfecho honesto.
        afirmacao = (
            "O Investigador não produziu afirmação separável do próprio rastro "
            "de raciocínio; o filtro de isolamento a suprimiu."
        )
    contexto = ContextoAuditor(
        pergunta=saida.pergunta,
        afirmacao=afirmacao.strip(),
        citacoes=citacoes,
    )
    vazamentos = conferir_isolamento(
        json.dumps(contexto.como_dicionario(), ensure_ascii=False), saida
    )
    if vazamentos:
        raise VazamentoDeRastroError(
            "o contexto do Auditor ainda contém rastro do Investigador: "
            f"{vazamentos[:3]}"
        )
    return contexto


_SEPARADOR_SENTENCA = re.compile(r"(?<=[.!?;])\s+|\n+")


def _remover_fragmentos(texto: str, fragmentos: Sequence[str]) -> str:
    """Descarta as sentenças do texto que carregam algum fragmento de rastro.

    A remoção é **por sentença**, não por janela de caracteres: recortar no meio
    de uma frase devolveria texto sem sentido ao Auditor, e um texto truncado é
    tão difícil de auditar quanto um texto vazio. O preço é remover um pouco a
    mais que o estritamente vazado — preço aceito, porque o erro caro aqui é
    deixar passar, não remover demais.
    """
    if not texto or not fragmentos:
        return texto or ""
    sentencas = [s for s in _SEPARADOR_SENTENCA.split(texto) if s and s.strip()]
    mantidas = []
    for sentenca in sentencas:
        normalizada = _normalizar(sentenca)
        copiou_o_rastro = any(f and f in normalizada for f in fragmentos)
        # A direção inversa (a sentença cabe dentro de uma linha de rastro) só
        # vale para sentenças longas: abaixo do limiar, a coincidência é de
        # vocabulário do domínio, não cópia.
        veio_do_rastro = len(normalizada) >= MIN_FRAGMENTO_RASTRO and any(
            f and normalizada in f for f in fragmentos
        )
        if copiou_o_rastro or veio_do_rastro:
            continue
        mantidas.append(sentenca.strip())
    return " ".join(mantidas).strip()


# --------------------------------------------------------------------------- #
# Leitura da saída JSON dos agentes
# --------------------------------------------------------------------------- #


def extrair_json(bruto: str) -> dict | None:
    """Lê o objeto JSON da resposta do agente, tolerando cerca de código.

    Não "conserta" conteúdo: se não houver objeto legível, devolve `None` e quem
    chamou trata como saída fora do contrato — que vira recusa registrada, nunca
    resposta livre publicada.
    """
    texto = (bruto or "").strip()
    if not texto:
        return None
    if texto.startswith("```"):
        texto = re.sub(r"^```[a-zA-Z]*\n?", "", texto)
        texto = re.sub(r"\n?```$", "", texto).strip()
    try:
        objeto = json.loads(texto)
    except json.JSONDecodeError:
        inicio = texto.find("{")
        fim = texto.rfind("}")
        if inicio < 0 or fim <= inicio:
            return None
        try:
            objeto = json.loads(texto[inicio : fim + 1])
        except json.JSONDecodeError:
            return None
    return objeto if isinstance(objeto, dict) else None


def _lista_de_textos(valor: Any) -> tuple[str, ...]:
    if valor is None:
        return ()
    if isinstance(valor, str):
        return (valor,) if valor.strip() else ()
    if isinstance(valor, Sequence):
        return tuple(
            str(item).strip()
            for item in valor
            if str(item).strip() and not isinstance(item, (dict, list))
        )
    return ()


# --------------------------------------------------------------------------- #
# RN01 e RN02 verificadas por código sobre o JSON de saída (5.9.5)
# --------------------------------------------------------------------------- #


def valores_monetarios_do_texto(texto: str) -> tuple[float, ...]:
    """Valores em dinheiro citados na resposta, já convertidos para reais.

    Usa o parser pt-BR do projeto (`extrair_numeros_ptbr_tipados`), que
    distingue dimensão: só `monetario` e `escala` entram. Percentual, data e
    número nu ficam de fora **de propósito** — um percentual costuma ser
    aritmética derivada de dois valores já lastreados, e cobrá-lo aqui
    reprovaria resposta correta, medindo a régua em vez do agente. Limitação
    declarada.
    """
    return tuple(
        numero.valor
        for numero in extrair_numeros_ptbr_tipados(texto or "")
        if numero.dimensao in ("monetario", "escala")
    )


def _tem_lastro(valor: float, evidencias: Sequence[float]) -> bool:
    """O valor escrito corresponde a algum número devolvido pelas ferramentas?

    Compara sob as escalas usuais (unidade, mil, milhão, bilhão) porque o painel
    devolve reais e a resposta fala em milhões. A tolerância acompanha a
    precisão com que o número foi escrito: "R$ 6,2 bilhões" tem meia-casa de
    0,05 bilhão, e cobrar igualdade exata acusaria de alucinação um
    arredondamento correto.
    """
    if not evidencias:
        return False
    magnitude = abs(valor)
    if magnitude == 0:
        return any(abs(e) == 0 for e in evidencias)
    tolerancia = max(magnitude * TOLERANCIA_RELATIVA_MINIMA, _meia_casa(valor))
    for evidencia in evidencias:
        for escala in ESCALAS_LASTRO:
            # A tolerância vive nas unidades do número **escrito**, e é por isso
            # que ela acompanha a escala apenas quando é o escrito que sobe. Se
            # ela fosse multiplicada pela escala nos dois lados, comparar contra
            # bilhões abriria uma janela de milhões e qualquer número passaria —
            # a verificação de RN02 viraria carimbo.
            if abs(magnitude - abs(evidencia) * escala) <= tolerancia:
                return True
            if abs(magnitude * escala - abs(evidencia)) <= tolerancia * escala:
                return True
    return False


def _meia_casa(valor: float) -> float:
    """Meia unidade do último dígito significativo escrito."""
    texto = f"{abs(valor):.10g}"
    if "e" in texto or "E" in texto:
        return abs(valor) * 1e-3
    inteiro, _, decimais = texto.partition(".")
    if decimais:
        return 0.5 * (10 ** (-len(decimais)))
    zeros = len(inteiro) - len(inteiro.rstrip("0"))
    return 0.5 * (10**zeros)


def _rotulos_compativeis(
    tokens_resposta: frozenset[str], tokens_evidencia: frozenset[str]
) -> bool:
    """A mesma regra de `metricas_compativeis` do caminho livre.

    Quando os dois lados nomeiam grupo de métrica, eles precisam ser o mesmo:
    é o que impede margem casar com despesa. Quando um dos lados não nomeia
    grupo, basta compartilhar um token de rótulo.
    """
    grupos_resposta = _com_grupos_gerais(tokens_resposta & _NOMES_GRUPOS)
    grupos_evidencia = _com_grupos_gerais(tokens_evidencia & _NOMES_GRUPOS)
    if grupos_resposta and grupos_evidencia:
        return bool(grupos_resposta & grupos_evidencia)
    return bool(tokens_resposta & tokens_evidencia)


# Grupo específico que é caso do geral. O tokenizador do caminho livre põe
# "margem financeira" num grupo próprio, que substitui o de margem: "a margem
# com clientes foi de R$ 27,7 bilhões" contra "Margem financeira com clientes
# 27,7" dava grupos disjuntos, e a resposta certa virava recusa (achado B3 da
# auditoria de 20/10). Só aqui, nos agentes: o caminho livre é medido nas 45.
_GRUPO_GERAL: dict[str, str] = {"metrica_margem_financeira": "metrica_margem"}


def _com_grupos_gerais(grupos: frozenset[str]) -> frozenset[str]:
    return grupos | {_GRUPO_GERAL[g] for g in grupos if g in _GRUPO_GERAL}


def _julgar_rotulos(
    saida: SaidaInvestigador, ferramentas: FerramentasDoAgente
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Orações com rótulo trocado e orações com rótulo não verificável.

    Só a oração que nomeia métrica é julgada. Para cada valor em dinheiro dela:

    * há número igual rotulado e nenhum é de métrica compatível → **trocado**;
    * não há número igual rotulado, mas o valor tem lastro na RN02 sem rótulo
      (literal de SQL, célula de texto) → **não verificável**. Falha fechada,
      pela regra 4 da §4.4: sem rótulo para conferir, a guarda não aprova;
    * não há lastro nenhum → é a `VIOLACAO_RN02_SEM_LASTRO`, não esta.
    """
    fatos = ferramentas.fatos_rotulados()
    evidencias = ferramentas.valores_de_evidencia()
    trocadas: list[str] = []
    sem_rotulo: list[str] = []
    for clausula in dividir_em_clausulas(saida.afirmacao or ""):
        tokens_resposta = _tokens_do_rotulo(clausula)
        if not tokens_resposta & _NOMES_GRUPOS:
            continue
        for numero in extrair_numeros_ptbr_tipados(clausula):
            if numero.dimensao not in ("monetario", "escala"):
                continue
            iguais = [f for f in fatos if _tem_lastro(numero.valor, (f.valor,))]
            if iguais:
                if not any(
                    _rotulos_compativeis(tokens_resposta, f.tokens) for f in iguais
                ):
                    trocadas.append(clausula.strip())
                    break
            elif _tem_lastro(numero.valor, evidencias):
                sem_rotulo.append(clausula.strip())
                break
    return tuple(trocadas), tuple(sem_rotulo)


def valores_com_rotulo_trocado(
    saida: SaidaInvestigador, ferramentas: FerramentasDoAgente
) -> tuple[str, ...]:
    """Orações cujo valor só existe na evidência sob OUTRA métrica.

    Achado da rodada real de 19/10 no chat: o Investigador escreveu "margem
    financeira gerencial de R$ 17,2 bilhões" para o Itaú no 3T2025. O número
    estava no trecho recuperado, e era "Despesas não decorrentes de juros"; a
    margem é R$ 31.382 milhões. A RN02 dos agentes só perguntava se o número
    existia, e aprovou. O caminho livre já pergunta também de que métrica ele
    é, e esta função leva a mesma pergunta aos agentes, com o mesmo
    tokenizador. Regras em `_julgar_rotulos`.
    """
    return _julgar_rotulos(saida, ferramentas)[0]


def valores_sem_rotulo_verificavel(
    saida: SaidaInvestigador, ferramentas: FerramentasDoAgente
) -> tuple[str, ...]:
    """Orações cujo valor tem lastro, mas em número que nenhuma fonte rotula."""
    return _julgar_rotulos(saida, ferramentas)[1]


def verificar_regras_agente(
    saida: SaidaInvestigador, ferramentas: FerramentasDoAgente
) -> tuple[str, ...]:
    """RN01 e RN02 sobre o JSON de saída — mecânicas, sem julgar texto livre.

    Seis checagens:

    1. saída que não é o objeto JSON do contrato (o agente ignorou o formato);
    2. valor apresentado sem nenhuma citação (RN01);
    3. citação que não casa com **nada** que alguma ferramenta devolveu — fonte
       inventada (RN01);
    4. valor monetário no texto sem correspondência em nenhum número devolvido
       pelas ferramentas — é a definição operacional de alucinação aqui (RN02);
    5. valor que existe na evidência só sob outra métrica — o número certo com
       o nome errado — ou cujo lastro não tem rótulo para conferir (RN02,
       `_julgar_rotulos`);
    6. recusa que ainda assim apresenta valor (RN02).

    Nenhuma delas confia no julgamento do modelo, e é essa a diferença entre
    verificar a regra e pedir ao agente que a respeite.
    """
    violacoes: list[str] = []
    if not saida.json_valido:
        violacoes.append(VIOLACAO_SAIDA_ILEGIVEL)
    valores = valores_monetarios_do_texto(saida.afirmacao)
    recusa = saida.comportamento == "recusa"

    if valores and not saida.citacoes:
        violacoes.append(VIOLACAO_RN01_SEM_CITACAO)

    rotulos = ferramentas.rotulos_de_evidencia()
    for citacao in saida.citacoes:
        normalizada = _normalizar(citacao)
        if not any(rotulo in normalizada for rotulo in rotulos):
            violacoes.append(VIOLACAO_RN01_CITACAO_SEM_LASTRO)
            break

    evidencias = ferramentas.valores_de_evidencia()
    if any(not _tem_lastro(valor, evidencias) for valor in valores):
        violacoes.append(VIOLACAO_RN02_SEM_LASTRO)

    if valores and not recusa:
        trocadas, sem_rotulo = _julgar_rotulos(saida, ferramentas)
        if trocadas:
            violacoes.append(VIOLACAO_RN02_ROTULO_TROCADO)
        if sem_rotulo:
            violacoes.append(VIOLACAO_RN02_ROTULO_NAO_VERIFICAVEL)

    if recusa and valores:
        violacoes.append(VIOLACAO_RN02_RECUSA_COM_VALOR)
    return tuple(dict.fromkeys(violacoes))


def converter_em_recusa_agente(
    saida: SaidaInvestigador, violacoes: Sequence[str]
) -> SaidaInvestigador:
    """Transforma saída que violou RN01/RN02 em **recusa registrada** (5.9.5).

    A saída original não é apagada — vai para `bruto`, porque quem executa
    precisa dela para depurar e o log da RNF08 precisa dela para auditar. O que
    não pode acontecer é a resposta sem citação (ou com citação inventada)
    chegar ao usuário como resposta.
    """
    return SaidaInvestigador(
        pergunta=saida.pergunta,
        afirmacao=(
            "Recusa registrada: a resposta produzida foi descartada por violar "
            "as regras verificadas em código sobre a saída "
            f"({', '.join(violacoes)}). Nenhum valor é apresentado sem citação "
            "da fonte que o produziu (RN01/RN02)."
        ),
        citacoes=(),
        rastro=saida.rastro,
        cobertura=saida.cobertura,
        comportamento="recusa",
        motivo_recusa="recusa_convertida_por_violacao",
        bases=(),
        bruto=saida.bruto or saida.afirmacao,
        json_valido=saida.json_valido,
        parcial=True,
        teto_ferramenta=saida.teto_ferramenta,
        teto_iteracoes=saida.teto_iteracoes,
        chamadas=saida.chamadas,
        uso=saida.uso,
        erro=saida.erro,
        # A recusa apaga a resposta, nunca o registro de como se chegou nela: o
        # experimento precisa saber que houve segundo tiro e que ele falhou.
        correcao_aplicada=saida.correcao_aplicada,
        correcao_resultado=saida.correcao_resultado,
    )


# --------------------------------------------------------------------------- #
# Execução de um agente
# --------------------------------------------------------------------------- #


def _montar_crew(
    *,
    papel: str,
    objetivo: str,
    historia: str,
    instrucao: str,
    llm: BaseLLM,
    ferramentas_crew: Sequence[BaseTool],
    max_iteracoes: int,
) -> Crew:
    """Um agente, uma tarefa, `Process.sequential` — sem memória e sem cache.

    Memória desligada porque memória do framework é um segundo armazenamento
    vetorial fora do controle do projeto; cache desligado porque resultado de
    ferramenta reaproveitado entre perguntas esconderia chamada da contagem de
    custo, e o experimento mede exatamente isso.
    """
    agente = Agent(
        role=papel,
        goal=objetivo,
        backstory=historia,
        llm=llm,
        tools=list(ferramentas_crew),
        max_iter=max_iteracoes,
        allow_delegation=False,
        cache=False,
        verbose=False,
        inject_date=False,
    )
    tarefa = Task(
        description=instrucao,
        expected_output="Um único objeto JSON no formato pedido, sem texto fora dele.",
        agent=agente,
    )
    return Crew(
        agents=[agente],
        tasks=[tarefa],
        process=Process.sequential,
        memory=False,
        cache=False,
        verbose=False,
    )


def _executar_crew(crew: Crew) -> tuple[str, str | None, bool]:
    """Roda o crew e devolve (texto bruto, erro, teto de iterações estourado).

    Três desfechos, tratados de forma diferente de propósito:

    * **teto rígido** — não é erro: é a contenção cortando o laço. Volta
      marcado, para virar resposta parcial e não recusa por defeito;
    * **estouro de orçamento** — sobe, porque a execução inteira precisa parar;
    * **qualquer outra exceção** — vira erro registrado, porque uma pergunta não
      pode derrubar as outras catorze.
    """
    try:
        saida = crew.kickoff()
    except TetoIteracoesExcedidoError:
        return "", None, True
    except OrcamentoAgentesExcedidoError:
        raise
    except Exception as erro:  # contenção: uma pergunta não derruba as 15
        return "", f"{type(erro).__name__}: {erro}", False
    return str(getattr(saida, "raw", "") or ""), None, False


def _resumo_da_evidencia(ferramentas: FerramentasDoAgente) -> str:
    """Descreve, sem número e sem afirmação, o que foi reunido até o corte.

    Texto gerado por **código**: nada aqui vem do modelo, que justamente não
    concluiu. Nenhum valor monetário entra — publicar número de uma resposta que
    não fechou seria inventar o que o teto interrompeu.
    """
    if not ferramentas.chamadas:
        return "Nenhuma consulta foi concluída antes do corte."
    por_ferramenta: dict[str, int] = {}
    for chamada in ferramentas.chamadas:
        por_ferramenta[chamada.ferramenta] = (
            por_ferramenta.get(chamada.ferramenta, 0) + 1
        )
    itens = ", ".join(f"{nome} ×{n}" for nome, n in sorted(por_ferramenta.items()))
    return f"Consultas concluídas antes do corte: {itens}."


def _saida_por_teto(
    pergunta: str, ferramentas: FerramentasDoAgente, uso: UsoAgente
) -> SaidaInvestigador:
    """A resposta que a 5.9.5 manda dar quando o teto estoura.

    Parcial marcada, não recusa: o sistema não deixou de encontrar evidência —
    ele parou de procurar por decisão de contenção, e dizer "recusa" confundiria
    as duas coisas justamente no experimento que existe para separá-las (5.9.4).
    """
    return SaidaInvestigador(
        pergunta=pergunta,
        afirmacao=(
            "RESPOSTA PARCIAL — o teto de passos por pergunta foi atingido "
            "antes de a investigação concluir. Nenhuma afirmação é publicada "
            f"sem conclusão. {_resumo_da_evidencia(ferramentas)}"
        ),
        citacoes=(),
        rastro=(),
        cobertura="",
        comportamento=COMPORTAMENTO_PARCIAL_MARCADO,
        motivo_recusa="n/a",
        bases=(),
        bruto="",
        json_valido=True,
        parcial=True,
        teto_ferramenta=ferramentas.teto_atingido,
        teto_iteracoes=True,
        chamadas=tuple(ferramentas.chamadas),
        uso=uso,
    )


def executar_investigador(
    pergunta: str,
    config: Config,
    ferramentas: FerramentasDoAgente,
    llm: BaseLLM,
    *,
    papel: str = PAPEL_INVESTIGADOR,
    max_iteracoes: int | None = None,
    permitir_correcao: bool = True,
) -> SaidaInvestigador:
    """Responde, registra o rastro e — se preciso — dá **um** segundo tiro.

    O braço A usa exatamente esta função (com `papel=agente_unico`): "mesmo
    prompt de resposta, mesma temperatura" é o que torna A e B comparáveis — a
    única diferença entre os dois braços é a segunda passagem do Auditor.

    ## O gate de correção (5.9.5), e por que ele não é orçamento novo

    Se a saída publica dado (valor, base ou citação) e **nenhuma** ferramenta de
    dado foi chamada, o agente respondeu de memória. Antes de o código converter
    isso em recusa registrada — o que já funcionava, e é o que protege o
    usuário — vale **uma** reexecução com a regra violada reinjetada por código.
    Uma só: não é laço aberto, é um segundo tiro.

    A contenção não afrouxa. A rodada corretiva:

    * roda no **mesmo** `LLMComTetoRigido` da primeira, logo consome o mesmo
      `agentes_max_iteracoes` — se não couber, ela é cortada e a primeira saída
      segue para a conversão em recusa;
    * roda na **mesma** `FerramentasDoAgente`, logo consome o mesmo
      `agentes_max_chamadas_ferramenta`;
    * aparece na contabilidade normal (`chamadas_llm`, `custo_usd`,
      `latencia_s`), porque o acumulador é o do provedor, não o da passagem.
    """
    teto = max_iteracoes or config.agentes_max_iteracoes
    contido = LLMComTetoRigido(llm, teto + MARGEM_PEDIDO_RESPOSTA_FINAL)
    saida, cortada = _passagem_investigador(
        pergunta,
        ferramentas,
        contido,
        llm,
        teto,
        instrucao_investigador(pergunta, com_modelo=FERRAMENTA_MODELO in ferramentas.nomes),
    )
    if cortada or not permitir_correcao:
        return saida
    if not precisa_correcao_de_dado(saida, ferramentas):
        return saida
    registrador.info(
        "gate_de_dado: rodada corretiva do Investigador | pergunta=%r | "
        "ferramentas usadas até aqui=%s",
        pergunta[:80],
        sorted({c.ferramenta for c in ferramentas.chamadas}) or ["(nenhuma)"],
    )
    corrigida, cortada_corretiva = _passagem_investigador(
        pergunta,
        ferramentas,
        contido,
        llm,
        teto,
        instrucao_corretiva_investigador(
            pergunta, com_modelo=FERRAMENTA_MODELO in ferramentas.nomes
        ),
    )
    return _consolidar_correcao(saida, corrigida, cortada_corretiva, ferramentas, llm)


def _consolidar_correcao(
    primeira: SaidaInvestigador,
    corrigida: SaidaInvestigador,
    cortada: bool,
    ferramentas: FerramentasDoAgente,
    llm: BaseLLM,
) -> SaidaInvestigador:
    """Escolhe entre a saída original e a corretiva, e rotula o desfecho.

    Duas situações mandam **manter a primeira**: a rodada corretiva não coubera
    no teto, ou ela devolveu saída ilegível. Nos dois casos a primeira saída
    segue o caminho de sempre — RN01/RN02 a convertem em recusa registrada —, e
    o que muda é só o rótulo, que passa a dizer que houve tentativa. Preferir a
    corretiva ilegível seria trocar uma recusa informativa por uma recusa por
    defeito de formato.
    """
    from dataclasses import replace

    uso = getattr(llm, "uso", UsoAgente())
    chamadas = tuple(ferramentas.chamadas)
    if cortada or not corrigida.json_valido:
        return replace(
            primeira,
            correcao_aplicada=True,
            correcao_resultado=(
                CORRECAO_CORTADA_POR_TETO if cortada else CORRECAO_FALHOU
            ),
            parcial=True,
            teto_iteracoes=primeira.teto_iteracoes or cortada,
            teto_ferramenta=ferramentas.teto_atingido,
            chamadas=chamadas,
            uso=uso,
        )
    # A conferência é direta — `consultou_ferramenta_de_dado` e `declara_dado` —,
    # e **não** `precisa_correcao_de_dado`: aquela função devolve `False` também
    # quando o teto foi atingido, e usá-la aqui rotularia como "corrigida" uma
    # segunda passagem que só ficou sem orçamento.
    resolvido = consultou_ferramenta_de_dado(ferramentas) or not declara_dado(
        corrigida
    )
    return replace(
        corrigida,
        correcao_aplicada=True,
        correcao_resultado=(
            CORRECAO_BEM_SUCEDIDA if resolvido else CORRECAO_FALHOU
        ),
    )


def _passagem_investigador(
    pergunta: str,
    ferramentas: FerramentasDoAgente,
    contido: BaseLLM,
    llm: BaseLLM,
    teto: int,
    instrucao: str,
) -> tuple[SaidaInvestigador, bool]:
    """Uma passagem do Investigador. Devolve (saída, cortada pelo teto rígido).

    O `LLMComTetoRigido` é recebido pronto, e não criado aqui, exatamente para
    que a rodada corretiva compartilhe o contador com a primeira passagem.
    """
    crew = _montar_crew(
        papel="Investigador",
        objetivo=OBJETIVO_INVESTIGADOR,
        historia=HISTORIA_INVESTIGADOR,
        instrucao=instrucao,
        llm=contido,
        ferramentas_crew=construir_ferramentas(ferramentas),
        max_iteracoes=teto,
    )
    bruto, erro, cortado = _executar_crew(crew)
    uso = getattr(llm, "uso", UsoAgente())
    if cortado:
        return _saida_por_teto(pergunta, ferramentas, uso), True
    objeto = extrair_json(bruto)
    teto_iteracoes = uso.chamadas_llm > teto
    if objeto is None:
        return SaidaInvestigador(
            pergunta=pergunta,
            afirmacao=bruto.strip(),
            bruto=bruto,
            json_valido=False,
            parcial=True,
            teto_ferramenta=ferramentas.teto_atingido,
            teto_iteracoes=teto_iteracoes,
            chamadas=tuple(ferramentas.chamadas),
            uso=uso,
            erro=erro,
        ), False
    parcial = bool(
        ferramentas.teto_atingido
        or teto_iteracoes
        or str(objeto.get("comportamento", "")) == "resposta_parcial_marcada"
    )
    return SaidaInvestigador(
        pergunta=pergunta,
        afirmacao=str(objeto.get("afirmacao", "") or "").strip(),
        citacoes=_lista_de_textos(objeto.get("citacoes")),
        rastro=_lista_de_textos(objeto.get("rastro")),
        cobertura=str(objeto.get("cobertura", "") or "").strip(),
        comportamento=str(objeto.get("comportamento", "") or "").strip(),
        motivo_recusa=str(objeto.get("motivo_recusa", "n/a") or "n/a").strip(),
        bases=_lista_de_textos(objeto.get("bases")),
        bruto=bruto,
        json_valido=True,
        parcial=parcial,
        teto_ferramenta=ferramentas.teto_atingido,
        teto_iteracoes=teto_iteracoes,
        chamadas=tuple(ferramentas.chamadas),
        uso=uso,
        erro=erro,
    ), False


def executar_auditor(
    contexto: ContextoAuditor,
    config: Config,
    ferramentas: FerramentasDoAgente,
    llm: BaseLLM,
    *,
    max_iteracoes: int | None = None,
    permitir_correcao: bool = True,
) -> VereditoAuditor:
    """Segunda passagem: tenta derrubar a afirmação, sem ver o rastro.

    Recebe o `ContextoAuditor` já filtrado — esta função **não** tem acesso à
    `SaidaInvestigador`, e essa restrição de assinatura é parte do isolamento:
    não há como vazar o que não foi passado.

    Saída ilegível vira `nao_reproduz`, nunca `confirma`. Um auditor que não
    conseguiu se expressar não confirmou nada, e o default seguro é o veredito
    que marca a resposta como parcial.

    ## O mesmo gate de dado do Investigador, com o desfecho próprio do Auditor

    Um Auditor que emite `confirma` (ou `contesta`) sem ter executado nenhuma
    consulta de dado não conferiu nada — carimbou. Ele recebe **um** segundo
    tiro, com a regra reinjetada por código e dentro do mesmo teto. Se ainda
    assim não consultar, o veredito é **rebaixado para `nao_reproduz`**, com
    justificativa escrita por código: ausência de reexecução é exatamente o
    terceiro veredito de 5.9.1, e é o mais valioso de não perder.

    ## `confirma` responde por cada fonte citada (19/10)

    Na rodada real do chat, o Auditor confirmou "a faixa de porte e a taxa
    histórica no modelo preditivo" tendo reexecutado só o painel. Uma consulta
    de dado qualquer bastava para o gate acima. Agora, para `confirma`, cada
    tipo de fonte das citações (`fonte_da_citacao`: painel, release, modelo)
    precisa de reconsulta própria. A fonte que falta e a caixa alcança ganha o
    mesmo segundo tiro; a que segue faltando, ou que a caixa não alcança,
    rebaixa a `nao_reproduz` com justificativa escrita por código.
    """
    teto = max_iteracoes or config.agentes_max_iteracoes
    com_modelo = FERRAMENTA_MODELO in ferramentas.nomes
    contido = LLMComTetoRigido(llm, teto + MARGEM_PEDIDO_RESPOSTA_FINAL)
    veredito, cortada = _passagem_auditor(
        contexto,
        ferramentas,
        contido,
        llm,
        teto,
        instrucao_auditor(contexto, com_modelo=com_modelo),
    )
    if cortada:
        return veredito
    from dataclasses import replace

    if not permitir_correcao or not _precisa_correcao_auditor(
        veredito, ferramentas, contexto
    ):
        # Sem rodada corretiva (desligada, teto atingido, ou fonte que a caixa
        # dele não alcança): o rebaixamento vale do mesmo jeito. `permitir_
        # correcao` desliga o segundo tiro, não a verificação.
        rebaixamento = _rebaixamento(veredito, contexto, ferramentas)
        if rebaixamento:
            return replace(veredito, **rebaixamento, chamadas=tuple(ferramentas.chamadas))
        return veredito
    faltantes_antes = _faltantes_para_confirmar(veredito, contexto, ferramentas)
    registrador.info(
        "gate_de_dado: rodada corretiva do Auditor | pergunta=%r | veredito "
        "%s | fontes sem reconsulta=%s",
        contexto.pergunta[:80],
        veredito.veredito,
        sorted(faltantes_antes) or ["(nenhuma consulta de dado)"],
    )
    corrigido, cortada_corretiva = _passagem_auditor(
        contexto,
        ferramentas,
        contido,
        llm,
        teto,
        instrucao_corretiva_auditor(
            contexto,
            faltantes=faltantes_antes if consultou_ferramenta_de_dado(ferramentas) else frozenset(),
            com_modelo=com_modelo,
        ),
    )

    escolhido = veredito if cortada_corretiva else corrigido
    desfecho_falho = CORRECAO_CORTADA_POR_TETO if cortada_corretiva else CORRECAO_FALHOU
    # Mesma precaução de `_consolidar_correcao`: a conferência é direta, e não
    # por `_precisa_correcao_auditor`, que também devolve `False` quando o teto
    # foi atingido — um `confirma` sem nenhuma consulta, ou com fonte citada
    # sem reconsulta, não pode escapar do rebaixamento porque acabou o orçamento.
    rebaixamento = _rebaixamento(escolhido, contexto, ferramentas)
    if rebaixamento:
        return replace(
            escolhido,
            **rebaixamento,
            correcao_aplicada=True,
            correcao_resultado=desfecho_falho,
            chamadas=tuple(ferramentas.chamadas),
            uso=getattr(llm, "uso", UsoAgente()),
        )
    return replace(
        escolhido,
        correcao_aplicada=True,
        correcao_resultado=CORRECAO_BEM_SUCEDIDA,
    )


def _faltantes_para_confirmar(
    veredito: VereditoAuditor,
    contexto: ContextoAuditor,
    ferramentas: FerramentasDoAgente,
) -> frozenset[str]:
    """Fontes citadas que um `confirma` deixou sem reconsulta.

    Só `confirma` responde por todas as fontes: `contesta` precisa de uma
    contraevidência, e `nao_reproduz` é a própria declaração de que a
    reprodução não aconteceu.
    """
    if veredito.veredito != VEREDITO_CONFIRMA:
        return frozenset()
    return fontes_sem_reconsulta(contexto, ferramentas)


def _rebaixamento(
    veredito: VereditoAuditor,
    contexto: ContextoAuditor,
    ferramentas: FerramentasDoAgente,
) -> dict[str, Any] | None:
    """Os campos que rebaixam o veredito a `nao_reproduz`, ou `None`.

    Duas razões, nesta ordem: veredito afirmativo sem nenhuma consulta de
    dado; e `confirma` com fonte citada sem reconsulta.
    """
    if veredito.veredito != VEREDITO_NAO_REPRODUZ and not consultou_ferramenta_de_dado(
        ferramentas
    ):
        return {
            "veredito": VEREDITO_NAO_REPRODUZ,
            "justificativa": (
                "a conferência independente não executou nenhuma consulta de "
                "dado (consultar_cvm, buscar_trechos ou calcular_indicadores); "
                "sem reexecução não há reprodução, e o veredito registrado é o "
                "de não reprodução"
            ),
            "contraevidencia": (),
        }
    faltantes = _faltantes_para_confirmar(veredito, contexto, ferramentas)
    return _rebaixamento_por_fonte(faltantes) if faltantes else None


def _rebaixamento_por_fonte(faltantes: frozenset[str]) -> dict[str, Any]:
    lista = "; ".join(DESCRICAO_FONTE[f] for f in sorted(faltantes))
    return {
        "veredito": VEREDITO_NAO_REPRODUZ,
        "justificativa": (
            "a conferência independente confirmou a afirmação sem reconsultar "
            f"todas as fontes que ela cita (faltou: {lista}); a parte dessas "
            "fontes não foi reproduzida, e o veredito registrado é o de não "
            "reprodução"
        ),
        "contraevidencia": (),
    }


def _precisa_correcao_auditor(
    veredito: VereditoAuditor,
    ferramentas: FerramentasDoAgente,
    contexto: ContextoAuditor,
) -> bool:
    """Veredito afirmativo sem consulta de dado, ou `confirma` com fonte citada
    sem reconsulta que a caixa do Auditor alcança?

    `nao_reproduz` fica de fora: ele **é** a declaração de que a reexecução não
    aconteceu, e cobrar uma consulta para poder dizer que não conseguiu
    consultar seria circular.
    """
    if veredito.veredito == VEREDITO_NAO_REPRODUZ:
        return False
    if veredito.teto_iteracoes or veredito.teto_ferramenta:
        return False
    if not consultou_ferramenta_de_dado(ferramentas):
        return True
    faltantes = _faltantes_para_confirmar(veredito, contexto, ferramentas)
    return bool(_fontes_que_ele_pode_reconsultar(faltantes, ferramentas))


def _passagem_auditor(
    contexto: ContextoAuditor,
    ferramentas: FerramentasDoAgente,
    contido: BaseLLM,
    llm: BaseLLM,
    teto: int,
    instrucao: str,
) -> tuple[VereditoAuditor, bool]:
    """Uma passagem do Auditor. Devolve (veredito, cortado pelo teto rígido)."""
    crew = _montar_crew(
        papel="Auditor",
        objetivo=OBJETIVO_AUDITOR,
        historia=HISTORIA_AUDITOR,
        instrucao=instrucao,
        llm=contido,
        ferramentas_crew=construir_ferramentas(ferramentas),
        max_iteracoes=teto,
    )
    bruto, erro, cortado = _executar_crew(crew)
    uso = getattr(llm, "uso", UsoAgente())
    if cortado:
        # O Auditor que não fecha o próprio laço não confirmou nada. A afirmação
        # fica irreprodutível — que é o terceiro veredito, não um erro.
        return VereditoAuditor(
            veredito=VEREDITO_NAO_REPRODUZ,
            justificativa=(
                "a conferência independente atingiu o teto de passos antes de "
                "concluir; a afirmação não foi reproduzida nem contestada"
            ),
            chamadas=tuple(ferramentas.chamadas),
            uso=uso,
            teto_ferramenta=ferramentas.teto_atingido,
            teto_iteracoes=True,
        ), True
    objeto = extrair_json(bruto)
    teto_iteracoes = uso.chamadas_llm > teto
    if objeto is None:
        return VereditoAuditor(
            veredito=VEREDITO_NAO_REPRODUZ,
            justificativa=(
                "o Auditor não devolveu um veredito legível; ausência de "
                "confirmação não é confirmação"
            ),
            bruto=bruto,
            json_valido=False,
            chamadas=tuple(ferramentas.chamadas),
            uso=uso,
            teto_ferramenta=ferramentas.teto_atingido,
            teto_iteracoes=teto_iteracoes,
            erro=erro,
        ), False
    declarado = str(objeto.get("veredito", "") or "").strip().lower()
    veredito = declarado if declarado in VEREDITOS else VEREDITO_NAO_REPRODUZ
    contraevidencia = _lista_de_textos(objeto.get("contraevidencia"))
    if veredito == VEREDITO_CONTESTA and not contraevidencia:
        # "Contesta com contraevidência citada" (5.9.1). Contestação sem
        # contraevidência não é contestação — é discordância sem lastro, e o
        # honesto é registrá-la como não reprodução.
        veredito = VEREDITO_NAO_REPRODUZ
    return VereditoAuditor(
        veredito=veredito,
        justificativa=str(objeto.get("justificativa", "") or "").strip(),
        contraevidencia=contraevidencia,
        citacoes=_lista_de_textos(objeto.get("citacoes")),
        bruto=bruto,
        json_valido=True,
        chamadas=tuple(ferramentas.chamadas),
        uso=uso,
        teto_ferramenta=ferramentas.teto_atingido,
        teto_iteracoes=teto_iteracoes,
        erro=erro,
    ), False


# --------------------------------------------------------------------------- #
# Resposta publicada
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RespostaAgente:
    """O que o sistema publica depois de código e (no braço B) auditoria."""

    pergunta: str
    resposta: str
    resposta_bruta: str = ""
    recusa: bool = False
    motivo_recusa: str = "n/a"
    parcial: bool = False
    precisa_desambiguacao: bool = False
    nao_conciliada: bool = False
    comportamento: str = ""
    cobertura: str = ""
    bases: tuple[str, ...] = ()
    citacoes: tuple[str, ...] = ()
    veredito_auditor: str | None = None
    violacoes: tuple[str, ...] = ()
    convertida_em_recusa: bool = False
    chamadas: tuple[ChamadaFerramenta, ...] = ()
    uso: UsoAgente = field(default_factory=UsoAgente)
    parcial_por_teto: bool = False
    contexto_auditor: ContextoAuditor | None = None
    erro: str | None = None
    # Gate de dado (5.9.5): houve rodada corretiva, e no que ela deu. Fica
    # visível na resposta porque a métrica que o experimento reporta é "quantas
    # respostas precisaram do segundo tiro, e quantas ele salvou".
    correcao_aplicada: bool = False
    correcao_resultado: str = CORRECAO_NAO_NECESSARIA


def _texto_nao_conciliado(
    saida: SaidaInvestigador, veredito: VereditoAuditor
) -> str:
    """Apresenta a divergência com as duas evidências, sem eleger vencedor (5.9.5)."""
    contra = "\n".join(f"- {c}" for c in veredito.contraevidencia)
    citadas = "\n".join(f"- {c}" for c in saida.citacoes) or "- (nenhuma)"
    return (
        "RESPOSTA NÃO CONCILIADA — a conferência independente contestou a "
        "afirmação, e o sistema não elege um vencedor.\n\n"
        f"AFIRMAÇÃO:\n{saida.afirmacao}\n\nEVIDÊNCIA DA AFIRMAÇÃO:\n{citadas}\n\n"
        f"CONTRAEVIDÊNCIA DA CONFERÊNCIA:\n{contra or '- (não apresentada)'}\n\n"
        f"Justificativa da conferência: {veredito.justificativa}"
    )


def _texto_nao_reproduzido(saida: SaidaInvestigador, veredito: VereditoAuditor) -> str:
    return (
        "RESPOSTA PARCIAL — a conferência independente não conseguiu reproduzir "
        "a evidência desta afirmação. Ela não foi contestada, mas também não "
        "está confirmada.\n\n"
        f"{saida.afirmacao}\n\n"
        f"Observação da conferência: {veredito.justificativa}"
    )


def consolidar(
    saida: SaidaInvestigador,
    *,
    violacoes: Sequence[str] = (),
    convertida: bool = False,
    veredito: VereditoAuditor | None = None,
    contexto: ContextoAuditor | None = None,
) -> RespostaAgente:
    """Junta investigação, verificação por código e (se houver) veredito.

    A ordem das marcações importa: o veredito do Auditor **não** apaga a recusa
    convertida por violação — uma resposta descartada por falta de citação
    continua descartada, mesmo que o Auditor a tenha confirmado.
    """
    comportamento = saida.comportamento
    recusa = comportamento == "recusa"
    parcial = saida.parcial
    nao_conciliada = False
    texto = saida.afirmacao
    if veredito is not None and not recusa:
        if veredito.veredito == VEREDITO_CONTESTA:
            texto = _texto_nao_conciliado(saida, veredito)
            nao_conciliada = True
            parcial = True
            comportamento = "resposta_parcial_marcada"
        elif veredito.veredito == VEREDITO_NAO_REPRODUZ:
            texto = _texto_nao_reproduzido(saida, veredito)
            parcial = True
            comportamento = "resposta_parcial_marcada"
    uso = saida.uso
    if veredito is not None:
        uso = uso.somar(veredito.uso)
    chamadas = tuple(saida.chamadas)
    if veredito is not None:
        chamadas = chamadas + tuple(veredito.chamadas)
    return RespostaAgente(
        pergunta=saida.pergunta,
        resposta=texto,
        resposta_bruta=saida.bruto if (convertida or not saida.json_valido) else "",
        recusa=recusa,
        motivo_recusa=saida.motivo_recusa or "n/a",
        parcial=parcial,
        precisa_desambiguacao=comportamento == "pergunta_de_desambiguacao",
        nao_conciliada=nao_conciliada,
        comportamento=comportamento,
        cobertura=saida.cobertura,
        bases=saida.bases,
        citacoes=saida.citacoes,
        veredito_auditor=veredito.veredito if veredito is not None else None,
        violacoes=tuple(violacoes),
        convertida_em_recusa=convertida,
        chamadas=chamadas,
        uso=uso,
        parcial_por_teto=bool(
            saida.teto_ferramenta
            or saida.teto_iteracoes
            or (veredito is not None and (veredito.teto_ferramenta or veredito.teto_iteracoes))
        ),
        contexto_auditor=contexto,
        erro=saida.erro or (veredito.erro if veredito is not None else None),
        correcao_aplicada=bool(
            saida.correcao_aplicada
            or (veredito is not None and veredito.correcao_aplicada)
        ),
        correcao_resultado=(
            saida.correcao_resultado
            if saida.correcao_aplicada
            else (
                veredito.correcao_resultado
                if veredito is not None and veredito.correcao_aplicada
                else CORRECAO_NAO_NECESSARIA
            )
        ),
    )


# --------------------------------------------------------------------------- #
# Fábricas injetáveis (é o que mantém os testes sem rede e sem LLM)
# --------------------------------------------------------------------------- #

FabricaLLM = Callable[[str], BaseLLM]
FabricaFerramentas = Callable[[str], FerramentasDoAgente]


def config_para_agentes(config: Config) -> Config:
    """Sobe o teto de tokens de saída **só** para a camada de agentes.

    Medido no Gemini em 2026-08-12: com `GEMINI_MAX_TOKENS=512` — suficiente
    para a resposta curta do caminho de avaliação — o JSON do Investigador
    (afirmação + citações + rastro) é **cortado no meio**, e a saída truncada
    entra como `saida_fora_do_contrato_json`. O experimento passaria a medir o
    limite de tokens, não a orquestração.

    A alteração é local e não toca o `.env`: o caminho de avaliação E0–E3 roda
    com a configuração original, como a RNF11 exige. Teto maior não é gasto
    maior — a cobrança é por token gerado, e o que se compra aqui é o direito de
    o JSON fechar.
    """
    from dataclasses import replace

    if config.gemini_max_tokens >= AGENTES_MIN_TOKENS_SAIDA:
        return config
    return replace(config, gemini_max_tokens=AGENTES_MIN_TOKENS_SAIDA)


def fabrica_llm_padrao(
    config: Config, orcamento: ControleOrcamento | None = None
) -> FabricaLLM:
    """Um provedor por papel — instâncias separadas, contadores separados."""
    config_agentes = config_para_agentes(config)

    def fabricar(papel: str) -> BaseLLM:
        return LLMPonte(
            fabricar_provedor_llm(config_agentes),
            papel=papel,
            temperatura=config_agentes.temperatura,
            orcamento=orcamento,
        )

    return fabricar


def fabrica_ferramentas_padrao(
    config: Config,
    *,
    indice_cobertura: Any = None,
    recuperador: Any = None,
    leitor: Any = None,
    caminho_painel: Path | None = None,
    nomes: Sequence[str] = FERRAMENTAS_DISPONIVEIS,
    ao_chamar: ObservadorDeFerramenta | None = None,
) -> FabricaFerramentas:
    """Uma caixa por papel: o Auditor reexecuta com orçamento próprio (5.9.1).

    `nomes` escolhe o conjunto de ferramentas: as quatro do experimento por
    padrão, `FERRAMENTAS_DO_PRODUTO` no chat (§3.16). Índice, recuperador e
    leitor podem vir prontos do app, para a pergunta não carregar o Chroma
    duas vezes, uma por agente."""

    def fabricar(papel: str) -> FerramentasDoAgente:
        caixa = CaixaDeFerramentas(
            config,
            indice_cobertura=indice_cobertura,
            recuperador=recuperador,
            leitor=leitor,
            caminho_painel=caminho_painel,
        )
        return FerramentasDoAgente(caixa, papel, nomes, ao_chamar=ao_chamar)

    return fabricar


# --------------------------------------------------------------------------- #
# Os dois braços
# --------------------------------------------------------------------------- #


def responder_braco_a(
    pergunta: str,
    config: Config,
    *,
    fabrica_llm: FabricaLLM,
    fabrica_ferramentas: FabricaFerramentas,
) -> RespostaAgente:
    """Braço A: **um** agente com todas as ferramentas.

    Serve para medir se dividir em dois acrescenta algo. Nenhuma segunda
    passagem, `veredito_auditor` nulo — e é essa coluna nula que o cruzamento de
    5.9.3 usa para achar as discordâncias entre A e B.
    """
    ferramentas = fabrica_ferramentas(PAPEL_AGENTE_UNICO)
    llm = fabrica_llm(PAPEL_AGENTE_UNICO)
    saida = executar_investigador(
        pergunta, config, ferramentas, llm, papel=PAPEL_AGENTE_UNICO
    )
    violacoes = verificar_regras_agente(saida, ferramentas)
    if violacoes:
        saida = converter_em_recusa_agente(saida, violacoes)
    return consolidar(saida, violacoes=violacoes, convertida=bool(violacoes))


def responder_braco_b(
    pergunta: str,
    config: Config,
    *,
    fabrica_llm: FabricaLLM,
    fabrica_ferramentas: FabricaFerramentas,
) -> RespostaAgente:
    """Braço B: Investigador + Auditor, em `Process.sequential`, com isolamento.

    A ordem é fixa e a mensagem entre os dois é montada por código:

    1. o Investigador responde e registra o rastro;
    2. **RN01/RN02 são verificadas antes da auditoria** — auditar uma resposta
       que o código já descartou seria pagar uma chamada para conferir algo que
       não será publicado;
    3. saída que **não é afirmação de fato** (`dispensa_auditoria` — hoje, a
       pergunta de desambiguação da RN11) segue direto, sem rodada de Auditor e
       sem `veredito_auditor`, como já acontece quando a etapa 2 barra;
    4. `montar_contexto_auditor` filtra: afirmação e citações, nada mais;
    5. o Auditor reexecuta com **caixa de ferramentas própria** e devolve um dos
       três vereditos;
    6. `consolidar` aplica o veredito sem eleger vencedor.
    """
    ferramentas_investigador = fabrica_ferramentas(PAPEL_INVESTIGADOR)
    llm_investigador = fabrica_llm(PAPEL_INVESTIGADOR)
    # Spans do trace (5.12): no-op fora de uma consulta do chat, então o
    # experimento roda exatamente como antes.
    with observabilidade.etapa(
        "agente.investigador",
        tipo="agent",
        entrada=lambda: observabilidade.texto_livre(pergunta),
    ) as etapa:
        saida = executar_investigador(
            pergunta, config, ferramentas_investigador, llm_investigador
        )
        etapa.atualizar(saida=lambda: _resumo_para_trace(saida))
    with observabilidade.etapa("verificacao.rn01_rn02") as etapa:
        violacoes = verificar_regras_agente(saida, ferramentas_investigador)
        etapa.atualizar(saida={"violacoes": list(violacoes)})
    if violacoes:
        saida = converter_em_recusa_agente(saida, violacoes)
        return consolidar(saida, violacoes=violacoes, convertida=True)

    if dispensa_auditoria(saida):
        # Nem contexto, nem fábrica de LLM do Auditor, nem caixa de ferramentas
        # dele: a pergunta de desambiguação é o resultado do braço B tal como
        # saiu do Investigador.
        return consolidar(saida)

    contexto = montar_contexto_auditor(saida)
    ferramentas_auditor = fabrica_ferramentas(PAPEL_AUDITOR)
    llm_auditor = fabrica_llm(PAPEL_AUDITOR)
    with observabilidade.etapa(
        "agente.auditor",
        tipo="agent",
        entrada=lambda: {
            "afirmacao": observabilidade.texto_livre(contexto.afirmacao),
            "citacoes": list(contexto.citacoes),
        },
    ) as etapa:
        veredito = executar_auditor(contexto, config, ferramentas_auditor, llm_auditor)
        etapa.atualizar(
            saida=lambda: {
                "veredito": veredito.veredito,
                "justificativa": observabilidade.texto_livre(veredito.justificativa),
                "ferramentas": [c.ferramenta for c in veredito.chamadas],
                "chamadas_llm": veredito.uso.chamadas_llm,
                "custo_usd": round(veredito.uso.custo_usd, 6),
            }
        )
    return consolidar(saida, veredito=veredito, contexto=contexto)


def _resumo_para_trace(saida: SaidaInvestigador) -> dict:
    """O que o trace guarda do Investigador: decisão, fontes, uso — e o texto
    da afirmação só pela regra de texto livre (RN06)."""
    return {
        "comportamento": saida.comportamento,
        "cobertura": saida.cobertura,
        "afirmacao": observabilidade.texto_livre(saida.afirmacao),
        "citacoes": list(saida.citacoes),
        "ferramentas": [c.ferramenta for c in saida.chamadas],
        "chamadas_llm": saida.uso.chamadas_llm,
        "custo_usd": round(saida.uso.custo_usd, 6),
        "correcao": saida.correcao_resultado,
    }


# --------------------------------------------------------------------------- #
# Caminho do produto: guardrails em volta do braço (RNF11 §6)
# --------------------------------------------------------------------------- #


def responder_com_guardrails(
    pergunta: str,
    config: Config,
    *,
    fabrica_llm: FabricaLLM,
    fabrica_ferramentas: FabricaFerramentas,
    responder: Callable[..., RespostaAgente] | None = None,
) -> RespostaAgente:
    """O caminho interativo inteiro: entrada → braço → saída (spec 5.11, §6).

    **Por que isto é uma composição e não uma alteração dos braços.** A RNF11
    separa o produto do benchmark, e `responder_braco_a`/`responder_braco_b` são
    os braços do experimento de 5.9.3: o que eles medem é orquestração. Enfiar
    guardrail dentro deles faria o experimento medir orquestração + guardrail, e
    a comparação A×B deixaria de responder à pergunta que motivou o
    experimento. O produto compõe; o experimento continua puro.

    Três garantias que os testes travam:

    1. **Entrada bloqueada não chega a gastar.** A varredura roda antes de
       qualquer fábrica ser chamada — nenhum LLM, nenhuma ferramenta, custo
       zero. Um ataque não deve custar dinheiro para ser recusado.
    2. **O braço recebe o texto anonimizado**, nunca o original (RN06). É
       `texto_seguro` que entra no prompt, no rastro e no log.
    3. **Bloquear a saída não apaga o custo já incorrido.** O `uso` da resposta
       é preservado: a chamada aconteceu, e esconder isso corromperia a
       contabilidade de orçamento.
    """
    from src.seguranca import avaliar_entrada, avaliar_saida, texto_de_recusa

    executar = responder_braco_b if responder is None else responder
    scanners = tuple(config.guardrails_ativos)
    presidio = dict(
        presidio_habilitado=config.presidio_habilitado,
        presidio_idioma=config.presidio_idioma,
        presidio_modelo_spacy=config.presidio_modelo_spacy,
    )
    # Só `avaliar_entrada` aceita os kwargs de injeção ML — injeção é ataque de
    # ENTRADA, `avaliar_saida` nunca a verifica (ver docstring dela).
    entrada_kwargs = dict(
        presidio,
        prompt_guard_habilitado=config.prompt_guard_habilitado,
        prompt_guard_modelo=config.prompt_guard_modelo,
        prompt_guard_revisao=config.guardrails_modelo_injecao_revision,
        prompt_guard_limiar=config.guardrails_limiar_injection,
    )

    with observabilidade.etapa("guardrail.entrada", tipo="guardrail") as etapa:
        entrada = avaliar_entrada(pergunta, scanners, **entrada_kwargs)
        etapa.atualizar(saida=lambda: _resumo_guardrail_trace(entrada))
    if entrada.bloqueado:
        return RespostaAgente(
            pergunta=entrada.texto_seguro,
            resposta=texto_de_recusa(entrada),
            recusa=True,
            motivo_recusa=entrada.motivo,
            comportamento=COMPORTAMENTO_RECUSA,
            violacoes=tuple(
                f"guardrail_entrada:{achado.scanner}:{achado.subtipo}"
                for achado in entrada.achados
            ),
        )

    # RN07 no mesmo lugar da RN05, e pela mesma razão. Esta função se declara
    # "o caminho interativo inteiro" (§6) — e até 2026-08-25 ela era o único
    # portão do produto que NÃO verificava pergunta prospectiva. Enquanto a
    # camada de agentes não está ligada à interface o buraco é teórico; ligá-la
    # (etapa 11) o tornaria real, e a correção não pode depender de alguém
    # lembrar na hora. Custo zero: recusa antes de qualquer fábrica ser
    # chamada, como o ataque bloqueado da garantia (1).
    from src.projecao import (
        detectar_pergunta_prospectiva,
        recusa_de_ultimo_recurso,
    )

    achado_projecao = detectar_pergunta_prospectiva(entrada.texto_seguro)
    if achado_projecao is not None:
        projecao = recusa_de_ultimo_recurso(
            achado_projecao,
            motivo="a camada de agentes não atende a rota prospectiva",
        )
        return RespostaAgente(
            pergunta=entrada.texto_seguro,
            resposta=projecao.texto,
            recusa=True,
            motivo_recusa=achado_projecao.detalhe,
            comportamento=COMPORTAMENTO_RECUSA,
            violacoes=(
                f"rn07_projecao:{achado_projecao.scanner}:"
                f"{achado_projecao.subtipo}",
            ),
        )

    resposta = executar(
        entrada.texto_seguro,
        config,
        fabrica_llm=fabrica_llm,
        fabrica_ferramentas=fabrica_ferramentas,
    )

    with observabilidade.etapa("guardrail.saida", tipo="guardrail") as etapa:
        saida = avaliar_saida(resposta.resposta, scanners, **presidio)
        etapa.atualizar(saida=lambda: _resumo_guardrail_trace(saida))
    if not saida.bloqueado:
        # Ainda assim substitui pelo texto anonimizado: a RN06 vale para o que
        # sai, e a anonimização é idempotente quando não há o que anonimizar.
        return replace(resposta, resposta=saida.texto_seguro)
    return replace(
        resposta,
        resposta=texto_de_recusa(saida),
        recusa=True,
        motivo_recusa=saida.motivo,
        comportamento=COMPORTAMENTO_RECUSA,
        convertida_em_recusa=True,
        violacoes=resposta.violacoes
        + tuple(
            f"guardrail_saida:{achado.scanner}:{achado.subtipo}"
            for achado in saida.achados
        ),
    )


def _resumo_guardrail_trace(resultado: Any) -> dict:
    """Decisão e scanners do veredito, sem o detalhe (que pode citar o texto)."""
    return {
        "bloqueado": resultado.bloqueado,
        "achados": [f"{a.scanner}/{a.subtipo}" for a in resultado.achados],
        "entidades_pii_anonimizadas": len(resultado.entidades_pii),
    }


def registrar_evento_agentes(
    evento: dict, dir_logs: Path = DIR_LOGS_EXECUCOES, arquivo: str | None = None
) -> Path:
    """Atalho para o log JSONL da RNF08 — mesmo `fsync`, mesmo carimbo UTC."""
    return registrar_execucao(evento, dir_logs=dir_logs, arquivo=arquivo)


__all__ = [
    "CAMPOS_CONTEXTO_AUDITOR",
    "CLASSES_DE_FERRAMENTA",
    "COMPORTAMENTOS_SEM_AUDITORIA",
    "COMPORTAMENTO_DESAMBIGUACAO",
    "CORRECAO_BEM_SUCEDIDA",
    "CORRECAO_CORTADA_POR_TETO",
    "CORRECAO_FALHOU",
    "CORRECAO_NAO_NECESSARIA",
    "EXEMPLO_REACT",
    "FERRAMENTAS_DE_DADO",
    "ChamadaFerramenta",
    "ContextoAuditor",
    "ControleOrcamento",
    "FerramentasDoAgente",
    "LLMComTetoRigido",
    "LLMPonte",
    "MARGEM_PEDIDO_RESPOSTA_FINAL",
    "MARCADORES_RASTRO",
    "OrcamentoAgentesExcedidoError",
    "PAPEL_AGENTE_UNICO",
    "PAPEL_AUDITOR",
    "PAPEL_INVESTIGADOR",
    "RespostaAgente",
    "SaidaInvestigador",
    "UsoAgente",
    "VEREDITOS",
    "VEREDITO_CONFIRMA",
    "VEREDITO_CONTESTA",
    "VEREDITO_NAO_REPRODUZ",
    "VERSAO_PROMPT_AGENTES",
    "VIOLACAO_RN01_CITACAO_SEM_LASTRO",
    "VIOLACAO_RN01_SEM_CITACAO",
    "VIOLACAO_RN02_RECUSA_COM_VALOR",
    "VIOLACAO_RN02_SEM_LASTRO",
    "VIOLACAO_SAIDA_ILEGIVEL",
    "AuditoriaNaoAplicavelError",
    "TetoIteracoesExcedidoError",
    "VazamentoDeRastroError",
    "VereditoAuditor",
    "achatar_mensagens",
    "conferir_isolamento",
    "configurar_ambiente_crewai",
    "consolidar",
    "construir_ferramentas",
    "consultou_ferramenta_de_dado",
    "converter_em_recusa_agente",
    "declara_dado",
    "dispensa_auditoria",
    "executar_auditor",
    "executar_investigador",
    "extrair_json",
    "instrucao_corretiva_auditor",
    "instrucao_corretiva_investigador",
    "precisa_correcao_de_dado",
    "fabrica_ferramentas_padrao",
    "fabrica_llm_padrao",
    "fragmentos_de_rastro",
    "instrucao_auditor",
    "instrucao_investigador",
    "montar_contexto_auditor",
    "registrar_evento_agentes",
    "responder_braco_a",
    "responder_braco_b",
    "responder_com_guardrails",
    "valores_monetarios_do_texto",
    "verificar_regras_agente",
]
