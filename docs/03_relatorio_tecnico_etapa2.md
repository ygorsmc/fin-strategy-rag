# Relatório técnico da Etapa 2

Nesta etapa, o assistente ganhou um classificador de prejuízo treinado com dados da CVM, dois agentes CrewAI, traces no Langfuse e uma suíte DeepEval. O que mais me ensinou foi a avaliação: o DeepEval concordou com a minha auditoria manual em apenas 4 de 10 casos, e entender por quê guiou as correções do final.

## O dataset

O modelo usa o painel de demonstrações contábeis das companhias abertas, montado com os formulários ITR e DFP do [Portal de Dados Abertos da CVM](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC). São 21.903 pares de companhia e trimestre, de 741 companhias, entre 2011 e 2025, descritos por 15 variáveis calculadas só com o que se sabia até o trimestre T, como ROE, alavancagem, porte e histórico de prejuízos. A variável-alvo é o prejuízo líquido no trimestre seguinte, presente em 33,3% dos casos; o produto usa uma versão mais exigente, com prejuízo em dois trimestres seguidos.

A ligação com o domínio é direta: o assistente ajuda um analista a ler os releases de cinco bancos e a conferi-los contra a CVM, e o modelo estende esse trabalho a uma triagem do mercado inteiro. Como os cinco bancos tiveram um único prejuízo em 173 trimestres, o modelo diz pouco sobre eles, e o chat o apresenta de forma agregada.

## As métricas e a escolha do modelo

A divisão respeitou o tempo: treino até o 2T2025, limiar escolhido no 3T2025 e teste no 4T2025, com 413 companhias. Os baselines vieram antes dos modelos.

| Modelo (teste 4T2025, alvo T+1) | Limiar | Accuracy | Precision | Recall | F1 | ROC-AUC |
| --- | --- | --- | --- | --- | --- | --- |
| Sempre lucro | — | 0,680 | 0,000 | 0,000 | 0,000 | — |
| Sempre prejuízo | — | 0,320 | 0,320 | 1,000 | 0,484 | — |
| Persistência (prejuízo em T prevê T+1) | — | 0,777 | 0,647 | 0,667 | 0,657 | 0,748 |
| Regressão logística | 0,131 (F2) | 0,758 | 0,573 | 0,955 | 0,716 | 0,928 |
| Gradient boosting | 0,049 (F2) | 0,584 | 0,434 | 0,992 | 0,604 | 0,925 |

Para um gerente, eu começaria dizendo que a accuracy engana: prever lucro para todas as companhias acerta 68% sem achar um único prejuízo. O recall também engana, porque marcar todas como risco dá recall 1,0. Comecei priorizando o recall, com o limiar escolhido pelo F2, e o teste mostrou o problema: o boosting passou a marcar 302 das 413 companhias, o que já não é triagem.

A métrica que decide, então, é o ROC-AUC. No chat, o modelo não responde sim ou não; ele ordena companhias por risco, e o analista lê a lista de cima para baixo até onde o tempo permitir. Em walk-forward sobre 47 trimestres, o boosting marca 0,865, contra 0,846 do melhor baseline, a fração de prejuízos nos últimos quatro trimestres, e 0,879 no alvo do produto. A regressão logística empatou e teve F2 melhor no teste; mantive o boosting por lidar com dados ausentes sem imputação.

A ressalva que eu faria antes de o gerente perguntar é que, dentro de uma mesma companhia, o AUC cai para 0,663, e 97% das companhias no decil de maior escore já estão em prejuízo. O modelo sabe quais companhias costumam dar prejuízo, mas não em que trimestre uma lucrativa vai virar.

## Os agentes

O chat ganhou um modo com dois agentes CrewAI isolados, que reproduzem uma divisão comum em research: quem produz a análise e quem a confere. O Investigador descobre em que camada de dados a companhia existe e responde citando a fonte, com cinco ferramentas: `verificar_cobertura` (painel, releases ou ambos), `buscar_trechos` (releases no ChromaDB), `consultar_cvm` e `calcular_indicadores` (painel no DuckDB) e `consultar_modelo_prejuizo` (modelo de ML). O Auditor tem as mesmas ferramentas numa caixa própria, recebe só a afirmação e as citações e reconsulta cada fonte para confirmar, contestar ou declarar que não reproduz. Antes dele, o código recusa a resposta se algum número não aparecer na evidência sob a mesma métrica.

Por precaução com a Resolução CVM 20/2021, que regula a análise de valores mobiliários divulgada a terceiros, a instância pública não publica previsão sobre companhia nomeada; em execução local, uma variável de ambiente libera o escore de cada companhia. Na pública, o modelo entrega o panorama agregado e, dado um ativo, a faixa de porte com sua taxa histórica de prejuízo. Perguntado sobre o lucro e a faixa do Banco Inter no 3T2025, o Investigador buscou lucro e ativo no DuckDB e passou o ativo ao modelo, que devolveu a faixa de R$ 10 a 100 bilhões e a taxa de 21,8%, apresentada como taxa da faixa, não como chance do Inter. O Auditor refez as consultas e confirmou.

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
  ▼
