# Assistente de Research Financeiro com RAG e Comparação de Estratégias

*Projeto de portfólio direcionado à vaga Estágio em Ciência de Dados (TECH - DATA) — BTG Pactual*

| Campo | Valor |
|-------|-------|
| **Data** | 2026-07-14 |
| **Empresa / vaga-alvo** | BTG Pactual · Estágio em Ciência de Dados (TECH - DATA) |
| **Perfil** | Ciência de Dados, com núcleo de arquitetura IA/LLM proporcional ao pedido explícito da vaga ("projetar e treinar modelos baseados em LLMs"). Os artefatos de meio (seção 5) combinam a variante Dados (pergunta de negócio, pipeline, métricas) com elementos da variante IA/ML (arquitetura, limitações previstas) onde isso aumenta o rigor, sem duplicar seções. |
| **Modo** | Misto — consolida Python, arquitetura de provedor de LLM plugável e avaliação estatística de saídas de IA (ambos já validados no projeto "Corretor de Redação do ENEM"); usa inferência local com Ollama e avalia Azure apenas como opção condicional de Fase 3, além de busca vetorial/BM25 formal, Streamlit e ajuste fino leve (LoRA, aprovado em `escopo.md`) |
| **Status** | Aprovada para execução — escopo marcado em `escopo.md` (2026-07-14): transcrições de teleconferência adiadas (⏸), todos os demais módulos aprovados (✅), incluindo Fase 3 e LoRA. Passe crítico de modos de falha aplicado após a aprovação (seção 5.18) |

---

## 1. Contexto de mercado e dores (pesquisa de campo)

- **Setor / área da empresa:** BTG Pactual é o maior banco de investimento da América Latina,
  com atuação em Investment Banking, Corporate Lending, Sales & Trading, Wealth Management,
  Asset Management, SME e Digital Investments and Banking. A vaga é para a área "Analytics"
  do banco, que a própria descrição define como transversal — apoia "diversas áreas de
  negócio" com estatística, modelagem analítica, visualização e experimentação, e não um
  produto único. O texto isola, ao lado dessas responsabilidades clássicas, uma frente
  explícita de "projetar e treinar modelos baseados em LLMs".
- **Concorrentes analisados:** Itaú Unibanco (agente de investimento por IA generativa,
  ~1,9 mil projetos de automação/analytics), Nubank (aquisição da Hyperplane, empresa de
  inteligência de dados, para acelerar IA em crédito e aconselhamento), XP Investimentos
  (modelo de propensão a investir para direcionar recomendações a assessores), C6 Bank e
  PagBank (IA generativa focada em eficiência de back-office e atendimento).

**Dores identificadas**

| Dor | Tipo | Evidência (fonte) |
|-----|------|-------------------|
| BTG mantém uma plataforma pública de research/conteúdo financeiro (relatórios de análise, equity research) com volume relevante de documentos | Observada | content.btgpactual.com/research |
| A área de Analytics do BTG atua de forma transversal e difusa ("diversas áreas de negócio"), sem um produto de dados único — texto da própria vaga | Observada | vaga.md (texto integral fornecido) |
| BTG já opera 150+ iniciativas de IA, ~80 relacionadas a personalização de experiência do cliente, com LLM proprietário desenvolvido desde 2019 | Observada | finsidersbrasil.com.br — "O potencial e os riscos da IA generativa, na visão de BTG, C6 e PagBank" |
| BTG lançou o "Minhas Finanças" (IA + Open Finance) para prever gastos, mas a adoção de Open Finance no Brasil ainda é de apenas 37% dos usuários — limita o alcance de qualquer IA que dependa desse dado | Observada | letsmoney.com.br — "BTG lança gestão financeira com IA que prevê gastos" |
| Concorrentes diretos (Itaú, Nubank, XP) também investem pesado em personalização/IA aplicada a produtos financeiros — corrida setorial, não iniciativa isolada do BTG | Observada | neofeed.com.br; international.nubank.com.br; conteudos.xpi.com.br |
| Bancos citam explicitamente "prevenir alucinações" como preocupação central de governança ao adotar IA generativa | Observada | finsidersbrasil.com.br (mesmo artigo BTG/C6/PagBank) |
| Profissionais de research/analytics gastam tempo relevante localizando uma informação pontual dentro de relatórios financeiros longos (releases de resultado, formulários trimestrais), tornando lenta a resposta a uma pergunta específica | Hipótese | inferência a partir do volume/formato dos documentos públicos (CVM, RIs dos bancos) — não há métrica de tempo divulgada publicamente pelo BTG ou concorrentes |

**Fontes consultadas**

- `finsidersbrasil.com.br` — "O potencial e os riscos da IA generativa, na visão de BTG, C6 e
  PagBank": 150+ iniciativas de IA no BTG, LLM proprietário desde 2019, hiperpersonalização,
  preocupações de governança (alucinação, privacidade, regulação).
- `letsmoney.com.br` — "BTG lança gestão financeira com IA que prevê gastos": mecânica do
  "Minhas Finanças" (Open Finance + previsão de gastos + LLM proprietário no WhatsApp) e o
  dado de 37% de adoção de Open Finance no Brasil.
- `neofeed.com.br` — "IA, hiperpersonalização e quase 2 mil projetos: o plano do Itaú":
  ~1,9 mil projetos de automação/analytics, agente de investimento (50 bases, 22 mil
  simulações), SuperApp com 10,1 milhões de usuários migrados.
- `international.nubank.com.br` — aquisição da Hyperplane e estratégia de IA baseada em
  dados/modelos fundacionais para crédito e aconselhamento financeiro.
- `conteudos.xpi.com.br` — uso de IA para estimar propensão de cliente a investir em renda
  variável e direcionar recomendações a assessores.
- `dados.cvm.gov.br` — Portal de Dados Abertos da CVM: conjuntos ITR (Informações
  Trimestrais) e DFP (Demonstrações Financeiras Padronizadas), histórico desde 2010/2011,
  atualizado semanalmente, com link de download dos formulários — usado como fonte
  estruturada de conferência do gabarito (seção 5.8).
- Páginas de Relações com Investidores de Itaú Unibanco, Santander Brasil, Bradesco e Banco
  do Brasil ("Central de Resultados"/"Divulgação de Resultados") — confirma que releases de
  resultado trimestrais são publicados em PDF, gratuitos, sem cadastro.
- `content.btgpactual.com/research` — plataforma de research do próprio BTG, usada apenas
  como referência de contexto (não como fonte do corpus, por ter conteúdo restrito a
  autenticação).
- `learn.microsoft.com/en-us/answers` — threads "Azure OpenAI with Azure for Students" e
  "Azure Student Foundry issue" (respostas de moderadores Microsoft, mar–abr/2026):
  assinatura Azure for Students **não é elegível** para criar recursos Azure OpenAI/AI
  Foundry — bloqueio de política da plataforma (erro `RequestDisallowedByAzure` em todas
  as regiões, não configurável pelo usuário), e mesmo quando o recurso chega a ser criado
  a cota de modelos pode vir zerada. A saída oficial é assinatura Pay-As-You-Go ou oferta
  educacional gerenciada pela instituição. Fato usado no plano de provedores (5.7), no
  deploy (5.13) e nas limitações (5.17).
- `docs.streamlit.io` — "App resource limits": apps no Streamlit Community Cloud têm
  limite de ~1 GB de memória; estourar derruba o app para o visitante. Fato usado na
  arquitetura de deploy (5.13).

## 2. Problema e objetivo

