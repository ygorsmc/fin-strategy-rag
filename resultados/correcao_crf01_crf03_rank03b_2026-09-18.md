# Correção CRF-01 a CRF-03 — Rank 3-B

Início: 2026-09-17. Fechamento da verificação: 2026-09-18.
**Resultado: CRF-01/02 fechados no instrumento e CRF-03 na documentação,
com conferência independente. Painel reconstruído REPROVADO EM G0;
cobertura operacional insuficiente. Treino não autorizado.**

## Escopo e contratos

Pedido: corrigir os achados da [conferência RF](conferencia_rf01_rf08_rank03b_2026-09-17.md).
Contrato registrado antes do código:
[CRF-01 a CRF-03](contratos_correcao_crf01_crf03_rank03b_2026-09-17.md);
[adendo da auditoria de 18/09](adendo_contratos_crf_2026-09-18.md).

Nenhum treino, alvo real, T1/T2/baseline real, acesso ao holdout, chamada paga,
download novo ou alteração dos painéis compartilhados foi autorizado.
As cinco escolhas de política continuam [DECIDIR]. O executor v2 de pré-treino
não foi implementado nesta onda.

## 1. CRF-01 — evidência vinculada à célula

A regra vigente é v4. As funções v2/v3 continuam disponíveis explicitamente
para reprodução histórica. O novo extrator só decide quando encontra, nas
notas, uma tabela com unidade e perímetro consolidados locais, datas completas
inequívocas, rótulo de conta completo e uma célula para cada data. A comparação
usa apenas a célula da data corrente. Um número de fornecedores ao lado de
caixa não prova caixa.

O escopo operacional da v4 é deliberadamente restrito a **saldos**: ativo
total, passivo total e caixa/equivalentes. A data final de um fluxo não basta
para distinguir trimestre e acumulado; nenhuma conta 6.x decide escala nesta
versão. Assim, a movimentação cambial de investimento que sustentava
ESC-0029 não é mais aceita como prova de caixa.

Isso não demonstra que o valor real da antiga ESC-0029 era errado.
Ausência de prova suportada pelo extrator produz **indecidível**, não
uma correção inversa nem exclusão de companhia.

A prova serializada registra conta, forma, período, perímetro, unidade,
cabeçalhos, anexo, página, linha e coluna. Os valores ficam mascarados.
O consumidor exige esse escopo também: não aceita apenas metadata de conta
junto a rótulo incompatível, célula corrente vazia ou cardinalidade incorreta.

**Custo assumido antes de medir:** notas com unidade só no cabeçalho global,
tabelas mistas Controladora/Consolidado, anos sem datas completas, intervalos
de fluxo não identificados e linhas quebradas ficam indecidíveis. Não foi
criada lista branca por ID nem relaxado G0 para compensar essa perda.

Arquivos:
[fonte_rad_cvm.py](../scripts/fonte_rad_cvm.py),
[adjudicar_escala_rank03b.py](../scripts/adjudicar_escala_rank03b.py),
[gates_painel_pesquisa_rank03b.py](../scripts/gates_painel_pesquisa_rank03b.py).

## 2. CRF-02 — prova ausente não vira aprovação

As quatro entradas — medir, verificar_falsificacoes, g1_provas_depois_de_d e
g1_cego — exigem cobertura integral das chaves corrigidas e datas válidas.
Mapa parcial, vazio ou com None/NaT/data inválida levanta ProvasAusentes antes
de publicar qualquer aprovação. g1_cego sem painel também recusa certificação.

As datas continuam recalculadas pelo manifesto/cadastro, independentemente
do dt_prova produzido pelo construtor. Não se completa o mapa com o campo
que a auditoria existe para conferir.

Controles preservados: painel sem correções funciona; mapa completo e
construtor correto aprova; construtor sabotado e mapa completo continua
reprovando com duas violações na fixture. Não foi demonstrado vazamento
real na execução 3; a falha corrigida era a guarda diante de regressão.

## 3. CRF-03 — histórico separado da versão vigente

O pré-registro passa a rotular localmente os números e o piloto da execução 2
como históricos. A descrição de D no produtor de G1 passou a dizer datas
distintas de disponibilidade das linhas de FCO fornecidas ao construtor;
no painel de pesquisa, essas datas incluem a publicação da prova de escala.

Nenhuma grade de D nem limiar foi escolhido por edição de texto.
Os resultados vigentes e seus hashes estão indicados no §4 abaixo, com as
execuções anteriores preservadas, não apagadas.

## 4. Resultados e procedência

### 4.1 Regra corrigida, cobertura automática nula

