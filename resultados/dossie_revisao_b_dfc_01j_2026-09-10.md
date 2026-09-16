# Dossiê de revisão — B-DFC-01J-M, do contrato ao veredito

**Data:** 2026-09-10 · **Branch:** `corrige-contrato-corpus` · **Nada commitado.**
**Para:** agente revisor. **Autor do trabalho revisado:** sessão principal.

Este documento existe para que outra pessoa (ou agente) possa **refutar** o
veredito sem precisar reconstruir a investigação. Ele não repete os relatórios —
aponta para eles, diz o que cada um responde, e concentra o que um revisor
precisa: **o que foi decidido por julgamento e não por medição**, que é onde o
erro, se houver, está.

Ordem de leitura sugerida: §1 (o pedido) → §2 (veredito) → §5 (julgamentos) →
§3 (reproduzir) → o resto conforme a dúvida.

---

## 1. O que se pede ao revisor

Não é "leia e concorde". São perguntas falsificáveis, cada uma com onde olhar.
A mais importante é a **R1**.

| # | Pergunta | Onde verificar |
|---|---|---|
| **R1** | Reclassificar as duas rubricas para `nao_identificado` **resolve** o G0 ou **define o problema para fora dele**? O G0 passa porque a não conformidade sumiu de dentro de J — isso é pagar o preço ou esconder a conta? | §5.1 deste dossiê; `gates.json` G0; §2-bis do relatório |
| **R2** | A evidência do **Bradesco** sustenta a mesma conclusão do Itaú? Ela é declaradamente mais fraca — coincidência de trimestre + sinal credor + exposição cambial conhecida, **sem** casamento de magnitude | `scripts/piloto_bancos_dfc.py:459-475` (o `motivo`); §5.2 |
| **R3** | A não separabilidade se apoia em **ausência** de divulgação. Existe nota de composição por moeda que eu não abri? Inclusive fora do corpus (Pilar 3, formulário de referência) | §5.3; `corpus/ifrs/` |
| **R4** | A tolerância de **8%** no casamento de magnitude foi escolhida por mim depois de ver os números. Ela é significativa ou foi ajustada ao resultado? | §5.4 |
| **R5** | A guarda de derivação recusa `total<0 ∧ parcial<0 ∧ diferença>0`. Ela é estreita demais? Um 4T que encolhe **sem** trocar de sinal passa | §5.6; `scripts/piloto_bancos_dfc.py:1740` |
| **R6** | O veredito **muda** com este trabalho? Antes e depois, é `NÃO AUTORIZA`. Verifique se o que mudou é só a *razão* e o *caminho de reabertura* | §5.7 |
| **R7** | Todos os números publicados reproduzem? **Três** não reproduziam e foram corrigidos hoje, o último deles derrubando um argumento — procure um quarto | §3, §9.3, §9.8 |
| **R8** | O caminho de reabertura sobrevive? O recorte "rubricas sem crédito" **não** seleciona baixa dispersão — admite CV 0,96, pior que as cambiais removidas | §9.8 |

**Regra da casa que se aplica à revisão:** se um teste precisar ser enfraquecido
para o código passar, o problema é o código. E discordância medida vale mais que
concordância — um relatório que só confirma não justifica a rodada.

---

## 2. O veredito

**`NÃO AUTORIZA TREINO`.** Nenhum modelo foi carregado em nenhum momento.

Alvo congelado **antes** de medir (`resultados/pre_registro_b_dfc_01j_modelo_2026-09-09.md`):
`y = ln(J(t+1)/J(t))`, crescimento log do custo de captação por competência um
trimestre à frente, com companheiro binário para T1/T2.

