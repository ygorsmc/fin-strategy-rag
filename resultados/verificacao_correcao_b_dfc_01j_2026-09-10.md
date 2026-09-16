# Pacote de verificação — correção do instrumento B-DFC-01J

**Para:** revisor independente. **Item da sequência:** §6.1-bis da
[revisão de 2026-09-10](revisao_independente_b_dfc_01j_2026-09-10.md) —
*"Revisor independente confere a correção."*
**Objeto a verificar:** [`correcao_instrumento_b_dfc_01j_2026-09-10.md`](correcao_instrumento_b_dfc_01j_2026-09-10.md).
**Autor da correção:** sessão principal. **Data:** 2026-09-10.

A pergunta não é "a correção parece boa". São três, em ordem de importância:

1. **Os seis defeitos F1, F2, F7–F11 realmente saíram do código?**
2. **Alguma asserção existente foi enfraquecida para a suíte passar?**
3. **A correção introduziu defeito novo, ou corrigiu demais?** — a §4 deste
   documento lista sete lugares onde eu decidi por julgamento, e é onde eu
   olharia primeiro.

Nada aqui pede concordância. Um "a correção do F1 está errada porque…" é o
resultado mais útil que este pacote pode produzir.

---

## 1. Caminho rápido: confirmar ou refutar em dois comandos

```bash
export PYTHONPATH=.
python -m pytest -q                     # esperado: 1953 passed, zero skip
python -m pytest -q \
  tests/test_prontidao_b_dfc_01j.py::TestContraprovasDaRevisaoIndependente \
  tests/test_piloto_bancos_dfc.py::TestContraprovasDaRevisaoIndependente
                                        # esperado: 12 passed
```

As contraprovas do relatório de revisão, isoladas e sem tocar artefato:

```bash
python - <<'PY'
from decimal import Decimal
from scripts import auditar_prontidao_b_dfc_01j as a
from scripts.piloto_bancos_dfc import Fato, construir_j

# F7: variável constante não pode receber associação máxima (era 1.0)
print('F7  amplitude p/ constante :', a.amplitude_por_quintis([1.0]*50, [0,1]*25)[0])

# F1: a contraprova exata do relatório (era status=limitado, limites [70,100])
def f(c, v, t, lim=False):
    return Fato(fato_id=c, pacote_id='p', fonte_id='s', conceito=c,
        rotulo_original=c, periodo='2020T1', coluna_indice=0, texto_original=v,
        valor=Decimal(v), unidade='milhares_de_reais',
        valor_reais=Decimal(v)*1000, pagina_pdf=1, pagina_impressa='1',
        nota='n', tratamento=t, motivo='m', base_contabil='IFRS',
        perimetro='consolidado', evidencia='e', cd_cvm_do_fato='000906',
        limite_demonstravel=lim)
class S: cd_cvm='000906'
r = construir_j([f('inc','-100','incluir'), f('desc','30','nao_identificado'),
                 f('tot','-70','total')], '2020T1', S())
print('F1  status                 :', r.status)
print('F1  limites                :', r.limite_inferior, r.limite_superior)
print('F1  fechamento (segue OK!) :', r.fechamento_confere)
print('F1  sem limite demonstravel:', r.conceitos_sem_limite_demonstravel)

# F1 segunda contraprova: desconhecidas que se anulam (era identificado, ponto)
r2 = construir_j([f('inc','-100','incluir'), f('d1','30','nao_identificado'),
                  f('d2','-30','nao_identificado'), f('tot','-100','total')],
                 '2020T1', S())
print('F1  residual liquido zero  :', r2.status, '| residuo =', r2.residuo_nao_identificado)

# F2: o par real do Bradesco (base 02/05, alvo 2024T2 começa 01/04)
alvo = a.Alvo('000906','2024T1','2024T2',0.05,0.05,0.05,1000.0,1050.0,
              '2024-05-02','2024-08-05',0.0)
print('F2  horizonte respeitado   :', a.horizonte_contratual_respeitado(alvo))
print('F2  G1 aprovado            :', a.gate_g1([alvo])['aprovado'])
PY
```

