# Validação do CAND-02 — redline semântico de divulgações

## Veredito

Os dois especialistas, em contextos isolados e depois de duas rodadas de
objeções mediadas, chegaram aos mesmos dois vereditos:

1. **REJEITAR a implementação de componente aprendido agora.**
2. **REJEITAR a afirmação de que o redline determinístico já demonstrou
   utilidade empírica.**

O estado científico é **INDECIDÍVEL**, não “ML provado inútil”. A estrutura do
experimento passou; a evidência humana que permitiria julgar ranking, segurança
e economia de tempo ainda não existe.

## O candidato

CAND-02 compara releases consecutivos do mesmo emissor e produziria uma fila de
mudanças que merecem leitura:

- adição, remoção ou alteração de afirmação;
- texto literal antes/depois;
- empresa, documentos, trimestres, páginas e hashes;
- razão de prioridade, sem recomendação, retorno esperado ou preço-alvo.

O nome correto do rótulo é **prioridade de leitura**, não materialidade legal.
A [IFRS Practice Statement 2](https://www.ifrs.org/content/dam/ifrs/publications/amendments/english/2017/ifrs-practice-statement-2-making-materiality-judgements.pdf)
e o [SEC SAB 99](https://www.sec.gov/interps/account/sab99.htm) reforçam que
materialidade depende de contexto quantitativo e qualitativo; isso não autoriza
um algoritmo de triagem a declarar “fato material”.

A [Resolução CVM 44](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol044consolid.pdf)
usa critério jurídico próprio para fato relevante. A
[Resolução CVM 20](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol020consolid.pdf)
também exige cautela quando uma interpretação sobre emissor é divulgada a
terceiros. O uso cogitado aqui permanece ferramenta interna de leitura.

## Por que a hipótese merece teste

O estudo
[Lazy Prices](https://www.nber.org/papers/w25084) encontrou informação econômica
em mudanças de linguagem de 10-Ks norte-americanos. Isso justifica investigar,
mas não transfere validade para releases bancários brasileiros nem prova que
um modelo supera um diff lexical.

O problema técnico de mapear spans antes/depois também é reconhecido como
tarefa própria, distinta da priorização econômica; ver o
[framework de change tracking da IBM Research](https://research.ibm.com/publications/a-change-tracking-framework-for-financial-documents).
Por isso o protocolo separa alinhamento, ranking e estudo de workflow.

## Isolamento dos especialistas

- O cientista de dados e o analista de equity research receberam o mesmo
  enunciado mínimo em sessões novas e separadas.
- Nenhum recebeu números ou parecer do outro na primeira rodada.
- A sessão principal trocou apenas objeções anonimizadas: unidade de label,
  custo de falso negativo, pooling, tamanho efetivo, métricas e tempo.
- Na fase final, ambos receberam exatamente o mesmo resultado do auditor.
- Não houve comunicação direta entre os agentes.

## Pré-registro

As regras foram congeladas antes de calcular ranking ou abrir rótulos:
`resultados/pre_registro_cand02_redline_2026-08-27.md`.

Pontos centrais:

- unidade: afirmação atômica; alinhamento pode ser muitos-para-muitos;
- tabelas exigem linha/métrica, cabeçalho, unidade, período e notas;
- B0 trivial e B1 determinístico forte vêm antes de ML;
- challenger aprendido recebe os mesmos eventos e só reordena;
- leitura completa e livre por dois analistas, seguida de adjudicação;
- estudo humano contrabalanceado de tempo;
- sem esses elementos, **não carregar o modelo**.

## Split e resultado real do gate

Pares adjacentes compartilham o documento intermediário. O split correto usa
um período inteiro de embargo:

| Papel | Transição | Pares |
|---|---|---:|
| desenvolvimento | 2T2025 → 3T2025 | 5 |
| embargo | 3T2025 → 4T2025 | 5 |
| teste | 4T2025 → 1T2026 | 5 |

O auditor reproduzível encontrou:

| Gate | Resultado |
|---|---|
| Documentos | 20 |
| Pares adjacentes | 15 |
| Clusters independentes no teste | **5** |
| PDF compartilhado entre desenvolvimento e teste | **0** |
| Estrutura temporal | **aprovada** |
| Gabarito de dupla leitura | ausente |
| Manifesto de leitura completa + adjudicação | ausente |
| Estudo humano de tempo | ausente |
| Estado científico | **INDECIDÍVEL** |
| Decisão de implementação ML | **NÃO IMPLEMENTAR AGORA** |

Sentenças, tabelas e chunks não aumentam o número de réplicas independentes:
continuam aninhados nos cinco emissores finais.

## Barras congeladas para reabertura

O workflow determinístico precisa demonstrar:

- zero falso negativo crítico nos pares auditados;
- recall de prioridade 2 ≥ 0,90;
- nDCG@20 ≥ 0,80;
- 100% de procedência nos itens exibidos.

O aprendido, além disso, precisa obter simultaneamente:

- zero falso negativo crítico adicional;
- nenhum prioridade 2 adicional perdido enquanto houver menos de 50;
- ΔnDCG@10 ≥ +0,10 e ΔnDCG@20 ≥ +0,05;
- ganho em 5/5 emissores;
- `N@R90` pelo menos 20% menor;
- ganho humano de tempo sem perda de acurácia.

O gate de rótulo exige dupla leitura dos **15 pares**, adjudicação, α ordinal
≥ 0,67, acordo binário ≥ 80%, acordo positivo ≥ 75% e pelo menos 30 mudanças
prioridade 2. Para generalização além deste corpus: no mínimo 30–34 pares
finais, dez emissores e 50 prioridade 2, recalculando potência com o piloto.

## Consenso final

| Especialista | ML agora | “Determinístico já é útil” |
|---|---|---|
| Ciência de Dados | **REJEITAR** | **REJEITAR** |
| Equity Research | **REJEITAR** | **REJEITAR** |
| Sessão principal | **NÃO IMPLEMENTAR** | **NÃO ALEGAR UTILIDADE** |

O resultado correto não é construir embeddings, LLM ou ranker para preencher
os campos ausentes. O próximo trabalho desta linha, se priorizado, é humano:
gold de dupla leitura, adjudicação e teste de tempo. Só depois B0/B1 são
comparados e o challenger pode ser executado.

## Reprodução

```bash
.venv/bin/python -m scripts.auditar_cand02_redline
.venv/bin/python -m pytest tests/test_auditar_cand02_redline.py -q
```

Artefato: `artefatos/cand02/auditoria_precondicoes.json`.

Este veredito não conclui que redline de documentos é inútil. Conclui que,
neste projeto e hoje, nem o valor do baseline nem a incrementalidade de ML
foram medidos; implementar o aprendido agora seria complexidade sem evidência.
