# Becos sem saída — ideias medidas e descartadas

**Registro consolidado.** Cada linha aqui foi **medida**, não descartada por
opinião. O objetivo é um só: impedir que uma sessão futura gaste orçamento
refazendo uma medição que já existe.

## Como usar

1. **Antes de propor qualquer ideia nova, procure nela aqui.** Se estiver
   listada, a pergunta deixa de ser "vale a pena tentar?" e passa a ser "o que
   mudou desde a medição?".
2. A coluna **"O que reabriria"** existe porque um registro de becos sem saída
   que nunca diz o que mudaria a resposta vira dogma. Nenhuma linha aqui é
   permanente — todas são condicionais ao dado e ao alvo que existiam na data.
3. **Descartado ≠ errado.** Boa parte destas ideias é boa e simplesmente não
   rende **neste** painel, com **este** alvo, **neste** tamanho de amostra.
4. Quando uma linha for reaberta e remedida, **atualize a linha** — não
   acrescente uma segunda. O registro é o estado, não o histórico; o histórico
   é o Git.

**Convenção de leitura:** "nulo" = medido e indistinguível de zero. "negativo" =
medido e pior que o controle. "reprovado em T1/T2" = falhou o protocolo dos dois
testes (AGENTS.md §3.7).

---

## A. Alvo e modelagem preditiva

### A.1 Alvos que reprovaram o protocolo dos dois testes

**Nota de escopo — 2026-09-08.** O padrão abaixo é alerta contra baselines
mecânicos, não teorema de impossibilidade de previsão. Os T1/T2 congelados
continuam valendo. A revisão do Rank 3 encontrou ausência da guarda de
recebimento e seleção indevida por saúde futura; suas métricas não certificam
o protocolo completo. O Rank 3-B admitido na própria tabela permanece outro
experimento, ainda sem treino. Fontes: [retomada DFC](viabilidade_ml_dfc_2026-09-08.md).

> **Padrão medido três vezes, com três roupas diferentes — leia antes de propor
> alvo novo:** *alvo definido como **variação** de uma grandeza que reverte à
> média fabrica o **nível** dessa grandeza como baseline.* Corte absoluto de
> ROA (nível `roa_ttm`, 0,317) · C1 (o próprio `sd8`, 0,180–0,247) · Rank 3
> (`accrual` 0,266 e `conversao` 0,229). Se o alvo é "X piora", o nível de X
> entra em T1 **obrigatoriamente** — a reversão à média é a hipótese nula certa
> e ela vence sozinha. Escapa disso só alvo com evento **materialmente
> definido** (falência, evento legal, reapresentação), não movimento de série
> contínua.

| Ideia | Medição | Veredito | O que reabriria |
|---|---|---|---|
| **Corte absoluto** (ΔROA < −2pp) | Amplitude por quintil **0,317**; coluna crua AUC 0,599 sob este alvo e **0,491** sob alvo escala-livre | **Reprova T1** — fabrica o próprio baseline. A força da coluna era artefato da definição | Nada. O defeito é da forma do corte, não do dado |
| **Efeitos fixos por empresa** (ΔROA < μ própria − 2pp) | Amplitude **0,321** | **Reprova T1** — herda o defeito do corte absoluto | Idem |
| **Alvo setorial** (pior que a mediana do setor) | Amplitude **0,164–0,213** (limiar 0,15) | **Reprova T1**, por pouco | Refazer com `SETOR_ATIV` do `cad_cia_aberta.csv` (59 setores reais, não os 5 do dicionário fixo) — a medição usou setor aproximado |
| **Corte relativo** (lucro cai ≥ 30%) | T1 = 0,092 (passa). Lacuna **+0,173**, AUC intra-companhia **abaixo do acaso** | **Reprova T2** — ordena emissor crônico, não momento | Nada com este alvo. A normalização pela volatilidade própria virou C1 e também foi rejeitada |
| **Rank 3 — Δaccrual no quintil superior** (deterioração de conversão de caixa) | `accrual` amplitude **0,266** (0,374 → 0,108 entre quintis) e `conversao` **0,229**; `roa` 0,061 e `ativo_medio` 0,116 passam | **Reprova T1 antes do treino.** Quem tem accrual BAIXO hoje tem 3,5× mais chance de ser marcado — é reversão à média com outro nome | Só com evento **materialmente definido** (ex.: FCO negativo em dois trimestres consecutivos), que é Rank 3-B com pré-registro próprio |
| **C1 — ΔROA TTM < −1,25 × sd8 próprio** | Replicação principal: amplitude T1 **0,180/0,181/0,183**, `-sd8` AUC **0,634** agregada e **0,709** intra, precisão top-20 **0,346**. Implementação cega do agente: amplitude **0,247** | **Reprova T1 antes do treino** — o normalizador que define o evento fabrica seu próprio baseline; T2 favorável não compensa | Apenas erro computacional ou incompatibilidade com a fórmula. Piso de materialidade, novo normalizador ou horizonte é **C2**, não reabertura do C1 |

### A.2 Preditores e features