| Gate | Pergunta | Medido | Limiar | |
|---|---|---|---|---|
| **G0** | O dado é íntegro e conforme ao contrato? | 0 rubricas não conformes | 0 | ✅ |
| **G1** | É *point-in-time*? | **72,0%** (18/25) | 100% | ❌ **decisivo** |
| **G2** | O rótulo tem erro menor que o sinal? | **1,0464** | < 0,10 | ❌ |
| **G3** | A amostra decide algo? | 2 emissores | ≥ 3 clusters | ❌ em aberto |
| **T1** | O alvo fabrica o próprio baseline? | 16 observações | ≥ 25 p/ quintil | ❌ em aberto |
| **T2** | Sinal temporal ou ordenação de emissor? | sem baseline eleito | — | ❌ em aberto |

Fonte: `artefatos/b_dfc_01j/prontidao/gates.json`.

**O achado que dá nome à rodada:** duas rubricas que o contrato manda somar em J
embutem **variação cambial do principal de captação em moeda estrangeira**, que o
contrato exclui nominalmente, e **a parcela não é separável** por leitura de nota.
Elas viraram `nao_identificado`; **J como ponto exato foi de 5 para ZERO** nos 25
pacotes congelados, e o G2 — que passava com folga de 48× — foi para 1,0464:
**o rótulo ficou mais ruidoso que o sinal**.

**Reprova em aberto ≠ aprovação.** G3/T1/T2 entram na cadeia como gate reprovado
**com o motivo**. Amostra insuficiente nunca vira "passou".

---

## 3. Reproduzir do zero

Custo **zero** — todos os documentos estão em disco, nenhuma chamada paga.

```bash
export PYTHONPATH=.
python scripts/piloto_bancos_dfc.py auditar                 # 25 pacotes congelados
python scripts/piloto_bancos_dfc.py estender               # série 2018T1..2026T1
python scripts/auditar_prontidao_b_dfc_01j.py              # cadeia de gates
python scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py   # conforme x anterior
python -m pytest tests/test_piloto_bancos_dfc.py \
                 tests/test_prontidao_b_dfc_01j.py \
                 tests/test_sensibilidade_b_dfc_01j.py -q   # 142 testes
python -m pytest -q                                        # suíte: 1.938, zero skip
```

> **Nota:** o `PYTHONPATH=.` é obrigatório — `sensibilidade_…py` importa
> `scripts.auditar_prontidao_b_dfc_01j` e falha com `ModuleNotFoundError` sem ele.
> Isso é atrito de reprodução, não defeito de resultado, mas está em §9.2.

**Idempotência conferida em 2026-09-10:** `gates.json` e `sensibilidade.json`
re-gerados saem **byte-idênticos** aos versionados.

**Confirmação rápida dos três números de manchete:**

```bash
python -c "
import json
g=json.load(open('artefatos/b_dfc_01j/prontidao/gates.json'))
print('interrompido_em =', g['interrompido_em'])
print({x.get('gate') or x.get('teste'): x['aprovado'] for x in g['gates']})
a=json.load(open('artefatos/b_dfc_01j/auditoria.json'))
print('J ponto/intervalo/nao-ident =', a['j_identificado'], a['j_limitado'], a['j_nao_identificado'])
"
# esperado: G1 · G0 True e o resto False · 0 15 9
```

---

## 4. A trilha — como se chegou aqui

Ordem real dos fatos. Cada etapa tem artefato próprio.

1. **Contrato B-DFC-01J.** J = juros por competência sobre instrumentos de
   captação incluídos (depósitos, compromissadas, empréstimos/repasses, títulos
   emitidos, subordinados como passivo IFRS). **Exclui nominalmente** câmbio,
   valor justo e derivativos. Construção aditiva exaustiva; **ausência de
   composição nunca vira zero nem estimativa**.
   → `resultados/formulacao_bancaria_dfc_2026-09-09.md`
2. **Piloto documental**, 25 pacotes congelados, 5 emissores.
   → `resultados/piloto_bancos_dfc_2026-09-09.md`, `artefatos/b_dfc_01j/`
3. **Extensão da janela** para 2018T1–2026T1, 65 documentos, 3 emissores com
   série utilizável. → `resultados/extensao_janela_dfc_2026-09-09.md`
