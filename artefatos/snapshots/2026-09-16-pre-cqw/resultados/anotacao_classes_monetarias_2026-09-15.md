# Anotação dimensional assistida por IA — plano de contas

Data: 2026-09-15. Pedido: anotar a classe monetária no CSV existente.

## Contrato e alcance

A anotação é da **descrição exemplar no contexto do demonstrativo**, não de
todas as declarações que compartilham o código. A chave atual agrega planos
e não é uma chave semântica universal (RN09). A própria CVM informa que seus
arquivos incluem contas fixas e não fixas. [Fonte: catálogo DFP da CVM](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp).

- `monetaria`: montante contábil expresso em moeda, incluindo saldos,
  receitas/despesas e ajustes sem efeito caixa. Não significa liquidez,
  disponibilidade de caixa nem item monetário na taxonomia do CPC 02.
- `nao_monetaria`: aqui, valor **por ação**, cuja dimensão difere de um
  montante total. Não significa que LPA deixe de ser expresso em reais.
- Classe vazia + status `inconclusiva_descricao`: o exemplo não identifica
  uma conta; não converter ausência em confirmação pela magnitude.

As novas colunas `classe_anotada_ia`, `dimensao_anotada_ia`,
`status_anotacao_ia`, `escopo_anotacao_ia`, `fundamento_anotacao_ia`,
`fonte_anotacao_ia`, `evidencia_contextual_ia`, `anotador_ia` e
`data_anotacao_ia` separam esta curadoria da proposta
estatística. **`classe_confirmada` continua inalterada:** o produtor a define
como campo de decisão, e não há evidência suficiente para autorizar uma
classe operacional para todo o agrupamento. Não se declara revisão humana,
gold independente, mapa semântico validado ou permissão de reescala.

O preenchimento não modifica os onze campos originais, a ordem das 300
linhas ou as propostas. Em particular, as duas propostas `INDEFINIDA`
permanecem assim na coluna original: a decisão semântica adicional vive na
coluna IA, com fundamento próprio.

## Fontes primárias consultadas

Consultadas em 2026-09-15. As normas sustentam a distinção dimensional; não
certificam a unidade de cada declaração histórica do painel.

