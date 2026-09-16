# Implementação de C1–C6 — relatório

**Data:** 2026-09-11. **Contratos:**
[registrados antes de implementar](contratos_correcao_c1_c6_b_dfc_01j_2026-09-11.md).
**Origem:** [parecer de 11/09](parecer_correcao_b_dfc_01j_2026-09-11.md) §2 e
[revisão da conferência](revisao_conferencia_parecer_b_dfc_01j_2026-09-11.md) §5.

> **⚠️ RESSALVA POSTERIOR (2026-09-11, mesma data) — leia antes de citar este
> relatório.** A frase abaixo, "os seis contratos foram fechados", **era forte
> demais** e a [conferência independente desta
> implementação](conferencia_independente_c1_c6_b_dfc_01j_2026-09-11.md) mediu
> onde: C1–C4 confirmados, mas **C5 e C6 tinham sido fechados só no PRODUTOR**.
> Os dois publicavam o campo de estado novo e deixavam o predicado de decisão
> do consumidor intacto — G0 aprovava com zero evidência independente, e G3
> aprovava declarando o próprio cálculo de poder inválido, se B3 fosse
> habilitado. Veredito correto da onda C1–C6: **aprovação parcial.**
>
> Os dois achados (R-C5, R-C6), mais uma dívida preexistente de robustez
> (R-SUPORTE), foram implementados em seguida:
> [contratos](contratos_correcao_rc5_rc6_b_dfc_01j_2026-09-11.md) e
> [implementação](implementacao_rc5_rc6_b_dfc_01j_2026-09-11.md), +12
> contraprovas, suíte **1.985**. Nada abaixo foi reescrito; as medições de
> C1–C6 continuam válidas para o que mediram.
>
> **A lição de método, que vale para qualquer contrato futuro deste projeto:**
> contrato que cria um campo de estado só está cumprido quando existe
> contraprova exercitando a **decisão** governada por ele. Asserção sobre o
> JSON publicado prova o produtor e não prova nada sobre o consumidor.

**Resultado:** os seis contratos foram fechados, com 20 contraprovas novas. As
seis entradas que o parecer usou para demonstrar os defeitos **deixaram de
reproduzi-los**. G0 segue reprovado, a população elegível segue vazia e
**nenhum modelo foi treinado.**

---

## 1. Placar: as seis contraprovas do parecer, antes e depois

Mesmo comando, mesma entrada, medido nesta onda:

| | Entrada do parecer | Antes | Agora |
|---|---|---|---|
| **C1** | constante, rótulos agrupados | **1,0** | **0,0** |
| **C2** | 1.000 milhares → 1 milhão | **−6,907755…** | **0,0** |
| **C3** | D=02/05/2024 → T2/T3/T4/T1 | F, T, **T, T** | F, T, **F, F** |
| **C4** | antecedentes públicos só em 2025 | **B1=0,2 B2=0,5** | **None, None** |
| **C5** | acumulado derivado | `independente=True` | `independente=False` |
| **C6** | volatilidade, 16 e 60 emissores | `decidivel=true` | `decidivel=false` |

---

## 2. O que mudou em cada contrato

### C1 — os quintis passam a ser formados por VALOR

A 1ª versão desempatava pelo evento; a 2ª, pela posição original. **As duas
usavam algo que não é a variável** para criar a ordem. Agora o corte de quintil
é estendido até o fim do grupo de empate: um mesmo valor nunca atravessa duas
faixas, e variável constante vira **uma** faixa com amplitude 0,0.

**Por que 0,0 e não erro:** variável que não ordena nada não fabrica baseline
nenhum, e é exatamente isso que T1 pergunta. Amplitude zero é a medição correta,
não ausência de medição.

A invariância à permutação agora é **medida**, não afirmada: 25 embaralhamentos
distintos devolvem a mesma amplitude. O parecer avisa que randomizar empates
esconderia o problema atrás de uma semente em vez de resolvê-lo; não foi o
caminho tomado.

### C2 — a conversão de unidade entrou no consumidor

F8 corrigiu a **etiqueta** na exportação e deixou o **consumidor** dividindo os
números crus. A série mistura de verdade: **108 registros em milhares** (Bradesco,
BB) e **90 em milhões** (Itaú).

