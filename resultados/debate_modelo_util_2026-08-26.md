# Debate — modelo de ML funcional e útil (2026-08-26, em andamento)

> **ATUALIZAÇÃO POSTERIOR (validação concluída na virada de 26–27/08).**
> A premissa abaixo de que o alvo anterior estava aprovado foi retratada:
> o C1 reprovou T1 e foi rejeitado antes do treino
> (`resultados/validacao_c1_2026-08-26.md`). Os seis resultados negativos deste
> relatório permanecem válidos; somente a caracterização do C1 como alternativa
> aprovada deixou de valer.

**Estado: RODADA 1 EM EXECUÇÃO.** Este arquivo é o registro de retomada. Se a
sessão cair, ele diz o que já foi dito, o que já foi verificado e o que estava
pendente.

## Por que este debate existe

O debate anterior (`debate_alvo_ml_2026-08-26.md`) terminou em **"aprovado, não
implementado"**. O alvo aprovado é metodologicamente sólido e não é um produto:
Δ de +0,03 sobre a melhor coluna crua, limiar `k` escolhido *post-hoc*, e
nenhuma afirmação de retorno possível sem preços.

Pedido de Ygor: um modelo de ML **funcional e com utilidade real ao projeto** —
entrega acadêmica de verdade, não item de checklist. Implementável é requisito,
não bônus.

**Duas reprovações distintas, e o debate tem de escapar das duas.** Isto é a
regra central desta rodada:

| Reprovação | Como se manifesta |
|---|---|
| **Aprovado e não implementável** | O que aconteceu no debate anterior. Rigor metodológico sem entrega |
| **Implementável e irrelevante** | O risco novo, criado pela própria exigência de funcionar. O jeito mais seguro de entregar algo que roda é entregar algo trivial |

O alvo é **ferramenta de ouro para o analista que cobre bancos** — algo que
fortalece análise de Value Investing e muda o que a pessoa faz na segunda-feira
de manhã. "Roda sem erro" não é utilidade. "Tem AUC alto" não é utilidade.
Utilidade é **decisão que muda**.

## Protocolo desta rodada de debate

- **Dois especialistas independentes**, ambos com acesso à web: um cientista de
  dados e um analista de *equity research*.
- **Briefing deliberadamente mínimo.** Recebem o resumo funcional do projeto, os
  dados disponíveis e a barra de validação — e mais nada. Não recebem o AGENTS.md
  nem o histórico de decisões, para não ancorarem no que já existe.
- **Leitura obrigatória única:** `resultados/becos_sem_saida.md`, para não
  repetir medição já feita. Podem reabrir uma linha se a condição de reabertura
  declarada nela estiver satisfeita — dizendo por quê.
- **Toda afirmação com peso é verificada de forma independente** pela sessão
  principal antes de virar resultado. Número de agente não vira publicação sem
  replicação.
- **Quantas rodadas forem necessárias.** Cada uma é anexada a este arquivo
  assim que fecha.
- **Custo zero de API paga.** Os agentes rodam script local sobre o painel.

## Barra de validação passada aos dois

Alvo supervisionado tem de passar nos **dois testes ao mesmo tempo**
(protocolo herdado do debate anterior):

- **T1** — amplitude da taxa de evento entre quintis do baseline pretendido
  **< 0,15**. Impede que o alvo fabrique o próprio baseline.
- **T2** — lacuna (AUC agregada − AUC intra-companhia) **< 0,12**. Exige sinal
  temporal, não só ordenação de emissor.

Proposta que não seja classificação supervisionada precisa trazer a **barra
equivalente proposta pelo próprio autor**, justificada.

---

## Rodada 1 — analista de mercado: FECHADA E VERIFICADA

### O que ele foi buscar

A tese que um analista de bancos mais quereria ter: **antecipar a linha de custo
de crédito por baixo**, pelo balanço dos próprios tomadores. Construiu painel de
crédito corporativo (22.428 obs · 700 não-financeiras · 2011–2026) e rótulo
*point-in-time* de evento legal (RJ, recuperação extrajudicial, falência,
liquidação) a partir do `cad_cia_aberta.csv` — 47 eventos no painel.

**A tese morreu em quatro pontos, todos com número.**

### Negativo 1 — não existe *default surpresa* para prever

| | |
|---|---|
| Eventos que **nunca** pareceram saudáveis nos 8 trimestres anteriores | **31 de 32** |
| Mediana de trimestres com sinal vermelho antes do evento | **15** (≈ 4 anos) |
| Melhor **coluna crua** (`pl_ativo`), AUC OOS | **0,8765** |
| Modelo (logística / boosting) | 0,8514 / 0,8537 — **perde para a coluna** |
| Lacuna T2 | +0,247 / +0,163 — **reprova** |

Decil superior: 85,0% já em prejuízo TTM, 42,0% com PL negativo. É o formato
exato do beco do modelo antigo.

**Caso Americanas, medido:** juros implícitos entre os percentis **42 e 66** de
2018 a 2022; só estouram em 4T2022, *depois* do fato. O detector forense de
dívida oculta não dispara — pela razão certa: risco sacado estava fora da linha
de despesa financeira.

### Negativo 2 — o estresse agregado não lidera a inadimplência do sistema

Índice ponderado por dívida × série SGS 21083 do BCB, n = 59 trimestres:
ρ = **+0,687** em nível (p = 5e−09) e **+0,076 em primeira diferença** (p = 0,58).
A correlação era tendência comum. **Some inteira ao detrendar.**

### Negativo 3 — onde os dois testes passam, o ML perde para uma razão

No conjunto já estressado (ICR<1 ou PL<0) — a pauta do comitê de crédito,
estágio 2→3 da Res. CMN 4.966. T1 = 0,081 ✅.

| Escore | AUC | intra | lacuna | prec@5% |
|---|---|---|---|---|
| `liq_corrente` **cru** | 0,7935 | **0,7539** | **+0,040** ✅ | 0,1339 |
| Logística (27 features) | 0,8016 | 0,6481 | +0,154 ❌ | 0,1607 |
| Boosting | 0,7632 | 0,6922 | +0,071 ✅ | 0,0982 |

Ativo circulante ÷ passivo circulante domina os dois modelos em AUC intra e em
lacuna. A logística compra 2,7 pontos de precisão pagando com memorização de
emissor. **É a reprovação nº 2 do briefing medida, não temida.**

### Negativo 4 — o lado banco do painel não existe

**Verificado de forma independente pela sessão principal, e é pior do que ele
relatou.** Contagem própria sobre `fatos_contabeis` (5.552.787 linhas, 741
emissores):

