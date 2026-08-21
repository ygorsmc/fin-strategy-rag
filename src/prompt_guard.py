"""Llama Prompt Guard 2 como detector de injeção ML (spec 5.11) — camada
ADICIONAL ao regex determinístico de `src.seguranca.detectar_injecao`, nunca
substituto.

**Medido antes de integrar**, contra `conjunto_padrao/ataques.csv` e as 55
perguntas congeladas (dev + teste):

- **0/55 falso positivo** nas perguntas legítimas — mesmo padrão de contraprova
  exigido de todo scanner desta camada.
- **Não cobre a família `topico` (11 ataques).** Esperado, não defeito: Prompt
  Guard 2 classifica *tentativa de sobrepor instrução*, não *pedido de
  recomendação de investimento* — são categorias diferentes (RN05 × injeção).
  `detectar_topico_proibido` continua sendo o único scanner dessa família.
- **Da família `injecao` (9 ataques), pega 5/9 sozinho** — ATK012, ATK013,
  ATK017, ATK019, ATK020. Perde ATK014/015/016/018 (redefinição de papel,
  extração de prompt, "modo desenvolvedor" — frases curtas de um só turno,
  sem o contexto de documento de terceiro para o qual o modelo foi treinado).
  Todos os 9 já são pegos pelo regex. **O valor de somar as duas defesas não
  é o placar nesta amostra fixa — é a paráfrase e a ofuscação que NENHUM
  padrão fixo cobre, em tráfego real.** Por isso a composição é OR: bloqueia
  se o regex OU o classificador disparar, nunca só um substituindo o outro.

**Pesos GATED.** `meta-llama/Llama-Prompt-Guard-2-86M` exige licença aceita na
conta Hugging Face e `HF_TOKEN` — mas só no BUILD, para baixar os pesos uma
vez. Runtime carrega com `local_files_only=True`: confirmado que funciona sem
token nenhum quando os pesos já estão no cache/imagem (RNF12).
"""

from __future__ import annotations

from functools import lru_cache

from src.seguranca import Achado

MODELO_PADRAO = "meta-llama/Llama-Prompt-Guard-2-86M"
# SHA do commit baixado e validado em 2026-08-21 (RNF01: pinar ao que foi
# medido). Vazio = build não reprodutível, per o comentário original em
# src/config.py — aqui é o valor que fecha essa lacuna.
REVISAO_PADRAO = "a8ded8e697ce7c355e395a0df51f94adb4a2fd27"
LIMIAR_PADRAO = 0.85
_ROTULO_MALICIOSO = "LABEL_1"


class PromptGuardIndisponivelError(RuntimeError):
    """Falha fechada (RNF03): dizer exatamente o que falta."""


@lru_cache(maxsize=4)
def _classificador(modelo: str, revisao: str):
    try:
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            pipeline,
        )
    except ImportError as exc:
        raise PromptGuardIndisponivelError(
            "PROMPT_GUARD_HABILITADO=true mas transformers/torch não estão "
            "instalados. Instale requirements-guardrails.txt."
        ) from exc
    revisao_kwarg = {"revision": revisao} if revisao else {}
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            modelo, local_files_only=True, **revisao_kwarg
        )
        classificador = AutoModelForSequenceClassification.from_pretrained(
            modelo, local_files_only=True, **revisao_kwarg
        )
    except OSError as exc:
        raise PromptGuardIndisponivelError(
            f"PROMPT_GUARD_HABILITADO=true mas os pesos de {modelo!r} não "
            "estão no cache local. Baixe uma vez em BUILD com HF_TOKEN "
            "(licença Meta aceita em huggingface.co/" + modelo + "), nunca "
            "em runtime (RNF12)."
        ) from exc
    return pipeline("text-classification", model=classificador, tokenizer=tokenizer)


def prompt_guard_disponivel(
    modelo: str = MODELO_PADRAO, revisao: str = REVISAO_PADRAO
) -> bool:
    """Sonda sem lançar — diagnóstico/UI, nunca no caminho de decisão."""
    try:
        _classificador(modelo, revisao)
        return True
    except PromptGuardIndisponivelError:
        return False


def avaliar_injecao_ml(
    texto: str,
    *,
    modelo: str = MODELO_PADRAO,
    revisao: str = REVISAO_PADRAO,
    limiar: float = LIMIAR_PADRAO,
) -> Achado | None:
    """`None` se benigno ou abaixo do limiar; `Achado` de injeção caso contrário.

    Levanta `PromptGuardIndisponivelError` se o modelo faltar — só é chamado
    quando `prompt_guard_habilitado=True` foi ligado explicitamente, e nesse
    caso a ausência é erro de configuração, não degradação silenciosa.
    """
    if not isinstance(texto, str) or not texto.strip():
        return None
    classificador = _classificador(modelo, revisao)
    resultado = classificador(texto, truncation=True, max_length=512)[0]
    if resultado["label"] != _ROTULO_MALICIOSO or resultado["score"] < limiar:
        return None
    return Achado(
        scanner="injection",
        subtipo="injecao_prompt",
        detalhe=(
            "classificador de injeção (Llama Prompt Guard 2) sinalizou "
            f"conteúdo malicioso (score {resultado['score']:.3f})"
        ),
    )