| Ideia | Medição | Veredito | O que reabriria |
|---|---|---|---|
| **Anomalia de accrual** (Sloan) como alvo | β **+0,0027**, p = 0,32 — **inverte de sinal** sob controle de ROA corrente | Nulo. Consistente com a literatura brasileira (Cupertino, Martinez & Costa) que rejeita a anomalia por teste de Mishkin | Preços *point-in-time* (etapa 19). O teste feito é contábil; a anomalia é sobre **retorno** |
| **Accrual total de Sloan** como feature | Sozinho AUC **0,603** (informativo). Acrescentado às 28 features: **+0,0017**, p = 0,50 | Nulo por **redundância**, não por ausência de sinal | Se o conjunto de features encolher, ele volta a ser candidato |
| **Republicação** (`versao_documento`) como preditor | 0,1671 (em prejuízo) × 0,1664 (em lucro) — diferença **0,0007** | Nulo | Nada |
| **Features do O-score de Ohlson** | Negativo na ablação de grupo. **Reaberto em 2026-08-26** sob a condição declarada (alvo de insolvência de fato: 47 eventos legais de RJ/falência/liquidação do `cad_cia_aberta.csv`) e **negativo de novo** — a coluna crua `pl_ativo` (AUC 0,8765) bate o modelo, e a lacuna T2 reprova (+0,163/+0,247) | **LINHA FECHADA EM DEFINITIVO** | Nada. A condição de reabertura foi cumprida e o resultado se repetiu |
| **Defasagem sazonal T−3** como explicação do ganho sazonal | **−0,0005**, p = 0,46 — exatamente zero | O ganho do grupo (+0,0102) vem de `taxa_prejuizos_4t`, que é **janela móvel**, não defasagem sazonal | Se o alvo virar **magnitude** em vez de sinal: a sazonalidade vive no nível, e o alvo binário a destrói |
| **Setor como feature** (`instituicao_financeira`) | +0,0007 (p = 0,014) no alvo de 1T · **+0,0005 (p = 0,19)** no publicado | Nulo. `alavancagem` já separa os grupos por acidente (mediana 8,8 × 2,5) | Alvo em universo **não-financeiro** com 59 setores reais — outro problema, medição não transfere |

### A.3 Técnicas de treino

| Ideia | Medição | Veredito | O que reabriria |
|---|---|---|---|
| **SMOTE** | AUC **−0,0060** (p = 5,4e−08) e **−0,0080** (p = 5,4e−06). Erro de calibração 0,054 → **0,104** | **Negativo em dois eixos.** Com 22–33% de positivos estamos longe do regime de classe rara | Alvo com prevalência de fato baixa (< 5%) |
| **Ajuste de hiperparâmetros** | +0,003 nos 20 folds da busca · **−0,0000** (p = 0,77) nos 27 folds não vistos | Nulo. O ganho da busca era **ruído de seleção** | Mudança de família de modelo ou de escala do painel |
| **Recalibração isotônica** | AUC **−0,0047** e **−0,0062** (p ≈ 1e−13); erro de calibração não melhora | **Negativo.** Conjunto de ajuste de um trimestre (~400 linhas) faz a função em degraus decorar ruído | Conjunto de calibração de vários trimestres |
| **Recalibração de Platt** | AUC **idêntico** por construção (monotônico); erro de calibração nulo | Nulo — e o AUC idêntico em 93/93 folds serve de **contraprova do arnês** | Idem |
| **LightGBM** | −0,0001 (p = 0,87) e +0,0004 (p = 0,66) | Empate. **O teto é da tarefa, não da implementação** | Nada com esta família. XGBoost/CatBoost seguem sem teste, mas com expectativa baixa pelo mesmo motivo |
| **Trocar o alvo para `resultado_antes_tributos`** | **+0,0034** | Ruído. Recomendado pelos dois especialistas, **descartado por decisão de Ygor** | Nada — a decisão foi de escopo, não de medição |

### A.4 Hipóteses de diagnóstico que não se confirmaram

| Hipótese | Medição | Veredito |
|---|---|---|
| **O "interruptor do porte" em instituição financeira** | 42 de 49 eventos (85,7%) vinham de *private equity*, holding e uma companhia em liquidação. Universo limpo tem **7 positivos** contra o mínimo de 20 do próprio módulo | **Retratado.** Recorte removido. Reproduzível por `scripts/auditar_recorte_is_banco.py` |
| **Volatilidade explica o colapso intra-companhia do alvo relativo** | Remover as features de volatilidade **piora** a intra (0,4432 → 0,4230) | **Retratado (hipótese da sessão principal).** Causa real: paradoxo de Simpson — `roa_ttm` tem AUC 0,461 transversal × 0,615 intra, sinais opostos |
| **Duas camadas: coluna crua triando, modelo refinando** | Sob o alvo honesto todas as colunas cruas ficam no acaso (`marg` 0,496 · `roa` 0,501 · `gm` 0,476 · `giro` 0,499) | **Retratado (analista de mercado).** A camada 1 não existe |
| **Assimetria direcional: deterioração é previsível, recuperação não** | Pareado corretamente: recuperação **+0,0256**, p = 6e−06 | **Retratado (cientista de dados).** Comparava as direções com **modelos diferentes** e leu artefato de modelagem como fato sobre o mundo |

