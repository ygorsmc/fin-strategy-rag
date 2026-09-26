# Correção das pendências GEOM-1 / Rank 3-B

Data: 2026-09-26. **Implementação técnica parcial; não autoriza medição do
alvo, congelamento do v2 ou treino.** Contrato anterior ao código:
[P1–P5](contratos_pendencias_geom1_rank03b_2026-09-26.md), hash
`97a7d537fdb7c683b7566a2c90e6758e15656d66c58443b334b97fc6bff10068`;
[adendo AP1/AP2](adendo_pendencias_geom1_rank03b_2026-09-26.md), hash
`4c0c50f695ddfd3b2c377307f94adbb513af10dc2e0f28cbf198a48da73d38d3`.

## Resultado por pendência

| Item pedido | Entrega / estado |
|---|---|
| Sinal perdido por marcas/preenchedores e `R $` | Corrigido; ambiguidade ou recusa integral, nunca positivo presumido nos casos contratados. |
| B4 — esquema do manifesto | Corrigido no consumidor CSV, antes de validação semântica/pacotes; preservada exceção histórica explícita. |
| Ativo ÷1.000 arredondado | Contrato próprio e função diagnóstica implementada/testada **só com sintéticos**, ainda desconectada da busca real. Não adjudica escala. |
| Piso/teto do FCO no detector | Leitura estrita: O1 original não dá autorização explícita. Proposta de exceção exclusivamente protetiva aguarda decisão; detector preservado, sem execução real nesta onda. |
| Busca arredondada de FCO | Não implementada nem autorizada. Aprovar a exceção protetiva não aprova a busca. |
| Seis escolhas do v2 | Organizadas com consequências e propostas; continuam sem aprovação. |
| Executor v2 | Não implementado nesta onda: §6 manda decidir as políticas antes. Handoff detalha ordem, integrações e contraprovas necessárias. |

O [documento de decisões e passagem](decisoes_executor_v2_rank03b_2026-09-26.md)
contém o texto proposto para O1, as seis escolhas e o trabalho do executor.
Um pedido de continuar a correção não foi interpretado como aprovação dessas
decisões metodológicas.

## O que mudou no código

- `scripts/conferir_alcance_geom1_rank03b.py`: a classe de interferências
  inclui marcas Mn/Mc/Me e preenchedores definidos pelo nome Unicode, além de
  Cf/Cc não espaciais, excluídos os sinais. Dentro do número, a sequência
  inteira é recusada; no contexto de sinal, fica ambígua. Prefixo monetário
  fragmentado não recebe sinal presumido. A versão Unicode é registrada.
- O prefixo monetário considera palavras inteiras: não absorve sufixos de
  `TOTAL` e `ATIVO`. `TOTAL R$`, `ATIVO US$` e `TOTAL $` continuam válidos.
  Sequências curtas como `PL R$` ainda podem ser ambíguas; é o custo declarado
  da regra conservadora de até três letras, não análise semântica de rótulos.
- `candidatas_ativo_arredondado`: deslocamento decimal exato por três casas,
  seguido de ROUND_HALF_UP; empates se afastam de zero. Exige entrada finita,
  não nula e sinal não ambíguo; não casa resultado zero nem vizinhos. A divisão
  não sofre arredondamento intermediário por precisão do contexto. A função
  não é chamada pelo executor e não tem modo FCO/por módulo.
- `scripts/gates_painel_pesquisa_rank03b.py`: esquema fechado, inclusive sem
  linhas; rejeita colunas extras/ausentes/duplicadas e linhas longas/curtas.
  Validação lexical de aspas complementa o `csv` estrito. Parser e hash usam
  uma única leitura dos bytes; alteração posterior continua barrada.
- `AGENTS.md`: regra durável de esquema atualizada para não descrever como
  vigente o comportamento corrigido. Pré-registro, adjudicador e construtor
  não foram alterados; nenhuma correção por conta foi introduzida.

Foram substituídos explicitamente dois testes que caracterizavam o defeito
antigo de sinal e seu limite. Os originais estão preservados, não apagados.
Os testes novos ficam em `tests/test_pendencias_geom1_rank03b.py`; os testes
da busca também conferem os hashes dos dois novos contratos nas duas entradas.