O time de Analytics do BTG atende múltiplas áreas de negócio e cita, isolada das demais
responsabilidades, uma frente de "projetar e treinar modelos baseados em LLMs" — sinal de
que a vaga espera exposição a IA generativa aplicada, não só modelagem analítica clássica.
Este projeto recorta um problema concreto e plausível para essa frente: profissionais de
research/analytics financeiro precisam localizar informações pontuais — um número, uma
comparação entre instituições, um destaque qualitativo — dentro de um volume crescente de
documentos longos (releases de resultado trimestrais de bancos listados), hoje só
navegáveis por leitura manual. O projeto constrói um assistente de perguntas e respostas
ancorado em Retrieval-Augmented Generation (RAG) sobre um corpus curado e 100% público
desses documentos, com uma restrição não negociável: nunca inventar um número ou fato
ausente da fonte recuperada. O objetivo é demonstrar, lado a lado e com evidência honesta
de acerto/erro/recusa, os dois eixos que a vaga pede: modelagem analítica rigorosa
(comparação de estratégias de recuperação) e arquitetura de IA/LLM aplicada a um problema
financeiro real, ao mesmo tempo em que o projeto ensina, na prática, como cinco dos
maiores bancos do Brasil reportam seus próprios resultados.

## 3. Escopo e não-escopo

**No escopo:**

- Corpus curado e fixo de documentos públicos — releases de resultado trimestrais de 5
  bancos listados (BTG Pactual, Itaú Unibanco, Bradesco, Santander Brasil, Banco do Brasil),
  para os últimos 4 trimestres disponíveis no momento da coleta — não um pipeline de
  ingestão contínua ou scraping em larga escala.
- Pipeline RAG completo: ingestão → chunking → indexação (vetorial + palavra-chave) →
  recuperação → geração com citação obrigatória.
- Conjunto-padrão de 45 perguntas com gabarito verificado manualmente, cobrindo 4
  categorias (factual, comparativa, qualitativa, adversarial-sem-resposta).
- Comparação formal de 4 estratégias de resposta (closed-book, keyword/BM25, semântica,
  híbrida) sobre esse conjunto-padrão.
- Interface de consulta local (Streamlit, estilo chat) exibindo resposta e fontes citadas.
- Fase 3 (aprovada em `escopo.md`): após o fluxo local estar 100% verde e mediante
  autorização explícita de gasto, publicação opcional em Azure Container Apps ou
  Streamlit Community Cloud, com mitigação de custo/exposição, e o módulo de ajuste
  fino leve (LoRA) da seção 5.16.

**Nota honesta sobre "treinar modelos baseados em LLMs":** esta especificação cobre
integralmente o **projetar** (arquitetura RAG, engenharia de prompt, avaliação formal).
"Treinar" no sentido literal — ajustar pesos de um modelo — não é coberto pelo uso de LLMs
via API/inferência. Para fechar essa lacuna com honestidade, a seção 5.16 descreve um
módulo de ajuste fino leve (LoRA) de um classificador pequeno — **aprovado em
`escopo.md`** para esta rodada (Fase 3).

**Nota honesta sobre a nuvem escolhida (Azure, não AWS):** a vaga pede explicitamente
"interesse em desenvolvimento de soluções na AWS". Este projeto usa **Azure** — decisão
consciente do candidato, não desconhecimento do pedido. Justificativa a comunicar em
entrevista: aproveitamento de créditos de estudante (Azure for Students) e continuidade
com outro projeto do portfólio que já roda em Azure (Container Apps, no corretor de
redação do ENEM). **Fato verificado na pesquisa (2026):** a assinatura Azure for
Students **não é elegível** para criar recursos Azure OpenAI/AI Foundry — bloqueio de
política da plataforma (fontes na seção 1). Por isso o plano começa com um Gate L1 local
e reserva o Gate G1 Azure ao pré-deploy (seção 5.7). Se a publicação em nuvem for
aprovada após o fluxo local estar verde, os créditos podem ser usados na hospedagem em
Azure Container Apps. Os conceitos de arquitetura — serviço
de IA generativa gerenciado, autenticação/segredo em nuvem, deploy serverless/contêiner
— são portáveis entre provedores; o equivalente direto na AWS seria o Amazon Bedrock,
citado ao longo desta spec como referência de equivalência sempre que relevante. Se a
entrevista cobrar AWS especificamente, a resposta esperada é nomear essa equivalência,
não alegar experiência que o projeto não teve.

**Fora do escopo:**

- Ingestão automática/contínua de novos documentos — o corpus é fixo, coletado uma vez e
  versionado.
- Cobertura de todo o mercado financeiro — o corpus cobre 5 bancos, não é um produto de
  research completo nem substitui a plataforma de research do próprio BTG.
- Teste A/B com usuários reais ou cálculo de poder estatístico a priori — não se aplica a
  este tipo de sistema de perguntas e respostas em lote; a comparação de estratégias por
  benchmark offline determinístico cumpre esse papel de validação comparativa.
- Uso de qualquer dado interno, proprietário ou não público do BTG — todo o corpus é
  público e nominalmente documentado.
- Interface mobile nativa ou suporte a idiomas além do português.

## 4. Requisitos

Vocabulário: `RF` = funcional (o que faz), `RNF` = não funcional (qualidade),
`RN` = regra de negócio (restrição/política).

### Requisitos funcionais (RF)

| ID | Requisito | Módulo |
|----|-----------|--------|
| RF01 | Selecionar e obter um corpus curado de releases de resultado (5 bancos, últimos 4 trimestres), com lista nominal dos documentos e data de coleta | Seleção do corpus |
| RF02 | Extrair texto dos PDFs e dividir em chunks com metadados de citação (empresa, tipo de documento, trimestre, página) | Ingestão e chunking |
| RF03 | Validar a qualidade da extração (chunk vazio/corrompido, cobertura por documento) antes de indexar | Qualidade de dados |
| RF04 | Construir um conjunto-padrão de 45 perguntas com gabarito verificado, conferindo números contra a fonte estruturada CVM (ITR/DFP) | Conjunto-padrão de avaliação |
| RF05 | Indexar os chunks por embeddings (busca vetorial) e por índice de palavra-chave (BM25) | Indexação |
| RF06 | Recuperar os top-k trechos mais relevantes para uma pergunta, com filtro opcional por metadados quando a pergunta especifica empresa/trimestre | Recuperação |
| RF07 | Gerar resposta com LLM a partir dos trechos recuperados, em saída estruturada (JSON: resposta, recusa, citações com empresa/documento/trimestre/página) que permita verificação automática de RN01–RN02 | Geração |
| RF08 | Declarar ausência de evidência suficiente quando os trechos recuperados não sustentam uma resposta (RN02) | Geração |
| RF09 | Comparar 4 estratégias (closed-book, keyword, semântica, híbrida) no conjunto-padrão e reportar métricas por estratégia | Comparação de estratégias |
| RF10 | Expor uma interface de consulta (Streamlit, estilo chat) mostrando resposta e trechos/fontes recuperados | Interface |
| RF11 | Se a Fase 3 for autorizada após o fluxo local estar verde, publicar a interface em Azure Container Apps ou Streamlit Community Cloud, conforme créditos disponíveis, com mitigação de custo/exposição para tráfego público anônimo | Deploy |

### Requisitos não funcionais (RNF)

| ID | Requisito |
|----|-----------|
| RNF01 | Pipeline reproduzível por um único comando (`executar_pipeline.py`), com flag `--amostra` para um subconjunto reduzido (smoke test) |
| RNF02 | Corpus 100% público e nominalmente documentado; nenhum dado privado ou sintético apresentado como real |
| RNF03 | Custo de desenvolvimento/avaliação estimado a priori (teto) e medido ao final (meta vs. resultado) |
| RNF04 | Segredos (chaves Azure/API) nunca versionados; uso de `.env` local e Streamlit secrets na versão publicada |
| RNF05 | Cobertura de testes automatizados (pytest) para ingestão/chunking e para as regras RN01–RN03 |
| RNF06 | Arquitetura de provedor plugável para embeddings e LLM, sem travar num único fornecedor |
| RNF07 | Latência ponta a ponta por consulta documentada como meta e depois medida |
| RNF08 | Avaliação reproduzível: temperatura 0, modelo/versão/parâmetros/custo registrados por execução (log JSONL versionado); conjunto-padrão congelado após construção, com número de execuções completas documentado |
| RNF09 | Consistência de índice: o índice vetorial grava provedor/modelo/dimensão do embedding usado na construção; consultar com modelo diferente gera erro explícito, nunca resultado silenciosamente errado |