### A.5 Limitações de dado que bloqueiam ideias inteiras

| Ideia | O bloqueio | O que reabriria |
|---|---|---|
| **Reapresentação como alvo** | ~~Censura à direita~~ **REABERTO E RESOLVIDO em 2026-08-26, depois morto por outro motivo.** A censura era do estimador antigo, não do fenômeno: a coluna `ORDEM_EXERC` dos CSVs (descartada pelo carregador) dá o mesmo período republicado como comparativo do ano seguinte, com defasagem **fixa de 365 dias** — 1.060.295 pares, 682 companhias, taxa **estável em 4,2%–7,6% de 2013 a 2025**. O alvo morreu depois, por **vazamento de observabilidade** (ver E.1), não por censura | O IPE não é mais necessário para esta linha. O que falta é sinal, não dado |
| **Gerencial × contábil como alvo** | 5 emissores não dão amostra | Escala via IPE (~USD 12 de OCR para 40–60 não-financeiras), ancorada na **Res. CVM 156/2022**, que obriga conciliação de LAJIDA. Frente separada e exploratória |
| **Viés de sobrevivência** | 277 de 741 companhias somem do painel; 41,2% delas em prejuízo na última declaração contra 34,1% das que ficam. A observação final **nunca recebe rótulo** (exige T+1) | Não tem correção com este dado. Torna o resultado **conservador para eventos extremos** — limitação declarada, não corrigida |
| **Escala declarada errada em `valor_reais`** *(achado em 2026-09-11, números corrigidos em 12/09)* | **Transições de escala suspeitas**, não células adjudicadas: no painel inteiro 137 transições — 123 com `vl_conta` CONTÍNUO, 13 de redenominação aparentemente real, 1 indefinida, em 43 companhias; no universo do candidato e só entre adjacentes, **132/119/12/1 em 41**. O ITR passa a declarar `UNIDADE`, a DFP segue em `MIL`, e o painel aplica os dois fielmente: erro de **1.000×**. Mais **25 linhas de FCO `trimestral`**: 16 períodos curtos (12/31/38/41 dias) e 9 semestres da derivação (183). E **15 grupos** com linha válida e anômala juntas — que contêm os **curtos**, não os semestres, e em **12** o `max` elege o curto | **Bloqueia qualquer alvo que use `valor_reais` nessas companhias**, não só o Rank 3-B. Reprovou o G0 do Rank 3-B antes de o alvo ser testado | **Inventário com evidência, esquema v2 em 2026-09-15** ([relatório](inventario_escala_cvm_2026-09-12.md), [correção](implementacao_qw1_qw8_2026-09-15.md)): **34.952 casos em 51 companhias**; adjudicação **por declaração** — **3.401 casos, 6.456 declarações, 111 documentos em 35 companhias**, todas `PENÚLTIMO`, só balanço. A v1 dizia 10.261: 6.736 tinham só **zero** como prova e 292 declarações eram condenadas por extrapolação. Direção 2.430 `MIL` × 971 `UNIDADE`: correção em bloco numa direção só continua proibida. O desempate é a DFP anual: DRE/DFC trimestral fica indecidível por falta de instância auditada do mesmo período. Aplicar exige contrato próprio no padrão do §3.3 (guarda que **falha** se a CVM republicar). Nunca excluir a célula nem corrigir em silêncio. [Validação](validacao_rank03b_consumo_operacional_2026-09-11.md) |
| **Rank 3-B — início de consumo operacional persistente** | **NÃO MEDIDO.** `Y = 1` se `FCO(q1)+FCO(q2) < 0` **e** `FCO(q3)+FCO(q4) < 0`, em não financeiras com FCO_TTM > 0 em D. G0 reprovou por escala antes de T1 rodar. O instrumento levou **duas** ondas de correção, cada uma depois de conferência independente: 12/09 (R1–R5 — devolvia `PRONTO PARA CHALLENGER` com os baselines falhos) e 15/09 (QW3–QW7 — G1 aprovava por existência, e o horizonte civil sobre rótulo fiscal aceitava trimestre já iniciado em 322 observações reais) | **REPROVADO EM G0 — rodada invalidada.** Não diz nada sobre a qualidade do alvo | Corrigir a escala (linha acima) e **pré-registro novo** — este foi consumido; retomar o mesmo alvo depois de mexer na população é ajustá-la tendo visto o resultado. **A previsão registrada de que `fco_ttm_sobre_sd8` reprovaria T1 segue SEM TESTE** e deve ser transportada literalmente |
| **CAND-02, CAND-03, CAND-04 e Rank 5 — treinar antes de haver gold** | Em todos, o bloqueio é o mesmo em quatro roupas: **o lado que tem `n` não tem rótulo**. Mapa exato em 4,951%, setor em 5/741, zero vintages numéricos, 20 releases, e "quatro correções curadas" que são **um episódio-raiz em um emissor** | **INDECIDÍVEL — não é medição negativa.** Detalhe, medições e preço de entrada de cada um em **§F** | Ver **§F**. Nenhum deles reabre com modelo novo; todos reabrem com **gold anotado** |

