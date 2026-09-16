# Lote C — painel de pesquisa do Rank 3-B e G0/G1

**Data:** 2026-09-16.
**Contrato:** [lote C](contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md) — parte 1
(construção) escrita antes do construtor; parte 2 (escala) escrita antes do
resultado do piloto e antes do código de adjudicação.
**Antecedente:** [lote B](viabilidade_dados_rank03b_lote_b_2026-09-16.md).
**Decisões do responsável:** painel separado; download público autorizado com
piloto antes; parar no rascunho do pré-registro.

**Não mede o alvo.** Nenhuma taxa de evento, T1, T2 ou baseline. Todo artefato
é conferido contra as chaves proibidas de O1. **Correção da auditoria (§8):**
até a correção A1, o G1 montava a amostra calculando `S1`, `S2` e `y` em
memória (e só depois apagava `y`), e publicava a contagem de descartes por
`FCO_TTM ≤ 0`. Desde a A1 o rótulo não é calculado e a contagem sai omitida.

**Veredito estrutural: G0 e G1 APROVADOS no painel de pesquisa**, com 101
correções de escala feitas com fonte. G0.3 = **47 saltos (0,2092%)**, contra
132 (0,5875%) sem correção e limite de 0,5%; G1 = **10.750 observações em 502
companhias**, zero violações. **Isto não é aprovação do alvo** — é a condição
para medi-lo. O pré-registro v2 está em
[rascunho](pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md) e **aguarda
aprovação**; nenhum T1, T2 ou baseline foi medido.

**A regra de escala mudou uma vez, antes de qualquer G0 com correções, por um
defeito que eu achei nela** (§3.2). Com a regra da primeira execução o G0
também aprovaria (61 saltos, 0,2715%): a mudança não foi o que fez o G0
passar.

---

## 1. O painel

Construído por `scripts/painel_pesquisa_rank03b.py` a partir dos 31 ZIPs
pinados — nunca do painel compartilhado, do qual só a tabela `companhias` é
lida (somente leitura). Três decisões resolvem o que o painel compartilhado não
resolvia:

1. **Período por datas, rótulo derivado.** A coluna `trimestre` é o trimestre
   civil de `dt_fim`; colisão entre válidos não se desempata.
2. **Método fora da identidade.** O FCO total não depende do método.
3. **Disponibilidade conservadora.** O número vale a partir da recepção da
   versão que o carrega; num derivado, da mais tardia entre os operandos.

### 1.1 Estados

| FCO trimestral | Linhas | Companhias |
|---|---:|---:|
| **válido** | **22.088** | 691 |
| primeiro período não trimestral | 371 | 327 |
| lacuna | 11 | 11 |
| curto | 1 | 1 |
| conflito · valor nulo · operando indisponível · ambíguo | 0 | 0 |

| Ativo total | Linhas | Companhias |
|---|---:|---:|
| **válido** | **22.469** | 700 |
| não informativo (A2) | 3 | 2 |
| conflito de declarações | 1 | 1 |
| ambíguo | 2 | 1 |

### 1.2 Custos medidos

- **Disponibilidade (P2):** 3.082 trimestres válidos têm intervalo cego;
  6.735 datas de decisão da mesma companhia caem dentro de algum deles.
- **Vintage na subtração (F6):** 2.762 períodos existem só como `PENÚLTIMO`;
  308 perdas seriam fechadas por eles. Não foram usados.
- **N2 do painel compartilhado, no recorte do candidato (131 grupos, 94
  companhias):** 60 recuperados (antecedente em outro método), 71 sem
  antecedente algum (`medicoes_estruturais.json`, `n2_no_recorte_do_candidato`).

### 1.3 Reprodutibilidade e falsificação

Duas construções independentes sobre o dado real: **digest idêntico**
(`08fffc8b…`, sem correções; era `d5499b22…` antes de a coluna `plano_contas`
entrar nas linhas, §8), em `medicoes_estruturais.json`, `reprodutibilidade`. Reordenar a entrada não muda o digest (teste).
As condições de falsificação 1–5 e 8 da parte 1 são verificadas **a cada
execução** sobre o painel real e derrubam a execução se violadas; no dado real,
todas dão zero.

