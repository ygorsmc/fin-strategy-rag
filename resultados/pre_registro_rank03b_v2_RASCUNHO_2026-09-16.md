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
**[DECIDIR]** no texto: §3.2 (seguradoras), §5.1 (leitura de G0.1) e §5.5
(G0.5). **Leia o §11 antes de decidir:** ele declara o que já foi visto,
inclusive uma taxa de evento no painel compartilhado publicada em 15/09.

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

**Painel de pesquisa** (`artefatos/painel_pesquisa_rank03b/painel.duckdb`,
digest de conteúdo **`f9cb9da9d58673ff…`**, manifesto de correções
**`4735fb107cce…`**, 101 linhas, manifesto do painel em
`manifesto_painel.json`), construído por `scripts/painel_pesquisa_rank03b.py`
a partir dos 31 ZIPs pinados, segundo o
[contrato do lote C](contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md).
Identificado por **digest de conteúdo** e pelos hashes das entradas, inclusive
o manifesto de correções de escala. `cvm.duckdb` e `cvm_treino.duckdb` não são
usados como fonte de valores.

Regras de dado que esta medição herda, todas escritas **antes** de medir o
alvo: estados de trimestre e perdas (F1–F6), valor não informativo (A2),
disponibilidade (P1–P3) e adjudicação de escala por documento com fonte (S1–S10).
**Documento de escala suspeita não adjudicado permanece com o rótulo declarado.**

---

## 5. G0 — integridade, decisivo

| # | Verificação | Limiar | Como se aplica ao painel de pesquisa |
|---|---|---|---|
| G0.1 | Sem soma de `DFC_MD` e `DFC_MI` no mesmo trimestre | 0 | **Leitura a decidir (§5.1).** Por unicidade: um valor por (companhia, trimestre) → 0. Literal: 117 |
| G0.2 | Nenhum trimestre fora de 80–100 dias | 0 | Duração **recomputada das datas** das linhas trimestrais; período fora da banda nunca é linha trimestral, é perda inventariada |
| G0.3 | Saltos de ativo ≥ 100× entre trimestres adjacentes | ≤ 0,5% | Depois das correções com fonte, e só delas |
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
**escalas declaradas diferentes**, sem que nenhuma das duas tenha sido
adjudicada, pode estar errado por mil — e um trimestre assim muda o sinal do
TTM, que define a elegibilidade e três componentes de T1. Medido em 16/09,
**antes** de qualquer adjudicação: 83 trimestres isolados combinam acumulados de
escalas declaradas diferentes.

- **Proposta:** G0.5 = fração de trimestres **válidos** derivados de operandos
  com escalas declaradas diferentes em que ao menos um operando **não** tem
  veredito decidido; limiar **≤ 0,5%**, a mesma tolerância já congelada para
  G0.3 (não é número novo).
- **Já medido, e declarado aqui por isso:** no painel com correções, 82
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
linhagem já implementadas. **Amostra vazia reprova.**

---

## 7. T1 — **idêntico à v1**

Seis componentes (`fco_ttm_sobre_sd8`, `fco_ttm_em_D`, `fco_ttm_sobre_ativo`,
`sd8_fco_isolado`, `ativo_total_em_D`, `trimestres_com_fco_negativo_nos_ultimos_8`);
limiar < 0,15 para todos; mínimo de 500 observações **e** 30 companhias por
componente; zona cinzenta [0,12; 0,15) com 2.000 reamostragens por companhia e
P(> 0,15) > 10% ⇒ INDECIDÍVEL. Nenhum componente pode ser retirado.

## 8. T2 — **idêntico à v1**

Lacuna AUC agregada − AUC intra-companhia < 0,12; escore constante levanta;
companhias com um só rótulo publicadas.

## 9. Baselines — da v1, com a ambiguidade do §8 resolvida

B0 a B3 da v1. As métricas **não são as mesmas para os quatro**, e a v1 já
dizia isso (§8: "B0 publica acerto **e cobertura**"):

| Baseline | Publica | Por quê |
|---|---|---|
| **B0** (classe majoritária) | **Acerto e cobertura**, com IC 95% agrupado por companhia | É escore constante: AUC = 0,5 e precisão no top-10% indefinida por construção. Exigir essas métricas dele seria exigir número sem conteúdo — e T2 levanta com escore constante (§8) |
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
- no painel de pesquisa **sem correções** (digest `08fffc8b…`): G0.3 = 132
  saltos (0,5875%), G1 = 10.748 observações em 502 companhias, zero violações;
