# Gate G4 — mapa semântico × linha contábil do release (spec 5.5, RN09)

Medição local sobre o cache de OCR congelado (`corpus/ocr/`), as demonstrações em IFRS de `corpus/ifrs/` (conferidas por hash contra `manifesto_ifrs.csv` antes de cada leitura) e o painel `artefatos/cvm.duckdb`. Sem chamada de API, sem rede.

## Veredito: **APROVADO**

- Parte A (mapa × conferência congelada): **APROVADO**
- Parte B (painel × âncora na mesma base contábil): 20/20 conferidos, 0 divergentes, 0 sem âncora, 0 sem extração

**Divergente e sem âncora não são a mesma coisa**, e o veredito depende de qual é qual. *Sem âncora* é ausência de evidência: nada foi medido, e aprovar seria inventar prova. *Divergente* é evidência medida que não bate: alguma coisa está errada e o gate diz qual número, contra qual documento e de quanto. Uma célula divergente reprova o gate; uma célula sem âncora o deixa incompleto.

Bloqueiam o gate: nenhuma célula por divergência · nenhuma célula por falta de âncora. A Parte A separa a pergunta que dá nome ao gate: o mapa semântico resolve o conceito certo em todos os emissores, e nenhuma das células abaixo é reprovada por erro de mapeamento. Quem consumir estes rótulos — o modelo preditivo da spec 5.10 em primeiro lugar — sabe nominalmente quais células estão conferidas (20), quais têm valor errado medido (0) e quais não foram medidas (0).

## Banco a banco, trimestre a trimestre

Valores em R$ milhões. `painel` é `fatos_semanticos.lucro_liquido_controladores` (o padrão da spec 5.5, por ser a convenção de mercado); `contábil` é a linha do resultado contábil da tabela de conciliação do release, em BRGAAP; `âncora IFRS` é a linha na **mesma base do painel**, vinda da ponte do próprio release (Itaú, Bradesco) ou da demonstração em IFRS publicada em separado (BB, BTG, Santander); `gerencial` é a linha na coluna gerencial/ajustada — medição não bloqueante.

