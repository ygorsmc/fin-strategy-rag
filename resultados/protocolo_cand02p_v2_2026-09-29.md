# Protocolo — CAND-02-P v2: mais treino da transição anual→trimestral, teste novo

**Data:** 2026-09-29. **Fixado antes de qualquer rótulo do v2**, no commit que
introduz este arquivo.

**Origem.** O v1 deu INVIÁVEL
([relatório](piloto_cand02p_2026-09-29.md)). Uma das condições que o
relatório listava para reabrir era ter mais pares de treino da mesma transição
do teste (4T→1T). O responsável decidiu buscá-los em 29/09 ("Então vamos atrás
de mais documentos"), com US$ 5 de OCR, e confirmou o conjunto de 2.010
páginas.

## 1. O que muda em relação ao v1

**Só os dados.** Braços, features, hiperparâmetros do M, rubrica, leitor
(Claude, Emenda 1 do v1), pool, limiares e paradas são os mesmos, sem
alteração. A métrica primária **continua sendo nDCG@10**. O ganho de nDCG@20
visto no v1 **não** a substitui: trocá-la agora seria escolher a métrica depois
de ver um teste.

| Papel | Pares | Rótulos |
|---|---|---|
| treino | 8 pares 2T2025→3T2025 (v1) | já existem (952) |
| treino | 8 pares 4T2025→1T2026 (**o teste do v1**, aqui só treino) | já existem (940) |
| treino | 6 pares 4T2023→1T2024: ABC, BMG, BRADESCO, BTG, ITAU e SANTANDER | novos |
| **teste** | **8 pares 4T2024→1T2025, os oito emissores** | novos; **nunca vistos** |

O teste do v1 não é reusado como teste. Os pares 4T2023→1T2024 e
4T2024→1T2025 compartilham só o emissor, não documento. Nenhum documento do
teste v2 aparece no treino.

**Documentos:** corpus `corpus/cand02p_v2/`, com manifesto e cache de OCR
próprios (AGENTS.md §3.15). São os releases do RAD da CVM, localizados pelo
índice IPE, com a maior versão entregue.

## 2. Diferenças declaradas

- **Itaú.** O documento do RAD, "Análise Gerencial da Operação", tem cerca de
  33 páginas. O do corpus do v1, baixado do site de RI, tem cerca de 160 e traz
  as demonstrações completas. O par de teste do Itaú é curto com curto e
  coerente por dentro, mas difere do Itaú do treino.
- **Treino extra sem BB e sem BANESTES.** O BB ficou de fora por orçamento: 661
  páginas. O BANESTES não tem release de 1T2024 no RAD.
- **O desenhista viu o resultado do v1.** Isso é inevitável e é a razão de nada
  além dos dados mudar.

## 3. Paradas, as mesmas do v1 com a Emenda 1

1. Não julgáveis acima de 5% → INDECIDÍVEL.
2. Menos de 30 eventos com nota 2 → INDECIDÍVEL.
3. B1 com nDCG@10 ≥ 0,95 → INVIÁVEL.
4. O M precisa, ao mesmo tempo:
   - superar o B1 em Δ nDCG@10 ≥ +0,10 e em Δ nDCG@20 ≥ +0,05;
   - vencer em pelo menos 7 dos 8 pares;
   - não trazer menos eventos críticos no top-20 que o B1.

   Se cumprir as quatro condições → PROMISSOR, e aí vem a conferência humana
   do §6 do v1. Senão, INVIÁVEL sob o julgamento do Claude.

## 4. Ordem de congelamento

1. Este protocolo e o código do `--piloto v2`.
2. Universo, B0, B1 e C dos 14 pares novos.
3. Pool e pacotes do treino novo.
4. Rótulos do treino novo.
5. M treinado nos 22 pares e congelado.
6. Pool e pacotes do teste, e os rótulos.
7. Métricas.

Cada passo é commitado antes do seguinte.
