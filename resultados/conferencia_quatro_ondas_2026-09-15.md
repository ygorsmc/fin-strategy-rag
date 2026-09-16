# Conferência independente das quatro ondas — 2026-09-15

Revisão iniciada em 14/09 e concluída em 15/09. Ponto de partida:
[dossiê de 14/09](dossie_revisao_quatro_ondas_2026-09-14.md).

**Parecer: aprovação parcial das correções; aprovação integral recusada.**
O Rank 3-B continua bloqueado em G0. Não houve remedição do alvo, treino de
candidato, reconstrução de painel nem correção de escala nesta revisão.
**O próximo passo não é simplesmente preencher `classe_confirmada`: há
defeitos de implementação e de evidência a corrigir antes de usar essa
classificação para reescalar dados.**

## 1. Escopo e método

Foram conferidos os contratos, código, testes e artefatos das quatro ondas:

| Onda | Resultado da conferência |
|---|---|
| R1–R7 do Rank 3-B | Identidade atômica, calendário, contiguidade e desempates melhoraram; G1, completude, suporte e CLI ainda têm defeitos |
| Derivação intermediária | A banda impede os semestres observados; a contagem de recusas não usa a mesma identidade da inserção |
| Inventário de escala | As contagens reproduzem, mas parte importante da alegada adjudicação não constitui prova |
| Plano de contas | CSV reproduz como esqueleto de propostas, não como mapa semântico validado; exclusões herdam problemas do inventário |

Três revisores em contextos separados cuidaram de Rank 3-B, derivação e
inventário. A sessão principal conferiu o esqueleto e a coerência documental,
e repetiu as contraprovas centrais dos revisores. Houve interrupção por cota
entre as duas datas; os três retomaram e concluíram seus pareceres.

Verificação executada:

- Suíte completa no estado inicial: **2.056 passed, 30 warnings, 223,59 s**.
- Reexecução focada em 15/09: **236 passed, 99,05 s** — 45 Rank 3-B, 169
  dados estruturados, 9 inventário e 13 esqueleto.
- `executar()` do Rank 3-B reproduz o JSON publicado, sem gravá-lo.
- `executar()` do esqueleto reproduz todas as 300 linhas do CSV, sem gravá-lo.
- Painéis abertos somente leitura; contraprovas de alteração usam memória e
  interceptação de escrita. Não se executaram as CLIs que regeneram artefatos.

Durante a pausa houve mudanças de outra frente em interface, geração,
avaliação e MEMORY. Foram preservadas e **não estão certificadas por esta
revisão**. A contagem global mais recente de 2.093 declarada no MEMORY não é
a execução de 2.056 acima. Os hashes das peças destas quatro ondas continuaram
iguais aos do dossiê. Nenhuma chamada paga foi feita por esta revisão.

## 2. Achados novos, por prioridade

### QW1 — P1: zero está sendo usado como prova de escala errada

Fonte: [inventariar_escala_cvm.py](../scripts/inventariar_escala_cvm.py),
linhas 180–196; consumo em
[esqueleto_plano_padrao.py](../scripts/esqueleto_plano_padrao.py), 89–102.

O inventário considera qualquer valor bruto coincidente sob duas escalas
como prova e escolhe a escala da DFP. Isso inclui **zero**. Porém
`0 × 1.000 = 0 × 1`: a observação não identifica a escala correta.

Recontagem do artefato, **sobre os valores que ele armazena após arredondamento**:

| Medida | Quantidade |
|---|---:|
| Casos rotulados `ADJUDICAVEL_PELA_DFP` | 10.261 |
| Com `valores_em_conflito == [0]` | **6.736** |
| Com alguma coincidência não nula | 3.525 |
| Documentos cuja única prova é a coincidência zero | **14 de 127** |
| Linhas arquivadas desses 14 documentos | **3.502 de 33.655** |