## 2. Linha de base estrutural, sem correção de escala

| | Painel compartilhado | Painel de pesquisa |
|---|---:|---:|
| G0.1 métodos somados | 0 | 0 |
| G0.2 fora da banda | 25 | **0** |
| G0.3 saltos | 132 (0,5874%) | 132 (0,5875%) |
| G0.4 nulos | 0 | 0 |
| G1 | 10.605 obs · 494 cias | **10.748 obs · 502 cias** · 0 violações |

**G0 dependia só da escala.** O limite de 0,5% admite no máximo 112 saltos. Por
isso a regra de adjudicação foi **congelada antes** de rodar sobre a extensão.

## 3. Adjudicação de escala

### 3.1 Aquisição

371 documentos do escopo S4 (135 trechos com duas pontas, 71 trechos de um
documento, 30 controles só `MIL`) mais os 34 documentos do piloto fora dele:
**405, todos íntegros** — 413 pacotes em disco, 2,8 GB, fora do Git, com
SHA-256 no manifesto de aquisição. Três conexões paralelas, cada uma com sessão
própria, **sem pausa entre documentos** — desvio de V1.1 do lote B, declarado
na ressalva RA7 de lá.

### 3.2 O defeito da primeira execução, e a regra final

A primeira execução (código `6d100e4b…`) produziu 109 correções. Ao ler o
resultado, **antes** de construir o painel com elas, os dois controles só `MIL`
"corrigidos" eram **falsos positivos**:

- a BRF declara *"estão **expressas** em milhares de reais"* — o padrão só
  cobria `expressos?`;
- o único "cabeçalho em reais" dos dois era um **rodapé por ação**: *"(1)
  valores expressos em reais"*, *"dividendos por ação (valores expressos em
  reais)"*.

A primeira correção (RC1: flexões + só frases no título da página ou que falem
das demonstrações) foi **testada na amostra de desenho antes de rodar** e
refutada pela própria condição que declarou: o rodapé da TIM caía no título da
página, e *"as demonstrações financeiras são **apresentadas em reais**"* — o
parágrafo de **moeda funcional** — tornava contraditório um cabeçalho de
milhares verdadeiro em 5 documentos.

**Leitura que ficou:** "em reais" declara a **moeda**, não a **escala**.
Nenhuma frase de cabeçalho prova, sozinha, que um formulário está em unidades.
A regra final (RC1-bis) é assimétrica:

| Cabeçalho de milhares nas notas | Números do formulário nas notas | Escala |
|---|---|---|
| presente | como estão | `MIL` |
| presente | divididos por mil | `UNIDADE` |
| qualquer outro caso | — | indecidível |

**Verificada antes de rodar** na amostra de desenho: nos documentos do piloto
dos estratos E1–E4, e nos dois documentos que expuseram o defeito (BRF
confirmada em `MIL`; TIM indecidível) — resultado em §8.3.

Rodou **uma vez** (código `042e7bcd…`), e é a governante. A primeira execução
está preservada em `adjudicacao/execucao1/`, com hashes. **Desenho e
avaliação se sobrepõem** (a amostra de desenho está no escopo), e a regra foi
escrita depois de ver a saída da execução 1 — declarado em §8.

### 3.3 Resultado

| Declarada | Confirmada | Corrigida | Indecidível |
|---|---:|---:|---:|
| `MIL` | 172 | 0 | 69 |
| `UNIDADE` | 2 | **77** | 85 |

Por perfil: pontas de companhias mistas 137 / **72** / 98; só `UNIDADE` 1 /
**3** / 30; controles só `MIL` 19 / 0 / 11. **Nenhum controle corrigido, mas
isso é evidência fraca:** pela regra final, um formulário rotulado `MIL` só pode
ser corrigido no caso raro de notas em milhares com valores divididos por mil.
Erro consistente do tipo "rotulado `MIL`, na verdade em reais" praticamente não
é detectável por ela, e não se pode afirmar que não exista.

