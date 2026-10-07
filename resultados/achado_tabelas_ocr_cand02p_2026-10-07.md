# Achado: o v2 e o v3 do CAND-02-P não têm evento de tabela

**Data:** 2026-10-07. Achado durante a rotulagem do teste do v3, a partir de uma
ressalva do leitor do ABC 4T2021→1T2022 ("as tabelas aparecem só como links
`tbl-N.html`").

## O que foi medido

| Piloto | Eventos de tabela | Exemplos |
|---|---|---|
| **v1** | só nos 5 emissores do corpus principal | Itaú 2.978 de 4.704 (63%), BB 3.422 de 6.368 (54%), Bradesco 2.225 de 5.249 (42%); ABC, BANESTES e BMG: zero |
| **v2** | **zero**, nos 8 emissores | 0 de 9.733 |
| **v3** | **zero**, nos 8 emissores | 0 de 20.003 |

## Causa

O formato do cache de OCR mudou entre os lotes:
- **Lote do corpus principal (10/08):** a tabela vem embutida no `markdown` da
  página. São 37.561 linhas `|` nas 2.790 páginas.
- **Lotes posteriores (expansão, v2 e v3):** o script passou a pedir
  `table_format` à Mistral. A tabela vem em `pages[].tables[]`, em HTML, e o
  `markdown` traz só o link `[tbl-N.html](tbl-N.html)`. São 3.762 tabelas
  nas 4.727 páginas do v3.

`scripts/cand02p_piloto.py::carregar_documento` lê só `markdown`. Por isso o
extrator do redline (`src/redline.py`) e os documentos exportados para os
leitores ficaram sem as tabelas, sem erro e sem aviso.

## O que isto corrige no registro

- **O relatório do v2 dizia: "O que mudou do v1 para o v2 foi só o dado."**
  Não é verdade. O universo também mudou. O teste do v1 (INVIÁVEL) tinha
  tabelas nos emissores grandes, e o do v2 (PROMISSOR) era só texto. O B1 é
  feito de regras numéricas e deve ser mais forte em linha de tabela. Parte da
  virada do v1 para o v2 pode vir do universo, e não do volume de treino.
  **A curva de aprendizado de 29/09 herda a mesma mistura:** pares do v1 com
  tabela e pares do v2 sem.
- **Os leitores do v2 e do v3 julgaram sem ver as tabelas.** Quando o texto
  cita um número que só a tabela confirma, a conferência ficou limitada.

## O que isto NÃO invalida

- **O v3 continua válido para a pergunta que congelou.** O universo foi fixado
  no passo 3, antes de qualquer rótulo, e é o mesmo do v2: redline **de texto**
  de releases. Treino novo e teste saem do mesmo extrator. O v3 testa se o
  PROMISSOR do v2 se repete nesse universo.
- **Corrigir agora invalidaria tudo.** Embutir as tabelas muda os eventos e,
  com eles, os itens dos rótulos e o M congelado.

## Para reabrir com tabelas (v4, com protocolo próprio)

O conteúdo das tabelas está no cache, então não há novo custo de OCR. Falta:
1. embutir o HTML de `pages[].tables[]` no lugar do link, convertido para as
   linhas `|` que o extrator já entende;
2. regenerar universo e pacotes;
3. rotular de novo os pares que ganharem eventos de tabela.

O relatório de qualquer piloto deve passar a dizer em que universo mediu.
