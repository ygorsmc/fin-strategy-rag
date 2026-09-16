# Validação do Rank 3-B — início de consumo operacional persistente

> **⚠️ RESSALVA POSTERIOR (2026-09-12) — leia antes de citar qualquer número
> deste relatório.** Uma [revisão independente](revisao_rank03b_consumo_operacional_2026-09-12.md)
> confirmou a parada em G0, mas **não aprovou** a alegação de que o auditor
> implementava integralmente o pré-registro, e corrigiu três descrições daqui:
>
> | Afirmação abaixo | Estado em 2026-09-12 |
> |---|---|
> | "136 saltos entre trimestres **adjacentes**" | **132.** Quatro pares distavam 3, 3, 5 e 14 trimestres. G0.3 reprova de todo jeito |
> | "o `max` pode eleger o **semestre**" nos 15 grupos mistos | **Falso.** Os grupos têm períodos **curtos** (12, 31, 41 dias), nenhum de 183 — e em **12 dos 15** o `max` elege mesmo o curto. Consertar a derivação semestral **não** toca nesses grupos |
> | "**123 linhas erradas**, publicadas e preservadas" | São **transições suspeitas**, não linhas nem células adjudicadas: entrada e saída de uma célula produzem dois sinais. E há uma **terceira** classe (bruto anterior zero), razão de 123+13 não somar 137 |
>
> A revisão achou ainda **cinco defeitos de implementação** (R1–R5), entre eles
> um que devolvia `PRONTO PARA CHALLENGER` com os baselines falhos. Todos
> corrigidos em [implementacao_r1_r5](implementacao_r1_r5_rank03b_2026-09-12.md)
> — suíte 2.030. **O veredito não mudou:** G0 reprovado, alvo não testado.

**Data:** 2026-09-11. **Veredito: REPROVADO EM G0 — rodada invalidada.**
**Nenhum modelo foi carregado. T1, T2 e os baselines NÃO foram medidos.**

| | |
|---|---|
| Pré-registro | [`pre_registro_rank03b_consumo_operacional_2026-09-11.md`](pre_registro_rank03b_consumo_operacional_2026-09-11.md) |
| SHA-256 congelado antes do auditor existir | `fbae30cce2bde9b3ece5ccf254e300ce99ba11946568720441193b0a3ac644cc` |
| Auditor | `scripts/auditar_rank03b_consumo_operacional.py` |
| Contraprovas | `tests/test_rank03b_consumo_operacional.py` — **25 casos** |
| Artefato | `artefatos/rank03b/auditoria.json` |
| Suíte | **2.010 casos, zero skip** (era 1.985) |
| Custo | **zero** — painel em disco, sem rede, sem API |

---

## 1. Em uma frase

**O alvo não chegou a ser testado: o painel reprovou antes.** G0 encontrou
**123 trocas de escala declarada com valor bruto contínuo em 43 companhias** —
o que significa que `valor_reais` está errado por 1.000× nessas linhas — e **25
linhas de FCO "trimestral" cobrindo período que não é um trimestre**, das quais
as de 183 dias são semestres produzidos pela própria derivação.

**A previsão que registrei no pré-registro continua sem resposta.** Eu havia
escrito que esperava reprovação em T1 pelo componente `fco_ttm_sobre_sd8`.
**T1 nunca rodou.** Não há vindicação nem refutação dessa previsão nesta rodada,
e seria desonesto apresentar o resultado como se houvesse.

---

## 2. G0.3 — a escala declarada está errada, e o painel a aplica fielmente

**136 saltos de ativo total por fator ≥ 100 entre trimestres adjacentes,
0,61% das observações** contra tolerância de 0,50%.

O diagnóstico separa defeito de redenominação real, usando `vl_conta` como
discriminante: se o valor bruto segue contínuo e só a `escala` declarada muda, a
companhia não mudou de unidade — o campo está errado.

| | |
|---|---:|
| Trocas de escala em trimestres adjacentes | **137** |
| Com valor bruto **contínuo** → defeito | **123** |
| Com valor bruto saltando junto → redenominação aparentemente real | 13 |
| Companhias com defeito | **43** |

**O caso testemunha, companhia `003549`:**

| trimestre | conjunto | escala | `vl_conta` | `valor_reais` |
|---|---|---|---:|---:|
| 1T2020 | itr | MIL | 19.535 | 19.535.000 |
| 2T2020 | itr | MIL | 19.543 | 19.543.000 |
| **3T2020** | itr | **UNIDADE** | 19.358 | **19.358** |
| 4T2020 | dfp | MIL | 19.424 | 19.424.000 |
| **1T2021** | itr | **UNIDADE** | 18.823 | **18.823** |
| 4T2021 | dfp | MIL | 18.794 | 18.794.000 |

