# Destilação de um anotador LLM para priorizar mudanças entre releases de resultados de bancos

**Data:** 2026-10-07. **Tipo:** relatório de experimento.
**Código e dados:** este repositório. Cada número tem a origem indicada.

## Resumo

Um analista que acompanha um banco precisa descobrir, a cada trimestre, o que
mudou no novo release de resultados em relação ao anterior. Um release tem de
cerca de 20 a 400 páginas; a comparação automática entre dois releases consecutivos
gera de 95 a 4.090 mudanças por par, e quase todas são rotina. O problema é
**ordenar essas mudanças pela prioridade de leitura**.

Usamos um LLM (Claude) como anotador. Ele leu os dois documentos inteiros e
deu nota de prioridade (0, 1 ou 2) a 7.612 mudanças de 64 pares de releases
de oito bancos brasileiros. Com esses rótulos treinamos um modelo leve de
*gradient boosting* sobre 38 atributos baratos. O objetivo é destilar o
julgamento do LLM num ordenador que roda em milissegundos, sem chamada a
modelo de linguagem.

Num teste novo de 16 pares, fixado antes de qualquer rótulo de teste, o modelo
treinado ordena as mudanças melhor que as alternativas, segundo o rótulo do
LLM:
- nDCG@10 de **0,583**, contra 0,365 de um ordenador por regras e 0,326 de
  similaridade de embeddings sem treino;
- diferença para as regras com IC95% de **[+0,14; +0,30]**;
- vence nos 8 bancos.

A validade do rótulo do LLM diante de um analista humano foi medida e é
**moderada**: α de Krippendorff entre 0,65 e 0,67 em três conferências cegas,
logo abaixo da convenção de 0,67. O resultado mostra que **o julgamento do LLM
pode ser destilado**. Não mostra que o modelo prioriza como um analista.

## 1. Problema e unidade de análise

- **Par:** dois releases consecutivos do mesmo banco. Os testes usam sempre a
  transição do 4º trimestre para o 1º do ano seguinte, a de maior mudança de
  formato, porque o release do 4º trimestre é anual. O treino inclui também 8
  pares do 2º para o 3º trimestre.
- **Evento:** uma mudança atômica entre os dois documentos. Pode ser uma
  sentença alterada, acrescentada ou removida, pareada por similaridade
  (`src/redline.py`).
- **Tarefa:** dado o conjunto de eventos de um par, ordená-los de forma que o
  que um analista precisa ler fique no topo.

## 2. Dados

| Item | Valor |
|---|---|
| Bancos | ABC Brasil, Banestes, Banco do Brasil, BMG, Bradesco, BTG Pactual, Itaú Unibanco, Santander Brasil |
| Fonte | releases públicos (RAD da CVM e sites de RI), texto extraído por Mistral OCR |
| Pares | 64, em três lotes: 16, 14 e 34 |
| Eventos | 49.168 |
| Itens rotulados pelo LLM | 7.612; 7.600 julgáveis |
| Custo de OCR do material novo | cerca de US$ 13,50 (6.737 páginas) |

**Universo só de texto.** No material novo, o OCR entregou as tabelas fora do
texto, e o extrator não as leu. O estudo mede mudanças de **texto**
(`resultados/achado_tabelas_ocr_cand02p_2026-10-07.md`).

## 3. Método

### 3.1 Anotação pelo LLM

**Rubrica de três níveis** (`artefatos/cand02p_v3/rubrica.md`):
- **0, rotina:** período que rolou, paráfrase, número atualizado sem mudar a
  leitura, ruído de extração;
- **1, conferir:** muda fato, número, definição, causa ou risco;
- **2, leitura obrigatória:** muda guidance, tendência ou sinal, perímetro,
  política contábil, capital ou liquidez, risco de crédito.

**Cada par foi lido por um agente Claude independente, em contexto limpo.** O
agente tinha acesso aos dois documentos inteiros, e a decisão de usar os
documentos inteiros veio de uma auditoria anterior do projeto, em que a
anotação com documento inteiro se igualou à humana. O agente não sabia qual
sistema tinha proposto cada item.

