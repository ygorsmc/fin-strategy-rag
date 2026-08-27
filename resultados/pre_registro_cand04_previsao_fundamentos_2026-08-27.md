# Pré-registro — CAND-04: previsão interpretável de fundamentos

**Congelado em 2026-08-27 antes de calcular baselines, ajustar modelo ou abrir
resultado de teste.**

## Pergunta

Usando apenas informação disponível quando o release T foi recebido, um
componente aprendido prevê o fundamento de T+1 melhor que baselines simples de
um analista, com erro e intervalo suficientemente pequenos para mudar a revisão
de premissas?

A saída não é preço-alvo, retorno ou recomendação. É uma previsão auditável de
fundamento, com unidade, horizonte, intervalo, baseline, principais
contribuições e procedência.

## Estimando primário

Prever o **ROA trimestral de T+1 sobre o ativo conhecido em T**, em pontos-base:

```text
y(i,t+1) = 10.000 × lucro_liquido_consolidado(i,t+1) / ativo_total(i,t)
```

O denominador é conhecido na origem e comum a modelo e baselines. O nível em
reais continua sendo publicado como derivado:

```text
lucro_previsto(i,t+1) = y_previsto / 10.000 × ativo_total(i,t)
```

Não usar ativo de T+1. Não converter o alvo em classe, evento ou ranking. O alvo
é magnitude; prejuízo é somente a região `y < 0`.

Unidade independente para split e incerteza: release companhia–trimestre.
Features/contas da mesma unidade são aninhadas, não réplicas.

## Horizonte e disponibilidade

- instante de previsão: `DT_RECEB` da versão disponível de T;
- horizonte: primeiro release trimestral consecutivo da mesma companhia;
- target conhecido apenas no `DT_RECEB` de T+1;
- versões recebidas depois do instante de previsão nunca alteram features
  retrospectivamente;
- observação sem T+1 consecutivo é censurada, nunca recebe target inventado;
- exercício não calendário usa datas de início/fim e recebimento, não o texto
  `1T/2T/3T/4T` isoladamente.

## Baselines obrigatórios

Todos usam exatamente as mesmas linhas do challenger.

| ID | Previsão do lucro de T+1 |
|---|---|
| B0 | lucro de T — persistência |
| B1 | lucro de T−3 — mesmo trimestre fiscal do ano anterior |
| B2 | mediana dos lucros T, T−1, T−2 e T−3 |
| B3 | mediana de B0, B1 e B2, pesos fixos |

Cada previsão é dividida pelo mesmo `ativo_total(i,t)`. “ML venceu” significa
vencer o **melhor** B0–B3 no teste, nunca um baseline escolhido depois.

Antes do challenger, medir:

- cobertura de cada baseline;
- erro por companhia, trimestre, setor e quintil de ativo;
- decomposição agregada × intra-companhia;
- sensibilidade a lucro/ativo próximo de zero e extremos;
- se a sazonalidade só identifica companhia ou prevê mudança temporal.

## Dados e população

- demonstrativo consolidado, trimestre isolado ou 4T derivado pela mesma regra;
- `ativo_total > 0` e lucro/ativo finitos;
- pelo menos oito releases anteriores para entrar na avaliação;
- setor e plano contábil preservados; instituições financeiras reportadas
  separadamente;
- nenhum preenchimento de target ou de futuro ausente;
- correções/reapresentações registradas, nunca aplicadas antes de `DT_RECEB`.

O treino pode usar todas as companhias elegíveis, mas o resultado deve ser
publicado também:

1. macro por companhia;
2. apenas companhias vistas no treino;
3. holdout de emissores nunca vistos;
4. instituições financeiras e não financeiras separadas.

## Split

Walk-forward expansivo por `DT_RECEB`, com purga de um horizonte entre
desenvolvimento/validação/teste. Nenhuma unidade T pode entrar no treino antes
de seu target T+1 estar disponível. Hiperparâmetros, features e intervalos são
ajustados somente em desenvolvimento/validação.

