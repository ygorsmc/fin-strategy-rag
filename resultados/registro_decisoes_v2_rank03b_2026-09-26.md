# Registro de decisões — pendências do pré-registro v2 do Rank 3-B

**Data:** 2026-09-26.

**Quem decidiu:** Claude (sessão principal), por **delegação expressa do
responsável** nesta data: *"Deixo as decisões de aprovação com você"*. Não é
aprovação pessoal do responsável. Ele pode revogar qualquer item antes do
congelamento; a revogação entra aqui, com data, sem apagar este texto.

**Base:** a [proposta v3](proposta_preenchimento_decidir_v2_rank03b_2026-09-26.md)
(SHA-256 `46bc85539a3f4570…91be59`), os pareceres do revisor independente em
`artefatos/preenchimento_decidir_v2_rank03b_2026-09-26/` e conferência própria
no código e nas contagens estruturais já publicadas, descrita em cada item.
Rascunho antes deste registro: `bd880da38f55f3c6…a1e1948f` (commit `bd07216`).

**O que este registro não faz:** não congela o v2. Não autoriza o executor v2,
que exige contrato antes do código, nem busca ou reconferência com FCO real,
busca de FCO arredondado, T1, T2, baseline ou treino. **O congelamento exige
ato explícito do responsável,** ou delegação expressa para esse ato, com as
palavras e a data. A delegação de 26/09 respondeu à pergunta sobre quais itens
aprovar e que lado escolher no §5.5 e no §6.1. Ela cobre os pontos [DECIDIR] e
o adendo ao O1, não o congelamento, que encerra a cegueira e libera a primeira
medição de desfecho.

**Revisado em 27/09** depois da auditoria de conformidade da onda (APTA COM
RESSALVAS; 1 ALTA, 4 MÉDIA, 5 BAIXA) e da reconferência dela (FECHADO COM
RESSALVAS; 4 BAIXA novos, tratados). Nenhum achado mudou a opção escolhida em
nenhum item, mas M1, M3, M4 e B2 alteraram ou acrescentaram regras. Detalhe
em "Auditoria da onda", no fim.

## Resumo

| Item | Decisão | Em relação à proposta v3 |
|---|---|---|
| §3.2 Seguradoras | Excluir `plano_contas LIKE 'll3_13_%'`, com falha fechada se o padrão alcançar outro plano além de `ll3_13_48e4cd07` | Igual, mais a falha fechada e a descrição exata da assinatura |
| §5.1 G0.1 | Unicidade; derivação entre métodos permitida, contada e sujeita às demais regras | Igual, com texto mais preciso e contagem das observações expostas |
| §5.5 G0.5 | **C+E, em três níveis:** censura do trimestre derivado de escalas heterogêneas e da observação cuja janela, S1 ou S2 misture escalas, em ambos os casos com documento sem veredito para o FCO; e `fco_ttm_sobre_ativo` ausente quando ativo e TTM divergem de escala. As regras 1 e 2 comparam escalas aplicadas ao FCO; a regra 3, a aplicada ao ativo com a aplicada ao FCO. G0.5 passa a ser "uso zero" | **Diverge do preenchedor (C);** adota a alternativa do revisor sem esperar medição, porque a perda tem teto por construção. O terceiro nível e a escala comparada vieram da auditoria |
| §6.1 Grade de D | Grade por disponibilidade do FCO utilizável, **com uma observação por (companhia, q1)**: a de maior D, escolhida antes de janela, elegibilidade e censura, sem reposição. Ordem de filtros fixa; antes do congelamento, nada do que permita recompor a contagem omitida pelo O1 | **Diverge do preenchedor;** adota a alternativa do revisor e fixa a ordem |
| §8.1 Suporte de T2 | Piso de 30 companhias com os dois rótulos, só na amostra original, **e zona cinzenta:** lacuna < 0,12 com frequência bootstrap de lacuna ≥ 0,12 acima de 10% dá INDECIDÍVEL. Semente, ordem e denominador fixados | Acrescenta a opção C, que a proposta apresentou sem propor |
| §12-bis Alcance da prova | Opção B, estendida ao "decidido" do G0.5, com três condições para qualquer correção por conta | Igual, mais as condições da correção por conta |
| O1 | Adendo com a exceção protetiva (nove cláusulas) e o esclarecimento da identidade contábil com saída booleana | Igual nas nove cláusulas, com três ajustes; o esclarecimento é novo |
| Transversal | Congelar só depois do executor v2 testado, da conferência independente e da resolução estrutural do G0, com pins novos, e por ato explícito do responsável. O O1 vale até lá | Igual, mais o ato do responsável |