---

## B. Recuperação e chunking

| Ideia | Medição | Veredito | O que reabriria |
|---|---|---|---|
| **Fusão E3 + E4** (RRF e intercalado) | RRF **8/15** · intercalado **8–9/15** · E4 puro **11/15**, todos em top-5 | **Negativo.** Dividir cinco vagas entre duas listas expulsa o trecho que só uma delas achou | Orçamento de contexto de **dez** vagas — outra comparação, não comparável com E1–E4 |
| **Descartar tabela da cauda de sobreposição** (1ª correção do chunk órfão) | Zerou os 101 chunks órfãos e derrubou a exatidão factual **E2 0,467 → 0,267** | **Negativo.** A duplicação do overlap era **também** rede de segurança | Nada — a correção final (recolocar o cabeçalho) domina esta em todos os eixos |
| **`recall@5` por página como métrica de chunking** | Contava como acerto o chunk órfão, que não conseguia responder | **Métrica enganosa para esta decisão.** Para julgar chunking, medir se o **valor** está no top-5 | Nada. Vale como métrica de recuperação, não de chunking |
| **Exatidão comparativa como meta alcançável no top-5** | Teto estrutural: perguntas com **todos** os valores presentes — E1 1/10 · E2 2/10 · E3 2/10 · E4 5/10 | O sistema opera contra um teto de 1–5, não de 10. **Não é regressão do chunker** (medido nas três rodadas) | Subconsulta com orçamento **por banco** em vez de top-5 global |
| **CAND-02 — implementar redline semântico antes do gold humano** | 20 documentos → 15 pares, mas teste purgado tem **5 clusters**. Dupla leitura, adjudicação e estudo de tempo ausentes; dois especialistas convergiram | **Não implementar ML agora.** O aprendido é INDECIDÍVEL e a utilidade do determinístico não foi demonstrada | Dupla leitura completa dos 15 pares, ≥30 P2 adjudicados e estudo de tempo; provar B1 antes de executar challenger |

---

## C. Provedores de LLM

| Modelo | Medição | Veredito |
|---|---|---|
| **Gemma 4 31B** | Pior acerto do lote (**0,4**) e maior latência entre as que terminaram (71,9 s). `reasoning_effort=high` **nunca convergiu** — gerou `<thought>` sem `Final Answer` em duas tentativas, com 55 min de timeout | Descartado |
| **Gemini 3.7 Flash** | Cota gratuita de **20 req/dia**; uma rodada de 15 perguntas consome 40–56 chamadas. Em 3 perguntas: 2/3 corretas, 1/3 morreu em 503 | **Sem dado suficiente** — não é descarte por desempenho |
| **DeepSeek V4 Flash** | Acerto **0,40–0,60** contra 0,88 do ramo ativo; risco de resposta de vários minutos | Descartado |
| **`gemini-3.5-flash-lite` com `reasoning_effort=high`** | Acerto 0,84 × **0,88** do `low` — dentro de um desvio-padrão, por mais custo | **Considerado, não escolhido** |
| **Azure OpenAI** (gate G1) | Recurso não disponível na assinatura de estudante | Reservado ao pré-deploy; créditos vão para hospedagem |

---

## E. Modelos reprovados pelo próprio baseline (debate de 2026-08-26)

Quatro rodadas entre um cientista de dados e um analista de *equity research*,
com verificação independente de cada número pela sessão principal. **Os dois
retiraram as próprias propostas.** Relatório completo:
`resultados/debate_modelo_util_2026-08-26.md`.

> **A formulação exata do veredito:** nenhuma proposta sustentou um componente
> aprendido **superior ao seu próprio baseline**. Não é que nada de útil saiu —
> o que saiu foi a régua que reprovou todas.

| Ideia | Baseline que a venceu | O que reabriria |
|---|---|---|
| **E.1 — Selo de risco de revisão** (prever qual número citado será revisado) | Barra de falsificação **pré-registrada pelo próprio autor**: captura no top-20% dentro da declaração = **0,284** contra barra 0,40. A manchete original (0,847 / 75,6%) era **vazamento de observabilidade** — a feature usava o rótulo da declaração de D−90, que só se torna observável em D+365 | Nada com este dado. O fenômeno é real (bancos revisam 12,3% da manchete contra 7,8% do painel) mas **não é antecipável** |
| **E.2 — Evento legal de crédito** (RJ/falência/liquidação em T+k) | Coluna crua **`pl_ativo`, AUC 0,8765** > modelo 0,8514. Lacuna T2 +0,163/+0,247 reprova. **31 de 32 eventos nunca pareceram saudáveis**; mediana de 15 trimestres de sinal vermelho antes | Não existe *default* surpresa para prever. Reabre só com dado **fora** de balanço trimestral |
| **E.3 — Estresse agregado do devedor → inadimplência do sistema** | Nada. ρ **+0,687 em nível** (tendência comum) e **+0,076 em 1ª diferença** (p = 0,58) | Nada. A correlação some inteira ao detrendar |
| **E.4 — Modelo dentro do recorte já estressado** | **`liq_corrente` cru**: AUC intra 0,754 × 0,692 do modelo, e lacuna +0,040 × +0,154. O modelo compra 2,7 pontos de precisão pagando com memorização de emissor | Nada |
| **E.5 — Camada de abstenção aprendida** (*selective prediction* sobre extração) | **Guarda determinístico RN02 que já existe**: risco 0,007 contra 0,081 do seletor aprendido. McNemar ao nível da pergunta: 3 discordâncias, **p = 1,0000** | Volume de rótulo. Existem **222** células conferíveis (11 conceitos × 5 bancos × 4 trimestres), não 186.701. Reabre com **mais documentos**, não com mais orçamento |
| **E.6 — Mapeador semântico de contas em escala** | **`JOIN ON ds_conta_norm`**: macro-F1 **0,9923** contra **0,7743** do aprendido; McNemar **205 × 1, p = 4,0e−60**. O modelo é *ativamente pior*: **208 falsos positivos**, que é a falha exata que a RN09 existe para impedir | Nada como ML. **A entrega vale como dados** (ver abaixo) |

