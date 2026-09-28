# Pré-registro v2 — Rank 3-B: início de consumo operacional persistente

**Data do rascunho:** 2026-09-16. **Data do congelamento:** 2026-09-28.
**Status: CONGELADO em 2026-09-28, por ato do responsável.**

**Ato de congelamento (2026-09-28).** O responsável delegou o ato a Claude,
nesta sessão, com estas palavras:

> "Congelar, por cópia. O rascunho fica onde está; você copia para um arquivo
> sem "RASCUNHO" no nome, põe a linha **Status: CONGELADO em <data>…**, cola
> os seis hashes do §4 e publica o SHA-256."
>
> "Antes de congelar: a previsão registrada desde 11/09 é que o T1 reprove por
> fco_ttm_sobre_sd8. Se ela se confirmar, o veredito é REJEITADO e não há
> treino. Congelar significa aceitar esse risco antes de ver o resultado."
>
> "Seja crítico, atue como um especialista, e garanta as melhores decisões."

É a delegação expressa que o parágrafo "Decidir não é congelar", abaixo,
exige. Este arquivo é cópia de `pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md`
no commit `c815930` (SHA-256
`f419ee56cc03662705af177fa6421aa8e2c27c8333b6fbb18095add0f86a0ce1`). Diferem
só: a linha de status, este bloco, a data do congelamento, "esteve em
rascunho" no parágrafo seguinte e o `codigo_de_medicao` no §4.

*Texto do rascunho, mantido:* enquanto esteve em rascunho, **nenhum T1, T2 ou baseline é medido** sobre dado
real. O congelamento é: aprovação explícita do responsável → remoção de
"RASCUNHO" do título e do nome do arquivo → SHA-256 publicado → só então a
medição. *(28/09, M1 e AF1 da auditoria final: congela-se **por cópia**. Este
rascunho fica no lugar, e o congelado é um arquivo novo, com nome sem
RASCUNHO e com esta linha de status trocada por `**Status: CONGELADO em
<data>, por ato do responsável.**`. A medição recusa se a linha de status não
declarar congelamento. A ordem está no [contrato](contratos_caminho_medicao_rank03b_2026-09-27.md),
seção "Auditoria final (28/09)".)*

**Substitui** o [pré-registro de 11/09](pre_registro_rank03b_consumo_operacional_2026-09-11.md)
(`fbae30cc…`), **consumido** pela rodada que parou em G0. **Não é Rank 3-C:** o
estimando, os componentes e os limiares são os mesmos. Mudam o painel (agora o
de pesquisa, com fonte e linhagem) e as regras que a v1 deixava implícitas e
três ondas de correção mostraram ambíguas.

**Decisões de 26/09.** Os seis pontos que estavam marcados **[DECIDIR]** —
§3.2 (seguradoras), §5.1 (leitura de G0.1), §5.5 (G0.5), §6.1 (grade de D),
§8.1 (suporte de T2) e §12-bis (alcance da prova de escala) — foram decididos
em 26/09 por Claude (sessão principal), **por delegação expressa do
responsável**. Motivos e alternativas estão no
[registro de decisões](registro_decisoes_v2_rank03b_2026-09-26.md). O
[adendo ao O1](adendo_o1_rank03b_2026-09-26.md) é da mesma data, e o texto
anterior está no Git (commit `bd07216`).

**Revisão de 27/09.** A auditoria de conformidade da onda (APTA COM
RESSALVAS) e a reconferência dela (FECHADO COM RESSALVAS) corrigiram o texto
das decisões, sem mudar a opção escolhida em nenhum item. Mudaram ou entraram
regras:
- no §5.5: escala comparada, regra 3, por que só o estado do §5.5 ocupa o seu
  lugar, teto de perda só sem correções;
- no §6.1: ordem fixa dos filtros e o que se publica antes do congelamento;
- no §8.1: especificação do bootstrap;
- no §12-bis, condição 3, e no §13.

Foram corrigidas as declarações dos §§11.1 e 11.7 e o status, que diz quem
congela. O detalhe está no registro de decisões.

**Decidir não é congelar.** O congelamento espera o executor v2 testado, a
conferência independente e a resolução estrutural do G0, num painel com pins
novos (§4). O O1 vale até lá. Congelar encerra a cegueira e libera a primeira
medição de desfecho, por isso exige ato explícito do responsável, ou delegação
expressa para esse ato, registrada com as palavras e a data. A delegação de
26/09 cobre as decisões dos pontos [DECIDIR] e o adendo ao O1, **não** o
congelamento. **Leia o §11 antes de rever qualquer decisão:**
ele declara o que já foi visto, inclusive uma taxa de evento no painel
compartilhado publicada em 15/09.

**Estado em 27/09, fim do dia.** As três condições do parágrafo acima foram
cumpridas:
- o executor v2 foi testado em sintético e conferido de forma independente;
- as correções por conta foram provadas pela ROTA-2 e aprovadas numa
  conferência documental independente, sem recusa;
- num painel com pins novos, **G0, G0.5 e G1 aprovaram sem rótulo** (G0.3:
  95 saltos, 0,4255%).

Os pins propostos estão no §4 e o que se viu, no §11.8. **O rascunho continua
não congelado.** Congelar é o próximo ato, e é do responsável.

*(28/09: a conferência independente do executor, que a primeira condição cita,
ficou completa com a auditoria final sobre o commit `9049579`: APTA COM
RESSALVAS. As ressalvas (M1 e B1–B5) foram tratadas antes do congelamento,
com as emendas AF1 a AF3 e os pareceres versionados.)*

> **Revisão de 17/09.** A [conferência independente](conferencia_pre_treino_rank03b_2026-09-17.md)
> achou erro de escala comprovado (ESC-0101), uso de prova de escala antes da
> publicação e partição defeituosa de T1. As correções seguem os
> [contratos RF-01 a RF-08](contratos_correcao_rf01_rf08_rank03b_2026-09-17.md)
> e estão no [relatório da onda](correcao_rf01_rf08_rank03b_2026-09-17.md).
> A conferência seguinte achou CRF-01 a CRF-03. As
> [correções de 18/09](correcao_crf01_crf03_rank03b_2026-09-18.md) fecharam as
> guardas e tornaram a adjudicação mais estrita. **Nenhum dos 405 documentos
> teve tabela suportada pela v4; o manifesto ficou sem correções e G0 voltou
> a reprovar.** Isso não prova que as 68 correções antigas eram erradas:
> não foram certificadas pela nova regra. Este rascunho não autoriza treino.

---

## 1. A previsão — transcrita da v1, sem alteração

> **Eu espero que este alvo REPROVE T1, e o componente que deve reprová-lo é
> `fco_ttm_sobre_sd8` — a distância de FCO até zero medida em desvios-padrão do
> próprio FCO.**
>
> **Mecanismo:** `Y` é um limiar de sinal sobre uma série contínua. Quem está a
> 0,2 desvios acima de zero atravessa por ruído; quem está a 5 desvios não
> atravessa nem com deterioração real. A regra do §4.4 diz que escapa da
> armadilha só evento **materialmente definido** — falência, evento legal,
> reapresentação. `FCO < 0` **não é** um desses: é limiar sobre série contínua, e
> a elegibilidade "FCO_TTM > 0 em D" agrava, porque concentra a população perto
> da fronteira.
>
> **Se essa previsão se confirmar, o veredito é REJEITADO e não há terceira
> tentativa com o mesmo formato.** Baixar o limiar, trocar `sd8` por outro
> normalizador ou mudar o horizonte cria **Rank 3-C**, com pré-registro próprio.
>
> **Se ela NÃO se confirmar** — todos os componentes abaixo de 0,15 com folga —,
> então a distinção "limiar sobre série contínua × evento material" é mais fraca
> do que o §4.4 afirma, e **a regra é que precisa ser corrigida**, não o alvo.
> Esse resultado seria publicável como achado de método.

A previsão **continua não testada**: a rodada de 11/09 parou em G0.

### 1.1 O que um T1 aprovado permite afirmar — acrescentado em 28/09, antes do congelamento

A citação acima continua sem alteração. Este item só restringe o que se pode
afirmar se a previsão **não** se confirmar. Não muda limiar, componente,
código nem veredito.

**O limiar do T1 é absoluto, e a taxa-base deste alvo é baixa.** Os
precedentes em que o T1 reprovou tinham prevalência de 17% a 20%: C1, 0,174
(1.761 eventos em 10.117 observações, `validacao_c1_2026-08-26.md`); Rank 3,
0,203 (`validacao_rank03_conversao_caixa_2026-08-27.md`). A taxa-base deste
alvo já foi vista (§11.1): 0,053, no painel compartilhado. Com ela, a maior
amplitude possível entre cinco quintis é de cerca de 0,26, com todos os
eventos num só quintil.

**Consequência, só por aritmética.** O padrão que reprovou o C1 foi 30,2% no
quintil de menor `sd8` contra 5,5% no maior, com AUC agregada de 0,70.
Transposto para a taxa-base de 0,053, mantendo a razão entre as taxas, dá
cerca de 9,2% contra 1,7%: amplitude de 0,075, abaixo até da zona cinzenta.
O mesmo mecanismo, com a mesma força, passaria aqui sem bootstrap.

**Regra de leitura, fixada antes de medir:**
- T1 **reprovado** continua conclusivo, como no §7.
- T1 **aprovado não refuta o mecanismo do §1.** O parágrafo "Se ela NÃO se
  confirmar" **não se aplica** a esta medição. Dela não sai correção do §4.4
  nem achado de método. Um achado de método exigiria pré-registro próprio, com
  limiar relativo à taxa-base.
- Em qualquer desfecho, publica-se ao lado da amplitude de cada componente a
  razão entre a maior taxa por quintil e a taxa-base. É **descritiva e não
  decisória**. Sai da `taxa_por_quintil` que o T1 já publica, e nenhum código
  muda.

**Por que o limiar não muda.** Ele é identidade da v1 (topo deste rascunho),
e a taxa-base é estatística de rótulo já vista. Escolher agora outro limiar,
conhecendo-a, seria ajustar o teste ao dado, e criaria o Rank 3-C.

**O que protege o desfecho PRONTO PARA CHALLENGER.** Ele só autoriza escrever
o D8 (§9). O D8 exige que o desafiante supere o **melhor** trivial, e o B1
ordena justamente por `fco_ttm_sobre_sd8`. Se o mecanismo existir abaixo do
limiar, ele aparece como um B1 forte, e o desafiante tem de vencê-lo.

---

## 2. Alvo — o da v1, com as operacionalizações escritas

**Origem de cada operacionalização**, para não atribuir à v1 o que ela não
dizia. A v1 (§2) escreve só "primeiro trimestre **fiscal** cujo INÍCIO é
posterior a D" e "os três trimestres fiscais seguintes". São **posteriores à
v1** e já estavam em código antes deste rascunho:

- **"até D + 3 meses"** e **q2–q4 com datas encadeadas** — contrato H1.1/H1.2
  de [15/09](contratos_correcao_qw1_qw8_2026-09-15.md), achado N1;
- **rótulo = trimestre civil de `dt_fim`** — contrato T2 do
  [lote C](contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md) (16/09), que
  só nomeia; a ordem e o encadeamento continuam pelas datas (§2.1);
