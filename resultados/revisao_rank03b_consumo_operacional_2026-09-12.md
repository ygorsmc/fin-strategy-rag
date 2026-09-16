# Revisão independente do Rank 3-B — consumo operacional persistente

**Data de conclusão:** 2026-09-12. Revisão iniciada em 11/09 e concluída após
a retomada. **Objeto:** [validação de 11/09](validacao_rank03b_consumo_operacional_2026-09-11.md),
seu [pré-registro](pre_registro_rank03b_consumo_operacional_2026-09-11.md),
auditor, testes e evidências locais.

**Veredito:** confirmo a parada em G0 e a ausência de avaliação do alvo nesta
rodada. **Não aprovo a alegação de que o auditor implementa integralmente o
pré-registro nem todas as explicações do relatório.** Há problemas reais no
painel, erros na descrição de parte deles e falhas de código que invalidariam
uma retomada sem correção do instrumento.

**O Rank 3-B não foi refutado. Nenhum treino foi autorizado.** Os testes do
alvo/baselines feitos nesta revisão foram exclusivamente sintéticos. Não foi
removida nenhuma observação real para tentar fazer G0 passar.

## 1. Resultado confirmado e correções à leitura dos números

| Item | Publicado em 11/09 | Conferência independente |
|---|---|---|
| Carga não financeira | 22.013 FCO; 22.428 ativos | Reproduzida. São entradas da carga, não observações elegíveis com rótulo. |
| G0.3 | 136 saltos entre trimestres adjacentes; 0,6064% | O programa produz 136, mas quatro pares não são adjacentes. São **132 adjacentes / 22.428 = 0,58855%**, ainda acima de 0,5%. |
| G0.2 | 25 linhas fora de 80–100 dias | Confirmado: **16 períodos curtos e nove semestres derivados**. |
| Grupos mistos | 15 grupos; narrativa de risco de eleger semestre | Confirmados 15 grupos, mas **todos misturam trimestre e período curto**, não semestre. Em **12**, o máximo elege o período curto. |
| Diagnóstico de escala | 137 trocas; 123 com bruto contínuo; 43 companhias | Reproduzido no **painel inteiro**, sem exigir adjacência. Não é o mesmo universo de G0 nem adjudicação individual de 123 erros. |
| T1/T2 e baselines reais | Não medidos | Confirmado: `executar()` retorna depois de G0. Não os medi sobre o painel. |
| Suíte completa | 2.010 casos, zero skip | **2.010 passed, 30 warnings, zero skips, 118,66 s** nesta revisão. |

O ajuste da adjacência não resgata G0. Mesmo ignorando o problema de escala,
as 25 durações fora do contrato já impedem a aprovação. Não há motivo para
trocar esse resultado por rejeição do alvo, tampouco por autorização de treino.

## 2. Achados de implementação, em ordem de risco

### R1 — P1: a carga combina valor e data de fatos diferentes

**Fontes:** `scripts/auditar_rank03b_consumo_operacional.py:151–159` e
`:205–215`; pré-registro §§2 e 5. O agrupamento toma independentemente
`max(valor_reais)`, `min(dt_receb)`, `min(dt_ini_exerc)` e `max(dt_fim_exerc)`.
Esses atributos não necessariamente pertencem à mesma observação financeira.

No universo carregado, encontrei **quatro grupos de FCO e 26 de ativo** nos
quais a data atribuída ao máximo é anterior à primeira recepção de qualquer
linha que contém aquele valor. Não são 30 observações supervisionadas:
são grupos da carga com disponibilidade antecipada artificialmente.

Exemplo real de FCO, `cd_cvm=023507`, ambos rotulados `1T2015`:

| Período exato da linha | FCO em reais | Recepção |
|---|---:|---|
| 10/04/2014–30/06/2014 | −4.337.000 | 21/10/2014 |
| 01/01/2015–31/03/2015 | +19.075.000 | 05/05/2015 |

