# Lote B — viabilidade dos dados do Rank 3-B (D2–D5)

**Data:** 2026-09-16. **Contrato:** [contratos do lote B](contratos_lote_b_rank03b_2026-09-16.md),
com a ressalva RA1–RA6 escrita antes da segunda execução do piloto.
**Origem:** [levantamento de desbloqueio](pendencias_desbloqueio_treino_dfc_2026-09-15.md), §3 D2–D5 e §6.

**Não é treino nem medição do alvo.** Nenhuma taxa de evento, soma de semestres
futuros, T1, T2, AUC ou baseline foi calculada sobre dado real **neste lote**
(cláusula O1). Uma taxa de evento **de 15/09**, anterior ao lote, está
declarada na ressalva RA7 do contrato e no §11 do pré-registro v2.
`cvm.duckdb` e `cvm_treino.duckdb` foram abertos só para leitura.

**Resposta curta:** existe rota de dados defensável. A fonte primária é legível
nos dois formatos da CVM, a escala pode ser adjudicada com evidência escrita pela
própria companhia, a identidade temporal por datas elimina o defeito de duração,
e a disponibilidade pode ser tratada sem vazamento com perda medida. O piloto
passou nos três critérios fixados antes dele, e a extensão foi autorizada pelo
próprio contrato.

---

## 1. D2 — as identidades contábeis que o candidato usa

Medido nos 31 ZIPs pinados, consolidado, 700 companhias do universo:

| Fato | Medido | Leitura |
|---|---|---|
| `6.01` é conta fixa | `ST_CONTA_FIXA = 'S'` em 45.045/45.045 | Identidade por código **evidenciada** para esta conta — não é junção universal por código (RN09) |
| Descrições de `6.01` | "Caixa Líquido Atividades Operacionais" (**todas as 700** cias, 22.516 linhas) e "…**Seguradora/Resseguradora**" (2 dessas cias, 24 linhas) | **Seguradoras dentro do universo "não financeiro"** |
| Plano `ll3_13` | 3 companhias, entre elas BB Seguridade e IRB | Exclusão proposta no rascunho do pré-registro v2 |
| `1` e `2` | "Ativo Total" e "Passivo Total", fixas | Ativo = Passivo como verificação |
| Ativo ≠ Passivo | 6 documentos | Defeito de valor, publicado |
| Ativo ≤ 1 | 35 documentos (32 zerados, 3 em (0, 1]) | Placeholder: regra A2 no lote C |
| Identidade de caixa da DFC | 23 somas e 14 saldos que não fecham, em 22.483 períodos | Verificação disponível |
| Métodos | nenhum documento com `DFC_MD` e `DFC_MI`; **53 companhias trocam** | O FCO total não depende do método (CPC 03) |

**Conferência do painel compartilhado contra a fonte.** As linhas `ÚLTIMO` da
fonte e as linhas arquivadas do `cvm_treino.duckdb` coincidem, exceto por:

- **60 linhas duplicadas na própria fonte**, por conta (a mesma linha repetida
  no CSV da CVM);
- **períodos declarados por ITR e DFP ao mesmo tempo** — 9 no FCO e 11 no
  ativo —, dos quais o painel compartilhado guarda um só documento;
- **4 períodos de exercício de transição que o painel compartilhado descarta** —
  dois de 15 meses (`003336`, `021709`), um de 366 dias começando no dia 31
  (`025496`) e um "exercício" de **um dia** (`080187`, 01/01/2019).

Nenhuma linha do painel compartilhado está ausente da fonte.

## 2. Dois formatos de fonte

| Formato | Quando | Estrutura | Armadilhas |
|---|---|---|---|
| Formulário `.itr`/`.dfp` | 2011 até pelo menos o 1T2021 | ZIP dentro do ZIP; `InfoFinaDFin.xml` | Consolidado e individual no mesmo XML; `ValorConta{N}` é o período N, não a N-ésima data |
| **XML único** | a partir de 2021, convivendo com o anterior no mesmo ano | `025704ITR30-09-2024v1.xml` | Valores em texto pt-BR; colunas nomeadas por papel; datas num cabeçalho; o acumulado anterior do ITR não tem data própria |

