# Etapa 10 — o debate entre dois especialistas, e o que ele derrubou

**Data:** 2026-08-25 · **Custo de API:** zero (medições em CPU sobre o painel
local) · **Método:** dois agentes independentes com acesso à web — um analista
sênior de equity research bancário e um cientista de dados sênior — auditaram o
modelo em paralelo e depois debateram até convergir.

## Por que este documento existe

O modelo tinha passado por uma avaliação crítica minha e por uma onda de
correções de robustez. Os dois relatórios anteriores
(`revisoes_modelo_2026-08-23.md`, `robustez_modelo_2026-08-24.md`) davam a
impressão de um módulo bem medido. **Estava errado em três pontos que nenhuma
das minhas rodadas tinha alcançado**, e um deles era a manchete.

Três retratações saíram do debate, **uma de cada participante, inclusive minha**
— o que é o melhor argumento a favor de fazer isso com dois avaliadores
independentes em vez de um.

---

## Retratação 1 (minha): o "interruptor do porte" não existe

Eu havia publicado, no `panorama.json` e na rota que responde ao usuário, uma
tabela de "regime de risco por porte" separada em instituição financeira ×
demais, com um gradiente de **0,6% a 29,6%** entre as financeiras. A leitura
era que porte funciona como interruptor em banco e é quase irrelevante fora.

**A flag `is_banco` não significa "banco".** Ela significa "usa plano de contas
de instituição financeira" — e das 41 entidades marcadas, oito não são banco:

| Entidade | Eventos positivos | Ativo médio |
|---|---|---|
| SUL 116 PARTICIPAÇÕES — **em liquidação** | 12 | R$ 0,0 bi |
| GP INVESTMENTS (private equity) | 9 | R$ 3,6 bi |
| PPLA PARTICIPATIONS | 5 | R$ 34,5 bi |
| CELGPAR (holding de energia) | 3 | R$ 1,6 bi |

**29 dos 35 eventos positivos (82,9%) do recorte vinham dessas entidades.**
Limpo o universo, sobram 6 eventos, a série fica não monotônica, e o teste
contínuo mata o efeito: correlação de Spearman entre ativo e prejuízo, em
bancos de verdade **excluindo os ≥ R$ 500 bi**, é **ρ = −0,014 (p = 0,79)**.
Fora do topo, porte não prediz nada — o que restava era uma variável dummy para
cinco bancos.

Pior: entre bancos de verdade, quem mais dá prejuízo são instituições
**grandes** em fase de crescimento — Nu Holdings 7/10 (R$ 117 bi), XP 3/15
(R$ 151 bi), Inter. Os pequenos de verdade quase não dão: Pine 0/33, Patagônia
0/30, CFI 0/12. **A tese inverte.**

**Agravante de método:** a guarda `minimo_positivos=20`, que eu havia criado no
dia anterior exatamente para impedir "AUC bonito sobre poucos eventos", **não
pegou este caso** — a contaminação inflou a contagem de 6 para 35 e as linhas
passaram legitimamente pelo corte. Guarda estatística não substitui conferir o
que a variável significa.

**Correção aplicada:** o recorte setorial **saiu**, não foi corrigido. O que
sobra e se sustenta é a tabela do painel inteiro, com amostra em cada faixa:

| Porte | Trimestres | Com prejuízo |
|---|---|---|
| ≥ R$ 500 bi | 231 | 6,1% |
| R$ 100–500 bi | 506 | 21,9% |
| R$ 10–100 bi | 5.365 | 21,8% |
| < R$ 10 bi | 16.760 | 37,4% |

---

## Retratação 2 (cientista de dados): o oráculo de identidade vazava

Ele reportou que um "oráculo de identidade" — a taxa histórica de rótulo da
própria companhia, sem feature nenhuma — marcava AUC 0,90 e **batia o modelo**,
concluindo que o módulo não agregava nada além de saber quem é o emissor.

