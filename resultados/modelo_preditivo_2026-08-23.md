# Etapa 10 — modelo preditivo: prejuízo em T+1

**Data:** 2026-08-23 · **Custo de API:** zero (DuckDB local, treino em CPU) ·
**Artefato:** `artefatos/modelo/metricas.json` · **Reprodução:**
`python -m scripts.treinar_modelo --painel artefatos/cvm_treino.duckdb`

Pré-condição satisfeita: o gate **G4 foi aprovado em 2026-08-22**. O rótulo
depende do mapa semântico de contas, e treinar antes disso treinaria um modelo
confiantemente errado.

> Este documento é a **segunda versão**. A primeira treinou sobre a janela
> curta (1 ano, 1.699 observações, uma única partição de teste) e está
> preservada em `artefatos/modelo/metricas_painel_curto_2026-08-23.json`. O que
> mudou entre as duas, e por quê, está em
> `resultados/pesquisa_modelo_preditivo_2026-08-23.md`.

## Dois painéis, de propósito

| Painel | Janela | Uso |
|---|---|---|
| `artefatos/cvm.duckdb` | 2025–2026 | **consultável** pela camada interativa; segue casado com o corpus |
| `artefatos/cvm_treino.duckdb` | **2011–2026** | **só treino offline** (RN07) |

A decisão de manter o painel consultável estreito continua valendo — ela existe
para que o que o sistema responde ao usuário tenha documento correspondente no
corpus. A janela larga é do painel de **treino**, e os dois coexistem. Carga
reproduzível por `scripts/construir_painel_cvm.py`.

Volume: **5,5 milhões de linhas**, 741 companhias, 64 trimestres, todas as seis
regras de armadilha da 5.5 aplicadas.

## Tarefa e painel supervisionado

Classificação binária: *dada a posição contábil até o trimestre T, a companhia
reportará prejuízo em T+1?* Unidade amostral é companhia × trimestre; o rótulo
sai de `fatos_semanticos` pelo mapa semântico, **nunca de `cd_conta` cru**
(RN09).

- **21.903 observações** (eram 1.699), **61 trimestres**, **33,3% de positivos**.
- **Split temporal**, nunca aleatório.
- **Três trimestres descartados** por estarem incompletos (`2T2026` com 128
  companhias, `3T2026` com 9, `1T2027` com 1). O corte é relativo à mediana de
  companhias por trimestre, não um número fixo.

**Por que descartar trimestre parcial não é desperdiçar amostra.** O `2T2026`
tinha **17% de prejuízo contra ~29%** dos trimestres fechados: quem declara
cedo é sistematicamente mais saudável. Admiti-lo não adicionaria amostra —
adicionaria viés de seleção com cara de amostra.

## Validação walk-forward — 47 folds

Este é o resultado principal. Um fold por trimestre, janela de treino
expansível, validação sempre no trimestre anterior ao de teste, treino sempre
estritamente no passado dos dois.

| Modelo | AUC médio | Desvio | IC 95% empírico entre folds |
|---|---|---|---|
| **Gradient boosting** | **0,866** | 0,033 | [0,793; 0,913] |
| Regressão logística | 0,863 | 0,032 | [0,801; 0,905] |
| Baseline — persistência (defasagem 1) | 0,752 | 0,035 | [0,702; 0,824] |
| Baseline — passeio sazonal (defasagem 4) | 0,739 | 0,035 | [0,683; 0,798] |

Comparações pareadas fold a fold (Wilcoxon):

| Comparação | Diferença média | IC 95% | p (Wilcoxon) | Folds vencidos |
|---|---|---|---|---|
| boosting − passeio sazonal | **+0,1269** | [+0,119; +0,134] | 1,4e−14 | **47/47** |
| boosting − persistência | **+0,1139** | [+0,105; +0,123] | 1,4e−14 | **47/47** |
| logística − passeio sazonal | +0,1235 | [+0,117; +0,130] | 1,4e−14 | 47/47 |
| logística − persistência | +0,1105 | [+0,101; +0,120] | 1,4e−14 | 47/47 |
| persistência − passeio sazonal | +0,0130 | [+0,000; +0,026] | 0,042 | 30/47 |
| boosting − logística | +0,0033 | **[−0,0002; +0,0069]** | 0,041 | 32/47 |

