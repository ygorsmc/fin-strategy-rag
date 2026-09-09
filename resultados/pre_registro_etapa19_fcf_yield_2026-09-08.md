# Pré-registro — FCF yield × retorno futuro (etapa 19)

**Escrito ANTES de qualquer medição de desempenho.** Nenhum modelo carregado,
nenhum baseline calculado, nenhum T1 rodado. Conforme §3.7, o que este documento
declarar não pode ser ajustado depois de ver resultado: mudar limiar,
normalizador ou população cria um candidato NOVO, com pré-registro próprio e sem
herdar número nenhum daqui.

## 1. Por que este candidato é diferente dos que morreram

O §3.8 nomeou três condições de reabertura — *"DFC, preços point-in-time, ou
documentos além dos 20"*. DFC entrou em §3.13, documentos em §3.15. **Preço é o
terceiro e último**, e é a única família de dado do projeto que ainda não foi
medida e reprovada.

**A diferença estrutural, e é ela que justifica gastar o esforço:** todo alvo que
morreu em T1 era uma **transformação aritmética de grandezas contábeis que as
features também continham**.

| Candidato | Alvo | Nível que virou baseline |
|---|---|---|
| Corte de ROA | ΔROA | `roa_ttm` (0,317) |
| C1 | ΔROA / sd₈ | `sd8`, o próprio normalizador (0,180–0,247) |
| Rank 3 | Δaccrual | `accrual` (0,266) e `conversao` (0,229) |

**Retorno de mercado é EXÓGENO ao painel contábil.** Ele não é função das contas
da CVM, então o mecanismo que matou os três — variação de grandeza que reverte à
média fabricando o próprio nível — **não se aplica da mesma forma**. É a primeira
vez que isso vale neste projeto.

## 2. A armadilha nova, declarada antes de medir

Não estou otimista por decreto. Há um vínculo mecânico **novo**, e ele é a
principal razão pela qual este candidato pode reprovar em T1:

> Se o alvo é `P(t+4)/P(t) − 1` e a feature é um múltiplo com preço no
> denominador (FCF/P, E/P), então **`P(t)` é compartilhado entre alvo e
> feature**. Preço baixo hoje eleva mecanicamente o múltiplo *e* o retorno
> futuro, se preço reverte. É a crítica clássica de que "fator valor é em parte
> reversão de preço" — e T1 vai pegá-la se ela morder.

**Predição registrada (§3.7 exige nomear o desfecho mais provável antes de
medir):** o componente de maior risco em T1 é **valor de mercado / nível de
preço**, não o FCF. Efeito tamanho e reversão de curto prazo são dois dos fatos
mais replicados em finanças empíricas. Se a amplitude de `valor_mercado`
estourar 0,15, o candidato morre exatamente como os três anteriores, e o registro
dirá que a regra durável vale também para alvo exógeno.

## 3. G0 — integridade de preço, gate que roda ANTES de T1

**Preço do COTAHIST não é ajustado por evento corporativo.** Um desdobramento de
2:1 aparece como retorno de −50% que não é econômico. Isso é a **mesma classe de
defeito** que invalidou a rodada A do CAND-04 (§3.11): trocas `MIL`↔`UNIDADE` e
saltos de ativo próximos de 1.000× em 23 linhas explicavam 61,64% do erro.

A lição do CAND-04 é literal e vale aqui: *"as 23 linhas foram descobertas pelo
residual e **não podem ser removidas** para salvar o teste. Congelar qualquer
quarentena **antes** de um teste novo."* Então a quarentena vai congelada agora:

**Regra de quarentena, congelada antes de medir.** Uma observação é marcada
`suspeita_evento_corporativo` se, entre `t` e `t+4`, a razão `P(t+4)/P(t)`
estiver a menos de 2% de uma razão redonda de desdobramento ou grupamento
— `1/N` ou `N` para `N ∈ {2, 3, 4, 5, 10, 100}` — **ou** se `|retorno| > 300%`.
A regra é sintática e vale para todas as observações, independentemente do
resultado.

**Limiar do gate:** se as suspeitas passarem de **5%** das observações, G0
**reprova** e o candidato é **INDECIDÍVEL por integridade de dado** — o mesmo
veredito do CAND-04, e não se prossegue para T1 com base contaminada. Abaixo de
5%, as suspeitas são **excluídas da amostra primária** (não corrigidas) e o
resultado é publicado com e sem elas.

**O que G0 não é:** não é licença para caçar outliers depois. Nenhuma exclusão
adicional entra depois de ver o residual.

## 4. Definições

**Âncora point-in-time.** `P(t)` é o fechamento (`PREULT`, lote padrão
`tpmerc=010`) do **primeiro pregão em ou depois de `min(documentos.dt_receb)`**
da companhia-trimestre. Nunca antes: o §3.13 mediu que 41% dos documentos chegam
mais de 45 dias depois do fim do exercício, e usar `dt_refer` enxerga o
formulário antes de ele existir.

