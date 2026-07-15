"""Ingestão e chunking dos releases em PDF (seções 5.3 e 5.4 — RF02, RF03).

Extrai texto por página preservando a numeração, divide em chunks de
~CHUNK_TAMANHO_TOKENS com sobreposição, prefixa cada chunk com o cabeçalho
contextual `[EMPRESA | documento | trimestre | pág. N]` e valida a qualidade
antes de qualquer indexação (testes estruturais + teste-sentinela).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from src.config import CAMINHO_METADADOS_CORPUS, Config

# Esquema do manifesto do corpus — fonte de verdade (seção 5.2).
COLUNAS_METADADOS_CORPUS = (
    "empresa",
    "trimestre",
    "documento",
    "url",
    "data_coleta",
    "hash_sha256",
)


@dataclass(frozen=True)
class DocumentoCorpus:
    """Uma linha do `corpus/metadados.csv`."""

    empresa: str
    trimestre: str
    documento: str
    url: str
    data_coleta: str
    hash_sha256: str

    @property
    def caminho_pdf(self) -> str:
        return f"{self.documento}.pdf"


@dataclass(frozen=True)
class PaginaExtraida:
    documento: DocumentoCorpus
    numero: int  # 1-indexado, como impresso no leitor de PDF
    texto: str


@dataclass(frozen=True)
class Chunk:
    """Unidade de indexação/citação. Todos os campos de metadado são
    obrigatórios (RN01 depende deles) — a validação de qualidade rejeita
    chunk com campo vazio."""

    id: str  # ex.: "ITAU_4T2025_release_0007"
    empresa: str
    trimestre: str
    documento: str
    pagina_inicio: int
    pagina_fim: int  # == pagina_inicio quando o chunk não cruza página
    posicao_no_documento: int
    texto: str  # JÁ inclui o cabeçalho contextual na primeira linha


@dataclass
class RelatorioQualidade:
    """Resultado da validação RF03. Falha em um documento não derruba o
    pipeline: o documento é marcado aqui e a execução segue (seção 5.4)."""

    documentos_ok: list[str] = field(default_factory=list)
    documentos_falhos: dict[str, str] = field(default_factory=dict)  # doc -> motivo
    avisos: list[str] = field(default_factory=list)

    @property
    def aprovado(self) -> bool:
        return not self.documentos_falhos


def carregar_metadados_corpus(
    caminho: Path = CAMINHO_METADADOS_CORPUS,
) -> list[DocumentoCorpus]:
    """Lê o manifesto e valida o esquema de colunas."""
    with open(caminho, newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        if tuple(leitor.fieldnames or ()) != COLUNAS_METADADOS_CORPUS:
            raise ValueError(
                f"Esquema inesperado em {caminho}: {leitor.fieldnames!r} "
                f"(esperado {COLUNAS_METADADOS_CORPUS})"
            )
        return [DocumentoCorpus(**linha) for linha in leitor]


def montar_cabecalho_contextual(
    empresa: str, documento: str, trimestre: str, pagina_inicio: int, pagina_fim: int
) -> str:
    """Cabeçalho prefixado ao texto indexado (seção 5.3).

    Torna banco/trimestre "buscáveis" mesmo quando o parágrafo não os repete e
    entrega o dado de citação ao LLM dentro do próprio trecho. Chunk que cruza
    páginas registra o intervalo (`págs. 12–13`).
    """
    if pagina_fim == pagina_inicio:
        pagina = f"pág. {pagina_inicio}"
    else:
        pagina = f"págs. {pagina_inicio}–{pagina_fim}"
    return f"[{empresa} | {documento} | {trimestre} | {pagina}]"


def extrair_paginas(
    caminho_pdf: Path, doc: DocumentoCorpus, parser: str = "pypdf"
) -> list[PaginaExtraida]:
    """Extrai texto página a página. `parser` alterna pypdf ↔ pdfplumber —
    o fallback é acionado quando o teste-sentinela reprova o documento
    (seção 5.4, modo de falha nº 2)."""
    raise NotImplementedError("Etapa 4 do AGENTS.md — extração de PDF")


def gerar_chunks(
    paginas: list[PaginaExtraida], config: Config
) -> list[Chunk]:
    """Divide em chunks de ~config.chunk_tamanho_tokens com
    config.chunk_sobreposicao_tokens de overlap, respeitando limites de
    parágrafo quando possível, e prefixa o cabeçalho contextual.

    Contagem de tokens via tiktoken (mesmo tokenizador do provedor default).
    """
    raise NotImplementedError("Etapa 4 do AGENTS.md — chunking")


def validar_qualidade(
    chunks: list[Chunk], documentos: list[DocumentoCorpus], minimo_chunks_por_pagina: float = 0.5
) -> RelatorioQualidade:
    """Validação estrutural RF03 (seção 5.4):
      - nenhum chunk vazio ou só com caracteres de controle;
      - todo documento do manifesto gerou >= limiar mínimo de chunks;
      - todo chunk tem os 5 campos de metadado preenchidos;
      - nenhuma página duplicada dentro do mesmo documento.
    """
    raise NotImplementedError("Etapa 4 do AGENTS.md — validação de qualidade")


def teste_sentinela(
    chunks_do_documento: list[Chunk], valores_ancora: list[float]
) -> bool:
    """Confere 1–2 valores-âncora conhecidos (ex.: lucro líquido de capa) no
    texto extraído, após normalização numérica pt-BR. Se o valor-âncora não
    aparece, a extração falhou de forma relevante mesmo com os testes
    estruturais passando (seção 5.4)."""
    raise NotImplementedError("Etapa 4 do AGENTS.md — teste-sentinela")


def ingerir_corpus(config: Config, amostra: bool = False) -> list[Chunk]:
    """Pipeline de ingestão completo: manifesto -> páginas -> chunks -> RF03.

    `amostra=True` processa 1 banco × 1 trimestre (smoke test, RNF01).
    """
    raise NotImplementedError("Etapa 4 do AGENTS.md — ingestão ponta a ponta")
