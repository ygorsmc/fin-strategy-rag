# MEMORY.md

> Handoff entre sessões. Leia no início de toda tarefa; ao final, **sobrescreva**
> o que ficou desatualizado. Não é changelog — o Git já é.
> Regras de uso em [AGENTS.md](AGENTS.md#10-memória-entre-sessões--memorymd).
>
> **Onde as coisas vivem:** o plano e as regras de conduta são o `AGENTS.md`; o
> que já foi **medido e descartado** está em `resultados/becos_sem_saida.md` —
> **consultar antes de propor ideia nova**; os números de cada rodada vivem em
> `artefatos/` e no relatório datado em `resultados/`. Aqui fica o **estado da
> execução**: o que está em aberto e não se deduz do código.
> Enxugado em 2026-09-08, de 498 linhas.
>
> **Mudança de 2026-09-11:** o `AGENTS.md` foi reduzido de 1.402 para ~880
> linhas. Os vereditos de candidatos que viviam em §3.7–§3.17 foram
> consolidados em `becos_sem_saida.md` (§F, novo, e §A.1/§C-bis); as regras de
> método que estavam enterradas naquela narrativa viraram o **§4.4**; e o
> "Estado atual do repositório" e o estado dos gates vieram **para cá**, que é
> onde estado vive por contrato. Nada foi apagado.

## Estado atual

### Implementado e coberto — não regredir

Configuração validada; parser numérico pt-BR; extração via Mistral OCR
*content-addressed* com cache versionado em `corpus/ocr/` (RNF10) e
`pdfplumber` como alternativa atrás da mesma interface; chunking e
teste-sentinela independentes; embeddings plugáveis; índice com transação,
checksums e guarda RNF09; recuperação E0–E4 com subconsulta por banco; geração
JSON com RN01 e grounding numérico da RN02; avaliação retomável com fingerprint
v3, journal/checkpoint, teto de custo e locks; interface cacheada com pergunta
livre opt-in.

**Dados congelados:** `corpus/metadados.csv` com 20 documentos íntegros
(interseção `2T2025`–`1T2026`), `corpus/ancoras_sentinela.csv` cobrindo 20/20,
`conjunto_padrao/perguntas.csv` com 10 `dev` + 45 `teste`. O contrato que
proíbe mexer neles está em AGENTS.md §4.3.

### Gates — estado medido

| Gate | Estado |
|---|---|
| **G1** Azure OpenAI | ❌ **Não disponível** (`resultados/gate.md`, 2026-07-15). Reservado ao pré-deploy |
| **G2** cobertura CVM para o rótulo T+1 | ✅ Fechado em 2026-08-07 — 1.351 observações de trimestre isolado, ~29% de positivos |
| **G3** OCR × `pdfplumber` | ✅ Rodado em 2026-08-11, **favorável mas não conclusivo** (`resultados/gate_g3.md`) |
| **G4** lucro pelo mapa semântico, banco a banco | ✅ Reprovou em 2026-08-11, **APROVADO em 2026-08-22** — 20/20 CONFERIDO (`resultados/gate_g4.md`). BTG 4T2025 por OCR pontual; Santander 3T/4T2025 por correção com procedência declarada |
| **L1** Ollama local · **Gemini** | ✅ Passaram em 2026-07-15, com `prompt=v1` — relatórios **históricos**, não comprovam o prompt atual |

### Interface — a etapa 13 virou bloqueio de ENTREGA (medido em 2026-09-14)

O Streamlit sobe sem exceção e **não serve para nada de fábrica**: os dois modos
estão fechados. O cacheado falha porque `metricas_teste.json` está em
`status="auditoria_manual_pendente"` (`groundedness_manual_15` e
`estabilidade_10x3` pendentes) e `app_streamlit.py` exige `"completa"`; o modo
livre é opt-in desligado por padrão (RNF12). Sem a auditoria da etapa 13 não há
resposta cacheada na tela — deixou de ser dívida de avaliação e passou a ser o
que impede a demonstração.

**Mitigado em parte, não resolvido:** a etapa 15 ganhou **rota de consulta ao
painel contábil** ligada aos dois modos, inclusive ao cacheado — sem LLM, sem
segredo e sem custo, por isso elegível ao modo demonstração. Reusa
`responder_por_gabarito`; a interface só adapta, renderiza a tabela de fatos,
avisa o valor derivado (RN10) e mostra a procedência (RN01).
`tests/test_rota_estruturada.py` (38 casos) trava as guardas de entrada
(RN05/RN06) e da RN07 **dentro** da rota — um chamador futuro não as contorna
esquecendo de varrer antes. Suíte: **2139 verdes** em 2026-09-15; +39 desse
total **não são desta onda** (ver composição na seção de estado abaixo).

**Achados da auditoria independente de 2026-09-15, tratados no mesmo dia:**
portão duplo de RN05/RN06 dentro da rota (achado 6, **fechado** — os casos
chamam a função sem varredura prévia, com frases que trazem conceito do
vocabulário para que sem o portão produzissem fatos); e a resposta do painel
passou a declarar que é o número contábil arquivado e que o gerencial do
release não foi lido, sempre que a companhia tem release (achado 2,
**mitigado, não fechado** — a paráfrase "segundo o resultado apresentado a
investidores" continua chegando ao painel, agora com a declaração).
**Em aberto:** achado 3 — 5 de 10 paráfrases prospectivas ("outlook de lucro",
"tende a piorar") atravessam a guarda da RN07 e saem com tabela de fatos no
modo demonstração. Lacuna do detector (§3.6); a rota ampliou o raio do dano.

**Defeito que a rota introduziu e a revisão pegou — corrigido no mesmo dia.**
`extrair_conceito` casa "lucro líquido" em qualquer posição, então a rota
sequestrava **5 das 45 congeladas**, respondendo o número CONTÁBIL a perguntas
que diziam "Segundo a demonstração gerencial do Santander". Em 3 delas o valor
era materialmente outro (Santander 2T2025: R$ 1.928 mi contra R$ 3.659 mi do
release) e uma era **adversarial**, cuja resposta certa é recusar a premissa.
Corrigido com deferência à camada documental antes de abrir o painel; medido
0/45. **O que a correção NÃO resolve:** a lista de radicais foi derivada das
próprias 45, então paráfrase que aponta o release sem casar radical continua
indo ao painel ("segundo o resultado apresentado a investidores" → devolve o
contábil). Fechar isso exige conjunto de paráfrases que não existe — mesma
classe da lacuna do detector prospectivo (§3.6).

**Defeito pré-existente corrigido junto:** `responder_prospectiva_se_couber` lia
`resolucao.companhia`, que não existe em `ResolucaoEntidade` (é `.resolvida`).
O `except Exception` do chamador engolia o `AttributeError` num warning e a
resposta rica da RN07 nunca chegava à tela — a fronteira se manteve pelo portão
profundo, por acidente e não por desenho.

**Falso bloqueio da RN02 corrigido — era defeito da EVIDÊNCIA, não da guarda.**
A congelada TSTF004 saía rebaixada com o valor do gabarito (`11.508`), a página
certa (5) e citação válida. Causa: o sumário do Itaú tem a primeira coluna
mesclada e o OCR a devolve como ano solto (`| 2025 | Resultado Recorrente
Gerencial | 11.508 |`); o seletor de rótulo elegia a primeira célula sem número
— o ano — e a linha chegava **sem grupo métrico** à comparação, então
`metricas_compativeis` não tinha o que casar. Rótulo passou a exigir letra
(`_CARACTERE_DE_PALAVRA`, `src/geracao.py`). A guarda **não** foi afrouxada: há
contraprova de que métrica trocada, valor inventado e trimestre trocado
continuam recusados (`TestRotuloDeLinhaComColunaMesclada`). Mesma família do
§3.4, no eixo da linha em vez do da coluna.

**Consequência a não esquecer:** isto muda a exatidão factual medida. Os
números publicados da rodada de 2026-08-21 descrevem o código anterior.

**O fingerprint da rodada congelada JÁ ESTAVA VENCIDO antes desta sessão.**
`sha256_codigo_execucao` diverge em `src/config.py` e `src/normalizacao.py`
desde o commit `3380b88` (2026-08-24), um dia **depois** da rodada; agora soma
`src/geracao.py` e `app_streamlit.py`. Ou seja: destravar o modo demonstração
**não depende só da auditoria humana** — exige reexecutar o congelado (225
chamadas) contra o código atual. Antes desta medição a suposição corrente era
que bastava concluir a etapa 13.

**RETRATADO no mesmo dia: "a interface está na pior estratégia" não se
sustenta.** A versão anterior deste parágrafo dizia que a `semantica` (0,333)
perdia para a `hibrida` (0,467). Os 0,467 são da rodada de 08-23; a rodada
executada às 22:11 de hoje mede **0,333 para as duas**. O argumento morreu na
medição da própria sessão que o escreveu. O que permanece verdadeiro e não
depende de rodada: `estrategia_demo_e_auditoria` **herda** `ESTRATEGIA_PADRAO`
do `.env` (`src/avaliacao.py:971`) — a estratégia da demo nunca foi escolhida,
e nenhum relatório a justifica. Trocá-la mexe no fingerprint (§4.3), então é
decisão explícita do Ygor.

**Rodada nova: `c3a03ff7`, run `20260915T011103Z-85fbfadd35`, US$ 0,2577,
zero erros** (grade nominal de 225 chamadas; o artefato registra 226 tentativas
— `semantica` teve uma repetição sem telemetria). **Rótulos E1/E2 corrigidos em
2026-09-19** — a versão anterior trocava os dois (dizia "E2 0,400 · E1 0,333"),
recontado do JSONL por NOME de estratégia. Factual: E0 `closed_book` 0,000 ·
E1 `keyword` 0,400 · E2 `semantica` 0,333 · E3 `hibrida` 0,333 · E4 `fatos`
0,400. Comparativa: E4 0,400 · E2/E3 0,100 · E1 0,000. Recall@5: E1 0,920 ·
E3/E4 0,880 · E2 0,800. Recusa 10/10 em todas com documento; E0 8/10.
**Recall idêntico em 225/225** — a recuperação é determinística e toda
variação está na geração: 15 vereditos mudaram, 8 para melhor e 7 para pior,
com o MESMO modelo. Pelo limiar do §4.2 (6 discordâncias na mesma direção),
indistinguível. A melhora das comparativas foi **isolada** como efeito da
correção da RN02 (TSTC005 dá True com o patch e False sem ele); as quedas no
factual **não** são dela (TSTF005 dá veredito idêntico nos dois códigos — o
modelo deixou de escrever a unidade).

**PENDÊNCIA DE PUBLICAÇÃO, em aberto:** o README ainda publica a rodada de
08-23, inclusive o 0,667 de E4 com dois parágrafos em cima. A rodada de hoje
mede 0,400 para E4. Publicar a melhor de duas medições sem dizer que há duas é
o que o §4.2 existe para impedir — **decidir antes de qualquer entrega**.

**E o fingerprint de hoje já nasceu vencido:** a correção de deferência entrou
depois da rodada e mudou `app_streamlit.py`. Reexecutar de novo custa outros
~US$ 0,26 e só vale a pena depois que o código parar de mudar.

**Ensaio do roteiro do vídeo da Etapa 1 (2026-09-18, 2 chamadas, US$ 0,0027):**
7/7 passos sem exceção pela interface real; TSTF004 e TSTF014 acertaram ao vivo.
Achou 4 defeitos de tela; 1–3 **corrigidos no mesmo dia** (só apresentação:
aviso em vez de erro vermelho na auditoria pendente, fontes limpas com as
citadas primeiro, valor legível ao lado do exato), 4 é desenho (13 s de espera
pela RN02). Suíte 2753 verdes; uma asserção de literal substituída e declarada
(`resultados/ensaio_roteiro_video_2026-09-18.md`). Falta ensaiar a 3ª pergunta
RAG (TSTF011) — não autorizada ainda. A avaliação da Etapa 1 é
por vídeo: o que aparece na tela durante a gravação é o que conta.

**Entrega escrita da Etapa 1 (2026-09-19, reduzida em 2026-09-20):** `docs/`
com 3 páginas em Markdown (visão geral, desafio CBL, arquitetura) +
`scripts/build_docs_html.py`, que emite `docs/documentacao.html` (HTML único,
autocontido, mesmo padrão do projeto anterior do Ygor). O HTML é ARTEFATO
GERADO — editar o Markdown, nunca ele. **Decisão do Ygor:** entregar só o que a
Etapa 1 pede; evidências medidas e limitações saíram para
`docs/nao_entregue_etapa1/` e voltam na Etapa 3 (basta reinseri-las em `PAGES`).
Com isso a entrega não publica número de rodada nenhum, e a decisão sobre qual
rodada o README publica segue aberta.

**Rota do painel com LLM-intérprete, LIGADA à interface (2026-09-20).** A etapa
15 ganhou uma terceira rota, `responder_plano_se_couber` em `app_streamlit.py`,
entre o casador de graça e o corpus. O LLM devolve, **numa chamada**, um plano
de consultas atômicas — uma por (companhia, conceito, trimestre) — e cada célula
vira seu próprio `SELECT`; o SQL é template, a aritmética é Python, o modelo
nunca vê número. `src/plano_consulta.py`, `tests/test_plano_consulta.py` (55) e
`tests/test_rota_plano_interface.py` (20). A rota anterior de intenção única
(`src/intencao_consulta.py`, 31 casos) **continua**, como base compartilhada e
como termo de comparação — não está ligada à interface.

**Três comparações reais com as 12 perguntas de `scripts/comparar_rotas_painel.py`
(US$ 0,0115 a rodada, artefato em `artefatos/comparacao_rotas_painel.json`):
zero divergência de valor entre as três rotas em todas as execuções.** O ganho
medido é um caso que nenhuma das outras duas resolve — "qual dos cinco bancos
lucrou mais" devolve os 4 resolvidos e declara o BTG pendente, onde a
determinística não identifica companhia nenhuma e a intenção única morre inteira
na desambiguação.

**Quatro guardas que existem só por causa do formato de célula**, cada uma com
contraprova: conceito único em comparação/variação (com uma célula por
companhia, nada impedia comparar `consolidado` de um com `controladores` de
outro); comparação incompleta **não elege vencedor** (o ausente pode ser o
maior — publica-se a ordem, nunca o superlativo); teto de 24 células; e período
obrigatório. **Decisão do Ygor (20/09):** pergunta sem trimestre deixou de
devolver a série inteira e virou recusa com justificativa
(`PeriodoIndefinido`), para o usuário reformular.

**Duas famílias de recusa, com destinos diferentes** — a distinção é do código,
não do prompt: `RecusaDeReformulacao` (período ausente, réguas misturadas) vai
à tela, porque só quem perguntou resolve; `ErroDeIntencao` genérico (conceito
fora do painel, companhia inexistente) encaminha ao corpus, que pode ter a
resposta. **A chamada é paga nos dois casos e debita cota e orçamento inclusive
quando encaminha** — não contá-la abriria um caminho de gasto fora do teto da
RN03.

**Cache por célula** (`CacheDeCelulas`, `st.cache_resource`), chaveado por
(cd_cvm, conceito, trimestre) e compartilhado entre sessões — é número público
do painel, sem texto de usuário nem PII. **A validade é do ARQUIVO, não do
tempo:** `conferir_painel` compara tamanho e mtime e esvazia tudo se o painel
for reconstruído; um TTL serviria número velho depois de uma reconstrução.
Economia medida no arnês: 3 de 13 consultas.

**O que esta rota NÃO resolve, e continua aberto:** ela roda **depois** do
casador determinístico, então herda a lacuna do detector prospectivo (§3.6) e a
da deferência documental — as duas guardas moram dentro dela, mas têm o tamanho
dos detectores de sempre. E o `motivo` de recusa é o único texto escrito pelo
modelo que chega à tela; passa por `avaliar_saida`, nada mais.

**Vídeo da Etapa 1 — roteiro e slides prontos (2026-09-21).**
`docs/roteiro_apresentacao_etapa1.md` (584 palavras faladas = 3m54 a 150 ppm,
cronometrado bloco a bloco contra o alvo) e
`docs/apresentacao_etapa1.pptx` (8 slides), emitido por
`scripts/gerar_slides_apresentacao.py`. O `.pptx` é ARTEFATO GERADO — editar o
script e reemitir, como o HTML da entrega. `python-pptx` fica **fora** do
`requirements.txt` (RNF12) e do `.venv` do projeto, que tem o conflito de pin
aberto; o script diz como criar o ambiente à parte. Slides conferidos por
renderização (LibreOffice → PNG): uma colisão de título com subtítulo foi
achada e corrigida assim.

**Notas do apresentador acrescentadas em 21/09**, uma por slide, com o texto da
fala do roteiro — fonte única é o `.md`, o script é reescrito se o roteiro
mudar. QA completo: conteúdo (`markitdown`, sem placeholder), estrutura
(`validate.py` da skill de pptx, `All validations PASSED`) e visual
(re-renderizado, sem regressão).

O roteiro dá 2m20 dos 4 min à demonstração, porque a rubrica de 70% nomeia
quatro coisas que precisam **aparecer na tela** — streaming, session state, UX
writing e system prompt —, e cada uma é dita em voz alta no momento em que
aparece. **Nenhum número de rodada é publicado nos slides**, pela pendência de
publicação ainda aberta (README publica `5b9b142d`, vigente é `c3a03ff7`); só
entram fatos estáveis (20 documentos, guardrails 20/20 e 0/45).

**Dois slides acrescentados em 21/09, com o estado real declarado.** O de
*relevância* argumenta com os dois números já medidos no projeto (Santander
2T2025 contábil × gerencial; a conta `3.09` valendo lucro líquido em 3 dos 5
bancos), em vez de adjetivo. O de *como a resposta é montada* explica os cinco
passos da rota sem LLM e **declara a camada de agentes como "construído e
testado"** — `src/agentes.py` existe com o isolamento travado por 16 casos em
`tests/test_isolamento.py`, mas **não está ligada a `app_streamlit.py`** e a
comparação dos três braços não rodou. O roteiro tem uma seção "o que NÃO
afirmar" por causa disso.

**Achado que o roteiro registra como "não demonstrar":** na interface ao vivo, a
rota determinística INTERCEPTA pergunta de comparação e de variação — responde
listando os valores, sem comparar e sem calcular a variação —, e com isso a rota
do plano nunca é chamada para elas. Os ganhos medidos em
`artefatos/comparacao_rotas_painel.json` valem para o arnês, **não** para a
tela. Corrigir exige `responder_estruturada_se_couber` ceder a vez quando
detecta operação que não sabe cumprir; **não foi feito**, é decisão do Ygor.

### Bloqueio de dependências, em aberto

A resolução limpa que soma `requirements-guardrails.txt` está travada por
conflito de pin: `numpy==2.5.1` no runtime × `presidio-analyzer==2.2.364`, que
exige `numpy<2.5.0`. **Tratar em onda própria**, nunca como efeito lateral de
outra tarefa.

- **Etapa ativa (plano §7): 13 (Langfuse + DeepEval).** Concordância juiz ×
  humano medida; groundedness da rodada vigente **ainda não auditada**.
- **Prioridade solicitada agora: formulação de ML com DFC própria para bancos.**
  **B-DFC-01J:** juros de instrumentos de captação, no mesmo consolidado IFRS.
  Dois especialistas concluíram parecer independente, réplica e tréplica;
  admitiram somente piloto documental. Acordo e contrato financeiro:
  `resultados/debate_bancos_dfc_2026-09-09.md` §§3 e 6. Plano:
  `resultados/plano_piloto_bancos_dfc_2026-09-09.md`.
  **O piloto FOI EXECUTADO em 2026-09-09** (custo zero, sem rede):
  `resultados/piloto_bancos_dfc_2026-09-09.md`, `scripts/piloto_bancos_dfc.py`,
  `tests/test_piloto_bancos_dfc.py` (77 casos), `artefatos/b_dfc_01j/`.
  Revisado por `auditor-conformidade`: 7 defeitos achados e corrigidos (§10 do
  relatório), 2 deles afirmações minhas que a evidência não sustentava.
  **Rodada atual: os três achados da conferência independente de C1–C6 foram
  IMPLEMENTADOS em 2026-09-11** — contratos em
  `resultados/contratos_correcao_rc5_rc6_b_dfc_01j_2026-09-11.md` (registrados
  antes de codar), implementação em
  `resultados/implementacao_rc5_rc6_b_dfc_01j_2026-09-11.md`, +12 contraprovas.
  A conferência (`resultados/conferencia_independente_c1_c6_b_dfc_01j_2026-09-11.md`)
  aprovou C1–C4 e achou que **C5 e C6 estavam fechados só no PRODUTOR**: G0
  certificava com zero evidência independente e com o campo ausente; G3
  aprovava declarando o próprio cálculo de poder inválido, se B3 fosse
  habilitado. Corrigidos — G0 exige evidência independente presente, inteira e
  > 0 (piso deliberadamente SEM cobertura mínima, que o contrato C5-B não
  fixou); G3 passou a ter **três vetos independentes**, com
  `PODER_REDESENHADO_APOS_F3 = False` na conjunção de aprovação. A dívida
  preexistente R-SUPORTE (eleito com um único erro levantava `StatisticsError`,
  que `_medir` não captura, derrubando o relatório inteiro) virou
  `ReprovaEmAberto` com motivo. Veredito inalterado: **NÃO AUTORIZA TREINO**,
  decisivo em G0, J elegível zero. **F3 segue sem redesenho** — a diferença é
  que a invalidez agora VETA em vez de só estar escrita ao lado.
  **Falta conferência independente desta terceira onda.**
  A pista documental de subordinadas permanece aberta; não repetir
  impossibilidade universal nem certificar a série futura com o auditor atual.
  **Nenhum modelo foi treinado.**
- **Regra de método que saiu das três ondas, e vale para contrato futuro:**
  contrato que cria campo de estado só está cumprido quando existe contraprova
  exercitando a **decisão** governada por ele. Asserção sobre o JSON publicado
  prova o produtor e nada sobre o consumidor — foi assim que o achado F10
  (exigência que existe como texto e não participa da condição de aprovação)
  reapareceu **dentro dos contratos escritos para corrigi-lo**, duas vezes.
- **Conferência das quatro ondas concluída em 15/09: aprovação parcial,
  não fechamento integral.** Parecer com fontes, contraprovas executáveis,
  limites e encaminhamento:
  `resultados/conferencia_quatro_ondas_2026-09-15.md`.
  Não houve correção de código/dados nesta revisão. As mudanças paralelas de
  interface/geração acima não foram certificadas por ela.
- **Conferência QW1–QW8 (15/09) e correções CQW (16/09) — os três achados estão
  FECHADOS, mais um quarto que veio do levantamento de treino.**
  Parecer: `resultados/conferencia_independente_qw1_qw8_2026-09-15.md`.
  Contrato antes do código: `resultados/contratos_correcao_cqw_2026-09-16.md`.
  **CQW-01** (consumidor aceitava estado de adjudicação inválido como "não
  adjudica") passou a levantar contra o vocabulário fechado de E1.2 — a
  exclusão real continua **111 documentos em 35 companhias**. **CQW-02**: a
  linhagem do ativo carrega os quatro campos de H1.4; `dt_ini` sai `None` e
  **assim fica** (saldo de balanço não tem início — 23.395 de 23.395 linhas de
  `BPA`/`1` o trazem nulo). **CQW-03**: errata publicada — **156.100**
  declarações, não 154.160; as contagens por estado sempre estiveram certas.
  **O quarto é de gate: `G0.4` estava congelada no §4 do pré-registro desde
  11/09 e NUNCA fora implementada** — nem contador nem campo no artefato — e os
  três carregadores filtram `IS NOT NULL`, então seria vazia por construção.
  Implementada medindo **fora** do filtro: zero nulos em FCO `6.01` (22.034) e
  Ativo `1` (22.471). `gate_g0([], [], [])` também aprovava. **Nada disso muda
  veredito:** G0 segue reprovando pelos mesmos 132 saltos, fração 0,005874.
  Não houve corrupção do inventário nem vazamento temporal por esses achados.
  **Falta conferência independente desta onda CQW.**
- **ESCALA — adjudicação refeita por declaração e conferida em 15/09.**
  Readjudicação dos 34.952 casos persistidos idêntica ao v2, caso a caso;
  não houve nova varredura integral dos ZIPs nesta conferência.
  Inventário v2: **3.401 casos, 6.456 declarações, 111 documentos
  em 35 companhias**, todas `PENÚLTIMO`, só balanço. Zero nunca prova; a
  premissa "a DFP tem o rótulo certo" está publicada como premissa. **Não
  citar 10.261 adjudicações nem 127 documentos/33.655 linhas.** O zero de
  alterações diretas sobrevive no escopo restrito. Correção de escala, se vier,
  é por declaração — e a chave `(demonstrativo, cd_conta)` do esqueleto não é
  semântica entre planos (RN09).
- **DERIVAÇÃO — contagem e aviso corrigidos e conferidos em 15/09; dois defeitos
  pré-existentes abertos.** Inserir e contar saem da mesma relação; o aviso tem
  contraprova no carregador; `sem_antecedente` é estado próprio (**139.435
  grupos**, boa parte por deriva de descrição — contado, não curado).
  Simulação independente em memória reproduziu **382.454 criados / 7.733
  recusados / 139.435 sem antecedente**, sem reconstruir o painel. **N3: a
  derivação é não determinística em 141 grupos de 7 companhias**, onde a troca
  de exercício social põe dois períodos sob o mesmo rótulo — resolver antes de
  reconstruir. O painel ainda carrega 7.734 derivados longos em **513**
  companhias. Reconstrução não decidida; períodos curtos pendentes.
- **Rank 3-B — QW3–QW7 conferidos em 15/09; H1.4 completado em 16/09.** G1
  reconfere pela linhagem e para a cadeia; q1 vem das **datas** da linha — o
  rótulo civil sobre painel fiscal aceitava **322 observações reais** com
  trimestre já iniciado (N1; depois da correção: 278 reancoradas, 65
  censuradas segundo a implementação; conferência atual: **10.605 observações,
  494 companhias, G1 com zero violações**). Completude exige métricas e IC das três
  métricas; piso de observações por componente; a CLI sai com 2 e compõe a tela
  antes de gravar. Alvo não avaliado; pré-registro `fbae30cc…` consumido;
  previsão sobre `fco_ttm_sobre_sd8` sem teste.
  **Em 16/09 o JSON deixou de ser byte-idêntico, por decisão declarada:**
  `a2ef88be…` → `8f7316ad…`, porque o artefato passou a publicar G0.0 e G0.4.
  Veredito, `primeiro_reprovado`, `g0_3_fracao` (0,005874), os 132 saltos e os
  inventários de G0.1–G0.3 foram conferidos **idênticos** campo a campo sobre os
  bytes publicados. A linhagem do ativo agora tem os quatro campos de H1.4, com
  `dt_ini` nulo — e normalizar o `NaT` do pandas para `None` foi necessário:
  `NaT is None` é falso e toda comparação com ele devolve falso.
- **Rank 3-B — GEOM-1, piloto e extensão documental concluídos (18/09).**
  `resultados/escala_geometrica_rank03b_2026-09-18.md` e evidências em
  `artefatos/escala_geometrica_rank03b_2026-09-18/`. Regra nova separada da v4,
  com vínculo geométrico de unidade/conta/perímetro/data/coluna e consumidor
  por replay da fonte pinada. Seleção por hash e quatro estratos, antes da
  leitura; emissor de desenho não aparece na verificação. Piloto reservado:
  uma aceitação, conferida independentemente no PDF/XML original; confirma
  MIL já declarada, **não valida correção de escala nem precisão geral**.
  Verificação não pode ser reaberta para ajustar a regra. Defeitos de unidade,
  coordenadas e guarda de caminho absoluto corrigidos/conferidos antes dela.
  **Nenhuma correção promovida; sete arquivos protegidos intactos; G0 vigente
  permanece reprovado.** Extensão aos 405 concluída, apenas evidências
  candidatas; duas divergências de escala de caixa conferidas na fonte, ambas
  na mesma companhia e uma já do desenho. Isso **não autoriza extrapolar para
  outras contas/DFC**. Sem herança S5, CSV, painel, gates ou alvo real.
  **Alcance conferido em 24/09:** somente Ativo Total/140867 ganhou prova
  direta adicional (PDF p42, nota 30.2, total consolidado em nota de
  segmentos). FCO dos dois períodos e Ativo/142900: **busca numérica exata sem
  correspondência nas notas 193/412** (revisão da mesma noite; antes,
  "igualdade não executada") — não é ausência em outra fonte.
  `resultados/alcance_geom1_rank03b_2026-09-24.md` (com ressalva da revisão) e
  `artefatos/alcance_geom1_rank03b_2026-09-24/` (`revisao/` tem pin, busca e o
  código que gerou o inventário publicado).
  **Revisão de 24/09** (`resultados/contratos_revisao_alcance_geom1_rank03b_2026-09-24.md`):
  a correção só do ativo foi **RETIRADA** do próximo passo — não reduz o G0.3
  (o salto só muda de lugar) e deixaria G0.3 (só ativo) e G0.5 (veredito por
  documento) cegos ao FCO. Máscara do inventário agora por classe Unicode e
  sem trecho em linha de fluxo; o inventário publicado não vazou nada e não
  foi regravado. **§12-bis do v2 (prova de saldo corrige o FCO do mesmo
  documento?) decidido em 26/09: B, não** (item −3 do próximo passo).
  Consumidor, construtor, CSV, painéis e gates não foram alterados. Qualquer
  rota de prova do FCO (anexo do grupo 192, ou identidade interna da DFC, que
  o adendo O1 de 26/09 permite com saída booleana) exige contrato próprio.
  Executor v2 pendente. Não treinar.
  **Auditoria da revisão (25/09): 1 ALTA, 1 MÉDIA, 4 BAIXA**, corrigidos sob
  `resultados/adendo_revisao_alcance_geom1_rank03b_2026-09-25.md`, menos o B4
  (o consumidor não confere o cabeçalho do manifesto), que fica como
  pré-condição do contrato que criar correção por conta. Execuções de 24/09
  preservadas; reconferência dos publicados sob as regras novas sem vazamento
  e com texto legível (`revisao/reconferencia_pos_auditoria.json`). A
  reconferência do auditor então fechou A1–B3 e achou só o N1 (hashes não
  registrados), corrigido e reconferido naquele parecer, com B4 declarado.
  **Conferência independente posterior (25/09): aprovação parcial, não
  fechamento integral.** Parecer:
  `resultados/conferencia_revisao_alcance_geom1_rank03b_2026-09-25.md`.
  Três defeitos P2 reproduzidos em sintético: **RAG-01**, reconferência aceita
  pin de fontes vazio e de hash diferente; **RAG-02**, busca exata casa
  prefixo de número malformado ou perde sinal; **RAG-03**, autoverificação
  aceita valores equivalentes com zeros decimais extras. **RAG-04 (P3):**
  resíduo de "cinco decisões" no bloco CRF, descrito no parecer.
  Resultados reais reproduzidos, sete protegidos íntegros e suíte 3.111
  passando sem override do modo. Nenhum erro monetário/vazamento real
  demonstrado. Evidências: `artefatos/conferencia_revisao_alcance_geom1_rank03b_2026-09-25/`.
  **Correção RAG (25/09):** contrato
  `resultados/contratos_correcao_rag_alcance_geom1_rank03b_2026-09-25.md`,
  adendo `resultados/adendo_correcao_rag_alcance_geom1_rank03b_2026-09-25.md`,
  relatório `resultados/correcao_rag_alcance_geom1_rank03b_2026-09-25.md`,
  evidência em `artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/`.
  Toda entrada das duas funções conferida por hash antes do uso (inclusive
  `pin_execucao.json` e `selecao.json`, também lidos sem conferência);
  universo e versão = pin; pacote lido uma vez. Token inteiro; sinal só nas
  formas explícitas, e o resto é ambíguo, publicado à parte. O que nega ou
  afirma é definido por categoria e NFKC. Invisível e sinal depois do token
  viram recusa. Autoverificação por equivalência numérica, sem lista de
  separadores; isenção pela forma. Nada é gravado antes das recusas. Limite da
  forma ÷1.000 declarado: ela não testa "XML em reais, notas em milhares".
  A primeira conferência da correção **reabriu** (2 MÉDIA, 5 BAIXA); o
  adendo tratou os sete achados. Mutação: 45 de 45 mortas. As contraprovas da
  conferência não reproduzem, e a busca repetida (não cega) dá o mesmo
  resultado de 24/09. Adendos 2 e 3 (26/09) fecharam as ressalvas daquela
  onda; mutação com 52 de 52 mortas. **Pendências corrigidas em 26/09:**
  marcas/preenchedores e `R $` agora geram ambiguidade/recusa integral; B4
  exige esquema CSV fechado e sintaxe válida antes de carregar correções.
  Primeira revisão independente encontrou falsa recusa em `TOTAL R$` e aspa
  solta aceita pelo CSV; ambas corrigidas sob adendo e **reconferidas como
  fechadas**. Limite residual: `PL R$` pode ser ambíguo; não há garantia
  universal de Unicode/OCR nem validação em outros emissores.
  Ativo arredondado ganhou contrato e função **só sintética, desconectada da
  busca real**, sem adjudicar escala. O1 original não autoriza explicitamente
  piso/teto do FCO; a exceção exclusivamente protetiva foi **aprovada em
  26/09, por delegação** (`resultados/adendo_o1_rank03b_2026-09-26.md`).
  Detector preservado, nenhuma busca/reconferência com FCO real nesta onda.
  Busca arredondada de FCO e executor v2 permanecem pendentes (as seis
  decisões foram tomadas em 26/09); não treinar. Contrato/relatório:
  `resultados/contratos_pendencias_geom1_rank03b_2026-09-26.md`,
  `resultados/adendo_pendencias_geom1_rank03b_2026-09-26.md`,
  `resultados/correcao_pendencias_geom1_rank03b_2026-09-26.md`;
  passagem e decisões em `resultados/decisoes_executor_v2_rank03b_2026-09-26.md`.
  Evidências em `artefatos/pendencias_geom1_rank03b_2026-09-26/`.
- **Rank 3-B — CRF-01/02/03 CORRIGIDAS E CONFERIDAS; G0 REPROVADO (18/09).
  NÃO CONGELAR NEM TREINAR.**
  Contratos: `resultados/contratos_correcao_crf01_crf03_rank03b_2026-09-17.md`
  e adendo `resultados/adendo_contratos_crf_2026-09-18.md`. V4 estrita para
  saldos implementada; v3 preservada explicitamente. Cobertura integral de
  provas no G1 implementada. Execução 3 preservada em `adjudicacao/execucao3/`.
  Readjudicação 4b: **405/405 indecidíveis**, zero cabeçalhos tabulares
  elegíveis reconhecidos, **zero correções** (antes: 68). Isso mede a falta
  de cobertura do extrator estrito; **não prova 68 correções erradas**, nem
  ausência da informação nos PDFs. S5 sem trechos testáveis, herança barrada.
  CSV anterior recuperável no snapshot; nenhuma declaração bruta apagada.
  Painel/gates/verificações regenerados: digest **`6ca635a9…`**, manifesto
  **`13520e61…`**. **G0.3 = 132 saltos (0,5875% > 0,5%)**; G1 diagnóstico
  aprovado (10.748 observações / 502 companhias, G1.4 zero). G0.5 proposto:
  **82/22.088 = 0,3712%**, sem força de gate. Suíte final: **2.615**, zero
  falhas/erros/skips. Painéis compartilhados e manifesto de aquisição intactos.
  Relatório: `resultados/correcao_crf01_crf03_rank03b_2026-09-18.md`;
  evidências/reproduções: `artefatos/correcao_crf_rank03b_2026-09-17/`.
  Auditor independente encontrou sinal oposto antes da unicidade, escopo e
  traço corrente no consumidor; corrigidos com contraprovas, instrumento
  reconferido. Conferência final independente: sem achado remanescente no
  escopo CRF; hashes/vínculos conferem, mesmas 405 decisões e zero diferenças
  nas três tabelas reconstruídas. O auditor conferiu registros e código da
  reconstrução/readjudicação, sem repetir essas execuções integrais nem
  adjudicar a verdade contábil. Parecer em `auditoria_final.json` na pasta
  da onda. A cobertura operacional continua insuficiente.
  CRF-03 separa medições históricas da vigente e corrige a descrição de D;
  as cinco decisões pendentes eram as de 18/09 — desde 24/09 são seis, com o
  §12-bis do v2. Nenhum alvo real/T1/T2/baseline/treino.
  **Registro da revisão anterior (achados tratados acima):**
  Parecer: `resultados/conferencia_rf01_rf08_rank03b_2026-09-17.md`;
  evidências e reproduções: `artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/`.
  Reconstrução em memória idêntica às três tabelas persistidas; G0/G1
  reproduzidos, 2.544 testes passando, antiga ESC-0101 corrigida. **Achados
  de então — CRF-01 (P2):** prova então vigente de ESC-0029 casa variação cambial de investimento
  com conta de caixa; uma contraprova sintética usa o valor de outra conta na
  mesma linha. **Não foi provado novo erro monetário real. CRF-02 (P2):** mapa
  parcial de provas permite aprovação indevida de G1/c3 em contraprova; o mapa
  completo da execução canônica confere, **sem vazamento real demonstrado**.
  **CRF-03 (P3):** prosa ainda mistura execuções e descreve mal a grade de D.
  Não congelar v2: fechar os achados, decidir os cinco pontos e implementar/
  testar o executor v2 cego. Nenhum alvo real ou treino nesta conferência;
  hashes de código operacional, manifesto, painéis e pré-registro preservados.
  **Registro da implementação RF revisada (execução 3, substituída pela CRF acima):**
  Contratos `resultados/contratos_correcao_rf01_rf08_rank03b_2026-09-17.md`,
  relatório `resultados/correcao_rf01_rf08_rank03b_2026-09-17.md`. Regra de
  escala v3 (evidência numérica localizada) reexecutada offline: **101 → 68
  correções** (manifesto `6330d78d…`), nenhuma escala invertida, ESC-0101 fora.
  Disponibilidade exige a publicação da prova da escala (pontas da herança) e
  G1.4 confere isso independentemente (reproduz as 5 observações do parecer no
  manifesto antigo). Painel novo `1250cefb…`: **G0 e G1 aprovados**, G0.3 = 68
  saltos (0,3026%), G1 = 10.750 obs / 503 cias. T1 com partição corrigida,
  AUC zero em T2, B0 `sempre_nao_consumir` com IC, correções só validadas.
  Execução 2 preservada em `adjudicacao/execucao2/`. **Suíte: 2.544, zero skip.** Auditoria de conformidade da onda: sem ALTA; M1–M3 e B1–B4/B6–B8 corrigidos; B5 (buracos residuais da v3) declarado para uma v4.
  Nenhum T1/T2/baseline real, nenhum rótulo, nada nos painéis compartilhados.
- **Rank 3-B — CONFERÊNCIA DE 17/09 (registro, parcialmente superado acima).**
  Parecer: `resultados/conferencia_pre_treino_rank03b_2026-09-17.md`;
  reproduções: `artefatos/revisao_pre_treino_rank03b_2026-09-17/`.
  A reconstrução **em memória** reproduziu o painel e a saída de aprovação
  G0/G1 de 16/09, mas **não certifica sua validade**: ESC-0101 introduz erro
  de 1.000× no ativo, a disponibilidade ignora provas futuras das 24 correções
  herdadas (cinco observações elegíveis afetadas), e o algoritmo de quintis
  fabrica grupos unitários depois de empates grandes. Também há lacuna no
  G0.5 proposto, contratos estatísticos incompletos e vínculo de hash
  desatualizado. **375 testes focados e 2.495 da suíte passaram**, sem fechar
  essas contraprovas. Próximo passo: contratos de correção RF01–RF08 do parecer,
  implementação e nova conferência; não basta aprovar os três [DECIDIR].
  Nenhum código operacional, CSV ou painel foi alterado nesta revisão;
  nenhum alvo real, T1/T2 ou baseline foi medido e nenhum modelo foi treinado.
  **Registro da entrega de 16/09, parcialmente contestado acima:**
  Decisões do Ygor: painel separado (`cvm.duckdb`/`cvm_treino.duckdb` e etapa 10
  intocados), download público da CVM com piloto antes, parar no pré-registro.
  `artefatos/painel_pesquisa_rank03b/` (binários fora do Git, 2,8 GB): lê os 31
  ZIPs pinados; período por **datas** (N3 dissolvido, 0 colisões); método fora
  da identidade (60 dos 131 N2 do recorte eram troca de método); disponibilidade
  conservadora pela versão numérica (3.082 trimestres com intervalo cego — perda,
  não vazamento). Escala adjudicada **com fonte** — cabeçalho de milhares nas
  notas explicativas (grupos 193/412) **e** números do formulário impressos nelas
  — em 405 documentos: **101 correções `UNIDADE → MIL` em 32 companhias**.
  **"Em reais" declara moeda, não escala**: a primeira execução da adjudicação
  foi descartada por isso (ressalvas RC1/RC1-bis, antes de qualquer G0 com
  correções). Resultado: **G0.3 = 47 saltos (0,2092%)**, G1 = **10.750 obs em 502
  companhias**, zero violações; digest `f9cb9da9…` (manifesto de correções
  `4735fb10…`), reprodutível. Com a execução
  descartada, também aprovaria (61 saltos). **Auditoria de conformidade feita
  (16/09)**: nenhuma decisão de escala nem veredito mudou; corrigidos o G1 que
  calculava `y` em memória (A1), o consumidor que não validava o manifesto
  (M1/M2), manifesto de painel compartilhado entre as duas variantes, e textos.
  Ressalvas RA7 (lote B) e RC2 (lote C). **G0.1 lido literalmente reprova**
  (117 trimestres derivados entre métodos) — leitura vai a decisão no v2. Limite declarado: a regra quase não
  detecta "rotulado `MIL`, na verdade em reais"; 4 dos 47 saltos foram criados
  pela correção parcial. Dois formatos de fonte na CVM (formulário `.itr`/`.dfp`
  até 2021 e XML único depois); o PDF renderizado vem cortado em 8 MiB.
- **PLANO DE CONTAS — anotação dimensional por IA realizada em 15/09, não
  mapa operacional validado.** CSV atual `fa271cd3…`, 300 linhas, 20 colunas.
  Onze campos originais preservados; nove colunas novas separam classe,
  dimensão, status, escopo, fundamento, fonte, evidência contextual e autoria/data.
  **284 descrições/contextos monetários, 7 por ação, 9 inconclusivos** (`0`/`-`).
  `classe_confirmada` continua vazia: anotação restrita à declaração identificada
  não autoriza decisão sobre a chave agregada entre planos. As duas provisões
  para reestruturação receberam anotação monetária, sem apagar a proposta
  original `INDEFINIDA`. Procedência e critérios em
  `resultados/anotacao_classes_monetarias_2026-09-15.md`; snapshot semântico e
  300 contextos em `artefatos/curadoria_plano_contas/2026-09-15/`.
  **32 testes focados passaram.** Auditor separado aprovou o desenho; a
  conferência final dele foi interrompida por limite de uso, não concluída.
  O revisor principal verificou os artefatos, sem alegar validação humana.
  O esqueleto original exclui só
  documentos com declaração adjudicada, identificados com `conjunto`; inventário
  ausente ou de esquema anterior **falha**; e desde 16/09 estado fora do
  vocabulário fechado de E1.2 **levanta** em vez de virar "não adjudica" em
  silêncio (**CQW-01**, fechado; não havia ocorrência no inventário atual, e a
  exclusão segue em 111 documentos / 35 companhias). Os 92,892% são do universo do
  gerador (arquivados fora dos 111 documentos), não cobertura semântica.
  Curadoria pode continuar; não autoriza reescala.
- **`cad_cia_aberta.csv` nunca foi baixado**, ao contrário do que o antigo §3.7
  sugeria. Por isso `companhias.setor` está preenchido em **5 de 741** e **não
  há controle setorial possível** hoje. Para separar financeiras, o critério que
  funciona é estrutural: `plano_contas LIKE 'll3_09_%'` (os 36 filers desse
  plano são todos financeiros; o plano principal, com 688 companhias, não tem
  nenhum). Como **exclusão**, sobrevive à retratação do `is_banco`.
- Última etapa concluída: **10 (modelo preditivo)**, 2026-08-23 — o **único
  modelo treinado** do projeto. Depois dela só houve trabalho de dado/corpus e
  validações **negativas** — nenhuma etapa nova do plano andou.

  > **Duas advertências de leitura, que valem mais que o AUC.** Vieram de quatro
  > rodadas de revisão que retrataram três achados da primeira, e estavam
  > enterradas numa célula da tabela do plano até 2026-09-11.
  >
  > 1. **A manchete publicável é +0,019 sobre `taxa_prejuizos_4t` crua e +0,073
  >    sobre a identidade implementável** — não os +0,11 sobre a persistência
  >    binária que a primeira versão anunciou.
  > 2. **AUC intra-companhia 0,663 contra 0,865 agregado.** O modelo ordena
  >    **QUAIS** companhias, não **QUANDO** elas viram; 97,1% do decil superior
  >    já está em prejuízo. Ler o 0,865 como "prevê a virada" é o erro que o
  >    número convida.
  >
  > Números completos e as três retratações: `resultados/modelo_preditivo_2026-08-23.md`,
  > `revisoes_modelo_2026-08-23.md`, `robustez_modelo_2026-08-24.md`,
  > `debate_modelo_2026-08-25.md`. O que foi medido e **descartado** (SMOTE,
  > ajuste, recalibração, controle setorial): `becos_sem_saida.md` §A.2–A.4.
- Rodada congelada vigente: fingerprint **`c3a03ff7`** (2026-09-15), status
  **`auditoria_manual_pendente`**. O README ainda publica a anterior
  (`5b9b142d`, 08-23) e os dois conjuntos de números divergem — ver a
  pendência de publicação na seção "Interface" acima.
- Suíte atual: **4.567 casos passando, zero falhas/erros/skips**, 28 avisos
  (06/10, código do CAND-02-P v3, pelo próprio `.venv`).
  Antes: 4.480 (28/09, depois das emendas AF1–AF3 do Rank 3-B). A contagem de 26/09
  (4.184) tem XML em
  `artefatos/pendencias_geom1_rank03b_2026-09-26/pytest_suite_pos_auditoria.xml`.
  Testes dirigidos: 1.179; os dois achados da auditoria independente foram
  corrigidos e reconferidos, sem executar busca real/gates/treino de Rank 3-B.
  Antes: **4.019** na correção RAG
  com adendo 3 (a busca tinha 970 testes, contra 62 antes da onda), XML em
  `artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/adendo3/pytest_suite.xml`.
  Antes: 4.016 no adendo 2, 3.976 no adendo, 3.297 na primeira execução da correção e 3.111 na conferência
  independente de 2026-09-25, sem alterar testes ou sobrescrever o modo: XML em
  `artefatos/conferencia_revisao_alcance_geom1_rank03b_2026-09-25/pytest_suite.xml`.
  A execução anterior do fechamento da revisão GEOM-1 está no XML
  `artefatos/alcance_geom1_rank03b_2026-09-24/revisao/pytest_suite_final.xml`.
  +3 do N1 sobre **3.108** (`revisao/pytest_suite_pos_auditoria.xml`), que
  somaram +104 contraprovas do adendo (79 do inventário, 25 da busca; uma substituição
  declarada no docstring) sobre **3.004** (24/09, revisão: +90, 56 da máscara e
  34 da busca, `revisao/pytest_suite_sem_override.xml`). **Roda com o `.env`
  local, sem sobrescrever variável:** o teste de interface que pressupunha modo
  cacheado passou a fixar `HABILITAR_PERGUNTAS_LIVRES=0` no próprio processo
  (R6, declarado no docstring, nenhuma asserção mudou). Antes: **2.914**
  (24/09, alcance GEOM-1, só com a variável sobrescrita no processo; a
  primeira execução, 2.906/2.907, herdou o `.env` e está preservada). Alcance
  GEOM acrescentou 20 testes; há também adições paralelas desde a contagem
  anterior, não atribuir todas a esta onda. **Contagem anterior: 2.860** (2026-09-20, rota do
  plano ligada à interface). São 75 casos novos sobre os 2.785 da rodada
  anterior do mesmo dia (55 em `test_plano_consulta.py` + 20 em
  `test_rota_plano_interface.py`); uma asserção foi **substituída e declarada**
  no docstring (`test_sem_trimestre_nao_monta_sql` troca
  `test_sem_trimestre_nao_filtra_periodo`, porque o contrato do período mudou).
  Antes: **2.727** (2026-09-18,
  piloto e extensão GEOM-1; XML em `artefatos/escala_geometrica_rank03b_2026-09-18/pytest_extensao_final.xml`).
  Eram 112 casos novos em relação aos 2.615 após CRF, que acrescentou
  71 casos aos **2.544** de 17/09 (correções RF-01..RF-08);
  execuções focadas não se somam à suíte. Eram 2.495 em 16/09, depois da auditoria
  e da verificação dos lotes B/C. Antes da auditoria: **2.456** (depois dos lotes B/C
  do Rank 3-B: +226 contraprovas em `test_fonte_zip_cvm`, `test_fonte_rad_cvm`,
  `test_piloto_fonte_rad_rank03b`, `test_painel_pesquisa_rank03b`,
  `test_gates_painel_pesquisa_rank03b` e `test_adjudicar_escala_rank03b`; os
  testes de rede usam dublês e proíbem processo real). Antes: **2.230** (onda CQW; +28
  contraprovas sobre os 2.202 medidos antes dela). **Número medido, não
  composto:** a árvore tem três frentes não commitadas misturadas — QW/CQW,
  interface/rota e roteamento adversarial (`test_roteamento_adversarial*`, 51
  casos) — e a soma por onda **não fecha**: ~18 casos não são atribuíveis sem a
  coleta por arquivo de cada revisor. Separar antes de qualquer commit.
  Histórico: **2.139** em 2026-09-15. Composição de então: 2.093 da
  véspera + 7 da onda da interface (38 no `test_rota_estruturada.py`) + 39
  atribuídos **por diferença** a edições feitas FORA daquela sessão entre
  06:46 e 07:08 de 15/09 — `src/dados_estruturados.py`,
  `scripts/inventariar_escala_cvm.py`, `scripts/esqueleto_plano_padrao.py`,
  `scripts/auditar_rank03b_consumo_operacional.py` e seus testes. Nada disso
  está commitado e as duas ondas estão **misturadas na mesma árvore**: separar
  antes de qualquer commit. `src/dados_estruturados.py` não entra no
  fingerprint do congelado. Composição herdada: 45 do Rank 3-B em
  `test_rank03b_consumo_operacional.py` + 126 do piloto/extensão em
  `test_piloto_bancos_dfc.py` + 53 do auditor de prontidão em
  `test_prontidao_b_dfc_01j.py` + 10 da sensibilidade). 1.938 → 1.953 foram as
  contraprovas da revisão independente; 1.953 → 1.973, as dos contratos C1–C6;
  1.973 → 1.985, as de R-C5/R-C6/R-SUPORTE (28 warnings, 108,41 s).
  Conferência independente do Rank 3-B, concluída em 12/09: **2.010 passed,
  30 warnings, zero skips, 118,66 s**, sem alteração de testes pelo revisor.
  Exige dependências de modelo/local. No sandbox, usar `CREWAI_STORAGE_DIR`
  em diretório temporário gravável; o SQLite padrão fora do workspace causou
  falhas ambientais, resolvidas sem alteração de testes. Comando no relatório.
- **Quatro corpora, separados por contrato — ler §3.15 antes de tocar em
  qualquer manifesto.** Misturá-los quebra `hash_corpus`/`hash_cache_ocr`
  (RNF09) e invalida a rodada congelada. Já aconteceu uma vez.

  | Corpus | Docs | Emissores | Papel |
  |---|---:|---:|---|
  | `principal` | 20 | 5 | **o produto**; identidade do índice |
  | `expansao` | 24 | 7 | material de teste |
  | `holdout_2T2026` | 12 | 12 | **fora da amostra** — ver aviso abaixo |
  | `ifrs` | 15 | 3 | demonstrações completas (evidência G4) |

- **O holdout é holdout.** O 2T2026 é o único dado que nenhum ajuste deste
  projeto viu. Usá-lo para iterar destrói a única coisa que ele tem. Ele só se
  gasta uma vez, numa medição confirmatória pré-registrada.
- Orçamento: **OCR ≈ USD 1,5 restantes**, por estimativa, não conferido no painel
  da Mistral. Em 06/10 o responsável liberou USD 10, e o v3 do CAND-02-P gastou
  ~9,45; sobravam ~0,98 dos USD 5 do v2. O teto do `.env` continua USD 8; o v3
  o elevou só na própria execução, por variável de ambiente. · LLM USD 2,87 de
  um teto de 25 (RNF03).
- **`.venv` consertado em 06/10, depois de quebrar com a atualização do
  sistema.** O `/usr/bin/python3` passou a 3.14 e o 3.12 foi removido; o
  `.venv` (criado com o 3.12.3 do sistema) deixou de achar os próprios pacotes
  (`No module named pytest`). Reapontado, sem reinstalar nada, para o 3.12.13 do
  `uv` (`~/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu`): o symlink
  `.venv/bin/python3` e o `pyvenv.cfg`. Mesmos pacotes (sklearn 1.8.0, numpy
  2.5.1), suíte inteira verde pelo `.venv` (4.567). **Se esse diretório do `uv`
  for apagado, o `.venv` quebra de novo**; refazer com `uv python install 3.12`.
  O conflito de pin numpy × presidio da seção acima não foi tocado.

### Branch de trabalho

Branch **`corrige-contrato-corpus`**, não mesclada em `main`. Integração de
branch é tarefa separada; não commitar como efeito lateral da pesquisa. Em
26/09, a pedido, todo o pendente foi commitado: `bd07216` (17–26/09: Rank 3-B,
GEOM-1, interface, Etapa 1) e `0a6a838` (pendências GEOM-1, feitas pelo Codex).
Os **68 PDFs** do IPE em `artefatos/b_dfc_01j/raw/` (218 MB) seguem fora do Git
por regra do `.gitignore`: apagá-los não tem volta sem novo download.

**Limpeza de 26/09 — o que saiu do diretório e onde recuperar.** A extração
`artefatos/cvm/` (2,5 GB; o `construir_painel_cvm.py` a refaz dos ZIPs de
`corpus/cvm/`), caches e locks velhos; e as opções de logo de
`assets/branding/` (`f84e834`). Material de ML **não** saiu: os cinco
candidatos do becos §F são vivos, o Rank 3 é a origem do Rank 3-B e o C1 é
citado pelo README. **`artefatos/snapshots/` (101 MB) ficou**, com remoção
pendente de decisão do responsável: só cinco relatórios de 15–16/09 o citam, os
34 arquivos rastreados voltam por `git show 0a6a838:<caminho>`, mas as cópias de
AGENTS.md e MEMORY.md lá dentro são ignoradas pelo git e três não existem em
commit nenhum.

**Commit `9049579` (27/09, 20h37, feito pelo responsável):** toda a onda de
26–27/09, com as decisões do v2, a correção por conta, as ROTAs 1 e 2, o
executor v2 e o G0 aprovado. A mensagem ("Refactor code structure…") não
descreve o conteúdo; não foi reescrita. **Sem commit:** as correções da
auditoria final de 28/09 (emendas AF1 a AF3, pareceres versionados, estrutural
regerado e notas).

## Decisões e bloqueios em aberto

### DFC bancária: inventário do piloto — certificação de J em revisão

Estados produzidos pelo piloto depois da correção de F1, conferidos em
2026-09-11. **São classificações do programa, não identificação de J:**

| | |
|---|---:|
| Pacotes no escopo | 25 |
| Com fonte IFRS declarada | 24 |
| **J marcado como ponto** | **0** |
| **J marcado como intervalo** | **0** — era 15 com limites não demonstrados |
| J não identificado | **24** — mais um pacote sem fonte |
| **P3 (disponibilidade histórica) conferido** | **10** — Bradesco e Itaú |
| Emissores sem nenhum documento | **0** |

**O caminho que funcionou foi o catálogo IPE da CVM, não site de RI.** A central
de resultados do Itaú devolve HTTP 403; o IPE
(`dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE`) dá `Link_Download`,
`Protocolo_Entrega`, `Versao` e **`Data_Entrega`** — a data em que o documento
passou a existir publicamente. É ela que destrava P3, e vale também para
recuperar o vintage dos 20 congelados (item de custo zero mais abaixo).
**Os dois emissores publicam IFRS trimestral** — a suposição de que eram lacuna
estava errada.

**Duas armadilhas de coleta, ambas pegas e travadas com teste:**

- **Truncamento silencioso.** `HTTP 200` + `Content-disposition: …pdf` + arquivo
  começando com `%PDF-1.7` e **incompleto** (1,78 MB de 2,41 MB, sem `%%EOF`).
  O host usa `Transfer-Encoding: chunked` (não há `Content-Length`) e ignora
  `Range`: **só validação estrutural do PDF detecta**.
- **Escala.** O Itaú publica em **milhões**; os outros quatro em **milhares**.
  Tratar tudo como milhares erra por mil vezes — a troca `MIL`↔`UNIDADE` que
  invalidou a rodada A do CAND-04.

**A conclusão antiga de J pontual no Bradesco foi retirada.** A abertura de
parcelas de seguros/capitalização permite exclusões explícitas, mas não demonstra
a pureza das demais rubricas. Fechamento aritmético não certifica a semântica.

**Motivos dos 10 pacotes sem J, todos documentados:**

- **Santander:** a nota de fundos de pensão diz textualmente que o benefício
  definido é reconhecido **na própria linha** "Despesas com juros e similares",
  que o contrato exclui — e a informação é qualitativa, sem montante. Mistura
  não separável ⇒ J não identificado; estimar a exclusão é proibido.
- **BTG:** a nota 21 traz DUAS decomposições do mesmo total (por instrumento e
  por natureza), que **não são pai e filhas**. A soma das quatro linhas por
  instrumento fecha exatamente no total em 2025T1 e erra **R$ 6,5 bi** em
  2024T1 — as linhas são *resultado líquido* (embute valor justo), não juros
  por competência. **A curadoria inicial deste piloto caiu nessa armadilha e
  foi corrigida**; é o exemplo vivo de "soma fechar não prova semântica".
  Falta ainda o 2024T4: o anual está legível pelo cache de OCR, mas as rubricas
  não aparecem sob os mesmos rótulos — é curadoria, custo zero, não acesso.

**Três regras de vintage que saíram daqui e valem para qualquer trabalho
futuro:**

1. **A posse do período se decide pela data-base, não pelo rótulo.** No
   documento do 3T, trimestre isolado e acumulado de nove meses encerram os
   dois em 30/09: ambos são originais.
2. **Derivado herda a disponibilidade do operando mais tardio.** `Q4 = anual −
   9M` com os dois operandos originais é point-in-time; com um reapresentado,
   não é.
3. **Documento do período sem data de publicação não certifica nada.** Os PDFs
   do corpus `ifrs` (BB/BTG/Santander) vieram de RI e só têm data de download:
   ficam em `SEM_DATA_DE_PUBLICACAO`. Recuperá-los pelo IPE fecharia o P3 deles
   também.

**A camada estruturada da CVM não produz J**, e o motivo é RN09 pura: há **17
descrições distintas sob `3.02.01`** para os cinco bancos — de "Despesas com
Juros e Similares" a perdas de crédito e variação cambial —, além de
`3.02.02`–`3.02.04` igualmente heterogêneas. Nenhuma decompõe juros de captação
por instrumento. J vive nas notas explicativas, que só existem em PDF.
(Uma primeira versão do relatório afirmava "linha única idêntica à conta-pai";
era generalização de um emissor-trimestre e foi **retratada**.)

**O que continua NÃO sendo point-in-time:** os pacotes de BB, Santander e BTG,
cujos valores de 2024 vêm de coluna comparativa em documento de 2025
(*as-restated*) e cujos PDFs não têm data de publicação. Recuperá-los pelo IPE
resolveria — mesmo caminho já validado.

### Conferência independente de C1–C6 — aprovação parcial, achados já corrigidos

**Lista técnica vigente e reproduções:**
[conferência independente de C1–C6](resultados/conferencia_independente_c1_c6_b_dfc_01j_2026-09-11.md).
O [parecer anterior](resultados/parecer_correcao_b_dfc_01j_2026-09-11.md)
permanece como origem; suas seis entradas não reproduzem mais os defeitos.

**Confirmado:** C1 não divide empates e constante mede zero; C2 converte no
loader para reais e preserva a unidade original; C3 exige exatamente q(D);
C4 filtra disponibilidade de antecedentes e conta emissores efetivos no erro
do eleito. C5 inclui o acumulado na inspeção de linhagem e separa as contagens.
C6 põe a sensibilidade em quarentena explícita, preservando 16/60 como números
inválidos. As guardas anteriores de F1 e o veto por B3 ausente permanecem.

**As três pendências foram FECHADAS em 2026-09-11** — contratos registrados
antes do código em
`resultados/contratos_correcao_rc5_rc6_b_dfc_01j_2026-09-11.md`; implementação e
auditorias em `resultados/implementacao_rc5_rc6_b_dfc_01j_2026-09-11.md`:

- **R-C6 — fechado.** `PODER_REDESENHADO_APOS_F3 = False` entrou na conjunção de
  aprovação de G3, ao lado de `B3_EXECUTADO` e do limiar de poder: **três vetos
  independentes**. Constante de módulo, não literal embutido, para que o veto
  seja legível no artefato e a liberação futura seja uma linha declarada. G3
  ganhou `decidivel`, `clusters_suficientes` e `ressalva`, no mesmo vocabulário
  de `_poder`. Contraprova é a **matriz 2×2** de B3 × F3 com poder folgado nos
  quatro casos — inclusive o (True, True) que aprova, sem o qual um
  `aprovado: False` literal passaria nos outros três.
- **R-C5 — fechado.** G0 só certifica com `identidades_conferidas_independentes`
  presente, inteira e > 0; campo ausente é recusa, e `bool` não conta como
  contagem. **Piso deliberadamente sem cobertura mínima** — C5-B não fixou
  percentual e esta onda não o inventou; há contraprova dos dois lados
  (reprova com zero e com campo ausente, aprova com 1 entre 40 conferidas).
  No artefato real nada mudou: 24 independentes, G0 reprova pelo mesmo motivo
  de antes (`observacoes_de_J == 0`). Atenção ao ler o artefato: a lista
  `rubricas_com_conformidade_contratual_nao_demonstrada` sai **vazia** porque
  as rubricas não chegam a entrar numa população que não existe — não porque
  tenham sido absolvidas.
- **R-SUPORTE — fechado.** Suporte com menos de duas observações levanta
  `ReprovaEmAberto` com o motivo, preservando G0/G1/G2 já medidos.
  `StatisticsError` continua **fora** do `except` de `_medir`, de propósito.
  Prova independente de que é dívida anterior a C4, sem depender do snapshot
  perdido: a chamada que estourava está na linha 603 do arquivo original e a
  alteração de C4-B na 627.
- **Fora da onda, segue aberto:** reconstrução PIT, **redesenho de poder (F3)**,
  B3 econômico, adjudicação de rubricas e schema de limites ausentes. Os 198
  registros não identificados ainda exportam 0/0 e largura zero, com
  consumidores bloqueados pelo status. Também não fixada — de propósito — a
  cobertura mínima de evidência independente em G0; se um dia for, é política
  nova e precisa de pré-registro próprio.

**Última verificação desta conferência (antes da correção):** suíte **1.973
passed, 30 warnings, zero skips, 105,49 s**; 20 testes novos focados passaram
separadamente. *(Depois da correção dos três achados: **1.985 passed, 28
warnings, zero skips, 108,41 s**; snapshot durável agora em
`artefatos/b_dfc_01j/snapshots/2026-09-11-pre-rc5-rc6/` com `SHA256SUMS.txt`,
atendendo à recomendação do revisor de não deixá-lo em diretório efêmero.)* Auditor e
sensibilidade reproduziram os JSONs em memória. A função de identidades
reproduziu 51 registros: 24 conferidos/independentes, zero anuais certificados.
J elegível segue zero e G0 reprova. Scripts/testes e painéis tiveram hashes
conferidos. O snapshot temporário anterior foi comparado, incluindo diffs
completos dos seis arquivos, mas deixou de estar acessível na retomada;
limitação de rastreabilidade durável registrada no relatório.

**Pendência documental R1 — FECHADA em 2026-09-11.** Os cinco pontos receberam
aviso local de estado vigente, preservando os números antigos como
invalidados (nunca apagados): `AGENTS.md` §3.17 e linha 25 da tabela,
`becos_sem_saida.md` §C-bis, e as retratações do piloto, da extensão e do
relatório de prontidão. A distinção que faltava: **G2=1,0464 deixou mesmo de
ser produzido**, mas o **~16 continuava publicado** em `sensibilidade.json` com
selo de válido — hoje em quarentena (`decidivel: false`,
`calculo_de_poder_invalidado_por: "F3"`). Datas de modificação não certificam
não-mutação; a onda de C1–C6 usou snapshot/hashes antes e depois (R2).

Nesta conferência foram escritos somente o novo relatório e este handoff.
Houve auditor de conformidade em contexto separado, somente leitura; não é
novo debate de validação do modelo. Sem alterações de implementação, testes,
gates, painéis, PDFs ou corpus; sem API paga ou acesso ao holdout. Atualizar os
avisos de conclusão integral no relatório do implementador e no AGENTS.md
para incorporar a aprovação parcial; não apagar retratações históricas.

### Pista concreta de reabertura: movimentação de dívidas subordinadas

**Já há divulgação separada de juros e câmbio para uma família.** No Bradesco
IFRS 2022T2, nota20b p.63, juros de subordinadas **3.326.725** e câmbio
**−499.780**, em R$ mil; os juros conferem exatamente com nota27 p.79,
**acumulado semestral**, não trimestre isolado. Em 2024T1 pp.53/69 também
confere **1.563.818**. Em 2025T1 pp.53/69 há diferença de **1 em R$ mil**:
1.963.052 × 1.963.051; adjudicar, não corrigir silenciosamente ou presumir
arredondamento. Títulos emitidos de 2022T2 NÃO conciliam: 9.318.945 ×
9.489.327. URLs IPE, protocolos, hashes e comandos estão na revisão §4/§7.

Marcador da movimentação de subordinadas encontrado em **16/18 PDFs Bradesco
do manifesto da extensão**, até 2026T1. É inventário de notas, não 16 rótulos
independentes já conciliados. A pista **não separa as duas rubricas problemáticas
do J total**; permite testar um novo recorte por instrumento, não por baixo CV
ou ausência histórica de créditos.

**Próxima tarefa recomendada:** corrigir o auditor com contraprovas e fazer
piloto documental por família economicamente definida, com inventário completo,
conciliação e disponibilidade. Depois, novo protocolo de regressão com D/q(D),
M0/M1 e benchmark econômico no mesmo suporte; só então considerar treino
exploratório. A nota de movimentação deve estar disponível também a M0; não
escondê-la para fabricar contribuição da DFC. Hoje a classificação DFC tem
apenas duas linhas do BB 2025T1, não uma matriz histórica de preditores.
A meta Selic tem fonte pública SGS432, consultada mas não integrada.

**A pista documental não foi reavaliada como série supervisionada nesta
conferência.** As novas correções ainda não certificam J total nem um novo
estimando de subordinadas. Testes e resíduos vigentes estão no bloco anterior.

**Lacunas documentais anteriores permanecem:** sete documentos de 65 sem nota
extraída; “anuais” Bradesco 2019/2020 são comunicados e BB2023T2 é relatório
gerencial em inglês; demais casos envolvem tabela ilegível/embaralhada ou
rótulo de outra era. A revisão não recarregou nem certificou todas as páginas.
Coleta corrigida e OCR pago, se necessários, são trabalho separado com escopo
e orçamento próprios.

### Contrato financeiro acordado (referência do piloto)

O debate escolheu **J, juros por competência dos instrumentos de captação
definidos**, não encargo agregado, linha total de juros/similares ou g1/g1+h
do IFData. Inclusões, exclusões e hedge no relatório. Construção aditiva
exaustiva é admitida; ausência de composição não vira zero ou estimativa.

DRE/BP/DFC/notas do mesmo IFRS podem dispensar a ponte CVM ↔ prudencial BCB
no núcleo, se não usarem números BCB. IFData REST funciona, mas rubricas,
reinício semestral e vintages impedem emenda automática. Sua quebra de 2025
não comprova a mesma quebra no IFRS. O agregado permanece outra finalidade
legítima, retirado da prioridade antes de qualquer desempenho.

Contraprovas conferidas: duas linhas DFC do BB repetem deltas de balanço;
juros/similares Santander inclui pensões. M0 precisa conter diferenças de
saldos; M1 tem de superar M0 e benchmark econômico forte. Recuperação por ID
de um ZIP CVM versão 1 funcionou, mas números ainda não conferidos e demais
tentativas tiveram timeout. Não declarar vintages resolvidos.

Piloto acordado: cinco emissores × 2024T1–2025T1 e operandos necessários;
mapa, reconciliações, vintages e inventário de cobertura antes de treino.
Protocolo futuro próprio de regressão: quantis 0,1/0,5/0,9; materialidade,
calibração, poder e regras finais ainda pendentes. Nenhum limiar de 10% foi
adotado; T1/T2 anteriores não foram revogados ou declarados aprovados.

### DFC: bloqueios compartilhados e Rank 3-B interrompido em G0

**Cadastro de versões não é vintage numérico.** `documentos` tem datas/IDs,
mas `fatos_contabeis` retém a maior versão. As derivações não preservam a
linhagem completa; há períodos de seis meses rotulados trimestrais. Auditoria:
`scripts/auditar_prontidao_dfc.py` → `artefatos/dfc_viabilidade/`.
Uma fonte bruta DFC_MI/ITR/2024 também não preservou múltiplos vintages por
chave: não prometer que recarregar os mesmos CSVs resolve tudo.

O auditor antigo do Rank 3 não aplicou o filtro `DT_RECEB` do pré-registro e
filtrou lucro/ativo antes de construir o futuro, impondo saúde também em
`t+4`. A medição negativa continua histórica, **não confirmação PIT**;
não foi refeita. Procedência e plano no relatório da retomada.

**Rank 3-B: REJEITADO em 28/09** (T2 com lacuna de 0,207; T1 com 0,1555;
item −3 do próximo passo). Em 27/09 o G0 tinha aprovado sem rótulo no painel
v2, com 95 saltos. Histórico: **foi pré-registrado e executado em 11/09, mas parou em G0.** São
dois semestres futuros não sobrepostos de FCO negativo, em não financeiras
com FCO TTM positivo conhecido em D; não herda filtro de lucro positivo/porte.
A revisão de 12/09 confirmou o bloqueio e encontrou falhas no instrumento,
inclusive q(D), janelas e disponibilidade. Corrigir dado **e auditor** antes
de outro protocolo; não medir múltiplas definições para escolher a melhor.
Rótulo contábil calculável não equivale a utilidade humana validada.

### Tarefas que continuam exigindo avaliação humana

A expansão aumentou a cobertura, mas os 56 releases incluem o holdout:
**não contar o reservado como desenvolvimento** nem declarar todos os gates
fechados só por contagem. As tarefas abaixo exigem leitores independentes e
adjudicação; isso não significa que todo modelo com DFC precise de gold humano
por observação:

- **10 gabaritos** de `conjunto_padrao/conjunto_agentes.csv` com dupla leitura
  independente → destrava o McNemar da etapa 12. Página-fonte em `fonte_gabarito`.
- **Dupla leitura + adjudicação** dos três candidatos INDECIDÍVEL: CAND-02
  (§3.9), CAND-03 (§3.10), Rank 5 (§3.12). Reavaliar os demais gates de dados;
  não presumir que a expansão os resolveu.
- **Coluna nova no gabarito** com as redações de métrica aceitas por pergunta
  (regra "acrescente coluna, nunca linha"). Afrouxar o qualificador foi **recusado
  com evidência**: no Itaú 1T2026 coexistem `11.636` (controladores) e `11.875`
  (controladores + não controladores) — sem o qualificador o corretor aceitaria a
  linha errada.
- **Âncoras-sentinela** dos 36 documentos novos. `ancoras_sentinela.csv` cobre
  20/20 do `principal` e nada dos outros três corpora.

### Preços — os três destravadores do §3.8 estão todos medidos agora

O §3.8 nomeou três condições de reabertura — *"DFC, preços point-in-time, ou
documentos além dos 20"*. **Os três foram feitos** (§3.13, §3.15, §3.16). O
terceiro (FCF yield × retorno futuro, com `src/precos.py` novo e 34 testes)
rodou em 2026-09-08: G0 aprovou (4,19% de suspeita de evento corporativo,
limiar 5%), mas T1 saiu **INDECIDÍVEL** — os cinco componentes obrigatórios
passam na leitura pontual (o maior, `valor_mercado`, em 0,120 contra limiar
0,15), mas um bootstrap por companhia mostra 32% de chance de a amplitude
verdadeira exceder o limiar, porque a amostra final é pequena (1.908 obs, 19
trimestres) — `composicao_capital` da CVM só existe a partir de 2020. Um
caminho de reabertura (derivar ações de `LPA` reportado desde 2011) foi
examinado e **rejeitado**: o campo vem arredondado a 2 casas decimais e falha
justo nas companhias de LPA pequeno — mesma classe de defeito do CAND-04.
Relatório completo: `resultados/validacao_etapa19_fcf_yield_2026-09-08.md`.
Detalhe: §3.16.

**Duas restrições continuam valendo para qualquer candidato futuro:**

- **T1 permanece obrigatório nos protocolos que o exigem.** As reprovações
  anteriores não demonstram impossibilidade geral de prever caixa. O Rank
  3-B foi admitido no registro específico de becos sem saída e precisa de
  protocolo próprio, sem herdar métricas.
- **Baseline trivial antes do modelo.** Em §3.8 a linha de base venceu 205 × 1.

**Nenhum desses experimentos aprovou um novo modelo.** Isso não esgota os
usos das fontes; a retomada DFC encontrou falhas na execução do protocolo
antigo. Preservar o negativo e seus limites, sem trocar definições depois de
observar desempenho. Na etapa 19, a condição de reabertura continua sendo a
do relatório específico.

### Dois achados de 2026-09-08 ainda não fechados

- **O detector de período falha EM ABERTO na forma em prosa.**
  `PADRAO_TRIMESTRE` e `extrair_trimestres_citados` só leem a forma compacta
  (`1T26`, `2T2026`); *"1º trimestre de 2026"* devolve conjunto **vazio**. Em
  `src/geracao.py:1355` a checagem é `periodos_resposta <= set(periodos)`, e
  **∅ ⊆ qualquer coisa passa** — resposta que diz o período em prosa atravessa
  sem ser verificada. Consertar **exige medir no congelado** (225 chamadas, custo
  real): o comentário logo abaixo registra que mexer no que é "lido como período"
  já causou **recusa falsa** em 2026-08-20. Não mudar às cegas.
- **Capa de documento não é fonte confiável de período** — 3 casos medidos em 3
  emissores: Itaú release 2T2026 (capa diz "1º trimestre de 2026"), Bradesco IFRS
  1T/2T/3T2025 ("3T24") e Banco Pan 2T2025 ("30/06/2021"). Nos três o **corpo
  está correto**, e a razão de frequência separa os casos (1 ocorrência da capa
  contra 66–74 do período real). **Não editar o documento para consertar:** o
  cache de OCR é endereçado pelo hash do PDF e versionado como evidência
  (RNF10), e o padrão do projeto para fonte defeituosa é **declarar com
  procedência** (§3.3, `correcoes_contabeis.csv`), nunca mutar. O período
  autoritativo já vem do manifesto, não da página
  (`montar_cabecalho_contextual`).

### Trabalho de código que qualquer agente pode fazer, custo zero

- **Vintage dos 20 congelados de graça.** O gate G1 do Rank 5 reprova por não
  haver "data original de publicação e versão". O catálogo **IPE da CVM**
  (`dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE`) traz `Data_Entrega` e `Versao`
  por protocolo, e os 36 documentos novos já os têm no manifesto. Os 20 antigos
  vieram de sites de RI sem essa data, mas estão no IPE — é consulta, não OCR.
- **698 chaves semânticas duplicadas** (587 conflitantes) no `mapa_contas` —
  bloqueio nomeado do CAND-03.
- **Curadoria do plano de contas:** 300 chaves em
  `corpus/cvm/plano_padrao_contas.csv` já têm anotação IA contextual (284/7/9),
  sem confirmação operacional. Próximo: adjudicar os nove exemplos `0`/`-`
  e validar alcance por declaração/plano antes de consumir a classe.
  “208 contas → 85%”
  não reproduz; cobertura de códigos não é cobertura de conceitos. Ver §3.4
  da conferência de 15/09 antes de planejar o join ou a correção de escala.
  Entregar como curadoria com escopo/evidência, nunca como modelo.
- **Canonização dos emissores novos.** `APELIDOS_BANCOS` em
  `src/normalizacao.py` tem só os 5 originais + NUBANK: sem entrada ali, pergunta
  sobre BMG/Pine/Banrisul não é reconhecida. `setor`/`ticker` também saem de
  dicionário fixo dos 5 (§3.7 mostra que `cad_cia_aberta.csv` já resolve).

### Pendências externas e decisões tomadas

- **Resolução limpa com `requirements-guardrails.txt` está quebrada:**
  `numpy==2.5.1` (runtime) × `presidio-analyzer` (`numpy<2.5.0`). Tratar em onda
  própria — **não** alterar pins como efeito lateral de outra tarefa.
- **Descartado em 2026-09-08:** completar o IFRS com Itaú e Bradesco (1.274 pp,
  USD 2,55). Não é lacuna — `scripts/gate_g4.py` documenta que os dois publicam a
  ponte BRGAAP→IFRS **dentro do próprio release** e por isso ancoram o gate
  sozinhos; a peça avulsa existe para BB/BTG/Santander porque eles *não* a
  publicam. Não reabrir sem motivo novo.
- **Alvo pré-tributos:** recomendado pelos dois especialistas e **descartado por
  Ygor** (ganho é ruído, +0,0034, e invalidaria três relatórios). Caminho
  conhecido, não pendência — não reabrir sem pedido.

## Próximo passo concreto

**Levantamento até o treino, realizado em 15/09:**
`resultados/pendencias_desbloqueio_treino_dfc_2026-09-15.md` separa o caminho
Rank 3-B (D1–D8) da trilha bancária, com fontes e critérios de conclusão.
G0 rechecado somente leitura continua reprovado; nenhuma correção ou treino.
Recorte novo da simulação de derivação: no **FCO não financeiro**, N2 tem
**131 grupos/94 companhias** sem antecedente e N3 **10 grupos/6 companhias**
com mais de um período candidato. Não são exemplos finais de treino nem
erros já adjudicados. O relatório registra ainda a aprovação de G0 isolado
sobre entrada vazia e a ausência de verificação explícita de nulos antes do
filtro dos carregadores; G1 barra vazio e não há nulos nas contas requeridas
do universo atual, portanto não foi demonstrada aprovação indevida da cadeia.
Recomenda-se delimitar a curadoria a FCO/ativo e considerar painel de pesquisa
separado — **decidido em 16/09: painel separado** (ver item −1 abaixo) —, sem
transformar toda dívida do projeto em pré-requisito. O novo protocolo deverá separar autorização de treino de
aprovação por superioridade do modelo. Nenhum painel/CSV/código foi alterado
por este levantamento; não houve T1/T2, baselines ou nova auditoria externa.

−6. **CAND-02-P v3: PROMISSOR em 07/10, AGUARDANDO O RESPONSÁVEL.** Teste novo de 16
   pares (4T2021→1T2022 e 4T2022→1T2023): M 0,583 × B1 0,365 em nDCG@10
   (Δ +0,219, IC95% por emissor [+0,139; +0,301]), 8 de 8 emissores, críticos
   no top-20 29 × 17. Relatório: `resultados/piloto_cand02p_v3_2026-10-07.md`.
   **Próximo passo concreto:** o responsável rotula às cegas
   `artefatos/cand02p_v3/humana/rotulos.csv` (60 itens; `pacote.md` aponta os
   PDFs em `corpus/cand02p_v3/raw/`), sem abrir `mapa.json` nem `rotulos/`, e
   depois roda `python -m scripts.cand02p_piloto --piloto v3 avaliar-humana`
   (α ≥ 0,67 confirma). A amostra do v2 (item −5) mede o mesmo leitor; a do v3
   é a que vale para o resultado atual.
   **Limites que não saem do relatório:**
   - redline **só de texto**: v2 e v3 têm zero eventos de tabela
     (`resultados/achado_tabelas_ocr_cand02p_2026-10-07.md`, com errata no
     relatório do v2). Com tabelas é um v4: o HTML está no cache, sem novo OCR;
   - leitor único de IA, com releitura cega α 0,81 e 0,74;
   - uma leitura de teste descartada por contaminação
     (`artefatos/cand02p_v3/rotulos/descartados/LEIAME.md`).
   **Ferramenta:** `scripts/cand02p_qc.py` faz o controle de qualidade e a
   auditoria de acesso dos leitores. Procedimento de leitores: no máximo 3
   simultâneos, retomada pelo mesmo agente, pasta temporária exclusiva por
   leitor.
−5. **CAND-02-P v2: PROMISSOR em 29/09, AGUARDANDO O RESPONSÁVEL.** Com 22 pares de
   treino (OCR de 28 releases do RAD, US$ 4,02), o M venceu o B1 (nDCG@10 0,508
   × 0,342, 7 de 8 pares). Próximo passo concreto: o responsável rotula às cegas
   `artefatos/cand02p_v2/humana/rotulos.csv` (60 itens, lendo `pacote.md` e os
   PDFs de `corpus/cand02p_v2/raw/`), sem abrir `mapa.json` nem `rotulos/`;
   depois `python -m scripts.cand02p_piloto --piloto v2 avaliar-humana`
   (α ≥ 0,67 confirma). Relatório: `resultados/piloto_cand02p_v2_2026-09-29.md`.
−4. **CAND-02-P (piloto do redline com rótulo de IA) ENCERRADO EM 29/09: INVIÁVEL
   sob o julgamento do Claude.** Primeiro treino feito (M em 952 eventos), mas
   Δ nDCG@10 +0,027 sobre o B1 e vitória em só 3 de 8 pares. Leitor único por
   decisão do responsável (Emenda 1), depois de α 0,42 entre Claude e Gemini no
   treino. Relatório: `resultados/piloto_cand02p_2026-09-29.md`; código em
   `src/redline.py` e `scripts/cand02p_piloto.py`. A chave Gemini agora tem
   faturamento (antes, cota gratuita de 250 mil tokens/min barrava docs grandes).
−3. **RANK 3-B ENCERRADO EM 28/09: congelado e REJEITADO (itens 5 e 6).**
   **DECISÕES DO v2 TOMADAS EM 26/09, por delegação do responsável.** Ele
   disse: "Deixo as decisões de aprovação com você". Registro com motivos e
   alternativas em `resultados/registro_decisoes_v2_rank03b_2026-09-26.md`;
   adendo em `resultados/adendo_o1_rank03b_2026-09-26.md` (versão vigente
   `7f51ab27…414b0f`, revisada em 27/09 depois da auditoria; é o hash que a
   primeira execução fixa). O texto foi aplicado ao rascunho v2, que continua
   RASCUNHO. Auditoria da onda: APTA COM RESSALVAS; reconferência e conferência
   final: FECHADO COM RESSALVAS, com todos os ajustes aplicados (registro,
   "Auditoria da onda"). As decisões:
   - §3.2: exclui `ll3_13_%`, com falha fechada se surgir outro plano;
   - §5.1: unicidade;
   - §5.5: censura C+E em três níveis (o terceiro torna ausente
     `fco_ttm_sobre_ativo` quando ativo e TTM divergem de escala), comparando
     a escala aplicada ao FCO; G0.5 = uso zero. **No painel sem correções**, a
     perda alcança no máximo 54 companhias (da ordem de 1.683 observações);
     com correções, o teto é recalculado;
   - §6.1: uma observação por (companhia, q1), a de maior D, escolhida antes
     de janela e elegibilidade, sem reposição; ordem fixa de doze filtros;
     antes do congelamento, nada que recomponha a contagem omitida pelo O1;
   - §8.1: piso de 30 companhias com os dois rótulos e zona cinzenta de T2
     (bootstrap, 10%);
   - §12-bis: opção B, com três condições para a correção por conta;
   - O1: exceção protetiva aprovada, e identidade contábil com saída booleana
     permitida.

   Proposta v3 e orquestração em
   `resultados/proposta_preenchimento_decidir_v2_rank03b_2026-09-26.md` e
   `artefatos/preenchimento_decidir_v2_rank03b_2026-09-26/`.
   **Estado em 27/09: os passos 1 a 4 estão FEITOS; G0 aprovou sem rótulo.**
   Documento de revisão para o responsável:
   `resultados/revisao_caminho_ate_treino_rank03b_2026-09-27.md`. Contratos e
   emendas: `resultados/contratos_caminho_medicao_rank03b_2026-09-27.md`.
   1. Correção por conta: feita (parte A). Consumidor em
      `scripts/correcoes_por_conta_rank03b.py`; o painel aplica escala por conta.
   2. Rota de prova: a ROTA-1 rodou e **parou na B7**, porque a conferência
      recusou 4 correções (`60719`, unidade não demonstrada; `80868`, item 4
      ambíguo). Fica em `artefatos/rota_prova_rank03b_2026-09-27/`, sem
      manifesto. A **ROTA-2** só estreita a regra (apresentação exige objeto e
      só vale nos grupos 193/412) e rodou em
      `artefatos/rota_prova_rank03b_v2_2026-09-27/`: 42 correções do ativo, 48
      do caixa e 35 do FCO; B6 com 50 documentos e nenhuma discordância.
      Dois conferentes aprovaram 125 correções e 10 confirmações, **sem
      recusa**.
   3. Manifesto por conta: `corpus/cvm/painel_pesquisa_rank03b/correcoes_escala_por_conta.csv`,
      77 linhas, `f26ede4d…`. Painel v2: digest `fd2932e7…`. **G0.3 = 95
      saltos (0,4255%)**; G0.5 e G1 sem violação; amostra de 10.168
      observações em 495 companhias (`artefatos/executor_v2_rank03b/estrutural.json`).
      O `140867` continua pendente: conta no G0.3 e não é usado como ativo em D
      por nenhuma observação. Desde a AF3 isso é verificado em código, e uso
      reprovaria o G0.5.
   4. Executor v2: feito e conferido. A auditoria final de 28/09, sobre o
      `9049579`, deu **APTA COM RESSALVAS**. M1 e B1–B5 foram tratados antes do
      congelamento com as emendas AF1 (linha de status), AF2 (contraprova da
      folga) e AF3 (erro demonstrado pendente reprova o G0.5), mais os
      pareceres reconstruídos byte a byte e versionados. A C8 (serialização)
      veio antes de o G0 ser visto; a C9 e as AF1 a AF3, depois. Nenhuma mudou
      regra de dado.
   5. **CONGELADO em 28/09, por cópia**, por delegação expressa do responsável
      nesta data (palavras no topo do congelado):
      `resultados/pre_registro_rank03b_v2_2026-09-16.md`, SHA-256
      **`8fdbd145b614628392fc1e53433c73a552eed5d2d250f54e46ecf4592e1660b2`**.
      `codigo_de_medicao` `3de953a5…01ca`. O rascunho fica no lugar.
      Antes da cópia, a revisão do responsável (commit `c815930`, só texto):
      §1.1 (T1 aprovado não refuta o mecanismo: limiar absoluto, taxa-base
      0,053 contra 17–20% nos precedentes); `113026` mantido sem ROTA-3
      (`54783` está no mesmo caso, como confirmação); §14 aponta os
      artefatos governantes.
   6. **MEDIDO em 28/09: REJEITADO.** `artefatos/executor_v2_rank03b/medicao.json`
      (não refazer: o executor recusa sobrescrever); relatório em
      `resultados/medicao_rank03b_v2_2026-09-28.md`. O T2 decide: lacuna
      0,207, IC 0,167–0,250. O T1 reprova raspando (0,1555) por
      `trimestres_com_fco_negativo_nos_ultimos_8`, e não por `fco_ttm_sobre_sd8`,
      que ficou em 0,126 e passou. **Sem D8 e sem treino. Rank 3-B encerrado.**
      Registrado em `becos_sem_saida.md` §A.1 e no AGENTS.md §3.7. Reabre só
      como Rank 3-C, com outro estimando e pré-registro próprio.

   Achado de método que ficou aberto: o T1 do §4.4 usa limiar absoluto de
   0,15, pouco sensível em prevalência baixa (taxa-base 0,05 contra 0,17–0,20
   nos precedentes). Qualquer alvo raro futuro precisa de proposta de limiar
   relativo, escrita **antes** de medir. O §4.4 não foi mudado. A onda de 27/09
   está no `9049579`; as correções de 28/09, no `c210e00`.
−2. **GEOM-1 — alcance conferido em 24/09 e revisado (24–25/09):** caixa dos
   dois candidatos confirmado; Ativo/140867 demonstrado diretamente;
   FCO/140867, Ativo/142900 e FCO/142900 com busca numérica exata sem
   correspondência nas notas 193/412. A conferência independente de 25/09
   reabriu o instrumento (RAG-01–03), e a correção RAG do mesmo dia, com
   adendo, o refez (bloco acima). O resultado se manteve. A forma ÷1.000 não
   testa "XML em reais, notas em milhares". Instrumento **conferido e fechado em 26/09** (4 conferências;
   relatório da correção RAG), válido para estas notas. Para outros
   emissores ainda exige validação de corpus; as classes de interferência e
   `R $` foram corrigidas na onda de pendências de 26/09, conferida sob AP1/AP2.
   A forma arredondada do ativo ganhou diagnóstico sintético separado, não
   conectado à busca real. Uso protetivo de piso/teto do FCO: adendo O1
   aprovado em 26/09; busca arredondada de FCO continua sem autorização.
   **O §12-bis do v2 foi decidido em 26/09: B** (item −3). Sob B, nenhum
   documento se qualifica hoje; sob A, 140867 e 142900 se qualificariam, e o
   G0.3 iria de 132 para 130, ainda reprovado. **Correção só do ativo, por
   conta,** só com as três condições do §12-bis: esquema do manifesto fechado,
   G0.3 e G0.5 por conta e a regra 3 do §5.5 lida por conta
   (`fco_ttm_sobre_ativo` ausente onde as escalas do ativo e do FCO divergirem
   e um dos lados não tiver veredito para a própria conta; a regra vale mesmo
   sem correção). **B4 fechado em 26/09:** o consumidor já recusa coluna
   desconhecida, ausente ou duplicada e sintaxe inválida, inclusive em
   manifesto sem linhas. Isso não autoriza correção por conta. Rotas para
   provar o FCO (anexo do grupo 192 do mesmo pacote; identidade interna da
   DFC, permitida com saída booleana pelo adendo O1) exigem contrato próprio.
   Fontes e critérios em
   `resultados/alcance_geom1_rank03b_2026-09-24.md` (com a ressalva).
   Extrator permanece congelado; nenhuma promoção/herança ou novo G0.
   Conferir demais provas necessárias e suficiência de S5; integração exige
   produtor/consumidor próprios, não desligar ou falsificar a validação v4.
   Nova versão se ampliar cobertura; verificação já vista não vira teste novo.
   Não treinar.
−1. **CRF CORRIGIDA E CONFERIDA EM 18/09 — o bloqueio agora é a cobertura da prova
   de escala e a reprovação de G0, não os dois defeitos já corrigidos.**
   Relatório e evidências: `resultados/correcao_crf01_crf03_rank03b_2026-09-18.md`.
   A v4 não certificou nenhum dos 405 documentos; não treinar nem voltar às
   provas v3 sem resolver sua correspondência contábil. Contrato próprio para
   extração/adjudicação com fonte já iniciado na GEOM-1 (item −2), com controles
   de correção e cobertura. Reconstrução e gates ainda não iniciados nessa onda.
   Não baixar o limiar de G0, excluir companhias pelo efeito no gate ou chamar
   abstinência do extrator de inexistência de informação. CRF-03 é atualização
   documental, não licença para mudar a política. Os **seis** [DECIDIR] do v2
   foram decididos em 26/09 (item −3). Falta escrever e testar em sintético o
   **executor v2** (G0/G1 cegos, só então `y`), conferir, resolver o G0 com
   pins novos, congelar hash por ato explícito do responsável, medir.
   Registro anterior:
   **CONFERÊNCIA DO PRÉ-TREINO CONCLUÍDA EM 17/09 — corrigir antes de aprovar
   o v2.** Parecer e critérios de fechamento em
   `resultados/conferencia_pre_treino_rank03b_2026-09-17.md` (RF01–RF08).
   Bloqueios principais: adjudicação de escala sem contexto (ESC-0101
   comprovadamente errada), disponibilidade PIT sem a data das provas herdadas
   e quintis artificiais após empates. Fechar também o escopo do G0.5,
   explicitar os contratos estatísticos e regenerar a cadeia de procedência.
   Fazer contratos antes da correção, reavaliar as decisões produzidas pela
   mesma heurística e suas heranças, reconstruir **somente o painel de
   pesquisa** e conferir independentemente. Não generalizar uma correção
   comprovadamente errada às outras 100; não certificar as outras por silêncio.
   **Estado histórico de 16/09, substituído:** o pré-registro v2 era rascunho
   com três pontos **[DECIDIR]** (hoje são seis, acima): excluir o plano de seguros `ll3_13` (3 companhias,
   proposta: excluir); a leitura de G0.1 (proposta: unicidade; literal reprova
   com 117); e acrescentar o G0.5 (derivação com escalas não adjudicadas,
   ≤ 0,5%; mede 0,172%). **Nenhum T1, T2 ou baseline foi medido.** Mas
   **estatística de rótulo já foi vista**: taxa do evento 0,0526 → 0,0530 no
   painel compartilhado, publicada em 15/09 (QW1–QW8), e `y` calculado em
   memória até a correção A1 — declarado no §11 do v2, que o Ygor deve ler
   antes de aprovar. **Só após fechar os achados e revalidar G0/G1**, aprovar =
   remover "RASCUNHO" do título e do nome, publicar o SHA-256, e só então estender
   `scripts/gates_painel_pesquisa_rank03b.py` para T1/T2/baselines lendo o
   painel de pesquisa. A conferência independente encontrou pendências nos
   lotes B/C e no instrumento; não é aprovação integral. Contratos originais:
   `resultados/contratos_lote_b_rank03b_2026-09-16.md` e
   `resultados/contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md`;
   relatórios originais `resultados/viabilidade_dados_rank03b_lote_b_2026-09-16.md` e
   `resultados/painel_pesquisa_rank03b_lote_c_2026-09-16.md`. Lote D (primeiro
   desafiante) só depois de PRONTO PARA CHALLENGER. **Nenhum treino autorizado.**
0. **CONFERIDO COM PENDÊNCIAS: correções QW1–QW8 de 15/09.** Parecer em
   `resultados/conferencia_independente_qw1_qw8_2026-09-15.md`.
   Contrato
   antes do código em `resultados/contratos_correcao_qw1_qw8_2026-09-15.md`;
   relatório em `resultados/implementacao_qw1_qw8_2026-09-15.md`. Suíte
   **2.132**, zero skip. Rank 3-B segue `REPROVADO EM G0`; nenhum painel
   reconstruído, nenhuma célula corrigida. Três achados da própria onda:
   **N1** — horizonte civil sobre rótulo fiscal aceitava 322 observações reais
   com trimestre já iniciado (corrigido); **N2** — 139.435 grupos da derivação
   sem antecedente, boa parte por deriva de descrição (contado, não curado);
   **N3** — a derivação é **não determinística** em 141 grupos de 7 companhias
   (não corrigido; impede reconstrução reproduzível).
1. **FEITO em 2026-09-16: CQW-01, CQW-02, errata CQW-03 e G0.4.** Contrato em
   `resultados/contratos_correcao_cqw_2026-09-16.md`, relatório em
   `resultados/implementacao_cqw_2026-09-16.md`. Suíte **2.230**, zero skip.
   `auditoria.json` mudou de `a2ef88be…` para `8f7316ad…` — **quebra de hash
   declarada**, porque o artefato passou a publicar G0.0/G0.4; veredito,
   `primeiro_reprovado`, `g0_3_fracao` e os inventários de G0.1–G0.3 conferidos
   **idênticos** campo a campo. **Próximo trabalho: conferência independente
   desta onda.** A anotação IA do CSV
   **foi feita** (`fa271cd3…`, campos originais preservados, fontes/contextos
   por linha); resta validar escopo e adjudicar nove descrições inconclusivas,
   sem promover automaticamente `classe_anotada_ia` a `classe_confirmada`.
   Correção de
   escala, se vier, é **por declaração**, restrita a conta monetária confirmada
   e sem junção universal por código (RN09). Reconstrução exige antes resolver
   N3, declarar quebra de hash e medir a etapa 10. **Nenhum treino autorizado.**
   **Tarefa bancária separada:** R-C5/R-C6/R-SUPORTE já foram implementados
   pelo outro agente; falta conferir essa terceira onda independentemente.
   A revisão do Rank 3-B não a certificou. C1–C4 bancários não precisam ser
   refeitos. F3 sem redesenho, população PIT e schema dos 198 registros
   continuam dívidas declaradas.
1-bis. **FEITO em 2026-09-11: a sincronização documental R1.** Os cinco pontos
   que apresentavam estado superado agora abrem com aviso de estado vigente —
   `AGENTS.md` §3.17 e linha 25, `becos_sem_saida.md` §C-bis (o mais crítico: o
   `AGENTS.md` manda consultá-lo antes de propor investigação nova) e as
   retratações do piloto, da extensão e do relatório de prontidão. Números
   antigos preservados como **invalidados**, nunca apagados.
2. **Piloto por família econômica:** subordinadas classificadas como passivo
   IFRS, começando pelas notas localizadas nos PDFs Bradesco. Inventário completo,
   conciliação, adjudicação de 2025T1 e disponibilidade antes de contar rótulos.
   Novo estimando/protocolo se o alvo for restrito; não herdar resultados de J
   total. Só depois decidir treino exploratório e desenho M0/M1. **Nada aqui
   autoriza treino imediato, mudanças no produto ou uso do holdout 2T2026.**
   Rank 3-B continua bloqueado conforme a revisão de 12/09.
3. Quando a prioridade voltar à etapa 13, retomar auditoria humana do
   fingerprint `5b9b142d`; chamadas pagas só com opt-in explícito. Mantêm-se
   pendentes a dupla leitura do conjunto de agentes e os vintages IPE dos
   20 documentos do principal, em ondas separadas.
4. A revisão transversal da retomada de 2026-09-08 continua não executada.
   Os debates **não financeiro** e **bancário** foram concluídos; nenhum
   validou um novo modelo. A interrupção anterior dos especialistas por cota
   não bloqueou esta réplica/tréplica bancária.