### E.6 é o caso mais instrutivo, e não é um fracasso da entrega

O mapeador **é a melhor coisa que passou pelas quatro rodadas** — destrava 85%
de 5,55 M de linhas para 741 companhias e escapa do teto de 20 documentos. Mas:

- As 300 triplas mais frequentes vêm de **um único plano de contas**, usado por
  **696 das 741** companhias — é o plano padrão da CVM, **que a CVM publica**.
  Cobrir 85% das linhas é transcrever **208 contas de um documento público**:
  ~7 horas de um analista júnior.
- Os 11 conceitos atuais são realizados por **18 descrições normalizadas
  distintas, nenhuma ambígua** — inclusive a armadilha fundadora do G4 (`3.09`
  = lucro líquido em 3 bancos, resultado antes das participações em 2), que
  **a descrição separa sozinha**.
- O gargalo real não é rotular: é o **G4 por conceito**, humano e sem atalho,
  agora sobre 741 companhias em vez de 5.

**Conclusão: entregar como curadoria + join declarado, nunca como modelo.**

### A restrição estrutural que apareceu quatro vezes

> **O lado que tem `n` não tem conteúdo bancário; o lado que tem conteúdo
> bancário tem 20 documentos.**

| Conceito | Painel (5,55 M linhas, 741 cias.) | Corpus (20 PDFs) |
|---|---|---|
| Basileia / CET1 | **0 linhas** | 20/20 |
| Margem financeira | **0 linhas** | 17/20 |
| NPL / inadimplência | 1 emissor | 17/20 |
| Índice de eficiência | 1 emissor | 20/20 |
| **Fluxo de caixa (DFC)** | **não existe** — painel só tem BPP, BPA, DRE | — |

### Duas regras de método que saíram daqui e valem para sempre

1. **"Denominador não é rótulo."** Pegou os **dois** especialistas: 186.701
   células do painel contadas como rótulo quando o usável era **222** (840×); e
   37.540 triplas contadas como rótulo quando existem **198** (190×). Item a
   classificar não é exemplo rotulado.
2. **Construa o baseline trivial ANTES do modelo.** Em E.6 a linha de base
   venceu 205 a 1 — e só descobre isso quem a constrói primeiro.

### O que este negativo NÃO autoriza concluir

- **Não** conclui que ML é inútil em research financeiro. Conclui que **nesta
  base** não há tarefa em que o componente aprendido bata o baseline trivial dela.
- **Não** conclui que o produto não tem valor: RAG + extração + abstenção
  determinística é o ouro do analista, e **não tem ML**.
- **Reabre com dado novo, não com modelo novo** — DFC, preços *point-in-time*,
  ou documentos além dos 20. As três reabrem coisas diferentes.

---

## C-bis. B-DFC-01J-M — custo de captação um trimestre à frente (2026-09-09)

