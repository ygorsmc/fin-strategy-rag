# Plano de execução e handoff — piloto documental B-DFC-01J

**Data:** 2026-09-09. **Estado:** plano preparado; piloto ainda não executado.
**Destinatário:** agente que assumirá a implementação e auditoria documental.

## 1. Missão e limite da entrega

Executar o piloto que os especialistas admitiram no
[debate concluído](debate_bancos_dfc_2026-09-09.md): verificar se é possível
reconstruir **juros por competência de instrumentos de captação — J**, seus
componentes, informações da DFC e disponibilidade histórica, no mesmo
consolidado societário IFRS, para cinco bancos × cinco trimestres.

O resultado esperado é uma base documental pequena, rastreável e reproduzível,
acompanhada de um diagnóstico de identificabilidade e recuperabilidade.
**Uma conclusão negativa bem demonstrada também conclui esta tarefa.**

Não executar treino, backtest, seleção de features, comparação preditiva de
baselines, busca de hiperparâmetros ou medição no holdout. Calcular e reconciliar
J **histórico** nos pacotes é parte do piloto; parear esses valores com origens
de previsão e medir desempenho é outra etapa.

Este documento operacionaliza o acordo, **não é o pré-registro confirmatório
de um modelo**. Os critérios documentais abaixo são contratos de integridade,
não novos limiares de eficácia aprovados pelos especialistas.

## 2. Leitura inicial e precedência

Ler antes de agir, nesta ordem:

1. [AGENTS.md](../AGENTS.md) e [MEMORY.md](../MEMORY.md), integralmente: regras
   locais, mudanças posteriores a este plano e estado da execução.
2. [Debate bancário](debate_bancos_dfc_2026-09-09.md), integralmente: contrato
   final, fontes, limites e pontos ainda não aprovados. É a referência da decisão.
3. [Formulação preliminar](formulacao_bancaria_dfc_2026-09-09.md), §§2–3 e 6:
   fontes e consultas. O esboço de alvo/experimento anterior **não prevalece**
   sobre o debate final.
4. [Retomada DFC](viabilidade_ml_dfc_2026-09-08.md), §§2 e 6, e
   [becos sem saída](becos_sem_saida.md), trechos de DFC/CAND-04: defeitos de
   vintage, período e escala que não podem ser herdados.
5. Código e testes relacionados antes de reutilizá-los:
   [auditor estrutural](../scripts/auditar_prontidao_dfc.py),
   [testes do auditor](../tests/test_auditar_prontidao_dfc.py),
   [dados estruturados](../src/dados_estruturados.py),
   [normalização](../src/normalizacao.py) e [.gitignore](../.gitignore).

O debate já terminou; não começar outro para escolher um alvo. Se encontrar
contradição material entre documentos ou mudança posterior no projeto, registrar
a divergência e pedir direção antes de alterar o contrato financeiro.

## 3. Escopo fechado

### 3.1 População e períodos

| CD_CVM, preservando zeros | Emissor de referência | Períodos principais |
|---|---|---|
| `000906` | Bradesco | 2024T1, 2024T2, 2024T3, 2024T4, 2025T1 |
| `001023` | Banco do Brasil | mesmos cinco |
| `019348` | Itaú Unibanco Holding | mesmos cinco |
| `020532` | Santander | mesmos cinco |
| `022616` | BTG Pactual | mesmos cinco |

São **25 pacotes banco–trimestre**, não 25 PDFs nem 25 exemplos supervisionados.
Um pacote reúne as demonstrações, notas, versões e operandos necessários.
Não resolver empresa por nome, ticker ou pelo antigo indicador `is_banco`.
Confirmar a entidade que reporta e seu consolidado; o CD_CVM identifica o
emissor, mas sozinho não prova equivalência entre dois perímetros contábeis.

Usar `2024T1` como convenção dos novos artefatos; adaptar explicitamente os
campos locais que usam `1T2024`, sem inferir período pela capa do PDF.
Os fechamentos principais são 31/03, 30/06, 30/09 e 31/12 de 2024 e 31/03/2025.

Podem entrar períodos anteriores **somente como suporte documentado**, por
exemplo saldo de 31/12/2023 ou operandos acumulados de uma diferença. Não
aumentam o denominador de 25. Versões posteriores de um mesmo arquivamento
podem ser investigadas, mas conservam sua disponibilidade posterior.
Não ampliar a janela de resultados ou o conjunto de bancos para salvar cobertura.

### 3.2 O que pode e o que não pode ser feito

Permitido na execução deste piloto:

- Consultas locais somente leitura, extração de evidência e downloads gratuitos
  de fontes públicas oficiais/RI dos emissores, limitados ao escopo acima.
- Criar scripts, testes e artefatos **isolados** do piloto; curadoria explícita
  de conceitos com fonte; atualizar relatório e MEMORY ao terminar.
- Reaproveitar PDFs e caches já existentes sem sobrescrevê-los. Texto extraível
  ou leitura visual servem à auditoria; OCR pago não está autorizado.

Fora do escopo:

- Abrir, buscar conteúdo ou calcular números de `corpus/holdout_2T2026`, inclusive
  por pesquisa web dos resultados de 2T2026. Não executar buscas recursivas
  indiscriminadas no corpus. Registrar acessos acidentais, se ocorrerem.
- Alterar `artefatos/cvm.duckdb`, `artefatos/cvm_treino.duckdb`, mapas/correções
  de produção, índices, quatro manifestos existentes, caches OCR existentes,
  perguntas congeladas, README de desempenho ou caminho interativo.
