# Contratos do lote C — painel de pesquisa do Rank 3-B e gates G0/G1

**Data:** 2026-09-16. **Parte 1 (construção) escrita antes do código do
construtor. A parte 2 (regra de escala) é acrescentada depois do piloto de fonte
e antes do código dela.**
**Origem:** [levantamento](pendencias_desbloqueio_treino_dfc_2026-09-15.md) D4–D6;
[contratos do lote B](contratos_lote_b_rank03b_2026-09-16.md), que valem aqui
integralmente — em especial **O1, cegueira ao desfecho**.
**Decisão do responsável:** painel **separado**. `cvm.duckdb` e
`cvm_treino.duckdb` não são alterados; a etapa 10 não é tocada.

**O que este lote entrega:** um painel de pesquisa reproduzível, restrito ao que
o Rank 3-B consome, e G0/G1 medidos sobre ele. **Não mede T1, T2 nem
baselines.** Se G0 ou G1 reprovarem, o lote para e o relatório diz por quê.

---

## Parte 1 — construção

### U — Universo

**U1.** Companhias com `plano_contas NOT LIKE 'll3_09_%' AND NOT is_banco`,
lidas de `companhias` do painel compartilhado (somente leitura; hash do arquivo
registrado). É a regra do pré-registro de 11/09.

**U2.** O painel **não** decide elegibilidade: carrega as 700 e marca
`plano_contas`. As 3 companhias do plano `ll3_13` (seguros; entre elas BB
Seguridade e IRB, cuja `6.01` se chama "…Atividades Seguradora/Resseguradora")
ficam identificadas. **Excluí-las é decisão do pré-registro novo**, a tomar
antes de medir.

**U3.** Só consolidado, como a carga compartilhada.

### T — Identidade temporal

**T1 — O período é identificado pelas DATAS.** Um trimestre é
`(cd_cvm, dt_ini, dt_fim)`. O rótulo é **derivado** das datas, nunca o
contrário. É o que dissolve o N3: dois períodos distintos nunca disputam uma
chave.

**T2 — Rótulo = trimestre civil de `dt_fim`**, na coluna `trimestre` (o nome
`rotulo` é reservado ao alvo e proibido por O1 — a guarda pegou o primeiro nome
que usei) (`kTAAAA`, k = ⌈mês/3⌉), para
fluxo e para posição. Num exercício de abril a março, os trimestres terminam em
junho, setembro, dezembro e março: ordinais civis consecutivos. O q1 do alvo
continua escolhido **pelas datas** (H1.1), e q2–q4 continuam exigindo ordinal
consecutivo **e** datas encadeadas (H1.2).

**T3 — Colisão de rótulo não se desempata.** Dois trimestres válidos da mesma
companhia com o mesmo rótulo são marcados `ambiguo_exercicio` e **nenhum** entra
na série. Escolher um tornaria repetível uma escolha sem fundamento econômico —
a advertência exata do levantamento sobre o N3.

### F — FCO trimestral

**F1 — Base.** Declarações `ÚLTIMO` da conta `6.01` (`DFC_MD` ou `DFC_MI`) de
ITR e DFP: são acumulados do exercício.

**F2 — O método não entra na identidade.** O caixa líquido operacional é o
mesmo pelo método direto e indireto (CPC 03, §§18–20). Medido: nenhum documento
traz os dois; 53 companhias trocam de método; 117 trimestres combinam
acumulados de métodos diferentes. O método de cada operando é preservado na
linhagem.

**F3 — Declaração repetida do mesmo período** (mesma companhia, `dt_ini` e
`dt_fim`, em documentos diferentes — medido: 58 casos, todos ITR + DFP): se os
valores em reais coincidem, vale a declaração **recebida primeiro**; se
divergem, o período fica `conflito_de_declaracoes` e não serve de operando.

**F4 — Isolamento.** Dentro de um exercício (`cd_cvm`, `dt_ini`), em ordem de
`dt_fim`: o primeiro acumulado é trimestre se durar 80–100 dias; o k-ésimo
isolado é `A_k − A_{k−1}`, com período `(dt_fim_{k−1} + 1, dt_fim_k)`. O
antecedente **não precisa ser trimestre**: um primeiro acumulado de seis meses
serve de operando para o trimestre seguinte.

**F5 — Estados de cada candidato**, vocabulário fechado:

