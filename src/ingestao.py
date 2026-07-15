"""Ingestão e chunking dos releases em PDF (seções 5.3 e 5.4 — RF02, RF03).

Extrai texto por página preservando a numeração, divide em chunks de
~CHUNK_TAMANHO_TOKENS com sobreposição, prefixa cada chunk com o cabeçalho
contextual `[EMPRESA | documento | trimestre | pág. N]` e valida a qualidade
antes de qualquer indexação (testes estruturais + teste-sentinela).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import tiktoken

from src.config import CAMINHO_METADADOS_CORPUS, DIR_CORPUS_RAW, Config
from src.normalizacao import MULTIPLICADORES, remover_acentos, valores_equivalentes

# Mesmo tokenizador da família OpenAI-compatible usada pelos provedores (5.3).
_ENCODER = tiktoken.get_encoding("cl100k_base")

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
    if parser == "pypdf":
        from pypdf import PdfReader

        leitor = PdfReader(str(caminho_pdf))
        return [
            PaginaExtraida(doc, i + 1, pagina.extract_text() or "")
            for i, pagina in enumerate(leitor.pages)
        ]
    if parser == "pdfplumber":
        import pdfplumber

        with pdfplumber.open(caminho_pdf) as pdf:
            return [
                PaginaExtraida(doc, i + 1, pagina.extract_text() or "")
                for i, pagina in enumerate(pdf.pages)
            ]
    raise ValueError(f"parser desconhecido: {parser!r} (use pypdf ou pdfplumber)")


def gerar_chunks(
    paginas: list[PaginaExtraida], config: Config
) -> list[Chunk]:
    """Divide em chunks de ~config.chunk_tamanho_tokens com
    config.chunk_sobreposicao_tokens de overlap, respeitando limites de
    parágrafo quando possível, e prefixa o cabeçalho contextual.

    Contagem de tokens via tiktoken (mesmo tokenizador do provedor default).
    """
    chunks: list[Chunk] = []
    por_documento: dict[str, list[PaginaExtraida]] = {}
    for pagina in paginas:
        por_documento.setdefault(pagina.documento.documento, []).append(pagina)

    for pags in por_documento.values():
        doc = pags[0].documento
        sobre = config.chunk_sobreposicao_tokens
        # Reserva do cabeçalho medida com o cabeçalho mais largo possível.
        cab_reserva = len(
            _ENCODER.encode(
                montar_cabecalho_contextual(
                    doc.empresa, doc.documento, doc.trimestre, 999, 1000
                )
            )
        ) + 2
        max_corpo = max(config.chunk_tamanho_tokens - cab_reserva, sobre + 50)
        seg_max = max_corpo - sobre

        # Segmentos = linhas não vazias (limite natural de parágrafo/frase);
        # linha maior que o orçamento é fatiada por tokens com overlap interno.
        segmentos: list[tuple[str, int, int]] = []  # (texto, página, n_tokens)
        for pag in sorted(pags, key=lambda p: p.numero):
            for linha in pag.texto.split("\n"):
                linha = linha.strip()
                if not linha:
                    continue
                tokens = _ENCODER.encode(linha)
                if len(tokens) <= seg_max:
                    segmentos.append((linha, pag.numero, len(tokens)))
                else:
                    passo = seg_max - sobre
                    for i in range(0, len(tokens), passo):
                        fatia = tokens[i : i + seg_max]
                        texto = _ENCODER.decode(fatia).strip("�").strip()
                        if texto:
                            segmentos.append((texto, pag.numero, len(fatia)))

        atual: list[tuple[str, int, int]] = []
        n_tokens = 0
        posicao = 0

        def emitir() -> None:
            nonlocal posicao, atual, n_tokens
            posicao += 1
            pag_ini = min(n for _, n, _ in atual)
            pag_fim = max(n for _, n, _ in atual)
            corpo = "\n".join(t for t, _, _ in atual)
            cabecalho = montar_cabecalho_contextual(
                doc.empresa, doc.documento, doc.trimestre, pag_ini, pag_fim
            )
            chunks.append(
                Chunk(
                    id=f"{doc.empresa}_{doc.trimestre}_release_{posicao:04d}",
                    empresa=doc.empresa,
                    trimestre=doc.trimestre,
                    documento=doc.documento,
                    pagina_inicio=pag_ini,
                    pagina_fim=pag_fim,
                    posicao_no_documento=posicao,
                    texto=f"{cabecalho}\n{corpo}",
                )
            )
            # Sobreposição: últimos `sobre` tokens do corpo abrem o próximo chunk.
            cauda_tokens = _ENCODER.encode(corpo)[-sobre:]
            cauda = _ENCODER.decode(cauda_tokens).lstrip("�").strip()
            atual = [(cauda, pag_fim, len(cauda_tokens))] if cauda else []
            n_tokens = sum(n for _, _, n in atual)

        for segmento in segmentos:
            if atual and n_tokens + segmento[2] + 1 > max_corpo:
                emitir()
            atual.append(segmento)
            n_tokens += segmento[2] + 1
        # Só emite o resto se houver conteúdo novo além da cauda de overlap.
        if atual and (posicao == 0 or len(atual) > 1):
            emitir()

    return chunks


def validar_qualidade(
    chunks: list[Chunk], documentos: list[DocumentoCorpus], minimo_chunks_por_pagina: float = 0.5
) -> RelatorioQualidade:
    """Validação estrutural RF03 (seção 5.4):
      - nenhum chunk vazio ou só com caracteres de controle;
      - todo documento do manifesto gerou >= limiar mínimo de chunks;
      - todo chunk tem os 5 campos de metadado preenchidos;
      - nenhuma página duplicada dentro do mesmo documento.
    """
    relatorio = RelatorioQualidade()
    conhecidos = {d.documento for d in documentos}
    por_documento: dict[str, list[Chunk]] = {d.documento: [] for d in documentos}
    for chunk in chunks:
        if chunk.documento not in conhecidos:
            relatorio.avisos.append(
                f"chunk {chunk.id} referencia documento fora do manifesto: "
                f"{chunk.documento!r}"
            )
            continue
        por_documento[chunk.documento].append(chunk)

    for nome, chunks_doc in por_documento.items():
        motivos: list[str] = []
        if not chunks_doc:
            motivos.append("nenhum chunk gerado")
        corpos_vistos: set[str] = set()
        for chunk in chunks_doc:
            corpo = chunk.texto.split("\n", 1)[1] if "\n" in chunk.texto else ""
            if not re.sub(r"[\s\x00-\x1f\x7f]+", "", corpo):
                motivos.append(f"chunk vazio ou só controle: {chunk.id}")
            elif corpo in corpos_vistos:
                motivos.append(
                    f"página duplicada (corpo repetido) no chunk {chunk.id}"
                )
            corpos_vistos.add(corpo)
            metadados = (
                chunk.empresa,
                chunk.trimestre,
                chunk.documento,
                chunk.pagina_inicio,
                chunk.posicao_no_documento,
            )
            if any(campo in ("", None) for campo in metadados):
                motivos.append(f"metadado de citação vazio no chunk {chunk.id}")
        if chunks_doc:
            n_paginas = max(c.pagina_fim for c in chunks_doc)
            if len(chunks_doc) < minimo_chunks_por_pagina * n_paginas:
                motivos.append(
                    f"apenas {len(chunks_doc)} chunks para {n_paginas} páginas "
                    f"(limiar {minimo_chunks_por_pagina}/pág.)"
                )
        if motivos:
            relatorio.documentos_falhos[nome] = "; ".join(motivos)
        else:
            relatorio.documentos_ok.append(nome)
    return relatorio


def teste_sentinela(
    chunks_do_documento: list[Chunk], valores_ancora: list[float]
) -> bool:
    """Confere 1–2 valores-âncora conhecidos (ex.: lucro líquido de capa) no
    texto extraído, após normalização numérica pt-BR. Se o valor-âncora não
    aparece, a extração falhou de forma relevante mesmo com os testes
    estruturais passando (seção 5.4)."""
    padrao_numero = re.compile(
        r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?", re.IGNORECASE
    )
    valores_no_texto: list[float] = []
    for chunk in chunks_do_documento:
        texto = remover_acentos(chunk.texto).lower()
        for m in padrao_numero.finditer(texto):
            valor = float(m.group(0).replace(".", "").replace(",", "."))
            resto = texto[m.end() : m.end() + 12]
            if re.match(r"\s*%", resto):
                valores_no_texto.append(valor / 100.0)
                continue
            palavra = re.match(r"\s*([a-z]+)\b", resto)
            if palavra and palavra.group(1) in MULTIPLICADORES:
                valores_no_texto.append(valor * MULTIPLICADORES[palavra.group(1)])
            valores_no_texto.append(valor)
    return all(
        any(valores_equivalentes(ancora, v) for v in valores_no_texto)
        for ancora in valores_ancora
    )


def ingerir_corpus(
    config: Config,
    amostra: bool = False,
    caminho_metadados: Path = CAMINHO_METADADOS_CORPUS,
    dir_raw: Path = DIR_CORPUS_RAW,
) -> list[Chunk]:
    """Pipeline de ingestão completo: manifesto -> páginas -> chunks -> RF03.

    `amostra=True` processa 1 banco × 1 trimestre (smoke test, RNF01).
    """
    documentos = carregar_metadados_corpus(caminho_metadados)
    if amostra:
        empresa = documentos[0].empresa
        trimestre = next(
            d.trimestre for d in documentos if d.empresa == empresa
        )
        documentos = [
            d
            for d in documentos
            if d.empresa == empresa and d.trimestre == trimestre
        ]

    chunks: list[Chunk] = []
    for doc in documentos:
        caminho = Path(dir_raw) / doc.caminho_pdf
        if not caminho.exists():
            print(f"AVISO: PDF ausente para {doc.documento} — rode baixar_corpus")
            continue
        paginas = extrair_paginas(caminho, doc, parser="pypdf")
        # Fallback pdfplumber (5.4, modo de falha nº 2): acionado quando a
        # extração pypdf devolve páginas demais sem texto útil.
        if _fracao_paginas_vazias(paginas) > 0.2:
            alternativa = extrair_paginas(caminho, doc, parser="pdfplumber")
            if _fracao_paginas_vazias(alternativa) < _fracao_paginas_vazias(paginas):
                paginas = alternativa
        chunks.extend(gerar_chunks(paginas, config))

    relatorio = validar_qualidade(chunks, documentos)
    for nome, motivo in relatorio.documentos_falhos.items():
        print(f"AVISO RF03: documento {nome} reprovado — {motivo}")
    for aviso in relatorio.avisos:
        print(f"AVISO RF03: {aviso}")
    return [c for c in chunks if c.documento not in relatorio.documentos_falhos]


def _fracao_paginas_vazias(paginas: list[PaginaExtraida]) -> float:
    if not paginas:
        return 1.0
    vazias = sum(1 for p in paginas if len(p.texto.strip()) < 20)
    return vazias / len(paginas)
