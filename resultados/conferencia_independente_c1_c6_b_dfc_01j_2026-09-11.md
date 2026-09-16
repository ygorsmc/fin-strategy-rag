# Conferência independente da implementação de C1–C6 — B-DFC-01J

**Data:** 2026-09-11. **Natureza:** revisão de implementação, não novo debate
de viabilidade econômica nem autorização para treinar.

**Veredito: correções centrais confirmadas; encerramento integral ainda não
aprovado.** As seis entradas originais deixaram de reproduzir os defeitos.
C1–C4 atendem às correções específicas propostas; C5 corrige a linhagem e as
contagens, mas não liga a independência à decisão de G0; C6 põe a sensibilidade
em quarentena, mas não impede G3 de aprovar um cálculo explicitamente inválido
se B3 for habilitado. Há ainda um caso de amostra insuficiente que derruba G3,
**preexistente**, não regressão desta onda.

**Estado real preservado:** zero observações elegíveis de J, interrupção em G0,
nenhum treino do candidato. Suíte completa: **1.973 testes passando, zero skips,
30 warnings, 105,49 s**. Testes verdes confirmam os contratos que cobrem; não
eliminam as lacunas de integração demonstradas abaixo.

## 1. Escopo e fontes examinadas

- [Contratos congelados antes da implementação](contratos_correcao_c1_c6_b_dfc_01j_2026-09-11.md), especialmente C4, C5-B e C6.
- [Relatório da implementação](implementacao_c1_c6_b_dfc_01j_2026-09-11.md), incluindo alterações de testes e hashes.
- [Conferência com as contraprovas originais](conferencia_parecer_b_dfc_01j_2026-09-11.md), §§2.1–2.2; seus dois blocos executáveis foram reexecutados.
- [Revisão anterior](revisao_conferencia_parecer_b_dfc_01j_2026-09-11.md), para distinguir pendências antigas de alterações desta onda.
- `scripts/auditar_prontidao_b_dfc_01j.py`, `scripts/piloto_bancos_dfc.py`,
  `scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py` e os três arquivos de testes correspondentes.
- JSON/JSONL da extensão e da prontidão; `MEMORY.md`, avisos locais de estado
  do `AGENTS.md` §3.17, de `becos_sem_saida.md` §C-bis e dos relatórios anteriores.

A sessão principal conferiu C5, artefatos, diferenças entre versões, testes e
documentação. O agente `auditor_conformidade_c1_c6`, em contexto separado e
somente leitura, conferiu C1–C4 e C6 no auditor de prontidão. Seus achados foram
recebidos antes de fechar este parecer; as duas contraprovas principais abaixo
foram executadas também pela sessão principal. Não é dupla adjudicação
financeira de rubricas: nenhuma nova leitura de PDF para identificar J foi feita.

Nesta revisão foram escritos somente este relatório e a atualização do
`MEMORY.md`. Sem correções de implementação, alteração de testes, regeneração
em disco dos artefatos, API paga, consulta à web, treino do candidato, commit ou
acesso aos dados do holdout.

## 2. Achados que impedem declarar a onda inteiramente encerrada

### R-C6 — P2: a quarentena de poder não governa a aprovação de G3

**Fonte:** `scripts/auditar_prontidao_b_dfc_01j.py:668–704`;
`tests/test_prontidao_b_dfc_01j.py:631–654`; contrato C6, regra comum aos dois
consumidores e critério 5.

O retorno de G3 contém `calculo_de_poder_invalidado_por="F3"` e um aviso
correto, mas sua decisão continua sendo:

```python
"aprovado": relativa <= G3_MELHORIA_DETECTAVEL and B3_EXECUTADO
```

No caso sintético com três emissores e erros iguais, a conta antiga produz
melhoria detectável relativa zero. Com B3 desabilitado, G3 reprova; habilitando
B3 **somente em memória**, G3 aprova, embora continue declarando F3. A
contraprova da sessão principal fornece previsões de B0 e B3 no mesmo suporte;
não depende de comparar suportes diferentes. Não simula uma implementação
econômica válida de B3: testa a independência entre as duas travas.

Também não aparecem `decidivel`, `clusters_suficientes` e `ressalva`, campos
que a regra de C6 diz valer em `_poder` **e** `gate_g3`. Na sensibilidade, eles
estão implementados corretamente.

