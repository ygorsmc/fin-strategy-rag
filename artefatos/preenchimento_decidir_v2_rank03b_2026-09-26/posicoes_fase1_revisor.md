<!--
Posições da fase 1 (às cegas) do revisor independente (auditor-conformidade,
somente leitura, contexto separado), devolvidas em 26/09 antes de ver a proposta
do preenchedor. Transcritas na íntegra. É saída de modelo, não decisão humana.
-->

# Fase 1: posições às cegas sobre os sete itens do Rank 3-B (revisor independente)

**Aliases usados nas citações** (todos sob `/home/ygor/Antigravity_Projects/fin-strategy-rag/`):
- **Pré-registros e contratos:** v1 = `resultados/pre_registro_rank03b_consumo_operacional_2026-09-11.md` · v2 = `resultados/pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md` · LB = `resultados/contratos_lote_b_rank03b_2026-09-16.md` · LC = `resultados/contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md` · CRF = `resultados/contratos_correcao_crf01_crf03_rank03b_2026-09-17.md`
- **Decisões e relatórios:** DEC = `resultados/decisoes_executor_v2_rank03b_2026-09-26.md` · PEN = `resultados/contratos_pendencias_geom1_rank03b_2026-09-26.md` · CONF17 = `resultados/conferencia_pre_treino_rank03b_2026-09-17.md` · ALC = `resultados/alcance_geom1_rank03b_2026-09-24.md` · RAG = `resultados/correcao_rag_alcance_geom1_rank03b_2026-09-25.md` · GEOM = `resultados/escala_geometrica_rank03b_2026-09-18.md` · D7 = `resultados/pendencias_desbloqueio_treino_dfc_2026-09-15.md`
- **Artefato:** MED = `artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json`
- **Scripts:** AUD = `scripts/auditar_rank03b_consumo_operacional.py` · GAT = `scripts/gates_painel_pesquisa_rank03b.py` · PP = `scripts/painel_pesquisa_rank03b.py` · VER = `scripts/conferir_alcance_geom1_rank03b.py`
- **Raiz:** AG = `AGENTS.md` · MEM = `MEMORY.md`

## Declaração de exposição

- **Números de desfecho vistos e não usados:** ao ler o §11 (v2:382–402) e a RA7 (LB:286–289), vi a taxa agregada do evento no painel compartilhado (≈5%), "y diferente: 3", "FCO TTM não positivo −5" e ≈2.865 descartes por TTM ≤ 0. Nenhuma posição abaixo depende deles. O piso do §8.1 vem do piso de T1 e do D7. O limiar do §5.5 vem da regra do T1. Também vi o 82/22.088 do G0.5 (v2:427); minha proposta é mais estrita que ele e não depende dele.
- **Não fiz:** não abri DuckDB, RAD nem PDF, não li valor de FCO e não executei nada. Li código e o JSON estrutural MED.
- **Citações do CPC 03:** vêm de memória (sem rede). Conferir no texto.

## A. Critérios de revisão, declarados antes de ver a proposta

1. **Mérito, não efeito no gate.** Nenhuma das sete escolhas destrava G0 hoje: G0.3 tem 132 saltos contra o limite de 112 (v2:425, 560; DEC:106–113). Justificativa do tipo "assim passa" é recusada.
2. **Regra operacional completa.** Unidade, numerador, denominador, limiar, estado de falha e posição na cadeia. Cada regra precisa de contraprova que exercite a **decisão**, não só o campo publicado (AG:796, regra 7). Cada regra nova entra também no §13 (falsificação) e no §14 (exigência do executor).
3. **Nada aprova por ausência.** Suporte insuficiente leva a INDECIDÍVEL ou exceção, nunca a aprovação (AG:782, regra 4).
4. **Nada é removido para passar.** Exclusão ou censura só como regra de população fixada antes, com o efeito sobre os gates publicado (AG:806, regra 9).
5. **Unidade certa.** Fração de trimestres não limita fração de observações (AG:802, regra 8). Inferência por companhia.
6. **Estimando intocado.** Y, os seis componentes e 0,15/0,12/500/30 não mudam. Só se acrescenta no sentido conservador (v1:171–172).
7. **Evidência contábil com fonte primária.** Identidades com tolerância explícita; escala provada **por conta**.
8. **Três passos distintos.** Aprovar regras ≠ congelar pins ≠ autorizar medição. O O1 vale até o terceiro.
9. **Exposição declarada por decisão.** Cada escolha registra que números estruturais eram conhecidos quando foi feita.

