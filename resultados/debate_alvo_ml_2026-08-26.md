# Debate de dois especialistas — alvo de ML para Value Investing (2026-08-26)

> **RETRATAÇÃO POSTERIOR (validação concluída na virada de 26–27/08).**
> Este relatório preserva a rodada exploratória, mas sua aprovação do alvo não
> representa mais o estado do projeto. Ao aplicar T1 também ao `sd8` — componente
> que define mecanicamente o próprio evento — o C1 reprovou: amplitude
> **0,180–0,183** na replicação principal e **0,247** na implementação isolada
> do agente, contra o limiar < 0,15. Os dois especialistas terminaram em
> **REJEITAR**. Ver `resultados/validacao_c1_2026-08-26.md`.

Quatro rodadas entre um cientista de dados e um analista de equity research, ambos
com acesso à web, mediando eu (sessão principal) com verificação independente de
toda afirmação que carregava peso. Motivo: o alvo então em produção — "prejuízo
contábil em T+1" — não é decisão de investimento, e o modo analista autenticado
(§3.6) tornou possível expor saída por emissor.

**Resultado: existe um alvo aprovado pelos dois, e ele é menor e mais estranho
do que qualquer uma das três propostas iniciais.** O caminho até ele produziu
**seis retratações** e um achado metodológico que vale mais que o alvo.

> **Nada aqui está implementado.** Este documento é especificação aprovada, não
> entrega. O repositório não foi alterado por nenhum dos agentes.

---

## 1. O achado metodológico — dois testes que todo alvo tem de passar

É o que este debate acrescenta ao projeto, e é reutilizável fora dele.

Um alvo de ML sobre demonstrações financeiras pode falhar de **duas maneiras
opostas**, e cada uma é invisível pelo teste da outra:

### Teste 1 — o alvo fabrica o próprio baseline?

Corte **absoluto** ("ROA cai mais de 2 pontos", "margem cai 5pp") não é
escala-livre: quem tem ROA de 40% cai 2pp sem esforço; quem tem 2% cairia para
território negativo. O alvo passa a **favorecer mecanicamente** quem tem nível
alto — e o nível é justamente a coluna usada como baseline.

Medido (taxa de evento por quintil de `roa_ttm`, painel de treino):

| Alvo | Q1 · Q2 · Q3 · Q4 · Q5 | Amplitude | AUC da coluna crua |
|---|---|---|---|
| Absoluto (ΔROA < −2pp) | 0,307 · 0,252 · 0,222 · 0,291 · **0,540** | **0,317** | **0,5988** |
| Relativo (lucro cai ≥30%) | 0,377 · 0,336 · 0,286 · 0,285 · 0,377 | 0,092 | **0,4912** |

A coluna que parecia um baseline forte (0,60) vale **menos que o acaso** (0,49)
quando o alvo é escala-livre. **A força dela era artefato da definição do alvo.**

**Métrica operacional:** amplitude da taxa de evento entre quintis do
estratificador. Limiar adotado: **< 0,15**.

### Teste 2 — o alvo tem sinal temporal ou só ordena emissores?

Já era disciplina do projeto (§ decomposição obrigatória), mas aqui ele
**reprovou o candidato favorito**:

| Alvo | AUC agregada | **AUC intra-companhia** | **Lacuna** |
|---|---|---|---|
| Absoluto (ΔROA < −2pp) | 0,6506 | 0,6217 | **+0,029** ✅ |
| Relativo (lucro cai ≥30%) | 0,6331 | **0,4597** | **+0,173** ❌ |
| Relativo + filtros de investibilidade | 0,6293 | **0,4488** | **+0,181** ❌ |

**A AUC intra-companhia do alvo relativo fica ABAIXO do acaso.** Dentro de uma
mesma empresa ao longo do tempo, o modelo ordena pior que sorteio. O ganho
aparente de +0,13 a +0,18 é ganho sobre uma coluna inútil, não antecipação.

