# MEMORY.md

> Memória de trabalho entre sessões. Leia no início de toda tarefa; ao final,
> **sobrescreva** o que ficou desatualizado. Não é changelog — é handoff.
> Regras de uso em [AGENTS.md](AGENTS.md#10-memória-entre-sessões--memorymd).
>
> Histórico detalhado de investigações já resolvidas (RN02, chunking,
> propagação de unidade, gates) não vive mais aqui — está fechado em
> `AGENTS.md` (§3) e recuperável via `git log -p MEMORY.md` se precisar do
> raciocínio completo. Esta versão foi enxugada em 2026-08-23 por exceder a
> disciplina de "poucas dezenas de linhas" do §10.

## Estado atual

- Etapa ativa (plano §7): **13 (Langfuse + DeepEval)** — concordância
  juiz × humano medida (0,867, `resultados/concordancia_juiz_humano_2026-08-23.md`);
  groundedness da rodada vigente ainda não auditada.
- Última etapa concluída: **10 (modelo preditivo)**, 2026-08-23 —
  `resultados/modelo_preditivo_2026-08-23.md`, custo zero. Antes dela, a 4
  (chunking de tabela, AGENTS.md §3.4).
- Suíte: **1.564** casos, sem skip (exige `requirements-modelo.txt`).
- Rodada congelada vigente: fingerprint `5b9b142d`
  (`20260823T131515Z-4ad67021f6`), números publicados no README. Status:
  `auditoria_manual_pendente`.
- Gasto acumulado nos logs versionados: **USD 2,87** de um teto de 25 (RNF03).

## Decisões e bloqueios em aberto

- **McNemar da camada de agentes (etapa 12) bloqueado por leitura humana, não
  por código.** Braço C já reapurado (2026-08-21, 0/15 mudou). Faltam 10 dos
  15 gabaritos de `conjunto_padrao/conjunto_agentes.csv` com dupla leitura
  independente — tarefa do Ygor, página-fonte em `fonte_gabarito`.
- **Pedido de afrouxar os qualificadores de métrica no corretor de exatidão
  foi recusado com evidência**, não esquecido: no Itaú 1T2026 coexistem
  `11.636` ("atribuível a controladores") e `11.875` ("controladores e não
  controladores") — sem exigir o qualificador o corretor aceitaria a linha
  errada. Caminho certo, não feito: coluna nova no gabarito com as redações
  aceitas por pergunta (regra "acrescente coluna, nunca linha") — decisão do
  Ygor.
- **Exatidão comparativa 0,000 é TETO ESTRUTURAL, não regressão** (apurado
  2026-08-23, custo zero — `resultados/teto_comparativas_2026-08-23.md`). O
  top-5 é global e 5 das 10 comparativas pedem 5 bancos → 1 chunk por banco.
  Teto real (todos os valores presentes): E1 1/10 · E2 2/10 · E3 2/10 ·
  E4 5/10. Recuperação de banco está 40/40 correta. **Corrigi o README, que eu
  próprio havia escrito chamando isso de regressão.** Resolver exige orçamento
  por banco, o que muda o orçamento de contexto e por §3.1-bis **não pode**
  entrar em E0–E4 — teria de ser medição declarada em separado. Não feito.
- **O modelo preditivo vence a persistência em ordenação, e PERDE em F1 —
  as duas coisas ficam publicadas.** AUC 0,877 × 0,745; precisão 0,833 × 0,644
  no mesmo recall. Mas no limiar escolhido por F2, F1 e acurácia ficam abaixo
  da regra simples: é o preço declarado da preferência por recall da 5.10, não
  omissão. Ablação: o boosting mantém AUC 0,835 **sem nenhuma feature de
  histórico de prejuízo** — o sinal contábil é próprio, não é a persistência
  disfarçada.
- **E4 (`fatos`) não é persistido em disco, por decisão**: construir sob
  demanda (~35 s) evita a classe de defeito "índice novo, fatos velhos".
- Gate G1 (Azure) resolvido para o pré-deploy — sem ação pendente até lá.

## Próximo passo concreto

1. Rodar `python -m scripts.preparar_auditoria_final` sobre o fingerprint
   `5b9b142d` (arquivar `auditoria_groundedness.json`/`plano_estabilidade.json`
   de fingerprint antigo antes, se ainda estiverem no lugar) e repetir a
   leitura humana das 15 perguntas.
2. Depois da leitura: `scripts/executar_estabilidade.py --permitir-api-paga`
   (30 chamadas) e `scripts/consolidar_auditoria_final.py` — promoção a
   `completa` exige groundedness ≥ 0,90.
3. Em paralelo, sem depender do passo 1: dupla leitura dos 10 gabaritos
   pendentes de `conjunto_agentes.csv` — destrava o McNemar da etapa 12.
