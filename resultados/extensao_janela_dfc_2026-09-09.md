# Extensão da janela — série histórica de J

**Data:** 2026-09-09. **Custo:** zero (dados públicos gratuitos).
Onda **separada** do piloto: os 25 pacotes de
[`piloto_bancos_dfc_2026-09-09.md`](piloto_bancos_dfc_2026-09-09.md)
permanecem congelados e não são alterados por nada aqui.

Pergunta desta onda: **até onde a série de J existe?** O piloto respondeu que J
é reconstruível; ele não disse por quantos trimestres. Cinco trimestres de três
emissores não sustentam poder estatístico nenhum, e era esse o gargalo declarado
na §9 do relatório do piloto.

Artefatos: `artefatos/b_dfc_01j/extensao/`. Código: mesmo
`scripts/piloto_bancos_dfc.py`, comando `estender`.

> **⚠️ RETRATAÇÃO ATUALIZADA OUTRA VEZ (2026-09-11).** A retratação logo abaixo,
> de 10/09, **também deixou de valer** — ela apresenta "os 15 mapeáveis são
> **todos** intervalo" e larguras de 3,9%–6,3% (Bradesco) e 16,5%–40,7% (Itaú)
> como resultado vigente. **Não são.** A
> [revisão independente](revisao_independente_b_dfc_01j_2026-09-10.md) mostrou
> que esses limites eram **fabricados** (achado F1): o residual líquido de uma
> rubrica que mistura juros e câmbio não limita a parcela de juros, porque
> câmbio tem os dois sinais e pode compensar juros.
>
> **Estado vigente, medido no artefato** (`artefatos/b_dfc_01j/auditoria.json`):
>
> | | |
> |---|---:|
> | Pacotes no escopo | 25 |
> | J identificado (ponto) | **0** |
> | J limitado (intervalo) | **0** — era 15 |
> | J não identificado | **24** |
> | Sem fonte | 1 |
>
> As larguras citadas abaixo ficam como **registro do que foi publicado**, não
> como medição. Trilha: [correção do instrumento](correcao_instrumento_b_dfc_01j_2026-09-10.md)
> → [parecer](parecer_correcao_b_dfc_01j_2026-09-11.md) →
> [implementação C1–C6](implementacao_c1_c6_b_dfc_01j_2026-09-11.md).

> **⚠️ RETRATAÇÃO ATUALIZADA (2026-09-10).** A retratação abaixo dizia que
> "nenhum número deste relatório muda". **Isso deixou de valer.** A leitura das
> notas explicativas mostrou que a parcela cambial dessas rubricas **não é
> separável** e elas passaram a NÃO IDENTIFICADAS. Consequência medida:
> **J como PONTO exato foi de 5 para ZERO** e o Bradesco passou a intervalo de
> **3,9% a 6,3%**; o Itaú, de **16,5% a 40,7%**. Os 25 pacotes seguem 24 com
> fonte e 9 sem J; o que mudou é que os 15 mapeáveis são **todos** intervalo.
> Evidência e magnitude:
> [`prontidao_b_dfc_01j_modelo_2026-09-09.md`](prontidao_b_dfc_01j_modelo_2026-09-09.md) §2-bis.

> **⚠️ RETRATAÇÃO PARCIAL (2026-09-09, mesma data, onda posterior).** A
> tentativa de construir um alvo de ML sobre esta série descobriu que **três
> das rubricas incluídas em J vêm CREDORAS em alguns trimestres** — duas
> impressas pelo próprio emissor. Despesa de captação por competência não é
> crédito: essas linhas embutem algo que o contrato exclui (câmbio, valor
> justo) ou são reclassificação. **Nenhum número deste relatório muda e a
> aritmética continua conferindo**; o que não se sustenta é a afirmação de que
> o J aqui somado é **o J do contrato** para Itaú e Bradesco. Dentro da janela
> congelada (2024T1–2025T1) nenhum crédito aparece, mas a dúvida é da rubrica,
> não do trimestre. É a armadilha do BTG outra vez, no emissor que este
> relatório tratou como melhor caso. Escopo, evidência e o que fecharia:
> [`prontidao_b_dfc_01j_modelo_2026-09-09.md`](prontidao_b_dfc_01j_modelo_2026-09-09.md) §2.

## 1. O que tornou a escala possível

Declarar página e colunas à mão para dezenas de documentos de sete anos seria
curadoria impossível de auditar — e o número da página muda a cada trimestre.
Duas automações substituíram a declaração manual, e **as duas foram validadas
contra a curadoria existente antes de qualquer uso**.

**A página da nota é localizada, não declarada.** Uma sonda regex exclusiva por
emissor varre o documento e exige **unicidade**: âncora que aparece em duas
páginas é ambiguidade, e escolher a primeira decidiria em silêncio qual tabela
vale. As sondas precisaram ser específicas — *"Despesa de juros e similares"*
sozinha também casa na DRE, *"Recursos de emissões de títulos"* aparece em nove
páginas do BB, e o título da nota do BB casa também no **sumário**, que traz
pontilhado e número de página.