| Conceito | Como conta no painel | No corpus de PDFs |
|---|---|---|
| Basileia / CET1 | **0 linhas, 0 emissores** | **20/20 documentos** |
| Margem financeira | **0 linhas, 0 emissores** | 17/20 |
| NPL / inadimplência | 94 linhas, **1 emissor** | 17/20 |
| Índice de eficiência | 63 linhas, **1 emissor** | **20/20** |
| Índice de cobertura | 194 linhas, 11 emissores (genérico) | **20/20** |
| Carteira de crédito | **1 linha, 1 emissor** | — |
| Despesa de PDD (`3.04.01`) | 367 linhas, 19 emissores | — |
| Custo do crédito | — | 16/20 |
| Res. 4.966 | — | 19/20 |

**Este é o achado estrutural da rodada.** A camada de ML vinha garimpando o
painel contábil, que é **estruturalmente cego** para tudo que move o preço de um
banco; e esses números existem, como texto não estruturado, **dentro do corpus
do próprio produto**. A contagem de KPIs no cache OCR foi refeita
independentemente (20 documentos, 21,0 M de caracteres) e replicou.

### Proposta A — extrator de KPI bancário com abstenção

*"Hoje o analista reabre 5 PDFs por trimestre e redigita à mão cobertura,
formação de inadimplência, custo do crédito, eficiência e CET1 numa planilha,
porque cada banco define e formata diferente e não existe fonte estruturada."*
Com isto: painel gerencial comparável dos 5 bancos, com citação de documento e
página, e etiqueta quando as definições divergem entre bancos.

Unidade de observação vira o **campo extraído** (≈ 5 bancos × 4 trimestres × 15
KPIs ≈ 300 campos sobre 2.790 páginas), não o emissor — o `n` minúsculo do lado
banco deixa de ser o gargalo.

**Barra proposta por ele, não AUC:** (i) exatidão do valor ≥ 0,90; (ii) **taxa
de abstenção correta ≥ 0,95** — declarar "não divulgado" quando o banco não
divulga, medida contra os 4/20 sem custo do crédito e os 12/20 sem NPL 15–90,
porque inventar KPI de banco é o pior erro possível e é o que a RN02 existe para
impedir; (iii) zero valor sem página-fonte.

### Fragilidade que ele mesmo declarou

**A proposta A tem número de viabilidade, não de desempenho.** Ele mediu que os
KPIs estão no corpus e que não estão na base estruturada; **não mediu exatidão
de extração**, porque o gabarito não existe. Trocou um problema medido e
reprovado por um não medido — e admite. Argumento dele: a diferença é de
natureza do risco (A pode falhar por execução; a família de crédito falhou por
**inexistência de sinal**, medida em quatro cortes).

Segundo ponto: o rótulo de evento é **truncado à esquerda** — `SIT_EMISSOR`
guarda só o estado atual, então empresa que entrou em RJ e saiu perde o rótulo.
Torna os negativos **conservadores**, não otimistas. O dataset IPE reabriria.

### Reabertura formal de linha do `becos_sem_saida.md`

Reabriu **A.2 — features do O-score de Ohlson**, cuja condição declarada era
"alvo de insolvência/falência de fato". Condição satisfeita: construiu o alvo de
evento legal. **Resultado: negativo. A linha deve ser fechada em definitivo.**

### Pendência crítica para a rodada 2 (levantada pela sessão principal)

Extração com abstenção **é uma tarefa de ML legítima**, mas a proposta precisa
declarar **qual é o componente aprendido**. Se a resposta for "chamamos o LLM
com um prompt", não é entrega de modelo — é engenharia de prompt, e reprova a
exigência acadêmica por outro caminho. Isto vai aos dois na rodada 2.

Scripts: `/tmp/debate_er/01..08_*.py`. Nenhum arquivo do repositório alterado.

## Rodada 1 — cientista de dados: FECHADA, COM DIVERGÊNCIA DE MAGNITUDE

### Proposta A — "selo de revisão": qual número citado não vai sobreviver

*"Hoje o analista cita o lucro do 3T, monta o comparativo anual no modelo, e
descobre meses depois — quando o comparativo do ano seguinte sai — que a base
estava errada."* Com isto, cada número que o assistente cita vem com
probabilidade de revisão, e ele confere só os marcados.

### O destravamento — dado que já estava em disco, descartado pelo carregador

Os CSVs em `corpus/cvm/` têm **`ORDEM_EXERC`**: `ÚLTIMO` (período corrente) e
`PENÚLTIMO` (o **mesmo** período republicado como comparativo no arquivo do ano
seguinte). O carregador do painel descartou a coluna.

**Verificado independentemente pela sessão principal:** a coluna existe e a
estrutura é a descrita. Pareamento próprio sobre a DRE consolidada de todos os
ZIPs:

| | agente | **replicação da sessão** |
|---|---|---|
| Pares linha-período | 1.060.269 | **1.060.295** |
| Companhias | 682 | **682** |
| Defasagem | 365 d em 99% | **mediana 365 d, 100% entre 300–430 d** |

### A reabertura de `becos_sem_saida.md` §A.5 é LEGÍTIMA

A linha "reapresentação como alvo" fora morta por **censura à direita** (taxa
caindo 28,1% → 4,3%), com reabertura condicionada ao dataset IPE. Ele **não usa
IPE e não precisa**: o comparativo chega com defasagem **fixa**, não quando a
empresa resolve corrigir. Só o último ano é censurado.

Taxa por ano do período, medição própria (|Δ|>1%, >R$ 1 mi):

| 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5,9% | 6,4% | 7,0% | 5,8% | 5,1% | 7,1% | 7,1% | 6,0% | 4,2% | 6,1% | 4,3% | 4,4% | 4,7% |

Amplitude 0,033 e **sem declínio nos anos recentes**. (2012 = 18,4%, adoção
plena do IFRS, não censura.) **A censura sumiu de verdade.**

### Números dele que a replicação NÃO reproduziu

| Métrica | agente | **replicação da sessão** |
|---|---|---|
| Taxa de revisão por linha | 10,3% | 6,6% (limiar diferente — não é contradição) |
| AUC global | 0,868 | **0,717** |
| AUC dentro da declaração | **0,847** | **0,692** |
| Top 20% captura | **75,6%** | **39,2%** |
| Lacuna (T2) | +0,030 ✅ | +0,025 ✅ |

