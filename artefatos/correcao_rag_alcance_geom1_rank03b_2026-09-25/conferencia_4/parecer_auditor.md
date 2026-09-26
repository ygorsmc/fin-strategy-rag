<!--
Parecer do auditor-conformidade (subagente somente leitura, mesmo contexto das
conferências anteriores), devolvido em 26/09 sobre o adendo 3 da correção RAG.
Transcrito na íntegra. É saída de modelo, não gold humano.
-->

# Parecer: conferência final, restrita e somente leitura, do adendo 3 (26/09)

## Veredito: FECHADO

O único achado BAIXA da reconferência do adendo 2 (declaração incompleta do limite B2) está fechado pelo critério que dei. Não há regressão e não encontrei achado novo.

Caminhos:
- [A] = scripts/conferir_alcance_geom1_rank03b.py (`d75252bb…`)
- [T] = tests/test_conferir_alcance_geom1_rank03b.py (`6d239c05…`)
- [K4] = resultados/adendo3_correcao_rag_alcance_geom1_rank03b_2026-09-26.md (`ee89b795…`)
- [R] = resultados/correcao_rag_alcance_geom1_rank03b_2026-09-25.md
- [AD3] = artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/adendo3/

## Achados

Nenhum.

## O que foi confirmado

**Declaração completa, nos três lugares.**
- **Na saída.** O `LIMITE` ([A]:105-111) agora diz:
  - o sinal separado por ignorável fora de Cf/Cc, ou posto antes de moeda com espaço interno, "se perde, e o número pode casar como positivo";
  - o ignorável "dentro do número parte o token, e o prefixo pode casar";
  - "corrigir isso é pré-condição para usar o instrumento em notas de outros emissores".

  O texto não tem dígito e aparece inteiro em `[AD3]busca/conferencia_revisao.json`.
- **No relatório:** [R]:309, com marca de complemento, e [R]:378-384.
- **No contrato:** [K4] (C1).

**Teste de caracterização.** `test_limite_declarado_descreve_o_comportamento_atual` prende comportamento e texto juntos:
- os quatro casos de sinal perdido casam positivo e não entram na lista de ambíguos;
- `1.234.͏567` casa o prefixo;
- as quatro frases do efeito estão no `LIMITE`.

A mutação `limite_sem_o_prefixo` morre por esse teste.

**Mutação.** Rodei `[AD3]verificar_mutacoes.py` de novo e ele reproduziu exatamente:
- 52 de 52 mortas, controle com 970 passed;
- mesmas contagens por mutação e mesmos hashes de código, testes e plugin;
- `adendo3_nao_conferido` e `limite_sem_o_prefixo` morrem, cada uma com 1 falha.

**Sem regressão.**
- **Busca:** a diferença campo a campo contra a busca do adendo 2 é só `limite` e, no pin, os campos do adendo 3 e o hash do código. Confere com `diferenca_para_o_adendo2.json`.
- **24/09:** as expectativas continuam cumpridas.
- **Testes:**
  - os 30 anteriores à onda estão intactos pela AST (só as três mudanças já declaradas);
  - contra o adendo 2, só ganharam asserções/parâmetros do adendo 3 os dois testes de vínculo, mais o teste novo.
- **Hashes:** os 16 da tabela "Hashes do adendo 3" conferem, e a tabela do adendo 2 também. Os artefatos anteriores estão intactos.
- **Arquivos alterados:** desde 00:20 só mudaram os arquivos esperados, e nada fora do escopo.
- **Ordem das escritas:** contrato às 00:28:39, antes dos testes (00:29:04) e do código (00:29:18).
- **Suíte:** 4.019, zero falhas, erros ou skips, rodada às 00:34, depois das edições. Os focados dão 1.125 passed (970 + 155).
- **Não-reprodução:** rodada de novo, sai idêntica à publicada, com `nenhum_reproduz: true`.

**Bytecode.** Nenhum `__pycache__` ou `.pyc` na pasta da onda, nem depois das minhas execuções, todas com `PYTHONDONTWRITEBYTECODE=1`.

**Saídas novas.** Nenhum dígito em trecho, nenhum número ≥ 1.000, `fco_paginas` todas vazias, e nenhum montante ou sinal de FCO.

## O que não foi verificado

- **Suíte completa:** não rodei de novo; usei o XML e os testes focados.
- **Busca e reconferência reais:** não repeti (O1). Confiei na diferença campo a campo e na comparação publicada.
- **Holdout e `cvm*.duckdb`:** não tocados.
- **Repositório:** não criei nem editei nada.