Todas as **67 adjudicações fora de BPA/BPP** estão no grupo de prova zero:
DRE 14, DMPL 26, DVA 24 e DRA 3. Portanto, a conclusão de que incluir
`DT_INI_EXERC` destravou adjudicação substantiva de fluxos não foi demonstrada
pelas adjudicações publicadas. A inclusão do início na identidade continua
correta e necessária; o que não sobrevive é essa interpretação do resultado.

Os 14 documentos abaixo são ITR, versão 1:

| CD_CVM | DT_REFER | Linhas arquivadas |
|---|---|---:|
| 018414 | 2024-06-30 | 364 |
| 018414 | 2024-09-30 | 362 |
| 023299 | 2013-03-31 | 197 |
| 023299 | 2013-06-30 | 226 |
| 024279 | 2019-03-31 | 194 |
| 024279 | 2019-06-30 | 252 |
| 024309 | 2019-03-31 | 249 |
| 024309 | 2019-06-30 | 234 |
| 024309 | 2019-09-30 | 267 |
| 026565 | 2021-09-30 | 285 |
| 027006 | 2022-06-30 | 253 |
| 027006 | 2022-12-31 | 63 |
| 027316 | 2024-06-30 | 277 |
| 027316 | 2024-09-30 | 279 |

Isso **não prova que esses documentos estejam corretos**; prova que o
argumento usado para classificá-los como defeituosos não basta. Tampouco
certifica automaticamente os outros 113 documentos ou 3.525 casos.
O esqueleto já usa os 127 como exclusões, de modo que o problema alcança a
seleção da amostra, ainda que nenhuma correção de valor tenha sido aplicada.

### QW2 — P2: a prova não é vinculada à declaração que se condena

Fontes: inventário, linhas 183–199; esqueleto, linhas 98–101;
[relatório do inventário](inventario_escala_cvm_2026-09-12.md), §9.

Uma coincidência entre duas declarações produz uma única `escala_correta`
para o grupo inteiro. O consumidor considera divergente qualquer outra
declaração cuja escala difira dessa direção, mesmo com outro valor bruto.

- **292 declarações em 235 casos** são tratadas como divergentes embora seu
  valor nem pertença a `valores_em_conflito`.
- Em **124 dos 3.525 casos com coincidência não nula**, nenhuma DFP declara
  o valor coincidente: a coincidência ocorre apenas entre ITRs.

Exemplo real: `003549/BPA/1`, fim 2023-12-31. DFP e dois comparativos têm
`18652`, mas o comparativo de março de 2024 tem `18663`. Este último pode estar
errado; **a igualdade numérica usada como prova não o adjudica**.

Contraprova: DFP `100 MIL`, ITR A `100000 UNIDADE`, ITR B `100 UNIDADE`.
O programa escolhe `MIL` para o grupo e o consumidor condenaria também A,
que representa corretamente os mesmos 100.000 reais da DFP. Este cenário
exato é sintético; não foi encontrado como tal no artefato real.

Logo, os **19.859 comparativos com escala divergente** não devem ser chamados
indiscriminadamente de 19.859 erros provados. O contrato futuro precisa
distinguir evidência direta por declaração de propagação/inferência, com
vintage, unidade e identidade preservados.

### QW3 — P1: R2.5 não foi implementado; G1 continua aprovando por existência

Fontes: [contrato R2.5](contratos_correcao_r1_r5_rank03b_2026-09-12.md);
[auditor](../scripts/auditar_rank03b_consumo_operacional.py), 549 e 1062–1075.

G1 ainda usa `aprovado = bool(amostra)`. Não executa as verificações e
contagens de horizonte, disponibilidade, contiguidade e unicidade prometidas.

A contraprova usa o construtor real: série regular, mas uma linha rotulada
`3T2019` declara período **01/01–31/03/2019**, de 90 dias. Para
`D=10/05/2019`, ela é aceita como primeiro trimestre futuro. **G0 e G1
aprovam no sintético**, embora o período tenha começado e terminado antes de D.

R2 corrigiu a escolha do trimestre textual e suas lacunas, mas não certificou
que as datas da linha correspondem a esse trimestre. Não é uma alegação de
vazamento medido no alvo real: o painel real para antes, em G0. É uma
contraprova de identidade temporal que viola o contrato do instrumento.

