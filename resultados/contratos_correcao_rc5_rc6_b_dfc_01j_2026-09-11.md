# Contratos de correção R-C5 / R-C6 / R-SUPORTE — B-DFC-01J

**Data:** 2026-09-11. **Escrito ANTES de qualquer alteração de código**, pelo
mesmo rito da onda C1–C6: a política é escolhida e registrada primeiro, para
que nenhuma decisão possa ser tomada olhando o resultado medido.

**Origem:** [conferência independente da implementação de
C1–C6](conferencia_independente_c1_c6_b_dfc_01j_2026-09-11.md), achados R-C6
(P2), R-C5 (P2) e R-SUPORTE (P2, dívida preexistente).

**Os três achados foram reproduzidos pela sessão principal antes de virar
contrato**, com o bloco executável do §5 daquele parecer. A saída bateu
integralmente com a publicada:

```text
G0 zero_independentes True 0
G0 campo_ausente True None
G3 False False F3 {'decidivel': 'AUSENTE', 'clusters_suficientes': 'AUSENTE', 'ressalva': 'AUSENTE'}
G3 True True F3 {'decidivel': 'AUSENTE', 'clusters_suficientes': 'AUSENTE', 'ressalva': 'AUSENTE'}
G3_UM_ERRO StatisticsError stdev requires at least two data points
```

**Estado de partida, conferido contra o parecer.** Os seis SHA-256 dos arquivos
em escopo coincidem com os publicados no §6 da conferência. Cópia durável em
`artefatos/b_dfc_01j/snapshots/2026-09-11-pre-rc5-rc6/`, com `SHA256SUMS.txt`
— atende à recomendação do revisor de não deixar o snapshot em diretório
efêmero de sessão.

**O que esta onda NÃO faz:** redesenhar a estatística de poder (F3), implementar
B3, reconstruir a população point-in-time, adjudicar as rubricas do BB, alterar
a representação de largura zero dos 198 registros, treinar qualquer modelo ou
tocar `corpus/holdout_2T2026`.

---

## Diagnóstico comum a R-C5 e R-C6

Os dois achados são o **mesmo defeito de integração**: na onda C1–C6 eu
implementei o **produtor** do campo novo, publiquei o campo, e deixei o
**predicado de decisão** do consumidor exatamente como estava. O gate passou a
*exibir* a informação sem passar a *decidir* por ela.

É a repetição do achado F10 — *"essa exigência do pré-registro só existia como
TEXTO e não participava da condição de aprovação"* —, desta vez dentro dos
contratos escritos para corrigi-lo. A regra que sai disso, e que vale para
qualquer contrato futuro deste projeto:

> **Contrato que cria um campo de estado só está cumprido quando existe uma
> contraprova que exercita a DECISÃO governada por ele.** Asserção sobre o JSON
> publicado prova o produtor e não prova nada sobre o consumidor.

---

## R-C6 — a quarentena de F3 tem de vetar a aprovação de G3

### Defeito

`gate_g3` devolve `calculo_de_poder_invalidado_por: "F3"` e decide por

```python
"aprovado": relativa <= G3_MELHORIA_DETECTAVEL and B3_EXECUTADO
```

Um gate que declara o próprio cálculo inválido e continua aprovando por ele não
está em quarentena — está com etiqueta. Faltam também `decidivel`,
`clusters_suficientes` e `ressalva`, que o contrato C6 fixou como vocabulário
comum aos dois consumidores e que a sensibilidade implementa corretamente.

### Contrato

**C6-bis.1 — três vetos independentes.** A aprovação de G3 passa a exigir a
conjunção de três condições, cada uma suficiente para reprovar sozinha:

1. `relativa <= G3_MELHORIA_DETECTAVEL` — o poder medido;
2. `B3_EXECUTADO` — o benchmark econômico do §4 do pré-registro;
3. `PODER_REDESENHADO_APOS_F3` — o método de poder não estar invalidado.

**C6-bis.2 — a terceira condição é uma constante de módulo, não um literal.**
`PODER_REDESENHADO_APOS_F3 = False`, no mesmo formato de `B3_EXECUTADO`, para
que (a) o veto seja legível no artefato, (b) a contraprova possa exercitar as
quatro combinações sem editar código, e (c) o dia em que F3 for redesenhado a
liberação seja **uma linha declarada**, não a remoção de um `False` escondido
dentro de uma expressão.

**C6-bis.3 — estado explícito de C6 em G3.** `gate_g3` publica `decidivel`,
`clusters_suficientes` e `ressalva` com a mesma semântica de `_poder`:
`decidivel` é `False` enquanto F3 vigorar; `clusters_suficientes` mede os
emissores que **efetivamente entram no erro do baseline eleito** (a contagem de
C4-B), não a população.

**C6-bis.4 — os números continuam publicados.**
`melhoria_minima_detectavel_relativa` e
`emissores_necessarios_para_o_gate_decidir` permanecem no artefato, marcados.
Publicar e invalidar, nunca apagar.

### Alternativas rejeitadas, registradas antes de medir