- **disponibilidade pela maior versão** (§2.2) — contrato P do lote C.

Nenhuma delas muda o estimando; todas mudam **quais** observações existem, e
por isso entram aqui para serem congeladas.

```text
D  = data de decisão. Só entra informação disponível em D (§2.2).
q1 = primeiro trimestre cujo INÍCIO é posterior a D, e até D + 3 meses (H1.1)
q2, q3, q4 = os três trimestres seguintes a q1, com datas encadeadas (H1.2)

S1 = FCO(q1) + FCO(q2)
S2 = FCO(q3) + FCO(q4)

Y = 1  se  S1 < 0  E  S2 < 0
Y = 0  se  ambos S1 e S2 existem e a condição não se cumpre
Y = indefinido (observação DESCARTADA) se qualquer um dos quatro FCO falta
```

Elegibilidade, **a da v1**: `FCO_TTM` conhecido em `D` > 0; companhia não
financeira (§3); os quatro trimestres existem como trimestre isolado; ativo total
conhecido em `D` e > 0. Unidade de observação: (companhia, `D`), com no
máximo uma `D` por (companhia, q1) (§6.1, decidido em 26/09). Unidade de
agrupamento de toda inferência: **companhia**.

### 2.1 Identidade dos trimestres

Trimestre = `(companhia, dt_ini, dt_fim)`, com duração de 80 a 100 dias. O
rótulo `kTAAAA` é o trimestre civil de `dt_fim` e serve só para ordenar; q1 é
escolhido pelas **datas** e q2–q4 exigem ordinal consecutivo **e** início no dia
seguinte ao fim do anterior. Num exercício de trimestres de três meses isso é o
"trimestre fiscal" da v1; num exercício irregular, o que não encadeia é
censurado, nunca deslocado.

### 2.2 Disponibilidade das features — política conservadora

O número em mãos de cada documento é o da **maior versão** (a única que a fonte
guarda). Ele só é usado a partir da **recepção dessa versão**; num trimestre
derivado, da recepção mais tardia entre os operandos. **Consequência
declarada:** quando `D` cai entre a primeira e a última versão de um documento,
aquele trimestre não está disponível em `D` e a janela usa o que estava. Isso
não vaza; custa perda, medida em §11.

**Prova da escala (P4, 17/09).** A escala corrigida também é informação. Um
documento corrigido só está disponível quando **todas as provas da escala
aplicada** foram publicadas: o próprio documento, na correção por documento;
**as duas pontas do trecho**, na correção herdada. A data vale para o valor e
para toda derivação que o usa. Não se usa "dado corrigido retrospectivamente".

### 2.3 Safra do rótulo

`FCO(q1..q4)` usa a maior versão, **disponível ou não em D** — o rótulo é
futuro por definição. Reapresentação posterior entra no rótulo.

---

## 3. População

### 3.1 Da v1, sem alteração

Exclui-se a companhia com `plano_contas LIKE 'll3_09_%'` **ou** `is_banco`.
Sem controle setorial (`companhias.setor` em 5 de 741). Só consolidado.

### 3.2 Seguradoras — decidido em 26/09: exclusão

Exclui-se também a companhia com `plano_contas LIKE 'll3_13_%'`. A regra de
população passa a ser:

    EXCLUI  se  plano_contas LIKE 'll3_09_%'
            OU  plano_contas LIKE 'll3_13_%'
            OU  is_banco = TRUE

`plano_contas` é a assinatura do mapa semântico (`assinatura_plano_contas`, em
`src/mapa_contas.py`): o prefixo nomeia a conta do lucro consolidado (`3.13`)
e o sufixo resume o mapa inteiro. Medido em 16/09, depois da v1
(`artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json`, `fonte`): no
universo de 700, o prefixo alcança só o plano `ll3_13_48e4cd07`, com **3
companhias**. Em **duas** delas (`023159`, `024180`, 24 linhas) a `6.01` se
chama *"Caixa Líquido Atividades Seguradora/Resseguradora"*. Fluxo operacional
de seguradora é outra economia. É o critério estrutural da v1 aplicado a outro
plano financeiro, e é **conservador**: perde-se companhia, não se contamina a
população.

**Falha fechada.** A decisão conhece um só plano com esse prefixo. Se o painel
medido tiver outro plano `ll3_13_*`, o executor para: plano novo exige
decisão.

**Efeito publicado.** A exclusão muda numerador e denominador do G0.3. O
executor publica quantos saltos do G0.3 e quantas linhas de ativo válidas
pertencem às companhias excluídas (§4.4, regra 9). O painel não muda: o filtro
usa a coluna `plano_contas` já carregada. Contraprovas: companhia sintética em
`ll3_13_*` excluída; em `ll3_11_*`, mantida; outro plano `ll3_13_*` →
execução interrompida.

Não há controle setorial (§3.1): entidade financeira registrada em plano
`ll3_11_*` não é alcançada, e nenhuma afirmação setorial está no escopo.
Decidido **antes** de medir T1/T2. Nenhuma contagem de evento **por companhia
ou por plano** foi vista; a taxa agregada do painel compartilhado foi (§11), e
não separa seguradoras. Alternativa não adotada: manter as 3 e declarar.

---

## 4. Painel

**Painel de pesquisa:** `artefatos/painel_pesquisa_rank03b/painel.duckdb`,
digest de conteúdo **`6ca635a904f11140…`**, manifesto de correções
**`13520e61d99f…`**, zero linhas, execução 4b da adjudicação com a regra v4,
manifesto do painel em `manifesto_painel.json`; **G0 reprovado em 18/09**.
A execução 3 de 17/09 — `1250cefb…`/`6330d78d…`, 68 correções — foi
preservada e substituída por insuficiência de prova tabular. A versão de 16/09 —
`f9cb9da9…`/`4735fb10…`, 101 linhas — foi **substituída** depois da
conferência de 17/09. O painel é construído por `scripts/painel_pesquisa_rank03b.py`
a partir dos 31 ZIPs pinados, segundo o
[contrato do lote C](contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md).
Identificado por **digest de conteúdo** e pelos hashes das entradas, inclusive
o manifesto de correções de escala. `cvm.duckdb` e `cvm_treino.duckdb` não são
usados como fonte de valores.

Regras de dado que esta medição herda, todas escritas **antes** de medir o
alvo: estados de trimestre e perdas (F1–F6), valor não informativo (A2),
disponibilidade (P1–P4) e adjudicação de escala por documento com fonte (S1–S10,
com a evidência tabular v4 do contrato CRF-01 de 17/09 e adendo de 18/09;
a evidência numérica v3 do contrato E é histórica).
**Documento de escala suspeita não adjudicado permanece com o rótulo declarado.**

**Estes pins não são os do congelamento (decisão de 26/09).** Descrevem um
painel em que G0 já se sabe reprovado. O congelamento usará os pins do painel
que resolver o G0 com correções provadas (§12-bis), medido sem rótulo.
Congelar com os pins atuais consumiria o v2 com o veredito já conhecido, como
a rodada de 11/09 consumiu a v1.

**Pins propostos para o congelamento (27/09).** Vêm do painel que resolveu o
G0 com correções provadas, medido sem rótulo. São os que o executor v2
confere na medição (`pins_do_congelamento`); cada hash tem de estar no texto
congelado.

| Pin | SHA-256 | O quê |
|---|---|---|
| `digest_do_painel` | `fd2932e7d026ea6c56ed69ce86d187114f02c87942331dadc0e85383a657c23b` | digest de conteúdo de `artefatos/painel_pesquisa_rank03b_v2/painel.duckdb` |
| `manifesto_por_conta` | `f26ede4da45c37946f555cbd641783633c01345d62a6b1c0b29e13d1fbc8313c` | `corpus/cvm/painel_pesquisa_rank03b/correcoes_escala_por_conta.csv`, 77 linhas |
| `evidencias_da_rota` | `e2001e0615c3e9a482ac78d2b69e22d7dc5ceffb34f570de165f6cb61dc54c24` | evidências da ROTA-2 |
| `conferencia_da_rota` | `734e7e709390cca8356cf4f31e50f457f62d53864e58f807584046411654aa68` | registro da conferência B8 da ROTA-2 |
| `adendo_o1` | `7f51ab27aff2604e8ec2b3a46f7e39cc12dd8aa82d52a44b2bb47dd158414b0f` | adendo ao O1 |
| `codigo_de_medicao` | `3de953a599eface1e7c0462aa381c446e940b32336257a5181b370d04e2601ca` | digest do código de medição inteiro (C9, M3), copiado de `artefatos/executor_v2_rank03b/estrutural.json` regerado em 28/09 sobre o commit `c815930` |

**O digest do código muda a cada edição de qualquer arquivo medido.** No
congelamento, ele é copiado do artefato estrutural regerado sobre o código
final. Se diferir do que a medição calcula, ela recusa.

O manifesto por documento (`13520e61…`, zero linhas) continua como entrada, e
o painel v2 é construído pelos mesmos 31 ZIPs pinados.

*(28/09, B4 da auditoria final.)* Os hashes das entradas ficam aqui **como
procedência**. O pin que a medição verifica é o digest de conteúdo do painel:
entradas diferentes que gerem o mesmo conteúdo não mudam a medição, e
conteúdo diferente a recusa.

| Entrada | SHA-256 |
|---|---|
| manifesto de correções por documento (zero linhas) | `13520e61d99f221715a26ade80dc278de15a6b30c93e30a63ed6b6aa753ff07d` |
| `cvm_treino.duckdb` (lido só para o universo) | `c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b` |
| manifesto de aquisição dos pacotes RAD | `36902f4ce38add21889bb41bfaf8c83c6264c8cfa77049acf3c5c30633cb5f8b` |
| os 31 ZIPs | `entradas.zips_sha256` de `artefatos/executor_v2_rank03b/estrutural.json` |

---

## 5. G0 — integridade, decisivo

| # | Verificação | Limiar | Como se aplica ao painel de pesquisa |
|---|---|---|---|
| G0.1 | Um só valor de FCO por (companhia, trimestre); nenhum valor que combine `DFC_MD` e `DFC_MI` do mesmo período | 0 | **Leitura por unicidade (§5.1, decidida em 26/09).** Derivação entre métodos permitida e contada. A leitura literal daria 117 |
| G0.2 | Nenhum trimestre fora de 80–100 dias | 0 | Duração **recomputada das datas** das linhas trimestrais; período fora da banda nunca é linha trimestral, é perda inventariada |
| G0.3 | Saltos de ativo ≥ 100× entre trimestres adjacentes | ≤ 0,5% | Depois das correções com fonte, e só delas. **Fórmula (RF-05):** pares de linhas de ativo **válidas** da mesma companhia, consecutivas e com ordinal adjacente, com `max/min ≥ 100`, divididos pelo **número de linhas de ativo válidas** (não pelo número de pares) |
| G0.4 | Nenhum valor nulo nas contas usadas | 0 | Contado em **todos** os candidatos, antes dos estados |
| G0.5 | Nenhum trimestre, observação ou componente censurados pelo §5.5 usados na amostra | 0 (uso) | **Censura em três níveis (§5.5, decidida em 26/09).** Perda publicada antes de montar `y`, em observações e em companhias. *(28/09, AF3: também reprova o uso de documento com erro demonstrado **pendente** na conta que o demonstra (§12-bis). Hoje o uso é zero.)* |
| G0.0 | Universo não vazio; toda conta requerida com linha | — | Implementado em 16/09 |

