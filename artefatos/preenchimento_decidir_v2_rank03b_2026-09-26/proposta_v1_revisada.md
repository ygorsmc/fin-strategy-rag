# Proposta de preenchimento — decisões pendentes do v2 (Rank 3-B)

**Data:** 2026-09-26

> **PROPOSTA de agente; não é decisão nem aprovação do responsável; o rascunho não foi alterado.**

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
| MED | `artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json` (por chave) |

### 0.3 O que li e o que vi — exposição deste agente

- Li o rascunho inteiro, com o §11 antes de decidir. Números de desfecho que
  ele expõe e que, portanto, vi: taxa do evento no painel compartilhado
  **0,0526 → 0,0530**, "3" observações com `y` diferente e "−5" em FCO TTM não
  positivo (RASC:384-391); **≈ 2.865 a 2.867** descartes por `FCO_TTM ≤ 0` no
  painel de pesquisa (RASC:397-402). MEM:1149-1151 repete a taxa. Não abri o
  relatório de 15/09 que a publicou.
- Números estruturais vistos: os do §11.3 (RASC:416-457) e, em MED, só as
  chaves e os campos de plano de contas, seguradoras, troca de método,
  identidades contábeis, N2 e perfil de escala. Nenhum valor de FCO.
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
- Fato: nenhuma das sete decisões altera G0.3. G0 continua reprovado em
  qualquer combinação delas (DEC:106-113).

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

Julgamentos:
- Seguradora aplica reservas técnicas em ativos financeiros e costuma
  classificar parte desse giro nas atividades operacionais. "Consumo
  operacional de caixa" de seguradora é outro objeto econômico. A exclusão
  alinha a operacionalização ao estimando que a v1 já declarou; não cria
  estimando novo.
- A opção B só teria mérito se houvesse razão para estudar seguradoras junto
  com não financeiras, e nenhum documento a apresenta. O custo de A é pequeno
  (3 de 700, cerca de 0,43%) e é pago antes de medir.

**O que muda.**
- População: de 700 para 697 companhias no universo, antes dos demais filtros.
- Gates: os números do §11.3 foram medidos com as três e passam a históricos;
  G0 e G1 precisam ser medidos de novo no universo decidido.
- Amostra: saem as observações das três.
- Executor: filtro de universo, com contraprova (companhia sintética
  `ll3_13` excluída; `ll3_11` mantida).
- O painel não muda.

**O que não se pode alegar.** Que a população é estritamente não financeira;
que todas as seguradoras ou entidades financeiras foram excluídas (o critério
só alcança `ll3_09`, `ll3_13` e `is_banco`); qualquer afirmação setorial, já
que não há controle setorial (V1:113-116; RASC:133-134); que seguradoras se
comportam de outro modo quanto ao alvo, porque nada foi medido.

**Riscos e custo.** Custo: 3 companhias. Risco: se alguma das três não for
seguradora, a perda é conservadora. A atividade da terceira companhia não é
identificada nos documentos lidos além de "seguros" (LC:26-30).

**Natureza:** técnica (operacionalização da população já declarada), com
efeito de população. **Confiança:** alta.

**Exposição.** À vista: contagens estruturais (3 companhias, 24 linhas) e a
taxa-base agregada do painel compartilhado, que não separa planos
(RASC:150-152, 384-396). Nenhuma contagem de evento por companhia ou por plano
foi vista. A escolha decorre do universo declarado na v1 e seria a mesma para
qualquer taxa-base.

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
mesma linha falam de soma.

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
limiar da mesma linha tratam de soma, e o trimestre derivado entre métodos não
existia no painel para o qual a frase foi escrita.
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
   LB:121). Parear acumulados por demonstrativo "fabrica 'sem antecedente'"
   nelas (LC:188). Na simulação da derivação do painel compartilhado, 61 dos
   131 grupos sem antecedente tinham antecedente no outro método (MED
   `n2_no_recorte_do_candidato`; MEM:1072-1074).
4. A `6.01` é conta fixa (`ST_CONTA_FIXA = 'S'` em 45.045 de 45.045 linhas) e
   tem a descrição "Caixa Líquido Atividades Operacionais" nas 700 companhias
   (LB:117; MED `fonte.conta_fixa` e `fonte.descricoes_6_01`).
5. A conferência independente recomendou a leitura por unicidade, citando o
   CPC 03 (R2), itens 18–20A, "preservando a comparabilidade dos operandos e
   sua linhagem; isso não valida automaticamente qualquer par documental"
   (CONF17:284-290). O levantamento de 15/09 descreve o G0 como "sem uso duplo
   de métodos" e o critério de D4 como "ausência de duplicação entre métodos"
   (LEV:151-153, 218).