**Métrica operacional:** lacuna (agregada − intra). Limiar: **< 0,12**.

### O ponto que fecha o argumento

**Os dois cortes reprovam, em critérios opostos.** Nenhum dos dois é limpo. Um
alvo só é honesto se passar nos **dois ao mesmo tempo** — e essa exigência
conjunta é o que nenhuma das propostas iniciais satisfazia.

---

## 2. Por que o alvo relativo colapsa — paradoxo de Simpson, não volatilidade

Minha hipótese como mediador foi: *"cair 30% é fácil para quem tem lucro pequeno;
o alvo mede volatilidade, que é atributo de empresa"*. **Medida e parcialmente
refutada.**

| Medição | Resultado | Veredito |
|---|---|---|
| `vol_roa` sozinha, alvo relativo | agregada 0,614 · intra 0,508 | volatilidade **é** atributo de empresa ✅ |
| Modelo **sem** features de volatilidade | intra 0,443 → **0,423** | remover **não** salva ❌ |
| Correlação(escore, `vol_roa`) | **+0,049** | o escore nem a usa ❌ |

Tirar a volatilidade derruba a AUC **agregada** (0,622 → 0,544) sem recuperar a
**intra**. A causa real, achada pelo cientista de dados:

| Coluna, no alvo relativo | AUC **agregada** | AUC **intra** |
|---|---|---|
| `roa_ttm` | **0,461** | **0,615** |
| `margem_ebit` | 0,485 | 0,584 |
| Modelo treinado | 0,659 | **0,499** |

**`roa_ttm` tem sinais opostos entre e dentro de empresa.** Na seção transversal,
ROA alto → *menos* provável cair 30%. Dentro da mesma empresa, ROA alto → *mais*
provável. O treino maximiza AUC agregada, ajusta o sinal transversal — que domina
a amostra — e por isso acerta **ao contrário** dentro da empresa.

**O sinal temporal existe nos dados; o objetivo de treino é que o descarta.** E
isso aponta o conserto: normalizar pela própria empresa.

---

## 3. O alvo aprovado

```
alvo = 1  se  ROA_ttm(t+4) − ROA_ttm(t)  <  −k · sd₈(ΔROA_ttm até t)

ROA_ttm(t) = Σ lucro_líquido[t−3..t] / ativo_total(t)
sd₈        = desvio-padrão móvel de 8 trimestres da variação anual de ROA,
             min_periods=6, calculado SÓ com dados até t
k          = 1,25   (ver ressalva de pré-registro em §6)
```

Ou seja: **queda de lucratividade medida em desvios-padrão da própria companhia.**
Escala-livre (passa T1) e comparável dentro da empresa (passa T2).

### Verificação em três implementações independentes

| Fonte | T1 | Agregada | **Intra** | **Lacuna** | Δ vs coluna | p |
|---|---|---|---|---|---|---|
| Cientista de dados (k=1,25) | 0,130 | 0,631 | 0,670 | **−0,039** | +0,028 | 0,0051 |
| Analista de mercado (≈1σ) | 0,127 | 0,575 | 0,628 | **−0,053** | +0,018 | 0,019 |
| **Verificação da sessão (k=1,25)** | **0,135** | 0,606 | **0,653** | **−0,047** | **+0,030** | 2,6e−04 |

**A lacuna é NEGATIVA nas três.** A AUC intra-companhia é *maior* que a agregada
— o escore ordena melhor **dentro** da empresa do que entre empresas, que é a
definição operacional de antecipação temporal. É a inversão exata da assinatura
do modelo antigo (+0,202).

Coerência monotônica (verificação da sessão, 409 companhias, 39 folds):

| k | Base | T1 | Lacuna | Δ vs coluna | p |
|---|---|---|---|---|---|
| 1,00 | 25,3% | 0,176 ❌ | −0,047 | +0,026 | 5,5e−04 |
| **1,25** | **21,4%** | **0,135** ✅ | **−0,047** | **+0,030** | 2,6e−04 |
| 1,50 | 18,1% | 0,105 ✅ | −0,052 | +0,021 | 0,048 |

