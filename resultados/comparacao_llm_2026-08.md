# Comparação de provedores/modelos de LLM na camada de agentes (spec 5.9)

Sessões de 2026-08-14 a 2026-08-16. Escopo: escolher o modelo default do
`LLM_PROVIDER` para o caminho interativo (RNF11), medindo qualidade, custo e
latência sob o **mesmo prompt e o mesmo arnês** — Braço A (agente único,
`src/braco_agente.py`), as 15 perguntas de `conjunto_padrao/conjunto_agentes.csv`,
temperatura 0. Todas as chamadas foram reais e pagas (`--permitir-api-paga`
implícito na execução direta do braço).

## Metodologia

- **Prompt `a3`** (`VERSAO_PROMPT_AGENTES` em `src/agentes.py`): bloco estático
  (regras + exemplo ReAct + esquema JSON) movido para **antes** da pergunta —
  o prefixo comum entre perguntas diferentes subiu de ~21 para ~7.650
  caracteres (~1.912 tokens), o que manteve casamento com o cache automático
  de prompt da DeepSeek (verificado empiricamente: 97% de cache-hit em
  perguntas diferentes com o mesmo prefixo). Ganhou também regras mecânicas de
  formato de saída e uma guarda de código (`_PADRAO_OBSERVACAO_FABRICADA`)
  contra observação de ferramenta fabricada em notação alternativa (XML,
  markdown) — achado real: DeepSeek em `reasoning_effort=max` escreveu
  `<Observation>` com um retorno de `verificar_cobertura` que nenhuma
  ferramenta devolveu, porque a parada do executor só reconhecia o literal
  `Observation:`.
- **Sem teto de tokens por chamada** — cada provedor rodou no teto real
  documentado (65.536 para Gemini, mesmo valor usado como teto experimental
  para DeepSeek, abaixo do arquitetural de 384.000 por decisão de custo/tempo).
  Objetivo: medir quanto cada modelo *precisa*, não quanto um teto artificial
  permite.
- **n=5 repetições por configuração**, mesma pergunta, mesmo prompt,
  temperatura 0 — a primeira execução isolada de cada modelo mostrou variância
  real entre repetições idênticas (ver seção de achados), então uma execução
  só não é evidência suficiente.
- **Execução sequencial, nunca paralela, dentro do mesmo modelo.** Achado
  operacional: rodar duas configurações do mesmo modelo em paralelo consome a
  mesma cota de requisições/minuto do free tier do Google AI Studio e
  contamina as duas. Modelos diferentes têm cotas independentes (confirmado
  pelo campo `quotaDimensions.model` no erro 429) e podem rodar em paralelo
  entre si.
- **Apuração de acerto sobre as 5 das 15 perguntas com gabarito conferido**
  (as outras 10 aguardam dupla leitura humana — ver `MEMORY.md`). Violações,
  custo, uso de ferramenta e latência são medidos nas 15.

## Resultado — n=5, todas as execuções limpas (zero erro de infraestrutura)

| Configuração | Acerto (5 apuradas) | Violações (15) | Custo/execução | Chamadas ferramenta | Latência total |
|---|---|---|---|---|---|
| **Gemini 3.5 Flash Lite, low** | **0,880 ± 0,160** | 2,40 ± 0,80 | US$ 0,134 | 40,4 | 198 s |
| Gemini 3.5 Flash Lite, high | 0,840 ± 0,080 | **1,60 ± 0,49** | US$ 0,300 | 52,8 | 342 s |
| Gemini 3.1 Flash Lite, low | 0,400 ± 0,000 | 3,60 ± 0,49 | US$ 0,128 | 35,4 | 475 s |
| Gemini 3.1 Flash Lite, high | 0,600 ± 0,000 | **6,00 ± 0,00** | US$ 0,325 | 37,0 | 975 s |
| DeepSeek V4 Flash, low | 0,600 ± 0,000 | 3,20 ± 0,40 | US$ 0,059 (tabela antiga) | 50,4 | 1.391 s |
| DeepSeek V4 Flash, max | 0,600 ± 0,000 | 0,60 ± 0,49 | US$ 0,102 (tabela antiga) | 52,2 | 2.371 s |

Custo do DeepSeek recalculado sob a tabela nova (peak/off-peak, vigente desde
2026-08-16 16:00 UTC — ver seção própria): **low US$ 0,133 (off-peak) / 0,265
(peak); max US$ 0,231 (off-peak) / 0,461 (peak)**. Em nenhum horário o DeepSeek
fica mais barato que o Gemini 3.5 low; em horário de pico fica mais caro que
qualquer configuração testada.

## Latência por pergunta individual (não por lote) — n=75 (5×15) por configuração

O que um usuário do caminho interativo realmente espera é o tempo de **uma**
resposta, não o total de 15. A cauda importa mais que a média para essa
decisão:

| | Mediana | Média | p90 | p99 | Pior caso |
|---|---|---|---|---|---|
| Gemini 3.5 low | 10,0 s | 13,2 s | 30,2 s | 42,0 s | 42,0 s |
| Gemini 3.5 high | 17,1 s | 22,8 s | 48,5 s | 78,0 s | 103 s |
| Gemini 3.1 low | 23,1 s | 31,6 s | 56,3 s | 184,6 s | 186,6 s |
| Gemini 3.1 high | 32,8 s | 65,0 s | 174,7 s | 483,4 s | **566 s (9 min 26 s)** |
| DeepSeek low | 70,6 s | 92,7 s | 212,2 s | 353,3 s | 438,7 s |
| DeepSeek max | 112,3 s | 158,1 s | 384,2 s | 676,3 s | **784,7 s (13 min 5 s)** |

