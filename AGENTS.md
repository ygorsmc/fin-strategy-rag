# AGENTS.md — Execução: Assistente de Research Financeiro com RAG

Este é o guia **específico** para o agente que vai executar o projeto descrito na `especificacao.md`. Seu papel é materializar o repositório de código que roda de ponta a ponta, implementando rigorosamente a arquitetura, as regras de negócio (RN) e o escopo aprovado.

## 0. Agnosticismo e Privacidade da Empresa (Regra Dura)

O projeto deve ser 100% **agnóstico quanto à empresa-alvo de qualquer vaga**. 
- NENHUM nome de banco (como BTG Pactual, Itaú, etc.) deve aparecer na documentação como *seu possível empregador* ou *empresa-alvo*.
- O repositório aborda o domínio de "Research Financeiro" processando dados públicos (releases de resultados dos 5 maiores bancos do Brasil), mas a ferramenta não é um "produto de uma empresa X".
- Use o slug neutro do projeto: `assistente-research-financeiro`.
- O README focará no problema técnico: localizar informações pontuais em textos longos e auditar alucinações de LLMs em dados financeiros estruturados.

## 1. O Pipeline a ser construído

A ordem de construção já foi definida na seção 5.15 da spec. Você deve implementá-la nesta exata sequência:

1. **Gate G1 (`scripts/gate.py`):** Valide a criação do recurso de inferência LLM e embeddings. Registre a evidência de sucesso ou falha (acionando fallback documentado) em `resultados/gate.md`. Não inicie processamento pesado sem passar pelo gate.
2. **Download do Corpus (`scripts/baixar_corpus.py`):** Crie o script que obtém os PDFs dos releases trimestrais. Atualize o `corpus/metadados.csv` (empresa, URL, data, hash).
3. **Conjunto-Padrão (`conjunto_padrao/perguntas.csv`):** Configure as 45 perguntas de avaliação divididas em factuais, comparativas, qualitativas e adversariais.
4. **Ingestão e Chunking (`src/ingestao.py`):** Extraia texto dos PDFs mantendo numeração de páginas. Divida em blocos de ~600 tokens (100 de overlap), inserindo cabeçalho contextual no texto.
5. **Normalização (`src/normalizacao.py`):** Implemente parser numérico pt-BR (lidando com R$, bilhões, milhões e %). É fundamental que este módulo seja coberto por testes unitários (`pytest`).
6. **Indexação (`src/indexacao.py`):** Construa os índices de embeddings (FAISS) e de palavra-chave (BM25). Crie a guarda de consistência de metadados para garantir que consulta e índice usem o mesmo modelo.
7. **Recuperação (`src/recuperacao.py`):** Lógica Top-K, permitindo filtro opcional por empresa/trimestre com base nos metadados da pergunta.
8. **Geração (`src/geracao.py`):** Implemente o prompt fixo e a arquitetura plugável. O LLM deve retornar JSON contendo: resposta, indicador booleano de recusa, e metadados de citação da fonte.
9. **Avaliação (`src/avaliacao.py`):** Script para medir Recall@5, Exatidão Numérica e Taxa de Recusa, comparando as estratégias (Closed-book, BM25, Semântica e Híbrida).
10. **Interface (`app_streamlit.py`):** Crie a interface de consulta interativa permitindo modo de demonstração livre ou cacheado.
11. **(Fase 3) Módulo LoRA:** Implemente o classificador PEFT leve para rotear perguntas e servir de guardrail.

## 2. Estrutura Obrigatória do Repositório

Sua saída deve espelhar exatamente esta estrutura (`assistente-research-financeiro/`):

```text
├── AGENTS.md               (Cópia deste guia)
├── README.md               (Foco no domínio financeiro e na avaliação de métricas vs resultados reais)
├── LICENSE                 (MIT)
├── requirements.txt        (Versões pinadas)
├── .env.example            (Contrato de variáveis de ambiente sem expor chaves)
├── .gitignore              (Regras para ignorar `corpus/raw/`, `artefatos/indice_vetorial/` não estáticos, etc)
├── executar_pipeline.py    (Orquestrador com flag `--amostra` para smoke test)
├── scripts/
│   ├── baixar_corpus.py
│   └── gate.py
├── corpus/
│   ├── raw/                (Arquivos PDF não comitados)
│   └── metadados.csv       (Fonte de verdade)
├── src/
│   ├── ingestao.py
│   ├── normalizacao.py
│   ├── indexacao.py
│   ├── recuperacao.py
│   ├── geracao.py
│   └── avaliacao.py
├── conjunto_padrao/
│   └── perguntas.csv
├── artefatos/
│   ├── indice_vetorial/
│   ├── logs_execucoes/     (JSONL com registro de versão/modelo/parâmetros)
│   └── resultados_avaliacao/
├── app_streamlit.py
└── tests/
    ├── test_ingestao.py
    ├── test_normalizacao.py
    └── test_regras.py
```

## 3. Contratos e Regras Invioláveis

- **Honestidade de Avaliação:** Testes no `pytest` são para regras de formatação/chunking (passa/falha). Recall@5, taxa de alucinação e Exatidão são **resultados avaliados**. Eles devem ser rodados no conjunto-padrão (temperatura 0), calculados honestamente, logados no `artefatos/logs_execucoes/` e expostos no README.
- **Tolerância Zero para Alucinação e Vazamento:** Se o LLM não encontrar base no trecho recuperado, a flag booleana de recusa DEVE ser verdadeira (RN02).
- **Dados Privados/Segredos:** Nunca versionar PDFs (`corpus/raw/`) para evitar questões de redistribuição, e NUNCA colocar chaves de API reais (OpenAI/Azure) em código.
- **Deploy Seguro:** Para mitigar custos e estouro de memória, a versão publicada no Streamlit Cloud/Container Apps deve funcionar por padrão no modo "demonstração cacheado" usando o conjunto-padrão pré-computado, ou limitar as execuções de perguntas livres ao limite estabelecido no `.env`.

## 4. Seu Entregável Final

Quando finalizar o trabalho, o script `executar_pipeline.py` deve processar a extração dos metadados, aplicar testes unitários com pytest, rodar as avaliações no conjunto de teste e salvar os números reais das estratégias testadas para serem postas no README final. O sistema deverá estar pronto para o push no GitHub sem nenhuma amarra ao nome da empresa-alvo da vaga.
