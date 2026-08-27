# Pré-registro — CAND-03: triagem de anomalias contábeis

**Congelado em 2026-08-27, antes de calcular score, carregar modelo ou ver
rótulos de teste.**

## Emenda 1 — consenso pré-análise dos dois revisores

Registrada depois dos pareceres cegos, réplica e tréplica mediadas, ainda sem
modelo, ranking, gold ou outcome calculado. Prevalece onde for mais estrita ou
mais específica que o texto original:

- **E2 continua sendo o alvo primário.** E1 pode ser mais fácil de supervisionar
  depois de recuperar vintages, mas escolhê-lo por conveniência mudaria o
  produto; E1 e E3 permanecem experimentos separados.
- A unidade independente do workflow é o **release**; episódio-raiz é a unidade
  de rótulo e fica agrupado dentro do release. Conta nunca é réplica.
- O piloto shadow começa com 30 releases completos e continua até obter
  ≥30 releases com pelo menos um P1/P2 e rubrica estável, limitado a 150.
  Falhar nesse teto encerra o candidato como não operacionalizável nesta
  rodada. Piloto não entra no teste confirmatório.
- O confirmatório usa
  `N = max(100, N_poder, N_50+)`. `N_poder` vem da diferença pareada de
  tempo por release; `N_50+` usa o limite inferior da prevalência do piloto e
  dá ≥95% de probabilidade de pelo menos 50 releases positivos. O tamanho
  aumenta se a precisão pré-especificada do recall exigir.
- A métrica primária é minutos/itens para alcançar recall congelado antes do
  teste: 100% dos críticos e o piso pré-registrado de P1/P2. nDCG@20 passa a
  corroborativa obrigatória.
- O ganho mínimo de tempo é o maior entre (a) break-even econômico + margem
  congelada e (b) 20% contra o baseline.
- DFC é obrigatória para usar a expressão “qualidade do lucro”. Um E2 estreito
  de prioridade de leitura em BPA/BPP/DRE pode existir sem ela; como os ZIPs
  já contêm DFC, o shadow deve preservá-la desde o primeiro snapshot.
- E2 prospectivo não exige reconstruir vintages históricos: cada novo release,
  features, ranking, mapa e hashes são congelados em `DT_RECEB`. Vintages
  históricos continuam obrigatórios para E1.
- Antes do piloto só se implementam snapshots imutáveis, baseline-**candidato**,
  anotação/adjudicação, métricas e shadow logging. Não se implementa ML e não
  se declara utilidade do determinístico antes da medição humana.

## Pergunta e fronteira do enunciado

Uma camada aprendida consegue ordenar combinações
companhia–trimestre–conta que merecem investigação por um analista melhor que
um baseline determinístico forte, sob o mesmo universo e orçamento de leitura?

A saída é uma fila auditável de **prioridade de leitura**. Não é acusação de
erro, fraude, manipulação, insolvência, deterioração futura nem recomendação de
investimento. Cada alerta precisa exibir companhia, período, demonstrativo,
conta, valor atual, comparáveis usados, motivo do score e origem.

Três estimandos não podem ser misturados:

| ID | Estimando | Verdade necessária |
|---|---|---|
| E1 | erro ou inconsistência no arquivamento | correção confirmada por documento/reapresentação e causa-raiz independente |
| E2 | mudança válida, incomum e prioritária para leitura | julgamento humano sobre ação analítica, com leitura do contexto |
| E3 | fraude, manipulação ou deterioração futura | evento externo datado e observável, disponível só depois do trimestre |

O teste primário é **E2**. E1 é um controle de qualidade de dados e E3 é outro
problema supervisionado; nenhum dos dois pode fornecer positivos a E2.

## Unidade econômica e gold

A unidade candidata é:

```text
(cd_cvm, trimestre, demonstrativo, conta_semantica)
```

Ela só é julgável se preservar conta-pai, descrição, unidade, tipo de período,
valor em T, valor sazonal T−4, ativo ou receita usados para escala e grupo de
comparação. Linhas, razões, janelas e scores derivados da mesma
companhia–trimestre são unidades aninhadas, não réplicas independentes.

Gold ordinal para E2:

| Nota | Ação do analista |
|---|---|
| 0 | ignorar: variação esperada, artefato de escala/período ou sem consequência analítica |
| 1 | conferir: abrir nota/release, reconciliar definição ou entender causa |
| 2 | investigar: atualizar premissa/modelo, confrontar outra demonstração ou escalar revisão |

Nota 2 exige motivo e ação verificáveis. Casos sem contexto, comparável, unidade
ou conta estável são `nao_julgavel`, nunca negativos.

Dois analistas fazem leitura independente e cega para sistema/score; um terceiro
adjudica. O conjunto final deve abranger a fila e a cauda: apenas anotar o
top-N dos sistemas tornaria falso negativo invisível.

## Universo e cronologia

- Treino/desenvolvimento só usa informação cuja primeira data de recepção seja
  anterior ao instante da decisão.
- A maior versão republicada não pode substituir silenciosamente a versão
  disponível naquele instante.
- Splits são por companhia e tempo, com embargo de quatro trimestres; conta ou
  linha não é unidade de split.
