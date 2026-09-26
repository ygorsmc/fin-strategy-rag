# Correção RAG-01 a RAG-04 do instrumento de alcance GEOM-1 — contrato

Data: 2026-09-25. Pedido do responsável: onda completa de correção dos achados
da [conferência independente de 25/09](conferencia_revisao_alcance_geom1_rank03b_2026-09-25.md),
mais os dois pontos que a conferência daquela conferência acrescentou (C1,
entradas não vinculadas além do `pin.json`; C4, forma ÷1.000). Escrito antes
de editar código ou documentos.

Escopo: `scripts/conferir_alcance_geom1_rank03b.py`, seus testes, uma frase do
MEMORY.md, ressalva datada no [relatório de alcance](alcance_geom1_rank03b_2026-09-24.md)
e o relatório desta onda. **Fora do escopo e proibido:** consumidor,
construtor, CSV de correções, painéis, gates, regra e código GEOM-1
(`reconhecer_geometria`, `piloto_geometria`, `fonte_rad_cvm`), o inventário
(`inventariar_alcance`), os sete arquivos protegidos, `artefatos/cvm.duckdb`,
`artefatos/cvm_treino.duckdb`, holdout, fonte nova, download, API paga, alvo,
T1/T2, baseline e treino. Nenhum ponto do pré-registro é decidido. Artefatos de
24/09 e da conferência de 25/09 não são regravados; o contrato de 24/09 e o
adendo de 25/09 não são alterados. **O1 continua valendo:** o FCO (6.01) só é
lido em memória para igualdade com o PDF; montante e sinal nunca são impressos
nem gravados.

## C1 — toda entrada vinculada antes do uso (RAG-01 e acréscimo)

Achado: a reconferência conferia três arquivos e tirava o universo de
documentos de um quarto, `pin.json`, sem conferi-lo; com `fontes: []`
aprovava sem examinar nada. O mesmo vale para `executar()`, e para mais duas
referências lidas sem conferência nas duas entradas: `pin_execucao.json`, de
onde saem os hashes do código congelado, e `selecao.json`, de onde saem os
hashes dos sete protegidos.

Correção, nas duas entradas (`executar` e `reconferir_publicados`):

- Cada entrada é lida uma vez; o SHA-256 é calculado sobre os mesmos bytes que
  serão interpretados e comparado com a referência fixada no código **antes**
  de qualquer uso: `pin.json` (`0dd42e2f…`, o mesmo registrado em
  `pin_execucao.json` e em `revisao/pin_revisao.json`), `pin_execucao.json`
  (`bb2059f3…`), `selecao.json` (`b3e85417…`), o inventário e as duas saídas
  de 24/09 (já fixados pelo N1), e os contratos que governam a execução.
- Estrutura do pin: `fontes` é lista não vazia; cada fonte tem `id_doc`
  (dígitos) e `sha256` (64 hexadecimais); nenhum `id_doc` ou `sha256` repetido.
- Mesmo universo, na mesma ordem e sem repetição: fontes do pin = fontes do
  `pin_revisao.json` = documentos da `conferencia_revisao.json` = registros do
  inventário. `pin_execucao.pin_sha256` e `pin_revisao.pin_alcance_sha256`
  têm de ser o hash do pin.
- Recusa ausência, retirada, acréscimo, duplicação e substituição, sempre
  antes de gravar qualquer saída.
- **Autoverificação nunca vazia:** gravar exige ao menos um valor comparado
  com módulo ≥ 1.000. Sem isso a execução falha, não aprova (§4.4, regra 4).
- A identidade da execução registra a data real da execução — não a data fixa
  de 24/09, que o replay da conferência herdou — e os contratos com hash.

Contraprovas, pelo caminho inteiro das duas funções: o cenário exato da
conferência (pin com `fontes: []`, demais entradas íntegras) é recusado sem
gravar; com as referências trocadas pelos hashes de arquivos sintéticos, para
exercitar a decisão e não só o hash, cada recusa estrutural e de universo
falha antes de gravar; pin de execução e seleção alterados falham; **controle
positivo** com duas fontes sintéticas examina exatamente os dois documentos, na
ordem do pin, nas duas funções.

Falsificação: alguma entrada lida antes de conferida; saída gravada com
universo diferente do pin; autoverificação aprovada sem valor verificável.

## C2 — token inteiro e sinal explícito (RAG-02)

Achado: o analisador não delimitava o token (`1.234.5678` casava `1234567`),
aceitava no máximo um espaço entre sinal e número (`-  1.234` virava
positivo) e não admitia moeda entre parêntese e número (`(R$ 1.234)` virava
positivo).

