# Contratos do lote B — dados necessários ao Rank 3-B (D2–D5)

**Data:** 2026-09-16. **Escrito antes de qualquer código deste lote.**
**Origem:** [levantamento de desbloqueio](pendencias_desbloqueio_treino_dfc_2026-09-15.md), §3 (D2–D5) e §6 (lote B).
**Decisões do responsável (16/09):** painel de pesquisa **separado**; download de
documentos públicos da CVM **autorizado, com piloto antes da extensão**; parar
**no rascunho do pré-registro**, sem medir T1/T2.

**Não é treino, não é medição do alvo.** Produz inventário, evidência de fonte e
a regra de construção do painel de pesquisa. `cvm.duckdb` e `cvm_treino.duckdb`
não são alterados.

> ## ⚠️ RESSALVA ANTES DA SEGUNDA EXECUÇÃO DO PILOTO (2026-09-16, manhã)
>
> A primeira execução do piloto foi **interrompida** depois de 3 documentos, e
> o reconhecimento feito em seguida mudou quatro coisas. Tudo abaixo foi fixado
> **antes** da segunda execução, com base em estrutura e custo medidos — nenhuma
> adjudicação foi feita, e nenhuma estatística de rótulo foi calculada.
>
> **RA1 — Segundo formato (amplia V1.2).** A partir de 2021 a CVM entrega um
> **XML único** (`025704ITR30-09-2024v1.xml`), sem `.itr`/`.dfp`; os dois
> formatos convivem no mesmo ano. O piloto o classificou corretamente como
> `formato_nao_reconhecido`. V1.2 passa a aceitar os dois, escolhidos pelo
> conteúdo. Medido em 9 documentos reais (2011–2025, ITR e DFP, os dois
> formatos): **X1.3 = 20/20 linhas iguais ao ZIP em todos**, inclusive o
> acumulado do exercício anterior, cuja data o XML único não traz e é derivada.
>
> **RA2 — Vazão e servidor.** 12 a 34 s por documento (o PDF renderizado, de até
> 8 MiB, domina o tamanho e não pode ser evitado). O servidor chegou a
> responder `HTTP 200` com 40 bytes: *"There is not enough space on the disk."*
> — rejeitado como transporte. O download passa a abortar transferência parada
> (`--speed-limit`) e mantém sessão.
>
> **RA3 — Evidência por anexo (amplia N1, sem mudar P1.3).** A classe N1.3 por
> documento saiu `contraditorio` em 9 de 11 amostras: o comentário de
> desempenho fala em "R$ milhões" enquanto as demonstrações estão em milhares.
> Os anexos têm código de grupo estável: **notas explicativas = 193 (ITR) e 412
> (DFP)**; comentário/relatório = 192/1653. O piloto passa a medir também, **só
> nas notas**:
> - **cabeçalho de apresentação**, vocabulário fechado aqui:
>   `MIL` = "expressos em milhares de reais", "(em milhares de reais",
>   "em milhares de reais, exceto", "valores em milhares de reais";
>   `UNIDADE` = "expressos em reais", "(em reais", "em reais, exceto",
>   "valores em reais";
> - **evidência numérica**: se algum valor monetário do formulário (contas
>   `1`, `1.01.01`, `2`, `6.01`–`6.05.02`, módulo ≥ 1.000) aparece no texto das
>   notas **como está** (`bruto`), **dividido por 1.000** (`dividido`) ou
>   **multiplicado por 1.000** (`multiplicado`), como número inteiro isolado
>   no formato pt-BR. Classe: a única que aparece; `nenhum`; ou `conflitante`.
>
> O critério P1.3 **não muda**: c3 continua sendo a classe N1.3 do documento
> diferente de `ausente`. As medidas novas alimentam o contrato do lote C.
>
> **RA4 — Escopo da extensão (substitui S1), por custo medido.**
> - **Escala por trecho:** um *trecho* é a sequência máxima de documentos
>   consecutivos da mesma companhia com o mesmo rótulo. Adquirem-se as **duas
>   pontas** de cada trecho: 307 documentos nas 54 companhias mistas e 34 nas
>   17 só `UNIDADE` — contra 2.083 documento a documento (~16 h).
>   **Premissa** a testar, não a supor: o interior de um trecho tem a escala das
>   pontas quando as duas concordam. O piloto ganha o estrato
>   **E10 — trechos completos**: 3 trechos de companhias mistas com ≥ 3
>   documentos (até 10 cada), escolhidos pelo hash da primeira ponta.
> - **Controle só `MIL`:** 30 companhias por hash, um documento cada (não 629).
> - **Vintages:** a aquisição completa custaria 4.134 versões (~23 h). Fica
>   **fora** do lote. O painel usa a **política conservadora** — um trimestre só
>   está disponível em D quando todas as versões usadas já tinham sido recebidas
>   —, que não vaza e custa perda, e publica o **inventário dessa perda**. O
>   estrato E7 continua medindo a recuperabilidade. O levantamento admite
>   exatamente isto: *"é necessário conhecer as perdas"*.
>
> **RA5 — Placeholder.** Em `003328`/1T2021 o Ativo Total 1,0 está no próprio
> formulário, e as notas não trazem o balanço: não há fonte para corrigir o
> valor. Ativo Total com módulo ≤ 1 na unidade declarada é tratado como **valor
> não informativo** no lote C (regra a declarar lá), não como correção.
>
> **RA6 — Dois deslizes meus, declarados.** (a) Ao estudar o XML único,
> **imprimi dois valores de FCO acumulado de uma companhia** (`025704`, 3T2024),
> o que O1.3 proíbe. Não houve rótulo, semestre futuro, soma ou agregação.
> (b) Um teste de `tests/test_fonte_rad_cvm.py` **executou o `curl` real** uma
> vez (um argumento padrão escapava do dublê); gravou só em diretório
> temporário. Corrigido, e o arquivo de testes agora proíbe processo real.

