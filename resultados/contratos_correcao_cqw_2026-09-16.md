# Contratos de correção — CQW-01, CQW-02, CQW-03 e G0.4

**Data:** 2026-09-16. **Escrito ANTES de qualquer edição de código**, como o
§4.4 exige. Snapshot pré-onda: `artefatos/snapshots/2026-09-16-pre-cqw/`,
17 registros conferidos em `SHA256SUMS.txt`.

**Origem dos achados.** Três vêm da
[conferência independente de 15/09](conferencia_independente_qw1_qw8_2026-09-15.md)
(§2). O quarto vem do
[levantamento de desbloqueio de treino](pendencias_desbloqueio_treino_dfc_2026-09-15.md)
(§3, D1, quarto item) e **cresceu quando medido**: não é só que
`gate_g0([], [], [])` aprove — **G0.4 não existe no código**, embora o §4 do
pré-registro o congele.

> **⚠️ RESSALVA DE IMPLEMENTAÇÃO (2026-09-16).** Duas coisas apareceram ao
> executar o contrato e estão registradas aqui em vez de reescritas acima:
>
> 1. **H2.3 precisou de código, não só de preservação.** O contrato dizia
>    "`dt_ini` nulo é preservado como nulo". Medido contra o painel, o valor não
>    chega nulo: chega como `NaT` do pandas, e `NaT is None` é **falso**. Como
>    toda comparação com `NaT` também devolve falso, o sentinel atravessaria a
>    verificação de H2.3 sem acusar nada — a contraprova passava na fixture e
>    falhava no painel. `_procedencia` passou a normalizar `NaT`/`NaN` para
>    `None` (`_ou_nulo`). Isso normaliza um sentinel; não preenche data.
> 2. **`_executar_com` precisou dublar `carregar_nulos`.** G4.1 acrescentou um
>    carregador que `executar` chama, e o auxiliar de dublê não o cobria — seis
>    casos passaram a rodar o carregador real contra uma conexão falsa. Está na
>    tabela de mudanças de teste declaradas.

**O que esta onda NÃO faz.** Não reconstrói painel, não corrige célula, não
adjudica escala, não treina, não toca no holdout, não promove
`classe_anotada_ia` a `classe_confirmada`, não cura N2, não resolve N3, não
mexe no seletor de exemplar do esqueleto (contrato próprio, §6).

---

## E2 — CQW-01: vocabulário fechado aplicado na fronteira do consumidor

### Defeito

`documentos_defeituosos` confere a **existência** da chave `adjudicacao` e a
compara por igualdade com `ADJUDICA`. Não confere o **domínio**. Contraprova
executada contra o consumidor real:

| `adjudicacao` | Devolve |
|---|---|
| `rotulo_divergente_com_valor_identico_ao_da_dfp` | `{('000001','ITR','2020-06-30',1)}` |
| `None` | `set()`, sem exceção |
| `"estado_desconhecido"` | `set()`, sem exceção |
| `ADJUDICA + " "` | `set()`, sem exceção |
| `123` | `set()`, sem exceção |

