# CAND-03 — triagem de anomalias contábeis

**Veredito unânime dos dois especialistas: NÃO IMPLEMENTAR ML AGORA.**

**Estado científico: INDECIDÍVEL.** Não se mediu derrota nem vitória de modelo:
o componente aprendido parou nos gates anteriores ao algoritmo. O baseline
determinístico também **não** demonstrou utilidade; neste estado ele é somente
um gerador candidato para o experimento humano.

## O candidato que foi testado

Ferramenta auditável para ordenar combinações
companhia–release–conta que merecem investigação, ampliando a cobertura do
analista. O enunciado não promete fraude, retorno ou erro contábil.

O ranking original não havia persistido nomes. A sequência funcional adotada
foi:

1. deterioração de fundamentos;
2. redline semântico;
3. **triagem de anomalias contábeis/qualidade do lucro**.

O pré-registro foi congelado antes de score, modelo ou gold:
`pre_registro_cand03_anomalias_contabeis_2026-08-27.md`.

## Protocolo de isolamento

- um cientista de dados e um especialista em mercado/contabilidade receberam a
  mesma formulação neutra;
- nenhum pôde ler AGENTS, MEMORY, relatórios anteriores, arquivos de conclusão
  ou o parecer do outro;
- a sessão principal auditou o DuckDB e os ZIPs de forma independente;
- somente depois dos pareceres cegos foram enviadas objeções anonimizadas;
- réplica e tréplica ocorreram por mediação, sem contato direto;
- nenhum agente escreveu no repositório e nenhum modelo foi carregado.

Na tréplica, ambos retiraram seus limiares arbitrários anteriores, aceitaram E2
como alvo primário e assinaram o mesmo protocolo prospectivo.

## Três problemas que não podem compartilhar rótulo

| ID | Pergunta | Gold válido | Decisão atual |
|---|---|---|---|
| E1 | há erro/inconsistência no arquivamento? | correção confirmada e causa-raiz adjudicada | sem rótulos independentes suficientes |
| **E2** | esta mudança válida deve subir na fila de leitura? | dupla leitura humana, ação e prioridade | **alvo primário; gold ausente** |
| E3 | haverá deterioração ou fraude? | outcome externo datado; fraude e deterioração ainda separados | fora desta rodada |

E1 seria mais fácil de supervisionar se cada vintage numérico fosse recuperado,
mas escolhê-lo por conveniência mudaria a ação do produto. Reapresentação,
raridade, erro, prioridade de leitura e fraude não são sinônimos.

