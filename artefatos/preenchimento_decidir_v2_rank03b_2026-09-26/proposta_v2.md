# Proposta de preenchimento — decisões pendentes do v2 (Rank 3-B)

**Data:** 2026-09-26

> **PROPOSTA de agente; não é decisão nem aprovação do responsável; o rascunho não foi alterado.**

**Versão 2.** Corrige os dois erros de fato apontados pelo revisor independente
(E1 no §5.1, E2 no §5.5) e trata as ressalvas do parecer da fase 2 (PAR). As
escolhas dos sete itens não mudam. Nas duas divergências (§5.5 e §6.1), a
alternativa do revisor aparece com os argumentos dele e uma resposta minha. A
v1 fica preservada em `proposta_v1_revisada.md` (SHA-256 `5c0e72b9…31e0`). O
que mudou, item a item, está no fim, em "Registro da revisão".

---

## 0. Como ler este documento

### 0.1 Escopo

Sete pontos. Seis estão marcados **[DECIDIR]** no rascunho v2: §3.2
(seguradoras), §5.1 (leitura de G0.1), §5.5 (G0.5), §6.1 (grade de D), §8.1
(suporte da AUC intra) e o bloco "Alcance da prova de escala" do §12-bis
(RASC:15-18, 136, 193, 220, 278, 334, 542). O sétimo é a exceção protetiva ao
O1 proposta em DEC:15-48.

### 0.2 Convenções

- **Fontes** no formato `ALIAS:linha`, pela tabela abaixo. O artefato JSON é
  citado pelo caminho da chave. O CPC 03 é fonte externa e não está no
  repositório (ver §10, item 1).
- **Fato** é o que a fonte citada diz ou o que o código faz. **Julgamento** é
  inferência ou escolha minha. Toda justificativa separa os dois.
- **Texto pronto** é o bloco que substituiria o marcador depois de aprovado;
  `[data]` fica para o responsável. Nada foi aplicado ao rascunho.
- **Nova** marca opção que não está no rascunho nem em DEC.

| Alias | Arquivo (relativo à raiz do repositório) |
|---|---|
| RASC | `resultados/pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md` |
| V1 | `resultados/pre_registro_rank03b_consumo_operacional_2026-09-11.md` |
| DEC | `resultados/decisoes_executor_v2_rank03b_2026-09-26.md` |
| PEND | `resultados/correcao_pendencias_geom1_rank03b_2026-09-26.md` |
| CPEND | `resultados/contratos_pendencias_geom1_rank03b_2026-09-26.md` |
| LB | `resultados/contratos_lote_b_rank03b_2026-09-16.md` |
| LC | `resultados/contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md` |
| LCR | `resultados/painel_pesquisa_rank03b_lote_c_2026-09-16.md` |
| CONF17 | `resultados/conferencia_pre_treino_rank03b_2026-09-17.md` |
| CRF | `resultados/contratos_correcao_rf01_rf08_rank03b_2026-09-17.md` |
| CRF18 | `resultados/correcao_crf01_crf03_rank03b_2026-09-18.md` |
| R15 | `resultados/contratos_correcao_r1_r5_rank03b_2026-09-12.md` |
| ALC | `resultados/alcance_geom1_rank03b_2026-09-24.md` |
| CALC | `resultados/contratos_alcance_geom1_rank03b_2026-09-24.md` |
| CRAG | `resultados/contratos_correcao_rag_alcance_geom1_rank03b_2026-09-25.md` |
| RAG | `resultados/correcao_rag_alcance_geom1_rank03b_2026-09-25.md` |
| ARAG | `resultados/adendo_correcao_rag_alcance_geom1_rank03b_2026-09-25.md` |
| LEV | `resultados/pendencias_desbloqueio_treino_dfc_2026-09-15.md` |
| BECOS | `resultados/becos_sem_saida.md` |
| AG | `AGENTS.md` |
| MEM | `MEMORY.md` |
| AUD | `scripts/auditar_rank03b_consumo_operacional.py` |
| GAT | `scripts/gates_painel_pesquisa_rank03b.py` |
| VER | `scripts/conferir_alcance_geom1_rank03b.py` |
| PPR | `scripts/painel_pesquisa_rank03b.py` |
| SRC | `src/dados_estruturados.py` |
| REV24 | `artefatos/alcance_geom1_rank03b_2026-09-24/revisao/conferir_alcance_executado.py` (código preservado da revisão de 24/09) |
| REC25 | `artefatos/alcance_geom1_rank03b_2026-09-24/revisao/conferir_alcance_reconferencia.py` (código preservado da reconferência de 25/09) |
| MED | `artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json` (por chave) |
| PAR | `artefatos/preenchimento_decidir_v2_rank03b_2026-09-26/parecer_fase2_revisor.md` |

### 0.3 O que li e o que vi — exposição deste agente

- Li o rascunho inteiro, com o §11 antes de decidir. Números de desfecho que
  ele expõe e que, portanto, vi: taxa do evento no painel compartilhado
  **0,0526 → 0,0530**, "3" observações com `y` diferente e "−5" em FCO TTM não
  positivo (RASC:384-391); **≈ 2.865 a 2.867** descartes por `FCO_TTM ≤ 0` no
  painel de pesquisa (RASC:397-402). MEM:1149-1151 repete a taxa. Não abri o
  relatório de 15/09 que a publicou.
- Números estruturais vistos: os do §11.3 (RASC:416-457) e, em MED, só as
  chaves e os campos de plano de contas, seguradoras, troca de método,
  identidades contábeis, N2 e rótulos de escala. Nenhum valor de FCO.
- Nesta segunda rodada li, além do parecer do revisor, só código e texto:
  SRC:1318-1350 e 1478-1510, PPR:490-515, VER:810-868, REV24:110-140 e
  REC25:136-152, os adendos 2 e 3 em RAG:309-450, e o campo
  `rotulos_de_escala` do MED. Nenhum número de desfecho novo.
- Não abri painel DuckDB, pacote RAD, PDF nem `corpus/holdout_2T2026`; não
  executei script do projeto; não calculei nada sobre dado real, nem contagem
  estrutural. As estimativas de ordem de grandeza deste documento são limites
  por construção, feitos à mão sobre números já publicados, e estão marcadas.
- **Nenhum número de desfecho orientou escolha.** Quando um número estrutural
  já visto é relevante para uma escolha, o item o declara.

### 0.4 Estado de partida, comum aos sete itens

- Fato: o rascunho não está congelado; nenhum T1, T2 ou baseline foi medido
  sobre dado real (RASC:3-7, 377-381).
- Fato: versão vigente (18/09, execução 4b, regra v4): 405 documentos
  indecidíveis, zero correções; **G0 reprovado** com G0.3 = 132 saltos
  (0,5875% > 0,5%); G1 estrutural 10.748 observações em 502 companhias; G0.5
  proposto 82/22.088 = 0,3712%; G0.1 literal 117 trimestres em 49 companhias
  (RASC:422-428). Para G0.3 passar, no máximo 112 saltos (ALC:193-194).
- Fato e julgamento: **nenhuma das sete decisões foi escolhida pelo efeito no
  G0.3.** Seis não tocam o G0.3 no estado vigente. A do §3.2 muda o universo e,
  com ele, o numerador e o denominador do G0.3; esse efeito não foi medido, e o
  texto do §3.2 manda publicá-lo. Nada aqui resolve a reprovação: resolvê-la
  exige correções de escala com prova (DEC:106-113).
- Fato: os pins do rascunho — digest `6ca635a9…`, manifesto `13520e61…`
  (RASC:158-161) — descrevem um painel com G0 sabidamente reprovado. Aprovar as
  sete decisões não é congelar o pré-registro (ver §8, item 9).

---

## 1. §3.2 — Seguradoras

**Pergunta.** A exclusão estrutural da v1 (`ll3_09_%` ou `is_banco`) deve
alcançar também o plano de seguros `ll3_13_%`? (RASC:136-152; LC:26-30:
"Excluí-las é decisão do pré-registro novo, a tomar antes de medir".)

**Opções.**
- **A** (rascunho, proposta; RASC:145-147): acrescentar
  `OU plano_contas LIKE 'll3_13_%'` à exclusão.
- **B** (rascunho, alternativa; RASC:148): manter as três companhias e
  declarar.

**Proposta: A.**

Texto pronto, que substitui RASC:136-152:

```markdown
### 3.2 Seguradoras (decidido em [data] pelo responsável)

Exclui-se também a companhia com `plano_contas LIKE 'll3_13_%'`, o plano de
contas de seguros da CVM. A regra de população passa a ser:

    EXCLUI  se  plano_contas LIKE 'll3_09_%'
            OU  plano_contas LIKE 'll3_13_%'
            OU  is_banco = TRUE

É o critério estrutural da v1 (§3) aplicado a outro plano financeiro, e é
conservador: perde companhias, não contamina a população. Medido antes da
decisão (`medicoes_estruturais.json`, `fonte`): 3 companhias no plano
`ll3_13_48e4cd07`; em `023159` e `024180` a `6.01` aparece como "Caixa
Líquido Atividades Seguradora/Resseguradora" (24 linhas). O executor aplica
a exclusão sobre a coluna `plano_contas` já carregada; o painel não muda.

A exclusão muda o universo e, com ele, o numerador e o denominador do G0.3.
O executor publica quantos dos saltos do G0.3 pertencem às companhias
excluídas e quantas linhas de ativo válidas elas tinham, para que nenhuma
variação do G0.3 venha de remoção sem declaração (§4.4, regra 9).

Não há controle setorial: seguradoras, holdings financeiras ou outras
entidades financeiras registradas em plano diferente de `ll3_09`/`ll3_13`
não são alcançadas por esta regra, e nenhuma afirmação setorial está no
escopo.
```

**Justificativa.**

Fatos:
1. A v1 define a população como "companhia não financeira" e a
   operacionaliza pelo plano de contas, com a regra explícita de que, para
   "não financeira", "super-incluir na exclusão é **conservador**: perde-se
   algumas companhias, não se contamina a população" (V1:62-68, 96-111).
2. O universo de 700 tem 697 companhias em planos `ll3_11_*` e 3 no plano
   `ll3_13_48e4cd07` (MED `fonte.companhias_por_plano`). O lote C descreve as
   três como seguros (LC:26-30). Em `023159` e `024180` a `6.01` aparece em 24
   linhas como "Caixa Líquido Atividades Seguradora/Resseguradora" (MED
   `fonte.companhias_com_6_01_de_seguradora` e `fonte.descricoes_6_01`;
   LB:294-296).
3. A conferência independente de 17/09 julgou a exclusão "coerente com o
   universo não financeiro declarado" (CONF17:292-294).
4. O painel "não decide elegibilidade: carrega as 700 e marca
   `plano_contas`" (LC:26-27). Excluir é filtro do executor, sem reconstruir
   o painel.
5. Linha descoberta pelo residual não se remove para salvar o teste
   (AG:806-809).

Julgamentos:
- Seguradora aplica reservas técnicas em ativos financeiros e costuma
  classificar parte desse giro nas atividades operacionais. "Consumo
  operacional de caixa" de seguradora é outro objeto econômico. A exclusão
  alinha a operacionalização ao estimando que a v1 já declarou; não cria
  estimando novo.
- A opção B só teria mérito se houvesse razão para estudar seguradoras junto
  com não financeiras, e nenhum documento a apresenta. O custo de A é pequeno
  (3 de 700, cerca de 0,43%) e é pago antes de medir.
- A exclusão não foi escolhida pelo efeito no G0.3, que não foi medido. Como
  ela tira companhias do denominador e, possivelmente, saltos do numerador,
  publicar esse efeito impede que um ganho no G0.3 venha de remoção sem
  declaração (fato 5).

