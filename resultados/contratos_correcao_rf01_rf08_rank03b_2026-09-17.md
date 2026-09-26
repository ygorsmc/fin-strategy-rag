# Contratos de correção RF-01 a RF-08 — Rank 3-B, pré-treino

**Data:** 2026-09-17, escritos **antes** de editar a implementação.
**Origem:** [conferência independente de 17/09](conferencia_pre_treino_rank03b_2026-09-17.md),
ordem 1 da lista finita (§4 de lá).
**Não autoriza:** T1, T2, baseline ou treino sobre dado real; escrita em
`cvm.duckdb`/`cvm_treino.duckdb`; acesso ao holdout; chamada paga; download
novo (os 405 pacotes da adjudicação já estão em disco e a reexecução roda com a
rede bloqueada).

**Regra desta onda:** a regra de escala v3 e a política de disponibilidade são
congeladas **aqui**, antes de reexecutar. O resultado de G0/G1 que sair delas é
publicado como sair — **não há segunda revisão de regra nesta onda**, inclusive
se G0 reprovar.

---

## E — Evidência numérica localizada (RF-01)

**E1. Regra v3 da evidência numérica.** Um número das notas só conta como
evidência de escala se **todas** as condições valerem:

| # | Condição | O que fecha |
|---|---|---|
| a | O valor testado é **consolidado**, do **período corrente** (`dt_fim = dt_refer` do documento), com módulo ≥ 1.000 | comparativo e coluna individual não decidem |
| b | O número aparece numa **linha** de página das notas (grupos 193/412) que contém o **rótulo da conta** do valor (vocabulário fechado E2) | número de outra conta (capital, ações, obras) |
| c | A linha não menciona **ação/ações** | quantidade de ações |
| d | A **página** declara milhares (padrões `MIL` de `PADROES_DE_UNIDADE` ou `CABECALHOS_V2`) e não tem cabeçalho `UNIDADE` nos primeiros 300 caracteres | unidade da tabela |
| e | O número **não** é também a forma, sob **outro** multiplicador, de outro valor da mesma conta (qualquer período, consolidado ou individual) | coincidência entre colunas |

Classes, como antes: `bruto`, `dividido`, `multiplicado`, `nenhum`,
`conflitante`. A tabela S2 **não muda** (cabeçalho `MIL` + `bruto` → `MIL`;
`MIL` + `dividido` → `UNIDADE`; o resto é indecidível). Nenhum piso novo de
quantidade de casamentos: um casamento localizado basta, como antes.

**E2. Vocabulário de rótulo, fechado**, tirado da descrição das contas no plano
padrão, **não** das linhas casadas:

| Conta | Padrão (texto da linha normalizado) |
|---|---|
| `1` | `total do ativo` · `ativo total` |
| `2` | `total do passivo` · `passivo total` |
| `1.01.01` | `caixa e equivalentes de caixa` |
| `6.01` | `atividades operacionais` |
| `6.02` | `atividades de investimento` |
| `6.03` | `atividades de financiamento` |
| `6.04` | `variação cambial` |
| `6.05` | `aumento`/`redução`/`variação` seguido de `caixa` |
| `6.05.01` | `caixa` + `início`/`inicial` |
| `6.05.02` | `caixa` + `final`/`fim` |

Custo aceito e declarado: rótulo quebrado em duas linhas pelo extrator não
casa; tabela cujo total é só "Total" não casa. Os dois viram `nenhum` → mais
indecisão, nunca mais correção.

**E3. Procedência da evidência numérica.** Cada documento publica até cinco
casamentos com `conta`, `forma`, `anexo`, `pagina` e `trecho` (a linha, com os
valores de caixa `6.x` mascarados por O1.3). O manifesto ganha a coluna
`evidencia_numerica`; o validador (produtor **e** consumidor) exige ao menos um
casamento com conta, página e trecho em toda linha `corrigida_documento`. Os
manifestos das execuções 1 e 2 são relidos com essa exigência desligada,
explicitamente.

**E4. Execução 3.** Reexecuta o escopo inteiro (405 documentos), o teste da
premissa de herança e a herança, com a regra v3, **rede bloqueada**. A
execução 2 (`evidencias.jsonl`, `herdados.jsonl`, `resumo.json`, manifesto
`4735fb107cce…`) é **preservada** em `adjudicacao/execucao2/` antes. O
manifesto governante é regravado e **declarado** como nova versão.

**E5. Resposta conhecida.** `027570`/doc `152742` (ESC-0101) **não** pode sair
corrigido para `MIL` pela v3. Isto é critério de parada, não de ajuste: se sair,
a onda para e a regra volta para contrato. **Declarado:** a v3 foi escrita
conhecendo esse caso e as linhas casadas de dois documentos corrigidos
(`98645`, `97899`), inspecionadas para saber se o extrator preserva rótulo e
número na mesma linha. Não é amostra fresca.

**E6. Contraprovas obrigatórias** (fixtures sintéticas):
número em "capital social dividido em N ações" não decide; número igual ao
valor de **outra** conta não decide; valor **comparativo** casado não decide;
número que coincide com a coluna **individual** sob outro multiplicador não
decide; página sem declaração de milhares não decide; documento em reais com
notas em milhares e "Total do ativo" dividido **continua em reais**
(`confirmada`), mesmo com um número coincidente em linha de ações.

## P — Disponibilidade da prova de escala (RF-02)

