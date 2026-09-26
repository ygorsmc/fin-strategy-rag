# Conferência independente — pré-treino do Rank 3-B

**Conclusão em 2026-09-17: aprovação parcial da infraestrutura; não congelar
o v2 nem medir o alvo ainda.** Há erro de escala comprovado contra o próprio
documento, uso antecipado da evidência de correções herdadas e defeito no
agrupamento de T1. Não são razões para rejeitar a ideia de ML; são razões para
corrigir o instrumento e a base antes de julgá-la.

Revisão solicitada dos seguintes materiais, incluindo seus produtores e
consumidores:

- [Pré-registro v2, rascunho](pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md).
- [Painel de pesquisa, lote C](painel_pesquisa_rank03b_lote_c_2026-09-16.md).
- [Verificações finais publicadas](../artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json).

**Artefatos desta conferência:**
[contagens e hashes](../artefatos/revisao_pre_treino_rank03b_2026-09-17/conferencia.json)
e [reprodução somente leitura/memória](../artefatos/revisao_pre_treino_rank03b_2026-09-17/reproduzir_estrutura.py).
Não houve correção de implementação ou dos dados, treino do candidato, cálculo
do alvo real, T1/T2/baselines reais ou acesso ao holdout.

## 1. O que foi efetivamente confirmado

| Conferência | Resultado |
|---|---|
| Testes dos nove arquivos em escopo | **375 passed**, 35,97 s |
| Suíte completa | **2.495 passed**, 30 warnings, zero skip, 157,11 s |
| Reconstrução independente a partir dos ZIPs, só em memória | **31 hashes conferidos**; digest `f9cb9da9d58673ff36e8d00abee45870fcd56d7966858762e4a006a528d8f279` reproduzido |
| Comparação bidirecional das tabelas reconstruídas com o DuckDB persistido | **Zero linhas diferentes** em ativo, FCO acumulado e FCO trimestral |
| Gates executados pelo código vigente | Cadeia publicada reproduzida: 47 saltos; G1 com 10.750 observações/502 companhias; contadores implementados sem violações |
| CQW-01/CQW-02/G0.4 | Vocabulário validado no consumidor, campos de linhagem do ativo presentes, guarda de nulos/vazio implementada e contraprovas passando |
| Preservação dos dois painéis compartilhados | Hashes permanecem os de referência |

**Reproduzir uma aprovação não demonstra que o gate mede todos os riscos que
promete cobrir.** O G1 vigente verifica a recepção dos valores, mas não a
publicação das provas de correção. O G0 admite tolerância a saltos, mas isso
não legitima uma correção sabidamente errada.

## 2. Achados, por prioridade

### RF-01 — P1: ESC-0101 corrige um valor certo e cria erro de 1.000×

**Fonte do defeito:** `scripts/fonte_rad_cvm.py:680–701`, especialmente a linha
689; decisão em `scripts/adjudicar_escala_rank03b.py:79–102`.

`evidencia_numerica` reduz as contas a um conjunto de magnitudes e procura
essas magnitudes em todo o texto das notas. Perde conta, período, sinal,
coluna, perímetro e contexto. Encontrar o mesmo número em capital social ou
quantidade de ações pode ser contado como prova da unidade do ativo/caixa.
O manifesto conserva a página do **cabeçalho**, não a localização que permite
auditar cada correspondência numérica.

**Contraprova real, conferida pelo revisor principal:**

| Fonte, mesma companhia/período | Ativo total |
|---|---:|
| CVM `027570`, documento `152742`, 30/09/2025; formulário consolidado, PDF página física **11**, unidade **reais** | **5.073.000** |
| Balanço no comentário de desempenho, mesmo PDF, página física **30**, unidade **milhares de reais** | **5.073** |
| Painel de pesquisa após `ESC-0101`, `UNIDADE → MIL` | **5.073.000.000 reais** |

As duas primeiras representações são equivalentes. A terceira erra por mil.
O cabeçalho da página 30 identifica o balanço intermediário individual e
consolidado; trata-se da peça de comentário de desempenho, não de uma página
de notas explicativas. A página 11 é explicitamente consolidada. Não confundir
com o ativo individual do formulário, em outra página.

Pacote local:
`artefatos/painel_pesquisa_rank03b/rad/brutos/152742.zip`;
SHA-256 `ff2b0b4d534d245962b1aab75ffa4c9c3eece14caaa530799fca1617806958ac`.
Membro PDF: `152742_027570_16092026084005.pdf`.
O manifesto registra apenas **um** número bruto como evidência para essa
correção. A investigação do especialista localizou o casamento em rubrica de
capital/ações; a conclusão de erro acima independe dessa interpretação, pois
foi reconferida diretamente nos dois balanços e no painel.