Motivos de indecisão: 62 sem cabeçalho de milhares mas com os números brutos
nas notas; 35 com cabeçalho e sem números impressos; 32 sem nenhum dos dois;
25 com evidência numérica conflitante.

**Premissa da herança (S5)**, reavaliada com a regra final: 2 trechos
completos testados (`003549`, `023604`), nenhum discordante; `023426` deixou de
ser testável (sua única "evidência de reais" era o rodapé por ação). Herança
permitida: **772 interiores confirmados e 24 corrigidos**.

**Manifesto final:** `corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv`,
**101 linhas em 32 companhias**, todas `UNIDADE → MIL`: 77 por documento
(cabeçalho de milhares + números brutos, com trecho literal, anexo e página) e
24 por herança (com as duas pontas e seus pacotes). A validação do manifesto
(condições 11, 12 e 14) roda antes de gravar.

**Limite honesto:** a regra não consegue **confirmar** formulário em reais a
não ser pelo caso raro de notas em milhares com valores divididos (2 casos).
Documento realmente em reais fica indecidível e mantém o rótulo declarado — o
que é correto para ele, mas significa que o painel não **prova** a escala das
companhias só `UNIDADE`.

## 4. G0 e G1 com as correções

| | Sem correção | Execução 1 (descartada) | **Execução 2 (governante)** |
|---|---:|---:|---:|
| Correções aplicadas | 0 | 109 | **101** |
| G0.3 saltos | 132 (0,5875%) ❌ | 61 (0,2715%) | **47 (0,2092%)** ✅ |
| G0.1 · G0.2 · G0.4 · unicidade | 0 | 0 | **0** |
| G1 | 10.748 · 502 | 10.749 · 502 | **10.750 obs · 502 cias** ✅ |
| Digest do painel | `08fffc8b…` | — | **`f9cb9da9…`** |

Os digests mudaram depois da primeira versão deste relatório (`d5499b22…` e
`ec036d53…`) porque a coluna `plano_contas` passou a ir para as linhas; os
valores são os mesmos (§8). Duas construções independentes com as correções:
**digest idêntico** (`medicoes_estruturais.json`). As condições de
falsificação 1–5 e 8 dão zero, inclusive as novas checagens por linha.

**Diagnósticos declarados, que não governam:**

- **A2:** incluindo os 3 ativos não informativos, G0.3 seria 49 saltos
  (0,218%) — também aprovado. A regra A2 não é o que faz G0 passar.
- **Ativos em conflito ou ambíguos** (3), que ficam fora da série: incluídos,
  G0.3 seria 49 saltos — também aprovado.
- **G0.5 proposto:** 82 trimestres válidos combinam escalas declaradas
  diferentes; 38 com operando sem veredito — **0,172%**.
- **G0.1 lido literalmente:** 117 trimestres válidos em 49 companhias são
  derivados de acumulados de métodos diferentes. A leitura por unicidade dá
  zero. **Qual leitura vale é decisão do pré-registro v2 (§5.1)**; pela
  literal, G0 reprova.

**Os 47 saltos que restam** (25 companhias):

| Natureza | Saltos |
|---|---:|
| Rótulo diferente, valor bruto contínuo, algum documento indecidível | 32 |
| Mesmo rótulo, valor bruto salta (evento de valor, não de rótulo) | 10 |
| **Criados pela correção parcial**: documento corrigido para `MIL` ao lado de um vizinho do mesmo rótulo sem evidência | 4 |
| Rótulo diferente, valor bruto salta | 1 |

Os 4 da terceira linha são o custo declarado de corrigir só o que tem fonte.
Nenhum documento foi removido para reduzir a contagem.

O painel compartilhado **não mudou** e continua reprovando G0 como antes.

## 5. Pontos de julgamento

