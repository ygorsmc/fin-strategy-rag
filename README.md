# Assistente de Research Financeiro (RAG + painel contábil)

Assistente de perguntas e respostas sobre os resultados trimestrais dos cinco
maiores bancos listados do Brasil — Banco do Brasil, Bradesco, BTG Pactual,
Itaú Unibanco e Santander Brasil — cruzando **duas fontes públicas que hoje
vivem separadas**: os *releases* de resultado que cada banco publica em PDF e os
formulários contábeis que esses mesmos bancos arquivam na CVM.

O problema técnico é localizar informação pontual em documento longo, reconciliar
o número **gerencial** divulgado com o número **contábil** arquivado, e auditar
respostas numéricas de LLM com evidência rastreável.

> Projeto demonstrativo e educacional. Não constitui recomendação de
> investimento — o sistema recusa esse tipo de pedido por regra (Resoluções CVM
> 19/2021 e 20/2021).

A restrição central, medida e não apenas afirmada: **o assistente nunca afirma o
que não está na fonte, e declara explicitamente quando não sabe** — mesmo que o
modelo de linguagem "saiba" a resposta de memória.

---

## O que o sistema precisa acertar — e o que precisa recusar

| Pergunta | Comportamento esperado |
|---|---|
| "O Banco do Brasil ganhou ou perdeu dinheiro?" | Responde com o valor e cita documento, período e linha |
| "Qual desses cinco bancos deu mais lucro?" | Compara — resolvendo antes que cada banco arquiva o lucro em um código de conta diferente |
| "Vi outro número na notícia. Quem está errado?" | Ninguém — mostra o gerencial e o contábil lado a lado e explica a diferença |
| "E o Nubank? E o Inter?" | **Respostas diferentes para perguntas que parecem iguais**: o Inter está no painel do regulador mas não no corpus de documentos — entrega o número e declara o que falta; o Nubank não está em nenhum dos dois — recusa, dizendo por quê |
| "Devo comprar essa ação?" | **Recusa e explica**: é atividade privativa de analista credenciado |
| "E o quarto trimestre?" | Responde **marcando que o valor é derivado** — o regulador não recebe informação trimestral no 4T |

As duas últimas linhas são o desafio de verdade. Responder é fácil; **saber
quando não responder** é o que precisa ser medido.

---

## Arquitetura

```text
corpus público (PDF)                   dados abertos CVM (ITR/DFP)
  │                                       │
  ▼                                       ▼
extração + chunking (~600/100 tokens)  painel contábil em DuckDB
validação estrutural + sentinelas      companhias ⋈ fatos_contabeis
  │                                       │ mapa_contas ⇒ fatos_semanticos
  │                                       │ (4º trimestre derivado e marcado)
  ├──► índice BM25 (palavra-chave)        │
  └──► embeddings ──► índice vetorial     │
                        │                 │
                        ▼                 ▼
        ┌──────────────────────────────────────────┐
        │ FERRAMENTAS: verificar_cobertura ·       │
        │ buscar_trechos · consultar_cvm ·         │
        │ calcular_indicadores                     │
        └──────────────────────────────────────────┘
                        ▲
pergunta → guardrails → Investigador → [filtro de contexto]
                                        │ só a afirmação + citações
                                        ▼
                                     Auditor → guardrails → resposta
```

**Dois caminhos de execução, deliberadamente separados.** O caminho interativo
(agentes, guardrails, Streamlit) é o produto. O caminho de avaliação — as 45
perguntas congeladas sobre as estratégias E0–E4 — roda o pipeline determinístico
de recuperação + geração, **sem** a camada de agentes: a orquestração multiagente
introduz variabilidade de plano que destruiria a comparabilidade entre
estratégias, mesmo a temperatura 0. Os dois caminhos compartilham as mesmas
ferramentas e o mesmo prompt; só a orquestração difere.

As estratégias comparadas são:

- **E0** — closed-book, apenas como controle diagnóstico (expõe quanto o modelo
  "sabe" de pré-treinamento);
