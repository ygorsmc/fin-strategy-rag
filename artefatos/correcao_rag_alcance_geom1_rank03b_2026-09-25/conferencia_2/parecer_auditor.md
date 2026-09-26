<!--
Parecer do auditor-conformidade (subagente somente leitura, mesmo contexto da
primeira conferência), devolvido na virada de 25 para 26/09 sobre o adendo da
correção RAG. Transcrito na íntegra. É saída de modelo, não gold humano. [A], [T],
[K2], [R] e [AD] apontam para as versões preservadas em `../codigo_adendo/`, para
`relatorio_conferido.md`, para o adendo ao contrato e para `../adendo/`. As sondas
em [S] ficaram no scratchpad da sessão, fora do repositório. A primeira tentativa
desta reconferência foi interrompida por limite de sessão da API e retomada às 23:50.
-->

# Parecer: reconferência, somente leitura, do adendo à correção RAG (25/09)

## Veredito: FECHADO COM RESSALVAS

Os sete achados do meu parecer anterior e a observação sobre recusas depois de gravar estão fechados pelos critérios que eu mesmo dei. Em cada caso, reproduzi a correção e a contraprova que exercita a decisão.

Ficam cinco achados BAIXA, todos confirmados por execução. Nenhum muda resultado publicado, e os resíduos de parser não ocorrem nos dois documentos reais (medi por contagem).

Uma ressalva de coerência. Pelo critério mais estrito da conferência de 25/09 (reprodução sintética, sem ocorrência real, impede fechar), a classe do RAG-02 ainda se reproduz com caracteres fora da classe que o adendo fixou (achado 2). Não reabro por três motivos:
- o achado que apontei (Cf) está fechado, com a classe definida no contrato e testada caractere a caractere;
- o resíduo está fora dessa classe;
- ele não aparece no dado real.

Mesmo assim, esse resíduo deve ser declarado como limite, ou corrigido, antes de usar o instrumento em documentos de outros emissores. Nada aqui autoriza correção de escala, gate ou treino.

Caminhos:
- [A] = scripts/conferir_alcance_geom1_rank03b.py (ebe90e3e…)
- [T] = tests/test_conferir_alcance_geom1_rank03b.py (f74d5745…)
- [K2] = resultados/adendo_correcao_rag_alcance_geom1_rank03b_2026-09-25.md (af03e314…)
- [R] = resultados/correcao_rag_alcance_geom1_rank03b_2026-09-25.md
- [AD] = artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/adendo/
- [S] = scratchpad da sessão (sondas, fora do repositório)

## Achados (todos BAIXA, confirmados)

### 1. A3: a regra "parêntese pela NFKC" não tem contraprova que a discrimine

**Evidência.** Rodei [S]/mut/rodar.py, que usa o `mutacao_plugin.py` da própria onda. Troquei `"abre"` e `"fecha"` em [A]:260-261 pela definição por nome (a da primeira execução): **927 passed** nos dois casos.

O comportamento atual é o seguro, mas nenhum teste o fixa. Estes casos saem ambíguos hoje e sairiam −1 pela definição por nome:
- `"Total ❨1.234❩"`
- `"Total (1.234❩"`
- `"Total ﴾1.234﴿"`

Os testes em [T]:431-466 nunca combinam um parêntese ornamental com o parêntese normal.

**Por que importa.** É regra 7: a decisão não é exercitada. [R]:191-193 afirma que as 45 mutações cobrem "cada regra de A2 a A7", e esta regra não está entre elas e sobrevive.

**Critério de fechamento.**
- Casos que misturem os dois tipos de parêntese, esperando ambíguo.
- Essa mutação incluída no harness.
- Frase de [R] corrigida.

### 2. A2: o sinal ainda some, e o número casa positivo, com caracteres fora de Cf/Cc

É a classe do RAG-02, em resíduo mais estreito.

**Evidência** ([S]/a2a3_casos.py). Todos estes casam +1234 e não entram na lista de ambíguos:
- `"Total −͏1.234"` (U+034F, combining grapheme joiner, categoria Mn);
- `"Total (͏1.234͏)"`;
- seletores de variação `-️1.234` e `(︀1.234︀)`;
- U+E0100;
- preenchedores Hangul U+3164 e U+FFA0 (categoria Lo);
- U+17B4 e U+180B;
- moeda com espaço interno: `"Total -R $ 1.234"` e `"−US $ 1.234"` → +1 "limpo".

