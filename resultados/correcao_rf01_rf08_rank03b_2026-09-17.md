# Correções RF-01 a RF-08 — Rank 3-B, painel de pesquisa

**Data:** 2026-09-17. **Contratos:** [RF-01 a RF-08](contratos_correcao_rf01_rf08_rank03b_2026-09-17.md),
escritos antes da implementação. **Origem:** [conferência independente de 17/09](conferencia_pre_treino_rank03b_2026-09-17.md).

**Resumo.** A regra de escala foi refeita (evidência numérica localizada) e
reexecutada nos 405 documentos, com a rede bloqueada: **101 → 68 correções**.
Nenhuma escala decidida se inverteu, e ESC-0101 deixou de ser corrigida. A
disponibilidade passou a exigir a publicação da prova da escala, e o G1 confere
isso de forma independente: no manifesto antigo, acha exatamente as **cinco**
observações que a conferência apontou. No painel novo, **G0 e G1 continuam
aprovados**: G0.3 = **68 saltos (0,3026%)**, antes 47; G1 = **10.750
observações em 503 companhias**, G1.4 = 0.

**Não foi feito:** T1, T2, baseline ou treino sobre dado real; nenhuma
estatística de rótulo; nenhum download; nada escrito em `cvm.duckdb`,
`cvm_treino.duckdb` ou no holdout. **Continua em rascunho:** o pré-registro
v2, com cinco pontos [DECIDIR]. **Falta:** conferência independente desta onda.

---

## 1. RF-01 — adjudicação de escala, regra v3

### 1.1 O que mudou

`rad.evidencia_numerica_localizada` substitui a busca de magnitudes no texto
corrido. Um número só conta se: é valor **consolidado do período corrente**;
aparece numa **linha** com o **rótulo da conta** (vocabulário fechado E2) e sem
menção a ações; a **página** declara milhares; e não coincide, sob outro
multiplicador, com outro valor da mesma conta (qualquer período, consolidado ou
individual). Cada correção publica até cinco casamentos com conta, forma,
anexo, página e a linha. Linhas de conta `6.x` saem com **todos** os números
mascarados, e a máscara geral passou a cobrir também o FCO individual. O
manifesto ganhou a coluna `evidencia_numerica`, exigida pelo validador no
produtor e no consumidor.

**Declarado (E5):** a v3 foi escrita conhecendo ESC-0101 e as linhas casadas de
dois documentos corrigidos (`98645`, `97899`), inspecionadas só para saber se o
extrator mantém rótulo e número na mesma linha. Nessa inspeção apareceu uma
coincidência do tipo que a conferência descreve: "Obras por administração …
2.472" casava com um valor de FCO. Não é amostra fresca.

### 1.2 Execução 3

Rede bloqueada por `RAD_SEM_REDE=1`, que vale também nos processos filhos:
um pedido de download pararia a execução. 405/405 pacotes reaproveitados do
disco; o manifesto de aquisição não mudou (`36902f4c…`). A execução 2 está
preservada em `artefatos/painel_pesquisa_rank03b/adjudicacao/execucao2/`
(evidências, herdados, resumo, manifesto `4735fb10…` e o artefato de gates dela).
Hashes do código antes da execução: `adjudicacao/codigo_antes_da_execucao3.sha256`.

| | Execução 2 | **Execução 3** |
|---|---:|---:|
| Correções no manifesto | 101 | **68** |
| — por documento | 77 | **59** |
| — herdadas | 24 | **9** |
| Documentos confirmados / corrigidos / indecidíveis | 174 / 77 / 154 | **108 / 59 / 238** |
| Trechos em que a premissa de herança foi testada | 2 | **1** (`003549`) |
| Manifesto de correções | `4735fb107cce…` | **`6330d78d02df…`** |

**Transições documento a documento (405):** 103 confirmadas e 53 corrigidas
continuaram iguais; **71 confirmadas e 24 corrigidas viraram indecidíveis**;
**5 indecidíveis viraram confirmadas e 6 viraram corrigidas**; 143 continuaram
indecidíveis. **Nenhuma escala decidida nas duas execuções se inverteu.**
Todas as 68 correções são `UNIDADE → MIL`.

