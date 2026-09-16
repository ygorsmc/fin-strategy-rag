# Pré-registro — Rank 3-B: início de consumo operacional persistente

**Data:** 2026-09-11. **Status: CONGELADO.** Escrito e hasheado **antes** de
qualquer linha do auditor e antes de qualquer medição de T1, T2 ou baseline.

**Origem.** O Rank 3 reprovou T1 em 2026-08-27 porque `Δaccrual` é *variação* de
grandeza que reverte à média. A [auditoria de viabilidade de
2026-09-08](viabilidade_ml_dfc_2026-09-08.md) §4 propôs este substituto com
**evento definido** em vez de movimento de série contínua, e os dois
especialistas apoiaram **somente a preparação** — nenhum alvo novo foi medido
desde então.

**Nenhum número de Rank 3 é herdado.** Nem o corte de R$ 1 bilhão, nem o filtro
de lucro positivo, nem as amplitudes medidas. Este é estimando novo.

---

## 1. A previsão registrada antes de medir

Esta seção existe por causa do §3.14: naquele caso *"o pré-registro previu a
reprovação e nomeou o mecanismo antes de medir"*, e é isso que separa diagnóstico
de racionalização pós-hoc.

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

---

## 2. Alvo congelado

```text
D  = data de decisão. Só entra informação com dt_receb <= D.
q1 = primeiro trimestre fiscal cujo INÍCIO é posterior a D
q2, q3, q4 = os três trimestres fiscais seguintes a q1

S1 = FCO(q1) + FCO(q2)
S2 = FCO(q3) + FCO(q4)

Y = 1  se  S1 < 0  E  S2 < 0
Y = 0  se  ambos S1 e S2 existem e a condição não se cumpre
Y = indefinido (observação DESCARTADA) se qualquer um dos quatro FCO falta
```

**Elegibilidade, congelada:**

