# Contratos de correção do instrumento do Rank 3-B — R1 a R5

**Data:** 2026-09-12. **Escritos ANTES de qualquer alteração de código**, pelo
rito já usado em C1–C6 e R-C5/R-C6: a política é escolhida e registrada
primeiro, para que nenhuma decisão seja tomada olhando o resultado medido.

**Origem:** [revisão independente de 12/09](revisao_rank03b_consumo_operacional_2026-09-12.md),
achados R1–R5 (implementação), R6–R7 (descrição dos números).

**Os sete achados foram reproduzidos pela sessão principal antes de virar
contrato**, com os blocos executáveis do §5 do parecer. Saídas idênticas às
publicadas: `132 adjacentes / 22.428 = 0,58855%`; quatro pares não adjacentes;
durações `16 curtas + 9 semestrais`; 15 grupos mistos com `{12, 31, 41}` dias e
`max` elegendo o anômalo em 12; 4 grupos de FCO e 26 de ativo com
disponibilidade antecipada; `q1=4T2019` com `3T2019` ausente; empate total
devolvendo precisão 1,0 e lift 10,0; T1 aprovando componente com 570
observações de **uma** companhia; e os três estados errados do orquestrador.

**Estado de partida, conferido contra o §6 do parecer.** Os quatro SHA-256
coincidem. Cópia durável em
`artefatos/rank03b/snapshots/2026-09-12-pre-r1-r5/` com `SHA256SUMS.txt`.

---

## Natureza desta onda, e o que ela NÃO é

**Esta onda corrige o INSTRUMENTO para que ele implemente fielmente o contrato
já congelado. Ela não remede o alvo, não altera limiar nenhum e não cria
critério novo.**

O pré-registro `fbae30cc…` está **consumido**: o item 4 do §7 do parecer exige
protocolo novo antes de qualquer remedição. Portanto:

- Nenhum limiar muda (0,15 · 0,12 · 500 · 30 · 10% · 80–100 dias · fator 100).
- Nenhum gate novo é criado. G0.1–G0.4 seguem sendo os quatro do §4.
- **O veredito tem de continuar `REPROVADO EM G0`.** Se alguma correção fizer
  G0 passar, a correção está errada — é sinal de que removi observação para
  salvar o teste, o que o §4.4 regra 9 proíbe.
- Nenhuma observação real é removida do painel ou da auditoria.

---

## R1 — a observação passa a ser uma LINHA, não uma combinação de agregações

### Defeito

`carregar_fco` e `carregar_ativo` agrupam por `(cd_cvm, trimestre)` e tomam
`max(valor_reais)`, `min(dt_receb)`, `min(dt_ini_exerc)` e `max(dt_fim_exerc)`
**independentemente**. Os quatro atributos podem vir de linhas diferentes.

Medido: **4 grupos de FCO e 26 de ativo** recebem data anterior à chegada da
linha que de fato contém o valor. Em `023507/1T2015`, o valor `+19.075.000`
(período 01/01–31/03/2015, recebido em 05/05/2015) sai com disponibilidade
**21/10/2014**, herdada de outra linha rotulada com o mesmo trimestre mas
cobrindo 10/04–30/06/2014. As duas linhas duram 82 e 90 dias e **passam** em
G0.2 — corrigir as 25 durações anômalas não elimina este defeito.

### Contrato

**R1.1 — o carregador devolve LINHAS, não grupos.** `carregar_fco` e
`carregar_ativo` passam a devolver uma entrada por linha-fonte, cada uma com
seu próprio `valor`, `dt_ini`, `dt_fim`, `dt_receb`, `demonstrativo`, `origem`
e `versao`. Nenhum atributo é agregado.

**R1.2 — a escolha do vintage é feita em D, não na carga.** Para cada decisão
`D`, entre as linhas do mesmo `(cd_cvm, trimestre)` com `dt_receb <= D`,
escolhe-se **a de `dt_receb` mais recente** — que é a informação vigente em `D`.
Mover a seleção da carga para o momento da decisão é o que torna a escolha
point-in-time em vez de retroativa.

**R1.3 — desempate determinístico e cego ao desfecho.** Empate de `dt_receb`
resolve-se por, nesta ordem: maior `versao`, depois `demonstrativo` em ordem
alfabética, depois `dt_ini`. Nenhum critério olha o valor nem o rótulo.