Também reproduzido em fixture: um formulário com conta `1 = 1.234.567` e
texto contendo somente “Capital social dividido em 1.234.567 ações” produz
`numerica_classe='bruto'`. O teste demonstra a causa, não só um caso isolado.

**Impacto:** o trecho do lote C que descreve os quatro saltos novos apenas como
“custo de corrigir só o que tem fonte” é insuficiente: pelo menos um contém
erro produzido pela correção. Manter a linha “para evitar ajuste pós-hoc”
também não é defensável. Corrigir erro demonstrado contra fonte, declarando
a nova versão, não é otimizar o alvo por desempenho.

**Fechamento necessário:**

1. Retratar a decisão `ESC-0101` com evidência; preservar a execução anterior.
2. Exigir correspondência econômica do número com conta/período/perímetro e
   unidade da tabela. Registrar também página/trecho da evidência numérica.
3. Reexaminar as decisões produzidas pela mesma heurística, inclusive as
   pontas usadas em herança; não remendar só uma linha e certificar as outras
   por terem passado no mesmo código.
4. Contraprovas: número coincidente em ações, outra conta, comparativo e
   coluna individual não decide a escala consolidada; documento legítimo em
   unidades com notas em milhares continua em unidades.
5. Só depois materializar nova versão do painel de pesquisa e medir G0/G1.

Não contei as demais correções como erradas; falta revalidar o método que as
sustenta. Não corrigi nem removi linha nesta revisão.

### RF-02 — P1: a data da evidência herdada não governa a disponibilidade

**Locais:** `scripts/painel_pesquisa_rank03b.py:163–181`, `:338`;
`scripts/gates_painel_pesquisa_rank03b.py:90–108`;
`scripts/auditar_rank03b_consumo_operacional.py:847–867`.

A escala herdada é aplicada, mas `dt_receb` continua sendo a data do documento
corrigido. A disponibilidade do trimestre é o máximo entre os documentos dos
operandos, **sem incluir as pontas que provam a correção**.

Conferência real: **24/24 correções herdadas, em oito companhias**, dão ao
ativo corrigido uma disponibilidade entre **12 e 734 dias anterior** à prova
mais tardia usada na herança.

| Exemplo | Disponibilidade atribuída | Publicação da ponta necessária |
|---|---|---|
| ESC-0004, documento 107954, CVM 003549 | 16/08/2021 | Documento 109902: **12/11/2021** |
| ESC-0041, documento 10677, CVM 022144 | 10/08/2011 | Documento 30517: **13/08/2013** |

Não é só presença inócua no painel. Construindo a amostra com
`calcular_rotulo=False`, **cinco observações de três companhias** usam essa
evidência antes de sua publicação, tanto no ativo quanto na janela de FCO:
`003549/2023-08-15`, `003549/2024-08-15`, `007811/2020-10-15`,
`022144/2013-03-27`, `022144/2013-05-14`.

Essa contagem verifica **identidade e data**, não valores das features nem
resultado do alvo. O G1 atual aprova as cinco porque só recebe a data já
reduzida pelo construtor.

**Distinção importante:** uma correção retrospectiva pode estar numericamente
certa. Isso não prova que era demonstrável na decisão histórica. Se a escala
correta já constava do documento original, é possível obter essa evidência e
dispensar a ponta futura. O encadeamento de provas atual não demonstra isso.

**Fechamento:** registrar a disponibilidade de cada prova e sua dependência;
ou adjudicar o documento com evidência existente em D, ou postergar a
disponibilidade corrigida até todas as provas necessárias existirem. Propagar
isso às derivações, à seleção as-of e ao G1 independente. Não mudar o critério
silenciosamente para “dados retrospectivamente corrigidos”. Testes devem
manter intactas as datas dos valores e deslocar apenas a publicação da ponta:
o caso antes dela deve ser recusado, o caso depois pode ser aceito.

### RF-03 — P1: o agrupamento de T1 fabrica quintis unitários após um empate grande

**Local:** `scripts/auditar_rank03b_consumo_operacional.py:919–933`.

Contraprova **executada apenas em dados sintéticos**:

