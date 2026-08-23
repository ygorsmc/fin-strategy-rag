# MEMORY.md

> Memória de trabalho entre sessões. Leia no início de toda tarefa; ao final,
> **sobrescreva** o que ficou desatualizado. Não é changelog — é handoff.
> Regras de uso em [AGENTS.md](AGENTS.md#10-memória-entre-sessões--memorymd).

## Estado atual

- **Marco:** o repositório foi realinhado à **revisão 3** da especificação
  (2026-08-10). O plano em `AGENTS.md` tem 18 etapas, RN01–RN12 e os gates
  G1/G2/G3/G4 — o plano antigo de 10 etapas não vale mais.
- **Suíte local: 1.474 casos passando, sem skips, sem falhas.** Verificado em
  2026-08-21 COM `requirements-guardrails.txt` instalado E os pesos do Prompt
  Guard 2 no cache local (1.349 em 19/08 → +16 de `tests/test_fatos.py` (E4)
  → +7 das guardas de coluna → +9 da métrica de exatidão comparativa → +36 de
  `tests/test_seguranca.py` → +22 da fiação dos guardrails → +17 de
  `tests/test_reconhecedor_presidio.py` → +12 de `tests/test_prompt_guard.py`).
  Sem os dois requirements opcionais, a contagem é 1.445 — `pytest` erraria a
  coleta desses dois arquivos, não silenciaria com skip.
- **ETAPA 14 (guardrails) — CONSTRUÍDA, MEDIDA e LIGADA em 2026-08-21, custo
  zero.** `src/seguranca.py`, `src/reconhecedores_br.py`,
  `conjunto_padrao/ataques.csv` (20 ataques), `scripts/medir_guardrails.py`,
  `responder_com_guardrails` em `src/agentes.py`, portão em
  `app_streamlit.py`, 58 testes. Evidência: `resultados/guardrails.json`.
  **TRÊS metas na mesma execução: 20/20 ataques bloqueados** (9 injeção,
  11 tópico, todos pelo scanner E subtipo corretos), **0/45 falso bloqueio de
  entrada** nas congeladas e **0/855 de saída** sobre os textos que o próprio
  sistema gerou nas 4 estratégias do congelado. Medir só a primeira premiaria
  um scanner que recusa tudo.
  - **Dígito verificador é o que faz funcionar.** CPF/CNPJ são validados pela
    aritmética, não pela forma: um release está cheio de números de onze
    dígitos (`1.296.511` de carteira, códigos de conta) e reconhecer pela
    forma seria fábrica de falso bloqueio. Há teste de regressão com número
    de 15 dígitos.
  - **PII NÃO bloqueia, anonimiza.** Um CPF na pergunta é dado a proteger, não
    ataque. Bloquear viraria proteção do usuário em recusa de atendimento.
  - **Cada subtipo de tópico declara a norma em CÓDIGO** (`ANCORA_LEGAL`):
    recomendação e preço-alvo → **Res. CVM 20/2021** (analista); consultoria
    pessoal → **Res. CVM 19/2021**. É o que permite a interface explicar a
    recusa citando a resolução, em vez de confiar isso ao prompt.
  - **O gatilho é o VERBO, não o assunto** — "qual foi o lucro" e "qual o
    preço-alvo" falam ambos de dinheiro e só o segundo é conduta regulada. É
    isso que segura o falso bloqueio em zero.
  - **Ordem importa:** consultoria é testada antes de recomendação, porque
    "onde devo investir" é aconselhamento pessoal (19/2021) antes de ser
    recomendação (20/2021), e a âncora legal muda com isso.
  - **PRESIDIO CONSTRUÍDO em 2026-08-21** (mesma sessão) —
    `src/reconhecedor_presidio.py`, `requirements-guardrails.txt` (isolado,
    reusa `requirements-lora.txt` para torch/transformers), config
    `presidio_habilitado` (padrão `False` — RNF12), 17 testes. Fundido em
    `src.seguranca.anonimizar` via `combinar_sem_sobreposicao` (extraído de
    `reconhecedores_br.encontrar_entidades` para ser reusável). Ligado em
    `app_streamlit.guardar_entrada`/`avaliar_saida` e em
    `agentes.responder_com_guardrails`, threadado de `Config`.
    - **Dois falsos positivos medidos e corrigidos ANTES de aceitar o
      resultado, não depois:** (1) "Santander" sozinho vira PERSON (score
      0,85 — o recognizer spaCy da Presidio dá score FIXO por tipo, não
      confiança gradiente) → filtrado contra `APELIDOS_BANCOS`; (2) "Ignore"
      e "Aja" no início da frase viram PERSON só por capitalização de início
      de sentença → filtrado por token único na posição 0. **O achado 2 é o
      mais sério dos dois:** sem o filtro, ATK012 e ATK015 deixavam de ser
      bloqueados, porque a anonimização roda ANTES da varredura de conduta e
      apagava o verbo que o scanner de injeção precisa ver. Remedido depois
      da correção: 20/20 ataques, 0/55 alteradas (dev+teste), 0/855 na saída.
    - **`PresidioIndisponivelError` captura `SystemExit`, não só
      `OSError`:** modelo spaCy ausente não levanta exceção comum — a CLI do
      spaCy tenta baixar e chama `sys.exit(1)` ao falhar. Sem capturar os
      dois, um erro de configuração comum derrubava o processo inteiro.
  - **LLAMA PROMPT GUARD 2 (86M) CONSTRUÍDO em 2026-08-21, mesma sessão** —
    `src/prompt_guard.py`, config `prompt_guard_habilitado` (padrão `False`),
    `guardrails_modelo_injecao_revision` agora pinado no SHA real
    (`a8ded8e...4a2fd27`) em vez de vazio, 12 testes. Ygor forneceu
    `HF_TOKEN` (conta `ygorsmc`) — token válido de imediato, mas os DOIS
    modelos (`86M` e `22M`) estavam com `gated: manual`: aprovação por
    revisão da Meta, não automática por aceitar licença. Ygor solicitou
    acesso na página do modelo e foi aprovado em minutos, dentro da mesma
    sessão.
    - **Achado central, medido ANTES de compor:** sozinho, o classificador
      **não cobre a família `topico_proibido`** (0/11) — ele foi treinado
      para *sobreposição de instrução*, não *pedido de conduta regulada*;
      são categorias diferentes, não é defeito. Da família `injecao`, pega
      5/9 sozinho (perde ATK014/015/016/018 — redefinição de papel e
      extração de prompt em frase curta de um turno, fora do caso de uso
      "documento de terceiro" para o qual foi treinado). **Os 9 já são
      cobertos pelo regex** — o valor de somar não é o placar nesta amostra
      fixa, é a paráfrase/ofuscação que nenhum padrão fixo cobre em tráfego
      real.
    - **Composição é OR, não substituição:** em `seguranca.avaliar_entrada`,
      só chama o classificador ML quando o regex NÃO achou nada (mesmo
      resultado final, sem pagar a inferência duas vezes). Com as duas
      camadas ML (Presidio + Prompt Guard 2) ligadas ao mesmo tempo: 20/20
      ataques, 0/45 falso bloqueio de entrada, 0/855 de saída — nenhuma
      interfere na outra.
    - **`local_files_only=True` confirmado sem HF_TOKEN em runtime:** testei
      explicitamente com a variável removida do ambiente — os pesos já
      cacheados carregam normalmente. Confirma a doutrina da RNF12: o token
      é segredo de BUILD (baixa uma vez), nunca de runtime.
    - **86M, não 22M:** o card do modelo diz que só o 86M usa base
      multilíngue treinada para injeção não-inglesa; o 22M é avaliado em
      múltiplos idiomas mas não necessariamente treinado com eles. Como o
      corpus e os ataques são em português, 86M foi a escolha, apesar do
      custo de latência 4x maior.
  - **Etapa 14 está COMPLETA** — nenhum item pendente. `PRESIDIO_HABILITADO`
    e `PROMPT_GUARD_HABILITADO` continuam `False` no `.env` (RNF12); ligar é
    decisão de deploy, não lacuna técnica.
  - **Fiação é COMPOSIÇÃO, não alteração dos braços (RNF11).**
    `responder_com_guardrails` embrulha `responder_braco_b`; os braços A/B
    continuam puros porque o experimento de 5.9.3 mede orquestração, e
    guardrail dentro deles faria a comparação A×B medir outra coisa. Há teste
    que lê o fonte dos braços e falha se `avaliar_entrada`/`avaliar_saida`
    aparecerem lá.
  - **Três garantias da fiação, travadas por teste:** (1) entrada bloqueada não
    constrói fábrica nenhuma — ataque não custa dinheiro nem cota de sessão;
    (2) o braço recebe o texto **anonimizado**, nunca o original; (3) bloquear
    a saída **não zera o `uso`** — a chamada foi paga, e esconder isso
    corromperia a contabilidade de orçamento.
  - **Falso bloqueio de saída foi medido ANTES de ligar**, não depois: 855
    textos reais do checkpoint congelado, zero bloqueios. Ligar uma guarda de
    saída sem essa contraprova seria apostar que ela não recusa resposta
    legítima.
- **E4 (`Estrategia.FATOS`) construído em 2026-08-20** — `src/fatos.py`,
  ligado em `src/recuperacao.py::_top_fatos`, no vocabulário de
  `ESTRATEGIA_PADRAO`, em `app_streamlit.ESTRATEGIAS_AVALIACAO` e na lista do
  `executar_pipeline.py`. **Consequência de contrato:** `src/avaliacao.py:1103`
  exige `set(estrategias) == set(Estrategia)` no congelado, então a rodada
  publicável passou de 180 para **225 chamadas**.
  - **Parser único, de propósito:** o laço que a guarda da RN02 usava para
    montar evidência virou `geracao.fatos_numericos_do_chunk()` e é o mesmo que
    a tabela usa. `tests/test_fatos.py::test_parser_e_o_mesmo_da_guarda_da_rn02`
    trava isso — um segundo interpretador proporia página que o grounding
    depois recusa.
  - **Não é persistido em disco, por decisão.** Construir sob demanda custa
    ~35 s e 36.621 fatos (só os que têm grupo métrico; os outros 127 mil não
    discriminam chunk nenhum). Um artefato derivado dos chunks criaria a classe
    de defeito "índice novo, fatos velhos" e exigiria guarda própria de
    consistência — construir sob demanda torna a incoerência impossível.
  - **Validado pelo caminho de produção** contra o índice real, custo zero:
    recall@5 por categoria E1/E2/E3/E4 = comparativa 10/10/10/**10**, factual
    13/12/12/**12**, total 23/22/22/**27**; valor exato no top-5 das factuais
    **E3=9/15 · E4=11/15**. Consulta leva 0,5 s para as 45.
- Etapas **3 (CVM → DuckDB)** e **5 (indexação em Chroma)**: **concluídas**.
- Etapa ativa (plano §7): **11 (camada de agentes)**. **Os três braços existem e
  rodaram** (2026-08-12): `src/cobertura.py`, `src/ferramentas.py`,
  `src/braco_determinista.py` (C), `src/agentes.py` (Investigador + Auditor com
  **CrewAI 0.193.2**, filtro de contexto por código) e `src/braco_agente.py`
  (arnês de A e B). Resultados em `artefatos/resultados_agentes/braco_{a,b,c}.json`.
  **Falta da etapa 11:** o caso (B) de acompanhamento de projeções (5.9.2, "construir
  depois"). **Falta da etapa 12:** o McNemar formal — a **injeção de falha
  (5.9.4) rodou** em 2026-08-12 (`src/injecao_falha.py`,
  `tests/test_injecao_falha.py`, `artefatos/resultados_agentes/injecao_falha.json`).
- **A e B estão agora sob o MESMO prompt (`a2` + gate de correção)** — a
  comparação pareada voltou a ser válida. Vigentes: `braco_a.json` (run
  `20260812T212837Z-5410ab16e7`) e `braco_b.json` (run
  `20260813T200629Z-a9cb37a310`, 2026-08-13, **já com o roteamento da
  desambiguação corrigido**). Preservados só para comparação, nunca como
  resultado corrente: `braco_{a,b}_prompt_a1.json` (prompt anterior) e
  `braco_b_prompt_a2_sem_fix_desambiguacao.json` (run
  `20260813T170119Z-da0a6fc4f2`, mesmo prompt, roteamento defeituoso).
  **`braco_c.json` foi REAPURADO em 2026-08-21** (run
  `20260821T173509Z-8dd07cd4c6`, custo zero, zero chamada de LLM) e o
  resultado é **idêntico ao anterior: 0 de 15 registros mudaram** em
  apuração, acerto, cobertura, comportamento, motivo, recusa ou resposta —
  só a latência variou. As correções de `src/cobertura.py` não tocaram
  nenhum veredito do braço C. A pendência era de procedência (run_id velho),
  não de conteúdo. **Débito fechado, e fechou como no-op.**
  Números vigentes: 15 perguntas, 5 apurados (2 acertos, 3 erros,
  taxa 0,400), **10 pendentes de dupla leitura humana** — o gabarito não
  conferido nunca vira acerto nem erro, por regra dura.
- **OCR completo (2026-08-11).** A passagem pela Batch API rodou: job
  `0eb6eab2`, 20/20 documentos, **2.790 páginas, zero erros, USD 5,58** (metade
  do síncrono). Cache versionado em `corpus/ocr/<hash-do-pdf>.json`, 23 MB.
  Validação: 2.790/2.790 páginas, nenhuma vazia, sentinela ok em 4 amostras.
  O desbloqueio foi ativar **Pay-As-You-Go** no console — crédito pré-pago é
  saldo, não permissão, e a Batch API recusava com HTTP 402 até então.
- **Rodada congelada VIGENTE: `20260823T131515Z-4ad67021f6`** (2026-08-23,
  225 chamadas, zero erro, **USD 0,2501**, `gemini-3.5-flash-lite`,
  fingerprint `5b9b142d`). É a primeira sobre o índice de **7.147 chunks**,
  com o chunking de tabela corrigido (ver bloco próprio abaixo).
  **Exatidão factual: E0 0,000 · E1 0,333 · E2 0,333 · E3 0,467 · E4 0,667.**
  **Exatidão comparativa: 0,000 em TODAS** — regressão contra os 0,100/0,200
  da rodada anterior.
  Recall@5: E1 0,920 · E2 0,800 · E3/E4 0,880. Recusa correta 1,000 em E1–E4.
  **O 0,667 do E4 é o maior número de exatidão factual do projeto e MESMO
  ASSIM não é vitória:** contra a rodada anterior o máximo é 4 discordâncias
  numa direção e 3 na outra, e o limiar pré-declarado é 6 (McNemar exato).
  Publicar como melhoria seria a leitura que o limiar existe para impedir.
- **DUAS RODADAS PAGAS FORAM GASTAS NUM CONSERTO QUE PIOROU ANTES DE
  MELHORAR** (2026-08-22/23, USD ~0,26 cada). Registrado porque a lição é o
  método, não o número. A auditoria manual rastreou o erro do TSTF006 (o
  modelo respondeu `12.144`, coluna 4T25, a uma pergunta de 1T26 cujo valor é
  `11.875`) até o **chunker** — não o modelo, não o OCR. A tabela estava
  íntegra; o chunk é que abria nas duas últimas linhas dela, órfãs do
  cabeçalho de período. **Duas causas:** (a) a cauda de sobreposição copiava
  os últimos tokens sem olhar o tipo de bloco; (b) a partição de tabela grande
  media a parte sem contar a legenda de unidade que ela mesma emite.
  **101 chunks** abriam com 3+ colunas de valor sem cabeçalho e **18 das 45**
  recebiam um no top-5.
  - **A 1ª correção foi cega e custou uma rodada.** Descartar tabela da cauda
    zerou os órfãos e derrubou a exatidão factual junto (E1 0,400→0,200,
    E2 0,467→0,267). Causa: a duplicação do overlap era **também** rede de
    segurança — em TSTF010 o valor `3.659` estava em 2 chunks do top-5 antes
    e em **nenhum** depois. Recall continuou `True` nos 6 casos que
    quebraram, o que prova que o problema não era recuperação de página.
  - **A 2ª correção recoloca o cabeçalho na cauda** em vez de descartar a
    tabela: os fragmentos passaram a carregar os tokens do cabeçalho de
    origem. Resultado: **0 órfãos**, valores de volta no top-5, e
    **TSTF006 passou a acertar em E3**.
  - **Lição de método:** `recall@5` é medido POR PÁGINA e foi sinal enganoso
    aqui — ele contava como acerto o chunk órfão, que não conseguia
    responder. Nas duas vezes em que recall e realidade discordaram nesta
    investigação, recall estava errado. Para julgar chunking, medir se o
    VALOR está no top-5, não se a página está.
- **CITAÇÃO É O GARGALO ATUAL, MEDIDO (2026-08-21).** Em **18** respostas
  publicadas a página aceita **estava no top-5** e o modelo citou **outra**:
  12 factuais e 6 comparativas. Exemplos conferidos na mão: TSTC006 citou a
  **pág. 2 do Santander (o índice do documento)** em vez da 11; TSTC005 citou
  a **pág. 38 do Itaú**, onde mora a coluna do semestre acumulado (22,8%), em
  vez da pág. 5 com o trimestre (23,3%). As guardas recusam **10 das 18**; as
  outras **8 continuam publicadas**.
  **Consequência interpretativa:** a exatidão comparativa baixa NÃO é a
  métrica nova sendo severa — é a guarda recusando corretamente uma citação
  que não sustenta o número. Recuperação não é mais o gargalo; escolha de
  página é.
  **Ressalva:** `locais_aceitos` lista uma página por documento. Parte das 18
  pode estar citando página alternativa legítima (a pág. 108 do BB é
  provavelmente a demonstração completa). Separar exige leitura humana — é o
  caso mais forte para enriquecer a coluna `locais_aceitos` do gabarito.
- **A REPLAY PREVÊ O AGREGADO, NÃO O ITEM — aprendido na marra em 2026-08-20.**
  O replay das correções sobre as respostas já pagas estimou E1 6/15, E2 6/15,
  E3 5/15, E4 8/15 (agregado 25/60). Medido de verdade: **3, 6, 7, 7 (agregado
  23/60)**. O agregado bateu quase na mosca; a alocação por estratégia embaralhou
  completamente — o E1 caiu 5→3 e o E3 subiu 4→7. Motivo: a temperatura 0 não
  torna a LLM determinística entre execuções, e o replay reusa as respostas
  antigas. **Usar replay para decidir SE vale rodar, nunca para publicar
  número por estratégia.**
- **O GARGALO MUDOU DE CAMADA — e as recusas foram APURADAS e CORRIGIDAS
  (2026-08-20, custo zero).** O E4 levou o valor exato ao top-5 em 11/15 contra
  9/15 do E3, e isso não virou exatidão porque o sistema recusava 9/15 das
  factuais, **5 delas com o valor exato já no trecho**. Rastreadas com
  `sys.settrace` sobre o checkpoint pago, as 5 caíam em **dois defeitos, nenhum
  deles de fundamento**:
  1. **Trimestre abreviado (TSTF004, TSTF007, TSTF010).**
     `extrair_trimestres_citados` só lia `2T2025`, não `2T25` — que é a grafia
     do próprio release. O não-lido virava suspeita: `_escopo_solicitado_esta_
     coberto` recusava **em bloco** toda resposta com período abreviado. A
     resposta estava certa em valor, página e trimestre; caiu por ortografia.
     **A guarda da RN02 já tinha recebido essa correção; faltou aqui** — a
     mesma falha, corrigida num lugar só.
     Corrigido em `PADRAO_TRIMESTRE`, que agora canoniza a forma curta na
     leitura, e a recusa em bloco saiu de `geracao.py`.
  2. **Marcador de citação entre parênteses (TSTF005, TSTF014).** O stripper
     tratava `[..., pág. 12]` mas não `(..., p. 12)` — e a marca curta `p.`
     não casava nem entre colchetes, porque o padrão exigia o "a" de "pág".
     A abreviação termina em ponto, o divisor de cláusulas corta ali, e sobrava
     `12).` como afirmação: a guarda tentava fundamentar **o número da página**
     como valor financeiro e derrubava a resposta inteira.
  **Efeito medido por replay sobre as 60 respostas já pagas, zero regressão:**
  E1 5→6 · E2 4→6 · E3 4→5 · **E4 5→8**; agregado **18/60 → 25/60**.
  Nenhuma célula piorou.
- **ATENÇÃO — a rodada congelada vigente ficou DESATUALIZADA em relação ao
  código.** Os números publicados (E4 0,333 etc.) são os da rodada; o replay
  acima é **estimativa**, não resultado publicável. Como o fingerprint hasheia
  `geracao.py` e `normalizacao.py`, o checkpoint já está invalidado — publicar
  exige **nova rodada de 225 chamadas** (~USD 0,23). Não rodada ainda.
- **DEFEITO DO TSTF006: CAUSA APURADA E CORRIGIDA (2026-08-20).** O sistema
  publicava **12.144** com gabarito **11.875**, reproduzindo idêntico nas duas
  rodadas. A causa não era alucinação: era **atribuição de coluna**, em dois
  defeitos distintos da tabela `Comparativo BRGAAP¹ e IFRS` (Itaú 1T2026,
  pág. 30), cuja linha é
  `| IFRS - ... controladores e não controladores | 220.017 | 11.875 | 12.144 | 10.707 |`
  sob as colunas `31/mar/26 | 1T26 | 4T25 | 1T25`:
  1. **Cabeçalho de duas linhas.** A linha de períodos vem ABAIXO do
     `| --- |`, e `_periodos_das_colunas` só lia a de cima (que traz
     `Patrimônio Líquido* | Resultado Líquido*`, sem período nenhum). Resultado:
     zero coluna identificada, guarda inerte, qualquer célula fundamentando
     qualquer trimestre. Corrigido por `_periodos_do_cabecalho_da_tabela`, que
     procura dos dois lados do separador e exige 2+ células com período para
     não confundir linha de dados com cabeçalho.
  2. **O chunk recuperado nem tinha cabeçalho.** O E2 recuperou o
     `itau_release_1T2026_0085`, que **começa no meio da tabela** — o cabeçalho
     ficou no `0084`. É o problema que a "Opção B" tentou resolver na ingestão
     e falhou três vezes. Resolvido pelo outro lado, na guarda: linha de tabela
     órfã (sem cabeçalho no próprio chunk) com **2+ células numéricas** não
     fundamenta afirmação de trimestre único. Célula única continua valendo —
     `| Lucro líquido | 11.508 |` não é ambíguo.
  **Alcance medido antes de implementar:** 63% dos chunks começam com tabela
  sem cabeçalho; as linhas órfãs multicoluna são 4.322, ou 10,7% de todas as
  linhas de tabela do corpus.
  **Efeito medido por replay sobre as 180 respostas da rodada vigente:
  exatamente DOIS vereditos mudam, e os dois eram respostas ERRADAS.**
  `TSTF006/semantica` (12.144 → recusa) e **`TSTC005/keyword`**, que publicava
  `22,8%` para o ROAE do Itaú no 2T2025 quando o gabarito é `23,3%` — 22,8% é a
  coluna do semestre acumulado `1S25`. Exatidão fica **idêntica** (23/60,
  E1 3 · E2 6 · E3 7 · E4 7): nenhum acerto foi perdido. Ganho puro de
  segurança.
- **BURACO NA AVALIAÇÃO, ACHADO DE RASPÃO E AINDA ABERTO: as 10 comparativas
  não têm métrica de acerto numérico.** `exatidao_numerica` roda só sobre as 15
  factuais. O `TSTC005` publicou um número errado e **nenhuma métrica registrou
  isso** — `recall_ok=True`, `recusa_correta=None`. Só apareceu porque eu fui
  conferir manualmente. Enquanto isso não for coberto, o número de exatidão
  publicado descreve um terço do conjunto congelado.
- **MÉTRICA DE EXATIDÃO PARA COMPARATIVAS: CONSTRUÍDA (2026-08-21), custo
  zero.** `avaliar_exatidao_comparativa` em `src/avaliacao.py`, nova coluna
  `exatidao_numerica_comparativa` em `MetricasEstrategia` (a antiga
  `exatidao_numerica` continua escopada às factuais — regra do projeto é
  acrescentar coluna, nunca linha). `VERSAO_AVALIACAO` "v5"→"v6": o
  checkpoint vigente fica invalidado, então **este número exige rodada nova
  para virar oficial** — e uma rodada completa são 225 chamadas, MAIS do que
  as 50 que restam hoje no 3.5. Não dá para oficializar nesta sessão.
  **Mecanismo:** para cada banco citado no gabarito, pega os valores
  percentuais na janela até a PRÓXIMA menção de banco (nunca além — é a
  mesma disciplina de escopo da RN09/G4, senão o valor do BTG validaria
  também uma afirmação sobre o Itaú); delta em p.p. cai fora por DIMENSÃO
  (`delta_percentual` ≠ `taxa_percentual`), não por posição, então não
  precisa de tratamento especial. 9 testes novos, incluindo o caso real do
  TSTC005 como regressão.
  **Replay contra o checkpoint pago (estimativa, não oficial):**
  factual keyword 3/15 · semantica 6/15 · hibrida 7/15 · fatos 7/15 (igual a
  antes — nada mudou na factual); **comparativa keyword 0/10 · semantica
  1/10 · hibrida 0/10 · fatos 2/10.**
  **ACHADO REAL, NÃO É BUG DA MÉTRICA: o modelo cita a página ERRADA dentro
  do próprio top-5 recuperado nas comparativas.** TSTC006/hibrida: recuperou
  Santander pgs 1–3 (índice), 3–3, **24–25** (onde o dado real provavelmente
  está) — e citou a **pág. 2** (o índice) para o valor de 17,5%. `recall_ok`
  dá `True` porque a página certa ESTÁ no top-5; a exatidão dá `False`
  porque a citação não aponta pra ela. É por isso que ninguém via esse
  defeito: a única métrica que existia (recall) não enxerga citação, só
  presença. É provavelmente o principal motivo da exatidão comparativa
  vir tão mais baixa que a factual, e é achado novo desta sessão — não
  investigado a fundo, fica para a próxima.
- **10 respostas publicam o valor CERTO e o grader reprova** na rodada vigente
  (TSTF002, TSTF006, TSTF009, TSTF010, TSTF012, em várias estratégias). É a exigência de repetir
  os qualificadores, já discutida em 19/08. O caminho correto continua sendo
  **coluna nova no gabarito** com as redações aceitas por pergunta — decisão do
  Ygor, não feita.
- **Histórico das rodadas no congelado** (mesmo conjunto de 45):
  `20260818T235938Z-5c0da1df7f` (v9) E1 0,200 · E2 0,133 · E3 0,200 → agregado 8;
  `20260819T200308Z-fe444d53d8` (v9) E1 0,133 · E2 0,133 · E3 0,267 → agregado 8;
  `20260819T220100Z-46ab9dc70f` (v9) E1 0,200 · E2 0,133 · E3 0,333 → agregado 10;
  **vigente** (v10 + guarda afrouxada + E4) E1 0,333 · E2 0,267 · E3 0,267 ·
  E4 0,333 → agregado 13.
  **Isto é o número real, promovível ao README.** O `dev` (10 perguntas) tinha
  sugerido híbrida em 0,600; no congelado ela nunca passou de 0,333 — o `dev`
  nunca teve poder estatístico para prever o número real.
- **E0–E3 rodou no `dev` três vezes em 2026-08-16/17**, contra o índice
  **integral**, ~40 chamadas e ~US$ 0,04 cada. **A vigente é a run
  `20260817T181108Z-f1158b4907`** (depois do redesenho da RN02 + da
  propagação de unidade, ver bullets abaixo): exatidão **E3 0,600 · E1/E2
  0,400 · E0 0,000**; recall@5 E3/E2 1,000 · E1 0,833; recusa correta 1,000
  em todas; zero erro de infraestrutura; zero resposta com número errado
  passando (conferido caso a caso). As duas runs anteriores
  (`20260817T004427Z-...`, exatidão 0,200/0,200/0,200; e a de 16/08,
  0,000/0,000/0,000) ficam só como trilha da progressão. **Ainda é `dev`, n=1,
  10 perguntas — não promover para o README.** O ganho de E3 (0,200→0,600) é
  grande demais pra ser só ruído de amostra, mas o tamanho da amostra
  continua pequeno demais pra declarar vitória.
- **O índice Chroma integral está pronto e carrega** (7.574 chunks desde a
  reconstrução de 2026-08-17 — era 6.812 antes da propagação de unidade
  aumentar um pouco a fragmentação de tabela; `bge-m3` 1024d, hash do corpus
  confere). O bullet antigo, que mandava reconstruir por ainda ser FAISS,
  estava desatualizado.
- **`AGENTS.md` §3.2/§3.3 corrigidas em 2026-08-17** para refletir que a
  migração de OCR já terminou (extrator ativo `mistral_ocr`, cache versionado
  em `corpus/ocr/`, gate G3 rodado) e que o gate G4 rodou e **reprovou** — a
  seção descrevia as duas coisas como pendentes, o que já não era verdade
  desde o commit `83d7cad` (onda paralela). Gates §5 e etapas 1/3/4 do plano
  §7 também corrigidas.

## Decisões e bloqueios em aberto

- **Três correções determinísticas na RN02 (2026-08-18), medidas por replay
  offline sobre o checkpoint congelado — custo zero, nenhuma chamada nova.**
  Vieram do diagnóstico caso a caso das 15 factuais: **8 das 15 tinham número
  certo e página certa e pontuaram zero**; só 4 eram falha real de recuperação.
  1. **Marcador de nota no rótulo** (`^{N}`) fazia a célula do rótulo parecer
     numérica, a linha perdia a métrica e nada nela fundamentava resposta.
     Removido em `_sem_marcador_de_nota`. Medido no índice: devolve o rótulo de
     **454 linhas** de tabela. **`(N)` NÃO é removido** — devolveria zero
     rótulos e apareceria em 6.034 linhas onde parêntese é **negativo
     contábil**; removê-lo trocaria sinal de valor real. Tem contraprova.
  2. **Citação inline no texto** (`[SANTANDER, ..., pág. 11]`, que o modelo
     copia do cabeçalho do trecho): o split de cláusulas quebra em `pág.` +
     `11]`, e a segunda cláusula fica com número e sem métrica. **9 respostas
     traziam o marcador e as 9 foram recusadas — 100%.** Removido só o colchete
     que contém marca de página; `[1.234]` continua sujeito ao grounding.
  3. **Stopwords `conforme`/`segundo`/`reais`/`real`** — conectivo e palavra de
     moeda contavam como conteúdo inventado (derrubaram TSTF009 e TSTF006).
  **Efeito medido (replay):** exatidão E1 3→4/15, E2 2→3/15, E3 3→4/15
  (0,200→0,267 · 0,133→0,200 · 0,200→0,267); das 66 respostas rebaixadas pela
  RN02, **6 passam a ser publicadas**. Suíte 1.302 → **1.314**, nenhuma
  asserção enfraquecida. É estimativa de piso: o Gemini não é determinístico,
  então rodada real pode divergir.
- **Ataque à exatidão (2026-08-19, segunda leva) — 4 correções, todas com
  causa medida caso a caso sobre a rodada congelada vigente.** O diagnóstico
  das 15 factuais deu: 4 acertos + 3 recusas CORRETAS (valor ausente dos
  trechos) = 7 comportamentos certos, e **8 perdas evitáveis**.
  1. **Empresa da citação comparada por identidade canônica**
     (`_mesma_empresa`, usado em `citacoes_sao_subconjunto` e no grounding).
     O corpus usa sigla (`ITAU`, `BB`), o modelo cita o nome do documento
     (`Itaú Unibanco`, `Banco do Brasil`) — igualdade literal zerava a lista de
     chunks citados e derrubava a resposta inteira. **8 de 106 citações (8%)
     não casavam; duas só por caixa.** `APELIDOS_BANCOS` resolve; citar banco
     diferente continua órfão (tem contraprova).
  2. **`_tem_negacao` não lê mais "não controladores" como negação** — é conta
     contábil, aparece em **270 chunks**. `_e_modal` já normalizava; esta não.
  3. **Grupo métrico herdado do título da seção** quando a linha não tem grupo
     próprio. O release nomeia a métrica em `### Indicadores de Inadimplência`
     e escreve "O indicador acima de 90 dias encerrou setembro em 4,93%".
     **Preenche lacuna, nunca sobrescreve** (contraprova no teste).
  4. **Stopwords de atribuição** (`pelo`, `informado`, `divulgado`, …):
     "conforme informado pelo BB" diz de onde veio o fato, não afirma fato.
  **Replay: E1 2→4/15, E2 2→3/15, E3 4→4/15.** Suíte 1.324 → **1.349**.
  **Não medido com chamada real ainda.**
- **Terceira leva (2026-08-19, fim da sessão): 2 de 3 mudanças pedidas foram
  feitas; a terceira foi RECUSADA COM EVIDÊNCIA.**
  1. **Guarda afrouxada onde um dos lados não nomeia grupo métrico**
     (`metricas_compativeis`): quando resposta E evidência nomeiam grupo, eles
     continuam tendo que ser o mesmo (impede lucro casar com carteira); quando
     um lado não nomeia — linha de tabela de reconciliação, rótulo "IFRS -
     valores atribuíveis aos acionistas controladores" — cai na sobreposição de
     tokens. **Replay: E3 5→6 (TSTF009). Zero resposta errada admitida**,
     conferido programaticamente. Suíte intacta.
  2. **Prompt endurecido contra arredondamento — `VERSAO_PROMPT` v9 → v10.**
     Manda copiar o número como impresso, proíbe converter escala e proíbe a
     segunda forma entre parênteses. **Efeito NÃO demonstrado:** rodada `dev`
     (`20260819T225003Z-7ce66fd5ba`, 40 chamadas) deu E1 0,200 · E2 0,600 ·
     E3 0,600 contra E1 0,400 · E2 0,400 · E3 0,600 antes — sobe num lugar,
     cai noutro, com n=10. E o modelo **continua arredondando** (DEV007:
     "R$ 3,4 bilhões" para um gabarito de R$ 3.431 milhões — passou porque o
     corretor tolera 1% e o release imprime a forma arredondada também).
  3. **NÃO removi a exigência de repetir os qualificadores da métrica no
     corretor**, apesar de pedido — porque a evidência mostrou que ela não é só
     redação. Removê-la quebra
     `test_exatidao_distingue_total_de_atribuivel_a_controladores`, e o
     contraexemplo é real: no Itaú 1T2026 coexistem
     `IFRS - valores atribuíveis aos acionistas controladores` = **11.636** e
     `...controladores e não controladores` = **11.875**. Sem o qualificador o
     corretor **aceitaria como certa** uma resposta que atribui 11.875 à linha
     errada (±R$ 239 mi). **Mas o pedido tem razão de existir:** no BTG só há
     `Índice de eficiência ajustado` (a versão sem "ajustado" é linha de
     glossário, não valor concorrente), então ali a exigência reprova redação.
     **Caminho certo, não feito: coluna nova no gabarito** com as redações
     aceitas por pergunta — é a regra "acrescente coluna, nunca linha" do
     AGENTS.md. Patch da remoção guardado no scratchpad, não aplicado.
- **Tabela de fatos numéricos (proposta E4) — VIABILIDADE MEDIDA em 2026-08-19,
  custo zero. Vale construir, mas NÃO pelo motivo óbvio.** Materializando
  `_fatos_numericos_da_linha` sobre o corpus inteiro: **163.317 fatos**, 39 s
  de construção, 20 chaves (empresa × trimestre).
  **Cuidado com a métrica errada:** por *recall@5 da página aceita*, o canal
  entrega E3=12/15, fatos=10/15, **união 13/15 — só +1**, retorno ruim. Foi o
  que quase me fez recomendar não construir.
  **A métrica certa é "um chunk com o VALOR EXATO está no top-5?"** — é essa
  que modela a falha real (DEV007 teve `recall_ok=True` e ainda assim respondeu
  "R$ 3,4 bilhões", porque a página recuperada tinha só a prosa arredondada e a
  tabela com `3.431` estava na pág. 13, fora do top-5). Nessa métrica:
  **E3=9/15 · canal-fatos=11/15**, e o canal recupera exatamente os casos do
  tipo DEV007 (TSTF004, TSTF005, TSTF007, TSTF013).
  **CORREÇÃO de 2026-08-20 — o "UNIÃO=13/15 (+4)" que eu publiquei aqui em
  19/08 estava errado e não reproduz.** Ele era união de DEZ chunks (top-5 de
  cada canal), ou seja, o dobro do orçamento de contexto — não uma estratégia,
  outro orçamento. Refeito sob o mesmo top-5 de todo mundo: RRF(E3,canal)=8/15,
  intercalado=8–9/15, **canal sozinho=11/15**, união-de-10=13/15. Fundir PIORA,
  porque dividir cinco vagas entre duas listas expulsa justamente o trecho que
  só uma delas achou. Daí o E4 ser canal PURO, não fusão.
  **Como tabela de RESPOSTAS não serve:** o valor do gabarito está entre os
  candidatos em 14/15, mas em 1º lugar por frequência em só **4/15**, com
  70–700 valores distintos por consulta. É canal de RECUPERAÇÃO, não de
  resposta.
  **Não resolve:** TSTF008 e TSTF015 falham nos dois canais.
- **Onde eu PAREI de afrouxar, de propósito:** TSTF006 e TSTF009 têm o número
  certo e a página certa, mas a evidência é uma tabela de reconciliação cujo
  título é "Comparativo BRGAAP x IFRS" e cuja linha é "IFRS - valores
  atribuíveis aos acionistas controladores" — **em lugar nenhum perto do número
  aparece "lucro" ou "resultado"**. Fazer casar exigiria deixar qualquer número
  de tabela de reconciliação sustentar qualquer métrica. A recusa é
  conservadora e correta; o caminho certo seria enriquecer o gabarito, não
  afrouxar a guarda.
- **Guarda de período por coluna de tabela: implementada, testada e HOJE
  INERTE** (`src/geracao.py`, 2026-08-19). Mapeia coluna→período pelo cabeçalho
  (`| 2T25 | 1S25 |`), distingue trimestre de acumulado e **falha aberto**
  quando falta informação de qualquer lado. Nunca disparou em dado real: só
  342 dos 2.887 chunks de tabela têm período no cabeçalho, e o chunk que
  motivou a guarda (Itaú pág. 38) não tem cabeçalho nenhum. **Fica no código
  como rede para quando o cabeçalho existir — não contar com ela hoje.**
- **Opção B (propagar cabeçalho de tabela no chunking) FALHOU em três
  tentativas e foi revertida** (2026-08-19, `git stash` "opcao-B-ingestao-
  cabecalho-descartada"). (1) herdar cabeçalho entre PÁGINAS: **0 chunks
  alterados** — no corpus real a extração não corta tabela na virada de página;
  (2) repetir cabeçalho na continuação fatiada por capacidade: **0 chunks** —
  tabela que cabe nunca é fatiada, e a que não cabe já repetia; (3) injetar o
  cabeçalho na CAUDA DE SOBREPOSIÇÃO: mexeu (7.574→7.597 chunks) mas **inseriu
  o cabeçalho da tabela ERRADA** (linhas do "Retorno" sob o cabeçalho de
  "Ações") e corrompeu a linha separadora — pior que o defeito original.
  **O defeito segue aberto e medido: 1.162 chunks de tabela (24%) têm linha de
  dados sem cabeçalho, com 4.163 linhas; e 98% das tabelas TÊM cabeçalho na
  extração** — logo é artefato do chunking, mas nenhuma das três hipóteses o
  explica. Próxima tentativa precisa começar por descobrir de qual caminho
  esses chunks saem, não por adivinhar.
- **Nota operacional: a indexação parece travada e não está.** O processo
  Python fica em `poll_schedule_timeout` com ~1% de CPU e não escreve em disco
  até o fim — quem trabalha é o `llama-server` (90% de CPU). Matei uma
  reconstrução saudável aos 26 min por essa leitura errada. **Conferir o CPU do
  `llama-server` antes de concluir que travou.** Reconstrução completa leva
  ~50 min, não ~18.
- **Custo da correção, declarado e não escondido: das 6 respostas destravadas,
  5 conferem com o gabarito e 1 publica número ERRADO** (TSTC005/keyword: cita
  Itaú 22,8% quando o 2T2025 é 23,3%). O 22,8% existe no documento, com o nome
  exato da métrica — é a coluna **1S25 (semestre)** da pág. 38, e a pergunta
  pede o trimestre. **A proteção anterior era acidental:** o `^{2}` quebrava o
  rótulo e a RN02 recusava por bug de parsing, não por detectar o período
  errado. O limite já estava declarado no docstring de
  `_fatos_numericos_da_linha` ("dentro de uma mesma linha as colunas não são
  distinguidas"). **Gargalo seguinte, agora visível e mensurável: atribuição de
  período/coluna dentro da linha de tabela** — trimestre isolado × acumulado do
  semestre é a armadilha, e nenhuma guarda a cobre hoje.

- **RN02 redesenhada de 12 portões para 4** (2026-08-16, `src/geracao.py`). A
  guarda vinha recusando **toda** resposta do `dev` (exatidão 0,000 nas quatro
  estratégias) — inclusive respostas com o número certo. A decisão foi tomada
  por **ablação medida**, não por argumento: cada portão foi avaliado contra o
  contrato de teste (o que ele faz recusar) e contra as 21 recusas reais (o que
  ele custa). Ficaram os 4 que sustentam o contrato — `grounding_numerico`,
  `metrica_da_evidencia`, `qualitativo_com_numero`, `qualitativo_sem_numero`;
  saíram 8 que não recusavam **nenhum** caso a mais. O mais caro era exigir uma
  única grandeza por segmento de evidência: release enuncia valor e variação na
  mesma oração ("totalizou R$ 6.344 milhões, avanço de 3,9%"), então a frase que
  enuncia o fato era descartada. **Suíte intacta em 1.286, nenhuma asserção
  enfraquecida** — os casos de troca de métrica, troca entre bancos/períodos,
  qualificador contábil inventado e causa fabricada continuam recusando.
  **Resíduo, com a ressalva que importa:** sobram respostas com o número certo
  ainda recusadas, mas **11 de 16 delas citam página que não contém o valor** —
  número certo de memória, não de leitura. Recusá-las está **correto**, e é a
  falha exata que a RN02 existe para pegar. Só ~5 são candidatas legítimas a
  falso negativo. **Não afrouxar mais sem antes checar essa distinção**: o teto
  de 12/21 medido na ablação sem restrição é enganoso, porque conta como ganho
  respostas que publicariam número certo com citação que não o sustenta.
  Duas mudanças posteriores (extração ciente de tabela, que pareia o rótulo da
  linha às células numéricas; e remoção da exigência de um único número por
  cláusula, redundante com o `all()` de `analisar_valores`) mantiveram a suíte
  em 1.286 e renderam +1 resposta. O gargalo real que sobrava era outro — ver
  bullet da propagação de unidade, abaixo — e resolvido, a RN02 passou a
  publicar 4 das respostas certas que antes recusava (medido por *replay*
  offline sobre os checkpoints anteriores, sem gastar chamada nova).
- **Achado maior da sessão: metade dos chunks de tabela do corpus não
  carregava a unidade monetária ("Em R$ milhões"), e isso — não a dimensão do
  embedding, a pergunta original que abriu esta investigação — era o gargalo
  real.** Duas causas empilhadas, cada uma exigindo correção separada:
  1. **Ingestão (`src/ingestao.py`, `gerar_chunks`):** a legenda de unidade
     ficava num bloco de TEXTO, a tabela num bloco separado — a tentativa
     inicial de herdar a legenda só dentro da mesma PÁGINA (`segmentar_blocos`)
     recuperou só 1pp (71%→70%) porque tabela grande é rotineiramente cortada
     no meio pela extração, e a legenda fica na página anterior à continuação.
     Correção real: estado `legenda_vigente` do **documento inteiro**,
     atravessando página, threaded pelo laço de `gerar_chunks` — uma seção
     declara a escala uma vez, tudo abaixo herda até a próxima declaração.
     Medido: **71%→24%** de chunks de tabela sem unidade. Índice reconstruído
     em 2026-08-17, custo zero (embeddings locais, extração do cache de OCR
     já versionado): 6.812 → **7.574 chunks**.
  2. **Geração (`src/geracao.py`, `_fatos_numericos_da_linha` dentro de
     `analisar_valores`):** mesmo com a legenda já no mesmo chunk, a RN02
     continuava recusando — o verificador tipa cada CÉLULA da tabela
     isoladamente, e "20.051" sem `R$` na própria célula fica `escalar`
     (20.051), nunca compatível com a resposta do modelo "R$ 20.051 milhões"
     (`monetario`, 2,0051e10). Correção: célula com número nu é reanalisada
     junto com a legenda vigente do chunk (mesmo texto, `extrair_numeros_ptbr_tipados`
     tipa certo) — mas a legenda entra só nessa reanálise pontual, nunca antes
     do split por `|`, porque prefixá-la na linha inteira faz `_fatos_numericos_da_linha`
     escolher a legenda como "rótulo" da linha em vez da métrica real (bug que
     encontrei e não cheguei a versionar — corrigido antes do commit).
  **Efeito ponta a ponta, medido com chamada real (não só replay):** E0–E3 no
  `dev`, exatidão da híbrida **0,200 → 0,600** (ver bullet do E0–E3 acima).
  Suíte com +16 testes entre as duas correções (ingestão + geração), 1.302
  no total, nenhuma asserção enfraquecida, zero resposta errada passando
  (conferido caso a caso nas duas rodadas).
- **`executar_pipeline.py` ganhou `--conjunto {dev,teste}`**, independente de
  `--amostra`. Antes não existia caminho para rodar o `dev` contra o índice
  integral: `--amostra` acoplava "1 banco × 1 trimestre" a "conjunto dev", e o
  índice de amostra cobre 1 documento, alcançando só 2 das 10 perguntas.
  `--amostra` + `--conjunto teste` é rejeitado por código (o índice de amostra
  não cobre o corpus das 45 congeladas).
- **Limitador de taxa do Gemini em `src/geracao.py`** (2026-08-16): espaçamento
  mínimo por modelo antes de cada chamada — 15 req/min nos `-flash-lite`, 5 no
  `gemini-3.7-flash`. Motivo: chamada rejeitada por 429 **também consome cota
  diária**, então estourar o limite por minuto queima cota à toa. Estado é de
  módulo (a cota é do processo contra a chave, não da instância); `conftest.py`
  zera entre testes.

- **Ramo de LLM: Gemini** (`gemini-3.5-flash-lite`, `reasoning_effort=low` —
  trocado de `3.1-flash-lite` em 2026-08-15, **confirmado com n=5 em
  2026-08-16**). Divergência consciente da letra da spec 5.20; motivo agora é
  medido, não só custo — comparação completa contra 3.1 e DeepSeek V4 Flash
  em `resultados/comparacao_llm_2026-08.md`. `Config.gemini_modelo_llm` e os
  preços-padrão em `src/config.py` foram atualizados junto (o docstring da
  classe promete "defaults idênticos aos do `.env.example`").
- **Prompt dos agentes subiu para `a3`** (2026-08-15, `src/agentes.py`):
  bloco estático movido para antes da pergunta (destrava cache de prompt —
  medido 97% de hit na DeepSeek), regras de formato de saída mais rígidas, e
  guarda de código contra observação de ferramenta fabricada em notação
  alternativa (`_PADRAO_OBSERVACAO_FABRICADA`). **Os artefatos vigentes
  citados abaixo (`braço_a.json`/`braço_b.json`, run de 2026-08-12/13) são do
  prompt `a2` e estão desatualizados** — precisam de nova rodada sob `a3`
  antes de qualquer decisão que dependa deles (inclusive o McNemar).
- **Preço da DeepSeek mudou para peak/off-peak em 2026-08-16 16:00 UTC**
  (peak 01h–04h e 06h–10h UTC, o dobro do off-peak). `Config` usa PEAK como
  default — nunca subestima, mas o custo por execução do DeepSeek mais que
  triplicou frente à tabela anterior. Ver `resultados/comparacao_llm_2026-08.md`.
- **CrewAI fixado em 0.193.2, não na linha 1.15.x** (2026-08-12). A linha nova
  exige `chromadb~=1.1.0` e arrasta `lancedb`: o framework de agentes passaria a
  ditar o banco vetorial do projeto inteiro, e o índice atual foi construído com
  `chromadb==1.4.0`. A 0.193.x aceita `chromadb>=0.5.23` e não mexe em chromadb,
  pydantic nem opentelemetry. Motivo registrado em `requirements.txt`.
- **O `max_iter` do CrewAI não é teto** (achado de 2026-08-12): ao atingi-lo, o
  framework só anexa um pedido de resposta final e **continua** iterando. Com um
  modelo que não coopere, o laço não termina. `src/agentes.py` tem teto rígido
  próprio (`LLMComTetoRigido`), com teste que **trava** se ele for removido.
- **Braço B vigente (2026-08-13, run `20260813T200629Z-a9cb37a310`, USD 0,171,
  100 chamadas de LLM, 1.541 s).** Consulta de dado real **12/15, como no A**;
  violações RN01/RN02 2/15. **O Auditor não é carimbo:** 7 `confirma`,
  1 `contesta`, 4 `nao_reproduz` sobre as **12** respostas que chegam a ele —
  5 respostas alteradas, **USD 0,034 por resposta alterada**. Nas 5 apuradas,
  3 acertos (0,60). A contestação é AGTP001 (BB); AGTR003 virou `nao_reproduz`
  nesta amostragem (era `contesta` na rodada anterior) e AGTP002 segue o
  `nao_reproduz` que pega a tabela *Projeções Corporativas* embaralhada.
  **Atenção ao comparar com a rodada preservada:** a temperatura é 0 mas o
  Gemini **não é determinístico** — entre as duas rodadas mudaram veredito,
  teto atingido e taxa de acerto em perguntas que a correção não toca. Só
  AGTC003 mudou *por causa* dela.
- **Discordâncias A×B sob `a2`, preliminar (não é McNemar): 3 de 15** (eram 4
  antes da correção do roteamento) — AGTR003, AGTP001 e AGTP002, todas
  causadas pelo veredito do Auditor e todas na mesma direção (B marca parcial
  onde A publica completa). Nas 5 com gabarito verificado **não há mais
  nenhuma** discordância. O limiar de 6 continua intocado; **nada é
  declarável**, e o teste formal só roda depois da dupla leitura humana.
- **Corrigido (2026-08-13): desambiguação não vai mais ao Auditor.**
  `src/agentes.py` ganhou `dispensa_auditoria` + `COMPORTAMENTOS_SEM_AUDITORIA`;
  `montar_contexto_auditor` — único ponto de passagem entre os dois agentes —
  **recusa** montar contexto para `pergunta_de_desambiguacao`
  (`AuditoriaNaoAplicavelError`), e `responder_braco_b` devolve a desambiguação
  direto, sem `veredito_auditor`. Motivo: pergunta não é afirmação, não há
  evidência a reproduzir, e o `nao_reproduz` mecânico rebaixava a resposta
  **correta** (RN11) a parcial. Efeito medido em AGTC003 ("BTG"): acerto
  **False → True**, igual ao braço A, com 6 → 2 chamadas de LLM (USD 0,0063 →
  0,0034); `desambiguacoes` no resumo B: 0 → 1. Cinco testes novos em
  `tests/test_agentes.py::TestDesambiguacaoNaoVaiAoAuditor`, incluindo o que
  falha se a **fábrica de LLM do Auditor** for sequer chamada.
  **Caso latente do mesmo tipo, não corrigido:** a **recusa** ainda é roteada
  ao Auditor (AGTC002 e AGTC005 gastaram uma rodada cada e receberam
  `nao_reproduz`). `consolidar` ignora o veredito no texto — nenhum dano ao
  usuário —, mas ele entra em `vereditos_auditor` e infla
  `respostas_alteradas_pelo_auditor` sem ter alterado resposta nenhuma. Fica
  para uma medição própria, mesmo critério do resíduo AGTC005.
- **O achado que dominava a rodada, e a correção (prompt `a2` + gate de dado,
  2026-08-12).** Em 14 das 15 perguntas o agente chamava **só**
  `verificar_cobertura` — que não devolve valor nenhum — e pulava para
  `Final Answer` com número e citação inventados (Inter R$ 160 mi contra os
  R$ 417,5 mi reais); RN01/RN02 por código pegavam 11 e as convertiam em recusa
  registrada. Duas frentes, ambas em `src/agentes.py`:
  **(c) prompt** — a regra do lastro virou mecânica ("`bases`/`citações`/número
  não vazio exige ter chamado `buscar_trechos`/`consultar_cvm`/
  `calcular_indicadores`") e ganhou `EXEMPLO_REACT`, um turno completo do
  protocolo textual com companhia **fictícia** (999999, "Banco Exemplo") mais um
  contraexemplo. **O Auditor NÃO recebe esse exemplo**: literal de
  `MARCADORES_RASTRO` na mensagem dele é indistinguível de rastro vazando e
  `conferir_isolamento` o acusa — há teste.
  **(d) gate por código** (`precisa_correcao_de_dado`) — publicar dado sem
  consulta de dado dispara **uma** reexecução corretiva, no **mesmo**
  `LLMComTetoRigido` e na **mesma** caixa de ferramentas (sem orçamento novo), e
  só a segunda falha vira recusa. O Auditor tem o equivalente, com desfecho
  próprio: confirmar sem reexecutar é **rebaixado a `nao_reproduz`**.
  **Medido no braço A, mesmas 15 perguntas:** perguntas que consultaram dado
  **1/15 → 12/15**; violações de RN01/RN02 **11/15 → 2/15**; chamadas de
  ferramenta 16 → 40; custo USD 0,047 → 0,125; latência total 130 s → 547 s.
  A rodada corretiva disparou em **4 das 15** e resolveu o critério nas 4 — ou
  seja, o prompt sozinho levou de 1 para 8 e o gate acrescentou 4.
  **`GEMINI_REASONING_EFFORT` não precisou subir** e o teto de 6 iterações não
  precisou subir (nenhuma rodada corretiva foi cortada por teto).
  **Resíduo declarado:** AGTC005 (C6 Bank) recusa com `cobertura=nenhuma` sem
  ter chamado **nenhuma** ferramenta — afirma uma ausência que não verificou. O
  gate não morde porque recusa não publica dado, e a resposta acerta por sorte.
  Candidato a um gate próprio ("cobertura declarada exige `verificar_cobertura`"),
  **não implementado de propósito** para não misturar duas mudanças na mesma
  medição.
- **Injeção de falha (5.9.4) rodada em 7 perguntas, braço A, 2026-08-12 —
  meta cumprida, leitura fraca.** Ablação **na camada de ferramenta**
  (`RecuperadorComExclusao`), nunca no índice: 79 trechos escondidos, ablação
  completa nas 7 (nenhum resíduo no escopo empresa+trimestre). Resultado sob
  ausência induzida: **7 recusas, 0 afirmações, 0 recuperações pela outra
  camada**. **O que enfraquece a leitura:** o controle (corpus íntegro) recusou
  em 6 das 7 — o agente chamou `buscar_trechos` em **1** de 7 e `consultar_cvm`
  em **nenhuma**, então a recusa acompanha a rede de RN01/RN02, não a ablação.
  A sonda determinística (sem LLM) mostra que a remoção **morde** onde deveria:
  em 3 das 7 (DEV005, DEV006, AGTR003) o valor estava no top-k do controle e
  sumiu no ablado. **Nenhuma pergunta ficou conclusiva no nível do agente**, e a
  taxa de recuperação pela camada estruturada é **0 de 3** com alternativa —
  resultado negativo declarado, não omitido. Custo USD 0,042; artefato em
  `artefatos/resultados_agentes/injecao_falha.json`.
  **Reexecutar com o prompt `a2` custa ~USD 0,04 e passa a medir o que a 5.9.4
  quer medir** — agora o agente consulta o corpus em vez de recusar por RN02.
  Não foi refeita nesta sessão de propósito: misturaria duas mudanças na mesma
  medição.
- **Gate G3: rodado, favorável mas NÃO conclusivo** (`resultados/gate_g3.md`,
  2026-08-11, custo zero — lê o cache em disco). Âncora: OCR 20/20 ×
  pdfplumber 18/20, e 20/20 nos dois tolerando escala — **praticamente empate**,
  porque o valor de capa aparece também em texto corrido e um parser posicional
  o acha. A diferença está na estrutura: 37.612 × 28.268 linhas de tabela
  (+33%), concentrada no **Itaú (3,5×)**; no **BTG o pdfplumber reconstrói o
  dobro**. Ressalva registrada no relatório: contagem de linhas mede quantidade
  de estrutura, **não correção**. A prova real é a exatidão numérica por
  `origem=tabela|texto` (spec 5.4). A decisão de trocar o extrator não se
  reverte, mas também não está demonstrada com a força que a spec antecipava.
- **Gate G4: REPROVOU em 2026-08-11, APROVADO em 2026-08-22** (destravado nesta
  sessão — `resultados/gate_g4.md` regenerado, custo zero, lê painel + cache
  OCR local). Parte A seguia aprovada desde sempre. Parte B foi de **17/20
  conferidos, 2 divergentes, 1 sem âncora** para **20/20 CONFERIDO**, por duas
  ações distintas:
  - **BTG 4T2025 (sem âncora):** localizada a página certa da demonstração
    anual (63/71 páginas sem mapa de caracteres) por **alinhamento geométrico
    de coluna** — a estrutura de tabela sobrevive à corrupção de fonte mesmo
    quando o texto não. OCR pago escopado a essa única página
    (`scripts/ocr_ancora_ifrs.py`; cache em
    `corpus/ifrs/ocr/<hash-do-pdf>.json`). **Custo real USD 0,30, não os USD
    0,14 estimados** — três bugs do próprio script (nome de campo errado,
    gravação fora do `try`, merge de cache por sobrescrita) perderam duas
    chamadas já pagas antes da correta; os três foram corrigidos e ficam
    registrados no script. Resultado: Δ = +0,00002% — CONFERIDO. Detalhe
    completo, inclusive o custo desperdiçado, em
    `resultados/ancora_btg_4T2025.md`. **Achado lateral confirma a RN11:**
    resolver "BTG" por nome (em vez de `cd_cvm`) bate em duas companhias
    (`022616` e `027774`).
  - **SANTANDER 3T2025 e 4T2025 (divergentes):** em vez de excluir as células
    ou corrigir em silêncio, nova infraestrutura de **correção com
    procedência obrigatória** — `corpus/cvm/correcoes_contabeis.csv`
    (versionado), carregado/aplicado por `src/dados_estruturados.py`
    (`carregar_correcoes`/`aplicar_correcoes`), exposto pela view
    `fatos_semanticos` com os dois números (`valor_reais` corrigido e
    `valor_reais_arquivo` original) e a flag `corrigido`. **Guarda
    anti-porta-dos-fundos:** a correção só aplica se `valor_original_reais`
    ainda bater com o painel ao vivo (tolerância 0,5); se a CVM republicar, a
    carga **falha** em vez de aplicar às cegas. Evidência/motivo exigem
    ≥60 caracteres cada. 24 testes em `tests/test_correcoes_contabeis.py`,
    incluindo um canário que trava "toda correção viva hoje é do Santander" —
    qualquer correção nova para outro banco exige revisão explícita desse
    teste. Causa da divergência (inalterada desde 2026-08-11): a conta-pai do
    ITR bate com a demonstração em IFRS ao milhar, as duas contas-filhas não;
    o 4T herdava o erro com sinal invertido por ser derivado do 3T defeituoso.
  **Consequência:** a etapa 10 (modelo preditivo) está desbloqueada — G4 era a
  única pré-condição em aberto. `AGENTS.md` e `README.md` já refletem G4
  aprovado (atualizados nesta sessão).
- **Defeitos de resolução de entidade corrigidos em `src/cobertura.py`**
  (2026-08-11), achados pelo braço C: `extrair_mencoes` devolvia o **slug** em
  vez da forma de superfície, e "Banco do Brasil" reduzido a `BB` passava a
  casar o token distintivo `bb`, que designa também BB SEGURIDADE (023159) —
  desambiguação espúria de nome inequívoco, a inversão do risco 12c. Somava-se
  a isso preposições virando companhia (`com` → M.DIAS BRANCO; `para` → AERIS),
  porque razões sociais abreviam *comércio*/*indústria*. **7 das 15 perguntas do
  conjunto de agentes terminavam em desambiguação; 5 eram espúrias.** A
  ambiguidade real do BTG (`022616` + `027774`) foi preservada e tem teste.
  **O braço C precisa ser reapurado** — 5 das 15 respostas mudaram.
- **Gate G4 anterior (parcial, sem OCR): superado pelo acima.** Aprovado no que era verificável sem
  OCR (os cinco bancos resolvem o conceito certo, `3.09` ≠ `3.11`, valores de
  1T2026 batem com a pesquisa). A parte que faltava — conferir o lucro resolvido
  contra a **tabela de conciliação do release** — **agora é possível**, porque o
  texto extraído existe. Fechar isso é pré-condição para o modelo preditivo
  (etapa 10) treinar.
- **Painel casado com o corpus** (decisão do Ygor, 2026-08-10):
  `CVM_ANO_INICIAL=2025`, não 2011. Motivo no código. **Consequência assumida:**
  o modelo preditivo perde volume amostral — com 4 trimestres o split temporal
  fica magro. Se a etapa 10 precisar de mais dado, a saída é reabrir a janela
  **só para o treino**, mantendo o painel consultável casado com o corpus.
- **Conjunto separado para a camada de agentes** (decisão do Ygor, 2026-08-10).
  As 45 ficam intocadas. Motivo medido: o subconjunto pareado de n=15 da spec
  5.9.3 **não é extraível** das 45 (máximo 8, e sem nenhum caso `so_painel`),
  porque os requisitos de 5.9.2/5.9.3 nasceram **depois** do congelamento de
  2026-07-29. `conjunto_padrao/conjunto_agentes.csv` **foi criado em
  2026-08-10**: 15 perguntas (6 cobertura, 5 reconciliação, 4 projeções), com as
  cinco colunas da revisão 2 dentro do próprio arquivo e mais três (`subconjunto`,
  `status_gabarito`, `fonte_gabarito`). Racional, esquema e composição no
  `conjunto_padrao/README.md`; guardas em `tests/test_conjunto_agentes.py`.
- **Bloqueio para rodar os três braços A/B/C:** 10 das 15 linhas do conjunto de
  agentes têm valor vindo de release lido **uma vez** só, marcado
  `PENDENTE DE CONFERÊNCIA HUMANA` (5 estão conferidas por consulta ao painel).
  Falta a **dupla leitura independente**, em outra data — trabalho do Ygor. Rodar
  o experimento antes disso mediria o extrator, não os agentes. A figura
  *Projeções Corporativas* do BB sai da extração com as colunas embaralhadas e é
  a parte mais frágil (`AGTP001`–`AGTP003`).
- **As colunas da revisão 2 vivem em arquivo separado**, não em
  `perguntas.csv`: `conjunto_padrao/anotacoes_revisao2.csv`, ligado por `id`.
  Fundir mudaria o hash do CSV, que entra no fingerprint da avaliação
  (`src/avaliacao.py:898` e `:956`), invalidando checkpoint, journal e cache —
  reexecução paga sem que uma só resposta mude. A fusão fica para quando o
  fingerprint for invalidado de qualquer jeito; o caminho está escrito no
  `conjunto_padrao/README.md`.
- **`TSTA006` continua correta** como recusa, graças ao painel casado com o
  corpus. Se a janela do painel for reaberta, esse gabarito precisa ser
  reavaliado — a recusa ficaria meia-errada.
- **Gate G1 (Azure)** resolvido para o pré-deploy; **G2 fechado** em 2026-08-07.
- Teto de orçamento em **USD 25** (spec 5.20).
- `.docs/especificacao.md` menciona a vaga de origem e **nunca** é publicada.
  Já saiu do rastreamento, mas permanece no histórico antigo: um repositório
  público deve nascer de histórico limpo (regra dura §0).

## Correções ao documento de pesquisa (medidas no dado real, 2026-08-10)

Registradas aqui porque contradizem `.docs/PESQUISA_TECNICA.md`, que é
tratado como fonte na spec:

- **`VERSAO` republicada: 0 linhas descartadas.** As versões chegam a 6 (não 3),
  mas nenhuma partição tem duas — o arquivo já traz só a última.
- **A armadilha `3.09`/`3.11` não morde numericamente nesta janela:** os dois
  códigos têm valor **idêntico** em BB e Bradesco (participações estatutárias =
  0). Ela é real, porém semântica. Onde morde no dado é no balanço:
  `cd_conta='2.07'` devolve o patrimônio de BB/Bradesco e **zero** para Itaú,
  BTG e Santander.
- **O arquivo da CVM não fecha:** Santander, ITR 3T2025, `3.09` ≠
  `3.09.01`+`3.09.02` por 356.909 mil. A carga conta e reporta (656 fatos no
  painel, 3 no corpus) — não conserta nem descarta. **Em 2026-08-11 o G4
  identificou de quem é o defeito:** são as duas contas filhas que estão erradas
  (o total bate com a demonstração em IFRS ao milhar). O gap era o sintoma; a
  âncora externa disse qual das três linhas mente.
- **Santander usa dois planos no mesmo exercício** (ITR `3.09`/`2.08`, DFP
  `3.11`/`2.07`), único caso entre 470 companhias.

## Próximo passo concreto

- **O que falta para o McNemar (RF26, etapa 12) rodar de verdade: só a dupla
  leitura humana dos 10 gabaritos pendentes — tarefa do Ygor.** A comparabilidade
  de prompt está resolvida (A e B em `a2` desde 2026-08-13). Com 5 perguntas
  apuradas o teste não tem poder nenhum: há 1 par discordante contra um limiar
  de 6. O braço C **já foi reapurado** em 2026-08-21 (0/15 registros mudaram) —
  esse débito está fechado.
- **Por que o agente não consultava o painel: respondido em 2026-08-12.** Era
  prompt + protocolo, não o tier do modelo — `GEMINI_REASONING_EFFORT` continua
  em `low` e a taxa de consulta de dado foi de 1/15 para 12/15. Ver o bullet do
  prompt `a2` acima. Fica em aberto só o resíduo AGTC005 (recusa sem verificar
  cobertura).
- **G4 resolvido em 2026-08-22 — nada pendente dele.** Ver bloco acima.
- **Etapa 14 está fechada — nada pendente dela.** Próximo trabalho é outra
  etapa do plano (§7 do AGENTS.md): 10 (modelo preditivo, agora desbloqueado),
  11–13 (agentes/observabilidade além do já construído), ou a leitura humana
  de groundedness abaixo.
- **O bloqueio do fingerprint de 2026-08-22 está FECHADO.** Ele veio de um bug
  real, não do guarda: `src/auditoria.py::_validar_metricas_contra_checkpoint`
  não conhecia `avaliar_exatidao_comparativa` e reconstruía `exatidao_ok` como
  `None` para toda pergunta comparativa, reprovando 50 linhas corretas com
  "Flags automáticas do checkpoint foram adulteradas". Corrigido, com a
  fixture `_item_auditoria` de `tests/test_hardening_final.py` junto.
- **Auditoria de groundedness: 10/15 = 0,667 na rodada `a0bea525`, meta 0,90
  NÃO atingida.** Vereditos do Ygor em
  `artefatos/resultados_avaliacao/auditoria_groundedness_a0bea525.json`,
  análise em `resultados/auditoria_groundedness_2026-08-22.md`.
  **Nenhuma alucinação publicada: os 5 erros são todos falso negativo da
  guarda.** Duas leituras importantes que saíram dela:
  - **`grounded` foi preenchido como "o sistema fez a coisa certa?"**, não como
    "o texto publicado afirma algo sem lastro". Pela leitura literal o score
    seria 15/15, porque 12 das 15 terminaram em recusa e recusa não alucina —
    número verdadeiro e vazio. A escolha está declarada no relatório.
  - **TSTC008 é descarte CORRETO, ao contrário do que a auditoria marcou.** A
    diferença entre duas taxas é em **pontos percentuais**: o modelo escreveu
    `26,6% - 24,8% = 1,8%` e a guarda recusou com razão; `1,8 p.p.` passaria.
    Travado em teste para nenhuma correção futura afrouxar isso.
  **Esta auditoria vale para um fingerprint já obsoleto** — refazer sobre a
  rodada vigente `5b9b142d`.
- **Juiz automático medido contra a auditoria humana (etapa 13, 2026-08-23):
  concordância 0,867 (13/15), USD 0,0161.** `gemini-3.7-flash` julgando
  `gemini-3.5-flash-lite` (juiz ≠ gerador de propósito), sobre os 15 cujo
  veredito humano foi dado ÀS CEGAS — rodar o juiz antes da leitura ancoraria
  o auditor e a matriz viraria artefato. Relatório em
  `resultados/concordancia_juiz_humano_2026-08-23.md`.
  - **A célula `juiz acertou × humano errou` é ZERO:** o juiz pegou os 5
    falsos negativos que a leitura humana pegou. Serve como TRIAGEM.
  - **E falhou no caso decisivo.** Em TSTF006 disse "fundamentada" porque viu
    `12.144` no trecho — sem conferir de qual período era a coluna. É *número
    certo, coluna errada*, a falha que o projeto existe para pegar. A guarda
    determinística acertou onde o LLM mais forte errou. **Confirma a spec 5.23
    com dado do próprio projeto** e é a razão de o juiz NÃO poder decidir
    publicação.
  - Cota: 20 req/dia, **5 req/min** — o script pausa 12,5 s entre chamadas.
- **Próximo passo imediato:** rodar `python -m scripts.preparar_auditoria_final`
  sobre a rodada vigente `5b9b142d` e refazer a leitura humana dos 15. Depois
  dela, `scripts/executar_estabilidade.py --permitir-api-paga` (30 chamadas) e
  `scripts/consolidar_auditoria_final.py` — a promoção a `completa` exige
  groundedness ≥ 0,90, então com 0,667 ela ficaria em
  `auditoria_concluida_meta_nao_atingida`.
- **Gasto acumulado nos logs versionados: USD 2,87** de um teto de 25 (RNF03).
- Em paralelo, fazer a **dupla leitura** dos 10 valores de release marcados como
  pendentes em `conjunto_agentes.csv` (a página física de cada um está em
  `fonte_gabarito`). Sem ela, 10 das 15 seguem em `pendente_conferencia_humana`
  e a taxa de acerto dos três braços continua apoiada em 5 perguntas só.
