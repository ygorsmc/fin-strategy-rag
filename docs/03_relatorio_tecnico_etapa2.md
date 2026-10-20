# Relatório técnico da Etapa 2

Nesta etapa, o Assistente de Research Financeiro ganhou um classificador de prejuízo treinado com dados abertos da CVM, dois agentes CrewAI que consultam o painel contábil, os releases e o próprio modelo, traces no Langfuse e uma suíte DeepEval sobre as 45 perguntas do golden dataset. O que mais me ensinou veio da avaliação: o DeepEval concordou com a minha auditoria manual em apenas 4 de 10 casos, e entender essa diferença guiou as correções descritas no final.

## O dataset

O modelo usa o painel de demonstrações contábeis das companhias abertas, montado com os formulários ITR e DFP do [Portal de Dados Abertos da CVM](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC). São 741 companhias e 21.903 pares de companhia e trimestre entre o 1T2011 e o 4T2025, cada um descrito por 15 variáveis calculadas só com o que se sabia até o trimestre T, como ROE, ROA, alavancagem, porte e histórico de prejuízos. A variável-alvo é o prejuízo líquido consolidado no trimestre seguinte, presente em 33,3% dos casos. O produto usa uma versão mais exigente, com prejuízo em dois trimestres seguidos, que deixa 21.119 observações e 22,3% de positivos.

A escolha vem do próprio domínio: o assistente ajuda um analista a ler os releases de cinco bancos e a conferi-los contra a CVM, e o modelo amplia esse trabalho com uma triagem do mercado inteiro. Como os cinco bancos tiveram um único prejuízo em 173 trimestres, o modelo diz pouco sobre eles, e por isso o chat o apresenta de forma agregada.

## As métricas e a escolha do modelo

Priorizei o recall, com o limiar escolhido pelo F2 na validação, porque numa triagem deixar passar uma companhia que terá prejuízo custa mais do que um alarme falso, que o analista descarta lendo o balanço. A divisão respeitou o tempo: treino até o 2T2025, limiar no 3T2025 e teste no 4T2025, com 413 companhias, 32% delas com prejuízo. Os baselines foram construídos antes dos modelos.

| Modelo (teste 4T2025, alvo T+1) | Limiar | Accuracy | Precision | Recall | F1 | ROC-AUC |
| --- | --- | --- | --- | --- | --- | --- |
| Classe majoritária | — | 0,680 | 0,000 | 0,000 | 0,000 | — |
| Persistência (prejuízo em T prevê T+1) | — | 0,777 | 0,647 | 0,667 | 0,657 | 0,748 |
| Regressão logística | 0,131 (F2) | 0,758 | 0,573 | 0,955 | 0,716 | 0,928 |
| Gradient boosting | 0,049 (F2) | 0,584 | 0,434 | 0,992 | 0,604 | 0,925 |
| Gradient boosting | 0,500 | 0,864 | 0,828 | 0,727 | 0,774 | 0,925 |

Para um gerente, eu explicaria primeiro que a accuracy engana, já que prever lucro para todas as companhias acerta 68% sem achar nenhum prejuízo. No limiar do F2, o gradient boosting encontra 131 dos 132 prejuízos ao custo de 171 alarmes falsos, que é a troca desejada. No chat, porém, o modelo ordena companhias por risco, e então o que vale é o ROC-AUC: na média de 47 trimestres em walk-forward, ele marca 0,865, contra 0,846 do melhor baseline, que é a fração de prejuízos nos últimos quatro trimestres. Há ainda uma ressalva: dentro de uma mesma companhia, o AUC cai para 0,663. Em outras palavras, o modelo sabe quais companhias costumam dar prejuízo, mas não em que trimestre uma empresa lucrativa vai virar.

O produto usa o alvo de dois trimestres, que elimina o ruído do prejuízo isolado e eleva o AUC em walk-forward para 0,879. Nesse alvo, os 10% de companhias com maior escore têm 3,4 vezes a taxa média de prejuízo. A regressão logística e o boosting empataram, e mantive o boosting por lidar com dados ausentes sem imputação.

## Os agentes

O chat ganhou um modo com dois agentes CrewAI isolados um do outro. O Investigador descobre em que camada de dados a companhia existe, busca a informação e responde citando a fonte. Ele usa `verificar_cobertura`, que diz se a companhia está no painel, nos releases ou nos dois, `buscar_trechos`, que pesquisa os releases no ChromaDB, `consultar_cvm` e `calcular_indicadores`, que leem o painel no DuckDB, e `consultar_modelo_prejuizo`, que acessa o modelo de ML. O Auditor usa as mesmas ferramentas numa caixa própria e refaz as consultas para confirmar, contestar ou declarar que não reproduz a resposta. Ele recebe apenas a afirmação e as citações, nunca o raciocínio do Investigador.

Entre os dois, o código confere se cada citação veio de uma ferramenta e se cada valor em reais aparece na evidência sob a mesma métrica. Quando algo falha, a resposta é recusada antes de o Auditor ser chamado.

Como a Resolução CVM 20/2021 regula a análise de valores mobiliários, o modelo não faz previsão sobre companhia nomeada. Por isso, a ferramenta do modelo recebe apenas um valor de ativo e devolve a faixa de porte com sua taxa histórica de prejuízo. Na pergunta "qual foi o lucro do Banco Inter no 3T2025 e em que faixa de porte ele se encaixa no modelo?", o Investigador consultou lucro e ativo no DuckDB e passou o ativo de R$ 91,8 bilhões ao modelo. A resposta trouxe a faixa de R$ 10 a 100 bilhões e a taxa de 21,8%, apresentada como taxa da faixa e não como chance do Inter, e o Auditor a confirmou.

