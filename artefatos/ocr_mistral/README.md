# Artefatos Mistral OCR

Este diretório recebe respostas OCR locais e o manifesto verificável criado por
`scripts/preprocessar_ocr_mistral.py`. Os JSONs dinâmicos são ignorados pelo Git:
podem ser regenerados a partir dos PDFs públicos, mas cada chamada é externa e
paga.

A ingestão nunca chama a API. Quando `EXTRACAO_PDF_MODO=mistral_overlay`, ela
somente lê páginas já congeladas, confere o SHA-256 do PDF, o contrato da
requisição, os checksums dos artefatos e a confiança média mínima por página.
O modo, o hash deste manifesto e o fingerprint da derivação são registrados
nos metadados RNF09: mudar cache, parâmetros materiais ou código exige
reconstruir o índice.

Não copie chaves, PDFs em base64 ou respostas para arquivos versionados.