| Medição | Execução 3, histórica (v3) | Execução 4b, vigente (v4) |
|---|---:|---:|
| Documentos avaliados | 405 | 405 |
| Decisões por documento | 108 confirmadas, 59 corrigidas, 238 indecidíveis | 405 indecidíveis |
| Correções aplicadas ao painel | 68 (59 diretas + 9 herdadas) | 0 |
| G0.3 — saltos de escala | 68 (0,3026%) | 132 (0,5875%) |
| G0 | Aprovado | **Reprovado** (limite: 0,5%) |
| G1 diagnóstico — observações / companhias | 10.750 / 503 | 10.748 / 502 |
| G1.4 — prova publicada depois de D | 0 | 0 |
| G0.5 proposto, sem força de gate | 56 / 22.088 (0,2535%) | 82 / 22.088 (0,3712%) |

Fonte das decisões e transições:
[readjudicacao.json](../artefatos/correcao_crf_rank03b_2026-09-17/readjudicacao.json).
Fonte do painel/gates:
[resumo_painel.json](../artefatos/correcao_crf_rank03b_2026-09-17/resumo_painel.json)
e [gates_g0_g1.json](../artefatos/painel_pesquisa_rank03b/gates_g0_g1.json).
O G1 foi medido apenas como diagnóstico estrutural, sem calcular o alvo;
sua aprovação não supera a reprovação de G0. Com zero correções, G1.4 = 0
não exercita a proteção temporal de correções reais: essa guarda é coberta
pelas contraprovas sintéticas e pela reprodução histórica P6.

**O extrator reconheceu zero cabeçalhos tabulares elegíveis e zero matches
numéricos no lote real.** Portanto, não se provou que as 68 correções antigas
eram todas erradas, nem que as notas não contêm a informação: a v4 não
conseguiu certificá-la. Corrigir a associação entre conta e célula fechou
a contraprova, mas a implementação não tem cobertura operacional neste lote.
A premissa S5 ficou **sem teste** (zero trechos testados; três não testáveis)
e a herança não foi permitida. Não chamar isso de reprovação empírica de S5.

O CSV vigente contém somente o cabeçalho. As 68 linhas retiradas da versão
ativa são recuperáveis no snapshot da execução 3; nenhuma declaração bruta,
companhia ou observação foi apagada para melhorar o gate. Nenhum limiar foi
afrouxado após esse resultado. Reabrir a extração/adjudicação exige novo
contrato e evidência de cobertura e correção, não restaurar o manifesto v3
como se ele já cumprisse v4.

### 4.2 Identidade dos artefatos

- Digest de conteúdo do painel:
  `6ca635a904f11140fa24c496a11b77e961f841b72f076edd5650212afe12e6cd`.
- SHA-256 do manifesto de correções:
  `13520e61d99f221715a26ade80dc278de15a6b30c93e30a63ed6b6aa753ff07d`.
- [Medições estruturais](../artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json):
  duas reconstruções sem correções e duas consumindo o manifesto vigente
  produziram esse mesmo digest. A igualdade entre os dois braços é esperada:
  o manifesto vigente tem zero correções.
- Os hashes de `cvm.duckdb`, `cvm_treino.duckdb` e do manifesto de aquisição
  permaneceram iguais aos do pin anterior à execução:
  [integridade_painel.json](../artefatos/correcao_crf_rank03b_2026-09-17/integridade_painel.json).

A [conferência estrutural final](../artefatos/correcao_crf_rank03b_2026-09-17/conferencia_estrutura_final.json)
reconstruiu o painel em memória a partir dos 31 ZIPs pinados e comparou as
três tabelas por `EXCEPT ALL` nos dois sentidos: **zero linhas diferentes**
em ativo, FCO acumulado e FCO trimestral. Digest e cadeia G0/G1 conferem.
O [JSON de verificações](../artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json)
está ligado à versão vigente: os hashes do manifesto do painel, gates,
correções e código conferem. O piloto reavaliado pela v4 teve 23/23
indecidíveis; não é amostra nova nem evidência de acurácia.
As verificações também repetem a contraprova P6 sobre o manifesto histórico
da execução 2, sem calcular o alvo. Os três arquivos protegidos continuaram
intactos ao final dessa conferência.

As evidências desta onda vivem em
[artefatos/correcao_crf_rank03b_2026-09-17](../artefatos/correcao_crf_rank03b_2026-09-17/).
A pasta conserva a data de início, mesmo com término em 18/09.

## 5. Auditoria independente e testes

O auditor-conformidade trabalhou somente leitura, em contexto separado.
Encontrou três pontos durante a implementação, corrigidos antes dos gates:

1. O módulo era tomado antes da unicidade e juntava +x e −x. A unicidade
   agora precede a comparação de magnitude.