### QW4 — P2: completude dos baselines ainda pode ser um falso certificado

Fontes: auditor, 886–910, 960–992 e 1105–1122;
[pré-registro](pre_registro_rank03b_consumo_operacional_2026-09-11.md), §8;
contratos R4.2/R4.3.

Depois dos pisos de observações e companhias, o produtor marca
`completo=True` sem exigir métricas válidas. Um suporte de 600 observações e
60 companhias, todas negativas, pode produzir AUC e IC `None`, nenhuma
companhia com os dois rótulos e zero reamostragens válidas, mas ser certificado
como completo. A contraprova integrada chegou a `PRONTO PARA CHALLENGER`.

**Limite importante:** para chegar a esse caminho, a contraprova torna B3
ausente nos positivos. Isso exercita o consumidor e seu contrato de suporte;
não é saída natural do construtor atual nem ocorrência medida no painel.

Independentemente desse caso, o IC calculado é apenas o da AUC agregada.
Faltam os intervalos da precisão top-10% e da AUC intra apresentados como
parte do pacote de métricas do §8. Se outra interpretação desse contrato for
desejada, deve ser explicitada, não coberta por nomes genéricos de campos.
A distinção declarada de B0 entre previsão de classe e abstenção de ranking
foi corretamente implementada; não se exige inventar AUC de B0.

### QW5 — P2: R5 não trata o piso de observações como trata o de companhias

Fonte: auditor, 692–714; contratos R5.1–R5.3.

Um componente com menos de 30 companhias ganha registro `INSUFICIENTE` e o
laço continua. Com **499 observações e 60 companhias**, a exceção dentro de
`amplitude_por_quintis` interrompe T1 inteiro. Perdem-se o suporte desse
componente e as medições dos demais.

No sintético, outro componente pleno tem amplitude **1,0**, mas não chega a
ser registrado. Não é falsa aprovação: é possível converter uma rejeição
numérica identificável em insuficiência global, contrariando o tratamento
por componente e a distinção de estados que R4/R5 prometem.

### QW6 — P2: uma recusa de derivação pode não ser contada nem avisada

Fontes: [dados_estruturados.py](../src/dados_estruturados.py), 1286 versus
1327–1330; aviso em 1141; contrato D1.2.

A consulta de recusas usa `coalesce(m.conceito, f.cd_conta)`, mas a inserção
usa, na ausência de conceito, **código + descrição normalizada**.

Com a mesma conta A em 1T e 3T, faltando 2T, a função retorna `(0, 1)`.
Inserir em 2T outra descrição B sob o mesmo código faz retornar **`(0, 0)`**:
a derivação longa de A continua recusada, mas não é contada. O chamador,
que depende dessa contagem, não emite o aviso.

O revisor também comparou SELECTs sobre arquivados: contador atual **4.486**,
contador com chave alinhada **7.735**. O segundo ainda não replica o
`QUALIFY` da inserção; **não o adotar como total corrigido de derivados**.

Nenhum dos quatro testes novos inspeciona `relatorio.avisos` no carregador.
O teste chamado “1S sem 1T” usa de fato 1T e 9M, faltando 1S. O caso literal
de apenas 1S retorna `(0, 0)`; é preciso esclarecer e testar se ausência
completa do antecedente também pertence à contagem contratada.

**A banda em si funciona nos casos conferidos:** admite 80/100, recusa
79/101 dias e aceita o exemplo de 13 semanas. O SELECT da inserção elimina
os grupos longos observados sem precisar reconstruir o painel. Não foi
demonstrada validade universal para qualquer calendário fiscal.

### QW7 — P2: a CLI quebra depois de tentar escrever o resultado

Fonte: auditor, 1175–1177; dossiê §3.1.

R7 mudou o formato do diagnóstico, mas `principal()` continua lendo
`defeito_valor_bruto_continuo`, `trocas_de_escala` e
`companhias_com_defeito` no formato antigo. A reprodução com escrita
interceptada levanta **`KeyError('defeito_valor_bruto_continuo')`**, depois
de uma tentativa de gravação. Portanto, a CLI atual não termina normalmente
com o código 2 anunciado no dossiê.

