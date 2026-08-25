# O que a literatura diz sobre este dataset — e o que aconteceu ao aplicá-la

**Data:** 2026-08-23 · **Custo:** zero · Levantamento feito a pedido, depois da
primeira versão da etapa 10, para checar se as escolhas de modelagem eram as
melhores ou apenas as minhas.

> **Este documento tem duas camadas, e a segunda contradiz parte da primeira.**
> As seções 1–5 são o levantamento como foi escrito **antes** de executar as
> recomendações. O bloco final, *Placar das previsões*, registra o que
> aconteceu quando elas foram executadas: **das três recomendações
> testáveis, uma se confirmou de forma esmagadora e duas foram refutadas** —
> inclusive uma que eu havia implementado com confiança.
>
> Mantive o texto original em vez de reescrevê-lo porque um levantamento
> bibliográfico que só é publicado depois de dar certo não serve de registro de
> método. Os resultados finais estão em
> `resultados/modelo_preditivo_2026-08-23.md`.

Resumo em uma linha: **duas decisões minhas estavam certas e ficam
confirmadas; três estavam erradas ou incompletas; e o gargalo real não é o
modelo — é a janela de dados.**

---

## 1. Confirmado — não usar SMOTE nem reamostragem

A tentação óbvia com 29,9% de positivos seria reamostrar. **Não vamos.**

van den Goorbergh et al. (JAMIA, 2022) testaram exatamente isso em modelos de
risco com regressão logística: subamostragem, superamostragem e SMOTE
produziram modelos **mal calibrados** — a probabilidade da classe minoritária
ficava fortemente superestimada — e **não** melhoraram a área sob a curva ROC.
O ponto decisivo: *"resultados semelhantes foram obtidos deslocando o limiar de
probabilidade"* — que é exatamente o que a 5.10 já mandava fazer e o que o
módulo faz por F2.

Há um trabalho recente (arXiv 2605.14067) que recomenda SMOTE para previsão de
insolvência e mede ganho de recall com ele. **Ele não compara SMOTE contra
class weights nem contra ajuste de limiar** — reconhece explicitamente que
essas alternativas não foram discutidas. Comparado ao estudo que testa as três,
não sustenta a troca. Além disso, 29,9% de positivos é desbalanceamento **leve**;
SMOTE foi desenhado para classes raras de 1–5%.

**Ação: nenhuma.** A escolha de limiar continua sendo o mecanismo, e fica agora
com respaldo publicado em vez de só bom senso.

## 2. Corrigido — as features agora vêm da literatura, não do meu gosto

> ⚠️ **REFUTADO depois.** Tudo nesta seção foi medido sobre a partição única e
> não sobreviveu aos 47 folds: as features do O-score são nulas no boosting
> (p = 0,135) e **pioram** a logística (p = 3,3e−04). Foram removidas. Ver o
> *Placar das previsões*, no fim.

Eu havia inventado as onze features olhando as colunas disponíveis. A
referência estabelecida para insolvência é o **O-score de Ohlson (1980)**, cujo
desempenho geral é apontado como superior ao Z-score de Altman em
reavaliações empíricas. Confrontando as nove variáveis dele com o painel:

| O-score | Definição | Situação aqui |
|---|---|---|
| SIZE | log(ativo total) | já tinha (`log_ativo_total`) |
| NITA | lucro / ativo | já tinha (`roa_trimestral`) |
| OENEG | passivo > ativo | já tinha (`patrimonio_negativo`) |
| **TLTA** | passivo / ativo | **acrescentada** |
| **CHIN** | variação de lucro escalada | **acrescentada** |
| **INTWO** | dois períodos seguidos de prejuízo | **acrescentada** |
| WCTA | capital de giro / ativo | **impossível** — exige circulante/não circulante |
| CLCA | passivo circulante / ativo circulante | **impossível** — idem |
| FUTL | recursos de operações / passivo | **impossível** — exige fluxo de caixa |

As três impossíveis são a mesma lacuna que já impedia `liquidez` de existir em
`indicadores`: a demonstração de instituição financeira arquivada na CVM não
traz a separação circulante/não circulante. Ficam declaradas, não escondidas.

**Duas delas corrigem defeitos que eu mesmo tinha introduzido:**

- **TLTA (passivo/ativo) é melhor que a minha `alavancagem` (ativo/PL).** A
  minha explode e troca de sinal quando o patrimônio passa por zero — e o
  painel tem companhias com patrimônio negativo. TLTA fica bem definida:
  acima de 1 significa insolvente.
- **CHIN substitui o meu `delta_roe`**, que eu já havia sinalizado no relatório
  como provável artefato. CHIN é limitada a [−1, 1] e trata troca de sinal de
  lucro com elegância, em vez de dividir por um denominador que passa perto de
  zero.

**Efeito medido** (mesmo split, mesma semente):

| Conjunto de features | Logística | Boosting |
|---|---|---|
| 11 originais (minhas) | 0,877 | 0,844 |
| 14 com O-score | **0,887** | **0,853** |
| só as 6 do O-score | 0,769 | 0,857 |