A escolha é pelo **conteúdo** do pacote. O pacote traz ainda um PDF renderizado
que o servidor corta em exatamente **8 MiB** (duas vezes observado); nada
depende dele. O servidor também respondeu `HTTP 200` com 40 bytes —
*"There is not enough space on the disk."* —, rejeitado como falha de
transporte.

**Vazão:** 12 a 45 s por documento, **observada** durante o piloto, e não
gravada em artefato. O manifesto de aquisição guarda só a data de início de
cada download. É o que tornou necessário o escopo por trecho (RA4).

## 3. Piloto — segunda execução

58 documentos em 10 estratos, escolhidos pelo hash da identidade do documento,
um por companhia por estrato. A primeira execução foi interrompida depois de 3
documentos pelo formato novo e por transferências paradas; ver §7.

### 3.1 Critérios P1.3, fixados antes

| Critério | Limiar | Medido | |
|---|---|---|---|
| c1 download íntegro | ≥ 90% | **58/58** | ✅ |
| c2 parser idêntico ao ZIP (versão máxima) | 100% | **50/50 documentos** | ✅ |
| c3 evidência de unidade em E1–E4 | ≥ 70% | **95,65%** | ✅ |

`CodigoEscalaMoeda`: **1 → `UNIDADE` (17), 2 → `MIL` (33)**, sem exceção.
Formatos: 36 formulários, 22 XML únicos.

> **⚠️ Ressalva posterior (2026-09-16, lote C, RC1 e RC1-bis).** As classes de
> cabeçalho desta seção foram medidas com o vocabulário **v1**, que a adjudicação
> mostrou defeituoso: não cobria "express**as**" e aceitava a frase em qualquer
> ponto das notas. Pior: **"em reais" declara a moeda** (parágrafo de moeda
> funcional) e aparece em rodapés por ação — **não é evidência de escala**. Os
> pares `UNIDADE|…` abaixo não provam que um formulário esteja em reais; o de
> `023426` na §3.3 se apoiava só em *"prejuízo por ação básico (em reais)"*.
> Pela regra final, só o cabeçalho **de milhares** decide. Ver o
> [relatório do lote C](painel_pesquisa_rank03b_lote_c_2026-09-16.md) §3.

### 3.2 Evidência nas notas (medida da RA3)

Par *cabeçalho das notas | números do formulário nas notas*:

| Estrato | Pares |
|---|---|
| E1 fronteira `UNIDADE` | MIL\|bruto 4 · UNIDADE\|bruto 1 · contraditório\|bruto 1 |
| E2 fronteira `MIL` | MIL\|bruto 6 |
| E3 interior de mista | MIL\|bruto 4 · UNIDADE\|bruto 1 · contraditório\|bruto 1 |
| E4 só `UNIDADE` | UNIDADE\|bruto 3 · ausente\|conflitante 1 · ausente\|nenhum 1 |
| E5 só `MIL` (controle) | MIL\|bruto 3 · MIL\|nenhum 1 · contraditório\|bruto 1 |
| E10 trechos completos | MIL\|bruto 6 · UNIDADE\|bruto 3 |

Leitura: **4 dos 6 documentos de fronteira declarados `UNIDADE` têm notas em
milhares e os números brutos do formulário impressos nelas** — é o erro de
rótulo que o G0.3 flagra. `dividido` e `multiplicado` só apareceram **dentro**
de pares `conflitante`, nunca como classe única: no piloto, nenhum formulário
estava comprovadamente numa unidade diferente das próprias notas. Nos estratos
E1–E4, 4 de 23 documentos caem fora da tabela S2 (cabeçalho contraditório ou
ausente) — estimativa de **~17% de pontas indecidíveis**. *(Medido depois, com
a regra final do lote C: **128 de 341 pontas, 37,5%**, em
`adjudicacao/evidencias.jsonl`. A estimativa foi otimista porque o vocabulário
v1 contava "em reais" como evidência, e a regra final não conta.)*

### 3.3 A premissa da herança (E10)