O analista bancário apontou o defeito e eu verifiquei por conta própria: aquele
oráculo usava a média do rótulo sobre **todo o painel, incluindo os trimestres
de teste**. Não é observável no momento da predição.

| Escore | AUC | AP |
|---|---|---|
| Oráculo **vazado** (o que ele publicara) | 0,8947 | 0,7158 |
| Oráculo **honesto** (só o passado do fold) | **0,8008** | 0,5475 |
| `taxa_prejuizos_4t` cru | 0,8646 | 0,5929 |
| **Modelo** | **0,8765** | 0,6452 |

Ele reproduziu, concedeu e escreveu: *"é exatamente a classe de erro que
apontei no item 1(d) da minha auditoria, aplicada ao meu próprio baseline"*.

**A conclusão inverte:** o modelo **bate** a identidade implementável por
**+0,074 de AUC, vencendo em 46/46 folds**. E ele substituiu o argumento por um
mais forte — **oráculo como teto, não como baseline**: uma constante por
companhia calculada com conhecimento do futuro (LOO) marca 0,8797, e o modelo é
**estatisticamente indistinguível dela** (p = 0,51), atingindo 99,8% desse teto.

---

## Retratação 3 (analista bancário): duas, na verdade

**(a) Cobertura do pré-tributos.** Ele afirmou "758 de 918 banco-trimestres" e
retirou: estava comparando o numerador de uma tabela com o denominador de
outra. O correto é **758 de 758**, e 22.956 de 22.956 no painel — **zero** pares
com lucro líquido e sem pré-tributos. A troca de alvo não tem custo de
cobertura em lugar nenhum.

**(b) Modelo só de instituições financeiras.** Ele recomendou construir um, com
NII, índice de eficiência e cobertura de PDD. Depois fez a análise de poder e
**retirou a própria recomendação**: no universo limpo restam **6 eventos
positivos**; com 8 eventos, o AUC mínimo distinguível de 0,50 é 0,702
(Hanley & McNeil, 1982). Impossível por construção. As features bancárias
entram como **camada descritiva de relatório, sem predição** — ou o universo
migra para o IF.data do BACEN (~150 conglomerados prudenciais contra ~25
companhias abertas).

---

## O achado central: o modelo ordena *quais*, não *quando*

Este sobreviveu ao debate inteiro e é o mais importante.

| Medida | Valor |
|---|---|
| AUC agregado (walk-forward, 47 folds) | **0,8648** |
| **AUC *dentro* da mesma companhia, ao longo do tempo** | **0,6632** |
| `taxa_prejuizos_4t` sozinha, *within*-companhia | 0,6492 |
| Escore constante por companhia, *within* | 0,5 por construção |

**Mesmo dentro da companhia, as 15 features não agregam nada sobre uma coluna.**
E a composição da lista fecha a leitura:

> **97,1% do decil superior já está em prejuízo em T** (contra 33,3% do painel),
> e **99,8% tem `taxa_prejuizos_4t` ≥ 0,5.**

O lift de 3,3 no painel inteiro **não é triagem antecipada** — é uma lista de
deficitárias crônicas reproduzível por um `WHERE`. Publicá-lo sem esta linha ao
lado é vender um filtro SQL como modelo.

**Onde o modelo tem produto de verdade** é o recorte de companhias hoje
lucrativas, onde a regra de persistência é muda por construção: AUC 0,8315,
lift 4,35, contra 3,73 da identidade implementável. Mas o volume real é de
**~4 nomes novos por trimestre** — 21 companhias lucrativas entraram no decil
superior em 46 folds inteiros, e no fold mais recente as 41 de 41 do topo já
estavam em prejuízo.

---

## O baseline publicado era fraco por construção

A persistência ("teve prejuízo em T, terá em T+1") é preditor **binário**: no
fold 3T2025, **33,6% dos pares +/− ficam empatados**, e o AUC conta cada empate
como 0,5. O ganho de +0,10 que os relatórios anteriores publicavam era, em boa
parte, artefato de granularidade.

