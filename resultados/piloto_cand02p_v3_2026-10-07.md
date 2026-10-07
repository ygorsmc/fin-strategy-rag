# CAND-02-P v3 — PROMISSOR de novo, num teste novo e duas vezes maior

**Data:** 2026-10-07.
**Protocolo:** `resultados/protocolo_cand02p_v3_2026-10-06.md`, congelado antes
do OCR.
**Artefatos:** `artefatos/cand02p_v3/`.
**Universo:** redline **só de texto**. As tabelas ficaram fora, pelo achado de
07/10 (`resultados/achado_tabelas_ocr_cand02p_2026-10-07.md`).

## Em uma tela

O M foi treinado em 48 pares e testado em 16 pares nunca vistos (4T2021→1T2022
e 4T2022→1T2023, oito emissores). Ele passou nas quatro condições do protocolo,
com folga em todas:

| Braço | nDCG@10 | nDCG@20 | Críticos no top-20 |
|---|---:|---:|---:|
| B0, massa de tokens | 0,133 | 0,171 | 14 |
| B1, regras determinísticas | 0,365 | 0,389 | 17 |
| C, bge-m3 pré-treinado | 0,326 | 0,332 | 18 |
| **M, treinado** | **0,583** | **0,592** | **29** |

| Condição | Limiar | v3 | v2 |
|---|---|---:|---:|
| Δ nDCG@10 | ≥ +0,10 | **+0,219** | +0,166 |
| Δ nDCG@20 | ≥ +0,05 | **+0,203** | +0,231 |
| Vitórias do M sobre o B1 | ≥ 7 de 8 | **8 de 8 emissores** | 7 de 8 pares |
| Críticos no top-20 | M ≥ B1 | **29 × 17** | 13 × 6 |

Paradas 1 e 2: 0,37% de não julgáveis (limite 5%) e 213 eventos com nota 2
(mínimo 30).

**IC95% do Δ nDCG@10, por bootstrap de emissores** (10.000 reamostragens,
semente 20260928): **[+0,139; +0,301]**. O limite inferior fica acima do
limiar de +0,10. O v2 vencia exatamente no limite; o v3 não depende de um par.

## Por par e por emissor

| Emissor | 4T21→1T22 (B1 → M) | 4T22→1T23 (B1 → M) | Δ médio |
|---|---|---|---:|
| ABC | 0,252 → 0,518 | 0,579 → 0,840 | +0,263 |
| BANESTES | 0,195 → 0,518 | **0,526 → 0,367** | +0,082 |
| BB | 0,155 → 0,606 | 0,180 → 0,575 | +0,423 |
| BMG | **0,277 → 0,233** | 0,615 → 0,807 | +0,074 |
| BRADESCO | 0,139 → 0,541 | 0,217 → 0,456 | +0,320 |
| BTG | 0,656 → 0,711 | 0,341 → 0,537 | +0,125 |
| ITAU | 0,467 → 0,659 | 0,182 → 0,569 | +0,289 |
| SANTANDER | 0,697 → 0,840 | 0,357 → 0,558 | +0,173 |

O M perde em 2 dos 16 pares:
- **BANESTES 4T2022→1T2023:** o C, pré-treinado, foi o melhor braço (0,709).
- **BMG 4T2021→1T2022:** é o par do leitor mais leniente, com só 4 notas 2.

O ganho é maior onde o documento é grande e cheio de ruído (BB, Bradesco e
Itaú): ali o B1 fica entre 0,14 e 0,22.

## O que PROMISSOR significa, e o que não significa

- **O rótulo é de um leitor de IA só, e o M foi treinado para imitá-lo.** O
  protocolo trata o resultado como hipótese até a conferência humana. Ela está
  pronta e cega, em `artefatos/cand02p_v3/humana/` (60 itens). Se o α
  humano × Claude for ≥ 0,67, o veredito fica "rótulo de IA conferido por
  amostra humana"; abaixo disso, INDECIDÍVEL.
- **Confiabilidade medida, validade não.** A releitura cega do próprio
  leitor deu α 0,81 no par sorteado e 0,74 no dirigido
  (`artefatos/cand02p_v3/reteste/resultado.md`). O leitor repete a própria
  nota. Se um analista concordaria, só a conferência humana diz.
- **Só texto.** O universo não tem linha de tabela. É onde o B1, feito de
  regras numéricas, deveria ser mais forte. O resultado vale para redline de
  texto de releases; com tabela é outro experimento (v4).
- **No máximo:** ganho observado nestes 16 pares, oito emissores, dois anos.
  Nada vai para o produto.

## Ressalvas declaradas

- **Leitura descartada.** O primeiro leitor do BRADESCO 4T2022→1T2023 abriu
  rótulos de outros pares de teste na pasta temporária compartilhada. A
  leitura foi descartada e refeita por leitor isolado
  (`artefatos/cand02p_v3/rotulos/descartados/LEIAME.md`). A auditoria das 35
  transcrições não achou outro caso.
- **Régua entre leitores.** Cada par tem um leitor, e eles variam: nota 2 vai
  de 3% a 21% por par. Há também tratamento diferente para frase mal pareada
  pelo extrator: alguns dão 0, outros julgam contra a contraparte certa. O
  ruído afeta B1 e M igualmente, porque o rótulo é o mesmo para os dois.
- **Desenhista não cego.** O desenhista viu o v1, o v2 e a curva de
  aprendizado. Por isso só mudaram o dado, o tamanho do teste e a unidade de
  vitória, e esta última decorre da regra 8.
- **Pool.** O nDCG é calculado sobre o pool rotulado (os primeiros de cada
  braço e mais uma parte aleatória), como no v1 e no v2.

## Custo

- **OCR:** 4.727 páginas, cerca de US$ 9,45.
- **Leitor Claude:** 18 pares de treino, 16 de teste, 1 refeito e 2
  releituras, num total de 37 execuções de agente, de cerca de 140 mil a 240
  mil tokens cada. Houve dois limites de sessão; os leitores interrompidos
  foram retomados pelo mesmo agente.