6. O critério de refutação publicado pelo lote C, "mostrar companhia cujo FCO
   total difira entre métodos no mesmo período", nunca foi cumprido
   (LCR:258).

Julgamentos:
- Pelo CPC 03 (IAS 7), os métodos direto e indireto diferem na apresentação
  da seção operacional; o total do caixa líquido das atividades operacionais é
  o mesmo número. Subtrair acumulados do mesmo exercício apresentados por
  métodos diferentes é aritmética entre medidas da mesma grandeza, desde que
  valham as demais condições: mesma conta, perímetro, exercício, vintage e
  banda. A norma é fonte externa, não conferida aqui (§10, item 1).
- A frase larga da v1 foi escrita quando a derivação do painel em uso não
  atravessava métodos (fato 3). O trimestre derivado entre métodos não existia
  para ela alcançar, e a leitura que segue a origem e o limiar da própria
  linha é a mais fiel ao propósito. **É interpretação**: a letra da v1
  favorece B ou C mais do que a paráfrase do rascunho sugere.
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
conferido; que troca de método nunca coincide com reclassificação; que G0.1 = 0
certifica a comparabilidade dos operandos.

**Riscos e custo.** Risco: o residual acima, não medido. Custo: nenhum em
população; implementação pequena.

**Natureza:** técnica (norma contábil e propósito declarado da v1).
**Confiança:** alta.

**Exposição.** À vista: 117 trimestres em 49 companhias (RASC:201-202,
214-216), 53 companhias que trocam de método, 61 grupos N2 com antecedente no
outro método e a taxa-base (RASC:384-396). A escolha não depende das
contagens: decorre da invariância do total e do risco que a v1 declarou. Com
10 ou 1.000 trimestres assim, a leitura seria a mesma.

**O que mudaria a escolha.** Um caso da mesma companhia, período e perímetro
com totais de `6.01` diferentes por método (o critério de LCR:258); evidência
de que trocas de método coincidem sistematicamente com reclassificação entre
atividades; ou decisão do responsável de que a letra da v1 governa. Nesse
último caso, C (censura) é menos destrutiva que B, que para a rodada por algo
que não é defeito.

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
- **E** (**nova**, considerada e não proposta): C estendida. Censurar também
  a observação cuja janela ou rótulo **some** trimestres de documentos com
  escalas aplicadas diferentes, mesmo sem derivação entre eles, quando algum
  documento não tem veredito para o FCO.

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
sem rótulo e antes de montar `y`, publicam-se: trimestres censurados por
configuração (declaradas × aplicadas) e por companhia; observações
(companhia, D) perdidas por esse motivo, com motivo próprio no inventário de
descartes. Contraprovas do executor: trimestre heterogêneo com operando sem
veredito → censurado; com os dois operandos decididos para o FCO → usado;
construtor que use trimestre censurado → G0.5 reprova.

**O que esta regra não é.** Não é tolerância e não reutiliza o 0,5% do G0.3.
Não corrige escala nem afirma que os trimestres censurados estavam errados.
Não alcança documento de escala errada **homogênea** com os vizinhos, nem a
soma de trimestres de escalas diferentes que não foram derivados um do outro
(por exemplo, o 4T de um exercício e o 1T isolado do seguinte): esses casos
continuam cobertos só pelo G0.3, no ativo.
```

Linha nova na tabela do §5 (RASC:183-189):

```markdown
| G0.5 | Nenhum trimestre com escalas heterogêneas não adjudicadas para o FCO usado em janela ou rótulo | 0 | Censura (§5.5); perda publicada antes de montar `y` |
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
   (RASC:426). A população de risco tem 54 companhias de rótulo misto como
   origem possível (MED `rotulos_de_escala.companhias_por_perfil`).
6. Censura como tratamento de dado já existe no desenho: o que não encadeia "é
   censurado, nunca deslocado" (RASC:103-105); `Y` é indefinido se qualquer um
   dos quatro FCO falta (RASC:90); a política de disponibilidade "não vaza;
   custa perda" (RASC:113-114). A regra 9 do §4.4 admite "congelar a
   quarentena antes de um teste novo" (AG:806-809).