---

## O1 — Cegueira ao desfecho (vale para todo o lote B e o lote C)

O pré-registro de 11/09 foi **consumido** (`fbae30cc…`) e o novo ainda não
existe. Até ele ser aprovado pelo responsável:

1. **Proibido calcular sobre dado real:** `Y`, S1, S2, taxa do evento, soma ou
   sinal de FCO em janela futura, TTM de FCO agregado, T1, T2, AUC, baseline,
   precisão, ou qualquer estatística condicional ao rótulo.
2. **Permitido:** contagens estruturais (documentos, versões, durações,
   rótulos de escala, identidades contábeis, igualdade de valores entre duas
   declarações do mesmo período), número de observações e de companhias.
3. Valor individual de FCO só é lido para **testar igualdade** entre duas
   fontes (parser × ZIP, `ÚLTIMO` × `PENÚLTIMO`). Não é impresso, agregado nem
   publicado.
4. Todo artefato publicado por este lote é conferido por teste: **nenhuma chave
   `y`, `rotulo`, `taxa_do_evento`, `s1`, `s2`** em lugar nenhum.

**Declaração do que já foi visto** (para o pré-registro novo): a contagem de
observações construíveis (10.605 em 494 companhias, 15–16/09), a fração de G0.3
(0,005874) e os inventários de G0.1–G0.3, G1 e G0.4. **Nenhuma taxa de evento,
T1, T2 ou baseline sobre dado real foi calculada** em 11/09, 12/09, 15/09 ou
16/09 — a rodada de 11/09 parou em G0.

---

## M1 — Medições estruturais já feitas (reconhecimento de 16/09)

Extraídas dos 31 ZIPs pinados em `corpus/cvm/manifesto_cvm.csv`, consolidado,
universo `plano_contas NOT LIKE 'll3_09_%' AND NOT is_banco` (700 companhias):