| Alternativa | Por que não |
|---|---|
| Fixar `"aprovado": False` em G3 | Esconde qual veto está agindo, impede testar os outros dois, e um redesenho futuro teria de **lembrar** de remover o literal. Permissão falsa latente trocada por outra. |
| Apagar os números de poder | Contraria o próprio C6 e a regra de proveniência do projeto: número superado fica publicado e marcado. |
| F3 levantar `ReprovaEmAberto` | `ReprovaEmAberto` significa *amostra insuficiente para decidir*. F3 não é amostra insuficiente: é método sabidamente errado com todos os demais diagnósticos ainda válidos. Levantar descartaria justamente o diagnóstico que C6 quer preservar, e misturaria dois estados que o projeto separou de propósito (a mesma razão de `ErroDeUnidade` não herdar de `ReprovaEmAberto`). |
| Deixar só a etiqueta e declarar que é telemetria | O docstring e o comentário do próprio gate dizem que a quarentena governa. Manter a divergência entre o que o código diz e o que faz é o defeito, não a correção. |

### Critérios de aceitação

A contraprova exercita **a decisão**, nas quatro combinações — verificar que a
constante atual é `False` não testa conjunção nenhuma:

| # | `B3_EXECUTADO` | `PODER_REDESENHADO_APOS_F3` | `aprovado` esperado | O que prova |
|---|---|---|---|---|
| 1 | `False` | `False` | `False` | estado de hoje |
| 2 | `True` | `False` | **`False`** | **o caso do parecer**: F3 veta mesmo com B3 |
| 3 | `False` | `True` | `False` | B3 veta mesmo sem F3 |
| 4 | `True` | `True` | `True` | nenhum dos dois vetos é um `False` fixo disfarçado |

Amostra com poder folgado (`relativa <= 0,20`) nos quatro casos, para que o que
se mede seja o veto e não o limiar.

5. `decidivel`, `clusters_suficientes` e `ressalva` presentes em todas as
   quatro; `decidivel is False` enquanto F3 vigorar; `ressalva` nomeia F3.
6. Não-regressão: os dois números de poder continuam não-nulos no artefato.

---

## R-C5 — G0 só certifica se houver evidência independente

### Defeito

`gate_g0` copia `identidades_conferidas_independentes` por `.get(...)` e não a
usa na decisão. Com zero verificações independentes e um fechamento por
construção, aprova. Com o **campo ausente**, publica `None` e aprova igual —
"não sei" tratado como "sim", que é a guarda-que-aprova-por-ausência-de-dado do
§3.14 do AGENTS.md.

### Contrato

**C5-bis.1 — o piso que não inventa limiar.** G0 só aprova se
`identidades_conferidas_independentes` estiver **presente, for inteiro e for
maior que zero**.

**C5-bis.2 — ausência do campo é recusa, não permissão.** Artefato sem o campo
(schema antigo, produtor trocado, leitura parcial) não certifica. Vale a mesma
regra que o §3.15 já fixou para o cache de OCR: *schema não reconhecido é
tratado como «não sei», nunca como aprovação*.

**C5-bis.3 — o motivo sai publicado.** G0 ganha um campo declarando o requisito
e o limiar passa a nomeá-lo, para que a reprovação por esta via seja legível no
artefato sem ler o código.

### A escolha do piso, e o que ela deliberadamente não faz

O revisor recusou-se a inventar um percentual de cobertura, corretamente: o
contrato C5-B pediu a marcação de linhagem e as duas contagens, e não fixou
cobertura mínima. **Esta onda não inventa esse número tampouco.** O que ela
fecha é só a lacuna entre a certificação anunciada e a implementação
meramente informativa — o caso extremo de *nenhuma* evidência independente, e o
caso de campo ausente.

| Alternativa | Por que não |
|---|---|
| Exigir `independentes == conferidas` | Inventa limiar que o contrato não fixou e reprovaria população legítima com mistura de fechamentos independentes e por construção. |
| Exigir fração mínima (50%, 80%…) | Nenhum número desses é derivável da evidência disponível. Escolher um agora seria fixar política por conveniência. |
| Exigir que todas as identidades anuais fechem | O revisor advertiu explicitamente contra isso; 17 das anuais são **não verificáveis**, o que é estado da fonte, não defeito do instrumento. |
| Declarar que é só telemetria e não mexer na decisão | Seria honesto, mas deixa o gate chamado de certificação sem certificar nada. Se fosse esta a escolha, o nome e o docstring teriam de mudar — mais confuso que aplicar o piso. |

### Critérios de aceitação

1. `identidades_conferidas_independentes: 0` + um fechamento por construção →
   `aprovado is False`, com o motivo publicado.
2. Campo ausente → `aprovado is False` e o campo publicado como `None`.
3. Campo presente e `> 0`, sem divergências, sem rubricas suspeitas e com J na
   população → `aprovado is True`. **Não-regressão: o piso não pode reprovar
   quem tem evidência independente.**
