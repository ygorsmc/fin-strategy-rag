# Alcance documental das candidatas GEOM-1

Data: 2026-09-24. Continuação da extensão de 18/09, sem alterar sua regra.
**Resultado: uma das quatro ligações necessárias foi comprovada. Nenhuma
correção aplicada; G0 vigente continua reprovado e treino não autorizado.**

## Resultado por declaração

| Documento | Conta e período | Conclusão documental |
|---|---|---|
| 140867 | Ativo Total `1`, 30/06/2024 | **MIL demonstrada diretamente**, apesar de UNIDADE declarada |
| 140867 | FCO `6.01`, 01/01/2024–30/06/2024 | Célula equivalente não localizada nas notas autorizadas; igualdade não executada |
| 142900 | Ativo Total `1`, 30/09/2024 | Célula equivalente não localizada nas notas autorizadas; igualdade não executada |
| 142900 | FCO `6.01`, 01/01/2024–30/09/2024 | Célula equivalente não localizada nas notas autorizadas; igualdade não executada |

Não são quatro réplicas independentes: duas contas em dois períodos da mesma
companhia. A seleção é dirigida pelas candidatas anteriores; 142900 já era
desenho conhecido. Não é avaliação nova do modelo ou da GEOM-1.

### Prova do Ativo Total de junho

Pacote RAD **140867**, XML `021520ITR30-06-2024v1.xml`, anexo original
**1 (base zero)**, grupo **193**, página **42 do PDF (base um)**, também
impressa 42. Nota **30.2 — Principais ativos e passivos**, linha **Total dos
ativos**, última coluna **Consolidado**, bloco **30/06/2024**. Cabeçalho
declara milhares de reais, com ressalva genérica; nenhuma exceção local
foi identificada.

A célula coincide exatamente, preservando sinal e sem arredondamento, com:
`DadosITR/Formulario/DfConsolidadas/BalancoPatrimonialAtivo/Conta[CodigoConta='1']/TrimestreAtual`.
Saldo não tem início de período. Contraprovas do auditor:

- Comparativo de 31/12/2023 coincide exatamente com `ExercicioAnterior`.
- Cruzar corrente e comparativo não coincide.
- Totais não coincidem com os campos individuais.
- Nenhuma das quatro colunas de segmentos da linha corrente coincide com o
  consolidado; não foi feita soma de segmentos para fabricar uma prova.

O auditor usou XML direto/ElementTree e os PDFs embutidos com pdfplumber e
pdftotext, não o replay GEOM como árbitro. Depois de receber a localização,
o principal replicou as igualdades via pdftotext/XML, sem imprimir montantes;
×1.000 e ÷1.000 não coincidem. Essa réplica posterior não é segunda leitura
cega. Na exploração, `Decimal` sem normalização pt-BR falhou diante dos
separadores do XML; a comparação só foi concluída após normalizá-los também
no XML. Nenhum erro de parse foi convertido em aprovação.

**A prova vem de total consolidado reproduzido numa nota de segmentos**, não
do corpo do balanço. Não abrange subtotais de segmentos, outras rubricas ou
FCO. Corrigir apenas o ativo exigiria suporte por conta no consumidor; o
manifesto vigente corrige o documento, não deve receber uma entrada que
implicitamente altere também FCO.

### Três ligações que continuam sem prova

O auditor percorreu as **43 páginas** das notas de 140867 e as **38 páginas**
de 142900 por dois extratores. Não localizou célula correspondente ao FCO em
nenhum, nem Ativo Total de setembro. Não dereferenciou valores numéricos de
FCO sem contraparte documental para comparação.

As menções a atividades operacionais na página 12 tratam de motores; a
página 40 de 140867 trata de passivos de financiamento. Nenhuma é FCO.
Os PDFs declaram MIL nos cabeçalhos e na nota 2, página 3 do anexo;
**declaração geral de unidade, sozinha, não fecha o vínculo numérico ausente**.
“Não localizado” é o limite desta conferência nas notas 193/412, não alegação
de que a companhia não divulga o dado em outra fonte.

## Procedência e reprodução