| banco | trimestre | origem | painel | contábil (release) | Δ painel−contábil | âncora IFRS | Δ painel−IFRS | gerencial | Δ ger−cont | situação |
|---|---|---|---|---|---|---|---|---|---|---|
| BB | 2T2025 | arquivado | 2.782,1 | 3.035,0 | -252,9 | 2.782,1 | 0,000 | 3.784,0 | 749,0 | CONFERIDO |
| BB | 3T2025 | arquivado | 2.237,3 | 3.028,0 | -790,7 | 2.237,3 | 0,000 | 3.785,0 | 757,0 | CONFERIDO |
| BB | 4T2025 | derivado | 5.239,9 | 4.972,0 | 267,9 | 5.239,9 | 0,000 | 5.742,0 | 770,0 | CONFERIDO |
| BB | 1T2026 | arquivado | 2.397,2 | 3.090,0 | -692,8 | 2.397,2 | 0,000 | 3.431,0 | 341,0 | CONFERIDO |
| BRADESCO | 2T2025 | arquivado | 6.066,7 | 6.067,0 | -0,3 | 6.067,0 | -0,279 | 6.067,0 | 0,0 | CONFERIDO |
| BRADESCO | 3T2025 | arquivado | 5.500,7 | 6.205,0 | -704,3 | 5.501,0 | -0,335 | 6.205,0 | 0,0 | CONFERIDO |
| BRADESCO | 4T2025 | derivado | 6.500,5 | 6.476,0 | 24,5 | 6.501,0 | -0,509 | 6.516,0 | 40,0 | CONFERIDO |
| BRADESCO | 1T2026 | arquivado | 5.177,9 | 5.030,0 | 147,9 | 5.178,0 | -0,060 | 6.811,0 | 1.781,0 | CONFERIDO |
| BTG | 2T2025 | arquivado | 4.091,7 | 4.009,2 | 82,5 | 4.091,7 | 0,000 | 4.182,1 | 172,9 | CONFERIDO |
| BTG | 3T2025 | arquivado | 4.408,7 | 4.337,4 | 71,3 | 4.408,7 | 0,000 | 4.538,6 | 201,2 | CONFERIDO |
| BTG | 4T2025 | derivado | 4.386,1 | 4.390,5 | -4,4 | 4.386,1 | 0,001 | 4.597,1 | 206,6 | CONFERIDO |
| BTG | 1T2026 | arquivado | 4.760,6 | 4.570,4 | 190,2 | 4.760,6 | 0,000 | 4.808,1 | 237,7 | CONFERIDO |
| ITAU | 2T2025 | arquivado | 11.137,0 | 11.278,0 | -141,0 | 11.137,0 | 0,000 | 11.508,0 | 230,0 | CONFERIDO |
| ITAU | 3T2025 | arquivado | 11.306,0 | 11.561,0 | -255,0 | 11.306,0 | 0,000 | 11.876,0 | 315,0 | CONFERIDO |
| ITAU | 4T2025 | derivado | 11.907,0 | 11.937,0 | -30,0 | 11.907,0 | 0,000 | 12.317,0 | 380,0 | CONFERIDO |
| ITAU | 1T2026 | arquivado | 11.636,0 | 11.938,0 | -302,0 | 11.636,0 | 0,000 | 12.282,0 | 344,0 | CONFERIDO |
| SANTANDER | 2T2025 | arquivado | 1.928,1 | 3.593,0 | -1.664,9 | 1.928,1 | 0,000 | 3.659,0 | 66,0 | CONFERIDO |
| SANTANDER | 3T2025 | arquivado | 3.828,2 | 3.944,0 | -115,8 | 3.828,2 | 0,000 | 4.009,0 | 65,0 | CONFERIDO |
| SANTANDER | 4T2025 | derivado | 3.901,0 | 4.023,0 | -122,0 | 3.901,0 | 0,000 | 4.086,0 | 63,0 | CONFERIDO |
| SANTANDER | 1T2026 | arquivado | 3.218,0 | 3.725,0 | -507,0 | 3.218,0 | 0,000 | 3.788,0 | 63,0 | CONFERIDO |

## Por que a linha contábil do release não serve de âncora sozinha

Existe uma **terceira base contábil** além do par gerencial × contábil que a spec 5.5 já documenta, e ela não estava prevista: a conciliação publicada nos releases parte do **BRGAAP/COSIF**, enquanto as demonstrações consolidadas arquivadas na CVM — a fonte deste painel — estão em **IFRS**, por força da Resolução CMN 4.818/2020. O Banco do Brasil declara isso em texto, na nota *Declaração de conformidade* do próprio release: as demonstrações em Cosif “estão sendo apresentadas ‘adicionalmente’ às demonstrações contábeis consolidadas no padrão contábil internacional – IFRS”.

Itaú e Bradesco publicam a ponte BRGAAP→IFRS dentro do próprio release, e por isso ancoram o gate sozinhos. BB, BTG e Santander não a publicam — mas a mesma CMN 4.818/2020 os obriga a publicar **demonstrações consolidadas em IFRS em separado**, que é a peça de onde sai a âncora deles. São 15 documentos registrados em `corpus/ifrs/manifesto_ifrs.csv` com URL, data de download e SHA-256; o gate confere o hash antes de abrir cada um e recusa ler uma peça que tenha mudado desde o registro. O PDF fica fora do Git, como o resto do corpus bruto — o manifesto é que é versionado.

A leitura dessas demonstrações não usa posição de coluna: a ordem entre trimestre isolado e acumulado do exercício **não é convenção** (no BB o acumulado vem primeiro; no BTG e no Santander, depois), e ler por posição acertaria metade dos documentos com número plausível. A coluna do trimestre é identificada pela identidade `acumulado(t) − isolado(t) = acumulado(t−1)`, com o acumulado anterior vindo do documento do trimestre anterior, e a leitura falha se mais de um par de colunas — ou nenhum — satisfizer a identidade. O 4T sai de `exercício − 9 meses`, a mesma aritmética que o painel usa (RN10): o gate compara derivado com derivado.

