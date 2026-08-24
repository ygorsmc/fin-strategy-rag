# Etapa 10 — modelo preditivo: prejuízo em T+1

**Data:** 2026-08-23 · **Custo de API:** zero (DuckDB local, treino em CPU) ·
**Artefato:** `artefatos/modelo/metricas.json` · **Reprodução:**
`python -m scripts.treinar_modelo`

Pré-condição satisfeita: o gate **G4 foi aprovado em 2026-08-22**. O rótulo
depende do mapa semântico de contas, e treinar antes disso treinaria um modelo
confiantemente errado.

## Tarefa e painel

Classificação binária: *dada a posição contábil até o trimestre T, a companhia
reportará prejuízo em T+1?* Unidade amostral é companhia × trimestre; o rótulo
sai de `fatos_semanticos` pelo mapa semântico, **nunca de `cd_conta` cru**
(RN09).

- **1.699 observações**, 470 companhias, **29,9% de positivos** — bate com o
  que o gate G2 mediu em 2026-08-07 (~29%).
- **Split temporal**, nunca aleatório: treino `1T2025`+`2T2025` (873),
  validação `3T2025` (420), teste `4T2025` (406).
- **Três trimestres descartados** por estarem incompletos: `2T2026` (128
  companhias), `3T2026` (9), `1T2027` (1). O corte é relativo à mediana de
  companhias por trimestre, não um número fixo.

**Por que descartar trimestre parcial não é desperdiçar amostra.** O `2T2026`
tem **17% de prejuízo contra ~29%** dos trimestres fechados: quem declara cedo
é sistematicamente mais saudável. Admiti-lo não adicionaria amostra —
adicionaria viés de seleção com cara de amostra.

## Resultados no teste (`4T2025` → rótulo em `1T2026`)

| Modelo | Limiar | Recall | Precisão | F1 | Acurácia | ROC-AUC |
|---|---|---|---|---|---|---|
| Baseline — classe majoritária | 0,50 | 0,000 | 0,000 | 0,000 | 0,682 | — |
| Baseline — persistência ("teve prejuízo em T") | 0,50 | 0,659 | 0,644 | 0,651 | 0,776 | 0,745 |
| Regressão logística | 0,08 | **0,930** | 0,550 | **0,692** | 0,736 | **0,887** |
| Regressão logística | 0,50 | 0,566 | 0,859 | 0,682 | 0,833 | **0,887** |
| Gradient boosting | 0,01 | 0,946 | 0,427 | 0,588 | 0,579 | 0,853 |
| Gradient boosting | 0,50 | 0,543 | 0,805 | 0,648 | 0,813 | 0,853 |

**Com as features do O-score (2026-08-23, segunda iteração), a logística passou
a bater a persistência em F1 também** (0,692 contra 0,651), não só em recall e
AUC. Restam abaixo a acurácia (0,736 contra 0,776) e a precisão naquele limiar.
A tabela anterior, sem essas features, marcava F1 0,583 — **abaixo** do
baseline.

O limiar de 0,08 / 0,01 saiu da **validação**, maximizando F2 — que pondera
recall com o dobro do peso da precisão, tradução declarada da preferência da
spec 5.10 (deixar de sinalizar deterioração custa mais que um falso alarme
descartado em cinco minutos). O limiar **nunca** foi escolhido olhando o teste.

## O modelo agrega? Sim — e a prova honesta não é o recall

**Comparar "recall 0,930 contra 0,659" seria enviesado**: o modelo comprou
recall baixando o limiar. A comparação maçã com maçã é a precisão **no mesmo
recall da persistência**:

| | Recall | Precisão |
|---|---|---|
| Persistência | 0,659 | 0,644 |
| Regressão logística | 0,659 | **0,802** |
| Gradient boosting | 0,659 | 0,708 |

Detectando exatamente tanto quanto a regra simples, a logística erra o alarme
**bem menos** (0,802 contra 0,644). Somado ao ROC-AUC (0,887 e 0,853 contra
0,745), que é livre de limiar, a conclusão é que o modelo **ordena melhor** —
que é precisamente o uso declarado na 5.10: ordenar centenas de companhias
abertas por atenção requerida.

