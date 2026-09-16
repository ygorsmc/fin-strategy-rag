# Conferência independente das correções QW1–QW8

**Data:** 2026-09-15. **Natureza:** revisão de implementação e evidência,
não execução de nova rodada do candidato, nem autorização de treino.

**Veredito: aprovação parcial do pacote.** As contraprovas dos oito defeitos
originais foram superadas. Persistem duas lacunas contratuais: o consumidor do
inventário não recusa estados de adjudicação inválidos, e a linhagem do ativo
omite as datas de referência exigidas. Há também uma errata no total de
declarações. Nenhuma delas demonstra corrupção do inventário atual ou
vazamento temporal na amostra atual; não confundir falha de guarda/contrato
com defeito já ocorrido nos dados.

**Rank 3-B continua barrado em G0.** O retorno literal do auditor é
`REPROVADO EM G0/G1`, com cadeia contendo somente G0. O alvo não foi testado.
Nenhum código de implementação, painel, CSV ou artefato de resultado foi
alterado nesta revisão. Foram escritos este parecer e o handoff no MEMORY.

## 1. Fontes, independência e limites

Fontes normativas e evidência confrontadas:

- [Contrato QW1–QW8](contratos_correcao_qw1_qw8_2026-09-15.md), em especial
  E1, K1, H1, B1, S1 e D2.
- [Relatório de implementação](implementacao_qw1_qw8_2026-09-15.md).
- [Conferência anterior](conferencia_quatro_ondas_2026-09-15.md), que contém
  os defeitos e contraprovas originais.
- Snapshot `artefatos/snapshots/2026-09-15-pre-qw1-qw8/`: os 19 registros
  de `SHA256SUMS.txt` passaram na conferência. Código, testes, inventário e
  CSV anteriores foram comparados com os atuais.
- Os quatro módulos alterados e seus quatro arquivos de testes, indicados
  nas seções seguintes; inventário JSONL, resumo, CSV e painel em leitura.

Foram iniciados três revisores separados: escala/esqueleto, temporal/CLI e
derivação. Entregaram verificações parciais, mas os três encerraram por limite
de uso antes de emitir parecer final. **Não há aprovação final de três
especialistas.** Os achados e os números materiais usados neste parecer
foram conferidos também pelo revisor principal.

Não houve pesquisa web: o objeto é a conformidade do código com os contratos
locais, não uma nova tese financeira. Não foram acessados holdout, APIs pagas
ou serviços de treinamento. Não foram calculados T1, T2 ou baselines sobre
dados reais. Baselines/contraprovas estatísticas usaram somente dados
sintéticos. A construção da amostra e G1 reais foram diagnósticos isolados,
não continuação da cadeia reprovada em G0.

## 2. Achados remanescentes

### CQW-01 — prioridade média: estado inválido volta a significar ausência de defeito

**Fonte:** `scripts/esqueleto_plano_padrao.py:150–165`, função
`documentos_defeituosos`; contrato E1.2, combinado com K1.2/K1.3.

O consumidor verifica a versão do resumo e a **existência** da chave
`adjudicacao`, mas não seu domínio. `None`, texto desconhecido ou o estado
adjudicado com um espaço adicional são tratados como estados legítimos que
não adjudicam: o retorno é `set()`. Se forem os únicos registros do documento,
ele deixa de ser excluído e volta ao universo do gerador.

Contraprova executada, inteiramente em memória, usando o consumidor real:

```python
import io, json
from pathlib import Path
from unittest.mock import patch
from scripts.esqueleto_plano_padrao import documentos_defeituosos
from scripts.inventariar_escala_cvm import ADJUDICA

for estado in [ADJUDICA, None, "estado_desconhecido", ADJUDICA + " "]:
    caso = {"cd_cvm": "000001", "declaracoes": [{
        "adjudicacao": estado, "conjunto": "ITR",
        "dt_refer": "2020-06-30", "versao": 1,
    }]}
    with (
        patch.object(Path, "is_file", return_value=True),
        patch.object(Path, "read_text", return_value='{"versao_do_esquema":2}'),
        patch.object(Path, "open", return_value=io.StringIO(json.dumps(caso)+"\n")),
    ):
        print(repr(estado), documentos_defeituosos(
            Path("/tmp/inventario-simulado"), Path("/tmp/resumo-simulado")))
```

Saída: o estado exato retorna `{('000001', 'ITR', '2020-06-30', 1)}`;
os outros três retornam conjunto vazio, sem exceção.