Texto normativo: no próprio [rascunho v2](pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md)
(cabeçalho e §§2, 3.2, 4, 5, 5.1, 5.5, 6.1, 8, 8.1, 10, 11.1, 11.7, 12-bis, 13
e 14) e no [adendo ao O1](adendo_o1_rank03b_2026-09-26.md).

## Exposição de quem decidiu

- Li o rascunho v2 inteiro, inclusive o §11. Vi, portanto, a taxa-base
  agregada do evento no painel compartilhado e a contagem de descartes por
  `FCO_TTM ≤ 0` que o §11.1 declara; não as repito aqui. Li também a proposta,
  os pareceres, o `AGENTS.md` e o `MEMORY.md`.
- Contagens estruturais lidas hoje em `medicoes_estruturais.json`, só nas
  chaves `rotulos_de_escala`, `fonte.companhias_por_plano`,
  `fonte.companhias_com_6_01_de_seguradora` e `fonte.companhias_no_universo`.
  Não abri painel DuckDB, pacote RAD nem PDF, e não li valor de FCO.
- Sou a mesma linha de sessões que conduziu a correção RAG do instrumento
  GEOM-1 (25 e 26/09). As execuções dela sobre dado real leram FCO em memória
  para igualdade e calcularam piso e teto no verificador; isso fica declarado
  no §11.7 do rascunho e na cláusula 7 do adendo. Nenhum valor de FCO foi
  impresso nem visto.
- Nenhuma estatística de rótulo além das do §11.1 foi vista, e nenhuma decisão
  usou número de desfecho. Os números citados abaixo são contagens
  estruturais já publicadas.
- A taxa-base permite prever que o piso de 30 companhias com os dois rótulos
  do §8.1 provavelmente é alcançado. O número 30 não foi calibrado por essa
  expectativa: repete o mínimo de companhias que a v1 fixou para T1.
  Declarado também no §11.1 do rascunho.

## §3.2 — Seguradoras: excluir, com falha fechada

**Conferido.** `plano_contas` é a assinatura do mapa semântico
(`src/mapa_contas.py`, `assinatura_plano_contas`). O prefixo nomeia a conta do
lucro consolidado (`ll3_13` = lucro em `3.13`), e o sufixo é o resumo do mapa
inteiro. No universo de 700: 697 companhias em cinco planos `ll3_11_*` e 3 no
`ll3_13_48e4cd07`. Em `023159` e `024180`, a `6.01` se chama "Caixa Líquido
Atividades Seguradora/Resseguradora".

**Julgamento.** Seguradora classifica como operacional parte do giro das
reservas técnicas. O "consumo operacional de caixa" dela é outro objeto
econômico, e a v1 já declarou a população como não financeira. O custo são 3
de 700 companhias, pago antes de medir. O prefixo descreve onde está o lucro,
não a atividade, e a decisão foi tomada conhecendo um só plano com ele. Por
isso a falha fechada: se o painel medido tiver outro plano `ll3_13_*`, o
executor para em vez de excluir em silêncio.

**Não se pode alegar:** que a população é estritamente não financeira, nem
qualquer afirmação setorial.

## §5.1 — G0.1: leitura por unicidade

**Conferido.**
- O G0.1 que a v1 executou conta só grupos (companhia, trimestre) com mais de
  um demonstrativo entre as linhas
  (`scripts/auditar_rank03b_consumo_operacional.py`, `gate_g0`). Um trimestre
  derivado entre métodos nunca foi contado.