**A ordem das colunas é declarada por emissor e conferida por aritmética.** O
`scripts/gate_g4.py` já registrava que a ordem entre isolado e acumulado *"muda
de emissor para emissor"*: o BB imprime **acumulado primeiro**, o Itaú e o
Bradesco imprimem **isolado primeiro**. E demonstração **anual não tem coluna de
trimestre isolado** — toda coluna é o exercício, e o 4º trimestre sai por
derivação, nunca por leitura direta.

**Contraprova antes de escalar: a automação reproduziu 15 de 15 declarações
manuais**, página e colunas, nos documentos que já tinham curadoria. Divergir
em uma só teria removido a razão de confiar nela onde não há com o que comparar.

## 2. A conferência que valida o mapeamento sem confiar em posição

Para cada emissor e ano, os trimestres isolados têm de somar ao acumulado
publicado — com os operandos vindo de **documentos diferentes**:

```
T1 + T2         = S1   (1º trimestre + 2º trimestre = 1º semestre)
T1 + T2 + T3    = M9   (…= acumulado de nove meses)
T1 + T2 + T3+T4 = A    (…= exercício, com o T4 derivado)
```

Se uma coluna estivesse mapeada para o período errado, a soma não fecharia. É o
mesmo método que `scripts/ancora_ifrs.py` já usa para resolver a cadeia
trimestral — identidade aritmética, nunca posição de coluna.

## 3. Seleção das fontes: onde o metadado engana

O catálogo IPE da CVM é a origem, mas seus campos **não podem ser tomados ao pé
da letra**:

- O BB arquivou demonstrações **em BR GAAP** sob o tipo *"Demonstrações
  Financeiras em Padrões Internacionais"* de 2019 a 2021. Aceitá-las teria
  produzido extração fora do perímetro IFRS que o contrato exige — plausível e
  errado.
- O Bradesco tem um documento de 2021 que é uma **"Reconciliação BRGAAP/IFRS"**,
  não demonstração completa.
- A convenção de `Especie`/`Assunto` **mudou** entre os catálogos: até 2024 a
  espécie é *"Demonstrações Financeiras em IFRS"*; em 2025 passa a
  *"Demonstrações Financeiras em Padrões Internacionais"* com o IFRS no assunto.
  Um filtro escrito para uma das convenções perde a outra em silêncio.

O filtro final aceita as duas convenções e **exclui** BR GAAP, reconciliação,
versão em inglês e formulário 6-K. O metadado seleciona candidatos; **o conteúdo
decide** — documento cuja nota não é localizável entra como lacuna declarada,
nunca como ausência silenciosa.

## 4. Resultado

**A série de J existe em 50 pares (emissor, trimestre), numa janela de
2018T1 a 2026T1** — contra 15 pacotes de cinco trimestres no piloto. Todos os
50 têm **fechamento aritmético conferido**: a soma das parcelas dá exatamente o
total impresso na nota.

| Emissor | Trimestres | Janela | J como ponto | Com P3 | Largura do intervalo |
|---|---:|---|---:|---:|---|
| **Bradesco** | 13 | 2021T2 – 2025T3 | **13** | 9 | 0 (ponto exato) |
| **Itaú Unibanco** | 21 | 2018T1 – 2026T1 | 0 | 15 | 0,02% – 1,41% |
| **Banco do Brasil** | 16 | 2021T1 – 2026T1 | 0 | 12 | 0,29% – 34,57% |
| **Total** | **50** | **2018T1 – 2026T1** | **13** | **36** | |

**36 dos 50 vêm do arquivamento original** do próprio trimestre, com protocolo,
versão e data de entrega à CVM — disponibilidade histórica certificada, não
coluna comparativa reapresentada.

A largura de até 34,57% no BB é honesta e tem causa nomeada: até 2023 a nota
imprime *"Obrigações por emissão de títulos e valores mobiliários **e outras
obrigações**"* numa linha só, misturando títulos emitidos (incluídos) com um
residual sem composição. O contrato proíbe estimar a parcela ausente.

| | |
|---|---:|
| Documentos no manifesto | 65 |
| Documentos coletados e validados | **65** |
| Documentos com nota extraída | 53 |
| Fatos extraídos com procedência | 1.194 |
| Identidades trimestrais conferidas | **20** (divergentes: **0**) |
| Identidades não verificáveis por vintage misto | 10 |
| Períodos com reapresentação medida | 6 |

## 5. Cinco defeitos que a extensão expôs, todos corrigidos

A escala revelou problemas que cinco trimestres não revelariam. Nenhum foi
descoberto por inspeção: **todos foram acusados por guarda ou conferência**.

### 5.1 "Usável" não exigia fechamento — o mais grave

