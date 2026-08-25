# Etapa 10 — as sete revisões, SMOTE e o alvo persistente

**Data:** 2026-08-23 · **Custo de API:** zero · **Artefato:**
`artefatos/modelo/experimentos.json` · **Reprodução:**
`python -m scripts.experimentos_modelo --painel artefatos/cvm_treino.duckdb`

Documento das correções pedidas depois da avaliação crítica. Tudo roda sob o
**mesmo walk-forward** (um fold por trimestre, treino sempre no passado), para
que toda comparação seja pareada.

> **Correção posterior (2026-08-24).** O AUC de 0,881 desta rodada foi medido
> **sem purga/embargo**: com alvo de 2 trimestres, o rótulo de uma linha de
> treino alcançava o trimestre de teste. Corrigido, o número é **0,8797**
> (−0,0016, p = 0,026). A diferença é desprezível e não muda nenhuma conclusão
> deste documento, mas o número correto é o de lá:
> `resultados/robustez_modelo_2026-08-24.md`. Duas ressalvas abertas aqui
> também foram fechadas naquele relatório — recalibração e biblioteca
> alternativa, ambas medidas e ambas sem ganho.

## Resumo

**Duas mudanças valeram; cinco revisões viraram resultado negativo ou nulo.**
O alvo persistente proposto pelo Ygor é a melhoria real desta rodada. O SMOTE
piora. O ajuste de hiperparâmetros não faz nada. E o rótulo derivado, que eu
apontava como fragilidade séria, não move o resultado.

---

## O alvo persistente (T+1 **e** T+2) — a mudança que valeu

| | Alvo 1 trimestre | Alvo 2 consecutivos |
|---|---|---|
| Observações | 21.903 | 21.119 |
| Taxa-base de positivos | 33,3% | **22,3%** |
| ROC-AUC (boosting) | 0,866 | **0,881** |
| **Lift no top-10%** | 2,55 | **3,36** |
| Recall no top-20% | 0,478 | **0,588** |
| Brier | 0,140 | **0,115** |
| Erro de calibração | 0,067 | **0,058** |
| **Fração sinalizada no limiar F2** | 57,6% | **41,5%** |

**Melhora em todas as dimensões práticas ao mesmo tempo.** O ponto que mais
importa é o último: a crítica de que o modelo "sinaliza 60% da base" cai de
57,6% para 41,5%, e o lift no topo da lista salta de 2,55 para **3,36 vezes a
taxa-base**. Ou seja: lendo os 10% mais bem ranqueados, o analista encontra
três vezes e meia mais deterioração do que sorteando.

**Por que era previsível que melhorasse, e por que ainda assim precisava ser
medido.** Exigir prejuízo em dois trimestres seguidos remove do rótulo positivo
o ruído contábil de um trimestre só — baixa isolada, sazonalidade, evento
não recorrente. O que sobra é mais próximo de deterioração. O alvo fica mais
raro (22,3%) e, ao mesmo tempo, **mais previsível**, o que não é contraditório:
é sinal mais limpo.

**Ressalva que o alvo novo introduz, e não é pequena:** a janela de dois
trimestres tem muito mais chance de tocar um 4º trimestre, que é derivado por
aritmética (RN10). **A fração de rótulos que envolve trimestre derivado sobe de
24,8% para 50,8%.** Medi a sensibilidade a isso — ver adiante — e o resultado
se sustenta, mas o alvo persistente depende bem mais da derivação do 4T.

**O baseline também melhora** (persistência 0,752 → 0,776), então parte do
ganho é da tarefa ter ficado mais fácil de ordenar, não do modelo. A vantagem
sobre o baseline encolhe de +0,1139 para **+0,1052** — ainda 46/46 folds,
p = 2,8e−14.

---

## SMOTE — medido no dado do projeto, e **piora**

Até esta rodada, a decisão de não reamostrar era argumento emprestado da
literatura. Agora é medição própria.

| Alvo | SMOTE − controle (AUC) | IC 95% | p | Folds vencidos |
|---|---|---|---|---|
| 1 trimestre | **−0,0060** | [−0,0079; −0,0040] | 5,4e−08 | **7/47** |
| 2 consecutivos | **−0,0080** | [−0,0110; −0,0050] | 5,4e−06 | 11/46 |

E o estrago maior não é no AUC, é na **calibração**:

| Alvo | Brier: controle → SMOTE | Erro de calibração: controle → SMOTE |
|---|---|---|
| 1 trimestre | 0,140 → 0,149 | 0,067 → **0,094** |
| 2 consecutivos | 0,115 → 0,129 | 0,054 → **0,104** |

O erro de calibração praticamente **dobra** no alvo persistente. E o
ranqueamento — o uso declarado do módulo — não melhora nada (precisão no
top-10% de 0,853 para 0,851).

É exatamente o que van den Goorbergh et al. (JAMIA 2022) previam: reamostragem
degrada a probabilidade sem melhorar a discriminação. Com 22–33% de positivos,
estamos longe do regime de classe rara para o qual o SMOTE foi desenhado.

**Cuidado metodológico que essa medição exigiu:** o SMOTE interpola vizinhos e
**não tolera nulo**, enquanto o boosting trata nulo nativamente. Comparar SMOTE
contra o boosting puro mediria reamostragem *e* imputação de uma vez. Por isso
existe o braço `boosting_imputado` (mesma imputação, sem SMOTE) — a comparação
publicada é contra ele. O boosting puro e o imputado são indistinguíveis
(+0,0006, p = 0,11), o que valida o controle.

