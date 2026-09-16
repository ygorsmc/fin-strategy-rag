# Debate dos especialistas — DFC bancária, B-DFC-01J

**Data:** 2026-09-09. **Debate concluído:** pareceres independentes, réplica
mediada e tréplica de fechamento de Ciência de Dados e Finanças.

**Resultado comum: admitir um piloto documental de B-DFC-01J, previsão dos
juros de instrumentos de captação. Não treinar nem declarar um modelo
validado agora.** Recuperação completa do alvo, amostra utilizável, ganho de
ML e contribuição incremental da DFC continuam **INDECIDÍVEIS/não medidos**.

O debate fecha a escolha de uma pergunta e os limites do piloto. **Não é um
pré-registro confirmatório completo nem uma validação empírica.** A
concordância de agentes não substitui teste fora da amostra ou avaliação do
uso pelo analista.

Este relatório dá continuidade à [investigação preliminar](formulacao_bancaria_dfc_2026-09-09.md).
Não renumera o ranking original e não reabre os resultados de C1, Rank 3,
CAND-04 ou AA–H → custo do risco.

## 1. Como o debate foi conduzido

Foram retomados os agentes `bancos_dfc_ciencia` e `bancos_dfc_financas`, cuja
rodada anterior havia sido interrompida por cota. Desta vez ambos concluíram
as três etapas. Cada um recebeu o mesmo conjunto de fatos estruturais e sua
pergunta de domínio. Foram instruídos a não ler a síntese anterior da
coordenação, não consultar o trabalho do outro e não se comunicar diretamente.

Os pareceres iniciais foram recebidos antes de qualquer repasse de objeções
entre especialistas. Na réplica, a coordenação transmitiu objeções
anonimizadas e evidências verificáveis, não rastros privados de raciocínio.
Na tréplica, submeteu a mesma formulação de fechamento a ambos, permitindo
discordância explícita. Eles não receberam resultados de treino ou teste:
esses resultados não foram produzidos.

O isolamento foi **de contexto e procedimento**, não uma barreira física:
os agentes compartilham filesystem, receberam instruções de não consultar
pareceres alheios e mantiveram o contexto de suas próprias pesquisas
anteriores. Não se alega cegamento absoluto ou independência equivalente à
de dois avaliadores humanos.

## 2. A divergência inicial e sua resolução

| Etapa | Ciência de Dados | Finanças |
|---|---|---|
| Parecer inicial | Preferiu encargo contábil total de captação, para projetar uma linha da DRE; admitiu somente preparação | Preferiu juros dos instrumentos de captação, no IFRS do mesmo perímetro; rejeitou o agregado como alvo principal dessa pergunta |
| Réplica | Aceitou restringir a pergunta a juros e retirar o agregado da prioridade; não prometeu recuperação histórica | Reconheceu que o agregado é legítimo para outra finalidade; não foi refutado. Manteve preferência por juros e explicitou hedge/exclusões |
| Tréplica | Confirmou o piloto único 01J, construção aditiva exaustiva e ausência de divergência impeditiva | Confirmou os mesmos limites; esclareceu que instrumentos incluídos no alvo não se confundem com elegibilidade a capital regulatório |

A mudança de alvo ocorreu **antes de qualquer medição de desempenho**.
O encargo agregado não foi descartado porque um modelo perdeu, nem J foi
selecionado por ter um resultado melhor. A escolha foi de interpretação
econômica. Seu custo foi aceito explicitamente: J pode ser mais difícil de
recuperar e resultar em histórico insuficiente.

**Formulação final dos vereditos:** ambos admitem o piloto; nenhum admite
tratar a formulação, o acesso a uma API ou o acordo entre especialistas como
prova de eficácia de ML.

## 3. Contrato financeiro acordado para o piloto

```text
D = data de decisão segundo disponibilidade documental verificável
q(D) = primeiro trimestre fiscal inteiro cujo início seja posterior a D

J(q) = juros reconhecidos por competência em q sobre os instrumentos
       de captação incluídos no contrato, no consolidado societário IFRS
```

