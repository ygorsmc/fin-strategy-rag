# Contratos de correção — QW1 a QW8 da conferência de 15/09

**Data:** 2026-09-15 · **Escrito ANTES de qualquer alteração de código.**
**Origem:** [conferência independente das quatro ondas](conferencia_quatro_ondas_2026-09-15.md)
(`4c768b5970b2…`).
**Snapshot de partida:** `artefatos/snapshots/2026-09-15-pre-qw1-qw8/`, com
`SHA256SUMS.txt`. Os 13 hashes do §6 da conferência **conferem** — a onda parte
da versão conferida.
**Suíte de partida:** **2.093 passed, zero falha, zero skip** (inclui a frente
de interface/geração que mudou durante a pausa da conferência; não é tocada
aqui).

---

## Natureza desta onda, e o que ela NÃO é

Corrige **instrumento, evidência e consumidores**. Não reconstrói painel, não
corrige célula, não remede o alvo, não autoriza treino. O Rank 3-B continua
`REPROVADO EM G0`; o pré-registro `fbae30cc…` continua consumido.

**Artefatos que serão regenerados, declarados antes:**

| Artefato | Por quê | Condição |
|---|---|---|
| `artefatos/escala_cvm/{inventario.jsonl,resumo.json}` | a regra de adjudicação muda (QW1/QW2) | varredura dos 31 ZIPs, custo zero; contagem de linhas e de conflitos **não pode** mudar |
| `corpus/cvm/plano_padrao_contas.csv` | o conjunto de exclusão muda (QW1/QW8) | só se `classe_confirmada` estiver vazia nas 300 linhas; o original fica no snapshot |
| `artefatos/rank03b/auditoria.json` | a CLI passa a terminar (QW7) | tem de sair **byte-idêntico** (`a2ef88be…`) |

---

## 0. Reprodução antes de aceitar

Todas as reproduções do §4 da conferência foram executadas em 15/09, sem gravar
nada, e **todas devolveram o número do revisor**:

| Achado | Revisor | Reproduzido |
|---|---|---|
| QW1 | 10.261 adjudicados, 6.736 só com zero; 14 de 127 documentos só zero (3.502 linhas); 67 fora do balanço, todos zero | idem |
| QW2 | 124 casos sem DFP do valor; 292 declarações extrapoladas em 235 casos | idem |
| QW3 | G0 e G1 aprovam com `3T2019` datado de jan–mar | idem |
| QW4 | `PRONTO PARA CHALLENGER` com AUC/IC `None` e `completo=True` | idem |
| QW5 | amplitude 1,0 perdida por exceção com 499 observações | idem |
| QW6 | `(0, 1)` → `(0, 0)` com outra descrição no 2T | idem |
| QW7 | `KeyError('defeito_valor_bruto_continuo')` após 1 escrita | idem |
| QW8 | inventário ausente → `set()` | idem |
| §6 | corpo da validação de 11/09 recompõe `edfee5d6…` | idem |

**Nenhum achado contestado.**

### Dois achados novos, desta sessão, que ampliam QW3 e QW6

**N1 — o horizonte usa rótulo civil; o painel rotula pelo exercício fiscal.**
A carga numera trimestres a partir do início do exercício social
(`src/dados_estruturados.py`, `ordinal_trimestre`/`ano_exercicio`). Em
**23 das 691 companhias** elegíveis com FCO há trimestres de exercício não civil
(início em abril, julho, março, outubro). `primeiro_trimestre_apos(D)` devolve o
rótulo **civil** e a construção o casa pelo **texto**. Medido em memória sobre o
painel real, a construção atual aceita **322 observações em 15 companhias
(3,0% de 10.670) cujo trimestre de rótulo começou antes de D**. Exemplo:
`009539`, exercício iniciado em julho, `D = 2013-09-09` recebe como q1 o
"4T2013" — **abr–jun/2013, já encerrado**. Mais **8 observações em 3
companhias** com rótulo cujas datas não encadeiam (`019836` "3T2013" datado
out–dez/2012). O G1 atual aprovaria todas. **O resultado publicado não é
afetado** só porque G0 reprova antes.

