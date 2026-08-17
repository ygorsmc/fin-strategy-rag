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
perguntas congeladas sobre as estratégias E0–E3 — roda o pipeline determinístico
de recuperação + geração, **sem** a camada de agentes: a orquestração multiagente
introduz variabilidade de plano que destruiria a comparabilidade entre
estratégias, mesmo a temperatura 0. Os dois caminhos compartilham as mesmas
ferramentas e o mesmo prompt; só a orquestração difere.

As estratégias comparadas são:

- **E0** — closed-book, apenas como controle diagnóstico (expõe quanto o modelo
  "sabe" de pré-treinamento);
- **E1** — keyword/BM25;
- **E2** — semântica/embeddings (estratégia-alvo);
- **E3** — híbrida por *Reciprocal Rank Fusion*.

O isolamento de contexto entre os dois agentes é a decisão de arquitetura, não a
divisão por fonte de dado: o Auditor acrescenta informação justamente porque
**não pode ver** o raciocínio do Investigador — se visse, tenderia a concordar.
Ele tem três vereditos: confirma, contesta com contraevidência citada, ou não
consegue reproduzir. O terceiro é o mais valioso: uma afirmação irreprodutível
não é falsa, mas também não é publicável.

---

## Estado de implementação

Nem tudo o que a arquitetura descreve está construído. Esta tabela é o estado
verificável em **2026-08-10**, não a intenção.

| Camada | Estado |
|---|---|
| Corpus (20 PDFs, 5 bancos × 4 trimestres, manifesto com SHA-256) | ✅ íntegro |
| Ingestão, chunking, validação estrutural e teste-sentinela (20/20 âncoras) | ✅ |
| Normalização numérica pt-BR e canonização de bancos | ✅ |
| Índice vetorial + BM25 com guarda de consistência (RNF09) | 🔄 migração para ChromaDB em curso |
| Recuperação E0–E3 com filtro de metadados e subconsulta por banco | ✅ base implementada |
| Geração com contrato JSON, citação obrigatória e recusa (RN01–RN02) | ✅ |
| Avaliação retomável: fingerprint, journal, checkpoint, teto de custo | ✅ |
| Painel contábil CVM em DuckDB, mapa semântico de contas, 4T derivado | 🔄 em construção |
| Camada de agentes (Investigador + Auditor, três braços, injeção de falha) | ⬜ não construída |
| Modelo preditivo supervisionado sobre o painel | ⬜ não construído |
| Guardrails (PII, injeção, tópico proibido) | ⬜ não construídos |
| Observabilidade e suíte automatizada de *faithfulness* | ⬜ não construídas |
| Interface Streamlit (modo cacheado + pergunta livre opt-in) | ✅ base; camadas novas pendentes |

Suíte de testes: **525 casos automatizados, sem skips**. `pytest` verde é
pré-condição de qualquer commit.

Extração por OCR de documento: **pendente**. O extrator ativo é o local
(`pypdf` ⇄ `pdfplumber`); o subsistema Mistral OCR existe como pré-processador
explícito e pago, com cache *content-addressed*, mas **não** é o extrator
primário e o gate de comparação contra `pdfplumber` ainda não foi executado.

---

## Resultados medidos

**Nada foi medido no conjunto congelado.** As 45 perguntas `teste` foram
congeladas em 2026-07-29 após segunda leitura dos documentos, mas ainda não
foram executadas pelo avaliador atual. As métricas `dev` de 2026-07-15 foram
**invalidadas** por correções posteriores no avaliador, no controle closed-book
e nas perguntas comparativas — e número de `dev` não vira resultado final em
nenhuma hipótese.

| Estratégia | Recall@5 | Exatidão numérica | Recusa correta | Custo médio | Latência quente média / p95 |
|---|---|---|---|---|---|
| E0 — Closed-book | — (não se aplica) | não medido | diagnóstico | não medido | não medido |
| E1 — Keyword/BM25 | não medido | não medido | não medido | não medido | não medido |
| E2 — Semântica | não medido | não medido | não medido | não medido | não medido |
| E3 — Híbrida/RRF | não medido | não medido | não medido | não medido | não medido |

| Outras métricas | Escopo | Resultado |
|---|---|---|
| Groundedness (auditoria manual) | 15 respostas | não medido |
| Estabilidade a temperatura 0 | 10 perguntas × 3 repetições | não medido |
| Acerto da classe de cobertura (`ambas`/`so_painel`/`nenhuma`) | perguntas anotadas | não medido |
| Recusa **pelo motivo certo** | 10 adversariais | não medido |
| Taxa de falso bloqueio dos guardrails | 45 perguntas legítimas | não medido |
| Ataques bloqueados | 4 ataques nomeados | não medido |
| Concordância entre juiz automático e auditoria humana | mesma amostra de 15 | não medido |
| Comparação dos três braços (agente único × Investigador+Auditor × determinístico) | 15 pareadas | não medido |
| Modelo preditivo (ROC-AUC contra baselines) | teste temporal | não medido |
| Custo real da API contra o teto de USD 25 | projeto inteiro | não medido |

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
│                                 # recuperacao · geracao · avaliacao ·
│                                 # auditoria · bloqueio · ocr_* · config
├── artefatos/                    # índice, logs JSONL, resultados, cache do demo
├── resultados/                   # evidência dos gates
├── app_streamlit.py
└── tests/                        # 525 casos, sem skips
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
  roda no caminho determinístico. As métricas de E0–E3 descrevem o pipeline de
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