E no ponto de operação escolhido por F2, o ganho é maior do que o AUC sugere:
a precisão da logística subiu de 0,423 para **0,550** e o F1 de 0,583 para
**0,692** — que passa a **superar a persistência (0,651)**, coisa que a versão
anterior não fazia.

**Ressalva que impede comemorar:** bootstrap pareado de 4.000 reamostragens dá
diferença de AUC **+0,010, IC 95% [−0,005; +0,030]** — inclui zero. É
direcionalmente positivo (P = 0,885) e teoricamente ancorado, mas **não
demonstrado** com um único trimestre de teste. Mantive as features pelo
argumento teórico, não pelo número.

## 3. Achado que eu não conhecia — o trimestre de teste é o pior possível

A literatura de lucro trimestral registra que **as inovações de lucro do quarto
trimestre são menos persistentes** — há um padrão próprio de 4º trimestre
(ajustes e acertos de fim de exercício).

Nosso split faz exatamente o pior arranjo possível diante disso:

- treino: transições **Q1→Q2** e **Q2→Q3**
- validação: **Q3→Q4**
- teste: **Q4→Q1**

O modelo **nunca viu uma transição Q4→Q1 durante o treino**, e Q4 é justamente
o trimestre anômalo. Pior ainda: o nosso `4T2025` é **derivado por aritmética**
(RN10), porque o 4º trimestre não existe como ITR.

Isso não invalida o resultado — o teste ser difícil é conservador, não
otimista. Mas explica parte da distância entre validação (AUC 0,795) e teste, e
significa que o número publicado **não é** uma estimativa do desempenho médio
em um trimestre qualquer.

## 4. Achado relacionado — o baseline canônico não é calculável hoje

> ⚠️ **REFUTADO depois.** Com a janela larga o passeio sazonal virou
> calculável — e mostrou-se marginalmente **mais fraco** que a persistência
> (0,739 × 0,752). A suspeita de baseline fraco demais não se confirmou. Mas a
> intuição sazonal estava certa no lugar errado: virou **feature**, e foi de lá
> que veio todo o ganho.

Para lucro trimestral, o benchmark consagrado não é a persistência de
defasagem 1 que uso: é o **seasonal random walk**, que compara com o **mesmo
trimestre do ano anterior** (defasagem 4). A literatura registra ainda que a
autocorrelação das diferenças sazonais de lucro trimestral **inverte de sinal
na defasagem 4**.

Com 5 trimestres no painel, **defasagem 4 não existe**. Ou seja: não só me
falta a feature sazonal, como o baseline que publico pode ser **fraco demais**,
tornando a vitória do modelo mais fácil do que seria contra o benchmark certo.
Isso está agora nas ressalvas do relatório principal.

## 5. A limitação dominante — uma única partição

A prática recomendada para dado financeiro é **walk-forward com janela
expansível**, e a referência prática citada é da ordem de **30 folds
(≈1 trimestre por fold)** para capturar múltiplos regimes e ter poder
estatístico. Validação cruzada aleatória é explicitamente inadequada para
painel: mistura passado e futuro e superestima a capacidade do modelo.

**Nós temos 1 fold.** O IC 95% do AUC tem largura de 0,08. Nenhuma comparação
de features, modelo ou hiperparâmetro consegue ser resolvida com essa
resolução — foi o que aconteceu no item 2.

Isso também explica um resultado que destoa da literatura: nos estudos de
insolvência, gradient boosting costuma dominar a regressão logística com
folga (um deles reporta XGBoost com AUC 0,91 contra 0,71 da logística). **Aqui
a logística venceu** (0,887 × 0,853), o que é o padrão esperado quando o
treino tem 873 linhas. Com mais dados, a ordem provavelmente se inverte.

---

## Recomendação, em ordem de retorno

### 1. Reabrir a janela do painel para o treino — é o desbloqueio de tudo

> ✅ **EXECUTADO e CONFIRMADO** em 2026-08-23. 21.903 observações, 47 folds.

`CVM_ANO_INICIAL=2025` foi decisão consciente para casar o painel com o corpus,
e o `MEMORY.md` já registrava a saída: *reabrir a janela só para o treino,
mantendo o painel consultável casado com o corpus*. A etapa 10 chegou nesse
ponto.

`Config` já aceita de **2011** a 2100 e `scripts/baixar_cvm.py` já recebe
`--anos`. O dado é público e gratuito; o custo é download e processamento.

Isso resolve, de uma vez, os itens **3, 4 e 5**:

- múltiplas transições **Q4→Q1** no treino, em vez de nenhuma;
- viabiliza a feature sazonal e o **seasonal random walk** como baseline correto;
- viabiliza **walk-forward com ~50 folds** em vez de 1, com intervalo de
  confiança de verdade;
- dá volume para o boosting operar na faixa em que a literatura o mostra
  vencendo.

Estimativa grosseira: 15 anos × 4 trimestres × ~450 companhias ≈ **25 mil
observações**, contra as 1.699 de hoje.

### 2. Depois disso, e só depois, medir de novo o que ficou indeciso

Com folds suficientes, refazer a comparação das features do O-score (hoje
IC inclui zero), a escolha entre logística e boosting, e aí sim considerar
XGBoost/LightGBM/CatBoost, que a literatura reporta como os melhores da
categoria.

