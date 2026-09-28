# Rank 3-B: o que foi feito e o que falta até o treino

**Data:** 2026-09-27, revisado em 28/09 depois da auditoria final. **Para:** o
responsável, antes do ato de congelamento.
**Estado:** o G0 foi resolvido, sem rótulo. O pré-registro v2 continua
**RASCUNHO**.
- A onda de 27/09 está no commit `9049579`, feito por você.
- As correções da auditoria final, de 28/09, ainda não têm commit.

## Em uma tela

**O bloqueio era o G0.** Eram 132 saltos de escala no ativo, contra um máximo
de 111 (0,5% de 22.325 linhas). **Agora são 95 (0,4255%).** A redução veio de
correções de escala **por conta**:
- 42 no Ativo Total;
- 35 no FCO.

Cada correção foi provada no próprio documento por uma regra fixada antes de
ler (ROTA-2) e aprovada por dois conferentes independentes, sem nenhuma
recusa. G0.5 e G1 também aprovaram. A amostra tem 10.168 observações em 495
companhias. **Nenhum rótulo foi montado**, e nenhuma taxa de evento, T1, T2,
AUC ou baseline foi calculada.

**O que falta:**
1. a sua revisão;
2. o commit das correções de 28/09;
3. **o seu ato de congelamento**, por cópia (seção 4);
4. a medição;
5. o protocolo do desafiante (D8), só se a medição der PRONTO PARA CHALLENGER;
6. o treino, só depois disso.

**Leia antes de congelar.** A previsão registrada desde 11/09 é que **T1
reprove por `fco_ttm_sobre_sd8`**. Se ela se confirmar, o veredito é
REJEITADO e não há treino. Congelar é aceitar esse risco antes de ver o
resultado, e é isso que dá valor ao pré-registro.

## 1. Os quatro itens do seu pedido

| Item | Contrato | Código e testes | Resultado |
|---|---|---|---|
| 1. Correção por conta (três condições do §12-bis) | [contratos](contratos_caminho_medicao_rank03b_2026-09-27.md), parte A | `scripts/correcoes_por_conta_rank03b.py`; o painel aplica escala e disponibilidade por conta (`scripts/painel_pesquisa_rank03b.py`) | Manifesto de esquema fechado, validado pelo consumidor na gravação e na releitura; 77 linhas, `f26ede4d…` |
| 2. Rota de prova (ativo pela célula, FCO pela cadeia de identidades) | partes B e ROTA-2 | `scripts/rota_prova_rank03b.py`; conferência B8 em `conferencia.json` | ROTA-1 parou na B7; ROTA-2 aprovada sem recusa (seção 2) |
| 3. Painel novo com G0 sem rótulo | parte D | `artefatos/painel_pesquisa_rank03b_v2/` | digest de conteúdo `fd2932e7…`; **G0, G0.5 e G1 aprovados** |
| 4. Executor v2 | parte C, emendas C8 e C9; AF1 a AF3 (28/09) | `scripts/executor_v2_rank03b.py` (modos estrutural e de medição); 296 testes nos três arquivos novos | `artefatos/executor_v2_rank03b/estrutural.json` com os pins propostos |

A suíte completa tem **4.480 testes aprovados**, sem nenhum pulado.

**Auditoria final (28/09), sobre o commit `9049579`: APTA COM RESSALVAS.**
Não houve achado ALTA. Houve um MÉDIA e cinco BAIXA, todos corrigidos antes do
congelamento (tabela no fim do [contrato](contratos_caminho_medicao_rank03b_2026-09-27.md)):
- **M1:** o procedimento de congelamento desta revisão, na versão de 27/09,
  falharia. Renomear o rascunho quebra o executor, e ajustar o código depois
  deixa o digest velho. Agora se congela por cópia (seção 4).
- **B1:** a trava do título não protegia o arquivo real, porque a marca de
  rascunho está na linha de status. Agora **toda** linha de status tem de
  dizer exatamente `**Status: CONGELADO em AAAA-MM-DD`, em qualquer forma que
  apareça (emenda AF1).
- **B2:** a guarda da folga do motivo 11 não tinha contraprova. Agora tem, e o
  mutante sem a guarda é derrubado (emenda AF2).
- **B3:** o `140867` fora da amostra era acaso do dado. Agora o uso de erro
  demonstrado pendente reprova o G0.5 (emenda AF3). Hoje o uso é zero.
- **B4:** faltavam notas datadas no rascunho e os hashes das entradas.
  Acrescentados.
- **B5:** os pareceres da conferência estavam num scratchpad apagado. Foram
  reconstruídos byte a byte, com os hashes conferidos, e versionados em
  `artefatos/rota_prova_rank03b_v2_2026-09-27/pareceres/`.

**Verificação curta das correções (28/09): FECHADO COM RESSALVAS.** Os seis
achados foram dados como fechados. As seis ressalvas BAIXA também foram
tratadas:
- a trava da linha de status aceitava uma linha CONGELADO acrescentada sem
  trocar a de RASCUNHO; foi endurecida;
- dois ramos da AF3 não tinham teste; os cinco mutantes da verificação agora
  morrem;