**Valores esperados** — qualquer divergência é achado:

```text
F7  amplitude p/ constante : 0.0            (antes 1.0)
F1  status                 : nao_identificado   (antes limitado)
F1  limites                : 0 0            (antes 70 100)
F1  fechamento (segue OK!) : True           ← o defeito era invisível por isso
F1  sem limite demonstravel: ('desc',)
F1  residual liquido zero  : nao_identificado | residuo = 0   (antes identificado)
F2  horizonte respeitado   : False
F2  G1 aprovado            : False          (antes o par contava como certificado)
```

**Determinismo, conferido em 2026-09-10:** `gates.json` e `sensibilidade.json`
re-gerados saem **byte-idênticos**; `auditoria.json` idêntico fora de
`gerado_em`. Rodar os comandos abaixo reescreve artefatos — se a intenção é só
revisar, chame `executar()` em memória, como o §7 da sua revisão instrui.

---

## 2. Verificação por achado

| # | Critério falsificável | Onde | Como refutar |
|---|---|---|---|
| **F1** | Rubrica não identificada sem `limite_demonstravel` **nunca** produz intervalo; residual líquido nulo **nunca** produz `identificado` | `piloto_bancos_dfc.py::construir_j` (3 ramos de retorno) | Achar entrada que ainda devolva `limitado` ou `identificado` com desconhecida sem declaração |
| **F1-bis** | A **mesma** regra vale na sensibilidade, que reimplementava os limites | `sensibilidade_…py::cenario_intervalo`, `construir()` | Achar uma **terceira** implementação. Varri `grep -rn "min(soma\|max(soma\|limite_inferior=" scripts/ src/` e só existem as duas |
| **F2** | G1 aprova só por horizonte contratual, não por ordem de publicação; os dois números saem separados | `auditar_…py::gate_g1`, `horizonte_contratual_respeitado` | Achar par que o gate aprove com alvo já iniciado |
| **F7** | Desempate de quintil não usa o evento | `auditar_…py::amplitude_por_quintis` | Achar entrada em que variável sem poder ordenador meça amplitude > 0 |
| **F8** | Unidade do JSON vem dos fatos; unidades mistas **levantam erro** | `ResultadoJ.unidade`, `para_json`, `construir_j` | Achar registro cuja `unidade` divirja dos fatos que o compuseram |
| **F9a** | B2 exige os **quatro** trimestres imediatamente anteriores | `auditar_…py::previsoes_dos_baselines` | Achar previsão B2 com menos de quatro ou com buraco de calendário |
| **F9b** | Eleição de baseline usa a interseção onde todos opinam | `auditar_…py::gate_g3` (`mae_macro_no_suporte_comum`) | Ver §4.4 — **eu deixei o poder medido no suporte próprio**, de propósito, e isso merece objeção |
| **F10a** | T2 não informativo **reprova** | `auditar_…py::teste_t2` | Achar T2 com `informativo=False` e `aprovado=True` |
| **F10b** | B3 ausente **bloqueia** G3 | `B3_EXECUTADO`, `gate_g3` | Ver §4.6 — é flag manual |
| **F11** | `independente` sai em **todos** os ramos; identidade com operando derivado é `False` | `piloto_…py::conferir_identidade_trimestral` | Achar registro sem o campo, ou com `independente=True` tendo operando derivado |
| **extra** | Reprova em aberto em G0–T2 não apaga gates anteriores | `auditar_…py::executar`, `_medir` | Fazer qualquer gate levantar e ver se o relatório perde os anteriores |

### Efeito agregado a conferir

| | Antes | Depois | Onde |
|---|---:|---:|---|
| J como intervalo (25 pacotes) | 15 | **0** | `auditoria.json` |
| J não identificado | 9 | **24** | idem |
| Pares emissor-trimestre | 69 | **0** | `extensao/resumo.json` |
| Gate decisivo | G1 | **G0** | `prontidao/gates.json` |
| `T1+T2+T3+T4 = A` conferidas | "15 de 15" | **0 (17 não verificáveis)** | `extensao/conferencias.jsonl` |
| G2 ruído/sinal | 1,0464 | **campo ausente** | `prontidao/sensibilidade.json` |

