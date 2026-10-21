# As quatro recusas das perguntas livres de 20/10 e as três correções

Na rodada real pelo app em 20/10 (`resultados/agentes_produto_2026-10-20.md`),
4 das 5 perguntas livres foram recusadas pela RN02. As quatro são de
desenvolvimento (`dev`) e têm resposta no corpus, então o ideal era responder.
A pergunta deste relatório é se a guarda acertou ao descartar, isto é, se o
rascunho do modelo estava errado.

- **Fonte dos rascunhos:** os traces do Langfuse da sessão
  `traces_2026-10-20T213509Z`, gravados com texto. Foram só lidos, sem custo.
- **Método:** a guarda foi reaplicada offline aos rascunhos e reproduziu as
  quatro recusas. Variantes controladas de cada rascunho isolaram a regra
  responsável.
- **Custo:** zero.
- **Por que não contamina o teste:** as perguntas são `dev`, então corrigir a
  partir delas não toca as 45 congeladas.

## Veredito de cada recusa

| Pergunta | Rascunho | Regra que recusou | Veredito |
| --- | --- | --- | --- |
| DEV003 (margem financeira gerencial do Itaú, 3T2025) | "31.382 (consolidado) ou 28.550 (Brasil)". Os dois números existem no release | O 28.550 da p. 26 era lido sem unidade | Indevida no motivo. O rascunho tinha o número certo, mas era ambíguo |
| DEV004 (por que o NPL de 15 a 90 dias do Itaú subiu) | Sazonalidade e +0,23 p.p. em PF Brasil, citando a p. 14 do 1T2026 | A pergunta diz "ante o 4T2025", e a regra de cobertura exigia citar um documento do 4T2025 | Indevida |
| DEV008 (fatores da carteira do Santander) | Sazonalidade em cartões, câmbio e os destaques anuais, todos da p. 3 | A frase sem número precisava repetir a linha inteira do release, com banco e trimestre escritos nela | Indevida |
| DEV009 (maior ROAE no 1T2026) | Só Itaú e Santander, sem dizer qual é o maior | As citações cobrem 2 dos 5 bancos | Correta |

Nenhum dos quatro rascunhos trazia número errado. A causa do DEV009 é a
recuperação, que traz só 5 trechos no total para uma pergunta sobre cinco
bancos. É o teto das comparativas, já registrado.

## As três correções

**1. Período-base da comparação** (`_periodos_base_de_comparacao`, em
`src/geracao.py`).

- O período escrito logo depois de "ante", "frente a", "em relação a", "na
  comparação com" ou "comparado a" não exige citação nem afirmação própria,
  quando é anterior a outro período que a pergunta pede.
- A resposta ainda pode mencioná-lo, e os números continuam conferidos contra
  o trecho citado.
- "No 1T2026 e no 4T2025" continua pedindo os dois períodos.

**2. Texto sem número** (`_texto_qualitativo_esta_fundamentado`).

A regra anterior exigia a mesma sequência de palavras de uma linha inteira do
trecho, e só a cópia literal passava. A nova exige:

- toda palavra de conteúdo que não vem da pergunta sai da **mesma oração** da
  evidência;
- banco e trimestre não escritos na oração valem pelo documento de onde ela
  saiu;
- negação e direção (queda × alta) batem.

O motivo da recusa passou a distinguir os casos. "Ao menos uma afirmação"
indica frase sem número; "ao menos um valor numérico", número.

**3. Escala da tabela** (`_unidade_da_legenda`).

- A legenda vigente guarda só a unidade ("R$ milhões").
- Antes, a linha inteira era colada à célula, e o "¹" de "Brasil¹ (em R$
  milhões…)" fazia o parser recusar o texto todo.
- O defeito já existia antes do ajuste do painel feito no mesmo dia.

Cada correção tem contraprovas em `tests/test_guarda_rn02_auditoria.py`, que
travam o que ela não pode abrir:

- dois períodos pedidos;
- base posterior ao período pedido;
- troca de trimestre;
- direção trocada com palavra da pergunta;
- duas orações da evidência juntadas numa só;
- outro banco e outro trimestre;
- negação;
- palavra inventada;
- coluna de outro trimestre;
- escala errada.

## Medição

| Medição | Resultado |
| --- | --- |
| Os quatro rascunhos | DEV004 e DEV008 passam a publicar; DEV009 segue recusado. O DEV003 segue recusado por outro motivo, descrito abaixo |
| Rodada congelada `c3a03ff7`, 4 estratégias × 45 | A semântica passa de 14 para 15 publicações (TSTQ006); as outras estratégias não mudam. Nenhuma resposta deixa de publicar |
| Rodada auditada `a0bea525`, 4 estratégias × 45 | Na semântica, nenhuma publicação muda. Em `fatos`, o TSTF007 passa a publicar |
| E4 (`medir_recuperacao_e4.py`) | Igual à de antes: recall@5 de 12/15 e 10/10; valor no top-5 em 9/15 |
| Guarda de rótulo dos agentes (`medir_guarda_rotulo_agentes.py`) | Igual à de antes: 2 acusações (AGTP002) em 201 respostas; nenhuma das 16 certas acusada |

**Não houve publicação errada nova.**

- **TSTQ006** é qualitativa e não tem conferência automática. A resposta nomeia
  as duas linhas do guidance revistas (serviços e seguros) e a cautela na
  originação de crédito. Não traz as faixas numéricas do gabarito, então está
  certa, mas incompleta; o DeepEval já a tinha julgado fiel (1,0).
- **TSTF007 em `fatos`** traz exatamente o valor do gabarito, R$ 6.067 milhões,
  com a métrica, o banco e o período certos. O avaliador automático a reprova
  porque a frase não repete "consolidado", palavra da pergunta: é o falso
  negativo de redação que o README já registra, não um número errado.

**O que continua aberto:**

- **O DEV003 segue recusado.** O rascunho descreve a fonte como "tabela de
  demonstrações contábeis condensadas" e "demonstração Brasil", palavras que não
  estão nos trechos citados. A guarda de conteúdo inventado está certa ao
  barrar isso. Escrito sem a descrição, o 28.550 do segmento Brasil agora se
  fundamenta.
- **Itens qualitativos parados na cobertura.** Na rodada congelada, TSTQ001,
  TSTQ002, TSTQ005 (em `fatos`), TSTQ006 (nas estratégias híbrida e BM25),
  TSTQ008, TSTQ009 e TSTC006
  passaram a ser aprovados na checagem de texto e agora param na regra de
  cobertura de banco e período. Se essa regra for afrouxada, eles precisam ser
  lidos um a um antes.
- **Sobrescrito ao lado de número.** Fora da legenda, o caractere sobrescrito
  continua anulando o texto inteiro: "R$ 3,8 bilhões¹" não é lido. Tratar a
  nota de rodapé no parser mexe em todo o sistema e fica para uma correção
  própria, medida.

## Uma armadilha encontrada no caminho

A primeira versão da correção 3 punha a função em `src/ingestao.py`. O código
desse arquivo entra na identidade do índice (`_fingerprint_derivacao_ocr`,
RNF09), e o índice existente passou a ser recusado como desatualizado; o app ao
vivo também o recusaria. A função foi para `src/geracao.py`, e
`src/ingestao.py` voltou byte a byte ao estado anterior. Mudança que não altera
os chunks não deve morar no código da ingestão.

## Reprodução

```bash
python -m scripts.reaplicar_guarda_rn02 --fingerprint c3a03ff7 \
    --saida artefatos/resultados_avaliacao/reaplicacao_rn02_c3a03ff7_recusas_dev.json
python -m scripts.reaplicar_guarda_rn02 --fingerprint a0bea525 \
    --saida artefatos/resultados_avaliacao/reaplicacao_rn02_a0bea525_recusas_dev.json
python -m scripts.medir_recuperacao_e4
python -m scripts.medir_guarda_rotulo_agentes
pytest tests/test_guarda_rn02_auditoria.py
```