Três trechos completos, todos com veredito decidido em cada documento:

| Companhia | Trecho | Declarado | Evidência | Escala do formulário |
|---|---|---|---|---|
| `003549` | 1T–3T2022 | `UNIDADE` ×3 | MIL\|bruto ×3 | **`MIL` ×3** |
| `023604` | 4T2016–2T2017 | `UNIDADE` ×3 | MIL\|bruto ×3 | **`MIL` ×3** |
| `023426` | 1T–3T2024 | `UNIDADE` ×3 | UNIDADE\|bruto ×3 | `UNIDADE` ×3 |

**Nenhum interior discordou das pontas** → pela regra S5, **a herança está
permitida**. O teste é pequeno — três trechos de três documentos — e é o que o
contrato fixou; um teste maior não foi feito. *(Reavaliado no lote C com a
regra final: `023426` deixou de ser testável; ficam **2 trechos testados**.)*

### 3.4 Versões (E7)

Os 8 pares v1/versão máxima foram recuperados e lidos. **Desvio de P1.2:** o
contrato pedia a v1 comparada com o `PENÚLTIMO` posterior; foi medida a v1
contra a versão máxima (RA7). Em **3 dos 8**, a v1
difere da versão final (11, 14 e 16 de 20 valores iguais). Reapresentação é
comum, e usar a versão final antes da data dela seria vazamento.

## 4. D3 — escala

**O formulário não adjudica**: `CodigoEscalaMoeda` é a origem do rótulo do CSV.
**O texto da companhia adjudica**: cabeçalho das notas (grupos 193 no ITR, 412
na DFP) **e** os números do formulário impressos nesse texto. A regra está
congelada na [parte 2 do contrato do lote C](contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md)
(S1–S10) **antes** de rodar sobre a extensão.

Escopo medido: 54 companhias mistas (1.683 documentos em 189 trechos, 71 de um
documento só) e 17 só `UNIDADE` (400 documentos). Por trecho: **307 + 34
pontas** e 30 controles só `MIL`. Os três componentes de T1 em reais tornam o
erro consistente relevante; é por isso que as só `UNIDADE` entram.

## 5. D4 — períodos e identidade da derivação

Com **identidade por datas** (contrato do lote C, T1–T3) e o método fora da
chave:

| Estado | Linhas | Companhias |
|---|---:|---:|
| **válido** | **22.088** | 691 |
| primeiro período não trimestral | 371 | 327 |
| lacuna | 11 | 11 |
| curto | 1 | 1 |
| ambíguo (colisão de rótulo) | 0 | 0 |

- **N3 dissolvido:** com a data como chave, **nenhuma** colisão de rótulo entre
  trimestres válidos. Os 24 trimestres sobrepostos entre exercícios da mesma
  companhia ficam na série com rótulos distintos; uma janela que os atravesse
  só é aceita se as datas encadearem (H1.2/H1.3).
- **N2 explicado, medido** (`medicoes_estruturais.json`,
  `n2_no_recorte_do_candidato`): dos **131 grupos N2** do recorte do
  levantamento (94 companhias, reproduzidos), **60 têm o antecedente no outro método** — o
  pareamento por demonstrativo os fabricava, e aqui eles viram trimestres
  válidos —, **0** vêm de deriva de descrição (a `6.01` tem uma descrição só) e
  **71 não têm antecedente algum** no exercício, e viram *primeiro período não
  trimestral* ou *lacuna*.
- **Os 16 curtos e os 15 grupos mistos** deixam de ser linhas trimestrais: o
  trimestre válido tem suas próprias datas, e o período curto é perda
  inventariada.
- **117 trimestres** combinam acumulados de métodos diferentes (legítimo) e
  **83** combinam **escalas declaradas diferentes** (motivo do G0.5 proposto).
- **308 perdas** seriam fechadas por um `PENÚLTIMO`; a regra F6 proíbe usá-lo
  (mistura *as-reported* com *as-restated*). Contado, não feito.

## 6. D5 — disponibilidade

