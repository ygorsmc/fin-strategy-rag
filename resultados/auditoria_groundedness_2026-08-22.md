# Auditoria manual de groundedness — 2026-08-22

Leitura humana das 15 perguntas amostradas da rodada congelada
`20260822T183429Z-c1d6b4dbe5` (fingerprint `a0bea525`, estratégia `semantica`,
225 chamadas, USD 0,2555, zero erro). Auditor: Ygor. Vereditos registrados em
`artefatos/resultados_avaliacao/auditoria_groundedness.json`.

## Resultado

**Score: 10/15 = 0,667.** Meta da spec 5.14: ≥ 0,90. **Não atingida.**

| Veredito | n | IDs |
|---|---|---|
| Acertou | 10 | TSTF006, TSTF010, TSTF001, TSTC009, TSTC006, TSTC002, TSTQ001, TSTA008, TSTA002, TSTA003 |
| Errou | 5 | TSTF012, TSTC008, TSTQ005, TSTQ010, TSTQ003 |

**Os 5 erros são todos do mesmo tipo: falso negativo da guarda da RN02.**
Nenhum é alucinação. Em nenhum dos 15 casos o sistema publicou número sem
lastro — o modo de falha medido é o oposto, a guarda descartando resposta que
*estava* fundamentada.

## Como o campo `grounded` foi interpretado

A spec (5.14, 5.15) define groundedness como "a resposta se sustenta no
contexto recuperado?", mas não diz o que fazer quando o sistema **recusa**.
Nesta rodada só **3 das 15** respostas foram publicadas; 12 terminaram em
recusa (7 rebaixadas pela RN02, 5 recusadas pelo próprio modelo).

Ler `grounded` ao pé da letra — "o texto publicado afirma algo sem lastro?" —
daria **15/15 = 1,00**, porque recusa não afirma nada e não pode alucinar. Um
score de 1,00 obtido assim seria verdadeiro e vazio: mediria sobretudo a
frequência de recusa. Por isso o campo foi preenchido com a leitura que o
auditor de fato usou — **"o sistema fez a coisa certa diante da evidência?"** —
em que descartar resposta bem fundamentada conta como falha. É a leitura que
produz número informativo, e é a que reprova.

Consequência: `consolidar_auditoria_final` marcará
`auditoria_concluida_meta_nao_atingida`, não `completa`. O modo demonstração
segue bloqueado, corretamente.

## Causa-raiz dos 5 descartes indevidos

Reproduzidos offline contra o checkpoint (custo zero), cláusula a cláusula.
São **três defeitos distintos**, não um só.

### 1. Fato de tabela sem rótulo de métrica — TSTF012

A resposta ("carteira de crédito ampliada no 4T25 foi de R$ 708,2 bilhões")
está certa e o valor **está literalmente no trecho citado**. O fato extraído
daquela célula, porém, sai com os tokens `{qoq, yoy}` e **nenhum grupo
métrico** — o rótulo da linha não foi capturado. Em `metricas_compativeis`, o
lado da resposta nomeia grupo (`carteira`) e o lado da evidência não, então cai
no fallback de sobreposição de tokens, que não acha nada em comum com
`qoq`/`yoy` e reprova.

O auditor observou que o valor também aparece detalhado em tabela na pág. 22 —
página que não foi recuperada. Duas frentes, então: o rótulo da linha na pág. 3
e o recall da pág. 22.

### 2. Valor derivado por aritmética — TSTC008

A resposta trazia `26,6% - 24,8% = 1,8%`. O `1,8` não existe literalmente em
lugar nenhum do corpus — é resultado de conta. Existe caminho para isso
(`_calculo_subtracao_explicito_valido` e `_conclusao_comparativa_derivada_valida`),
mas a redação da resposta não entrou no formato que esses reconhecem. Falso
negativo por valor calculado.

### 3. Cláusulas qualitativas longas — TSTQ003, TSTQ005, TSTQ010

Dois sub-defeitos somados:

**(a) O split de cláusulas quebra em `p.p.`** — o separador
`(?<=[.!?])\s+` trata o ponto final de *pontos percentuais* como fim de frase.
"queda de 0,6 p.p. no trimestre e 1,5 p.p. em relação a Set24" vira três
fragmentos órfãos (`no trimestre e 1,5 p.p.`, `em relação a Set24`) que não têm
como se fundamentar isolados e derrubam a resposta inteira. **É exatamente a
mesma classe do defeito de `pág.` já corrigido em 2026-08-18** — a correção de
então tratou o caso específico, não a família.

**(b) `_clausula_numerica_sem_conteudo_inventado` reprova prosa explicativa
longa.** Nas qualitativas o modelo parafraseia a explicação causal do próprio
documento; a checagem de conteúdo inventado acusa cláusulas de 20+ tokens
mesmo quando fiéis. Reprovou 2 de 2 cláusulas em TSTQ003 e 3 de 10 em TSTQ005.

## Ressalva do auditor em TSTA008

Registrada porque não cabe nesta métrica e não deve se perder. A pergunta
("por que o lucro caiu do 3T2025 para o 4T2025?") tem **premissa falsa** — não
houve queda, houve aumento. O sistema recusou, o que o gabarito considera
certo, mas recusou dizendo *"não há evidência suficiente nos trechos
recuperados"*, e não negando a premissa. O auditor observa que o melhor
comportamento seria corrigir a premissa e dar o número certo.

Isso é **recusa pelo motivo errado**, e a spec 5.14 já tem métrica separada
para exatamente isso ("Recusa **pelo motivo certo** (não apenas recusa)",
meta ≥ 0,80) — ainda não medida. Fica anotado como entrada dessa métrica.

## O que isto significa para o plano

O gargalo medido do sistema **não é alucinação — é a precisão da guarda**.
Nesta amostra a RN02 descartou 7 respostas e **5 dos descartes estavam
errados** (a taxa é alta demais para o tamanho da amostra permitir estimativa
fina, mas a direção é inequívoca). Isso também explica, de outro ângulo, a
exatidão baixa medida em E1–E4: a resposta certa é gerada e depois jogada fora.

Corrigir os três defeitos acima muda respostas, o que invalida o fingerprint e
exige nova rodada paga e nova leitura humana. A alternativa — promover com
0,667 — é honesta, mas publica um sistema que se sabe descartando resposta boa.
