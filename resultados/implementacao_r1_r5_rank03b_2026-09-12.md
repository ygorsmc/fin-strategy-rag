# Implementação das correções R1–R5 do instrumento do Rank 3-B

**Data:** 2026-09-12. **Origem:** [revisão independente de
12/09](revisao_rank03b_consumo_operacional_2026-09-12.md).
**Contratos, registrados antes do código:**
[contratos_correcao_r1_r5](contratos_correcao_r1_r5_rank03b_2026-09-12.md).

**Veredito do candidato inalterado: REPROVADO EM G0. Nenhum modelo carregado.
T1, T2 e baselines seguem NÃO medidos sobre o painel real.** Esta onda corrige o
instrumento; **não remede o alvo**.

Suíte: **2.030 casos, zero skip** (era 2.010). **+20 contraprovas**, todas
exercitando a decisão.

---

## 1. Placar

| Achado | Antes | Depois |
|---|---|---|
| **R1** identidade da observação | `max(valor)` e `min(dt_receb)` de linhas diferentes; 4 grupos de FCO e 26 de ativo com data antecipada | Carga por **linha**; vintage escolhido **em D** por `vigente_em`; **0 e 0** |
| **R2** horizonte e janelas | `q1` deslocava para o trimestre seguinte disponível; "TTM" com lacuna | `q(D)` pelo **calendário**; janelas contíguas exigidas; chave `(companhia, D)` única |
| **R3** ranking | `sorted(zip(escores, alvos))` desempatava **pelo rótulo**: precisão 1,0 e lift 10,0 com escore constante | Ordenação cega ao desfecho; empate no corte pelo **valor esperado**: precisão 0,1 e lift 1,0 |
| **R4** decisão | Insuficiência virava `REJEITADO`; baseline falho dava **`PRONTO PARA CHALLENGER`** | Três estados separados; completude dos baselines **na conjunção**; métricas do §8 implementadas |
| **R5** suporte | Mínimo de companhias só na amostra global; componente de **1 companhia** aprovava | Mínimo aplicado ao suporte **efetivo** por componente e por baseline |
| **R6** adjacência | 136 saltos, quatro deles não adjacentes | **132**, com os quatro publicados e o motivo |
| **R7** diagnóstico de escala | Um recorte, duas classes, linguagem de "linhas erradas" | Quatro recortes lado a lado, **três** classes, linguagem de **transições suspeitas** |
| **M1** tautologia · **M2** determinismo | `assert ... or True`; dez exemplos variáveis | Asserção real; **inventário completo e ordenado** |

---

## 2. R4 é o mais grave, e é o achado F10 pela quarta vez

A falha dos baselines virava `reprova_em_aberto` e **não entrava na conjunção de
aprovação**: o auditor declarava o próprio instrumento quebrado e devolvia
`PRONTO PARA CHALLENGER`. É exatamente a regra 7 do §4.4 — *"exigência que
existe como texto e não participa da condição de aprovação"* —, que eu escrevi
naquele arquivo **no dia anterior** e repeti no auditor seguinte.

A contraprova é a matriz completa, com o consumidor isolado:

| Estado | Antes | Agora |
|---|---|---|
| T1 insuficiente, T2 passa | `REJEITADO` | **`INDECIDIVEL`** |
| T1 zona cinzenta, T2 passa | `REJEITADO` | **`INDECIDIVEL`** |
| T1 reprova numericamente | `REJEITADO` | `REJEITADO` (não-regressão) |
| Tudo passa, baseline falho | **`PRONTO PARA CHALLENGER`** | **`INDECIDIVEL`** |
| Tudo passa, baselines completos | — | `PRONTO PARA CHALLENGER` |

**O quinto caso é o que dá sentido aos outros quatro.** Sem ele, um
`"aprovado": False` literal passaria nos quatro primeiros e pareceria correto.

---

## 3. R1 — a observação passou a ser uma linha