| Decisão | Por quê | Como refutar |
|---|---|---|
| Rótulo civil de `dt_fim` | Dissolve a colisão N3 sem desempate arbitrário | Mostrar trimestre de 80–100 dias cujo rótulo civil quebre a contiguidade de uma série válida |
| Método fora da identidade | CPC 03: o caixa operacional é o mesmo | Mostrar companhia cujo FCO total difira entre métodos no mesmo período |
| Disponibilidade pela versão numérica | Só o número da versão máxima está em mãos | Mostrar que a versão máxima estava disponível antes da sua recepção |
| Não usar `PENÚLTIMO` como antecedente | Mistura vintages numa subtração | — |
| Valor não informativo (A2) | "1,0 mil reais" de Ativo Total não é balanço de companhia operacional, e a fonte não traz o valor certo | Mostrar companhia do universo com Ativo Total real ≤ R$ 1 mil |
| Documento não adjudicado fica com o rótulo declarado | Excluí-lo passaria G0.3 por remoção | — |
| Herança dentro do trecho | Premissa testada no E10 com a regra final (**2 trechos**, 0 discordâncias; 1 não testável) | Um trecho completo com interior de escala diferente das pontas |
| Exigir as duas evidências (cabeçalho **e** números) | Uma sozinha não separa as hipóteses | Documento em que as duas concordam e a escala está errada |
| G1 medido mesmo com G0 reprovado | Diagnóstico estrutural, sem rótulo (desde a A1; antes, o rótulo era calculado em memória) | — |
| G0.1 como unicidade | Nenhum documento soma os dois métodos | **Em decisão** (v2 §5.1): a leitura literal conta 117 |

## 6. Erros e desvios meus neste lote

1. **Um parâmetro sombreado** no leitor de anexos (`grupos` reutilizado como
   dicionário de saída) faria a leitura restrita às notas pular **todos** os
   anexos. Pego na revisão antes de qualquer execução, com teste.
2. **Um teste meu aceitava G1 reprovado** num painel limpo
   (`is None or == "G1"`); apertado.
3. **A violação "documento excluído" saía como `KeyError`**, por acaso; virou
   violação nomeada.
4. **O teste de "subtração entre exercícios" aceitava `KeyError`**; apertado.

5. **A regra de escala da primeira execução estava errada em dois pontos**
   (flexão; rodapé e moeda tomados por cabeçalho), e a primeira correção que
   escrevi também — refutada na amostra de desenho antes de rodar. Tudo
   registrado como RC1 e RC1-bis no contrato.
6. **Classifiquei `023426` como "confirmado em reais" no relatório do lote B**
   com base num rodapé por ação. Ressalva datada lá.
7. **Editei a CLI do executor depois da medição governante**; a medição foi
   refeita com o código final para que o hash registrado bata (§7).
8. **Os 4 saltos criados pela correção parcial** não foram previstos no
   contrato. Ficam como estão e declarados.

## 7. Procedência

Hashes **depois da auditoria** (§8). Os da primeira versão deste relatório
ficam na última coluna, para quem os tiver citado.

| Artefato | SHA-256 atual | Antes da auditoria |
|---|---|---|
| Manifesto de correções (governante) | **`4735fb107cce…`** | `6e2c86a1291d…` (mesmas 101 decisões, §8.2) |
| Manifesto de correções, execução 1 | `95d86cc68265…` (em `adjudicacao/execucao1/`) | igual |
| Código da adjudicação que **produziu** a execução 2 | `042e7bcdf99c…` | igual |
| Código da adjudicação atual (reproduz a execução 2, §8.2) | `e637ba9494dd…` | — |
| `fonte_rad_cvm.py` atual (com a máscara de §8.6) | `66786a03adc9…` | `78e418ffc50c…` na reexecução |
| Código do construtor | `f1b30744b45c…` | `bb232ab84f77…` |
| Código do executor dos gates | `cb90fbf5052b…` | `08e6779e8764…` |
| Código do auditor (G0/G1) | `d7319dd6ff31…` | `3e771b33…` |
| Digest de conteúdo do painel, com correções | **`f9cb9da9d586…`** | `ec036d53a5f9…` |
| Digest de conteúdo do painel, sem correções | `08fffc8b1c43…` | `d5499b22…` |
| `gates_g0_g1.json` (governante) | `f27cfd18a9ef…` | `a0ce6ab90fa0…` |
| `manifesto_painel.json` | `4b5e94926a3c…` | `54ac88fb2f3a…` (sobrescrito depois pelo da variante sem correções, §8.1) |
| `medicoes_estruturais.json` | `94031d0d08a7…` | não existia |
| `verificacoes_revisao_final.json` | ver §8.2–8.6 | não existia |
| `cvm.duckdb` · `cvm_treino.duckdb` | `43e31d9f…` · `c1a60445…` — inalterados | igual |
| Pré-registro de 11/09 | `fbae30cc…` — inalterado | igual |

