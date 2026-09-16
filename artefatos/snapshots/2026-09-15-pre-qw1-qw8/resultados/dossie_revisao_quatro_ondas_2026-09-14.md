# Dossiê de revisão — as quatro ondas depois da revisão de 12/09

**Data:** 2026-09-14 · **Branch:** `corrige-contrato-corpus` · **Nada commitado.**
**Para:** agente revisor, com contexto separado.
**Autor do trabalho revisado:** sessão principal.
**Ponto de partida:** [revisão independente do Rank 3-B,
2026-09-12](revisao_rank03b_consumo_operacional_2026-09-12.md)
(`4e6a3eb13dd5…`), que é a última conferência independente que este trabalho
recebeu.

Quatro ondas foram executadas depois dela. **Nenhuma foi conferida por
ninguém além de mim.** Este documento existe para que isso deixe de ser
verdade — e para concentrar o que um revisor precisa: **onde parei de medir e
comecei a julgar**, que é onde o erro, se houver, está.

Ordem de leitura sugerida: §1 (o que se pede) → §2 (o que mudou e o que **não**
mudou) → §6 (julgamentos) → §3 (reproduzir) → §9 (o que eu deixei aberto).

---

## 1. O que se pede ao revisor

Perguntas falsificáveis, em ordem de risco. **Q1 e Q2 são as que importam.**

| # | Pergunta | Onde verificar |
|---|---|---|
| **Q1** | Corrigir o instrumento do Rank 3-B **melhorou a medição** ou apenas **moveu o número para onde eu queria**? O veredito era e continua `REPROVADO EM G0`; confira se algum limiar, população ou regra de seleção foi mexido no caminho | §6.1 · §4.1 · `artefatos/rank03b/auditoria.json` |
| **Q2** | A **retratação** da minha própria recomendação de escala está certa, ou eu me enganei duas vezes? A afirmação é forte: as 10.261 adjudicações corrigem **zero** linhas do painel | §6.3 · §3.3 · inventário §9 |
| **Q3** | O sinal de monetariedade do plano padrão (razão sobre o ativo total) **distingue** conta monetária de não monetária, ou só distingue **ordem de grandeza**? Uma conta monetária minúscula cai na mesma faixa de uma por ação | §6.4 · §9.4 |
| **Q4** | A banda de **80–100 dias** da derivação é a fronteira certa, ou ela recusa derivação legítima que eu não observei? Ela foi calibrada **depois** de ver a distribuição | §6.2 |
| **Q5** | A emenda que eu fiz ao meu próprio contrato (R6, adjacência) é correção honesta ou **alargamento de escopo para melhorar o resultado**? Ela mudou `g0_3` de 136 para 132 | §6.5 · implementação §6 |
| **Q6** | Os números publicados reproduzem? **Três inconsistências foram achadas hoje, escrevendo este dossiê** (§9.1–§9.3). Procure uma quarta | §9 |
| **Q7** | Alguma asserção foi enfraquecida? Duas linhas de teste mudaram em quatro ondas, as duas declaradas em contrato antes | §7 |
| **Q8** | O que **não** foi feito está declarado, ou algum item silenciosamente sumiu da lista? A revisão de 12/09 pediu quatro coisas; entreguei três | §5 |

**Regra da casa que se aplica à revisão:** se um teste precisar ser enfraquecido
para o código passar, o problema é o código. E **discordância medida vale mais
que concordância** — parecer que só confirma não justifica a rodada.

---

## 2. O que mudou, e o que deliberadamente não mudou

### 2.1 Não mudou — e é o mais importante