| Estado | Quando |
|---|---|
| `valido` | período de 80 a 100 dias, operandos utilizáveis |
| `primeiro_periodo_nao_trimestral` | primeiro acumulado do exercício fora da banda — não é trimestre, pode ser operando |
| `lacuna` | período > 100 dias com antecedente: falta documento intermediário |
| `curto` | período < 80 dias |
| `conflito_de_declaracoes` | F3 |
| `valor_nulo` | a declaração não tem valor na fonte (conta para G0.4) |
| `operando_indisponivel` | um operando está em `conflito_de_declaracoes` ou `valor_nulo` |
| `ambiguo_exercicio` | T3 |

Só `valido` é consumido pelos gates. **Todo o resto vai para o inventário de
perdas**, com contagem por estado e por companhia. Nada é descartado em silêncio.

**F6 — Não se mistura vintage numa subtração.** O comparativo `PENÚLTIMO` de um
documento posterior **não** serve de antecedente: ele é o valor reapresentado, e
subtraí-lo do acumulado original misturaria *as-reported* com *as-restated*.
Medido: 2.762 períodos existem só como `PENÚLTIMO`; a recuperação que eles
permitiriam é **contada** no inventário, não feita.

### A — Ativo total

**A1.** Declarações `ÚLTIMO` da conta `1` do `BPA`. Posição na data `dt_fim`;
`dt_ini` nulo (saldo não tem início).

**A2 — Valor não informativo.** Ativo Total com módulo **≤ 1 na unidade
declarada** é `nao_informativo` e não entra na série. Medido: 3 documentos com
valor em (0, 1] — em `003328`/1T2021 o "1,0" está no próprio formulário e as
notas não trazem o balanço, então não há fonte para corrigi-lo (ressalva RA5 do
lote B). Zero e negativo seguem como estão: a elegibilidade do alvo
(`ativo_total > 0`) já os trata.

**A2-bis — Mesmas regras de F3 e T3 para o ativo:** a mesma data declarada por
dois documentos vale pela recepção mais antiga se os valores coincidem e vira
`conflito_de_declaracoes` se divergem; valor ausente na fonte é `valor_nulo`;
duas posições válidas com o mesmo rótulo são `ambiguo_exercicio`.

**A3 — Identidade contábil publicada, não usada para excluir.** Ativo ≠
Passivo total (6 documentos) e as identidades de caixa da DFC (23 + 14) saem no
relatório de integridade. Nenhuma linha é removida por elas.

### P — Disponibilidade (D5)

**P1 — Política conservadora.** Toda linha carrega `disponivel_em`: a data de
recebimento da **versão numérica** (a maior, a única que os ZIPs guardam). Num
trimestre derivado, é o **máximo** entre os operandos. Uma linha não é usada
antes dessa data. Não há vazamento: o valor só existia completo a partir dela.

**P2 — O custo da política é medido.** Cada linha carrega também
`disponivel_em_v1`: o máximo, entre os operandos, da recepção da **primeira**
versão. O intervalo `[disponivel_em_v1, disponivel_em)` é o intervalo cego. O
relatório publica quantas linhas têm intervalo cego e quantas decisões da mesma
companhia caem dentro dele.

**P3 — Rótulo futuro usa a versão numérica**, disponível ou não em D — o rótulo
não precisa estar publicado em D (levantamento, D5). Isto é política declarada
e vai para o pré-registro.

### G — Gates sobre o painel de pesquisa

**G1-pp.** O executor lê o painel de pesquisa nas **mesmas formas** que os
carregadores do auditor e chama as **mesmas funções puras** `gate_g0`,
`construir_amostra` e `gate_g1`. Nenhuma cópia de lógica de gate.

**G2-pp — G0.2 recomputa a duração das datas**, sem ler a coluna guardada:
verifica a regra de banda do construtor em vez de confiar nela. Os períodos que
o construtor recusou estão no inventário, não nas linhas trimestrais. **Esta
leitura de G0.2 vai para o pré-registro novo** — é aplicação ao painel de
pesquisa, não relaxamento: nenhum período fora da banda é tratado como
trimestre.

**G3-pp — G0.1 continua valendo** como unicidade: um valor por
`(cd_cvm, rótulo)`.

**G4-pp — G0.3 mede o ativo depois das correções com fonte**, e só delas.
Documento de escala suspeita **não adjudicado permanece com o rótulo
declarado**. Excluí-lo faria G0.3 passar por remoção — proibido (§4.4 regra 9).