---

## 3. Nenhuma asserção enfraquecida — cinco casos para auditar um a um

**Este é o ponto onde eu mais poderia ter trapaceado**, então está separado. A
regra da casa é que teste é contrato e código se adapta a ele; eu mudei cinco
casos existentes e preciso que cada um seja julgado.

| Caso | Diagnóstico que dou | O que conferir |
|---|---|---|
| `test_residual_sem_composicao_vira_intervalo_nao_ponto` | **Afirmava o defeito.** Exigia intervalo para qualquer residual | Virou `test_residual_COM_limite_demonstravel_vira_intervalo` e continua exigindo `[290, 300]` no caso legítimo. Dois casos novos cobrem as contraprovas. **Nada foi removido sem substituto** |
| `test_p2_sem_total_e_nao_aplicavel_nao_conflito` | **Premissa acidental.** Supunha `nao_identificado` ⇒ sem total | Agora testa o critério real (sem total ⇒ NAO_APLICAVEL) e um caso **novo** trava a independência entre fechamento e certificado semântico — que é o que sua revisão pediu |
| `test_a_conformidade_derrubou_o_rotulo_abaixo_do_sinal` | Travava G2 1,0464 × 0,0214, ambos de limites fabricados | Virou guarda **contra o retorno** do F1: nenhum cenário de intervalo pode publicar razão G2. É asserção mais forte, não mais fraca |
| `test_o_g2_que_passava_era_comprado_pelo_defeito` | Travava a folga de 48× | Virou o caso que mede o **colapso** do cenário anterior (sobra 1 emissor) |
| `test_exclusao_documentada_e_subtraida_exata` | Fato sobre a fonte mudou; régua não | **As três asserções de contrato seguem literalmente iguais**: exclusão nomeada, `excluido_por_contrato > 0`, `fechamento_confere is True`. Só o `status` mudou |

O último é o **terceiro fato consecutivo** a mudar sob o mesmo caso — ponto
exato → intervalo → não identificado — em ~24 h. Se isso parecer teste que
persegue o resultado em vez de fixar contrato, é objeção legítima e eu gostaria
de ouvi-la.

**Contagem:** 18 casos escritos, **+15 líquidos** (1.938 → 1.953). Por arquivo:
piloto 115 → **122**, prontidão 17 → **25**, sensibilidade 10 → **10** (dois
reescritos).

---

## 4. Onde a própria correção decide por julgamento

Sete pontos. Nenhum é medição; todos são escolha minha, e cada um pode estar
errado numa direção diferente.

### 4.1 `limite_demonstravel=False` em TODA rubrica — corrigi demais?

É a decisão que zerou a série. Ninguém declara limite demonstrável, então todo
período com rubrica não identificada virou `nao_identificado`.

**Meu raciocínio:** declarar exigiria afirmar que a linha é de sinal único e que
nenhum componente de sinal oposto compensa juros dentro dela — afirmação sobre
composição contábil, que é o item 2 da sua sequência. Sua revisão diz que
*"ausência de crédito nas parcelas restantes também não é certificado positivo
de sua natureza contábil"*, e tratei isso como valendo para toda rubrica.

**A objeção que eu faria:** existem rubricas onde o limite talvez seja
trivialmente demonstrável — uma linha "Outros" num quadro cujo total é despesa e
cujos componentes são todos despesa. Se ao menos uma merecer a declaração, a
série não precisava ter colapsado inteira, e eu transformei uma correção em
apagão.

**O conjunto a adjudicar é pequeno e está aqui, para a objeção ser acionável.**
São **cinco** rubricas não identificadas em toda a série estendida (trimestre
isolado):