| | Estado |
|---|---|
| **Veredito do Rank 3-B** | `REPROVADO EM G0` — idêntico ao de 11/09 |
| **Modelo carregado** | **Nenhum**, em nenhuma onda |
| **T1 / T2 / baselines sobre o painel real** | **NÃO medidos**. A cadeia publicada tem **só `G0`** |
| **Painel em disco** | **Intocado.** `cvm.duckdb` `43e31d9f…` · `cvm_treino.duckdb` `c1a60445…` |
| **Correção de escala aplicada** | **Nenhuma.** Zero células alteradas |
| **Previsão pré-registrada sobre `fco_ttm_sobre_sd8`** | **Segue sem teste.** Corrigir instrumento e dado **não** a confirma |
| **Pré-registro `fbae30cc…`** | **Consumido.** Remedir exige protocolo novo |

**Um revisor cético pode dizer que quatro ondas não mudaram o veredito.**
Correto. O que mudou foi o **instrumento**, o **inventário do defeito de dado** e
o **destravador da correção** — e cada um desses é verificável por si.

### 2.2 Mudou

| Onda | Entrega | Suíte |
|---|---|---|
| **1 — R1–R7** | Instrumento do Rank 3-B corrigido em sete achados da revisão + duas emendas minhas | 2.010 → **2.030** |
| **2 — derivação** | `_derivar_trimestres_intermediarios` deixa de produzir semestre rotulado trimestre (**código**, não painel) | 2.030 → **2.034** |
| **3 — inventário de escala** | 26,3 M de linhas varridas; 34.952 conflitos; **retratação** da recomendação que eu mesmo dei | 2.034 → **2.043** |
| **4 — plano padrão** | Esqueleto de 300 contas para anotação humana; `classe_confirmada` nasce vazia | 2.043 → **2.056** |

---

## 3. Reproduzir do zero

Custo **zero** — tudo lido de disco. Sem rede, sem API paga, sem holdout.

**Os quatro blocos abaixo foram executados hoje, 2026-09-14, antes de publicar
este dossiê.** Todos devolvem o esperado.

### 3.1 O instrumento e a suíte

```bash
export PYTHONPATH=.
CREWAI_STORAGE_DIR="$(mktemp -d)" .venv/bin/python -m pytest -q
# esperado: 2.056 passed, zero skip

.venv/bin/python -m scripts.auditar_rank03b_consumo_operacional   # sai com código 2
```

### 3.2 O defeito de derivação (mede o painel, não escreve nele)

```bash
.venv/bin/python - <<'PY'
import duckdb
con = duckdb.connect('artefatos/cvm_treino.duckdb', read_only=True)
print(con.execute("""
  select (dt_fim_exerc - dt_ini_exerc) + 1 as dias, count(*) linhas,
         count(distinct cd_cvm) cias, count(distinct cd_conta) contas
  from fatos_contabeis
  where origem like '%deriv%' and tipo_periodo = 'trimestral'
  group by 1 order by 2 desc limit 8
""").fetchall())
PY
```

Esperado: **7.555** linhas de 183 dias (507 companhias, 111 contas) e mais
179 fora da banda — **7.734** no total, contra 701.357 corretas. **Elas ainda
estão lá:** o código foi corrigido, o painel não foi reconstruído (§6.2).

### 3.3 A retratação da escala — a checagem que derrubou minha recomendação

```bash
.venv/bin/python - <<'PY'
import json
adj = [json.loads(l) for l in open('artefatos/escala_cvm/inventario.jsonl')]
adj = [c for c in adj if c['veredito'] == 'ADJUDICAVEL_PELA_DFP']
erradas_ultimo = sum(
    1 for c in adj
    if any(d['ordem_exerc'] == 'ÚLTIMO' and d['escala'] != c['escala_correta']
           for d in c['declaracoes'])
)
print('adjudicados:', len(adj), '| com ÚLTIMO errado:', erradas_ultimo)
PY
```

Esperado: **10.261 e 0**. Zero é a retratação inteira: o erro está sempre no
comparativo `PENÚLTIMO`, que a **regra de armadilha já descarta na carga**.

### 3.4 O esqueleto do plano padrão