Contrato anterior à leitura adicional:
`resultados/contratos_alcance_geom1_rank03b_2026-09-24.md`.
Artefatos: `artefatos/alcance_geom1_rank03b_2026-09-24/`:

- `pin.json`: contrato, duas fontes, hash da extensão e vínculo aos sete
  arquivos protegidos, conferidos idênticos aos de 18/09 antes desta etapa.
- `pin_execucao.json` e `inventario_textual.json`: busca auxiliar em 81 páginas,
  sem valores, sem adjudicação e sem cálculo de FCO.
- `execucao1/`: inventário, pin e código inicial preservados. Um teste encontrou
  apenas espaço duplicado ao mascarar parênteses; a formatação foi corrigida
  sem enfraquecer o teste. Nenhum número/sinal foi exposto por essa falha.
- `execucao2/`: versão anterior à revisão da máscara, com pin e código.
  O auditor demonstrou que sinais Unicode e posfixos podiam sobreviver à
  máscara em sintético. Corrigidos com sete contraprovas adicionais e
  reconferidos independentemente. As três execuções têm inventário idêntico;
  nenhum vazamento observado no dado real. A fragilidade era da guarda.
- `adjudicacao_documental.json`: quatro declarações com estados separados,
  fontes, comparações, contraprovas e limites, sem montantes.
- `parecer_auditor.json`: método, achado de máscara corrigido, rechecagem de
  integridade e limites da conferência independente.

Script: `scripts/inventariar_alcance_geom1_rank03b.py`; execução offline:
`PYTHONPATH=. .venv/bin/python -m scripts.inventariar_alcance_geom1_rank03b`.
O destino existe e recusa sobrescrita. A busca foi desenvolvida **após** o
reconhecimento, não pré-registrada como detector exaustivo. **Limitação
demonstrada:** seu vocabulário não inclui “Total dos ativos”, justamente o
sinônimo em que o auditor encontrou a prova. Zero correspondências lexicais
jamais foi consumido como ausência contábil. Não alterar a GEOM-1 congelada
nem rebatizar esse inventário como sua versão confirmatória.

| Fonte | SHA-256 |
|---|---|
| 140867 ZIP | `35571da80c582f26ace27f94b0f9f02dcddf30f70498e663d61f5ef75087f105` |
| 140867 XML | `28ca3369a0787548d5654d3ee08c8601b00f02ab97b8e663c17d0eef9e7e9258` |
| 140867 PDF | `1bf92ff2aefb00710d975aa84b5522c790d59eb53cda5f007afeb3fd7f39b808` |
| 142900 ZIP | `4cc8d45a42fecc590023b80255c1a5cbb48c8c9da0e86bc528c105faf945efb2` |
| 142900 XML | `4ee561c7f5cf601bc03b7cf44b0f331c891adc668d6508a057bd4cabdf93bc68` |
| 142900 PDF | `685eb99d0fd961de01c1a7621bc79a4b1b15055e6902671256d483ca85aad5d2` |

Metadados provisórios errados na primeira mensagem do auditor (página impressa
55 e nota 31.2 para junho) foram corrigidos por ele antes do parecer final e
conferidos no PDF: página 42, nota 30.2. Setembro tem paginação impressa
diferente da física; referências desta onda usam página do anexo.

## Verificação de software e limites

**20 testes específicos e 132 focados passaram** (20 desta etapa + 112 da
regressão GEOM); o auditor executou os 20 independentemente. A suíte completa
anterior ao último ajuste da máscara, registrada em
`pytest_completo.xml` executou **2.907 casos: 2.906 passaram, 1 falhou, zero
erros/skips**. A falha é `tests/test_config_app.py:158`: a interface apresentou
também “Pergunta livre”, enquanto o teste esperava só “Demonstração (cacheado)”.
Essa frente não foi alterada nesta etapa. O diagnóstico confirmou
`HABILITAR_PERGUNTAS_LIVRES=1` no `.env` local, herdado pelo teste. O mesmo
teste passou com `HABILITAR_PERGUNTAS_LIVRES=0` definido apenas no processo
(`teste_interface_modo_cacheado.xml`). Não se alterou configuração, interface
ou asserção. O teste não isola o modo que pressupõe; a árvore também contém
alterações paralelas. Não apagar a execução inicialmente vermelha.