**R1.4 — o conflito é publicado, não silenciado.** Grupos cujas linhas
candidatas discordam do valor são contados e publicados no artefato.

### Alternativas rejeitadas, registradas antes de medir

| Alternativa | Por que não |
|---|---|
| Escolher a linha de `dt_receb` mais antiga na carga | No caso `023507` isso elege justamente a linha **mal rotulada** de 2014. Primeira aparição não é identidade correta. |
| Escolher a maior `versao` na carga | É leitura *as-restated*: usa em `D` uma versão que só existiu depois. Troca um vazamento por outro. |
| Filtrar na carga as linhas de duração anômala | **Remover observação para salvar o teste.** G0 precisa continuar enxergando-as e reprovando. |
| Manter o `max(valor_reais)` e só corrigir a data | O defeito é de identidade, não de data: o valor eleito pode ser de um período que não é o rotulado. |

### Critérios de aceitação

1. Nenhum grupo produz observação cuja `dt_receb` seja anterior à recepção da
   linha que contém o valor usado — reexecução do bloco §5.1 devolve **0 e 0**,
   onde hoje devolve 4 e 26.
2. Valor, período e data de toda observação vêm da **mesma** linha-fonte.
3. Não-regressão: `G0` segue reprovado, com `g0_2 = 25` e `g0_3` inalterado.

---

## R2 — horizonte q(D) pelo calendário e janelas contíguas

### Defeito

Três, no mesmo lugar:

1. O código confere se os quatro períodos **encontrados** são consecutivos, não
   se começam em **q(D)**. Removendo `3T2019`, para `D = 10/05/2019` ele aceita
   `q1 = 4T2019`. O contrato exige `3T2019`; a ausência pede **censura**, não
   deslocamento do horizonte.
2. `passado[-4:]` soma quatro linhas sem exigir contiguidade fiscal. Removendo
   `4T2018`, o "TTM" aceito soma `2T2018 + 3T2018 + 1T2019 + 2T2019` — quatro
   linhas num vão de cinco trimestres. O mesmo vale para `passado[-JANELA_SD:]`.
3. `G1` decide por `aprovado = bool(amostra)`: não verifica nada.

Além disso: duas linhas com a mesma recepção geram **duas** observações para a
mesma chave `(companhia, D)`, que é a unidade declarada; e
`len(passado) < JANELA_SD + 1` exige **nove** antecedentes para componentes que
usam oito, exigência que não consta da elegibilidade registrada.

### Contrato

**R2.1 — q(D) vem do calendário.** `primeiro_trimestre_apos(D)` calcula o
primeiro trimestre fiscal cujo início é posterior a `D`, **independentemente de
haver dado**. O rótulo exige exatamente `q(D), q(D)+1, q(D)+2, q(D)+3`, por
ordinal. Faltando qualquer um, a observação é **descartada com motivo** — nunca
substituída pelo trimestre seguinte disponível.

**R2.2 — janelas passadas contíguas.** A janela de 4 e a de `JANELA_SD` exigem
ordinais consecutivos terminando na âncora. Lacuna descarta a observação.

**R2.3 — `JANELA_SD` antecedentes, não `JANELA_SD + 1`.** O corte passa a ser
o que os componentes de fato usam, e fica declarado no artefato.

**R2.4 — uma observação por `(companhia, D)`.** Chave única, verificada.

**R2.5 — G1 verifica.** Passa a conferir explicitamente horizonte exato,
contiguidade das janelas, unicidade da chave e disponibilidade em `D`,
publicando cada contagem — em vez de `bool(amostra)`.

### Alternativas rejeitadas

| Alternativa | Por que não |
|---|---|
| Aceitar o primeiro trimestre existente após D | É o defeito. Desloca o horizonte contratual em silêncio e muda o estimando. |
| Preencher a lacuna por interpolação | Inventa fluxo de caixa que a companhia não publicou. |
| Manter `bool(amostra)` e confiar na construção | Foi exatamente assim que o horizonte errado passou sem sinal. Gate que não verifica não é gate. |

### Critérios de aceitação

1. Removendo `3T2019`, `D = 10/05/2019` **não produz observação** (hoje produz
   com `q1 = 4T2019`).
2. Removendo `4T2018`, `D = 09/08/2019` não produz observação.
3. `q(D)` correto nas bordas de trimestre, incluindo 31/12 e 01/01.
4. Duas linhas com a mesma `dt_receb` produzem **uma** observação.
5. Não-regressão: série completa e regular continua produzindo observações.