O diagrama abaixo resume esse fluxo.

```text
pergunta no chat (Streamlit)
  │
  ▼
guardrails de entrada ─────────────────────► recusa sem LLM,
(PII, injeção, tópico proibido, RN07)          ou rota prospectiva agregada
  │
  ▼
Investigador ◄──────► ferramentas (uma caixa por agente)
  │                     DuckDB: painel CVM · ChromaDB: releases
  │                     modelo de ML: artefato agregado
  │                     cobertura e indicadores
  ▼
verificação em código ─────────────────────► recusa registrada
(a citação veio de alguma ferramenta?          (o Auditor nem é chamado)
 o número está na fonte, na mesma métrica?)
  │
  ▼
filtro de contexto: passa só a afirmação e as citações
  │
  ▼
Auditor ◄───────────► ferramentas (caixa própria)
(reconsulta cada fonte citada;
 confirma, contesta ou não reproduz)
  │
  ▼
guardrails de saída → resposta com o veredito do Auditor

Langfuse: um trace por pergunta, com um span por etapa, agente e ferramenta
```

## Observabilidade

Cada pergunta do chat gera um trace no Langfuse, com um span por etapa e, no modo Agentes, um span por agente e por ferramenta; a etapa de geração registra tokens e custo. Em 19/10 gerei 12 traces reais e conferi pela API que o custo registrado no servidor era o mesmo calculado pelo aplicativo.

![Lista de traces no Langfuse, com latência, tokens e custo](img/langfuse_traces.png)

Nos seis traces da figura, as perguntas livres levaram de 3,9 a 13 segundos e custaram até US$ 0,0023, enquanto as perguntas aos agentes levaram de 13 a 50 segundos e custaram de 2 a 17 vezes mais. Os traces mostraram também onde o tempo se perdia: na pergunta livre mais lenta, o LLM respondeu em 1,2 segundo e a recuperação, somada à carga do pipeline, levou 11,7.

## Testes com o golden dataset e o DeepEval

O golden dataset tem 45 perguntas congeladas em 29/07, com resposta e página-fonte conferidas à mão. São 15 factuais, 10 comparativas, 10 qualitativas e 10 adversariais, que testam premissas falsas e dados ausentes do corpus. O DeepEval mediu faithfulness e answer relevancy nas respostas gravadas dessas perguntas, com um juiz de outra família, o DeepSeek V4 Flash, julgando o Gemini 3.5 Flash-Lite. Foram 196 chamadas, que custaram US$ 0,40.

| Desfecho | Perguntas | Faithfulness (média) | Faithfulness = 1 | Answer relevancy (média) |
| --- | --- | --- | --- | --- |
| Resposta publicada | 10 | 0,947 | 8 | 1,000 |
| Rascunho descartado pela guarda | 18 | 0,821 | 9 | 0,988 |
| Recusa do próprio modelo | 17 | não pontuada | — | não pontuada |

Decidi antes de rodar que uma afirmação sem sustentação contaria como infiel, porque o faithfulness padrão só penaliza contradição e, como o juiz não encontrou nenhuma, daria nota 1,0 a todas as respostas. As recusas não foram pontuadas, já que não afirmam nada.

Comparado à minha auditoria humana, feita às cegas, o DeepEval concordou em apenas 4 de 10 itens, enquanto o juiz próprio do projeto concordava em 8. Numa das discordâncias, o faithfulness aprovou o número da coluna errada de uma tabela. Criei então um critério de período em G-Eval, com passos e limiar definidos antes da execução, que reprovou esse caso e elevou a concordância para 5 de 10. O DeepEval funciona, portanto, como triagem, e a referência continua sendo a auditoria humana.

## Pontos fracos e ajustes

O ponto fraco mais caro era a guarda de evidência descartar respostas corretas: 9 dos 18 rascunhos descartados eram fiéis aos trechos, e a auditoria humana tinha encontrado 5 descartes indevidos em 15. Suspeitei de arredondamento, mas a causa era outra. O release imprime valores como "R$ 6,1 bi" em infográficos que o OCR quebra em linhas soltas, e a guarda lia uma linha por vez, separando o número da métrica. Com a leitura corrigida e reaplicada às 45 respostas gravadas, o sistema passou a publicar 14 respostas em vez de 10, sem nenhuma errada a mais. Ainda faltam as frases que reúnem várias métricas.

Os agentes também apresentaram dois problemas na primeira rodada real. O Investigador chamou de "margem financeira" os R$ 17,2 bilhões que o Itaú reportava como "despesas não decorrentes de juros", e agora o código exige o número sob a mesma métrica; reexecutada em 201 respostas gravadas, a regra não rejeitou nenhuma das 16 sabidamente corretas. Além disso, o Auditor confirmou uma resposta consultando só o DuckDB, e o "confirma" passou a exigir nova consulta a cada fonte citada.

Contra a latência, o índice agora carrega na inicialização do aplicativo, e o modo Agentes mostra cada ferramenta enquanto ela roda, embora as chamadas ao LLM, que levam até 50 segundos, continuem as mesmas.

Por fim, medi o modelo apenas nas companhias que hoje dão lucro. Entre elas, ele supera o baseline trivial, com AUC de 0,831 contra 0,787, mas dentro de cada companhia os dois empatam, com 0,624 contra 0,613. Assim, o modelo serve para indicar quais companhias ler primeiro, e não para prever quando cada uma entrará em prejuízo.
