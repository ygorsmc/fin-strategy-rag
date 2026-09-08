# MEMORY.md

> Memória de trabalho entre sessões. Leia no início de toda tarefa; ao final,
> **sobrescreva** o que ficou desatualizado. Não é changelog — é handoff.
> Regras de uso em [AGENTS.md](AGENTS.md#10-memória-entre-sessões--memorymd).
>
> Histórico detalhado de investigações já resolvidas (RN02, chunking,
> propagação de unidade, gates) não vive mais aqui — está fechado em
> `AGENTS.md` (§3) e recuperável via `git log -p MEMORY.md` se precisar do
> raciocínio completo. Esta versão foi enxugada em 2026-08-23 por exceder a
> disciplina de "poucas dezenas de linhas" do §10.

## Estado atual

- Etapa ativa (plano §7): **13 (Langfuse + DeepEval)** — concordância
  juiz × humano medida (0,867, `resultados/concordancia_juiz_humano_2026-08-23.md`);
  groundedness da rodada vigente ainda não auditada.
- Última etapa concluída: **10 (modelo preditivo)**, 2026-08-23 —
  `resultados/modelo_preditivo_2026-08-23.md`, custo zero. Antes dela, a 4
  (chunking de tabela, AGENTS.md §3.4).
- Suíte: **1.736** casos, sem skip (exige `requirements-modelo.txt`).
- Rodada congelada vigente: fingerprint `5b9b142d`
  (`20260823T131515Z-4ad67021f6`), números publicados no README. Status:
  `auditoria_manual_pendente`.
- Gasto acumulado nos logs versionados: **USD 2,87** de um teto de 25 (RNF03).

## Decisões e bloqueios em aberto

- **McNemar da camada de agentes (etapa 12) bloqueado por leitura humana, não
  por código.** Braço C já reapurado (2026-08-21, 0/15 mudou). Faltam 10 dos
  15 gabaritos de `conjunto_padrao/conjunto_agentes.csv` com dupla leitura
  independente — tarefa do Ygor, página-fonte em `fonte_gabarito`.
- **Pedido de afrouxar os qualificadores de métrica no corretor de exatidão
  foi recusado com evidência**, não esquecido: no Itaú 1T2026 coexistem
  `11.636` ("atribuível a controladores") e `11.875` ("controladores e não
  controladores") — sem exigir o qualificador o corretor aceitaria a linha
  errada. Caminho certo, não feito: coluna nova no gabarito com as redações
  aceitas por pergunta (regra "acrescente coluna, nunca linha") — decisão do
  Ygor.
- **Exatidão comparativa 0,000 é TETO ESTRUTURAL, não regressão** (apurado
  2026-08-23, custo zero — `resultados/teto_comparativas_2026-08-23.md`). O
  top-5 é global e 5 das 10 comparativas pedem 5 bancos → 1 chunk por banco.
  Teto real (todos os valores presentes): E1 1/10 · E2 2/10 · E3 2/10 ·
  E4 5/10. Recuperação de banco está 40/40 correta. **Corrigi o README, que eu
  próprio havia escrito chamando isso de regressão.** Resolver exige orçamento
  por banco, o que muda o orçamento de contexto e por §3.1-bis **não pode**
  entrar em E0–E4 — teria de ser medição declarada em separado. Não feito.
- **Painel de treino é SEPARADO do consultável** (AGENTS.md §3.5):
  `artefatos/cvm_treino.duckdb` cobre 2011–2026 e serve só ao modelo offline;
  `artefatos/cvm.duckdb` segue casado com o corpus para tudo que responde ao
  usuário. Ambos fora do Git, regeneráveis por
  `scripts/construir_painel_cvm.py`.
- **Modelo preditivo: boosting AUC 0,866 × 0,752 da persistência, vencendo em
  47/47 folds.** Boosting × logística, porém, é MARGINAL: +0,0033 com IC 95%
  [-0,0002; +0,0069] — corrigi um +0,0065/p=2e-04 que eu havia publicado antes
  de remover as features do O-score. O ganho veio das features SAZONAIS (+0,0102, p=7,0e-09), que
  só existem com janela longa — não do modelo nem da literatura de insolvência.
- **RESULTADO NEGATIVO a não repetir: as features do O-score de Ohlson não
  ajudam aqui.** Acrescentei-as por argumento de literatura; na janela curta
  pareciam somar +0,010 mas o IC incluía zero. Com 47 folds: nulo no boosting
  (p=0,135) e **piora** na logística (−0,0027, p=3e-04), inclusive testadas como
  substituição. Removidas. Motivo em `OSCORE_REMOVIDAS_POR_MEDICAO`.
- **ALVO DE 2 TRIMESTRES CONSECUTIVOS é melhor em tudo** (ideia do Ygor,
  medida em 2026-08-23): AUC **0,8797** (com purga; 0,881 sem, ver abaixo),
  lift@10% **3,36** (era 2,55), Brier 0,115,
  e o ponto de operação sinaliza **41,5%** da base contra 57,6%. Custo: 50,8%
  dos rótulos passam a tocar o 4T derivado (era 24,8%) — testado, se sustenta.
  `construir_painel(trimestres_consecutivos=2)`.
- **SMOTE MEDIDO E REJEITADO com dado próprio** (antes era só argumento de
  literatura): −0,0060 de AUC (p=5,4e-08, vence 7/47) e **dobra o erro de
  calibração**. Controle `boosting_imputado` existe porque SMOTE exige
  imputação — comparar com o boosting puro mediria duas mudanças.
- **Ajuste de hiperparâmetros rende ZERO.** A busca "ganhava" +0,003 nos folds
  em que escolheu; nos 27 folds não vistos a diferença é −0,0000 (p=0,77). Era
  ruído de seleção. Não adotar continua certo, agora por medição.
- **Rótulo derivado NÃO é a fragilidade que eu apontei:** restringindo a
  rótulos arquivados o AUC é igual ou melhor (0,872 × 0,866). Fechado.
- **Também não se confirmou:** eu suspeitava que a persistência de defasagem 1
  fosse baseline fraco para lucro trimestral e que o passeio sazonal
  (defasagem 4) fosse mais duro. Medido, o sazonal é marginalmente PIOR
  (0,739 × 0,752) — a comparação antiga estava adequada.
- **RN07 VIROU CONDICIONAL AO MODO** (2026-08-24, AGENTS.md §3.6). Público
  recusa e entrega agregados; `PREVISAO_POR_EMISSOR_HABILITADA=1` (local)
  acrescenta o escore etiquetado. Motivo: a mordida da Res. CVM 20/2021 é na
  DIVULGAÇÃO, não no uso interno de analista credenciado. Três travas em
  código: o caminho interativo nunca importa `src.modelo` (lê artefato
  offline); `escores_por_companhia.json` está no `.gitignore`; e o agregado
  extremo é suprimido para não vazar por eliminação. 0/55 falso bloqueio.
- **DEBATE DE DOIS ESPECIALISTAS (2026-08-25) derrubou 3 coisas publicadas** —
  detalhe completo em `resultados/debate_modelo_2026-08-25.md`. Uma retratação
  de cada lado, inclusive minha. O que muda a execução daqui pra frente:
  - **NÃO publicar "+0,11 sobre a persistência".** Ela é BINÁRIA e o AUC pune
    empate. Baselines honestos já estão no código (`escore_taxa_recente`,
    `escore_identidade_implementavel`): ganho real **+0,019** e **+0,073**.
  - **O modelo ordena QUAIS companhias, não QUANDO viram.** Intra-companhia
    0,663 × 0,865 agregado; 97,1% do decil superior já está em prejuízo.
    `auc_within_companhia` e `composicao_do_topo` são OBRIGATÓRIAS ao lado de
    qualquer lift — sem elas o número é lido como capacidade que não existe.
  - **`is_banco` não significa banco** (é "usa plano de contas de IF"). Recorte
    setorial removido da rota. Se voltar a precisar, casar por CNPJ com a lista
    do BACEN — `cnpj` está preenchido em 741/741.
  - **Para banco, nenhum rótulo contábil da CVM serve**: líquido omite,
    pré-tributos exagera (24,5% resgatados pela linha fiscal × 6,2% nas não
    financeiras). O recorrente gerencial não está no arquivo — é a TESE do
    projeto, não uma falha dele.
- **ONDE O MODELO DE FATO SERVE — medido em 2026-08-25, e faltava.** As duas
  medidas de decomposição acima dizem o que o modelo NÃO faz, e publicá-las
  sozinhas leva à conclusão (errada) de que o módulo não tem função — foi
  exatamente a conclusão que o Ygor tirou ao ler o resumo, e ele estava certo
  em tirá-la do que estava escrito. `taxa_prejuizos_4t` tem denominador 4:
  **7 valores possíveis**, e o maior bloco de empate (sem prejuízo em 4
  trimestres) é **46% do painel**, onde ela é CONSTANTE — **AUC 0,500 por
  construção, não por estar pior**. O modelo mede **0,757** ali (alvo 2T;
  0,723 no 1T), lift **3,92×**. É isso que dilui o +0,019: nos 54% em que o
  baseline discrimina o modelo empata, nos 46% em que ele é cego o modelo é a
  única coisa que ordena. **Ressalva que anda junto:** o bloco cego é o dos
  saudáveis, concentra só **5,6% dos eventos** — filtro onde não havia filtro,
  não máquina de achar prejuízo. `desempenho_no_bloco_cego`, dentro de
  `decomposicao`.
- **Duas armadilhas de código que voltam se alguém mexer**: a validação precisa
  ficar em `ordem_teste − 1 − n_alvo` (o rótulo dela alcançava o teste, mesmo
  com alvo de 1 trimestre), e `early_stopping` precisa ficar `False` explícito
  (o `'auto'` liga com n>10.000 e ajusta o nº de árvores por fold).
- **A AUDITORIA PEGOU 4 DEFEITOS REAIS na rota nova** (2026-08-24, todos
  corrigidos com teste — `resultados/robustez_modelo_2026-08-24.md` §7):
  `KeyError` que derrubava o app e impedia a recusa de chegar à tela;
  trimestre ordenado como TEXTO (janela publicada errada); prejuízo derivado
  somado como arquivado (RN10); e "41 de 413 no decil superior" publicado como
  achado quando é 10% por definição. **Lição: rodar o auditor ANTES de
  considerar a onda pronta, não depois de escrever o relatório.**
- **`ordinal_trimestre` MUDOU DE CASA**: de `src/modelo/construir_painel.py`
  para `src/normalizacao.py`. Motivo é a RN07 — o caminho interativo precisa
  ordenar trimestre e não pode importar `src.modelo`. `construir_painel`
  reexporta; não duplique a regra.
- **RN07 virou GUARDA PROFUNDA** (2026-08-25, era a pendência anterior).
  Artefato ausente agora **recusa** (`recusa_de_ultimo_recurso`, sem número
  nenhum — trocar RN07 por RN02 não seria conserto) em vez de cair no LLM, e
  `responder_pergunta_livre` repete a verificação antes de recuperar e antes
  de estimar custo (portão duplo, como já se faz com a RN05).
  `TestGuardaProfunda` trava inclusive a ORDEM: recusar depois de gastar não
  é recusar.
- **O produto ESCORA O PRESENTE** (2026-08-25).
  `construir_painel_para_inferencia` usa `LEFT JOIN` no alvo e devolve o
  último trimestre fechado: referência foi de `3T2025` para **`1T2026`**.
  Restrita a `prejuizo_em_t=0` por medição, não por gosto — 97,1% do decil
  superior já está em prejuízo. **286 hoje lucrativas, 25 acima do limiar, 136
  já em prejuízo publicadas ao lado** para a queda de volume não passar por
  melhora. Duas travas: `PainelDeInferencia` é tipo PRÓPRIO (passar um pelo
  outro treinaria sobre rótulo inexistente) e `rotulo` vem `pd.NA`, porque o
  `ELSE 0` do `CASE` daria "lucro" a quem só não tem futuro ainda.
- **Viés as-restated é MENSURÁVEL com o painel carregado** — eu havia escrito
  que exigiria reler os ZIPs por versão, e estava errado: `versao_documento`
  sobrevive em `fatos_contabeis`. `medir_republicacao`: 16,36% das obs, e a
  assimetria entre classes é **0,66 ponto** (16,81% em prejuízo × 16,14% em
  lucro) — não contamina o rótulo.
- **Rota prospectiva precisa do artefato para funcionar**: gerar com
  `python -m scripts.gerar_panorama_modelo --painel artefatos/cvm_treino.duckdb
  --com-escores`. Sem `panorama.json` a rota se desliga e loga; com a chave
  local ligada e sem os escores, falha fechada de propósito.
- **Quatro apontamentos de revisor medidos em 2026-08-24**
  (`resultados/robustez_modelo_2026-08-24.md`): purga/embargo faltava e foi
  acrescentada (AUC 0,881 → **0,8797**, p=0,026; alvo de 1 trimestre fica
  IDÊNTICO, que é a contraprova); **controle setorial REJEITADO** (+0,0005,
  p=0,19 — `alavancagem` já era proxy); **recalibração não ajuda** e a
  isotônica piora a ordenação (−0,0062, p=1e-13) porque o calibrador vê um
  trimestre só; **LightGBM empata** (p=0,66). E a decisão sobre as features
  sazonais **sobrevive em folds não vistos** (+0,0072, p=4e-06) — ao contrário
  dos hiperparâmetros, que eram ruído.
- **NÃO usar o "AUC 0,883 / lift 5,10 em instituição financeira"** que ficou
  escrito aqui até 2026-08-25: é o MESMO recorte `is_banco` contaminado que o
  debate derrubou (29 dos 35 eventos vinham de private equity, holding e uma
  companhia em liquidação). Limpo o universo sobram ~6 eventos — insuficientes
  para distinguir qualquer AUC de 0,50 (Hanley & McNeil). O recorte que se
  sustenta é o de **hoje-lucrativas**, que não depende de setor.
- **E4 (`fatos`) não é persistido em disco, por decisão**: construir sob
  demanda (~35 s) evita a classe de defeito "índice novo, fatos velhos".
- Gate G1 (Azure) resolvido para o pré-deploy — sem ação pendente até lá.

- **A AUDITORIA DA ONDA DE 2026-08-25 PEGOU 7 DEFEITOS** — a lição da rodada
  anterior ("rodar o auditor antes de considerar pronto") se repetiu, e um dos
  achados foi eu ter reescrito esta memória como se tivesse fechado os dois
  portões da RN07 tendo fechado um. O que ficou travado por teste:
  - `responder_com_guardrails` também verifica a RN07 agora (era o único
    portão do produto sem ela, e se declara "o caminho interativo inteiro").
  - A guarda anti-eliminação do trimestre corrente é sobre **fração**
    (`BANDA_PUBLICAVEL`, 5%–95%), não sobre contagem: barrar só 0 e "todas"
    deixava passar 2 de 286, que entrega a mesma dedução.
- **DEFEITO DE CÁLCULO ACHADO DEPOIS DA AUDITORIA, conferindo a própria onda:**
  o limiar do bloco do trimestre corrente era herdado do panorama — "2× a
  taxa-base do PAINEL INTEIRO" (22,3%) — mas aplicado só às **hoje lucrativas**,
  cuja base é 8,1%. Virava **5,5×** na prática. Efeito: **2 de 286 em vez de 25**,
  fator 12. Corrigido: o limiar sai da população que ele filtra, e
  `taxa_base_do_recorte` é publicada ao lado dele — foi a ausência dela que
  escondeu o erro. **Lição que vale mais que o conserto: número de corte sem a
  base ao lado é incomparável, e "2× a taxa-base" não diz nada sem dizer de
  QUAL base.**
  - Um teste meu se chamava `test_falha_fechada_*`, dizia cobrir a falha e não
    tinha `pytest.raises`. Guarda extraída para `exigir_trimestre_sem_rotulo`
    para poder ser exercitada de verdade.
  - A interface sobrescrevia `modo`/`provedor` à mão e debitava cota da RN03
    numa recusa de custo zero.
- **Retratação sem artefato é dívida, não conserto**: os números que derrubaram
  o recorte `is_banco` viviam só em prosa enquanto o número retratado tinha
  artefato versionado. Agora há `scripts/auditar_recorte_is_banco.py` →
  `artefatos/modelo/auditoria_is_banco.json`. Os valores corretos são **42/49
  (85,7%)** e **ρ = −0,046 (p = 0,83)** — a prosa do debate dizia 29/35 e
  −0,014, de contagem ad hoc num painel diferente. Conclusão idêntica, base
  agora conferível.
- **C1 — QUEDA DE ROA NORMALIZADA PELA VOLATILIDADE REJEITADO (2026-08-26)** —
  a aprovação exploratória de `resultados/debate_alvo_ml_2026-08-26.md` foi
  retratada após validação cega com dois especialistas e replicação
  independente: `resultados/validacao_c1_2026-08-26.md`.
  - **PROTOCOLO DOS DOIS TESTES continua valendo para todo alvo futuro**
    (AGENTS §3.7), com uma correção: **T1** deve testar cada componente que
    define mecanicamente o rótulo, inclusive o normalizador; **T2** mede a
    lacuna agregada−intra. Passar em um não compensa falhar no outro.
  - O próprio `sd8` fabrica o baseline: amplitude T1 **0,180** na especificação
    primária, **0,181/0,183** nas sensibilidades e **0,247** na implementação
    isolada do agente, sempre acima de 0,15.
  - Na replicação principal, `-sd8` sozinho obtém AUC **0,634** agregada e
    **0,709** intra-companhia; precisão top-20 **0,346**. T2 favorável não
    resgata T1 reprovado.
  - Artefato: `artefatos/modelo/auditoria_alvo_c1.json`; reprodução:
    `scripts/auditar_alvo_c1.py`; contrato:
    `tests/test_auditar_alvo_c1.py`.
  - O painel ainda não dá procedência point-in-time completa, mas isso é
    bloqueio adicional, **não** a causa da rejeição.
  - C1 só reabre por erro computacional ou divergência com a fórmula registrada.
    Piso de materialidade, outro normalizador ou horizonte é **C2**, que não
    herda números nem aprovação do C1.
  - **`cad_cia_aberta.csv` derruba 3 bloqueios que os três davam como
    intransponíveis**: `SETOR_ATIV` 710/731 (controle setorial deixa de ser
    impossível), `CATEG_REG` (135 são Cat. B e não podem ter ação),
    `SIT_EMISSOR`+`DT_INI_SIT_EMISSOR` (51 em RJ, com data — resolve o
    look-ahead). Melhoria do painel independente do modelo.
  - **Mortos com medição, não repetir:** accrual como alvo (inverte sob controle
    de ROA), republicação como preditor (0,0007), reapresentação como alvo
    (censura à direita: 28,1%→4,3%; `dt_refer=dt_fim_exerc` em 100%), alvo
    setorial e efeitos fixos (reprovam T1).
- **CAND-02 — REDLINE SEMÂNTICO: NÃO IMPLEMENTAR ML AGORA (2026-08-27)** —
  dois especialistas isolados e duas rodadas mediadas fecharam por unanimidade:
  rejeitar a implementação aprendida agora e rejeitar a alegação de que o
  determinístico já provou utilidade. `resultados/validacao_cand02_redline_2026-08-27.md`.
  - Gate real: 20 documentos → 15 pares, mas só **5 clusters** no teste purgado;
    zero PDF cruza desenvolvimento/teste; estrutura aprovada.
  - Ausentes: dupla leitura completa dos 15 pares, adjudicação/gold e estudo
    humano de tempo. Estado **INDECIDÍVEL**; nenhum modelo foi carregado.
  - Pré-registro: `resultados/pre_registro_cand02_redline_2026-08-27.md`.
    Auditor/artefato: `scripts/auditar_cand02_redline.py` →
    `artefatos/cand02/auditoria_precondicoes.json`.
  - Reabre com ≥30 mudanças P2 adjudicadas e estudo de tempo; primeiro provar
    B1 (zero FN crítico, recall P2 ≥0,90, nDCG@20 ≥0,80), depois comparar ML.
- **CAND-03 — TRIAGEM DE ANOMALIAS: NÃO IMPLEMENTAR ML AGORA (2026-08-27)** —
  dois especialistas isolados, réplica e tréplica mediadas fecharam por
  unanimidade: E2 (prioridade de leitura) é o alvo correto; erro/reapresentação
  e fraude/deterioração são tarefas separadas. Estado **INDECIDÍVEL** e
  baseline determinístico **não validado**.
  - Painel: 5.552.787 linhas → 23.346 companhia–trimestres; mapa exato
    274.935/5.552.787 (4,951%), 11 conceitos; setor 5/741; 698 duplicidades
    semânticas, 587 conflitantes; BPA/BPP/DRE, sem DFC e sem `DT_RECEB`.
  - Gold conhecido: quatro células, um emissor e **um episódio-raiz** (o
    auditor publica limite superior de dois companhia–trimestres porque a
    tabela ainda não tem `cause_id`). Denominador não é rótulo.
  - Os 31 ZIPs locais já têm DFC e `DT_RECEB`. Metadados: 48.129
    documento–versões, 41.062 arquivamentos, 5.803 reapresentados (14,13%);
    o painel preserva **zero** grupos com múltiplas versões numéricas.
  - Pré-registro:
    `resultados/pre_registro_cand03_anomalias_contabeis_2026-08-27.md`.
    Relatório: `resultados/validacao_cand03_anomalias_contabeis_2026-08-27.md`.
    Auditor/artefato: `scripts/auditar_cand03_anomalias.py` →
    `artefatos/cand03/auditoria_precondicoes.json`.
  - Reabre o **experimento**, não o deploy, com shadow prospectivo: 30 releases,
    seguir até ≥30 releases P1/P2 e rubrica estável, teto 150. Confirmatório
    `N=max(100,N_poder,N_50+)`; primária é tempo/itens sob recall congelado,
    nDCG@20 corroborativa; ganho precisa superar
    `max(break-even+margem,20%)` com procedência perfeita.
- **CAND-04 — PREVISÃO DE FUNDAMENTOS: RODADA A REJEITADA/INVALIDADA
  (2026-08-27)** — dois especialistas cegos, réplica mediada e tréplica
  validaram por unanimidade: a rodada A acabou; a fórmula econômica prospective
  ROA não foi refutada; ML está **INDECIDÍVEL** e **NÃO IMPLEMENTAR AGORA**.
  - Pré-registro: `resultados/pre_registro_cand04_previsao_fundamentos_2026-08-27.md`.
    Relatório: `resultados/validacao_cand04_previsao_fundamentos_2026-08-27.md`.
    Auditor/artefato: `scripts/auditar_cand04_previsao_fundamentos.py` →
    `artefatos/cand04/auditoria_baselines.json`; 6 testes focados.
  - Teste as-restated: 3.218 releases, 435 companhias, oito targets. B3 mede
    MAE macro 950,94 bp × mediana AE 57,80; top 1% = 83,55% do erro.
  - 23 linhas (0,71%, oito companhias) com saltos de ativo próximos de 1.000×
    explicam 61,64% do erro; 20 targets `|y|>10.000 bp` explicam 71,28%; 4T
    derivado MAE 2.602,46 × 449,94 no arquivado. G0 integridade e G1 PIT falham.
  - **Não remover as 23 pós-hoc.** Adjudicar escala/perímetro contra fonte e
    congelar regra antes de novo teste; a sensibilidade MAE 459,52 é somente
    diagnóstico e não pode virar baseline oficial.
  - Divergência preservada: Ciência de Dados prioriza A2 corrigido; Finanças
    prioriza B (lucro dos controladores em R$ + materialidade em bps do PL).
    Ambos são estimandos novos e não herdam números de A.
- **RANK 5 — DIVERGÊNCIA GERENCIAL × CONTÁBIL: INDECIDÍVEL; ML FECHADO
  (2026-08-27)** — dois especialistas isolados, réplica medida e tréplica
  convergiram: **não implementar ML agora**; autorizar apenas K1 determinístico
  + construção do gold.
  - Auditoria: 20 releases, cinco bancos, 2.790 páginas. LAJIDA/LAJIR/EBITDA/
    EBIT como palavra inteira = **0/20**. Ponte explícita contábil↔gerencial =
    **12/20**, três emissores, 16 páginas. Ponte geral de resultado ajustado =
    **20/20**, cinco emissores, 31 páginas.
  - G0-L reprova; G0-K passa. G1 PIT, G2 gold, G3 baseline e G4 amostra
    reprovam. O corpus tem URL/hash/data de coleta, mas não data original e
    versão; 20/5 fica abaixo de 30 releases/10 emissores e positivos são
    desconhecidos. Nenhum modelo foi carregado.
  - K1 separado: `lucro líquido contábil + ajustes = lucro líquido ajustado/
    recorrente`; rótulo do emissor não vira verdade econômica.
  - Ranking normativo: `resultados/ranking_candidatos_ml_value_investing.md`.
    Pré-registro: `resultados/pre_registro_rank05_divergencia_gerencial_contabil_2026-08-27.md`.
    Relatório: `resultados/validacao_rank05_divergencia_gerencial_contabil_2026-08-27.md`.
    Auditor/artefato: `scripts/auditar_rank05_divergencia_gerencial_contabil.py`
    → `artefatos/rank05/auditoria_precondicoes.json`; 7 testes focados; suíte
    ampliada **1.725 passed, zero skips**.
  - Reprodutibilidade: resolução limpa com `requirements-guardrails.txt` falha
    por `numpy==2.5.1` × `presidio-analyzer` (`numpy<2.5.0`). Não alterar pins
    como efeito lateral desta validação; tratar em onda própria.
- **Alvo pré-tributos: RECOMENDADO pelos dois especialistas e DESCARTADO por
  Ygor (2026-08-25).** Ganho estatístico é ruído (+0,0034) e a troca
  invalidaria os três relatórios publicados. Registrado como caminho conhecido,
  não como pendência — não reabrir sem pedido.

- **`resultados/becos_sem_saida.md` (2026-08-26) — consultar ANTES de propor
  ideia nova.** Registro consolidado do que já foi medido e descartado, que
  antes estava espalhado por sete relatórios: alvos que reprovam T1/T2, SMOTE,
  ajuste de hiperparâmetros, recalibração isotônica/Platt, LightGBM, controle
  setorial, accrual, fusão E3+E4, o primeiro conserto do chunker, os provedores
  de LLM descartados, e as quatro hipóteses retratadas (interruptor do porte,
  volatilidade, duas camadas, assimetria direcional). Cada linha traz **o que
  reabriria** — o registro é condicional, não dogma. Ao remedir, **atualize a
  linha**; o histórico é o Git. Em divergência, o relatório datado de origem
  vence.

- **Busca por modelo de ML útil ao Value Investing: NEGATIVO medido (2026-08-26,
  §3.8).** Quatro rodadas, briefing mínimo, os dois especialistas **retiraram as
  próprias propostas**. Seis candidatos, cada um vencido pelo **seu próprio
  baseline trivial** — detalhe em `becos_sem_saida.md` §E. A frase publicável é
  "nenhuma proposta sustentou componente aprendido superior ao seu baseline",
  **não** "nada de útil saiu". Restrição estrutural medida quatro vezes: o lado
  com `n` não tem conteúdo bancário (Basileia/margem financeira = **0 linhas**);
  o lado com conteúdo bancário tem **20 documentos**. O painel **não tem DFC**.
  Duas regras novas: **"denominador não é rótulo"** (pegou os dois: 840× e 190×)
  e **"construa o baseline trivial antes do modelo"** (venceu 205×1). Entrega
  real que saiu disso e **não é modelo**: a tabela de **208 contas** do plano
  padrão da CVM destrava **85% das 5,55 M de linhas** (hoje: 4,95%) — ~7 h de
  anotação, com o G4 por conceito como trabalho de verdade.

- **DFC e point-in-time CARREGADOS (2026-08-27, §3.13).** O loader lia 3
  demonstrativos e ignorava o resto do ZIP; agora lê 5 e tem tabela
  `documentos` com `DT_RECEB`. Custo zero — os ZIPs já estavam em disco.
  Painel: 5.552.787 → **6.787.589** linhas; **48.123** documentos;
  **FCO existe para as 741 companhias**. Atraso mediano de publicação: 44 dias
  (ITR) e 83 (DFP); **41% dos documentos chegam depois de 45 dias** — usar
  `dt_refer` como data de publicação era ver o formulário antes de existir.
  **Hash do painel de treino mudou** (`74aa28e8…` → `476a11da…`); o anterior
  conferiu antes da troca, e o C1 exige tratar reexecução como nova medição.
  A rejeição do C1 **não muda**. `artefatos/cvm.duckdb` não foi tocado (§3.5).
  **Destrava o Rank 3 de intestável para decidível** — não garante que passe.

- **Rank 3 REJEITADO em T1 (2026-08-27, §3.14).** Primeiro candidato testado com
  o painel de fluxo de caixa. `accrual` amplitude **0,266** e `conversao`
  **0,229** contra limiar 0,15 — quem tem accrual BAIXO hoje tem 3,5× mais
  chance de ser marcado. **O pré-registro previu isso antes de medir.**
  **Regra durável, 3ª medição do mesmo padrão:** alvo definido como *variação*
  de grandeza que reverte à média fabrica o *nível* dela como baseline; se o
  alvo é "X piora", o nível de X vai a T1 obrigatoriamente. Escapa só evento
  materialmente definido (falência, evento legal), não movimento de série.
  **Dois achados laterais:** a CVM não publica DFC isolada no 2T/3T (só
  acumulada) — derivado agora, +390.187 fatos, painel a **7.177.705** linhas; e
  o auditor **falhava em aberto** (`NaN >= 0,15` é False → "aprovado" sobre
  amostra vazia), corrigido com mínimo e exceção. Hash do painel:
  `c1a60445…`.

- **TRÊS CORPORA, NÃO UM — e a separação é contrato, não organização
  (2026-09-08).** Os 7 emissores novos entraram primeiro em
  `corpus/metadados.csv` e no cache `corpus/ocr/`, e isso **quebrou três
  contratos congelados de uma vez**. Os testes pegaram; o conserto foi separar,
  não afrouxar asserção.
  | Corpus | Manifesto | Cache de OCR | Docs |
  |---|---|---|---:|
  | **principal** (produto) | `corpus/metadados.csv` | `corpus/ocr/` | 20 |
  | **expansao** (teste) | `corpus/expansao/manifesto_expansao.csv` | `corpus/expansao/ocr/` | 24 |
  | **ifrs** (evidência G4 + leitura completa) | `corpus/ifrs/manifesto_ifrs.csv` | `corpus/ifrs/ocr_documento/` | 15 |
  O que quebrou e voltou: `hash_cache_ocr` da RNF09 saiu de `83463136…` para
  `52edfba4…` (índice publicável deixou de conferir) — **restaurado**;
  `empresas(manifesto) == Config.bancos` de `_validar_manifesto`; e a auditoria
  congelada do Rank 5 (20 documentos). **O `.gitignore` já dizia essa regra para
  o IFRS** — *"nunca entram em corpus/metadados.csv: isso mudaria a identidade
  do índice (RNF09)"* — e ela agora está escrita também para a expansão.
  **ATENÇÃO: o commit `f994421` contém as 24 linhas no `corpus/metadados.csv`.**
  A árvore de trabalho já restaurou o manifesto congelado de 20; o commit é que
  precisa ser corrigido.
  `scripts/ocr_batch_mistral.py --corpus principal|expansao|ifrs`.
- **OCR do corpus IFRS CONCLUÍDO (2026-09-08).** 15 documentos, **1.255/1.255
  páginas, zero vazias**, job `67d038aa…`, custo estimado **USD 2,51**. Cache em
  `corpus/ifrs/ocr_documento/` — **separado de `corpus/ifrs/ocr/` de
  propósito**: aquele é endereçado pelo mesmo hash de PDF mas guarda um RECORTE
  de 8 páginas em schema próprio, e `scripts/ancora_ifrs.py` o lê como evidência
  do G4 aprovado; gravar em cima sobrescreveria prova de gate com outro formato.
  Conferido intacto. **Validação independente:** o BTG 4T2025 tinha 63 de 71
  páginas com fonte ilegível ao `pdfplumber`, e o OCR devolveu na pág. 13
  exatamente `16.663.803 / 16.005.964 / 657.839` — os três valores da âncora que
  custou USD 0,30 (`resultados/ancora_btg_4T2025.md`).
- **Guarda nova: "arquivo existe" ≠ "documento processado".**
  `separar_pendentes` confere a contagem de páginas do cache contra o PDF e
  reporta cache incompleto como pendente. Veio de armadilha real: o cache de
  âncora do BTG 4T2025 tem **8 de 71 páginas**, e a lógica antiga teria pulado o
  documento inteiro deixando 63 páginas fora sem sinal nenhum. Schema não
  reconhecido é tratado como **"não sei"**, nunca como incompleto — senão uma
  mudança de formato viraria reprocessamento pago do corpus inteiro sem ninguém
  pedir.
- **Bug de teste que poluiu o cache REAL, achado e corrigido.** Um teste meu
  atribuía `modulo.DIR_CACHE_OCR = tmp_path`, mas o default do parâmetro é
  vinculado na **definição** da função — a atribuição não o alcança e a gravação
  caiu em `corpus/ocr/ha.json`, mudando o `hash_cache_ocr` que a RNF09 usa.
  Removido; `dir_cache` agora vai explícito e há contraprova
  (`test_nao_escreve_fora_do_dir_cache_recebido`) que falha se voltar a escrever
  no cache do projeto.
- **Corpus enriquecido com 7 emissores novos (2026-08-27) — OCR CONCLUÍDO.**
  BMG, ABC Brasil, Banestes, Pine, Mercantil do Brasil, Banco do Nordeste,
  Banrisul: 24 documentos, 1.874 páginas, registrados em `corpus/metadados.csv`
  (hash conferido, fonte CVM RAD via catálogo IPE aberto), **44/44 no cache
  `corpus/ocr/`** (20 originais + 24 novos). Motivo: destravar o
  `≥10 emissores` que Rank 5, CAND-02 e CAND-03 exigem para sair de
  INDECIDÍVEL — material de teste, **não** expansão do produto público agora.
  `HOSTS_PERMITIDOS` em `scripts/baixar_corpus.py` estendido para
  `www.rad.cvm.gov.br`.
  - Dois jobs Batch: `2b2cd99a…` (23/24 — Banrisul 2T2025 saiu ausente da
    saída, ver bug abaixo) + `dcc2b386…` (retentativa, só o que faltou,
    1/1 sucesso). Custo **estimado** somado: **USD 4,19** (3,75 + 0,45) —
    **acima** dos ~USD 3,95 que o Ygor tinha de saldo, porque o primeiro job
    já incluía a página do Banrisul que falhou e precisou ser resubmetida; o
    script só registra `custo_estimado_usd` por lote (nunca fatura real via
    API), então **não sei se a Mistral cobra por página tentada ou só por
    página que teve sucesso** — se for a primeira, o Banrisul 2T2025 foi
    cobrado duas vezes. **Conferir a fatura real da Mistral na próxima sessão**
    antes de gastar mais este mês.
  - Completar o que falta abaixo antes de considerar os 7 bancos utilizáveis:
  - `src/normalizacao.py::APELIDOS_BANCOS` só tem os 5 originais + NUBANK —
    sem entrada aqui, pergunta sobre um banco novo não é reconhecida.
  - Índice vetorial não reconstruído com os novos chunks.
  - Âncoras-sentinela ausentes em `corpus/ancoras_sentinela.csv` — manual,
    tarefa do Ygor (página-fonte por documento).
  - `mapa_contas.py`/`dados_estruturados.py` resolvem setor/ticker por
    dicionário fixo dos 5 bancos (§3.7); os 7 novos caem em `None`.
  - Descoberto no reconhecimento: Mercantil e Banco do Nordeste publicam só
    **semestralmente** (2T/4T, sem 1T/3T isolado); Banco Pan teve o registro
    CVM **cancelado em 2026-03-30** (fechou capital) — por isso ficou de fora
    deste pacote.
- **Bug real achado e corrigido ao submeter o job acima**: o journal de OCR em
  lote (`journal_ocr_batch.json`) era um registro FLAT — um job antigo
  concluído (`0eb6eab2`, 2026-08-10, 20 documentos) fazia a passagem nova (24
  documentos diferentes) ler "já existe, retomando" e travar **sem criar job
  nem gastar nada** (seguro, mas também não processava). Corrigido com
  fingerprint por lote — `(nome, hash_esperado)` pendente vira a chave;
  mesmo lote retoma, lote diferente cria job novo. Job antigo preservado como
  histórico sob `legado-0eb6eab2…`. `scripts/ocr_batch_mistral.py::
  fingerprint_pendentes` + `_ler_journal` migram o formato antigo; 6 testes
  novos em `tests/test_ocr_batch_mistral.py`.
- **PENDÊNCIA EXPLÍCITA — represada para depois do início do próximo mês
  (crédito de OCR mensal, ~USD 4, já comprometido com o pacote acima em
  2026-08-27):** completar o OCR do corpus IFRS paralelo. `corpus/ifrs/` tem
  **15 documentos** (Demonstrações Financeiras Completas de BTG/BB/Santander,
  5 trimestres cada, 1.255 páginas), baixados em 2026-08-11 só para ancorar o
  gate G4 (`corpus/ifrs/manifesto_ifrs.csv`) — **nunca entraram em
  `corpus/metadados.csv`, nunca foram indexados**. Só 1 página (BTG 4T2025,
  pág. 13) foi OCR'd até hoje, num script pontual
  (`resultados/ancora_btg_4T2025.md`). Custo estimado em lote: **USD 2,51**
  (1.255 pg × USD 0,002/pg). Investigação de "por que refazer OCR" nas versões
  antigas do `MEMORY.md` (commit `83d7cad`) achou outra pista — contradição
  entre `extrator=mistral_ocr` nos metadados do índice e o `AGENTS.md` — mas
  essa já foi apurada e fechada em 2026-08-17 (índice reconstruído sobre o
  OCR real); não é a mesma pendência.

## Próximo passo concreto

1. Rank 5 não autoriza modelo. Se priorizado, primeiro inventariar/adjudicar as
   31 páginas K1, recuperar data original/versão, implementar o extrator e B0–B3
   determinísticos e iniciar gold de 30–150 releases até ≥30 P2/P3.
2. CAND-04 não autoriza modelo. Se priorizada, primeiro reconstruir vintages
   (`DT_RECEB`/`ID_DOC`), adjudicar as 23 linhas e a derivação 4T, completar
   setor e então escolher/pre-registrar A2 ou B com teste novo.
3. Se a linha CAND-03 for priorizada, o próximo passo não é modelo: construir
   snapshots imutáveis point-in-time, ingerir DFC/`DT_RECEB`, resolver as 698
   duplicidades e instrumentar o piloto shadow de 30–150 releases. Não chamar
   o baseline-candidato de útil antes da dupla leitura e do estudo de tempo.
4. Se CAND-02 voltar à prioridade, organizar dupla leitura completa dos 15
   pares, adjudicação e estudo contrabalanceado conforme o pré-registro.
5. Rodar `python -m scripts.preparar_auditoria_final` sobre o fingerprint
   `5b9b142d` (arquivar `auditoria_groundedness.json`/`plano_estabilidade.json`
   de fingerprint antigo antes, se ainda estiverem no lugar) e repetir a
   leitura humana das 15 perguntas.
6. Depois da leitura: `scripts/executar_estabilidade.py --permitir-api-paga`
   (30 chamadas) e `scripts/consolidar_auditoria_final.py` — promoção a
   `completa` exige groundedness ≥ 0,90.
7. Em paralelo, sem depender do passo 5: dupla leitura dos 10 gabaritos
   pendentes de `conjunto_agentes.csv` — destrava o McNemar da etapa 12.