O agrupamento tomava `max(valor_reais)`, `min(dt_receb)`, `min(dt_ini_exerc)` e
`max(dt_fim_exerc)` **independentemente**. Em `023507/1T2015`, o valor
`+19.075.000` (recebido em 05/05/2015) saía com disponibilidade de
**21/10/2014**, herdada de outra linha rotulada com o mesmo trimestre.

A correção move a escolha do vintage **da carga para a decisão**: `vigente_em`
devolve, entre as linhas com `dt_receb <= D`, a de recepção mais recente —
inteira. É o que a torna point-in-time em vez de retroativa.

**Evidência colateral de que o defeito era real:** a carga passou de 22.013 para
**22.034** linhas de FCO e de 22.428 para **22.471** de ativo. As 64 linhas a
mais são exatamente as duplicatas que o `GROUP BY` colapsava — e cujos atributos
eram recombinados.

O desempate é cego ao valor e ao rótulo: `versao`, depois `demonstrativo`,
depois `dt_ini`. Escolher pelo valor **era** o defeito.

---

## 4. R2 — q(D) pelo calendário

`primeiro_trimestre_apos(D)` calcula o horizonte **sem olhar o dado**. Removendo
`3T2019`, `D = 10/05/2019` deixou de produzir observação — antes aceitava
`q1 = 4T2019`, deslocando o horizonte contratual em silêncio e medindo outro
estimando. Bordas conferidas: 31/03, 01/04, 31/12 e 01/01.

Janelas passadas exigem ordinais consecutivos: sem `4T2018`, o "TTM" que somava
`2T2018 + 3T2018 + 1T2019 + 2T2019` — quatro linhas num vão de cinco — passou a
ser descartado com motivo. E `JANELA_SD + 1` virou `JANELA_SD`: exigir nove
antecedentes para componentes que usam oito era corte não declarado.

**Não-regressão travada por contraprova:** série completa e regular continua
produzindo observações, e em todas elas `q1 == primeiro_trimestre_apos(D)`. Sem
esse caso, descartar tudo passaria nos dois testes acima.

---

## 5. R3 — a ordenação deixou de ver o rótulo

Além de ordenar só pelo escore, a precisão no top-k passou a ser a **esperada
sob desempate aleatório** quando um grupo de empate atravessa o corte. Isso
elimina o vazamento *e* a arbitrariedade de qual metade entraria.

| Cenário | Antes | Agora |
|---|---|---|
| Escore constante, taxa-base 0,10 | precisão **1,0**, lift **10,0** | precisão **0,1**, lift **1,0** |
| Escore perfeitamente discriminante | 1,0 | **1,0** (não-regressão: sinal real não é achatado) |
| Permutação das linhas | — | métricas **idênticas** |

Rejeitei desempate por semente aleatória, que *"não demonstra invariância, só a
esconde atrás de uma semente"* — mesma razão que já havia rejeitado essa via no
contrato C1.

As métricas do §8 que faltavam passaram a existir: **IC95% por bootstrap
agrupado por companhia** e **AUC intra-companhia**, por baseline. `if auc` virou
`if auc is not None`, para que AUC **zero** — ordenação perfeitamente errada —
não seja publicada como "não medido". E B0 publica as **duas** coberturas:
abstenção de ranqueamento não é ausência de previsão de classe.

---

## 6. Uma emenda ao meu próprio contrato, declarada

**Meu contrato desta onda adiou a correção de adjacência (R6) para "outra onda".
Isso foi erro de escopo meu, e o corrigi durante a execução.**

O pré-registro **congelado** diz, literalmente: *"nenhum salto de `ativo_total`
por fator ≥ 100 **entre trimestres adjacentes**"*. Meu código comparava linhas
consecutivas na lista ordenada, que não é a mesma coisa quando há lacuna. Isso é
defeito de **fidelidade ao contrato**, exatamente a classe que esta onda existe
para corrigir — adiá-lo enquanto eu corrigia cinco outros seria incoerente.

