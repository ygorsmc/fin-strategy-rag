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

## Fontes e cadeia de procedência

Esta seção é o ponto de entrada para outro agente. Ela separa **fonte pública**,
**transformação local**, **resultado reproduzível** e **parecer de agente**. Os
quatro níveis não são intercambiáveis.

### 1. Fonte pública primária

Os fatos contábeis vêm exclusivamente do Portal de Dados Abertos da CVM:

- [ITR — Formulário de Informações Trimestrais](https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr);
- [DFP — Demonstrações Financeiras Padronizadas](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp);
- diretórios anuais usados pelo downloader:
  [`ITR/DADOS`](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/) e
  [`DFP/DADOS`](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/).

As páginas oficiais informam que os conjuntos recebem atualização semanal e
eventuais reapresentações. Por isso “baixar hoje” não necessariamente reconstrói
o que estava publicado na data histórica de cada previsão.

O snapshot efetivamente usado está pinado em
`corpus/cvm/manifesto_cvm.csv`: uma linha por conjunto × ano, com URL, data de
download, tamanho e SHA-256. O manifesto cobre ITR 2011–2026 e DFP 2011–2025;
seu SHA-256 no momento desta validação era:

```text
8446d06b5d7df3eef515ea55b165f5555bbd70630be001ca1ef7e2a5c8b1b610
```

O downloader que constrói e verifica esse manifesto é
`scripts/baixar_cvm.py`. Os ZIPs vivem em `corpus/cvm/`; o manifesto é a fonte
auditável para detectar republicação posterior do portal.

### 2. Construção do painel usado pelo C1

O painel foi construído por:

```bash
python -m scripts.construir_painel_cvm \
  --anos 2011-2026 \
  --destino artefatos/cvm_treino.duckdb
```

O construtor extrai somente demonstrações consolidadas **DRE, BPA e BPP** dos
ZIPs ITR/DFP. A cadeia de transformação é:

```text
ZIPs CVM
  → scripts/baixar_cvm.py
  → corpus/cvm/manifesto_cvm.csv
  → scripts/construir_painel_cvm.py
  → src/dados_estruturados.py::carregar_painel
  → fatos_contabeis
  → fatos_semanticos
  → indicadores
  → scripts/auditar_alvo_c1.py
  → artefatos/modelo/auditoria_alvo_c1.json
```

Regras materiais da carga em `src/dados_estruturados.py`:

1. mantém `ORDEM_EXERC='ÚLTIMO'`, moeda real e linhas tipáveis;
2. conserva apenas a maior `VERSAO` por companhia × demonstrativo × data de
   referência;
3. converte `ESCALA_MOEDA` para reais;
4. deriva o trimestre pelo intervalo do exercício, não pela ordenação textual;
5. deriva o 4T de contas de fluxo por DFP anual menos ITR acumulado de nove
   meses, marcando `origem='derivado'`;
6. resolve lucro e ativo pela camada semântica; `cd_conta` isolado não é chave
   de significado.

O arquivo exato lido pelo auditor tinha 194.260.992 bytes e SHA-256:

```text
74aa28e86dfcf5d2eab50b1de62851100baffd5936ea60fff585908ebf108192
```

Seu esquema relevante era:

| Tabela | Colunas consumidas direta ou indiretamente |
|---|---|
| `indicadores` | `cd_cvm`, `trimestre`, `lucro_liquido_consolidado`, `ativo_total` |
| `companhias` | `cd_cvm`, `is_banco` |
| `fatos_contabeis` | `versao_documento`, além da procedência que alimenta `indicadores` |

No snapshot, `indicadores` tinha 23.346 companhia–trimestres e 741 companhias
antes dos filtros próprios do C1.

### 3. Especificação computacional exata

A implementação normativa desta rodada é
`scripts/auditar_alvo_c1.py`, SHA-256:

```text
0a73bae1f16acb90b336560e7bb5b076fe810af7deb9940ac13feee22daffba9
```

