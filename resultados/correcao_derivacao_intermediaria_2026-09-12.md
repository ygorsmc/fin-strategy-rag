# Correção da derivação de trimestre intermediário — camada comum

**Data:** 2026-09-12. **Contrato, registrado antes do código:**
[contratos_correcao_derivacao_intermediaria](contratos_correcao_derivacao_intermediaria_2026-09-12.md).
**Origem:** item 3 do §7 da [revisão do Rank
3-B](revisao_rank03b_consumo_operacional_2026-09-12.md).

**Escopo:** `src/dados_estruturados.py`. **O painel NÃO foi reconstruído** —
ver §5. Suíte: **2.034 casos, zero skip** (era 2.030), **+4 contraprovas**.

---

> **⚠️ RESSALVA POSTERIOR (2026-09-15) — leia antes de citar este relatório.**
> A [conferência de 15/09](conferencia_quatro_ondas_2026-09-15.md) (QW6 e §3.3)
> e a [onda de correção](implementacao_qw1_qw8_2026-09-15.md) mudam a leitura
> abaixo. O corpo não foi reescrito.
>
> | Afirmação abaixo | Estado em 15/09 |
> |---|---|
> | "7.734 linhas em 507 companhias" (§1) | **513 companhias.** 507 é só o grupo de 183 dias |
> | "os 701.357 derivados corretos caem dentro" da banda (§2, §4) | São **todos** os derivados trimestrais em disco, **inclusive 319.049 do 4T**, que outra função produz. Não provam preservação individual pela função nova |
> | "A recusa é contada e reportada" (§2) | A contagem usava `coalesce(conceito, cd_conta)` e a inserção `coalesce(conceito, cd_conta\|descrição)`: a recusa podia acontecer e sair **zero**, sem aviso. Agora inserção e contagens saem da mesma relação. Simulado em memória sobre os arquivados do painel de treino: contador antigo **4.486**, corrigido **7.733**; criados **382.454** nas duas versões |
> | Critério 6 do contrato — aviso só quando houve recusa | **Nunca foi testado no carregador**: os quatro casos olhavam só o retorno da função. Agora há contraprova sobre `relatorio.avisos`, presente e ausente |
> | Falsificação 1 — "701.357 preservados" (§4) | A comparação foi feita agora, na simulação: os **382.454 grupos derivados são idênticos** entre as duas versões, e as linhas são idênticas fora de **141 grupos de 7 companhias** onde o desempate é **não determinístico nas duas versões** (troca de exercício social põe dois períodos sob o mesmo rótulo). Pré-existente; não corrigido |
> | — | **Antecedente inexistente** virou estado próprio, contado e avisado: **139.435 grupos** sem acumulado anterior do mesmo exercício, boa parte porque a descrição da conta muda entre arquivamentos. Pré-existente; curar muda a identidade de pareamento (RN09) |

## 1. O defeito, e por que ele é maior que o Rank 3-B

A derivação `isolado(q) = acumulado(q) − acumulado(q−1)` pareia, por `lag` sobre
`ORDER BY dt_fim_exerc`, o **período anterior disponível**. Faltando um
acumulado intermediário, a diferença cobre mais de um trimestre — e saía
rotulada `tipo_periodo='trimestral'`.

A docstring prometia *"o de mesmo início de exercício com o maior `dt_fim_exerc`
estritamente menor"*. Era **verdade e insuficiente**: nada garantia que esse
período fosse o trimestre anterior.

| Duração do derivado | Linhas | Companhias | Contas |
|---|---:|---:|---:|
| 183 dias | 7.555 | 507 | 111 |
| 184 dias | 139 | 7 | 38 |
| 182 dias | 30 | 3 | 16 |
| 273 dias | 10 | 1 | 10 |
| **Total anômalo** | **7.734** | | |
| Corretos (80–100 dias) | 701.357 | | |

**São 1,1% dos derivados trimestrais, em 507 companhias e 111 contas** — não os
9 que o recorte de FCO do Rank 3-B mostrou. O defeito contamina **qualquer
janela TTM do painel**, e é por isso que o conserto é da camada comum.

O caso do parecer, ainda vivo no painel em disco:

```text
cd_cvm  trimestre  dt_ini      dt_fim      dias  valor_reais
025887  3T2024     2024-04-01  2024-09-30   183   17.297.000
```

`19.289.000` (jan–set) − `1.992.000` (jan–mar) = seis meses de caixa,
publicados como trimestre isolado.

## 2. A correção

Uma condição, declarada em constante:

```sql
AND (a.dt_fim_exerc - a.fim_anterior)
    BETWEEN {DIAS_MINIMOS_DE_UM_TRIMESTRE} AND {DIAS_MAXIMOS_DE_UM_TRIMESTRE}
```

**A banda separa exatamente o que foi medido:** os 701.357 derivados corretos
caem dentro dela e os 7.734 anômalos caem fora. Nenhum caso ambíguo foi
observado.

