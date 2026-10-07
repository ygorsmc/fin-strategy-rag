# Releitura cega (teste-reteste) do leitor Claude — declaração antes de rodar

**Data:** 2026-10-06. Commitada antes de qualquer releitura.

## Por quê

O leitor é único desde a Emenda 1 do v1, e a confiabilidade dele nunca foi
medida. No primeiro lote do treino do v3, o leitor do SANTANDER 4T2018→1T2019
deu nota 1 a todas as 13 inversões de sinal ou tendência que justificou. Isso
inclui inadimplência, Basileia e PDD. Os leitores anteriores do Santander, na
mesma transição, deram nota 2 a cerca de 3 em cada 10 dessas inversões (7 de
22). O caso está na ponta leniente da régua do próprio leitor, sem estar fora
dela. **Não se relê o par para corrigir a nota**: aplicar a régua do desenhista
só onde ela discordou seria pior do que o ruído. O que se faz é medir.

## Desenho

- **Releitura dirigida:** `SANTANDER_4T2018_1T2019`, motivada pelo alerta acima.
  Reportada à parte.
- **Releitura sorteada:** `BMG_4T2018_1T2019`. Sorteio entre os outros 17 pares
  de treino, com `random.Random("20260928:reteste").choice(sorted(pares))`. É a
  estimativa sem viés de seleção.
- **Leitor:** o mesmo modelo, as mesmas instruções e o mesmo prompt, em contexto
  limpo. A saída vai para `rotulos/claude_reteste/treino/<PAR>.jsonl`, que o
  piloto não lê, porque `LEITORES = ("claude",)`.
- **Medidas, por par:** α ordinal de Krippendorff entre a primeira leitura e a
  releitura, acordo exato e acordo em "nota ≥ 1", sobre os itens julgáveis nas
  duas.

## Uso

- **Só descritivo.** Os rótulos de registro continuam sendo os da primeira
  leitura. A releitura não entra no treino, no teste nem em decisão nenhuma do
  protocolo.
- Se o α do par sorteado ficar abaixo de 0,67, o limiar que o protocolo usa
  para a conferência humana, o relatório registra que o próprio leitor não
  repete a sua nota com essa confiabilidade. Isso vira ressalva do veredito, não
  o muda.
