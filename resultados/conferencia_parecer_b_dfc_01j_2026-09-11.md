# Conferência do parecer de 11/09 e correção da linha 25 — pacote de revisão

**Data:** 2026-09-11. **Escopo desta sessão:** reproduzir por conta própria os
seis contratos abertos pelo
[parecer de 11/09](parecer_correcao_b_dfc_01j_2026-09-11.md) e corrigir **uma
linha** do plano. **Nenhum defeito foi corrigido, nenhum código foi tocado,
nenhum modelo foi treinado.**

Este documento existe para que outro agente possa (a) refazer as seis
reproduções sem depender da minha palavra e (b) julgar se a única alteração
feita é fiel ao que a evidência sustenta.

---

## 1. O que esta sessão fez, na íntegra

| | |
|---|---|
| Li | `MEMORY.md` e `resultados/parecer_correcao_b_dfc_01j_2026-09-11.md` |
| Reproduzi | os seis contratos C1–C6 do parecer — **6/6 conferem** |
| Alterei | **uma linha** do `AGENTS.md` (linha 1221, linha 25 da tabela do §7) |
| Não alterei | código, testes, artefatos, painéis, corpus, gates, pré-registros |
| Não rodei | a suíte completa — nenhum arquivo `.py` mudou (prova no §5) |
| Custo | zero: sem rede, sem API paga, sem acesso ao `corpus/holdout_2T2026` |

**A conclusão desta sessão é uma só e é negativa:** o parecer está correto nos
seis pontos, e o `AGENTS.md` afirmava encerramento que a evidência não
sustenta. Corrigir a linha **não fecha nenhum dos seis contratos.**

---

## 2. As seis reproduções — comandos e saídas exatas

### 2.1 Bloco do próprio parecer (C1, C2, C3, C4, C6)

Rodado verbatim, a partir da raiz do repositório. Ele **verifica primeiro** que
`executar()` do auditor e da sensibilidade reproduzem os JSONs gravados, e só
depois mede — isto é, não escreve artefato nenhum:

```bash
.venv/bin/python - <<'PY'
import io, json, math
from unittest.mock import patch
from pathlib import Path
from scripts import auditar_prontidao_b_dfc_01j as a
from scripts import sensibilidade_rubricas_suspeitas_b_dfc_01j as s

root = Path('artefatos/b_dfc_01j')
assert a.executar() == json.loads((root/'prontidao/gates.json').read_text())
assert s.executar() == json.loads((root/'prontidao/sensibilidade.json').read_text())
print('C1 (alternado):', a.amplitude_por_quintis([1.0]*50, [0,1]*25)[0])
print('C1 (agrupado) :', a.amplitude_por_quintis([1.0]*50, [0]*25+[1]*25)[0])

def alvo(cd, base, futuro, y=.1, db='2024-05-02', df='2025-02-01'):
    return a.Alvo(cd,base,futuro,y,y,y,1000.,1000.*math.exp(y),db,df,0.)
print('C3:', [(q, a.gate_g1([alvo('A','2024T1',q)])['aprovado'])
             for q in ['2024T2','2024T3','2024T4','2025T1']])

rows = [dict(cd_cvm='A', periodo=q, status='identificado',
    fechamento_confere=True, base_temporal='original', disponivel_em=d,
    limite_inferior=str(v), limite_superior=str(v), unidade=u)
    for q,d,v,u in [('2023T1','2023-05-01',1000,'milhares_de_reais'),
                    ('2023T2','2023-08-01',1,'milhoes_de_reais')]]
class SerieMemoria:
    def is_file(self): return True
    def open(self, **kwargs):
        return io.StringIO('\n'.join(json.dumps(r) for r in rows))
with patch.object(a, 'SERIE', SerieMemoria()):
    obs,_ = a.carregar_populacao()
    ys,_ = a.montar_alvos(obs)
    print('C2: y para mesmo montante real =', ys[0].y_centro)

hist = [alvo('A',f'2023T{q}',a.proximo_trimestre(f'2023T{q}'),q*.2,
             db='2023-05-01',df='2025-01-01') for q in [1,2,3,4]]
current = alvo('A','2024T1','2024T3',.15,df='2024-11-01')
b = a.previsoes_dos_baselines(hist+[current])
print('C4: B1/B2 =', b['B1'][('A','2024T1')], b['B2'][('A','2024T1')])
for nome in ['volatilidade_conforme','volatilidade_estado_anterior_nao_conforme']:
    c = s.executar()[nome]
    print('C6:', nome, c['decidivel'], c['ressalva'], c['emissores_necessarios'])
PY
```

**Saída obtida — confere com a documentada no parecer §6:**