Isso não invalida automaticamente o JSON: a função `executar()` reproduz o
artefato. Invalida a afirmação sobre execução completa do comando publicado.

### QW8 — P2: inventário ausente remove silenciosamente todas as exclusões

Fonte: esqueleto, 89–92 e 105–115.

Se `INVENTARIO` não existe, `documentos_defeituosos()` retorna `set()`;
`levantar()` transforma isso em filtro `TRUE`. O esqueleto pode ser calculado
com todos os arquivados, sem avisar que deixou de excluir os documentos que
promete excluir. A contraprova de caminho inexistente retorna o conjunto
vazio, sem erro.

Não ocorreu na geração deste CSV: o inventário existe. É uma falha fechada
faltante na dependência do gerador. Um inventário válido sem casos e um
inventário ausente precisam de estados distintos.

## 3. O que foi confirmado e como ler os números

### 3.1 Rank 3-B: o negativo é de G0, não do alvo

Reprodução do artefato atual: **132 / 22.471 = 0,5874%**, acima de 0,5%;
25 durações anômalas, 22.034 linhas de FCO carregadas. A cadeia publicada
contém somente G0. O literal do JSON é `REPROVADO EM G0/G1`, com
`primeiro_reprovado='G0'`. Nenhum T1/T2/baseline real foi medido.

R1 removeu as agregações independentes. Os casos testados de q(D), censura,
contiguidade e deduplicação passaram. R3 devolve precisão 0,1 e lift 1,0 no
empate constante, preservando sinal real. A falha explícita de baseline
passou a vetar prontidão. Não se encontrou enfraquecimento das asserções
anteriores: a tautologia e a mudança de nome foram declaradas.

Os quatro saltos retirados por R6 eram não adjacentes: a emenda corresponde
à definição de adjacência, não a exclusão arbitrária de empresas. Mas a defesa
do dossiê — “não cruzou o limiar, logo não favoreceu o resultado” — não prova
ausência de viés. **Uma correção legítima pode mudar o veredito.** O critério
de aceitação deve ser a regra e a contraprova, não a obrigação de preservar
uma rejeição. Nenhum limiar foi alterado nesta revisão.

### 3.2 A retratação “zero alterações diretas” sobrevive com escopo restrito

Reproduz: nenhum dos 10.261 casos contém declaração `ÚLTIMO` com escala
divergente da direção publicada. A carga filtra `ORDEM_EXERC` antes da seleção
de versões ([dados_estruturados.py](../src/dados_estruturados.py), 876).

Portanto, **aplicar diretamente os rótulos atuais às declarações
inventariadas não altera linhas arquivadas do painel**. Isso não valida a
adjudicação, não prova o erro de todas as linhas dos 127 documentos e não
exclui outras correções possíveis por evidência diferente.

O inventário continua útil como catálogo de divergências de metadado. A
varredura integral de 26,3 milhões de linhas não foi repetida nesta revisão;
foram recontados os casos persistidos, examinados o algoritmo e a carga, e
testadas suas decisões. Não se certificaram moeda, semântica, colunas de
DMPL ou condição auditada individual de cada documento.

### 3.3 Derivação: 513 companhias, e não 507 no total

A consulta ao painel retorna **7.734 linhas, 513 companhias e 111 contas**
fora de 80–100 dias. Os 507 emissores pertencem apenas às 7.555 linhas de
183 dias. Os 701.357 dentro da banda são todos os derivados em disco,
inclusive 4T: não equivalem a uma reconstrução comparativa que tenha provado
preservação individual de 701.357 resultados pela nova função.

O painel continua com as linhas antigas. A correção de código e a correção
de dado são estados diferentes; os períodos curtos permanecem pendentes.

### 3.4 Plano de contas: cobertura de códigos não é cobertura semântica