**A equivalência que fecha a prova:** o período derivado tem
`dt_ini_exerc = fim_anterior + 1 dia`, então sua duração em dias é
`dt_fim_exerc − fim_anterior` — **a mesma expressão da banda**. Logo as 7.734
linhas com duração fora de 80–100 são precisamente as que passam a ser
recusadas: nem uma a mais, nem uma a menos.

### Por que dias e não diferença de meses

`date_diff('month', …)` parece mais principiado e quebra em exercício de 13
semanas: de `2025-03-29` a `2025-06-28` ele conta **2** meses, recusando
derivação legítima. A banda de dias não tem esse modo de falha.

### A recusa é contada e reportada

A função passou a devolver `(criados, recusados)`, e o carregador emite aviso —
mesmo padrão do `DFC_MD × DFC_MI` e das incoerências do lucro. **Recusa
silenciosa seria trocar um defeito por outro:** painel que perde linha sem sinal
é o defeito que o §3.15 descreve como *"pior que sumir com erro"*.

### Alternativas rejeitadas, registradas antes de medir

| Alternativa | Por que não |
|---|---|
| Emitir como `'semestral'` | Vocabulário que nenhum consumidor conhece: quem filtra `trimestral` deixaria de ver o problema; quem não filtra somaria semestre com trimestre |
| Ratear o valor (dividir por 2) | Inventa fluxo de caixa que a companhia não publicou — a linha que o §3.16 recusou na derivação por LPA |
| Filtrar no consumidor | Foi o que produziu este achado: cada consumidor teria de conhecer o defeito |
| Recusar em silêncio | Ver acima |

## 3. Contraprovas

Quatro casos novos, em painel mínimo **em memória** — construir o caso por
arquivo-fonte esconderia a ausência de UM acumulado atrás da carga inteira:

| Caso | Verifica |
|---|---|
| 1T ausente + acumulado do 1S | `criados == 0`, `recusados == 1` — o caso do parecer |
| **1T presente + acumulado do 1S** | `criados == 1`, valor 2.000, período 01/04–30/06. **Não-regressão obrigatória:** sem ela, recusar tudo passaria no caso acima |
| 1T + 1S + 9M juntos | Dois derivados, **nenhum** fora da banda |
| A banda | Está declarada e vale 80–100 |

Os testes que já existiam — `TestDerivacaoDeTrimestreIntermediario`, com o 2T
derivado, o isolado da CVM preservado como `arquivado` e a proibição de
atravessar exercícios — **passaram sem alteração**.

## 4. Condições de falsificação — todas negativas

| # | Condição | Resultado |
|---|---|---|
| 1 | Derivado legítimo deixa de ser criado | ❌ — não-regressão travada por contraprova; 701.357 preservados |
| 2 | Hash de painel muda | ❌ — `43e31d9f…` e `c1a60445…` intactos |
| 3 | Asserção enfraquecida | ❌ — única linha `def` removida é a assinatura, declarada em D1.2 |
| 4 | Recusa sem aviso | ❌ — aviso implementado e coberto |

## 5. O que esta onda deliberadamente NÃO fez

**O painel em disco continua carregando as 7.734 linhas defeituosas.** A
correção é do **código**; aplicá-la exige reconstruir `cvm_treino.duckdb`, o que
muda o hash do painel — decisão que o §3.13 manda declarar por si, e que o §3.5
agrava: esse painel alimenta a **etapa 10**, o único modelo treinado do projeto.

Reconstruir é a próxima decisão, e não é efeito lateral desta onda. Quem
reconstruir precisa:

1. Declarar a quebra de hash, com o hash anterior conferido antes da troca,
   como o §3.13 fez em 2026-08-27.
2. Medir o efeito sobre as métricas da etapa 10 — **sem** presumir que são todas
   inválidas nem que nenhuma é. Razões podem cancelar uma escala comum;
   diferenças e janelas TTM não cancelam.
3. Reconstruir também `cvm.duckdb`, ou declarar por que não.

## 6. O que continua aberto

1. **As transições de escala** (`MIL`↔`UNIDADE`) seguem sem adjudicação. Exigem
   o padrão do §3.3 — `correcoes_contabeis.csv` com procedência e guarda
   anti-porta-dos-fundos —, **caso a caso**, nunca por tabela automática.
2. **Os períodos curtos** (16 linhas de 12/31/38/41 dias) não são derivação: são
   colisão de trimestre fiscal na fonte. Em **15 grupos** convivem com a linha
   válida, e em **12** o `max` elege o curto. Outro conserto, outro contrato.
3. **Protocolo novo** antes de qualquer remedição do Rank 3-B — o pré-registro
   `fbae30cc…` está consumido.
4. **A previsão sobre `fco_ttm_sobre_sd8` segue SEM TESTE.** Corrigir dado não a
   confirma.
5. **Falta conferência independente** desta onda e da de R1–R5.
