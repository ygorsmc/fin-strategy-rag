# Pré-registro v2 — Rank 3-B: início de consumo operacional persistente

**Data do rascunho:** 2026-09-16.
**Status: RASCUNHO — NÃO CONGELADO. Aguarda aprovação do responsável.**
Enquanto estiver neste estado, **nenhum T1, T2 ou baseline é medido** sobre dado
real. O congelamento é: aprovação explícita → remoção de "RASCUNHO" do título e
do nome do arquivo → SHA-256 publicado → só então a medição.

**Substitui** o [pré-registro de 11/09](pre_registro_rank03b_consumo_operacional_2026-09-11.md)
(`fbae30cc…`), **consumido** pela rodada que parou em G0. **Não é Rank 3-C:** o
estimando, os componentes e os limiares são os mesmos. Mudam o painel (agora o
de pesquisa, com fonte e linhagem) e as regras que a v1 deixava implícitas e
três ondas de correção mostraram ambíguas.

**Pontos que exigem decisão do responsável antes de congelar** — marcados
**[DECIDIR]** no texto: §3.2 (seguradoras), §5.1 (leitura de G0.1), §5.5
(G0.5 e seu limiar), §6.1 (grade de D), §8.1 (suporte intra de T2) e, desde
24/09, §12-bis (alcance da prova de escala). **Leia o
§11 antes de decidir:** ele declara o que já foi visto, inclusive uma taxa de
evento no painel compartilhado publicada em 15/09.

> **Revisão de 17/09.** A [conferência independente](conferencia_pre_treino_rank03b_2026-09-17.md)
> achou erro de escala comprovado (ESC-0101), uso de prova de escala antes da
> publicação e partição defeituosa de T1. As correções seguem os
> [contratos RF-01 a RF-08](contratos_correcao_rf01_rf08_rank03b_2026-09-17.md)
> e estão no [relatório da onda](correcao_rf01_rf08_rank03b_2026-09-17.md).
> A conferência seguinte achou CRF-01 a CRF-03. As
> [correções de 18/09](correcao_crf01_crf03_rank03b_2026-09-18.md) fecharam as
> guardas e tornaram a adjudicação mais estrita. **Nenhum dos 405 documentos
> teve tabela suportada pela v4; o manifesto ficou sem correções e G0 voltou
> a reprovar.** Isso não prova que as 68 correções antigas eram erradas:
> não foram certificadas pela nova regra. Este rascunho não autoriza treino.

---

## 1. A previsão — transcrita da v1, sem alteração

> **Eu espero que este alvo REPROVE T1, e o componente que deve reprová-lo é
> `fco_ttm_sobre_sd8` — a distância de FCO até zero medida em desvios-padrão do
> próprio FCO.**
>
> **Mecanismo:** `Y` é um limiar de sinal sobre uma série contínua. Quem está a
> 0,2 desvios acima de zero atravessa por ruído; quem está a 5 desvios não
> atravessa nem com deterioração real. A regra do §4.4 diz que escapa da
> armadilha só evento **materialmente definido** — falência, evento legal,
> reapresentação. `FCO < 0` **não é** um desses: é limiar sobre série contínua, e
> a elegibilidade "FCO_TTM > 0 em D" agrava, porque concentra a população perto
> da fronteira.
>
> **Se essa previsão se confirmar, o veredito é REJEITADO e não há terceira
> tentativa com o mesmo formato.** Baixar o limiar, trocar `sd8` por outro
> normalizador ou mudar o horizonte cria **Rank 3-C**, com pré-registro próprio.
>
> **Se ela NÃO se confirmar** — todos os componentes abaixo de 0,15 com folga —,
> então a distinção "limiar sobre série contínua × evento material" é mais fraca
> do que o §4.4 afirma, e **a regra é que precisa ser corrigida**, não o alvo.
> Esse resultado seria publicável como achado de método.

A previsão **continua não testada**: a rodada de 11/09 parou em G0.

---

## 2. Alvo — o da v1, com as operacionalizações escritas

**Origem de cada operacionalização**, para não atribuir à v1 o que ela não
dizia. A v1 (§2) escreve só "primeiro trimestre **fiscal** cujo INÍCIO é
posterior a D" e "os três trimestres fiscais seguintes". São **posteriores à
v1** e já estavam em código antes deste rascunho:

- **"até D + 3 meses"** e **q2–q4 com datas encadeadas** — contrato H1.1/H1.2
  de [15/09](contratos_correcao_qw1_qw8_2026-09-15.md), achado N1;
- **rótulo = trimestre civil de `dt_fim`** — contrato T2 do
  [lote C](contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md) (16/09), que
  só nomeia; a ordem e o encadeamento continuam pelas datas (§2.1);
- **disponibilidade pela maior versão** (§2.2) — contrato P do lote C.

Nenhuma delas muda o estimando; todas mudam **quais** observações existem, e
por isso entram aqui para serem congeladas.

