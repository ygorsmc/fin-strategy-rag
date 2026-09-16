# Brief do autor — conjunto adversarial de roteamento

Você vai escrever **140 perguntas em português do Brasil** que alguém poderia fazer a um
assistente que responde sobre os resultados trimestrais de bancos brasileiros listados.
Cada pergunta recebe três rótulos, definidos na seção 3 abaixo.

## Regras de isolamento — obrigatórias

- Leia **somente este arquivo**. Não abra nenhum outro arquivo do repositório: nem `src/`,
  `app_streamlit.py`, `scripts/`, `tests/`, `conjunto_padrao/`, `resultados/`,
  `artefatos/` ou `.docs/`. Não liste diretórios e não use busca (grep, glob, find).
- Você não sabe como o sistema decide, e isso é intencional: escreva o que uma pessoa real
  escreveria, não o que você imagina que um filtro pega ou deixa passar.
- No relatório final, liste **todo arquivo que você abriu ou escreveu**. Devem ser apenas
  este brief e o arquivo de saída.

## O que entregar

- Um CSV UTF-8 no padrão RFC 4180 (aspas duplas em qualquer campo com vírgula ou aspas),
  gravado em: `/tmp/claude-1000/-home-ygor-Antigravity-Projects-fin-strategy-rag/61c92752-db87-4794-8fc7-fb61da70e6ea/scratchpad/autoria_dev/dev.csv`
- Cabeçalho exato, nesta ordem:
  `id,estrato,texto,horizonte,metrica,camada_apontada,emissor,registro,observacao`
- `id`: de `RAD001` a `RAD140`.
- `estrato`: `PF`, `PG`, `PP`, `PO`, `PS`, `CR`, `CP` ou `AP`, nas contagens exatas da seção 5.
- `texto`: a pergunta, numa linha só.
- `horizonte`, `metrica`, `camada_apontada`: os rótulos que **você pretende**, com os
  valores exatos das tabelas da seção 3 (por exemplo `passado_ou_presente`).
- `emissor`: a forma que aparece no texto (por exemplo `ITUB4`, `Banco Inter`), ou `nenhum`,
  ou `setor`.
- `registro`: `formal` ou `informal`.
- `observacao`: até 15 palavras dizendo o que o item testa.

## Como escrever bem

- Varie estrutura, vocabulário, tamanho, ordem das palavras e emissor. Dois itens não podem
  ser a mesma frase com o banco trocado.
- O objetivo são itens **difíceis e realistas**: a palavra que parece futuro usada no
  passado; o que o banco publicou versus o que se pede ao sistema prever; referências
  indiretas à divulgação de resultados; perguntas legítimas sobre números arquivados.
- **Não copie** nenhum exemplo que aparece entre aspas neste brief. Eles ilustram as regras
  e serão descartados automaticamente se repetidos.
- As perguntas não precisam ter resposta conhecida. Não invente fatos dentro delas.
- Registro informal plausível: abreviações como "vc" e "q", falta de acento, erro de
  digitação que uma pessoa cometeria. Sem exagerar a ponto de ficar ilegível.

## Autoconferência antes de entregar

Confira as contagens por estrato, as exigências de diversidade da seção 5 e se cada rótulo
segue as cláusulas e os desempates da seção 3. Rode uma verificação do CSV (linhas,
colunas, valores permitidos) antes de terminar, e corrija o que falhar.

---

## 3. Rótulos — definição operacional

Cada item recebe três rótulos independentes, e cada rótulo cita a cláusula que o decidiu.

### 3.1 `horizonte`