- A derivação do 4T pareia anual e nove meses sem o demonstrativo na chave, o
  que tornava um 4T entre métodos possível já no painel da v1. Conferi isso no
  código durante a revisão da proposta (achado E1).

**Julgamento.** O risco que a v1 declarou é duplicar caixa somando os dois
métodos, e ele é nulo por construção no painel de pesquisa: nenhum documento
traz os dois métodos, e há um valor por (companhia, trimestre). O total
operacional é o mesmo número nos dois métodos (CPC 03, itens 18–20A). A norma
é fonte externa, não conferida aqui, e o critério de refutação do lote C nunca
foi testado; isso é ausência de teste, não evidência a favor. Censurar os
trimestres derivados entre métodos removeria até 117 deles sem defeito
demonstrado, e a leitura literal reprovaria G0 por algo que não é defeito.

**Acréscimo à proposta.** O G0 também publica quantas observações da amostra
usam, na janela ou no rótulo, algum trimestre derivado entre métodos. Assim a
exposição ao risco residual fica visível: troca de método que coincida com
reclassificação entre atividades.

## §5.5 — G0.5: C+E, sem esperar a medição

**Conferido no código.**
- A janela é formada pelos oito trimestres mais recentes disponíveis em D,
  contíguos e encadeados; se houver lacuna, a observação é censurada
  (`construir_amostra`).
- O rótulo usa a linha mais recente de cada trimestre.
- S1 e S2 são somas de dois trimestres cada (`_somas_do_rotulo`).
- No ITR, a DFC é acumulada no exercício: só o 1T não é derivado. O 2T e o 3T
  saem de ITRs acumulados, e o 4T sai da DFP menos o ITR de nove meses.

**Por que C sozinha não basta.** A censura C só vê o trimestre fabricado por
subtração de acumulados de escalas diferentes. Há dois casos em que
aparecem, na mesma janela ou no mesmo S1/S2, valores fora de proporção por um
fator de mil sem nenhum trimestre heterogêneo:
- uma mudança de escala na virada do exercício (DFP numa escala, ITR do 1T
  seguinte em outra);
- um 1T isolado de escala diferente dos vizinhos. Há 71 trechos de um
  documento só em companhias mistas; quando esse documento é o ITR do 1T, é
  este o caso.

Esses casos mudam sinal de soma, portanto mudam rótulo e elegibilidade, não só
nível. Exemplo sintético da proposta: 4T de −30 mil somado a 1T de +50 mil
registrado como +50 dá `S1` negativo quando o verdadeiro é positivo.

**Por que não esperar a medição.** A perda de C+E tem teto por construção,
calculável com números já publicados:
- sem correções, a escala aplicada é a declarada;
- heterogeneidade só existe nas 54 companhias de rótulo misto; as 629 só `MIL`
  e as 17 só `UNIDADE` não têm (`rotulos_de_escala`);
- cada linha trimestral de FCO tem um só documento corrente, e cada linha gera
  no máximo uma data D. As observações perdidas não passam, portanto, do
  número de documentos dessas 54 companhias: 1.683 na tabela de rótulos, que
  só conta documentos com recepção única no cadastro. É ordem de grandeza, não
  limite exato.

Logo, C e E juntas tiram observações de no máximo 54 companhias, da ordem de
1.683. No pior caso, a amostra estrutural de 18/09 (10.748 observações, 502
companhias) conserva pelo menos 448 companhias e da ordem de 9.000
observações, muito acima do mínimo do T1 (500 e 30 por componente). Mesmo com
o dobro de documentos, a folga continuaria enorme. Medir antes não mudaria a
escolha, e decidir antes impede que o número a oriente. A perda real será
publicada.

**Julgamento sobre o custo.** E troca contaminação por seleção nas mesmas 54
companhias que C já atinge. A contaminação que ficaria sem E tende a atenuar
T1 e T2, o que empurra na direção de aprovar, o lado oposto da previsão
registrada. Aprovar por contaminação é erro pior que perder observações.