**A emenda não podia favorecer o candidato, e não favoreceu:** sob as duas
leituras G0.3 reprova (0,6052% e **0,5874%**, contra 0,5%). Os quatro pares
descartados saem publicados com a distância em trimestres — 14, 3, 3 e 5 —, os
mesmos que a revisão identificou.

Registro a emenda em vez de silenciá-la porque alterar contrato depois de medir
é justamente o laço que este projeto proíbe. Aqui a alteração **endurece** o
critério, o veredito é o mesmo sob ambas as leituras, e está escrita.

---

## 7. R7 — transição, linha e adjudicação são três coisas

O diagnóstico de escala ganhou três precisões e perdeu a linguagem errada:

1. **Conta-se TRANSIÇÃO**, não linha nem célula. Entrada e saída de uma única
   célula problemática produzem **dois** sinais. "123 linhas erradas" confundia
   os três níveis.
2. **Há uma terceira classe:** bruto anterior **zero**, razão indefinida. É por
   isso que 123 + 13 não somava 137.
3. **Quatro recortes publicados lado a lado**, para que ninguém escolha o mais
   favorável depois de ver o resultado:

| Recorte | Transições | Bruto contínuo | Redenominação aparente | Indefinida | Companhias |
|---|---:|---:|---:|---:|---:|
| Painel inteiro, sucessivos | 137 | 123 | 13 | 1 | 43 |
| Painel inteiro, adjacentes | 134 | 121 | 12 | 1 | 42 |
| Universo do candidato, sucessivos | 135 | 121 | 13 | 1 | 42 |
| **Universo do candidato, adjacentes** | **132** | **119** | **12** | **1** | **41** |

**Divergência declarada com a revisão.** O recorte primário reproduz
exatamente o publicado (137/123/43), e "candidato, sucessivos" também
(135/121/42). Os dois recortes de **adjacência** diferem em **1** dos números do
parecer (que traz 135/122/43 e 133/120/42). Caracterizei a causa sem forçar
coincidência: das 137 transições, **134 distam um trimestre** e três não — a
distâncias **−3, +3 e +6**. A de **−3 anda para trás** quando ordenada por
`dt_refer`: um documento de trimestre anterior que chegou depois. Qual convenção
de adjacência é a certa é questão em aberto; como é **diagnóstico** e não decide
gate nenhum, publico as duas leituras em vez de escolher.

**Nada disto é adjudicação.** Continuidade do bruto é **suspeita**, não prova de
qual valor corrigir — a função não lê uma segunda demonstração caso a caso. A
palavra "aparentemente" na classe de redenominação é obrigatória.

---

## 8. Um defeito meu, achado ao reescrever

