# 💡 Grande ideia

Confiança na informação financeira pública. Toda companhia aberta é obrigada a divulgar seus resultados, mas divulgar não resolve dois problemas diferentes: tornar o conteúdo compreensível para quem não é do mercado, e tornar a busca por um número específico rápida e confiável para quem já é, o analista que precisa localizar e conferir um dado entre centenas de páginas e não pode se dar ao luxo de citar um valor que a fonte não sustenta.

---

# ❓ Pergunta essencial

> Como a tecnologia pode ajudar alguém a entender os resultados de uma empresa aberta sem depender exclusivamente da interpretação de terceiros, e como saber quando essa tecnologia está errada?

---

# 🎯 Desafio

Construir um assistente que responda perguntas sobre os resultados trimestrais dos cinco bancos listados do Brasil cruzando duas fontes que hoje vivem separadas: os releases de resultado que cada banco publica em PDF e os formulários contábeis que esses mesmos bancos arquivam na CVM. Os documentos são indexados para busca semântica e o painel contábil oficial é carregado em um banco analítico consultável por linguagem natural, de modo que a mesma pergunta possa ser respondida pela leitura do release, pelo dado arquivado no regulador, ou pelos dois lado a lado. É assim que o sistema alcança a pergunta que nenhuma das fontes responde sozinha: o número que o banco divulgou bate com o que ele arquivou, e por que existe diferença entre eles?

Sobre essa base trabalham dois agentes separados por isolamento de contexto. O primeiro investiga e registra como chegou à resposta. O segundo recebe apenas a afirmação final e as fontes citadas, nunca o raciocínio que as produziu, e tenta derrubá-la refazendo as consultas por conta própria. A divisão não é por fonte de dado, e sim pelo que cada cabeça pode ver: o auditor acrescenta informação justamente porque desconhece o caminho percorrido pelo primeiro, o que o impede de apenas concordar com ele. Um modelo supervisionado treinado sobre o mesmo painel contábil mede se essa camada de dados sustenta uma tarefa de previsão, avaliado contra baselines e reportado com franqueza, mas deliberadamente não exposto como previsão sobre companhia nomeada, porque isso contradiria o limite que o próprio sistema impõe adiante.

Esse limite é a parte mais importante do desafio. Uma camada de segurança bloqueia tentativas de injeção de instruções, anonimiza dados pessoais que o usuário porventura forneça e recusa pedidos de recomendação de investimento, atividade privativa de analista credenciado pela Resolução CVM 20/2021. A resposta sai por padrão em linguagem acessível a quem não é do mercado, explicando cada termo técnico no primeiro uso, com a evidência disponível em painéis para quem quiser conferir. E vale, acima de tudo, a restrição que atravessa o projeto inteiro e que precisa ser medida em vez de apenas afirmada: o assistente nunca afirma o que não está na fonte e declara explicitamente quando não sabe, mesmo que o modelo de linguagem saiba a resposta de memória.

## 🗣️ O desafio em oito perguntas

A forma mais direta de descrever o que o sistema precisa fazer é listar as perguntas que ele recebe de quem não é do mercado, porque duas delas não devem ser respondidas de jeito nenhum.

| Pergunta | O que o sistema faz |
|---|---|
| "O Banco do Brasil ganhou ou perdeu dinheiro?" | Responde com o valor e cita documento, período e linha |
| "Qual desses cinco bancos deu mais lucro?" | Compara, resolvendo antes que cada banco arquiva o lucro em um código de conta diferente |
| "O lucro caiu? Por quê?" | Traz a variação calculada e o que a administração apontou como causa, com a página |
| "O que é ROE?" | Explica em linguagem simples, com a definição de origem citada junto |
| "Vi outro número na notícia. Quem está errado?" | Ninguém: mostra o gerencial e o contábil lado a lado e explica a diferença |
| "E o Nubank? E o Inter?" | Respostas diferentes para perguntas que parecem iguais. O Inter está no painel do regulador mas não no corpus de documentos, então recebe o número com a declaração do que falta; o Nubank não está em nenhum dos dois e é recusado, com o motivo |
| "Devo comprar essa ação?" | Recusa e explica: é atividade privativa de analista credenciado |
| "E o quarto trimestre?" | Responde marcando que o valor é derivado, porque o regulador não recebe informação trimestral no 4T |

As duas últimas linhas são o desafio de verdade. Responder é a parte fácil; saber quando não responder é o que precisa ser medido.

---

# 🙋 Justificativa pessoal

Projeto de portfólio quase sempre cai em um de dois lados: ou é um exercício genérico, que não corresponde a nada que alguém precise de verdade, ou exige um repertório de mercado que quem está entrando na área ainda não tem. Sou engenheiro civil em transição para Dados e Inteligência Artificial. Reconheço um problema real numa obra, mas não sei, de saída, o que dói de verdade dentro de um banco, de uma seguradora ou de uma indústria.

Foi para resolver isso que construí uma ferramenta de ideação. Ela parte de um setor real, pesquisa com fontes as dores que ele de fato tem e as competências que a área efetivamente cobra, e daí deriva escopo e especificação antes de qualquer linha de código. A intenção é que alguém sem repertório naquele domínio consiga entendimento inicial suficiente para começar um projeto que faça sentido fora da sala de aula.

O que me fez escolher este recorte entre os possíveis não foi a sugestão da ferramenta. Foi ter esbarrado uma vez com um release de resultados de banco e achado o documento incompreensível para quem não é do mercado: a informação é pública e gratuita, mas está escrita para quem já sabe onde procurar e domina o vocabulário do setor.

Reconheci ali o mesmo problema que a ferramenta tenta resolver, uma escala abaixo, alguém de fora diante de um conteúdo escrito para quem já está dentro. Por ser leigo na área, e ao ver que a informação é escrita para um público específico e fica esparsa dentro de um documento longo, resolvi criar uma ferramenta que ajude tanto o leigo quanto o especialista a buscar a informação mais rapidamente, economizando tempo nas próprias análises, sem decidir pela pessoa, mas devolvendo a ela a informação com a fonte à vista.

Quando as aulas começaram, vi que a especificação já cobria boa parte do que a disciplina pede, e preferi aprofundar um único projeto a construir dois pela metade.
