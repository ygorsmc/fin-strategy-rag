# Escala geométrica GEOM-1 — Rank 3-B

Data: 2026-09-18. **Piloto e extensão documental concluídos.
Nenhuma correção promovida; treino continua não autorizado.**

## Resultado do piloto

A extração por posições das palavras recuperou provas que a v4 textual não
reconhecia, sem voltar à busca de um número em qualquer coluna. O ganho é de
cobertura documental, não uma validação do modelo de ML nem aprovação de G0.

| Conjunto | Documentos | Com prova | Abstinências legíveis | Falhas de leitura |
|---|---:|---:|---:|---:|
| Desenho | 8 | 2 | 5 | 1 |
| Verificação reservada | 12 | 1 | 11 | 0 |

As duas sentinelas históricas adicionais, 76468 e 152742, abstiveram nas duas
passagens; não entram nesses denominadores. Na verificação, os três documentos
de cada estrato `formato × escala declarada` foram mantidos: só `xml_unico ×
MIL` teve aceitação (1/3); os outros três estratos tiveram 0/3.

No desenho, 157672 confirmou MIL e 142900 sugeriu UNIDADE→MIL. São evidências
de desenvolvimento, **não resultados independentes**. O documento 144031
apresentou XML inválido na saída do Poppler, registrado como falha sem
substituição, saneamento ou fallback. Não se conclui que a informação inexiste.

Na verificação, a única aceitação, **145037**, confirmou MIL. O auditor leu
independentemente o XML `007870DFP31-12-2024v1.xml` e o PDF embutido no anexo
índice 1, grupo 412, página 3. Conferiu conta 1.01.01, rótulo integral de
Caixa e equivalentes de caixa, unidade MIL, coluna 3 Consolidado/31-12-2024 e
igualdade exata com o formulário. As outras três células também corresponderam
aos respectivos perímetros/períodos; nenhuma contradição encontrada.

**Limite importante:** essa conferência confirma MIL já declarada; não demonstra
acerto de uma correção de escala. Uma aceitação não permite estimar precisão
geral. A auditoria por outro agente não substitui gold humano.

## Fonte e reprodução

Pasta de evidências: `artefatos/escala_geometrica_rank03b_2026-09-18/`.

- `selecao.json`: escolha determinística anterior à leitura, quatro estratos,
  emissores de desenho excluídos da verificação, hashes das entradas.
- `layout_<id>.json`: reconhecimento mascarado do desenho e sentinelas.
- `pin_desenho.json` / `piloto_desenho.json`: primeira passagem de desenvolvimento.
- `pin_verificacao.json` / `piloto_verificacao.json`: regra/código fixados antes
  da passagem reservada; todas as provas, inclusive caixas de palavras.
- `parecer_piloto_verificacao.json`: registro pelo principal do parecer
  independente, com método, identidade da prova e limitações. PDF lido com
  pdfplumber e XML com ElementTree; não se usou GEOM como árbitro de si mesma.
- `extensao/pin.json`, `extensao/evidencias.jsonl`, `extensao/resumo.json`:
  execução completa, separada e sem aplicação de correções.
- `parecer_instrumentos.json`: revisões do produtor/consumidor e dos runners.
- `parecer_candidatas_extensao.json`: conferência independente dos dois saldos
  cuja escala diverge da declarada.
- `replay_extensao.json`: reprodução idêntica das 13 provas nos 12 documentos
  aceitos; teste de determinismo, **não** validação independente da fonte.

Regra e contrato: `resultados/contratos_escala_geometrica_rank03b_2026-09-18.md`
e `resultados/adendo_escala_geometrica_rank03b_2026-09-18.md`.
Seleção SHA-256: `b3e85417f2bcbc5c157f364bafcf8276cf1da7dcb3713535e58f45ca2431452d`.
Piloto reservado: `20e699ca35d5d72b49f99bcb16ce6c67556bae8d47a77402d0ee80a1f42fc532`.

Scripts: `reconhecer_geometria_rank03b.py` seleciona/reconhece;
`provas_geometricas_rank03b.py` extrai e confere por replay do pacote pinado;
`piloto_geometria_rank03b.py` executa o piloto. Os dois destinos do piloto já
existem e a CLI **recusa sobrescrita**, intencionalmente. Para reproduzir uma
prova sem escrever resultados, usar `conferir_prova(prova, pacote, data, hash)`.
As fontes são os pacotes locais do manifesto RAD, não PDFs externos.

## Extensão aos 405 documentos

O auditor aprovou o orquestrador após duas contraprovas adicionais: mapa de
hashes parcial/vazio e eventual sentinela aceita sem conferência. Corrigidos
antes da execução. A regra GEOM-1 e o piloto reservado não foram alterados.

| Formato / escala declarada | Total | Confirmações candidatas | Correções candidatas | Abstinências | Falhas de leitura |
|---|---:|---:|---:|---:|---:|
| ZIP de formulário / MIL | 149 | 1 | 0 | 145 | 3 |
| ZIP de formulário / UNIDADE | 104 | 0 | 0 | 100 | 4 |
| XML único / MIL | 92 | 9 | 0 | 83 | 0 |
| XML único / UNIDADE | 60 | 0 | 2 | 57 | 1 |
| **Total** | **405** | **10** | **2** | **385** | **8** |

Cobertura: **12/405 = 2,96%**, 13 provas. Os conjuntos de desenho/verificação
e as sentinelas estão incluídos nesses 405; não somar denominadores. As duas
sentinelas abstiveram. A v4 vigente permanece com zero provas; GEOM-1 não a
substituiu na cadeia governante.

