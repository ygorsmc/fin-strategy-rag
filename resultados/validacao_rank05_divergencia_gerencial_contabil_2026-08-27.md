# Validação do rank 5 — divergência gerencial × contábil

## Veredito

Os dois especialistas, isolados na primeira opinião e nas réplicas, chegaram ao
mesmo resultado depois da auditoria reproduzível e da tréplica mediada:

1. **Rank 5: INDECIDÍVEL.**
2. **Implementar ou treinar ML agora: NÃO.**
3. **Autorizar extrator determinístico + construção do gold para K1: SIM.**

O braço primário L, LAJIDA/LAJIR, é encerrado **neste corpus** porque não há uma
única ocorrência elegível. Isso não refuta sua utilidade em outro universo. O
braço bancário K existe documentalmente, mas precisa começar como candidato
independente e com ontologia própria.

O primeiro K será:

> **K1 — ponte entre lucro líquido contábil e lucro líquido
> ajustado/recorrente, com os itens de ajuste individualizados.**

## O que foi pré-registrado

Antes de abrir o corpus, contar páginas ou carregar qualquer modelo, foram
congelados em
`resultados/pre_registro_rank05_divergencia_gerencial_contabil_2026-08-27.md`:

- unidade atômica: `emissor × release × versão × métrica × período`;
- release como unidade independente de split, bootstrap e workflow;
- E1 objetivo e determinístico, separado de E2 — prioridade humana P0–P3;
- magnitude como baseline, nunca como rótulo;
- dois leitores completos, adjudicação e spans muitos-para-muitos;
- B0 magnitude, B1 regras, B2 novidade/recorrência, B3 combinado e B4 leitura
  integral antes de qualquer challenger;
- piloto com no mínimo 30 releases e continuidade até pelo menos 30 P2/P3;
- confirmatório `N=max(100,N_poder,N_50+)` e no mínimo dez emissores;
- concordância ponderada mínima de 0,70;
- nenhum modelo antes de G0–G4.

O ranking normativo está em
`resultados/ranking_candidatos_ml_value_investing.md`.

## Medição do corpus congelado

O auditor leu os caches OCR dos 20 releases, sem embeddings, LLM ou modelo:

| Evidência | Documentos | Emissores | Páginas |
|---|---:|---:|---:|
| Corpus | 20 | 5 | 2.790 |
| LAJIDA/LAJIR/EBITDA/EBIT como palavra inteira | **0** | **0** | **0** |
| Ponte numérica com colunas explícitas “contábil” e “gerencial” | **12** | **3** | **16** |
| Ponte numérica geral de resultado ajustado | **20** | **5** | **31** |
| Algum KPI bancário | **20** | **5** | — |

A ponte geral cobre quatro releases de cada um dos cinco emissores. Ela inclui:

- `contábil → ajustes → gerencial`;
- `contábil → itens não recorrentes → ajustado`;
- `lucro líquido ajustado + itens extraordinários → lucro líquido`,
  preservando a orientação publicada.

Essas contagens demonstram **observabilidade**, não gold. “20/20” não informa
precisão ou recall do detector, não revela quantos casos seriam P2/P3 e não
autoriza chamar uma ponte de divergência, erro ou manipulação.

## Gates

| Gate | Resultado | Razão |
|---|---|---|
| G0-L — observabilidade de LAJIDA/LAJIR | **reprovado** | 0/20 |
| G0-K — observabilidade de ponte bancária | **aprovado** | 20/20 candidatos |
| G1 — point-in-time | **reprovado** | há URL, hash e data de coleta; faltam data original de publicação e versão/vintage |
| G2 — gold duplo adjudicado | **reprovado** | inexistente |
| G3 — baselines pontuados no gold | **reprovado** | sem gold não há score honesto |
| G4 — amostra | **reprovado** | 20 releases e 5 emissores, abaixo de 30 e 10; positivos desconhecidos |
| G5 — incrementalidade de ML | não executado | gate anterior falhou |
| G6 — workflow humano | não executado | não há estudo de tempo |

Páginas, linhas e itens continuam aninhados nos mesmos 20 releases; não viram
réplicas independentes. Data de coleta reproduz o snapshot obtido pelo projeto,
mas não prova o que estava disponível ao analista no instante da primeira
publicação.

## Por que K1 é a primeira família

Os dois especialistas escolheram K1 independentemente. Ela tem:

1. âncora contábil mais estável que NPL, eficiência, margem financeira, ROE ou
   capital prudencial;
2. identidade aditiva mecanicamente verificável;
3. ocorrência candidata nos cinco emissores;
4. separação clara entre extração e julgamento econômico;
5. proximidade com o workflow de normalização de lucro em valuation.

A equação deve ser armazenada na orientação literal da publicação e também em
forma normalizada:

```text
lucro líquido contábil + soma(ajustes) = lucro líquido ajustado/recorrente
```

Campos mínimos: emissor; escopo; trimestre isolado/acumulado; moeda; unidade;
lucro atribuível ou consolidado; valores de origem e destino; cada item, sinal
e efeito fiscal/não controladores quando aplicável; rótulo literal; categoria
normalizada; justificativa; recorrência; versão da definição; resíduo;
página/span; estado `extraído`, `verificado` ou `ambíguo`.