O loader devolve **+19.075.000 com disponibilidade em 21/10/2014** e intervalo
10/04/2014–31/03/2015. As linhas individuais duram 82 e 90 dias, ambas aceitas
por G0.2. Portanto corrigir só os 25 registros de duração anômala não elimina
esse defeito. O agrupamento anteriormente considerado apenas um problema de
medir duração é também um problema de identidade da observação.

**Correção requerida antes de G1:** selecionar uma linha/vintage com período,
valor e procedência inseparáveis, em vez de montar uma linha pela combinação
de agregações. Resolver colisões do trimestre fiscal e seleção de versão antes
de usar a data para filtrar features. Para derivados, a disponibilidade de
todos os operandos continua sendo requisito separado; um join ao documento
do resultado não certifica sozinho essa linhagem.

**Impacto delimitado:** há defeito real na carga, mas o experimento interrompido
não chegou a transformar essas linhas em avaliação preditiva. Isso não
autoriza chamar a rodada atual de backtest com vazamento medido de desempenho:
nenhum desempenho real foi calculado.

### R2 — P1: G1 não confere o horizonte exato; o histórico pode não ser TTM

**Fontes:** auditor `:364–402`, `:734–747`; pré-registro §§2 e 5.

O código verifica se os quatro períodos **encontrados** são consecutivos, não
se começam em q(D). Contraprova com calendário regular: removendo `3T2019`,
para **D=10/05/2019** aceita **q1=4T2019**. O contrato exige `3T2019`;
ausência desse período exige censura, não deslocamento do horizonte.

No passado ocorre o problema complementar: `passado[-4:]` soma quatro linhas
sem exigir continuidade fiscal. Removendo `4T2018`, em **D=09/08/2019** o
“TTM” aceito soma **2T2018 + 3T2018 + 1T2019 + 2T2019**. São quatro linhas
num intervalo de cinco trimestres. A mesma fragilidade existe em
`passado[-JANELA_SD:]` para as features de oito trimestres.

G1 usa `aprovado = bool(amostra)`: não verifica novamente horizonte, janela,
unicidade ou procedência. Os testes existentes cobrem trimestre faltando
dentro do futuro selecionado, não o primeiro período contratual ausente.

O auditor isolado também reproduziu duas divergências de população:

- duas linhas com a mesma recepção geram duas observações para a mesma chave
  `(companhia,D)`, embora essa seja a unidade declarada;
- `len(passado) < JANELA_SD + 1` exige **nove** antecedentes para componentes
  que usam oito, sem esse corte constar da elegibilidade registrada.

**Correção requerida:** calendário fiscal explícito, q(D) calculado
independentemente da presença de valores, janelas completas consecutivas,
unicidade da chave de decisão e política de histórico documentada. A correção
não é aceitar o primeiro trimestre que por acaso existe.

### R3 — P1: o ranking dos baselines usa o próprio rótulo para desempatar

**Fonte:** auditor `:644`; pré-registro §8.

```python
ordenados = sorted(zip(escores, alvos), reverse=True)
```

Quando há empate no escore, a tupla ordena por `y` decrescente. Isso coloca os
positivos primeiro usando a resposta que o baseline deveria desconhecer.
Contraprova: 100 observações com escores todos iguais e dez positivos:

```text
AUC agregada = 0,5
precisão no top-10% = 1,0
lift = 10,0
```

O resultado foi reproduzido pela sessão principal; o auditor isolado também
reproduziu com 600 observações e 60 positivos. Afeta especialmente B2, que tem
escore discreto. Não é a falha antiga de dividir empates de T1: é vazamento do
rótulo na avaliação de priorização.

**Correção requerida:** desempate independente do desfecho, com política
pré-declarada para empates no corte; publicar cobertura efetiva. Testar escores
constantes e muitos empates. Nenhuma precisão real do Rank 3-B foi invalidada
por isso, pois os baselines não chegaram a rodar sobre o painel.

### R4 — P1/P2: a decisão final não respeita os estados de T1 e dos baselines

**Fontes:** auditor `:624–670`, `:759–775`; pré-registro §§6, 8 e 9.

