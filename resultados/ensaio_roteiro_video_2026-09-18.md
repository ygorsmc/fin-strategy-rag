# Ensaio do roteiro de demonstração — 2026-09-18

Ensaio do roteiro do vídeo da Etapa 1 **pelo caminho real da interface**
(`streamlit.testing.v1.AppTest` sobre `app_streamlit.py`), não pelo arnês de
avaliação. É evidência de que o roteiro funciona na tela; **não é métrica** —
duas perguntas escolhidas porque acertaram na rodada `c3a03ff7` não medem a
exatidão do sistema (§4.2).

## Condições

| | |
|---|---|
| Código | branch `corrige-contrato-corpus`, commit `de0da7f` + árvore local · `app_streamlit.py` sha256 `e8b97e407f36…` · `src/geracao.py` `5e9fd846f997…` |
| Modo | `HABILITAR_PERGUNTAS_LIVRES=true`, `MODO_DEMONSTRACAO_CACHEADO=true` |
| Provedor | `gemini/gemini-3.5-flash-lite`, estratégia `semantica`, embeddings `ollama/bge-m3` |
| Teto de chamadas | **2**, travado pela própria cota do app (`LIMITE_PERGUNTAS_LIVRES_POR_SESSAO=2`, RN03) |
| Chamadas pagas feitas | **2** · custo registrado pela sessão: **US$ 0,0027** |
| Reprodução | `artefatos/ensaio_video_2026-09-18/ensaio_video.py` · respostas integrais em `respostas.json` |

## Resultado

| # | Rota | Pergunta | Saída | Gabarito | Tempo |
|---|---|---|---|---|---|
| 1 | painel (sem LLM) | Lucro líquido do Banco do Brasil no 4T2025 | R$ 5.239.936.000,00, **marcado derivado (RN10)** com a conta explicitada | — (painel) | 1,7 s |
| 2 | painel (sem LLM) | Patrimônio líquido do Itaú no 3T2025 | R$ 224.707.000.000,00, arquivado | — (painel) | 1,3 s |
| 3 | painel (sem LLM) | Lucro do Banco Inter no 3T2025 | R$ 336.345.000,00 + declara que **não há release** (RN12 `so_painel`) | — | 1,0 s |
| 4 | painel (sem LLM) | Lucro do Nubank no 3T2025 | **Recusa classificada** (RN12 `nenhuma`), com o motivo | recusa | 0,7 s |
| 5 | guardrail | Devo comprar ações do Itaú agora? | **Recusa** citando a Res. CVM 20/2021, sem chamada externa | recusa | 0,8 s |
| 6 | RAG pago | TSTF004 — resultado recorrente gerencial do Itaú no 2T2025 | **R$ 11.508 milhões**, pág. 5 | R$ 11.508 milhões ✅ | 13,4 s |
| 7 | RAG pago | TSTF014 — inadimplência acima de 90 dias do BB no 3T2025 | **4,93%**, pág. 12 | 4,93% ✅ | 13,4 s |

Nenhuma exceção em nenhum passo.

## Defeitos de tela achados

1. **No modo demonstração, toda tela exibe um erro vermelho:** `Cache de
   demonstração inválido: ValueError: Status das métricas de teste não permite
   esta operação.` (`app_streamlit.py:1130`). É o bloqueio conhecido da etapa 13
   aparecendo como falha, quando é estado declarado. Em vídeo, lê-se como
   sistema quebrado.
2. **O painel de fontes mostra OCR cru:** marcações `![img-0.jpeg](img-0.jpeg)`,
   tabelas markdown partidas e, no Itaú, o **sumário** do release (págs. 1–5)
   como primeira fonte — recuperado, mas não citado.
3. **Valores do painel em reais com centavos** (`R$ 224.707.000.000,00`); o
   release fala em milhões/bilhões. Correto, mas difícil de ler em voz alta.
4. **13 s sem texto** antes do streaming nas perguntas RAG: o streaming começa
   só depois da validação da RN02, por desenho (ver `_fluxo_de_texto`).

## Correções aplicadas no mesmo dia (só apresentação)

Nenhuma muda resposta, recuperação ou guarda; todas vivem em `app_streamlit.py`
e estão travadas por `tests/test_apresentacao_interface.py`, com contraprovas.

| Defeito | Correção | Contraprova que trava o custo |
|---|---|---|
| 1. Erro vermelho no modo demonstração | Vira **aviso amarelo** explicando a trava da auditoria humana — só quando a mensagem é a de status **e** o status gravado é `auditoria_manual_pendente` | Fingerprint divergente, outro status ou métrica ilegível continuam erro vermelho |
| 2. OCR cru nas fontes | Remove imagem, nota LaTeX, título e células `---`; linha de tabela vira `célula · célula`. Trechos **citados na resposta** (documento + página da citação da RN01) vêm primeiro, marcados ✅ | Nenhum número do trecho se perde; mesma página de outro documento não é marcada; recusa não marca nem reordena; redação de PII continua |
| 3. Valor em reais com centavos | Texto mostra `R$ 224,71 bilhões (R$ 224.707.000.000,00)`; tabela ganha `valor_resumido` ao lado de `valor` | A coluna `valor` continua exata (teste antigo intacto) |
| extra: `$` virando LaTeX | Dois `R$` na mesma resposta seriam lidos como fórmula pelo markdown; o `$` é escapado na exibição | O gerador de streaming continua devolvendo o texto intacto |

**Substituição de asserção declarada:** `TestStreaming::test_nao_ha_streaming_de_token_cru_do_provedor`
conferia o literal `_fluxo_de_texto(msg["conteudo"])`; passou a conferir
`_fluxo_de_texto(_escapar_cifrao(msg["conteudo"]))`. A origem do fluxo segue
sendo o conteúdo validado do histórico. Motivo no docstring do caso.

Suíte completa depois das correções: **2753 verdes**. O defeito 4 (13 s de
espera) é desenho e fica para ser explicado no vídeo.

**Não re-ensaiado com chamada paga:** as correções foram conferidas na tela real
pelas rotas gratuitas (painel e aviso) e, para as fontes do RAG, aplicando a
limpeza aos trechos gravados neste ensaio.

## O que isto não prova

- Não mede exatidão: na rodada `c3a03ff7` a estratégia da demo acertou 5/15
  factuais e 1/10 comparativas. Temperatura 0 não garante repetição (15
  vereditos mudaram entre duas rodadas com o mesmo modelo), então o ensaio vale
  para esta execução.
- Não cobre pergunta qualitativa ("por que…"), que não tem gabarito medido.
