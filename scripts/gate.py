"""Gate G1 — verificação opcional de Azure no pré-deploy (seção 5.7).

Tenta uma chamada mínima de LLM e de embeddings no Azure OpenAI. Registra a
evidência (sucesso ou erro literal, ex. `RequestDisallowedByAzure`) em
`resultados/gate.md`. O desenvolvimento usa primeiro o Gate L1 local em
`scripts/gate_local.py`; este script não cria recurso nem faz deploy.

Uso:
    python scripts/gate.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.config import Config, carregar_config  # noqa: E402

CAMINHO_RELATORIO = RAIZ / "resultados" / "gate.md"


def _testar_azure(config: Config, alvo: str) -> tuple[bool, str]:
    """Uma chamada mínima ao deployment de LLM ou de embeddings.

    Devolve (passou, evidência) — a evidência é a resposta truncada ou o texto
    literal do erro, que é o que vai para o relatório (evidência, não alegação).
    """
    faltando = [
        n
        for n, v in (
            ("AZURE_OPENAI_ENDPOINT", config.azure_openai_endpoint),
            ("AZURE_OPENAI_API_KEY", config.azure_openai_api_key),
            ("AZURE_OPENAI_API_VERSION", config.azure_openai_api_version),
        )
        if not v
    ]
    if faltando:
        return False, f"não configurado — variáveis ausentes no .env: {faltando}"
    try:
        from openai import AzureOpenAI

        cliente = AzureOpenAI(
            azure_endpoint=config.azure_openai_endpoint,
            api_key=config.azure_openai_api_key,
            api_version=config.azure_openai_api_version,
        )
        if alvo == "llm":
            if not config.azure_openai_deployment_llm:
                return False, "AZURE_OPENAI_DEPLOYMENT_LLM ausente no .env"
            r = cliente.chat.completions.create(
                model=config.azure_openai_deployment_llm,
                messages=[{"role": "user", "content": "Responda apenas: ok"}],
                max_tokens=5,
                temperature=0,
            )
            return True, f"chat.completions ok — resposta: {r.choices[0].message.content!r}"
        if not config.azure_openai_deployment_embedding:
            return False, "AZURE_OPENAI_DEPLOYMENT_EMBEDDING ausente no .env"
        r = cliente.embeddings.create(
            model=config.azure_openai_deployment_embedding, input=["teste"]
        )
        return True, f"embeddings ok — dimensão: {len(r.data[0].embedding)}"
    except Exception as exc:  # a mensagem literal do erro É a evidência
        return False, f"{type(exc).__name__}: {exc}"


def _ramo_fallback(config: Config) -> str:
    if config.llm_provider == "gemini":
        return "gemini API (GEMINI_API_KEY/GOOGLE_API_KEY presente)"
    if config.llm_provider == "ollama":
        return "ollama local (sem API paga)"
    if config.openai_api_key:
        return "openai (OPENAI_API_KEY presente)"
    if config.deepseek_api_key:
        return "deepseek (DEEPSEEK_API_KEY presente)"
    return (
        "NENHUM fallback configurado — defina OPENAI_API_KEY ou "
        "DEEPSEEK_API_KEY no .env antes da etapa de geração"
    )


def executar_gate(config: Config | None = None) -> bool:
    config = config or carregar_config()
    agora = datetime.now(timezone.utc)
    llm_ok, llm_evidencia = _testar_azure(config, "llm")
    emb_ok, emb_evidencia = _testar_azure(config, "embeddings")
    passou = llm_ok and emb_ok

    if passou:
        decisao = (
            "**Ramo A ativo:** Azure OpenAI Service para LLM e embeddings "
            "(`LLM_PROVIDER=azure_openai`, `EMBEDDING_PROVIDER=azure_openai`)."
        )
    else:
        decisao = (
            "**Ramo B ativo (fallback documentado, seção 5.7 da spec):** "
            f"inferência via {_ramo_fallback(config)}; embeddings "
            f"via `EMBEDDING_PROVIDER={config.embedding_provider}`. "
            "Nenhum deploy Azure é necessário para desenvolvimento ou avaliação; "
            "os créditos permanecem preservados até uma decisão explícita de publicação."
        )

    CAMINHO_RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_RELATORIO.write_text(
        f"""# Gate G1 — recurso de inferência (seção 5.7 da especificacao.md)

- **Data/hora (UTC):** {agora.isoformat()}
- **Resultado:** {"✅ PASSOU" if passou else "❌ FALHOU / não disponível"}

## Evidências

| Teste | Status | Evidência |
|-------|--------|-----------|
| Azure OpenAI — LLM | {"✅" if llm_ok else "❌"} | `{llm_evidencia}` |
| Azure OpenAI — Embeddings | {"✅" if emb_ok else "❌"} | `{emb_evidencia}` |

## Decisão de ramo

{decisao}

> Registro exigido pelo AGENTS.md (etapa 1): evidência, não alegação. Este
> arquivo é regenerado a cada execução de `scripts/gate.py`.
""",
        encoding="utf-8",
    )
    print(f"Gate G1: {'PASSOU' if passou else 'FALHOU (fallback documentado)'}")
    print(f"Relatório: {CAMINHO_RELATORIO}")
    return passou


if __name__ == "__main__":
    raise SystemExit(0 if executar_gate() else 1)