```text
D  = data de decisão. Só entra informação disponível em D (§2.2).
q1 = primeiro trimestre cujo INÍCIO é posterior a D, e até D + 3 meses (H1.1)
q2, q3, q4 = os três trimestres seguintes a q1, com datas encadeadas (H1.2)

S1 = FCO(q1) + FCO(q2)
S2 = FCO(q3) + FCO(q4)

Y = 1  se  S1 < 0  E  S2 < 0
Y = 0  se  ambos S1 e S2 existem e a condição não se cumpre
Y = indefinido (observação DESCARTADA) se qualquer um dos quatro FCO falta
```

Elegibilidade, **a da v1**: `FCO_TTM` conhecido em `D` > 0; companhia não
financeira (§3); os quatro trimestres existem como trimestre isolado; ativo total
conhecido em `D` e > 0. Unidade de observação: (companhia, `D`). Unidade de
agrupamento de toda inferência: **companhia**.

### 2.1 Identidade dos trimestres

Trimestre = `(companhia, dt_ini, dt_fim)`, com duração de 80 a 100 dias. O
rótulo `kTAAAA` é o trimestre civil de `dt_fim` e serve só para ordenar; q1 é
escolhido pelas **datas** e q2–q4 exigem ordinal consecutivo **e** início no dia
seguinte ao fim do anterior. Num exercício de trimestres de três meses isso é o
"trimestre fiscal" da v1; num exercício irregular, o que não encadeia é
censurado, nunca deslocado.

### 2.2 Disponibilidade das features — política conservadora

O número em mãos de cada documento é o da **maior versão** (a única que a fonte
guarda). Ele só é usado a partir da **recepção dessa versão**; num trimestre
derivado, da recepção mais tardia entre os operandos. **Consequência
declarada:** quando `D` cai entre a primeira e a última versão de um documento,
aquele trimestre não está disponível em `D` e a janela usa o que estava. Isso
não vaza; custa perda, medida em §11.

**Prova da escala (P4, 17/09).** A escala corrigida também é informação. Um
documento corrigido só está disponível quando **todas as provas da escala
aplicada** foram publicadas: o próprio documento, na correção por documento;
**as duas pontas do trecho**, na correção herdada. A data vale para o valor e
para toda derivação que o usa. Não se usa "dado corrigido retrospectivamente".

### 2.3 Safra do rótulo

`FCO(q1..q4)` usa a maior versão, **disponível ou não em D** — o rótulo é
futuro por definição. Reapresentação posterior entra no rótulo.

---

## 3. População

### 3.1 Da v1, sem alteração

Exclui-se a companhia com `plano_contas LIKE 'll3_09_%'` **ou** `is_banco`.
Sem controle setorial (`companhias.setor` em 5 de 741). Só consolidado.

### 3.2 Seguradoras — **[DECIDIR]**

Medido em 16/09, depois da v1
(`artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json`, `fonte`): o
plano **`ll3_13`** (seguros) tem **3 companhias** no universo de 700; em
**duas** delas (`023159`, `024180`, 24 linhas) a conta `6.01` se chama
*"Caixa Líquido Atividades Seguradora/Resseguradora"*. Fluxo operacional de
seguradora é outra economia.

- **Proposta:** acrescentar `OU plano_contas LIKE 'll3_13_%'` à exclusão. É o
  mesmo critério estrutural da v1, aplicado a outro plano financeiro, e é
  **conservador** (perde-se companhia, não se contamina população).
- **Alternativa:** manter as 3 e declarar.

Decidido **antes** de medir T1/T2. Nenhuma contagem de evento **por
companhia ou por plano** foi vista; a taxa agregada do painel compartilhado
foi (§11), e não separa seguradoras.

---

## 4. Painel

**Painel de pesquisa:** `artefatos/painel_pesquisa_rank03b/painel.duckdb`,
digest de conteúdo **`6ca635a904f11140…`**, manifesto de correções
**`13520e61d99f…`**, zero linhas, execução 4b da adjudicação com a regra v4,
manifesto do painel em `manifesto_painel.json`; **G0 reprovado em 18/09**.
A execução 3 de 17/09 — `1250cefb…`/`6330d78d…`, 68 correções — foi
preservada e substituída por insuficiência de prova tabular. A versão de 16/09 —
`f9cb9da9…`/`4735fb10…`, 101 linhas — foi **substituída** depois da
conferência de 17/09. O painel é construído por `scripts/painel_pesquisa_rank03b.py`
a partir dos 31 ZIPs pinados, segundo o
[contrato do lote C](contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md).
Identificado por **digest de conteúdo** e pelos hashes das entradas, inclusive
o manifesto de correções de escala. `cvm.duckdb` e `cvm_treino.duckdb` não são
usados como fonte de valores.

