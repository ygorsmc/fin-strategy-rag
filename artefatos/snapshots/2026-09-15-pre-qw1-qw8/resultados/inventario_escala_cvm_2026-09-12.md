# Inventário das declarações conflitantes de escala — arquivos da CVM

**Data:** 2026-09-12. **Natureza: INVENTÁRIO COM EVIDÊNCIA, não tabela de
correção.** Nenhum valor foi alterado, nenhum painel foi tocado, nenhuma
correção foi aplicada.

**Origem:** item 2 do §7 da [revisão do Rank
3-B](revisao_rank03b_consumo_operacional_2026-09-12.md) — *"publicar inventário
completo e determinístico... Adjudicar fontes, **sem converter um detector de
suspeitas em tabela automática de correções**"*.

| | |
|---|---|
| Script | `scripts/inventariar_escala_cvm.py` |
| Contraprovas | `tests/test_inventario_escala_cvm.py` — **9 casos** |
| Artefatos | `artefatos/escala_cvm/inventario.jsonl` (completo, 46 MB) · `resumo.json` |
| Suíte | **2.043 casos, zero skip** |
| Custo | **zero** — os 31 ZIPs já em disco, pinados por SHA-256; 4min47 de varredura |

---

## 1. O que destravou a adjudicação

A revisão disse que continuidade do valor bruto é **suspeita, não prova**, e que
adjudicar exige *"ler uma segunda demonstração"*. Ela existe, e estava à mão:

**A CVM declara o mesmo período duas vezes** — no arquivamento dele
(`ORDEM_EXERC = 'ÚLTIMO'`) e como comparativo no seguinte (`PENÚLTIMO`). A carga
aplica a regra de armadilha e **descarta o `PENÚLTIMO`**; por isso a segunda
declaração não aparecia em nenhuma medição anterior. Ela vive só nos CSVs
primários.

Com ela a suspeita vira prova: **o mesmo valor bruto sob escalas diferentes**.
`19424` não pode ser milhares e reais ao mesmo tempo.

## 2. A regra, deliberadamente conservadora

1. **Conflito** = mesma `(companhia, demonstrativo, conta, dt_ini, dt_fim)` sob
   mais de uma `ESCALA_MOEDA`.
2. **Prova de rótulo errado** = valor bruto **idêntico** sob escalas diferentes.
   Sem isso pode ser redenominação real, e o caso **não** é adjudicável.
3. **Desempate** = a escala que a **DFP anual auditada** declara, se declarar uma
   só. DFP ambígua ou ausente ⇒ **INDECIDÍVEL**.

**O que a regra recusa:** decidir por maioria de votos — arquivamento repetido
não é evidência nova —, inferir pela plausibilidade do valor, ou corrigir nada.

## 3. Resultado

| | |
|---|---:|
| Linhas consolidadas lidas | 26.267.152 |
| Casos com escala conflitante | **34.952** |
| Companhias envolvidas | **51** |
| **ADJUDICÁVEL pela DFP** | **10.261** (41 companhias) |
| INDECIDÍVEL | 24.691 |

### O achado que desfaz a leitura ingênua

Das 10.261 adjudicadas, **7.648 apontam para `MIL` e 2.613 para `UNIDADE`**.

**Não é "o ITR sempre erra".** Em um quarto dos casos é a declaração `MIL` que
está errada. Correção em bloco numa direção única estragaria 2.613 casos — e é
exatamente a tabela automática contra a qual a revisão advertiu.

### O caso testemunha

`003549`, `2020-12-31`, valor bruto **19424** em todas as declarações:

| Fonte | `DT_REFER` | `ORDEM_EXERC` | Escala |
|---|---|---|---|
| **DFP 2020** | 2020-12-31 | ÚLTIMO | **MIL** |
| ITR 2021 | 2021-03-31 / 06-30 / 09-30 | PENÚLTIMO | UNIDADE |
| **DFP 2021** | 2021-12-31 | PENÚLTIMO | **MIL** |

Adjudicado **MIL**. É a companhia com mais casos do inventário: **1.340**.

### A conservadoria funcionando

