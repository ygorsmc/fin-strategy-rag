# Retomada de ML com DFC — viabilidade e pendências verificadas

**Data:** 2026-09-08. **Decisão:** preparar um experimento novo de consumo
operacional persistente; **não treinar no painel atual** antes de resolver
integridade e disponibilidade histórica. Hipótese viável para investigação,
não modelo validado. Custo de API paga nesta rodada: zero.

Este documento é diagnóstico e handoff, **não pré-registro confirmatório**.
Não foram calculados eventos, AUC, lift ou baselines de um novo alvo. Nenhum
limiar antigo foi relaxado. O `holdout_2T2026` não foi acessado.

## 1. O que mudou desde a avaliação inicial

A DFC já está carregada: não estamos mais bloqueados pela ausência de FCO.
O [relatório da carga](carga_dfc_e_point_in_time_2026-08-27.md) registra a
inclusão de DFC_MI/DFC_MD e do cadastro de recebimentos. Depois, o
[Rank 3](validacao_rank03_conversao_caixa_2026-08-27.md) mediu um alvo
específico de variação de accrual e o rejeitou em T1. A
[etapa 19](validacao_etapa19_fcf_yield_2026-09-08.md) ficou inconclusiva para
FCF yield e retorno futuro. Nenhum desses resultados testa o evento proposto
abaixo.