- no painel de pesquisa **com as 101 correções** (manifesto `4735fb107cce…`,
  digest `f9cb9da9d58673ff…`): **G0 e G1 aprovados** — G0.3 = 47 saltos
  (0,2092%), G0.2 e G0.4 = 0, G0.1 por unicidade = 0 (literal = 117, §5.1),
  G1 = **10.750 observações em 502 companhias**, zero violações. Com o
  manifesto da execução 1 da adjudicação (substituída pela ressalva RC1):
  61 saltos (0,2715%), também aprovado — **a regra corrigida não decidiu o
  veredito**;
- diagnósticos do painel governante: A2 (3 ativos não informativos; 49 saltos
  se incluídos), conflito/ambíguo (3 ativos; 49 saltos se incluídos), G0.5
  proposto (§5.5), G0.1 literal (§5.1), identidades contábeis (6/23/14);
- inventário de perdas, versões e identidades (lote B e
  `medicoes_estruturais.json`);
- o custo da política de disponibilidade (§2.2): **3.082** trimestres válidos
  com intervalo cego entre a primeira e a última versão, e **6.735** datas de
  decisão da mesma companhia dentro deles.

### 11.4 Adjudicação de escala — como a regra foi escrita

- 405 documentos adjudicados (cabeçalho de apresentação e números impressos
  nas notas), 77 corrigidos por documento e 24 por herança dentro de trecho;
  premissa de herança testada em 2 trechos (`003549`, `023604`), 1 não
  testável.
- **A regra final (RC1-bis) foi escrita depois de ver a saída da execução 1**
  (falsos positivos da BRF e de notas de rodapé) e **refinada sobre uma
  amostra de desenho que se sobrepõe à avaliação** (documentos do piloto e
  casos BRF/TIM que também estão no escopo). Não houve amostra fresca. O que
  mitiga, sem eliminar: a regra ficou **mais conservadora** (só MIL decide), a
  execução 1 está preservada e medida (61 saltos, também aprovada), e nenhuma
  estatística de rótulo participou da escolha.
- **Conferência pontual das 7 correções apoiadas num único número bruto**
  (B8 da auditoria), por continuidade do ativo bruto com vizinhos declarados
  MIL (`verificacoes_revisao_final.json`): **5 corroboradas**. `ESC-0040` só
  tem vizinhos que também são correções (circular) e `ESC-0101` não tem
  vizinho declarado MIL; as duas se apoiam só no cabeçalho. Mantidas, sem
  ajuste pós-hoc.
- **Amostra de desenho sob a regra final** (23 documentos vmax do piloto em
  E1–E4): MIL 11 confirmados e 1 indecidível; UNIDADE 5 corrigidos e 6
  indecidíveis.

### 11.5 Deslize de leitura

Dois valores de FCO acumulado de uma companhia (`025704`, 3T2024) foram
impressos ao estudar o formato de XML. Não há rótulo, semestre futuro nem
agregação envolvidos.

## 12. O que esta rodada não fará

Nenhum modelo; nenhuma escrita nos painéis compartilhados; nenhum acesso ao
holdout; nenhuma chamada paga; nenhum ajuste de população, limiar, componente,
regra de dado ou correção de escala depois de medir.

## 13. Condições de falsificação

As da v1 (§11), mais: o painel medido ter digest diferente do registrado aqui;
o manifesto de correções ter hash diferente; alguma regra de dado (F, A, P, S)
ter mudado depois do congelamento; qualquer estatística de rótulo **além das
declaradas no §11** ter sido calculada antes do congelamento; o G1 da medição
montar a amostra com o rótulo antes de G0 e G1 aprovarem.

## 14. Artefatos

| | |
|---|---|
| Painel | `artefatos/painel_pesquisa_rank03b/painel.duckdb` + `manifesto_painel.json` (o painel sem correções tem `manifesto_painel_sem_correcoes.json` próprio desde 16/09) |
| Correções | `corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv` |
| Gates estruturais | `artefatos/painel_pesquisa_rank03b/gates_g0_g1.json` (governante), `gates_g0_g1_sem_correcoes.json`, `gates_g0_g1_diagnostico_execucao1.json` |
| Medições estruturais | `artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json` (`scripts/medicoes_estruturais_rank03b.py`) |
| Auditor | `scripts/auditar_rank03b_consumo_operacional.py` (a medição de T1/T2 lerá o painel de pesquisa por `scripts/gates_painel_pesquisa_rank03b.py`, a estender só depois do congelamento). **Requisitos que o código ainda não cumpre e que a extensão tem de cumprir antes de medir:** IC 95% agrupado para acerto e cobertura do B0 (§9); a leitura de G0.1 decidida em §5.1; o G0.5 se aprovado |
| Verificações da revisão | `artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json` (`scripts/verificacoes_revisao_final_rank03b.py`) |
