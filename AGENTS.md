# AGENTS.md — Execução: Assistente de Research Financeiro com RAG

Plano de execução do projeto descrito em `.docs/especificacao.md`, **revisão 3
(2026-08-07)**. Este arquivo é o plano; `MEMORY.md` é onde a execução parou.
Leia os dois no início de qualquer sessão.

> **A revisão 3 expandiu o escopo.** Se você trouxe da memória a ideia de que
> este projeto é "um RAG com FAISS sobre PDFs de banco", essa era a revisão 1.
> Leia a seção 1 antes de agir: o índice mudou, o extrator mudou, e entraram
> cinco camadas novas (dados estruturados, agentes, modelo preditivo,
> segurança, observabilidade).

---

## 0. Agnosticismo e privacidade da empresa-alvo (regra dura — inalterada)

O repositório é 100% **agnóstico quanto à empresa-alvo de qualquer vaga**.

- NENHUM nome de banco aparece na documentação como *possível empregador* ou
  *empresa-alvo*. Citar os 5 bancos como **fonte de dados públicos do corpus**
  é permitido e necessário — é a distinção inteira.
- Slug neutro do projeto: `assistente-research-financeiro`.
- **`.docs/` inteiro é documento de trabalho local e NUNCA é publicado.** A
  `especificacao.md` menciona a vaga de origem nominalmente (seções 3, 6 e
  5.23); publicá-la quebra a regra.
- **Exceção declarada:** `DESAFIO_CBL.md`, que a RF18 exige versionado. A cópia
  na raiz do repositório é a publicável; a de `.docs/` é a fonte. Conferido
  agnóstico em 2026-08-10 antes da cópia.
- O README foca no problema técnico: localizar informação pontual em texto
  longo, reconciliar número gerencial com número contábil e auditar alucinação
  de LLM em dado financeiro.

---

## 1. O que a revisão 3 mudou (leia antes de agir)

| Camada | Revisão 1 (2026-07-14) | Revisão 3 (2026-08-07) |
|---|---|---|
| Extração | `pypdf` ⇄ `pdfplumber` | **Mistral OCR** primário, `pdfplumber` como extrator alternativo atrás da mesma interface (5.3) |
| Índice vetorial | FAISS | **ChromaDB** — a RF06 exige filtro por metadados antes do ranqueamento (5.6) |
| Dados estruturados | CVM só como fonte de gabarito | **Camada consultável de primeira classe** — DuckDB, ITR/DFP, `mapa_contas`, `fatos_semanticos` (5.5) |
| Agentes | não existia | **Investigador + Auditor por isolamento de contexto**, com braços A/B/C e injeção de falha (5.9) |
| "Treinar" | LoRA sobre as próprias perguntas | **Modelo supervisionado** sobre o painel CVM; LoRA rebaixado a opcional (5.10, 5.22) |
| Segurança | não existia | **Presidio + Llama Prompt Guard 2 + detector de tópico próprio** (5.11) |
| Observabilidade | não existia | **Langfuse** por etapa + **DeepEval medido contra a auditoria humana** (5.12, 5.15) |
| Regras de negócio | RN01–RN03 | **RN01–RN12** |
| Teto de orçamento | USD 10 | **USD 25** (5.20) |
| Ordem de construção | 10 etapas | **18 etapas** (5.21) |

Motivo declarado da expansão (spec 3): o mesmo sistema passa a servir também
como entrega da disciplina *AI Factory: Building Intelligent Systems*, e cada
camada nova resolve um problema que a revisão 1 **já tinha identificado e
deixado em aberto** — a divergência gerencial × contábil, a fragilidade da
extração de tabela, a fronteira entre relatar e recomendar, o custo por
consulta.

---

## 2. Estado atual do repositório

**Implementado e coberto (não regredir):** configuração validada; parser
numérico pt-BR; extração via Mistral OCR *content-addressed*, cache versionado
em `corpus/ocr/` (RNF10), `pdfplumber` como alternativa atrás da mesma
interface; chunking e teste-sentinela independentes; embeddings plugáveis;
índice com transação, checksums e guarda RNF09; recuperação E0–E4 com
subconsulta por banco; geração JSON com RN01 e grounding numérico da RN02;
avaliação retomável com fingerprint v3, journal/checkpoint, teto de custo e
locks; interface cacheada com pergunta livre opt-in.

**Convenção de testes (obrigatória):** a suíte local tem **1.653 casos coletados
e nenhum skip** (medido em 2026-08-25, com `requirements-guardrails.txt` e
`requirements-modelo.txt` instalados e os pesos do Prompt Guard 2 no cache
local). NUNCA enfraquecer uma asserção para fazer
código passar — o teste é o contrato e o código se adapta a ele. `pytest` verde
é pré-condição de qualquer commit; etapa implementada = testes da etapa
presentes e passando. Enquanto houver onda paralela em voo, um vermelho
transitório pode aparecer no meio do caminho: ele é fechado antes do commit,
nunca contornado enfraquecendo o teste.

**Dados congelados:** `corpus/metadados.csv` tem 20 documentos íntegros
(interseção `2T2025`–`1T2026`), `corpus/ancoras_sentinela.csv` cobre 20/20 e
`conjunto_padrao/perguntas.csv` tem 10 perguntas `dev` + **45 `teste`
congeladas em 2026-07-29**. `candidatas_teste.csv` permanece apenas como origem
auditável da curadoria e não é carregado pelo pipeline.

**Dependências:** `requirements.txt` é o runtime pinado (Python 3.12) e já
inclui `chromadb` e `duckdb`. `requirements-local.txt` adiciona
`sentence-transformers` só para `EMBEDDING_PROVIDER=local`;
`requirements-lora.txt` isola PyTorch/PEFT do módulo opcional;
`requirements-modelo.txt` isola o scikit-learn da etapa 10, que roda offline e
não toca o caminho interativo (RN07);
`requirements-guardrails.txt` isola Presidio + modelo spaCy `pt_core_news_md`
(~40 MB) e reusa `requirements-lora.txt` para o PyTorch/transformers que o
Prompt Guard 2 vai exigir. Nenhum dos quatro entra no deploy enxuto por padrão
(RNF12).