**O que muda.**
- População: de 700 para 697 companhias no universo, antes dos demais filtros.
- Gates: os números do §11.3 foram medidos com as três e passam a históricos;
  G0 e G1 precisam ser medidos de novo no universo decidido, com a
  publicação do efeito da exclusão no G0.3.
- Amostra: saem as observações das três.
- Executor: filtro de universo, com contraprova (companhia sintética
  `ll3_13` excluída; `ll3_11` mantida).
- O painel não muda.

**O que não se pode alegar.** Que a população é estritamente não financeira;
que todas as seguradoras ou entidades financeiras foram excluídas (o critério
só alcança `ll3_09`, `ll3_13` e `is_banco`); qualquer afirmação setorial, já
que não há controle setorial (V1:113-116; RASC:133-134); que seguradoras se
comportam de outro modo quanto ao alvo, porque nada foi medido; que uma
variação do G0.3 depois da exclusão é melhora de dado.

**Riscos e custo.** Custo: 3 companhias. Risco: se alguma das três não for
seguradora, a perda é conservadora. A atividade da terceira companhia não é
identificada nos documentos lidos além de "seguros" (LC:26-30).

**Natureza:** técnica (operacionalização da população já declarada), com
efeito de população. **Confiança:** alta.

**Exposição.** À vista: contagens estruturais (3 companhias, 24 linhas) e a
taxa-base agregada do painel compartilhado, que não separa planos
(RASC:150-152, 384-396). Nenhuma contagem de evento por companhia ou por plano
foi vista, nem o número de saltos do G0.3 dessas companhias. A escolha decorre
do universo declarado na v1 e seria a mesma para qualquer taxa-base.

**O que mudaria a escolha.** Evidência de que alguma companhia `ll3_13` não é
seguradora (a regra passaria a ser por atividade, com fonte); decisão de
estudar entidades financeiras (outro estimando, outro pré-registro); ou
`SETOR_ATIV` disponível (V1:89-95), o que permitiria regra setorial, decidida
antes de medir.

---

## 2. §5.1 — Leitura de G0.1

**Pergunta.** G0.1 proíbe só a soma (duplicação) de `DFC_MD` e `DFC_MI` do
mesmo período, que é a leitura por unicidade, ou proíbe também o trimestre
derivado de acumulados apresentados por métodos diferentes, que é a leitura
literal? (RASC:193-218; LC:422-425.)

Fato que o responsável precisa ter à vista antes das opções: a v1 escreve a
verificação como "Nenhuma observação usa `DFC_MD` e `DFC_MI` para o mesmo
(companhia, trimestre)", com origem do risco "somar os dois duplica o caixa" e
limiar "0 casos somados" (V1:130). A frase da verificação é mais larga que a
paráfrase do rascunho, "sem soma" (RASC:185, 195). A origem e o limiar da
mesma linha falam de soma, e o G0.1 que a v1 executou contava só grupos com
mais de um demonstrativo (AUD:407-415).

**Opções.**
- **A** (rascunho, proposta; RASC:204-208): unicidade; derivação entre
  métodos permitida e declarada.
- **B** (rascunho, "alternativa A"; RASC:209): leitura literal. G0 reprova e a
  rodada para.
- **C** (rascunho, "alternativa B"; RASC:210-212): leitura literal como
  censura. Os trimestres derivados entre métodos viram perda inventariada.

**Proposta: A**, com as condições escritas no texto.

Texto pronto, que substitui RASC:193-218:

```markdown
### 5.1 G0.1 — leitura por unicidade (decidido em [data] pelo responsável)

G0.1 verifica que nenhum trimestre consumido pela amostra tem valor obtido
somando ou justapondo `DFC_MD` e `DFC_MI` do **mesmo período**, e que há um só
valor de FCO por (companhia, trimestre). Limiar: 0. É o risco que a v1
declarou para o item: "somar os dois duplica o caixa", "0 casos somados"
(v1, §4).

O trimestre **derivado** de acumulados do mesmo exercício apresentados por
métodos diferentes é **permitido**: o caixa líquido das atividades
operacionais é o mesmo total pelos dois métodos (CPC 03 (R2), itens 18–20A),
e a `6.01` é conta fixa com a mesma descrição nos dois (lote B, M1). A
permissão não dispensa nenhuma outra regra — mesma conta, consolidado, mesmo
exercício, banda de 80–100 dias, sem `PENÚLTIMO` como antecedente,
disponibilidade pelo operando mais tardio (F1–F6, P1–P4) — nem o G0.5. O
método de cada operando fica na linhagem, e G0 publica a contagem de
trimestres válidos derivados entre métodos e de companhias envolvidas.
Contraprovas do executor: MD e MI do mesmo período somados → G0.1 reprova;
derivação entre métodos → aceita e marcada na linhagem.

A leitura literal da v1 ("nenhuma observação usa `DFC_MD` e `DFC_MI` para o
mesmo (companhia, trimestre)") foi considerada e não adotada: a origem e o
limiar da mesma linha tratam de soma, e o G0.1 que a v1 executou contava só
pares (companhia, trimestre) com mais de um demonstrativo entre as linhas
(`scripts/auditar_rank03b_consumo_operacional.py`, `gate_g0`). Um trimestre
derivado entre métodos é uma linha com um só demonstrativo e nunca foi
contado. A unicidade é a leitura que a v1 de fato aplicou.
```

Linha da tabela do §5, que substitui RASC:185:

```markdown
| G0.1 | Um só valor de FCO por (companhia, trimestre); nenhuma soma de `DFC_MD` e `DFC_MI` do mesmo período | 0 | Leitura por unicidade (§5.1); derivação entre métodos permitida e contada |
```

**Justificativa.**

Fatos:
1. O risco que a v1 declarou para G0.1 é a duplicação: "a sobreposição não é
   vazia (5 companhia–trimestres); somar os dois duplica o caixa" (V1:130;
   AG:605-607). A abertura do G0 diz que "cada item vem de defeito já medido"
   (V1:125-126).
2. No painel de pesquisa nenhum documento traz os dois métodos (MED
   `fonte.documentos_com_dfc_md_e_dfc_mi` = 0; LB:121), e o G3-pp garante um
   valor por (companhia, trimestre) (LC:149-150; GAT:249-252). O risco de
   duplicação é nulo por construção.
3. 53 companhias trocam de método (MED `fonte.companhias_que_trocam_de_metodo`;
   LB:121). No painel de pesquisa, parear acumulados por demonstrativo
   "fabrica 'sem antecedente'" nelas (LC:188). No painel compartilhado, que é o
   da v1 (V1:118), as duas derivações se comportam de modo diferente:
   - a do 2T e do 3T particiona por demonstrativo (SRC:1342-1346). Na
     simulação dessa derivação, 61 dos 131 grupos sem antecedente tinham
     antecedente no outro método (MED `n2_no_recorte_do_candidato`;
     MEM:1072-1074);
   - a do 4T junta a DFP anual e o ITR de nove meses por companhia, chave de
     pareamento e início do exercício, sem olhar o demonstrativo
     (SRC:1500-1504; a chave de pareamento não contém o demonstrativo,
     SRC:1322-1325), e grava o demonstrativo do anual (SRC:1486).

   Um 4T derivado entre métodos era, portanto, possível no painel da v1. Se
   existiu de fato não foi verificado: exigiria abrir o DuckDB.
4. A `6.01` é conta fixa (`ST_CONTA_FIXA = 'S'` em 45.045 de 45.045 linhas) e
   tem a descrição "Caixa Líquido Atividades Operacionais" nas 700 companhias
   (LB:117; MED `fonte.conta_fixa` e `fonte.descricoes_6_01`).
5. A conferência independente recomendou a leitura por unicidade, citando o
   CPC 03 (R2), itens 18–20A, "preservando a comparabilidade dos operandos e
   sua linhagem; isso não valida automaticamente qualquer par documental"
   (CONF17:284-290). O levantamento de 15/09 descreve o G0 como "sem uso duplo
   de métodos" e o critério de D4 como "ausência de duplicação entre métodos"
   (LEV:151-153, 218).
6. O lote C publicou um critério de refutação, "mostrar companhia cujo FCO
   total difira entre métodos no mesmo período" (LCR:258). Ele nunca foi
   testado, e, como nenhum documento traz os dois métodos (fato 2), não pode
   ser testado dentro do mesmo documento. É **ausência de teste, não
   evidência** a favor da invariância.
7. O G0.1 que a v1 executou conta só pares (companhia, trimestre) com mais de
   um demonstrativo entre as linhas (AUD:407-415). Um trimestre derivado entre
   métodos é uma linha com um só demonstrativo, e nunca foi contado.

Julgamentos:
- Pelo CPC 03 (IAS 7), os métodos direto e indireto diferem na apresentação
  da seção operacional; o total do caixa líquido das atividades operacionais é
  o mesmo número. Subtrair acumulados do mesmo exercício apresentados por
  métodos diferentes é aritmética entre medidas da mesma grandeza, desde que
  valham as demais condições: mesma conta, perímetro, exercício, vintage e
  banda. A norma é fonte externa, não conferida aqui (§10, item 1); o fato 6
  não a reforça.
- **A unicidade não é reinterpretação: é a leitura que a v1 de fato aplicou**
  (fato 7). A frase larga da verificação (V1:130) nunca foi executada à letra:
  mesmo no painel da v1, onde um 4T derivado entre métodos era possível (fato
  3), o G0.1 implementado não o contaria. O responsável deve saber, ainda
  assim, que a letra da v1 favorece B ou C mais do que a paráfrase do rascunho
  sugere.
- B reprovaria G0 por algo que não é defeito de dado. C removeria até 117
  trimestres em 49 companhias, mais as observações cujas janelas ou rótulos
  dependem deles, sem defeito demonstrado.
- Risco residual: troca de método que coincida com reclassificação entre
  atividades (por exemplo, juros pagos movidos de operacional para
  financiamento) mistura políticas contábeis na subtração. É risco de toda
  derivação que atravesse mudança de política dentro do exercício, não
  específico da troca de método, e não há evidência no repositório de que
  ocorra. Fica declarado, não vira regra.

**O que muda.**
- População: nenhuma mudança em relação ao painel vigente, e os 117
  continuam. Em relação a C, preserva-os.
- Gates: G0.1 = 0 no estado vigente (RASC:185).
- Executor: G0.1 como unicidade mais ausência de soma MD+MI do mesmo período;
  contagem publicada dos derivados entre métodos (o campo `metodos` já existe,
  GAT:462-471); as duas contraprovas do texto.
- §13 do rascunho: acrescentar "valor de FCO obtido somando ou justapondo
  `DFC_MD` e `DFC_MI` do mesmo período".

**O que não se pode alegar.** Que cada trimestre derivado entre métodos foi
conferido; que a invariância do total foi verificada nos dados (o teste de
LCR:258 nunca rodou); que troca de método nunca coincide com reclassificação;
que G0.1 = 0 certifica a comparabilidade dos operandos.

**Riscos e custo.** Risco: o residual acima, não medido. Custo: nenhum em
população; implementação pequena.

**Natureza:** técnica (norma contábil e leitura que a v1 executou).
**Confiança:** alta.

**Exposição.** À vista: 117 trimestres em 49 companhias (RASC:201-202,
214-216), 53 companhias que trocam de método, 61 grupos N2 com antecedente no
outro método e a taxa-base (RASC:384-396). A escolha não depende das
contagens: decorre da invariância do total, do risco que a v1 declarou e do
G0.1 que ela executou. Com 10 ou 1.000 trimestres assim, a leitura seria a
mesma.

