# Contratos CRF-01 a CRF-03 — Rank 3-B
Data: 2026-09-17. Registrados antes de editar o instrumento ou reexecutar a
adjudicação. Origem: conferencia_rf01_rf08_rank03b_2026-09-17.md.
Pedido do usuário: resolver os achados. Não autoriza treino, T1/T2/baseline
real, decisão dos cinco [DECIDIR], holdout, chamadas pagas, novos downloads ou
alteração dos painéis compartilhados.

## C1 — prova de escala v4, estrita para saldos

A v3 fica disponível explicitamente para reprodução histórica. A v4 passa a
ser a regra vigente e NÃO infere coluna por coincidência de magnitude.

1. Só tabelas das notas (grupos 193/412) com cabeçalho local inequívoco:
   duas linhas não vazias imediatamente anteriores à linha de datas são
   exatamente um perímetro "Consolidado" e uma declaração de valores em
   milhares de reais, em qualquer ordem. Sem unidade herdada da página;
   cabeçalhos mistos Controladora/Consolidado não são aceitos.
2. A linha de datas contém somente datas completas dd/mm/aaaa ou aaaa-mm-dd,
   separadas por espaços ou barras verticais. Datas válidas, únicas; a data
   corrente tem de existir. Não inferir trimestre pelo ano.
3. Uma linha de dado contém um único rótulo textual antes de uma sequência
   de células numéricas. Número de células = número de datas. Letras entre
   células, colunas de notas, dois rótulos na mesma linha ou perda de células
   impedem o uso da linha. Linha vazia ou não reconhecida encerra a tabela;
   um cabeçalho não atravessa tabela/página. Zero e traço ocupam coluna mas
   não são prova de escala.
4. Contas admitidas: saldos 1 (ativo total / total do ativo), 2 (passivo total /
   total do passivo, também com patrimônio líquido), 1.01.01 (caixa e
   equivalentes de caixa). Rótulos completos, não substrings; não aceitar
   circulante/não circulante/ações. A conta 6.04 não se prova por "variação
   cambial", nem por movimentação de investimento. **Nesta v4 não se adjudica
   escala por fluxos 6.x:** a data final sozinha não identifica o intervalo
   acumulado/trimestral. Não é proibição permanente nem afirmação de ausência
   de dados; ampliar o extrator exige contrato próprio de intervalo.
5. O valor consolidado do saldo corrente precisa ser único no formulário,
   módulo >= 1.000. Comparar somente a célula da data corrente, usando módulo,
   nas três formas (bruto, dividido e multiplicado por mil). Não fazer busca
   em toda a linha. Preservar o piso de 1.000 para a forma dividida e a recusa
   v3 de coincidência sob outro multiplicador da mesma conta, inclusive
   individual/comparativo. Células inteiras admitem arredondamento ao inteiro
   mais próximo; célula decimal exige igualdade decimal.
6. Cada prova publica regra v4, conta, forma, anexo, página, linha, coluna
   (índices iniciando em 1), data, perímetro, unidade e cabeçalho local; os
   números do trecho ficam mascarados. Cabeçalho global e tabela S2 seguem
   exigidos. Ausência de tabela suportada é indecidível, nunca prova contrária.
7. A validação do manifesto exige esse escopo no produtor E no consumidor;
   leitura histórica v2/v3 exige opção explícita. Pontas herdadas carregam
   a regra que as decidiu. Reexecutar os 405 documentos e S5/heranças sobre
   pacotes locais, preservar execução 3 antes e publicar todas as transições.
   Hash do código registrado antes da execução. Não ajustar a regra depois
   de ver G0, mesmo se reprovar ou perder todas as correções.
8. Contraprovas: contas lado a lado; câmbio de investimento; comparativo;
   perímetro individual/misto; unidade ausente/contrária; cabeçalho distante;
   data repetida/ausente/inválida; células faltantes; subtotal; fluxo sem
   intervalo. Controles positivos: saldo corretamente em reais permanece,
   saldo comprovadamente em milhares é corrigido, ordem das datas invertida,
   várias linhas válidas na mesma tabela; máscara de números.

Custo conscientemente aceito: extrações sem essa estrutura local explícita
serão indecidíveis. Não criar lista branca de IDs, não apagar observações,
não mudar G0 para compensar cobertura. Conhecidos antes da regra: ESC-0029,
ESC-0101 e contraprovas publicadas; não é amostra fresca.

## C2 — completude das provas temporais

Exigir todas as chaves de documentos com base de escala não declarada, não só
mapa não vazio. Chaves ausentes, prova nula/NaT ou data inválida levantam
ProvasAusentes antes de produzir qualquer aprovação. Entradas medir,
verificar_falsificacoes, g1_provas_depois_de_d e g1_cego têm a guarda.
g1_cego exige painel para poder certificar G1.4; não publica zero como medição
quando não possui a fonte. Documento sem correção não requer prova.

datas_das_provas continua recalculando datas pelo manifesto/cadastro, nunca
pelo campo dt_prova do construtor; rejeita recepções inválidas. A guarda de
completude não compara com dt_prova, pois deve capturar construtor sabotado.
Não pretende certificar um mapa arbitrariamente forjado pelo chamador como se
viesse do cadastro; o executor é responsável por gerar o mapa dessa fonte.

Contraprovas: mapa parcial de dois documentos, vazio, valor nulo/NaT/string
inválida; chamada direta; mapa completo e construtor correto; construtor
sabotado continua reprovando; painel sem correções continua permitido.

## C3 — versão e descrição documental

Marcar números da execução 2 localmente como históricos; execução 3 preservada
como substituída depois de publicar a v4. Descrever D como datas distintas de
disponibilidade das linhas de FCO fornecidas ao construtor, não como cadastro
de todos os documentos; no painel de pesquisa inclui a prova de escala.
Atualizar somente a descrição, não a grade nem os cinco [DECIDIR].

## Entrega e verificação

Testes focados e suíte completa; auditor-conformidade somente leitura, em
contexto separado, antes de conclusão. Reconstruir apenas painel de pesquisa,
regenerar artefatos ligados à versão quando necessário, preservar a anterior.
Documentar cobertura, contraprovas, hashes antes/depois, limites e veredito.
Se a regra segura perder evidência, relatar bloqueio de dados: não autorização
de treino. Atualizar MEMORY.md e pré-registro ainda rascunho.
