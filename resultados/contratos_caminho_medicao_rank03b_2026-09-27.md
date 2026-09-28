# Contratos do caminho até a medição — Rank 3-B

**Data:** 2026-09-27. **Escritos antes de qualquer código desta onda e antes
de a regra de prova ser aplicada a qualquer documento.**

**Pedido do responsável (27/09), literal:** "Poderia fazer tudo por sua conta
e ao final elaborar um documento para eu revisar, com tudo o que falta até o
treino?"

**Como o pedido é lido.** Cobre os passos 1 a 4 da lista de 26/09: contrato e
código da correção por conta, contrato e execução da rota de prova, painel
novo com G0 medido sem rótulo, e executor v2 testado em dado sintético. Cada
um com conferência independente. **Não cobre** o que a própria lista atribui
ao responsável ("Seu ato de congelamento") nem o que depende dele: medir o
alvo, treinar. Também ficam fora: download, chamada paga, commit, holdout e
escrita nos painéis compartilhados. O documento de revisão final diz o que
falta.

**Fontes das regras**, conferidas por hash antes de escrever:

| Documento | SHA-256 |
|---|---|
| Rascunho v2 | `0404d4076df2752155c8fbb03ee6756e3b9da44b3aa0d648bcdf0a78a4f966fd` |
| Registro de decisões de 26/09 | `9e6519db9dcc95c322371c43bee1fa47c5109d4ff6eb0193457f9a2e3470d60b` |
| Adendo ao O1 | `7f51ab27aff2604e8ec2b3a46f7e39cc12dd8aa82d52a44b2bb47dd158414b0f` |
| Manifesto de aquisição RAD | `36902f4ce38add21889bb41bfaf8c83c6264c8cfa77049acf3c5c30633cb5f8b` |
| Manifesto de correções v4 (zero linhas) | `13520e61d99f221715a26ade80dc278de15a6b30c93e30a63ed6b6aa753ff07d` |
| Painel de pesquisa governante (digest do conjunto) | `6ca635a904f11140fa24c496a11b77e961f841b72f076edd5650212afe12e6cd` |

Onde este contrato especifica o que o rascunho deixa em aberto, diz isso.
Onde muda o rascunho, a mudança entra nele como revisão datada (parte E).

---

## Parte A — Correção por conta (condições 1 a 3 do §12-bis)

**A1. Manifesto próprio:** `corpus/cvm/painel_pesquisa_rank03b/correcoes_escala_por_conta.csv`.
O manifesto por documento (v4, zero linhas) não muda e continua lido como
hoje. Colunas, exatamente estas e nesta ordem:

    id_correcao, cd_cvm, conjunto, dt_refer, versao, id_doc, sha256_pacote,
    conta, escala_declarada, escala_aplicada, base, prova, id_prova, regra,
    sha256_evidencias, sha256_conferencia, impressao_digital

- `conta` ∈ {`1`, `6.01`}; `base` = `corrigida_conta`; `regra` = `ROTA-1`;
- `prova` = `celula_propria` para a conta `1` e `cadeia_dfc` para a `6.01`;
- `id_prova` aponta um registro do arquivo de evidências da ROTA-1, cujo
  SHA-256 é `sha256_evidencias`;
- `sha256_conferencia` fixa o registro da conferência independente (B8);
- `impressao_digital` é a do construtor (linhas `1` e `6.01` do documento),
  a mesma guarda contra republicação do §3.3.

**A2. Validação antes da primeira aplicação**, pela mesma função no produtor
e no consumidor:
1. esquema fechado: cabeçalho idêntico ao da A1, sem coluna extra, ausente,
   duplicada ou fora de ordem, inclusive em arquivo sem linhas; sintaxe CSV
   estrita (a guarda de 26/09);
2. vocabulários da A1; `escala_aplicada` diferente de `escala_declarada`;
   `id_correcao` único; no máximo uma linha por (documento, conta);
3. pacote íntegro no manifesto de aquisição, com o hash declarado;
4. o arquivo de evidências tem o hash declarado; o registro `id_prova` é do
   mesmo documento e da mesma conta, tem veredito `corrigida` e escala igual à
   aplicada, e passa na validação da ROTA-1 (a mesma função do produtor;
   §4.4, regra 7);
5. o registro da conferência tem o hash declarado, aprova esse `id_prova` e
   não recusa nenhuma correção do arquivo de evidências (B7);
6. documento com linha por conta não pode ter linha no manifesto por
   documento.

Qualquer falha levanta antes de aplicar qualquer linha.

**A3. Construtor.** Cada documento passa a ter escala aplicada, base e data
da prova **por conta** (ativo e FCO). As linhas de ativo usam a escala do
ativo; os acumulados de FCO, a do FCO; o trimestre derivado registra as
escalas aplicadas ao FCO de cada operando. A correção por documento (legado)
põe a mesma escala nas duas contas. Disponibilidade (P4) por conta: a
recepção do documento ou a da prova da conta, a mais tardia, recalculada do
cadastro. Republicação: `CorrecaoObsoleta`, como hoje.

**A4. Vereditos por conta**, lidos do arquivo de evidências da ROTA-1,
fixado por hash:
- decidido para o ativo: `confirmada` ou `corrigida` por `celula_propria` da
  conta `1`;
- decidido para o FCO: `confirmada` ou `corrigida` por `cadeia_dfc` da conta
  `6.01`.

Prova de saldo não decide o FCO (§12-bis). `documentos_decididos`, da v4, não
é usado pelo executor v2.

**A5. Gates.** O G0.3 lê o ativo na escala do ativo (o valor já sai assim do
construtor). As regras 1 e 2 do §5.5 e o G0.5 leem as escalas aplicadas ao
FCO e os vereditos do FCO. A regra 3 compara a escala aplicada ao ativo em D
com a aplicada ao FCO de cada documento do TTM, com o veredito de cada conta
(parte C).

**A6. Contraprovas sintéticas:**
- linha da conta `1` muda só o ativo; o FCO sai idêntico, valor a valor, ao
  do painel sem correção;
- linha da conta `6.01` muda só o FCO;
- coluna extra, ausente, duplicada ou fora de ordem, com e sem linhas →
  recusa antes de aplicar;
- evidência `confirmada` ou `indecidivel`, de outro documento, de outra conta
  ou com outra escala → recusa;
- hash de evidências ou de conferência divergente, prova sem aprovação na
  conferência, ou conferência que recusou outra correção → recusa;
- duas linhas do mesmo (documento, conta), ou documento também no manifesto
  por documento → recusa;