4. Artefato real: G0 continua reprovando **pelos mesmos motivos de antes**
   (rubricas com conformidade não demonstrada e zero observações de J), com
   `identidades_conferidas_independentes` seguindo em 24. A correção não pode
   mudar o veredito vigente nem o motivo dele.

---

## R-SUPORTE — um único erro é amostra insuficiente, não exceção crua

### Defeito

Com o baseline eleito cobrindo uma só observação, `statistics.stdev(todos)`
levanta `StatisticsError`. `_medir` captura `ReprovaEmAberto`, não
`StatisticsError` — então essa configuração **derruba o relatório inteiro**,
levando junto G0, G1 e G2 que já haviam sido medidos.

### Não é regressão de C4, e há prova independente do snapshot

O revisor concluiu isso comparando as duas cópias. A ordem do arquivo confirma
sem depender do snapshot: a chamada `statistics.stdev(todos)` está na linha
**603** e a alteração de C4-B (`emissores_usados = sorted(por_emissor)`) na
**627**. A exceção estoura antes de qualquer linha introduzida por C4. Entra
como dívida anterior declarada, não como retratação da correção de contagem.

### Contrato

**S.1** — quando o suporte de erro do baseline eleito tiver menos de duas
observações, `gate_g3` levanta `ReprovaEmAberto` com o motivo, antes de
qualquer conta de dispersão.

**S.2** — nenhuma outra classe de exceção passa a ser capturada por `_medir`.

| Alternativa | Por que não |
|---|---|
| Acrescentar `StatisticsError` ao `except` de `_medir` | Converteria **qualquer** defeito estatístico futuro em veredito plausível de gate. É exatamente o que a separação `ErroDeUnidade` × `ReprovaEmAberto` existe para impedir: esconder defeito atrás de verdito plausível é pior que a execução falhar alto. |
| `try/except StatisticsError` em volta do gate | Mesmo problema, escopo um pouco menor. |
| Devolver dict degradado com `aprovado: False` | `ReprovaEmAberto` já é o vocabulário do projeto para "amostra insuficiente, nunca aprovação", e `_medir` já sabe convertê-la em gate reprovado com motivo. Criar um segundo caminho para o mesmo estado é dívida nova. |

### Critérios de aceitação

1. A entrada exata do §5 do parecer levanta `ReprovaEmAberto`, não
   `StatisticsError`, e a mensagem nomeia o baseline eleito e o tamanho do
   suporte.
2. A exceção é subclasse de `ReprovaEmAberto` — que é o que `_medir` captura, e
   cuja conversão em "gate reprovado com motivo" já tem contraprova própria.
3. Não-regressão: com duas ou mais observações no suporte, a conta segue sendo
   feita e o gate devolve os mesmos campos.

---

## Impacto previsto nos testes, declarado antes de rodar

Pré-registrar isto importa porque a regra do projeto é que teste é contrato e
**nunca se enfraquece asserção para fazer código passar**. Se algo quebrar fora
desta lista, é sinal de efeito não previsto e vira achado, não conserto.

| Teste | Previsão | Natureza |
|---|---|---|
| `test_C6_a_marcacao_nao_e_o_que_reprova_o_gate` | **Substituição declarada.** Hoje tem uma única asserção — `B3_EXECUTADO is False` —, que é precisamente o que o revisor apontou como não testar a conjunção. O título afirma o contrário do que C6-bis estabelece. A intenção que ele protegia (o veto de B3 é independente) é **preservada e generalizada** pelo caso 3 da matriz 2×2. | substituição por contrato |
| `test_F10_B3_ausente_impede_aprovacao_do_G3` | **Continua passando sem alteração.** Asserta `aprovado is False` com B3 ausente, que segue verdadeiro. | não-regressão |
| `test_C6_gate_g3_marca_o_poder_como_invalidado_por_F3` | **Continua passando sem alteração.** Asserta marcação e preservação dos números. | não-regressão |
| `test_C4_g3_conta_os_emissores_que_entram_na_comparacao` | **Continua passando.** Asserta `aprovado is False`, que os novos vetos só reforçam. | não-regressão |
| Testes de `gate_g0` | **Não existem** — nenhum teste exercita `gate_g0` diretamente hoje. É a própria lacuna do R-C5. | cobertura nova |

---

## Condições de falsificação desta onda

A onda está **errada** se qualquer uma se verificar:

1. **G0 muda de veredito ou de motivo no artefato real.** O esperado é
   reprovação idêntica à de antes; evidência independente real é 24.
2. **Algum número do artefato muda além dos campos declarados.** Série de J,
   fatos, derivações, conferências, vintages e manifesto devem sair
   byte-idênticos.
3. **A suíte precisa de qualquer asserção enfraquecida** fora da substituição
   declarada acima.
4. **G3 aprova em alguma das combinações 1–3 da matriz**, ou reprova na 4 —
   nos dois casos o veto virou literal disfarçado em vez de conjunção.
5. **A população de J deixa de ser zero**, ou qualquer gate anterior a G3 muda
   de veredito. Esta onda corrige instrumento; não produz rótulo.