4. **Pré-registro** do alvo e dos limiares, **antes** de qualquer medição.
   → `resultados/pre_registro_b_dfc_01j_modelo_2026-09-09.md`
5. **Primeira rodada de gates (2026-09-09): G0 reprovou.** Três rubricas que o
   contrato manda somar em J vinham **credoras** em quatro trimestres. Despesa de
   captação por competência não é crédito. **E a soma fechava do mesmo jeito** —
   daí a regra durável: *fechamento aritmético e conformidade contratual são
   estados diferentes, e só o primeiro estava sendo medido.*
6. **Condição de reabertura nº 1 executada (2026-09-10):** ler as notas
   explicativas para saber o que as rubricas contêm. É o trabalho desta rodada.
7. **Resposta: o ramo ruim.** Não separável. Reclassificação, medição do custo,
   e a cadeia de gates refeita. → `§2-bis` de
   `resultados/prontidao_b_dfc_01j_modelo_2026-09-09.md`

### 4.1 A evidência do Itaú, medida na fonte

Rubrica `Recursos de Mercados Interbancários`. A **Nota 17b** decompõe o saldo;
a maior sub-rubrica é `Financiamentos à Importação e Exportação`, que a própria
nota declara *"geralmente denominadas em moeda estrangeira"*.

| Medição | Valor |
|---|---|
| (i) Composição | R$ **84.051** de R$ 188.134 em 31/03/2020 (e 105.837 de 363.192 em 31/03/2025) |
| (ii) Salto do saldo no 1T2020 | 64.622 → 84.051 = **+19.429 (+30,1%)**, sem emissão que explique |
| (ii) Salto da linha de juros | 3.111 → 24.230 = **+21.119** — **casam dentro de 8%** |
| (iii) Teto contratual declarado | `0% a 9,60% a.a.` → sobre R$ 84 bi, ~R$ 2,0 bi/trimestre. **R$ 24 bi não pode ser juros** |
| (iv) Caso simétrico | 2T2021, real valorizando: saldo cai, linha vem **credora (+3.107)** |

E o emissor diz com as próprias palavras: a DFC dele tem três linhas nomeadas
**`Resultado de Juros e Variação Cambial de …`**.

**Por que não é separável:** a Nota 21b é tabela plana sem rodapé; não há nota de
exposição por moeda nos intermediários; a nota de hedge do anual nomeia
`Depósitos` e `Captações no Mercado Aberto` como objetos de cobertura — **nunca
esta rubrica**. O saldo em moeda estrangeira *é* publicado, o que permitiria
**estimar** a parcela. Estimar é proibido pelo contrato.

### 4.2 A distinção que evitou condenar rubrica sem evidência

A terceira rubrica suspeita — `Depósitos interfinanceiros` do Bradesco — só vem
credora num **4T derivado**: o anual imprime `(521.525)` contra `(2.282.154)` dos
nove meses. **Acumulado de doze meses menor que o de nove não é diferença de
nada** — ou houve reversão no 4T, ou o anual reclassificou. Não se sabe qual.

Vale a recusa da **derivação**, não a condenação da **rubrica**. A rubrica
continua `_INCLUIR` (`scripts/piloto_bancos_dfc.py:452`).

---

## 5. Onde eu decidi por julgamento — o alvo da revisão

Tudo abaixo é onde a medição parou e eu escolhi. É aqui que a revisão rende.

### 5.1 (R1) O G0 passa porque o problema saiu de dentro dele

**A objeção mais forte contra este trabalho.** O G0 exige "0 rubricas incluídas
com conformidade não demonstrada". Eu tirei as rubricas não conformes de dentro
de J — e o G0 passou. Isso é resolver ou é tautologia?

**Minha resposta, e ela é falsificável:** não é tautologia **se o preço foi pago
e medido**, e foi:

| | Conforme (agora) | Anterior, não conforme |
|---|---:|---:|
| Cortados por largura > 5% | **40 de 69** | 9 de 69 |
| Alvos | **25** | 55 |
| **G2 ruído/sinal** | **1,0464** ❌ | 0,0214 ✅ |
| Emissores na população | **2** | 3 |