**N2 — "antecedente inexistente" é grande, e boa parte é deriva de descrição.**
Sobre os arquivados, excluídos os períodos que já têm isolado publicado, há
**~140 mil acumulados sem antecedente** na partição da derivação (DFC_MI 2T
75.725; 3T 61.477; DFC_MD e DRE ~2,9 mil). No 2T da DFC, de 264.899 acumulados,
76.923 não têm antecedente com o mesmo código **e descrição**, mas só 22.308
não têm com o mesmo **código** — a descrição normalizada muda entre
arquivamentos e parte a partição. Pré-existente à onda D1; hoje, silencioso.

---

## QW1 + QW2 — evidência por declaração no inventário

### Defeito

Uma coincidência qualquer de valor bruto sob duas escalas — **inclusive zero** —
adjudicava o **caso inteiro** para a escala da DFP, e o consumidor condenava
**toda** declaração de escala diferente, **mesmo com outro valor**.
`0 × 1.000 = 0 × 1` não identifica escala; e `100.000 UNIDADE` representa
exatamente os `100 MIL` da DFP.

### Contrato

**E1.1 — três camadas, com nomes distintos.**
(i) *conflito de metadado*: a chave tem mais de uma `ESCALA_MOEDA`;
(ii) *evidência informativa não nula*: algum valor bruto **≠ 0** aparece sob
duas escalas — prova que **algum** rótulo do caso está errado, não **qual**;
(iii) *adjudicação por declaração*: decide sobre **uma** declaração.

**E1.2 — vocabulário fechado de estado por declaração** (`adjudicacao`):

| Estado | Quando |
|---|---|
| `referencia_auditada` | declaração da DFP, e a DFP declara uma escala só |
| `dfp_ambigua` | declaração da DFP, e a DFP declara mais de uma escala |
| `sem_referencia_auditada` | não-DFP, e a DFP está ausente ou ambígua |
| `mesma_escala_da_referencia` | não-DFP com a mesma escala da DFP |
| `zero_nao_informativo` | não-DFP de escala diferente com valor bruto zero |
| **`rotulo_divergente_com_valor_identico_ao_da_dfp`** | não-DFP de escala diferente cujo valor bruto **≠ 0** é **idêntico** ao de uma declaração da DFP — **único estado que adjudica** |
| `equivalente_em_reais_a_dfp` | escala diferente, valor bruto diferente, **mesmo montante em reais** que uma declaração não nula da DFP, na precisão da escala mais grossa (meia unidade dela) — evidência de rótulo **certo** |
| `evidencia_contraditoria` | idêntico a uma declaração da DFP **e** equivalente em reais a outra |
| `sem_prova` | nenhum dos anteriores |

**E1.3 — veredito do caso.** `ADJUDICAVEL_PELA_DFP` se e somente se ao menos uma
declaração estiver no estado que adjudica. Caso contrário `INDECIDIVEL`, com
motivo enumerado (só zero coincide; coincidência só entre ITRs; nenhuma
coincidência; DFP ausente ou ambígua).

**E1.4 — zero nunca prova, nem como referência.** Valor zero da DFP não serve de
termo de comparação para identidade nem para equivalência.

**E1.5 — a premissa é publicada como premissa.** Adjudicar supõe que a DFP anual
auditada tem o rótulo certo quando o mesmo número não nulo aparece sob outra
escala. Isso é **premissa**, não prova; vai escrito no `resumo.json` e no motivo
de cada caso adjudicado.

**E1.6 — o campo de grupo muda de nome, de propósito.** `escala_correta` sai;
entra `escala_da_referencia_auditada`. Consumidor antigo que comparava toda
declaração com a escala do grupo passa a **falhar alto** em vez de continuar
extrapolando em silêncio.

**E1.7 — o resumo diz a regra que o código aplica.** A chave publicada passa a
ser `(cd_cvm, demonstrativo, cd_conta, dt_ini_exerc, dt_fim_exerc)` — fecha o
§9.1 do dossiê. Acrescenta `versao_do_esquema = 2`, contagem por estado de
declaração e documentos com declaração adjudicada, por
`(cd_cvm, conjunto, dt_refer, versao)`.

**E1.8 — escala desconhecida falha.** Fator fora de `{UNIDADE, MIL, MILHAO}`
levanta erro, em vez de comparar com fator inventado.

### Alternativas rejeitadas