- Resultado primário é macro por companhia–trimestre e também por emissor.
- Conta sem mapeamento econômico estável fica fora do comparativo aprendido.
- Setor e tipo de demonstração são controles obrigatórios; instituição
  financeira não é comparável automaticamente a companhia industrial.

Sem data de primeira recepção ou vintages preservados, não se faz afirmação
point-in-time. Um piloto descritivo pode estudar workflow, mas não validar E3.

## Baselines antes do modelo

### B0 — trivial

Valor absoluto da variação sazonal:

```text
abs(valor_T − valor_T−4) / max(abs(ativo_T−4), piso)
```

Contas de fluxo usam trimestre isolado; contas de estoque usam a data de
referência. Sem T−4 comparável, a unidade não recebe score.

### B1 — determinístico forte

Máximo lexicográfico, com pesos congelados e sem ajuste aprendido, entre:

1. quebra de identidade contábil verificável;
2. troca de sinal ou valor impossível;
3. variação sazonal escalada, padronizada por mediana/MAD da própria companhia;
4. desvio robusto contra pares do mesmo setor e conta;
5. persistência por dois períodos e materialidade relativa a ativo, receita ou
   patrimônio líquido.

O baseline deve explicar qual regra disparou e quais observações formaram o
comparável. Regras sem mapeamento semântico ou denominador economicamente
compatível ficam desabilitadas, não imputadas.

### ML — challenger

Só pode ser executado depois dos gates de dados e gold. Recebe exatamente as
mesmas unidades e features disponíveis a B1; na primeira rodada apenas
reordena. O algoritmo e hiperparâmetros são congelados no desenvolvimento.
Autoencoder ou modelo profundo não é permitido no piloto: o tamanho efetivo é
companhia–trimestre, não linha.

## Gates anteriores ao algoritmo

### G0 — observabilidade

Todos:

- data de primeira recepção e versão disponível preservadas para cada unidade;
- conta, período e escala reconciliados;
- DFC disponível se a alegação usar `qualidade do lucro` ou accruals;
- setor preenchido em pelo menos 95% das companhias avaliadas;
- pelo menos 80% das contas materiais do escopo têm conceito estável;
- nenhuma correção conhecida é tratada como observação independente de sua
  causa-raiz.

### G1 — rótulo

Para E1: pelo menos 30 causas-raiz confirmadas, dez emissores e cinco setores.

Para E2: pelo menos 300 unidades julgadas no teste, 30
companhias–trimestres, dez emissores, 30 notas 2 e três notas 2 em cada um de
pelo menos cinco emissores. Krippendorff α ordinal ≥ 0,67, acordo bruto
binário ≥ 80%, acordo positivo ≥ 75% e `nao_julgavel` ≤ 5%.

Para E3: evento externo datado, no mínimo 100 positivos independentes,
primeira-recepção preservada e teste por emissor e tempo. E3 não é executado
se qualquer requisito faltar.

### G2 — utilidade do baseline

B1 precisa obter zero falso negativo crítico observado, recall de nota 2
≥ 0,90, nDCG@20 ≥ 0,80 e procedência perfeita. Se B1 falhar, corrige-se a
extração/rubrica antes de acrescentar ML.

## Métricas e barras de decisão

Primária: macro nDCG@20, ganhos 0/1/3. Secundárias: nDCG@10, Precision@20,
recall de nota 2, `N@R90`, alertas redundantes, procedência e minutos para
encontrar 90% das notas 2. Estudo humano confirmatório é contrabalanceado e usa
analistas que não produziram o gold.

**VALIDAR ML no piloto** exige simultaneamente:

- zero falso negativo crítico adicional e 100% de procedência;
- ΔnDCG@20 ≥ +0,05 e ΔnDCG@10 ≥ +0,10 contra o melhor B0/B1;
- ganho positivo em pelo menos 80% dos emissores e nenhum emissor com perda de
  recall de nota 2;
- `N@R90` ou tempo pelo menos 20% menor, sem queda de acurácia > 5 pp.

**REJEITAR ML** se houver evidência/procedência falsa, falso negativo crítico
adicional, ΔnDCG@20 ≤ 0 com derrota na maioria dos emissores, ou B1 estiver no
teto (nDCG@20 ≥ 0,95) e o ganho aprendido for < 0,03.

Qualquer outro resultado é **INDECIDÍVEL**. Falta de gold, vintages ou estudo
de tempo implica decisão de engenharia **NÃO IMPLEMENTAR ML AGORA**, não prova
de que o candidato é inútil.

## Falsificadores obrigatórios

- tamanho da conta, setor, plano contábil ou companhia domina o score;
- republicação futura fabrica a anomalia ou remove o erro;
- percentual explode por denominador perto de zero;
- conta nova/removida é tratada como zero;
- 4T anual é comparado diretamente a trimestre isolado;
- quebra de identidade vem de arredondamento ou escopo consolidado/individual;
- muitos alertas da mesma causa são contados como muitos positivos;
- o ganho desaparece ao agrupar por companhia–trimestre ou segurar emissores;
- ranking offline melhora sem reduzir leitura ou aumentar achados humanos.

## Estado ex ante

- necessidade econômica: plausível;
- baseline determinístico: obrigatório e possivelmente útil;
- superioridade de ML: **INDECIDÍVEL antes dos gates**;
- nenhum algoritmo deve ser carregado durante a auditoria de precondições.