Se fosse tautologia, o resto da cadeia teria melhorado ou ficado igual. Em vez
disso **o G2 explodiu** e o Itaú saiu inteiro. A conformidade custou a folga de
48× que o G2 tinha — ela era **comprada pelo defeito**.

**Como refutar:** mostre que a reclassificação era desnecessária (a parcela É
separável — §5.3), ou que J deveria ter sido tratado como ponto com a rubrica
dentro, apesar do crédito impresso.

### 5.2 (R2) O Bradesco foi reclassificado com evidência mais fraca

Declarado no próprio código, não escondido em nota de rodapé:

> "A evidência aqui é o crédito impresso e a coincidência de trimestre, **NÃO o
> casamento de magnitude que se mediu no Itaú** — a composição da rubrica por
> moeda não é publicada, que é justamente o motivo de não ser separável."

O que há: crédito de **+2.335.452** no 2T2021 dentro de uma tabela cujo total é
despesa (−9.652.884); **mesmo trimestre** em que a linha equivalente do Itaú
virou credora; e R$ 30,8 bi de investimentos no exterior.

O que **não** há: composição por moeda da rubrica, logo nenhum teste de
magnitude. **Assimetria assumida, não resolvida.**

**Se o revisor discordar:** o efeito de reverter é calculável — devolva
`juros_emprestimos_e_repasses` para `_INCLUIR` e rode a sensibilidade. Não
refaça o julgamento sem medir o efeito.

### 5.3 (R3) Não separabilidade se apoia em ausência de divulgação

Ausência de nota é evidência **mais fraca** que uma declaração positiva. O que eu
abri: Nota 17b (composição), Nota 21b (tabela plana), nota de hedge do anual.

**O que eu NÃO abri, e um revisor deveria:** relatórios de Pilar 3, formulário de
referência, seção de gestão de riscos de mercado. **Nada disso está no corpus** —
buscar exigiria coletar documento novo, o que muda escopo e não foi autorizado.

Se existir composição por moeda dessa rubrica em algum lugar, **a parcela vira
separável e este veredito muda de ramo.**

### 5.4 (R4) O "dentro de 8%" foi escolhido depois de ver os números

+19.429 contra +21.119 dá 8,0% de discrepância. Eu vi os números e então
escrevi "casam dentro de 8%". **Não é limiar pré-registrado.**

Em defesa: o argumento não depende da tolerância. O item (iii) é independente e
mais forte — o **teto contratual de 9,60% a.a.** torna R$ 24 bi aritmeticamente
impossível como juros, qualquer que seja a tolerância. E o item (iv), o caso
simétrico, também não usa tolerância.

**Leia (ii) como corroboração, não como prova.** Se o revisor quiser, descarte
(ii) inteiro: (i)+(iii)+(iv) ainda sustentam a conclusão.

### 5.5 Larguras de intervalo: a regra de seleção faz parte do número

Publiquei mediana **23,79%** para o Itaú na série estendida. Ao reconferir hoje
**não reproduzi de primeira** — obtive 23,23% e 22,67% sob outras regras. A regra
correta é **trimestre isolado com `fechamento_confere = True`, sem deduplicar
safra** (Itaú n=47 → 23,7918%; Bradesco n=21 → 4,07%; BB n=29 → 0,57%).

A regra estava implícita. **Agora está escrita** no §2-bis.5 do relatório e no
§3.17 do AGENTS.md. Registro aqui porque é a classe de defeito a procurar em
outros números: *número certo, regra de seleção não publicada*.

### 5.6 (R5) O escopo da guarda de derivação

```python
# scripts/piloto_bancos_dfc.py:1740
if fato_total.valor < 0 and fato_parcial.valor < 0 and valor > 0:
    ...  # recusa: "o acumulado encolheu e a diferença sairia credora"
```