## Revisão independente e testes

Pasta de evidências:
`artefatos/pendencias_geom1_rank03b_2026-09-26/`.

O auditor-conformidade trabalhou em contexto separado, somente leitura, sem
acesso solicitado a valores reais de FCO. A primeira revisão achou uma falha
MÉDIA (rótulos maiúsculos absorvidos pelo prefixo) e uma BAIXA (aspa solta no
CSV); as duas foram reproduzidas e corrigidas sob AP1/AP2. Parecer preservado
em `parecer_independente_1.md`, código examinado em `antes_auditoria/`.

- Testes dirigidos pós-correção: **1.179 aprovados**, zero falhas/erros/skips;
  `pytest_dirigido_pos_auditoria.xml`.
- Suíte completa pós-auditoria: **4.184 aprovados**, zero falhas/erros/skips,
  28 avisos, 161,89 s; `pytest_suite_pos_auditoria.xml`. Os avisos vêm de
  features sintéticas sem observação, AUC com classe única em fixtures e
  depreciação de TorchScript; não foram suprimidos.
- Reconferência independente: **AP1 e AP2 fechados**, sem regressão concreta
  encontrada; `parecer_independente_2.md`. O auditor declarou verificações
  adicionais em memória, não uma reexecução independente da suíte completa.

Histórico preservado: `pytest_dirigido.xml` (1.109), `pytest_pendencias.xml`
(97), `pytest_suite.xml` (4.114) e `pytest_suite_final.xml` (4.118).
**O nome deste último é histórico e não o torna a suíte final desta onda**:
as correções AP1/AP2 ocorreram depois. Resultados de rodadas e testes
parametrizados não são replicações independentes nem validação de ML.

## Integridade e reprodução

Os snapshots anteriores à onda estão em `antes/`. `registrar.py` lê o pin
GEOM-1 e confere por hash os sete protegidos; não consulta contas do DuckDB.
Também passa o manifesto governante vazio pelo novo consumidor, sem chamar
gates ou reconstruir o painel. O registro inicial é
`verificacao_antes_testes.json`; o final é `verificacao_depois_testes.json`.
**Sete de sete hashes conferem com o pin nos dois registros**, e o manifesto
governante de zero correções passou pelo consumidor novo. Nenhum gate foi
reexecutado para obter essa verificação.

Comandos usados para a última rodada:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q tests/test_conferir_alcance_geom1_rank03b.py tests/test_gates_painel_pesquisa_rank03b.py tests/test_pendencias_geom1_rank03b.py --junitxml=artefatos/pendencias_geom1_rank03b_2026-09-26/pytest_dirigido_pos_auditoria.xml
CREWAI_STORAGE_DIR=$(mktemp -d /tmp/rank03b_pendencias_auditoria.XXXXXX) PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --junitxml=artefatos/pendencias_geom1_rank03b_2026-09-26/pytest_suite_pos_auditoria.xml
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m artefatos.pendencias_geom1_rank03b_2026-09-26.registrar depois_testes
```

Em nova reprodução, escolher nomes novos para os XML; não sobrescrever os
desta rodada. O registrador recusa sobrescrever seus registros. Nenhuma
variável de modo público/local foi sobrescrita para fazer a suíte passar.

## Limites e estado de ML

Não foi demonstrada cobertura universal de Unicode ou OCR. A correção cobre
as classes e formas contratadas; ainda é necessária validação de corpus
antes de generalizar a outros emissores. Correspondência arredondada requer
conferência de conta, período, perímetro, unidade e regra da própria fonte;
não é prova automática de escala.

**Nenhuma busca/reconferência real com FCO, novo gate, T1/T2 ou treino do
candidato foi executado.** Os testes do módulo de modelo na suíte usam seus
controles sintéticos; não são um experimento de Rank 3-B. Não houve API paga,
download, promoção de escala, herança ou alteração de documento histórico.

O último estado governante continua sendo o do v2 §11.3: G0 reprovado,
132 saltos e zero correções v4. Isso não foi remedido nesta onda. Resolver
os itens de software não supre as provas de escala faltantes nem demonstra
viabilidade do treino.