### 3. Acrescentar calibração ao relatório

Como publicamos probabilidade e escolhemos limiar sobre ela, faz sentido
reportar **Brier score** e uma curva de calibração junto das métricas atuais —
é a dimensão que a literatura de reamostragem mostra ser a primeira a se
degradar, e hoje não medimos.

### O que **não** fazer

- **Não** adicionar SMOTE ou reamostragem (item 1).
- **Não** trocar de modelo com base no fold único (item 5).
- **Não** reabrir a janela do painel **consultável** — a decisão de casá-lo com
  o corpus continua válida para o caminho interativo; a janela larga é do
  painel de **treino**, e os dois podem coexistir.

---

---

## Placar das previsões — o que sobreviveu à execução

Escrito **depois** de reabrir a janela, construir o painel de treino
2011–2026 e rodar 47 folds de walk-forward.

| # | O que este documento previu | Veredito | Evidência |
|---|---|---|---|
| 1 | Não usar SMOTE; ajuste de limiar basta | **não testado** | O limiar por F2 seguiu em uso e funcionou; SMOTE nunca foi tentado, então isto continua sendo argumento emprestado, não medição própria |
| 2 | As features do O-score melhorariam o modelo | **REFUTADO** | Nulo no boosting (+0,0005, p=0,135) e **piora** na logística (−0,0027, p=3,3e−04). Removidas |
| 3 | O teste Q4→Q1 é o pior arranjo possível | **mitigado, não refutado** | Segue sendo Q4→Q1 na partição única, mas o treino passou a conter 14 outras transições Q4→Q1 e o walk-forward mede todos os trimestres |
| 4 | O passeio sazonal seria um baseline mais duro | **REFUTADO** | É marginalmente *mais fraco* que a persistência (0,739 × 0,752, p=0,042) |
| 5 | Partição única é a limitação dominante | **CONFIRMADO** | 47 folds resolveram as três comparações que a partição única deixava indecidíveis, com p da ordem de 1e−09 |
| 6 | Com mais dados o boosting passaria a logística | **confirmado, mas fraco** | Passou (0,866 × 0,863), porém o IC 95% da diferença toca o zero: +0,0033 [−0,0002; +0,0069] |

### O que isso ensina sobre o método, não sobre o dataset

**A previsão que mais falhou foi a mais bem fundamentada.** As features do
O-score vinham de 1980, de um modelo reconhecidamente superior ao Z-score em
reavaliações empíricas, e três das nove eram diretamente deriváveis do painel.
Eu as implementei e o número subiu — mas o intervalo de confiança incluía zero,
e eu registrei isso como "não demonstrado" em vez de comemorar. Foi essa
ressalva, e não a intuição, que se provou correta quando o poder estatístico
chegou.

**O ganho real veio de onde a literatura apontava sem eu ter percebido.** A
seção 4 anotou que o benchmark de lucro trimestral é sazonal, e eu tratei isso
como um problema de *baseline fraco*. Era, na verdade, uma dica sobre
**features**: a sazonalidade que torna o passeio sazonal um benchmark natural é
a mesma que faz `prejuizo_no_mesmo_trimestre_do_ano_anterior` ser informativa.
O baseline sazonal se mostrou fraco; a *feature* sazonal deu todo o ganho
(+0,0102, p=7,0e−09, 42/47 folds).

**A recomendação certa era a menos sofisticada.** Entre "usar as variáveis
canônicas de insolvência" e "conseguir mais dados", a segunda venceu com folga.
Reabrir a janela destravou de uma vez o volume, os folds e as features
sazonais.

## Fontes

- [The harm of class imbalance corrections for risk prediction models — van den Goorbergh et al., JAMIA 2022](https://academic.oup.com/jamia/article/29/9/1525/6605096)
- [Comparative Evaluation of ML Approaches for Minority-Class Financial Distress Prediction (arXiv 2605.14067)](https://arxiv.org/html/2605.14067)
- [The Hidden Cost of Resampling: How Imbalance Correction Degrades Probability Calibration in Tree Ensembles (arXiv 2606.29720)](https://arxiv.org/html/2606.29720)
- [Empirical implications of Ohlson's O-score (Copenhagen Business School)](https://research.cbs.dk/files/68333991/1114538_18123_Thesis.pdf)
- [Bankruptcy classification errors in the 1980s: Altman's and Ohlson's models — Review of Accounting Studies](https://link.springer.com/article/10.1007/BF00570833)
- [The contextual nature of the predictive power of statistically-based quarterly earnings models](https://link.springer.com/article/10.1007/s11156-006-0001-z)
- [A re-examination of analysts' superiority over time-series forecasts (Notre Dame)](https://care-mendoza.nd.edu/assets/152185/bradshawpaper.pdf)
- [On the (Mis)Use of Machine Learning with Panel Data (arXiv 2411.09218)](https://arxiv.org/pdf/2411.09218)
- [Machine Learning Meets Panel Data: What Practitioners Need to Know](https://towardsdatascience.com/machine-learning-meets-panel-data-what-practitioners-need-to-know/)