**A conclusão qualitativa replica — a lacuna é pequena e T2 passa com folga em
ambas.** A magnitude não replica, e é ela que sustenta a utilidade: "conferir
20% dos números captura 75,6% das revisões" é uma proposta de produto; captura
39,2% é bem menos. A replicação é deliberadamente simples (6 features, só DRE),
então a diferença pode ser mérito das features dele — **ou vazamento na feature
de histórico**. O ônus é dele na rodada 2.

### T1 reprova, e ele pede para trocar o teste

Amplitude por quintil de porte = 0,263; tornando o alvo escala-livre, **0,211** —
continua reprovando. Argumento dele: na rodada anterior, tornar o alvo
escala-livre **colapsou** o baseline (0,599 → 0,491), provando artefato; aqui
não colapsa, logo o gradiente de porte é **fato** (companhia grande revisa mais
por ter mais controladas e mais reclassificação IFRS 5). Propõe **T1′**: *a
amplitude colapsa quando o alvo vira escala-livre?*

Argumento adicional, mais forte: **o modelo nunca compara companhias em
inferência** — ordena linhas dentro de um documento, onde porte e identidade
são constantes. Por isso a métrica publicável seria a AUC dentro da declaração.

Ele mesmo escreveu "ataquem este ponto". Vai ser atacado: trocar o critério
depois de reprovar nele é exatamente o padrão que o protocolo existe para
impedir, e o mérito do argumento não apaga o vício do momento em que foi feito.

### Negativo que ele mediu e publicou contra si

Declaração revisada **não** antecipa prejuízo: 17,83% (revisada) × 17,30% (não),
Δ +0,005, **p = 0,44**. É confiança no dado, **não sinal de investimento**.

### Proposta B — deriva de rebaixamento no IF.data do BCB: NEGATIVO

Baixou o IF.data (Olinda OData, gratuito): 43 trimestres, 289 conglomerados,
distribuição AA–H e perda mínima da Res. CMN 2682/1999. Hipótese: a deriva de
rebaixamento antecipa o custo do risco. **Falso** — R² within 0,0460 → 0,0495;
walk-forward **−0,043** (vence 7/21); colchão → reversão de ROE R² 0,0166 →
0,0002.

**Dois achados de dado que valem mais que a hipótese:**
1. **63,5% das observações têm provisão contábil abaixo do mínimo implícito
   pelos ratings** — porque o relatório 8 é base SCR e o 2 é COSIF. **Sistemas
   diferentes; o "colchão" assim construído não mede conservadorismo.**
2. **A Res. CMN 4.966 encerra a série AA–H em 2024T4** — o relatório 8 volta
   vazio a partir de 2025T1. Qualquer reuso do IF.data enfrenta a quebra.

### Fragilidade que ele mesmo declarou

O rótulo mistura **reapresentação genuína com reclassificação legítima** (IFRS 5,
mudança de segmento). Para o modelo do analista as duas quebram o comparativo
igualmente; para o julgamento sobre a companhia significam coisas **opostas**.
Separá-las exige ler a nota explicativa.

Scripts: `/tmp/debate_cd/02..10_*.py`. Repositório não alterado.

---

## Rodada 2 — pauta fixada pela sessão principal

1. **Ao cientista de dados:** explicar a divergência de magnitude contra a
   replicação (0,847 × 0,692; 75,6% × 39,2%), com o código exato do rótulo e
   das features de histórico, provando que não olham para o ano de teste.
2. **Ao cientista de dados:** defender T1′ da acusação de mover a trave depois
   de reprovar.
3. **Aos dois:** qual é o **componente aprendido** da extração de KPI? Se a
   resposta for "chamamos o LLM com um prompt", não é entrega de modelo.
4. **Ao analista:** o selo de revisão é ferramenta de ouro ou conveniência? E a
   resposta muda se a captura for 39% em vez de 75,6%?
5. **Aos dois:** o painel é cego para banco (verificado) e o corpus do produto é
   de 5 bancos. Isso condena modelagem sobre painel neste produto?
6. **Convergir em UMA entrega.** O pedido é um modelo funcional, não dois.

---

## Rodada 2 — analista de mercado: FECHADA E VERIFICADA

### Ele veta a própria proposta

**"O componente aprendido é nada."** Resposta direta à pergunta da pauta: o
extrator de KPI é prompt + gabarito curado + disciplina de abstenção. Rejeitou
os três candidatos que ofereci: classificador de abstenção (`n ≈ 300`, e um `if`
sobre "divulgou no trimestre anterior" resolve — é tabela, não ML);
desambiguador de definição (5 bancos); reconciliador gerencial × contábil (já
morto no `becos_sem_saida.md` A.5). Mantém que é o item de maior utilidade
prática do produto, **mas que é engenharia, não modelo, e não vai defendê-la
fingindo que é.**

### Terceira medição independente do selo: 38,3%

Replicou direto dos CSVs, sem passar pelo DuckDB: 1.085.886 pares, 657
companhias. Capture@20% = **0,3833**, lift **1,92**.

**Três medições independentes — 39,2% (sessão) · 38,3% (analista) · 75,6%
(autor) — convergindo duas a duas contra a terceira.** Ele aponta a causa
provável: `expanding().mean()` sem `shift(1)` inclui a própria linha.

### O número que muda a narrativa — verificado pela sessão

Os "18,4% de |Δ| mediano" e os "14,6% que invertem sinal" **não são da linha que
o analista usa**. Verificação própria na linha de lucro (3.09/3.11) dos 5 bancos:

| | sessão | analista |
|---|---|---|
| Pares | 307 | 153 |
| Taxa de revisão | **11,40%** (bate com o autor) | 13,73% |
| **\|Δ\| mediano entre as revisadas** | **4,14%** | 1,13% |
| Pares com \|Δ\| > 5% | **12 de 307** | 3 de 153 |
| **Inversões de sinal** | **ZERO** | **ZERO** |

A magnitude exata diverge entre nós dois, mas **a direção é a mesma e o ponto
sobrevive**: na linha de lucro de banco a revisão é frequente e pequena, e
**nunca inverte sinal**. Os 18,4% e os flips vêm de subconta profunda, onde uma
linha de R$ 3 mil vira R$ 5 mil — 67% aritméticos, zero econômicos.

### A favor dele: bancos revisam mais, e isso é real

Medição própria:

| | manchete (nível ≤2) | profunda |
|---|---|---|
| **5 bancos** | **12,29%** | **14,80%** |
| Demais 700+ | 7,81% | 8,51% |

### O veto de fato — e é o Negativo 4 voltando