**As observações que G0.3 reprovar NÃO são removidas** (§4.4 regra 9). A
censura do §5.5 é outra coisa: é quarentena congelada antes do teste (a
mesma regra 9 a admite), não toca o ativo nem o G0.3, e a existência dos
trimestres censurados não reprova G0. Só o **uso** deles reprova (G0.5).

### 5.1 G0.1 — decidido em 26/09: leitura por unicidade

G0.1 verifica que há um só valor de FCO por (companhia, trimestre) e que
nenhum valor de FCO consumido pela amostra resulta de combinar `DFC_MD` e
`DFC_MI` do **mesmo período**, por soma ou qualquer outra operação. Limiar: 0.
É o risco que a v1 declarou para o item: "somar os dois duplica o caixa", "0
casos somados" (v1, §4).

O trimestre **derivado** de acumulados do mesmo exercício apresentados por
métodos diferentes é **permitido**. O caixa líquido das atividades
operacionais é o mesmo total nos dois métodos (CPC 03 (R2), itens 18–20A), e a
`6.01` é conta fixa com a mesma descrição nos dois (lote B, M1). A permissão
não dispensa nenhuma outra regra: mesma conta, consolidado, mesmo exercício,
banda de 80–100 dias, sem `PENÚLTIMO` como antecedente, disponibilidade pelo
operando mais tardio (F1–F6, P1–P4). Também não dispensa o §5.5: trimestre
derivado entre métodos **e** entre escalas não adjudicadas é censurado. O
método de cada operando fica na linhagem. O G0 publica quantos trimestres
válidos são derivados entre métodos, em quantas companhias, e quantas
observações da amostra usam algum deles na janela ou no rótulo.

Contraprovas do executor:
- MD e MI do mesmo período somados → G0.1 reprova;
- dois valores de FCO para o mesmo (companhia, trimestre) → G0.1 reprova;
- derivação entre métodos → aceita e marcada na linhagem.

**A leitura literal foi considerada e não adotada.** A frase da v1 é
"nenhuma observação usa `DFC_MD` e `DFC_MI` para o mesmo (companhia,
trimestre)", mas a origem e o limiar da mesma linha tratam de soma. O G0.1 que
a v1 executou contava só pares (companhia, trimestre) com mais de um
demonstrativo entre as linhas (`scripts/auditar_rank03b_consumo_operacional.py`,
`gate_g0`). Um trimestre derivado entre métodos tem um só demonstrativo e
nunca foi contado. Um 4T assim já era possível no painel da v1, porque a
derivação do 4T pareia anual e nove meses sem o demonstrativo na chave
(`src/dados_estruturados.py`). A unicidade é, portanto, a leitura que a v1
aplicou.

**Já medido, e declarado por isso:** pela leitura literal, o G0.1 daria **117
trimestres válidos em 49 companhias** (16/09, `gates_g0_g1.json`,
`diagnostico_g0_1_literal`), e o G0 reprovaria por algo que não é defeito de
dado. A censura desses trimestres tiraria observações sem defeito demonstrado.

**Risco residual, declarado:** troca de método que coincida com mudança de
classificação entre atividades mistura políticas na subtração. Nada no
repositório indica que ocorra, e o critério de refutação do lote C (totais
diferentes entre métodos no mesmo período) nunca foi testado. Isso é ausência
de teste, não evidência a favor.

### 5.5 G0.5 — decidido em 26/09, revisado em 27/09: censura das escalas heterogêneas não adjudicadas

G0.3 só olha o ativo. Um trimestre de FCO derivado de acumulados de escalas
heterogêneas não adjudicadas pode estar errado por mil. Um trimestre assim
muda o sinal do TTM, que define a elegibilidade e três componentes de T1, e o
de `S1` ou `S2`. Medido em 16/09, **antes** de qualquer adjudicação: 83
trimestres isolados combinavam acumulados de escalas declaradas diferentes. Na
versão vigente, 82 de 22.088 trimestres válidos estão na população de G5.1
(§11.3). Escalas distintas não provam erro sozinhas: o que se trata aqui é a
**ausência de adjudicação** onde há heterogeneidade.

**"Decidido para o FCO"** tem o sentido do §12-bis: veredito apoiado em prova
que alcance a `6.01` do documento. Confirmação ou correção apoiada só em prova
de saldo não conta. `documentos_decididos`
(`scripts/gates_painel_pesquisa_rank03b.py`) conta como decidido todo veredito
que não seja `indecidivel`, inclusive o apoiado só em saldo, e por isso não
pode ser reaproveitado como está. *(27/09: o executor v2 lê o "decidido" por
conta, das evidências da ROTA-1 conferidas. O FCO só é decidido pela cadeia da
DFC. E o executor confere que a escala decidida é a aplicada no painel.)*
*(27/09, depois: a ROTA-1 parou na B7 sem manifesto. As evidências que decidem
são as da ROTA-2 (§12-bis).)*

**Qual escala se compara.** As regras 1 e 2 abaixo comparam escalas
**aplicadas ao FCO**, e a regra 3 compara a aplicada ao ativo com a aplicada
ao FCO. A escala aplicada ao FCO é a declarada, salvo correção com prova que
alcance a `6.01` (§12-bis). Documentos de escalas declaradas diferentes mas aplicadas iguais
não são censurados, porque a diferença de declaração foi adjudicada pela
prova. Isto substitui, para o FCO, o "declarada **ou** aplicada" da população
G5.1 de 17/09. Aquela regra foi escrita quando uma prova de saldo podia mudar
a escala aplicada ao documento inteiro. Sob o §12-bis, só a prova do FCO muda
a escala aplicada ao FCO, e manter a declarada na comparação tornaria a prova
do FCO inútil para recuperar janelas: bastaria um vizinho sem veredito para
censurar. Hoje, sem correções, as duas leituras coincidem.

**Regra de dado, em três níveis.**

1. **Trimestre.** Recebe o estado `escala_heterogenea_nao_adjudicada`, e não é
   usado, o trimestre de FCO válido cujos operandos diferem na escala aplicada
   ao FCO, com algum operando sem veredito decidido para o FCO (população de
   G5.1, 17/09, lida como acima). O valor dele não entra na janela de oito
   trimestres, no TTM, em `sd8`, na contagem de trimestres negativos nem em
   q1–q4, e ele não gera data D (§6.1). **Mas ele ocupa o seu lugar:** conta
   como disponível desde a sua `disponivel_em` ao formar a janela (os oito
   mais recentes disponíveis em D) e ao identificar q1. Se estiver entre os
   oito, a observação é censurada, nunca deslocada para uma janela mais
   antiga. Se for q1 ou estiver em q2–q4, `Y` é indefinido (§2), e a chave
   (companhia, q1) se perde.

   **Por que só este estado ocupa o seu lugar.** Ele recusa um valor que
   existe, é trimestral e foi publicado: pular a sua posição daria à
   observação uma janela que ninguém tinha em D. Os estados de trimestre
   herdados do lote C (valor nulo, operando indisponível, duração fora da
   banda) descrevem **ausência** de valor trimestral nos documentos, e a
   janela sem eles é a informação que os documentos davam. Dois estados são
   casos intermediários, em que o valor existe mas não se sabe qual é:
   `conflito_de_declaracoes` (duas declarações do mesmo período) e
   `ambiguo_exercicio` (duas linhas válidas com o mesmo rótulo, marcadas por
   `_marcar_colisoes`; nenhuma fica). Os dois seguem a regra herdada, sem
   mudança, e isso fica declarado como limite.
2. **Observação.** É censurada a observação cuja janela de oito trimestres,
   cujo S1 ou cujo S2 reúnam valores de documentos com escalas aplicadas ao
   FCO diferentes, com algum desses documentos sem veredito decidido para o
   FCO. Os documentos de um trimestre são os seus operandos. A regra alcança
   somas de trimestres que não derivam um do outro, que a regra 1 não vê: por
   exemplo, o 4T de um exercício e o 1T isolado do seguinte, ou um 1T de
   escala diferente entre trimestres de outra. Não alcança o rótulo inteiro,
   porque `Y` depende do sinal de S1 e do de S2 separadamente.
3. **Componente.** `fco_ttm_sobre_ativo` fica ausente, como o §6.2 faz com
   `sd8 = 0`, quando a escala aplicada ao ativo em D difere da escala aplicada
   ao FCO de algum documento do TTM e um dos dois lados não tem veredito para
   a própria conta. O ativo em D é a linha mais recente disponível, escolhida
   fora da janela. Quando ele vem de documento que não opera no TTM, as regras
   1 e 2 não o veem, e a razão sairia errada por mil. A observação continua nos
   outros componentes; o componente e o baseline B3, que ordena por ele,
   publicam `observacoes_usadas` e `companhias_usadas`.

Os documentos continuam no painel com a escala declarada (§4). Seus ativos
continuam em G0.3, e seus acumulados continuam servindo de operando onde a
derivação é homogênea.

**G0.5 (decisivo): uso zero.** Recalculado pela linhagem, fora do construtor,
sobre a amostra montada sem rótulo: nenhuma observação tem, na janela ou em
q1–q4, trimestre no estado da regra 1; nenhuma cai na regra 2; e nenhuma usa
`fco_ttm_sobre_ativo` no caso da regra 3. Limiar: 0. Antes de montar `y`,
publicam-se, separados por regra:
- trimestres no estado da regra 1, por configuração (declaradas × aplicadas)
  e por companhia;
- observações (companhia, D) perdidas, com motivo próprio no inventário;
- companhias que perdem ao menos uma observação e companhias que saem
  inteiras, cada contagem com a fração sobre as companhias da amostra antes
  da censura;
- observações com `fco_ttm_sobre_ativo` ausente pela regra 3;
- observações e companhias da amostra final que pertencem a companhias só
  `UNIDADE`.

Contraprovas do executor:
- trimestre heterogêneo com operando sem veredito para o FCO → censurado;
- os dois operandos decididos para o FCO → usado;
- operando confirmado só por prova de saldo → conta como não decidido;
- operandos de escalas declaradas diferentes e aplicadas iguais, um corrigido
  com prova do FCO e o outro sem veredito → usado;
- operandos de escalas declaradas iguais e aplicadas diferentes, um sem
  veredito → censurado;
- D gerada por outra linha logo depois de um trimestre censurado → a janela
  o inclui e a observação é censurada, não formada com os oito anteriores;
- trimestre censurado que seria q1 (inclusive em exercício irregular) → q1 é
  ele, `Y` indefinido, chave perdida;
- janela com um 1T isolado de escala diferente dos outros sete → censurada
  pela regra 2, não pela 1;
- S2 = 4T + 1T de escalas diferentes → censurada;
- S1 homogêneo numa escala e S2 homogêneo em outra → não censurada;
- ativo em D de documento fora do TTM, com escala aplicada diferente e sem
  veredito → `fco_ttm_sobre_ativo` ausente, observação mantida nos outros
  componentes;