`carregar_populacao` agora converte para **reais** antes de qualquer aritmética,
e `Observacao` carrega a unidade de origem — converter e esquecer a procedência
impediria conferir a conversão depois.

**Unidade ausente ou desconhecida levanta `ErroDeUnidade`, que deliberadamente
NÃO herda de `ReprovaEmAberto`.** Essa distinção é o ponto: `ReprovaEmAberto` é
capturada por `_medir` e vira "gate reprovado com motivo", um estado legítimo do
mundo. Defeito de dado virando veredito plausível é pior que a execução cair. Há
contraprova para a não-herança.

### C3 — horizonte virou igualdade com q(D)

A 2ª versão exigia `início do alvo > D` e corrigiu o trimestre já em curso,
**deixando passar o oposto**: para D = 02/05/2024 aprovava 2024T4 e 2025T1, que
pulam q(D). Prever três trimestres à frente é outra tarefa, com outra
dificuldade; misturar horizontes torna o erro médio incomparável.

Entrou `primeiro_trimestre_apos(d)` — a função que faltava. Sem ela só dava para
perguntar "começa depois de D?", satisfeito por infinitos trimestres. O campo de
diagnóstico do G1 foi renomeado de `alvo_ja_iniciado_quando_a_base_saiu` para
`fora_do_horizonte_q_de_d`, que cobre os dois lados do defeito.

### C4 — duas partes

**(A) Disponibilidade.** B1 e B2 só usam antecedente cujo **desfecho** já era
conhecido na data de decisão do alvo corrente. Antecedente sem data é
inutilizável — ausência de data nunca vira "estava disponível".

**A guarda não zerou o caso legítimo:** os mesmos quatro antecedentes com datas
anteriores a D continuam alimentando B1 e B2 (0,2 e 0,5). Há contraprova dos dois
lados.

**(B) Contagem.** `gate_g3` publicava `emissores_independentes = 3` ao lado de
`trimestres_por_emissor = {'A': 2}`. Agora conta os emissores que **entram no
erro do baseline eleito**, e nomeia os que ficaram de fora em
`emissores_fora_do_erro_do_eleito`.

**Declarado como NÃO feito:** reconstruir a população point-in-time. A função
passou a **recusar** o que não estava disponível; a série não foi refeita.

### C5 — linhagem de todos os operandos

`derivadas` inspecionava `escolhido[:-1]`, que exclui justamente o acumulado —
o operando que pode ter sido derivado das parcelas. É a mesma tautologia do F11,
na outra ponta da identidade. Agora inspeciona `escolhido` inteiro e **nomeia
qual** operando é derivado, em `operandos_derivados`.

O resumo passou a publicar **duas** contagens: `identidades_conferidas` (fecham) e
`identidades_conferidas_independentes` (fecham **e** não têm operando derivado),
mais a lista `identidades_que_fecham_por_construcao`. G0 lê a segunda.

**Hoje as duas valem 24 e a lista está vazia** — como o contrato previu. A
separação existe para que uma identidade futura que feche por construção não
volte a ser contada como conferida.

### C6 — quarentena que publica e invalida

O pacote de 10/09 declarou F3 adiado e disse que a conta ficara inócua por não
haver população. **Não ficou:** os cenários de volatilidade continuavam
produzindo `decidivel=true`, `ressalva=null` e "16 emissores" com selo de válido.

