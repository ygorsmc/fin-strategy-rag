"""Observabilidade do caminho interativo (spec 5.12): traces no Langfuse.

Uma consulta do chat vira um trace, e cada etapa vira uma observação filha:
guardrail de entrada, roteamento, recuperação, chamada ao LLM (com tokens e
custo), ferramentas de agente e guardrail de saída. O Langfuse mede a
latência de cada uma pela duração do span.

**Papel, e o que ele não é.** O Langfuse serve para o diagnóstico ao vivo:
qual etapa domina a latência, qual chamada custou mais, qual ferramenta o
agente chamou. Ele **não** é o registro do benchmark. A camada gratuita
retém 30 dias, e o registro reprodutível das avaliações continua sendo o
JSONL versionado (RNF08).

Contratos, cada um travado em `tests/test_observabilidade.py`:

1. **Sem chave, nada.** Sem `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY`, o
   módulo não importa o SDK e todas as funções viram no-op. O modo
   demonstração sobe sem segredo (RNF12).
2. **Só dentro de uma consulta.** `etapa` e a geração só emitem com uma
   `consulta` aberta no contexto. O caminho de avaliação nunca abre uma, e
   por isso o benchmark não vira trace nem com chave configurada (AGENTS §6).
3. **RN06 no ponto de saída.** Entrada, saída e metadados passam pelo redator
   central (`redigir_dados_pessoais`), instalado como a máscara do próprio
   SDK. Exceção é registrada **só pelo tipo**. O OpenTelemetry grava a
   mensagem e a pilha num evento que a máscara não alcança (medido no SDK
   5.0.2), e a mensagem pode carregar o texto do usuário.
4. **Só os spans deste módulo saem.** O provider do OpenTelemetry é próprio,
   nunca o global, e o filtro de export aceita só spans do SDK do Langfuse.
   ChromaDB e CrewAI não pegam carona no envio.
5. **Rastrear nunca derruba a resposta.** Falha do SDK vira aviso no log, e
   a consulta segue sem trace.
"""

from __future__ import annotations

import contextvars
import logging
import os
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)

# Um campo de texto acima disto é cortado no trace, com a contagem do que
# saiu. O prompt de geração com cinco trechos fica bem abaixo; o limite existe
# para um resultado de ferramenta desproporcional não virar um trace de MB.
TAMANHO_MAXIMO_TEXTO = 30_000

# Exceções que o Streamlit usa como controle de fluxo (`st.rerun`, `st.stop`).
# Atravessar uma etapa com elas não é falha da etapa.
_CONTROLE_DE_FLUXO = frozenset({"RerunException", "StopException"})

_EM_CONSULTA: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "observabilidade_em_consulta", default=False
)
_EM_GERACAO: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "observabilidade_em_geracao", default=False
)


@dataclass(frozen=True)
class Estado:
    """Se o rastreamento está ligado e, se não estiver, por quê.

    A interface exibe isto. Trace que some sem aviso é o defeito que o
    `OTEL_SDK_DISABLED` do CrewAI causaria, e o motivo precisa aparecer.
    """

    ativo: bool
    motivo: str
    host: str = ""


_cliente: Any = None
_chave_publica: str = ""
_estado = Estado(False, "não configurado")
# Ids dos últimos traces fechados, para um script conferir no servidor que
# eles chegaram. Sobrevive a reconfigurar o cliente.
_TRACES_RECENTES: deque[tuple[str, str]] = deque(maxlen=200)


def estado() -> Estado:
    return _estado


def traces_recentes() -> list[tuple[str, str]]:
    """(nome, id do trace) das consultas fechadas, da mais antiga à mais nova."""
    return list(_TRACES_RECENTES)


# --------------------------------------------------------------------------- #
# Redação (RN06)
# --------------------------------------------------------------------------- #


def _truncar(texto: str) -> str:
    if len(texto) <= TAMANHO_MAXIMO_TEXTO:
        return texto
    omitidos = len(texto) - TAMANHO_MAXIMO_TEXTO
    return texto[:TAMANHO_MAXIMO_TEXTO] + f"\n[... {omitidos} caracteres omitidos no trace]"