*"O selo protege a base que eu menos uso na cobertura de bancos."* As séries que
ele reconstrói ano-contra-ano — margem financeira, custo do crédito, cobertura,
eficiência, CET1 — **não existem no painel** (0 linhas, 0 linhas, 11 emissores
genéricos, 1 emissor, 0 linhas). Vivem no release, são gerenciais, e são
reapresentadas num lugar que o `ORDEM_EXERC` não enxerga.

Para as 700 não-financeiras que o assistente cita e ninguém conferiu, o selo
protege exatamente a base certa. **É lá que ele é bom — e não é lá que mora o
Value Investing em banco.**

### O separador que ele mediu, e que não custa dado novo

Reclassificação × reapresentação quebram o comparativo igualmente mas significam
o oposto sobre a companhia. Separador: **quantas linhas da mesma declaração
revisaram juntas.**

| Tipo | % das declarações | % de todas as linhas revisadas |
|---|---|---|
| BLOCO (≥50% das linhas) | 2,20% | **14,5%** |
| PONTUAL (≤2 linhas) | 11,25% | 5,3% |
| Intermediário | 28,92% | **80,2%** |

Nos 5 bancos, BLOCO é **7,62% das declarações — 3,5× a média**, confirmando que
o 72% de Itaú e Bradesco é reorganização, não erro. A massa intermediária de
80% continua ambígua — limitação real, não resolvida.

### Recomendação: construir o modelo DELE, com três emendas

1. **Pontuar a LINHA, não a declaração.** "43%–72% das declarações" é inflado
   por uma declaração ter ~700 linhas.
2. **Publicar LIFT no orçamento, não capture** — e o competidor não é sorteio, é
   o hábito real: o analista já olha ~10 linhas de manchete em ~700, orçamento
   de 1,4%. O selo a 20% pede **14× mais trabalho**. Critério de retirada
   declarado antes: **lift < 2,5 → retira o selo.** Hoje está em **1,92**.
   **Pelo critério que ele mesmo propõe, o selo como está hoje NÃO passa** — e a
   auditoria de vazamento decide se o módulo existe.
3. **Selo de três classes** (`BLOCO`/`PONTUAL`/`INDETERMINADO`), materialidade
   condicional à classe, e nunca publicar "|Δ| 18,4%" sem dizer quais linhas.

### A conclusão dura da rodada

> **"Modelo de ML funcional" e "ferramenta de ouro para o analista de bancos"
> não são satisfazíveis pelo mesmo artefato com este dado.** O lado com `n`
> (1,08 M de pares, 657 companhias) não tem conteúdo bancário; o lado com
> conteúdo bancário (20 documentos, 21 M de caracteres) não tem `n`.

Não é falta de imaginação — está medido em quatro cortes. O selo entra como
**camada de confiança da citação**, na mesma gramática das etiquetas que já
existem (`derivado` da RN10, `corrigido` da tabela de correções), e **não** como
ferramenta de Value Investing. Vendido como Value Investing, repete a reprovação
nº 1 da rodada anterior com roupa nova.

---

## Rodada 2 — cientista de dados: RETRATAÇÃO INTEGRAL

### Havia vazamento, e valia +0,21 de AUC

O mecanismo é **pior** do que "expanding sobre o período inteiro", e é
específico deste problema: o rótulo de uma declaração publicada em D **só é
observável em D+365**, quando o comparativo sai. A feature
`groupby([CD_CVM, CD_CONTA])["rev"].shift(1)` é o rótulo da declaração de D−90,
que em D **ainda não existe**.

Reimplementado com `merge_asof` sobre `data − 365 dias`, sob o rótulo da sessão:

| | ingênuo (publicado) | **observável** |
|---|---|---|
| AUC global | 0,887 | **0,654** |
| AUC dentro da declaração | 0,857 | **0,650** |
| AUC intra-companhia | 0,849 | 0,563 |
| Lacuna T2 | +0,039 | +0,091 |
| Captura top-20% global | 0,774 | **0,342** |
| **Captura top-20% dentro da declaração** | 0,461 | **0,284** |

**Minha replicação (0,692 / 39,2%) também vazava** — menos, porque minhas taxas
históricas eram mais grossas (empresa×raiz) e as dele por empresa×conta exata,
que é onde o bloco de retificação mora. A do analista (38,3%) idem. **A verdade
é 0,284, abaixo das três.**

Registrou também que os 75,6% eram captura **global**, e a métrica que o produto
promete é a **dentro da declaração** — que já era 45,8% no regime ingênuo. Duas
inflações somadas.

### Ablação: não há feature que salve

Regime observável: completo 0,650 · **sem histórico da companhia 0,664**
(melhora) · sem histórico da linha 0,622 · só estruturais 0,622. **Não existe o
salto para 0,847 a ser explicado — ele era o vazamento.**

### T1′ — a contraprova reprovou o próprio autor

Ele declarou `BARRA_FALSIFICACAO = 0.40` **dentro do script, antes de rodar**:
*abandono a proposta A se a captura no top-20% dentro da declaração não atingir
o dobro do acaso no regime observável.* **Medido: 0,284. Proposta A abandonada.**

É a resposta à acusação de mover a trave: T1′ não era critério mais frouxo, era
critério que **podia matá-lo, e matou**.

### O resíduo honesto e não-ML

`P(linha revisada | mesma linha revisada no trimestre anterior) = **0,6895**`
contra `0,0282` — **24,5×** (n = 712.034). Reapresentação é feita **em bloco**:
retificar FY2020 muda os quatro trimestres de uma vez. Por isso o rótulo vizinho
era quase o próprio rótulo. Vira **consulta, não modelo** — quando o comparativo
de um período chega diferente, os irmãos já estão condenados a ~69%.

### O veredito dele sobre a cegueira do painel

Mais forte que o do analista, e por evidência própria: **a proposta B era
exatamente a tentativa de curar a cegueira por fonte externa.** O IF.data do BCB
tem Basileia, carteira, PDD e distribuição AA–H para todo banco brasileiro,
trimestralmente, de graça. **A disponibilidade foi resolvida; o sinal não.**

> Leitura correta: não é "o painel é cego, importe os KPIs e modele". É
> **"importei os KPIs de um regulador e a estrutura preditiva continuou não
> existindo"**. A restrição que morde não é falta de variável — é ausência de
> sinal antecipatório em dado contábil trimestral agregado.

---

## CONVERGÊNCIA — os dois recomendam a mesma entrega

