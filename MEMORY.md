# MEMORY.md

> Memória de trabalho entre sessões. Leia no início de toda tarefa; ao final,
> **sobrescreva** o que ficou desatualizado. Não é changelog — é handoff.
> Regras de uso em [AGENTS.md](AGENTS.md#10-memória-entre-sessões--memorymd).

## Estado atual

- **Marco:** o repositório foi realinhado à **revisão 3** da especificação
  (2026-08-10). O plano em `AGENTS.md` tem 18 etapas, RN01–RN12 e os gates
  G1/G2/G3/G4 — o plano antigo de 10 etapas não vale mais.
- **Suíte local: 1.302 casos passando, sem skips, sem falhas.** Verificado ao
  final da sessão de 2026-08-17 (eram 1.270 em 2026-08-16; +32 do redesenho da
  RN02, do limitador de taxa do Gemini, de `--conjunto` e da propagação de
  unidade — ver bullets abaixo).
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
  **`braco_c.json`
  continua pendente de reapuração**, mas por outro motivo: ele é determinístico
  e não depende do prompt; o que o desatualiza são as correções de
  `src/cobertura.py` (custo zero para refazer).
- **OCR completo (2026-08-11).** A passagem pela Batch API rodou: job
  `0eb6eab2`, 20/20 documentos, **2.790 páginas, zero erros, USD 5,58** (metade
  do síncrono). Cache versionado em `corpus/ocr/<hash-do-pdf>.json`, 23 MB.
  Validação: 2.790/2.790 páginas, nenhuma vazia, sentinela ok em 4 amostras.
  O desbloqueio foi ativar **Pay-As-You-Go** no console — crédito pré-pago é
  saldo, não permissão, e a Batch API recusava com HTTP 402 até então.
- A avaliação E0–E3 **nunca rodou no conjunto congelado** e o cache público
  (`respostas_cacheadas.json`) segue deliberadamente vazio. As métricas `dev` de
  2026-07-15 continuam invalidadas — `VERSAO_AVALIACAO` está em **v5**.
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
- **Gate G4: veredito REPROVADO** (`resultados/gate_g4.md`, 2026-08-11, custo
  zero). Parte A (mapa × conferência congelada) **APROVADA** — o mapa resolve o
  conceito certo nos cinco emissores e **nenhuma célula reprova por erro de
  mapeamento**. Parte B: **17/20 conferidos, 2 divergentes, 1 sem âncora**.
  **A terceira base contábil, agora com âncora dos dois lados.** A conciliação
  dos releases parte de **BRGAAP/COSIF** e o arquivo da CVM está em **IFRS**
  (CMN 4.818/2020). Itaú e Bradesco publicam a ponte no próprio release; para
  BB, BTG e Santander a âncora passou a vir das **demonstrações em IFRS
  publicadas em separado** (`corpus/ifrs/`, 15 peças com URL, data e SHA-256 em
  `manifesto_ifrs.csv`; PDFs fora do Git, lidos por `scripts/ancora_ifrs.py`,
  hash conferido antes de cada leitura). **Estas peças NUNCA entram em
  `corpus/metadados.csv`** — isso mudaria a identidade do índice (RNF09).
  **O que bloqueia:** (a) **SANTANDER 3T2025 e 4T2025 divergem de verdade**,
  ±363,754 R$ mi — ver bullet próprio abaixo; (b) **BTG 4T2025 sem âncora**: a
  demonstração anual tem 63 de 71 páginas com fonte sem mapa de caracteres
  (`pdfplumber` e `pdftotext` devolvem `(cid:N)`); ler exigiria **OCR pago** —
  decisão de orçamento, não tomada. Fallback mais fraco: o ITR/DFP em PDF.
  **Consequência para a etapa 10:** o rótulo de lucro está conferido em **17 das
  20** células, com as 3 restantes identificadas nominalmente — 2 com valor
  errado **conhecido e quantificado**, 1 não medida.
- **A divergência do Santander tem causa apurada: o erro é da CVM, não do
  painel nem do mapa** (2026-08-11). No ITR `DT_REFER=2025-09-30` (`VERSAO=1`,
  única publicada, `DT_RECEB=2025-10-29`), a conta `3.09` reproduz a
  demonstração em IFRS **ao milhar** — 9.021.926 (9M) e 3.882.410 (3T) —, mas as
  filhas não: `3.09.01` traz 8.501.317 / 3.464.450 onde a demonstração publica
  8.865.071 / 3.828.204, e `3.09.02` traz 163.700 / 61.051 onde ela publica
  156.855 / 54.206. O arquivo se contradiz sozinho (o gap de 356.909 já
  registrado abaixo). Descartadas com evidência: erro de mapa (o mesmo mapa
  fecha 2T2025 e 1T2026 do mesmo emissor ao milhar), retificadora (não há
  `VERSAO=2` para esse `DT_REFER`, embora haja para o 1T2025 — a regra de maior
  versão funciona) e troca de conceito. O 4T2025 herda o erro com **sinal
  invertido**, porque o subtraendo da derivação (RN10) é o 9M defeituoso; a DFP
  anual está correta, e por isso os dois erros **se anulam no exercício** — o
  que torna a falha invisível para quem só olha o número anual.
  **Nada foi consertado nem descartado no painel.** Decisão pendente do Ygor:
  treinar a etapa 10 excluindo essas 2 células, ou corrigi-las com procedência
  declarada. Corrigir em silêncio é o que o G4 existe para impedir.
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
  de 6. Falta ainda **reapurar o braço C** (custo zero, pendente desde a
  correção de `src/cobertura.py`) — ele não depende do prompt.
- **Por que o agente não consultava o painel: respondido em 2026-08-12.** Era
  prompt + protocolo, não o tier do modelo — `GEMINI_REASONING_EFFORT` continua
  em `low` e a taxa de consulta de dado foi de 1/15 para 12/15. Ver o bullet do
  prompt `a2` acima. Fica em aberto só o resíduo AGTC005 (recusa sem verificar
  cobertura).
- **Decidir o que fazer com SANTANDER 3T2025/4T2025 no rótulo da etapa 10**
  (excluir as 2 células ou corrigi-las com procedência declarada) e se vale
  gastar OCR pago para ler a demonstração anual do BTG e fechar a última célula
  sem âncora. As duas decisões são do Ygor; o gate já entregou a medição.
- Migrar a ingestão para consumir `corpus/ocr/` (`EXTRATOR=mistral_ocr`) e
  reconstruir o índice Chroma em namespace separado.
- Em paralelo, fazer a **dupla leitura** dos 10 valores de release marcados como
  pendentes em `conjunto_agentes.csv` (a página física de cada um está em
  `fonte_gabarito`). Sem ela, 10 das 15 seguem em `pendente_conferencia_humana`
  e a taxa de acerto dos três braços continua apoiada em 5 perguntas só.
