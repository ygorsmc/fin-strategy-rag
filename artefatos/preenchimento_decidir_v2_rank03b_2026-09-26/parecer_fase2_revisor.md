<!--
Parecer da fase 2 do revisor independente (auditor-conformidade, somente leitura,
mesmo contexto da fase 1), devolvido em 26/09 sobre a proposta do preenchedor
(SHA-256 5c0e72b95b0c6322ddfd1d41afd1d7b261382e928cd3758ae0fc0bafc4ef31e0, cópia em
proposta_v1_revisada.md). Transcrito na íntegra. É saída de modelo, não decisão
humana. O orquestrador conferiu o E1 no código (src/dados_estruturados.py:1325,
1342–1346, 1486, 1500–1504; chave_pareamento sem demonstrativo) e o E2 no texto da
própria proposta.
-->

# Fase 2 do Rank 3-B v2: proposta apta com ressalvas, dois erros de fato a corrigir

A proposta pode ir ao responsável depois de corrigidos dois erros de fato. Os dois estão em textos que entrariam no rascunho e nenhum muda a escolha do preenchedor. Há duas divergências de julgamento (§5.5 e §6.1), que vão como alternativas.

**Objeto:** `/home/ygor/Antigravity_Projects/fin-strategy-rag/resultados/proposta_preenchimento_decidir_v2_rank03b_2026-09-26.md`. O SHA-256 confere com o informado (`5c0e72b9…31e0`). Os aliases usados abaixo (RASC, V1, LB, LC, AUD, GAT, VER etc.) são os da tabela §0.2 da proposta.

**Método:**
- Li a proposta inteira e abri as fontes citadas nos sete itens. Todas dizem o que a proposta afirma, exceto nos pontos marcados abaixo.
- Li também código que a proposta não cita: `src/dados_estruturados.py`.
- Nada foi executado além de `sha256sum`, `sed` e `grep`. Não abri DuckDB, RAD nem PDF, e não li valor de FCO. Minha exposição é a mesma da fase 1 (a taxa-base do §11), e não a usei.

**Regras:**
- **Nada aparece como aprovado:** há aviso no cabeçalho, `[data]` nos textos prontos e o §11 da proposta diz que não decide nem aprova.
- **Nenhuma escolha se apoia em número de desfecho**, e a exposição é declarada item a item.
- **O limite "82 × 12 ≈ 1.000 observações"** é aritmética sobre contagens estruturais já publicadas, o que o O1.2 permite.
- **§4.4:** as regras 4, 7, 8 e 9 são respeitadas; todo item que cria estado novo traz contraprova da decisão.

## Veredito por item

### §3.2 Seguradoras — CONFERE COM RESSALVA
- A escolha é idêntica à minha e as fontes conferem (V1:62–68 e 96–111; LC:26–30; LB:294–296; CONF17:292–294; MED `companhias_por_plano`). O texto pronto se aplica como está.
- **Ressalva — G0.3 depois da exclusão:**
  - O §0.4 afirma que "nenhuma das sete decisões altera G0.3". A exclusão muda o universo, e com isso o numerador e o denominador do G0.3 — o próprio item manda medir G0 e G1 de novo. O certo é "nenhuma faz o G0.3 passar".
  - O texto deveria mandar publicar quantos dos 132 saltos saem junto com as três companhias. Assim nenhum ganho no G0.3 vem, sem declaração, de remoção (regra 9).

### §5.1 G0.1 — ERRO (a escolha confere; a justificativa histórica não)
- A escolha é a minha: unicidade, checagem de soma MD+MI, contagem publicada e contraprovas.
- **ERRO E1:** o texto pronto (linhas 239–242) e o julgamento (287–291) afirmam que o trimestre derivado entre métodos "não existia no painel para o qual a frase foi escrita".
  - O fato citado (fato 3, os grupos N2) cobre só a derivação do 2T e 3T. Essa derivação particiona por demonstrativo (`/home/ygor/Antigravity_Projects/fin-strategy-rag/src/dados_estruturados.py:1342–1346`).
  - A derivação do 4T no mesmo painel junta DFP anual e ITR de 9 meses **sem demonstrativo**: o join é por companhia, chave de pareamento e início do exercício (`:1500–1504`), e a linha gravada leva o demonstrativo da DFP (`:1486`).
  - Portanto um 4T derivado entre métodos era possível no painel da v1 (`cvm_treino.duckdb`, V1:118). Não verifiquei se existiu de fato, porque isso exigiria abrir o DuckDB. A afirmação "não existia" não tem fonte.
- **Correção sugerida, que fortalece a conclusão:** o G0.1 que a v1 executou (AUD:407–415) conta só pares (companhia, trimestre) com mais de um demonstrativo. Um 4T derivado entre métodos carrega um único demonstrativo e nunca foi contado. A unicidade é, portanto, a leitura que a v1 de fato aplicou.
- **Ressalva menor:** a frase "o critério de refutação nunca foi cumprido" (LCR:258) é ausência de teste, não evidência. Sem nenhum documento com os dois métodos (MED), esse teste é impossível dentro do mesmo documento.