Exemplo sintético do mecanismo do fato 1 (não é dado): acumulado verdadeiro de
FCO de R$ 300 mil em junho e R$ 500 mil em setembro, o que dá 3T isolado de
+R$ 200 mil. Se o ITR de setembro declara `UNIDADE` com números em milhares (o
modo de erro descrito em AG:429-431) e o de junho declara `MIL` corretamente,
o painel tem 300.000 e 500 reais, e o 3T derivado sai 500 − 300.000 =
**−299.500**: sinal trocado, módulo da ordem do acumulado anterior. No erro
inverso (junho errado, setembro certo), sai 500.000 − 300 = **+499.700**:
sinal certo, módulo 2,5 vezes o verdadeiro. Os dois casos podem mudar o sinal
do TTM (elegibilidade) e de `S1`/`S2` (rótulo).

Julgamentos:
- **A tolerância de A é contada no denominador errado.** Com D cerca de 44
  dias depois do fim do trimestre-âncora (mediana do ITR, AG:587-589), o
  trimestre seguinte já começou e q1 é o segundo depois da âncora (regra de
  AUD:743-759). Então, na grade regular, um trimestre contamina da ordem de
  uma dezena de observações (até 8 janelas + 4 rótulos), e uma linha de ativo
  da ordem de uma. O mesmo 0,5% é muito mais permissivo em G0.5 do que em
  G0.3. **Limite grosseiro por construção, não medição:** 82 trimestres × 12 ≈
  1.000 observações, cerca de 9% das 10.748, antes de descontar sobreposição.
  O teto de A (0,5% de 22.088 ≈ 110 trimestres) admitiria cerca de 1.300
  observações, cerca de 12%.
- **A contaminação empurra na direção de aprovar.** Erro de medida ou de
  classificação sem relação com o rótulo tende a atenuar associações.
  Ilustração, não medição: se uma fração `c` das observações tiver janela ou
  rótulo sem relação com o componente, a taxa de cada faixa tende a
  `(1 − c)·r_faixa + c·r̄`, e a amplitude a `(1 − c)` vezes a verdadeira. Com
  `c = 9%`, uma amplitude verdadeira de 0,165 aparece como cerca de 0,150; com
  12%, cerca de 0,145, na zona cinzenta. Em T2, as duas AUCs se aproximam de
  0,5 e a lacuna encolhe. Contaminação real não é aleatória e o efeito pode
  ser outro; a direção esperada é a da aprovação, o lado oposto da previsão
  registrada no §1 do rascunho.
- **C troca contaminação por perda, e a perda é inventariável sem rótulo.**
  As cerca de 1.000 observações do limite acima são as mesmas nos dois casos:
  contaminadas sob A, fora da amostra sob C. A perda é contagem estrutural,
  permitida pelo O1.2 (LB:93-95) e publicável antes de montar `y`.
- **C não é "passar G0 por remoção".** A proibição do lote C (G4-pp,
  LC:152-154; RASC:177) é de excluir **documento** para fazer G0.3 passar. C
  não exclui documento, não toca no ativo nem em G0.3 e não decide o veredito
  de G0 por esses trimestres. Suspende uma **operação** que o próprio pipeline
  faz, a subtração entre acumulados cuja unidade não está estabelecida.
- **Por que não D:** sob a regra v4, nenhum documento pode ser decidido para o
  FCO (nenhum fluxo `6.x` prova escala; RASC:527-529), então D bloqueia G0
  indefinidamente por um motivo que C já neutraliza. A escolha entre C e D é
  entre medir sem esses trimestres ou não medir.
- **Por que não E por padrão:** E fecha um resíduo que C deixa, a soma entre
  trimestres de documentos com escalas diferentes que não foram derivados um
  do outro (por exemplo, 4T de um exercício e 1T isolado do seguinte). Mas vai
  além da população contratada em G5.1 (CRF:134-137), sobrepõe-se à tolerância
  que a v1 congelou para as mesmas transições no G0.3 (V1:132, 135-137) e tem
  perda sem nenhum limite já publicado. É a opção certa se o responsável
  quiser eliminar toda aritmética entre escalas não adjudicadas, e não só a
  derivação.
- Efeito colateral declarado: se uma companhia declarar `UNIDADE` no ITR e
  `MIL` na DFP todos os anos (o padrão de AG:429-431), todo 4T derivado é
  heterogêneo. Sob C, nenhuma janela de oito trimestres contíguos se forma e a
  companhia sai inteira da amostra. Sob A, fica inteira, com 4T da ordem do
  FCO anual e 1T a 3T mil vezes menores.

**O que muda.**
- População: sai toda observação cuja janela ou rótulo exija trimestre
  censurado (limite grosseiro de cerca de 1.000, concentradas em companhias de
  rótulo misto).