Todas reprodutíveis por `python -m scripts.treinar_modelo` — saem em
`artefatos/modelo/metricas.json`, em `walk_forward.comparacoes_pareadas`.

**O modelo bate a regra simples em todos os 47 folds.** Não há trimestre, em
quinze anos, em que a persistência tenha ordenado melhor.

**A ordem entre os modelos inverteu com o volume — mas a diferença é
marginal, e isso ficou mais claro depois de remover as features do O-score.**
Na janela curta a logística vencia (0,887 × 0,853); com 21 mil observações o
boosting passa à frente. A margem, porém, é pequena: **+0,0033, com IC 95% de
[−0,0002; +0,0069]** — o intervalo **toca o zero**, ainda que o Wilcoxon dê
p = 0,041 e o boosting vença em 32/47 folds. É evidência fraca, de natureza
completamente diferente da vitória sobre os baselines.

**Correção de um número que publiquei antes:** numa medição intermediária esta
diferença saiu como +0,0065 com p = 2e−04, e eu a reportei assim. Aquela
medição usava o conjunto de 18 features, com as do O-score ainda dentro; com o
conjunto final de 15 a vantagem do boosting encolhe pela metade. O número
correto para o modelo publicado é o da tabela acima.

**O passeio sazonal não era o baseline mais forte.** Eu havia registrado a
suspeita de que a persistência de defasagem 1 fosse fraca demais para lucro
trimestral, e que o benchmark correto (mesmo trimestre do ano anterior)
tornasse a vitória do modelo mais difícil. **Medido, é o contrário**: o passeio
sazonal fica marginalmente *abaixo* da persistência (p = 0,042, vence em
30/47). A suspeita não se confirmou, e a comparação anterior estava adequada.

## Partição única — para comparabilidade com a versão anterior

Teste em `4T2025` → rótulo em `1T2026` (413 observações), treino com 21.063.

| Modelo | Limiar | Recall | Precisão | F1 | Acurácia | ROC-AUC |
|---|---|---|---|---|---|---|
| Baseline — classe majoritária | 0,50 | 0,000 | 0,000 | 0,000 | 0,680 | — |
| Baseline — persistência | 0,50 | 0,667 | 0,647 | 0,657 | 0,777 | 0,748 |
| Regressão logística | 0,13 | 0,955 | 0,573 | 0,716 | 0,772 | 0,928 |
| Regressão logística | 0,50 | 0,659 | 0,837 | 0,737 | 0,850 | 0,928 |
| Gradient boosting | 0,10 | **0,985** | 0,524 | 0,684 | 0,724 | **0,929** |
| Gradient boosting | 0,50 | 0,720 | 0,826 | **0,769** | **0,862** | **0,929** |

O limiar saiu da **validação**, maximizando F2 — que pondera recall com o dobro
do peso da precisão, tradução declarada da preferência da 5.10. O limiar
**nunca** foi escolhido olhando o teste.

**Com a janela larga, o modelo passou a bater a persistência em todas as
métricas simultaneamente**, o que a versão de janela curta não conseguia: no
limiar 0,5 o boosting tem F1 0,769 (contra 0,657), acurácia 0,862 (contra
0,777) e recall 0,720 (contra 0,667). A preferência por recall deixou de custar
acurácia — porque o modelo melhorou, não porque a régua mudou.

## O modelo agrega? A comparação maçã com maçã

Precisão **no mesmo recall da persistência** (0,667):

| | Recall | Precisão |
|---|---|---|
| Persistência | 0,667 | 0,647 |
| Regressão logística | 0,667 | 0,830 |
| Gradient boosting | 0,667 | **0,854** |

Detectando exatamente tanto quanto a regra simples, o boosting erra o alarme
bem menos (0,854 contra 0,647).

## Resultado negativo: as features do O-score não ajudaram

