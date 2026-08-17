"""Utilitários de segurança e auditoria dos gates externos.

O journal é append-only e registra o instante imediatamente anterior e
posterior a cada chamada. Ele melhora a auditoria de custo, mas não oferece
semântica exactly-once: uma interrupção depois da resposta do provedor e antes
do segundo registro deixa o custo daquela chamada indeterminado.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote


_PADROES_CREDENCIAL = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(
        r"(?i)((?:api[-_]?key|x-goog-api-key|subscription[-_]?key)"
        r"\s*[=:]\s*)[^\s,;&]+"
    ),
    re.compile(r"(?i)([?&](?:key|api[-_]?key)=)[^&#\s]+"),
)


def sanitizar_evidencia(
    texto: object,
    *,
    segredos: Iterable[str] = (),
    limite: int = 700,
) -> str:
    """Remove credenciais conhecidas/padrões comuns e neutraliza Markdown."""
    saida = str(texto)
    for segredo in segredos:
        if not segredo:
            continue
        variantes = {segredo, quote(segredo, safe="")}
        for variante in sorted(variantes, key=len, reverse=True):
            if variante:
                saida = saida.replace(variante, "[REDACTED]")
    for padrao in _PADROES_CREDENCIAL:
        saida = padrao.sub(r"\1[REDACTED]", saida)
    saida = (
        saida.replace("|", "\\|")
        .replace("`", "\\`")
        .replace("\r", " ")
        .replace("\n", " ")
    )
    return saida[:limite]


def resumir_excecao(
    exc: BaseException,
    *,
    segredos: Iterable[str] = (),
) -> str:
    """Resume falha externa sem persistir corpo/mensagem potencialmente refletida."""
    partes = [type(exc).__name__]
    for rotulo, atributo in (
        ("status", "status_code"),
        ("code", "code"),
        ("request_id", "request_id"),
    ):
        valor = getattr(exc, atributo, None)
        if isinstance(valor, (str, int)) and str(valor).strip():
            partes.append(f"{rotulo}={valor}")
    return sanitizar_evidencia("; ".join(partes), segredos=segredos)


def custo_valido(valor: object) -> bool:
    """Retorna True apenas para custo numérico, finito e não negativo."""
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(float(valor))
        and float(valor) >= 0
    )


def registrar_evento(caminho: Path, evento: dict[str, object]) -> None:
    """Acrescenta e força em disco um evento pequeno, sem prompts/respostas."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    registro = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **evento,
    }
    linha = json.dumps(
        registro,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with caminho.open("a", encoding="utf-8") as arquivo:
        arquivo.write(linha + "\n")
        arquivo.flush()
        os.fsync(arquivo.fileno())