Artefatos em `artefatos/painel_pesquisa_rank03b/`: `gates_g0_g1.json`
(governante), `gates_g0_g1_sem_correcoes.json`,
`gates_g0_g1_diagnostico_execucao1.json`, `painel.duckdb` +
`manifesto_painel.json`, `painel_sem_correcoes.duckdb` +
`manifesto_painel_sem_correcoes.json`, `medicoes_estruturais.json`,
`adjudicacao/` e `piloto/`. Cada artefato de gate registra os hashes do código
que o produziu.

## 8. Auditoria de conformidade e revisão final

A auditoria (somente leitura) rodou depois da execução 2 e da medição
governante. **Nenhuma decisão de escala e nenhum veredito de G0/G1 mudou.** A
lista completa, com o que foi feito em cada achado, está na
[ressalva RC2 do contrato](contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md);
aqui fica o que muda a leitura deste relatório.

### 8.1 O que estava errado

- **A1 — rótulo em memória.** O G1 calculava `S1`, `S2` e `y` para contar
  observações e publicava os descartes por `FCO_TTM ≤ 0`. Corrigido; o
  pré-registro v2 (§11) declara o que foi visto.
- **M1/M2 — o manifesto só era validado por quem o grava.** O construtor agora
  valida ao ler e confere o SHA de cada pacote; a herança passou a exigir
  pontas **de mesma escala**, registradas no manifesto.
- **M5 — G0.1.** A leitura por unicidade foi adotada sem decisão; a literal
  reprova (117 trimestres, 49 companhias). Vai para o v2 (§5.1).
- **M6 — desenho × avaliação.** A regra final foi escrita depois de ver a
  execução 1, e a amostra de desenho está dentro do escopo. Sem correção
  possível; declarado.
- **Manifesto de painel compartilhado** (revisão final): as duas variantes
  gravavam `manifesto_painel.json`, e a sem correções, rodada depois,
  deixava o manifesto errado ao lado do painel governante. Agora cada painel
  tem o seu; teste novo.
- **Textos:** "3 trechos" na §5 (são 2); RC1 cita 9 correções (eram 13 linhas);
  A2 do contrato se contradiz; `resumo.json` com chave duplicada.
- **Digests:** mudaram porque `plano_contas` passou a ir para as linhas; os
  valores não mudaram (os G0/G1 dão os mesmos números).

### 8.2 Reprodução da adjudicação com o código atual

O código da adjudicação mudou depois da execução 2 (validação, regravação,
chave duplicada). A adjudicação inteira foi **reexecutada com o código atual**,
com o download **bloqueado** (uma tentativa de baixar abortaria), num
diretório de rascunho, lendo os pacotes já em disco:

| | Resultado |
|---|---|
| Documentos com veredito, motivo, escala, evidência, cabeçalho, numérica ou SHA diferentes | **0 de 405** |
| `herdados.jsonl` | idêntico |
| Manifesto de correções | **idêntico byte a byte** (`4735fb107cce…`) |
| `resumo.json` (fora o SHA do manifesto) | idêntico |

Isto também confirma a regravação do manifesto (`6e2c86a1…` → `4735fb10…`):
a execução completa com o código atual produz exatamente o arquivo regravado.
A comparação está gravada em `artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json` (`reproducao_da_adjudicacao`, com os dois
SHA e o das evidências reproduzidas). **Ordem declarada:** a reexecução rodou
com a adjudicação `e637ba94…` e `fonte_rad_cvm.py` `78e418ff…`; **depois**
dela entrou a máscara de O1.3 (§8.6), que não muda nenhum trecho publicado.
Levou 16 minutos de relógio (133 de CPU), local, sem custo.

