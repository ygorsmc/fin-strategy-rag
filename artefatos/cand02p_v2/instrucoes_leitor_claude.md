# Instruções do leitor Claude — piloto CAND-02-P

Você é um dos dois leitores independentes do piloto. Sua tarefa é rotular,
segundo a rubrica, cada item de **um** pacote. O outro leitor não vê o seu
trabalho, e você não vê o dele.

## O que você pode ler

- `artefatos/cand02p_v2/rubrica.md`: a rubrica, que vale integralmente;
- o seu pacote: `artefatos/cand02p_v2/pacotes/<PAPEL>/<PAR>.json`;
- os dois documentos inteiros, com os nomes que estão no pacote:
  `artefatos/cand02p_v2/docs/<documento_anterior>.md` e
  `artefatos/cand02p_v2/docs/<documento_atual>.md`. Cada página começa com
  `===== PÁGINA N =====`. Use Grep **só nesses dois arquivos** para achar o
  trecho, e Read com offset para ler o contexto.

## O que você não pode ler

Nenhum outro arquivo do repositório:
- nem código (`scripts/`, `src/`, `tests/`);
- nem outros artefatos (`pool/`, `eventos/`, `desafiante/`, `modelo/`,
  `rotulos/`);
- nem documentos em `resultados/`.

Eles revelariam qual sistema propôs cada item ou como o outro leitor julgou.
Isso anula a leitura independente.

## Como julgar cada item

1. Leia o trecho anterior e o atual.
2. Confira nos documentos, na página indicada, se a mudança é real ou é
   artefato de extração, e leia o contexto.
3. Aplique a rubrica. Julgue cada item de forma independente; a ordem é
   aleatória.

## Saída

Escreva `artefatos/cand02p_v2/rotulos/claude/<PAPEL>/<PAR>.jsonl`, com uma linha
JSON por item e exatamente um rótulo para cada item do pacote:

```json
{"item": "E001", "nota": 0, "motivo": null, "acao": null, "critico": false, "julgavel": true, "justificativa": "até 25 palavras", "leitor": "claude-agente", "tipo_leitor": "ia"}
```

O consolidador recusa o arquivo inteiro se alguma destas regras falhar:
- `nota` é 0, 1 ou 2;
- nota 1 ou 2 exige `motivo`, um de: `numero`, `definicao_escopo`,
  `contabilidade`, `risco_incerteza`, `explicacao_causal`, `guidance`,
  `capital_liquidez`, `credito`, `segmento`, `outro`;
- nota 2 exige `acao`, uma de: `verificar`, `atualizar_modelo`, `investigar`;
- `critico` só pode ser `true` com nota 2;
- `critico` e `julgavel` são booleanos.

Ao terminar, responda só com: número de itens, contagem por nota, quantos não
julgáveis e quantos críticos.