Ela pega **exatamente** o caso impossível: dois operandos devedores cuja
diferença sai credora. **Não pega** um 4T que encolhe sem trocar de sinal — se o
anual for −2.400.000 contra M9 −2.282.154, a diferença é um 4T pequeno e legítimo,
e deve mesmo passar.

**Escolha consciente:** condenar todo encolhimento reprovaria 4T legítimos. O
revisor deve julgar se a fronteira está no lugar certo.

**Efeito medido:** recusou **2** derivações —
`juros_depositos_interfinanceiros|000906|2025T4` (+1.760.629) e
`juros_mercados_interbancarios|019348|2020T4` (+4.136), esta última **na própria
rubrica cambial do Itaú**. Nos dois casos o trimestre fica com
`fechamento_confere = False` — descompasso exatamente igual ao valor recusado — e
é **descartado da população do gate**. Verificável:

```bash
python -c "
import json
from decimal import Decimal as D
for l in open('artefatos/b_dfc_01j/extensao/j_por_periodo.jsonl'):
    d=json.loads(l)
    if d.get('fechamento_confere') is False:
        delta=D(str(d['soma_incluidas']))+D(str(d['residuo_nao_identificado']))+D(str(d['excluido_por_contrato']))-D(str(d['total_declarado']))
        print(d['cd_cvm'], d['periodo'], d['base_temporal'], 'delta =', delta)
"
```

**A rubrica recusada não vira zero** — o trimestre é descartado por não fechar.
Essa era a checagem crítica e ela passa.

### 5.7 (R6) O veredito não mudou; a razão e o caminho de saída mudaram

Antes e depois: `NÃO AUTORIZA`. Um revisor cético pode dizer que a rodada não
alterou a decisão. **Correto, e importa mesmo assim:**

| | Antes (2026-09-09) | Depois (2026-09-10) |
|---|---|---|
| Gate decisivo | G0 (conformidade) | **G1** (*point-in-time*), 72,0% |
| Estado do G0 | reprovado, causa **desconhecida** | **resolvido**, causa medida |
| Caminho de reabertura | "ler as notas" (custo zero) | **coletar emissor não resolve** |
| J como ponto | 5 | **0** |

O obstáculo **mudou de lugar pela terceira vez**: era "intervalo × ponto", virou
"número de emissores", agora é **o rótulo**. E a exigência de ~16 emissores que
eu havia publicado como caminho **não vale** — cada emissor novo entra com o
mesmo defeito, porque câmbio dentro da linha de juros é **prática de
apresentação**, não peculiaridade de um banco.

### 5.8 O que decidiria o caso está fora do controle do projeto

O G0 só fecharia de vez se **o emissor passasse a publicar a parcela cambial
dessas linhas**. Nenhuma engenharia contorna isso.

---

## 6. Mudanças de código

Quatro, todas com teste.

| # | Onde | O quê | Teste |
|---|---|---|---|
| 1 | `scripts/piloto_bancos_dfc.py:536` | Itaú `juros_mercados_interbancarios`: `_INCLUIR` → `_NAO_IDENT`, com `motivo` citando as quatro medições | `TestRubricasComCambioEmbutido` |
| 2 | `scripts/piloto_bancos_dfc.py:461` | Bradesco `juros_emprestimos_e_repasses`: `_INCLUIR` → `_NAO_IDENT`, `motivo` declarando evidência mais fraca | idem |
| 3 | `scripts/piloto_bancos_dfc.py:1740` | `derivar_trimestre` recusa diferença credora entre operandos devedores | `TestDerivacaoComAcumuladoQueEncolhe` |
| 4 | `scripts/auditar_prontidao_b_dfc_01j.py:717` | `_medir()` captura `ReprovaEmAberto` por gate | `tests/test_prontidao_b_dfc_01j.py` |

**Não mudou:** `juros_depositos_interfinanceiros` do Bradesco continua `_INCLUIR`
(§4.2). Há teste que trava isso — `test_interfinanceiros_do_bradesco_CONTINUA_em_J`.

