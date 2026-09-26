# Correção RAG-01 a RAG-04 do instrumento de alcance GEOM-1

Data: 2026-09-25. Onda de correção dos achados da
[conferência independente de 25/09](conferencia_revisao_alcance_geom1_rank03b_2026-09-25.md),
sob o [contrato da correção](contratos_correcao_rag_alcance_geom1_rank03b_2026-09-25.md)
(`69797721…`), escrito antes do código. Evidência:
`artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/`.

**Resultado:** os três defeitos técnicos foram corrigidos, e as contraprovas da
própria conferência, rodadas sem alteração contra o código novo, não
reproduzem nenhum deles. A busca repetida nas mesmas fontes dá o mesmo
resultado de 24/09, como o contrato previa antes de rodar. O instrumento
continua **não adjudicando escala**; nada aqui autoriza correção, gate ou
treino.

**Atualização do mesmo dia (adendo):** a conferência independente desta primeira execução
**reabriu a onda** (2 MÉDIA, 5 BAIXA, nenhum ALTA, nenhum resultado publicado alterado). O
[adendo ao contrato](adendo_correcao_rag_alcance_geom1_rank03b_2026-09-25.md) tratou os sete
achados; o que mudou está em [Adendo pós-conferência](#adendo-pós-conferência-2509). As seções
abaixo, até ela, descrevem a primeira execução e ficam como foram escritas, com marcas onde a
conferência as desmentiu.

## O que mudou

| Achado | Correção | Contraprova |
|---|---|---|
| **RAG-01** — a reconferência tirava o universo de um `pin.json` não conferido; com `fontes: []`, aprovava sem examinar nada | **C1.** Nas duas entradas (`executar` e `reconferir_publicados`), toda entrada é lida uma vez e tem o hash dos mesmos bytes conferido antes de qualquer uso; o pin precisa ter fontes, sem repetição; pin, saídas publicadas e inventário precisam ter o mesmo universo, na mesma ordem | o cenário exato da conferência, nas duas entradas; sete pins malformados com o hash refixado, para que quem decida seja a estrutura; conferência, pin da revisão e inventário com outro universo; controle positivo com duas fontes sintéticas pelo caminho inteiro. *(Corrigido no adendo, achados 1 e 6: a contraprova estrutural não isolava a estrutura — a vinculação recusava antes —, e os pacotes das fontes eram relidos depois do hash.)* |
| Acréscimo da conferência da conferência: **`pin_execucao.json` e `selecao.json`**, as referências do código congelado e dos sete protegidos, também eram lidas sem conferência | **C1.** Fixadas por hash (`bb2059f3…`, `b3e85417…`), assim como os contratos que governam cada entrada | referência alterada e contrato diferente do fixado são recusados, sem gravar nada |
| **RAG-02** — `1.234.5678` casava `1234567`; `-  1.234` e `(R$ 1.234)` casavam positivo | **C2.** O token é a sequência máxima de dígitos, e só é comparado se estiver **inteiro** na gramática pt-BR; o resto é recusado e contado. O sinal só vale nas formas explícitas do contrato (parênteses equilibrados, com espaço e moeda; traço ou menos colado); todo o resto é **ambíguo**, uma recusa explícita. Ativo ambíguo sai numa lista à parte, nunca como correspondência | os três casos da conferência; ausência falsa; as 31 formas de traço e menos, coladas e separadas, montadas a partir da tabela Unicode e não da implementação; formas aceitas e ambíguas; colunas vizinhas; formas recusadas. *(Corrigido no adendo, achados 2 a 4: invisível entre sinal e número, "outro sinal" como ❖ e sinal colado depois do token seguido de dígito ainda davam sinal; das 31 formas, só as 26 da categoria Pd vinham da tabela.)* |
| **RAG-03** — `1.234.567,00`, `1234567.00`, `1 234 567,00` e `1.234.567,50` passavam pela autoverificação; a mensagem repetia a chave | **C3.** Equivalência numérica: cada número publicado é lido de dois jeitos e comparado com o módulo, o piso e o teto de cada valor comparado ≥ 1.000. A isenção vale pela forma: só hash de verdade e só data de verdade. Tipo não previsto derruba. Mensagem com dígitos mascarados | os oito casos, mais expoente, zeros, arredondamento, espaço fino, sinal e parênteses, em texto, chave e lista; isenção pela forma; tipo não previsto |
| Acréscimo: **forma ÷1.000 inerte** | **C4.** Limite declarado no campo `limite`, sem dígitos, e na [ressalva do relatório de alcance](alcance_geom1_rank03b_2026-09-24.md). Para o ativo, a saída lista as formas que só casariam se as notas imprimissem as casas decimais | alvo não inteiro listado; texto do limite sem dígito |
| **RAG-04** — "cinco decisões" no bloco CRF de 18/09 | **C5.** Uma frase no MEMORY.md: as cinco eram as de 18/09; desde 24/09 são seis | — |

Três guardas que o contrato não pedia, achadas durante a implementação e
cobertas por contraprova *(corrigido no adendo, achado 7a: a segunda estava no C1; as não pedidas eram duas)*:

- **A identidade da execução era gravada sem autoverificação.** O
  `pin_revisao.json` saía antes de os valores serem conhecidos. Agora os
  valores do XML são lidos em memória primeiro, e a identidade só é gravada
  depois de verificada. Contraprova: um metadado do pin igual a um valor
  comparado derruba a execução antes de gravar qualquer arquivo.
- **A autoverificação não pode ser vazia.** Gravar exige ao menos um valor
  comparado com módulo ≥ 1.000. Com o pin vazio de antes, ela devolvia `true`
  sem ter o que comparar.
- **Código ISO colado ao número.** Em `−USD1.234`, a checagem de fronteira
  deixava o menos de fora, e o número saía positivo. Mesma classe do RAG-02.

A data registrada na identidade passou a ser a da execução. Antes era fixa em
24/09, e o replay da conferência a herdou.

## Substituições de teste, declaradas

Estão declaradas no docstring de cada caso, conforme o §4.4 do AGENTS.md.

- `test_numeros_da_linha_com_sinal_por_parenteses_e_por_traco_unicode` →
  `test_tokens_da_linha_sinal_colado_vale_e_sinal_separado_e_ambiguo`.
  - O caso antigo fixava `− 1.000` → −1.000 e `‐ 5` → −5, com sinal separado do
    número por espaço, e isso passa a ambíguo.
  - Motivo: no `-raw`, o traço de "sem valor" de uma coluna seguido do valor da
    coluna seguinte tem exatamente essa forma.
  - A mesma linha continua verificada inteira, e o sinal colado segue
    negativo, com os mesmos caracteres.
- `test_autoverificacao_isenta_so_hash_e_data` →
  `test_autoverificacao_isenta_hash_e_data_pela_forma`.
  - O caso antigo usava `"1234567"` como hash e como `dt_refer`, isentos só pelo
    nome do campo.
  - O novo usa hashes de 64 hexadecimais que contêm o valor e verifica que o
    mesmo texto, fora do campo de hash, é barrado.
  - Os falsos viraram contraprova: `test_isencao_nao_cobre_o_que_nao_tem_a_forma`.
- `test_codigo_congelado_alterado_derruba_antes_de_gravar_pin`: mudou só a
  pré-condição, que agora fixa os hashes dos pins falsos. As asserções ficaram
  intactas.

## Execução no dado real (C6)

Preservados antes da primeira edição, em `codigo_sob_conferencia/`: o código
que a conferência examinou (`b0272037…`) e seus testes (`8f0a339e…`).

1. **As contraprovas da conferência não reproduzem**
   (`nao_reproducao.json`). O `reproduzir_achados.py` rodou sem alteração
   (`4fdb7f89…`).
   - `pin_vazio` é recusado pela guarda nova.
   - `parser` e `autoverificacao` param na primeira contraprova, com "deixou de
     reproduzir".
   - Os 3 + 8 casos, rodados um a um, também não reproduzem.
   - Os controles se mantêm: o positivo inteiro casa, e `1.234.567` segue
     barrado.
2. **Busca repetida** (`busca/`), nas mesmas fontes fixadas, em pasta nova.
   **Não é teste cego:** os resultados de 24/09 e a medição em memória de
   25/09 eram conhecidos. Todas as expectativas fixadas no contrato antes de
   rodar se cumpriram (`comparacao_com_24_09.json`):
   - o ativo de 140867 aparece nas mesmas páginas, linhas, colunas e tokens de
     24/09, nos dois modos, com os mesmos trechos;
   - não há ocorrência ambígua do ativo;
   - o FCO dos dois documentos e o ativo de 142900 seguem sem correspondência;
   - a concordância entre os modos, a identidade de caixa e o reinventário são
     iguais aos de 24/09.
3. **Reconferência dos artefatos de 24/09** sob C1 e C3
   (`reconferencia.json`): os dois arquivos passam na autoverificação nova. Os
   documentos saíram idênticos aos da reconferência anterior, e os sete
   protegidos estão íntegros.

**O que a medição nova mostra, e não decide nada:**

| Documento | Tokens recusados (páginas) | Tokens de sinal ambíguo |
|---|---:|---:|
| 140867 | 141 (28) | 291 |
| 142900 | 120 (25) | 242 |

*(Números da primeira execução. No adendo, os ambíguos são 294 e 245 — +3 por
documento e modo, efeito do A4a —, e o perfil por motivo que sustenta o parágrafo abaixo está em
`adendo/perfil_de_tokens.json`.)*

Os números são iguais nos dois modos. As recusas são datas e números com
formato fora da gramática. Nos ambíguos, a maior parte tem **mais de um sinal
à esquerda**: são os traços de "sem valor" das colunas vizinhas, que o C2, pela
letra, inclui no contexto do token. A regra é conservadora por contrato. Um
ativo numa linha dessas apareceria na lista de ambíguos, não como
correspondência e não em silêncio. Nos dois documentos isso não aconteceu.
Refinar a regra para olhar só o sinal colado ao token reduziria esses falsos
ambíguos, mas exige contrato próprio.

## Fora do escopo — registrado, não corrigido

- **Máscara do inventário com ISO colado ao número.** `\b(?:USD|…)\b` não reconhece
  `USD1.234`, e em `−USD1.234` o menos ficaria no trecho do inventário. É um
  canal latente, sem ocorrência no dado real, porque as notas usam `R$` e
  `US$`. O inventário está congelado nesta onda.
- **Forma arredondada.** Para o ativo, é medição nova e exige contrato. Para o
  FCO, não é igualdade, e o O1 só autoriza igualdade: decisão do responsável.
- Continuam pendentes: **B4** (o consumidor não confere o cabeçalho do
  manifesto), os seis **[DECIDIR]** do v2 e o executor v2.

Consumidor, construtor, CSV de correções, painéis, gates, código GEOM-1,
inventário, os sete protegidos e o holdout ficaram intactos: hashes e datas
conferidos. Nenhum montante ou sinal de FCO foi impresso ou gravado. Não houve
fonte nova, download, API, alvo, T1/T2, baseline ou treino.

## Suíte (primeira execução)

Suíte completa, com o `.env` local ativo e sem sobrescrever variável:
**3.297 passed, zero falhas/erros/skips**, 152,7 s
(`pytest_suite.xml`). São **+186 contraprovas da busca** sobre as 3.111 da
conferência, com as duas substituições e o ajuste de pré-condição declarados
acima. Arquivos focados: 248 da busca (eram 62) e 155 do inventário, sem
mudança.

## Conferência independente (primeira execução)

**REABERTO em dois pontos** pelo auditor-conformidade, somente leitura, em contexto separado: 2 MÉDIA,
5 BAIXA, nenhum ALTA. Confirmou a não reprodução dos defeitos da conferência de 25/09, os hashes, a
preservação e os resultados reais, e achou o que o adendo trata. Parecer na íntegra:
`conferencia_1/parecer_auditor.md`; relatórios que ele conferiu: `conferencia_1/`.

## Hashes (primeira execução)

| Artefato | SHA-256 |
|---|---|
| contrato da correção | `6979772114c4eeb0a8ac3ee832329e12e764b3091ec2242435423fc06a839e78` |
| `scripts/conferir_alcance_geom1_rank03b.py` (corrigido) | `1760c37244db76874bc4386afc069c72633322b53582cb797eb4346190cd89d7` |
| `tests/test_conferir_alcance_geom1_rank03b.py` | `51276e50b58880444e7a66cb0bd80d5dce8cad17668e6811b014ebc030950a69` |
| `pytest_suite.xml` | `8999066a7d9172e0fdc398be7bba2fb5b6b7d63be26917e9cf7234f8b1f90545` |
| `codigo_sob_conferencia/conferir_alcance_geom1_rank03b.py` | `b02720373cded4b2eded22b0dcaf209cbbfe2d73bfb33f8db8b28d39bc89f053` |
| `codigo_sob_conferencia/test_conferir_alcance_geom1_rank03b.py` | `8f0a339ed3f3d723ebbb9801ddfbb780486cd279bc027c0e55393adefa4bbf2d` |
| `busca/pin_revisao.json` | `5a98d2e212608dc6149d622d18e2cd2e93f19034095b7d038c7c20d125886413` |
| `busca/conferencia_revisao.json` | `b42c7bced791ef3d1fdc07b8df293d8c90b5347ced7005251ce564bdd41e651f` |
| `reconferencia.json` | `719cb65daff2ba49671a5f942543c50c9db8abd100999c2e596cfd71f5a69add` |
| `nao_reproducao.json` | `34e5a1a604fe1fc65a386c037c16b40fbf2dc5e741193fe83f8575d01fc36474` |
| `comparacao_com_24_09.json` | `1d6eb0f7318e01f2dc1814b0c5e172eb44faaa4d49be4f4b0f787eccc48fed1c` |
| `verificar_nao_reproducao.py` | `89b27a238ee0bafa98b18f942c006e2d678e5c7bacd396459671ee90b2fba714` |
| `comparar_com_24_09.py` | `94430535186afcd47bf271848edd64bad0712e8d8e53f555dc0373f651091436` |

## Adendo pós-conferência (25/09)

O [adendo ao contrato](adendo_correcao_rag_alcance_geom1_rank03b_2026-09-25.md) (`af03e314…`)
foi escrito antes de editar. Código e testes da primeira execução estão preservados em
`codigo_primeira_execucao/`; tudo o que é novo está em `adendo/`, sem regravar a
primeira execução.

| Achado da conferência | Correção (adendo) |
|---|---|
| **1 (MÉDIA)** — a contraprova estrutural do pin não isolava a estrutura | **A1.** Pin de execução, pin da revisão, conferência e inventário espelham o pin malformado; cada caso casa a própria mensagem; teste unitário de `validar_fontes`; controle mostrando que o espelhamento sozinho não recusa |
| **2 (MÉDIA)** — invisível (Cf) entre sinal e número apagava o sinal | **A2.** Invisível no contexto de um token com sinal ou parêntese: ambíguo. Dentro do número: token recusado. Contraprova para os 220 invisíveis da tabela |
| **3 (BAIXA)** — "todos os MINUS" não testados; ❖ negava | **A3.** Nega o que é Pd ou se normaliza no MINUS SIGN (29); afirma o que se normaliza em `+` (6); parêntese pela NFKC (6 de cada lado); os outros 108 sinais da classe são "outro sinal", portanto ambíguos. Toda expectativa derivada da tabela |
| **4 (BAIXA)** — duas leituras não declaradas | **A4a.** Sinal colado depois do token passa a ambíguo, mesmo seguido de dígito (`1.234.567-8`). **A4b.** `-R$ 1.234,00` segue negativo, agora como leitura declarada |
| **5 (BAIXA)** — separadores de milhar em lista fechada | **A5.** NFKC, sem invisíveis; separador é qualquer caractere que não seja letra nem dígito (inclusive sublinhado e letra modificadora); a mantissa é lida também sem expoente |
| **6 (BAIXA)** — fonte vinculada só pelo id; pacote relido depois do hash | **A6.** Inventário e conferência publicada conferidos também pela versão (`sha256`, `sha256_pdf`, `xml_sha256`, `pdf_sha256`); o pacote é lido uma vez e os leitores abrem uma cópia privada com os mesmos bytes |
| **7 (BAIXA)** — documentação | **A8.** Marcas acima; sentido de `coluna` e `tokens` declarado na saída (`sentido_de_coluna`) e na comparação; ressalva do relatório de alcance corrigida; perfil de tokens publicado |
| Observação — recusas depois de gravar | **A7.** Leituras, recusas e autoverificação acontecem antes de gravar; identidade e resultado são gravados no fim |

**Mutação (A1).** O `adendo/verificar_mutacoes.py` troca, em memória, 45 trechos do código:
- cada checagem de C1 a C3;
- cada regra de A2 a A7.

Um controle sem mutação passa inteiro, pelo mesmo caminho. Nenhum arquivo do repositório é editado.

- **Rodada 1** (`mutacoes_rodada_1.json`): 43 mortas e 2 sobreviventes, e as duas eram contraprovas imprecisas, não defeito de código.
  - Documento repetido no universo: o teste casava só o prefixo da mensagem, e a igualdade de listas também recusava.
  - Normalização NFKC: os casos testados já passavam sem ela.
  - A correção foi casar a mensagem específica e acrescentar os dígitos de compatibilidade (sobrescrito, circulado, subscrito), que só a NFKC lê.
- **Rodada 2** (`mutacoes.json`): **45 de 45 mortas**, controle com 927 passed. Registra o código (`ebe90e3e…`) e os testes (`f74d5745…`) finais.

**Testes da primeira execução que mudaram no adendo** — oito, conferidos por AST contra
`codigo_primeira_execucao/`, declarados no docstring quando mudam expectativa:
- `test_pin_malformado_com_hash_conferido_e_recusado` → `test_pin_malformado_e_recusado_pela_estrutura`
  (A1: o antigo passava sem a regra estrutural);
- `test_todo_traco_ou_menos_colado_nega_e_separado_e_ambiguo` e
  `test_mais_colado_e_positivo_e_separado_e_ambiguo`: listas passam a vir da tabela; `➖`, `˗` e `➕`
  saem e viram "outro sinal" (A3);
- `test_colunas_vizinhas_nao_contaminam_o_sinal`: `2024-2025` passa a ambíguo dos dois lados (A4a);
- `test_reconferencia_recusa_conferencia_de_outro_universo` e
  `test_inventario_de_outro_universo_e_recusado`: casam a mensagem específica (rodada 1 das mutações);
- `test_controle_positivo_examina_exatamente_as_duas_fontes_nas_duas_entradas` e
  `test_documento_governante_diferente_do_fixado_e_recusado`: só ganharam asserções (sentido de
  coluna, adendo fixado por hash).

Nenhum dos 30 testes anteriores a esta onda mudou no adendo; os três que mudaram na primeira
execução seguem como estavam.

### Execução no dado real (adendo)

- **Contraprovas da conferência de 25/09** (`adendo/nao_reproducao.json`): seguem sem reproduzir. `pin_vazio` é recusado pela guarda; os 3 + 8 casos não passam.
- **Busca** (`adendo/busca/`), nas mesmas fontes. **Não é teste cego.** As expectativas fixadas no adendo antes de rodar se cumpriram, contra 24/09 e contra a primeira execução (`adendo/comparacao_com_24_09.json`, `adendo/comparacao_com_primeira_execucao.json`):
  - o ativo de 140867 aparece nas mesmas páginas, linhas, colunas e trechos;
  - nenhuma ocorrência do ativo é ambígua;
  - o FCO dos dois documentos e o ativo de 142900 seguem sem correspondência;
  - concordância dos modos, identidade de caixa, reinventário e versões do XML e do PDF são iguais.

  Os ambíguos subiram de 291 e 242 para **294 e 245**: são os 3 tokens por documento e modo com sinal colado depois, efeito do A4a. Os recusados não mudaram (141 e 120).
- **Reconferência dos artefatos de 24/09** (`adendo/reconferencia.json`): passam na autoverificação do adendo. Os documentos são idênticos aos das reconferências anteriores, e os sete protegidos estão íntegros.
- **Saídas da primeira execução**, sob a autoverificação do adendo (`adendo/autoverificacao_primeira_execucao.json`): as duas passam.
- **Perfil dos tokens** (`adendo/perfil_de_tokens.json`), só contagens e sem ler o XML:

  | | 140867 | 142900 |
  |---|---:|---:|
  | tokens | 3.158 | 2.769 |
  | aceitos limpos | 2.320 | 2.062 |
  | aceitos negativos por parênteses | 403 | 342 |
  | aceitos com menos colado | 0 | 0 |
  | recusados (com forma de data) | 141 (80) | 120 (64) |
  | ambíguos: vários sinais | 171 | 137 |
  | ambíguos: sinal seguido de espaço | 54 | 41 |
  | ambíguos: parêntese sem par (fecha / abre) | 46 / 19 | 42 / 21 |
  | ambíguos: sinal depois do token | 3 | 3 |
  | ambíguos: colado a palavra | 1 | 1 |

  Os números são iguais nos dois modos. Nas notas destes dois documentos o negativo é sempre de parênteses: não há menos colado. O caso mais comum de ambíguo é o de "vários sinais", os traços de coluna vizinha, e é conservador por contrato.

### Leituras e limites declarados

- **A4b:** o menos colado à moeda, com a moeda separada do número por espaço, é negativo.
- **FCO, piso e teto (A8c):** a autoverificação calcula em memória o piso e o teto de cada valor comparado, inclusive das formas do FCO, só para barrar publicação. Nada disso é publicado. É o uso protetivo que o O1 tem desde o R3; se o responsável entender que o O1 não o cobre, a alternativa é tirar piso e teto das formas do FCO, e a proteção diminui.
- **Vários sinais:** refinar para olhar só o sinal colado ao token exige contrato próprio. A forma arredondada e o B4 seguem como na primeira execução.

### Suíte (adendo)

Suíte completa, com o `.env` local ativo e sem sobrescrever variável:
**3.976 passed, zero falhas/erros/skips**, 152,2 s (`adendo/pytest_suite.xml`), gerada depois da
última edição de código e testes. São 927 testes da busca, contra 248 na primeira execução e 62
antes da onda, e os 155 do inventário não mudaram.

### Nova conferência

PENDENTE_CONFERENCIA_ADENDO

### Hashes do adendo

| Artefato | SHA-256 |
|---|---|
| adendo ao contrato | `af03e314b2406d3c7852f449ec554d58824cb7bde3ba99e81f6e7afbfb32e676` |
| `scripts/conferir_alcance_geom1_rank03b.py` | `ebe90e3e594e95607be2e3be9b979402d1233a7827c07329d52d799f3487a735` |
| `tests/test_conferir_alcance_geom1_rank03b.py` | `f74d5745c3dda910aa31c8272c7b10a99e7c21fbe49c40d2b2e84d459eeecdc4` |
| `codigo_primeira_execucao/conferir_alcance_geom1_rank03b.py` | `1760c37244db76874bc4386afc069c72633322b53582cb797eb4346190cd89d7` |
| `codigo_primeira_execucao/test_conferir_alcance_geom1_rank03b.py` | `51276e50b58880444e7a66cb0bd80d5dce8cad17668e6811b014ebc030950a69` |
| `conferencia_1/parecer_auditor.md` | `b06899111e27657cefe76d5af8df1e75580f73e76362ef9a18c8616c9240debc` |
| `conferencia_1/relatorio_conferido.md` | `530d98c133e8f54c14621626086848d9c0d7dbcc8b9780551c9440ac3d11eca1` |
| `conferencia_1/relatorio_alcance_conferido.md` | `a5e6e5a1800115c264bddc0d58af943ca86cca242d7af64deeb9ab1fbfb86a60` |
| `adendo/busca/pin_revisao.json` | `c9db52e8a70b07e6e61c5398d4940cc80588b8b1540513e0d911c355300006db` |
| `adendo/busca/conferencia_revisao.json` | `bd946cad6cf5b56dc26917a620b9617aa42e635af04fde191f55341fa037933f` |
| `adendo/reconferencia.json` | `77a11687ecc3950ec7e8ae1e2bf43d18b39d0fb00563e42c515b4adb2349eb1f` |
| `adendo/nao_reproducao.json` | `09dac40adfa5a0859639790ef69ccd5279103108c3126e8e877afb196c695b1a` |
| `adendo/autoverificacao_primeira_execucao.json` | `9a5919ea9ed125dd1db4e9f573c84e2734fdd30d9b69b3e937d659f98383ce0a` |
| `adendo/comparacao_com_24_09.json` | `a998e2249a38149e4a4f95cfcf41fe54b3e0d7b21e0dd9e08cc32a5d631297b8` |
| `adendo/comparacao_com_primeira_execucao.json` | `286b38d644898402d8621428434b16e4ebebcca6b9181206dc08e4de6f1431b3` |
| `adendo/perfil_de_tokens.json` | `821fab38dbae6b6b6b2e79787bd358230f6acd8948716a4ee53077c0946f9c69` |
| `adendo/mutacoes.json` | `7ee968a34c7bd5d6265ce6d8ac705ca1e96f0ffb53cb0c42a70daaa4f75940ee` |
| `adendo/mutacoes_rodada_1.json` | `0b0a9f5aa9714b61385d57419bba384fec9888d51c4a443b3ac57738c6282ee8` |
| `adendo/verificar_mutacoes.py` | `fd2831ee4f754cc5b38ef63e12ea8d79be37d6e3cf1bca80b87d94c7594a628b` |
| `adendo/mutacao_plugin.py` | `d34673937925b56674b75db86044c506ebac57f601c47748c4c856ac6b617898` |
| `adendo/comparar_execucoes.py` | `62edb2b6f7a70eb6eba60da686bb8d901ede4a75ad425d9b5b43e7e12abc6acc` |
| `adendo/perfil_de_tokens.py` | `7c9634fe605c6d55d68b27bb8f9878f2cdd40185af53ef57e3120f5e872f56f4` |
| `adendo/autoverificar_primeira_execucao.py` | `8ce95d67cad746c7a970864c1ff8618f33c68396bb1b3ffa312cba3d18ef6e8a` |
| `adendo/pytest_suite.xml` | `9a652c140e24728c5027415eb212cd0494c235a381255b7d185c734e3bea9788` |