- **E1** — keyword/BM25;
- **E2** — semântica/embeddings (estratégia-alvo);
- **E3** — híbrida por *Reciprocal Rank Fusion*;
- **E4** — tabela de fatos numéricos: ranqueia o trecho por quantos números
  da métrica perguntada ele contém, e não por similaridade de texto. Existe
  porque recuperar a *página* certa não basta — a prosa da página costuma
  arredondar ("R$ 3,4 bilhões") enquanto a tabela com o valor exato fica
  fora do top-k.

O isolamento de contexto entre os dois agentes é a decisão de arquitetura, não a
divisão por fonte de dado: o Auditor acrescenta informação justamente porque
**não pode ver** o raciocínio do Investigador — se visse, tenderia a concordar.
Ele tem três vereditos: confirma, contesta com contraevidência citada, ou não
consegue reproduzir. O terceiro é o mais valioso: uma afirmação irreprodutível
não é falsa, mas também não é publicável.

---

## Estado de implementação

Nem tudo o que a arquitetura descreve está construído. Esta tabela é o estado
verificável em **2026-08-23**, não a intenção.

| Camada | Estado |
|---|---|
| Corpus (20 PDFs, 5 bancos × 4 trimestres, manifesto com SHA-256) | ✅ íntegro |
| Extração por **Mistral OCR** com cache versionado *content-addressed* | ✅ extrator primário; 2.790 páginas, zero erro |
| Ingestão, chunking, validação estrutural e teste-sentinela (20/20 âncoras) | ✅ · tabela nunca abre chunk sem cabeçalho (0 de 7.147, era 101) |
| Normalização numérica pt-BR e canonização de bancos | ✅ |
| Índice vetorial **ChromaDB** + BM25 com guarda de consistência (RNF09) | ✅ 7.147 chunks, `bge-m3` 1024d |
| Recuperação E0–E4 com filtro de metadados e subconsulta por banco | ✅ |
| Geração com contrato JSON, citação obrigatória e recusa (RN01–RN02) | ✅ |
| Avaliação retomável: fingerprint, journal, checkpoint, teto de custo | ✅ |
| Painel contábil CVM em DuckDB, mapa semântico de contas, 4T derivado | ✅ construído · ✅ **gate G4 aprovado** (ver abaixo) |
| Camada de agentes (Investigador + Auditor, três braços, injeção de falha) | ✅ os três braços rodaram · ⬜ falta acompanhamento de projeções |
| Modelo preditivo supervisionado sobre o painel | ✅ 21.903 obs (painel 2011–2026), **walk-forward de 47 folds**, baselines e ablações (`resultados/modelo_preditivo_2026-08-23.md`) — offline, nunca exposto por companhia nomeada (RN07) |
| Guardrails (PII, injeção, tópico proibido) | ✅ **20/20 ataques bloqueados · 0/45 falso bloqueio de entrada · 0/855 de saída**, com Presidio e Llama Prompt Guard 2 ligados na contraprova |
| Observabilidade (Langfuse) e suíte automatizada de *faithfulness* | ⬜ Langfuse não construída · ✅ juiz automático medido contra a auditoria humana (0,867) |
| Interface Streamlit (modo cacheado + pergunta livre opt-in) | ✅ base; camadas novas pendentes |

Suíte de testes: **1.689 casos automatizados, sem skips**. `pytest` verde é
pré-condição de qualquer commit.

**Gate G4: reprovou em 2026-08-11, aprovado em 2026-08-22.** O gate confere,
banco a banco, se o lucro resolvido pelo mapa semântico de contas bate com o
release. Reprovou em 2 das 20 células (Santander 3T e 4T2025) — causa apurada:
**erro no próprio arquivo da CVM**, não no mapa; o 4T herdava o erro com sinal
invertido por ser derivado do 3T defeituoso. Uma célula (BTG 4T2025) ficou sem
âncora porque 63 de 71 páginas da demonstração anual não têm mapa de
caracteres. As duas causas foram resolvidas com procedência auditável, não
com exclusão nem correção silenciosa: o BTG foi lido por OCR pago e escopado a
uma única página localizada por alinhamento geométrico de coluna
(`resultados/ancora_btg_4T2025.md`); o Santander recebeu uma tabela de
correções versionada e travada ao valor observado no painel — se a CVM
republicar o arquivo, a correção deixa de valer e a carga falha em vez de
aplicar às cegas (`corpus/cvm/correcoes_contabeis.csv`). 20/20 células
conferidas; painel liberado como fonte de resposta.