Só `gemini_low` e `gemini_max` (3.5) ficam num intervalo praticável para
produto ao vivo em qualquer cenário — o pior caso do 3.5 low (42 s) é mais
rápido que a *mediana* de qualquer configuração do DeepSeek.

## Decisão

**`gemini-3.5-flash-lite`, `reasoning_effort=low`, é o default declarado** em
`.env`, `.env.example` e nos defaults de `Config` (`src/config.py`) desde
2026-08-15, confirmado com n=5 completo em 2026-08-16. Vence em acerto (0,88
contra 0,60 do DeepSeek e 0,40–0,60 do 3.1), é o mais barato entre os que
batem 0,6+ de acerto, e é o único sem risco de latência de vários minutos
numa única resposta.

`high` no 3.5 não vence `low`: acerto dentro de 1 desvio-padrão (0,84 × 0,88),
2,24× mais caro, 1,7× mais lento — só ganha em violações (1,6 × 2,4).
Considerado, não escolhido.

## Achados que não eram o objetivo da comparação, mas mudaram código de produção

1. **Gemini cobra tokens de raciocínio que `completion_tokens` não mostra.**
   Medido: `prompt=24, completion=1087, total=3037` — 1.926 tokens cobrados e
   invisíveis na telemetria de saída. Custo calculado por `completion_tokens`
   subestimava. Corrigido em `derivar_tokens_saida` (`src/geracao.py`):
   deriva de `total - entrada` sempre que maior que o reportado, nunca reduz
   abaixo do reportado quando a telemetria não fecha.
2. **DeepSeek fabricava evidência de ferramenta por notação alternativa.**
   `reasoning_effort=max` escreveu o protocolo em tags XML
   (`<Thought>`/`<Action>`/`<Observation>`) e preencheu a própria
   `<Observation>` com CD_CVM e razão social que nenhuma ferramenta devolveu —
   a parada do executor só reconhecia `Observation:` literal. Corrigido com
   guarda de código (`_PADRAO_OBSERVACAO_FABRICADA`, `src/agentes.py`), não só
   instrução de prompt.
3. **Cache automático da DeepSeek, cache-aware desde 2026-08-14.** O adaptador
   agora lê `prompt_cache_hit_tokens`/`prompt_cache_miss_tokens` e cobra cada
   faixa no seu preço (`Config.deepseek_preco_entrada_cache_hit_usd_milhao`).
   Medido: 80–83% de cache-hit em execução real sob o prompt `a3`.
4. **Reasoning capturado e persistido.** `RespostaBrutaLLM.raciocinio` guarda o
   `reasoning_content` da DeepSeek (redigido de PII antes de sair do
   adaptador), acumulado em `UsoAgente.raciocinios`. O Gemini não expõe
   raciocínio legível pela compatibilidade OpenAI — só um
   `thought_signature` opaco — e o campo fica vazio por ausência de
   instrumentação, não por afirmação de que não houve raciocínio.
5. **Tabela de preço da DeepSeek mudou para peak/off-peak em 2026-08-16
   16:00 UTC** (peak: 01h–04h e 06h–10h UTC). O default de `Config` adota
   PEAK — o único valor que não subestima em nenhum horário — porque o
   contrato de preço único e reproduzível é o que mantém o custo auditável a
   partir só da configuração (RNF03); trocar por horário dentro do adaptador
   tornaria o custo por chamada dependente de relógio, não de config.

## Modelos avaliados e descartados sem comparação completa

- **Gemma 4 31B** (via endpoint OpenAI-compatible do Gemini, mesma
  `GOOGLE_API_KEY`): `reasoning_effort=minimal` rodou limpo mas com o pior
  acerto do lote (0,4) e a maior latência por chamada entre as configurações
  que terminaram (71,9 s). `reasoning_effort=high` **nunca convergiu** —
  ficou gerando `<thought>` sem produzir `Final Answer` mesmo isolado e com
  55 minutos de timeout, em duas tentativas. Não é limite de cota, é o modelo
  não terminando de "pensar" nesse fluxo de ferramentas. Descartado.
- **Gemini 3.7 Flash**: cota gratuita de 20 requisições/dia inviabiliza
  qualquer rodada de 15 perguntas via agente (uma rodada sozinha já consome
  40–56 chamadas). Testado com 3 perguntas em `reasoning_effort=high`: 2/3
  responderam corretamente (recusa RN12 do Nubank e desambiguação RN11 do
  BTG, zero violação nas duas), 1/3 morreu num 503 real de sobrecarga do
  Google. `low` não pôde ser testado — a cota diária esgotou antes da
  primeira chamada bem-sucedida, inclusive por chamadas rejeitadas
  consumirem cota (confirmado em três ocasiões distintas, com três modelos
  diferentes, ao longo desta comparação). Sem dado suficiente para decisão.

## Reprodutibilidade

Artefatos brutos em `artefatos/resultados_agentes/distribuicao/`
(`a3_<config>_rep{1..5}.json`), um por execução, com `resumo` e `registros`
por pergunta (inclui `latencia_s`, `tokens_raciocinio`,
`tokens_entrada_cache_hit`, `raciocinios` por chamada desde 2026-08-15). Logs
RNF08 correspondentes em `artefatos/logs_execucoes/`.