Regras de dado que esta medição herda, todas escritas **antes** de medir o
alvo: estados de trimestre e perdas (F1–F6), valor não informativo (A2),
disponibilidade (P1–P4) e adjudicação de escala por documento com fonte (S1–S10,
com a evidência tabular v4 do contrato CRF-01 de 17/09 e adendo de 18/09;
a evidência numérica v3 do contrato E é histórica).
**Documento de escala suspeita não adjudicado permanece com o rótulo declarado.**

---

## 5. G0 — integridade, decisivo

| # | Verificação | Limiar | Como se aplica ao painel de pesquisa |
|---|---|---|---|
| G0.1 | Sem soma de `DFC_MD` e `DFC_MI` no mesmo trimestre | 0 | **Leitura a decidir (§5.1).** Por unicidade: um valor por (companhia, trimestre) → 0. Literal: 117. A conferência de 17/09 recomenda a leitura por unicidade (CPC 03, §§18–20A) |
| G0.2 | Nenhum trimestre fora de 80–100 dias | 0 | Duração **recomputada das datas** das linhas trimestrais; período fora da banda nunca é linha trimestral, é perda inventariada |
| G0.3 | Saltos de ativo ≥ 100× entre trimestres adjacentes | ≤ 0,5% | Depois das correções com fonte, e só delas. **Fórmula (RF-05):** pares de linhas de ativo **válidas** da mesma companhia, consecutivas e com ordinal adjacente, com `max/min ≥ 100`, divididos pelo **número de linhas de ativo válidas** (não pelo número de pares) |
| G0.4 | Nenhum valor nulo nas contas usadas | 0 | Contado em **todos** os candidatos, antes dos estados |
| G0.0 | Universo não vazio; toda conta requerida com linha | — | Implementado em 16/09 |

**As observações que G0.3 reprovar NÃO são removidas** (§4.4 regra 9).

### 5.1 G0.1 — **[DECIDIR]**: qual leitura vale

O texto da v1 é "sem soma de `DFC_MD` e `DFC_MI` no mesmo trimestre". No
painel de pesquisa nenhum documento traz os dois métodos, e a tabela acima
aplica G0.1 como **unicidade** (um valor por companhia e trimestre), o que dá
**zero**. Mas um trimestre **derivado** (acumulado atual − acumulado anterior)
pode subtrair acumulados de métodos diferentes quando a companhia troca de
método dentro do exercício. **Lido literalmente, isso é "soma" dos dois
métodos no mesmo trimestre**, e aí G0.1 dá **117 trimestres válidos em 49
companhias** — reprova com limiar 0.

- **Proposta:** a leitura por unicidade, com a derivação entre métodos
  **permitida e declarada**. Motivo: o caixa líquido operacional é o mesmo
  número nos dois métodos (CPC 03, §§18–20); o risco que G0.1 protegia na v1 era
  **duplicar** caixa somando as duas demonstrações do mesmo documento, e esse
  risco é zero aqui. O método de cada operando fica na linhagem.
- **Alternativa A:** leitura literal — G0 **reprova** e a rodada para.
- **Alternativa B:** leitura literal como **censura** — os 117 trimestres saem
  como perda inventariada (novo estado), e G0.1 volta a zero. Muda a
  população; é regra de dado nova e precisa ser congelada aqui.

**Já medido, e declarado por isso:** o número 117/49 foi calculado em 16/09
(`gates_g0_g1.json`, `diagnostico_g0_1_literal`). Foi a auditoria de
conformidade que apontou a ambiguidade; o lote C tinha adotado a leitura por
unicidade sem submetê-la a decisão (contrato G3-pp). A decisão é do
responsável.

### 5.5 G0.5 — **[DECIDIR]**: derivação com escalas não adjudicadas

G0.3 só olha o ativo. Um trimestre de FCO derivado de dois acumulados de
escalas **heterogêneas**, sem que as duas tenham sido adjudicadas, pode estar
errado por mil — e um trimestre assim muda o sinal do TTM, que define a
elegibilidade e três componentes de T1. Medido em 16/09, **antes** de qualquer
adjudicação: 83 trimestres isolados combinam acumulados de escalas declaradas
diferentes.

**População (corrigida em 17/09, RF-04):** trimestre válido cujos operandos
diferem na escala **declarada ou aplicada**, com algum operando sem veredito
decidido. A versão de 16/09 olhava só a declarada e deixava fora a correção
parcial (declaradas iguais, uma corrigida). Publicado por configuração.
Escalas distintas não provam erro sozinhas; o que G0.5 mede é **ausência de
adjudicação** onde há heterogeneidade.

**Limiar — a decisão não é automática.** A proposta abaixo reutiliza 0,5%, mas
isso é **política nova** para outro evento (trimestre de FCO) e outro
denominador (trimestres válidos): não herda a validação do G0.3. E erro já
demonstrado **não** é tolerado por caber no limiar — ele é corrigido (§11.6).
Os números da versão de 16/09, abaixo, são da população antiga; os da
população corrigida estão no §11.3.

