# B-DFC-01J-M — prontidão para treino: **NÃO AUTORIZA** (2026-09-09)

**Custo:** zero (sem rede, sem chamada paga) · **Pré-registro:**
[`pre_registro_b_dfc_01j_modelo_2026-09-09.md`](pre_registro_b_dfc_01j_modelo_2026-09-09.md)
**Auditor:** `scripts/auditar_prontidao_b_dfc_01j.py` →
`artefatos/b_dfc_01j/prontidao/gates.json` +
`sensibilidade.json`
**Série-fonte:** `artefatos/b_dfc_01j/extensao/` · **Suíte:** ver §7 · **Atualizado em 2026-09-10** com a resolução do G0 (§2-bis)

> ## ⛔ RETRATAÇÃO ESTRUTURAL (2026-09-10, pós-revisão independente)
>
> **Este relatório inteiro mede um J cujos limites o programa fabricava.** A
> [revisão independente](revisao_independente_b_dfc_01j_2026-09-10.md) achou
> (F1) que `construir_j` usava o residual **líquido** de rubricas que misturam
> juros e câmbio como limite da parcela de **juros** — e câmbio tem os dois
> sinais, então não limita nada. Corrigido o instrumento
> ([correção](correcao_instrumento_b_dfc_01j_2026-09-10.md)):
>
> | | Aqui | Depois da correção |
> |---|---:|---:|
> | J como intervalo (25 pacotes) | 15 | **0** |
> | J não identificado | 9 | **24** |
> | Pares na série estendida | 69 | **0** |
> | Gate decisivo | G1 (72,0%) | **G0, reprovado** |
> | G2 ruído/sinal | 1,0464 | **não existe** |
>
> **NÃO usar como conclusões atuais:** "G0 resolvido", "o rótulo é mais ruidoso
> que o sinal", "~16 emissores", "J limpo não existe". As três primeiras vinham
> dos limites inventados; a última é mais forte do que a evidência sustenta
> (F5). O que resta válido: as duas rubricas **não** voltam para J, porque falta
> prova para aprová-las — e a suspensão do treino continua.
>
> Também retratado o §6.1: "**15 de 15 identidades anuais**" não está no
> artefato. `T1+T2+T3+T4 = A` tem **0 conferidas e 17 não verificáveis**, e uma
> identidade cujo T4 saiu de `A − M9` fecha por construção (F11).
>
> Os 25 pacotes congelados seguem sendo 25 — o denominador não mudou; o que
> mudou é o que se mede sobre ele. O `corpus/holdout_2T2026` **não foi tocado**.
> Painéis e corpora de produção intactos, conferido por hash e `git diff` vazio.
>
> **Atualização de 2026-09-11 — duas precisões sobre esta retratação.**
>
> 1. **O "~16 emissores" não sumiu; ficou em quarentena.** A frase acima o põe
>    entre as conclusões a não usar, e está certo — mas o número **continuava
>    sendo publicado** por `prontidao/sensibilidade.json` com `decidivel: true`
>    e `ressalva: null`, isto é, com selo de válido. O
>    [parecer de 11/09](parecer_correcao_b_dfc_01j_2026-09-11.md) pegou isso
>    (contrato C6) e a
>    [implementação](implementacao_c1_c6_b_dfc_01j_2026-09-11.md) marcou o campo:
>    `decidivel: false`, `calculo_de_poder_invalidado_por: "F3"`. **Publicado e
>    invalidado, não apagado.** O `G2 = 1,0464`, esse sim, deixou de ser
>    produzido — o gate devolve "alvos insuficientes".
> 2. **O instrumento levou TRÊS ondas de correção.** A de 10/09 fechou o
>    achado central (F1); a conferência de 11/09 encontrou **seis contratos
>    ainda abertos** — empates de quintil fabricando associação máxima para
>    variável constante, unidade descartada pelo consumidor, horizonte aceitando
>    qualquer trimestre em vez de q(D), antecedentes de baseline não conferidos
>    quanto à disponibilidade, e identidade com acumulado derivado saindo como
>    independente. Os seis foram implementados no mesmo dia (+20 contraprovas).
>    A **conferência independente dessa implementação** aprovou só em parte:
>    C5 e C6 estavam fechados **apenas no produtor** — publicavam o campo de
>    estado novo sem tocar o predicado de decisão do consumidor, de modo que G0
>    certificava com zero evidência independente e G3 aprovava declarando o
>    próprio cálculo de poder inválido. Corrigidos em seguida, com uma dívida
>    preexistente de robustez (+12 contraprovas, suíte **1.985**):
>    `implementacao_rc5_rc6_b_dfc_01j_2026-09-11.md`. **F3, o redesenho do
>    cálculo de poder, segue sem correção** — mas a invalidez agora **veta** a
>    aprovação de G3, em vez de só estar escrita ao lado dela.

---

## 1. Em uma frase

O gate reprovou **antes de qualquer modelo**, e a causa mais grave não é
estatística: **duas rubricas que o contrato manda somar em J embutem variação
cambial e a parcela não é separável** — despesa de captação por competência não
é crédito, e essas linhas vêm credoras quando o real valoriza. A tentativa de
construir o alvo foi o que expôs isso; olhar níveis nunca mostraria.

> **A leitura das notas foi feita (§2-bis) e fechou o G0.** Com J conforme ao
> contrato, o rótulo passa a ser **mais ruidoso que o sinal** (G2 de 0,021 para
> **1,0464**) e o Itaú sai da população. **O veredito deixou de ser
> condicional:** o ramo pessimista é o que se realizou.

Estado **final**, depois de resolver o G0 (a coluna "antes" é o estado publicado
em 2026-09-09, quando a natureza das rubricas ainda era pergunta aberta):

