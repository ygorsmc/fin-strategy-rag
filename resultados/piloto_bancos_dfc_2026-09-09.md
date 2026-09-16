# Piloto documental B-DFC-01J — resultado

**Data:** 2026-09-09. **Custo:** zero (nenhuma rede, nenhuma chamada paga).
Plano executado: [`plano_piloto_bancos_dfc_2026-09-09.md`](plano_piloto_bancos_dfc_2026-09-09.md).
Contrato financeiro: [`debate_bancos_dfc_2026-09-09.md`](debate_bancos_dfc_2026-09-09.md) §§3 e 6.
Código: `scripts/piloto_bancos_dfc.py` · testes: `tests/test_piloto_bancos_dfc.py`
(63 casos) · artefatos: `artefatos/b_dfc_01j/`.
**Atualizado em 2026-09-09 após a recuperação dos arquivamentos originais de
Itaú e Bradesco pelo catálogo IPE da CVM** — ver §11, que mudou o resultado
principal e destravou o gate P3.
**Revisado** por `auditor-conformidade` (somente leitura); os defeitos que ela
encontrou estão corrigidos e listados na §10.

> **⚠️ RETRATAÇÃO ATUALIZADA OUTRA VEZ (2026-09-11).** A retratação logo abaixo,
> de 10/09, **também deixou de valer** — ela apresenta "os 15 mapeáveis são
> **todos** intervalo" e larguras de 3,9%–6,3% (Bradesco) e 16,5%–40,7% (Itaú)
> como resultado vigente. **Não são.** A
> [revisão independente](revisao_independente_b_dfc_01j_2026-09-10.md) mostrou
> que esses limites eram **fabricados** (achado F1): o residual líquido de uma
> rubrica que mistura juros e câmbio não limita a parcela de juros, porque
> câmbio tem os dois sinais e pode compensar juros.
>
> **Estado vigente, medido no artefato** (`artefatos/b_dfc_01j/auditoria.json`):
>
> | | |
> |---|---:|
> | Pacotes no escopo | 25 |
> | J identificado (ponto) | **0** |
> | J limitado (intervalo) | **0** — era 15 |
> | J não identificado | **24** |
> | Sem fonte | 1 |
>
> As larguras citadas abaixo ficam como **registro do que foi publicado**, não
> como medição. Trilha: [correção do instrumento](correcao_instrumento_b_dfc_01j_2026-09-10.md)
> → [parecer](parecer_correcao_b_dfc_01j_2026-09-11.md) →
> [implementação C1–C6](implementacao_c1_c6_b_dfc_01j_2026-09-11.md).

> **⚠️ RETRATAÇÃO ATUALIZADA (2026-09-10).** A retratação abaixo dizia que
> "nenhum número deste relatório muda". **Isso deixou de valer.** A leitura das
> notas explicativas mostrou que a parcela cambial dessas rubricas **não é
> separável** e elas passaram a NÃO IDENTIFICADAS. Consequência medida:
> **J como PONTO exato foi de 5 para ZERO** e o Bradesco passou a intervalo de
> **3,9% a 6,3%**; o Itaú, de **16,5% a 40,7%**. Os 25 pacotes seguem 24 com
> fonte e 9 sem J; o que mudou é que os 15 mapeáveis são **todos** intervalo.
> Evidência e magnitude:
> [`prontidao_b_dfc_01j_modelo_2026-09-09.md`](prontidao_b_dfc_01j_modelo_2026-09-09.md) §2-bis.

> **⚠️ RETRATAÇÃO PARCIAL (2026-09-09, mesma data, onda posterior).** A
> tentativa de construir um alvo de ML sobre esta série descobriu que **três
> das rubricas incluídas em J vêm CREDORAS em alguns trimestres** — duas
> impressas pelo próprio emissor. Despesa de captação por competência não é
> crédito: essas linhas embutem algo que o contrato exclui (câmbio, valor
> justo) ou são reclassificação. **Nenhum número deste relatório muda e a
> aritmética continua conferindo**; o que não se sustenta é a afirmação de que
> o J aqui somado é **o J do contrato** para Itaú e Bradesco. Dentro da janela
> congelada (2024T1–2025T1) nenhum crédito aparece, mas a dúvida é da rubrica,
> não do trimestre. É a armadilha do BTG outra vez, no emissor que este
> relatório tratou como melhor caso. Escopo, evidência e o que fecharia:
> [`prontidao_b_dfc_01j_modelo_2026-09-09.md`](prontidao_b_dfc_01j_modelo_2026-09-09.md) §2.

