# Revisão independente — B-DFC-01J: o veto ao treino e as condições de reabertura

**Data:** 2026-09-10. **Natureza:** revisão de evidências e código, não implementação.
**Pedido:** procurar erros ou condições legítimas que permitam reconsiderar o treino.
**Resultado:** há erros materiais no instrumento de validação e uma fonte documental
promissora que não foi explorada pelo extrator. **Isso reabre a investigação, não
autoriza treinar o J atual nem demonstra utilidade de ML ou incrementalidade da DFC.**

## 1. Parecer executivo

O diagnóstico correto não é “o modelo perdeu” nem “J limpo não existe”. É:

> A construção atual de J não demonstrou limites válidos; o horizonte implementado
> não é o acordado; o cálculo de poder não mede a comparação pretendida. Há notas
> que permitem identificar juros separadamente de câmbio em uma família de passivos,
> mas ainda falta uma série conciliada, point-in-time, e a comparação M0/M1.

Consequências práticas:

1. **Manter a suspensão do treino desta implementação.** G0 não está demonstrado
   como resolvido, apesar de o programa devolver aprovação.
2. **Retirar o caráter conclusivo de impossibilidade** das alegações sobre G2,
   quantidade necessária de bancos e ausência universal de divulgação.
3. **Admitir uma próxima etapa documental e de correção do protocolo**, começando
   pela movimentação de dívidas subordinadas. É uma família econômica definida,
   não uma seleção de rubricas que pareceram fáceis de prever.
4. **Não consumir o holdout 2T2026**, não reincluir câmbio em juros, não aumentar
   tolerâncias para aprovar os resultados existentes e não herdar seus números
   como validação de um candidato reformulado.

O parecer estatístico independente convergiu com a revisão principal. A parte
contábil foi conferida diretamente nos PDFs locais; depois do parecer cego, o
revisor também reproduziu os dois contraexemplos de limites e conferiu as três
âncoras de subordinadas em réplica mediada. Não houve dois especialistas
financeiros independentes adjudicando cada nova célula: essa conferência continua
sendo trabalho da próxima etapa, não uma aprovação implícita deste relatório.

## 2. Escopo, fontes locais e verificações

Foram lidos AGENTS.md e MEMORY.md integralmente; contrato do debate, pré-registro,
dossiê e relatório de prontidão; auditor e sensibilidade completos; construção de
J, derivações, vintages e identidades do extrator; testes e artefatos pertinentes.
As referências abaixo são os documentos auditados, **não fontes de autoridade
independentes para suas próprias conclusões**:

- [Debate e contrato financeiro](debate_bancos_dfc_2026-09-09.md), §§3 e 5–6.
- [Pré-registro](pre_registro_b_dfc_01j_modelo_2026-09-09.md), §§2–7.
- [Dossiê de revisão](dossie_revisao_b_dfc_01j_2026-09-10.md), especialmente R1–R8.
- [Prontidão](prontidao_b_dfc_01j_modelo_2026-09-09.md), §§2-bis e 5–9.
- [Extrator](../scripts/piloto_bancos_dfc.py), funções `construir_j`,
  `derivar_trimestre`, `conferir_identidade_trimestral` e `executar_extensao`.
- [Auditor](../scripts/auditar_prontidao_b_dfc_01j.py) e
  [sensibilidade](../scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py).
- [Gates gravados](../artefatos/b_dfc_01j/prontidao/gates.json),
  [sensibilidade gravada](../artefatos/b_dfc_01j/prontidao/sensibilidade.json),
  [manifesto](../artefatos/b_dfc_01j/extensao/manifesto_extensao.csv),
  [J por período](../artefatos/b_dfc_01j/extensao/j_por_periodo.jsonl),
  [fatos](../artefatos/b_dfc_01j/extensao/fatos.jsonl) e
  [conferências](../artefatos/b_dfc_01j/extensao/conferencias.jsonl).

**Reprodução:** `executar()` do auditor e da sensibilidade, chamados em memória,
reproduziram exatamente seus JSONs atuais. Os três arquivos de testes específicos
passaram: **142 passed, 36,80 s**, sem skips. O revisor independente também rodou
os 17 testes de prontidão. A suíte completa de 1.938 casos **não foi reexecutada**
nesta revisão; esse número é do trabalho anterior.