**Distinção importante:** o critério 5 preserva B3 como veto independente. Isso
não torna dispensável o veto de F3. É necessário que **B3 ausente bloqueie
mesmo sem F3, e F3 bloqueie mesmo com B3 presente**. Acrescentar esses bloqueios
não exige redesenhar a estatística de poder nesta onda.

**Impacto atual:** nenhum treino indevido foi autorizado. `B3_EXECUTADO=False`
e a população vazia mantêm o bloqueio real. A fórmula de aprovação já existia;
o defeito desta entrega é ter declarado a quarentena concluída sem integrá-la
à decisão.

**Correção mínima a solicitar:** manter os números como diagnóstico invalidado,
completar o estado explícito de C6 em G3 e impedir aprovação enquanto F3 estiver
vigente. Testar o comportamento com B3 ausente e presente; verificar apenas que
a constante atual é `False` não testa a conjunção dos vetos.

### R-C5 — P2: independência é informada por G0, mas não condiciona a certificação

**Fonte:** `scripts/auditar_prontidao_b_dfc_01j.py:317–340`;
`scripts/piloto_bancos_dfc.py:3382–3394`;
`tests/test_piloto_bancos_dfc.py:1613–1635`; contrato C5-B.

A separação entre fechamentos aritméticos e verificações independentes está
correta no produtor. No consumidor, porém, a nova contagem é apenas copiada
por `.get(...)`. O predicado de aprovação de G0 verifica divergências, presença
de J e rubricas suspeitas; não verifica a existência de evidência independente.

Com duas observações sintéticas de J, nenhuma divergência nem rubrica suspeita,
um fechamento por construção e **zero verificações independentes**, G0 devolve
`aprovado=True`. Retirando inteiramente o novo campo, também aprova e publica
`identidades_conferidas_independentes=None`.

**Limite da conclusão:** os critérios enumerados de C5 exigem a marcação da
linhagem e as duas contagens, e essas entregas passaram. O contrato não fixou
percentual mínimo de cobertura independente nem exigiu verificar todas as
identidades anuais. Esta revisão **não inventa esses limiares**. A lacuna é
entre a alegação de certificação protegida no consumidor e a implementação
meramente informativa: nem o caso extremo de nenhuma evidência independente
é distinguido. Se a intenção era apenas telemetria, isso deve ser declarado
explicitamente, sem atribuir ao gate uma proteção que ele não executa.

**Impacto atual:** as duas contagens reais são 24, a lista de fechamentos por
construção está vazia e G0 reprova por outros motivos. Não foi encontrado um
caso real erroneamente certificado nesta rodada.

**Correção mínima a solicitar:** explicitar o requisito de evidência
independente que G0 certifica e aplicá-lo; ausência de campo obrigatório ou
ausência total dessa evidência não pode produzir a certificação anunciada.
Não substituir esse requisito por exigir indiscriminadamente todas as
identidades possíveis. Acrescentar contraprova com contagens diferentes e
outra com campo ausente, exercitando **a decisão**, não só o JSON atual.

## 3. Resíduo preexistente, separado das correções C1–C6

### R-SUPORTE — P2: eleito com um único erro derruba o relatório

**Fonte:** `scripts/auditar_prontidao_b_dfc_01j.py:601` e `:972–982`.

Há três emissores na população, B0 cobre os três e outro baseline cobre uma
única observação do emissor A. Este vence no suporte comum. G3 executa
`statistics.stdev(todos)` sobre seu único erro e levanta:

```text
StatisticsError: stdev requires at least two data points
```

Isso ocorre antes de devolver a contagem corrigida de C4-B. `_medir` captura
`ReprovaEmAberto`, não `StatisticsError`; logo essa configuração interrompe a
produção do relatório, em vez de registrar amostra insuficiente e preservar os
gates anteriores.

O auditor independente executou a mesma entrada na cópia anterior e na atual:
**ambas falham**. A sessão principal reproduziu a falha atual e verificou no
diff que a chamada já existia. Portanto **não é regressão de C4**, nem motivo
para retratar sua correção de contagem. Deve permanecer como dívida explícita
de robustez antes de certificar populações novas. Tratá-la como insuficiência
amostral não exige adotar um novo método de poder.