**G5-pp — G0.4** conta nulos em **todos** os candidatos, antes dos estados.

**G6-pp — Cegueira.** O executor apaga `y` de cada observação antes de qualquer
contagem ou gravação; o artefato é conferido contra as chaves proibidas de O1.
Nenhuma taxa de evento é calculada.

**G7-pp — Parada.** G0 ou G1 reprovado encerra o lote. Aprovado, o próximo passo
é o **rascunho** do pré-registro, que só vira protocolo com aprovação do
responsável.

### R — Reprodutibilidade

**R1.** Entradas congeladas: 31 ZIPs (manifesto), `companhias` (hash do
painel), manifesto de correções de escala (hash), manifesto de aquisição
(hash).

**R2.** Duas construções seguidas produzem o **mesmo digest de conteúdo** —
SHA-256 sobre cada tabela exportada em ordem total. O arquivo DuckDB em si não
é comparado (o formato não é byte-determinístico).

**R3.** Reordenar a entrada não muda o digest. Há teste.

**R4.** O manifesto do painel registra entradas, parâmetros (banda, piso de
valor não informativo), hash do código do construtor e o digest.

### Alternativas rejeitadas (parte 1)

| Alternativa | Por que não |
|---|---|
| Reconstruir o `cvm_treino.duckdb` | Decisão do responsável: painel separado. Quebraria hash e alcançaria a etapa 10 |
| Rótulo fiscal do painel compartilhado | É a origem da colisão N3 |
| Desempatar colisão por `cd_conta`, maior valor ou versão | Escolha sem fundamento econômico (levantamento D4.3) |
| Parear acumulados por demonstrativo | Fabrica "sem antecedente" nas 53 companhias que trocam de método |
| Usar `PENÚLTIMO` como antecedente | Mistura vintages numa subtração |
| Excluir documento de escala não adjudicada | Passaria G0.3 por remoção |
| Usar a data da v1 como disponibilidade do número da vmax | Vazamento: o número usado só existiu na data da vmax |
| Recuperar todas as versões antigas agora | ~23 h de aquisição; política conservadora + inventário é o que o levantamento exige |

### Condições de falsificação (parte 1)

| # | Condição |
|---|---|
| 1 | Alguma linha `valido` com duração fora de 80–100 dias |
| 2 | Duas linhas `valido` com o mesmo `(cd_cvm, rótulo)` |
| 3 | Linha usada antes de `disponivel_em`, ou `disponivel_em` anterior à recepção de algum operando |
| 4 | Subtração entre acumulados de exercícios diferentes |
| 5 | Candidato que não aparece nem nas linhas válidas nem no inventário de perdas |
| 6 | Digest diferente entre duas construções, ou após reordenar a entrada |
| 7 | Artefato com chave proibida por O1, ou taxa de evento calculada |
| 8 | Documento de escala suspeita excluído do painel |
| 9 | Hash de `cvm.duckdb`, `cvm_treino.duckdb`, ZIPs ou pré-registro de 11/09 mudar |
| 10 | Arquivo da outra frente mudar |

---

## Parte 2 — escala

**Escrita em 16/09, antes do resultado do piloto de fonte e antes do código de
adjudicação.** O que já se sabia ao escrevê-la: a evidência em 11 documentos de
reconhecimento (ressalva RA3 do lote B) e a linha de base estrutural do painel
**sem correção** — G0.3 = **132 saltos, 0,5875%**, contra limite de 0,5% (no
máximo 112). Por isso esta regra fica **congelada antes** de rodar sobre a
extensão: uma regra ajustada depois de ver o G0 seria escolhida pelo resultado.

### S — Adjudicação de escala por documento

**S1 — Evidência**, só das notas explicativas (grupos 193/412), com os
vocabulários fechados da RA3: **cabeçalho** (`MIL`, `UNIDADE`, `contraditorio`,
`ausente`, `sem_notas`) e **numérica** (`bruto`, `dividido`, `multiplicado`,
`nenhum`, `conflitante`, `sem_notas`).

**S2 — Escala do formulário**, exigindo as **duas** evidências:

| Cabeçalho das notas | Números do formulário nas notas | Escala do formulário |
|---|---|---|
| `MIL` | `bruto` | `MIL` |
| `MIL` | `dividido` | `UNIDADE` |
| `UNIDADE` | `bruto` | `UNIDADE` |
| `UNIDADE` | `multiplicado` | `MIL` |
| qualquer outro par | — | **indecidível** |

Veredito do documento: `confirmada` (= rótulo declarado), `corrigida` (≠) ou
`indecidivel`. O cabeçalho sozinho não basta: não distingue formulário em
milhares com rótulo errado de formulário em reais com notas em milhares. O
número sozinho não basta: não diz em que unidade as notas estão.

**S3 — Escopo da correção.** A escala adjudicada vale para as contas que este
painel usa (`1` e `6.01`), que são monetárias por construção (`ST_CONTA_FIXA`,
"Ativo Total", "Caixa Líquido Atividades Operacionais"). Nada aqui corrige
outra conta, e LPA não está no painel.

**S4 — O que se adquire** (ressalva RA4 do lote B): as duas pontas de cada
trecho nas 54 companhias mistas e nas 17 só `UNIDADE`; 30 companhias só `MIL`
como controle; os documentos já baixados pelo piloto entram com o mesmo
tratamento.

**S5 — Herança dentro do trecho.** O interior de um trecho recebe a escala das
pontas **somente se**:
1. as duas pontas saíram com veredito **não** indecidível e com a **mesma**
   escala do formulário; e
2. o teste da premissa no estrato E10 do piloto **não encontrou discordância**:
   em nenhum trecho completo cujos documentos tenham todos veredito decidido, um
   documento interior saiu com escala diferente das pontas.

Se (2) falhar em um único trecho, **não há herança em lugar nenhum** e os
interiores ficam com o rótulo declarado. Trecho de um documento usa só o
próprio veredito; de dois, os dois, sem interior. Ponta indecidível não é
substituída pelo documento vizinho — isso exigiria aquisição iterativa, que
este lote não faz.

**S6 — Controle só `MIL`.** Adjudicado como qualquer outro. Um `corrigida`
entre eles é evidência de **erro consistente fora do escopo** — publicado e
levado ao pré-registro, sem corrigir as companhias não amostradas.

**S7 — Valor não informativo** (A2) não é objeto de adjudicação de escala.

**S8 — Manifesto de correções** em
`corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv`, **só** com os
documentos cuja escala aplicada difere da declarada. Colunas: `id_correcao`,
chave do documento, `id_doc`, SHA-256 do pacote, escala declarada e aplicada,
`base` (`corrigida_documento` ou `herdada_trecho`), impressão digital dos
valores brutos, classes e contagens das duas evidências, trecho, **trecho literal
de ≥ 60 caracteres com anexo e página** e, para herança, as duas pontas com
seus próprios pacotes. A tabela completa de evidência — confirmados e
indecidíveis inclusive — vai para
`artefatos/painel_pesquisa_rank03b/adjudicacao/`.

**S9 — Guarda** (padrão do §3.3): a correção só se aplica se o rótulo declarado
e a impressão digital ainda baterem com o ZIP pinado; senão a construção falha.
Já implementada na parte 1.

**S10 — Sem iteração.** A regra acima roda **uma vez** sobre a extensão. Se o
G0 reprovar depois das correções, o lote para e reporta; nenhum parâmetro de S
é ajustado depois de ver o G0.