**Ticker** resolve por CNPJ contra `fca_cia_aberta_valor_mobiliario` (RN11 —
nunca por nome), respeitando `Data_Inicio/Fim_Negociacao`, e a série da companhia
é a de **maior volume financeiro** entre ON/PN/Unit.

**Feature central (a que só existe com DFC + preço):**

```
fcf_ttm(t)    = FCO_ttm(t) − |capex_ttm(t)|        (DFC, isolado por trimestre)
valor_mercado = P(t) × ações_em_circulação(t)
fcf_yield(t)  = fcf_ttm(t) / valor_mercado(t)
```

**Alvo.** `ret(t) = P(t+4Q)/P(t) − 1`, e o rótulo é o **quintil superior de
`ret` DENTRO de cada trimestre** — corte transversal, não relativo à própria
companhia. Prevalência 0,20 por construção. O corte transversal é deliberado: é
o que o C1 errou ao normalizar pela própria companhia (§3.7).

**População.** Companhias com ticker válido e série de maior volume; FCO isolado
disponível para os quatro trimestres da janela TTM; `valor_mercado > 0`;
`dt_receb` observável. Sem filtro de setor e sem filtro de lucratividade — os
dois já se mostraram fontes de contaminação (§3.6, `is_banco`).

**Censura.** Companhia-trimestre sem `P(t+4)` observável é **censurada**, não
imputada, e a contagem de censurados é publicada.

## 5. Baselines obrigatórios — construídos ANTES do modelo

§3.8: *"construa o baseline trivial antes do modelo"* — em E.6 a linha de base
venceu 205 × 1.

| | Baseline | Por que está aqui |
|---|---|---|
| **B0** | `valor_mercado` (log) | **candidato mais provável a vencer** — efeito tamanho |
| **B1** | `−P(t)` | reversão de preço puro, sem contabilidade nenhuma |
| **B2** | `fcf_yield` cru, sem modelo | o próprio fator; modelo tem de bater o fator |
| **B3** | `e_p` = lucro_ttm / valor_mercado | múltiplo clássico, para separar FCF de lucro |
| **B4** | retorno passado 4T | momento/reversão, o fator que compete de graça |

## 6. Testes e limiares — declarados agora

| Teste | Pergunta | Limiar | Se reprova |
|---|---|---|---|
| **G0** | O preço está contaminado por evento corporativo? | suspeitas < **5%** | INDECIDÍVEL por dado; não roda T1 |
| **T1** | O alvo fabrica o próprio baseline? | amplitude < **0,15** em **cada** componente | encerra antes do treino |
| **T2** | Há sinal ou só ordenação de emissor? | AUC agregada − intra-companhia < **0,12** | encerra |
| **T3** | O modelo bate o melhor baseline? | ≥ **+0,02** de AUC, p < 0,05 em teste pareado por fold | não implementar |

**Componentes que vão a T1 obrigatoriamente** (§3.7: *"se o alvo contém nível,
volatilidade, média setorial ou qualquer outro normalizador, **todos** entram"*):
`valor_mercado`, `P(t)`, `fcf_ttm`, `fcf_yield`, `ativo_total`. `P(t)` e
`valor_mercado` entram porque são componentes mecânicos do alvo; os outros porque
são a feature e seus insumos.

**T2 usa split temporal com purga e embargo**, como a etapa 10 exigiu depois da
auditoria de 2026-08-24 — sem purga o rótulo de `t` alcança o teste.

## 7. O que este experimento NÃO promete

- **Não** é recomendação de investimento. Qualquer resultado é medição sobre
  dado histórico e a RN05/RN07 continuam valendo integralmente: nada disso vira
  resposta sobre companhia nomeada no caminho interativo.
- **Não** herda nada do C1, do Rank 3 ou do CAND-04.
- **Não** é o mesmo que "múltiplos de mercado" da etapa 19 como *feature de
  produto* (P/L e P/VPA citáveis no RAG). Aquilo é entrega separada, com conjunto
  próprio, e não depende deste resultado.
- Se T1 reprovar, o registro dirá que a regra durável de §3.14 vale **também
  para alvo exógeno**, o que é achado publicável — não fracasso a contornar.

## 8. Reprodução

```bash
python -m scripts.baixar_precos_b3 --anos 2014-2025      # COTAHIST + FCA, hash pinado
python -m scripts.auditar_etapa19_fcf_yield --painel artefatos/cvm_treino.duckdb
```

Lacuna declarada de origem: o **BTG (`022616`) não tem ticker** porque
`fca_cia_aberta_valor_mobiliario` traz `Codigo_Negociacao = '000000'` de 2023 a
2026. O código correto é `BPAC11`, mas cravá-lo à mão seria a correção silenciosa
que o §3.3 proíbe; a companhia entra em `descartados` e fica fora do universo até
haver correção com procedência.