A primeira reescrita de `diagnosticar_escala` devolveu **2 transições** onde
havia 137. Causa: ordenei a janela por `trimestre`, que é **texto** — e
`'1T2020'` vem antes de `'2T2019'`. É precisamente a armadilha que o docstring
de `ordinal_trimestre` documenta (*"ordenar `trimestre` como texto inverte o
tempo sem levantar erro nenhum"*), e que já tinha derrubado a rota prospectiva
em 2026-08-24.

Corrigido para `dt_refer`, que é data. Registro porque o número errado teria
passado por plausível — 2 transições pareceria "quase nenhum problema", que é o
tipo de resultado que ninguém questiona.

---

## 9. Auditoria das alterações de teste

```console
$ diff <(grep -E "^\s*(assert |def test)" <snapshot>) \
       <(grep -E "^\s*(assert |def test)" tests/...) | grep "^<"
<             assert faixa["valor_minimo"] != faixa["valor_maximo"] or True
<         assert descarte["q1_nao_e_o_primeiro_apos_D"] > 0
```

**Duas linhas, as duas declaradas no contrato:**

- a **tautologia** (M1), substituída por verificação real — o bloco empatado de
  400 linhas tem de caber inteiro numa faixa. A asserção útil que vinha depois
  dela foi **preservada**.
- o **nome** do motivo de descarte, que R2.1 renomeou de
  `q1_nao_e_o_primeiro_apos_D` para `rotulo_incompleto_em_q_de_D`. A asserção é
  a mesma.

**Nenhuma asserção enfraquecida.** Os oito casos que o contrato previu como
não-regressão passaram sem alteração, incluindo
`test_quatro_trimestres_negativos_marcam_o_evento`, que eu havia marcado como
"risco".

---

## 10. Condições de falsificação — todas negativas

| # | Condição | Resultado |
|---|---|---|
| 1 | G0 passa a aprovar | ❌ — segue `REPROVADO EM G0` |
| 2 | `g0_2` deixa de ser 25, ou `g0_3` muda fora da correção declarada | ❌ — `g0_2 = 25`; `g0_3` 136→132 pela emenda do §6 |
| 3 | Observação real removida | ❌ — nenhuma; inventário **completo** publicado |
| 4 | Limiar alterado | ❌ — os dez conferidos por teste |
| 5 | Asserção enfraquecida fora do declarado | ❌ — só as duas do §9 |
| 6 | T1/T2/baselines medidos no painel real | ❌ — a cadeia publicada tem só `G0` |
| 7 | Hash de painel muda | ❌ — `43e31d9f…` e `c1a60445…` intactos |

---

## 11. Rastreabilidade

Snapshot durável em `artefatos/rank03b/snapshots/2026-09-12-pre-r1-r5/`, com
`SHA256SUMS.txt`. Os quatro hashes de partida **coincidem com os publicados no
§6 da revisão** — prova de que a onda partiu da versão auditada.

```text
antes                                    depois
040495f7…  scripts/auditar_rank03b_…py   afffe087b2e2d66843d2ee2e28839b83f48ce6f2cc4376303c50ac53d85951ef
004150 63…  tests/test_rank03b_…py        fcdf7be547b4c498b46dca12b006d422d53d0abe0547ce046848234bad89da68
7b59cf0b…  artefatos/rank03b/auditoria   a2ef88bea647777797d909624662bfe2761ab6ceaaaf4f5eae7f4b2e3d327ee0
fbae30cc…  pré-registro                  fbae30cc…  (INALTERADO)
43e31d9f…  cvm.duckdb                    43e31d9f…  (INALTERADO)
c1a60445…  cvm_treino.duckdb             c1a60445…  (INALTERADO)
```

Sem rede, sem API paga, sem leitura do holdout, sem escrita no painel.

### Reprodução

```bash
.venv/bin/python -m scripts.auditar_rank03b_consumo_operacional   # sai com 2
CREWAI_STORAGE_DIR="$(mktemp -d)" .venv/bin/python -m pytest -q \
  tests/test_rank03b_consumo_operacional.py::TestContratosR1aR5
```

---

## 12. O que continua aberto

1. **Os três problemas de dado** seguem sem conserto: derivação semestral
   (nove linhas de 183 dias), períodos curtos com colisão de trimestre fiscal
   (16 linhas; **15 grupos mistos**, e em **12** o `max` elege o curto), e as
   transições de escala a adjudicar. Corrigir exige o padrão do §3.3 —
   `correcoes_contabeis.csv` com procedência e guarda anti-porta-dos-fundos —,
   **caso a caso**, não por tabela automática.
2. **A derivação na camada comum** (`src/dados_estruturados.py`) produz o
   semestre rotulado trimestre: o `lag` acha o período anterior *disponível*,
   sem garantir que é o imediatamente anterior. Conserto tem consumidores
   próprios e testes próprios — não é efeito lateral desta onda.
3. **Protocolo novo antes de qualquer remedição.** O pré-registro `fbae30cc…`
   está **consumido**.
4. **A previsão sobre `fco_ttm_sobre_sd8` segue SEM TESTE** e deve ser
   transportada literalmente. Corrigir o instrumento **não** a confirma.
5. **Falta conferência independente desta onda.**