**Suíte final: 2.914 passed, zero falhas/erros/skips, 28 warnings**, em
154,65 segundos, com código final e modo cacheado explícito somente no
processo. XML: `pytest_final_modo_cacheado.xml`. Comando reproduzível:

```sh
HABILITAR_PERGUNTAS_LIVRES=0 CREWAI_STORAGE_DIR=/tmp/alcance-geom1-BVymbv/crewai PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --junitxml=artefatos/alcance_geom1_rank03b_2026-09-24/pytest_final_modo_cacheado.xml
```

O auditor reconferiu a máscara, os 20 testes desta etapa, os snapshots e os
sete arquivos protegidos: nenhum achado técnico remanescente no escopo.
Não executou a suíte completa; a última execução acima é do principal.

O terminal perdeu a montagem do sandbox durante a retomada (`mountinfo path
is not absolute`), e a sessão da suíte deixou de ser recuperável pelo ID.
O resultado acima veio do XML persistido, lido com a permissão de execução
solicitada; não de uma suposição de conclusão do processo.

Sem downloads, APIs pagas, acesso ao holdout, mudança de GEOM-1, CSV ou painel,
herança S5, novo G0/G1, alvo, T1/T2, baselines ou treino. Concordância de agentes
não é gold humano.

## Próximo passo

Para fechar as três ligações documentais restantes, falta fonte que mostre os
vínculos da tabela inicial, em particular **FCO nos dois períodos**. Mesmo
quatro ligações conferidas não provariam todas as outras contas. Procurar a
demonstração financeira completa do mesmo período/perímetro, com unidade e
procedência verificáveis; incorporar outro grupo de anexo ou fonte exige
contrato explícito, sem alterar silenciosamente o escopo 193/412.

Alternativa técnica separada: manifesto de correção **por conta**, aproveitando
somente Ativo/140867 já demonstrado. Exige novo schema, guardas, testes de não
alteração do FCO, revisão independente e preservação das provas. Nenhuma das
duas alternativas foi implementada, nem seu efeito em G0 medido. Os cinco
pontos de política e executor v2 seguem pendentes; não treinar.

> **Retirado na revisão de 24/09** — ver a ressalva abaixo. Corrigir só o ativo
> não reduz o G0.3 neste caso e deixaria o FCO do mesmo documento na escala
> declarada sem que G0.3 ou G0.5 percebessem.

## Ressalva da revisão (24/09)

Revisão pedida pelo responsável depois da publicação deste relatório;
correções sob o [contrato da revisão](contratos_revisao_alcance_geom1_rank03b_2026-09-24.md).
Os fatos acima se sustentam; mudam o próximo passo e o que se pode afirmar
das ausências. Evidência: `artefatos/alcance_geom1_rank03b_2026-09-24/revisao/`.

### Correção só do ativo — retirada (R1)

- O G0.3 só olha o ativo (`gate_g0` em
  `scripts/auditar_rank03b_consumo_operacional.py`), e o FCO trimestral é a
  diferença entre acumulados (`construir_fco` em
  `scripts/painel_pesquisa_rank03b.py`).
- Na 021520 os saltos de 2024 são 1T→2T e 3T→4T. Corrigir só o ativo de 140867
  move o primeiro para 2T→3T, porque 142900 continua em UNIDADE: o G0.3 segue
  em 132. O FCO de 2T2024 (MIL+UNIDADE) e de 4T2024 (UNIDADE+MIL) continua
  derivado de escalas diferentes, sem adjudicação.
- Com mais ativos provados, cada correção só do ativo tira um sinal do único
  detector de escala, enquanto o FCO, de onde sai o rótulo, continua na escala
  declarada. E o G0.5 proposto conta "decidido" por documento
  (`documentos_decididos` em `scripts/gates_painel_pesquisa_rank03b.py`): um
  manifesto por conta faria o FCO de 140867 contar como adjudicado por causa
  do ativo.
- **Regra:** correção que alcance só uma das contas que o painel usa exige,
  antes, G0.3 e G0.5 lendo o veredito por conta.