### O que o alvo entrega, e o número que responde aos 97,1%

| | Modelo antigo (prejuízo T+1) | Alvo Z |
|---|---|---|
| Decil superior **já em prejuízo** | **97,1%** | **2,4%** |
| Decil superior já com ROA caindo | — | 17,4% |
| Lacuna intra-companhia | +0,202 | **−0,047** |

**82,6% dos nomes sinalizados parecem saudáveis no momento do sinal.**

**Materialidade econômica** (medida pelo analista, porque AUC não responde isso):
mediana do evento é **ROA caindo 5,31pp e lucro caindo 80,3%**; 88,4% dos eventos
são queda ≥2pp de ROA; **47,1% viram prejuízo de fato**, contra 19,2% dos
não-eventos. Precisão@10 = **0,419** contra taxa-base 0,171 — **lift 2,45**.

O alvo é estatisticamente limpo **e** economicamente material. As duas coisas
precisavam ser verificadas separadamente.

---

## 4. Universo — três bloqueios caíram com um arquivo gratuito

Os três agentes (inclusive eu) tratavam como intransponíveis limitações que
`cad_cia_aberta.csv` resolve. Download gratuito, atualização diária, casa por
`cd_cvm`:

| Bloqueio declarado | Realidade medida |
|---|---|
| "não há setor" (`setor` NULL em 736/741) | **`SETOR_ATIV` em 710/731**, 59 setores |
| "investibilidade não é mensurável" | **`CATEG_REG`: 575 Categoria A, 135 Categoria B** — pela Res. CVM 80, a B **não pode** ter ação negociada |
| "filtro de RJ é look-ahead" | **`SIT_EMISSOR`: 51 empresas** em RJ/liquidação/falência (o regex sobre razão social achava 38) **+ `DT_INI_SIT_EMISSOR`** — *point-in-time* resolvido |
| — | `CONTROLE_ACIONARIO`: 25 estatais, 33 estrangeiras |

**Universo final:** não-financeira · `ativo > R$ 1 bi` · `CATEG_REG = 'Categoria A'`
· exclui `SIT_EMISSOR` em crise com `data_do_trimestre ≥ DT_INI_SIT_EMISSOR`
→ **~410 companhias**.

Nota lateral: o carregador atual preenche `setor`/`ticker` a partir de um
dicionário fixo com os 5 bancos do corpus (`BANCO_POR_CD_CVM`) e grava `None`
para as outras 736 — **limitação por desenho, não defeito**, e agora fechável.

---

## 5. Especificação implementável

1. **Alvo:** §3, com `k` **pré-registrado** antes da medição publicável.
2. **Universo:** §4.
3. **Features:** razões fundamentalistas em **rank transversal por trimestre**.
   `SETOR_ATIV` passou a estar disponível e **deve entrar como teste, não como
   suposição**.
4. **Modelo:** **logística sobre ranks**. Boosting perdeu em toda célula medida
   nas quatro rodadas — e a logística é auditável em coeficientes, o que importa
   sob a RN01.
5. **Baseline obrigatório ao lado:** `roa_ttm` cru, com **sinal fixado no treino,
   nunca no teste**. Publicar a AUC dele sempre.
6. **Winsorizar `sd₈` a 1%/99%.** A distribuição tem cauda absurda (mín. 0,23pp,
   máx. 1.278pp, razão p90/p10 = 7,1×) — sem isso o alvo é ruído em ~2% dos casos.
7. **Métricas obrigatórias no artefato:** AUC agregada · **AUC intra-companhia** ·
   **lacuna** · **T1 (amplitude entre quintis)** · β do escore sob controle de
   `roa_rank` e `vol_rank`.