**O que mudaria a escolha.** Um caso da mesma companhia, período e perímetro
com totais de `6.01` diferentes por método (o critério de LCR:258, que exigiria
fonte além do formulário, por exemplo reapresentação no outro método);
evidência de que trocas de método coincidem sistematicamente com
reclassificação entre atividades; ou decisão do responsável de que a letra da
v1 governa. Nesse último caso, C (censura) é menos destrutiva que B, que para a
rodada por algo que não é defeito.

---

## 3. §5.5 — G0.5: derivação com escalas não adjudicadas

**Pergunta.** Como tratar o trimestre de FCO válido cujos operandos diferem na
escala declarada ou aplicada, com algum operando sem veredito decidido: gate
de tolerância, nenhum gate ou outra coisa? (RASC:220-258; CRF:132-141;
CONF17:178-204.)

**Opções.**
- **A** (rascunho, proposta; RASC:243-249): G0.5 decisivo; fração de
  trimestres válidos na população de risco ≤ 0,5%.
- **B** (rascunho, alternativa; RASC:258): não acrescentar; declarar a lacuna.
- **C** (**nova**, proposta): censura como regra de dado. Esses trimestres
  não entram em janela nem em rótulo; G0.5 vira verificação decisiva de uso
  zero, com a perda inventariada antes de montar `y`.
- **D** (**nova**, considerada e não proposta): G0.5 decisivo com tolerância
  zero, sem censura. G0 reprova enquanto houver um trimestre desses.
- **E** (**nova**, considerada e não proposta por padrão): C estendida.
  Censurar também a observação cuja janela ou rótulo **some** trimestres de
  documentos com escalas aplicadas diferentes, mesmo sem derivação entre eles,
  quando algum documento não tem veredito para o FCO. **É a alternativa do
  revisor (C+E)**, apresentada abaixo com os argumentos dele.

**Proposta: C.**

Texto pronto, que substitui RASC:220-258:

```markdown
### 5.5 G0.5 — derivação com escalas não adjudicadas: censura (decidido em [data] pelo responsável)

**População de risco** (G5.1, 17/09): trimestre de FCO válido cujos
operandos diferem na escala **declarada ou aplicada** e em que algum operando
não tem veredito de escala decidido **para o FCO** (§12-bis).

**Regra de dado.** Trimestre da população de risco recebe o estado
`escala_heterogenea_nao_adjudicada` e não é usado: não entra na janela de
oito trimestres, no TTM, em `sd8`, na contagem de trimestres negativos nem em
q1–q4, e não gera data D (§6.1). A observação que precisaria dele é censurada
pela regra do §2.1, nunca deslocada; se o trimestre for do rótulo, `Y` é
indefinido (§2). Os documentos operandos continuam no painel com a escala
declarada (§4); seus ativos continuam em G0.3; seus acumulados continuam
servindo de operando onde a derivação é homogênea.

**G0.5 (decisivo).** Nenhuma observação da amostra tem, na linhagem da
janela ou do rótulo, trimestre nesse estado. Limiar: 0. Com a amostra montada
sem rótulo e antes de montar `y`, publicam-se:
- trimestres censurados, por configuração (declaradas × aplicadas) e por
  companhia;
- observações (companhia, D) perdidas por esse motivo, com motivo próprio no
  inventário de descartes;
- companhias que perdem ao menos uma observação e companhias que saem
  inteiras da amostra por esse motivo, cada contagem com a fração sobre as
  companhias da amostra sem rótulo antes da censura.

Contraprovas do executor: trimestre heterogêneo com operando sem veredito →
censurado; com os dois operandos decididos para o FCO → usado; construtor que
use trimestre censurado → G0.5 reprova.

**O que esta regra não é.** Não é tolerância e não reutiliza o 0,5% do G0.3.
Não corrige escala nem afirma que os trimestres censurados estavam errados.
Não alcança a soma de trimestres de escalas diferentes que não foram
derivados um do outro (por exemplo, o 4T de um exercício e o 1T isolado do
seguinte); o G0.3 só vê esses casos quando há transição detectável no ativo.
Também não alcança erro de escala **consistente**, sem transição — por
exemplo, companhia que declara `UNIDADE` em todos os documentos com números
em milhares: **esse erro não é coberto por gate nenhum**. Ele afeta os três
componentes de nível (`fco_ttm_em_D`, `sd8_fco_isolado`, `ativo_total_em_D`),
não as razões, a contagem de trimestres negativos nem o rótulo.
```

Linha nova na tabela do §5 (RASC:183-189):

```markdown
| G0.5 | Nenhum trimestre com escalas heterogêneas não adjudicadas para o FCO usado em janela ou rótulo | 0 | Censura (§5.5); perda publicada antes de montar `y`, em observações e em companhias |
```

**Justificativa.**

Fatos:
1. O rascunho descreve o risco: um trimestre derivado de acumulados de escalas
   heterogêneas não adjudicadas "pode estar errado por mil — e um trimestre
   assim muda o sinal do TTM, que define a elegibilidade e três componentes de
   T1" (RASC:222-225). O rótulo também sai de trimestres isolados: `S1` e `S2`
   são somas de FCO trimestral (RASC:85-90).
2. A classe de defeito é demonstrada e frequente: 132 saltos de ativo no
   universo (RASC:425); no painel inteiro, 123 de 137 transições de escala com
   valor bruto contínuo (AG:432-434); uma correção com "prova" já introduziu
   erro de 1.000× (ESC-0101, CONF17:41-74).
3. O limiar de 0,5% da opção A "é política nova (outro evento, outro
   denominador)" e não herda a validação do G0.3 (RASC:236-241, 245-247;
   CRF:139-141; CONF17:201-204).
4. Cada trimestre de FCO entra em até oito janelas de features
   (`JANELA_SD = 8`; AUD:59, 729-741) e em até quatro rótulos (q1–q4;
   AUD:743-773). Uma linha de ativo entra na observação em que é a mais
   recente disponível (AUD:784-792).
5. Estado vigente: 82 trimestres na população de risco, entre 22.088 válidos
   (RASC:427; LCR:81), numa amostra estrutural de 10.748 observações
   (RASC:426). Sem correções, a heterogeneidade declarada só existe em
   companhias de rótulo misto: 54, com 189 trechos, dos quais 71 de um só
   documento (MED `rotulos_de_escala`).
6. Há 17 companhias só `UNIDADE`, com 400 documentos (MED
   `rotulos_de_escala`), não adjudicadas; presumi-las certas foi alternativa
   rejeitada pelo lote B (LB:264).
7. Censura como tratamento de dado já existe no desenho: o que não encadeia "é
   censurado, nunca deslocado" (RASC:103-105); `Y` é indefinido se qualquer um
   dos quatro FCO falta (RASC:90); a política de disponibilidade "não vaza;
   custa perda" (RASC:113-114). A regra 9 do §4.4 admite "congelar a
   quarentena antes de um teste novo" (AG:806-809).

Exemplo sintético do mecanismo do fato 1 (não é dado; conferido pelo revisor,
PAR:50): acumulado verdadeiro de FCO de R$ 300 mil em junho e R$ 500 mil em
setembro, o que dá 3T isolado de +R$ 200 mil. Se o ITR de setembro declara
`UNIDADE` com números em milhares (o modo de erro descrito em AG:429-431) e o
de junho declara `MIL` corretamente, o painel tem 300.000 e 500 reais, e o 3T
derivado sai 500 − 300.000 = **−299.500**: sinal trocado, módulo da ordem do
acumulado anterior. No erro inverso (junho errado, setembro certo), sai
500.000 − 300 = **+499.700**: sinal certo, módulo 2,5 vezes o verdadeiro. Os
dois casos podem mudar o sinal do TTM (elegibilidade) e de `S1`/`S2`
(rótulo).

Julgamentos:
- **A tolerância de A é contada no denominador errado.** Na grade regular, um
  trimestre contamina da ordem de uma dezena de observações (até 8 janelas + 4
  rótulos, fato 4), e uma linha de ativo da ordem de uma. O mesmo 0,5% é muito
  mais permissivo em G0.5 do que em G0.3. **Limite grosseiro por construção,
  não medição:** 82 trimestres × 12 ≈ 1.000 observações, cerca de 9% das
  10.748, antes de descontar sobreposição. O teto de A (0,5% de 22.088 ≈ 110
  trimestres) admitiria cerca de 1.300 observações, cerca de 12%.
- **A contaminação empurra na direção de aprovar.** Erro de medida ou de
  classificação sem relação com o rótulo tende a atenuar associações.
  Ilustração, não medição: se uma fração `c` das observações tiver janela ou
  rótulo sem relação com o componente, a taxa de cada faixa tende a
  `(1 − c)·r_faixa + c·r̄`, e a amplitude a `(1 − c)` vezes a verdadeira. Com
  `c = 9%`, uma amplitude verdadeira de 0,165 aparece como cerca de 0,150; com
  12%, cerca de 0,145, na zona cinzenta. Em T2, as duas AUCs se aproximam de
  0,5 e a lacuna encolhe. Contaminação real não é aleatória e o efeito pode
  ser outro; a direção esperada é a da aprovação, o lado oposto da previsão
  registrada no §1 do rascunho. O revisor aceita essa direção no componente
  previsto: um trimestre errado por mil infla o `sd8` e empurra a observação
  para a faixa "perto de zero" (PAR:103-105).
- **C troca contaminação por perda, e a perda é inventariável sem rótulo.**
  As cerca de 1.000 observações do limite acima são as mesmas nos dois casos:
  contaminadas sob A, fora da amostra sob C. A perda é contagem estrutural,
  permitida pelo O1.2 (LB:93-95) e publicável antes de montar `y`. Como a
  censura não tem teto, o texto manda publicar também a perda em companhias,
  não só em observações.
- **C não é "passar G0 por remoção".** A proibição do lote C (G4-pp,
  LC:152-154; RASC:177) é de excluir **documento** para fazer G0.3 passar. C
  não exclui documento, não toca no ativo nem em G0.3 e não decide o veredito
  de G0 por esses trimestres. Suspende uma **operação** que o próprio pipeline
  faz, a subtração entre acumulados cuja unidade não está estabelecida.
- **Por que não D:** sob a regra v4, nenhum documento pode ser decidido para o
  FCO (nenhum fluxo `6.x` prova escala; RASC:527-529), então D bloqueia G0
  indefinidamente por um motivo que C já neutraliza. A escolha entre C e D é
  entre medir sem esses trimestres ou não medir.
- **Por que C e não C+E nesta rodada:** a diferença entre as duas é de alcance
  e de perda, não de princípio (ver a resposta à divergência, abaixo). C
  cobre a população contratada em G5.1 (CRF:134-137) e o mecanismo que o
  rascunho nomeou, o trimestre fabricado por subtração (RASC:222-225). E muda
  o objeto do G0.5 de "derivação" para "combinação de documentos", e sua perda
  não tem limite publicado.
- **Erro consistente, sem transição, fica sem gate** (fato 6). Pelas
  definições dos componentes (V1:162-169), um fator de 1.000 igual em todos os
  documentos da companhia se cancela nas razões (`fco_ttm_sobre_sd8`,
  `fco_ttm_sobre_ativo`), não muda sinais (contagem de negativos,
  elegibilidade, `S1`, `S2`) e afeta só os três componentes de nível. Nem C
  nem E o alcançam; só adjudicação com prova (§12-bis).
- Efeito colateral declarado: se uma companhia declarar `UNIDADE` no ITR e
  `MIL` na DFP todos os anos (o padrão de AG:429-431), todo 4T derivado é
  heterogêneo. Sob C, nenhuma janela de oito trimestres contíguos se forma e a
  companhia sai inteira da amostra. Sob A, fica inteira, com 4T da ordem do
  FCO anual e 1T a 3T mil vezes menores.

