# Contratos e critérios de aceitação — correção C1–C6

**Data:** 2026-09-11. **Escrito ANTES de implementar**, conforme a resposta 3 da
[revisão da conferência](revisao_conferencia_parecer_b_dfc_01j_2026-09-11.md):
*"Registrar os contratos e os testes de aceitação antes da implementação, sem
escolher uma política pelo desempenho observado."*

**Objeto:** os seis contratos abertos pelo
[parecer de 11/09](parecer_correcao_b_dfc_01j_2026-09-11.md) §2.

**O que este documento NÃO é:** não é pré-registro de experimento. Nenhum número
de desempenho é medido, previsto ou herdado aqui. O pré-registro antigo segue
invalidado pela sua própria §7, e **medir desempenho de novo exige protocolo
novo** — isto corrige o instrumento, não reabre a medição.

**Estado de partida** (hashes conferidos contra os do §4 da revisão):
população elegível vazia, G0 reprovado, 198 registros J todos `nao_identificado`.
Nenhuma correção abaixo pode reativar a série; se alguma reativar, é defeito.

---

## Princípio comum às seis

Toda correção obedece à regra do §3.14 do AGENTS.md — **guarda que aprova por
ausência de dado é pior que guarda nenhuma** — e à regra de testes do §2:
**nunca enfraquecer uma asserção para o código passar.** Onde um teste vigente
afirma conclusão invalidada, ele é **substituído por asserção mais forte**, e a
substituição é justificada caso a caso no relatório de implementação.

---

## C1 — política de empates em `amplitude_por_quintis`

**Contrato.** A amplitude mede a capacidade **da variável** de ordenar
observações. Duas observações com valor idêntico são **indistinguíveis pela
variável**: nenhuma política pode colocá-las em quintis diferentes, porque isso
atribui à variável uma ordenação que só existe na fonte do desempate.

**Regra escolhida:** os grupos são formados **por valor**, não por posição. Corta-se
nos limites de quintil, mas cada corte é **estendido até o fim do grupo de
empate**, de modo que um mesmo valor nunca atravessa duas faixas. O resultado tem
**no máximo** cinco faixas e no mínimo uma.

**Casos declarados antes de medir:**

| Entrada | Saída exigida |
|---|---|
| Variável constante (1 valor distinto) | amplitude **0,0** — não é erro, é a medição correta: variável que não ordena nada não fabrica baseline nenhum |
| Menos de 5 valores distintos | amplitude sobre as faixas que existirem, com a contagem de faixas publicada |
| Amostra abaixo de `MINIMO_PARA_QUINTIS` | continua levantando `ReprovaEmAberto` — inalterado |

**Rejeitadas explicitamente:** desempate aleatório (não demonstra invariância,
só a esconde atrás de uma semente) e desempate por posição original (é a política
vigente, e é o defeito — posição carrega emissor e tempo).

**Critérios de aceitação:**

1. constante com rótulos **agrupados** → 0,0 (hoje 1,0)
2. constante com rótulos **alternados** → 0,0 (hoje já 0,0)
3. **invariância a permutação:** variável com empates medida sob ≥20 embaralhamentos
   distintos devolve sempre a **mesma** amplitude
4. **não-regressão:** variável que de fato ordena continua medindo amplitude alta
5. nenhum valor empatado aparece em duas faixas
6. `MINIMO_PARA_QUINTIS` e o limiar 0,15 de T1 **não mudam**

---

## C2 — unidade no consumidor, não só na etiqueta

**Contrato.** Nenhuma aritmética entre registros de J pode ocorrer antes da
conversão a uma **unidade canônica**. Etiquetar a unidade na exportação sem
convertê-la no consumidor deixa o defeito no caminho que será reutilizado.

**Regra escolhida:** `carregar_populacao` converte os limites para **reais**
usando o mesmo `MULTIPLICADOR_UNIDADE` do extrator. Unidade ausente ou fora do
vocabulário **levanta erro** — nunca é suposta.

**Motivo de a canônica ser reais e não "a unidade do emissor":** a série mistura
de verdade — 108 registros em milhares (Bradesco, BB) e 90 em milhões (Itaú).
Os quintis de T1 comparam emissores entre si; sem canônica comum eles comparam
grandezas mil vezes diferentes.

