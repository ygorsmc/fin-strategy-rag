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
- Suíte: **1.689** casos, sem skip (exige `requirements-modelo.txt`).
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
  superior já está em prejuízo. **286 hoje lucrativas, 2 acima do limiar, 136
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
    deixava passar 2 de 286, que entrega a mesma dedução. **Com o painel atual
    o bloco fica suprimido** — guarda que nunca dispara é decorativa.
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
- **Alvo pré-tributos: RECOMENDADO pelos dois especialistas e DESCARTADO por
  Ygor (2026-08-25).** Ganho estatístico é ruído (+0,0034) e a troca
  invalidaria os três relatórios publicados. Registrado como caminho conhecido,
  não como pendência — não reabrir sem pedido.

## Próximo passo concreto

1. Rodar `python -m scripts.preparar_auditoria_final` sobre o fingerprint
   `5b9b142d` (arquivar `auditoria_groundedness.json`/`plano_estabilidade.json`
   de fingerprint antigo antes, se ainda estiverem no lugar) e repetir a
   leitura humana das 15 perguntas.
2. Depois da leitura: `scripts/executar_estabilidade.py --permitir-api-paga`
   (30 chamadas) e `scripts/consolidar_auditoria_final.py` — promoção a
   `completa` exige groundedness ≥ 0,90.
3. Em paralelo, sem depender do passo 1: dupla leitura dos 10 gabaritos
   pendentes de `conjunto_agentes.csv` — destrava o McNemar da etapa 12.