8. **Critério de retirada, operacional** — retira-se o modelo se **qualquer** um
   falhar: (a) lacuna > 0,12; (b) intra < 0,55; (c) T1 > 0,15; (d) Δ sobre a
   coluna não significativo a 5% em walk-forward pareado.

### Acompanhamento declarado antes de medir

1. Congelar hoje os 10 maiores escores do último trimestre fechado, com data,
   escore e taxa-base do recorte ao lado.
2. Congelar junto a **lista-controle**: os 10 maiores pela melhor coluna crua.
   Sem ela não se sabe se o modelo agregou.
3. Em 4 trimestres, medir nas duas: precisão@10 observada × 0,419 esperada, e
   quantos viraram prejuízo (esperado ~47%).
4. **Sucesso declarado antes:** precisão@10 ≥ 0,35 **e** ≥ a da lista-controle.
   Abaixo disso publica-se o negativo e retira-se o módulo.

---

## 6. Ressalvas que enfraquecem o resultado, declaradas

**O limiar `k` foi escolhido post-hoc.** Três valores foram testados e o do meio
escolhido depois de ver os resultados — jardim de caminhos que se bifurcam. Sob
Bonferroni para 3 testes o p = 0,0051 vira **p ≈ 0,015**; na verificação da sessão,
2,6e−04 vira ≈ 7,8e−04. Ainda passa, mas **a medição atual é a rodada de seleção,
não a de confirmação**. O que sustenta a família não é o limiar e sim a
**coerência monotônica**: lacuna negativa nos três valores de `k`, T1 melhorando
com o corte.

**O ganho sobre a coluna é +0,03, não +0,18.** Quem publicar o número grande
estará repetindo exatamente o erro que estas quatro rodadas existiram para
corrigir.

**Não medido, e não pode ser prometido:**

- **Alfa.** Sem tabela de preços *point-in-time* (item 19 do plano) não há
  afirmação de retorno. A literatura brasileira dá razão específica para
  desconfiar: Galdi & Lopes (2009) mostram que o efeito do F-Score vem de small
  caps ilíquidas; Cupertino, Martinez & Costa rejeitam a anomalia de accrual por
  teste de Mishkin — **o mercado precifica accruals racionalmente**. A hipótese
  default deve ser que **o preço já sabe**.
- **Liquidez e free float.** `CATEG_REG` resolve "pode ter ação negociada", não
  "dá para comprar R$ 50 mi sem mover o preço". É a única razão de o alvo ser
  aprovado como **fila de leitura para analista**, não como sinal de alocação.
- **Viés de sobrevivência.** 277 de 741 companhias somem; a última observação
  antes do sumiço nunca recebe rótulo.
- **Setor como controle** ficou disponível nesta rodada e **não foi testado**.
- **Viés *as-restated*** (16,36%, assimetria 0,66pp) afeta o `sd₈`, que é
  calculado sobre números possivelmente republicados.

---

## 7. Retratações — seis, distribuídas entre os três

**Cientista de dados (quatro):**
1. **Assimetria direcional** ("deterioração é previsível, recuperação não") —
   causa: comparava as duas direções **com modelos diferentes** (logística sobre
   ranks × boosting sobre escala bruta) e leu a diferença como fato sobre o mundo.
   Pareado: recuperação +0,0256, p=6e−06. Era reivindicada como contribuição inédita.
2. **Veredito sobre accruals** ("AUC 0,506, ruído") — era sobre o proxy de capital
   de giro. Baixou a DFC e mediu o accrual **total** de Sloan: **0,603**. Mas
   acrescentá-lo ao modelo rende +0,0017 (p=0,50): a informação já estava lá.