1. `FCO_TTM` conhecido em `D` **> 0` — a pergunta é sobre *início* de consumo,
   não sobre quem já consome.
2. Companhia **não financeira** (critério estrutural no §3).
3. Os quatro trimestres `q1..q4` existem como **trimestre isolado** no painel.
4. `ativo_total` conhecido em `D` e **> 0**.

**Unidade de observação:** par (companhia, `D`). **Unidade de agrupamento para
toda inferência: companhia.** Trimestres do mesmo emissor não são réplicas
independentes (§4.4 regra 8) — todo bootstrap e todo intervalo reamostra
**companhias inteiras**.

**Os dois blocos S1 e S2 não se sobrepõem**, de propósito: `Y` exige consumo em
dois semestres distintos, o que é a diferença entre "um trimestre ruim" e
"passou a consumir caixa".

**Uso pretendido, declarado:** orientar investigação de recebíveis, estoques,
fornecedores e fontes de financiamento. **O evento NÃO significa** fraude,
insolvência, deterioração economicamente material nem recomendação de
investimento (RN05/RN07). Caixa ligeiramente negativo e consumo por crescimento
exigem interpretação distinta e o alvo não os separa.

---

## 3. População — e o bloqueio de setor, declarado antes de medir

**"Não financeira" NÃO pode ser resolvido por setor neste painel.** Medido no
schema antes de escrever isto: `companhias.setor` está preenchido em **5 de
741**, e o `cad_cia_aberta.csv` que o §3.7 nomeou como solução **nunca foi
baixado** — não está em disco. Usar `is_banco` também está fora: é o recorte
**retratado em 2026-08-25**, contaminado por *private equity*, holdings e uma
companhia em liquidação.

**Critério estrutural adotado:** exclui-se a companhia cujo `plano_contas`
comece por `ll3_09_`, que é o plano de contas de instituição financeira da CVM.
Medido no schema: as 36 companhias em planos `ll3_09_*` têm `is_banco = True`
**sem exceção**, e o plano principal (`ll3_11_d55d74d8`, 688 companhias) não tem
**nenhuma**.

**Por que isto sobrevive à retratação do `is_banco`:** aqui ele é usado para
**excluir**, não para selecionar. A contaminação do `is_banco` era
*super-inclusão* — entidades financeiras não bancárias marcadas como banco. Para
"não financeira", super-incluir na exclusão é **conservador**: perde-se algumas
companhias, não se contamina a população. Por isso a exclusão é a união dos dois
critérios:

```text
EXCLUI  se  plano_contas LIKE 'll3_09_%'  OU  is_banco = TRUE
```

**Limitação registrada:** sem `SETOR_ATIV`, **não há controle setorial** e não
haverá. Qualquer afirmação sobre heterogeneidade entre setores está fora do
escopo deste pré-registro. Baixar o `cad_cia_aberta.csv` e refazer é trabalho
de outra onda — e **não** se ajusta a população depois de ver o resultado.

**Painel:** `artefatos/cvm_treino.duckdb`, aberto **somente leitura**. O painel
consultável (`cvm.duckdb`) não é tocado (§3.5).

---

## 4. G0 — integridade, decisivo, antes de qualquer T1

Reprova a rodada inteira, não é diagnóstico. Cada item vem de defeito **já
medido** neste projeto, não de precaução genérica:

| # | Verificação | Origem do risco | Limiar |
|---|---|---|---|
| G0.1 | Nenhuma observação usa `DFC_MD` e `DFC_MI` para o mesmo (companhia, trimestre) | §3.13: a sobreposição **não é vazia** (5 companhia–trimestres); somar os dois duplica o caixa | 0 casos somados |
| G0.2 | Nenhum FCO "trimestral" cobre intervalo diferente de ~1 trimestre | Auditoria de 2026-09-08 achou **fluxos semestrais rotulados trimestrais** | 0 fora de 80–100 dias |
| G0.3 | Escala coerente: nenhum salto de `ativo_total` por fator ≥ 100 entre trimestres adjacentes | §3.11: 23 linhas com saltos ~1.000× explicavam **61,64%** do erro do CAND-04, por troca `MIL`↔`UNIDADE` | ≤ 0,5% das observações |
| G0.4 | `valor_reais` nunca nulo nas contas usadas | §3.13: 4 linhas de 2014 com `DS_CONTA` vazio entram com marcador | 0 nulos |

**As observações que G0.3 reprovar NÃO são removidas para salvar o teste**
(§4.4 regra 9). Se aparecerem, a rodada é **invalidada**, a quarentena é
publicada e congelada, e um teste novo é outro pré-registro.

## 5. G1 — point-in-time, decisivo

| # | Verificação | Limiar |
|---|---|---|
| G1.1 | Toda feature usada tem `dt_receb <= D` | 100% |
| G1.2 | `q1` é **exatamente** o primeiro trimestre fiscal iniciado após `D` | 100% |
| G1.3 | Nenhum dos quatro trimestres do rótulo tem início anterior a `D` | 100% |

G1.2 vem do achado C3 do B-DFC-01J: *"começa depois de D"* **não é** o horizonte
contratual; aceitar qualquer trimestre posterior deixou 18 de 18 pares com o
alvo já iniciado. G1 aqui é **decisivo**, não diagnóstico — um painel que se diz
point-in-time e não é seria pior que nenhum (§3.13).

---

## 6. T1 — os componentes, nomeados antes de medir

**Limiar: amplitude da taxa de evento entre quintis < 0,15 para TODOS.** Um só
acima reprova, e **T2 favorável não resgata T1 reprovado** (§4.4).

A regra manda auditar *cada componente que define mecanicamente o alvo* —
inclusive nível, volatilidade e qualquer normalizador. Para `Y = [S1<0 ∧ S2<0]`:

| # | Componente | Por que é mecânico |
|---|---|---|
| T1.1 | **`fco_ttm_sobre_sd8`** | Distância até zero em desvios do próprio FCO. **É o suspeito nomeado no §1.** |
| T1.2 | `fco_ttm_em_D` (reais) | O nível cuja mudança de sinal É o evento |
| T1.3 | `fco_ttm_sobre_ativo` | O mesmo nível, normalizado por escala |
| T1.4 | `sd8_fco_isolado` | Volatilidade própria: mais dispersão ⇒ atravessa zero mais fácil, com a mesma média. É a lição do C1, onde o `sd8` do corte fabricava o baseline |
| T1.5 | `ativo_total_em_D` | Escala. Entra porque corte absoluto nunca é escala-livre (§3.7) |
| T1.6 | `trimestres_com_fco_negativo_nos_ultimos_8` | Persistência histórica do mesmo sinal que o alvo mede |

**Nenhum componente pode ser retirado desta lista depois de medido.** Acrescentar
é permitido (mais auditoria é mais conservador); retirar, não.

**Amostra mínima para T1: 500 observações e 30 companhias.** Abaixo disso o
auditor **levanta exceção** e a rodada fica em *reprova em aberto* — nunca vira
aprovação (§4.4 regra 4; foi exatamente o defeito `NaN >= 0,15 → False` do
Rank 3).

### A regra do viés da amplitude, fixada antes de ver o número

`amplitude = max − min` sobre cinco quintis é **enviesada para cima** (§3.16 /
§4.4). Por isso, congelado agora:

- Componente **≥ 0,15** → **REPROVA**. Sem apelação por viés: o viés é para
  cima, então uma reprovação com folga é conservadora.
- Componente em **[0,12; 0,15)** → bootstrap por companhia (2.000 reamostragens).
  Se P(amplitude verdadeira > 0,15) **> 10%**, o veredito é **INDECIDÍVEL**, não
  aprovado. É a lição da Etapa 19, onde 32% de chance foi lida corretamente como
  "não aprovou".
- Componente **< 0,12** → passa.

---

## 7. T2 — sinal temporal, não ordenação de emissor

**Lacuna = AUC agregada − AUC intra-companhia < 0,12.**

**Escore constante não pode "passar" T2 por ter lacuna zero** — levanta exceção.
Foi o defeito do próprio instrumento do B-DFC-01J: T2 aprovava por **ausência**
de poder discriminante, porque B0 é escore constante e dá AUC 0,5 por construção.

A AUC intra-companhia exige companhias com os dois rótulos; as que têm um só
saem da conta **e o número delas é publicado** ao lado.

---

## 8. Baselines triviais — construídos ANTES de qualquer modelo

§4.4 regra 2, que já custou um 205-a-1. **Nenhum componente aprendido é
executado nesta onda.** O que esta rodada mede é se o alvo sobrevive a T1/T2 e
o que os triviais entregam.

| Baseline | Regra |
|---|---|
| **B0** | Classe majoritária (prever sempre "não vai consumir"). Publica acerto **e cobertura** |
| **B1** | Ordenar por `fco_ttm_sobre_sd8` crescente — o suspeito do T1 como ranqueador |
| **B2** | Ordenar por `trimestres_com_fco_negativo_nos_ultimos_8` decrescente |
| **B3** | Ordenar por `fco_ttm_sobre_ativo` crescente |

Cada um publica AUC agregada, AUC intra-companhia e precisão no top-10%, com IC
95% por bootstrap **agrupado por companhia**.

**Condição de aprovação para algum dia treinar um modelo:** G0 e G1 aprovados,
todos os seis componentes de T1 abaixo de 0,15, T2 abaixo de 0,12, **e** o
desafiante superando o **melhor** dos quatro triviais por margem cujo IC 95%
pareado exclua zero. **Sem os quatro triviais medidos, nenhum modelo é
autorizado** — e nada nesta onda autoriza treino.

---

## 9. Vocabulário de veredito

| Veredito | Quando |
|---|---|
| **REJEITADO** | Algum componente de T1 ≥ 0,15, ou T2 ≥ 0,12 |
| **REPROVADO EM G0/G1** | Integridade ou point-in-time falham. Decisivo, e T1/T2 não resgatam |
| **INDECIDÍVEL** | Amostra insuficiente, ou componente na zona [0,12; 0,15) com P(>0,15) > 10% |
| **PRONTO PARA CHALLENGER** | Tudo acima passa. **Não é** "modelo aprovado": é permissão para medir um |

---

## 10. O que esta onda NÃO fará

1. **Nenhum modelo carregado.** Sem `sklearn`, sem boosting, sem challenger.
2. **Nenhuma escrita no painel.** `cvm_treino.duckdb` aberto somente leitura;
   `cvm.duckdb` não tocado.
3. **Nenhum acesso a `corpus/holdout_2T2026`.**
4. **Nenhuma chamada de rede ou API paga.** Custo zero: o painel está em disco.
5. **Nenhum ajuste de população, limiar ou lista de componentes depois de medir.**
6. **Nenhum controle setorial** — impossível neste painel, declarado no §3.

## 11. Condições de falsificação desta rodada

A execução está **errada**, independentemente do veredito, se:

1. A lista de componentes de T1 medida diferir da do §6.
2. Qualquer limiar (0,15 · 0,12 · 500 · 30 · 10%) diferir dos fixados aqui.
3. A população for filtrada por critério não declarado no §3.
4. Alguma observação reprovada em G0.3 for silenciosamente removida.
5. O bootstrap reamostrar observações em vez de companhias.
6. O veredito for "aprovado" com algum gate decisivo reprovado.
7. Qualquer hash de painel mudar entre o início e o fim da execução.

---

## 12. Artefatos desta rodada

| | |
|---|---|
| Auditor | `scripts/auditar_rank03b_consumo_operacional.py` |
| Testes | `tests/test_rank03b_consumo_operacional.py` |
| Artefato | `artefatos/rank03b/auditoria.json` |
| Relatório | `resultados/validacao_rank03b_consumo_operacional_2026-09-11.md` |

**Este documento é o contrato.** Divergência entre ele e o auditor é defeito do
auditor, nunca licença para reinterpretar o contrato.