Estado inválido significa **ausência de defeito**, e o documento volta ao
universo do gerador. O `ESTADOS_DE_DECLARACAO` **existe** com os nove estados
de E1.2; [o consumidor importa só `ADJUDICA` e `VERSAO_DO_ESQUEMA`](../scripts/esqueleto_plano_padrao.py#L99).

É a terceira reincidência do §4.4 regra 7 nesta linhagem de contratos:
cláusula que existe como texto e não participa da condição de decisão.

### Contrato

**E2.1 — o consumidor importa e aplica `ESTADOS_DE_DECLARACAO`.** Toda
declaração lida tem seu `adjudicacao` conferido contra a tupla dos nove
estados.

**E2.2 — fora do domínio levanta `InventarioIncompativel`**, com o valor
recusado no texto do erro. Vale para `None`, tipo diferente de `str`, texto
desconhecido e variação por espaço em branco.

**E2.3 — não normalizar.** `strip()`, `lower()` ou casamento aproximado estão
proibidos: um estado com espaço sobrando é inventário corrompido, não um
estado válido mal digitado.

**E2.4 — válido e não adjudicante continua devolvendo `set()`**, sem levantar.
Válido-e-vazio é estado diferente de inválido (§4.4 regra 5).

**E2.5 — a decisão é exercitada, não só o produtor.** Cada estado inválido tem
contraprova que chama `documentos_defeituosos` e observa a **exclusão**, não o
JSON do inventário.

### Alternativas rejeitadas

| Alternativa | Por que não |
|---|---|
| Normalizar com `strip()` antes de comparar | Aceitaria inventário corrompido como bom; esconde a causa |
| Tratar desconhecido como adjudicante (fail-safe) | Condenaria documento sem prova — é o defeito QW2 ao contrário |
| Validar no produtor (`adjudicar`) e confiar no consumidor | Foi exatamente essa confiança que criou CQW-01; o arquivo pode ser editado, truncado ou vir de outra versão |
| Validar com `set` em vez da tupla congelada | Perde a ordem declarada de E1.2, que o resumo publica |

### Aceitação

Os nove estados válidos passam; os quatro inválidos da tabela levantam;
`documentos_defeituosos()` contra o inventário real continua devolvendo
**111 documentos em 35 companhias** — medido antes da edição.

---

## H2 — CQW-02: linhagem temporal completa do ativo

### Defeito

H1.4 exige `trimestre`, `dt_ini`, `dt_fim` e `dt_receb` da janela, do rótulo
**e do ativo**. Medido no painel real, sobre as 10.605 observações:

| Linhagem | Campos |
|---|---|
| `rotulo` | `trimestre`, `dt_ini`, `dt_fim`, `dt_receb` |
| `janela` | `trimestre`, `dt_ini`, `dt_fim`, `dt_receb` |
| **`ativo`** | **`trimestre`, `dt_receb`** |

[`carregar_ativo` já seleciona `dt_ini_exerc AS dt_ini`](../scripts/auditar_rank03b_consumo_operacional.py#L216)
— o campo é carregado e **descartado** na construção. Falta só `dt_fim_exerc`
na consulta.

### Contrato

**H2.1 — `carregar_ativo` seleciona também `dt_fim_exerc AS dt_fim`.**

**H2.2 — a linhagem do ativo carrega os quatro campos de H1.4**, pelo mesmo
`_procedencia` da janela e do rótulo, sem recombinar: os quatro saem da linha
eleita por `vigente_em`.

**H2.3 — `dt_ini` nulo é preservado como nulo.** Medido: **23.395 de 23.395**
linhas de `BPA`/`cd_conta = '1'` têm `dt_ini_exerc` nulo, porque saldo de
balanço é posição numa data, não período. Inventar início é fabricar dado
(§4.4 regra 9). `dt_fim_exerc` é nulo em **0** delas.

**H2.4 — a banda de duração NÃO se aplica ao ativo.** `_encadeada` e
`_contigua` continuam valendo só para janela e rótulo. Submeter saldo a banda
de fluxo acusaria defeito onde há só natureza contábil diferente.

**H2.5 — G1 não ganha verificação nova.** G1.1 do pré-registro exige
`dt_receb <= D` para toda feature, e isso **já** vale para o ativo. Esta
correção é de **linhagem contratada e auditabilidade**, não de vazamento: não
foi encontrado vazamento temporal por este achado. Inventar aqui um critério
que o pré-registro não congelou seria mudar o gate depois de conhecer o
resultado.

### Alternativas rejeitadas

| Alternativa | Por que não |
|---|---|
| Preencher `dt_ini` com `dt_fim` ou com o início do trimestre | Fabrica período para um saldo; §4.4 regra 9 |
| Revisar H1.4 para pedir só dois campos do ativo | Legítimo, mas some com a auditabilidade que o contrato queria; e a correção custa uma coluna |
| Acrescentar verificação de duração do ativo em G1 | Saldo não tem duração; reprovaria 100% das observações |
| Acrescentar `dt_fim <= D` a G1 | Critério novo, não congelado no pré-registro §5 — mudar gate depois do resultado |

### Aceitação

`Counter` dos campos da linhagem do ativo devolve os quatro nomes para as
10.605 observações; `dt_ini` sai `None` e o teste **exige** que saia `None`;
`gate_g1` continua com as sete contagens em zero e `aprovado` inalterado.

---

## G4 — G0.4 implementado, e G0 que não aprova por ausência

### Defeito

O §4 do pré-registro congela quatro verificações. O código publica contadores
para G0.1, G0.2 e G0.3. **Não há contador algum de G0.4** — nem no código nem
no artefato publicado. E os três carregadores filtram `valor_reais IS NOT NULL`
([163](../scripts/auditar_rank03b_consumo_operacional.py#L163),
[191](../scripts/auditar_rank03b_consumo_operacional.py#L191),
[223](../scripts/auditar_rank03b_consumo_operacional.py#L223)): mesmo que o
contador existisse dentro de `gate_g0`, ele seria **estruturalmente incapaz de
ver um nulo**. Guarda vazia por construção.

Além disso, `gate_g0([], [], [])` devolve `aprovado = True`: sem nada medido,
aprova. É o §4.4 regra 4 — *guarda que aprova por ausência de dado é pior que
guarda nenhuma* —, a mesma que já obrigou `gate_g1` a reprovar amostra vazia.

### Contrato

**G4.1 — G0.4 é medido fora dos carregadores filtrados.** Função própria
`carregar_nulos(con)`, no mesmo universo elegível (`plano_contas NOT LIKE
'll3_09_%' AND NOT is_banco`), **sem** `IS NOT NULL`, devolvendo por conta
requerida o total de linhas e o total de nulos.

**G4.2 — `gate_g0` recebe a medição como quarto argumento.** A função
continua **pura** — recebe listas e dicionários, não conexão. É o que a torna
testável e o que permitiu as contraprovas de G0.1–G0.3.

**G4.3 — G0.4 participa da aprovação.** Publica
`g0_4_nulos_nas_contas_usadas`, `g0_4_por_conta` e
`g0_4_contas_sem_linha_alguma`. Aprova só se **toda** conta requerida tiver
`total > 0` **e** `nulos == 0`. Conta requerida sem linha nenhuma é ausência de
dado: reprova, não aprova.

**G4.4 — medição ausente não aprova.** Payload vazio ou faltando uma conta
requerida reprova com motivo. É a contrapartida de G4.3 para o caso em que a
própria medição não aconteceu.

**G4.5 — universo inteiramente vazio reprova (G0.0).** Se `fco`, `ativo` e
`duracoes` chegarem **os três** vazios, `gate_g0` reprova com
`motivo`, publicando `g0_0_fontes_vazias`. Espelha o
`bool(amostra)` de `gate_g1`.

**G4.6 — a granularidade de G0.0 é deliberada.** Reprovar quando **qualquer**
fonte vem vazia quebraria
[`test_salto_de_escala_reprova_acima_da_tolerancia`](../tests/test_rank03b_consumo_operacional.py#L182),
que passa `fco = []` e `duracoes = []` **de propósito**, para isolar G0.3. Esse
teste é legítimo e não será enfraquecido (§4.4). A ausência que o achado
denuncia é a do universo inteiro.

**G4.7 — o limiar publicado passa a citar G0.4**, para que o artefato diga a
regra que o código aplica.

### Alternativas rejeitadas

| Alternativa | Por que não |
|---|---|
| Tirar `IS NOT NULL` dos três carregadores | Nulo entraria em `construir_amostra` e viraria aritmética com `None`; troca uma guarda vazia por um defeito real |
| Medir G0.4 dentro de `gate_g0`, recebendo a conexão | Destrói a pureza que sustenta todas as contraprovas de G0 |
| Exigir as três fontes não vazias | Enfraqueceria/quebraria um teste de isolamento legítimo — proibido pelo §4.4 |
| Deixar G0.4 como diagnóstico fora da aprovação | É exatamente o achado F10/regra 7 que esta onda existe para não repetir |
| Não implementar, por dar zero hoje | "Mede zero hoje" não é "guarda existe"; o pré-registro congelou a verificação |

### Aceitação

Medido **antes** da edição, no painel real e no universo elegível:

| Conta | Linhas | Nulos |
|---|---:|---:|
| FCO `6.01`, `DFC%`, `tipo_periodo = 'trimestral'` | 22.034 | **0** |
| Ativo `1`, `BPA` | 22.471 | **0** |

Logo **G0.4 não pode mudar o veredito**: G0 continua reprovando por G0.3
(132 saltos, fração 0,005874, limiar 0,005) e `primeiro_reprovado` continua
`G0`. Se mudar, a implementação está errada — não o painel.

**Quebra de hash declarada.** `artefatos/rank03b/auditoria.json` sai de
`a2ef88bea647777797d909624662bfe2761ab6ceaaaf4f5eae7f4b2e3d327ee0` porque
passa a publicar os campos de G0.4 e G0.0. É implementação de cláusula
congelada do pré-registro, não alteração de contrato. O veredito, o
`primeiro_reprovado`, a fração de G0.3 e todos os inventários de G0.1–G0.3
ficam **idênticos**, e isso é conferido campo a campo contra o snapshot.

---

## DOC — CQW-03 e sincronização documental

**DOC.1 — errata de CQW-03 por ressalva datada, nunca reescrita.** O
[relatório de implementação](implementacao_qw1_qw8_2026-09-15.md) diz
**154.160** declarações na linha 59. O valor certo é **156.100**, confirmado
em duas contas independentes (soma de `len(declaracoes)` no JSONL e soma de
`declaracoes_por_estado` no resumo), sobre 34.952 casos. Diferença: 1.940.
**As contagens por estado publicadas na mesma frase estão certas** e somam
exatamente 156.100 — só a manchete erra.

**DOC.2 — hash do CSV.** O mesmo relatório fixa `db597d3a…` para
`corpus/cvm/plano_padrao_contas.csv` (linhas 262 e 286). O arquivo hoje é
`fa271cd3…`, pela anotação dimensional de 15/09. Ressalva datada com a cadeia
`b58dbe01 → db597d3a → fa271cd3`.

**DOC.3 — "11 colunas".** O
[dossiê de 14/09](dossie_revisao_quatro_ondas_2026-09-14.md) (linha 244) diz
300 contas e 11 colunas. São **20** desde a anotação. Ressalva datada.

**DOC.4 — o parecer do revisor NÃO se corrige.** A conferência fixa
`db597d3a…` e estava **certa na data em que foi escrita**. Documento de revisor
independente não se reescreve para acompanhar o repositório.

**DOC.5 — AGENTS.md ganha o estado vigente do plano de contas**, incluindo que
a anotação é por IA e não é validação humana, e que `classe_confirmada`
continua vazia.

**DOC.6 — três observações medidas nesta conferência entram no registro**,
porque nenhum dos dois documentos as traz:

1. O `fundamento_anotacao_ia` tem **7 valores distintos** em 300 linhas
   (o maior cobre 111); `fonte` tem 6; `escopo` tem 1. O que é genuinamente
   por linha é a procedência: **300/300** contextos distintos.
2. A informação incremental da anotação sobre a proposta estatística é de
   **11 linhas**: 2 resolvem `INDEFINIDA`, 9 **retratam** para inconclusivo.
   Nas 289 restantes as duas concordam, e as 7 "por ação" são exatamente as 7
   que a magnitude já apontava.
3. Só **110 de 300** `ds_conta_exemplo` são a descrição **modal** da chave;
   190 divergem, dos quais 9 são o marcador `0`/`-`. É defeito do
   `min(ds_conta)` do gerador, não do dado. **A conclusão dimensional
   sobrevive**: entre as 300 chaves não há nenhuma descrição por ação fora de
   `3.99`, e sob `3.99` todo o topo é classe de ação ou "por Ação".

---

## Mudanças de teste declaradas

O §4.4 proíbe enfraquecer asserção para fazer código passar e exige que
substituição exigida por contrato seja **declarada**, no docstring do caso e
aqui.

| Teste | Mudança | Por que o contrato exige |
|---|---|---|
| `TestGateG0::test_dado_limpo_aprova` | Passa a receber o payload de G0.4 | G4.2 muda a assinatura; sem o payload o caso afirmaria aprovação sobre gate que não mede G0.4 |
| `TestGateG0::test_soma_dos_dois_metodos_reprova` | idem | idem |
| `TestGateG0::test_periodo_semestral_rotulado_trimestral_reprova` | idem | idem |
| `TestGateG0::test_duracao_e_medida_por_linha_nao_pelo_grupo` | idem | idem |
| `TestGateG0::test_salto_de_escala_reprova_acima_da_tolerancia` | idem; **continua passando `fco=[]` e `duracoes=[]`** | G4.6 preserva o isolamento de propósito |
| `TestContratosQW3aQW7::_executar_com` | Passa a dublar também `carregar_nulos`; `gate_g0` continua dublado | G4.1 acrescentou um carregador que `executar` chama. Sem o dublê, seis casos rodavam o carregador real contra a conexão falsa e estouravam. A assinatura verdadeira de `gate_g0` é exercitada por `TestGateG0`, não aqui |
| `_ativo` (auxiliar do arquivo) | Ganha `dt_fim`, derivado do rótulo do trimestre; `dt_ini` continua `None` | H2.1/H2.2 acrescentaram o campo à linha-fonte do ativo; sem ele `_procedencia` levantaria `KeyError` |

**Nenhuma asserção existente é removida ou afrouxada.** Toda alteração é
acréscimo de argumento exigido por G4.2.

---

## Condições de falsificação

Esta onda está **errada** se qualquer uma se verificar:

| # | Condição | Estado |
|---|---|---|
| 1 | `documentos_defeituosos()` deixar de devolver 111 documentos / 35 companhias | |
| 2 | Algum dos nove estados válidos de E1.2 passar a levantar | |
| 3 | `gate_g1` deixar de ter as sete contagens em zero no painel real | |
| 4 | A contagem de observações sair diferente de 10.605 / 494 companhias | |
| 5 | `dt_ini` do ativo sair diferente de `None` em qualquer observação | |
| 6 | `veredito` ou `primeiro_reprovado` de `auditoria.json` mudarem | |
| 7 | `g0_3_fracao`, `g0_3_saltos_de_escala` ou qualquer inventário de G0.1–G0.3 mudarem | |
| 8 | G0.4 acusar nulo onde a medição direta no painel acusa zero | |
| 9 | `gate_g0([], [], [], limpo)` continuar aprovando | |
| 10 | A CLI quebrar **depois** de gravar o artefato (defeito QW7) | |
| 11 | A suíte cair abaixo de 2.202, ou aparecer skip | |
| 12 | Qualquer hash de `cvm.duckdb`, `cvm_treino.duckdb`, do CSV anotado, do inventário ou do pré-registro mudar | |
| 13 | Os seis arquivos da outra frente mudarem | |

Os hashes de referência são os do snapshot
`artefatos/snapshots/2026-09-16-pre-cqw/SHA256SUMS.txt`.
