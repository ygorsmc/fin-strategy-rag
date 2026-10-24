# 🏛️ Como o sistema está montado

O caminho de uma pergunta até a resposta atravessa quatro camadas. Duas delas preparam material antes de qualquer usuário aparecer: a ingestão dos releases em PDF, que termina em dois índices de busca, e a carga dos formulários da CVM, que termina em um banco analítico. As outras duas funcionam durante a conversa: as ferramentas que consultam esse material e os agentes que decidem o que perguntar a elas. Na Etapa 2 entraram mais duas peças: um modelo de classificação treinado offline sobre o painel, que as ferramentas leem na forma de um resumo agregado, e o Langfuse, que registra o percurso de cada pergunta.

```text
corpus público (PDF)                   dados abertos CVM (ITR/DFP)
  │                                       │
  ▼                                       ▼
extração + chunking (600/100 tokens)   painel contábil em DuckDB
validação estrutural + sentinelas      companhias ⋈ fatos_contabeis
  │                                       │ mapa_contas ⇒ fatos_semanticos
  │                                       │ (4º trimestre derivado e marcado)
  ├──► índice BM25 (palavra-chave)        ├──► modelo de prejuízo (offline)
  └──► embeddings ──► índice vetorial     │      └──► panorama agregado
                        │                 │
                        ▼                 ▼
        ┌──────────────────────────────────────────┐
        │ FERRAMENTAS: verificar_cobertura ·       │
        │ buscar_trechos · consultar_cvm ·         │
        │ calcular_indicadores ·                   │
        │ consultar_modelo_prejuizo                │
        └──────────────────────────────────────────┘
                        ▲
pergunta → guardrails → Investigador → [filtro de contexto]
                                        │ só a afirmação + citações
                                        ▼
                                     Auditor → guardrails → resposta

Langfuse: um trace por pergunta, com spans de recuperação, geração,
agentes e ferramentas
```

Há um detalhe de projeto que vale explicar, porque não é óbvio olhando o diagrama. O sistema tem dois caminhos de execução separados de propósito. O caminho interativo, que é o produto, passa pelos guardrails e pelos agentes. Já o caminho de avaliação, usado para comparar as estratégias de busca, roda o pipeline determinístico de recuperação e geração sem a camada de agentes, porque a orquestração multiagente introduz variabilidade no plano de execução e isso destruiria a comparabilidade entre as estratégias, mesmo com a temperatura zerada. Os dois caminhos compartilham as mesmas ferramentas e o mesmo prompt; apenas a orquestração difere.

---

# 📄 A camada documental

## O corpus

São vinte releases de resultado, cinco bancos ao longo de quatro trimestres, todos baixados das páginas públicas de relações com investidores. O arquivo `corpus/metadados.csv` funciona como fonte de verdade e guarda, para cada documento, a URL de origem, a data e o SHA-256 do arquivo. Os PDFs em si ficam fora do Git, já que podem ser baixados de novo por script, e o hash é o que permite verificar depois que o arquivo usado numa medição é exatamente aquele que foi indexado.

## A extração

Release de banco é um documento hostil para extração automática. O conteúdo que interessa está em tabelas de muitas colunas, cercado de notas de rodapé, texto em duas colunas e números que só significam alguma coisa quando lidos junto do cabeçalho da coluna. O extrator primário escolhido foi o Mistral OCR, e a escolha se apoia em três características dele.

A primeira é que ele lê a página como imagem e reconstrói a estrutura, em vez de raspar a camada de texto do PDF. A tabela volta como tabela, com a linha de cabeçalho preservada, e é isso que permite ao sistema saber que 11.508 é o Resultado Recorrente Gerencial do segundo trimestre de 2025, e não um número solto no meio da página. A segunda é que ele funciona mesmo quando a fonte embutida no PDF não tem mapa de caracteres, situação que parece exótica mas apareceu neste corpus: na demonstração anual do BTG, 63 das 71 páginas devolviam apenas sequências como `(cid:127)` para extratores que dependem da camada de texto. Para um modelo que enxerga a página, a codificação do arquivo é irrelevante. A terceira é a ordem de leitura, que ele preserva em layouts de múltiplas colunas, evitando que dois blocos de texto paralelos se intercalem e produzam frases sem sentido.