O [registro de becos sem saída, A.1](becos_sem_saida.md#a1-alvos-que-reprovaram-o-protocolo-dos-dois-testes)
admite expressamente um Rank 3-B com evento definido, exemplificando FCO
negativo persistente. A afirmação genérica anterior do MEMORY de que toda
reformulação estaria encerrada excedia esse registro específico.

Também havia uma afirmação excessiva sobre dados: **guardar `DT_RECEB` não
torna automaticamente os valores e todas as suas derivações point-in-time**.
As seções seguintes distinguem o que foi carregado do que ainda precisa ser
reconstruído. Não alteramos o painel para produzir este diagnóstico.

## 2. Evidência reproduzível da base atual

Auditor: [scripts/auditar_prontidao_dfc.py](../scripts/auditar_prontidao_dfc.py).
Saída completa: [auditoria_prontidao_2026-09-08.json](../artefatos/dfc_viabilidade/auditoria_prontidao_2026-09-08.json).
Consulta somente leitura; `dt_refer <= 2026-03-31`. SHA-256 do painel,
verificado antes/depois da execução:

```text
c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b
```

| Medição estrutural | Resultado | Interpretação e limite |
|---|---:|---|
| FCO identificado por código **e descrição** | 39.773 linhas, 741 companhias | Mistura arquivado/derivado e acumulado/isolado; **não é número de exemplos rotulados** |
| Formulários com DFC retida e data da mesma versão | 23.280/23.280 | O join documental é possível; não certifica os operandos dos derivados |
| Versões retidas recebidas após `last_day(dt_refer + 3 meses)` | 2.483/23.280 | Demonstra a importância de aplicar disponibilidade; **não é a contagem de exclusões do antigo Rank 3** |
| Versões cadastradas sem DFC retida correspondente | 4.867 | Ausentes nessa tabela; não prova que cada versão continha DFC nem que seja irrecuperável |
| FCO derivado rotulado trimestral com duração de seis meses | 12 linhas | Não pode entrar como trimestre isolado sem reconciliação |
| FCO derivado rotulado trimestral com duração de dois meses | 1 linha | Investigar exercício irregular ou erro antes de somar |
| FCO arquivado rotulado trimestral com duração de um/dois meses | 20/4 linhas | Período curto pode ser real; não completar meses nem descartar por desempenho |
| Cadastro local com setor preenchido | 5/741 companhias | `NOT is_banco` não equivale a classificação validada de não financeiras |

As durações usam `date_diff('month', início, fim + 1 dia)` como diagnóstico.
Ter resultado 3 **não certifica** alinhamento ao trimestre fiscal: o gate
deverá verificar datas exatas, continuidade, exercício e ausência de
sobreposição.

O código `6.01` também aparece com a descrição de atividades de
seguradora/resseguradora em 38 linhas. O auditor separa essas descrições;
o mapeamento do produto continua sujeito à RN09 e à conferência por conceito.
Não introduzimos um novo conceito consultável nem tratamos código isolado
como significado universal.

No recorte de FCO com descrição aceita, pareando por companhia, trimestre,
tipo de período e datas exatas, existe **um** par MI/MD, sem divergência acima
de R$ 0,50. Essa chave não é a contagem de cinco sobreposições gerais do
relatório da carga. Não transportar uma contagem para a outra. Mesmo sem
conflito nesse recorte, `max(valor)` não é política de reconciliação válida
para conflitos futuros.

### 2.1 Por que ainda falta reconstrução histórica

Em [src/dados_estruturados.py](../src/dados_estruturados.py), o esquema de
`documentos` está na linha 296; `_e2`, a partir da linha 900, conserva apenas
a maior versão numérica. A tabela de datas não contém os valores antigos.

As derivações de 2T/3T, a partir da linha 1215, usam o acumulado anterior
disponível e carregam apenas a versão do minuendo. A derivação de 4T, a partir
da linha 1316, também depende de dois documentos, mas não preserva os dois
identificadores como linhagem. Subtrair o último acumulado disponível pode
produzir seis meses quando o intermediário falta.

**Contrato necessário:** selecionar versões disponíveis em D **antes** da
aritmética; conservar todos os operandos e exigir que a maior data de
disponibilidade deles seja no máximo D. O resultado deve declarar intervalo,
método, unidade, origem e fórmula. Marcar apenas `origem='derivado'` não fecha
esse contrato.

Também não basta remover o filtro de maior versão e recarregar às cegas.
Inspecionamos uma fonte bruta: `itr_cia_aberta_DFC_MI_con_2024.csv` tem
**1.365 chaves** de FCO/intervalo com `ORDEM_EXERC=ÚLTIMO` e **nenhuma** com
mais de uma versão. Caminho, hash e contagem estão no JSON. É evidência de
uma fonte, não inventário de todos os ZIPs. Primeiro verificar quais vintages
realmente existem nos brutos; os ausentes podem exigir recuperação dos
formulários originais identificados no cadastro.

A CVM informa que os arquivos de DFP são atualizados com reapresentações e
disponibiliza endereços dos formulários. Isso orienta a recuperação, **não
garante que todos os vintages necessários já estejam nos CSVs locais**.
[Fonte: dataset DFP da CVM](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp).

### 2.2 Duas desconformidades do experimento antigo

O [pré-registro do Rank 3, §4](pre_registro_rank03_conversao_caixa_2026-08-27.md)
exigia filtro de recebimento e contagem de excluídos. Em
[scripts/auditar_rank03_conversao_caixa.py](../scripts/auditar_rank03_conversao_caixa.py):

1. `_carregar_base`, linhas 67–103, não consulta `documentos` nem transporta
   datas/versões. O filtro prescrito **não foi implementado**.
2. `construir_amostra` filtra ativo e lucro positivo antes de construir a
   tabela `futuro`, linhas 136–159. Com isso, exige implicitamente esses
   critérios também em `t+4`, apesar de o protocolo restringir a saúde em
   `t`. Casos com futuro disponível, mas fora desses filtros, entram como se
   fossem censura por ausência de futuro.

Os números negativos publicados continuam sendo os da amostra efetivamente
calculada. **Não representam execução integral do protocolo congelado.**
Não houve remedição nem aprovação retrospectiva nesta sessão; corrigir a
população e a temporalidade seria uma execução distinta, declarada.

## 3. Revisões independentes e réplica mediada

Dois agentes especialistas começaram em contextos novos, sem acesso ao
parecer do outro e sem contato direto. Ambos puderam ler as mesmas fontes
históricas do projeto; portanto, o isolamento é entre os **novos pareceres**,
não cegamento aos resultados publicados. A sessão principal executou a
auditoria estrutural e mediou as objeções após os pareceres iniciais.

| Rodada | Ciência de Dados | Finanças |
|---|---|---|
| Parecer inicial | Reconstrução PIT primeiro; evento de dois trimestres negativos é hipótese distinta; identificou seleção pelo futuro no auditor antigo | FCO antes de FCF; propôs dois semestres negativos para cobrir um ciclo anual; rótulo numérico não exige gold humano por linha |
| Objeção mediada | Dois trimestres podem apenas refletir semestre sazonalmente fraco | Dois semestres ainda não provam materialidade; mudar população após medir é inadmissível |
| Encerramento | Aceitou dois semestres como preferência **a priori**, sem comparar os dois alvos | Manteve dois semestres e dispensou filtro de lucro positivo atual |
| Veredito comum | **Preparar e auditar; treino bloqueado por integridade/PIT** | **Preparar e auditar; utilidade e ML ainda não demonstrados** |

Uma revisão transversal adicional por `auditor_conformidade` foi solicitada,
mas o agente não executou por limite de uso da plataforma. **Não contar essa
revisão como realizada.** A verificação local e os testes estão na seção 6;
esta sessão não declara uma etapa de implementação do produto concluída.

## 4. Candidato preferido para o próximo pré-registro

**Rank 3-B — início de consumo operacional persistente**, em companhias não
financeiras que hoje apresentam FCO dos últimos quatro trimestres positivo.
Não herdar o corte de R$ 1 bilhão nem lucro positivo do experimento anterior.
A composição definitiva do universo precisa ser congelada antes de medir.

```text
D  = data de decisão, com informação efetivamente disponível em D
q1 = primeiro trimestre fiscal cujo início seja posterior a D

S1 = FCO(q1) + FCO(q2)
S2 = FCO(q3) + FCO(q4)

Y = 1 se S1 < 0 e S2 < 0
Elegibilidade proposta: FCO_TTM conhecido em D > 0
```

Os dois blocos não se sobrepõem. O horizonte cobre um ciclo anual futuro,
mas exige mais espera e pode reduzir a amostra. Não foi feita contagem de
eventos. Não medir também dois trimestres e escolher o alvo mais favorável.

**Uso pretendido:** antecipar empresas cuja operação passa a consumir caixa
para orientar investigação de recebíveis, estoques, fornecedores e fontes de
financiamento. O evento não significa fraude, insolvência, recomendação de
investimento nem deterioração economicamente material. Caixa ligeiramente
negativo e consumo por crescimento precisam de interpretação distinta.

**Gabarito:** os fluxos futuros podem produzir rótulos contábeis automaticamente,
depois de validar valores e intervalos. Conferência de mapeamento e exceções
continua necessária. Já o julgamento de relevância e tempo economizado pelo
analista exige avaliação humana própria; agente especialista não substitui
essa evidência com rótulos que ele próprio inventou.

O CPC 03 relaciona fluxo operacional histórico à avaliação de geração futura;
também distingue investimento de operação e admite políticas alternativas
para juros/dividendos. Por isso, comparar FCO requer conferir classificação e
mudanças de política. A estrutura econômica dos bancos demanda tratamento
próprio: o piloto não se transfere aos cinco bancos do produto.
[CPC 03, §§13–16 e 31–34A](https://conteudo.cvm.gov.br/export/sites/cvm/menu/regulados/normascontabeis/cpc/CPC_03_R2_rev_13.pdf).

Barth, Cram e Nelson (2001) encontraram contribuição de componentes de accrual
para prever fluxos futuros. Isso fundamenta investigar relações contábeis,
**não valida nosso evento, uma família de ML ou sua eficácia no Brasil**.
[Artigo original, resumo no acervo de Stanford](https://www.gsb.stanford.edu/faculty-research/publications/accruals-prediction-future-cash-flows).

**Por que não começar por FCF:** fluxo líquido de investimento inclui mais
que capex; é necessário mapear os desembolsos pertinentes e seus sinais.
[CPC 03, §16](https://conteudo.cvm.gov.br/export/sites/cvm/menu/regulados/normascontabeis/cpc/CPC_03_R2_rev_13.pdf).
FCF tampouco tem definição uniforme ou significa automaticamente caixa
disponível ao acionista. [SEC, C&DI 102.07](https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/non-gaap-financial-measures).
Uma aprovação de integridade de preços não valida a semântica de capex/FCF.

## 5. Trabalho necessário, em ordem

1. **Provar recuperação histórica em pequena escala.** Selecionar formulários
   por estrutura — versões múltiplas, métodos DFC e exercícios —, não pelo
   desfecho. Inventariar vintages nos brutos e testar a recuperação dos
   ausentes por `ID_DOC`/`LINK_DOC`. Guardar hashes, versão e datas; não
   retroagir um valor atual à primeira entrega. Se a recuperação falhar,
   publicar cobertura efetiva e considerar snapshots prospectivos, sem
   promover backtest as-restated a confirmação histórica.
2. **Construir tabela de pesquisa separada e derivação as-of.** Não substituir
   `cvm.duckdb` nem `cvm_treino.duckdb`. Resolver conceito FCO, conflitos de
   método, unidade, períodos e linhagem dos operandos. Validar reconciliação
   de acumulados/ano e não derivar saldos de caixa como se fossem fluxos.
   Exercício irregular e lacuna recebem regra geral, registrada antes do alvo;
   não excluir linhas por erro de previsão.
3. **Congelar pré-registro do Rank 3-B.** Fixar calendário fiscal, D, universo
   não financeiro, política contábil, zero/arredondamento, vintage dos
   desfechos, censura, amostra mínima, componentes de T1 e tratamento da
   incerteza. Cadastro atual não deve virar classificação histórica sem
   ressalva. Elegibilidade só usa D; o futuro vem de uma tabela não filtrada
   por saúde futura. Contar eventos e clusters apenas depois disso.
4. **Baselines antes do modelo.** Taxa-base estimada só no treino; FCO/ativo
   corrente; frequência histórica de caixa negativo; repetição sazonal e
   previsão contábil linear. Fixar orientação dos escores e seleção do melhor
   baseline sem olhar o teste. T1/T2 do projeto continuam obrigatórios;
   não tratar sua reprovação como teorema sobre todos os usos de DFC.
5. **Só após os gates, um challenger simples.** Comparar de forma pareada com
   baselines, com treino temporal, rótulos já maturados na data do treino e
   purga dos horizontes sobrepostos. Transformações ajustadas só no treino.
   Reportar AUC/intra-companhia, calibração e precisão/recall em orçamento
   fixo de leitura; incerteza deve considerar emissores e dependência temporal.
   Fixar ganhos mínimos e regra de aprovação antes da comparação. Não iniciar
   busca ampla de modelos para resgatar um alvo reprovado.
6. **Validar uso humano, se houver ganho preditivo.** Medir relevância dos
   alertas, duplicação de episódios e tempo líquido de revisão. Manter RN05,
   RN07 e execução offline; não integrar escore por emissor ao produto público.

**Próxima tarefa executável:** passo 1, auditoria de recuperabilidade dos
vintages. Não há dependência de preço, OCR pago ou gold manual em massa para
começar essa investigação. A recuperação completa ainda não foi demonstrada.

## 6. Reprodução, testes e limites desta entrega

```bash
.venv/bin/python -m scripts.auditar_prontidao_dfc \
  --painel artefatos/cvm_treino.duckdb \
  --csv-dfc-amostra artefatos/cvm/itr_cia_aberta_DFC_MI_con_2024.csv \
  --saida /tmp/auditoria_prontidao_dfc.json

.venv/bin/python -m pytest -q \
  tests/test_auditar_prontidao_dfc.py tests/test_dados_estruturados.py
```

**177 testes focados passaram**, incluindo 12 novos: versão/data corretas,
recebimento ausente e no limite, código semanticamente ambíguo, conflito
MI/MD, duplicata, semestre mal classificado, proteção do período reservado,
base vazia, conexão somente leitura, versões no CSV e cabeçalho inválido.
Os testes são sintéticos: **não são evidência de desempenho de ML**.

**Suíte completa: 1.796 passaram, zero skips, 30 avisos.** A primeira tentativa
teve 41 falhas/1.755 sucessos porque o armazenamento padrão do CrewAI tentou
escrever SQLite fora da área gravável do sandbox. A reexecução abaixo passou
sem modificar código do produto ou asserções:

```bash
dfc_test_state=$(mktemp -d /tmp/dfc-test-state.XXXXXX)
CREWAI_STORAGE_DIR="$dfc_test_state" .venv/bin/python -m pytest -q --tb=short
```

O JSON identifica os hashes do auditor, painel e CSV. A consulta por código
e descrição é diagnóstico local e não substitui mapa validado nem validação
dos PDFs. Os arquivos brutos e painéis permaneceram inalterados. Não houve
commit, alteração de dependências, integração ao produto ou uso de métricas
inéditas do holdout. Fontes externas consultadas em 2026-09-08.
