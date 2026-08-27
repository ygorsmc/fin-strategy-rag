# Validação CAND-04 — previsão interpretável de fundamentos

**Data:** 2026-08-27  
**Estado:** CAND-04A congelado **REJEITADO/INVALIDADO** · hipótese econômica
**INDECIDÍVEL** · componente aprendido **INDECIDÍVEL** · engenharia
**NÃO IMPLEMENTAR ML AGORA**

## Veredito conjunto

Dois especialistas trabalharam isolados na primeira rodada — um em Ciência de
Dados e outro em Mercado Financeiro/Value Investing —, receberam os mesmos
achados apenas por mediação na réplica e validaram por unanimidade na tréplica:

1. o experimento congelado CAND-04A está **rejeitado/invalidado**;
2. a fórmula econômica `lucro T+1 / ativo T` **não foi refutada**: sua
   previsibilidade permanece indecidível porque o teste não mediu um gold
   íntegro e point-in-time;
3. as 23 linhas identificadas depois do resultado não podem ser removidas para
   “corrigir” o resultado; só podem ser adjudicadas contra a fonte e tratadas
   por regra independente do residual em uma nova rodada;
4. nenhum modelo aprendido foi carregado e nenhum deve ser carregado agora;
5. CAND-04A2 versus um novo alvo de lucro dos controladores é uma escolha de
   novo estimando. Nenhum dos dois herda números, aprovação ou teste de A.

Isso separa três afirmações que não são sinônimas:

| Objeto | Veredito |
|---|---|
| Rodada CAND-04A, tal como congelada | **REJEITADA/INVALIDADA** |
| Conceito econômico de prospective ROA | **INDECIDÍVEL**, não refutado |
| Superioridade de um componente aprendido | **INDECIDÍVEL** |
| Ação de engenharia | **NÃO IMPLEMENTAR ML AGORA** |

## O que foi pré-registrado

Antes de abrir o resultado, foi congelado em
`pre_registro_cand04_previsao_fundamentos_2026-08-27.md`:

```text
y(i,t+1) = 10.000 × lucro_liquido_consolidado(i,t+1) / ativo_total(i,t)
```

O denominador de T foi escolhido para ser conhecido no instante da previsão e
comum aos quatro baselines:

- B0: persistência do lucro de T;
- B1: lucro de T−3, mesmo trimestre fiscal do ano anterior;
- B2: mediana dos lucros T, T−1, T−2 e T−3;
- B3: mediana fixa de B0, B1 e B2.

O teste final teria os últimos oito targets completos, com pelo menos oito
releases anteriores por companhia. A métrica primária seria MAE em pontos-base,
macro por companhia. O próprio pré-registro listava como falsificadores alvo ou
erro dominado por escala, mistura indevida de 4T derivado e trimestre isolado e
uso de versões futuras.

## Resultado as-restated dos baselines

O auditor encontrou 3.218 releases, 435 companhias e cobertura sazonal de 100%
nos targets 2T2024–1T2026. A amostra passou; a integridade, não.

| Baseline | MAE macro, bp | MAE micro, bp | Mediana AE, bp | Correlação intra | Direção: cobertura / acerto |
|---|---:|---:|---:|---:|---:|
| B0 — persistência | 1.025,38 | 1.055,67 | 73,27 | −0,009 | 0% / abstém |
| B1 — sazonal | 1.172,50 | 1.196,38 | 69,56 | +0,528 | 99,97% / 68,44% |
| B2 — mediana 4T | 953,59 | 985,81 | 59,10 | −0,077 | 99,97% / 67,35% |
| B3 — combinado | **950,94** | **983,06** | **57,80** | −0,068 | 83,59% / 71,40% |

B3 “vence” B2 por apenas 2,65 bp de MAE macro, mas **nenhum desses números é
confirmação preditiva**. O painel é as-restated e a discrepância MAE × mediana
é produzida principalmente por fatos contaminados por unidade.

Uma correção de métrica também ficou travada em teste: B0 prevê mudança zero e,
portanto, **abstém** da direção. Contar todas as abstenções como erros produziria
“acerto 0%” sem significado. O artefato passou a publicar cobertura e acerto
condicional à emissão de direção.

## O falsificador que encerrou a rodada

### 1. Concentração da cauda