O efeito disso aparece na estrutura recuperada: 37.612 linhas de tabela reconstruídas, contra 28.268 do extrator alternativo, o `pdfplumber`, que segue disponível atrás da mesma interface. Como OCR custa dinheiro, o resultado de cada documento fica gravado em um cache endereçado pelo hash do PDF, e reprocessar o corpus não gera nova cobrança.

## A divisão em blocos

O texto extraído é dividido em blocos de 600 tokens com 100 de sobreposição, e a divisão respeita o tipo de conteúdo. Prosa é cortada em fronteira de parágrafo ou de sentença. Tabela nunca é partida no meio de uma linha, e quando uma tabela é maior que o bloco ela é dividida em partes que repetem a linha de cabeçalho, pela mesma razão que motivou a escolha do extrator: valor sem o nome da coluna não pode ser citado. A sobreposição existe para que um trecho próximo da fronteira apareça em dois blocos, o que evita perder justamente o valor que caiu na divisão.

Cada bloco carrega consigo os metadados que a citação exige, a saber, a empresa, o documento, o trimestre e as páginas inicial e final de onde o texto veio. O corpus inteiro resulta em 7.147 blocos.

## As estratégias de recuperação

A pergunta do usuário não vai direto ao modelo de linguagem. Antes disso, o sistema procura, entre os 7.147 blocos, os cinco mais promissores, e apenas esses cinco entram no prompt como contexto. O modelo responde olhando só para eles.

É por isso que a recuperação decide o resultado. Se o trecho que contém a resposta não estiver entre os cinco selecionados, o modelo não tem como acertar, e a regra de fundamentação o obriga a recusar em vez de arriscar um palpite. Como não existe uma forma única e óbvia de escolher esses cinco trechos, o projeto implementa cinco maneiras diferentes e as compara sob o mesmo orçamento de contexto.

| Estratégia | Como escolhe os trechos | O que ela testa |
|---|---|---|
| E0, closed-book | Não escolhe nada: o modelo responde sem documento algum | Serve de controle e mostra quanto o modelo já sabe de pré-treinamento |
| E1, palavra-chave | BM25, por coincidência de termos entre pergunta e trecho | A linha de base clássica, forte quando a pergunta usa as palavras do documento |
| E2, semântica | Compara o significado da pergunta com o do trecho, via embeddings | Encontrar o trecho certo mesmo quando ele usa outro vocabulário |
| E3, híbrida | Funde as listas de E1 e E2 por Reciprocal Rank Fusion | Se combinar as duas evidências supera cada uma isolada |
| E4, tabela de fatos | Ranqueia pelo quanto o trecho contém números da métrica perguntada | Encontrar a tabela, que é onde mora o valor exato |

A última merece explicação, porque nasceu de um problema concreto. Recuperar a página certa não basta: a prosa da página costuma arredondar, dizendo algo como "R$ 3,4 bilhões", enquanto a tabela com o valor exato, 3.431, fica de fora dos cinco selecionados. A estratégia E4 existe para alcançar essa tabela.

---

# 🗄️ A camada de dados estruturados

O painel é carregado a partir dos conjuntos ITR e DFP do portal de dados abertos da CVM, e o resultado é um conjunto de tabelas relacionadas em DuckDB, não uma planilha solta. A relação central liga `companhias` a `fatos_contabeis` pelo código CVM da companhia, e cada linha contábil encontra seu significado em `mapa_contas` pelo par formado pelo plano de contas e o código da conta.

