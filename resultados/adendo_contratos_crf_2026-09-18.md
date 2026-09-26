# Adendo de execução CRF — 2026-09-18

Contrato original de 17/09 preservado em
contratos_correcao_crf01_crf03_rank03b_2026-09-17.md.

Antes da primeira medição de G0/G1 da v4, o auditor de conformidade identificou
uma violação de C1.5 em dado sintético: o módulo era tomado antes de conferir
unicidade. Corrigido para rejeitar declarações +x e −x da mesma conta/período.
Acrescentada guarda do consumidor: o rótulo e a quantidade de células do
trecho mascarado precisam corresponder à conta/datas publicadas; metadata
plausível junto de trecho de outra conta não certifica prova.

Errata de C1.6: **linha e coluna** começam em 1; **anexo conserva o índice
original do extrator, que começa em 0**. Reindexar anexo romperia procedência
histórica. A fixture e o produtor/consumidor usam essa convenção.

A primeira execução v4 foi preservada em
artefatos/painel_pesquisa_rank03b/adjudicacao/execucao4_pre_auditoria/.
Pin anterior: antes_execucao4.json; a repetição após a correção do instrumento
usa antes_execucao4b.json, no diretório artefatos/correcao_crf_rank03b_2026-09-17/.
Não houve ajuste ao resultado de G0 nem relaxamento do contrato de escala;
as duas alterações só recusam evidência antes aceita indevidamente.

A regra estrita de tabelas e os cinco [DECIDIR] permanecem inalterados.