---

## R3 — o ranking não pode desempatar pelo rótulo

### Defeito

```python
ordenados = sorted(zip(escores, alvos), reverse=True)
```

Com empate no escore, a tupla ordena por `y` decrescente: os positivos vão para
a frente **usando a resposta que o baseline deveria desconhecer**. Medido: 100
observações com escore constante e 10 positivos devolvem precisão no top-10% de
**1,0** e lift **10,0**, com AUC 0,5. Atinge principalmente B2, que tem escore
discreto.

### Contrato

**R3.1 — ordenação cega ao desfecho.** A chave de ordenação é o escore e um
índice estável. O rótulo **nunca** participa.

**R3.2 — empate no corte resolve-se pelo valor esperado.** Quando um grupo de
empate atravessa o corte do top-k, a precisão publicada é a **esperada sob
desempate aleatório** — a média do grupo, ponderada pela fração que entra. Isso
elimina ao mesmo tempo o vazamento e a arbitrariedade de qual metade entra.

**R3.3 — o empate é publicado.** `empates_no_corte` e a cobertura efetiva saem
no artefato, para que ninguém leia uma precisão de grupo empatado como
discriminação.

### Alternativas rejeitadas

| Alternativa | Por que não |
|---|---|
| Desempatar por semente aleatória | Não demonstra invariância, só a esconde atrás de uma semente — mesma razão que rejeitou essa via no contrato C1. |
| Desempatar pelo `cd_cvm` | Cego ao rótulo, mas arbitrário: favorece sistematicamente companhias de código menor. |
| Manter a ordem e só avisar | O número publicado continuaria errado. Aviso não conserta métrica. |

### Critérios de aceitação

1. Escore constante com taxa-base `p` devolve precisão no top-10% **igual a
   `p`**, não 1,0, e lift **1,0**, não 10,0.
2. Escore perfeitamente discriminante continua com precisão 1,0 — a correção
   não pode achatar sinal real.
3. Inverter a ordem das linhas de entrada não muda nenhuma métrica.

---

## R4 — a decisão passa a respeitar os estados de T1 e dos baselines

### Defeito

| Condição | Hoje | Contrato |
|---|---|---|
| T1 levanta insuficiência; T2 passa | `REJEITADO` | `INDECIDÍVEL` |
| T1 na zona cinzenta inconclusiva; T2 passa | `REJEITADO` | `INDECIDÍVEL` |
| Gates e T1/T2 passam; `medir_baselines` falha | **`PRONTO PARA CHALLENGER`** | não autorizar |

A condição `indecidivel and t1["aprovado"]` nunca se satisfaz nos dois primeiros
casos, porque T1 não está aprovado justamente por ser inconclusivo. E a falha de
baselines vira `reprova_em_aberto` **sem entrar na conjunção de aprovação**.

**O terceiro é o mais grave, e é o achado F10 pela quarta vez neste projeto:**
exigência que existe como texto e não participa da condição de aprovação. O
§4.4 regra 7 foi escrita um dia antes deste auditor.

Além disso, `medir_baselines` **não implementa** o IC95% por companhia nem a AUC
intra por baseline que o §8 exige; B0 publica cobertura de direção zero sem
distinguir abstenção de ranqueamento de ausência de previsão de classe; e
`if auc` serializa **AUC zero como `None`**.

### Contrato

**R4.1 — três estados distintos, nunca fundidos.** Reprovação **numérica**
(amplitude ≥ limiar), **insuficiência** (amostra) e **falha de instrumentação**
(baseline não medido) produzem vereditos diferentes. Só a primeira é
`REJEITADO`.

**R4.2 — completude dos baselines entra na conjunção.** `PRONTO PARA
CHALLENGER` exige os quatro triviais **medidos e válidos**. Baseline ausente
bloqueia, como B3 bloqueia no B-DFC-01J.

**R4.3 — as métricas do §8 passam a existir:** IC95% por bootstrap **agrupado
por companhia** e AUC intra-companhia, por baseline.

**R4.4 — B0 publica as duas coberturas.** Cobertura de **ranqueamento** zero
(abstém) e cobertura de **previsão de classe** integral, com os nomes dizendo
qual é qual.

**R4.5 — `None` só quando não há medida.** `if auc is not None`, para que AUC
zero seja publicada como zero.