**O que o modelo NÃO faz melhor, e fica registrado:** no limiar escolhido por
F2, a **acurácia** (0,736 e 0,579) fica abaixo da persistência (0,776), e a
precisão da logística naquele ponto (0,550) também. Isso é o preço explícito da
preferência por recall, não um detalhe a omitir.

## Ablação: o modelo é a persistência com passos extras?

Removendo as três features que codificam histórico de prejuízo
(`prejuizo_em_t`, `prejuizo_em_t_menos_1`, `taxa_prejuizos_ate_t`):

| Modelo | AUC completo | AUC sem histórico de prejuízo |
|---|---|---|
| Regressão logística | 0,887 | 0,771 |
| Gradient boosting | 0,853 | **0,850** |

O gradient boosting perde quase nada (0,853 → 0,850) e **continua acima da
persistência (0,745) sem saber de nenhum prejuízo passado**. Os índices
contábeis contemporâneos — alavancagem, patrimônio negativo, ROE e suas
variações — carregam sinal próprio. A logística depende bem mais do histórico.

## Features, e o que ficou de fora com motivo

**Catorze features**, todas calculadas com dados de períodos **≤ T**. Seis
delas são análogas diretas do **O-score de Ohlson (1980)**, a referência da
literatura de insolvência — a escolha passou a ser rastreável a algo publicado,
não ao meu gosto:

| O-score | Feature aqui |
|---|---|
| SIZE | `log_ativo_total` |
| TLTA | `passivo_sobre_ativo` |
| NITA | `roa_trimestral` |
| OENEG | `patrimonio_negativo` |
| INTWO | `dois_prejuizos_seguidos` |
| CHIN | `variacao_lucro_escalada` |

**WCTA, CLCA e FUTL não são calculáveis neste painel** e faltam
declaradamente: as duas primeiras exigem a separação circulante/não circulante,
que a demonstração de instituição financeira arquivada na CVM não traz (o mesmo
motivo pelo qual `liquidez` nunca existiu em `indicadores`); FUTL exige
demonstração de fluxo de caixa, que não está carregada.

Duas escolhas do Ohlson corrigem defeitos que eu tinha introduzido:
`passivo_sobre_ativo` (TLTA) é bem definido mesmo com patrimônio negativo,
enquanto `alavancagem` (ativo/PL) explode e troca de sinal ao passar por zero;
e `variacao_lucro_escalada` (CHIN) é limitada a [−1, 1] e trata troca de sinal
com elegância, ao contrário do `delta_roe`, que eu havia sinalizado como
artefato.

Descartadas com motivo registrado em código (`COLUNAS_DESCARTADAS`):

- `receita_intermediacao` e `margem_liquida` — preenchidas em **77 de 2.321
  linhas (3%)**; são conceito de instituição financeira num painel
  majoritariamente não financeiro. Imputar 97% de uma coluna é inventar
  variável.
- `n_trimestres_observados` e `n_prejuizos_ate_t` — **confundidas com o
  tempo**. Como o painel começa em `1T2025`, a profundidade de histórico é
  determinada pelo trimestre: treino vê 1–3, teste vê **4**, valor nunca
  observado no treino. Qualquer corte de árvore nessa coluna extrapolaria.
  Substituídas por `taxa_prejuizos_ate_t`, comparável entre profundidades.

## Guardas contra vazamento

- **Features não reagem ao futuro.** `TestVazamentoTemporal` constrói o painel
  duas vezes, mudando só o lucro de T+1, e falha se qualquer feature de T
  mudar. Só o rótulo pode reagir.
- **Rótulo embaralhado derruba o AUC ao acaso** (teste exige 0,40–0,60). Se
  houvesse vazamento, o modelo acertaria mesmo com rótulo aleatório.
