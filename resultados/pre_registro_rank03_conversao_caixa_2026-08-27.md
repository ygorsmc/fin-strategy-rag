# Pré-registro — Rank 3: deterioração de conversão de caixa

**Escrito em 2026-08-27, ANTES de qualquer medição de desempenho.** A única
inspeção feita до este documento foi **estrutural** (quais contas existem, para
quantos emissores, com que cobertura). Nenhuma taxa de evento, AUC, lift ou
comparação com baseline foi calculada antes de congelar o que está aqui.

Isto existe porque a rodada do C1 mostrou o custo de não ter: o `k = 1,25` foi
escolhido depois de ver três valores, e a defesa disso consumiu uma rodada
inteira. Aqui o parâmetro é declarado antes e não se mexe.

---

## 1. O estimando — e o que ele NÃO é

**Pergunta:** *quais companhias hoje lucrativas terão, daqui a um ano, uma
piora material na parcela do lucro que vira caixa?*

**Uso declarado:** fila de **prioridade de leitura** para o analista. Nunca
recomendação, preço-alvo ou sinal de alocação (RN05). No modo público a saída
por emissor continua vedada (RN07); a rota é a mesma do §3.6.

### O que este candidato NÃO é — três confusões a evitar

1. **Não é a anomalia de accrual de Sloan.** Aquela é uma aposta de **retorno**
   e está morta em `becos_sem_saida.md` §A.2, com reabertura condicionada a
   preços *point-in-time*, que continuam ausentes. Aqui não há afirmação sobre
   preço, retorno ou alfa — o desfecho é **contábil**.
2. **Não herda nada do C1.** Alvo diferente, população diferente, normalizador
   diferente. Nenhum número do C1 é transportável.
3. **Não é o accrual como *feature*,** medido e nulo por redundância (+0,0017,
   p = 0,50). Ali o accrual era proxy de capital de giro e entrava num modelo
   de prejuízo. Aqui é **FCO real**, e é o **alvo**.

---

## 2. Definição congelada do alvo

Todas as grandezas em janela móvel de quatro trimestres (`ttm`), escaladas por
ativo médio — a escala padrão da literatura de accruals, escolhida por ser
escala-livre e **não** por ter medido que funciona.

```text
FCO_ttm(t)      = soma do Caixa Líquido das Atividades Operacionais [6.01], t-3..t
lucro_ttm(t)    = soma do lucro líquido consolidado, t-3..t
ativo_medio(t)  = média(ativo_total(t), ativo_total(t-4))

conversao(t)    = FCO_ttm(t)   / ativo_medio(t)
roa(t)          = lucro_ttm(t) / ativo_medio(t)
accrual(t)      = roa(t) - conversao(t)          [quanto do lucro NÃO virou caixa]

Δaccrual(t)     = accrual(t+4) - accrual(t)

alvo(t) = 1  se  Δaccrual(t) está no QUINTIL SUPERIOR
                 da distribuição de Δaccrual DENTRO do trimestre t
```

### Por que quintil transversal e não corte por volatilidade própria

É a lição direta do C1, aplicada de propósito. Um normalizador **da própria
companhia** (`sd8`) é um atributo dela, e por isso pode fabricar um baseline no
nível da companhia — foi exatamente o que reprovou T1 lá. A distribuição
transversal **do trimestre** não é atributo de nenhuma companhia, então não pode
desempenhar esse papel.

Isso não isenta o alvo de T1: `roa`, `conversao`, `accrual` e `ativo_medio`
continuam sendo componentes que definem mecanicamente o rótulo, e **todos os
quatro** vão a T1. A prevalência fica em 20% por construção.

---

## 3. População

| Critério | Valor |
|---|---|
| Universo | não financeiras (`NOT is_banco`) |
| Ativo total | > R$ 1 bilhão em `t` |
| Exigências | `FCO_ttm`, `lucro_ttm` e `ativo_medio` finitos em `t` e `t+4` |
| **Restrição de estado** | **`lucro_ttm(t) > 0`** — a pergunta é sobre lucro que deixa de virar caixa; quem já dá prejuízo não tem lucro para converter |
| Censura | quem não tem `t+4` observável sai, e o número sai publicado |

A restrição de lucro positivo é declarada aqui porque foi a lição do modelo de
prejuízo: escorar quem **já** está mal produz decil superior com 97,1% de
eventos já consumados e nenhuma antecipação.