**Divergência do revisor — alternativa C+E (PAR:45-58).** O revisor concorda
com G0.5 decisivo, com "decidido" medido pelo FCO e com a rejeição do 0,5%
contado em trimestres (PAR:46-50). Ele adotaria C+E, com três argumentos:
1. **O resíduo atinge rótulo e elegibilidade.** Um 1T isolado mal rotulado
   entra no TTM e em `S2` sem que haja trimestre heterogêneo na mesma janela.
   Há 71 trechos de um só documento em companhias mistas (MED
   `rotulos_de_escala.trechos_em_companhias_mistas`) (PAR:52).
2. **O argumento da v1 contra E não separa E de C.** A v1 desta proposta dizia
   que E "sobrepõe-se à tolerância que a v1 congelou no G0.3" (V1:132,
   135-137). Isso vale igualmente para C: os trimestres que C censura ficam
   sobre as mesmas transições dentro do exercício que o G0.3 conta (PAR:53).
3. **A perda de E pode ser medida antes de decidir,** como contagem sem
   rótulo (O1.2), como a proposta admite para C (PAR:54).

**Minha resposta, curta.** O argumento 2 procede, e o retirei: a
sobreposição com a tolerância do G0.3 vale para C e para E. Os argumentos 1 e 3
também procedem: o resíduo muda sinais de soma (exemplo: 4T correto de −30 mil
somado a 1T de +50 mil registrado como +50 dá `S1` negativo, quando o
verdadeiro é positivo), e as duas perdas são contagens estruturais medíveis
com `calcular_rotulo=False` (LB:93-95; AUD:655-662). Mantenho C como proposta
desta rodada porque a perda de E não tem limite publicado e E redefine a
população contratada em G5.1 (CRF:134-137). Recomendo ao responsável medir as
duas perdas antes de decidir. Se a perda adicional de E não ameaçar os mínimos
do T1 (500 observações e 30 companhias por componente, RASC:307-309), E é a
escolha mais coerente com o argumento de contaminação deste mesmo item. Texto
pronto de E, para acrescentar ao bloco de C se o responsável a preferir:

```markdown
**Extensão (C+E).** Também é censurada a observação cuja janela de oito
trimestres, cujo ativo em D ou cujos q1–q4 combinem valores de documentos
com escalas **aplicadas** diferentes, quando algum desses documentos não tem
veredito de escala decidido para o FCO. A perda é publicada como a de C,
separada por motivo.
```

**O que muda.**
- População: sai toda observação cuja janela ou rótulo exija trimestre
  censurado (limite grosseiro de cerca de 1.000, concentradas nas 54
  companhias de rótulo misto).
- Gates: linha G0.5 nova (uso = 0); G0.3 intacto; G1 estrutural recontado.
- Amostra: menor, montada sem rótulo, com a perda publicada antes de `y`, em
  observações e em companhias.
- Executor: estado ou filtro antes de `construir_amostra`; motivo próprio de
  descarte; verificação pela linhagem; contraprovas. O `diagnostico_g0_5`
  (GAT:310-342) passa a alimentar a população.
- Rascunho: §13 ganha "observação que use trimestre no estado
  `escala_heterogenea_nao_adjudicada`"; §14 (RASC:590) deixa de pedir "o G0.5
  com o limiar decidido".

**O que não se pode alegar.** Que os trimestres censurados estavam errados;
que a amostra restante está livre de erro de escala (erro consistente, sem
transição, não é coberto por gate nenhum, e somas através de transição sem
derivação só seriam alcançadas por E); que os resultados valem para companhias
com transição de escala não adjudicada; que G0.5 = 0 atesta a qualidade da
escala (atesta uso, não dado).

**Riscos e custo.** Custo: perda de observações e de companhias, concentrada;
companhia com padrão anual sai inteira. Risco de seleção: T1 e T2 são medidos
sem as janelas em torno de transições não adjudicadas. Risco de implementação:
censura errada vira perda silenciosa, o que o inventário e a verificação de uso
mitigam. Resíduos não cobertos: o descrito em E e o erro consistente.

**Natureza:** política/risco (regra de dado nova, que troca viés de
contaminação por viés de seleção). **Confiança:** média.

**Exposição.** À vista: 82/22.088 = 0,3712% (vigente), 56 (0,2535%, execução
3), 38 (0,172%, execução 2), 83 (16/09, antes de adjudicar) e as configurações
43/43, 8/39 e 5/5 (RASC:226-227, 248-257, 427, 434-436), além da taxa-base
(RASC:384-396) e das contagens estruturais de rótulos de escala (MED). Sei que
0,3712% passaria sob A e reprovaria sob D. C não tem limiar, então nenhum
número foi escolhido com esse valor à vista, e C não reprova G0 por esses
trimestres. O limite de perda usa 82, contagem estrutural permitida (LB:93-95).
Nenhum número de desfecho participou.

**O que mudaria a escolha.**
- As perdas reais de C e de E, se o responsável quiser vê-las antes de decidir.
  São contagens estruturais (O1.2), medíveis com `calcular_rotulo=False`.
  Perda adicional de E compatível com os mínimos do T1 favorece E (resposta
  acima). Perda que ameace os mínimos já sob C indicaria que o painel não
  sustenta a medição sem adjudicar o FCO, o que é argumento para D
  (bloquear), não para A (tolerar).
- Rota de prova do FCO que adjudique a maior parte dessas derivações: a
  censura encolhe sozinha, sem mudar a regra.
- Preferência do responsável por não mudar a população. Nesse caso, A, com
  três frases acrescentadas ao texto do rascunho: "(i) a tolerância é contada
  em trimestres, mas cada trimestre entra em até oito janelas e quatro
  rótulos, e a fração de observações expostas pode ser da ordem de dez vezes a
  de trimestres; (ii) contaminação sem relação com o rótulo tende a atenuar T1
  e T2, isto é, a favorecer a aprovação; (iii) erro de escala consistente, sem
  transição, não é coberto por gate nenhum."

---

## 4. §6.1 — Grade de D

**Pergunta.** Que datas D geram observações (companhia, D)? (RASC:278-290;
CONF17:210-212.)

**Opções.**
- **A** (rascunho, proposta; RASC:287-288): manter e congelar a grade do
  código, que são as datas de disponibilidade das linhas de FCO trimestral
  válidas.
- **B** (rascunho, alternativa; RASC:289-290): D = toda recepção do cadastro
  da companhia.
- **C** (**nova**, considerada e não proposta): grade de calendário, com datas
  fixas iguais para todas as companhias.
- **D** (**nova**, considerada e não proposta nesta rodada): A com
  deduplicação — uma observação por (companhia, q1), a de maior D. **É a
  alternativa do revisor**, apresentada abaixo com os argumentos dele.

**Proposta: A.**

Texto pronto, que substitui RASC:278-290 (o trecho entre colchetes só vale se
a proposta C do §5.5 for aprovada):

```markdown
### 6.1 Grade de D (decidido em [data] pelo responsável)

Para cada companhia, D percorre as **datas distintas** de `disponivel_em`
(§2.2; P1 e P4) das suas linhas de FCO trimestral utilizáveis — estado
`valido`[ e fora do estado `escala_heterogenea_nao_adjudicada` do §5.5] —,
inclusive derivadas e postergadas pela publicação da prova de escala. Uma
observação por (companhia, D). Na entrada do auditor, `dt_receb` é essa
`disponivel_em`.

Não geram D, por construção: a recepção de versão cujo número não está em
mãos (a v1 de documento com mais de uma versão), a recepção que só traz ativo
e a de documento cujo FCO não é utilizável.

Duas observações da mesma companhia com o mesmo q1 têm o mesmo rótulo (§2.3)
e janelas diferentes; não se deduplica. O executor publica, sem rótulo, o
número de chaves (companhia, q1) com mais de uma observação e o número de
observações nessas chaves. Toda inferência agrupa por companhia.

O executor publica também o número de datas D por companhia e os descartes
por motivo; a contagem `fco_ttm_nao_positivo` continua omitida enquanto
vigorar o O1.
```

**Justificativa.**

Fatos:
1. A v1 não definiu a grade: "D = data de decisão. Só entra informação com
   dt_receb <= D" (V1:50). A grade veio da implementação: "Um par (companhia,
   D) por data de recepção" e "a grade de decisão é a chegada do formulário,
   não o fim do trimestre" (AUD:657, 664). D percorre as datas distintas das
   linhas de FCO da companhia (AUD:712-721), com uma observação por chave
   (R15:131).
2. No painel de pesquisa, a `dt_receb` entregue ao auditor é a
   `disponivel_em` da linha (GAT:212): recepção da versão máxima e, num
   derivado, a mais tardia entre os operandos (LC:121-124), postergada até a
   publicação da prova de escala (CRF:87-92). A conferência pediu que a
   política fosse registrada com seus efeitos de seleção (CONF17:210-212), e a
   descrição foi corrigida em 18/09 (CRF18:73).
3. 3.863 de 24.925 documentos têm mais de uma versão; o intervalo v1→vmax tem
   mediana de 7 dias, p90 de 260 e máximo de 2.093 (LB:127). O número em mãos
   é o da versão máxima, e usar a data da v1 seria vazamento (LC:191).
4. q1 é o primeiro trimestre que começa depois de D, até D + 3 meses; a janela
   são os oito trimestres mais recentes disponíveis, contíguos e encadeados
   (RASC:82, 294-295; AUD:729-773).
5. Cinco dos seis componentes de T1 e os três baselines ranqueadores são
   funções da janela de FCO (RASC:305-307; V1:162-169, 213-218).
6. Atraso de recepção: mediana de 44 dias no ITR e 83 na DFP; 41% dos
   documentos chegam depois de 45 dias (AG:587-589).
7. O rótulo usa a maior versão de cada trimestre, disponível ou não em D
   (RASC:122-125; AUD:706-711). Duas observações da mesma companhia com o mesmo
   q1 têm, portanto, os mesmos q1–q4 e o mesmo `Y`.

Julgamentos:
- Com D na chegada da informação de FCO de cada companhia, q1 costuma ser o
  segundo trimestre depois da âncora (fatos 4 e 6: D cerca de 44 dias depois do
  fim do trimestre). Passa a ser o terceiro quando D cai depois do início do
  segundo trimestre seguinte — por exemplo, DFP recebida ou reapresentada
  depois de 31/03 (PAR:65-66). O horizonte é, portanto, de dois ou três
  trimestres, não constante; ainda assim, uma grade de calendário (C) faria
  ele depender do atraso de cada companhia em todos os casos, e esse atraso pode
  estar ligado à situação dela.
- B acrescenta, para cada documento com mais de uma versão, uma D na recepção
  da v1, quando por construção o número recém-recebido não está em mãos (fato
  3). Seria uma observação com um conjunto de informação que nenhum analista
  teve. B também dá mais peso a quem republica mais, e republicar pode estar
  ligado à situação da companhia (hipótese plausível, não medida).
- A amostra as datas em que muda a informação que T1 e T2 examinam (fato 5).
- A é o comportamento já contratado e testado, com o menor risco para o
  executor.

**Divergência do revisor — deduplicação por (companhia, q1) (PAR:60-67).** O
revisor adota a mesma grade, mas manteria uma observação por (companhia, q1),
a de maior D. Argumentos:
1. **Agrupar por companhia corrige o erro-padrão, não o peso.** As
   quase-duplicatas pesam a mais nas estimativas pontuais: as taxas por faixa
   do T1 e a AUC agregada. A própria proposta reconhece esse risco (PAR:63).
2. **O argumento de horizonte homogêneo favorece a deduplicação.** Uma DFP
   recebida ou reapresentada depois de 31/03 e o ITR do 1T em maio geram o
   mesmo q1 (AUD:743-759); o primeiro tem horizonte de três trimestres depois
   da âncora e o segundo, de dois. Ficar com o maior D elimina justamente o
   caso irregular (PAR:64-67).