### Onde ainda não há âncora nenhuma

A varredura abaixo mede a ausência em vez de afirmá-la: procura, página a página, qualquer número do release equivalente (±0,05%, tolerando as três escalas de impressão) ao valor que o painel resolve, e informa o número **mais próximo** que achou. Uma demonstração financeira imprime a linha exata em R$ mil; distância de centésimos de por cento é coincidência de documento longo, não publicação.

| banco | trimestre | painel (R$ mi) | páginas dentro de ±0,05% | número mais próximo no release | distância |
|---|---|---|---|---|---|
| — | — | — | — | — | toda célula tem âncora medida |

## Detalhe e procedência de cada célula

**BB 2T2025** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = −252,9 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: bb_release_2T2025, conciliação contábil × gerencial, pág. 17, linha “ii lucro liquido”, coluna “2t25”, célula '**3.035**'; bb_ifrs_2T2025, pág. 14, linha “atribuivel aos acionistas controladores”, célula 2.782.083 (R$ mil); coluna do trimestre isolado identificada pela identidade acumulado − trimestre = acumulado publicado em 1T2025

**BB 3T2025** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = −790,7 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: bb_release_3T2025, conciliação contábil × gerencial, pág. 16, linha “lucro liquido”, coluna “3t25”, célula '**3.028**'; bb_ifrs_3T2025, pág. 13, linha “atribuivel aos acionistas controladores”, célula 2.237.301 (R$ mil); coluna do trimestre isolado identificada pela identidade acumulado − trimestre = acumulado publicado em 2T2025

**BB 4T2025** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = +267,9 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: bb_release_4T2025, conciliação contábil × gerencial, pág. 18, linha “lucro liquido”, coluna “4t25”, célula '**4.972**'; bb_ifrs_4T2025, pág. 18, linha “atribuivel aos acionistas controladores”, coluna do exercício 2025, célula 13.698.124 (R$ mil) − acumulado de nove meses (8.458.188 R$ mil); 4T não é publicado — derivado, como o do painel (RN10)

**BB 1T2026** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = −692,8 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: bb_release_1T2026, conciliação contábil × gerencial, pág. 16, linha “lucro liquido”, coluna “1t26”, célula '**3.090**'; bb_ifrs_1T2026, pág. 16, linha “atribuivel aos acionistas controladores”, coluna do exercício 2026, célula 2.397.165 (R$ mil); coluna comparativa confere com o 1T2025 publicado, o que fixa a ordem das colunas

**BRADESCO 2T2025** — CONFERIDO (linha contábil da conciliação)
- Δ = −0,279 R$ mi, dentro da meia-unidade do último dígito impresso (0,500); neste trimestre a linha IFRS da ponte coincide com a contábil (6.067,0 R$ mi), logo as duas bases dão o mesmo número
- fonte: bradesco_release_2T2025, conciliação contábil × gerencial, pág. 47, linha “lucro liquido”, coluna “dre gerencial”, célula '**6.067**'

**BRADESCO 3T2025** — CONFERIDO (linha IFRS da ponte do próprio release)
- Δ contra a linha IFRS = −0,335 R$ mi (tolerância de arredondamento 1,000); Δ contra a linha contábil BRGAAP = −704,3 R$ mi; âncora na ponte BRGAAP→IFRS do próprio release
- fonte: bradesco_release_3T2025, conciliação contábil × gerencial, pág. 47, linha “lucro liquido”, coluna “dre gerencial”, célula '**6.205**'; ponte BRGAAP→IFRS: 9m25 (pág. 47 de bradesco_release_3T2025) − 1s25 (pág. 47 de bradesco_release_2T2025)