| Rubrica | n | períodos credores | Emissor |
|---|---:|---:|---|
| `juros_mercados_interbancarios` | 47 | **1** | Itaú |
| `juros_outros_sem_composicao` | 46 | **2** | Itaú |
| `juros_emprestimos_e_repasses` | 24 | **1** | Bradesco |
| `juros_outras_sem_composicao` | 19 | 0 | BB |
| `juros_titulos_emitidos_e_outras_obrigacoes` | 10 | 0 | BB |

As três primeiras têm período credor observado, o que **por si já refuta**
sinal único — para essas, `False` não é escolha conservadora, é o que os dados
mostram. As duas do BB nunca vêm credoras, e são as candidatas reais à
adjudicação: se ambas se demonstrarem de sinal único pela nota, **o BB volta a
ter série** e a conclusão "a série colapsou inteira" fica exagerada em um
emissor de três.

Reproduzir a tabela:

```bash
python -c "
import json,collections
from decimal import Decimal
por=collections.defaultdict(lambda:[0,0])
for l in open('artefatos/b_dfc_01j/extensao/fatos.jsonl'):
    d=json.loads(l); p=str(d.get('periodo'))
    if d.get('tratamento')!='nao_identificado' or len(p)!=6 or p[4]!='T': continue
    por[d['conceito']][0]+=1
    if Decimal(d['valor'])>0: por[d['conceito']][1]+=1
for k,(n,c) in sorted(por.items(), key=lambda x:-x[1][0]): print(f'{k:46} n={n:3d} credores={c}')
"
```

**Não adjudiquei nenhuma das duas** porque isso exige ler a nota e é o item 2 da
sua sequência — mas o silêncio a esse respeito era uma escolha, e agora está
quantificado em vez de vago.

### 4.2 `limite_inferior = 0` quando não há teto — isso descarta verdade

Quando o estado é `nao_identificado`, publico **os dois** limites como zero e
guardo o piso em `soma_incluidas_quando_sem_limite`.

**Por quê:** publicar `[S, S]` faria qualquer leitor ver ponto exato, que é
justamente o defeito.

**A objeção:** J é **de fato** ≥ S, então `limite_inferior = 0` é falso, e um
campo chamado "limite inferior" com valor falso é a mesma classe de problema
que a etiqueta de unidade do F8. Preservei a informação, mas num campo que
ninguém lendo o schema antigo vai procurar. Um `limite_superior = null` com
`limite_inferior = S` talvez fosse mais honesto — **não implementei** porque
mudaria o schema para todos os consumidores, e preferi errar para o lado de
não publicar número usável.

### 4.3 F2 tornado visível, mas a população NÃO foi reconstruída

G1 agora reporta 0% de horizonte contratual. Mas os alvos continuam sendo
`base → trimestre seguinte`, não `base → q(D)`.

**Por quê:** construir q(D) é o item 4 da sua sequência e exige protocolo novo;
fazer isso agora seria redefinir a população depois de ver o resultado.

**A objeção:** reportar "0% certificado" sobre uma população construída pela
regra errada é medir a coisa certa no lugar errado. O número é honesto como
diagnóstico e **inútil** como certificação, e o JSON deveria talvez dizer isso
mais forte do que diz no campo `o_que_mudou`.

### 4.4 F9b: elejo no suporte comum, mas meço poder no suporte próprio

A eleição do melhor baseline passou a usar a interseção. Mas
`mae_melhor` e o bootstrap de poder continuam no suporte **próprio** do
eleito.

**Por quê:** eleger com régua justa, depois descrever o eleito no seu suporte
inteiro.

**A objeção:** é mistura de suportes outra vez, só num lugar diferente — e o
seu F3 já diz que essa conta de poder mede a quantidade errada de qualquer
jeito. Pode ser que o certo seja medir tudo no suporte comum, ou não medir.

### 4.5 F3 NÃO foi corrigido, e isso é deliberado

Seu item 1 lista F1, F2, F7–F11 — **F3 não está lá**, e eu não o toquei.
`melhoria_minima_detectavel_relativa` **continua** reamostrando a dispersão da
perda do baseline em vez da diferença pareada de perdas.