| Alternativa | Por que não |
|---|---|
| Excluir os 6.736 casos de zero e certificar o resto | Rejeitada pela própria conferência: 292 condenações extrapoladas e 124 coincidências sem DFP continuariam |
| Manter adjudicação por caso, só sem zero | Continua condenando `100.000 UNIDADE` pelo `100 MIL` do grupo (QW2) |
| Igualdade de valor bruto com tolerância | Limiar novo. Usa-se a igualdade após o arredondamento de duas casas que o inventário já aplicava |
| Tratar "equivalente em reais" como erro | É evidência de que aquele rótulo está **certo** |
| Maioria de votos ou plausibilidade | Já recusadas na regra original; continuam |

### Critérios de aceitação — contraprovas

1. Zero sob duas escalas **não** adjudica (contraprova C.1 da conferência).
2. DFP `100 MIL`, ITR `100000 UNIDADE`, ITR `100 UNIDADE`: **só** o `100
   UNIDADE` é adjudicado; o `100000` sai `equivalente_em_reais_a_dfp`
   (contraprova C.2).
3. DFP com outro valor não nulo: `sem_prova`.
4. Reapresentação na DFP (v1 `100 MIL`, v2 `110 MIL`) com ITR `100 UNIDADE`: o
   ITR é adjudicado por identidade com v1; ITR `105 UNIDADE` sai `sem_prova`.
5. Coincidência só entre ITRs: `INDECIDIVEL`, com evidência informativa não nula
   marcada.
6. Contradição (idêntico a uma DFP e equivalente a outra): não adjudica.
7. Não-regressão: o caso `003549` em miniatura continua adjudicado; valor
   diferente, DFP ambígua, sem DFP e maioria continuam recusados; determinismo
   e procedência preservados.

### Impacto previsto nos testes

Quatro casos existentes afirmam sobre `escala_correta`; a asserção passa a ser
sobre `escala_da_referencia_auditada` **com o mesmo valor** (renomeação de campo,
E1.6). Nenhuma asserção removida.

### Previsão registrada antes da varredura

Aplicada aos casos persistidos, a regra por declaração (sem os estados E1.4 de
zero-referência e contradição) deu **6.456 declarações adjudicadas, 3.401 casos,
111 documentos em 35 companhias, todos de BPA/BPP**. Os dois estados a mais só
podem **mover** declarações entre estados que não adjudicam ou **reduzir** as
adjudicadas. Previsão: **≤ 6.456 / ≤ 3.401 / ≤ 111**, e a varredura nova tem de
coincidir com a readjudicação dos casos persistidos — a varredura e a chave não
mudam. **Linhas lidas (26.267.152) e casos conflitantes (34.952) não podem
mudar.** Dos 127 documentos antigos, prevê-se a saída de **16**: 14 só com zero
(os da conferência) e 2 condenados por extrapolação (`021520/2016-09-30`,
`027006/2022-09-30`).

---

## QW8 + identidade do documento — esqueleto

**K1.1 — inventário ausente falha** (`InventarioAusente`), nunca `set()`.
**K1.2 — inventário de esquema anterior falha** (`InventarioIncompativel`):
sem `versao_do_esquema = 2` no resumo ou sem `adjudicacao` nas declarações, a
leitura antiga extrapolaria. Esquema não reconhecido é *não sei* (§3.15).
**K1.3 — inventário válido sem adjudicação** devolve conjunto vazio, sem erro —
estado distinto de ausente.
**K1.4 — exclui só documentos com declaração adjudicada**, identificados por
`(cd_cvm, conjunto, dt_refer, versao)`. O `conjunto` faltava; medido hoje,
**zero colisões** ITR×DFP — efeito nulo, declarado.
**K1.5 — denominadores e limites escritos.** O universo da cobertura é
`origem = 'arquivado'` fora dos documentos excluídos; a docstring publica os
três universos da conferência. `ds_conta_exemplo` é exemplo, não conceito
(DRE/3.04). A chave `(demonstrativo, cd_conta)` **não** é semântica entre planos
(RN09): o contrato futuro de correção não pode fazer junção universal por código.
**K1.6 — regenerar o CSV** só depois de conferir `classe_confirmada` vazia nas
300 linhas; publicar o diff de linhas e propostas.

