# Ensaio de perguntas do vídeo — 2026-09-21

Complementa `ensaio_roteiro_video_2026-09-18.md`. Mesmo método: caminho **real**
da interface (`streamlit.testing.v1.AppTest` sobre `app_streamlit.py`), não o
arnês de avaliação. **Não é métrica** (§4.2) — três perguntas escolhidas não
medem exatidão do sistema.

Motivo do ensaio: escolher as perguntas pagas do vídeo com o comportamento
**conferido**, em vez de suposto. A rota de plano (porta 3) entrou na interface
depois do ensaio de 18/09 e muda o custo de algumas perguntas.

## Condições

| | |
|---|---|
| Código | branch `corrige-contrato-corpus`, árvore local de 21/09 |
| Modo | `HABILITAR_PERGUNTAS_LIVRES=true`, `MODO_DEMONSTRACAO_CACHEADO=true` |
| Provedor | `gemini/gemini-3.5-flash-lite`, embeddings `ollama/bge-m3` |
| Chamadas pagas | **3** · custo somado das duas sessões: **US$ 0,0034** |
| Reprodução | `artefatos/ensaio_video_2026-09-21/` (`ensaio_porta4.py`, `ensaio_substituta.py`, `respostas*.json`) |

## Resultado

| # | Pergunta | Saída | Tempo | Serve ao vídeo? |
|---|---|---|---|---|
| A | Segundo o **release do Bradesco, por que** a margem financeira variou no 3T2025? | **Recusa RN02** — *"ao menos um valor numérico da resposta não aparece nos trechos citados"* | 14,7 s | ❌ não como resposta |
| B | Segundo o **release do Santander**, qual foi o resultado gerencial no **2T2019**? | **Recusa RN02** — *"não há evidência suficiente nos trechos recuperados"* | 3,4 s | ✅ como recusa |
| C | Segundo o **release do BB**, qual foi o índice de inadimplência acima de 90 dias no 3T2025? | **4,93%**, BB · `bb_release_3T2025` · pág. 12 | 13,4 s | ✅ como resposta |

Nenhuma exceção e nenhum erro de tela em nenhum passo.

## O achado que muda a escolha de pergunta

**Pergunta narrativa ("por que X variou") não serve como a resposta do vídeo.**
O caso A não falhou por defeito: o modelo respondeu e a **guarda da RN02
rebaixou**, porque um valor numérico da redação não aparecia literalmente nos
trechos citados. É a guarda funcionando — e é exatamente o comportamento que o
projeto existe para ter —, mas o resultado na tela é uma recusa.

A razão é estrutural, não deste enunciado: resposta narrativa tende a
**parafrasear número** ("cresceu cerca de 4%"), e a RN02 exige o valor como
impresso. Logo, **factual de release é o que demonstra resposta; narrativa
demonstra recusa.** Quem for montar demonstração não deve contar com narrativa
para exibir uma resposta sustentada.

O caso B confirma o previsto e é a recusa mais didática das duas: o corpus cobre
2025–2026, não existe documento de 2019, e ela recusa em **3,4 s** — a recuperação
não sustenta e o modelo não inventa. É mais rápida que uma resposta (13–15 s)
porque não há o que redigir.

## Custo de rota, depois da porta 3

Pergunta **sem** marca da camada documental e **fora** do vocabulário contábil
fechado passa pela porta 3 antes do corpus — **duas chamadas pagas e duas
unidades de cota** para uma resposta. Incluir `release` ou `gerencial` no
enunciado manda direto à porta 4 e custa **uma**. O ensaio de 18/09 é anterior à
porta 3 e não registra esse efeito.

## O que isto não prova

- Não mede exatidão. Temperatura 0 não garante repetição — o ensaio de 18/09
  registra 15 vereditos mudando entre duas rodadas com o mesmo modelo. O caso C
  foi conferido contra gabarito em 18/09 **e** reconferido aqui; os casos A e B
  não têm gabarito.
- Não cobre a porta 3, que nenhuma das três perguntas exercita.
