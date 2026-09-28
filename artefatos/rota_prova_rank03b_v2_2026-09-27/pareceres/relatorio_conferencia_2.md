Não achei nada que justifique recusa na conferência da ROTA-2: aprovei as 42 correções e as 10 confirmações. O JSON está gravado em `/tmp/claude-1000/-home-ygor-Antigravity-Projects-fin-strategy-rag/b3cd8830-7fb5-446d-ae1b-5242b33bd763/scratchpad/final_rota2_cadeia.json` (SHA-256 `498e083b31a08774ff986dcb63d50114e44240abe512b8a8f0eaec18cefa762f`).

## 1. Método

**Integridade**
- O arquivo de evidências confere com `e2001e06…4c24` antes e depois do trabalho. São 900 `id_prova`, todos únicos.
- A lista da Tarefa A coincide exatamente com as 42 correções de elo e cadeia do arquivo. A `98282-6.01` saiu porque o caixa dela perdeu a prova (`sem_unidade_de_milhares`), o que é coerente com uma regra que só estreita.
- Os 49 pacotes batem com `sha256_pacote` e com o manifesto de aquisição. Os ZIPs da CVM batem com `manifesto_cvm.csv`.

**Leitor próprio**
- O scratchpad foi limpo entre as rodadas, então reescrevi os módulos com a mesma lógica da ROTA-1, sem usar o script do produtor.
- O formulário é lido com ElementTree. A coluna corrente sai das datas dos períodos e da presença de dado, e foi única em todos os documentos.
- O CSV é lido em memória: `DFC_MI/MD_con` e `BPA_con`, linha `ÚLTIMO`, período corrente.

**Identidades**
- Ficam em funções puras. Antes de tocar o dado real, passaram 17 contraprovas sintéticas: identidade aberta, 6.01 e caixa ×1000, conta ausente, CSV divergente ou com duas versões, tolerância de 1 e de 2.
- No dado real, o script imprimiu por id só b1/b2 ou d1–d3/`igual_ao_csv`, a âncora e as escalas: CSV e envelope iguais à declarada, formulário da companhia, decidida.
- As pré-condições estruturais (período e bloco da DFC únicos, sem ambiguidade) entram dentro das próprias identidades.
- Os booleanos gravados nos 44 registros de elo e cadeia coincidem com os meus.

**Células da Tarefa B**
- A linha é localizada pelo `pdftotext -layout`, com anexo em base 0 entre os PDFs não vazios.
- Conferi:
  - números e `posicoes`;
  - o trecho mascarado, comparado só dentro do script;
  - o rótulo;
  - o título do "Total" (o mais próximo acima, pulando dados e cabeçalhos);
  - a linha de unidade: confere com o trecho, é de milhares e não há declaração contrária entre ela e a linha de valor;
  - `v` igual ao CSV;
  - os códigos de escala do registro contra a minha leitura;
  - a ausência de linha `dividido` em todos os anexos.
- Os dígitos foram reconfirmados com `pdftotext -raw` e com os caracteres do pdfplumber.
- Não imprimi nenhuma linha de valor, nem mascarada. Saíram só booleanos, o texto antes do primeiro dígito e as declarações de unidade sem número.

Não rodei `pytest`, que escreveria no repositório. O `git status` só mostra o diretório novo do produtor.

## 2. Resultado

Estas são as notas por id, com as mesmas do arquivo gravado, nenhum número de conta:

- **5 elos (`102304`, `110005`, `19302`, `48495`, `155968`):**
  - B1 e B2 fecham.
  - Caixa e ativo do formulário são iguais ao CSV.
  - CSV e envelope declaram UNIDADE, o formulário da companhia também, e a decisão é MIL.
  - A âncora `ROTA-2-<doc>-1` é célula própria corrigida, com a mesma escala.
  - Não há linha `dividido` do caixa nos anexos.
- **Os outros 2 elos (`137390`, `143037`):** idem.
- **35 cadeias:**
  - D1–D3 e `igual_ao_csv` fecham, com uma linha `ÚLTIMO` da mesma versão.
  - Escalas UNIDADE no CSV, no envelope e no formulário da companhia, e decisão MIL.
  - A âncora `…-1.01.01` foi corrigida para MIL por célula própria. Em `137390`, `143037` e `155968` a âncora é o elo aprovado neste lote.
  - Particularidades:
    - `131612` usa DFC método direto;
    - `19708` tem exercício de abril a março;
    - `108371` e `131612` têm `CodigoCvm` provisório no formulário interno, e a identidade se confirma pelo envelope e pelo CSV;
    - `145753` é documento de desenho;
    - `142900` e `35423` são GEOM-1.
- **`80868-6.01`:** a cadeia fecha. CSV e envelope declaram UNIDADE. O formulário da companhia declara MIL, o que vai só na nota, como manda o item 4 reescrito. O registro `ROTA-2-80868-1` guarda envelope 1 e formulário 2, igual à minha leitura.
- **Confirmações:** as 10 foram aprovadas.
  - `114850`: ficou só com as 2 linhas de milhares local, porque as 3 que dependiam de "apresentação" saíram, como previsto.
  - `155283`: é um release (grupo 1653), com unidade só por cabeçalho local.
  - `158838`: o "Total" da pág. 67 tem como título mais próximo "Caixa e equivalentes de caixa".
  - `54694`: é um elo, e as linhas do caixa falham no rótulo, então o elo era a via correta.
  - `67787` pág. 19: ativo e passivo estão lado a lado; o `-raw` separa as colunas, mas confirma os dois números na página.

## 3. Casos limítrofes

- **Códigos de escala só no registro do ativo.** O `codigos_de_escala` é gravado uma vez por documento, no registro da conta `1`, e vem nulo nos registros de caixa, elo e cadeia. Isso atende à letra do item 3, mas quem ler só o registro da `6.01` do 80868 não vê a divergência.
- **Defeito do meu verificador, corrigido.** Na primeira passada, o meu localizador de título pulou "7. Caixa e equivalentes de caixa" por causa do dígito da numeração e subiu até a prosa. Corrigi e o caso passou; não era defeito do produtor.
- **Nenhuma confirmação depende de "apresentação" na ROTA-2.** Todas as linhas aceitas são de cabeçalho local.

## 4. Exposição ao O1 nesta rodada

Não imprimi linha de DFC, nem mascarada. Não gravei cache com valor. Não imprimi valor, resíduo, sinal ou nulidade de conta 6.x.

Declaro dois pontos na fronteira:
- **`v_valido` na Tarefa B.** Nas 4 confirmações de caixa, imprimi o booleano da pré-condição B3.1 (módulo ≥ 1.000). A informação já decorre do registro publicado como confirmada, mas formalmente é um booleano de magnitude do caixa, fora do conjunto que você autorizou.
- **`sem_linha_dividido_do_caixa`.** É um booleano de conflito de escala, verdadeiro para qualquer magnitude. Não vejo informação nele, mas deixo registrado.

Os scripts estão em `scratchpad/b8b/`; os principais são `tarefa_a.py`, `tarefa_b.py`, `identidades.py` e `sintetico.py`.