# Contrato de correção — derivação de trimestre intermediário (camada comum)

**Data:** 2026-09-12. **Escrito ANTES de qualquer alteração de código.**
**Escopo:** `_derivar_trimestres_intermediarios` em `src/dados_estruturados.py`.

**Origem:** item 3 do §7 da [revisão independente do Rank
3-B](revisao_rank03b_consumo_operacional_2026-09-12.md) — *"corrigir a derivação
e a identificação de períodos na camada comum com procedência, preservando os
consumidores existentes; isso exige testes próprios e não foi feito como efeito
lateral da revisão"*.

> **⚠️ RESSALVA POSTERIOR (2026-09-15).** A tabela abaixo atribui 507
> companhias ao total de 7.734 linhas: são **513** (507 é só o grupo de 183
> dias). Os 701.357 "corretos" incluem 319.049 derivados do 4T. D1.2 foi
> cumprido com identidade de contagem **diferente** da inserção e sem teste do
> aviso no carregador — conferência QW6, corrigido pelo
> [contrato D2](contratos_correcao_qw1_qw8_2026-09-15.md).

## O defeito, medido no painel inteiro

A derivação `isolado(q) = acumulado(q) − acumulado(q−1)` pareia, por `lag` sobre
`ORDER BY dt_fim_exerc`, o **período anterior disponível** — não o trimestre
imediatamente anterior. Faltando um acumulado intermediário, a diferença cobre
mais de um trimestre e **sai rotulada `tipo_periodo='trimestral'`**.

A docstring atual promete *"o de mesmo início de exercício com o maior
`dt_fim_exerc` estritamente menor"*, o que é verdade — e insuficiente: nada
garante que esse período seja o trimestre anterior.

**Alcance, medido antes de corrigir** (não os 9 do recorte do Rank 3-B):

| Duração do derivado | Linhas | Companhias | Contas |
|---|---:|---:|---:|
| 183 dias | 7.555 | 507 | 111 |
| 184 dias | 139 | 7 | 38 |
| 182 dias | 30 | 3 | 16 |
| 273 dias | 10 | 1 | 10 |
| **Total anômalo** | **7.734** | — | — |
| Derivados corretos (80–100 dias) | 701.357 | — | — |

São **1,1% dos derivados trimestrais**, e o defeito contamina qualquer janela
TTM do painel — muito além deste candidato. Exemplo do parecer,
`025887/3T2024`: `19.289.000` (jan–set) − `1.992.000` (jan–mar) =
**`17.297.000` de abr–set**, rotulado trimestral.

## Contrato

**D1.1 — só deriva trimestre quem cobre um trimestre.** A linha derivada é
emitida como `trimestral` somente se o período resultante
(`fim_anterior + 1 dia` até `dt_fim_exerc`) durar entre **80 e 100 dias**.

**D1.2 — a recusa é contada e reportada.** A função devolve quantas derivações
recusou, e o carregador acrescenta um **aviso** com o número, pelo mesmo padrão
já usado para `DFC_MD × DFC_MI` e para as incoerências do lucro. Recusa
silenciosa seria trocar um defeito por outro.

**D1.3 — nada é sobrescrito nem apagado.** O isolado que a CVM publica continua
`arquivado` e único. A recusa apenas **não cria** a linha errada.

**D1.4 — o painel NÃO é reconstruído nesta onda.** A correção é do código.
Aplicá-la ao `cvm_treino.duckdb` muda o hash do painel, o que o §3.13 exige
declarar como decisão própria — e o painel de treino alimenta a etapa 10. **Até
que essa reconstrução seja decidida, o painel em disco continua carregando as
7.734 linhas defeituosas**, e isso fica escrito no `MEMORY.md`.

### Por que a banda de dias, e não diferença de meses

`date_diff('month', ...)` parece mais principiado, mas quebra em exercício de
13 semanas: de `2025-03-29` a `2025-06-28` ele conta **2** meses, e a derivação
legítima seria recusada. A banda de dias não tem esse modo de falha.

**A banda separa exatamente o que foi medido:** todos os 701.357 derivados
corretos caem dentro dela, e todos os 7.734 anômalos — 182, 183, 184 e 273 dias
— caem fora. Nenhum caso ambíguo foi observado.

### Alternativas rejeitadas, registradas antes de medir

| Alternativa | Por que não |
|---|---|
| Emitir com `tipo_periodo='semestral'` | Vocabulário novo que nenhum consumidor conhece; quem filtra `trimestral` deixaria de ver o problema, e quem não filtra somaria semestre com trimestre. |
| Corrigir o valor por rateio (dividir por 2) | Inventa fluxo de caixa que a companhia não publicou. É a linha que o §3.16 recusou na derivação por LPA. |
| Deixar como está e filtrar no consumidor | Foi o que produziu este achado: cada consumidor teria de conhecer o defeito. A carga é o lugar de falhar fechado (§3.13, invariante 3). |
| Recusar em silêncio | Painel que perde linha sem sinal é o defeito da Batch API do §3.15: *"documento sumindo do corpus sem sinal é pior que sumir com erro"*. |

## Critérios de aceitação

1. Acumulado do **1S** sem o 1T presente **não** produz `2T` derivado; a recusa
   é contada.
2. **Não-regressão, obrigatória:** `1T` presente + acumulado do `1S` continua
   produzindo o `2T` isolado, com `dt_ini_exerc` no dia seguinte ao fim do 1T e
   o valor da subtração — é o caso que a função existe para resolver.
3. A derivação continua não atravessando exercícios.
4. O isolado publicado pela CVM continua `arquivado` e único.
5. Nenhum derivado emitido com duração fora de 80–100 dias.
6. O aviso aparece quando houve recusa, e **não** aparece quando não houve.

## Condições de falsificação

1. Algum derivado legítimo (80–100 dias) deixa de ser criado.
2. O hash de `cvm_treino.duckdb` ou de `cvm.duckdb` muda nesta onda.
3. Alguma asserção existente é enfraquecida.
4. A recusa acontece sem aviso.