- construtor que use trimestre, observação ou componente censurados → G0.5
  reprova.

**Teto da perda, por construção — vale para o painel sem correções.** Sem
correções, a escala aplicada é a declarada, e só há heterogeneidade nas 54
companhias de rótulo misto; as 629 só `MIL` e as 17 só `UNIDADE` não têm
(`medicoes_estruturais.json`, `rotulos_de_escala`). As regras 1 e 2 tiram,
portanto, observações de no máximo 54 companhias da amostra estrutural de
18/09 (10.748 observações e 502 companhias), que conserva pelo menos 448. Cada
linha trimestral de FCO tem um só documento corrente e gera no máximo uma data
D. A perda em observações é, então, da ordem do número de documentos dessas
companhias: 1.683 na tabela de rótulos, que só conta documentos com recepção
única no cadastro. Sobram da ordem de 9.000 observações, muito acima do mínimo
do T1 (§7). **Com correções, o teto muda:** uma correção com prova do FCO numa
companhia só `UNIDADE` cria heterogeneidade fora das 54, e o teto é
recalculado sobre o painel novo antes de montar `y`. A perda real é publicada
e não pode mudar a regra.

**O que esta regra não é.**
- Não é tolerância. Não reutiliza o 0,5% do G0.3, que é contado em linhas de
  ativo e seria muito mais permissivo aqui, já que cada trimestre entra em até
  oito janelas e quatro rótulos.
- Não corrige escala nem afirma que o censurado estava errado.
- **Não alcança erro de escala consistente,** sem transição: companhia que
  declara `UNIDADE` em todos os documentos com números em milhares (17
  companhias, 400 documentos, não adjudicadas). Esse erro não tem gate. Ele se
  cancela nas razões e nos sinais e afeta só os três componentes de nível
  (`fco_ttm_em_D`, `sd8_fco_isolado`, `ativo_total_em_D`).
- Troca contaminação por seleção: T1 e T2 são medidos sem as janelas em torno
  de transições não adjudicadas, e o resultado não vale para elas.

**Proposta de 16 a 18/09, não adotada, e já medida:** G0.5 como fração de
trimestres na população de risco, com limiar ≤ 0,5%. Media 0,3712% na versão
vigente, 0,2535% na execução 3 e 0,172% na execução 2 (histórico). A decisão
não se apoia nesses números. A tolerância foi recusada por ser contada no
denominador errado e por a contaminação que ela admite empurrar T1 e T2 na
direção de aprovar.

## 6. G1 — point-in-time, decisivo

Os três itens da v1 (G1.1 features com recepção ≤ D; G1.2 q1 é o primeiro
trimestre iniciado depois de D, até D + 3 meses; G1.3 nenhum trimestre do
rótulo começa antes de D), mais as verificações de contiguidade, unicidade e
linhagem já implementadas, e **G1.4 (17/09): nenhuma feature usa, em D, um
documento cuja prova de escala foi publicada depois de D** — recalculado do
manifesto de correções e do cadastro, **não** da data que o construtor gravou.
**Amostra vazia reprova.**

**Ordem da medição (RF-05).** G0 e G1 são medidos com a amostra montada **sem
rótulo** (`calcular_rotulo=False`). Só se os dois aprovarem o executor monta
`y` — e sobre **a mesma** amostra, com uma conferência de que as chaves
(companhia, D) são idênticas. O `executar()` do auditor de 11/09 **não** é
reutilizado: ele monta `y` antes de G1. O executor v2 é escrito e testado em
dados sintéticos **depois** das decisões deste rascunho e **antes** do
congelamento.

### 6.1 Grade de D — decidido em 26/09, revisado em 27/09: disponibilidade do FCO, uma observação por (companhia, q1)

**Datas candidatas.** Para cada companhia, são as datas distintas de
`disponivel_em` (§2.2; P1 e P4) das suas linhas de FCO trimestral
utilizáveis: estado `valido` e fora do estado
`escala_heterogenea_nao_adjudicada` (§5.5), inclusive derivadas e postergadas
pela publicação da prova de escala. Na entrada do auditor, `dt_receb` é essa
`disponivel_em`. Não geram data candidata:
- a recepção de versão cujo número não está em mãos;
- a recepção que só traz ativo;
- a de documento cujo FCO não é utilizável.

Efeito de seleção declarado: uma companhia cujo único arquivamento novo num
período é de balanço não gera D nesse período, e uma D pode ser a data de
publicação de uma ponta de trecho.

**Uma observação por (companhia, q1).** q1 é identificado para cada data
candidata só por datas, como no §2 (H1.1), contando o trimestre censurado pelo
§5.5 no seu lugar. Entre as datas da mesma companhia
com o mesmo q1 — que têm o mesmo rótulo (§2.3) —, fica só a **maior**. Data
sem q1 identificável sai pelo motivo 1 da ordem abaixo. A escolha é feita
**sobre a grade, antes** de janela, elegibilidade e censura por observação.

Se a observação da maior data cair por qualquer motivo, a chave (companhia,
q1) se perde e **não é reposta** por data anterior, por dois motivos:
- depois da elegibilidade, a reposição traria de volta, com informação velha,
  a companhia cujo TTM já não é positivo — justamente quem já começou a
  consumir caixa, o que contamina o "início" do evento;
- a reposição trocaria a observação por outra com informação mais velha, que
  é o que o §2.1 evita no rótulo ("censurado, nunca deslocado").

As datas removidas vão ao inventário com motivo próprio
(`q1_repetido_mantido_o_maior_D`), contadas sem rótulo, com o número de chaves
afetadas.

**Ordem dos filtros, fixa.** Cada data candidata sai no primeiro motivo que a
remove, nesta ordem:
1. sem q1 identificável;
2. q1 repetido, mantida a maior D;
3. histórico insuficiente;
4. trimestre no estado do §5.5 entre os oito da janela;
5. janela com lacuna;
6. janela sem encadeamento;
7. trimestre no estado do §5.5 em q1–q4;
8. rótulo incompleto (q2–q4);
9. rótulo sem encadeamento;
10. regra 2 do §5.5;
11. `FCO_TTM ≤ 0` em D;
12. sem ativo disponível.

Os motivos 1 a 10 são estruturais: dependem de datas, estados e escalas, e não
leem valor de FCO. A elegibilidade (11 e 12) vem por último. A regra 3 do §5.5
não remove observação: só torna ausente um componente.

**O que se publica antes do congelamento (O1).** Observações finais, no total e
por companhia, e os descartes dos motivos 1 a 10 e 12. **Não** se publica o
total da grade, nem o número de datas candidatas por companhia, nem qualquer
conjunto de números do qual a contagem do motivo 11 saia por aritmética exata.
Depois do congelamento, publica-se tudo. Toda inferência agrupa por
companhia.

O critério é "exata" de propósito. As linhas por estado já saem no inventário
do painel, e as do estado do §5.5 sairão no G0.5. Com elas, um limite superior
do motivo 11 continua dedutível: linhas utilizáveis, menos os motivos
publicados, menos as observações finais. O erro desse limite é o número de
linhas da mesma companhia com a mesma `disponivel_em`. A ordem de grandeza
da contagem do motivo 11 já foi vista (§11.1). Calcular esse limite antes do
congelamento é proibido pelo O1.

Contraprovas do executor:
- duas datas com o mesmo q1 → fica a maior;
- maior data censurada → chave perdida, sem reposição;
- maior data inelegível → chave perdida, sem reposição;
- observação que falha em dois motivos → contada só no primeiro da ordem;
- artefato publicado antes do congelamento → não permite recompor
  `fco_ttm_nao_positivo` por soma ou subtração dos números que traz.

**Alternativas não adotadas:**
- **D em toda recepção do cadastro:** acrescentaria datas em que o número
  recém-recebido não está em mãos.
- **Grade de calendário fixa:** faria o horizonte depender do atraso de cada
  companhia em todos os casos.
- **Grade sem deduplicação** (a proposta anterior deste rascunho): dava peso
  extra ao mesmo evento, justamente nas companhias que arquivam tarde ou
  reapresentam.

### 6.2 Janela e `sd8`

Oito trimestres históricos **contíguos e encadeados** (§2.1), os mais recentes
disponíveis em D; TTM = os quatro últimos. `sd8` é o desvio-padrão amostral dos
oito. **`sd8 = 0`** não descarta a observação: deixa `fco_ttm_sobre_sd8`
**ausente**, e ela sai **só** do componente e do baseline que dividem por
`sd8` (B1 e T2). Cada componente e cada baseline publicam
`observacoes_usadas` e `companhias_usadas`, para que a ausência seja visível.

---

## 7. T1 — **idêntico à v1**, com a partição escrita

Seis componentes (`fco_ttm_sobre_sd8`, `fco_ttm_em_D`, `fco_ttm_sobre_ativo`,
`sd8_fco_isolado`, `ativo_total_em_D`, `trimestres_com_fco_negativo_nos_ultimos_8`);
limiar < 0,15 para todos; mínimo de 500 observações **e** 30 companhias por
componente; zona cinzenta [0,12; 0,15) com 2.000 reamostragens por companhia e
**frequência bootstrap** de amplitude > 0,15 acima de 10% ⇒ INDECIDÍVEL.
Nenhum componente pode ser retirado.

**Partição (RF-03, 17/09).** Ordena-se pelo componente; os cortes nominais são
`⌊k·n/5⌋`, k = 1..4; cada corte avança até o fim do grupo de valores
empatados; corte que cai em 0, em n, ou não depois do anterior é **eliminado**.
Um componente discreto (como `trimestres_com_fco_negativo_nos_ultimos_8`) pode
ter menos de cinco faixas, e o número de faixas é publicado. A versão anterior
do código criava faixas de uma observação depois de um empate grande.

**Natureza da frequência bootstrap.** É a fração das reamostragens de
companhias em que a amplitude passou de 0,15 — uma medida de instabilidade da
estatística, **não** a probabilidade posterior de a amplitude verdadeira
exceder o limiar. A regra de decisão a usa como está.

## 8. T2 — o limiar da v1, com o escore, o suporte e a precisão escritos

Lacuna AUC agregada − AUC intra-companhia < 0,12; escore constante levanta;
companhias com um só rótulo publicadas.

**Escore e sentido (RF-05):** o de **B1**, `fco_ttm_sobre_sd8` com sentido
**negativo** (quanto menor a distância a zero, maior o risco). AUC com meio
ponto para empate. **AUC intra** = média simples das AUCs das companhias que
têm os dois rótulos; AUC zero é publicada como zero (R6, 17/09).

### 8.1 Suporte e precisão da AUC intra — decidido em 26/09, revisado em 27/09

**Piso.** T2 só é decidido se ao menos **30 companhias** da amostra de T2
(observações com escore B1 definido, §6.2) tiverem os dois rótulos. Abaixo
disso, T2 levanta `AmostraInsuficiente` e o veredito é **INDECIDÍVEL**, nunca
aprovação (AGENTS.md §4.4, regra 4). É o mínimo de companhias que a v1 fixou
para T1, reaplicado à unidade de que a AUC intra é média. Não garante
precisão: cada AUC por companhia está em [0, 1], e o erro-padrão da média de k
companhias pode chegar a 0,5/√k, que é 0,091 com k = 30.