**Delimitação:** as duas condições explicitamente exemplificadas em K1.2
(versão antiga e campo ausente) foram implementadas e passam nos testes. A
lacuna é a aplicação do **vocabulário fechado** E1.2 na fronteira do consumidor,
não uma repetição da ausência de arquivo de QW8. O inventário atual contém
somente estados válidos; seus 111 documentos e sua cobertura não são
invalidados por esta contraprova.

**Aceitação para fechar:** consumidor deve lançar `InventarioIncompativel`
para qualquer estado fora dos nove permitidos, incluindo nulo e tipo errado.
Exercitar a decisão de exclusão, mantendo conjunto vazio para estados válidos
sem adjudicação. Não normalizar um estado desconhecido silenciosamente nem
tratar toda declaração não adjudicada como erro.

### CQW-02 — prioridade baixa: H1.4 não está integralmente implementado para o ativo

**Fontes:** contrato H1.4, linha 232;
`scripts/auditar_rank03b_consumo_operacional.py:197–228` e `:692–699`.

H1.4 exige `trimestre`, `dt_ini`, `dt_fim` e `dt_receb` da janela, do rótulo
**e do ativo**. A linhagem do ativo contém somente `trimestre` e `dt_receb`.
Além disso, `carregar_ativo` não seleciona `dt_fim_exerc`.

Reprodução em leitura, sem testes de sinal:

```python
from collections import Counter
import duckdb
from scripts import auditar_rank03b_consumo_operacional as a

with duckdb.connect(str(a.PAINEL), read_only=True) as con:
    amostra, descartes = a.construir_amostra(
        a.carregar_fco(con), a.carregar_ativo(con))
print(Counter(tuple(sorted(o["linhagem"]["ativo"])) for o in amostra))
print(a.gate_g1(amostra, descartes)["aprovado"])
```

Resultado: `{('dt_receb', 'trimestre'): 10605}` e `True`.

**Delimitação:** G1.1 realmente verifica a disponibilidade do ativo por
`dt_receb <= D`; não foi encontrado vazamento temporal por este achado. H1.6
não exige verificar a duração de um saldo de balanço. A pendência é de
linhagem contratada e auditabilidade, não evidência de que o ativo é futuro.

**Aceitação para fechar:** carregar e preservar as datas da linha-fonte do
ativo, com teste do caminho carregador → construção → linhagem. BPA é saldo:
`dt_ini_exerc` ausente na origem deve permanecer ausente/nulo, não ser
inventado nem submetido à banda de duração de fluxo. Alternativamente,
revisar H1.4 de modo explícito e motivado; não declarar cumprimento literal
do contrato atual mantendo apenas dois campos.

### CQW-03 — prioridade baixa: total de declarações incorreto no relatório

**Fonte:** `implementacao_qw1_qw8_2026-09-15.md:59` diz **154.160**.
O JSONL e a soma de `resumo.json.declaracoes_por_estado` dão **156.100**.
Diferença: **1.940**. As contagens individuais publicadas estão corretas.

Reprodução:

```python
import json
from pathlib import Path
raiz = Path("artefatos/escala_cvm")
casos = [json.loads(l) for l in (raiz/"inventario.jsonl").read_text().splitlines()]
resumo = json.loads((raiz/"resumo.json").read_text())
print(sum(len(c["declaracoes"]) for c in casos))
print(sum(resumo["declaracoes_por_estado"].values()))
# 156100 nas duas contas
```

**Aceitação:** publicar errata rastreável do total; não regenerar dados para
acomodar a frase. Não afeta 3.401 casos/6.456 declarações adjudicadas.

## 3. O que efetivamente foi fechado

| Item | Evidência conferida | Veredito desta revisão |
|---|---|---|
| QW1 | Zero excluído como prova e como referência; adjudicação não nula | Fechado no escopo contratado |
| QW2 | Decisão por declaração; equivalência em reais separada; readjudicação integral idêntica ao v2 | Fechado no escopo contratado |
| QW3/N1 | G1 verifica linhagem, interrompe cadeia, usa datas fiscais; 10.605 observações com contadores zero | Núcleo fechado; H1.4 pendente em CQW-02 |
| QW4 | Baseline sem dois rótulos não fica completo; três IC exigidos; ramo pronto continua alcançável com suporte válido | Fechado |
| QW5 | Componente de 499 linhas insuficiente não apaga amplitude 1,0 de outro; falha de bootstrap é localizada | Fechado |
| QW6 | Contagem/inserção pela mesma relação; retorno com três estados; avisos exercitados no carregador | Fechado; não cura N2/N3 |
| QW7 | Resumo composto antes de gravar; saída 2 no G0; esquema antigo falha antes de publicar | Fechado |
| QW8 | Ausência/versão antiga/campo ausente falham; vazio válido é distinto | Defeito original fechado; domínio de estado pendente em CQW-01 |

