# Protocolo — conferência final da rubrica v2 do CAND-02-P (última tentativa, resultado vinculante)

**Data:** 2026-10-07. **Fixado antes do sorteio**, no commit que introduz este
arquivo, junto com o script, os testes e a simulação de poder.

**Origem.** A calibração deu RUBRICA_V2_NAO_BASTA por 0,004 (α 0,666;
`resultados/calibracao_rubrica_v2_cand02p_2026-10-07.md`). O teste não tinha
poder: IC95% de [0,39; 0,87] e só 1 a 2 notas 2 em 60 itens. O efeito da
rubrica foi positivo (Δα +0,17 sobre a v1). O responsável decidiu fazer uma
última conferência, bem desenhada ("Então vamos para a última conferência").

## 1. Última tentativa, resultado vinculante

Esta é a última conferência da rubrica v2 com estes dados. O resultado decide
e não se repete o teste:

- **RUBRICA_V2_APROVADA:** autoriza escrever o protocolo de um v4. Ele teria a
  rubrica v2, a releitura de todos os pares com ela, as tabelas no universo e
  um teste novo, com protocolo próprio.
- **RUBRICA_V2_REPROVADA:** o CAND-02-P fecha como INDECIDÍVEL e entra em
  `resultados/becos_sem_saida.md`. Sobre estes dados, não haverá nova tentativa
  de rubrica. Só reabre com gold de mais de um humano ou com outro desenho de
  leitor, sempre com pré-registro próprio.

## 2. Desenho

- **Pares:** os mesmos 4 da calibração (BANESTES, BMG, BRADESCO e ITAU
  4T2021→1T2022), que já têm rótulos do Claude v2. Não gasta leitor novo.
- **Amostra estratificada:** 30 itens com nota 0 do Claude v2, 30 com nota 1 e
  30 com nota 2, sorteados com semente fixa entre os itens que o humano nunca
  viu. Ficam fora os 75 itens desses pares que ele já viu, nas duas
  conferências anteriores. Itens disponíveis: 285 de nota 0, 72 de nota 1 e 48
  de nota 2.
- **Humano:** rotula os 90 itens às cegas com a rubrica v2, em ordem
  embaralhada, sem ver nota nenhuma do Claude.

## 3. Portões (os dois precisam passar)

| Portão | Medida | Limiar |
|---|---|---|
| **G1** | α ordinal humano × Claude v2 na amostra | **≥ 0,67** |
| **G2** | dos itens com nota 2 do Claude v2, fração que o humano marca com 1 ou 2 | **≥ 0,70** |

α ausente ou NaN, ou G2 sem item de nota 2, reprova (AGENTS.md §4.4, regra 4).

**Por que dois portões.** Uma amostra equilibrada tende a dar α maior que uma
amostra ao acaso, dominada pela nota 0, com a mesma qualidade de leitura. O G1
sozinho, numa amostra estratificada, facilitaria o teste por troca do que se
mede. O limiar de 0,67 não baixa. O G2 acrescenta a exigência central do
redline: o que o Claude prioriza, um analista reconhece como relevante.

**O α desta amostra não se compara** com 0,652 (v3) nem com 0,666
(calibração), que vieram de amostras ao acaso.

## 4. Poder, calculado antes do sorteio

Simulação com 2.000 reamostragens (`python -m scripts.cand02p_conferencia_final poder`,
`artefatos/cand02p_v3/conferencia_final/poder.json`). Os cenários são hipóteses
de P(nota humana | nota do Claude):
- **base:** estimado das duas conferências anteriores;
- **pessimista** e **acaso:** contraste.

| Cenário | α mediano | Faixa 95% | P(aprovar G1 e G2) |
|---|---:|---|---:|
| base | 0,709 | [0,567; 0,824] | **0,72** |
| pessimista | 0,478 | [0,307; 0,637] | 0,006 |
| acaso | 0,003 | [−0,206; 0,214] | 0,000 |

**Leitura:**
- O teste separa bem "a rubrica funciona como os dados indicam" de "não
  funciona".
- Se a verdade estiver colada no limiar, como sugere o cenário base, o teste
  ainda reprova em cerca de 28% dos casos. Com 120 itens, o poder quase não
  muda (0,73 contra 0,72, com os dois portões e a mesma semente), e por isso
  ficaram 90 itens.

## 5. Declarações

- **O humano conhece o desenho.** Ele soube no chat que a amostra teria cerca
  de 30 itens de cada nota do Claude. Isso pode levá-lo a dar mais notas 2. Não
  sabe quais itens são de qual estrato. O viés residual fica declarado.
- **A estratificação foi escolhida depois de ver a calibração falhar.** A
  razão é o defeito de desenho identificado (nenhuma nota 2 na amostra), não o
  valor do α. O limiar não baixou e o G2 tornou o teste mais exigente.
- **Os rótulos do Claude v2 vêm da calibração e ficam como estão.**

## 6. Descritivos (não decidem)

- matriz humano × Claude v2;
- acordo exato;
- número de itens em que o humano deu 2 e o Claude deu 0;
- α humano × Claude v1 nos mesmos itens.

## 7. Ordem

1. Este protocolo, o script, os testes e `poder.json`.
2. O sorteio e o pacote cego.
3. Os rótulos do humano, gravados como entregues.
4. A medição.

Cada passo é commitado antes do seguinte.
