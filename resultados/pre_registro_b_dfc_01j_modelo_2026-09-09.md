# Pré-registro — B-DFC-01J-M: custo de captação por competência, um trimestre à frente

**Data:** 2026-09-09 · **Contrato de dado:** `B-DFC-01J/2026-09-09`
**Série-fonte:** `artefatos/b_dfc_01j/extensao/j_por_periodo.jsonl`
**Auditor:** `scripts/auditar_prontidao_b_dfc_01j.py` →
`artefatos/b_dfc_01j/prontidao/`

> **Este documento é escrito ANTES de medir qualquer desempenho.** É a condição
> que o AGENTS.md §3.11 impõe depois da rodada A do CAND-04: alvo, população,
> baselines, gates e limiares congelados primeiro; medição depois. Nenhum
> número de desempenho aparece aqui, e nenhum limiar abaixo foi escolhido
> olhando resultado.

---

## 1. O que este candidato é, e o que ele não herda

O piloto documental B-DFC-01J e a extensão da janela produziram uma série de
**J** — juros por competência dos instrumentos de captação, em IFRS
consolidado — para três emissores. Este pré-registro pergunta a única coisa que
ainda não foi perguntada: **essa série sustenta um componente aprendido?**

**Nada é herdado.** Os T1/T2 reprovados do C1 (§3.7) e do Rank 3 (§3.14), a
rodada A invalidada do CAND-04 (§3.11) e os INDECIDÍVEL do CAND-02/03 e Rank 5
não emprestam número, população nem limiar a este candidato. Em particular, **o
fato de a série existir e ser auditável não é evidência a favor do modelo** — é
pré-condição de dado, e o §3.8 já mediu seis candidatos em que a pré-condição
existia e o baseline trivial venceu.

---

## 2. Estimando

### 2.1 Alvo contínuo (para comparação com baselines)

```
y(i, t) = ln( J(i, t+1) / J(i, t) )
```

`J(i,t)` é o J do emissor `i` no trimestre isolado `t`, em unidade monetária
declarada por fonte. `y` é o **crescimento log do custo de captação por
competência** de um trimestre para o seguinte.

**Por que crescimento log e não nível.** O nível de J é dominado por porte: o
Itaú publica em milhões e os outros em milhares, e o erro absoluto de um
emissor de R$ 40 bi por trimestre não é comparável com o de R$ 15 bi. Erro
médio sobre níveis mediria porte, não previsão — é a classe de defeito que
invalidou a rodada A do CAND-04, onde 23 linhas de escala explicaram 61,64% do
erro. Log-razão é adimensional, aditiva no tempo e não exige denominador de
estoque (que a camada estruturada da CVM não resolve sob RN09).

**Por que não taxa efetiva `J/estoque`.** Seria economicamente melhor, e é o
alvo preferido se o estoque de captação vier a existir com procedência. Hoje
não vem: o estoque exigiria mapear as contas de passivo do painel CVM, cuja
cobertura semântica é de **4,95%**, com 698 chaves duplicadas (587
conflitantes). Declarar `J/estoque` agora seria pré-registrar um alvo cujo
denominador não existe.

### 2.2 Companheiro binário (para T1 e T2)

```
y_bin(i, t) = 1  se  y(i, t) > 0     (o custo de captação subiu)
```

**Por que existe um companheiro binário.** O limiar 0,15 do T1 e o 0,12 do T2
foram calibrados sobre amplitude de taxa de evento e sobre AUC — formas
definidas para alvo binário. Reaproveitá-los num alvo contínuo exigiria
inventar métrica nova, e métrica inventada é exatamente o que o §4.2 proíbe.
T1 e T2 rodam sobre `y_bin`; a comparação com baselines roda sobre `y`.

---

## 3. População

Entra em `y(i,t)` o par de trimestres consecutivos que satisfizer **todas** as
condições abaixo. As condições são de dado, não de resultado.

1. Os dois trimestres `t` e `t+1` são **isolados** (`T1`…`T4`) do mesmo emissor.
2. Os dois têm `fechamento_confere == True` — a composição fecha exato no total
   impresso da nota.
3. Os dois têm `status` em (`identificado`, `limitado`).
4. Quando o mesmo (emissor, trimestre) existe em mais de uma safra, vale a de
   **maior precedência**: `original` > `derivada_de_originais` >
   `derivada_sem_certificacao` > `as_restated`, empate pela data de entrega
   mais antiga. É a regra já implementada em `PREFERENCIA`.
5. **Corte de largura, declarado agora:** o par é excluído se a meia-largura
   relativa do intervalo de J em **qualquer** dos dois trimestres exceder
   **5%**. Justificativa: 5% é a ordem da variação trimestral que o alvo
   pretende prever; acima disso o intervalo do rótulo cobre o movimento a ser
   previsto e a observação não é mensurável. O corte é fixado antes de ver
   quantas observações sobrevivem.
6. O 4º trimestre entra **somente** por derivação `A − M9` com os dois
   operandos na mesma safra, marcado `derivado` (RN10).

**O 2T2026 (`corpus/holdout_2T2026`) não entra em nada.** Não é população, não
é validação, não é diagnóstico.

