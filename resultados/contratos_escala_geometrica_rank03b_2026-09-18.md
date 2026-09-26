# Escala com evidência geométrica — Rank 3-B

Data: 2026-09-18. Pedido: melhorar a extração/adjudicação documentada nas
fontes já disponíveis, após o fechamento CRF. Não é novo alvo de ML.

## 1. Fronteiras preservadas

O resultado v4 e seus artefatos permanecem intactos durante o desenvolvimento.
Não calcular alvo real, T1/T2/baseline, acessar holdout, baixar documentos,
usar API paga, alterar os painéis compartilhados ou decidir os cinco pontos
do pré-registro. O1 continua valendo: nenhuma publicação de valor de FCO.
Nenhum limiar, universo ou exclusão de G0/G1 muda nesta rodada.

## 2. Reconhecimento antes de definir o extrator

A v4 pressupunha um layout literal que não reconheceu nenhum documento.
Esta rodada primeiro observa estrutura de fontes, sem adjudicar nem medir
G0. O reconhecimento utiliza apenas os 405 pacotes pinados já adquiridos.
Preserva a identificação original dos anexos e trabalha somente com notas
explicativas, grupos 193/412. O PDF renderizado externo não é fonte.

Seleção, antes da leitura de layouts: quatro estratos `formato × escala
declarada`; em cada um, ordenar por SHA-256 de
`geometria-2026-09-18|cd_cvm|conjunto|dt_refer|versao`.
Selecionar dois documentos de companhias distintas para desenho e três para
verificação documental. Excluir da verificação companhias presentes em
qualquer estrato de desenho; uma companhia por estrato de verificação.
Não usar correção anterior, salto de ativo ou efeito em G0 para selecionar.
Se faltar suporte num estrato, registrar a insuficiência, sem substituição
oportunista. Os IDs 76468 e 152742 são sentinelas históricas adicionais,
explicitamente conhecidas, não amostra nova de avaliação.

A seleção e os hashes das entradas serão gravados antes da leitura. Os
documentos de verificação não serão usados para ajustar a regra após a
primeira medição nela. Os 405 já passaram por regras antigas: não chamar
esse subconjunto de amostra financeira virgem nem de holdout do modelo.

## 3. Evidência exigida e mudança permitida

Pode mudar o reconhecimento de layout, não a necessidade de demonstrar:
conta completa, saldo corrente, coluna consolidada, unidade aplicável e
correspondência numérica com o formulário daquele documento. Não inferir
coluna/perímetro pela magnitude que se deseja encontrar. Sem ambiguidade
resolvida pela fonte, abster-se. Não retomar a busca v3 em qualquer número
da linha ou aceitar câmbio de investimento como caixa.

Só saldos 1, 2 e 1.01.01 nesta rodada; fluxo 6.x continua fora das provas.
Zero não prova escala; unicidade antes do módulo e recusa de multiplicadores
ambíguos continuam obrigatórias. Reutilizar a tabela S2 vigente (cabeçalho
MIL mais forma bruto/dividido); nenhuma extrapolação para LPA/outras contas.

Após o reconhecimento, registrar aqui um adendo operacional **antes** de
implementar e medir o novo extrator na verificação/405 documentos. Especificar
vínculo de coordenadas, escopo da unidade, tratamento de cabeçalhos e limites
de aceitação. Preservar v4 para reprodução; não sobrescrever seu veredito.

## 4. Validação antes de promover

Contraprovas devem cobrir conta vizinha, comparativo, controladora, cabeçalho
de outra tabela, fluxo, unidade ausente/contrária, datas/colunas ambíguas,
arredondamento, sinal, zero, e prova adulterada no consumidor. Controles
positivos precisam corresponder a layouts observados, não apenas à forma
inventada pelo parser.

Publicar abstinência e cobertura, inclusive zero. Toda prova aceita no piloto
de verificação exige conferência independente contra a fonte. Um erro
demonstrado impede promoção; ajuste posterior invalida aquela passagem e
exige declarar nova versão, não substituir silenciosamente o resultado.
Concordância de agentes não é gold humano nem estimativa de acurácia geral.

Só depois desse piloto e da revisão do instrumento pode-se aplicar a mesma
regra ao escopo completo, sem seleção de documentos pelo resultado. Fixar
hashes antes da execução. Antes de alterar o manifesto governante, preservar
um snapshot da v4 e obter auditoria do produtor e consumidor das provas.
Herança só se S5 for testável e conforme, pelas regras já existentes.

G0/G1 são a última medição, com código e decisões de escala fechados. Depois
dessa medição não se ajusta a regra para recuperar aprovação. Mesmo aprovados,
os gates não autorizam treino: decisões de política, executor v2 e protocolo
continuam pendentes.