---

## Resultados medidos

Rodada vigente no conjunto congelado: **`20260823T131515Z-4ad67021f6`**
(2026-08-23), 45 perguntas × 5 estratégias = **225 chamadas**, temperatura 0,
zero erro de infraestrutura, **USD 0,2501**. As 45 `teste` foram congeladas em
2026-07-29 e nenhum número de `dev` aparece aqui.

| Estratégia | Recall@5 | Exatidão factual (15) | Exatidão comparativa (10) | Recusa correta | Custo médio |
|---|---|---|---|---|---|
| E0 — Closed-book | — (não se aplica) | 0,000 | 0,000 | 0,800 | USD 0,000701 |
| E1 — Keyword/BM25 | **0,920** | 0,333 | 0,000 | 1,000 | USD 0,001208 |
| E2 — Semântica | 0,800 | 0,333 | 0,000 | 1,000 | USD 0,001260 |
| E3 — Híbrida/RRF | 0,880 | 0,467 | 0,000 | 1,000 | USD 0,001227 |
| E4 — Tabela de fatos | 0,880 | **0,667** | 0,000 | 1,000 | USD 0,001161 |

**Nenhuma estratégia é declarada vencedora, nem mesmo o 0,667 do E4.** O limiar
declarado **antes** da execução é de **6 discordâncias na mesma direção**
(McNemar exato, p = 0,031). Contra a rodada anterior, o máximo observado em
qualquer estratégia é 4 numa direção e 3 na outra. O veredito publicado é
*indistinguível neste tamanho de amostra* — inclusive para o maior número de
exatidão factual que o projeto já mediu. Publicar 0,667 como vitória seria
exatamente o tipo de leitura que o limiar pré-registrado existe para impedir.

**A coluna comparativa está em zero, e isso é teto estrutural — não regressão.**
Uma versão anterior deste README chamou o zero de regressão; a apuração de
2026-08-23 (`resultados/teto_comparativas_2026-08-23.md`, custo zero) mostra que
a palavra estava errada. Cada comparativa exige de 1 a 5 valores, um por banco,
e o orçamento de recuperação é **top-5 global** — nas cinco perguntas que pedem
os cinco bancos sobra **um chunk por banco**. Medindo se o valor do gabarito
está no chunk daquele banco, o **teto** (perguntas em que todos os valores
chegaram) é E1 1/10 · E2 2/10 · E3 2/10 · **E4 5/10**. Com 0/10 publicado, o
sistema disputa contra um teto de 1 a 5, nunca de 10.

A recuperação **não** é o gargalo aqui: a subconsulta por banco entregou todos
os bancos exigidos em **40 de 40** execuções. O que falta é o número dentro do
chunk certo. E o teto do E4 é **idêntico** nas três últimas rodadas (5/10),
enquanto E2/E3 variaram em uma pergunta — a diferença entre "0,100–0,200" e
"0,000" são 1 a 3 eventos sobre uma base de 1 a 5, dentro do ruído e muito
abaixo do limiar de 6.

Dar orçamento por banco à comparativa resolveria o teto, mas **mudaria o
orçamento de contexto** — e o §3.1-bis do `AGENTS.md` já estabeleceu, com
medição, que isso torna a comparação E0–E4 não comparável. O caminho correto é
medição declarada em separado, como o E4 entrou. Não implementado.

### Chunking de tabela: o defeito achado pela auditoria manual

A leitura humana de 2026-08-22 rastreou uma resposta errada (`R$ 12.144
milhões`, coluna do 4T25, para uma pergunta sobre o 1T2026, cujo valor é
`11.875`) até o chunker, não até o modelo nem o OCR. A tabela estava montada
corretamente; o chunk entregue ao modelo é que abria nas duas últimas linhas
dela, **órfãs do cabeçalho que nomeia o período**. Duas causas independentes:

1. a **cauda de sobreposição** copiava os últimos tokens do chunk emitido sem
   olhar o tipo do bloco — terminando em tabela, o chunk seguinte abria no meio
   da grade;
2. a **partição de tabela grande** media a parte sem contar a legenda de unidade
   que ela mesma emite, estourando o orçamento na emissão e sendo repartida por
   tokens, sem repetir o cabeçalho.

Medição no índice: **101 chunks** abriam com 3+ colunas de valor sem cabeçalho,
e **18 das 45 perguntas congeladas** recebiam um deles no top-5. Depois das
correções: **zero**, verificado por teste que roda contra o índice publicável.

**A primeira tentativa de conserto piorou o sistema, e isso fica registrado.**
Descartar tabela da cauda zerou os órfãos e derrubou a exatidão factual junto
(E2 de 0,467 para 0,267), porque a duplicação que o overlap criava também era
uma rede de segurança: um valor perto da fronteira aparecia em dois chunks e
recuperar qualquer um resolvia. A correção final **recoloca o cabeçalho** na
cauda em vez de descartar a tabela, preservando as duas propriedades.

**Propriedade de segurança verificada nesta rodada:** das respostas publicadas
(não recusadas), nenhuma omite o valor do gabarito. As que o avaliador reprova
contêm os valores corretos e falham por exigência de qualificador na redação,
não por número errado.

**Guardrails (medido em 2026-08-21, custo zero — nenhum scanner chama LLM).**
Três números na mesma execução, porque publicar só o primeiro premiaria um
scanner que recusa tudo:

| Meta | Escopo | Resultado |
|---|---|---|
| Ataques bloqueados pelo scanner **e** subtipo corretos | 20 ataques (9 injeção · 11 tópico) | **20/20** |
| Falso bloqueio na **entrada** | 45 perguntas legítimas congeladas | **0/45** |
| Falso bloqueio na **saída** | 855 textos gerados pelo próprio sistema nas 4 estratégias | **0/855** |

A terceira linha existe porque a guarda de saída entrou no caminho do produto e
precisava do mesmo contraprova que a de entrada — medida sobre a linguagem que
este sistema realmente gerou no conjunto congelado, não sobre exemplos escritos
para ela passar. Evidência em `resultados/guardrails.json`.

Cada recusa por tópico declara a norma que a fundamenta: **Resolução CVM
20/2021** para atividade de analista (recomendar, precificar, classificar) e
**Resolução CVM 19/2021** para consultoria (aconselhar pessoa determinada
sobre a carteira dela). PII **não** bloqueia — CPF, CNPJ, e-mail, telefone e
CEP são anonimizados e a pergunta segue; bloquear transformaria proteção do
usuário em recusa de atendimento. CPF e CNPJ são validados pelo **dígito
verificador**, não pela forma: um release está cheio de números de onze
dígitos, e reconhecer pela forma seria uma fábrica de falso bloqueio.

Os scanners estão **ligados ao caminho interativo**: a varredura de entrada roda
antes de qualquer fábrica ser construída — um ataque é recusado sem gastar
chamada nem cota de sessão —, o braço de agentes recebe o texto já anonimizado, e
bloquear a saída **não apaga** o custo já incorrido, porque a chamada aconteceu e
esconder isso corromperia a contabilidade de orçamento. O benchmark E0–E4 e os
braços A/B/C do experimento continuam **fora** dessa fiação (RNF11): guardrail é
composição do produto, não alteração da orquestração medida.

**Presidio construído** (`src/reconhecedor_presidio.py`, `requirements-guardrails.txt`,
desligado por padrão via `PRESIDIO_HABILITADO` — RNF12) — NER de nome de
pessoa, que expressão regular não resolve. Dois falsos positivos reais foram
medidos e corrigidos antes de publicar: o modelo spaCy marca o próprio nome de
banco ("Santander") como PESSOA (filtrado contra `APELIDOS_BANCOS`) e marca o
verbo que abre a frase ("Ignore", "Aja" — maiúsculo só por convenção de início
de frase) como PESSOA, o que apagaria o gatilho que o scanner de injeção
precisa ver (filtrado por token único na posição 0). Com Presidio ligado, as
20 ataques e as 55 congeladas (dev + teste) foram remedidas: nenhuma mudança.

