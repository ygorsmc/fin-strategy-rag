<!--
Resposta final do preenchedor (modelo-preditivo, contexto separado), devolvida em
26/09 junto com a proposta (SHA-256 5c0e72b9…31e0). Transcrita na íntegra. É saída
de modelo, não decisão humana. O caminho citado era o scratchpad da sessão, que foi
apagado num reinício; a cópia revisada está em proposta_v1_revisada.md.
-->

Escrevi a proposta para os sete itens em:
`/tmp/claude-1000/-home-ygor-Antigravity-Projects-fin-strategy-rag/b3cd8830-7fb5-446d-ae1b-5242b33bd763/scratchpad/preenchimento_v2/proposta.md`

É proposta, não aprovação, e nada no repositório mudou. O `git status` mostra só o `M MEMORY.md` que já existia antes. Não rodei scripts, não abri painéis, pacotes RAD nem PDFs, e não li nenhum valor de FCO.

Duas propostas divergem do rascunho: §5.5 e §8.1. As demais concordam com ele, algumas com acréscimos.

| Item | Proposta | Confiança |
|---|---|---|
| §3.2 seguradoras | Excluir `ll3_13_%`, como no rascunho. São 3 companhias; o painel não muda, o executor filtra. | alta |
| §5.1 G0.1 | Unicidade: proíbe somar MD e MI do mesmo período. Derivação entre métodos fica permitida, contada na linhagem e sujeita às regras F1–F6 e ao G0.5. | alta |
| §5.5 G0.5 | **Diverge (opção nova).** Em vez do limiar de ≤0,5%, os trimestres com escalas heterogêneas não adjudicadas são censurados, e o G0.5 verifica que nenhum foi usado. A perda é publicada antes de montar `y`. | média |
| §6.1 grade de D | Manter a grade atual: datas de disponibilidade das linhas de FCO utilizáveis. | alta |
| §8.1 suporte do T2 | **Diverge da proposta; é a alternativa do rascunho.** Piso de 30 companhias com os dois rótulos (o mínimo que a v1 já fixava para T1); abaixo disso, INDECIDÍVEL. | média |
| §12-bis | Opção B, com um acréscimo: confirmação ou correção só por prova de saldo também não conta como "decidido para o FCO" dentro do G0.5. | alta |
| O1 | Aprovar a exceção protetiva com emendas: só as cinco formas do FCO do próprio documento, proibição de usar o verificador como oráculo, sem efeito retroativo, e contraprovas. | alta |

**Por que divergi no §5.5.** O 0,5% conta trimestres, mas cada trimestre entra em até 8 janelas de features e 4 rótulos. Pelo limite grosseiro que calculei à mão, os 82 trimestres atuais chegam a cerca de 1.000 observações (~9%). Contaminação sem relação com o rótulo tende a atenuar T1 e T2, ou seja, empurra para aprovar. Censurar troca essa contaminação por perda de observações, e a perda é visível.

**Contradições e limitações nas fontes:**
- **CPC 03:** não está no repositório e não há rede. Os itens 18–20A que sustentam o §5.1 não foram conferidos.
- **Letra da v1 no G0.1:** a v1 diz "nenhuma observação usa DFC_MD e DFC_MI para o mesmo (companhia, trimestre)" (V1:130). É mais largo que a paráfrase "sem soma" do rascunho. Declarei isso no documento.
- **`becos_sem_saida.md:96` desatualizado:** ainda diz que G0/G1 aprovam (estado de 16/09).
- **O1 × identidade da DFC, não resolvido:** o O1.2 permite "identidades contábeis" e o lote B mediu identidades da DFC. Já `alcance_geom1:288-290` e `MEMORY.md:408-410` dizem que o fechamento da DFC é vedado pelo O1. Isso pesa sobre a rota de prova de FCO exigida pela opção B.
- **Piso/teto sob o O1:** o adendo RAG de 25/09 diz que o uso seguia o O1, o contrato de 26/09 diz que não há autorização explícita. Piso e teto do FCO já foram calculados em memória em 25/09.
- **Menores:** 83 × 82 trimestres heterogêneos (RASC:226-227 contra RASC:427), sem explicação. O docstring do auditor (AUD:657) ainda descreve D como `dt_receb`.

**Exposição.** No §11 do rascunho vi números de desfecho: a taxa do evento 0,0526 → 0,0530, os "3" rótulos alterados, os "−5" em FCO TTM não positivo e os ≈2.865–2.867 descartes por FCO_TTM ≤ 0. Nenhum orientou as escolhas. Os números estruturais usados estão declarados item a item no documento.