2. O consumidor precisava verificar também rótulo/células do trecho e recusar
   traço na célula corrente. Traço comparativo continua permitido.
3. O contrato dizia índices iniciando em 1 genericamente. Errata: linha e
   coluna começam em 1; o índice original do anexo começa em 0 e é preservado.

O auditor confirmou 96 controles tabulares independentes, seis controles de
zero/traço do produtor e 12 controles de traço/data invertida no consumidor.
Essas contagens não são somadas às da suíte.
[Registro do instrumento](../artefatos/correcao_crf_rank03b_2026-09-17/auditoria_instrumento.json).

A suíte completa final passou com **2.615 testes, zero falhas, zero erros e
zero skips**, em 557,268 segundos:
[pytest_final.xml](../artefatos/correcao_crf_rank03b_2026-09-17/pytest_final.xml).
São 71 casos novos em relação aos 2.544 da rodada anterior. A primeira
passagem desta onda, antes dos três casos finais de traço, teve 2.612 testes;
não somar execuções sobrepostas.

**Conferência final independente:** sem achado remanescente no escopo CRF.
O auditor conferiu hashes/pins, os mesmos 405 IDs e todas as transições,
vínculo das verificações, XML da suíte e código/saída da comparação exaustiva.
Encontrou um aviso adjacente ainda chamando a v3 de "vigente" no relatório
do lote C; foi rotulado histórico, com link para esta onda, e reconferido.
Pré-registro, MEMORY e lote C estão coerentes com G0 reprovado.
[Parecer final registrado](../artefatos/correcao_crf_rank03b_2026-09-17/auditoria_final.json).

**Limite da independência:** o auditor não repetiu a readjudicação nem a
reconstrução integral; conferiu seus registros, código e vínculos. Não houve
nova validação humana da verdade contábil dos 405 documentos. O parecer
fecha os defeitos de instrumento/documentação, **não aprova a cobertura
operacional**, o alvo ou o treino.

Os testes históricos da v3 conservam suas asserções e agora chamam a regra
explicitamente; não foram enfraquecidos para fazer a v4 passar. Os testes da
regra nova ficam em [test_rank03b_crf.py](../tests/test_rank03b_crf.py).

## 6. Como reproduzir e por que há dois pins

A execução 3, incluindo painel, código, manifesto e provas, foi preservada em
adjudicacao/execucao3/. A primeira passagem da v4 também foi preservada em
adjudicacao/execucao4_pre_auditoria/. A correção de unicidade exigiu repetir
a adjudicação antes de G0, com pin antes_execucao4b.json.

A última mudança foi apenas no consumidor da prova serializada, para barrar
traço corrente; o produtor já o recusava. Em vez de atribuir hashes novos à
execução anterior, fechar_consumidor_e_medir.py compara as ASTs: todo o módulo
deve ser idêntico, exceto a função validadora, e os demais hashes precisam
conferir. Todas as provas e o manifesto são revalidados antes dos gates; os
hashes finais ficam em antes_gates_fecho_consumidor.json.

Comandos, a partir da raiz:

~~~sh
# A readjudicação foi executada uma vez por pin; o script recusa sobrescrevê-lo.
PYTHONPATH=. RAD_SEM_REDE=1 .venv/bin/python artefatos/correcao_crf_rank03b_2026-09-17/executar.py adjudicar --retomada-auditoria
PYTHONPATH=. .venv/bin/python artefatos/correcao_crf_rank03b_2026-09-17/fechar_consumidor_e_medir.py
PYTHONPATH=. .venv/bin/python artefatos/correcao_crf_rank03b_2026-09-17/executar.py verificar --retomada-auditoria
PYTHONPATH=. .venv/bin/python -m scripts.medicoes_estruturais_rank03b
PYTHONPATH=. .venv/bin/python artefatos/correcao_crf_rank03b_2026-09-17/conferir_estado_final.py
~~~

As execuções estruturais bloqueiam _somas_do_rotulo com exceção. Não apagar
pins nem snapshots para repetir a primeira linha: uma nova rodada deve ter
destino/pin próprios. O manifesto anterior de 68 correções não deve voltar ao
consumidor vigente como se carregasse provas v4; para histórico existe a opção
explícita exigir_escopo_v4=False.

## 7. Fronteira de conclusão

Corrigir o instrumento não valida o alvo nem autoriza ML. Após fechar os
achados, o caminho continua: evidência de dados suficiente para os gates,
cinco decisões de política, executor v2 testado, aprovação/congelamento do
protocolo e medições pré-treino. O primeiro desafiante depende de PRONTO PARA
CHALLENGER, não apenas de uma suíte de software verde.
