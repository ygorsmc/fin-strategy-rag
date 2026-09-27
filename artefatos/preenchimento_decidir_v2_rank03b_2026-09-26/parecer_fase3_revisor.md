<!--
Parecer da fase 3 (reconferência restrita) do revisor independente
(auditor-conformidade, somente leitura, mesmo contexto das fases 1 e 2),
devolvido em 26/09 sobre proposta_v2.md (SHA-256 e64f61db…07b6c). Transcrito na
íntegra. É saída de modelo, não decisão humana.
-->

# Fase 3 do Rank 3-B v2: 15 de 16 pontos fechados; falta ajustar o texto da alternativa C+E

**Veredito geral: APTA COM RESSALVAS.** Os dois erros de fato (E1 e E2) estão corrigidos e todas as ressalvas foram tratadas. Um ponto fica em aberto: o texto pronto da minha alternativa C+E no §5.5 saiu mais largo do que eu propus. Com esse ajuste, a proposta fica apta para decisão do responsável.

Conferi os hashes (`proposta_v2.md` = `e64f61db…07b6c`; `proposta_v1_revisada.md` = `5c0e72b9…31e0`), comparei as duas versões e abri as fontes novas citadas. Somente leitura: não abri DuckDB, RAD nem PDF e não li valor de FCO. Li o código preservado de 24 e 25/09, que só contém a lógica, sem valores.

| Ponto | Veredito |
|---|---|
| E1 (§5.1) | FECHADO |
| E2 (§5.5) | FECHADO |
| §3.2 | FECHADO |
| §5.1, critério de refutação | FECHADO |
| §5.5, perda também em companhias | FECHADO |
| §8.1, IC da lacuna | FECHADO |
| §12-bis (a) a (d) | FECHADO |
| O1 (a), (b), (d) | FECHADO |
| O1 (c), datas da retroatividade | FECHADO |
| Congelamento condicionado ao G0 | FECHADO |
| Fidelidade da alternativa do §6.1 | FECHADO |
| **Fidelidade da alternativa do §5.5** | **NÃO FECHADO** |
| Erro novo | Nenhum substantivo; dois ponteiros imprecisos |
| Regras (cegueira, O1, §4.4) | FECHADO |

## Erros de fato
- **E1 — FECHADO.** Saiu do texto pronto e do julgamento a frase de que o trimestre derivado entre métodos "não existia" no painel da v1.
  - No lugar entrou o fato verificável: o G0.1 que a v1 executou só contava pares (companhia, trimestre) com mais de um demonstrativo (AUD:407–415).
  - O fato 3 agora distingue as duas derivações. A do 2T e 3T separa por demonstrativo (SRC:1342–1346). A do 4T junta anual e nove meses sem olhar o demonstrativo e grava o do anual (SRC:1486, 1500–1504). O texto diz que esse 4T era possível e que não se verificou se existiu.
  - Ponteiro impreciso: a chave de pareamento do 4T está em SRC:1461–1464, não em SRC:1322–1325. A expressão é a mesma, só a linha citada é da outra função.
- **E2 — FECHADO.** O texto pronto passa a dizer que o G0.3 só vê esses casos quando há transição no ativo, e que erro de escala consistente não tem gate nenhum.
  - A afirmação de que esse erro afeta só os três componentes de nível, e não as razões, a contagem de trimestres negativos nem o rótulo, está correta pelas definições de V1:162–169. Vale porque a escala declarada é uma por documento.
  - O "O que não se pode alegar" agora está coerente com o texto pronto.

## Ressalvas
- **§3.2 — FECHADO, e o desvio do meu texto procede.**
  - Escrever "nenhuma faz o G0.3 passar" seria afirmar algo não medido: os saltos das três companhias excluídas não foram contados.
  - A nova redação é mais exata: nenhuma decisão foi escolhida pelo efeito no G0.3, seis delas não o tocam, e o executor publica os saltos e as linhas de ativo das excluídas.
  - Conferi que as seis outras de fato não mexem no ativo nem no G0.3.
- **§5.1 — FECHADO.** O critério de refutação do lote C (LCR:258) passa a ser tratado como ausência de teste, não como evidência. A mudança aparece nos fatos, no "O que não se pode alegar" e no §10.
- **§5.5 — FECHADO.** A perda passa a ser publicada também em companhias: as que perdem alguma observação e as que saem inteiras, com a fração sobre o total.
- **§8.1 — FECHADO.** O IC da lacuna entra como descritivo, com contraprova de que não altera o veredito. O §13 ganha "IC usado na decisão".
- **§12-bis — FECHADO, os quatro pontos.**
  - A conta `1` se prova pela própria célula; prova de `2` ou de `1.01.01` não a substitui. É coerente com as "quatro ligações" do rascunho.
  - A frase sobre correção só do ativo passa a citar só o G0.3 e o esquema do manifesto (CPEND:47–49).
  - O ativo de 140867 fica registrado como erro demonstrado e pendente, e o executor o lista no artefato de G0.
  - A rota pela identidade da DFC fica no §10, remetida a contrato próprio com teste fora dos documentos de desenho.