Incluídos: depósitos, compromissadas, empréstimos/repasses recebidos e
títulos de dívida emitidos, inclusive subordinados **classificados como
passivos nas demonstrações IFRS**. Não se restringe aos instrumentos
elegíveis a capital regulatório.

Excluídos: distribuições de instrumentos classificados como patrimônio,
juros de arrendamento, componentes atuariais, atualização de provisões e
resultados separados de câmbio, negociação, valor justo e derivativos.
Encargos integrantes da taxa efetiva seguem o reconhecimento contábil, sem
substituição por um cupom hipotético.

**Hedge:** preservar amortizações/reclassificações que integrem
contabilmente os juros da obrigação, quando identificadas pela política e
apresentação do emissor. Não somar derivativos separados por associação
econômica presumida. Mistura não separável com componentes fora do alvo
significa **J não identificado**.

É permitida a **soma exaustiva de parcelas documentadas**. Não é preciso
subtrair pensões que comprovadamente já estejam fora das parcelas somadas.
Mas reunir apenas as linhas disponíveis não prova exaustividade; “outras
despesas de juros” exige composição. Não estimar uma exclusão ausente,
assumir ausência como zero, aplicar percentuais de outro período ou tomar
valores absolutos indiscriminadamente.

J é componente contábil para um cenário de resultado. **Não é** taxa de
captação, custo marginal, caixa pago, custo econômico líquido de todas as
proteções, nem indicador automático de estresse.

### Uma simplificação real em relação à proposta inicial

DRE, balanço, DFC e notas vêm do **mesmo consolidado IFRS**. Se o núcleo não
usar números do IFData, a ponte CVM ↔ conglomerado prudencial BCB **não é
pré-condição desse núcleo**. IFData pode ser conferência ou complemento,
mas qualquer uso de seus saldos exige correspondência de perímetro e tempo.

A quebra de rubricas de 2025 foi comprovada no IFData. Não se deve atribuir
automaticamente a mesma ruptura à série IFRS: suas mudanças de política,
apresentação e perímetro precisam ser examinadas nas próprias fontes.

## 4. Evidências que mudaram o debate

### 4.1 Duas linhas da DFC repetem diferenças de saldos

Finanças identificou e a coordenação conferiu no PDF do BB IFRS 1T2025,
em **R$ mil**:

| Item | Saldo em 31/03/2025 menos saldo em 31/12/2024 | Linha da DFC |
|---|---:|---:|
| Recursos de clientes | `864.972.382 − 873.710.691` | `−8.738.309` |
| Recursos de instituições financeiras | `749.565.355 − 724.024.327` | `25.541.028` |

As duas igualdades foram recalculadas. Nesse documento, essas linhas não
entregam informação numérica adicional à diferença dos saldos. **Não** se
conclui redundância de toda DFC, de todos os períodos ou de outros emissores.
Também não se pode descrevê-las como fluxos de principal já expurgados de
todos os efeitos de competência/câmbio.