- Gates: linha G0.5 nova (uso = 0); G0.3 intacto; G1 estrutural recontado.
- Amostra: menor, montada sem rótulo, com a perda publicada antes de `y`.
- Executor: estado ou filtro antes de `construir_amostra`; motivo próprio de
  descarte; verificação pela linhagem; contraprovas. O `diagnostico_g0_5`
  (GAT:310-342) passa a alimentar a população.
- Rascunho: §13 ganha "observação que use trimestre no estado
  `escala_heterogenea_nao_adjudicada`"; §14 (RASC:590) deixa de pedir "o G0.5
  com o limiar decidido".

**O que não se pode alegar.** Que os trimestres censurados estavam errados;
que a amostra restante está livre de erro de escala (erro homogêneo dentro de
um trecho e somas através de transição sem derivação não são alcançados, o
segundo só por E); que os resultados valem para companhias com transição de
escala não adjudicada; que G0.5 = 0 atesta a qualidade da escala (atesta uso,
não dado).

**Riscos e custo.** Custo: perda de observações, concentrada; companhia com
padrão anual sai inteira. Risco de seleção: T1 e T2 são medidos sem as janelas
em torno de transições não adjudicadas. Risco de implementação: censura errada
vira perda silenciosa, o que o inventário e a verificação de uso mitigam.
Resíduo não coberto: o descrito em E.

**Natureza:** política/risco (regra de dado nova, que troca viés de
contaminação por viés de seleção). **Confiança:** média.

**Exposição.** À vista: 82/22.088 = 0,3712% (vigente), 56 (0,2535%, execução
3), 38 (0,172%, execução 2), 83 (16/09, antes de adjudicar) e as configurações
43/43, 8/39 e 5/5 (RASC:226-227, 248-257, 427, 434-436), além da taxa-base
(RASC:384-396). Sei que 0,3712% passaria sob A e reprovaria sob D. C não tem
limiar, então nenhum número foi escolhido com esse valor à vista, e C não
reprova G0 por esses trimestres. O limite de perda usa 82, contagem estrutural
permitida (LB:93-95). Nenhum número de desfecho participou.

**O que mudaria a escolha.**
- A perda real, se o responsável quiser vê-la antes de decidir. É contagem
  estrutural (O1.2), medível com `calcular_rotulo=False`. Perda que ameace os
  mínimos do T1 indicaria que o painel não sustenta a medição sem adjudicar o
  FCO, o que é argumento para D (bloquear), não para A (tolerar).
- Rota de prova do FCO que adjudique a maior parte dessas derivações: a
  censura encolhe sozinha, sem mudar a regra.
- Preferência do responsável por não mudar a população. Nesse caso, A, com
  duas frases acrescentadas ao texto do rascunho: "(i) a tolerância é contada
  em trimestres, mas cada trimestre entra em até oito janelas e quatro
  rótulos, e a fração de observações expostas pode ser da ordem de dez vezes a
  de trimestres; (ii) contaminação sem relação com o rótulo tende a atenuar T1
  e T2, isto é, a favorecer a aprovação."

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
- **D** (**nova**, considerada e não proposta): só datas em que a janela de
  oito trimestres ou o ativo mudam (deduplicação).

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
e a de documento cujo FCO não é utilizável. Uma data de disponibilidade
tardia pode gerar observação com a mesma janela da anterior; não se
deduplica, e toda inferência agrupa por companhia.

O executor publica o número de datas D por companhia e os descartes por
motivo; a contagem `fco_ttm_nao_positivo` continua omitida enquanto vigorar o
O1.
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

Julgamentos:
- Com D na chegada da informação de FCO de cada companhia, a distância entre o
  último trimestre da janela e q1 fica quase constante (q1 costuma ser o
  segundo trimestre depois da âncora). O horizonte efetivo é homogêneo entre
  companhias. Uma grade de calendário (C) faria esse horizonte depender do
  atraso de cada companhia (fato 6), que pode estar ligado à situação dela.
- B acrescenta, para cada documento com mais de uma versão, uma D na recepção
  da v1, quando por construção o número recém-recebido não está em mãos (fato
  3). Seria uma observação com um conjunto de informação que nenhum analista
  teve. B também dá mais peso a quem republica mais, e republicar pode estar
  ligado à situação da companhia (hipótese plausível, não medida).
- A amostra as datas em que muda a informação que T1 e T2 examinam (fato 5).
- A é o comportamento já contratado e testado, com o menor risco para o
  executor.
- D atacaria um defeito real de A (datas de disponibilidade tardia que repetem
  a janela anterior), mas é regra nova sem medição do tamanho do problema. A
  dependência entre observações da mesma companhia já é tratada por
  agrupamento (AG:802-805).