### §5.5 G0.5 — DIVERGE na escolha + ERRO no texto pronto
- **Onde concordamos:**
  - G0.5 decisivo.
  - "Decidido" medido pelo FCO, como na minha fase 1.
  - Rejeitar os 0,5% contados em trimestres, porque é o denominador errado (regra 8).
  - Conferi o exemplo sintético: −299.500 e +499.700 estão certos.
- **Divergência:** a proposta escolhe C — censurar só o trimestre derivado de acumulados com escalas diferentes. Deixa fora, por padrão, a opção E, que censura também as somas entre trimestres de escalas diferentes que não foram derivados um do outro. Eu adotaria C+E, que é a própria opção E da proposta. Três razões:
  1. **O resíduo atinge rótulo e elegibilidade.** Um 1T isolado mal rotulado entra no TTM e em S2 sem que haja trimestre heterogêneo na mesma janela. Há 71 trechos de um só documento em companhias mistas (MED `trechos_em_companhias_mistas`).
  2. **O argumento contra E não separa E de C.** A proposta diz que E "sobrepõe-se à tolerância que a v1 congelou no G0.3" (V1:132, 135–137). Isso vale igualmente para C: os trimestres que C censura ficam sobre as mesmas transições dentro do exercício que o G0.3 conta.
  3. **A perda de E pode ser medida antes de decidir.** É contagem sem rótulo (O1.2), como a proposta admite para C.
- **ERRO E2:** o texto pronto (linhas 389–392) diz que esses casos "continuam cobertos só pelo G0.3, no ativo".
  - Isso é falso para erro de escala consistente, sem transição no ativo. Exemplo: as 17 companhias só `UNIDADE` (400 documentos, MED `rotulos_de_escala`) não geram salto, e nenhum gate as cobre.
  - O próprio trecho "O que não se pode alegar" da proposta (linhas 501–506) diz a coisa certa. O texto pronto é que está errado.
- **Ressalva:** a censura não tem teto de perda. Deve-se publicar ao menos a fração de companhias do universo perdida, e não só as observações.

### §6.1 Grade de D — DIVERGE
- A grade escolhida é a mesma que eu propus, e as fontes conferem (AUD:657, 664 e 712–721; R15:131; GAT:212; LC:121–124 e 191; CRF:87–92; CRF18:73; LB:127; AG:587–589).
- **Divergência — deduplicação:** a proposta não deduplica e diz que "toda inferência agrupa por companhia". Eu manteria uma observação por (companhia, q1), a de maior D.
  - Agrupar por companhia corrige o erro-padrão, mas não o peso extra que as quase-duplicatas têm nas estimativas pontuais: as taxas por faixa do T1 e a AUC agregada. A proposta reconhece esse risco (linhas 640–641).
  - O argumento de horizonte homogêneo, que a proposta usa contra a grade de calendário, favorece a deduplicação.
    - Uma DFP recebida ou reapresentada depois de 31/03 e o ITR do 1T em maio geram o mesmo q1 (AUD:743–759).
    - O primeiro tem horizonte de três trimestres depois da âncora; o segundo, de dois.
    - Ficar com o maior D elimina justamente o caso irregular.

### §8.1 Suporte da AUC intra — CONFERE
- É idêntico à minha posição: 30 companhias com os dois rótulos; abaixo disso, INDECIDÍVEL.
- **Fontes:** conferem (AUD:94–100 e 1135–1147; V1:174–177; AG:782–786; CONF17:218–219; LEV:222).
- **Aritmética:** confere (0,5/√30 = 0,091; 0,5/√17 = 0,121, acima de 0,12).
- **Exposição:** dizer que a taxa-base "permite prever" que 30 companhias existem é exposição honesta. O número vem de V1:174; eu cheguei a ele sem essa inferência.
- **Opcional:** publicar o IC da lacuna por reamostragem de companhias, sem papel decisivo.

### §12-bis Alcance da prova — CONFERE COM RESSALVA
- A escolha B, estendida ao que o G0.5 conta como "decidido", é a da minha fase 1. As fontes conferem (RASC:524–530 e 544–547; LB:120 e 128; LC:242–245, 252–264 e 386; ALC:177–180, 193–198, 209–211 e 284–290; GAT:288–299; AG:549–551).
- **Ressalvas:**
  - **(a) O que prova a conta `1`:** o texto não diz se só vale a célula direta da `1` ou também `2` e `1.01.01`, como na v4. As "quatro ligações" do rascunho implicam prova direta; é preciso escrever isso.
  - **(b) Frase incoerente:** "Correção só do ativo continua vedada enquanto G0.3 e G0.5 lerem o veredito por documento" não combina com o G0.5 por FCO que a própria proposta cria. Deve se referir só ao G0.3 e ao esquema do manifesto.
  - **(c) Erro demonstrado sem correção:** sob B, o ativo de 140867 continua errado. Precisa ser registrado como erro conhecido, pendente de G0.3 por conta, e não ficar em silêncio (RASC:238–239).
  - **(d) Rota por identidade da DFC:** o status dela sob o O1 fica em aberto (§10.3 da proposta).
    - Minha leitura é que o O1.2 permite identidades com saída booleana (LB:93–95). O painel já calculou esse fechamento somando o 6.01 (`scripts/painel_pesquisa_rank03b.py:497–515`).
    - A rota ainda exige contrato próprio. Também aceito o argumento da proposta: exige teste pré-registrado fora dos documentos de desenho da GEOM-1.

