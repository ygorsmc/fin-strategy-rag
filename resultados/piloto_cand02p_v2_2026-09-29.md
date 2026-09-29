# CAND-02-P v2 — PROMISSOR, aguardando a conferência humana

**Data:** 2026-09-29.
**Protocolo:** `resultados/protocolo_cand02p_v2_2026-09-29.md`.
**Artefatos:** `artefatos/cand02p_v2/`.

## Em uma tela

Com mais treino da transição anual→trimestral, o modelo treinado passou nas
três condições do protocolo, num teste novo que nunca tinha sido visto
(4T2024→1T2025, os oito emissores):

| Braço | nDCG@10 | nDCG@20 | Críticos no top-20 |
|---|---:|---:|---:|
| B0, massa de tokens | 0,134 | 0,181 | 9 |
| B1, regras determinísticas | 0,342 | 0,340 | 6 |
| C, bge-m3 pré-treinado | 0,391 | 0,373 | 14 |
| **M, treinado** | **0,508** | **0,571** | 13 |

As três condições do desafio passaram:
- Δ nDCG@10 = **+0,166**, para um mínimo de 0,10;
- Δ nDCG@20 = **+0,231**, para um mínimo de 0,05;
- o M vence o B1 em **7 de 8 pares**, exatamente o mínimo, e perde no
  Santander.

Os críticos no top-20 também passaram: 13 no M, contra 6 no B1.

**O que mudou do v1 para o v2 foi só o dado.** O treino passou de 8 pares
(952 eventos, só 2T→3T) para 22 pares (2.602 eventos), dos quais 14 são da
transição 4T→1T que o teste mede. Braços, features, hiperparâmetros, rubrica,
leitor e limiares são os mesmos.

## O que PROMISSOR significa, e o que não significa

**O rótulo é de um leitor só, o Claude, e o M foi treinado para imitá-lo.** O
viés favorece o M. Por isso o protocolo trata "promissor" como hipótese, não
como resultado, até a conferência humana do §6:
- 60 itens do teste, sorteados com semente fixa e estratificados por par;
- rotulados às cegas pelo responsável;
- se o α entre o humano e o Claude for ≥ 0,67 → "promissor, rótulo de IA
  conferido por amostra humana";
- se ficar abaixo → INDECIDÍVEL.

Mesmo conferido, o máximo que se afirma é "ganho observado nestes oito pares".
Nada vai para o produto.

## Ressalvas declaradas

- **O M vence em 7 de 8 pares, exatamente no limite.** Uma virada de par
  mudaria o veredito.
- **Tipo de documento.** O documento de 4T2024 do BTG no RAD é uma apresentação
  de teleconferência, e o de 1T2025 é o release; muitas mudanças desse par são
  efeito de formato (nota 0). O Itaú do RAD é a versão curta (cerca de 33
  páginas), enquanto o do treino herdado do v1 tem cerca de 160.
- **Exposição.** O leitor do treino BRADESCO 4T2023→1T2024 viu, por um Grep com
  curinga, 3 linhas do release 4T2024 do Bradesco, que é documento do teste.
  Era texto público, sem rótulo. Outros leitores declararam desvios só de
  forma: gravação em lote único e leitura por Read ou script em vez de Grep,
  sempre restrita aos dois documentos do próprio par.
- **O desenhista viu o v1.** Por isso o v2 mudou só o dado. A métrica primária
  continuou nDCG@10.

## Custo

- **OCR:** 2.010 páginas, cerca de US$ 4,02, num job em lote.
- **Leitor Claude:** 14 execuções de agente, de 116 mil a 172 mil tokens cada.
- **Gemini:** não usado no v2.
