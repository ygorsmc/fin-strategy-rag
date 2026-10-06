# Protocolo — CAND-02-P v3: teste de 16 pares, dois anos × oito emissores

**Data:** 2026-10-06. **Fixado antes do OCR e de qualquer rótulo do v3**, no
commit que introduz este arquivo.

**Origem.** O v2 deu PROMISSOR ([relatório](piloto_cand02p_v2_2026-09-29.md)),
mas com o M vencendo o B1 em **7 de 8 pares, exatamente no limite**: a virada
de um par mudaria o veredito. A curva de aprendizado de 29/09
(`artefatos/cand02p_v2/curva_aprendizado.json`, descritiva, reusa o teste do
v2) indicou duas coisas:
- o ganho vem sobretudo de pares da mesma transição do teste: só 4T→1T, Δ nDCG@10
  +0,178; só 2T→3T, −0,014;
- volume acrescenta pouco no fim da curva: +0,133 com 16 pares, +0,166 com 22.

O responsável liberou US$ 10 de OCR em 06/10 e escolheu este desenho entre
três ("4.727 págs (Recomendado)").

## 1. O que muda em relação ao v2

Três coisas, e só elas:
1. **O teste fica maior e é novo:** 16 pares em vez de 8.
2. **O treino cresce:** 30 pares já rotulados mais 18 novos.
3. **A condição de vitória passa a contar emissores, não pares.** No v2 havia um
   par por emissor e as duas contagens coincidem; no v3 há dois, e trimestres do
   mesmo emissor não são réplicas (AGENTS.md §4.4, regra 8).

Braços, features, hiperparâmetros do M, rubrica, leitor (Claude, Emenda 1 do
v1), pool, limiares de Δ e as paradas 1 a 3 ficam iguais. A métrica primária
**continua nDCG@10**.

| Papel | Pares | Rótulos |
|---|---|---|
| treino | 16 do v1: 8 pares 2T2025→3T2025 e 8 pares 4T2025→1T2026 | já existem |
| treino | 14 do v2: 6 pares 4T2023→1T2024 e os 8 pares 4T2024→1T2025 (**o teste do v2**, aqui só treino) | já existem |
| treino | 6 pares 4T2018→1T2019: ABC, BMG, BRADESCO, BTG, ITAU, SANTANDER | novos |
| treino | 7 pares 4T2019→1T2020: os oito emissores menos o BB | novos |
| treino | 5 pares 4T2020→1T2021: ABC, BMG, BTG, ITAU, SANTANDER | novos |
| **teste** | **16 pares 4T2021→1T2022 e 4T2022→1T2023, os oito emissores** | novos; **nunca vistos** |

**Nenhum documento do teste aparece no treino**, nem nos pilotos herdados. Os
trimestres do teste (4T2021, 1T2022, 4T2022, 1T2023) não estão em par de treino
nenhum. Há um teste que verifica isso:
`test_v3_nenhum_documento_do_teste_aparece_no_treino`.

**Documentos:** corpus `corpus/cand02p_v3/`, com manifesto e cache de OCR
próprios (AGENTS.md §3.15). São 68 releases do RAD da CVM, num total de **4.727
páginas**, localizados pelo índice IPE com a regra do v2:
- mesmo tipo de documento por emissor;
- versão em português;
- maior versão entregue.

## 2. Diferenças declaradas

- **BB só no teste.** Um par do BB custa de 505 a 783 páginas. O treino novo
  ficou sem ele por orçamento. O BB continua no treino herdado, com três pares.
- **Bradesco 4T2020→1T2021 fora** por orçamento: 407 páginas passariam do teto
  de 5.000.
- **BANESTES** não tem release de 1T2019 nem de 4T2020 no RAD.
- **Entregas sem assunto.** BTG 1T2020, 4T2021 e 1T2022 e ABC 1T2022 e 1T2023
  têm, cada um, uma entrega em português e outra em inglês sem assunto
  distinguível. Ficou a versão em português, escolhida pela contagem de palavras
  funcionais das três primeiras páginas.
- **Reentregas.** BB 1T2022, Itaú 4T2022 e BANESTES 1T2023 têm uma v2 com PDF
  diferente da v1. Ficou a v2.
- **Bradesco 1T2019 não tem camada de texto.** Só o OCR o lê. O português foi
  conferido numa página renderizada como imagem.
- **Itaú.** É a versão do RAD: 33 a 46 páginas. Coerente com o v2, mas não com o
  Itaú de cerca de 160 páginas do v1.
- **O desenhista viu o v1, o v2 e a curva**, e a curva reusou o teste do v2. Por
  isso, além do dado, só mudam o tamanho do teste e a unidade de vitória. A
  unidade decorre da regra 8, não do resultado do v2: no v2 as duas contagens
  dão 7.

## 3. Paradas, as do v2 com a unidade de vitória por emissor

1. Não julgáveis acima de 5% → INDECIDÍVEL.
2. Menos de 30 eventos com nota 2 → INDECIDÍVEL.
3. B1 com nDCG@10 ≥ 0,95 → INVIÁVEL.
4. O M precisa, ao mesmo tempo:
   - superar o B1 em Δ nDCG@10 ≥ +0,10 e em Δ nDCG@20 ≥ +0,05, em média macro
     sobre os 16 pares;
   - **vencer em pelo menos 7 dos 8 emissores.** Um emissor conta como vencido
     quando a média do nDCG@10 do M nos dois pares dele supera a do B1. Par sem
     nDCG (nenhum ganho positivo) fica fora da média; emissor sem par medido não
     conta como vencido;
   - não trazer menos eventos críticos no top-20 que o B1, somando os 16 pares.

   Se cumprir as quatro → PROMISSOR. Senão → INVIÁVEL sob o julgamento do
   Claude. A contagem por par sai no resultado como número descritivo e não
   decide nada.

Código: `scripts/cand02p_piloto.py --piloto v3` (`UNIDADE_VITORIA = "emissor"`,
`vencidos_por_emissor`). Contraprova da decisão:
`test_no_v3_a_decisao_conta_emissores_e_nao_pares`.

## 4. Conferência humana

**Se der PROMISSOR:** vale o §6 do v1. São 60 itens do pool de teste do v3,
sorteados com semente fixa e estratificados por par; o responsável os rotula às
cegas, e o α precisa ser ≥ 0,67.

**A conferência do v2 continua pendente e é independente desta.** O leitor é o
mesmo nos dois pilotos. Se a conferência do v2 der α < 0,67, os rótulos do v3
ficam sob a mesma suspeita, e um PROMISSOR do v3 não a resolve.

## 5. Ordem de congelamento

1. Este protocolo, o manifesto e o código do `--piloto v3`.
2. OCR em lote dos 68 documentos.
3. Universo, B0, B1 e C dos 34 pares novos.
4. Pool e pacotes do treino novo.
5. Rótulos do treino novo.
6. M treinado nos 48 pares e congelado.
7. Pool e pacotes do teste, e os rótulos.
8. Métricas.

Cada passo é commitado antes do seguinte.

## Custo previsto

- **OCR:** 4.727 páginas, cerca de US$ 9,45, num job em lote.
- **Leitor Claude:** 34 execuções de agente, contra 14 no v2. As mais pesadas
  são os dois pares do BB e os quatro do Bradesco.
