<!--
Parecer do auditor-conformidade (subagente somente leitura, contexto separado),
devolvido em 2026-09-25 sobre a primeira execução da correção RAG. Transcrito
na íntegra. É saída de modelo, não gold humano. Os caminhos [A], [T], [R] e [K]
apontam para as versões preservadas em `../codigo_primeira_execucao/` e em
`relatorio_conferido.md`, e para o contrato da correção. As sondas citadas em
[S] ficaram no scratchpad da sessão, fora do repositório.
-->

# Parecer: conferência independente, somente leitura, da onda de correção RAG (25/09) do instrumento de alcance GEOM-1

## Veredito: REABERTO, em dois pontos

Estão corrigidos os casos que a conferência de 25/09 reproduziu para RAG-01, RAG-02 e RAG-03. Estão confirmados RAG-04, C4, C5 e a preservação pedida em C6. As contraprovas da conferência não reproduzem mais. A busca e a reconferência no dado real conferem com o que foi publicado, e nenhum achado abaixo muda resultado publicado.

Não sustento o fechamento por dois motivos:
- **Contraprova de C1 que não exercita a decisão (regra 7).** O contrato exige que cada recusa estrutural do pin seja exercitada como decisão. O teste não faz isso, e o relatório afirma que faz.
- **A mesma classe do RAG-02 continua reproduzível.** Um sinal perdido vira correspondência positiva. É exatamente o padrão (só sintético, sem ocorrência real) que a conferência de 25/09 usou para negar o fechamento.

Não há achado ALTA. Nada aqui autoriza correção de escala, gate ou treino.

Caminhos citados abaixo:
- [A] = scripts/conferir_alcance_geom1_rank03b.py (1760c372…)
- [T] = tests/test_conferir_alcance_geom1_rank03b.py (51276e50…)
- [K] = resultados/contratos_correcao_rag_alcance_geom1_rank03b_2026-09-25.md (69797721…)
- [R] = resultados/correcao_rag_alcance_geom1_rank03b_2026-09-25.md
- [S] = scratchpad da sessão (sondas e mutações, fora do repositório)

Todos os achados estão **confirmados por execução**, sempre com números inventados. As mutações foram aplicadas em memória, por plugin pytest, sem tocar em arquivo do repositório.

## Achados

### 1. MÉDIA — C1: as recusas estruturais do pin não têm contraprova que exercite a decisão

**Evidência.** Plugin de uma linha (`monkeypatch.setattr(c, "validar_fontes", lambda pin: pin.get("fontes"))`, em [S]/x/mut.py), rodado com:

`CREWAI_STORAGE_DIR=$(mktemp -d)/crewai PYTHONPATH=.:[S]/x PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider -p mut tests/test_conferir_alcance_geom1_rank03b.py` → **248 passed**.

Mantendo só a checagem de lista não vazia, o resultado é o mesmo: 248 passed.

A sonda [S]/sonda/test_sonda_pin.py mostra o que acontece nos sete pins malformados, nas duas entradas:
- Com a estrutura presente, quem recusa é a mensagem estrutural: "pin sem fontes…", "fonte do pin malformada" ou "fonte repetida no pin".
- Sem a estrutura, os 7×2 casos continuam recusados, mas pela vinculação: "pin de execução não aponta para o pin de alcance fixado" em [A]:616-617, ou "pin da revisão aponta para outro pin ou outras fontes" em [A]:701-702.
- As duas mensagens casam com `match="pin"` em [T]:683.
- O teste refixa só `PIN_ALCANCE_SHA256` ([T]:682). Não refixa `pin_execucao.pin_sha256` nem `pin_revisao`, então a vinculação por hash sempre decide.
- Não existe teste unitário de `validar_fontes` ([A]:134-150).

**Contrato.** [K]:52-56 pede "referências trocadas pelos hashes de arquivos sintéticos, para exercitar a decisão e não só o hash, cada recusa estrutural e de universo falha antes de gravar". O docstring em [T]:679 e [R]:20 ("para que quem decida seja a estrutura") afirmam o que o teste não garante.

**Por que importa.** O código hoje está certo. Mas uma regressão que retire qualquer uma destas checagens passaria com a suíte verde:
- lista vazia;
- `id_doc` não numérico (`../900002` sairia de `BRUTOS`);
- hash malformado;
- fonte repetida.

As recusas de universo, ao contrário, estão isoladas: com `exigir_mesmo_universo` anulada, 8 testes falham.

