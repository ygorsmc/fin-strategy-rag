<!--
Parecer do auditor-conformidade (subagente somente leitura, mesmo contexto das
conferências anteriores), devolvido em 26/09 sobre o adendo 2 da correção RAG.
Transcrito na íntegra. É saída de modelo, não gold humano. [A], [T], [K3], [R] e
[AD2] apontam para as versões preservadas em `../codigo_adendo2/`, para o adendo 2
ao contrato, para o relatório da onda e para `../adendo2/`.
-->

# Parecer: reconferência restrita, somente leitura, do adendo 2 (26/09)

## Veredito: FECHADO COM RESSALVAS

B1, B3, B4 e B5 estão fechados pelos critérios que dei, cada um com contraprova que exercita a decisão. B2 ficou declarado como limite (a alternativa que aceitei) e a declaração aparece na saída publicada, mas está incompleta: omite um dos efeitos que reportei e atenua a direção do erro. Isso vira um achado BAIXA. Não há regressão, e nada fechado antes foi reaberto.

Caminhos:
- [A] = scripts/conferir_alcance_geom1_rank03b.py (`fa928c3d…`)
- [T] = tests/test_conferir_alcance_geom1_rank03b.py (`9671c9d0…`)
- [K3] = resultados/adendo2_correcao_rag_alcance_geom1_rank03b_2026-09-26.md (`4328e69e…`)
- [R] = resultados/correcao_rag_alcance_geom1_rank03b_2026-09-25.md
- [AD2] = artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/adendo2/

## Achado

### 1. BAIXA — B2: a declaração do limite omite o efeito de prefixo e atenua a direção do erro

**O que está declarado.** O texto novo do `LIMITE` está em [A]:103-106 e aparece em `[AD2]busca/conferencia_revisao.json`. Diz que os ignoráveis fora de Cf/Cc "não entram no contexto do sinal" e que "moeda com espaço interno não é reconhecida".

**O que o código faz hoje** (reproduzido, números inventados). Em todos estes casos o número casa como correspondência positiva, e nada entra na lista de ambíguos:
- `"Total −͏1.234"` e `"Total (︀1.234︀)"`: +1234, motivo `limpo`;
- `"Total -ㅤ1.234"`: +1234;
- `"Total -R $ 1.234"`: +1234;
- **`"Total 1.234.͏567"`: casa o prefixo +1234.** O ignorável dentro do número parte o token, que é o formato original do RAG-02. Eu tinha reportado este caso no achado 2 do parecer anterior.

**O que falta na declaração.**
- O efeito de prefixo não aparece no `LIMITE`, em [K3] (B2) nem em [R]:309.
- O `LIMITE` não diz que o erro é uma **correspondência positiva indevida**. "Não é reconhecida", no caso da moeda, sugere só falta de reconhecimento, quando o menos antes dela se perde.
- [K3] diz "um sinal ... se perde" e [R]:309 diz "sinal perdido", mas nenhum dos dois diz que o número passa a casar.
- A pré-condição ("corrigir antes de usar em notas de outros emissores") está em [K3] e em [R]:309, mas não na saída, que só diz "o instrumento só foi medido nestas notas".

**Por que é BAIXA.** O dado real tem zero ocorrências. É uma declaração incompleta, não um defeito ativo.

**Critério de fechamento.**
- Completar o `LIMITE` (e [K3]/[R]) com: sinal separado do número por um ignorável, ou posto antes de moeda com espaço interno, se perde, e o número pode casar como positivo; ignorável dentro de um número parte o token, e o prefixo pode casar.
- Levar a pré-condição para o texto da saída.
- Opcionalmente, fixar em teste o comportamento declarado. Hoje `test_limite_declara_o_residuo_do_sinal` só confere que duas expressões existem no texto.

## Observação (não é achado)