**Precisão.** A lacuna é reamostrada 2.000 vezes por companhia inteira,
recalculando as duas AUCs em cada reamostragem:
- semente `20260911` (a `SEMENTE` do auditor), com a lista de companhias
  ordenada por `cd_cvm` antes do sorteio;
- o piso de 30 vale para a amostra original, **não** para cada reamostragem;
- reamostragem em que alguma das duas AUCs não é calculável (falta uma das
  classes, ou nenhuma companhia sorteada tem os dois rótulos) não conta;
- a frequência é calculada sobre as reamostragens válidas, como no T1; com
  menos de 40 válidas, T2 é INDECIDÍVEL.

Veredito:
- lacuna ≥ 0,12 → **REJEITADO**;
- lacuna < 0,12 e frequência de reamostragens com lacuna ≥ 0,12 acima de 10%
  → **INDECIDÍVEL**;
- lacuna < 0,12 e frequência ≤ 10% → T2 aprovado.

O limiar é o da v1. A regra aplica a T2 a disciplina que o §7 aplica a T1:
passar raspando não é aprovação. Usa os mesmos 2.000 e 10%, que são política,
não calibração. Ao contrário do T1, vale para toda lacuna abaixo do limiar: a
faixa do T1 existe porque a amplitude tem viés para cima, e a lacuna não tem
viés conhecido que dispense o bootstrap. Como no T1, a frequência mede
instabilidade entre reamostragens de companhias, não probabilidade posterior.

Publicam-se, ao lado da lacuna: `companhias_com_os_dois_rotulos`,
`companhias_na_amostra`, observações nessas companhias, reamostragens
válidas, a frequência e o IC 95% percentil da lacuna.

Contraprovas do executor:
- 29 companhias com os dois rótulos → INDECIDÍVEL;
- 30 → segue para o limiar;
- lacuna abaixo de 0,12 com frequência acima de 10% → INDECIDÍVEL;
- menos de 40 reamostragens válidas → INDECIDÍVEL;
- reamostragem com menos de 30 companhias de dois rótulos, mas com as duas
  AUCs calculáveis → conta como válida;
- duas execuções com a mesma amostra → mesma frequência;
- escore constante → levanta.

Proposta anterior deste rascunho, não adotada: congelar sem piso. Com ela,
uma única companhia com os dois rótulos bastava para T2 ser decidido.

## 9. Baselines — da v1, com a ambiguidade do §8 resolvida

B0 a B3 da v1. As métricas **não são as mesmas para os quatro**, e a v1 já
dizia isso (§8: "B0 publica acerto **e cobertura**"):

| Baseline | Publica | Por quê |
|---|---|---|
| **B0** — **"sempre não consumir"** (regra fixa, **não** uma classe majoritária estimada) | **Acerto** com IC 95% agrupado por companhia, e **cobertura de previsão de classe = 1,0 por construção** (sem intervalo: não há o que variar) | É escore constante: AUC = 0,5 e precisão no top-10% indefinida por construção. Exigir essas métricas dele seria exigir número sem conteúdo — e T2 levanta com escore constante (§8). Implementado em 17/09 (`B0_sempre_nao_consumir`) |
| **B1–B3** (ranqueadores) | AUC agregada, AUC intra-companhia e precisão no top-10%, **todas com IC 95%** agrupado por companhia | — |

Mínimo de 40 reamostragens válidas por intervalo. Baseline sem as métricas da
sua linha é **incompleto**.

**O que muda:** a v1 punha como condição "o desafiante superar o melhor
trivial" — resultado de um modelo que o próprio protocolo ainda não permite
treinar. Aqui os dois momentos se separam:

| Momento | Condição |
|---|---|
| **PRONTO PARA CHALLENGER** (fim desta rodada) | G0, G1, T1 e T2 aprovados **e** os quatro baselines completos |
| **Modelo aprovado** (protocolo próprio — D8 do [levantamento](pendencias_desbloqueio_treino_dfc_2026-09-15.md), escrito e congelado **depois** desta rodada e **só** se ela terminar em PRONTO PARA CHALLENGER) | Desafiante supera o **melhor** trivial por margem cujo IC 95% pareado exclui zero, fora da amostra. A métrica que define "melhor" entre baselines de métricas diferentes (B0 × B1–B3) **não é fixada aqui**: é parte do D8 |

PRONTO PARA CHALLENGER é **permissão para escrever e executar o protocolo do
desafiante**, não evidência de superioridade.

## 10. Vocabulário de veredito — o da v1

REJEITADO · REPROVADO EM G0/G1 · INDECIDÍVEL · PRONTO PARA CHALLENGER.

Acréscimos de 26/09 ao INDECIDÍVEL (§8.1): T2 com menos de 30 companhias com
os dois rótulos, com menos de 40 reamostragens válidas, ou com lacuna abaixo
de 0,12 e frequência bootstrap de lacuna ≥ 0,12 acima de 10%.

---

## 11. O que já foi visto antes deste pré-registro

Declaração exigida pelo levantamento (D7). **Nenhum T1, T2, AUC ou baseline
sobre dado real foi calculado** em nenhuma rodada (11/09 parou em G0; 12/09,
15/09 e 16/09 mediram estrutura). **Mas estatística de rótulo foi vista**, e
uma versão anterior deste rascunho dizia o contrário. O inventário completo:

### 11.1 Estatísticas de rótulo — vistas

- **Taxa do evento no painel compartilhado (`cvm_treino.duckdb`), publicada
  em 15/09:** [implementação QW1–QW8](implementacao_qw1_qw8_2026-09-15.md), §3,
  "Taxa do evento **0,0526 → 0,0530**" (construção de 12/09, 10.670
  observações → construção corrigida, 10.605), "Com rótulo `y` diferente: **3**"
  e "FCO TTM não positivo **−5**". Foi calculada **antes** de existir a regra
  O1 (lote B, 16/09), para medir o efeito da correção N1, e o
  [contrato do lote B](contratos_lote_b_rank03b_2026-09-16.md) a omitiu da
  declaração do que já fora visto (ressalva RA7 de lá).
  **O que ela revela:** a taxa-base **agregada** do evento, ≈ 5%, num painel
  com o defeito de escala. **O que não revela:** nenhuma taxa condicional a
  componente, quintil, companhia ou plano — nada do que T1 ou T2 medem. A
  previsão do §1 é de 11/09, anterior a esse número. As propostas dos §§3.2,
  5.1 e 5.5 foram escritas **conhecendo** a taxa-base, e isto fica declarado.
  **As seis decisões de 26/09 também foram tomadas conhecendo-a.** No §8.1,
  ela permite prever que o piso de 30 companhias com os dois rótulos
  provavelmente é alcançado. O número 30 não foi calibrado por essa
  expectativa: repete o mínimo de companhias que a v1 fixou para T1.
- **Descartes por `FCO_TTM ≤ 0` em D no painel de pesquisa** — contagem
  agregada sobre uma feature que define a elegibilidade (proibida pelo item 1
  do O1: "TTM de FCO agregado"). Esteve nas versões de 16/09 dos três
  artefatos de gate (≈ 2.865 a 2.867 candidatos, conforme a variante) e foi
  lida. Removida desde a correção de auditoria A1: os artefatos atuais dizem
  "omitido por O1".

### 11.2 Rótulo calculado em memória — não inspecionado

Até a correção A1 de 16/09, `construir_amostra` do auditor **sempre** calculava
`S1`, `S2` e `y` ao montar a amostra, inclusive quando só se queria contar
observações para G1. Toda execução que mediu G1 fez isso: no painel
compartilhado (as rodadas e conferências de 12 a 16/09 que chegaram a G1) e no
painel de pesquisa em 16/09 (sem correções, diagnóstico da execução 1 e o
painel governante, cada um mais de uma vez). **Fora do 11.1, nenhum valor
derivado desses cálculos foi impresso, agregado ou gravado.** Desde a A1, o G1
do painel de pesquisa monta a amostra com `calcular_rotulo=False`, e um teste
garante que as somas do rótulo nem são chamadas.

### 11.3 Contagens estruturais — permitidas e vistas

- no painel compartilhado: 132 saltos (fração 0,005874); 10.605 observações
  construíveis em 494 companhias;
- no painel de pesquisa **sem correções** (digest `08fffc8b…`, versão de 16/09; com o código de 17/09 o mesmo painel tem digest `6ca635a9…` pela coluna `dt_prova_escala`): G0.3 = 132
  saltos (0,5875%), G1 = 10.748 observações em 502 companhias, zero violações;
- **versão vigente (18/09, execução 4b, regra v4):** 405 documentos
  indecidíveis, zero tabelas com cabeçalho local suportado, zero correções,
  herança não autorizada por S5. Manifesto `13520e61d99f…`, digest
  `6ca635a904f11140…`. **G0 reprovado:** 132 saltos (0,5875%, acima de 0,5%).
  G1 estrutural aprovado: 10.748 observações / 502 companhias, G1.4 = 0.
  G0.5 proposto: 82/22.088 = 0,3712%; A2/conflito: três ativos cada,
  134 saltos se incluídos. G0.1 literal: 117 trimestres em 49 companhias.
  Nenhuma estatística do alvo calculada; perda de cobertura do extrator não
  prova erro em todas as correções antigas nem impossibilidade de adjudicar;
- **versão de 17/09, execução 3, substituída (68 correções, manifesto
  `6330d78d02df…`, digest `1250cefb9a7276ce…`): G0 e G1 aprovados** — G0.3 =
  **68 saltos (0,3026%)**, G0.1/G0.2/G0.4 = 0 (G0.1 literal = 117 em 49
  companhias), G1 = **10.750 observações em 503 companhias**, G1.4 = 0; G0.5
  com a população corrigida = **56/22.088 (0,2535%)**, por configuração:
  43/43, 8/39 e **5/5** (declaradas iguais, aplicadas diferentes); A2 e
  conflito/ambíguo: 3 ativos cada, 70 saltos se incluídos; P2: 3.077
  trimestres com intervalo cego, **6.728 pares (trimestre, D)** e **4.175
  chaves (companhia, D) distintas**. Sem correções, com o código novo: digest
  `6ca635a9…`, mesmos 132 saltos, G1 10.748/502. Diagnóstico da execução 1:
  61 saltos, G1 10.744/502;
- **versão de 16/09, substituída** — no painel de pesquisa **com as 101 correções** (manifesto `4735fb107cce…`,
  digest `f9cb9da9d58673ff…`): **G0 e G1 aprovados** — G0.3 = 47 saltos
  (0,2092%), G0.2 e G0.4 = 0, G0.1 por unicidade = 0 (literal = 117, §5.1),
  G1 = **10.750 observações em 502 companhias**, zero violações. Com o
  manifesto da execução 1 da adjudicação (substituída pela ressalva RC1):
  61 saltos (0,2715%), também aprovado — **a regra corrigida não decidiu o
  veredito**;
- diagnósticos **históricos da execução 2 (16/09, substituída)**: A2 (3 ativos não informativos; 49 saltos
  se incluídos), conflito/ambíguo (3 ativos; 49 saltos se incluídos), G0.5
  proposto (§5.5), G0.1 literal (§5.1), identidades contábeis (6/23/14);
