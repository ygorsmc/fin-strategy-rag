# 🧪 Como o sistema é avaliado

Há uma separação rígida entre o que o `pytest` verifica e o que é **medido**:

- O `pytest` cobre regras de formatação, *chunking* e contrato — passa ou falha. São **2.753 casos automatizados, sem skips**, e verde é pré-condição de qualquer commit.
- Exatidão, recall, recusa e falso bloqueio são **resultados avaliados**: rodam no conjunto congelado a temperatura 0, com registro por execução.

O conjunto-padrão tem **45 perguntas congeladas** (desde 29/07/2026) mais 10 de desenvolvimento e 20 ataques. Nenhum número de desenvolvimento vira resultado final, e mexer nas 45 invalida a rodada publicada — é decisão explícita, nunca efeito lateral.

As 45 se dividem em quatro tipos: 15 **factuais** (valor pontual num release), 10 **comparativas** (exigem cruzar bancos), 10 **qualitativas** (por que algo variou) e 10 **adversariais**, cuja resposta certa é **recusar** — companhia fora do corpus, período que não existe, pergunta de conhecimento geral.

---

# 📊 Resultado da rodada congelada

Rodada `20260915T011103Z-85fbfadd35`, *fingerprint* `c3a03ff7`, executada em 15/09/2026: 45 perguntas × 5 estratégias = **225 chamadas**, temperatura 0, custo total **US$ 0,2577**, zero erros.

| Estratégia | Factual | Comparativa | Recusa correta | Recall@5 |
|---|---|---|---|---|
| **E0** *closed-book* (controle) | 0/15 · 0,000 | 0/10 · 0,000 | 8/10 · 0,800 | — |
| **E1** palavra-chave (BM25) | **6/15 · 0,400** | 0/10 · 0,000 | 10/10 · 1,000 | **23/25 · 0,920** |
| **E2** semântica | 5/15 · 0,333 | 1/10 · 0,100 | 10/10 · 1,000 | 20/25 · 0,800 |
| **E3** híbrida (RRF) | 5/15 · 0,333 | 1/10 · 0,100 | 10/10 · 1,000 | 22/25 · 0,880 |
| **E4** tabela de fatos | **6/15 · 0,400** | **4/10 · 0,400** | 10/10 · 1,000 | 22/25 · 0,880 |

**Como ler estes números, honestamente:**

- **O E0 é a prova de que o RAG está fazendo trabalho.** Sem documento nenhum, o modelo acerta **zero** das factuais e zero das comparativas — e ainda aceita responder 2 das 10 perguntas que deveria recusar. Tudo que as outras estratégias acertam vem da recuperação, não da memória do modelo.
- **A exatidão factual é modesta: o melhor caso acerta 6 de 15.** Isso não é omitido aqui porque é o resultado real, e a análise do porquê vale mais que o número: a maior parte das falhas é de recuperação de tabela, não de raciocínio.
- **As comparativas são o ponto fraco declarado.** Só a estratégia E4 passa de um acerto — cruzar cinco bancos exige trazer o trecho certo de cinco documentos diferentes dentro do mesmo orçamento de contexto.
- **A recusa é o ponto forte: 10/10 em todas as estratégias com documento.** O sistema recusa corretamente quando a companhia não está no corpus, quando o período não existe e quando a pergunta é de conhecimento geral.
- **O recall é medido por página**, e isso é sinal enganoso para julgar *chunking*: um *chunk* órfão de cabeçalho conta como acerto de página e ainda assim não consegue responder. Por isso a exatidão fica abaixo do recall.

> **Divergência declarada entre duas rodadas.** Uma rodada anterior, de 23/08/2026, mediu valores diferentes para o mesmo conjunto — entre eles 0,667 para o E4 nas factuais. A rodada de 15/09 mede 0,400. O código mudou entre as duas (a correção de um falso bloqueio, descrita adiante), e **15 vereditos mudaram de valor com o mesmo modelo e a mesma recuperação** — 8 para melhor e 7 para pior. Publicar apenas a melhor das duas seria exatamente o que a disciplina de avaliação deste projeto existe para impedir. Os números acima são os da rodada **mais recente**.

---

# 🔐 Segurança medida

Medição de 21/08/2026, com as duas camadas de ML ligadas (Presidio e Llama Prompt Guard 2), custo zero e nenhuma chamada a LLM:

| Métrica | Resultado | Meta |
|---|---|---|
| Ataques bloqueados | **20 de 20** · 1,000 | máxima |
| Falso bloqueio na **entrada** (45 perguntas legítimas) | **0 de 45** · 0,000 | 0 |
| Falso bloqueio na **saída** (855 respostas geradas) | **0 de 855** · 0,000 | 0 |

Os 20 ataques se dividem em duas famílias: **11 de tópico proibido** (pedidos de recomendação, preço-alvo e aconselhamento pessoal) e **9 de injeção de prompt** (tentativas de sobrescrever as regras ou revelar o *prompt*).

