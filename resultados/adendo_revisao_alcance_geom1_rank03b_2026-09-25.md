# Adendo pós-auditoria — revisão do alcance GEOM-1

Data: 2026-09-25. Escrito antes de editar, depois do parecer do
auditor-conformidade sobre a onda de 24/09 (1 ALTA, 1 MÉDIA, 4 BAIXA). Mesmo
escopo e mesmas proibições do
[contrato da revisão](contratos_revisao_alcance_geom1_rank03b_2026-09-24.md),
que segue fixado por hash e não é alterado.

## A1 — MEMORY.md ainda mandava fazer o que o R1 retirou

Reescrever o item −2 do "Próximo passo concreto": sem correção por conta
(salvo com G0.3 e G0.5 lendo veredito por conta) e, no lugar de "não aplicar
escala por documento a partir de prova só do ativo", remissão ao [DECIDIR] do
§12-bis. Onde o texto descreve o estado vigente, "cinco [DECIDIR]" passa a
seis. A ressalva do R2 cita a mesma premissa em `parecer_auditor.json`
(artefato fixado, não reescrito).

## M1 — consequências da opção A

No v2 §12-bis e no dimensionamento da ressalva: sob A, depois de integrada a
GEOM-1, 140867 e 142900 se qualificam pela prova de caixa de 18/09 (142900 é
documento de desenho da regra, o que se declara); efeito −2 no G0.3
(132 → 130), e o G0 continua reprovado. Sob B, nenhum documento se qualifica
hoje; −2 só com as quatro ligações.

## B1 — canais latentes de vazamento (nada vazou no dado real)

- **Máscara:** moeda é classe (categoria Unicode `Sc`, com prefixo de até três
  maiúsculas, ou código de três maiúsculas colado ao número); parêntese que
  sobra num trecho com número mascarado sai; linha com palavra de caixa, fluxo
  ou polaridade, de vocabulário fechado, não publica trecho. O vocabulário é
  lexical: reduz o canal, não o fecha — limite declarado.
- **Busca:** o trecho do ativo segue a mesma política do inventário.
- **Autoverificação:** varre também as chaves; reconhece milhar com espaço,
  espaço inseparável e vírgula; isenta só campos de hash e de data, como o
  contrato diz, sem isentar subárvores de identidade. Nomes de campo deixam de
  levar dígitos (`_x1000` → `_vezes_mil`).

As execuções de 24/09 não se repetem: os destinos existem e recusam
sobrescrita. O código que produziu cada artefato da revisão é preservado antes
da mudança. Os artefatos publicados são reconferidos contra as regras novas,
em memória, com saída só de booleanos e contagens.

## B2 — guardas sem contraprova

Contraprovas para: hash do inventário publicado, código congelado, conta
duplicada ou ausente e campo ausente no XML, paginação divergente, concordância
dos modos. Guarda nova de qualidade de texto: `(cid:` ou U+FFFD na extração
derrubam a execução; páginas com pouco texto passam a ser publicadas, para
qualificar "sem correspondência". A frase do R4 "publicar se difere..." é
medida publicada, não condição de gravação.

## B3 — imprecisões da ressalva

A 021520 tem quatro saltos além dos de 2024 (2T16→3T16, 4T16→1T17, 4T24→1T25,
3T25→4T25). A máscara antiga cobria 3 dos 26 traços da categoria Pd e deixava
passar os outros 23; os cinco citados eram exemplos.

## B4 — fica aberto, como pré-condição

O consumidor não confere o cabeçalho do manifesto: uma linha "por conta", com
coluna extra, seria aplicada ao documento inteiro. Corrigir exige mexer no
consumidor, que o contrato de 24/09 proíbe nesta onda. Passa a ser
pré-condição declarada do contrato que criar correção por conta ou integrar a
GEOM-1: o consumidor recusa coluna desconhecida ou ausente.

## Entrega

Testes focados e suíte completa; o mesmo auditor reconfere A1–B3.