O período `2019-12-31` da mesma companhia saiu **INDECIDÍVEL**: ali a declaração
`UNIDADE` traz **19.572** contra **19.491** das `MIL`. Valores diferentes podem
ser reapresentação, não erro de rótulo — e a regra se recusa a adjudicar, embora
o padrão da companhia sugerisse `MIL`.

**É o caso que mostra que o inventário não está só confirmando a hipótese que o
gerou.**

## 4. Dois defeitos meus, achados ao ampliar o escopo

**Primeiro: a conta detectora deixava uma lacuna que eu mesmo havia declarado.**
A versão inicial usou só o ativo total e registrava o *documento*, deixando em
aberto quais contas dele a correção alcançaria — porque escala **não** é uniforme
dentro de um documento (16.248 de 23.407 misturam `MIL` e `UNIDADE`
legitimamente: dinheiro em milhares, ações em unidades). Medido que a varredura
completa custa 4min47, a lacuna deixou de ter razão de existir: **cada conta é
adjudicada pela própria evidência**, sem heurística sobre "conta monetária".

**Segundo: a chave ignorava `DT_INI_EXERC`.** Balanço é posição; DRE e DFC são
período. Sem o início na chave, o acumulado e o isolado que terminam no mesmo dia
colapsavam num caso só — e, tendo valores legitimamente diferentes, saíam **todos
indecidíveis**. Era por isso que nenhum caso de DRE ou DFC aparecia adjudicável.
Corrigido, eles aparecem.

## 5. O limite real da regra, medido e não contornado

Mesmo com a chave certa, a adjudicação concentra-se no balanço:

| | BPA | BPP | DRE | DFC_MI | DMPL | DVA | DRA |
|---|---:|---:|---:|---:|---:|---:|---:|
| Adjudicáveis | 3.692 | 6.502 | 14 | 0 | 26 | 24 | 3 |
| Indecidíveis | 1.696 | 2.889 | 6.179 | 4.335 | 3.363 | 5.219 | 1.010 |

**A razão é estrutural, não um defeito a consertar:** o desempate é a DFP, e a
DFP declara **períodos anuais**. Balanço tem posição em 31/12, que a DFP declara
e o ITR repete como comparativo. Resultado e fluxo de caixa **trimestrais** não
têm declaração anual do mesmo período — logo não há instância auditada para
desempatar.

### Uma propagação possível, medida e NÃO adotada

**270 documentos** têm adjudicação direta e coerente (uma escala só). Dentro
deles há **17.803** casos indecidíveis distintos, dos 24.691 totais.

Propagar a adjudicação do documento para esses casos é **defensável** — o
`ESCALA_MOEDA` nasce da escala declarada no arquivamento — mas é **inferência,
não evidência direta**, e seria decisão nova. Publico o número para que o
próximo contrato possa decidi-la com o custo à vista. **Não a adotei.**

## 6. Contraprovas

Nove casos, e a maioria verifica o que a peça **se recusa** a fazer: valor
diferente não adjudica; DFP ambígua não adjudica; conflito só entre ITRs não
adjudica; **maioria de votos não decide** (três ITRs não vencem uma DFP); a saída
não declara `valor_corrigido`; e toda declaração carrega arquivo, membro, versão
e `ORDEM_EXERC` para reconferência.

**Determinismo:** inverter a ordem da entrada não muda o inventário, e a saída
sai ordenada.

## 7. O que isto NÃO autoriza

1. **Não corrige nada.** Aplicar exige contrato próprio no padrão do §3.3, com a
   guarda anti-porta-dos-fundos que **falha** se a CVM republicar o arquivo.
2. **Não mede impacto na etapa 10.** Exige análise de dependências própria:
   razões podem cancelar uma escala comum; diferenças e janelas TTM não cancelam.
3. **Não resolve os 24.691 indecidíveis.** 17.803 poderiam cair por propagação
   documental — decisão não tomada; o resto precisa da demonstração publicada
   pela companhia.
4. **Não cobre o individual.** Só demonstrativos consolidados: o individual é
   outra entidade contábil e não serve de segunda declaração do mesmo fato.

## 8. Reprodução

```bash
.venv/bin/python -m scripts.inventariar_escala_cvm          # ~4min47, custo zero
CREWAI_STORAGE_DIR="$(mktemp -d)" .venv/bin/python -m pytest -q \
  tests/test_inventario_escala_cvm.py
```

