# Validação da etapa 19 — FCF yield × retorno futuro

**Veredito: INDECIDÍVEL — nem T1 aprova nem reprova com confiança.** Custo de
API: zero (COTAHIST e FCA são dados públicos gratuitos da B3/CVM).

Pré-registro: `resultados/pre_registro_etapa19_fcf_yield_2026-09-08.md`,
escrito **antes** de qualquer medição de desempenho. Artefato:
`artefatos/etapa19/t1_fcf_yield.json`.

> **O pré-registro previu o mecanismo de risco antes de medir.** A seção 2
> nomeou `valor_mercado`/nível de preço como o componente de maior risco em T1,
> pela crítica clássica de que fator-valor é em parte reversão de preço. Foi
> exatamente o componente que ficou mais perto do limiar.

## G0 — integridade de preço: APROVA

| | |
|---|---:|
| Observações antes da quarentena | 12.664 |
| Suspeitas de evento corporativo não ajustado | 4,19% |
| Limiar de reprovação | 5,00% |
| Observações depois da exclusão | 12.133 |

A regra de quarentena (razão `P(t+4)/P(t)` a menos de 2% de `1/N` ou `N` para
`N ∈ {2,3,4,5,10,100}`, ou `\|retorno\| > 300%`) foi congelada no pré-registro
**antes** de rodar — nenhuma exclusão adicional entrou depois de ver o
resultado.

## A amostra final é pequena, e a causa é externa ao candidato

| | |
|---|---:|
| Observações | 1.908 |
| Companhias | 166 |
| Trimestres | 19 |
| Prevalência (quintil superior de retorno) | 0,204 |

**A causa é `composicao_capital` (ações em circulação) só existir a partir de
2020 no dado aberto da CVM.** Sem quantidade de ações não há `valor_mercado`,
e a janela útil caiu de potencialmente 2011–2026 para 2020–2026 — 19
trimestres, não 60.

## T1 — passa no ponto, mas o intervalo não decide

| Componente | Amplitude observada | IC95% (bootstrap por companhia, 2.000 reamostragens) | P(amplitude ≥ 0,15) |
|---|---:|---|---:|
| `valor_mercado` | 0,120 | [0,071; 0,206] | **32%** |
| `ativo_total` | 0,123 | [0,054; 0,215] | 26% |
| `fcf_yield` | 0,113 | [0,060; 0,201] | 29% |
| `p_t` | 0,113 | [0,064; 0,197] | 29% |
| `fcf_ttm` | 0,024 | [0,027; 0,143] | 2% |

Limiar: **0,15**. Todos os cinco componentes passam na leitura pontual — a
**primeira vez** neste projeto que T1 não reprova de cara (compare com C1
0,180–0,247 e Rank 3 0,266/0,229, ambos muito acima do limiar). Mas o
bootstrap por companhia mostra **uma em três chances** de o componente de
maior risco (`valor_mercado`) estar de fato acima de 0,15 na população, dado o
tamanho da amostra.

**Por que não se declara "T1 aprovado".** Tratar uma leitura pontual marginal
como aprovação repetiria o erro que a auditoria de 2026-08-26 já corrigiu uma
vez no C1 — aprovado em exploração, retratado na validação. A régua do
projeto (§3.7) não previu essa zona cinzenta porque nenhum candidato anterior
chegou perto do limiar; os que passavam em algum componente passavam com
folga (`roa` 0,061, `ativo_medio` 0,116).

## Achado metodológico: amplitude é estatística enviesada para cima

`fcf_ttm` observado (0,024) fica **fora** do próprio IC95% pelo lado de baixo
— o intervalo começa em 0,027. Isso não é erro de cálculo: `amplitude =
max − min` sobre cinco estimativas ruidosas tem viés positivo, e o viés cresce
quando a amostra por quintil é pequena (~380 observações por quintil aqui).

**Consequência para trás, registrada porque é verificável:** o viés empurra
toda amplitude para cima, nunca para baixo. C1 (0,180–0,247) e Rank 3
(0,266/0,229) reprovaram por margem muito maior que qualquer viés desse
tamanho poderia produzir a partir de um valor verdadeiro abaixo de 0,15 — as
duas rejeições ficam **mais robustas**, não menos, à luz deste achado.

## O caminho de reabertura examinado e não tomado nesta sessão

A CVM publica **Lucro Básico por Ação** (`cd_conta 3.99.01`) desde 2011,
antes de `composicao_capital`. Em tese, `ações = lucro_atribuído_aos_
controladores / LPA` estenderia a amostra a 2011–2019 sem precisar de fonte
nova.

**Não foi usado.** Inspeção de `3.99.01` mostrou que a CVM aceita o campo com
a precisão que a própria companhia declarou — **2 casas decimais** na maioria
dos arquivamentos. Para companhias com LPA pequeno (muitos milhões de ações
ou margens finas), o valor chega arredondado a `0,00`, e ações derivadas dessa
divisão ficam **indeterminadas ou com erro relativo enorme** exatamente nas
observações onde isso mais atrapalha. É a mesma classe de defeito que
invalidou a rodada A do CAND-04 (§3.11) — trocas de escala silenciosas que só
aparecem no residual. Usar essa derivação para resgatar o T1 atual seria
ajustar a população **depois** de ver um resultado ambíguo, o que o
pré-registro (§3.7) proíbe: população nova é candidato novo.

## Veredito e condição de reabertura

**Estado científico: INDECIDÍVEL.** Não é reprovação (nenhum componente
excedeu 0,15) nem aprovação (a incerteza é grande demais para um limiar
binário). **Decisão de engenharia: NÃO AVANÇAR para T2/T3** com esta amostra —
treinar sobre 1.908 observações depois de mostrar que o próprio T1 é
estatisticamente indeterminado construiria em cima de uma base que este
relatório acabou de qualificar como frágil.

Reabre com qualquer um dos dois:

1. **Amostra maior sem derivação frágil** — outra fonte de ações em
   circulação anterior a 2020 (ex.: FRE/DFP em XBRL bruto, se tiver o dado
   estruturado fora do campo LPA arredondado), pré-registrada como extensão
   antes de rodar.
2. **G0 próprio para a derivação por LPA** — se a via de `3.99.01` for
   retomada, ela precisa de um gate de integridade que descarte observações
   com LPA de baixa precisão (ex.: `\|LPA\| < 0,05`) **antes** de ver o
   resultado de T1, não depois.

Nenhum número deste relatório é herdado por um candidato futuro sob população
diferente — a mesma regra que vale para C1→C2 (§3.7) vale aqui.

## O que isto não conclui

Não conclui que FCF yield seja inútil para prever retorno — é a mesma
ressalva que já vale para os outros negativos do §3.8: ausência de
evidência **decisiva** não é evidência de ausência. Também não invalida o
G0 de integridade de preço, que é reutilizável por qualquer candidato futuro
que use COTAHIST.