“Extraordinário” ou “não recorrente” é rótulo declarado pelo emissor, não
verdade econômica produzida pelo extrator.

## Base normativa e limites de transferência

A [Resolução CVM 156](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/100/resol156.pdf)
define regras específicas para LAJIDA/LAJIR: base nas demonstrações,
reconciliação, identificação de versão ajustada, descrição, justificativa e
consistência. Ela **não** transforma lucro ajustado bancário em LAJIDA nem
fornece automaticamente o gold de K1.

Como referências metodológicas, não como normas aplicáveis ao corpus, as
[C&DIs da SEC sobre non-GAAP](https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/non-gaap-financial-measures)
alertam para recorrência, inconsistência, assimetria de ganhos/perdas, rótulos
e medidas individualmente adaptadas. As
[diretrizes de APM da ESMA](https://www.esma.europa.eu/document/esma-guidelines-alternative-performance-measures)
tratam de definição, componentes, reconciliação e consistência.

A [IFRS 18](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-18-presentation-and-disclosure-in-financial-statements/)
torna medidas de desempenho definidas pela administração ainda mais relevantes,
mas é obrigatória para períodos anuais iniciados em ou após 1º de janeiro de
2027, salvo adoção antecipada. Não pode ser usada como rótulo retroativo de
conformidade para estes releases.

## Debate isolado e consenso

Os agentes não receberam arquivos locais nem conclusões um do outro. A sessão
principal forneceu a ambos a mesma medição e mediou as objeções.

| Pergunta | Ciência de Dados | Mercado Financeiro |
|---|---|---|
| Rank 5 agora | **INDECIDÍVEL** | **INDECIDÍVEL** |
| Implementar ML agora | **NÃO** | **NÃO** |
| Autorizar K1 determinístico + gold | **SIM** | **SIM** |
| Primeira família | lucro líquido contábil → ajustado | lucro líquido contábil → ajustado |
| 20/20 valida ML? | **NÃO** | **NÃO** |

Na tréplica, ambos aceitaram explicitamente:

- zero LAJIDA encerra L apenas neste projeto, sem validade externa;
- prevalece o limiar pré-registrado de concordância ≥0,70; 0,80 pode ser
  apenas sensibilidade secundária;
- 20/20 aprova somente G0-K; G1–G4 permanecem reprovados.

## O que está autorizado agora

- inventário das 31 páginas candidatas, com spans e tabela-fonte;
- recuperação de data original, versão e eventual republicação;
- ontologia estreita de K1;
- extrator determinístico de valores, sinais, unidade, período, escopo e itens;
- fechamento aritmético com abstenção em tabela ambígua;
- baselines B0–B3 transparentes;
- formulário e protocolo de dupla leitura, adjudicação e estudo de tempo;
- expansão do corpus e construção do gold.

Ainda não estão autorizados classificador/ranker aprendido, uso da saída do
detector como rótulo, alegação de utilidade ou inferência de fraude/infração.

## Reabertura do ML

O experimento aprendido só reabre quando **todos** forem verdadeiros:

1. pelo menos 30 releases e continuidade até pelo menos 30 P2/P3 adjudicados;
2. K1 com rubrica própria e censo completo do conjunto avaliado;
3. dois leitores independentes, concordância ponderada ≥0,70 e 100% das
   discordâncias adjudicadas;
4. data original e vintage resolvidos para 100% das features temporais;
5. precisão/recall do extrator conhecidos;
6. B0–B4 executados e congelados;
7. split temporal e por emissor sem compartilhamento de release, versão ou
   tabela.

Qualquer confirmação posterior exige pelo menos 100 releases, dez emissores,
teste temporal intocado e ganho sobre B3 nos limites pré-registrados: recall P3
= 1,00; recall P2/P3 ≥0,90; `N@R90` pelo menos 20% menor; ΔnDCG@20 ≥+0,05;
procedência perfeita; e estudo humano com redução de tempo sem perda crítica.

## Reprodução

```bash
python3 -m scripts.auditar_rank05_divergencia_gerencial_contabil
uv run --with openai==2.45.0 --with pytest==9.1.1 \
  python -m pytest -q tests/test_auditar_rank05_divergencia.py
```

Resultado focado: **7 testes passaram**. A suíte ampliada com runtime,
`requirements-modelo.txt` e `requirements-local.txt` terminou com **1.725
testes aprovados, nenhum skip e 28 warnings** em 79,02 s. Artefato:
`artefatos/rank05/auditoria_precondicoes.json`.

Ressalva ambiental, separada do candidato: uma resolução limpa que acrescenta
`requirements-guardrails.txt` é atualmente insatisfatível porque o runtime
fixa `numpy==2.5.1` e `presidio-analyzer==2.2.364` declara `numpy<2.5.0`. Nenhum
pin foi alterado nesta rodada. Isso não afetou os sete testes do auditor nem a
suíte ampliada, mas impede reproduzir em um único ambiente efêmero a combinação
literal dos quatro manifestos.

O resultado não é “falta tudo”. O corpus já contém a matéria-prima de K1. O
que falta para ML é justamente a evidência que separa localizar uma ponte de
priorizar uma revisão: vintage, diversidade, gold, baselines e efeito no
trabalho humano.
