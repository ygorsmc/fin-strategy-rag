# O que falta para desbloquear um experimento de ML com DFC

Data: 2026-09-15. Levantamento do estado do repositório, com verificações
somente leitura e simulação de derivação em memória. **Não é autorização de
treino, implementação das correções ou nova rodada de T1/T2.**

## 1. Resposta curta

**Ainda falta trabalho relevante de dados, não apenas terminar o CSV.** A
instrumentação avançou bastante; o painel efetivamente usado ainda reprova
integridade. Depois de corrigi-lo, falta saber se o alvo sobrevive aos testes
contra explicações triviais. Essa segunda parte pode terminar em rejeição,
mesmo com dados perfeitamente corrigidos.

O caminho mais delimitável hoje é o **Rank 3-B, não financeiro**: início de
consumo operacional persistente. A trilha **B-DFC-01J-M, bancária**, tem um
bloqueio adicional mais fundamental: nenhuma observação de juros de captação
elegível no artefato de prontidão vigente.

Não há base para prometer uma data ou um percentual de conclusão. A maior
incerteza é recuperar/adjudicar fontes e demonstrar disponibilidade histórica
dos valores utilizados, não programar um classificador.

Há três permissões diferentes:

1. **Medir o alvo:** dados íntegros, períodos e disponibilidade demonstrados.
2. **Treinar um desafiante experimental offline:** alvo sobrevive a T1/T2,
   baselines completos, protocolo de comparação congelado.
3. **Aprovar o modelo para uso:** ganho fora da amostra e utilidade para o
   analista demonstrados. Isso não decorre automaticamente de 1 ou 2.

Os limiares citados abaixo são **contratos metodológicos deste projeto**, não
uma impossibilidade universal de treinar ML. Alterá-los exige decisão
explícita e novo protocolo; não vale relaxá-los depois de conhecer o resultado.

## 2. Estado confirmado e tamanho real do problema

| Evidência | Estado | Consequência |
|---|---|---|
| CSV de classes | 300 exemplos: 284 monetários, 7 por ação, 9 inconclusivos; `classe_confirmada` vazia | Anotação IA contextual, não mapa operacional nem correção de escala |
| G0 do Rank 3-B, reexecutado sem escrita | 22.034 linhas de FCO e 22.471 de ativo; 25 durações inválidas; 132 saltos adjacentes, fração 0,005874, acima de 0,005 | Rodada continua interrompida antes de T1/T2 |
| Durações de FCO | 16 períodos curtos e 9 semestres; 15 grupos contêm linha válida e curta | Consertar a derivação semestral não resolve os curtos |
| Derivação intermediária em memória | 382.454 criados, 7.733 recusados, 139.435 grupos sem antecedente | Código corrigido não equivale a painel reconstruído |
| N3, ambiguidade de período | 141 grupos em 7 companhias no conjunto de fluxos; **10 grupos em 6 companhias no FCO não financeiro** | Há trabalho diretamente pertinente ao candidato, não apenas dívida de outras contas |
| N2, antecedente ausente | **131 grupos em 94 companhias no FCO não financeiro** | Inventariar recuperação e efeito na cobertura; não significa 131 valores errados |
| Disponibilidade histórica | Painel conserva versões selecionadas; derivados não preservam toda a linhagem dos operandos | O G1 atual não certifica sozinho um painel integralmente point-in-time |
| Prontidão bancária | 198 registros na série, **0 observações de J e 0 alvos elegíveis** | Mais distante de um experimento que a trilha não financeira |

Os números de N2/N3 específicos de FCO são deste levantamento. São contagens
de **grupos de candidatos à derivação**, não de exemplos finais de treino nem
de erros adjudicados. O filtro é o estrutural já adotado: excluir
`is_banco` e planos `ll3_09_%`; conta `6.01` em DFC.

Fontes: [anotação do CSV](anotacao_classes_monetarias_2026-09-15.md),
[conferência QW](conferencia_independente_qw1_qw8_2026-09-15.md),
[implementação QW, §4](implementacao_qw1_qw8_2026-09-15.md),
[auditoria congelada](../artefatos/rank03b/auditoria.json),
[prontidão bancária](../artefatos/b_dfc_01j/prontidao/gates.json).

## 3. Rank 3-B: trabalho necessário, em ordem de dependência

### D1 — Fechar as lacunas do instrumento, sem reconstruir nada