---

## 3. Divergências conscientes da letra da especificação

Registradas aqui porque escondê-las seria o oposto do que o projeto mede.

### 3.1 Provedor de LLM: Gemini no ramo ativo

A spec 5.20 lista `LLM_PROVIDER=azure_openai | openai | deepseek | local` e
**não menciona Gemini**. O ramo ativo deste repositório é
**`gemini-3.5-flash-lite`, `reasoning_effort=low`** (Gate Gemini passou em
2026-07-15, então com `gemini-3.1-flash-lite`), com Ollama como fallback sem
API e os provedores da spec atrás da **mesma interface plugável da RNF06**.

**Motivo:** medido, não só custo. Comparação real de 2026-08-14 a 2026-08-16
sob o mesmo prompt e arnês (`resultados/comparacao_llm_2026-08.md`) —
`gemini-3.5-flash-lite/low` venceu `gemini-3.1-flash-lite` (que era o ramo
anterior por custo) e o DeepSeek V4 Flash em acerto (0,88 contra 0,40–0,60),
custo (empatado ou mais barato que o DeepSeek fora do horário de pico dele) e
latência — é a única configuração sem risco de resposta levando vários
minutos. A camada de agentes multiplica chamadas por resposta e o LLM-juiz do
DeepEval soma centenas de chamadas curtas sobre as 45 perguntas — a spec 5.20
reconhece isso ao subir o teto de USD 10 para USD 25; um modelo de tier
barato continua mantendo o teto auditável, mas deixou de ser o único
critério.

**O que a divergência não autoriza:** trocar o provedor não relaxa nada. Preço
por 1M de tokens continua obrigatório na configuração (sem ele o teto não é
auditável), temperatura 0 continua obrigatória na avaliação, e o modelo usado
fica registrado por execução (RNF08).

### 3.1-bis Estratégia E4 (`fatos`) — quarta via de recuperação, acrescentada

A spec 5.16 fecha o vocabulário de estratégias em **E0–E3**. Este repositório
acrescentou **E4 = `fatos`** em 2026-08-20: recuperação por **tabela de fatos
numéricos** (`src/fatos.py`), que ranqueia o trecho por quantos números da
métrica perguntada ele contém, em vez de por similaridade de texto.

**Motivo medido, não estético.** O E3 recupera a *página* certa em 12/15 das
factuais congeladas, mas o *trecho* que ele traz contém o valor exato do
gabarito em só 9/15 — é a falha do DEV007: a prosa da página certa arredonda
("R$ 3,4 bilhões") e a tabela com `3.431` fica fora do top-k. O E4 mede
**11/15** no mesmo orçamento de top-5, e 27/45 de recall@5 total contra 22/45
do E3.

**E4 é canal PURO, não fusão** — e isso foi medido, não escolhido. Sob o mesmo
top-5, RRF(E3, fatos) cai para 8/15 e o intercalado para 8–9/15: dividir cinco
vagas entre duas listas expulsa justamente o trecho que só uma delas achou. A
união só vence com dez vagas, o que é outro orçamento de contexto e não seria
comparável com E1–E3.

**O que a divergência não autoriza:** E4 é mais uma coluna da mesma comparação,
não uma exceção a ela. Roda a temperatura 0, no mesmo prompt de geração, sob a
mesma guarda da RN02, e **fora da camada de agentes** como o §6 exige. O
`src/avaliacao.py` continua exigindo o conjunto COMPLETO de estratégias na
publicação do congelado — o efeito prático é que a rodada publicável passou de
180 para **225 chamadas**, e nenhuma estratégia pode ser omitida para melhorar
a foto.

### 3.2 OCR — migrado (2026-08-11); estado atual, não mais divergência

A spec 5.3 torna o Mistral OCR o extrator **primário**. Isso **já é o caso**:
`Config.extrator` tem default `"mistral_ocr"` (`src/config.py`), a variável
antiga `EXTRACAO_PDF_MODO` foi removida — setá-la levanta erro explícito
apontando para `EXTRATOR=mistral_ocr|pdfplumber` (RNF03: falhar fechado em vez
de silenciosamente ignorar a variável trocada) —, e o cache vive versionado em
`corpus/ocr/<hash-do-pdf>.json` (RNF10), carregado pela Batch API: job
`0eb6eab2`, 20/20 documentos, 2.790 páginas, zero erros, USD 5,58. `pdfplumber`
continua disponível atrás da mesma interface plugável, como extrator
alternativo — nunca fallback automático.

O **gate G3** rodou (`resultados/gate_g3.md`, 2026-08-11, custo zero — lê o
cache em disco) e o veredito é **favorável mas não conclusivo**: na âncora de
sanidade, OCR e `pdfplumber` empatam praticamente (20/20 × 18/20, e 20/20 nos
dois tolerando escala perdida) — o valor de capa também aparece em texto
corrido, e um parser posicional o encontra de qualquer forma. A diferença real
está na estrutura de tabela reconstruída: 37.612 linhas contra 28.268 (+33%),
concentrada no Itaú (3,5×); no BTG é o `pdfplumber` que reconstrói mais
(0,5×). A decisão de trocar o extrator não se reverte, mas a spec 5.3
antecipava uma vitória mais clara do que a medição entregou — ver o relatório
para a ressalva completa (contagem de linhas mede estrutura, não correção).

O índice vetorial em produção já é construído sobre o cache OCR — não há
namespace separado pendente.

### 3.3 Gate G4 — rodou, reprovou, e foi destravado com procedência declarada