Procedência: [PDF original BB](https://api.mziq.com/mzfilemanager/v2/d/5760dff3-15e1-4962-9e81-322a0b3d0bbd/a4033fa2-0a8e-d6ab-9cd1-a044c3ab904b?origin=2),
[cópia local](../corpus/ifrs/raw/bb_ifrs_1T2025.pdf).
DFC: página impressa **6**, página **17 do PDF** (índice zero 16).
Notas: página impressa **41**, página **52 do PDF** (índice zero 51).
SHA-256:
`1f3e89212f0ad62f8cc7a03ebab90ea06510193780f42186bb90e25c1b56c0da`.

O mesmo documento apresenta caixa pago em juros e despesa por competência
em lugares distintos: páginas impressas **7 e 19**, páginas **18 e 30 do
PDF**. A nota 5 discrimina juros de recursos de clientes, de instituições
financeiras, de títulos e “outros”. Há um caminho de extração, **não uma
reconciliação exaustiva já concluída de J**.

### 4.2 A linha IFRS ampla também pode misturar conceitos

O Santander IFRS 1T2025 informa que obrigações de planos de benefício
definido são reconhecidas também em despesas com juros e similares.
Portanto, copiar essa linha da DRE não entrega automaticamente J. A nota
qualitativa não fornece por si o valor a excluir.

Procedência: [PDF original Santander](https://api.mziq.com/mzfilemanager/v2/d/a2595886-9fbb-4339-8a38-71d6ce7c7d36/f6754e68-2d4d-baa9-6490-6251042430e1?origin=2),
[cópia local](../corpus/ifrs/raw/santander_ifrs_1T2025.pdf), página impressa
**14**, página **14 do PDF** (índice zero 13), item sobre fundos de pensão.
SHA-256:
`1bdcfffacc5a276d921e5461f2e27c572c5c47e04ccdab79f7940a8f86533f5f`.
O especialista e a coordenação conferiram o texto no PDF, além do OCR.

### 4.3 Nem g1, nem g1 + h identificam J automaticamente

Os metadados oficiais de 2024 separam `78209/b1` de `78210/b2` (empréstimos
e repasses). Em 2025, `79824/g1` inclui contas de empréstimos, mas exclui
`8119110003`, `8119120000` e `8119130007`; `79829/h` reúne instrumentos de
dívida elegíveis a capital, misturando essas contas com outros ajustes.
A coordenação confirmou as composições por GET, independentemente dos
pareceres. [Metadados 2024-12](https://www3.bcb.gov.br/ifdata/rest/arquivos?nomeArquivo=ifdata/202412/info202412.json),
[metadados 2025-03](https://www3.bcb.gov.br/ifdata/rest/arquivos?nomeArquivo=ifdata_2025_2030//202503/info202503.json).

Logo, g1 sozinho pode omitir juros incluídos no contrato de J, e adicionar
h inteiro pode introduzir efeitos fora dele. A elegibilidade prudencial não
certifica classificação como passivo IFRS. Nenhuma dessas fórmulas foi
adotada como atalho de mapeamento.

### 4.4 Vintages: um caminho verificável, não um problema encerrado

Consulta somente leitura ao painel de treino encontrou **25 arquivamentos**
dos cinco bancos entre 2024T1 e 2025T1; **8 têm múltiplas versões** no
cadastro. Isso não significa que oito tenham J alterado — diferenças de
valores não foram medidas.

Exemplo: BTG, CD_CVM `022616`, ITR de 31/03/2024:

| Versão cadastrada | ID_DOC | Recebimento cadastrado |
|---|---|---|
| 1 | `137097` | 2024-05-13 |
| 2 | `137730` | 2024-05-20 |
| 3 | `143583` | 2024-11-29 |

A coordenação recebeu HTTP 200 e ZIP válido do
[link público da versão 1](https://www.rad.cvm.gov.br/ENETCONSULTA/frmDownloadDocumento.aspx?CodigoInstituicao=1&NumeroSequencialDocumento=137097).
O pacote continha `022616ITR31-03-2024v1.xml`, `DadosDocumento.xlsx`,
`FormularioCadastral.xml`, `FormularioDemonstracaoFinanceiraITR.xml` e PDF
com nome gerado na data da consulta. O servidor informou `text/html`, mas a
assinatura/conteúdo foram reconhecidos como ZIP.

O corpo recebido tinha 4.238.120 bytes e SHA-256
`b03d79bed821bd8850c58e30b057edf545a2cad788b2092fb3466de298db050f`.
Esse hash identifica **aquele download**, não certifica imutabilidade da
fonte. Não foi preservado snapshot desse corpo. As tentativas de obter a
versão 3 e de repetir a inspeção para verificar os XMLs terminaram em timeout.
O conteúdo numérico ainda **não foi certificado como pertencente à versão
solicitada**. Nome de arquivo não basta; PDF gerado hoje não é data de
publicação original.

Há, portanto, fundamento para testar recuperabilidade por ID. Não se
conclui que todas as versões estão recuperadas ou que datas de recepção
transformam o painel atual, que retém valores mais recentes, em PIT.

## 5. O que fica acordado para a avaliação futura

| Elemento | Encaminhamento comum | Ainda falta fechar |
|---|---|---|
| Unidade | Perímetro IFRS × D × trimestre-alvo, sem duplicar previsões | Regra operacional de elegibilidade e D |
| Horizonte | Primeiro trimestre fiscal inteiro posterior a D | Calendário e datas de disponibilidade de todas as peças |
| Vintage do alvo | Primeira divulgação em que J seja identificável; revisões separadas | Recuperação, prova dos valores e política final no pré-registro |
| Saída mínima | Quantis 0,1/0,5/0,9, sem chamá-los de distribuição completa | Procedimento de estimação e calibração |
| Comparação | M1 com DFC contra M0 sem DFC **e** benchmark econômico forte | Implementações e escolha ex ante do benchmark principal |
| Métrica | Perda de quantis; erro em R$ e escala conhecida em D; cobertura/largura/caudas | Pesos, denominador elegível, tolerâncias e benefício mínimo |
| Inferência | Dependência por banco e por tempo; ganhos dentro de cada banco | Dimensionamento e desenho temporal reservado |

**Benchmark econômico:** projetar saldo por fonte × custo esperado × duração,
usando apenas informação disponível em D. Persistência e sazonalidade
continuam referências. Juros e saldos médios realizados no trimestre futuro
não entram como se fossem conhecidos na origem.

M0 deve receber balanço, DRE, notas e juros, incluindo **diferenças de saldos**
que já representem os mesmos números da DFC. M1 usa a mesma família,
população, datas, transformações, orçamento de ajuste e procedimento de
intervalos, acrescentando os componentes DFC identificados. Se esperar a DFC
atrasar a previsão, registrar esse custo operacional, além do teste pareado
na mesma data.

A diferença caixa pago em juros − J só pode virar preditor após reconciliação
de seus escopos. Calendário de cupons, juros a pagar, capitalização e
classificação podem explicá-la; não a rotular automaticamente como estresse.

**Duas vitórias distintas são necessárias:**

- M1 vence benchmark mas empata com M0: não demonstrou contribuição da DFC.
- M1 vence M0 mas perde para o benchmark: não justificou a adoção dessa solução.

O desenho deve exigir evidência nas duas comparações. Ganho em reexpressar
uma subtração omitida de M0 não será anunciado como informação nova da DFC.

### Critérios que não podem ser inventados depois

Materialidade do erro, piora tolerada por banco/regime, calibração, largura
útil de intervalo, cobertura documental e custo de revisão/manutenção
precisam ser definidos antes do teste. A sugestão inicial de **10% foi
retirada**; nenhum percentual ou amostra mínima foi aprovado por conveniência.

O tamanho do teste depende do efeito mínimo relevante e da variabilidade e
dependência das perdas em desenvolvimento. Reamostrar linhas independentes
seria inadequado. Para os cinco bancos fixos, o desenho pode usar blocos
temporais conjuntos; isso não valida generalização para bancos nunca vistos.

Depois de fixada uma barra material, evidência que a sustente pode aprovar o
benefício; limite superior abaixo dela pode rejeitar aquele benefício; intervalo
que atravesse a barra é indecidível. Não confundir ausência de prova com
prova de inexistência de sinal.

T1/T2 anteriores permanecem nos protocolos em que foram definidos. AUC e
amplitude de prevalência não serão aplicadas a J contínuo ou declaradas
aprovadas por analogia. O futuro pré-registro de regressão preservará a
auditoria de baseline mecânico, escala e ganho temporal dentro do emissor.
O [CAND-04](pre_registro_cand04_previsao_fundamentos_2026-08-27.md) é precedente
de desenho contínuo, **não fonte de métricas ou limiares herdados**.

## 6. Próxima tarefa admitida pelos dois especialistas

**Piloto de identificação e recuperabilidade:** cinco emissores do corpus
(`000906`, `001023`, `019348`, `020532`, `022616`) × 2024T1–2025T1, incluindo
documentos e períodos anteriores necessários às derivações.

Cada um dos 25 pacotes é uma unidade de auditoria documental, **não exemplo
supervisionado automaticamente utilizável**. Um pacote pode exigir múltiplos
arquivos, notas e versões. Entregas:

1. Mapa de instrumentos incluídos/excluídos, perímetro e política contábil.
2. Reconciliação exaustiva de J com DRE/notas, sinais, escala e intervalo.
3. Classificação dos componentes DFC: repetição de saldos, fluxos líquidos,
   emissões/liquidações, juros pagos e ajustes sem caixa.
4. Fonte e disponibilidade histórica de cada valor e operando derivado.
5. Inventário integral: identificado, não identificado ou conflitante, com
   motivo; só depois contar a interseção utilizável.

Se o conceito não puder ser identificado ou a interseção for insuficiente,
parar nessa formulação. Não substituir por agregado para salvar amostra,
preencher ausência com zero, excluir casos pelo desempenho ou afirmar que
um contrato falhou porque o fenômeno econômico é impossível.

**Não executado nesta rodada:** piloto completo dos 25 pacotes, construção
de série J, baselines preditivos, pré-registro final, treino, backtest ou estudo
com analista. O que foi executado foram o debate, verificações pontuais de
fonte e auditoria de metadados descritas acima.

## 7. Reprodução e bibliografia de método

Os hashes dos dois PDFs foram conferidos contra o manifesto IFRS. O painel
permanece com SHA-256
`c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b`.
Consulta que reproduz 25/8 e o exemplo de versões, com DuckDB somente leitura:

```sql
WITH grupos AS (
  SELECT cd_cvm, conjunto, dt_refer, count(*) AS n
  FROM documentos
  WHERE cd_cvm IN ('000906','001023','019348','020532','022616')
    AND dt_refer BETWEEN DATE '2024-03-31' AND DATE '2025-03-31'
  GROUP BY 1, 2, 3
)
SELECT count(*) AS arquivamentos,
       count(*) FILTER (WHERE n > 1) AS multiversao
FROM grupos;

SELECT versao, id_doc, dt_receb, link_doc
FROM documentos
WHERE cd_cvm = '022616' AND dt_refer = DATE '2024-03-31'
ORDER BY versao;
```

Conferência dos PDFs, sem OCR pago ou alteração do cache:

```bash
pdftotext -f 17 -l 17 -layout corpus/ifrs/raw/bb_ifrs_1T2025.pdf -
pdftotext -f 52 -l 52 -layout corpus/ifrs/raw/bb_ifrs_1T2025.pdf -
pdftotext -f 14 -l 14 -layout corpus/ifrs/raw/santander_ifrs_1T2025.pdf -
```

Referências primárias usadas para fundamentar o desenho, não para afirmar
que nosso modelo funciona:

- [CPC 03](https://conteudo.cvm.gov.br/export/sites/cvm/menu/regulados/normascontabeis/cpc/CPC_03_R2_rev_13.pdf),
  §§15, 18–24 e 31–33: distinções entre fluxos bancários, apresentação líquida
  e juros pagos/reconhecidos.
- [Alencar, BCB Working Paper 235](https://www.bcb.gov.br/content/publicacoes/WorkingPaperSeries/wps235.pdf):
  determinantes das taxas bancárias brasileiras; sustenta controles
  macroeconômicos e de composição, não ganho de DFC.
- [Drechsler, Savov e Schnabl, The Deposits Channel of Monetary Policy](https://www.nber.org/papers/w22152):
  motivação para heterogeneidade de depósitos e resposta aos juros; evidência
  estrangeira não valida automaticamente o caso brasileiro.
- [Dias e Scott, Monetary Policy and Bank Funding Costs](https://www.federalreserve.gov/econres/feds/monetary-policy-and-bank-funding-costs.htm):
  ciclos de juros e fontes de financiamento como elementos do benchmark.
- [Gneiting e Raftery, 2007](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf):
  regras de pontuação para previsões probabilísticas; cobertura isolada não
  basta para avaliar intervalos.

Nesta rodada foram alterados somente documentos de pesquisa/handoff. Não
houve commit, mudança em produto, painel, dependências ou testes; nenhum
acesso ao `holdout_2T2026` ou chamada paga de OCR/LLM pela coordenação.
Consultas e identidades aritméticas foram executadas; a suíte de testes não
foi reexecutada e não é apresentada como validação de ML.