```text
C1 (alternado): 0.0
C1 (agrupado) : 1.0
C3: [('2024T2', False), ('2024T3', True), ('2024T4', True), ('2025T1', True)]
C2: y para mesmo montante real = -6.907755278982137
C4: B1/B2 = 0.2 0.5
C6: volatilidade_conforme True None 16
C6: volatilidade_estado_anterior_nao_conforme True None 60
```

As duas linhas `assert` passaram: os JSONs em disco **são** o que as funções
produzem hoje. Nenhum artefato foi reescrito — os `main()` não foram chamados
(mtimes no §5 provam).

### 2.2 C5 — reprodução que o parecer descreve mas não instrumenta

O parecer afirma o defeito de `conferir_identidade_trimestral` sem dar comando.
Construí a contraprova. **Duas armadilhas na montagem**, registradas porque
custaram tentativa:

1. a função filtra `fato.conceito != "despesa_juros_total"` — qualquer outro
   conceito sai vazio e parece "sem defeito";
2. `origem_periodo` usa `"propria"` / `"comparativa"` / `"derivada"`; passar
   `"original"` cai no ramo de fonte comum, não no de vintage original.

```bash
.venv/bin/python - <<'PY'
from decimal import Decimal
from scripts import piloto_bancos_dfc as p

def fato(periodo, valor, origem="comparativa"):
    return p.Fato(
        fato_id=f"f{periodo}", pacote_id="pk", fonte_id="dA",
        conceito="despesa_juros_total",
        rotulo_original="Total", periodo=periodo, coluna_indice=0,
        texto_original=str(valor), valor=Decimal(valor),
        unidade="milhares_de_reais", valor_reais=Decimal(valor)*1000,
        pagina_pdf=1, pagina_impressa=1, nota="n1", tratamento="incluida",
        motivo="", base_contabil="ifrs", perimetro="consolidado",
        evidencia="x"*60, origem_periodo=origem, cd_cvm_do_fato="019348",
        disponivel_em="2024-05-02", limite_demonstravel=False,
    )

# T1 e T2 comparativos; S1 DERIVADO — a identidade fecha por construção
fatos = [fato("2024T1", -100), fato("2024T2", -100),
         fato("2024S1", -200, "derivada")]
for c in p.conferir_identidade_trimestral(fatos):
    print({k: c[k] for k in
           ("identidade","base","confere","independente","motivo_nao_independente")})
PY
```

**Saída obtida:**

```text
{'identidade': 'T1+T2 = S1', 'base': 'comparativa_de_dA', 'confere': True,
 'independente': True, 'motivo_nao_independente': None}
```