- republicação → `CorrecaoObsoleta`;
- série M U M com prova do ativo do documento do meio → o G0.3 perde os dois
  saltos, e o trimestre de FCO continua heterogêneo e sem veredito.

---

## Parte B — ROTA-1: prova de escala por célula própria e cadeia de identidades

**O que decide.** O formulário (XML do pacote) traz o número bruto. As
demonstrações e notas que a própria companhia anexou **ao mesmo pacote**
imprimem esse número sob uma unidade que ela declara. Se um PDF do pacote
imprime **exatamente** os dígitos do formulário numa tabela em milhares, o
formulário está em milhares. Se imprime esses dígitos divididos por mil numa
tabela em milhares, o formulário está em reais. Só a declaração de milhares
decide (tabela S2, RC1-bis): "em reais" declara a moeda com frequência e
nunca prova escala.

**Por que é uma regra nova, e não a v3 de volta.** A v4 exigia cabeçalho
local de duas linhas exatas e proibia procurar o número fora da célula da
data corrente. Não reconheceu tabela nenhuma nos 405 documentos. O risco que
a v4 fechava era o da v2/v3: **um** número casado fora de contexto, como o
"1.000" de ações de ESC-0101. A ROTA-1 fecha o mesmo risco por outro caminho:
- a linha tem de conter **dois** valores exatos da mesma conta no mesmo
  formulário, o corrente e uma âncora;
- tem de conter o rótulo da conta;
- a unidade tem de valer para aquela linha, com veto a qualquer declaração
  contrária.

A coluna não precisa ser identificada pelo cabeçalho: os mesmos dígitos, na
mesma tabela, estão sob a mesma unidade, em qualquer coluna. A §12-bis prevê
esta via ("Reabrir a adjudicação exige outro contrato de extração/prova").

### B1. Conjunto fixado antes de ler

Calculado por código a partir do painel de pesquisa governante (digest
`6ca635a9…`, sem correções), na população do v2 (sem `ll3_09`, `ll3_13` e
bancos), olhando só estrutura: datas, estados, rótulos de escala e o ativo,
que o G0.3 já lê.

| Parte | Documentos |
|---|---|
| T_A | Todos os documentos dos trechos minoritários que tocam algum salto do G0.3. Trecho: linhas de ativo válidas entre dois saltos. Minoritário: rótulo declarado diferente do mais frequente da companhia, contado em linhas de ativo válidas |
| T_B | Os dois documentos de cada salto |
| T_C | Os operandos dos trimestres de FCO válidos com escalas declaradas heterogêneas |
| K (controles) | Os 30 documentos de controle do escopo v4: companhias só `MIL`, na ordem fixada em 16/09 |

Documento sem pacote local fica de fora e é publicado como `sem_pacote`.
Esta onda não baixa nada.

### B2. Leitura

- Pacote conferido pelo hash do manifesto de aquisição.
- Do formulário: consolidado e individual, só as contas de balanço
  necessárias. Para a prova por célula, `1` e `1.01.01`. Para o elo do
  balanço, `1.01`, `1.02` e os filhos diretos de `1.01`. As contas 6.x só na
  cadeia (B5).
- Texto de **todos** os PDFs anexados, página a página, por
  `pdftotext -layout` (Poppler 24.02.0). O grupo e o nome do anexo são
  publicados.
- Nenhum grupo é excluído. Número gerencial não coincide com os dois valores
  contábeis exatos que a linha precisa conter (B3).

### B3. Prova por célula própria, para a conta `a` ∈ {`1`, `1.01.01`}

1. **Valor.** `v` é o valor consolidado de `a` na data corrente: único e não
   nulo no formulário, com módulo ≥ 1.000. Tem de ser igual ao valor da mesma
   conta no CSV da CVM (`declaracoes`, `ÚLTIMO`), que é o número que o painel
   usa.
2. **Âncora.** Outro valor exato da mesma conta no mesmo formulário:
   consolidado de outra data, ou individual da data corrente. Diferente de
   `v`, com módulo ≥ 1.000.
3. **Linha.** Uma linha de texto que contém `v` e a âncora como números
   inteiros, nas formas abaixo. Separador de milhar obrigatório, parênteses
   admitidos, nenhum dígito ou separador colado ao número.
   - `bruto`: como estão;
   - `dividido`: divididos por mil e arredondados ao inteiro mais próximo
     (empate: aceita-se o arredondamento para cima e o para par), com módulo
     impresso ≥ 1.000.
4. **Rótulo.** O texto antes do primeiro número, sem espaços e em minúsculas,
   contém o rótulo da conta:
   - conta `1`: `totaldoativo`, `ativototal`, `totaldosativos` ou
     `totalativo`, sem `circulante` depois;
   - conta `1.01.01`: `caixaeequivalentedecaixa` ou
     `caixaeequivalentesdecaixa`; ou então a linha se chama `total` e o
     título mais próximo acima, na mesma página, fala de caixa e equivalentes
     de caixa.

   Linha que fala de ações é recusada.
5. **Unidade.**
   - Decide a declaração de unidade mais próxima **acima** da linha, na
     mesma página. Se for de milhares, vale. Se for de reais ou de milhões, a
     linha não prova nada.
   - Sem declaração acima da linha, vale a declaração de apresentação do
     anexo (RC1: título de página ou objeto da apresentação), com três
     condições: ser de milhares; o anexo não ter declaração de apresentação de
     outra unidade; a página da linha não ter declaração de reais nem de
     milhões.

   Os vocabulários ficam fechados no código e são publicados no pin.
6. **Decisão por (documento, conta).**

   | Linhas aceitas | Resultado |
   |---|---|
   | só `bruto` sob milhares | formulário em `MIL` |
   | só `dividido` sob milhares | `UNIDADE` |
   | as duas | `conflitante`, indecidível |
   | nenhuma | indecidível, com o motivo mais avançado alcançado |

   Veredito: `confirmada` ou `corrigida`, contra a escala declarada.

### B4. Elo do balanço: o caixa pela prova do ativo

Vale só quando o ativo tem prova por célula e o caixa não. No formulário,
consolidado, data corrente, com diferença ≤ 1 em bruto, fecham:
- `1 = 1.01 + 1.02`;
- `1.01 =` soma dos filhos diretos de `1.01`, com `1.01.01` entre eles, não
  nulo.

Então o caixa tem a escala provada do ativo. **Por quê:** o ativo provado é
igual ao total impresso pela companhia em milhares. Se o caixa estivesse
digitado em outra base, a soma do formulário diferiria desse total em 999
vezes o caixa, salvo compensação exata entre parcelas.