### O1 Exceção protetiva — CONFERE COM RESSALVA
- A escolha (aprovar com condições) é a minha, e os fatos conferem (LB:90–98; VER:560–572, 588–625 e 668–673; CRAG:129–135 e 162–165; ALC:251–264 e 302–306; CPEND:73–86; PEND:17; RAG:261; ARAG:134–143).
- **Ressalvas:**
  - **(a) Recusa como oráculo:** a cláusula 5 não diz o que acontece depois de uma recusa. O "um bit por execução" vira oráculo se a execução puder ser refeita com a saída alterada. Falta: "a recusa encerra a execução; nova execução exige registro do incidente e contrato novo".
  - **(b) Comparativo:** a cláusula 2 fala em "documento e período em exame", mas as formas enumeradas incluem o comparativo do exercício anterior (`consolidado_acumulado_anterior`, VER:670). Deve dizer "as formas enumeradas, inclusive o comparativo".
  - **(c) Retroatividade incompleta:** a cláusula 7 e o fato 5 datam as execuções em "25/09". As execuções de 26/09 da mesma onda RAG (adendos 2 e 3, RAG:333–340 e 401–408) também calcularam piso e teto sobre o FCO real: a busca passa todas as formas do FCO à autoverificação (VER:816, 863–864). O certo é 25–26/09.
  - **(d) §11 do v2:** a proposta não manda declarar essas exposições ali. Faltam as leituras de FCO por igualdade de 24 a 26/09 e o piso/teto calculado em memória em 25–26/09. O §11 atual não traz nenhuma das duas.

## Ressalvas transversais
1. **Congelar agora consome o v2.**
   - Aprovar as sete decisões não é congelar o pré-registro. Os pins do rascunho (§4 e §13: digest `6ca635a9…`, manifesto `13520e61…`) descrevem um painel com G0 sabidamente reprovado (132 saltos, limite 112).
   - Congelar com esses pins consumiria o v2 com o veredito já conhecido.
   - A proposta condiciona o congelamento ao executor testado e à conferência independente (§9), mas não à resolução estrutural do G0. Isso deve ser acrescentado, com o O1 vigente até lá. A cláusula do adendo "até o congelamento" ajuda.
2. **Erro de escala consistente continua sem gate.** O caso das 17 companhias só `UNIDADE` está declarado no §5.5 da proposta, mas o texto pronto o contradiz (é o E2).

## Onde mudei de ideia em relação à fase 1
1. **§5.5, limiar:** abandono meu limiar 2m/n_min < 0,03. A censura converte contaminação em perda inventariada antes de montar y, sem precisar escolher um δ. Mantenho a população ampliada (E).
2. **§5.5, direção da contaminação:**
   - Aceito que a contaminação tende a favorecer a aprovação no componente previsto (`fco_ttm_sobre_sd8`). Um trimestre errado por mil infla o `sd8` e empurra a observação para a faixa "perto de zero", diluindo a taxa da faixa de risco.
   - Minha tese das faixas extremas não fixava direção. Isso reforça eliminar em vez de tolerar.
3. **§5.1:** retiro a ressalva de chamar a decisão de "redefinição, não leitura". AUD:407–415 mostra que a v1 executou a unicidade.
4. **§12-bis, "0 de 22.486 documentos":**
   - O dado de nenhum documento com mais de uma escala é verdade por construção: a escala declarada é uma por formulário (LB:128). Eu o citei como se sustentasse a escala verdadeira.
   - A cadeia de identidades continua admissível, mas só depois de teste pré-registrado fora dos documentos de desenho. Já se sabe que os dois candidatos da GEOM-1 satisfazem 6.05.02 = 1.01.01.

## Veredito geral: APTA COM RESSALVAS

## Erros a corrigir
- **E1 — §5.1** (texto pronto nas linhas 239–242 e julgamento nas linhas 287–291).
  - *O que está errado:* a frase "o trimestre derivado entre métodos não existia no painel para o qual a frase foi escrita". A fonte citada cobre só o 2T e 3T. O 4T do painel compartilhado pareia sem demonstrativo e grava o da DFP (`src/dados_estruturados.py:1500–1504` e `:1486`).
  - *Correção:* trocar pelo fato verificável — o G0.1 implementado da v1 contava só grupos com mais de um demonstrativo (AUD:407–415).
- **E2 — §5.5** (texto pronto nas linhas 389–392).
  - *O que está errado:* a frase "esses casos continuam cobertos só pelo G0.3, no ativo" é falsa para erro de escala consistente, sem transição.
  - *Correção:* "o G0.3 só os vê quando há transição detectável no ativo; erro consistente sem transição não é coberto por gate nenhum".