**P4.** Todo documento tem `disponivel_em = max(dt_receb, datas das provas da
escala aplicada)`. Provas: escala declarada → nenhuma; `corrigida_documento` →
o próprio documento; `herdada_trecho` → o `dt_receb` de **cada ponta** citada,
pelo cadastro. O mesmo vale para `disponivel_em_v1`. Derivação, seleção as-of
(`vigente_em`) e G1 herdam por construção — as linhas passadas ao auditor
carregam a data já postergada.

**P5.** Ponta citada sem linha no cadastro **derruba** a construção
(`DefeitoDeFonte`); não vira "sem prova".

**P6. G1 independente.** O executor recalcula, **a partir do manifesto e do
cadastro** — não da data do construtor —, a data da prova de cada documento
usado em cada observação (janela de FCO e ativo) e publica
`g1_4_prova_de_escala_publicada_depois_de_D`; qualquer valor > 0 reprova G1. A
condição de falsificação c3 passa a comparar com a mesma data recalculada.

**P7. Contraprova:** mesmos valores e mesmas datas dos documentos; só a
recepção da ponta muda. Ponta publicada **depois** de D → a observação não usa
o valor corrigido em D; ponta **antes** de D → aceita. E o G1 independente
acusa um construtor que ignore a prova.

**Fora do escopo, declarado:** adjudicar o documento interior com evidência
própria existente em D (a alternativa do parecer) não é feito nesta onda.

## Q — Partição de T1 (RF-03)

**Q1.** Cortes nominais em `⌊k·n/5⌋`, k = 1..4; cada corte avança até o fim do
empate; corte que cai em `0`, em `n` ou não depois do anterior é **eliminado**.
Faixas = intervalos entre cortes restantes.

**Q2. Contraprovas:** o exemplo do parecer dá **duas** faixas (400 e 100);
constante dá uma; sem empate dá cinco de tamanho igual; empate atravessando um
corte e vários cortes; resultado invariante a permutação da entrada. O limiar
0,15 e a zona cinzenta **não mudam**.

**Q3.** A chave `probabilidade_de_exceder_o_limiar` vira
`frequencia_bootstrap_acima_do_limiar` — é frequência entre reamostragens, não
probabilidade posterior. A regra de decisão (> 10% ⇒ INDECIDÍVEL) não muda.
Substituição de nome declarada nos testes que a citam.

## R — Serialização de T2 (RF-08)

**R6.** `auc_agregada` zero publica `0.0`; a lacuna usa a AUC agregada, não
`agregada or 0`. Contraprova: o exemplo do parecer (AUC 0,0) publica 0,0.

## G — G0.5 pela proveniência aplicada (RF-04)

**G5.1.** População de risco: trimestre **válido** com operandos heterogêneos
na escala **declarada ou aplicada**, em que algum operando não tem veredito
decidido (execução vigente). Publicado por configuração
(declaradas iguais/diferentes × aplicadas iguais/diferentes).

**G5.2.** O limiar de 0,5% **não é herdado** de G0.3: é política nova para
outro evento e outro denominador, e fica **[DECIDIR]** no v2 com essa
ressalva. Nenhum limiar novo é aprovado nesta onda.

## V — Validação no caminho programático

**V1.** `carregar_correcoes` devolve um objeto `CorrecoesValidadas`. O
executor de gates **recusa** correções que não sejam desse tipo (um `dict`
comum com linhas, montado à mão, levanta). O painel sem correções continua
explícito (`{}` vazio).

## B — B0 (parte do RF-05 que já está especificada)

**B0.1.** O baseline se chama `B0_sempre_nao_consumir` e publica `acerto`
com IC 95% agrupado por companhia (mínimo de 40 reamostragens válidas) e
`cobertura_de_previsao_de_classe` = 1,0 **por construção** (sem bootstrap,
declarado). Sem IC válido, `completo = False`.

**Fora do escopo, declarado:** o **executor v2** (G0/G1 cegos, só depois o
alvo) e as políticas de grade D, janela, suporte intra de T2 e fórmula de G0.3
dependem das decisões do RF-05. Esta onda as **escreve no v2 como propostas**;
não as implementa.

## T — Nomes e ligação de evidência (RF-06, RF-07)

**T1.** O inventário publica `p2_pares_trimestre_decisao_no_intervalo_cego` e
`p2_chaves_companhia_D_distintas_no_intervalo_cego`. A chave antiga some.

**T2.** As verificações finais são regeneradas **depois** do painel novo e
registram, além do manifesto do painel, o digest e o hash do artefato de gates;
o produtor confere que o digest do manifesto é o do artefato de gates.

## Ordem de execução

1. Código e testes (E, P, Q, R, G, V, B, T). Suíte verde.
2. Preservar execução 2; reexecutar a adjudicação (E4) com rede bloqueada;
   conferir E5.
3. Reconstruir **só** o painel de pesquisa; G0/G1 com correções, sem
   correções e diagnóstico da execução 1.
4. Regenerar verificações e medições estruturais; hashes consistentes.
5. Relatório da onda, ressalvas datadas nos relatórios de 16/09, v2 atualizado,
   `MEMORY.md`. Auditor de conformidade.

## Condições de falsificação desta onda

1. Regra v3 alterada depois de rodar a execução 3.
2. ESC-0101 (ou o documento `152742`) corrigido para `MIL` na execução 3.
3. Observação cuja prova de escala é posterior a D aprovada por G1.
4. Teste existente enfraquecido sem declaração.
5. Algum hash dos painéis compartilhados, do pré-registro v1 ou do holdout
   alterado.
6. Estatística de rótulo calculada ou publicada.
