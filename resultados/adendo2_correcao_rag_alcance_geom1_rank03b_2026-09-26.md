# Adendo 2 à correção RAG — ressalvas da reconferência

Data: 2026-09-26. Escrito antes de editar, depois da reconferência do
auditor-conformidade sobre o [adendo](adendo_correcao_rag_alcance_geom1_rank03b_2026-09-25.md):
**FECHADO COM RESSALVAS**. Os sete achados anteriores e a observação estão
fechados; ficam cinco achados BAIXA e quatro observações. Parecer na íntegra em
`artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/conferencia_2/parecer_auditor.md`.
Valem o escopo e as proibições do contrato da correção (`69797721…`) e do adendo
(`af03e314…`), que seguem fixados por hash e não são alterados. O O1 continua
valendo.

## B1 — parêntese pela NFKC exercitado como decisão (achado 1)

Contraprova para cada parêntese ornamental da tabela — de abertura que não se
normaliza em `(`, de fechamento que não se normaliza em `)` —, combinado com o
parêntese normal do outro lado: ambíguo. As mutações "abre pelo nome" e "fecha pelo
nome" entram no harness.

## B2 — resíduo de invisível e moeda com espaço: limite declarado (achado 2)

A classe de invisíveis do A2 continua a do contrato (Cf e Cc que não são espaço nem
sinal). Ficam **declarados como limite**, no campo `limite` da saída e no relatório:

- caracteres ignoráveis fora dessa classe — combinante de grafema (U+034F),
  seletores de variação, preenchedores Hangul e afins — não entram no contexto do
  sinal, e um sinal separado do número por um deles se perde;
- moeda com espaço interno (`R $`, `US $`) não é reconhecida.

Motivo de declarar em vez de corrigir: a biblioteca padrão não expõe a propriedade
Default_Ignorable_Code_Point, e cobri-la exigiria uma lista mantida à mão — o que o
C2 e o adendo evitaram de propósito. No dado real não há nenhum desses caracteres
nem `R $`, medido pelo auditor. Antes de usar o instrumento em documentos de outros
emissores, a correção desse resíduo é pré-condição.

## B3 — quebra de linha na autoverificação (achado 3)

A leitura das representações passa a aceitar quebra de linha entre grupos (DOTALL),
em vez de derrubar a verificação com `TypeError`. Contraprova: `1\n234\n567` é
barrado; `9\n999` passa; a reconferência registra o publicado em vez de abortar.

## B4 — serializar antes de gravar (achado 4)

Identidade e resultado são serializados antes da primeira escrita. Contraprova: um
campo que passa na autoverificação e não é JSON derruba a execução sem gravar nada.

## B5 — documentação (achado 5 e observações)

- Frase dos "108 sinais": a classe tem 170 = 29 que negam + 6 que afirmam + 6 + 6
  parênteses normalizados + 108 "outro sinal" + 15 parênteses de fechamento
  ornamentais, que encerram o contexto à esquerda e contam como sinal colado à direita.
- Frase "cada regra de A2 a A7" corrigida.
- Declarados no relatório, como limite e não como achado: os resíduos da
  autoverificação (dois espaços entre grupos, espaço antes do ponto, combinante dentro
  do grupo, preenchedor como separador, expoente de quatro dígitos); os sósias de
  menos fora da classe; as contagens acima de mil no perfil de tokens, que é artefato
  de evidência, sem valor do XML; e a cópia privada do pacote em diretório temporário,
  apagada no fim, de onde nenhum valor é gravado.

## Execução

Código e testes do adendo preservados em `codigo_adendo/` (`ebe90e3e…`,
`f74d5745…`). Evidência nova em `adendo2/`: harness de mutação com as mutações
novas, busca, reconferência, contraprovas da conferência de 25/09, comparação com a
busca do adendo e com 24/09, suíte. **Esperado, fixado antes de rodar:** busca
idêntica à do adendo em tudo, menos a identidade (código, data, contratos) e o texto
do `limite`; as expectativas do adendo continuam cumpridas; todas as mutações
morrem. Qualquer outra diferença é relatada. O mesmo auditor reconfere B1 a B5.