**O acesso dos agentes foi auditado** a partir das chamadas de ferramenta
(`scripts/cand02p_qc.py`):
- uma leitura que abriu rótulos de outros pares foi descartada e refeita;
- a releitura cega do próprio leitor deu α de 0,81 e 0,74 em dois pares.

### 3.2 Avaliação por pool

Rotular todos os eventos é inviável: há até 4.090 por par. Rotulou-se um
**pool** de até 120 itens por par, formado pelos primeiros itens de cada
ordenador e por uma parte aleatória. O pool foi montado às cegas: o anotador
não sabe a origem de cada item. A métrica é o **nDCG@10 macro** sobre os
pares, com ganho 0, 1 e 3 para as notas 0, 1 e 2.

### 3.3 Ordenadores comparados

| Braço | O que é |
|---|---|
| **B0** | massa de texto alterado (quanto maior a mudança, mais alto) |
| **B1** | regras determinísticas: números, sinais, palavras de guidance, capital, crédito |
| **C** | similaridade do evento com 10 âncoras semânticas, por embeddings (bge-m3), sem treino |
| **M** | *gradient boosting* (`HistGradientBoostingRegressor`) sobre 38 atributos: operação, sinais do B1, categorias lexicais, magnitude numérica, tamanho e posição, e as similaridades do C |

Os hiperparâmetros foram fixados antes, sem busca: 200 iterações, taxa 0,05,
15 folhas, mínimo de 20 por folha, L2 = 1,0 e semente 20260928.

### 3.4 Desenho experimental

**Três rodadas, cada uma com protocolo pré-registrado** e congelado em commit
antes de qualquer rótulo do respectivo teste:
- o modelo foi congelado antes de os rótulos de teste existirem;
- treino e teste nunca compartilham documento.

**Regra de decisão fixada antes.** O modelo precisa, ao mesmo tempo:
- superar o B1 em Δ nDCG@10 ≥ +0,10 e Δ nDCG@20 ≥ +0,05;
- vencer em ≥ 7 de 8 emissores;
- não trazer menos itens críticos no top-20.

## 4. Resultados

### 4.1 Teste principal (v3: 16 pares, 2021→2022 e 2022→2023)

Treino em 48 pares. Fonte: `artefatos/cand02p_v3/resultado_teste.json`.

| Braço | nDCG@10 | nDCG@20 | Críticos no top-20 |
|---|---:|---:|---:|
| B0 | 0,133 | 0,171 | 14 |
| B1 | 0,365 | 0,389 | 17 |
| C | 0,326 | 0,332 | 18 |
| **M** | **0,583** | **0,592** | **29** |

- Δ nDCG@10 M − B1 = **+0,219**, com IC95% por bootstrap de emissores de
  **[+0,139; +0,301]**.
- O M vence o B1 nos **8 de 8 emissores** e em 14 de 16 pares.
- O ganho é maior nos documentos longos (Banco do Brasil, Bradesco, Itaú),
  onde as regras ficam entre 0,14 e 0,22.

### 4.2 Evolução com o volume de treino

| Rodada | Pares de treino | Teste | M × B1 (nDCG@10) | Veredito |
|---|---:|---|---|---|
| v1 | 8 | 8 pares, 2025→2026 | 0,390 × 0,363; vence em 3 de 8 | inviável |
| v2 | 22 | 8 pares, 2024→2025 | 0,508 × 0,342; vence em 7 de 8 | promissor |
| v3 | 48 | 16 pares, 2021→2023 | 0,583 × 0,365; vence em 8 de 8 emissores | promissor |

**Ressalva:** o teste do v1 incluía tabelas e os do v2 e do v3 não. Parte da
melhora do v1 para o v2 pode vir dessa mudança de universo, e não do volume
de treino.

### 4.3 O que o modelo aprendeu

O teste: embaralhar cada grupo de atributos dentro do par, no teste do v3,
com o modelo congelado, e medir a queda do nDCG@10. Fonte:
`artefatos/cand02p_final/importancia.json`.