- inventário de perdas, versões e identidades (lote B e
  `medicoes_estruturais.json`);
- o custo da política de disponibilidade (§2.2), na versão de 16/09: **3.082**
  trimestres válidos com intervalo cego e **6.735** — que são **pares
  (trimestre, D)**, não decisões distintas (RF-07); as chaves distintas eram
  4.181.

### 11.4 Adjudicação de escala — como a regra foi escrita

- **Execução 2 (16/09, histórica):** 405 documentos adjudicados (cabeçalho de apresentação e números impressos
  nas notas), 77 corrigidos por documento e 24 por herança dentro de trecho;
  premissa de herança testada em 2 trechos (`003549`, `023604`), 1 não
  testável.
- **A regra da execução 2 (RC1-bis) foi escrita depois de ver a saída da execução 1**
  (falsos positivos da BRF e de notas de rodapé) e **refinada sobre uma
  amostra de desenho que se sobrepõe à avaliação** (documentos do piloto e
  casos BRF/TIM que também estão no escopo). Não houve amostra fresca. O que
  mitiga, sem eliminar: a regra ficou **mais conservadora** (só MIL decide), a
  execução 1 está preservada e medida (61 saltos, também aprovada), e nenhuma
  estatística de rótulo participou da escolha.
- **(16/09, sobre a execução 2, substituída)** **Conferência pontual das 7 correções apoiadas num único número bruto**
  (B8 da auditoria), por continuidade do ativo bruto com vizinhos declarados
  MIL (`verificacoes_revisao_final.json`): **5 corroboradas**. `ESC-0040` só
  tem vizinhos que também são correções (circular) e `ESC-0101` não tem
  vizinho declarado MIL; as duas se apoiam só no cabeçalho. Mantidas, sem
  ajuste pós-hoc — **e ESC-0101 estava errada** (conferência de 17/09); a
  frase "sem ajuste pós-hoc" confundia corrigir erro comprovado com ajustar
  ao resultado.
- **Amostra de desenho sob a regra da execução 2, histórica** (23 documentos vmax do piloto em
  E1–E4): MIL 11 confirmados e 1 indecidível; UNIDADE 5 corrigidos e 6
  indecidíveis.

### 11.5 Deslize de leitura

Dois valores de FCO acumulado de uma companhia (`025704`, 3T2024) foram
impressos ao estudar o formato de XML. Não há rótulo, semestre futuro nem
agregação envolvidos.

### 11.6 Conferência e correções de 17/09

- A conferência reproduziu o painel e os gates de 16/09 em memória, comprovou
  o erro de ESC-0101 em duas páginas do PDF, e contou por identidade e data
  (sem valores) as **24 correções herdadas** com prova posterior e as **5
  observações** afetadas. Mediu a classe omitida de G0.5 (3 trimestres) e as
  6.735/4.181 incidências do P2.
- A execução 3 mudou 95 decisões para indecidível e 11 de indecidível para
  decidida, sem inverter nenhuma escala. **A regra v3 foi escrita conhecendo
  ESC-0101 e com a execução 2 à vista**, e duas correções foram inspecionadas
  linha a linha (declarado no contrato E5). O resultado de G0 não foi visto
  antes da execução, e a regra não foi mexida depois dela.
- A contraprova do G1.4 no manifesto da execução 2 reproduziu as 5
  observações e contou observações, sem valores.
- **Nenhuma estatística de rótulo foi calculada.**

### 11.7 Leituras de FCO em memória de 24 a 26/09 — declaradas em 26/09, corrigidas em 27/09

Exigida pela cláusula 9 do [adendo ao O1](adendo_o1_rank03b_2026-09-26.md).
Nas execuções abaixo que leram FCO, salvo a primeira R3, cujo método não está
documentado: leitura só em memória, por módulo, como igualdade, nas formas que
o contrato enumerava — contra números impressos nas notas, na busca, ou contra
a saída publicada, nas reconferências e autoverificações —, e nenhum valor de
FCO impresso, gravado ou publicado. Em nenhuma execução listada se calculou
rótulo, soma de janela, TTM, T1, T2, AUC ou baseline.

- **24/09, alcance documental:** **não** leu FCO. A busca foi lexical, sem
  cálculo de FCO ("igualdade não executada"). O parecer do auditor dessa etapa
  registra que não se dereferenciou valor numérico de FCO.
- **24/09, revisão do alcance:** a busca numérica exata (R3) foi executada
  primeiro **em memória e sem contrato**, durante a revisão. As fontes só
  dizem isso e que os resultados ficaram conhecidos: não documentam as formas
  comparadas nem garantem, além de "em memória", que nada foi impresso. Depois
  a R3 foi refeita sob o contrato da revisão, que autoriza comparar o FCO por
  módulo em cinco formas: acumulado corrente e anterior, individual corrente,
  ×1.000 e ÷1.000. O verificador de não publicação calculou o piso por
  truncamento do módulo (`int(abs(v))`).
- **25/09, revisão:** a conferência independente repetiu a busca e a
  reconferência em memória, com o mesmo verificador. A reconferência
  pós-auditoria reconferiu em memória os artefatos publicados, também com
  piso por truncamento. O parecer da auditoria de conformidade dessa revisão
  não está arquivado em arquivo próprio; não se sabe se ela repetiu a busca.
- **25/09, correção RAG:** busca repetida (C6) e busca do adendo, com
  reconferência dos artefatos de 24/09 e autoverificação das saídas da
  primeira execução, que relê o FCO em memória. O verificador passou a
  calcular piso e teto.
- **26/09, adendos 2 e 3 da correção RAG:** busca e reconferência no dado real,
  com piso e teto.
- **25 e 26/09, as quatro conferências independentes da correção RAG:** não
  leram FCO. A primeira fez só contagens sobre o texto dos PDFs e booleanos
  com a conta `1`; registra que `alvos_fco` e a `6.01` nunca foram acessados.
  A segunda, a terceira e a quarta não repetiram a busca nem a reconferência
  reais; a segunda deixou de rodar a autoverificação justamente porque ela lê
  o FCO.
- **26/09, onda de pendências:** nenhuma busca nem reconferência com FCO real.

Os pisos e tetos ficam como histórico: o adendo não os autoriza
retroativamente (cláusula 7). Quem decidiu os pontos [DECIDIR] em 26/09 é a
mesma linha de sessões que conduziu a correção RAG. O que viu está declarado
no [registro de decisões](registro_decisoes_v2_rank03b_2026-09-26.md): este
§11 inteiro, contagens estruturais e nenhum valor de FCO.

**Correção de 27/09.** A primeira redação deste item dizia que a busca de
alcance de 24/09 leu FCO sob o contrato daquele dia. Não leu. Ela também
omitia a primeira execução da R3, sem contrato, e a conferência de 25/09. A
auditoria de conformidade da onda de 26/09 apontou os dois erros. A
reconferência dela precisou mais três pontos: o método não documentado da
primeira R3, a autoverificação da correção RAG e o fato de as quatro
conferências da RAG não terem lido FCO.

Fontes: `resultados/contratos_alcance_geom1_rank03b_2026-09-24.md`,
`resultados/alcance_geom1_rank03b_2026-09-24.md` (seções "Três ligações" e
"Busca numérica exata (R3)"),
`resultados/contratos_revisao_alcance_geom1_rank03b_2026-09-24.md` (R3 e
exposição declarada),
`resultados/conferencia_revisao_alcance_geom1_rank03b_2026-09-25.md`,
`resultados/adendo_revisao_alcance_geom1_rank03b_2026-09-25.md`,
`resultados/correcao_rag_alcance_geom1_rank03b_2026-09-25.md` (execuções no
dado real e adendos 2 e 3),
`resultados/adendo_correcao_rag_alcance_geom1_rank03b_2026-09-25.md`,
`resultados/correcao_pendencias_geom1_rank03b_2026-09-26.md`, o parecer
`artefatos/alcance_geom1_rank03b_2026-09-24/parecer_auditor.json`, os
pareceres `conferencia_1` a `conferencia_4` em
`artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/` e o código
preservado em `artefatos/alcance_geom1_rank03b_2026-09-24/revisao/`.

### 11.8 O que a onda de 27/09 viu — ROTA-1, ROTA-2 e executor v2

Fontes: [contratos do caminho até a medição](contratos_caminho_medicao_rank03b_2026-09-27.md)
e as pastas `artefatos/rota_prova_rank03b_2026-09-27/` e
`artefatos/rota_prova_rank03b_v2_2026-09-27/`.

- **Estrutura, antes do contrato.** O G0 reprovado (132 saltos) e a estrutura
  dos saltos: trechos, rótulos declarados, 28 documentos isolados. É contagem
  estrutural, sem rótulo.
- **Levantamento de disponibilidade.** Nos 103 documentos de T_A com pacote
  local, contou-se quantos tinham o valor exato do ativo (45) e do caixa (60)
  numa linha com o comparativo. Sem unidade e sem decisão.
- **Documentos de desenho.** Páginas de `98282`, `98645`, `70099` e `145753`.
- **ROTA-1, em dado real.** A prova por célula leu só contas de balanço. A
  cadeia da DFC leu, em memória e no processo principal, as contas 6.x dos
  formulários com âncora de caixa e a 6.01 do CSV, só para identidades e
  igualdade, com saída booleana (adendo ao O1, parte 2). A construção do
  painel carrega todo o FCO em memória, como sempre carregou. Nenhum valor de
  FCO foi impresso nem gravado.
- **Conferência B8 da ROTA-1.**
  - A conferência 1 não leu conta 6.x.
  - A conferência 2 leu contas 6.x em memória para as identidades, dentro do
    adendo. Ela declarou quatro exposições no próprio processo:
    - linhas da DFC com dígitos mascarados apareceram no console e deixaram
      ver a quantidade de dígitos e o sinal em três documentos, inclusive a
      6.01 de `100665`;
    - imprimiu booleanos com magnitude: 6.01 não nula com módulo ≥ 1.000 em
      36 documentos, e caixa ≥ 1.000.000 em 8;
    - imprimiu padrões agregados de formato de valor;
    - um cache temporário com valores do CSV existiu por segundos e foi
      apagado sem leitura.
  - Nenhuma dessas exposições é estatística de rótulo, e nenhuma é soma de FCO
    entre períodos.
- **O que se viu das provas.** Contagens por conta e veredito, as quatro
  recusas e os casos limítrofes (`80868`, `113026`). Isso foi antes de
  escrever a ROTA-2, que por isso só estreita a regra.
- **Não visto até o manifesto ficar final:** o G0 do painel novo.
- **Nenhuma** taxa de evento, T1, T2, AUC ou baseline foi calculada.

**Depois da ROTA-2 (acrescentado em 27/09).**
- **ROTA-2, em dado real.** Mesma exposição da ROTA-1, com as mesmas leituras.
  O pin foi gravado antes do processamento.
- **Conferência B8 da ROTA-2.**
  - A conferência 1 não leu conta 6.x. Consultou só a coluna
    `escala_declarada` do painel sem correções.
  - A conferência 2 não imprimiu linha de DFC, não gravou cache e não mostrou
    valor 6.x. Declarou dois booleanos na fronteira: `v_valido` (caixa com
    módulo ≥ 1.000, em quatro confirmações) e `sem_linha_dividido_do_caixa`.