**Critério de fechamento.**
- Refixar também as referências seguintes para o pin malformado: `pin_execucao.pin_sha256` (em `executar`) e `pin_revisao.pin_alcance_sha256` e `fontes` (em `reconferir_publicados`).
- Casar a mensagem estrutural específica, ou acrescentar testes unitários de `validar_fontes`.
- Mostrar por mutação que retirar cada checagem derruba ao menos um teste.
- Corrigir [R]:20 e o docstring.

### 2. MÉDIA — C2: caractere de formatação (Cf) entre sinal e número apaga o sinal (classe do RAG-02)

**Evidência.** Comando:

`PYTHONPATH=. .venv/bin/python -c "…ocorrencias(['Total −​1.234','Total (​1.234​)'], {'a': D(1234)}, por_modulo=False)…"`

- Resultado: **2 correspondências positivas**.
- `ocorrencias_de_sinal_ambiguo` sobre as mesmas linhas devolve `[]`.
- O mesmo vale para U+2060, U+FEFF, U+200E e U+200F ([S]/c2_casos.py).

**Causa.** `str.isspace()` é falso para caracteres Cf. Com isso:
- `_contexto_esquerdo` encerra o contexto no `break` ([A]:241-242);
- `_sinal` devolve +1 quando o núcleo fica vazio ([A]:272-273);
- o `lstrip()` do lado direito não remove Cf ([A]:261).

**Contrato.** O código cumpre a letra de [K]:77-88: o contexto é espaço, moeda, sinal e parêntese. Mas contradiz a intenção ("qualquer outra combinação" é recusa explícita) e a frase de [R]:22 ("todo o resto é ambíguo"). Também não atende o critério da conferência para o RAG-02: "recusar explicitamente a forma não suportada".

**Dado real.** Zero caracteres Cf no texto dos dois documentos, nos dois modos (contagem em [S]/pdf_contagens.py). O resultado publicado não muda. Não verifiquei outros emissores; em PDF gerado por navegador ou editor, a ocorrência é plausível.

**Critério de fechamento.** Adendo ao contrato e código que tratem Cf e separadores invisíveis colados entre sinal ou parêntese e o token como ambíguos (ou como espaço), com contraprova para cada caractere.

### 3. BAIXA — C2: a contraprova de "todos os caracteres MINUS" não foi entregue

**Evidência.**
- `_tracos()` ([A]:184-189) tem 48 caracteres: 26 da categoria Pd e 22 com "MINUS" no nome.
- [T]:378 testa só 5 dos 22.
- Restringindo `menos` aos 31 caracteres testados ([S]/mutante2.py, `menos_so_pd_e_5`): **248 passed**.
- Ficam sem teste, entre outros:
  - U+2052 COMMERCIAL MINUS SIGN (menos legítimo);
  - U+2756 ❖ (marcador de lista);
  - U+2216 SET MINUS;
  - U+293C (seta);
  - U+0320 (caractere combinante);
  - U+E002D (TAG, invisível).
- `"❖1.234"` sai com sinal −1. Não casa com o ativo positivo e não entra na lista de ambíguos, então a ausência é silenciosa.

**Contrato.** [K]:113 pede "**todos** os caracteres `Pd` e `MINUS`". [R]:22 diz "31 formas… montadas a partir da tabela Unicode e não da implementação", mas só os 26 Pd vêm da tabela; os 5 restantes foram escolhidos à mão.

**Dado real.** Nenhuma ocorrência dos 17 caracteres não testados ([S]/pdf_contagens2.py).

**Critério de fechamento.** Derivar a expectativa da tabela Unicode também para MINUS, ou restringir a regra por contrato e decidir o que fazer com glifos que não são sinal de menos.

### 4. BAIXA — C2: duas leituras não declaradas dão sinal onde a letra do contrato pede ambíguo

- **(a) Sinal colado depois do token e seguido de dígito é ignorado** ([A]:269, `not depois.isdigit()`).
  - `"Total 1.234.567-8"` casa +1234567.
  - O contrato inclui "sinal colado ao token" no contexto direito e classifica "sinal depois do token" como ambíguo ([K]:79-80, 85-88).
  - [T]:399 fixa `2024-2025` com 2024 positivo.
  - No dado real, essa exceção pega 3 tokens por documento e modo. Nenhum deles tem o módulo de um alvo do ativo (checagem só booleana, [S]/pdf_ativo_bool.py).
- **(b) `"−R$ 1.234"` sai −1** ([T]:353 e 386), com o menos colado à moeda e a moeda separada do número.
  - A leitura natural de "colado ao token ou a uma moeda colada a ele" ([K]:83-84) exige a moeda colada ao número.
  - Se a leitura estiver errada, a ocorrência some sem aviso: sai negativa, não ambígua.

**Critério de fechamento.** Declarar as duas leituras no contrato e no relatório, ou torná-las ambíguas. Em qualquer caso, com contraprova.