Hoje é inócuo: a população é vazia e o campo sai sob reprova em aberto. **Mas
se a série voltar, o número volta com o defeito** — e ele não tem contraprova
na suíte. Redesenhar a inferência é o seu item 6. **Registro como dívida
declarada**, não como coisa feita. F4, F5, F6 e F12 também não foram tocados:
são invalidação de pré-registro e interpretação, não código.

### 4.6 `B3_EXECUTADO` é flag manual

Constante de módulo em `False`. Quem integrar a série SGS 432 tem de virá-la à
mão; nada verifica automaticamente que B3 existe. Há teste que trava o `False`
atual e obriga a revisar o caso quando mudar — mas é convenção, não mecanismo.

### 4.7 Derivado nunca herda limite demonstrável

Fato derivado por `A − M9` recebe `limite_demonstravel=False` fixo, mesmo que a
rubrica de origem venha a declarar `True`.

**Por quê:** compõe duas incertezas, e seu F6 diz que a comparabilidade dos
operandos não está adjudicada. **A objeção:** se a rubrica for genuinamente de
sinal único, a diferença de dois períodos dela continua de sinal único, e a
regra pode ser mais forte do que precisa.

---

## 5. O que eu afirmo NÃO ter feito

Cada linha é verificável, e cada uma é uma coisa que sua revisão proibiu.

| Proibição | Como conferir |
|---|---|
| Não reincluí rubrica duvidosa em J | `grep -n "_NAO_IDENT" scripts/piloto_bancos_dfc.py` — as duas cambiais seguem lá |
| Não declarei `limite_demonstravel=True` em rubrica alguma | `grep -n "limite_demonstravel=True" scripts/` — só em fixture de teste |
| Não aumentei tolerância nem mexi em limiar | `grep -n "^LARGURA_MAXIMA\|^G2_RUIDO\|^G3_MELHORIA\|^T1_AMPLITUDE\|^T2_LACUNA\|^FATOR_DE_PODER\|^MINIMO" scripts/auditar_prontidao_b_dfc_01j.py` — inalterados |
| Não acessei `corpus/holdout_2T2026` | não lido em nenhum comando desta onda |
| Não herdei número do pré-registro invalidado como validação | a correção se declara **diagnóstico**; §4.5 acima registra F4 intocado |
| Não treinei modelo, não chamei API paga | tudo lido de disco |
| Não mutei painel, corpus ou PDF | `git status --porcelain corpus/` vazio · `cvm.duckdb` `43e31d9f…` · `cvm_treino.duckdb` `c1a60445…` |
| Não alterei o denominador dos 25 pacotes | `auditoria.json`: `pacotes_no_escopo = 25` |

---

## 6. O que refutaria a correção

Em ordem de gravidade. Qualquer um destes é motivo para eu refazer, não para
ajustar texto.

1. **Uma terceira implementação de limites** que eu não achei, ainda publicando
   intervalo fabricado.
2. **Uma entrada que passe pelos três ramos de `construir_j`** e produza
   intervalo ou ponto com desconhecida não declarada.
3. **Uma asserção existente enfraquecida** que eu tenha justificado como "fato
   mudou" quando era a régua cedendo — especialmente o caso do Bradesco (§3).
4. **`limite_demonstravel=False` universal ser over-correction demonstrável** —
   isto é, uma rubrica das 15 cujo limite se demonstre com a nota já em disco
   (§4.1). Isso não restauraria o veredito, mas mostraria que o apagão da série
   foi maior que o necessário.
5. **A conta de F9b/poder estar incoerente** de um jeito que mude alguma
   conclusão (§4.4).
6. Qualquer número deste pacote que **não reproduza**.

**Limite deste pacote:** ele verifica que os seis defeitos de código saíram e
que o efeito medido é o declarado. **Não** certifica os dados restantes, não
adjudica composição de rubrica nenhuma, e não avança um milímetro nos itens 2–7
da sua sequência. O treino continua suspenso e o pré-registro continua
invalidado pela própria regra.