Constantes congeladas no script:

| Parâmetro | Valor |
|---|---:|
| `k` | 1,25 |
| janela do `sd8` | 8 variações anuais |
| mínimo para o `sd8` | 6 observações |
| corte de ativo | R$ 1 bilhão |
| limiar de reprovação T1 | 0,15 |
| fila diagnóstica | top 20 por trimestre |

População de entrada:

```sql
SELECT i.cd_cvm, i.trimestre,
       i.lucro_liquido_consolidado AS lucro,
       i.ativo_total, c.is_banco
FROM indicadores AS i
JOIN companhias AS c USING (cd_cvm)
WHERE i.lucro_liquido_consolidado IS NOT NULL
  AND i.ativo_total IS NOT NULL
  AND NOT c.is_banco
```

Depois do SQL, o script executa, nesta ordem:

1. converte `trimestre` em inteiro monotônico por
   `src.normalizacao.ordinal_trimestre`; todas as defasagens são joins exatos,
   portanto trimestre ausente não vira “linha anterior”;
2. calcula
   `ROA_ttm(t) = soma(lucro[t..t-3]) / média(ativo[t], ativo[t-4])`;
3. calcula a variação anual
   `delta_roa_anual(t) = ROA_ttm(t) - ROA_ttm(t-4)`;
4. na especificação primária, winsoriza `delta_roa_anual` nos percentis 1% e
   99% **dentro de cada trimestre**;
5. por companhia, reindexa todos os trimestres entre mínimo e máximo, deixando
   lacunas como `NaN`, e calcula desvio-padrão amostral (`ddof=1`) móvel de oito
   variações, com mínimo de seis;
6. mantém `ativo_total > R$ 1 bi`, `sd8` finito e positivo;
7. junta `ROA_ttm(t+4)` por chave exata e censura quem não tem futuro
   observável;
8. cria o rótulo
   `ROA_ttm(t+4)-ROA_ttm(t) < -1,25*sd8(t)`;
9. usa o adversário trivial `escore=-sd8`;
10. forma quintis de `sd8` por `pandas.qcut` **sobre a amostra inteira**, não
    dentro de cada trimestre, e define T1 como `max(taxa)-min(taxa)`;
11. calcula AUC agregada com `sklearn.metrics.roc_auc_score`;
12. calcula AUC intra-companhia por pares positivo–negativo apenas dentro do
    mesmo `cd_cvm`, ponderados pelo número de pares, em
    `src.modelo.treinar.auc_within_companhia`;
13. calcula a precisão top-20 em cada trimestre e tira a média simples entre
    trimestres.

As duas sensibilidades mudam somente a winsorização: uma winsoriza o próprio
`sd8` por trimestre; a outra não winsoriza. Todo o restante permanece igual.

**Limitação de população:** `is_banco` é inferido pelo plano de contas e pela
lista dos cinco bancos do corpus; ele não equivale a uma classificação setorial
histórica completa. Pode excluir holdings/companhias financeiras por heurística
e não usa ainda `SETOR_ATIV` do cadastro aberto da CVM. Isso limita a população,
mas não explica a reprovação mecânica observada nas três sensibilidades.

### 4. Mapa dos achados para suas fontes