**O que muda.**
- Código: nada; o texto fixa o que o código faz.
- População e amostra: nenhuma mudança em relação ao vigente, salvo o efeito
  do §5.5 se C for aprovada.
- Executor: publicar o número de D por companhia.
- Rascunho: §13 ganha "observação com D fora da grade do §6.1".

**O que não se pode alegar.** Que D representa todos os momentos de decisão de
um analista; que as observações são independentes (há quase-duplicatas); que a
grade é exógena ao comportamento de arquivamento, já que segue as datas de
cada companhia.

**Riscos e custo.** Quase-duplicatas em datas de disponibilidade tardia, com
peso extra a companhias com muitas postergações. Companhias sem oito
trimestres válidos contíguos não geram observação, em qualquer grade. Custo:
nenhum.

**Natureza:** técnica, com efeito de seleção declarado. **Confiança:** alta,
quanto à preferência sobre B e C. Os efeitos de seleção de qualquer grade não
são mensuráveis sem o desfecho.

**Exposição.** À vista: G1 estrutural (10.748/502 vigente; 10.750/503 na
execução 3), P2 (3.077 trimestres, 6.728 pares, 4.175 chaves; RASC:437-439), a
taxa-base e os ≈ 2.865 a 2.867 descartes por `FCO_TTM ≤ 0` (RASC:397-402),
contagem que o O1 proíbe e que o §11 declara. Nenhum desses números orientou a
escolha, que é estrutural.

**O que mudaria a escolha.** Decisão de tratar atualização só de balanço como
momento de decisão, se componentes de ativo fossem centrais. Ou medição
estrutural, antes de congelar, mostrando muitas quase-duplicatas, o que seria
argumento para D, decidida antes de medir.

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

**Proposta: B, com piso de 30 companhias.**

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
a 0,5/√k, que é 0,091 com k = 30. Publicam-se, ao lado da lacuna,
`companhias_com_os_dois_rotulos`, `companhias_na_amostra` e o número de
observações nessas companhias. Contraprovas do executor: 29 companhias com os
dois rótulos → INDECIDÍVEL; 30 → T2 decidido pelo limiar.
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
   medir.

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
- Uma regra de precisão (por exemplo, erro-padrão máximo) dependeria da
  dispersão das AUCs por companhia, que é função do desfecho, e não pode ser
  fixada às cegas. Um piso de contagem pode.
- C daria proteção de precisão. Não a proponho por padrão porque ela muda a
  regra de decisão de T2 além do suporte, e o rascunho promete T2 "idêntico à
  v1" (RASC:324). Também importaria os 2.000/10% do T1 sem validação para
  outra estatística. Se o responsável quiser simetria com o T1, o texto é:
  "Se a lacuna for < 0,12, reamostram-se companhias 2.000 vezes; se a
  frequência de lacuna ≥ 0,12 passar de 10%, T2 é INDECIDÍVEL."

**O que muda.**
- População: nenhuma.
- Teste: T2 pode sair INDECIDÍVEL por suporte.
- Executor: `teste_t2` levanta `AmostraInsuficiente` abaixo de 30, com
  contraprovas de 29 e 30 companhias; o artefato publica as três contagens.
- Rascunho: §13 ganha "T2 decidido com menos de 30 companhias com os dois
  rótulos".
- Baselines: a AUC intra de B1 a B3 segue a regra de completude do §9, sem
  piso novo.

**O que não se pode alegar.** Que T2 com 30 ou mais companhias tem precisão
para decidir perto de 0,12; que a discriminação intra-companhia vale para
companhias com um só rótulo; que 30 tem validação estatística.

**Riscos e custo.** Se menos de 30 companhias tiverem os dois rótulos, T2 fica
INDECIDÍVEL e a rodada não chega a PRONTO PARA CHALLENGER. Implementação
pequena.

**Natureza:** política (suporte mínimo). **Confiança:** média. É alta quanto a
existir piso; o número é política.

**Exposição.** A taxa-base agregada, cerca de 5% (RASC:384-396), permite
prever que 30 companhias com os dois rótulos provavelmente existem. O número
não foi calibrado por essa expectativa: copia o mínimo da v1 (V1:174). Nenhuma
contagem de companhias com os dois rótulos foi feita, porque exigiria `y`.

**O que mudaria a escolha.** Preferência do responsável por outro mínimo, ou
pela opção C, desde que decidida antes de medir e nunca depois de ver a
contagem.

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
`6.01` provadas; prova de saldo (`1`, `2`, `1.01.01`) sozinha não entra.

