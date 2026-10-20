# 📝 Relatório técnico — Etapa 2

Na Etapa 2, o Assistente de Research Financeiro ganhou um classificador de prejuízo treinado no painel aberto da CVM (ROC-AUC 0,88 em walk-forward), dois agentes CrewAI ligados ao DuckDB, ao ChromaDB e ao modelo, traces no Langfuse e uma suíte DeepEval sobre as 45 perguntas do golden dataset. O achado mais útil do DeepEval foi negativo: ele concordou com a auditoria humana em só 4 de 10 casos.

---

# 📊 Dataset de ML

O dataset é o painel de demonstrações contábeis das companhias abertas brasileiras, dos dados abertos da CVM: 741 companhias, do 1T2011 ao 4T2025. É o mesmo tipo de dado que o assistente consulta, então não precisou de analogia.

| Item | Valor |
| --- | --- |
| Nome | Painel ITR/DFP de companhias abertas |
| Fonte | [Portal de Dados Abertos da CVM](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC), formulários ITR (trimestral) e DFP (anual) |
| Registros | 21.903 pares companhia × trimestre (21.119 no alvo do produto) |
| Variável-alvo | Prejuízo líquido consolidado em T+1; no produto, em T+1 **e** T+2 |
| Positivos | 33,3% (T+1) e 22,3% (T+1 e T+2) |
| Features | 15, calculadas até T: ROE, ROA, alavancagem, porte, histórico de prejuízos e variações |

**Ligação com o domínio.** O assistente ajuda um analista a ler releases de cinco bancos e a conferi-los contra a CVM. O modelo acrescenta uma triagem do mercado inteiro. Para os cinco bancos ele informa pouco (um prejuízo em 173 trimestres), e por isso o chat o usa de forma agregada.

---

# 📈 Métricas do modelo

A métrica prioritária é o recall, com limiar escolhido por F2 na validação. Numa triagem, deixar passar uma companhia que vai ter prejuízo custa mais do que um alarme falso, que o analista descarta lendo o balanço. A divisão é temporal: treino até 2T2025, limiar na validação (3T2025) e teste no 4T2025 (413 companhias, 32% com prejuízo). Os modelos do scikit-learn foram comparados com baselines construídos antes deles.

| Modelo (teste 4T2025, alvo T+1) | Limiar | Accuracy | Precision | Recall | F1 | ROC-AUC |
| --- | --- | --- | --- | --- | --- | --- |
| Classe majoritária | — | 0,680 | 0,000 | 0,000 | 0,000 | — |
| Persistência (prejuízo em T prevê T+1) | — | 0,777 | 0,647 | 0,667 | 0,657 | 0,748 |
| Regressão logística | 0,131 (F2) | 0,758 | 0,573 | 0,955 | 0,716 | 0,928 |
| Gradient boosting | 0,049 (F2) | 0,584 | 0,434 | 0,992 | 0,604 | 0,925 |
| Gradient boosting | 0,500 | 0,864 | 0,828 | 0,727 | 0,774 | 0,925 |

- **Accuracy engana:** dizer "lucro" para todas dá 0,680 sem achar nenhum prejuízo.
- **No limiar F2, o boosting acha 131 dos 132 prejuízos**, com 171 alarmes falsos. É a troca que o F2 escolhe de propósito.
- **ROC-AUC é o que o chat usa**, porque ele ordena companhias. O 0,925 é de um só trimestre; a média de 47 trimestres em walk-forward é 0,865, contra 0,846 do melhor baseline trivial (taxa de prejuízos nos últimos quatro trimestres).
- **Ressalva para o gerente:** dentro de cada companhia, o AUC cai para 0,663. O modelo separa quais companhias vivem em prejuízo, não o trimestre em que uma lucrativa vira.

O produto usa o alvo de dois trimestres seguidos, que tira o ruído do prejuízo isolado: ROC-AUC 0,879 em walk-forward e, nos 10% mais bem ranqueados, 3,4 vezes a taxa-base de prejuízo. Boosting e logística empatam; o boosting ficou porque trata dado ausente sem imputação.

---

# 🤖 Agentes implementados

São dois agentes CrewAI no mesmo chat, isolados por contexto: o Auditor recebe só a afirmação e as citações do Investigador, nunca o raciocínio dele.

| Agente | Papel | Ferramentas |
| --- | --- | --- |
| Investigador | Descobre em que camada a companhia existe, busca o dado e responde com citação de fonte | `verificar_cobertura` (CVM + corpus), `buscar_trechos` (ChromaDB), `consultar_cvm` e `calcular_indicadores` (DuckDB), `consultar_modelo_prejuizo` (modelo de ML) |
| Auditor | Reexecuta as consultas e devolve confirma, contesta ou não reproduz | As mesmas cinco, com caixa e teto de chamadas próprios |

Entre os dois, o código confere que toda citação veio de uma ferramenta e que todo valor em reais está na evidência, sob a mesma métrica. O que falha vira recusa registrada antes de gastar a chamada do Auditor.

**Como o modelo entra no chat**, sem previsão sobre companhia nomeada, que a Resolução CVM 20/2021 regula. A pergunta prospectiva vai para uma rota que entrega o histórico e o panorama agregado. No modo Agentes, `consultar_modelo_prejuizo` recebe um valor de ativo e devolve a faixa de porte e a taxa histórica dela.

Exemplo de tarefa composta: "qual foi o lucro do Banco Inter no 3T2025 e em que faixa de porte ele se encaixa no modelo?". O Investigador verificou a cobertura, consultou lucro e ativo no DuckDB e passou o ativo (R$ 91,8 bi) ao modelo. Respondeu com a faixa R$ 10–100 bi e a taxa histórica de 21,8%, dita como taxa da faixa e não como chance do Inter. O Auditor confirmou.