3. **Composição do decil** ("ROA mediano 12,2% contra 3,1% — armadilha de lucro
   de pico") — artefato do corte absoluto, e **inverte de sinal** sob corte
   relativo (decil fica *abaixo* da mediana do painel).
4. **O alvo absoluto inteiro**, por fabricar o baseline.

**Analista de mercado (duas):**
5. **"O alvo está certo, o modelo é supérfluo"** — era *aquele* alvo. Sob
   especificação escala-livre o multivariado bate a coluna em 26/26 folds.
6. **"Um sinal que inverte de direção conforme o estrato não é um sinal"** — ele
   estratificava uma **coluna crua**; nós, um **escore ajustado**. Objetos
   diferentes. A inversão é argumento **a favor** do modelo, não contra o alvo.
   Junto caiu a **proposta de duas camadas**: no alvo honesto todas as colunas
   cruas ficam no acaso (`marg` 0,496 · `roa` 0,501 · `gm` 0,476 · `giro` 0,499),
   então **a camada 1 não existe**.

**Mediador (uma):** a hipótese de que a volatilidade explicava o colapso
intra-companhia do alvo relativo — parcialmente certa (volatilidade infla a
agregada) e **errada no ponto que importa** (removê-la não recupera a intra).

---

## 8. Ideias medidas e mortas — para não repetir

| Ideia | Como morreu |
|---|---|
| **Anomalia de accrual** (Sloan) como alvo | Efeito **inverte de sinal** sob controle de ROA corrente (β +0,0027, p=0,32). Literatura brasileira concorda por teste de Mishkin |
| **Republicação** (`versao_documento`) como preditor | 0,1671 × 0,1664 entre lucrativas — diferença de 0,0007 |
| **Reapresentação** como alvo | Censura à direita: taxa cai 28,1% (2011) → 4,3% (2026) porque declaração recente não teve tempo de ser retificada. Corrigir exige data de entrega, e `dt_refer = dt_fim_exerc` em **100%** das 5,55 M linhas |
| **Alvo setorial** (pior que a mediana do setor) | Reprova T1 (amplitude 0,164–0,213) |
| **Efeitos fixos por empresa** (ΔROA < μ própria − 2pp) | Reprova T1 (0,321) — herda o defeito do corte absoluto |
| **Gerencial × contábil sobre os 5 bancos** | 5 emissores não dão amostra. Escala via dataset **IPE** (~USD 12 de OCR para 40–60 não-financeiras), ancorada na **Res. CVM 156/2022**, que obriga conciliação de LAJIDA. **Frente separada, exploratória** |

---

## 9. Discordância residual, publicada como tal

O cientista de dados sustenta que o multivariado agrega **+0,049** no universo
investível sobre o alvo dele; o analista mede **+0,018** sobre o dele com 6
features; a verificação da sessão mede **+0,030** no alvo Z. Os três podem estar
certos — são alvos e capacidades diferentes.

**O critério de escolha entre eles não deve ser o Δ maior, e sim a lacuna menor.**
Foi a lacuna que reprovou dois alvos e salvou um.

**Achado lateral, não resolvido:** a lacuna cresce com a capacidade do modelo de
memorizar identidade de emissor. Na verificação da sessão, remover uma única
feature (`vol_roa`) move a lacuna de +0,179 para +0,121 no alvo relativo. Logo o
critério de retirada (< 0,12) **precisa fixar o conjunto de features** para ser
comparável entre execuções — hoje não fixa.

---

## Fontes

Fama & French (2000), *Forecasting Profitability and Earnings* · Cao & You (2024),
*Fundamental Analysis via Machine Learning*, FAJ · Sloan (1996) · Piotroski (2000)
· Galdi & Lopes (2009) · Cupertino, Martinez & Costa, *Accrual anomaly in the
Brazilian capital market*, BAR · Bao et al. (2020), *Rev. Acc. Studies* · Gu, Kelly
& Xiu (2020) · Hanley & McNeil (1982) · Res. CVM 80 (categorias A e B) · Res. CVM
156/2022 (LAJIDA/LAJIR) · Lei 11.101/2005 art. 69 · Portal de Dados Abertos da CVM
(ITR, DFP, CAD, IPE).
