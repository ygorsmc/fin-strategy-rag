# Regra GEOM-1 — fixada após reconhecimento, antes do piloto de verificação

2026-09-18. Complementa o contrato de escala geométrica da mesma data.
Oito documentos de desenho: sete legíveis; 144031 devolveu XML inválido no
Poppler e fica como falha de leitura. Não saneamos texto nem substituímos ID.
O helper foi corrigido para registrar essa falha e seguir nos demais; seu
código inicial foi preservado e a seleção continua com o pin inicial.

## Regra operacional

1. Poppler `pdftotext -bbox-layout` local extrai palavras e caixas. Somente
   PDFs dos anexos de notas 193/412 do pacote original, com SHA-256 conferido.
   Versão do Poppler e hashes do código são registrados. Sem fallback/OCR.
2. Agrupar palavras por topo vertical, tolerância de 1,5 ponto PDF; ordenar
   horizontalmente. Coordenada não finita, invertida ou fora da página
   invalida a página. Não transformar um erro de extração em aprovação.
3. Datas completas dd/mm/aaaa, dd.mm.aaaa ou aaaa-mm-dd; calendários válidos.
   Linha de datas contém apenas datas e, opcionalmente, um `Nota`/`Notas` à
   esquerda. Não inferir data pelo valor nem completar ano abreviado.
4. Linha anterior de perímetro a até 24 pontos: somente `Consolidado`,
   `Controladora`, `Individual` ou `Companhia`, com uma ocorrência de
   Consolidado. Um grupo único é permitido se explicitamente consolidado.
   Dividir as datas em grupos contíguos de igual tamanho, na mesma ordem
   horizontal dos perímetros. Se houver vários grupos, as sequências de datas
   devem ser idênticas; dentro do grupo não pode haver repetição. Centro do
   rótulo de perímetro deve estar entre o início da primeira data e o fim da
   última do grupo, tolerância de 12 pontos. Datas futuras ao documento não
   são prova do saldo corrente. Cabeçalho desigual/ambíguo abstém.
5. Unidade precisa estar na MESMA página, antes do cabeçalho, no topo até
   200 pontos, em linha exclusivamente de declaração: `em milhares de reais`,
   opcional `valores`, `expressos/apresentados` e apenas a ressalva genérica
   `exceto quando indicado de outra forma` / `exceto indicado de outra forma`.
   Não aceitar unidade do rodapé de ação nem menção numérica em prosa.
   Qualquer indicação de moeda/unidade contrária entre a unidade e a linha
   candidata invalida o uso do cabeçalho; cabeçalhos repetidos MIL não brigam.
   Declaração que começa com Em/Valores/Montantes/Expresso(s)/Unidade/Moeda
   fora do vocabulário aceito, ou contém unidade/moeda contrária, veta;
   não classificar uma moeda desconhecida como ausência de declaração.
6. A linha de dado fica depois das datas, na mesma página, no máximo 300
   pontos abaixo. Nova data/perímetro, prosa sem célula numérica, intervalo
   vertical entre linhas > 30 pontos ou unidade nova encerram o contexto.
   Seções tabulares sem número permitidas: Ativo/Passivo, Circulante,
   Não circulante, Custo amortizado e Ativos financeiros.
7. Células são identificadas pelo alinhamento da borda direita com a data
   (até 12 pontos), nunca por igualdade com o valor procurado. Exigir uma
   célula numérica/traço por coluna e nenhuma palavra extra à direita do
   rótulo. Uma referência de nota inteira é permitida só se alinhar com a
   coluna explicitamente intitulada Nota, também em até 12 pontos.
8. Rótulos completos de saldo, vocabulário v4, mais `total de caixa e
   equivalentes de caixa`. Sufixo explícito `(Nota N)`/`- Nota N` pode ser
   removido. Não aceitar subtotais, prefixos `(-)`, fluxo, investimento,
   aplicações financeiras junto a caixa, saldo inicial/final ou somas
   implícitas. Nenhuma conta 6.x vira prova.
9. Selecionar a coluna por data corrente e perímetro consolidado ANTES da
   comparação numérica. Preservar unicidade antes do módulo, piso 1.000,
   arredondamento inteiro/equivalência decimal e recusa de formas ambíguas
   do contrato CRF. Todos os matches entram no veredito; não ocultar
   discordância escolhendo só a primeira prova.
10. Publicar somente coordenadas, metadados de conta/data/perímetro/unidade
    e trechos numéricos mascarados. A prova inclui SHA-256 do PDF do anexo.
    Para validação, reler a fonte pinada e reproduzir a prova inteira;
    metadata plausível sem replay não é prova validada.

## Critério desta etapa

Implementação e contraprovas primeiro; desenho pode exercitar o instrumento.
Depois fixar hash e rodar UMA passagem nos 12 documentos de verificação e
sentinelas, sem G0. Toda aceitação dessa passagem deve ser conferida contra
a fonte por auditor independente. Publicar cobertura por estrato, falhas e
abstinências. Nenhuma extrapolação de precisão estatística a partir desse
piloto. Zero prova aceita ou erro comprovado impede promoção à extensão.

GEOM-1 é uma regra nova e separada; não rebatiza a v4 nem altera o consumidor
governante nesta etapa. Extensão aos 405, S5, integração do manifesto e G0
somente após o critério acima e revisão do produtor/consumidor.

## Correção do desenho antes da verificação

O auditor independente mostrou em sintético que a ressalva arbitrária
`exceto ...` aceitava uma exclusão explícita de caixa em reais/milhões.
Fechado o vocabulário acima, e declaração contrária não enumerada passou a
vetar em vez de ser ignorada. Dimensões da página também precisam ser
positivas e finitas. Nenhum PDF da verificação havia sido aberto; nenhum G0
novo havia sido medido. Os layouts de desenho já eram conhecidos.