## 1. Resultado em uma frase

**J é reconstruível em 15 dos 25 pacotes — como PONTO exato nos 5 do Bradesco
e como intervalo de 0,02%–0,67% nos 5 do Itaú e nos 5 do Banco do Brasil; em
10 pacotes J não é identificável**, por razões documentadas e distintas: o
Santander publica agregado que mistura componente atuarial, o BTG publica
resultado líquido por instrumento em vez de juros por competência, e um pacote
do BTG carece de curadoria própria no documento anual.

**E 10 desses 15 têm disponibilidade histórica certificada** (P3), porque vêm
do arquivamento **original** de cada trimestre, recuperado do catálogo IPE da
CVM com protocolo, versão e data de entrega — não de coluna comparativa
reapresentada.

## 2. Matriz cinco bancos × cinco trimestres

`limitado` = parcelas do contrato identificadas, com residual declarado.
`não ident.` = J não separável. `sem fonte` = nenhuma fonte declarada cobre o
período.

`identificado` = J é ponto exato. `limitado` = intervalo com residual
declarado. `não ident.` = J não separável. **P3** marca disponibilidade
histórica certificada.

| Emissor | 2024T1 | 2024T2 | 2024T3 | 2024T4 | 2025T1 | P3 |
|---|---|---|---|---|---|---|
| **Bradesco** (`000906`) | identificado | identificado | identificado | identificado¹ | identificado | **5/5** |
| **Itaú Unibanco** (`019348`) | limitado | limitado² | limitado | limitado¹ | limitado | **5/5** |
| **Banco do Brasil** (`001023`) | limitado | limitado | limitado | limitado³ | limitado | 0/5 |
| **Santander** (`020532`) | não ident. | não ident. | não ident. | não ident.³ | não ident. | 0/5 |
| **BTG Pactual** (`022616`) | não ident. | não ident. | não ident. | sem fonte⁴ | não ident. | 0/5 |

¹ Derivado `2024A − 2024M9` com **os dois operandos originais** — estava
calculável na data de entrega do anual, logo é point-in-time.
² Há duas versões (entregas 2024-08-06 e 2024-08-07). Ambas foram lidas e
**J não mudou** entre elas.
³ Derivado de colunas comparativas: não certifica histórico.
⁴ O anual do BTG **está legível** pelo cache de OCR, mas as rubricas da nota 21
não aparecem sob os mesmos rótulos: falta curadoria própria, não acesso.

### J do Banco do Brasil, em R$ mil

| Período | Limite inferior | Limite superior | Largura | Total impresso |
|---|---:|---:|---:|---:|
| 2024T1 | 40.734.518 | 40.956.417 | 0,54% | 40.956.417 |
| 2024T2 | 40.837.496 | 41.023.068 | 0,45% | 41.023.068 |
| 2024T3 | 42.191.395 | 42.433.360 | 0,57% | 42.433.360 |
| 2024T4 | 44.330.839 | 44.577.982 | 0,55% | 44.577.982 |
| 2025T1 | 47.629.112 | 47.952.209 | 0,67% | 47.952.209 |

O limite inferior soma as três rubricas do contrato — recursos de clientes,
recursos de instituições financeiras e emissões de títulos. O superior
acrescenta "Outras despesas de juros", que a nota **não abre**. A soma das
quatro fecha **exatamente** no total impresso em todos os cinco períodos, sem
tolerância escolhida.

## 3. Cobertura em números separados

| | |
|---|---:|
| Pacotes no escopo | **25** |
| Pacotes com fonte IFRS declarada | **24** |
| Pacotes sem fonte declarada | **1** |
| Pacotes com J identificado como **ponto** | **5** |
| Pacotes com J limitado (intervalo) | **10** |
| Pacotes com J não identificado | **9** |
| Pacotes com fechamento aritmético conferido (P2) | **15** |
| Pacotes com **P3 (histórico) conferido** | **10** |
| Emissores sem nenhum documento | **0** |
| Componentes de DFC classificados | **2** |
| Fatos extraídos com procedência | **409** |
| Arquivamentos CVM inventariados (25 pacotes, 8 multiversão) | **40** |

