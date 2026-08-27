# Pré-registro — CAND-02: redline semântico para prioridade de leitura

**Congelado em 2026-08-27, antes de calcular qualquer ranking ou abrir rótulo
do teste.**

## Emenda 1 — consenso pré-análise dos dois revisores

Registrada ainda sem ranking, pool ou rótulo calculado. Ela prevalece onde
for mais estrita que o texto abaixo:

- a unidade econômica é uma **afirmação atômica**; spans podem alinhar
  muitos-para-muitos, e tabela exige linha/métrica, cabeçalho, unidade, período
  e notas necessárias;
- o gold final exige leitura completa e livre dos 15 pares por dois analistas,
  seguida de adjudicação; pooling serve apenas ao piloto de ranking e não mede
  omissão documental;
- workflow: zero falso negativo crítico observado, recall de nota 2 ≥ 0,90,
  nDCG@20 ≥ 0,80 e 100% de procedência nos itens exibidos;
- challenger: zero falso negativo crítico adicional, nenhum nota 2 adicional
  perdido enquanto houver menos de 50 deles, ΔnDCG@10 ≥ +0,10,
  ΔnDCG@20 ≥ +0,05, ganho em 5/5 emissores e `N@R90` pelo menos 20% menor;
- o gate exige acordo positivo ≥ 75% e pelo menos **30 eventos nota 2**;
- sem dupla leitura completa ou estudo humano de tempo, a decisão binária é
  **NÃO IMPLEMENTAR AGORA o componente aprendido**. O estado científico
  permanece INDECIDÍVEL, não “modelo rejeitado”.

## Pergunta

Um componente semântico pré-treinado e congelado consegue priorizar mudanças
entre releases consecutivos que merecem leitura humana melhor que um redline
determinístico forte, sob o mesmo universo de candidatos e o mesmo orçamento?

Não se prevê retorno, recomendação, preço-alvo nem “fato relevante”. A saída é
uma fila auditável de **prioridade de leitura**. “Materialidade” jurídica ou
contábil não é rótulo deste experimento.

## Unidade e rótulo

A unidade é um `evento_de_mudanca` entre dois releases adjacentes do mesmo
emissor:

- um ou mais blocos contíguos no documento anterior;
- zero ou mais blocos correspondentes no documento atual;
- operação `adicao`, `remocao` ou `alteracao`;
- texto literal antes/depois, seção, página, empresa, trimestre e hash dos dois
  documentos;
- em tabela: rótulo da linha, cabeçalho, unidade e período.

Movimentação, quebra/fusão de bloco, layout, cabeçalho, rodapé e ruído de OCR
não são mudanças positivas. Casos sem comparabilidade segura recebem
`nao_julgavel_ocr_ou_estrutura`, nunca rótulo negativo.

Rótulo ordinal:

| Nota | Definição |
|---|---|
| 0 | rotina/superfície: layout, período automático, paráfrase equivalente ou mudança sem ação analítica |
| 1 | conferir: muda fato, número, definição, escopo, causa, risco, incerteza ou qualificador que merece inspeção |
| 2 | leitura obrigatória: muda guidance, KPI, tendência, sinal, ordem de grandeza, perímetro, política contábil, capital/liquidez, risco de crédito, reapresentação ou contradiz/qualifica afirmação anterior |

Cada positivo recebe código de motivo:
`numero`, `definicao_escopo`, `contabilidade`, `risco_incerteza`,
`explicacao_causal`, `guidance`, `capital_liquidez`, `credito`, `segmento` ou
`outro`. Nota 2 exige uma ação objetiva: `verificar`, `atualizar_modelo` ou
`investigar`.

## Baselines e challenger

### B0 — trivial

Redline por blocos depois de normalizar apenas whitespace, hifenização,
cabeçalho/rodapé e artefato de paginação. Números, sinais, percentuais,
moedas, negações e modais são preservados. Blocos idênticos saem; os demais
são alinhados por seção e ordem. Ranking pela massa de tokens alterados, com
desempate estável por página.

### B1 — determinístico forte

Mesmo universo e alinhamento. Ranking lexicográfico, sem peso aprendido:

1. alteração de número, sinal, percentual, moeda, negação ou modal;
2. guidance/meta, definição/perímetro, contabilidade/reapresentação,
   risco/regulação, capital/liquidez/payout ou crédito;
3. adição/remoção integral;
4. massa de tokens informativos e distância de edição.

Na comparação numérica, as regras de triagem congeladas são: 50 bp para
ratios gerais, 20 bp para crédito/custo de risco e 10% para valor ou volume
comparável. Não são limiares de materialidade legal.

### ML — challenger

Modelo semântico pré-treinado, local, congelado e identificado por revisão.
Ele recebe **exatamente os mesmos eventos** de B1. Nesta rodada não pode mudar
segmentação, alinhamento ou universo de candidatos: só reordena. Assim, eventual
ganho pode ser atribuído ao componente aprendido.

