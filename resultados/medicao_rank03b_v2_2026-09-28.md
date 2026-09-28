# Rank 3-B: medição do pré-registro v2 — REJEITADO

**Data:** 2026-09-28.
**Pré-registro:** `resultados/pre_registro_rank03b_v2_2026-09-16.md`, SHA-256
`8fdbd145b614628392fc1e53433c73a552eed5d2d250f54e46ecf4592e1660b2`, congelado
e publicado no commit `fcbb26d` antes da medição.
**Artefato:** `artefatos/executor_v2_rank03b/medicao.json`, com os seis pins
conferidos pela trava do congelamento.
**Comando:** o da seção 4 da
[revisão até o treino](revisao_caminho_ate_treino_rank03b_2026-09-27.md),
executado uma vez.

## Em uma tela

**Veredito: REJEITADO, por T1 e por T2.** Não há treino nem protocolo do
desafiante (D8). Pelo §1 do pré-registro, não há terceira tentativa no mesmo
formato.

- **T2 reprova com folga, e é o que decide.** A lacuna é **0,207**: AUC
  agregada de 0,758 contra 0,551 dentro da companhia. O IC 95% vai de 0,167 a
  0,250, e 100% das 2.000 reamostragens ficam acima de 0,12. São 174
  companhias com os dois rótulos, para um piso de 30.
- **T1 reprova raspando, por outro componente que o previsto.**
  `trimestres_com_fco_negativo_nos_ultimos_8` tem amplitude **0,1555**, para
  um limiar de 0,15. `fco_ttm_sobre_sd8` fica em **0,1259**, na zona cinzenta,
  com frequência bootstrap de 1,95%, e passa.
- **Os gates foram medidos de novo, sem rótulo:** G0.3 com 95 saltos, G0.5 e
  G1 sem violação, 10.168 observações em 495 companhias, como no estrutural.
  O rótulo foi somado sobre as mesmas chaves (companhia, D), conferidas pelo
  executor. A taxa do evento é **0,0518**.

## 1. A previsão do §1, conferida

| Parte da previsão | Resultado |
|---|---|
| Veredito REJEITADO | **Acertou** |
| Reprovação por T1 | **Acertou, por margem mínima**: 0,0055 acima do limiar, numa estatística com viés para cima. A regra congelada não tem bootstrap para reprovação, e o veredito não depende dessa margem, porque o T2 rejeita sozinho |
| Reprovação por `fco_ttm_sobre_sd8` | **Errou.** Quem reprova é o histórico de trimestres negativos |

**O §1.1 se aplica, e foi escrito para este caso.** `fco_ttm_sobre_sd8`
ordena o evento de forma monotônica, com taxa de 13,1% no quintil mais perto
de zero e de 0,5% no mais longe: 27 vezes entre os extremos e 2,5 vezes a
taxa-base. O mecanismo do §1 está presente. Com taxa-base de 5%, a amplitude
absoluta não chega a 0,15. **Por isso não se publica que a regra do §4.4
precisa ser corrigida.** A leitura foi fixada antes de medir.

## 2. T1

Razão descritiva do §1.1, que não decide nada: maior taxa por quintil
dividida pela taxa-base (0,0518).

| Componente | Amplitude | Taxas por quintil | Maior ÷ base | Veredito |
|---|---:|---|---:|---|
| `trimestres_com_fco_negativo_nos_ultimos_8` | **0,1555** | 0,008 · 0,036 · 0,056 · 0,087 · 0,164 | 3,16 | **REPROVA** |
| `fco_ttm_sobre_sd8` | 0,1259 | 0,131 · 0,067 · 0,038 · 0,018 · 0,005 | 2,53 | passa (zona cinzenta; IC 0,102–0,149; frequência 1,95%) |
| `fco_ttm_em_D` | 0,1063 | 0,118 · 0,070 · 0,032 · 0,027 · 0,012 | 2,28 | passa |
| `fco_ttm_sobre_ativo` | 0,0945 | 0,120 · 0,046 · 0,030 · 0,026 · 0,038 | 2,32 | passa |
| `ativo_total_em_D` | 0,0723 | 0,094 · 0,061 · 0,051 · 0,032 · 0,022 | 1,81 | passa |
| `sd8_fco_isolado` | 0,0458 | 0,075 · 0,069 · 0,046 · 0,039 · 0,030 | 1,45 | passa |

