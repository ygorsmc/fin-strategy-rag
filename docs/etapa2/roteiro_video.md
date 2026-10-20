# Roteiro do vídeo — Etapa 2 (cerca de 4 min 30 s)

O que está entre aspas é fala; o que está em `código` é o que se cola na tela.
A orientação pede cinco coisas no vídeo: o modelo de ML funcionando no chat,
os agentes, o Langfuse, o DeepEval e as suas observações sobre o processo. A
demonstração ocupa a maior parte do tempo porque é ela que a rubrica confere.

## Antes de gravar

- **App em modo local.** No `.env`, defina `HABILITAR_PERGUNTAS_LIVRES=true` e
  `PREVISAO_POR_EMISSOR_HABILITADA=true`, com as chaves do Gemini e do
  Langfuse. O escore por companhia precisa existir:
  `python -m scripts.gerar_panorama_modelo --painel artefatos/cvm_treino.duckdb --com-escores`.
- **Abas abertas:** o app (`streamlit run app_streamlit.py`), a lista de
  traces do Langfuse e um terminal na raiz do repositório.
- **Ensaie as duas perguntas pagas uma vez.** O LLM não responde igual em
  toda execução: se a resposta do ensaio sair diferente da descrita abaixo,
  ajuste a fala ao que aparecer na tela. Cada passada custa cerca de US$ 0,05.
- **Cole as perguntas, não digite.** O roteiro não tem folga para digitar.

| Bloco | Tempo | Acumulado |
| --- | --- | --- |
| Abertura | 20 s | 0:20 |
| Modelo de ML no chat | 50 s | 1:10 |
| Agentes | 1 min 20 s | 2:30 |
| Langfuse | 45 s | 3:15 |
| DeepEval | 35 s | 3:50 |
| Suas observações | 40 s | 4:30 |

---

## 0:00 – 0:20 · Abertura

*(App aberto na tela.)*

> "Na Etapa 1, o assistente respondia sobre os releases de cinco bancos e
> sobre o painel contábil da CVM. Nesta etapa ele ganhou um modelo de ML, dois
> agentes que trabalham em conjunto, observabilidade no Langfuse e testes com
> DeepEval. Vou mostrar cada um funcionando."

## 0:20 – 1:10 · O modelo de ML no chat

*(Modo "Pergunta livre". Cole a pergunta.)*

`O lucro do Banco Inter vai cair no próximo trimestre?`

> "O modelo foi treinado com quinze anos de formulários da CVM, de todas as
> companhias abertas, para prever prejuízo nos dois trimestres seguintes.
>
> Aqui ele está em modo local, que mostra o escore por companhia: um vírgula
> oito por cento para o Inter. E ele coloca ao lado a taxa histórica do porte
> do Inter, vinte e um vírgula oito por cento, para que ninguém leia o escore
> sozinho.
>
> Escolhi o ROC-AUC como métrica principal porque o modelo serve para ordenar
> companhias por risco, e o analista lê a lista de cima para baixo. Na
> validação ao longo de quarenta e sete trimestres, ele marca zero vírgula
> oitenta e oito. Na instância pública, essa mesma pergunta é recusada: prever
> o resultado de uma companhia nomeada é análise de valores mobiliários."

## 1:10 – 2:30 · Os agentes

*(Troque para o modo "Agentes". Cole a pergunta. Os agentes levam de 30 a 45
segundos, e a fala abaixo cobre a espera.)*

`O que o release do Itaú diz sobre a margem financeira gerencial no 3T2025, e quanto o painel da CVM registra de lucro líquido no mesmo trimestre?`

> "Essa pergunta precisa de duas fontes: o release, que está no ChromaDB, e o
> painel da CVM, que está no DuckDB.
>
> Na tela aparece cada ferramenta que os agentes chamam. O primeiro é o
> Investigador: ele descobre em que camada o Itaú existe, busca o trecho do
> release e consulta o painel.
>
> O segundo é o Auditor. Ele não vê o raciocínio do Investigador, só a
> afirmação e as citações, e refaz as consultas por conta própria. Se não
> conseguir reproduzir, a resposta sai marcada.
>
> *(Resposta na tela.)*
>
> Aqui está: a margem financeira gerencial de trinta e um bilhões, citando a
> página seis do release, e o lucro arquivado na CVM. E embaixo, o veredito do
> Auditor.
>
> Na primeira rodada real, essa mesma pergunta voltou com o número errado: o
> agente chamou de margem uma linha de despesas. Hoje o código confere se o
> número aparece na fonte com o mesmo rótulo antes de o Auditor ser chamado."

## 2:30 – 3:15 · Langfuse

*(Aba do Langfuse, lista de traces.)*

> "Cada pergunta do chat vira um trace no Langfuse, com latência, tokens e
> custo. Eu conferi pela API que o custo registrado aqui é o mesmo que o app
> calcula."

*(Abra o trace da pergunta dos agentes.)*

> "Dentro do trace dá para ver cada agente, cada ferramenta e cada chamada ao
> modelo de linguagem. Foi assim que eu descobri que a primeira pergunta do
> dia demorava treze segundos, e quase todo esse tempo era o carregamento do
> índice, não o LLM. Agora o índice carrega quando o app abre."

## 3:15 – 3:50 · DeepEval

*(Terminal.)*

`pytest tests/test_deepeval.py -q`

*(Enquanto roda, abra `resultados/deepeval_2026-10-20.md` na tabela de
concordância.)*

> "O golden dataset tem quarenta e cinco perguntas conferidas à mão. O DeepEval
> mediu faithfulness e answer relevancy nas respostas, com um juiz de outro
> fabricante.
>
> O resultado mais importante foi este: comparado com a minha auditoria feita
> à mão, o DeepEval concordou em só quatro de dez casos. Num deles, ele aprovou
> um número tirado da coluna errada da tabela. Por isso eu uso o DeepEval como
> triagem, e não como a medida final."

## 3:50 – 4:30 · Suas observações

Esta parte a orientação pede nas suas palavras, então aqui ficam só os fatos
para você escolher. Fale de uma coisa que deu certo, uma que deu errado e uma
que aprendeu.

- **Deu certo:** conferir o número em código, e não confiar no modelo. Nas sete
  perguntas medidas, os agentes não trouxeram nenhum número errado; quando
  erraram, foi por explicação incompleta.
- **Deu errado:**
  - A guarda de evidência descartava respostas certas, porque o OCR quebra os
    infográficos do release em linhas soltas.
  - O limiar que eu tinha escolhido para o modelo marcava três de cada quatro
    companhias como risco.
- **Aprendi:**
  - Uma métrica automática precisa ser medida contra uma leitura humana antes
    de virar número oficial.
  - A métrica certa depende do uso: o modelo ordena, então o que importa é o
    ROC-AUC, e não a accuracy.

## 4:30 · Fecho

> "O código, o relatório técnico e os números de cada etapa estão no
> repositório. Obrigado."
