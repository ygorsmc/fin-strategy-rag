# Implementação das correções QW1–QW8 da conferência de 15/09

**Data:** 2026-09-15. **Origem:** [conferência independente das quatro
ondas](conferencia_quatro_ondas_2026-09-15.md) (`4c768b5970b2…`).
**Contrato, registrado antes do código:**
[contratos_correcao_qw1_qw8](contratos_correcao_qw1_qw8_2026-09-15.md)
(`774935510cfa…`).
**Snapshot de partida:** `artefatos/snapshots/2026-09-15-pre-qw1-qw8/` — os 13
hashes do §6 da conferência conferem.

**Veredito do Rank 3-B inalterado: `REPROVADO EM G0`. Nenhum modelo carregado,
nenhum painel reconstruído, nenhuma célula corrigida.** Esta onda corrige
instrumento, evidência e consumidores.

Suíte: **2.132 passed, zero falha, zero skip** (era 2.093). **+39
contraprovas**, todas exercitando decisão.

---

## 1. Placar

| Achado | Antes | Depois |
|---|---|---|
| **QW1** zero como prova | 6.736 dos 10.261 casos adjudicados só por coincidência **zero** | Zero nunca prova, nem como referência. **3.401 casos**, nenhum adjudicado com zero |
| **QW2** extrapolação | 292 declarações condenadas com outro valor; 124 casos sem DFP do valor | Decisão **por declaração**, vocabulário fechado de 9 estados. **6.456 declarações** adjudicadas, **0** sem DFP do mesmo valor; 20 saem *equivalentes em reais* |
| **QW3** G1 por existência | `aprovado = bool(amostra)`; o caso `3T2019` datado jan–mar aprovava | `gate_g1` reconfere pela linhagem, com código próprio; é decisivo e para a cadeia |
| **N1** horizonte civil sobre rótulo fiscal | **322 observações reais em 15 companhias** com trimestre de rótulo já iniciado em D | q1 pelas **datas** da linha. No painel real: **G1 com todas as contagens zero** |
| **QW4** completude falsa | B3 só com negativos: `completo=True`, AUC/IC `None` → `PRONTO PARA CHALLENGER` | Completude exige métricas e **IC das três métricas**. O mesmo caso → **`INDECIDIVEL`** |
| **QW5** piso de observações | 499 observações interrompiam T1 e apagavam a amplitude 1,0 de outro componente | Componente `INSUFICIENTE`; o outro é medido → **reprovação numérica** |
| **QW6** recusa silenciosa | Contagem com outra identidade que a inserção: `(0, 0)` com recusa real | Uma relação de candidatos. Simulado no painel: **4.486 → 7.733**; criados **382.454** nas duas versões |
| **QW7** CLI | `KeyError` depois de gravar | **Sai com 2**; `auditoria.json` regravado **byte-idêntico** |
| **QW8** dependência | Inventário ausente → `set()` → medida sobre tudo | `InventarioAusente` / `InventarioIncompativel`; vazio válido é outro estado |

---

## 2. O que mudou nos números publicados

### Inventário de escala — v1 × v2

Mesma varredura: **26.267.152 linhas, 34.952 casos**, ZIPs com os mesmos
SHA-256 de 12/09. A varredura nova coincide **caso a caso, na mesma ordem**, com
a readjudicação dos casos persistidos — e com a previsão registrada no contrato.

| | v1 (12/09) | v2 (15/09) |
|---|---:|---:|
| Casos adjudicáveis | 10.261 | **3.401** |
| Declarações adjudicadas | — | **6.456**, todas `PENÚLTIMO` |
| Direção dos casos `MIL` / `UNIDADE` | 7.648 / 2.613 | **2.430 / 971** |
| Companhias adjudicáveis | 41 | **35** |
| Documentos com rótulo adjudicado | 127 | **111** |
| … linhas arquivadas desses documentos no painel | 33.655 | **29.650** |
| Adjudicáveis fora do balanço | 67 | **0** |
| Casos com evidência informativa não nula | — | 13.437 |

**Os 16 documentos que saíram** são os 14 só com zero da conferência e 2
condenados por extrapolação (`021520/2016-09-30`, `027006/2022-09-30`).
**Nenhum entrou.**

Estado das 154.160 declarações: `sem_referencia_auditada` 84.248 ·
`dfp_ambigua` 24.447 · `referencia_auditada` 18.638 · `zero_nao_informativo`
13.174 · `mesma_escala_da_referencia` 8.261 · **adjudicada 6.456** ·
`sem_prova` 856 · `equivalente_em_reais_a_dfp` 20 · `evidencia_contraditoria` 0.

**A retratação de 12/09 sobrevive, com o escopo que a conferência deu:**
nenhuma declaração adjudicada é `ÚLTIMO`, então aplicar os rótulos atuais não
altera linha arquivada do painel.

