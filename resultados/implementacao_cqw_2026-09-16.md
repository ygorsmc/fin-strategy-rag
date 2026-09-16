# Implementação — CQW-01, CQW-02, CQW-03 e G0.4

**Data:** 2026-09-16.
**Origem:** [conferência independente QW1–QW8](conferencia_independente_qw1_qw8_2026-09-15.md) (§2)
e [levantamento de desbloqueio de treino](pendencias_desbloqueio_treino_dfc_2026-09-15.md) (§3, D1).
**Contrato, registrado antes do código:**
[contratos_correcao_cqw_2026-09-16](contratos_correcao_cqw_2026-09-16.md).
**Snapshot de partida:** `artefatos/snapshots/2026-09-16-pre-cqw/`, 17 registros
conferidos.

**Veredito do Rank 3-B inalterado: `REPROVADO EM G0`.** Nenhum painel
reconstruído, nenhuma célula corrigida, nenhum modelo treinado, holdout não
tocado, `classe_confirmada` não promovida.

Suíte: **2.230 passed, zero falha, zero skip** (era 2.202). **+28 contraprovas**,
todas exercitando decisão.

---

## 1. Placar

| Achado | Antes | Depois |
|---|---|---|
| **CQW-01** domínio do estado | `None`, `"estado_desconhecido"`, `ADJUDICA + " "` e `123` devolviam `set()` **sem exceção** — estado inválido significava "sem defeito" | Levanta `InventarioIncompativel` contra o vocabulário de E1.2. Exclusão real **inalterada: 111 documentos / 35 companhias** |
| **CQW-02** linhagem do ativo | 2 dos 4 campos de H1.4 (`trimestre`, `dt_receb`) nas 10.605 observações | Os 4 campos. `dt_ini` sai `None` **e assim fica** |
| **CQW-03** errata | "Estado das **154.160** declarações" | **156.100**, conferido em duas contas independentes. Ressalva datada, sem reescrever o relatório |
| **G0.4** (do levantamento) | **Não existia no código** — nem contador, nem campo no artefato | Medida fora do filtro dos carregadores e **participando da aprovação** |
| **G0.0** (do levantamento) | `gate_g0([], [], [])` → `aprovado = True` | Universo vazio reprova com motivo |

---

## 2. G0.4 — o achado que cresceu quando medido

O levantamento relatou que `gate_g0([], [], [])` aprovava. Ao verificar, o
problema era maior: **`G0.4` está congelada no §4 do pré-registro desde 11/09 —
*`valor_reais` nunca nulo nas contas usadas, 0 nulos* — e o código nunca a
implementou.** O artefato publicado trazia `g0_1_*`, `g0_2_*`, `g0_3_*` e nada
de `g0_4`.

E não bastaria acrescentar um contador dentro de `gate_g0`: os três carregadores
filtram `valor_reais IS NOT NULL` (linhas 163, 191 e 223). Um contador
alimentado por eles seria **incapaz de ver um nulo por construção** — guarda
vazia, não guarda frouxa. É a mesma família do achado F10 (§4.4 regra 7):
exigência que existe como texto e não participa da condição de aprovação.

`carregar_nulos` mede no mesmo universo elegível, **sem** o filtro:

| Conta | Linhas | Nulos |
|---|---:|---:|
| FCO `6.01`, `DFC%`, `tipo_periodo = 'trimestral'` | 22.034 | **0** |
| Ativo `1`, `BPA` | 22.471 | **0** |

**Isto não desbloqueia nada.** G0 segue reprovando pelos mesmos 132 saltos de
escala, fração 0,005874 contra limiar 0,005. O que muda é a guarda deixar de
aprovar por ausência de medição.

**G0.0 tem granularidade deliberada.** Reprovar quando *qualquer* fonte chega
vazia quebraria `test_salto_de_escala_reprova_acima_da_tolerancia`, que passa
`fco = []` e `duracoes = []` **de propósito** para isolar G0.3. Esse teste é
legítimo e não foi enfraquecido (§4.4). A ausência que o achado denuncia é a do
universo inteiro.

---

## 3. O que mudou no artefato publicado

Comparação sobre os **bytes publicados**, não sobre o objeto em memória:

| | Resultado |
|---|---|
| `veredito`, `primeiro_reprovado`, `modelo_carregado`, `pre_registro_sha256`, `quarentena`, `candidato`, `pre_registro` | **Idênticos** |
| Etapas na cadeia | `['G0']`, como antes |
| Campos **removidos** de G0 | **nenhum** |
| Campos **acrescentados** | `g0_0_fontes_vazias`, `g0_4_nulos_nas_contas_usadas`, `g0_4_por_conta`, `g0_4_contas_sem_linha_alguma` |
| Campos **alterados** | só `limiar` — cláusula G4.7, o artefato passa a dizer a regra que o código aplica |
| `g0_1_inventario`, `g0_2_inventario`, `g0_3_inventario`, `g0_3_fracao`, `g0_3_saltos_de_escala`, `g0_2_duracoes_distintas`, `diagnostico_de_escala` | **Idênticos** |