Há dois erros distintos, demonstrados no consumidor com retornos sintéticos:

| Condição | Resultado atual | Contrato |
|---|---|---|
| T1 levanta insuficiência amostral; T2 passa | `REJEITADO` | `INDECIDÍVEL`, sem reprovação numérica do alvo |
| T1 retorna zona cinzenta inconclusiva; T2 passa | `REJEITADO` | `INDECIDÍVEL` |
| Gates e T1/T2 passam; `medir_baselines` falha com `StatisticsError` | `PRONTO PARA CHALLENGER` | Não autorizar enquanto os quatro triviais não forem medidos |

O primeiro erro está na condição `indecidivel and t1["aprovado"]`: nos casos
citados, T1 não está aprovado justamente por ser inconclusivo. O segundo surge
porque a falha de baselines vira `reprova_em_aberto`, mas não entra na conjunção
de aprovação. São respectivamente risco de falsa rejeição e de falsa prontidão.

Além disso, `medir_baselines` **não implementa os IC95% por companhia nem a
AUC intra por baseline** exigidos pelo §8. B0 publica acerto de prever sempre
zero e cobertura de direção zero, embora a previsão de classe tenha cobertura
integral; não se deve confundir abstenção de ranqueamento com ausência de
previsão de classe. AUC zero também é serializada como `None` por `if auc`.

**Correção requerida:** separar reprovação numérica, insuficiência e falha de
instrumentação; fazer a completude válida dos baselines participar da decisão;
implementar as métricas previstas. A reprodução de prontidão falsa injeta
retornos em memória para isolar o consumidor: não representa aprovação de
nenhum gate real nem implementação de um challenger.

### R5 — P2: T1 conta companhias antes de definir o suporte efetivo

**Fonte:** auditor `:509–526`; pré-registro §6, mínimo de 500 observações e
30 companhias.

O mínimo de companhias é conferido na amostra global. Depois, cada componente
descarta seus `None`, mas não reconta companhias. Com 600 observações e
31 companhias, deixei `fco_ttm_sobre_sd8` disponível em **570 observações de
uma única companhia** e ausente nas demais. T1 aprova esse componente e os
outros, embora aquela medição tenha só um grupo independente.

**Correção requerida:** verificar e publicar o suporte efetivo de cada
componente e baseline, após os filtros de disponibilidade. Não se trata de
aumentar os mínimos: trata-se de aplicar os mínimos registrados aos dados
que realmente entram na estatística.

## 3. Achados sobre G0 e sobre a explicação financeira publicada

### R6 — P2: adjacência e natureza dos períodos foram descritas incorretamente

**Fontes:** auditor `:265–319`; validação §§2–4 e 7.

G0.3 usa pares de linhas consecutivas, sem exigir diferença de ordinal igual
a um. Os quatro falsos “adjacentes” são:

| Companhia | De | Para | Diferença de ordinal |
|---|---|---|---:|
| 003328 | 2T2021 | 4T2024 | 14 |
| 010596 | 1T2012 | 4T2012 | 3 |
| 022624 | 3T2011 | 2T2012 | 3 |
| 023337 | 2T2013 | 3T2014 | 5 |

Excluí esses pares **somente da contagem de auditoria de adjacência**, sem
remover linhas do painel nem executar qualquer teste posterior. Preservando
o denominador registrado de observações, G0.3 ainda reprova: 0,58855% > 0,5%.

As 25 durações de FCO se decompõem em:

| Origem | Dias | Linhas |
|---|---:|---:|
| Arquivado | 12 | 1 |
| Arquivado | 31 | 13 |
| Arquivado | 38 | 1 |
| Arquivado | 41 | 1 |
| Derivado | 183 | 9 |

Os **15 grupos mistos** são a interseção de linhas válidas com linhas **curtas**.
Nenhum deles contém uma das nove linhas de 183 dias. Logo, a frase de que
esses 15 grupos estão contaminados por semestre é incorreta.