> ## ⚠️ RESSALVA RC1 — defeito da primeira execução (2026-09-16, antes de qualquer G0 com correções)
>
> **O que aconteceu.** A adjudicação rodou uma vez sobre a extensão (405
> documentos; código `6d100e4b…`; manifesto `95d86cc6…`, 109 linhas). Ao ler o
> resultado — **antes** de construir o painel com correções e antes de qualquer
> G0 —, os dois controles só `MIL` que saíram "corrigidos" mostraram que a
> implementação **não cumpria S1**:
>
> - **D1, flexão não coberta.** `016292` (BRF) declara *"as demonstrações
>   financeiras individuais e consolidadas da companhia estão **expressas** em
>   milhares de reais"*. O padrão implementado era `expressos?`; o cabeçalho
>   verdadeiro não foi reconhecido.
> - **D2, rodapé tomado por cabeçalho.** O único "cabeçalho `UNIDADE`" desses
>   documentos era uma nota **sobre valores por ação** — *"(1) valores expressos
>   em reais"* ao lado de opções outorgadas; *"dividendos por ação (valores
>   expressos em reais)"*. S1 fala em **cabeçalho de apresentação**; o código
>   aceitava a frase em qualquer ponto das notas.
>
> Consequência: as **9** correções `MIL → UNIDADE` da primeira execução têm todas
> o par `UNIDADE|bruto` e **não têm a evidência que S2 exige** (condição de
> falsificação 11). Aplicá-las dividiria por mil valores corretos.
>
> **Correção de implementação, fixada aqui antes de rodar de novo.** A frase de
> unidade só conta como cabeçalho de apresentação se:
> 1. usa o vocabulário da RA3 **com as flexões** de "expresso" e "apresentado"
>    (`expresso`, `expressa`, `expressos`, `expressas`; idem para
>    `apresentad-`); **e**
> 2. está nos **primeiros 300 caracteres** de uma página das notas (o título
>    *"(valores expressos em milhares de reais…)"*), **ou** os **200 caracteres
>    anteriores** mencionam o objeto da apresentação: *demonstrações
>    financeiras*, *demonstrações contábeis*, *informações trimestrais*,
>    *informações financeiras*, *informações contábeis* ou *notas explicativas*.
>
> A regra é **positiva** — exige que a frase fale das demonstrações — e não uma
> lista de contextos a excluir. A evidência numérica, a tabela S2, S3–S9 e o
> escopo **não mudam**. O teste da premissa S5 passa a reler os documentos do E10
> com a regra corrigida, em vez de reaproveitar as classes gravadas pelo piloto.
>
> **Segunda execução, e última.** Roda uma vez. Os artefatos da primeira ficam
> preservados em `artefatos/painel_pesquisa_rank03b/adjudicacao/execucao1/`. O
> painel e o G0 **governantes** são os da segunda execução; o G0 com o manifesto
> da primeira é medido **depois**, como diagnóstico, e publicado ao lado. Se a
> segunda execução revelar outro defeito de implementação, o lote **para** e
> reporta — não há terceira.
>
> **Como refutar esta correção:** mostrar documento em que o cabeçalho de
> apresentação real esteja fora das duas posições aceitas, ou um rodapé que
> as satisfaça.
>
> ### RC1-bis — refutada antes de rodar; a regra muda (2026-09-16)
>
> A regra acima foi verificada **antes** da segunda execução, na amostra de
> desenho (documentos do piloto) e nos dois documentos que expuseram o defeito.
> Ela foi refutada pela própria condição que declarou:
>
> - o rodapé da TIM (`69541`), *"dividendos por ação (valores expressos em
>   reais)"*, cai nos primeiros 300 caracteres de uma página;
> - em 5 documentos da amostra, *"as demonstrações financeiras … são
>   **apresentadas em reais**"* — do parágrafo de **moeda funcional** — tornava
>   contraditório um cabeçalho `MIL` verdadeiro;
> - o único "cabeçalho `UNIDADE`" de `023426` (dado como `UNIDADE` confirmado
>   no piloto) era *"prejuízo por ação básico (em reais)"*.
>
> **Leitura:** "em reais" declara a **moeda**, e aparece em rodapés por ação;
> não declara **escala**. "Em milhares de reais" declara escala. Não há frase
> de cabeçalho que prove, sozinha, que um formulário está em unidades.
>
> **Regra que vale para a segunda execução (substitui a tabela S2):**
>
> | Cabeçalho de apresentação `MIL` (regra de posição RC1) | Números do formulário nas notas | Escala do formulário |
> |---|---|---|
> | presente | `bruto` | `MIL` |
> | presente | `dividido` | `UNIDADE` |
> | qualquer outro caso | — | **indecidível** |
>
> Frases "em reais" são **contadas e publicadas**, mas não entram na decisão.
> Consequência declarada: um formulário realmente em reais só é confirmado
> quando as notas estão em milhares e mostram os valores divididos por mil; do
> contrário fica indecidível e **permanece com o rótulo declarado** (G4-pp).
> Correções `UNIDADE → MIL` — o erro que o G0.3 flagra — seguem possíveis.
>
> Na amostra do piloto (E1–E4) e nos dois documentos, a regra é verificada
> antes da execução; o resultado entra no relatório. A premissa S5 é reavaliada
> com esta regra. **Esta é a última mudança:** se a execução 2 revelar outro
> defeito, o lote para.

