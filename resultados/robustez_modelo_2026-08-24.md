# Etapa 10 — os apontamentos do revisor, medidos um a um

**Data:** 2026-08-24 · **Custo de API:** zero · **Artefato:**
`artefatos/modelo/robustez.json` · **Reprodução:**
`python -m scripts.experimentos_robustez --painel artefatos/cvm_treino.duckdb`

Segunda onda da etapa 10. Cada bloco aqui existe porque uma crítica ao módulo
ficou sem resposta empírica. Tudo roda sob o **mesmo walk-forward** (um fold por
trimestre, treino sempre no passado), para que as comparações sejam pareadas.

## Placar

| # | Apontamento | Veredito |
|---|---|---|
| 1 | Falta purga/embargo no walk-forward | **Procedente.** Corrigido; número publicado muda 0,8813 → **0,8797** |
| 2 | Falta controle setorial | **Improcedente na prática.** +0,0005, p = 0,19 — rejeitado |
| 3 | Calibração medida, não corrigida | **Tentada e não melhora.** Isotônica ainda PIORA a ordenação |
| 4 | Só uma biblioteca de boosting | **Empate.** LightGBM ±0,0004, p = 0,66 |
| 5 | Features escolhidas nos folds reportados | **Decisão confirmada** em folds não vistos (+0,0072, p = 4e-06) |
| 6 | AUC condicional era script solto | Promovida a função, com guarda de amostra rasa |

**Dois procedentes, um confirmado, três resultados nulos.** O padrão da etapa
10 se repete: quase toda melhoria plausível medida com poder estatístico de
verdade dá zero, e o que sobrevive é pouco.

---

## 1. Purga / embargo — procedente, corrigido

Separar por trimestre não basta quando o rótulo olha para frente: uma linha de
treino em `o` tem rótulo cobrindo `o+1 .. o+n`, e com **n = 2** isso alcança o
trimestre de **teste**. O treino continha o desfecho do período avaliado — é o
que López de Prado chama de necessidade de *purging*, e o desenho não tinha.

| Alvo | Sem purga | Com purga | Diferença | Treino médio |
|---|---|---|---|---|
| 1 trimestre | 0,8660 | 0,8660 | **exatamente 0** | 11.793 → 11.793 |
| 2 consecutivos | 0,8813 | **0,8797** | −0,0016, p = 0,026 | 11.387 → 11.024 |

**A linha do alvo de 1 trimestre é a contraprova, e ela importa.** Ali o rótulo
alcança a validação e para; a purga não tem o que remover, e não removeu — os
conjuntos de treino ficaram idênticos, linha a linha. Uma purga que jogasse
amostra fora nesse caso estaria custando dados de graça.

O efeito no alvo persistente é **detectável e desprezível**: −0,0016. Mas o
número publicado estava inflado e agora não está. `dividir_walk_forward` purga
por padrão, e `tests/test_modelo.py::TestPurga` verifica a invariante
diretamente — nenhuma linha de treino pode ter rótulo alcançando o teste, para
alvos de 1, 2 e 3 trimestres.

---

## 2. Controle setorial — a hipótese era boa e não se confirmou

**De onde veio.** Uma leitura descritiva do painel mostrou que porte funciona
como interruptor em instituição financeira e quase não importa nas demais:

| Porte | Instituição financeira | Demais |
|---|---|---|
| ≥ R$ 500 bi | **0,6%** | 21,0% |
| R$ 100–500 bi | 12,3% | 23,2% |
| R$ 10–100 bi | 9,7% | 22,5% |
| < R$ 10 bi | **29,6%** | 37,5% |

Isso é uma **interação porte × setor** — e o modelo não tinha setor. Tinha
`alavancagem`, que separa os dois grupos por acidente (mediana 8,8 contra 2,5).
A hipótese: dar o setor explicitamente deveria destravar a interação.

**Não destravou.**

| Alvo | Com `instituicao_financeira` | Sem | Diferença |
|---|---|---|---|
| 1 trimestre | 0,8668 | 0,8660 | +0,0007, p = 0,014 |
| 2 consecutivos | 0,8802 | 0,8797 | +0,0005, **p = 0,19** |

No alvo publicado a diferença **não é significativa**. No de um trimestre é
significativa e vale 0,0007 — significância sem relevância, que 47 folds
detectam e nenhum usuário sente. A feature **não foi promovida** a
`COLUNAS_FEATURES`; segue calculada no painel para auditoria.

**Por que a hipótese falhou.** O modelo já separava os dois grupos sem que
ninguém lhe dissesse o setor — `alavancagem` faz isso por acidente:

| | n | Mediana de ativo/PL | IQR |
|---|---|---|---|
| Instituição financeira | 866 | **8,8** | 5,8 – 12,2 |
| Demais | 19.936 | **2,5** | 1,8 – 3,7 |

Distribuições quase disjuntas: uma árvore separa razoavelmente sem a flag.

E o porte, que seria o outro lado da interação, o modelo **quase não usa**.
Importância por permutação (alvo de 2 trimestres, fold 3T2025, 15 repetições):

| Feature | Δ AUC ao permutar |
|---|---|
| `taxa_prejuizos_4t` | **+0,1480** |
| `taxa_prejuizos_ate_t` | +0,0172 |
| `roa_trimestral` | +0,0064 |
| `roe_trimestral` | +0,0059 |
| **`log_ativo_total`** | **+0,0023** |
| `alavancagem` | +0,0010 |

O modelo é, na prática, **"com que frequência esta companhia deu prejuízo nos
últimos 4 trimestres"**, temperado com rentabilidade. Porte pesa 64× menos que
o histórico recente. A interação porte × setor que a tabela descritiva sugere é
real no dado e **irrelevante para a predição**, porque o histórico recente já
carrega a informação.

**Ressalva sobre permutação, que não é detalhe.** Ela mede o quanto *este*
modelo já ajustado depende da feature; a **ablação** mede informação
insubstituível, porque retreina sem ela. Sob colinearidade as duas discordam de
propósito — as sazonais aparecem baixas aqui e valem +0,0102 (p = 7e-09) na
ablação de grupo, porque quando `taxa_prejuizos_4t` some de verdade,
`taxa_prejuizos_ate_t` a substitui parcialmente. As duas medições não se
contradizem; medem coisas diferentes, e ler só uma leva a conclusão errada.
Esta é de um fold só.

---

## 3. Calibração — tentada, e a isotônica machuca

O calibrador é ajustado no trimestre de **validação** (que já é conjunto
reservado, de onde sai o limiar) e medido no de teste. Ajustá-lo por validação
cruzada interna sobre o treino misturaria trimestres e devolveria um calibrador
de época errada.

| Alvo | Método | Brier | Erro de calibração | AUC |
|---|---|---|---|---|
| 1 trimestre | cru | 0,1402 | **0,0670** | 0,8660 |
| | isotônica | 0,1459 | 0,0787 (+0,0117, p = 0,008) | 0,8614 (**−0,0047**, p = 4e-14) |
| | Platt | 0,1432 | 0,0762 (+0,0093, p = 0,022) | 0,8660 (idêntico) |
| 2 consecutivos | cru | 0,1158 | **0,0576** | 0,8797 |
| | isotônica | 0,1176 | 0,0546 (−0,0030, p = 0,57) | 0,8734 (**−0,0062**, p = 1e-13) |
| | Platt | 0,1154 | 0,0551 (−0,0025, p = 0,36) | 0,8797 (idêntico) |

**Nenhuma recalibração melhora o erro de forma significativa, e a isotônica
sempre piora a ordenação.** A explicação é o tamanho do conjunto de ajuste: o
calibrador vê um trimestre só (~400 linhas), a função em degraus da isotônica
se ajusta ao ruído daquele trimestre e destrói granularidade do escore — que é
exatamente o que o AUC mede.

**Contraprova embutida no arnês:** o Platt é monotônico, então o AUC dele
**tem** de ser idêntico ao do escore cru. Deu `+0,0000` em todos os 93 folds
das duas tabelas. Se tivesse dado qualquer outra coisa, o erro estaria na
medição, não no método.

A ressalva "calibração medida, não corrigida" sai do relatório e é substituída
por: **corrigir foi tentado e não vale a pena com um trimestre de ajuste.**

---

## 4. LightGBM — empate, como esperado, agora medido

| Alvo | LightGBM | `HistGradientBoosting` | Diferença |
|---|---|---|---|
| 1 trimestre | 0,8660 | 0,8660 | −0,0001, p = 0,87 |
| 2 consecutivos | 0,8801 | 0,8797 | +0,0004, p = 0,66 |

Com boosting e logística já empatados e a busca de hiperparâmetros rendendo
zero fora dos folds de ajuste, a expectativa de ganho por troca de biblioteca
era baixa. **O teto é da tarefa, não da implementação.** A ressalva sai; o
`lightgbm` fica em `requirements-modelo.txt` como o que é — um controle, não
uma dependência do caminho publicado.

---

## 5. As features foram escolhidas nos folds reportados — decisão confirmada

Esta era a crítica mais séria de método. As sazonais foram mantidas e as do
O-score removidas **medindo os 47 folds**, e o resultado foi publicado **nesses
mesmos 47**. É a mesma circularidade que a busca de hiperparâmetros teve — e lá
a conferência em folds reservados mostrou que o ganho aparente era ruído puro.

