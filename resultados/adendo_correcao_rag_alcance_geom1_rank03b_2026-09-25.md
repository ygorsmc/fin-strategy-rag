# Adendo à correção RAG — resposta à conferência que reabriu a onda

Data: 2026-09-25. Escrito antes de editar, depois do parecer do
auditor-conformidade sobre a primeira execução da correção: **REABERTO em
dois pontos**, com 2 achados MÉDIA e 5 BAIXA e nenhum ALTA. O parecer está na
íntegra em
`artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/conferencia_1/parecer_auditor.md`.
Valem o mesmo escopo e as mesmas proibições do
[contrato da correção](contratos_correcao_rag_alcance_geom1_rank03b_2026-09-25.md)
(`69797721…`), que segue fixado por hash e não é alterado. O O1 continua
valendo.

## A1 — recusa estrutural do pin exercitada como decisão (achado 1)

A contraprova de C1 refixava só o hash do pin; a vinculação do pin de execução
e da revisão recusava antes da estrutura. Passa a ser assim:

- As outras referências concordam com o pin malformado: `pin_sha256` do pin de
  execução em `executar`; `pin_alcance_sha256` e `fontes` do pin da revisão,
  além da conferência e do inventário, em `reconferir_publicados`.
- Cada caso casa a sua mensagem estrutural. Há também teste unitário de
  `validar_fontes`, um por regra.
- **Evidência por mutação:** retirar cada checagem derruba ao menos um teste.
  - Checagens de `validar_fontes`: lista não vazia, id numérico, hash bem
    formado, id repetido e hash repetido.
  - Cada regra nova desta onda também entra.
  - O harness reproduzível fica na pasta da onda e muta o código em memória,
    sem editar o repositório.

## A2 — caractere invisível (achado 2)

Invisível é o caractere de formatação (Cf) ou de controle (Cc) que não é
espaço nem pertence à classe de sinais.

- Invisível dentro da sequência de dígitos: token recusado, fora da gramática.
- Invisível no contexto de um token que tem sinal ou parêntese: ambíguo. Isso
  inclui o invisível entre o token e o parêntese de fechamento.
- Sem sinal nem parêntese no contexto, o invisível não muda o sinal.

Contraprova para cada caractere da classe, montada a partir da tabela Unicode.

## A3 — o que nega, o que afirma, o que é parêntese (achado 3)

Definição por categoria e normalização, não por nome:

- **nega:** categoria Pd, como o R3 já dizia, ou forma NFKC igual a U+2212
  (MINUS SIGN, U+207B e U+208B);
- **afirma:** forma NFKC igual a `+`;
- **parêntese:** forma NFKC igual a `(` ou `)`.

Todo outro caractere da classe de sinais vira "outro sinal", portanto
ambíguo. Entram aqui:

- os 19 que têm "MINUS" no nome e não se normalizam no MINUS SIGN (❖, ∖, ⊖,
  seta, combinante, TAG e outros);
- os que têm "PLUS" no nome e não viram `+`;
- os parênteses ornamentais.

Parêntese de fechamento de qualquer forma continua encerrando o contexto à
esquerda, porque pertence a algo anterior. Há contraprova para cada caractere
da classe, com a expectativa derivada da tabela e não da implementação.

**Ajuste declarado de contraprova desta onda:** `➕` (HEAVY PLUS SIGN) e `˗`
(MODIFIER LETTER MINUS SIGN) saem dos testes de sinal colado. Os dois passam a
ambíguos.

## A4 — sinal depois do token; menos na moeda (achado 4)

**(a)** Sinal colado depois do token, ou depois do seu parêntese de
fechamento, torna o token ambíguo, qualquer que seja o caractere seguinte. É a
letra do C2.

- `1.234.567-8` e `2024-2025` passam a ambíguos dos dois lados.
- **Ajuste declarado de contraprova desta onda:** o caso `2024-2025` fixava
  2024 como positivo.

**(b)** Leitura declarada e mantida: menos colado à moeda, com a moeda separada
do número por espaço, é negativo. É o formato de valor negativo em reais,
`-R$ 1.234,00`.

