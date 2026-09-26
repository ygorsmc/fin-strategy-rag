# Roteiro de apresentação — Etapa 1 (4 minutos)

Roteiro do vídeo de demonstração, sincronizado com `docs/apresentacao_etapa1.pptx`.
O que está entre aspas é fala; o que está em `código` é o que se digita na tela.

**Como o tempo foi dividido.** A rubrica dá 70% a *sistema funcional: interface,
dados e RAG*, e nomeia quatro coisas que precisam **aparecer na tela**:
streaming, session state, UX writing contextualizado e system prompt específico.
Por isso a demonstração ocupa 1m45 dos 4 minutos — o maior bloco isolado — e
cada uma das quatro é dita em voz alta no momento em que aparece: o corretor
precisa ver **e** ouvir.

| Bloco | Slide | Tempo | Acumulado |
|---|---|---|---|
| Abertura | 1 | 5 s | 0:05 |
| Problema | 2 | 25 s | 0:30 |
| Relevância — os dois números medidos | 3 | 30 s | 1:00 |
| Arquitetura: quatro portas | 4 | 18 s | 1:18 |
| Como a resposta é montada | 5 | 30 s | 1:48 |
| **Demonstração ao vivo** | 6 (fundo) | **1 min 45 s** | 3:33 |
| Por que não inventa número | 7 | 15 s | 3:48 |
| Fecho | 8 | 8 s | 3:56 |

**A fala foi cronometrada, não estimada.** São **584 palavras**: 3m54 a 150
palavras por minuto, 3m32 a 165. A 150 não sobra tempo para digitar, então
**cole as perguntas em vez de digitá-las** — as quatro estão prontas abaixo, e
digitar ao vivo custa uns 20 segundos que o roteiro não tem. Os 13 segundos de
espera do D4 não são custo extra: a narração daquele bloco existe para cobri-los.

**Se estourar o tempo, corte o slide 7** — é o único cujo conteúdo já foi dito
antes: o system prompt aparece no slide 5 e a recusa aparece na demonstração.
Os slides 3 e 5 não se cortam; são eles que sustentam os dois critérios.

---

## 0:00 – 0:30 · Slides 1 e 2 — o problema

*(Slide 1 no ar na primeira frase; passe para o 2 em seguida.)*

> "Todo trimestre, os cinco bancos deste projeto publicam duas versões do mesmo
> resultado: o release em PDF, escrito para o mercado, e os formulários que o
> mesmo banco entrega à CVM. As duas são públicas, e quase ninguém abre as duas.
>
> Quem é de fora não entende o que leu. Quem é de dentro não pode citar um
> número que a fonte não sustenta — e leva tempo demais para achá-lo."

---

## 0:30 – 1:00 · Slide 3 — por que isso importa

Sustenta o critério de relevância com dois números medidos **dentro do próprio
projeto**. Deixe cada um no ar alguns segundos.

> "Não é hipotético, e eu tenho dois números do próprio projeto.
>
> No segundo trimestre de 2025, o lucro do Santander é **um vírgula nove
> bilhões** pelo contábil arquivado na CVM, e **três vírgula sete bilhões** pelo
> gerencial do release. Mesmo trimestre, mesma empresa, nenhum dos dois errado.
>
> O segundo caso é pior, porque é invisível: a conta 3.09 é lucro líquido em três
> dos cinco bancos; nos outros dois, é outra coisa. Consultar sem saber disso
> devolve número plausível e errado, sem nenhum sinal."

---

## 1:00 – 1:18 · Slide 4 — arquitetura

> "É uma interface de chat em Streamlit, e a pergunta passa por até quatro
> portas: guardrails, o painel contábil sem modelo nenhum, o modelo como
> intérprete, e o RAG. A ordem é a que gasta menos — só chega ao modelo o que as
> anteriores não resolvem."

---

## 1:18 – 1:48 · Slide 5 — como a resposta é montada

Responde à pergunta que o corretor vai ter: *se tem RAG, o que o modelo faz
quando o rodapé diz "nenhuma chamada externa"?*

> "A maioria das perguntas não passa pelo modelo. São cinco passos
> determinísticos: uma expressão regular tira período e conceito, a companhia
> vira código CVM, o mapa semântico acha a conta certa **daquele** banco — é ele
> que resolve o problema do slide anterior —, o DuckDB devolve o valor com a
> procedência, e a frase sai de um template em Python.
>
> O modelo entra em dois casos só: narrativa do release, e conceito fora do
> painel. E há dois agentes construídos, com o isolamento travado por dezesseis
> testes; medir os três braços é da próxima etapa."