O próprio shape original do RAG-02 volta: `"Total 1.234.͏567"` casa o prefixo 1.234.

**Causa.**
- Caractere fora de toda classe encerra o contexto ([A]:315-316), e contexto vazio vale +1 ([A]:363-364).
- A classe de invisíveis é só Cf/Cc ([A]:268-269, [K2]:32-33).
- A moeda só reconhece maiúsculas coladas ao símbolo ([A]:306-310).

**Dado real.** Zero ignoráveis fora de Cf/Cc, zero caracteres Mn e zero ocorrências de "R $", nos dois documentos e nos dois modos ([S]/pdf_residuos.py, só contagens, sem ler XML).

**Critério de fechamento.** Tratar Default_Ignorable_Code_Point (Mn e Lo incluídos) como invisível, e reconhecer "R $" ou torná-lo ambíguo, com contraprova. Alternativa: declarar o limite no contrato e no relatório.

### 3. A5: quebra de linha entre grupos de dígitos derruba a autoverificação com `TypeError`

**Evidência.**
- `verificar_sem_valores({"nota": "1\n234\n567"}, [D(1234567)])` → `TypeError: 'NoneType' object is not subscriptable`.
- O mesmo acontece com `"9\n999"`, que não tem valor protegido nenhum.
- Causa: o separador `[^\w.,]` ([A]:480-481) admite `\n`, mas `_leituras` usa `.+?` sem DOTALL ([A]:493), e o `fullmatch` devolve `None`.
- Em `reconferir_publicados`, um publicado com esse texto aborta a execução em vez de registrar `false`. Sonda em [S]/sonda/test_sonda_a7.py: `TypeError`, nada gravado.

**Por que é BAIXA.** Falha fechada, e hoje nenhuma saída tem quebra de linha.

**Critério de fechamento.** DOTALL, ou separador sem `\n`, com teste.

### 4. A7: a serialização do resultado acontece depois de gravar o pin

**Evidência.** Em [A]:796-800, o `json.dumps(resultado)` roda dentro do segundo `write_text`, depois de `pin_revisao.json` gravado.

Um valor que passa na autoverificação e não é JSON (um `Decimal` menor que 1.000) deixa o pin sem resultado. Sonda (monkeypatch em `formas_que_so_casam_com_decimais`): `TypeError`, pin gravado `True`, resultado gravado `False`.

**Por que é BAIXA.** Com os campos atuais, todos nativos de JSON, isso é inalcançável.

**Critério de fechamento.** Serializar identidade e resultado antes da primeira escrita, com contraprova.

### 5. Documentação

- **(a)** [R]:184 diz "os outros 108 sinais da classe são 'outro sinal'". A classe tem 170 = 29 + 6 + 6 + 6 + 108 + **15**. Os 15 parênteses de fechamento ornamentais encerram o contexto à esquerda e são "sinal depois" à direita; não são "outro sinal".
- **(b)** A frase "cada regra de A2 a A7" ([R]:191-193) é contradita pelo achado 1.

**Critério de fechamento.** Corrigir as duas frases.

## Observações (não são achados)

- **Resíduos de A5 que passam sem ser barrados:** dois espaços entre grupos; `1 .234 .567`; combinante dentro de um grupo; preenchedor Lo como separador; expoente com 4 dígitos (`1234567000e-0003`). Hoje nenhum canal leva texto assim à saída.
- **Sósias de menos fora da classe** (U+2500, U+23AF, U+223C) dão +1 por desenho do contrato.
- **Totais ≥ 1.000 no perfil.** `[AD]perfil_de_tokens.json` publica totais de tokens ≥ 1.000 (3.158, 2.320…). São contagens independentes do XML, então não é questão de O1. Mas o instrumento evita esses números nas próprias saídas.
- **Cópia do pacote em disco.** O pacote inteiro é copiado para um diretório temporário do sistema durante a execução, e apagado no fim. Na minha leitura não fere o O1, porque nenhum valor é extraído. Se o responsável ler "gravar" de forma estrita, convém declarar.

## O que foi confirmado

**Achado 1 (MÉDIA) — fechado.**
- Minha mutação original (`validar_fontes` sem estrutura) agora derruba 27 testes: `test_pin_malformado_e_recusado_pela_estrutura` e `test_validar_fontes_recusa_cada_regra`.
- As cinco checagens internas morrem no harness.
- `_espelhar_pin` refixa o pin de execução, o inventário, o pin da revisão e a conferência.
- Cada caso casa a sua mensagem específica, e existe um teste de controle do espelhamento.

