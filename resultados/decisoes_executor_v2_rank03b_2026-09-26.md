# Decisões restantes e passagem para o executor v2

Data: 2026-09-26. **Propostas, não aprovação do responsável.** Este documento
organiza o trabalho restante; não substitui nem congela o
[rascunho v2](pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md).

## O que já pode ser resolvido sem escolher política

A correção de sinal, a guarda B4 e o diagnóstico sintético de ativo
arredondado têm contrato próprio em
[contratos_pendencias_geom1_rank03b_2026-09-26.md](contratos_pendencias_geom1_rank03b_2026-09-26.md).
Nada disso corrige uma linha do painel ou aprova um gate. O diagnóstico
arredondado não está conectado à busca real.

## O1: decisão técnica e autorização pendente

**O1.3 não cobre explicitamente piso/teto:** autoriza leitura individual de
FCO para igualdade entre fontes do mesmo período. Mesmo que a finalidade
seja proteger a saída, arredondar é operação adicional. A exceção protetiva
abaixo é a recomendação, mas exige aprovação do responsável; não se registra
como aprovada por ter sido sugerida por um agente.

Texto proposto para um adendo, ainda não vigente:

> Permite-se, exclusivamente no verificador de não publicação, obter módulo,
> piso e teto das formas do FCO já lidas para igualdade autorizada. Esses
> resultados permanecem locais à verificação, não são registrados, retornados
> como evidência de escala, usados em busca de correspondências, agregados,
> usados para selecionar documentos ou fornecidos a modelo. Só podem causar
> recusa de publicação. A autorização não abrange rótulos, janelas futuras,
> métricas de modelo nem busca de FCO arredondado.

Se aprovada: criar adendo datado com a decisão, fixá-lo por hash nas duas
entradas da busca, testar seu vínculo antes de ler pacotes e reconferir
somente as saídas autorizadas. O critério de equivalência da proteção pode
ser mais conservador que o da busca; piso/teto bloqueiam ambos os lados,
enquanto a busca arredondada escolhe um único inteiro sob regra explícita.

Se recusada: separar os valores de FCO dos demais no verificador, conservar
as magnitudes exatas permitidas e documentar/testar a redução de cobertura.
Não remover piso/teto globalmente nem mascarar essa redução. Nesta onda o
verificador foi preservado e **não houve busca ou reconferência com FCO real**.

**FCO arredondado é outra decisão.** O adendo protetivo acima não o libera.
Uma futura busca precisará fixar fonte, período, conta, perímetro, unidade,
regra de arredondamento, saídas permitidas e testes negativos antes de ler
os valores. A função nova de ativo não deve ser reaproveitada sobre FCO por
conveniência.

## Seis escolhas: o que muda e o que não pode ser alegado

| Decisão do v2 | Proposta existente e encaminhamento | Limite / custo |
|---|---|---|
| §3.2 — seguradoras | Excluir também o plano de seguros; recomendação mantida | Muda a população. Não escolher depois de ver desempenho por setor. |
| §5.1 — G0.1 | Unicidade do FCO, sem duplicar MD e MI; permitir derivação entre métodos com linhagem e demais invariantes | Não dispensa mesma conta, perímetro, exercício e períodos compatíveis. Troca de método não é, sozinha, prova de comparabilidade de qualquer linha. |
| §5.5 — G0.5 | Tornar a heterogeneidade não adjudicada uma verificação decisiva; a proposta de corte é ≤0,5% | O corte é política nova, não validado por G0.3. A medição estrutural já foi vista. Não vender esse número como garantia de ausência de erro nem ignorar erro comprovado por caber nele. |
| §6.1 — datas D | Usar disponibilidade das linhas de FCO e publicar perdas; recomendação mantida | Não representa todas as recepções de balanço. Provas tardias adiam disponibilidade. |
| §8.1 — suporte de T2 | O rascunho propõe manter sem piso novo e divulgar suporte | Permite medir com um só emissor com ambos os rótulos; não comprova generalização. O responsável deve aceitar esse alcance restrito ou exigir contrato de suficiência antes de medir. Não inventar um piso depois de observar o resultado. |
| §12-bis — alcance da prova | Opção B: alteração de FCO exige prova que alcance FCO; recomendação mantida | Hoje nenhum dos dois documentos GEOM satisfaz o conjunto de provas. Saldo de caixa não prova sozinho escala do fluxo. |