- **O1 (a), (b), (d) — FECHADO.**
  - A primeira recusa encerra a execução; nova execução exige registro do incidente e contrato novo, com contraprova na cláusula 8.
  - O comparativo do exercício anterior entrou nas formas enumeradas (VER:670).
  - A cláusula 9 manda declarar no §11 do v2 as leituras de FCO de 24 a 26/09 e as operações da cláusula 7.
- **O1 (c) — FECHADO, e o preenchedor corrigiu o revisor corretamente.**
  - O verificador preservado da revisão de 24/09 calcula `int(abs(v))` de cada valor comparado (REV24:123–124, 132–137), inclusive da forma ÷1.000 do FCO (REV24:197–198). Isso é piso por truncamento.
  - Ele rodou sobre dado real em 24/09: a saída `conferencia_revisao.json` é de 24/09.
  - A reconferência de 25/09 faz o mesmo. A linha que efetivamente rodou em 25/09 é REC25:395 (`reconferir_publicados`), não REC25:343–344 (`executar`, que não foi reexecutada, ALC:322). O fato se mantém; só o ponteiro está impreciso.
  - A data "25–26/09" que eu dei no parecer estava incompleta.
- **Congelamento — FECHADO.** O §8 ganhou o item 9 e o §0.4 e o §9 acompanham: o congelamento espera a resolução estrutural do G0, com pins novos, e o O1 continua vigente até lá.

## Fidelidade das alternativas
- **§6.1 — FECHADO.**
  - Meus dois argumentos estão reproduzidos fielmente.
  - O texto pronto da deduplicação (uma observação por companhia e q1, a de maior D, com motivo próprio no inventário) é fiel.
  - O novo fato 7 (mesmo q1 implica mesmo `Y`, RASC:122–125; AUD:706–711) está correto e reforça a alternativa. A contagem de chaves repetidas é estrutural, porque q1 depende só de datas.
- **§5.5 — NÃO FECHADO.** Os três argumentos estão fiéis, a retirada do argumento de "sobreposição com o G0.3" procede e a conta do exemplo novo está certa. O problema é o texto pronto de E (linhas 598–602), que é mais largo que a minha alternativa em dois pontos:
  1. **Rótulo inteiro em vez de S1 e S2 separados.** O texto censura quando os q1 a q4 "combinem valores de documentos com escalas aplicadas diferentes". O rótulo depende só do sinal de S1 e do sinal de S2, cada um separadamente. Se S1 vem de documentos numa escala e S2 de documentos em outra, o rótulo não muda. Isso acontece quando a divisão entre S1 e S2 coincide com a virada do exercício; nos outros casos, o trimestre da fronteira já é derivação heterogênea e cai em C.
  2. **Inclui o ativo em D com o critério errado.** O texto usa "decidido para o FCO" também para o documento do ativo. Para o ativo, o veredito que importa é o do ativo. Incluí-lo é uma extensão que eu não propus (defensável para `fco_ttm_sobre_ativo`, mas com o critério da conta certa).
  - **Por que importa:** a proposta recomenda escolher entre C e E pela perda medida. Um texto de E mais largo que o necessário infla justamente essa perda.
  - **Correção:** "cuja janela de oito trimestres, cujo S1 ou cujo S2 combinem valores de documentos com escalas aplicadas diferentes, com algum documento sem veredito para o FCO". O ativo sai do texto, ou entra como variante separada, com o veredito do ativo.

## Erro novo e regras
- **Erro novo — nenhum substantivo.** Conferi os fatos, frases e números acrescentados; as referências novas do §5.5, do O1 e do §6.1 conferem. Restam os dois ponteiros imprecisos já citados: SRC:1322–1325 em vez de SRC:1461–1464, e REC25:343–344 em vez de REC25:395.
- **Regras — FECHADO.** O cabeçalho continua dizendo que é proposta de agente, o "Registro da revisão" não apresenta nada como aprovado, a exposição foi atualizada no §0.3 sem número de desfecho novo, e as leituras novas são só de código.

## Correções que faltam
1. **Obrigatória:** texto pronto de E no §5.5 (linhas 598–602), como acima.
2. **Opcionais, de ponteiro:** SRC:1322–1325 → SRC:1461–1464 no fato 3 do §5.1 e no Registro; REC25:343–344 → REC25:395 no fato 5 do O1.