**Llama Prompt Guard 2 (86M) também construído** (`src/prompt_guard.py`,
desligado por padrão via `PROMPT_GUARD_HABILITADO`) — pesos gated do Hugging
Face, baixados uma vez com `HF_TOKEN` de build e pinados por SHA
(`guardrails_modelo_injecao_revision`); runtime carrega com
`local_files_only=True`, confirmado que não pede token nenhum depois de
baixado (RNF12). Medido antes de compor: sozinho, o classificador **não
cobre a família `topico_proibido`** (recomendação, preço-alvo, consultoria) —
ele foi treinado para reconhecer *tentativa de sobrepor instrução*, não
*pedido de conduta regulada*, então isso é escopo, não defeito. Da família de
injeção, pega 5 dos 9 ataques sozinho; os 9 continuam cobertos pelo regex
determinístico. A integração é **OR**, não substituição: bloqueia se o regex
ou o classificador disparar, e só chama o modelo quando o regex não achou
nada. Com as duas camadas ML ligadas juntas, os 20/20 ataques e o 0/45+0/855
de falso bloqueio se mantêm — evidência em `resultados/guardrails.json`.

| Outras métricas | Escopo | Resultado |
|---|---|---|
| Groundedness (auditoria manual) | 15 respostas | **0,667** na rodada `a0bea525` — meta 0,90 **não atingida**; refazer sobre a rodada vigente |
| Estabilidade a temperatura 0 | 10 perguntas × 3 repetições | não medido |
| Acerto da classe de cobertura (`ambas`/`so_painel`/`nenhuma`) | perguntas anotadas | não medido |
| Recusa **pelo motivo certo** | 10 adversariais | não medido |
| Taxa de falso bloqueio dos guardrails | 45 legítimas (entrada) + 855 textos gerados (saída) | **0/45 e 0/855** |
| Ataques bloqueados | 20 ataques (injeção + tópico) | **20/20** |
| Concordância entre juiz automático e auditoria humana | mesma amostra de 15 | **0,867** (13/15), `gemini-3.7-flash` |
| Comparação dos três braços (agente único × Investigador+Auditor × determinístico) | 15 pareadas | não medido |
| Modelo preditivo (ROC-AUC contra baselines) | walk-forward, 47 folds | **0,865**. Contra a regra binária de persistência, +0,113 — mas esse número é inflado por empate (a persistência tem 2 valores e o AUC pune empate). **Ganho honesto: +0,019 sobre `taxa_prejuizos_4t` crua** (coluna que já existe no painel) e **+0,073 sobre a taxa histórica da própria companhia**, vencendo em 47/47 |
| Modelo: o que ele NÃO faz (decomposição obrigatória) | walk-forward, 47 folds | **AUC intra-companhia 0,663** contra 0,865 agregado: o modelo ordena **quais** companhias são cronicamente deficitárias, não **quando** uma vira. **97,1% do decil superior já está em prejuízo** no próprio trimestre. Onde há sinal de antecipação é o recorte de hoje-lucrativas (AUC 0,832, lift 4,35), ~4 nomes novos por trimestre |
| Modelo: escoragem do trimestre corrente | `1T2026`, sem rótulo | Das **286** companhias que fecharam o trimestre **com lucro**, **2** receberam escore acima do limiar absoluto. Outras **136** já estão em prejuízo e ficam fora da contagem de propósito — para elas o escore alto repete a demonstração. **Sem AUC, e isso é declarado:** o resultado ainda não aconteceu. Nesta rodada o agregado **não é publicado na interface**: 2 de 286 é fração baixa demais e permitiria deduzir por eliminação o estado do emissor perguntado — a guarda suprime, e o escore por emissor segue disponível só no modo local |
| Modelo: viés *as-restated* (medido, não suposto) | painel de treino, 22.862 obs | **16,36%** das observações usam valor que só existiu após republicação. O que importa é a assimetria: **16,81%** nos trimestres de prejuízo contra **16,14%** nos de lucro — **0,66 ponto**, sem concentração na classe positiva. Não reverte o viés; dimensiona |
| Modelo: o que foi medido e NÃO ajudou | walk-forward pareado | Features do O-score de Ohlson (nulo/pior) · SMOTE (−0,006, p=5e-08) · ajuste de hiperparâmetros (zero em folds não vistos) · controle setorial (+0,0005, p=0,19) · recalibração isotônica (piora a ordenação) · LightGBM (empate, p=0,66) |
| Custo real da API contra o teto de USD 25 | projeto inteiro | **USD 2,87** acumulado nos logs versionados |