**Acréscimos à proposta.**
- O trimestre censurado **ocupa o seu lugar**: conta como disponível ao formar
  a janela e ao identificar q1, e só o valor dele é que não se usa. Sem isso,
  uma D gerada por outra linha (uma reapresentação, por exemplo) logo depois
  dele formaria a janela com os oito trimestres anteriores. Isso seria
  deslocamento disfarçado, com informação velha. Vale só para este estado,
  porque ele recusa um valor que existe e foi publicado. Os estados herdados
  do lote C (valor nulo, operando indisponível, duração fora da banda)
  descrevem ausência de valor trimestral. O `conflito_de_declaracoes` fica
  como limite declarado.
- **Qual escala se compara (auditoria, M3).** As regras 1 e 2 comparam
  escalas **aplicadas ao FCO**, e a regra 3 compara a aplicada ao ativo com a
  aplicada ao FCO. A escala aplicada ao FCO só muda com prova do FCO
  (§12-bis). Isso substitui,
  para o FCO, o "declarada ou aplicada" da população G5.1 de 17/09. Com a
  declarada na comparação, bastaria um vizinho sem veredito para censurar, e
  a prova do FCO não recuperaria janela nenhuma. Hoje, sem correções, as duas
  leituras coincidem. `documentos_decididos` não pode ser reaproveitado como
  está, porque conta como decidido o veredito apoiado só em saldo.
- **Terceiro nível (auditoria, B2).** `fco_ttm_sobre_ativo` fica ausente quando
  a escala aplicada ao ativo em D difere da aplicada ao FCO de algum documento
  do TTM, com um dos lados sem veredito para a própria conta. O ativo em D é
  escolhido fora da janela; quando vem de documento que não opera no TTM, as
  regras 1 e 2 não o veem. O preenchedor tinha tirado isso de E para não
  inflar a perda usada na escolha entre C e E. O motivo caiu quando se
  decidiu sem medir, e a regra entra como ausência de componente, sem perda
  de observação.
- O G0.5 publica também a exposição das 17 companhias só `UNIDADE`. O erro
  consistente, sem transição, não tem gate nenhum.
- **O teto de perda vale para o painel sem correções (auditoria, B1).** Uma
  correção com prova do FCO numa companhia só `UNIDADE` cria heterogeneidade
  fora das 54, e o teto é recalculado sobre o painel novo.

## §6.1 — Grade de D: uma observação por (companhia, q1), a de maior D

**Conferido no código.**
- q1 depende só de datas.
- O rótulo usa a linha mais recente publicada de cada trimestre, qualquer que
  seja D.
- Logo, duas observações da mesma companhia com o mesmo q1 têm o mesmo `Y`.
  Com trimestres de três meses, q1 é o trimestre da companhia seguinte ao que
  contém D, e "mesma (companhia, q1)" quer dizer "datas no mesmo trimestre da
  companhia".

**Julgamento.**
- Sem deduplicar, o mesmo evento da mesma companhia pesa duas ou mais vezes
  nas estimativas pontuais: nas taxas por faixa do T1 e na AUC agregada.
  Agrupar por companhia corrige o erro-padrão, não o peso.
- O peso extra cai sobre quem arquiva tarde ou reapresenta, comportamento
  plausivelmente ligado à situação da companhia.
- A maior D é a informação mais recente, sempre anterior a q1, e não usa
  desfecho.

**Acréscimo à proposta: a ordem.** A escolha é feita sobre a grade, antes de
janela, elegibilidade e censura por observação. Se a observação escolhida cair,
a chave se perde e não é reposta. O motivo principal: se a escolha viesse
depois da elegibilidade, uma companhia com TTM ≤ 0 na maior D voltaria à
amostra pela data anterior, com informação velha que a mostrava positiva.
Voltariam justamente as companhias que já começaram a consumir caixa, o que
contamina o "início" do evento. Por coerência, a censura também não repõe: a
reposição trocaria a observação por outra com informação mais velha, que é o
que o §2.1 evita no rótulo.