**Sobre a mudança 4 — defeito do próprio instrumento.** Com o Itaú fora, o G3
passou a levantar `ReprovaEmAberto`; a exceção subia até `main()` e o relatório
saía **só com a mensagem de erro, descartando G0/G1/G2 já calculados**. Regra que
sai daqui: *reprova em aberto num gate posterior não pode apagar os anteriores*.

**Um teste foi reescrito, não enfraquecido.** `test_exclusao_documentada_permite_J_como_ponto`
afirmava que o Bradesco dá J como ponto exato. Deixou de ser verdade — não porque
o rigor caiu, mas porque **um fato sobre a fonte mudou**. Renomeado para
`test_exclusao_documentada_e_subtraida_exata`, com docstring explicando a
distinção, mantendo as asserções que continuam válidas (exclusões nomeadas e
subtraídas exatas, `fechamento_confere is True`) e trocando as que mudaram
(`status == "limitado"`, intervalo com `limite_inferior < limite_superior`).
**Confira que isso não foi afrouxamento disfarçado.**

**Inversão do script de sensibilidade (v1.0.0 → v2.0.0).** Ele comparava "estado
atual (rubricas dentro)" × "cenário hipotético (rubricas fora)". Quando o
hipotético virou o real, rodá-lo sem mexer compararia o estado novo **consigo
mesmo** sob um rótulo velho — silenciosamente sem sentido. Chaves renomeadas
(`intervalo_conforme`, `intervalo_estado_anterior_nao_conforme`, …) e campo
`o_que_mudou` documentando a inversão.

---

## 7. Artefatos e o que cada um responde

| Artefato | Responde |
|---|---|
| `artefatos/b_dfc_01j/auditoria.json` | Os 25 pacotes: `j_identificado=0`, `j_limitado=15`, `j_nao_identificado=9` |
| `artefatos/b_dfc_01j/extensao/resumo.json` | 65 docs, 58 extraídos, 7 sem nota; 69 pares emissor-trimestre; 2018T1–2026T1 |
| `artefatos/b_dfc_01j/extensao/j_por_periodo.jsonl` | J por período com limites, largura, conceitos incluídos/não identificados |
| `artefatos/b_dfc_01j/extensao/derivacoes.jsonl` | Linhagem das derivações: 117 calculadas, 8 recusadas |
| `artefatos/b_dfc_01j/prontidao/gates.json` | A cadeia G0–T2, com `interrompido_em: G1` |
| `artefatos/b_dfc_01j/prontidao/sensibilidade.json` | Conforme × estado anterior — **o custo da conformidade** |

**Conferências:** 24 identidades conferidas, **0 divergentes**, 27 não
verificáveis. `T1+T2+T3+T4 = A` fecha em **15 de 15** anos completos.

---

## 8. Não mutação — verificado em 2026-09-10

| Invariante | Estado |
|---|---|
| `corpus/` inalterado | ✅ `git status --porcelain corpus/` vazio |
| `corpus/holdout_2T2026` | ✅ nunca lido |
| `artefatos/cvm.duckdb` | ✅ SHA-256 `43e31d9f…` inalterado |
| `artefatos/cvm_treino.duckdb` | ✅ SHA-256 `c1a60445…` inalterado |
| Índice vetorial / `metadados.csv` | ✅ intocados (`hash_corpus` preservado) |
| Suíte | ✅ **1.938 passed, zero skip** |
| Chamadas pagas | ✅ **zero** — tudo lido de disco |

**Fora de limites e respeitado:** nenhum treino, backtest ou ML foi executado; a
existência dos 25 pacotes como denominador não foi alterada (os **resultados**
medidos sobre eles mudaram, que é outra coisa); painéis de produção intocados.

---

## 9. Pontos abertos que eu encontrei e NÃO fechei

Declarados porque escondê-los é o oposto do que o projeto mede.

### 9.1 `resumo.json` subconta as recusas de derivação
`quartos_trimestres_recusados` lista **6** entradas — só as de operando ausente.
As **2** recusas em nível de rubrica (a guarda nova) aparecem **apenas** em
`derivacoes.jsonl`. Quem lê só o resumo não descobre que dois trimestres
perderam uma rubrica.