### Alternativas rejeitadas (parte 2)

| Alternativa | Por que não |
|---|---|
| Só o cabeçalho das notas | Não separa formulário em reais com notas em milhares |
| Só a evidência numérica | Não diz a unidade das notas |
| Continuidade do valor bruto | Suspeita, não prova (correção de 12/09) |
| `CodigoEscalaMoeda` do formulário | É a origem do rótulo |
| Maioria dentro do trecho | Contagem de documentos não é evidência nova |
| Herdar sem testar a premissa | Premissa não testada vira fato por decreto |
| Buscar o vizinho quando a ponta é indecidível | Aquisição iterativa: escolhe o que baixar olhando o resultado |
| Ajustar vocabulário ou tabela depois de ver o G0 | Regra escolhida pelo resultado |
| (RC1) Aplicar as 9 correções da primeira execução mesmo assim | São sabidamente sem a evidência que S2 exige |
| (RC1) Remover só as 9 linhas e manter o resto da primeira execução | D1 também afeta documentos que ficaram indecidíveis ou "confirmados" pelo motivo errado; remendar a saída deixaria a implementação errada |
| (RC1) Lista de contextos proibidos ("por ação", "dividendos"…) | Lista negativa é aberta: o próximo rodapé escapa. A regra positiva exige que a frase fale das demonstrações |
| (RC1) Só a primeira página das notas | Medido na BRF: o cabeçalho real está na nota de base de preparação, não na página 1 |

### Condições de falsificação (parte 2)

| # | Condição |
|---|---|
| 11 | Correção com só uma das duas evidências |
| 12 | Herança com pontas de escalas diferentes, com ponta indecidível, ou depois de o E10 ter mostrado discordância |
| 13 | Correção aplicada a documento cujo rótulo ou valores brutos mudaram |
| 14 | Linha do manifesto sem trecho literal, anexo e página |
| 15 | Qualquer parâmetro de S alterado depois da primeira medição de G0 com correções |

---