### B5. Cadeia da DFC para a conta `6.01`

Vale sob a parte 2 do adendo ao O1, fixado por hash. Condições:
- **Âncora:** `1.01.01` com escala provada (B3 ou B4), não nula.
- **Identidades:** no formulário, consolidado, no período corrente da DFC
  (início do exercício até a data de referência, único), com diferença ≤ 1
  em bruto:
  - D1: `6.01 + 6.02 + 6.03 + 6.04 = 6.05` (conta ausente vale zero, salvo
    `6.01` e `6.05`);
  - D2: `6.05.01 + 6.05 = 6.05.02`;
  - D3: `6.05.02 = 1.01.01`.
- **Igualdade entre fontes:** o valor da `6.01` no formulário é igual ao do
  CSV (O1.3).

Se tudo fecha, a `6.01` tem a escala da âncora. **Por quê:** D3 liga o caixa
do balanço, provado, ao saldo final da DFC. D1 e D2 obrigam os fluxos
digitados a reconstituir esse saldo. Um FCO digitado em outra base quebraria
a igualdade, salvo em dois casos: fluxo nulo, em que a escala não muda o
valor, ou compensação exata entre fluxos.

**Saída só booleana.** Por documento, grava-se se cada identidade fecha e a
conclusão. Nenhum valor, resíduo, sinal ou magnitude de conta 6.x é gravado,
impresso ou retornado. Os valores vivem só dentro da função que devolve os
booleanos. Contas, identidades e tolerância são as desta cláusula e não
mudam depois de vistos os booleanos.

### B6. Teste fora dos documentos de desenho

Exigido pela cláusula 6 da parte 2 do adendo.
- **Amostra:** documentos de T ∪ K com prova por célula do ativo **e** do
  caixa, fora dos 22 da seleção GEOM-1 e dos documentos de desenho desta onda
  (parte F).
- **Critério, fixado antes:** zero discordâncias de escala entre ativo e
  caixa, com pelo menos 10 documentos.
- **Se falhar,** B4 e B5 não produzem prova, e só a conta `1` entra no
  manifesto.

O teste examina a premissa de que B4 e B5 dependem, o formulário digitado
numa base só, no ponto em que ela pode ser observada sem ler FCO.

### B7. Parada

A ROTA-1 não produz manifesto se algum controle K receber `corrigida` em
qualquer conta, ou se a conferência (B8) recusar alguma correção. Revisar a
regra é versão nova, com contrato e conferência novos.

### B8. Conferência documental independente

Feita pelo `auditor-conformidade`, somente leitura. Alcança toda correção e
uma amostra de dez confirmações sorteada com a semente `20260911`. O auditor:
- relê o XML e a página com ferramentas próprias, sem usar o extrator como
  árbitro;
- confirma conta, número, âncora e unidade;
- para a `6.01`, recalcula em memória os booleanos da cadeia, sem publicar
  valor.

### B9. Saídas

Em `artefatos/rota_prova_rank03b_2026-09-27/`, que recusa sobrescrita:

| Arquivo | Conteúdo |
|---|---|
| `pin.json` | Hashes do contrato, do código, dos vocabulários, do adendo, do painel e do manifesto de aquisição; versão do Poppler; os conjuntos T e K com hash |
| `evidencias.jsonl` | Um registro por documento e conta. As provas saem com todos os dígitos trocados por marcador e com a posição: anexo, página, linha e ordem dos números na linha |
| `resumo.json` | Vereditos por papel, conta e motivo; o teste B6; os controles |

Mais o manifesto por conta. Um teste varre as saídas: nenhum valor de conta
6.x aparece em lugar nenhum.

### B10. Contraprovas sintéticas da ROTA-1

Sobre texto e formulário sintéticos:
- ativo em milhares nas notas e formulário declarado em reais → `corrigida`
  para MIL;
- formulário de fato em reais e notas em milhares imprimindo ÷1.000 →
  `confirmada` UNIDADE (o caso ESC-0101);
- número só em linha de ações, sem âncora, sem rótulo ou em "Total do ativo
  circulante" → nada;
- declaração de reais ou de milhões acima da linha, mais próxima que a de
  milhares → nada;
- página com "em reais" e sem cabeçalho local → nada;
- `bruto` e `dividido` no mesmo documento → indecidível;
- número colado a dígito ou separador → nada;
- formulário diferente do CSV → indecidível;
- elo do balanço com identidade aberta → sem elo;
- cadeia com D3 aberta → sem prova do FCO;
- saída da cadeia varrida: nenhum número de 6.x;
- controle corrigido → sem manifesto.

---

## Parte C — Executor v2

**Arquivo:** `scripts/executor_v2_rank03b.py`. O rascunho v2 é a
especificação. As remissões abaixo são às suas seções, e esta parte só fixa
o que ele deixa ao código.

**C1. Dois modos.**
- `estrutural`, o padrão: G0, amostra sem rótulo, G0.5 e G1. Grava só o que
  o O1 permite antes do congelamento (C8).
- `medicao`: recusa se o pré-registro não estiver congelado (C9). Monta a
  mesma amostra sem rótulo e exige G0 e G1 aprovados. Calcula `y` sobre a
  mesma amostra, com as chaves conferidas. Depois T1, T2, baselines e
  veredito (§10).

**C2. População (§3.2).** Exclui `ll3_09_%`, `ll3_13_%` e bancos. Plano
`ll3_13_*` diferente de `ll3_13_48e4cd07` interrompe a execução. Publica
quantos saltos do G0.3 e quantas linhas de ativo válidas pertencem às
excluídas.

**C3. G0 (§5).**
- G0.0 e G0.4 como hoje.
- G0.1 (§5.1), pela linhagem, sem ler valor. Reprova com:
  - dois trimestres válidos para a mesma (companhia, trimestre);
  - trimestre com dois operandos do mesmo período.

  Publica os trimestres válidos derivados entre métodos, em quantas
  companhias, e quantas observações os usam na janela ou no rótulo.
- G0.2 pelas datas.
- G0.3 pela função do auditor, sobre as linhas de ativo válidas da população
  do v2.
- G0.5 depois da amostra (C5).
- Lista o erro demonstrado de `140867` com o estado dele: corrigido pelo
  manifesto por conta, ou pendente.

**C4. Amostra (§§2, 5.5, 6.1, 6.2).**
- Os estados da regra 1 do §5.5 saem das escalas aplicadas ao FCO e do
  veredito do FCO.
- As datas candidatas, a identificação de q1 e a deduplicação por
  (companhia, q1), fica a maior D, seguem o §6.1.
