# Rank 3-B: o que foi feito e o que falta até o treino

**Data:** 2026-09-27. **Para:** o responsável, antes do ato de congelamento.
**Estado:** o G0 foi resolvido, sem rótulo. O pré-registro v2 continua
**RASCUNHO** e nada foi commitado.

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
2. o commit;
3. **o seu ato de congelamento**;
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
| 4. Executor v2 | parte C, emendas C8 e C9 | `scripts/executor_v2_rank03b.py` (modos estrutural e de medição); 268 testes nos três arquivos novos | `artefatos/executor_v2_rank03b/estrutural.json` com os pins propostos |

A suíte completa tem **4.452 testes aprovados**, sem nenhum pulado.

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
   do G0.3 e não é usada por nenhuma observação (verificado por contagem, sem
   ler valor). O FCO do mesmo documento foi provado e corrigido.
3. **A folga é de 16 saltos.** Os 95 que sobram não são removidos, pela regra
   9 do §4.4. Mudança de dado depois do congelamento é condição de
   falsificação (§13).
4. **O que foi visto antes de congelar (§11.8).** O G0 foi visto antes do
   congelamento, como o próprio rascunho previa. Depois de ver o G0, só
   mudaram a serialização e os pins; nenhuma regra de dado, população, limiar
   ou correção. Os conferentes declararam exposições ao O1, todas booleanas ou
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
datadas de 27/09 no [rascunho](pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md):
topo, §4, §5.5, §11.8, §12-bis, §13 e §14.

**2. O commit, quando você pedir.** Estão prontos para entrar:
- os scripts e testes novos;
- os artefatos das duas rotas e do executor;
- o manifesto por conta;
- os documentos.

O `.duckdb` do painel v2 fica fora do Git, como o do painel anterior.

**3. O congelamento, que é ato seu.** A delegação de 26/09 não o cobre. Os
passos:
1. Registrar o ato com as suas palavras e a data.
2. Regerar o artefato estrutural sobre o código final:

   ```
   python -m scripts.executor_v2_rank03b --rota artefatos/rota_prova_rank03b_v2_2026-09-27 --correcoes-por-conta corpus/cvm/painel_pesquisa_rank03b/correcoes_escala_por_conta.csv
   ```

   Copie de lá o `codigo_de_medicao`, porque ele muda a cada edição de
   qualquer arquivo medido.
3. Tirar "RASCUNHO" do título, do status e do nome do arquivo, e ajustar os
   links que apontam para o nome antigo.
4. Colar no texto os seis hashes do §4. A medição recusa se faltar algum.
5. Publicar o SHA-256 do arquivo congelado.

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
- commit;
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