```bash
.venv/bin/python -m scripts.esqueleto_plano_padrao    # RECUSA sobrescrever o CSV existente
.venv/bin/python - <<'PY'
import csv, collections
r = list(csv.DictReader(open('corpus/cvm/plano_padrao_contas.csv')))
print(len(r), collections.Counter(x['classe_proposta'] for x in r))
print('confirmada vazia em todas:', all(x['classe_confirmada'] == '' for x in r))
PY
```

Esperado: **300** · `{monetaria: 291, nao_monetaria: 7, INDEFINIDA: 2}` · `True`.

---

## 4. A trilha — quatro ondas, em ordem

Cada uma seguiu o mesmo rito: **snapshot com hashes conferidos contra os
publicados pela revisão** → **contrato escrito antes do código, com alternativas
rejeitadas** → implementação com contraprovas que exercitam a **decisão** →
suíte cheia → diff dos artefatos contra o snapshot → relatório com **tabela de
condições de falsificação** → sincronização de AGENTS/MEMORY/becos por **blocos
datados acrescentados**, nunca por reescrita.

### 4.1 Onda 1 — R1–R7 no instrumento do Rank 3-B

Contrato `cc5c851e…` · implementação `13ba12d1…`.

| Achado | Antes | Depois |
|---|---|---|
| **R1** identidade da observação | `max(valor)` e `min(dt_receb)` vinham de **linhas diferentes**; 4 grupos de FCO e 26 de ativo com data antecipada | Carga por linha; vintage escolhido em D por `vigente_em`; **0 e 0** |
| **R2** horizonte | `q1` deslizava para o primeiro trimestre **disponível** | `primeiro_trimestre_apos(D)` puro de **calendário**; janelas contíguas exigidas |
| **R3** ranking | `sorted(zip(escores, alvos))` desempatava **pelo rótulo**: precisão 1,0 e lift 10,0 com escore **constante** | Ordenação cega ao desfecho; empate no corte pelo **valor esperado**: precisão 0,1 e lift 1,0 |
| **R4** decisão | Baseline falho devolvia **`PRONTO PARA CHALLENGER`** | Três estados; completude dos baselines **na conjunção** |
| **R5** suporte | Mínimo de companhias só na amostra global | Recontado por **componente**, após filtrar ausentes |
| **R6** adjacência *(emenda minha)* | 136 "saltos adjacentes", 4 deles a 3, 3, 5 e 14 trimestres de distância | **132**, com os quatro publicados |
| **R7** diagnóstico de escala | Um recorte, duas classes, linguagem de "linhas erradas" | **Quatro** recortes, **três** classes, linguagem de **transições suspeitas** |

**R4 é o mais grave e é o achado F10 pela quarta vez** no projeto: exigência que
existe como texto e **não participa da condição de aprovação**. Eu havia escrito
essa regra no AGENTS.md no dia anterior.

### 4.2 Onda 2 — a derivação, na camada comum

Contrato `b71a9e94…` · relatório `138e4c07…`.

`isolado(q) = acumulado(q) − acumulado(q−1)` pareava, por `lag`, o período
anterior **disponível** — não o **imediatamente** anterior. Faltando um
acumulado intermediário, a diferença cobria dois trimestres e saía rotulada
`tipo_periodo='trimestral'`.

A correção é uma condição declarada em constante: a diferença entre fins tem de
ficar **entre 80 e 100 dias**. Os 701.357 derivados corretos caem dentro; os
7.734 anômalos caem fora; **nenhum caso ambíguo foi observado**.

**O que esta onda não fez:** reconstruir o painel. §6.2.

### 4.3 Onda 3 — inventário de escala, e a retratação

Relatório `40ea0a41…` (inclui o §9, a retratação).

O que destravou: `ORDEM_EXERC = 'PENÚLTIMO'`. A CVM **redeclara o mesmo período**
como comparativo no arquivamento seguinte; a carga descarta essa linha pela regra
de armadilha, e por isso essa segunda declaração independente **nunca havia sido
olhada**.