| Tabela | Registros | Papel |
|---|---|---|
| `companhias` | 470 | Cadastro: código CVM, CNPJ, denominação social, setor, ticker e plano de contas |
| `fatos_contabeis` | 553.856 | Linhas contábeis por companhia, trimestre, demonstrativo e conta |
| `mapa_contas` | 68 | Mapa semântico que traduz código de conta em conceito de negócio |
| `indicadores` | 2.321 | Indicadores derivados por companhia e trimestre |
| `correcoes_contabeis` | 4 | Correções com procedência obrigatória: documento, página, SHA-256 e evidência |
| `fatos_semanticos` | visão | Junta as demais e entrega o conceito já resolvido, marcando o que é derivado e o que foi corrigido |

## Por que existe um mapa de contas

Esta é a parte do projeto com maior potencial de causar dano silencioso, e a razão de o painel só ser liberado depois de passar por uma verificação bloqueante. O mesmo código de conta designa linhas diferentes conforme o plano de contas adotado pela companhia. O código 3.09, por exemplo, é lucro líquido no Itaú, no Santander e no BTG, mas significa resultado antes das participações no Banco do Brasil e no Bradesco. Uma consulta ingênua devolveria, para dois dos cinco bancos, um número plausível, não nulo e errado, sem levantar erro algum. É exatamente a falha que o projeto existe para combater, reproduzida dentro da própria base de dados.

A consequência prática é que nenhuma consulta pode referenciar o código de conta diretamente. Todo conceito passa pelo mapa semântico validado, e a lista branca que governa o SQL rejeita qualquer tentativa de contornar esse caminho.

## Consulta em linguagem natural

A rota estruturada da interface interpreta a pergunta, resolve de que companhia se trata, qual conceito está sendo pedido e a qual trimestre ele se refere, e só então monta a consulta. Todo esse percurso acontece sem chamar modelo de linguagem, o que significa que ele funciona sem nenhuma chave configurada e sem gerar custo. Uma resposta real da interface:

> ITAU UNIBANCO HOLDING S.A. (CD_CVM 019348) está nas duas camadas em 3T2025: há release indexado e fatos contábeis no painel da CVM. Patrimônio líquido consolidado em 3T2025: R$ 224,71 bilhões (R$ 224.707.000.000,00).

Junto do texto, a interface mostra uma tabela com os fatos usados e a procedência de cada um deles no painel.

---

# 🛡️ As regras que o código verifica

Doze regras de negócio governam o comportamento do sistema, e a diferença entre elas e uma lista de boas intenções é que cada uma tem verificação em código e teste que falha quando ela é violada. As que o usuário percebe na tela são estas:

| Regra | O que exige |
|---|---|
| RN01 | Toda resposta cita empresa, documento, trimestre e página dos trechos usados |
| RN02 | Sem evidência suficiente no trecho recuperado, o sistema declara isso em vez de responder de memória |
| RN05 | Nada de recomendação de investimento, preço-alvo ou aconselhamento pessoal, conforme as Resoluções CVM 20/2021 e 19/2021 |
| RN06 | Dado pessoal digitado pelo usuário é anonimizado antes de qualquer chamada externa e não entra em log nem em cache |
| RN09 | Código de conta nunca é chave de significado sozinho: todo conceito passa pelo mapa semântico |
| RN10 | Valor obtido por aritmética entre períodos sai marcado como derivado, com a conta explicitada |
| RN11 | Companhia é resolvida por código CVM, nunca por nome; nome ambíguo gera pergunta de desambiguação em vez de escolha automática |
| RN12 | A ausência de evidência é classificada em três estados: presente nas duas camadas, presente só no painel, ou ausente em ambas |

A RN12 é a que produz respostas diferentes para perguntas que parecem iguais. O Banco Inter arquiva na CVM mas não tem release no corpus, então a pergunta sobre ele recebe o número contábil acompanhado da declaração do que não pode ser dito. O Nubank não está em nenhuma das duas camadas, e a pergunta é recusada com o motivo explicado.