As 300 linhas e propostas reproduzem: **291 monetárias, 7 não monetárias,
2 indefinidas; todas as confirmações vazias**. Não há consumidor dessa tabela
em `src/`; “campo que decide” descreve intenção futura, não autorização
implementada de reescala. A proteção contra sobrescrita existente passou.

O denominador efetivamente usado é `origem='arquivado'`, excluindo os 127
documentos. A cobertura publicada **92,890% = 5.977.442 / 6.434.959** pertence
a esse universo. Outros denominadores dão:

| Universo | Linhas com as 300 chaves / total | Cobertura |
|---|---:|---:|
| Arquivados após exclusão usada pelo gerador | 5.977.442 / 6.434.959 | 92,890% |
| Todos os arquivados | 6.008.928 / 6.468.614 | 92,894% |
| Painel inteiro, incluindo derivados | 6.680.366 / 7.177.705 | 93,071% |

As 208 primeiras chaves cobrem 77,609% do universo do gerador. O dossiê já
reconhece que “208 → 85%” não reproduz. Não converter isso em cobertura de
conceitos: agrupar por `(demonstrativo, cd_conta)` e selecionar `min(ds_conta)`
não resolve a semântica por plano contábil. Exemplo DRE/3.04: o CSV mostra
“Despesas Administrativas” (218 ocorrências), mas “Despesas/Receitas
Operacionais” aparece 33.598 vezes. A coluna se chama exemplo, corretamente;
não pode virar conceito canônico em um join universal.

A razão sobre ativos mede magnitude, não natureza contábil. Isso já estava
declarado e **não é achado novo**. O esqueleto pode auxiliar curadoria; não há
base para carimbar 291 propostas por amostrar algumas. Cada decisão aplicada
precisa de escopo, unidade e evidência, ou os casos não confirmados permanecem
sem correção. “Monetária” deve ser definido operacionalmente como montante
sujeito à escala do arquivamento, sem confundir com taxonomias contábeis mais
amplas. Os achados QW1/QW2 precisam ser resolvidos independentemente disso.

### 3.5 A diferença histórica de tamanho do painel não é só denominador

O dossiê §9.3 afirma que o hash não mudou desde a carga de 6.787.589 linhas
e sugere diferença de denominador. Há registro explícito contrário em
[validação do Rank 3, 27/08](validacao_rank03_conversao_caixa_2026-08-27.md),
seções “Achado de dado” e “Hash do painel”, linhas 104–133:

- Painel com DFC, antes dos intermediários:
  `476a11da2382c6f2a4575de1e37cf997b93edff2b449b67d9f7b75c6adf53247`.
- Após a derivação intermediária:
  `c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b`.
- Contagem registrada: **6.787.589 → 7.177.705**.

Isso explica qual mudança separa as contagens; não houve mutação de painel
nesta revisão. Persiste uma diferença histórica de **71 linhas** entre o
acréscimo líquido de 390.116 e os 390.187 derivados relatados. Sem o painel
anterior, esta revisão não atribui causa a esses 71. A chave desatualizada em
`resumo.json` e as coberturas conflitantes do mapa já estavam declaradas no
dossiê; continuam pendentes, não foram “descobertas novamente”.

## 4. Reproduções executáveis, sem alterar os artefatos

Executar na raiz com `.venv/bin/python`. As duas primeiras contraprovas
alteram exclusivamente dicionários/conexões em memória.

### A. G1 aceita trimestre textual incompatível com as datas