| | |
|---|---:|
| Linhas varridas (31 ZIPs) | **26.267.152** |
| Casos com escala conflitante | **34.952** em 51 companhias |
| Adjudicáveis pela DFP auditada | **10.261** (41 companhias) |
| Direção: `MIL` / `UNIDADE` | **7.648 / 2.613** |
| Indecidíveis | **24.691** |

**A direção importa:** corrigir em bloco para `MIL` estragaria 2.613 casos.

**E então a retratação.** Eu recomendei aplicar as 10.261; medi antes de
escrever o contrato; **elas corrigem zero linhas do painel** (§3.3). O que o
inventário entrega é **identificação**: **127 documentos** (41 companhias,
**33.655 linhas** no painel) provadamente defeituosos. O que falta não é *qual
documento* — é *quais linhas dele* reescalar.

**A propagação refinada que eu propus em seguida também falhou na medição:**
aprender a escala natural de cada conta nos documentos incontestados marcaria
27.728 linhas "a corrigir" — e **613 delas são `3.99.*`, Lucro por Ação**.
Convertê-las multiplicaria o LPA por mil: **criaria exatamente o defeito que se
está consertando**. Rejeitada.

### 4.4 Onda 4 — o esqueleto do plano padrão

O bloqueio ficou nomeável: *distinguir conta monetária de não monetária dentro
de um documento comprovadamente defeituoso*.

| | |
|---|---|
| Entrega | `corpus/cvm/plano_padrao_contas.csv` — **300 contas**, 11 colunas, **92,89%** das linhas do painel |
| Proposta | 291 monetárias · **7 não monetárias** · 2 `INDEFINIDA` |
| Campo que decide | `classe_confirmada`, **vazia em todas as 300 linhas** |
| Trava | O script **recusa sobrescrever** o arquivo existente |

**Correção ao §3.8 do AGENTS.md:** a alegação de que *"208 contas destravam 85%
das linhas"* **não reproduz** — 208 contas dão **77,6%** por
`(demonstrativo, cd_conta)`; 300 dão **92,9%**, onde a curva achata.

**Um sinal foi testado e descartado:** a fração de linhas `UNIDADE` dentro de
documentos `MIL` classifica **as 300** como monetárias, inclusive o LPA — o
`ESCALA_MOEDA` é metadado do arquivamento e não sabe o que a conta significa.
O sinal adotado é a **magnitude relativa ao ativo total da mesma companhia no
mesmo arquivamento**: por ação fica em ~1e-8, monetária entre 1e-4 e 1.

---

## 5. O que a revisão de 12/09 pediu, item por item

| Pedido do §7 da revisão | Estado |
|---|---|
| 1. Corrigir e testar o instrumento (fato/vintage/data, horizonte, desempate, suporte, decisão) | ✅ **Onda 1**, R1–R5 + R6/R7 |
| 2. Inventário completo e determinístico dos problemas de escala; corrigir a descrição dos 15 grupos; **não** converter detector em tabela automática | ✅ **Onda 3** — e a tentação de virar tabela automática foi medida e **rejeitada duas vezes** |
| 3. Corrigir derivação e identificação de períodos na camada comum, com testes próprios | ⚠️ **Parcial — Onda 2.** A **derivação** foi corrigida no código; o **painel não foi reconstruído**; os **períodos curtos** (16 linhas, colisão de trimestre fiscal na fonte) **seguem sem conserto** |
| 4. Registrar novo protocolo antes de qualquer remedição do alvo | ❌ **Não feito, e não deve ser feito ainda** — o alvo não foi remedido, então não há protocolo a registrar. Quando houver, `fbae30cc…` está consumido |

---

## 6. Onde eu decidi por julgamento — o alvo da revisão

### 6.1 (Q1) Corrigir o instrumento não mudou o veredito

**A objeção honesta:** eu corrigi sete defeitos e o resultado é o mesmo
`REPROVADO EM G0`. Isso prova que as correções valeram?

**Minha resposta, falsificável:** o que mudou é **verificável e mede contra
mim**, não a favor:

| | Antes | Depois |
|---|---:|---:|
| `g0_3` saltos de escala (universo, adjacentes) | 136 | **132** |
| `g0_3_fracao` contra limiar de 0,5% | 0,6052% | **0,5874%** |
| Precisão dos baselines com escore constante | **1,0** (leakage) | **0,1** |
| Lift no mesmo cenário | **10,0** | **1,0** |
| Grupos de FCO com data antecipada | 4 | **0** |

**O G0 continua reprovando sob as duas leituras** — 0,6052% e 0,5874% são ambos
maiores que 0,5%. Se as correções tivessem sido escolhidas para favorecer o
candidato, a fração teria cruzado o limiar. **Não cruzou.**

**Como refutar:** encontre um limiar, uma população ou uma regra de seleção que
mudou sem estar declarada no contrato `cc5c851e…`.

### 6.2 (Q4) A banda de 80–100 dias foi calibrada depois de ver os dados

**Declarado, não escondido.** Eu medi a distribuição de durações dos derivados e
**então** escrevi a banda. Não é limiar pré-registrado.

Em defesa: a distribuição é **bimodal com separação limpa** — 701.357 casos entre
80 e 100 dias, e o próximo grupo salta para **182–184**. Não há massa entre 101 e
181. **Nenhum caso ambíguo foi observado**, então a escolha exata dentro do vão
não altera nenhuma classificação.

**Como refutar:** ache um trimestre fiscal legítimo fora de 80–100 dias — um
exercício social com trimestres desiguais o produziria. Se existir, a banda
recusa derivação boa, e **o aviso de recusa é o único sinal disso** (é contado e
reportado, §4.2).

### 6.3 (Q2) A retratação depende de uma leitura da regra de armadilha

A afirmação "corrigem zero linhas" só vale se **`PENÚLTIMO` realmente nunca
chega ao painel**. Isso é comportamento da carga, não do inventário.

**Se o revisor achar um caminho pelo qual uma linha `PENÚLTIMO` entra no
painel, a retratação cai e a recomendação original volta a valer.** É a
verificação mais barata e mais decisiva deste dossiê.

### 6.4 (Q3) O sinal de monetariedade mede grandeza, não semântica

**A objeção mais forte contra a onda 4.** A razão sobre o ativo total separa
`1e-8` de `1e-4` — mas isso é **ordem de grandeza**, não natureza contábil. Uma
provisão monetária minúscula cai na mesma faixa de uma linha por ação.

**Foi observado na prática:** as duas contas `INDEFINIDA` são "Provisões para
Reestruturação", a **9,981e-05** e **1,152e-05** — monetárias pequenas na zona
cinzenta. O comportamento é o desejado (sinaliza em vez de chutar), mas confirma
que o sinal **não decide**.

**É por isso que `classe_confirmada` nasce vazia e o script nunca a preenche.**
O sinal é auxílio de revisão. **Se o revisor concluir que ele induz mais erro do
que economiza tempo, a coluna `classe_proposta` deve ser removida**, não
ajustada.

### 6.5 (Q5) Eu emendei meu próprio contrato no meio da implementação

O contrato R1–R5 adiava explicitamente a adjacência para "outra onda". Eu a
corrigi **na mesma onda**, e declarei a emenda no §6 do relatório.

**Em defesa:** deixar um "trimestres adjacentes" sabidamente errado enquanto se
corrigem cinco defeitos irmãos seria incoerente. **Contra:** é exatamente o
formato de alargar escopo para melhorar resultado.

**A verificação que me protege — e que o revisor deve refazer:** a emenda
**piorou** minha posição relativa ao limiar em nada e não cruzou fronteira
nenhuma (§6.1). Se tivesse cruzado, a emenda seria indefensável.

### 6.6 Decidi sozinho o que era "próximo item" três vezes

Depois da revisão, o usuário aprovou cada passo com uma frase curta
("Sim, pode começar", "Então continue", "Então bora fazer"). **Qual era o
"próximo item" fui eu quem escolheu** — instrumento, depois derivação, depois
escala, depois plano padrão.