> **⛔ AVISO DE ESTADO (2026-09-11) — leia antes de usar qualquer número desta
> seção.** Esta seção foi escrita quando o **instrumento de medição estava
> quebrado**. Uma [revisão independente](revisao_independente_b_dfc_01j_2026-09-10.md)
> mostrou que `construir_j` **fabricava os limites de J** (achado F1), e uma
> [conferência posterior](parecer_correcao_b_dfc_01j_2026-09-11.md) achou mais
> seis defeitos no auditor. Os números abaixo ficam como **registro do que foi
> publicado**, não como resultado corrente.
>
> **O que muda na leitura desta seção:**
>
> | Afirmação abaixo | Estado em 2026-09-11 |
> |---|---|
> | "**G0 FOI RESOLVIDO**, pelo lado ruim" | **Falso hoje.** G0 voltou a reprovar: 24 dos 25 pacotes com J **não identificado**, 0 identificados, 0 limitados |
> | **G2 = 1,0464** | **Não é mais produzido.** O gate devolve "alvos insuficientes para medir ruído/sinal" |
> | "**J como ponto exato foi de 5 para ZERO**" | Continua certo — e **J como intervalo também foi a ZERO** (era 15). A série utilizável saiu de 69 pares para **zero** |
> | "**~16 emissores**" na série diagnóstica | **Cálculo invalidado por F3** e posto em quarentena: segue publicado em `sensibilidade.json` com `decidivel: false` e `calculo_de_poder_invalidado_por: "F3"`. Publicado e invalidado, **não** "deixou de existir" |
> | "os ~16 só valem para **um J limpo que não existe**" | **Não repetir.** A revisão derrubou a prova de não separabilidade **universal** (F5) e achou juros e câmbio **separados** na nota de movimentação de dívidas subordinadas do Bradesco |
> | "Reabre com outro estimando, restrito às rubricas **sem crédito em nenhum trimestre**" | Critério **enfraquecido**: das 5 rubricas não identificadas, 3 têm crédito observado e 2 (do BB) não — mas ausência de crédito **não é prova** de pureza, e a pista viável hoje é **por família econômica** (subordinadas), não por ausência de crédito |
>
> **O que continua valendo:** o treino segue suspenso; as rubricas **não**
> voltam para J sem prova; e as duas regras de método da seção — *fechamento
> aritmético não é conformidade contratual* e *exigência de amostra é
> propriedade da dispersão medida, não do universo*. Estado atual e próximos
> passos: o instrumento levou **três** ondas de correção —
> [C1–C6](implementacao_c1_c6_b_dfc_01j_2026-09-11.md), depois
> [R-C5/R-C6/R-SUPORTE](implementacao_rc5_rc6_b_dfc_01j_2026-09-11.md) achadas
> por [conferência independente](conferencia_independente_c1_c6_b_dfc_01j_2026-09-11.md).
> **F3, o redesenho do cálculo de poder, segue sem correção** — em quarentena
> que hoje **veta** a aprovação de G3, em vez de só estar escrita ao lado dela.

**Sétimo candidato em que o baseline trivial vence.** Alvo pré-registrado
`y = ln(J(t+1)/J(t))` sobre a série documental de J (3 emissores, 71 pares
emissor-trimestre, 2018T1–2026T1). Relatório:
`prontidao_b_dfc_01j_modelo_2026-09-09.md`. AGENTS.md §3.17.

| O que foi medido | Valor | Limiar |
|---|---:|---:|
| **G0** rubricas com conformidade não demonstrada (antes de resolver) | **3** | 0 |
| **G2** ruído/sinal depois de tornar J conforme | **1,0464** | < 0,10 |
| G3 melhoria mínima detectável (bootstrap por emissor) | **130,6%** do MAE | ≤ 20% |
| Emissores necessários — com a rubrica suspeita dentro | ~128 † | 3 disponíveis |
| Emissores necessários — **sem** ela (série diagnóstica) | **~16** | 3 disponíveis |
| MAE macro: B0 sem mudança × sazonal × mediana 4T | **0,1579** × 0,2151 × 0,1771 | — |
| Acerto de direção: "sempre sobe" × sazonal × mediana | **0,6491** × 0,5652 × 0,5455 | — |
| G2 ruído do rótulo sobre sinal | 0,021 | < 0,10 ✅ |

**Duas coisas para não repetir.** (1) *Fechamento aritmético não é conformidade
contratual* — três rubricas incluídas em J vêm credoras, e despesa de captação
por competência não é crédito; a soma fechava. (2) *O gargalo era emissor, não
trimestre* — a onda levou a série de 50 para 71 pares e G3 não se moveu, porque
três clusters não sustentam inferência por mais trimestres que tenham. (3)
*Exigência de amostra não é propriedade do universo, é da dispersão medida* — o
"~128 emissores" foi publicado como limite dos bancos existentes e era, em boa
parte, sintoma do defeito do G0.

**G0 FOI RESOLVIDO em 2026-09-10, pelo lado ruim.** A leitura das notas mostrou
que a parcela cambial **não é separável**: a maior sub-rubrica do `Recursos de
Mercados Interbancários` do Itaú é declarada em moeda estrangeira, no 1T2020 o
saldo dela subiu 30,1% enquanto a linha de juros saltou 21.119 (casam dentro de
8%) e a taxa contratual de teto 9,60% proíbe a leitura alternativa. As duas
rubricas com crédito impresso viraram `_NAO_IDENT` e **J como ponto exato foi de
5 para ZERO**.

| | Conforme (agora) | Anterior, não conforme |
|---|---:|---:|
| G2 ruído/sinal (limiar < 0,10) | **1,0464** ❌ | 0,0214 ✅ |
| Alvos | 25 | 55 |
| Emissores na população | **2** | 3 |

**A folga de 48× do G2 era comprada pelo defeito.** Evidência:
`artefatos/b_dfc_01j/prontidao/sensibilidade.json`.

† O `~128` é da rodada de gate original, sobre a série contaminada, e **não
reproduz** contra o artefato de hoje: reconstruindo aquele estado, o
`sensibilidade.json` v2.0.0 devolve **102**. A diferença é a guarda de acumulado
que encolhe, que retirou dois 4T derivados. Fica como registro do que foi
publicado, não como número corrente.