def redigir(valor: Any) -> Any:
    """Aplica o redator central a toda string, em qualquer profundidade."""
    from src.geracao import redigir_dados_pessoais

    if isinstance(valor, str):
        return _truncar(redigir_dados_pessoais(valor))
    if valor is None or isinstance(valor, (bool, int, float)):
        return valor
    if isinstance(valor, Mapping):
        return {str(chave): redigir(item) for chave, item in valor.items()}
    if isinstance(valor, (list, tuple, set, frozenset)):
        return [redigir(item) for item in valor]
    return _truncar(redigir_dados_pessoais(str(valor)))


def _mascara(*, data: Any, **_: Any) -> Any:
    return redigir(data)


# --------------------------------------------------------------------------- #
# Ciclo de vida do cliente
# --------------------------------------------------------------------------- #


def configurar(config: Any, *, exportador: Any = None) -> Estado:
    """Liga o rastreamento conforme a configuração e devolve o estado.

    ``exportador`` substitui o envio HTTP por outro `SpanExporter` do
    OpenTelemetry. Os testes passam um exportador em memória e inspecionam
    exatamente o que sairia para o Langfuse.
    """
    global _cliente, _chave_publica, _estado

    desligar()
    publica = getattr(config, "langfuse_public_key", "") or ""
    secreta = getattr(config, "langfuse_secret_key", "") or ""
    host = getattr(config, "langfuse_host", "") or ""
    if not (publica and secreta):
        _estado = Estado(False, "sem chave (LANGFUSE_PUBLIC_KEY e LANGFUSE_SECRET_KEY)")
        return _estado
    if os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true":
        # O SDK do OpenTelemetry devolve tracer nulo com isto ligado, e o
        # Langfuse se apoia nele: sem este aviso, o trace sumiria calado.
        _estado = Estado(False, "OTEL_SDK_DISABLED=true desliga o OpenTelemetry, e o Langfuse com ele", host)
        LOGGER.warning("Langfuse desligado: %s", _estado.motivo)
        return _estado

    from src.config import endpoint_langfuse_e_https

    if not endpoint_langfuse_e_https(host):
        _estado = Estado(False, "LANGFUSE_HOST não é HTTPS", host)
        return _estado
    try:
        from langfuse import Langfuse
        from langfuse.span_filter import is_langfuse_span
        from opentelemetry.sdk.trace import TracerProvider
    except ImportError:
        _estado = Estado(False, "pacote langfuse não instalado", host)
        return _estado
    try:
        _cliente = Langfuse(
            public_key=publica,
            secret_key=secreta,
            base_url=host,
            tracer_provider=TracerProvider(),
            should_export_span=is_langfuse_span,
            mask=_mascara,
            span_exporter=exportador,
        )
    except Exception as exc:  # contrato 5: rastrear nunca derruba o app
        LOGGER.warning("Langfuse não iniciou (%s); seguindo sem trace.", type(exc).__name__)
        _cliente = None
        _estado = Estado(False, f"falha ao iniciar o cliente ({type(exc).__name__})", host)
        return _estado
    _chave_publica = publica
    _estado = Estado(True, "ativo", host)
    return _estado


def descarregar() -> None:
    """Envia o que estiver no buffer. Scripts curtos chamam isto ao sair."""
    if _cliente is None:
        return
    try:
        _cliente.flush()
    except Exception as exc:
        LOGGER.warning("Langfuse: flush falhou (%s).", type(exc).__name__)


def desligar() -> None:
    """Descarrega, encerra o cliente e volta ao estado não configurado."""
    global _cliente, _chave_publica, _estado

    if _cliente is not None:
        try:
            _cliente.shutdown()
        except Exception as exc:
            LOGGER.warning("Langfuse: shutdown falhou (%s).", type(exc).__name__)
        try:
            # O SDK guarda um gerenciador por chave pública, e reconfigurar com
            # a mesma chave reaproveitaria o exportador antigo.
            from langfuse._client.resource_manager import LangfuseResourceManager

            with LangfuseResourceManager._lock:
                LangfuseResourceManager._instances.pop(_chave_publica, None)
        except Exception:
            pass
    _cliente = None
    _chave_publica = ""
    _estado = Estado(False, "não configurado")