- os nomes das emendas colidiam com um C10 antigo; viraram AF1 a AF3;
- o estrutural estava defasado em relação ao rascunho;
- a contagem da suíte no `MEMORY.md` era a antiga;
- faltava declarar no contrato as mudanças de fixture.

Depois de todas as correções, o artefato estrutural foi regerado. Mudaram só
os hashes informativos de código, do contrato e do rascunho, e entraram dois
campos novos, ambos zero. G0, G0.5 e G1 continuam aprovados.

**Números de referência**

| | Antes (18/09) | Agora |
|---|---:|---:|
| G0.3: saltos / linhas de ativo da população v2 | 132 / 22.325 (0,59%)¹ | **95 / 22.325 (0,4255%)** |
| Documentos com escala decidida: ativo · FCO | 0 · 0 | 94 · 90 |
| Correções no manifesto: ativo · FCO | 0 · 0 | 42 · 35 |
| Amostra sem rótulo | — | 10.168 observações, 495 companhias |

¹ 0,5875% na população da v1, com 22.469 linhas. As três seguradoras
excluídas pelo §3.2 têm zero saltos.

## 2. O que deu errado no caminho, e como foi tratado

- **A primeira auditoria do contrato saiu NÃO APTA.** Os achados A1, A2, M1–M6
  e B1–B10 foram corrigidos com emenda datada, antes de qualquer execução. Uma
  reconferência e uma verificação curta fecharam o que sobrou (N1, N2 e as
  BAIXAs).
- **A ROTA-1 rodou e não produziu manifesto.** A conferência recusou 4 das 129
  correções:
  - em `60719`, a unidade não estava demonstrada, e isso era defeito real da
    regra;
  - em `80868`, a recusa veio da redação ambígua do item 4.

  Pela parada B7, uma recusa basta para não haver manifesto. A ROTA-2 foi
  escrita **só estreitando** a regra: a apresentação do anexo passou a exigir
  o objeto e ficou restrita aos grupos 193/412. Verificada APTA, rodou e passou
  por uma conferência nova, com amostra nova de confirmações.
- **A guarda de publicação barrou o primeiro artefato estrutural (emenda C8).**
  O estado de linha `lacuna` do painel tem o mesmo nome da estatística do T2,
  que é proibida. A guarda não foi afrouxada: o inventário passou a sair como
  lista de pares, com vocabulário fechado. A causa estava no teste:
  `executar_estrutural` não tinha teste nenhum. Agora tem, de ponta a ponta.
- **A conferência não estava nos pins (emenda C9).** Estava só implícita,
  pelas linhas do manifesto. Agora é pin por nome, e o nome legado
  `evidencias_rota_1` foi trocado.

## 3. Pontos que pedem o seu julgamento

1. **`113026-1.01.01` é limítrofe.** O caixa foi provado só pelo saldo final da
   DFC impressa. A linha do balanço não traz os dígitos, porque a `1.01.01`
   dessa companhia soma caixa e caixa restrito. Os dígitos são exatos, em duas
   datas, sob milhares.

   A correção do FCO do mesmo documento (`ROTA-2-113026-6.01`) usa esse caixa
   como âncora. O ativo (`ROTA-2-113026-1`) foi provado pela própria célula, de
   forma independente. Por isso a correção dele, que é a que conta no G0.3,
   não depende desse caixa.

   Se você entender que linha de DFC não é célula própria do caixa, saem as
   duas correções, a do caixa e a do FCO. Isso exige uma ROTA-3 e uma
   conferência nova antes do congelamento.
2. **`140867` fica pendente, e visível.** A GEOM-1 demonstrou `MIL` no ativo,
   mas a ROTA-2 não achou linha com os dois números. A linha entra na contagem
   do G0.3 e nenhuma observação a usa como ativo em D. Desde a AF3 isso é
   verificado em código: se alguma observação passar a usá-la, o G0.5 reprova.
   O FCO do mesmo documento foi provado e corrigido; quatro observações o usam
   no rótulo, legitimamente.
3. **A folga é de 16 saltos.** Os 95 que sobram não são removidos, pela regra
   9 do §4.4. Mudança de dado depois do congelamento é condição de
   falsificação (§13).
4. **O que foi visto antes de congelar (§11.8).** O G0 foi visto antes do
   congelamento, como o próprio rascunho previa. Depois de ver o G0, mudaram
   os pins (C9) e três guardas que só tornam a medição mais estrita (AF1 a
   AF3). Nenhuma regra de dado, população, limiar ou correção mudou, e as
   guardas novas dão zero neste dado. Os conferentes declararam exposições ao O1, todas booleanas ou
   de formato. Nenhuma é estatística de rótulo.
5. **A ROTA-2 foi escrita conhecendo os resultados da ROTA-1.** Por isso só
   estreita a regra. O auditor confirmou que ela não pode aumentar as
   correções neste dado. O custo: `98282-1.01.01`, que a ROTA-1 aprovava, virou
   indecidível.
6. **Em `80868` há divergência de escala.** O formulário interno declara
   `MIL`, e o envelope e o CSV declaram `UNIDADE`. A correção vai para `MIL`,
   que é a escala provada. A divergência está na nota da conferência.

