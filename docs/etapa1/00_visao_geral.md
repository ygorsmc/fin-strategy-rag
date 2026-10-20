# 🎯 Visão geral

Todo trimestre, os cinco bancos listados que este projeto acompanha — Banco do Brasil, Bradesco, BTG Pactual, Itaú Unibanco e Santander Brasil — publicam dois conjuntos de números sobre o mesmo período. De um lado está o release de resultados, um PDF de dezenas ou centenas de páginas que o banco escreve para o mercado, com métricas ajustadas e a leitura que a própria administração faz do trimestre. Do outro estão os formulários ITR e DFP que esse mesmo banco entrega à CVM, onde o número é contábil, padronizado e sujeito a auditoria. As duas fontes são públicas e gratuitas, mas vivem separadas: quem consulta uma raramente abre a outra, e quando os dois números divergem para o mesmo trimestre não há nada que explique por quê.

O assistente responde perguntas sobre esses resultados consultando as duas fontes. A camada documental funciona por RAG: os releases estão indexados e, a cada pergunta, o sistema recupera os trechos que podem conter a resposta e pede ao modelo de linguagem que responda usando apenas aquilo, citando documento e página. A camada estruturada carrega o painel contábil da CVM em um banco analítico que responde a perguntas em linguagem natural sem depender de modelo de linguagem nenhum, e é ela que entrega o número arquivado quando a pergunta pede o dado oficial.

O que diferencia o projeto de um chatbot sobre PDFs é a disciplina de recusa. Um modelo treinado em texto público provavelmente já viu esses releases e consegue produzir um número convincente mesmo sem documento algum, e um número convincente e errado, numa resposta sobre balanço de banco, é pior do que não responder. Por isso, depois de gerar a resposta, o sistema confere se cada valor numérico dela aparece nos trechos que foram citados. Quando não aparece, a resposta é rebaixada para uma recusa explícita, ainda que o modelo tenha respondido com toda a confiança do mundo.

> Projeto demonstrativo e educacional. Não constitui recomendação de investimento: o sistema recusa esse tipo de pedido por regra, com base nas Resoluções CVM 19/2021 e 20/2021.

---

## 🧩 As camadas do sistema

A conversa acontece em uma interface de chat feita em Streamlit, que mantém o histórico da sessão, transmite a resposta aos poucos enquanto ela aparece na tela e indica sempre em que modo está operando e qual provedor gerou cada resposta. Há dois modos: um de demonstração, que abre sem nenhuma chave configurada e consulta o painel contábil sem custo, e um de pergunta livre, que precisa ser habilitado explicitamente e aciona o modelo de linguagem sobre os releases.

Por trás dela, os vinte releases do corpus foram extraídos, divididos em blocos e indexados em duas frentes complementares: um índice vetorial no ChromaDB, que encontra trechos por significado, e um índice BM25, que encontra por coincidência de palavras. O painel contábil, por sua vez, vive em DuckDB e reúne o cadastro das companhias, as linhas contábeis dos formulários e o mapa que traduz código de conta em conceito de negócio, todos relacionados entre si.

A conversa com o modelo é governada por um prompt escrito para este domínio, que proíbe responder de memória, obriga a citação e manda copiar cada número exatamente como impresso, sem converter escala nem arredondar. Antes que qualquer texto saia da máquina, uma camada de segurança bloqueia tentativas de injeção de instruções, recusa pedidos de recomendação de investimento e anonimiza dados pessoais que o usuário porventura tenha digitado na própria pergunta, como CPF, e-mail ou telefone.

---

## 🛠️ Stack tecnológica

| Função | Tecnologia | Por que esta escolha |
|---|---|---|
| Interface | Streamlit 1.59 | Chat com transmissão progressiva e estado de sessão |
| Banco vetorial | ChromaDB 1.4 | O filtro por metadados precisa acontecer antes do ranqueamento, e o FAISS indexa vetores e nada mais |
| Busca léxica | rank-bm25 | Canal paralelo ao vetorial, que sustenta a estratégia híbrida |
| Embeddings | BGE-M3 via Ollama | 1024 dimensões, roda local, nenhum custo por consulta |
| Dados estruturados | DuckDB 1.4 | Analítico, embarcado, lê os formulários da CVM sem servidor |
| Geração | Gemini 3.5 Flash Lite | Venceu o comparativo de acerto, custo e latência; Ollama, DeepSeek, OpenAI e Azure ficam atrás da mesma interface plugável |
| Extração de PDF | Mistral OCR | Reconstrói a estrutura da tabela, que é onde os números moram |
| Segurança | Presidio, Llama Prompt Guard 2 e detector próprio | Camada determinística sempre ativa; as duas de aprendizado de máquina são opcionais |

---

## 🚀 Como executar

O projeto exige Python 3.12 e o [Ollama](https://ollama.com) ativo, que gera os embeddings das perguntas localmente e sem custo. A preparação do ambiente é a de sempre:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull bge-m3
cp .env.example .env
```

Para abrir no modo de demonstração, que não exige segredo nenhum configurado e consulta o painel contábil da CVM sem gerar custo:

```bash
streamlit run app_streamlit.py
```

Para habilitar também as perguntas livres, que acionam o modelo de linguagem sobre os releases, é preciso ter uma chave de API no `.env` e ligar o modo explicitamente. Ele vem desligado de propósito, para que uma instância exposta não gaste sem que alguém tenha decidido isso:

```bash
HABILITAR_PERGUNTAS_LIVRES=true streamlit run app_streamlit.py
```

Nos dois casos a interface abre em `http://localhost:8501`. Nenhuma chave está no código: elas vivem apenas no `.env` local, que o Git ignora, e o repositório versiona somente o `.env.example`, com todas as variáveis documentadas e os valores em branco.

---

## 📁 Organização do repositório

```text
├── app_streamlit.py          interface de chat
├── src/                      ingestão, indexação, recuperação, geração,
│                             dados estruturados, cobertura, segurança
├── conjunto_padrao/          45 perguntas congeladas + 10 de dev + 20 ataques
├── corpus/                   manifesto com SHA-256 e cache de OCR versionado
├── artefatos/                índices, painel DuckDB, logs por execução
├── resultados/               evidência datada de cada medição
├── tests/                    suíte automatizada, sem skips
└── docs/                     esta documentação
```

O corpus e os índices merecem uma observação. Os PDFs, o banco DuckDB e o índice vetorial não são versionados, porque são pesados e regeneráveis por script. O que entra no Git é o manifesto com o SHA-256 de cada documento e os metadados de construção do índice, o que permite verificar depois que o material usado numa medição é exatamente o mesmo que está descrito aqui.