| Referência usada no CSV | Fundamento |
|---|---|
| [CPC 26 (R1), itens 51(d/e), 53, 54 e 82](https://www.cpc.org.br/Arquivos/Documentos/312_CPC_26_R1_rev%2023.pdf) | Moeda/arredondamento devem ser identificados; apresentação de saldos de balanço e componentes do resultado. Isso não resolve qual escala um arquivamento defeituoso deveria usar. |
| [CPC 03 (R2), itens 10, 17–20](https://www.cpc.org.br/Arquivos/Documentos/183_CPC_03_R2_rev%2024.pdf) | DFC apresenta fluxos e, no método indireto, ajustes de resultado; ajuste sem caixa ainda é montante, não quantidade física. |
| [CPC 41, itens 9–10 e 31](https://www.cpc.org.br/Arquivos/Documentos/430_CPC_41_rev%2003.pdf) | Resultado por ação relaciona resultado e quantidade de ações; não aplicar automaticamente escala de montante total. |
| [CPC 25, itens 9–10, 36 e 70–83](https://www.cpc.org.br/Arquivos/Documentos/304_CPC_25_rev%2021.pdf) | Provisões, incluindo reestruturação, são obrigações mensuradas por montante; tamanho relativo pequeno não as transforma em LPA. |

## Procedimento e limites

Leitura das 300 descrições exemplares e sua posição no demonstrativo;
consulta somente leitura aos arquivados do `cvm_treino.duckdb`; busca de
descrições com unidades por ação/quantidade/percentual; conferência da família
de LPA e das duas provisões. Há **105.127 descrições distintas** nos
agrupamentos selecionados. Isso confirma por que não se deve promover a
anotação do exemplo a classificação de todas as linhas. **Não foram lidas
individualmente essas 105.127 descrições** nem validadas todas as declarações
contra PDFs.

A busca de palavras não decide a classe: por exemplo, ganho na mudança de
percentual de participação e pagamento por aquisição de 50% de uma empresa
são montantes, não percentuais. Ações em tesouraria no balanço representam
valor contábil; ON/PN sob o grupo de lucro por ação representam classe de
ação à qual a métrica se refere, não uma contagem de ações.

Os sete itens de `3.99` são anotados a partir do contexto de LPA. As
descrições ON nas duas folhas dependem dos pais **da mesma declaração**,
não dos exemplos agregados de outras linhas do CSV. O código sozinho não é
a evidência. Nas demais descrições, a anotação indica
a dimensão do saldo ou movimento apresentado, não uma identidade de conceito
entre planos. Valores negativos/contas redutoras mantêm a dimensão monetária.

Nove exemplos são apenas `0` ou `-` e ficam inconclusivos:

| Demonstrativo | Conta |
|---|---|
| DRE | 3.01 |
| BPA | 1.02.01.05 |
| BPP | 2.02.02.02.03 |
| BPP | 2.02.02.02.04 |
| BPP | 2.02.02.02.05 |
| BPP | 2.01.05.02.07 |
| BPA | 1.02.01.10.03 |
| DRE | 3.04.02.01 |
| BPP | 2.01.05.02.09 |

Não escolher a descrição mais frequente para preencher esses nove campos em
silêncio: isso substituiria o objeto da anotação. Para fechá-los, selecionar
declaração e plano com procedência, preservando a relação com o exemplo
original. O mesmo cuidado vale para promover qualquer anotação a confirmação
operacional.

## Procedência contextual reproduzível

`artefatos/curadoria_plano_contas/2026-09-15/contextos.jsonl` contém 300
registros AM0001–AM0300, referenciados individualmente no CSV. Cada um traz
emissor, conjunto, data de referência, versão, demonstrativo, código,
descrição, tipo de período, início/fim, escala e valor bruto observado.
Pais/avós preservam código e descrição; só são associados quando coincidem
**emissor + conjunto + data de referência + versão + demonstrativo + tipo de
período + início/fim**, com início nulo tratado por igualdade de nulos.
Raízes não recebem a si próprias como ancestral.

Amostra determinística: entre arquivados com descrição literal igual ao
exemplo do CSV, escolher o menor `(cd_cvm, dt_refer, versao_documento,
dt_ini_exerc NULLS FIRST, dt_fim_exerc, tipo_periodo)`. A identidade de plano
no registro vem de `companhias.plano_contas` e **não certifica plano
histórico**. Os ancestrais vêm das linhas do próprio arquivamento, não desse
atributo cadastral.

Isso resolveu os rótulos contextuais: Corrente/Diferido sob IR/CSLL; Outros
sob outros ativos/obrigações; moedas sob empréstimos; Danos sob seguros e
provisões técnicas; Carteira Própria/Terceiros sob captações no mercado
aberto; ANEEL sob provisões; ON sob lucro básico/diluído por ação. A presença
de `MIL` ao lado de LPA é preservada como metadado de origem, **não** usada
como prova de que LPA deve ser multiplicado por mil.

O painel foi aberto em leitura e tem SHA-256
`c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b`.
Contexto obtido do painel não substitui conferência do formulário/PDF para
futura correção de unidade. Zero na observação não é a razão da classe:
classifica-se a dimensão do item descrito no contexto identificado.

## Resultado da curadoria e verificação

300 chaves examinadas: **284 descrições monetárias, 7 por ação e 9
inconclusivas**. Zero confirmações operacionais; zero correções de valores.
Não usar os 92,892% de cobertura de códigos como cobertura semântica validada.

O snapshot semântico dos onze campos originais fica em
`artefatos/curadoria_plano_contas/2026-09-15/antes.json`, com o SHA-256 dos
bytes originais do CSV:
`db597d3a7b8c1b787850acc21269cf05f523f8a7f7f5052f5a580baf39226710`.
Esse JSON preserva campos/ordem, não o terminador CRLF do arquivo original.
O CSV anotado usa LF. Nenhuma estatística original é recalculada.

Hashes da entrega:

| Artefato | SHA-256 |
|---|---|
| CSV anotado | `fa271cd3174000da2877828d7e75b556ac8506e5a5d3cfcd01bb85ff3cb3bb03` |
| `antes.json` | `07e08617c9d7e4c24f3a27d19a819fc6f1421a153224d799ea6d7b0e19dde442` |
| `contextos.jsonl` | `6b3d44027712945fe2727dfffa94411dcedf330f9f8c78b380b40d669fea87ba` |

Verificação: **32 testes passaram em 0,67 s**, executando
`tests/test_anotacao_classes_monetarias.py` e
`tests/test_esqueleto_plano_padrao.py`. Incluem preservação dos onze campos,
ordem, enumerações, vínculos com contexto, ausência de promoção operacional,
provisões, ações em tesouraria e ON com pai identificado. Não medem acurácia
contra um gold humano. A suíte completa não foi repetida nesta tarefa de
anotação, que não alterou código de execução.

O auditor em contexto separado aprovou o **desenho**, sugerindo a separação
da confirmação operacional e exigindo ancestrais da mesma declaração. Isso
foi incorporado. Sua conferência final do artefato foi interrompida por limite
de uso; portanto **não há parecer final independente nem validação humana**
do CSV. As checagens finais de integridade são do agente principal.

Conferência final somente leitura contra o painel: **300/300 declarações
identificadas encontradas**, incluindo descrição, valor bruto e escala;
**zero divergências** entre as descrições dos pais/avós persistidos e os
ancestrais da mesma declaração. Conferir a correspondência com a fonte não
transforma a anotação dimensional em autorização de reescala. Hashes dos
painéis consultável (`43e31d9f…`) e treino (`c1a60445…`) permaneceram iguais.

Nenhum painel reconstruído, script de carga alterado, modelo treinado ou
holdout acessado. Os bloqueios G0/N2/N3 e CQW-01/CQW-02/CQW-03 da conferência
anterior permanecem fora desta tarefa.
