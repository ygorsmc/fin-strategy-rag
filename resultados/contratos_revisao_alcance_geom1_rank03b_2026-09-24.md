# Revisão do alcance GEOM-1 — contrato das correções

Data: 2026-09-24. Pedido do usuário: fazer as correções apontadas na revisão
do [relatório de alcance](alcance_geom1_rank03b_2026-09-24.md). Escrito antes
de editar código ou documentos. Não altera a regra GEOM-1, a v4, o CSV de
correções, os painéis, os gates nem os artefatos já publicados de 18/09 e
24/09. Não decide nenhum ponto do pré-registro. Sem download, API paga,
holdout, alvo, T1/T2, baseline ou treino.

**Exposição declarada:** a busca numérica de R3 já foi executada uma vez
durante a revisão, em memória e sem contrato; os resultados são conhecidos.
A execução formal reproduz o método fixado aqui. Não é teste cego.

## R1 — correção "por conta" retirada do próximo passo

Achado: corrigir só o ativo de 140867 não reduz o G0.3 — o salto
1T→2T/2024 passa para 2T→3T/2024, porque 142900 segue em UNIDADE — e deixa
os trimestres de FCO 2T2024 e 4T2024 derivados de escalas diferentes. O G0.3
só olha o ativo; o G0.5 proposto lê veredito por documento.

Correção: ressalva datada no relatório de 24/09 (o parágrafo original fica,
marcado como retirado), MEMORY.md e AGENTS.md. Regra: correção que alcance só
uma das contas que o painel usa exige, antes, G0.3 e G0.5 lendo o veredito
por conta.

Falsificação: algum texto vigente recomendar correção só do ativo sem essa
pré-condição.

## R2 — alcance da prova: contradição declarada, não resolvida

Achado da própria revisão: "correção por documento só com as duas contas
provadas" contraria a v4 governante, em que prova de saldo (1, 2 ou 1.01.01)
corrige o documento inteiro — o construtor aplica a escala do documento ao
ativo e ao FCO. A linha GEOM-1 (plano de 18/09, contrato de 24/09) exige
demonstrar a escala nas contas que o painel usa.

Correção: **[DECIDIR]** no rascunho v2, com as duas opções e suas
consequências. Nenhuma mudança no consumidor, no manifesto ou nas regras.

Falsificação: algum documento declarar uma das opções como vigente sem decisão
do responsável; código do consumidor ou do construtor alterado nesta onda.

## R3 — busca numérica exata como evidência reprodutível

Script novo, offline, sobre as fontes fixadas no pin de 24/09, só anexos de
notas (grupos 193/412), `pdftotext -layout` e `-raw`. XML lido direto, sem o
leitor do painel nem o replay GEOM. Compara em memória:

- **Ativo (1):** consolidado corrente e comparativo, individual corrente e
  comparativo, consolidado corrente ×1.000 e ÷1.000. Comparação com sinal.
- **FCO (6.01):** consolidado acumulado corrente e anterior, individual
  corrente, consolidado corrente ×1.000 e ÷1.000. Comparação por módulo.
- **Identidade:** saldo final de caixa da DFC (6.05.02) = caixa do balanço
  (1.01.01), consolidado, corrente. Booleano. Não envolve 6.01 e não prova a
  escala do FCO.

Publica: para o ativo, página, linha, coluna e trecho mascarado; para o FCO,
só páginas. Zero correspondência é "busca exata sem correspondência nas notas",
nunca ausência da informação em outra fonte.

Guardas: contrato, código e fontes conferidos contra os pins antes da leitura;
sete arquivos protegidos antes e depois; destino existente recusa
sobrescrita; erro de leitura ou de conversão derruba a execução, nunca vira
"sem correspondência"; autoverificação antes de gravar — nenhum dígito em
trecho, nenhum número publicado com módulo ≥ 1.000 fora dos campos de hash e
data, nenhum valor comparado (≥ 1.000, com ou sem separador) em texto
publicado. Se falhar, não grava.

Falsificação: a saída conter montante ou sinal de FCO; os dois modos
divergirem sem declaração; o artefato de 24/09 ser alterado.

Contraprovas: conversão pt-BR (milhar, decimal, sinal por parênteses e por
traço Unicode); valor certo em outra coluna; FCO sem trecho; autoverificação
acusando vazamento em texto e em número; fonte com hash divergente; destino
existente.

## R4 — máscara por classe, sem trecho em contexto de fluxo

Achado: a correção de 24/09 enumerou variantes. Cinco traços Unicode,
`(R$ 123)` e palavras de polaridade ("aplicado", "negativo") passam.

Correção: sinal é classe — todo caractere Unicode de traço, hífen, menos,
mais ou parêntese —, e moeda (`R$`, `US$`) entra no número. Linha que casa o
padrão de fluxo (atividades operacionais, fluxo de caixa) não publica trecho
em nenhuma menção, inclusive declaração de unidade. O código que produziu o
inventário publicado é preservado antes da mudança; o inventário de 24/09 não
é regravado. A regra nova é reaplicada em memória às mesmas páginas: publicar
se difere do inventário publicado só pela retirada de trechos de fluxo.

Falsificação: algum caractere daquela classe, adjacente a número, sobreviver;
trecho de linha de fluxo publicado; teste anterior enfraquecido.

## R5 — o que o contrato de 24/09 pedia e o relatório não publicou

Na ressalva:

- por que o total Consolidado da nota de segmentos não é "linha gerencial"
  (item 3);
- concordâncias e divergências entre principal, auditor e revisão (item 5);
- comando reproduzível sem o diretório temporário da sessão;
- caminho absoluto em `pin_execucao.json`, herdado do `selecao.json` de
  18/09 e fixado por hash: declarado, não reescrito;
- dimensionamento: no máximo −2 dos 20 saltos que faltam ao G0.3;
- rotas locais (anexo do grupo 192, identidade interna da DFC) como opções
  que exigem contrato — não executadas.

## R6 — teste de interface hermético

`tests/test_config_app.py::test_app_cacheado_sobe_sem_habilitar_respostas_dev_como_finais`
passa a fixar `HABILITAR_PERGUNTAS_LIVRES=0` no próprio processo. Nenhuma
asserção muda; a mudança é declarada no docstring.

Falsificação: a suíte depender do `.env` local; asserção alterada.

## Entrega

Testes focados; suíte completa sem sobrescrever variável de ambiente;
auditor-conformidade somente leitura antes de concluir; MEMORY.md atualizado.