- Os doze motivos, na ordem do §6.1, cada data saindo no primeiro que a
  remove.
- A janela é formada pelos oito trimestres mais recentes disponíveis em D,
  com o trimestre da regra 1 **no seu lugar**.
- A regra 2 é aplicada sobre os documentos da janela, os de S1 e os de S2,
  separadamente.
- A regra 3 e o `sd8 = 0` tornam o componente ausente sem remover a
  observação.
- A linhagem guarda, de cada trimestre, os documentos operandos.
- A amostra sai ordenada por (companhia, D).
- O rótulo só é somado com `calcular_rotulo=True`.

**C5. G0.5 e G1**, recalculados da linhagem, fora da construção.
- G0.5 (uso zero): nenhum trimestre da regra 1 na janela ou em q1–q4; nenhuma
  observação na regra 2; nenhuma `fco_ttm_sobre_ativo` presente no caso da
  regra 3.
- G1: os itens da v1, o G1.4 por conta e nenhuma (companhia, q1) repetida.
- Amostra vazia reprova.

**C6. T1** pela função do auditor, idêntica à v1 (§7). **Baselines** pela
função do auditor (§9).

**C7. T2 do §8.1:**
- piso de 30 companhias com os dois rótulos;
- 2.000 reamostragens por companhia inteira, semente `20260911`, companhias
  ordenadas por `cd_cvm` antes do sorteio;
- reamostragem válida quando as duas AUCs são calculáveis;
- frequência sobre as válidas, com mínimo de 40;
- IC 95% percentil da lacuna;
- vereditos REJEITADO, INDECIDÍVEL e aprovado, como no §8.1.

**C8. O que o modo estrutural publica (O1).** Publica:
- G0 com os inventários;
- as perdas do G0.5 por regra, na forma do §5.5;
- G1;
- observações finais, no total e por companhia;
- os descartes dos motivos 1 a 10 e 12.

**Não** publica o total da grade, as datas candidatas por companhia, o
motivo 11, nem nenhuma chave `y`, `rotulo`, `taxa_do_evento`, `s1`, `s2` ou
de T1, T2 e baseline. Um teste varre o artefato.

**C9. Trava do congelamento.** O modo `medicao` exige quatro condições.
- O arquivo do pré-registro não tem "RASCUNHO" no nome.
- A primeira linha do arquivo não tem "RASCUNHO".
- O SHA-256 do arquivo é igual ao informado na chamada.
- O texto contém, por extenso, os SHA-256 fixados:
  - digest do painel medido;
  - manifesto por conta;
  - evidências da ROTA-1;
  - adendo ao O1;
  - código do executor.

As três primeiras e os pins que não dependem do painel são conferidos antes de
ler o painel. O digest só existe depois de o painel ser construído: é
conferido logo em seguida, antes de montar a amostra. Sem qualquer condição, a
execução para sem calcular nada do alvo. *(Emenda de 27/09, antes do código da
parte C: a primeira redação mandava conferir tudo antes de ler o painel, o que
é impossível para o digest.)*

**C10. Contraprovas sintéticas.** Todas as listadas nos §§3.2, 5.1, 5.5, 6.1
e 8.1 do rascunho, mais estas:
- modo estrutural com rótulo pedido → recusa;
- as quatro condições da C9, cada uma isolada → recusa;
- artefato estrutural sem as chaves proibidas;
- nenhum conjunto de números publicados recompõe o motivo 11 por soma ou
  subtração;
- mesma entrada, dois processos, mesma saída byte a byte.

---

## Parte D — Painel novo e G0 sem rótulo

**D1. Construção.**
- **Entradas:** os 31 ZIPs pinados; o universo lido somente leitura do
  painel de treino, como hoje; o manifesto v4, com zero linhas; o manifesto
  por conta da ROTA-1, se B7 permitir.
- **Destino:** `artefatos/painel_pesquisa_rank03b_v2/`, com painel e
  manifesto do painel. O painel governante de 18/09 é preservado.

**D2. Medição.** O executor v2 roda em modo estrutural e publica
`artefatos/executor_v2_rank03b/estrutural.json`.

**D3. Sem ajuste depois de ver.** Se o G0 continuar reprovado, o resultado é
publicado assim. Nada muda depois de visto o G0: nem a regra da ROTA-1, nem o
conjunto, nem a aplicação de correções provadas, nem o limiar. O mesmo vale
para a perda do §5.5.

**D4. Pins propostos para o congelamento:**
- digest do painel novo;
- hash do manifesto por conta;
- hash das evidências da ROTA-1;
- hash do adendo;
- hash do executor;
- hashes das entradas.

Vão ao rascunho como **propostos**. Só o ato do responsável os torna
congelados.

---

## Parte E — O que muda no rascunho v2 (revisão datada de 27/09)

- **§4:** o painel novo e os pins propostos. A ROTA-1 vira a regra vigente do
  manifesto por conta, e a v4 fica histórica.
- **§12-bis:** subseção nova "Regra vigente: ROTA-1 (27/09)", com as partes
  A e B. A cadeia da DFC é a rota de prova do FCO que a própria §12-bis
  previa, agora com contrato.
- **§5.5 e §6:** o "decidido" lido por conta, das evidências da ROTA-1 (A4).
- **§11.8, novo:** o que esta onda viu (parte F).
- **§13 e §14:** condições de falsificação e artefatos novos.

---

## Parte F — Exposição declarada e entrega

**O que foi visto antes deste contrato:**
- O G0 reprovado (132 saltos, limite 112) e a estrutura dos saltos:
  trechos, rótulos, 28 documentos isolados que tirariam dois saltos cada.
  Estrutura, sem rótulo.
- **Levantamento de disponibilidade**, em 27/09, sobre os 103 documentos de
  T_A com pacote local. Contou se o valor exato de `1` e de `1.01.01`
  aparecia numa linha de algum anexo junto do comparativo: 45 e 60. Não leu
  unidade nem decidiu escala. As saídas intermediárias se perderam na limpeza
  do diretório temporário; os números estão aqui.
- **Documentos de desenho**, cujas páginas foram lidas para escrever B3:
  `98282` (003328, 3T2020, que é também da verificação GEOM-1), `98645`
  (003549, 3T2020), `70099` (019658, 3T2017) e `145753` (018414, 2024). Serão
  adjudicados pela regra congelada como os outros, marcados como desenho, e
  ficam fora da amostra do B6.
- Nenhum valor de FCO foi lido nesta onda antes deste contrato. Nenhuma
  estatística de rótulo foi calculada.