- as 33 linhas do top 1% respondem por **83,55%** do erro absoluto de B3;
- as 17 linhas do top 0,5% respondem por **78,57%**;
- 20 targets com `|y| > 10.000 bp` respondem por **71,28%**;
- o menor quintil de ativo mede MAE **4.332,62 bp**, contra **97,76 bp** no
  maior quintil.

### 2. Descontinuidade de escala observável

O ativo de T+1 foi usado **somente como auditoria do rótulo**, nunca como
feature nem como denominador. Vinte e três linhas, oito companhias e 0,71% do
teste apresentaram `ativo(T+1)/ativo(T)` fora de `[0,01; 100]` ou não positivo.
Elas respondem por **61,64%** do erro absoluto de B3.

O rastreamento até `fatos_contabeis` mostrou mudanças próximas de 1.000× entre
`MIL` e `UNIDADE`. Em casos concretos, o ITR de nove meses chega marcado como
`UNIDADE`, embora a ordem de grandeza permaneça a de milhares, enquanto a DFP
anual volta a `MIL`. A derivação do 4T converte um lado e subtrai o outro,
produzindo lucro trimestral maior que o ativo por ordens de grandeza.

O problema não é uma suposição do auditor. A própria CVM orienta que o
preenchimento de ITR/DFP mantenha consistência com a escala escolhida, mil ou
unidade. [Ofício-Circular CVM/SEP 002/2011](https://www.gov.br/cvm/pt-br/assuntos/noticias/2011/oficio-circular-cvm-sep-n002-2011---orientacoes-gerais-sobre-o-preenchimento-dos-formularios-dfp-e-itr-29f5c5651de24daf90fe91da46a95fca/)

### 3. O 4T é outro regime

| Origem do target | n | MAE B3, bp | Mediana AE, bp |
|---|---:|---:|---:|
| Arquivado | 2.421 | 449,94 | 52,28 |
| 4T derivado | 797 | **2.602,46** | 84,70 |

O CPC 21 reconhece sazonalidade, maior uso de estimativas em demonstrações
intermediárias e apresentação do trimestre corrente e do acumulado. A Resolução
CVM 80 também distingue o calendário do ITR e da DFP. Logo, versão, período e
transição 3T→DFP fazem parte da definição do gold, não são apenas metadados.
[CPC 21](https://www.cpc.org.br/Arquivos/Documentos/288_CPC21_R1.pdf) ·
[Resolução CVM 80](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol080.pdf)

### 4. A sensibilidade não salva o teste

Remover as 23 linhas reduz o MAE macro de B3 para 459,52 bp, mas isso foi
observado **depois** de saber que elas explicavam 61,64% do erro. A exclusão é
outcome-informed e só pode aparecer como diagnóstico. A correlação
intra-companhia de B3 continua negativa (−0,074), e a aparente força sazonal
também desaparece. Nenhum desses números pode virar baseline oficial de uma
nova rodada.

As linhas precisam ser adjudicadas contra a fonte. Erros de unidade são
corrigidos com procedência; fusões, cisões e mudanças econômicas reais
permanecem; casos irreparáveis seguem regra de quarentena congelada antes do
novo teste. Um alarme de 100× não é, por si só, regra de exclusão.

## Gates

| Gate | Estado | Evidência |
|---|---|---|
| G0 — alvo e amostra | **FALHA** | amostra/cobertura passam; integridade de escala falha |
| G1 — point-in-time | **FALHA** | ZIP bruto tem `DT_RECEB`, painel não preserva `DT_RECEB`, `ID_DOC` e vintages |
| G2 — baselines | **PASSA apenas como diagnóstico** | B0–B3 executados, nenhum modelo carregado |
| G3 — intervalos | **FALHA** | não calibrados |
| G4 — utilidade | **FALHA** | limiar acionável e estudo humano ausentes |

O portal oficial informa que os dados ITR/DFP são atualizados com
reapresentações. Usar hoje a maior versão no passado é vazamento. Os campos
necessários existem nos brutos, portanto o bloqueio é de construção do painel,
não de impossibilidade da fonte. [ITR](https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr) ·
[DFP](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp) ·
[dicionário ITR](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/META/meta_itr_cia_aberta_txt.zip)

Setor também falha: 5 de 741 companhias estão preenchidas no painel, embora o
cadastro público já permita ampliar essa cobertura. DFC existe nos ZIPs, mas
não foi carregada na camada atual.

## Debate dos especialistas

### Rodada cega

Os dois pareceres foram independentes, sem acesso a AGENTS, MEMORY, relatórios
anteriores ou artefatos da CAND-04. Ambos auditaram o painel em modo somente
leitura, pesquisaram fontes primárias e disseram **NÃO IMPLEMENTAR ML AGORA**.

- Ciência de Dados preservaria, após reparo, o alvo normalizado pelo ativo T,
  por ser escala-livre e não usar denominador futuro.
- Finanças preferiria lucro trimestral atribuível aos controladores em R$, que
  entra diretamente na planilha do acionista; materialidade seria reportada
  também em bps do patrimônio atribuível, com regime próprio para PL não
  positivo.

Ambos exigiram sazonalidade antes de ML. Isso é consistente com o modelo
clássico de lucro trimestral de Brown–Rozeff e com a evidência de que analistas
podem superar modelos mecânicos por usarem informação mais ampla.
[Brown & Rozeff (1979)](https://doi.org/10.2307/2490312) ·
[Fried & Givoly (1982)](https://doi.org/10.1016/0165-4101(82)90015-5)

O requisito é material: evidência recente encontrou que cerca de 80% das
especificações de ML testadas não superaram analistas. Isso impede tratar
“baseline interno” como sinônimo de “ferramenta melhor para o analista”.
[Campbell, Ham & Lu](https://doi.org/10.1287/mnsc.2024.05808)

### Réplica mediada

Depois de receberem os mesmos números medidos:

- ambos encerraram A como rodada inválida;
- ambos proibiram excluir as 23 linhas pós-hoc;
- ambos distinguiram “experimento rejeitado” de “hipótese econômica não
  refutada”;
- ambos mantiveram ML indecidível e engenharia sem autorização;
- Ciência de Dados priorizaria **A2** após corrigir o dado; Finanças priorizaria
  **B**, lucro dos controladores, deixando A2 como indicador secundário/setorial.

A divergência é substantiva e fica publicada. Lucro em R$ pode reintroduzir
porte e identidade; PL próximo de zero/negativo pode tornar bps instável. Por
outro lado, lucro consolidado inclui não controladores, e ROA universal mistura
economias de bancos, indústrias, seguradoras e holdings. O resultado contaminado
de A não decide essa escolha.

### Tréplica

Os dois responderam **VALIDADO** à formulação conjunta no início deste
relatório. Não houve unanimidade artificial sobre A2 versus B.

## Condição de reabertura

Antes de escolher A2 ou B:

1. preservar `DT_RECEB`, `ID_DOC`, `VERSAO`, hash e todas as versões;
2. congelar features as-of e usar a primeira versão T+1 como gold primário;
3. validar unidade antes de qualquer subtração e reconciliar o 4T;
4. adjudicar todas as 23 linhas e todos os `|y| > 10.000 bp` contra a fonte;
5. distinguir mudança real de perímetro de erro de carga;
6. completar setor e separar regimes econômicos com potência suficiente;
7. congelar um novo teste, sem reutilizar a sensibilidade desta rodada;
8. executar B0–B3 point-in-time e intervalos antes de qualquer challenger;
9. definir materialidade/abstenção e medir o workflow humano;
10. exigir ganho intra-companhia e por trimestre, não apenas agregado.

Se a escolha for A2, o prospective ROA continua como magnitude normalizada e o
4T é estrato próprio. Se a escolha for B, lucro dos controladores precisa ser
reconciliado com consolidado + não controladores, e o denominador de
materialidade precisa de regra explícita quando o patrimônio é não positivo.
São experimentos novos.

## Reprodutibilidade

- pré-registro:
  `resultados/pre_registro_cand04_previsao_fundamentos_2026-08-27.md`;
- auditor: `scripts/auditar_cand04_previsao_fundamentos.py`;
- artefato: `artefatos/cand04/auditoria_baselines.json`;
- contrato: `tests/test_auditar_cand04_previsao_fundamentos.py`;
- reprodução:

```bash
python -m scripts.auditar_cand04_previsao_fundamentos
python -m pytest -q tests/test_auditar_cand04_previsao_fundamentos.py
```

O auditor importa apenas DuckDB, NumPy e pandas. Nenhuma biblioteca ou módulo
de modelo é carregado.