Às 26/09 00:12:04 apareceu `artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/adendo/__pycache__/verificar_mutacoes.cpython-312.pyc`. Veio de carregar o harness do adendo 1 por `importlib` sem `PYTHONDONTWRITEBYTECODE`. O git ignora (`.gitignore:2`) e nenhum artefato com hash mudou. Mesmo assim, é um arquivo novo dentro da pasta de evidência preservada: convém rodar com `PYTHONDONTWRITEBYTECODE=1`. Na minha repetição da rodada não surgiu bytecode.

## O que foi confirmado

**B1 (parêntese pela NFKC) — fechado.**
- Parêntese ornamental de abertura com `)` normal, e `(` normal com ornamental de fechamento: ambíguo, caractere a caractere (15 + 15), mais os dois lados ornamentais.
- As mutações "abre pelo nome" e "fecha pelo nome" morrem com 15 falhas cada. Na rodada anterior sobreviviam.

**B3 (quebra de linha) — fechado.**
- Com DOTALL em [A]:501, `"1\n234\n567"` é barrado e `"9\n999"` passa.
- A reconferência registra `false` em vez de abortar, com teste.
- A mutação `sem_dotall` morre (3 falhas).

**B4 (serialização) — fechado.**
- Identidade e resultado são serializados antes de `mkdir` e de qualquer escrita ([A]:809-813).
- Um campo que não é JSON derruba a execução sem deixar arquivo, com teste.
- `serializar_depois_de_gravar` morre.
- A troca de `gravar_antes_de_verificar` mira o bloco novo: o trecho inclui as duas serializações e a escrita do pin, e o harness exige ocorrência única. Ela morre com 3 falhas.

**B5 (documentação) — fechado.**
- Marcas em [R]:184 (170 = 29 + 6 + 6 + 6 + 108 + 15) e em [R]:193.
- As observações estão declaradas em [R]:314-318; a dos sósias de menos diz corretamente que "o número sai positivo".

**Harness.** Rodei `[AD2]verificar_mutacoes.py` de novo e ele reproduziu exatamente: 50 de 50 mortas, controle com 967, mesmas contagens, mesmos hashes (código `fa928c3d`, testes `9671c9d0`, plugin `d3467393`). O harness do adendo 1 continua `fd2831ee`, sem alteração.

**Sem regressão.**
- A busca difere da do adendo só em `limite`, e no pin só em `data`, `codigo_sha256` e nos dois campos do adendo 2. Confirmei por diff campo a campo, que bate com `diferenca_para_o_adendo.json`.
- As expectativas de 24/09 e do adendo estão cumpridas nas duas comparações.
- Os 30 testes anteriores à onda estão intactos (AST: só as três mudanças já declaradas).
- Contra o adendo 1, só dois testes mudaram, e só ganharam asserções/parâmetros (adendo 2 fixado por hash).
- Os 18 hashes da tabela do adendo 2 conferem.
- Os artefatos de 24/09, da conferência de 25/09, da primeira execução e do adendo 1 estão intactos.
- Nada fora do escopo mudou: desde 25/09 21:02 só mudaram os arquivos esperados, e o relatório de alcance não foi tocado.

**Execuções.**
- Contrato às 00:10:36, antes do código (00:11:00) e dos testes (00:11:22), pela última escrita.
- Testes focados: 1.122 passed (967 + 155).
- Suíte: 4.016, zero falhas, erros ou skips, rodada às 00:17, depois das edições; +40 = 967 − 927.
- `nao_reproducao` rodada de novo sai idêntica à publicada, com `nenhum_reproduz: true`.

**Saídas novas.** Nenhum dígito em trecho, nenhum número ≥ 1.000, `fco_paginas` todas vazias, e nenhum montante ou sinal de FCO.

## O que não foi verificado, e por quê

- **Suíte completa:** não rodei de novo; usei o XML e os 1.122 focados.
- **Busca e reconferência reais:** não repeti (O1). Confiei na diferença campo a campo contra a busca do adendo e nas comparações, que reproduzi.
- **Precedência do contrato sobre a primeira edição do código:** o sistema de arquivos só mostra a última escrita.
- **Holdout e `cvm*.duckdb`:** não tocados.
- **Repositório:** não criei nem editei nada; minhas sondas ficaram no scratchpad.