| Gate | Pergunta | Antes | Depois | Limiar | |
|---|---|---|---|---|---|
| **G0** | O dado é íntegro? | 3 rubricas não conformes | **0** | 0 | ✅ **resolvido** |
| **G1** | É *point-in-time*? | 74,14% | **72,0%** (18/25) | 100% | ❌ **decisivo** |
| G2 | O rótulo erra menos que o sinal? | 0,021 ✅ | **1,0464** | < 0,10 | ❌ diagnóstico |
| G3 | A amostra decide algo? | 130,6% do erro | **2 emissores < 3 clusters** | ≤ 20% | ❌ diagnóstico |
| T1 | O alvo fabrica o próprio baseline? | 0,1439 restrita | **16 obs < 25 p/ quintil** | < 0,15 | ❌ diagnóstico |
| T2 | Sinal temporal ou ordenação de emissor? | 0,1084, não informativo | **sem baseline eleito** | < 0,12 | ❌ diagnóstico |

As três últimas linhas fecham em **reprova em aberto** — amostra insuficiente
para decidir, que nunca é aprovação (§3.14 do AGENTS.md). Elas entram na cadeia
como gate reprovado **com o motivo**, em vez de derrubar o relatório e levar
consigo o que já havia sido medido.

A cadeia **para em G0**, como o §5 do pré-registro manda. O que vem depois
continua medido e publicado como **diagnóstico**, para que a reprovação diga o
tamanho do que falta em vez de só dizer que falta. Só G0 conta para o veredito.

---

## 2. O achado: crédito em linha de despesa de juros

`juros_mercados_interbancarios` (Itaú), `juros_depositos_interfinanceiros` e
`juros_emprestimos_e_repasses` (Bradesco) assumem **valor credor** em quatro
trimestres da série. Dois são **impressos pelo próprio emissor**:

| Emissor | Trimestre | Rubrica | Valor | Fonte |
|---|---|---|---:|---|
| Itaú | 2T2021 | Recursos de Mercados Interbancários | **+3.107** | `itau_ifrs_2021T2` p.89 |
| Bradesco | 2T2021 | Empréstimos e repasses | **+2.335.452** | `bradesco_ifrs_2022T2` p.79 |
| Itaú | 4T2020 | Recursos de Mercados Interbancários | **+4.136** | derivado `A − M9` |
| Bradesco | 4T2025 | Depósitos interfinanceiros | **+1.760.629** | derivado `A − M9` |

**Por que isto é não conformidade, e não curiosidade.** O contrato B-DFC-01J
exclui nominalmente câmbio, valor justo e derivativos, e define J como juros
**por competência** dos instrumentos de captação. Uma linha de despesa de
captação publicada como crédito embute um dos excluídos — ou é
reclassificação. Nos dois casos ela deixou de ser o que o contrato mandou
somar. **A soma fecha do mesmo jeito:** o P2 do Itaú de 2T2021 confere exato.

**A magnitude confirma.** No Itaú, `Recursos de Mercados Interbancários` vai de
**(24.230)** no 1T2020 a **+3.107** no 2T2021 — coeficiente de variação **0,68**
numa linha de funding, enquanto a Selic mal se moveu entre trimestres vizinhos.
No Bradesco, `juros_depositos_interfinanceiros` tem **CV 0,96**, o pior de
todas as parcelas dos três emissores. As seis parcelas do **BB não têm um único
crédito** e têm CV entre **0,11 e 0,50**: o defeito não é da série, é destas
linhas.

> **CVs re-medidos em 2026-09-10.** A versão de ontem publicava **0,75**, **1,46**
> e **0,11–0,54**. Aqueles valores são de antes da guarda de acumulado que
> encolhe, que retirou dois 4T derivados espúrios — inclusive o de
> `juros_depositos_interfinanceiros`, cuja diferença credora de +1.760.629 é o
> que inflava o 1,46. Método: CV amostral sobre trimestre **isolado**, por
> emissor e por rubrica, em `extensao/fatos.jsonl`.

**Os dois derivados admitem uma segunda explicação, e ela fica declarada.**
`A − M9` sai credor quando o acumulado anual é MENOR em módulo que o de nove
meses. Isso pode ser reversão econômica, mas também pode ser o documento anual
**reclassificando** a composição — e aí os dois operandos não são comparáveis
mesmo sendo os dois originais. Não sei qual dos dois é, e por isso **não
escolho**: os dois casos entram como não conformidade, o que é a leitura
conservadora. **Os dois impressos não têm essa ambiguidade** e sustentam o
achado sozinhos.

### 2.1 Retratação

