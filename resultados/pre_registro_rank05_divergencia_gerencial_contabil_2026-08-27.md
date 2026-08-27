# Pré-registro — rank 5: risco de divergência gerencial × contábil

**Congelado em 2026-08-27 antes de inspecionar o corpus local, contar
reconciliações, abrir rótulos humanos, calcular baselines ou carregar modelo.**

Fonte da posição no ranking:
`resultados/ranking_candidatos_ml_value_investing.md`.

## Pergunta

Uma ferramenta consegue priorizar reconciliações entre métricas gerenciais e
contábeis que exigem revisão humana melhor que regras determinísticas de
completude, consistência, novidade e magnitude, com procedência integral e sem
transformar ajuste legítimo em suspeita de fraude?

A saída é uma **fila de leitura** acompanhada dos motivos observáveis. Não é
parecer jurídico, acusação de irregularidade, previsão de retorno, recomendação
ou substituição do auditor independente.

## Escopos que não podem compartilhar rótulo

### L — LAJIDA/LAJIR

Escopo primário por ter identidade e obrigações explícitas na Resolução CVM
156: base nas demonstrações contábeis, conciliação, descrição/justificativa dos
ajustes e consistência entre períodos.

Inclui LAJIDA, LAJIR e versões identificadas como ajustadas. A conformidade
objetiva com uma identidade não decide sozinha se o ajuste é economicamente
recorrente ou prioritário para o analista.

### K — KPIs setoriais, inclusive bancários

Escopo separado e inicialmente exploratório. Cada KPI precisa de definição,
perímetro, período, unidade e ponte contábil próprios. NPL, custo de crédito,
capital, margem e eficiência não podem ser empilhados como se fossem o mesmo
estimando. Um KPI sem contraparte reconciliável não entra no experimento L.

Nenhum resultado de L é transferido para K apenas por ambos serem “gerenciais”.

## Dois estimandos

### E1 — falha objetiva de reconciliação

Binário e verificável:

- base contábil ou reconciliação obrigatória ausente;
- soma dos itens não fecha no valor divulgado além da tolerância de
  arredondamento declarada;
- período, moeda, unidade ou perímetro incompatível;
- rótulo não identifica corretamente a natureza ajustada;
- mudança de definição sem descrição/reapresentação comparável quando exigida.

E1 é tarefa prioritariamente **determinística**. Um componente aprendido só é
aceitável como extrator de candidatos; a decisão final vem de identidades,
regras e evidência. Se o baseline determinístico resolver E1, não há razão para
substituí-lo por ML.

### E2 — prioridade de revisão humana

Estimando primário para eventual aprendizado. Rubrica ordinal:

| Classe | Definição |
|---|---|
| P0 | reconciliação completa, aritmeticamente consistente, estável e sem questão material para revisão |
| P1 | diferença ou mudança material, mas claramente explicada; leitura rotineira |
| P2 | ambiguidade, item novo/recorrente tratado como extraordinário, assimetria de ajustes, mudança de definição ou ponte incompleta que pode alterar a leitura econômica |
| P3 | falha objetiva crítica de E1 ou impossibilidade de reconciliar o número divulgado com a evidência disponível |

O endpoint binário para probabilidade é `P2 ou P3`. A ordenação preserva P3
acima de P2. Magnitude da diferença é feature/baseline, nunca o próprio gold.

Persistência futura, qualidade do lucro, sanção regulatória e retorno são
outcomes distintos e não validam E2 por procuração.

## Unidade e gold

Unidade atômica: `emissor × release × versão × métrica × período`. As unidades
atômicas do mesmo release são aninhadas; o **release** é a unidade independente
do workflow, split, bootstrap e teste de hipótese.

Gold:

1. dois leitores independentes com experiência contábil/financeira;
2. leitura completa do release e das demonstrações que sustentam a ponte;
3. spans muitos-para-muitos para valor gerencial, base contábil, itens de
   reconciliação, unidade, período, definição e justificativa;
4. E1 marcado campo a campo; E2 marcado pela rubrica P0–P3;
5. toda discordância adjudicada e motivo preservado;
6. nenhuma anotação inferida somente de uma lista produzida pelo sistema.

Pooling pode descobrir candidatos no piloto, mas a avaliação final exige
censo completo dos documentos de teste. Item não anotado não vira negativo.

## Relógio point-in-time

- instante `t0`: primeira publicação pública da versão analisada;
- features: somente documentos e versões disponíveis até `t0`;
- mudanças posteriores servem a análises secundárias, nunca alteram o gold
  retrospectivamente sem registro;
- hash, URL/ID do documento, versão e data de recebimento/publicação são
  obrigatórios;
- tabelas precisam conservar cabeçalho, unidade, período e notas.

## Baselines anteriores ao modelo

Todos produzem score e explicação no mesmo universo:

- **B0 — magnitude:** diferença absoluta e relativa entre medida gerencial e
  contraparte contábil, sem julgamento textual;
- **B1 — regras objetivas:** presença da ponte, fechamento aritmético, unidade,
  período, rótulo, consistência e mudança de definição;
- **B2 — novidade/recorrência:** item novo, item repetido apesar de chamado não
  recorrente, inclusão apenas de perdas ou apenas de ganhos e mudança de
  composição;
- **B3 — determinístico combinado:** P3 objetivo primeiro; depois B1, B2 e B0
  em ordem congelada, sem peso aprendido;
