# MEMORY.md

> Handoff entre sessões. Leia no início de toda tarefa; ao final, **sobrescreva**
> o que ficou desatualizado. Não é changelog — o Git já é.
> Regras de uso em [AGENTS.md](AGENTS.md#10-memória-entre-sessões--memorymd).
>
> **Onde as coisas vivem:** o plano é o `AGENTS.md`; o histórico de investigação
> já fechada está no `AGENTS.md` §3 (com relatório datado em `resultados/`); o
> que já foi **medido e descartado** está em `resultados/becos_sem_saida.md` —
> **consultar antes de propor ideia nova**; métricas vivem em `artefatos/` e no
> README. Aqui fica só o que está **em aberto** e não se deduz do código.
> Enxugado em 2026-09-08, de 498 linhas.

## Estado atual

- **Etapa ativa (plano §7): 13 (Langfuse + DeepEval).** Concordância juiz ×
  humano medida; groundedness da rodada vigente **ainda não auditada**.
- Última etapa concluída: **10 (modelo preditivo)**, 2026-08-23. Depois dela só
  houve trabalho de dado/corpus e validações **negativas** (§3.7–§3.15) — nenhuma
  etapa nova do plano andou.
- Rodada congelada vigente: fingerprint `5b9b142d`, status
  **`auditoria_manual_pendente`**. Números publicados no README saem dela.
- Suíte: **1.784 casos, zero skip** (exige `requirements-modelo.txt` e
  `requirements-local.txt`; inclui `tests/test_precos.py`, novo em 2026-09-08).
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

### Trabalho não commitado — resolver primeiro

Branch **`corrige-contrato-corpus`, NÃO mesclado em `main`**. `main` ainda tem o
`corpus/metadados.csv` com as 24 linhas que quebram o contrato; o conserto está
no commit `51ecb52` **deste branch**. Pendente de commit em cima dele:
`corpus/holdout_2T2026/`, a fonte `holdout_2T2026` e o retry de 404 em
`scripts/ocr_batch_mistral.py`, `.gitignore` e os testes; e agora também
`src/precos.py`, `tests/test_precos.py`, `artefatos/etapa19/`, o pré-registro e
o relatório de validação da etapa 19 (§3.16). Suíte verde (1.784).

## Decisões e bloqueios em aberto

### O gargalo de ML é rótulo humano, não dado — e isso é o item mais importante daqui

Documento **deixou de ser** o bloqueio em 2026-09-08. As barras estruturais
caíram: 12 emissores (era 5) e 56 releases (era 20) cruzam os `≥10` e `≥30` que
CAND-02 e Rank 5 exigiam. O que restou depende de leitura humana, e **só o Ygor
pode fazer**:

- **10 gabaritos** de `conjunto_padrao/conjunto_agentes.csv` com dupla leitura
  independente → destrava o McNemar da etapa 12. Página-fonte em `fonte_gabarito`.
- **Dupla leitura + adjudicação** dos três candidatos INDECIDÍVEL: CAND-02
  (§3.9), CAND-03 (§3.10), Rank 5 (§3.12). Nenhum está travado por falta de dado.
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

- **T1 mata todo alvo que seja "variação de grandeza que reverte à média"** —
  três medições independentes (§3.7, §3.14). O alvo tem de ser **evento
  materialmente definido** (falência, evento legal, reapresentação), não
  movimento de série contínua.
- **Baseline trivial antes do modelo.** Em §3.8 a linha de base venceu 205 × 1.

Dizer o desconfortável ao próximo agente: **os três destravadores nomeados já
foram gastos e nenhum produziu modelo aprovado.** Reabrir exige dado
genuinamente novo (não uma reformulação dos mesmos três) ou uma fonte melhor
de ações em circulação pré-2020 — o negativo está medido com rigor e é entrega
científica legítima, não fracasso a ser contornado.

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
- **Tabela de 208 contas** do plano padrão da CVM: leva a cobertura do mapa de
  **4,95% para ~85%** das 5,55 M de linhas. ~7 h de anotação; o trabalho real é o
  G4 conceito a conceito. Entregar como curadoria + join declarado, **nunca como
  modelo** (§3.8).
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

1. Commitar o pendente e **mesclar `corrige-contrato-corpus` em `main`** —
   enquanto não mesclar, `main` continua com o contrato de corpus quebrado.
   Arquivos hoje modificados/novos, todos com suíte verde (1.784): `.gitignore`,
   `AGENTS.md`, `MEMORY.md`, `scripts/ocr_batch_mistral.py`,
   `tests/test_ocr_batch_mistral.py`, `corpus/holdout_2T2026/` (dados fora do
   Git por `.gitignore`, só o manifesto entra), `src/precos.py`,
   `tests/test_precos.py`, `artefatos/etapa19/`,
   `resultados/pre_registro_etapa19_fcf_yield_2026-09-08.md`,
   `resultados/validacao_etapa19_fcf_yield_2026-09-08.md`. Provavelmente vale
   dois commits separados (holdout/retry-404 vs. etapa 19), já que são ondas
   de trabalho independentes.
2. Recuperar o vintage dos 20 documentos congelados pelo catálogo IPE (custo
   zero) e gravar `data_publicacao`/`versao` no manifesto do `principal`. É o que
   o G1 do Rank 5 reprovava, e não exige decisão de ninguém.
3. Rodar `python -m scripts.preparar_auditoria_final` sobre o fingerprint
   `5b9b142d` (arquivar `auditoria_groundedness.json`/`plano_estabilidade.json`
   de fingerprint antigo antes, se ainda estiverem no lugar) e repetir a leitura
   humana das 15 perguntas.
4. Depois da leitura: `scripts/executar_estabilidade.py --permitir-api-paga`
   (30 chamadas) e `scripts/consolidar_auditoria_final.py` — promoção a
   `completa` exige groundedness ≥ 0,90.
5. Em paralelo, sem depender de (3): dupla leitura dos 10 gabaritos pendentes de
   `conjunto_agentes.csv` — destrava o McNemar da etapa 12.
6. Se ML voltar à prioridade: os três destravadores do §3.8 já foram gastos
   (§3.16 fechou o de preço). Reabrir exige dado genuinamente novo, não uma
   reformulação. Nenhum dos candidatos mortos reabre sem isso.
7. Se o holdout for usado: só em medição **confirmatória pré-registrada**, uma
   vez. Não iterar contra ele.