### Critérios de aceitação

A contraprova exercita **a decisão**, nos três estados, com o consumidor
isolado:

1. T1 insuficiente + T2 passa → `INDECIDIVEL`.
2. T1 zona cinzenta + T2 passa → `INDECIDIVEL`.
3. T1 reprovado numericamente → `REJEITADO` (a correção não pode apagar a
   rejeição legítima).
4. Tudo passa + baseline falho → **não** `PRONTO PARA CHALLENGER`.
5. Tudo passa + baselines completos → `PRONTO PARA CHALLENGER` — sem este caso,
   um literal `False` passaria nos quatro anteriores.
6. AUC zero sai como `0.0`, não `None`.

---

## R5 — o mínimo de companhias vale sobre o suporte EFETIVO

### Defeito

O mínimo de 30 companhias é conferido na amostra global. Cada componente depois
descarta seus `None` e **não reconta**. Medido: com 600 observações e 31
companhias, `fco_ttm_sobre_sd8` disponível em 570 observações de **uma única
companhia** é **aprovado** por T1.

### Contrato

**R5.1** — cada componente reconta observações **e companhias** depois dos
filtros de disponibilidade, e o mínimo registrado se aplica ao suporte efetivo.

**R5.2** — abaixo do mínimo, o componente é **insuficiente** (não aprovado, não
reprovado), e T1 sai `INDECIDIVEL` por R4.1.

**R5.3** — o suporte efetivo de cada componente e de cada baseline é publicado.

**Isto não aumenta nenhum mínimo** — aplica o mínimo já registrado aos dados que
realmente entram na estatística.

### Critérios de aceitação

1. Componente com 570 observações de 1 companhia **não é aprovado**.
2. Componente com suporte pleno continua sendo avaliado normalmente.
3. `observacoes_usadas` e `companhias_usadas` saem no artefato por componente.

---

## Correções menores, no mesmo lote

**M1 — tautologia.** `assert faixa["valor_minimo"] != faixa["valor_maximo"] or
True` (linha 87 do arquivo de testes) é sempre verdadeira. Substituída por
asserção real; a asserção útil que vem depois dela é **preservada**.

**M2 — determinismo da quarentena.** `carregar_duracoes` não tem `ORDER BY`, e
`[:10]` publica subconjuntos diferentes a cada execução. Passa a ordenar, e a
quarentena publica o **inventário completo e identificável**, não dez exemplos —
que é a exigência do §7 item 2 do parecer.

---

## Impacto previsto nos testes, declarado antes de rodar

| Teste | Previsão | Natureza |
|---|---|---|
| `test_o_rotulo_nunca_comeca_antes_de_D` | passa sem alteração | não-regressão |
| `test_antecedente_publicado_depois_de_D_nao_entra` | passa sem alteração | não-regressão |
| `test_rotulo_com_trimestre_faltando_e_descartado` | passa; motivo de descarte pode mudar de nome | ajuste de nome |
| `test_um_semestre_negativo_sozinho_nao_marca_o_evento` | passa | não-regressão |
| `test_quatro_trimestres_negativos_marcam_o_evento` | **risco**: R2.2 exige janela contígua e o fixture pode não tê-la | ajuste de fixture, nunca da asserção |
| `test_elegibilidade_exige_fco_ttm_positivo` | passa | não-regressão |
| `TestGateG0` (6 casos) | passam; assinaturas podem mudar | ajuste de chamada |
| `test_empates_nao_sao_divididos_entre_quintis` | **substituição declarada** da linha 87 (M1) | substituição |
| `TestVeredito` (2 casos) | passam | não-regressão |

Qualquer quebra fora desta lista é achado, não conserto.

---

## Condições de falsificação desta onda

A onda está **errada** se qualquer uma se verificar:

1. **G0 passa a aprovar.** O veredito tem de continuar `REPROVADO EM G0`.
2. `g0_2` deixa de ser 25, ou `g0_3` muda, sem que a mudança seja a correção de
   adjacência declarada em R6 (que é outra onda, não esta).
3. Alguma observação real é removida do painel ou da auditoria.
4. Algum limiar do pré-registro muda.
5. Alguma asserção é enfraquecida fora da substituição declarada em M1.
6. T1, T2 ou baselines passam a ser medidos sobre o painel real — esta onda
   **não remede o alvo**.
7. Qualquer hash de painel muda.