### Esqueleto do plano padrão

Regenerado depois de conferir **zero** `classe_confirmada` preenchidas (o
original está no snapshot). **Mesmas 300 contas, na mesma ordem, e nenhuma
proposta de classe mudou** (291/7/2). Mudaram contagens (290 linhas), cobertura
acumulada (296), mediana bruta (144) e razão sobre o ativo (74), porque 16
documentos deixaram de ser excluídos.

| Universo | Linhas cobertas / total | Cobertura |
|---|---:|---:|
| **Do gerador** — arquivados fora dos 111 documentos | 5.981.271 / 6.438.964 | **92,892%** |
| Todos os arquivados | 6.008.928 / 6.468.614 | 92,894% |
| Painel inteiro, com derivados | 6.680.366 / 7.177.705 | 93,071% |

---

## 3. N1 — o achado mais sério desta onda

A carga numera trimestres pelo **exercício social**. O R2 de 12/09 calculou
`q(D)` pelo **calendário civil** e casou o rótulo pelo **texto**. Em exercício
não civil os dois apontam períodos diferentes — e o rótulo aceito podia já ter
começado, ou terminado, antes de D.

| Medido em memória sobre o painel real | |
|---|---:|
| Companhias elegíveis com trimestre de exercício não civil | **23 de 691** |
| Observações aceitas com rótulo iniciado até D (construção de 12/09) | **322**, em 15 companhias |
| … com rótulo cujas datas não encadeiam | 8, em 3 companhias |
| Pares de rótulos consecutivos com datas que não se sucedem | 15 |

Exemplo: `009539`, exercício em julho, `D = 2013-09-09` recebia como q1 o
"4T2013" — **abr–jun/2013, já encerrado**. É o caso sintético QW3 da
conferência, existindo no dado.

**A correção reancorou em vez de censurar.** q1 é o trimestre de menor início
posterior a D, até D + 3 meses; q2..q4 pelo ordinal fiscal com datas
encadeadas. Construção antiga × nova sobre o painel real:

| | |
|---|---:|
| Observações | 10.670 → **10.605** |
| Mesma (companhia, D) com **q1 diferente** | **278**, em 12 companhias |
| Censuradas | 65 — rótulo incompleto +31, identidade do rótulo +6, identidade da janela +33, FCO TTM não positivo −5 |
| Com rótulo `y` diferente | 3 |
| Taxa do evento | 0,0526 → 0,0530 |
| G1 sobre a amostra nova | **todas as contagens zero** |

**O resultado publicado não é afetado** só porque G0 reprova antes de a amostra
ser construída. Qualquer remedição do Rank 3-B teria herdado o defeito.

---

## 4. N2 e N3 — dois defeitos pré-existentes da derivação, medidos e **não** corrigidos

A simulação em memória (painel em disco só lido) rodou a função antiga e a
corrigida sobre os mesmos 2.323.166 arquivados de fluxo.

**N2 — antecedente inexistente: 139.435 grupos.** Há o acumulado, mas nenhum
acumulado anterior do mesmo exercício com a mesma chave — boa parte porque a
descrição normalizada muda entre arquivamentos (no 2T da DFC, 76.923 sem
antecedente de mesmo código **e** descrição, só 22.308 sem antecedente de mesmo
código). Agora **contado e avisado** como estado próprio. Curar muda a
identidade de pareamento: RN09 e todos os consumidores, contrato próprio.

**N3 — a derivação não é determinística.** A **mesma** função, rodada duas
vezes, difere em 49 linhas (antiga) e 73 (corrigida). A causa são **141 grupos
de 7 companhias** (`019836`, `022586`, `022950`, `023507`, `023795`, `026352`,
`080071`) onde a troca de exercício social põe **dois períodos sob o mesmo
rótulo** e o `QUALIFY … ORDER BY cd_conta` empata.

**O que isso permitiu afirmar, e o que não:** os **382.454 grupos derivados são
idênticos** entre as duas versões, e **fora dos 141 grupos as linhas são
idênticas nos dois sentidos**. Dentro deles, comparar antiga × nova não informa
nada. **Reconstruir o painel hoje produziria conteúdo não reproduzível** — isto
é precondição do contrato de reconstrução, não detalhe.

---

## 5. Onde decidi por julgamento

