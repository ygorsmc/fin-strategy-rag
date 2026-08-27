# Ranking de candidatos de ML para Value Investing

**Fonte normativa da ordem de validação.** Registrado em 2026-08-27 conforme
definição do Ygor. Se relatórios anteriores tiverem adotado uma sequência
funcional diferente por ausência deste registro, este arquivo prevalece para a
numeração e para a escolha dos próximos candidatos.

| Rank | Candidato | Uso pelo analista | Situação |
|---:|---|---|---|
| **1** | **Fila de deterioração anormal da lucratividade — alvo Z** | Priorizar empresas aparentemente saudáveis com risco de queda material de ROA | Pronto para experimento confirmatório |
| **2** | **Previsão probabilística de fundamentos** | Alimentar cenários de lucro, margem e ROA em vez de emitir buy/sell | Viável com o painel atual |
| **3** | **Deterioração de conversão de caixa/FCF** | Detectar lucro que deixa de virar caixa | Excelente alvo, mas exige incorporar DFC |
| **4** | **Early warning de KPIs bancários** | Antecipar deterioração de NPL, custo de crédito, capital e eficiência | Melhor encaixe no corpus; exige fonte bancária em escala |
| **5** | **Risco de divergência gerencial × contábil** | Priorizar reconciliações de LAJIDA/KPIs que merecem revisão humana | Diferenciador forte, mas faltam documentos e rótulos |
| **6** | **Reading queue por mudança de divulgação** | Destacar alterações materiais em notas, releases e fatores de risco | Precisa ampliar o corpus e criar julgamentos humanos |
| **7** | **Detecção multivariada de anomalias contábeis** | Sinalizar combinações incomuns de contas para investigação | Fácil de prototipar, difícil de provar incrementalidade |
| **8** | **Seleção de pares e valuation relativo** | Encontrar comparáveis e múltiplos condicionais | Depende de preços point-in-time e universo investível |

## Regra de leitura

- O **rank** define a ordem solicitada de avaliação, não aprovação automática.
- Cada candidato mantém pré-registro, baselines, gates, pareceres isolados e
  veredito próprios.
- Resultado de outro candidato não é herdado apenas por semelhança de nome.
- Alterar alvo, gold, população ou unidade de decisão cria nova rodada e exige
  novo pré-registro.

## Validações registradas

- **Rank 5 — risco de divergência gerencial × contábil:** estado científico
  **INDECIDÍVEL**; **não implementar ML agora**. O corpus tem pontes bancárias,
  mas não LAJIDA/LAJIR, gold ou escala confirmatória. Relatório:
  `resultados/validacao_rank05_divergencia_gerencial_contabil_2026-08-27.md`.