- Recarregar o painel inteiro, instalar/trocar dependências, fazer chamadas
  pagas, publicar dados, criar commit/PR ou mesclar branches como efeito lateral.
- Reabrir Rank 3-B não financeiro, Pilar 3 ou outro candidato nesta onda.

Se uma ação exigir expansão, custo ou mudança em produção, concluir as partes
independentes e apresentar o pedido específico. Não interpretar orçamento
remanescente de OCR no MEMORY como autorização para gastá-lo.

## 4. Contrato financeiro vinculante

```text
D = data de decisão segundo disponibilidade documental verificável
q(D) = primeiro trimestre fiscal inteiro cujo início seja posterior a D
J(q) = juros por competência em q dos instrumentos de captação incluídos,
       no mesmo consolidado societário IFRS
```

A regra de D orienta a auditoria de disponibilidade. O piloto não escolhe um
calendário final de previsões nem monta observações supervisionadas.

| Tratamento | Instrumentos/efeitos |
|---|---|
| Incluir | Depósitos, compromissadas, empréstimos/repasses recebidos, títulos de dívida emitidos; subordinados e instrumentos de capital regulatório **se classificados como passivos IFRS** |
| Excluir | Distribuições de patrimônio, juros de arrendamento, componentes atuariais, atualização de provisões, câmbio/negociação/valor justo/derivativos apresentados separadamente |
| Taxa efetiva | Manter encargos que integram o reconhecimento contábil por taxa efetiva; não substituir por cupom hipotético |
| Hedge | Manter amortizações/reclassificações identificadas que integrem contabilmente os juros da obrigação; não acrescentar derivativos separados por associação econômica presumida |
| Mistura inseparável | Marcar **J não identificado**; não estimar a parcela fora do contrato |

A construção aditiva é admitida se **exaustiva**: todas as fontes de captação
incluídas precisam estar cobertas ou ter ausência explicitamente documentada.
Não exigir subtração de pensões comprovadamente fora das parcelas escolhidas.
Também não somar algumas linhas disponíveis e chamar o resultado de total.
“Outras despesas de juros” exige esclarecimento; uma nota qualitativa não
fornece o valor de uma exclusão.

J não é custo marginal, taxa, caixa pago, custo econômico líquido de todas as
proteções ou sinal automático de estresse. Não trocar o contrato pela linha
total de juros/similares ou pelas fórmulas `g1` e `g1+h` do IFData.

**Perímetro:** DRE, BP, DFC e notas devem pertencer ao mesmo consolidado IFRS.
Não misturar consolidado/individual, holding/banco operacional ou IFRS/BRGAAP.
Ponte de lucro usada no G4 não prova a ponte de cada componente de J ou da DFC.
Procurar demonstrações IFRS específicas quando necessário é necessidade deste
piloto, não motivo para reabrir o antigo lote de OCR descartado para o G4.

O núcleo não precisa de números BCB. Se não os usar, **não exigir crosswalk
prudencial**. Qualquer complemento numérico IFData exige sua própria ponte
temporal/de perímetro. Não importar automaticamente sua quebra de 2025 para o
IFRS: examinar políticas, apresentação e consolidação de cada banco.

## 5. Ponto de partida verificável

### 5.1 Dados locais e limitações conhecidas

- Painel de treino: `artefatos/cvm_treino.duckdb`, somente leitura. SHA-256
  conferido na rodada anterior:
  `c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b`.
  Se mudou, registrar e investigar a mudança; não restaurar nem assumir corrupção.
- `documentos` contém `cd_cvm`, `conjunto`, `dt_refer`, `versao`, `id_doc`,
  `dt_receb`, `link_doc`. O recorte produziu 25 grupos, oito multiversão.
  **São metadados de arquivamento, não 25 pacotes IFRS completos.**
- `fatos_contabeis` retém valores da maior versão, não todos os vintages.
  As derivações atuais não preservam toda a linhagem; foram encontrados
  períodos semestrais classificados como trimestrais. Não usar esses valores
  como prova automática de J histórico ou PIT.
- [Manifesto IFRS](../corpus/ifrs/manifesto_ifrs.csv): 15 documentos de BB,
  BTG e Santander; filtrar o piloto. Os PDFs ficam em `corpus/ifrs/raw/` e o
  OCR completo em `corpus/ifrs/ocr_documento/`. `corpus/ifrs/ocr/` é cache
  **parcial de âncoras do G4**, de outro schema; não sobrescrever.
- Ausência da expressão “captação” na DRE ou presença do código `6.01` são
  diagnósticos de busca, não decisões semânticas. RN09 continua valendo.

### 5.2 Três casos para testar o método antes de escalar

**BB IFRS 1T2025 — redundância parcial de DFC.**