**Critérios de aceitação:**

1. 1.000 milhares e 1 milhão do mesmo emissor → **y = 0,0** (hoje −6,907755…)
2. unidade ausente → erro explícito
3. unidade desconhecida → erro explícito
4. `meia_largura` e o corte de largura **não mudam** (são razões, invariantes à escala)
5. `Observacao` passa a carregar a unidade de origem — procedência preservada,
   não descartada

---

## C3 — horizonte é igualdade com q(D), não "posterior a D"

**Contrato.** `horizonte_contratual_respeitado` só pode devolver `True` para o
**primeiro** trimestre inteiro cujo início é posterior à data em que o J-base
ficou público. Qualquer trimestre mais distante é **outro** horizonte de previsão,
com outra dificuldade — aceitá-lo mistura tarefas.

**Regra escolhida:** calcular `q(D)` explicitamente e exigir
`periodo_alvo == q(D)`. Data de base ausente continua devolvendo `None`.

**Critérios de aceitação,** para D = 02/05/2024 (o caso do parecer):

| Alvo | Hoje | Exigido |
|---|---|---|
| 2024T2 | False | **False** (já começou) |
| 2024T3 | True | **True** (é q(D)) |
| 2024T4 | True | **False** (pulou q(D)) |
| 2025T1 | True | **False** (pulou q(D)) |

Mais: D no primeiro dia de um trimestre e D no último dia — os dois com q(D)
declarado no teste; e G1 reprovando o par fora de q(D).

---

## C4 — disponibilidade dos antecedentes e contagem do que foi usado

**Contrato (parte A — baselines).** B1 e B2 só podem usar antecedente cujo
**resultado já era conhecido** na data de decisão do alvo que estão prevendo.
Antecedente sem data é **inutilizável**, nunca presumido disponível.

- data de decisão do alvo corrente: `disponivel_base`
- data em que o antecedente vira conhecido: o `disponivel_alvo` **dele**
- condição: `antecedente.disponivel_alvo <= alvo.disponivel_base`

**Contrato (parte B — contagem).** `gate_g3` não pode publicar como "emissores
independentes" um número que inclua emissores **ausentes do erro do baseline
eleito**. A contagem publicada tem de ser a das unidades **efetivamente usadas**
na comparação.

**Critérios de aceitação:**

1. reprodução do parecer (4 antecedentes só públicos em 01/01/2025, decisão em
   02/05/2024) → **B1 = None e B2 = None** (hoje 0,2 e 0,5)
2. os mesmos antecedentes com data anterior a D → B1 e B2 **opinam** (não-regressão:
   a guarda não pode zerar tudo)
3. antecedente sem data → não usado
4. subcaso do revisor (3 bancos na população, eleito cobre só A) →
   `emissores_independentes` reflete **1**, não 3
5. `B3_EXECUTADO` continua `False` e continua bloqueando G3

**Declarado como NÃO feito:** reconstruir a população point-in-time. É tarefa de
protocolo novo (§4.3 do pacote de 10/09, confirmado pelo parecer). Esta correção
faz a função **recusar** o que não estava disponível; não refaz a série.

---

## C5 — linhagem de todos os operandos, e contagens separadas

**Contrato.** Uma identidade é **independente** apenas se **nenhum** de seus
operandos for derivado — o acumulado incluído. `T1+T2 = S1` com `S1` derivado de
`T1` e `T2` fecha por construção e não prova mapeamento de coluna nenhum.

**Regra escolhida:** inspecionar `escolhido` inteiro, não `escolhido[:-1]`, e
nomear no motivo **qual** operando é derivado.

**Contrato (parte B — resumo).** O resumo da extensão publica **duas** contagens
distintas: `identidades_conferidas` (fecham aritmeticamente) e
`identidades_conferidas_independentes` (fecham **e** não têm operando derivado).
G0 passa a ler a segunda. Hoje as duas coincidem em 24; o contrato existe para
que uma identidade futura que feche por construção não seja contada como
conferida.

**Critérios de aceitação:**

