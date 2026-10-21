# Assistente de Research Financeiro

Assistente de perguntas e respostas sobre os resultados trimestrais dos cinco
maiores bancos listados do Brasil (Banco do Brasil, Bradesco, BTG Pactual, Itaú
Unibanco e Santander Brasil). Ele cruza duas fontes públicas que costumam viver
separadas: os releases de resultado que cada banco publica em PDF e os
formulários contábeis que as companhias abertas arquivam na CVM.

O problema técnico é localizar um número dentro de um documento longo,
reconciliar o valor gerencial divulgado com o contábil arquivado e impedir que
o modelo de linguagem afirme o que a fonte não sustenta. Por isso o sistema
cita página e documento em toda resposta e prefere recusar a arriscar.

> Projeto educacional da disciplina *AI Factory: Building Intelligent Systems*
> (PUCPR). Não é recomendação de investimento: o sistema recusa esse tipo de
> pedido por regra, com base nas Resoluções CVM 19/2021 e 20/2021.

## Entregas da disciplina

A documentação do projeto é uma página só, [docs/documentacao.html](docs/documentacao.html),
que cresce a cada etapa. Ela é gerada por `scripts/build_docs_html.py` a partir
dos Markdown de `docs/`.

| Etapa | Onde está |
| --- | --- |
| Desafio CBL | [DESAFIO_CBL.md](DESAFIO_CBL.md) e a aba "Desafio CBL" da página |
| Etapa 1: interface, dados e RAG | abas "Visão Geral" e "Arquitetura"; [slides](docs/apresentacao_etapa1.pptx) e [roteiro do vídeo](docs/roteiro_apresentacao_etapa1.md) |
| Etapa 2: modelo de ML, agentes, observabilidade e testes | aba "Etapa 2", com o [relatório técnico](docs/03_relatorio_tecnico_etapa2.md); [roteiro do vídeo](docs/roteiro_apresentacao_etapa2.md) |

## Como o sistema funciona

```text
releases em PDF (20)                    dados abertos da CVM (ITR/DFP)
  │ Mistral OCR, com cache versionado      │
  ▼                                        ▼
chunks de 600 tokens                    painel contábil em DuckDB
  ├─► índice BM25                          │ mapa semântico de contas
  └─► embeddings ─► ChromaDB               │ 4º trimestre derivado e marcado
                       │                   ├─► modelo de prejuízo (offline)
                       │                   │     └─► panorama agregado
                       ▼                   ▼
        ferramentas: verificar_cobertura · buscar_trechos · consultar_cvm
                     calcular_indicadores · consultar_modelo_prejuizo
                       ▲
pergunta ─► guardrails ─► Investigador ─► verificação em código
                                             │ só a afirmação e as citações
                                             ▼
                                          Auditor ─► guardrails ─► resposta

Langfuse: um trace por pergunta, com spans de recuperação, geração,
agentes e ferramentas
```

O chat tem três modos. O de demonstração responde com a rodada já avaliada e
com consultas ao painel da CVM, sem chave nenhuma e sem custo. A pergunta livre
faz recuperação e geração ao vivo sobre os releases. O modo Agentes põe dois
agentes CrewAI para trabalhar: o Investigador descobre em que camada de dados a
companhia existe, consulta o que precisa e responde com citações; o Auditor
recebe só a afirmação e as citações, refaz as consultas por conta própria e
confirma, contesta ou declara que não reproduz. Entre os dois, o código confere
que cada número da resposta aparece na evidência sob a mesma métrica.

A avaliação corre num caminho separado. As 45 perguntas congeladas passam pelo
pipeline determinístico de recuperação e geração, sem agentes, porque a
variabilidade do plano multiagente tornaria as estratégias de recuperação
incomparáveis. As estratégias comparadas são E0 (sem documento, só como
controle), E1 (BM25), E2 (embeddings), E3 (fusão das duas) e E4, que ranqueia o
trecho pelos números da métrica perguntada.