- [PDF oficial](https://api.mziq.com/mzfilemanager/v2/d/5760dff3-15e1-4962-9e81-322a0b3d0bbd/a4033fa2-0a8e-d6ab-9cd1-a044c3ab904b?origin=2),
  [cópia local](../corpus/ifrs/raw/bb_ifrs_1T2025.pdf).
- SHA-256: `1f3e89212f0ad62f8cc7a03ebab90ea06510193780f42186bb90e25c1b56c0da`.
- DFC: página impressa 6, PDF 17, índice zero 16. Saldos: impressa 41,
  PDF 52, índice zero 51. Em R$ mil:
  `864.972.382 − 873.710.691 = −8.738.309` (clientes);
  `749.565.355 − 724.024.327 = 25.541.028` (instituições financeiras).
- Juros pagos e competência aparecem nas páginas PDF 18 e 30, impressas 7 e
  19. A nota 5 apresenta parcelas e “outros”; **J ainda não foi reconciliado**.
- Essas duas igualdades não provam redundância de toda DFC. São contraprovas
  ao argumento de que qualquer linha DFC já traz informação nova.

**Santander IFRS 1T2025 — juros/similares pode incluir pensões.**

- [PDF oficial](https://api.mziq.com/mzfilemanager/v2/d/a2595886-9fbb-4339-8a38-71d6ce7c7d36/f6754e68-2d4d-baa9-6490-6251042430e1?origin=2),
  [cópia local](../corpus/ifrs/raw/santander_ifrs_1T2025.pdf).
- SHA-256: `1bdcfffacc5a276d921e5461f2e27c572c5c47e04ccdab79f7940a8f86533f5f`.
- Página impressa/PDF 14, índice zero 13, item sobre fundos de pensão.
  A informação é qualitativa: não autoriza inventar montante a subtrair.

**BTG ITR 1T2024 — acesso por versão não certifica seu conteúdo.**

| Versão cadastrada | ID_DOC | DT_RECEB cadastrado |
|---|---|---|
| 1 | `137097` | 2024-05-13 |
| 2 | `137730` | 2024-05-20 |
| 3 | `143583` | 2024-11-29 |

[Endpoint oficial da versão 1](https://www.rad.cvm.gov.br/ENETCONSULTA/frmDownloadDocumento.aspx?CodigoInstituicao=1&NumeroSequencialDocumento=137097).
Uma resposta foi ZIP válido, embora `Content-Type` fosse `text/html`.
Continha XMLs, XLSX e PDF gerado na consulta. As novas tentativas deram timeout.
O corpo anterior **não foi arquivado** e seus valores não foram certificados.
Seu hash histórico está no debate; não o tratar como hash esperado imutável.

Validar identidade e versão **dentro** do conteúdo recuperado e seu regime
contábil. Um ITR não é automaticamente a demonstração IFRS procurada. Guardar
hash do ZIP e dos membros relevantes: a geração de PDF com timestamp pode
alterar o contêiner sem alterar o XML. Download em 2026 não é publicação em 2024.

## 6. Entregáveis e organização isolada

Os caminhos abaixo são **propostos para criação pelo executor**, não artefatos
já existentes. Não iniciar um novo framework nem ligar o piloto ao produto.

```text
scripts/piloto_bancos_dfc.py                # inventário, coleta controlada e auditoria
tests/test_piloto_bancos_dfc.py             # contratos e contraprovas offline
artefatos/b_dfc_01j/
  escopo.csv                              # exatamente 25 pacotes principais
  fontes.jsonl                            # documentos, versões, downloads e evidências
  fatos.jsonl                             # valores observados, sem perder texto de origem
  mapa_j.jsonl                            # decisão semântica com procedência
  derivacoes.jsonl                        # DAG de operandos e fórmulas
  componentes_dfc.jsonl                    # natureza, comparação com BP e disponibilidade
  auditoria_pacotes.csv                    # todos os 25, inclusive falhas/ausências
  auditoria.json                          # contagens derivadas e gates documentais
  execucao.json                           # hashes, versões de código, comandos e acessos
  README.md                               # schema, regeneração e limites
  raw/                                    # binários de novas fontes, FORA do Git
resultados/piloto_bancos_dfc_<data>.md       # resultado real, não este plano
resultados/revisao_piloto_bancos_dfc_<data>.md
```

Se for necessário dividir o script em módulos auxiliares de `scripts/`, fazê-lo
sem importar treino ou aplicação. Registrar a mudança de caminhos no README.
Usar dependências já instaladas. Acrescentar uma regra estreita para
`/artefatos/b_dfc_01j/raw/` ao `.gitignore` **antes** de guardar novos PDFs/XMLs/
XLSX; não ignorar os manifestos e resultados leves. Não duplicar PDFs locais
íntegros: referenciá-los por caminho e hash.

Arquivar downloads de forma imutável/endereço por conteúdo, com escrita
atômica e retomada. Artefatos derivados devem carregar hashes dos insumos;
curadoria não deve ser sobrescrita por nova extração sem detectar o conflito.

### 6.1 Campos mínimos dos artefatos

Todos têm `schema_version`. IDs são estáveis, sem dependência da ordem das
linhas; CD_CVM e versões externas não perdem zeros ou identidade.

**`escopo.csv`:** `pacote_id`, `cd_cvm`, `periodo`, `inicio`, `fim`.
Não construir esta lista a partir apenas de documentos encontrados.

**`fontes.jsonl`:** `fonte_id`, `pacote_ids`, `papel` (principal/suporte),
`cd_cvm`, entidade reportante, base contábil, perímetro, tipo de documento,
intervalo/data-base, versão, ID/protocolo, URL oficial, caminho local,
hash SHA-256, tamanho, formato detectado, hash/localizador do membro interno,
data/hora de coleta, disponibilidade histórica, precisão dessa data,
evidência que a sustenta, identidade/versão verificadas e tentativas/erros.
Datas desconhecidas ficam nulas com motivo; não preencher pela data de coleta.

**`fatos.jsonl`:** `fato_id`, `pacote_id`, `fonte_id`, conceito proposto,
código e descrição originais, rótulos de linha/coluna, texto numérico original,
valor decimal assinado, moeda, unidade/multiplicador, resolução de apresentação,
valor em reais, início/fim ou data de estoque, base/perímetro, disponibilidade,
página PDF 1-based + impressa + índice zero quando houver, ou XML/XPath/
planilha/célula, trecho de evidência, método de extração e estado da conferência.

**`mapa_j.jsonl`:** `mapeamento_id`, pacote/versão de validade, instrumento,
fatos de suporte, `incluir|excluir|nao_identificado`, motivo financeiro,
política de taxa efetiva/hedge, prova de cobertura/exaustividade, relação
pai–filha e decisão/revisor. Não usar só `cd_conta` ou só similaridade textual.

**`derivacoes.jsonl`:** `derivado_id`, conceito/período resultante, operandos
por ID, coeficientes/fórmula, versão da regra, moeda/escala/perímetro,
compatibilidade de políticas/vintages, resultado, tolerância justificada,
resíduo, disponibilidade máxima dos operandos e status. Grafo sem ciclos;
todo operando deve existir, ser observado ou ter sua própria derivação.

**`componentes_dfc.jsonl`:** IDs de fatos/derivações, natureza, método MI/MD,
equivalente BP/DRE/notas, reconciliação, classificação de redundância,
limitações semânticas, disponibilidade e eventual atraso em relação às demais
fontes. Separar “não se provou redundante” de “informação incremental provada”.

**`auditoria_pacotes.csv`:** exatamente 25 linhas; contagens de fontes/versões,
gates por eixo, J histórico ou ID de derivação (nulo se não identificado),
primeira divulgação identificável e grau de certeza, componentes DFC
classificados, restrições de disponibilidade, motivo de falha/conflito,
evidências e pendência de revisão. Contagens agregadas saem desta tabela,
nunca são digitadas para obter uma manchete.

**`execucao.json`:** início/fim UTC, branch/HEAD, estado inicial das alterações,
versões de ambiente/script/contrato, parâmetros, hashes antes/depois das entradas
usadas, comandos, tentativas HTTP, custo efetivo, logs de teste, desvios e
registro de exposição. Não escrever `holdout_acessado=false` sem verificar
os caminhos/requisições efetivamente usados. Não registrar segredos.

## 7. Plano de execução por ondas

### Onda 0 — preflight e contrato operacional

1. Ler os documentos indicados; registrar `git status --short`, branch/HEAD e
   insumos relevantes. O worktree já contém trabalho da investigação anterior:
   não limpar, restaurar ou incorporar mudanças alheias.
2. Conferir schema do DuckDB em conexão `read_only=True`, hashes dos arquivos
   usados e existência dos PDFs permitidos. Não rodar o construtor do painel.
3. Criar os 25 pacotes e a política de fontes/saídas. Guardas de escopo devem
   rodar antes de abrir arquivo/fazer requisição, não só depois de extrair números.
4. Registrar as convenções deste plano antes de extrair: sinal, nulidade,
   arredondamento, período, versionamento e status. Ajustes de engenharia são
   documentados; mudança no estimando exige nova decisão.

**Saída:** escopo, manifesto de execução inicial e testes das guardas.
**Aceite:** 25 chaves únicas, zero acesso proibido, entradas somente leitura,
destino separado e binários novos ignorados pelo Git.

### Onda 1 — inventário de documentos, perímetros e versões

1. Cruzar cada pacote com o cadastro `documentos`, sem supor que o cadastro
   contém todas as peças IFRS. Listar versões, datas/IDs e lacunas.
2. Conferir os manifestos locais **filtrando os períodos permitidos**. Pesquisar
   fontes primárias por banco/período exatos apenas para peças faltantes.
3. Localizar DRE, BP, DFC, notas de captação/juros/pensões/hedge e políticas.
   Marcar cada peça como encontrada, ausente, ilegível ou de outro perímetro.
4. Relacionar o documento IFRS à evidência de sua própria publicação. Não
   transferir `DT_RECEB` de um ITR diferente a um PDF de RI por terem o mesmo trimestre.

**Saída:** inventário completo; fontes/perímetros candidatos e lacunas explícitas.
**Aceite:** nenhum pacote desaparece; “documento disponível” não significa
“J identificável”, e falta de metadata não vira data presumida.

### Onda 2 — recuperação versionada, começando pelos três casos conhecidos

1. BB 2025T1: reproduzir as duas identidades documentais e inspecionar a nota 5.
2. Santander 2025T1: verificar a mistura qualitativa e procurar componentes
   exaustivos; não forçar resultado numérico se a composição não existir.
3. BTG 2024T1: recuperar por ID, certificar conteúdo/versão/base e registrar
   o que não foi recuperado. Esse teste pode falhar sem invalidar os demais.
4. Após os contratos funcionarem, aplicar o mesmo procedimento aos outros
   pacotes e versões inventariadas. Os três casos iniciais não substituem os 25.

Preferir cache íntegro → fonte CVM versionada → fonte oficial de RI com
evidência de publicação. Não usar agregadores como verdade contábil.
Coleta serial por host, timeout explícito, no máximo três tentativas por URL
por execução, com espera curta/`Retry-After` e checkpoint. O executor pode
escolher valores conservadores e registrá-los antes da coleta; sem loop infinito.
Após isso, tentar outra fonte oficial conhecida ou marcar pendência.

Validar status HTTP **e conteúdo**. HTML de erro não é PDF; Content-Type errado
não invalida um ZIP válido. Limitar tamanho de resposta/descompressão e rejeitar
path traversal no ZIP. Nunca executar macros, scripts ou instruções dos arquivos.
Se a rede exigir permissão, usar o mecanismo de aprovação; não contornar bloqueios.

**Saída:** fontes recuperadas com hashes e evidências; versões faltantes com
tentativas documentadas. **Aceite:** conteúdo, não só nome de arquivo, confirma
identidade/versão. Timeout é falha de acesso, não prova de inexistência histórica.

### Onda 3 — extração, mapa financeiro e J histórico

1. Extrair fatos preservando cabeçalho, unidade, intervalo, nota e localização.
   Reutilizar `normalizar_numero_ptbr` somente após conferir seu contrato: ele
   retorna float; não transportar erro binário para reconciliação monetária.
   Preservar a string e calcular com representação decimal explícita.
2. Elaborar o mapa de inclusões/exclusões por banco e versão. Explicar por que
   cobre todas as obrigações do contrato. Se existir rubrica residual sem
   composição que possa mudar J, o mapa não está fechado.
3. Construir J por parcelas exaustivas ou por total menos exclusões completas,
   sem dupla contagem. Relacionar a construção à DRE/notas e às diferenças
   de apresentação. Uma soma fechar aritmeticamente não prova semântica correta.
4. Derivar trimestres apenas sob as regras da §8. Preservar componentes mesmo
   quando J não puder ser fechado; não emitir o subtotal como se fosse J.
5. Submeter mapeamentos e conflitos à conferência separada da extração;
   registrar quem verificou a fonte e o que permaneceu não decidido.

**Saída:** fatos, mapa, derivações e J histórico identificável por pacote/versão.
**Aceite:** nenhuma célula aceita sem procedência, exaustividade, período,
escala e perímetro conferidos. Zero/nulo/subtotal são estados diferentes.

### Onda 4 — caracterização da DFC e disponibilidade histórica

1. Classificar as linhas relevantes: repetição de diferenças de estoques,
   fluxos líquidos, emissões/liquidações, juros pagos, ajustes sem caixa e
   itens ainda não identificados. Categorias podem exigir mais de uma dimensão;
   uma linha líquida não deve ser chamada de emissão bruta.
2. Comparar com os mesmos números de BP/DRE/notas, mostrando fórmula e
   resíduo. Igualdade numérica isolada é diagnóstico, não prova universal da
   composição econômica. Diferença de saldo não é automaticamente fluxo de principal.
3. Comparar juros pagos com J **somente se os escopos estiverem reconciliados**.
   Registrar diferenças de competência, calendário, juros a pagar e classificação;
   não criar um proxy de estresse a partir do resíduo.
4. Construir a disponibilidade de cada fato e operando, distinguindo original,
   reapresentado, recuperado e não certificado. Marcar a primeira divulgação
   em que J foi identificado; se versões anteriores faltam, isso é apenas a
   primeira **recuperada**, não a primeira histórica demonstrada.
5. Registrar quando cada conjunto informacional ficaria disponível e o eventual
   atraso de esperar a DFC. Não escolher D a posteriori para favorecer M1.

**Saída:** classificação DFC e trilha as-of. **Aceite:** valores atuais não se
transformam em históricos por receber uma data antiga; componentes redundantes
ficam explícitos para o futuro M0, não omitidos para fabricar ganho de M1.

### Onda 5 — consolidação, testes e revisão de conformidade

1. Gerar a tabela integral e os gates da §9; contar separadamente cobertura
   documental, J identificado, vintage certificado e DFC classificada.
2. Rodar os testes da §10. Reexecutar a auditoria offline a partir dos artefatos,
   sem rede, e conferir resultados determinísticos. Conferir hashes das entradas.
3. Fazer revisão transversal `auditor-conformidade`, somente leitura, conforme
   AGENTS §7; fechar defeitos de implementação antes de declarar a onda concluída.
4. Gerar relatório de resultado com fontes/células reproduzíveis, limitações,
   custos, testes, revisão e recomendação estritamente documental. Atualizar
   MEMORY com o resultado e a próxima decisão, sem transformar o plano em log.

**Saída:** relatório, artefatos, testes e revisão. **Aceite:** §11 atendida.
Não avançar automaticamente da conclusão desta onda para treino.

## 8. Regras de aritmética e point-in-time

### 8.1 Período, sinal, escala e reconciliação

- Preferir trimestre isolado explicitamente divulgado. Para acumulados anuais,
  Q2 = 6m − 3m, Q3 = 9m − 6m e Q4 = 12m − 9m **apenas se** os intervalos,
  conceitos, perímetros, políticas e bases de revisão forem compatíveis.
- Se a fonte reinicia no semestre, a regra é outra: Q3 pode já ser isolado e
  Q4 = 2º semestre − Q3. Usar datas reais, não uma regra global “último menos
  anterior”. Um valor de seis meses nunca recebe etiqueta de três meses.
- Não impor o reinício semestral do IFData a um PDF IFRS sem conferir. Não
  reutilizar `_derivar_trimestres_intermediarios` como se já fechasse este contrato.
- Derivação com operando ausente, unidade incerta ou política incompatível fica
  indisponível. Nada de dividir anual por quatro ou inferir zero de célula vazia.
- Conservar sinal original; representar J como despesa positiva somente com
  transformação de sinal documentada. Reversão/crédito não vira despesa com `abs`.
- Moeda, MIL/UNIDADE e precisão são propriedades da fonte. Não corrigir erro
  de escala por fator escolhido para fazer uma soma fechar.
- Não somar pai com filhas ou MI com MD. Duplicatas iguais são rastreadas;
  divergentes viram conflito, não `max`, média ou escolha silenciosa.
- Justificar tolerância pela resolução exibida: em soma/diferença, o limite de
  arredondamento combina as resoluções de cada operando e do total comparado.
  Registrar a hipótese de arredondamento; se desconhecida, não supor precisão.
  Não usar um percentual de materialidade escolhido depois de ver o resíduo.
  Tolerância aritmética nunca valida uma exclusão conceitual desconhecida.

### 8.2 Disponibilidade e versões

- `dt_refer` mede a referência contábil; `dt_receb` pertence a uma versão/
  protocolo; data de coleta mede a coleta. Nenhuma substitui a outra.
- Data de recepção só sustenta disponibilidade daquele **conteúdo** quando
  a identidade entre valor, versão e protocolo foi demonstrada. Hash comprova
  integridade de um snapshot, não sua existência pública em data passada.
- Com apenas data, não alegar horário intradiário. Guardar essa precisão e
  usar limite conservador de fim do dia; o calendário operacional final de D
  será definido no pré-registro, sem antecipar informação no mesmo dia.
- Disponibilidade de derivado é no mínimo o máximo da disponibilidade de todos
  os operandos e evidências necessárias à sua interpretação. Não retroagir uma
  nota esclarecedora publicada depois. Se algum operando é incerto, o derivado
  não é PIT certificado.
- Para uma consulta as-of, cada operando deve estar disponível no corte e ser
  semanticamente compatível. Números de versão de dois formulários diferentes
  não precisam ser iguais; a compatibilidade deve ser demonstrada, não inferida.
- Comparativo de 2024 reapresentado num PDF posterior não prova o valor que o
  analista conhecia em 2024. Guardar ambos, sem sobrescrever a primeira versão.
- Separar identificação contábil *as-restated* de identificação histórica.
  O piloto pode demonstrar a primeira e não a segunda. Não herdar a regra
  diagnóstica `last_day(dt_refer + 3 meses)` como decisão final do experimento.

## 9. Gates documentais e condições de parada

Estes identificadores são exclusivos do piloto, não os G1–G4 do produto.

| Gate | Condição para `CONFERIDO` no pacote | Exemplo que impede aprovação |
|---|---|---|
| P0 — integridade | Fonte recuperada, íntegra, identidade/base/período verificados | HTML de erro, conteúdo de outra versão |
| P1 — semântica | Perímetro IFRS consistente; mapa exaustivo do contrato J | Juros com pensões não separáveis |
| P2 — aritmética | Sinais, escala, intervalo e reconciliação documentados | Semestre tratado como trimestre; dupla contagem |
| P3 — histórico | Valores e operandos vinculados às próprias versões e disponibilidade | Só existe metadata v1 com valores v3 |
| P4 — DFC | Componentes investigados/classificados com equivalentes e lacunas explícitos | Suposta informação nova é subtração não examinada |

Por eixo usar `CONFERIDO`, `NAO_IDENTIFICADO`, `CONFLITANTE` ou `PENDENTE`,
sempre com motivo e evidência. Uma revisão ainda não feita permanece pendente;
não é convertida em concordância pela execução do script.

Publicar interseções de gates por banco/período e os gargalos de cada uma.
P4 não exige encontrar informação nova; classificar corretamente componentes
redundantes é conclusão válida. A interseção é **documental**, não o tamanho
de amostra supervisionada nem prova de poder estatístico.

Condições de parada:

- Falha localizada: registrar o pacote e continuar os demais. Não substituir
  por outro banco/trimestre nem omitir a falha do denominador.
- J inseparável: parar sua reconstrução naquele pacote; conservar evidências
  e componentes parciais, sem renomear o alvo ou estimar exclusões.
- Fonte não recuperada após tentativas e alternativas limitadas: marcar
  pendência de acesso; não declarar impossibilidade econômica.
- Necessidade de gasto, de ampliar escopo ou de alterar produção: pedir direção
  para essa parte. Não tratar como autorização implícita para ultrapassar limites.
- Se nenhuma interseção documental utilizável puder ser certificada, concluir
  o negativo do piloto. Se houver interseção, reportar sua extensão; **não existe
  mínimo aprovado** que autorize treino. Suficiência estatística continua pendente.

## 10. Testes, conferência independente e reprodução

### 10.1 Contratos obrigatórios do código novo

Implementar testes offline com fixtures pequenas, positivas e adversariais:

1. Os 25 pacotes existem mesmo com zero documentos; IDs/períodos fora do escopo
   e caminhos/URLs de holdout são barrados antes de leitura/requisição.
2. Saída não sobrescreve entrada/painel; DuckDB abre somente leitura; hashes
   inconsistentes não são aceitos; nova coleta não sobrescreve vintage anterior.
3. ZIP com Content-Type errado pode ser válido; HTML com HTTP 200 falha;
   versão interna diferente, ZIP inseguro, timeout e retorno vazio têm tratamento.
4. MIL/UNIDADE, parênteses/sinais, crédito, zero explícito e ausente não se
   confundem; nenhuma coerção por `abs`, preenchimento ou escala ad hoc.
5. Quarterização anual e semestral correta; falta de operando, intervalos
   incompatíveis, seis meses rotulados trimestrais e políticas incompatíveis falham.
6. Pai/filhas, MI/MD e duplicatas não duplicam J; conflito permanece visível.
   Composição não exaustiva, residual desconhecido ou hedge separado não viram J.
7. Derivação guarda todos os operandos; indisponibilidade de um deles impede
   certificação; versão futura não passa usando recepção de versão antiga.
8. Precisão somente diária não é promovida a horário; primeira recuperada não
   vira primeira publicação quando faltam versões anteriores.
9. Reproduzir as identidades do BB e a contraprova qualitativa do Santander em
   fixtures com procedência. Esses casos não são gold de J nem amostra de ML.
10. Base vazia, pacotes omitidos ou nenhum J identificado não produzem aprovação;
    contagens do relatório correspondem ao inventário; nova execução offline
    reproduz cálculos e estados sem acesso à rede.

Fixtures sintéticas exercitam o software; evidências documentais exercitam a
extração real. Uma categoria não substitui a outra. Não versionar PDFs completos
como fixtures, não introduzir skips nem enfraquecer asserções existentes.

### 10.2 Revisões e limites do que agentes podem validar

Separar conferência semântica e revisão de código/procedência. O revisor deve
receber fontes e contrato, conferir os valores decisivos e registrar objeções,
não apenas concordar com a síntese do executor. Para pareceres independentes,
não fornecer a conclusão do outro revisor antes do primeiro parecer; mediação
posterior transmite objeções e evidências, não raciocínios privados.

Rodar o `auditor-conformidade` somente leitura após a implementação, conforme
AGENTS. Isolamento por instrução/contexto não é isolamento físico do filesystem.
Agentes podem auditar mapeamentos e cálculos; concordância deles **não** demonstra
utilidade para analista nem substitui o estudo humano futuro. Se a revisão não
puder ocorrer, entregar com `revisao_pendente`, sem afirmar conclusão integral.

### 10.3 Comandos de referência

Comandos já disponíveis, sem iniciar treino ou alterar corpus:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
sha256sum artefatos/cvm_treino.duckdb
pdftotext -f 17 -l 17 -layout corpus/ifrs/raw/bb_ifrs_1T2025.pdf -
pdftotext -f 52 -l 52 -layout corpus/ifrs/raw/bb_ifrs_1T2025.pdf -
pdftotext -f 14 -l 14 -layout corpus/ifrs/raw/santander_ifrs_1T2025.pdf -
```

Consulta histórica de inventário, em DuckDB somente leitura:

```sql
SELECT cd_cvm, conjunto, dt_refer, versao, id_doc, dt_receb, link_doc
FROM documentos
WHERE cd_cvm IN ('000906','001023','019348','020532','022616')
  AND dt_refer IN (DATE '2024-03-31', DATE '2024-06-30',
                  DATE '2024-09-30', DATE '2024-12-31', DATE '2025-03-31')
ORDER BY cd_cvm, dt_refer, conjunto, versao;
```

**Interface a implementar**, não comandos existentes hoje. Manter coleta
explícita e auditoria offline separadas:

```bash
.venv/bin/python scripts/piloto_bancos_dfc.py inventariar --painel artefatos/cvm_treino.duckdb --saida artefatos/b_dfc_01j
.venv/bin/python scripts/piloto_bancos_dfc.py coletar --diretorio artefatos/b_dfc_01j --permitir-rede
.venv/bin/python scripts/piloto_bancos_dfc.py auditar --diretorio artefatos/b_dfc_01j
```

Sem `--permitir-rede`, nenhuma etapa pode baixar implicitamente. `auditar` deve
calcular gates a partir das evidências/curadoria e verificar sua integridade,
não carimbar aprovação de um arquivo de decisões sem conferência. Documentar
como extração e curadoria alimentam os artefatos e sua ordem de execução.

Testes após implementar; preparar diretório temporário gravável para o SQLite
do CrewAI, sem alterar HOME, pins ou contratos:

Conferir previamente fixtures e coleta de testes: datas sintéticas de 2T2026
para testar uma guarda não são o holdout real. Se algum teste passar a exigir
leitura do reservado, não executá-lo nem introduzir skip para obter verde;
registrar o conflito e solicitar direção antes da suíte completa.

```bash
bdfc_test_state=$(mktemp -d /tmp/bdfc-test-state.XXXXXX)
CREWAI_STORAGE_DIR="$bdfc_test_state" .venv/bin/python -m pytest -q tests/test_piloto_bancos_dfc.py tests/test_auditar_prontidao_dfc.py tests/test_dados_estruturados.py --tb=short
CREWAI_STORAGE_DIR="$bdfc_test_state" .venv/bin/python -m pytest -q --tb=short
git diff --check
```

A referência anterior foi 1.796 testes aprovados, zero skip; não é garantia
do estado futuro nem número a copiar como resultado desta execução. Registrar
contagens reais e falhas ambientais separadamente. Não corrigir nesta onda
o conflito de dependências numpy/Presidio já registrado no MEMORY.

## 11. Definição de pronto e formato da entrega

O piloto está documentalmente concluído quando:

- [ ] Os 25 pacotes têm decisão por eixo, inclusive ausência/conflito justificados.
- [ ] Toda cifra aceita tem fonte/localizador, unidade, período, perímetro e versão.
- [ ] Todo J identificado tem mapa exaustivo e reconciliação reproduzível.
- [ ] Todo derivado tem linhagem completa; incerteza PIT não está escondida.
- [ ] As informações DFC investigadas estão classificadas sem alegação preditiva.
- [ ] Cobertura/interseções são calculadas, com denominadores explícitos.
- [ ] Código novo, testes, regeneração offline e revisão estão concluídos;
      problemas não resolvidos constam como pendências, não aprovações.
- [ ] Não houve mutação de produto/painéis/corpora nem exposição ao holdout;
      qualquer desvio real está declarado, não apagado.
- [ ] Relatório e MEMORY foram atualizados com caminhos e próxima decisão.

O relatório final deve permitir repassar o trabalho sem abrir esta conversa:

1. Resultado em uma frase: o que foi identificável e o que permanece indecidível.
2. Matriz cinco bancos × cinco trimestres, com J, gates, fontes e motivos.
3. Cobertura em números separados: documentos, versões, pacotes com J,
   pacotes historicamente certificados e interseção documental com DFC.
4. Reconciliações auditáveis e conflitos; exemplos positivos e negativos,
   não apenas os três casos já conhecidos.
5. Inventário de lacunas: fonte faltante, tarefa precisa para resolver, custo
   ou autoridade necessária; separar fonte inexistente de não recuperada.
6. Comandos, hashes, versões, testes executados, revisão e custos efetivos.
7. Recomendação: continuar coleta / pedir decisão / preparar pré-registro.
   Nunca “modelo validado” nem “DFC sem valor” a partir deste piloto.

Uma cobertura parcial pode concluir a investigação documental com resultado
negativo ou limitado. Tarefa interrompida antes de avaliar os pacotes e concluir
a revisão é entrega parcial, não piloto integralmente concluído.

## 12. Depois do piloto — decisão separada, não executar agora

Se houver dados identificáveis, submeter o resultado para decidir se vale
ampliar a base e fechar um **pré-registro de regressão**. Faltará definir:

- População elegível, calendário de D, alvo na primeira divulgação identificável,
  política de revisões/censura, separação temporal e tamanho mínimo fundamentado.
- Materialidade em unidades econômicas, piora tolerada por banco/regime,
  calibração, largura útil dos intervalos, cobertura documental e custo de uso.
  **O limiar de 10% foi retirado; nenhum percentual está aprovado.**
- Benchmark econômico por fonte: saldo projetado × custo esperado × duração,
  com informação conhecida em D; persistência e sazonalidade como referências.
- M0 com BP/DRE/notas/juros e diferenças de saldos; M1 com os mesmos dados,
  datas, algoritmo, transformações, ajuste e intervalos, acrescentando DFC.
  Precisa demonstrar benefício contra **M0 e benchmark**, não apenas um deles.
- Quantis 0,1/0,5/0,9, perda de quantis, erros em R$ e escala conhecida em D,
  cobertura/largura/caudas, resultados por banco e ganho temporal dentro dele.
- Poder e incerteza respeitando dependência temporal e choques comuns. Cinco
  bancos fixos não demonstram generalização para instituições nunca vistas.
- Estudo de benefício para o analista, separado de precisão contábil e preditiva.

Não usar juros/saldos médios futuros realizados como preditores. Não gastar o
holdout para definir materialidade, tamanho amostral ou escolher features.
T1/T2 dos experimentos anteriores continuam onde foram definidos; não declarar
aprovação por analogia com J contínuo. O novo protocolo deve preservar auditoria
de baseline mecânico, escala e sinal dentro do emissor, com critérios próprios.

## 13. Referências adicionais e instrução pronta para o próximo agente

As fontes por caso estão na §5; as evidências e bibliografia do acordo estão no
[debate, §§4–7](debate_bancos_dfc_2026-09-09.md). Para resolver dúvida contábil,
consultar fontes primárias, sem transformar pesquisa genérica em prova do piloto:

- [CPC 03, §§15, 18–24 e 31–33](https://conteudo.cvm.gov.br/export/sites/cvm/menu/regulados/normascontabeis/cpc/CPC_03_R2_rev_13.pdf):
  distinções de apresentação de fluxos e juros; a política do banco ainda precisa
  ser conferida no documento que originou cada valor.
- [Metodologia IFData](https://www.bcb.gov.br/conteudo/dadosabertos/BCBDesig/IFData%20-%20Esclarecimentos%20e%20Metodologia.pdf)
  e [rotas verificadas na investigação](formulacao_bancaria_dfc_2026-09-09.md):
  somente se necessário como complemento; não são pré-condição do núcleo IFRS.
- [Pré-registro CAND-04](pre_registro_cand04_previsao_fundamentos_2026-08-27.md):
  precedente metodológico contínuo, sem herança de métricas ou limiares.

Texto para iniciar a próxima sessão:

> Execute o piloto documental B-DFC-01J descrito em
> `resultados/plano_piloto_bancos_dfc_2026-09-09.md`. Leia primeiro AGENTS.md,
> MEMORY.md e o debate bancário de 2026-09-09. A tarefa é investigar os 25
> pacotes dos cinco bancos entre 2024T1 e 2025T1, reconstruir J histórico quando
> identificável, classificar DFC, certificar versões/disponibilidade e entregar
> artefatos, testes, revisão e relatório reproduzível. Comece pelo preflight e
> inventário; use BB 2025T1, Santander 2025T1 e BTG 2024T1 como casos iniciais,
> sem abandonar os demais. Preserve as alterações existentes. Trabalhe isolado
> do produto, sem modificar painéis/corpora, sem treino, sem chamadas pagas e
> sem acessar o holdout 2T2026. Ausência não é zero, metadata não é vintage e
> concordância entre agentes não valida um modelo. Conclua com a cobertura real
> e os bloqueios, mesmo se o resultado for negativo; não avance para ML sem
> nova decisão e pré-registro.

**Registro desta entrega:** somente o plano e sua referência no MEMORY foram
preparados nesta etapa. Scripts/artefatos novos acima ainda serão implementados;
nenhum dos gates do piloto foi declarado aprovado por este documento.