Há 655 páginas recusadas por coordenadas inválidas, distribuídas por 64
documentos. Não são 655 documentos nem 655 erros contábeis. Os oito documentos
com `ParseError` são 144031, 16954, 54081, 72976, 74741, 76091, 83777 e 97708.
Não foram substituídos nem saneados. A regra pode abster por limitações de
extração/layout; não se auditou a verdade das 385 abstinências.

### Duas candidatas conferidas documentalmente

| Documento / data | Companhia CVM | Anexo (base 0) / grupo / página (base 1) | Evidência demonstrada |
|---|---|---|---|
| 140867 / 30-06-2024 | 021520 | 1 / 193 / 37 | Caixa consolidado corrente, conta 1.01.01, MIL apesar de UNIDADE declarada |
| 142900 / 30-09-2024 | 021520 | 1 / 193 / 35 | Caixa consolidado corrente, conta 1.01.01, MIL apesar de UNIDADE declarada |

O auditor conferiu todas as provas desses dois documentos (uma por documento)
em PDF/XML original, por método independente. Nas duas, a coluna 3 e as quatro
células da tabela correspondem exatamente aos seus perímetros/períodos no XML;
forma bruto, sem arredondamento. Identidades e hashes conferem. Em junho a
extração textual padrão fragmentava palavras; a conferência usou fluxo de
texto e caracteres posicionados do pdfplumber. Nenhuma contradição encontrada.

**Alcance:** prova material da escala desses saldos, não licença para corrigir
automaticamente todas as contas ou a DFC. São dois períodos da mesma companhia,
e 142900 era desenho conhecido. As outras confirmações não receberam conferência
documental nesta extensão, exceto 145037 no piloto. Nenhuma herança foi executada.

Evidências SHA-256: `d5fd851ce66e0b5c3005f1b106f22ffcfa016b4978770e9d21ccc3f28db27ad3`.
Pin da extensão: `8f1f31d4591feb19118e04dbe841fbf557463fe101a347068f50b93a9e9a124e`.
Execução: `PYTHONPATH=. .venv/bin/python -m scripts.estender_geometria_rank03b`.
O destino já existe; a CLI recusa reexecutar/sobrescrever nele.

## Defeitos encontrados e corrigidos antes da verificação

O auditor independente identificou duas falsas aceitações sintéticas: ressalva
arbitrária de unidade (`exceto...`) e unidade contrária não enumerada. A regra
foi fechada às ressalvas genéricas expressamente descritas, com veto para
declaração de moeda/unidade desconhecida. Dimensões inválidas de página também
passaram a vetar. As correções e contraprovas foram reconferidas antes de
abrir qualquer documento reservado.

O runner inicial ignorava o manifesto de aquisição porque seu caminho no pin
era absoluto, enquanto a seleção dos protegidos usava prefixos relativos.
Corrigido para normalização de caminhos e exigência dos sete arquivos; ausência
ou adulteração agora falha. O pin do desenho original **não foi reescrito**:
registrava seis guardas. O manifesto foi conferido separadamente e permanece
idêntico ao pin inicial. Runner anterior preservado em
`piloto_antes_da_guarda_absoluta.py`; helper original em
`reconhecer_geometria_inicial.py`. O pin da verificação já contém as sete guardas.

## Testes e fronteiras

**112 testes específicos** (86 extrator/piloto + 26 extensão); suíte completa
final: **2.727 passed, zero falhas/erros/skips**, 30 warnings de dependências e
fixtures já presentes. XML: `pytest_extensao_final.xml`, SHA-256
`06d4680b985050c61c63066c0a9fd3e1b94466d4dfb883db1117e12c306c64ed`.
Comando: `PYTHONDONTWRITEBYTECODE=1 CREWAI_STORAGE_DIR=<temporário>/crewai
.venv/bin/pytest -q --junitxml=<pasta-da-onda>/pytest_extensao_final.xml`.
O piloto isolado havia passado em 2.701 casos (`pytest_final.xml`). A execução
anterior `pytest_completo.xml` tinha 2.698
casos, antes das três contraprovas da guarda de caminho absoluto; não somar
rodadas. Testes sintéticos cobrem datas, contas, perímetros, unidades, notas,
ambiguidade, sinal, arredondamento, coordenadas e adulteração da prova.

Sete arquivos protegidos conferidos antes/depois do piloto e extensão, sem mudança:
painéis compartilhados, manifesto de aquisição, evidências v4, correções CSV,
painel de pesquisa e gates. **G0 vigente continua reprovado**; não foi medido
outro G0 nesta etapa. Não houve download, API paga, mudança de política,
cálculo de alvo real, T1/T2/baselines ou treino do candidato.

## Continuação

A extensão integral está concluída sob o contrato em
`resultados/contratos_extensao_geom1_rank03b_2026-09-18.md`. O próximo trabalho
é **adjudicação do alcance**, não treino:

1. Demonstrar pela fonte se a escala dos saldos conferidos vale para as contas
   monetárias que o painel pretende corrigir; não extrapolar para FCO apenas
   pela igualdade do caixa. Registrar qualquer discordância de unidade/conta.
2. Concluir conferência documental das demais provas que forem sustentar uma
   decisão. Testar S5 em trechos completos se houver proposta de herança; sem
   suporte testável, não herdar.
3. Integrar GEOM-1 ao produtor/consumidor governante com contratos, replay e
   contraprovas próprias, sem desligar ou fingir cumprir a validação v4.
   Preservar snapshots e obter revisão independente antes da promoção.
4. Só após decisões fechadas, reconstruir o painel de pesquisa e medir G0/G1.
   Não ajustar a regra pelo resultado. Os cinco pontos de política, aprovação
   do pré-registro e executor v2 continuam necessários antes de qualquer treino.

Se for preciso ampliar o reconhecimento, será nova versão declarada. Não
ajustar GEOM-1 sobre a verificação já vista e apresentá-la como teste novo.
