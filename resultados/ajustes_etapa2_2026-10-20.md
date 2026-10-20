# Ajustes propostos no relatório da Etapa 2 — 2026-10-20

O relatório técnico (`docs/03_relatorio_tecnico_etapa2.md`) terminava com
quatro pontos fracos sem correção: a guarda de evidência descartando resposta
boa, o faithfulness cego a período, a latência e o modelo que ordena
companhias, não o momento. Este relatório diz o que foi feito em cada um, como
foi medido e o que continua aberto.

Custo total: **US$ 0,099**, todo no critério de período (38 chamadas ao juiz).
O resto é reaplicação sobre respostas gravadas e treino em CPU, sem LLM.

## 1. A guarda de evidência (RN02) descartava resposta boa

### O diagnóstico mudou a correção

A proposta era aceitar arredondamento e diferença entre números citados. A
causa medida era outra. `scripts/reaplicar_guarda_rn02.py` reaplica as guardas
às respostas gravadas da rodada congelada `c3a03ff7` (4 estratégias × 45),
usando a mesma função que a geração chama (`aplicar_guardas_pos_llm`, extraída
de `gerar_resposta` para isso). Com o código anterior, ela reproduz os 180
desfechos gravados, sem divergência.

Lendo cláusula por cláusula os 17 descartes por número da estratégia
semântica:

| Causa | Casos | Correção |
|---|---|---|
| Infográfico de destaques lido linha a linha: valor em título markdown (`## R$ 6,1 bi`), valor solto sob o rótulo, negrito no meio da moeda (`R$ **3,8** bilhões`) | TSTF001, TSTF007, TSTF008, TSTF013, TSTC001, TSTC004 | Leitura de painel em `fatos_numericos_do_chunk` |
| Coluna mesclada com palavra (`\| Desempenho \| Retorno ... \| 24,8% \|`) | TSTC003, TSTC008 | Rótulo é a célula que nomeia métrica |
| Identificador do documento copiado na frase (`no documento bb_release_2T2025`) | TSTF013, TSTQ006 | Removido como marcador de citação |
| `(+14,8%)` lido como negativo contábil | TSTQ010 | Sinal explícito vence o parêntese |
| Arredondamento de verdade (`ou R$ 3,7 bilhões` ao lado de 3.659) | TSTF010 | **Não corrigido**, ver abaixo |
| Diferença de taxas escrita em `%` (`= 1,8%`) | TSTC008 | **Não corrigido**, ver abaixo |
| Cláusula com várias métricas (enumeração qualitativa) | TSTQ005, TSTQ010 | Aberto |
| Checagem de conteúdo qualitativo | TSTQ001, TSTQ002, TSTQ006, TSTQ008, TSTC006 | Aberto |

Três dos quatro casos de "arredondamento" não eram arredondamento: o release
imprime `R$ 6,1 bi` e `R$ 1.034 bi` no infográfico, e a guarda não lia aquelas
linhas.

### Duas propostas não adotadas, com o motivo

- **Arredondamento.** Sobrou um caso (TSTF010), e ele contraria a regra 5 do
  prompt de geração: "não arredonde além do que está escrito". Afrouxar a guarda
  para um caso que viola o contrato do próprio prompt seria trocar a regra por
  conveniência.
- **Diferença em `%`.** `TestDeltaPercentualSegueExigido` trava a recusa desde
  setembro: diferença entre taxas é em pontos percentuais, e o gabarito do
  TSTC008 diz `1,8 p.p.`. Diferença escrita em p.p. num `Cálculo:` explícito
  já é aceita.

### Duas regressões que a reaplicação pegou antes de qualquer commit

- A primeira versão da leitura de painel publicava, na estratégia híbrida, "o
  Bradesco apresentou ROAE de 21,6%". Os 21,6% são do Grupo Segurador, e o
  consolidado é 15,8%: o infográfico emenda os dois painéis sem quebra. A regra
  agora falha fechada: depois de uma linha curta que não nomeia métrica nem é
  cabeçalho genérico ("Grupo Segurador", "Pessoas Físicas"), nenhum rótulo é
  herdado até o painel acabar.
- A legenda `R$ milhões` foi classificada como cabeçalho de segmento e sumiu
  antes de registrar a escala da tabela, o que derrubava TSTF006, TSTF007,
  TSTF010 e TSTF012 em outras estratégias. Legenda saiu da classificação.

### Resultado na rodada congelada (reaplicação, custo zero)

