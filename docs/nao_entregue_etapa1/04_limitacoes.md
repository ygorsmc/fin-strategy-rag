# ⚠️ Limitações conhecidas

Declaradas porque escondê-las seria o oposto do que este projeto se propõe a medir.

## Do dado e do corpus

- **Corpus pequeno:** 5 bancos, 4 trimestres, 20 documentos. Conclusões sobre recall e exatidão não generalizam para qualquer documento financeiro público.
- **Contaminação por pré-treinamento:** o LLM pode ter visto estes *releases* públicos durante o próprio treinamento. É por isso que o E0 (*closed-book*) é reportado separadamente, como controle diagnóstico — e ele acerta zero, o que é a evidência de que o RAG está fazendo o trabalho.
- **Métricas gerenciais não são comparáveis entre bancos:** cada instituição define os próprios ajustes. As perguntas comparativas fixam "como divulgado em cada release" justamente por isso.
- **O 4º trimestre não existe como informação trimestral arquivada:** é derivado por subtração (anual menos acumulado do 3T) e apresentado **marcado como derivado**. Apresentá-lo como número arquivado seria mentir por omissão.

## Do método de verificação

- **Guarda mecânica não prova fidelidade semântica.** Ela prova a origem das citações e dos números: todo valor da resposta precisa aparecer nos trechos citados. Se a resposta interpretar mal um número que existe na fonte, a guarda não pega. Fidelidade qualitativa continua exigindo auditoria humana.
- **Um juiz automático tem a mesma fragilidade que está sendo testada.** Por isso a suíte automatizada é medida **contra** a auditoria humana (concordância de 0,867), não no lugar dela.
- **Temperatura 0 não garante repetição.** Entre duas rodadas com o mesmo modelo e a mesma recuperação, 15 vereditos mudaram. Qualquer número aqui descreve uma execução identificada, não uma constante.

## Da camada estruturada

- **O mapa de contas é mantido à mão**, e é a limitação com maior potencial de dano do projeto: o mesmo código de conta designa linhas diferentes conforme o plano de contas da companhia, e uma consulta ingênua devolveria número plausível, não nulo e errado. Por isso a validação do mapa é um gate bloqueante, e por isso `cd_conta` nunca é chave de significado sozinho.
- **A deferência à camada documental tem uma lacuna conhecida.** A regra que impede a consulta contábil de responder pergunta sobre o *release* foi derivada das próprias 45 perguntas congeladas. Uma paráfrase que aponte para o release sem casar com os termos previstos ainda chega ao painel — agora com uma declaração explícita de que o número é o contábil arquivado e que o gerencial não foi lido, mas a lacuna existe e está registrada.

## Do escopo desta etapa

- **As respostas pré-computadas do modo demonstração estão travadas** até a auditoria humana de fundamentação ser concluída. A tela declara esse estado em vez de exibir resultado não auditado. As consultas ao painel contábil e o modo pergunta livre funcionam normalmente.
- **A camada de observabilidade (Langfuse) não está construída.** É material da Etapa 2.
- **Os índices binários e o painel DuckDB não são versionados** — são regeneráveis por script e pinados por hash, mas quem clonar o repositório precisa reconstruí-los antes de rodar a interface.

---

# 🔭 Próximos passos

O que já está encaminhado para as etapas seguintes:

| Frente | Situação |
|---|---|
| Observabilidade com Langfuse, com *traces* por etapa | A construir (Etapa 2) |
| Suíte DeepEval formal de *faithfulness* e *answer relevancy* | O juiz automático já foi medido contra a auditoria humana; falta a suíte formal |
| Publicação em URL pública | A fazer (Etapa 3) |
| Conjunto adversarial de paráfrases para fechar a lacuna da deferência | Protocolo em execução, com pré-registro, cegamento e dupla anotação |
| Auditoria humana de fundamentação, que destrava o modo cacheado | Pendente |

---

# 📚 Onde conferir cada afirmação

Todo número deste documento tem origem rastreável no repositório:

| Afirmação | Evidência |
|---|---|
| Resultado da rodada congelada | `artefatos/logs_execucoes/execucao_20260915T011103Z-85fbfadd35.jsonl` |
| Segurança (ataques e falso bloqueio) | `resultados/guardrails.json` |
| Ensaio do roteiro de demonstração | `resultados/ensaio_roteiro_video_2026-09-18.md` e `artefatos/ensaio_video_2026-09-18/` |
| Correção do *chunk* órfão de cabeçalho | `tests/test_chunking_tabela_orfa.py` |
| Correção do falso bloqueio da guarda numérica | `tests/test_guarda_rn02_auditoria.py` |
| Deferência à camada documental | `tests/test_rota_estruturada.py` |
| Integridade do corpus | `corpus/metadados.csv`, com SHA-256 por documento |
| Identidade do índice | `artefatos/indice_vetorial/metadados_construcao.json` |
| Gate do mapa de contas | `resultados/gate_g4.md` |
