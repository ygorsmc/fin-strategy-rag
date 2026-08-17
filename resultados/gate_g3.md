# Gate G3 — OCR de documento × pdfplumber (spec 5.3)

Medição local sobre o cache de OCR congelado (`corpus/ocr/`) e o `pdfplumber` rodando nos mesmos PDFs. Sem chamada de API.

A âncora é procurada **página a página**: o parser pt-BR do projeto falha fechado em texto de documento inteiro (a guarda de notação ambígua dispara e ele devolve zero números), e a sentinela da spec 5.4 é definida por página de qualquer forma. `sim` = casou no valor canônico; `escala` = só casou tolerando a escala perdida quando o cabeçalho da tabela ficou noutra página — critério mais frouxo, reportado à parte e nunca somado ao canônico.

| documento | pág. OCR/plumber | âncora OCR | âncora plumber | linhas tab. OCR | linhas tab. plumber |
|---|---|---|---|---|---|
| btg_release_2T2025 | 32/32 | sim | sim | 190 | 379 |
| btg_release_3T2025 | 32/32 | sim | sim | 190 | 367 |
| btg_release_4T2025 | 36/36 | sim | sim | 238 | 397 |
| btg_release_1T2026 | 33/33 | sim | sim | 192 | 375 |
| itau_release_2T2025 | 163/163 | sim | sim | 2450 | 752 |
| itau_release_3T2025 | 153/153 | sim | sim | 2489 | 540 |
| itau_release_4T2025 | 169/169 | sim | sim | 2606 | 783 |
| itau_release_1T2026 | 153/153 | sim | sim | 2595 | 791 |
| bradesco_release_2T2025 | 185/185 | sim | sim | 2277 | 1741 |
| bradesco_release_3T2025 | 158/158 | sim | sim | 2259 | 1627 |
| bradesco_release_4T2025 | 222/222 | sim | sim | 2433 | 2131 |
| bradesco_release_1T2026 | 167/167 | sim | sim | 2533 | 2752 |
| santander_release_2T2025 | 25/25 | sim | sim | 286 | 129 |
| santander_release_3T2025 | 25/25 | sim | sim | 281 | 131 |
| santander_release_4T2025 | 25/25 | sim | sim | 273 | 143 |
| santander_release_1T2026 | 20/20 | sim | sim | 272 | 190 |
| bb_release_2T2025 | 291/291 | sim | sim | 3904 | 3608 |
| bb_release_3T2025 | 288/288 | sim | escala | 3850 | 3562 |
| bb_release_4T2025 | 312/312 | sim | escala | 3986 | 3774 |
| bb_release_1T2026 | 301/301 | sim | sim | 4308 | 4096 |

**Âncora canônica:** OCR 20/20 · pdfplumber 18/20

**Âncora tolerando escala:** OCR 20/20 · pdfplumber 20/20

**Linhas de tabela reconstruídas:** OCR 37612 · pdfplumber 28268

**Veredito na âncora:** OCR de documento

## Leitura honesta do resultado

**No critério da âncora, o gate é praticamente empate: 20/20 contra 18/20.** E os
dois documentos em que o `pdfplumber` só casou tolerando escala (BB 3T2025 e
4T2025) não são erro de leitura do número — são perda do cabeçalho que dizia a
unidade. Tolerando a escala, os dois extratores ficam em 20/20.

Isso não é surpresa, e o desenho da âncora explica: o valor de capa aparece
**também em texto corrido**, não só em tabela. Um parser posicional acha um
número que está numa frase. A âncora, portanto, é um piso de sanidade — ela
detectaria uma extração catastrófica, mas **não discrimina bem** entre os dois
extratores neste corpus.

**Onde a diferença aparece é na estrutura de tabela: 37.612 linhas contra
28.268 (+33%).** E ela não é uniforme, o que importa registrar:

| Instituição | OCR | pdfplumber | razão |
|---|---|---|---|
| Itaú (4 trimestres) | 10.140 | 2.866 | **3,5×** |
| Santander | 1.112 | 593 | 1,9× |
| Bradesco | 9.502 | 8.251 | 1,2× |
| Banco do Brasil | 16.048 | 15.040 | 1,1× |
| BTG | 810 | 1.518 | **0,5× — pdfplumber reconstrói mais** |

**Ressalva metodológica, e ela é séria:** contagem de linhas de tabela mede
*quantidade de estrutura reconstruída*, **não correção**. Mais linhas podem
significar melhor reconstrução ou fragmentação excessiva. Este gate **não
estabelece** que o OCR extrai os números corretamente — estabelece que ele
recupera mais estrutura tabular em 4 das 5 instituições, e menos no BTG.

**Veredito:** a decisão de trocar o extrator **não se reverte**, mas também não
se confirma com a força que a spec 5.3 antecipava ("superar visivelmente"). O
ganho é concentrado no Itaú, que é justamente o documento com tabelas de
múltiplos níveis. A prova real virá da **exatidão numérica por origem**
(`origem=tabela|texto`, spec 5.4): se os erros se concentrarem em `tabela` com o
extrator posicional e não com o OCR, aí sim a troca está demonstrada. Até lá,
este gate é **favorável mas não conclusivo**.
