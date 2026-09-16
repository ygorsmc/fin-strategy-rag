# Revisão da conferência do parecer B-DFC-01J

**Data:** 2026-09-11. **Objeto:**
[conferência do outro agente](conferencia_parecer_b_dfc_01j_2026-09-11.md),
incluindo a alteração do item 25 do AGENTS.md e as perguntas de sua §7.

## Veredito

**A conclusão técnica da conferência está confirmada, com ressalvas de
documentação e rastreabilidade.** Reexecutei os dois blocos de contraprovas:
as seis saídas conferem. A linha do item 25 descreve corretamente um instrumento
ainda pendente; não afirma aprovação para treino.

Isso **não é uma nova correção de código**. C1–C6 continuam abertos, J elegível
continua vazio e G0 continua reprovado. Não encontrei, nesta conferência, erro
que derrube as seis contraprovas ou justifique restaurar o J antigo.

**Nova execução da suíte completa: 1.953 passed, 30 warnings, zero skips,
114,14 s.** Resultado medido nesta rodada, não inferido de datas de arquivos.

## 1. Ressalvas da revisão

### R1 — O estado documental ainda é contraditório fora da linha corrigida

**Fontes:** conferência §4, linhas 254–258;
[AGENTS.md](../AGENTS.md), §3.17, linhas 968–972;
[becos sem saída](becos_sem_saida.md), §C-bis, linhas 197–257;
[piloto](piloto_bancos_dfc_2026-09-09.md), linhas 14–22;
[extensão](extensao_janela_dfc_2026-09-09.md), linhas 16–24.

A conferência reconhece que deixou a linha 972 e os relatórios antigos fora do
escopo. Não é defeito introduzido por ela nem razão para rejeitar a correção
restrita solicitada ao autor. Entretanto, a lacuna efetiva é maior que uma linha:

- A própria retratação do AGENTS.md ainda diz “Corrigido o instrumento” e que
  a exigência de aproximadamente 16 emissores deixou de existir como medição.
  A tabela do item 25 e o JSON atual dizem o contrário.
- Os avisos intitulados “RETRATAÇÃO ATUALIZADA” no piloto e na extensão ainda
  apresentam **15 intervalos** como resultado vigente. O artefato atual tem
  **zero intervalos**, 24 pacotes não identificados e um sem fonte.
- O registro de becos sem saída ainda diz **“G0 FOI RESOLVIDO”**, apresenta
  G2=1,0464 e condiciona a reabertura a um “J limpo que não existe”. Não contém
  ali um aviso local da revisão que invalidou essas conclusões.

**Impacto:** outro agente pode seguir um estado superado, sobretudo porque o
AGENTS.md manda consultar os becos sem saída antes de propor nova investigação.
Não basta que a ressalva correta exista em outro arquivo.

**Ação recomendada, não executada nesta revisão:** sincronizar os avisos de
estado vigente em uma onda documental curta. Preservar os números antigos como
históricos/invalidados, com ligação para o parecer; não apagá-los nem apresentá-los
como resultados correntes. Não é necessário esperar a implementação de C1–C6.
Preferir “o cálculo continua publicado, mas está invalidado” a “deixou de existir”.

### R2 — A prova de não-mutação é mais limitada que o texto afirma

**Fonte:** conferência, linhas 23, 96–98, 256–257 e §5, especialmente
285–306. A ressalva sobre ausência de versão no HEAD em §3.2 é correta,
mas impede a conclusão mais forte publicada depois.

- `mtime` antigo é compatível com arquivo inalterado, mas **não prova identidade
  de conteúdo** contra o início da sessão. Não substitui snapshot/diff ou hashes
  antes/depois.
- `git status` limpo não certifica os PDFs, painéis ou demais arquivos ignorados.
  Os hashes dos dois DuckDBs conferem com os hashes completos do documento;
  essa comparação certifica esses dois conteúdos, não o workspace inteiro.
- Os três scripts e três arquivos de teste do candidato continuam **untracked**.
  A linha 25 tampouco existe no HEAD. Sem snapshot anterior, não é possível
  atribuir pelo `git diff` cada alteração não commitada à sessão que a fez.
- “Só AGENTS.md foi tocado hoje” e “MEMORY.md não tocado nesta sessão” não
  descrevem integralmente o pacote encontrado: **antes de qualquer edição minha**,
  MEMORY.md já referenciava a própria conferência, e seu mtime era
  **11/09/2026 13:40:38 −03:00**, posterior ao documento (**13:39:59**) e ao
  AGENTS.md (**13:36:30**). Isso é compatível com atualização de handoff posterior;
  não permite inferir autoria ou alteração indevida. O relato de escopo precisa
  contemplar a versão efetivamente entregue.