Exemplo `022586/1T2025`: a linha da DFP de **dezembro de 2024**, com 31 dias,
traz **52.038.000**; o trimestre janeiro–março de 2025 traz **2.539.000**.
O `max` escolhe dezembro. Isso acontece com a linha curta em 12 dos 15 grupos,
não apenas como possibilidade hipotética.

Já a causa das **nove derivações semestrais** foi confirmada no código comum,
`src/dados_estruturados.py:1263–1298`: o `lag` encontra o período anterior
disponível, sem assegurar que é o trimestre imediatamente anterior.
Exemplo `025887/3T2024`: 19.289.000 de janeiro–setembro menos 1.992.000 de
janeiro–março gera **17.297.000 de abril–setembro**, rotulado trimestral.

**Consequência para o plano de correção:** há três questões, não uma só:
derivação semestral, períodos curtos/colisões de trimestre fiscal e agregação
que escolhe valor/data sem preservar identidade. Corrigir a derivação de
183 dias não resolve os 15 grupos mistos nem o exemplo de R1.

### R7 — P2: diagnóstico de escala não equivale a adjudicação nem a quarentena completa

**Fontes:** auditor `:222–261`, `:313–319`, `:717–728`; validação §§1–2 e 6.

`diagnosticar_escala` usa todo o painel, ao contrário da carga não financeira
de G0, e compara registros sucessivos mesmo com lacunas. A diferença é medida:

| Universo do diagnóstico | Trocas | Bruto contínuo | Companhias com esse sinal |
|---|---:|---:|---:|
| Painel inteiro, pares sucessivos — código publicado | 137 | 123 | 43 |
| Painel inteiro, apenas datas-base em trimestres adjacentes | 135 | 122 | 43 |
| Exclusão estrutural do candidato, pares sucessivos | 135 | 121 | 42 |
| Exclusão estrutural do candidato, apenas adjacentes | 133 | 120 | 42 |

São diagnósticos, não reestimativas de T1 e não universos alternativos para
escolher o resultado mais favorável. Há ainda uma troca fora das duas classes
publicadas: `023299`, junho–setembro de 2013, tinha bruto anterior zero.
Isso explica por que **123 + 13 não soma 137**.

O caso testemunha `003549` foi conferido tanto no painel quanto nos CSVs
primários dentro de `corpus/cvm/itr_cia_aberta_2020.zip` e
`corpus/cvm/dfp_cia_aberta_2020.zip`. Os valores e as etiquetas MIL/UNIDADE
citados no relatório constam de fato desses arquivos. Portanto a alternância
não foi inventada pela conversão do auditor.

Entretanto, continuidade do valor bruto é **sinal de suspeita**, não prova
individual de qual valor/unidade deve ser corrigido. A função não lê uma
segunda demonstração para adjudicar cada célula. Também conta **transições**:
a entrada e a saída de uma única célula problemática podem produzir dois
sinais. A afirmação “123 linhas erradas, publicadas e preservadas” confunde
transições, linhas-fonte e adjudicações. Não atribuir culpa automaticamente
à segunda ponta de todo par, nem chamar a outra classe de redenominações
confirmadas. A redação “aparentemente” precisa ser preservada.

**Quarentena:** o JSON contém totais e até **dez exemplos**, não a relação
completa das 123 transições ou das 43 companhias para adjudicação. Além disso,
`carregar_duracoes` não tem `ORDER BY`; `[:10]` publica subconjuntos diferentes
em reexecuções. Reproduzi os totais e o veredito, mas **não o JSON exato**:
somente `g0_2_exemplos` diferiu na comparação com o arquivo publicado.

**Correção requerida:** distinguir universo, transição e célula; publicar a
lista completa, ordenada e identificável de casos a adjudicar, com datas,
origem/versão e hashes pertinentes. Preservar a rodada invalidada. A origem
primária foi conferida no exemplo, mas **as 43 companhias não foram
adjudicadas nesta revisão**.