---

## 4. Baselines, todos calculados antes de qualquer modelo

| ID | Previsão de `y(i,t)` | Por que está aqui |
|---|---|---|
| **B0** | `0` — passeio aleatório em log | O nulo honesto: custo de captação não muda |
| **B1** | `y(i, t−4)` — mesmo trimestre do ano anterior | Sazonalidade; **só existe porque o 4T passou a ser derivado** |
| **B2** | mediana de `y(i, t−1..t−4)` | Persistência de tendência recente |
| **B3** | `ln(Selic_acum(t+1) / Selic_acum(t))` com a meta **vigente em `t`** propagada | **Benchmark econômico forte** exigido pelo contrato: J é estoque × taxa, e a taxa é decidida pelo COPOM |

**B3 é a barra que importa e pode não ser executável.** Ele exige a série da
meta Selic com disciplina point-in-time (a meta conhecida no fim de `t`, nunca
a realizada em `t+1`). Se a série não estiver disponível sem rede paga, **B3
fica declarado como não executado** e o candidato **não pode** ser aprovado com
base em B0–B2 apenas: superar persistência sem superar a taxa de juros não
demonstra nada sobre captação. Essa consequência é fixada agora.

Métrica primária de comparação: **MAE macro por emissor** (média dos MAE
por emissor, para que o emissor com mais trimestres não domine). Secundária:
MAE agregado. Intervalos por **bootstrap agrupado por emissor**, 2.000
reamostragens — o agrupamento é obrigatório porque trimestres do mesmo emissor
não são independentes (a lição do §3.16, onde o bootstrap agrupado mudou o
veredito de um T1 que passava na leitura pontual).

---

## 5. Gates, em ordem, com limiar congelado

Um gate reprovado **interrompe**: não se passa ao seguinte, e nenhum modelo é
carregado.

| Gate | Pergunta | Métrica | Limiar |
|---|---|---|---|
| **G0** | O dado é íntegro? | fração da população com fechamento exato **e** zero identidades trimestrais divergentes | **100% e 0** |
| **G1** | É *point-in-time*? | fração da população cujos dois trimestres têm `disponivel_em` certificado, e em que a data do operando mais tardio de `t` é **anterior** à de `t+1` | **100%** |
| **G2** | O rótulo tem erro menor que o sinal? | `mediana(meia-largura relativa) / mediana(\|y\|)` | **< 0,10** |
| **G3** | A amostra decide algo? | melhoria mínima detectável em MAE macro, 80% de poder, α = 0,05, bootstrap agrupado | **≤ 20%** do MAE do melhor baseline |
| **T1** | O alvo fabrica o próprio baseline? | maior amplitude de taxa de `y_bin` entre quintis de **cada** componente que define mecanicamente o alvo — `J(i,t)` e `J(i,t+1)` — e de qualquer normalizador usado | **< 0,15** |
| **T2** | Há sinal temporal ou só ordenação de emissor? | AUC agregada − AUC intra-emissor sobre `y_bin` | **< 0,12** |

**Justificativa dos dois limiares novos.** O 0,10 do G2 vem da mesma lógica do
corte de 5% da população: rótulo cujo erro passa de um décimo do movimento a
prever torna indistinguível uma melhoria de modelo de uma flutuação de leitura.
O 20% do G3 é o mesmo piso de economia que o CAND-03 (§3.10) congelou —
reaproveitar mantém coerência entre candidatos em vez de calibrar um número por
candidato.

**G3 tem uma exigência extra que não é negociável:** o poder é calculado com o
`n` **efetivo em emissores**, não em observações. Três emissores dão três
clusters independentes. Se o poder só alcançar o limiar tratando trimestres
como independentes, o gate **reprova** — tratar 22 trimestres do mesmo banco
como 22 réplicas é a "denominador não é rótulo" do §3.8 com outra roupa.

---

## 6. O que uma aprovação autorizaria, e o que não

Aprovar G0–G3 + T1 + T2 autoriza **executar um componente aprendido contra os
baselines B0–B3**, nada mais. Não autoriza publicá-lo, não autoriza expô-lo no
caminho interativo (RN07 continua valendo integralmente) e não autoriza usar o
`corpus/holdout_2T2026`.

**Confirmação, se e quando houver:** o holdout se gasta **uma vez**, numa
medição confirmatória cujo protocolo é escrito depois da aprovação e antes da
execução, com o modelo e os baselines já congelados.

## 7. Condição de invalidação deste pré-registro

Este documento é invalidado — e reescrito do zero, sem herdar número — se:

- o alvo, a população, os baselines ou os limiares mudarem **depois** de
  qualquer medição de desempenho;
- a série de J for reestendida ou recorrigida de forma que altere `y` de
  observação já medida (a correção é permitida; o pré-registro é que não
  sobrevive a ela);
- alguma observação for removida por ser *outlier* de resíduo. A lição do
  §3.11 é literal: as 23 linhas descobertas pelo residual **não podem ser
  removidas** para salvar o teste. Defeito achado no resíduo é adjudicado
  contra a fonte, com procedência, e o teste é refeito inteiro.
