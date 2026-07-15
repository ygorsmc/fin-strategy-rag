"""Gerador de PDFs sintéticos mínimos para os testes de ingestão.

Exigência do AGENTS.md (etapa 4): o pytest nunca depende de PDF real do
corpus. Este módulo constrói, sem dependências externas, um PDF válido com
uma página de texto Helvetica por item de `paginas` — suficiente para
exercitar pypdf e pdfplumber.
"""

from __future__ import annotations

from pathlib import Path


def _stream_conteudo(texto: str) -> bytes:
    linhas = texto.split("\n")
    partes = ["BT", "/F1 11 Tf", "14 TL", "72 760 Td"]
    for linha in linhas:
        escapada = (
            linha.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        )
        partes.append(f"({escapada}) Tj")
        partes.append("T*")
    partes.append("ET")
    return "\n".join(partes).encode("latin-1", errors="replace")


def criar_pdf(caminho: Path, paginas: list[str]) -> Path:
    """Escreve um PDF com uma página por string e devolve o caminho."""
    objetos: list[bytes] = []  # corpo de cada objeto, 1-indexado na ordem

    n_paginas = len(paginas)
    # Objetos: 1=Catalog, 2=Pages, 3=Font, depois pares (página, conteúdo).
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_paginas))
    objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objetos.append(
        f"<< /Type /Pages /Kids [{kids}] /Count {n_paginas} >>".encode()
    )
    objetos.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )
    for i, texto in enumerate(paginas):
        stream = _stream_conteudo(texto)
        objetos.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> "
                f"/Contents {5 + 2 * i} 0 R >>"
            ).encode()
        )
        objetos.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode()
            + stream
            + b"\nendstream"
        )

    saida = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for num, corpo in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida += f"{num} 0 obj\n".encode() + corpo + b"\nendobj\n"

    inicio_xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n".encode()
    saida += b"0000000000 65535 f \n"
    for offset in offsets:
        saida += f"{offset:010d} 00000 n \n".encode()
    saida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{inicio_xref}\n%%EOF\n"
    ).encode()

    caminho = Path(caminho)
    caminho.write_bytes(bytes(saida))
    return caminho
