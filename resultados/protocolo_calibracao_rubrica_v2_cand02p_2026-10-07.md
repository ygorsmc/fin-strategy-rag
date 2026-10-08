# Protocolo — calibração da rubrica v2 do CAND-02-P, antes de qualquer releitura geral

**Data:** 2026-10-07. **Fixado antes do sorteio e de qualquer rótulo com a v2**,
no commit que introduz este arquivo.

**Origem.** O v3 deu INDECIDÍVEL na conferência humana: α 0,652, abaixo do
limiar de 0,67 (`resultados/piloto_cand02p_v3_2026-10-07.md`). Na
adjudicação, a discordância cega veio de duas fontes opostas:
- o humano deu 1 a divulgações novas que não mudavam a leitura;
- o leitor Claude deu 1 a inversões de sinal e a mudanças de perímetro que a
  rubrica manda tratar como 2.

O responsável decidiu (07/10, "Pode começar") testar se uma rubrica mais
precisa resolve isso **antes** de pagar a releitura dos 64 pares.

## 1. A pergunta

Com a rubrica v2, um humano e o leitor Claude concordam, em itens novos, com
α ≥ 0,67?

## 2. Rubrica v2

`artefatos/cand02p_v3/rubrica_v2.md` é a v1 inteira, sem mudança, mais uma seção de
esclarecimentos em regras gerais, sem citar item nenhum. A origem de cada
regra:

| Regra | Origem |
|---|---|
| Divulgação nova que não muda a leitura é 0 | adjudicação: H25, H32, H35, H36 |
| Causa repetida do release anterior é 0 | adjudicação: H42 |
| Sinal que muda só pela troca de base (ano contra trimestre) não é inversão | controle de qualidade do treino: SANTANDER 4T2018→1T2019, não o gold |
| Inversão real de sinal em crédito, capital ou resultado é 2, também em segmento | adjudicação: H57 |
| Perímetro consolidado é 2 | adjudicação: H37 |
| Norma contábil que entra em vigor é 2 | adjudicação: H51 |
| Inadimplência ou custo de crédito em alta material é 2 | adjudicação: H24 |
| KPI de rentabilidade em máxima ou mínima de vários anos é 2 | adjudicação: H12 |
| Ranking de mercado e causa nova são 1 | adjudicação: H09, H03 |

## 3. Desenho

- **Pares:** 4 pares de teste do v3, de 4 emissores distintos, sorteados com
  semente fixa (`escolher_pares`).
- **Itens:** 60 itens desses pares, 15 por par, sorteados entre os que o
  humano **ainda não viu**. Os 60 da conferência e da adjudicação ficam fora
  (`escolher_itens`).
- **Leitor Claude v2:** o mesmo modelo e as mesmas instruções, só que com a
  rubrica v2 (`instrucoes_leitor_claude_v2.md`). Relê os 4 pares inteiros
  (120 itens cada), cada leitor com uma pasta temporária exclusiva. Saída em
  `rotulos/claude_v2/`.
- **Humano:** rotula os 60 itens às cegas com a rubrica v2, sem ver nota
  nenhuma do Claude, v1 ou v2.

## 4. Medida e decisão

| Medida | Papel |
|---|---|
| **α humano × Claude v2** | **portão**: ≥ 0,67 → RUBRICA_V2_APROVADA; abaixo, ausente ou NaN → RUBRICA_V2_NAO_BASTA |
| α humano × Claude v1, nos mesmos 60 itens | controle: separa a melhora da rubrica da mudança do próprio humano |
| α Claude v1 × Claude v2 | descritivo: quanto a rubrica mudou o leitor |

**Leitura dos controles, fixada aqui:**
- Se o α com a **v1** também passar de 0,67, o humano mudou depois da
  adjudicação, porque aprendeu a régua do Claude. A aprovação da v2 então
  não prova que a rubrica funciona.
- A rubrica só se credita pela diferença entre os dois α, nos mesmos itens.
- Com 60 itens, diferença pequena entre os dois α é indistinguível.

## 5. O que cada decisão autoriza

- **RUBRICA_V2_APROVADA:** autoriza escrever o protocolo de um v4. Ele teria
  a rubrica v2, a releitura de todos os pares com ela, as tabelas incluídas no
  universo e um teste novo. O v4 tem protocolo próprio; esta calibração não o
  congela.
- **RUBRICA_V2_NAO_BASTA:** a releitura geral não se justifica por esta via.
  O limite está em quanto um leitor de IA reproduz o julgamento humano, não na
  redação da rubrica.

**Nenhuma decisão muda o veredito do v3**, que segue INDECIDÍVEL.

## 6. Ordem de congelamento

1. Este protocolo, a rubrica v2, as instruções v2, o script e os testes.
2. O sorteio (`sortear`) e o pacote cego do humano.
3. Os rótulos do Claude v2, que podem rodar em paralelo com o humano.
4. Os rótulos do humano, gravados como entregues.
5. A medição (`medir`).

Cada passo é commitado antes do seguinte.

## Custo previsto

4 execuções de leitor Claude, de cerca de 150 mil a 200 mil tokens cada, e
cerca de uma hora de leitura humana.
