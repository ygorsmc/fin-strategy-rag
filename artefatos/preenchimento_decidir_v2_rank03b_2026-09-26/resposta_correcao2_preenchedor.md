<!--
Respostas do preenchedor à segunda rodada de correção, 26/09. Transcritas na
íntegra, na ordem. É saída de modelo, não decisão humana. A primeira entrega da v3
tinha SHA-256 a8964772…a39f6; a versão final, depois do ajuste das duas sobras que
o próprio preenchedor apontou, é 46bc85539a3f45705dc85fba0a3c3e65b2d9a55751afa50c7c6467195791be59.
-->

## Primeira entrega da v3

A v3 está pronta: `artefatos/preenchimento_decidir_v2_rank03b_2026-09-26/proposta_v3.md`, SHA-256 `a8964772182382d955af3c0caff6263237378fe23b818726b53a0807454a39f6`. É igual à v2 exceto nos três pontos pedidos; v1 (`5c0e72b9…31e0`), v2 (`e64f61db…07b6c`) e o estado do git ficaram como estavam.

1. **Texto pronto de E no §5.5.** Passa a censurar a observação "cuja janela de oito trimestres, cujo S1 ou cujo S2 combinem valores de documentos com escalas aplicadas diferentes, com algum documento sem veredito de escala decidido para o FCO". Saíram o rótulo inteiro (q1–q4) e o ativo em D.
2. **Ativo não mantido como variante.** Ele só afeta `fco_ttm_sobre_ativo` e `ativo_total_em_D`, não o rótulo. Mantê-lo inflaria a perda que o responsável vai usar para escolher entre C e E.
3. **Ponteiros.** SRC:1322–1325 virou SRC:1461–1464, no fato 3 do §5.1 e na linha E1 do registro. REC25:343–344 virou REC25:395, no fato 5 do §7. Conferi as duas linhas no código antes de trocar.
4. **Registro da revisão.** Ganhou uma linha para esta rodada, com o que mudou e o motivo de o ativo ter saído.

Duas coisas ficaram como estavam porque a instrução era não mexer em outro texto:
- **Descrição de E na lista de opções do §5.5.** Continua dizendo "janela ou rótulo". É mais larga que o novo texto pronto e ainda não diz "S1 ou S2".
- **Cabeçalho.** Ainda se apresenta como "Versão 2".

Se quiser, ajusto os dois numa rodada rápida.

## Ajuste das duas sobras (pedido pelo orquestrador)

Ajustei as duas sobras na própria `artefatos/preenchimento_decidir_v2_rank03b_2026-09-26/proposta_v3.md`. O SHA-256 novo é `46bc85539a3f45705dc85fba0a3c3e65b2d9a55751afa50c7c6467195791be59`.

1. **Descrição de E na lista de opções do §5.5:** agora censura a observação cuja janela de oito trimestres, cujo S1 ou cujo S2 combinem documentos de escalas aplicadas diferentes, com algum documento sem veredito de escala para o FCO. O texto diz explicitamente que o rótulo inteiro e o ativo em D não entram, o que bate com o texto pronto de E.
2. **Cabeçalho:** "Versão 2." virou "Versão 3.".

A linha desta rodada no "Registro da revisão" registra as duas mudanças. O `diff` contra a v2 mostra só elas, além das alterações da rodada anterior (texto pronto de E, dois ponteiros, linha do registro). A v1 (`5c0e72b9…31e0`), a v2 (`e64f61db…07b6c`) e o estado do git não mudaram.
