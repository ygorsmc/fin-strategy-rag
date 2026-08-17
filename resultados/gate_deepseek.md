# Gate DeepSeek — geração via API

- **Início (UTC):** 2026-08-13T20:43:09.766877+00:00
- **Fim (UTC):** 2026-08-13T20:43:14.840038+00:00
- **Resultado:** ✅ PASSOU
- **Provedor/modelo configurado:** LLM_PROVIDER=deepseek /
  deepseek-v4-flash
- **Versão do prompt:** v9
- **Pior caso reservado no preflight:** US$ 0.000955
- **Teto desta execução:** US$ 10.000000
- **Chamadas iniciadas/concluídas/falhas:** 2 /
  2 / 0
- **Custo observado:** US$ 0.000333
- **Débito conservador:** US$ 0.000333

## Evidência sanitizada

resposta factual/citação + recusa RN02 válidas; tokens=1461+457; latência=5.073s

O teto acima vale para **uma execução** deste gate; invocá-lo novamente pode
gerar nova cobrança. O journal append-only em
`resultados/gate_deepseek_execucoes.jsonl` registra o antes e o depois de cada
chamada sem salvar prompts/respostas. Se o processo morrer após o provedor
responder e antes do segundo registro, o custo fica indeterminado e o pior caso
pré-reservado deve ser tratado como débito. Isso não é garantia exactly-once.

O custo observado usa a telemetria e os preços configurados em
`DEEPSEEK_PRECO_ENTRADA_USD_MILHAO` e `DEEPSEEK_PRECO_SAIDA_USD_MILHAO` — o de
entrada é o pior caso (cache-miss); confira a tabela vigente do provedor antes
de usar o número aqui como referência de orçamento futuro.