| Camada | Tecnologia | Código |
| --- | --- | --- |
| Interface | Streamlit | `app_streamlit.py` |
| Documentos e RAG | Mistral OCR, ChromaDB, BM25, Gemini 3.5 Flash-Lite | `src/ingestao.py`, `src/indexacao.py`, `src/recuperacao.py`, `src/fatos.py`, `src/geracao.py` |
| Dados estruturados | DuckDB sobre os ZIPs da CVM | `src/dados_estruturados.py`, `src/mapa_contas.py`, `src/cobertura.py` |
| Modelo de ML | scikit-learn (gradient boosting) | `src/modelo/`, `src/projecao.py` |
| Agentes | CrewAI | `src/agentes.py`, `src/ferramentas.py` |
| Segurança | regras próprias, Presidio, Llama Prompt Guard 2 | `src/seguranca.py`, `src/reconhecedor_presidio.py`, `src/prompt_guard.py` |
| Observabilidade | Langfuse | `src/observabilidade.py` |
| Avaliação | golden dataset próprio, DeepEval | `src/avaliacao.py`, `src/avaliacao_deepeval.py`, `conjunto_padrao/` |

## Resultados medidos

### RAG no golden dataset

O golden dataset tem 45 perguntas congeladas em 29/07/2026, com resposta e
página-fonte conferidas à mão: 15 factuais, 10 comparativas, 10 qualitativas e
10 adversariais (premissa falsa, período ou companhia fora do corpus). Há ainda
10 perguntas de desenvolvimento, que nunca entram nos números abaixo, e 20
ataques em `conjunto_padrao/ataques.csv`.

Rodada `20260915T011103Z-85fbfadd35`, 45 perguntas × 5 estratégias, temperatura
0, US$ 0,26 no total:

| Estratégia | Recall@5 | Exatidão factual (15) | Exatidão comparativa (10) | Recusa correta (10) |
| --- | --- | --- | --- | --- |
| E0, sem documento | — | 0,000 | 0,000 | 0,800 |
| E1, BM25 | 0,920 | 0,400 | 0,000 | 1,000 |
| E2, semântica | 0,800 | 0,333 | 0,100 | 1,000 |
| E3, híbrida | 0,880 | 0,333 | 0,100 | 1,000 |
| E4, tabela de fatos | 0,880 | 0,400 | 0,400 | 1,000 |

Nenhuma estratégia é declarada vencedora. O limiar fixado antes da rodada exige
6 discordâncias na mesma direção (McNemar exato), e a maior diferença observada
entre duas estratégias foi 4 ([comparações](resultados/)). A exatidão é baixa
porque o sistema recusa quando não consegue fundamentar o número: na estratégia
semântica, que é a do chat, 10 respostas foram publicadas, 17 foram recusas do
próprio modelo e 18 rascunhos foram descartados pela verificação numérica.
Depois das correções de 20/10, reaplicadas às mesmas respostas gravadas, a
semântica publica 15, sem nenhuma errada a mais
([ajustes](resultados/ajustes_etapa2_2026-10-20.md),
[recusas das perguntas de desenvolvimento](resultados/recusas_dev_2026-10-20.md)).

### Segurança

Os guardrails bloquearam 20 de 20 ataques (9 de injeção, 11 de tópico regulado)
e não bloquearam nenhuma das 45 perguntas legítimas na entrada nem nenhum dos
855 textos gerados pelo próprio sistema na saída
([guardrails.json](resultados/guardrails.json)). CPF, CNPJ, e-mail e telefone
são anonimizados antes de qualquer chamada externa e não entram em log nem em
trace.

### Modelo de ML