| Decisão | Por que é julgamento | Como refutar |
|---|---|---|
| IC só com ≥ 40 reamostragens válidas | Deriva do nível de 95% (cada cauda com uma reamostragem), mas não estava registrado | Mostrar que o §8 pede outro critério de validade |
| q1 até **D + 3 meses** | Correto para trimestres de três meses. Trimestre de 13 semanas começando além de D + 3 meses seria censurado | Achar exercício de 13 semanas no painel; hoje G1 dá zero e só 65 observações foram censuradas |
| Equivalência em reais com meia unidade da escala mais grossa | Supõe declaração em milhares arredondada ao milhar; só separa estados que **não** adjudicam, salvo contradição | Caso real em que a tolerância bloqueia adjudicação legítima |
| A DFP tem o rótulo certo | **Premissa**, publicada no resumo e em cada motivo | Documento em que a DFP errou a escala e o ITR acertou |
| G1 reprovado para a cadeia | O §5 do pré-registro diz "decisivo"; antes a cadeia seguia | Ler "decisivo" como diagnóstico |
| `escala_da_referencia_auditada` só preenchida quando algo foi adjudicado | Mantém o valor das asserções antigas; a escala da DFP está sempre em `escalas_na_dfp` | Consumidor que precise dela em caso indecidível |
| Regenerar o CSV antes da anotação | Nenhuma confirmação existia; depois custaria trabalho humano | — |

---

## 6. Auditoria das alterações de teste

```console
$ diff <(grep -E "^\s*(assert |def test)" <snapshot>/tests/...) \
       <(grep -E "^\s*(assert |def test)" tests/...) | grep "^<"
tests/test_inventario_escala_cvm.py:
<         assert casos[0]["escala_correta"] == "MIL"
<         assert casos[0]["escala_correta"] is None
<         assert casos[0]["escala_correta"] == "MIL", (
<         assert "escala_correta" in casos[0]
(os outros três arquivos: nenhuma)
```

**Quatro linhas, as quatro declaradas no contrato (E1.6):** o campo mudou de
nome e cada asserção voltou com **o mesmo valor esperado**.

Adaptações que não removem asserção, todas declaradas no contrato:

- o auxiliar `_veredito` de `TestContratosR1aR5` passou a fixar `gate_g1`
  aprovado, como já fixava `gate_g0`;
- `test_R4_baselines_publicam_as_metricas_do_paragrafo_8` troca os nomes
  genéricos `ic95_inferior`/`ic95_superior` pelos três IC explícitos —
  **mais forte**;
- os casos D1 desempacotam três valores e ganharam `assert sem_antecedente == 0`;
- docstrings corrigidas (507 → 513; "1S sem 1T" era 1T e 9M sem o 1S).

**Limiares registrados idênticos ao snapshot** em todos os arquivos. Constantes
novas: `MINIMO_DE_REAMOSTRAGENS_VALIDAS`, `FATOR_DA_ESCALA`,
`VERSAO_DO_ESQUEMA`, `ADJUDICA`.

---

## 7. Condições de falsificação — todas negativas

| # | Condição | Resultado |
|---|---|---|
| 1 | Hash de painel muda | ❌ — `43e31d9f…` e `c1a60445…` |
| 2 | CLI não sai com 2 ou artefato não byte-idêntico | ❌ — sai com 2; `a2ef88be…` |
| 3 | Limiar registrado muda | ❌ — idênticos ao snapshot |
| 4 | Asserção enfraquecida além do declarado | ❌ — só as quatro renomeações |
| 5 | Veredito real do Rank 3-B muda | ❌ — `REPROVADO EM G0` |
| 6 | Varredura muda linhas lidas ou casos | ❌ — 26.267.152 e 34.952 |
| 7 | Varredura diverge da readjudicação ou excede a previsão | ❌ — idêntica caso a caso; 3.401 / 6.456 / 111, dentro de ≤ |
| 8 | `classe_confirmada` preenchida antes de regenerar | ❌ — zero de 300 |
| 9 | Teste pulado ou suíte abaixo de 2.093 + novas | ❌ — 2.132 passed, zero skip |
| 10 | Arquivo da outra frente alterado | ❌ — seis hashes conferem |

---

## 8. Erros meus nesta onda, achados antes de publicar

- Um teste novo montava o ativo **depois** de converter `dt_receb` para
  `Timestamp`, e o auxiliar só aceita texto ISO. Corrigida a **construção** do
  caso; a asserção é a mesma.
- A simulação da derivação falhou duas vezes por mecânica de import (script
  fora do `PYTHONPATH`; módulo com `@dataclass` fora de `sys.modules`). Nenhum
  número foi lido de execução falha.
- Escrevi na docstring do esqueleto um numerador **não medido** (5.981.199); a
  conferência do número antes de publicar deu **5.981.271**.
- O patch da derivação criou um `from typing` duplicado; unificado.

---

## 9. Reprodução

Custo zero; nada grava fora de diretório temporário, exceto as três
regenerações declaradas.

