# Curadoria do conjunto-padrão

`perguntas.csv` é o único arquivo carregado pelo pipeline. Desde 2026-07-29,
ele contém 10 perguntas `dev` e as 45 perguntas `teste` congeladas.

`candidatas_teste.csv` preserva a cópia de curadoria que originou o conjunto
congelado: 15 factuais, 10 comparativas, 10 qualitativas e 10 adversariais.
O pipeline não lê esse arquivo.

`anotacoes_revisao2.csv` traz as colunas acrescentadas pela revisão 2/3 da
spec (5.13), ligadas por `id` às mesmas 55 linhas. Ver
[Colunas da revisão 2/3](#colunas-da-revisão-23-spec-513) abaixo.

`conjunto_agentes.csv` é o conjunto **próprio** da camada de agentes (spec
5.9.3), congelado em 2026-08-10 e separado das 45. Ver
[Conjunto da camada de agentes](#conjunto-da-camada-de-agentes-conjunto_agentescsv-spec-593)
abaixo. O pipeline não lê esse arquivo.

## Protocolo para promover as candidatas

1. Fazer uma segunda leitura independente dos locais citados, em outro dia.
2. Para `release_gerencial`, confirmar definição, valor, unidade e página sem
   reutilizar a anotação da primeira leitura.
3. Para `cvm`, conferir o valor no ITR/DFP estruturado e a ocorrência equivalente
   no PDF do corpus. A primeira leitura usou os arquivos oficiais
   `itr_cia_aberta_2026.zip` e `dfp_cia_aberta_2025.zip` do Portal de Dados
   Abertos da CVM; eles não são versionados no repositório.
4. Validar que todas as páginas são físicas e 1-indexadas, como o extrator do
   pipeline, e que cada documento pertence ao manifesto congelado.
5. Só então mover as 45 linhas para `perguntas.csv`, registrar a data de
   congelamento no `AGENTS.md` e não alterar perguntas/respostas após a primeira
   execução completa de teste.

## Estado da primeira leitura — 2026-07-15

- Corpus: `2T2025`, `3T2025`, `4T2025`, `1T2026`.
- Desenvolvimento: 10/10 perguntas `dev` validadas no arquivo do pipeline.
- Candidatas: 45/45, com IDs únicos e distribuição contratual.
- CVM já cruzada na primeira leitura: resultado IFRS do Itaú 1T26 e lucro IFRS
  atribuível ao controlador do Bradesco 1T26.
  No ITR 2026 consolidado, as contas `3.09` e `3.11.01` registram
  `11.875.000` e `5.177.940` em escala `MIL`, respectivamente.
- Validação estrutural concluída: esquema, contratos condicionais, documentos e
  limites das páginas físicas.
- Uma auditoria cruzada por instituição corrigiu a primeira versão no mesmo dia;
  ela não substitui a segunda leitura independente em outra data.

## Alertas para a segunda leitura

- No BTG 4T25, uma frase da página 3 mostra ROAE de 26,7%, mas a tabela da mesma
  página, o comentário da página 4 e a reconciliação da página 6 mostram 27,6%.
  A candidata `TSTC003` fixa as tabelas como fonte e usa 27,6%.
- No Bradesco, o ROAE trimestral de 3T25/4T25 (14,7%/15,2%) difere do ROAE
  acumulado anualizado (14,6%/14,8%). As comparativas fixam a série trimestral.
- O BTG reapresentou bases após a consolidação do Banco Pan; por isso a candidata
  temporal que cruzava 3T25 e 1T26 foi substituída por uma comparação só de 1T26.
- Em `TSTC009`, usar os deltas reportados, não apenas números arredondados: BB
  +404 bps e Santander +0,02 p.p.

## Segunda leitura e congelamento — 2026-07-29

- As 45 perguntas foram relidas contra os 20 PDFs íntegros, em uma data
  diferente da anotação inicial; páginas são físicas e 1-indexadas.
- As duas factuais `classe_verificacao=cvm` foram cruzadas novamente com o ITR
  estruturado de 2026 e com a reconciliação equivalente nos releases.
- Seis listas de `locais_aceitos` foram restringidas às páginas que contêm o
  valor exato, removendo páginas apenas arredondadas.
- `TSTQ002` foi reescrita para separar comparação trimestral/anual e apontar
  somente as páginas que sustentam todos os fatores esperados.
- Depois dessas correções, esquema, IDs e distribuição 15/10/10/10 foram
  revalidados; quatro adversariais tratam explicitamente do banco fora do
  corpus. O conteúdo foi então copiado para `perguntas.csv` e congelado.
- A partir deste ponto, pergunta, resposta e páginas do conjunto `teste` não
  devem mudar após a primeira execução integral; eventual erro exige nova
  versão do benchmark e invalidação explícita do fingerprint anterior.

## Colunas da revisão 2/3 (spec 5.13)

A spec acrescentou cinco colunas ao esquema do gabarito. Elas anotam **as mesmas
55 linhas** — regra "acrescente coluna, nunca linha". Nenhuma pergunta foi criada,
reordenada ou reescrita para acomodá-las.

### Por que num arquivo separado, e não dentro de `perguntas.csv`

As colunas vivem em `anotacoes_revisao2.csv`, ligadas por `id`, em vez de
mescladas no gabarito. A decisão é deliberada e tem duas razões, medidas e não
supostas:

1. **O fingerprint da avaliação inclui o hash do arquivo inteiro.**
   `src/avaliacao.py` grava `sha256_gabarito_completo` no manifesto material e o
   reconfere na carga. Mesclar colunas muda o hash de `perguntas.csv` e invalida
   **todo** fingerprint já registrado — checkpoint, journal, `metricas_dev.json`
   e `respostas_cacheadas.json`. O modo demo falha fechado e a avaliação `dev`
   E0–E3 teria de ser repetida contra provedor pago, sem que uma única resposta
   tenha mudado. Anotar não pode custar uma reexecução paga.
2. **O leitor do gabarito exige igualdade estrita de cabeçalho.**
   `COLUNAS_CONJUNTO_PADRAO` é comparada com `!=` contra os `fieldnames` do CSV,
   e `PerguntaPadrao` é construída por `PerguntaPadrao(**linha)`. Medido numa
   cópia isolada do repositório: mesclar as cinco colunas quebra **9 testes**
   (`test_regras.py::TestEsquemaConjuntoPadrao`, 5 de `test_app_hardening.py` e
   3 de `test_operacao.py`), todos pela mesma `ValueError: Esquema inesperado`.

O arquivo separado tem ainda a vantagem de deixar visível o que foi anotado
**depois** do congelamento de 2026-07-29 — a anotação não se confunde com o
gabarito conferido por dupla leitura.

### Como fundir, quando for a hora

A fusão é desejável assim que a avaliação final for rodada (o fingerprint é
invalidado de qualquer forma nesse momento). Ela exige, na mesma mudança:

1. `src/avaliacao.py`: acrescentar as colunas a `COLUNAS_CONJUNTO_PADRAO` e os
   campos correspondentes a `PerguntaPadrao`, com `camada_esperada` entre
   `origem` e `locais_aceitos` (posição do esquema base da spec) e as quatro da
   revisão 2 ao final;
2. validar os vocabulários abaixo em `carregar_conjunto_padrao`;
3. reexecutar a avaliação, porque o fingerprint anterior deixa de valer.

`tests/test_conjunto_padrao_revisao2.py` já cobre os dois estados: enquanto os
arquivos estiverem separados ele valida a ligação por `id`; depois da fusão,
passa a exigir que os valores mesclados não divirjam da anotação.

### Vocabulário e derivação de cada coluna

| Coluna | Valores | Como foi derivada |
|---|---|---|
| `camada_esperada` | `documento` · `cvm` · `ambas` | De onde a resposta **deve vir**. `release_gerencial` → `documento`; `classe_verificacao=cvm` → `ambas` (o número está na reconciliação do release **e** arquivado no ITR). Nas adversariais, registra a(s) camada(s) que precisam ser consultadas para a recusa ser diagnosticada. |
| `cobertura_esperada` | `ambas` · `so_painel` · `nenhuma` | O que o sistema **tem sobre a entidade perguntada** — não se confunde com a coluna acima. Os cinco bancos do corpus estão nas duas camadas (`ambas`); o Nubank, em nenhuma (`nenhuma`, spec 5.9.2: a Nu Holdings é listada na NYSE e não arquiva ITR). |
| `motivo_recusa_esperado` | `n/a` + os cinco subtipos adversariais | Qual subtipo nomeado a recusa deve **alegar**. Recusar pelo motivo errado não conta como acerto. `n/a` nas 44 linhas em que nenhuma recusa é esperada. |
| `base_esperada` | `n/a` · `gerencial` · `contabil_consolidado` · `contabil_controladores` | Torna verificável a regra de que nenhum número aparece sem sua definição. `n/a` só nas recusas puras, onde número algum pode ser apresentado. |
| `rota_esperada` | `busca_documental` · `busca_documental_multiempresa` · `reconciliacao` · `triagem_cobertura` · `recusa_documental` | O percurso que deveria ter resolvido a pergunta, para separar **erro de roteamento** de erro de resposta. |

Notas de derivação que não cabem na tabela:

- **`base_esperada` das duas linhas contábeis.** `TSTF006` pergunta pelo
  resultado IFRS "atribuível a controladores **e não controladores**" — a linha
  final consolidada, conferida no ITR (conta `3.09` do Itaú, `11.875.000` em
  escala `MIL`) → `contabil_consolidado`. `TSTF009` pergunta pelo lucro
  "atribuível aos acionistas controladores" (conta `3.11.01` do Bradesco,
  `5.177.940` em escala `MIL`) → `contabil_controladores`. As duas conferem com
  a segunda leitura de 2026-07-29 registrada acima.
- **`base_esperada` das qualitativas é `gerencial`, não `n/a`.** Elas não têm
  gabarito numérico, mas nascem da análise gerencial e várias citam números
  (`TSTQ005`, `TSTQ006`, `TSTQ007`). O valor afirma que qualquer número que
  apareça na resposta precisa ser rotulado como base gerencial — que é
  exatamente a regra que a coluna existe para tornar verificável.
- **`cobertura_esperada` das adversariais que não são sobre o Nubank é `ambas`.**
  `TSTA009` ("quem fundou o Bradesco?") recusa porque o **fato** não está no
  corpus, não porque o banco seja desconhecido. É a distinção que a coluna
  captura: entidade coberta, fato ausente.

### Valor pendente de conferência humana

- **`TSTA006` · `camada_esperada` = `pendente_conferencia`.** A pergunta é o
  ROAE do Santander no 1T2020 e a recusa congelada supõe que o período está fora
  das duas camadas. Isso é certo para o corpus documental, mas **não está
  decidido para o painel CVM**: a fonte tem histórico desde 2011 e a spec 5.5 diz
  apenas que a ingestão traz as demais companhias "do mesmo período". Se a janela
  do painel for maior que a do corpus, o 1T2020 passa a ser respondível pela
  camada estruturada e a recusa esperada fica errada pela metade — o mesmo erro
  que o par Nubank × Inter existe para expor. **Decisão humana pendente:** fixar
  a janela temporal do painel. Não preenchido por inferência.

O `TSTA005` (2T2026 do BB) não tem essa ambiguidade: é trimestre futuro, ausente
das duas camadas por construção.

## Lacunas do conjunto congelado (levantadas em 2026-08-10)

As 45 foram congeladas em 2026-07-29. Os requisitos abaixo entraram na spec
**depois** (achados de 2026-08-06 e 2026-08-07, que criaram a camada estruturada
e a camada de agentes). Nenhum deles pode ser suprido por anotação: exigem
pergunta nova, o que exigiria descongelar. Ficam registrados aqui para a decisão
do Ygor, e vigiados por `TestLacunasConhecidas`.

| Exigência da spec | Estado no conjunto congelado |
|---|---|
| Par de contraste de cobertura *"e o Nubank?"* × *"e o Inter?"* (5.13, 5.9.2) | **Ausente.** Não há nenhuma linha `so_painel`; a string "Inter" não aparece no gabarito. O lado `nenhuma` existe (5 linhas de Nubank), o lado `so_painel` não. Sem ele, a coluna `cobertura_esperada` não tem como ser falsificada. |
| Reconciliação ≥5, dentro das comparativas (5.13) | **2 de 5, e nenhuma comparativa.** `TSTF006` e `TSTF009` são factuais e cruzam release × CVM. As 11 comparativas são todas `release_gerencial` e não tocam a camada estruturada. |
| Fraseado não técnico ≥5 (5.13) | **2 ou 3 de 5.** Só `TSTA009` e `TSTA010` são plenamente leigas; `TSTA008` é limítrofe. As demais fixam a definição no enunciado ("segundo a divulgação gerencial… ROAE ajustado anualizado"), o que é exigido pela classe `release_gerencial` mas é o oposto do fraseado leigo. |
| Sete perguntas-semente do `diagnostico_e_objetivos.md` (5.13) | **0 de 7.** Nenhuma das oito da abertura está no conjunto — o que é coerente com a cronologia: elas foram escritas depois do congelamento. A oitava ("vale a pena comprar ações?") corretamente não entra: é do conjunto de ataques de 5.11. |
| Projeções ≥4, para o braço (B) de 5.9.2 | **1 de 4.** Só `TSTQ006` trata de guidance. |
| Nubank ≥4, nas adversariais (5.13) | **Cumprida:** 4 no conjunto `teste` (`TSTA001`–`TSTA004`) e 1 em `dev` (`DEV010`). |
| Consolidado × controladores no Banco do Brasil (5.5) | **Ausente.** As duas linhas contábeis são do Itaú e do Bradesco. Nenhuma pergunta exercita o BB, que é justamente onde as duas linhas divergem **23%** — o caso em que responder "lucro líquido" sem qualificar produz o maior erro. |

Consequência para o experimento de 5.9.3: o subconjunto de n = 15 previsto
(5 reconciliação + 6 cobertura + 4 projeções) **não é extraível** das 45 atuais.
O máximo hoje é 2 + 5 + 1 = 8, com o lado `so_painel` faltando — abaixo das seis
discordâncias que a própria spec fixa como piso para declarar diferença entre os
braços B e C.

**Resolvido em 2026-08-10 por separação, não por descongelamento:** as 45 ficam
intocadas como benchmark de recuperação e o experimento dos três braços passa a
rodar em `conjunto_agentes.csv`, descrito na seção seguinte.

## Conjunto da camada de agentes (`conjunto_agentes.csv`, spec 5.9.3)

**n = 15 · congelado em 2026-08-10 · 5 reconciliação + 6 cobertura + 4 projeções.**

### Por que um arquivo próprio, e não mais linhas nas 45

A regra de contenção de 5.13 — *acrescente coluna, nunca linha* — existe para
proteger o custo do gabarito manual, e é uma boa regra. Só que ela **já falhou
nos próprios termos**: as exigências de 5.9.2/5.9.3 nasceram dos achados de
06–07/08/2026, ou seja, **depois** do congelamento de 2026-07-29, e nenhuma
delas pode ser suprida por anotação. A medição está na tabela de lacunas acima:
o máximo extraível das 45 é 8 de 15, sem nenhum caso `so_painel`, e a string
"Inter" não aparece no gabarito. Espremer um subconjunto de 15 de onde só saem 8
seria fingir uma extração que os dados não sustentam — pior que separar.

A decisão (Ygor, 2026-08-10) é separar: as 45 permanecem **intocadas**, o
`perguntas.csv` não muda uma vírgula, e a camada de agentes ganha benchmark
próprio. Continua valendo a regra para o conjunto congelado; o que muda é que
capacidade que **não existia** quando ele foi congelado passa a ser medida fora
dele.

### Este conjunto não entra no benchmark E0–E3 (RNF11)

A RNF11 diz que o benchmark de recuperação E0–E3 **nunca** passa pela camada de
agentes — e diz também que medir a camada de agentes é obrigatório, em conjunto
próprio com seus próprios braços de comparação. É exatamente esta separação.

Três guardas tornam a fronteira verificável, em `tests/test_conjunto_agentes.py`:
`conjunto=agentes` em todas as linhas (nunca `teste`/`dev`), nenhum `id` colide
com os congelados (`AGTC`/`AGTR`/`AGTP` contra `DEV`/`TST*` — ids aparecem em
checkpoint, journal e respostas cacheadas) e nenhum enunciado é cópia de linha do
`perguntas.csv`. O cabeçalho também é deliberadamente diferente do congelado, de
modo que um arquivo não possa ser usado no lugar do outro por engano:
`carregar_conjunto_padrao` exige igualdade estrita de cabeçalho e recusaria este.

### Esquema — as cinco colunas da revisão 2 nascem aqui dentro

Ao contrário de `perguntas.csv`, este arquivo **não** separa as colunas da
revisão 2 num arquivo de anotação. A separação lá existe por um motivo medido —
mesclar mudaria o hash do gabarito e invalidaria checkpoint, journal e cache já
pagos —, e esse motivo não se aplica aqui: este conjunto não entra em nenhum
fingerprint de avaliação. Manter a separação seria repetir o custo sem o
benefício.

As 12 colunas de `perguntas.csv`, mais `camada_esperada` na posição canônica da
spec (entre `origem` e `locais_aceitos`, como o roteiro de fusão desta página
prevê), mais as outras quatro da revisão 2, mais três próprias deste arquivo:

| Coluna própria | Para que serve |
|---|---|
| `subconjunto` | `reconciliacao` · `cobertura` · `projecoes` — o eixo pelo qual 5.9.3 fatia a comparação dos três braços |
| `status_gabarito` | `verificado_painel` · `parcial_pendente_release` · `pendente_conferencia_humana` — o que já foi conferido por consulta e o que ainda espera leitura humana |
| `fonte_gabarito` | a **consulta SQL** que produziu cada valor contábil, e a página exata de cada valor que veio de release |

### Extensões de vocabulário, e por que cada uma

Quatro valores novos, cada um exigido por um comportamento que as 45 não pediam:

- **`origem=painel`** — o número não vem de tabela nem de texto de documento,
  vem da camada estruturada. Uma pergunta `so_painel` que declarasse `tabela`
  mentiria a própria procedência, e `n/a` diria que não há número quando há.
- **`cobertura_esperada=ambigua`** — quando o termo resolve para mais de uma
  companhia, **nenhum** dos três estados da RN12 é verdadeiro. `src/cobertura.py`
  devolve `cobertura=None` com `precisa_desambiguacao`; rotular de `ambas` faria
  um sistema que escolhe sozinho pontuar como acerto, apagando a RN11.
- **`rota_esperada=desambiguacao_entidade` e `=acompanhamento_projecoes`** — uma
  para cada braço de 5.9.2 que não existia no roteamento antigo.
- **`comportamento_aceito`** ganha `resposta_completa`,
  `resposta_parcial_marcada` (modo de falha 12b: o número **e** o nome do que
  falta), `pergunta_de_desambiguacao` (RN11), `divergencia_registrada` (5.9.5: o
  sistema apresenta as duas evidências em vez de eleger um vencedor) e
  `registro_sem_juizo` (5.9.2(B): o verbo é *registrar*, nunca *avaliar*).

`base_esperada` **não** ganhou valor novo: quando a resposta precisa apresentar
mais de uma definição na mesma frase — que é a tarefa das reconciliações — os
valores compõem com `|`, como `comportamento_aceito` já fazia nas 45
(`recusa|correcao_fundamentada`).

Em `motivo_recusa_esperado`, as linhas `so_painel` registram `fora_do_corpus`.
Não é recusa: é o motivo da **metade ausente**, e é o mesmo valor que
`Cobertura.motivo` emite em `src/cobertura.py`, o que torna a coluna comparável
contra a saída real.

### O que cada subconjunto exercita

**Cobertura (6)** — os três estados da RN12 mais a ambiguidade da RN11, todos
conferidos contra o painel real em 2026-08-10 e reproduzidos com
`src/cobertura.py`:

| id | Pergunta | Estado | Por que está aqui |
|---|---|---|---|
| `AGTC001` | *"E o Inter?"* | `so_painel` | INTER & CO, INC. (`080217`) está no painel e não no corpus — o lado que faltava |
| `AGTC002` | *"E o Nubank?"* | `nenhuma` | mesma frase, entidade trocada: o **par de contraste** que 5.13 exige |
| `AGTC003` | *"Quanto o BTG lucrou…"* | `ambigua` | "BTG" resolve para `022616` **e** `027774`; a resposta correta é perguntar |
| `AGTC004` | *"E o Banco Mercantil do Brasil?"* | `so_painel` | segundo `so_painel`, e a armadilha do token "BRASIL" (não é o `001023`) |
| `AGTC005` | *"E o C6 Bank?"* | `nenhuma` | segundo `nenhuma`, sem explicação registrada — o sistema deve dizer que não sabe explicar, não inventar |
| `AGTC006` | *"E o Santander?"* | `ambas` | controle positivo: sem ele, recusar tudo pontuaria bem |

O par `AGTC001`/`AGTC002` é literalmente a mesma frase com a entidade trocada —
o teste verifica isso por substituição de string. Um sistema que recusa as duas
acerta pela métrica antiga e erra pela nova.

**Reconciliação (5)** — cada uma cruza release e CVM na mesma resposta, com a
metade contábil conferida por consulta:

| id | Caso | O que só ela mede |
|---|---|---|
| `AGTR001` | BB 1T2026 | consolidado × controladores no BB: **22,8%** de diferença, ausente das 45 — mais o ajustado gerencial como terceira definição |
| `AGTR002` | Itaú 2T2025 | contábil BRGAAP → itens extraordinários → recorrente gerencial, e o IFRS da CVM ao lado |
| `AGTR003` | Bradesco 3T2025 | fraseado leigo: *"é o mesmo que ele registrou na CVM?"* — e a explicação precisa dispensar consulta externa |
| `AGTR004` | Santander 3T2025 | **o arquivo da CVM não fecha**: as parcelas somam R$ 356,9 milhões a menos que o consolidado. Registrar a divergência, não escolher nem "corrigir" |
| `AGTR005` | Itaú 4T2025 | o 4T do painel é **derivado** por diferença contra o 9M; apresentá-lo como arquivado é erro silencioso |

Nenhuma reconciliação usa o BTG: sob a RN11, **todas** as formas de superfície
("BTG", "BTG Pactual", "Banco BTG Pactual") são ambíguas no painel, e a pergunta
viraria um segundo caso de desambiguação em vez de medir reconciliação. O caso
do BTG está onde deve estar, em `AGTC003`.

**Projeções (4)** — o guidance do BB em 2025, que é o caso descrito em 5.9.2(B):
a faixa de Lucro Líquido Ajustado aparece "Em revisão" no release do 2T2025,
revisada no do 3T2025 e com realizado no do 4T2025. `AGTP001` é a pergunta leiga
(*"cumpriu a promessa?"*), cuja resposta certa exige descobrir **qual faixa
estava vigente**; `AGTP002` pergunta a faixa vigente numa data; `AGTP003` pede a
detecção da revisão com procedência; `AGTP004` põe lado a lado o realizado
gerencial e o lucro contábil de 2025 da CVM, que **não são comparáveis** — e
dizer isso é parte do acerto.

### Gabarito: o que está conferido e o que espera o Ygor

| `status_gabarito` | Linhas | Situação |
|---|---|---|
| `verificado_painel` | `AGTC001`–`AGTC005` (5) | valor conferido por consulta ao painel; a consulta está em `fonte_gabarito` e pode ser reexecutada |
| `parcial_pendente_release` | `AGTC006`, `AGTR001`–`AGTR005`, `AGTP004` (7) | a metade contábil está conferida por consulta; a metade que sai do release veio de **uma** leitura automática |
| `pendente_conferencia_humana` | `AGTP001`–`AGTP003` (3) | o gabarito inteiro sai de release; nada foi conferido por consulta |

**Pendência declarada:** 10 das 15 dependem de valores lidos do release. Eles
estão preenchidos a partir de **uma** extração automática, com a página física
registrada em `fonte_gabarito`, e marcados com `PENDENTE DE CONFERÊNCIA HUMANA`
no próprio texto — um teste falha se a marca sumir sem o status mudar. A dupla
leitura independente, em outra data, é trabalho do candidato, como nas 45.

Ponto de atenção para essa leitura: a figura *Projeções Corporativas* do BB sai
da extração automática **com as colunas embaralhadas** (intervalo, observado e
revisado se misturam). É a única fonte deste conjunto em que a leitura mecânica
não é confiável nem para conferir, e as três linhas `AGTP001`–`AGTP003`
dependem dela.

**Ainda não congelado para medição:** enunciado, `id` e composição estão fixos
desde 2026-08-10; os valores pendentes precisam da dupla leitura **antes** da
primeira execução dos três braços. Rodar o experimento contra gabarito não
conferido mediria o extrator, não os agentes.