- **3.863 de 24.925** documentos do universo têm mais de uma versão; o número
  em mãos é **sempre** o da maior (100%). Intervalo entre a primeira e a última
  versão: mediana 7, p90 260, máximo 2.093 dias.
- **Política adotada (P1):** o número só vale a partir da recepção da versão
  que o carrega; num derivado, a mais tardia entre os operandos. Não vaza.
- **Custo medido (P2):** **3.082** trimestres válidos têm intervalo cego, e
  **6.735** datas de decisão da mesma companhia caem dentro de algum deles.
- **Recuperação:** 8 de 8 v1 recuperadas no piloto. A recuperação completa
  custaria **4.134 versões** (~23 h) e fica fora deste lote, com o inventário de
  perda publicado — o que o levantamento admite.
  *(Correção da revisão final: o artefato de medições conta **4.740** versões
  anteriores à máxima no cadastro dos ZIPs — soma de n − 1 por documento. O
  4.134 veio de uma contagem anterior sem artefato e sem definição
  registrada; vale o 4.740, e a estimativa de tempo cresce na mesma
  proporção.)*

## 7. Erros e desvios meus neste lote

1. **Primeira execução do piloto interrompida** por dois defeitos do meu
   downloader: não reconhecia o XML único e esperava até 5 min por transferência
   parada. Corrigidos, com ressalva no contrato, e o piloto foi **refeito
   inteiro**.
2. **Imprimi dois valores de FCO acumulado** de uma companhia (`025704`,
   3T2024) ao estudar o XML único — O1.3 proíbe. Sem rótulo, sem semestre
   futuro, sem agregação.
3. **Um teste executou o `curl` real** uma vez: um argumento padrão
   `executar=subprocess.run` era resolvido na definição e escapava do dublê.
   Corrigido; o arquivo de testes agora proíbe processo real.
4. **`pkill -f` casou com o próprio shell** e o derrubou. Sem efeito em arquivo.
5. **A promoção de pacotes "não reconhecidos"** não gravava linha no manifesto;
   corrigido, e as três promoções da segunda execução foram **reconciliadas por
   linhas novas**, sem apagar as antigas.
6. **Duas asserções frouxas que eu mesmo escrevi** (`… or …`) foram apertadas;
   e a coluna do rótulo do trimestre se chamava `rotulo`, nome proibido por O1 —
   a guarda pegou, e a coluna virou `trimestre`.
7. **O extrator quebraria com célula vazia**, o que impediria o G0.4 de contar
   nulos; passou a guardar nulo como nulo, antes de existir o construtor.
8. **Declarados depois, pela auditoria (RA7 do contrato):** o downloader não
   pausava entre documentos (V1.1); a extensão usou três conexões; E7 mediu
   v1 × versão máxima em vez de v1 × `PENÚLTIMO` posterior; o
   `piloto/resultado.json` não registra o hash do código; e a declaração O1
   omitia a taxa de evento de 15/09.

## 8. Procedência

| Artefato | Onde |
|---|---|
| Manifesto de aquisição | `artefatos/painel_pesquisa_rank03b/rad/manifesto_aquisicao.jsonl` |
| Pacotes (fora do Git) | `artefatos/painel_pesquisa_rank03b/rad/brutos/` |
| Resultado do piloto | `artefatos/painel_pesquisa_rank03b/piloto/resultado.json` e `evidencias.jsonl` |
| Código | `scripts/fonte_zip_cvm.py`, `scripts/fonte_rad_cvm.py`, `scripts/piloto_fonte_rad_rank03b.py` |
| Testes | `tests/test_fonte_zip_cvm.py`, `tests/test_fonte_rad_cvm.py`, `tests/test_piloto_fonte_rad_rank03b.py` |

As medições estruturais deste relatório (§1, §5 e §6) são reproduzidas por
`scripts/medicoes_estruturais_rank03b.py` →
`artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json`, que registra o
hash do código e dos ZIPs.

Os 31 ZIPs são conferidos contra `corpus/cvm/manifesto_cvm.csv` a cada
extração; `cvm.duckdb` (`43e31d9f…`) e `cvm_treino.duckdb` (`c1a60445…`) não
mudaram.