| Alternativa rejeitada | Por que não |
|---|---|
| Aviso e seguir com `set()` | É o defeito: calcula sobre tudo prometendo excluir |
| Manter os 127 antigos | Herdaria QW1/QW2 na seleção da amostra |

**Aceitação:** caminho ausente levanta; esquema antigo levanta; inventário
válido sem adjudicação devolve vazio; exclusão usa `conjunto`; as checagens
contra o CSV real continuam (Ativo Total com razão 1,0; LPA não monetário;
confirmação vazia).

---

## QW3 + N1 — horizonte pelas datas e G1 que verifica

### Contrato

**H1.1 — q1 vem das datas da linha.** Entre as linhas de rótulo (a mais recente
publicada por trimestre — regra de desfecho inalterada), q1 é a de **menor
`dt_ini` estritamente posterior a D**, e só é q(D) se
**`dt_ini ≤ D + 3 meses`** — trimestres de três meses começam a cada três
meses, então o primeiro início posterior a D cai nesse intervalo. Fora dele, o
trimestre contratual falta: **censura** (`rotulo_incompleto_em_q_de_D`), nunca
deslocamento.

**H1.2 — q2..q4 por ordinal fiscal e datas encadeadas.** Cada um existe
(senão `rotulo_incompleto_em_q_de_D`) e começa no dia seguinte ao fim do
anterior (senão `identidade_temporal_do_rotulo_nao_confere`).

**H1.3 — janelas de features:** contíguas por ordinal (inalterado) **e** com
datas encadeadas (senão `identidade_temporal_da_janela_nao_confere`).

**H1.4 — a observação carrega linhagem** (trimestre, `dt_ini`, `dt_fim`,
`dt_receb` da janela, do rótulo e do ativo), usada por G1 e nunca publicada.

**H1.5 — `D` publicado como data ISO.** Em dado real saía
`'2013-03-08 00:00:00'`.

**H1.6 — `gate_g1` verifica pela linhagem, com código próprio**, publicando cada
contagem: G1.1 features/ativo com `dt_receb > D`; G1.2 q1 fora de
`(D, D + 3 meses]`; G1.3 rótulo com `dt_ini ≤ D`; R2.5 rótulo ou janela sem
contiguidade de ordinal ou de datas, chave `(companhia, D)` repetida,
observação sem linhagem. **Aprova só com amostra não vazia e todas as contagens
zero.** Amostra vazia reprova com motivo (§4.4 regra 4).

**H1.7 — G1 é decisivo e para a cadeia**, como G0: sem T1, T2 nem baseline sobre
amostra que não é point-in-time. Veredito `REPROVADO EM G0/G1`,
`primeiro_reprovado = G1`.

### Alternativas rejeitadas

| Alternativa | Por que não |
|---|---|
| Exigir rótulo fiscal = rótulo civil | Censura as 23 companhias de exercício não civil inteiras — perde dado legítimo |
| Datas iguais aos limites do trimestre civil | 540 linhas reais de exercício não civil falhariam sem defeito |
| Inferir o calendário fiscal de cada companhia pelo rótulo | Mesmo resultado com mais código, e quebra em mudança de exercício |
| G1 só por construção | Vacuidade: foi assim que `bool(amostra)` passou |
| G1 reprovar sem a construção censurar | Uma linha mal rotulada invalidaria a rodada; o §2 do pré-registro manda **descartar** quando o FCO do trimestre falta |

### Aceitação

1. Caso da conferência (`3T2019` datado jan–mar): nenhuma observação em
   `D = 2019-05-10`, descarte contado.
2. **Exercício iniciado em julho:** q1 é o trimestre fiscal iniciado após D e
   nenhum início de rótulo é ≤ D (hoje viola).
3. G1 alimentado com observação violadora (construção contornada) **reprova e
   para a cadeia**.
4. Série regular: G1 aprova — sem este caso um `False` fixo passaria.
5. Amostra vazia: G1 reprova.
6. Os casos R2 existentes passam sem alteração.

**Impacto nos testes:** o auxiliar `_veredito` de `TestContratosR1aR5` passa a
fixar `gate_g1` aprovado, como já fixa `gate_g0` — isola o consumidor da decisão
agora que G1 verifica de fato. Declarado.

**Medição prevista:** reconstruída em memória sobre o painel real, a construção
aceita **zero** observações com violação de G1.2, G1.3 ou encadeamento.

