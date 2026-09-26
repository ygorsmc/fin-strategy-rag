# Parecer independente — reconferência AP1/AP2

Data: 2026-09-26. Agente `auditor_pendencias_geom1_26`, somente leitura.
Transcrição do parecer recebido:

**AP1 e AP2 fechados no escopo desta reconferência.** Não encontrei regressão
concreta nas alterações do adendo.

- **AP1:** os casos `TOTAL R$`, `ATIVO US$` e `TOTAL $` voltaram a
  corresponder. Passaram 78 controles sintéticos de contexto, sinais e
  moedas, além da varredura de marcas/preenchedores. Prefixos fragmentados
  continuam ambíguos. O limite residual `PL R$` está declarado no adendo.
- **AP2:** a reprodução original com `ESC-0001"solta` agora levanta
  `csv.Error` **antes da validação semântica**. Oito manifestos válidos com
  aspas escapadas, vírgulas e quebras de linha passaram pela cadeia
  semântica. Comparei também a validação lexical com uma gramática
  independente em **97.656 entradas curtas**, sem divergências.

Conferi os diffs contra `antes_auditoria/` e o SHA-256 do adendo:
`4c0c50f695ddfd3b2c377307f94adbb513af10dc2e0f28cbf198a48da73d38d3`.
Não houve mudança em arredondamento, esquema ou exceção histórica nesses
diffs.

Limites: verificação sintética, sem nova validação de corpus e sem reexecução
independente da suíte completa. Não alterei arquivos nem executei
busca/reconferência real, gates ou treino. **O1 e as seis escolhas permanecem
pendentes; este parecer não aprova o v2 nem execução real.**

Nota de registro do implementador: os controles suplementares foram
executados em memória pelo auditor e relatados nesta mensagem; não há um
harness persistido desses 97.656 casos. Os testes de regressão persistidos
estão nos arquivos `tests/test_pendencias_geom1_rank03b.py` e
`tests/test_conferir_alcance_geom1_rank03b.py`.