O critério de trimestre usável aceitava `identificado` ou `limitado` **sem
exigir que a composição fechasse no total impresso**. Publicaria 75 trimestres
onde a aritmética sustentava 56. Composição que não fecha significa parcela não
capturada, e J estaria errado exatamente por essa parcela.

Corrigido: usável exige `fechamento_confere is True`. E a queda de 75 para 56
foi o que levou a investigar — e a encontrar o defeito 5.2.

### 5.2 Uma parcela de exclusão que só existe até 2020

Faltavam exatamente **3.912** no 1T2019 do Itaú. A causa: a nota daquela era
tinha uma linha a mais — *"Despesa Financeira de Provisões Técnicas de Seguros
e Previdência"* —, atualização de provisão e componente atuarial, os dois
excluídos pelo contrato. Declarada como rubrica opcional, os documentos de
2018–2020 passaram a fechar e a série voltou a 72 leituras.

**A conferência de fechamento apontou o valor exato do que faltava.** Sem ela, a
ausência de uma exclusão teria inflado J em 21% naquele trimestre.

### 5.3 Vírgula onde devia ser ponto: erro de mil vezes na origem

O total da nota do Itaú no 2T2023 imprime **`(41,923)`** — vírgula — enquanto
todas as parcelas da mesma tabela usam ponto. Lido como decimal em pt-BR, o
valor é 41,923; lido como milhar, 41.923. **Diferença de 1000×**, a mesma classe
que invalidou a rodada A do CAND-04 (§3.11).

As parcelas somam exatamente 41.923, o que sugere a intenção — **e usar essa
soma para escolher a leitura seria ajustar o dado ao teste.** O valor é
**recusado** e o defeito de origem fica declarado, seguindo o §3.3: declarar com
procedência, nunca mutar em silêncio.

### 5.4 Intervalo que não era intervalo

Quando a rubrica residual vem **credora** (reversão), somá-la reduz J em vez de
aumentar — e o "intervalo" saía com limite inferior maior que o superior.
Medido no Itaú de 2020. Corrigido com `min`/`max`: um intervalo mal ordenado não
é intervalo.

### 5.5 Reapresentação lida como divergência de mapeamento

A conferência `T1+T2 = S1` acusou divergência de R$ 1,3 bi no Bradesco de 2022.
Não era erro de leitura: o emissor **reapresentou** o período, e a soma misturava
um trimestre reapresentado com um semestre original.

| Período | No documento de 2022 | Como comparativo em 2023 | Diferença |
|---|---:|---:|---:|
| 2022T2 | 30.687.911 | 29.842.304 | 845.607 |
| 2022S1 | 59.901.357 | 57.759.632 | **2.141.725 (3,6%)** |
| 2022A | 131.311.254 | 130.801.913 | 509.341 |

A conferência passou a exigir **vintage consistente** e devolve
`nao_verificavel` quando os operandos só existem em bases diferentes — em vez de
acusar divergência que é do emissor. As reapresentações vão para
`vintages.jsonl` com os dois valores; nenhum sobrescreve o outro.

**Isto é a prova empírica de que *as-restated* não é *as-originally-reported*.**
A distinção que o piloto construiu em P3 deixou de ser teórica: tem magnitude
medida de até 3,6% num semestre.

## 6. Lacunas declaradas

**10 dos 65 documentos não tiveram a nota extraída**, cada um com causa
diagnosticada em `resumo.json` — sonda de página ausente em documento de era
não coberta (Bradesco 2019/2020, BB 2023T2, Itaú 2022A), rubrica com redação
ainda não mapeada, ou fecho de seção diferente. Nenhum foi descartado em
silêncio, e nenhum guarda foi afrouxado para incluí-lo: **a extração recusa em
vez de adivinhar**.

Duas lacunas de conteúdo, não de acesso:

- **Bradesco 2019 e 2020 anuais têm 3 páginas.** Não são demonstrações
  completas; o documento existe e não serve.
- **Santander e BTG continuam fora.** O piloto mostrou que J não é identificável
  neles por razão estrutural (mistura atuarial e resultado líquido por
  instrumento), e mais trimestres não mudam isso.

## 7. O que isto NÃO autoriza

**Nenhum treino.** 50 pares em três emissores mostram que o dado **existe** e é
auditável; não dizem que um modelo seja possível, nem substituem o pré-registro
com materialidade, poder e baselines do §12 do plano do piloto.

**Os 25 pacotes do piloto não foram alterados** — 5 identificados, 10 limitados,
9 não identificados, 10 com P3, exatamente como publicado. A extensão tem escopo
e artefatos próprios.

E o gargalo mudou de lugar, não desapareceu: **13 dos 50 têm J como ponto
exato**, e os outros 37 são intervalos cuja largura vai de 0,02% a 34,57%.
Qualquer protocolo futuro precisa decidir o que fazer com intervalo — não tratá-lo
como ponto.