| Fato | Medido | Consequência para o desenho |
|---|---|---|
| `6.01` é conta fixa | `ST_CONTA_FIXA = 'S'` em 45.045/45.045 | Identidade por código é **evidenciada** para esta conta (D2), não suposta |
| Descrições de `6.01` | 2: "Caixa Líquido Atividades Operacionais" (698 cias) e **"…Seguradora/Resseguradora" (2 cias)** | **Seguradoras dentro do universo "não financeiro"** — plano `ll3_13` tem 3 companhias |
| `1`/`2` | "Ativo Total"/"Passivo Total", fixas, 45.055 cada | Identidade Ativo = Passivo disponível como verificação |
| Escala nas contas monetárias | **0** de 22.486 documentos misturam | Escala é propriedade **do documento** para estas contas |
| `DFC_MD` × `DFC_MI` | **0** documentos com os dois; **53** companhias trocam de método | FCO total não depende do método (CPC 03); parear por demonstrativo fabrica "sem antecedente" |
| Rótulo de escala por companhia | 629 só `MIL`, **17 só `UNIDADE`**, **54 mistas** (1.683 documentos) | Três componentes de T1 são nível em reais: erro consistente importa |
| Fronteiras de rótulo | 229 documentos (119 `MIL`, 110 `UNIDADE`); 82 já adjudicados pelo inventário v2 | Corrigir só fronteiras deixaria o interior de trechos errados |
| Ativo Total ≤ 1 | 35 documentos (32 zerados, 3 com 1,0) | Placeholder, não valor |
| Ativo ≠ Passivo | 6 documentos | Defeito de valor, não de escala |
| Identidade de caixa da DFC | 23 somas e 14 saldos que não fecham, em 22.483 períodos | Verificação de integridade disponível |
| Versões | 3.863 de 24.925 documentos têm mais de uma; número em mãos = versão máxima em 100%; intervalo v1→vmax: mediana 7, p90 260, máx. 2.093 dias | D5 é real |
| Formulário XML | `CodigoEscalaMoeda` do formulário **é a origem do rótulo** do CSV | O formulário não adjudica escala; o texto da companhia pode |
| Notas explicativas | No 3T2020 de `003328`, formulário diz `UNIDADE`, notas dizem "valores expressos em milhares de reais" | Adjudicação por fonte é viável |

---

## V1 — Aquisição de documentos da CVM

**V1.1** Fonte: `LINK_DOC` do cadastro de cada ZIP, por **HTTPS**, identificado
por `ID_DOC` (cada versão tem o seu). Agente HTTP declarado, sessão com cookies,
espera entre requisições.

**V1.2 — Íntegro ou falha.** O pacote só é aceito se: o ZIP externo passa em
`testzip`; contém exatamente um formulário `.itr`/`.dfp`; o formulário interno
passa em `testzip`; e contém `InfoFinaDFin.xml`,
`PeriodoDemonstracaoFinanceira.xml` e `FormularioDemonstracaoFinanceira*.xml`.
Falha depois de todas as tentativas é **falha de acesso**, registrada — nunca
"documento inexistente".

**V1.3 — Procedência.** Cada pacote aceito entra num manifesto JSONL com
`id_doc`, `cd_cvm`, `conjunto`, `dt_refer`, `versao`, URL, data do download,
tamanho e SHA-256. Os binários ficam fora do Git, em
`artefatos/painel_pesquisa_rank03b/rad/`; o manifesto entra.

**V1.4** Não depender do PDF renderizado que o pacote traz: no piloto de
reconhecimento ele veio com exatamente 2²³ bytes, tamanho suspeito.

## X1 — Extração do formulário

**X1.1** Só `CodigoTipoInformacaoFinanceira = 2` (consolidado), mesma regra da
carga compartilhada. Contas `1`, `2`, `6.01`–`6.05`, `6.05.01`, `6.05.02`,
`1.01.01`.

**X1.2** `ValorConta{N}` corresponde ao período `NumeroIdentificacaoPeriodo = N`
de `PeriodoDemonstracaoFinanceira.xml`. Coluna sem período declarado é erro.

**X1.3 — Prova do mapeamento.** Para a **versão máxima**, os valores extraídos
têm de ser **idênticos** aos do ZIP, na mesma conta e no mesmo período. Uma
divergência invalida o parser para o documento; a taxa de concordância é
publicada.

**X1.4** `CodigoEscalaMoeda` é lido e o mapeamento código→rótulo é **medido**
contra o CSV, não suposto.

## N1 — Evidência textual de unidade

**N1.1** Texto dos PDFs anexados em `AnexoDocumento.xml` (notas explicativas,
comentário de desempenho), extraído com `pdfplumber`, sem OCR pago.

