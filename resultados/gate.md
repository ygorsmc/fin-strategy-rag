# Gate G1 — recurso de inferência (seção 5.7 da especificacao.md)

- **Data/hora (UTC):** 2026-07-15T13:36:16.786380+00:00
- **Resultado:** ❌ FALHOU / não disponível

## Evidências

| Teste | Status | Evidência |
|-------|--------|-----------|
| Azure OpenAI — LLM | ❌ | `não configurado — variáveis ausentes no .env: ['AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_API_VERSION']` |
| Azure OpenAI — Embeddings | ❌ | `não configurado — variáveis ausentes no .env: ['AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_API_VERSION']` |

## Decisão de ramo

**Ramo B ativo (fallback documentado, seção 5.7 da spec):** inferência via NENHUM fallback configurado — defina OPENAI_API_KEY ou DEEPSEEK_API_KEY no .env antes da etapa de geração; embeddings `local` em desenvolvimento e via API na instância publicada. Créditos de estudante ficam integralmente na hospedagem (Azure Container Apps).

> Registro exigido pelo AGENTS.md (etapa 1): evidência, não alegação. Este
> arquivo é regenerado a cada execução de `scripts/gate.py`.