O modelo classifica se uma companhia aberta terá prejuízo no trimestre
seguinte, treinado no painel da CVM de 2011 a 2025 (741 companhias, 21.903
pares de companhia e trimestre). Em walk-forward sobre 47 trimestres, o ROC-AUC
médio é 0,865, contra 0,846 do melhor baseline trivial; no alvo que o produto
usa (prejuízo em dois trimestres seguidos) é 0,879. Dentro de uma mesma
companhia o AUC cai para 0,663: o modelo indica quais companhias costumam dar
prejuízo, não em que trimestre uma lucrativa vai virar
([relatório do modelo](resultados/modelo_preditivo_2026-08-23.md),
[robustez](resultados/robustez_modelo_2026-08-24.md)).

O chat não usa o modelo para prever o resultado de companhia nomeada na
instância pública. Os agentes recebem o panorama agregado (quantas companhias
lucrativas estão acima do limiar, a validação do modelo e a taxa histórica por
faixa de porte). Em execução local, depois de gerar os escores com
`gerar_panorama_modelo.py --com-escores`, `PREVISAO_POR_EMISSOR_HABILITADA=true`
libera o escore por companhia no chat, etiquetado como fora de domínio quando
for o caso.

### Agentes, observabilidade e DeepEval

Em 20/10/2026, 19 perguntas feitas pelo próprio app geraram 19 traces no
Langfuse, e o custo registrado no servidor bateu com o do app em todos
([traces](artefatos/observabilidade/)). As perguntas livres levaram de 1,7 a
8,1 segundos; as dos agentes, de 8 a 44. Em 7 perguntas do conjunto próprio
dos agentes, 4 respostas cobriram tudo o que o gabarito pede e 3 trouxeram os
números certos com explicação incompleta; nenhuma trouxe número errado
([medição](resultados/agentes_produto_2026-10-20.md)).

O DeepEval mediu faithfulness e answer relevancy nas 45 respostas gravadas, com
o DeepSeek V4 Flash como juiz. Contra a auditoria humana feita às cegas em 10
itens, concordou em 4, e o juiz próprio do projeto em 8; um critério de período
em G-Eval levou a concordância a 5. Por isso o DeepEval serve como triagem, e a
referência continua sendo a auditoria humana
([relatório](resultados/deepeval_2026-10-20.md)).

## Como reproduzir