### 5. BAIXA — C3: a equivalência ainda depende de uma lista fechada de separadores (classe do RAG-03)

**Evidência** ([S]/c3_casos.py). Para o valor inventado 1234567, passam sem ser barradas:
- `1 234 567`, com FIGURE SPACE, que é o espaço tipográfico feito para algarismos;
- U+2008, U+2006, U+200A e U+3000;
- `1'234'567`, `1’234’567`, `1_234_567` e `1·234·567`;
- vírgula de largura cheia e ZWSP entre os grupos;
- `1234567e2024` e `1234567E-1`: `_leituras` ([A]:372-381) nunca lê a mantissa sem o expoente.

**Contrato.** [K]:130-133 enumera quatro espaços, e o código cumpre essa letra.

**Por que é BAIXA.** Hoje não há canal real que leve esse texto à saída. O trecho é mascarado com `\s`, que cobre U+2007, e ainda barrado se tiver dígito; o resto da saída são identificadores e textos fixos.

**Critério de fechamento.** Tratar todo `Zs`, apóstrofos e sublinhado como separador de grupo e ler também a mantissa sem expoente, ou declarar o limite.

### 6. BAIXA — C1: a fonte é vinculada só por `id_doc`, e o ZIP é relido depois do hash

**Troca de versão aceita** (sonda [S]/sonda/test_sonda_versao.py):
- inventário com o mesmo `id_doc` e outro `sha256`/`sha256_pdf`: `executar` conclui;
- conferência com outro `xml_sha256`/`pdf_sha256`: `reconferir_publicados` conclui.

A causa é que `exigir_mesmo_universo` ([A]:153-161) compara só `id_doc`, enquanto [K]:45-46 manda recusar "substituição".

**ZIP relido.** O hash é calculado lendo o arquivo (scripts/fonte_rad_cvm.py:146-151). Depois, `formulario` ([A]:459-467) e `anexos_pdf` (scripts/reconhecer_geometria_rank03b.py:61-65) reabrem o arquivo, então os bytes interpretados não são os que tiveram o hash conferido. [R]:20 ("toda entrada é lida uma vez e tem o hash dos mesmos bytes") exagera no caso das fontes.

O defeito é latente: com as constantes reais, não acontece.

**Critério de fechamento.** Comparar os `sha256` dos registros e documentos com o pin, e ler o ZIP uma vez e interpretar esses bytes; ou declarar o limite.

### 7. BAIXA — documentação

- **(a)** [R]:27-37 lista "três guardas que o contrato não pedia". A segunda ("a autoverificação não pode ser vazia") está explícita no C1 ([K]:47-48).
- **(b)** Mudança de sentido de `coluna` e de `tokens` não declarada.
  - [K]:95-97 exige que a mudança de sentido de `coluna` seja declarada na comparação.
  - Nem `comparacao_com_24_09.json`, nem `busca/conferencia_revisao.json`, nem [R] a declaram. Só existe o booleano `coluna_so_mudaria_pelo_novo_sentido`, calculado como igualdade.
  - `tokens` também mudou de sentido e não é declarado em lugar nenhum.
- **(c)** Frase inexata sobre divisibilidade do FCO.
  - resultados/alcance_geom1_rank03b_2026-09-24.md:372-373 diz "Para o FCO nada foi calculado sobre divisibilidade".
  - Porém `_magnitudes_protegidas` ([A]:392) testa em memória se cada valor comparado, inclusive FCO/1000, é inteiro, para decidir piso e teto (é o que o C3 pede).
  - Nada disso é publicado e não há vazamento. Ainda assim a frase é inexata, e a tensão entre C3 e C4 não está registrada.
- **(d)** As afirmações qualitativas de [R]:103-108 e 114-117 não têm artefato que as sustente. Conferem na minha recontagem, feita só com contagens:

  | Documento | Datas recusadas | Fora da gramática | Coladas a separador | Ambíguos com 2+ sinais |
  |---|---:|---:|---:|---:|
  | 140867 | 80 | 61 | 0 | 171/291 |
  | 142900 | 64 | 56 | 0 | 137/242 |

  Nenhum código ISO colado a dígito, e os números são iguais nos dois modos.
- **(e)** A frase de [R]:22, "o sinal só vale nas formas explícitas… todo o resto é ambíguo", é contradita pelos achados 2 e 4.

## O que foi confirmado

- **Hashes.**
  - Contrato 69797721…; os 13 hashes da tabela de [R] conferem.
  - O código preservado (b0272037…) é o `codigo_sha256` registrado em `verificacao.json`.
  - `reproduzir_achados.py` continua 4fdb7f89….
