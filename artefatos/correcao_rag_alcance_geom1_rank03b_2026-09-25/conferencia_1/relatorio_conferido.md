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

## O que mudou

| Achado | Correção | Contraprova |
|---|---|---|
| **RAG-01** — a reconferência tirava o universo de um `pin.json` não conferido; com `fontes: []`, aprovava sem examinar nada | **C1.** Nas duas entradas (`executar` e `reconferir_publicados`), toda entrada é lida uma vez e tem o hash dos mesmos bytes conferido antes de qualquer uso; o pin precisa ter fontes, sem repetição; pin, saídas publicadas e inventário precisam ter o mesmo universo, na mesma ordem | o cenário exato da conferência, nas duas entradas; sete pins malformados com o hash refixado, para que quem decida seja a estrutura; conferência, pin da revisão e inventário com outro universo; controle positivo com duas fontes sintéticas pelo caminho inteiro |
| Acréscimo da conferência da conferência: **`pin_execucao.json` e `selecao.json`**, as referências do código congelado e dos sete protegidos, também eram lidas sem conferência | **C1.** Fixadas por hash (`bb2059f3…`, `b3e85417…`), assim como os contratos que governam cada entrada | referência alterada e contrato diferente do fixado são recusados, sem gravar nada |
| **RAG-02** — `1.234.5678` casava `1234567`; `-  1.234` e `(R$ 1.234)` casavam positivo | **C2.** O token é a sequência máxima de dígitos, e só é comparado se estiver **inteiro** na gramática pt-BR; o resto é recusado e contado. O sinal só vale nas formas explícitas do contrato (parênteses equilibrados, com espaço e moeda; traço ou menos colado); todo o resto é **ambíguo**, uma recusa explícita. Ativo ambíguo sai numa lista à parte, nunca como correspondência | os três casos da conferência; ausência falsa; as 31 formas de traço e menos, coladas e separadas, montadas a partir da tabela Unicode e não da implementação; formas aceitas e ambíguas; colunas vizinhas; formas recusadas |
| **RAG-03** — `1.234.567,00`, `1234567.00`, `1 234 567,00` e `1.234.567,50` passavam pela autoverificação; a mensagem repetia a chave | **C3.** Equivalência numérica: cada número publicado é lido de dois jeitos e comparado com o módulo, o piso e o teto de cada valor comparado ≥ 1.000. A isenção vale pela forma: só hash de verdade e só data de verdade. Tipo não previsto derruba. Mensagem com dígitos mascarados | os oito casos, mais expoente, zeros, arredondamento, espaço fino, sinal e parênteses, em texto, chave e lista; isenção pela forma; tipo não previsto |
| Acréscimo: **forma ÷1.000 inerte** | **C4.** Limite declarado no campo `limite`, sem dígitos, e na [ressalva do relatório de alcance](alcance_geom1_rank03b_2026-09-24.md). Para o ativo, a saída lista as formas que só casariam se as notas imprimissem as casas decimais | alvo não inteiro listado; texto do limite sem dígito |
| **RAG-04** — "cinco decisões" no bloco CRF de 18/09 | **C5.** Uma frase no MEMORY.md: as cinco eram as de 18/09; desde 24/09 são seis | — |

Três guardas que o contrato não pedia, achadas durante a implementação e
cobertas por contraprova:

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

## Suíte

Suíte completa, com o `.env` local ativo e sem sobrescrever variável:
**3.297 passed, zero falhas/erros/skips**, 152,7 s
(`pytest_suite.xml`). São **+186 contraprovas da busca** sobre as 3.111 da
conferência, com as duas substituições e o ajuste de pré-condição declarados
acima. Arquivos focados: 248 da busca (eram 62) e 155 do inventário, sem
mudança.

## Conferência independente

PENDENTE_CONFERENCIA

## Hashes

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