**No manifesto:** 62 correções ficaram, com a mesma escala; **39 saíram** (24
por documento que ficou indecidível, 15 herdadas cujas pontas ficaram
indecidíveis ou cujo trecho deixou de ser testável); **6 entraram**
(`023868` DFP 2018 v2 e 2021, `025461` 1T2026, `022144` DFP 2013, `027430` DFP
2022, `024716` DFP 2018), todas indecidíveis na execução 2.

**Onde a v3 é mais permissiva que a v2 (auditoria de 17/09, B4).** As 11
decisões novas (6 corrigidas e 5 confirmadas) eram **`MIL|conflitante`** na
execução 2. A v3 descarta o lado que não é localizado e decide. O auditor
inspecionou três das seis correções novas (`022144` DFP 2013 e `023868` DFP
2018 e 2021): nelas o "dividido" descartado vinha de coincidências com valores
comparativos em linhas de outra conta ("veículos 20% 2.540", "trabalhista (a)
1.492", "outros (iii) 1.765"). As outras três não foram inspecionadas.

**E5 (critério de parada), cumprido:** o documento `152742` (ESC-0101) saiu
**indecidível** (`MIL|nenhum`). Seu ativo volta a ser o declarado, em reais.

**O que as guardas fizeram de fato.** Nos 405 documentos, as recusas foram
**2.404 por falta de rótulo** e **219 por página sem milhares**; as guardas de
**ações** e de **coincidência entre colunas não recusaram nenhuma ocorrência**
real. **ESC-0101 foi barrado pela condição E1a** (correção da auditoria, B1;
a versão anterior deste parágrafo atribuía o bloqueio à exigência de rótulo).
O `1.000` que a v2 casou é o saldo inicial de caixa **comparativo**
(`dt_fim` 30/09/2024), e o período corrente não chega a ser testado. Não houve
recusa nenhuma nesse documento. As duas guardas
que não dispararam continuam com contraprova sintética, mas **não há evidência
real de que sejam necessárias**.

**Premissa de herança mais fraca.** Com a v3, o trecho `023604` ficou não
testável (algum documento indecidível) e a herança passou a se apoiar num único
trecho testado (`003549`), sem interior discordante. O contrato S5 só exige
algum trecho testado e nenhum discordante; está cumprido, mas com menos
evidência que antes.

**Custo declarado:** a exigência de rótulo na mesma linha é conservadora.
Rótulo quebrado pelo extrator e total só "Total" não casam. **As 95
decisões perdidas (71 + 24) eram todas `MIL|bruto` e viraram `MIL|nenhum`**
(correção da auditoria, B1). **Não atribuí causa documento a documento.** O custo é mais indecisão, nunca mais correção.

## 2. RF-02 — disponibilidade da prova de escala

`Documento.disponivel_em = max(dt_receb, recepção das provas)`: o próprio
documento, na correção por documento; **as duas pontas**, na herdada. Vale para
ativo, acumulados, derivações e, portanto, para `vigente_em` e G1. Ponta
ausente do cadastro derruba a construção (P5). O painel publica
`dt_prova_escala`.

**G1.4 independente (P6):** o executor recalcula a data da prova **do
manifesto e do cadastro** e conta as observações que usam, em D, documento
com prova posterior. A condição de falsificação c3 usa a mesma data.

**Contraprova em dado real** (`verificacoes_revisao_final.json`,
`p6_contraprova_real_manifesto_execucao2`), com o manifesto da execução 2:

| Construtor | G1.4 | As 5 chaves do parecer na amostra | Observações |
|---|---:|---|---:|
| o de 16/09 (sem a prova) | **5** | as cinco | 10.750 |
| o atual | **0** | nenhuma | 10.745 |

No painel governante novo, G1.4 = 0. As provas herdadas da execução 3 são 9.

## 3. RF-03 e RF-08 — T1 e T2

**Partição de T1 (Q1):** cortes nominais `⌊k·n/5⌋` estendidos até o fim do
empate e eliminados quando redundantes. O exemplo do parecer passou de
`[400, 1, 1, 1, 97]` (amplitude 1,0) para `[400, 100]` (0,0). Contraprovas:
sem empate, constante, empate atravessando um e vários cortes, valores
distintos por faixa, permutação. Limiar e zona cinzenta sem mudança.
**Nenhum T1 real existia, então não há resultado a retratar.**

**Q3:** `probabilidade_de_exceder_o_limiar` → `frequencia_bootstrap_acima_do_limiar`.
A regra de decisão é a mesma.

**T2 (R6):** AUC agregada zero sai `0.0`; a lacuna usa a AUC agregada e, se
ela não for calculável, levanta em vez de usar zero. Contraprova com o exemplo
do parecer.

## 4. RF-04 — G0.5 pela escala aplicada

População: trimestre válido com operandos heterogêneos na escala **declarada
ou aplicada**, com algum operando sem veredito. Painel governante novo:

| Configuração | Trimestres | Sem veredito |
|---|---:|---:|
| declaradas diferentes, aplicadas diferentes | 43 | 43 |
| declaradas diferentes, aplicadas iguais | 39 | 8 |
| **declaradas iguais, aplicadas diferentes** (a classe omitida) | **5** | **5** |
| homogêneas | 22.001 | — |
| **Total em risco** | | **56 / 22.088 = 0,2535%** |

A versão de 16/09, com a população antiga e a execução 2, publicava
38/22.088 = 0,172%. O limiar ficou **[DECIDIR]** no v2, com a ressalva de que
0,5% seria política nova.

## 5. RF-05 — protocolo

Escritas no v2 como especificação ou proposta: fórmula do G0.3 (pares
adjacentes ÷ linhas de ativo válidas); grade de D (**[DECIDIR]**, §6.1);
janela e `sd8 = 0` (§6.2); escore e sentido de T2 (B1, negativo) e suporte
intra (**[DECIDIR]**, §8.1); partição e natureza da frequência bootstrap
(§7); B0 = "sempre não consumir"; ordem cega da medição (§6).

**Implementado:** B0 renomeado `B0_sempre_nao_consumir`, com IC 95% do acerto
agrupado por companhia. Sem IC válido, o B0 fica incompleto e bloqueia
`todos_completos`. A cobertura de classe é 1,0 por construção.

**Não implementado, de propósito:** o executor v2. Ele depende das decisões
dos §§5.1, 5.5, 6.1 e 8.1 e é o próximo trabalho depois delas.

## 6. Validação no caminho programático (V1)

`carregar_correcoes` devolve `CorrecoesValidadas`, com o SHA-256 do arquivo. O
executor de gates recusa `dict` comum com linhas e recusa manifesto alterado
depois de validado. Isto fecha a pendência "validação só pela CLI" do lote C
§8.7.

## 7. RF-06 e RF-07 — ligação de evidência e nomes

**RF-06.** O `c404c422…` que a verificação de 16/09 registrava era o hash do
manifesto do painel **antes** da última regeneração dos gates daquele dia. O
JSON de verificação tinha sido gerado antes dela, e o manifesto foi regravado
com os novos hashes de código. Não houve alteração de valores (a conferência
reconstruiu o painel). Agora `ligacao_de_versao` exige o mesmo digest no
manifesto do painel e no artefato de gates, e o mesmo manifesto de correções
nos dois, e grava os três hashes. O JSON foi regenerado **depois** do painel
novo.

**RF-07.** O inventário publica
`p2_pares_trimestre_decisao_no_intervalo_cego` e
`p2_chaves_companhia_D_distintas_no_intervalo_cego`. No painel governante
novo: 3.077 trimestres válidos com intervalo cego, **6.728 pares** e **4.175
chaves distintas**. Sem correções: 3.082 / 6.735 / 4.181, os números da
conferência.

## 8. Painel e gates, versão nova

| | Sem correções | Diagnóstico exec. 1 | **Governante (exec. 3)** |
|---|---:|---:|---:|
| Digest do painel | `6ca635a904f1…` | `86c42ec427b5…` | **`1250cefb9a72…`** |
| G0.3 | 132 (0,5875%) — **reprova** | 61 (0,2715%) | **68 (0,3026%)** |
| G0.1 / G0.2 / G0.4 | 0 / 0 / 0 | 0 / 0 / 0 | **0 / 0 / 0** |
| G1 | 10.748 obs, 502 cias | 10.744 obs, 502 cias | **10.750 obs, 503 cias** |
| G1.4 | 0 | 0 | **0** |
| Veredito | REPROVADO EM G0 | aprovado | **G0 E G1 APROVADOS** |

**Os digests mudaram também no painel sem correções** (`08fffc8b…` →
`6ca635a9…`) porque as tabelas ganharam a coluna `dt_prova_escala`; os
valores e os saltos são os mesmos. O diagnóstico da execução 1 passou de
10.750 para 10.744 observações pelo P4.

**G0.3 subiu de 47 para 68 saltos** porque 39 correções da execução 2 não se
sustentam na v3: os documentos voltaram à escala declarada e alguns saltos
reapareceram. Isso **não** significa que as 39 estavam erradas; significa que
a evidência localizada não basta para mantê-las. Diagnósticos: A2 (3 não
informativos; 70 saltos se incluídos), conflito/ambíguo (3; 70), G0.1 literal
**117 trimestres em 49 companhias** (inalterado).

Falsificações da parte 1 (c1–c5, c8): **todas zero** nas três variantes.

## 9. Verificações regeneradas

`artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json`
(`c74bc0500823…`), gerado **depois** do painel novo (e regenerado depois das
correções da auditoria); `versao` registra o digest `1250cefb…`, o artefato de
gates `aaffb03e…`, o manifesto do painel `039abb5a…` e o de correções
`6330d78d…`, conferidos entre si.

- **Máscara O1.3:** 167 evidências de cabeçalho, 68 linhas do manifesto, **189
  casamentos no manifesto** e **557 em `evidencias.jsonl`** (todos os
  documentos). A máscara **não mudaria nenhum**, e **nenhuma** linha de conta
  `6.x` publicada tem dígito.
- **Conferência de continuidade (B8)** das correções apoiadas em **um único
  valor localizado**: agora são **23** (a contagem é a da v3, por valor
  localizado; não é comparável com as 7 de 16/09). **21 corroboradas** por
  vizinhos declarados `MIL` com razão de ativo entre 0,91 e 1,91. Os vizinhos
  declarados `MIL` não são correções, porque toda correção é de documento
  declarado `UNIDADE`. **ESC-0017 e ESC-0019 não têm vizinho `MIL`** e se apoiam
  só no documento. Ficam, declaradas.
- **Amostra de desenho** (23 documentos do piloto, v3): MIL 6 confirmados e 6
  indecidíveis; UNIDADE 4 corrigidos e 7 indecidíveis. Na v2 eram 11/1 e 5/6.
- **Contraprova P6 em dado real:** §2.
- **Reprodutibilidade** (`medicoes_estruturais.json`, `bccf3528b345…`): duas
  construções independentes dão o mesmo digest, com correções (`1250cefb…`) e
  sem (`6ca635a9…`).

A comparação com uma reexecução separada (`--reproducao`) não foi refeita
nesta onda. A execução 3 é a própria reexecução, e o campo registra "não
fornecida".

## 10. Procedência

| Arquivo | SHA-256 (12) |
|---|---|
| `scripts/painel_pesquisa_rank03b.py` | `f61f5ab115d3` |
| `scripts/gates_painel_pesquisa_rank03b.py` | `131e44129987` |
| `scripts/fonte_rad_cvm.py` | `0697d1fed36f` |
| `scripts/adjudicar_escala_rank03b.py` | `67444c160b2f` |
| `scripts/auditar_rank03b_consumo_operacional.py` | `a550108f46de` |
| `scripts/verificacoes_revisao_final_rank03b.py` | `d4a9b7eec4f2` |
| `artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json` | `c74bc0500823` |
| `artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json` | `bccf3528b345` |
| `corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv` | `6330d78d02df` |
| `artefatos/painel_pesquisa_rank03b/gates_g0_g1.json` | `aaffb03e8aff` |
| `artefatos/painel_pesquisa_rank03b/manifesto_painel.json` | `039abb5a429e` |
| `…/gates_g0_g1_sem_correcoes.json` | `5fcaaab4252e` |
| `…/gates_g0_g1_diagnostico_execucao1.json` | `e1742f523d04` |

Reprodução, da raiz:

```bash
export PYTHONPATH=. RAD_SEM_REDE=1
.venv/bin/python -m scripts.adjudicar_escala_rank03b          # ~15 min, 10 processos
.venv/bin/python -m scripts.gates_painel_pesquisa_rank03b --sem-correcoes
.venv/bin/python -m scripts.gates_painel_pesquisa_rank03b --diagnostico-execucao-1
.venv/bin/python -m scripts.gates_painel_pesquisa_rank03b --correcoes corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv
.venv/bin/python -m scripts.verificacoes_revisao_final_rank03b
.venv/bin/python -m scripts.medicoes_estruturais_rank03b
```

## 11. Substituições de teste, declaradas

- `TestAdjudicarFormulario` (adjudicação): passa `dt_refer`, e as linhas
  sintéticas que devem decidir ganharam o rótulo da conta. O caso de O1.3
  passou a exigir que o número tenha decidido, o que é mais forte.
- A fixture de correção do painel ganhou `id_doc` (P5).
- `p2_decisoes_da_mesma_companhia_no_intervalo_cego` → as duas chaves novas,
  com a antiga proibida.
- G0.5: `com_escalas_declaradas_diferentes` → `com_escalas_heterogeneas`, com
  a contagem por configuração.
- `B0_classe_majoritaria` → `B0_sempre_nao_consumir`, com a antiga proibida.
- `amostra_de_desenho`: o dublê recebe `dt_refer`.

Nenhuma asserção foi retirada.

**Suíte:** 2.544 casos passando, zero skip (antes 2.495). A suíte isola `RAD_SEM_REDE`: exportada no ambiente, derrubava 5 testes de download com dublê. **Hashes
congelados conferidos:** `cvm.duckdb` `43e31d9f`, `cvm_treino.duckdb`
`c1a60445`, pré-registro v1 `fbae30cc`, plano de contas `fa271cd3`; holdout sem
alteração.

**Efeito sobre o script da conferência (corrigido, auditoria B2):**
`artefatos/revisao_pre_treino_rank03b_2026-09-17/reproduzir_estrutura.py`
**não roda mais** contra o código atual. Ele chama `verificar_falsificacoes`
sem `provas`, o que agora levanta `ProvasAusentes`; e lê a chave
`painel_sha256_do_manifesto`, que virou `versao`. O script não foi alterado,
porque é evidência da conferência. **A próxima conferência precisa de script
próprio.**

## 11-bis. Auditoria de conformidade desta onda

Sem achado de severidade alta. Corrigido depois dela:

- **M1:** `medir` e `verificar_falsificacoes` levantam `ProvasAusentes` quando
  o painel tem escala corrigida e nenhuma data de prova. Antes, G1.4 e c3
  saíam zero. Um construtor sabotado chamado sem provas aprovava; com provas,
  reprova com 3.
- **M2:** o executor recusa correções sem caminho de origem (o artefato
  registraria "SEM CORREÇÕES") e correções alteradas em memória depois da
  validação (hash do conteúdo).
- **M3:** a proposta do G0.5 no v2 ainda dizia "declaradas" e "não é número
  novo". Reescrita.
- **B1, B2, B4:** texto deste relatório, acima.
- **B3:** números de 16/09 marcados como substituídos no `AGENTS.md` e no v2.
- **B6:** a verificação da máscara passou a cobrir também os casamentos de
  `evidencias.jsonl` (todos os documentos, não só os corrigidos).
- **B7:** o teste de permutação da partição agora varia `y` dentro do empate.
- **B8:** nota em `adjudicacao/execucao2/NOTA.md`: o `resumo.json` preservado
  registra o manifesto `6e2c86a1…`, de antes da regravação M2 de 16/09. O CSV
  preservado é o `4735fb10…`, com as mesmas decisões.

**Declarado sem correção (B5), porque mudar a regra depois da execução 3
violaria o contrato da onda.** São buracos plausíveis da v3, sem caso real
encontrado:

- "total do ativo não-circulante", com hífen, passa como rótulo da conta 1;
- "acoes" sem acento escapa da guarda de ações;
- a guarda de milhares olha a **página**, não a tabela.

O auditor varreu as 59 correções por documento: só ESC-0065 tem "em reais" na
página, e é "denominados em reais" (moeda). Ficam para uma v4, com contrato
próprio.

## 12. Limites

- A verdade econômica das 68 correções **não** foi conferida uma a uma por
  humano. A v3 só exige mais da evidência.
- As 39 correções que saíram não foram julgadas erradas; ficaram sem
  evidência localizada.
- O executor v2, a decisão de G0.1, o limiar de G0.5 e os §§6.1/8.1 seguem
  pendentes.
- Esta onda precisa de **conferência independente** antes da aprovação do v2.