- **CQW-01:** validar o vocabulário fechado de `adjudicacao` no consumidor do
  inventário; estado desconhecido/nulo não pode virar silenciosamente conjunto
  vazio. Exigir contraprovas para os nove estados válidos e os inválidos.
- **CQW-02:** completar a linhagem temporal do ativo, com data de posição e
  disponibilidade; `dt_ini` pode ser inaplicável a saldo de BPA. Cumprir H1.4
  ou revisar expressamente o contrato, sem inventar início de fluxo para saldo.
- **CQW-03:** publicar a errata de 154.160 para **156.100 declarações**. É
  pendência documental, não causa numérica da reprovação do candidato.
- **Lacuna adicional observada neste levantamento:** `gate_g0([], [], [])`
  devolve `aprovado=True`; os carregadores também filtram nulos antes do gate,
  que não publica uma verificação própria de G0.4. Fechar com testes de entrada
  vazia e nulo na fonte requerida. **Não demonstrou aprovação indevida da
  cadeia completa:** G1 barra amostra vazia e foram encontrados zero nulos nas
  contas requeridas do universo atual. Não atribuir a isso a reprovação real.

Conclusão verificável: contratos, consumidor e decisão coerentes; testes
adversariais falham antes e passam depois; conferência independente da onda.
CQW-01 é necessário antes de confiar nesse consumidor na curadoria, não um
teste estatístico adicional do alvo.

Fontes: [parecer, §§2 e 5](conferencia_independente_qw1_qw8_2026-09-15.md),
[`carregar_fco`, `carregar_ativo`, `gate_g0`](../scripts/auditar_rank03b_consumo_operacional.py).

### D2 — Validar as identidades contábeis efetivamente necessárias

O candidato usa **FCO (`6.01`, DFC_MD/DFC_MI) e ativo total (`1`, BPA)**.
Validar significado, unidade, plano, descrição, emissor, período e declaração
para essas contas e seus históricos. Resolver a equivalência entre descrições
quando houver evidência; não fazer junção universal só pelo código.

As 300 anotações podem ajudar, mas classificar um exemplo como monetário não
prova a unidade de todas as suas ocorrências. Também não torna duas rubricas
economicamente equivalentes. Não promover a coluna IA automaticamente a
`classe_confirmada`, nem a apresentar como validação humana.

Conclusão verificável: mapa restrito e versionado, evidência por regra e
exceção, validação na origem e teste que recusa aplicação fora de escopo.
**Não é necessário curar todas as contas do repositório antes desse mapa.**

### D3 — Adjudicar escala nos dados que realmente chegam ao experimento

Os 132 saltos são **transições suspeitas**, não 132 células a multiplicar ou
dividir por mil. Confrontar os valores com documentos do mesmo período,
distinguindo erro de declaração, mudança real de escala e evento econômico.
Aplicar somente correções sustentadas por fonte, com valor anterior, valor
corrigido, documento/página/hash, justificativa e guarda contra republicação.

O inventário v2 identificou 3.401 casos adjudicáveis, 6.456 declarações,
111 documentos e 35 companhias. São declarações `PENÚLTIMO` de balanço:
**corrigi-las diretamente altera zero linhas retidas do painel**. O documento
suspeito ajuda a investigar, mas não autoriza corrigir todas as suas contas,
nem o `ÚLTIMO` de outro período. Esse é o trabalho que a anotação do CSV
sozinha não encerra.

Conclusão verificável: fonte para cada correção aplicada, incertezas
explicitadas, diffs reproduzíveis e G0.3 atendido no universo contratual.
Não excluir as observações que acusaram o defeito só para passar o limiar.

Fontes: [conferência QW, §3.1](conferencia_independente_qw1_qw8_2026-09-15.md),
AGENTS.md §3.3 e §4.4, regras de procedência e quarentena.

### D4 — Corrigir períodos e identidade da derivação

1. Aplicar a correção já implementada que recusa diferença acumulada de mais
   de um trimestre. Ela ainda não foi aplicada ao painel em disco.
2. Adjudicar os **16 períodos curtos** e os **15 grupos mistos**, identificando
   qual declaração cobre o trimestre pretendido. Não eleger a linha pelo maior
   valor nem apagar a anômala sem inventário e justificativa.