Não foram alterados código, testes, dependências, PDFs, painéis ou artefatos de
gates. Nenhum modelo foi treinado, nenhuma API paga foi utilizada e o holdout não
foi acessado. As alterações desta revisão se limitam a este relatório e MEMORY.md.
O worktree já continha alterações do usuário: não foram revertidas nem commitadas.

## 3. Achados prioritários

P1 significa que o achado compromete a conclusão ou o contrato do experimento;
P2 significa erro adicional relevante, sem inversão demonstrada do veto atual.

### F1 — P1: os “limites” de J não são limites demonstrados

**Fonte:** extrator, `construir_j`, linhas 1492–1625, especialmente 1595 e 1619.

O código soma parcelas incluídas, `S`, e residual líquido desconhecido, `U`, e
declara J entre `min(S,S+U)` e `max(S,S+U)`. Isso exige que a parcela de juros
desconhecida esteja entre zero e o residual líquido. Essa hipótese não decorre de
uma linha que mistura juros e variação cambial, pois o câmbio pode ter ambos os
sinais e compensar juros.

**Contraprova sintética executada na função real, não estimativa de um banco:**

| Item | Valor com sinal da fonte |
|---|---:|
| Juros incluídos | −100 |
| Rubrica desconhecida | +30 |
| Total declarado | −70 |

O programa fecha a nota e declara intervalo **[70, 100]**. Entretanto, a rubrica
desconhecida pode ser **−20 de juros + 50 de ganho cambial = +30**. Nesse caso,
os juros do contrato são **120**, fora do intervalo. O fechamento continua exato.

Uma segunda contraprova usa duas rubricas desconhecidas, +30 e −30. Como seu
residual líquido é zero, o programa declara **`identificado`, [100,100]**. Elas
podem conter juros de 20 e 10, respectivamente, compensados por câmbio; J seria
130. **Residual líquido nulo não significa ausência de componente desconhecido.**

**Impacto:** classificar a rubrica problemática como desconhecida é cautela
adequada; tratá-la automaticamente como intervalo finito não é. Reclassificá-la
retira o alerta das rubricas incluídas e faz G0 passar sem provar a validade dos
limites. A interpretação de G2, os centros usados como rótulo e a seleção por
largura herdam esse problema. Não basta ordenar os extremos ou usar `abs`.

**Correção necessária, não executada:** limites por componente com hipóteses
documentadas; sem limites demonstráveis, estado não identificado, não ponto nem
intervalo fabricado. A ausência de crédito nas parcelas restantes também não é
certificado positivo de sua natureza contábil.

### F2 — P1: os 18 pares aceitos por G1 não respeitam o horizonte acordado

**Fontes:** debate, linhas 62–64; auditor, `montar_alvos` (169–194) e
`gate_g1` (238–258); manifesto e alvos reproduzidos em memória.

O contrato exige o **primeiro trimestre inteiro cujo início seja posterior à data
de decisão D**. O código usa simplesmente o trimestre seguinte a J-base e verifica
se a divulgação da base antecede a divulgação do resultado futuro.

Exemplo real: Bradesco 2024T1 ficou disponível em **02/05/2024**; o código escolhe
2024T2, que começou em **01/04/2024**. Pelo contrato, q(D) seria **2024T3**.
**Todos os 18/18 pares que G1 considera certificados têm o trimestre-alvo já
iniciado quando a base se torna pública.** Os demais sete pares carecem de datas
completas; corrigi-las não conserta o horizonte dos primeiros 18.

Isso não prova que prever o restante do trimestre seja ilegítimo. Seria outra
tarefa, de previsão do trimestre em andamento, com outra data de corte e avaliação.
Também não basta ordenar datas dos dois J: a disponibilidade de **cada preditor,
operando e alvo histórico usado no treino** deve ser anterior a D.

**Consequência:** o 72% atual mede ordenação das publicações, não cumprimento do
contrato prospectivo. O novo protocolo precisa explicitar D, q(D), o J-base
conhecido em D e o que significa crescimento quando há um trimestre intermediário.

### F3 — P1: G3 não estima poder para detectar melhoria entre previsores

**Fontes:** auditor, `gate_g3`, linhas 351–482, especialmente 389–405 e 423;
debate, linhas 243–249; sensibilidade que reutiliza essa função.

O auditor reamostra **médias dos erros de um baseline entre bancos**, calcula seu
erro-padrão e transforma `2,8 × SE` em melhoria mínima detectável. A quantidade
relevante para uma comparação pareada é a diferença de perdas:

```text
d(i,t) = |y(i,t) − previsão_baseline(i,t)| − |y(i,t) − previsão_modelo(i,t)|
Var(d) = Var(L_baseline) + Var(L_modelo) − 2 Cov(L_baseline, L_modelo)
```

A dispersão de `L_baseline` sozinha não determina essa variância. Um planejamento
antes do treino precisa de hipóteses explícitas ou simulações para o ganho pareado,
não de uma igualdade implícita entre as duas quantidades.

**Contraprova do revisor independente:** três bancos com a mesma trajetória de
erros dão melhoria detectável **zero**, “emissores necessários” **zero** e aprovação,
mesmo compartilhando choque temporal. No sentido oposto, níveis diferentes de
dificuldade entre bancos podem inflar a conta apesar de um ganho pareado estável.

O debate permitia **blocos temporais conjuntos para os bancos fixos**. O pré-registro
substituiu essa possibilidade pela tese de que apenas o número de bancos acrescenta
informação. Não se deve tratar trimestres como independentes, mas tampouco concluir
que toda série temporal equivale a uma única observação para qualquer pergunta.
Inferência por clusters requer hipóteses sobre dependência e quantidade de grupos;
atingir três grupos não a torna automaticamente confiável. Ver a discussão de
poucos grupos e dependência multidimensional em
[Cameron e Miller, seção VI](https://cameron.econ.ucdavis.edu/research/Cameron_Miller_JHR_2015_February.pdf).

**Impacto:** “130,6%”, “~128/~60/~16 emissores” não sustentam o poder de detectar
ganho pretendido. Não há, por outro lado, prova de poder suficiente hoje. É legítimo
redesenhar a inferência para previsões futuras dos bancos fixos, sem anunciar
generalização para outros emissores nem garantir que a janela existente baste.

### F4 — P1: o próprio pré-registro manda invalidar esta rodada

**Fontes:** pré-registro, §7, linhas 167–177; auditor, identificação em 677–683;
relatório de prontidão, reclassificação de 10/09.

O §7 determina invalidação se uma correção de J alterar `y` já medido. A
reclassificação e a guarda de derivação alteraram intervalos, centros e população
após a primeira medição. O artefato continua apontando o mesmo pré-registro.

Há ainda divergência entre o debate e o protocolo: o debate pediu auditoria própria
de regressão, sem herdar T1/T2; o pré-registro criou um companheiro binário para
reutilizar os limiares 0,15/0,12. O piso de 20% foi transportado de economia de
leitura humana para redução de MAE, sem uma ponte econômica demonstrada.

**Impacto:** as rodadas corrigidas são diagnósticos úteis e reproduzíveis, mas não
execução intacta daquele pré-registro. Uma revisão exige versão nova e reserva de
avaliação ainda não usada. Não se apaga o resultado anterior nem se muda sua barra
retroativamente. Nenhum destes achados afirma que os limiares foram deliberadamente
escolhidos para produzir reprovação.

### F5 — P1: a prova contábil apresentada não demonstra não separabilidade universal

**Fontes:** dossiê, §§4 e 5.2–5.4; prontidão, §2-bis; notas 17b, 17c e 21b
do Itaú 2020T1, já usadas e referenciadas nesses relatórios.

A revisão confirma indícios de mistura que exigem cautela, mas encontra três
saltos na justificativa:

- O limite de aproximadamente R$ 2 bi usa **84.051 milhões e a taxa de uma
  subcategoria** para confrontar a despesa de todo o agregado de **188.134 milhões**.
  Saldo final tampouco demonstra saldo médio ou exposição máxima no período.
- O aumento de estoque de 19.429 é **2019T4 → 2020T1**; o aumento de despesa de
  21.119 é **2019T1 → 2020T1**. São janelas diferentes. Além disso, variação de
  estoque não é câmbio puro sem decompor emissões, pagamentos e demais movimentos.
  “Casam em 8%” não é uma conciliação, independentemente de ser pós-hoc.
- As três linhas da DFC citadas como juros e câmbio não identificam a contribuição
  cambial da rubrica interbancária: uma trata de dívida subordinada e duas de ativos.
  No Bradesco, exposição em investimentos no exterior também não identifica por si
  a causa de crédito em **empréstimos/repasses recebidos**.

Portanto, **não reincluir as rubricas no J**: falta prova para aprová-las. Mas também
não usar esses argumentos para afirmar que todas as famílias e bancos carecem de
separação ou que coletar notas adicionais não pode ajudar. A seção 4 traz evidência
positiva concreta, com suas próprias ressalvas.

### F6 — P2: crédito no trimestre é alerta, não diagnóstico automático de câmbio

**Fonte:** extrator, `derivar_trimestre`, linhas 1730–1759; dossiê, R5.

Recusar a derivação enquanto a comparabilidade não foi adjudicada é prudente.
Entretanto, dizer que acumulado menor “não é diferença de nada” é excessivo:
reversões e revisões contábeis existem. A IAS 34 descreve alterações de estimativas
no acumulado e seu reconhecimento posterior, inclusive reversões em certos casos;
isso **não identifica a causa desta rubrica bancária específica**.
[IAS 34, §§26 e 28–30](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2021/issued/part-a/ias-34-interim-financial-reporting.pdf).

A guarda também não certifica os casos que passam: reclassificação pode ocorrer
sem troca de sinal. Ampliá-la para rejeitar todo encolhimento seria seleção por
resultado. A saída é adjudicar política, perímetro, reapresentação e natureza da
reversão; separar “diferença aritmética calculável” de “trimestre comparável”.
Para o alvo log, J não positivo exige regra própria declarada antes da avaliação.

### F7 — P2: T1 cria associação usando o próprio rótulo no desempate

**Fonte:** auditor, `amplitude_por_quintis`, linha 498.

```python
amplitude_por_quintis([1.0] * 50, [0, 1] * 25)
# amplitude = 1.0; taxas dos quintis = [0, 0, 0.5, 1, 1]
```

`sorted(zip(valores, eventos))` desempata por `eventos`. Uma variável constante
recebe associação máxima. Essa contraprova foi reproduzida por ambos os revisores.
O problema não decide a rodada atual, pois T1 já não dispõe de amostra mínima;
precisa ser corrigido antes de voltar a usar o teste. Mesmo corrigido, T1 sobre
J futuro não decide se uma previsão contínua é útil; o relatório anterior já
reconhecia esse defeito conceitual.

### F8 — P2: unidade de J incorreta no JSON e descartada no auditor

**Fontes:** extrator, `ResultadoJ.para_json`, linha 1478; auditor, carregamento em
128–143 e componentes de T1 em 525; cruzamento J/fatos pela fonte.

Há **90/198 registros de J** cuja unidade declarada como milhares diverge dos
fatos do Itaú, em milhões. O valor numérico continua na unidade da publicação.
O auditor não conserva a unidade e combina J bruto nos quintis entre bancos.

A log-razão cancela uma escala constante dentro do banco: **não foi demonstrado
erro de mil vezes em `y` ou no MAE atual**. Já T1 transversal e exportações monetárias
ficam incorretos. A contraprova independente, sem empates, mudou amplitude de 1
para 0 apenas harmonizando unidades. Na população histórica reconstruída, não
foi demonstrada inversão do veredito por esse defeito isolado.

### F9 — P2: B2 não é a mediana dos quatro trimestres anteriores

**Fontes:** auditor, `previsoes_dos_baselines`, linhas 296–327; eleição em 383.

B2 usa até quatro **linhas disponíveis** e aceita menos de quatro; não verifica
continuidade trimestral. Na contraprova com 2020T1=0,5 e 2024T1=0,2, usa 0,5
para prever 2024T1. Na população vigente há seis previsões com apenas um a três
antecedentes e seis usos de antecedentes sem disponibilidade certificada.

Os históricos são montados a partir da lista de alvos já filtrada, que depende
também da qualidade do J futuro. Isso exige distinguir elegibilidade em D de
disponibilidade posterior do rótulo. Uma população condicionada à mensurabilidade
futura pode ser analisada, mas não representar silenciosamente toda a fila de
decisões. Preditores devem ser reconstruídos com o que era conhecido em D.

Além disso, a eleição compara erros em suportes diferentes. Contraprova independente:
B0 tem MAE 7 nas nove observações e B1 tem 2 nas três em que existe; o programa
escolhe B1, embora B0 tenha MAE 1 nessas mesmas três.

**Reprodução real atual:** B0 ainda é menor também no suporte comum; não houve
inversão real demonstrada. Isso não significa vitória sobre um modelo não treinado.

| Baseline | MAE macro, suporte próprio | n | MAE macro, interseção comum n=17 |
|---|---:|---:|---:|
| B0 | 0,0709054 | 25 | 0,0645197 |
| B1 | 0,1000608 | 17 | 0,1000608 |
| B2 | 0,0774362 | 23 | 0,0674177 |

Os 0,1579 / 0,2151 / 0,1771 do dossiê, linha 512, não descrevem a população
vigente e precisam de etiqueta do cenário anterior. “O trivial ganha pela sétima
vez” não é resultado de uma comparação entre baseline e ML nesta rodada.

### F10 — P2: T2 não informativo e B3 ausente não bloqueiam a aprovação em código

**Fontes:** auditor, T2 em 627–650, B3 em 466 e veredito em 790–795.

Com escores `-y`, a contraprova independente produz AUC agregada e intra iguais
a zero, `informativo=False` e **`aprovado=True`**. A ressalva existe; a trava não.
O teste atual verifica a ressalva, não essa aprovação contraditória.

B3 é obrigatório no pré-registro, mas sua ausência só aparece como texto. Não
participa da condição de aprovação de G3 ou do veredito final. São permissões
falsas latentes: **não liberaram a rodada atual**, que falha por outros motivos.

A meta Selic tem fonte pública oficial: série diária SGS 432, com recursos JSON/CSV.
Portanto, “B3 não implementado” não equivale a “só existe dado pago”. O catálogo
foi consultado; a série não foi integrada nem validada nesta revisão.
[Catálogo BCB — SGS 432](https://dadosabertos.bcb.gov.br/dataset/432-taxa-de-juros---meta-selic-definida-pelo-copom).
Para uma família de dívida, Selic isolada pode ser benchmark insuficiente: moeda,
indexador, estoque e calendário precisam corresponder aos instrumentos, sem usar
taxas realizadas futuras nem alterar o benchmark após ver o ganho de ML.

### F11 — P2: “15/15 identidades anuais” não é o certificado que o artefato contém

**Fontes:** prontidão, §6.1; extrator, `conferir_identidade_trimestral`, linha 2839;
`extensao/conferencias.jsonl`.

O arquivo atual contém:

| Identidade | `confere=True` | `confere=None` |
|---|---:|---:|
| T1+T2 = S1 | 12 | 5 |
| T1+T2+T3 = M9 | 12 | 5 |
| T1+T2+T3+T4 = A | **0** | **17** |

Isso não demonstra que as somas anuais sejam falsas. Demonstra que a certificação
publicada não está nesse artefato sob suas regras de vintage. E uma soma que usa
Q4 definido como `A−M9` não é, sozinha, contraprova independente: `M9+(A−M9)=A`
fecha por construção. É preciso conservar a linhagem e distinguir identidades
independentes de verificações algébricas. Ausência de divergência não prova que
todas as identidades exigidas foram efetivamente verificadas.

### F12 — P1 de interpretação: G2 não mediu “ruído maior que sinal” no sentido alegado

**Fontes:** auditor, `gate_g2`, linha 261; prontidão, §§2-bis.5, 4 e 8.

O **1,0464 reproduz**. É a razão entre a meia-largura mediana propagada para `y`
e a mediana do módulo de seu centro. Não é variância empírica do erro de medição,
nem prova de imprevisibilidade. Sobretudo, os intervalos de entrada não foram
validados (F1). Não há base para interpretar seus centros como verdade medida ou
suas larguras como ruído estatístico identificado.

Mesmo intervalos válidos expressariam identificação parcial, não automaticamente
ruído aleatório independente entre períodos. Dependência das parcelas desconhecidas
pode mudar a incerteza sobre a variação. Um método para rótulos intervalares seria
outra hipótese, com perdas e hipóteses próprias — não conserta limites falsos.

Por fim, CV alto de uma rubrica não mede dificuldade de previsão condicional;
CV baixo não prova vantagem de ML sobre persistência. Escolher alvos por baixo
CV ou ausência de créditos em todo o histórico cria risco de seleção retrospectiva.

## 4. Evidência nova: uma família tem juros e câmbio separados nas notas

### 4.1 Prova positiva delimitada

No Bradesco IFRS **2022T2**, p. **63**, nota **20b**, a movimentação de dívidas
subordinadas separa, em **R$ mil**, os seguintes valores do **primeiro semestre
de 2022**, não do segundo trimestre isolado:

```text
54.451.077 saldo inicial
 8.074.700 emissões
 3.326.725 juros
−11.557.020 liquidação e pagamentos de juros
   −499.780 variação cambial
=53.795.702 saldo final
```

Os **3.326.725** conferem exatamente com a despesa de juros de subordinadas da
nota **27**, p. **79**, coluna acumulada de 2022. A coluna comparativa de 2021
também confere em **1.056.573**, mas **não certifica sozinha o vintage de 2021**.
Fonte: [PDF local](../artefatos/b_dfc_01j/raw/bradesco_2022T2_v1.pdf) e
[arquivo oficial CVM/IPE](https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1003904&numSequencia=528638&numVersao=1).

Não é correto generalizar o êxito a todas as linhas: no mesmo documento, nota
**19c**, p. **62**, juros de títulos emitidos são **9.318.945**, contra **9.489.327**
na nota 27 — diferença **170.382** em R$ mil, **não conciliada** nesta revisão.

### 4.2 Checagem em períodos posteriores — incluindo a divergência

| Documento | Movimentação das subordinadas | DRE/nota 27 | Resultado |
|---|---:|---:|---|
| 2024T1, pp.53/69 | 1.563.818 | 1.563.818 | Confere exato |
| 2025T1, pp.53/69 | 1.963.052 | 1.963.051 | Diferença de **1 em R$ mil**; adjudicar |

Fontes: [Bradesco 2024T1 local](../artefatos/b_dfc_01j/raw/bradesco_2024T1_v1.pdf),
[CVM/IPE 2024T1](https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1231187&numSequencia=755913&numVersao=1);
[Bradesco 2025T1 local](../artefatos/b_dfc_01j/raw/bradesco_2025T1_v1.pdf),
[CVM/IPE 2025T1](https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1373668&numSequencia=898380&numVersao=1).

O saldo fecha na movimentação de ambos os documentos. Isso **não autoriza corrigir
a DRE de 2025 nem presumir arredondamento**; os dois valores e a divergência devem
ser preservados até adjudicação, sob as regras de procedência do projeto.

O marcador de movimentação de subordinadas foi encontrado em **16 dos 18 PDFs
Bradesco do manifesto da extensão**, de 2021A a 2026T1. Os outros dois são os
comunicados de 2019A/2020A já diagnosticados como documentos errados. Essa contagem
é de documentos com seção localizável, **não 16 rótulos independentes, conciliados
e point-in-time**. Só as âncoras acima receberam a conciliação aqui descrita.

### 4.3 Por que esta é uma pista legítima, e seu limite

A IAS 7 prevê divulgação de mudanças em passivos de financiamento, distinguindo
movimentos de caixa e sem caixa, inclusive câmbio, e ligações com balanço, DFC e
notas. Isso motiva procurar a **movimentação do passivo**, não apenas a composição
da despesa. Não se presume que toda captação bancária caia nessa categoria nem que
toda nota forneça a abertura necessária.
[IFRS Interpretations Committee, decisão IAS 7 de setembro de 2019](https://www.ifrs.org/content/dam/ifrs/supporting-implementation/agenda-decisions/2019/ias-7-disclosure-of-changes-in-liabilities-arising-from-financing-activities-september-2019.pdf).

A evidência afasta a generalização “não existe separação em nenhuma família”,
mas **não separa as duas rubricas problemáticas do J total**. Há duas rotas distintas:

- Para preservar J total: investigar pontes documentais para **todas** as famílias;
  uma família reconciliada não supre a parte ainda desconhecida.
- Para um candidato novo: definir economicamente juros de subordinadas IFRS
  classificadas como passivo e auditar sua série inteira, sem selecionar períodos
  por desempenho, sinal ou CV. A decisão de usar essa família ainda exige justificar
  materialidade para o analista e sua relação com a DFC.

**Juros pagos não foram identificados isoladamente nessa tabela:** a linha é
“liquidação e pagamentos de juros”. Não convertê-la em caixa de juros por hipótese.
O estoque aparece na mesma nota; a limitação de mapeamento do painel CVM não impede
em princípio obter esse denominador documental para a família. Uma taxa efetiva,
porém, exigiria justificar estoque médio, emissões, amortizações e duração — não
basta dividir J pelo saldo final.

## 5. Respostas às oito perguntas do dossiê

| Pergunta | Resposta da revisão |
|---|---|
| R1: a reclassificação resolveu G0? | **Não demonstrado.** Retirar a inclusão duvidosa é correto; os limites líquidos adotados não contêm necessariamente J (F1). |
| R2: evidência do Bradesco é suficiente? | **Não para atribuir causalmente a câmbio.** Sustenta investigação e não identificação, não estimativa da parcela cambial (F5–F6). |
| R3: há notas não exploradas? | **Sim.** Movimentação de subordinadas separa juros/câmbio em uma âncora e confere com DRE; não fecha J total (§4). |
| R4: casamento em 8% é significativo? | **Não é conciliação.** Além de pós-hoc, mistura períodos e universos diferentes (F5). |
| R5: ampliar guarda do 4T? | **Não por sinal ou magnitude.** Adjudicar comparabilidade e revisões, preservando a recusa enquanto faltar evidência (F6). |
| R6: muda o veredito? | **Treino imediato continua sem suporte; encerramento definitivo cai.** Agora há erros no auditor e uma rota documental concreta. |
| R7: todos os números reproduzem? | **Não como manchetes do estado atual.** JSONs reproduzem; baselines do texto são antigos e 15/15 anual não está certificado no artefato (F9/F11). |
| R8: reabertura por rubricas sem crédito/baixo CV? | **Critério insuficiente.** Reabrir por família econômica e evidência contábil, não facilidade ex post de previsão (§4/F12). |

## 6. Trabalho necessário antes de considerar treino exploratório

Esta é uma sequência proposta para a próxima tarefa, **não executada nem um novo
pré-registro aprovado**. Não exige que um modelo prove superioridade antes de ser
treinado; exige dado semanticamente mensurável e um experimento capaz de testar a
pergunta que declara fazer.

1. **Corrigir primeiro o instrumento de medição.** Acrescentar contraprovas F1,
   F2, F7–F11 aos testes; corrigir sem enfraquecer asserções existentes. Separar
   certificado semântico de fechamento, valor exato de não identificado, e identidade
   independente de soma por construção. Revisor independente confere a correção.
2. **Piloto documental limitado de subordinadas.** Inventariar os 16 documentos
   localizados e os períodos necessários; conferir política IFRS/passivo, mesma
   família/perímetro, notas/DRE, sinais, escala e disponibilidade. Tratar explicitamente
   2025T1 divergente; não introduzir tolerância para fazê-lo passar. Inventariar
   falhas, não somente sucessos; buscar originais ausentes sem acessar o holdout.
3. **Decidir o estimando antes de nova comparação.** Preservar J total se a
   cobertura exaustiva for demonstrada, ou registrar candidato novo restrito.
   O encargo agregado publicado também era reconhecido como pergunta legítima no
   debate, mas não foi testado nem vira “juros puros” por mudança de nome.
4. **Refazer o relógio do experimento.** Fixar D e q(D); reconstruir todos os
   preditores e históricos pelo vintage disponível em D. Separar falta de futuro
   da elegibilidade da previsão, embargo dos rótulos e mudanças de perímetro.
5. **Construir M0, M1 e benchmark econômico no mesmo suporte.** M0 recebe BP,
   DRE, notas, taxas conhecidas e diferenças de estoques; M1 acrescenta apenas DFC
   definida e rastreável. A movimentação encontrada é nota disponível também a M0:
   não pode ser artificialmente escondida dele para favorecer M1. Hoje o piloto
   classifica **duas linhas DFC do BB 2025T1**; isso não é uma matriz histórica de
   features. Fonte: `classificar_componentes_dfc` e `COMPONENTES_DFC` no extrator.
6. **Registrar materialidade e análise temporal próprias.** Definir utilidade do
   erro em cenários do analista, horizonte, orçamento de complexidade, calibração,
   pioras toleradas e regra de indecisão. Dimensionar diferenças pareadas de perdas,
   com dependência temporal/contemporânea e sensibilidades de blocos. Não trocar
   “~16 bancos” por outro mínimo arbitrário.
7. **Somente então propor treino exploratório offline**, com modelos simples,
   transformações ajustadas apenas no treino, tuning contido em desenvolvimento,
   baselines válidos e registro integral das tentativas. O futuro ainda não usado
   será reservado para confirmação; o 2T2026 permanece intocado nesta sequência.

O benefício exigido continua duplo: **M1 superar M0 e o benchmark econômico**, no
mesmo conjunto de previsões. Se isso não ocorrer, pode haver ferramenta documental
útil sem contribuição demonstrada de ML/DFC. Se faltar informação ou precisão,
o resultado deve ser indecidível, não vitória nem impossibilidade universal.

## 7. Reproduzir esta revisão sem sobrescrever os artefatos

Executar na raiz do repositório. As chamadas em memória abaixo não invocam os
`main()` que gravam JSON. Não usar as CLIs `estender`/`auditar` apenas para revisar:
elas reescrevem artefatos do trabalho anterior.

```bash
.venv/bin/python -m pytest -q tests/test_piloto_bancos_dfc.py tests/test_prontidao_b_dfc_01j.py tests/test_sensibilidade_b_dfc_01j.py --tb=short
```

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from collections import Counter
from datetime import date
from scripts import auditar_prontidao_b_dfc_01j as a
from scripts import sensibilidade_rubricas_suspeitas_b_dfc_01j as s

root = Path('artefatos/b_dfc_01j')
assert a.executar() == json.loads((root/'prontidao/gates.json').read_text())
assert s.executar() == json.loads((root/'prontidao/sensibilidade.json').read_text())
obs, contagem = a.carregar_populacao()
alvos, pares = a.montar_alvos(obs)
print(contagem, pares)
certificados = [x for x in alvos if x.disponivel_base and x.disponivel_alvo
                and x.disponivel_base < x.disponivel_alvo]
def inicio(periodo):
    return date(int(periodo[:4]), 3*(int(periodo[5])-1)+1, 1)
print('alvo já iniciado:', sum(date.fromisoformat(x.disponivel_base)
      >= inicio(x.periodo_alvo) for x in certificados), '/', len(certificados))
print('T1 constante:', a.amplitude_por_quintis([1.0]*50, [0,1]*25))
conferencias = map(json.loads, (root/'extensao/conferencias.jsonl').read_text().splitlines())
print('identidades:', Counter((r['identidade'], r['confere']) for r in conferencias))
PY
```

Para a contraprova de limites, construir três `Fato` sintéticos da mesma fonte,
período e unidade, com tratamentos `incluir`, `nao_identificado`, `total` e valores
−100, +30, −70, respectivamente, e chamar `construir_j`. Resultado observado:
`fechamento_confere=True`, `status=limitado`, limites 70/100. Para cancelamento,
usar desconhecidas +30/−30 e total −100; resultado observado: `identificado`,
100/100. Nenhum desses valores pertence ao painel financeiro real.

```bash
pdftotext -layout -f 63 -l 63 artefatos/b_dfc_01j/raw/bradesco_2022T2_v1.pdf -
pdftotext -layout -f 79 -l 79 artefatos/b_dfc_01j/raw/bradesco_2022T2_v1.pdf -
pdftotext -layout -f 62 -l 62 artefatos/b_dfc_01j/raw/bradesco_2022T2_v1.pdf -
pdftotext -layout -f 53 -l 53 artefatos/b_dfc_01j/raw/bradesco_2024T1_v1.pdf -
pdftotext -layout -f 69 -l 69 artefatos/b_dfc_01j/raw/bradesco_2024T1_v1.pdf -
pdftotext -layout -f 53 -l 53 artefatos/b_dfc_01j/raw/bradesco_2025T1_v1.pdf -
pdftotext -layout -f 69 -l 69 artefatos/b_dfc_01j/raw/bradesco_2025T1_v1.pdf -
```

**Procedência das novas âncoras** — data e protocolo do manifesto, hash medido dos
arquivos locais nesta revisão. Não foi feito novo download para comparar bytes
com a CVM. Os PDFs não são versionados; preservar o manifesto e estes hashes:

| Arquivo | Data de entrega IPE | Protocolo |
|---|---|---|
| bradesco_2022T2_v1.pdf | 2022-08-04 | 000906IPE300620220104477710-98 |
| bradesco_2024T1_v1.pdf | 2024-05-02 | 000906IPE310320240104541403-84 |
| bradesco_2025T1_v1.pdf | 2025-05-07 | 000906IPE310320250168989810-79 |

```text
SHA-256 bradesco_2022T2_v1.pdf
9fcabab97fd1a5b89f327e8564d9884146c8d6d9ead781deefb1b8207d786901
SHA-256 bradesco_2024T1_v1.pdf
a24093bd823acf2435a86d8f82522ce9b4505593dbb567973d151c7fad143591
SHA-256 bradesco_2025T1_v1.pdf
8a25d1958dbd7fd97cef042705415cb1206b6ef9844fe56d7b19235659f1f0ae
```

**Limite final:** este relatório auditou a cadeia que fundamentava o veto e
amostras documentais relevantes; não refez a extração de todas as páginas nem
certificou todos os fatos dos 65 documentos. Os defeitos encontrados bastam para
rever a conclusão forte de encerramento, não para certificar os dados restantes.
