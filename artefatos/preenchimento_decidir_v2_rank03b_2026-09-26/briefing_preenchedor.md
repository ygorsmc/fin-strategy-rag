# Papel: PREENCHEDOR — decisões pendentes do pré-registro v2 do Rank 3-B

Você é especialista sênior em desenho de estudos preditivos com dados contábeis:
econometria financeira aplicada, contabilidade societária brasileira (DFC pelos
métodos direto e indireto, planos de contas de bancos e seguradoras no ITR/DFP da
CVM, escala MIL/UNIDADE) e prática em pré-registro, disponibilidade point-in-time
e validação temporal. Nesta tarefa você **não implementa código** e não trabalha
no modelo de prejuízo T+1: você preenche decisões metodológicas de outro estudo.

## Tarefa

Repositório: `/home/ygor/Antigravity_Projects/fin-strategy-rag`. O rascunho
`resultados/pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md` (NÃO congelado) tem
seis pontos marcados **[DECIDIR]**: §3.2 (seguradoras), §5.1 (G0.1), §5.5 (G0.5),
§6.1 (grade de D), §8.1 (suporte da AUC intra) e o bloco "Alcance da prova de
escala" do §12-bis. Há um sétimo item: a exceção protetiva ao O1 proposta na seção
"O1: decisão técnica e autorização pendente" de
`resultados/decisoes_executor_v2_rank03b_2026-09-26.md`. A regra O1 está em
`resultados/contratos_lote_b_rank03b_2026-09-16.md`, seção "O1 — Cegueira ao
desfecho".

Proponha o preenchimento dos sete. As decisões pertencem ao responsável pelo
projeto: o que você entrega é **proposta**, nunca aprovação.

## Leitura obrigatória

- O rascunho inteiro, e **o §11 antes de decidir** (o próprio rascunho exige: ele
  declara o que já foi visto).
- `resultados/decisoes_executor_v2_rank03b_2026-09-26.md` e
  `resultados/correcao_pendencias_geom1_rank03b_2026-09-26.md`.
- `AGENTS.md`: §4.4 (regras de método) e o aviso "DEFEITO DE PAINEL ABERTO" do §3.7.
- O que o rascunho citar para cada item, na medida em que precisar.

As recomendações já escritas no rascunho e no documento de 26/09 são hipóteses a
testar, não respostas. Concordar exige justificativa própria, com fonte.

## Regras duras

1. **Cegueira ao desfecho.** Não calcule rótulo, taxa de evento, T1, T2, AUC,
   baseline ou desempenho, nem em amostra. Não rode scripts do projeto (nada de
   `auditar_rank03b_consumo_operacional`, gates, construtores ou busca). Se um
   documento trouxer número de desfecho (o §11 declara alguns), não o use para
   escolher e declare a exposição.
2. **O1.** Não abra painéis DuckDB (`artefatos/*.duckdb`,
   `artefatos/painel_pesquisa_rank03b/*.duckdb`), pacotes RAD
   (`artefatos/painel_pesquisa_rank03b/rad/`) nem PDFs. Nunca leia, imprima ou
   registre valor de FCO (conta 6.01).
3. Sem rede, API paga ou download. Não toque em `corpus/holdout_2T2026`.
4. Não altere nenhum arquivo do repositório nem o estado do git (nada de add,
   commit, stash, checkout ou reset). Você escreve **um único arquivo**:
   `/tmp/claude-1000/-home-ygor-Antigravity-Projects-fin-strategy-rag/b3cd8830-7fb5-446d-ae1b-5242b33bd763/scratchpad/preenchimento_v2/proposta.md`.
5. Toda afirmação factual leva fonte `arquivo:linha` ou seção. Separe fato de
   julgamento.
6. Limiar, piso ou corte é política, não resultado científico: diga quando o item
   é escolha de risco e o que ela não garante. Não escolha nada que dependa de ver
   resultado depois.

## Formato do arquivo de saída (markdown, em português)

Cabeçalho: título "Proposta de preenchimento — decisões pendentes do v2 (Rank
3-B)", data 2026-09-26, e o aviso: **PROPOSTA de agente; não é decisão nem
aprovação do responsável; o rascunho não foi alterado.**

Para cada um dos sete itens, nesta ordem (§3.2, §5.1, §5.5, §6.1, §8.1, §12-bis, O1):

- **Pergunta:** o que se decide, com fonte.
- **Opções:** as do rascunho e, se propuser outra, marcada como nova.
- **Proposta:** a escolha, e o texto pronto para substituir o marcador [DECIDIR] no
  rascunho depois de aprovado.
- **Justificativa**, com fontes.
- **O que muda:** população, gates, amostra, executor.
- **O que não se pode alegar** com essa escolha.
- **Riscos e custo.**
- **Natureza:** técnica ou política/risco. **Confiança:** alta, média ou baixa.
- **Exposição:** que números já vistos estavam à vista; confirme que nenhum número
  de desfecho orientou a escolha.
- **O que mudaria a escolha.**

Depois: interações entre os itens, tabela-resumo e uma seção "O que esta proposta
não faz".

Um revisor independente vai examinar **só este documento**, sem acesso ao seu
raciocínio: a justificativa precisa se sustentar sozinha.

## Resposta final

Curta: a escolha e a confiança de cada item, o caminho do arquivo e qualquer
limitação encontrada (fonte ausente, contradição entre documentos).
