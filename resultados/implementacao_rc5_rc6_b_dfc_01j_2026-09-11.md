# Implementação de R-C5, R-C6 e R-SUPORTE — B-DFC-01J

**Data:** 2026-09-11. **Origem:** [conferência independente da implementação de
C1–C6](conferencia_independente_c1_c6_b_dfc_01j_2026-09-11.md).
**Contratos, registrados antes do código:**
[contratos_correcao_rc5_rc6](contratos_correcao_rc5_rc6_b_dfc_01j_2026-09-11.md).

**Nenhum modelo foi treinado. Nenhum dado novo foi produzido.** O veredito do
candidato não mudou: **NÃO AUTORIZA TREINO**, decisivo em G0, população de J
igual a zero.

---

## 1. Placar

| Achado | Antes | Depois |
|---|---|---|
| **R-C6** — quarentena de F3 não governava G3 | Com B3 habilitado, G3 **aprovava** declarando `calculo_de_poder_invalidado_por: "F3"` | Três vetos independentes; F3 vigente reprova **mesmo com B3 presente** |
| **R-C6** — estado de C6 incompleto em G3 | `decidivel`, `clusters_suficientes`, `ressalva` ausentes | Os três publicados, mesmo vocabulário de `_poder` |
| **R-C5** — independência não condicionava G0 | Zero independentes → `aprovado=True`; campo ausente → `aprovado=True` | Os dois reprovam; requisito publicado no artefato |
| **R-SUPORTE** — eleito com um erro | `StatisticsError` derrubava o relatório inteiro | `ReprovaEmAberto` com motivo; G0/G1/G2 preservados |

Suíte: **1.985 casos, zero skip** (era 1.973). **+12 contraprovas**, todas
exercitando a decisão dos gates, nenhuma apenas o JSON publicado.

---

## 2. R-C6 — a quarentena passou a vetar

`gate_g3` decidia por `relativa <= G3_MELHORIA_DETECTAVEL and B3_EXECUTADO`,
com a etiqueta de F3 pendurada ao lado sem efeito. **Isso não é quarentena, é
etiqueta** — e era o achado F10 repetido dentro do contrato escrito para
corrigi-lo: exigência que existe como texto e não participa da condição de
aprovação.

A correção é uma constante de módulo, no mesmo formato de `B3_EXECUTADO`:

```python
PODER_REDESENHADO_APOS_F3 = False
...
"aprovado": (
    relativa <= G3_MELHORIA_DETECTAVEL
    and B3_EXECUTADO
    and PODER_REDESENHADO_APOS_F3
),
```

Constante e não literal embutido por três razões, todas registradas no contrato
antes de codar: o veto fica legível no artefato (`poder_redesenhado_apos_f3`); a
contraprova exercita as quatro combinações sem editar código; e o dia em que F3
for redesenhado a liberação é **uma linha declarada**, não a remoção de um
`False` escondido dentro de um `and`.

**A contraprova é a matriz 2×2, com poder folgado nos quatro casos** para que o
que se meça seja o veto e não o limiar:

| `B3_EXECUTADO` | `PODER_REDESENHADO_APOS_F3` | `aprovado` | |
|---|---|---|---|
| `False` | `False` | `False` | estado de hoje |
| `True` | `False` | **`False`** | **o caso do parecer** — F3 veta com B3 presente |
| `False` | `True` | `False` | B3 veta sem F3 — o veto novo não substituiu o antigo |
| `True` | `True` | **`True`** | nenhum dos dois é `False` fixo disfarçado |

A quarta linha é a que dá sentido às outras três: **sem ela, um gate travado com
`"aprovado": False` literal passaria nos três primeiros casos e pareceria
correto.** Era a alternativa mais óbvia, e o contrato a rejeitou por escrito
antes de medir.

`decidivel`, `clusters_suficientes` e `ressalva` passaram a existir em G3 com a
semântica que `_poder` já usava. `clusters_suficientes` conta os emissores que
**entram no erro do baseline eleito** (contagem de C4-B), não os da população —
e é deliberadamente distinto de `decidivel`: três emissores bastam em número, e
a conta segue inválida por F3. São dois estados diferentes e o artefato os
separa.

---

## 3. R-C5 — G0 passou a exigir evidência independente

`gate_g0` copiava `identidades_conferidas_independentes` por `.get(...)` e não a
usava. Zero independentes aprovava; **campo ausente aprovava publicando
`None`** — "não sei" virando "sim", que é a guarda-que-aprova-por-ausência-de-dado
do §3.14 do AGENTS.md.

O piso implementado é o mínimo que não inventa limiar: o campo tem de estar
**presente, ser inteiro e ser maior que zero**. `bool` é descartado
explicitamente, porque é subclasse de `int` e um `true` num artefato malformado
passaria por contagem.

**O que este piso deliberadamente NÃO faz**, e por quê:

| Não faz | Por quê |
|---|---|
| Exigir cobertura percentual | O contrato C5-B pediu a marcação de linhagem e as duas contagens; **não fixou cobertura mínima**. Escolher um número agora seria fixar política depois de ver o dado. O revisor advertiu explicitamente contra inventar esse limiar, e esta onda não o inventa. |
| Exigir `independentes == conferidas` | Reprovaria população legítima com mistura de fechamentos independentes e por construção. |
| Exigir que as identidades anuais fechem | 17 das anuais são **não verificáveis por estado da fonte**, não por defeito do instrumento. |

Há contraprova para cada lado: a que reprova com zero, a que reprova com campo
ausente, **e as que confirmam que o piso não virou reprovação universal** — uma
identidade independente entre 40 conferidas certifica. Sem estas últimas, fixar
`aprovado: False` passaria nas primeiras.

**No artefato real nada mudou de veredito:** as duas contagens são 24,
`tem_evidencia_independente` sai `True`, e **G0 continua reprovando pelo mesmo
motivo de antes** — `observacoes_de_J == 0`. O piso novo não é o que reprova
hoje; muda o que aconteceria numa população futura.

**Precisão sobre esse motivo, porque é fácil errar:** a lista
`rubricas_com_conformidade_contratual_nao_demonstrada` sai **vazia** no artefato
de hoje, antes e depois desta onda. Isso **não** significa que as rubricas
suspeitas foram absolvidas — significa que elas nunca chegam a entrar numa
população que não existe. Com J identificado em zero dos 25 pacotes, não há
observação onde a não conformidade possa ser registrada. Ler a lista vazia como
"conformidade demonstrada" seria exatamente a leitura que o §3.17 proíbe.

---

## 4. R-SUPORTE — amostra insuficiente em vez de exceção crua

Com o baseline eleito cobrindo uma só observação, `statistics.stdev` levantava
`StatisticsError`, que `_medir` não captura — a execução morria levando junto
G0, G1 e G2 **já medidos**. Agora levanta `ReprovaEmAberto` com o motivo,
nomeando o baseline e o tamanho do suporte.

**`StatisticsError` continua sem ser capturada por `_medir`, de propósito.**
Acrescentá-la à cláusula converteria qualquer defeito estatístico futuro em
veredito plausível de gate — exatamente o que a separação `ErroDeUnidade` ×
`ReprovaEmAberto` existe para impedir.

**Confirmação independente de que é dívida anterior, sem depender do snapshot
perdido:** a chamada que estourava está na linha **603** do arquivo original e a
alteração de C4-B (`emissores_usados = sorted(por_emissor)`) na **627**. A
exceção estoura antes de qualquer linha introduzida por C4-B — que, portanto,
não pode tê-la causado. O revisor chegou à mesma conclusão comparando as duas
cópias; a ordem do arquivo prova o mesmo sem elas.

---

## 5. Auditoria das alterações de teste

Regra do projeto: **nunca enfraquecer asserção para fazer código passar.**

```console
$ diff <(grep -E "^\s*(assert |def test)" <snapshot>) \
       <(grep -E "^\s*(assert |def test)" tests/test_prontidao_b_dfc_01j.py) | grep "^<"
  NENHUMA
```

**Zero asserções ou testes removidos.** Os outros dois arquivos de teste ficaram
byte-idênticos.

**Desvio da previsão, na direção segura.** O contrato previu uma *substituição
declarada* em `test_C6_a_marcacao_nao_e_o_que_reprova_o_gate`, cuja única
asserção era `B3_EXECUTADO is False` — precisamente o que o revisor apontou como
não testar conjunção nenhuma. Na prática não foi preciso substituir: a asserção
existente **foi preservada**, ganhou uma segunda (`PODER_REDESENHADO_APOS_F3 is
False`) e a intenção que o teste protegia — o veto de B3 é independente — está
generalizada na matriz 2×2. O que mudou foi o **docstring**, porque o título do
caso passou a ser falso sob C6-bis: a marcação de F3 **é** um dos motivos da
reprovação agora, por contrato. A correção está declarada dentro do próprio
docstring, não escondida.

Nenhum dos quatro testes que o contrato previu como não-regressão precisou de
ajuste.

---

## 6. Auditoria de artefatos

Regenerados pelos entrypoints reais (`-m scripts.auditar_prontidao_b_dfc_01j` e
`-m scripts.sensibilidade_rubricas_suspeitas_b_dfc_01j`), nunca por edição de
JSON. Diff campo a campo contra o snapshot pré-onda:

- **`gates.json`** — três mudanças, **todas em G0 e todas declaradas**: o texto
  de `limiar`, e os campos novos `tem_evidencia_independente` (`True`) e
  `requisito_de_evidencia_independente`. Nenhuma mudança em G1, G2, G3, T1, T2.
- **`sensibilidade.json`** — **byte-idêntico**. A sensibilidade já cumpria C6; a
  onda não a tocou.
- **`extensao/*.jsonl` e `extensao/resumo.json`** — inalterados (hash do resumo
  idêntico ao do snapshot). A extensão não foi reexecutada; nenhum fato,
  derivação, conferência, vintage ou registro de J foi reproduzido.
- **Veredito:** `NAO AUTORIZA TREINO` antes e depois, decisivo em G0.

