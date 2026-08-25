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
- Suíte: **1.640** casos, sem skip (exige `requirements-modelo.txt`).
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
- **RN07 PENDENTE de virar guarda profunda**: hoje a rota vive só no ramo do
  `app_streamlit.py` e devolve `None` (caindo no LLM) se faltar panorama,
  painel ou resolução de entidade. `responder_pergunta_livre` e
  `responder_com_guardrails` NÃO chamam o detector. É a correção seguinte.
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
- **Onde o modelo de fato serve** (medido, contraria o que eu disse antes):
  vai MELHOR em instituição financeira (AUC 0,883, lift 5,10) que na média do
  painel. O ponto cego são os 5 bancos do corpus, todos na faixa de ativo com
  0,6% de prejuízo. Recorte `≥ R$100 bi` tem 5 eventos e sai marcado
  INSUFICIENTE pela guarda `minimo_positivos` — não publicar AUC de 0,97 ali.
- **E4 (`fatos`) não é persistido em disco, por decisão**: construir sob
  demanda (~35 s) evita a classe de defeito "índice novo, fatos velhos".
- Gate G1 (Azure) resolvido para o pré-deploy — sem ação pendente até lá.

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