**Achado 2 (MÉDIA) — fechado para Cf/Cc.**
- 220 invisíveis tirados da tabela, com teste por caractere.
- Meus casos de ZWSP agora saem `invisivel_no_contexto`.
- Minhas mutações sobre o invisível antes do parêntese de fechamento, antes do sinal seguinte e à esquerda: cada uma derruba 220 testes.

**Achado 3 — fechado.**
- Nega = Pd ∪ NFKC em U+2212 (29 caracteres). ➖, ˗, ❖, ∖ e os demais passam a ambíguos, testados nos 108.
- As mutações por nome morrem.

**Achado 4 — fechado.**
- `1.234.567-8` e `2024-2025` saem ambíguos dos dois lados.
- A leitura A4b está declarada em [K2]:77-83, em [R]:185 e 251, e em teste.

**Achado 5 — fechado.** Meus 13 casos são todos barrados.

**Achado 6 — fechado.**
- A versão é conferida pelos quatro campos (`sha256`, `sha256_pdf`, `xml_sha256`, `pdf_sha256`), com testes.
- O pacote é lido uma vez e os leitores abrem uma cópia privada, com testes.
- Minhas mutações parciais (sem `sha256_pdf`, sem `pdf_sha256`) morrem.

**Achado 7 — fechado.**
- Marcas nas frases desmentidas, em [R]:27, 29, 35 e 110-112.
- `sentido_de_coluna` aparece na saída, e `mudanca_de_sentido` nas comparações.
- A frase do FCO foi corrigida: é a única mudança no relatório de alcance, comparado com `conferencia_1/relatorio_alcance_conferido.md`.
- O perfil publicado confere com a minha recontagem da rodada anterior (80/61, 171/54/46/19/1, mais 3 de "sinal depois"). Rodei de novo e saiu byte a byte igual.

**Observação A7 — fechada** para texto ilegível, paginação, anexo duplo e vazamento. Minhas mutações (ordem fina de gravação, anexo "primeiro" em vez de único, texto legível não exigido) morrem.

**Harness de mutação.** Rodei de novo e reproduziu exatamente:
- controle com 927 passed;
- 45 de 45 mortas, mesmas contagens, mesmos hashes (código `ebe90e3e`, testes `f74d5745`, plugin `d3467393`);
- a rodada 1 registra os testes da época (`eb94a1a5`);
- "morta" exige falha sem erro de execução, e nenhuma rodada teve erro;
- `main()` e o plugin exigem que cada trecho apareça exatamente uma vez.

**Testes.**
- Os 30 anteriores à onda estão como na primeira execução (AST).
- Os oito da primeira execução que mudaram não perderam asserção sem um substituto mais estrito, e estão declarados quando a expectativa mudou.
- 1.082 testes focados passam.
- Suíte do adendo: 3.976 = 927 + 155 + 2.894, zero falhas, erros ou skips, rodada às 20:58, depois da última edição.

**Hashes e integridade.**
- Os 24 hashes da tabela do adendo conferem.
- Artefatos de 24/09, da conferência de 25/09 e da primeira execução estão intactos.
- Nada fora do escopo mudou.
- Depois de 19:48 só mudaram os arquivos esperados.
- `nao_reproducao` e as duas comparações, rodadas de novo, saem idênticas.

**Saídas novas.** Sem montante nem sinal de FCO, sem dígito em trecho, sem número ≥ 1.000 (exceto as contagens do perfil) e sem quebra de linha. `fco_paginas` estão todas vazias.

## O que não foi verificado, e por quê

- **Suíte completa:** não rodei de novo; usei o XML e os 1.082 testes focados.
- **`autoverificar_primeira_execucao.py`:** não rodei, porque lê o FCO em memória. Usei os booleanos publicados e a varredura estrutural.
- **Precedência do adendo sobre a primeira edição de código:** o sistema de arquivos só mostra a última escrita (adendo 20:36:58, código 20:48:34); o código cita o hash do adendo.
- **Busca real:** não repeti. Nesta rodada, no dado real, fiz só contagens sobre o texto dos PDFs, via cópia com hash conferido; nenhum XML foi lido.
- **Holdout e `cvm*.duckdb`:** não tocados.
- **Repositório:** nada foi criado ou editado. O MEMORY.md é da onda (21:01:45, junto do relatório).
