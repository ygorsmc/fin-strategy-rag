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

## 2. Onde está o estado da execução — não aqui

**Este arquivo é o plano; `MEMORY.md` é onde a execução parou.** A divisão é do
§10 e vale como regra dura, porque quebrá-la já custou caro: esta seção
sustentou por semanas uma contagem de suíte que estava **260 casos defasada**, e
o §3 chegou a 45% do arquivo com narrativa de candidatos já medidos.

| Pergunta | Onde se responde |
|---|---|
| O que já está implementado, qual a contagem da suíte, qual gate passou quando | `MEMORY.md` |
| O que foi medido e descartado, e o que reabriria | `resultados/becos_sem_saida.md` |
| Os números de uma rodada | `artefatos/` e o relatório datado em `resultados/` |
| **Como o agente deve agir** | **aqui** |

**Ao mexer neste arquivo, pergunte:** isto diz a alguém *o que fazer*, ou
registra *o que aconteceu*? Se for a segunda, o lugar é outro.

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
4. **A fronteira não some quando o artefato some** (acrescentada em
   2026-08-25). Antes, `responder_prospectiva_se_couber` devolvia `None` se o
   panorama ou o painel faltassem, e `None` significa "siga o fluxo normal" —
   a pergunta prospectiva ia para o LLM. Camada acessória ausente virava
   permissão. Agora artefato ausente degrada a **riqueza** da resposta
   (`recusa_de_ultimo_recurso`, sem número nenhum, para não trocar violação de
   RN07 por violação de RN02), nunca a fronteira. E há **portão duplo**: a
   mesma verificação roda dentro de `responder_pergunta_livre` **e de
   `responder_com_guardrails`** (que se declara "o caminho interativo
   inteiro" e era o único portão do produto sem ela), antes de recuperar e
   antes de estimar custo, pela razão que já vale para a RN05 — um chamador
   futuro não pode contornar a regra esquecendo de varrer antes.
   `TestGuardaProfunda` trava as três coisas, inclusive a **ordem**: recusar
   depois de gastar não é recusar.

   **O que esta trava NÃO fecha, e continua aberto:** ela cobre o ramo
   "artefato ausente / entidade não resolvida". Não amplia o *detector*, que
   segue sem casar paráfrases como "qual o outlook de resultado do BB?" ou
   "o resultado do Bradesco tende a piorar?". A lacuna é anterior a esta onda
   e está registrada em `resultados/robustez_modelo_2026-08-24.md` (item 6);
   fechá-la exige conjunto adversarial de prospectivas parafraseadas, que não
   existe. Não leia "a fronteira não some" como "toda pergunta prospectiva é
   detectada".

**Falso bloqueio medido:** o detector de pergunta prospectiva dispara **0 vezes
nas 55 perguntas congeladas** (`TestFalsoBloqueio`), mesma disciplina da
etapa 14.

**Ressalva técnica que a permissão legal não remove:** para os cinco bancos do
corpus, todos na faixa de ativo onde o prejuízo ocorre em 0,6% dos trimestres,
o escore sai quase constante e quase zero. Autorização não torna um número não
informativo em útil. O valor real do módulo está nas companhias **hoje
lucrativas** (lift 4,35), não nos cinco do corpus.

> **Correção (2026-08-26).** Esta frase citava "instituição financeira de porte
> médio, AUC 0,832 abaixo de R$ 100 bi". É o recorte `is_banco` **retratado**
> em 2026-08-25 — 42 dos 49 eventos vinham de entidades que não são banco, e o
> universo limpo tem 7 positivos contra o mínimo de 20 do próprio módulo. O
> número sobreviveu aqui depois de ter sido riscado no relatório e marcado em
> `robustez.json`; removido agora. Reproduzível por
> `scripts/auditar_recorte_is_banco.py`. **O recorte de hoje-lucrativas NÃO é
> afetado** — ele não depende de setor.

### 3.7 Candidatos de ML avaliados e barrados — índice

**Onze candidatos foram pré-registrados, medidos e barrados antes de qualquer
treino. Nenhum modelo de Value Investing foi carregado até hoje.** Esta seção
era, até 2026-09-11, a narrativa completa de cada um — 633 linhas, 45% deste
arquivo. Isso é **registro de medição, não regra de conduta**, e o §10 manda o
contrário: AGENTS.md é o plano, o que foi medido vive em `resultados/`.

O texto integral foi consolidado em
[`resultados/becos_sem_saida.md`](resultados/becos_sem_saida.md) — **nada foi
apagado**. As regras duráveis que essas medições produziram estão no **§4.4**,
que é onde um agente deve procurá-las.

#### Redirecionamento — onde foi parar cada seção antiga

Comentários de código, testes e relatórios datados citam estas seções pelo
número. **As citações continuam válidas; use esta tabela para resolvê-las.** Os
relatórios em `resultados/` não foram reescritos, de propósito: o que foi
publicado numa data fica como foi publicado.

| Citação antiga | O que quem cita normalmente quer | Onde está agora |
|---|---|---|
| **§3.7** | O protocolo T1/T2 e seus limiares | **§4.4** |
| **§3.8** | "Denominador não é rótulo"; "baseline trivial antes do modelo"; o negativo medido | **§4.4** (regras 2 e 3) · becos §E |
| **§3.11** | "B0 abstém da direção, publicar cobertura junto do acerto"; "linha achada pelo residual não se remove" | **§4.4** (regra 9) · becos §F |
| **§3.14** | "Guarda que aprova por ausência de dado é pior que guarda nenhuma"; "alvo-variação fabrica o nível" | **§4.4** (regras 1 e 4) |
| **§3.16** | "`amplitude = max−min` sobre quintis é enviesada para cima" | **§4.4** (armadilhas de medição) |
| **§3.17** | "Fechamento aritmético ≠ conformidade contratual" | **§4.4** (regra 6) · becos §C-bis |
| **§3.9 · §3.10 · §3.12** | Unidades aninhadas não são réplicas; o veredito de cada candidato | **§4.4** (regra 8) · becos §F |
| **§2** ("Estado atual do repositório") | Suíte, gates, o que está implementado | **`MEMORY.md`** |

**Duas categorias, e confundi-las é o erro mais caro do registro:**

| | Significa | Reabre com |
|---|---|---|
| **REJEITADO** | Há um número que reprovou a ideia | Erro computacional, ou **outro estimando** com pré-registro próprio |
| **INDECIDÍVEL** | **Não há número.** Falta gold, amostra ou vintage para decidir | **Gold anotado**, nunca modelo novo |

| Candidato | Veredito | Onde está o detalhe |
|---|---|---|
| **C1** — queda de ROA normalizada pela volatilidade *(era §3.7)* | ❌ **REJEITADO** em T1: o próprio `sd8` que define o corte fabrica o baseline (amplitude 0,180–0,247) | becos §A.1 · [validação](resultados/validacao_c1_2026-08-26.md) |
| **Busca livre por um ML útil ao Value Investing** *(era §3.8)* | ❌ **NEGATIVO medido.** Seis candidatos, cada um vencido pelo próprio baseline trivial; os dois especialistas **retiraram as próprias propostas** | becos §E · [debate](resultados/debate_modelo_util_2026-08-26.md) |
| **CAND-02** — redline semântico *(era §3.9)* | ⛔ **INDECIDÍVEL** — estrutura passou, faltam as três evidências humanas. **Piloto com rótulo de IA (CAND-02-P) fechado INDECIDÍVEL em 07/10:** o M vence o B1 contra o rótulo do Claude, mas o rótulo não passou na conferência humana (α ≈ 0,65 < 0,67, três vezes) | becos §F · [validação](resultados/validacao_cand02_redline_2026-08-27.md) |
| **CAND-03** — triagem de anomalias contábeis *(era §3.10)* | ⛔ **INDECIDÍVEL** — 5,55 M de linhas não são rótulos | becos §F · [validação](resultados/validacao_cand03_anomalias_contabeis_2026-08-27.md) |
| **CAND-04** — previsão de fundamentos *(era §3.11)* | ❌ **Rodada A INVALIDADA** (23 linhas de escala explicam 61,64% do erro); a **fórmula econômica não foi refutada** | becos §F · [validação](resultados/validacao_cand04_previsao_fundamentos_2026-08-27.md) |
| **Rank 5** — divergência gerencial × contábil *(era §3.12)* | ⛔ **INDECIDÍVEL** — LAJIDA/LAJIR em 0/20 releases; só K1 determinístico + gold autorizados | becos §F · [validação](resultados/validacao_rank05_divergencia_gerencial_contabil_2026-08-27.md) |
| **Rank 3** — deterioração de conversão de caixa *(era §3.14)* | ❌ **REJEITADO** em T1 antes do treino (`accrual` 0,266, `conversao` 0,229) | becos §A.1 · [validação](resultados/validacao_rank03_conversao_caixa_2026-08-27.md) |
| **Etapa 19** — FCF yield × retorno futuro *(era §3.16)* | ⚠️ **INDECIDÍVEL.** T1 não reprovou pela primeira vez — mas 32% de chance de a amplitude verdadeira exceder o limiar | becos §F · [validação](resultados/validacao_etapa19_fcf_yield_2026-09-08.md) |
| **B-DFC-01J-M** — custo de captação um trimestre à frente *(era §3.17)* | ❌ **NÃO AUTORIZA**, decisivo em G0. Ver o aviso abaixo | becos §C-bis · [prontidão](resultados/prontidao_b_dfc_01j_modelo_2026-09-09.md) |
| **Rank 3-B** — início de consumo operacional persistente | ❌ **REJEITADO em 28/09, antes do treino.** O pré-registro v2 foi congelado (`8fdbd145…`) e medido no painel v2, com G0, G0.5 e G1 aprovados (95 saltos). **T2: lacuna 0,207** (IC 0,167–0,250). **T1: 0,1555** por `trimestres_com_fco_negativo_nos_ultimos_8`. Os triviais dizem **quem** vive perto de zero, não **quando** o consumo começa. A previsão acertou o veredito e errou o componente. Até 27/09 o alvo esteve bloqueado em G0 por escala, e o instrumento levou várias ondas de correção; o histórico está em becos §A.5 e nos relatórios ao lado. O defeito de painel do aviso abaixo continua no painel compartilhado | [medição](resultados/medicao_rank03b_v2_2026-09-28.md) · becos §A.1 · becos §A.5 · [validação](resultados/validacao_rank03b_consumo_operacional_2026-09-11.md) · [revisão](resultados/revisao_rank03b_consumo_operacional_2026-09-12.md) · [correções](resultados/implementacao_r1_r5_rank03b_2026-09-12.md) · [dossiê das quatro ondas](resultados/dossie_revisao_quatro_ondas_2026-09-14.md) · [conferência de 15/09, aprovação parcial](resultados/conferencia_quatro_ondas_2026-09-15.md) · [correções QW1–QW8](resultados/implementacao_qw1_qw8_2026-09-15.md) · [conferência QW1–QW8](resultados/conferencia_independente_qw1_qw8_2026-09-15.md) · [contratos CQW](resultados/contratos_correcao_cqw_2026-09-16.md) · [lote B](resultados/viabilidade_dados_rank03b_lote_b_2026-09-16.md) · [lote C, painel de pesquisa](resultados/painel_pesquisa_rank03b_lote_c_2026-09-16.md) · [pré-registro v2, rascunho](resultados/pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md) · [conferência de 17/09](resultados/conferencia_pre_treino_rank03b_2026-09-17.md) · [correções RF-01..RF-08](resultados/correcao_rf01_rf08_rank03b_2026-09-17.md) · [correções CRF](resultados/correcao_crf01_crf03_rank03b_2026-09-18.md) · [GEOM-1](resultados/escala_geometrica_rank03b_2026-09-18.md) · [alcance GEOM-1 e revisão](resultados/alcance_geom1_rank03b_2026-09-24.md) · [contratos até a medição](resultados/contratos_caminho_medicao_rank03b_2026-09-27.md) · [revisão até o treino](resultados/revisao_caminho_ate_treino_rank03b_2026-09-27.md) |

> **⚠️ B-DFC-01J é o único candidato com trabalho em voo, e o estado dele não
> cabe numa linha de tabela.** O instrumento de medição passou por **três ondas
> de correção** depois do veredito, cada uma achada por revisão independente da
> anterior: [F1 e mais cinco defeitos](resultados/correcao_instrumento_b_dfc_01j_2026-09-10.md)
> · [C1–C6](resultados/implementacao_c1_c6_b_dfc_01j_2026-09-11.md)
> · [R-C5/R-C6/R-SUPORTE](resultados/implementacao_rc5_rc6_b_dfc_01j_2026-09-11.md).
> **Estado vigente:** J identificado em **0** dos 25 pacotes, população elegível
> **zero**, G0 reprovado, nenhum modelo treinado. **F3 — o redesenho do cálculo
> de poder — segue sem correção**, em quarentena que hoje veta a aprovação de
> G3. Falta conferência independente da terceira onda. Onde a execução parou:
> `MEMORY.md`.
>
> **Não citar como conclusão atual:** "G0 resolvido", "o rótulo é mais ruidoso
> que o sinal", "~16 emissores", "J limpo não existe". Os quatro foram
> retratados; becos §C-bis tem a tabela afirmação-por-afirmação.

> **⚠️ DEFEITO DE PAINEL ABERTO — vale para qualquer análise, não só para o
> Rank 3-B.** A rodada de 2026-09-11 achou **transições de escala suspeitas em
> ~43 companhias**: a `escala` declarada alterna entre `MIL` e `UNIDADE`
> enquanto o `vl_conta` segue contínuo — o ITR passa a declarar `UNIDADE`, a DFP
> continua em `MIL`, e o painel aplica os dois fielmente, errando por 1.000×. No
> painel inteiro são **137 transições: 123 com bruto contínuo, 13 de
> redenominação aparentemente real e 1 indefinida**; no universo do candidato e
> só entre trimestres adjacentes, **132/119/12/1 em 41 companhias**.
>
> **Ler como transições SUSPEITAS, não como células já adjudicadas** (correção
> de 12/09): entrada e saída de uma única célula produzem dois sinais, e
> continuidade do bruto é suspeita, não prova de qual valor corrigir. É a mesma
> classe do defeito do CAND-04, achada de forma independente, em outra conta.
>
> Mediu também **25 linhas de FCO marcadas `trimestral`**: 16 períodos curtos
> (12, 31, 38, 41 dias) e nove semestres de 183 dias produzidos pela derivação.
> E **15 grupos (companhia, trimestre) com uma linha válida e uma anômala** —
> que contêm os períodos **curtos**, não os semestres, e em **12 deles** o
> `max(valor_reais)` da carga elege mesmo o curto. **Corrigir a derivação
> semestral não resolve esses 15.**
>
> **Parcialmente corrigido em 2026-09-12.** A **derivação** que produzia o
> semestre rotulado trimestre foi consertada no código
> (`_derivar_trimestres_intermediarios`, banda de 80–100 dias, recusa contada e
> avisada): eram **7.734 linhas** em 513 companhias (dizia 507, que é só o grupo
> de 183 dias — corrigido em 15/09) e 111 contas no painel
> inteiro — 1,1% dos derivados —, não as nove do recorte do Rank 3-B.
> **Mas o `cvm_treino.duckdb` em disco ainda as carrega:** aplicar a correção
> exige reconstruir o painel, o que quebra o hash (§3.13) e alcança a etapa 10.
> Essa reconstrução é decisão própria e **não foi tomada**.
>
> As **transições de escala** ganharam inventário com evidência em 12/09, e
> nenhuma correção: a segunda declaração que permite adjudicar é o comparativo
> `ORDEM_EXERC = 'PENÚLTIMO'`, que a carga descarta e que por isso nunca
> aparecera. Varridos 26,3 M de linhas: **34.952 casos conflitantes em 51
> companhias**, dos quais **10.261 adjudicáveis** pela DFP anual auditada.
> **Das 10.261, 7.648 apontam para `MIL` e 2.613 para `UNIDADE`** — corrigir em
> bloco numa direção só estragaria 2.613. O desempate é a DFP, que declara
> períodos **anuais**: por isso quase todo adjudicável é de balanço, e DRE/DFC
> trimestral fica indecidível por não ter instância auditada do mesmo período.
>
> **Medido em seguida, e corrige a leitura acima:** aplicar essas adjudicações
> corrigiria **zero linhas do painel** — o erro está sempre no comparativo
> `PENÚLTIMO`, que a carga já descarta. O que chega ao painel é a declaração
> `ÚLTIMO` de **meio de ano**, que nenhum segundo documento declara. O
> inventário serve para **identificar os 127 documentos defeituosos** (33.655
> linhas), não para corrigi-los: falta distinguir conta monetária de não
> monetária, senão a correção multiplica o **Lucro por Ação** por 1.000. É a
> mesma lacuna do `mapa_contas` (4,95%), e o destravador é a tabela de 208
> contas do plano padrão.
> Os **períodos curtos** seguem sem conserto.
>
> **Conferido em 2026-09-15, e corrige números acima**
> ([conferência](resultados/conferencia_quatro_ondas_2026-09-15.md),
> [correção](resultados/implementacao_qw1_qw8_2026-09-15.md)). **Não citar
> 10.261 adjudicações nem "127 documentos defeituosos (33.655 linhas)":** 6.736
> casos só tinham **zero** como prova, e 292 declarações eram condenadas por
> extrapolação. Pela regra **por declaração** (inventário v2): **3.401 casos,
> 6.456 declarações, 111 documentos em 35 companhias**, todas `PENÚLTIMO`, só
> balanço. A recusa da derivação era contada com **outra identidade** que a
> inserção (4.486 contra 7.733 simulados) e o aviso nunca fora testado no
> carregador; agora há estado próprio para **antecedente inexistente**
> (139.435 grupos). **Antes de qualquer reconstrução de painel:** a derivação
> escolhe ao acaso em **141 grupos de 7 companhias** onde a troca de exercício
> social põe dois períodos sob o mesmo rótulo — reconstruir hoje não é
> reproduzível.
>
> **Conferido de novo em 2026-09-16, e acrescenta um achado de gate**
> ([conferência](resultados/conferencia_independente_qw1_qw8_2026-09-15.md),
> [pendências até o treino](resultados/pendencias_desbloqueio_treino_dfc_2026-09-15.md),
> [contratos CQW](resultados/contratos_correcao_cqw_2026-09-16.md)). Os números
> de escala e derivação acima **sobrevivem**. Mudam três coisas: **não citar
> "154.160 declarações"** — são **156.100** (as contagens por estado publicadas
> junto sempre estiveram certas e somam isso); o consumidor do inventário
> aceitava **estado de adjudicação inválido** como "não adjudica" e agora
> levanta; e a linhagem do ativo cumpria dois dos quatro campos exigidos.
> **O mais sério é de gate: `G0.4` — `valor_reais` nunca nulo nas contas
> usadas — está congelada no §4 do pré-registro desde 11/09 e NUNCA foi
> implementada**, nem como contador nem como campo do artefato; e os três
> carregadores filtram `IS NOT NULL`, então ela seria vazia por construção.
> Implementada agora, medindo fora do filtro: **zero nulos** em FCO `6.01`
> (22.034 linhas) e Ativo `1` (22.471) — **não muda veredito nenhum**, muda a
> guarda deixar de aprovar por ausência de medição. `gate_g0([], [], [])`
> também aprovava. **Isto não desbloqueia nada:** G0 segue reprovando pelos
> mesmos 132 saltos de escala, fração 0,005874 contra limiar 0,005.
>
> **Painel de pesquisa do Rank 3-B, 2026-09-16** ([lote C](resultados/painel_pesquisa_rank03b_lote_c_2026-09-16.md)).
> A escala foi **adjudicada com fonte** fora do painel compartilhado: o
> cabeçalho de milhares das notas explicativas **e** os números do formulário
> impressos nelas. **101 correções `UNIDADE → MIL` em 32 companhias**; G0.3 no
> painel de pesquisa cai de 132 para **47 saltos (0,2092%)** *(números de 16/09,
> substituídos em 17/09 — ver abaixo)*. Duas regras para
> quem mexer em escala: **"em reais" declara a moeda, não a escala** (aparece no
> parágrafo de moeda funcional e em rodapés por ação), e o `CodigoEscalaMoeda`
> do formulário é a **origem** do rótulo, não prova. **O painel compartilhado
> não foi corrigido** e continua com o defeito.
>
> **Regra de cegueira ao desfecho que saiu da auditoria (16/09):** antes de o
> pré-registro estar congelado, **contagem estrutural não monta rótulo**. O
> G1 do auditor calculava `y` em memória só para contar observações, e o
> relatório de uma onda de correção (15/09) publicou a taxa do evento "para
> medir o efeito da correção". Os dois passaram por revisão sem serem vistos
> como vazamento. Quem medir efeito de correção publica **contagem de
> observações**, nunca taxa, `y` alterado ou descarte por feature do alvo; e
> quem montar amostra para gate usa `construir_amostra(..., calcular_rotulo=False)`.
>
> **Duas regras da conferência de 17/09**
> ([correções](resultados/correcao_rf01_rf08_rank03b_2026-09-17.md)): (1) um
> número só prova escala **localizado** — mesma conta (rótulo na linha),
> período corrente, perímetro consolidado, página que declara a unidade.
> Magnitude casada em texto corrido já "provou" `MIL` com uma quantidade de
> ações (ESC-0101, erro de 1.000×). (2) **Correção também é informação com
> data:** um valor corrigido só está disponível quando **todas** as provas da
> correção foram publicadas (numa herança, as duas pontas), e o G1 confere isso
> pelo manifesto, não pela data do construtor. Na **execução 3 de 17/09,
> histórica e substituída**, eram 68 correções em 26 companhias e G0.3 = 68
> saltos (0,3026%). O estado vigente está em `MEMORY.md` e nas
> [correções CRF](resultados/correcao_crf01_crf03_rank03b_2026-09-18.md).
>
> **Regra da revisão do alcance GEOM-1 (24/09)**
> ([ressalva](resultados/alcance_geom1_rank03b_2026-09-24.md)): o G0.3 só vê
> o ativo, e o G0.5 proposto lê o veredito por documento. Correção que alcance
> uma conta e não a outra do mesmo documento tira o sinal do único detector de
> escala, enquanto o FCO — de onde sai o rótulo, por diferença de acumulados —
> continua na escala declarada. **Não fazer sem antes tornar G0.3 e G0.5 por
> conta.** E, antes disso, o consumidor tem de recusar coluna desconhecida no
> manifesto, antes de qualquer aplicação. Cabeçalho deve ser completo e sem
> extras ou duplicatas, inclusive em CSV sem linhas; uma linha "por conta"
> não pode ser aplicada ao documento inteiro. Se uma prova de saldo autoriza corrigir o FCO
> do mesmo documento foi **decidido em 26/09, por delegação do responsável:
> não** (opção B do §12-bis do rascunho v2). Correção que altera o FCO exige
> prova que alcance o FCO, e cada conta se prova pela própria célula. Correção
> só do ativo exige, antes, manifesto e gates por conta; e `fco_ttm_sobre_ativo`
> fica ausente, com ou sem correção, onde as escalas aplicadas ao ativo e ao
> FCO divergirem e um dos dois lados não tiver veredito para a própria conta
> ([registro](resultados/registro_decisoes_v2_rank03b_2026-09-26.md)).
>
> Nenhuma linha foi removida. Conserto exige
> adjudicar contra a fonte pelo padrão do §3.3 (`correcoes_contabeis.csv`, com
> procedência e guarda anti-porta-dos-fundos). Enquanto isso não for feito,
> **qualquer número derivado de `valor_reais` herda o defeito** — inclusive, em
> princípio, os da etapa 10.

**Antes de propor candidato novo, leia `resultados/becos_sem_saida.md` inteiro.**
A coluna "o que reabriria" existe para que o registro não vire dogma: nenhuma
linha é permanente, todas são condicionais ao dado e ao alvo da data.

### 3.13 Fluxo de caixa e point-in-time carregados (2026-08-27)

O carregador lia **três** demonstrativos e ignorava o resto do ZIP. Passou a
ler **cinco**, e a tabela `documentos` entrou com `DT_RECEB`. Custo zero — os
31 ZIPs já estavam em disco e pinados por SHA-256. Relatório completo:
`resultados/carga_dfc_e_point_in_time_2026-08-27.md`.

**Não é modelo.** É o primeiro dos três destravadores que o §3.8 declara como
condição de reabertura (*"DFC, preços point-in-time, ou documentos além dos
20"*), e o CAND-03 já havia diagnosticado: os ZIPs sempre tiveram DFC e
`DT_RECEB`; o bloqueio era do loader.

| | Antes | Depois |
|---|---:|---:|
| Linhas em `fatos_contabeis` | 5.552.787 | **6.787.589** |
| Demonstrativos | 3 | **5** (+ `DFC_MD`, `DFC_MI`) |
| Documentos com `DT_RECEB` | 0 | **48.123** |

**FCO (`6.01`) existe para as 741 companhias.** Atraso mediano entre fim do
exercício e recebimento: **44 dias no ITR, 83 na DFP**; **19.674 documentos
(41%) chegam depois de 45 dias**. Usar `dt_refer` como data de publicação —
que era o que se fazia — enxerga o formulário antes de ele existir.

**Três invariantes que quem mexer na carga precisa preservar:**

1. **A derivação do 4T (RN10) é governada por `DEMONSTRATIVOS_DE_FLUXO`**, não
   por literal `= 'DRE'`. Fluxo de caixa acumula dentro do exercício e também
   não existe como ITR no 4T. Balanço **nunca** é derivado — há contraprova.
2. **`documentos` guarda TODAS as versões**, ao contrário de
   `fatos_contabeis`, que mantém só a maior. Sem a série completa não se
   responde "o que se sabia em D?" — inclusive que a versão vigente naquela
   data foi depois substituída.
3. **Cabeçalho sem `DT_RECEB` faz a carga FALHAR.** Painel que se diz
   point-in-time e não é seria pior que nenhum: o defeito ficaria invisível
   dentro de todo backtest construído em cima.

**Duas armadilhas novas, tratadas e não supostas:** a sobreposição `DFC_MD` ×
`DFC_MI` **não é vazia** (5 companhia–trimestres; somar os dois duplica o
caixa — o número é reportado em `avisos`); e 4 linhas de 2014 têm `DS_CONTA`
vazio na origem (conta livre não nomeada, valor 0,0) — entram com marcador
explícito e, por não casarem com `mapa_contas`, nunca resolvem conceito (RN09).

**Quebra de hash declarada,** como o C1 exige: o painel de treino saiu de
`74aa28e8…` para `476a11da…`. O hash anterior conferiu antes da troca. A
rejeição do C1 **não muda** — ela vem do vínculo mecânico entre `sd8` e o
rótulo, que independe de haver fluxo de caixa. `artefatos/cvm.duckdb`
(consultável) não foi tocado, por §3.5.

**O que destrava:** cálculo de FCO/accrual real e auditoria das datas de
recebimento. **Correção de 2026-09-08:** isso não certifica backtest
point-in-time. `fatos_contabeis` retém só a maior versão e os derivados não
guardam a linhagem de todos os operandos. A frase anterior "qualquer candidato
pode ser avaliado point-in-time de verdade" excedia a implementação.
Reconstruir vintages e selecionar operandos disponíveis em D antes da
aritmética é necessário; nem os CSVs brutos preservam necessariamente todas
as versões. Evidência e reprodução:
`resultados/viabilidade_ml_dfc_2026-09-08.md` §2. T1/T2 continuam obrigatórios.

### 3.15 Três corpora, não um — separação por contrato (2026-09-08)

O repositório passou a ter **três** corpora com manifesto e cache de OCR
próprios. A separação não é organização de pastas: é o que impede material de
teste de entrar no contrato do produto.

| Corpus | Manifesto | Cache de OCR | Docs | Papel |
|---|---|---|---:|---|
| `principal` | `corpus/metadados.csv` | `corpus/ocr/` | 20 | o produto; identidade do índice (RNF09) |
| `expansao` | `corpus/expansao/manifesto_expansao.csv` | `corpus/expansao/ocr/` | 24 | material de teste (7 emissores novos) |
| `ifrs` | `corpus/ifrs/manifesto_ifrs.csv` | `corpus/ifrs/ocr_documento/` | 15 | demonstrações completas de BTG/BB/Santander |

**A regra veio de erro medido, não de projeto.** Os 7 emissores novos entraram
primeiro no `corpus/metadados.csv` e no cache `corpus/ocr/`, e isso quebrou
**três contratos congelados de uma vez**:

1. **`hash_cache_ocr` da RNF09** saiu de `83463136…` para `52edfba4…` — o
   índice publicável deixou de conferir contra o cache. Restaurado.
2. **`empresas(manifesto) == Config.bancos`**, verificada por
   `_validar_manifesto` em `scripts/baixar_corpus.py`.
3. **A auditoria congelada do Rank 5** (§3.12), que mede 20 documentos.

O `.gitignore` **já dizia essa regra** para o IFRS — *"Estes documentos nunca
entram em `corpus/metadados.csv`: isso mudaria a identidade do índice
(RNF09)"* — e ela agora está escrita também para a expansão. Enriquecer o
corpus de teste é barato; mudar o corpus do produto invalida a rodada
congelada e os números do README.

**O cache do IFRS é `ocr_documento/`, não `ocr/`, e isso é obrigatório.** Os
dois são endereçados pelo hash do PDF, mas `corpus/ifrs/ocr/` guarda um
**recorte** de 8 páginas em schema próprio que `scripts/ancora_ifrs.py` lê como
evidência do G4 **aprovado**. Gravar o documento inteiro em cima sobrescreveria
prova de gate com um arquivo de outro formato.

**Duas guardas que saíram daqui:**

- **"Arquivo existe" não é "documento processado".** `separar_pendentes` confere
  a contagem de páginas do cache contra o PDF. O cache de âncora do BTG 4T2025
  tem 8 de 71 páginas; a lógica antiga pularia o documento inteiro deixando 63
  páginas fora **sem sinal nenhum**. Schema não reconhecido é tratado como *não
  sei*, nunca como incompleto — senão uma mudança de formato viraria
  reprocessamento pago do corpus inteiro.
- **Documento ausente da saída do lote é falha.** A Batch API pode **omitir** a
  linha de um request que falhou, em vez de devolver erro. Aconteceu: 23 de 24
  gravaram, `falhos` saiu vazio e o script terminou com código 0. Documento
  sumindo do corpus sem sinal é pior que sumir com erro.

**Nota de leitura do OCR do IFRS:** o BTG 4T2025 tinha 63 de 71 páginas com
fonte sem mapa de caracteres (§3.3). A passagem em lote devolveu na pág. 13
`16.663.803 / 16.005.964 / 657.839` — os três valores da âncora estabelecida em
`resultados/ancora_btg_4T2025.md`. Validação independente da leitura, não
autoavaliação.

**O que isto NÃO faz:** nenhum dos 39 documentos novos é consultável. Eles não
estão no `corpus/metadados.csv`, não foram chunkados e não estão no índice.
Indexá-los muda o `hash_corpus`, o que invalida a rodada congelada e os números
publicados — é decisão explícita, nunca efeito lateral.

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

**O congelado é congelado.** `conjunto_padrao/perguntas.csv` tem 10 perguntas
`dev` + **45 `teste` congeladas em 2026-07-29**, e `corpus/metadados.csv` define
a identidade do índice (RNF09). Mexer em qualquer um dos dois invalida a rodada
publicada e os números do README — é decisão explícita, nunca efeito lateral de
outra tarefa. Nenhum número de `dev` vira resultado final.
`candidatas_teste.csv` permanece só como origem auditável da curadoria e **não é
carregado pelo pipeline**.

**Os quatro `requirements-*.txt` extras ficam fora do deploy enxuto por padrão**
(RNF12): `-local` (sentence-transformers), `-lora` (PyTorch/PEFT), `-modelo`
(scikit-learn da etapa 10, offline, fora do caminho interativo por RN07) e
`-guardrails` (Presidio + spaCy pt).

### 4.4 Regras de método — saíram de medição, valem para qualquer candidato novo

Cada regra aqui custou uma rodada inteira, e várias foram descobertas **duas
vezes** porque estavam enterradas na narrativa de um candidato específico em vez
de escritas como regra. Este é o lugar onde se procura antes de propor alvo,
gate ou contrato novo. A evidência de cada uma está em
`resultados/becos_sem_saida.md`.

#### O protocolo dos dois testes — obrigatório antes de qualquer treino

Todo alvo novo passa nos **dois ao mesmo tempo**. Falhar num é invisível pelo
teste do outro, e cada proposta inicial já reprovada falhou em exatamente um.

| Teste | Pergunta | Métrica | Limiar |
|---|---|---|---|
| **T1** | O alvo fabrica o próprio baseline? | maior amplitude da taxa de evento entre quintis de **cada componente que define mecanicamente o alvo** | **< 0,15** |
| **T2** | Há sinal temporal ou só ordenação de emissor? | lacuna (AUC agregada − intra-companhia) | **< 0,12** |

**T2 favorável nunca resgata T1 reprovado.** Se o alvo contém nível,
volatilidade, média setorial ou qualquer outro normalizador, **todos** entram na
auditoria T1 — testar só contra a coluna que *parece* o baseline é insuficiente,
e foi assim que o C1 passou numa primeira avaliação.

#### As nove regras

1. **Alvo definido como *variação* de grandeza que reverte à média fabrica o
   *nível* dela como baseline.** Medido três vezes com três roupas. Se o alvo é
   "X piora", o nível de X entra em T1 obrigatoriamente — a reversão à média é a
   hipótese nula certa e vence sozinha. Escapa só evento **materialmente
   definido** (falência, evento legal, reapresentação), nunca movimento de série
   contínua.
2. **Construa o baseline trivial ANTES do modelo.** Num dos casos a linha de
   base venceu **205 a 1** — e só descobre isso quem a constrói primeiro. O
   trivial já venceu **sete vezes** neste projeto.
3. **"Denominador não é rótulo."** Pegou dois especialistas no mesmo dia:
   186.701 células contadas como rótulo quando o usável era **222** (840×); e
   37.540 triplas quando existem **198** (190×). Antes de dizer "temos n",
   conte o que tem **rótulo**.
4. **Guarda que aprova por ausência de dado é pior que guarda nenhuma.** Com
   `n = 0` a amplitude saía `NaN`, e `NaN >= 0,15` é `False` — o auditor
   devolvia "T1 aprovado" sobre amostra vazia. Amostra insuficiente **levanta
   erro** (`ReprovaEmAberto`), nunca vira aprovação. Pelo mesmo motivo, escore
   constante não pode "passar" T2 por ter lacuna zero.
5. **Defeito de dado e amostra insuficiente são estados diferentes.** O segundo
   entra na cadeia como gate reprovado com motivo; o primeiro **derruba a
   execução** (`ErroDeUnidade`, que deliberadamente não herda de
   `ReprovaEmAberto`). Esconder defeito de dado atrás de veredito plausível de
   gate é pior que a execução falhar alto.
6. **Fechamento aritmético e conformidade contratual são estados diferentes.**
   Uma parcela que vem **credora** fecha a soma e ainda assim não é despesa por
   competência. "Demonstrada não conforme em algum trimestre" significa **não
   demonstrada conforme em nenhum**.
7. **Contrato que cria um campo de estado só está cumprido quando existe
   contraprova exercitando a DECISÃO governada por ele.** Asserção sobre o JSON
   publicado prova o produtor e não prova nada sobre o consumidor. Esta mesma
   classe de defeito — exigência que existe como texto e não participa da
   condição de aprovação — reapareceu **duas vezes dentro dos contratos escritos
   para corrigi-la**.
8. **Unidades aninhadas não são réplicas independentes.** Chunk, página,
   sentença e linha de tabela são aninhados; release é a unidade do workflow,
   episódio-raiz é a unidade de rótulo, **conta nunca é réplica**. Trimestres do
   mesmo emissor também não — o bootstrap agrupa por emissor.
9. **Linha descoberta pelo residual não pode ser removida para salvar o teste.**
   Adjudicar contra a fonte: corrigir erro de unidade com procedência, manter
   evento econômico real, congelar a quarentena **antes** de um teste novo.
   Sensibilidade pós-hoc nunca vira resultado primário.

#### Duas armadilhas de medição, registradas para não reincidir

- **`amplitude = max−min` sobre cinco quintis é estatística enviesada para
  cima.** Um observado chegou a cair **fora** do próprio IC95% pelo lado de
  baixo. Isso torna as reprovações com folga grande **mais** robustas, não
  menos — mas um T1 que passa **raspando** não deve ser lido como aprovação.
- **`recall@5` medido por página é sinal enganoso para julgar chunking** —
  contava como acerto o chunk órfão, que não conseguia responder. Para
  chunking, medir se **o valor** está no top-5, não se a página está.

#### Nunca enfraquecer uma asserção para fazer código passar

O teste é o contrato e o código se adapta a ele. Quando um contrato pré-registrado
exigir mudar um teste, a substituição é **declarada** — no docstring do caso e no
relatório da onda —, nunca silenciosa. `pytest` verde é pré-condição de qualquer
commit. Enquanto houver onda paralela em voo um vermelho transitório pode
aparecer no meio do caminho: ele é fechado antes do commit, nunca contornado
enfraquecendo o teste.

---

## 5. Gates bloqueantes — o que cada um protege

O **estado** de cada gate (passou, reprovou, quando) vive no `MEMORY.md`, com os
relatórios em `resultados/`. Aqui fica só o que o gate existe para impedir.

| Gate | O que verifica | Por que bloqueia |
|---|---|---|
| **G1** | Recurso Azure OpenAI disponível | Reservado ao pré-deploy; sem ele os créditos vão para hospedagem |
| **G2** | Cobertura da CVM suficiente para o rótulo T+1 | Sem rótulo não há etapa 10 |
| **G3** | Mistral OCR × `pdfplumber` num release, conferindo âncoras | Trocar o extrator sem medir é trocar um defeito conhecido por um desconhecido |
| **G4** | Lucro pelo mapa semântico bate com o release, **banco a banco, em todos os trimestres** | **É o gate com maior potencial de dano do projeto.** Ver abaixo |
| **L1** · **Gemini** | Inferência local sem API · duas chamadas ao ramo ativo | Provedor precisa ser verificado antes de virar ramo ativo |

**Por que o G4 para o pipeline.** O mesmo `cd_conta` designa contas diferentes
conforme o plano de contas: `3.09` é lucro líquido no Itaú, Santander e BTG, e
*resultado antes das participações* no BB e no Bradesco. Uma consulta ingênua
devolve **número plausível, não nulo e errado** para 2 dos 5 bancos — a falha
exata que o projeto existe para combater, dentro da própria base.

**Relatório de gate tem data de validade.** Os datados de 2026-07-15 são
históricos: o Gate L1 registra `prompt=v1` e o Gate Azure antecede o hardening
atual. Nenhum comprova o prompt ou os adaptadores de hoje até ser regenerado
explicitamente.

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
| 10 | **Modelo preditivo** — split temporal, baselines, métricas completas | `modelo-preditivo` | ✅ **2026-08-23**, e o único modelo treinado do projeto. Painel de treino próprio (2011–2026, §3.5), walk-forward de 47 folds. **Passou por quatro rodadas de revisão que retrataram três achados da primeira**, entre eles um recorte setorial contaminado (`is_banco`: 42 de 49 eventos não eram banco) e vazamento no trimestre de validação. **Números, manchete corrigida e retratações:** `MEMORY.md` e `resultados/` (`modelo_preditivo_2026-08-23.md`, `revisoes_modelo_2026-08-23.md`, `robustez_modelo_2026-08-24.md`, `debate_modelo_2026-08-25.md`). O que foi medido e **descartado** — SMOTE, ajuste de hiperparâmetros, recalibração, controle setorial — está em `becos_sem_saida.md` §A.2–A.4 |
| 11 | **Ferramentas + agentes** — `verificar_cobertura`, Investigador e Auditor com filtro de contexto **em código**, teste que falha se o rastro vazar, braços A/B/C, triagem de cobertura; projeções depois | `agentes-investigacao` | ⬜ |
| 12 | **Injeção de falha (RF25) e comparação dos três braços (RF26)** — registrar o veredito, inclusive se for "o determinístico basta" | `agentes-investigacao` + `observabilidade-avaliacao` | ⬜ |
| 13 | **Langfuse + DeepEval** — traces por etapa e matriz de concordância com a auditoria manual | `observabilidade-avaliacao` | 🔄 matriz de concordância **medida** em 2026-08-23 (0,867, `scripts/medir_juiz_groundedness.py`) · ✅ Langfuse **instrumentado** em 2026-10-19 (`src/observabilidade.py`: trace por consulta do chat e span por ferramenta de agente, RN06 na máscara do SDK, texto livre só com o Presidio ligado, benchmark fora do trace; auditado no mesmo dia, sem achado alto) · ⬜ traces reais no servidor (falta a chave) · ⬜ suíte DeepEval formal |
| 14 | **Guardrails** — ataques bloqueados × falso bloqueio medido nas 45 legítimas (meta 0) | `seguranca-guardrails` | ✅ **completa** em 2026-08-21 — base determinística, ligada ao caminho interativo, **Presidio e Llama Prompt Guard 2 (86M) integrados** — **20/20 ataques · 0/45 falso bloqueio de entrada · 0/855 de saída** (`resultados/guardrails.json`, com as duas camadas ML ligadas na contraprova); `src/seguranca.py`, `src/reconhecedores_br.py`, `src/reconhecedor_presidio.py`, `src/prompt_guard.py`, `conjunto_padrao/ataques.csv`, `responder_com_guardrails` em `src/agentes.py`, portão em `app_streamlit.py`, `requirements-guardrails.txt`, 87 testes · `presidio_habilitado`/`prompt_guard_habilitado` desligados por padrão (RNF12) — pesos do Prompt Guard 2 já baixados e pinados (`guardrails_modelo_injecao_revision`), `HF_TOKEN` só foi necessário no download, runtime usa `local_files_only` |
| 15 | **Interface Streamlit** — streaming, estado de sessão, painéis de evidência, etiqueta de derivado, estado de cobertura, veredito do Auditor | `interface-produto` | ✅ base cacheada + pergunta livre · ⬜ camadas novas |
| 16 | **Publicação** — Container Apps primário, teto/alerta no provedor, dois modos validados | `interface-produto` | ⬜ |
| 17 | **`DESAFIO_CBL.md`, README e resumo executivo** (metas × resultados) | `documentacao-projeto` | ✅ desafio e README · ⬜ resumo executivo |
| 18 | **(Opcional) LoRA** — roteador de entrada, com split por pergunta-base | — | ⬜ opcional |
| 20 | **Alvo de ML para Value Investing** (§3.7) — o candidato C1 (queda de lucratividade normalizada pela volatilidade da própria companhia) foi reavaliado com especialistas isolados e replicação independente. Reprovou T1 em todas as operacionalizações: amplitude **0,180–0,183** na sessão principal e **0,247** no agente; o baseline `-sd8` já obtém AUC **0,634** agregada e **0,709** intra-companhia. Qualquer piso de materialidade ou novo normalizador é **C2**, com pré-registro e T1/T2 próprios | sessão principal | ❌ **C1 rejeitado antes do treino** — `resultados/validacao_c1_2026-08-26.md` · `scripts/auditar_alvo_c1.py` |
| 21 | **CAND-02 — redline semântico de divulgações** (§3.9) — fila auditável de mudanças entre releases; unidade atômica, B0/B1 antes de ML, split sem PDF compartilhado e workflow humano medido | sessão principal | ⛔ **ML não implementar agora; utilidade determinística não medida** — 20 docs · 15 pares · 5 clusters finais; faltam dupla leitura, adjudicação e estudo de tempo. Piloto CAND-02-P (rótulo de IA, 64 pares) fechado INDECIDÍVEL em 07/10; reabre com gold de mais de um humano |
| 22 | **CAND-03 — triagem de anomalias contábeis** (§3.10) — E2 prospectivo ordena episódios por prioridade de leitura; release é unidade independente; shadow e gold antes de ML | sessão principal | ⛔ **ML não implementar agora; estado INDECIDÍVEL** — 5,55 M linhas não são rótulos; falta gold/tempo/painel point-in-time. Reabre com piloto shadow de 30–150 releases e ≥30 positivos |
| 23 | **CAND-04 — previsão interpretável de fundamentos** (§3.11) — prospective ROA T+1, baselines simples antes de ML, intervalos e workflow humano | sessão principal | ❌ **rodada A rejeitada/invalidada; ML INDECIDÍVEL e não implementar agora** — 23 linhas de escala explicam 61,64% do erro; G0/G1 falham. A2 versus lucro dos controladores é novo experimento |
| 24 | **Rank 5 — divergência gerencial × contábil** (§3.12) — fila de reconciliações gerenciais que merecem revisão, com L e K separados | sessão principal | ⛔ **ML não implementar agora; estado INDECIDÍVEL** — L=0/20; K1 observável em 20/20, mas faltam vintage, gold, amostra e workflow. Autorizado só determinístico + gold |
| 25 | **B-DFC-01J-M — custo de captação por competência, um trimestre à frente** (§3.7) — primeiro candidato sobre a série de J do piloto bancário, com alvo congelado em pré-registro antes de medir | sessão principal | ❌ **NÃO AUTORIZA, decisivo em G0** — e o instrumento de medição levou **três ondas de correção**, cada uma achada por revisão independente da anterior. Estado vigente: J identificado em **0** dos 25 pacotes, população elegível **zero**, nenhum modelo carregado. **F3 — o redesenho do cálculo de poder — segue sem correção**, em quarentena que veta G3. Falta conferência independente da terceira onda. Histórico das ondas e o que **não se pode mais citar** deste candidato: §3.7 e `becos_sem_saida.md` §C-bis. Onde parou: `MEMORY.md` |
| 19 | **Bônus — múltiplos de mercado (P/L, P/VPA)** — fora da spec 5.21, proposta em 2026-08-21 durante conversa sobre Value Investing. `precos_fechamento` no DuckDB (5 tickers, fonte pública), disciplina *point-in-time* obrigatória (preço da data do release, nunca o de hoje), múltiplo marcado como **derivado** pela RN10, medido em conjunto próprio — nunca nas 45 congeladas nem em E0–E4 | — | ⬜ **não iniciar antes das etapas 1–18 concluídas; G4 aprovado é pré-condição** |

**Transversal:** rodar `auditor-conformidade` (somente leitura) ao final de cada
onda de implementação, antes de considerar a etapa concluída.

**Regra de crescimento do gabarito: acrescente coluna, nunca linha.** O gargalo
declarado do projeto é o gabarito manual. Toda capacidade nova é avaliada
anotando mais sobre as mesmas 45 perguntas.

**Antes de propor ideia nova, consultar `resultados/becos_sem_saida.md`.** É o
registro consolidado do que já foi **medido e descartado** — alvos que reprovam
T1/T2, SMOTE, ajuste de hiperparâmetros, recalibração, fusão E3+E4, provedores
de LLM, e as quatro hipóteses de diagnóstico que foram retratadas. Cada linha
traz **o que reabriria** a questão, para que o registro não vire dogma: nenhuma
delas é permanente, todas são condicionais ao dado e ao alvo da data. Ao
reabrir e remedir, **atualize a linha** em vez de acrescentar outra — o
histórico é o Git.

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
│   ├── auditar_recorte_is_banco.py ✅ (torna a retratação de is_banco
│   │                                   reproduzível — veredito CALCULADO)
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
│   ├── prompt_guard.py ✅ · projecao.py ✅ · observabilidade.py ✅
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
├── resultados/                  (evidência dos gates + becos_sem_saida.md,
│                                 registro do que já foi medido e descartado)
├── app_streamlit.py             ✅
└── tests/  conftest · test_ingestao ✅ · test_normalizacao ✅ · test_regras ✅
         · test_dados_estruturados ✅ · test_seguranca ✅ · test_isolamento ✅
         · test_cobertura ✅ · test_guardrails_integracao ✅ · test_deepeval ⬜
         · test_observabilidade ✅ (Langfuse: estrutura, RN06, isolamento do OTel)
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
