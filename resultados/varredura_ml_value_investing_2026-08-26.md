# Varredura — onde ML é (ou pode ser) usado em Value Investing

**Estado: VARREDURA CONCLUÍDA; candidatos em validação sequencial.**

Resultados já fechados:

- C1 — deterioração de lucratividade: **rejeitado antes do treino**
  (`validacao_c1_2026-08-26.md`);
- CAND-02 — redline semântico: **não implementar ML agora; utilidade
  determinística ainda não medida** (`validacao_cand02_redline_2026-08-27.md`).
- CAND-03 — triagem de anomalias contábeis: **não implementar ML agora;
  E2 prospectivo permanece cientificamente indecidível**. Reabre com shadow,
  gold humano e tempo, não com algoritmo novo
  (`validacao_cand03_anomalias_contabeis_2026-08-27.md`).
- CAND-04 — previsão interpretável de fundamentos: **rodada A
  rejeitada/invalidada; hipótese econômica e ML indecidíveis; não implementar
  ML agora**. Vinte e três linhas contaminadas por escala explicam 61,64% do
  erro; A2 versus lucro dos controladores é novo estimando
  (`validacao_cand04_previsao_fundamentos_2026-08-27.md`).

## Por que esta varredura existe

O debate anterior (`debate_modelo_util_2026-08-26.md`) terminou em negativo:
seis candidatos, cada um vencido pelo próprio baseline trivial. Mas ele partiu
de **"o que dá para fazer com o dado que temos"**, e isso ancorou a busca inteira
nas restrições do projeto.

Decisão de Ygor: **inverter a ordem.** Primeiro o mapa completo do campo, sem
contexto do projeto e sem filtro de viabilidade. Depois a eliminação, uma a uma.
Só no fim se pergunta o que faz sentido aqui.

## Protocolo

- **Quatro levantadores independentes**, com acesso à web, territórios sem
  sobreposição.
- **Nenhum recebe contexto do projeto.** Não sabem que existe corpus de bancos
  brasileiros, painel CVM, RAG, restrição de orçamento ou qualquer resultado
  anterior. Se soubessem, filtrariam por viabilidade — que é exatamente o viés
  que esta varredura existe para evitar.
- **Nenhum filtro de viabilidade nesta fase.** Item caro, item que exige dado que
  não temos e item que já falhou em replicação entram todos. A eliminação vem
  depois e é decisão nossa, não deles.
- **Resultado negativo da literatura é item de primeira classe** — técnica que
  não replicou é informação tão útil quanto técnica que funciona.

## Territórios

| # | Território |
|---|---|
| A | Sinais fundamentalistas e qualidade contábil — *scores*, accruals, fraude, insolvência, previsão de lucro a partir de demonstrações |
| B | NLP e texto — arquivamentos, teleconferências, tom, legibilidade, mudança de divulgação, LLMs em análise financeira |
| C | Dados alternativos e sinais externos — satélite, cartão, web, cadeia de suprimentos, ESG, patentes, vagas, *insiders*, posse |
| D | Valuation, previsão de fundamentos e construção de carteira — incluindo mercados emergentes |

## Formato exigido de cada item

Nome · o que produz · dado necessário · evidência (com números e com falhas de
replicação) · quem usa na prática · maturidade (commodity / contestado /
fronteira) · fontes.

---