### 3.1 Escala e esqueleto

Readjudicação dos **34.952 casos do snapshot** com `adjudicar`: resultado
igual ao inventário atual **caso a caso e na mesma ordem**. `resumir` produziu
campos iguais aos do resumo persistido. Não foi repetida a varredura integral
dos 26,3 milhões de registros brutos dos ZIPs nesta revisão; o teste
independente aqui é sobre os casos persistidos e sua nova adjudicação.

Números confirmados: **3.401 casos**, **6.456 declarações adjudicadas**, todas
`PENÚLTIMO`, **35 companhias**, **111 documentos**. Direção: 2.430 casos
`MIL`, 971 `UNIDADE`. Só BPA/BPP. Os documentos alcançam **29.650 linhas
arquivadas** do painel; isso não prova defeito em todas essas linhas nem
autoriza corrigi-las. A premissa de usar a escala da DFP está explícita.

CSV anterior × atual: 300 linhas na mesma ordem, mesmas chaves e propostas;
`classe_confirmada` continua vazia. Diferenças por coluna: `linhas` 290,
`companhias` 3, `cobertura_acumulada_pct` 296, `mediana_bruta` 144,
`razao_sobre_ativo_total` 74 e `evidencia` 154. Não são 154 anotações humanas
perdidas: a coluna já era texto gerado, e as confirmações permanecem vazias.

Contagem SQL independente sobre o painel, com as 300 chaves do CSV:

| Universo | Cobertas / total |
|---|---:|
| Gerador: arquivados fora dos 111 documentos | 5.981.271 / 6.438.964 |
| Todos os arquivados | 6.008.928 / 6.468.614 |
| Painel inteiro | 6.680.366 / 7.177.705 |

Portanto as coberturas publicadas reproduzem. Continuam sendo cobertura de
códigos, não confirmação semântica nem autorização de join entre planos.

### 3.2 Temporal, métricas e consumidores

Diagnóstico real, separado da cadeia: **10.605 observações, 494 companhias**,
zero em todos os contadores de G1. A proteção de disponibilidade inclui o
ativo; casos sintéticos de recepção futura, data de rótulo incompatível,
ausência de linhagem, amostra vazia e interrupção da cadeia estão cobertos.
O limite `D + 3 meses` continua uma decisão declarada do contrato, não prova
de adequação a todo calendário fiscal possível.

Contraprova QW4 repetida localmente: 1.200 linhas sintéticas, 60 companhias;
B3 observado só nas 600 negativas. Apesar de superar os pisos de suporte,
fica `completo=False`, AUC agregada/intra e lift nulos, com motivos explícitos.
O teste integrado retorna `INDECIDIVEL`, não `PRONTO PARA CHALLENGER`.

Não-regressão: 600 linhas/60 companhias com os dois rótulos e 50
reamostragens produzem baselines completos. Em integração sintética com
G1/T1/T2 aprovados, o ramo `PRONTO PARA CHALLENGER` permanece alcançável.
Permutar as linhas preservou o resultado. Com 39 reamostragens o IC é
indisponível; o piso 40 é uma regra operacional explicitada, **não validação
empírica da cobertura estatística de 95%**.

A nova AUC por postos foi comparada com a definição por pares em **9.330
casos exaustivos**: n de 1 a 5, escores em {0,1,2}, todos os vetores binários
de alvo; igualdade, incluindo amostra de uma classe. A mudança de algoritmo
não alterou o estimando nesses casos.

QW5: a reprodução com 499 observações válidas num componente preservou a
amplitude **1,0** e a reprovação numérica de outro componente pleno.

Executar `auditor.executar()` em leitura retornou objeto igual ao JSON
publicado, com **uma etapa, G0**. Não foi chamada a CLI contra o diretório
publicado: sua gravação foi testada pelos testes com destino temporário.

### 3.3 Derivação

Leitura do código em `src/dados_estruturados.py:1254–1422`: contagens e
inserção usam `_candidatos_intermediarios`; identidade de pareamento e banda
são compartilhadas, e há asserção da igualdade entre grupos deriváveis e
linhas inseridas. Os avisos são testados no carregador real em
`tests/test_dados_estruturados.py::TestAvisosDaDerivacaoNoCarregador`.