**Cobertura documental não é tamanho de amostra.** Cinco pacotes de um único
emissor não sustentam nenhuma afirmação de poder estatístico, e o piloto não a
faz.

## 4. Três achados que mudam o que se pode afirmar

### 4.1 O BTG: uma soma que fecha num período e falha no anterior

A nota 21 do BTG traz duas decomposições do **mesmo total** — uma por
instrumento (captação, depósitos, aceites, empréstimos) e outra por natureza
(receitas de juros, despesas de juros, mensuração a valor justo). Elas não são
pai e filhas.

| Período | Soma das 4 linhas por instrumento | "Despesas de juros" | Diferença |
|---|---:|---:|---:|
| 2025T1 | 14.052.043 | 14.052.043 | **0** |
| 2024T1 | 10.098.636 | 3.549.360 | **6.549.276** |

Ter conferido só 2025T1 teria produzido J plausível e errado: as linhas por
instrumento são **resultado líquido**, que embute mensuração a valor justo —
exatamente o que o contrato exclui. É a aplicação literal da regra do plano
(*"uma soma fechar aritmeticamente não prova semântica correta"*), e foi a
curadoria inicial deste piloto que errou e teve de ser corrigida.

### 4.2 O Santander: a mistura atuarial está escrita, mas sem valor

A nota de obrigações para fundos de pensão diz, textualmente, que os planos de
benefício definido *"são reconhecidos na demonstração consolidada do resultado
nas linhas de **Despesas com juros e similares** e Provisões (líquidas)"*
(p. 14 do IFRS 1T2025). O contrato exclui componentes atuariais, e a informação
é **qualitativa** — não há montante a subtrair. Mistura não separável significa
J não identificado; estimar a exclusão é proibido.

A mesma demonstração dá, em separado, os juros dos Instrumentos de Dívida
Elegíveis a Capital (Nível I 258.134 e Nível II 531.061 no 2025T1, p. 28), mas
isso é uma fração do agregado e não fecha composição nenhuma.

### 4.3 O painel CVM não substitui as notas

> **Correção de 2026-09-09.** Uma versão anterior deste parágrafo afirmava que
> o painel traz "apenas `3.02.01 Despesa de Juros` como linha única, idêntica à
> conta-pai". **A afirmação era falsa** e foi generalizada de um único
> emissor-trimestre (BB, 2024T1). A revisão de conformidade a derrubou.

O painel tem, para os cinco bancos, **17 descrições distintas sob `3.02.01`** —
de "Despesas com Juros e Similares" a "Perdas esperadas decorrentes de risco de
crédito" e "Ganhos / (Perdas) Líquidos de Operações de Câmbio" — além de
`3.02.02`–`3.02.04` igualmente heterogêneas. Isso é a **demonstração viva da
RN09**: `cd_conta` não é chave de significado, e o mesmo código carrega
conceitos incompatíveis conforme o emissor.

O que continua valendo, e agora pelo motivo certo: **nenhuma dessas descrições
decompõe juros de captação por instrumento** — não há "Recursos de clientes",
"Depósitos" ou "Títulos emitidos" como rubrica de despesa de juros no painel.
A composição de J vive nas notas explicativas, que só existem em PDF.

## 5. Contraprovas executadas

- **Duas identidades documentais do BB reproduzidas** (caso do plano §5.2):
  `864.972.382 − 873.710.691 = −8.738.309` (recursos de clientes) e
  `749.565.355 − 724.024.327 = 25.541.028` (instituições financeiras). Resíduo
  **zero** nas duas. As linhas correspondentes da DFC **repetem a diferença de
  estoques do balanço** e são classificadas como redundantes. Isso é contraprova
  ao argumento de que qualquer linha da DFC já traz informação nova — não prova
  que a DFC inteira seja redundante.
- **Consistência entre três documentos independentes.** Os trimestres isolados
  de 2024 vêm de três PDFs diferentes (1T2025, 2T2025, 3T2025) e somam
  **exatamente** o acumulado de nove meses impresso no 3T2025:
  `40.956.417 + 41.023.068 + 42.433.360 = 124.412.845`. Se uma coluna estivesse
  mapeada errado, não fecharia. É o teste que valida o mapeamento de colunas.

## 6. O que NÃO foi demonstrado

