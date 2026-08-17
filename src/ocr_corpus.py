"""Leitura do cache de OCR versionado em ``corpus/ocr/`` (spec 5.3, RNF10).

Este módulo **nunca** chama a API do provedor. Ele lê os artefatos já
congelados e versionados no Git — um JSON por documento, nomeado pelo SHA-256
do PDF de origem — e devolve as páginas em markdown para a ingestão.

A escolha de nomear o arquivo pelo hash do PDF (*content-addressed*) é o que
mantém a RNF10 verificável sem os PDFs: o manifesto (`corpus/metadados.csv`)
guarda o SHA-256 de cada PDF, e o cache só é aceito quando o nome do arquivo,
o campo ``hash_pdf`` e o hash do manifesto coincidem. Uma troca silenciosa de
documento passa a ser impossível sem que o manifesto mude junto.

Consequência deliberada: com ``EXTRATOR=mistral_ocr`` a ingestão roda em um
clone limpo, sem `corpus/raw/`, exatamente como a spec 5.6 exige
("reconstrução determinística a partir do cache de OCR + metadados.csv").
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import RAIZ_PROJETO

# Cache versionado (RNF10). Fica aqui, e não em `src/config.py`, porque é uma
# constante de layout do repositório, não uma opção de configuração.
DIR_CACHE_OCR = RAIZ_PROJETO / "corpus" / "ocr"

_PADRAO_SHA256 = re.compile(r"[0-9a-f]{64}")
# Um artefato do corpus tem ~1,5 MB; 64 MiB comportam folga larga sem permitir
# que um arquivo adulterado esgote memória durante a leitura.
_MAX_ARQUIVO_BYTES = 64 * 1024 * 1024

# Chaves gravadas por `scripts/ocr_batch_mistral.py`. O conjunto é exato de
# propósito: campo novo no artefato é mudança de contrato e deve falhar alto,
# não entrar em silêncio num índice que se declara reprodutível.
_CHAVES_ARTEFATO = frozenset(
    {"documento", "empresa", "trimestre", "hash_pdf", "modelo", "ocr"}
)


class ErroCacheOCR(ValueError):
    """Cache de OCR ausente, adulterado ou incompatível com o manifesto."""


@dataclass(frozen=True)
class PaginaCacheOCR:
    """Uma página do cache, com o markdown como o provedor o devolveu.

    ``confianca_media``/``confianca_minima`` são ``None`` quando o artefato não
    traz escore — é o caso da passagem pela Batch API de 2026-08-11, que não
    pediu ``confidence_scores``. A ausência é registrada e reportada (spec 5.4),
    nunca preenchida com um valor inventado.
    """

    indice: int  # 0-based, como o provedor numera
    markdown: str
    confianca_media: float | None = None
    confianca_minima: float | None = None

    @property
    def numero(self) -> int:
        """Página 1-indexada, como impressa no leitor de PDF."""
        return self.indice + 1


@dataclass(frozen=True)
class DocumentoCacheOCR:
    documento: str
    empresa: str
    trimestre: str
    hash_pdf: str
    modelo: str
    hash_artefato: str  # SHA-256 do próprio JSON de cache
    paginas: tuple[PaginaCacheOCR, ...]


def caminho_documento_ocr(sha256_pdf: str, dir_cache: Path = DIR_CACHE_OCR) -> Path:
    """Caminho do artefato de um PDF, derivado só do hash do manifesto."""
    if not isinstance(sha256_pdf, str) or _PADRAO_SHA256.fullmatch(sha256_pdf) is None:
        raise ErroCacheOCR(
            "sha256_pdf deve ter 64 caracteres hexadecimais minúsculos; "
            f"recebido {sha256_pdf!r}."
        )
    return Path(dir_cache) / f"{sha256_pdf}.json"


def _ler_json_do_cache(caminho: Path) -> dict:
    if caminho.is_symlink():
        raise ErroCacheOCR(f"Artefato de OCR não pode ser symlink: {caminho}.")
    if not caminho.is_file():
        raise ErroCacheOCR(
            f"Cache de OCR ausente: {caminho}. Rode "
            "scripts/ocr_batch_mistral.py ou use EXTRATOR=pdfplumber."
        )
    tamanho = caminho.stat().st_size
    if tamanho > _MAX_ARQUIVO_BYTES:
        raise ErroCacheOCR(f"Artefato de OCR excede o limite seguro: {caminho}.")
    try:
        bruto = caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ErroCacheOCR(f"Artefato de OCR ilegível: {caminho}.") from exc

    def sem_duplicadas(pares: list[tuple[str, object]]) -> dict:
        objeto: dict = {}
        for chave, valor in pares:
            if chave in objeto:
                raise ErroCacheOCR(
                    f"Artefato de OCR contém chave duplicada: {chave!r}."
                )
            objeto[chave] = valor
        return objeto

    def constante_invalida(valor: str):
        raise ErroCacheOCR(f"Artefato de OCR contém constante inválida: {valor}.")

    try:
        objeto = json.loads(
            bruto,
            object_pairs_hook=sem_duplicadas,
            parse_constant=constante_invalida,
        )
    except json.JSONDecodeError as exc:
        raise ErroCacheOCR(f"Artefato de OCR não é JSON válido: {caminho}.") from exc
    if not isinstance(objeto, dict):
        raise ErroCacheOCR(f"Artefato de OCR deve ser objeto JSON: {caminho}.")
    return objeto


def _confianca_da_pagina(
    bruto: object, descricao: str
) -> tuple[float | None, float | None]:
    """Ausência é aceita e sinalizada; presença malformada falha fechado.

    A distinção importa: um escore ausente é uma limitação conhecida do
    artefato (e vira aviso de qualidade, spec 5.4); um escore presente e
    inválido é adulteração ou mudança de contrato do provedor.
    """
    if bruto is None:
        return None, None
    if not isinstance(bruto, dict):
        raise ErroCacheOCR(f"{descricao} deve ser objeto JSON ou nulo.")
    valores: list[float] = []
    for campo in ("average_page_confidence_score", "minimum_page_confidence_score"):
        if campo not in bruto:
            raise ErroCacheOCR(f"{descricao} não contém {campo}.")
        valor = bruto[campo]
        if (
            isinstance(valor, bool)
            or not isinstance(valor, (int, float))
            or not math.isfinite(valor)
            or not 0.0 <= float(valor) <= 1.0
        ):
            raise ErroCacheOCR(f"{descricao}.{campo} deve ser finito entre 0 e 1.")
        valores.append(float(valor))
    media, minima = valores
    if minima > media:
        raise ErroCacheOCR(f"{descricao} tem mínimo maior que a média.")
    return media, minima


def carregar_documento_ocr(
    *,
    documento: str,
    empresa: str,
    trimestre: str,
    sha256_pdf: str,
    modelo_esperado: str,
    dir_cache: Path = DIR_CACHE_OCR,
) -> DocumentoCacheOCR:
    """Lê e valida o artefato de um documento; falha explícita em divergência.

    Toda validação existe para impedir um índice que se diz reprodutível sobre
    um cache que já não corresponde ao manifesto: identificação cruzada
    (documento/empresa/trimestre/hash), modelo pinado, páginas contíguas, sem
    duplicata e sem markdown vazio.
    """
    caminho = caminho_documento_ocr(sha256_pdf, dir_cache)
    artefato = _ler_json_do_cache(caminho)
    if set(artefato) != set(_CHAVES_ARTEFATO):
        raise ErroCacheOCR(
            f"Esquema inesperado em {caminho}: {sorted(artefato)} "
            f"(esperado {sorted(_CHAVES_ARTEFATO)})."
        )
    esperados = {
        "documento": documento,
        "empresa": empresa,
        "trimestre": trimestre,
        "hash_pdf": sha256_pdf,
    }
    for campo, esperado in esperados.items():
        if artefato[campo] != esperado:
            raise ErroCacheOCR(
                f"Cache de OCR não corresponde ao manifesto em {campo}: "
                f"artefato={artefato[campo]!r}, manifesto={esperado!r} "
                f"({caminho})."
            )
    modelo = artefato["modelo"]
    if not isinstance(modelo, str) or modelo != modelo_esperado:
        raise ErroCacheOCR(
            "Cache de OCR foi produzido por outro modelo: "
            f"artefato={modelo!r}, MISTRAL_OCR_MODELO={modelo_esperado!r}. "
            "Reprocessar o corpus é a única saída honesta."
        )
    resposta = artefato["ocr"]
    if not isinstance(resposta, dict):
        raise ErroCacheOCR(f"Campo `ocr` deve ser objeto JSON em {caminho}.")
    modelo_resposta = resposta.get("model")
    if not isinstance(modelo_resposta, str) or not (
        modelo_resposta == modelo or modelo_resposta.startswith(f"{modelo}-")
    ):
        raise ErroCacheOCR(
            f"Modelo da resposta OCR ({modelo_resposta!r}) diverge de "
            f"{modelo!r} em {caminho}."
        )
    paginas_brutas = resposta.get("pages")
    if not isinstance(paginas_brutas, list) or not paginas_brutas:
        raise ErroCacheOCR(f"Resposta OCR sem páginas em {caminho}.")

    paginas: list[PaginaCacheOCR] = []
    vistos: set[int] = set()
    for posicao, pagina in enumerate(paginas_brutas):
        if not isinstance(pagina, dict):
            raise ErroCacheOCR(f"pages[{posicao}] deve ser objeto JSON em {caminho}.")
        indice = pagina.get("index")
        if isinstance(indice, bool) or not isinstance(indice, int) or indice < 0:
            raise ErroCacheOCR(
                f"pages[{posicao}].index inválido em {caminho}: {indice!r}."
            )
        if indice in vistos:
            raise ErroCacheOCR(
                f"Página OCR duplicada (index={indice}) em {caminho}."
            )
        vistos.add(indice)
        markdown = pagina.get("markdown")
        if not isinstance(markdown, str) or not markdown.strip():
            raise ErroCacheOCR(
                f"Página OCR {indice} está vazia ou sem markdown em {caminho}."
            )
        media, minima = _confianca_da_pagina(
            pagina.get("confidence_scores"),
            f"pages[{posicao}].confidence_scores",
        )
        paginas.append(PaginaCacheOCR(indice, markdown, media, minima))

    paginas.sort(key=lambda pagina: pagina.indice)
    if [pagina.indice for pagina in paginas] != list(range(len(paginas))):
        raise ErroCacheOCR(
            f"Páginas OCR não são contíguas a partir de 0 em {caminho}."
        )
    usage = resposta.get("usage_info")
    if isinstance(usage, dict) and "pages_processed" in usage:
        processadas = usage["pages_processed"]
        if processadas != len(paginas):
            raise ErroCacheOCR(
                f"usage_info.pages_processed={processadas!r} diverge das "
                f"{len(paginas)} páginas presentes em {caminho}."
            )
    return DocumentoCacheOCR(
        documento=documento,
        empresa=empresa,
        trimestre=trimestre,
        hash_pdf=sha256_pdf,
        modelo=modelo,
        hash_artefato=_sha256_arquivo(caminho),
        paginas=tuple(paginas),
    )


def hash_cache_ocr(dir_cache: Path = DIR_CACHE_OCR) -> str:
    """Digest determinístico do cache inteiro — entra na identidade do índice.

    Cobre nomes e conteúdo de todos os artefatos, então acrescentar, remover ou
    editar um documento invalida o índice construído sobre a versão anterior
    (RNF09). Diretório ausente devolve o digest do conjunto vazio, e não erro:
    quem exige o cache é o extrator, no ponto de uso, com mensagem própria.
    """
    dir_cache = Path(dir_cache)
    if dir_cache.is_symlink():
        raise ErroCacheOCR(f"Cache de OCR não pode ser symlink: {dir_cache}.")
    arquivos: dict[str, str] = {}
    if dir_cache.is_dir():
        for caminho in sorted(dir_cache.glob("*.json")):
            if caminho.is_symlink() or not caminho.is_file():
                raise ErroCacheOCR(
                    f"Artefato de OCR inválido no cache: {caminho}."
                )
            arquivos[caminho.name] = _sha256_arquivo(caminho)
    canonico = json.dumps(
        {"versao_cache_ocr": 1, "arquivos": arquivos},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonico).hexdigest()


def _sha256_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb", buffering=0) as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


__all__ = [
    "DIR_CACHE_OCR",
    "DocumentoCacheOCR",
    "ErroCacheOCR",
    "PaginaCacheOCR",
    "caminho_documento_ocr",
    "carregar_documento_ocr",
    "hash_cache_ocr",
]
