# Brief do anotador — conjunto adversarial de roteamento

Você vai **rotular 140 perguntas** em português segundo as regras da seção 3 abaixo. As
perguntas estão em `/home/ygor/Antigravity_Projects/fin-strategy-rag/artefatos/roteamento_adversarial/anotacao/itens_cegos_lote1.csv`, com ids neutros de `X001` a `X140`.

## Regras de isolamento — obrigatórias

- Leia **somente** este brief e o arquivo de itens. Não abra nenhum outro arquivo do
  repositório, não liste diretórios e não use busca (grep, glob, find). Em particular, não
  procure quem escreveu as perguntas, os rótulos que os autores pretendiam nem o trabalho
  de outro anotador: rotular sem vê-los é o único motivo de você existir.
- No relatório final, liste **todo arquivo que você abriu ou escreveu**.

## O que entregar

- Um CSV UTF-8 no padrão RFC 4180, gravado em: `/tmp/claude-1000/-home-ygor-Antigravity-Projects-fin-strategy-rag/61c92752-db87-4794-8fc7-fb61da70e6ea/scratchpad/anotacao_lote1/rotulos.csv`
- Cabeçalho exato, nesta ordem:
  `id_neutro,horizonte,clausula_horizonte,metrica,clausula_metrica,camada_apontada,clausula_camada,confianca`
- Uma linha por item, os 140, sem pular nenhum.
- Rótulos com os valores exatos das tabelas da seção 3.
- Cláusulas com os códigos da seção 3: `H1` a `H4`, `D-H1` a `D-H4`, `M1` a `M4`, `D-M`,
  `C1` a `C3`, `D-C1` a `D-C3`. Cite o código que **decidiu** o rótulo: se foi um
  desempate, cite o desempate.
- `confianca`: `alta` ou `baixa`.
- **Trabalhe de forma retomável:** grave o cabeçalho logo no início e acrescente as linhas
  em blocos de até 30 itens, salvando a cada bloco. Se o arquivo de saída já existir quando
  você começar, ele é trabalho anterior deste mesmo papel: confira-o e continue dele.

## Como rotular

- Rotule cada coluna de forma independente das outras.
- Leia a pergunta como a pessoa que a escreveu: decide o que se pede, não a presença de uma
  palavra.
- Não há cota por rótulo e as classes não precisam estar equilibradas.
- O relatório final **não pode conter o texto de nenhuma pergunta** — só contagens e ids.

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

---

Fim do brief.
