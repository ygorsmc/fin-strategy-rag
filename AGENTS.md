# AGENTS.md — Execução: Assistente de Research Financeiro com RAG

Guia **específico** para o agente que executa o projeto descrito na `especificacao.md`.
**Fase atual: EXECUÇÃO.** O boilerplate foi entregue em 2026-07-15 (estrutura completa,
contratos tipados, utilitários de base e suíte de testes); o trabalho agora é implementar
os contratos pendentes, coletar o corpus real, construir o conjunto-padrão e medir as
métricas honestamente.

## 0. Agnosticismo e Privacidade da Empresa (Regra Dura — inalterada)

O projeto deve ser 100% **agnóstico quanto à empresa-alvo de qualquer vaga**.
- NENHUM nome de banco (BTG Pactual, Itaú, etc.) deve aparecer na documentação como
  *seu possível empregador* ou *empresa-alvo*. Citar os 5 bancos como **fonte de dados
  públicos do corpus** é permitido e necessário.
- Use o slug neutro do projeto: `assistente-research-financeiro`.
- O README foca no problema técnico: localizar informações pontuais em textos longos e
  auditar alucinações de LLMs em dados financeiros estruturados.
- A `especificacao.md` menciona a vaga de origem: ela é documento de trabalho local e
  **não deve ser publicada** no repositório final.

## 1. Estado atual do repositório (boilerplate entregue)

**Já implementado e testado (não regredir):**
- `src/config.py` — `Config` imutável; único ponto de leitura do `.env` (defaults = seção 5.14).
- `src/normalizacao.py` — `remover_acentos`, `normalizar_texto_bm25`, `APELIDOS_BANCOS`
  (inclui NUBANK como armadilha adversarial), `PADRAO_TRIMESTRE`, `MULTIPLICADORES`.
- `src/ingestao.py` — dataclasses (`DocumentoCorpus`, `PaginaExtraida`, `Chunk`,
  `RelatorioQualidade`), `carregar_metadados_corpus` (valida esquema),
  `montar_cabecalho_contextual` (formato `[EMPRESA | doc | trimestre | pág. N]`).
- `src/indexacao.py` — guarda RNF09 completa (`validar_consistencia`,
  `ErroConsistenciaIndice`, `salvar/carregar_metadados_indice`) e fábrica plugável de
  provedores de embeddings.
- `src/geracao.py` — `PROMPT_SISTEMA` fixo (`VERSAO_PROMPT="v1"` — mudou o prompt, sobe a
  versão e loga), dataclasses do contrato JSON, fábrica plugável de LLMs,
  `citacoes_sao_subconjunto` (checagem mecânica de RN01).
- `src/avaliacao.py` — esquema do gabarito (`COLUNAS_CONJUNTO_PADRAO`),
  `registrar_execucao` (JSONL, RNF08), dataclasses de resultado/métricas.
- `scripts/gate.py` — funcional: testa Azure OpenAI (LLM + embeddings) e regenera
  `resultados/gate.md` com evidência a cada execução.
- `scripts/baixar_corpus.py` — funcional: baixa pelo manifesto, valida/preenche SHA-256,
  reporta URL morta e hash divergente (nunca re-raspa silenciosamente).
- `executar_pipeline.py` — orquestrador com `--amostra` e `--etapa`; reporta
  OK/PENDENTE/FALHOU por etapa; a etapa `testes` roda o pytest.
- `app_streamlit.py` — casca funcional: modos demo-cacheado/pergunta-livre, limite por
  sessão, transparência de modo/provedor.

**Pendente (stubs `NotImplementedError`, cada um citando sua etapa):** parser numérico
pt-BR e apelidos (`normalizar_numero_ptbr`, `valores_equivalentes`, `canonizar_banco`,
`extrair_bancos_citados`, `extrair_trimestre_citado`); extração/chunking/qualidade
(`extrair_paginas`, `gerar_chunks`, `validar_qualidade`, `teste_sentinela`,
`ingerir_corpus`); embeddings e índices (`embedar` dos 3 provedores,
`construir_indice_faiss/bm25`, `carregar_indice_faiss`); recuperação
(`extrair_filtro_metadados`, `fusao_reciprocal_rank`, `Recuperador.recuperar`); geração
(`montar_prompt_usuario`, `parsear_resposta_llm`, `gerar_resposta`, adaptadores `.gerar`
dos 3 provedores); avaliação (`avaliar_recall_at_k`, `avaliar_exatidao_numerica`,
`avaliar_recusa`, `executar_avaliacao`, `consolidar_metricas`);
`responder_pergunta_livre` no app.