- **Nenhuma disponibilidade histórica (P3 = 0 de 25).** Todos os valores de
  2024 são **coluna comparativa em documento de 2025**: identificação
  *as-restated*, não o que um analista conhecia em 2024. Nenhum documento traz
  data de publicação original — o manifesto registra a data de *download*
  (2026-08-11), e preenchê-la como publicação seria inventar.
- **Nenhuma comparação entre juros pagos (DFC) e J.** Exigiria escopos
  reconciliados; o piloto não os reconciliou e não construiu proxy de estresse
  a partir de resíduo.
- **Nenhuma recuperação em rede.** Itaú, Bradesco e os arquivamentos originais
  de 2024 dependem dela. Timeout e ausência local são **falha de acesso**, não
  prova de inexistência histórica.
- **Nenhuma revisão independente.** Entregue com `revisao_pendente`.

## 7. Inventário de lacunas

| Lacuna | Tarefa para resolver | Autoridade/custo |
|---|---|---|
| Itaú e Bradesco sem IFRS local | Verificar se publicam IFRS **trimestral** ou só anual (Res. CMN 4.818 exige anual); baixar de RI | rede; gratuito |
| 2024T1–2024T4 originais | Recuperar por ID no `rad.cvm.gov.br` e certificar identidade/versão **dentro** do conteúdo | rede; tentativas anteriores deram timeout |
| BTG anual (2024T4) | O cache de OCR já está legível; as rubricas da nota 21 não aparecem sob os mesmos rótulos — exige curadoria própria | zero; só código |
| "Outras despesas de juros" do BB | Só fecharia com composição que a nota não fornece | pode não existir |
| Data de publicação original | Catálogo IPE da CVM traz `Data_Entrega` e `Versao` | zero; consulta |
| Revisão independente | `auditor-conformidade` + conferência semântica separada | zero |

## 8. Reprodução

```bash
python -m scripts.piloto_bancos_dfc auditar        # offline, determinístico
python -m pytest tests/test_piloto_bancos_dfc.py   # 45 casos
```

Recuperação (Onda 2): 11 documentos do catálogo IPE, todos validados por
estrutura de PDF completa e conferidos por SHA-256 antes de cada leitura.

Inventário da Onda 1 (`inventariar --painel artefatos/cvm_treino.duckdb`):
25 pacotes, **40 arquivamentos**, 8 multiversão — o painel abre somente-leitura
e seu SHA-256 continua `c1a6044…`, o mesmo do plano §5.1.

Suíte completa na execução: **1.859 passed, zero skip**
(`CREWAI_STORAGE_DIR` em diretório temporário gravável).
`execucao.json` registra `rede_utilizada=false`, `custo_efetivo_usd=0.0` e
`holdout_acessado=false` — este último **verificado** contra os caminhos
efetivamente abertos, não declarado por conveniência.

## 9. Recomendação

**A lacuna de acesso está fechada e o piloto está documentalmente concluído.**
J é reconstruível com procedência em 3 dos 5 emissores, e em 2 deles com
disponibilidade histórica certificada. Isso é base suficiente para **discutir**
o pré-registro de regressão do §12 do plano — não para dispensá-lo.

O que decide a próxima onda, em ordem:

1. **Ampliar a janela**, que é o gargalo real agora: 5 trimestres × 3 emissores
   com J utilizável não sustentam poder estatístico nenhum. O IPE cobre anos
   anteriores e o mesmo código já lê as notas — é custo de coleta, não de método.
2. **Curar o anual do BTG** (custo zero) e decidir o que fazer com Santander,
   cujo agregado é irrecuperável sem composição que o emissor não publica.
3. **Só então** o pré-registro, com materialidade, poder e baselines definidos
   antes de qualquer medição.

**Não** ler este piloto como "modelo validado" nem como "DFC sem valor". Ele
mede identificabilidade documental, e só isso. Nenhum gate aqui autoriza treino:
15 pacotes de 3 emissores em 5 trimestres é evidência de que o dado **existe**,
não de que um modelo seja possível.

## 10. Defeitos encontrados pela revisão de conformidade e corrigidos

A revisão (`auditor-conformidade`, somente leitura) verificou limpo o escopo do
holdout, a não-mutação de painéis/corpora e a ausência de afirmação de
disponibilidade histórica. Encontrou sete defeitos reais, todos corrigidos
nesta mesma onda, com teste de regressão:

| # | Defeito | Correção |
|---|---|---|
| 1 | **"Sem fonte" era falso em 4 pacotes.** Os PDFs IFRS do Santander 2T/3T/4T2025 estavam em disco e não foram declarados; o relatório dizia que o período dependia de rede | Fontes declaradas; Santander passou a ter os 5 períodos. Cobertura corrigida de 11/14 para **14/11** |
| 2 | **`abs` parcela a parcela**, proibido pelo plano §8.1: uma reversão viraria despesa e inflaria J, invisível onde não há total para conferir | Soma preserva o sinal; a convenção troca **uma vez** no agregado e é declarada em `convencao_de_sinal` |
| 3 | **Destino de saída sem guarda:** `--diretorio corpus/holdout_2T2026` gravaria dentro do reservado | `verificar_destino_isolado` restringe a escrita a `artefatos/b_dfc_01j` |
| 4 | **Hash calculado e nunca comparado** — PDF trocado daria extração de outro documento com `P0=CONFERIDO` | Divergência levanta `ErroExtracao` |
| 5 | **Afirmação falsa sobre o painel CVM** (§4.3), generalizada de um emissor-trimestre | Reescrita com a medição real: 17 descrições sob `3.02.01` |
| 6 | **DFC lia a coluna 0 sem conferir a contagem**, ao contrário da extração de notas | Mesma guarda de contagem; datas dos saldos gravadas |
| 7 | **`inventariar` era idêntico a `auditar`** — a Onda 1 contra `documentos` não existia | Implementada: 25 pacotes, 40 arquivamentos, 8 multiversão, em `inventario_cvm.jsonl` |

O defeito 2 merece registro à parte: **ele não teria aparecido nos dados
usados**, porque nenhuma parcela do BB é credora. Foi encontrado por leitura de
contrato, não por medição — e é exatamente o tipo de erro que só se manifesta
quando o universo cresce.

A guarda de contagem de colunas provou seu valor sozinha: ao declarar o anual
do Santander, ela recusou a extração porque a **referência da nota** ("32") era
lida como valor. Sem ela, todas as colunas teriam deslizado uma casa e 2024
receberia o número de 2023, em silêncio.

## 11. A recuperação de Itaú e Bradesco (2026-09-09)

O piloto havia declarado esses dois emissores como lacuna de acesso. Foram
recuperados **11 documentos** pelo caminho autoritativo, e o resultado do
piloto mudou por completo.

### 11.1 O caminho: catálogo IPE da CVM, não site de RI

A central de resultados do Itaú devolve **HTTP 403** a requisição
programática. O caminho que funcionou é melhor de qualquer forma: o catálogo
**IPE** (`dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE`) lista cada documento
entregue à CVM com `Link_Download`, `Protocolo_Entrega`, `Versao` e —
decisivo — **`Data_Entrega`**.

Site de RI dá o arquivo. O IPE dá o arquivo **com a data em que ele passou a
existir publicamente**, ligada a um protocolo. É a diferença entre "tenho o
documento" e "sei o que se conhecia naquela data", e é ela que destrava P3.

**Os dois emissores publicam IFRS trimestral**, ao contrário do que o
relatório supunha ao chamá-los de lacuna: a CMN 4.818/2020 obriga a peça
separada, e ela existe para todos os cinco trimestres.

### 11.2 Duas armadilhas na coleta, ambas pegas

**Truncamento silencioso.** A primeira tentativa devolveu `HTTP 200`,
`Content-disposition: …pdf` e um arquivo que **começa com `%PDF-1.7`** — e
estava incompleto: 1,78 MB contra 2,41 MB, sem `%%EOF` e sem trailer. O
servidor usa `Transfer-Encoding: chunked`, então não há `Content-Length` para
conferir, e não honra `Range`. **Só a validação estrutural do PDF detecta.**
Aceitar o arquivo teria produzido extração de um documento pela metade, com
todos os gates verdes.

**Escala.** O Itaú publica em **milhões de reais**; os outros quatro bancos em
milhares. Tratar tudo como milhares erraria por mil vezes — é a troca
`MIL`↔`UNIDADE` que invalidou a rodada A do CAND-04 (§3.11). A unidade passou
a ser declarada por fonte, com multiplicador próprio.