```bash
.venv/bin/python - <<'PY'
import datetime as dt, runpy
from contextlib import ExitStack
from unittest.mock import patch, MagicMock
from scripts import auditar_rank03b_consumo_operacional as a
m = runpy.run_path('tests/test_rank03b_consumo_operacional.py')
fco = m['TestPointInTime']._serie(n=24, inicio=2016)
for r in fco:
    if r['trimestre'] == '3T2019':
        r.update(dt_ini=dt.date(2019, 1, 1), dt_fim=dt.date(2019, 3, 31))
ativo = [m['_ativo']('A', r['trimestre'], 10000,
                    r['dt_receb'].isoformat()) for r in fco]
dur = [m['_duracao']('A', r['trimestre'],
                    (r['dt_fim']-r['dt_ini']).days+1) for r in fco]
with ExitStack() as s:
    s.enter_context(patch.object(a.duckdb, 'connect', return_value=MagicMock()))
    for nome, valor in {'carregar_fco': fco, 'carregar_ativo': ativo,
                        'carregar_duracoes': dur,
                        'diagnosticar_escala': {}}.items():
        s.enter_context(patch.object(a, nome, return_value=valor))
    r = a.executar()
print([(x.get('gate') or x.get('teste'), x['aprovado']) for x in r['cadeia']])
amostra, _ = a.construir_amostra(fco, ativo)
print([r for r in amostra if r['D'] == '2019-05-10'])
# G0=True, G1=True; observação aceita com q1=3T2019.
PY
```

### B. Recusa silenciosa da derivação

```bash
.venv/bin/python - <<'PY'
from tests.test_dados_estruturados import TestDerivacaoSoCobreUmTrimestre as T
from src.dados_estruturados import _derivar_trimestres_intermediarios as derivar
for extra in (False, True):
    linhas = [('1T2025','trimestral','2025-03-31',1000.),
              ('3T2025','acumulado','2025-09-30',9000.)]
    if extra:
        linhas.insert(1, ('2T2025','acumulado','2025-06-30',3000.))
    con = T._painel(linhas)
    if extra:
        con.execute("""UPDATE fatos_contabeis SET ds_conta='Outra conta',
            ds_conta_norm='outra conta' WHERE trimestre='2T2025'""")
    print(extra, derivar(con))
    con.close()
# False (0, 1); True (0, 0).
PY
```

### C. Inventário: zeros, extrapolação e alcance documental

```bash
.venv/bin/python - <<'PY'
import collections, json, duckdb
casos = [json.loads(l) for l in open('artefatos/escala_cvm/inventario.jsonl')]
adj = [c for c in casos if c['veredito'] == 'ADJUDICAVEL_PELA_DFP']
print('adjudicados/zeros:', len(adj),
      sum(c['valores_em_conflito'] == [0] for c in adj))
print('ULTIMO divergente:', sum(any(d['ordem_exerc'] == 'ÚLTIMO'
    and d['escala'] != c['escala_correta'] for d in c['declaracoes']) for c in adj))
sem_dfp = [c for c in adj if any(v != 0 for v in c['valores_em_conflito'])
    and not any(d['conjunto'] == 'dfp' and d['vl_conta'] in c['valores_em_conflito']
                for d in c['declaracoes'])]
extra = [(c, d) for c in adj for d in c['declaracoes']
         if d['escala'] != c['escala_correta']
         and d['vl_conta'] not in c['valores_em_conflito']]
print('sem DFP do valor/declarações extrapoladas:', len(sem_dfp), len(extra))
docs = collections.defaultdict(list)
for c in adj:
    for d in c['declaracoes']:
        if d['escala'] != c['escala_correta']:
            docs[(c['cd_cvm'], d['conjunto'], d['dt_refer'], d['versao'])].append(c)
con = duckdb.connect('artefatos/cvm_treino.duckdb', read_only=True)
total = n_zero = total_zero = 0
for chave, evidencias in docs.items():
    n = con.execute("""SELECT count(*) FROM fatos_contabeis
        WHERE cd_cvm=? AND conjunto=? AND dt_refer=? AND versao_documento=?
          AND origem='arquivado'""", chave).fetchone()[0]
    total += n
    if all(c['valores_em_conflito'] == [0] for c in evidencias):
        n_zero += 1
        total_zero += n
        print('documento só zero:', chave, n)
print('docs/linhas/docs só zero/linhas só zero:', len(docs),total,n_zero,total_zero)
con.close()
# 10261/6736; 0; 124/292; 127/33655/14/3502.
PY
```

Contraprovas sem dados reais:

```bash
.venv/bin/python - <<'PY'
import runpy
from scripts import inventariar_escala_cvm as a
d = runpy.run_path('tests/test_inventario_escala_cvm.py')['_dec']
def dec(tipo, escala, valor, ref):
    return d('A', tipo, ref, 'ÚLTIMO' if tipo=='dfp' else 'PENÚLTIMO',
             escala, valor, '2020-12-31')
for linhas in (
    [dec('dfp','MIL',0,'2020-12-31'), dec('itr','UNIDADE',0,'2021-03-31')],
    [dec('dfp','MIL',100,'2020-12-31'),
     dec('itr','UNIDADE',100000,'2021-03-31'),
     dec('itr','UNIDADE',100,'2021-06-30')],
):
    r = a.adjudicar(linhas)[0]
    print(r['veredito'],r['escala_correta'],r['valores_em_conflito'])
    print([d['vl_conta'] for d in r['declaracoes']
           if d['escala'] != r['escala_correta']])
# Ambos adjudicados MIL; o segundo marca também 100000 como divergente.
PY
```

### D. Completude e suporte: dois caminhos sintéticos

```bash
.venv/bin/python - <<'PY'
from contextlib import ExitStack
from unittest.mock import patch, MagicMock
from scripts import auditar_rank03b_consumo_operacional as a
rows = [{'cd_cvm':f'C{i//20}', 'y':i%2,
         **{c:float(i%3+1) for c in a.COMPONENTES_T1}} for i in range(1200)]
for r in rows:
    r['fco_ttm_sobre_ativo'] = 1.0 if r['y']==0 else None
with ExitStack() as s:
    s.enter_context(patch.object(a.duckdb,'connect',return_value=MagicMock()))
    s.enter_context(patch.object(a,'REAMOSTRAGENS',10))  # só custo do sintético
    for nome, valor in {'carregar_fco':[], 'carregar_ativo':[],
        'carregar_duracoes':[], 'diagnosticar_escala':{},
        'gate_g0':{'aprovado':True}, 'construir_amostra':(rows,{})}.items():
        s.enter_context(patch.object(a,nome,return_value=valor))
    r = a.executar()
print(r['veredito'])
print(r['baselines_triviais']['baselines']['B3_fco_sobre_ativo'])
rows = [{'cd_cvm':f'C{i%60}', 'y':i%2,
         **{c:float(i%2+1) for c in a.COMPONENTES_T1}} for i in range(600)]
for r in rows[499:]:
    r['fco_ttm_sobre_sd8'] = None
print(a.amplitude_por_quintis([r['fco_ttm_em_D'] for r in rows],
                             [r['y'] for r in rows])['amplitude'])
try:
    a.teste_t1(rows)
except a.AmostraInsuficiente as e:
    print(type(e).__name__, str(e))
# PRONTO com métricas None; depois amplitude 1.0 e exceção por 499 observações.
PY
```

### E. CLI sem gravar e inventário ausente

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from unittest.mock import patch
from scripts import auditar_rank03b_consumo_operacional as a
from scripts import esqueleto_plano_padrao as e
r = json.loads((a.DESTINO/'auditoria.json').read_text())
with patch.object(a,'executar',return_value=r), patch.object(Path,'mkdir'), \
     patch.object(Path,'write_text') as escrita:
    try:
        print(a.principal())
    except KeyError as erro:
        print(repr(erro), 'escritas interceptadas:', escrita.call_count)
with patch.object(Path,'is_file',return_value=False):
    print('inventário ausente:', e.documentos_defeituosos())