**Convenção de testes (obrigatória):** a suíte tem 92 casos — 40 passando (contratos já
implementados) e 52 marcados com `pendente = pytest.mark.skip(...)`. Ao implementar uma
etapa: (1) remova o marcador `pendente` da(s) classe(s) correspondente(s); (2) complete os
testes-esqueleto que contêm `raise AssertionError("implementar...")`; (3) NUNCA enfraqueça
uma asserção para fazer código passar — o teste é o contrato, o código se adapta a ele.
Arquivos de dados: `corpus/metadados.csv` e `conjunto_padrao/perguntas.csv` estão só com
cabeçalho (esquema validado por teste), aguardando as etapas 2–3.

**Dependências:** `requirements.txt` está curado e pinado nas versões do venv
(Python 3.12). `sentence-transformers==5.6.0` foi adicionado para a etapa 6 mas **ainda
não está instalado** — rode `pip install -r requirements.txt` antes de implementar os
embeddings locais.

## 2. Plano de execução (nesta ordem)

Cada etapa referencia a seção da spec, os stubs a implementar e o critério de conclusão.

1. **Gate G1 real (spec 5.7):** preencher o `.env` (copiar de `.env.example`), rodar
   `python scripts/gate.py` e commitar o `resultados/gate.md` com a evidência real.
   Fixar `LLM_PROVIDER`/`EMBEDDING_PROVIDER` conforme o ramo. O gate atual registra
   apenas "não configurado" — não vale como evidência final.
2. **Corpus (spec 5.2):** preencher `corpus/metadados.csv` com os releases reais —
   regra da interseção: os 4 trimestres mais recentes disponíveis para **todos os 5**
   bancos. Rodar `python scripts/baixar_corpus.py` até todos os hashes registrados.
   Concluída quando: 20 linhas no manifesto, 20 PDFs íntegros em `corpus/raw/`.
3. **Conjunto-padrão (spec 5.8):** 45 perguntas `conjunto=teste` (15 factuais,
   10 comparativas, 10 qualitativas, 10 adversariais com subtipos nomeados — ≥4 de
   Nubank) + ~10 `conjunto=dev`. Conferir gabarito pela classe de verificação
   (`cvm` via ITR/DFP; `release_gerencial` via dupla leitura). Registrar a **data de
   congelamento** neste arquivo ao concluir.
4. **Ingestão (spec 5.3–5.4; stubs de `src/ingestao.py`):** implementar extração
   pypdf⇄pdfplumber, chunking ~600/100 tokens (tiktoken), validação estrutural e
   teste-sentinela. Destravar os skips de `tests/test_ingestao.py`. Criar PDFs sintéticos
   pequenos em `tests/fixtures/` para os testes — nunca depender de PDF real no pytest.
5. **Normalização (spec 5.8; stubs de `src/normalizacao.py`):** parser numérico pt-BR,
   comparador com tolerância, canonização de bancos/trimestres. Destravar os skips de
   `tests/test_normalizacao.py` — os casos parametrizados já definem o contrato exato.
6. **Indexação (spec 5.5; stubs de `src/indexacao.py`):** `embedar` (local primeiro),
   FAISS + BM25, persistência determinística. A guarda RNF09 já existe — os construtores
   DEVEM gravar `MetadadosIndice` e a carga DEVE passar por `validar_consistencia`.
7. **Recuperação (spec 5.6; stubs de `src/recuperacao.py`):** filtro por metadados,
   subconsulta por banco nas comparativas (modo de falha nº 6), RRF para E3.
8. **Geração (spec 5.7; stubs de `src/geracao.py`):** adaptadores de provedor
   (o SDK `openai` cobre os 3 — Azure/OpenAI/DeepSeek), parse do JSON com UMA tentativa
   de reparo, checagem RN01 dentro de `gerar_resposta`. Destravar os skips de geração em
   `tests/test_regras.py`.
9. **Avaliação (spec 5.9–5.10; stubs de `src/avaliacao.py`):** métricas por definição
   operacional, checkpoint por pergunta, retry/backoff, teto de custo
   (`CustoExcedidoError`). Iterar SÓ no conjunto `dev`; rodar as 45 congeladas ao final,
   temperatura 0, logando cada execução completa (RNF08). Gerar
   `artefatos/resultados_avaliacao/respostas_cacheadas.json` para o modo demo.
   Destravar os skips de avaliação em `tests/test_regras.py`.
10. **Interface e README:** implementar `responder_pergunta_livre`, validar os dois modos
    localmente e preencher a tabela do README com os números **medidos** (nunca metas).
11. **(Fase 3) Deploy:** Azure Container Apps primário; demo cacheado sem segredo;
    teto/alerta de orçamento no provedor (RN03).
