# Calibração da rubrica v2 — RUBRICA_V2_NAO_BASTA por 0,004, com teste sem poder

**Data:** 2026-10-07.
**Protocolo:** `resultados/protocolo_calibracao_rubrica_v2_cand02p_2026-10-07.md`.
**Artefatos:** `artefatos/cand02p_v3/calibracao/`. Rótulos e resultado
congelados no commit `bd23110`.

## Resultado, pela regra congelada

| Nos mesmos 60 itens novos | α ordinal | Acordo exato |
|---|---:|---:|
| **Humano × Claude v2** (portão, ≥ 0,67) | **0,666** | 0,867 |
| Humano × Claude v1 (controle) | 0,498 | 0,817 |
| Claude v1 × Claude v2 | 0,722 | 0,883 |

**Decisão: RUBRICA_V2_NAO_BASTA.** O α ficou 0,004 abaixo do limiar. A
decisão não muda depois de vista.

## O que os números dizem além da decisão

Bootstrap de itens, 4.000 reamostragens, semente 20260928:

- **O portão não tinha poder.** IC95% do α humano × v2: [0,39; 0,87]. Em
  47% das reamostragens o α passa de 0,67, então o resultado é inconclusivo,
  e não negativo.
- **A amostra quase não tem nota 2.** O humano deu 1, o Claude v1 deu 1 e o
  Claude v2 deu 2, em 60 itens; na primeira conferência foram 7. O α foi
  decidido quase só pela fronteira entre 0 e 1, e a categoria que mais pesa
  no redline ficou praticamente sem teste.
- **O efeito da rubrica é positivo.** O Δα entre v2 e v1, pareado nos mesmos
  itens, é **+0,168**, com IC95% de [0,000; +0,372] e P(Δ ≤ 0) = 0,028.
- **O humano não mudou na direção do Claude.** O α humano × v1 nestes itens é
  0,498, abaixo do 0,652 da primeira conferência. A hipótese de que a
  adjudicação ensinou ao humano a régua do Claude, que o controle existia para
  pegar, não se confirma.

## Correção da interpretação pré-escrita

O protocolo (§5) dizia que, com RUBRICA_V2_NAO_BASTA, "o limite está em
quanto um leitor de IA reproduz o julgamento humano, não na redação da
rubrica". **Os dados contradizem isso.** A rubrica moveu o α em +0,17. A
decisão continua valendo: a releitura geral não fica autorizada por esta
calibração. A frase, não.

## Erro de desenho, registrado para não repetir

Os 60 itens foram sorteados ao acaso no pool, sem garantir itens de nota 2.
Com prevalência de nota 2 perto de 3% a 10%, um portão de α ≥ 0,67 em 60
itens é quase moeda. **Regra para qualquer conferência futura:** fixar antes
uma amostra com número mínimo de itens de cada nota, ou medir acordo
separado na nota 2, e calcular o poder antes de rodar.

## Estado

O CAND-02-P segue **INDECIDÍVEL** (v3). A rubrica v2 é melhor que a v1 para
aproximar humano e Claude, mas não está validada contra o limiar.