- **Proposta (reescrita em 17/09):** G0.5 = fração de trimestres **válidos**
  cujos operandos diferem na escala **declarada ou aplicada** e em que ao menos
  um operando **não** tem veredito decidido; limiar **≤ 0,5%**. **Este limiar é
  política nova** (outro evento, outro denominador): reutiliza o número do
  G0.3 por simplicidade, não por validação herdada, e aprová-lo é decisão
  própria. Na versão vigente (18/09) mede **0,3712%** (§11.3); na execução 3
  substituída, media 0,2535%.
- **Texto de 16/09, substituído:** "escalas declaradas diferentes … a mesma
  tolerância já congelada para G0.3 (não é número novo)".
- **Já medido na execução 2 (histórico), e declarado aqui por isso:** no painel com correções, 82
  trimestres válidos combinam escalas declaradas diferentes, 38 deles com algum
  operando sem veredito — **0,172%**. A proposta foi escrita **antes** dessa
  medição (a versão anterior deste rascunho não tinha o número); aprová-la
  agora não muda o resultado estrutural, e por isso a decisão deve se apoiar no
  mérito do risco, não no número.
- **Alternativa:** não acrescentar e declarar a lacuna.

## 6. G1 — point-in-time, decisivo

Os três itens da v1 (G1.1 features com recepção ≤ D; G1.2 q1 é o primeiro
trimestre iniciado depois de D, até D + 3 meses; G1.3 nenhum trimestre do
rótulo começa antes de D), mais as verificações de contiguidade, unicidade e
linhagem já implementadas, e **G1.4 (17/09): nenhuma feature usa, em D, um
documento cuja prova de escala foi publicada depois de D** — recalculado do
manifesto de correções e do cadastro, **não** da data que o construtor gravou.
**Amostra vazia reprova.**

**Ordem da medição (RF-05).** G0 e G1 são medidos com a amostra montada **sem
rótulo** (`calcular_rotulo=False`). Só se os dois aprovarem o executor monta
`y` — e sobre **a mesma** amostra, com uma conferência de que as chaves
(companhia, D) são idênticas. O `executar()` do auditor de 11/09 **não** é
reutilizado: ele monta `y` antes de G1. O executor v2 é escrito e testado em
dados sintéticos **depois** das decisões deste rascunho e **antes** do
congelamento.

### 6.1 Grade de D — **[DECIDIR]**

**O que o código faz:** para cada companhia, D percorre as datas de
**disponibilidade das linhas de FCO trimestral válidas** (inclusive as
derivadas e as adiadas pela prova de escala, §2.2), não todas as recepções do
cadastro nem as atualizações que só trazem ativo. Efeito de seleção: uma
companhia cujo único arquivamento novo num período é de balanço não gera D
nesse período; um D pode ser a data de publicação de uma ponta de trecho.

- **Proposta:** manter e congelar essa grade, publicando o número de datas
  descartadas por cada motivo (já publicado em `descartes`).
- **Alternativa:** D = toda recepção do cadastro da companhia. Muda a
  população; precisa ser decidido antes de medir.

### 6.2 Janela e `sd8`

Oito trimestres históricos **contíguos e encadeados** (§2.1), os mais recentes
disponíveis em D; TTM = os quatro últimos. `sd8` é o desvio-padrão amostral dos
oito. **`sd8 = 0`** não descarta a observação: deixa `fco_ttm_sobre_sd8`
**ausente**, e ela sai **só** do componente e do baseline que dividem por
`sd8` (B1 e T2). Cada componente e cada baseline publicam
`observacoes_usadas` e `companhias_usadas`, para que a ausência seja visível.

---

## 7. T1 — **idêntico à v1**, com a partição escrita

Seis componentes (`fco_ttm_sobre_sd8`, `fco_ttm_em_D`, `fco_ttm_sobre_ativo`,
`sd8_fco_isolado`, `ativo_total_em_D`, `trimestres_com_fco_negativo_nos_ultimos_8`);
limiar < 0,15 para todos; mínimo de 500 observações **e** 30 companhias por
componente; zona cinzenta [0,12; 0,15) com 2.000 reamostragens por companhia e
**frequência bootstrap** de amplitude > 0,15 acima de 10% ⇒ INDECIDÍVEL.
Nenhum componente pode ser retirado.

**Partição (RF-03, 17/09).** Ordena-se pelo componente; os cortes nominais são
`⌊k·n/5⌋`, k = 1..4; cada corte avança até o fim do grupo de valores
empatados; corte que cai em 0, em n, ou não depois do anterior é **eliminado**.
Um componente discreto (como `trimestres_com_fco_negativo_nos_ultimos_8`) pode
ter menos de cinco faixas, e o número de faixas é publicado. A versão anterior
do código criava faixas de uma observação depois de um empate grande.

