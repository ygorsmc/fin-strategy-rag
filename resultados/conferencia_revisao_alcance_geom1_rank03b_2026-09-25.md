# Conferência independente da revisão do alcance GEOM-1

Data: 2026-09-25. Escopo: contratos de revisão de 24/09, adendo de 25/09,
relatório de alcance e evidências em `revisao/`. **Aprovação parcial:** os
resultados documentais publicados reproduzem, mas há três defeitos técnicos
reproduzíveis e um resíduo documental. Não sustento o fechamento integral do
instrumento. Nenhum deles demonstrou erro monetário real, vazamento de FCO
real ou alteração dos painéis nesta onda.

**Não autoriza treino, correção de escala ou integração GEOM-1.** A revisão
não mudou código operacional, testes existentes, contratos, CSV, gates ou
painéis. Foram escritos apenas este parecer, evidências próprias e o handoff.

## Achados, em ordem de impacto

### RAG-01 — P2: a reconferência não vincula o pin que escolhe as fontes

Fonte: `scripts/conferir_alcance_geom1_rank03b.py:390`, especialmente
linhas 396–403. N1 verifica os hashes de três arquivos publicados, incluindo
`pin_revisao.json`, mas depois lê **outro** arquivo, `BASE/pin.json`, sem
compará-lo com o `pin_alcance_sha256` que consta daquele pin já verificado.
É o arquivo não verificado que fornece a lista de fontes e seus hashes.

Contraprova executada: em diretório temporário, copiar o inventário intacto e
fornecer `pin.json` com `fontes: []`, cujo hash é diferente do registrado.
Manter `pin_revisao.json`, `conferencia_revisao.json` e os sete protegidos reais
intactos. A função **termina e grava**:

- zero documentos examinados, apesar de dois no pin verificado;
- as duas autoverificações como `true`;
- sete protegidos conferidos.

`comparados` fica vazio; a verificação de strings contra valores da fonte
deixa de testar qualquer valor. Portanto, verificar as saídas não basta para
certificar a reconferência que usa outra entrada para definir seu universo.
O pin real atual confere; **não foi constatada adulteração histórica**.

Critério de fechamento: validar o hash do pin de alcance contra a referência
já fixada **antes de consumi-lo**, exigir o mesmo conjunto de fontes e recusar
ausência, retirada, duplicação ou substituição. Acrescentar contraprovas do
caminho `reconferir_publicados`, com controle positivo dos dois documentos;
não apenas testar `conferir_fontes` isoladamente.

### RAG-02 — P2: a busca exata admite correspondência parcial e perda de sinal

Fonte: `scripts/conferir_alcance_geom1_rank03b.py:95`, linhas 98–108,
consumidas em `ocorrencias` (linha 112). O regex não delimita o token numérico
inteiro; o entorno de sinal aceita espaços de forma incompleta e não inclui
moeda entre parêntese/sinal e dígitos.

Contraprovas **sintéticas**, passando por `ocorrencias(..., por_modulo=False)`:

| Texto inventado | Alvo inventado | Resultado indevido |
|---|---:|---|
| `Total 1.234.5678` | `1234567` | Casa o prefixo e interpreta o último dígito separadamente |
| `Total -  1.234` | `+1234` | Perde o menos separado por dois espaços e casa positivo |
| `Total (R$ 1.234)` | `+1234` | Perde a negatividade contábil dos parênteses e casa positivo |

O contrato R3 exige comparação com sinal para ativo e que erro de conversão
não vire resultado silencioso. A restrição publicada a números pt-BR não
autoriza aproveitar um prefixo válido dentro de um token malformado. Essa
busca não adjudica sozinha, mas sua evidência pode afirmar correspondência
que o texto não contém.

Critério de fechamento: delimitar e validar o token inteiro; preservar sinal
na gramática aceita, incluindo espaçamento do extrator e moeda, ou recusar
explicitamente a forma não suportada. Testar correspondência falsa e falsa
ausência, positivos/negativos, módulo do FCO e números em colunas distintas.
Repetir a busca nas mesmas fontes sem rebatizá-la como teste cego.

### RAG-03 — P2: zeros decimais adicionais atravessam a autoverificação

Fonte: `scripts/conferir_alcance_geom1_rank03b.py:141`, linhas 141–158 e
163–180. `_formas` gera representações textuais, mas não contempla zeros
decimais equivalentes. O limite do regex impede o casamento da forma inteira
quando ela é seguida de separador decimal e dígitos.

Para o valor **inventado** `1234567`, `verificar_sem_valores` aceita
`1.234.567,00`, `1234567.00` e `1 234 567,00`. Para o valor inventado
`1234567.5`, aceita `1.234.567,50`. Os oito casos — quatro representações,
cada uma no texto de `nota` e como chave do JSON — passaram indevidamente.
A forma `1.234.567`, sem casas extras, é corretamente barrada.

O campo `trecho` tem defesa adicional contra dígitos e continua barrando
esses exemplos. O defeito é na defesa para **outros textos e chaves**, que
B1/R3 também prometem verificar. Não é prova de vazamento real: o replay e a
inspeção dos artefatos publicados não mostraram tal ocorrência.