Correção:

- **Token** é a sequência máxima de dígitos separados por um único `.` ou `,`
  entre dígitos. Só entra na comparação se o token **inteiro** estiver na
  gramática pt-BR (milhar com ponto em grupos de três, ou sem separador;
  decimal com vírgula) e não vier colado a `.` ou `,` à esquerda. Fora disso
  é **recusado explicitamente**: nunca comparado, nem por prefixo, e contado.
- **Sinal**, lido do contexto (à esquerda: espaços, marcador de moeda —
  símbolo `Sc` com até três maiúsculas de prefixo, ou código ISO 4217 —,
  sinais e parêntese de abertura; à direita: espaços e parêntese de
  fechamento, ou sinal colado ao token):
  - positivo: nenhum sinal ou parêntese no contexto; ou `+` colado;
  - negativo: parênteses equilibrados em volta do token, com qualquer
    espaçamento e moeda dentro; ou traço/menos (categoria `Pd` ou nome
    `MINUS`) colado ao token ou a uma moeda colada a ele;
  - **ambíguo** — recusa explícita: sinal separado do número por espaço,
    parêntese com sinal, parêntese sem par, sinal colado a palavra ou número
    anterior (`2024-2025`), sinal depois do token, outros sinais (`±`, hífen
    invisível) e qualquer outra combinação.
- Ativo (comparação com sinal): só token positivo ou negativo casa. Token de
  mesmo módulo com sinal ambíguo é publicado **à parte**, com os mesmos campos
  (página, linha, coluna, tokens, trecho pela política do inventário), nunca
  como correspondência.
- FCO (comparação por módulo): qualquer token aceito, com o sinal que tiver;
  publica só páginas, como antes.
- Coluna passa a ser a ordem do token entre **todos** os tokens da linha,
  aceitos ou recusados. Em 24/09 era a ordem entre os casamentos da expressão
  antiga — mudança de sentido declarada na comparação.
- Por documento e modo, publicado e independente do alvo: quantos tokens
  foram recusados, em que páginas, e quantos têm sinal ambíguo.

**Substituição declarada:**
`test_numeros_da_linha_com_sinal_por_parenteses_e_por_traco_unicode` fixava
`− 1.000` → −1.000 e `‐ 5` → −5, sinal separado do número por um espaço. No
`-raw`, o traço de "sem valor" de uma coluna seguido do valor da coluna
seguinte aparece exatamente assim; ler como negativo apagaria um ativo
positivo sem sinal nenhum. Passa a ambíguo. Sinal colado segue negativo,
verificado no teste substituto com a mesma linha e as variantes coladas.

Contraprovas: os três casos da conferência (sem correspondência indevida);
ausência falsa — traço de pontuação ou de coluna vazia antes de ativo positivo
aparece como ambíguo, não some; cada forma aceita de positivo e de negativo
(parênteses com espaço e moeda; sinal antes e depois da moeda; parênteses de
largura cheia e pequenos; **todos** os caracteres `Pd` e `MINUS`, colados e
separados); formas ambíguas; FCO por módulo; números em colunas vizinhas (o
sinal de uma não contamina a outra); formas recusadas (prefixo, data,
milhar com vírgula, separador à esquerda); ordem de coluna; contagens.

Falsificação: token malformado casando por prefixo; sinal ambíguo contado
como correspondência; token recusado sem contagem publicada.

## C3 — autoverificação por equivalência numérica (RAG-03)

Achado: a lista finita de grafias deixava passar `1.234.567,00`,
`1234567.00`, `1 234 567,00` e `1.234.567,50`, em texto e em chave; e a
mensagem de erro repetia o nome do campo.

Correção:

- Toda representação numérica em texto ou chave publicados é lida como número
  de dois jeitos — todo `.`/`,` como milhar; ou o último como decimal e os
  outros como milhar —, com milhar também por espaço, espaço inseparável,
  espaço estreito e espaço fino (grupos de três), e expoente opcional. Recusa
  se alguma leitura for igual ao módulo de um valor comparado ≥ 1.000, ou ao
  seu piso ou teto quando o valor não é inteiro (cobre zeros decimais,
  `1234567.0` e arredondamento; o piso já era barrado antes).