# KeyError, 1 escrita interceptada; set().
PY
```

## 5. Encaminhamento: o que fechar antes da próxima etapa

1. **Inventário:** separar conflito de metadado, evidência informativa não
   nula e adjudicação por declaração. Testar zero, redenominação equivalente,
   reapresentação e DFP com outro valor. Recontar os consumidores; não
   simplesmente excluir 6.736 casos e certificar o restante.
2. **Auditor:** implementar G1 verificável com linhagem/datas reais; completar
   R4/R5 e o consumidor CLI. Testar decisões negativas e um caminho positivo
   legítimo. Preservar o alvo, limiares e artefatos históricos.
3. **Derivação:** usar a mesma relação de candidatos para inserir/recusar,
   tratar a deduplicação e testar o aviso no carregador, não só o retorno da
   função. Decidir explicitamente o caso de antecedente inexistente.
4. **Esqueleto:** falhar quando a dependência faltar e corrigir a descrição
   dos denominadores. Curadoria pode prosseguir como trabalho documental,
   mas confirmação de classe **não conserta uma adjudicação de escala inválida**.
5. Depois dessas correções e sua conferência, decidir contrato de correção
   de células e reconstrução, com procedência, proteção contra reapresentação
   e efeito na etapa 10. A reconstrução não está autorizada por este parecer.

Períodos curtos, vintages numéricos e a terceira onda bancária
R-C5/R-C6/R-SUPORTE continuam tarefas separadas. Novo protocolo do Rank 3-B
só antes de nova medição do alvo; o pré-registro anterior permanece consumido.
**Não surgiu evidência a favor nem contra o alvo supervisionado nesta revisão.**

## 6. Procedência e não mutação

Os arquivos de código, testes, CSV e artefatos das quatro ondas conferiram com
o manifesto do dossiê §8. O revisor do Rank conferiu os quatro hashes do
snapshot `artefatos/rank03b/snapshots/2026-09-12-pre-r1-r5/` contra a revisão
anterior. Também se confirmou a preservação do corpo da validação de 11/09:
retirar apenas a ressalva das linhas 3–18 recompõe exatamente o hash anterior
`edfee5d66f3ce85119dc83ac9943df60525cc50e87375ea8397dd50690d91f5b`.
Reprodução sem editar: `awk 'NR < 3 || NR > 18'
resultados/validacao_rank03b_consumo_operacional_2026-09-11.md | sha256sum`.
Identificadores centrais:

```text
afffe087b2e2d66843d2ee2e28839b83f48ce6f2cc4376303c50ac53d85951ef  scripts/auditar_rank03b_consumo_operacional.py
fcdf7be547b4c498b46dca12b006d422d53d0abe0547ce046848234bad89da68  tests/test_rank03b_consumo_operacional.py
2659dee71141bde2f65a35a6d2d569fbd286d1a70151004f2a03b7fc1b988f6e  src/dados_estruturados.py
079ef99c7fc1cb086b5d43ffb7a0b82f16d63a7f23cce1edf4375b5f12f62eb2  tests/test_dados_estruturados.py
5b719f1e799cb054b52299a5995eae18ca4e35ec6720cd6582308fc45339a404  scripts/inventariar_escala_cvm.py
117e924f403a436a549d633b11a9cfaafc8482a8da11b339e907d2d5780613a1  tests/test_inventario_escala_cvm.py
4e9a0dc5ce4ec068631aacb3afc45221776d220034c6af5a4003c1dced33dda4  scripts/esqueleto_plano_padrao.py
13bfbf3fa9886413daebd95ffec508a56e3806764a4b14362b71edf2fe7ed58e  tests/test_esqueleto_plano_padrao.py
b58dbe0115d18347c13c37cd7192d1a2d8c0c78a008a9041772e526c650dd9e9  corpus/cvm/plano_padrao_contas.csv
a2ef88bea647777797d909624662bfe2761ab6ceaaaf4f5eae7f4b2e3d327ee0  artefatos/rank03b/auditoria.json
d420138c9659215834d63811b41064341097f5c4e957a12649e11c8b8b564ed0  artefatos/escala_cvm/resumo.json
43e31d9f150e535f1ab20576d9aacf1a53b83ecc5424ca7d48ba50781e4cef18  artefatos/cvm.duckdb
c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b  artefatos/cvm_treino.duckdb
```

Escritas desta revisão: somente este parecer e atualização localizada do
handoff em `MEMORY.md`. Os relatórios antigos permanecem como evidência
histórica; suas alegações de fechamento integral e de prova documental devem
ser lidas com as qualificações desta conferência.