- **Manifesto final, depois G0.** O manifesto por conta foi gravado com a
  conferência aprovada. Só então o executor v2 rodou em modo estrutural.
  - A primeira execução calculou o G0 em memória e parou na guarda de
    publicação, antes de imprimir ou gravar, pela colisão de nome `lacuna`
    (emenda C8 do contrato).
  - Uma sonda imprimiu só os caminhos das chaves que colidiam.
  - Corrigida a serialização, o G0 foi visto: **G0.3 = 95 saltos (0,4255%);
    G0.5 e G1 sem violação; amostra de 10.168 observações em 495 companhias**,
    com os descartes por motivo, exceto o 11.
- **Verificação do `140867`.** Contou-se, em memória, quantas observações da
  `021520` usam o ativo de 30/06/2024: zero, de 20. Foram impressos a
  contagem, a lista dos documentos de ativo usados e os nomes das chaves de
  uma observação. Nenhum valor foi impresso.
- **Depois de ver o G0, só mudaram serialização e pins** (emendas C8 e C9).
  Nenhuma regra de dado, população, limiar, componente ou correção mudou.
- **Nenhuma** taxa de evento, T1, T2, AUC ou baseline foi calculada. O rótulo
  não foi montado.

**Auditoria final e correções (acrescentado em 28/09).**
- **A auditoria** montou em memória a amostra sem rótulo do painel v2. Imprimiu
  contagens estruturais e, para uma única companhia (`021520`), a lista de
  trimestres com estado, escalas e datas de disponibilidade, além das datas
  dos documentos de ativo das 20 observações. Isso deixa ver quais datas D
  dessa companhia sobreviveram a todos os filtros, inclusive ao de TTM
  positivo, misturado com os outros motivos. O inventário com o motivo 11 foi
  descartado sem leitura. Não houve rótulo, `--medir` nem soma de FCO.
- **A sessão principal** reconstruiu os pareceres da conferência a partir do
  `conferencia.json` e dos parâmetros de serialização das transcrições, sem
  ler conta 6.x. Rodou de novo o modo estrutural depois das emendas AF1 a
  AF3: G0, G0.5 e G1 continuam aprovados, e os dois campos novos
  (`observacoes_que_usam` e `erro_demonstrado_pendente`) dão zero.
- **Nenhuma** taxa de evento, T1, T2, AUC ou baseline foi calculada. O rótulo
  não foi montado.

**Sessão de congelamento (acrescentado em 28/09).**
- Leu documentos, código, o `estrutural.json` e os registros de evidência de
  caixa da ROTA-2, com os trechos já mascarados. Contou, por padrão de
  rótulo, os registros de caixa apoiados só em linha de DFC. Não leu conta
  6.x nem abriu painel fora do executor.
- Rodou a suíte, que é sintética, e o modo estrutural, que é o passo 2 do
  congelamento. As contagens estruturais já tinham sido vistas.
- Para o §1.1, usou a taxa-base já declarada no §11.1 e as prevalências
  publicadas do C1 e do Rank 3. Não calculou estatística de rótulo nova.
- Depois do G0, só mudou texto:
  - o §1.1, que restringe a leitura de um T1 aprovado;
  - a nota do `113026` no §12-bis, que mantém o que a ROTA-2 decidiu;
  - o §14, que aponta os artefatos governantes.

  Nenhuma regra de dado, população, limiar, componente, correção ou código
  mudou.

## 12. O que esta rodada não fará

Nenhum modelo; nenhuma escrita nos painéis compartilhados; nenhum acesso ao
holdout; nenhuma chamada paga; nenhum ajuste de população, limiar, componente,
regra de dado ou correção de escala depois de medir.

## 12-bis. Adjudicação de escala — regra v3 (17/09, histórica)

A evidência numérica que decide a escala de um documento é **localizada**
(contrato E1): valor consolidado do período corrente; número numa linha das
notas que contém o rótulo daquela conta (vocabulário fechado E2) e não fala de
ações; página que declara milhares; número que não coincide, sob outro
multiplicador, com outro valor da mesma conta. Cada correção publica onde
estão os números que decidiram. A regra v2 (execuções 1 e 2) corrigiu
ESC-0101 por um "1.000" de quantidade de ações e está aposentada.

### Regra v4 (18/09) — vigente até 27/09

Os [contratos CRF](contratos_correcao_crf01_crf03_rank03b_2026-09-17.md) e
seu [adendo](adendo_contratos_crf_2026-09-18.md) exigem cabeçalho local com
unidade e perímetro consolidados, datas completas e correspondência da
conta com a célula da data corrente. Só saldos 1, 2 e 1.01.01 são elegíveis
como prova nesta versão; nenhum fluxo 6.x é usado sem identificação do
intervalo. Linha sem estrutura suportada é indecidível. Não se exige que as
notas reais adotem esse layout: **o extrator é que não sabe certificá-las**.
Na aplicação aos 405 documentos, nenhuma tabela foi reconhecida. A regra
não foi relaxada para recuperar G0. Reabrir a adjudicação exige outro
contrato de extração/prova, não elevar o limiar do gate nem recolocar a v3.

Exposição declarada: a v4 foi desenhada conhecendo ESC-0029, ESC-0101 e as
contraprovas publicadas. Houve correção de unicidade em sintético e nova
readjudicação (4b) antes do primeiro G0 da v4; depois, só a guarda do
consumidor de prova serializada mudou, com igualdade de AST fora dela e
revalidação das provas. Os pins anteriores foram preservados. Não houve
nova estatística de rótulo, T1, T2 ou baseline real nesta onda.

### ROTA-1 (27/09) — vigente por um dia; parou na B7 sem manifesto

Contratos em [contratos do caminho até a medição](contratos_caminho_medicao_rank03b_2026-09-27.md),
partes A e B, com a emenda pós-auditoria e a reconferência do mesmo dia. As
duas foram feitas antes de qualquer execução em dado real. É o "outro
contrato de extração/prova" que esta seção exigia para reabrir a adjudicação.
A v4 fica histórica: o manifesto por documento continua com zero linhas.

- **Célula própria (contas `1` e `1.01.01`).** A linha de um PDF do próprio
  pacote contém o valor corrente consolidado da conta e uma âncora, os dois
  exatos do formulário. Contém também o rótulo da conta. A tabela está em
  milhares, sem declaração contrária. Os mesmos dígitos provam `MIL`; os
  dígitos ÷1.000 provam `UNIDADE`. Só a declaração de milhares decide.
- **Elo do balanço.** Com o ativo provado, o caixa herda a escala se
  `1 = 1.01 + 1.02` e se `1.01` é a soma dos filhos diretos.
- **Cadeia da DFC (conta `6.01`).** Com o caixa provado, a `6.01` herda a
  escala se fecham `6.01 + … + 6.04 = 6.05`, `6.05.01 + 6.05 = 6.05.02` e
  `6.05.02 = 1.01.01`, e se a `6.01` do formulário é igual à do CSV. É a rota
  de prova do FCO que esta seção previa ("identidade interna da DFC"), sob a
  parte 2 do adendo ao O1, com saída só booleana. Só vale se o teste B6
  (concordância entre as provas do ativo e do caixa, fora dos documentos de
  desenho) aprovar.
- **Conferência documental independente** de toda correção e de uma amostra de
  dez confirmações, antes do manifesto. Uma recusa, ou um controle corrigido,
  e não há manifesto.

**Por que não é a v3 de volta.** A v3 aceitava um número só, casado na linha
com o rótulo. A ROTA-1 exige dois valores exatos da mesma conta na mesma
linha, e unidade de milhares com veto a qualquer declaração contrária. Foi
esse o risco que derrubou ESC-0101.

**Exposição.** A regra foi escrita conhecendo:
- o G0 reprovado;
- a estrutura dos saltos;
- a contagem de disponibilidade dos valores nos anexos dos alvos;
- quatro documentos de desenho (§11.8).

O G0 do painel novo só foi visto depois de o manifesto estar final.

### Regra vigente: ROTA-2 (27/09), para o manifesto por conta

A conferência B8 da ROTA-1 recusou quatro correções:
- em `60719`, a unidade não estava demonstrada, e isso era defeito real da
  regra;
- em `80868`, a recusa veio da ambiguidade do item 4 da conferência.

Pela B7, a ROTA-1 não produziu manifesto. A ROTA-2, no
[contrato](contratos_caminho_medicao_rank03b_2026-09-27.md) (seção ROTA-2),
**só estreita** a regra:
- uma declaração de milhares só vale como apresentação do anexo se o objeto
  da apresentação estiver por perto;
- só há apresentação em notas e demonstrações (grupos 193 e 412);
- os códigos de escala do envelope e do formulário são registrados, só como
  informação.

O item 4 da conferência foi reescrito: a escala declarada é a do CSV, a que
o painel aplica. O auditor a verificou APTA antes da execução.

**Resultado.** 300 documentos, com estas correções:
- 42 do ativo;
- 48 do caixa: 41 por célula própria e 7 pelo elo do balanço;
- 35 do FCO, pela cadeia da DFC.

B6 aprovou com 50 documentos e nenhuma discordância, e nenhum controle foi
corrigido. Dois conferentes independentes aprovaram as 125 correções e as 10
confirmações sorteadas, **sem recusa**.

O manifesto por conta tem 77 linhas, 42 da conta `1` e 35 da `6.01`. Com ele,
o G0.3 do painel v2 caiu de 132 para 95 saltos.

**Perda conservadora declarada.** `98282-1.01.01`, aprovado na ROTA-1, virou
indecidível pela regra de apresentação. O caso limítrofe `113026-1.01.01` foi
provado só pelo saldo final da DFC impressa. Se linha de DFC deixar de valer
como célula própria, é este o registro que muda.