**Metas declaradas antes do teste** (spec 5.14): Recall@5 ≥ 0,80; exatidão
numérica ≥ 0,75; recusa correta ≥ 0,90; groundedness manual ≥ 0,90; falso
bloqueio = 0; latência ponta a ponta ≤ 10 s. **Metas não são resultados**, e esta
tabela só será preenchida com número medido no conjunto congelado, a temperatura
0, com log JSONL versionado.

Para a comparação dos três braços, o limiar de detecção foi registrado **antes**
da execução: diferença só é declarada a partir de 6 discordâncias na mesma
direção (McNemar exato, p = 0,031). Abaixo disso, o resultado é publicado como
"indistinguível neste tamanho de amostra" — nunca como vitória de um braço.

Os relatórios em `resultados/` datados de 2026-07-15 são **históricos**: o gate
local registra `prompt=v1` e o gate Azure antecede o endurecimento atual.
Nenhum deles comprova o prompt ou os adaptadores em uso hoje.

---

## Garantias implementadas

- Toda resposta afirmativa precisa citar empresa, documento, trimestre e uma
  página pertencente a um chunk realmente recuperado.
- Cada valor financeiro reconhecido pelo parser também precisa existir nos
  chunks citados: citar uma página válida e inventar outro número resulta em
  recusa.
- Trechos e pergunta são delimitados como dados não confiáveis no prompt.
- Índice, chunks e metadados são preparados e reabertos em *staging*; checksums,
  dimensão, quantidade, modelo/digest e hash do corpus são conferidos na carga.
  A promoção usa renomeações sob lock — não é uma troca atômica de diretório
  garantida por todos os sistemas de arquivos.
- Locks serializam indexação e avaliação no mesmo namespace. Antes de cada
  chamada externa, um journal *write-ahead* persiste a intenção; se houver queda
  antes do registro do resultado, a retomada automática é bloqueada para
  reconciliação, em vez de repetir a chamada às cegas. APIs externas não
  oferecem *exactly-once*.
- O fingerprint de avaliação inclui gabarito, corpus, índice, prompts, código,
  modelo, parâmetros de geração e preços — e nunca chaves de API.
- Avaliação ou indexação em provedor externo exige confirmação explícita.
  Perguntas livres ficam desabilitadas por padrão e têm limites por sessão,
  tamanho e orçamento.
- A ingestão não depende do cliente HTTP do Mistral OCR: uma etapa separada e
  paga cria artefatos *content-addressed* sob journal; a ingestão apenas lê o
  cache, valida PDF, contrato e checksums, e propaga a proveniência até os
  metadados do índice.

---

## Generalização — o que é agnóstico e o que está ancorado

**O pipeline é agnóstico a setor; a avaliação está ancorada em cinco bancos e
quatro trimestres. Rodar sobre outra companhia funciona; afirmar que funciona
bem exigiria estender o conjunto-padrão.** A distinção entre *executa* e *foi
medido* é a mesma que o sistema aplica às próprias respostas.

O pipeline documental (extração → fragmentação → índice → recuperação → geração
com citação e recusa) não sabe de que setor é o PDF, e a camada estruturada já é
geral: a ingestão do ITR/DFP traz todas as companhias abertas, não só as cinco do
corpus. O que **não** generaliza sozinho é o gabarito: acrescentar uma companhia
é trivial no pipeline e caro em trabalho humano — perguntas novas com conferência
independente. Sem isso, o sistema roda sobre a nova companhia sem que ninguém
saiba se responde bem.

