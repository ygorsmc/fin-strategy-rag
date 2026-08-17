"""Gerador de artefatos sintéticos do cache de OCR (`corpus/ocr/`).

Mesma exigência do gerador de PDFs: o pytest nunca depende do cache real nem
de rede. O esquema reproduzido aqui é exatamente o gravado por
`scripts/ocr_batch_mistral.py` — se ele mudar, estes testes falham, que é o
comportamento desejado para um artefato versionado (RNF10).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.ingestao import DocumentoCorpus


def escrever_cache_ocr(
    dir_cache: Path,
    doc: DocumentoCorpus,
    paginas: list[str],
    *,
    confiancas: list[tuple[float, float] | None] | None = None,
    modelo: str = "mistral-ocr-4-0",
    modelo_resposta: str | None = None,
    indices: list[int] | None = None,
    pages_processed: int | None = None,
    campos_extras: dict | None = None,
) -> Path:
    """Grava `<sha256_do_pdf>.json` com as páginas em markdown.

    ``confiancas=None`` reproduz o cache real do corpus, que veio da Batch API
    **sem** `confidence_scores` — a ausência é parte do contrato testado.
    """
    dir_cache = Path(dir_cache)
    dir_cache.mkdir(parents=True, exist_ok=True)
    numeros = indices if indices is not None else list(range(len(paginas)))
    escores = confiancas if confiancas is not None else [None] * len(paginas)
    corpo_paginas = []
    for posicao, (indice, markdown) in enumerate(zip(numeros, paginas)):
        escore = escores[posicao]
        corpo_paginas.append(
            {
                "index": indice,
                "markdown": markdown,
                "confidence_scores": (
                    None
                    if escore is None
                    else {
                        "average_page_confidence_score": escore[0],
                        "minimum_page_confidence_score": escore[1],
                    }
                ),
                "blocks": [],
                "tables": [],
            }
        )
    artefato = {
        "documento": doc.documento,
        "empresa": doc.empresa,
        "trimestre": doc.trimestre,
        "hash_pdf": doc.hash_sha256.lower(),
        "modelo": modelo,
        "ocr": {
            "model": modelo_resposta or modelo,
            "pages": corpo_paginas,
            "usage_info": {
                "pages_processed": (
                    len(paginas) if pages_processed is None else pages_processed
                ),
                "doc_size_bytes": 1024,
            },
        },
    }
    artefato.update(campos_extras or {})
    destino = dir_cache / f"{doc.hash_sha256.lower()}.json"
    destino.write_text(
        json.dumps(artefato, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destino