Seguindo a R1 do revisor (*"preferir 'o cálculo continua publicado, mas está
invalidado' a 'deixou de existir'"*), os números **ficam** no artefato:

- `clusters_suficientes` — o booleano que `decidivel` significava até aqui
- `calculo_de_poder_invalidado_por: "F3"`
- `decidivel` — **False em todo cenário**, porque agora exige clusters **e** cálculo válido
- `ressalva` — nunca `null`; nomeia F3 e acrescenta a falta de clusters quando for o caso

Vale nos **dois** lugares que fazem a conta: `_poder` da sensibilidade e `gate_g3`.

---

## 3. Testes: o que foi acrescentado e o que foi substituído

**20 contraprovas novas** — 16 em `test_prontidao_b_dfc_01j.py` (41 casos, era
25) e 4 em `test_piloto_bancos_dfc.py` (126, era 122).

**Auditoria de asserções removidas**, por diff contra o snapshot do início:

| Arquivo | Asserções removidas |
|---|---|
| `test_piloto_bancos_dfc.py` | **nenhuma** |
| `test_prontidao_b_dfc_01j.py` | 1 — `g1["alvo_ja_iniciado_quando_a_base_saiu"]`, só o **nome** do campo mudou |
| `test_sensibilidade_b_dfc_01j.py` | 4 — a substituição declarada no contrato C6 |

As quatro da sensibilidade eram `decidivel is True` / `ressalva is None` para
três clusters, e `emissores_necessarios` cair e permanecer acima de 3. **Todas
afirmavam uma conclusão que F3 invalidou** — eram o que mantinha o "16/60" com
selo de válido. Foram trocadas por asserções de que a quantidade sai **marcada
como inválida**: asserção fraca sobre número sem validade vira asserção forte
sobre a marcação.

**A perda descritiva continua asseverada.** As duas asserções sobre MAE e
dispersão do Itaú permanecem intactas — o parecer é explícito que preservar a
perda descritiva não exige apresentar sua dispersão como poder.

Um teste teve a **fixture** corrigida sem tocar a asserção:
`test_F9_B2_opina_quando_os_quatro_existem` usava as datas padrão de `_alvo`,
que punham o desfecho dos antecedentes **depois** da decisão. A asserção (0,25)
é a mesma; o que entrou foram as datas que a fixture nunca declarou. Sem elas o
teste não distinguia "B2 opina" de "B2 opina com informação do futuro".

---

## 4. Artefatos: mudaram só onde foi declarado

Regenerados pelos `main()` (`estender`, auditor, sensibilidade). Diff contra o
snapshot do início, ignorando `gerado_em`:

| Artefato | Mudança |
|---|---|
| `extensao/fatos.jsonl` | **byte-idêntico** |
| `extensao/j_por_periodo.jsonl` | **byte-idêntico** |
| `extensao/derivacoes.jsonl` | **byte-idêntico** |
| `extensao/vintages.jsonl` | **byte-idêntico** |
| `extensao/conferencias.jsonl` | +`operandos_derivados` em 24 dos 51 |
| `extensao/resumo.json` | +2 campos de C5-B; **o resto idêntico** |
| `prontidao/gates.json` | +2 campos de C5-B; **o resto idêntico** |
| `prontidao/sensibilidade.json` | só os 4 campos de quarentena de C6 |

**Determinismo conferido:** `executar()` do auditor e da sensibilidade reproduzem
os JSONs gravados.

---

## 5. As quatro condições de falha do contrato

| Condição | Medido |
|---|---|
| 1. Alguma correção reativar a série | **Não.** População 0 observações, 0 alvos; G0 reprovado; veredito `NAO AUTORIZA TREINO` |
| 2. Artefato mudar fora do declarado | **Não.** §4 |
| 3. Teste removido para acomodar correção | **Não.** §3, auditado por diff |
| 4. Contraprova do parecer ainda reproduzir | **Não.** 6/6 deixaram de reproduzir (§1) |

**Não-mutação:** `corpus/` limpo; `cvm.duckdb` e `cvm_treino.duckdb` com
SHA-256 inalterados. Sem rede, sem API paga, sem acesso ao `holdout_2T2026`.

---

## 6. O que continua aberto — e não foi tocado

| Item | Estado |
|---|---|
| **F3 de verdade** (redesenho do poder para ganho pareado) | Aberto. A quarentena impede a leitura errada; **não conserta a conta** |
| Reconstrução point-in-time da população | Aberto; protocolo novo |
| Representação de ausência de limites (4.2 do parecer) | Aberto. Os 198 registros seguem exportando largura zero |
| Adjudicação das duas rubricas do BB | Aberto; item 2 da sequência |
| **Sincronização documental R1** | **Aberto.** Linha 972 do AGENTS.md, `becos_sem_saida.md` §C-bis e as retratações do piloto/extensão ainda apresentam estado superado |
| Constante `"unidade": "milhares_de_reais"` em `piloto_bancos_dfc.py:2062` | **Achado lateral desta onda.** É o mesmo padrão de F8, no registro de classificação DFC. Hoje está correto por acaso (a fonte é o BB, que publica em milhares); fica declarado, não corrigido — está fora de C1–C6 |

**R1 é a mais urgente das seis**, porque o AGENTS.md manda consultar
`becos_sem_saida.md` antes de propor investigação nova: um agente pode seguir o
estado superado sem nunca abrir o parecer.

---

## 7. Suíte e reprodução

```text
1973 passed, 28 warnings in 101.54s — zero skips
```

**1.953 → 1.973**: exatamente as 20 contraprovas novas. Nenhum teste
preexistente foi removido.

```bash
# suíte completa
CREWAI_STORAGE_DIR="$(mktemp -d /tmp/bdfc-c1c6.XXXXXX)" .venv/bin/python -m pytest -q --tb=short

# só as contraprovas dos seis contratos
.venv/bin/python -m pytest -q \
  tests/test_prontidao_b_dfc_01j.py::TestContratosC1aC6 \
  tests/test_piloto_bancos_dfc.py::TestContratoC5Linhagem

# regenerar os artefatos (reescreve artefatos/b_dfc_01j/, nada mais)
.venv/bin/python scripts/piloto_bancos_dfc.py estender      # ~4 min, lê PDFs locais
.venv/bin/python scripts/auditar_prontidao_b_dfc_01j.py
.venv/bin/python -m scripts.sensibilidade_rubricas_suspeitas_b_dfc_01j
```

> **Nota de execução:** a sensibilidade importa `scripts.…` e precisa rodar como
> **módulo** (`-m scripts.sensibilidade_…`); chamá-la pelo caminho do arquivo
> levanta `ModuleNotFoundError`. O comando publicado no parecer §6 usa
> `executar()` em memória e não esbarra nisso.

## 8. Rastreabilidade (recomendação R2 do revisor)

Snapshot tirado **antes** de qualquer edição, com os seis fontes copiados
integralmente para permitir diff. Os hashes de partida conferem com os
publicados no §4 da revisão da conferência — ou seja, parti exatamente da
versão que o revisor auditou:

```text
724500b7…  scripts/piloto_bancos_dfc.py
79d9de4e…  scripts/auditar_prontidao_b_dfc_01j.py
d4ec9951…  scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py
9ff2f399…  tests/test_piloto_bancos_dfc.py
665f5475…  tests/test_prontidao_b_dfc_01j.py
52450e83…  tests/test_sensibilidade_b_dfc_01j.py
```

Separando o que o revisor pediu para não misturar:

- **Declaração do executor:** não alterei nada fora dos seis fontes, dos
  artefatos de `artefatos/b_dfc_01j/` e dos dois documentos desta onda.
- **Verificação de conteúdo:** diff integral dos seis fontes contra o snapshot;
  diff campo a campo dos oito artefatos; `corpus/` limpo; SHA-256 dos dois
  painéis conferido antes e depois.
- **O que não tenho:** os arquivos seguem **untracked**, então não existe
  versão no HEAD para um `git diff` integral. O snapshot desta sessão cobre o
  intervalo desta sessão, não a história anterior.
- **Testes:** 1.973 é medição **desta** rodada, não herdada.

Hashes **depois** (identificam a versão a conferir):

```text
2353ba5593a902306edb70ec73dbc70d20d71601d30a2bb33219f6cd2d4f076d scripts/piloto_bancos_dfc.py
23dd96791c034b065921ea3cda862f470cb47d30b9006cfa10efee26ffa360b1 scripts/auditar_prontidao_b_dfc_01j.py
f38516be03973acc35b71300e1efc6bfdedef0442abc50c8cb84b41f6df59e2a scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py
9aa68cbd25719afccecedfaab0feacbd91c21fbdf214e9c779963d16329cfd17 tests/test_piloto_bancos_dfc.py
0dfe80111b61ca09988cc5f0996b6023243dea2ee9f11d06016aa8d1da7a1445 tests/test_prontidao_b_dfc_01j.py
5b4193b0607555d645b4f6a872fb682611ca956ab5c630955ca72d63b67141c7 tests/test_sensibilidade_b_dfc_01j.py
```

Painéis inalterados nos dois snapshots:
`43e31d9f…` (cvm.duckdb) e `c1a60445…` (cvm_treino.duckdb).