Nenhum treino ou ajuste por sentença é permitido: chunks do mesmo par não são
observações independentes. Prompt, âncoras semânticas, modelo e regra de score
devem ser persistidos antes dos rótulos do teste.

## Split sem PDF compartilhado

Pares adjacentes compartilham documentos. Portanto:

| Papel | Pares | Uso |
|---|---|---|
| desenvolvimento | 2T2025 → 3T2025, cinco emissores | calibrar rubrica e conferir implementação |
| embargo | 3T2025 → 4T2025, cinco emissores | não ajustar nem publicar |
| teste | 4T2025 → 1T2026, cinco emissores | único resultado comparativo |

Nenhum split por sentença, chunk, página ou evento é válido. Resultado usa
macro-média com peso igual por par. O teste tem **cinco clusters**, não centenas
de exemplos.

## Pool e anotação

Dois leitores independentes com repertório de research financeiro, cegos para
sistema, score e posição. A ordem dos eventos é aleatória. Um terceiro
adjudicador resolve divergências apenas depois das duas leituras.

- 40 eventos de desenvolvimento calibram a rubrica e não entram na métrica;
- no teste: união do top-20 de B0, B1 e ML por par, deduplicada;
- completar cada par com amostra aleatória estratificada da cauda até no mínimo
  60 eventos julgados;
- mínimo total: 300 eventos únicos e 600 julgamentos independentes;
- leitura livre dos releases pelos anotadores precisa acrescentar mudanças
  omitidas pelos três braços ao gabarito.

Gate de validade da avaliação:

- Krippendorff α ordinal ≥ 0,67;
- concordância bruta no binário nota ≥ 1 de pelo menos 80%;
- ao menos 30 positivos nota ≥ 1, dez nota 2 e três positivos em cada par;
- `nao_julgavel_ocr_ou_estrutura` ≤ 5%.

Falha no gate torna o resultado **INDECIDÍVEL**, não negativo.

## Métricas

Primária operacional: macro `nDCG@10`, ganhos 0/1/3 para notas 0/1/2.
`nDCG@20` é corroborativa obrigatória e não pode ser trocada pela primária.

Secundárias:

- Precision@10 para nota ≥ 1;
- cobertura dos nota 2 no top-10 do pool;
- nDCG@5 e nDCG@20;
- redundância top-10;
- acurácia da operação e do alinhamento;
- citação literal, página, empresa e trimestre corretos;
- quantidade de itens e minutos para atingir 90% de recall;
- mudanças nota 1/2 encontradas corretamente em dez minutos.

Tempo e qualidade são medidos juntos, por par. Um estudo de workflow
confirmatório exige analistas que não produziram o gabarito e desenho
contrabalanceado.

## Barras de decisão

### VALIDAR o componente aprendido no piloto estreito

Todos precisam ocorrer:

- 100% das evidências top-10 existem literalmente e têm procedência correta;
- Δ macro nDCG@10 ≥ +0,10 contra o melhor entre B0/B1;
- Δ macro nDCG@20 ≥ +0,05;
- ganho estritamente positivo nos cinco pares finais;
- Precision@10 não cai;
- cobertura de nota 2 não perde mais de 5 pontos percentuais;
- nenhuma mudança crítica adicional perdida;
- e pelo menos 20% menos itens/tempo para a mesma cobertura, ou 20% mais
  mudanças de alta prioridade no mesmo tempo, sem queda de acurácia > 5 pp.

Mesmo aprovado, o enunciado máximo é “ganho observado nestes cinco pares”.
Generalização exige no mínimo 30–34 pares finais, mais emissores e novo teste
travado.

### REJEITAR o componente aprendido

Qualquer um:

- evidência fabricada, citação/procedência errada ou falso negativo crítico
  adicional;
- ΔnDCG@10 ≤ 0 e derrota em pelo menos três pares, sem ganho de tempo;
- tempo piora ≥ 10% sem compensação de qualidade;
- B1 atinge nDCG@10 ≥ 0,95 e o ganho aprendido fica abaixo de 0,03.

### INDECIDÍVEL

Qualquer caso que não cruze integralmente uma das duas barras, inclusive
concordância insuficiente, poucos positivos, efeito carregado por um emissor,
ausência da segunda leitura ou ausência do estudo de tempo.

## Falsificadores obrigatórios

- datas, números rolados, tabelas ou comprimento dominam o ranking;
- 4T anual contra 1T trimestral fabrica mudança estrutural;
- texto movido vira remoção mais adição;
- OCR/cabeçalho fabrica evento;
- alinhamento une afirmações semanticamente incompatíveis;
- ganho desaparece sem PDF compartilhado;
- resultado é carregado por um emissor;
- métrica offline melhora sem economia de tempo;
- baseline determinístico já está no teto.

## Estado ex ante

- necessidade econômica: plausível;
- redline determinístico: candidato viável a protótipo;
- superioridade de componente aprendido: **INDECIDÍVEL antes da medição**;
- corpus atual: adequado a um gate interno severo, inadequado a alegação geral
  ou treino supervisionado próprio.