## 4. O que efetivamente foi confirmado

| Contrato | Verificação independente | Conclusão delimitada |
|---|---|---|
| C1 — empates | Constante com rótulos alternados ou agrupados dá amplitude 0; empates não são divididos; permutações preservam o resultado. | Correção confirmada. Não altera os limiares de T1. |
| C2 — unidade | Loader converte 1.000 milhares e 1 milhão para 1.000.000 de reais, preserva origem e produz y=0; testes de unidade ausente/desconhecida passam. | Correção confirmada. Não identifica J nem resolve ausência de limites. |
| C3 — q(D) | Para D=02/05/2024, T2/2024, T3/2024, T4/2024 e T1/2025 resultam F/T/F/F; bordas de trimestre verificadas. | Correção confirmada. Não reconstrói a população PIT. |
| C4-A — disponibilidade | Antecedentes cujo desfecho só fica público depois de D, ou sem data, são recusados; exemplos disponíveis continuam utilizáveis. | Correção confirmada. |
| C4-B — emissores | A contagem corresponde aos emissores efetivamente presentes no erro do eleito, não à população total. | Correção confirmada; caso de um único erro continua sendo dívida preexistente. |
| C5 — linhagem/contagens | Acumulado derivado deixa de ser independente; operando é nomeado; parcelas derivadas também são recusadas. Contagens reais reproduzidas. | Produtor confirmado; proteção da decisão de G0 pendente, R-C5. |
| C6 — quarentena | Na sensibilidade, 16/60 permanecem publicados, com `decidivel=False` e ressalva F3. G3 publica o marcador. | Parcial: G3 ainda pode aprovar F3 e não implementa todo o estado combinado, R-C6. |

Além dos casos do parecer, o auditor isolado testou **100 distribuições de
empates × 25 permutações** para C1. A sessão principal verificou nove tamanhos
de população, de 25 a 1.000, com grande grupo empatado e cauda desigual:
nenhuma linha perdida nem valor igual dividido entre faixas.

A conferência das identidades foi recalculada a partir dos fatos atuais e
reproduziu exatamente os **51 registros** de `extensao/conferencias.jsonl`:

- 17 identidades anuais não verificáveis, nenhuma certificação anual;
- 12 semestrais e 12 de nove meses conferidas e independentes;
- outras cinco semestrais e cinco de nove meses não verificáveis;
- resumo: 24 fechamentos, 24 independentes, zero fechamentos por construção.

Não se deve somar os não verificáveis como certificados. Essa reprodução
confere a lógica e o artefato; não substitui adjudicação da natureza financeira
das parcelas de J.

## 5. Reproduções adicionais sem mutação de dados

Executar na raiz com o ambiente local. As saídas abaixo descrevem os defeitos
atuais, **não os resultados que os testes de correção deverão exigir**.

```bash
.venv/bin/python - <<'PY'
import json
import math
from types import SimpleNamespace
from unittest.mock import patch
from scripts import auditar_prontidao_b_dfc_01j as a

# R-C5: isola o consumidor; não altera o resumo nem reativa J real.
real = json.loads(a.RESUMO_EXTENSAO.read_text())
for estado in ('zero_independentes', 'campo_ausente'):
    resumo = dict(
        real, identidades_conferidas=1, identidades_divergentes=[],
        rubricas_com_conformidade_nao_demonstrada=[],
    )
    resumo['identidades_que_fecham_por_construcao'] = [{
        'cd_cvm': 'A', 'ano': '2024', 'identidade': 'T1+T2 = S1',
        'operandos_derivados': ['S1 (despesa_juros_total)'],
    }]
    if estado == 'zero_independentes':
        resumo['identidades_conferidas_independentes'] = 0
    else:
        resumo.pop('identidades_conferidas_independentes')
    leitor = SimpleNamespace(read_text=lambda **_: json.dumps(resumo))
    with patch.object(a, 'RESUMO_EXTENSAO', leitor):
        g = a.gate_g0({
            'observacoes_de_J': 2, 'descartados_sem_fechamento': 0,
        })
    print('G0', estado, g['aprovado'],
          g['identidades_conferidas_independentes'])

def alvos(y):
    return [a.Alvo(
        cd, '2024T1', '2024T3', y, y, y, 1e6, 1e6 * math.exp(y),
        '2024-05-02', '2024-11-01', 0.,
    ) for cd in 'ABC']

# R-C6: B0 e B3 têm o mesmo suporte; flag alterada só durante o teste.
ys = alvos(.1)
prev = {b: {(r.cd_cvm, r.periodo_base): 0. for r in ys}
        for b in ('B0', 'B3')}
for b3 in (False, True):
    with patch.object(a, 'B3_EXECUTADO', b3):
        g = a.gate_g3(ys, prev)
    print('G3', b3, g['aprovado'], g['calculo_de_poder_invalidado_por'],
          {k: g.get(k, 'AUSENTE') for k in
           ('decidivel', 'clusters_suficientes', 'ressalva')})

# R-SUPORTE: um único erro no baseline eleito.
ys = alvos(.9)
prev = {
    'B0': {(r.cd_cvm, r.periodo_base): 0. for r in ys},
    'BX': {('A', '2024T1'): .8},
}
try:
    a.gate_g3(ys, prev)
except Exception as exc:
    print('G3_UM_ERRO', type(exc).__name__, str(exc))
PY
```

