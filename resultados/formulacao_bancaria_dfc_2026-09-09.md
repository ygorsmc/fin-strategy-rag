# DFC em bancos — formulação própria e auditoria de fontes

> **Continuação concluída em 2026-09-09:** os dois especialistas terminaram
> parecer, réplica e tréplica. O candidato prioritário passou a **B-DFC-01J,
> juros de instrumentos de captação no mesmo consolidado IFRS**, admitido
> apenas para piloto documental. Modelo e contribuição incremental da DFC
> seguem não validados. O texto abaixo preserva a investigação inicial;
> decisão atual, contraprovas e condições estão no
> [relatório do debate](debate_bancos_dfc_2026-09-09.md).

**Data:** 2026-09-09. **Estado:** investigação preliminar; nenhum modelo,
baseline preditivo ou rótulo futuro foi calculado nesta rodada.

**Recomendação da sessão principal:** preparar um piloto de dados para
**previsão probabilística do encargo de captação**, usando componentes da DFC
como informação adicional. Não interpretar FCO negativo como deterioração
bancária. A hipótese econômica é plausível; a viabilidade empírica do ML e o
ganho específico da DFC continuam **não demonstrados**.

**Não houve consenso final de dois especialistas.** Os agentes de Ciência de
Dados e Finanças trabalharam separadamente e enviaram achados preliminares,
mas ambos foram interrompidos por limite de uso da plataforma antes da réplica
e dos pareceres finais. A síntese abaixo é da sessão principal, com checagem
direta das fontes. Não equivale ao debate concluído da investigação não
financeira de 2026-09-08.

Os pareceres de um agente não foram repassados ao outro antes da interrupção.
Esse isolamento de contexto não equivale a segregação física: o ambiente de
arquivos é compartilhado e os agentes receberam instruções de não consultar
o trabalho alheio. Não houve troca de rótulos ou resultados de treino.

| Especialidade | Contribuição preliminar recebida | O que não foi concluído |
|---|---|---|
| Ciência de Dados | Descontinuidade de formatos do Pilar 3 e limitações de acesso às séries do IFData | Auditoria final do desenho, amostra e protocolo estatístico |
| Finanças | Perímetro contábil/prudencial, interpretação da média LIQ1 e hipótese de encargo de captação | Aprovação do conceito exato do alvo e debate final |

O acesso bem-sucedido pela interface alternativa do IFData, documentado
adiante, foi obtido pela sessão principal **depois** desses achados.

## 1. A pergunta econômica

> Conhecendo apenas os documentos disponíveis na data D, podemos melhorar os
> cenários do gasto futuro de captação de um banco ao acrescentar sua DFC ao
> balanço, à DRE e ao cenário de juros?

Uso pelo analista: revisar premissas da margem financeira e identificar quais
componentes do financiamento merecem investigação. A saída proposta é uma
distribuição de um fundamento contábil, acompanhada de fontes e hipóteses —
não uma recomendação de investimento, previsão de corrida bancária ou
diagnóstico automático de insolvência.