**N1.2** Vocabulário fechado de declarações de unidade, **fixado aqui**:
- `MIL`: "em milhares de reais", "em milhares de R$", "R$ mil", "(R$ mil)",
  "expressos em milhares", "em R$ milhares";
- `UNIDADE`: "em reais" não seguido de "mil"/"milhões", "expressos em reais",
  "(R$)" isolado como cabeçalho de unidade;
- `MILHAO`: "em milhões de reais", "R$ milhões" em cabeçalho de unidade.

**N1.3** Classificação do documento: `declara_MIL`, `declara_UNIDADE`,
`declara_MILHAO`, `contraditorio` (mais de uma classe), `ausente`. Menção a
valores em prosa ("lucro de R$ 1.393,6 milhões") **não** é declaração de
unidade de tabela e não entra.

**N1.4** Cada classificação guarda a página e o trecho literal (≥ 60
caracteres), para leitura humana.

---

## P1 — Piloto, com seleção por estrutura

**P1.1 — Seleção determinística, cega ao desfecho.** Estratos, e dentro de cada
um os documentos ordenados pelo SHA-256 de `cd_cvm|conjunto|dt_refer|versao`:

| Estrato | Quantos |
|---|---:|
| E1 fronteira declarada `UNIDADE` | 6 |
| E2 fronteira declarada `MIL` | 6 |
| E3 interior de companhia mista (não fronteira) | 6 |
| E4 companhia só `UNIDADE` | 5 |
| E5 companhia só `MIL` (controle) | 5 |
| E6 Ativo Total ≤ 1 com valor não nulo | 3 |
| E7 documento com mais de uma versão: **v1 e vmax** | 8 pares |
| E8 DFP (formulário `.dfp`) | 4 |
| E9 exercício 2011–2012 (formato antigo) | 4 |

No máximo uma entrada por companhia por estrato. Estratos se sobrepõem; o
documento é baixado uma vez.

**P1.2 — Métricas publicadas:** taxa de download íntegro; taxa de parse; taxa
de igualdade X1.3; mapeamento de `CodigoEscalaMoeda`; distribuição N1.3 por
estrato; concordância entre N1.3 e o rótulo declarado; concordância entre N1.3
e o estado do inventário v2 quando houver; para E7, igualdade da v1 extraída
com o `PENÚLTIMO` posterior (informativo, não critério).

**P1.3 — Critério para estender, fixado antes do piloto.** A extensão para o
escopo completo acontece se, e só se:

1. download íntegro ≥ 90% (falhas de acesso reportadas);
2. igualdade X1.3 = **100%** dos documentos com parse (um erro de mapeamento
   invalida tudo o que vem depois);
3. N1.3 diferente de `ausente` em ≥ 70% dos estratos E1–E4 somados.

Se (2) falhar, o parser é corrigido e o piloto **repetido inteiro**. Se (1) ou
(3) falharem, a extensão para e o relatório diz qual caminho sobra — sem
afrouxar o critério.

**P1.4** O piloto **não adjudica** nada. Ele mede se a evidência existe.

---

## S1 — Escopo da extensão (se P1.3 passar)

- **Escala:** todos os documentos das 54 companhias mistas e das 17 só
  `UNIDADE`; os documentos com Ativo Total ≤ 1 não nulo; e um documento por
  companhia só `MIL` escolhido por hash, como **controle** de erro consistente.
- **Vintages:** a versão v1 (e intermediárias) de todo documento com mais de uma
  versão cujo intervalo cego `[dt_receb(v1), dt_receb(vmax))` contém ao menos
  uma data de recebimento de outro documento da **mesma companhia**. Fora
  disso, nenhuma decisão cai no intervalo e a versão antiga é irrelevante.

## R1 — O que o lote B entrega e o que não entrega

**Entrega:** manifesto de aquisição; tabela de evidência por documento
(rótulo declarado, código do formulário, declaração textual com página e
trecho, estado do inventário, identidades contábeis); inventário de vintages;
inventário de períodos atípicos, N2 e N3 no recorte `6.01`; relatório de
viabilidade com números medidos.

**Não entrega:** correção de valor, painel, gate, pré-registro. A **regra de
adjudicação** e a **regra de construção** são o contrato do lote C, escrito
depois de ver a evidência estrutural e **antes** de construir.