O `resumo.json` traz contagens, a regra e o SHA-256 dos 31 ZIPs; o
`inventario.jsonl` traz **todos** os casos, um por linha, cada um com todas as
suas declarações e procedência.

**Sem escrita** em painel, corpus ou tabela de correções. Sem rede, sem API paga,
sem leitura do holdout.

---

## 9. Retratação da recomendação — medido em 2026-09-12, depois do §8

**Eu havia recomendado aplicar as 10.261 adjudicações diretas. Medi antes de
escrever o contrato, e a recomendação estava errada: elas corrigiriam ZERO
linhas do painel.**

```text
casos adjudicados cuja declaração ÚLTIMO está errada:  0 de 10.261
linhas ÚLTIMO a corrigir (chegam ao painel):           0
linhas PENÚLTIMO erradas (descartadas na carga):  19.859
```

**Por que.** O desempate é a DFP, que declara o **fim de exercício**. Nesses
períodos a declaração da DFP é a correta; quem erra é o **comparativo
`PENÚLTIMO`** do ITR seguinte — e `PENÚLTIMO` é exatamente o que a regra de
armadilha descarta na carga. O defeito que chega ao painel é outro: a declaração
`ÚLTIMO` das posições de **meio de ano**, que nenhum segundo documento declara e
que portanto **não é adjudicável por esta regra**.

O caso testemunha mostra os dois lados: o ITR `2020-09-30` de `003549` entra no
painel com `UNIDADE` e `valor_reais = 19358`, e **não aparece** entre os casos
adjudicáveis — porque ninguém mais declara 30/09/2020.

### O que o inventário entrega, então

**Identifica os documentos defeituosos, com evidência direta.** São **127
documentos** em 41 companhias cuja declaração foi provada errada, e o ITR
`2020-09-30` de `003549` está entre eles. Esses documentos põem **33.655 linhas**
no painel, **todas** com escala divergente da adjudicada.

O que falta não é *qual documento* — é *quais linhas dele* reescalar.

### E por que a propagação não resolve, nem na versão refinada

Testei a regra refinada que eu mesmo havia proposto — aprender a escala natural
de cada conta nos documentos incontestados da própria companhia:

| | Linhas |
|---|---:|
| Corrigir (natureza da conta bate com a adjudicada) | 27.728 |
| Preservar (natureza diverge) | 5.735 |
| Sem evidência da conta | 192 |

Parece funcionar — e **não funciona**. Entre as 27.728 "a corrigir" há **613
linhas `3.99.*`**, que é **Lucro por Ação** no plano padrão da CVM. Convertê-las
de `UNIDADE` para `MIL` multiplicaria o LPA por 1.000: **criaria exatamente o
defeito que estamos consertando**.

A refinação não protege porque, nessas companhias, os documentos limpos também
declaram `3.99` como `MIL` — o `ESCALA_MOEDA` é metadado do documento e não se
aplica de fato às linhas por ação. Isso é defeito **preexistente e mais amplo**
que o desta onda, e o §3.16 já havia sinalizado o LPA como campo frágil.

### Recomendação revista

**Não escrever tabela de correção nenhuma agora.** O bloqueio é preciso e
nomeável: *distinguir conta monetária de conta não monetária dentro de um
documento comprovadamente defeituoso*.

Essa é a mesma lacuna que o `mapa_contas` tem hoje — **4,95% de cobertura** — e o
§3.8 já nomeou o destravador: **a tabela de 208 contas do plano padrão da CVM**,
estimada em ~7 horas de anotação, que aquele registro classificou como *"entrega
real sem ser modelo"*. Ela diz quais contas são monetárias, que é exatamente o
que falta aqui.

**Ordem sugerida, revista:**

1. Anotar o plano padrão (as 208 contas) — trabalho já identificado como valioso
   e adiado, que agora tem um segundo consumidor concreto.
2. Com ele, escrever a correção de escala por documento, restrita às contas
   monetárias.
3. Uma única reconstrução de painel, com a derivação já corrigida junto.
4. Medir o efeito na etapa 10.

**O que NÃO mudou:** o inventário continua válido e é o que torna o passo 2
possível — ele prova quais documentos estão errados e para que lado. O que caiu
foi minha suposição de que a adjudicação já bastava para corrigir.