**Armadilhas por item:**
- **§3.2:** decidir por setor depois de ver desempenho; vender "não financeira" como completa.
- **G0.1:** chamar redação nova de "leitura"; perder a checagem original de dupla contagem; censura seletiva.
- **G0.5:** 0,5% por analogia; denominador em trimestres; olhar heterogeneidade só entre operandos; "decidido" por documento; tolerar erro já demonstrado.
- **Grade de D:** pseudo-réplica do rótulo; seleção por atraso ou reapresentação.
- **T2:** aprovar com uma companhia; escolher o piso depois de ver o número.
- **§12-bis:** premissa da opção A adotada por decreto; opção B sem rota de prova definida.
- **O1:** verificador usado como oráculo; exposição retroativa não declarada; O1 caducar na aprovação das regras.

## B. Posições

### §3.2 — Seguradoras

**Escolha:** excluir `plano_contas LIKE 'll3_13_%'`, como propõe o rascunho.

**Razão principal:**
- O estimando é consumo operacional de companhia **não financeira** (v1:66, 96–111).
- Em seguradora, prêmios, sinistros e aplicação das reservas entram no fluxo operacional (CPC 03 (R2) ≈ IAS 7 §§14(e) e 15). Numa holding de seguros, dividendos recebidos podem ser operacionais (§33). O sinal do 6.01 ali não mede capital de giro.
- É o mesmo critério estrutural e conservador da v1. No universo de 700 companhias, os únicos planos são `ll3_11_*` (697) e `ll3_13` (3) (MED:24–31). Duas das três usam a descrição de seguradora em 24 linhas (MED:13–22, 44–55).

**Riscos:**
- Seguradora registrada sob `ll3_11` continua dentro (não há SETOR_ATIV, v1:113–116). Declarar.
- Se algum dos 132 saltos for dessas três companhias, a exclusão reduz o G0.3 por remoção. Publicar o efeito e não usá-lo como motivo.

**Natureza:** técnica (definição de população). **Confiança:** alta.

### §5.1 — G0.1

**Escolha:** unicidade, com derivação entre métodos permitida e declarada. Deve ser redigida como **redefinição** do gate, não como "leitura" da v1. O gate passa a ser:
- (a) zero (companhia, período) com 6.01 de DFC_MD e DFC_MI somados, que é o risco original;
- (b) zero trimestre válido repetido;
- (c) método por operando registrado na linhagem, com a contagem estrutural publicada (117 trimestres em 49 companhias).

**Razão principal:**
- A letra da v1 ("nenhuma observação usa DFC_MD e DFC_MI para o mesmo (companhia, trimestre)") conflita com a origem e o limiar declarados na mesma linha: "somar os dois duplica o caixa … 0 casos somados" (v1:130).
- A_k − A_{k−1} subtrai acumulados de períodos distintos da mesma conta 6.01, que é conta fixa (MED:33–43).
- O caixa operacional líquido é um só número nos dois métodos (CPC 03 §§18–20A; CONF17:284–290).
- Nenhum documento traz os dois métodos (MED:56).

**Alternativas rejeitadas:**
- *Literal:* aplica a letra contra o risco que a própria v1 declarou.
- *Censura:* é regra de perda sem mecanismo de erro demonstrado. Cada trimestre censurado quebra até 8 janelas de features e 4 de rótulo (a contiguidade é exigida em AUD:735–741). E troca de método pode correlacionar com reestruturação, o que é seleção.

**Riscos:**
- A troca de método pode coincidir com mudança de política de classificação (juros, dividendos, IR; CPC 03 §§31–36). Isso não é específico da troca e o G0.1 não detecta. Declarar como limitação.
- Uma sensibilidade não decisiva (T1 sem as observações que usam trimestre entre métodos) é aceitável **só se declarada agora**.
- Declarar que a escolha foi feita sabendo que a leitura literal reprova (v2:428). Hoje ela não decide o veredito, porque o G0.3 reprova de qualquer forma.

**Natureza:** técnica (contábil) + redação. **Confiança:** alta.

### §5.5 — G0.5