**Não é erro de resultado** — o efeito propaga corretamente via
`fechamento_confere = False` → descarte. É lacuna de **reportabilidade**, e é
exatamente o padrão silencioso que o projeto combate. **Não corrigi**: mexer no
schema do resumo depois de publicar os números exigiria re-verificar tudo, e não
era o pedido desta rodada.

### 9.2 `derivado_id` inconsistente na mesma linhagem
As 6 recusas por operando ausente gravam `derivado_id: None`; as 2 da guarda nova
gravam `conceito|cd_cvm|periodo`. **Mesmo arquivo, dois formatos.**

### 9.3 Três números publicados não reproduziam (corrigidos hoje)
- `0,3379 / 4,82× / ~75` do lado contaminado: medidos **antes** da guarda de
  derivação. Valores corretos: `0,2956 / 4,16× / ~60`. Corrigidos em AGENTS.md,
  MEMORY.md, `becos_sem_saida.md` e no relatório, com o valor antigo preservado.
- Mediana de largura do Itaú: reproduz, mas só com a regra de seleção que faltava
  (§5.5). Regra agora publicada.

- **Os CVs por rubrica**: `0,75` (Itaú cambial), `1,46` (Bradesco
  interfinanceiro) e a faixa `0,11–0,54` do BB também eram anteriores à guarda.
  Re-medidos: **0,68**, **0,96** e **0,11–0,50**. Ver §9.8 — este terceiro caso
  não é só drift numérico, ele **derruba um argumento**.

Foram encontrados por reconferência, não por teste — **não há guarda automática
contra número publicado que deixa de reproduzir**, e essa é a recomendação
estrutural que eu faria ao revisor: ela pegaria os três de uma vez.

### 9.4 `Recursos de Mercados Institucionais` do Itaú
Inclui **R$ 77,9 bi** de títulos no exterior e mede **CV 0,28** — o **mais baixo**
entre as parcelas do Itaú. Se fosse contaminada por câmbio, deveria oscilar.
**Por que não oscila não foi medido.** Isso importa porque o caminho de
reabertura (§10) depende de haver um subconjunto limpo, e ausência de crédito é
*consistente* com estar limpo, **não é prova**.

### 9.5 B3 nunca foi executado
O benchmark econômico exigido pelo contrato (meta Selic *point-in-time*) **não
está no repositório**. O §4 do pré-registro fixou, antes de medir, que sem ele
não há aprovação com B0–B2 apenas. Discutível hoje, porque G0/G1/G2 já decidem —
mas é **exigência contratual não cumprida** e deve constar.

### 9.6 Sete documentos de 65 sem nota legível
Causa diagnosticada um a um em `resumo.json`. Três são de classe diferente do
que se supunha (documento errado, não nota ausente).

### 9.7 `PYTHONPATH=.` obrigatório
`sensibilidade_…py` importa `scripts.…` e quebra sem ele. Atrito de reprodução.

---

### 9.8 O caminho de reabertura estava mal caracterizado (corrigido hoje)

**O achado mais material desta reconferência**, porque atinge a única afirmação
prospectiva do relatório.

A versão de 2026-09-09 dizia que o subconjunto "rubricas sem crédito em nenhum
trimestre" tem **"dispersão bem menor: CV de 0,11 a 0,54 contra 0,75 da rubrica
cambial do Itaú e 1,46 da do Bradesco"**. Medido direito, **a comparação se
inverte**:

| Conjunto | CV |
|---|---|
| Subconjunto "sem crédito" (15 rubricas `incluir`) | **0,11 a 0,96** |
| Itaú `juros_mercados_interbancarios` (cambial, removida) | 0,68 |
| Bradesco `juros_emprestimos_e_repasses` (cambial, removida) | 0,60 |