- **T+1 por junção explícita em `ordem + 1`**, nunca `LEAD` sobre a linha
  vizinha: se um trimestre falta para aquela companhia, ela sai do painel em
  vez de receber rótulo de um trimestre distante.
- **Imputação e padronização ajustadas só no treino** — calcular a mediana
  sobre o painel inteiro vazaria estatística do futuro.

## RN07 — o que o módulo se proíbe

O modelo **não** responde sobre companhia nomeada. `prever_para_companhia`
existe **para recusar**: deixar a fronteira como função que levanta erro é mais
difícil de contornar por acidente do que deixá-la como parágrafo de
documentação. `TestRN07` falha se qualquer módulo do caminho interativo
(`agentes`, `ferramentas`, `geracao`, `recuperacao`, `cobertura`, `seguranca`,
`app_streamlit`, os dois braços) importar `src.modelo`.

O motivo é coerência com o próprio guardrail: o sistema recusa "vale a pena
comprar ações do BB?" citando a Res. CVM 20/2021. Publicar, na pergunta
seguinte, "o BB tem X% de chance de prejuízo" seria a mesma fronteira na
direção oposta.

## Contraste corpus × painel (retrospectivo, não previsão)

| | Observações | Com prejuízo | Taxa |
|---|---|---|---|
| Corpus (5 bancos) | 28 | **0** | **0,0%** |
| Painel completo | 2.305 | 684 | 29,7% |

Confirma o alcance honesto declarado na 5.10: aplicado ao corpus, o modelo
responderia sempre a mesma coisa. É leitura de dado arquivado, não previsão, e
é o segundo entregável da etapa.

## Ressalvas

1. **Um único trimestre de teste (406 observações), e isto é a limitação
   dominante — não as features.** Bootstrap pareado de 4.000 reamostragens:
   o AUC de 0,887 tem **IC 95% [0,836; 0,917]**, largura de 0,08. A melhoria
   trazida pelas features do O-score é **+0,010 com IC 95% [−0,005; +0,030]**,
   que **inclui zero** (P(diferença > 0) = 0,885). Direcionalmente positiva e
   ancorada na literatura, mas **não demonstrada** neste tamanho de amostra.
   Ver `resultados/pesquisa_modelo_preditivo_2026-08-23.md`.
2. **A janela do painel é curta por decisão anterior** (`CVM_ANO_INICIAL=2025`,
   para casar com o corpus). Reabrir a janela só para o treino segue sendo a
   saída registrada se a etapa precisar de mais volume.
3. **26% do painel tem lag nulo** — as observações de `1T2025` não têm T−1
   porque o painel começa ali. Os modelos lidam com isso (nativamente no
   boosting, por imputação na logística), mas é assimetria entre treino e teste.
4. **O trimestre de teste é o pior possível, e a literatura previa isso.** O
   teste é a transição `4T2025 → 1T2026`, e as inovações de lucro do 4º
   trimestre são reconhecidamente **menos persistentes** (ajustes de
   fim de exercício). Pior: o modelo **nunca viu uma transição Q4→Q1 no
   treino**, que só tem Q1→Q2 e Q2→Q3. Some-se a isso que o `4T2025` é
   derivado por aritmética (RN10).
5. **O benchmark canônico da literatura não é calculável aqui.** Para lucro
   trimestral, a referência é o *seasonal random walk* (mesmo trimestre do ano
   anterior, defasagem 4) — com 5 trimestres no painel, defasagem 4 não existe.
   A persistência de defasagem 1 que uso como baseline **não é** o benchmark
   consagrado, e a literatura registra que a autocorrelação de lucro trimestral
   **inverte de sinal na defasagem 4**. Isso pode estar tornando meu baseline
   fraco demais, e portanto a vitória do modelo mais fácil do que deveria.
6. **O rótulo da validação vem do `4T2025`, que é derivado** (RN10): o 4º
   trimestre não existe como ITR e sai de aritmética entre DFP e 9M. Isso afeta
   a **escolha do limiar**, não os rótulos de treino nem de teste, que são
   arquivados. O ROC-AUC, sendo livre de limiar, não é afetado.