**Em G3, o artefato real não ganhou os campos novos** — a população é vazia, o
gate levanta `ReprovaEmAberto` antes de chegar neles e entra na cadeia como
reprovado com motivo. Os campos existem e estão cobertos por contraprova; no
artefato de hoje eles não aparecem porque não há o que medir. Registrado para
que ninguém leia a ausência como implementação faltando.

---

## 7. Condições de falsificação — todas checadas negativas

| # | Condição | Resultado |
|---|---|---|
| 1 | G0 muda de veredito ou de motivo no artefato real | ❌ não ocorreu — reprova pelo mesmo motivo (`observacoes_de_J == 0`); evidência independente 24, `tem_evidencia_independente: true` |
| 2 | Algum número muda além dos campos declarados | ❌ não ocorreu — série, fatos, derivações, conferências, vintages e sensibilidade inalterados |
| 3 | Alguma asserção enfraquecida | ❌ não ocorreu — zero remoções |
| 4 | G3 aprova nos casos 1–3 da matriz, ou reprova no 4 | ❌ não ocorreu — matriz exata ao contrato |
| 5 | População de J deixa de ser zero, ou gate anterior muda | ❌ não ocorreu |

---

## 8. O que esta onda NÃO fez

Continua aberto, e nada aqui encosta nisso:

1. **F3 — o redesenho estatístico do poder.** Segue sem correção. A diferença é
   que agora a invalidez **veta**, em vez de só estar escrita. `decidivel`
   continua `False` e os números continuam publicados e marcados.
2. **B3** — o benchmark econômico do §4 do pré-registro não foi implementado.
3. **Reconstrução point-in-time da população.**
4. **Cobertura mínima de evidência independente em G0** — deliberadamente não
   fixada, pelas razões do §3. Se algum dia for fixada, é política nova e
   precisa de pré-registro próprio.
5. **Adjudicação das rubricas do BB** e **representação de largura zero** dos
   198 registros `nao_identificado`.
6. **A constante `"unidade": "milhares_de_reais"` fixa** em
   `scripts/piloto_bancos_dfc.py:2062`, achado lateral da onda C1–C6.

---

## 9. Rastreabilidade

**Snapshot durável**, atendendo à recomendação do revisor de não deixá-lo em
diretório efêmero de sessão: `artefatos/b_dfc_01j/snapshots/2026-09-11-pre-rc5-rc6/`,
com os seis arquivos em escopo, três artefatos JSON e `SHA256SUMS.txt`. Os seis
hashes de partida **coincidem com os publicados no §6 da conferência
independente** — prova de que a onda partiu exatamente da versão auditada.

### Depois desta onda

```text
2353ba5593a902306edb70ec73dbc70d20d71601d30a2bb33219f6cd2d4f076d  scripts/piloto_bancos_dfc.py                      (inalterado)
08ac429f3dc07fc2dd7359797394d11139de3da19bd807127f053cccdf647ee0  scripts/auditar_prontidao_b_dfc_01j.py            (era 23dd9679…)
f38516be03973acc35b71300e1efc6bfdedef0442abc50c8cb84b41f6df59e2a  scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py  (inalterado)
9aa68cbd25719afccecedfaab0feacbd91c21fbdf214e9c779963d16329cfd17  tests/test_piloto_bancos_dfc.py                   (inalterado)
1231a7b748f1558641343dbcaa86aee439232041d81736b901d1926e665d9b02  tests/test_prontidao_b_dfc_01j.py                 (era 0dfe8011…)
5b4193b0607555d645b4f6a872fb682611ca956ab5c630955ca72d63b67141c7  tests/test_sensibilidade_b_dfc_01j.py             (inalterado)
43e31d9f150e535f1ab20576d9aacf1a53b83ecc5424ca7d48ba50781e4cef18  artefatos/cvm.duckdb                              (inalterado)
c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b  artefatos/cvm_treino.duckdb                       (inalterado)
```

**Dois arquivos mudaram nesta onda** — o auditor de prontidão e seus testes.
Painéis consultável e de treino intactos, `corpus/` limpo,
`corpus/holdout_2T2026` não acessado.

### Reprodução

```bash
CREWAI_STORAGE_DIR="$(mktemp -d)" .venv/bin/python -m pytest -q --tb=short
CREWAI_STORAGE_DIR="$(mktemp -d)" .venv/bin/python -m pytest -q \
  tests/test_prontidao_b_dfc_01j.py::TestContratosRC5RC6
CREWAI_STORAGE_DIR="$(mktemp -d)" .venv/bin/python -m scripts.auditar_prontidao_b_dfc_01j
```

**Nota de execução:** a sensibilidade precisa rodar como módulo
(`-m scripts.sensibilidade_...`), não por caminho de arquivo — ela importa
`from scripts.auditar_prontidao_b_dfc_01j import ...`.

---

## 10. Estado para a próxima conferência

Os três achados da conferência independente foram implementados com contraprova
que exercita a decisão. **O que segue faltando é a conferência independente
desta onda** — o mesmo ponto que a onda anterior deixou aberto, e que é a razão
de nenhuma delas poder se declarar encerrada por conta própria.

**Nada aqui autoriza treino, mudança de produto ou uso do holdout 2T2026.**