A ordem é defensável (cada um destrava o seguinte), mas **não foi negociada**.
Um revisor pode legitimamente dizer que a ordem certa era parar depois da onda 1
e pedir conferência independente antes de mexer na camada comum.

---

## 7. Mudanças de código, e a auditoria das alterações de teste

| Onde | O quê | Contraprovas |
|---|---|---|
| `scripts/auditar_rank03b_consumo_operacional.py` | `vigente_em`, `primeiro_trimestre_apos`, `_contigua`, `_precisao_no_topo`, `_auc_intra`, `_ic_por_companhia`; `construir_amostra`, `medir_baselines`, `executar`, `gate_g0`, `diagnosticar_escala` reescritos | +20 em `TestContratosR1aR5` (25 → **45**) |
| `src/dados_estruturados.py` | Banda `80–100` na derivação; retorno `int` → `(criados, recusados)`; aviso ao chamador | +4 em `TestDerivacaoSoCobreUmTrimestre` (**169** no arquivo) |
| `scripts/inventariar_escala_cvm.py` | Novo. Varredura em duas passagens; chave com `demonstrativo` e `dt_ini_exerc` | **9** contraprovas, quase todas de **recusa** |
| `scripts/esqueleto_plano_padrao.py` | Novo. Sinal de magnitude relativa; recusa sobrescrever anotação | **13** contraprovas |

**Duas linhas de teste mudaram em quatro ondas**, as duas declaradas em contrato
**antes**:

- uma **tautologia** (`assert ... or True`) substituída por verificação real;
- um **nome** de motivo de descarte, renomeado com a asserção intacta.

**Nenhuma asserção enfraquecida.** O diff de `^\s*(assert |def test)` contra o
snapshot mostra exatamente essas duas remoções.

**Um teste merece destaque para o revisor:** `test_ativo_total_tem_razao_um`
existe porque **achou um bug meu** — eu dividia `vl_conta` **bruto** pelo ativo
já **escalado**, erro de 1000× em silêncio. A checagem "Ativo Total dividido por
si mesmo tem de dar 1,0" devolveu `1e-3`. Está no docstring do caso.

---

## 8. Não mutação — verificado em 2026-09-14

| Invariante | Estado |
|---|---|
| `artefatos/cvm.duckdb` | ✅ `43e31d9f150e535f…` inalterado |
| `artefatos/cvm_treino.duckdb` | ✅ `c1a604453a9a2fa7…` inalterado |
| `corpus/holdout_2T2026` | ✅ nunca lido |
| `corpus/metadados.csv` · índice vetorial | ✅ intocados |
| Pré-registro `fbae30cc…` | ✅ inalterado; confere com `PRE_REGISTRO_CONGELADO.txt` |
| Chamadas pagas | ✅ **zero** |
| Modelo treinado | ✅ **nenhum**, em nenhuma onda |
| Suíte, reexecutada hoje | ✅ **2.056 passed, 28 warnings, 190,53 s, zero skip** |

**Um hash mudou e é esperado:** o relatório de validação de 11/09 saiu de
`edfee5d6…` (o que a revisão conferiu) para `c0119513…`. A diferença é o **bloco
de ressalva datado acrescentado no topo**; o corpo **não foi reescrito**. O
revisor deve confirmar isso, e não aceitar minha palavra.

### Procedência dos artefatos desta revisão