A possível propagação para a etapa 10 exige análise de dependências e
sensibilidade próprias. Não se demonstrou aqui que toda métrica da etapa 10
está errada: razões podem cancelar uma escala comum, enquanto diferenças e
variáveis de porte podem não cancelar. Não certificar nem invalidar a etapa
inteira por extrapolação deste diagnóstico.

## 4. Qualidade dos testes e ressalvas de método

As 25 contraprovas passam. Confirmam a conjunção dos dois semestres negativos,
o bloqueio atual em G0, a invariância de empates de valores e exemplos de
disponibilidade. **Não comprovam integralmente os consumidores posteriores.**

- Os dois testes de `TestVeredito` chamam o painel real, que para em G0; não
  exercitam os estados de insuficiência, zona cinzenta ou baselines ausentes.
- `assert faixa["valor_minimo"] != faixa["valor_maximo"] or True` é tautológico
  (`tests/test_rank03b_consumo_operacional.py:87`). O mesmo teste contém depois
  uma asserção útil entre faixas; não é correto dizer que o teste inteiro não
  verifica nada. Retirar a tautologia não substitui as contraprovas faltantes.
- A presença de `DefeitoDeIntegridade` e o teste de sua hierarquia não demonstram
  seu uso: a classe não é levantada. O fluxo real publica G0 reprovado e a CLI
  retorna 2. Essa saída preserva o bloqueio, mas não deve ser descrita como
  proteção efetivamente exercitada apenas porque a classe existe.
- G0.4 não tem saída própria, mas `valor_reais` é `NOT NULL` no schema real;
  consultei as contas usadas e encontrei zero nulos. **Não classifico como
  falha atual de nulos** o filtro `IS NOT NULL` ignorando essa restrição.

**Ressalva metodológica, não novo limiar:** o algoritmo de empates pode formar
faixas `[400,1,1,1,97]` em 500 observações; o auditor isolado demonstrou
amplitude 1,0 determinada pelos grupos unitários. Ele não separa valores
empatados, como exige o precedente, mas isso não garante faixas estáveis.
Não há mínimo por faixa no contrato: esta revisão não inventa um nem muda a
regra depois de medir o alvo. Antes de outro protocolo, explicitar a
interpretação e a incerteza de tais faixas é questão metodológica pertinente.

Do mesmo modo, viés para cima não torna uma rejeição estatística automaticamente
mais robusta: ele pode elevar a frequência de cruzar o limiar. Pode-se manter
uma política conservadora de **não autorizar treino**, sem confundi-la com
evidência mais forte de que o alvo é mecanicamente inválido. Nenhum limiar
vigente foi alterado, e nenhum T1 real foi calculado nesta revisão.

## 5. Reproduções executáveis, sem escrita no painel

### 5.1 Medição real de G0, adjacência, duração e colisão temporal

O bloco abaixo lê o painel e imprime as evidências. Não chama `principal()`
nem escreve sobre `artefatos/rank03b/auditoria.json`.

