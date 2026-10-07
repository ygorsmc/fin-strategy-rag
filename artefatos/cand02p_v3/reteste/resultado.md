# Releitura cega do leitor Claude: resultado (07/10)

Desenho e regras de uso em `declaracao.md`, commitada antes de as releituras
rodarem. Números em `resultado.json`, gerados por
`python -m scripts.cand02p_qc --piloto v3 reteste BMG_4T2018_1T2019 SANTANDER_4T2018_1T2019`.

| Releitura | α ordinal | Acordo exato | Acordo "nota ≥ 1" | Acordo "nota 2" | Notas 2 (1ª → 2ª) |
|---|---:|---:|---:|---:|---:|
| **Sorteada:** BMG 4T2018→1T2019 | **0,810** | 0,850 | 0,883 | 0,950 | 19 → 25 |
| **Dirigida:** SANTANDER 4T2018→1T2019 | **0,735** | 0,825 | 0,883 | 0,942 | 3 → 6 |

## Leitura

- **Nos dois pares o α fica acima de 0,67**, o limiar que o protocolo usa
  para a conferência humana. O leitor repete a própria nota com essa
  confiabilidade.
- **O topo é estável.** No par sorteado, as 19 notas 2 da primeira leitura
  voltaram como nota 2, e todas as discordâncias foram na mesma direção (a
  releitura mais severa). O ruído fica na fronteira entre 0 e 1, que pesa
  pouco no nDCG (ganho 0 contra 1; a nota 2 vale 3).
- **A suspeita sobre o Santander não se confirmou.** Um segundo leitor
  independente também deu poucas notas 2 (6 em 120) e tratou como "conferir"
  a maioria das inversões de sinal que o desenhista achou graves. O padrão é
  do conteúdo do par, não de um leitor leniente. Reler o par para corrigir a
  nota teria imposto a régua do desenhista contra dois leitores que
  concordam entre si.

## O que isto não mede

- **Confiabilidade não é validade.** Dois leitores Claude concordarem não
  diz que um analista humano concordaria. Isso só a conferência humana mede,
  e a do v2 continua pendente.
- **São dois pares de treino, e um deles foi escolhido pelo alerta.** É uma
  estimativa pontual, sem intervalo de confiança.