**Vazamento evitado por construção:** o `Pipeline` usado é o do `imblearn`, que
aplica reamostragem só no `fit`. Com o do scikit-learn o SMOTE rodaria também
na predição, sintetizando linhas de teste. Há teste travando isso.

---

## As sete revisões, uma a uma

### 1. Erro de categoria no enquadramento — **corrigido**

O docstring do módulo agora abre declarando que **prejuízo trimestral não é
insolvência**: é evento de ~33% de base, frequentemente benigno, enquanto
Altman e Ohlson tratam de evento terminal de 1–2%. Isso também passou a ser a
explicação registrada para o fracasso das features do O-score — são fenômenos
diferentes, não só features diferentes. O alvo persistente é a resposta prática
a essa crítica.

### 2. Ponto de operação sinalizava 60% da base — **corrigido e medido**

Duas mudanças. Primeiro, o módulo passou a reportar **métricas de
ranqueamento** (precisão, lift e recall no topo da lista), que é como se mede o
uso declarado na 5.10 — ordenar companhias por atenção requerida. Um corte
global por F2 nunca foi a métrica certa para isso.

Segundo, o alvo persistente reduz a fração sinalizada de 57,6% para 41,5%.
Ainda é muito para uma triagem confortável, e isso fica declarado: quem precisa
de lista curta deve usar o **top-10%**, onde o lift é 3,36.

### 3. Rótulo derivado (RN10) — **medido, não move o resultado**

Reexecutando tudo **apenas sobre as linhas cujo rótulo não toca trimestre
derivado**:

| Alvo | AUC completo | AUC só rótulo arquivado | Folds |
|---|---|---|---|
| 1 trimestre | 0,866 | 0,872 | 35 |
| 2 consecutivos | 0,881 | 0,883 | 22 |

O desempenho é **igual ou ligeiramente melhor** sem os rótulos derivados, o que
indica que a derivação adiciona algum ruído mas não inverte nem sustenta nada.
A hierarquia entre modelos e baselines é idêntica nos dois recortes. Eu havia
classificado isso como fragilidade séria; **não é**.

### 4. Viés de sobrevivência — **quantificado, permanece como limitação**

277 das 741 companhias somem do painel ao menos um ano antes do fim da janela.
Na última declaração, **41,2% delas estavam com prejuízo, contra 34,1%** das
que permanecem. Há seleção, mas modesta.

O que **não** tem correção com este dado: a observação final antes do
desaparecimento nunca recebe rótulo, porque o rótulo exige T+1 (ou T+1 e T+2).
Os desfechos mais severos — companhia que colapsa e para de declarar — são
estruturalmente excluídos. Isso torna o resultado **conservador para eventos
extremos** e é limitação declarada, não corrigida.

### 5. Boosting × logística era diferença arbitrária — **confirmado, e assumido**

| Alvo | Boosting − logística | IC 95% | p |
|---|---|---|---|
| 1 trimestre | +0,0033 | [−0,0002; +0,0069] | 0,041 |
| 2 consecutivos | +0,0024 | [−0,0007; +0,0054] | 0,163 |

No alvo persistente a diferença **não é significativa**. Os dois modelos são
equivalentes para efeito prático; o relatório deixa de tratar o boosting como
vencedor e passa a reportá-los como empatados.

### 6. Calibração e hiperparâmetros — **os dois medidos; o ajuste não rende nada**

Calibração entrou nas métricas (Brier e erro de calibração esperado por faixa)
e está nas tabelas acima.

Sobre hiperparâmetros: a busca correu numa grade de 5 configurações **nos 20
folds mais antigos**, e a melhor (`max_leaf_nodes=31`, `learning_rate=0,02`,
`min_samples_leaf=50`) marcou 0,8605 contra 0,8572 do padrão — aparente ganho
de +0,003.

**Conferido nos 27 folds que a busca não viu, o ganho é exatamente zero:**

| | AUC |
|---|---|
| Configuração padrão | 0,8726 |
| Configuração "ajustada" | 0,8726 |

Diferença **−0,0000**, IC 95% [−0,0012; +0,0012], p = 0,77, vencendo em 14/27.
O ganho da busca era **ruído de seleção**. A decisão anterior de não ajustar
hiperparâmetros não custava desempenho nenhum — e agora isso está medido em vez
de suposto.

### 7. "AUC normal, não notável" — **mantido como está**

Não é uma revisão a fazer, é uma calibração de expectativa a preservar no
texto. O relatório principal continua registrando que 0,866–0,881 é resultado
correto e ordinário para esta literatura, não um resultado notável.

---

## O que continua em aberto

1. **XGBoost/LightGBM/CatBoost** seguem sem teste. Dado que boosting e
   logística empataram e que o ajuste de hiperparâmetros rendeu zero, a
   expectativa de ganho por troca de biblioteca é baixa — mas é expectativa,
   não medição.
2. **A calibração é medida, não corrigida.** Erro de 0,054–0,067 no controle;
   uma recalibração isotônica ou de Platt provavelmente reduziria isso e não
   foi tentada.
3. **O viés de sobrevivência não tem correção** com os dados disponíveis.
4. **O alvo persistente depende mais do 4T derivado** (50,8% dos rótulos).
   Mostrou-se robusto no recorte sem derivados, mas com metade dos folds.
