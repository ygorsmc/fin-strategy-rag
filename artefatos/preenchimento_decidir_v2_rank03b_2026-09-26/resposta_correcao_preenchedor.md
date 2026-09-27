<!--
Resposta do preenchedor à rodada de correção, devolvida em 26/09 junto com
proposta_v2.md (SHA-256 e64f61db86e2cd303c197085a67e32e9f9a332deb56942b83787345ea2307b6c).
Transcrita na íntegra. É saída de modelo, não decisão humana.
-->

A versão corrigida está em `artefatos/preenchimento_decidir_v2_rank03b_2026-09-26/proposta_v2.md`, SHA-256 `e64f61db86e2cd303c197085a67e32e9f9a332deb56942b83787345ea2307b6c`. Corrigi E1 e E2, tratei as 14 ressalvas e mantive as sete escolhas. A `proposta_v1_revisada.md` continua com `5c0e72b9…31e0`, e o estado do git é o mesmo do início da rodada.

**Erros de fato**
- **E1 (§5.1):** saiu a frase sem fonte de que o trimestre derivado entre métodos "não existia" no painel da v1, tanto no texto pronto quanto no julgamento. No lugar entrou o fato indicado pelo revisor: o G0.1 que a v1 executou só contava grupos com mais de um demonstrativo (AUD:407–415), então a unicidade é a leitura que a v1 de fato aplicou. O fato 3 agora separa as duas derivações: a do 2T/3T particiona por demonstrativo; a do 4T junta anual e nove meses sem demonstrativo (`src/dados_estruturados.py:1322–1325, 1486, 1500–1504`). Um 4T entre métodos era, portanto, possível na v1.
- **E2 (§5.5):** o texto pronto passa a dizer que o G0.3 só vê esses casos quando há transição no ativo. Erro de escala consistente, sem transição, não tem gate nenhum. O exemplo são as 17 companhias só `UNIDADE`, com 400 documentos (MED). Esse erro afeta só os três componentes de nível.

**Ressalvas**
- **§3.2:** incorporada com ajuste. Não escrevi "nenhuma faz o G0.3 passar", porque os saltos das três companhias não foram medidos. O texto diz que nenhuma decisão foi escolhida pelo efeito no G0.3 e manda publicar os saltos e as linhas de ativo das excluídas.
- **§5.1:** o critério de refutação do lote C passa a ser tratado como ausência de teste, não como evidência.
- **§5.5:** a perda passa a ser publicada também em companhias, não só em observações.
- **§8.1:** incluí o IC da lacuna, descritivo e fora da decisão.
- **§12-bis:** a conta `1` se prova pela própria célula. A frase sobre correção só do ativo passa a citar só o G0.3 e o esquema do manifesto. O ativo de 140867 fica registrado como erro demonstrado e pendente. A rota pela identidade da DFC ficou registrada no §10, sem decidir.
- **O1:** a primeira recusa encerra a execução, e refazer exige registro do incidente e contrato novo. O comparativo entrou nas formas enumeradas. Há uma cláusula 9 que manda declarar no §11 do v2 as leituras de FCO de 24 a 26/09 e o piso/teto.
- **Datas da retroatividade (O1):** corrigi o revisor. O código preservado mostra piso por truncamento já em 24/09 e 25/09 (REV24:123–124; REC25:136–137). Piso e teto juntos, em 25 e 26/09.
- **Transversal:** o congelamento passa a exigir também a resolução estrutural do G0, com o O1 vigente até lá.

**Divergências, mantidas com a alternativa do revisor**
- **§5.5, C contra C+E:** retirei meu argumento de "sobreposição com o G0.3", porque vale igual para C. Mantenho C pela perda de E não medida. Recomendo medir as duas perdas antes de decidir e preferir E se a perda adicional couber nos mínimos do T1. O texto pronto de E está incluído.
- **§6.1, deduplicação:** acrescentei um fato que reforça o revisor. Observações com o mesmo q1 têm o mesmo `Y` (RASC:122–125; AUD:706–711). Corrigi também minha frase de horizonte "quase constante". Mantenho A e passo a publicar as chaves (companhia, q1) repetidas. A confiança em não deduplicar caiu para média. O texto pronto da deduplicação está incluído.