verificação em código ─────────────────────► recusa registrada
(o número está na fonte, na mesma métrica?)    (o Auditor nem é chamado)
  │
  ▼
filtro de contexto: passa só a afirmação e as citações
  │
  ▼
Auditor ◄───────────► ferramentas (caixa própria)
(reconsulta cada fonte; confirma, contesta ou não reproduz)
  │
  ▼
guardrails de saída → resposta com o veredito do Auditor
```

Medi o modo Agentes em 7 perguntas do conjunto próprio dos agentes, separado das 45. Quatro respostas cobriram tudo o que o gabarito pede, entre elas a recusa sobre o Nubank, ausente das duas camadas, e a pergunta de desambiguação para "BTG", nome de duas companhias no painel. As outras três trouxeram números certos, mas explicaram mal por que o release e a CVM diferem. Nenhuma trouxe número errado, e o Auditor confirmou as seis que chegaram a ele: ele confere a fidelidade, não a completude.

## Observabilidade

Cada pergunta gera um trace no Langfuse, com spans de recuperação, geração, agentes e ferramentas, e cada geração registra tokens e custo. Em 20/10, rodei 19 perguntas pelo aplicativo e conferi pela API que o custo no servidor batia com o do app.

![Lista de traces no Langfuse, com latência, tokens e custo](img/langfuse_traces.png)

As perguntas livres levaram de 1,7 a 8,1 segundos e custaram até US$ 0,0021; as dos agentes, de 8 a 44 segundos e até US$ 0,035. Os traces também mostraram o que a tela escondia: em 19/10, carregar o índice e o modelo de embeddings consumia 11,7 dos 13 segundos da primeira pergunta, e os dois passaram a carregar na inicialização; em 20/10, dois traces de agentes trouxeram uma chamada ao LLM sem uso registrado, ainda não investigada.

## Testes com o golden dataset e o DeepEval

O golden dataset tem 45 perguntas congeladas em 29/07, com resposta e página-fonte conferidas à mão: 15 factuais, 10 comparativas, 10 qualitativas e 10 adversariais, com premissas falsas e dados fora do corpus. Pedidos fora do escopo, como recomendação de compra, ficam num conjunto de 20 ataques, todos bloqueados. Na rodada de 15/09, a estratégia do chat publicou 10 respostas e recusou 35, entre elas as 10 adversariais.

O DeepEval mediu faithfulness e answer relevancy dessas respostas, com um juiz de outra família, o DeepSeek V4 Flash, em 196 chamadas que custaram US$ 0,40. Decidi antes de rodar que afirmação sem sustentação contaria como infiel, porque o faithfulness padrão só penaliza contradição e daria 1,0 a todas.

| Desfecho | Perguntas | Faithfulness (média) | Faithfulness = 1 | Answer relevancy (média) |
| --- | --- | --- | --- | --- |
| Resposta publicada | 10 | 0,947 | 8 | 1,000 |
| Rascunho descartado pela guarda | 18 | 0,821 | 9 | 0,988 |
| Recusa do próprio modelo | 17 | não pontuada | — | não pontuada |

Contra a minha auditoria humana, feita às cegas, o DeepEval concordou em 4 de 10 itens, e o juiz próprio do projeto, em 8. Numa discordância, o faithfulness aprovou o número da coluna errada de uma tabela. Criei então um critério de período em G-Eval, com passos e limiar fixados antes, que reprovou esse caso e levou a concordância a 5 de 10, diferença que dez itens não distinguem do acaso. O DeepEval serve como triagem, e a referência continua sendo a auditoria humana.

## Pontos fracos e ajustes

O ponto fraco mais caro era a guarda de evidência descartar respostas corretas: 9 dos 18 rascunhos descartados eram fiéis aos trechos. Suspeitei de arredondamento, mas o release imprime valores como "R$ 6,1 bi" em infográficos que o OCR quebra em linhas soltas, e a guarda separava o número da métrica. Com a leitura corrigida e outros três ajustes, achados nas perguntas de desenvolvimento, as mesmas respostas gravadas renderam 15 publicações em vez de 10, sem nenhuma errada a mais. O ganho, porém, foi medido nas perguntas que revelaram o defeito, e seguem descartadas três respostas que a auditoria humana julgou certas.

Na primeira rodada real dos agentes, em 19/10, o Investigador chamou de "margem financeira" R$ 17,2 bilhões de despesas do Itaú, e o Auditor confirmou a resposta do Inter sem consultar o modelo citado. O código passou a exigir o número sob a mesma métrica e a reconsulta de cada fonte, e em 20/10 a mesma pergunta trouxe a margem correta, R$ 31.382 milhões.

Por fim, nas companhias hoje lucrativas, o modelo supera o baseline trivial (AUC de 0,831 contra 0,787), mas dentro de cada companhia os dois empatam (0,624 contra 0,613), e o painel de treino herda defeitos da CVM, como valores declarados em milhares num formulário e em reais noutro, de efeito não medido. O modelo serve, portanto, para indicar quais companhias ler primeiro, e não para prever quando cada uma entrará em prejuízo.