Nos bancos, empréstimos a clientes podem compor as atividades operacionais da
DFC. Assim, expansão de crédito pode consumir caixa operacional sem indicar
lucro de baixa qualidade. Essa diferença inviabiliza **transferir a
interpretação** do Rank 3-B não financeiro; não prova que a DFC seja inútil
como preditor. [CPC 03, especialmente §15](https://conteudo.cvm.gov.br/export/sites/cvm/menu/regulados/normascontabeis/cpc/CPC_03_R2_rev_13.pdf).

### Alternativas examinadas

| Formulação | Papel possível da DFC | Encaminhamento desta investigação |
|---|---|---|
| **Encargo de captação futuro** | Movimentações de depósitos, captações, crédito e juros pagos, quando reconciliáveis | **Primeiro piloto de dados recomendado**, condicionado a conceito, perímetro, período e vintage |
| **LCR/NSFR futuros publicados** | Fluxos históricos como complemento aos indicadores regulatórios defasados | Segunda alternativa: alvo mais diretamente ligado à liquidez, mas cobertura e extração histórica ainda não verificadas |
| **NPL/custo do crédito/capital** | Complemento, sem identidade direta com FCO | Não priorizado nesta rodada; exige outra justificativa e respeito aos negativos anteriores |
| **FCO negativo ou FCF industrial como “estresse bancário”** | O próprio fluxo vira um rótulo de deterioração | Não adotar essa interpretação econômica |

O debate anterior já testou deriva dos ratings AA–H do IFData para custo do
risco, sem ganho convincente, e encontrou incompatibilidade SCR × COSIF.
Este trabalho **não reabre esse experimento** nem herda seus números como
evidência favorável. Procedência: [debate anterior, “Proposta B”](debate_modelo_util_2026-08-26.md).

## 2. O que foi efetivamente encontrado no projeto

Painel lido exclusivamente em modo `read_only=True`:
`artefatos/cvm_treino.duckdb`, SHA-256
`c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b`.
Todas as consultas desta seção restringem `dt_refer <= 2026-03-31`.
Os cinco emissores são os do corpus, identificados por `cd_cvm`, **não** pela
heurística `is_banco` anteriormente retratada.

### 2.1 Cobertura estrutural não é tamanho de amostra utilizável

Contagem da conta candidata a FCO `6.01`, em registros rotulados
`tipo_periodo='trimestral'`, considerando DFC_MI e DFC_MD:

| Emissor público | `cd_cvm` | Datas distintas | Primeira–última referência | Métodos presentes |
|---|---|---:|---|---|
| Bradesco | `000906` | 17 | 2022-03-31–2026-03-31 | MI |
| Banco do Brasil | `001023` | 17 | 2022-03-31–2026-03-31 | MI |
| Itaú Unibanco Holding | `019348` | 58 | 2011-03-31–2026-03-31 | MI |
| Santander | `020532` | 59 | 2011-03-31–2026-03-31 | 55 MI + 4 MD, sem sobreposição nessas datas |
| BTG Pactual | `022616` | 17 | 2022-03-31–2026-03-31 | MI |

São **168 registros**, não 168 exemplos supervisionados prontos. A conta
total não garante componentes utilizáveis, disponibilidade em D, intervalo
futuro completo ou correspondência com a entidade do BCB. Nenhum desses
registros tem duração superior a 100 dias nessa consulta específica; isso
**não resolve** os problemas de período e linhagem encontrados no painel
geral. A seleção da conta aqui é diagnóstica, não uma certificação RN09.

Para três dos cinco bancos, a janela trimestral atual começa em 2022, embora
existam DFCs anuais anteriores. Logo, “painel 2011–2026” não significa quinze
anos de DFC trimestral para cada banco.

### 2.2 Há componentes úteis, mas não um mapa universal por código

A busca em descrições encontrou, por exemplo:

- BB: variação de depósitos de clientes e captação de passivos de longo prazo;
- Itaú: variações de depósitos, de captações no mercado aberto e de depósitos
  compulsórios;
- outros bancos: componentes com classificações e detalhamento diferentes.

Contraprova concreta ao mapeamento cego: no Itaú, `6.01.02.11` aparece tanto
como variação de captações no mercado aberto quanto como variação de
depósitos, em períodos distintos. São necessárias descrição, período,
documento e conferência; o código sozinho não fixa a semântica.

A busca lexical por `captac`/`funding` na DRE local desses cinco emissores
retornou **zero linhas**. Isso **não significa ausência de despesa de
financiamento**: existem descrições como “Despesa de Juros” e “Despesa de
Juros e Similares”. Esses agregados não devem ser renomeados automaticamente
como despesa de captação do IFData. Usá-los seria outra especificação do
alvo, dependente de reconciliação própria.

Os problemas de vintages e derivações já documentados continuam válidos:
[auditoria de prontidão DFC, §2](viabilidade_ml_dfc_2026-09-08.md).

## 3. Fontes externas: o acesso avançou, a comparabilidade não está pronta

### 3.1 IFData: a rota alternativa funcionou

OData respondeu ao catálogo/metadados, mas as tentativas de obter
`IfDataValores`/`IfDataCadastro` retornaram HTTP 500. Isso foi uma falha de
acesso observada, **não prova de inexistência dos dados**.

Inspecionando o código público da interface oficial, a sessão principal
identificou as rotas que ela própria utiliza:

- [Interface histórica, até 2024](https://www3.bcb.gov.br/ifdata/index2024.html)
  → [catálogo 2000–2024](https://www3.bcb.gov.br/ifdata/rest/relatorios2000a2024).
- [Interface a partir de 2025](https://www3.bcb.gov.br/ifdata/)
  → [catálogo 2025–2030](https://www3.bcb.gov.br/ifdata/rest/relatorios2025a2030).
- Arquivo listado pelo catálogo: `rest/arquivos?nomeArquivo=<campo f>`.
  O nome é descoberto no catálogo, não construído supondo um padrão eterno.

**Verificado com HTTP 200**, para 2024-12 e 2025-03: catálogo, dicionário
`info`, cadastro prudencial e primeiro arquivo numérico `dados..._1.json`.
Os dois arquivos numéricos foram recebidos e reconhecidos como JSON, mas
**não foi construída uma série de saldos nem extraído um gabarito por banco**.

| Data-base | Relatório DRE prudencial no catálogo | Campo `ge` observado | Entradas no cadastro `1009` | Bytes do primeiro arquivo numérico |
|---|---:|---|---:|---:|
| 2024-12 | 113 | `15/04/2026` | 1.367 | 15.612.512 |
| 2025-03 | 116 | `17/04/2026` | 1.366 | 14.675.928 |

Essas entradas **não são 1.367/1.366 bancos elegíveis** nem rótulos úteis.
Os cadastros contêm códigos que ainda precisam de interpretação e filtros.
O campo `ge` não foi certificado como data de primeira publicação. Os próprios
avisos dos relatórios informam republicação de dados: não se pode tratar o
arquivo servido hoje como informação disponível em 2024/2025.

Esta rota é pública e oficial, mas é uma interface de apoio ao site; sua
estabilidade futura não está garantida. Um coletor precisará de snapshots,
hashes, validação de esquema e falha explícita quando o contrato mudar.

### 3.2 O conceito contábil muda em 2025 — confirmado nos campos ativos

Não foi suficiente encontrar nomes no dicionário `info`, que contém rubricas
de mais de uma época. A checagem cruzou seus IDs com as colunas efetivamente
ativas (`trel.c`, incluindo subcolunas) de cada relatório DRE prudencial:

| Data-base examinada | Campo ativo | Nome na fonte | Composição indicada pela fonte |
|---|---:|---|---|
| 2024-12 | `78209` | Despesas de Captação (b1) | `[81100008]+[81980008]+[81986002]+[81912007]` |
| 2025-03 | `79824` | Despesa de Juros com Captações (g1) | `[8110000002]+[8120000009]-[8115020001]-[8118500009]-[8119110003]-[8119120000]-[8119130007]` |
| 2025-03 | `79825` / `79826` / `79827` | Ajuste cambial / hedge de valor justo / outros resultados de captações | Componentes apresentados separadamente |
| 2025-03 | `79828` | Despesas de Captações (g) | Agregado de despesas e ajustes, distinto de apenas juros |

Fontes diretas:
[dicionário 2024-12](https://www3.bcb.gov.br/ifdata/rest/arquivos?nomeArquivo=ifdata/202412/info202412.json),
[dicionário 2025-03](https://www3.bcb.gov.br/ifdata/rest/arquivos?nomeArquivo=ifdata_2025_2030//202503/info202503.json)
e os respectivos catálogos acima, relatórios 113 e 116.

**Consequência:** não emendar `78209` e `79824` por semelhança verbal. O
encargo total também contém efeitos que não são preço puro do funding. Nem
crescimento da despesa prova estresse, nem sua razão por depósitos mede
automaticamente um custo comparável: volume, mix, moeda e perímetro precisam
ser considerados. Essa conclusão é uma inferência contábil da composição
observada, não resultado de um modelo.

### 3.3 A DRE do IFData acumula por semestre, não pelo ano inteiro

Os avisos `trel.rp` dos relatórios 113/2024-12 e 116/2025-03 especificam:
março cobre janeiro–março; junho, janeiro–junho; setembro, julho–setembro;
dezembro, julho–dezembro. Portanto, após validar entidade, regime e vintage:

```text
Q1 = saldo de março             Q2 = saldo de junho − saldo de março
Q3 = saldo de setembro          Q4 = saldo de dezembro − saldo de setembro
```

Subtrair junho de setembro ou interpretar dezembro como ano completo
fabricaria o alvo errado. A regra é da fonte IFData; não autoriza aplicá-la
indiscriminadamente aos formulários CVM. Também não autoriza subtrair versões
incompatíveis de dois arquivos.

### 3.4 Perímetro e primeira disponibilidade continuam sendo bloqueios reais

A metodologia distingue instituição individual, conglomerado financeiro e
conglomerado prudencial; suas séries não começam todas na mesma data.
Informa também calendário de disponibilização de 60/90 dias. Esse calendário
**não reconstrói vintages**. [Metodologia oficial IFData, pp. 1–2](https://www.bcb.gov.br/conteudo/dadosabertos/BCBDesig/IFData%20-%20Esclarecimentos%20e%20Metodologia.pdf).

Um CNPJ ou nome semelhante ajuda a resolver identidade, mas não demonstra
igualdade de consolidação. O cruzamento exigirá histórico
`cd_cvm ↔ CNPJ ↔ entidade/conglomerado BCB`, com vigência e evidência de
perímetro. Não casar por ativo semelhante, não repetir holding e banco como
observações independentes, não tratar sumiço do cadastro como ausência de
estresse. O universo não pode conter apenas sobreviventes de hoje.

Se não houver DFC de perímetro reconciliável, o experimento **DFC + alvo
IFData não está pronto**. Prever só com IFData seria outro braço, não uma
validação da utilidade da DFC.

### 3.5 Pilar 3: alternativa legítima, não uma série pronta

O catálogo oficial informa v1 até 2023-06 e v2 a partir de 2025-12; o intervalo
intermediário foi divulgado exclusivamente em PDFs das instituições. O BCB
catalogua links; os bancos hospedam os dados. Portanto, o trecho
2023T3–2025T3 exige recuperação documental, e catálogo acessível não garante
histórico completo. [Pilar 3 v1](https://dadosabertos.bcb.gov.br/dataset/pilar3),
[Pilar 3 v2](https://dadosabertos.bcb.gov.br/dataset/pilar3-v2).

A LIQ1 publica médias diárias do trimestre. Não fornece o menor LCR diário
nem revela toda ocorrência transitória de insuficiência de liquidez. Um alvo
baseado nela deve ser denominado **LCR médio publicado**, não “violação em
qualquer dia”. LIQ2/NSFR precisa de tratamento próprio, sem herdar a
agregação da LIQ1. [Tabelas oficiais do Pilar 3, LIQ1/LIQ2](https://www.bcb.gov.br/content/estabilidadefinanceira/regulacao_prudencial_docs/Relatorio_Pilar_3/Tabelas_Pilar_3.pdf).

Não foram contados eventos de LCR baixo, construído painel nem estimada
frequência de crise. Recomendar esta alternativa em segundo lugar é uma
avaliação de custo e adequação de fonte, **não uma rejeição estatística**.

## 4. Esboço do experimento — não é pré-registro aprovado

Identificador de trabalho: **B-DFC-01**. Não renumera o ranking original nem
reabre automaticamente C1, Rank 3 ou CAND-04.

### Alvo proposto

`Y(i,D)` = encargo contábil de captação, em reais, no **primeiro trimestre
fiscal inteiramente posterior a D**, para a entidade/perímetro `i`.

Antes de produzir `Y`, é obrigatório fixar qual rubrica e regime representam
esse conceito. A tabela da seção 3.2 mostra por que essa decisão está aberta.
Não escolher o agregado ou só juros depois de comparar resultados. A série
pré-2025 pode servir para investigação histórica em regime próprio, mas
desempenho nela não valida aplicação em 2025–2026 sem uma ponte demonstrada.

O protótipo poderá apresentar mediana e intervalos preditivos. Normalização
de treino/erro, se necessária, usa escala conhecida em D e será declarada;
não se divide silenciosamente pelo saldo futuro. Datas de publicação e
períodos fiscais não são intercambiáveis. Documento recebido no meio do
trimestre não permite chamar esse trimestre inteiro de “futuro”.

### Preditores e controles que separam duas perguntas

1. **O aprendizado ajuda?** Comparar com persistência, sazonalidade e um
   cenário simples de carregamento do encargo, dadas as últimas captações,
   seu mix e juros conhecidos em D. Documentar hipóteses e parâmetros
   estimados; um baseline com estimação não é “puramente determinístico”.
2. **A DFC ajuda?** Comparar a mesma família de modelo e o mesmo orçamento de
   ajuste **sem DFC** e **com DFC**, nas mesmas observações e partições.

O controle sem DFC deve incluir níveis **e variações** de saldos relevantes
de balanço, despesas passadas, composição de financiamento e informação
macroeconômica disponível em D. Caso contrário, uma simples variação de
depósitos poderá parecer contribuição exclusiva da DFC.

Os candidatos a preditores DFC são fluxos reconciliados de depósitos,
captações de mercado/longo prazo, crédito e juros efetivamente pagos, com
idade da informação e flags de ausência/método. Nenhum campo é obrigatório
por mera coincidência de código. Não somar ajustes de juros ao lucro com
pagamentos de juros, duplicar conta-pai e filha, ou usar juros de aplicações
como despesa de funding. A ponte entre fluxo e variação de saldo deve declarar
câmbio, aquisições e demais ajustes não caixa, quando aplicáveis.

Juros efetivamente realizados **depois de D** não entram como preditor. Um
cenário condicionado a juros futuros fornecidos pelo analista é outro produto
e deve ser avaliado como cenário, não como previsão incondicional.

### Validação exigida antes de qualquer alegação de utilidade

- Walk-forward por data de decisão, com treino restrito a rótulos já
  disponíveis, purga de horizontes sobrepostos e tuning só em janelas internas.
- Transformações e imputação ajustadas somente no treino; empresas e períodos
  do teste não podem escolher cortes, rubricas ou hiperparâmetros.
- Perda de quantis/calibração dos intervalos e erro em reais/escala
  pré-definida; resultado por banco e por regime de juros. Desempenho agregado
  não pode ser dominado pelo porte dos maiores bancos.
- Inferência pareada com dependência por instituição e por tempo; contar
  bancos e janelas independentes, não contas contábeis como réplicas.
- Auditoria dos erros que mudariam uma premissa do analista. Concordância
  entre agentes LLM não substitui julgamento independente desse uso.

**Pendência de protocolo explícita:** T1/T2 do projeto foram formulados com
taxa de evento e AUC; essas estatísticas não se aplicam diretamente a `Y`
contínuo. Este relatório **não revoga os testes nem declara aprovação por
analogia**. Antes de execução, os especialistas devem fechar o protocolo
próprio de regressão, preservando as perguntas sobre baseline mecânico e
sinal dentro do mesmo emissor, com limiares e tamanho amostral justificados
antes de observar desempenho. Se houver conversão em alerta binário, corte
e componentes do alvo precisam passar pelos gates correspondentes. Enquanto
isso estiver aberto, não há autorização metodológica para chamar um treino
de confirmatório.

## 5. Trabalho necessário e condição de parada

| Ordem | Entrega | Evidência para seguir |
|---|---|---|
| 1 | Piloto de contrato de dados em poucas entidades, escolhidas por disponibilidade/perímetro, não por desfecho | Fonte, página/campo, unidade, sinal, período, regime e entidade conferidos; divergências explicitadas |
| 2 | Recuperabilidade de vintages CVM/BCB/RI e linhagem das subtrações | Cada entrada tem disponibilidade histórica demonstrável; o arquivo mais recente não se faz passar pelo original |
| 3 | Inventário da interseção DFC × alvo reconciliado | Bancos, datas e janelas utilizáveis contados depois dos filtros; casos não elegíveis e motivo preservados |
| 4 | Pré-registro e revisão independente de DS/Finanças | Conceito, horizonte, protocolo, perdas, limiares de ganho, amostra e regras de rejeição fechados |
| 5 | Baselines antes de ML | Resultado auditável de referências econômicas simples, sem ajuste pelo teste |
| 6 | Aprendizado sem/com DFC e avaliação do analista | Ganho incremental fora da amostra, calibrado, material e com evidência de uso; caso contrário, não adicionar ML/DFC ao produto |

**Primeiro lote sugerido:** investigar 2024T1–2024T4 e a transição 2025T1,
sem usar desempenho para selecionar bancos. É um lote de conferência de
conceito/período, **não amostra para aprovar modelo**. Todos os valores que
forem consultados nesse piloto deverão ser marcados como desenvolvimento.

Não é necessário um humano inventar um rótulo subjetivo para cada despesa
futura: o gabarito contábil é extraível e reconciliável. O trabalho especializado
está em aprovar a equivalência dos conceitos e o uso econômico, além de
resolver divergências. Extração por agente pode ajudar, mas não confere a si
mesma validade independente.

**Parar sem treinar** se perímetros não forem reconciliáveis, vintages forem
irrecuperáveis para a alegação pretendida, ou a interseção ficar insuficiente.
Um estudo explicitamente *as-restated* pode investigar estrutura, mas não
substitui confirmação point-in-time. Não trocar de alvo após reprovação para
preservar a narrativa de sucesso.

## 6. Procedência executável e limites da entrega

### Consultas locais de reprodução

Executar com DuckDB somente leitura. São consultas estruturais, sem acessar
o holdout nem calcular desfechos:

```python
import duckdb

c = duckdb.connect('artefatos/cvm_treino.duckdb', read_only=True)
base = """
FROM fatos_contabeis
WHERE cd_cvm IN ('000906','001023','019348','020532','022616')
  AND dt_refer <= DATE '2026-03-31'
"""
print(c.sql("""
SELECT cd_cvm, count(*) AS registros,
       count(DISTINCT dt_refer) AS referencias,
       min(dt_refer), max(dt_refer),
       count(*) FILTER (WHERE dt_fim_exerc - dt_ini_exerc > 100) AS longos
""" + base + """
AND demonstrativo LIKE 'DFC_%'
AND cd_conta = '6.01' AND tipo_periodo = 'trimestral'
GROUP BY 1 ORDER BY 1
""").fetchall())
print(c.sql("""
SELECT cd_cvm, ds_conta, count(*)
""" + base + """
AND demonstrativo = 'DRE'
AND (ds_conta_norm LIKE '%captac%' OR ds_conta_norm LIKE '%funding%')
GROUP BY ALL
""").fetchall())
print(c.sql("""
SELECT cd_cvm, cd_conta, ds_conta, count(*)
""" + base + """
AND demonstrativo LIKE 'DFC_%' AND tipo_periodo = 'trimestral'
AND (ds_conta_norm LIKE '%deposit%' OR ds_conta_norm LIKE '%captac%')
GROUP BY ALL ORDER BY 1, 2, 3
""").fetchall())
```

### Reprodução dos metadados externos

Os GETs abaixo são públicos, gratuitos e não baixam saldos do holdout. A
resposta atual pode mudar; os valores observados nesta sessão estão nas
seções 3.1–3.3. Não foram arquivados snapshots dos corpos HTTP nesta rodada.

```python
import requests

base = 'https://www3.bcb.gov.br/ifdata/rest/'
for rota, data, relatorio in [
    ('relatorios2000a2024', 202412, 113),
    ('relatorios2025a2030', 202503, 116),
]:
    r = requests.get(base + rota, timeout=30)
    r.raise_for_status()
    catalogo = next(x for x in r.json() if x['dt'] == data)
    dre = next(x['trel'] for x in catalogo['files']
               if x.get('trel', {}).get('id') == relatorio)
    print(data, dre['ge'], dre['rp'])
    nome = next(x['f'] for x in catalogo['files']
                if x['f'].endswith(f'/info{data}.json'))
    r = requests.get(base + 'arquivos',
                     params={'nomeArquivo': nome}, timeout=30)
    r.raise_for_status()

    def ids(colunas):
        for coluna in colunas:
            yield coluna['ifd']
            yield from ids(coluna.get('sc', []))

    ativos = set(ids(dre['c']))
    print([x for x in r.json()
           if x['id'] in ativos and 'Capta' in x['n']])
```

### Escopo preservado

- Nenhum painel, regra de produto, dependência, manifesto ou teste foi alterado
  nesta investigação bancária. Foram acrescentados este relatório e o handoff.
- Nenhuma chamada paga de OCR/LLM foi iniciada pela sessão principal; não se
  confunde isso com contabilização do uso da plataforma dos agentes.
- O `holdout_2T2026` não foi aberto; leituras numéricas externas limitaram-se
  a arquivos históricos, e consultas locais ao corte 2026-03-31.
- Não houve treino, contagem de eventos futuros ou comparação de desempenho.
  Não há novo resultado de ML aprovado ou rejeitado estatisticamente.
- A suíte de **1.796 testes** passou na etapa anterior da retomada DFC,
  conforme seu relatório. Esta continuação só documental não foi tratada como
  nova execução dessa suíte; foram conferidos diff e links locais.

**Próxima ação:** contrato de dados e vintages do B-DFC-01, começando pela
ponte de perímetro e pela distinção entre encargo agregado e juros. Retomar
os dois pareceres independentes quando a plataforma permitir, antes de
congelar o experimento. O Rank 3-B não financeiro permanece documentado,
mas não é a prioridade solicitada agora.