## Orquestração

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

A pergunta só chega ao Investigador depois dos guardrails, e a resposta dele só chega ao Auditor depois da verificação em código. O Auditor nunca vê o raciocínio do Investigador, só o que o filtro deixa passar.

---

# 🔭 Observabilidade

Cada pergunta do chat vira um trace no Langfuse, com um span por etapa (guardrails, recuperação no ChromaDB, geração com tokens e custo) e, no modo Agentes, um span por agente e por ferramenta. Em 19/10 gerei 12 traces reais pelo chat e conferi pela API que o custo registrado no servidor bate com o do app.

![Lista de traces no Langfuse, com latência, tokens e custo](img/langfuse_traces.png)

| Trace | Modo | Latência (s) | Tokens | Custo (US$) |
| --- | --- | --- | --- | --- |
| DEV003 | pergunta livre (RAG) | 13,0 | 3.814 | 0,0014 |
| DEV004 | pergunta livre (RAG) | 3,9 | 3.782 | 0,0016 |
| DEV008 | pergunta livre (RAG) | 8,1 | 4.717 | 0,0023 |
| Inter: painel + modelo | agentes | 34,0 | 25.244 | 0,0131 |
| Itaú: release + painel | agentes | 49,5 | 44.848 | 0,0238 |
| Modelo: panorama e AUC | agentes | 13,2 | 13.067 | 0,0055 |

Os traces mostraram onde vai o tempo: na DEV003, o LLM levou 1,2 s, e a recuperação com a carga do pipeline, 11,7 s. Uma pergunta aos agentes custa de 2 a 17 vezes uma pergunta livre. O texto da pergunta e da resposta só entra no trace com o anonimizador de dados pessoais (Presidio) ligado.

---

# 🧪 Testes: golden dataset e DeepEval

O golden dataset tem 45 perguntas congeladas em 29/07 (mais 10 de desenvolvimento), com resposta e página-fonte conferidas à mão. São 15 factuais, 10 comparativas, 10 qualitativas e 10 adversariais: banco fora do corpus, período ausente, métrica não divulgada, premissa falsa e conhecimento geral.

O DeepEval mediu faithfulness e answer relevancy nas respostas já gravadas das 45. O juiz é de outra família que o gerador (DeepSeek V4 Flash julgando o Gemini 3.5 Flash-Lite), para que nenhum modelo avalie a própria resposta. Foram 196 chamadas, por US$ 0,40.

| Desfecho | Perguntas | Faithfulness (média) | Faithfulness = 1 | Answer relevancy (média) |
| --- | --- | --- | --- | --- |
| Resposta publicada | 10 | 0,947 | 8 | 1,000 |
| Rascunho descartado pela guarda de evidência | 18 | 0,821 | 9 | 0,988 |
| Recusa do próprio modelo | 17 | não pontuada | — | não pontuada |

Fixei antes de rodar que afirmação sem sustentação conta como infiel. O faithfulness padrão só penaliza contradição, o juiz não achou nenhuma em 196 veredictos, e o padrão daria 1,0 às 28 respostas. Recusas não são pontuadas, porque não afirmam nada.

Contra a auditoria humana, feita às cegas antes de existir qualquer juiz, o DeepEval concordou em **4 de 10** itens. O juiz próprio do projeto concorda em 8 de 10 nos mesmos itens. Um critério de período em G-Eval, fixado antes de rodar, pegou a coluna errada que o faithfulness aprovava: 5 de 10.

---

# 🔧 Pontos fracos e ajustes propostos

O ponto fraco mais caro era a guarda de evidência descartar resposta boa. Todos os itens foram tratados e medidos; o que continua aberto está na última coluna.

| Problema | Evidência | Ajuste |
| --- | --- | --- |
| Agente trocou o rótulo de um número | Chamou de "margem financeira" os R$ 17,2 bi que, no release do Itaú, eram "despesas não decorrentes de juros" | **Feito:** o código exige o número sob a mesma métrica. Reexecutei 201 respostas gravadas: nenhuma das 16 sabidamente certas foi rejeitada |
| Auditor confirmou sem reconsultar | Confirmou a faixa do modelo consultando só o DuckDB | **Feito:** "confirma" exige reconsultar cada fonte citada |
| Guarda de evidência descarta resposta boa | 9 de 18 rascunhos descartados são fiéis; a auditoria humana achou 5 descartes indevidos em 15 | **Feito:** não era arredondamento; o release imprime "R$ 6,1 bi" num infográfico que a guarda lia linha a linha. Reaplicada às 45, publica 14 em vez de 10, nenhuma errada. Segue aberta a frase com várias métricas |
| Faithfulness não enxerga período | Deu 1,0 a R$ 12.144 milhões, coluna do 4T25, numa pergunta sobre o 1T26 | **Feito:** o G-Eval de período deu 0,4 a esse caso. Não vê erro de segmento |
| Latência | 11,7 de 13 s em recuperação e carga do pipeline; os agentes levam até 50 s | **Feito:** índice carregado na subida do app e cada ferramenta na tela. Os 50 s dos agentes são chamadas ao LLM e continuam |
| Modelo ordena companhias, não o momento | AUC dentro da companhia de 0,663 | **Medido:** entre as hoje lucrativas, vence o trivial (0,831 contra 0,787), mas dentro da companhia empata (0,624 contra 0,613). É triagem de quais companhias, não de quando |