```python
x = [0] * 400 + list(range(1, 101))
y = [i % 2 for i in range(500)]
amplitude_por_quintis(x, y)
# n por faixa: [400, 1, 1, 1, 97]
# amplitude: 1.0
```

O primeiro empate consome quatro cortes nominais. A linha
`fim = max(corte, inicio + 1)` tenta criar os cortes já ultrapassados mesmo
assim, isolando três observações. Os grupos grandes têm taxas próximas de
0,5; os unitários produzem 0 e 1 e determinam uma reprovação espúria. Uma
política de estender cada corte ao fim do empate e eliminar cortes repetidos
produziria aqui dois grupos, de 400 e 100, ambos com taxa 0,5.

O teste existente em `tests/test_rank03b_consumo_operacional.py:115` usa
distribuição semelhante, mas só exige que valores iguais não sejam divididos.
Não verifica a criação dos grupos artificiais. O componente de frequência de
FCO negativo é discreto, tornando a classe de defeito pertinente ao candidato;
**seu efeito no dado real não foi medido**.

**Fechamento:** fixar a política de cortes/empates no protocolo, implementar
cortes não redundantes e travar tamanhos das faixas, constante, permutação da
entrada e exemplos com empates atravessando um ou vários cortes. Preservar o
limiar de T1; corrigir a partição não é uma licença para relaxá-lo.

Não existe resultado real de T1 do Rank 3-B a retratar: a medição não começou.

### RF-04 — P2: G0.5 deixa fora uma classe produzida pela própria correção parcial

**Local:** `scripts/gates_painel_pesquisa_rank03b.py:177–181`;
pré-registro v2 §5.5.

O diagnóstico reproduz os **38/22.088 = 0,172%** publicados, mas seu filtro
inicial exige escalas **declaradas** diferentes. Há três trimestres válidos
com `UNIDADE+UNIDADE` na fonte, escalas **aplicadas diferentes** e algum
operando sem veredito, que ficam fora:

| Companhia / trimestre | Escalas aplicadas |
|---|---|
| 003549 / 3T2025 | UNIDADE + MIL |
| 025461 / 2T2025 | MIL + UNIDADE |
| 027570 / 3T2025 | UNIDADE + MIL |

O último contém a correção errada de RF-01. Escalas distintas, sozinhas, não
provam erro — duas fontes podem declarar legitimamente unidades diferentes.
O problema é declarar que a guarda cobre incompatibilidade de unidade sem
examinar essa classe nem validar as adjudicações das quais depende.

**Fechamento:** definir a população de risco em termos da proveniência das
conversões efetivamente aplicadas, incluindo correção parcial, e testar cada
configuração. Recontar após RF-01/RF-02. O 0,5% em G0.5 é **política nova para
outro evento e denominador**, embora reutilize o número de G0.3. Exige
justificativa e decisão, não herda validação automaticamente. Erro já
demonstrado deve ser corrigido, não tolerado porque cabe em 0,5%.

### RF-05 — P2: o protocolo ainda não especifica toda a operação que pretende congelar

Além das três decisões já marcadas no v2, explicitar:

- **Grade D:** o código (`auditar...:712`) usa disponibilidades de FCO
  **válido**, não todas as recepções do cadastro nem as atualizações só de
  ativo. Registrar a política escolhida e seus efeitos de seleção.
- **Janela:** oito trimestres históricos contíguos; `sd8=0` produz ausência
  apenas nos componentes/baseline que dividem por ele. Fixar tratamento,
  suporte de comparação e cobertura, sem esconder os ausentes.
- **T2:** qual escore e sentido governam. O executor antigo usa B1 negativo;
  a AUC intra é média simples das AUCs de companhias com ambos os rótulos.
  Fixar também a política de suporte intra: hoje uma única companhia basta.
  Não imponho aqui um novo piso arbitrário.
- **G0.3:** o denominador implementado é o número de linhas de ativo, não o
  número de pares adjacentes. Escrever a fórmula evita mudança acidental.
- **T1:** regra de empate corrigida em RF-03; documentar a natureza da
  frequência bootstrap, sem tratá-la automaticamente como probabilidade
  posterior sobre um parâmetro verdadeiro.
- **B0:** a implementação é “sempre não consumir”, não uma classe majoritária
  estimada fora da amostra. Nomear a regra exata e implementar os IC exigidos.
- **Executor v2:** não reutilizar o `executar()` antigo inteiro: ele monta
  `y` antes de G1. A nova orquestração deve verificar G0/G1 cegos e somente
  depois montar o alvo. B0 sem IC e G0.5/G0.1 ainda não implementados conforme
  a decisão são requisitos já reconhecidos pelo próprio §14 do rascunho.