A RN10 aparece sempre que alguém pergunta pelo quarto trimestre. O regulador não recebe informação trimestral nesse período, apenas o acumulado do ano, de modo que o valor do 4T precisa ser obtido subtraindo o acumulado do terceiro trimestre do total anual. O número é legítimo, mas não é um dado arquivado, e a interface diz isso em vez de apresentá-lo como se fosse.

---

# 💬 O prompt e a verificação da resposta

O prompt de geração foi escrito para este domínio e tem sete regras invioláveis. Três delas explicam a maior parte do comportamento observável. A primeira proíbe usar conhecimento próprio: se a informação não estiver literalmente nos trechos fornecidos, o modelo precisa recusar, mesmo que saiba a resposta. A segunda manda copiar o número exatamente como impresso, com os mesmos dígitos, a mesma pontuação e a mesma unidade, sem converter escala, de forma que um trecho dizendo "R$ 6.067 milhões" não vire "R$ 6,1 bilhões" na resposta. A terceira determina que tanto o trecho recuperado quanto a própria pergunta sejam tratados como entrada não confiável, ignorando qualquer instrução embutida neles.

A saída não é texto livre, e sim um objeto JSON com a resposta, um sinalizador de recusa, o motivo da recusa quando houver, e a lista de citações. Esse contrato existe para que a citação possa ser verificada por código em vez de depender da formatação do texto.

E a verificação de fato acontece. Depois da geração, uma guarda confere se todo valor numérico presente na resposta aparece nos trechos citados. Quando algum número não aparece, a resposta inteira é rebaixada para recusa. É essa etapa, e não a boa vontade do modelo, que impede a alucinação numérica de chegar à tela.

---

# 🖥️ A interface

O chat foi feito em Streamlit e abre em um de três modos, escolhidos na barra lateral. O modo de demonstração consulta o painel contábil, funciona sem nenhum segredo configurado e não gera custo; as respostas pré-computadas da rodada avaliada entram nele depois da auditoria humana. Cada modo abre dizendo o que cobre, com os bancos e os trimestres do corpus lidos do manifesto, e oferece exemplos que se enviam com um clique, pelo mesmo caminho da pergunta digitada, com a mesma cota. O modo de pergunta livre aciona a inferência ao vivo sobre os releases, precisa ser habilitado explicitamente e está sujeito a uma cota de perguntas por sessão e a um teto de orçamento. O modo Agentes, da Etapa 2, segue as mesmas regras e mostra na tela cada ferramenta que os agentes chamam enquanto trabalham.

A resposta aparece na tela aos poucos, palavra por palavra. Essa escolha tem uma consequência que vale registrar: o que é transmitido é a resposta já validada, não o texto cru que o provedor devolve. Como a guarda de fundamentação só consegue decidir depois de ver o texto inteiro, transmitir o rascunho colocaria na tela, ainda que por um segundo, exatamente o número que a guarda vai derrubar em seguida.

Quando a guarda de fundamentação descarta uma resposta, a tela diz em linguagem comum o que faltou e o que tentar, por exemplo perguntar um banco e um trimestre por vez; o diagnóstico técnico da regra fica numa legenda. Quando um nome designa mais de uma companhia, como o BTG, as candidatas aparecem como botões; a escolha, ou o código digitado, refaz a pergunta com o código da CVM, e é o usuário quem decide, nunca o sistema. Para companhia que está no painel e não no corpus, a resposta diz que não há release dela. Abaixo de cada resposta, a interface mostra os trechos recuperados, com os que foram efetivamente citados aparecendo primeiro e destacados. Nas consultas ao painel contábil ela exibe também a tabela de fatos, um aviso quando algum valor é derivado e a procedência de cada linha. Em toda resposta, por fim, ficam indicados o modo de operação e o provedor que a gerou, para que ninguém confunda uma resposta pré-computada com uma inferência feita na hora.