Na primeira versão eu acrescentei três análogas do **O-score de Ohlson (1980)**
— TLTA (`passivo_sobre_ativo`), CHIN (`variacao_lucro_escalada`) e INTWO
(`dois_prejuizos_seguidos`) — por argumento de literatura. Na janela curta
pareciam somar +0,010 de AUC, mas o IC incluía zero e isso ficou declarado como
**não demonstrado**.

Com 47 folds e poder estatístico de verdade:

| Modelo | Efeito das features do O-score | p |
|---|---|---|
| Gradient boosting | +0,0005 · IC [−0,0004; +0,0014] | 0,135 (nulo) |
| Regressão logística | **−0,0027** · IC [−0,0040; −0,0013] | 3,3e−04 (**piora**) |

Testar como *substituição* (removendo `alavancagem` e `delta_roe`, que elas
deveriam suplantar) não muda o quadro. **Foram removidas das features.** O
`+0,010` da janela curta era ruído, exatamente como o intervalo de confiança
avisava. Continuam calculadas no quadro para auditoria, e o motivo está em
`OSCORE_REMOVIDAS_POR_MEDICAO`, no código.

Também errei a explicação intermediária: supus que as features do Ohlson
ajudariam a logística e seriam indiferentes para árvores (invariantes a
transformação monótona). Medido, ocorreu o oposto — provavelmente
colinearidade com as colunas que elas duplicavam.

## O que de fato ganhou: estrutura sazonal

O ganho da janela larga não veio de modelo nem de Ohlson, mas das quatro
features que **só existem** com vários anos:

| Comparação (boosting, 47 folds) | AUC | Diferença | p | Folds vencidos |
|---|---|---|---|---|
| conjunto completo (15 features) | 0,8660 | — | — | — |
| sem o grupo sazonal (11 features) | 0,8559 | **+0,0102** · IC [+0,0074; +0,0130] | 7,0e−09 | **42/47** |

Reprodutível por `ablacao_walk_forward(painel, GRUPO_SAZONAL)`; sai em
`artefatos/modelo/metricas.json`, em `ablacao_sazonal`.

As features são `prejuizo_no_mesmo_trimestre_do_ano_anterior` (T−3, que é o
mesmo trimestre do ano anterior visto do alvo T+1), `variacao_lucro_anual`
(T contra T−4, escalada), `taxa_prejuizos_4t` (janela móvel) e
`trimestre_do_ano`.

**`trimestre_do_ano` só virou feature legítima agora.** Com um ano de painel
ela seria idêntica à identidade do trimestre, e o teste teria um valor nunca
visto no treino — a mesma armadilha que fez `n_trimestres_observados` ser
descartada. Com 61 trimestres, os quatro valores aparecem no treino.

## Ablação: o modelo é a persistência com passos extras?

Removendo as features que codificam histórico de prejuízo:

| Modelo | AUC completo | AUC sem histórico de prejuízo |
|---|---|---|
| Regressão logística | 0,928 | 0,920 |
| Gradient boosting | 0,929 | **0,924** |

Praticamente inalterado, e muito acima da persistência (0,748). Os índices
contábeis contemporâneos carregam sinal próprio: o modelo **não** é a regra
simples disfarçada.

## Features, e o que ficou de fora com motivo

Quinze features, todas calculadas com dados de períodos **≤ T**. Descartadas
com motivo registrado em código (`COLUNAS_DESCARTADAS`):

- `receita_intermediacao` e `margem_liquida` — preenchidas em ~3% das linhas;
  são conceito de instituição financeira num painel majoritariamente não
  financeiro. Imputar 97% de uma coluna é inventar variável.
- `n_trimestres_observados` e `n_prejuizos_ate_t` — **confundidas com o
  tempo**: a profundidade de histórico é determinada pelo trimestre, e o split
  temporal poria no teste um valor nunca visto no treino. Substituídas por
  taxas, comparáveis entre profundidades.
- As três do O-score, pelo resultado negativo medido acima.