**Fechamento:** protocolo completo e testes das decisões antes da medição.
Não é preciso definir agora todos os hiperparâmetros do futuro modelo: D8
continua separado e só nasce se houver `PRONTO PARA CHALLENGER`.

### RF-06 — P2: a verificação final está ligada a outro manifesto de painel

**Locais:** `verificacoes_revisao_final.json:100`;
`scripts/verificacoes_revisao_final_rank03b.py:171`.

O campo `painel_sha256_do_manifesto` registra `c404c422…`; o produtor o calcula
sobre `manifesto_painel.json`. O arquivo vigente tem hash **`4b5e9492…`**,
coerente com o relatório do lote C, mas diferente do JSON de verificação.

Os quatro hashes de código desse JSON conferem. A reconstrução desta revisão
também confere com os valores persistidos. Portanto, o achado é **ligação
desatualizada da evidência**, não prova de alteração clandestina dos valores.

**Fechamento:** identificar/documentar o manifesto anterior ou reexecutar as
verificações sobre a versão governante, publicando hashes consistentes entre
fontes, correções, painel, gates e verificação. Não substituir o hash no JSON
sem a correspondente conferência. Isso deve ser feito depois das correções
materiais, para não congelar uma versão já vencida.

### RF-07 — P3: 6.735 são incidências trimestre–decisão, não decisões distintas

**Local:** `scripts/painel_pesquisa_rank03b.py:367–381`.

O laço soma cada D em cada intervalo cego de trimestre. Reproduzido:
**6.735 pares (trimestre, D)**, mas **4.181 chaves distintas (companhia, D)**.
Uma decisão pode cair em mais de um intervalo. O texto do lote C/v2 precisa
nomear a unidade corretamente; não se deve interpretar 6.735 como decisões
únicas perdidas, nem 4.181 como exemplos finais que necessariamente faltam.

**Fechamento:** publicar as duas contagens com nomes distintos. Não afeta os
valores dos gates ou a aritmética do painel.

### RF-08 — P3: T2 ainda publica AUC zero como ausente

**Local:** `scripts/auditar_rank03b_consumo_operacional.py:1129`.

`round(agregada, 4) if agregada else None` transforma **0,0** em `None`.
Contraprova sintética: dois exemplos da mesma companhia, escores `[0,1]`,
eventos `[1,0]`; retorna AUC agregada nula, intra 0,0, lacuna 0,0 e aprovação.
O problema apontado é a serialização contraditória, não exigir que T2 passe
a funcionar como teste de utilidade preditiva.

**Fechamento:** distinguir `None` de zero e acrescentar contraprova no T2,
como já foi feito no serializador de baselines. Não foi medida a ocorrência
desse extremo nos dados reais.

## 3. Decisões que não precisam se tornar bloqueios artificiais