---

## Instalação

Requer Python 3.12. O perfil de desenvolvimento usa BGE-M3 no Ollama e não
precisa de PyTorch nem de `sentence-transformers` no ambiente Python.

Instale o Ollama pelo método adequado ao seu sistema e deixe o daemon ativo
(`ollama serve` em instalações que não iniciam um serviço automaticamente).
Depois prepare os dois modelos do perfil local:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull bge-m3
ollama pull qwen2.5:14b
install -m 600 .env.example .env
```

Dependências pesadas são opcionais:

```bash
pip install -r requirements-local.txt  # EMBEDDING_PROVIDER=local
pip install -r requirements-lora.txt   # módulo PEFT opcional
```

Nunca versione `.env`, chaves ou os PDFs de `corpus/raw/`.

## Execução sem API paga

```bash
python scripts/baixar_corpus.py
pytest -q
LLM_PROVIDER=ollama python executar_pipeline.py --amostra
streamlit run app_streamlit.py
```

`--amostra` executa ingestão, cria o **índice de amostra** em namespace próprio
(`artefatos/amostra/`) e só então avalia o conjunto `dev` — não substitui o
índice, os logs nem o cache integrais. Para rodar fases isoladas, não pule a
indexação:

```bash
python executar_pipeline.py --amostra --etapa indexacao
LLM_PROVIDER=ollama python executar_pipeline.py --amostra --etapa avaliacao
```

## Chamadas externas

O perfil de `.env.example` usa Gemini (`gemini-3.5-flash-lite`) para geração,
atrás da mesma interface plugável dos demais provedores. Qualquer execução que
gere custo exige o opt-in `--permitir-api-paga`:

```bash
python scripts/gate_gemini.py --permitir-api-paga   # duas chamadas externas
python executar_pipeline.py --amostra --permitir-api-paga
```

O gate faz um preflight conservador contra `ORCAMENTO_TETO_USD` (teto a priori:
**USD 25**) e grava um journal *append-only* antes e depois de cada chamada. O
teto vale por execução: repetir o comando pode gerar nova cobrança. Uma
interrupção entre a resposta e o registro final não oferece garantia
*exactly-once*; nesse caso, o pior caso reservado deve ser considerado debitado.
O controle real de custo é o teto configurado no lado do provedor.

O gate Azure (`python scripts/gate.py --permitir-api-paga`) é reservado ao
pré-deploy: testa conectividade dos *deployments* configurados, não mede
capacidade nem cria recursos. Como preços Azure não fazem parte da configuração
atual, esse gate não aplica o teto monetário.

O pré-processador Mistral OCR é explícito, nunca um fallback automático. O
dry-run confere manifesto, SHA-256, páginas, cache, journal e teto sem chamar a
rede e sem exigir a chave:

```bash
python scripts/preprocessar_ocr_mistral.py --paginas-factuais --conjunto dev
```

Só as páginas selecionadas e ainda ausentes do cache são reconstruídas em um PDF
mínimo em memória e enviadas ao endpoint oficial — nunca o PDF-fonte completo.
Ainda assim, essas páginas saem da máquina: não use o fluxo com conteúdo privado
sem base legal e política de tratamento compatíveis. Não há retry automático
após timeout: sem chave de idempotência documentada, repetir poderia cobrar duas
vezes.

## Interface

A interface abre no **modo demonstração cacheado** e não exige nenhum segredo
configurado. Como a avaliação do conjunto congelado ainda não foi executada, o
cache final está vazio e a interface informa essa pendência — sem apresentar
respostas `dev` como se fossem finais. Para habilitar inferência ao vivo em
ambiente controlado:

```dotenv
HABILITAR_PERGUNTAS_LIVRES=true
LIMITE_PERGUNTAS_LIVRES_POR_SESSAO=5
LIMITE_CARACTERES_PERGUNTA=2000
ORCAMENTO_TETO_USD=25
```

Provedores sem preço configurável e embeddings externos são bloqueados antes da
pergunta livre, evitando custo falsamente registrado como zero.

---

## Estrutura

```text
├── executar_pipeline.py          # orquestrador (--amostra, --etapa)
├── DESAFIO_CBL.md                # declaração de desafio (CBL)
├── scripts/                      # corpus, gates, OCR, auditoria, estabilidade
├── corpus/
│   ├── metadados.csv             # fonte de verdade: URL, data, SHA-256
│   ├── ancoras_sentinela.csv     # 20 âncoras independentes do gabarito
│   └── raw/                      # PDFs — fora do Git, regeneráveis
├── conjunto_padrao/
│   ├── perguntas.csv             # 10 dev + 45 teste congeladas
│   └── candidatas_teste.csv      # origem auditável da curadoria
├── src/                          # ingestao · normalizacao · indexacao ·
│                                 # recuperacao · fatos (E4) · geracao ·
│                                 # avaliacao · auditoria · bloqueio ·
│                                 # dados_estruturados · mapa_contas ·
│                                 # cobertura · ferramentas · agentes ·
│                                 # braco_agente · braco_determinista ·
│                                 # injecao_falha · ocr_* · config
├── corpus/ocr/                   # cache de OCR versionado (RNF10)
├── artefatos/                    # índice, logs JSONL, resultados, cache do demo
├── resultados/                   # evidência dos gates
├── app_streamlit.py
└── tests/                        # 1.387 casos, sem skips
```

---

## Limitações honestas

- **Corpus pequeno:** 5 bancos, 4 trimestres. Conclusões sobre recall e exatidão
  não generalizam para qualquer documento financeiro público.
- **Contaminação por pré-treinamento:** o LLM pode ter visto estes releases
  públicos durante o próprio treinamento — por isso E0 é reportado
  separadamente, como controle diagnóstico.
- **Guarda mecânica não prova fidelidade semântica:** ela prova a origem das
  citações e dos números. Groundedness qualitativo continua exigindo auditoria
  manual, e um juiz automático tem a mesma fragilidade que está sendo testada —
  por isso a suíte automatizada é medida **contra** a auditoria humana, não no
  lugar dela.
- **A camada estruturada depende de um mapa mantido à mão:** o plano de contas
  varia por companhia e o mesmo código de conta designa linhas diferentes — uma
  consulta ingênua devolve número plausível, não nulo e errado para parte dos
  bancos, sem erro visível. É a limitação com maior potencial de dano do
  projeto, e por isso a validação do mapa é um gate bloqueante.
- **O 4º trimestre não existe como informação trimestral arquivada:** é derivado
  por subtração e apresentado marcado como derivado. Apresentá-lo como número
  arquivado seria mentir por omissão.
- **Métricas gerenciais não são perfeitamente comparáveis entre bancos:** cada
  instituição define os próprios ajustes; as perguntas comparativas fixam "como
  divulgado em cada release".
- **Não-determinismo da camada de agentes:** por isso a comparação de estratégias
  roda no caminho determinístico. As métricas de E0–E4 descrevem o pipeline de
  recuperação, não o comportamento do agente.
- **Guardrails têm custo de memória e de falso bloqueio:** qualquer scanner pode
  barrar uso legítimo, e por isso a taxa de falso bloqueio é métrica reportada,
  com meta zero.
- **Índices binários são locais e regeneráveis:** não são versionados.
- **Nenhum resultado de `dev` é promovido para a tabela final.**

---

## Licença e créditos

MIT — ver [LICENSE](LICENSE).

Os PDFs públicos não são redistribuídos: o manifesto versionado registra URL e
SHA-256 para reobtenção e auditoria. Os dados contábeis vêm do Portal de Dados
Abertos da CVM (`dados.cvm.gov.br`), conjuntos ITR e DFP.

**Built with Llama.** A camada de segurança usa o Llama Prompt Guard 2 86M como
detector de injeção e *jailbreak*, sob a Llama 4 Community License, que exige
esta atribuição. A camada ainda não está construída (ver *Estado de
implementação*); a atribuição fica registrada aqui como condição de uso do
modelo, não como afirmação de que o componente já roda.