Simulação independente numa conexão DuckDB **em memória**, com o painel
original anexado `READ_ONLY` e somente arquivados DRE/DFC copiados:

```text
arquivados de fluxo: 2.323.166
ResultadoDaDerivacao(criados=382454, recusados=7733, sem_antecedente=139435)
```

Reproduz os três números publicados. Isso verifica o contador, **não** a
correção semântica de todos os pareamentos. Não foi repetida nesta revisão a
análise multiexecução dos 141 grupos de N3; ela permanece evidência declarada
da implementação, coerente com o desempate insuficiente do `QUALIFY` que
continua no código. N2/N3 não são descobertas novas desta conferência.

## 4. Testes e rastreabilidade

Suíte completa executada:

```bash
CREWAI_STORAGE_DIR="$(mktemp -d /tmp/conferencia-qw-corrigidos.XXXXXX)" \
  .venv/bin/python -m pytest -q --tb=short
```

**2.132 passed, 30 warnings, zero falhas/skip, 140,54 s.** Avisos em dependências
e testes anteriores de modelo/guardrails; não são falhas desta onda.

Reexecução focada dos quatro arquivos abaixo: **275 passed em 32,91 s**.

```bash
.venv/bin/python -m pytest -q --tb=short \
  tests/test_rank03b_consumo_operacional.py \
  tests/test_inventario_escala_cvm.py \
  tests/test_esqueleto_plano_padrao.py tests/test_dados_estruturados.py
```

O MEMORY também recebeu registro paralelo de **2.139** casos da interface.
Não atribuir esse número à execução acima nem substituir a evidência medida
por composição aritmética de ondas: a árvore estava suja e compartilhada.
Esta revisão não certifica as alterações paralelas de interface/geração.

Hashes completos dos principais alvos conferidos antes e depois dos
diagnósticos; iguais aos declarados na implementação:

| Arquivo | SHA-256 |
|---|---|
| `scripts/auditar_rank03b_consumo_operacional.py` | `02af50bdb9b6745db99c0ad4fd46347d852ef778d0e551712d0d875519a68678` |
| `scripts/inventariar_escala_cvm.py` | `cde20df0a519d49ca0ad914a25a4317727b3df8c69cc2d1f553aaca5befa4140` |
| `scripts/esqueleto_plano_padrao.py` | `cd6f4916e7931baec956ffed579bcbf2ae1cda026a6bf3d6e9216fecba407fdd` |
| `src/dados_estruturados.py` | `b7587f2a3267f9f1828e134970ae1c064a85a3ec082655ce158ce32816de46cf` |
| `corpus/cvm/plano_padrao_contas.csv` | `db597d3a7b8c1b787850acc21269cf05f523f8a7f7f5052f5a580baf39226710` |
| `artefatos/cvm.duckdb` | `43e31d9f150e535f1ab20576d9aacf1a53b83ecc5424ca7d48ba50781e4cef18` |
| `artefatos/cvm_treino.duckdb` | `c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b` |

Artefatos também conferidos: inventário `f18c60dd8d2b…`, resumo
`177977798e85…`, Rank JSON `a2ef88bea647…`. O hash do contrato conferido é
`774935510cfa7a28e93d782ac79cfa7106ec5375f79dce0d794da546801e2afd`.

## 5. Encaminhamento para o próximo agente

1. Fechar CQW-01 com teste do **consumidor** para os nove estados válidos e
   estados inválidos; não basta testar o produtor do inventário.
2. Resolver a divergência H1.4/CQW-02, preservando a semântica de saldo do BPA.
3. Publicar errata CQW-03. Esses três itens não exigem reconstruir painéis,
   mudar valores, executar T1/T2 reais ou treinar.
4. Em frente separada, enfrentar N3 antes de reconstrução reproduzível;
   N2 requer identidade semântica de pareamento, não união por código.
   Curadoria do CSV pode continuar com escopo e evidência.
5. Manter o bloqueio real: escala/períodos do painel ainda não foram
   adjudicados/corrigidos de modo suficiente para G0. Uma futura reconstrução
   exige decisão explícita, quebra de hash declarada e análise de impacto
   sobre a etapa 10. Passar testes do instrumento não autoriza treino.

Não reabrir como defeitos novos QW1/QW2, a antiga vacuidade de G1 ou as
recusas já contadas de QW6. Não dizer que o alvo foi refutado: **a rodada
continua interrompida na qualidade do painel**. A terceira onda bancária
R-C5/R-C6/R-SUPORTE não foi certificada por esta revisão.