**Extrator de KPI sobre o corpus, com a CAMADA DE ABSTENÇÃO como o componente
de ML aprendido** (*selective prediction*). O extrator vira **gerador de
features**; o modelo é o classificador calibrado que decide **responder ou se
abster**.

Por que isso é ML de verdade e não prompt:

- **Objetivo próprio e não trivial:** minimizar risco seletivo, avaliado por
  curva risco–cobertura (AURC), não acurácia.
- **Baseline obrigatório e conhecidamente fraco:** a confiança auto-reportada
  pelo LLM, que a literatura mostra ser mal calibrada.
- **Features que não são o prompt:** concordância entre passagens recuperadas,
  geometria da tabela de origem, consistência aritmética com a conta-mãe,
  distância do valor à série histórica do emissor, concordância entre fontes.
- **Fronteira de decisão que muda o produto:** abster é a diferença entre RN02
  cumprida e alucinação numérica.

### Verificado pela sessão

`fatos_semanticos`: **186.701 células**, 741 companhias, **11 conceitos**, 64
trimestres — o número dele bate exatamente. Para os 5 bancos: **2.024 células**.

### FURO QUE A SESSÃO ENCONTROU NA PROPOSTA SOBREVIVENTE

**186.701 é o tamanho do painel, não o número de pares extraíveis-e-conferíveis.**
Para gerar o rótulo "o extrator acertou?" é preciso (a) um **documento** de onde
extrair e (b) o valor do painel. **Documento só existe para 5 bancos × 4
trimestres = 20 PDFs.** A saída (i) que ele propõe — "treinar nas 741
companhias, onde o rótulo é farto" — exige baixar e fazer OCR de centenas de
PDFs. O OCR de 20 documentos custou **USD 5,58**; o teto do projeto é **USD 25**.
A saída (i) não cabe no orçamento como escrita.

**Alternativa de custo zero que a sessão localizou:**
`artefatos/resultados_avaliacao/checkpoint_teste.jsonl` tem **1.981 respostas de
LLM já pagas e cacheadas**, cada uma com `exatidao_ok`, `recall_ok`,
`recusa_correta`, `recuperados` e a decisão de recusar. É exatamente o arranjo
de *selective prediction*, a custo zero. Limitação: **45 perguntas distintas**.

Isto vai aos dois na rodada 3.

---

## Rodada 3 — analista de mercado: FECHADA E VERIFICADA

*(Os dois agentes caíram por limite de sessão no início da rodada 3, sem produzir
resultado. Retomados pelo transcript às 18:15, com contexto das rodadas 1–2
intacto. Nada além do trabalho parcial da rodada 3 foi perdido.)*

### (a) A camada de abstenção reprova no teste dele: **abster é requisito, não entrega**

*"Cinto de segurança é obrigatório e não é o carro."* O motivo é o mesmo que
matou o selo, e ele nota que seria incoerente mudar de régua: **15 KPIs × 5
bancos = 75 células por trimestre, e ele confere as 75.** *Selective prediction*
ganha a vida onde o humano não consegue conferir tudo — milhares de extrações
por dia. A 75 células, resolve triagem que não existe.

**Exceção que ele registra:** na instância pública, respondendo a quem não tem o
PDF aberto, abster **é** o produto — é a RN02. Mas isso é conformidade da
instância pública, não ferramenta de analista.

### (b) A razão de custo dos dois erros — e por que ele recusa a pergunta

Número pedido: **≈ 50:1 só em tempo** (buraco = 5 min de ctrl-F; número errado
que ele não sabe que está errado = entra no relatório e o cliente opera em cima).
Mas ele recusa transformar isso em perda esperada: *"nenhuma casa de research
otimiza perda esperada em cima de número publicado; ela opera sob restrição
dura."* Os três parâmetros que ele assina:

1. **Risco máximo no conjunto respondido: 1 erro em 100.** Acima disso não usa,
   com qualquer cobertura.
2. **Cobertura mínima 60%; abaixo de 40% o produto não existe** — o ganho evapora.
3. **Abstenção por célula, nunca por documento.**

Ponto de operação = **joelho da curva risco–cobertura sob risco ≤ 1%**, não o
mínimo de risco seletivo.

### (c) A conclusão dura, reafirmada e agora explicada

> **Com este dado, nenhum artefato único é ao mesmo tempo "modelo de ML
> funcional" e "ferramenta de ouro para o analista de bancos". As duas
> exigências são satisfazíveis, mas não pelo mesmo objeto.**

A camada de abstenção **é a confirmação mais limpa disso**, não a exceção: o
rótulo exige documento, documento existe para 20 PDFs, logo o `n` do componente
aprendido está limitado **pela mesma restrição** que zera Basileia, margem,
NPL e eficiência no painel. **O gargalo é um só, aparecendo pela terceira vez.**

### (d) Proposta nova — mapeador semântico de contas em escala, com abstenção dentro

**Verificado pela sessão, número a número, e replica exatamente:**

| | agente | **sessão** |
|---|---|---|
| Triplas distintas `(plano_contas, cd_conta, ds_conta_norm)` | 37.540 | **37.540** |
| Mapeadas no `mapa_contas` validado | 198 (0,53%) | **198** |
| **Fração das 5.552.787 linhas que o mapa cobre hoje** | 4,95% | **4,9513%** |
| As 300 triplas mais frequentes cobrem | 85,06% | **85,059%** |
| Triplas em ≥10 emissores cobrem | 88,38% | **88,375%** |
| Cauda de emissor único | 29.978 triplas / 6,09% | **29.978 / 6,091%** |

**"Hoje":** o assistente responde com segurança sobre **11 conceitos e 4,95% das
linhas**. Fora disso não há conceito, a RN09 proíbe usar `cd_conta` direto, e a
resposta é recusa. **"Com isto":** ~300 conceitos, ~85% das linhas, 741
companhias, sob o mesmo gate G4 conferido emissor a emissor.

**Por que é ML de verdade, ao contrário da proposta A dele:** rótulo gratuito e
em escala (37.540 itens contra ~300), decisão aprendida com custo de erro real,
**gate de aceitação que já existe e já reprovou uma vez** (G4), e a abstenção
entra no lugar certo — a cauda de 29.978 triplas de emissor único é 6% das
linhas e é onde o modelo tem de se calar. **Esse rótulo não precisa de PDF.**

**Armadilha fundadora confirmada pela sessão:** `3.09` carrega
`lucro_liquido_consolidado` **e** `resultado_antes_tributos` conforme o plano.

### Os dois furos que ele mesmo declarou — e o estado real do primeiro