### Regras de negócio (RN)

| ID | Regra |
|----|-------|
| RN01 | Toda resposta gerada cita explicitamente a fonte (empresa, documento, trimestre, página) dos trechos usados para produzi-la |
| RN02 | Se os trechos recuperados não contiverem evidência suficiente, o sistema declara isso explicitamente — mesmo que o modelo "saiba" a resposta por conhecimento geral de pré-treinamento. Nunca responde com base em memória paramétrica fora do corpus curado |
| RN03 | A instância pública (Fase 3) limita perguntas livres por sessão (melhor esforço — contornável por refresh) **e** mantém teto/alerta de orçamento no lado do provedor; o controle real é o do provedor, não o do cliente. Estourou o teto: o modo livre desliga, o demo cacheado continua no ar |

## 5. Pergunta, dados e pipeline (Ciência de Dados + arquitetura de IA/LLM)

### 5.1 Visão geral do pipeline

```
corpus público (PDF)
   │  RF01
   ▼
ingestão + chunking (texto, metadados de citação)          RF02
   │
   ▼
validação de qualidade (chunk vazio? cobertura ok?)         RF03
   │
   ├──────────────► índice BM25 (palavra-chave)             RF05
   │
   └──────────────► embeddings ──► índice FAISS (vetorial)  RF05
                                          │
conjunto-padrão (45 perguntas + gabarito) │  RF04
   │                                      │
   ▼                                      ▼
        recuperação top-k (+ filtro de metadados)           RF06
                        │
                        ▼
        geração com citação obrigatória / recusa (RN01–02)  RF07, RF08
                        │
                        ▼
        comparação de estratégias (E0–E3)                   RF09
                        │
                        ▼
        interface de consulta (Streamlit)                   RF10
                        │
                        ▼
        publicação com mitigação de custo (Fase 3)           RF11
```

Orquestrador único: `executar_pipeline.py`, com `--amostra` rodando 1 banco × 1 trimestre
para validar o pipeline de ponta a ponta em minutos antes da execução completa.

### 5.2 Seleção e obtenção do corpus

- **Instituições:** BTG Pactual, Itaú Unibanco, Bradesco, Santander Brasil, Banco do
  Brasil — os cinco maiores bancos listados do país, escolhidos por padronizarem o
  formato de release trimestral e por serem diretamente comparáveis entre si (mesmo tipo
  de produto financeiro: crédito, captação, seguros).
- **Período:** os 4 trimestres mais recentes disponíveis no momento da coleta (ancorado
  em torno de 2T2025–1T2026 nesta data de leitura; ajustável ao que estiver publicado na
  execução real). Regra de fixação: no congelamento do corpus, vale a **interseção** —
  os 4 trimestres mais recentes disponíveis para **todos os cinco** bancos (as datas de
  divulgação variam semanas entre eles), registrados nominalmente em `metadados.csv`;
  sem isso, as perguntas comparativas quebrariam por corpus assimétrico.