**Ordem dos filtros e o O1 (auditoria, M1).** O rascunho mandava publicar "o
número de datas por companhia" junto dos descartes por motivo. Somado, isso
dá o total da grade, e a contagem de `FCO_TTM ≤ 0`, que o O1 manda omitir,
sairia por subtração. O canal nasceu desta decisão. O texto agora:
- fixa a ordem dos doze motivos: estruturais primeiro, elegibilidade por
  último;
- publica, antes do congelamento, só as observações finais por companhia e
  os demais motivos, sem o total da grade;
- exige a contraprova de que o artefato não permite recompor a contagem por
  aritmética exata.

## §8.1 — Suporte e precisão de T2: piso de 30 e zona cinzenta

**Conferido.** `teste_t2` hoje decide com uma única companhia com os dois
rótulos. O bootstrap do T1 reamostra companhias inteiras, com semente fixa.
`_intervalo` exige 40 reamostragens válidas.

**Julgamento.**
- O piso afasta o caso degenerado, mas não dá precisão: o erro-padrão da AUC
  intra pode chegar a 0,5/√30 ≈ 0,091, da ordem do próprio limiar.
- O projeto já decidiu que passar raspando não é aprovação (§4.4 e zona
  cinzenta do T1), mas o T2 não tinha proteção equivalente.
- A falha que o T2 existe para pegar é o sinal que só ordena emissores. É a que
  produziria um modelo inútil para Value Investing: acerta quais companhias,
  não quando.
- A zona cinzenta só pesa perto do limiar ou com suporte pequeno. Ela usa os
  mesmos 2.000 e 10% do T1, que são política e não calibração.
- Ao contrário do T1, ela vale para toda lacuna abaixo de 0,12. A faixa do T1
  existe porque a amplitude tem viés para cima; a lacuna não tem viés conhecido
  que dispense o bootstrap longe do limiar.
- Foi decidida às cegas: nenhuma lacuna, AUC ou contagem de companhias com os
  dois rótulos foi calculada.

**Especificação do bootstrap (auditoria, M4).** Fixado antes de medir:
- o piso de 30 vale para a amostra original, não para cada reamostragem. Com
  cerca de 30 companhias de dois rótulos, uma reamostragem traz uns 19 nomes
  distintos, e o piso por reamostragem jogaria o T2 em INDECIDÍVEL quase
  sempre;
- a frequência é calculada sobre as reamostragens válidas, como no T1;
- a semente é `20260911`, com as companhias ordenadas por `cd_cvm` antes do
  sorteio, porque o executor v2 é código novo e a ordem de entrada não é
  garantida.

**Custo, declarado.** T2 pode sair INDECIDÍVEL, e a rodada não chega a PRONTO
PARA CHALLENGER. O limiar 0,12 continua o da v1. O vocabulário do §10 ganha
os três casos de INDECIDÍVEL do §8.1: suporte abaixo de 30, menos de 40
reamostragens válidas e frequência acima de 10%.

## §12-bis — Alcance da prova: opção B, com as condições da correção por conta

**Julgamento.** As consequências são assimétricas:
- correção errada do FCO corrompe em silêncio o rótulo e cinco dos seis
  componentes;
- correção que falta deixa o G0 reprovado, de modo visível.

B erra do lado visível. A premissa de A (a escala verdadeira é uma só por
formulário) é plausível, mas não foi testada, e o projeto já recusou estender
escala por premissa não testada (lote C, S5). A extensão ao "decidido" do G0.5
fecha a porta pela qual a premissa voltaria.

**Acréscimo à proposta: três condições para qualquer correção por conta.**
Correção só do ativo desfaz um cancelamento que hoje protege a razão:
- num documento com escala declarada errada, ativo e FCO estão errados pelo
  mesmo fator, e `fco_ttm_sobre_ativo` sai certa;
- corrigido o ativo e não o FCO, a razão sai mil vezes errada.