```text
afffe087b2e2d66843d2ee2e28839b83f48ce6f2cc4376303c50ac53d85951ef  scripts/auditar_rank03b_consumo_operacional.py
fcdf7be547b4c498b46dca12b006d422d53d0abe0547ce046848234bad89da68  tests/test_rank03b_consumo_operacional.py
5b719f1e799cb054b52299a5995eae18ca4e35ec6720cd6582308fc45339a404  scripts/inventariar_escala_cvm.py
117e924f403a436a549d633b11a9cfaafc8482a8da11b339e907d2d5780613a1  tests/test_inventario_escala_cvm.py
4e9a0dc5ce4ec068631aacb3afc45221776d220034c6af5a4003c1dced33dda4  scripts/esqueleto_plano_padrao.py
13bfbf3fa9886413daebd95ffec508a56e3806764a4b14362b71edf2fe7ed58e  tests/test_esqueleto_plano_padrao.py
2659dee71141bde2f65a35a6d2d569fbd286d1a70151004f2a03b7fc1b988f6e  src/dados_estruturados.py
079ef99c7fc1cb086b5d43ffb7a0b82f16d63a7f23cce1edf4375b5f12f62eb2  tests/test_dados_estruturados.py
b58dbe0115d18347c13c37cd7192d1a2d8c0c78a008a9041772e526c650dd9e9  corpus/cvm/plano_padrao_contas.csv
a2ef88bea647777797d909624662bfe2761ab6ceaaaf4f5eae7f4b2e3d327ee0  artefatos/rank03b/auditoria.json
d420138c9659215834d63811b41064341097f5c4e957a12649e11c8b8b564ed0  artefatos/escala_cvm/resumo.json
```

Snapshot de partida da onda 1: `artefatos/rank03b/snapshots/2026-09-12-pre-r1-r5/`,
com `SHA256SUMS.txt`. Os hashes de partida **coincidem com os publicados no §6 da
revisão** — prova de que a onda partiu da versão auditada.

---

## 9. Pontos abertos que eu encontrei e NÃO fechei

Os três primeiros foram achados **hoje, escrevendo este dossiê**. Declarados
porque escondê-los é o oposto do que o projeto mede.

### 9.1 `resumo.json` publica uma regra de adjudicação **desatualizada**

O campo `regra_de_adjudicacao` diz:

> "conflito = mesma **(cd_cvm, cd_conta, dt_fim_exerc)** sob mais de uma
> `ESCALA_MOEDA`…"

**A chave real do código é `(cd_cvm, demonstrativo, cd_conta, dt_ini_exerc,
dt_fim_exerc)`** — `scripts/inventariar_escala_cvm.py:111`. O texto é da **v1**
do script, quando o escopo era só `conta='1'`; a generalização acrescentou
`demonstrativo` e `dt_ini_exerc` (este último **corrigindo um defeito que zerava
as adjudicações em DRE/DFC**) e o resumo não acompanhou.

**Os números estão certos** — foram produzidos pela chave real. **A regra
publicada ao lado deles, não.** É exatamente a classe *"número certo, regra de
seleção não publicada"* que o dossiê anterior registrou no §5.5.

**Não corrigi**, e a razão é declarada: mudar só a string deixa código e
artefato discordando; regenerar o artefato exige revarrer 26,3 M de linhas.
A correção certa é **as duas coisas na mesma onda**, e ela não estava no escopo
deste documento.

### 9.2 A cobertura do `mapa_contas` circula com **quatro** valores diferentes

| Fonte | Valor |
|---|---:|
| AGENTS.md §3.7 e inventário §9 | **4,95%** |
| Docstring de `scripts/esqueleto_plano_padrao.py` | **3,8%** |
| Medido hoje: `fatos_semanticos` ÷ linhas com `tipo_periodo` compatível | **3,26%** |
| Medido hoje: `fatos_semanticos` ÷ painel inteiro | **2,60%** |

`186.939` linhas em `fatos_semanticos`; `5.741.481` com `tipo_periodo IN
('trimestral','instantaneo')`; `7.177.705` no painel.

**Nenhuma das duas fontes publicou o denominador.** É *"denominador não é
rótulo"* aplicado a mim mesmo. O número não muda nenhuma conclusão — a cobertura
é baixa sob qualquer leitura, e o plano padrão continua sendo o destravador —,
mas **a frase citável precisa vir com a regra de seleção ao lado.**

### 9.3 O painel tem 7.177.705 linhas; o §3.13 publica 6.787.589