**O G0 do painel novo não foi visto**, e só será depois de o manifesto estar
final (D3).

**Emenda antes do código (27/09).** A primeira redação da A1 não fixava a
conferência no manifesto: o consumidor não teria como saber se a B8 aprovou
cada prova, e a exigência não entraria na condição de aprovação (§4.4, regra
7). Acrescentadas a coluna `sha256_conferencia` e a condição 5 da A2, antes de
qualquer código.

**Entrega.**
- Testes sintéticos de A, B e C, e suíte completa verde.
- `auditor-conformidade` ao fim de cada onda: código de A e C; ROTA-1 com a
  conferência B8; painel novo com G0.
- Revisão datada do rascunho; `MEMORY.md`, `AGENTS.md` e becos atualizados.
- Documento de revisão para o responsável, com tudo o que falta até o
  treino.
- Sem commit, sem congelamento, sem medição do alvo e sem treino.

---

## Emenda pós-auditoria (27/09), antes da primeira execução em dado real

O `auditor-conformidade` conferiu o código das partes A, B e C antes de a
ROTA-1 tocar o dado real e deu **NÃO APTA**: 2 achados ALTA, 6 MÉDIA e 9 BAIXA.
A regra fica congelada na primeira execução, por isso todos foram tratados
antes. Nenhuma prova tinha sido produzida, nem o G0 do painel novo visto.
Achados, na ordem do parecer:

| Achado | Defeito | O que mudou |
|---|---|---|
| A1 (ALTA) | A seleção GEOM-1 era lida como texto de dicionários: nenhum documento de desenho saía do B6, e o erro favorecia aprovar | Ids tirados do campo `id_doc`, 22 exigidos, arquivo conferido pelo hash publicado em 18/09 (`b3e85417…`). O consumidor recalcula as marcas de desenho, GEOM-1 e controle das fontes fixadas |
| A2 (ALTA) | O veto de unidade não pegava "Em reais" sem parêntese, "(R$)", "Valores em R$" e "em unidades de reais". A ressalva "por ação" neutralizava até "milhões" | Vocabulário de reais ampliado. Milhões vetam sempre. A menção de reais só é neutra numa ressalva por ação da própria linha que declara milhares |
| M1 | "Decidido" não estava amarrado a "aplicado" | O executor confere que todo documento e conta decidido tem, no painel, a escala que a prova decidiu |
| M2 | Manifesto sem a ROTA-1 era ignorado em silêncio | Os dois entram juntos, ou nenhum |
| M3 | O pin do congelamento cobria só o arquivo do executor | O pin passa a ser um digest de todo o código de medição (auditor de 11/09, painel, gates, `src/normalizacao.py` e os demais). O adendo é relido do disco. `medicao.json` não é sobrescrito |
| M4 | Decisões do consumidor sem contraprova | Contraprovas para: B6 no consumidor, prova de saldo que não decide o FCO, parada B7 e conferência. Registro decidido tem de ter contagem zero da outra forma |
| M5 | A amostra de confirmações da B8 não tinha efeito | A conferência passa a ter o campo `confirmacoes`, exigido igual à amostra recalculável, e uma recusa ali também para tudo |
| M6 | Contraprovas fracas | Novas contraprovas para: q1 censurado contra motivo 1, motivo 4 antes do 5, regra 2 no G0.5, G1.4 do ativo, ordem do T2, ativo de documento fora do TTM, recomposição do motivo 11, determinismo entre processos e trava do rótulo |
| B1 | G0.5 aprovava amostra vazia | Reprova |
| B2 | G1.4 ignorava as provas das correções legadas | Entram, nas duas contas |
| B3 | A 6.01 do CSV era lida para todos os documentos e passava entre processos | A cadeia roda no processo principal e lê a 6.01 do CSV dentro da função |
| B4 | Âncora "não nula" com tolerância 1 | Módulo ≥ 1.000, como na prova por célula |
| B5 | A linha "total" do caixa aceitava qualquer título até 15 linhas acima | Vale só o título mais próximo, pulando dados e cabeçalhos |
| B6 | Correções por conta sem conferência de conteúdo | O executor exige o manifesto validado, com o hash do conteúdo e o da origem |
| B7 | O consumidor confiava nas marcas gravadas | Tratado com A1 |
| B8 | Um erro num documento derrubava a execução depois do pin | O erro vira indecisão do documento, com o tipo e sem a mensagem |
| B9 | "Companhias que saem inteiras" contava saída por qualquer motivo | A chave passou a dizer o que conta: perda no §5.5 e nenhuma observação final |

**Motivo 11, recomposição.** A auditoria mostrou que o G0 publicava o número
de linhas válidas de FCO da população. Sem colisão de disponibilidade, esse
número menos:
- as linhas do estado da regra 1;
- os motivos publicados;
- as observações finais,

dá o motivo 11 exato. O número não sai mais antes do congelamento, e um teste
mostra, num fixture sem colisões, que a subtração seria exata.

**Trava do rótulo (C10).** Somar o rótulo exige o registro do congelamento. Os
testes sintéticos passam um registro explícito, e o modo estrutural não o tem.

**Duas substituições de teste, declaradas no próprio arquivo:**
- "lucro por ação (em reais)" era neutro e passou a vetar (A2);
- a aritmética de duas fixtures sintéticas foi corrigida sem mudar asserção de
  regra.

### Reconferência (27/09), ainda antes da execução

O mesmo auditor reconferiu a emenda. Deu **NÃO APTA** por um único item, N1;
o resto ficou fechado ou em BAIXA. Tratamento:

| Achado | Defeito | O que mudou |
|---|---|---|
| **N1** | O veto de unidade ainda aceitava tabela em reais como milhares. Três formas: declaração quebrada entre duas linhas (regressão da emenda), "R$" ou "(Reais)" sozinhos como cabeçalho de coluna, e dois cabeçalhos lado a lado na mesma linha | Cada coluna da linha crua (três espaços ou mais) é classificada sozinha. Pares de linhas adjacentes também vetam, no local, na página e na apresentação; o par nunca faz valer milhares. "R$" sozinho e "(Reais)" vetam, salvo "R$" como moeda da própria declaração de milhares do segmento. O trecho de unidade publicado guarda as colunas, e o consumidor classifica igual |
| T1 | Marcas e veto da página sem contraprova de ligação | Contraprovas por `validar_arquivo` e de veto da página depois do título |
| T2 | Ligações de `carregar_entradas` e a conferência do pré-registro antes do painel sem contraprova | Contraprovas sobre painel sintético |
| T3 | O teste "motivo 4 antes do 5" passava com a ordem invertida | Fixture em que toda janela com a lacuna tem o censurado; o motivo 5 tem de ser zero |
| B-a | A trava do rótulo aceitava qualquer `dict` com hash | Só aceita o objeto `Congelamento`, que a verificação do congelamento emite. O dos testes é marcado sintético e recusado na medição real |
| B-b | O inventário do painel, com as linhas por estado, entra no artefato | Guarda em memória antes de gravar. As colisões de disponibilidade mais as linhas válidas de FCO das companhias excluídas têm de ser maiores que zero; senão o artefato não sai. Nada disso é publicado |
| B-c | O `except` largo cobria a lógica da regra | Só erro de leitura vira indecisão. Erro de lógica derruba a execução, com `falha.json` ao lado do pin |
| B-d | Os 30 controles não eram exigidos nas evidências | Exigidos |
| B10 | A parte E do rascunho não foi aplicada | É do plano: entra depois da execução, com os resultados (parte E) |