**Quebra de hash declarada:** `a2ef88be…` → `8f7316ad…`. É implementação de
cláusula congelada do pré-registro, não alteração de contrato.

A CLI foi executada de verdade, saiu com **código 2** e compôs a tela **antes**
de gravar — a disciplina do QW7 continua valendo.

---

## 4. Achado próprio da implementação: `NaT` não é `None`

Ao exercitar H2.3 contra o painel real, a contraprova **passou na fixture e
falhou no dado**. A causa não é o painel: data ausente chega do `.df()` como
`NaT` do pandas, e `NaT is None` é **falso**. Pior — toda comparação com `NaT`
devolve falso, então o sentinel atravessaria qualquer verificação futura de
H2.3 sem acusar nada.

`_procedencia` passou a normalizar `NaT`/`NaN` para `None` (`_ou_nulo`). Isso
normaliza um sentinel; **não preenche nem inventa data**. Medido depois: `dt_ini`
é `None` nas 10.605 observações, `dt_fim` e `dt_receb` presentes em todas.

O modo de falha vale como regra: *fixture que concorda com o autor não prova
nada sobre o dado real*. Só a execução contra o painel separou os dois.

---

## 5. Pontos de julgamento

| Decisão | Por quê | Como refutar |
|---|---|---|
| G0.0 reprova o universo **inteiro** vazio, não fonte a fonte | Preserva um isolamento legítimo de G0.3 que o §4.4 proíbe enfraquecer | Mostrar um caso real em que uma só fonte vazia deveria reprovar |
| `nulos` é argumento **exigido** de `gate_g0`, não opcional | Esquecer de passar vira `TypeError`, não aprovação silenciosa | Mostrar chamador legítimo que não pode medir G0.4 |
| `gate_g0` continua **pura** (recebe listas, nunca a conexão) | É o que sustenta as contraprovas de G0.1–G0.4 | Mostrar verificação de G0 que exige a conexão |
| **Nenhuma** verificação nova em G1 | O §5 do pré-registro não congelou `dt_fim ≤ D` para saldo; inventá-la seria mudar o gate depois de ver o resultado | Apontar cláusula do pré-registro que a exija |
| `dt_ini` do ativo fica `None` | Saldo de balanço é posição numa data; 23.395/23.395 linhas o trazem nulo na origem | Mostrar que o BPA declara início de período |
| Estado inválido **não** é normalizado (`strip`/`lower`) | Espaço sobrando é inventário corrompido, não erro de digitação | Mostrar fonte legítima que emita o estado com espaço |
| Uma declaração inválida derruba o caso inteiro | Ignorar a inválida e seguir com as boas é o defeito CQW-01 em escala menor | Mostrar inventário em que isso perca dado bom |

---

## 6. Auditoria das mudanças de teste

O §4.4 proíbe enfraquecer asserção para fazer código passar. Diff contra o
snapshot:

| Arquivo | `assert` antes → depois | Asserções removidas | Testes removidos |
|---|---|---|---|
| `tests/test_rank03b_consumo_operacional.py` | 133 → **159** (+26) | **1**, declarada | **0** |
| `tests/test_esqueleto_plano_padrao.py` | 25 → **29** (+4) | **0** | **0** |

A única linha removida é
`assert auditor.gate_g0(fco, ativo, dur)["aprovado"] is True`, que virou
`gate_g0(fco, ativo, dur, _nulos())` — **mesma asserção, com o argumento que
G4.2 passou a exigir**. As outras quatro trocas de assinatura são multilinha e
não aparecem no diff de linha única; estão todas na tabela de mudanças
declaradas do contrato, junto com os dois auxiliares (`_ativo`, e os dublês
`_executar_com` e `_veredito`).

---

## 7. Condições de falsificação

As treze do contrato, medidas:

| # | Condição | Estado |
|---|---|---|
| 1 | `documentos_defeituosos()` ≠ 111 / 35 | **Negativa** — 111 / 35 |
| 2 | Algum dos nove estados válidos passar a levantar | **Negativa** — parametrizado nos nove |
| 3 | `gate_g1` com alguma contagem ≠ 0 no painel | **Negativa** — sete em zero |
| 4 | Observações ≠ 10.605 / 494 companhias | **Negativa** |
| 5 | `dt_ini` do ativo ≠ `None` em alguma observação | **Negativa** (exigiu `_ou_nulo`; ver §4) |
| 6 | `veredito` ou `primeiro_reprovado` mudarem | **Negativa** |
| 7 | `g0_3_fracao`, saltos ou inventários de G0.1–G0.3 mudarem | **Negativa** — idênticos |
| 8 | G0.4 acusar nulo onde a medição direta acusa zero | **Negativa** — 0 e 0 nos dois |
| 9 | `gate_g0([], [], [], limpo)` continuar aprovando | **Negativa** — reprova com motivo |
| 10 | CLI quebrar depois de gravar | **Negativa** — compõe antes, sai com 2 |
| 11 | Suíte < 2.202 ou com skip | **Negativa** — 2.230, zero skip |
| 12 | Hash de painel, CSV, inventário, resumo ou pré-registro mudar | **Negativa** — todos iguais |
| 13 | Os seis arquivos da outra frente mudarem | **Negativa** — todos iguais |

