# Correção do instrumento de medição — B-DFC-01J (2026-09-10)

**Origem:** [revisão independente](revisao_independente_b_dfc_01j_2026-09-10.md),
§6 item 1 — *"Corrigir primeiro o instrumento de medição. Acrescentar
contraprovas F1, F2, F7–F11 aos testes; corrigir sem enfraquecer asserções
existentes."*

**Executado:** os seis defeitos de código. **Não executado:** os itens 2–7 da
sequência (piloto de subordinadas, novo estimando, relógio do experimento,
M0/M1, materialidade, treino exploratório) — dependem de decisão e de
pré-registro novo, não de correção.

**Nenhum modelo foi treinado. Nenhuma chamada paga. Holdout não acessado.**
Suíte: **1.953 casos, zero skip** (era 1.938; +15 contraprovas).

---

## 1. O que a correção fez com o veredito

O veredito não mudou de rótulo — continua `NÃO AUTORIZA TREINO` — mas **mudou de
razão, e para pior**. A revisão dizia que "G0 não está demonstrado como
resolvido, apesar de o programa devolver aprovação". Corrigido o programa, G0
**reprova**, e a série utilizável desaparece.

| | Antes (2026-09-09/10) | Depois da correção |
|---|---:|---:|
| J como **ponto** exato (25 pacotes) | 0 | 0 |
| J como **intervalo** | **15** | **0** |
| J **não identificado** | 9 | **24** |
| Pares emissor-trimestre na extensão | **69** | **0** |
| Gate decisivo | G1 (72,0%) | **G0** |
| G0 | ✅ aprovado | ❌ **reprovado** |
| G2 ruído/sinal | 1,0464 | **não existe mais** |
| Identidade anual `T1+…+T4 = A` | "15 de 15" | **0 conferidas, 17 não verificáveis** |

**A leitura honesta:** o trabalho documental não produziu uma série de J
mensurável. O que parecia um rótulo ruidoso (G2 1,0464) era um rótulo
**inexistente** cujos limites o programa fabricava.

---

## 2. F1 — o defeito que zerou a série

`construir_j` somava as parcelas incluídas `S` e o residual líquido `U` das
rubricas não identificadas, e declarava J entre `min(S, S+U)` e `max(S, S+U)`.
Isso pressupõe que a parcela de **juros** dentro do desconhecido esteja entre
zero e o residual líquido — e **não está**, quando a linha mistura juros com
variação cambial: câmbio tem os dois sinais e pode compensar juros.

Contraprova da revisão, agora executada como teste:

| Item | Valor com sinal da fonte |
|---|---:|
| Juros incluídos | −100 |
| Rubrica desconhecida | +30 |
| Total declarado | −70 |

O programa fechava a nota **exato** e declarava `[70, 100]`. Mas a desconhecida
pode ser **−20 de juros + 50 de ganho cambial**, e então J = **120**, fora do
intervalo, com o fechamento ainda perfeito. Segunda contraprova: duas
desconhecidas de +30 e −30 têm residual líquido **zero** e produziam
`identificado` com J como ponto exato.

### A correção

`Rubrica` e `Fato` ganharam `limite_demonstravel: bool = False`. O default é o
ponto: só produz intervalo a rubrica que **declara** ser de sinal único, e que
naquele período de fato veio devedora. Três estados, não dois:

- `identificado` — exige **ausência** de rubrica não identificada (antes exigia
  residual líquido nulo, que é outra coisa);
- `limitado` — todas as não identificadas com limite demonstrável e devedoras;
- `nao_identificado` — qualquer outra situação. Limites saem **zero**, e o piso
  fica em `soma_incluidas_quando_sem_limite`, fora dos campos de limite, para
  que ninguém o use como J.

**Nenhuma rubrica declara `limite_demonstravel=True` hoje**, e é por isso que a
série colapsou. Declarar exigiria adjudicar a composição da linha — trabalho do
piloto por família, item 2 da sequência da revisão. A revisão é explícita:
*"A ausência de crédito nas parcelas restantes também não é certificado
positivo de sua natureza contábil."*

### O defeito estava em DOIS lugares

`sensibilidade_rubricas_suspeitas_b_dfc_01j.py` **reimplementava** a mesma regra
(`min/max(soma, soma+residuo)`) em vez de chamar `construir_j`. Corrigir o
extrator não corrigiu a sensibilidade: ela continuou publicando os intervalos
fabricados até receber a mesma correção. **Lógica duplicada é a razão de o
defeito ter precisado de duas correções**, e vale como aviso para quem mexer.