- Número publicado com módulo ≥ 1.000 fora das isenções: recusado, como antes.
- **Isenção pela forma, não pelo nome:** sob chave terminada em `sha256`, só
  texto de 64 hexadecimais é isento (dicionário ou lista sob essa chave: as
  chaves continuam varridas e só as folhas hexadecimais são isentas); sob
  `data` ou `dt_refer`, só data `AAAA-MM-DD`. É a leitura estrita do R3
  ("campos de hash e data": campo que traz hash ou data).
- Tipo não previsto na saída derruba a verificação.
- Mensagem de erro nunca repete chave nem valor: dígitos mascarados.
- Números abaixo de 1.000 seguem fora da verificação, como o R3 prevê.

**Substituição declarada:** `test_autoverificacao_isenta_so_hash_e_data`
usava hashes falsos (`"1234567"` como hash) e `"1234567"` em `dt_refer`, que a
isenção pela forma deixa de aceitar. Passa a usar hashes de 64 hexadecimais que
contêm o valor (isentos), e os falsos viram contraprova (recusados).

Contraprovas: os oito casos da conferência; `1234567.0`, `1.234.567,000`,
expoente, piso e teto, sinal e parênteses; chaves; mensagem sem dígitos;
isenção pela forma e o que ela deixa de isentar; tipo não previsto. Controles:
números pequenos, hash, data, trecho mascarado e valor dentro de uma sequência
de dígitos mais longa, que não é representação dele.

Falsificação: alguma representação equivalente de valor comparado passando;
mensagem com dígito de chave ou valor.

## C4 — limite da forma ÷1.000 (acréscimo)

Achado: a forma ÷1.000 compara exatamente, e só casaria se as notas
imprimissem as casas decimais do milhar. Notas em milhares imprimem inteiros
arredondados: para valor que não é múltiplo de 1.000, a forma exata não tem
como achar nada. No ativo dos dois documentos o quociente não é inteiro. A
tabela do relatório de 24/09 lista "÷1.000 sem correspondência" como se a
hipótese "XML em reais, notas em milhares" tivesse sido testada.

Correção: ressalva datada no relatório; campo `limite` da saída declara o
alcance da forma; para o ativo, que não está sob o O1, a saída lista as formas
que só casariam com casas decimais. Para o FCO nada é calculado sobre
divisibilidade (O1).

Fora desta onda: comparação arredondada. No ativo é medição nova e exige
contrato próprio; no FCO não é igualdade, e o O1 só autoriza igualdade —
decisão do responsável.

## C5 — RAG-04

Uma frase no MEMORY.md, no bloco CRF de 18/09: as cinco decisões eram as de
18/09; desde 24/09 são seis (§12-bis). Registros inequivocamente históricos
ficam como estão.

## C6 — execução e preservação

1. Antes de editar: código e testes conferidos preservados em
   `artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/codigo_sob_conferencia/`
   (código `b0272037…`, testes `8f0a339e…`).
2. As contraprovas da conferência (`reproduzir_achados.py`, sem alteração)
   rodam contra o código novo, função a função e caso a caso. Esperado:
   nenhuma reproduz.
3. **Nova execução da busca**, com o código corrigido, nas mesmas fontes
   fixadas, em pasta nova desta onda — nunca em `revisao/`. **Exposição:** os
   resultados de 24/09 e a medição em memória de 25/09 (as oito ocorrências do
   ativo de 140867 são tokens inteiros, sem sinal no contexto ampliado; o
   ativo de 142900 não casa nem por módulo) são conhecidos. Não é teste cego.
   **Esperado, fixado antes de rodar:** o ativo de 140867 nas mesmas páginas e
   linhas de 24/09, nos dois modos; nenhuma ocorrência ambígua do ativo; FCO
   dos dois documentos e ativo de 142900 sem correspondência; a coluna só
   muda pelo novo sentido. Qualquer outra diferença é relatada, não ajustada.
4. Nova reconferência dos artefatos publicados de 24/09 sob C1 e C3, na mesma
   pasta.
5. Comparação da nova execução com a de 24/09, publicando só booleanos e
   contagens.
6. Suíte completa; `auditor-conformidade` como nova conferência independente,
   antes de concluir; relatório da onda; MEMORY.md.

## Falsificação da onda

- Saída com montante ou sinal de FCO, ou FCO lido para outra coisa que não
  igualdade.
- Artefato de 24/09 ou da conferência de 25/09 alterado.
- Asserção enfraquecida ou teste trocado sem declaração.
- Alguma contraprova da conferência ainda reproduzindo.
- Nova execução divergindo do esperado sem declaração.
- Consumidor, construtor, CSV, painéis, gates, código GEOM-1, inventário ou
  protegidos alterados.