**G0.1:** derivar FCO através de mudança de método não equivale, por si só, a
somar duas demonstrações do mesmo período e duplicar o caixa. O CPC 03
apresenta os métodos direto e indireto como alternativas de apresentação dos
fluxos operacionais (§§18–20A). Recomendo explicitar a leitura por unicidade,
preservando a comparabilidade dos operandos e sua linhagem; isso não valida
automaticamente qualquer par documental.
[Fonte primária: CPC 03 disponibilizado pela CVM](https://conteudo.cvm.gov.br/cvm_institucional/export/sites/cvm/menu/regulados/normascontabeis/cpc/CPC_03_R2_rev_13.pdf).

**Seguradoras:** a exclusão estrutural proposta é coerente com o universo não
financeiro declarado. Depende da decisão do responsável antes da medição,
preservando a divulgação de que a taxa-base agregada já foi vista.

**Exposição anterior:** §11 do v2 melhorou materialmente a honestidade do
registro. Não chamar o trabalho de totalmente cego; também não afirmar que
T1/T2 já foram medidos. A exposição declarada não obriga, por si só, a jogar
fora o corpus ou abrir o holdout.

**Caminho separado:** manter o painel de pesquisa continua apropriado.
Não é necessário reconstruir `cvm_treino.duckdb`, reabrir a etapa 10, curar
todas as contas do CSV ou concluir a trilha bancária para prosseguir aqui.

## 4. Lista finita para a próxima implementação

| Ordem | Entrega / aceitação | Quando |
|---|---|---|
| 1 | Contrato de correção de RF-01/RF-02/RF-03, com contraprovas e mudança de versão declaradas | Antes de editar a implementação |
| 2 | Adjudicação com correspondência numérica contextual; ESC-0101 resolvida; revalidação das decisões e heranças atingidas | Antes de certificar o painel |
| 3 | Disponibilidade da evidência propagada ao as-of e ao gate independente; as cinco chaves deixam de ser aprovadas antes da prova, salvo evidência contemporânea demonstrada | Antes de certificar G1 |
| 4 | Partição T1 corrigida; RF-08; validação de correções também protegida no caminho programático que o executor final usará | Antes de medir T1/T2 |
| 5 | RF-04 e escolhas de RF-05 decididas; três `[DECIDIR]` resolvidos; IC do B0 e fluxo cego implementados/testados conforme protocolo | Antes da medição real |
| 6 | Nova versão do painel de pesquisa; G0/G1 reexecutados; RF-06/RF-07 resolvidos; manifesto, código, provas e relatórios na mesma versão | Antes do congelamento da base |
| 7 | Conferência independente das correções, aprovação explícita do responsável e hash do pré-registro final | Antes de T1/T2/baselines |
| 8 | Medir T1/T2 e baselines completos; parar se rejeitado/indecidível; só com `PRONTO PARA CHALLENGER` escrever/aprovar D8 | Antes do treino experimental |

A validação apenas pela CLI e o B0 sem IC já estão reconhecidos no lote C
§8.7; não são apresentados aqui como descobertas novas. A rota de treino não
deve aceitar um dicionário de correções sem as validações que a CLI exige.

O critério não é obter um gate verde a qualquer custo. **Fechar os defeitos
possibilita uma medição válida, que ainda pode rejeitar o alvo.** Não há motivo
para treinar outro modelo enquanto o rótulo/base e o instrumento não estiverem
aptos a essa medição.

## 5. Reprodução e limites

Da raiz do projeto:

```bash
env PYTHONPATH=. .venv/bin/python artefatos/revisao_pre_treino_rank03b_2026-09-17/reproduzir_estrutura.py
```

O script confere os ZIPs, reconstrói somente em memória, compara com o painel
aberto `READ_ONLY`, reproduz G0/G1 e as contagens estruturais, lê apenas as duas
páginas de balanço citadas e executa as fixtures sintéticas de T1/T2. A função
que soma o desfecho real é substituída por erro; `calcular_rotulo=False` é
obrigatório. Saída em stdout, sem regravar o painel ou os artefatos governantes.
Exige `pdftotext` e as dependências já usadas pelo projeto.

Testes executados:

```bash
.venv/bin/pytest -q tests/test_esqueleto_plano_padrao.py tests/test_rank03b_consumo_operacional.py tests/test_fonte_zip_cvm.py tests/test_fonte_rad_cvm.py tests/test_piloto_fonte_rad_rank03b.py tests/test_painel_pesquisa_rank03b.py tests/test_gates_painel_pesquisa_rank03b.py tests/test_adjudicar_escala_rank03b.py tests/test_verificacoes_revisao_final_rank03b.py
env CREWAI_STORAGE_DIR=/tmp/revisao-rank03b-ZRcW2Q/crewai .venv/bin/pytest -q
```

O diretório temporário foi criado com `mktemp`; numa reprodução futura usar
outro diretório temporário gravável. A suíte inclui testes sintéticos do modelo
antigo; não foi executado treino do candidato Rank 3-B nem avaliação real de
seu alvo. Não houve chamada paga ou alteração de dependências.

**Independência:** três revisores receberam escopos separados (escala/fontes,
PIT/períodos e protocolo), sem troca de evidências entre eles. O de protocolo
concluiu parecer; os outros dois enviaram achados, mas foram interrompidos
por limite de uso. O revisor principal reproduziu os achados materiais e as
contagens publicadas aqui. Isso não equivale a três pareceres finais completos.

**Limites:** não foi refeita a adjudicação textual dos 405 documentos nem
validada uma a uma a verdade econômica das 101 correções. A reconstrução
integral dos dados estruturados e a comparação byte/linha não suprem essa
auditoria semântica. O erro confirmado em ESC-0101 basta para impedir a
certificação integral atual; não prova que as outras 100 decisões estejam
erradas. Não medi novos gates sob uma correção hipotética nem desempenho do
modelo. Somente relatório, evidência desta revisão e MEMORY.md foram editados.