| Estratégia | Publicadas | Exatidão automática | Passaram a publicar | Destas, o gabarito reprova | Deixaram de publicar |
|---|---:|---:|---|---:|---:|
| semântica | 10 → **14** | 16 → **20** | TSTF001, TSTF007, TSTF008, TSTF013 | 0 | 0 |
| híbrida | 8 → 10 | 16 → 18 | TSTF001, TSTF013 | 0 | 0 |
| keyword | 13 → 14 | 16 → 17 | TSTF001 | 0 | 0 |
| fatos | 15 → 15 | 20 → 20 | — | 0 | 0 |

Contra as duas réguas externas:

- **DeepEval (semântica):** dos 9 rascunhos descartados que o faithfulness
  julgou fiéis, 4 passaram a publicar, todos certos pelo gabarito. Dos 5
  restantes:
  - 3 estão errados pelo gabarito (TSTC001, TSTC003 e TSTC006): fiel aos
    trechos não é estar certo;
  - TSTF010 é o arredondamento;
  - TSTQ006 cai na checagem qualitativa.

  Nenhum rascunho com faithfulness abaixo de 1 passou a publicar.
- **Auditoria humana (`a0bea525`):** dos 5 descartes indevidos, TSTF012 e
  TSTQ003 já passavam antes de hoje (correções de setembro). Os outros 3 seguem
  descartados: TSTC008 pelo `%`, e TSTQ005 e TSTQ010 pela enumeração. Os dois
  descartes que o humano julgou corretos (TSTF006, a coluna errada, e TSTQ001)
  continuam descartados.

### Efeitos colaterais medidos

- **E4 (`fatos`).** Ranqueia chunk com o mesmo parser. Nas 25 factuais e
  comparativas, a ordem muda em 12 perguntas e os agregados não mudam:
  recall@5 de 12/15 factuais e 10/10 comparativas, e valor no top-5 em 9/15
  (`scripts/medir_recuperacao_e4.py`, antes e depois).
- **Guarda de rótulo dos agentes.** Usa o mesmo parser. Sobre as 201 respostas
  gravadas, a contagem é a mesma de antes: 2 acusações (AGTP002, pendentes de
  leitura humana) e nenhuma das 16 sabidamente certas acusada.

## 2. O faithfulness não enxerga período nem coluna

Métrica nova: `periodo_geval`, um G-Eval com seis passos escritos em
`src/avaliacao_deepeval.py::PASSOS_PERIODO` e limiar 0,5 (o padrão do G-Eval),
os dois fixados antes da rodada. Com os passos prontos e um juiz sem logprobs,
o G-Eval faz uma chamada por caso. Juiz e preços são os de 20/10 (DeepSeek V4
Flash).

**Concordância com a auditoria humana (10 itens, US$ 0,027):**

| Regra de "fundamentada" | Concorda |
|---|---:|
| faithfulness = 1,0 (pré-registrada em 20/10) | 4/10 |
| **faithfulness = 1,0 e período ≥ 0,5 (pré-registrada hoje)** | **5/10** |
| só período ≥ 0,5 (leitura secundária) | 9/10 |

- O critério pega a armadilha que motivou a métrica: TSTF006, o `12.144` da
  coluna do 4T25, sai com 0,4 e é o único abaixo do limiar.
- O 9/10 do período sozinho não é ganho de instrumento. O critério aprova 9
  dos 10 rascunhos, e o humano julgou a maioria dos descartes indevida; é o
  mesmo efeito que deu 8/10 ao escore padrão da biblioteca em 20/10.

**Nas 45 congeladas (28 pontuados, US$ 0,072):** os 28 ficam no limiar ou
acima.

- TSTC003, que está errado, sai com 0,5, exatamente no limiar.
- TSTC004 sai com 1,0. É o ROAE do Grupo Segurador: o erro é de segmento, não
  de período, e o critério não o vê.

**Leitura.** É um detector estreito da armadilha de coluna, útil como alarme
ao lado do faithfulness. Não vira métrica de groundedness; a régua continua
sendo a auditoria humana. Com n = 10, a diferença entre 4/10 e 5/10 não é
resolvível.

## 3. Latência

Medido nos traces de 19/10. A primeira pergunta do processo levou 13 s:

- 4,4 s para carregar o índice;
- 7,3 s na primeira recuperação, com o Ollama carregando o modelo de
  embeddings;
- 1,2 s de LLM.

Com o Presidio ligado, o guardrail frio somava 6,7 s. A quente, a mesma
recuperação leva 0,33 s. Feito:

- **Aquecimento na subida** (`aquecer_caminho_ao_vivo`): só com pergunta
  livre habilitada, sem LLM e sem custo. Falha nele não derruba a página.
  Medido com `AppTest`: 4,2 s na primeira carga da página, uma vez por
  processo, e 0,1 s nas seguintes.
- **Cache do índice sem `ttl=300`.** O índice expirava depois de 5 minutos
  sem pergunta. A chave agora é a identidade de OCR mais a assinatura dos
  arquivos do índice: reconstruir o índice invalida o cache, e a RNF09 roda de
  novo na carga. O teste pegou um defeito da primeira versão: o Streamlit deixa
  fora da chave o parâmetro cujo nome começa com `_`.
- **Progresso no modo Agentes.** Cada ferramenta aparece na tela enquanto o
  agente trabalha (`FerramentasDoAgente(ao_chamar=...)`), com papel,
  ferramenta e desfecho, sem argumentos. Um observador que falha não chega ao
  agente.

**Não feito:**

- Os 13–50 s dos agentes são chamadas de LLM; o progresso os torna visíveis,
  não mais curtos.
- O Ollama descarrega o modelo de embeddings após 5 minutos ocioso, e isso é
  configuração do servidor (`OLLAMA_KEEP_ALIVE`), não do app.
- A primeira pergunta paga depois do aquecimento não foi medida ao vivo.

## 4. O modelo ordena companhias, não o momento

O recorte das companhias hoje lucrativas já tinha AUC agregado (0,8315,
`robustez.json`). Faltava o que responde à pergunta: o AUC dentro da
companhia, no recorte, ao lado dos baselines triviais nas mesmas linhas.
`scripts/medir_virada_lucrativas.py` usa o alvo do produto (prejuízo em T+1 e
T+2) e walk-forward com purga.

**Regra de leitura, fixada antes de rodar.** O modelo "antecipa o momento" só
se o IC95% do AUC intra-companhia, com bootstrap por companhia, ficar inteiro
acima de 0,5 e acima do AUC intra-companhia de `taxa_prejuizos_4t`.

Recorte: 11.337 observações, 917 eventos, taxa-base 8,1%.

| | Modelo | `taxa_prejuizos_4t` | Identidade implementável |
|---|---:|---:|---:|
| AUC agregado | **0,831** | 0,787 | 0,739 |
| AUC intra-companhia (IC95%) | 0,624 (0,596–0,651) | 0,613 (0,587–0,638) | 0,412 |

- **Entre companhias**, o modelo vence o melhor trivial com folga no recorte:
  +0,050 de AUC por fold (IC 0,036–0,064), vencendo em 39 de 46 folds
  (p = 3e-09). No painel inteiro a vantagem é +0,019.
- **Dentro da companhia**, empata com o trivial. Veredito pela regra: ordena
  companhias, não o momento, também no recorte.
- **Sem prejuízo no último ano** (7.793 observações, 212 eventos), onde o
  trivial é constante: AUC agregado 0,754 e intra-companhia 0,612 (0,548–0,674).

Leitura para o produto: o valor do modelo é dizer quais companhias hoje
lucrativas merecem leitura primeiro. Não é dizer em que trimestre uma delas
vai virar.

## Reprodução

```bash
python -m scripts.reaplicar_guarda_rn02 \
    --saida artefatos/resultados_avaliacao/reaplicacao_rn02_c3a03ff7.json
python -m scripts.reaplicar_guarda_rn02 --fingerprint a0bea525 --estrategias semantica \
    --saida artefatos/resultados_avaliacao/reaplicacao_rn02_a0bea525.json
python -m scripts.medir_recuperacao_e4          # o docstring mostra o antes/depois
python -m scripts.medir_virada_lucrativas --painel artefatos/cvm_treino.duckdb

# juiz e preços de resultados/deepeval_2026-10-20.md
python -m scripts.avaliar_deepeval --metricas periodo_geval --teto-usd 0.20 --permitir-api-paga
python -m scripts.avaliar_deepeval --metricas periodo_geval --teto-usd 0.20 --permitir-api-paga \
    --concordancia artefatos/resultados_avaliacao/auditoria_groundedness_a0bea525.json \
    --fidelidade-de artefatos/resultados_avaliacao/deepeval_a0bea525_concordancia.json
```

Artefatos:
- `artefatos/resultados_avaliacao/reaplicacao_rn02_{c3a03ff7,a0bea525}.json`
- `artefatos/resultados_avaliacao/deepeval_{a0bea525_concordancia,c3a03ff7_semantica}_periodo_geval.json`
- `artefatos/modelo/virada_lucrativas.json`