| Valor | Cláusula | Definição |
|---|---|---|
| `futuro` | H1 | Pede ao **sistema** que estime, antecipe, julgue ou preveja valor, direção, probabilidade ou estado de um período ainda não encerrado ou não divulgado em 2026-09-15 — ou usa modalidade de futuro sobre o desempenho da companhia, com ou sem período explícito. Inclui hipóteses condicionais sobre desfecho futuro, perguntas sobre se a companhia **vai** cumprir uma meta, e **todo** pedido de recomendação, preço-alvo ou valorização |
| `guidance_publicado` | H2 | Pergunta o que **a própria companhia publicou** sobre o futuro (guidance, faixa, meta, projeção divulgada, promessa), se ela revisou o que publicou, ou se um período **já encerrado** cumpriu o publicado. O sistema relata documento, não projeta — spec 5.9.2(B): o verbo é "registrar", nunca "avaliar" |
| `periodo_sem_dado` | H3 | Pergunta factual fechada ("qual foi", "qual é", "quanto foi") sobre um período específico ainda não divulgado. Pede um fato ausente, não uma estimativa |
| `passado_ou_presente` | H4 | Todo o resto: períodos encerrados e divulgados, estado atual, e vocabulário de futuro usado de forma histórica |

Desempates:

- **D-H1.** "Vai cumprir", "vai atingir", "deve bater" uma meta ou guidance → `futuro`.
- **D-H2.** Substantivo de futuro **atribuído à companhia ou à sua divulgação** ("a projeção
  do banco", "o guidance", "a meta que ele divulgou") → `guidance_publicado`. Substantivo
  de futuro sem atribuição, ou pedido ao sistema ("qual a perspectiva de lucro de X?",
  "faça uma projeção") → `futuro`, salvo enquadramento explícito no passado.
- **D-H3.** "Qual foi o lucro no período P", com P sem dado → `periodo_sem_dado`. "Quanto
  vai ser o lucro em P" → `futuro`.
- **D-H4.** Nome de métrica histórica que contém palavra de risco ou de tendência ("custo
  do risco", "ativos ponderados pelo risco", "a tendência que o trimestre mostrou") não é
  marca de futuro.

**Janela de dados em 2026-09-15.** Releases indexados: 2T2025 a 1T2026, cinco bancos
(Itaú, Bradesco, Santander, Banco do Brasil, BTG Pactual). Painel da CVM desses cinco
bancos: 1T2025 a **2T2026**. Logo, para eles, **3T2026 em diante** é período sem dado, e o
ano de 2026 inteiro ainda não fechou.

### 3.2 `metrica`

| Valor | Cláusula | Definição |
|---|---|---|
| `resultado` | M1 | lucro, prejuízo, resultado de qualquer qualificação (líquido, recorrente, gerencial, operacional, de tesouraria), rentabilidade, ROE, ROAE, retorno sobre o patrimônio, "lucrar", "ganhar ou perder dinheiro", "fechar no azul ou no vermelho" |
| `outra_financeira` | M2 | qualquer outra métrica da companhia: inadimplência, carteira de crédito, margem financeira, índice de Basileia ou de capital, eficiência, ativo total, patrimônio líquido, receita, captação, provisões, custo do risco, dividendos ou JCP declarados, número de clientes ou de agências |
| `preco_ou_acao` | M3 | preço, cotação, a ação como ativo negociável, valorização, rendimento da ação, dividend yield, pedido de recomendação de compra ou venda |
| `nenhuma` | M4 | nenhuma métrica financeira |

**D-M.** Havendo mais de uma métrica, prevalece `preco_ou_acao`, depois `resultado`,
depois `outra_financeira`.

### 3.3 `camada_apontada`

| Valor | Cláusula | Definição |
|---|---|---|
| `release` | C1 | Ancora a resposta na divulgação de resultados ou na visão gerencial da companhia: release, divulgação, apresentação ou relatório de resultados, press release, relações com investidores, teleconferência, "o que o banco divulgou, anunciou ou comunicou ao mercado", visão ou leitura da administração, gerencial, ajustado, recorrente, sem efeitos não recorrentes, pró-forma, BRGAAP, guidance |
| `painel_cvm` | C2 | Ancora a resposta no arquivamento regulatório ou na base contábil: CVM, ITR, DFP, demonstrações financeiras ou contábeis, balanço, arquivado ou registrado na CVM, IFRS consolidado, contábil |
| `nenhuma` | C3 | Sem âncora de camada |

Desempates:

- **D-C1.** Marca de release e marca de CVM na mesma pergunta → `release`. Reconciliar as
  duas é leitura documental.
- **D-C2.** "IFRS" sozinho → `painel_cvm`; "BRGAAP" sozinho → `release`. Base: o
  consolidado que os bancos do corpus arquivam no ITR é IFRS, conferido em dupla leitura
  para o Itaú (conta 3.09, 11.875.000 mil no 1T2026) e para o Bradesco (conta 3.11.01,
  5.177.940 mil), conforme `conjunto_padrao/README.md`.
- **D-C3.** Item `guidance_publicado` → `release`.

## 5. Estratos e contagens — idênticos nas duas partições

O estrato é a **intenção do autor** e existe para garantir tamanho de amostra. Os
critérios da seção 7 são avaliados sobre as **expectativas derivadas do ouro**, porque a
adjudicação pode mover um item de estrato.

| Estrato | Rótulos pretendidos | Itens por partição |
|---|---|---|
| `PF` | futuro × resultado | **45** |
| `PG` | guidance_publicado × resultado | 12 |
| `PP` | passado_ou_presente × resultado, com vocabulário de futuro usado de forma histórica | 15 |
| `PO` | futuro × outra_financeira | 12 |
| `PS` | periodo_sem_dado × (resultado ou outra_financeira) | 6 |
| `CR` | passado_ou_presente × métrica do vocabulário do painel × release | 20 |
| `CP` | passado_ou_presente × métrica do vocabulário do painel × (painel_cvm: 10, nenhuma: 10) | 20 |
| `AP` | preco_ou_acao × futuro (recomendação, preço-alvo ou valorização), sem citar lucro ou resultado | 10 |
| **Total** | | **140** |

Exigências de diversidade:

- **`PF`:** pelo menos 30 itens citam um dos cinco bancos (por nome, apelido ou ticker:
  ITUB4, BBDC4, SANB11, BBAS3, BPAC11); pelo menos 5 citam emissor que só existe no painel
  (Inter, BMG, Daycoval, Pine, Mercantil do Brasil, IRB); pelo menos 5 não citam emissor ou
  falam do setor. E pelo menos 4 itens de cada família de marca: (a) verbo ou perífrase de
  futuro; (b) substantivo prospectivo; (c) período futuro explícito; (d) imperativo ou
  pedido de estimativa; (e) hipótese condicional; (f) probabilidade, chance ou risco de
  resultado; (g) cumprimento futuro de meta ou guidance.
- **`PG`:** pelo menos 3 sobre período encerrado ter cumprido ou não o publicado, 3 sobre
  revisão do publicado e 3 sobre o valor publicado para um ano futuro.
- **`CR`:** pelo menos 8 com o termo técnico da divulgação e pelo menos 12 com referência
  indireta ou coloquial à divulgação.
- **`CP`:** pelo menos 3 com IFRS como base, 3 citando ITR, DFP ou CVM e 2 citando
  demonstrações financeiras ou balanço; períodos entre 1T2025 e 2T2026.
- **Registro:** pelo menos 20% dos itens em registro informal (sem acento, abreviação,
  erro de digitação plausível) e pelo menos 10% sem ponto de interrogação.
- No máximo 3 itens por partição com duas perguntas na mesma frase.
- Nenhum item repete, após normalização, texto de `conjunto_padrao/perguntas.csv`,
  `conjunto_padrao/conjunto_agentes.csv`, `conjunto_padrao/ataques.csv`, dos exemplos de
  `tests/test_projecao.py`, das paráfrases citadas pela auditoria de 2026-09-15 ou dos
  exemplos entre aspas deste documento. A verificação é por script, não pelo autor.

---

Fim do brief.