**O que reabriria, agora que o G0 fechou.** **Não é mais emissor** — cada emissor
novo entra com o mesmo defeito de apresentação, e os ~16 da série diagnóstica só
valem para um J limpo que não existe. Reabre com **outro estimando**, restrito às
rubricas sem crédito em nenhum trimestre — **ciente de que esse critério não
seleciona baixa dispersão** (CV vai de 0,11 a 0,96, e a pior é uma rubrica não
cambial que segue em J, acima das duas cambiais removidas: 0,68 e 0,60), com pré-registro e G0 próprios e sem herdar número — e com a ressalva
de que ausência de crédito **não é prova** de estar limpo. E `B3`, o benchmark
econômico (meta Selic *point-in-time*) exigido pelo contrato, segue **não
executado**: superar persistência sem superar a taxa de juros não diz nada sobre
custo de captação, porque J é estoque × taxa.

---

## F. Candidatos parados por falta de gold, amostra ou vintage — não por medição negativa

**Esta seção é diferente de todas as anteriores, e confundir as duas é o erro
mais caro do registro.** Em A, B, C e E há um número que reprovou a ideia. Aqui
**não há número nenhum**: o estado científico é **INDECIDÍVEL** e a decisão de
engenharia é **NÃO IMPLEMENTAR ML AGORA**. Ninguém mediu que a ideia é ruim —
mediu-se que ela **não é decidível** com o gold, a amostra e o vintage que
existem. São candidatos vivos, com preço de entrada declarado.

> **Não cite nenhuma linha desta seção como "foi medido e não funciona".** A
> formulação correta é "não foi medido, e eis o que falta para medir".

Consolidado a partir de AGENTS.md §3.9–§3.12 e §3.16, em 2026-09-11, quando
aquelas seções saíram do plano por serem registro de medição, não regra de
conduta. Cada relatório datado continua sendo a fonte.

| Candidato | O que é | Por que é indecidível hoje | Preço de entrada para decidir |
|---|---|---|---|
| **CAND-02 — redline semântico** ([relatório](validacao_cand02_redline_2026-08-27.md) · [pré-registro](pre_registro_cand02_redline_2026-08-27.md)) | Compara releases consecutivos e ordena mudanças por **prioridade de leitura** | A estrutura **passou**: 20 docs → 15 pares, split purgado 5 dev · 5 embargo · 5 teste, zero PDF compartilhado. Faltam as três evidências **humanas**: dupla leitura, adjudicação e estudo de tempo. Nenhum modelo foi carregado | Dupla leitura completa dos 15 pares + adjudicação + **≥30 mudanças prioridade 2** + estudo humano contrabalanceado. O determinístico precisa antes de zero FN crítico, recall P2 ≥0,90, nDCG@20 ≥0,80 e procedência perfeita. Só então o aprendido roda contra B0/B1, exigindo ΔnDCG@10 ≥+0,10, ΔnDCG@20 ≥+0,05, ganho 5/5 e `N@R90` 20% menor. Generalizar exige 30–34 pares e dez emissores |
| **CAND-03 — triagem de anomalias contábeis** ([relatório](validacao_cand03_anomalias_contabeis_2026-08-27.md) · [pré-registro](pre_registro_cand03_anomalias_contabeis_2026-08-27.md)) | Ordena episódios contábeis por prioridade de leitura (E2). Erro/reapresentação (E1) e fraude (E3) são estimandos **separados** e não servem de proxy | O painel tem 5.552.787 linhas mas só **23.346** companhia–trimestres; mapa exato em **4,951%**; setor em 5 de 741 companhias; 698 chaves semânticas duplicadas (587 conflitantes); **zero grupos com mais de um vintage numérico**. As quatro correções curadas são **um episódio-raiz em um emissor**, não quatro rótulos. `VERSAO>1` não localiza a conta alterada nem prova erro | Shadow prospectivo: 30 releases completos, seguindo até ≥30 com P1/P2 e rubrica estável, teto 150. Congelar snapshot, baseline, recall e break-even. Confirmatório `N=max(100, N_poder, N_50+)`, primária de minutos/itens sob 100% de recall crítico e recall P1/P2 ≥0,90. ML só avança com procedência perfeita e economia cujo IC supere `max(break-even+margem, 20%)` |
| **CAND-04 — previsão de fundamentos** ([relatório](validacao_cand04_previsao_fundamentos_2026-08-27.md) · [pré-registro](pre_registro_cand04_previsao_fundamentos_2026-08-27.md)) | Prospective ROA em bps: `10.000 × lucro(T+1) / ativo(T)`, com B0 persistência, B1 sazonal T−3, B2 mediana 4T, B3 mediana dos três | **A rodada A está REJEITADA/INVALIDADA, mas a fórmula econômica NÃO foi refutada.** G0 integridade e G1 point-in-time falharam. O top 1% explica **83,55%** do erro; **23 linhas** (0,71%) com saltos de ativo próximos de 1.000× explicam **61,64%**. Rastreamento confirmou trocas `MIL`↔`UNIDADE` e subtração 4T contaminada | Preservar `DT_RECEB`/`ID_DOC`/todas as versões; validar escala **antes** da derivação; reconciliar 4T; completar setor; congelar teste novo e rodar baselines/intervalos PIT antes de qualquer challenger. **Divergência publicada entre os especialistas:** Ciência de Dados prefere **A2** corrigido, Finanças prefere **B** (lucro dos controladores em R$, materialidade em bps do PL atribuível). Ambos são estimandos novos e **não herdam número de A** |
| **Rank 5 — divergência gerencial × contábil** ([relatório](validacao_rank05_divergencia_gerencial_contabil_2026-08-27.md) · [pré-registro](pre_registro_rank05_divergencia_gerencial_contabil_2026-08-27.md)) | Fila de reconciliações gerenciais que merecem revisão. **L e K são separados** | LAJIDA/LAJIR/EBITDA/EBIT como palavra inteira aparece em **0/20** releases — G0-L reprova. A ponte de resultado ajustado aparece em 20/20, mas isso passa só G0-K: **contagem de ponte é candidato à anotação, não gold**. G1 reprova por não haver data original de publicação e versão. G2/G3/G4 reprovam por falta de dupla leitura e por 20 releases/5 emissores contra as barras de 30/10 | ≥30 releases e ≥30 P2/P3 adjudicados; rubrica própria; concordância ponderada ≥0,70; vintage em 100%; extrator auditado; B0–B4 congelados; split temporal/emissor. Confirmação exige `N=max(100, N_poder, N_50+)`, ≥10 emissores, recall P3=1, recall P2/P3 ≥0,90, `N@R90` 20% menor, ΔnDCG@20 ≥+0,05 e procedência perfeita. **K1 não herda identidade, regra nem gold de LAJIDA/LAJIR** |
| **Etapa 19 — FCF yield × retorno futuro** ([relatório](validacao_etapa19_fcf_yield_2026-09-08.md) · [pré-registro](pre_registro_etapa19_fcf_yield_2026-09-08.md)) | Terceiro e último destravador nomeado pelo negativo de E ("DFC, preços PIT, ou documentos além dos 20") | **T1 não reprovou pela primeira vez neste projeto — mas também não aprovou.** Os cinco componentes ficaram abaixo de 0,15 na leitura pontual (`valor_mercado` 0,120 é o maior), porém o bootstrap por companhia (2.000 reamostragens) dá **32% de chance de a amplitude verdadeira de `valor_mercado` exceder 0,15**. A amostra tem só 1.908 observações e 19 trimestres porque a `composicao_capital` da CVM só existe a partir de 2020. G0 de preço **aprovou** (4,19% de suspeitas contra limiar de 5%) | Amostra maior por fonte **não frágil** de ações pré-2020, ou G0 próprio para a derivação por LPA que descarte baixa precisão **antes** de medir. Ver em D por que a derivação por LPA foi examinada e recusada |