12. **(Fase 3) Módulo LoRA (spec 5.16):** classificador PEFT roteador/guardrail, split
    por pergunta-base (anti-vazamento de paráfrases).

## 3. Contratos e Regras Invioláveis (inalterados)

- **Honestidade de Avaliação:** pytest cobre regras de formatação/chunking (passa/falha).
  Recall@5, alucinação e exatidão são **resultados avaliados** — rodados no
  conjunto-padrão (temperatura 0), calculados honestamente, logados em
  `artefatos/logs_execucoes/` e expostos no README.
- **Tolerância Zero para Alucinação e Vazamento:** sem base no trecho recuperado, a flag
  booleana de recusa DEVE ser verdadeira (RN02).
- **Dados Privados/Segredos:** nunca versionar PDFs (`corpus/raw/`); NUNCA colocar chaves
  reais em código ou commit — `.env` local e secrets no deploy (RNF04).
- **Deploy Seguro:** a versão publicada funciona por padrão em modo demonstração cacheado
  e limita perguntas livres pelo `.env`; o controle real de custo é o teto no provedor.
- **Determinismo e não-regressão:** `pytest` verde é pré-condição de qualquer commit;
  etapa implementada = skips da etapa removidos e passando.

## 4. Estrutura do repositório (como está)

```text
├── AGENTS.md / CLAUDE.md / especificacao.md (local, não publicar a spec)
├── README.md · LICENSE (MIT) · requirements.txt (pinado) · .env.example · pytest.ini
├── executar_pipeline.py        (orquestrador; --amostra, --etapa)
├── scripts/gate.py · scripts/baixar_corpus.py
├── corpus/raw/ (fora do Git) · corpus/metadados.csv (fonte de verdade)
├── src/ config.py · ingestao.py · normalizacao.py · indexacao.py
│        recuperacao.py · geracao.py · avaliacao.py
├── conjunto_padrao/perguntas.csv
├── artefatos/ indice_vetorial/ · logs_execucoes/ · resultados_avaliacao/
├── resultados/gate.md          (evidência do gate G1 — regenerado por execução)
├── app_streamlit.py
└── tests/ conftest.py · test_ingestao.py · test_normalizacao.py · test_regras.py
```

## 5. Entregável Final

`executar_pipeline.py` processando ponta a ponta: testes verdes (sem skips), corpus
íntegro pelo manifesto, índices construídos com guarda RNF09, avaliação das estratégias
E0–E2 (E3 incluída) rodada nas 45 perguntas congeladas com log JSONL, números reais no
README (metas vs. resultados) e resumo executivo (spec 5.12). Pronto para push no GitHub
sem nenhuma amarra ao nome da empresa-alvo da vaga e sem a `especificacao.md`.

## Memória entre sessões — MEMORY.md

O `MEMORY.md` na raiz do repositório é o arquivo de **handoff entre sessões de
execução** — não um changelog, não um substituto deste AGENTS.md. A divisão de
papéis: AGENTS.md descreve o plano (estável, muda só quando o escopo muda);
MEMORY.md descreve **onde a execução parou** (muda a cada sessão que avança o
projeto).

- **No início de toda sessão de trabalho neste projeto:** ler o `MEMORY.md`
  antes de agir. Ele pode registrar decisão, bloqueio ou estado que não é
  óbvio a partir do código ou do `git log` — ex.: qual ramo do gate G1 ficou
  ativo, quantos documentos do corpus já foram baixados, se o conjunto-padrão
  já foi congelado, um bloqueio externo em aberto (cota de provedor, chave
  pendente etc.).
- **Ao final de toda sessão que mudar o estado da execução:** sobrescrever
  (nunca só anexar) as seções que ficaram desatualizadas. Formato sugerido:

  ```markdown
  ## Estado atual
  - Etapa ativa (plano §2): <número e nome>
  - Última etapa concluída: <número e nome> (<data>)

  ## Decisões e bloqueios em aberto
  - <decisão que desvia do padrão da spec, com o motivo — se houver>
  - <bloqueio esperando algo externo: chave de API, cota, disponibilidade de provedor>

  ## Próximo passo concreto
  - <ação específica, imediatamente executável pela próxima sessão>
  ```

- **O que NÃO vai no MEMORY.md:** nada que já esteja em `git log`/`git diff`
  (o histórico de commits já conta essa história); números de métricas de
  avaliação (vivem em `artefatos/` e no README, não aqui); segredos ou chaves
  (mesma regra do `.env`, RNF04 — nunca); o plano em si (isso é o AGENTS.md).
- Mantenha o arquivo curto (poucas dezenas de linhas). Se crescer a ponto de
  virar um changelog completo, está sendo mal usado — o Git já é o changelog.