Saída medida:

```text
G0 zero_independentes True 0
G0 campo_ausente True None
G3 False False F3 {'decidivel': 'AUSENTE', 'clusters_suficientes': 'AUSENTE', 'ressalva': 'AUSENTE'}
G3 True True F3 {'decidivel': 'AUSENTE', 'clusters_suficientes': 'AUSENTE', 'ressalva': 'AUSENTE'}
G3_UM_ERRO StatisticsError stdev requires at least two data points
```

## 6. Testes, artefatos e rastreabilidade

### Execuções desta conferência

```bash
CREWAI_STORAGE_DIR="$(mktemp -d /tmp/bdfc-conferencia-implementacao.XXXXXX)" .venv/bin/python -m pytest -q --tb=short
```

Resultado: **1.973 passed, 30 warnings, 105,49 s; zero skips**. O diretório
temporário apenas acomoda o armazenamento de teste fora do caminho padrão
não gravável; nenhum teste foi alterado para resolver o ambiente.

```bash
.venv/bin/python -m pytest -q tests/test_prontidao_b_dfc_01j.py::TestContratosC1aC6 tests/test_piloto_bancos_dfc.py::TestContratoC5Linhagem
```

Resultado: **20 passed, 0,14 s**. O auditor isolado também rodou os 41 testes
de prontidão, todos aprovados. Os warnings da suíte completa não foram
suprimidos; sua contagem distinta da execução do implementador não é tratada
como regressão por si só.

Em execução somente em memória, `auditar_prontidao_b_dfc_01j.executar()` e
`sensibilidade_rubricas_suspeitas_b_dfc_01j.executar()` reproduziram exatamente
os respectivos `gates.json` e `sensibilidade.json` atuais.

### Comparação anterior × atual

Foi localizado e lido o snapshot de trabalho anterior à implementação em
`/tmp/claude-1000/-home-ygor-Antigravity-Projects-fin-strategy-rag/b3cd8830-7fb5-446d-ae1b-5242b33bd763/scratchpad/`.
Na primeira parte desta conferência, foram conferidos os hashes anteriores e
os diffs completos dos três scripts e três testes, além dos artefatos da
extensão. **O snapshot temporário deixou de estar acessível na retomada**;
não é um anexo durável deste relatório. O parecer registra a comparação já
realizada, não promete que outro agente poderá abrir esse caminho. Não houve
cópia de diretório privado nem publicação de cookies ou outros arquivos de
sessão. Para futuras ondas, conservar diff/snapshot dos arquivos em escopo em
local estável e sem credenciais melhora a reprodutibilidade.

Resultado da comparação, desconsiderando apenas `gerado_em` quando presente:

- Fatos, série J, derivações, vintages e manifesto da extensão: sem alteração
  de conteúdo; a população não foi reativada.
- Conferências: 51 registros preservados; acrescentada a lista de operandos
  derivados em 24 registros verificáveis, vazia nos casos reais atuais.
- Resumo: acrescentadas contagem independente e lista de fechamentos por
  construção; nenhum novo caso certificado.