1. contraprova do parecer (S1 derivado) → `independente=False`, com motivo
   nomeando o operando
2. identidade toda original → `independente=True` (não-regressão)
3. parcela derivada → `independente=False` (comportamento vigente, preservado)
4. resumo traz as duas contagens e **hoje elas são iguais**; se divergirem, o
   artefato mudou e é a divergência que precisa ser explicada

---

## C6 — quarentena explícita do cálculo de poder (F3)

**Contrato.** F3 estabeleceu que a conta de poder reamostra a **dispersão da
perda do baseline eleito**, não a **diferença pareada** entre desafiante e
baseline — que é a quantidade da qual o poder depende. Enquanto não for
redesenhada, **nenhuma saída pode apresentá-la como decidível**.

**Regra escolhida — publicar e invalidar, não apagar.** Segue a recomendação R1
do revisor (*"preferir 'o cálculo continua publicado, mas está invalidado' a
'deixou de existir'"*):

- `clusters_suficientes`: o booleano que `decidivel` significava até aqui, preservado
- `calculo_de_poder_invalidado_por`: `"F3"`, com o motivo por extenso
- `decidivel`: **False em todos os cenários**, porque agora exige clusters
  suficientes **E** cálculo válido — e o cálculo não é válido
- `ressalva`: nunca `None`; nomeia F3, e acrescenta a falta de clusters quando for o caso
- os números (`melhoria_minima_detectavel_relativa`, `emissores_necessarios`)
  **permanecem publicados**, marcados como inválidos

Vale nos **dois** lugares que fazem a conta: `_poder` da sensibilidade e `gate_g3`.

**Critérios de aceitação:**

1. `volatilidade_conforme` → `decidivel=False`, `ressalva` cita F3
   (hoje `True`/`None`/16)
2. `volatilidade_estado_anterior_nao_conforme` → idem (hoje `True`/`None`/60)
3. os valores 16 e 60 **continuam no artefato**, agora marcados
4. `gate_g3` carrega o mesmo marcador
5. `aprovado` de G3 continua `False` e **não passa a depender** do marcador para
   ser False — a exigência de B3 continua bloqueando por si

**Substituição de teste declarada:** `test_sensibilidade_b_dfc_01j.py:157-160`
exige hoje que `emissores_necessarios` caia e permaneça acima de 3 — asserção
sobre quantidade que a revisão invalidou. É **substituída** pela asserção de que
a quantidade sai marcada como inválida. Troca de asserção fraca sobre número sem
validade por asserção forte sobre a marcação; não é afrouxamento.

---

## O que continua fora desta onda

| Item | Por quê |
|---|---|
| Redesenho estatístico do poder (F3 de verdade) | Exige escolher método de poder para ganho pareado — decisão de protocolo, não de instrumento |
| Reconstrução point-in-time da população | Protocolo novo; §4.3 do pacote de 10/09 e C4 do parecer |
| Adjudicação das rubricas do BB (`limite_demonstravel`) | Item 2 da sequência: piloto por família econômica, com leitura de notas |
| Representação de ausência de limites (item 4.2 do parecer) | Exige schema versionado e mudança nos consumidores; contrato próprio |
| Sincronização documental R1 (linha 972, becos, retratações do piloto/extensão) | Onda documental curta, separada; o revisor a recomenda sem esperar o código |
| Qualquer medição de desempenho | Pré-registro antigo invalidado; exige protocolo novo |

---

## Como esta onda pode falhar

1. **Alguma correção reativar a série.** População elegível tem de continuar
   vazia e G0 reprovado. Se J voltar a ter observação elegível, a correção
   fabricou dado.
2. **Os artefatos mudarem.** `gates.json` e `sensibilidade.json` devem mudar
   **apenas** nos campos de quarentena e contagem aqui declarados. Qualquer
   outro campo que mude precisa ser explicado.
3. **Suíte cair abaixo de 1.953 + novas contraprovas.** Nenhum teste existente
   pode ser removido para acomodar as correções, fora a substituição declarada
   em C6.
4. **Alguma das seis contraprovas do parecer continuar reproduzindo.** É o teste
   final: as seis saídas antigas têm de deixar de ocorrer.