```bash
.venv/bin/python - <<'PY'
import json
from collections import Counter
from pathlib import Path
import duckdb
from scripts import auditar_rank03b_consumo_operacional as a
from src.normalizacao import ordinal_trimestre as ordinal

con = duckdb.connect(str(a.PAINEL), read_only=True)
fco, ativo, dur = a.carregar_fco(con), a.carregar_ativo(con), a.carregar_duracoes(con)
g = a.gate_g0(fco, ativo, dur)
print('G0', g['aprovado'], len(fco), len(ativo), g['g0_3_saltos_de_escala'])
por_cia = {}
for r in sorted(ativo, key=lambda r: (r['cd_cvm'], ordinal(r['trimestre']))):
    por_cia.setdefault(r['cd_cvm'], []).append(r)
saltos = []
for cd, linhas in por_cia.items():
    for p, r in zip(linhas, linhas[1:]):
        x, y = p['ativo'], r['ativo']
        if x and y and max(abs(x), abs(y)) / min(abs(x), abs(y)) >= 100:
            saltos.append((cd, p['trimestre'], r['trimestre'],
                           ordinal(r['trimestre']) - ordinal(p['trimestre'])))
adj = sum(s[-1] == 1 for s in saltos)
print('ADJACENTES', adj, adj / len(ativo))
print('NAO_ADJACENTES', [s for s in saltos if s[-1] != 1])
print('DURACOES', sorted(Counter(
    (r['origem'], r['dias']) for r in dur if not 80 <= r['dias'] <= 100
).items()))

for nome, cond in [
    ('FCO', "f.demonstrativo LIKE 'DFC%' AND f.cd_conta='6.01' AND f.tipo_periodo='trimestral'"),
    ('ATIVO', "f.demonstrativo='BPA' AND f.cd_conta='1'"),
]:
    q = f"""
    WITH bruto AS (
      SELECT f.cd_cvm, f.trimestre, f.valor_reais, d.dt_receb
      FROM fatos_contabeis f JOIN companhias c USING(cd_cvm)
      JOIN documentos d ON d.cd_cvm=f.cd_cvm AND d.conjunto=f.conjunto
        AND d.dt_refer=f.dt_refer AND d.versao=f.versao_documento
      WHERE c.plano_contas NOT LIKE 'll3_09_%' AND NOT c.is_banco AND {cond}
    ), g AS (
      SELECT cd_cvm,trimestre,max(valor_reais) v,min(dt_receb) d
      FROM bruto GROUP BY 1,2
    )
    SELECT g.cd_cvm,g.trimestre,g.v,g.d,min(b.dt_receb) data_valor
    FROM g JOIN bruto b ON b.cd_cvm=g.cd_cvm AND b.trimestre=g.trimestre
      AND b.valor_reais=g.v
    GROUP BY 1,2,3,4 HAVING g.d<min(b.dt_receb) ORDER BY 1,2
    """
    linhas = con.execute(q).fetchall()
    print('DISPONIBILIDADE_ANTECIPADA', nome, len(linhas), linhas)

q = """
WITH x AS (
 SELECT f.cd_cvm,f.trimestre,f.valor_reais,
        f.dt_fim_exerc-f.dt_ini_exerc+1 dias
 FROM fatos_contabeis f JOIN companhias c USING(cd_cvm)
 WHERE c.plano_contas NOT LIKE 'll3_09_%' AND NOT c.is_banco
   AND f.demonstrativo LIKE 'DFC%' AND f.cd_conta='6.01'
   AND f.tipo_periodo='trimestral'
), g AS (
 SELECT cd_cvm,trimestre,
   max(valor_reais) FILTER(WHERE dias BETWEEN 80 AND 100) bom,
   max(valor_reais) FILTER(WHERE dias NOT BETWEEN 80 AND 100) ruim,
   max(dias) FILTER(WHERE dias NOT BETWEEN 80 AND 100) dias_ruins
 FROM x GROUP BY 1,2
)
SELECT * FROM g WHERE bom IS NOT NULL AND ruim IS NOT NULL ORDER BY 1,2
"""
mistos = con.execute(q).fetchall()
print('MISTOS', len(mistos), mistos)
print('MAX_ELEGE_ANOMALO', sum(r[3] > r[2] for r in mistos))
con.close()

novo = a.executar()
publicado = json.loads(Path('artefatos/rank03b/auditoria.json').read_text())
print('CAMPOS_G0_DIFERENTES', [
    k for k in novo['cadeia'][0]
    if novo['cadeia'][0][k] != publicado['cadeia'][0].get(k)
])
print('VEREDITO', novo['veredito'], novo['primeiro_reprovado'])
PY
```

### 5.2 Contraprovas sintéticas dos consumidores

Este bloco reproduz resultados **defeituosos atuais**, não o resultado esperado
de uma implementação corrigida. Os patches isolam o orquestrador; não trocam
gates do painel real nem produzem uma avaliação científica do alvo.

