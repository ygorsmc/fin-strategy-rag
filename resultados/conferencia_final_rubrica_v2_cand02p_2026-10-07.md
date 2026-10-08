# Conferência final da rubrica v2 — REPROVADA; CAND-02-P fecha como INDECIDÍVEL

**Data:** 2026-10-07.
**Protocolo:** `resultados/protocolo_conferencia_final_rubrica_v2_cand02p_2026-10-07.md`
(última tentativa, resultado vinculante).
**Artefatos:** `artefatos/cand02p_v3/conferencia_final/`. Rótulos e resultado
congelados no commit `3703a8c`.

## Resultado, pela regra congelada

90 itens nunca vistos, 30 de cada nota do Claude v2, rotulados às cegas pelo
responsável com a rubrica v2.

| Portão | Resultado | Limiar | |
|---|---:|---:|---|
| G1: α ordinal humano × Claude v2 | **0,647** | ≥ 0,67 | não passa |
| G2: itens de nota 2 do Claude que o humano marca com 1 ou 2 | **0,833** (25 de 30) | ≥ 0,70 | passa |

**Decisão: RUBRICA_V2_REPROVADA.** Pelo §1 do protocolo, o CAND-02-P fecha
como INDECIDÍVEL e não há nova tentativa de rubrica sobre estes dados.

| Humano (linha) × Claude v2 (coluna) | 0 | 1 | 2 |
|---|---:|---:|---:|
| **0** | 26 | 8 | 5 |
| **1** | 4 | 14 | 5 |
| **2** | 0 | 8 | 20 |

## Leitura

- **Nenhum item obrigatório ficou de fora.** Em nenhum item em que o humano
  deu 2 o Claude deu 0. O erro mais caro de uma fila de leitura, esconder o
  que importa, não apareceu.
- **O que o Claude prioriza, o humano reconhece** em 83% dos casos (G2).
- **A discordância está no meio e em alarmes falsos.**
  - A nota 1 do Claude se espalha: o humano deu 0 em 8 casos e 2 em outros 8,
    de 30.
  - Cinco itens de nota 2 do Claude (17%) receberam 0 do humano.
- **O α humano × Claude v1 nestes itens foi maior (0,707) que o da v2.** Não
  se pode concluir que a v2 piorou. A amostra foi estratificada pelas notas da
  v2, e selecionar itens pela nota de um leitor penaliza esse leitor (os
  extremos dele incluem os próprios erros). O número é descritivo e enviesado
  por desenho.

## O padrão das quatro medições

| Medição | Amostra | α humano × Claude |
|---|---|---:|
| Conferência do v3 (rubrica v1) | 60 ao acaso | 0,652 |
| Calibração (rubrica v2) | 60 ao acaso | 0,666 |
| Conferência final (rubrica v2) | 90 estratificados | 0,647 |
| Conferência final, Claude v1 | mesmos 90 | 0,707 (enviesado a favor) |

O Claude concorda com este analista num nível estável, em torno de 0,65, logo
abaixo do limiar de 0,67, que é a convenção de Krippendorff para conclusões
tentativas. **Fica sem resposta qual é o teto humano:** quanto dois analistas
concordam entre si nesta tarefa. Com um único humano, não há como saber se
0,65 é pouco ou se já é o nível de concordância entre pessoas.

## O que reabriria

Gold de **mais de um humano** nos mesmos itens, com o α humano × humano medido
e pré-registrado como referência do limiar. Se dois analistas concordarem
perto de 0,65, o leitor Claude está no nível humano e o limiar fixo de 0,67
era exigente demais para a tarefa. Isso é decisão de um protocolo novo, não
releitura deste.

## Erros de desenho deste ciclo, para não repetir

- **Calibração sem poder.** Sorteio ao acaso, quase sem nota 2. Corrigido
  aqui, com poder calculado antes.
- **Limiar absoluto sem referência humana.** O 0,67 foi aplicado sem saber o
  α entre humanos. Qualquer conferência futura deve medir esse teto antes de
  fixar o limiar.