**Escolha:** G0.5 decisivo, mas **não** na forma proposta (0,5% dos trimestres). Três mudanças:

1. **População ampliada.** Uma observação (companhia, D) da amostra cega do G1 está em risco se alguma soma que ela usa mistura escalas declaradas ou aplicadas com algum documento sem veredito. As somas são:
   - os operandos de um trimestre derivado (é a definição atual);
   - o conjunto de documentos da janela de 8 trimestres, que contém o TTM da elegibilidade;
   - o de S1;
   - o de S2.
2. **"Decidido" por conta.** Um veredito de saldo não decide o FCO.
3. **Limiar derivado da margem do T1, não por analogia com o G0.3.** Com m observações em risco e n_min = menor faixa da partição congelada do §7, calculada na amostra cega, aprova só se 2m/n_min < 0,03. O 0,03 é a largura da zona cinzenta [0,12; 0,15).

G0.5 é medido pelo executor, sem rótulo, depois da autorização.

**Razão principal:**
- **Escala é propriedade do documento** (zero documentos com mais de uma escala, MED:57).
  - Erro de escala *consistente* preserva sinais e razões: Y, a elegibilidade, T1.1, T1.3 e T1.6 não mudam.
  - Mistura de escalas *dentro* de uma soma quebra essa invariância e pode inverter o sinal de S1, S2 ou do TTM.
- **O G0.5 atual só olha os operandos de um trimestre derivado** (GAT:318–330). A derivação não atravessa exercício (LC:70–74).
  - Um documento isolado mal rotulado no 1º trimestre do exercício entra no TTM, em S1 ou em S2 sem acender nada.
  - Há 71 trechos de um só documento em companhias mistas (MED:196–198).
  - Das 137 transições do painel, 123 têm bruto contínuo (AG:431–433).
- **Fração de trimestres não limita fração de observações** (regra 8).
- **O pior caso é o caso relevante.** Um erro de ×1000 empurra a observação para a faixa extrema, que é onde a amplitude max−min é medida (lição do CAND-04, v1:132).

**Alternativa rejeitada:** "não acrescentar". O G0.3 só olha o ativo; sem G0.5 o rótulo sairia sem nenhuma guarda de escala.

**Riscos:**
- O δ = 0,03 é escolha de política.
- Provavelmente reprova no painel atual. É consequência honesta: o próprio rascunho proíbe elevar limiar para recuperar G0 (v2:531–533).
- Erro já demonstrado continua sendo corrigido, não tolerado por caber no limiar (v2:238–239; CONF17:199–204).

**Natureza:** técnica (unidade e população) + política (δ). **Confiança:** alta nas mudanças (1) e (2) e em rejeitar 0,5% por trimestre; média no δ.

### §6.1 — Grade de D

**Escolha:** manter a grade de disponibilidade das linhas de FCO válidas, e acrescentar agora uma regra: **uma observação por (companhia, q1), a de maior D.** Publicar três contagens estruturais: D por companhia; chaves (companhia, q1) com mais de um D antes da deduplicação; D originados de prova de escala.

**Razão principal:**
- É nessas datas que o conjunto de features muda.
- A alternativa "toda recepção do cadastro" acrescenta D em que a linha ainda não está disponível (a P1 só libera o número na recepção da versão máxima; v2:109–114, LC:121–125). Isso gera janelas velhas com o mesmo q1 e dá mais peso a quem reapresenta: 3.863 de 24.925 documentos têm mais de uma versão, p90 de 260 dias (MED:64–70).
- Mesmo na grade proposta, a deduplicação atual é só por (companhia, D) (AUD:712, 717–721). Dois D no mesmo trimestre civil produzem o mesmo q1 (AUD:747–759). Exemplo: DFP entregue ou reapresentada depois de 31/03 e ITR do 1T em maio.
- Isso é pseudo-réplica do rótulo, concentrada em quem atrasa ou reapresenta — característica plausivelmente ligada a dificuldade financeira, portanto viés potencial na direção do desfecho previsto.
- O maior D usa toda a informação disponível antes do início de q1.

**Riscos:**
- A deduplicação reduz n; publicar o efeito.
- A perda da política P1 concentra-se em quem reapresenta: ≈4,2 mil chaves (companhia, D) caem em intervalo cego (v2:437–439, 454–457). É seleção declarada, não corrigível sem vintages.
- Não medi a frequência real das duplicatas.

