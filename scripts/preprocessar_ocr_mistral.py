"""Pré-processa páginas selecionadas com Mistral OCR, fora da ingestão.

Sem ``--permitir-api-paga`` o comando é estritamente local e funciona como
dry-run. A seleção também é sempre explícita: páginas factuais de dev/teste,
um documento com páginas determinadas, ou todo o corpus com confirmação
adicional.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import stat
import sys
from io import BytesIO
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence
from uuid import uuid4

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject


RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.bloqueio import bloqueio_exclusivo  # noqa: E402
from src.config import (  # noqa: E402
    CAMINHO_METADADOS_CORPUS,
    DIR_CORPUS_RAW,
    DIR_LOGS_EXECUCOES,
    DIR_OCR_MISTRAL,
    Config,
    carregar_config,
    endpoint_mistral_ocr_e_oficial,
)
from src.ingestao import DocumentoCorpus, carregar_metadados_corpus  # noqa: E402
from src.ocr_mistral import (  # noqa: E402
    ClienteMistralOCR,
    ErroMistralOCR,
    MAX_PDF_BYTES_PADRAO,
    ResultadoOCR,
)


CAMINHO_JOURNAL_PADRAO = DIR_LOGS_EXECUCOES / "journal_ocr_mistral.jsonl"
MAX_PAGINAS_POR_DOCUMENTO = 1_000
_PADRAO_PAGINA = re.compile(r"([1-9]\d*)(?:-([1-9]\d*))?")
_PADRAO_SHA256 = re.compile(r"[0-9a-f]{64}")
_CHAVES_EXCLUIDAS_PAGINA_OCR = (
    "/Metadata",
    "/Thumb",
    "/Annots",
    "/AA",
    "/PieceInfo",
)
_CHAVES_EXCLUIDAS_CATALOGO_OCR = (
    *_CHAVES_EXCLUIDAS_PAGINA_OCR,
    "/OpenAction",
)


class ErroPreprocessamentoOCR(RuntimeError):
    """Falha local segura, sem chave, PDF ou texto OCR na mensagem."""


@dataclass(frozen=True)
class DocumentoPlanejado:
    documento: DocumentoCorpus
    caminho_pdf: Path
    total_paginas: int
    paginas_solicitadas: tuple[int, ...]  # 1-based, para apresentação humana
    paginas_faltantes: tuple[int, ...]  # 1-based

    @property
    def paginas_faltantes_zero_based(self) -> tuple[int, ...]:
        return tuple(pagina - 1 for pagina in self.paginas_faltantes)


@dataclass(frozen=True)
class PlanoOCR:
    documentos: tuple[DocumentoPlanejado, ...]
    n_paginas_faltantes: int
    custo_planejado_usd: float
    custo_historico_usd: float
    custo_total_conservador_usd: float
    teto_usd: float


@dataclass(frozen=True)
class EstadoJournal:
    custo_debitado_usd: float
    # chave material -> índices zero-based já concluídos com sucesso
    paginas_sucesso: Mapping[tuple[object, ...], frozenset[int]]


def _sha256_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _sha256_bytes(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _hash_endpoint(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def _custo_paginas(n_paginas: int, preco_usd_mil_paginas: float) -> float:
    if type(n_paginas) is not int or n_paginas < 0:
        raise ErroPreprocessamentoOCR("Quantidade de páginas inválida.")
    if (
        not isinstance(preco_usd_mil_paginas, (int, float))
        or isinstance(preco_usd_mil_paginas, bool)
        or not math.isfinite(float(preco_usd_mil_paginas))
        or preco_usd_mil_paginas <= 0
    ):
        raise ErroPreprocessamentoOCR("Preço OCR deve ser finito e positivo.")
    return n_paginas * float(preco_usd_mil_paginas) / 1_000.0


def parsear_paginas(argumentos: Sequence[str]) -> tuple[int, ...]:
    """Aceita ``1 2``, ``1,2`` e intervalos inclusivos como ``4-6``."""
    if isinstance(argumentos, (str, bytes)) or not argumentos:
        raise ErroPreprocessamentoOCR("--paginas exige ao menos uma página.")
    paginas: set[int] = set()
    for argumento in argumentos:
        if not isinstance(argumento, str):
            raise ErroPreprocessamentoOCR("--paginas contém valor inválido.")
        for parte in argumento.split(","):
            parte = parte.strip()
            correspondencia = _PADRAO_PAGINA.fullmatch(parte)
            if correspondencia is None:
                raise ErroPreprocessamentoOCR(
                    "--paginas aceita apenas inteiros positivos e intervalos A-B."
                )
            inicio = int(correspondencia.group(1))
            fim = int(correspondencia.group(2) or inicio)
            if fim < inicio or fim - inicio + 1 > 100_000:
                raise ErroPreprocessamentoOCR("Intervalo de páginas inválido.")
            paginas.update(range(inicio, fim + 1))
    if not paginas:
        raise ErroPreprocessamentoOCR("--paginas produziu uma seleção vazia.")
    return tuple(sorted(paginas))


def selecionar_paginas_factuais(
    caminho_perguntas: Path,
    *,
    conjunto: str = "dev",
) -> dict[str, tuple[int, ...]]:
    """Extrai somente ``locais_aceitos`` de linhas factuais do conjunto pedido."""
    if conjunto not in {"dev", "teste", "todos"}:
        raise ErroPreprocessamentoOCR("Conjunto factual inválido.")
    conjuntos = {"dev", "teste"} if conjunto == "todos" else {conjunto}
    por_documento: dict[str, set[int]] = {}
    try:
        with Path(caminho_perguntas).open(newline="", encoding="utf-8") as arquivo:
            leitor = csv.DictReader(arquivo)
            obrigatorias = {"conjunto", "categoria", "locais_aceitos"}
            if not obrigatorias <= set(leitor.fieldnames or ()):
                raise ErroPreprocessamentoOCR(
                    "Conjunto-padrão não contém as colunas factuais necessárias."
                )
            for numero_linha, linha in enumerate(leitor, start=2):
                # Campos de resposta/pergunta não são lidos nem persistidos aqui.
                if (
                    linha.get("categoria", "").strip() != "factual"
                    or linha.get("conjunto", "").strip() not in conjuntos
                ):
                    continue
                locais = linha.get("locais_aceitos", "")
                if not isinstance(locais, str) or not locais.strip():
                    raise ErroPreprocessamentoOCR(
                        f"Factual da linha {numero_linha} não possui local aceito."
                    )
                for local in locais.split(";"):
                    documento, separador, pagina_bruta = local.strip().rpartition(":")
                    if (
                        not separador
                        or not documento
                        or re.fullmatch(r"[1-9]\d*", pagina_bruta) is None
                    ):
                        raise ErroPreprocessamentoOCR(
                            f"Local factual inválido na linha {numero_linha}."
                        )
                    por_documento.setdefault(documento, set()).add(int(pagina_bruta))
    except ErroPreprocessamentoOCR:
        raise
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ErroPreprocessamentoOCR(
            "Não foi possível ler o conjunto-padrão factual."
        ) from exc
    if not por_documento:
        raise ErroPreprocessamentoOCR(
            f"Nenhuma página factual encontrada no conjunto {conjunto!r}."
        )
    return {
        documento: tuple(sorted(paginas))
        for documento, paginas in sorted(por_documento.items())
    }


def selecionar_paginas_teste_congelado(
    caminho_perguntas: Path,
) -> dict[str, tuple[int, ...]]:
    """Lê locais de todas as categorias de teste para impedir uso acidental."""

    por_documento: dict[str, set[int]] = {}
    try:
        with Path(caminho_perguntas).open(newline="", encoding="utf-8") as arquivo:
            leitor = csv.DictReader(arquivo, strict=True)
            obrigatorias = {"conjunto", "locais_aceitos"}
            if not obrigatorias <= set(leitor.fieldnames or ()):
                raise ErroPreprocessamentoOCR(
                    "Conjunto-padrão não contém as colunas do gate congelado."
                )
            for numero_linha, linha in enumerate(leitor, start=2):
                if None in linha:
                    raise ErroPreprocessamentoOCR(
                        f"Linha {numero_linha} malformada no conjunto-padrão."
                    )
                conjunto = linha.get("conjunto")
                if not isinstance(conjunto, str) or conjunto.strip() not in {
                    "dev",
                    "teste",
                }:
                    raise ErroPreprocessamentoOCR(
                        f"Conjunto inválido na linha {numero_linha}."
                    )
                if conjunto.strip() != "teste":
                    continue
                locais = linha.get("locais_aceitos")
                if not isinstance(locais, str):
                    raise ErroPreprocessamentoOCR(
                        f"Locais de teste inválidos na linha {numero_linha}."
                    )
                # Adversariais sem fonte podem não ter local; não há página
                # concreta a proteger nesses casos.
                if not locais.strip():
                    continue
                for local in locais.split(";"):
                    documento, separador, pagina_bruta = local.strip().rpartition(":")
                    if (
                        not separador
                        or not documento
                        or re.fullmatch(r"[1-9]\d*", pagina_bruta) is None
                    ):
                        raise ErroPreprocessamentoOCR(
                            f"Local de teste inválido na linha {numero_linha}."
                        )
                    por_documento.setdefault(documento, set()).add(
                        int(pagina_bruta)
                    )
    except ErroPreprocessamentoOCR:
        raise
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ErroPreprocessamentoOCR(
            "Não foi possível ler os locais do conjunto teste congelado."
        ) from exc
    return {
        documento: tuple(sorted(paginas))
        for documento, paginas in sorted(por_documento.items())
    }


def _validar_argumentos_selecao(args: argparse.Namespace) -> None:
    selecao_documento = args.documento is not None or args.paginas is not None
    if (args.documento is None) != (args.paginas is None):
        raise ErroPreprocessamentoOCR(
            "--documento e --paginas devem ser usados juntos."
        )
    n_modos = sum(
        (bool(args.paginas_factuais), bool(args.todas_paginas), selecao_documento)
    )
    if n_modos != 1:
        raise ErroPreprocessamentoOCR(
            "Escolha exatamente um modo: --paginas-factuais, "
            "--documento com --paginas, ou --todas-paginas."
        )
    if args.todas_paginas and not args.confirmar_todas_paginas:
        raise ErroPreprocessamentoOCR(
            "--todas-paginas exige --confirmar-todas-paginas."
        )
    if (
        args.paginas_factuais
        and args.conjunto in {"teste", "todos"}
        and not args.confirmar_teste_congelado
    ):
        raise ErroPreprocessamentoOCR(
            "O conjunto teste congelado exige --confirmar-teste-congelado."
        )


def _selecionar_documentos(
    args: argparse.Namespace,
    documentos: Sequence[DocumentoCorpus],
    caminho_perguntas: Path,
) -> dict[str, tuple[int, ...] | None]:
    _validar_argumentos_selecao(args)
    por_nome = {documento.documento: documento for documento in documentos}
    if args.paginas_factuais:
        selecao: dict[str, tuple[int, ...] | None] = selecionar_paginas_factuais(
            caminho_perguntas,
            conjunto=args.conjunto,
        )
    elif args.todas_paginas:
        selecao = {documento.documento: None for documento in documentos}
    else:
        selecao = {args.documento: parsear_paginas(args.paginas)}
    ausentes = sorted(set(selecao) - set(por_nome))
    if ausentes:
        raise ErroPreprocessamentoOCR(
            "Seleção referencia documento ausente do manifesto: "
            + ", ".join(ausentes)
        )
    return selecao


def _validar_gate_teste_congelado(
    args: argparse.Namespace,
    selecao: Mapping[str, tuple[int, ...] | None],
    documentos: Sequence[DocumentoCorpus],
    caminho_perguntas: Path,
) -> None:
    """Exige confirmação se seleção manual/integral toca local do teste."""

    if args.paginas_factuais:
        # O gate direto de --conjunto teste|todos já ocorreu antes de qualquer
        # leitura; páginas escolhidas por dev não revelam a seleção de teste.
        return
    paginas_teste = selecionar_paginas_teste_congelado(caminho_perguntas)
    documentos_manifesto = {documento.documento for documento in documentos}
    ausentes = sorted(set(paginas_teste) - documentos_manifesto)
    if ausentes:
        raise ErroPreprocessamentoOCR(
            "Conjunto teste referencia documento ausente do manifesto: "
            + ", ".join(ausentes)
        )
    intersecta = any(
        documento in paginas_teste
        and (
            paginas is None
            or bool(set(paginas) & set(paginas_teste[documento]))
        )
        for documento, paginas in selecao.items()
    )
    if intersecta and not args.confirmar_teste_congelado:
        raise ErroPreprocessamentoOCR(
            "A seleção alcança locais do conjunto teste congelado; "
            "use --confirmar-teste-congelado conscientemente."
        )


def _inspecionar_pdf(
    documento: DocumentoCorpus,
    dir_raw: Path,
) -> tuple[Path, int]:
    raiz = Path(dir_raw).resolve()
    caminho = (Path(dir_raw) / documento.caminho_pdf).resolve(strict=False)
    if caminho.parent != raiz or not caminho.is_file():
        raise ErroPreprocessamentoOCR(
            f"PDF local ausente ou inseguro para {documento.documento}."
        )
    try:
        digest = _sha256_arquivo(caminho)
    except OSError as exc:
        raise ErroPreprocessamentoOCR(
            f"PDF local ilegível para {documento.documento}."
        ) from exc
    if digest != documento.hash_sha256:
        raise ErroPreprocessamentoOCR(
            f"SHA-256 do PDF diverge do manifesto para {documento.documento}."
        )
    try:
        with caminho.open("rb") as arquivo:
            leitor = PdfReader(arquivo, strict=False)
            if leitor.is_encrypted:
                raise ErroPreprocessamentoOCR(
                    f"PDF criptografado não é aceito: {documento.documento}."
                )
            total_paginas = len(leitor.pages)
    except ErroPreprocessamentoOCR:
        raise
    except Exception as exc:  # pypdf expõe várias subclasses conforme o PDF
        raise ErroPreprocessamentoOCR(
            f"PDF estruturalmente inválido: {documento.documento}."
        ) from exc
    if total_paginas < 1:
        raise ErroPreprocessamentoOCR(
            f"PDF sem páginas: {documento.documento}."
        )
    return caminho, total_paginas


def _carregar_overlay_cache(
    *,
    documento: str,
    sha256_pdf: str,
    config: Config,
    dir_cache: Path,
):
    # Import tardio: a camada de cache continua independente do cliente HTTP.
    from src.ocr_cache import carregar_overlay_documento

    return carregar_overlay_documento(
        documento=documento,
        sha256_pdf=sha256_pdf,
        modelo=config.mistral_ocr_modelo,
        endpoint=config.mistral_ocr_endpoint,
        table_format=config.mistral_ocr_table_format,
        include_blocks=config.mistral_ocr_include_blocks,
        confidence=config.mistral_ocr_confidence_granularity,
        dir_cache=Path(dir_cache),
    )


def _persistir_resultado_cache(
    resultado: ResultadoOCR,
    *,
    documento: str,
    sha256_pdf: str,
    mapa_paginas_origem: Mapping[int, int],
    config: Config,
    dir_cache: Path,
) -> Path:
    from src.ocr_cache import persistir_resposta_ocr

    return persistir_resposta_ocr(
        resultado,
        documento=documento,
        sha256_pdf=sha256_pdf,
        modelo=config.mistral_ocr_modelo,
        endpoint=config.mistral_ocr_endpoint,
        table_format=config.mistral_ocr_table_format,
        include_blocks=config.mistral_ocr_include_blocks,
        confidence=config.mistral_ocr_confidence_granularity,
        mapa_paginas_origem=dict(mapa_paginas_origem),
        dir_cache=Path(dir_cache),
    )


def _indices_cache_validos(
    paginas_cacheadas: object,
    *,
    documento: str,
    total_paginas: int,
) -> set[int]:
    if not isinstance(paginas_cacheadas, (tuple, list)):
        raise ErroPreprocessamentoOCR(
            f"Cache OCR possui retorno inválido para {documento}."
        )
    indices: list[int] = []
    for pagina in paginas_cacheadas:
        indice = getattr(pagina, "indice", None)
        if type(indice) is not int or not 0 <= indice < total_paginas:
            raise ErroPreprocessamentoOCR(
                f"Cache OCR possui página inválida para {documento}."
            )
        indices.append(indice)
    if len(indices) != len(set(indices)):
        raise ErroPreprocessamentoOCR(
            f"Cache OCR repete página para {documento}."
        )
    return set(indices)


def _construir_pdf_minimo(
    item: DocumentoPlanejado,
) -> tuple[bytes, dict[int, int]]:
    """Copia somente páginas faltantes para o PDF enviado ao provedor."""

    try:
        pdf_fonte = item.caminho_pdf.read_bytes()
    except OSError as exc:
        raise ErroPreprocessamentoOCR(
            f"PDF ficou ilegível antes da chamada: {item.documento.documento}."
        ) from exc
    if _sha256_bytes(pdf_fonte) != item.documento.hash_sha256:
        raise ErroPreprocessamentoOCR(
            f"PDF mudou após o preflight: {item.documento.documento}."
        )
    originais = item.paginas_faltantes_zero_based
    mapa = {relativo: original for relativo, original in enumerate(originais)}
    try:
        leitor = PdfReader(BytesIO(pdf_fonte), strict=False)
        if leitor.is_encrypted or len(leitor.pages) != item.total_paginas:
            raise ErroPreprocessamentoOCR(
                f"PDF mudou estruturalmente: {item.documento.documento}."
            )
        escritor = PdfWriter()
        for original in originais:
            # Excluir durante a clonagem impede que streams/anexos referenciados
            # apenas por estruturas ocultas virem objetos órfãos no payload.
            pagina = escritor.add_page(
                leitor.pages[original],
                excluded_keys=_CHAVES_EXCLUIDAS_PAGINA_OCR,
            )
            for chave in _CHAVES_EXCLUIDAS_PAGINA_OCR:
                pagina.pop(NameObject(chave), None)

        catalogo = escritor.root_object
        for chave in _CHAVES_EXCLUIDAS_CATALOGO_OCR:
            catalogo.pop(NameObject(chave), None)
        nomes = catalogo.get(NameObject("/Names"))
        if nomes is not None:
            try:
                nomes_resolvidos = nomes.get_object()
            except Exception:
                # Uma árvore de nomes malformada não é necessária para OCR.
                catalogo.pop(NameObject("/Names"), None)
            else:
                if isinstance(nomes_resolvidos, dict):
                    nomes_resolvidos.pop(NameObject("/EmbeddedFiles"), None)
                    if not nomes_resolvidos:
                        catalogo.pop(NameObject("/Names"), None)
                else:
                    catalogo.pop(NameObject("/Names"), None)
        destino = BytesIO()
        escritor.write(destino)
        payload = destino.getvalue()
        verificacao = PdfReader(BytesIO(payload), strict=True)
        if verificacao.is_encrypted or len(verificacao.pages) != len(originais):
            raise ErroPreprocessamentoOCR(
                f"Falha ao minimizar o PDF: {item.documento.documento}."
            )
    except ErroPreprocessamentoOCR:
        raise
    except Exception as exc:
        raise ErroPreprocessamentoOCR(
            f"Falha ao minimizar o PDF: {item.documento.documento}."
        ) from exc
    if not payload:
        raise ErroPreprocessamentoOCR(
            f"Payload PDF vazio para {item.documento.documento}."
        )
    if len(payload) > MAX_PDF_BYTES_PADRAO:
        raise ErroPreprocessamentoOCR(
            f"PDF minimizado excede o limite seguro para {item.documento.documento}."
        )
    return payload, mapa


def _chave_material(
    *,
    documento: str,
    sha256_pdf: str,
    modelo: str,
    endpoint_sha256: str,
    table_format: str,
    include_blocks: bool,
    confidence: str,
) -> tuple[object, ...]:
    return (
        documento,
        sha256_pdf,
        modelo,
        endpoint_sha256,
        table_format,
        include_blocks,
        confidence,
    )


def _chave_material_config(
    documento: DocumentoCorpus,
    config: Config,
) -> tuple[object, ...]:
    return _chave_material(
        documento=documento.documento,
        sha256_pdf=documento.hash_sha256,
        modelo=config.mistral_ocr_modelo,
        endpoint_sha256=_hash_endpoint(config.mistral_ocr_endpoint),
        table_format=config.mistral_ocr_table_format,
        include_blocks=config.mistral_ocr_include_blocks,
        confidence=config.mistral_ocr_confidence_granularity,
    )


def _construir_plano(
    config: Config,
    documentos: Sequence[DocumentoCorpus],
    selecao: Mapping[str, tuple[int, ...] | None],
    *,
    dir_raw: Path,
    dir_cache: Path,
    estado_journal: EstadoJournal,
) -> PlanoOCR:
    teto = config.mistral_ocr_orcamento_teto_usd
    if (
        not isinstance(teto, (int, float))
        or isinstance(teto, bool)
        or not math.isfinite(float(teto))
        or teto <= 0
    ):
        raise ErroPreprocessamentoOCR("Teto OCR deve ser finito e positivo.")
    planejados: list[DocumentoPlanejado] = []
    for documento in documentos:
        if documento.documento not in selecao:
            continue
        caminho_pdf, total_paginas = _inspecionar_pdf(documento, dir_raw)
        solicitadas = selecao[documento.documento]
        if solicitadas is None:
            solicitadas = tuple(range(1, total_paginas + 1))
        if not solicitadas or solicitadas[-1] > total_paginas:
            raise ErroPreprocessamentoOCR(
                f"Página solicitada excede o PDF {documento.documento} "
                f"({total_paginas} páginas)."
            )
        paginas_cacheadas = _carregar_overlay_cache(
            documento=documento.documento,
            sha256_pdf=documento.hash_sha256,
            config=config,
            dir_cache=dir_cache,
        )
        indices_cacheados = _indices_cache_validos(
            paginas_cacheadas,
            documento=documento.documento,
            total_paginas=total_paginas,
        )
        faltantes = tuple(
            pagina for pagina in solicitadas if pagina - 1 not in indices_cacheados
        )
        if len(faltantes) > MAX_PAGINAS_POR_DOCUMENTO:
            raise ErroPreprocessamentoOCR(
                f"{documento.documento} excede o limite de "
                f"{MAX_PAGINAS_POR_DOCUMENTO} páginas por request."
            )
        chave = _chave_material_config(documento, config)
        concluidas = estado_journal.paginas_sucesso.get(chave, frozenset())
        if concluidas & {pagina - 1 for pagina in faltantes}:
            raise ErroPreprocessamentoOCR(
                f"Journal registra sucesso sem cache correspondente para "
                f"{documento.documento}; retomada bloqueada."
            )
        planejados.append(
            DocumentoPlanejado(
                documento=documento,
                caminho_pdf=caminho_pdf,
                total_paginas=total_paginas,
                paginas_solicitadas=tuple(solicitadas),
                paginas_faltantes=faltantes,
            )
        )
    n_faltantes = sum(len(item.paginas_faltantes) for item in planejados)
    custo_planejado = _custo_paginas(
        n_faltantes, config.mistral_ocr_preco_usd_mil_paginas
    )
    custo_total = estado_journal.custo_debitado_usd + custo_planejado
    return PlanoOCR(
        documentos=tuple(planejados),
        n_paginas_faltantes=n_faltantes,
        custo_planejado_usd=custo_planejado,
        custo_historico_usd=estado_journal.custo_debitado_usd,
        custo_total_conservador_usd=custo_total,
        teto_usd=float(teto),
    )


def _abrir_journal(caminho: Path, *, append: bool):
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT if append else os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descritor: int | None = None
    try:
        descritor = os.open(caminho, flags, 0o600)
        estado = os.fstat(descritor)
        if not stat.S_ISREG(estado.st_mode) or estado.st_nlink != 1:
            raise ErroPreprocessamentoOCR(
                "Journal OCR deve ser arquivo regular privado, sem links."
            )
        if append and hasattr(os, "fchmod"):
            os.fchmod(descritor, 0o600)
        modo = "a" if append else "r"
        arquivo = os.fdopen(descritor, modo, encoding="utf-8")
        descritor = None
        return arquivo
    except FileNotFoundError:
        raise
    except ErroPreprocessamentoOCR:
        raise
    except OSError as exc:
        raise ErroPreprocessamentoOCR(
            "Journal OCR é inseguro ou não pôde ser aberto."
        ) from exc
    finally:
        if descritor is not None:
            os.close(descritor)


def _anexar_evento_journal(caminho: Path, evento: Mapping[str, object]) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    registro = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **dict(evento),
    }
    try:
        linha = json.dumps(
            registro,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        with _abrir_journal(caminho, append=True) as arquivo:
            arquivo.write(linha + "\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
    except (OSError, TypeError, ValueError) as exc:
        raise ErroPreprocessamentoOCR("Falha ao persistir o journal OCR.") from exc


def _numero_nao_negativo(valor: object) -> bool:
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(float(valor))
        and valor >= 0
    )


def _json_sem_chaves_duplicadas(
    pares: list[tuple[str, object]],
) -> dict[str, object]:
    objeto: dict[str, object] = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ValueError("chave JSON duplicada")
        objeto[chave] = valor
    return objeto


def _mapa_paginas_journal_valido(
    mapa: object,
    paginas_payload: object,
    paginas_origem: object,
) -> bool:
    if (
        type(mapa) is not dict
        or not isinstance(paginas_payload, list)
        or not isinstance(paginas_origem, list)
        or paginas_payload != list(range(len(paginas_origem)))
        or set(mapa) != {str(indice) for indice in paginas_payload}
    ):
        return False
    return all(
        type(mapa[str(indice)]) is int
        and mapa[str(indice)] == paginas_origem[indice]
        for indice in paginas_payload
    )


def _validar_inicio_journal(registro: dict) -> tuple[object, ...]:
    paginas = registro.get("paginas_zero_based")
    paginas_payload = registro.get("paginas_payload_zero_based")
    if (
        not isinstance(registro.get("call_id"), str)
        or not registro["call_id"]
        or not isinstance(registro.get("documento"), str)
        or not registro["documento"]
        or not isinstance(registro.get("modelo"), str)
        or not registro["modelo"]
        or not isinstance(registro.get("table_format"), str)
        or not registro["table_format"]
        or type(registro.get("include_blocks")) is not bool
        or not isinstance(registro.get("confidence"), str)
        or not registro["confidence"]
        or not isinstance(registro.get("sha256_pdf"), str)
        or _PADRAO_SHA256.fullmatch(registro["sha256_pdf"]) is None
        or not isinstance(registro.get("endpoint_sha256"), str)
        or _PADRAO_SHA256.fullmatch(registro["endpoint_sha256"]) is None
        or not isinstance(paginas, list)
        or not paginas
        or any(type(pagina) is not int or pagina < 0 for pagina in paginas)
        or paginas != sorted(set(paginas))
        or not _mapa_paginas_journal_valido(
            registro.get("mapa_paginas_origem"),
            paginas_payload,
            paginas,
        )
        or not isinstance(registro.get("sha256_payload_pdf"), str)
        or _PADRAO_SHA256.fullmatch(registro["sha256_payload_pdf"]) is None
        or type(registro.get("bytes_payload_pdf")) is not int
        or registro["bytes_payload_pdf"] <= 0
        or registro.get("n_paginas") != len(paginas)
        or not _numero_nao_negativo(registro.get("custo_estimado_usd"))
    ):
        raise ErroPreprocessamentoOCR("Journal OCR contém intenção inválida.")
    return _chave_material(
        documento=registro["documento"],
        sha256_pdf=registro["sha256_pdf"],
        modelo=registro["modelo"],
        endpoint_sha256=registro["endpoint_sha256"],
        table_format=registro["table_format"],
        include_blocks=registro["include_blocks"],
        confidence=registro["confidence"],
    )


def _carregar_estado_journal(caminho: Path) -> EstadoJournal:
    caminho = Path(caminho)
    inicios: dict[str, dict] = {}
    finais: dict[str, dict] = {}
    try:
        with _abrir_journal(caminho, append=False) as arquivo:
            linhas = arquivo.read().splitlines()
    except FileNotFoundError:
        return EstadoJournal(0.0, MappingProxyType({}))
    except ErroPreprocessamentoOCR:
        raise
    except (OSError, UnicodeError) as exc:
        raise ErroPreprocessamentoOCR("Journal OCR está ilegível.") from exc
    for numero, linha in enumerate(linhas, start=1):
        if not linha.strip():
            continue
        try:
            registro = json.loads(
                linha,
                object_pairs_hook=_json_sem_chaves_duplicadas,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErroPreprocessamentoOCR(
                f"Journal OCR inválido na linha {numero}."
            ) from exc
        if not isinstance(registro, dict):
            raise ErroPreprocessamentoOCR("Journal OCR exige objetos JSON.")
        evento = registro.get("evento")
        call_id = registro.get("call_id")
        if evento not in {"inicio", "fim"} or not isinstance(call_id, str) or not call_id:
            raise ErroPreprocessamentoOCR("Journal OCR contém evento inválido.")
        destino = inicios if evento == "inicio" else finais
        if call_id in destino:
            raise ErroPreprocessamentoOCR("Journal OCR contém evento duplicado.")
        destino[call_id] = registro
    if set(finais) - set(inicios):
        raise ErroPreprocessamentoOCR("Journal OCR contém terminal sem intenção.")
    paginas_sucesso: dict[tuple[object, ...], set[int]] = {}
    custo_total = 0.0
    for call_id, inicio in inicios.items():
        chave = _validar_inicio_journal(inicio)
        fim = finais.get(call_id)
        if fim is None:
            continue
        if (
            fim.get("resultado") not in {"sucesso", "erro"}
            or fim.get("documento") != inicio.get("documento")
        ):
            raise ErroPreprocessamentoOCR("Terminal OCR diverge da intenção.")
        estimativa = float(inicio["custo_estimado_usd"])
        if fim["resultado"] == "sucesso":
            custo = fim.get("custo_estimado_debitado_usd")
            if (
                not _numero_nao_negativo(custo)
                or not math.isclose(float(custo), estimativa, abs_tol=1e-12)
                or fim.get("n_paginas_processadas") != inicio.get("n_paginas")
            ):
                raise ErroPreprocessamentoOCR(
                    "Terminal de sucesso OCR contém estimativa/páginas divergentes."
                )
            paginas_sucesso.setdefault(chave, set()).update(
                inicio["paginas_zero_based"]
            )
        else:
            custo = fim.get("debito_conservador_usd")
            if (
                not _numero_nao_negativo(custo)
                or not math.isclose(float(custo), estimativa, abs_tol=1e-12)
                or not isinstance(fim.get("erro"), str)
                or not fim["erro"]
            ):
                raise ErroPreprocessamentoOCR(
                    "Terminal de erro OCR subconta a reserva da intenção."
                )
        custo_total += float(custo)
    orfaos = set(inicios) - set(finais)
    if orfaos:
        raise ErroPreprocessamentoOCR(
            "Journal OCR possui intenção órfã; retomada bloqueada para evitar "
            f"cobrança duplicada ({len(orfaos)} chamada(s))."
        )
    return EstadoJournal(
        custo_debitado_usd=custo_total,
        paginas_sucesso=MappingProxyType(
            {chave: frozenset(indices) for chave, indices in paginas_sucesso.items()}
        ),
    )


def _evento_inicio(
    item: DocumentoPlanejado,
    config: Config,
    *,
    call_id: str,
    custo_estimado_usd: float,
    mapa_paginas_origem: Mapping[int, int],
    sha256_payload_pdf: str,
    bytes_payload_pdf: int,
) -> dict[str, object]:
    mapa_canonico = {
        str(relativo): original
        for relativo, original in sorted(mapa_paginas_origem.items())
    }
    return {
        "evento": "inicio",
        "call_id": call_id,
        "documento": item.documento.documento,
        "sha256_pdf": item.documento.hash_sha256,
        "modelo": config.mistral_ocr_modelo,
        "endpoint_sha256": _hash_endpoint(config.mistral_ocr_endpoint),
        "table_format": config.mistral_ocr_table_format,
        "include_blocks": config.mistral_ocr_include_blocks,
        "confidence": config.mistral_ocr_confidence_granularity,
        "paginas_zero_based": list(item.paginas_faltantes_zero_based),
        "paginas_payload_zero_based": list(sorted(mapa_paginas_origem)),
        "mapa_paginas_origem": mapa_canonico,
        "sha256_payload_pdf": sha256_payload_pdf,
        "bytes_payload_pdf": bytes_payload_pdf,
        "n_paginas": len(item.paginas_faltantes),
        "custo_estimado_usd": custo_estimado_usd,
    }


def _validar_resultado_solicitado(
    resultado: ResultadoOCR,
    paginas_esperadas: tuple[int, ...],
) -> None:
    paginas = getattr(resultado, "pages", None)
    uso = getattr(resultado, "usage", None)
    if not isinstance(paginas, (tuple, list)):
        raise ErroPreprocessamentoOCR("Cliente OCR devolveu páginas inválidas.")
    indices = tuple(getattr(pagina, "index", None) for pagina in paginas)
    if indices != paginas_esperadas:
        raise ErroPreprocessamentoOCR(
            "Cliente OCR devolveu páginas diferentes das solicitadas."
        )
    if getattr(uso, "pages_processed", None) != len(paginas_esperadas):
        raise ErroPreprocessamentoOCR(
            "Telemetria OCR diverge das páginas solicitadas."
        )


def _executar_plano(
    plano: PlanoOCR,
    config: Config,
    *,
    caminho_journal: Path,
    dir_cache: Path,
    cliente_factory=ClienteMistralOCR,
) -> int:
    chave = config.mistral_ocr_api_key
    if not isinstance(chave, str) or not chave.strip():
        raise ErroPreprocessamentoOCR(
            "MISTRAL_API_KEY é obrigatória para --permitir-api-paga."
        )

    # Materializa e valida todos os payloads antes de construir o cliente ou
    # registrar a primeira intenção. Assim uma falha local em um documento
    # posterior não causa execução/cobrança parcial do lote.
    payloads: list[tuple[DocumentoPlanejado, bytes, dict[int, int]]] = []
    for item in plano.documentos:
        if item.paginas_faltantes:
            pdf, mapa_paginas_origem = _construir_pdf_minimo(item)
            payloads.append((item, pdf, mapa_paginas_origem))

    cliente = cliente_factory(
        api_key=chave,
        endpoint=config.mistral_ocr_endpoint,
        modelo=config.mistral_ocr_modelo,
        timeout_s=config.mistral_ocr_timeout_s,
        # Sem idempotency key documentada, um retry automático pode cobrar 2x.
        max_retries=0,
    )
    chamadas = 0
    for item, pdf, mapa_paginas_origem in payloads:
        paginas_payload = tuple(sorted(mapa_paginas_origem))
        sha256_payload_pdf = _sha256_bytes(pdf)
        call_id = uuid4().hex
        estimativa = _custo_paginas(
            len(item.paginas_faltantes),
            config.mistral_ocr_preco_usd_mil_paginas,
        )
        _anexar_evento_journal(
            caminho_journal,
            _evento_inicio(
                item,
                config,
                call_id=call_id,
                custo_estimado_usd=estimativa,
                mapa_paginas_origem=mapa_paginas_origem,
                sha256_payload_pdf=sha256_payload_pdf,
                bytes_payload_pdf=len(pdf),
            ),
        )
        try:
            resultado = cliente.processar_pdf(
                pdf,
                pages=paginas_payload,
                table_format=config.mistral_ocr_table_format,
                include_blocks=config.mistral_ocr_include_blocks,
                confidence_scores_granularity=(
                    config.mistral_ocr_confidence_granularity
                ),
            )
            _validar_resultado_solicitado(
                resultado, paginas_payload
            )
            # O terminal só é publicado depois do cache atômico. Uma queda entre
            # esses passos deixa intenção órfã e bloqueia cobrança repetida.
            _persistir_resultado_cache(
                resultado,
                documento=item.documento.documento,
                sha256_pdf=item.documento.hash_sha256,
                mapa_paginas_origem=mapa_paginas_origem,
                config=config,
                dir_cache=dir_cache,
            )
        except Exception as exc:
            _anexar_evento_journal(
                caminho_journal,
                {
                    "evento": "fim",
                    "call_id": call_id,
                    "documento": item.documento.documento,
                    "resultado": "erro",
                    "erro": type(exc).__name__,
                    "debito_conservador_usd": estimativa,
                },
            )
            raise
        _anexar_evento_journal(
            caminho_journal,
            {
                "evento": "fim",
                "call_id": call_id,
                "documento": item.documento.documento,
                "resultado": "sucesso",
                "custo_estimado_debitado_usd": estimativa,
                "n_paginas_processadas": len(item.paginas_faltantes),
            },
        )
        chamadas += 1
    return chamadas


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paginas-factuais",
        action="store_true",
        help="seleciona apenas locais_aceitos das perguntas factuais",
    )
    parser.add_argument(
        "--conjunto",
        choices=("dev", "teste", "todos"),
        default="dev",
        help="conjunto usado por --paginas-factuais (padrão: dev)",
    )
    parser.add_argument("--documento", help="slug exato presente no manifesto")
    parser.add_argument(
        "--paginas",
        nargs="+",
        help="páginas 1-based, separadas por espaço/vírgula ou intervalo A-B",
    )
    parser.add_argument("--todas-paginas", action="store_true")
    parser.add_argument("--confirmar-todas-paginas", action="store_true")
    parser.add_argument("--confirmar-teste-congelado", action="store_true")
    parser.add_argument(
        "--permitir-api-paga",
        action="store_true",
        help="executa o plano após todos os gates; ausente = dry-run local",
    )
    return parser


def _imprimir_plano(plano: PlanoOCR, *, dry_run: bool) -> None:
    n_documentos = sum(bool(item.paginas_faltantes) for item in plano.documentos)
    modo = "DRY-RUN" if dry_run else "EXECUÇÃO"
    print(
        f"{modo}: {n_documentos} documento(s), "
        f"{plano.n_paginas_faltantes} página(s) ainda não cacheada(s)."
    )
    print(
        "Custo conservador: "
        f"histórico US$ {plano.custo_historico_usd:.6f} + "
        f"plano US$ {plano.custo_planejado_usd:.6f} = "
        f"US$ {plano.custo_total_conservador_usd:.6f}; "
        f"teto US$ {plano.teto_usd:.6f}."
    )


def principal(
    argv: list[str] | None = None,
    *,
    config: Config | None = None,
    caminho_manifesto: Path = CAMINHO_METADADOS_CORPUS,
    dir_raw: Path = DIR_CORPUS_RAW,
    dir_cache: Path = DIR_OCR_MISTRAL,
    caminho_journal: Path = CAMINHO_JOURNAL_PADRAO,
    cliente_factory=ClienteMistralOCR,
) -> int:
    args = _criar_parser().parse_args(argv)
    try:
        # Gates puramente sintáticos precedem configuração, manifesto e cache.
        # Assim, a invocação padrão e confirmações ausentes sempre encerram
        # localmente, mesmo quando os artefatos do projeto ainda não existem.
        _validar_argumentos_selecao(args)
        config = config or carregar_config()
        if not endpoint_mistral_ocr_e_oficial(config.mistral_ocr_endpoint):
            raise ErroPreprocessamentoOCR(
                "MISTRAL_OCR_ENDPOINT deve ser o endpoint HTTPS oficial."
            )
        documentos = carregar_metadados_corpus(Path(caminho_manifesto))
        selecao = _selecionar_documentos(
            args,
            documentos,
            Path(config.conjunto_padrao_path),
        )
        _validar_gate_teste_congelado(
            args,
            selecao,
            documentos,
            Path(config.conjunto_padrao_path),
        )
        caminho_journal = Path(caminho_journal)
        caminho_lock = caminho_journal.with_suffix(caminho_journal.suffix + ".lock")
        with bloqueio_exclusivo(caminho_lock, "o pré-processamento Mistral OCR"):
            estado_journal = _carregar_estado_journal(caminho_journal)
            plano = _construir_plano(
                config,
                documentos,
                selecao,
                dir_raw=Path(dir_raw),
                dir_cache=Path(dir_cache),
                estado_journal=estado_journal,
            )
            if plano.custo_total_conservador_usd > plano.teto_usd + 1e-12:
                raise ErroPreprocessamentoOCR(
                    "Custo conservador excede MISTRAL_OCR_ORCAMENTO_TETO_USD; "
                    "nenhuma chamada foi feita."
                )
            _imprimir_plano(plano, dry_run=not args.permitir_api_paga)
            if not args.permitir_api_paga:
                print("Nenhuma chamada externa foi realizada.")
                return 0
            if plano.n_paginas_faltantes == 0:
                print("Nada a processar; todas as páginas selecionadas estão no cache.")
                return 0
            chamadas = _executar_plano(
                plano,
                config,
                caminho_journal=caminho_journal,
                dir_cache=Path(dir_cache),
                cliente_factory=cliente_factory,
            )
        print(f"OCR concluído: {chamadas} request(s), um por documento.")
        return 0
    except (ErroPreprocessamentoOCR, ErroMistralOCR) as exc:
        print(f"FALHOU: {exc}")
        return 1
    except Exception as exc:
        # Exceções de terceiros podem refletir payload/header. Só o tipo é seguro.
        print(f"FALHOU: {type(exc).__name__}.")
        return 1


if __name__ == "__main__":
    raise SystemExit(principal())