O teste final é formado pelos últimos oito trimestres completos, desde que
tenha ao menos 100 companhias e 500 releases elegíveis. Resultado usa bootstrap
por companhia e release; linha contábil não entra como unidade de reamostragem.

## Métricas

Primária: MAE em pontos-base, macro por companhia.

Obrigatórias:

- mediana do erro absoluto e RMSE em pontos-base;
- erro absoluto em R$ derivado, somente como diagnóstico por porte;
- viés assinado;
- acerto da direção `y(t+1) − y(t)`;
- erro e cobertura em trimestres lucrativos/prejuízo;
- cobertura e largura de intervalos de 50%, 80% e 95%;
- calibração do intervalo por setor/porte;
- ganho por fold e companhia contra o melhor baseline;
- tempo para revisar premissas em estudo humano.

Uma previsão pontual sem intervalo calibrado reprova o produto mesmo que o MAE
melhore.

## Gates anteriores ao modelo

### G0 — alvo

- fórmula e componentes reproduzíveis;
- nenhum componente futuro no denominador;
- amplitude de target e erro reportada por ativo, setor e companhia;
- baseline sazonal calculável em pelo menos 80% do teste;
- nenhuma conclusão agregada sem métrica intra-companhia.

### G1 — point-in-time

100% das features e versões ligadas a `ID_DOC`, `VERSAO` e `DT_RECEB`. Painel
as-restated pode gerar diagnóstico exploratório, nunca confirmação ou deploy.

### G2 — baseline

B0–B3 executados e congelados antes do challenger. Se B3 ou B1 estiver no teto
operacional definido pelo analista, não carregar ML.

### G3 — intervalo

Método de intervalo congelado na validação. No teste, cobertura 80% entre
75%–85% e cobertura 95% entre 91%–98%, sem falha grave em porte/setor.

### G4 — utilidade

Definir antes do teste quanto erro em pontos-base ou R$ faz o analista mudar
premissa e qual economia de tempo paga manutenção. Métrica offline sem ação
humana não valida o produto.

## Barras de decisão

### VALIDAR o challenger no piloto

Todos:

- redução de MAE macro ≥10% contra o melhor B0–B3;
- limite inferior do IC95 clusterizado do ganho >0;
- ganho em ≥75% dos folds finais e ≥60% das companhias elegíveis;
- nenhum setor/porte material piora ≥10%;
- intervalos passam G3 e procedência é 100%;
- direção não piora;
- estudo humano mostra redução ≥20% de tempo ou revisão materialmente melhor,
  sem aumento de erro.

### REJEITAR o componente aprendido

Qualquer um:

- MAE não melhora ou perde na maioria dos folds;
- ganho de MAE <3% e sem ganho humano;
- melhora agregada desaparece intra-companhia;
- intervalo é sistematicamente mal calibrado;
- desempenho depende de versão futura, porte ou identidade da companhia;
- baseline simples já está no teto e o learned só acrescenta manutenção.

### INDECIDÍVEL

Ausência de painel point-in-time, setor, intervalos, potência, estudo humano ou
qualquer resultado entre as barras. Nesse estado, não implementar ML agora.

## Falsificadores

- alvo ou erro é dominado por escala;
- `ativo_total(i,t)` fabrica ordenação previsível;
- 4T derivado e trimestre isolado são misturados;
- mesmo trimestre do ano anterior cruza exercício fiscal incompatível;
- companhias que somem recebem target negativo/zero;
- versão final revisa silenciosamente o passado;
- resultado agregado vem apenas de diferenças permanentes entre emissores;
- intervalo estreita em média e falha justamente nos eventos críticos;
- ganho estatístico não muda nenhuma premissa do analista.

## Estado ex ante

- necessidade econômica: plausível;
- baseline sazonal: provavelmente forte, ainda não medido;
- alvo magnitude: novo candidato, não herda resultados de alvos binários;
- superioridade de ML: **INDECIDÍVEL**;
- nenhum modelo deve ser carregado antes de G0–G2.