---

## QW4 — completude exige métricas e intervalos válidos

**B1.1 — as três métricas do §8 com IC95% agrupado por companhia**, com nomes
explícitos: `auc_agregada_ic95`, `precisao_no_top_10pct_ic95`,
`auc_intra_companhia_ic95`, cada um `{inferior, superior,
reamostragens_validas}`.

**B1.2 — IC só existe com ao menos 40 reamostragens válidas** (`⌈1/0,025⌉`):
abaixo disso uma cauda de 2,5% não contém nenhuma reamostragem e o "intervalo" é
um ponto. O número deriva do nível de 95% registrado, não do dado.
**Julgamento declarado para o revisor.**

**B1.3 — `completo=True` exige:** pisos de suporte (inalterados); os dois
rótulos no suporte; AUC agregada, AUC intra, precisão e lift não nulos; os três
IC calculados. Senão `completo=False` com `motivos_de_incompletude`.

**B1.4 — `_auc` por postos médios**, O(n log n), com aritmética inteira até a
divisão final: **mesmo valor** da definição por pares com meio ponto no empate.
Necessário para bootstrapar três métricas × 2.000 × 3 baselines.

| Alternativa rejeitada | Por que não |
|---|---|
| Completude só por suporte | É o defeito |
| IC só da AUC | O §8 nomeia as três |
| Exigir 100% de reamostragens válidas | Limiar novo; reprova concentração legítima |
| Mínimo de 30 companhias com os dois rótulos na AUC intra | Critério novo; valeria também para T2 — é matéria de protocolo |
| Inventar AUC para B0 | A conferência confirmou B0 correto |

**Aceitação:** caso D.1 da conferência (B3 só com negativos) → B3 incompleto com
motivo, veredito **`INDECIDIVEL`**; tudo válido → `PRONTO PARA CHALLENGER`
(não-regressão); AUC por postos = AUC por pares em dado aleatório com empates;
com `REAMOSTRAGENS = 39`, IC `None` e baseline incompleto.

**Impacto nos testes:** `test_R4_baselines_publicam_as_metricas_do_paragrafo_8`
troca os nomes genéricos `ic95_inferior`/`ic95_superior` pelos três IC
explícitos — asserção **mais forte**, declarada.

---

## QW5 — piso de observações por componente

**S1.1** — no T1, observações **ou** companhias abaixo do mínimo tornam o
componente `INSUFICIENTE`, e o laço continua.
**S1.2** — bootstrap da zona cinzenta sem reamostragem válida torna o
componente `INSUFICIENTE` com motivo, sem interromper T1.

**Aceitação:** caso D.2 da conferência → `fco_ttm_sobre_sd8` insuficiente com
499 observações **e** `fco_ttm_em_D` registrado com amplitude 1,0 → T1
`reprova_numericamente`. Casos R5 existentes inalterados.

---

## QW7 — CLI

**C1.1** — `principal()` lê o formato atual do diagnóstico (recorte pertinente a
G0) e **compõe o que imprime antes de gravar**: formato divergente falha antes
de qualquer escrita.
**C1.2** — a CLI real termina com **código 2** e regrava `auditoria.json`
**byte-idêntico**.

**Aceitação:** com o JSON publicado, devolve 2 e grava uma vez; com diagnóstico
em formato antigo, levanta **sem** gravar.

---

## QW6 + N2 — derivação: a mesma relação para inserir e para recusar

**D2.1 — uma relação de candidatos.** Identidade da inserção
(`coalesce(conceito, 'conta:' || cd_conta || '|' || ds_conta_norm)`), mesmos
predicados e a banda como marcador. Criado = candidato na banda, com o mesmo
`QUALIFY`; recusado = grupo `(companhia, demonstrativo, trimestre, chave)` com
antecedente e **nenhum** candidato na banda.

**D2.2 — antecedente inexistente é estado próprio.** Grupo sem antecedente com
valor é **`sem_antecedente`**: contado à parte, aviso próprio, nunca somado à
recusa pela banda — as causas diferem (não há aritmética possível × a aritmética
cobriria mais de um trimestre). **A deriva de descrição (N2) não é corrigida
aqui:** mudar a identidade de pareamento toca a RN09 e todos os consumidores.

