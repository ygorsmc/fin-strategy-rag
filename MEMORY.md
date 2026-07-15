# MEMORY.md

> Memória de trabalho entre sessões de agentes. Leia no início de toda
> tarefa; ao final, sobrescreva o que ficou desatual. Não é changelog — é
> contexto de handoff para o próximo agente. Regras de uso em
> [AGENTS.md](AGENTS.md#memória-entre-sessões--memorymd).

## Estado atual

- Etapa ativa (plano §2): Etapa 3, segunda leitura e congelamento do
  conjunto-padrão; depois, Etapa 4 (ingestão).
- Últimas etapas concluídas: Gate L1 local (2026-07-15) e Etapa 2, Corpus
  (2026-07-15) — 20 documentos, hashes validados e 2.790 páginas.
- Primeira leitura da Etapa 3: 10 perguntas `dev` no arquivo do pipeline e 45
  candidatas `teste` separadas. Ainda não usar as candidatas para métricas.

## Decisões e bloqueios em aberto

- Decisão explícita do usuário: desenvolvimento, avaliação e interface devem
  funcionar 100% localmente antes de qualquer consumo de créditos Azure.
- Ramo ativo: Gemini API (`gemini-3.1-flash-lite`) para LLM e `bge-m3` via
  Ollama para embeddings. A chave local existente está sob o alias
  `GOOGLE_API_KEY`; não registrar o valor em logs ou commits.
- `scripts/gate_local.py` continua como fallback comprovado em endpoint loopback.
  `scripts/gate_gemini.py` passou em 2026-07-15: citação e recusa RN02 válidas,
  711+180 tokens, 4,95 s e custo estimado de US$ 0,000448.
- O Gate G1 Azure foi deliberadamente movido para o pré-deploy. O Gemini API é
  externo, mas não envolve Azure; seu teto de custo deve ser conferido antes do
  gate. Container e
  ngrok também só entram após o fluxo nativo estar verde; nunca expor `11434`.
- A segunda leitura das 45 candidatas deve ocorrer em outro dia e sem reutilizar
  a anotação inicial; só então promover e registrar o congelamento.
- `sentence-transformers` ainda não está instalado; é necessário somente para
  a alternativa `EMBEDDING_PROVIDER=local`, não para o ramo Ollama ativo.

## Próximo passo concreto

- Em outra data, executar a segunda leitura descrita em
  `conjunto_padrao/README.md`, promover as 45 perguntas e registrar a data de
  congelamento no `AGENTS.md`.
- Em seguida, implementar a Etapa 4 (ingestão) com fixtures PDF sintéticas e
  remover apenas os 11 skips correspondentes quando os contratos passarem.