```bash
.venv/bin/python - <<'PY'
import runpy
import statistics
from contextlib import ExitStack
from unittest.mock import patch, MagicMock
from scripts import auditar_rank03b_consumo_operacional as a

# Reutiliza somente as fábricas sintéticas do arquivo de testes hasheado.
m = runpy.run_path('tests/test_rank03b_consumo_operacional.py')
serie = m['TestPointInTime']._serie
ativo = m['_ativo']
for faltante, data in [('3T2019', '2019-05-10'), ('4T2018', '2019-08-09')]:
    fco = [r for r in serie(n=24, inicio=2016) if r['trimestre'] != faltante]
    ativos = [ativo('A', r['trimestre'], 10000, r['dt_receb'].isoformat()) for r in fco]
    amostra, _ = a.construir_amostra(fco, ativos)
    print('JANELA', faltante, [
        {k: r[k] for k in ('D', 'q1', 'fco_ttm_em_D')}
        for r in amostra if r['D'] == data
    ])

rows = [{'cd_cvm': str(i), 'y': int(i < 10),
         **{c: 1. for c in a.COMPONENTES_T1}} for i in range(100)]
print('EMPATE', a.medir_baselines(rows)['baselines']['B2_trimestres_negativos'])

rows = [{'cd_cvm': 'A' if i < 570 else f'C{i}', 'y': i % 2,
         **{c: 1. for c in a.COMPONENTES_T1}} for i in range(600)]
for r in rows[570:]:
    r['fco_ttm_sobre_sd8'] = None
t1 = a.teste_t1(rows)
print('UMA_COMPANHIA_NO_COMPONENTE', t1['aprovado'],
      t1['componentes']['fco_ttm_sobre_sd8'])

rows = [{'cd_cvm': 'A', 'y': i % 2,
         **{c: float(i + 1) for c in a.COMPONENTES_T1}} for i in range(20)]
for caso in ('amostra_insuficiente', 'zona_cinzenta', 'baseline_falhou'):
    with ExitStack() as stack:
        stack.enter_context(patch.object(a.duckdb, 'connect', return_value=MagicMock()))
        substitutos = {
            'carregar_fco': [], 'carregar_ativo': [], 'carregar_duracoes': [],
            'diagnosticar_escala': {}, 'gate_g0': {'aprovado': True},
            'construir_amostra': (rows, {}), 'teste_t2': {'aprovado': True},
        }
        for nome, valor in substitutos.items():
            stack.enter_context(patch.object(a, nome, return_value=valor))
        if caso == 'zona_cinzenta':
            stack.enter_context(patch.object(a, 'teste_t1', return_value={
                'aprovado': False, 'indecidivel': True,
            }))
        elif caso == 'baseline_falhou':
            stack.enter_context(patch.object(a, 'teste_t1', return_value={'aprovado': True}))
            stack.enter_context(patch.object(a, 'medir_baselines',
                side_effect=statistics.StatisticsError('baseline sem suporte')))
        r = a.executar()
        print('ORQUESTRADOR', caso, r['veredito'],
              r['baselines_triviais'].get('reprova_em_aberto'))
PY
```

Resultados centrais: `q1=4T2019` com o trimestre contratual ausente; precisão
1/lift 10 no empate; T1 aprovado com uma companhia efetiva; `REJEITADO` nas
duas condições inconclusivas e `PRONTO PARA CHALLENGER` com baseline falho.

## 6. Procedência, testes e limites desta revisão

A sessão principal conferiu AGENTS.md/MEMORY.md, pré-registro, relatório, todo
o auditor e testes, G0 real, derivações no código comum e o exemplo de escala
nos membros `itr_cia_aberta_BPA_con_2020.csv` e
`dfp_cia_aberta_BPA_con_2020.csv` dos ZIPs CVM. O agente
**`auditor_rank03b_contratos`**, com contexto separado,
fez revisão somente leitura dos contratos de população, G1, T1/T2, baselines
e decisão; rodou 23 testes sintéticos focados e contraprovas. A sessão
principal replicou os achados centrais, incluindo os três estados do orquestrador.

```bash
CREWAI_STORAGE_DIR="$(mktemp -d /tmp/rank03b-revisao.XXXXXX)" .venv/bin/python -m pytest -q --tb=short
```