**D2.3 — retorno nomeado** `ResultadoDaDerivacao(criados, recusados,
sem_antecedente)`; o carregador emite os dois avisos. Testes que desempacotavam
duas posições passam a ler atributos — adaptação de assinatura, declarada.

**D2.4 — contraprova no carregador**, sobre `relatorio.avisos`: aviso de recusa
presente quando há recusa (fixture sem o 1S de `6.01`) e **ausente** quando não
há; aviso de `sem_antecedente` presente quando há.

**D2.5 — o teste que se dizia "1S sem 1T"** usa 1T e 9M sem o 1S: docstring
corrigida, asserções iguais. Caso literal "só o 1S" acrescentado.

**D2.6 — números corrigidos nas docstrings:** 513 companhias, não 507 (507 é só
o grupo de 183 dias); os 701.357 são **todos** os derivados em disco, incluindo
319.049 do 4T — não prova de preservação individual pela função nova.

**D2.7 — painel não reconstruído.** Uma simulação **em memória** sobre os
arquivados publica `(criados, recusados, sem_antecedente)` da função corrigida —
estimativa do que uma reconstrução faria, **não** total corrigido do painel.

| Alternativa rejeitada | Por que não |
|---|---|
| Contar recusas com a chave antiga | É o defeito |
| Somar `sem_antecedente` à recusa | Funde causas; o aviso mentiria |
| Ignorar `sem_antecedente` | Ausência silenciosa |
| Parear por `cd_conta` sozinho para curar a deriva | RN09 e consumidores; contrato próprio |
| Contar linhas em vez de grupos | Conta como perda o grupo em que outro candidato derivou |

**Aceitação:** caso B da conferência → `(0, 1, 0)` sem a descrição extra e
`(0, 1, 1)` com ela; os quatro casos D1 continuam; avisos do carregador
presentes e ausentes conforme D2.4.

---

## Documentação — correções datadas, nunca reescrita

| Documento | O que recebe bloco de ressalva |
|---|---|
| Dossiê de 14/09 | §3.1 "sai com código 2" (falso até C1); §3.2 507→513 e o que são os 701.357; §6.1 a defesa "não cruzou o limiar" não prova ausência de viés; §9.3 o hash **mudou** (`476a11da…` → `c1a60445…`, registrado em 27/08), resíduo de 71 linhas sem causa atribuída |
| Inventário de 12/09 | 10.261 → número novo; 127 → 111; "`DT_INI_EXERC` destravou DRE/DFC" não demonstrado (as 67 eram zero); "prova" é premissa; 19.859 e 17.803 calculados pela regra antiga |
| Derivação de 12/09 (relatório e contrato) | 507→513; 701.357; aviso sem teste no carregador; `sem_antecedente` |
| AGENTS.md, becos §A.5, MEMORY.md | números vigentes com data, sem apagar histórico |

---

## Condições de falsificação — todas precisam dar negativo

| # | Condição |
|---|---|
| 1 | Hash de `cvm.duckdb` ou `cvm_treino.duckdb` muda |
| 2 | `auditoria.json` regenerado pela CLI não é byte-idêntico, ou a CLI não sai com 2 |
| 3 | Algum limiar registrado muda (T1, T2, mínimos, banda, tolerância de G0, limiares do esqueleto) |
| 4 | Alguma asserção é enfraquecida além das adaptações declaradas acima |
| 5 | O veredito real do Rank 3-B muda |
| 6 | A varredura nova muda linhas lidas (26.267.152) ou casos conflitantes (34.952) |
| 7 | A varredura nova diverge da readjudicação dos casos persistidos, ou excede as previsões |
| 8 | Alguma `classe_confirmada` preenchida antes da regeneração (então a regeneração é abortada) |
| 9 | Algum teste pulado, ou suíte abaixo de 2.093 + contraprovas novas |
| 10 | Algum arquivo da outra frente alterado (`app_streamlit.py`, `src/geracao.py`, `tests/test_guarda_rn02_auditoria.py`, `artefatos/resultados_avaliacao/`) |

## O que esta onda não faz

Correção de célula, reconstrução de painel, cura da deriva de descrição (N2),
piso de suporte do T2, períodos curtos, vintages numéricos, terceira onda
bancária, novo protocolo do Rank 3-B.