| Grupo de atributos | Queda do nDCG@10 |
|---|---:|
| similaridade semântica (C) | −0,310 |
| operação e tipo do evento | −0,207 |
| tamanho e posição no documento | −0,153 |
| regras do B1 | −0,076 |
| magnitude da mudança numérica | −0,042 |
| categorias lexicais | −0,011 |

O C sozinho perde para as regras (0,326 × 0,365). Mesmo assim, é o atributo
mais importante dentro do M. O ganho vem da **combinação** entre o
significado do trecho e a estrutura do evento, não de um sinal isolado.

## 5. Validação do rótulo do LLM contra um analista humano

Um analista rotulou às cegas amostras de itens sem ver a nota do LLM.

| Conferência | Itens | α (humano × LLM) | Observação |
|---|---:|---:|---|
| v3, rubrica original | 60, ao acaso | 0,652 | acordo exato 77% |
| calibração, rubrica v2 | 60, ao acaso | 0,666 | a rubrica v1, nos mesmos itens: 0,498 |
| final, rubrica v2 | 90, estratificada por nota | 0,647 | 83% das notas 2 do LLM reconhecidas como relevantes |

- **Regra fixada antes:** α ≥ 0,67. As três ficaram logo abaixo. Pela regra,
  a validade humana do rótulo **não foi demonstrada**.
- **Onde o LLM e o analista discordam:** na nota intermediária e em alarmes
  falsos (17% dos itens de nota 2 do LLM o humano deu 0). Em nenhum item que
  o humano considerou obrigatório o LLM deu 0.
- **Gold adjudicado de 60 itens, só como descrição:** o M continua o melhor
  ordenador, com AUC de 0,786 para separar a nota 2, contra 0,656 do B1. Com
  60 itens, o IC95% da diferença é [−0,10; +0,35].
- **Pergunta em aberto:** quanto dois analistas humanos concordam entre si
  nesta tarefa. Sem esse teto, não se sabe se α ≈ 0,65 é pouco ou já é nível
  humano.

## 6. Limitações

- **O alvo é o julgamento do LLM.** A conclusão é sobre destilação, não sobre
  a prioridade de um analista.
- **Só texto.** As tabelas ficaram fora, e é nelas que as regras numéricas
  seriam mais fortes.
- **Um tipo de transição.** Os testes são todos do 4º trimestre para o 1º,
  em oito bancos brasileiros.
- **Um analista humano.** Não há referência entre humanos.
- **Avaliação por pool:** os eventos fora do pool contam como irrelevantes.
- **Desenhista não cego** entre rodadas. Mitigado por mudar só dados, tamanho
  do teste e unidade de vitória, e por pré-registro em cada rodada.

## 7. Modelo final

`scripts/cand02p_modelo_final.py treinar` treina o mesmo modelo nos 64 pares,
com 7.600 observações. É o modelo de uso. Não tem métrica própria: o
desempenho de referência é o do teste do v3, medido antes. O pickle fica fora
do repositório, e o SHA-256 dele está em
`artefatos/cand02p_final/modelo/congelado.json`.

## 8. Reprodução

```
python -m scripts.cand02p_piloto --piloto v3 avaliar --papel teste   # tabela 4.1
python -m scripts.cand02p_modelo_final importancia                    # tabela 4.3
python -m scripts.cand02p_modelo_final treinar                        # modelo final (congela uma vez)
python -m scripts.cand02p_gold                                        # gold e AUC da seção 5
```

Os protocolos e relatórios de cada rodada estão em `resultados/`, nos arquivos
`protocolo_cand02p_*`, `piloto_cand02p_*`,
`calibracao_rubrica_v2_cand02p_*` e `conferencia_final_rubrica_v2_cand02p_*`.

## 9. Conclusão

Um modelo de *gradient boosting* com 38 atributos baratos aprende a ordenar
mudanças entre releases bancários como o anotador LLM ordena. Ele supera
regras determinísticas e similaridade de embeddings, com margem estável num
teste novo e pré-registrado. Isso permite trocar uma leitura de LLM de
centenas de milhares de tokens por par por uma inferência local.

A distância entre o julgamento do LLM e o de um analista foi medida e é
moderada. Fechá-la exige referência entre humanos, não mais rótulos de LLM.