Do O-score, **WCTA, CLCA e FUTL nunca foram calculáveis** e faltam
declaradamente: as duas primeiras exigem a separação circulante/não circulante,
que a demonstração de instituição financeira arquivada na CVM não traz (mesmo
motivo pelo qual `liquidez` não existe em `indicadores`); FUTL exige
demonstração de fluxo de caixa, não carregada.

## Guardas contra vazamento

- **Features não reagem ao futuro.** `TestVazamentoTemporal` constrói o painel
  duas vezes mudando só o lucro de T+1 e falha se qualquer feature de T mudar.
- **Nenhum fold treina no futuro do seu teste** — verificado fold a fold em
  `TestWalkForward`, além de treino expansível que nunca encolhe.
- **Rótulo embaralhado derruba o AUC ao acaso** (teste exige 0,40–0,60).
- **T+1 e as defasagens por junção explícita em `ordem ± k`**, nunca
  `LAG`/`LEAD` sobre a linha vizinha: se um trimestre falta para aquela
  companhia, o valor vem nulo em vez de vir de um trimestre distante.
- **Imputação e padronização ajustadas só no treino.**

## RN07 — o que o módulo se proíbe

O modelo **não** responde sobre companhia nomeada. `prever_para_companhia`
existe **para recusar**: deixar a fronteira como função que levanta erro é mais
difícil de contornar por acidente do que deixá-la como parágrafo de
documentação. `TestRN07` falha se qualquer módulo do caminho interativo
importar `src.modelo`.

O motivo é coerência com o próprio guardrail: o sistema recusa "vale a pena
comprar ações do BB?" citando a Res. CVM 20/2021. Publicar, na pergunta
seguinte, "o BB tem X% de chance de prejuízo" seria a mesma fronteira na
direção oposta.

## Contraste corpus × painel (retrospectivo, não previsão)

| | Observações | Com prejuízo | Taxa |
|---|---|---|---|
| Corpus (5 bancos) | 173 | **1** | **0,6%** |
| Painel completo | 22.862 | 7.568 | 33,1% |

Com quinze anos em vez de um, aparece **exatamente um** trimestre de prejuízo
entre os cinco bancos: **Itaú, 2T2020** (−R$ 1,9 bi, dado arquivado, não
derivado) — o trimestre da pandemia. A leitura da 5.10 se mantém e fica mais
forte: aplicado ao corpus, o modelo responderia quase sempre a mesma coisa, e o
valor dele está no painel completo.

**Ressalva de cobertura:** Bradesco, BB e BTG só têm série a partir de `1T2022`
neste painel; Itaú e Santander vão a 2011. A taxa do corpus não é, portanto,
uniforme em quinze anos para os cinco.

## Ressalvas

1. **O trimestre de teste da partição única continua sendo Q4→Q1**, e as
   inovações de lucro do 4º trimestre são reconhecidamente menos persistentes.
   A diferença agora é que o treino **contém 14 outras transições Q4→Q1**, e o
   walk-forward mede todos os trimestres, não só esse.
2. **Calibração não é medida.** Publicamos probabilidade e escolhemos limiar
   sobre ela; Brier score e curva de calibração seguem pendentes.
3. **Nenhum ajuste de hiperparâmetro foi feito.** Os do boosting são os
   escolhidos a priori; não houve busca, o que é conservador (não há risco de
   super-ajuste por seleção) mas deixa desempenho na mesa.
4. **XGBoost/LightGBM/CatBoost não foram testados.** A literatura os reporta
   como melhores da categoria; aqui só há o `HistGradientBoosting` do
   scikit-learn, para não acrescentar dependência sem medir.
5. **Um arquivo da CVM tem *mojibake* na origem**
   (`itr_cia_aberta_BPA_con_2020.csv`, 12 bytes fora do latin-1, em campo
   descritivo). Saneado na extração, com o motivo registrado em
   `scripts/construir_painel_cvm.py`; códigos e valores são ASCII e não foram
   tocados.
6. **O rótulo da validação vem do `4T2025`, que é derivado** (RN10). Isso
   afeta a escolha do limiar, não os rótulos de treino nem de teste. O ROC-AUC,
   livre de limiar, não é afetado.
