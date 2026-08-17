# Declaração do Desafio — CBL

> Projeto da disciplina *AI Factory: Building Intelligent Systems* · Etapa 1

## Grande ideia

Confiança na informação financeira pública. Toda companhia aberta é obrigada a divulgar
seus resultados, mas divulgar não é o mesmo que tornar compreensível — o dado existe, está
disponível de graça, e ainda assim quase ninguém consegue usá-lo sem intermediário.

## Pergunta essencial

Como a tecnologia pode ajudar alguém a entender os resultados de uma empresa aberta sem
depender exclusivamente da interpretação de terceiros — e como saber quando essa tecnologia
está errada?

## Desafio

Construir um assistente que responda perguntas sobre os resultados trimestrais dos cinco
maiores bancos listados do Brasil cruzando duas fontes que hoje vivem separadas: os
*releases* de resultado que cada banco publica em PDF e os formulários contábeis que esses
mesmos bancos arquivam na CVM. O sistema indexa os documentos por busca semântica, carrega
o painel contábil oficial em banco analítico consultável por linguagem natural, e coordena
dois agentes separados por **isolamento de contexto** — um que investiga e registra como
chegou à resposta, e um auditor que recebe apenas a afirmação e as fontes citadas, **nunca o
raciocínio**, e tenta derrubá-la refazendo as consultas — para responder à pergunta que
nenhuma das duas fontes responde sozinha: *o número que o banco divulgou bate com o que ele
arquivou, e por que a diferença existe?* A divisão não é por fonte de dado: o que a segunda
cabeça acrescenta é justamente não ter visto o que a primeira pensou. Um modelo
supervisionado treinado sobre o mesmo painel mede se essa camada de dados sustenta uma
tarefa de previsão — avaliado contra baselines e reportado, mas deliberadamente **não**
exposto como previsão sobre uma companhia nomeada, porque isso contradiria o próprio limite
que o sistema impõe adiante. Uma camada de segurança bloqueia tentativas de injeção de prompt, anonimiza dados pessoais que o usuário
forneça e recusa pedidos de recomendação de investimento — atividade privativa de analista
credenciado pela Resolução CVM 20/2021. A resposta sai por padrão em linguagem acessível a
quem não é do mercado, explicando cada termo técnico no primeiro uso, com a evidência
disponível em painéis para quem quiser conferir. A restrição central, medida e não apenas
afirmada:
**o assistente nunca afirma o que não está na fonte, e declara explicitamente quando não
sabe**, mesmo que o modelo de linguagem "saiba" a resposta de memória.

### O desafio em oito perguntas

O que o sistema precisa responder — e o que precisa recusar:

| Pergunta de quem não é do mercado | O que o sistema faz |
|---|---|
| "O Banco do Brasil ganhou ou perdeu dinheiro?" | Responde com o valor e cita documento, período e linha |
| "Qual desses cinco bancos deu mais lucro?" | Compara — resolvendo antes que cada banco arquiva o lucro em um código de conta diferente |
| "O lucro caiu? Por quê?" | Traz a variação calculada e o que a administração apontou como causa, com a página |
| "O que é ROE?" | Explica em linguagem simples, com a definição de origem citada junto |
| "Vi outro número na notícia. Quem está errado?" | Ninguém — mostra o gerencial e o contábil lado a lado e explica a diferença |
| "E o Nubank? E o Inter?" | **Respostas diferentes para perguntas que parecem iguais**: o Inter está no painel do regulador mas não no corpus de documentos — o sistema entrega o número e declara o que falta; o Nubank não está em nenhum dos dois — recusa, dizendo por quê |
| "Devo comprar essa ação?" | **Recusa e explica**: é atividade privativa de analista credenciado (Res. CVM 20/2021) |
| "E o quarto trimestre?" | Responde **marcando que o valor é derivado** — o regulador não recebe informação trimestral no 4T |

As duas últimas linhas da coluna da direita são o desafio de verdade. Responder é fácil;
**saber quando não responder** é o que precisa ser medido.

## Justificativa pessoal

Projeto de portfólio quase sempre cai em um de dois lados: ou é um exercício genérico, que
não corresponde a nada que alguém precise de verdade, ou exige um repertório de mercado que
quem está entrando na área ainda não tem. Sou engenheiro civil em transição para Dados e
Inteligência Artificial — reconheço um problema real numa obra, mas não sei, de saída, o que
dói de verdade dentro de um banco, de uma seguradora ou de uma indústria.

Foi para resolver isso que construí uma ferramenta de ideação. Ela parte de um setor real,
pesquisa com fontes as dores que ele de fato tem e as competências que a área efetivamente
cobra, e daí deriva escopo e especificação antes de qualquer linha de código. A intenção é
que alguém sem repertório naquele domínio consiga entendimento inicial suficiente para
começar um projeto que faça sentido fora da sala de aula.

O que me fez escolher este recorte entre os possíveis não foi a sugestão da ferramenta. Foi
ter esbarrado uma vez com um release de resultados de banco e achado o documento
incompreensível para quem não é do mercado: a informação é pública e gratuita, mas está
escrita para quem já sabe onde procurar e domina o vocabulário do setor.

Reconheci ali o mesmo problema que a ferramenta tenta resolver, uma escala abaixo — alguém
de fora diante de um conteúdo escrito para quem já está dentro. A diferença é que essa
barreira não é só minha: é de qualquer pessoa que queira saber como foi o resultado do banco
onde ela tem conta. Foi isso que me convenceu a construir um assistente que tornasse esse
conteúdo consultável em linguagem natural — sem decidir pela pessoa, mas devolvendo a ela a
informação com a fonte à vista.

Quando as aulas começaram, vi que a especificação já cobria boa parte do que a disciplina
pede, e preferi aprofundar um único projeto a construir dois pela metade.

---

## Validação de viabilidade (checklist da Etapa 1)

| Camada | Este projeto |
|---|---|
| **Dados estruturados** | `companhias` ⋈ `fatos_contabeis` em DuckDB, a partir dos conjuntos ITR/DFP do portal de dados abertos da CVM |
| **Documentos para RAG** | 20 *releases* de resultado (5 bancos × 4 trimestres), públicos e gratuitos, mais um glossário de termos ancorado em definições públicas — todos indexados em ChromaDB |
| **Problema de ML** | Classificação binária: a companhia reportará prejuízo em T+1? Treinada sobre o painel CVM, com divisão temporal e baselines. Avaliada offline — não exposta como previsão sobre companhia nomeada |
| **Agentes** | Investigador (cobertura, busca, SQL, indicadores) e Auditor de contexto isolado, que só vê a afirmação e as citações e tenta falsificá-las; ambos comparados contra um agente único e contra uma resolução determinística sem LLM |
| **Segurança** | PII fornecida pelo usuário; injeção de prompt; recusa de recomendação de investimento (Res. CVM 20/2021) |

Detalhamento técnico de cada camada na especificação do projeto.