- Não rerodar testes em uma alteração documental pode ser proporcional. Mas
  “1.953 continuam valendo por construção” excede a evidência: a execução depende
  também de dados, dependências e ambiente, não apenas dos `.py`.

**Impacto:** o documento mistura declaração do executor, indício de não-mutação
e verificação de conteúdo. Não encontrei evidência de adulteração de código;
o problema é a força da certificação, não uma acusação de mutação.

**Ação recomendada:** separar “não alterei”, “comparei estes hashes” e “não tenho
snapshot anterior”. Descrever testes não reexecutados como último resultado
conhecido, atribuído à rodada que os mediu. Para a próxima implementação,
registrar um snapshot/diff ou hashes dos arquivos em escopo antes e depois.

## 2. O que foi confirmado por execução

Os comandos da conferência §§2.1–2.2 foram executados a partir da raiz,
sem invocar os `main()` que reescrevem artefatos. Os dois `assert` iniciais
passaram: auditor e sensibilidade reproduzem os JSONs atuais.

| Contraprova | Saída desta rodada | Interpretação |
|---|---|---|
| C1 | constante: `0.0` com classes alternadas; `1.0` com classes agrupadas | Empates continuam transformando ordem de entrada em associação |
| C2 | `−6.907755278982137` | Mesmo montante em milhares/milhões ainda gera queda artificial |
| C3 | T2/2024 `False`; T3/2024, T4/2024 e T1/2025 `True` | G1 ainda aceita horizontes além de q(D) para D=02/05/2024 |
| C4 | B1=`0.2`; B2=`0.5` | Antecedentes indisponíveis em D ainda entram nas previsões |
| C5 | `confere=True`, `independente=True`, motivo `None` | Acumulado derivado ainda pode receber certificado independente |
| C6 | `True`, `None`, `16` / `True`, `None`, `60` | A sensibilidade ainda apresenta poder invalidado como decidível |

Reproduzi também o subcaso de C4 sobre suporte: três bancos na população,
baseline eleito cobrindo só A. G3 devolve `melhor_baseline='BX'`,
`emissores_independentes=3`, `trimestres_por_emissor={'A': 2}` e
`emissores_necessarios_para_o_gate_decidir=0`. `aprovado=False` permanece.
É resíduo já descrito no parecer, não novo bloqueio descoberto nesta rodada.

### Alegações herdadas que agora receberam conferência adicional

A conferência §6, item 3, nomeava a baixa do G2 e das identidades anuais como
afirmações herdadas sem nova medição. Conferi:

- **G2=1,0464:** não aparece na saída atual do gate. O estado é “Alvos
  insuficientes para medir ruído/sinal”. Ambos os cenários de intervalo da
  sensibilidade também saem sem os campos numéricos de G2.
- **Identidades anuais:** reconstruí os objetos `Fato` do JSONL e executei
  `conferir_identidade_trimestral`. A lista reproduz **exatamente os 51 registros**
  de `extensao/conferencias.jsonl`. São 12 semestrais e 12 de nove meses
  conferidos/independentes; cinco semestrais, cinco de nove meses e **17 anuais**
  não verificáveis/não independentes. Não existe certificado anual 15/15 atual.
- **População:** 198 registros J, todos `nao_identificado`; zero observações
  elegíveis e zero alvos no auditor. A largura exportada ainda é zero em 198/198,
  por representação sentinela, não por precisão demonstrada.
- **Piloto:** o JSON mantém 25 pacotes, 24 com fonte e um sem fonte; zero
  identificados, zero limitados e 24 não identificados. Não refiz a leitura
  integral dos PDFs nem a adjudicação econômica das rubricas.
- **Linha 25:** cinco delimitadores de coluna, igual aos itens 21–24; a célula
  não foi partida. O texto vigente corresponde ao trecho “depois” da conferência.

O caso C5 sintético não demonstra que os 24 certificados atuais sejam inválidos.
As contraprovas C2/C4 tampouco demonstram um novo backtest real contaminado:
hoje não há população elegível. São falhas latentes nos consumidores.

## 3. Respostas às três perguntas deixadas pelo autor

1. **Mudar o rótulo da etapa 25?** Não é obrigatório: “NÃO AUTORIZA, e o
   instrumento de medição ainda não está fechado” já comunica as duas coisas.
   “NÃO AUTORIZA TREINO — correção do instrumento pendente” seria uma alternativa
   mais curta, não uma mudança de veredito. A conferência pode ser concluída
   enquanto a implementação continua pendente.