Custo aceito: "Valores expressos em milhares de reais (R$)" deixou de vetar,
porque "R$" é a moeda da própria declaração. Continuam vetando os casos em que
"R$" aparece sem declaração de milhares no mesmo segmento.

### Verificação curta (27/09): APTA COM RESSALVAS

O auditor confirmou que o N1 fechou nas três formas, sem falsa prova nova, e
achou o **N2 (MÉDIA)**. O consumidor tirava os `#` do trecho mascarado e
reclassificava "R$ 1.000" como "R$ .", o que disparava o veto do símbolo:
- o registro do próprio produtor seria recusado;
- a execução única morreria depois do pin.

Correção: o consumidor troca `#` por `0`, com contraprova. Três BAIXAs também
foram fechadas:
- `validar_arquivo` entrou no bloco que grava `falha.json`;
- a cadeia só converte erro de leitura em identidade não fechada;
- o pin publica o vocabulário do símbolo e o separador de colunas.

**Limite declarado, que fica.** Uma declaração de milhares em OUTRA coluna,
acima, vale para a linha: a B3.5 não olha coluna. O layout é raro, e as
correções que dependerem dele passam pela conferência B8.

---

## ROTA-2 (27/09): a ROTA-1 rodou e não produziu manifesto

**O que aconteceu.** A ROTA-1 rodou uma vez sobre os 300 documentos de T ∪ K
(`artefatos/rota_prova_rank03b_2026-09-27/`). Os números:

| Conta | Corrigidas | Confirmadas |
|---|---:|---:|
| `1` (ativo) | 43 | 52 |
| `1.01.01` (caixa) | 50 | 74 |
| `6.01` (FCO) | 36 | 56 |

Todas as correções vão de UNIDADE para MIL. O teste B6 aprovou (51
documentos, zero discordâncias), e nenhum controle foi corrigido.

**Conferência B8.** Dois conferentes independentes aprovaram 125 das 129
correções e as 10 confirmações da amostra. Recusaram quatro:
- **`60719`, ativo e caixa:** a unidade não foi demonstrada. A prova está num
  comentário de desempenho (grupo 192), numa página sem declaração de
  unidade. A regra tomou como "apresentação do anexo" legendas "(R$ mil)" de
  outras tabelas, no topo das páginas. **É um defeito da regra.**
- **`80868`, ativo e caixa:** a recusa se apoia no item 4 como o principal o
  redigiu ("o formulário declara UNIDADE"). O formulário interno da companhia
  declara MIL; o envelope RAD e o CSV, que o painel usa, declaram UNIDADE.
  Números, rótulo e unidade foram conferidos. A correção para MIL concorda com
  as duas declarações. É defeito da redação da conferência, não da prova.

**Pela B7, a ROTA-1 não produz manifesto.** O registro da conferência está
em `conferencia.json`, ao lado das evidências, e o código que rodou está
preservado em `codigo_rota_1.py`, com o hash do pin.

