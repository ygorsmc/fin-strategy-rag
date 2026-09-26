# Conferência independente das correções RF-01 a RF-08 — Rank 3-B

Data: 2026-09-17. Escopo: implementação de pré-treino, sem medir o alvo real.

## Parecer

**Aprovação parcial. Não congelar o pré-registro v2 ainda.** As correções
resolveram o erro monetário da antiga ESC-0101, reproduziram o painel novo e
fecharam vários defeitos estatísticos e de procedência. Restam **dois achados
P2** no instrumento e **um P3** de documentação, descritos abaixo.

Não foi demonstrado outro valor monetário real errado, nem vazamento temporal
na execução governante atual. Isso é diferente de certificar que as 68
correções de escala estão economicamente corretas: a regra ainda aceita
correspondências que não provam a identidade contábil exigida.

Esta conferência não rejeita a hipótese de ML e não autoriza treino. Além dos
achados, continuam as cinco decisões de política e o executor v2 que a própria
entrega declara pendentes.

Fontes da entrega:

- [Relatório RF-01 a RF-08](correcao_rf01_rf08_rank03b_2026-09-17.md).
- [Contratos RF-01 a RF-08](contratos_correcao_rf01_rf08_rank03b_2026-09-17.md).
- [Pré-registro v2, ainda rascunho](pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md).
- [Reproduções e evidências desta conferência](../artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/).

Resumo verificável: [evidencias.json](../artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/evidencias.json),
com resultados, limites de cobertura e hashes comparados entre início e fim.

## 1. CRF-01 — P2: mesma linha e magnitude não provam a mesma conta

**Local:** [fonte_rad_cvm.py](../scripts/fonte_rad_cvm.py), linhas 863–873 e
944–967, em evidencia_numerica_localizada.

A v3 é substancialmente melhor que a busca de magnitudes da v2. Entretanto,
testa se o rótulo e o número aparecem na mesma linha física; não estabelece
que o número pertence à célula/conta daquele rótulo. A restrição ao valor
consolidado corrente seleciona os candidatos do formulário, mas não identifica
o perímetro e a coluna do trecho encontrado nas notas.

### 1.1 Evidência real: ESC-0029

| Campo | Identificação |
|---|---|
| Linha do manifesto vigente | 30, ESC-0029 |
| Companhia / período / documento | CVM 021717; ITR 2018-06-30; documento 76468 |
| Decisão publicada | UNIDADE → MIL |
| Único casamento numérico publicado e reproduzido | conta 6.04; forma bruto; anexo de índice 2, página 12 |
| Contagem reproduzida | bruto = 1; dividido = 0; multiplicado = 0 |
| Trecho mascarado | “ajuste de variação cambial [valor de caixa omitido]” |

Fonte primária local:
[76468.zip](../artefatos/painel_pesquisa_rank03b/rad/brutos/76468.zip),
SHA-256
4875c76f8407b0db1377c8249e6f67742eb4b25ee19031b1c4aba117c6dc9e3b.
A página citada é a do anexo, não a página global de um PDF concatenado.

A releitura do contexto mostra **Nota 10 — Investimento**, tabela
**“TISA NY, Inc. — Movimentação do investimento (Em milhares de reais)”**.
A linha de ajuste cambial está entre equivalência patrimonial e valores pagos
à controladora pelo desinvestimento. Isso não identifica o efeito cambial
sobre caixa e equivalentes consolidados que se pretende corroborar.