**BRADESCO 4T2025** — CONFERIDO (linha IFRS da ponte do próprio release)
- Δ contra a linha IFRS = −0,509 R$ mi (tolerância de arredondamento 1,000); Δ contra a linha contábil BRGAAP = +24,5 R$ mi; âncora na ponte BRGAAP→IFRS do próprio release
- fonte: bradesco_release_4T2025, conciliação contábil × gerencial, pág. 47, linha “lucro liquido”, coluna “dre gerencial”, célula '**6.476**'; ponte BRGAAP→IFRS: 12m25 (pág. 47 de bradesco_release_4T2025) − 9m25 (pág. 47 de bradesco_release_3T2025)

**BRADESCO 1T2026** — CONFERIDO (linha IFRS da ponte do próprio release)
- Δ contra a linha IFRS = −0,060 R$ mi (tolerância de arredondamento 0,500); Δ contra a linha contábil BRGAAP = +147,9 R$ mi; âncora na ponte BRGAAP→IFRS do próprio release
- fonte: bradesco_release_1T2026, conciliação contábil × gerencial, pág. 44, linha “lucro liquido”, coluna “dre gerencial”, célula '**5.030**'; ponte BRGAAP→IFRS, pág. 44, coluna 1t26

**BTG 2T2025** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = +82,5 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: btg_release_2T2025, conciliação contábil × gerencial, pág. 5, linha “lucro liquido”, coluna “2t 2025 contabil”, célula '**4.009,2**'; btg_ifrs_2T2025, pág. 8, linha “lucro liquido atribuivel aos acionistas controladores”, célula 4.091.691 (R$ mil); coluna do trimestre isolado identificada pela identidade acumulado − trimestre = acumulado publicado em 1T2025

**BTG 3T2025** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = +71,3 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: btg_release_3T2025, conciliação contábil × gerencial, pág. 5, linha “lucro liquido”, coluna “3t 2025 contabil”, célula '**4.337,4**'; btg_ifrs_3T2025, pág. 8, linha “lucro liquido atribuivel aos acionistas controladores”, célula 4.408.733 (R$ mil); coluna do trimestre isolado identificada pela identidade acumulado − trimestre = acumulado publicado em 2T2025

**BTG 4T2025** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,001 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = −4,4 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: btg_release_4T2025, conciliação contábil × gerencial, pág. 5, linha “lucro liquido”, coluna “4t 2025 contabil”, célula '**4.390,5**'; btg_ifrs_4T2025, pág. 13, linha “lucro liquido atribuivel aos acionistas controladores”, coluna do exercício 2025, célula 16.005.964 (R$ mil) − acumulado de nove meses (11.619.895 R$ mil); 4T não é publicado — derivado, como o do painel (RN10)

**BTG 1T2026** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = +190,2 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: btg_release_1T2026, conciliação contábil × gerencial, pág. 5, linha “lucro liquido”, coluna “1t 2026 contabil”, célula '**4.570,4**'; btg_ifrs_1T2026, pág. 9, linha “lucro liquido atribuivel aos acionistas controladores”, coluna do exercício 2026, célula 4.760.641 (R$ mil); coluna comparativa confere com o 1T2025 publicado, o que fixa a ordem das colunas

**ITAU 2T2025** — CONFERIDO (linha IFRS da ponte do próprio release)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,500); Δ contra a linha contábil BRGAAP = −141,0 R$ mi; âncora na ponte BRGAAP→IFRS do próprio release
- fonte: itau_release_2T2025, conciliação contábil × gerencial, pág. 5, linha “lucro liquido”, coluna “contabil”, célula '**11.278**'; ponte BRGAAP→IFRS, pág. 29, coluna 2t25, linhas 10–12 (11.137 + 261 = 11.398); rótulo perdido no OCR — linha identificada pela identidade da própria tabela

**ITAU 3T2025** — CONFERIDO (linha IFRS da ponte do próprio release)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,500); Δ contra a linha contábil BRGAAP = −255,0 R$ mi; âncora na ponte BRGAAP→IFRS do próprio release
- fonte: itau_release_3T2025, conciliação contábil × gerencial, pág. 5, linha “lucro liquido”, coluna “contabil”, célula '**11.561**'; ponte BRGAAP→IFRS, pág. 29, coluna 3t25, linhas 9–11 (11.306 + 294 = 11.600); rótulo perdido no OCR — linha identificada pela identidade da própria tabela; tabela realinhada em +1 coluna pela linha BRGAAP, fixada pela conciliação do próprio release

