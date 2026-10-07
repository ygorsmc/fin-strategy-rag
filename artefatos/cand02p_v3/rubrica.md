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