Requer Python 3.12 e o [Ollama](https://ollama.com) rodando localmente para os
embeddings.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull bge-m3
install -m 600 .env.example .env      # preencha só as chaves que for usar
```

Extras opcionais: `requirements-modelo.txt` (treino do modelo),
`requirements-guardrails.txt` (Presidio e Prompt Guard 2) e
`requirements-deepeval.txt` (instale com `pip install --no-deps -r`; o arquivo
explica por quê).

**Testes.** `pytest -q` roda 2.212 casos sem nenhuma chamada externa. Num clone
recém-feito, 4 deles ficam pulados até o índice e o painel de treino existirem.

**Dados.** Os PDFs e os ZIPs da CVM não vão para o Git; os manifestos guardam
URL e SHA-256, e os scripts conferem o hash ao baixar. O OCR dos releases já
está versionado em `corpus/ocr/`, então reconstruir o índice não paga OCR de
novo.

```bash
python scripts/baixar_corpus.py
python scripts/baixar_cvm.py --anos $(seq -s, 2011 2026) --conjuntos itr,dfp
python -m scripts.construir_painel_cvm --anos 2025-2026 --destino artefatos/cvm.duckdb
python -m scripts.construir_painel_cvm --anos 2011-2026 --destino artefatos/cvm_treino.duckdb
python executar_pipeline.py --etapa ingestao
python executar_pipeline.py --etapa indexacao
```

**Modelo.** Treino em CPU, alguns minutos:

```bash
pip install -r requirements-modelo.txt
python -m scripts.treinar_modelo --painel artefatos/cvm_treino.duckdb
python -m scripts.gerar_panorama_modelo --painel artefatos/cvm_treino.duckdb
```

**Interface.** `streamlit run app_streamlit.py` abre no modo de demonstração,
sem segredo nenhum. Para a pergunta livre e os agentes, defina no `.env`
`GEMINI_API_KEY` e `HABILITAR_PERGUNTAS_LIVRES=true`; o app limita perguntas
por sessão e aplica teto de orçamento. Com `LANGFUSE_PUBLIC_KEY` e
`LANGFUSE_SECRET_KEY`, cada pergunta vira um trace.

**Avaliações.** Toda chamada paga exige `--permitir-api-paga`; sem a flag, os
scripts só contam casos e estimam o custo.

```bash
python executar_pipeline.py --etapa avaliacao --conjunto teste --permitir-api-paga  # 225 chamadas, ~US$ 0,26
python -m scripts.comparar_estrategias_pareado --a fatos --b semantica                 # custo zero
python -m scripts.reaplicar_guarda_rn02                                                # custo zero
python -m scripts.medir_guardrails                                                     # custo zero
python -m scripts.avaliar_deepeval --permitir-api-paga --teto-usd 0.70                 # juiz pago
python -m scripts.gerar_traces_langfuse --permitir-api-paga                            # traces reais
```

## Estrutura do repositório

```text
├── app_streamlit.py          interface (demonstração, pergunta livre, agentes)
├── executar_pipeline.py      ingestão, indexação e avaliação
├── src/                      código do sistema (uma camada por módulo)
│   └── modelo/               painel supervisionado, treino e previsão
├── scripts/                  download, gates, treino, medições e avaliações
├── tests/                    suíte pytest
├── conjunto_padrao/          golden dataset, ataques e conjunto dos agentes
├── corpus/
│   ├── metadados.csv         os 20 releases: URL, data e SHA-256
│   ├── ocr/                  cache de OCR versionado
│   ├── cvm/                  manifesto dos ZIPs da CVM e correções com procedência
│   └── ifrs/                 âncora do gate de validação do painel
├── artefatos/
│   ├── modelo/               métricas e panorama agregado do modelo
│   ├── resultados_avaliacao/ rodada congelada, respostas do modo demonstração, DeepEval
│   ├── resultados_agentes/   respostas gravadas dos agentes
│   ├── observabilidade/      traces do Langfuse conferidos pela API
│   └── indice_vetorial/      descritor do índice (o índice é regenerado)
├── resultados/               relatórios dos números citados aqui
└── docs/                     página de documentação e as fontes em Markdown
```

## Limitações

- O corpus tem 5 bancos e 4 trimestres (2T2025 a 1T2026). Os números de recall
  e exatidão não valem para qualquer documento financeiro.
- A verificação numérica é conservadora de propósito e ainda descarta
  respostas corretas, sobretudo frases qualitativas que reúnem várias
  métricas.
- O modelo de ML ordena companhias por risco, mas não antecipa a virada de uma
  companhia lucrativa. Para os cinco bancos do corpus, que tiveram um único
  prejuízo em 173 trimestres, ele diz pouco.
- O painel de treino herda defeitos conhecidos dos arquivos da CVM, como
  escala declarada em mil numa versão e em unidade noutra para cerca de 43
  companhias; o efeito no modelo não foi medido.
- O modelo de linguagem pode ter visto estes releases no pré-treinamento; a
  estratégia E0 existe para medir isso.
- O quarto trimestre não é arquivado como trimestre na CVM. O sistema o deriva
  por subtração e marca o valor como derivado.

## Licença e créditos

MIT, ver [LICENSE](LICENSE). Os PDFs não são redistribuídos. Os dados contábeis
vêm do [Portal de Dados Abertos da CVM](https://dados.cvm.gov.br), conjuntos
ITR e DFP.

**Built with Llama.** A camada de segurança usa o Llama Prompt Guard 2 86M como
detector de injeção, sob a Llama 4 Community License, que exige esta
atribuição.
