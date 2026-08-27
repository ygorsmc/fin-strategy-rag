# Validação do candidato C1 — deterioração anormal da lucratividade

**Veredito: REJEITADO por consenso dos dois especialistas e pela replicação
independente da sessão principal.**

O C1 pretendia ordenar uma fila de leitura para o analista, nunca emitir
recomendação:

```text
alvo(t) = 1 se
ROA_ttm(t+4) - ROA_ttm(t) < -1,25 × sd8(Δ anual de ROA_ttm disponível em t)
```

O teste que encerrou o candidato precede qualquer algoritmo: o próprio
normalizador `sd8` separa mecanicamente a taxa do evento que ele ajuda a
definir. Logo, não há ainda um componente aprendido cuja utilidade possa ser
testada de forma honesta.

## Protocolo de isolamento e debate

Dois agentes receberam o mesmo enunciado mínimo, em contextos separados:

- um cientista de dados, responsável por validade estatística, temporalidade,
  baselines e replicação;
- um analista de equity research/value investing, responsável por
  materialidade econômica, utilidade no fluxo de trabalho e interpretação.

Na primeira fase, nenhum recebeu a conclusão ou os números do outro. A sessão
principal mediou apenas objeções anonimizadas; não houve comunicação direta
entre os agentes. Depois de uma réplica e uma tréplica sobre o alcance do
teste T1, ambos chegaram independentemente a **REJEITAR** o C1.

## Régua decisória

O protocolo de seleção de alvo exige simultaneamente:

| Teste | Pergunta | Métrica | Limiar |
|---|---|---:|---:|
| T1 | Algum componente que define mecanicamente o alvo fabrica seu próprio baseline? | amplitude da taxa de evento entre quintis do componente | **< 0,15** |
| T2 | Há sinal temporal ou apenas ordenação persistente de emissor? | AUC agregada − AUC intra-companhia | **< 0,12** |

A correção metodológica desta rodada é importante: T1 não se aplica apenas à
variável que aparece à esquerda da desigualdade. Ele se aplica a **cada
componente que participa da definição mecânica do rótulo**, inclusive o
`sd8` no lado direito.

T2 favorável não compensa T1 reprovado. Os testes detectam defeitos diferentes.

## Medição independente dos agentes

O cientista de dados reconstruiu o alvo diretamente do painel e encontrou:

- 10.117 observações, 417 companhias, 44 trimestres e 1.761 eventos;
- taxa de evento de 30,2% no quintil de menor `sd8` contra 5,5% no maior;
- amplitude de **0,247**, acima do teto de 0,15;
- AUC agregada de `-sd8` de 0,699 e AUC intra-companhia de 0,741;
- precisão top-20 de 0,341 contra prevalência trimestral de 0,182;
- autocorrelação de primeira ordem do rótulo de 0,602.

O analista rejeitou o alvo porque a fila seria dominada por companhias de
baixa volatilidade histórica, não necessariamente por deteriorações
economicamente materiais. Acrescentar piso de materialidade poderia ser uma
hipótese legítima, mas alteraria o alvo e, portanto, criaria o candidato C2.

## Replicação da sessão principal

A sessão principal implementou uma reconstrução separada e auditável em
`scripts/auditar_alvo_c1.py`. Ela usa defasagens trimestrais exatas, não pula
lacunas silenciosamente, e testa três interpretações declaradas da
winsorização:

| Winsorização | n | eventos | amplitude T1 | AUC `-sd8` | AUC intra | precisão top-20 |
|---|---:|---:|---:|---:|---:|---:|
| Δ anual por trimestre (primária) | 8.709 | 1.820 | **0,180** | 0,634 | 0,709 | 0,346 |
| `sd8` por trimestre | 8.709 | 1.812 | **0,181** | 0,635 | 0,710 | 0,343 |
| sem winsorização | 8.709 | 1.815 | **0,183** | 0,636 | 0,710 | 0,346 |

As diferenças de amostra e de magnitude em relação ao agente são preservadas,
não harmonizadas retroativamente. Elas vêm de operacionalizações
independentes de elegibilidade, defasagens exatas e winsorização. A conclusão
é robusta às quatro implementações observadas: **0,180, 0,181, 0,183 e 0,247
são todas maiores que 0,15**.

Na especificação primária, o C1 contém 8.709 observações de 359 companhias,
em 46 trimestres; 1.512 de 10.221 origens elegíveis não têm `t+4` observável.
O resultado completo está em
`artefatos/modelo/auditoria_alvo_c1.json`.

Reprodução:

```bash
.venv/bin/python -m scripts.auditar_alvo_c1 \
  --painel artefatos/cvm_treino.duckdb
```

## Temporalidade e procedência

O painel atual não preserva, para toda observação, a data de recebimento da
versão do formulário nem snapshots históricos completos de setor, categoria
e situação cadastral. Além disso, 16,36% das observações candidatas estão
associadas a formulários com `versao > 1`.

Isso impediria uma afirmação point-in-time publicável mesmo se T1 passasse.
Não é, porém, a causa da rejeição: reconstruir a procedência temporal não
remove o vínculo mecânico entre `sd8` e o rótulo.

## Consenso final

- **Ciência de Dados — REJEITAR.** O C1 falha T1 antes do treinamento; T2
  favorável e lift top-N não resgatam um alvo que fabrica o baseline.
- **Equity Research — REJEITAR.** A ordenação favorece estabilidade histórica,
  não materialidade econômica suficiente para justificar prioridade de
  leitura.
- **Sessão principal — REJEITAR.** A replicação confirma a falha em três
  interpretações de winsorização e mantém visível a divergência numérica.

## Condição de reabertura

O **C1** só reabre se for demonstrado erro computacional ou incompatibilidade
entre a implementação e sua fórmula registrada.

Adicionar piso absoluto/relativo de materialidade, trocar o normalizador ou
redefinir o horizonte produz o **C2**. Esse novo candidato deve ser
pré-registrado e repetir T1 e T2 desde o início; não herda a aprovação antiga
nem os números exploratórios do C1.

Este resultado negativo não implica que ML seja inútil para value investing.
Implica apenas que este rótulo específico não chega ao estágio de comparar
modelos. A curadoria cadastral gratuita da CVM continua necessária para
qualquer C2 e para análises setoriais point-in-time.