Consequência: os dois cenários de intervalo colapsam. O `intervalo_conforme`
fica com **0 observações**; o `intervalo_estado_anterior_nao_conforme`, que
devolvia as rubricas suspeitas a J, sobra com **1 emissor**. **Não havia dois
estados a comparar — havia dois conjuntos de limites inventados de tamanhos
diferentes.** A folga de 48× do G2 e o 1,0464 saem de circulação juntos.

---

## 3. Os outros cinco defeitos

### F2 — G1 media ordenação de publicações, não horizonte contratual

O contrato exige o **primeiro trimestre inteiro cujo início seja posterior** à
data em que o J-base ficou público. O gate só checava se a base saiu antes do
alvo. Caso real: Bradesco 2024T1 disponível em **02/05/2024**, par apontando
para 2024T2, que **começou em 01/04/2024** — um mês antes de a base existir.

`gate_g1` passou a medir as duas coisas separadamente
(`fracao_com_datas_em_ordem` × `fracao_certificada`) e a aprovar só pela
segunda, listando em `alvo_ja_iniciado_quando_a_base_saiu` cada par fora do
horizonte. **Não redefini a população** — construir q(D) é o item 4 da
sequência ("refazer o relógio do experimento") e exige protocolo novo.

### F7 — `amplitude_por_quintis` desempatava pelo próprio rótulo

`sorted(zip(valores, eventos))` usa o evento como segunda chave. Uma variável
**constante** recebia amplitude **1,0** — associação perfeita — com quintis
`[0, 0, 0.5, 1, 1]`. Agora o desempate é pela posição original, que não carrega
informação do rótulo: a mesma entrada mede **0,0**. Há contraprova do contrário,
para que a correção não cegue o teste: variável que de fato ordena continua
medindo 1,0.

### F8 — a unidade do JSON era constante

`para_json` gravava `"unidade": "milhares_de_reais"` fixo, divergindo dos fatos
em **90 de 198** registros (o Itaú publica em milhões). O valor numérico sempre
esteve na unidade da publicação; a **etiqueta** mentia, e cruzar emissores por
ela erraria por mil. A unidade agora vem dos fatos, e **unidades mistas dentro
do mesmo período levantam erro** em vez de escolher uma em silêncio.

### F9 — B2 não era a mediana dos quatro trimestres anteriores

Usava `lista[max(0, i-4):i]`: até quatro **linhas disponíveis**, aceitando menos
de quatro e sem exigir adjacência de calendário. Com 2020T1 e 2024T1 na série,
usava 2020T1 para prever 2024T1. Agora exige os quatro trimestres
imediatamente anteriores; faltando um, **B2 não opina**.

E a eleição do melhor baseline comparava MAE em **suportes diferentes** — B0 com
MAE 7 em nove observações perdia para B1 com MAE 2 em três, embora B0 medisse 1
nessas mesmas três. A eleição passou a usar a **interseção** onde todos os
baselines válidos opinam, publicada em `mae_macro_no_suporte_comum`.

### F10 — duas permissões falsas

**T2:** escore que ordena o evento pior que o acaso produzia lacuna pequena por
ser ruim, e o JSON dizia `aprovado: True` ao lado de uma ressalva dizendo "não
leia como aprovação". A ressalva existia, a trava não. Agora
`aprovado = informativo and lacuna < limiar`.

**B3:** o §4 do pré-registro exige o benchmark econômico (meta Selic
*point-in-time*) e diz que sem ele não há aprovação com B0–B2 apenas. A
exigência existia **só como texto no JSON** e não participava da condição de
aprovação. Agora `B3_EXECUTADO = False` bloqueia G3. Nenhuma das duas liberou
esta rodada, que reprova por outros motivos — eram permissões **latentes**.

Registrado também o que a revisão apurou: a série existe em fonte pública
oficial (SGS 432 do BCB), então "não implementado" nunca foi "só existe dado
pago". Não foi integrada aqui.

### F11 — "15 de 15 identidades anuais" não estava no artefato

Medido: `T1+T2 = S1` e `T1+T2+T3 = M9` têm 12 conferidas cada; **`T1+T2+T3+T4 =
A` tem ZERO conferidas e 17 não verificáveis.** E, pior, uma identidade cujo T4
saiu de `A − M9` fecha **por construção** — `M9 + (A − M9) = A` é álgebra, não
contraprova do mapeamento de colunas.

`conferir_identidade_trimestral` passou a gravar `independente` e
`motivo_nao_independente` em **todos** os ramos, inclusive no não verificável,
para que filtrar por esse campo dê a resposta certa sem saber por qual ramo o
registro veio.

---

## 4. Defeito adicional, achado ao rodar a correção