O contrato que criar correção por conta tem de, antes de aplicar a primeira
linha:
1. fechar o esquema do manifesto no produtor e no consumidor;
2. ler o G0.3 pela escala aplicada ao ativo e o G0.5 pela aplicada ao FCO;
3. aplicar a regra 3 do §5.5 com as escalas lidas por conta:
   `fco_ttm_sobre_ativo` ausente quando a escala aplicada ao ativo em D
   diferir da aplicada ao FCO de algum documento do TTM e um dos dois lados
   não tiver veredito para a própria conta.

Depois da auditoria, a regra 3 do §5.5 vale sempre, com ou sem correção. Com
correção por conta, ela passa a ser a guarda principal da razão.

**Por que isso importa para o treino.** Com as três condições, a correção por
conta é o caminho válido mais curto até o G0:
- provas do ativo, cada uma pela própria célula, reduzem o G0.3;
- o FCO continua na escala declarada, e o G0.5 censura a heterogeneidade dele;
- corrigir um trecho de um documento só, entre vizinhos certos, tira dois
  saltos (entrada e saída).

Ir de 132 para 112 saltos exige, portanto, **pelo menos** da ordem de dez
trechos assim, e mais se a correção cair em trechos longos. O gargalo medido é
a prova, não a regra: a v4 não certificou nenhuma tabela nos 405 documentos, e
a GEOM-1 demonstrou o ativo de um documento. O conjunto a adjudicar tem de ser
fixado antes, e todo resultado aceito, inclusive "indecidível" e "a declaração
estava certa" (§4.4, regra 9).

## O1 — adendo aprovado, com um esclarecimento

**Exceção protetiva: aprovada, nas nove cláusulas da proposta.** Os três
ajustes:
- a cláusula 1 vale para toda execução cujo contrato autorize ler FCO para
  igualdade, não só para a busca GEOM-1;
- a mensagem de recusa, além de não ter dígitos, não diz qual forma
  coincidiu;
- toda execução que invoque o adendo o fixa por hash.

**Julgamento.** As operações são módulo, piso e teto de um valor do próprio
documento, sem sinal, sem agregação e sem janela futura; não informam nada
sobre `Y`. Recusá-las enfraqueceria o O1.3 exatamente na forma mais provável
de vazamento: o FCO arredondado a milhares nas notas. O canal que sobra é a
recusa, que revela no máximo um bit e encerra a execução.

**Esclarecimento (novo): identidade contábil com saída booleana.** O
`MEMORY.md` e o relatório de alcance de 24/09 dizem que o O1 veda a identidade
interna da DFC porque ela "soma o FCO". Mas o O1.2 lista "identidades
contábeis" entre as contagens permitidas, e o construtor do painel de pesquisa
já conta fechamentos da DFC com a `6.01`. A contradição fica resolvida assim:
- verificar uma identidade contábil entre valores declarados no mesmo
  documento e período (um total contra a soma das parcelas, ou dois totais
  que a norma iguala ou manda conciliar) é igualdade entre declarações da
  mesma fonte;
- é permitido com saída só booleana por documento, sem valor, resíduo, sinal
  ou magnitude;
- a lista de identidades é fechada pelo contrato antes de ler;
- a tolerância é absoluta, em unidades do valor bruto, nunca proporcional ao
  FCO; tolerância relativa faria o booleano carregar a magnitude;
- vale a mesma trava contra uso como oráculo da parte 1: nada muda depois de
  vistos os booleanos, salvo contrato novo.

As três últimas condições vieram da auditoria (B4).

Usar essa identidade como elo de prova de escala do FCO continua exigindo
contrato próprio e teste fora dos documentos de desenho (§12-bis). O
esclarecimento abre a rota; não a executa.

## Condição transversal e o caminho até o treino

Aprovar estas decisões **não** é congelar o v2. Os pins atuais (digest
`6ca635a9…`, manifesto `13520e61…`) descrevem um painel em que G0 já se sabe
reprovado: 132 saltos, limite 112. Congelar com eles consumiria o v2 com o
veredito conhecido, como aconteceu com a v1.

