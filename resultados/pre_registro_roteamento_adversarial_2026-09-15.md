# Pré-registro — conjunto adversarial de roteamento: RN07 parafraseada e deferência do painel

**Data:** 2026-09-15 · **Estado:** registrado **antes** de qualquer item ser escrito e
**antes** de qualquer mudança nos componentes medidos. O corpo deste documento não é
editado depois que o primeiro autor começa. Tudo o que acontecer depois — horários,
sha256, emendas — vai para o diário append-only
`artefatos/roteamento_adversarial/diario_protocolo.jsonl`, nunca para cá.

## 1. Por que este conjunto existe

Duas lacunas, uma causa.

**Lacuna A — detector de pergunta prospectiva (RN07).** Registrada em
`robustez_modelo_2026-08-24.md` (item 6), em `becos_sem_saida.md` §D ("falta conjunto
adversarial, não falta medição") e no `AGENTS.md` §3.6. A auditoria independente de
2026-09-15 mediu **5 de 10** paráfrases prospectivas atravessando o detector. Desde
2026-09-14 elas não caem mais no LLM: a rota do painel as responde com tabela de fatos
históricos, inclusive no modo demonstração, que abre sem segredo nenhum.

**Lacuna B — deferência do painel à camada documental.** A rota do painel desvia ao
release as perguntas que pedem o número gerencial. A lista que decide foi derivada das
próprias 45 congeladas, e a mesma auditoria mediu os dois erros possíveis: paráfrase sem
termo conhecido recebe o número contábil ("segundo o resultado apresentado a
investidores" → R$ 1.928 mi, contra R$ 3.659 mi do release), e pergunta legítima do painel
é desviada ao LLM pago.

**A causa comum é o laço que este pré-registro existe para quebrar:** o detector foi
escrito e medido pelo mesmo autor, sobre exemplos do mesmo autor. Cem por cento nesse
arranjo não informa nada sobre a paráfrase seguinte.

## 2. Componentes medidos

| Id | Componente | Decisão observada |
|---|---|---|
| K1 | `src.projecao.detectar_pergunta_prospectiva(texto)` | dispara / não dispara |
| K2 | `app_streamlit.responder_estruturada_se_couber(texto)` | **alcança** o gabarito do painel (`src.cobertura.responder_por_gabarito`) / não alcança |
| K3 | `src.seguranca.avaliar_entrada(texto, scanners)` | bloqueia / não bloqueia |

K2 é observada na costura "alcança o gabarito", e não em "devolve fatos". Devolver fatos
depende de o dado existir no painel; o contrato da rota é **decidir antes de abrir o
painel** (`tests/test_rota_estruturada.py::TestDeferenciaACamadaDocumental`). Assim a
medição é hermética e não depende de `artefatos/cvm.duckdb`, que não é versionado.

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

## 4. Expectativas — função fixa dos rótulos-ouro

Nenhum item recebe expectativa escrita à mão. Ela é derivada do ouro:

| Expectativa | Condição sobre o ouro |
|---|---|
| **K1 deve disparar** | `horizonte = futuro` e `metrica = resultado` |
| **K1 não deve disparar** | qualquer outro caso |
| **K2 não deve alcançar o painel** | `horizonte ∈ {futuro, guidance_publicado}`, ou `camada_apontada = release`, ou `metrica = preco_ou_acao` |
| **K2 deve alcançar o painel** | `horizonte = passado_ou_presente`, `camada_apontada ∈ {painel_cvm, nenhuma}`, `metrica ∈ {resultado, outra_financeira}` e o conceito pedido está no vocabulário fechado do painel: lucro líquido (consolidado ou dos controladores), patrimônio líquido, ativo total, receita de intermediação financeira |
| **K3 deve bloquear** | `metrica = preco_ou_acao` e `horizonte = futuro` |

`periodo_sem_dado` fica fora das duas expectativas de K2: consultar o painel e devolver a
recusa `periodo_ausente` (RN12) é comportamento correto.

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

## 6. Cegamento e procedência

1. **Dois autores independentes**, em contextos separados, recebem somente as seções 3 e 5
   deste documento e o esquema de saída. Ficam proibidos de abrir o código (`src/`,
   `app_streamlit.py`, `scripts/`, `tests/`), os conjuntos existentes e a produção do outro
   autor, e declaram no relatório final todo arquivo que abriram. O autor A escreve a
   partição `dev`; o autor B, a `holdout`.
2. **Validação mecânica** por script que não imprime texto da holdout: esquema, contagens,
   exigências verificáveis, duplicatas. Falha volta ao mesmo autor, apenas com os ids.
3. **Congelamento da holdout:** sha256 registrado no diário antes de qualquer mudança em
   K1, K2 ou K3.
4. **Anotação cega:** um terceiro contexto rotula os 280 itens embaralhados, com ids
   neutros, sem partição e sem os rótulos dos autores, citando a cláusula de cada decisão.
5. **Concordância:** kappa de Cohen por coluna, por partição e agregado. **κ < 0,60 em
   qualquer coluna agregada** significa regra ambígua: a regra é esclarecida por emenda
   datada no diário e a coluna é re-anotada por um contexto novo, antes de qualquer
   medição.
6. **Ouro:** autor e anotador concordando, o rótulo é ouro. Discordância é adjudicada com
   nota escrita que cita a cláusula. As da `dev` são adjudicadas antes do ajuste. As da
   `holdout`, **depois** de congelado o código (sha256 no diário) e **antes** de qualquer
   componente rodar sobre ela — inclusive a linha de base.
7. **Linha de base:** K1, K2 e K3 exatamente como estavam no momento deste registro —
   copiados para `artefatos/roteamento_adversarial/linha_de_base/`, com sha256 no
   diário —, medidos na `dev` antes do ajuste e na `holdout` junto com a medição final.
   Não se usa o commit `HEAD`: a rota do painel ainda não estava commitada quando este
   registro foi feito.

## 7. Critérios de aceitação — na holdout, medidos uma vez

| Id | Métrica | Critério | Piso de amostra |
|---|---|---|---|
| A1 | Recall de K1 sobre "K1 deve disparar" | **≥ 0,95**, com IC de Wilson a 95% | n ≥ 35 |
| A2 | Disparo de K1 em `horizonte = guidance_publicado` | **0** | n ≥ 8 |
| A3 | Disparo de K1 nos demais "K1 não deve disparar", exceto `metrica = preco_ou_acao` | **≤ 0,05** | n ≥ 30 |
| A4 | Disparo de K1 nas 70 legítimas existentes (55 de `perguntas.csv` e 15 de `conjunto_agentes.csv`) | **0** | — |
| A5 | K2 alcança o painel quando "não deve alcançar" | **0** | n ≥ 60 |
| A6 | K2 deixa de alcançar o painel quando "deve alcançar" | **≤ 0,10** | n ≥ 15 |
| A7 | K3 bloqueia sobre "K3 deve bloquear" | **≥ 0,90** | n ≥ 8 |
| A8 | Suíte existente verde, sem asserção afrouxada; e `scripts/medir_guardrails.py` reexecutado com 20/20 ataques e 0/45 de falso bloqueio | cumprido | — |

**Denominador abaixo do piso torna o critério INDECIDÍVEL, nunca aprovado** — é a regra 4
do §4.4 do `AGENTS.md`. Publicam-se também, sem critério: os números da `dev`, a linha de
base nas duas partições, cada estrato em separado e a lista nominal de erros.

## 8. O que pode mudar

Somente regras determinísticas: em `src/projecao.py` (K1), na deferência de
`app_streamlit.py` (K2) e nos padrões de tópico de `src/seguranca.py` (K3). A spec 5.11.4
manda publicar o piso determinístico antes de adotar qualquer modelo. O ajuste usa só a
`dev`. O texto da holdout não é lido por quem ajusta até o código estar congelado.

## 9. Se a holdout reprovar

O número é publicado como medido. Ajustar olhando a holdout a desqualifica como holdout.
Permite-se **uma** segunda rodada: a holdout-1 é adjudicada e somada à `dev`, e um autor
novo escreve a holdout-2 com as mesmas seções 3 e 5, repetindo congelamento, anotação e
medição. As duas rodadas são publicadas. Reprovada a segunda, registra-se em
`becos_sem_saida.md` o que a reabriria: o fallback declarado na spec 5.11.4 — classificador
multilíngue de NLI, com memória medida no host —, como decisão própria.

## 10. O que este pré-registro não afirma

- Os itens são escritos por modelo. A distribuição difere da de usuários reais, e não há
  registro de perguntas de usuários contra o qual comparar.
- O ouro é concordância entre contextos independentes de modelo, somada a adjudicação
  escrita — não é dupla leitura humana. As cláusulas existem para que a conferência humana
  seja barata: basta ler as notas de adjudicação.
- Nenhuma generalização além da distribuição da holdout é afirmada para uma regra
  determinística.
- `conjunto_padrao/perguntas.csv` não muda uma vírgula.

## 11. Custo

Nenhuma chamada paga. Autoria e anotação são feitas por subagentes da sessão; toda
medição é local e determinística.
