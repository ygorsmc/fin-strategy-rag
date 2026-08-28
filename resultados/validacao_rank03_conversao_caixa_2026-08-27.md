# Validação do Rank 3 — deterioração de conversão de caixa

**Veredito: REJEITADO em T1, antes de qualquer treino.** Custo de API: zero.

Pré-registro: `resultados/pre_registro_rank03_conversao_caixa_2026-08-27.md`,
escrito **antes** de qualquer medição de desempenho. Auditor:
`scripts/auditar_rank03_conversao_caixa.py` →
`artefatos/rank03/auditoria_alvo.json`.

> **O pré-registro previu esta reprovação e nomeou o mecanismo.** A seção 5
> dizia, antes de medir: *"B0 é o desfecho mais provável. A reversão à média do
> accrual é um dos fatos mais replicados da literatura contábil, e o alvo —
> variação de accrual — está mecanicamente ligado ao nível."* Era isso.

## A amostra

| | |
|---|---:|
| Observações | **7.671** |
| Companhias | 378 |
| Trimestres | 54 |
| Eventos (quintil superior de Δaccrual) | 1.557 |
| Prevalência | 0,203 |
| Elegíveis antes da censura | 10.137 |
| Censurados sem `t+4` observável | 2.461 |

## T1 — dois dos quatro componentes reprovam

Taxa do evento por quintil de cada componente que define mecanicamente o
rótulo. Limiar de amplitude: **0,15**.

| Componente | Q1 · Q2 · Q3 · Q4 · Q5 | Amplitude | |
|---|---|---:|---|
| **`accrual`** (nível) | 0,374 · 0,227 · 0,168 · 0,139 · **0,108** | **0,266** | ❌ |
| **`conversao`** | 0,129 · 0,128 · 0,160 · 0,240 · **0,357** | **0,229** | ❌ |
| `roa` | 0,235 · 0,213 · 0,174 · 0,180 · 0,213 | 0,061 | ✅ |
| `ativo_medio` | 0,253 · 0,231 · 0,213 · 0,181 · 0,137 | 0,116 | ✅ |

**A companhia no quintil de MENOR accrual tem 3,5× mais chance de ser marcada
que a do quintil de maior accrual.** Isso não é deterioração detectada — é
reversão à média medida com outro nome. O mesmo em espelho na conversão: quem
converte muito caixa hoje é mecanicamente mais provável de converter menos
depois.

Pelo pré-registro, T1 reprovado **encerra o candidato antes do treino**, e
reformular em voo cria o Rank 3-B com pré-registro próprio. Nenhum modelo foi
carregado, nenhum baseline foi comparado, e a barra de T3 nunca chegou a ser
avaliada.

## A lição que generaliza — terceira vez no mesmo formato

> **Alvo definido como VARIAÇÃO de uma grandeza que reverte à média fabrica o
> NÍVEL dessa grandeza como baseline.**

É o terceiro candidato a morrer disso, com três roupas diferentes:

| Candidato | A variação | O nível que virou baseline |
|---|---|---|
| Corte absoluto de ROA | ΔROA < −2pp | `roa_ttm` (amplitude 0,317) |
| **C1** | ΔROA < −1,25·sd₈ | `sd8`, o próprio normalizador (0,180–0,247) |
| **Rank 3** | Δaccrual no quintil superior | `accrual` (0,266) e `conversao` (0,229) |

**Consequência prática para qualquer candidato futuro:** se o alvo é "X piora",
o nível de X entra em T1 obrigatoriamente — não como cortesia, mas porque a
reversão à média é a hipótese nula certa e ela vence sozinha. Um alvo só escapa
disso se o evento for **materialmente definido** (falência, evento legal,
reapresentação) em vez de definido por movimento de uma série contínua.

## O que NÃO se conclui

- **Não** se conclui que conversão de caixa é irrelevante para Value Investing.
  Conclui-se que *"a variação da conversão"* não é rótulo válido neste painel.
  Ler a conversão de caixa continua sendo trabalho de analista e o dado agora
  existe (§3.13).
- **Não** se conclui que a carga de DFC foi desperdício. Ela era pré-condição
  para a pergunta ser **feita**, e o resultado é que a pergunta foi respondida
  em vez de ficar em aberto por ausência de dado. O fluxo de caixa segue no
  painel, disponível para consulta, para o accrual real e para qualquer
  candidato futuro.
- **Não** se conclui que o Rank 3 inteiro está morto. O que está morto é **esta
  operacionalização**. Um Rank 3-B com evento materialmente definido — por
  exemplo, FCO negativo por dois trimestres consecutivos em companhia lucrativa
  — é outro estimando, com T1 próprio, e não herda nenhum número daqui.

## Um defeito do auditor, achado e corrigido durante a execução

A primeira execução devolveu **`n = 0` e veredito "T1 aprovado"**. A amplitude
saía `NaN`, e `NaN >= 0,15` é `False` — a guarda **falhava em aberto**.

Guarda que aprova por ausência de dado é pior que guarda nenhuma. Corrigido com
`MINIMO_PARA_T1 = 500` e exceção `AmostraInsuficienteError`: amostra pequena
demais **levanta erro**, nunca vira aprovação.

O `n = 0` original tinha causa real, e ela virou correção de dado — a próxima
seção.

## Achado de dado que a execução destravou

**A CVM não publica DFC trimestral isolada no 2T e no 3T — só acumulada.**
Medido: `6.01` tinha 5.767 linhas de 2T e 5.603 de 3T, **todas acumuladas e
nenhuma isolada**; a DRE, no mesmo recorte, tem 5.747 e 5.582 isoladas.

Sem isso, fluxo de caixa isolado existia apenas no 1T e no 4T derivado — **dois
trimestres por ano nunca formam janela móvel de quatro**, e nenhuma métrica TTM
de caixa era calculável. Foi a causa do `n = 0`.

Corrigido em `_derivar_trimestres_intermediarios` pela mesma aritmética da RN10,
dentro do próprio ITR: `isolado(q) = acumulado(q) − acumulado(q−1)`, pareando
por **mesmo início de exercício** e nunca por "a linha de cima" — que casaria
exercícios diferentes e produziria número plausível e errado.

| | |
|---|---:|
| Fatos derivados do 2T/3T isolado | **390.187** |
| Linhas no painel | 6.787.589 → **7.177.705** |

Cobertura do FCO isolado, depois da correção: **1T 725 · 2T 702 · 3T 693 ·
4T 683** companhias — equilibrada nos quatro trimestres.

## Hash do painel

| | SHA-256 |
|---|---|
| Anterior (com DFC, sem 2T/3T isolado) | `476a11da2382c6f2a4575de1e37cf997b93edff2b449b67d9f7b75c6adf53247` |
| **Atual** | `c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b` |

## Reprodução

```bash
python -m scripts.auditar_rank03_conversao_caixa \
  --painel artefatos/cvm_treino.duckdb \
  --saida /tmp/rank03_repro.json
```