A distinção não é só terminológica: o CPC 03 separa os efeitos cambiais sobre
caixa da geração de fluxos e dos ganhos/perdas cambiais não realizados.
[CPC 03 (R2), item 28, fonte CVM](https://conteudo.cvm.gov.br/cvm_institucional/export/sites/cvm/menu/regulados/normascontabeis/cpc/CPC_03_R2_rev_13.pdf).

**Conclusão limitada:** a evidência publicada não demonstra a correspondência
contábil alegada. Ela pode coincidir numericamente por razões econômicas
explicáveis, e a escala MIL pode estar correta por outra evidência. Esta
conferência **não provou que ESC-0029 tenha valor monetário errado** e não
autoriza inverter sua escala ou excluir a companhia.

### 1.2 Contraprova sintética: outra conta na mesma linha

Formulário consolidado corrente: caixa = 900.000, declarado em UNIDADE.
Notas em milhares: caixa = 900; fornecedores = 900.000. Nesse exemplo, a
declaração original de caixa está correta.

| Apresentação nas notas | Resultado do mesmo algoritmo |
|---|---|
| Caixa e fornecedores em linhas separadas | indecidível; não corrige |
| “Caixa e equivalentes de caixa 900    Fornecedores 900.000” | corrigida para MIL |

A segunda saída usa o valor de fornecedores como prova do caixa e introduziria
erro de 1.000× **nesse caso sintético**. A primeira é o controle negativo.
O limiar mínimo de magnitude da regra impede que o caixa de 900 seja usado
como evidência concorrente; o casamento indevido fica sem conflito.

Reprodução: [reproduzir_escala.py](../artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/reproduzir_escala.py).
O script também relê e readjudica o documento 76468, mantendo os números de
caixa mascarados na saída.

### 1.3 Critério de fechamento

Pré-contratar uma regra que ligue número, conta, unidade, período e perímetro
no trecho/tabela — ou que devolva indecidível quando essa ligação não puder
ser estabelecida. Acrescentar contraprovas de contas lado a lado e de
“variação cambial” fora da DFC, com controles positivos válidos.

Reavaliar as decisões alcançadas pela regra alterada e suas heranças, com
fontes e transições preservadas. ESC-0029 precisa de evidência adequada ou de
tratamento explícito de insuficiência de prova; não de exceção por ID.
Não ajustar a regra para recuperar a aprovação de G0.

Os buracos já declarados como B5 na entrega (por exemplo, unidade da página
versus unidade da tabela e grafias de rótulos) não são contados aqui como
descobertas independentes. O acréscimo é a contraprova de conta/célula e a
releitura de uma prova real vigente.

## 2. CRF-02 — P2: o G1 aceita um mapa de provas incompleto

**Local:** [gates_painel_pesquisa_rank03b.py](../scripts/gates_painel_pesquisa_rank03b.py),
linhas 131–155, 213–230, 299–305 e 323–330.

A guarda _exigir_provas recusa um mapa vazio quando existem correções, mas
não exige cobertura de todas as chaves corrigidas. No G1.4, uma chave ausente
é ignorada; na condição c3, a ausência retorna à data de recebimento do
documento. Assim, perder apenas uma entrada pode fazer desaparecer a
violação que a auditoria independente deveria encontrar.

O auditor de conformidade encontrou a falha em contexto separado. O agente
principal inspecionou e reexecutou a reprodução: dois documentos corrigidos,
com um mapa completo de duas provas e outro parcial de apenas uma. O
construtor sabotado ignora deliberadamente a data da prova; é uma injeção de
defeito exclusivamente sintética.

| Caso | G1 | G1.4 | c3 |
|---|---|---:|---:|
| Construtor correto, mapa completo | aprova | 0 | 0 |
| Construtor sabotado, mapa completo | reprova | 2 | 2, com exceção |
| Mesmo construtor sabotado, mapa parcial | **aprova** | **0** | **0** |
| Mapa vazio pela entrada medir | recusa com ProvasAusentes | — | — |
| Chamada direta g1_cego, painel sabotado, sem provas | **aprova** | **0** | não chamada |

Reprodução: [reproduzir_provas_parciais.py](../artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/reproduzir_provas_parciais.py).
O cálculo de rótulo é bloqueado por dublê que lança exceção.

**Alcance:** a execução canônica atual gera o mapa completo a partir do
manifesto e do cadastro. Na reconstrução real, as datas conferiram e G1.4
continuou zero. Portanto, isto **não demonstra vazamento no painel governante**
e não restaura a conclusão antiga das cinco observações afetadas. Demonstra
uma lacuna na guarda que deveria detectar uma regressão do construtor.

**Critério de fechamento:** exigir cobertura integral das chaves corrigidas
necessárias à certificação, datas válidas e coerência com suas fontes.
Entrada incompleta não pode ser tratada como prova inexistente nem como
recebimento original. Proteger também g1_cego quando usado para certificar
um painel corrigido, ou impedir explicitamente esse uso incompleto.
Testar mapa parcial, vazio, completo, controles sem correções e construtor
sabotado. Não basta conservar o teste atual de mapa totalmente vazio.

## 3. CRF-03 — P3: histórico e resultado vigente ainda se misturam

No pré-registro, §11.3, linhas 432–434, os diagnósticos do “painel governante”
ainda dizem **49 saltos** com A2/conflito incluídos; o registro vigente, logo
acima, diz **70**. O §11.4 também conserva 77/24 correções, dois trechos e os
resultados do piloto sob “regra final” sem identificar localmente todas essas
passagens como execução 2 substituída.

Além disso, o texto de construção produzido por
[auditar_rank03b_consumo_operacional.py](../scripts/auditar_rank03b_consumo_operacional.py),
linhas 884–887, descreve D como recebimento de cada documento, enquanto o
caminho do painel de pesquisa usa disponibilidade do FCO válido, incluindo
o atraso da prova de escala. A discussão da grade de D continua pendente
no próprio v2.

Fechamento: rotular o histórico por execução e tornar a descrição fiel à
grade usada. Preservar números antigos como histórico; não substituí-los
silenciosamente nem decidir a política estatística por edição de prosa.

## 4. O que foi confirmado

| Item | Resultado da conferência |
|---|---|
| RF-01, antiga ESC-0101 | Não é mais corrigida; documento 152742 tem ativo bruto = ativo em reais = 5.073.000, escala UNIDADE, base declarada |
| Manifestos | 101 → 68 correções: 62 permanecem, 39 saem, seis entram; nenhuma escala comum invertida; execução 2 preservada |
| RF-02, caminho canônico | Datas das provas recalculadas pelo cadastro; construtor respeita as provas; G1.4 = 0 no painel novo |
| RF-03 | Cortes nominais com extensão de empates e deduplicação; controles sintéticos e comparação do auditor com oráculo independente |
| RF-04 | G0.5 inclui heterogeneidade declarada OU aplicada: 56/22.088 = 0,2535%, incluindo as cinco linhas da classe antes omitida |
| RF-05 | B0 renomeado e com IC; contratos ampliados. Fechamento apenas parcial: cinco escolhas e executor v2 continuam pendentes, como declarado |
| RF-06 | Vínculos de versão e hashes do código de verificação correspondem aos arquivos atuais |
| RF-07 | Pares (trimestre, D) e chaves (companhia, D) nomeados separadamente; não tratar incidências como decisões distintas |
| RF-08 | AUC agregada igual a zero preservada como 0,0; ausência não é convertida silenciosamente em zero |
| V1 | Entrada programática normal exige correções validadas e verifica mudança do manifesto |

O auditor de conformidade verificou RF-03 contra 300 amostras sintéticas
aleatórias com empates, incluindo permutações. Seus 179 testes focados se
sobrepõem à suíte abaixo: **não são somados a ela**. Ele não recebeu o achado
CRF-01 antes de concluir a sua análise; a adjudicação contábil foi trabalho
do agente principal.

### 4.1 Reconstrução real, sem medir o alvo

[reproduzir_estrutura.py](../artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/reproduzir_estrutura.py)
reconstrói somente em memória a partir dos **31 ZIPs pinados** e consulta
o painel persistido com READ_ONLY. Resultado:

- Digest do conjunto: 1250cefb9a7276cec0642c722e1941b6e71262f965174dac9b34638014732e12.
- Comparação bidirecional EXCEPT ALL: **zero diferenças** em ativo,
  fco_acumulado e fco_trimestral.
- Cadeia G0/G1 reproduzida integralmente; **68 saltos**, **10.750 observações**,
  **503 companhias**, G1.4 = **0**.
- Todas as condições de falsificação implementadas retornaram zero.
- Datas das provas conferiram com uma consulta por ID no cadastro; nenhum
  ativo corrigido disponível antes da prova.
- Vínculo de versão das verificações e seus quatro hashes de código conferiram.

Reprodutibilidade do painel não equivale a validação econômica de cada
correção que entrou nele; CRF-01 é precisamente essa distinção.

### 4.2 Testes

Executados pelo agente principal:

- Seis arquivos focados: **351 passaram**, em 42,43 s.
- Suíte completa: **2.544 passaram**, zero skips, 30 avisos, em 167,71 s.
- As duas contraprovas adicionais acima foram reexecutadas separadamente.

Comandos, a partir da raiz:

~~~sh
.venv/bin/pytest -q tests/test_adjudicar_escala_rank03b.py tests/test_fonte_rad_cvm.py tests/test_gates_painel_pesquisa_rank03b.py tests/test_painel_pesquisa_rank03b.py tests/test_rank03b_consumo_operacional.py tests/test_verificacoes_revisao_final_rank03b.py

env CREWAI_STORAGE_DIR=/tmp/revisao-rf01-rf08-RzKe9U/crewai .venv/bin/pytest -q

PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/reproduzir_estrutura.py
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/reproduzir_escala.py
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/reproduzir_provas_parciais.py
~~~

A suíte existente passar não refuta contraprovas que ela ainda não cobre.

## 5. Limites e integridade desta conferência

Não houve nova adjudicação manual de todos os 68 casos, nem reexecução
concluída de todos os 405 documentos. A tentativa auxiliar de reler 60
pacotes não produziu resultado final antes da interrupção da sessão; não
é contabilizada como evidência. O script reler_fontes.py fica disponível
para repetição, sem alegação de conclusão. A releitura e readjudicação
pontual do documento 76468, por sua vez, **foram concluídas**.

A herança agora se apoia em um único trecho integralmente testável; isso está
declarado na entrega e cumpre o mínimo atual de S5. Não se inventou um novo
mínimo de trechos nem se impôs anotação humana de todos os documentos como
condição adicional nesta revisão.

Nenhum rótulo real, T1/T2 real, baseline real ou treino do candidato foi
executado. Nas reconstruções, _somas_do_rotulo foi substituída por uma função
que lança exceção. Nenhum acesso ao holdout, download de pacotes de dados
da CVM ou chamada paga.
A consulta web se limitou à norma contábil primária para a distinção do §1.1.

Foram acrescentados este parecer e reproduções/evidências em diretório próprio,
e atualizado MEMORY.md. Código operacional, testes existentes, manifesto de
correções, painéis e os três documentos revisados não foram corrigidos por
esta conferência. As alterações preexistentes no worktree pertencem à entrega
revisada e foram preservadas.

## 6. Próxima etapa delimitada

1. Escrever contratos para CRF-01 e CRF-02 antes de alterar a regra; corrigir
   com as contraprovas e controles positivos. Fechar também CRF-03.
2. Reavaliar as adjudicações afetadas e suas heranças; reconstruir somente o
   painel de pesquisa se houver mudança. Preservar as execuções anteriores e
   explicitar a exposição desta conferência no histórico do pré-registro.
3. Resolver as cinco escolhas já existentes: seguradoras (§3.2), interpretação
   de G0.1 (§5.1), adoção/limiar de G0.5 (§5.5), grade de D (§6.1) e suporte
   intra de T2 (§8.1).
4. Implementar e testar em sintético o executor v2, mantendo G0/G1 cegos antes
   de qualquer cálculo do alvo. O executor antigo não deve ser reutilizado
   integralmente: ainda monta o rótulo antes dessa barreira.
5. Conferir a nova entrega, aprovar o protocolo e congelar seus hashes. Só
   então executar as medições autorizadas pelo v2. O treino do primeiro
   desafiante depende do veredito PRONTO PARA CHALLENGER; não decorre apenas
   de G0/G1 aprovados.

São pendências delimitadas de instrumento e protocolo, não um novo veto
conceitual ao uso de DFC em ML.