**2.010 passed, 30 warnings, 118,66 s, zero skips.** Nenhuma asserção alterada
ou warning suprimido. Isso inclui os testes de outros módulos do projeto;
não é treino experimental do candidato. O arquivo de 25 testes do Rank 3-B
também foi executado separadamente pela sessão principal: **25 passed, 2,29 s**.

Hashes conferidos antes e depois das verificações, inclusive após a retomada:

```text
040495f7415c813e212141493d3ddf2a8fd02632b3d3169c87aa7d5295887926  scripts/auditar_rank03b_consumo_operacional.py
004150630471bdf3e0576fd4ed9feb224b58b9e97710cac4f6c591fe49a87397  tests/test_rank03b_consumo_operacional.py
fbae30cce2bde9b3ece5ccf254e300ce99ba11946568720441193b0a3ac644cc  resultados/pre_registro_rank03b_consumo_operacional_2026-09-11.md
edfee5d66f3ce85119dc83ac9943df60525cc50e87375ea8397dd50690d91f5b  resultados/validacao_rank03b_consumo_operacional_2026-09-11.md
7b59cf0b1d15f448a13ebe1a4ff3a7bf9c47f8d0f03cceb2ce52c9674129da24  artefatos/rank03b/auditoria.json
43e31d9f150e535f1ab20576d9aacf1a53b83ecc5424ca7d48ba50781e4cef18  artefatos/cvm.duckdb
c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b  artefatos/cvm_treino.duckdb
```

O hash atual do pré-registro coincide com `PRE_REGISTRO_CONGELADO.txt`.
Isso comprova identidade do arquivo disponível; a cronologia “antes do auditor
existir” permanece declarada pelo registro anterior, não demonstrada apenas
por um timestamp textual. Não há snapshot anterior do auditor do Rank 3-B
examinado nesta revisão: não afirmo auditoria de diff contra sua primeira
versão, nem classifico todos estes defeitos como regressões.

**Sem escrita** no painel, código, testes, pré-registro ou artefato original.
Sem rede, API paga, leitura do holdout ou treino do candidato. Foram escritos
somente este parecer e a atualização de `MEMORY.md`. Não foi realizada a
conferência da terceira onda bancária R-C5/R-C6/R-SUPORTE, que é outra tarefa.

## 7. Próximo trabalho recomendado, sem executá-lo nesta revisão

1. Corrigir e testar o instrumento: seleção indivisível de fato/vintage/data;
   horizonte e janelas fiscais; desempate dos rankings; suporte por componente;
   decisão com todos os estados de insuficiência/completude. Contraprovas acima
   precisam se tornar testes, sem remover os casos positivos existentes.
2. Publicar inventário completo e determinístico dos problemas de escala e
   período; corrigir a descrição dos 15 grupos. Adjudicar fontes, sem converter
   um detector de suspeitas em tabela automática de correções.
3. Corrigir a derivação e a identificação de períodos na camada comum com
   procedência, preservando os consumidores existentes; isso exige testes
   próprios e não foi feito como efeito lateral da revisão.
4. Registrar novo protocolo antes de qualquer remedição do alvo, conforme a
   condição de retomada do pré-registro consumido. Preservar a previsão antiga
   sobre `fco_ttm_sobre_sd8` como **ainda não testada**; correção de dado não é
   confirmação dessa previsão nem motivo para mudar a definição até ela passar.

Os avisos sobre o painel no AGENTS.md e a narrativa datada de 11/09 precisam
ser lidos com as ressalvas deste parecer. O MEMORY.md passa a apontar para
esta revisão; os documentos históricos não foram reescritos silenciosamente.

**Conclusão final:** há motivo suficiente para manter G0 reprovado, mas não
para declarar o alvo rejeitado. Corrigir só a escala ou só os semestres não
torna a próxima execução válida: o auditor também precisa das correções
delimitadas acima. Isso não demonstra inviabilidade de ML sobre DFC.
