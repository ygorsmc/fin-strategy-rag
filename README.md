# Assistente de Research Financeiro (RAG)

Assistente de perguntas e respostas sobre **releases de resultado trimestrais
dos 5 maiores bancos listados do Brasil** (Itaú Unibanco, Bradesco, Santander
Brasil, Banco do Brasil e BTG Pactual — corpus 100% público), construído para
atacar dois problemas técnicos concretos:

1. **Localizar informações pontuais em textos longos** — um número, uma
   comparação entre instituições, um destaque qualitativo — dentro de
   documentos financeiros de 20 a 312 páginas. O corpus congelado cobre
   `2T2025`–`1T2026`: são 20 documentos e 2.790 páginas, hoje só navegáveis
   por leitura manual.
2. **Auditar alucinações de LLMs sobre dados financeiros estruturados** — o
   sistema nunca responde com base em memória paramétrica: toda resposta cita
   a fonte (empresa, documento, trimestre, página) e, sem evidência no trecho
   recuperado, ele **recusa** explicitamente.

## Como funciona

```
corpus público (PDF) → ingestão + chunking (~600 tokens, cabeçalho contextual)
  → validação de qualidade → índices BM25 + FAISS (embeddings)
  → recuperação top-k (filtro por empresa/trimestre; subconsulta por banco)
  → geração com contrato JSON: {resposta, recusa, citações}
  → avaliação comparativa de 4 estratégias sobre 45 perguntas com gabarito
```

Quatro estratégias são comparadas sobre o mesmo conjunto-padrão congelado, a
temperatura 0, com log JSONL por execução:

| Estratégia | Recall@5 | Exatidão numérica | Recusa correta | Custo médio | Latência média |
|---|---|---|---|---|---|
| E0 — Closed-book (diagnóstico) | — | *a medir* | *diagnóstico* | *a medir* | *a medir* |
| E1 — Keyword/BM25 | *a medir* | *a medir* | *a medir* | *a medir* | *a medir* |
| E2 — Semântica (embeddings) | *a medir* | *a medir* | *a medir* | *a medir* | *a medir* |
| E3 — Híbrida (RRF) | *a medir* | *a medir* | *a medir* | *a medir* | *a medir* |

> **Honestidade de avaliação:** as células acima serão preenchidas com os
> números **medidos** pela execução real (`artefatos/logs_execucoes/`), nunca
> com metas. Metas declaradas a priori: Recall@5 ≥ 0,80 · Exatidão ≥ 0,75 ·
> Recusa correta ≥ 0,90 · Groundedness (auditoria manual) ≥ 0,90 ·
> Latência ≤ 10 s.

O gabarito das perguntas factuais é conferido de forma independente contra a
fonte estruturada da CVM (ITR/DFP) quando a métrica é contábil, e por dupla
leitura do release quando é gerencial/ajustada — as duas classes não batem
entre si por definição, e o sistema de avaliação trata isso explicitamente.

## Como rodar

O ramo ativo usa **Gemini 3.1 Flash-Lite via API** para geração e BGE-M3 via
Ollama para embeddings. Ollama continua disponível como fallback local. Azure só
será avaliado no pré-deploy, depois de testes, avaliação e interface funcionarem
ponta a ponta.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull bge-m3
cp .env.example .env
# preencha GEMINI_API_KEY ou GOOGLE_API_KEY no .env

python scripts/gate_gemini.py     # smoke test Gemini: citação + recusa + custo
python scripts/gate_local.py      # fallback local: embeddings + citação + recusa
python scripts/baixar_corpus.py   # baixa os PDFs do manifesto e valida hashes
python executar_pipeline.py --amostra   # smoke test (1 banco × 1 trimestre)
python executar_pipeline.py             # pipeline completo
streamlit run app_streamlit.py          # interface de consulta
```

O Gate Azure (`python scripts/gate.py`) fica reservado à Fase 3. Container e
ngrok entram somente após a execução nativa estar verde; o túnel deve expor
apenas o Streamlit, nunca a porta `11434` do Ollama. O modo demonstração
cacheado continua sem segredo e sem chamada paga.

- `executar_pipeline.py` roda, em ordem: pytest → ingestão/qualidade →
  indexação → avaliação, e imprime um resumo por etapa.
- A interface abre em **modo demonstração cacheado** (respostas pré-computadas
  do conjunto-padrão, custo zero, sem segredo configurado); o modo de pergunta
  livre é limitado por sessão (`LIMITE_PERGUNTAS_LIVRES_POR_SESSAO`).

## Estrutura

```
├── executar_pipeline.py        # orquestrador único (--amostra p/ smoke test)
├── scripts/
│   ├── gate.py                 # Gate G1 Azure, somente no pré-deploy
│   ├── gate_local.py           # Gate L1 Ollama (resultados/gate_local.md)
│   ├── gate_gemini.py          # smoke test Gemini (resultados/gate_gemini.md)
│   └── baixar_corpus.py        # re-obtém PDFs pelo manifesto e valida hash
├── corpus/
│   ├── raw/                    # PDFs (fora do Git — regeneráveis por script)
│   └── metadados.csv           # fonte de verdade do corpus
├── src/
│   ├── ingestao.py             # extração + chunking + cabeçalho contextual
│   ├── normalizacao.py         # parser numérico pt-BR + apelidos de banco
│   ├── indexacao.py            # FAISS + BM25 + guarda de consistência (RNF09)
│   ├── recuperacao.py          # top-k, filtro de metadados, estratégias E0–E3
│   ├── geracao.py              # prompt fixo, contrato JSON, citação/recusa
│   └── avaliacao.py            # métricas, checkpoint, log JSONL, teto de custo
├── conjunto_padrao/
│   ├── perguntas.csv           # 10 dev enquanto o teste não congela
│   └── candidatas_teste.csv    # 45 candidatas, fora da avaliação
├── artefatos/                  # índices, logs de execução, resultados
├── app_streamlit.py            # interface chat
└── tests/                      # pytest: ingestão, normalização, regras RN01–RN03
```

## Garantias de engenharia

- **Anti-alucinação verificável por código:** a saída do LLM é JSON com campo
  booleano de recusa, e toda citação precisa referenciar um chunk realmente
  recuperado naquela consulta (checagem de subconjunto automática).
- **Consistência de índice:** o índice vetorial grava provedor/modelo/dimensão
  de construção; consultar com outro modelo falha com erro explícito — nunca
  similaridade silenciosamente sem sentido.
- **Reprodutibilidade:** temperatura 0, versões pinadas, corpus reconstruível
  a partir do manifesto (URL + hash), log JSONL por execução.
- **Segredos:** nunca versionados — `.env` local / secrets no deploy.

## Testes

```bash
pytest        # regras de formatação/chunking e RN01–RN03 (passa/falha)
```

Métricas de qualidade (recall, exatidão, recusa) **não** são testes de
unidade: são resultados medidos pela avaliação e reportados aqui.

## Licença

MIT — ver [LICENSE](LICENSE). O corpus referencia apenas documentos públicos
de Relações com Investidores; os PDFs não são redistribuídos neste
repositório (o manifesto com URL + hash permite re-obtê-los).