**O mesmo critério vale para o que G0.5 conta como decidido:** para o FCO,
confirmação ou correção apoiada só em prova de saldo não torna o operando
adjudicado.

Correção só do ativo continua vedada enquanto G0.3 e G0.5 lerem o veredito
por documento. Rotas para provar o FCO (anexo do grupo 192; identidade interna
da DFC) exigem contrato próprio e, se lerem o FCO para algo além de igualdade
entre duas fontes, decisão explícita sobre o O1. A premissa da opção A (a
escala verdadeira é uma só por formulário) só pode ser adotada depois de
testada em amostra pré-registrada, no molde do teste da premissa de herança
(lote C, S5/E10).
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
   (RASC:554-565; ALC:193-198).
8. O G0.5 conta como decidido todo documento com veredito `confirmada`,
   `corrigida` ou `herdada` (GAT:288-299).

Julgamentos:
- A usa uma premissa não testada, a de que a escala verdadeira é uma só por
  formulário, para estender a prova à conta que define o rótulo. A premissa é
  plausível (demonstrações costumam usar um único nível de arredondamento),
  mas o projeto exige testar premissa do mesmo tipo antes de usá-la (fato 3).
- As consequências são assimétricas. Correção errada do FCO corrompe o rótulo
  e cinco dos seis componentes em silêncio. Correção que falta deixa G0
  reprovado, de modo visível. B erra do lado visível.
- A extensão ao "decidido" de G0.5 é necessária por coerência. Sem ela, o
  G0.5 trataria como adjudicado o FCO de um documento só confirmado por saldo,
  e a premissa de A voltaria por outra porta (fato 8; AG:547-551).
- B não piora o estado atual: sob as duas opções, G0 segue reprovado (fato
  7).

**O que muda.**
- Hoje: nada, porque a v4 não tem correções (RASC:422-425).
- Para o futuro: o validador do manifesto (produtor e consumidor) exige
  evidência localizada da `6.01` em toda linha que altere o FCO; o conjunto
  "decidido" do G0.5 passa a ser por FCO. Contraprovas: linha só com prova de
  saldo é recusada; operando confirmado só por saldo conta como não decidido
  no G0.5.
- População: nenhuma mudança agora.
- Rascunho: §13 ganha "correção de FCO sem prova que alcance o FCO".

**O que não se pode alegar.** Que o FCO dos documentos com prova de saldo está
errado (está indeterminado); que B melhora G0 (não melhora agora); que a
premissa de A é falsa.

**Riscos e custo.** Custo: G0 permanece reprovado até existir rota de prova do
FCO, com contrato próprio e talvez decisão sobre o O1 (§10, item 3). Risco: se
a premissa de A for verdadeira, B atrasa o estudo sem ganho.

**Natureza:** técnica/risco. **Confiança:** alta.

**Exposição.** À vista: contagens estruturais (132, 112, −2) e os documentos
candidatos da GEOM-1, um deles documento de desenho da regra (RASC:558-559).
Nenhum número de desfecho. A escolha não depende de quais documentos se
qualificam: B não qualifica nenhum hoje e é proposta pelo argumento da
premissa.

**O que mudaria a escolha.** Um teste pré-registrado da premissa de A, em que
documentos com prova de saldo e prova de FCO independentes não mostrem
nenhuma discordância, no molde do E10 (LC:252-264).

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
  às formas e ao documento em exame, proíbem uso como oráculo, tornam
  explícita a não retroatividade e exigem contraprovas.

**Proposta: C.**

Texto pronto do adendo (novo documento datado, vinculado ao O1 de LB:85-100):