### 8.3 Amostra de desenho com a regra final

Documentos **vmax** do piloto, íntegros, com algum estrato E1–E4 (**23**),
em `artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json` (`amostra_de_desenho`):

| Declarada | Confirmada | Corrigida | Indecidível |
|---|---:|---:|---:|
| `MIL` | 11 | 0 | 1 |
| `UNIDADE` | 0 | 5 | 6 |

*(Correção da revisão final: uma versão anterior desta tabela dizia 29
documentos e `UNIDADE` 9/8 — misturava a linha `UNIDADE` dos 50 vmax do piloto
inteiro com a linha `MIL` dos E1–E4. O recálculo também pegou um defeito de
filtro: "E10" passava por "E1" quando se comparava só o prefixo.)*

BRF (`016292`, DFP 2022) **confirmada** em `MIL`; TIM (`017639`, 3T2017)
**indecidível** (sem cabeçalho de milhares, números brutos). Na extensão,
**128 de 341 pontas (37,5%)** ficaram indecidíveis — mais que os ~17%
estimados no lote B com o vocabulário v1.

### 8.4 Conferência pontual das correções com um único número bruto (B8)

7 correções têm só **um** valor do formulário encontrado nas notas. Conferidas
por continuidade do ativo bruto com vizinhos **declarados** `MIL` (±200 dias),
em `artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json` (`b8_correcoes_com_um_bruto`):

- **5 corroboradas** (`ESC-0009`, `0015`, `0032`, `0076`, `0078`; razões de
  0,90 a 1,65);
- **`ESC-0040`** (`022144`, 1T2011): os dois vizinhos são declarados `UNIDADE` e
  **também foram corrigidos** — a continuidade com eles é circular, não
  corrobora;
- **`ESC-0101`** (`027570`, 3T2025): o único vizinho é declarado `UNIDADE`, tem o
  mesmo bruto e ficou indecidível; é um dos 4 saltos criados por correção
  parcial.

As duas se apoiam só no cabeçalho (4 e 34 frases de milhares). **Mantidas**,
sem ajuste depois de ver o G0. *(Uma versão anterior dizia "6 corroboradas":
contei como `MIL` os vizinhos de `ESC-0040` pela escala **aplicada**.)*

### 8.6 Guarda de O1.3 no trecho publicado (achado da verificação)

O teste de O1.3 excluía da verificação justamente o campo `evidencia`, e nada
impedia um trecho literal de carregar um valor de caixa do formulário.
Acrescentada `mascarar_valores_de_caixa` (`fonte_rad_cvm.py`): qualquer valor
`6.x` do formulário com módulo ≥ 1.000, como está, ÷1.000 ou ×1.000, vira
`[valor de caixa omitido]` no trecho. O teste passou a verificar o resultado
inteiro. **Sobre os dados publicados a máscara não muda nada:** 0 de 251
trechos da adjudicação e 0 de 101 linhas do manifesto (`mascara_o1_3`). Abaixo
de 1.000 a guarda não atua (o número coincide com numeração de nota e página)
— limite declarado.

### 8.7 Pendências de baixa severidade, declaradas

- A validação do manifesto (M1) roda no caminho de linha de comando;
  `painel_pesquisa_rank03b.construir(con, correcoes)` e
  `gates_painel_pesquisa_rank03b.executar(correcoes, …)` chamados direto
  aplicam o dicionário que receberem.
- Em `identidades_contabeis`, ativo × passivo com passivo nulo não é contado
  (diagnóstico, não governa).
- A vazão "12 a 45 s por documento" (lote B) não tem artefato.
- O B0 do v2 exige acerto e cobertura **com IC**; o auditor atual não calcula
  IC para o B0. É requisito da extensão de T1/T2, a implementar **antes** de
  medir (v2 §14).

### 8.8 O que continua valendo sem mudança

G0 e G1 aprovados no painel governante; 47 saltos; 10.750 observações em 502
companhias; a execução 1 também aprovaria; nenhuma linha removida; painéis
compartilhados intactos. **Falta conferência independente dos lotes B e C.**