O hash de `cvm_treino.duckdb` **não mudou** desde aquela data, então não é
mutação. A diferença é quase certamente o denominador (derivados incluídos ou
não, filtro de `tipo_periodo`), **mas eu não a reconciliei**. Enquanto não for,
a tabela do §3.13 não deve ser citada como contagem do painel de treino.

### 9.4 O sinal de monetariedade não foi validado contra gabarito

As 300 propostas foram conferidas por **inspeção minha** (LPA sai não monetário,
Ativo Total sai monetário, provisões pequenas saem `INDEFINIDA`). **Não há
conjunto anotado independente** contra o qual medir taxa de erro da proposta.
Isso é aceitável porque a proposta **não decide** — mas significa que
"291 monetárias" é uma **hipótese**, não uma medição.

### 9.5 Os períodos curtos seguem intocados

**16 linhas** de 12, 31, 38 e 41 dias, marcadas `trimestral`. Não são derivação:
são **colisão de trimestre fiscal na fonte**. Em **15 grupos** convivem com a
linha válida e em **12** o `max(valor_reais)` da carga **elege a curta**.
Contrato próprio, não feito.

### 9.6 O painel em disco continua defeituoso, e a etapa 10 depende dele

As **7.734 linhas** de derivação e as **33.655 linhas** dos 127 documentos de
escala continuam no `cvm_treino.duckdb`. A reconstrução única — derivação +
escala juntas — **exige decisão declarada de quebra de hash (§3.13)** e
**medição do efeito sobre a etapa 10**, sem presumir que toda métrica caiu nem
que nenhuma caiu. **Essa decisão não é minha e não foi tomada.**

### 9.7 A anotação humana é o gargalo real

`classe_confirmada` está **vazia nas 300 linhas**. Nenhuma correção de escala
pode referenciá-la antes disso. O trabalho concreto é conferir as **9** linhas
que não saíram "monetária" e amostrar o resto.

---

## 10. Onde estão os documentos

| Documento | Responde |
|---|---|
| [`revisao_rank03b_…_2026-09-12.md`](revisao_rank03b_consumo_operacional_2026-09-12.md) | O parecer independente que originou tudo isto |
| [`contratos_correcao_r1_r5_…`](contratos_correcao_r1_r5_rank03b_2026-09-12.md) | O que eu me comprometi a fazer **antes** de tocar no código |
| [`implementacao_r1_r5_…`](implementacao_r1_r5_rank03b_2026-09-12.md) | O que fiz, a emenda declarada, a auditoria dos testes, 7 condições de falsificação |
| [`contratos_correcao_derivacao_…`](contratos_correcao_derivacao_intermediaria_2026-09-12.md) · [`correcao_derivacao_…`](correcao_derivacao_intermediaria_2026-09-12.md) | A derivação: defeito, banda, alternativas rejeitadas, o que **não** foi feito |
| [`inventario_escala_cvm_2026-09-12.md`](inventario_escala_cvm_2026-09-12.md) | O inventário (§1–§8) **e a retratação** (§9) |
| `scripts/esqueleto_plano_padrao.py` (docstring) | A onda 4 inteira — inclusive o sinal descartado e a correção ao §3.8 |
| `artefatos/rank03b/auditoria.json` | A cadeia publicada: **só `G0`**, reprovado |
| `artefatos/escala_cvm/{inventario.jsonl,resumo.json}` | 34.952 casos com evidência por declaração |
| `corpus/cvm/plano_padrao_contas.csv` | As 300 contas aguardando anotação |

---

## 11. O que este dossiê não cobre

- **A terceira onda do B-DFC-01J** (R-C5/R-C6/R-SUPORTE) segue sem conferência
  independente. É outro candidato e outra tarefa.
- **F3** — o redesenho do cálculo de poder do B-DFC-01J — segue em quarentena.
- **Nada aqui reabre o Rank 3-B.** O veredito é `REPROVADO EM G0`, o pré-registro
  está consumido, e corrigir instrumento e dado **não** é evidência sobre o alvo.