*(28/09, antes do congelamento: **mantido, sem ROTA-3.** Decidido por Claude,
na sessão de congelamento, a pedido expresso do responsável ("garanta as
melhores decisões"). Motivos:*
- *A linha cumpre a B3 como foi fixada antes da execução. O rótulo só precisa
  **conter** `caixaeequivalentesdecaixa`; os dois valores são exatos (31/12/2021
  e 31/12/2020); a unidade é o "(Em milhares de reais)" local; o PDF é do
  próprio pacote. A regra não privilegia a linha do balanço.*
- *O caso não é único. `54783-1.01.01` (companhia `023434`, DFP 2015) também
  se apoia só no saldo final da DFC ("final do período"). É confirmação, não
  correção, e ancora a cadeia que confirma a `6.01` do documento, que por isso
  conta como decidida no G0.5. Não estava na amostra da conferência. Outros
  dez registros de caixa têm linha de DFC acessória. Tirar só o `113026` seria
  regra ad hoc. Tirar toda linha de DFC seria regra nova, escrita depois de
  ver o G0, e alcançaria mais que "as duas correções" que a revisão de 27/09
  descrevia.*
- *Para o uso que tem, que é ancorar a cadeia da `6.01`, o saldo final da DFC
  é prova mais direta que a linha do balanço: é a célula impressa da
  `6.05.02`, na mesma demonstração da `6.01`, e a cadeia confere
  `6.05.02 = 1.01.01` (d3).*
- *A conta `1` do mesmo formulário foi provada `MIL` pela própria célula, com
  sete dígitos nas duas datas. A alternativa seria um formulário corretamente
  em unidades, com dígitos de caixa coincidindo em duas datas numa linha com o
  rótulo, e ela não é plausível.*
- *O efeito no G0.3 é nulo: a correção do ativo não depende deste caixa.)*

### Alcance da prova de escala — decidido em 26/09, revisado em 27/09: opção B

Na v4 só saldos (`1`, `2`, `1.01.01`) provam escala, mas a correção entra no
manifesto **por documento**: o construtor aplica a escala do documento ao
ativo e ao FCO, e a impressão digital da correção cobre as contas `1` e
`6.01`. Pela v4, então, uma prova de saldo corrigiria também o FCO. A linha
GEOM-1 ([relatório de 18/09](escala_geometrica_rank03b_2026-09-18.md),
[contrato de 24/09](contratos_alcance_geom1_rank03b_2026-09-24.md)) adotou
outro critério: demonstrar a escala em cada conta que o painel usa. Os dois
não podem valer juntos. Origem: [ressalva da revisão de 24/09](alcance_geom1_rank03b_2026-09-24.md).

**Regra.** Correção que altera o FCO exige prova que alcance o FCO do mesmo
documento: conta `6.01`, consolidado, acumulado do período corrente com início
e fim identificados, sob as exigências da v4 (cabeçalho local com unidade e
perímetro, datas completas, correspondência da conta com a célula da data
corrente). O manifesto **por documento** só recebe documento com as contas `1`
e `6.01` provadas, **cada uma pela própria célula**. Prova de `2` ou de
`1.01.01` não substitui a da `1`, e prova de saldo sozinha não entra no
manifesto.

**O mesmo critério define o "decidido" do G0.5 (§5.5):** para o FCO,
confirmação ou correção apoiada só em prova de saldo não torna o operando
adjudicado.

**Correção só do ativo.** Continua vedada enquanto o manifesto não tiver
esquema por conta (hoje o consumidor recusa coluna por conta) e o G0.3 ler o
veredito por documento. *(28/09: as três condições abaixo foram cumpridas pela
parte A do [contrato de 27/09](contratos_caminho_medicao_rank03b_2026-09-27.md).
O manifesto por conta existe, com 77 linhas.)* O contrato que criar a correção por conta tem de,
antes de aplicar a primeira linha:
1. fechar o esquema do manifesto no produtor e no consumidor;
2. ler o G0.3 pela escala aplicada ao ativo, e o G0.5 pela aplicada ao FCO;
3. aplicar a regra 3 do §5.5 com as escalas lidas por conta: se a escala
   aplicada ao ativo em D diferir da aplicada ao FCO de algum documento do TTM,
   e um dos dois lados não tiver veredito para a própria conta,
   `fco_ttm_sobre_ativo` fica ausente.

A regra 3 do §5.5 já vale sem correção nenhuma. Com correção por conta, ela
passa a ser a guarda principal da razão: num documento com escala declarada
errada, ativo e FCO erram pelo mesmo fator, e `fco_ttm_sobre_ativo` sai certa.
Corrigir só o ativo desfaz esse cancelamento.

**Erro demonstrado conhecido, não corrigido.** O Ativo Total de `140867`
(companhia `021520`, 30/06/2024) tem `MIL` demonstrada diretamente, contra
`UNIDADE` declarada (alcance GEOM-1, 24/09). Pela regra acima, ele não entra
no manifesto enquanto o FCO do mesmo documento não for provado ou não houver
correção por conta. Fica registrado como erro demonstrado e pendente, e o
executor o lista no artefato de G0. Não é tolerado por caber em limiar nenhum.
*(28/09: as duas condições já valem. O FCO de `140867` foi provado pela
cadeia da DFC, e existe correção por conta. O ativo continua fora por outro
motivo: a ROTA-2 não achou linha com os dois números, e a demonstração da
GEOM-1 não é prova da ROTA-2. Segue pendente. Pela AF3, o G0.5 reprova se
alguma observação o usar como ativo em D; hoje são zero.)*

**Rotas para provar o FCO** (anexo do grupo 192; identidade interna da DFC)
exigem contrato próprio. *(27/09: a identidade interna da DFC ganhou o
contrato próprio. É a cadeia da ROTA-1, acima.)* Pelo [adendo ao O1](adendo_o1_rank03b_2026-09-26.md),
parte 2, verificar uma identidade contábil do mesmo documento e período, com
saída só booleana, é permitido. Usá-la como elo de prova exige que o contrato
fixe, antes de ler, as contas, a tolerância, o conjunto de documentos e o
teste fora dos documentos de desenho da GEOM-1. A premissa da opção A (a
escala verdadeira é uma só por formulário) só pode ser adotada depois de
testada em amostra pré-registrada, fora dos documentos de desenho, no molde do
teste da premissa de herança (lote C, S5/E10).

**Opção A, não adotada:** prova de saldo corrigiria o documento inteiro. Sob
A, depois de integrada a GEOM-1, **140867 e 142900** se qualificariam pela
prova de caixa conferida em 18/09 (142900 é documento de desenho da regra), e
o G0.3 cairia de 132 para 130 saltos, ainda reprovado (limite: 112). A é
recusada por dois motivos:
- usa uma premissa não testada para estender a prova à conta que define o
  rótulo;
- erra do lado invisível: correção errada do FCO corrompe em silêncio o rótulo
  e cinco dos seis componentes, enquanto a correção que falta deixa o G0
  reprovado à vista.

## 13. Condições de falsificação

As da v1 (§11), mais: o painel medido ter digest diferente do registrado aqui
no congelamento (os pins atuais do §4 não serão esses; *28/09: o §4 traz
agora os pins propostos, que são os do congelamento*); o manifesto de
correções ter hash diferente; alguma regra de dado (F, A, P, S)
ter mudado depois do congelamento; qualquer estatística de rótulo **além das
declaradas no §11** ter sido calculada antes do congelamento; o G1 da medição
montar a amostra com o rótulo antes de G0 e G1 aprovarem; alguma observação
usar, em D, escala cuja prova foi publicada depois de D; a partição de T1
diferir da do §7.

Acrescentadas em 26/09, com as decisões:
- companhia de plano `ll3_13_*` na amostra, ou outro plano `ll3_13_*` excluído
  sem interromper a execução (§3.2);
- valor de FCO que combine `DFC_MD` e `DFC_MI` do mesmo período, ou dois
  valores de FCO para o mesmo (companhia, trimestre) (§5.1);
- observação que use trimestre no estado `escala_heterogenea_nao_adjudicada`,
  que caia na regra 2 do §5.5, ou que use `fco_ttm_sobre_ativo` no caso da
  regra 3;
- duas observações com a mesma (companhia, q1), ou chave perdida reposta por
  data anterior (§6.1);
- T2 decidido com menos de 30 companhias com os dois rótulos, ou aprovado sem
  o bootstrap do §8.1 ou com frequência acima de 10%;
- correção de FCO sem prova que alcance o FCO, ou operando confirmado só por
  saldo contado como decidido no G0.5 (§12-bis);
- execução que use a exceção protetiva sem fixar o adendo ao O1 por hash, ou
  que prossiga depois de uma recusa.

Acrescentadas em 27/09, com a ROTA-1 e o executor v2:
- manifesto por conta, evidências da ROTA-1 ou registro da conferência com hash
  diferente do fixado no congelamento;
- código de medição com digest diferente do fixado (inclui o auditor de
  11/09, que tem T1, AUC, baselines e limiares);
- correção de escala apoiada em regra que não seja a ROTA-1, ou sem aprovação
  na conferência;
- documento decidido cuja escala aplicada no painel difere da decidida;
- rótulo somado sem o registro do congelamento.

Acrescentadas em 27/09, com a ROTA-2:
- onde as condições acima dizem ROTA-1, leia-se a regra do manifesto fixado,
  que é a ROTA-2. Correção apoiada só na ROTA-1 não está no manifesto; se
  aparecer, é falsificação;
- falta de algum dos pins do §4 no texto congelado, inclusive o do registro
  da conferência (`conferencia_da_rota`).

## 14. Artefatos

| | |
|---|---|
| Painel | *(28/09)* **Governante na medição:** o painel v2, com os pins do §4 (linha "Executor v2 e painel v2", abaixo). Histórico: `artefatos/painel_pesquisa_rank03b/painel.duckdb` + `manifesto_painel.json` (o painel sem correções tem `manifesto_painel_sem_correcoes.json` próprio desde 16/09) |
| Correções | *(28/09)* **Governante:** por conta (linha "Correções por conta", abaixo). `corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv`, por documento, continua como entrada, com zero linhas |
| Gates estruturais | *(28/09)* **Governante:** `artefatos/executor_v2_rank03b/estrutural.json`. Históricos: `artefatos/painel_pesquisa_rank03b/gates_g0_g1.json` (governante até 27/09), `gates_g0_g1_sem_correcoes.json`, `gates_g0_g1_diagnostico_execucao1.json` |
| Medições estruturais | `artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json` (`scripts/medicoes_estruturais_rank03b.py`) |
| Auditor | `scripts/auditar_rank03b_consumo_operacional.py` (a medição de T1/T2 lerá o painel de pesquisa por `scripts/gates_painel_pesquisa_rank03b.py`). **Cumpridos em 17/09:** IC do acerto do B0, partição de T1, AUC zero em T2, correções só validadas. **Ainda não cumpridos, e exigidos antes de congelar:** o executor v2 com a ordem do §6 e as decisões de 26/09 (§§3.2, 5.1, 5.5, 6.1, 8.1 e 12-bis), testado em sintético e conferido de forma independente; a resolução estrutural do G0, num painel com pins novos (§4) |
| Decisões de 26/09 | `resultados/registro_decisoes_v2_rank03b_2026-09-26.md` (motivos e alternativas); `resultados/adendo_o1_rank03b_2026-09-26.md` (exceção protetiva e identidade contábil) |
| ROTA-2 (27/09) | `artefatos/rota_prova_rank03b_v2_2026-09-27/` (`evidencias.jsonl`, `pin.json`, `resumo.json`, `conferencia.json`); a ROTA-1, sem manifesto, fica em `artefatos/rota_prova_rank03b_2026-09-27/` (`scripts/rota_prova_rank03b.py`) |
| Correções por conta | `corpus/cvm/painel_pesquisa_rank03b/correcoes_escala_por_conta.csv` (`scripts/manifesto_rota1_rank03b.py`; consumidor `scripts/correcoes_por_conta_rank03b.py`) |
| Executor v2 e painel v2 | `artefatos/executor_v2_rank03b/estrutural.json` (G0/G0.5/G1 sem rótulo e pins propostos); `artefatos/painel_pesquisa_rank03b_v2/painel.duckdb` + `manifesto_painel.json` (`scripts/executor_v2_rank03b.py`). *(27/09: cumpridos os dois itens "ainda não cumpridos" da linha do auditor; pins no §4.)* |
| Verificações da revisão | `artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json` (`scripts/verificacoes_revisao_final_rank03b.py`) |
