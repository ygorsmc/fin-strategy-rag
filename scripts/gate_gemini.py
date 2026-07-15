"""Gate Gemini — smoke test explícito do provedor de geração via API.

Este gate é separado do Gate L1 porque faz chamadas externas e registra custo
estimado. Não acessa Azure e não embeda documentos.

Uso:
    python scripts/gate_gemini.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.config import Config, carregar_config  # noqa: E402
from src.geracao import PROMPT_SISTEMA, fabricar_provedor_llm  # noqa: E402

CAMINHO_RELATORIO = RAIZ / "resultados" / "gate_gemini.md"


def _validar_fundamentada(objeto: object) -> None:
    esperado = {
        "resposta": "26,6%",
        "recusa": False,
        "motivo_recusa": None,
        "citacoes": [
            {
                "empresa": "BTG",
                "documento": "btg_release_1T2026",
                "trimestre": "1T2026",
                "pagina": 6,
            }
        ],
    }
    if objeto != esperado and not (
        isinstance(objeto, dict)
        and objeto.get("recusa") is False
        and isinstance(objeto.get("resposta"), str)
        and "26,6%" in objeto["resposta"]
        and objeto.get("motivo_recusa") is None
        and objeto.get("citacoes") == esperado["citacoes"]
    ):
        raise RuntimeError(f"resposta fundamentada inesperada: {objeto!r}")


def _validar_recusa(objeto: object) -> None:
    if not isinstance(objeto, dict):
        raise RuntimeError("recusa não é um objeto JSON")
    if (
        objeto.get("resposta") is not None
        or objeto.get("recusa") is not True
        or objeto.get("citacoes") != []
        or not isinstance(objeto.get("motivo_recusa"), str)
        or not objeto["motivo_recusa"].strip()
    ):
        raise RuntimeError(f"contrato RN02 inválido: {objeto!r}")


def _prompt(pergunta: str) -> str:
    return f"""TRECHOS:
[BTG | btg_release_1T2026 | 1T2026 | pág. 6]
O ROAE ajustado anualizado foi de 26,6% no 1T2026.

PERGUNTA:
{pergunta}"""


def executar_gate_gemini(config: Config | None = None) -> bool:
    config = config or carregar_config()
    inicio_utc = datetime.now(timezone.utc)
    passou = False
    evidencia = ""
    try:
        if config.llm_provider != "gemini":
            raise RuntimeError(
                f"LLM_PROVIDER deve ser gemini para este gate: {config.llm_provider!r}"
            )
        provedor = fabricar_provedor_llm(config)
        inicio = perf_counter()
        fundamentada = provedor.gerar(
            PROMPT_SISTEMA,
            _prompt("Qual foi o ROAE ajustado anualizado do BTG no 1T2026?"),
            temperatura=0.0,
        )
        _validar_fundamentada(json.loads(fundamentada.texto))
        recusa = provedor.gerar(
            PROMPT_SISTEMA,
            _prompt("Qual foi a receita do Nubank no 1T2026?"),
            temperatura=0.0,
        )
        _validar_recusa(json.loads(recusa.texto))
        latencia = perf_counter() - inicio
        tokens_entrada = (
            fundamentada.uso.tokens_entrada + recusa.uso.tokens_entrada
        )
        tokens_saida = fundamentada.uso.tokens_saida + recusa.uso.tokens_saida
        custo = fundamentada.uso.custo_usd + recusa.uso.custo_usd
        evidencia = (
            f"{fundamentada.modelo}; resposta factual/citação + recusa RN02 válidas; "
            f"tokens={tokens_entrada}+{tokens_saida}; latência={latencia:.3f}s; "
            f"custo estimado=US$ {custo:.6f}"
        )
        passou = True
    except Exception as exc:
        evidencia = f"{type(exc).__name__}: {exc}"
    fim_utc = datetime.now(timezone.utc)

    CAMINHO_RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_RELATORIO.write_text(
        f"""# Gate Gemini — geração via API

- **Início (UTC):** {inicio_utc.isoformat()}
- **Fim (UTC):** {fim_utc.isoformat()}
- **Resultado:** {"✅ PASSOU" if passou else "❌ FALHOU"}
- **Azure:** não utilizado
- **Provedor/modelo configurado:** LLM_PROVIDER={config.llm_provider} /
  {config.gemini_modelo_llm}

## Evidência

{evidencia.replace("|", "\\|")}

O custo é estimado pelos preços configurados em
GEMINI_PRECO_ENTRADA_USD_MILHAO e GEMINI_PRECO_SAIDA_USD_MILHAO.
""",
        encoding="utf-8",
    )
    print(f"Gate Gemini: {'PASSOU' if passou else 'FALHOU'}")
    print(f"Relatório: {CAMINHO_RELATORIO}")
    return passou


if __name__ == "__main__":
    raise SystemExit(0 if executar_gate_gemini() else 1)