# --------------------------------------------------------------------------- #
# Observações
# --------------------------------------------------------------------------- #


class Observacao:
    """Envelope de uma observação aberta: o chamador só atualiza campos.

    Cada campo de `atualizar` aceita o valor ou uma função sem argumentos que
    o produz. A função só roda com o rastreamento ligado, e uma falha dela
    vira aviso no log (contrato 5): montar o resumo de um trace não pode
    derrubar a resposta, nem custar nada com o rastreamento desligado.
    """

    def __init__(self, sdk: Any) -> None:
        self._sdk = sdk

    def atualizar(
        self,
        *,
        entrada: Any = None,
        saida: Any = None,
        metadados: Any = None,
    ) -> None:
        campos: dict[str, Any] = {}
        try:
            for chave, valor in (("input", entrada), ("output", saida), ("metadata", metadados)):
                valor = valor() if callable(valor) else valor
                if valor is not None:
                    campos[chave] = dict(valor) if chave == "metadata" else valor
        except Exception as exc:
            LOGGER.warning("Langfuse: resumo da observação falhou (%s).", type(exc).__name__)
            return
        if not campos:
            return
        try:
            self._sdk.update(**campos)
        except Exception as exc:
            LOGGER.warning("Langfuse: update falhou (%s).", type(exc).__name__)

    def concluir_geracao(self, bruta: Any) -> None:
        """Registra modelo, saída, tokens e custo de uma `RespostaBrutaLLM`."""
        uso = getattr(bruta, "uso", None)
        campos: dict[str, Any] = {"output": getattr(bruta, "texto", None)}
        modelo = getattr(bruta, "modelo", "") or getattr(uso, "modelo", "")
        if modelo:
            campos["model"] = str(modelo)
        if uso is not None:
            entrada = int(uso.tokens_entrada)
            saida = int(uso.tokens_saida)
            # `total` explícito: sem ele o Langfuse soma todas as chaves, e
            # raciocínio e cache já estão dentro de saída e entrada.
            campos["usage_details"] = {"input": entrada, "output": saida, "total": entrada + saida}
            if uso.custo_usd is not None:
                campos["cost_details"] = {"total": float(uso.custo_usd)}
            campos["metadata"] = {
                "tokens_raciocinio": int(uso.tokens_raciocinio),
                "tokens_entrada_cache_hit": int(uso.tokens_entrada_cache_hit),
                "latencia_provedor_s": round(float(uso.latencia_s), 3),
                "custo_auditavel": uso.custo_usd is not None,
            }
        try:
            self._sdk.update(**campos)
        except Exception as exc:
            LOGGER.warning("Langfuse: update da geração falhou (%s).", type(exc).__name__)

    def _marcar_erro(self, exc: BaseException) -> None:
        try:
            # Só o tipo: a mensagem pode trazer o texto do usuário (contrato 3).
            self._sdk.update(level="ERROR", status_message=type(exc).__name__)
        except Exception:
            pass


class _ObservacaoNula(Observacao):
    def __init__(self) -> None:
        super().__init__(None)

    def atualizar(self, **_: Any) -> None:
        return None

    def concluir_geracao(self, bruta: Any) -> None:
        return None

    def _marcar_erro(self, exc: BaseException) -> None:
        return None


_NULA = _ObservacaoNula()


@contextmanager
def _observacao(nome: str, tipo: str, entrada: Any, metadados: Any) -> Iterator[Observacao]:
    try:
        # Entrada e metadados também podem chegar como função (ver `Observacao`).
        entrada = entrada() if callable(entrada) else entrada
        metadados = metadados() if callable(metadados) else metadados
        gerenciador = _cliente.start_as_current_observation(
            as_type=tipo,
            name=nome,
            input=entrada,
            metadata=dict(metadados) if metadados is not None else None,
        )
        sdk = gerenciador.__enter__()
    except Exception as exc:
        LOGGER.warning("Langfuse: não abriu a observação %s (%s).", nome, type(exc).__name__)
        yield _NULA
        return
    observacao = Observacao(sdk)
    erro: BaseException | None = None
    try:
        yield observacao
    except BaseException as exc:
        # A exceção não atravessa o span do OpenTelemetry: se atravessasse,
        # mensagem e pilha sairiam num evento sem máscara (contrato 3).
        erro = exc
        if type(exc).__name__ not in _CONTROLE_DE_FLUXO:
            observacao._marcar_erro(exc)
    finally:
        try:
            gerenciador.__exit__(None, None, None)
        except Exception as exc:
            LOGGER.warning("Langfuse: não fechou a observação %s (%s).", nome, type(exc).__name__)
    if erro is not None:
        raise erro