### Um caminho de reabertura examinado e explicitamente NÃO tomado

A CVM publica Lucro Básico por Ação (`cd_conta 3.99.01`) desde 2011, o que em
tese permitiria derivar ações em circulação (`lucro_controladores / LPA`) antes
de 2020 e resgatar o T1 ambíguo da Etapa 19. **Não foi feito, de propósito:** o
campo vem com a precisão que a própria companhia declarou — 2 casas decimais na
maioria dos arquivamentos — e arredonda a `0,00` justamente para companhias de
LPA pequeno, produzindo ações derivadas indeterminadas ou com erro relativo
enorme. É a mesma classe de defeito do CAND-04 (trocas de escala silenciosas que
só aparecem no residual).

**Usar essa derivação para resgatar um T1 ambíguo seria ajustar a população
depois de ver o resultado, e o pré-registro proíbe.** Registrado aqui para que a
próxima sessão não "descubra" o atalho e o tome sem ver a razão da recusa.

---

## D. O que NÃO está neste documento

Coisas **abertas**, que ninguém mediu ainda — não confundir com beco sem saída:

- **XGBoost e CatBoost** seguem sem teste. A expectativa de ganho é baixa (o
  LightGBM empatou e o ajuste rendeu zero), mas expectativa não é medição.
- **Controle setorial em eventual C2** — a medição de A.2 é sobre o alvo de
  prejuízo e **não transfere**; o C1 foi rejeitado antes do treino.
- **Detecção de prospectivas parafraseadas** — lacuna conhecida da RN07,
  registrada em `robustez_modelo_2026-08-24.md` (item 6). Falta conjunto
  adversarial, não falta medição.
- **Liquidez e *free float*** — `CATEG_REG` resolve "pode ter ação negociada",
  não negociabilidade.

---

## Procedência

Consolidado em 2026-08-26 a partir de: `debate_alvo_ml_2026-08-26.md` ·
`debate_modelo_2026-08-25.md` · `robustez_modelo_2026-08-24.md` ·
`revisoes_modelo_2026-08-23.md` · `teto_comparativas_2026-08-23.md` ·
`comparacao_llm_2026-08.md` · `comparacao_fatos_x_*.json` · `gate.md` ·
AGENTS.md §3.1-bis, §3.4, §3.5, §3.6, §3.7.

Os relatórios de origem continuam sendo a fonte — este arquivo é índice e
resumo, e em caso de divergência **o relatório datado vence**.