**ITAU 4T2025** — CONFERIDO (linha IFRS da ponte do próprio release)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,500); Δ contra a linha contábil BRGAAP = −30,0 R$ mi; âncora na ponte BRGAAP→IFRS do próprio release
- fonte: itau_release_4T2025, conciliação contábil × gerencial, pág. 5, linha “lucro liquido”, coluna “contabil”, célula '**11.937**'; ponte BRGAAP→IFRS, pág. 31, coluna 4t25, linhas 9–11 (11.907 + 237 = 12.144); rótulo da linha conferido; tabela realinhada em +1 coluna pela linha BRGAAP, fixada pela conciliação do próprio release

**ITAU 1T2026** — CONFERIDO (linha IFRS da ponte do próprio release)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,500); Δ contra a linha contábil BRGAAP = −302,0 R$ mi; âncora na ponte BRGAAP→IFRS do próprio release
- fonte: itau_release_1T2026, conciliação contábil × gerencial, pág. 5, linha “lucro liquido”, coluna “contabil”, célula '**11.938**'; ponte BRGAAP→IFRS, pág. 29, coluna 1t26, linhas 9–11 (11.636 + 239 = 11.875); rótulo da linha conferido

**SANTANDER 2T2025** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = −1.664,9 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: santander_release_2T2025, conciliação contábil × gerencial, pág. 24, linha “lucro liquido”, coluna “contabil”, célula '**3.593**'; santander_ifrs_2T2025, pág. 7, linha “lucro atribuivel a controladora”, célula 1.928.066 (R$ mil); coluna do trimestre isolado identificada pela identidade acumulado − trimestre = acumulado publicado em 1T2025

**SANTANDER 3T2025** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = −115,8 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: santander_release_3T2025, conciliação contábil × gerencial, pág. 24, linha “lucro liquido”, coluna “contabil”, célula '**3.944**'; santander_ifrs_3T2025, pág. 7, linha “lucro atribuivel a controladora”, célula 3.828.204 (R$ mil); coluna do trimestre isolado identificada pela identidade acumulado − trimestre = acumulado publicado em 2T2025

**SANTANDER 4T2025** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = −122,0 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: santander_release_4T2025, conciliação contábil × gerencial, pág. 24, linha “lucro liquido”, coluna “contabil”, célula '**4.023**'; santander_ifrs_4T2025, pág. 17, linha “lucro atribuivel a controladora”, coluna do exercício 2025, célula 12.766.035 (R$ mil) − acumulado de nove meses (8.865.071 R$ mil); 4T não é publicado — derivado, como o do painel (RN10)

**SANTANDER 1T2026** — CONFERIDO (linha IFRS da demonstração publicada em separado)
- Δ contra a linha IFRS = +0,000 R$ mi (tolerância de arredondamento 0,001); Δ contra a linha contábil BRGAAP = −507,0 R$ mi; âncora na demonstração consolidada em IFRS publicada em separado
- fonte: santander_release_1T2026, conciliação contábil × gerencial, pág. 19, linha “lucro liquido”, coluna “contabil”, célula '**3.725**'; santander_ifrs_1T2026, pág. 11, linha “lucro atribuivel a controladora”, coluna do exercício 2026, célula 3.217.994 (R$ mil); coluna comparativa confere com o 1T2025 publicado, o que fixa a ordem das colunas

## Fechamento interno do painel (consolidado = controladores + não controladores)

Checagem que não depende do release: se a soma não fecha, quem não fecha é o arquivo da CVM — a carga conta e reporta, não conserta nem descarta. Esta checagem já acusava o defeito antes de existir âncora que o nomeasse: o gap era o sintoma, e a demonstração em IFRS publicada em separado é que disse **qual** das três linhas está errada.

| banco | trimestre | gap (R$ mil) |
|---|---|---|
| — | — | nenhum gap acima de R$ 1 mil |