- Gates: acrescentadas as duas informações de C5 em G0, sem mudança do veto.
- Sensibilidade: mudanças de quarentena, preservadas perdas e quantidades
  numéricas. Além dos quatro campos destacados no relatório de implementação,
  há `leitura_dos_dois_campos_acima`, explicação adicional compatível com C6.
- Painéis consultável e de treino: hashes inalterados.

**Testes alterados:** não houve remoção de asserções no piloto. Na prontidão,
uma chave de diagnóstico foi renomeada e o caso positivo de B2 recebeu datas
compatíveis com a nova guarda, preservando o resultado esperado. Na
sensibilidade, asserções que tratavam a conta invalidada como decidível foram
substituídas por quarentena, conforme contrato explícito; as verificações de
perda descritiva permaneceram. Não identifiquei redução de limiar para aprovar
o candidato. As lacunas são de cobertura: C5-B lê um artefato cujas duas
contagens coincidem; C6 em G3 verifica marcador e constante, não ambos os vetos.

### SHA-256 da implementação efetivamente conferida

Os seis hashes coincidem com o relatório do implementador e foram conferidos
novamente após a retomada. Servem para identificar o objeto desta revisão,
não para provar a semântica financeira dos dados.

```text
2353ba5593a902306edb70ec73dbc70d20d71601d30a2bb33219f6cd2d4f076d  scripts/piloto_bancos_dfc.py
23dd96791c034b065921ea3cda862f470cb47d30b9006cfa10efee26ffa360b1  scripts/auditar_prontidao_b_dfc_01j.py
f38516be03973acc35b71300e1efc6bfdedef0442abc50c8cb84b41f6df59e2a  scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py
9aa68cbd25719afccecedfaab0feacbd91c21fbdf214e9c779963d16329cfd17  tests/test_piloto_bancos_dfc.py
0dfe80111b61ca09988cc5f0996b6023243dea2ee9f11d06016aa8d1da7a1445  tests/test_prontidao_b_dfc_01j.py
5b4193b0607555d645b4f6a872fb682611ca956ab5c630955ca72d63b67141c7  tests/test_sensibilidade_b_dfc_01j.py
43e31d9f150e535f1ab20576d9aacf1a53b83ecc5424ca7d48ba50781e4cef18  artefatos/cvm.duckdb
c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b  artefatos/cvm_treino.duckdb
```

## 7. Handoff e limites do próximo trabalho

1. Fechar R-C6: quarentena efetiva na decisão de G3, sem remover o veto de B3
   nem apresentar a fórmula atual como poder válido. Não exige redesenho agora.
2. Fechar R-C5: definir e implementar o que G0 certifica sobre independência;
   testar falta de evidência e campo ausente, além do produtor de contagens.
3. Tratar R-SUPORTE como insuficiência amostral explícita que não apaga os
   gates já medidos; registrá-lo como dívida anterior, não regressão.
4. Reexecutar contraprovas e suíte; conferir artefatos, hashes e diferenças de
   testes. Atualizar os avisos documentais para **aprovação parcial** desta
   conferência, sem apagar as retratações históricas.

A sincronização documental R1 já incorporou avisos úteis aos relatórios
antigos. Ainda há formulações de conclusão integral — no relatório desta
implementação e no aviso do AGENTS.md §3.17 — que precisam incorporar este
parecer. O MEMORY.md foi atualizado agora, substituindo tanto os seis defeitos
antigos como se ainda estivessem intocados quanto a indicação de revisão
independente pendente. Os documentos do implementador não foram reescritos
silenciosamente por esta revisão.

**Fora desta conferência:** reconstrução point-in-time da população, redesenho
estatístico de poder, implementação econômica de B3, adjudicação das rubricas
do BB e representação versionada de limites ausentes. Os 198 registros com J
não identificado e limites/largura zero continuam sendo dívida conhecida de
schema, protegida hoje pelo status. Corrigir instrumentos não produz novos
rótulos nem valida a hipótese econômica.

O próximo piloto documental por família de subordinadas continua sendo uma
pista, não uma conclusão de viabilidade. **Nenhum resultado desta conferência
autoriza treino imediato, mudança do produto ou uso do holdout 2T2026.**