## Alternativas rejeitadas

| Alternativa | Por que não |
|---|---|
| Adjudicar pelo `CodigoEscalaMoeda` do XML | É a origem do rótulo errado; concordaria com o CSV por construção |
| Adjudicar por continuidade do valor bruto | Suspeita, não prova (§3.7, correção de 12/09) |
| Corrigir só os 229 documentos de fronteira | O interior de um trecho errado ficaria errado e criaria saltos novos |
| Presumir certas as 17 companhias só `UNIDADE` | T1.2, T1.4 e T1.5 são níveis em reais; erro consistente muda quintil |
| Baixar todas as 4.741 versões antigas | ~24 GB sem necessidade; só importa versão cujo intervalo cego contém uma decisão |
| OCR pago das notas | Os anexos têm camada de texto; `pdfplumber` basta até prova em contrário |
| Selecionar o piloto pelos documentos "mais suspeitos" | Seria escolher pelo desfecho da adjudicação |

## Condições de falsificação do lote B

| # | Condição |
|---|---|
| 1 | Algum artefato do lote conter `y`, taxa do evento, S1/S2 ou estatística de rótulo |
| 2 | Parser da vmax divergir do ZIP e o lote seguir adiante |
| 3 | Documento truncado aceito como íntegro |
| 4 | Critério P1.3 alterado depois de ver o piloto |
| 5 | Hash de `cvm.duckdb`, `cvm_treino.duckdb`, dos ZIPs ou do pré-registro de 11/09 mudar |
| 6 | Arquivo da outra frente mudar |

---

> ## ⚠️ RESSALVA RA7 — auditoria de conformidade e revisão final (2026-09-16, tarde)
>
> **A declaração do que já foi visto (O1) estava incompleta.** Ela diz que
> nenhuma taxa de evento foi calculada em 15/09. Foi: a
> [implementação QW1–QW8](implementacao_qw1_qw8_2026-09-15.md), §3, publica
> "Taxa do evento **0,0526 → 0,0530**", "Com rótulo `y` diferente: **3**" e
> "FCO TTM não positivo **−5**", no painel compartilhado, para medir o efeito
> da correção N1 — antes de este contrato existir. O pré-registro v2 (§11)
> declara o número, o que ele revela (a taxa-base agregada) e o que não revela
> (nada condicional a componente). Além disso, até a correção A1 da auditoria,
> o auditor calculava `y` **em memória** em toda medição de G1, sem imprimir.
>
> **Número corrigido:** a medição M1 citava a descrição operacional da `6.01`
> em "698 companhias"; são **700** — as 2 seguradoras também a usam
> (`medicoes_estruturais.json`, `descricoes_6_01`).
>
> **Desvios da letra deste contrato, declarados:**
>
> - **V1.1 "espera entre requisições":** o downloader só esperava **entre
>   tentativas** de um mesmo documento, não entre documentos. O piloto rodou em
>   sequência, com uma conexão, **sem pausa depois de um download bem-sucedido**;
>   a aquisição da extensão (S4 do lote C) rodou com **três conexões
>   simultâneas**, também sem essa pausa, 371 documentos. A pausa de 1 s depois
>   de cada sucesso (`PAUSA_ENTRE_DOCUMENTOS`) só entrou no código com a
>   auditoria, depois das duas aquisições. Nenhuma falha de acesso resultou; o
>   servidor é público. Fica registrado como desvio, não como prática.
> - **P1.2, E7:** o contrato pede "igualdade da v1 extraída com o `PENÚLTIMO`
>   posterior". O piloto mediu **v1 × versão máxima** (§3.4 do relatório). É
>   informativo, não critério, e não entra em P1.3; a métrica pedida não foi
>   medida.
> - **Procedência do código do piloto:** `piloto/resultado.json` **não
>   registra o hash do código** que o produziu, e `scripts/fonte_zip_cvm.py` foi
>   editado durante o lote (célula vazia → nulo, item 7 do relatório). O
>   resultado do piloto não pode ser amarrado a um hash de código. A edição
>   só troca a **falha** numa célula vazia por nulo; não altera valor presente,
>   que é o que c2 (parser = ZIP) compara. Os artefatos do lote C registram os
>   hashes do código que os produziu.