**Natureza:** técnica (desenho amostral). **Confiança:** média-alta.

### §8.1 — Suporte da AUC intra

**Escolha:** fixar o piso **agora**. T2 só decide com ≥ 30 companhias com os dois rótulos; abaixo disso, T2 = INDECIDÍVEL, nunca aprovado. Publicar também o IC 95% da lacuna por reamostragem de companhias (diferença calculada dentro de cada reamostra), sem papel decisivo.

**Razão principal:**
- Hoje uma companhia basta (AUD:1143–1147; aprovação em AUD:1165). T2 aprovaria por falta de dados, exatamente o que a regra 4 proíbe.
- 30 é o piso de companhias já congelado para T1 (v1:174; v2:307–308). O D7 exige mínimo "no suporte pertinente" (D7:220).
- Bootstrap por agrupamento com poucas companhias subestima a variância.
- A média simples de AUCs por companhia é ruidosa: uma companhia com 1 positivo e 1 negativo dá AUC em {0; 0,5; 1}.
- Divirjo da CONF17:216–219, que não quis impor piso: este não é arbitrário, porque está ancorado numa regra existente.

**Riscos:** o número é política. A contagem de companhias com os dois rótulos depende do rótulo, e é justamente por isso que o piso tem de ser fixado antes.

**Natureza:** estatística + política. **Confiança:** alta na necessidade do piso; média no valor 30.

### §12-bis — Alcance da prova de escala

**Escolha:** opção B, com a prova admissível definida **por conta**: direta (célula da conta, período, perímetro e unidade, como no método de 24/09) **ou** por cadeia de identidades exatas dentro do mesmo documento até uma conta provada.
- **Para o 6.01:** 1.01.01 provado; 6.05.02 = 1.01.01 em bruto; fechamento exato de 6.05.01 + 6.05 = 6.05.02; e de 6.01 + 6.02 + 6.03 + 6.04 = 6.05.
- **Para o 1:** prova direta, ou 1 = 2 em bruto com 2 provado.
- Um saldo sozinho não corrige o documento inteiro.

**Razão principal:**
- O rótulo e a elegibilidade dependem só do FCO.
- A opção A aplica ao FCO uma premissa não testada: a correção por documento alcança 1 e 6.01 (PP:187, 250, 316; LC:242–245).
- Isso falha aberto: se a premissa não valer, o FCO é multiplicado por mil sem que o G0.3, que só olha o ativo, perceba.
- A cadeia **testa a premissa de A documento a documento**. Com valores inteiros e tolerância ≤ 1, um 6.01 em unidade diferente das demais linhas não fecha; se 6.01 = 0, a unidade é irrelevante. Exigindo as duas condições, a cadeia vale independentemente de quais linhas o sistema da CVM calcula sozinho.
- A igualdade 6.05.02 = 1.01.01 em bruto já foi conferida nos dois documentos, sem tocar no 6.01 (ALC:284–290).

**Ponto de coerência com o O1:**
- O fechamento da DFC, somando o 6.01, já foi calculado para todos os 22.483 períodos como identidade que o O1.2 permite (PP:497–515; LB:93–95; MED:59–62).
- A afirmação de que "o O1 proíbe" esse fechamento (ALC:287–290; MEM:409–410) contradiz isso.
- A saída por documento deve ser só booleana.

**Riscos:**
- A cobertura é mínima. A GEOM-1 provou saldo em 12 de 405 documentos (GEOM:77–85) e faltam 20 saltos para o G0.3 passar (v2:559–560). A opção B não destrava o G0, e nenhuma opção destrava.
- 142900 é documento de desenho da regra (GEOM:101, 110–113); declarar.
- A rota da cadeia exige contrato próprio antes de rodar.

**Condição:** G0.3 e G0.5 têm de ler o veredito por conta antes de qualquer correção parcial (AG:546–556). Sem isso, o ativo já provado errado de 140867 continua errado, violando "erro demonstrado é corrigido" (v2:238–239). A saída é tornar os gates por conta, não adotar a opção A.

**Natureza:** técnica (padrão de evidência) + risco. **Confiança:** alta.

### O1 — Exceção protetiva para piso e teto do FCO