> **O que estava publicado e não se sustenta.** O relatório do piloto e o da
> extensão da janela afirmam que J foi identificado para Bradesco e Itaú — o
> Bradesco como **ponto exato** — com fechamento conferido. A aritmética
> continua conferindo e nenhum número muda. O que **não** se sustenta é a
> afirmação implícita de que o J assim somado é **o J do contrato**: três das
> parcelas incluídas não foram demonstradas como juros por competência, e duas
> foram demonstradas como **não** sendo.
>
> Isto é a armadilha do BTG outra vez, no emissor que o piloto tratou como
> melhor caso — e achada do mesmo modo: olhando mais períodos em vez de
> confiar num fechamento que por acaso deu certo. A lição do piloto ("soma
> fechar não prova semântica") valia também para quem a escreveu.

**Escopo exato da retratação.** Dentro da janela congelada do piloto
(2024T1–2025T1) **nenhum crédito aparece**: os 24 pacotes com fonte saem como
`conformidade_contratual = aparente` na coluna nova de
`auditoria_pacotes.csv`. "Aparente" quer dizer *nenhum crédito observado
aqui* — **não** quer dizer conforme. A dúvida é da **rubrica**, não do
trimestre, e uma linha pode embutir câmbio e ainda assim vir devedora. Por isso
o G0 reprova a série inteira quando qualquer trimestre acusa: demonstrada não
conforme em algum lugar significa **não demonstrada conforme em lugar nenhum**.

**O que fecharia isso** (não foi feito, custo baixo): ler a nota de política
contábil e a de gestão de risco de mercado dos dois emissores para saber o que
essas linhas contêm, e a nota de câmbio para separar o componente. É leitura de
documento que já está em disco — curadoria, não acesso.

---

## 2-bis. G0 RESOLVIDO (2026-09-10): a parcela cambial NÃO é separável

O §8.1 mandava ler as notas para saber o que essas três rubricas contêm. Foi
feito, custo zero, nos documentos em disco. **A resposta é a do ramo
pessimista**, e o efeito nos gates está medido no fim desta seção.

### 2-bis.1 O que a linha do Itaú contém

A Nota 17b decompõe `Recursos de Mercados Interbancários`, e a maior
sub-rubrica é **`Financiamentos à Importação e Exportação`**, que a própria
nota declara *"geralmente denominadas em **moeda estrangeira**"*:

| | 31/12/2019 | 31/03/2020 | 31/03/2025 |
|---|---:|---:|---:|
| Financiamentos à Importação e Exportação | 64.622 | **84.051** | 105.837 |
| Total de Recursos de Mercados Interbancários | 174.862 | 188.134 | 363.192 |
| Taxa de juros contratual declarada | — | **0% a 9,60% a.a.** | 0% a 10,20% a.a. |

**Quatro medições, e nenhuma delas é suposição:**

1. **O saldo em moeda estrangeira subiu 30,1% num trimestre** — 64.622 para
   84.051, +19.429 — sem emissão que explique. É a desvalorização do real no
   1T2020.
2. **A linha de juros saltou 21.119 no mesmo trimestre** — de `(3.111)` no
   1T2019 para `(24.230)` no 1T2020. Contra R$ 19.429 de reavaliação do saldo:
   **casam dentro de 8%**.
3. **O teto contratual proíbe a leitura alternativa.** A taxa declarada é
   `0% a 9,60% a.a.`; sobre R$ 84 bi isso não produz mais que ~R$ 2 bi de
   juros num trimestre. Um número de R$ 24 bi não pode ser juros.
4. **No sentido inverso funciona igual.** No 2T2021 o real valorizou, o saldo
   **caiu** (77.142 → 74.993) e a linha veio **credora, +3.107**.

**E o emissor diz isso com as próprias palavras.** A Demonstração dos Fluxos de
Caixa do Itaú tem três linhas nomeadas **`Resultado de Juros e Variação
Cambial de …`** — juros e câmbio viajam juntos na apresentação dele.

### 2-bis.2 Por que não é separável

- A **Nota 21b é tabela plana de cinco linhas**, sem rodapé e sem qualquer
  decomposição de componente cambial.
- **Não há nota de exposição por moeda** nas demonstrações intermediárias.
- A **nota de hedge do anual nomeia os objetos de cobertura**: `Depósitos` e
  `Captações no Mercado Aberto`. **Nunca `Recursos de Mercados
  Interbancários`** — então nem pela via do hedge a parcela se isola.
- O saldo em moeda estrangeira **é** publicado, o que permitiria *estimar* a
  parcela cambial. **Estimar é proibido pelo contrato** — "ausência de
  composição nunca vira zero ou estimativa".

### 2-bis.3 O Bradesco tem o mesmo defeito, com evidência mais fraca

`Obrigações por empréstimos e repasses` vem **credora em +2.335.452** no 2T2021,
dentro de uma tabela cujo total é despesa de `(9.652.884)`. É o **mesmo
trimestre** em que a linha do Itaú virou credora, e o Bradesco tem R$ 30,8 bi de
investimentos no exterior. **Mas o casamento de magnitude que se mediu no Itaú
não foi medido aqui** — a composição da rubrica por moeda não é publicada, que é
exatamente o motivo de não ser separável. A evidência é o crédito impresso e a
coincidência de trimestre, e o registro diz isso.

### 2-bis.4 A terceira rubrica NÃO era defeito de rubrica

`Depósitos interfinanceiros` do Bradesco só aparece credor num **4T derivado**
(2025T4): o anual imprime `(521.525)` contra `(2.282.154)` nos nove meses, e
`A − M9` devolve +1.760.629 numa rubrica cujo trimestre típico é `(52.085)`.
**Acumulado de doze meses menor que o de nove não é diferença de nada** — ou
houve reversão no 4T, ou o anual reclassificou a composição e os operandos não
são comparáveis mesmo sendo os dois originais. Não se sabe qual, então não se
escolhe: **a derivação é recusada** e a rubrica **continua em J**. Confundir
"esta subtração não vale" com "esta linha não é juros" teria condenado uma
rubrica sem evidência.

### 2-bis.5 O que a conformidade custou

As duas rubricas com crédito impresso passaram a **NÃO IDENTIFICADAS** — não
excluídas, porque excluir exigiria saber o valor da parcela cambial e jogaria
fora junto os juros legítimos das outras captações da mesma linha. J virou
intervalo. Medido em `prontidao/sensibilidade.json`:

| | Estado conforme (agora) | Estado anterior, não conforme |
|---|---:|---:|
| Pares antes do corte | 69 | 69 |
| **Cortados por largura > 5%** | **40** | 9 |
| Alvos | **25** | 55 |
| **G2 ruído/sinal** (limiar < 0,10) | **1,0464** ❌ | 0,0214 ✅ |
| Emissores na população | **2** | 3 |
| Poder interpretável | **não** | sim |

**A folga de 48× do G2 era comprada pelo defeito.** Com J conforme ao contrato,
o rótulo fica **mais ruidoso que o sinal** (meia-largura mediana 0,0482 contra
movimento mediano 0,0460). E o Itaú **sai inteiro da população**, porque o
intervalo dele estoura o corte de 5% em quase todo trimestre.

**Largura relativa do intervalo de J — e aqui há dois recortes que não se
confundem.** Os cinco trimestres congelados do piloto (2024T1–2025T1) são um
recorte estreito e favorável; a série estendida é a medida honesta:

| Emissor | Piloto (5 trimestres) | **Série estendida** | | |
|---|---|---:|---:|---:|
| | | n | mediana | máximo |
| Bradesco | 3,9%–6,3% | 21 | **4,07%** | 24,19% |
| BB | 0,45%–0,67% | 29 | **0,57%** | 34,57% |
| Itaú | 16,5%–40,7% | 47 | **23,79%** | **81,57%** |

**Regra de seleção da coluna "série estendida", necessária para reproduzir:**
trimestre **isolado** (`periodo` no formato `AAAATn`) **e** com
`fechamento_confere = True`, sem deduplicar por safra — um mesmo
emissor-trimestre publicado em duas safras entra duas vezes, com a largura de
cada uma. Sem essa regra os números não reproduzem: incluir os que não fecham
leva o Itaú a 23,23% (n=48) e deduplicar por safra leva a 22,67% (n=33).

Em mais da metade dos trimestres do Itaú, J é conhecido apenas dentro de
**±12%** — contra um movimento trimestral mediano de 4,6% que o alvo pretendia
prever.

**Cadeia de gates depois da resolução:**

| Gate | Antes do G0 resolvido | Depois | |
|---|---|---|---|
| **G0** | 3 rubricas não conformes ❌ | **0** | ✅ **resolvido** |
| **G1** | 74,14% | **72,0%** (18/25) | ❌ **decisivo agora** |
| G2 | 0,021 ✅ | **1,0464** | ❌ |
| G3 | 130,6% | **reprova em aberto**: 2 emissores < 3 clusters | ❌ |
| T1 | 0,1439 restrita | **reprova em aberto**: 16 obs < 25 para quintil | ❌ |
| T2 | passava, não informativo | **reprova em aberto**: sem baseline eleito | ❌ |

**O veredito deixou de ser condicional.** A versão anterior deste relatório
dizia que a viabilidade estava pendurada numa pergunta contábil e que havia dois
ramos. A pergunta foi respondida e **o ramo que se realizou é o ruim**: J
conforme ao contrato, nesta população, tem rótulo pior que o sinal que se
pretendia prever. Não é "indecidível por falta de dado" — é **medido**.

---

## 3. G3: poder, e por que o número que publiquei estava contaminado

> **CORREÇÃO (2026-09-09, mesma sessão).** A versão anterior desta seção
> apresentou os **~128 emissores** como limite estrutural — "não existem 128
> bancos brasileiros publicando IFRS com esta nota, então este alvo não é
> decidível nem coletando todos". **A conclusão não se sustenta.** O número não
> mede quantos bancos existem: mede **o quanto os três medidos discordam entre
> si**, e essa discordância vem em boa parte da mesma rubrica que o G0
> reprovou. Medido em `artefatos/b_dfc_01j/prontidao/sensibilidade.json`
> (`scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py`): tirando a rubrica
> suspeita, o MAE do Itaú cai de **0,2956 para 0,1555**, a dispersão entre
> emissores cai de **4,16× para 2,10×** e a exigência cai de **~60 para ~16**
> emissores na mesma série diagnóstica. A exigência continua acima dos três
> disponíveis, então **o G3 continua reprovado**; o que cai é a afirmação de
> que ele é inalcançável. Ver §3.1.
>
> **Segunda correção (2026-09-10), sobre a primeira.** Os números acima foram
> re-medidos: esta nota citava **0,3379 / 4,82× / ~75** do lado contaminado, de
> antes de `derivar_trimestre` recusar acumulado que encolhe — que retirou dois
> 4T derivados, inclusive o `juros_mercados_interbancarios|019348|2020T4` do
> próprio Itaú. E a frase "dezessete bancos com IFRS consolidado é coletável",
> que estava aqui, **também caiu**: coletar emissor não conserta defeito de
> apresentação. Ver §2-bis.



Esta onda levou a série de **50 para 71** pares (emissor, trimestre). Não
resolveu nada em G3, e a razão é aritmética.

| Baseline | MAE macro | MAE agregado | n | Acerto de direção | Cobertura |
|---|---:|---:|---:|---:|---:|
| **B0** — sem mudança | **0,1579** | 0,2168 | 58 | — abstém | **0** |
| B1 — sazonal `t−4` | 0,2151 | 0,3140 | 46 | 0,5652 | 0,79 |
| B2 — mediana de 4T | 0,1771 | 0,2458 | 55 | 0,5455 | 0,95 |
| *referência post-hoc* — "sempre sobe" | — | — | 57 | **0,6491** | 1,00 |

**O trivial ganha de novo, pela sétima vez neste projeto.** B0 — prever que o
custo de captação não muda — tem o menor erro. E o preditor de classe
majoritária ("vai subir") acerta **64,91%** da direção com cobertura total,
contra 56,52% do sazonal e 54,55% da mediana. A referência majoritária entrou
**depois** de medir e está rotulada como tal: ela só endurece a barra, nunca
resgataria o candidato.

**A cobertura vem publicada ao lado do acerto porque o §3.11 do AGENTS.md manda
literalmente isso.** B0 prevê zero e portanto **abstém da direção** — cobertura
0. Publicar "B0 é o melhor" sem a coluna de cobertura deixaria um baseline que
se cala parecer perfeito.

**O poder.** Com bootstrap agrupado **por emissor** (2.000 reamostragens), a
melhoria mínima detectável a 80% de poder é **130,6% do MAE do melhor
baseline**: para ser detectado, um modelo teria de cortar mais erro do que
existe erro. Mesmo tratando trimestre como réplica independente — o que é
ilegítimo e o pré-registro proíbe — a barra fica em **78,45%**, quatro vezes
acima do limiar de 20%.

| | Emissor | Trimestres | MAE do melhor baseline |
|---|---|---:|---:|
| | Bradesco | 15 | 0,0701 |
| | BB | 11 | 0,0662 |
| | Itaú | 32 | **0,3373** |

**Quantos emissores seriam necessários: ~128.** O erro padrão agrupado cai com
a raiz do número de clusters, e três clusters não sustentam inferência. A
estimativa é **frágil por construção** — a variância entre emissores está
medida sobre três — e serve para a ordem de grandeza, não como promessa.
Sensibilidade declarada: restrita à janela **comum aos três** (2021T1 em
diante), a conta cai para **85 emissores**, mesma ordem. A dispersão **não** é
artefato de janela: na janela comum o MAE do Itaú segue em 0,2433 contra 0,066
dos outros dois.

**A leitura que importa:** o gargalo declarado no fim da onda anterior era
"intervalo × ponto". Estava errado — e a substituição também precisou de
correção. **O gargalo é o número de emissores**, e nenhuma quantidade de
trimestres o resolve; mas o *tamanho* da exigência depende do G0, porque ela é
função da discordância entre emissores e não do universo de bancos. Ver §3.1.

---

### 3.1 O que a sensibilidade mostra, e por que ela é o nó de tudo

> ⚠️ **Seção histórica (2026-09-09), superada pelo §2-bis.** Ela está escrita no
> condicional — "*se* o componente de câmbio não for separável" — e a resposta
> chegou no dia seguinte: **não é**. O cenário chamado aqui de "pessimista" é o
> **estado real** desde 2026-09-10, e o chamado "como está" é o estado anterior,
> não conforme. Os números abaixo são de antes da guarda de acumulado que
> encolhe e **não reproduzem** contra `sensibilidade.json` v2.0.0, que mede
> **69 pares** (não 71), **40 cortados por largura** (não 41), **25 alvos** (não
> 26) e **G2 1,0464** (não 1,2334). A leitura válida está no §2-bis.5.

O G0 e o G3 **não são independentes**, e é isso que decide a viabilidade. O
cenário depende de uma única pergunta documental: **a nota separa o componente
de câmbio/valor justo dessas três linhas?**

| | Como está | Pessimista: as 3 viram NÃO IDENTIFICADAS |
|---|---:|---:|
| Pares antes do corte de largura | 71 | 71 |
| **Cortados por largura > 5%** | 9 | **41** |
| Alvos | 58 | **26** |
| **G2 ruído/sinal** (limiar < 0,10) | **0,021** ✅ | **1,2334** ❌ |
| Emissores que sobram | 3 | **2** — o Itaú sai inteiro |
| Poder interpretável? | sim | **não** (2 < 3 clusters) |

**O G2 passava com folga de 48× em parte por causa do defeito.** Se o componente
de câmbio **não** for separável, a parcela não pode ser excluída — excluir
exigiria saber o valor dela — e vira **desconhecida**, engordando o intervalo. O
resultado é que o rótulo fica **mais ruidoso que o sinal** (0,0539 contra
0,0437), 41 dos 71 pares estouram o corte de largura e **o Itaú desaparece da
população inteira**, porque a rubrica suspeita é fração grande do J dele.

**Como NÃO ler o cenário pessimista.** Nele a "melhoria detectável" cai para
0,067 e a conta devolve "~1 emissor necessário". **Isso é artefato**, não boa
notícia: sobram dois emissores cujos MAE por acaso quase coincidem (0,0708 e
0,0662), a variância entre clusters colapsa e o erro padrão fica minúsculo
justamente porque se perdeu o emissor que se comportava diferente. Dois clusters
estão abaixo do mínimo de três e o artefato sai marcado `decidivel: false`. Ler
esse 1 como poder seria aprovar por ausência de dado — §3.14 do AGENTS.md.

**Se for separável, o quadro é outro.** O diagnóstico de volatilidade (parcelas
limpas somadas como ponto — **não é J**, falta uma parcela, serve só para medir
oscilação) mostra os três emissores convergindo: 0,0741 · 0,1408 · **0,1555**,
contra 0,0710 · 0,1408 · **0,2956** com a suspeita dentro. Dispersão de 2,10×
em vez de 4,16×, e exigência de **~16** emissores em vez de ~60.

**Portanto:** a viabilidade deste candidato estava inteiramente pendurada numa
leitura de nota explicativa que custava zero e ninguém tinha feito. Não era uma
questão estatística, era uma questão contábil. **Foi feita em 2026-09-10 e
fechou pelo lado ruim** — §2-bis.

---

## 4. G2: o que o trabalho documental comprou, e o que era emprestado

> **Correção (2026-09-10).** Esta seção celebrava o G2 como "único gate que
> passa com folga". Depois de resolver o G0, **o G2 reprova em 1,0464**: o
> rótulo conforme ao contrato é mais ruidoso que o sinal. A folga de 48× medida
> abaixo é do **estado anterior**, em que J somava uma parcela que não é juros —
> ela era real como medição e falsa como conquista. O que o trabalho documental
> comprou de verdade **não** foi um rótulo preciso; foi a capacidade de
> descobrir que o rótulo não era o que dizia ser. Ver §2-bis.5.

**No estado anterior, o gate passava com folga grande.** A meia-largura mediana
do rótulo é **0,19%** contra um movimento trimestral mediano de **0,0915 em
log-razão** — 9,6% de variação. O rótulo é **~48×**
mais preciso que o sinal a prever: razão ruído/sinal **0,021** contra limiar
0,10.

A disciplina das ondas anteriores — extração recusando em vez de adivinhar,
fechamento exigido, intervalo declarado em vez de ponto inventado — é o que
permitiu **descobrir** o defeito, não o que produziu um rótulo bom. Depois da
correção, **o rótulo é exatamente a limitação deste candidato**: a frase
anterior desta seção dizia o contrário e estava errada.

Um alvo tem o intervalo cobrindo zero (não decidível na forma binária) e sai de
T1/T2. Nove observações de J saíram da população pelo corte de 5% de
meia-largura, fixado no pré-registro antes de contar quantas sobreviveriam.

---

## 5. G1 e T1/T2: o que a leitura precisa saber

**G1 — 74,14% *point-in-time*, e é fechável.** 43 dos 58 alvos têm data de
entrega certificada nos dois trimestres e em ordem correta. Os 15 restantes são
o Bradesco de 2022 (valores vindos de coluna comparativa de documento de 2023),
o Itaú de 2018 e o BB de 2023T2. **O caminho de fechar já foi validado**: são
os arquivamentos originais no catálogo IPE, o mesmo que recuperou Itaú e
Bradesco. Fechar G1 **não muda o veredito** — G0 e G3 reprovam por conta
própria — e por isso a coleta não foi feita: seria gasto sem efeito.

**T1 — defeito no meu próprio pré-registro, declarado.** O §5 manda testar
"cada componente que define mecanicamente o alvo" e nomeia `J(t)` e `J(t+1)`.
`J(t+1)` **é o futuro**: reprovar por ele diz apenas que o futuro prevê o
futuro, que não é o defeito que o T1 procura — o T1 existe para pegar
componente que está disponível na data da previsão e fabrica baseline. As duas
leituras ficam publicadas:

- **literal**, como pré-registrada: amplitude **0,4545** em `J(t+1)` — reprova;
- **restrita ao disponível na previsão**: amplitude **0,1439** em `J(t)` —
  passa, mas a **11 milésimos** do limiar 0,15.

E o 0,1439 merece uma ressalva que o §3.16 já estabeleceu: `amplitude = max−min`
sobre quintis é estatística **enviesada para cima** em amostra pequena. Aqui
isso corta contra a aprovação, não a favor: o valor observado está tão perto do
limiar que o teste é, na prática, **indeciso**. Não afirmo que T1 passa.

O veredito não muda por causa desta distinção, e é por isso que ela é
diagnóstico e não resgate: G0 já reprovou.

**T2 — passa e não informa.** Rodou primeiro no melhor baseline, B0, e o
auditor **recusou**: B0 prevê o mesmo valor para todas as 57 observações, a AUC
de escore constante é 0,5 por construção e a lacuna sai 0 — passaria por não
ter poder discriminante nenhum, que é a guarda-que-aprova-por-ausência-de-dado
condenada no §3.14. Substituído pelo melhor baseline não degenerado (B2), a
lacuna é 0,1084, abaixo do limiar 0,12 — **mas a AUC agregada é 0,4206**, pior
que o acaso, e a intra-emissor do BB é **0,0000**. Lacuna pequena entre dois
números ruins não é evidência de sinal temporal. O artefato carrega
`informativo: false` e a ressalva, para que ninguém leia este 0,1084 como
aprovação.

---

## 6. Nove defeitos corrigidos nesta onda

1. **A série não tinha 4º trimestre nenhum.** Nenhum emissor publica o 4T
   isolado, e sem derivar faltava um trimestre em cada quatro — nenhuma janela
   de doze meses fechava, o mesmo defeito medido no §3.14. Passou a derivar
   `A − M9` com **disciplina de safra**: 17 derivados, **6 recusados** com
   motivo, e safra mista é recusa (subtrair reapresentado de original devolve
   um 4T que não é a diferença de nada). **Contraprova:** `T1+T2+T3+T4 = A`
   fecha em **15 de 15** anos completos, zero falhas.
2. **Meu resumo contava registro como se fosse trimestre.** "Trimestres
   usáveis: 88" eram **66** pares distintos — o mesmo trimestre em duas safras
   contava duas vezes. Passou a publicar os dois números com nomes diferentes.
3. **Número recusado no meio da linha deslocava as colunas, em silêncio.**
   `numeros_da_linha` engolia o erro e seguia; a lista encurtava e a contagem
   de colunas saía errada. Medido no Itaú: no 2T2023 sobrava **1** número onde
   há 4 colunas, e no 3T2023 sobravam **2** — contagem que **existe** no layout
   declarado e teria sido aceita, atribuindo cada cifra ao período de outra
   coluna. Agora interrompe a linha inteira e diz por quê.
4. **T2 aprovava por ausência de poder discriminante** (§5).
5. **T1 reprovava por um componente que é o futuro** (§5) — defeito do
   pré-registro, não do código.
6. **Conformidade contratual não existia como estado.** `fechamento_confere` e
   "é isto que o contrato mandou somar" são perguntas diferentes, e só a
   primeira era medida. Agora `ResultadoJ.conformidade_contratual` existe, sai
   no JSON e em coluna própria de `auditoria_pacotes.csv`, e **reprova o G0**.
7. **`A − M9` derivava 4T credor a partir de dois operandos devedores** (achado
   ao resolver o G0). Acumulado de doze meses menor que o de nove não é
   diferença de nada — é reversão ou reclassificação, e não se sabe qual.
   Agora a derivação é **recusada** com o motivo nomeando as duas causas.
8. **Reprova em aberto derrubava o relatório inteiro.** `ReprovaEmAberto` num
   gate posterior fazia o auditor sair com um artefato mínimo, levando consigo
   G0, G1 e G2 já medidos. Agora ela entra na cadeia como gate **reprovado com
   o motivo** — continua sendo o oposto de aprovação, sem apagar o que já se
   sabia.
9. **O artefato de sensibilidade ia virar vazio em silêncio.** Ele comparava
   "com as rubricas suspeitas" contra "sem elas"; depois que elas saíram do
   pipeline de verdade, os dois cenários passariam a ser o mesmo e a tabela
   compararia o estado atual consigo mesmo. Foi **invertido** para medir o que
   a conformidade custou, com a troca declarada no campo `o_que_mudou` — e o
   defeito foi acusado por um teste, não por leitura.

### Três recuperações de extração, todas verificadas por fechamento

A extração foi de **53 para 58** documentos e a série de **50 para 71** pares.
Nenhuma das três adivinha — as três são verificadas pela aritmética da nota,
que é independente do critério usado para ler:

- **`I` maiúsculo e `l` minúsculo são o mesmo desenho** em várias fontes, e o
  extrator troca um pelo outro ("Recursos de Mercados **l**nterbancários").
  Dobrar as duas letras na chave de casamento é seguro **por medição**: nos 28
  rótulos declarados a dobra dá **zero colisões**, e nas 210 linhas das seis
  páginas afetadas **zero ambiguidades novas**. A unicidade exigida continua
  sendo a trava.
- **Célula em branco existe.** No Itaú de 1T2022 a rubrica "Outros" traz `(40)`
  na coluna do próprio trimestre e **nada** na do ano anterior. Contar cifras
  jogava a nota fora; ler em ordem atribuiria o valor de 2022 a 2021. Resolvido
  por **alinhamento geométrico de coluna** — a mesma técnica que salvou a
  âncora do BTG 4T2025 (§3.3) — com ausência devolvendo **`None`, nunca zero**.
- **Cinco glifos ambíguos no manifesto inteiro**, todos totais do Itaú de 2023
  com vírgula onde a própria tabela usa ponto. Declarados um a um com
  procedência, no padrão do `correcoes_contabeis.csv`: **nenhum dígito é
  alterado** e a guarda anti-porta-dos-fundos só aplica a leitura se o glifo
  ainda estiver lá. **A justificativa NÃO é que as parcelas somam o total** —
  usar a soma para escolher a leitura seria ajustar o dado ao teste, e o teste é
  justamente o fechamento. O argumento é de **desigualdade**: numa soma de
  parcelas de mesmo sinal o total não pode ser menor que a maior parcela, e
  `(41,923)` lido como decimal valeria 41,9 numa tabela cuja parcela isolada
  vale 17.842. A leitura decimal é **impossível**, não improvável.

---

## 7. Reprodução e verificação de não mutação

```bash
python -m scripts.piloto_bancos_dfc estender     # série (lê PDFs locais)
python -m scripts.piloto_bancos_dfc auditar      # 25 pacotes congelados
python -m scripts.auditar_prontidao_b_dfc_01j    # gates → prontidao/gates.json
python -m scripts.sensibilidade_rubricas_suspeitas_b_dfc_01j  # → sensibilidade.json
python -m pytest tests/test_piloto_bancos_dfc.py       # 115 casos
python -m pytest tests/test_prontidao_b_dfc_01j.py     #  17 casos
python -m pytest tests/test_sensibilidade_b_dfc_01j.py #  10 casos
```

Conferido nesta onda: `git diff` vazio em `corpus/`; `corpus/holdout_2T2026`
sem qualquer acesso; `artefatos/cvm.duckdb` e `cvm_treino.duckdb` com hash e
mtime inalterados; os 25 pacotes do piloto com o mesmo resultado (5 / 10 / 9,
P3 = 10). Custo: zero.

---

## 8. O que reabriria, em ordem de quem manda

1. ~~**G0 — conformidade das três rubricas.**~~ **FEITO em 2026-09-10 (§2-bis).**
   A parcela cambial **não é separável**, as duas rubricas com crédito impresso
   viraram `_NAO_IDENT` e J de Itaú e Bradesco passou a intervalo largo. G0
   aprova; o custo está medido no §2-bis.5. **Não reabre sem fonte nova:** o
   que fecharia é o emissor passar a publicar a parcela cambial dessas linhas,
   o que não está sob controle do projeto.
2. **G3 e G2 — e agora o G2 vem antes.** Com o item 1 resolvido pelo lado ruim,
   **o obstáculo mudou de lugar outra vez**: não é mais poder, é o **rótulo**.
   Com 2 emissores na população e ruído acima do sinal, coletar mais emissores
   não resolve — cada emissor novo entra com o mesmo defeito de rubrica, porque
   captação em moeda estrangeira dentro da linha de juros é prática de
   apresentação, não peculiaridade de um banco. **A exigência de ~16 emissores
   medida na série diagnóstica só vale para um J limpo, que não existe.**
   Reabre com **outro estimando** — um alvo restrito às rubricas que **não
   apresentam crédito em nenhum trimestre** (depósitos, poupança, a prazo,
   compromissadas, títulos emitidos, subordinadas).

   > ⚠️ **Correção de 2026-09-10, e ela enfraquece este caminho.** Esta alínea
   > dizia que esse conjunto tem "dispersão bem menor: CV de 0,11 a 0,54 contra
   > 0,75 da rubrica cambial do Itaú e 1,46 da do Bradesco". **Os três números
   > estavam errados e a comparação se inverte quando medida direito.** O
   > critério "sem crédito em nenhum trimestre" seleciona **15 rubricas com CV de
   > 0,11 a 0,96** — e a pior delas,
   > `juros_depositos_interfinanceiros` do Bradesco (**0,96**), é **mais
   > dispersa que as duas rubricas cambiais** que saíram de J (Itaú **0,68**,
   > Bradesco **0,60**). Além disso, o "1,46" era dessa mesma rubrica
   > interfinanceira, que **não é cambial e continua em J** — atribuí-lo à
   > "rubrica cambial do Bradesco" foi troca de referente.
   >
   > **Consequência:** ausência de crédito **não** seleciona um conjunto de
   > baixa dispersão, que era o argumento. Um estimando restrito continua
   > possível, mas o recorte precisa ser **justificado por outro critério** —
   > dispersão medida, por exemplo, com corte declarado **antes** de olhar o
   > resultado — e não pela ausência de crédito. Reproduzível sobre
   > `artefatos/b_dfc_01j/extensao/fatos.jsonl`.

   **Cuidado ao caracterizar esse conjunto:** ausência de crédito é
   *consistente* com estar livre do defeito, **não é prova** — e o caso do
   `juros_depositos_interfinanceiros` (sem crédito, CV 0,96) é o contraexemplo
   concreto. E ele não é "só reais" — `Recursos de Mercados Institucionais` do
   Itaú inclui R$ 77,9 bi de `Obrigações por Títulos e Valores Mobiliários no
   Exterior` e ainda assim mede CV 0,28, o mais baixo do emissor; por que essa
   linha não oscila e a interbancária oscila é pergunta aberta, provavelmente
   hedge, e **não foi medida**. Qualquer alvo assim é **pré-registro novo, sem
   herdar número daqui**, e com G0 próprio sobre as rubricas que sobrarem.
3. **B3 — benchmark econômico, não executado.** Exige a série da meta Selic com
   disciplina *point-in-time* (a meta conhecida no fim de `t`, nunca a
   realizada em `t+1`). Não está no repositório. O §4 do pré-registro fixou a
   consequência antes de medir: **sem B3 não há aprovação com B0–B2 apenas** —
   superar persistência sem superar a taxa de juros não demonstra nada sobre
   custo de captação, porque J é estoque × taxa.
4. **G1 — 15 vintages no IPE.** Consulta, não OCR. Não muda o veredito.

---

## 9. O que este relatório NÃO conclui

- **Não conclui que a série de J é inútil.** Ela é auditável e foi ela que
  **expôs** o defeito: sem o fechamento exigido, o intervalo declarado e a
  identidade trimestral, ninguém saberia que duas rubricas não são juros. O que
  ela não sustenta é **este** alvo. As rubricas de captação em reais seguem
  íntegras e sem um único crédito nos três emissores.
- **Não conclui que o rótulo é bom.** A versão anterior afirmava isso com a
  folga de 48× do G2. Depois da resolução do G0 o rótulo é **mais ruidoso que o
  sinal**, e a folga anterior era comprada pelo defeito (§4).
- **Não conclui que os números do piloto estão errados.** A aritmética confere
  e nenhum valor muda. O que se retrata é a afirmação de conformidade
  contratual (§2.1).
- **Não conclui que custo de captação é imprevisível.** Conclui que **este**
  alvo, nesta população, não é **decidível** — e "não decidível" não é
  "refutado". Nenhum modelo foi carregado.
- **Não conclui que o alvo é inviável em definitivo — mas ficou perto.** A
  versão de 2026-09-09 dizia aqui "**não sei qual dos dois é**" e apontava o
  §8.1 como próximo passo. **O §8.1 foi executado em 2026-09-10 e o ramo que
  saiu foi o ruim:** o componente de câmbio **não** é separável, o Itaú saiu da
  população, o rótulo ficou mais ruidoso que o sinal (G2 1,0464). O que
  **não** se conclui é que a pergunta econômica esteja morta: o que morreu é
  **este** estimando, construído sobre um J que inclui rubricas cambiais. Um
  estimando restrito às rubricas sem crédito é outro candidato, com
  pré-registro e G0 próprios — §8, item 2.
- **Não autoriza treino, nem parcialmente.** Nem o holdout, nem o painel de
  produção, nem o caminho interativo (RN07 segue integral).
- **Não fecha as lacunas de extração restantes.** **Sete** documentos de 65
  seguem sem nota, com causa diagnosticada uma a uma em `resumo.json`. E
  **três dos sete são de classe diferente do que se supunha: documento errado
  no manifesto** — os "anuais" 2019 e 2020 do Bradesco são **Comunicado ao
  Mercado de 3 páginas**, não as demonstrações, e o `bb_2023T2` é o
  *Management Report* em inglês. Isso não é falha de âncora: é a coleta ter
  pego o protocolo errado no IPE, e corrigir exige rede. Dos outros quatro,
  o `itau_2022T2` tem a **tabela ilegível** pelo `pdftotext` (a página traz os
  títulos e nenhuma cifra — mesma classe do BTG 4T2025, que precisou de OCR) e
  o `itau_2022A` tem a página embaralhada; `bradesco_2026T1` e `bb_2020A` são
  variação de rótulo por era, que é curadoria de custo zero.