3. Resolver **N3** por identidade econômica do período e exercício social.
   Ordenar arbitrariamente o `row_number()` apenas torna repetível uma escolha
   que pode continuar errada. No FCO não financeiro, os 10 grupos são:

   | Companhia CVM | Demonstrativo | Rótulos envolvidos |
   |---|---|---|
   | 019836 | DFC_MI | 2T2014, 3T2014 |
   | 022586 | DFC_MI | 3T2012 |
   | 023507 | DFC_MI | 2T2015, 3T2015 |
   | 023795 | DFC_MD | 2T2016, 3T2016 |
   | 026352 | DFC_MD | 3T2022 |
   | 080071 | DFC_MI | 2T2014, 3T2014 |

4. Classificar os **131 grupos N2** do recorte: ausência real de documento,
   alteração de descrição, alteração de conceito ou outra causa. Recuperar o
   que for demonstravelmente equivalente. Onde não houver antecedente,
   registrar indisponibilidade e efeito sobre elegibilidade/censura segundo
   regra prévia; não fabricar zero nem parear apenas pelo código.

Conclusão verificável: isolamento trimestral de 80–100 dias, ausência de
duplicação entre métodos, escolha de período explicável, derivação determinística
sob reordenação da entrada, e inventário de perdas. **Recuperar todos os N2 não
é obrigação absoluta**: é necessário conhecer as perdas e manter suporte
suficiente. O mesmo não permite excluir pós-hoc os erros que reprovaram G0.

Fontes: [implementação QW, §§4.2–4.3](implementacao_qw1_qw8_2026-09-15.md),
[`_derivar_trimestres_intermediarios`](../src/dados_estruturados.py).

### D5 — Demonstrar point-in-time dos valores, inclusive dos operandos

Uma data de recebimento ao lado da linha derivada não basta. Para cada
subtração — inclusive anual menos nove meses — preservar os dois valores,
versões, documentos, períodos, unidades e datas de disponibilidade. Selecionar
as versões disponíveis em D **antes** da subtração; a disponibilidade do
resultado não pode anteceder nenhum operando.

Fazer primeiro um piloto de recuperação das versões numéricas necessárias.
O catálogo de documentos contém versões que os arquivos numéricos locais não
necessariamente conservam. Retirar um filtro de versão máxima do carregador
não recria um arquivo original ausente.

**Não é preciso recuperar toda versão de toda companhia por princípio.** É
preciso provar a disponibilidade de cada entrada efetivamente utilizada em
cada decisão e quantificar o que se perde. Usar uma versão retificada só é
admissível a partir de sua disponibilidade real, sob política explícita;
nunca tratá-la como conhecida retroativamente. Fixar também qual safra define
o rótulo futuro — esse rótulo não precisa estar publicado em D, ao contrário
das features e dos critérios de elegibilidade.

Conclusão verificável: linhagem completa, reconstrução as-of reproduzível,
testes de revisão tardia, datas fiscais corretas e G1 aprovado. Os 10.605
exemplos do diagnóstico anterior, sem violações nas verificações existentes,
**não substituem essa prova** nem são uma amostra já aprovada para treino.

Fonte: [viabilidade DFC, §§2 e 5](viabilidade_ml_dfc_2026-09-08.md),
[`construir_amostra` e `gate_g1`](../scripts/auditar_rank03b_consumo_operacional.py).

### D6 — Materializar e conferir um painel de pesquisa corrigido

**Proposta, ainda não implementada nem autorizada:** construir um painel
separado, versionado, restrito às contas necessárias. Preservar os dois bancos
atuais e seus hashes. Essa alternativa já aparece no relatório de viabilidade
e reduz a dependência de curar contas alheias ao candidato.

Se a escolha for reconstruir o **painel compartilhado inteiro**, resolver N3
globalmente, declarar a quebra de hash, comparar linhas/valores/cobertura,
reexecutar os testes pertinentes e medir impacto sobre a etapa 10. Isso exige
decisão própria; não é efeito lateral desta lista ou da anotação monetária.

Em qualquer opção: hashes dos insumos e resultados, manifesto de correções,
perdas justificadas, duas execuções reproduzíveis e revisão independente.
Não regravar os resultados antigos como se tivessem usado o painel novo.

### D7 — Novo pré-registro e testes de viabilidade do alvo

O pré-registro de 11/09 foi consumido pela rodada invalidada. Antes de medir
resultados novos, registrar população, versões, correções, censura, política
para zeros/arredondamento, janela histórica e horizonte, declarando o que já
foi visto. Não mudar o evento para salvar uma reprovação: isso seria outro
estimando, com protocolo próprio.

Sequência e critérios vigentes a preservar ou revisar **explicitamente antes
da nova medição**:

| Etapa | Condição de conclusão |
|---|---|
| G0 | Sem uso duplo de métodos, sem duração trimestral inválida, sem nulos nas contas usadas e saltos de escala dentro do limite contratual |
| G1 | Features disponíveis em D, q1 exatamente o primeiro trimestre fiscal iniciado depois de D, quatro períodos do rótulo posteriores a D |
| T1 | Seis componentes previstos; mínimo de 500 observações e 30 companhias no suporte pertinente; amplitude < 0,15 e regra da zona cinzenta cumprida |
| Zona cinzenta de T1 | Em [0,12; 0,15), 2.000 reamostragens por companhia; probabilidade acima de 10% de exceder 0,15 torna indecidível |
| T2 | AUC agregada menos AUC intra-companhia < 0,12; escore não constante e cobertura intra-companhia publicada |
| Baselines | B0 majoritário, B1 FCO/volatilidade, B2 frequência de FCO negativo, B3 FCO/ativo; métricas e IC completos conforme seus papéis, sem tratar B0 constante como ranqueador informativo |

O resultado necessário é **PRONTO PARA CHALLENGER**, não “modelo aprovado”.
Reprovação numérica rejeita o alvo; falta de suporte ou métrica deixa-o
indecidível. **Nada disso foi medido sobre um painel corrigido.** O próprio
pré-registro antecipa possível reprovação em T1; isso é uma previsão, não um
resultado disponível.

Há uma ambiguidade documental a resolver: §8 menciona superar o melhor
baseline como condição para treinar, mas §9 distingue permissão de medir um
desafiante de aprovação do modelo. O novo protocolo deve separar os dois
momentos: não exigir resultado de um modelo ainda proibido de ser treinado,
nem interpretar autorização de experimento como evidência de superioridade.

Fonte: [pré-registro Rank 3-B, §§4–10](pre_registro_rank03b_consumo_operacional_2026-09-11.md),
[`executar`](../scripts/auditar_rank03b_consumo_operacional.py).

### D8 — Protocolo do primeiro treino e autorização do experimento

Se D7 passar, congelar o primeiro desafiante simples e seu orçamento de busca,
features, métrica primária e comparação pareada com o melhor baseline. Definir
walk-forward temporal, disponibilidade dos rótulos no momento de cada ajuste,
tratamento da sobreposição do horizonte futuro, transformação ajustada apenas
no treino e seleção de parâmetros/baseline sem usar o teste final.

Critério de conclusão: protocolo auditável e decisão explícita de iniciar o
experimento offline. O desempenho do desafiante será **resultado posterior**,
não dívida a ser resolvida antes de existir treino. Os detalhes estatísticos
desse protocolo ainda precisam ser especificados; esta lista não os congela.

Depois do treino, exigir ganho fora da amostra com incerteza, estabilidade e
avaliação de utilidade/custo de leitura para o analista antes de propor uso.
O evento contábil não é automaticamente fraude, insolvência, materialidade
econômica ou recomendação de investimento.

## 4. Trilha bancária: pendências adicionais e separadas

Não aplicar automaticamente o alvo de FCO de empresas não financeiras a bancos.
Para B-DFC-01J-M, a fila conhecida é:

1. **Conferir independentemente a terceira onda** R-C5/R-C6/R-SUPORTE. A
   revisão QW/Rank 3-B não a certificou. Não repetir C1–C4 já conferidos.
2. **Identificar economicamente J em fontes:** separar juros de captação das
   rubricas agregadas, documentar inclusões/exclusões, limites e conciliação
   independente. Fechamento aritmético não prova conformidade contratual.
   Adjudicar rubricas pendentes do BB; não contar largura zero de
   `nao_identificado` como ausência de erro. Hoje a população elegível é zero.
3. **Resolver o schema e unidades:** valores desconhecidos/intervalos
   explicitados; remover a presunção de `milhares_de_reais` onde o documento
   está em outra escala. Conferir produtor e consumidores.
4. **Construir população trimestral point-in-time**, com fontes, vintages,
   derivação anual/9M coerente e horizonte realmente futuro. Medir cobertura
   depois dessa reconstrução, não contar os 198 registros como rótulos.
5. **Implementar B3 econômico:** benchmark com taxa conhecida na decisão, não
   Selic futura realizada. A constante `B3_EXECUTADO` segue `False`.
6. **Redesenhar e validar F3, cálculo de poder:** está invalidado e
   `PODER_REDESENHADO_APOS_F3=False` veta G3. Fixar estimando, dependência entre
   medidas e melhoria detectável frente aos baselines. Não herdar a conclusão
   retratada de “aproximadamente 16 emissores”, nem ligar a flag para liberar.