- O menos só vale colado ao que vem logo depois dele: o token ou a moeda.
- Entre a moeda e o número, o espaço é livre.
- A contraprova já existe. O relatório passa a declarar a leitura.

## A5 — equivalência sem lista de separadores (achado 5)

Antes de ler números, a autoverificação normaliza o texto publicado (NFKC) e
retira os invisíveis.

- **Separador de milhar:** qualquer caractere não alfanumérico, ou o
  sublinhado, entre grupos de três dígitos.
- **Decimal:** `.` ou `,`.
- **Expoente:** cada representação é lida com e sem ele.

Contraprovas:

- cada espaço da categoria Zs, montado a partir da tabela;
- apóstrofos, sublinhado, ponto médio e vírgula de largura cheia;
- invisível entre grupos;
- expoente positivo e negativo.

## A6 — versão da fonte e leitura única do pacote (achado 6)

**(a)** O universo passa a conferir também a versão, sempre antes de gravar.

- Cada registro do inventário precisa ter:
  - o `sha256` do pin;
  - o `sha256_pdf` do PDF do pacote conferido.
- Cada documento da conferência publicada precisa ter o `xml_sha256` e o
  `pdf_sha256` do pacote conferido.

**(b)** Cada pacote é lido uma vez, e o hash é calculado sobre esses bytes,
que vão para uma cópia privada num diretório temporário. `formulario` e o
leitor congelado (`anexos_pdf`, que recebe caminho) leem a cópia. O código
GEOM-1 não muda.

## A7 — nenhuma recusa depois de gravar (observação do parecer)

Antes de gravar qualquer arquivo acontecem:

- todas as leituras e recusas da busca: anexo único, texto legível e paginação;
- a autoverificação da identidade e do resultado.

Só no fim a identidade e o resultado são gravados, nessa ordem. Contraprova:
texto ilegível, paginação divergente, anexo não único e vazamento no
resultado não deixam arquivo.

## A8 — documentação (achado 7)

- **(a)** A autoverificação não vazia estava no C1. O relatório passa a falar
  em duas guardas não pedidas.
- **(b)** O sentido de `coluna` e de `tokens` passa a ser declarado na saída
  da busca e na comparação.
- **(c)** A ressalva do relatório de alcance passa a dizer o que acontece com
  o FCO:
  - nada sobre divisibilidade é publicado;
  - em memória, a autoverificação calcula piso e teto de cada valor comparado,
    inclusive das formas do FCO, só para barrar publicação.

  Esse uso é protetivo e segue o O1 como ele vem sendo aplicado desde o R3:
  comparação em memória para recusar publicação. Se o responsável entender que
  o O1 não cobre esse uso, a alternativa é tirar piso e teto das formas do FCO,
  e a proteção diminui.
- **(d)** O perfil dos tokens recusados e ambíguos vira artefato, só com
  contagens.
- **(e)** A frase "todo o resto é ambíguo" é corrigida junto com A2 a A4.

## Execução

Continuam preservados:

- o código da primeira execução (`1760c372…`);
- seus testes (`51276e50…`);
- o parecer e os relatórios que ele conferiu, em `conferencia_1/`.

Tudo o que é novo vai para `adendo/`, sem regravar a primeira execução:

- nova busca;
- nova reconferência dos artefatos de 24/09;
- autoverificação nova sobre as saídas da primeira execução, em memória;
- contraprovas da conferência de 25/09;
- comparação com 24/09 e com a primeira execução;
- perfil de tokens;
- mutações;
- suíte.

**Esperado, fixado antes de rodar:**

- o ativo de 140867 nas mesmas páginas, linhas, colunas e trechos, nos dois
  modos;
- nenhuma ocorrência ambígua do ativo;
- FCO dos dois documentos e ativo de 142900 sem correspondência.

A contagem de ambíguos pode subir, por A3 e A4a. A de recusados e a ordem de
coluna só podem mudar onde houver separadores consecutivos ou invisíveis
entre dígitos. Qualquer outra diferença é relatada, não ajustada.

Depois disso, o mesmo auditor reconfere.
