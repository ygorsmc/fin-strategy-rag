# Gate L1 — inferência local

- **Início (UTC):** 2026-07-15T15:52:33.949323+00:00
- **Fim (UTC):** 2026-07-15T15:53:23.423886+00:00
- **Resultado:** ✅ PASSOU
- **Chamadas externas pagas/Azure:** não realizadas pelo Gate L1
- **Configuração:** prompt=v1; temperatura=0; max_tokens=512; lote_embeddings=4

## Evidências

| Teste | Status | Evidência |
|-------|--------|-----------|
| Runtime local | ✅ | `Ollama 0.30.10; endpoint=http://127.0.0.1:11434 (loopback)` |
| Embeddings locais | ✅ | `ollama/bge-m3@sha256:7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab; dimensão=1024; 2 textos em 6.438s; normas L2=1` |
| LLM local | ✅ | `ollama/qwen2.5:14b@sha256:7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6; resposta 26,6% com citação exata + recusa RN02 válidas; tokens=742+139; latência ponta a ponta=42.985s; custo de API=US$ 0,00` |

## Decisão de ramo

**Ramo local-first ativo:** `LLM_PROVIDER=ollama` e
`EMBEDDING_PROVIDER=ollama`. O Gate G1 de Azure fica
deliberadamente adiado até o pré-deploy, após testes, avaliação e interface
funcionarem localmente.

> Evidência regenerável por `python scripts/gate_local.py`. O ramo Ollama não
> exige nem envia credenciais reais ou segredos.
> As latências refletem o estado de cache encontrado no daemon; o gate não
> força cold ou warm start.