- **B4 — leitura integral:** todos os itens, referência de segurança e tempo.

O challenger compete com o melhor B0–B3. B4 não é modelo de ranking: mede o
custo e o recall da leitura completa.

## Amostra e split

Piloto de gold: começar com 30 releases completos e continuar até obter pelo
menos 30 releases com P2/P3 e estabilidade da rubrica, com teto de 150. Se o
teto não produzir 30 positivos independentes, o experimento aprendido é
operacionalmente inviável nesta rodada.

Confirmatório:

```text
N = max(100 releases, N_poder, N_50+)
```

onde `N_poder` vem do efeito mínimo economicamente útil contra B3 e `N_50+` é o
tamanho necessário para ao menos 50 releases P2/P3 sob prevalência conservadora
do piloto. Exigir pelo menos dez emissores no total e generalização temporal e
por emissor.

Split:

- desenvolvimento, embargo/calibração e teste final por data de publicação;
- nenhum release, versão ou tabela compartilhado entre partições;
- avaliação separada em emissores vistos e holdout de emissores;
- nenhum ajuste de rubrica, threshold, regra ou feature depois de abrir o teste.

## Métricas

### Segurança e ranking

- recall P3 = 1,00;
- recall P2/P3 e precisão da fila;
- `N@R100(P3)` e `N@R90(P2/P3)`;
- nDCG@10 e nDCG@20;
- AUPRC, Brier e calibração da probabilidade P2/P3;
- desempenho por emissor, período, métrica, magnitude e origem arquivada/
  derivada;
- ganho agregado e dentro do emissor.

### Workflow

Primária operacional: minutos e itens lidos para atingir o mesmo recall crítico
da leitura completa. Estudo crossover, contrabalanceado e cego ao método mede:

- tempo;
- achados P2/P3;
- falso negativo crítico;
- correções de classificação pelo analista;
- confiança e justificativa com procedência.

Item, linha ou ajuste não é réplica independente.

## Gates

| Gate | Aprovação |
|---|---|
| G0 — observabilidade | documentos contêm métrica, base e ponte suficientes; ausência é medida, não preenchida |
| G1 — point-in-time | 100% das unidades com documento, versão, hash e data reproduzíveis |
| G2 — gold | dupla leitura completa; concordância ponderada ≥0,70; 100% das discordâncias adjudicadas |
| G3 — baseline | B0–B4 executados antes do challenger; procedência determinística perfeita |
| G4 — amostra | piloto/confirmatório e diversidade de emissor passam as barras acima |
| G5 — incrementalidade | learned supera o melhor B0–B3 nas barras abaixo |
| G6 — workflow | ganho humano pareado sem perda de segurança |

## Barras de decisão

### VALIDAR o challenger no piloto

Todos:

- recall P3 = 1,00 e recall P2/P3 ≥0,90;
- redução de `N@R90(P2/P3)` ≥20% contra B3;
- ΔnDCG@20 ≥+0,05 e IC95% clusterizado favorável;
- ganho em ≥75% dos releases finais e sem depender de identidade do emissor;
- probabilidade calibrada e procedência de 100%;
- estudo humano: tempo −20% sem piorar achados/FN, ou mais achados com tempo
  não inferior, com IC pareado favorável.

Validação do piloto autoriza confirmatório, não deploy.

### REJEITAR o componente aprendido

Qualquer um:

- B1/B2/B3 resolve a tarefa no mesmo recall com custo igual ou menor;
- magnitude B0 explica todo o ganho;
- learned perde P3 ou não melhora `N@R90`/nDCG;
- ganho <3% e sem ganho humano;
- melhora agregada desaparece dentro do emissor ou no holdout;
- rótulos dependem de julgamento regulatório não reproduzível;
- explicação não reconcilia numericamente com a evidência.

### INDECIDÍVEL

Faltam documentos, pontes, gold, positivos independentes, point-in-time,
potência ou estudo humano. Nesse estado, não implementar ML agora.

## Falsificadores

- diferença legítima e bem explicada é tratada como risco apenas por ser grande;
- magnitude, número de itens ou extensão da tabela já dominam o modelo;
- “não recorrente” é julgado sem histórico suficiente;
- alteração de perímetro é confundida com alteração de definição;
- um item aparece em treino e teste por versões do mesmo release;
- pooling faz item não julgado virar negativo;
- regra brasileira de LAJIDA é aplicada a KPI bancário sem identidade própria;
- conformidade objetiva é chamada de fraude ou qualidade econômica;
- ganho offline não reduz leitura nem aumenta achados humanos;
- o sistema encontra apenas estilo permanente do emissor, não episódios.

## Referências normativas usadas para congelar o desenho

- [Resolução CVM 156/2022](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/100/resol156.pdf)
- [SEC — Non-GAAP Financial Measures C&DIs](https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/non-gaap-financial-measures)
- [ESMA — Guidelines on Alternative Performance Measures](https://www.esma.europa.eu/document/esma-guidelines-alternative-performance-measures)
- [IFRS 18 — management-defined performance measures](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-18-presentation-and-disclosure-in-financial-statements/)

## Estado ex ante

- necessidade do analista: forte;
- determinístico regulatório: provavelmente difícil de superar em E1;
- tarefa aprendível em E2: plausível, ainda não demonstrada;
- disponibilidade local e prevalência: desconhecidas;
- componente aprendido: **INDECIDÍVEL**;
- nenhum modelo pode ser carregado antes de G0–G4.