Sob o desenho corrigido (47 folds, purga de treino **e** validação,
`early_stopping` desligado):

| Comparação | Δ AUC | p | Folds |
|---|---|---|---|
| modelo − **`taxa_prejuizos_4t` crua** | **+0,0190** | 4,6e−11 | 44/47 |
| modelo − **identidade implementável** | **+0,0733** | 1,4e−14 | 47/47 |
| modelo − persistência (o número antigo) | +0,1126 | 1,4e−14 | 47/47 |
| modelo − regressão logística | +0,0021 | 0,10 | 30/47 |

**A manchete honesta é +0,019 sobre uma coluna que já existe no painel**, não
+0,11 sobre uma regra binária.

---

## Dois defeitos de método que o debate encontrou no código

**1. Vazamento no trimestre de validação.** A validação ficava em `k−1`. Com
alvo de `n` trimestres, o rótulo dessa linha cobre `k .. k+n−1` — **alcança o
teste**. Como o limiar F2 sai dela, *todo número dependente de limiar* estava
contaminado. Vale inclusive para `n = 1`: a validação em `k−1` tinha rótulo
igual ao desfecho do próprio trimestre de teste.

Corrigido para `ordem_teste − 1 − n_alvo`. Efeito no ponto de operação: fração
sinalizada **42,9% → 34,5%**, recall 0,879 → 0,795, precisão 0,479 → 0,534,
F1 0,614 → 0,627. **A contaminação fazia o modelo parecer pior** no critério que
mais se criticava.

*E o teste-guarda escrito para isso inspecionava só `divisao.treino`.* Uma
contraprova anterior chegava a **afirmar** que o alvo de 1 trimestre não era
afetado — travando o comportamento defeituoso. Hoje `TestPurga` cobre
`divisao.validacao` e verifica a invariante para `n` = 1, 2 e 3.

**2. `early_stopping='auto'` ajustava o modelo sozinho.** O padrão do
scikit-learn liga quando `n > 10.000`; no walk-forward isso acontece no fold 21.
**21 folds treinavam 300 iterações e 25 paravam cedo** (o último com 111
árvores), com o critério saindo de uma partição *aleatória e não temporal* de
10% do treino. Três consequências: o estimador não era o mesmo entre folds; a
ressalva publicada "nenhum ajuste de hiperparâmetro foi feito" era **falsa**; e
a comparação boosting × logística não era equivalente. Fixado em `False`
(efeito numérico: −0,0009, p = 0,20 — o problema era de contrato, não de
desempenho).

---

## O alvo: para banco, nenhum rótulo contábil da CVM serve

O analista propôs trocar `lucro_liquido_consolidado < 0` por
`resultado_antes_tributos < 0`, e o caso Itaú 2T2020 parecia decisivo. Medindo,
o quadro é mais interessante que a proposta:

**Nos 173 trimestres dos cinco bancos do corpus: líquido negativo em 1,
pré-tributos negativo em 10.** Nove trimestres resgatados pela linha fiscal,
zero afundados por ela. Os episódios são **2015 (recessão) e 2020 (COVID)** — e
o rótulo publicado não dispara em nenhum.

Mas o pré-tributos erra na direção oposta:

| | Bancos | Não financeiras |
|---|---|---|
| Trimestres com pré-tributos < 0 **que viram lucro líquido** | **24,5%** | 6,2% |

E os casos grandes vêm **aos pares**: Itaú e Santander ambos no 1T2020, ambos
no 3T2015. Dois emissores independentes com a mesma anomalia no mesmo trimestre
é causa comum, não idiossincrasia.

**Conclusão conjunta, mais dura que qualquer das duas propostas:** para banco, o
líquido **erra por omissão** (1 evento contra 10) e o pré-tributos **erra por
excesso** (24,5% resgatados). O número que o analista usa — resultado recorrente
gerencial — **não está no arquivo da CVM**.