`_medir` — a guarda que impede uma reprova em aberto de apagar os gates
anteriores — cobria **só G3/T1/T2**. Quando a correção do F1 zerou a população,
`gate_g1` levantou `ReprovaEmAberto` e o relatório saiu **sem o G0 que já estava
medido**, com `populacao: None`. Era o mesmo defeito de 2026-09-10, meio
corrigido. Agora cobre G0–T2, e a cadeia publica os seis gates com o motivo de
cada reprova.

---

## 5. Testes: nenhuma asserção enfraquecida

Cinco casos existentes mudaram. **Três afirmavam o defeito** e foram reescritos
com o motivo no docstring; dois tiveram um fato sobre a fonte mudar sob eles.

| Caso | O que era | O que é |
|---|---|---|
| `test_residual_sem_composicao_vira_intervalo_nao_ponto` | exigia intervalo para **qualquer** residual — o defeito F1 | virou `test_residual_COM_limite_demonstravel_vira_intervalo` + dois casos novos para as duas contraprovas |
| `test_p2_sem_total_e_nao_aplicavel_nao_conflito` | supunha `nao_identificado` ⇒ sem total ⇒ P2 não aplicável | mede o critério real (sem total), e um caso novo trava a **independência** entre fechamento e certificado semântico |
| `test_a_conformidade_derrubou_o_rotulo_abaixo_do_sinal` | travava G2 1,0464 × 0,0214 | virou guarda contra o **retorno** do F1: nenhum cenário de intervalo pode publicar razão G2 |
| `test_o_g2_que_passava_era_comprado_pelo_defeito` | travava folga de 48× | virou o caso que mede o colapso do cenário anterior |
| `test_exclusao_documentada_e_subtraida_exata` | Bradesco como `limitado` | Bradesco como `nao_identificado`; as três asserções de contrato (exclusão nomeada, subtraída exata, fechamento confere) **seguem intactas** |

O último caso é o **terceiro fato consecutivo** sobre a mesma fonte a mudar
debaixo dele: era ponto exato, virou intervalo em 09-10, virou não identificado
horas depois. A régua não mudou nenhuma vez.

**Quinze contraprovas novas**, uma por achado, para que voltar atrás quebre a
suíte em vez de voltar em silêncio.

---

## 6. O que NÃO foi feito, e por quê

| Item da sequência da revisão | Estado |
|---|---|
| 1. Corrigir o instrumento | ✅ **este documento** |
| 1-bis. Revisor independente confere a correção | ⬜ **pendente — é o próximo passo** |
| 2. Piloto documental de subordinadas | ⬜ exige inventário e adjudicação; nada aqui o antecipa |
| 3. Decidir o estimando | ⬜ decisão, não correção |
| 4. Refazer o relógio (D, q(D)) | ⬜ exige protocolo novo; F2 só tornou o defeito **visível** |
| 5. M0/M1 e benchmark econômico | ⬜ B3 agora **bloqueia**, mas não foi integrado |
| 6. Materialidade e análise temporal | ⬜ |
| 7. Treino exploratório | ⬜ **não autorizado** |

**Não fiz** nenhuma das coisas que a revisão proibiu: não reincluí rubrica
duvidosa em J, não aumentei tolerância para aprovar resultado existente, não
acessei o holdout 2T2026, não herdei número do pré-registro invalidado como
validação, e não declarei `limite_demonstravel=True` em rubrica alguma para
ressuscitar a série.

**O pré-registro segue invalidado pela própria regra (§7 dele, achado F4):** as
correções mudaram `y` depois da medição. Os números deste documento são
**diagnóstico do instrumento**, não execução de contrato intacto.

---

## 7. Reprodução

```bash
export PYTHONPATH=.
python scripts/piloto_bancos_dfc.py auditar     # 0 ponto · 0 intervalo · 24 não ident.
python scripts/piloto_bancos_dfc.py estender    # 0 pares emissor-trimestre
python scripts/auditar_prontidao_b_dfc_01j.py   # G0 decisivo, seis gates reprovados
python scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py   # cenários colapsam
python -m pytest -q                             # 1.953 passed, zero skip
```

Contraprovas isoladas, sem tocar artefato:

```bash
python -c "
from scripts import auditar_prontidao_b_dfc_01j as a
print('F7 constante ->', a.amplitude_por_quintis([1.0]*50,[0,1]*25)[0])
"
python -m pytest tests/test_prontidao_b_dfc_01j.py::TestContraprovasDaRevisaoIndependente \
                 tests/test_piloto_bancos_dfc.py::TestContraprovasDaRevisaoIndependente -q
```

**Não mutação verificada:** `git status --porcelain corpus/` vazio;
`cvm.duckdb` `43e31d9f…` e `cvm_treino.duckdb` `c1a60445…` inalterados;
holdout não acessado; nenhum PDF alterado.