Todos os componentes usam as 10.168 observações e as 495 companhias. O
componente discreto teve cinco faixas desiguais (3.453, 2.176, 2.030, 1.350
e 1.159), pela partição com empates do §7. A regra 3 do §5.5 não tornou
ausente nenhuma `fco_ttm_sobre_ativo`.

## 3. T2

| | Valor |
|---|---:|
| Escore | B1, `fco_ttm_sobre_sd8`, sentido negativo |
| AUC agregada | 0,758 |
| AUC intra-companhia (média de 174 companhias) | 0,551 |
| **Lacuna** | **0,207** (IC 95%: 0,167–0,250) |
| Frequência de reamostragens com lacuna ≥ 0,12 | 1,00 (2.000 válidas) |
| Observações nas 174 companhias | 3.978 |

## 4. Baselines

Todos estão completos. O melhor trivial, pela AUC agregada, é o B1.

| Baseline | AUC agregada | AUC intra | Precisão no top-10% | Lift |
|---|---|---|---|---:|
| B0, sempre não consumir | — | — | acerto 0,948 (0,939–0,956) | — |
| B1, `fco_ttm_sobre_sd8` | 0,758 (0,728–0,786) | 0,551 (0,509–0,593) | 0,154 (0,124–0,184) | 2,96 |
| B2, trimestres negativos | 0,754 (0,722–0,784) | 0,524 (0,486–0,561) | 0,169 (0,136–0,204) | 3,26 |
| B3, `fco_ttm_sobre_ativo` | 0,657 (0,613–0,698) | 0,546 (0,503–0,587) | 0,143 (0,110–0,172) | 2,75 |

## 5. Descartes da grade, agora completos

O motivo 11 estava retido pelo O1 até o congelamento.

| Motivo, na ordem do §6.1 | Datas |
|---|---:|
| 1. sem q1 identificável | 1.477 |
| 2. q1 repetido, mantida a maior D (868 chaves) | 921 |
| 3. histórico insuficiente | 3.626 |
| 4. trimestre do §5.5 na janela | 152 |
| 5. janela com lacuna | 475 |
| 6. janela sem encadeamento | 13 |
| 7. trimestre do §5.5 em q1–q4 | 72 |
| 8. rótulo incompleto | 1.518 |
| 9. rótulo sem encadeamento | 6 |
| 10. regra 2 do §5.5 | 16 |
| 11. `FCO_TTM ≤ 0` em D | **2.667** |
| 12. sem ativo disponível | 2 |

## 6. O que o resultado diz

**Os triviais sabem quem, não quando.** B1 e B2 separam o evento com AUC de
0,75 entre companhias. Dentro de uma companhia ficam entre 0,52 e 0,55, com
intervalos que encostam em 0,5. Como foi definido, o "início de consumo
operacional persistente" é previsto por **qual** emissor vive perto de zero
ou já teve trimestres negativos, e não pelo **momento** em que começa. É a
falha de T2 do corte relativo (becos §A.1), com outra roupa.

**O resultado confirma o §4.4, regra 1, em vez de corrigi-la.** O §1
argumentava que `FCO < 0` é limiar sobre série contínua, e não evento
materialmente definido. A medição concorda. O Rank 3 tinha registrado "FCO
negativo em dois trimestres consecutivos" como a saída da armadilha. Medida,
não é saída.

## 7. O que o resultado não autoriza

- Não diz que o FCO é imprevisível, nem nada sobre modelo, porque nenhum foi
  treinado.
- Não reabre o mesmo alvo. Mudar limiar, normalizador ou horizonte cria o
  Rank 3-C, com pré-registro próprio (§1).
- A baixa sensibilidade do T1 absoluto em prevalência baixa é **achado de
  método sobre o protocolo**, e não conclusão sobre este alvo. Propor limiar
  relativo à taxa-base exige proposta própria, escrita antes do próximo alvo
  de prevalência baixa. Nada foi mudado no §4.4.

## 8. Exposição

Esta foi a primeira estatística de rótulo calculada no painel v2. Antes dela,
o que se viu está no §11 do pré-registro congelado. A razão da tabela do T1
foi calculada depois, a partir da `taxa_por_quintil` publicada, sem nova
leitura do painel.