**Minha resposta, curta.** Os dois argumentos procedem, e o fato 7 os
reforça: as observações que a deduplicação removeria repetem o **mesmo** `Y`
com a janela mais antiga, então o peso extra é do mesmo evento. Corrigi acima
a minha frase de horizonte "quase constante". Mantenho A como proposta desta
rodada, por instrução do coordenador e porque a deduplicação é regra nova de
população cujo tamanho não foi medido. O texto de A passa a mandar publicar,
sem rótulo, quantas chaves (companhia, q1) têm mais de uma observação. q1
depende só de datas (AUD:743-759), então essa contagem é estrutural (O1.2).
Se o responsável quiser decidir antes de medir, a regra do revisor não usa
nada do desfecho: o maior D é a informação mais recente, sempre anterior a q1.
Eu não me oporia a ela. Texto pronto, se adotada, substituindo o terceiro
parágrafo do bloco de A:

```markdown
Entre observações da mesma companhia com o mesmo q1 — que têm o mesmo rótulo
(§2.3) —, fica só a de maior D. As removidas vão ao inventário de descartes
com motivo próprio (`q1_repetido_mantido_o_maior_D`), contadas sem rótulo.
```

**O que muda.**
- Código: nada; o texto fixa o que o código faz. A contagem de chaves
  (companhia, q1) repetidas é publicação nova, sem rótulo.
- População e amostra: nenhuma mudança em relação ao vigente, salvo o efeito
  do §5.5 se C for aprovada (e da deduplicação, se o responsável preferir a
  alternativa do revisor).
- Executor: publicar o número de D por companhia e as chaves (companhia, q1)
  repetidas.
- Rascunho: §13 ganha "observação com D fora da grade do §6.1".

**O que não se pode alegar.** Que D representa todos os momentos de decisão de
um analista; que as observações são independentes (há quase-duplicatas, com o
mesmo rótulo quando compartilham q1); que o horizonte é constante; que a grade
é exógena ao comportamento de arquivamento, já que segue as datas de cada
companhia.

**Riscos e custo.** Quase-duplicatas em datas de disponibilidade tardia, com
peso extra nas estimativas pontuais para companhias com muitas postergações.
Companhias sem oito trimestres válidos contíguos não geram observação, em
qualquer grade. Custo: nenhum além da publicação nova.

**Natureza:** técnica, com efeito de seleção declarado. **Confiança:** alta
quanto à preferência sobre B e C; média quanto a não deduplicar, diante do
fato 7. Os efeitos de seleção de qualquer grade não são mensuráveis sem o
desfecho.

**Exposição.** À vista: G1 estrutural (10.748/502 vigente; 10.750/503 na
execução 3), P2 (3.077 trimestres, 6.728 pares, 4.175 chaves; RASC:437-439), a
taxa-base e os ≈ 2.865 a 2.867 descartes por `FCO_TTM ≤ 0` (RASC:397-402),
contagem que o O1 proíbe e que o §11 declara. Nenhum desses números orientou a
escolha, que é estrutural. Não vi o número de chaves (companhia, q1)
repetidas.

**O que mudaria a escolha.** A contagem estrutural de chaves (companhia, q1)
repetidas, medida antes de congelar: se for relevante, argumento para a
deduplicação do revisor, decidida antes de medir. Ou decisão de tratar
atualização só de balanço como momento de decisão, se componentes de ativo
fossem centrais.

---

## 5. §8.1 — Suporte da AUC intra

**Pergunta.** Quantas companhias com os dois rótulos são necessárias para T2
ser decidido? (RASC:334-342; CONF17:216-219.)

**Opções.**
- **A** (rascunho, proposta; RASC:339-340): sem piso novo, publicando
  `companhias_com_os_dois_rotulos` e `companhias_na_amostra`.
- **B** (rascunho, alternativa; RASC:341-342): fixar um piso agora, antes de
  medir. **É a proposta, com o número 30.**
- **C** (**nova**, considerada e não proposta por padrão): piso mais zona
  cinzenta de T2 espelhando o T1. Se a lacuna for menor que 0,12 mas a
  frequência bootstrap (companhias reamostradas 2.000 vezes) de lacuna
  ≥ 0,12 passar de 10%, T2 é INDECIDÍVEL.

**Proposta: B, com piso de 30 companhias, e IC descritivo da lacuna.**

Texto pronto, que substitui RASC:334-342:

```markdown
### 8.1 Suporte da AUC intra (decidido em [data] pelo responsável)

T2 só é decidido se ao menos **30 companhias** da amostra de T2 (observações
com escore B1 definido, §6.2) tiverem os dois rótulos. Abaixo disso, T2
levanta `AmostraInsuficiente` e o veredito é **INDECIDÍVEL**, nunca aprovação
(AGENTS.md §4.4, regra 4). O número é o mínimo de companhias que a v1 já
fixava para T1 (v1 §6), reaplicado à unidade de que a AUC intra é média. É
política de suporte mínimo, **não** garantia de precisão: como cada AUC por
companhia está em [0, 1], o erro-padrão da média de k companhias pode chegar
a 0,5/√k, que é 0,091 com k = 30.

Publicam-se, ao lado da lacuna, `companhias_com_os_dois_rotulos`,
`companhias_na_amostra`, o número de observações nessas companhias e o IC 95%
percentil da lacuna por reamostragem de companhias (2.000). O IC é
**descritivo**: não entra na decisão de T2, que segue o limiar de 0,12.

Contraprovas do executor: 29 companhias com os dois rótulos → INDECIDÍVEL;
30 → T2 decidido pelo limiar; IC publicado sem alterar o veredito.
```

**Justificativa.**

Fatos:
1. Hoje uma companhia com os dois rótulos basta para T2 ser medido
   (RASC:336-337; AUD:1135-1147). Só com zero companhias o teste levanta
   `AmostraInsuficiente` (AUD:1143-1146), exceção que o auditor define como
   "nunca é aprovação" (AUD:94-100).
2. A AUC intra é a média simples das AUCs das companhias com os dois rótulos
   (RASC:331-332; AUD:1147).
3. Regra 4 do §4.4: amostra insuficiente levanta erro e nunca vira aprovação
   (AG:782-786). Regra 8: a companhia é a unidade, e trimestres do mesmo
   emissor não são réplicas (AG:802-805).
4. A v1 fixou, antes de medir, 500 observações e 30 companhias como mínimo de
   T1 (V1:174-177; RASC:307-309).
5. A conferência de 17/09 não impôs "novo piso arbitrário" (CONF17:218-219); o
   levantamento de 15/09 pedia só publicar a cobertura intra (LEV:222); DEC:58
   põe a escolha entre aceitar alcance restrito e exigir suficiência antes de
   medir. O revisor chegou ao mesmo piso e à mesma aritmética (PAR:69-74).

Julgamentos:
- Sem piso, T2 pode aprovar com uma única companhia, o que é aprovação sobre
  amostra insuficiente, contra o espírito da regra 4. A unidade efetiva da AUC
  intra é a companhia com os dois rótulos (fatos 2 e 3), então o análogo do
  mínimo de companhias do T1 é um mínimo dessas companhias.
- 30 é reuso de um número que a v1 congelou para a mesma função (mínimo de
  unidades independentes), não calibração. Aritmética sem suposição: cada AUC
  por companhia está em [0, 1], logo o desvio-padrão entre companhias é no
  máximo 0,5 e o erro-padrão da média é no máximo 0,5/√k. Isso dá 0,091 com
  k = 30 e 0,158 com k = 10; com k ≤ 17 o limite passa do próprio limiar de
  0,12. O piso afasta o caso degenerado; não dá precisão.
- O IC descritivo (sugestão opcional do revisor, PAR:74) torna visível a
  precisão sem mudar a regra de decisão, que o rascunho promete "idêntica à
  v1" (RASC:324). É o mesmo agrupamento por companhia que os baselines já usam
  (RASC:352).
- Uma regra de precisão (por exemplo, erro-padrão máximo) dependeria da
  dispersão das AUCs por companhia, que é função do desfecho, e não pode ser
  fixada às cegas. Um piso de contagem pode.
- C daria proteção de precisão decisiva. Não a proponho por padrão porque ela
  muda a regra de decisão de T2 além do suporte e importaria os 2.000/10% do
  T1 sem validação para outra estatística. Se o responsável quiser simetria com
  o T1, o texto é: "Se a lacuna for < 0,12, reamostram-se companhias 2.000
  vezes; se a frequência de lacuna ≥ 0,12 passar de 10%, T2 é INDECIDÍVEL."

**O que muda.**
- População: nenhuma.
- Teste: T2 pode sair INDECIDÍVEL por suporte; o IC é publicado, sem papel na
  decisão.
- Executor: `teste_t2` levanta `AmostraInsuficiente` abaixo de 30, com
  contraprovas de 29 e 30 companhias; o artefato publica as contagens e o IC.
- Rascunho: §13 ganha "T2 decidido com menos de 30 companhias com os dois
  rótulos" e "IC da lacuna usado na decisão de T2".
- Baselines: a AUC intra de B1 a B3 segue a regra de completude do §9, sem
  piso novo.

**O que não se pode alegar.** Que T2 com 30 ou mais companhias tem precisão
para decidir perto de 0,12; que um IC que cruza 0,12 muda o veredito; que a
discriminação intra-companhia vale para companhias com um só rótulo; que 30
tem validação estatística.

**Riscos e custo.** Se menos de 30 companhias tiverem os dois rótulos, T2 fica
INDECIDÍVEL e a rodada não chega a PRONTO PARA CHALLENGER. Risco de leitura:
um IC largo ao lado de um T2 aprovado pode ser lido como reprovação; o texto
diz que não é. Implementação pequena.

**Natureza:** política (suporte mínimo). **Confiança:** média. É alta quanto a
existir piso; o número é política.

**Exposição.** A taxa-base agregada, cerca de 5% (RASC:384-396), permite
prever que 30 companhias com os dois rótulos provavelmente existem. O número
não foi calibrado por essa expectativa: copia o mínimo da v1 (V1:174). Nenhuma
contagem de companhias com os dois rótulos foi feita, porque exigiria `y`.

**O que mudaria a escolha.** Preferência do responsável por outro mínimo, ou
pela opção C, desde que decidida antes de medir e nunca depois de ver a
contagem ou o IC.

---

## 6. §12-bis — Alcance da prova de escala

**Pergunta.** Uma prova de escala feita em conta de saldo (`1`, `2` ou
`1.01.01`) autoriza corrigir também o FCO do mesmo documento? (RASC:542-570;
ALC:200-213; AG:546-557.)

**Opções.**
- **A** (rascunho; RASC:554-561): prova de saldo corrige o documento inteiro,
  que é o que a v4 faz hoje.
- **B** (rascunho, proposta; RASC:562-570): correção que altera o FCO exige
  prova que alcance o FCO.
- **C** (**nova**, considerada e não proposta): A condicionada a que, no mesmo
  formulário, o saldo final de caixa da DFC (`6.05.02`) seja igual ao caixa
  do balanço (`1.01.01`) em bruto. Não proposta porque essa igualdade liga a
  linha de saldo da DFC à unidade do balanço, mas não chega à `6.01` sem o
  fechamento da DFC (ALC:284-290). Além disso, seria regra escrita sabendo que
  os dois candidatos da GEOM-1 a satisfazem (ALC:284-287).

**Proposta: B, estendida (novo) ao veredito que G0.5 conta como decidido.**

Texto pronto, que substitui RASC:542-570:

```markdown
### Alcance da prova de escala — opção B (decidido em [data] pelo responsável)

Correção que altera o FCO exige prova que alcance o FCO do mesmo documento:
conta `6.01`, consolidado, acumulado do período corrente com início e fim
identificados, sob as exigências da v4 (cabeçalho local com unidade e
perímetro, datas completas, correspondência da conta com a célula da data
corrente). O manifesto por documento só recebe documento com as contas `1` e
`6.01` provadas. **A conta `1` se prova pela sua própria célula** (Ativo
Total, consolidado, data corrente), sob as mesmas exigências; prova de `2` ou
de `1.01.01` não substitui a da `1`, e prova de saldo sozinha não entra no
manifesto.

**O mesmo critério vale para o que G0.5 conta como decidido:** para o FCO,
confirmação ou correção apoiada só em prova de saldo não torna o operando
adjudicado.

Correção só do ativo, sem prova do FCO, continua vedada enquanto o G0.3 ler
o veredito por documento e o manifesto não tiver esquema por conta (hoje o
consumidor recusa coluna por conta).

**Erro demonstrado conhecido, não corrigido.** O Ativo Total de `140867`
(companhia `021520`, 30/06/2024) tem `MIL` demonstrada diretamente, contra
`UNIDADE` declarada (alcance GEOM-1, 24/09). Pela regra acima ele não entra
no manifesto enquanto o FCO do mesmo documento não for provado. Fica
registrado aqui como erro demonstrado e pendente — de prova do FCO, ou de
G0.3 e manifesto por conta —, e o executor o lista no artefato de G0. Não é
tolerado por caber em limiar nenhum (§5.5 do rascunho).

Rotas para provar o FCO (anexo do grupo 192; identidade interna da DFC)
exigem contrato próprio e, se lerem o FCO para algo além de igualdade entre
duas fontes, decisão explícita sobre o O1. A premissa da opção A (a escala
verdadeira é uma só por formulário) só pode ser adotada depois de testada em
amostra pré-registrada, fora dos documentos de desenho da GEOM-1, no molde do
teste da premissa de herança (lote C, S5/E10).
```

**Justificativa.**

Fatos:
1. Na v4 só saldos `1`, `2` e `1.01.01` provam escala, e nenhum fluxo `6.x` é
   usado sem identificação do intervalo (RASC:524-530). A correção entra no
   manifesto por documento; o construtor aplica a escala do documento ao ativo
   e ao FCO; a impressão digital cobre `1` e `6.01` (RASC:544-547;
   ALC:203-206; LC:242-245).
2. A escala **declarada** é uma só por formulário por construção: o
   `CodigoEscalaMoeda` do formulário é a origem do rótulo do CSV (LB:128). Por
   isso "0 de 22.486 documentos misturam" escalas (LB:120; MED
   `fonte.documentos_com_mais_de_uma_escala` = 0) não testa se a escala
   **verdadeira** é uma só.
3. O projeto já recusou estender escala sem testar a premissa: "Herdar sem
   testar a premissa — premissa não testada vira fato por decreto" (LC:386). A
   herança dentro do trecho só vale depois do teste da premissa no estrato E10
   (LC:252-264).
4. O rótulo sai do FCO, por diferença de acumulados (AG:549-551;
   ALC:177-180).
5. Uma correção já introduziu erro de 1.000× com prova aparentemente válida
   (ESC-0101; CONF17:41-74).
6. Nos dois documentos da GEOM-1, o saldo final de caixa da DFC é igual ao
   caixa do balanço em bruto, e chegar à `6.01` exigiria o fechamento da DFC
   (ALC:284-290). O parecer do auditor de 24/09 registra que "uma prova do
   ativo não autoriza correção por documento que também altere FCO"
   (ALC:209-211).
7. Hoje, sob A, 140867 e 142900 se qualificariam depois de integrada a GEOM-1,
   e o G0.3 iria de 132 para 130, ainda reprovado (limite 112). Sob B, nenhum
   documento se qualifica, e fechar as quatro ligações daria o mesmo −2
   (RASC:554-565; ALC:193-198). As quatro ligações são Ativo e FCO de cada um
   dos dois documentos, provados cada um pela própria célula (ALC:9-14).
8. O G0.5 conta como decidido todo documento com veredito `confirmada`,
   `corrigida` ou `herdada` (GAT:288-299).
9. O Ativo Total de 140867 teve `MIL` demonstrada diretamente, apesar de
   `UNIDADE` declarada (ALC:9-11, 20-30). Corrigir só esse ativo move o salto
   de lugar e o G0.3 segue em 132 (ALC:181-184). O rascunho diz que "erro já
   demonstrado **não** é tolerado por caber no limiar — ele é corrigido"
   (RASC:238-239).
10. O consumidor do manifesto recusa `cd_conta`, `escopo` ou qualquer coluna
    nova (CPEND:47-49; PEND:15).

Julgamentos:
- A usa uma premissa não testada, a de que a escala verdadeira é uma só por
  formulário, para estender a prova à conta que define o rótulo. A premissa é
  plausível (demonstrações costumam usar um único nível de arredondamento),
  mas o projeto exige testar premissa do mesmo tipo antes de usá-la (fato 3).
- As consequências são assimétricas. Correção errada do FCO corrompe o rótulo
  e cinco dos seis componentes em silêncio. Correção que falta deixa G0
  reprovado, de modo visível. B erra do lado visível.
- A exigência de prova da própria célula da `1` segue o critério da GEOM-1 de
  demonstrar cada conta que o painel usa (RASC:548-550) e as quatro ligações do
  fato 7. Aceitar `1.01.01` pela `1` seria a mesma extensão entre contas que B
  recusa para o FCO. A `2` poderia provar a `1` quando as duas forem iguais em
  bruto no mesmo formulário, porque a identidade contábil as amarra; deixo isso
  ao contrato da rota de prova, em vez de decidir aqui.
- A extensão ao "decidido" de G0.5 é necessária por coerência. Sem ela, o
  G0.5 trataria como adjudicado o FCO de um documento só confirmado por saldo,
  e a premissa de A voltaria por outra porta (fato 8; AG:547-551). Por isso a
  frase sobre correção só do ativo passa a citar só o G0.3 e o esquema do
  manifesto (fato 10): o G0.5 desta proposta já lê o veredito pelo FCO.
- B deixa sem correção um erro demonstrado (fato 9), em tensão com RASC:238-239.
  A saída honesta é registrá-lo como erro conhecido e pendente, não
  silenciá-lo nem corrigi-lo pela metade. Isso não muda nenhum gate (fato 9).
- B não piora o estado atual: sob as duas opções, G0 segue reprovado (fato
  7).

**O que muda.**
- Hoje: nada nos dados, porque a v4 não tem correções (RASC:422-425). O
  artefato de G0 passa a listar o erro conhecido de 140867.
- Para o futuro: o validador do manifesto (produtor e consumidor) exige
  evidência localizada da `1` e da `6.01`, cada uma pela própria célula, em
  toda linha que altere o documento; o conjunto "decidido" do G0.5 passa a ser
  por FCO. Contraprovas: linha só com prova de saldo é recusada; linha com
  prova de `1.01.01` no lugar da `1` é recusada; operando confirmado só por
  saldo conta como não decidido no G0.5.
- População: nenhuma mudança agora.
- Rascunho: §13 ganha "correção de FCO sem prova que alcance o FCO".

**O que não se pode alegar.** Que o FCO dos documentos com prova de saldo está
errado (está indeterminado); que B melhora G0 (não melhora agora); que a
premissa de A é falsa; que o ativo de 140867 está correto no painel (não
está, e fica registrado).

**Riscos e custo.** Custo: G0 permanece reprovado até existir rota de prova do
FCO, com contrato próprio e talvez decisão sobre o O1 (§10, item 3); um erro
demonstrado fica sem correção até lá. Risco: se a premissa de A for
verdadeira, B atrasa o estudo sem ganho.

**Natureza:** técnica/risco. **Confiança:** alta.

**Exposição.** À vista: contagens estruturais (132, 112, −2) e os documentos
candidatos da GEOM-1, um deles documento de desenho da regra (RASC:558-559).
Nenhum número de desfecho. A escolha não depende de quais documentos se
qualificam: B não qualifica nenhum hoje e é proposta pelo argumento da
premissa.

**O que mudaria a escolha.** Um teste pré-registrado da premissa de A, fora
dos documentos de desenho da GEOM-1, em que documentos com prova de saldo e
prova de FCO independentes não mostrem nenhuma discordância, no molde do E10
(LC:252-264).

---

## 7. O1 — Exceção protetiva no verificador de não publicação

**Pergunta.** Aprovar, como adendo datado ao O1 (LB:85-100), a exceção que
permite ao verificador de não publicação obter módulo, piso e teto das formas
do FCO já lidas para igualdade autorizada? (DEC:15-37; CPEND:73-86.)

**Opções.**
- **A** (DEC, recomendação; DEC:25-31): aprovar o texto proposto.
- **B** (DEC, caminho se recusada; DEC:39-42): separar os valores de FCO no
  verificador, conservar só as magnitudes exatas e documentar e testar a
  redução de cobertura.
- **C** (**nova**, proposta): aprovar com emendas. As emendas limitam o escopo
  às formas enumeradas do documento em exame, encerram a execução na primeira
  recusa, datam a não retroatividade e mandam declarar as exposições no §11 do
  v2.

**Proposta: C.**

Texto pronto do adendo (novo documento datado, vinculado ao O1 de LB:85-100):

```markdown
## Adendo ao O1 — exceção protetiva (aprovado em [data] pelo responsável)

Vale enquanto vigorar o O1, até o congelamento do pré-registro v2.

1. **Onde.** Só na verificação que decide se uma saída pode ser gravada ou
   publicada (hoje, `_magnitudes_protegidas` e `verificar_sem_valores`, em
   `scripts/conferir_alcance_geom1_rank03b.py`).
2. **Sobre quais valores.** Só valores de FCO do próprio documento em exame,
   já lidos em memória para a igualdade autorizada pelo contrato da execução,
   e só nas formas que esse contrato enumera para a busca — hoje o acumulado
   consolidado corrente, **o comparativo do exercício anterior**, o individual
   corrente, ×1.000 e ÷1.000 (`alvos_fco`). Forma nova exige contrato.
3. **Quais operações.** Módulo; piso e teto do módulo, quando não inteiro.
   Nenhuma outra: nem soma, diferença, sinal, arredondamento a outra casa ou
   agregação entre valores ou períodos.
4. **Destino.** Os resultados ficam locais à verificação: não são gravados,
   registrados, retornados, publicados, passados a outra função, nem usados
   como evidência de escala, em busca de correspondência, em seleção de
   documento, em agregação ou em modelo. O único efeito possível é recusar a
   gravação, com mensagem sem dígitos.
5. **Sem uso como oráculo.** A verificação só examina saídas produzidas pela
   execução autorizada; é proibido submeter a ela números ou textos
   construídos para sondar valores. **A primeira recusa encerra a execução,
   sem gravar saída. Nova execução sobre os mesmos documentos exige registro
   do incidente e contrato novo**, que diga o que muda na saída e por quê.
6. **O que não autoriza.** Busca de FCO arredondado; publicação de
   divisibilidade; adjudicação de escala pelo FCO; soma de FCO em janela, TTM
   ou rótulo; métrica de modelo; reuso, sobre o FCO, da função de ativo
   arredondado.
7. **Retroatividade.** Não reclassifica as execuções que já fizeram essas
   operações em memória: o truncamento do módulo (piso) das formas do FCO na
   revisão de 24/09 e na reconferência de 25/09, e o piso e o teto na correção
   RAG de 25/09 e nos adendos 2 e 3 de 26/09. Ficam como histórico, como diz o
   contrato de pendências de 26/09 (P4).
8. **Vínculo e contraprovas.** O adendo é fixado por hash nas duas entradas da
   busca e conferido antes de ler pacotes. Contraprovas: saída que contenha
   piso ou teto de uma forma do FCO, inclusive do comparativo, é recusada;
   nenhum retorno, atributo, exceção ou log da verificação contém dígitos de
   valor protegido; depois de uma recusa, nada é gravado e a mesma execução não
   prossegue; adendo com hash diferente derruba a execução antes de ler pacote.
9. **Declaração no §11 do v2.** Antes de qualquer congelamento, o §11 do
   rascunho v2 passa a declarar, com datas: as leituras de FCO em memória para
   igualdade PDF × XML de 24 a 26/09 (alcance e revisão GEOM-1, correção RAG e
   adendos 2 e 3) e as operações de piso e teto da cláusula 7.
```