> ## ⚠️ RESSALVA RC2 — auditoria de conformidade (2026-09-16, depois da execução 2)
>
> A auditoria de conformidade (somente leitura) rodou sobre o lote depois da
> execução 2 da adjudicação e da medição governante. Nenhum achado mudou uma
> **decisão** de escala nem um veredito de G0/G1. Vários mudaram **código** e
> **artefatos**, e todos ficam declarados aqui, com o que foi feito.
>
> **Correções de texto deste contrato:**
>
> - **RC1 diz "as 9 correções `MIL → UNIDADE`"; eram 13 linhas** do manifesto
>   `95d86cc6…`: 9 por documento e **4 herdadas** dentro do trecho de `027316`.
>   A conclusão (nenhuma tinha a evidência que S2 exige) vale para as 13.
> - **A2 se contradiz:** "módulo ≤ 1" e, em seguida, "zero e negativo seguem
>   como estão". Vale a segunda frase: `nao_informativo` é valor em **(0, 1]**.
>   O código usava módulo; foi corrigido (achado B3). Sem efeito nas contagens
>   publicadas: válido 22.469 e não informativo 3, antes e depois.
> - **G3-pp aplicou G0.1 como unicidade sem submeter a leitura a decisão.** Lido
>   literalmente, G0.1 conta 117 trimestres válidos (49 companhias) derivados de
>   acumulados de métodos diferentes. Publicado como diagnóstico e levado ao
>   pré-registro v2 como **[DECIDIR]** (achado M5).
>
> **Defeitos de implementação, corrigidos:**
>
> | Achado | Defeito | Correção |
> |---|---|---|
> | A1 | O G1 do painel de pesquisa montava a amostra com `construir_amostra`, que **calculava `S1`, `S2` e `y` em memória** (O1, item 1), e publicava a contagem de descartes por `FCO_TTM ≤ 0` | `construir_amostra(..., calcular_rotulo=False)`; o G1 verifica que nenhuma observação tem `y`; a contagem do TTM sai como "omitido por O1". Teste: as somas do rótulo nem são chamadas |
> | M1 | O **consumidor** do manifesto (o construtor dos gates) não verificava as condições 11, 12 e 14 — só o produtor, ao gravar | `carregar_correcoes` roda `validar_manifesto` e confere o SHA de cada pacote contra o manifesto de aquisição |
> | M2 | A condição 12 (herança só entre pontas **de mesma escala**) não era verificável no manifesto: as pontas não registravam a escala; um teste consagrava a verificação fraca | As pontas passam a levar `escala_do_formulario`; a validação exige escala igual nas duas; o teste fraco foi **substituído**, e isso está declarado no docstring |
> | B3 | A2 por módulo (acima) | Só positivo |
> | B4 | Ativos em conflito ou ambíguos saíam da série sem medir o efeito | Diagnóstico publicado: 3 ativos; 49 saltos se incluídos (aprovaria igual) |
> | A3 | A soma das identidades da DFC contava duplicatas da fonte (72) | Máximo por conta antes de somar: **23**, o número deste contrato |
> | U2 | `plano_contas` não chegava às linhas | Coluna nas linhas. **Muda o digest de conteúdo**: sem correções `d5499b22…` → `08fffc8b…`; com correções `ec036d53…` → `f9cb9da9…`. Os valores não mudaram |
> | R1 | O artefato de gates não registrava o manifesto de aquisição | `entradas.manifesto_aquisicao_sha256` |
> | — | Os dois painéis gravavam o **mesmo** `manifesto_painel.json`; a execução sem correções sobrescrevia o do governante (achado da revisão final) | Um manifesto por painel (`manifesto_painel_sem_correcoes.json`), com contraprova |
> | — | O teste de O1.3 excluía o trecho literal da verificação, e nada impedia o trecho de carregar valor de caixa (verificação da auditoria) | `mascarar_valores_de_caixa` no trecho publicado; o teste verifica o resultado inteiro. Sobre os dados publicados, muda 0 trechos |
>
> **Pendente e declarado:** a validação M1 só roda pela linha de comando;
> chamar `construir`/`executar` direto aplica o dicionário recebido.
>
> **O manifesto de correções foi regravado, sem mudar decisão.** A correção M2
> exigiu escrever a escala das pontas. `reescrever_manifesto` reconstrói o
> manifesto a partir da evidência já adjudicada (sem reler PDF) e **falha** se
> alguma decisão mudar: `6e2c86a1…` → **`4735fb107cce…`**, as mesmas 101
> decisões. O `resumo.json` da execução 2 continua registrando `6e2c86a1…`,
> que é o que aquela execução gravou; não foi reescrito.
>
> **Condição 15 e o código da adjudicação.** `scripts/adjudicar_escala_rank03b.py`
> mudou depois da execução 2 (`042e7bcd…` → atual): validação, regravação e uma
> chave duplicada no resumo. Nenhum **parâmetro de S** mudou (vocabulário,
> posições, tabela, escopo). Para não deixar isso só como afirmação, a
> adjudicação foi **reexecutada com o código atual**, sem rede, num diretório
> de rascunho — resultado no relatório do lote C, §8.
>
> **Declarado, sem correção possível:**
>
> - **M6 — desenho e avaliação se sobrepõem.** RC1-bis foi escrita depois de ver
>   a saída da execução 1 e verificada numa amostra de desenho (piloto, BRF,
>   TIM) que está dentro do escopo avaliado. Não houve amostra fresca.
> - **S10 foi quebrado à letra.** Ele diz que a regra "roda **uma vez**" sobre a
>   extensão; rodou duas. A segunda veio de defeito de implementação achado
>   **antes** de qualquer G0 com correções (RC1), não de ver o G0, que é o que
>   S10 e a condição 15 existem para impedir. A execução 1 está preservada e
>   medida (61 saltos, também aprovada).

> ## ⚠️ RESSALVA RC3 — evidência numérica e disponibilidade da prova (17/09)
>
> A [conferência independente de 17/09](conferencia_pre_treino_rank03b_2026-09-17.md)
> mostrou que a evidência numérica de S2 (magnitudes procuradas no texto
> corrido das notas) aceita números de outras contas e de quantidade de ações,
> e produziu um erro comprovado (ESC-0101). Mostrou também que a parte P
> deste contrato não dava data à **prova** de uma escala herdada. As duas
> cláusulas foram substituídas pelos contratos
> [E e P4–P7 de 17/09](contratos_correcao_rf01_rf08_rank03b_2026-09-17.md),
> escritos antes da reexecução. As cláusulas acima ficam como foram escritas;
> a execução governante é a 3 ([relatório](correcao_rf01_rf08_rank03b_2026-09-17.md)).