Isso não enfraquece o projeto: **é literalmente a tese dele**. A divergência
gerencial × contábil é a razão de existir a camada de RAG sobre os releases.

---

## Discordâncias publicadas como tal

1. **Alcance do achado `is_banco`.** O cientista de dados mediu: excluindo as
   oito entidades, o AUC agregado vai de 0,8765 para 0,8776 e o
   *within*-companhia de 0,6220 para 0,6221. **É achado sério numa tabela sobre
   ~2,3% do painel; não invalida o modelo.** Eu havia exagerado o alcance no
   primeiro relato, e a medição dele está certa.
2. **Direção de recuperação.** O modelo fica **0,062 abaixo** do teto de
   identidade para prever *saída* de prejuízo (p = 1,6e−05, vence em 3/46),
   enquanto está *no* teto para *entrada*. Há informação de nível-companhia
   sobre viradas que ele não captura. Irrelevante se o produto for triagem de
   deterioração; bloqueante se alguém quiser usá-lo para detectar recuperação.
3. **Instrumento da decisão.** O cientista de dados usa *decision curve
   analysis* (`pt`); o analista argumenta que analista de research não escolhe
   limiar, tem orçamento fixo de nomes, e a métrica vinculante é precisão@N.
   **Os dois chegam à mesma conclusão operacional por caminhos diferentes** — o
   que vai para produção é a heurística de duas linhas (`taxa_prejuizos_4t` com
   desempate por ROA), não o modelo: diferença de precisão no topo **−0,0009,
   p = 0,95**.

---

## Fundamentação regulatória acrescentada

O **Ofício nº 002/2025/SSA/APIMEC Brasil** (05/03/2025) veda que IA gere
relatório ou recomendação sem supervisão humana, exige verificação humana de
toda informação processada e governança documentada. Citado pelo analista,
inicialmente não localizado pelo cientista de dados, e depois **confirmado por
ele na fonte primária**. Aponta na mesma direção da RN05 e da RN07, já
implementadas; e a cláusula do art. 19 §1º da Res. CVM 20/2021 — *IA não é
fonte* — mapeia direto na RN01, que já exige citação de empresa, documento,
trimestre e página.

---

## O que continua em aberto

1. **Viés *as-restated*.** 16,3% dos fatos vêm de documento republicado e a
   carga guarda `VERSAO = max` — features e rótulos usam número que não existia
   na data. Medir exige reler os ZIPs brutos da CVM por versão; o DuckDB
   carregado não serve.
2. **O produto não escora o presente.** `construir_painel` faz `JOIN alvo`, e
   linha sem rótulo é descartada: há dados completos até `1T2026` e a última
   linha supervisionada é `3T2025`. Vale construir a escoragem **restrita a
   `prejuizo_em_t = 0`**, e o denominador honesto do custo é ~4 nomes por
   trimestre, não "lift 3,3".
3. **Viés de sobrevivência.** 277 de 741 companhias somem do painel e a última
   observação antes do sumiço nunca recebe rótulo. Com uma lista de eventos
   terminais (B3/CVM/BACEN), o alvo deixaria de ser "prejuízo trimestral" (base
   33%) e passaria a ser o evento raro de que Altman e Ohlson tratam — o que
   também **explicaria** por que as features do O-score não transferiram.
4. **Dependência entre folds.** Folds consecutivos compartilham 96,3% do
   treino. A correção de Nadeau–Bengio muda **uma** conclusão: o efeito da
   purga deixa de ser significativo (p = 0,026 → 0,125) — o que só reforça o
   que já estava escrito, que ele é detectável e desprezível.
5. **`comparar_pareado` usa o quantil normal 1,96** num IC de 46 observações;
   deveria ser t₄₅ = 2,014. Os ICs saem ~3% estreitos demais.
