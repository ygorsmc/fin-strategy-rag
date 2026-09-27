# Adendo ao O1 do Rank 3-B — exceção protetiva e identidade contábil

**Data:** 2026-09-26. **Aprovado por delegação:** Claude (sessão principal),
por delegação expressa do responsável nesta data; motivos em
[registro_decisoes_v2_rank03b_2026-09-26.md](registro_decisoes_v2_rank03b_2026-09-26.md).
**Vincula-se ao** [O1 do lote B](contratos_lote_b_rank03b_2026-09-16.md)
("O1 — Cegueira ao desfecho") e vale enquanto o O1 vigorar, isto é, até o
congelamento do pré-registro v2. Não altera nenhum outro item do O1.

**Revisado em 27/09**, depois da auditoria de conformidade da onda e da
reconferência dela. Mudaram a cláusula 3 (frase sobre o ÷1.000), a cláusula 7
(remete ao §11.7 do rascunho), a cláusula 9 (data da correção) e a parte 2
(lista fechada, tolerância absoluta, trava contra oráculo e conciliação de
caixa). **Nenhuma execução fixou a versão de 26/09** (SHA-256 `a41ed948…`),
que não chegou a ser commitada. A primeira execução que invocar este adendo
fixa a versão vigente, cujo hash está no registro de decisões.

## Parte 1 — Exceção protetiva no verificador de não publicação

1. **Onde.** Só na verificação que decide se uma saída pode ser gravada ou
   publicada, numa execução cujo contrato autorize ler FCO em memória para
   igualdade entre fontes. Hoje: `_magnitudes_protegidas` e
   `verificar_sem_valores`, em `scripts/conferir_alcance_geom1_rank03b.py`.
2. **Sobre quais valores.** Só valores de FCO do próprio documento em exame,
   já lidos em memória para a igualdade autorizada pelo contrato da execução,
   e só nas formas que esse contrato enumera para a busca. Hoje: o acumulado
   consolidado corrente, o comparativo do exercício anterior, o individual
   corrente, ×1.000 e ÷1.000 (`alvos_fco`). Forma nova exige contrato.
3. **Quais operações.** Módulo; piso e teto do módulo, quando não inteiro.
   Nenhuma outra: nem soma, diferença, sinal, arredondamento a outra casa ou
   agregação entre valores ou períodos. Piso e teto da forma ÷1.000 dão o FCO
   arredondado a milhar, que é a forma em que ele apareceria impresso nas
   notas; barrar essa forma é a proteção pretendida. "Arredondamento a outra
   casa" é qualquer arredondamento além do piso e do teto das formas
   enumeradas.
4. **Destino.** Os resultados ficam locais à verificação. Não são gravados,
   registrados, retornados, publicados nem passados a outra função. Também não
   são usados como evidência de escala, em busca de correspondência, em seleção
   de documento, em agregação ou em modelo. O único efeito possível é recusar a
   gravação, com mensagem sem dígitos e que não diz qual forma coincidiu.
5. **Sem uso como oráculo.** A verificação só examina saídas produzidas pela
   execução autorizada. É proibido submeter a ela números ou textos
   construídos para sondar valores. **A primeira recusa encerra a execução,
   sem gravar saída. Nova execução sobre os mesmos documentos exige registro
   do incidente e contrato novo**, que diga o que muda na saída e por quê.
6. **O que não autoriza.**
   - Busca de FCO arredondado.
   - Publicação de divisibilidade.
   - Adjudicação de escala pelo FCO.
   - Soma de FCO em janela, TTM ou rótulo.
   - Métrica de modelo.
   - Reuso, sobre o FCO, da função de ativo arredondado.
7. **Retroatividade.** O adendo não reclassifica as execuções que já fizeram
   essas operações em memória. Ficam como histórico, como diz o contrato de
   pendências de 26/09 (P4), as execuções de 24 a 26/09 declaradas no §11.7
   do rascunho v2. Entre elas:
   - o piso por truncamento do módulo das formas do FCO na revisão de 24/09 e,
     em 25/09, na conferência independente e na reconferência;
   - o piso e o teto na correção RAG de 25/09 e nos adendos 2 e 3 de 26/09.
8. **Vínculo e contraprovas.** Toda execução que invoque este adendo o fixa
   por SHA-256 nas suas entradas e o confere antes de ler pacote. Contraprovas:
   - saída que contenha piso ou teto de uma forma do FCO, inclusive do
     comparativo, é recusada;
   - nenhum retorno, atributo, exceção ou log da verificação contém dígitos de
     valor protegido;
   - depois de uma recusa, nada é gravado e a mesma execução não prossegue;
   - adendo com hash diferente derruba a execução antes de ler pacote.
9. **Declaração no §11 do v2.** Feita em 26/09 no §11.7 do rascunho e
   corrigida em 27/09: as leituras de FCO em memória para igualdade PDF × XML
   de 24 a 26/09 e as operações da cláusula 7.

## Parte 2 — Identidade contábil com saída booleana (esclarecimento do O1.2 e do O1.3)

O O1.2 permite contar "identidades contábeis", e o O1.3 restringe a leitura de
FCO a "testar igualdade entre duas fontes". Fica esclarecido que:

1. **Quais identidades.** Só identidades do plano de contas padrão da CVM entre
   valores declarados **no mesmo documento e período**: um total contra a soma
   das suas parcelas, ou dois totais que a norma iguala ou manda conciliar. É
   igualdade entre declarações da mesma fonte, permitida mesmo quando a `6.01`
   é uma das parcelas. A lista é **fechada** pelo contrato da execução, antes
   de ler. As conhecidas hoje são:
   - `6.01 + 6.02 + 6.03 + 6.04 = 6.05`;
   - `6.05.01 + 6.05 = 6.05.02`;
   - `1 = 2`;
   - `6.05.02 = 1.01.01`: o caixa final da DFC e o do balanço, que a norma
     manda conciliar e que costumam coincidir. Quando não coincidem, a
     identidade só deixa de servir de prova.
2. **Tolerância absoluta,** em unidades do valor bruto declarado, fixada antes
   de ler, como a de `identidades_contabeis` em
   `scripts/painel_pesquisa_rank03b.py` (diferença maior que 1 não fecha).
   Nunca proporcional a um valor de FCO nem derivada dele: tolerância relativa
   faria o booleano carregar informação sobre a magnitude.
3. **Saída só booleana** por documento e período: fecha ou não fecha. Nenhum
   valor, resíduo, sinal ou magnitude sai da verificação. Contar quantas
   identidades fecham é contagem estrutural.
4. Não se soma FCO entre períodos, nem se forma janela, TTM ou rótulo.
5. **Sem uso como oráculo.** Só se verificam os documentos e as identidades
   que o contrato fixou. É proibido submeter valores construídos. Documentos,
   identidades e tolerância não mudam depois de vistos os booleanos, salvo
   contrato novo que declare o que foi visto.
6. **Como elo de prova de escala do FCO,** o resultado só pode ser usado sob
   contrato próprio, que fixe antes de ler:
   - as contas;
   - a tolerância;
   - o conjunto de documentos;
   - o teste em amostra fora dos documentos de desenho da GEOM-1.

   Este adendo não executa nem aprova nenhuma rota de prova.

Isto substitui, daqui em diante, a leitura de que o O1 veda a identidade
interna da DFC (`MEMORY.md` e relatório de alcance de 24/09). O construtor do
painel de pesquisa já contava esses fechamentos sob o O1.2.