A taxa de falso bloqueio é reportada junto e com meta zero de propósito: um filtro que bloqueia tudo teria 20/20 de ataques bloqueados e seria inútil. Só o par de números descreve o comportamento.

---

# 🎬 Ensaio do roteiro de demonstração

Execução de 18/09/2026 **pela interface real**, não pelo arnês de avaliação — é a prova de que o caminho que aparece na tela funciona ponta a ponta. Duas chamadas pagas, **US$ 0,0027** no total, nenhuma exceção em nenhum passo.

| # | Rota | Pergunta | Resultado |
|---|---|---|---|
| 1 | Painel, sem LLM | Lucro líquido do Banco do Brasil no 4T2025 | R$ 5,24 bilhões, **marcado como derivado** (RN10), com a conta explicitada |
| 2 | Painel, sem LLM | Patrimônio líquido do Itaú no 3T2025 | R$ 224,71 bilhões, arquivado |
| 3 | Painel, sem LLM | Lucro do Banco Inter no 3T2025 | Entrega o número **e declara** que não há release no corpus (RN12) |
| 4 | Painel, sem LLM | Lucro do Nubank no 3T2025 | **Recusa classificada**, explicando que a companhia não arquiva na CVM nem está no corpus |
| 5 | *Guardrail* | "Devo comprar ações do Itaú agora?" | **Recusa** citando a Res. CVM 20/2021, antes de qualquer chamada externa |
| 6 | RAG ao vivo | Resultado recorrente gerencial do Itaú no 2T2025 | **R$ 11.508 milhões**, pág. 5 — confere com o gabarito |
| 7 | RAG ao vivo | Inadimplência acima de 90 dias do BB no 3T2025 | **4,93%**, pág. 12 — confere com o gabarito |

Isso cobre, com evidência registrada, o que a Etapa 1 exige demonstrar: **três perguntas respondidas via RAG** (passos 6 e 7, mais a terceira gravada no vídeo) e **duas consultas a dados estruturados** (passos 1 e 2).

> **O que este ensaio não prova:** ele não mede exatidão. As perguntas foram escolhidas por já terem acertado na rodada congelada, e temperatura 0 não garante repetição — 15 vereditos mudaram entre duas rodadas com o mesmo modelo.

---

# 🐛 O que deu errado — defeitos achados e corrigidos

Os defeitos abaixo foram encontrados por auditoria do próprio sistema, não por acaso. Estão aqui porque o registro deles é parte do que o projeto se propõe a demonstrar.

## O chunk órfão de cabeçalho

O sistema respondeu `R$ 12.144 milhões` (coluna do 4T25) a uma pergunta sobre o 1T2026, cujo valor é `11.875`. O OCR estava correto e a tabela, íntegra — o **chunk** é que abria nas duas últimas linhas dela, sem o cabeçalho que nomeia as colunas. Eram 101 *chunks* nessa condição, alcançando 18 das 45 perguntas.

**A primeira correção piorou o sistema, e registrar isso é parte da lição.** Descartar a tabela da cauda zerou os órfãos e derrubou a exatidão factual junto (de 0,467 para 0,267), porque a duplicação também funcionava como rede de segurança: um valor perto da fronteira aparecia em dois *chunks*, e recuperar qualquer um resolvia. A correção final **recoloca o cabeçalho** em vez de descartar a tabela.

## O falso bloqueio que era defeito da evidência

Uma pergunta legítima saía recusada mesmo com o valor certo, a página certa e citação válida. A causa não estava na guarda: o sumário do Itaú tem a primeira coluna mesclada, e o OCR a devolvia como um ano solto (`| 2025 | Resultado Recorrente Gerencial | 11.508 |`). O seletor elegia a primeira célula sem número — o ano — como rótulo da linha, e a linha chegava sem métrica à comparação.

A guarda **não** foi afrouxada para resolver: passou a exigir que o rótulo tenha pelo menos uma letra, e há contraprova de que métrica trocada, valor inventado e trimestre trocado continuam sendo recusados.

## A rota do painel sequestrando perguntas sobre o release

Quando a consulta ao painel contábil foi ligada à interface, ela passou a interceptar **5 das 45 perguntas congeladas** que pediam explicitamente o número **gerencial** do release, respondendo com o número **contábil** da CVM. Em três delas o valor era materialmente outro — no Santander do 2T2025, R$ 1.928 milhões contra R$ 3.659 milhões do release.

Corrigido com uma regra de deferência: pergunta que aponta para a camada documental nunca vira consulta contábil. Medido em 0 de 45 depois da correção. **O que a correção não resolve** está declarado nas limitações.

## Quatro defeitos de tela

Um ensaio da interface encontrou um erro vermelho exibido em toda tela do modo demonstração (era estado declarado, não falha), texto cru do OCR nos painéis de fonte, valores contábeis ilegíveis em voz alta e um caso em que dois `R$` na mesma resposta seriam interpretados como fórmula matemática pelo *markdown*. Todos corrigidos, com testes que travam o que a correção não pode custar — nenhum número pode se perder do trecho limpo, e um erro de cache verdadeiro precisa continuar aparecendo como erro.
