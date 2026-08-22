# Âncora IFRS do BTG 4T2025 — a célula que faltava no G4

Fecha a única célula **SEM ÂNCORA** do gate G4 (`resultados/gate_g4.md`,
2026-08-11). Não altera as duas células **DIVERGENTES** do Santander, que são
problema de outra natureza e seguem em aberto.

## O que impedia a leitura

`corpus/ifrs/raw/btg_ifrs_4T2025.pdf` (SHA-256 conferido contra
`corpus/ifrs/manifesto_ifrs.csv`) tem fonte embutida sem mapa de caracteres:
`pdfplumber` devolve `(cid:130)(cid:131)…` no lugar dos algarismos em todas as
71 páginas. O G4 registrou **ausência de evidência**, não zero — e deixou a
leitura pendente de uma decisão de orçamento (spec 5.20), não técnica.

A decisão custou **USD 0,032**: 8 páginas pelo endpoint síncrono da Mistral OCR,
a USD 0,004/página. O relatório original não trazia esse número; com ele, a
decisão deixou de ser uma escolha e virou aritmética.

## Como a página foi localizada sem pagar às cegas

Mandar as 71 páginas custaria USD 0,284 para ler uma. A página da demonstração
do resultado foi localizada por **geometria**, que sobrevive à fonte ilegível:
contando quantas palavras de cada página terminam na mesma borda direita
(±1 pt), as páginas 12 e 15–17 aparecem com 70–78% das palavras alinhadas em
colunas — assinatura de demonstração financeira, não de texto corrido. A faixa
11–18 cobriu o bloco inteiro.

A posição bate com a dos trimestrais legíveis do mesmo emissor, onde a DRE está
a ~18% do documento (pág. 8 de 47 no 3T2025; pág. 9 de 48 no 1T2026). Em 71
páginas, ~18% é a página 13 — que é exatamente onde ela estava.

## A leitura

`corpus/ifrs/ocr/ce5ff293…76f.json`, pág. 13, tabela
**Demonstração consolidada do resultado**, exercícios findos em 31/12/2025 e
31/12/2024, em R$ mil:

| linha | 31/12/2025 |
|---|---|
| Lucro líquido do exercício | 16.663.803 |
| Lucro líquido atribuível aos acionistas controladores | **16.005.964** |
| Lucro atribuível aos acionistas não controladores | 657.839 |

Identidade fecha ao milhar: 16.005.964 + 657.839 = 16.663.803.

O acumulado de nove meses vem do `btg_ifrs_3T2025.pdf`, legível, lido pelo mesmo
`scripts/ancora_ifrs.py` que ancora as demais células (pág. 8, coluna do
acumulado identificada pela identidade aritmética entre documentos, não por
posição).

## O 4T derivado — derivado contra derivado

O 4T não é publicado como período isolado; sai de `exercício − 9 meses`, a mesma
aritmética que o painel usa (RN10). O gate compara derivado com derivado.

| | consolidado | controladores | não controladores |
|---|---|---|---|
| exercício 2025 | 16.663.803 | 16.005.964 | 657.839 |
| 9 meses (3T2025) | 12.160.875 | 11.619.895 | 540.980 |
| **4T2025 derivado** | **4.502.928** | **4.386.069** | **116.859** |

Identidade fecha no derivado também: 4.386.069 + 116.859 = 4.502.928.

## Veredito da célula

| | valor |
|---|---|
| painel (`fatos_semanticos.lucro_liquido_controladores`, `cd_cvm=022616`) | 4.386.070.000 R$ |
| âncora IFRS derivada | 4.386.069.000 R$ |
| Δ | **+1.000 R$ — +0,00002%** |

**CONFERIDO.** A diferença é de mil reais em 4,4 bilhões: arredondamento ao
milhar entre a demonstração publicada e o valor carregado do arquivo da CVM,
não divergência de conceito.

Nota de resolução de entidade (RN11): filtrar por nome traz **duas** companhias
— `BCO BTG PACTUAL S.A.` (`022616`) e `BTG PACTUAL COMMODITIES SERTRADING`
(`027774`, valor zero). A âncora vale para a primeira, resolvida por `CD_CVM`
como a RN11 exige. Consulta por nome aqui devolveria duas linhas e é
exatamente o caso que a regra existe para impedir.

## Custo real, incluindo o desperdiçado

| execução | páginas | USD | resultado |
|---|---|---|---|
| 1ª (8–28) | 21 | 0,084 | **perdida** — `AttributeError` ao serializar, depois da chamada paga |
| 2ª (8–28) | 21 | 0,084 | relatório de auditoria, sem DRE |
| 3ª (29–45) | 17 | 0,068 | notas de política contábil; **sobrescreveu** a 2ª (cache endereçado por hash do PDF) |
| 4ª (11–18) | 8 | 0,032 | páginas certas, mas o merge descartava as tabelas |
| 5ª (11–18) | 8 | 0,032 | **DRE lida** |
| | **75** | **0,300** | |

Três defeitos do script foram pagos com chamada real e estão corrigidos em
`scripts/ocr_ancora_ifrs.py`, cada um com o comentário do motivo: gravação
movida para dentro do `try` (uma exceção entre pagar e gravar perde a resposta),
merge por página em vez de sobrescrita, e persistência das tabelas — que é onde
os números moram, já que o markdown da página traz apenas
`[tbl-3.html](tbl-3.html)`.

Teto de OCR: USD 8,00 configurado, USD 5,58 da passagem do corpus, USD 0,30
aqui — **restam USD 2,12**.