```markdown
## Adendo ao O1 — exceção protetiva (aprovado em [data] pelo responsável)

Vale enquanto vigorar o O1, até o congelamento do pré-registro v2.

1. **Onde.** Só na verificação que decide se uma saída pode ser gravada ou
   publicada (hoje, `_magnitudes_protegidas` e `verificar_sem_valores`, em
   `scripts/conferir_alcance_geom1_rank03b.py`).
2. **Sobre quais valores.** Só valores de FCO do próprio documento e período
   em exame, já lidos em memória para a igualdade autorizada pelo contrato da
   execução, e só nas formas que esse contrato enumera para a busca.
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
   construídos para sondar valores.
6. **O que não autoriza.** Busca de FCO arredondado; publicação de
   divisibilidade; adjudicação de escala pelo FCO; soma de FCO em janela, TTM
   ou rótulo; métrica de modelo; reuso, sobre o FCO, da função de ativo
   arredondado.
7. **Retroatividade.** Não reclassifica as execuções que já calcularam piso e
   teto em memória (correção RAG, 25/09): ficam como histórico, como diz o
   contrato de pendências de 26/09 (P4).
8. **Vínculo e contraprovas.** O adendo é fixado por hash nas duas entradas da
   busca e conferido antes de ler pacotes. Contraprovas: saída que contenha
   piso ou teto de uma forma do FCO é recusada; nenhum retorno, atributo,
   exceção ou log da verificação contém dígitos de valor protegido; adendo com
   hash diferente derruba a execução antes de ler pacote.
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
   corrente, comparativo do exercício anterior, individual, ×1.000 e ÷1.000
   (VER:668-673).
3. Notas em milhares imprimem inteiros arredondados (CRAG:162-165). É nessa
   forma que um FCO apareceria num trecho publicado das notas. A forma ÷1.000
   raramente é inteira, e só piso e teto a protegem.
4. A máscara lexical, que não publica trecho de linha com vocabulário de caixa
   ou fluxo, "reduz o canal, não o fecha" (ALC:302-306). A máscara já falhou
   em sintético mais de uma vez (ALC:251-264).
5. Piso e teto das formas do FCO já foram calculados em memória nas execuções
   da correção RAG de 25/09 (RAG:261; ARAG:134-143). O contrato de 26/09 lê o
   O1.3 estritamente (sem autorização explícita), manda preservar o detector
   sem executá-lo sobre FCO real até a decisão e mantém as execuções passadas
   como histórico (CPEND:75-86; PEND:17).
6. Se recusada, a alternativa é separar os valores de FCO, conservar só as
   magnitudes exatas e documentar a redução de cobertura (DEC:39-42;
   ARAG:141-143).

Julgamentos:
- As operações são cegas ao sinal (módulo), de um só período e documento, sem
  agregação e sem janela futura. Não produzem informação sobre `Y`, que depende
  do sinal de somas de semestres futuros. O único canal de saída é a recusa,
  que diz no máximo que algum número publicado coincidiu com alguma magnitude
  protegida, sem dizer qual, sem sinal e sem valor.
- Recusar a exceção enfraquece a garantia de não publicação do próprio O1.3
  exatamente na forma mais provável de vazamento (fato 3), para evitar
  operações que não expõem nada. Aprovar serve ao propósito do O1 melhor do que
  recusar.
- As emendas fecham os dois riscos reais do texto de DEC: uso como oráculo
  (sondar valores por recusas sucessivas) e ampliação de escopo (outras
  formas, outros períodos, reuso da função).

**O que muda.**
- Código do verificador: nenhuma mudança de lógica (PEND:17).
- Executor da busca: vínculo por hash do adendo nas duas entradas e
  contraprovas (DEC:33-37).
- Se recusada (opção B): mudança de código para separar as formas do FCO, com
  redução de cobertura documentada.

**O que não se pode alegar.** Que a exceção autoriza busca de FCO arredondado
(DEC:44-48; CPEND:82-86), adjudicação de escala pelo FCO ou cálculo de rótulo;
que o estudo é inteiramente cego (o §11 declara exposições); que as execuções
de 25/09 foram autorizadas retroativamente.

**Riscos e custo.** O uso como oráculo fica fechado pela cláusula 5, mas por
regra, não por código. A ampliação de escopo fica fechada pelas cláusulas 2 e
6. O resíduo é a recusa, que revela no máximo um bit por execução. Custo: o
adendo e as contraprovas.

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
   permitida porque o total é invariante por norma e nenhum defeito foi
   demonstrado. A derivação entre escalas não adjudicadas é censurada porque o
   defeito é demonstrado e produz erro de 1.000× e troca de sinal. Um
   trimestre que seja as duas coisas cai no §5.5.
4. **§3.2 vem antes de tudo.** A exclusão muda o universo antes de qualquer
   gate; todos os números do §11.3 passam a históricos e precisam ser medidos
   de novo.
5. **§8.1 vem depois das perdas.** §3.2 e §5.5 reduzem companhias. Se sobrarem
   menos de 30 com os dois rótulos, T2 é INDECIDÍVEL, e isso nunca é motivo
   para rever §3.2 ou §5.5 depois de visto.
6. **O1 e §12-bis.** B exige prova que alcance o FCO. As rotas nomeadas (anexo
   do grupo 192; identidade interna da DFC) pedem contrato próprio e, se lerem
   o FCO para algo além de igualdade, decisão sobre o O1. A exceção protetiva
   não as autoriza (DEC:44-48; CPEND:82-86). Há uma ambiguidade a resolver
   nesse contrato (§10, item 3).
7. **G0 continua reprovado.** Nenhuma combinação muda o G0.3 (132 > 112). Com
   B, nenhuma correção é possível até existir rota de prova do FCO
   (DEC:106-113; RASC:566-570).
8. **Ordem sugerida de decisão:** §12-bis → §5.5 → §5.1 → §3.2 → §6.1 → §8.1.
   O O1 é independente do rascunho, mas condiciona a execução das rotas de
   prova.

---

## 9. Tabela-resumo

| Item | Proposta | Relação com rascunho/DEC | Muda a população? | Natureza | Confiança |
|---|---|---|---|---|---|
| §3.2 | Excluir `ll3_13_%` | Igual à proposta do rascunho | Sim (−3 companhias) | Técnica | Alta |
| §5.1 | Unicidade; derivação entre métodos permitida, contada e sujeita a F1–F6 e G0.5 | Igual, com condições escritas | Não | Técnica | Alta |
| §5.5 | Censura dos trimestres heterogêneos não adjudicados; G0.5 = uso zero | **Diverge** (opção nova C) | Sim (perda inventariada) | Política/risco | Média |
| §6.1 | Manter a grade por disponibilidade do FCO utilizável | Igual | Não | Técnica, com seleção | Alta |
| §8.1 | Piso de 30 companhias com os dois rótulos; abaixo, INDECIDÍVEL | **Diverge** da proposta; é a alternativa do rascunho, com número | Não | Política | Média |
| §12-bis | Opção B, estendida ao "decidido" do G0.5 | Igual, com extensão nova | Não, por ora | Técnica/risco | Alta |
| O1 | Aprovar a exceção com oito cláusulas | Igual à recomendação de DEC, com emendas | Não | Política | Alta |

**Pontos do rascunho a atualizar junto, se as propostas forem aprovadas:**
lista de pontos pendentes (RASC:15-20); linha G0.1 da tabela do §5
(RASC:185); linha G0.5 nova na mesma tabela (se C); §13 (RASC:572-580), com
as condições novas indicadas nos itens 2, 3, 4, 5 e 6; §14, "Ainda não
cumpridos" (RASC:590). Título, nome do arquivo e SHA-256 só mudam no
congelamento (RASC:5-7), depois do executor testado e da conferência
independente (DEC:99-104).

---

## 10. Limitações e contradições encontradas nas fontes

1. **O CPC 03 não está no repositório, e não há rede.** Os itens 18–20A são
   citados pela conferência de 17/09 (CONF17:284-290, com link para a CVM) e
   pelo lote C (LC:59-60). Não os conferi. A invariância do total operacional
   entre métodos é conhecimento normativo geral (IAS 7), não verificado aqui.
2. **`becos_sem_saida.md` está desatualizado.** BECOS:96 ainda registra "G0 e
   G1 aprovam (47 saltos, 0,2092%)" como estado de 16/09, sem a reprovação
   vigente de 18/09 (RASC:422-426; MEM:466-481).
3. **O1 × identidade da DFC.** O O1 permite contar "identidades contábeis"
   (LB:93-95), e o lote B mediu identidades de soma da DFC (LB:126; MED
   `fonte.identidades_contabeis`). Já o relatório de alcance e o MEMORY dizem
   que o fechamento da DFC "soma o FCO e o O1 hoje proíbe" (ALC:288-290;
   MEM:408-410). A distinção plausível, entre contar se a identidade fecha e
   usar o fechamento como prova de escala, não está escrita em lugar nenhum.
   Pesa sobre a rota de prova do FCO da opção B do §12-bis.
4. **Piso e teto sob o O1.** O adendo RAG de 25/09 diz que o uso protetivo
   "segue o O1 como ele vem sendo aplicado desde o R3" (ARAG:140-143). O
   contrato de 26/09 diz que o O1.3 não o autoriza explicitamente
   (CPEND:75-81). Segui a leitura mais estrita e mais recente, que é a de DEC.
5. **Letra da v1 × paráfrase do rascunho no G0.1.** V1:130 ("usa … para o
   mesmo (companhia, trimestre)") × RASC:185 e 195 ("sem soma"). Tratado no
   item 2.
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

---

## 11. O que esta proposta não faz

- Não altera o rascunho, nenhum arquivo do repositório nem o estado do git.
  Este é o único arquivo escrito.
- Não decide, não aprova e não congela. Não autoriza executor, medição ou
  treino.
- Não mede nada: nem rótulo, taxa, T1, T2, AUC ou baseline, nem contagem
  estrutural. Os limites de ordem de grandeza dos itens 3 e 5 são aritmética
  sobre números já publicados.
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