Critério de fechamento: reconhecer equivalência numérica nas representações
permitidas, não só uma lista finita de grafias; incluir zeros fracionários,
separadores e chaves. Preservar as exceções de hash/data e o tratamento de
números pequenos previsto no contrato. Mensagens de erro também não devem
repetir uma chave que carregue valor sensível.

### RAG-04 — P3: uma frase de estado ainda diz cinco decisões

Fonte anterior a este handoff: `MEMORY.md:448`, no bloco CRF, antes de
“Registro da revisão anterior”. Ainda diz “cinco decisões seguem pendentes”,
enquanto A1 determina seis no estado vigente. O bloco GEOM-1, o próximo passo
e o §12-bis já estão corretos. Marcar essa frase explicitamente como estado
de 18/09 ou atualizar sua remissão; não alterar os cinco de registros
inequivocamente históricos. Achado do auditor em contexto separado.

## O que foi confirmado

- **R1/R2/M1:** correção isolada do ativo retirada do próximo passo;
  alternativas A/B continuam pendentes; nenhuma política foi decidida pelo
  código desta onda. Os cenários publicados não equivalem a novo gate medido.
- **R5/B3:** inventário e contagens publicados sustentam 132 saltos sobre
  22.469 transições; o limite admite 112, portanto faltam 20. As seis
  transições da companhia citada constam do inventário. A contagem Unicode
  da máscara antiga confere: três dos 26 caracteres Pd cobertos.
- **R6:** apenas pré-condição, assinatura e docstring do teste de interface
  mudaram; nenhuma asserção foi enfraquecida. A suíte rodou sem sobrescrever
  `HABILITAR_PERGUNTAS_LIVRES` no comando.
- **Procedência:** snapshots correspondem aos hashes das versões executadas;
  os três hashes N1 conferem. Os sete protegidos permanecem íntegros.
  Consumidor, construtor, auditor de gates e adjudicador conferem com os pins
  CRF anteriores, segundo a conferência estática do auditor independente.
- **Resultados reais:** replay com o código atual reproduziu integralmente a
  saída histórica após normalizar somente os nomes `_x1000`/`_div1000` e
  desconsiderar o campo novo de páginas com pouco texto. Ambos os modos
  concordam; continuam sem correspondência as cinco buscas de FCO em cada
  documento. Nenhum montante/sinal de FCO foi impresso ou salvo.
- **Reconferência atual:** dois documentos, oito trechos do ativo idênticos,
  83 trechos do inventário idênticos e seis omissões por fluxo; sem texto
  ilegível ou página com pouco texto no critério implementado. Isto verifica
  esse critério, não certifica exaustividade de extração ou ausência em outra
  fonte.

**B4 não é achado novo nem foi fechado:** o consumidor ainda não valida o
cabeçalho do manifesto. Sua correção continua sendo pré-condição declarada
para integrar GEOM-1 ou criar correções por conta. Também continuam pendentes
as escolhas de política, dados suficientes e executor v2. Corrigir RAG-01–03
não basta, por si, para autorizar treino.

## Evidências e reprodução

Pasta própria: `artefatos/conferencia_revisao_alcance_geom1_rank03b_2026-09-25/`.

- `reproduzir_achados.py`: contraprovas sintéticas e controle positivo/negativo;
  **êxito significa defeito reproduzido, não aprovação**. Pin vazio existe só
  em diretório temporário; nenhuma entrada original é alterada.
- `contraprovas.json`: resultado e hashes do código sob teste.
- `replay/`: nova execução diagnóstica da busca e seu pin, sem sobrescrever
  `revisao/`; o script conserva no campo `data` a data fixa do contrato
  (24/09), mas este replay foi executado nesta revisão de **25/09**.
- `reconferencia_independente.json`: reconferência com as guardas N1 atuais.
- `pytest_suite.xml`: **3.111 passaram, zero falhas/erros/skips**, 28 warnings,
  155,82 s medidos pelo pytest. Warnings de fixtures do modelo e depreciação
  de Torch; não são aprovação de desempenho de ML.
- `verificacao.json`: integridade, comparação de replay, hashes de evidências
  e registro do escopo do auditor separado.

Comandos da raiz (não sobrescrever os artefatos publicados):

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python artefatos/conferencia_revisao_alcance_geom1_rank03b_2026-09-25/reproduzir_achados.py
CREWAI_STORAGE_DIR=$(mktemp -d)/crewai PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q
```

O primeiro comando lê evidências existentes e confere os sete protegidos;
não lê valores reais de FCO. A reprodução real da busca/reconferência foi
limitada aos mesmos dois pacotes e anexos 193/412, com comparações em memória
previstas em R3. Não houve fonte nova, download, API paga, holdout, novo G0/G1,
estatística de desfecho, T1/T2, baseline ou treino de candidato real. A suíte
inclui testes já existentes de ML com fixtures; isso não é novo experimento.

O sandbox apresentou `mountinfo path is not absolute`; leituras e testes
usaram execução autorizada fora dele. O repositório já estava sujo; não houve
commit, descarte de mudanças ou certificação das frentes paralelas.

## Encaminhamento

Fazer contrato de correção para RAG-01–03, implementar contraprovas que testem
a decisão de publicação, repetir a conferência e preservar esta execução.
Corrigir a remissão documental de RAG-04. Só então declarar fechado o
instrumento desta onda; a passagem ao treino continua sujeita às pendências
de dados, B4, decisões do responsável e protocolo v2.
