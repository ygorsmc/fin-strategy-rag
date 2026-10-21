# Modo Agentes do chat, com o código atual — 2026-10-20

Primeira rodada real dos agentes do produto depois das duas guardas de 20/10:
o rótulo conferido junto com o número e a reconsulta de cada fonte antes de
confirmar. A rodada de 19/10 foi feita antes delas.

- **Comando:** `python -m scripts.gerar_traces_langfuse --permitir-api-paga
  --capturar-texto --conjunto todos --ids-agentes
  AGTC001,AGTC002,AGTC003,AGTC006,AGTR002,AGTR003,AGTP004`, com
  `ORCAMENTO_TETO_USD=0.60`.
- **O que rodou:** 19 perguntas pelo próprio app (`AppTest`):
  - 9 do chat;
  - as 3 de exemplo do modo Agentes;
  - 7 do `conjunto_padrao/conjunto_agentes.csv`.
- **Modelo:** `gemini-3.5-flash-lite`.
- **Custo:** US$ 0,144 no total, dos quais US$ 0,136 nos agentes.
- **Dados:** `artefatos/observabilidade/traces_2026-10-20T213509Z.json`, com a
  resposta inteira de cada pergunta do modo Agentes.
- **Conferência:** feita pelo assistente de código contra o gabarito do
  conjunto, não por leitura humana independente. Os valores de release dos
  itens AGTC006, AGTR002, AGTR003 e AGTP004 estão marcados no gabarito como
  pendentes de conferência humana.

## As 7 perguntas do conjunto dos agentes

A regra do gabarito é "cobrir todos" os pontos-chave. "Parcial" quer dizer
números certos e algum ponto-chave faltando.

| Id | Veredito | Por quê |
| --- | --- | --- |
| AGTC001 (Inter, só no painel) | Correta | Os dois valores (R$ 417,5 mi consolidado e R$ 394,8 mi controladores), com a base nomeada. Diz que não há release do Inter. |
| AGTC002 (Nubank, em nenhuma camada) | Correta | Recusa, sem número. Diz que não está na CVM nem no corpus. |
| AGTC003 ("BTG", ambíguo) | Correta | Pergunta de desambiguação com as duas razões sociais e os dois CD_CVM, sem valor. Termina antes do Auditor. |
| AGTC006 (Santander, nas duas camadas) | Correta | CVM: R$ 3.281,6 mi consolidado e R$ 3.218,0 mi controladores. Release: R$ 3,788 bi, rotulado como gerencial e citado. |
| AGTR002 (Itaú, recorrente × CVM) | Parcial | Números certos: R$ 11.508 mi recorrente; R$ 11.398 mi e R$ 11.137 mi na CVM. Não responde se são o mesmo número nem diz que a diferença é de definição. |
| AGTR003 (Bradesco, relatório × CVM) | Parcial | Números certos: R$ 6.205 mi recorrente e contábil no release (p. 45); R$ 5.568,0 mi e R$ 5.500,7 mi na CVM. A explicação atribui a diferença a "ajustes gerenciais", mas no próprio release o contábil é igual ao recorrente. Não menciona IFRS × padrão brasileiro. |
| AGTP004 (BB 2025 × faixa projetada) | Parcial | Traz os quatro trimestres de 2025 na CVM, com o 4T marcado como derivado. As somas batem com o gabarito (R$ 16.781,9 mi e R$ 13.698,1 mi), mas o total anual não aparece. Não achou a faixa projetada nos trechos e declarou isso; não fez a comparação pedida. |

**Resultado:**

- 4 corretas, 3 parciais e nenhuma com número errado.
- O Auditor confirmou as 6 que chegaram a ele, inclusive as 3 parciais. Ele
  confere se cada afirmação tem lastro, não se a resposta está completa.

## As 3 perguntas de exemplo do modo Agentes

- **Inter: lucro e faixa de porte.**
  - Lucro de R$ 356,0 mi no 3T2025.
  - Faixa de R$ 10 a 100 bi, com taxa histórica de 21,8%, apresentada como taxa
    da faixa.
  - O Auditor reconsultou o painel e o modelo antes de confirmar. Em 19/10, ele
    tinha confirmado sem consultar o modelo.
- **Itaú: margem financeira gerencial e lucro na CVM.**
  - Margem de R$ 31.382 mi (p. 6), lucro de R$ 11.600 mi consolidado e de
    R$ 11.306 mi dos controladores.
  - Confirmada. Em 19/10, a resposta chamava de margem os R$ 17,2 bi de despesas
    não decorrentes de juros.
- **Modelo: companhias sinalizadas e AUC.**
  - AUC de 0,879 e 25 companhias lucrativas acima do limiar, os dois certos.
  - Mas a resposta soma a isso as 136 já em prejuízo, como se também fossem
    sinalizadas. O panorama as deixa fora da contagem de propósito.

## O que mais a rodada mostrou

- **Chat.**
  - Das 5 perguntas livres (`dev`), 1 foi publicada (DEV005) e 4 foram
    recusadas pela RN02.
  - A DEV003, publicada em 19/10, foi recusada agora: o gerador não é
    determinístico mesmo a temperatura 0.
  - Das 4 recusas, só a do DEV009 estava certa. As do DEV004 e do DEV008
    foram corrigidas na guarda no mesmo dia, e a do DEV003 segue por outro
    motivo (`resultados/recusas_dev_2026-10-20.md`).
- **Langfuse.**
  - 17 dos 19 traces chegaram completos, e o custo no servidor bateu com o do
    app em todos.
  - Nos outros 2 (`agentes_release_e_painel` e AGTP004), uma chamada ao LLM
    aparece sem modelo, sem tokens e sem custo. Não foi investigado.

## O que isto não autoriza

- **Não é a comparação dos três braços da etapa 12.** Aquela roda o braço B do
  experimento, sem a ferramenta do modelo, nas 15 perguntas.
- **É uma execução só, em 7 das 15 perguntas.** A variação entre execuções não
  foi medida.
