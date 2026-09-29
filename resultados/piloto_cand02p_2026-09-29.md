# CAND-02-P — piloto do redline com rótulo de IA: INVIÁVEL

**Data:** 2026-09-29.
**Protocolo:** `resultados/protocolo_cand02p_piloto_ia_2026-09-28.md`, com a
Emenda 1, que torna o Claude o leitor único.
**Artefatos:** `artefatos/cand02p/`, com o resultado em `resultado_teste.json`.

## Em uma tela

**Veredito: INVIÁVEL sob o julgamento do Claude** (parada 4). O primeiro
treino foi feito: o M foi treinado em 952 eventos rotulados. Mas ele não supera
o B1, o redline determinístico, na barra fixada antes de medir.

| Braço | nDCG@10 macro | nDCG@20 macro | Críticos no top-20 |
|---|---:|---:|---:|
| B0, massa de tokens | 0,108 | 0,113 | 3 |
| **B1, regras determinísticas** | **0,363** | 0,355 | 11 |
| C, bge-m3 pré-treinado | 0,287 | 0,312 | 14 |
| **M, treinado** | **0,390** | **0,474** | 14 |

Das três condições do desafio, duas passaram e a decisiva não:
- **Δ nDCG@10 = +0,027**, contra um mínimo de +0,10. **Reprova.**
- **O M vence o B1 em 3 de 8 pares**, contra um mínimo de 7. **Reprova.**
- Δ nDCG@20 = +0,119, contra um mínimo de +0,05. Passa.
- Críticos no top-20: M com 14, B1 com 11. Passa.

nDCG@10 por par:

| Par | B1 | M |
|---|---:|---:|
| ABC | 0,85 | 0,52 |
| BANESTES | 0,21 | 0,41 |
| BB | 0,27 | 0,57 |
| BMG | 0,34 | 0,23 |
| BRADESCO | 0,20 | 0,07 |
| BTG | 0,49 | 0,40 |
| ITAU | 0,10 | 0,51 |
| SANTANDER | 0,45 | 0,41 |

## O que o resultado diz

- **O M não é consistentemente melhor que regras simples.** O ganho na média
  vem de três pares (BB, ITAU e BANESTES), e o M perde em cinco. Com 8 pares,
  isso não é sinal distinguível de variância entre emissores.
- **O ganho no top-20 é real neste dado, mas não era a métrica primária.** Ele
  é uma pista, não um resultado: trocar de métrica depois de ver o teste seria
  ajuste ao dado.
- **Nenhum braço ordena bem.** O melhor nDCG@10 é 0,39. O problema continua
  difícil, e o B1 está longe do teto.
- **Treino e teste têm distribuições diferentes.** O treino compara
  2T→3T, trimestre com trimestre. O teste compara 4T→1T, anual com
  trimestral, e o universo do teste tem quase o dobro de eventos. Oito pares
  de treino é pouco para aprender essa diferença.

## Limites declarados

- **O rótulo é de um leitor só,** e a confiabilidade dele não foi medida
  (Emenda 1). No treino, o Claude e o Gemini concordaram pouco: α de 0,42 e
  acordo binário de 70%. "Inviável" vale sob o julgamento do Claude.
- **Uma ressalva de leitura:** no par BB do teste, um Grep com curinga do
  leitor trouxe linhas dos releases de 2T e 3T do BB, fora do seu pacote. O
  agente declarou que não as usou. São documentos públicos, sem rótulo, braço
  ou score.
- **Não se afirma nada sobre o CAND-02 humano,** que continua INDECIDÍVEL.

## Custo

- **Gemini:** US$ 1,48 contabilizados, só no treino, e o faturamento foi
  ativado em 29/09. Os rótulos do Gemini ficaram sem uso.
- **Claude:** 16 execuções de agente, cerca de 130 mil a 240 mil tokens cada.
  Duas ondas caíram no limite de sessão e foram retomadas sem perda de
  trabalho.

## O que reabriria

Três coisas, qualquer uma com pré-registro próprio:
- mais pares de treino da mesma transição do teste (4T→1T de outros anos ou
  emissores);
- métrica primária de top-20, fixada antes de medir;
- rótulo com confiabilidade medida: dois leitores concordando, ou conferência
  humana.

Nada disso autoriza reusar este teste.