O que falta, em ordem:
1. **Contrato da correção por conta** (§12-bis, condições 1–3), com código,
   contraprovas sintéticas e auditor independente.
2. **Contrato da rota de prova**, pré-registrado antes de ler: o conjunto a
   adjudicar e a regra, com teste fora dos documentos de desenho. Prova do
   ativo pela própria célula; prova do FCO pela cadeia ativo → identidade do
   balanço → caixa do balanço igual ao saldo final da DFC → fechamento da DFC,
   como esclarecido acima.
3. **Painel novo, com pins novos,** e G0 medido sem rótulo.
4. **Executor v2:** contrato, implementação, testes sintéticos e conferência
   independente, em paralelo com os itens 1 a 3.
5. **Congelamento, por ato explícito do responsável:** título e nome do
   arquivo sem RASCUNHO, SHA-256 publicado.
6. **Medição:** G0/G1 sem rótulo e, só se aprovarem, `y`, T1, T2 e baselines.
7. **Protocolo do desafiante (D8)** e treino, só em PRONTO PARA CHALLENGER.

**Expectativa honesta.** A previsão registrada no §1, anterior a qualquer
número, é que T1 **reprove** pelo componente `fco_ttm_sobre_sd8`. Se isso se
confirmar, o veredito é REJEITADO, não há terceira tentativa com o mesmo
formato e nenhum modelo sai do Rank 3-B. Nada nestas decisões muda essa
previsão nem foi escolhido para evitá-la.

## Auditoria da onda (27/09)

O `auditor-conformidade`, somente leitura e em contexto próprio, conferiu a
onda de 26/09 e deu **APTA COM RESSALVAS**. Nenhum achado mudou a opção
escolhida em nenhum item, mas M1, M3, M4 e B2 alteraram ou acrescentaram
regras. Cada achado foi conferido na fonte antes de ser tratado.

| Achado | O que era | Tratamento |
|---|---|---|
| **A1** (ALTA) | O §11.7 dizia que a busca de alcance de 24/09 leu FCO; não leu. Omitia a primeira execução da R3, feita sem contrato, e a conferência de 25/09. O §11.1 não declarava que as decisões de 26/09 conheciam a taxa-base | §11.7 reescrito com a cronologia verificada e com o contrato da revisão entre as fontes; ressalva datada no próprio item; §11.1 completado |
| **M1** (MÉDIA) | Publicar "datas por companhia" com os descartes por motivo recompunha, por subtração, a contagem que o O1 manda omitir | §6.1: ordem fixa dos doze motivos; antes do congelamento, sem o total da grade; contraprova aritmética |
| **M2** (MÉDIA) | O rascunho deixou de dizer quem aprova o congelamento | Congelamento exige ato explícito do responsável; a delegação de 26/09 não o cobre (rascunho, este registro, `MEMORY.md`, `AGENTS.md`) |
| **M3** (MÉDIA) | A regra 1 do §5.5 comparava "declarada ou aplicada"; a frase de abertura, só a aplicada | As três regras comparam a escala aplicada ao FCO, com o motivo; duas contraprovas; aviso sobre `documentos_decididos` |
| **M4** (MÉDIA) | Bootstrap do T2 sem piso por reamostragem, denominador, semente e ordem definidos | Piso só na amostra original; frequência sobre as válidas; semente `20260911`; companhias ordenadas por `cd_cvm` |
| **B1** (BAIXA) | O teto de perda só vale sem correções, e o `MEMORY.md` perdeu a ressalva | Ressalva no rascunho, aqui e no `MEMORY.md` |
| **B2** (BAIXA) | O ativo em D, escolhido fora da janela, podia estragar `fco_ttm_sobre_ativo` sem censura nenhuma | Regra 3 do §5.5, que vale sempre |
| **B3** (BAIXA) | "Ocupa o seu lugar" só para o estado do §5.5, sem justificativa, e sem contraprova de q1 | Justificado (valor recusado × valor ausente); `conflito_de_declaracoes` declarado como limite; contraprova de q1 |
| **B4** (BAIXA) | Parte 2 do adendo com lista aberta, tolerância sem forma e sem trava de oráculo; ambiguidade sobre o ÷1.000 | Lista fechada pelo contrato; tolerância absoluta; trava de oráculo; frase sobre o ÷1.000 |
| **B5** (BAIXA) | Ponteiros e paráfrases: `AGENTS.md` mais estrito que o rascunho; becos sem "por delegação"; seções omitidas aqui; §13 com pin ambíguo; hash do adendo não publicado | Corrigidos; hash publicado em "Versões de 27/09", abaixo |