### 11.3 O Bradesco entrega J como ponto, não como intervalo

A nota do Bradesco é a mais completa dos cinco bancos: abre **todas** as
parcelas da despesa de juros, inclusive as que ficam **fora** do contrato,
cada uma com valor próprio. Isso muda a natureza do resultado — subtrair as
exclusões passa a ser leitura de linha publicada, não estimativa.

2025T1, em R$ mil:

| Parcela | Valor | Tratamento |
|---|---:|---|
| Depósitos interfinanceiros | 47.204 | incluir |
| Captação no mercado aberto | 8.119.122 | incluir |
| Obrigações por empréstimos e repasses | 1.653.544 | incluir |
| Poupança | 2.185.122 | incluir |
| Depósitos a prazo | 9.997.211 | incluir |
| Recursos de emissão de títulos | 5.590.930 | incluir |
| Dívidas subordinadas | 1.963.051 | incluir |
| **Passivos de contratos de seguros** | 10.333.950 | **excluir** |
| **Provisões técnicas de capitalização** | 193.623 | **excluir** |
| **Total impresso** | **40.083.757** | |

`J = 29.556.184` e a conferência fecha **exata**: incluídas 29.556.184 +
excluídas 10.527.573 + residual 0 = 40.083.757. Passivo de contrato de seguro
não é captação, e provisão técnica é atualização de provisão — as duas saem
por nome, com valor.

**Defeito que isso expôs no meu próprio código:** a conferência somava apenas
incluídas + residual e ignorava as excluídas, o que fazia a nota **mais
completa** dos cinco parecer conflitante em todos os cinco períodos. Corrigido,
com contraprova.

### 11.4 O Itaú fecha com residual de 0,02% a 0,13%

Nota 21b, em R$ milhões. Depósitos, captação no mercado aberto, mercados
interbancários e mercados institucionais somam **exato** ao total; sobra
"Outros", sem composição — 70 de 52.474 no 2025T1, **0,13%**, e apenas 7 de
43.776 no 2024T2, **0,02%**. J fica limitado, não identificado como ponto,
porque o contrato proíbe estimar a parcela ausente.

### 11.5 P3 destravado — e a distinção que ele obrigou a fazer

Os documentos de 2024 recuperados são os **arquivamentos originais** daquele
trimestre. Seus valores são "como reportados na época", não coluna comparativa
reapresentada. Com `Data_Entrega` do IPE ligada a protocolo e versão, **10
pacotes passaram a ter P3 conferido** — antes eram zero.

Três regras saíram daí, e valem para qualquer trabalho futuro de vintage:

1. **A posse do período se decide pela data-base, não pelo rótulo.** No
   documento do 3T, o trimestre isolado e o acumulado de nove meses encerram
   ambos em 30/09: os dois são originais. Comparar rótulos trataria o
   acumulado como reapresentado e jogaria fora a evidência que permite derivar
   o 4º trimestre.
2. **Derivado herda a disponibilidade do operando mais tardio.** `Q4 = anual −
   9M` com os dois operandos originais estava calculável na entrega do anual —
   é point-in-time de verdade. Com um operando reapresentado, não é, e o
   estado é `derivada_sem_certificacao`, nunca CONFERIDO.
3. **Documento do período sem data de publicação não certifica nada.** Os PDFs
   do corpus `ifrs` vieram de sites de RI e o manifesto só tem a data de
   download; eles ficam em `SEM_DATA_DE_PUBLICACAO`. Saber que o documento é do
   trimestre não é saber quando ele existiu.

**Defeito corrigido no caminho:** quando duas fontes cobrem o mesmo pacote — o
arquivamento original e a coluna comparativa de um documento posterior — a
escolha era "a última que apareceu", e a reapresentada sobrescrevia a original,
destruindo a única evidência point-in-time. A preferência passou a ser
explícita, com empate entre originais resolvido pela divulgação **mais antiga**.

### 11.6 Uma reapresentação que não reapresentou

O Itaú entregou o 2T2024 duas vezes: versão 1 em 2024-08-06 e versão 2 em
2024-08-07. As duas foram lidas, e **J é idêntico** — `43.769..43.776` em
milhões nas duas. Afirmar isso exigiu ler as duas; supor estabilidade teria
sido a mesma coisa que supor mudança.