**Furo 1 — a alegação de ML ainda não está ganha.** No mapa validado,
`ds_conta_norm` **nunca** aponta para dois conceitos (a sessão confirmou: zero
casos). Se isso valer fora da amostra, um vizinho-mais-próximo sobre a string
resolve e a proposta vira "implementável e irrelevante".

**Medição adicional da sessão, que mantém o teste em aberto:** das **15.466**
descrições normalizadas distintas no painel, **5.595 (36%) aparecem com mais de
um `cd_conta`**. A descrição **não** é chave única no mundo real — ela só é
inequívoca nas 198 curadas. Isso é exatamente o viés de amostra curada que ele
teme, medido. **O teste continua genuinamente indeciso**, e é por isso que a
falsificação vai pré-registrada: publica-se **primeiro** a linha de base de
casamento por string, e o modelo só embarca se bater essa linha na métrica
ajustada por abstenção.

**Furo 2 — o rótulo aritmético não presta, e ele descarta.** Soma-dos-filhos ×
pai em **1.381.308** pares: 6,60% divergem acima de 5% e **47,5% das declarações**
têm ao menos uma divergência grave. Taxa dessa ordem mede a estrutura do plano da
CVM (irmãos duplicados), não erro de dado. *"É exatamente o tipo de número que eu
recusaria de outra pessoa. Reporto e descarto."*

### Recontagem do volume de rótulo — feita pela sessão

| Fonte | Volume honesto |
|---|---|
| Concordância PDF × painel, **só nos 20 documentos que existem** | **220 células** (5 bancos × 4 trimestres × 11 conceitos) |
| Checkpoint cacheado, respostas com exatidão avaliada | 288 registros — mas **45 perguntas distintas** |
| **Mapeamento de conta (proposta nova)** | **37.540 triplas, sem precisar de PDF** |

Os 186.701 do painel **não** são rótulo: rótulo de extração exige documento.

---

## Rodada 3 — cientista de dados: SEGUNDA E TERCEIRA RETRATAÇÕES

### (a) "186.701 células, rótulo farto" → **222**. Errou por 840×

Confirmou a contagem da sessão (220; ele achou 222, +2 do BB no 3T2025):
11 conceitos × 5 bancos × 4 trimestres. Contra 2.024 células dos 5 bancos nos 64
trimestres do painel: **60 das 64 janelas não têm documento de onde extrair.**

| Fonte | Rótulos **independentes** |
|---|---|
| PDF × painel na janela dos 20 documentos | **222** |
| Âncoras-sentinela já conferidas à mão | 20 |
| Perguntas do gabarito congelado | 45 |
| **Total** | **~287** |

Sobre o checkpoint: 1.981 registros = 225 células únicas repetidas em 9
configurações sobre as mesmas 45 perguntas. Exatidão existe em 960 registros mas
**em apenas 25 perguntas distintas**. *"Repetição não é amostra."*

### (b)(c) O piloto reprovou contra o guarda que já existe

Barra pré-registrada no docstring: risco tem de cair **e** McNemar ao nível da
pergunta ≥ 6 discordâncias com p ≤ 0,031 — o limiar que o projeto já usa.

| Política | Cobertura | Risco |
|---|---|---|
| Sem guarda | 1,000 | 0,490 |
| Baseline 1 — confiança do próprio LLM | 0,539 | 0,069 |
| **Baseline 2 — guarda determinístico RN02** | 0,269 | **0,007** |
| **Seletor aprendido**, cobertura casada | 0,499 | **0,081** |

**23 perguntas, 3 discordâncias, p = 1,0000 — INDISTINGUÍVEL.**

Dois portões que ele levantou contra o próprio piloto: o rótulo recuperado tem
concordância **0,7257** com o `exatidao_ok` do projeto (declarou 0,90 como
mínimo) — *"o piloto é ilustrativo, não é evidência"*; e o risco 0,007 do RN02 é
**em parte definicional** (o guarda pergunta se o número está no trecho; o rótulo
pergunta se a resposta contém o número do gabarito — quase a mesma condição) e
**não pode ser publicado como métrica de produto**.

### (d) Correção de um erro da SESSÃO PRINCIPAL: não é orçamento, é documento

A sessão havia enquadrado o gargalo como custo de OCR. **Errado.** O OCR dos 20
documentos **já está pago e cacheado** (`corpus/ocr/`, RNF10); extrair de novo
sobre o cache não custa OCR. Rotular 222 células + 20 âncoras = **242 extrações
≈ USD 0,27–0,30**. Os 1.981 registros do checkpoint custaram **USD 2,2232**.

> **"Cabe no orçamento e ainda assim não resolve. O que falta não é dinheiro: é
> documento. São 20."**

### (e) IF.data como terceira fonte: marginal, e o bloqueio é resolução de entidade

O relatório de capital **existe e está populado** na janela do corpus (33.672
linhas em 1T2026) com Basileia, RWA e Razão de Alavancagem — o que a CVM não tem.
**Mas nenhum dos 5 bancos aparece sob código resolvível**: os relatórios que os
cobrem usam uma série de código de conglomerado prudencial que o endpoint
público de cadastro **não mapeia**.

Ele conseguiria identificá-los por ordenação de ativo total e **recusou**:
*"identificar emissor por porte é exatamente o que a RN11 proíbe, e uma fonte de
conferência obtida por chute não confere nada."* Soma-se divergência de
perímetro (conglomerado prudencial × consolidação IFRS da holding).

---

## FURO NA PROPOSTA DO ANALISTA — encontrado pela sessão, é o MESMO erro

Aplicando à proposta do mapeador exatamente o teste que destruiu o número do
cientista de dados:

| | |
|---|---|
| Triplas **a classificar** | **37.540** |
| Triplas **com rótulo validado** (`mapa_contas`) | **198** |
| Conceitos definidos hoje | **11** |

**"Rótulo gratuito e em escala, 37.540 itens" repete a confusão de "186.701
células".** Item a classificar não é exemplo rotulado. O que existe são **198
sementes** e ~37.342 triplas **não rotuladas**.

Isso não mata a proposta — muda o que ela é. Deixa de ser aprendizado
supervisionado com rótulo farto e passa a ser **supervisão fraca / propagação a
partir de sementes**, e o custo humano passa a ser proporcional ao número de
**conceitos** (~300), não de triplas. Isso é trabalho manual real, mas limitado —
e, ao contrário de tudo o mais nestas três rodadas, **não esbarra no teto de 20
documentos**.

Vai aos dois na rodada 4, com a exigência de que o número seja recontado com o
mesmo rigor que derrubou os outros dois.