2. **Corrigir a linha 972 agora ou junto com C1–C6?** Em onda documental curta,
   sem esperar o código, incluindo os avisos locais listados em R1. Esta revisão
   não fez essas alterações nem recebeu autorização para implementar os reparos.
3. **Pré-registrar empates e ausência de limites?** Registrar os contratos e
   os testes de aceitação **antes da implementação**, sem escolher uma política
   pelo desempenho observado. Para empates: não usar classe, emissor ou ordem
   de entrada como evidência da variável; declarar comportamento para constante
   e para quantidade insuficiente de grupos distintos. Para limites ausentes:
   ausência explícita, schema versionado e consumidores que recusem ausência
   devem substituir a aparência de precisão zero, preservando zero verdadeiro
   como caso distinto. Isso não exige fingir um novo experimento científico
   para corrigir representação. **Para medir desempenho novamente**, porém, é
   necessário novo protocolo: o pré-registro antigo já foi invalidado por sua
   própria §7. Nenhum número antigo pode ser herdado como confirmação.

## 4. Reprodução e identificação da versão revisada

Os dois blocos executáveis de [§2 da conferência](conferencia_parecer_b_dfc_01j_2026-09-11.md)
reproduzem C1–C6. Para testes e integridade dos painéis:

```bash
CREWAI_STORAGE_DIR="$(mktemp -d /tmp/bdfc-reconferencia-crewai.XXXXXX)" .venv/bin/python -m pytest -q --tb=short
sha256sum artefatos/cvm.duckdb artefatos/cvm_treino.duckdb
```

Saída da suíte: `1953 passed, 30 warnings in 114.14s (0:01:54)`, zero skips.
Warnings de dependências, AUC com classe única e features vazias na suíte
preexistente não são testes pulados nem treinamento deste candidato.

Hashes medidos nesta rodada — identificam esta versão, **não provam
retrospectivamente** o que outro agente modificou:

```text
79d9de4efecabd113efe0ab9782b10a5a8a24f791543d29dd633725ae112f753  scripts/auditar_prontidao_b_dfc_01j.py
724500b79649673266f4198848c61d5af358f91cd2760edcd12021a216d05fff  scripts/piloto_bancos_dfc.py
d4ec995138b8c6211321e8720d19f051e4a28df54ff2b86f6bad5ca9b821e616  scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py
665f5475beb4cebfe2047ab0ca5e09f50864e31ae62a3b0425e4ce35ea9c97ff  tests/test_prontidao_b_dfc_01j.py
9ff2f3996c499f4cbb86697ee6330a327ff6a9a4e7a29543ce8e935fba03549a  tests/test_piloto_bancos_dfc.py
52450e8321994b3d37d47178b97a6ae9dffb37f2158e7d8299b4cafa854d914c  tests/test_sensibilidade_b_dfc_01j.py
370b692e036cdab1609ebb47739c406d4b8eeb908d93d549e680bb351c130090  artefatos/b_dfc_01j/prontidao/gates.json
72b0bf6747cdaf107059e7e758e61c9248d5cc3dd00fd9be074d62cfbc8e8a2d  artefatos/b_dfc_01j/prontidao/sensibilidade.json
b7382f37fdfce67caae4a9a92f794783ee37c4523d5430a2abbc7d3c53b0bf43  artefatos/b_dfc_01j/extensao/conferencias.jsonl
43e31d9f150e535f1ab20576d9aacf1a53b83ecc5424ca7d48ba50781e4cef18  artefatos/cvm.duckdb
c1a604453a9a2fa7df24b0b2dbc53df6fb5ef0d39fd06f492407028030bc069b  artefatos/cvm_treino.duckdb
```

## 5. Encaminhamento e limite desta rodada

**A próxima ação útil é implementar as correções conhecidas**, com contrato,
contraprovas e revisão de conformidade ao fim da onda; não repetir a mesma
conferência como substituto da implementação. O parecer anterior §5 continua
sendo a lista técnica, acrescida da sincronização documental R1 e do cuidado
de rastreabilidade R2. Não surgiram nesta rodada seis defeitos adicionais.

O piloto documental por família econômica pode continuar sem usar o auditor
pendente como certificado. Isso não autoriza treino nem altera a exigência
de protocolo novo, disponibilidade documental e comparação M0/M1.

Nesta rodada escrevi somente **este relatório e o handoff de MEMORY.md**.
AGENTS.md, documentos anteriores, código, testes, artefatos, painéis e PDFs
foram preservados. Não fiz commit/merge, pesquisa web ou chamada paga; não
acessei o holdout. Não convoquei novo especialista: esta é conferência local de
documento, código e saídas, não um novo debate ou aprovação independente do
modelo. Caches e temporários normais da execução dos testes não são entregáveis.