## 4. O que falta até o treino, em ordem

**1. A sua revisão.** Deste documento, das emendas no fim do
[contrato](contratos_caminho_medicao_rank03b_2026-09-27.md) e das revisões
datadas de 27 e 28/09 no [rascunho](pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md):
topo, §4, §5 (G0.5), §5.5, §11.8, §12-bis, §13 e §14.

**2. O commit das correções de 28/09, quando você pedir.** Entram:
- as emendas AF1 a AF3 no executor e nos testes;
- os pareceres versionados;
- o artefato estrutural regerado;
- as notas no rascunho, no contrato, neste documento e no `MEMORY.md`.

O `.duckdb` do painel v2 fica fora do Git, como o do painel anterior.

**3. O congelamento, que é ato seu, por cópia.** A delegação de 26/09 não o
cobre. O rascunho **fica no lugar**: o executor e um teste o leem pelo nome.
A ordem importa:
1. Todo o código final commitado, com a suíte verde. Depois do passo 5,
   qualquer edição de código medido exige congelar de novo.
2. Regerar o artefato estrutural:

   ```
   python -m scripts.executor_v2_rank03b --rota artefatos/rota_prova_rank03b_v2_2026-09-27 --correcoes-por-conta corpus/cvm/painel_pesquisa_rank03b/correcoes_escala_por_conta.csv
   ```

   Copie de lá o `codigo_de_medicao` de `pins_propostos_para_o_congelamento`.
3. Copiar o rascunho para um arquivo novo, com nome sem RASCUNHO. Por
   exemplo: `resultados/pre_registro_rank03b_v2_2026-09-16.md`.
4. Na cópia:
   - trocar a linha de status por `**Status: CONGELADO em <data>, por ato do
     responsável.**`;
   - registrar o ato com as suas palavras e a data;
   - colar os seis hashes do §4, com o `codigo_de_medicao` do passo 2.

   A medição recusa se a linha de status não declarar congelamento ou se
   faltar algum hash.
5. Calcular e publicar o SHA-256 da cópia (`sha256sum <arquivo>`), por exemplo
   no `MEMORY.md` e no commit do congelamento.

**4. A medição.**

```
python -m scripts.executor_v2_rank03b --medir --pre-registro resultados/<arquivo congelado> --sha256 <hash> --rota artefatos/rota_prova_rank03b_v2_2026-09-27 --correcoes-por-conta corpus/cvm/painel_pesquisa_rank03b/correcoes_escala_por_conta.csv
```

A medição confere o congelamento antes de ler o painel e refaz G0, G0.5 e G1.
Só se os três aprovarem ela monta o rótulo e roda T1, T2 e os baselines. Ela
não sobrescreve uma medição anterior.

**5. O que cada desfecho significa.**

| Veredito | Significado | Próximo passo |
|---|---|---|
| REPROVADO EM G0/G1 | Não deveria ocorrer com as mesmas entradas; se ocorrer, algo mudou | Tratar como falsificação (§13) |
| **REJEITADO** (o previsto) | O alvo fabrica o próprio baseline ou só ordena emissores | Registrar em `becos_sem_saida.md`. Sem treino. Reabre só com outro estimando e outro pré-registro |
| INDECIDÍVEL | Faltou suporte: menos de 30 companhias com os dois rótulos, bootstrap acima de 10% ou baselines incompletos | Sem treino. Registrar o que faltou |
| **PRONTO PARA CHALLENGER** | Permissão para escrever o protocolo do desafiante, não para treinar | Ir ao passo 6 |

**6. O protocolo do desafiante (D8).** Só depois de PRONTO PARA CHALLENGER.
Precisa ser escrito e congelado antes de treinar, e fixa pelo menos:
- a métrica que define o melhor baseline;
- o split temporal;
- a margem com IC 95% pareado fora da amostra.

**7. O treino.** Só sob o D8 congelado.

## 5. O que não foi feito, de propósito

Nada disto foi feito:
- congelamento;
- rótulo, T1, T2, AUC, baseline ou taxa de evento;
- treino;
- commit das correções de 28/09 (o da onda de 27/09 foi feito por você);
- download;
- chamada paga;
- acesso ao holdout;
- escrita em `cvm.duckdb` ou em `cvm_treino.duckdb` (o último foi lido só para
  o universo, somente leitura).

## 6. Dívidas que não bloqueiam o congelamento

- `MEMORY.md` tem cerca de 1.260 linhas, e o §10 do AGENTS.md pede poucas
  dezenas. Precisa de uma onda própria de enxugamento.
- `artefatos/snapshots/` (101 MB) segue com a remoção pendente de decisão sua,
  desde 26/09.
- O script `scripts/manifesto_rota1_rank03b.py` tem nome da primeira versão.
  A docstring declara que ele usa a regra vigente.
- O painel compartilhado continua com o defeito de escala. Só o painel de
  pesquisa foi corrigido, que é o que a medição usa.
- Mais cobertura de prova, com download de pacotes internos ausentes ou uma
  ROTA-3, só aumentaria a folga do G0. Não é necessária para medir.
