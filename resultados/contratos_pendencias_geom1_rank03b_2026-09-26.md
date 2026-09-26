# Pendências GEOM-1 / Rank 3-B — contrato de correção

Data: 2026-09-26. Escrito antes da alteração de código. Pedido: corrigir as
pendências remanescentes, sem confundir melhoria do instrumento com aprovação
do candidato. Não substitui contratos ou evidências históricos.

## P1 — sinal e fronteira do token

A classe de interferências do analisador passa de Cf/Cc não espaciais para
Cf/Cc não espaciais, marcas Unicode (Mn/Mc/Me) e caracteres cujo nome contém
FILLER, sempre excluindo a classe de sinais já contratada. A definição usa a
tabela Unicode da versão de Python registrada na execução. É uma barreira
conservadora: nem toda marca é invisível. Não é uma garantia sobre toda fonte,
OCR ou caractere Unicode não atribuído.

- Dentro da sequência numérica: o token inteiro é recusado; não pode casar
  prefixo nem sufixo. Mantêm-se ordem e contagem dos tokens recusados.
- Entre sinal/parêntese e número: ambiguidade, nunca positivo presumido.
- Sem sinal/parêntese: mantém-se a regra anterior de sinal limpo.
- Prefixo monetário de até três letras ASCII maiúsculas e símbolo Sc com
  espaços/interferências internos (inclusive `R $`, `U S $`): ambiguidade,
  mesmo sem sinal. Não se presume qual era o sinal original.
- A moeda sem fragmentação, como `-R$ 1.234`, continua negativa.

Contraprovas: os exemplos do defeito; todas as marcas/preenchedores da classe
adicional, com sinal e dentro de número; moedas fragmentadas, parênteses,
separadores espaciais; controles positivos sem fragmentação e colunas vizinhas.
Os dois testes de caracterização que prendiam o defeito e sua ressalva são
substituídos declaradamente por testes da correção e do novo limite. O histórico
fica no snapshot, não é reescrito. A busca continua exata nesta alteração.

## P2 — B4: esquema fechado do manifesto

O consumidor CSV exige exatamente as colunas de `COLUNAS_MANIFESTO`, sem
duplicatas, ausências ou extras, em qualquer ordem. Arquivo vazio não é
manifesto vazio: só cabeçalho válido representa zero correções. Linhas com
campos a mais ou a menos e sintaxe CSV inválida são recusadas antes da
validação semântica ou de consultar pacotes. Campos presentes e vazios
continuam sujeitos às regras semânticas existentes.

Exceção histórica já explícita na API: com
`exigir_evidencia_numerica=False`, admite-se também o esquema antigo sem
`evidencia_numerica`; nenhuma outra ausência ou coluna extra é permitida.
Isso não autoriza usar o esquema antigo na execução governante.

Os bytes são lidos uma única vez; parser e hash de origem usam os mesmos
bytes. Uma troca posterior continua barrada pelo executor existente. Não se
introduz correção por conta: `cd_conta`, `escopo` e qualquer coluna nova
derrubam o consumidor, inclusive em CSV sem linhas.

Contraprovas: extra/ausente/duplicada (inclusive sem linhas), linha longa ou
curta, CSV malformado, arquivo vazio, cabeçalho válido sem linhas, ordem
diferente, compatibilidade histórica explícita e troca posterior dos bytes.
Não altera adjudicador, construtor, painel, correções nem gates publicados.

## P3 — arredondamento do ativo: contrato separado, ainda sem busca real

Pode-se implementar e testar com dados sintéticos uma função exclusiva de
diagnóstico do ativo. Recebe valor **do ativo** em reais e procura sua forma
dividida por mil arredondada ao inteiro mais próximo, usando Decimal e
ROUND_HALF_UP (empates afastam-se de zero). O token impresso deve ser inteiro,
ter sinal não ambíguo, corresponder ao valor arredondado e este não pode ser
zero. Exige valor finito e diferente de zero. Não procura um intervalo aberto
de valores e não mistura esses resultados com a busca exata.

Correspondência significa somente candidata à inspeção da conta, período,
perímetro, unidade e política de arredondamento da própria fonte. Não prova
escala e não promove manifesto. Se a fonte declarar outra regra, este
diagnóstico não a substitui. Não conectar ao executor real nesta onda; não
oferecer modo por módulo/FCO. Testar sinais, empates, vizinhos, zero,
não finitos, centavos e interferências, sempre com dados artificiais.

## P4 — O1 e decisões do v2: não presumir aprovação

O1.3 só permite ler FCO individual para testar igualdade. Piso/teto não são
igualdade; a redação original não dá autorização explícita para esses
cálculos. A finalidade protetiva é distinta de pesquisa e justifica propor
uma exceção restrita, não afirmar que ela já estava aprovada. Foi solicitada
decisão ao responsável. Enquanto não houver resposta, preservar o detector
existente (não enfraquecê-lo) e **não executar sobre FCO real** nesta onda.

Uma eventual autorização de piso/teto **só para barrar publicação** não
autoriza buscar FCO arredondado, publicar valores, calcular o desfecho ou
adjudicar escala. Pesquisa arredondada de FCO requer decisão e contrato
próprios. O código protetivo antigo e suas execuções ficam registrados como
histórico, sem reclassificar retroativamente seu grau de autorização.

Os seis [DECIDIR] permanecem no rascunho até decisão do responsável. Não
implementar escolhas silenciosamente nem congelar o rascunho como aprovado.
O executor v2 depende dessas escolhas e da ordem G0 → G1 sem rótulo →
amostra com rótulo → T1 → T2 → baselines. Sua implementação não equivale a
permissão para rodar: a execução real precisa de pré-registro aprovado e
painel/manifesto fixados. Nenhum treino nesta onda.

## P5 — verificação e preservação

Snapshot do código e testes alterados antes da edição; hashes dos sete
protegidos antes/depois. Testes sintéticos dirigidos e suíte completa, com
registro próprio. Leitura do manifesto governante para validar somente seu
esquema não reconstrói painel nem reexecuta gates. Nenhum download ou API
paga. Ao final, auditor-conformidade somente leitura (§7 de AGENTS.md).

Condições de falsificação: um caso P1 casa positivo ou por prefixo; coluna
desconhecida/ausente em P2 passa; arredondamento promove escala ou alcança
FCO; artefato governante muda; cálculo real de desfecho ou aprovação
metodológica implícita. Qualquer uma impede encerrar esta onda como cumprida.