---

## 8. Meus próprios erros nesta onda

1. **Errei o caminho num `Edit`** (`Antigousity_Projects`) e a metade emparelhada
   da mudança de `gate_g0` entrou sozinha: o arquivo ficou com `return {` sem o
   bloco que o precede. Quem pegou foi o *smoke check*, não minha leitura.
2. **Escrevi a contraprova de H2.3 contra uma fixture que me dava razão.** A
   fixture dizia `dt_ini: None`; o painel entrega `NaT`. O teste passava e a
   realidade falhava (§4).
3. **Esqueci dois dublês ao acrescentar um carregador a `executar()`** — e em
   duas rodadas: corrigi `_executar_com` e só então descobri `_veredito`. Seis
   casos rodaram o carregador real contra uma conexão falsa.
4. **O contrato afirmou que `dt_ini` nulo seria "preservado"**, como se
   preservação fosse de graça; exigiu código. Registrado como ressalva datada
   no próprio contrato, sem reescrevê-lo.

---

## 9. Procedência

| Arquivo | Antes | Depois |
|---|---|---|
| `scripts/esqueleto_plano_padrao.py` | `cd6f4916…` | `f75da65c…` |
| `scripts/auditar_rank03b_consumo_operacional.py` | `02af50bd…` | `3e771b33…` |
| `tests/test_esqueleto_plano_padrao.py` | `4753ddf2…` | `63aa8a51…` |
| `tests/test_rank03b_consumo_operacional.py` | `3586218a…` | `540bbce3…` |
| `artefatos/rank03b/auditoria.json` | `a2ef88be…` | `8f7316ad…` (quebra declarada) |
| `resultados/implementacao_qw1_qw8_2026-09-15.md` | `9e523de9…` | `631fdf6c…` (ressalva) |
| `resultados/dossie_revisao_quatro_ondas_2026-09-14.md` | `a127520e…` | `11539f01…` (ressalva) |
| `AGENTS.md` | `545e7d5f…` | `7595bf61…` |
| `resultados/contratos_correcao_cqw_2026-09-16.md` | — | `6b58a2ed…` |
| **`scripts/inventariar_escala_cvm.py`** | `cde20df0…` | **inalterado** |
| **`corpus/cvm/plano_padrao_contas.csv`** | `fa271cd3…` | **inalterado** |
| **`artefatos/escala_cvm/inventario.jsonl` · `resumo.json`** | `f18c60dd…` · `17797779…` | **inalterados** |
| **`artefatos/cvm.duckdb` · `cvm_treino.duckdb`** | `43e31d9f…` · `c1a60445…` | **inalterados** |
| **Pré-registro Rank 3-B** | `fbae30cc…` | **inalterado** |

---

## 10. O que continua aberto

1. **Conferência independente desta onda.** Nenhuma parte dela foi revisada por
   terceiro.
2. **N3 — a derivação é não determinística** em 141 grupos de 7 companhias (10
   grupos em 6 companhias no recorte de FCO não financeiro). **Reconstruir o
   painel hoje não é reproduzível.** Precede qualquer reconstrução.
3. **N2 — 139.435 grupos sem antecedente** (131 em 94 companhias no recorte do
   candidato). Contado, não curado.
4. **O seletor de exemplar do esqueleto.** Só **110 de 300** `ds_conta_exemplo`
   são a descrição modal da chave; 190 divergem e 9 são o marcador `0`/`-`. É
   defeito do `min(ds_conta)`, com **contrato próprio ainda não escrito** —
   deliberadamente fora desta onda, porque mudaria o CSV outra vez.
5. **Períodos curtos** (16 linhas) e os 15 grupos mistos: sem conserto.
6. **A escala não foi adjudicada.** G0 reprova pelos mesmos 132 saltos. Correção,
   se vier, é **por declaração**, restrita a conta monetária confirmada, sem
   junção universal por código (RN09).
7. **`classe_confirmada` continua vazia nas 300 linhas.** A anotação de 15/09 é
   por agente e **não é validação humana**.
8. **A suíte não fecha por soma.** 2.230 medidos; três frentes não commitadas
   convivem na árvore e ~18 casos não são atribuíveis. Separar antes de commitar.
9. **Nenhum treino autorizado.** Passar nos testes do instrumento não é
   permissão de medir o alvo, que por sua vez não é permissão de treinar.
