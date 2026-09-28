# Pareceres da conferência B8 da ROTA-2 (27/09)

Estes são os dois arquivos que o campo `fontes` de `../conferencia.json` fixa
por hash, mais os relatórios finais de cada conferente.

| Arquivo | O quê | SHA-256 |
|---|---|---|
| `final_rota2.json` | conferência 1: 83 correções por célula própria | `ba9540b5a0d497ac860890caeacc17fa7d9289e3623c015fc4b6e90c1aa53424` |
| `final_rota2_cadeia.json` | conferência 2: 42 correções por elo e cadeia, mais 10 confirmações | `498e083b31a08774ff986dcb63d50114e44240abe512b8a8f0eaec18cefa762f` |
| `relatorio_conferencia_1.md` | relatório final do conferente 1 | — |
| `relatorio_conferencia_2.md` | relatório final do conferente 2 | — |

**Procedência.** Os originais foram gravados no scratchpad da sessão, que
depois foi limpo. A auditoria final de 28/09 apontou a lacuna (B5). Os dois
JSON foram **reconstruídos byte a byte**, com base em três fatos:
1. Os comandos dos conferentes, nas transcrições, gravaram com
   `json.dump(obj, ensure_ascii=False, indent=1)`, sem quebra de linha final.
2. Cada parecer foi copiado sem alteração para `../conferencia.json`.
3. Reserializados na ordem de string dos ids, os dois dão exatamente os hashes
   de `fontes`.

Os relatórios foram extraídos das mensagens finais dos conferentes. Antes de
versionar, foram varridos em busca de número com cara de valor: só aparecem
ids de documento, um código de companhia e o limiar `1.000`. Nenhum valor de
conta 6.x.

**O que não foi recuperado.** Os scripts de cada conferente. O método de cada
um está em `conferentes[].metodo` de `../conferencia.json` e nos relatórios.
