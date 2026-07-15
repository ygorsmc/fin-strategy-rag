# Curadoria do conjunto-padrão

`perguntas.csv` é o único arquivo carregado pelo pipeline. Enquanto a curadoria
de teste não estiver concluída, ele contém apenas o conjunto `dev`, que pode ser
usado para iterar sem contaminar a avaliação final.

`candidatas_teste.csv` contém a primeira leitura das 45 perguntas de teste na
distribuição exigida pela especificação: 15 factuais, 10 comparativas,
10 qualitativas e 10 adversariais. **Ainda não é o conjunto congelado e não deve
ser usado para medir métricas.**

## Protocolo para promover as candidatas

1. Fazer uma segunda leitura independente dos locais citados, em outro dia.
2. Para `release_gerencial`, confirmar definição, valor, unidade e página sem
   reutilizar a anotação da primeira leitura.
3. Para `cvm`, conferir o valor no ITR/DFP estruturado e a ocorrência equivalente
   no PDF do corpus. A primeira leitura usou os arquivos oficiais
   `itr_cia_aberta_2026.zip` e `dfp_cia_aberta_2025.zip` do Portal de Dados
   Abertos da CVM; eles não são versionados no repositório.
4. Validar que todas as páginas são físicas e 1-indexadas, como o extrator do
   pipeline, e que cada documento pertence ao manifesto congelado.
5. Só então mover as 45 linhas para `perguntas.csv`, registrar a data de
   congelamento no `AGENTS.md` e não alterar perguntas/respostas após a primeira
   execução completa de teste.

## Estado da primeira leitura — 2026-07-15

- Corpus: `2T2025`, `3T2025`, `4T2025`, `1T2026`.
- Desenvolvimento: 10/10 perguntas `dev` validadas no arquivo do pipeline.
- Candidatas: 45/45, com IDs únicos e distribuição contratual.
- CVM já cruzada na primeira leitura: resultado IFRS do Itaú 1T26 e lucro IFRS
  atribuível ao controlador do Bradesco 1T26.
  No ITR 2026 consolidado, as contas `3.09` e `3.11.01` registram
  `11.875.000` e `5.177.940` em escala `MIL`, respectivamente.
- Validação estrutural concluída: esquema, contratos condicionais, documentos e
  limites das páginas físicas.
- Uma auditoria cruzada por instituição corrigiu a primeira versão no mesmo dia;
  ela não substitui a segunda leitura independente em outra data.

## Alertas para a segunda leitura

- No BTG 4T25, uma frase da página 3 mostra ROAE de 26,7%, mas a tabela da mesma
  página, o comentário da página 4 e a reconciliação da página 6 mostram 27,6%.
  A candidata `TSTC003` fixa as tabelas como fonte e usa 27,6%.
- No Bradesco, o ROAE trimestral de 3T25/4T25 (14,7%/15,2%) difere do ROAE
  acumulado anualizado (14,6%/14,8%). As comparativas fixam a série trimestral.
- O BTG reapresentou bases após a consolidação do Banco Pan; por isso a candidata
  temporal que cruzava 3T25 e 1T26 foi substituída por uma comparação só de 1T26.
- Em `TSTC009`, usar os deltas reportados, não apenas números arredondados: BB
  +404 bps e Santander +0,02 p.p.