7. **Novo pré-registro e gates G0/G1/G2/G3/T1/T2**, incluindo erro do rótulo
   frente ao sinal, poder e baselines completos. Os limiares originais incluem
   G2 < 0,10 e G3 com poder de 80%, alfa 5% e melhoria detectável ≤ 20% do
   MAE do melhor baseline; o cálculo de G3 precisa primeiro deixar de ser
   inválido. O artefato atual para em G0; os demais resultados são diagnósticos
   sem população, não refutações empíricas do sinal.
8. Só então **protocolo/autorização de desafiante**, seguido de avaliação fora
   da amostra, como na distinção entre treinar e aprovar da seção 1.

O piloto de **subordinadas classificadas como passivo IFRS**, nas notas já
localizadas, é uma pista documental com escopo menor; inclui adjudicação
pendente de 2025T1. Se escolhido como alvo, requer **novo estimando**: não é
equivalente ao custo total de captação e não herda a validação de J total.

Cobertura mínima adicional de evidência independente em G0 bancário **não
foi fixada pelo contrato atual**. Não inventar aqui um novo percentual e
apresentá-lo como pendência antiga.

Fontes: [implementação R-C5/R-C6, §8](implementacao_rc5_rc6_b_dfc_01j_2026-09-11.md),
[pré-registro bancário](pre_registro_b_dfc_01j_modelo_2026-09-09.md),
[`auditar_prontidao_b_dfc_01j.py`](../scripts/auditar_prontidao_b_dfc_01j.py),
[gates vigentes](../artefatos/b_dfc_01j/prontidao/gates.json), MEMORY.md.

## 5. O que não precisa virar pré-requisito artificial

- Anotar/confirmar **todas** as 300 contas ou resolver os nove exemplos `0`/`-`
  independentemente de relevância. Para Rank 3-B, começar por FCO/ativo e os
  dados que seus históricos exigem; expandir somente se houver dependência.
- Corrigir **todos** os 139.435 grupos N2 ou as 698 chaves semânticas duplicadas
  do projeto. Corrigir/avaliar os que afetam o experimento; a reconstrução
  compartilhada tem escopo maior e obrigações próprias.
- Comprar preços ou construir universo investível, nem mapear CAPEX para um
  alvo que usa **FCO**, não FCF ou retorno de ações.
- Criar gabarito humano por observação para este alvo numérico. O rótulo vem
  de dados contábeis e fórmula; fonte e integridade precisam de adjudicação.
  Julgamentos humanos de relevância ajudam a provar **utilidade** depois, e
  anotação por agente não deve ser apresentada como validação humana.
- Completar interface, RAG, OCR de todo o corpus, segurança e observabilidade
  do produto para executar um experimento estritamente offline.
- Abrir `corpus/holdout_2T2026`, mudar RN07 ou publicar escores por emissor.
  Nada neste levantamento autoriza essas ações.

## 6. Encaminhamento e divisão do trabalho

**Lote A — engenharia delimitada:** D1 e contrato de D4/N3; testes em fixtures
e simulação em memória. Pode ser feito por agente, com revisão independente,
sem rede paga ou alteração dos painéis.

**Lote B — viabilidade dos dados necessários:** inventário conjunto D2–D5
somente para FCO/ativo, com piloto de fontes/vintages. Agente pode levantar,
confrontar e propor adjudicações com evidência; incerteza residual não deve
virar rótulo confirmado. Este lote determina se há uma rota de dados
defensável e permite estimar melhor o trabalho restante.

**Decisão do responsável:** painel de pesquisa separado ou reconstrução do
compartilhado; aprovação do escopo de correções e do novo protocolo. Uso de
API paga, mudança de estimando ou ampliação material de escopo são decisões
separadas, nunca inferidas desta lista.

**Lote C — painel e gates:** D6–D7, sob protocolo novo e com fonte congelada.
Parar se reprovar; não procurar um modelo mais complexo para contornar a
reprovação de dados ou de alvo.

**Lote D — primeiro desafiante:** D8, somente se autorizado pelo resultado do
lote C. É aqui que começa o treino, não ao terminar a anotação monetária.

Esta é uma recomendação de sequência. **Nenhum desses lotes foi implementado
por este levantamento.**

## 7. Rastreabilidade e limites desta verificação