A primeira redação do §6.1 dizia que a reposição "seria deslocamento (§2.1)".
O auditor observou que isso estica o §2.1, que trata do rótulo. A regra se
sustenta pelo motivo da elegibilidade, e o texto foi ajustado.

### Reconferência (27/09)

O mesmo auditor reconferiu e deu **FECHADO COM RESSALVAS**: os dez achados
fechados, com o hash do adendo pendente. As correções tinham introduzido
quatro erros novos, todos BAIXA e só de texto, conferidos na fonte e
tratados:

| Achado | O que era | Tratamento |
|---|---|---|
| **N1** | O §11.7 corrigido ainda generalizava três pontos: dava como não inventariadas as conferências da RAG; não nomeava a autoverificação da primeira execução, que relê o FCO; e estendia "por módulo, nas formas" à primeira R3, cujo método não está documentado | Os quatro pareceres da RAG dizem que nenhuma conferência leu FCO, e o texto diz isso. A autoverificação foi nomeada, e a primeira R3 qualificada. O parecer da auditoria da revisão de 25/09 não está arquivado, o que fica declarado |
| **N2** | A justificativa de "ocupa o seu lugar" omitia o estado `ambiguo_exercicio` | Declarado como limite, junto do `conflito_de_declaracoes` |
| **N3** | "Nenhum achado mudou uma decisão" exagerava | Trocado aqui pela formulação exata |
| **N4** | As revisões de 27/09 não estavam datadas nos próprios textos | Nota de revisão no adendo, com o registro de que nenhuma execução fixou a versão de 26/09; nota no cabeçalho do rascunho; títulos dos §§5.5, 6.1, 8.1 e do alcance da prova com "revisado em 27/09" |

Também foram tratados três resíduos:
- a frase do §5.5 que dizia que "as três regras" comparam a escala do FCO,
  quando a regra 3 compara ativo com FCO;
- a declaração no §6.1 de que o critério "exata" é proposital, com o limite
  superior aproximado que continua dedutível e a proibição de calculá-lo
  antes do congelamento;
- duas paráfrases antigas no `MEMORY.md`.

### Conferência final (27/09)

**FECHADO COM RESSALVAS.** N1 a N4, os resíduos e o B5 estão fechados, e os
hashes conferem. Ficaram três ajustes de redação, todos aplicados como
apontados:
- no §6.1, "dessa contagem" passou a nomear a contagem do motivo 11;
- a abertura do §11.7 agora se restringe às execuções que leram FCO e cobre
  a comparação com a saída publicada;
- a linha do §5.5 no resumo e o item M3 deste registro passaram a distinguir
  as regras 1 e 2 da regra 3.

Nenhum dos três toca o adendo, cujo hash abaixo continua valendo.

## Versões de 27/09

- **Adendo ao O1** (`resultados/adendo_o1_rank03b_2026-09-26.md`), versão
  vigente: SHA-256 `7f51ab27aff2604e8ec2b3a46f7e39cc12dd8aa82d52a44b2bb47dd158414b0f`. É este hash que a primeira execução que invocar o
  adendo fixa (cláusula 8). A versão de 26/09 (`a41ed948…`) nunca foi fixada
  por execução nenhuma nem commitada.
- O rascunho v2 continua rascunho, e o hash dele muda a cada edição até o
  congelamento. Por isso não é fixado aqui.