@contextmanager
def etapa(
    nome: str,
    *,
    tipo: str = "span",
    entrada: Any = None,
    metadados: Any = None,
) -> Iterator[Observacao]:
    """Uma etapa da consulta aberta. Fora de consulta, ou sem cliente, é no-op.

    ``tipo`` é o `as_type` do Langfuse: span, guardrail, retriever, tool,
    agent, chain ou generation.
    """
    if _cliente is None or not _EM_CONSULTA.get():
        yield _NULA
        return
    with _observacao(nome, tipo, entrada, metadados) as observacao:
        yield observacao


@contextmanager
def consulta(
    nome: str,
    *,
    sessao: str | None = None,
    tags: Sequence[str] = (),
    metadados: Mapping[str, Any] | None = None,
) -> Iterator[Observacao]:
    """Abre o trace de uma consulta do caminho interativo.

    A entrada é registrada depois, pelo chamador, quando já existe o texto
    anonimizado pelo guardrail. A pergunta crua nunca é argumento daqui.
    """
    if _cliente is None:
        yield _NULA
        return
    token = _EM_CONSULTA.set(True)
    try:
        try:
            from langfuse import propagate_attributes

            atributos = propagate_attributes(
                session_id=sessao, tags=[str(t) for t in tags] or None, trace_name=nome
            )
            atributos.__enter__()
        except Exception as exc:
            LOGGER.warning("Langfuse: atributos do trace falharam (%s).", type(exc).__name__)
            atributos = None
        try:
            with _observacao(nome, "chain", None, metadados) as raiz:
                try:
                    yield raiz
                finally:
                    id_trace = getattr(raiz._sdk, "trace_id", None)
                    if id_trace:
                        _TRACES_RECENTES.append((nome, str(id_trace)))
        finally:
            if atributos is not None:
                try:
                    atributos.__exit__(None, None, None)
                except Exception:
                    pass
    finally:
        _EM_CONSULTA.reset(token)


def observar_geracao(metodo: Callable[..., Any]) -> Callable[..., Any]:
    """Envolve `gerar`/`gerar_texto` de um provedor numa observação `generation`.

    Instalado por `ProvedorLLM.__init_subclass__`, de modo que todo provedor
    plugável (RNF06) é rastreado sem mudar de tipo. O tipo entra na
    identidade da avaliação (`src/avaliacao.py`), e um envelope o mudaria.
    Uma geração dentro de outra, como `gerar_texto` delegando em `gerar`,
    não abre segunda observação.
    """
    if getattr(metodo, "_observado", False):
        return metodo

    @wraps(metodo)
    def envolvido(self: Any, *args: Any, **kwargs: Any) -> Any:
        if _cliente is None or not _EM_CONSULTA.get() or _EM_GERACAO.get():
            return metodo(self, *args, **kwargs)
        sistema = args[0] if len(args) > 0 else kwargs.get("prompt_sistema")
        usuario = args[1] if len(args) > 1 else kwargs.get("prompt_usuario")
        temperatura = args[2] if len(args) > 2 else kwargs.get("temperatura", 0.0)
        token = _EM_GERACAO.set(True)
        try:
            with _observacao(
                f"llm.{getattr(self, 'nome', type(self).__name__)}",
                "generation",
                [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                {"metodo": metodo.__name__, "temperatura": temperatura},
            ) as observacao:
                bruta = metodo(self, *args, **kwargs)
                observacao.concluir_geracao(bruta)
                return bruta
        finally:
            _EM_GERACAO.reset(token)

    envolvido._observado = True  # type: ignore[attr-defined]
    return envolvido