**Natureza da frequência bootstrap.** É a fração das reamostragens de
companhias em que a amplitude passou de 0,15 — uma medida de instabilidade da
estatística, **não** a probabilidade posterior de a amplitude verdadeira
exceder o limiar. A regra de decisão a usa como está.

## 8. T2 — **idêntico à v1**, com o escore escrito

Lacuna AUC agregada − AUC intra-companhia < 0,12; escore constante levanta;
companhias com um só rótulo publicadas.

**Escore e sentido (RF-05):** o de **B1**, `fco_ttm_sobre_sd8` com sentido
**negativo** (quanto menor a distância a zero, maior o risco). AUC com meio
ponto para empate. **AUC intra** = média simples das AUCs das companhias que
têm os dois rótulos; AUC zero é publicada como zero (R6, 17/09).

### 8.1 Suporte da AUC intra — **[DECIDIR]**

**Hoje uma única companhia com os dois rótulos basta** para T2 ser medido.
Não há piso escrito.

- **Proposta:** congelar sem piso novo, publicando
  `companhias_com_os_dois_rotulos` e `companhias_na_amostra` ao lado da lacuna.
- **Alternativa:** fixar um piso **agora**, antes de medir. Um piso escolhido
  depois de ver o número seria ajuste pós-hoc.

## 9. Baselines — da v1, com a ambiguidade do §8 resolvida

B0 a B3 da v1. As métricas **não são as mesmas para os quatro**, e a v1 já
dizia isso (§8: "B0 publica acerto **e cobertura**"):

| Baseline | Publica | Por quê |
|---|---|---|
| **B0** — **"sempre não consumir"** (regra fixa, **não** uma classe majoritária estimada) | **Acerto** com IC 95% agrupado por companhia, e **cobertura de previsão de classe = 1,0 por construção** (sem intervalo: não há o que variar) | É escore constante: AUC = 0,5 e precisão no top-10% indefinida por construção. Exigir essas métricas dele seria exigir número sem conteúdo — e T2 levanta com escore constante (§8). Implementado em 17/09 (`B0_sempre_nao_consumir`) |
| **B1–B3** (ranqueadores) | AUC agregada, AUC intra-companhia e precisão no top-10%, **todas com IC 95%** agrupado por companhia | — |

Mínimo de 40 reamostragens válidas por intervalo. Baseline sem as métricas da
sua linha é **incompleto**.

**O que muda:** a v1 punha como condição "o desafiante superar o melhor
trivial" — resultado de um modelo que o próprio protocolo ainda não permite
treinar. Aqui os dois momentos se separam:

| Momento | Condição |
|---|---|
| **PRONTO PARA CHALLENGER** (fim desta rodada) | G0, G1, T1 e T2 aprovados **e** os quatro baselines completos |
| **Modelo aprovado** (protocolo próprio — D8 do [levantamento](pendencias_desbloqueio_treino_dfc_2026-09-15.md), escrito e congelado **depois** desta rodada e **só** se ela terminar em PRONTO PARA CHALLENGER) | Desafiante supera o **melhor** trivial por margem cujo IC 95% pareado exclui zero, fora da amostra. A métrica que define "melhor" entre baselines de métricas diferentes (B0 × B1–B3) **não é fixada aqui**: é parte do D8 |

PRONTO PARA CHALLENGER é **permissão para escrever e executar o protocolo do
desafiante**, não evidência de superioridade.

## 10. Vocabulário de veredito — o da v1

REJEITADO · REPROVADO EM G0/G1 · INDECIDÍVEL · PRONTO PARA CHALLENGER.

---

## 11. O que já foi visto antes deste pré-registro

Declaração exigida pelo levantamento (D7). **Nenhum T1, T2, AUC ou baseline
sobre dado real foi calculado** em nenhuma rodada (11/09 parou em G0; 12/09,
15/09 e 16/09 mediram estrutura). **Mas estatística de rótulo foi vista**, e
uma versão anterior deste rascunho dizia o contrário. O inventário completo:

### 11.1 Estatísticas de rótulo — vistas

- **Taxa do evento no painel compartilhado (`cvm_treino.duckdb`), publicada
  em 15/09:** [implementação QW1–QW8](implementacao_qw1_qw8_2026-09-15.md), §3,
  "Taxa do evento **0,0526 → 0,0530**" (construção de 12/09, 10.670
  observações → construção corrigida, 10.605), "Com rótulo `y` diferente: **3**"
  e "FCO TTM não positivo **−5**". Foi calculada **antes** de existir a regra
  O1 (lote B, 16/09), para medir o efeito da correção N1, e o
  [contrato do lote B](contratos_lote_b_rank03b_2026-09-16.md) a omitiu da
  declaração do que já fora visto (ressalva RA7 de lá).
  **O que ela revela:** a taxa-base **agregada** do evento, ≈ 5%, num painel
  com o defeito de escala. **O que não revela:** nenhuma taxa condicional a
  componente, quintil, companhia ou plano — nada do que T1 ou T2 medem. A
  previsão do §1 é de 11/09, anterior a esse número. As propostas dos §§3.2,
  5.1 e 5.5 foram escritas **conhecendo** a taxa-base, e isto fica declarado.