- **Item 4.** `verificar_nao_reproducao.py` produz saída idêntica a `nao_reproducao.json`: `nenhum_reproduz: true`, `pin_vazio` recusado pelo hash, controles mantidos.
- **Item 5.**
  - Testes focados: 248 + 155 = **403 passed**.
  - `pytest_suite.xml` da onda: 3.297 testes, 0 falhas, erros ou skips, 152,734 s.
  - O XML foi gerado às 19:45, depois da última edição do código (19:40) e dos testes (19:42).
  - O acréscimo de +186 é exatamente 248 − 62, no arquivo da busca.
- **Item 3.** Pela comparação da AST, mudaram só três testes preexistentes, todos declarados no docstring e em [R]:
  - duas substituições;
  - um ajuste só de pré-condição, com as asserções intactas.

  A substituição do teste de sinal usa a mesma linha e os mesmos caracteres U+2010 e U+2212. A de isenção ficou mais estrita e ganhou um caso negativo. Não houve enfraquecimento.
- **Mutações detectadas pelos testes.**
  - hash das entradas: 13 testes;
  - autoverificação da identidade: 1;
  - autoverificação vazia: 3, só em nível unitário;
  - universo: 8;
  - isenção pela forma: 7;
  - piso e teto: 2;
  - máscara da mensagem: 1;
  - também detectadas: sinal separado, ambíguo tratado como positivo, coluna, ISO colado, espaço fino.
- **Ordem do C1.**
  - Todas as entradas fixadas são lidas uma vez e têm o hash conferido antes de qualquer `json.loads` ([A]:604-611 e 697-698).
  - A identidade é autoverificada antes de ser gravada ([A]:640-642).
  - Nenhuma recusa de hash, estrutura, universo ou vínculo acontece depois de gravar.
  - Observação, não desvio do contrato: as recusas da busca (texto ilegível, paginação, anexo não único, vazamento no resultado) acontecem depois de `pin_revisao.json` gravado. É o desenho desde 24/09, e esse estado não tem contraprova.
- **Itens 7 e 8.**
  - Artefatos de 24/09 e evidências da conferência iguais a `verificacao.json` e à tabela N1; inventário 4bb25cf0… e seleção b3e85417… conferem.
  - O relatório de alcance só recebeu acréscimo: o prefixo de 21.228 bytes tem sha256 0b7922b5…, o valor conferido.
  - Depois de 19:27:32, quando a pasta da onda foi criada, só mudaram os arquivos esperados.
  - Consumidor, construtor, gates, adjudicador e CSV conferem com as referências CRF, com datas de 17 e 18/09.
  - GEOM-1 e inventário conferem: f0e3baa9, e02a2a97, 27160c30 e 57902e1d.
  - `AGENTS.md` e o rascunho v2 têm datas de 25/09 entre 00:10 e 00:11, antes da onda.
- **Item 9.** Nenhuma saída tem dígito em `trecho` ou número ≥ 1.000. Os dígitos que aparecem são identificadores, e `fco_paginas` estão todas vazias.
- **Números e reconferência.**
  - Os números de [R] conferem: 141/28/291 e 120/25/242, iguais nos dois modos.
  - Os documentos da reconferência nova são idênticos aos de `reconferencia_pos_auditoria.json` e `reconferencia_independente.json`.
  - Todas as expectativas de C6.3 foram cumpridas.
- **RAG-04.** A frase em MEMORY.md:462 está correta, e o v2 tem seis `[DECIDIR]`.
- **Pendências fora do escopo** (B4, os `[DECIDIR]`, executor v2, forma arredondada, refino de sinais) estão descritas no relatório sem distorção.

## O que não foi verificado, e por quê

- **Suíte completa:** não rodei de novo, para não gerar efeito colateral no repositório. Usei o XML da onda e os 403 testes focados.
- **Precedência do contrato:** o sistema de arquivos só guarda a última escrita (contrato 19:28:21, código 19:40:01), então não dá para provar que o contrato veio antes da primeira edição do código. A versão final do código cita o hash do contrato.
- **`verificacao.json` da conferência:** foi regravado às 18:44:46, antes desta onda, e não existe hash anterior registrado para comparar.
- **Estado do `.env` durante a suíte:** não é verificável.
- **Execução real completa:** não repeti, por causa do O1. No dado real fiz só duas coisas:
  - contagens sobre o texto dos PDFs;
  - booleanos com a conta 1 via `alvos_ativo`.

  `formulario` carrega o XML como faz a produção, mas `alvos_fco` e o 6.01 nunca foram acessados, e nada foi gravado.
- **Holdout:** só apareceu na varredura de datas; o conteúdo não foi aberto.
