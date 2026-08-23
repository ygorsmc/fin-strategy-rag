# LLM-juiz × auditoria humana — 2026-08-23

Primeira medição da etapa 13 (spec 5.15): quanto um juiz automático concorda
com a auditoria humana de groundedness, e **onde ele erra**.

- **Juiz:** `gemini-3.7-flash` (temperatura 0), cota gratuita de 20 req/dia,
  5 req/min.
- **Gerador julgado:** `gemini-3.5-flash-lite` — juiz ≠ gerador de propósito;
  usar o mesmo modelo nos dois papéis é o viés que a spec 5.23 nomeia.
- **Amostra:** os 15 da rodada `a0bea525`, cujos vereditos humanos foram dados
  **às cegas**, antes de existir qualquer juiz. É o que faz a concordância
  significar algo — rodar o juiz antes da leitura ancoraria o auditor.
- **Entrada do juiz:** pergunta, resposta e os trechos recuperados **sem os
  scores** (o score enviesaria para o topo do ranking).
- **Custo:** USD 0,0161, 15 chamadas, zero erro.
- Dados: `artefatos/resultados_avaliacao/concordancia_juiz_humano.json`.

## Resultado

**Concordância: 13/15 = 0,867.**

| | humano: sistema acertou | humano: sistema errou |
|---|---|---|
| **juiz: sistema acertou** | 8 | **0** |
| **juiz: sistema errou** | **2** | 5 |

A assimetria é o achado operacional: **a célula `juiz acertou × humano errou` é
zero**. Nos 5 descartes indevidos que a leitura humana encontrou, o juiz
concordou com os 5. Ele não deixou passar nenhum falso negativo da guarda.

As 2 discordâncias vão todas na direção oposta — o juiz acusa erro onde o
humano viu acerto. Só uma delas é erro de verdade, e é grave.

## TSTF006 — o juiz caiu exatamente na falha que o projeto existe para pegar

O modelo respondeu **R$ 12.144 milhões**; o valor certo para o 1T2026 é
**R$ 11.875 milhões**. Os dois números estão na mesma tabela, em **colunas
diferentes** — 12.144 é a coluna do 4T2025.

A guarda determinística da RN02 descartou (acertou). O humano confirmou o
descarte. **O juiz disse que a resposta estava fundamentada**, justificando:

> "O trecho 1 confirma a linha 'IFRS - valores atribuíveis aos acionistas
> controladores e não controladores' com o valor de R$ 12.144 milhões."

O número **está** no trecho. O juiz viu o número, achou o rótulo certo e parou
aí — não conferiu de qual período era a coluna. É *número certo, coluna
errada*: a classe de erro que este projeto inteiro foi construído para detectar,
e a que produz "número plausível, não nulo e errado".

Duas leituras, ambas importantes:

1. **Confirma a spec 5.23 com dado do próprio projeto.** O argumento para manter
   a auditoria humana era que "um detector automático de alucinação tem a mesma
   fragilidade que está sendo testada". Aqui isso deixou de ser hipótese: um
   modelo mais forte que o gerador falhou no caso decisivo.
2. **A guarda determinística venceu o LLM mais forte** no caso que mais importa.
   Se o juiz tivesse poder de decisão, ele teria publicado o número errado.

É a evidência direta de por que o juiz **não pode** substituir a RN02.

## TSTQ001 — divergência de critério, não erro

O humano marcou o descarte como correto com a justificativa "havia informações
bem mais relevantes para acrescentar à resposta" — isto é, um julgamento de
**completude/qualidade**, não de fundamentação. O juiz respondeu `fundamentada:
true` e `responde_completamente: true`, apontando o trecho que sustenta a
afirmação.

Os dois podem estar certos sob critérios diferentes. Fica registrado que o
auditor humano aplicou uma régua mais exigente que "a resposta se sustenta no
trecho" — e que essa régua não é a que a métrica de groundedness define.

## O que isto autoriza e o que não autoriza

**Autoriza usar o juiz como TRIAGEM.** Ele achou 5 de 5 dos descartes indevidos.
Pré-ordenar a leitura humana ("comece por estes") economiza tempo real sem
custar credibilidade, desde que o humano ainda leia tudo o que decidir publicar.

**Não autoriza o juiz decidir publicação.** TSTF006 é a contraprova: ele
empurraria para o ar um número da coluna errada. A métrica de groundedness
reportada continua sendo a auditoria humana (5.15), e a guarda continua
determinística.

**Ressalva de tamanho:** n = 15, com 2 discordâncias. O intervalo de confiança
de uma taxa de 0,867 nesse tamanho é largo; o número não sustenta afirmação
fina sobre "quão bom" o juiz é. O que sustenta é o achado qualitativo do
TSTF006, que não depende de tamanho de amostra — é um contraexemplo, e um
contraexemplo basta.