**Vire para a tela compartilhada agora.**

---

## 1:48 – 3:33 · Demonstração (slide 6 como fundo)

### D1 · 20 s — UX writing e valor derivado

Digite: `Qual foi o lucro do Itaú no segundo semestre de 2025?`

> "Semestre não existe no painel — ele guarda trimestre. O sistema traduz, soma
> os dois e responde em uma frase. Repare no valor legível ao lado do exato, na
> marca de **valor derivado** — o quarto trimestre não existe como ITR, foi
> calculado — e na procedência abaixo."

### D2 · 15 s — a interface pergunta de volta

Digite: `Qual foi o lucro do Itaú?`

> "Sem período, ele não chuta e não despeja a série inteira: pergunta de volta,
> e diz em que formato responder. Isso é **UX writing escrito para este
> domínio** — a pergunta incompleta é do usuário, mas quem resolve é a interface."

### D3 · 12 s — guardrail

Digite: `Devo comprar ações do Itaú agora?`

> "Recomendação de investimento é atividade privativa de analista credenciado,
> pela Resolução CVM 20/2021. O sistema recusa citando a norma — e recusa
> **antes** de qualquer chamada externa, com custo zero."

### D4 · 45 s — RAG com streaming

Digite: `Segundo a análise gerencial do Itaú Unibanco, qual foi o resultado recorrente gerencial no 2T2025?`

**Narre durante os ~13 segundos de espera** — o silêncio é a parte que precisa
de explicação, não um defeito a esconder:

> "Essa é a única das quatro que chama o modelo, e ela demora uns treze segundos
> antes de aparecer texto — de propósito. Ele recupera os trechos, gera a
> resposta, e só então confere se cada número aparece nos trechos citados. Se
> não aparecer, vira recusa. Ou seja: o que chega à tela **já passou pela
> validação**, e é por isso que o **streaming** começa tarde. O system prompt
> proíbe responder de memória e obriga a citação."

Quando o texto aparecer:

> "R$ 11.508 milhões, com o documento e a página de onde saiu."

### D5 · 13 s — session state

Aponte para a barra lateral.

> "E aqui na lateral: as perguntas livres caíram de cinco para quatro, e o
> orçamento da sessão foi debitado. Esse **session state** é o que impede uma
> demonstração aberta de virar uma conta aberta."

---

## 3:33 – 3:48 · Slide 7 — por que não inventa número

Curto de propósito: o system prompt já foi explicado no slide 5 e a recusa já
apareceu na demonstração. Aqui só se fecha com o número medido.

> "Tudo isso são regras que não são texto: são código com teste. E foram
> medidas — vinte de vinte ataques bloqueados, e zero falso bloqueio nas
> quarenta e cinco perguntas legítimas."

---

## 3:48 – 3:56 · Slide 8 — fecho

> "O que está aqui é o que está medido. O que ainda não está, eu deixei escrito
> na entrega. Obrigado."

---

## Antes de gravar — conferir

| | Por quê |
|---|---|
| `HABILITAR_PERGUNTAS_LIVRES=1` no `.env`, app reiniciado | Sem isso o rádio "Pergunta livre" não aparece e D4 não roda |
| Modo **Pergunta livre** selecionado na lateral | D1–D3 funcionam nos dois modos; **D4 só no livre** |
| Ollama ativo | Os embeddings da pergunta são locais; sem ele o RAG falha |
| Saldo e cota com folga na lateral | D5 depende de ver o número **cair** |
| Janela do navegador com a lateral visível | D5 aponta para ela |

**As duas perguntas pagas custam ~US$ 0,003 no total.** A de D4 é a mesma
validada no ensaio de 18/09 (`resultados/ensaio_roteiro_video_2026-09-18.md`),
conferida contra o gabarito: R$ 11.508 milhões, página 5. É a escolha segura —
uma pergunta nova pode terminar em recusa por falta de evidência, ao vivo.

**O que NÃO demonstrar:** comparação entre bancos ("quem lucrou mais") e
variação ("quanto cresceu de um trimestre para o outro"). A rota determinística
intercepta as duas e responde listando os valores **sem comparar e sem calcular
a variação**. Funciona no arnês de comparação, não na interface.

**O que NÃO afirmar:** que os dois agentes rodam na demonstração. Eles existem
em código e o isolamento é testado, mas não estão ligados à interface e a
comparação dos três braços não rodou. O slide 5 diz "construído e testado" por
isso.
