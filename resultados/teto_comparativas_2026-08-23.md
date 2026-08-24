# Por que a exatidão comparativa é 0,000 — teto estrutural, não regressão

**Data:** 2026-08-23 · **Custo:** zero (lê o checkpoint já pago) ·
**Rodada analisada:** `20260823T131515Z-4ad67021f6`, fingerprint `5b9b142d`

## O que motivou a investigação

A rodada vigente publicou **exatidão comparativa 0,000 nas cinco estratégias**,
contra 0,100–0,200 da rodada anterior. Eu havia registrado isso no README como
**regressão**. Esta apuração mostra que a palavra estava errada, e o que está
por trás é mais sério do que uma regressão.

## Achado 1 — a recuperação está correta; o gargalo não é dela

Nas 40 execuções comparativas com recuperação (E1–E4 × 10 perguntas), a
subconsulta por banco entregou **todos os bancos pedidos pelo gabarito, em
40 de 40** (`falta=[]` em todas). Não há pergunta comparativa em que um banco
exigido tenha ficado fora do top-5.

## Achado 2 — o banco certo chega, o número não

A pergunta comparativa exige de 1 a 5 valores, um por banco. Medindo se o
**valor do gabarito está no chunk daquele banco**:

| Estratégia | Valores presentes | Perguntas com TODOS os valores |
|---|---|---|
| E1 `keyword` | 6/25 | **1/10** |
| E2 `semantica` | 11/25 | **2/10** |
| E3 `hibrida` | 8/25 | **2/10** |
| E4 `fatos` | **18/25** | **5/10** |

A segunda coluna é o **teto**: uma comparativa só é respondível se todos os
valores dela estiverem presentes. Com exatidão publicada de 0/10, o sistema
opera contra um teto de 1 a 5 — não contra 10.

**A causa é o orçamento de contexto.** Cinco das dez comparativas pedem os
cinco bancos, e o top-5 é global: sobra **um único chunk por banco**. Um chunk
de release contém a métrica específica pedida em 24%–72% dos casos, conforme a
estratégia. Precisar de cinco acertos independentes desses torna a pergunta
quase inalcançável — as duas perguntas de cinco bancos (TSTC001, TSTC002)
chegam a 1/5 valores presentes em E3.

## Achado 3 — o conserto do chunker não causou o 0,000

Controle sobre as três rodadas, mesmo cálculo de teto:

| Rodada | E2 | E3 | E4 |
|---|---|---|---|
| `a0bea525` (antes do conserto) | 3/10 | 3/10 | 5/10 |
| `7f86fd5f` (1ª correção, cega) | 3/10 | 3/10 | 5/10 |
| `5b9b142d` (2ª correção, vigente) | 2/10 | 2/10 | **5/10** |

O teto do E4 é **idêntico nas três**. E2 e E3 variam em **uma** pergunta. A
diferença entre "0,100–0,200" e "0,000" são de 1 a 3 eventos sobre uma base de
1 a 5 possíveis — está dentro do ruído, muito abaixo do limiar pré-declarado
de 6 discordâncias.

**Correção ao README:** chamar isso de regressão foi leitura minha, e não se
sustenta. O número não caiu porque o sistema piorou; ele oscila perto de um
piso que já existia antes de qualquer correção desta semana.

## Achado 4 — o E4 se confirma pelo mesmo motivo que venceu nas factuais

O E4 dobra o teto de todos os outros (5/10 contra 1–2/10) e leva 18 dos 25
valores contra 6–11. É exatamente o comportamento previsto pelo §3.1-bis do
`AGENTS.md`: ranquear por conteúdo numérico da métrica traz a célula, enquanto
similaridade de texto traz a página. A comparativa é o caso onde essa diferença
mais pesa, porque o orçamento por banco é de um chunk só.

## Onde o modelo e a guarda entram (e não são o gargalo)

Distribuição dos 40 desfechos comparativos da rodada vigente:

- **22** o próprio modelo recusou (`Não há evidência suficiente`)
- **13** a RN02 rebaixou (valor sem lastro)
- **2** violação de contrato JSON (`recusa exige resposta=null`)
- **2** publicadas — e ambas erradas

As 22 recusas do modelo são, em sua maioria, **corretas**: o valor não estava
no contexto. A guarda e o modelo estão reagindo bem a um contexto insuficiente.

## O que fazer — e o que isso custa em comparabilidade

O caminho óbvio é dar **orçamento por banco** à comparativa (top-k por
subconsulta, não top-5 global). Mas o §3.1-bis já estabeleceu, com medição, que
mudar o orçamento de contexto **muda o que está sendo comparado** — foi por
isso que o E4 é canal puro e não união de dez vagas. Então:

- Aumentar o top-k das comparativas **não pode** entrar em E0–E4 sem
  invalidar a comparabilidade da tabela inteira.
- O caminho correto é **medição declarada em separado**, com o orçamento novo
  explicitado, exatamente como o E4 entrou.

**Não implementado nesta apuração, de propósito** — é decisão de escopo, não
detalhe técnico.

## Ressalva de método

A presença do valor foi medida por casamento textual do número do gabarito no
chunk do banco correspondente. Isso **subestima** o teto quando o release
imprime o valor em forma equivalente (`8,4%` contra `8,40%`), e não julga se o
rótulo ao lado do número é o certo. Serve para ordenar estratégias e para
provar a existência do teto — não como número publicável de recuperação.