Confere com o parecer. A causa está em
[`piloto_bancos_dfc.py:3062-3066`](../scripts/piloto_bancos_dfc.py#L3062-L3066):
`derivadas` inspeciona `escolhido[:-1]`, que **exclui o acumulado** — exatamente
o operando que pode ser derivado das parcelas.

### 2.3 C6 — a parte que o parecer atribui aos testes

Confirmado por leitura direta:
[`test_sensibilidade_b_dfc_01j.py:157-160`](../tests/test_sensibilidade_b_dfc_01j.py#L157-L160)
exige `limpo["emissores_necessarios"] < com[...]` e `> MINIMO_DE_CLUSTERS`. Os
testes **trancam no contrato** a conclusão que a revisão original invalidou.

### 2.4 Placar

| Contrato | Alegação do parecer | Reproduzi? |
|---|---|---|
| C1 / F7 | amplitude 1,0 para variável constante com rótulos agrupados | ✅ exato |
| C2 / F8 | `y = −6,907755278982137` para o mesmo montante em unidades diferentes | ✅ exato |
| C3 / F2 | G1 aprova 2024T4 e 2025T1 para D = 02/05/2024 | ✅ exato |
| C4 / F9 | B1=0,2 e B2=0,5 com histórico indisponível em D | ✅ exato |
| C5 / F11 | `confere=True, independente=True` com acumulado derivado | ✅ exato |
| C6 / F3 | `decidivel=true`, `ressalva=null`, 16 e 60 | ✅ exato |

**6 de 6.** Não encontrei nenhum ponto em que o parecer exagere ou erre.

---

## 3. A única alteração: `AGENTS.md`, linha 1221

### 3.1 Por que ela estava errada

A linha 25 da tabela do §7 dizia **"Corrigidos os seis defeitos de código"** e
**"o instrumento de medição estava quebrado"** (passado). Lida em 11/09, as duas
afirmam encerramento — e o §2 acima mostra seis contratos abertos.

Pior, a linha afirmava que *"a exigência de ~16 emissores **deixou de existir
como medição**"*. O C6 mostra que **não deixou**: `sensibilidade.json` publica
`decidivel: true`, `ressalva: null`, `emissores_necessarios: 16`.

### 3.2 Antes → depois (texto integral do que mudou)

> **Nota de auditabilidade:** a linha 25 **não existe no HEAD** (`git show
> HEAD:AGENTS.md | grep '^| 25 |'` devolve vazio) — ela é trabalho não commitado
> desta onda. Portanto `git diff` **não** exibe este antes/depois; ele mostra a
> linha inteira como adicionada. O par abaixo é a substituição literal aplicada.

**Trecho retirado:**

```text
Corrigidos os seis defeitos de código
(`resultados/correcao_instrumento_b_dfc_01j_2026-09-10.md`, +15 contraprovas,
suíte 1.953): **J como intervalo 15 → 0**, série utilizável **69 pares → 0**,
gate decisivo volta a ser **G0 reprovado**. O G2 de 1,0464, a exigência de ~16
emissores e as "15 de 15 identidades anuais" **deixaram de existir como
medições**.
```

**Trecho posto no lugar:**

```text
A correção de 10/09 (`resultados/correcao_instrumento_b_dfc_01j_2026-09-10.md`,
+15 contraprovas, suíte 1.953) fechou o achado central — **J como intervalo
15 → 0**, série utilizável **69 pares → 0**, gate decisivo volta a ser **G0
reprovado** —, e o G2 de 1,0464 e as "15 de 15 identidades anuais" **deixaram
de existir como medições**. Mas a conferência de 2026-09-11
(`resultados/parecer_correcao_b_dfc_01j_2026-09-11.md`) **aprovou só em parte e
o item 1 não está concluído**: seis contratos seguem abertos (C1–C6), todos
reproduzidos — F7 ainda atribui amplitude 1,0 a variável constante quando os
rótulos vêm agrupados em vez de alternados; o consumidor do auditor descarta
`unidade` e faz 1.000 milhares ≠ 1 milhão (`y = −6,9078` para o mesmo
montante); G1 aceita qualquer trimestre posterior a D, não q(D); B1/B2 não
conferem a disponibilidade dos antecedentes; identidade com acumulado derivado
sai `independente=True`; e a sensibilidade **ainda publica 16/60 emissores com
`decidivel=true` e `ressalva=null`** — a exigência de ~16 **não** deixou de
existir como medição, continua publicada com selo de válida, e os testes da
sensibilidade a trancam no contrato.
```

**Segunda substituição, no abre da célula:**

```text
❌ **NÃO AUTORIZA, e o instrumento de medição estava quebrado.**
→
❌ **NÃO AUTORIZA, e o instrumento de medição ainda não está fechado.**
```

### 3.3 O que deliberadamente **não** mudou na linha

Continuam como estavam, porque continuam verdadeiros: o `❌ NÃO AUTORIZA`; a
descrição do achado F1 original; os três números da correção (15 → 0, 69 → 0,
G0 decisivo); a baixa do G2 1,0464 e das "15 de 15"; a invalidação do
pré-registro pela regra do §7; e a reabertura **da investigação**, não do
treino, por família econômica.

### 3.4 Integridade estrutural da tabela

```bash
grep "^| 25 |" AGENTS.md | tr -cd '|' | wc -c     # 5
for n in 21 22 23 24; do grep "^| $n |" AGENTS.md | tr -cd '|' | wc -c; done  # 5 5 5 5
```

Cinco pipes, igual às linhas vizinhas: a célula não foi partida.

---

## 4. O que eu **não** fiz — e que outro agente não deve presumir feito

| Item | Estado |
|---|---|
| C1–C6 | **abertos.** Nenhum foi corrigido. O parecer §5 é a lista do que falta |
| `AGENTS.md` linha **972** | **ainda errada.** Carrega o mesmo *"a exigência de ~16 emissores deixaram de existir como medições"*, dentro da retratação do §3.17. As duas ocorrências vinham do mesmo erro; o usuário pediu só a linha 25, e eu parei aí |
| `MEMORY.md` | **não tocado nesta sessão.** A versão vigente foi escrita por quem produziu o parecer; conferi que é fiel a ele e não achei o que corrigir |
| Suíte completa | **não re-rodada.** Ver §5 — nenhum `.py` mudou, então o 1.953 do parecer continua valendo por construção, não por nova medição minha |
| `becos_sem_saida.md` e as retratações dos relatórios do piloto/extensão | **não revisados** contra o parecer. Lacuna conhecida, fora do pedido |
| Treino, holdout, API paga, painéis, corpus | **nada.** §5 |

---

## 5. Não-mutação — verificável

```bash
git status --porcelain corpus/          # vazio
sha256sum artefatos/cvm.duckdb artefatos/cvm_treino.duckdb
ls -l --time-style=+%F_%T AGENTS.md scripts/piloto_bancos_dfc.py \
  scripts/auditar_prontidao_b_dfc_01j.py \
  scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py \
  tests/test_*_b_dfc_01j.py tests/test_piloto_bancos_dfc.py \
  artefatos/b_dfc_01j/prontidao/*.json
```

Medido agora:

```text
corpus/ .......................... limpo
cvm.duckdb ....... 43e31d9f150e535f1ab20576d9aacf1a53b83ecc5424ca7d48ba50781e4cef18
cvm_treino.duckdb  c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b
```

Os dois hashes são **os mesmos** publicados no pacote de 10/09.

**Mtimes — a prova de que só o `AGENTS.md` mudou hoje:**

```text
2026-09-11_13:36:30  AGENTS.md                                      ← esta sessão
2026-09-10_19:52:28  scripts/auditar_prontidao_b_dfc_01j.py
2026-09-10_19:58:04  scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py
2026-09-10_20:04:55  scripts/piloto_bancos_dfc.py
2026-09-10_20:00:43  tests/test_sensibilidade_b_dfc_01j.py
2026-09-10_20:03:16  tests/test_prontidao_b_dfc_01j.py
2026-09-10_20:04:55  tests/test_piloto_bancos_dfc.py
2026-09-10_20:08:21  artefatos/b_dfc_01j/extensao/*.json[l]
2026-09-10_20:31:49  artefatos/b_dfc_01j/prontidao/gates.json
2026-09-10_20:31:49  artefatos/b_dfc_01j/prontidao/sensibilidade.json
```

Todo `.py` e todo artefato são de **10/09**, anteriores a esta sessão. Rodar as
reproduções do §2 não os reescreveu.

`git diff --stat` mostra seis arquivos modificados, mas **cinco deles são de
ondas anteriores ainda não commitadas** (`.gitignore`, `MEMORY.md`,
`becos_sem_saida.md` e dois relatórios de 27/08). Só o `AGENTS.md` foi tocado
hoje, e dentro dele só a linha 1221.

---

## 6. Como falsificar esta conferência

Cada item abaixo, se verdadeiro, derruba parte do que afirmo:

1. **Qualquer uma das seis reproduções do §2 sair diferente** na sua máquina.
   Aí ou o parecer erra, ou meu ambiente diverge — nos dois casos a linha 25
   está apoiada em base instável.
2. **O `assert` inicial falhar** (`executar() != JSON em disco`). Significaria
   que os artefatos de 10/09 não são mais o que o código produz, e todo o §2
   mede outra coisa.
3. **Algum trecho que mantive na linha 25 (§3.3) não se sustentar.** Em
   particular: o G2 de 1,0464 e as "15 de 15" realmente deixaram de existir?
   Eu afirmo que sim e **não re-medi isso nesta sessão** — herdei do pacote de
   10/09. É o ponto mais fraco da linha corrigida.
4. **A linha 25 ainda afirmar encerramento** em alguma leitura que eu não
   enxerguei. O teste: alguém que leia só a tabela do §7 consegue concluir que
   o instrumento está pronto para certificar população reconstruída? Se sim,
   a correção falhou no seu objetivo.
5. **Eu ter mudado algo além da linha 1221.** §5 dá os mtimes; o contraditório
   é `git diff AGENTS.md` e conferir que as demais seções são de ondas
   anteriores.
6. **A lacuna da linha 972 ser mais grave do que declarei** — se a retratação
   do §3.17 for a que outro agente lê primeiro, deixá-la errada anula o efeito
   de ter corrigido a tabela.

## 7. O que eu gostaria que o revisor decidisse

- A linha 25 agora **descreve** os seis contratos abertos. Isso é suficiente,
  ou o estado da etapa 25 deveria mudar de rótulo (hoje `❌ NÃO AUTORIZA`) para
  algo que diga também "instrumento em correção"?
- A linha 972 deve ser corrigida na mesma onda, ou entra no lote de C1–C6?
- Corrigir C1–C6 exige decidir **política de empate** (C1) e **política de
  ausência de limites** (§3 do parecer, item 4.2). Nenhuma das duas é
  refatoração — são escolhas de contrato. Devem ser pré-registradas antes de
  implementar?

---

**Estado ao fim desta sessão:** G0 segue reprovado, J elegível segue zero,
nenhum modelo foi treinado, o denominador documental de 25 pacotes está
preservado e o holdout `2T2026` não foi acessado. Nada aqui autoriza treino,
mudança no produto ou reativação da série.