---

## Rodada 4 — analista de mercado: RETIRA A PRÓPRIA PROPOSTA E FECHA EM NEGATIVO

### Ele reconhece o erro e mede a escala dele

*"37.540 é o denominador, não o numerador. Existem 198 rótulos. Cometi, na
rodada 3, exatamente a falha que passei duas rodadas cobrando."* Erro de **190×**
contra os **840×** do cientista de dados. **Os dois especialistas cometeram a
mesma confusão, em rodadas diferentes, cada um pegando a do outro.**

### O que mata o mapeador — verificado pela sessão, replica exato

| | agente | **sessão** |
|---|---|---|
| Planos representados no top-300 | **1** | **1** (`ll3_11_d55d74d8`) |
| Companhias que usam esse plano | 696 / 741 (93,93%) | **696 / 741** |
| Triplas desse plano para 80% das linhas | 182 | **182** |
| **Para 85%** | **208** | **208** |
| Para 90% / 95% | 531 / 3.940 | **531 / 3.940** |

> **O top-300 por frequência não é uma amostra do painel. É o plano de contas
> padrão da CVM para não-financeiras — que a CVM publica.** Cobrir 85% das
> 5,55 M de linhas é transcrever **208 contas de um documento público**.

Estimativa dele: ~2 min por conta com o plano aberto ao lado = **~7 horas, um dia
de júnior**. Sênior seria necessário para ~20 contas, e nenhuma está nesse plano
— a armadilha do `3.09` vive nos 13 planos minoritários das instituições
financeiras, onde as 198 já cobrem o essencial.

> **"Um dia de júnior resolve 85% do painel sem modelo nenhum. O que sobra para
> o modelo são os 15% da cauda, que é onde não há semente, não há frequência e
> não há utilidade. Quarta vez no mesmo formato: a parte útil não é aprendida, e
> a parte aprendível não é útil."**

### Minha contra-evidência estava SUBESTIMADA — verificado

Os 36% eram de **descrições**. Em **linhas**:

| | sessão |
|---|---|
| Linhas sob descrição que aparece com >1 `cd_conta` | **93,356%** |
| `cd_conta` distintos sob a descrição "outros" | **258** |

A falsificação pré-registrada dele (*"o modelo só embarca se bater o casamento
por string"*) **o modelo venceria** — a string provadamente não é chave. Mas isso
deixou de decidir: os 93% de ambiguidade vivem nas subcontas profundas
("outros", "outras contas a pagar"), e os 85% que importam saem de 208 contas
não ambíguas e publicadas. *"O teste mede algo. Só que mede a parte do problema
que eu não quero resolver."*

### Achado lateral grave — verificado pela sessão

**O painel não tem DFC.** Demonstrativos presentes: **BPP, BPA, DRE** e nada
mais. **Zero linhas de fluxo de caixa**, zero DVA, zero detalhe de nota.

> *"Para Value Investing, FCO, capex e conversão de caixa valem mais que metade
> da lista de frequência — o resultado é opinião do contador, o caixa não é."*

Ele também assinou uma lista de **~40 conceitos por valor analítico**, contra os
~300 por frequência, notando que no top-45 estão reserva legal, ágio na emissão,
provisões cíveis (duas vezes), débitos com coligadas (duas vezes) e o
desdobramento ON/PN de lucro por ação — *"contas que existem em toda declaração
porque o formulário as exige, não porque alguém as consulte."*

### VEREDITO FINAL DELE — seis mortes medidas, nenhuma sobrevivente

| # | Candidato | Como morreu |
|---|---|---|
| 1 | Evento de crédito nomeado | Coluna crua `pl_ativo` 0,8765 bate o modelo; lacuna +0,16/+0,25 reprova T2 |
| 2 | Índice de estresse liderando NPL | ρ +0,687 em nível, **+0,076 em 1ª diferença** — tendência espúria |
| 3 | Modelo no recorte estressado | Passa T1 e T2 e **perde para `liq_corrente`** (0,692 × 0,754 intra) |
| 4 | Selo de risco de revisão | Falsificação pré-registrada do autor: captura 0,284 contra barra 0,40 |
| 5 | Camada de abstenção aprendida | 222 rótulos; risco 0,081 × **0,007** do RN02; McNemar p = 1,0000 |
| 6 | Mapeador semântico de contas | **208 contas de um plano publicado cobrem 85%** — um dia de júnior, sem modelo |

> **"Com estes dados, não existe modelo de ML que seja ao mesmo tempo funcional
> e útil para este produto."** O lado que tem `n` (5,55 M de linhas, 741
> companhias) não tem conteúdo bancário — Basileia 0 linhas, margem financeira 0
> linhas. O lado que tem conteúdo bancário tem **20 documentos**. *"Isso apareceu
> quatro vezes seguidas com quatro roupas diferentes, e a quarta fui eu vestindo."*

### O que ele entregaria, sendo o dono

1. **A tabela de 208 contas** — um dia, destrava 85% do painel para 741
   companhias, maior ganho por hora do projeto. **Não chamar de modelo.**
2. **O guarda RN02 determinístico como está** — venceu o seletor aprendido em
   medição pareada. *"Não substitua o que funciona por ML para satisfazer um
   requisito de ementa."*
3. **A extração de KPI bancário** sob a restrição assinada (risco ≤ 1/100,
   cobertura ≥ 60%, abstenção por célula). É o ouro do analista, e não tem ML.
4. **O negativo como resultado publicado** — seis falsificações com condição de
   reabertura, o protocolo T1/T2, a regra de lift-no-orçamento e a disciplina
   **"denominador não é rótulo"**, que pegou os dois especialistas desta mesa.
5. **Se a ementa exigir artefato de ML embarcado:** o alvo Z da §3.7, que passa
   T1 e T2 e já tem a utilidade limitada e declarada. *"Embarque-o rotulado como
   isso. Não o chame de ferramenta de ouro, porque ele não é, e nada nesta base é."*

---

## Rodada 4 — cientista de dados: MESMO VEREDITO, POR CAMINHO INDEPENDENTE

Ele auditou o mapeador **sem saber que o autor já o havia retirado** — o que
torna a auditoria um controle independente. Construiu a linha de base por string
que o analista pré-registrou. Validação **deixa-um-plano-de-fora**, universo
inteiro de 37.540 triplas, 11 conceitos + classe `nenhum`.