**Justificativa.**

Fatos:
1. O O1 existe para cegar ao desfecho. Proíbe calcular sobre dado real `Y`,
   `S1`, `S2`, taxa do evento, soma ou sinal de FCO em janela futura, TTM
   agregado, T1, T2, AUC, baseline ou estatística condicional ao rótulo
   (LB:90-92). FCO individual só é lido para testar igualdade entre duas fontes
   e "não é impresso, agregado nem publicado" (LB:96-98).
2. O verificador recusa a saída se qualquer leitura de número publicado for
   igual ao módulo de um valor comparado ≥ 1.000, ou ao piso ou teto dele
   quando não inteiro (VER:560-572, 588-625; CRAG:129-135). As formas do FCO
   comparadas são cinco, todas do mesmo documento: acumulado consolidado
   corrente, **comparativo do exercício anterior** (VER:670), individual,
   ×1.000 e ÷1.000 (VER:668-673). A busca e a reconferência passam todas elas à
   autoverificação (VER:816, 863-864, 912, 949).
3. Notas em milhares imprimem inteiros arredondados (CRAG:162-165). É nessa
   forma que um FCO apareceria num trecho publicado das notas. A forma ÷1.000
   raramente é inteira, e só piso e teto a protegem.
4. A máscara lexical, que não publica trecho de linha com vocabulário de caixa
   ou fluxo, "reduz o canal, não o fecha" (ALC:302-306). A máscara já falhou
   em sintético mais de uma vez (ALC:251-264).
5. Operações já feitas em memória sobre as formas do FCO:
   - **24/09 e 25/09, piso por truncamento.** O verificador da revisão de 24/09
     calculava `int(abs(v))` de cada valor comparado, inclusive das formas do
     FCO (REV24:123-124, 132-137, 284-285). O da reconferência de 25/09 fazia o
     mesmo (REC25:136-137, 147-152, 343-344). É o "piso já era barrado antes"
     de CRAG:135.
   - **25/09 e 26/09, piso e teto.** A correção RAG de 25/09 os calculou (RAG:83,
     229, 261; ARAG:134-143), e as execuções no dado real dos adendos 2 e 3, em
     26/09, também (RAG:333, 401; VER:816, 863-864).

   O contrato de 26/09 lê o O1.3 estritamente (sem autorização explícita),
   manda preservar o detector sem executá-lo sobre FCO real até a decisão e
   mantém as execuções passadas como histórico (CPEND:75-86; PEND:17).
6. Leituras de FCO por igualdade de 24 a 26/09: o contrato de alcance autorizou
   ler o FCO em memória para igualdade PDF × XML (CALC:16-18); a revisão o
   comparou só em memória (ALC:235-237); a correção RAG e os adendos repetiram
   a busca (RAG:83, 229, 333, 401). O §11 atual do rascunho não declara nenhuma
   dessas leituras nem as operações do fato 5 (RASC:375-504).
7. Na saída atual, nada é gravado antes das recusas, e vazamento no resultado
   não deixa arquivo (ARAG:124-126).
8. Se recusada, a alternativa é separar os valores de FCO, conservar só as
   magnitudes exatas e documentar a redução de cobertura (DEC:39-42;
   ARAG:141-143).

Julgamentos:
- As operações são cegas ao sinal (módulo), de um só documento, sem agregação
  e sem janela futura. O comparativo é do exercício anterior, passado em
  relação ao documento. Não produzem informação sobre `Y`, que depende do
  sinal de somas de semestres futuros. O único canal de saída é a recusa, que
  diz no máximo que algum número publicado coincidiu com alguma magnitude
  protegida, sem dizer qual, sem sinal e sem valor.
- A recusa só vira oráculo se a execução puder ser refeita com a saída
  alterada; a cláusula 5 fecha isso ao encerrar a execução e exigir registro e
  contrato novo (ressalva do revisor, PAR:89).
- Recusar a exceção enfraquece a garantia de não publicação do próprio O1.3
  exatamente na forma mais provável de vazamento (fato 3), para evitar
  operações que não expõem nada. Aprovar serve ao propósito do O1 melhor do que
  recusar.
- A retroatividade precisa de datas completas (fato 5). O revisor datou em
  25–26/09 (PAR:91); o código preservado mostra que o piso por truncamento já
  existia na revisão de 24/09. A cláusula 7 usa as datas do código.
- A declaração no §11 (cláusula 9) segue a disciplina do próprio rascunho,
  cujo §11 existe para declarar o que já foi visto antes de decidir
  (RASC:377-381).

**O que muda.**
- Código do verificador: nenhuma mudança de lógica (PEND:17). A cláusula 5
  exige conferir que a execução termina na primeira recusa (fato 7 indica que
  o código atual não grava nada antes das recusas; a contraprova fixa isso).
- Executor da busca: vínculo por hash do adendo nas duas entradas e
  contraprovas (DEC:33-37).
- Rascunho: o §11 ganha a declaração da cláusula 9.
- Se recusada (opção B): mudança de código para separar as formas do FCO, com
  redução de cobertura documentada.

**O que não se pode alegar.** Que a exceção autoriza busca de FCO arredondado
(DEC:44-48; CPEND:82-86), adjudicação de escala pelo FCO ou cálculo de rótulo;
que o estudo é inteiramente cego (o §11 declara exposições); que as execuções
de 24 a 26/09 foram autorizadas retroativamente.

**Riscos e custo.** O uso como oráculo fica fechado pela cláusula 5, por regra
e por contraprova. A ampliação de escopo fica fechada pelas cláusulas 2 e 6. O
resíduo é a recusa, que revela no máximo um bit e encerra a execução. Custo: o
adendo, as contraprovas e a declaração no §11.

**Natureza:** política (autorização de exceção a regra de cegueira).
**Confiança:** alta.

**Exposição.** Nenhum número envolvido; nenhum valor de FCO visto.

**O que mudaria a escolha.** Um desenho com proteção equivalente sem
transformar o FCO, por exemplo não publicar dígito nenhum de trecho das notas,
só página, linha e coluna. Ou evidência de que recusas poderiam carregar
informação sobre sinal ou janela futura.

---

## 8. Interações entre os itens

1. **O §12-bis define o "decidido" do §5.5.** Com B, só prova que alcance o
   FCO torna um operando adjudicado para o G0.5. Com A, prova de saldo
   bastaria, e o G0.5 trataria como adjudicado o FCO que ninguém provou
   (AG:547-551; ALC:187-190; GAT:288-299). Escolher A no §12-bis enfraquece
   qualquer opção do §5.5.
2. **§5.5 (C) e §6.1.** Trimestre censurado não gera D e quebra a janela; o
   texto do §6.1 já prevê isso entre colchetes. Se o responsável escolher A no
   §5.5, o trecho entre colchetes sai do §6.1.
3. **Por que o §5.1 atravessa e o §5.5 não.** A derivação entre métodos é
   permitida porque o total é invariante por norma, nenhum defeito foi
   demonstrado e a v1 nunca a contou no G0.1. A derivação entre escalas não
   adjudicadas é censurada porque o defeito é demonstrado e produz erro de
   1.000× e troca de sinal. Um trimestre que seja as duas coisas cai no §5.5.
4. **§3.2 vem antes de tudo.** A exclusão muda o universo antes de qualquer
   gate; todos os números do §11.3 passam a históricos e precisam ser medidos
   de novo, com o efeito da exclusão no G0.3 publicado.
5. **§8.1 vem depois das perdas.** §3.2 e §5.5 (e a deduplicação do §6.1, se
   adotada) reduzem observações e companhias. Se sobrarem menos de 30 com os
   dois rótulos, T2 é INDECIDÍVEL, e isso nunca é motivo para rever §3.2, §5.5
   ou §6.1 depois de visto.
6. **O1 e §12-bis.** B exige prova que alcance o FCO. As rotas nomeadas (anexo
   do grupo 192; identidade interna da DFC) pedem contrato próprio e, se lerem
   o FCO para algo além de igualdade, decisão sobre o O1. A exceção protetiva
   não as autoriza (DEC:44-48; CPEND:82-86). Há uma ambiguidade a resolver
   nesse contrato (§10, item 3).
7. **G0 continua reprovado.** Nenhuma decisão faz o G0.3 passar por construção
   (o efeito do §3.2 será medido e publicado). Com B, nenhuma correção é
   possível até existir rota de prova do FCO (DEC:106-113; RASC:566-570).
8. **Ordem sugerida de decisão:** §12-bis → §5.5 → §5.1 → §3.2 → §6.1 → §8.1.
   O O1 é independente do rascunho, mas condiciona a execução das rotas de
   prova.
9. **Aprovar as decisões não é congelar o v2.** Os pins do rascunho — digest
   `6ca635a9…`, manifesto `13520e61…` (RASC:158-161) — descrevem um painel com
   G0 sabidamente reprovado (132 saltos, limite 112; RASC:425; ALC:193-194).
   Congelar com eles consumiria o v2 com o veredito já conhecido, como a
   rodada de 11/09 consumiu a v1 (RASC:9-10). O congelamento deve esperar,
   além do executor testado e da conferência independente (DEC:99-104), a
   **resolução estrutural do G0** — correções de escala com prova que alcance
   as contas usadas, num painel novo com pins novos, e G0 medido sem rótulo.
   **O O1 continua vigente até lá**, e com ele a exceção do §7.

---

## 9. Tabela-resumo

| Item | Proposta | Relação com rascunho, DEC e revisor | Muda a população? | Natureza | Confiança |
|---|---|---|---|---|---|
| §3.2 | Excluir `ll3_13_%`; publicar o efeito no G0.3 | Igual à proposta do rascunho; revisor concorda | Sim (−3 companhias) | Técnica | Alta |
| §5.1 | Unicidade; derivação entre métodos permitida, contada e sujeita a F1–F6 e G0.5 | Igual, com condições; revisor concorda | Não | Técnica | Alta |
| §5.5 | Censura dos trimestres heterogêneos não adjudicados (C); G0.5 = uso zero; perda em observações e companhias | **Diverge** do rascunho; **revisor propõe C+E** | Sim (perda inventariada) | Política/risco | Média |
| §6.1 | Manter a grade por disponibilidade do FCO utilizável, sem deduplicar; publicar chaves (companhia, q1) repetidas | Igual ao rascunho; **revisor propõe deduplicar por (companhia, q1)** | Não | Técnica, com seleção | Alta sobre B e C; média sobre não deduplicar |
| §8.1 | Piso de 30 companhias com os dois rótulos; abaixo, INDECIDÍVEL; IC descritivo | **Diverge** da proposta do rascunho (é a alternativa dele, com número); revisor concorda | Não | Política | Média |
| §12-bis | Opção B, estendida ao "decidido" do G0.5; `1` pela própria célula; erro de 140867 registrado | Igual, com extensões; revisor concorda | Não, por ora | Técnica/risco | Alta |
| O1 | Aprovar a exceção com nove cláusulas | Igual à recomendação de DEC, com emendas; revisor concorda | Não | Política | Alta |