- **Documento por banco/trimestre:** o release de resultados ("Divulgação de
  Resultados"/"Central de Resultados"), baixado diretamente da página de Relações com
  Investidores de cada banco — gratuito, sem cadastro, confirmado nas páginas de RI de
  Itaú, Santander Brasil, Bradesco e Banco do Brasil.
- **Volume esperado:** 5 bancos × 4 trimestres = 20 documentos-base, ~20–40 páginas cada
  (400–600 páginas no total) — tratável para chunking e indexação local.
- **Registro nominal:** `corpus/metadados.csv` lista, por documento, empresa, trimestre,
  URL de origem, data de coleta e hash do arquivo — auditável e reprodutível.
- **PDFs brutos fora do Git** (tamanho — 20 documentos podem passar de 100 MB — e
  cautela de redistribuição): `baixar_corpus.py` re-obtém cada documento pela URL do
  `metadados.csv` e valida o hash; URL morta ou hash divergente é detectado e
  documentado, nunca re-raspado silenciosamente. O manifesto é a fonte de verdade do
  corpus, não os binários.
- **Instituição-armadilha (para o subconjunto adversarial):** um banco real, conhecido e
  deliberadamente fora do corpus — Nubank (Nu Pagamentos/Nu Holdings) — usado para gerar
  perguntas plausíveis, mas genuinamente sem resposta no corpus curado (seção 5.8).
- **Extensão opcional (Fase 2):** transcrições de teleconferência de resultados, apenas
  para os bancos/trimestres em que estiverem publicamente disponíveis sem cadastro —
  enriquecem as perguntas qualitativas, mas não são um compromisso de Fase 1 por
  disponibilidade não verificada banco a banco. **Adiada nesta rodada** (⏸ em
  `escopo.md`).

### 5.3 Ingestão e chunking

- Extração de texto por página (biblioteca de leitura de PDF), preservando o número da
  página de origem.
- Divisão em chunks de aproximadamente 600 tokens com sobreposição de 100 tokens,
  respeitando limites de parágrafo quando possível (evita cortar uma frase ao meio).
- Cada chunk carrega metadados: `empresa`, `trimestre`, `documento`, `pagina`,
  `posicao_no_documento` — usados tanto no filtro de recuperação quanto na citação
  obrigatória (RN01). Chunk que cruza páginas registra o intervalo (ex.: `págs. 12–13`)
  e a citação herda o intervalo.
- **Cabeçalho contextual no texto indexado:** cada chunk é prefixado com
  `[EMPRESA | documento | trimestre | pág. N]` no próprio texto que vai para o índice e
  para o prompt — melhora a recuperação (o banco/trimestre passa a ser "buscável" mesmo
  quando o parágrafo não os repete) e entrega ao LLM o dado de citação dentro do próprio
  trecho, em vez de exigir que ele o infira.
- Parâmetros (`CHUNK_TAMANHO_TOKENS`, `CHUNK_SOBREPOSICAO_TOKENS`) configuráveis via
  `.env` (seção 5.14) — a comparação de estratégias (5.10) pode, opcionalmente, sensibilizar
  esses valores, mas isso não é um requisito de Fase 1.

### 5.4 Qualidade de dados

- Testes automatizados verificam: nenhum chunk vazio ou só com caracteres de controle;
  todo documento do `metadados.csv` gerou ao menos N chunks (limiar mínimo por página);
  todo chunk tem os 5 campos de metadado preenchidos; nenhuma página duplicada dentro do
  mesmo documento.
- **Teste-sentinela por documento:** releases são densos em tabelas, e extração de
  tabela é o ponto mais frágil de PDF→texto — os números que as perguntas factuais
  perseguem vivem exatamente lá. Para cada documento, 1–2 valores-âncora conhecidos
  (ex.: o lucro líquido de capa do release) são conferidos no texto extraído após
  normalização numérica pt-BR; se o valor-âncora não aparece, a extração daquele
  documento falhou de forma relevante mesmo com os testes estruturais passando. Antes de
  marcar o documento como falho, tenta-se o parser alternativo (pypdf ↔ pdfplumber).
- Cada pergunta factual do gabarito registra se o número-fonte vive em tabela ou em
  texto corrido (`origem=tabela|texto`) — se os erros se concentrarem em `tabela`, o
  diagnóstico aponta extração, não recuperação nem geração.
- Falha de qualidade em um documento não derruba o pipeline inteiro — o documento é
  marcado e reportado, e a execução segue com os demais (mesmo princípio de
  `continueOnFail` já usado no projeto de relatório de obra).

### 5.5 Indexação

- **Vetorial:** embeddings por chunk, armazenados num índice FAISS local (arquivo único,
  da ordem de poucos MB para os ~2–4 mil chunks esperados). Provedor de embeddings
  plugável (RNF06): Ollama/BGE-M3 multilíngue (1.024 dimensões, custo zero e padrão em
  desenvolvimento), MiniLM local alternativo ou serviço gerenciado apenas se o Gate G1
  de pré-deploy justificar (equivalente na AWS seria o Bedrock Titan Embeddings).
- **Guarda de consistência (RNF09):** o índice grava, junto dos vetores, metadados de
  construção — provedor, modelo, dimensão, data e hash do corpus. Consultar um índice
  com um modelo de embedding diferente do que o construiu produz similaridades sem
  sentido **sem nenhum erro visível** — o modo de falha mais silencioso do projeto —,
  então o código valida o par índice/consulta e falha com mensagem explícita em caso de
  mismatch. As métricas finais reportadas usam a mesma configuração de embedding ponta a
  ponta da instância publicada.
- **Palavra-chave:** índice BM25 sobre o mesmo conjunto de chunks — necessário para a
  estratégia E1 (seção 5.10) e como comparação clássica de recuperação.
- Reconstrução do índice é determinística a partir do corpus + `metadados.csv` — não há
  estado oculto fora do `artefatos/indice_vetorial/`. Versionados no Git: só os
  artefatos pequenos de que a instância publicada precisa (índice de deploy, respostas
  cacheadas do modo demonstração, `metadados.csv`); PDFs brutos e artefatos de
  desenvolvimento ficam fora (gitignore) e são regeneráveis por script.

### 5.6 Recuperação

- Top-k configurável (`TOP_K`, padrão 5) por similaridade (vetorial) ou por score BM25
  (palavra-chave), conforme a estratégia.
- Filtro opcional por metadados: se a pergunta menciona explicitamente uma empresa e/ou
  trimestre, a recuperação restringe a busca a esse subconjunto antes de rankear — reduz
  confusão entre bancos com métricas de nome parecido (ex.: "carteira de crédito").
- A extração do filtro (empresa/trimestre citados na pergunta) usa correspondência de
  texto simples (nomes e códigos de trimestre conhecidos), não um NER treinado — suficiente
  para o vocabulário fechado de 5 bancos e 4 trimestres deste projeto.
- **Perguntas comparativas (2+ bancos):** a recuperação decompõe em subconsultas por
  instituição detectada (top-k por banco, depois fusão) — num top-k global, os chunks de
  um único banco tendem a dominar e a categoria comparativa falharia em bloco.
- **Normalização mínima para o BM25 em pt-BR:** minúsculas e remoção de acentos na
  tokenização ("Itaú"/"Itau", "provisão"/"provisao"), documentada e coberta por teste —
  sem isso, a estratégia E1 perde exatamente os termos que deveria achar.

### 5.7 Geração de resposta e regras anti-alucinação

- Prompt fixo instrui o modelo a responder **apenas** com base nos trechos recuperados,
  citando empresa/documento/página para cada afirmação numérica, e a declarar
  explicitamente quando os trechos não bastam (operacionaliza RN01–RN02).
- Arquitetura de provedor de LLM plugável (RNF06), reaproveitando o padrão já validado no
  projeto do corretor de redação do ENEM (troca de provedor por variável de ambiente).
  Divergência deliberada em relação ao pedido literal de AWS da vaga — ver nota na
  seção 3. A ordem é **local-first**, para não consumir créditos durante desenvolvimento:
  - **Ramo ativo:** Gemini API executa a geração (`gemini-3.1-flash-lite`) pelo
    endpoint OpenAI-compatible; BGE-M3 via Ollama continua nos embeddings. O Gate
    Gemini registra JSON, citação, recusa, tokens, latência e custo estimado em
    `resultados/gate_gemini.md`.
  - **Fallback local:** Ollama continua disponível para geração e embeddings sem
    chave paga; o Gate L1 registra essa alternativa em `resultados/gate_local.md`.
  - Todo o pipeline, avaliação, Streamlit e eventual demonstração via container/ngrok
    são validados localmente antes de qualquer tentativa de deploy. Ollama nunca é
    exposto diretamente; somente a porta do Streamlit pode receber túnel autenticado.
  - **Gate G1 Azure no pré-deploy:** somente quando o fluxo local estiver 100% verde e
    após autorização separada para provisionar/configurar deployments Azure. O
    `scripts/gate.py` não descobre capacidade nem cria recursos: apenas valida endpoints
    já existentes. Se passar, o serviço gerenciado continua opcional; se não for
    autorizado ou falhar, a inferência local e o demo cacheado permanecem funcionais.
  - O Gate Gemini, o Gate L1 e, se executado, o G1 entram no resumo executivo como
    evidência, não alegação.
- **Contrato de saída estruturada (RF07):** o gerador responde JSON —
  `{resposta, recusa: bool, motivo_recusa, citacoes: [{empresa, documento, trimestre,
  pagina}]}`. Isso torna RN01–RN02 verificáveis por código: recusa é um campo booleano
  (não interpretação de texto livre) e toda citação deve referenciar um chunk realmente
  recuperado naquela consulta (checagem automática de subconjunto). JSON inválido tem
  **uma** tentativa de reparo; persistindo, conta como erro da estratégia naquele item —
  nunca re-tentado até passar.
- **Determinismo:** temperatura 0 em toda avaliação; modelo, versão e parâmetros de cada
  execução registrados em log JSONL (RNF08).

### 5.8 Conjunto-padrão de avaliação (golden set)

- 45 perguntas construídas manualmente pelo candidato após leitura dos documentos-fonte,
  divididas em 4 categorias:
  - **Factual numérica (15):** uma métrica pontual de um banco/trimestre (ex.: lucro
    líquido, ROE, carteira de crédito expandida, índice de inadimplência).
  - **Comparativa (10):** exige síntese entre 2+ documentos (ex.: qual banco teve maior
    ROE no trimestre X).
  - **Qualitativa/aberta (10):** destaques ou explicações discursivas mencionadas pela
    administração (ex.: principais fatores citados para a variação do resultado).
  - **Adversarial-sem-resposta (10):** perguntas plausíveis, mas genuinamente sem
    resposta no corpus, distribuídas por subtipos nomeados para estressar RN02 de vários
    ângulos: instituição fora do corpus (Nubank, ≥4 perguntas — o caso inequívoco),
    trimestre/período ausente (ex.: resultados de 2019), métrica não divulgada nos
    documentos coletados, premissa falsa (ex.: "por que o lucro caiu?" quando subiu) e
    fato que o LLM provavelmente "sabe" do pré-treinamento mas que não está no corpus
    (ex.: nome do CEO) — este último é o teste mais duro da regra RN02. Para premissa
    falsa, o gabarito aceita recusa **ou** correção fundamentada com citação.
- **Gabarito numérico conferido de forma independente — em duas classes:** releases
  trazem tanto números contábeis (IFRS) quanto **gerenciais/ajustados** ("lucro líquido
  ajustado", "ROE anualizado ajustado"), e os gerenciais frequentemente **não batem**
  com o ITR/DFP da CVM — por definição, não por erro. Ignorar isso condenaria a
  conferência do gabarito a "falhar" em massa com o sistema certo. Cada pergunta
  factual/comparativa declara sua classe de verificação:
  - `cvm`: métrica contábil — valor esperado extraído do conjunto estruturado ITR/DFP
    (`dados.cvm.gov.br`), independente do PDF do corpus (evita que um erro de leitura
    contamine pergunta e gabarito ao mesmo tempo);
  - `release_gerencial`: métrica ajustada — verificada por dupla leitura independente do
    release (em dias diferentes), com o enunciado **fixando a definição** ("segundo o
    release, qual o lucro líquido ajustado…"), nunca deixando ambíguo qual número é o
    esperado.
  Perguntas comparativas comparam **como divulgado em cada release**; a limitação de que
  métricas gerenciais não são perfeitamente comparáveis entre bancos (cada um ajusta à
  sua maneira) fica registrada na seção 5.17, não escondida.
- **Tolerância numérica:** resposta considerada correta se estiver dentro de 1% relativo
  do valor esperado ou coincidir após normalização de unidade/arredondamento (evita falso
  negativo por diferença de formatação, ex. milhares vs. milhões).
- **Normalização numérica pt-BR (pré-requisito do verificador):** "R$ 2,3 bilhões",
  "1.234,5 milhões" e "23,4%" são convertidos para unidades canônicas antes de qualquer
  comparação — vírgula decimal, separador de milhar, multiplicadores mil/milhões/bilhões
  e percentual. É um utilitário próprio com testes unitários; sem ele, a exatidão
  numérica produziria falsos negativos em massa. Nomes de banco em respostas
  comparativas passam por tabela de apelidos ("Itaú"/"Itaú Unibanco"/"ITUB4").
- **Esquema do gabarito (`perguntas.csv`):** id, conjunto (`teste`/`dev`), categoria,
  subtipo adversarial, pergunta, resposta esperada, classe de verificação, unidade,
  origem do número (`tabela`/`texto`), locais aceitos (documento + página, um ou mais —
  base do recall@k; o mesmo número pode aparecer na capa e no detalhamento), checklist
  de pontos-chave (para as 10 qualitativas — o critério manual de acerto é "cobre ≥ N
  pontos e não contradiz nenhum") e comportamento aceito (para premissa falsa).
- **Conjunto de desenvolvimento separado (anti-overfitting):** ~10 perguntas extras
  (mistas, com gabarito leve, sem exigência de conferência CVM) para iterar prompt,
  chunking e recuperação. As 45 do conjunto-padrão são **congeladas** após a construção
  (data registrada) e rodadas poucas vezes, com cada execução completa logada (RNF08) —
  iterar contra o próprio conjunto de teste inflaria as métricas reportadas, o mesmo
  vício de ajustar um modelo olhando o test set.

### 5.9 Métricas de avaliação (metas a validar)

| Métrica | Escopo | Meta |
|---------|--------|------|
| Recall@5 (chunk correto entre os 5 recuperados) | 25 perguntas factuais + comparativas | ≥ 0,80 |
| Exatidão numérica (tolerância 1% ou arredondamento) | 15 perguntas factuais | ≥ 0,75 |
| Taxa de recusa correta | 10 perguntas adversariais | ≥ 0,90 |
| Groundedness (auditoria manual amostral — resposta não afirma nada ausente do contexto recuperado) | amostra de 15 respostas entre todas as categorias | ≥ 0,90 |
| Latência ponta a ponta (recuperação + geração) | todas as consultas | ≤ 10 s |
| Custo médio por consulta | todas as consultas | sem meta a priori — medir e reportar |

Groundedness é avaliada por auditoria manual numa amostra fixa (não um classificador
automático) — mais lenta, mas honesta: um "detector de alucinação" automático teria a
mesma fragilidade que está sendo testada. A parte mecânica, porém, é automática: toda
citação deve referenciar um chunk realmente recuperado naquela consulta (contrato JSON,
seção 5.7); a auditoria manual cobre o que máquina não pega — afirmação sem lastro no
trecho citado.

Definições operacionais:

- **Recall@5, factual:** acerto se algum chunk do top-5 cobre uma das páginas-fonte
  aceitas no gabarito (comparação por página, já que fronteiras de chunk são
  arbitrárias).
- **Recall@5, comparativa:** exige **todas** as instituições da pergunta representadas
  no top-5 — é o modo de falha típico da categoria (top-k dominado por um único banco;
  mitigação na seção 5.6).
- **Latência:** medida **a quente** (exclui cold start e carga de modelo), reportando
  média e p95 — o primeiro acesso de uma instância que escala a zero não conta contra a
  meta.
- **Estabilidade:** um subconjunto de 10 perguntas é re-executado 3× para medir
  variância de resposta mesmo a temperatura 0; se houver flutuação, ela é reportada
  junto das métricas, não escondida.
- **Execução em lote resiliente:** checkpoint por pergunta (retomável após falha de rede
  ou limite de taxa, com retry e backoff) e custo logado por chamada — uma execução
  interrompida não é perdida nem paga duas vezes; se o gasto acumulado atingir o teto
  (RNF03), a execução pausa e reporta em vez de estourar o orçamento.

### 5.10 Comparação de estratégias

Quatro estratégias avaliadas sobre o mesmo conjunto-padrão de 45 perguntas:

- **E0 — Closed-book (diagnóstico, não candidata):** o LLM responde sem qualquer trecho
  recuperado, só com conhecimento de pré-treinamento. Não está sujeita a RN01/RN02 (não há
  trecho para citar) — seu papel é diagnóstico: expõe quanto de "vazamento" de
  conhecimento pré-treinado existe (ex.: o modelo pode "saber" um número real do Nubank
  sem nenhuma evidência recuperada, o que seria uma falha se um sistema real dependesse
  disso). Reportada separadamente, nunca comparada 1-para-1 com E1–E3 na coluna de
  recusa correta.
- **E1 — Keyword/BM25 + geração com citação:** recuperação clássica por palavra-chave.
- **E2 — Semântica (embeddings) + geração com citação:** RAG "padrão" deste projeto.
- **E3 — Híbrida (Fase 2, aprovada):** combina E1+E2 (ex.: reciprocal rank fusion).

| Estratégia | Recall@5 | Exatidão numérica | Recusa correta (10 adv.) | Groundedness (amostra) | Custo médio | Latência média |
|---|---|---|---|---|---|---|
| E0 — Closed-book | — (não recupera) | *meta/resultado* | *diagnóstico, não meta* | *meta/resultado* | *meta/resultado* | *meta/resultado* |
| E1 — Keyword/BM25 | *meta/resultado* | *meta/resultado* | *meta/resultado* | *meta/resultado* | *meta/resultado* | *meta/resultado* |
| E2 — Semântica | *meta/resultado* | *meta/resultado* | *meta/resultado* | *meta/resultado* | *meta/resultado* | *meta/resultado* |
| E3 — Híbrida (Fase 2) | *meta/resultado* | *meta/resultado* | *meta/resultado* | *meta/resultado* | *meta/resultado* | *meta/resultado* |

E2 (semântica) é a estratégia-alvo do projeto; E1 e E0 existem para provar, com número,
que a recuperação vetorial e a citação obrigatória valem o custo de engenharia — o mesmo
espírito da comparação regra-vs-modelo-vs-combinada usada nos outros projetos deste
ciclo, adaptado ao domínio de RAG. Todas as estratégias rodam sobre as mesmas perguntas
congeladas, com temperatura 0 e os mesmos índices; custo e latência de cada uma saem do
mesmo log JSONL de execução (RNF08) — comparação justa, não anedótica.

### 5.11 Interface de consulta

- Streamlit, estilo chat (`st.chat_message`): usuário digita a pergunta, recebe a
  resposta e, expansível, os trechos recuperados com empresa/documento/página de cada um.
- Modo "conjunto-padrão": permite re-executar qualquer uma das 45 perguntas do
  golden set e ver a resposta lado a lado com o gabarito — útil tanto para depuração
  quanto para demonstração.
- A interface sempre exibe em qual modo está (demonstração cacheada vs. pergunta livre)
  e qual provedor gerou a resposta — transparência de demonstração: ninguém confunde
  resposta cacheada com inferência ao vivo.

### 5.12 Resumo executivo

Documento de 1–2 páginas: problema, corpus (5 bancos, 4 trimestres, 20 documentos),
métodos comparados (E0–E3), métricas medidas vs. metas, principais casos de recusa
correta e de erro, resultado do Gate L1 e status condicional do G1 (com evidência quando
executado — seção 5.7), custo
real de desenvolvimento vs. teto estimado, limitações (seção 5.17).

### 5.13 Arquitetura de custo e exposição pública (Fase 3)

**Pré-condição local-first:** nenhum recurso ou deploy Azure é criado enquanto testes,
avaliação e interface não funcionarem ponta a ponta localmente. Antes da nuvem, uma
demonstração temporária pode usar container/ngrok autenticado, expondo somente o
Streamlit e nunca o endpoint do Ollama.

Diferença importante em relação aos outros dois projetos de Ciência de Dados deste ciclo
(Sanar e InComm/Méliuz não se aplicam aqui do mesmo jeito): um dashboard de agregados
pré-computados nunca faz uma chamada de API paga por visita, mas este assistente
**precisa** gerar uma resposta nova a cada pergunta livre — uma chamada real ao provedor
de LLM (e, se semântica, ao provedor de embeddings) por consulta. Publicar isso sem
limite exporia a conta de nuvem do candidato a qualquer visitante anônimo.

Mitigação:

- **Alvo de publicação condicional:** somente após autorização explícita de gasto,
  escolher entre Azure Container Apps e Streamlit Community Cloud conforme créditos,
  memória e custo medidos. Container/ngrok autenticado cobre demonstrações temporárias
  antes dessa decisão.
- **Uma eventual instância em nuvem nunca carrega modelo de embedding local** (centenas de MB de
  RAM só para embedar a consulta): embeddings do corpus são pré-computados offline; a
  pergunta livre embeda apenas a consulta via API, usando **o mesmo modelo** que
  construiu o índice publicado (RNF09).
- **Modo demonstração (padrão, custo zero):** as 45 perguntas do conjunto-padrão têm
  resposta pré-computada e armazenada (`artefatos/resultados_avaliacao/`); a interface
  pública abre nesse modo por padrão e funciona **sem nenhum segredo configurado** —
  mostra o sistema sem gerar tráfego pago nem expor chave.
- **Modo "pergunta livre" (limitado):** até `LIMITE_PERGUNTAS_LIVRES_POR_SESSAO`
  perguntas por sessão (padrão: 5), usando um provedor de custo baixo e previsível
  (RN03). Limite de sessão é melhor esforço — um refresh o contorna — e por isso **não**
  é o controle real.
- **O controle real é do lado do provedor:** teto e alerta de orçamento configurados na
  conta (alerta de custo do Azure e/ou limite de gasto do provedor de LLM). Estourou o
  teto: o modo livre é desligado e o demo cacheado continua no ar. RN03 exige os dois
  níveis, e o de provedor é o que de fato protege a conta.
- Uso de serviço gerenciado de IA no Azure (ramo A do gate G1, seção 5.7) é demonstrado
  via execução registrada do candidato (logs, capturas de tela ou vídeo curto) no resumo
  executivo, não necessariamente exposto ao tráfego público irrestrito.

### 5.14 Configuração

```
# Corpus
BANCOS=BTG,ITAU,BRADESCO,SANTANDER,BB
N_TRIMESTRES=4

# Chunking
CHUNK_TAMANHO_TOKENS=600
CHUNK_SOBREPOSICAO_TOKENS=100

# Recuperação
TOP_K=5
ESTRATEGIA_PADRAO=semantica       # closed_book | keyword | semantica | hibrida

# Provedores (plugável — RNF06; padrão local-first)
EMBEDDING_PROVIDER=ollama         # ollama | local | azure_openai | openai
LLM_PROVIDER=gemini               # gemini | ollama | azure_openai | openai | deepseek
TEMPERATURA=0                     # determinismo na avaliação (RNF08)
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
OLLAMA_MODELO_LLM=qwen2.5:14b
OLLAMA_MODELO_EMBEDDING=bge-m3
OLLAMA_EMBEDDING_DIMENSAO=1024
OLLAMA_TIMEOUT_S=180
OLLAMA_MAX_TOKENS=512
OLLAMA_EMBEDDING_BATCH_SIZE=4

# Gemini API — geração ativa; GOOGLE_API_KEY também é aceito
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODELO_LLM=gemini-3.1-flash-lite
GEMINI_TIMEOUT_S=120
GEMINI_MAX_TOKENS=512
GEMINI_REASONING_EFFORT=low
GEMINI_PRECO_ENTRADA_USD_MILHAO=0.25
GEMINI_PRECO_SAIDA_USD_MILHAO=1.50

# Azure: preencher apenas no Gate G1 de pré-deploy
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_API_VERSION=
AZURE_OPENAI_DEPLOYMENT_LLM=
AZURE_OPENAI_DEPLOYMENT_EMBEDDING=

# Avaliação
CONJUNTO_PADRAO_PATH=conjunto_padrao/perguntas.csv
TOLERANCIA_NUMERICA_PCT=1
ORCAMENTO_TETO_USD=10             # teto a priori (RNF03) — execução pausa ao atingir

# Exposição pública (Fase 3)
LIMITE_PERGUNTAS_LIVRES_POR_SESSAO=5
MODO_DEMONSTRACAO_CACHEADO=true
```

Sobre o teto de USD 10 (RNF03): ordem de grandeza, não chute — uma execução completa
das 4 estratégias sobre 45 perguntas movimenta centenas de milhares de tokens, o que em
modelo pequeno custa fração de dólar por execução; USD 10 comporta dezenas de execuções
completas mais as iterações de desenvolvimento. Estimativa a priori, a confirmar contra
a tabela de preços vigente somente se um provedor pago for ativado no Gate G1. No ramo
Ollama, o custo de API é zero e latência/consumo local são medidos e reportados.

### 5.15 Estrutura do repositório e ordem de construção

```
assistente-research-financeiro/
├── executar_pipeline.py
├── baixar_corpus.py            # re-obtém PDFs pela URL do manifesto e valida hash
├── .env.example
├── requirements.txt            # versões pinadas (reprodutibilidade)
├── corpus/
│   ├── raw/                    # PDFs baixados (fora do Git — regenerável por script)
│   └── metadados.csv           # empresa, trimestre, documento, URL, data de coleta, hash
├── src/
│   ├── ingestao.py             # extração + chunking + cabeçalho contextual
│   ├── normalizacao.py         # parser numérico pt-BR + apelidos de banco (testado)
│   ├── indexacao.py            # embeddings (local/API) + FAISS + BM25 + guarda RNF09
│   ├── recuperacao.py          # top-k, filtro de metadados, subconsulta por banco, E0–E3
│   ├── geracao.py              # prompt, contrato JSON, citação obrigatória, recusa
│   └── avaliacao.py            # métricas, checkpoint/retomada, log JSONL, teto de custo
├── conjunto_padrao/
│   ├── perguntas.csv           # ~10 dev enquanto o teste não congela
│   └── candidatas_teste.csv    # 45 candidatas, fora da avaliação até a 2ª leitura
├── artefatos/
│   ├── indice_vetorial/        # índice FAISS + metadados de construção (RNF09)
│   ├── logs_execucoes/         # JSONL por execução completa (RNF08)
│   └── resultados_avaliacao/   # métricas por estratégia + respostas cacheadas do demo
├── app_streamlit.py
├── tests/
│   ├── test_ingestao.py
│   ├── test_normalizacao.py    # parser pt-BR: vírgula, milhar, multiplicador, %
│   └── test_regras.py          # RN01–RN03 + guarda de consistência de índice
└── README.md
```

Ordem de construção:

1. **Gate Gemini:** validar a geração estruturada via Gemini API e registrar custo; manter
   o Gate L1 como fallback Ollama para embeddings/geração. O Gate G1 Azure fica reservado
   ao pré-deploy, depois de todo o fluxo local estar validado.
2. Selecionar e baixar o corpus (5 bancos × 4 trimestres, regra da interseção);
   registrar `metadados.csv` e congelar o conjunto de trimestres.
3. Construir o conjunto-padrão (45 candidatas a congelar + ~10 dev), conferindo números conforme a
   classe de verificação de cada pergunta (CVM ITR/DFP ou dupla leitura do release).
4. Implementar ingestão/chunking + normalizador pt-BR + testes de qualidade e sentinela.
5. Implementar indexação (BM25 + embeddings/FAISS) com a guarda de consistência (RNF09).
6. Implementar recuperação com filtro de metadados e subconsulta por banco.
7. Implementar geração com contrato JSON, citação obrigatória e recusa (RN01–RN02).
8. Implementar e rodar a comparação de estratégias (E0–E3) — iterando só no conjunto
   dev; o congelado roda ao final, com log por execução.
9. Construir a interface Streamlit e validar o fluxo nativo local.
10. Escrever resumo executivo e README (metas vs. resultados, Gates Gemini/L1).
11. Empacotar e, se necessário, demonstrar via ngrok autenticado somente após o fluxo
    nativo estar verde; não expor Ollama.
12. (Fase 3) Executar o Gate G1 Azure e só então decidir sobre Container Apps conforme
    créditos disponíveis; configurar teto/alerta e validar os dois modos.
13. (Fase 3) Módulo LoRA (seção 5.16), com a regra anti-vazamento de paráfrases.

### 5.16 Módulo de ajuste fino leve (cobre "treinar" literalmente) — aprovado

Para fechar com honestidade a lacuna apontada na seção 3 ("treinar" vs. "projetar"):
ajuste fino leve (LoRA/PEFT) de um modelo pequeno open-source (ex.: BERTimbau-base) para
uma subtarefa supervisionada real — classificar a categoria da pergunta
(factual/comparativa/qualitativa/fora-de-escopo). Base de treino: as perguntas do
projeto ampliadas por paráfrase (meta: ~200–300 exemplos rotulados), treinável em CPU ou
GPU gratuita (ex.: Google Colab T4). Aprovado em `escopo.md` como módulo de Fase 3.

- **Regra anti-vazamento:** a divisão treino/validação é por **pergunta-base** — todas
  as paráfrases de uma mesma pergunta ficam do mesmo lado do split. Avaliar sobre a
  paráfrase de uma pergunta vista no treino inflaria a acurácia do classificador, o
  vazamento clássico de dados aumentados.
- **Papel real no sistema (não decorativo):** o classificador vira o roteador de entrada
  da interface — pergunta classificada como fora-de-escopo recebe recusa rápida antes de
  gastar recuperação + chamada de LLM, funcionando como guardrail de custo (RN03) além
  de cobrir "treinar" literalmente.
- A acurácia do classificador é reportada como a de qualquer modelo: split honesto, meta
  declarada antes, resultado medido depois.

### 5.17 Limitações previstas

- **Corpus pequeno, não é o mercado inteiro:** 5 bancos, 4 trimestres — conclusões sobre
  recall/exatidão não generalizam para qualquer documento financeiro público, só para
  este recorte.
- **Contaminação por pré-treinamento:** o LLM pode ter visto estes releases (públicos)
  durante seu próprio treinamento — por isso E0 (closed-book) é reportado separadamente,
  como controle, não como concorrente direto.
- **LLM-as-judge é heurística, não verdade absoluta:** groundedness é auditada
  manualmente numa amostra justamente para não depender de um segundo LLM julgando o
  primeiro sem supervisão humana.
- **Hit rate de "recusa correta" depende de perguntas adversariais bem construídas:** se
  uma pergunta "armadilha" for ambígua o bastante para ter resposta parcial legítima no
  corpus, a categoria adversarial perde precisão — mitigado por reservar uma instituição
  inteira (Nubank) fora do corpus, o que é inequívoco.
- **Azure OpenAI/AI Foundry bloqueados para assinatura de estudante (fato verificado,
  2026):** política da plataforma impede a criação do recurso
  (`RequestDisallowedByAzure` em todas as regiões) e, quando o recurso chega a existir,
  a cota de modelos pode vir zerada — fontes na seção 1. Por isso o desenvolvimento usa
  Ollama e o Gate G1 ocorre apenas no pré-deploy (5.7). Container Apps permanece uma
  opção, não um requisito nem consumo antecipado de créditos.
- **Métricas gerenciais não são perfeitamente comparáveis entre bancos:** cada banco
  define os próprios ajustes ("lucro ajustado", "ROE anualizado"); as perguntas
  comparativas fixam "como divulgado em cada release" e essa limitação de domínio é
  declarada — bom assunto de entrevista, não defeito escondido.
- **Overfitting ao conjunto de avaliação:** iterar contra as mesmas 45 perguntas
  inflaria as métricas reportadas — mitigado pelo conjunto de desenvolvimento separado e
  pelo congelamento com log de execuções (5.8, RNF08).
- **Divergência consciente do pedido literal de AWS da vaga:** o projeto usa Azure por
  decisão de custo/continuidade do candidato (créditos de estudante, experiência prévia
  com Azure Container Apps), não por desconhecimento de AWS. A equivalência conceitual
  (Bedrock) é nomeada ao longo da spec para que essa divergência seja defensável em
  entrevista, não uma lacuna silenciosa.
- **Custo real da API é medido, não suposto:** RNF03 declara um teto a priori, mas o
  resumo executivo reporta o gasto medido — se o teto for furado, isso é reportado, não
  escondido.

### 5.18 Modos de falha previstos e mitigações (registro de risco)

Consolidação dos riscos de engenharia identificados no passe crítico. O detalhe de cada
mitigação vive na seção indicada; esta tabela existe para nenhum deles ser descoberto
"de surpresa" no meio da execução.

| # | Modo de falha | Sintoma provável | Mitigação prevista | Onde |
|---|---------------|------------------|--------------------|------|
| 1 | Assinatura de estudante bloqueia Azure OpenAI/Foundry (verificado) | `RequestDisallowedByAzure` ao criar o recurso; cota 0 | Ollama local-first + Gate G1 apenas no pré-deploy; Azure permanece opcional | 5.7, 5.13 |
| 2 | Extração de PDF quebra em tabelas — onde vivem os números | Recall alto, mas exatidão numérica baixa; números truncados/fora de ordem | Teste-sentinela por documento; parser alternativo; campo `origem=tabela\|texto` no gabarito para diagnóstico | 5.4, 5.8 |
| 3 | Gabarito gerencial ≠ CVM (ajustado vs. contábil) | Conferência do gabarito "falha" em massa com o sistema certo | Classe de verificação por pergunta (`cvm` vs. `release_gerencial`); enunciado fixa a definição da métrica | 5.8 |
| 4 | Comparação numérica sem normalização pt-BR | Falsos negativos ("R$ 2,3 bi" ≠ "2.300 milhões") | Normalizador testado (vírgula, milhar, multiplicador, %) + tabela de apelidos de banco | 5.8 |
| 5 | Índice construído com um modelo de embedding e consultado com outro | Similaridades sem sentido, **sem nenhum erro visível** | Metadados de construção no índice + erro explícito no mismatch (RNF09) | 5.5 |
| 6 | Top-k dominado por um único banco nas perguntas comparativas | Categoria comparativa falha em bloco | Decomposição em subconsultas por instituição + fusão | 5.6 |
| 7 | LLM devolve JSON inválido | Avaliação trava ou contabiliza lixo | Uma tentativa de reparo; depois conta como erro da estratégia (nunca loop) | 5.7 |
| 8 | Avaliação em lote interrompida (429/rede) no meio | Execução perdida; custo pago à toa | Checkpoint por pergunta + retomada; retry com backoff; custo logado por chamada; pausa ao atingir o teto | 5.9 |
| 9 | Iteração contra o conjunto de teste (overfitting) | Métricas reportadas infladas | Conjunto dev separado; 45 congeladas; execuções completas contadas e logadas | 5.8 |
| 10 | Instância pública estoura memória (Streamlit Cloud ~1 GB) | App cai para o visitante | Medir memória antes da escolha; não carregar embedding local em nuvem; demo sem segredo | 5.13 |
| 11 | Limite de sessão contornado por refresh gera custo | Conta de API cresce sem teto | Teto/alerta de orçamento no provedor (controle real); modo livre desliga, demo continua | 5.13, RN03 |
| 12 | Vazamento treino→teste no módulo LoRA (paráfrases) | Acurácia do classificador inflada | Split por pergunta-base — paráfrases nunca cruzam o split | 5.16 |

## 6. Stack e justificativa

| Camada | Tecnologia | Da vaga? | Conhecida? | Por quê |
|--------|-----------|----------|-----------|---------|
| Linguagem | Python | ✅ | ✅ tenho | pedida explicitamente |
| Extração de PDF | pypdf/pdfplumber | ➕ extra | 🆕 | indispensável para ingestão; não citado na vaga |
| Embeddings | Ollama/BGE-M3 local; MiniLM e APIs gerenciadas opcionais | ⚠️ diverge (vaga pede AWS) | 🆕 | custo zero em desenvolvimento, multilíngue e guardado por modelo/dimensão (RNF09) |
| Índice vetorial | FAISS | ➕ extra | 🆕 | padrão leve, local, sem servidor — agnóstico de nuvem |
| Busca por palavra-chave | BM25 (ex. `rank_bm25`) | ➕ extra | 🆕 | necessário para a comparação de estratégias (E1) |
| Geração (LLM) | Gemini 3.1 Flash-Lite via API; Ollama local como fallback; Azure/OpenAI/DeepSeek opcionais | ⚠️ diverge (vaga pede AWS) | 🆕 no Gemini/Ollama; ✅ no padrão plugável (validado no projeto ENEM) | geração estruturada com custo/latência registrados; equivalente AWS seria Bedrock |
| Ajuste fino leve (Fase 3, aprovado) | LoRA/PEFT sobre modelo pequeno (ex.: BERTimbau-base) | ➕ extra | 🆕 | cobre "treinar" literalmente e roteia fora-de-escopo (seção 5.16) |
| Orquestração do pipeline | Script único `executar_pipeline.py` | — | ✅ | reprodutibilidade (RNF01) |
| Testes | pytest | — | 🆕 documentado (mesmo padrão dos outros projetos do ciclo) | cobertura de ingestão e regras RN01–RN03 |
| Interface | Streamlit (chat) | ➕ extra | 🆕 (mesma curva dos outros projetos do ciclo) | ferramenta analítica de consulta |
| Deploy | nativo → container/ngrok autenticado → Azure Container Apps opcional | ⚠️ diverge (vaga pede AWS) | ✅ em Container Apps (ENEM); 🆕 neste app | progressão local-first; nuvem só após o fluxo local estar verde e conforme créditos |
| Segredos | `.env` local / Streamlit secrets | — | ✅ | nunca versionar chave |

> Marcado com 🆕 o que é aprendizado novo desta vaga; enriquece o próximo currículo
> **depois** de construído. Marcado com ➕ o que foi adicionado por necessidade do
> projeto, mesmo não estando na vaga. Marcado com ⚠️ **diverge** o que substitui
> deliberadamente uma tecnologia pedida pela vaga (AWS) por outra (Azure) — decisão de
> custo/continuidade do candidato, documentada na nota da seção 3 para ser defensável em
> entrevista, nunca apresentada como se fosse experiência em AWS.

## 7. Critério de "pronto"

- [ ] Corpus curado (5 bancos × 4 trimestres) baixado, com `metadados.csv` completo
      (empresa, trimestre, URL, data de coleta, hash).
- [ ] Pipeline de ingestão/chunking com testes automatizados de qualidade.
- [ ] Índice vetorial (FAISS) e índice BM25 construídos, reproduzíveis por
      `executar_pipeline.py` (com `--amostra` funcionando como smoke test).
- [x] Gate L1 local executado e documentado como fallback, com Ollama/BGE-M3/Qwen,
      custo zero e evidência regenerável em `resultados/gate_local.md`.
- [x] Gate Gemini executado e documentado com citação, recusa, tokens, latência e
      custo estimado em `resultados/gate_gemini.md`.
- [ ] (Fase 3 condicional; não bloqueia a conclusão local) Gate G1 Azure executado e
      documentado somente após autorização explícita de provisionamento/gasto.
- [ ] Conjunto-padrão de 45 perguntas com gabarito conferido conforme a classe de
      verificação de cada pergunta (CVM ITR/DFP para contábeis; dupla leitura
      independente para gerenciais), mais ~10 perguntas de desenvolvimento separadas.
- [ ] Data de congelamento das 45 perguntas registrada; log JSONL de cada execução
      completa versionado (RNF08).
- [ ] Regras RN01 (citação obrigatória) e RN02 (recusa por falta de evidência) testadas e
      comprovadas nas 45 perguntas, com cobertura de teste automatizado.
- [ ] Comparação de estratégias (E0–E2 no mínimo; E3 se incluída) rodada e registrada,
      com métricas da seção 5.9 reportadas como resultado, não meta.
- [ ] Interface Streamlit funcional localmente, exibindo resposta e fontes.
- [ ] `.env.example`/`requirements.txt` (versões pinadas) versionados; pipeline roda com
      os defaults documentados ou falha com mensagem clara se faltar uma chave
      obrigatória.
- [ ] Guarda de consistência de índice (RNF09) coberta por teste: mismatch de modelo de
      embedding gera erro explícito.
- [ ] Se um provedor pago for ativado, teto/alerta de orçamento configurado (RN03) e
      gasto real reportado contra o teto (RNF03).
- [ ] Custo real de desenvolvimento medido e comparado ao teto estimado (RNF03).
- [ ] (Fase 3) Deploy público com mitigação de custo/exposição (RN03) implementada e
      testada.
- [ ] README com metas vs. resultados medidos.
- [ ] Resumo executivo (seção 5.12) escrito.

## 8. Rastreabilidade

| Problema/necessidade | Requisito(s) | Módulo/entrega |
|----------------------|--------------|----------------|
| Vaga pede "projetar e treinar modelos baseados em LLMs", isolado das demais responsabilidades | RF07, RF08, RNF06 | Geração com citação/recusa; provedor plugável |
| Vaga pede interesse em AWS — projeto usa desenvolvimento local e mantém Azure opcional por continuidade técnica; assinatura de estudante não cria Azure OpenAI/Foundry | RF05, RF07, RF11, RNF04, RNF06 | Ollama + Gate L1; Gate G1 e Container Apps só no pré-deploy (5.7/5.13); equivalência com Bedrock nomeada na seção 6 |
| Diferencial "NLP" citado na vaga | RF02–RF09 | Pipeline RAG completo |
| Documentos financeiros longos dificultam localizar uma resposta pontual (dor observada) | RF06, RF09 | Recuperação com filtro; comparação de estratégias |
| Risco setorial documentado de alucinação em IA generativa aplicada a bancos | RN01, RN02, RF08 | Regras anti-alucinação e conjunto adversarial |
| Baixa adoção de Open Finance limita iniciativas de IA no setor (achado do "Minhas Finanças") | Escopo (seção 3) | Corpus público fixo, não dependente de dados de terceiros via Open Finance |
| "Treinar" (literal) não é coberto só por uso de LLM via API | Módulo 5.16 | Ajuste fino leve (LoRA) — aprovado em `escopo.md` (Fase 3), com papel de roteador/guardrail |
| Deploy público de um sistema que gera custo por consulta (diferente dos dashboards de agregados dos outros projetos do ciclo) | RF11, RN03 | Arquitetura de custo e exposição pública (5.13); teto no lado do provedor |
| Números de release são gerenciais e tabelas quebram na extração — risco simultâneo de gabarito e de ingestão | RF03, RF04 | Classes de verificação `cvm`/`release_gerencial`, testes-sentinela e normalizador pt-BR (5.4, 5.8) |
| Métricas reportadas precisam ser críveis (anti-overfitting, reprodutibilidade, consistência de índice) | RNF08, RNF09 | Conjunto dev + congelamento + logs de execução (5.8); guarda de índice (5.5); registro de risco (5.18) |