O valor bruto é contínuo em ~19.000 do começo ao fim. O ITR passa a declarar
`UNIDADE` a partir do 3T2020 e a DFP continua declarando `MIL` — daí a
alternância. Um ativo de R$ 19 mil não é plausível para companhia aberta: **a
escala declarada no ITR está errada na fonte**, e `valor_reais` erra por 1.000×
ao aplicá-la.

### Este é achado de painel, não de candidato

**Isto não é um problema do Rank 3-B.** É um defeito de `valor_reais` que afeta
qualquer análise que o use nessas 43 companhias — inclusive, em princípio, a
etapa 10. É a mesma classe de defeito que o §3.11 mediu no CAND-04 (*"trocas
`MIL`↔`UNIDADE`"*, 23 linhas explicando 61,64% do erro), agora encontrada de
forma independente, em outro candidato e em outra conta.

**As 123 linhas NÃO foram removidas** (§4.4 regra 9 e §4 do pré-registro). A
quarentena está publicada no artefato e a rodada está invalidada.

## 3. G0.2 — período que não é trimestre

**25 linhas de FCO marcadas `tipo_periodo='trimestral'` cobrem duração fora de
80–100 dias.** Durações distintas encontradas: **12, 31, 38, 41 e 183 dias**.

As de **183 dias** têm `origem='derivado'`: são semestres produzidos pela
derivação `isolado(q) = acumulado(q) − acumulado(q−1)` quando falta o acumulado
imediatamente anterior e ela pareia com um mais antigo. Confirma, com endereço,
o que a auditoria de 2026-09-08 havia notado como "fluxos semestrais rotulados
trimestrais".

**Agravante contado à parte: 15 grupos (companhia, trimestre) contêm ao mesmo
tempo uma linha de duração válida e uma anômala.** Como a carga resolve o grupo
por `max(valor_reais)`, ela pode **eleger o semestre** em vez do trimestre — e o
resultado não sinaliza nada. É pior que a linha anômala solta.

---

## 4. Um defeito do próprio auditor, achado por rodá-lo

A primeira execução acusou **30** linhas fora de duração, incluindo casos de
121, 274 e 365 dias. **Era defeito meu.** Eu media a duração sobre o grupo
`(companhia, trimestre)`, entre `min(dt_ini_exerc)` e `max(dt_fim_exerc)`: com
duas linhas de períodos distintos no mesmo grupo, o vão infla e acusa defeito
onde há só agrupamento.

Corrigido para medir **por linha, antes de qualquer `GROUP BY`** — que é o que o
§4 do pré-registro pede literalmente. Depois da correção: **25** linhas, e as
durações passam a ser todas explicáveis (12, 31, 38, 41, 183).

**O veredito não mudou com a correção** — G0.3 reprovava de qualquer forma —,
mas registrar isto importa por duas razões: o número publicado antes estava
errado, e um auditor que infla defeito é tão ruim quanto um que esconde. Há
contraprova travando o comportamento
(`test_duracao_e_medida_por_linha_nao_pelo_grupo`).

---

## 5. O que foi construído, e o que ele garante

O auditor implementa o contrato e já nasce com as guardas que este projeto
aprendeu a exigir:

| Guarda | Origem |
|---|---|
| Empates de quintil **agrupados por valor**; variável constante dá 1 grupo e amplitude 0,0 | achado C1 do B-DFC-01J |
| Amostra abaixo do mínimo **levanta** `AmostraInsuficiente`, nunca aprova | §4.4 regra 4 (o `NaN >= 0,15 → False` do Rank 3) |
| Escore constante **levanta** `EscoreDegenerado` em T2 | T2 aprovava por ausência de poder no B-DFC-01J |
| `DefeitoDeIntegridade` **não herda** de `AmostraInsuficiente` | §4.4 regra 5 (`ErroDeUnidade`) |
| `dt_receb` de `documentos`, nunca `dt_refer` | §3.13: atraso mediano 44/83 dias |
| `q1` é o primeiro trimestre **iniciado** após D, e os quatro conferidos por ordinal | achado C3 do B-DFC-01J |
| Bootstrap reamostra **companhias**, nunca observações | §4.4 regra 8 |
| `max(valor_reais)` entre `DFC_MD`/`DFC_MI`, nunca `sum` | §3.13: sobreposição não vazia |
| Ativo vem de `fatos_contabeis`, não de `indicadores` | `indicadores` não tem `dt_refer`/`versao` — não é auditável point-in-time |
| Zona cinzenta [0,12; 0,15) exige bootstrap; P(>0,15) > 10% ⇒ INDECIDÍVEL | §3.16 / Etapa 19 |

**As 25 contraprovas exercitam a decisão**, não o JSON: G0 aprovando em dado
limpo e reprovando em cada um dos três defeitos; a conjunção `S1<0 ∧ S2<0` com
**os dois lados** (um semestre negativo não marca; quatro trimestres negativos
marcam); e o PIT recusando antecedente publicado depois de D.

### A população, quando G0 permitir medi-la

Registrado para a retomada, **sem nenhum T1/T2 medido**: 22.013 observações de
FCO e 22.428 de ativo entram na carga, sobre companhias não financeiras.

**"Não financeira" não pôde ser resolvido por setor:** `companhias.setor` está
preenchido em **5 de 741** e o `cad_cia_aberta.csv` que o §3.7 nomeava como
solução **nunca foi baixado**. O critério adotado e declarado no pré-registro é
estrutural — exclui `plano_contas LIKE 'll3_09_%'` (plano de instituição
financeira) **ou** `is_banco`. Sobrevive à retratação do `is_banco` porque aqui
ele **exclui** em vez de selecionar, e super-incluir numa exclusão é
conservador. **Não há controle setorial nesta rodada e não haverá.**

---

## 6. Condições de falsificação — todas checadas

| # | Condição do §11 do pré-registro | |
|---|---|---|
| 1 | Lista de componentes de T1 diferente da registrada | ❌ não ocorreu (travada por teste; T1 não rodou) |
| 2 | Algum limiar diferente dos fixados | ❌ não ocorreu — `TestLimiaresCongelados` |
| 3 | População filtrada por critério não declarado | ❌ não ocorreu |
| 4 | Observação reprovada em G0.3 removida em silêncio | ❌ não ocorreu — 123 preservadas e publicadas |
| 5 | Bootstrap reamostrando observações | ❌ não ocorreu (não executado) |
| 6 | Veredito "aprovado" com gate decisivo reprovado | ❌ não ocorreu |
| 7 | Hash do painel mudou durante a execução | ❌ não ocorreu — `c1a604453a9a2fa7…` antes e depois |

---

## 7. O que retomar exige

A retomada **não** é "rodar de novo". Em ordem:

1. **Adjudicar a escala contra a fonte**, nas 43 companhias. O §3.3 já tem o
   padrão: `corpus/cvm/correcoes_contabeis.csv`, com valor original, valor
   corrigido, documento, página, SHA-256 do PDF e evidência — e a guarda
   anti-porta-dos-fundos que **falha** se a CVM republicar. Nunca corrigir em
   silêncio nem excluir a célula.
2. **Decidir o que fazer com os 15 grupos contaminados** por período semestral.
   `max(valor_reais)` sobre eles é aposta, não leitura.
3. **Consertar a derivação** que produz semestre rotulado trimestre, ou marcá-lo
   com a duração real para que o consumidor possa recusá-lo.
4. **Só então** um pré-registro novo. Este está **consumido**: retomar o mesmo
   alvo depois de mexer na população é ajustar a população tendo visto o
   resultado, e o §10 do próprio pré-registro proíbe.

**A previsão sobre `fco_ttm_sobre_sd8` fica pendente e deve ser transportada
literalmente para o pré-registro seguinte**, para que continue sendo previsão e
não virar explicação pós-hoc.

## 8. O que esta rodada NÃO fez

Nenhum modelo carregado · nenhuma escrita no painel (aberto somente leitura;
`cvm.duckdb` não tocado) · nenhum acesso a `corpus/holdout_2T2026` · nenhuma
chamada de rede ou API paga · nenhuma observação removida para salvar o teste ·
nenhum limiar ou componente alterado depois de medir.

## 9. Reprodução

```bash
.venv/bin/python -m scripts.auditar_rank03b_consumo_operacional   # sai com 2
CREWAI_STORAGE_DIR="$(mktemp -d)" .venv/bin/python -m pytest -q \
  tests/test_rank03b_consumo_operacional.py
sha256sum resultados/pre_registro_rank03b_consumo_operacional_2026-09-11.md
# fbae30cc… — tem de bater com artefatos/rank03b/PRE_REGISTRO_CONGELADO.txt
```

O auditor sai com **código 2** quando G0 reprova, e grava a quarentena em
`artefatos/rank03b/auditoria.json` — publicar a reprovação é exigência do §4 do
pré-registro, e a primeira versão do script só a imprimia na tela.

---

## 10. Leitura correta deste resultado

**O que este resultado NÃO diz:**

- **Não diz que o Rank 3-B é um alvo ruim.** Não foi medido.
- **Não diz que ML sobre DFC é inviável.** O que reprovou foi a integridade de
  escala do painel, que é conserto de dado com procedência — o §3.3 já fez isso
  duas vezes.
- **Não confirma minha previsão sobre T1.** Ela segue sem teste.

**O que ele diz:** o painel de treino tem um defeito de escala **de 1.000×** em
43 companhias e períodos mal rotulados em 25 linhas, e nada disso era conhecido
com endereço antes desta rodada. O candidato serviu de instrumento para achar
isso — o que é resultado, mesmo não sendo o resultado procurado.
