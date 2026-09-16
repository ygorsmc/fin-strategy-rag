# Carga de fluxo de caixa (DFC) e cadastro point-in-time (2026-08-27)

> **Ressalva posterior — 2026-09-08.** A carga de DFC e datas ocorreu, mas
> não certificou vintages numéricos nem disponibilidade dos operandos de
> valores derivados. As afirmações abaixo de que qualquer candidato já
> poderia ser avaliado "point-in-time de verdade" são excessivas. Ver a
> [auditoria da retomada, §2](viabilidade_ml_dfc_2026-09-08.md#2-evidência-reproduzível-da-base-atual).
> Este relatório continua sendo o registro histórico da carga.

**Custo de API: zero.** Os 31 ZIPs já estavam em disco, baixados e pinados por
SHA-256 em `corpus/cvm/manifesto_cvm.csv`. Não houve download, OCR nem chamada
paga — só leitura do que já estava pago.

> **Isto NÃO é um modelo de ML e não deve ser apresentado como tal.** É a
> remoção de dois bloqueios de dado que várias validações apontaram como
> condição de reabertura. O §3.8 do AGENTS.md diz textualmente: *"reabre com
> dado novo, não com modelo novo — DFC, preços point-in-time, ou documentos
> além dos 20."* Este é o primeiro dos três.

## O que estava bloqueado, e por quê

O carregador lia **três** demonstrativos — DRE, BPA e BPP — e ignorava o resto
do ZIP. Consequências medidas em rodadas anteriores:

| Bloqueio | Onde apareceu |
|---|---|
| Painel sem fluxo de caixa | `debate_modelo_util_2026-08-26.md` §Rodada 4 — *"o painel não tem DFC; para Value Investing, FCO, capex e conversão de caixa valem mais que metade da lista de frequência"* |
| Rank 3 intestável | `ranking_candidatos_ml_value_investing.md` — *"excelente alvo, mas exige incorporar DFC"* |
| "Qualidade do lucro" impossível | `validacao_cand03_anomalias_contabeis_2026-08-27.md` |
| Gate G1 (*point-in-time*) reprovado | `validacao_cand04_previsao_fundamentos_2026-08-27.md` e `validacao_rank05_...md` — falta data original de publicação |

O CAND-03 já havia registrado o diagnóstico correto: **"os 31 ZIPs já contêm
`DT_RECEB` e DFC; são bloqueios do loader, não da fonte."** Esta carga executa
exatamente isso.

## O que foi feito

1. **`DEMONSTRATIVOS_SUPORTADOS`** passou a incluir `DFC_MD` e `DFC_MI` — a CVM
   publica o fluxo de caixa em dois arquivos por método (direto e indireto).
2. **`DEMONSTRATIVOS_DE_FLUXO`** (constante nova) governa a derivação do 4T da
   RN10, que antes era literal `= 'DRE'`. Fluxo de caixa acumula dentro do
   exercício exatamente como a DRE, então o 4T também não existe como ITR e
   precisa de DFP anual − ITR de nove meses.
3. **Tabela `documentos`** — cadastro do formulário, não do fato:
   `cd_cvm, conjunto, dt_refer, versao, id_doc, dt_receb, link_doc`. Guarda
   **todas** as versões, ao contrário de `fatos_contabeis`, que mantém só a
   maior: sem a série completa não se responde "o que se sabia em D?".
4. **Falha fechado** se um cabeçalho não tiver `DT_RECEB` — painel que se diz
   point-in-time e não é seria pior que nenhum, porque o defeito ficaria
   invisível dentro de qualquer backtest construído em cima.

## Resultado da carga

| | Antes | **Depois** |
|---|---:|---:|
| Linhas em `fatos_contabeis` | 5.552.787 | **6.787.589** (+22,2%) |
| Demonstrativos | 3 | **5** |
| Fatos derivados do 4T (RN10) | — | **318.975** |
| Documentos com `DT_RECEB` | 0 | **48.123** |

Cobertura do fluxo de caixa:

| Demonstrativo | Linhas | Emissores |
|---|---:|---:|
| `DFC_MI` (indireto) | 1.219.438 | **722** |
| `DFC_MD` (direto) | 15.364 | 84 |

**FCO (`6.01`, Caixa Líquido das Atividades Operacionais) existe para as 741
companhias** — 28.836 linhas, 11.561 companhia–trimestres isolados em 728
companhias. As quatro contas de nível 2 (operacional, investimento,
financiamento, variação cambial) cobrem 741 emissores cada.

## O ganho de point-in-time, medido

| | ITR | DFP |
|---|---:|---:|
| Documentos | 35.244 | 12.879 |
| Atraso mediano entre `dt_refer` e `dt_receb` | **44 dias** | **83 dias** |
| p90 | 66 | 132 |

**19.674 documentos (41% dos 48.123) chegam mais de 45 dias depois do fim do
exercício.** Um backtest que usa `dt_refer` como data de publicação enxerga
esses formulários **antes de eles existirem**. É a falha do gate G1,
quantificada.

Republicação chega ainda mais tarde: **mediana de 74 dias** contra 45 das
versões originais (7.061 republicados de 48.123).

## Duas armadilhas novas, tratadas explicitamente

### 1. Fluxo de caixa pelos dois métodos — 5 casos, contados

A sobreposição `DFC_MD` × `DFC_MI` **não é vazia**: 5 companhia–trimestres no
painel completo (9 emissores em 2024, medido antes da carga). **Somar os dois
duplica o caixa desses emissores.** O número entra em
`RelatorioCarga.emissores_dfc_ambos_metodos` e em `avisos` — reportado, nunca
suposto zero. Quem consultar escolhe um método.

### 2. `DS_CONTA` vazio na origem — 4 linhas

`itr_cia_aberta_DFC_MI_con_2014.csv` tem 4 linhas com descrição vazia: conta
**livre** (`ST_CONTA_FIXA=N`) que um emissor criou e não nomeou, todas com valor
0,0. Descartar em silêncio esconderia dado da fonte; deixar nulo quebra a carga
(`NOT NULL`). A linha entra com o marcador `(sem descrição na fonte)` e, por não
casar com `mapa_contas`, **nunca resolve conceito** — que é o comportamento
certo pela RN09.

## Quebra de hash declarada

`validacao_c1_2026-08-26.md` pina o SHA-256 do painel de treino e determina que
divergência seja publicada. O hash anterior **conferiu exatamente** antes da
substituição — a cadeia de procedência estava íntegra.

| | SHA-256 |
|---|---|
| Anterior (pinado no C1) | `74aa28e86dfcf5d2eab50b1de62851100baffd5936ea60fff585908ebf108192` |
| **Novo** | `476a11da2382c6f2a4575de1e37cf997b93edff2b449b67d9f7b75c6adf53247` |

Qualquer reexecução do `auditar_alvo_c1.py` contra o painel novo é **nova
medição, não réplica bit a bit** — como o próprio C1 exige. A rejeição do C1
**não muda**: ela vem do vínculo mecânico entre `sd8` e o rótulo, que independe
de haver ou não fluxo de caixa no painel.

`artefatos/cvm.duckdb` (painel consultável, casado com o corpus) **não foi
tocado** — §3.5 mantém os dois separados de propósito, e mexer no consultável
mudaria o que a camada interativa responde.

## Testes

11 casos novos em `tests/test_dados_estruturados.py`
(`TestFluxoDeCaixa`, `TestDocumentosPointInTime`), com fixtures próprias que
reproduzem o formato real. Travam: DFC entra no painel; `PENÚLTIMO` da DFC é
descartado como o da DRE; escala convertida; **4T derivado com
`origem='derivado'`**; contraprova de que balanço **não** é derivado;
sobreposição MD×MI contada; `dt_receb` carregada e posterior a `dt_refer`;
todas as versões preservadas; **cabeçalho sem `DT_RECEB` falha fechado**;
ausência de cabeçalho vira aviso legível.

Suíte: **1.736 passando, zero skip** (era 1.725).

## O que isto destrava — e o que continua não destravando

**Destrava:** o Rank 3 (deterioração de conversão de caixa) passa de
*intestável* a **decidível**; qualquer candidato pode ser avaliado
*point-in-time* de verdade; "qualidade do lucro" (accrual = lucro − FCO) passa a
ser calculável com o FCO real em vez do proxy de capital de giro.

**Não destrava:** nada disso garante que o Rank 3 passe em T1/T2. Ele continua
exigindo pré-registro e os dois testes, e pode reprovar como os seis anteriores.
O que mudou é que a reprovação, se vier, será **por medição e não por ausência
de dado**.

**Continua ausente:** preços *point-in-time* e documentos além dos 20 — os
outros dois destravadores que o §3.8 lista.