O CPC 23 distingue correção de erro de mudança de estimativa; nova informação
não transforma automaticamente uma estimativa anterior em erro
([CPC 23](https://www.cpc.org.br/Arquivos/Documentos/296_CPC_23_rev%2020.pdf)).
Materialidade também depende de natureza, magnitude e contexto, não de um corte
percentual universal
([CPC 26](https://www.cpc.org.br/Arquivos/Documentos/312_CPC_26_R1_rev%2014.pdf)).

## Auditoria reproduzível do dado real

Fonte: `scripts/auditar_cand03_anomalias.py` →
`artefatos/cand03/auditoria_precondicoes.json`.

| Medida | Resultado |
|---|---:|
| linhas em `fatos_contabeis` | 5.552.787 |
| companhias × trimestre | 23.346 |
| companhias | 741 |
| trimestres | 64 |
| demonstrativos no painel | BPA, BPP e DRE |
| linhas com mapa semântico exato | 274.935 · 4,951% |
| mapa | 198 entradas · 11 conceitos |
| companhias com setor no painel | 5/741 · 0,675% |
| chaves companhia–trimestre–conceito duplicadas | 698 |
| duplicadas com valores conflitantes | 587 |
| grupos numéricos com mais de um vintage preservado | **0** |
| correções curadas | 4 linhas · 1 emissor · 2 companhia–trimestres |

As quatro linhas corrigidas têm **uma causa-raiz**: duas contas-filhas de um
mesmo arquivamento e sua propagação ao 4T derivado. Como a tabela não possui
`cause_id`, o auditor executável publica o limite superior conservador de dois
clusters companhia–trimestre; até esse limite reprova longe do mínimo 30.

“5,55 milhões” é denominador, não rótulo. Conta, subtotal e trimestre da mesma
companhia são aninhados; a unidade do workflow é o **release**, e o rótulo é o
episódio-raiz agrupado dentro dele.

### A fonte possui dados que o painel descartou

Os 31 ZIPs locais, cobrindo 2011–2026, contêm arquivo geral com
`ID_DOC`/`DT_RECEB` e DFC consolidada:

| Metadado | Resultado |
|---|---:|
| linhas documento–versão | 48.129 |
| arquivamentos lógicos | 41.062 |
| arquivamentos com mais de uma versão | 5.803 · 14,13% |
| maior versão | 8 |
| atraso primeira → última versão | mediana 8 dias · p95 372,9 dias · máximo 2.962 |
| ZIPs com `DT_RECEB` | 31/31 |
| ZIPs com DFC-MD ou DFC-MI consolidada | 31/31 |

A [CVM confirma oficialmente](https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr)
que o ITR inclui DFC e que os arquivos são atualizados com reapresentações; o
mesmo vale para a
[DFP](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp).

Logo, DFC e `DT_RECEB` são bloqueios do **loader**, não de disponibilidade. A
restrição mais difícil é outra: o painel guarda apenas a versão numérica final
por companhia–conjunto–demonstrativo–data. `VERSAO > 1` indica que houve
reapresentação, mas não diz qual conta mudou nem se a mudança foi erro.

Uma fonte de positivos E1 existe na lista oficial de
[determinações de refazimento/republicação da CVM](https://www.gov.br/cvm/pt-br/assuntos/regulados/consultas-por-participante/companhias/determinacao-de-refazimento-republicacao-de-dfs-e-itrs),
mas ainda exigiria vincular documento, período, conta e causa. Processos
sancionadores ou uma reapresentação, isoladamente, não equivalem a fraude
confirmada.

## Por que a literatura não autoriza pular os gates

- Dechow et al. treinaram o F-score com casos externos de enforcement, não com
  milhões de células sem rótulo
  ([artigo original](https://onlinelibrary.wiley.com/doi/10.1111/j.1911-3846.2010.01041.x)).
- Beneish é um filtro probabilístico a investigar, não determinação automática
  de manipulação
  ([artigo original](https://doi.org/10.2469/faj.v55.n5.2296)).
- Autoencoders contábeis publicados foram avaliados em **lançamentos de razão
  de ERP**, com atributos transacionais; isso não transfere automaticamente
  para células trimestrais agregadas
  ([Schreyer et al.](https://arxiv.org/abs/1709.05254)).
- “Qualidade do lucro” exige caixa. O
  [CPC 03](https://www.cpc.org.br/Arquivos/Documentos/183_CPC_03_R2_rev%2024.pdf)
  também mostra que a apresentação de fluxos para instituições financeiras tem
  particularidades, reforçando a necessidade de comparação setorial.

## Baseline-candidato

Antes de qualquer aprendizado, todos os braços usam exatamente o mesmo universo
e orçamento:

1. guardas de unicidade, escala, período, versão e
   consolidado/individual;
2. identidades contábeis cuja taxonomia declare relação aditiva;
3. variação YoY escalada e mediana/MAD intracompanha;
4. pares econômicos mapeados, como lucro × caixa, recebíveis × receita e
   provisões × exposição;
5. comparação setorial somente onde setor e conceito forem estáveis;
6. agrupamento de contas afetadas pela mesma causa.

Contagem bruta de resíduos é apenas geração de candidatos. Sem adjudicação, uma
“quebra” pode ser período, arredondamento, escala, escopo, mapeamento ou
apresentação legítima — por isso nenhum parecer chamou esse baseline de útil.

## Protocolo de reabertura aceito por ambos

### Piloto shadow

- congelar cada release, versão, `DT_RECEB`, PDF/CSV/DFC, URL, hashes, mapa,
  features e ranking no momento do recebimento;
- começar com 30 releases integralmente revisados;
- continuar até obter ≥30 releases com pelo menos um episódio prioridade 1/2
  e rubrica estável, no máximo 150;
- dois revisores cegos entre si, adjudicação e releases amostrados da população,
  não apenas do top-N;
- congelar o baseline, orçamento `K`, recall-alvo, prevalência, variância e
  break-even antes do confirmatório;
- falhar no teto encerra o candidato nesta rodada.

O piloto não treina modelo e não entra no teste.

### Confirmatório

```text
N = max(100, N_poder, N_50+)
```

- `N_poder` usa a variância piloto da diferença pareada de tempo por release,
  α unilateral 5% e poder 80%;
- `N_50+` usa o limite inferior da prevalência piloto e exige ≥95% de
  probabilidade de pelo menos 50 releases positivos;
- `N` aumenta se a precisão pré-especificada do recall exigir;
- splits e incerteza agrupam release, episódio e emissor; conta nunca é réplica.

Primária: minutos/itens para alcançar **100% dos críticos** e o piso de recall
P1/P2 congelado antes do teste. nDCG@20 é corroborativa.

ML só avança se:

- procedência for 100%;
- não perder nenhum crítico e mantiver recall P1/P2 ≥0,90;
- o limite de confiança da economia de tempo superar
  `max(break-even + margem, 20%)`;
- nDCG@20 não piorar e os resultados não forem carregados por um emissor/setor.

## O que pode ser construído agora

Sem antecipar o experimento:

- coletor imutável de snapshots e todos os vintages futuros;
- ingestão de DFC e `DT_RECEB`;
- chave canônica e resolução das 698 duplicidades;
- cadastro/setor com vigência;
- geradores determinísticos chamados **candidatos**, não alertas úteis;
- interface de dupla anotação/adjudicação e telemetria de tempo;
- shadow logging, split e arnês de métricas.

Não construir agora:

- classificador, ranker, Isolation Forest ou autoencoder;
- score chamado fraude, erro material ou qualidade do lucro;
- peso “aprendido” pela inspeção do piloto;
- ranking público ou promessa de economia de leitura.

## Conclusão

Os dois especialistas terminaram com exatamente a mesma frase operacional:

> E2 é o alvo correto; o shadow prospectivo torna o experimento possível, mas
> hoje não há gold, baseline medido nem painel point-in-time. Portanto, não se
> implementa ML agora.

Condição mínima de reabertura: piloto prospectivo aprovado, com ≥30 releases
positivos, rubrica estável, baseline congelado e tamanho confirmatório calculado
por potência. Uso no produto exige depois o confirmatório inteiro; passar o
piloto apenas autoriza testar o componente aprendido.
