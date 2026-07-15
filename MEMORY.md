# MEMORY.md

> Memória de trabalho entre sessões de agentes. Leia no início de toda
> tarefa; ao final, sobrescreva o que ficou desatual. Não é changelog — é
> contexto de handoff para o próximo agente. Regras de uso em
> [AGENTS.md](AGENTS.md#memória-entre-sessões--memorymd).

## Estado atual

- Etapa ativa (plano §2): Etapa 3 — segunda leitura e congelamento das 45
  candidatas (bloqueada: deve ocorrer em outra data, sem reusar a anotação
  inicial).
- Últimas etapas concluídas: **Etapas 4–10 implementadas e validadas em
  2026-07-15** — suíte com 112 testes passando SEM skips; corpus 20/20
  íntegro; índice FAISS real (5.280 chunks, bge-m3 pinado por digest, RNF09)
  + BM25; avaliação `dev` das 4 estratégias (E0–E3) rodada com checkpoint e
  log JSONL; cache demo gerado; pergunta livre do Streamlit implementada.
- Métricas medidas vivem em `artefatos/resultados_avaliacao/metricas_dev.json`
  e no log RNF08 — números de `dev` são para iteração, NUNCA vão ao README.

## Decisões e bloqueios em aberto

- `especificacao.md` foi removida do rastreamento (commit 8c045e5), mas
  permanece no histórico de commits antigos — o repositório público deve
  nascer de histórico limpo (regra dura AGENTS §0).
- NÃO rodar `--amostra --etapa indexacao` após o índice real construído: a
  amostra sobrescreve `artefatos/indice_vetorial/` (reconstrução ≈ 1 h de
  embedding no Ollama).
- O índice atual foi construído com `hash_corpus=""` (anterior ao fix do
  orquestrador); a próxima reconstrução grava o sha256 do manifesto.
- Adaptadores `.gerar` de Azure/OpenAI/DeepSeek e `.embedar` de
  Local/OpenAI/Azure seguem `NotImplementedError` deliberadamente
  (decisão local-first; Azure só no gate G1 do pré-deploy, etapa 12).
  `sentence-transformers` segue não instalado (só para EMBEDDING_PROVIDER=local).
- Durante a 1ª rodada `dev` da híbrida, o Ollama falhou transitoriamente em
  4 itens; o desenho retry+checkpoint (erro não é congelado) resolveu na
  retomada — comportamento esperado, sem ação pendente.

## Próximo passo concreto

- Em outra data: segunda leitura das 45 candidatas
  (`conjunto_padrao/README.md`), promover a `conjunto=teste` e registrar a
  data de congelamento no AGENTS.md.
- Depois: `python executar_pipeline.py --etapa avaliacao` (45 congeladas,
  E0–E3, temperatura 0), preencher a tabela do README com os números medidos
  e regenerar `respostas_cacheadas.json` a partir do conjunto congelado.