Reconferindo a decisão sobre o grupo sazonal nos folds que ela não viu:

| Alvo | Folds da decisão (20) | **Folds não vistos** |
|---|---|---|
| 1 trimestre | +0,0119 (p = 2e-04) | **+0,0089** (p = 1,1e-05, 24/27) |
| 2 consecutivos | +0,0153 (p = 2e-05) | **+0,0072** (p = 4,1e-06, 23/26) |

**A decisão sobrevive.** O ganho encolhe — 0,0119 → 0,0089 e 0,0153 → 0,0072,
que é o otimismo de seleção aparecendo — mas continua grande e altamente
significativo nos folds reservados.

E o contraste com os hiperparâmetros é o que valida o método: **a mesma
conferência classificou uma decisão como real e a outra como ruído.** Se ela
aprovasse tudo, não estaria medindo nada.

---

## 6. Desempenho por recorte — e um defeito meu, corrigido

A AUC condicional ao estado virou função (`desempenho_por_estado`,
`desempenho_por_recorte`) em vez de script descartável, e é a melhor evidência
de utilidade do módulo:

| Recorte (alvo 2 trimestres) | n | Positivos | Taxa-base | AUC | Lift@10% |
|---|---|---|---|---|---|
| Painel inteiro | 16.919 | 3.802 | 22,5% | 0,876 | 3,32 |
| **Lucrativa hoje** | 11.317 | 914 | **8,1%** | **0,831** | **4,35** |
| Já em prejuízo hoje | 5.602 | 2.888 | 51,6% | 0,722 | 1,46 |
| ~~Instituições financeiras~~ | ~~535~~ | ~~35~~ | ~~6,5%~~ | ~~0,883~~ | ~~5,10~~ |
| ~~— abaixo de R$ 100 bi~~ | ~~346~~ | ~~30~~ | ~~8,7%~~ | ~~0,832~~ | ~~4,28~~ |
| Não financeiras | 16.384 | 3.767 | 23,0% | 0,875 | 3,27 |

> **RETRATAÇÃO (2026-08-25) — as duas linhas riscadas não valem.** O recorte
> usa `companhias.is_banco`, que significa "usa plano de contas de instituição
> financeira", não "é banco". Entre as 41 entidades marcadas estão GP
> Investments (private equity), Sul 116 (em liquidação), CELGPAR (holding) e
> PPLA — e **42 dos 49 eventos positivos (85,7%) vêm delas**. Limpo o universo
> sobram **7 eventos**, abaixo do mínimo de 20 que este próprio documento
> estabelece duas seções adiante; por Hanley & McNeil (1982) essa amostra não
> distingue AUC 0,70 de 0,50. E entre os bancos de verdade fora da faixa do
> topo, porte não se correlaciona com prejuízo (ρ = −0,046, p = 0,83).
> **Reproduzível:** `python -m scripts.auditar_recorte_is_banco` →
> `artefatos/modelo/auditoria_is_banco.json`. Detalhe em
> `resultados/debate_modelo_2026-08-25.md`.
> **A linha "Lucrativa hoje" NÃO é afetada** — ela não depende de setor, e é
> ela que sustenta a escoragem do trimestre corrente entregue em 2026-08-25.

Entre companhias **hoje lucrativas** a regra de persistência prevê constante
zero — discriminação nenhuma. O modelo ordena ali com lift 4,35. É a resposta
técnica a "isso não é persistência disfarçada?": **não, e o ganho está
concentrado no caso em que a regra simples é muda.**

**O defeito que eu próprio cometi, e a correção.** A primeira versão da tabela
publicava `instituições financeiras ≥ R$ 100 bi` com **AUC 0,971** — sobre
**5 eventos positivos**. Número de aparência esplêndida e conteúdo nenhum:
bastam dois pares trocados para desabar. Era exatamente a crítica que este
documento faz aos outros. A função passou a exigir **20 eventos da classe
minoritária** (`minimo_positivos`), não só tamanho de amostra, e o recorte sai
marcado como insuficiente em vez de marcado como excelente. As duas linhas que
a guarda derrubou estão no artefato com o motivo.

---

---

## 7. Auditoria de conformidade — o que ela pegou

O `auditor-conformidade` rodou sobre esta onda e encontrou **quatro defeitos
reais**, três deles no código novo. Ficam registrados porque a alternativa —
corrigir em silêncio — é o oposto do que este projeto mede.