```bash
CREWAI_STORAGE_DIR="$(mktemp -d)" .venv/bin/python -m pytest -q   # 2.132 passed
.venv/bin/python -m scripts.auditar_rank03b_consumo_operacional   # sai com 2
.venv/bin/python -m scripts.inventariar_escala_cvm                 # ~5 min
```

As reproduções do §4 da conferência, adaptadas à API nova, foram executadas em
15/09 e devolvem:

| Bloco | Devolve |
|---|---|
| A — `3T2019` datado jan–mar | nenhuma observação em `D = 2019-05-10`; G1 aprova o resto |
| B — outra descrição no 2T | `(0, 1, 0)` e `(0, 1, 1)` |
| C — inventário v2 | 34.952 · 3.401 · 6.456; adjudicadas com zero **0**, sem DFP do valor **0**, `ÚLTIMO` **0**, fora do balanço **0**; sintéticos: zero `INDECIDIVEL`, `100000` equivalente e `100` adjudicado |
| D — completude e suporte | `INDECIDIVEL` com B3 incompleto; T1 com componente insuficiente e `reprova_numericamente = True` |
| E — CLI e dependência | CLI sai com 2 e grava o mesmo relatório; inventário ausente → `InventarioAusente` |

Os blocos C e E originais da conferência **falham de propósito** contra o
esquema v2 (`escala_correta` não existe; inventário ausente levanta).

---

## 10. Rastreabilidade

```text
antes (snapshot)                          depois
afffe087…  scripts/auditar_rank03b_…py     02af50bdb9b6745db99c0ad4fd46347d852ef778d0e551712d0d875519a68678
fcdf7be5…  tests/test_rank03b_…py          3586218a6dbf754c02f1a6e2a5d2316816c9cad505a7c74b79d981dc0d85077a
5b719f1e…  scripts/inventariar_escala…py   cde20df0a519d49ca0ad914a25a4317727b3df8c69cc2d1f553aaca5befa4140
117e924f…  tests/test_inventario_…py       f3564549fec59428d6ad9eb19ad5a24f05baf21d0b60a807cf1208925b9d9374
4e9a0dc5…  scripts/esqueleto_plano_…py     cd6f4916e7931baec956ffed579bcbf2ae1cda026a6bf3d6e9216fecba407fdd
13bfbf3f…  tests/test_esqueleto_…py        4753ddf2a04b38afc49e9a14a990b58877ca36bf76b151c48b6f930a17587e1a
2659dee7…  src/dados_estruturados.py       b7587f2a3267f9f1828e134970ae1c064a85a3ec082655ce158ce32816de46cf
079ef99c…  tests/test_dados_estruturados.py b2822642d7e384d3ab2b2396272314f6786d2702b110d84ed576a8bbc6847d15
b58dbe01…  corpus/cvm/plano_padrao_contas.csv db597d3a7b8c1b787850acc21269cf05f523f8a7f7f5052f5a580baf39226710
3c6d3cec…  artefatos/escala_cvm/inventario.jsonl f18c60dd8d2bce0750c97e3741c91aeede6194b8d59cf1b79623f24769c64550
d420138c…  artefatos/escala_cvm/resumo.json   177977798e850ae8993b3d81a6f13d637cbe2e9778b06067dbf5443488ebf328
a2ef88be…  artefatos/rank03b/auditoria.json   a2ef88be…  (INALTERADO)
fbae30cc…  pré-registro do Rank 3-B           fbae30cc…  (INALTERADO)
43e31d9f…  cvm.duckdb                         43e31d9f…  (INALTERADO)
c1a60445…  cvm_treino.duckdb                  c1a60445…  (INALTERADO)
```

Sem rede, sem API paga, sem leitura do holdout, sem escrita no painel.

---

## 11. O que continua aberto

1. **Conferência independente desta onda.**
2. **N3 antes de qualquer reconstrução:** 141 grupos com desempate arbitrário.
   Decidir entre recusa contada e desempate declarado é contrato próprio.
3. **N2:** 139.435 grupos sem antecedente, boa parte por deriva de descrição.
4. **Contrato de correção de escala** — se vier, precisa ser **por declaração**,
   restrito a conta monetária confirmada, e sem junção universal por código: a
   chave `(demonstrativo, cd_conta)` do esqueleto não é semântica entre planos
   (RN09).
5. **Anotação do plano padrão** pode seguir sobre o **CSV regenerado**
   (`db597d3a…`) — mas confirmar classe não conserta adjudicação.
6. Cobertura do `mapa_contas` com quatro valores (dossiê §9.2) e o resíduo de
   **71 linhas** entre 6.787.589 e 7.177.705 (conferência §3.5).
7. Períodos curtos, vintages numéricos, piso de suporte do T2, terceira onda
   bancária e novo protocolo do Rank 3-B — tarefas separadas.
8. **Reconstrução de painel não autorizada.**