- **Descartes por `FCO_TTM ≤ 0` em D no painel de pesquisa** — contagem
  agregada sobre uma feature que define a elegibilidade (proibida pelo item 1
  do O1: "TTM de FCO agregado"). Esteve nas versões de 16/09 dos três
  artefatos de gate (≈ 2.865 a 2.867 candidatos, conforme a variante) e foi
  lida. Removida desde a correção de auditoria A1: os artefatos atuais dizem
  "omitido por O1".

### 11.2 Rótulo calculado em memória — não inspecionado

Até a correção A1 de 16/09, `construir_amostra` do auditor **sempre** calculava
`S1`, `S2` e `y` ao montar a amostra, inclusive quando só se queria contar
observações para G1. Toda execução que mediu G1 fez isso: no painel
compartilhado (as rodadas e conferências de 12 a 16/09 que chegaram a G1) e no
painel de pesquisa em 16/09 (sem correções, diagnóstico da execução 1 e o
painel governante, cada um mais de uma vez). **Fora do 11.1, nenhum valor
derivado desses cálculos foi impresso, agregado ou gravado.** Desde a A1, o G1
do painel de pesquisa monta a amostra com `calcular_rotulo=False`, e um teste
garante que as somas do rótulo nem são chamadas.

### 11.3 Contagens estruturais — permitidas e vistas

- no painel compartilhado: 132 saltos (fração 0,005874); 10.605 observações
  construíveis em 494 companhias;
- no painel de pesquisa **sem correções** (digest `08fffc8b…`, versão de 16/09; com o código de 17/09 o mesmo painel tem digest `6ca635a9…` pela coluna `dt_prova_escala`): G0.3 = 132
  saltos (0,5875%), G1 = 10.748 observações em 502 companhias, zero violações;
- **versão vigente (18/09, execução 4b, regra v4):** 405 documentos
  indecidíveis, zero tabelas com cabeçalho local suportado, zero correções,
  herança não autorizada por S5. Manifesto `13520e61d99f…`, digest
  `6ca635a904f11140…`. **G0 reprovado:** 132 saltos (0,5875%, acima de 0,5%).
  G1 estrutural aprovado: 10.748 observações / 502 companhias, G1.4 = 0.
  G0.5 proposto: 82/22.088 = 0,3712%; A2/conflito: três ativos cada,
  134 saltos se incluídos. G0.1 literal: 117 trimestres em 49 companhias.
  Nenhuma estatística do alvo calculada; perda de cobertura do extrator não
  prova erro em todas as correções antigas nem impossibilidade de adjudicar;
- **versão de 17/09, execução 3, substituída (68 correções, manifesto
  `6330d78d02df…`, digest `1250cefb9a7276ce…`): G0 e G1 aprovados** — G0.3 =
  **68 saltos (0,3026%)**, G0.1/G0.2/G0.4 = 0 (G0.1 literal = 117 em 49
  companhias), G1 = **10.750 observações em 503 companhias**, G1.4 = 0; G0.5
  com a população corrigida = **56/22.088 (0,2535%)**, por configuração:
  43/43, 8/39 e **5/5** (declaradas iguais, aplicadas diferentes); A2 e
  conflito/ambíguo: 3 ativos cada, 70 saltos se incluídos; P2: 3.077
  trimestres com intervalo cego, **6.728 pares (trimestre, D)** e **4.175
  chaves (companhia, D) distintas**. Sem correções, com o código novo: digest
  `6ca635a9…`, mesmos 132 saltos, G1 10.748/502. Diagnóstico da execução 1:
  61 saltos, G1 10.744/502;
- **versão de 16/09, substituída** — no painel de pesquisa **com as 101 correções** (manifesto `4735fb107cce…`,
  digest `f9cb9da9d58673ff…`): **G0 e G1 aprovados** — G0.3 = 47 saltos
  (0,2092%), G0.2 e G0.4 = 0, G0.1 por unicidade = 0 (literal = 117, §5.1),
  G1 = **10.750 observações em 502 companhias**, zero violações. Com o
  manifesto da execução 1 da adjudicação (substituída pela ressalva RC1):
  61 saltos (0,2715%), também aprovado — **a regra corrigida não decidiu o
  veredito**;
- diagnósticos **históricos da execução 2 (16/09, substituída)**: A2 (3 ativos não informativos; 49 saltos
  se incluídos), conflito/ambíguo (3 ativos; 49 saltos se incluídos), G0.5
  proposto (§5.5), G0.1 literal (§5.1), identidades contábeis (6/23/14);