- **Dimensionamento:** faltam 20 saltos para o G0.3 passar (132 → no máximo
  112). Os dois documentos valem no máximo −2 (132 → 130): sob a opção A do
  §12-bis, pela prova de caixa; sob a B, só com as quatro ligações. A
  companhia tem ainda quatro saltos fora de 2024 (2T16→3T16, 4T16→1T17,
  4T24→1T25, 3T25→4T25). *(Corrigido em 25/09, auditoria M1 e B3: a primeira
  versão supunha a opção B e citava só os dois saltos de 2024–25.)*

### Alcance da prova — ponto de decisão (R2)

A frase "o manifesto vigente corrige o documento, não deve receber uma entrada
que implicitamente altere também FCO" pressupõe um critério que a cadeia
governante não adota. Na v4, prova de saldo (1, 2 ou 1.01.01) corrige o
documento inteiro: o construtor aplica a escala do documento ao ativo e ao
FCO, e a impressão digital da correção cobre as contas 1 e 6.01. A linha
GEOM-1 exige demonstrar cada conta que o painel usa. Hoje a diferença não tem
efeito, porque a v4 não tem correção nenhuma, mas os dois critérios não podem
valer juntos. A mesma premissa da opção B está no `parecer_auditor.json` de
24/09 ("uma prova do ativo não autoriza correção por documento que também
altere FCO"), artefato não reescrito, com hash registrado abaixo. Ficou registrado como
**[DECIDIR]** no [rascunho v2](pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md)
(§12-bis). Consumidor, construtor e manifesto não foram alterados.

### Busca numérica exata (R3)

Refeita como evidência reprodutível
(`scripts/conferir_alcance_geom1_rank03b.py`, saída em
`revisao/conferencia_revisao.json`, pin em `revisao/pin_revisao.json`). Foi
executada primeiro durante a revisão, em memória e sem contrato: **não é teste
cego**. `pdftotext -layout` e `-raw` concordam em todos os casos.

| Declaração | Principal (inventário lexical) | Auditor (leitura, dois extratores) | Revisão (busca numérica exata) |
|---|---|---|---|
| Ativo, 140867 | Nenhuma menção: o vocabulário não tinha "Total dos ativos" | MIL demonstrada, p42, nota 30.2 | Valor só na p42, coluna 5; comparativo idem; individual, ×1.000 e ÷1.000 sem correspondência |
| FCO, 140867 | Menções que não são de FCO (p12, p36, p40) | Não localizada | Sem correspondência: acumulado atual e anterior, individual, ×1.000 e ÷1.000 |
| Ativo, 142900 | Nenhuma menção | Não localizada | Sem correspondência nas mesmas seis formas do ativo |
| FCO, 142900 | Menções que não são de FCO (p12, p35) | Não localizada | Sem correspondência nas mesmas cinco formas do FCO |

A única divergência, o principal não ter achado a prova do ativo, veio do
vocabulário da busca lexical; a leitura do auditor, a réplica e a busca
numérica a resolvem. Para o ativo de 142900 e para o FCO, "igualdade não
executada" passa a **"busca exata sem correspondência nas notas"**. Isso não
é ausência da informação em outra fonte e só cobre números no formato pt-BR
com ponto de milhar. O FCO foi comparado só em memória: o artefato traz
páginas (todas vazias), nunca montante ou sinal, e uma autoverificação recusa
gravar saída que contenha algum valor comparado.

Na p42 o mesmo valor aparece também na linha "Total dos passivos", coluna 5,
nos dois períodos. É o esperado — ativo = passivo + patrimônio líquido, e o
total da nota inclui o patrimônio. A prova continua sendo a linha "Total dos
ativos".

### Nota de segmentos não é "linha gerencial" (R5, item 3 do contrato)

As colunas por segmento são de base gerencial; a prova não usa nenhuma delas,
e nenhuma coincide com o formulário. A coluna Consolidado é o total contábil
conciliado: coincide com o consolidado do formulário no período corrente e no
comparativo, e não com o individual.

### Máscara (R4)

A correção de 24/09 enumerou variantes: cobria só 3 dos 26 traços da
categoria Unicode Pd (U+002D, U+2013, U+2014) e deixava passar os outros 23 —
entre eles U+2010, U+2011, U+2012, U+FE63 e U+FF0D —, além de sinais de menos
fora dessa categoria; `(R$ 123)` e palavras de polaridade ("aplicado",
"negativo") também passavam em teste sintético. *(Contagem corrigida em
25/09, auditoria B3: a primeira versão falava em "cinco traços".)* Agora o sinal é uma classe
Unicode, a moeda entra no número e linha de fluxo de caixa não publica trecho.
No dado real nada vazou: a regra nova, reaplicada em memória às 81 páginas, só
difere do inventário publicado pela retirada de seis trechos de linhas de
fluxo (quatro em 140867, dois em 142900). O inventário publicado não foi
regravado; o código que o produziu está em
`revisao/inventariar_alcance_executado.py`.

### Detalhes (R5, R6)

- Comando reproduzível, sem o diretório temporário da sessão:
  `CREWAI_STORAGE_DIR=$(mktemp -d)/crewai PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q`.
  Desde R6 não precisa de `HABILITAR_PERGUNTAS_LIVRES=0`: o teste de
  interface fixa a própria pré-condição, sem mudar asserção.
- A chave com caminho absoluto em `pin_execucao.json` vem do `selecao.json` de
  18/09, fixado por hash: declarada, não reescrita.
- Testes: 90 contraprovas novas (56 da máscara, 34 da busca). Suíte completa
  com o `.env` local ativo e sem sobrescrever variável: **3.004 passed, zero
  falhas/erros/skips**, 151,9 s (`revisao/pytest_suite_sem_override.xml`).

### Duas fontes locais, não usadas

- Os pacotes têm um segundo anexo, do grupo 192: "Relatório da
  Administração_2ITR-2024.pdf" (140867) e "Comentário Desempenho_Multiner (ITR
  30-09-24).pdf" (142900), dentro dos ZIPs já fixados. Usá-los exige adendo ao
  escopo 193/412 e cuidado com número gerencial. O conteúdo não foi lido.
- O saldo final de caixa da DFC (6.05.02) é igual ao caixa do balanço
  (1.01.01), em bruto, nos dois formulários — conferido sem tocar no 6.01. Como
  o caixa foi provado em milhares em 18/09, a DFC foi preenchida na mesma
  unidade, ao menos nessa linha. Chegar ao 6.01 exigiria o fechamento da DFC,
  que soma o FCO e o O1 hoje proíbe: seria evidência de outro tipo, com
  contrato próprio, e antes é preciso saber quais linhas o sistema da CVM
  calcula sozinho.

### Adendo pós-auditoria (25/09)

O auditor-conformidade achou 1 ALTA, 1 MÉDIA e 4 BAIXA; correções sob o
[adendo](adendo_revisao_alcance_geom1_rank03b_2026-09-25.md), escrito antes
de editar.

- **A1 (ALTA):** o "Próximo passo" do MEMORY.md ainda recomendava a correção
  por conta. Reescrito, com remissão ao §12-bis; o v2 tem seis [DECIDIR].
- **M1 (MÉDIA) e B3:** consequências da opção A e contagens corrigidas acima,
  marcadas com a data.
- **B1 — canais latentes, nada vazou no dado real:** moeda passou a ser classe
  (símbolos `Sc` e códigos ISO 4217); parêntese órfão sai de trecho com número
  mascarado; linha com vocabulário de caixa, fluxo ou polaridade não publica
  trecho (lexical: reduz o canal, não o fecha); a busca usa a mesma política
  para o trecho do ativo; a autoverificação varre as chaves, reconhece milhar
  com espaço e vírgula e isenta só hash e data, como o contrato dizia.
- **B2:** contraprovas para os guardas de `executar()` e para o XML e a
  paginação; texto ilegível (`(cid:`, U+FFFD) derruba a execução, e páginas
  com pouco texto são publicadas. "Publicar se difere...", no R4, é medida
  publicada, não condição de gravação.
- **Substituição de teste, declarada:**
  `test_autoverificacao_aceita_identidade_e_numeros_pequenos` (24/09) fixava a
  isenção de campos de identidade; virou
  `test_autoverificacao_isenta_so_hash_e_data`, mais
  `test_identidade_de_documento_nao_e_isenta`.
- **B4 fica aberto:** o consumidor não confere o cabeçalho do manifesto, e uma
  linha "por conta" com coluna extra seria aplicada ao documento inteiro. O
  contrato desta onda proíbe mexer no consumidor; a guarda de schema é
  pré-condição do contrato que criar correção por conta ou integrar a GEOM-1.

As execuções de 24/09 não foram refeitas. O código que as produziu está
preservado em `revisao/conferir_alcance_executado.py` e
`revisao/inventariar_alcance_usado_na_revisao.py`, idênticos aos hashes do
pin. A reconferência dos artefatos publicados sob as regras novas
(`revisao/reconferencia_pos_auditoria.json`, em memória) deu:

- autoverificação estrita aprovada nos dois arquivos da revisão;
- nenhum texto ilegível e nenhuma página com pouco texto, nos dois documentos
  e nos dois modos;
- os 8 trechos do ativo publicados ficam idênticos;
- no inventário de 24/09, a política nova só retira os 6 trechos de fluxo já
  conhecidos (83 idênticos, nenhum alterado, nenhum retirado por vocabulário).

Suíte completa depois do adendo, com o `.env` local ativo e sem sobrescrever
variável: **3.108 passed, zero falhas/erros/skips**, 142,9 s — mais 104
contraprovas (79 do inventário, 25 da busca) sobre os 3.004 de 24/09
(`revisao/pytest_suite_pos_auditoria.xml`).

**N1 — hashes que faltavam (reconferência do auditor, 25/09).** A ressalva
chamava o `parecer_auditor.json` de "fixado por hash" sem registrar o hash, e
a reconferência lia as saídas da revisão sem conferi-las. Hashes registrados
agora, depois de conferidos pelo auditor pelo conteúdo e pelas datas (24/09,
23:02 e 23:34–23:35):

| Artefato | SHA-256 |
|---|---|
| `parecer_auditor.json` | `a3aab39c2974a63147df92b9836bad0b5865b32e8555490c3472c31fe093779b` |
| `revisao/conferencia_revisao.json` | `c19682bfde33480a66caeb088503f098360aebce57b6070a539f5f97a28eb3a3` |
| `revisao/pin_revisao.json` | `34139fb65ded85eb152039fe1a57d54f4fd9bcdfee4ef35f9cf6e104ae3db72e` |

A reconferência passou a exigir esses hashes, e o do inventário, antes de
ler qualquer coisa, e a registrá-los na saída. A execução de 25/09 foi feita
antes dessa guarda, pela versão preservada em
`revisao/conferir_alcance_reconferencia.py`. O auditor reconferiu o N1: fechado,
sem achado novo. Suíte completa depois do N1: **3.111 passed, zero
falhas/erros/skips**, 143,6 s (`revisao/pytest_suite_final.xml`).

## Ressalva da correção RAG (25/09)

A [conferência independente de 25/09](conferencia_revisao_alcance_geom1_rank03b_2026-09-25.md)
reabriu o instrumento da busca exata (RAG-01 a RAG-03). A correção, com
contrato próprio, está em
[correcao_rag_alcance_geom1_rank03b_2026-09-25.md](correcao_rag_alcance_geom1_rank03b_2026-09-25.md).
Duas coisas mudam a leitura da seção "Busca numérica exata (R3)":

- **A forma ÷1.000 não testou a hipótese que parece testar.** Ela compara
  exatamente e só casaria se as notas imprimissem as casas decimais do
  milhar. Notas em milhares imprimem inteiros arredondados, e o quociente do
  ativo não é inteiro em nenhum dos dois documentos. A coluna "Revisão" da
  tabela, onde diz "÷1.000 sem correspondência", não é evidência sobre "XML em
  reais, notas em milhares". Para o FCO nada foi calculado sobre
  divisibilidade (O1). As outras formas não mudam.
- **A busca foi repetida com o analisador corrigido** (token inteiro, sinal
  explícito, autoverificação por equivalência numérica). O resultado é o mesmo
  nas quatro linhas da tabela, com as mesmas posições e trechos e nenhuma
  ocorrência ambígua do ativo. A tabela acima fica como estava.
