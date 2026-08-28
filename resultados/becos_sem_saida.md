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
| **CAND-03 — detector aprendido de “anomalia” antes de gold e shadow** | 5,55 M células → 23.346 companhia–trimestres; quatro correções são um episódio-raiz; nenhum gold E2/tempo; mapa 4,951%; setor 5/741; painel sem DFC/`DT_RECEB` e sem vintages numéricos. Dois especialistas convergiram | **Não implementar ML agora; INDECIDÍVEL.** Raridade, erro, prioridade de leitura e fraude não são proxies. Nem o baseline determinístico demonstrou utilidade | E2 prospectivo: snapshots imutáveis; piloto 30–150 releases até ≥30 releases P1/P2; baseline e recall congelados; confirmatório `N=max(100,N_poder,N_50+)`. Passar o piloto autoriza testar ML, não usar no produto |
| **CAND-04A — prospective ROA no painel as-restated atual** | 3.218 releases; B3 MAE 950,94 bp × mediana 57,80. Top 1% = 83,55% do erro; 23 saltos de escala = 61,64%; 4T derivado MAE 2.602,46 bp. G0/G1 falham; dois especialistas validaram o encerramento | **Experimento rejeitado/invalidado; fórmula econômica e ML indecidíveis; não implementar ML agora.** Remover as 23 pós-hoc é proibido | Novo estimando e teste: vintages/`DT_RECEB`, escala e 4T adjudicados, setor completo, baselines/intervalos point-in-time. A2 ou lucro dos controladores começam do zero |
| **Rank 5 — treinar risco de divergência gerencial × contábil no corpus atual** | 20 releases/5 bancos; LAJIDA/LAJIR = 0/20; K1 candidato = 20/20 e 31 páginas, mas sem gold, PIT ou workflow | **ML INDECIDÍVEL; não implementar agora.** Ponte encontrada não é rótulo nem réplica independente | K1 separado: ≥30 releases e ≥30 P2/P3 adjudicados; vintage, extrator auditado e B0–B4. Confirmatório ≥100 releases/10 emissores |

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