`is_banco` é heurística de plano de contas e não classificação setorial — mesma
limitação declarada no C1. Não vou usar `SETOR_ATIV` nesta rodada para não
introduzir variável nova entre o pré-registro e a medição.

---

## 4. Disciplina point-in-time — nova, e obrigatória

Esta é a primeira rodada do projeto em que ela é possível (§3.13).

- Um fato de `t` só é elegível como **feature** se o documento que o originou
  tiver `dt_receb <= data_de_decisão`.
- A data de decisão é o **fim do trimestre seguinte a `t`**, que é quando o
  formulário de `t` já foi recebido na esmagadora maioria dos casos (atraso
  mediano de 44 dias no ITR).
- Observação cujo documento ainda não fora recebido na data de decisão **não
  entra**, e a contagem de excluídos por essa regra é publicada.

O rótulo usa `t+4`, que é futuro por definição e não precisa dessa guarda.

---

## 5. Baselines triviais — declarados ANTES, e obrigatórios

A regra durável do §3.8 é *"construa o baseline trivial ANTES do modelo"*. Os
seis candidatos anteriores foram vencidos pelos deles.

| # | Baseline | Por que é o candidato a vencer |
|---|---|---|
| **B0** | `accrual(t)` — o nível corrente | **O mais perigoso.** Accrual reverte à média por construção contábil; quem tem accrual alto hoje tende a cair. Se B0 vencer, o alvo mede reversão mecânica, não deterioração |
| B1 | `−conversao(t)` | Baixa conversão hoje |
| B2 | `roa(t)` | Rentabilidade corrente |
| B3 | `accrual(t) − accrual(t−4)` | Persistência da própria variação |
| B4 | `log(ativo_total)` | Porte |

**Expectativa honesta declarada antes de medir:** B0 é o desfecho mais provável.
A reversão à média do accrual é um dos fatos mais replicados da literatura
contábil, e o alvo — variação de accrual — está mecanicamente ligado ao nível.
Se isso se confirmar, o candidato morre e o registro fica.

---

## 6. Régua decisória — as três barras, congeladas

| Teste | Métrica | Limiar | Aplicado a |
|---|---|---:|---|
| **T1** | amplitude da taxa de evento entre quintis | **< 0,15** | `roa`, `conversao`, `accrual`, `ativo_medio` — **os quatro** |
| **T2** | AUC agregada − AUC intra-companhia | **< 0,12** | escore final |
| **T3** | ganho do modelo sobre o **melhor** baseline | **≥ +0,02 de AUC, com p < 0,05 em teste pareado por fold** | modelo × B0–B4 |

**T1 reprovado encerra o candidato antes de qualquer treino.** T2 favorável não
resgata T1, e T3 favorável não resgata nenhum dos dois.

### Barra de falsificação

> **Se T1 reprovar em qualquer um dos quatro componentes, ou se o melhor
> baseline não for batido por ao menos +0,02 de AUC com p < 0,05, o Rank 3 é
> REJEITADO e não se reformula em voo.**

Mudar escala, horizonte, corte ou população depois de ver o resultado **cria o
Rank 3-B**, com pré-registro novo, e nenhum número desta rodada é herdado.

---

## 7. O que será publicado, independentemente do resultado

Publicação obrigatória mesmo — e principalmente — se o veredito for negativo:

1. `n`, número de companhias, trimestres, eventos e **censurados**;
2. excluídos pela guarda point-in-time;
3. T1 dos quatro componentes, com a tabela de quintis;
4. AUC agregada, AUC intra-companhia e a lacuna;
5. AUC de **cada** baseline, não só do melhor;
6. composição do decil superior — quantos **já** tinham accrual alto em `t`;
7. o veredito, e a linha correspondente em `becos_sem_saida.md`.

## 8. Ordem de execução

1. Escrever `scripts/auditar_rank03_conversao_caixa.py` com as constantes deste
   documento congeladas no código.
2. Rodar **T1 primeiro**, sozinho. Se reprovar, publicar e parar — sem treinar.
3. Só se T1 passar: baselines, depois modelo, depois T2 e T3.
4. Publicar relatório e atualizar `becos_sem_saida.md` e `AGENTS.md`.

Custo de API: **zero**. Tudo roda local sobre o painel.