G4 (lucro pelo mapa semântico × release, banco a banco) **rodou, reprovou em
2026-08-11 e foi reaprovado em 2026-08-22** (`resultados/gate_g4.md`, custo
zero na reexecução — lê o painel e o cache OCR local). Parte A (mapa ×
conferência congelada) **aprovada** desde a primeira rodada — nenhuma célula
reprova por erro de mapeamento nos cinco emissores. Parte B chegou a **20/20
CONFERIDO** por duas ações distintas, cada uma com evidência versionada:

- **BTG 4T2025 (sem âncora → conferido):** a demonstração anual em IFRS tinha
  63 de 71 páginas com fonte sem mapa de caracteres (`pdfplumber`/`pdftotext`
  devolviam `(cid:N)`). Localizada a página certa por **alinhamento
  geométrico de coluna** (a estrutura tabular sobrevive à corrupção de fonte
  mesmo quando o texto não), e lida com OCR pago e escopo travado a essa
  única página (`scripts/ocr_ancora_ifrs.py`, custo real USD 0,30 — três
  bugs do próprio script perderam duas chamadas já pagas antes da correta;
  detalhe completo em `resultados/ancora_btg_4T2025.md`). Resultado: Δ =
  +0,00002% — CONFERIDO.
- **SANTANDER 3T2025 e 4T2025 (divergentes → conferidos com correção):** a
  causa já estava apurada (o arquivo da CVM se contradiz internamente — a
  conta-pai bate com a demonstração em IFRS ao milhar, as contas-filhas não).
  Em vez de excluir as células ou corrigir em silêncio, foi construída uma
  **tabela de correções com procedência obrigatória**
  (`corpus/cvm/correcoes_contabeis.csv`, carregada e aplicada por
  `src/dados_estruturados.py::carregar_correcoes`/`aplicar_correcoes`, RN09):
  cada linha declara o valor original, o valor corrigido, o documento e a
  página-fonte, o SHA-256 do PDF e uma evidência de no mínimo 60 caracteres.
  **Guarda anti-porta-dos-fundos:** a correção só é aplicada se
  `valor_original_reais` ainda bater com o painel ao vivo (tolerância 0,5);
  se a CVM republicar o arquivo, a correção para de valer e a carga **falha**
  em vez de aplicar às cegas. A visão `fatos_semanticos` expõe os dois
  números (`valor_reais` corrigido e `valor_reais_arquivo` original) e a
  flag `corrigido` — nunca silencioso. 24 testes em
  `tests/test_correcoes_contabeis.py`.

Nenhuma célula foi excluída e nenhum número foi trocado sem procedência
auditável — as duas saídas que a "decisão pendente do Ygor" desenhava foram,
na prática, a segunda (corrigir com procedência declarada) para o Santander e
uma terceira via (pagar o OCR pontual) para o BTG, que a decisão original
deixava em aberto por orçamento.

### 3.4 Chunking de tabela — invariante acrescentada em 2026-08-23

**Nenhum chunk pode abrir com linhas de valor sem a linha que nomeia a coluna.**
A spec 5.3 já dizia que "número recuperado sem o rótulo da coluna é número
inútil para citação" e essa era a razão declarada de ter trocado o extrator; o
que faltava era a invariante ser **verificada** em vez de suposta.

Veio da auditoria manual: o sistema respondeu `R$ 12.144 milhões` (coluna
4T25) a uma pergunta sobre o 1T2026, cujo valor é `11.875`. O OCR estava
certo e a tabela íntegra — o **chunk** é que abria nas duas últimas linhas
dela, órfãs do cabeçalho. Duas causas independentes, ambas no `src/ingestao.py`:
a cauda de sobreposição copiava tokens sem olhar o tipo de bloco, e a partição
de tabela grande media a parte sem contar a legenda de unidade que ela própria
emite. **101 chunks** abriam assim; **18 das 45 congeladas** recebiam um no
top-5.

**A primeira correção piorou o sistema e o registro disso é parte da regra.**
Descartar tabela da cauda zerou os órfãos e derrubou a exatidão factual junto
(E2 0,467 → 0,267), porque a duplicação do overlap era **também** rede de
segurança — um valor perto da fronteira aparecia em dois chunks e recuperar
qualquer um resolvia. A correção final **recoloca o cabeçalho** na cauda em vez
de descartar a tabela.

**O que a invariante exige de quem mexer no chunker:**
`tests/test_chunking_tabela_orfa.py` roda contra o índice publicável e falha se
um só chunk voltar a abrir com 3+ colunas de valor sem cabeçalho. As
contraprovas do mesmo arquivo travam o que a correção não pode custar — a
sobreposição de prosa continua atravessando e nenhuma linha de dado se perde na
partição.

**Lição de método, para não repetir:** `recall@5` é medido **por página** e foi
sinal enganoso aqui — contava como acerto o chunk órfão, que não conseguia
responder. Para julgar chunking, medir se o **valor** está no top-5, não se a
página está.

### 3.5 Dois painéis CVM — janela larga só para o treino (2026-08-23)

A spec 5.5 trata o painel como um só. **Passaram a ser dois**, e a separação é
a razão de a etapa 10 ter saído do lugar.

| Painel | Janela | Quem usa |
|---|---|---|
| `artefatos/cvm.duckdb` | 2025–2026 | camada **consultável** (agentes, Streamlit, gates) |
| `artefatos/cvm_treino.duckdb` | **2011–2026** | **só** o modelo supervisionado offline (RN07) |

**A decisão de casar o painel consultável com o corpus continua valendo** — ela
existe para que tudo que o sistema responde ao usuário tenha documento
correspondente. O que mudou é que o modelo preditivo não responde a usuário
nenhum (RN07), então nada o obriga a viver na mesma janela.