| Método | macro-F1 | Precisão pos. | **Falsos positivos** |
|---|---|---|---|
| **M1 — casamento exato de `ds_conta_norm`** | **0,9923** | 0,9850 | **3** |
| M2 — vizinho TF-IDF | 0,9798 | 0,9563 | 9 |
| **M3 — aprendido (TF-IDF + logística)** | **0,7743** | 0,4877 | **208** |
| M4 — só `cd_conta` (o que a RN09 proíbe) | 0,7056 | 0,2205 | 684 |

**McNemar: a string vence o aprendido 205 a 1, p = 4,0e−60.**

> **O modelo não é dispensável — é ativamente pior, e do jeito mais perigoso:**
> 208 falsos positivos, isto é, atribui conceito a conta que não é aquele
> conceito. **É a falha exata que a RN09 existe para impedir.**

### A razão, verificada pela sessão

| | |
|---|---|
| Descrições normalizadas que realizam os 11 conceitos | **18** |
| Dessas, apontando para 2 conceitos | **nenhuma** |
| A armadilha do G4 (`3.09`) | 2 conceitos, **2 descrições distintas** — a string separa |

### O custo que nenhum dos três havia nomeado

O gargalo **não** são as 180 decisões de conceito (171 das 180 descrições
aparecem em mais de um plano, então uma decisão propaga). É o **G4 por
conceito**: hoje o gate confere 11 conceitos contra os releases, emissor a
emissor. Cento e oitenta conceitos sob a mesma disciplina, agora sobre 741
companhias e não 5, é o trabalho real — **humano e sem atalho, porque é
exatamente o que dá validade ao mapa.**

### Consenso entre emissores não gera rótulo

Dá **classe, não identidade** (os 11 conceitos são realizados por 18 descrições;
o consenso parte o mesmo conceito em várias classes e alguém tem de dizer que
são a mesma coisa). E a frequência prevê **importância, não identidade** — taxa
de "ser um dos 11 conceitos" por quintil de nº de emissores: 0,0043 · 0,0040 ·
0,0033 · 0,0028 · 0,0120, plana.

### A fraqueza que ele levantou contra o próprio veredito

A curva de F1 por número de conceitos é plana (inclinação −0,00026, k = 3 a 11),
**mas sempre sorteia das mesmas 18 descrições** — não consegue criar strings
novas. *"É o mesmo viés de amostra curada que já nos enganou duas vezes, só que
agora do meu lado."* A extrapolação para k = 180 (F1 0,948) está no relatório
**declarada como não-medição** — extrapola 16× além da faixa sobre uma inclinação
indistinguível de ruído.

E recusou vender como risco os 33,9% de descrições com vizinha a cosseno ≥ 0,95:
inspecionou os pares e os de cosseno 1,000 são permutação de palavras
('gerais e administrativas' ~ 'administrativas e gerais') — **sinonímia, que o
mapa deve colapsar, não colisão.**

---

# SÍNTESE FINAL — o debate terminou em NEGATIVO, e a frase importa

**Os dois especialistas convergiram no mesmo veredito, por caminhos
independentes, cada um retirando a própria proposta.**

## A formulação exata, exigida pelo cientista de dados

> **Nenhuma das propostas sustentou um componente aprendido superior ao seu
> próprio baseline.**
>
> Não é que "nada de útil saiu". O que saiu foi **a régua que reprovou todas**.

## As seis mortes, com o baseline que venceu cada uma

| # | Candidato | Baseline vencedor |
|---|---|---|
| 1 | Evento de crédito nomeado | `pl_ativo` cru, AUC 0,8765 |
| 2 | Estresse agregado → NPL do sistema | Nada: ρ +0,076 em 1ª diferença (p=0,58) |
| 3 | Modelo no recorte estressado | `liq_corrente` cru, AUC intra 0,754 × 0,692 |
| 4 | Selo de risco de revisão | Barra pré-registrada do autor: 0,284 < 0,40 |
| 5 | Camada de abstenção aprendida | Guarda RN02 determinístico: risco 0,007 × 0,081 |
| 6 | Mapeador semântico | **`JOIN ON ds_conta_norm`: F1 0,9923 × 0,7743, 205×1** |

## A restrição estrutural, medida quatro vezes com quatro roupas

> **O lado que tem `n` não tem conteúdo bancário. O lado que tem conteúdo
> bancário tem 20 documentos.**

| | Painel (5,55 M linhas, 741 companhias) | Corpus (20 PDFs) |
|---|---|---|
| Basileia / CET1 | **0 linhas** | 20/20 |
| Margem financeira | **0 linhas** | 17/20 |
| NPL | 1 emissor | 17/20 |
| Eficiência | 1 emissor | 20/20 |
| **Fluxo de caixa (DFC)** | **não existe no painel** | — |

## O erro que pegou os DOIS especialistas — e virou regra

**"Denominador não é rótulo."** O cientista de dados contou 186.701 células do
painel como rótulo; o número usável é **222** (erro de 840×). O analista contou
37.540 triplas como rótulo; existem **198** (erro de 190×). Cada um pegou o do
outro; a sessão pegou o segundo aplicando a lição do primeiro.

## O que o projeto leva desta rodada

1. **A tabela de 208 contas** — um dia de júnior destrava 85% de 5,55 M de
   linhas para 741 companhias. **Curadoria + join, não modelo.** O trabalho real
   é o G4 estendido conceito a conceito.
2. **O guarda RN02 fica como está** — venceu o seletor aprendido em medição
   pareada. Não trocar o que funciona por ML para satisfazer requisito de ementa.
3. **A auditoria de observabilidade** como disciplina geral: *informação presente
   no dataset ≠ informação disponível no momento da decisão.* Foi o que derrubou
   o selo de revisão e é generalizável a qualquer feature histórica.
4. **A regra "construa o baseline trivial ANTES do modelo"** — na proposta 6, a
   linha de base venceu 205 a 1, e só descobre isso quem a constrói primeiro.
5. **Seis negativos reprodutíveis com barra pré-registrada**, todos com condição
   de reabertura, indo para `becos_sem_saida.md`.

## O que NÃO se conclui daqui

- Não se conclui que ML é inútil em research financeiro. Conclui-se que **nesta
  base** — 741 companhias, 3 demonstrativos, sem DFC, sem preços, 20 PDFs — não
  há tarefa em que um componente aprendido bata o baseline trivial dela.
- Não se conclui que o produto não tem valor. O ouro do analista (RAG +
  extração + abstenção determinística) **está entregue e não tem ML**.
- **Reabre com dado novo, não com modelo novo:** DFC (fluxo de caixa), preços
  *point-in-time*, ou documentos além dos 20. As três reabrem coisas diferentes.