**O que a ROTA-2 muda.** Só estreita a regra; nenhum caminho de aceitação é
acrescentado.
1. Uma declaração de MILHARES só conta como apresentação do anexo com o objeto
   da apresentação por perto ("notas explicativas", "demonstrações
   financeiras", "informações trimestrais" e afins). A posição no título da
   página já não basta. Declarações de outra unidade continuam vetando também
   pelo título.
2. Só há apresentação em notas e demonstrações, grupos 193 e 412. Em
   comentário de desempenho, release e outros anexos, só o cabeçalho local
   vale.
3. O registro guarda, só como informação, os códigos de escala do envelope RAD
   e do formulário da companhia.

**Conferência da ROTA-2.** Nova, com dois conferentes, sobre toda correção e
uma amostra nova de dez confirmações. O item 4 fica escrito assim: a escala
declarada no registro é a do CSV, a que o painel aplica; a correção é para a
escala provada; a do formulário interno é registrada, e se divergir, isso vai
na nota, sem recusar por esse motivo.

**Exposição.** A ROTA-2 foi escrita conhecendo os números da ROTA-1 e as
quatro recusas. Por só estreitar a regra, não pode aumentar as correções. O G0
do painel novo continua não visto.

**Verificação da ROTA-2 (27/09): APTA.** O auditor confirmou três pontos:
- a mudança só estreita a regra;
- ela fecha o `60719`;
- não pode aumentar as correções neste dado, porque a ROTA-1 não teve nenhuma
  indecisão por conflito.

Quatro BAIXAs foram fechadas antes de rodar:
- o consumidor recusa "apresentação" fora dos grupos 193 e 412;
- o pin traz os grupos e os objetos da apresentação, e também o pin e o código
  da ROTA-1;
- o campo do envelope foi conferido em pacotes reais (`80868`: envelope
  UNIDADE, formulário da companhia MIL);
- a coluna `regra` do manifesto (A1) e os `id_prova` passam a dizer `ROTA-2`.

## Execução da ROTA-2, conferência e manifesto (27/09)

**Evidências.** `artefatos/rota_prova_rank03b_v2_2026-09-27/evidencias.jsonl`
(SHA-256 `e2001e06…4c24`), 300 documentos. Correções: 42 do ativo, 48 do
caixa (41 por célula própria e 7 pelo elo do balanço) e 35 do FCO pela cadeia
da DFC. B6 passou com 50 documentos e nenhuma discordância, e nenhum controle
foi corrigido.

**Conferência B8.** Dois conferentes independentes, cada um com contexto
próprio, e **nenhuma recusa**:
- o primeiro aprovou as 83 correções por célula própria;
- o segundo aprovou as 42 por elo e cadeia e as 10 confirmações sorteadas com
  a semente `20260911`.

O registro fica em `conferencia.json` (SHA-256 `734e7e70…aa68`), validado pelo
próprio consumidor antes e depois de gravado. Com isso ficam decididos 94
documentos no ativo e 90 no FCO. Os casos limítrofes estão no registro:
`113026-1.01.01`, provado só pelo saldo final da DFC impressa; `80868`, com a
divergência entre o formulário interno e o envelope; e `98282-1.01.01`, que
virou indecidível. As duas exposições O1 do segundo conferente também estão
lá, ambas booleanas.

**Manifesto por conta.** `corpus/cvm/painel_pesquisa_rank03b/correcoes_escala_por_conta.csv`,
com 77 linhas (42 da conta `1` e 35 da `6.01`), SHA-256 `f26ede4d…313c`.
Validado pelo consumidor na gravação e de novo na releitura.

### Emenda C8 (27/09): o estado do painel é dado, não chave

**Achado.** Na primeira execução do modo estrutural sobre o dado real, a guarda
de publicação recusou gravar. O motivo: o inventário do painel conta as linhas
de FCO trimestral por estado, e um desses estados se chama `lacuna`, o mesmo
nome da estatística do T2 que o C8 proíbe como chave. A guarda falhou fechada,
antes de gravar qualquer arquivo. A causa estava no teste: `executar_estrutural`
não tinha contraprova nenhuma, e os painéis sintéticos dos outros testes nunca
publicavam o inventário com esse estado.

**O que não muda.** A guarda continua recusando `lacuna` como chave em qualquer
nível, e não ganhou exceção por caminho.

**O que muda.** O artefato estrutural publica cada contagem por estado do
inventário como uma lista de pares `{estado, linhas, companhias}`, na ordem do
vocabulário fechado:
- FCO trimestral: `ESTADOS_FCO` do painel;
- ativo: `ESTADOS_ATIVO`;
- FCO acumulado: `ok`, `valor_nulo` e `conflito_de_declaracoes`.

Um estado fora do vocabulário derruba a publicação com `PublicacaoInsegura`.
Nenhuma contagem nova é publicada: o mesmo inventário já saiu no lote C, em
`gates_g0_g1.json`.

**Contraprovas:**
- `executar_estrutural` roda de ponta a ponta sobre um painel sintético que
  tem o estado `lacuna` e a folga do motivo 11 positiva;
- o inventário cru, com o estado como chave, continua sendo recusado pela
  guarda;
- o vocabulário inteiro passa sem perder nenhuma contagem;
- um estado desconhecido derruba a publicação;
- um estado ausente não vira zero;
- os estados do acumulado que não são `ok` estão contidos nos do trimestral.

O fixture de ligação passou a substituir só a conexão em memória. Antes, a
gravação do painel em arquivo também caía nela.

### Emenda C9 (27/09): a conferência vira pin por nome

**Achado.** Os pins propostos no primeiro artefato estrutural não traziam o
registro da conferência, que a §13 do rascunho manda fixar. Ele estava fixado
só por transitividade: cada linha do manifesto carrega `sha256_conferencia`,
e o consumidor confere esse hash contra o arquivo. Essa garantia deixaria de
existir com um manifesto vazio, e é o tipo de exigência que fica fora da
condição de aprovação (§4.4, regra 7). Além disso, o pin das evidências se
chamava `evidencias_rota_1` e carregava o hash da ROTA-2.

**O que muda:**
- `pins_do_congelamento` passa a devolver `evidencias_da_rota` e
  `conferencia_da_rota`, os dois pelos dois caminhos: pela entrada carregada e
  pelos arquivos da pasta da rota;
- a entrada do artefato passa de `rota_1` para `rota` e registra `regra`
  (`ROTA-2`).

**Contraprova:** os dois caminhos dão o mesmo hash, e um pré-registro sem o
hash da conferência é recusado com `NaoCongelado`.

**Ajuste de fixture, declarado:** o teste que confere o pré-registro antes de
ler o painel passou a criar `conferencia.json` na pasta sintética da rota,
como já criava `evidencias.jsonl`. A asserção (`NaoCongelado`) não mudou.

**Reexecução do modo estrutural.** Em relação à execução anterior do mesmo
dia, mudaram só três coisas:
- o hash do código do executor e o digest do código de medição;
- o nome da entrada da rota;
- os pins.

Todo o resto do artefato é idêntico, inclusive o digest de conteúdo do painel
(`fd2932e7…`). O hash do arquivo `.duckdb` muda entre gravações porque o
arquivo não é determinístico byte a byte; por isso o pin é o digest de
conteúdo.

**G0 visto, sem rótulo** (`artefatos/executor_v2_rank03b/estrutural.json`):
- G0.3: 95 saltos em 22.325 linhas de ativo (0,4255%, limite 0,5%). Eram 132;
- G0.5: nenhuma violação;
- G1: nenhuma violação;
- amostra: 10.168 observações em 495 companhias.

O erro demonstrado de `140867` continua pendente, porque a ROTA-2 não achou
linha com os dois números do ativo. Ele conta no G0.3 e não entra em
observação nenhuma (verificado por contagem, sem ler valor).

## Auditoria final (28/09): APTA COM RESSALVAS — emendas antes do congelamento

Auditoria de conformidade, somente leitura, sobre o commit `9049579`. O
responsável fez o commit de toda a onda em 27/09, às 20h37. Suíte: 4.452
aprovados, nenhum pulado.

Não houve achado ALTA. Houve um MÉDIA, que é o procedimento de congelamento
entregue ao responsável, e cinco BAIXA. Todos são tratados abaixo **antes** do
congelamento. Nenhum altera veredito, e nenhuma asserção é enfraquecida.

| Achado | O que a auditoria mostrou | Tratamento |
|---|---|---|
| **M1** | Renomear o rascunho quebra o executor, porque `PRE_REGISTRO_RASCUNHO` faz o hash do arquivo em todo `executar_estrutural` e `test_rascunho_vigente_nao_mede` usa o arquivo. Ajustar o código depois de copiar o digest deixa o digest velho, e a medição recusa **depois** de o SHA ter sido publicado | **Congelar por cópia.** O rascunho fica no lugar, como histórico, e o congelado é um arquivo novo com nome sem RASCUNHO. Ordem fixa: (1) todo o código final, com a suíte verde; (2) regerar o estrutural; (3) copiar o rascunho, trocar a linha de status e colar os pins, com o `codigo_de_medicao` do passo 2; (4) calcular o SHA-256. Depois do passo 4, qualquer edição de código medido exige congelar de novo. Nenhum código muda por causa do M1 |
| **B1 → AF1** | A trava do título não decide nada no arquivo real, porque a primeira linha do rascunho nunca teve "RASCUNHO" e a marca está na linha de status. Uma cópia com o nome trocado passou como congelada | `verificar_congelamento` exige uma linha de status (a primeira que começa com `**Status:`) que diga `CONGELADO` e não diga `RASCUNHO` nem `NÃO CONGELADO`. Sem linha de status, recusa. Contraprova sobre uma **cópia do rascunho real**: só com o nome trocado, recusa; com a linha de status trocada, aceita |
| **B2 → AF2** | Tirar as duas linhas da guarda de folga do motivo 11 não derrubava nenhum teste (mutante sobreviveu) | Contraprova: painel sintético sem colisão de disponibilidade e sem companhia excluída → `PublicacaoInsegura`, sem gravar nada em `destino` nem em `destino_painel` |
| **B3 → AF3** | "O `140867` não entra" valia por acaso do dado: nem o código nem o artefato garantiam o zero, e o §12-bis diz "não é tolerado por caber em limiar nenhum" | Para cada erro demonstrado, o artefato publica `observacoes_que_usam`, uma contagem estrutural sem valor: para a conta `1`, as observações que usam o documento como ativo em D; para a `6.01`, as que usam o FCO dele na janela ou no rótulo. **G0.5 reprova** se um erro **pendente** tiver uso maior que zero. Isso implementa texto do §12-bis escrito antes de o G0 ser visto. O valor neste dado já é conhecido (zero, contado em 27/09 e pela auditoria) e não muda veredito. Declarado |
| **B4** | Três passagens do rascunho ficaram contraditas pelo estado de 27/09 sem nota datada, e os hashes das entradas não estavam no §4 | Notas datadas nos três pontos. No §4, os hashes das entradas (`cvm_treino`, manifesto de aquisição e manifesto por documento, completos) entram **como procedência**; o pin verificado é o digest de conteúdo do painel |
| **B5** | Os dois pareceres da conferência B8, fixados por hash em `fontes`, estavam no scratchpad, que foi limpo | **Reconstruídos byte a byte.** Os conferentes gravaram com `json.dump(..., ensure_ascii=False, indent=1)`, sem quebra de linha final, e os pareceres foram copiados sem alteração para o `conferencia.json`. Reserializados na ordem de string dos ids, os dois arquivos dão exatamente os hashes de `fontes` (`ba9540b5…3424` e `498e083b…a62f`). Versionados em `artefatos/rota_prova_rank03b_v2_2026-09-27/pareceres/`, com os relatórios finais dos conferentes. Os scripts dos conferentes não são recuperáveis; o método de cada um está em `conferentes[].metodo` |

**Atualizações de texto:**
- o documento de revisão e o `MEMORY.md` passam a registrar o commit
  `9049579`;
- no `MEMORY.md`, "não entra em observação" vira "não é usado como ativo em
  D";
- ainda no `MEMORY.md`: só a C9 veio depois de o G0 ter sido visto. A primeira
  execução parou antes de imprimir.

### Verificação curta das correções (28/09): FECHADO COM RESSALVAS

Os seis achados (M1 e B1 a B5) foram dados como fechados, sem asserção
enfraquecida e sem veredito alterado. Ficaram seis ressalvas BAIXA, todas
tratadas antes do congelamento:

| Ressalva | Tratamento |
|---|---|
| 1. A trava da linha de status era contornável: aceitava uma linha CONGELADO acrescentada antes da linha RASCUNHO, que continuava lá, e aceitava "NAO CONGELADO", "não está congelado", "a ser congelado", "DESCONGELADO" e "NÃO" em Unicode decomposto | **AF1 endurecida.** Linha de status é toda linha que, depois da normalização NFC e sem os prefixos de citação e de lista, começa por `status:`, sem distinguir caixa e com ou sem negrito. **Todas** elas têm de casar positivamente com `**Status: CONGELADO em AAAA-MM-DD`. Contraprovas: a linha acrescentada sem trocar a antiga, as variantes da sonda e uma segunda linha de status em minúsculas, em citação ou em lista. A sonda da verificação, rodada de novo, recusa todas as variantes e aceita só a troca correta |
| 2. Dois ramos da AF3 sem contraprova: FCO usado só no rótulo e `id_doc` composto (dois mutantes sobreviviam) | `TestUsoDosErrosDemonstrados`, com entradas montadas à mão. O caso do rótulo afirma a **decisão** do gate (reprova com uso 1, aprova a mesma amostra com uso 0). Os cinco mutantes da verificação (`sem_rotulo`, `sem_janela`, `sem_split`, `sem_filtro_pendente`, `conta_desconhecida_zero`) morrem |
| 3. "C10" nomeava três coisas: o item C10 da parte C, a trava do rótulo e a emenda da linha de status | As emendas de 28/09 passam a se chamar **AF1** (linha de status), **AF2** (contraprova da folga) e **AF3** (erro demonstrado pendente). A troca foi feita só nas linhas escritas em 28/09 e ainda sem commit, inclusive na tabela da seção anterior. As referências antigas a C10 ficam como estão |
| 4. O estrutural registrava um hash de rascunho anterior às notas de 28/09, e o documento de revisão omitia que o hash do rascunho também tinha mudado | O estrutural é regerado depois de todas as edições desta onda, e o documento de revisão cita os três hashes informativos que mudam (código, contrato e rascunho) |
| 5. O `MEMORY.md` trazia a contagem de suíte de 26/09 (4.184) | Atualizada com a contagem final desta onda |
| 6. As mudanças de fixture estavam declaradas no arquivo de teste, mas não no contrato | Declaradas abaixo |

**Substituições de fixture declaradas (28/09).** Em nenhuma delas mudou um
`assert` ou um `match`:
- `TestCongelamento._arquivo` passou a escrever a linha de status
  `**Status: CONGELADO em 2026-10-01, por ato do responsável.**` (constante
  `STATUS`). Sem ela, os casos de nome, título, SHA e pin seriam recusados pelo
  motivo errado. O parâmetro `status` permite omitir ou trocar a linha nos
  casos novos;
- `test_pin_fixa_a_conferencia_pelos_dois_caminhos` passou a escrever a mesma
  linha de status no pré-registro sintético, para que a recusa venha do pin da
  conferência;
- `TestLigacoesDeCarregarEntradas._preparar` ganhou os parâmetros `construir` e
  `planos` e substitui só a conexão `:memory:` (27/09, emenda C8).