**Motivo medido, não conveniência.** Com um ano de painel, o split temporal
tinha **uma única partição**: o IC 95% do AUC saía com largura 0,08 e nenhuma
comparação de feature ou de modelo era resolvível — duas foram tentadas e as
duas ficaram indecidíveis. Com 2011–2026 são **21.903 observações e 47 folds**
de walk-forward, e as mesmas comparações passaram a ter p da ordem de 1e-09.

**O que a janela larga destravou:** o grupo de features que só existe com
histórico longo — ganho de **+0,0102 de AUC (p = 7,0e-09)**, confirmado depois
em folds não vistos (+0,0072, p = 4e-06).

> **Correção de atribuição (2026-08-25).** Uma versão anterior deste parágrafo
> creditava o ganho à defasagem sazonal T−3 ("o preditor natural do alvo T+1 é
> o mesmo trimestre do ano anterior"). A ablação individual mostra que
> `prejuizo_no_mesmo_trimestre_do_ano_anterior` mede **exatamente zero**
> (−0,0005, p = 0,46). Quem carrega o grupo é **`taxa_prejuizos_4t`**, que é
> **janela móvel de 4 trimestres, não defasagem sazonal** (+0,0039, p = 3e-04).
> O número estava certo; a história em cima dele, não. A sazonalidade do lucro
> vive no **nível** e o alvo binariza o **sinal** — se o alvo virar magnitude,
> as sazonais precisam ser re-testadas, não apagadas.

**O que a divergência não autoriza:** a janela larga é do painel de treino e de
mais nada. O gate G4, a conferência de âncora e tudo que responde ao usuário
seguem no painel casado com o corpus. `scripts/construir_painel_cvm.py` recebe
`--destino` justamente para que os dois não se confundam.

**Achado lateral, registrado:** um arquivo da CVM (`itr_cia_aberta_BPA_con_2020.csv`)
tem *mojibake* na origem — texto UTF-8 codificado duas vezes, com 12 bytes fora
do latin-1. É saneado na extração, em campo puramente descritivo, com o motivo
no script. A carga de produção segue exigindo latin-1 estrito.

### 3.6 RN07 passou a ser condicional ao modo (2026-08-24)

A RN07 dizia, sem qualificação, que o modelo preditivo **não** é exposto como
resposta sobre companhia nomeada. **Passou a depender do modo de operação**, e
a razão é uma leitura da norma que a versão anterior não tinha feito.

| Modo | Pergunta prospectiva sobre emissor nomeado |
|---|---|
| **Instância pública** (padrão) | Recusa o número por emissor + entrega histórico arquivado, regime de risco por porte e panorama agregado |
| **Local/autenticado** (`PREVISAO_POR_EMISSOR_HABILITADA=1`) | Acrescenta o escore do emissor, etiquetado como fora de domínio, com a taxa-base do porte ao lado |

**Motivo.** A Res. CVM 20/2021 regula a *atividade* de análise — elaborar
relatório destinado a auxiliar decisão de investimento — e sua mordida está na
**divulgação a terceiros**. Ferramenta que um analista credenciado usa para
conferir o próprio trabalho é insumo do processo dele, não relatório não
registrado. A RN07 original era mais restritiva do que a norma exige *para uso
interno*; continua correta para o contexto de deploy real deste sistema, que é
um Streamlit aberto e sem autenticação.

**O que a divergência não autoriza — três travas em código, não em texto:**

1. **O modelo continua fora do caminho interativo.** Nem o modo público nem o
   local importam `src.modelo` em tempo de resposta: os dois leem artefato
   calculado offline por `scripts/gerar_panorama_modelo.py`. A varredura de
   import de `TestRN07` continua valendo e agora inclui `src/projecao.py`.
2. **O escore por emissor não é versionado.** `panorama.json` (agregado) é
   publicável e entra no Git; `escores_por_companhia.json` está no
   `.gitignore`, para que o deploy público **não tenha** o dado em vez de
   tê-lo e prometer não usar.
3. **O agregado não pode vazar por eliminação.** Publicar "0 das 13
   instituições financeiras estão no decil de risco" ao lado de uma pergunta
   sobre um banco permite deduzir o escore daquele banco. Por isso só se
   publica o agregado do **painel inteiro** e a taxa histórica por porte,
   nunca a contagem setorial do trimestre corrente — `_agregado_seguro` trava
   e `TestVazamentoPorEliminacao` verifica.

**Falso bloqueio medido:** o detector de pergunta prospectiva dispara **0 vezes
nas 55 perguntas congeladas** (`TestFalsoBloqueio`), mesma disciplina da
etapa 14.

**Ressalva técnica que a permissão legal não remove:** para os cinco bancos do
corpus, todos na faixa de ativo onde o prejuízo ocorre em 0,6% dos trimestres,
o escore sai quase constante e quase zero. Autorização não torna um número não
informativo em útil. O valor real do módulo está em instituição financeira de
porte médio (AUC 0,832 abaixo de R$ 100 bi) e nas companhias hoje lucrativas
(lift 4,35), não nos cinco do corpus.

---

## 4. Contratos e regras invioláveis

### 4.1 Regras de negócio RN01–RN12

| ID | Regra (resumo — texto normativo na spec §4) | Onde é verificada |
|---|---|---|
| RN01 | Toda resposta cita empresa, documento, trimestre e página dos trechos usados | `src/geracao.py` · `tests/test_regras.py` |
| RN02 | Sem evidência suficiente no trecho recuperado, o sistema declara isso — nunca responde de memória paramétrica | `src/geracao.py` · `tests/test_regras.py` |
| RN03 | Instância pública limita perguntas livres por sessão **e** mantém teto no provedor; o controle real é o do provedor | `app_streamlit.py` · `src/config.py` |
| RN04 | SQL do painel roda somente-leitura, sobre lista branca, com DDL/DML bloqueado por análise sintática, `LIMIT` e timeout — falha de guarda devolve erro, nunca executa | `src/dados_estruturados.py` · `tests/test_dados_estruturados.py` |
| RN05 | Sem recomendação de investimento, preço-alvo ou aconselhamento pessoal. Âncora legal: **Res. CVM 20/2021** (análise) e **19/2021** (consultoria); cada subtipo de recusa mapeia à sua | `src/seguranca.py` · `tests/test_seguranca.py` |
| RN06 | PII do usuário é anonimizada antes de qualquer chamada externa e nunca entra em log, trace ou cache | `src/seguranca.py` · `src/reconhecedores_br.py` |
| RN07 | Previsão sobre companhia nomeada é **condicional ao modo** (§3.6): instância pública recusa e entrega agregados; modo local/autenticado expõe o escore etiquetado. Em nenhum dos dois o caminho interativo importa `src.modelo` | `src/projecao.py` · `src/modelo/` · `tests/test_projecao.py` · `TestRN07` |
| RN08 | Verbete de glossário de métrica gerencial é sempre atribuído a instituição e release de origem | `src/ingestao.py` (glossário, RF19) |
| RN09 | `cd_conta` nunca é chave de significado sozinho: todo conceito passa pelo mapa semântico validado; consulta que referencie `cd_conta` direto é rejeitada pela lista branca | `src/mapa_contas.py` · gate G4 |
| RN10 | Valor derivado por aritmética entre períodos — notadamente o 4T, que não existe como ITR — sai marcado como **derivado**, com a conta explicitada | `src/dados_estruturados.py` · `app_streamlit.py` |
| RN11 | Companhia é resolvida por `CD_CVM`, nunca por nome. Nome que resolve para mais de uma companhia **gera pergunta de desambiguação** — nunca escolha automática | `src/cobertura.py` · `tests/test_cobertura.py` |
| RN12 | Ausência de evidência é **classificada**: `ambas` / `so_painel` / `nenhuma`. Companhia no painel mas fora do corpus recebe o dado contábil e a declaração do que falta. Especializa a RN02, não a relaxa | `src/cobertura.py` · `src/geracao.py` |

### 4.2 Honestidade de avaliação

`pytest` cobre regras de formatação, chunking e contrato (passa/falha). Recall,
exatidão, recusa, groundedness, falso bloqueio, acerto de cobertura e o veredito
dos três braços são **resultados avaliados** — rodados no conjunto congelado a
temperatura 0, calculados honestamente, logados em `artefatos/logs_execucoes/`
(RNF08) e expostos no README como **número medido ou a palavra "não medido"**.
Meta e resultado são colunas diferentes. Nenhum número de `dev` vira resultado
final.

Onde a spec declarou limiar antes da execução, ele é respeitado: a comparação
A/B/C só declara diferença a partir de **6 discordâncias na mesma direção**
(McNemar exato, p = 0,031); abaixo disso publica-se "indistinguível neste
tamanho de amostra".

### 4.3 Segredos, dados e determinismo

- Nunca versionar PDFs (`corpus/raw/`); NUNCA chave real em código ou commit —
  `.env` local e secrets no deploy (RNF04).
- O modo demonstração abre **sem nenhum segredo configurado** (RNF12); ausência
  de chave obrigatória no modo livre falha com mensagem explícita, nunca com
  degradação silenciosa.
- `HF_TOKEN` é segredo **de build**, nunca de runtime. Se o contêiner exigir
  token para subir, a RNF12 está quebrada e o build está errado.
- Chamada externa paga exige opt-in explícito (`--permitir-api-paga`) e passa
  pelo journal write-ahead antes e depois.

---

## 5. Gates — estado real

| Gate | O que verifica | Estado |
|---|---|---|
| **G1** | Criar recurso Azure OpenAI na assinatura de estudante | ❌ **Não disponível** (`resultados/gate.md`, 2026-07-15). Reservado ao pré-deploy; créditos vão para hospedagem |
| **G2** | Cobertura da CVM suficiente para o rótulo T+1 do modelo preditivo | ✅ **Fechado em 2026-08-07** na fase de investigação — 1.351 observações de trimestre isolado, ~29% de positivos em um ano |
| **G3** | Mistral OCR em **um** release contra `pdfplumber`, conferindo valores-âncora | ✅ **Rodado em 2026-08-11**, favorável mas não conclusivo (§3.2, `resultados/gate_g3.md`) |
| **G4** | Lucro resolvido pelo mapa semântico bate com o release, **banco a banco, em todos os trimestres** | ✅ **Reprovou em 2026-08-11, APROVADO em 2026-08-22** (§3.3, `resultados/gate_g4.md`) — 20/20 CONFERIDO; BTG 4T2025 fechado por OCR pontual, Santander 3T/4T2025 fechados por correção com procedência declarada |
| Gate L1 | Inferência local Ollama sem API | ✅ Passou em 2026-07-15 (`resultados/gate_local.md`), com `prompt=v1` |
| Gate Gemini | Duas chamadas controladas ao ramo ativo | ✅ Passou em 2026-07-15 (`resultados/gate_gemini.md`) |

Os relatórios em `resultados/` datados de 2026-07-15 são **históricos**: o Gate
L1 registra `prompt=v1` e o Gate Azure antecede o hardening atual. Nenhum deles
comprova o prompt ou os adaptadores atuais até ser regenerado explicitamente.

G4 é o gate com maior potencial de dano do projeto. O mesmo `cd_conta` designa
contas diferentes conforme o plano de contas: `3.09` é lucro líquido no Itaú,
Santander e BTG, e *resultado antes das participações* no BB e no Bradesco. Uma
consulta ingênua devolve **número plausível, não nulo e errado** para 2 dos 5
bancos — a falha exata que o projeto existe para combater, dentro da própria
base. Por isso ele para o pipeline.

---

## 6. Dois caminhos de execução (RNF11) — a separação que não se negocia

```text
CAMINHO INTERATIVO (o produto)
  pergunta → guardrails de entrada → Investigador → [filtro de contexto]
           → Auditor → guardrails de saída → resposta → Streamlit
           (instrumentado por Langfuse)

CAMINHO DE AVALIAÇÃO (o benchmark, determinístico)
  45 perguntas congeladas → E0–E4 → métricas + DeepEval
  SEM camada de agentes
```

**O benchmark de recuperação E0–E4 nunca passa pela camada de agentes.** Motivo:
a orquestração multiagente introduz variabilidade de plano — quantas
ferramentas o agente chama, em que ordem, quantos tokens gasta — que destruiria
a comparabilidade entre estratégias mesmo a temperatura 0.

A regra **não** proíbe medir a camada de agentes: essa medição é obrigatória e
roda em **conjunto próprio**, com os três braços (A: agente único · B:
Investigador+Auditor · C: determinístico sem LLM) sobre o subconjunto pareado
de 15 extraído das 45.

Os dois caminhos compartilham as mesmas ferramentas e o mesmo prompt de
geração; só a orquestração difere, e o resumo executivo reporta cada um
separadamente.

---

## 7. Plano de execução — 18 etapas (spec 5.21)

Legenda: ✅ concluída · 🔄 em execução agora · ⏸️ adiada por decisão · ⬜ pendente

| # | Etapa | Dono | Estado |
|---|---|---|---|
| 1 | **Gates do dia 1** — G1 (Azure) e G3 (OCR × `pdfplumber` em um release), com evidência antes de escrever código dependente | sessão principal | G1 ❌ resolvido para o pré-deploy · G3 ✅ (§3.2) |
| 2 | **Corpus** — regra da interseção, `metadados.csv` com URL, data e SHA-256 | — | ✅ 20 documentos, hashes registrados |
| 3 | **CVM → DuckDB** — carga ITR/DFP com as **seis regras de armadilha**, `mapa_contas`, visão `fatos_semanticos`, derivação do 4T, e o **gate G4 bloqueante** | `dados-cvm` | ✅ implementada · ✅ G4 aprovado em 2026-08-22 (§3.3) — etapa 10 desbloqueada |
| 4 | **Ingestão/OCR** com cache versionado + normalizador pt-BR + testes de qualidade e sentinela | sessão principal | ✅ `mistral_ocr` ativo, cache em `corpus/ocr/` (§3.2) · ✅ chunking de tabela corrigido em 2026-08-23 (§3.4) — 0 chunks abrindo sem cabeçalho, era 101 |
| 5 | **Indexação** — BM25 + embeddings em **Chroma**, com a guarda RNF09 | `indice-recuperacao` | 🔄 (migração FAISS → Chroma) |
| 6 | **Recuperação** — filtro de metadados, subconsulta por banco, E0–E4 (§3.1-bis) | `indice-recuperacao` | ✅ base implementada · 🔄 sob a migração |
| 7 | **Geração** — contrato JSON, citação obrigatória, recusa (RN01–RN02) | sessão principal | ✅ · ⬜ marcações de RN10/RN12 na resposta |
| 8 | **Conjunto-padrão** — 45 congeladas + ~10 dev, conferidas pela classe de verificação | `conjunto-padrao` | ✅ congelado 2026-07-29 · ⬜ colunas novas da revisão 2 (`cobertura_esperada`, `motivo_recusa_esperado`, `base_esperada`, `rota_esperada`) |
| 9 | **Comparação de estratégias E0–E4** — só `dev` na iteração; o congelado roda ao final, com log por execução | `observabilidade-avaliacao` | ✅ rodada em 2026-08-21 no congelado (45 × 5 = 225 chamadas, v6) — factual E1 0,400 · E2 0,333 · E3 **0,467** · E4 0,400; comparativa (métrica nova) E1 0,000 · E2/E3 0,100 · E4 **0,200**; E4 × E3 **indistinguível** (2×3 discordâncias, limiar 6) pela 3ª rodada seguida. Ver `MEMORY.md` |
| 10 | **Modelo preditivo** — split temporal, baselines, métricas completas | `modelo-preditivo` | ✅ **2026-08-23** — painel de treino próprio (2011–2026, §3.5), **21.903 obs**, 33,3% positivos. **Walk-forward de 47 folds**: boosting AUC **0,866** × persistência 0,752, vencendo em **47/47**. Ganho vem das features SAZONAIS (+0,0102, p=7,0e-09, 42/47); as do O-score de Ohlson deram **resultado negativo** e foram removidas. `resultados/modelo_preditivo_2026-08-23.md`. **Revisado em 2026-08-23** (`resultados/revisoes_modelo_2026-08-23.md`): alvo alternativo de **2 trimestres consecutivos** melhora tudo (lift@10% 2,55→**3,36**, sinaliza 57,6%→41,5%); **SMOTE PIORA** (−0,006, p=5e-08, e dobra o erro de calibração); ajuste de hiperparâmetros rende **zero** fora dos folds de busca. **Robustez em 2026-08-24** (`resultados/robustez_modelo_2026-08-24.md`): purga/embargo acrescentada — AUC publicado corrige 0,881 → **0,8797**; controle setorial **rejeitado** (+0,0005, p=0,19); recalibração isotônica/Platt **não melhora**; LightGBM **empata** (p=0,66); a decisão sobre as features sazonais **sobrevive em folds não vistos** (+0,0072, p=4e-06). **DEBATE DE DOIS ESPECIALISTAS em 2026-08-25** (`resultados/debate_modelo_2026-08-25.md`) — três retratações: (a) o "interruptor do porte" era contaminação de `is_banco`, 29 de 35 eventos vinham de private equity e de uma companhia em liquidação; recorte setorial REMOVIDO; (b) vazamento no trimestre de VALIDAÇÃO corrigido — ponto de operação vai de 57,6% para 34,5% sinalizado; (c) `early_stopping='auto'` ajustava o modelo sozinho a partir do fold 21, tornando falsa a ressalva de "nenhum ajuste". **Manchete corrigida:** o ganho publicável é **+0,019 sobre `taxa_prejuizos_4t` crua** e **+0,073 sobre a identidade implementável**, não +0,11 sobre a persistência binária. **AUC intra-companhia 0,663 contra 0,865 agregado** — o modelo ordena QUAIS companhias, não QUANDO viram; 97,1% do decil superior já está em prejuízo |
| 11 | **Ferramentas + agentes** — `verificar_cobertura`, Investigador e Auditor com filtro de contexto **em código**, teste que falha se o rastro vazar, braços A/B/C, triagem de cobertura; projeções depois | `agentes-investigacao` | ⬜ |
| 12 | **Injeção de falha (RF25) e comparação dos três braços (RF26)** — registrar o veredito, inclusive se for "o determinístico basta" | `agentes-investigacao` + `observabilidade-avaliacao` | ⬜ |
| 13 | **Langfuse + DeepEval** — traces por etapa e matriz de concordância com a auditoria manual | `observabilidade-avaliacao` | 🔄 matriz de concordância **medida** em 2026-08-23 (0,867, `scripts/medir_juiz_groundedness.py`) · ⬜ Langfuse e suíte DeepEval formal |
| 14 | **Guardrails** — ataques bloqueados × falso bloqueio medido nas 45 legítimas (meta 0) | `seguranca-guardrails` | ✅ **completa** em 2026-08-21 — base determinística, ligada ao caminho interativo, **Presidio e Llama Prompt Guard 2 (86M) integrados** — **20/20 ataques · 0/45 falso bloqueio de entrada · 0/855 de saída** (`resultados/guardrails.json`, com as duas camadas ML ligadas na contraprova); `src/seguranca.py`, `src/reconhecedores_br.py`, `src/reconhecedor_presidio.py`, `src/prompt_guard.py`, `conjunto_padrao/ataques.csv`, `responder_com_guardrails` em `src/agentes.py`, portão em `app_streamlit.py`, `requirements-guardrails.txt`, 87 testes · `presidio_habilitado`/`prompt_guard_habilitado` desligados por padrão (RNF12) — pesos do Prompt Guard 2 já baixados e pinados (`guardrails_modelo_injecao_revision`), `HF_TOKEN` só foi necessário no download, runtime usa `local_files_only` |
| 15 | **Interface Streamlit** — streaming, estado de sessão, painéis de evidência, etiqueta de derivado, estado de cobertura, veredito do Auditor | `interface-produto` | ✅ base cacheada + pergunta livre · ⬜ camadas novas |
| 16 | **Publicação** — Container Apps primário, teto/alerta no provedor, dois modos validados | `interface-produto` | ⬜ |
| 17 | **`DESAFIO_CBL.md`, README e resumo executivo** (metas × resultados) | `documentacao-projeto` | ✅ desafio e README · ⬜ resumo executivo |
| 18 | **(Opcional) LoRA** — roteador de entrada, com split por pergunta-base | — | ⬜ opcional |
| 19 | **Bônus — múltiplos de mercado (P/L, P/VPA)** — fora da spec 5.21, proposta em 2026-08-21 durante conversa sobre Value Investing. `precos_fechamento` no DuckDB (5 tickers, fonte pública), disciplina *point-in-time* obrigatória (preço da data do release, nunca o de hoje), múltiplo marcado como **derivado** pela RN10, medido em conjunto próprio — nunca nas 45 congeladas nem em E0–E4 | — | ⬜ **não iniciar antes das etapas 1–18 concluídas; G4 aprovado é pré-condição** |

**Transversal:** rodar `auditor-conformidade` (somente leitura) ao final de cada
onda de implementação, antes de considerar a etapa concluída.

**Regra de crescimento do gabarito: acrescente coluna, nunca linha.** O gargalo
declarado do projeto é o gabarito manual. Toda capacidade nova é avaliada
anotando mais sobre as mesmas 45 perguntas.

---

## 8. Estrutura do repositório

Alvo da spec 5.21, com o que já existe marcado:

```text
├── AGENTS.md · CLAUDE.md · MEMORY.md · README.md · DESAFIO_CBL.md · LICENSE (MIT)
├── .docs/                       (local — NUNCA publicado; exceto a cópia do desafio)
├── requirements.txt · requirements-local.txt · requirements-lora.txt ·
│   requirements-guardrails.txt · requirements-modelo.txt (sklearn + imblearn)
├── .env.example · .gitignore · pytest.ini
├── executar_pipeline.py         (orquestrador; --amostra, --etapa)
├── scripts/
│   ├── baixar_corpus.py         ✅   ├── baixar_cvm.py            ⬜
│   ├── gate_local.py  ✅ · gate_gemini.py ✅ · gate.py ✅ · gate_seguranca.py ✅
│   ├── medir_guardrails.py ✅   (etapa 14 — custo zero, evidência RNF08)
│   ├── treinar_modelo.py ✅     (etapa 10 — custo zero, treino em CPU)
│   ├── construir_painel_cvm.py ✅ (ZIPs da CVM → DuckDB; painel largo de treino)
│   ├── experimentos_modelo.py ✅ (matriz: alvo 1T×2T, SMOTE, calibração, ajuste)
│   ├── experimentos_robustez.py ✅ (purga, setor, calibração, LightGBM)
│   ├── gerar_panorama_modelo.py ✅ (artefato agregado da rota prospectiva)
│   ├── medir_juiz_groundedness.py ✅ (etapa 13 — juiz × auditoria humana)
│   ├── preprocessar_ocr_mistral.py ✅ · reconciliar_chamada_orfa.py ✅
│   └── preparar_auditoria_final.py · executar_estabilidade.py ·
│       consolidar_auditoria_final.py                             ✅
├── corpus/
│   ├── raw/                     (fora do Git — regenerável por script)
│   ├── ocr/                     ✅ cache de OCR versionado (RNF10)
│   ├── metadados.csv            ✅ fonte de verdade, versionada
│   └── ancoras_sentinela.csv    ✅
├── src/
│   ├── ingestao.py ✅ · normalizacao.py ✅ · indexacao.py 🔄 · recuperacao.py 🔄
│   ├── geracao.py ✅ · avaliacao.py ✅ · auditoria.py ✅ · bloqueio.py ✅
│   ├── config.py ✅ · ollama.py ✅ · ocr_mistral.py ✅ · ocr_cache.py ✅
│   ├── dados_estruturados.py 🔄 · mapa_contas.py 🔄
│   ├── ferramentas.py ✅ · cobertura.py ✅ · agentes.py ✅ · fatos.py ✅
│   ├── braco_agente.py ✅ · braco_determinista.py ✅ · injecao_falha.py ✅
│   ├── seguranca.py ✅ · reconhecedores_br.py ✅ · reconhecedor_presidio.py ✅
│   ├── prompt_guard.py ✅ · projecao.py ✅ · observabilidade.py ⬜
│   └── modelo/ construir_painel.py ✅ · treinar.py ✅ · prever.py ✅
├── conjunto_padrao/
│   ├── perguntas.csv            ✅ 10 dev + 45 teste congeladas
│   └── ataques.csv              ✅ 20 ataques (11 tópico + 9 injeção)
├── artefatos/
│   ├── cvm.duckdb               (consultável, 2025–26; fora do Git)
│   ├── cvm_treino.duckdb        (treino, 2011–26; fora do Git — §3.5)
│   ├── indice_vetorial/         (Chroma; só `metadados_construcao.json` versionado)
│   ├── modelo/                  (binário fora do Git; métricas e panorama versionados;
│   │                             escores_por_companhia.json FORA do Git — §3.6)
│   ├── logs_execucoes/          (JSONL por execução completa — versionado, RNF08)
│   └── resultados_avaliacao/    (métricas + respostas cacheadas do demo — versionadas)
├── resultados/                  (evidência dos gates)
├── app_streamlit.py             ✅
└── tests/  conftest · test_ingestao ✅ · test_normalizacao ✅ · test_regras ✅
         · test_dados_estruturados ✅ · test_seguranca ✅ · test_isolamento ✅
         · test_cobertura ✅ · test_guardrails_integracao ✅ · test_deepeval ⬜
         · test_chunking_tabela_orfa ✅ · test_guarda_rn02_auditoria ✅
         · test_projecao ✅ (rota RN07 condicional ao modo, 40 casos)
         · test_modelo ✅ (inclui TestRN07 e TestVazamentoTemporal)
         (+ suítes de hardening já existentes)
```

**O que é versionado e o que não é:** versionados o cache de OCR
(`corpus/ocr/`), `metadados.csv`, o índice de deploy, os logs JSONL e as
respostas cacheadas do demo. Fora do Git: PDFs brutos, ZIPs da CVM,
`cvm.duckdb`, o índice de desenvolvimento, pesos de modelo e qualquer segredo.

---

## 9. Entregável final

`executar_pipeline.py` processando ponta a ponta: suíte verde sem skips; corpus
íntegro pelo manifesto; painel CVM carregado com as seis regras de armadilha e
**G4 aprovado**; índices construídos com guarda RNF09; E0–E4 rodadas nas 45
congeladas no caminho determinístico, com log JSONL; camada de agentes medida
em conjunto próprio, com o veredito dos três braços publicado **mesmo se for
negativo**; guardrails com ataques bloqueados e falso bloqueio medidos; modelo
preditivo contra baselines, fora da caixa de ferramentas do agente; números
reais no README (metas × resultados) e resumo executivo (spec 5.18).

Critério de "pronto" completo: `.docs/especificacao.md` §7. O repositório final
sobe sem nenhuma amarra ao nome da empresa-alvo e sem `.docs/`.

---

## 10. Memória entre sessões — MEMORY.md

O `MEMORY.md` é o arquivo de **handoff entre sessões de execução** — não um
changelog, não um substituto deste AGENTS.md. A divisão de papéis: AGENTS.md
descreve o plano (estável, muda só quando o escopo muda); MEMORY.md descreve
**onde a execução parou** (muda a cada sessão que avança o projeto).

- **No início de toda sessão:** ler o `MEMORY.md` antes de agir. Ele registra
  decisão, bloqueio ou estado que não é óbvio a partir do código ou do
  `git log` — qual ramo de provedor está ativo, qual gate passou, o que uma
  onda paralela deixou pela metade, qual bloqueio externo está em aberto.
- **Ao final de toda sessão que mudar o estado da execução:** sobrescrever
  (nunca só anexar) as seções desatualizadas. Formato:

  ```markdown
  ## Estado atual
  - Etapa ativa (plano §7): <número e nome>
  - Última etapa concluída: <número e nome> (<data>)

  ## Decisões e bloqueios em aberto
  - <decisão que desvia do padrão da spec, com o motivo>
  - <bloqueio esperando algo externo: chave, cota, disponibilidade>

  ## Próximo passo concreto
  - <ação específica, imediatamente executável pela próxima sessão>
  ```

- **O que NÃO vai no MEMORY.md:** nada que já esteja em `git log`/`git diff`;
  números de métricas (vivem em `artefatos/` e no README); segredos ou chaves
  (RNF04); o plano em si (isso é este arquivo).
- Mantenha curto — poucas dezenas de linhas. Se virar changelog, está sendo mal
  usado: o Git já é o changelog.
