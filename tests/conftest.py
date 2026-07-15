"""Fixtures compartilhadas da suíte de testes."""

from __future__ import annotations

import pytest

from src.config import Config
from src.geracao import Citacao
from src.ingestao import Chunk, DocumentoCorpus


@pytest.fixture
def config_padrao() -> Config:
    """Config com os defaults da seção 5.14 — sem tocar no .env real."""
    return Config()


@pytest.fixture
def documento_exemplo() -> DocumentoCorpus:
    return DocumentoCorpus(
        empresa="ITAU",
        trimestre="4T2025",
        documento="itau_release_4T2025",
        url="https://exemplo.invalido/itau_4T2025.pdf",
        data_coleta="2026-07-15",
        hash_sha256="0" * 64,
    )


@pytest.fixture
def chunks_exemplo() -> list[Chunk]:
    """Dois chunks plausíveis de um mesmo documento, um cruzando páginas."""
    return [
        Chunk(
            id="ITAU_4T2025_release_0001",
            empresa="ITAU",
            trimestre="4T2025",
            documento="itau_release_4T2025",
            pagina_inicio=3,
            pagina_fim=3,
            posicao_no_documento=1,
            texto=(
                "[ITAU | itau_release_4T2025 | 4T2025 | pág. 3]\n"
                "O lucro líquido gerencial atingiu R$ 10,9 bilhões no trimestre."
            ),
        ),
        Chunk(
            id="ITAU_4T2025_release_0002",
            empresa="ITAU",
            trimestre="4T2025",
            documento="itau_release_4T2025",
            pagina_inicio=12,
            pagina_fim=13,
            posicao_no_documento=2,
            texto=(
                "[ITAU | itau_release_4T2025 | 4T2025 | págs. 12–13]\n"
                "A carteira de crédito expandida cresceu no período."
            ),
        ),
    ]


@pytest.fixture
def citacao_valida() -> Citacao:
    return Citacao(
        empresa="ITAU", documento="itau_release_4T2025", trimestre="4T2025", pagina=3
    )
