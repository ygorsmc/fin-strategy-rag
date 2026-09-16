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
— `semantica` teve uma repetição sem telemetria). Factual: E0 0,000 · E2 0,400
· E1 0,333 · E3 0,333 · E4 0,400. Comparativa: E4 0,400 · E1/E3 0,100 · E2
0,000. **Recall idêntico em 225/225** — a recuperação é determinística e toda
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
- **Conferência QW1–QW8 concluída em 15/09: aprovação parcial do pacote.**
  `resultados/conferencia_independente_qw1_qw8_2026-09-15.md` traz fontes,
  reproduções e critérios de fechamento. As contraprovas originais foram
  superadas; faltam **CQW-01** (consumidor aceita estado de adjudicação
  inválido como não adjudicado), **CQW-02** (H1.4: linhagem do ativo sem
  `dt_ini`/`dt_fim`) e **CQW-03** (errata: 156.100 declarações, não 154.160).
  Não foi demonstrada corrupção do inventário atual nem vazamento temporal
  da amostra atual por esses achados. Suíte da execução independente:
  **2.132 passed**, 30 warnings; recorte dos quatro arquivos: **275 passed**.
  A contagem paralela de 2.139 da interface não é a execução desta revisão.
  Só parecer e memória alterados; nenhum código/dado corrigido.
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
- **Rank 3-B — núcleo de QW3–QW7 conferido em 15/09; H1.4 parcial (CQW-02).** G1
  reconfere pela linhagem e para a cadeia; q1 vem das **datas** da linha — o
  rótulo civil sobre painel fiscal aceitava **322 observações reais** com
  trimestre já iniciado (N1; depois da correção: 278 reancoradas, 65
  censuradas segundo a implementação; conferência atual: **10.605 observações,
  494 companhias, G1 com zero violações**). Completude exige métricas e IC das três
  métricas; piso de observações por componente; a CLI sai com 2 e regrava o
  artefato byte-idêntico. JSON inalterado (**132/22.471**, só G0). Alvo não
  avaliado; pré-registro `fbae30cc…` consumido; previsão sobre
  `fco_ttm_sobre_sd8` sem teste.
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
  ausente ou de esquema anterior **falha**; estado desconhecido com campo
  presente ainda passa silenciosamente (**CQW-01**, sem ocorrência no
  inventário atual). Os 92,892% são do universo do
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
- Suíte: **2.139 casos passando, zero skip** (2026-09-15). Composição: 2.093 da
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
- Orçamento: **OCR ≈ USD 5,14 restantes de setembro** (cota mensal de USD 10 que
  **expira**, não acumula) · LLM USD 2,87 de um teto de 25 (RNF03).

### Branch de trabalho

Branch **`corrige-contrato-corpus`**, HEAD `38f6d43` ao iniciar. Não mesclar ou
commitar como efeito lateral da pesquisa; integração de branch é tarefa
separada. Pendente de commit, além do que já estava:
`scripts/piloto_bancos_dfc.py`, `scripts/auditar_prontidao_b_dfc_01j.py`,
`tests/test_piloto_bancos_dfc.py`, `tests/test_prontidao_b_dfc_01j.py`,
`artefatos/b_dfc_01j/` (os binários novos ficam fora do Git por regra no
`.gitignore`), `resultados/piloto_bancos_dfc_2026-09-09.md`,
`resultados/extensao_janela_dfc_2026-09-09.md`,
`resultados/pre_registro_b_dfc_01j_modelo_2026-09-09.md`,
`resultados/prontidao_b_dfc_01j_modelo_2026-09-09.md`,
`resultados/revisao_independente_b_dfc_01j_2026-09-10.md`,
`scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py`,
`tests/test_sensibilidade_b_dfc_01j.py`, `AGENTS.md` (§3.17),
`resultados/becos_sem_saida.md` e `MEMORY.md`. Somam-se os relatórios de
correção/verificação de 10/09, o parecer de 11/09 e a conferência
`resultados/conferencia_parecer_b_dfc_01j_2026-09-11.md`, agora revisada em
`resultados/revisao_conferencia_parecer_b_dfc_01j_2026-09-11.md`. Somam-se
os contratos e o relatório de implementação de C1–C6 e a conferência atual:
`resultados/conferencia_independente_c1_c6_b_dfc_01j_2026-09-11.md`.
Suíte completa reexecutada nesta conferência: **1.973 passed, zero skips**,
sem alteração de testes pelo revisor.
Os **68 PDFs** recuperados do IPE ficam em `artefatos/b_dfc_01j/raw/` (218 MB),
fora do Git por regra do `.gitignore`; o manifesto e os JSONL da extensão, em
`artefatos/b_dfc_01j/extensao/`, são leves e entram.

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

**Rank 3-B foi pré-registrado e executado em 11/09, mas parou em G0.** São
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
1. **Próximo trabalho: fechar CQW-01/CQW-02 e publicar errata CQW-03**, com
   contraprovas no consumidor e na linhagem. Não exige reconstrução nem
   treino; esta conferência não implementou as correções. A anotação IA do CSV
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
