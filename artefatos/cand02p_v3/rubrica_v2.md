RUBRICA — prioridade de leitura de mudanças entre dois releases consecutivos (CAND-02)

Você é um analista de research de bancos. Cada item descreve uma possível mudança
entre o release ANTERIOR e o ATUAL do mesmo emissor. Julgue se um analista que já
leu o release anterior precisa ler esta mudança no atual.

Notas:
- 0 — rotina ou superfície: layout, período que rolou automaticamente (3T25 virou
  4T25), paráfrase equivalente, número atualizado sem mudar a leitura, ou mudança
  sem ação analítica. Movimento de texto, quebra ou fusão de bloco, cabeçalho,
  rodapé e ruído de OCR também são 0.
- 1 — conferir: muda fato, número, definição, escopo, causa, risco, incerteza ou
  qualificador que merece inspeção.
- 2 — leitura obrigatória: muda guidance, KPI relevante, tendência, sinal, ordem de
  grandeza, perímetro, política contábil, capital ou liquidez, risco de crédito,
  reapresentação, ou contradiz ou qualifica afirmação anterior.

Para nota 1 ou 2, dê o motivo principal: numero, definicao_escopo, contabilidade,
risco_incerteza, explicacao_causal, guidance, capital_liquidez, credito, segmento
ou outro. Para nota 2, dê a ação: verificar, atualizar_modelo ou investigar.
critico = true só para nota 2 cuja omissão num relatório de research seria erro grave.
julgavel = false só quando o OCR ou a estrutura impedem comparar com segurança
(nao_julgavel_ocr_ou_estrutura). Mudança que você só acha pouco importante é
nota 0, não julgavel = false.

Regras:
- Confira nos documentos, não só no trecho. O item pode ser artefato de extração:
  a linha existe sem mudança no outro documento, ou o trecho foi cortado. Nesse
  caso é nota 0, ou julgavel = false se a comparação não for segura.
- Número que mudou só porque o trimestre mudou é rotina, salvo se muda tendência,
  sinal ou ordem de grandeza, ou foge do padrão.
- Julgue cada item de forma independente. A ordem dos itens é aleatória.
- justificativa: no máximo 25 palavras, em português.

Formato de cada rótulo:
{"item": "E001", "nota": 0, "motivo": null, "acao": null, "critico": false,
 "julgavel": true, "justificativa": "..."}

ESCLARECIMENTOS DA V2 (07/10/2026) — valem junto com tudo acima

Saíram da adjudicação humana de 60 itens. Não mudam as notas 0, 1 e 2; dizem
como aplicá-las nos casos em que leitores divergiam.

É 0:
- Divulgação nova (número, destaque, rodapé, métrica ou definição de métrica)
  que não muda a leitura do trimestre. Ser informação inédita não basta para 1.
- Explicação causal que repete a do release anterior. Só causa nova ou
  alterada pode ser 1 ou 2.
- Mudança de sinal que só reflete a troca da base de comparação. Por exemplo,
  o release anual compara o ano com o ano anterior, e o trimestral compara o
  trimestre com o mesmo trimestre do ano anterior. Isso não é inversão.

É 2, também em linha de segmento ou de produto:
- Inversão real de sinal na mesma base de comparação (trimestre contra
  trimestre, ano contra ano) em crédito, originação, inadimplência, provisão,
  capital, liquidez ou resultado.
- Entrada ou saída de empresa do perímetro consolidado.
- Política ou norma contábil que passa a valer no trimestre, ou
  reclassificação que ela provoca.
- Inadimplência ou custo de crédito que sobe de forma material.
- KPI de rentabilidade em máxima ou mínima de vários anos.

É 1:
- Fato novo que merece conferência sem mudar a leitura: mudança de posição em
  ranking de mercado, causa nova para a variação de uma linha, número que pede
  verificação.
