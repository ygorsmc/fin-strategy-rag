# Artefatos do piloto documental B-DFC-01J

Gerados por `scripts/piloto_bancos_dfc.py`. **Não são amostra supervisionada**
e nenhum gate aqui autoriza treino.

## Regeneração

```bash
python -m scripts.piloto_bancos_dfc auditar
```

Roda offline, sem rede e sem chamada paga: lê os PDFs já versionados do corpus
`ifrs` e reescreve todos os arquivos abaixo de forma determinística.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `escopo.csv` | Os 25 pacotes do escopo, por construção |
| `fontes.jsonl` | Documentos usados, com hash conferido |
| `fatos.jsonl` | Cada cifra com página, coluna, unidade, período e evidência |
| `mapa_j.jsonl` | Decisão semântica por rubrica, com motivo financeiro |
| `derivacoes.jsonl` | Linhagem dos derivados e o J de cada pacote |
| `componentes_dfc.jsonl` | Linhas da DFC confrontadas com o balanço |
| `auditoria_pacotes.csv` | Uma linha por pacote, inclusive os sem documento |
| `auditoria.json` | Contagens derivadas da tabela, nunca digitadas |
| `execucao.json` | Rede, custo, arquivos lidos e exposição ao holdout |

## Limites que não podem ser lidos a menos

- A identificação é **as-restated**: os valores de 2024 vêm de coluna
  comparativa em documento de 2025. Nenhum pacote tem P3 conferido.
- `j_limite_inferior` e `j_limite_superior` delimitam J; não há ponto estimado.
  Onde J não foi identificado os dois campos ficam **vazios**, não zero.
- Cobertura documental não é tamanho de amostra nem poder estatístico.