**Escolha:** aprovar, com condições. Se a exceção for recusada, **não** reduzir a proteção tirando piso e teto: trocar a comparação que depende do valor por bloqueio cego nos textos (todo número ≥ 1.000 fora de hash, data ou identidade fixada no pin), que não exige ler FCO.

**Razão principal:**
- A leitura estrita está correta: o O1.3 só permite igualdade entre duas fontes (LB:96–98), e piso/teto é operação adicional.
- Mas piso e teto da forma ÷1.000 são exatamente o FCO arredondado em milhares, que é como as notas o imprimem. Sem eles, esse canal fica aberto nos textos (VER:560–572, 621–622).
- Números JSON ≥ 1.000 já são barrados sem olhar valor (VER:613–615).

**Condições:**
1. O conjunto protegido fica local à verificação: sem retorno nem log, com teste espião.
2. Uma recusa encerra a execução sem gravar nada, uma por execução. Proibido reexecutar com a saída alterada sob o mesmo contrato ou chamar o verificador com textos avulsos — isso o tornaria um oráculo da magnitude do FCO. A recusa é registrada como incidente, sem valor, forma nem token.
3. Só as formas já lidas sob igualdade autorizada; nenhuma leitura nova de FCO para fins de proteção.
4. Adendo datado, fixado por hash nas duas entradas e com vínculo testado antes de ler pacotes (DEC:33–35).
5. Não cobre busca arredondada, evidência de escala nem seleção de documentos (DEC:44–48; PEN:73–93).

**Exposição retroativa a declarar no §11 do v2:**
- As execuções de 25 e 26/09 calcularam, em memória, piso e teto das formas do FCO de 140867 e 142900 antes de haver autorização (RAG:261; ALC:374–376). Não houve recusa.
- As leituras de FCO para igualdade feitas de 24 a 26/09.
- O §11 atual (v2:375–505) não traz nenhuma das duas.

**Duração:** o O1 vale "até ele ser aprovado" (LB:87–88). Aprovar estas escolhas não é aprovar o pré-registro: o O1 continua valendo até a medição real ser autorizada, com pins congelados.

**Natureza:** política/risco. **Confiança:** média-alta. Não verifiquei se as saídas precisam de números ≥ 1.000 em texto além das identidades.

## C. Interações que qualquer proposta precisa respeitar

1. **§12-bis → §5.5.** Sob a opção B, "decidido" é por conta: confirmação de saldo não neutraliza heterogeneidade de FCO. Hoje `documentos_decididos` é por documento (GAT:288–299).
2. **§12-bis ↔ v2:238–239.** Opção B com gates por documento deixa um erro demonstrado sem correção (ativo de 140867). Gates por conta são pré-condição de qualquer correção parcial.
3. **§6.1 → §5.5 → T1.** O G0.5 por observação é medido na amostra cega **já deduplicada**, e n_min vem da partição do §7. Decidir a grade primeiro.
4. **§5.1 ↔ §5.5.** Um trimestre pode ser, ao mesmo tempo, entre métodos e entre escalas. A linhagem precisa carregar método e escala por operando; a unicidade não certifica escala.
5. **§3.2 → denominadores.** Recalcular G0.3, G0.5 e G1 no universo decidido e publicar se a exclusão tocou algum dos 132 saltos.
6. **§8.1 ↔ T1.** Mesmo padrão de "30 companhias no suporte pertinente". A deduplicação do §6.1 não muda quais companhias têm os dois rótulos, porque as duplicatas têm o mesmo Y.
7. **O1 ↔ §12-bis.** O adendo do O1 deve afirmar que identidade contábil com saída booleana está coberta pelo O1.2; senão a rota da cadeia fica bloqueada por uma leitura contraditória.
8. **Todas ↔ congelamento.** Os pins do v2 (`6ca635a9…` e `13520e61…`, §§4 e 13) descrevem um painel com G0 sabidamente reprovado. Congelar agora consumiria o v2 com o veredito já conhecido. Aprovar as regras agora, fixar os pins depois da adjudicação, e manter o O1 vigente até lá.
9. **Lacuna fora dos sete itens.** Nenhum gate cobre erro de escala *consistente*: 17 companhias só UNIDADE, 400 documentos (MED:181–187). Ele afeta só T1.2, T1.4 e T1.5. Declarar como limitação ou pré-registrar uma sensibilidade agora.