**Pontos do rascunho a atualizar junto, se as propostas forem aprovadas:**
lista de pontos pendentes (RASC:15-20); linha G0.1 da tabela do §5
(RASC:185); linha G0.5 nova na mesma tabela (se C); §11, com a declaração da
cláusula 9 do §7; §13 (RASC:572-580), com as condições novas indicadas nos
itens 2, 3, 4, 5 e 6; §14, "Ainda não cumpridos" (RASC:590). Título, nome do
arquivo e SHA-256 só mudam no congelamento (RASC:5-7), que deve esperar o
executor testado, a conferência independente (DEC:99-104) e a resolução
estrutural do G0 (§8, item 9).

---

## 10. Limitações e contradições encontradas nas fontes

1. **O CPC 03 não está no repositório, e não há rede.** Os itens 18–20A são
   citados pela conferência de 17/09 (CONF17:284-290, com link para a CVM) e
   pelo lote C (LC:59-60). Não os conferi. A invariância do total operacional
   entre métodos é conhecimento normativo geral (IAS 7), não verificado aqui, e
   o critério de refutação de LCR:258 nunca foi testado.
2. **`becos_sem_saida.md` está desatualizado.** BECOS:96 ainda registra "G0 e
   G1 aprovam (47 saltos, 0,2092%)" como estado de 16/09, sem a reprovação
   vigente de 18/09 (RASC:422-426; MEM:466-481).
3. **O1 × identidade da DFC.** O O1 permite contar "identidades contábeis"
   (LB:93-95), e o construtor do painel de pesquisa calcula o fechamento da DFC
   somando a `6.01` às demais contas, com saída em contagem
   (PPR:497-516; MED `fonte.identidades_contabeis`). Já o relatório de alcance
   e o MEMORY dizem que o fechamento da DFC "soma o FCO e o O1 hoje proíbe"
   (ALC:288-290; MEM:408-410). A leitura do revisor é que o O1.2 permite
   identidade com saída booleana (PAR:83). A distinção plausível, entre contar
   se a identidade fecha e usar o fechamento como prova de escala, não está
   escrita em lugar nenhum. Pesa sobre a rota de prova do FCO da opção B do
   §12-bis, e o contrato dessa rota deve resolvê-la, com teste pré-registrado
   fora dos documentos de desenho da GEOM-1.
4. **Piso e teto sob o O1.** O adendo RAG de 25/09 diz que o uso protetivo
   "segue o O1 como ele vem sendo aplicado desde o R3" (ARAG:140-143). O
   contrato de 26/09 diz que o O1.3 não o autoriza explicitamente
   (CPEND:75-81). Segui a leitura mais estrita e mais recente, que é a de DEC.
   O piso por truncamento já existia no código de 24/09 (REV24:123-124), o que
   a v1 desta proposta não registrava.
5. **Letra da v1 × paráfrase do rascunho no G0.1.** V1:130 ("usa … para o
   mesmo (companhia, trimestre)") × RASC:185 e 195 ("sem soma"). O G0.1 que a
   v1 executou (AUD:407-415) resolve a questão a favor da unicidade. A v1
   desta proposta afirmava, sem fonte, que o trimestre derivado entre métodos
   não existia no painel da v1; o código mostra que o 4T podia ser derivado
   entre métodos (SRC:1486, 1500-1504). Corrigido no item 2 (E1).
6. **83 × 82.** O rascunho diz que em 16/09, antes da adjudicação, 83
   trimestres combinavam escalas declaradas diferentes (RASC:226-227); o
   relatório do lote C e a versão vigente dão 82 (LCR:232; RASC:427). A
   diferença não é explicada nos documentos lidos e não afeta nenhuma
   proposta.
7. **Descrição da grade no auditor.** AUD:657 diz "D = `dt_receb`"; no caminho
   do painel de pesquisa, `dt_receb` recebe `disponivel_em` (GAT:212). O
   comportamento é coerente com o §6.1, e a descrição do produtor de G1 foi
   corrigida em 18/09 (CRF18:73), mas o docstring do auditor não.
8. **Terceira companhia `ll3_13`.** Não é identificada nos documentos lidos
   além de "seguros" (LC:26-30).
9. **Origem desta versão.** O scratchpad da primeira rodada foi apagado; esta
   versão parte da cópia `proposta_v1_revisada.md`, cujo SHA-256
   (`5c0e72b9…31e0`) confere com o que o revisor examinou (PAR:15).

---

## 11. O que esta proposta não faz

- Não altera o rascunho, nenhum arquivo do repositório nem o estado do git.
  Este é o único arquivo escrito nesta rodada.
- Não decide, não aprova e não congela. Não autoriza executor, medição ou
  treino.
- Não mede nada: nem rótulo, taxa, T1, T2, AUC ou baseline, nem contagem
  estrutural. Os limites de ordem de grandeza dos itens 3 e 5 são aritmética
  sobre números já publicados; as contagens estruturais sugeridas (perdas de C
  e E, chaves (companhia, q1) repetidas, efeito do §3.2 no G0.3) ficam para o
  executor ou o responsável.
- Não abriu painel DuckDB, pacote RAD, PDF nem `corpus/holdout_2T2026`; não
  leu valor de FCO; não usou rede nem API.
- Não resolve a reprovação de G0 (132 saltos) e não propõe mudar nenhum
  limiar congelado pela v1.
- Não autoriza busca de FCO arredondado, rota de prova do FCO, correção por
  conta ou herança S5.
- Não resolve a ambiguidade O1 × identidade da DFC (§10, item 3).
- Não substitui a conferência independente que o rascunho e DEC exigem antes
  de congelar (DEC:99-104).
- Não verifica o texto do CPC 03.

---

## Registro da revisão

Parecer examinado: PAR (fase 2 do revisor, veredito **APTA COM RESSALVAS**),
sobre a v1 desta proposta (SHA-256 `5c0e72b9…31e0`). As sete escolhas não
mudaram.

### Erros de fato

| Item | Tratamento | O que mudou |
|---|---|---|
| **E1 — §5.1** | **Incorporado** | Retirada a frase, sem fonte, de que o trimestre derivado entre métodos "não existia no painel para o qual a frase foi escrita" (texto pronto e julgamento). No lugar: o G0.1 que a v1 executou contava só pares com mais de um demonstrativo (AUD:407-415), e por isso a unicidade é a leitura que a v1 aplicou. O fato 3 agora distingue a derivação do 2T/3T, que particiona por demonstrativo (SRC:1342-1346), da do 4T, que junta anual e nove meses sem demonstrativo e grava o do anual (SRC:1322-1325, 1486, 1500-1504); um 4T entre métodos era possível no painel da v1. Novo fato 7 e §10, item 5. |
| **E2 — §5.5** | **Incorporado** | O texto pronto dizia que os casos não alcançados "continuam cobertos só pelo G0.3, no ativo". Agora diz que o G0.3 só os vê quando há transição detectável no ativo, e que erro de escala consistente, sem transição, não é coberto por gate nenhum, afetando só os três componentes de nível. Coerente com o "O que não se pode alegar", que também foi reescrito. Novos fatos 5 e 6 (54 companhias mistas, 71 de 189 trechos de um documento; 17 companhias só `UNIDADE`, 400 documentos; MED `rotulos_de_escala`). |

### Ressalvas

| Ressalva | Tratamento | Motivo e onde |
|---|---|---|
| §3.2 / §0.4: "nenhuma das sete decisões altera G0.3" → "nenhuma faz o G0.3 passar" | **Incorporada com ajuste** | A frase antiga era falsa e saiu. Não escrevi que o §3.2 "não faz o G0.3 passar" porque o número de saltos das três companhias não foi medido. No lugar: nenhuma decisão foi escolhida pelo efeito no G0.3, seis não o tocam, e o efeito da do §3.2 será medido e publicado (§0.4; §8, item 7). |
| §3.2: publicar quantos dos 132 saltos saem com as três companhias | **Incorporada** | Texto pronto do §3.2 manda publicar saltos e linhas de ativo das excluídas (regra 9). |
| §5.1: "o critério de refutação nunca foi cumprido" é ausência de teste | **Incorporada** | Fato 6 reescrito: nunca testado e, sem documento com os dois métodos, não testável dentro do mesmo documento; ausência de teste, não evidência. Também em "O que não se pode alegar" e no §10, item 1. |
| §5.5: publicar a fração de companhias do universo perdida | **Incorporada** | Texto pronto manda publicar companhias que perdem ao menos uma observação e companhias que saem inteiras, com fração sobre as companhias da amostra antes da censura. |
| §8.1 (opcional): IC da lacuna por reamostragem de companhias, sem papel decisivo | **Incorporada** | Texto pronto publica o IC 95% percentil (2.000 reamostragens por companhia), descritivo, com contraprova de que não altera o veredito. |
| §12-bis (a): dizer o que prova a conta `1` | **Incorporada** | A `1` se prova pela própria célula; `2` e `1.01.01` não a substituem. A prova da `1` pela `2` com igualdade em bruto fica para o contrato da rota de prova, não decidida aqui. |
| §12-bis (b): frase "G0.3 e G0.5 lerem o veredito por documento" | **Incorporada** | Passa a citar só o G0.3 e o esquema do manifesto (CPEND:47-49), já que o G0.5 desta proposta lê o veredito pelo FCO. |
| §12-bis (c): registrar o ativo de 140867 como erro demonstrado conhecido | **Incorporada** | Parágrafo próprio no texto pronto (erro conhecido, pendente de prova do FCO ou de G0.3 e manifesto por conta, listado no artefato de G0); fato 9. |
| §12-bis (d): status da rota por identidade da DFC sob o O1 | **Incorporada como informação** | §10, item 3 registra que o construtor já soma a `6.01` no fechamento da DFC (PPR:497-516) e a leitura do revisor, sem decidir: fica para o contrato da rota. |
| O1 (a): depois de uma recusa, a execução termina; nova execução exige registro do incidente e contrato novo | **Incorporada** | Cláusula 5 e contraprova na cláusula 8. |
| O1 (b): incluir o comparativo nas formas enumeradas | **Incorporada** | Cláusula 2 enumera as cinco formas, inclusive o comparativo (VER:670). |
| O1 (c): datar a retroatividade em 25–26/09 | **Incorporada com correção** | O código preservado mostra piso por truncamento já em 24/09 e 25/09 (REV24:123-124; REC25:136-137). A cláusula 7 data: piso desde 24/09; piso e teto em 25 e 26/09. |
| O1 (d): declarar no §11 do v2 as leituras de FCO por igualdade de 24 a 26/09 e o piso/teto em memória | **Incorporada** | Cláusula 9 do adendo; fato 6 do §7; lista de pontos a atualizar (§9). |
| Transversal: condicionar o congelamento à resolução estrutural do G0, com o O1 vigente até lá | **Incorporada** | §0.4, §8 item 9 e §9. |

### Divergências (mantidas, com a alternativa do revisor)

| Item | Minha escolha | Alternativa do revisor | Onde |
|---|---|---|---|
| §5.5 | C | C+E (censurar também somas entre documentos de escalas diferentes sem derivação) | §3: argumentos do revisor e resposta. Retirei o meu argumento de "sobreposição com o G0.3" (procede a crítica); mantenho C por perda não medida e por E redefinir a população de G5.1; recomendo medir as duas perdas e, se a de E for compatível com os mínimos do T1, preferir E. Texto pronto de E incluído. |
| §6.1 | A, sem deduplicação | Deduplicar por (companhia, q1), ficando com o maior D | §4: argumentos do revisor e resposta. Acrescentei o fato de que observações com o mesmo q1 têm o mesmo `Y` (RASC:122-125; AUD:706-711), que reforça a alternativa, e corrigi a minha frase de horizonte "quase constante". Mantenho A nesta rodada por instrução e porque a regra não foi medida; o texto de A manda publicar as chaves repetidas. Texto pronto da deduplicação incluído. Confiança em não deduplicar rebaixada para média. |