- inventário de perdas, versões e identidades (lote B e
  `medicoes_estruturais.json`);
- o custo da política de disponibilidade (§2.2), na versão de 16/09: **3.082**
  trimestres válidos com intervalo cego e **6.735** — que são **pares
  (trimestre, D)**, não decisões distintas (RF-07); as chaves distintas eram
  4.181.

### 11.4 Adjudicação de escala — como a regra foi escrita

- **Execução 2 (16/09, histórica):** 405 documentos adjudicados (cabeçalho de apresentação e números impressos
  nas notas), 77 corrigidos por documento e 24 por herança dentro de trecho;
  premissa de herança testada em 2 trechos (`003549`, `023604`), 1 não
  testável.
- **A regra da execução 2 (RC1-bis) foi escrita depois de ver a saída da execução 1**
  (falsos positivos da BRF e de notas de rodapé) e **refinada sobre uma
  amostra de desenho que se sobrepõe à avaliação** (documentos do piloto e
  casos BRF/TIM que também estão no escopo). Não houve amostra fresca. O que
  mitiga, sem eliminar: a regra ficou **mais conservadora** (só MIL decide), a
  execução 1 está preservada e medida (61 saltos, também aprovada), e nenhuma
  estatística de rótulo participou da escolha.
- **(16/09, sobre a execução 2, substituída)** **Conferência pontual das 7 correções apoiadas num único número bruto**
  (B8 da auditoria), por continuidade do ativo bruto com vizinhos declarados
  MIL (`verificacoes_revisao_final.json`): **5 corroboradas**. `ESC-0040` só
  tem vizinhos que também são correções (circular) e `ESC-0101` não tem
  vizinho declarado MIL; as duas se apoiam só no cabeçalho. Mantidas, sem
  ajuste pós-hoc — **e ESC-0101 estava errada** (conferência de 17/09); a
  frase "sem ajuste pós-hoc" confundia corrigir erro comprovado com ajustar
  ao resultado.
- **Amostra de desenho sob a regra da execução 2, histórica** (23 documentos vmax do piloto em
  E1–E4): MIL 11 confirmados e 1 indecidível; UNIDADE 5 corrigidos e 6
  indecidíveis.

### 11.5 Deslize de leitura

Dois valores de FCO acumulado de uma companhia (`025704`, 3T2024) foram
impressos ao estudar o formato de XML. Não há rótulo, semestre futuro nem
agregação envolvidos.

### 11.6 Conferência e correções de 17/09

- A conferência reproduziu o painel e os gates de 16/09 em memória, comprovou
  o erro de ESC-0101 em duas páginas do PDF, e contou por identidade e data
  (sem valores) as **24 correções herdadas** com prova posterior e as **5
  observações** afetadas. Mediu a classe omitida de G0.5 (3 trimestres) e as
  6.735/4.181 incidências do P2.
- A execução 3 mudou 95 decisões para indecidível e 11 de indecidível para
  decidida, sem inverter nenhuma escala. **A regra v3 foi escrita conhecendo
  ESC-0101 e com a execução 2 à vista**, e duas correções foram inspecionadas
  linha a linha (declarado no contrato E5). O resultado de G0 não foi visto
  antes da execução, e a regra não foi mexida depois dela.
- A contraprova do G1.4 no manifesto da execução 2 reproduziu as 5
  observações e contou observações, sem valores.
- **Nenhuma estatística de rótulo foi calculada.**

## 12. O que esta rodada não fará

Nenhum modelo; nenhuma escrita nos painéis compartilhados; nenhum acesso ao
holdout; nenhuma chamada paga; nenhum ajuste de população, limiar, componente,
regra de dado ou correção de escala depois de medir.

## 12-bis. Adjudicação de escala — regra v3 (17/09, histórica)

A evidência numérica que decide a escala de um documento é **localizada**
(contrato E1): valor consolidado do período corrente; número numa linha das
notas que contém o rótulo daquela conta (vocabulário fechado E2) e não fala de
ações; página que declara milhares; número que não coincide, sob outro
multiplicador, com outro valor da mesma conta. Cada correção publica onde
estão os números que decidiram. A regra v2 (execuções 1 e 2) corrigiu
ESC-0101 por um "1.000" de quantidade de ações e está aposentada.

### Regra vigente: v4 (18/09)

Os [contratos CRF](contratos_correcao_crf01_crf03_rank03b_2026-09-17.md) e
seu [adendo](adendo_contratos_crf_2026-09-18.md) exigem cabeçalho local com
unidade e perímetro consolidados, datas completas e correspondência da
conta com a célula da data corrente. Só saldos 1, 2 e 1.01.01 são elegíveis
como prova nesta versão; nenhum fluxo 6.x é usado sem identificação do
intervalo. Linha sem estrutura suportada é indecidível. Não se exige que as
notas reais adotem esse layout: **o extrator é que não sabe certificá-las**.
Na aplicação aos 405 documentos, nenhuma tabela foi reconhecida. A regra
não foi relaxada para recuperar G0. Reabrir a adjudicação exige outro
contrato de extração/prova, não elevar o limiar do gate nem recolocar a v3.