| Defeito | Onde | Gravidade |
|---|---|---|
| A rota prospectiva devolvia `resposta`; o histórico do Streamlit lê `conteudo` → **`KeyError` no rerun, página de exceção** | `app_streamlit.py` | **A recusa da RN07 nunca chegava à tela** |
| Trimestres ordenados como **texto**: `1T2026` vinha antes de `2T2025`, e a janela publicada saía errada | `app_streamlit.py` | Itaú aparecia como "1T2025–4T2025" com dado até 2T2026 |
| Contagem de prejuízos somava trimestre **derivado** (420 de 435 linhas do 4T2025) e apresentava o total como arquivado | `app_streamlit.py` + `src/projecao.py` | **Violação da RN10** |
| "O modelo colocou 41 de 413 no decil superior" é **sempre 10% por definição** — tautologia publicada como medição, e ainda tornava `_agregado_seguro` inalcançável | `scripts/gerar_panorama_modelo.py` | Guarda anti-vazamento era ilusória |

**Correções, todas com teste:**

- O item do histórico agora preenche `conteudo`, e `TestAchadosDaAuditoria`
  verifica o contrato lendo a AST do `app_streamlit.py` — se o laço de
  renderização mudar de chave, o teste cai.
- `ordinal_trimestre` **saiu de `src/modelo/`** e passou a morar em
  `src/normalizacao.py`. O motivo é a própria RN07: quem responde ao usuário
  precisa ordenar trimestre e não pode importar o modelo. Duplicar a regra
  seria pior — foi a duplicação ausente que produziu o defeito.
- A contagem de prejuízos vem separada por `origem`, e o texto declara os
  derivados citando a RN10.
- O panorama publica contagem acima de um **limiar absoluto** (o dobro da
  taxa-base): 80 de 413 no 3T2025, número que varia com o trimestre.
  `_agregado_seguro` passou a testar essa contagem, que **pode** de fato bater
  em 0 ou no total — a guarda ficou alcançável.

Duas lacunas de reprodutibilidade também foram fechadas: a importância por
permutação e as medianas de alavancagem citadas na seção 2 vinham de script
descartável e agora são produzidas por `scripts/experimentos_robustez.py`
(`medir_importancia_permutacao`, `medir_separacao_setorial`). É a segunda vez
que essa classe de lacuna aparece no projeto; a regra é que número publicado
sai de código versionado.

**O que a auditoria confirmou conforme:** isolamento de import da RN07 (nenhum
dos dez módulos do caminho interativo importa `src.modelo`, incluindo
`src/projecao.py`); `escores_por_companhia.json` fora do Git e ausente dos
artefatos versionados; nenhum segredo ou PII no diff; RN05 preservada (o
guardrail roda **antes** da rota); RN11 preservada (desambiguação por `CD_CVM`,
sem escolha automática); e a invariante da purga verificada diretamente, não
inferida do AUC.

---

## O que continua em aberto

1. **O viés de sobrevivência não tem correção** com os dados disponíveis: a
   observação final antes do desaparecimento nunca recebe rótulo, então os
   desfechos mais severos ficam estruturalmente fora. Resultado conservador
   para eventos extremos.
2. **O alvo persistente depende mais do 4T derivado** (50,8% dos rótulos).
   Mostrou-se robusto no recorte sem derivados, mas com metade dos folds.
3. **A calibração continua imperfeita** (erro 0,058) e agora sabe-se que
   recalibrar num trimestre não resolve. Um calibrador ajustado em janela
   móvel de vários trimestres não foi tentado.
4. **`setor` fino** (via `cad_cia_aberta.csv` da CVM) não foi testado. Dado que
   a flag binária rendeu +0,0005, a expectativa é baixa — mas é expectativa.
5. **A RN07 pública mora só na camada de UI.** `responder_pergunta_livre` e
   `src/agentes.py::responder_com_guardrails` não chamam o detector: a rota
   existe apenas no ramo de `app_streamlit.py`, que devolve `None` — e cai na
   geração ao vivo — se o panorama ou o painel faltarem, se nenhuma companhia
   for resolvida, ou em qualquer exceção. O próprio app enuncia o princípio
   contrário para a RN05 ("a guarda que importa é a que mora na função que
   fala com o provedor"). **Levar o detector para dentro de
   `responder_pergunta_livre` é a correção pendente**, e ela é maior que uma
   linha porque exige resolver entidade lá dentro.
6. **O detector é regex de vocabulário estreito.** "Como estará o lucro do
   Itaú em 2027?", "O resultado do Bradesco tende a piorar?" e "Qual o outlook
   de resultado do BB?" não casam com nenhum dos seis padrões. O falso bloqueio
   é 0/55, mas a cobertura do lado positivo não foi medida contra um conjunto
   adversarial próprio — só contra os sete exemplos do teste. Um conjunto de
   perguntas prospectivas parafraseadas, na linha do `ataques.csv` da etapa 14,
   é o caminho e não foi feito.