| Achado no relatório | Fonte primária no repositório | Status |
|---|---|---|
| 8.709 observações, 359 companhias, 46 trimestres, 1.820 eventos e 1.512 censuradas | `artefatos/modelo/auditoria_alvo_c1.json` → `sensibilidades.delta_por_trimestre` | reproduzível |
| T1 = 0,180; AUC agregada 0,634; AUC intra 0,709; precisão top-20 0,346 | mesmo bloco do JSON acima | reproduzível |
| T1 = 0,181 e 0,183 nas sensibilidades | blocos `sd_por_trimestre` e `nenhuma` do mesmo JSON | reproduzível |
| joins trimestrais exatos e definição do rótulo | `scripts/auditar_alvo_c1.py` | reproduzível e coberto por teste |
| AUC intra-companhia | `src/modelo/treinar.py::auc_within_companhia` | reproduzível |
| 16,36% de exposição a reapresentação | `src/modelo/construir_painel.py::medir_republicacao` e `artefatos/modelo/metricas.json` → `analises.vies_as_restated` | reproduzível, mas mede o painel supervisionado geral, não a subamostra C1 |
| T1 <0,15 e T2 <0,12 | protocolo interno congelado em `resultados/debate_alvo_ml_2026-08-26.md` e `AGENTS.md` §3.7 | regra de decisão do projeto, não padrão externo |
| implementação cega: T1 0,247 e demais números da seção seguinte | resposta do agente de Ciência de Dados durante a sessão de debate; somente o resumo foi preservado neste arquivo | replicação independente, **não reproduzível a partir do repositório** |
| interpretação econômica e consenso | pareceres isolados e réplica/tréplica mediados; síntese preservada neste relatório e em `AGENTS.md` §3.7 | trilha deliberativa, não cálculo |

O artefato reproduzível tinha SHA-256:

```text
afb7b0633b638631224ac45ee7ac3ac6433a13921fd295c1e6a1a8f543802578
```

Se qualquer um dos quatro hashes desta seção divergir, o próximo agente deve
publicar a divergência e tratar a execução como nova medição, não como réplica
bit a bit.

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

**Procedência desta subseção:** os números abaixo vieram da implementação cega
do agente de Ciência de Dados. O código temporário, a amostra linha a linha e o
JSON bruto desse agente não foram versionados. Portanto, estes números são
contraprova independente e explicam a divergência entre operacionalizações,
mas **não devem ser a fonte primária de reprodução**. Para reprodução e handoff,
use a sessão principal, o script e o artefato identificados acima.

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
`artefatos/modelo/auditoria_alvo_c1.json`; o contrato mínimo do auditor está em
`tests/test_auditar_alvo_c1.py`. Os testes travam que uma defasagem exata não
pule trimestre ausente e que T1 reprove/passe nos dois lados do limiar.

Reprodução sem sobrescrever o artefato publicado:

```bash
uv run --with-requirements requirements-modelo.txt \
  python -m scripts.auditar_alvo_c1 \
    --painel artefatos/cvm_treino.duckdb \
    --saida /tmp/auditoria_alvo_c1_repro.json

uv run --with-requirements requirements-modelo.txt \
  python -m pytest -q tests/test_auditar_alvo_c1.py

sha256sum artefatos/cvm_treino.duckdb \
  scripts/auditar_alvo_c1.py \
  artefatos/modelo/auditoria_alvo_c1.json \
  corpus/cvm/manifesto_cvm.csv
```

Para comparar o JSON regenerado sem depender de formatação:

```bash
uv run --with-requirements requirements-modelo.txt python -c \
  "import json; a=json.load(open('/tmp/auditoria_alvo_c1_repro.json')); b=json.load(open('artefatos/modelo/auditoria_alvo_c1.json')); assert a == b; print('réplica idêntica')"
```

## Temporalidade e procedência

O painel atual não preserva, para toda observação, a data de recebimento da
versão do formulário nem snapshots históricos completos de setor, categoria
e situação cadastral. O bloco `analises.vies_as_restated` de
`artefatos/modelo/metricas.json`, calculado por
`src.modelo.construir_painel.medir_republicacao`, mede 3.741 de 22.862
observações (**16,36%**) com `versao_documento > 1`: 16,81% nos trimestres de
prejuízo e 16,14% nos de lucro.

Essa taxa mede o **painel supervisionado geral do modelo de prejuízo**, não as
8.709 observações finais do C1. Para o C1, a evidência reproduzível é mais
limitada: o DuckDB conserva apenas a maior versão e não contém a data da
primeira recepção; logo a exposição existe, mas sua fração exata dentro da
amostra C1 não foi calculada nesta rodada.

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