Exposição declarada: a v4 foi desenhada conhecendo ESC-0029, ESC-0101 e as
contraprovas publicadas. Houve correção de unicidade em sintético e nova
readjudicação (4b) antes do primeiro G0 da v4; depois, só a guarda do
consumidor de prova serializada mudou, com igualdade de AST fora dela e
revalidação das provas. Os pins anteriores foram preservados. Não houve
nova estatística de rótulo, T1, T2 ou baseline real nesta onda.

### Alcance da prova de escala — **[DECIDIR]** (acrescentado em 24/09)

Na v4 só saldos (1, 2, 1.01.01) provam escala, mas a correção entra no
manifesto **por documento**: o construtor aplica a escala do documento ao
ativo e ao FCO, e a impressão digital da correção cobre as contas 1 e 6.01.
Pela v4, então, uma prova de saldo corrige também o FCO. A linha GEOM-1
([relatório de 18/09](escala_geometrica_rank03b_2026-09-18.md), [contrato de
24/09](contratos_alcance_geom1_rank03b_2026-09-24.md)) adotou outro critério:
demonstrar a escala em cada conta que o painel usa. Hoje a diferença não tem
efeito, porque a v4 não tem correção, mas os dois critérios não podem valer
juntos quando houver uma. Origem: [ressalva da revisão de 24/09](alcance_geom1_rank03b_2026-09-24.md).

- **Opção A — o que a v4 faz hoje:** prova de saldo corrige o documento
  inteiro. Premissa: a escala é declarada uma vez por formulário; se um saldo
  mostra que ela está errada, está errada para todas as demonstrações do
  documento. Sob A, depois de integrada a GEOM-1 sob contrato próprio,
  **140867 e 142900** se qualificam pela prova de caixa conferida em 18/09
  (142900 é documento de desenho da regra); o G0.3 cairia de 132 para 130
  saltos e continuaria reprovado (limite: 112). *(Consequência corrigida em
  25/09: a primeira versão citava só 140867, que sozinho não move o G0.3.)*
- **Opção B — o que a linha GEOM-1 pede:** correção que altera o FCO exige
  prova que alcance o FCO. O manifesto por documento só recebe documento com
  as duas contas provadas; hoje nenhum cumpre isso. Fechar as quatro ligações
  dos dois documentos daria o mesmo −2.
- **Proposta:** B. É a regra que a GEOM-1 já adotou e impede que o G0 aprove
  com FCO não adjudicado; o custo é que, por ora, nenhum documento se
  qualifica. Rotas para provar o FCO (anexo do grupo 192, identidade interna
  da DFC) exigem contrato próprio. Nas duas opções, correção só do ativo
  continua vedada enquanto G0.3 e G0.5 lerem o veredito por documento.

## 13. Condições de falsificação

As da v1 (§11), mais: o painel medido ter digest diferente do registrado aqui;
o manifesto de correções ter hash diferente; alguma regra de dado (F, A, P, S)
ter mudado depois do congelamento; qualquer estatística de rótulo **além das
declaradas no §11** ter sido calculada antes do congelamento; o G1 da medição
montar a amostra com o rótulo antes de G0 e G1 aprovarem; alguma observação
usar, em D, escala cuja prova foi publicada depois de D; a partição de T1
diferir da do §7.

## 14. Artefatos

| | |
|---|---|
| Painel | `artefatos/painel_pesquisa_rank03b/painel.duckdb` + `manifesto_painel.json` (o painel sem correções tem `manifesto_painel_sem_correcoes.json` próprio desde 16/09) |
| Correções | `corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv` |
| Gates estruturais | `artefatos/painel_pesquisa_rank03b/gates_g0_g1.json` (governante), `gates_g0_g1_sem_correcoes.json`, `gates_g0_g1_diagnostico_execucao1.json` |
| Medições estruturais | `artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json` (`scripts/medicoes_estruturais_rank03b.py`) |
| Auditor | `scripts/auditar_rank03b_consumo_operacional.py` (a medição de T1/T2 lerá o painel de pesquisa por `scripts/gates_painel_pesquisa_rank03b.py`). **Cumpridos em 17/09:** IC do acerto do B0, partição de T1, AUC zero em T2, correções só validadas. **Ainda não cumpridos, e exigidos antes de medir:** o executor v2 com a ordem do §6; a leitura de G0.1 decidida em §5.1; o G0.5 com o limiar decidido; as decisões dos §§6.1 e 8.1 e do alcance da prova (§12-bis) |
| Verificações da revisão | `artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json` (`scripts/verificacoes_revisao_final_rank03b.py`) |