As recomendações mais firmes são exclusão das seguradoras, unicidade com
linhagem, grade de disponibilidade e opção B. **G0.5 e suporte de T2 têm
escolhas de risco explícitas**, não respostas científicas automáticas. O
pedido de aprovação conjunta das propostas é apenas uma opção de resposta:
não implica que o pacote foi aprovado nem que todos os critérios têm a mesma
força de evidência.

## Executor v2 — trabalho delimitado depois das decisões

O §6 do rascunho determina que ele seja escrito **depois** das escolhas e
testado **antes** do congelamento. Não há executor v2 novo nesta onda.

1. Registrar escolhas e contrato do executor. Fixar painel, manifesto,
   correções, regras de dados, código e declaração de exposições já vistas
   (§11). O registro precisa distinguir aprovação de regras, implementação
   sintética e autorização da medição real.
2. Implementar entrada própria sobre o painel de pesquisa; **não chamar**
   `auditar_rank03b_consumo_operacional.executar()`, que monta o rótulo antes
   de G1. Reutilizar funções verificadas, sem duplicar suas regras em cópias.
3. Aplicar universo decidido, validar manifesto e linhagem, conferir o digest
   e medir G0, incluindo a política adotada para G0.1/G0.5. Se falhar, parar
   sem construir rótulo. Não excluir os saltos suspeitos para fazer passar.
4. Construir a amostra com `calcular_rotulo=False`, medir G1 e a disponibilidade
   das provas, recusar amostra vazia. Se falhar, parar antes do desfecho.
5. Só com ambos aprovados, construir a versão com rótulo e conferir identidade
   das chaves (companhia, D), unicidade e linhagem das observações. Mesmas
   chaves não bastam se os insumos tiverem mudado entre as duas passagens.
6. Aplicar T1 com a partição congelada e T2 com B1 em sentido negativo e a
   regra de suporte aprovada. Não trocar score, limiares, amostra ou ordem
   após observar os resultados. Estados incompletos/indecidíveis não aprovam.
7. Medir os baselines conforme a sequência congelada; exigir todas as métricas
   e intervalos específicos de cada baseline (§9). Falha de suporte ou
   exceção computacional não pode virar sucesso silencioso.
8. Gravar execução identificada por hashes, parâmetros, decisões, inventário
   de perdas e motivos de interrupção; não sobrescrever rodadas anteriores.
   `PRONTO PARA CHALLENGER` exige a conjunção do §9, não somente que o script
   terminou. Não treinar modelo dentro deste executor.

Contraprovas mínimas: decisões ausentes, pré-registro rascunho, hash alterado,
amostra vazia, cada gate reprovado, espião que falha se a função do rótulo for
chamada cedo, prova publicada após D, amostra/linhagem divergente entre
passagens, schema por conta não autorizado, empate/escore constante, suporte
insuficiente, baseline incompleto, exceção de bootstrap e reexecução em
destino existente. Tudo sintético; depois, auditor-conformidade independente.

## Bloqueio material que a lista de software não remove

Mesmo depois dessas decisões e de implementar o executor, continua sendo
preciso resolver os defeitos de escala que reprovam G0 com evidência que
alcance as contas exigidas. O estado registrado no v2 (§11.3) é **132 saltos,
zero correções v4**; não foi reestimado nesta onda. O alcance de duas
candidatas não basta para superar esse bloqueio. Não há autorização para
treinar nem evidência de que um modelo já se tornou viável.