Foram lidos MEMORY.md, contratos/pré-registros, pareceres citados, código dos
carregadores/gates/derivação e artefatos vigentes. G0 foi recalculado em conexão
somente leitura. A derivação intermediária foi simulada com cópias de tabelas
em DuckDB `:memory:`, mantendo a relação temporária de candidatos apenas para
contar N2/N3. Não se mediram T1, T2, baselines ou desempenho de ML. Não houve
reconstrução, nova varredura integral de ZIPs, pesquisa web ou chamada paga.
Não houve nova execução da suíte completa nem auditor externo desta lista.

### 7.1 Impressões digitais da base consultada

| Arquivo | SHA-256 |
|---|---|
| `artefatos/cvm.duckdb` | `43e31d9f150e535f1ab20576d9aacf1a53b83ecc5424ca7d48ba50781e4cef18` |
| `artefatos/cvm_treino.duckdb` | `c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b` |
| `corpus/cvm/plano_padrao_contas.csv` | `fa271cd3174000da2877828d7e75b556ac8506e5a5d3cfcd01bb85ff3cb3bb03` |
| `scripts/auditar_rank03b_consumo_operacional.py` | `02af50bdb9b6745db99c0ad4fd46347d852ef778d0e551712d0d875519a68678` |
| `src/dados_estruturados.py` | `b7587f2a3267f9f1828e134970ae1c064a85a3ec082655ce158ce32816de46cf` |
| `artefatos/rank03b/auditoria.json` | `a2ef88bea647777797d909624662bfe2761ab6ceaaaf4f5eae7f4b2e3d327ee0` |

### 7.2 Como reproduzir o recorte de N2/N3 sem reconstruir o painel

Executar da raiz, no ambiente do projeto. A conexão persistente é anexada
`READ_ONLY`; toda inserção ocorre no banco em memória. A supressão do `DROP`
é instrumentação local da inspeção, não alteração da função em produção.

```python
import duckdb
from src.dados_estruturados import _derivar_trimestres_intermediarios

con = duckdb.connect(":memory:")
con.execute("ATTACH 'artefatos/cvm_treino.duckdb' AS p (READ_ONLY)")
for tabela in ("companhias", "mapa_contas"):
    con.execute(f"CREATE TABLE {tabela} AS SELECT * FROM p.{tabela}")
con.execute("""
    CREATE TABLE fatos_contabeis AS SELECT * FROM p.fatos_contabeis
    WHERE origem = 'arquivado'
      AND demonstrativo IN ('DRE', 'DFC_MD', 'DFC_MI')
""")

class ReterCandidatos:
    def execute(self, sql, *args):
        if sql.strip() == "DROP TABLE _candidatos_intermediarios":
            return con
        return con.execute(sql, *args)

print(_derivar_trimestres_intermediarios(ReterCandidatos()))
con.execute("""
    CREATE TEMP TABLE grupos AS
    SELECT cd_cvm, demonstrativo, trimestre, chave_pareamento,
           bool_or(tem_antecedente) AS tem_antecedente
    FROM _candidatos_intermediarios GROUP BY ALL
""")
con.execute("""
    CREATE TEMP TABLE multiplos AS
    SELECT cd_cvm, demonstrativo, trimestre, chave_pareamento,
           count(DISTINCT (fim_anterior, dt_fim_exerc)) AS periodos
    FROM _candidatos_intermediarios WHERE na_banda
    GROUP BY ALL HAVING periodos > 1
""")
filtro = """
    JOIN companhias c USING (cd_cvm)
    WHERE NOT c.is_banco AND c.plano_contas NOT LIKE 'll3_09_%'
      AND g.demonstrativo IN ('DFC_MD', 'DFC_MI')
      AND g.chave_pareamento LIKE 'conta:6.01|%'
"""
print("N2", con.execute(
    "SELECT count(*), count(DISTINCT cd_cvm) FROM grupos g "
    + filtro + " AND NOT g.tem_antecedente"
).fetchone())  # (131, 94)
print("N3", con.execute(
    "SELECT count(*), count(DISTINCT cd_cvm) FROM multiplos g " + filtro
).fetchone())  # (10, 6)
print(con.execute(
    "SELECT g.cd_cvm, g.demonstrativo, g.trimestre FROM multiplos g "
    + filtro + " ORDER BY 1, 2, 3"
).fetchall())
con.close()
```

O fallback `conta:6.01|...` corresponde às chaves de FCO presentes nessa
versão. Se o mapa semântico mudar, atualizar explicitamente o recorte; não
interpretar o desaparecimento dessas chaves como resolução automática de N2/N3.