A pior do subconjunto "limpo" — `juros_depositos_interfinanceiros` do Bradesco,
**CV 0,96** — é **mais dispersa que qualquer uma das duas cambiais removidas**.
E o "1,46" era dessa mesma rubrica interfinanceira, que **não é cambial e
continua em J**: atribuí-lo à "rubrica cambial do Bradesco" foi troca de
referente.

**Consequência:** ausência de crédito **não** seleciona um conjunto de baixa
dispersão — que era exatamente o argumento. O caminho de reabertura não morre,
mas precisa de **outro critério de recorte, declarado antes de olhar o
resultado**. Corrigido no relatório, AGENTS.md, MEMORY.md e `becos_sem_saida.md`.

**Para o revisor:** este é o contraexemplo concreto do §9.4 — uma rubrica sem
crédito nenhum e com a pior dispersão de todas. Confirma que *ausência de
crédito é consistente com estar limpo, não é prova*. Reproduzir com:

```bash
python -c "
import json,collections,statistics,re
ISO=re.compile(r'^[0-9]{4}T[1-4]\$')
v=collections.defaultdict(list); cr=collections.defaultdict(list); t={}
for l in open('artefatos/b_dfc_01j/extensao/fatos.jsonl'):
    d=json.loads(l); p=str(d.get('periodo')); c=d.get('conceito')
    if not ISO.match(p) or d.get('valor') is None or not c or c=='despesa_juros_total': continue
    k=(d.get('cd_cvm_do_fato'),c); v[k].append(float(d['valor'])); t[k]=d.get('tratamento')
    if float(d['valor'])>0: cr[k].append(p)
lim=[(abs(statistics.stdev(x)/statistics.mean(x)),k) for k,x in v.items() if t[k]=='incluir' and not cr.get(k)]
print('faixa do subconjunto sem credito:', round(min(lim)[0],2), 'a', round(max(lim)[0],2))
print('pior:', max(lim)[1])
"
```

---

## 10. O que este trabalho NÃO conclui

- **Não conclui que custo de captação seja imprevisível.** Conclui que **este**
  estimando, nesta população, não é **decidível**. "Não decidível" ≠ "refutado".
- **Não conclui que a pergunta econômica esteja morta.** O que morreu é este J,
  construído com rubricas cambiais dentro.
- **Não autoriza treino, nem parcialmente** — nem holdout, nem painel de
  produção, nem caminho interativo (RN07 segue integral).
- **Não fecha o G0 de vez.** Ele depende de o emissor passar a divulgar.

**O que reabriria:** **outro estimando**, com **pré-registro e G0 próprios, sem
herdar nenhum número daqui**. O recorte candidato — rubricas sem crédito em
nenhum trimestre — **não basta sozinho**: ele admite uma rubrica de CV 0,96, pior
que as duas cambiais removidas (§9.8). Vai precisar de critério de dispersão
declarado **antes** de medir, mais as ressalvas dos §9.4 e §9.8.
**Coletar mais emissores não resolve.**

**O trivial ganha pela sétima vez.** B0 (sem mudança) tem o menor MAE macro
(0,1579) contra sazonal 0,2151 e mediana de 4T 0,1771; "sempre sobe" acerta
**64,91%** da direção com cobertura total, contra 56,52% e 54,55%. Cobertura sai
ao lado do acerto porque B0 **abstém da direção**.

---

## 11. Estado do repositório

**Branch** `corrige-contrato-corpus`, **nada commitado**. 6 arquivos modificados,
19 não rastreados. Integração de branch é tarefa separada — não é efeito lateral
da pesquisa.

Documentos que carregam este veredito e devem ser lidos como um conjunto:
`resultados/prontidao_b_dfc_01j_modelo_2026-09-09.md` (§2-bis é o núcleo),
`AGENTS.md` §3.17, `MEMORY.md`, `resultados/becos_sem_saida.md` (entrada C-bis),
e as retratações no topo de `piloto_bancos_dfc_2026-09-09.md` e
`extensao_janela_dfc_2026-09-09.md`.
