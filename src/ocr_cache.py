"""Cache OCR local, imutável e verificável.

O módulo não chama provedores. Ele recebe uma resposta OCR já obtida, remove
qualquer campo fora do contrato persistível e congela páginas por conteúdo.
Arquivos de resposta são content-addressed; ``manifesto.json`` é a única raiz
de confiança mutável e sempre é promovido atomicamente sob lock exclusivo.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from src.bloqueio import bloqueio_compartilhado, bloqueio_exclusivo


VERSAO_CACHE_OCR = 1
NOME_MANIFESTO_OCR = "manifesto.json"
NOME_DIRETORIO_RESPOSTAS = "respostas"

_PADRAO_DOCUMENTO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_PADRAO_SHA256 = re.compile(r"[0-9a-f]{64}")
_PADRAO_MODELO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_FORMATOS_TABELA = frozenset({"html", "markdown"})
_CONFIANCAS = frozenset({"page", "word"})

# O cliente limita a resposta bruta a 32 MiB. O snapshot mantém essa resposta
# e também representações derivadas auditáveis; 128 MiB comportam essa
# duplicação sem permitir que um arquivo adulterado esgote memória na leitura.
_MAX_ARQUIVO_CACHE_OCR_BYTES = 128 * 1024 * 1024
_BLOCO_LEITURA_CACHE_OCR_BYTES = 64 * 1024


@dataclass(frozen=True)
class PaginaOCRCongelada:
    """Overlay textual de uma página OCR, com índice zero-based."""

    indice: int
    texto: str
    modelo: str
    hash_artefato: str
    average_page_confidence_score: float
    minimum_page_confidence_score: float

    @property
    def index(self) -> int:
        """Alias compatível com o vocabulário da resposta do provedor."""

        return self.indice

    @property
    def page_index(self) -> int:
        return self.indice

    @property
    def pagina_index(self) -> int:
        return self.indice


@dataclass(frozen=True)
class _CelulaTabela:
    texto: str
    cabecalho: bool
    ambigua: bool = False


def _objeto_sem_chaves_duplicadas(
    pares: list[tuple[str, object]],
) -> dict[str, object]:
    objeto: dict[str, object] = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ValueError("JSON do cache OCR contém chave duplicada.")
        objeto[chave] = valor
    return objeto


def _constante_json_invalida(valor: str):
    raise ValueError(f"JSON do cache OCR contém constante inválida: {valor}.")


def _carregar_json_estrito(dados: bytes, descricao: str) -> dict[str, object]:
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{descricao} não está em UTF-8 válido.") from exc
    try:
        objeto = json.loads(
            texto,
            object_pairs_hook=_objeto_sem_chaves_duplicadas,
            parse_constant=_constante_json_invalida,
        )
    except ValueError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"{descricao} não contém JSON válido.") from exc
    if type(objeto) is not dict:
        raise ValueError(f"{descricao} deve ser um objeto JSON.")
    _validar_valor_json(objeto, descricao)
    return objeto


def _validar_valor_json(valor: object, caminho: str, profundidade: int = 0) -> None:
    if profundidade > 64:
        raise ValueError(f"Objeto profundo demais em {caminho}.")
    if valor is None or type(valor) in {str, bool, int}:
        return
    if type(valor) is float:
        if not math.isfinite(valor):
            raise ValueError(f"Número não finito em {caminho}.")
        return
    if type(valor) is list:
        for indice, item in enumerate(valor):
            _validar_valor_json(item, f"{caminho}[{indice}]", profundidade + 1)
        return
    if type(valor) is dict:
        for chave, item in valor.items():
            if type(chave) is not str or not chave:
                raise ValueError(f"Chave inválida em {caminho}.")
            _validar_valor_json(item, f"{caminho}.{chave}", profundidade + 1)
        return
    raise ValueError(f"Tipo não JSON em {caminho}.")


def _bytes_canonicos(objeto: object) -> bytes:
    _validar_valor_json(objeto, "objeto")
    return json.dumps(
        objeto,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _exigir_chaves(
    objeto: object, esperadas: set[str], descricao: str
) -> dict[str, object]:
    if type(objeto) is not dict or set(objeto) != esperadas:
        encontradas = sorted(objeto) if type(objeto) is dict else type(objeto).__name__
        raise ValueError(
            f"Esquema inválido em {descricao}: esperado {sorted(esperadas)}, "
            f"encontrado {encontradas}."
        )
    return objeto


def _validar_documento(documento: object) -> str:
    if (
        type(documento) is not str
        or _PADRAO_DOCUMENTO.fullmatch(documento) is None
        or documento in {".", ".."}
    ):
        raise ValueError("documento deve ser um identificador seguro, não um caminho.")
    return documento


def _validar_sha_pdf(sha256_pdf: object) -> str:
    if type(sha256_pdf) is not str or _PADRAO_SHA256.fullmatch(sha256_pdf) is None:
        raise ValueError("sha256_pdf deve ter 64 caracteres hexadecimais minúsculos.")
    return sha256_pdf


def _validar_modelo(modelo: object) -> str:
    if (
        type(modelo) is not str
        or _PADRAO_MODELO.fullmatch(modelo) is None
        or modelo.casefold().endswith("-latest")
    ):
        raise ValueError("modelo OCR deve ser um identificador pinado.")
    return modelo


def _modelo_observado_compativel(solicitado: str, observado: str) -> bool:
    """Aceita o alias pinado solicitado ou sua revisão canônica observada."""

    return observado == solicitado or observado.startswith(f"{solicitado}-")


def _normalizar_endpoint(endpoint: object) -> str:
    if type(endpoint) is not str or not endpoint or endpoint != endpoint.strip():
        raise ValueError("endpoint OCR deve ser uma URL HTTPS não vazia.")
    if any(ord(caractere) < 32 or ord(caractere) == 127 for caractere in endpoint):
        raise ValueError("endpoint OCR contém caractere de controle.")
    try:
        partes = urlsplit(endpoint)
        porta = partes.port
    except ValueError as exc:
        raise ValueError("endpoint OCR possui porta/host inválido.") from exc
    if (
        partes.scheme.casefold() != "https"
        or (partes.hostname or "").casefold() != "api.mistral.ai"
        or porta not in {None, 443}
        or partes.username is not None
        or partes.password is not None
        or partes.query
        or partes.fragment
        or partes.path not in {"/v1/ocr", "/v1/ocr/"}
    ):
        raise ValueError("endpoint OCR deve ser exatamente o endpoint HTTPS oficial.")
    # A porta HTTPS explícita é semanticamente idêntica à implícita. Manter uma
    # representação única evita falsos conflitos de contrato no manifesto.
    return "https://api.mistral.ai/v1/ocr"


def _normalizar_contrato(
    *,
    modelo: object,
    endpoint: object,
    table_format: object,
    include_blocks: object,
    confidence: object,
) -> dict[str, object]:
    modelo_validado = _validar_modelo(modelo)
    endpoint_validado = _normalizar_endpoint(endpoint)
    if table_format not in _FORMATOS_TABELA:
        raise ValueError("table_format deve ser 'html' ou 'markdown'.")
    if type(include_blocks) is not bool:
        raise ValueError("include_blocks deve ser booleano.")
    if confidence not in _CONFIANCAS:
        raise ValueError("confidence deve ser 'page' ou 'word'.")
    return {
        "modelo": modelo_validado,
        "endpoint": endpoint_validado,
        "table_format": table_format,
        "include_blocks": include_blocks,
        "confidence": confidence,
    }


def _validar_contrato_armazenado(objeto: object) -> dict[str, object]:
    contrato = _exigir_chaves(
        objeto,
        {"modelo", "endpoint", "table_format", "include_blocks", "confidence"},
        "contrato_requisicao",
    )
    normalizado = _normalizar_contrato(**contrato)
    if contrato != normalizado:
        raise ValueError("Contrato OCR armazenado não está em forma canônica.")
    return normalizado


def _inteiro_nao_negativo(valor: object, campo: str) -> int:
    if type(valor) is not int or valor < 0:
        raise ValueError(f"{campo} deve ser inteiro não negativo.")
    return valor


def _score_confianca(valor: object, campo: str) -> float:
    if (
        isinstance(valor, bool)
        or not isinstance(valor, (int, float))
        or not math.isfinite(valor)
        or not 0.0 <= float(valor) <= 1.0
    ):
        raise ValueError(f"{campo} deve ser número finito entre 0 e 1.")
    return float(valor)


def _normalizar_confidence_scores(
    objeto: object, descricao: str
) -> dict[str, float]:
    if type(objeto) is not dict:
        raise ValueError(f"{descricao} deve ser objeto JSON.")
    obrigatorias = {
        "average_page_confidence_score",
        "minimum_page_confidence_score",
    }
    if not obrigatorias <= set(objeto):
        raise ValueError(f"{descricao} não contém scores obrigatórios.")
    palavras = objeto.get("word_confidence_scores")
    if palavras is not None:
        if type(palavras) is not list:
            raise ValueError(
                f"{descricao}.word_confidence_scores deve ser lista ou null."
            )
        for indice, score in enumerate(palavras):
            _score_confianca(
                score, f"{descricao}.word_confidence_scores[{indice}]"
            )
    media = _score_confianca(
        objeto["average_page_confidence_score"],
        f"{descricao}.average_page_confidence_score",
    )
    minimo = _score_confianca(
        objeto["minimum_page_confidence_score"],
        f"{descricao}.minimum_page_confidence_score",
    )
    if minimo > media:
        raise ValueError(
            f"{descricao}.minimum_page_confidence_score não pode exceder a média."
        )
    return {
        "average_page_confidence_score": media,
        "minimum_page_confidence_score": minimo,
    }


def _normalizar_usage(
    objeto: object,
    descricao: str = "usage",
    *,
    permitir_extras: bool = False,
) -> dict[str, int | None]:
    chaves = {"pages_processed", "doc_size_bytes"}
    if permitir_extras:
        if type(objeto) is not dict or not chaves <= set(objeto):
            raise ValueError(f"Esquema inválido em {descricao}.")
        usage = objeto
    else:
        usage = _exigir_chaves(objeto, chaves, descricao)
    doc_size_bytes = usage["doc_size_bytes"]
    if doc_size_bytes is not None:
        doc_size_bytes = _inteiro_nao_negativo(
            doc_size_bytes, f"{descricao}.doc_size_bytes"
        )
    return {
        "pages_processed": _inteiro_nao_negativo(
            usage["pages_processed"], f"{descricao}.pages_processed"
        ),
        "doc_size_bytes": doc_size_bytes,
    }


def _normalizar_mapa_paginas_origem(
    mapa: Mapping[int, int] | None,
    indices_retornados: list[int],
) -> dict[str, int]:
    """Valida e canonicaliza o mapa relativo→original como objeto JSON."""

    if mapa is None:
        itens: list[tuple[object, object]] = [
            (indice, indice) for indice in indices_retornados
        ]
    elif not isinstance(mapa, Mapping):
        raise ValueError("mapa_paginas_origem deve ser um mapping de inteiros.")
    else:
        try:
            itens = list(mapa.items())
        except (RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("mapa_paginas_origem não pôde ser lido.") from exc
    if any(
        type(relativo) is not int
        or relativo < 0
        or type(original) is not int
        or original < 0
        for relativo, original in itens
    ):
        raise ValueError(
            "mapa_paginas_origem exige chaves e valores inteiros não negativos."
        )
    relativos = [int(relativo) for relativo, _ in itens]
    originais = [int(original) for _, original in itens]
    if (
        len(relativos) != len(set(relativos))
        or set(relativos) != set(indices_retornados)
    ):
        raise ValueError(
            "mapa_paginas_origem deve cobrir exatamente todas as páginas retornadas."
        )
    if len(originais) != len(set(originais)):
        raise ValueError("mapa_paginas_origem não pode repetir página original.")
    por_relativo = dict(zip(relativos, originais, strict=True))
    return {str(indice): por_relativo[indice] for indice in sorted(por_relativo)}


def _desserializar_mapa_paginas_origem(objeto: object) -> dict[int, int]:
    if type(objeto) is not dict or not objeto:
        raise ValueError("Mapa de páginas OCR armazenado é inválido.")
    mapa: dict[int, int] = {}
    for chave, valor in objeto.items():
        if (
            type(chave) is not str
            or not chave.isdigit()
            or str(int(chave)) != chave
            or type(valor) is not int
            or valor < 0
        ):
            raise ValueError("Mapa de páginas OCR não está em forma canônica.")
        mapa[int(chave)] = valor
    if len(set(mapa.values())) != len(mapa):
        raise ValueError("Mapa de páginas OCR repete página original.")
    return mapa


def _limpar_celula(texto: object) -> str:
    if type(texto) is not str:
        return ""
    return re.sub(r"\s+", " ", texto).strip().replace("|", " / ")


class _ExtratorTextoHTML(HTMLParser):
    _BLOCOS = frozenset(
        {
            "address",
            "article",
            "aside",
            "blockquote",
            "br",
            "caption",
            "div",
            "figcaption",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "header",
            "li",
            "p",
            "section",
            "td",
            "th",
            "tr",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._ignorar = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        del attrs
        if tag in {"script", "style"}:
            self._ignorar += 1
        elif not self._ignorar and tag in self._BLOCOS:
            self.partes.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignorar:
            self._ignorar -= 1
        elif not self._ignorar and tag in self._BLOCOS:
            self.partes.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignorar:
            self.partes.append(data)

    def texto(self) -> str:
        linhas = [_limpar_celula(linha) for linha in "".join(self.partes).splitlines()]
        return "\n".join(linha for linha in linhas if linha)


class _ExtratorTabelasHTML(HTMLParser):
    """Extrai grades simples; qualquer span torna a grade ambígua."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tabelas: list[tuple[list[list[_CelulaTabela]], bool]] = []
        self._profundidade_tabela = 0
        self._linhas: list[list[_CelulaTabela]] = []
        self._linha: list[_CelulaTabela] | None = None
        self._texto_celula: list[str] | None = None
        self._celula_cabecalho = False
        self._celula_ambigua = False
        self._tabela_ambigua = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table":
            self._profundidade_tabela += 1
            if self._profundidade_tabela == 1:
                self._linhas = []
                self._tabela_ambigua = False
            else:
                self._tabela_ambigua = True
            return
        if self._profundidade_tabela != 1:
            return
        if tag == "tr":
            if self._linha is not None:
                self._tabela_ambigua = True
            self._linha = []
        elif tag in {"td", "th"} and self._linha is not None:
            if self._texto_celula is not None:
                self._tabela_ambigua = True
            atributos = {str(chave).casefold(): valor for chave, valor in attrs}
            spans = []
            for nome in ("colspan", "rowspan"):
                bruto = atributos.get(nome, "1")
                try:
                    spans.append(int(bruto or "1"))
                except ValueError:
                    spans.append(0)
            self._celula_ambigua = any(span != 1 for span in spans)
            self._tabela_ambigua |= self._celula_ambigua
            self._celula_cabecalho = tag == "th"
            self._texto_celula = []
        elif tag == "br" and self._texto_celula is not None:
            self._texto_celula.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self._profundidade_tabela == 1:
                if self._linha:
                    self._linhas.append(self._linha)
                self.tabelas.append((self._linhas, self._tabela_ambigua))
                self._linha = None
                self._texto_celula = None
            self._profundidade_tabela = max(0, self._profundidade_tabela - 1)
            return
        if self._profundidade_tabela != 1:
            return
        if tag in {"td", "th"} and self._texto_celula is not None:
            assert self._linha is not None
            self._linha.append(
                _CelulaTabela(
                    _limpar_celula("".join(self._texto_celula)),
                    self._celula_cabecalho,
                    self._celula_ambigua,
                )
            )
            self._texto_celula = None
        elif tag == "tr" and self._linha is not None:
            self._linhas.append(self._linha)
            self._linha = None

    def handle_data(self, data: str) -> None:
        if self._profundidade_tabela == 1 and self._texto_celula is not None:
            self._texto_celula.append(data)


def _markdown_para_texto(markdown: str) -> str:
    extrator = _ExtratorTextoHTML()
    try:
        extrator.feed(markdown)
        texto = extrator.texto()
    except Exception as exc:  # HTMLParser é tolerante; falhe fechado se mudar.
        raise ValueError("Não foi possível converter o markdown OCR.") from exc
    texto = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"^\s*```[^\n]*$", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^\s{0,3}(?:#{1,6}|>|[-+*])\s+", "", texto, flags=re.MULTILINE)
    texto = texto.replace("**", "").replace("__", "").replace("`", "")
    linhas = [_limpar_celula(linha) for linha in texto.splitlines()]
    return "\n".join(linha for linha in linhas if linha)


def _dividir_linha_markdown(linha: str) -> list[str]:
    linha = linha.strip()
    if linha.startswith("|"):
        linha = linha[1:]
    if linha.endswith("|") and not linha.endswith(r"\|"):
        linha = linha[:-1]
    celulas: list[str] = []
    atual: list[str] = []
    escapado = False
    for caractere in linha:
        if escapado:
            atual.append(caractere)
            escapado = False
        elif caractere == "\\":
            escapado = True
        elif caractere == "|":
            celulas.append(_limpar_celula("".join(atual)))
            atual = []
        else:
            atual.append(caractere)
    if escapado:
        atual.append("\\")
    celulas.append(_limpar_celula("".join(atual)))
    return celulas


def _grades_markdown(conteudo: str) -> list[tuple[list[list[_CelulaTabela]], bool]]:
    linhas = conteudo.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    grades: list[tuple[list[list[_CelulaTabela]], bool]] = []
    indice = 0
    while indice + 1 < len(linhas):
        cabecalho = _dividir_linha_markdown(linhas[indice])
        separadores = _dividir_linha_markdown(linhas[indice + 1])
        if (
            "|" not in linhas[indice]
            or len(cabecalho) < 2
            or len(cabecalho) != len(separadores)
            or any(re.fullmatch(r":?-{3,}:?", item) is None for item in separadores)
        ):
            indice += 1
            continue
        grade = [[_CelulaTabela(item, True) for item in cabecalho]]
        indice += 2
        while indice < len(linhas) and "|" in linhas[indice] and linhas[indice].strip():
            valores = _dividir_linha_markdown(linhas[indice])
            grade.append([_CelulaTabela(item, False) for item in valores])
            indice += 1
        grades.append((grade, False))
    return grades


_PADROES_ESCALA = (
    re.compile(r"R\$\s*(?:milh(?:ão|ões)|bilh(?:ão|ões)|milhares|mil|mi|bi)\b", re.I),
    re.compile(r"\b(?:milh(?:ão|ões)|bilh(?:ão|ões)|milhares)\s+de\s+reais\b", re.I),
    re.compile(r"\bp\.?\s*p\.?\b", re.I),
    re.compile(r"%"),
    re.compile(r"R\$", re.I),
)

_PADRAO_ESCALA_MONETARIA = re.compile(
    r"(?:R\$\s*(milh(?:ão|ões|ao|oes)|bilh(?:ão|ões|ao|oes)|milhares|mil|mi|bi)\b"
    r"|(milh(?:ão|ões|ao|oes)|bilh(?:ão|ões|ao|oes)|milhares|mil)"
    r"\s+de\s+reais\b)",
    re.I,
)


def _canonizar_escala_monetaria(unidade: str) -> str:
    unidade_cf = unidade.casefold()
    if unidade_cf.startswith("bilh") or unidade_cf == "bi":
        return "R$ bilhões"
    if unidade_cf.startswith("milh") or unidade_cf == "mi":
        return "R$ milhões"
    return "R$ mil"


def _escala_monetaria_unica(markdown: str) -> str | None:
    """Obtém uma única unidade monetária da página, sem adivinhar conflitos."""

    escalas = {
        _canonizar_escala_monetaria(match.group(1) or match.group(2))
        for match in _PADRAO_ESCALA_MONETARIA.finditer(markdown)
    }
    return next(iter(escalas)) if len(escalas) == 1 else None


def _separar_escala(texto: str) -> tuple[str, str | None]:
    for padrao in _PADROES_ESCALA:
        match = padrao.search(texto)
        if match:
            escala = _limpar_celula(match.group(0))
            coluna = _limpar_celula(texto[: match.start()] + texto[match.end() :])
            coluna = coluna.strip("()[]-–—: ")
            return coluna or "valor", escala
    return texto, None


_PADRAO_TRIMESTRE_CURTO = re.compile(r"\b([1-4])T(\d{2}|20\d{2})\b", re.I)
_PADRAO_DATA_CURTA = re.compile(
    r"\b\d{1,2}[/-](?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|\d{1,2})"
    r"[/-]\d{2,4}\b",
    re.I,
)
_PADRAO_GRANDEZA = re.compile(
    r"(?<![\w])[-+]?\(?\d+(?:\.\d{3})*(?:,\d+)?\)?(?![\w])"
)


def _periodo_canonico(cabecalho: str) -> str | None:
    periodos: list[str] = []
    for match in _PADRAO_TRIMESTRE_CURTO.finditer(cabecalho):
        ano = match.group(2)
        ano = f"20{ano}" if len(ano) == 2 else ano
        periodo = f"{match.group(1)}T{ano}"
        if periodo not in periodos:
            periodos.append(periodo)
    return periodos[0] if len(periodos) == 1 else None


def _valor_com_escala(valor: str, escala: str) -> str:
    valor = _limpar_celula(valor)
    escala = _limpar_celula(escala)
    if escala.casefold().startswith("r$"):
        unidade = escala[2:].strip()
        return _limpar_celula(f"R$ {valor} {unidade}")
    if "reais" in escala.casefold():
        unidade = re.sub(r"\s+de\s+reais\b", "", escala, flags=re.I)
        return _limpar_celula(f"R$ {valor} {unidade}")
    if escala == "%":
        return f"{valor}%"
    return _limpar_celula(f"{valor} {escala}")


def _campo_fato(texto: str) -> str:
    return _limpar_celula(texto).replace(";", ",").replace("|", "/")


def _fatos_da_grade(
    grade: list[list[_CelulaTabela]],
    ambigua: bool,
    escala_fallback: str | None = None,
) -> list[str]:
    if ambigua or len(grade) < 2 or len(grade[0]) < 2:
        return []
    cabecalho = grade[0]
    nomes_colunas: list[tuple[str, str | None]] = [
        _separar_escala(celula.texto) for celula in cabecalho
    ]
    escalas = {escala for _, escala in nomes_colunas[1:] if escala}
    escala_global = next(iter(escalas)) if len(escalas) == 1 else None
    colunas_normalizadas = [nome.casefold() for nome, _ in nomes_colunas]
    fatos: list[str] = []
    for linha in grade[1:]:
        if len(linha) != len(cabecalho) or not linha or linha[0].ambigua:
            continue
        metrica = _limpar_celula(linha[0].texto)
        if not metrica:
            continue
        _, escala_metrica = _separar_escala(metrica)
        for posicao in range(1, len(linha)):
            celula = linha[posicao]
            coluna, escala = nomes_colunas[posicao]
            periodo = _periodo_canonico(cabecalho[posicao].texto)
            if periodo is None and _PADRAO_DATA_CURTA.search(cabecalho[posicao].texto):
                # Data isolada introduziria escalares estranhos no grounding.
                continue
            numeros_valor = _PADRAO_GRANDEZA.findall(celula.texto)
            if (
                celula.ambigua
                or not celula.texto
                or len(numeros_valor) != 1
                or not coluna
                or not cabecalho[posicao].texto
                or colunas_normalizadas.count(coluna.casefold()) > 1
            ):
                continue
            escala_final = escala or escala_global or escala_metrica or escala_fallback
            if not escala_final:
                valor_formatado = _limpar_celula(celula.texto)
                sufixo_escala = ", escala não informada"
            else:
                valor_formatado = _valor_com_escala(celula.texto, escala_final)
                sufixo_escala = ""
            dimensao = (
                f"período {periodo}"
                if periodo is not None
                else f"coluna {_campo_fato(coluna)}"
            )
            fatos.append(
                "Fato tabular OCR — "
                f"{_campo_fato(metrica)}, {dimensao}, "
                f"valor {_campo_fato(valor_formatado)}{sufixo_escala}."
            )
    return fatos


def _texto_e_fatos_tabela(
    formato: str, conteudo: str, *, escala_fallback: str | None = None
) -> tuple[str, list[str]]:
    if formato == "html":
        extrator = _ExtratorTabelasHTML()
        try:
            extrator.feed(conteudo)
        except Exception as exc:
            raise ValueError("Tabela HTML OCR inválida.") from exc
        grades = extrator.tabelas
        texto = _markdown_para_texto(conteudo)
    else:
        grades = _grades_markdown(conteudo)
        texto = _markdown_para_texto(conteudo)
    fatos: list[str] = []
    for grade, ambigua in grades:
        fatos.extend(_fatos_da_grade(grade, ambigua, escala_fallback))
    return texto, fatos


def _montar_texto_overlay(markdown: str, tabelas: list[dict[str, object]]) -> str:
    partes: list[str] = []
    texto_pagina = _markdown_para_texto(markdown)
    if texto_pagina:
        partes.append(texto_pagina)
    escala_fallback = _escala_monetaria_unica(markdown)
    fatos: list[str] = []
    for tabela in tabelas:
        texto_tabela, fatos_tabela = _texto_e_fatos_tabela(
            str(tabela["formato"]),
            str(tabela["conteudo"]),
            escala_fallback=escala_fallback,
        )
        if texto_tabela:
            rotulo = tabela["identificador"] or "sem-id"
            partes.append(f"Tabela OCR {rotulo}:\n{texto_tabela}")
        fatos.extend(fatos_tabela)
    if fatos:
        partes.append("\n".join(fatos))
    return "\n\n".join(parte for parte in partes if parte).strip()


def _normalizar_tabela(
    bruto: object, formato_solicitado: str, *, serializada: bool
) -> tuple[int | None, dict[str, object]]:
    if type(bruto) is not dict:
        raise ValueError("Tabela OCR deve ser objeto JSON.")
    if serializada:
        tabela = _exigir_chaves(
            bruto,
            {"page_index", "identificador", "formato", "conteudo", "dados"},
            "tabela OCR serializada",
        )
        _validar_valor_json(tabela["dados"], "tabela.dados")
        page_index = _inteiro_nao_negativo(tabela["page_index"], "table.page_index")
        identificador = tabela["identificador"]
        formato = tabela["formato"]
        conteudo = tabela["conteudo"]
    else:
        _validar_valor_json(bruto, "tabela OCR bruta")
        page_index = None
        identificador = bruto.get("id")
        formato = bruto.get("format", formato_solicitado)
        candidatos = [
            bruto[chave]
            for chave in ("content", formato_solicitado)
            if chave in bruto
        ]
        if len(candidatos) != 1:
            raise ValueError("Tabela OCR possui conteúdo ambíguo.")
        conteudo = candidatos[0]
        if "bbox" in bruto:
            _validar_valor_json(bruto["bbox"], "table.bbox")
        if "confidence" in bruto:
            _validar_valor_json(bruto["confidence"], "table.confidence")
    if identificador is not None and (
        type(identificador) is not str or not identificador.strip()
    ):
        raise ValueError("Identificador de tabela OCR é inválido.")
    if formato != formato_solicitado or formato not in _FORMATOS_TABELA:
        raise ValueError("Formato de tabela OCR diverge do solicitado.")
    if type(conteudo) is not str:
        raise ValueError("Conteúdo de tabela OCR deve ser texto.")
    return page_index, {
        "identificador": identificador,
        "formato": formato,
        "conteudo": conteudo,
    }


def _normalizar_bloco(
    bruto: object, *, serializado: bool
) -> tuple[int | None, dict[str, object]]:
    if type(bruto) is not dict:
        raise ValueError("Bloco OCR deve ser objeto JSON.")
    if serializado:
        bloco = _exigir_chaves(
            bruto,
            {"page_index", "tipo", "conteudo", "dados"},
            "bloco OCR serializado",
        )
        _validar_valor_json(bloco["dados"], "bloco.dados")
        page_index = _inteiro_nao_negativo(bloco["page_index"], "block.page_index")
        tipo = bloco["tipo"]
        conteudo = bloco["conteudo"]
    else:
        _validar_valor_json(bruto, "bloco OCR bruto")
        page_index = None
        tipo = bruto.get("type")
        candidatos = [
            bruto[chave]
            for chave in ("content", "text", "markdown", "html")
            if chave in bruto
        ]
        if len(candidatos) > 1:
            raise ValueError("Bloco OCR possui conteúdo ambíguo.")
        conteudo = candidatos[0] if candidatos else None
        for chave in ("bbox", "confidence"):
            if chave in bruto:
                _validar_valor_json(bruto[chave], f"block.{chave}")
    if type(tipo) is not str or not tipo.strip():
        raise ValueError("Tipo de bloco OCR é inválido.")
    if conteudo is not None and type(conteudo) is not str:
        raise ValueError("Conteúdo de bloco OCR é inválido.")
    return page_index, {"tipo": tipo, "conteudo": conteudo}


def _objeto_resultado(resultado: object) -> dict[str, object]:
    if type(resultado) is dict:
        return resultado
    if type(resultado) in {bytes, str}:
        dados = resultado if type(resultado) is bytes else resultado.encode("utf-8")
        return _carregar_json_estrito(dados, "Resposta OCR")
    for atributo in ("bruto", "resposta_bruta"):
        resposta_bruta = getattr(resultado, atributo, None)
        if (
            resposta_bruta is not None
            and resposta_bruta != ""
            and resposta_bruta != b""
        ):
            return _objeto_resultado(resposta_bruta)
    for nome in ("to_dict", "para_dict"):
        serializador = getattr(resultado, nome, None)
        if callable(serializador):
            serializado = serializador()
            if type(serializado) is not dict:
                raise ValueError("Serializador OCR deve devolver objeto JSON.")
            return serializado
    raise ValueError("resultado OCR deve ser dict ou objeto serializável do cliente.")


_CHAVES_PROIBIDAS_RESPOSTA = frozenset(
    {
        "apikey",
        "authorization",
        "bearertoken",
        "documentdata",
        "documenturl",
        "pdf",
        "pdfbytes",
        "secrettoken",
        "xapikey",
    }
)


def _validar_resposta_sem_segredos(
    valor: object, caminho: str = "resposta_bruta"
) -> None:
    """Impede que um payload de requisição/PDF seja confundido com resposta."""

    if type(valor) is dict:
        for chave, item in valor.items():
            chave_normalizada = re.sub(r"[^a-z0-9]", "", chave.casefold())
            if chave_normalizada in _CHAVES_PROIBIDAS_RESPOSTA:
                raise ValueError(f"Campo sensível proibido em {caminho}.")
            if chave_normalizada == "imagebase64" and item is not None:
                raise ValueError(f"Imagem base64 proibida em {caminho}.")
            _validar_resposta_sem_segredos(item, f"{caminho}.{chave}")
    elif type(valor) is list:
        for indice, item in enumerate(valor):
            _validar_resposta_sem_segredos(item, f"{caminho}[{indice}]")
    elif type(valor) is str:
        compacto = valor.lstrip().casefold()
        if (
            compacto.startswith("data:application/pdf")
            or compacto.startswith("data:image/")
            or compacto.startswith("%pdf-")
        ):
            raise ValueError(f"Conteúdo PDF/imagem proibido em {caminho}.")


def _normalizar_resultado(
    resultado: object,
    contrato: dict[str, object],
    mapa_paginas_origem: Mapping[int, int] | None = None,
) -> dict[str, object]:
    bruto = _objeto_resultado(resultado)
    _validar_valor_json(bruto, "resposta OCR")
    _validar_resposta_sem_segredos(bruto)
    # O cliente atual serializa também a resposta completa. Ela é a fonte de
    # verdade; os campos normalizados externos só são aceitos se coincidirem.
    chaves_serializadas = {"modelo", "usage", "pages", "tabelas", "blocos"}
    chaves_serializadas_atuais = chaves_serializadas | {"modelo_solicitado"}
    if frozenset(bruto) in {
        frozenset(chaves_serializadas | {"resposta_bruta"}),
        frozenset(chaves_serializadas_atuais | {"resposta_bruta"}),
    }:
        resposta_bruta = bruto["resposta_bruta"]
        if type(resposta_bruta) is not dict:
            raise ValueError("resposta_bruta OCR serializada deve ser objeto JSON.")
        if "modelo_solicitado" in bruto and bruto["modelo_solicitado"] != contrato["modelo"]:
            raise ValueError("Modelo solicitado serializado diverge do contrato OCR.")
        externo = _normalizar_resultado(
            {chave: bruto[chave] for chave in chaves_serializadas},
            contrato,
            mapa_paginas_origem,
        )
        interno = _normalizar_resultado(
            resposta_bruta, contrato, mapa_paginas_origem
        )
        for chave in ("modelo_retornado", "usage", "paginas"):
            if externo[chave] != interno[chave]:
                raise ValueError(
                    "Campos normalizados do ResultadoOCR divergem da resposta bruta."
                )
        return interno
    formato = str(contrato["table_format"])
    include_blocks = bool(contrato["include_blocks"])
    paginas: dict[int, dict[str, object]] = {}

    if {"model", "usage_info", "pages"} <= set(bruto):
        modelo_retornado = bruto["model"]
        usage = _normalizar_usage(
            bruto["usage_info"], "usage_info", permitir_extras=True
        )
        paginas_brutas = bruto["pages"]
        if type(paginas_brutas) is not list:
            raise ValueError("pages OCR deve ser lista.")
        for posicao, pagina_bruta in enumerate(paginas_brutas):
            if type(pagina_bruta) is not dict:
                raise ValueError(f"pages[{posicao}] deve ser objeto JSON.")
            if "confidence_scores" not in pagina_bruta:
                raise ValueError(
                    f"pages[{posicao}].confidence_scores é obrigatório."
                )
            obrigatorias = {"index", "markdown", "confidence_scores"}
            if not obrigatorias <= set(pagina_bruta):
                raise ValueError(f"Esquema inválido em pages[{posicao}].")
            indice = _inteiro_nao_negativo(pagina_bruta["index"], "page.index")
            markdown = pagina_bruta["markdown"]
            if type(markdown) is not str or indice in paginas:
                raise ValueError("Página OCR possui markdown inválido ou índice duplicado.")
            confianca = _normalizar_confidence_scores(
                pagina_bruta["confidence_scores"],
                f"pages[{posicao}].confidence_scores",
            )
            tabelas_brutas = pagina_bruta.get("tables", [])
            blocos_brutos = pagina_bruta.get("blocks", [])
            tabelas_brutas = [] if tabelas_brutas is None else tabelas_brutas
            blocos_brutos = [] if blocos_brutos is None else blocos_brutos
            if type(tabelas_brutas) is not list or type(blocos_brutos) is not list:
                raise ValueError("tables/blocks OCR devem ser listas.")
            tabelas = [
                _normalizar_tabela(item, formato, serializada=False)[1]
                for item in tabelas_brutas
            ]
            blocos = [
                _normalizar_bloco(item, serializado=False)[1]
                for item in blocos_brutos
            ]
            paginas[indice] = {
                "indice": indice,
                "markdown": markdown,
                "tabelas": tabelas,
                "blocos": blocos,
                **confianca,
            }
    elif set(bruto) == {"modelo", "usage", "pages", "tabelas", "blocos"}:
        modelo_retornado = bruto["modelo"]
        usage = _normalizar_usage(bruto["usage"])
        paginas_brutas = bruto["pages"]
        tabelas_brutas = bruto["tabelas"]
        blocos_brutos = bruto["blocos"]
        if any(type(item) is not list for item in (paginas_brutas, tabelas_brutas, blocos_brutos)):
            raise ValueError("Listas da resposta OCR serializada são inválidas.")
        for posicao, pagina_bruta in enumerate(paginas_brutas):
            pagina = _exigir_chaves(
                pagina_bruta,
                {
                    "index",
                    "markdown",
                    "average_page_confidence_score",
                    "minimum_page_confidence_score",
                },
                f"pages[{posicao}]",
            )
            indice = _inteiro_nao_negativo(pagina["index"], "page.index")
            if type(pagina["markdown"]) is not str or indice in paginas:
                raise ValueError("Página OCR possui markdown inválido ou índice duplicado.")
            confianca = _normalizar_confidence_scores(
                {
                    "average_page_confidence_score": pagina[
                        "average_page_confidence_score"
                    ],
                    "minimum_page_confidence_score": pagina[
                        "minimum_page_confidence_score"
                    ],
                },
                f"pages[{posicao}]",
            )
            paginas[indice] = {
                "indice": indice,
                "markdown": pagina["markdown"],
                "tabelas": [],
                "blocos": [],
                **confianca,
            }
        for tabela_bruta in tabelas_brutas:
            indice, tabela = _normalizar_tabela(
                tabela_bruta, formato, serializada=True
            )
            if indice not in paginas:
                raise ValueError("Tabela OCR referencia página ausente.")
            paginas[indice]["tabelas"].append(tabela)
        for bloco_bruto in blocos_brutos:
            indice, bloco = _normalizar_bloco(bloco_bruto, serializado=True)
            if indice not in paginas:
                raise ValueError("Bloco OCR referencia página ausente.")
            paginas[indice]["blocos"].append(bloco)
    else:
        raise ValueError("Resposta OCR não segue um esquema persistível conhecido.")

    modelo_retornado = _validar_modelo(modelo_retornado)
    if not _modelo_observado_compativel(
        str(contrato["modelo"]), modelo_retornado
    ):
        raise ValueError("Modelo retornado pelo OCR diverge do modelo solicitado.")
    if not paginas or sorted(paginas) != list(paginas):
        raise ValueError("Páginas OCR devem existir e estar em ordem crescente.")
    if usage["pages_processed"] != len(paginas):
        raise ValueError("usage.pages_processed diverge das páginas OCR.")
    if not include_blocks and any(pagina["blocos"] for pagina in paginas.values()):
        raise ValueError("Resposta OCR inclui blocos que não foram solicitados.")

    indices_retornados = list(paginas)
    mapa_canonico = _normalizar_mapa_paginas_origem(
        mapa_paginas_origem, indices_retornados
    )
    paginas_normalizadas: list[dict[str, object]] = []
    for indice_relativo, pagina in paginas.items():
        texto = _montar_texto_overlay(
            str(pagina["markdown"]), pagina["tabelas"]  # type: ignore[arg-type]
        )
        paginas_normalizadas.append(
            {
                **pagina,
                "indice": mapa_canonico[str(indice_relativo)],
                "texto": texto,
            }
        )
    paginas_normalizadas.sort(key=lambda pagina: int(pagina["indice"]))
    return {
        "modelo_retornado": modelo_retornado,
        "usage": usage,
        "paginas": paginas_normalizadas,
        # Cópia JSON defensiva: o chamador não consegue mutar o snapshot depois
        # desta validação, e bytes/chaves/PDF de requisição nunca entram aqui.
        "resposta_bruta": _carregar_json_estrito(
            _bytes_canonicos(bruto), "Resposta OCR bruta"
        ),
        "mapa_paginas_origem": mapa_canonico,
    }


def _artefato(
    *,
    documento: str,
    sha256_pdf: str,
    contrato: dict[str, object],
    resultado: dict[str, object],
) -> dict[str, object]:
    resposta_bruta = resultado["resposta_bruta"]
    mapa_paginas_origem = resultado["mapa_paginas_origem"]
    return {
        "versao": VERSAO_CACHE_OCR,
        "documento": documento,
        "sha256_pdf": sha256_pdf,
        "contrato_requisicao": contrato,
        "modelo_retornado": resultado["modelo_retornado"],
        "usage": resultado["usage"],
        "paginas": resultado["paginas"],
        "resposta_bruta": resposta_bruta,
        "sha256_resposta_bruta": _sha256(_bytes_canonicos(resposta_bruta)),
        "mapa_paginas_origem": mapa_paginas_origem,
        "sha256_mapa_paginas_origem": _sha256(
            _bytes_canonicos(mapa_paginas_origem)
        ),
    }


def _manifesto_vazio() -> dict[str, object]:
    return {"versao": VERSAO_CACHE_OCR, "documentos": {}}


def _caminho_lock(dir_cache: Path) -> Path:
    return dir_cache.parent / f".{dir_cache.name}.lock"


def _rejeitar_symlink(caminho: Path, descricao: str) -> None:
    if caminho.is_symlink():
        raise ValueError(f"{descricao} não pode ser symlink: {caminho}.")


def _normalizar_dir_cache(dir_cache: Path) -> Path:
    """Normaliza lexicalmente a raiz e rejeita symlinks antes de abrir o lock."""

    caminho = Path(dir_cache)
    if not caminho.name or ".." in caminho.parts:
        raise ValueError("dir_cache deve apontar para um diretório específico e seguro.")
    try:
        absoluto = Path(os.path.abspath(os.fspath(caminho)))
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("dir_cache possui caminho inválido.") from exc
    atual = Path(absoluto.anchor)
    for parte in absoluto.parts[1:]:
        atual = atual / parte
        _rejeitar_symlink(atual, "Componente de dir_cache")
    return absoluto


def _preparar_raiz(dir_cache: Path, *, criar: bool) -> None:
    # Repete a verificação sob lock para reduzir a janela de troca de caminho.
    dir_cache = _normalizar_dir_cache(dir_cache)
    _rejeitar_symlink(dir_cache, "Diretório do cache OCR")
    if criar:
        dir_cache.mkdir(parents=True, exist_ok=True)
    if dir_cache.exists() and not dir_cache.is_dir():
        raise ValueError("Diretório do cache OCR não é um diretório regular.")
    if not dir_cache.exists():
        return
    _rejeitar_symlink(dir_cache / NOME_MANIFESTO_OCR, "Manifesto OCR")
    respostas = dir_cache / NOME_DIRETORIO_RESPOSTAS
    _rejeitar_symlink(respostas, "Diretório de respostas OCR")
    if respostas.exists() and not respostas.is_dir():
        raise ValueError("respostas do cache OCR não é diretório regular.")


def _caminho_relativo_seguro(dir_cache: Path, relativo: object) -> Path:
    if type(relativo) is not str:
        raise ValueError("Caminho de artefato OCR deve ser texto.")
    puro = PurePosixPath(relativo)
    if puro.is_absolute() or any(parte in {"", ".", ".."} for parte in puro.parts):
        raise ValueError("Manifesto OCR contém path traversal.")
    caminho = dir_cache.joinpath(*puro.parts)
    atual = dir_cache
    for parte in puro.parts:
        atual = atual / parte
        _rejeitar_symlink(atual, "Componente do cache OCR")
    return caminho


def _ler_arquivo_regular(caminho: Path, descricao: str) -> bytes:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    # Sem O_NONBLOCK, abrir uma FIFO adulterada para leitura poderia bloquear
    # antes que o fstat tivesse a oportunidade de recusá-la.
    flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        descritor = os.open(os.fspath(caminho), flags)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(f"{descricao} ausente, inacessível ou inseguro.") from exc

    try:
        try:
            estado_inicial = os.fstat(descritor)
            if (
                not stat.S_ISREG(estado_inicial.st_mode)
                or estado_inicial.st_nlink != 1
            ):
                raise ValueError(f"{descricao} deve ser arquivo regular exclusivo.")
            tamanho = estado_inicial.st_size
            if tamanho < 0 or tamanho > _MAX_ARQUIVO_CACHE_OCR_BYTES:
                raise ValueError(f"{descricao} excede o limite seguro de leitura.")

            partes: list[bytes] = []
            total = 0
            # Lê pelo descritor já validado. O byte adicional detecta crescimento
            # ocorrido depois do fstat inicial sem reabrir o pathname.
            while total <= tamanho:
                quantidade = min(
                    _BLOCO_LEITURA_CACHE_OCR_BYTES,
                    tamanho - total + 1,
                )
                bloco = os.read(descritor, quantidade)
                if not bloco:
                    break
                partes.append(bloco)
                total += len(bloco)
                if total > tamanho:
                    raise ValueError(f"{descricao} mudou durante a leitura.")

            estado_final = os.fstat(descritor)
            if (
                total != tamanho
                or not stat.S_ISREG(estado_final.st_mode)
                or estado_final.st_nlink != 1
                or estado_final.st_dev != estado_inicial.st_dev
                or estado_final.st_ino != estado_inicial.st_ino
                or estado_final.st_size != estado_inicial.st_size
                or estado_final.st_mtime_ns != estado_inicial.st_mtime_ns
                or estado_final.st_ctime_ns != estado_inicial.st_ctime_ns
            ):
                raise ValueError(f"{descricao} mudou durante a leitura.")
            return b"".join(partes)
        except OSError as exc:
            raise ValueError(f"Não foi possível ler {descricao} com segurança.") from exc
    finally:
        try:
            os.close(descritor)
        except OSError:
            pass


def _escrever_atomico(caminho: Path, dados: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    _rejeitar_symlink(caminho.parent, "Diretório de destino OCR")
    descritor, nome = tempfile.mkstemp(
        prefix=f".{caminho.name}.tmp-", dir=str(caminho.parent)
    )
    temporario = Path(nome)
    try:
        with os.fdopen(descritor, "wb") as arquivo:
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
        try:
            descritor_dir = os.open(caminho.parent, os.O_RDONLY)
            try:
                os.fsync(descritor_dir)
            finally:
                os.close(descritor_dir)
        except OSError:
            pass
    finally:
        if temporario.exists():
            temporario.unlink()


def _validar_pagina_artefato(objeto: object) -> dict[str, object]:
    chaves_legadas = {"indice", "markdown", "tabelas", "blocos", "texto"}
    chaves_atuais = chaves_legadas | {
        "average_page_confidence_score",
        "minimum_page_confidence_score",
    }
    if type(objeto) is not dict or set(objeto) not in {
        frozenset(chaves_legadas),
        frozenset(chaves_atuais),
    }:
        raise ValueError("Esquema inválido em página do artefato OCR.")
    pagina = objeto
    indice = _inteiro_nao_negativo(pagina["indice"], "pagina.indice")
    if type(pagina["markdown"]) is not str or type(pagina["texto"]) is not str:
        raise ValueError("markdown/texto da página OCR devem ser strings.")
    if type(pagina["tabelas"]) is not list or type(pagina["blocos"]) is not list:
        raise ValueError("tabelas/blocos da página OCR devem ser listas.")
    tabelas: list[dict[str, object]] = []
    for item in pagina["tabelas"]:
        tabela = _exigir_chaves(
            item, {"identificador", "formato", "conteudo"}, "tabela congelada"
        )
        identificador = tabela["identificador"]
        if identificador is not None and (
            type(identificador) is not str or not identificador.strip()
        ):
            raise ValueError("Identificador de tabela congelada é inválido.")
        if tabela["formato"] not in _FORMATOS_TABELA or type(tabela["conteudo"]) is not str:
            raise ValueError("Tabela congelada possui formato/conteúdo inválido.")
        tabelas.append(tabela)
    blocos: list[dict[str, object]] = []
    for item in pagina["blocos"]:
        bloco = _exigir_chaves(item, {"tipo", "conteudo"}, "bloco congelado")
        if type(bloco["tipo"]) is not str or not bloco["tipo"].strip():
            raise ValueError("Tipo de bloco congelado é inválido.")
        if bloco["conteudo"] is not None and type(bloco["conteudo"]) is not str:
            raise ValueError("Conteúdo de bloco congelado é inválido.")
        blocos.append(bloco)
    esperado = _montar_texto_overlay(str(pagina["markdown"]), tabelas)
    if pagina["texto"] != esperado:
        raise ValueError("Texto derivado da página OCR foi adulterado.")
    normalizada = {
        "indice": indice,
        "markdown": pagina["markdown"],
        "tabelas": tabelas,
        "blocos": blocos,
        "texto": pagina["texto"],
    }
    if set(pagina) == chaves_atuais:
        normalizada.update(
            _normalizar_confidence_scores(
                {
                    "average_page_confidence_score": pagina[
                        "average_page_confidence_score"
                    ],
                    "minimum_page_confidence_score": pagina[
                        "minimum_page_confidence_score"
                    ],
                },
                "página do artefato OCR",
            )
        )
    return normalizada


def _validar_artefato(objeto: object) -> dict[str, object]:
    artefato = _exigir_chaves(
        objeto,
        {
            "versao",
            "documento",
            "sha256_pdf",
            "contrato_requisicao",
            "modelo_retornado",
            "usage",
            "paginas",
            "resposta_bruta",
            "sha256_resposta_bruta",
            "mapa_paginas_origem",
            "sha256_mapa_paginas_origem",
        },
        "artefato OCR",
    )
    if artefato["versao"] != VERSAO_CACHE_OCR:
        raise ValueError("Versão do artefato OCR é incompatível.")
    documento = _validar_documento(artefato["documento"])
    sha256_pdf = _validar_sha_pdf(artefato["sha256_pdf"])
    contrato = _validar_contrato_armazenado(artefato["contrato_requisicao"])
    modelo = _validar_modelo(artefato["modelo_retornado"])
    if not _modelo_observado_compativel(str(contrato["modelo"]), modelo):
        raise ValueError("Modelo retornado diverge do contrato congelado.")
    usage = _normalizar_usage(artefato["usage"])
    resposta_bruta = artefato["resposta_bruta"]
    if type(resposta_bruta) is not dict:
        raise ValueError("resposta_bruta do artefato OCR deve ser objeto JSON.")
    _validar_valor_json(resposta_bruta, "artefato.resposta_bruta")
    hash_resposta_bruta = artefato["sha256_resposta_bruta"]
    if (
        type(hash_resposta_bruta) is not str
        or _PADRAO_SHA256.fullmatch(hash_resposta_bruta) is None
        or hash_resposta_bruta != _sha256(_bytes_canonicos(resposta_bruta))
    ):
        raise ValueError("Checksum da resposta bruta OCR diverge do artefato.")
    mapa_armazenado = artefato["mapa_paginas_origem"]
    mapa_paginas_origem = _desserializar_mapa_paginas_origem(mapa_armazenado)
    hash_mapa = artefato["sha256_mapa_paginas_origem"]
    if (
        type(hash_mapa) is not str
        or _PADRAO_SHA256.fullmatch(hash_mapa) is None
        or hash_mapa != _sha256(_bytes_canonicos(mapa_armazenado))
    ):
        raise ValueError("Checksum do mapa de páginas OCR diverge do artefato.")
    if type(artefato["paginas"]) is not list or not artefato["paginas"]:
        raise ValueError("Artefato OCR deve conter páginas.")
    paginas_armazenadas = [
        _validar_pagina_artefato(item) for item in artefato["paginas"]
    ]
    indices = [pagina["indice"] for pagina in paginas_armazenadas]
    if indices != sorted(indices) or len(indices) != len(set(indices)):
        raise ValueError("Páginas congeladas estão fora de ordem ou duplicadas.")
    if usage["pages_processed"] != len(paginas_armazenadas):
        raise ValueError("Usage do artefato diverge da quantidade de páginas.")
    if not contrato["include_blocks"] and any(
        pagina["blocos"] for pagina in paginas_armazenadas
    ):
        raise ValueError("Artefato contém blocos não solicitados.")
    if any(
        tabela["formato"] != contrato["table_format"]
        for pagina in paginas_armazenadas
        for tabela in pagina["tabelas"]
    ):
        raise ValueError("Artefato contém tabela em formato divergente.")
    derivado = _normalizar_resultado(
        resposta_bruta, contrato, mapa_paginas_origem
    )
    chaves_confianca = {
        "average_page_confidence_score",
        "minimum_page_confidence_score",
    }
    estado_confianca = [
        chaves_confianca <= set(pagina) for pagina in paginas_armazenadas
    ]
    if any(estado_confianca) and not all(estado_confianca):
        raise ValueError("Artefato OCR mistura páginas legadas e atuais.")
    paginas_derivadas = derivado["paginas"]
    paginas_comparacao = paginas_armazenadas
    if not all(estado_confianca):
        paginas_comparacao = [
            {
                chave: valor
                for chave, valor in pagina.items()
                if chave not in chaves_confianca
            }
            for pagina in paginas_derivadas
        ]
    if (
        derivado["modelo_retornado"] != modelo
        or derivado["usage"] != usage
        or paginas_comparacao != paginas_armazenadas
        or derivado["mapa_paginas_origem"] != mapa_armazenado
    ):
        raise ValueError("Dados derivados divergem da resposta bruta OCR congelada.")
    return {
        "versao": VERSAO_CACHE_OCR,
        "documento": documento,
        "sha256_pdf": sha256_pdf,
        "contrato_requisicao": contrato,
        "modelo_retornado": modelo,
        "usage": usage,
        # Artefatos v1 pagos sem os campos derivados permanecem válidos: os
        # scores são reconstruídos da resposta bruta e expostos em memória.
        "paginas": paginas_derivadas,
        "_confianca_derivada_persistida": all(estado_confianca),
        "_hashes_paginas_armazenadas": {
            int(pagina["indice"]): _sha256(_bytes_canonicos(pagina))
            for pagina in paginas_armazenadas
        },
        "resposta_bruta": resposta_bruta,
        "sha256_resposta_bruta": hash_resposta_bruta,
        "mapa_paginas_origem": mapa_armazenado,
        "sha256_mapa_paginas_origem": hash_mapa,
    }


def _carregar_manifesto(dir_cache: Path) -> tuple[dict[str, object], bytes | None]:
    caminho = dir_cache / NOME_MANIFESTO_OCR
    if not caminho.exists():
        return _manifesto_vazio(), None
    dados = _ler_arquivo_regular(caminho, "Manifesto OCR")
    manifesto = _carregar_json_estrito(dados, "Manifesto OCR")
    if dados != _bytes_canonicos(manifesto):
        raise ValueError("Manifesto OCR não está em JSON canônico.")
    return manifesto, dados


def _validar_manifesto(
    dir_cache: Path, manifesto: object
) -> dict[tuple[str, str], dict[str, object]]:
    raiz = _exigir_chaves(manifesto, {"versao", "documentos"}, "manifesto OCR")
    if raiz["versao"] != VERSAO_CACHE_OCR or type(raiz["documentos"]) is not dict:
        raise ValueError("Versão/documentos do manifesto OCR são inválidos.")
    artefatos: dict[tuple[str, str], dict[str, object]] = {}
    for documento, entrada_bruta in raiz["documentos"].items():
        documento = _validar_documento(documento)
        entrada = _exigir_chaves(
            entrada_bruta,
            {
                "sha256_pdf",
                "contrato_requisicao",
                "modelo_retornado",
                "respostas",
                "paginas",
            },
            f"documentos.{documento}",
        )
        sha_pdf = _validar_sha_pdf(entrada["sha256_pdf"])
        contrato = _validar_contrato_armazenado(entrada["contrato_requisicao"])
        modelo = _validar_modelo(entrada["modelo_retornado"])
        if not _modelo_observado_compativel(str(contrato["modelo"]), modelo):
            raise ValueError("Modelo do documento diverge do contrato OCR.")
        if type(entrada["respostas"]) is not dict or not entrada["respostas"]:
            raise ValueError("Documento OCR deve referenciar ao menos uma resposta.")
        if type(entrada["paginas"]) is not dict or not entrada["paginas"]:
            raise ValueError("Documento OCR deve congelar ao menos uma página.")

        dir_documento = dir_cache / NOME_DIRETORIO_RESPOSTAS / documento
        _rejeitar_symlink(dir_documento, "Diretório do documento OCR")
        if not dir_documento.is_dir():
            raise ValueError("Diretório do documento OCR está ausente.")
        indices_por_resposta: dict[str, set[int]] = {}
        hashes_paginas_por_resposta: dict[str, dict[int, str]] = {}
        conteudos_paginas: dict[int, dict[str, object]] = {}
        for digest, registro_bruto in entrada["respostas"].items():
            if type(digest) is not str or _PADRAO_SHA256.fullmatch(digest) is None:
                raise ValueError("Digest de resposta OCR é inválido.")
            registro = _exigir_chaves(
                registro_bruto,
                {
                    "arquivo",
                    "paginas",
                    "modelo_retornado",
                    "usage",
                    "mapa_paginas_origem",
                    "sha256_mapa_paginas_origem",
                },
                "registro de resposta OCR",
            )
            esperado_relativo = f"{NOME_DIRETORIO_RESPOSTAS}/{documento}/{digest}.json"
            if registro["arquivo"] != esperado_relativo:
                raise ValueError("Manifesto OCR contém caminho inesperado/traversal.")
            caminho = _caminho_relativo_seguro(dir_cache, registro["arquivo"])
            dados = _ler_arquivo_regular(caminho, "Resposta OCR congelada")
            if _sha256(dados) != digest:
                raise ValueError("Checksum da resposta OCR diverge do manifesto.")
            objeto = _carregar_json_estrito(dados, "Resposta OCR congelada")
            if dados != _bytes_canonicos(objeto):
                raise ValueError("Resposta OCR não está em JSON canônico.")
            artefato = _validar_artefato(objeto)
            if (
                artefato["documento"] != documento
                or artefato["sha256_pdf"] != sha_pdf
                or artefato["contrato_requisicao"] != contrato
                or artefato["modelo_retornado"] != modelo
            ):
                raise ValueError("Resposta OCR diverge da entrada do manifesto.")
            paginas_registro = registro["paginas"]
            if (
                type(paginas_registro) is not list
                or any(type(indice) is not int or indice < 0 for indice in paginas_registro)
                or paginas_registro != sorted(set(paginas_registro))
            ):
                raise ValueError("Lista de páginas da resposta OCR é inválida.")
            indices_artefato = [pagina["indice"] for pagina in artefato["paginas"]]
            if paginas_registro != indices_artefato:
                raise ValueError("Páginas do manifesto divergem da resposta OCR.")
            usage = _normalizar_usage(registro["usage"], "registro.usage")
            mapa_registro = registro["mapa_paginas_origem"]
            _desserializar_mapa_paginas_origem(mapa_registro)
            hash_mapa_registro = registro["sha256_mapa_paginas_origem"]
            if (
                registro["modelo_retornado"] != modelo
                or usage != artefato["usage"]
                or mapa_registro != artefato["mapa_paginas_origem"]
                or hash_mapa_registro != artefato["sha256_mapa_paginas_origem"]
            ):
                raise ValueError("Modelo/usage do manifesto divergem da resposta OCR.")
            indices_por_resposta[digest] = set(indices_artefato)
            hashes_paginas_por_resposta[digest] = artefato[
                "_hashes_paginas_armazenadas"
            ]
            artefatos[(documento, digest)] = artefato
            for pagina in artefato["paginas"]:
                indice = int(pagina["indice"])
                anterior = conteudos_paginas.get(indice)
                if anterior is not None and anterior != pagina:
                    raise ValueError("Página OCR foi congelada com conteúdos conflitantes.")
                conteudos_paginas[indice] = pagina

        indices_manifesto: set[int] = set()
        for chave, registro_bruto in entrada["paginas"].items():
            if type(chave) is not str or not chave.isdigit() or str(int(chave)) != chave:
                raise ValueError("Índice de página no manifesto OCR é inválido.")
            indice = int(chave)
            chaves_legadas = {"arquivo", "hash_artefato", "hash_conteudo"}
            chaves_atuais = chaves_legadas | {
                "average_page_confidence_score",
                "minimum_page_confidence_score",
            }
            if type(registro_bruto) is not dict or set(registro_bruto) not in {
                frozenset(chaves_legadas),
                frozenset(chaves_atuais),
            }:
                raise ValueError("Esquema inválido em registro de página OCR.")
            registro = registro_bruto
            digest = registro["hash_artefato"]
            if type(digest) is not str or digest not in entrada["respostas"]:
                raise ValueError("Página OCR aponta para resposta inexistente.")
            esperado_relativo = f"{NOME_DIRETORIO_RESPOSTAS}/{documento}/{digest}.json"
            if registro["arquivo"] != esperado_relativo:
                raise ValueError("Página OCR contém caminho inesperado/traversal.")
            if indice not in indices_por_resposta[digest]:
                raise ValueError("Página OCR não existe no artefato apontado.")
            if registro["hash_conteudo"] != hashes_paginas_por_resposta[
                digest
            ].get(indice):
                raise ValueError("Checksum de conteúdo da página OCR diverge.")
            pagina_derivada = conteudos_paginas[indice]
            artefato_pagina = artefatos[(documento, digest)]
            if (
                artefato_pagina["_confianca_derivada_persistida"]
                and set(registro) == chaves_legadas
            ):
                raise ValueError(
                    "Manifesto OCR atual não pode omitir scores persistidos."
                )
            if set(registro) == chaves_atuais:
                confianca_manifesto = _normalizar_confidence_scores(
                    {
                        "average_page_confidence_score": registro[
                            "average_page_confidence_score"
                        ],
                        "minimum_page_confidence_score": registro[
                            "minimum_page_confidence_score"
                        ],
                    },
                    "registro de página OCR",
                )
                if any(
                    confianca_manifesto[chave] != pagina_derivada[chave]
                    for chave in confianca_manifesto
                ):
                    raise ValueError(
                        "Confiança do manifesto diverge da resposta bruta OCR."
                    )
            indices_manifesto.add(indice)
        if indices_manifesto != set(conteudos_paginas):
            raise ValueError("Mapa de páginas OCR diverge das respostas congeladas.")
    return artefatos


def _parametros_contrato(
    *,
    modelo: str,
    endpoint: str,
    table_format: str,
    include_blocks: bool,
    confidence: str,
) -> dict[str, object]:
    return _normalizar_contrato(
        modelo=modelo,
        endpoint=endpoint,
        table_format=table_format,
        include_blocks=include_blocks,
        confidence=confidence,
    )


def persistir_resposta_ocr(
    resultado: object,
    *,
    documento: str,
    sha256_pdf: str,
    modelo: str,
    endpoint: str,
    table_format: str,
    include_blocks: bool,
    confidence: str,
    dir_cache: Path,
    mapa_paginas_origem: Mapping[int, int] | None = None,
) -> Path:
    """Congela uma resposta OCR e devolve seu caminho content-addressed.

    A função nunca recebe credencial e só persiste o hash do PDF, não seus
    bytes. Repetir exatamente a mesma operação é idempotente.
    """

    documento = _validar_documento(documento)
    sha256_pdf = _validar_sha_pdf(sha256_pdf)
    contrato = _parametros_contrato(
        modelo=modelo,
        endpoint=endpoint,
        table_format=table_format,
        include_blocks=include_blocks,
        confidence=confidence,
    )
    resultado_normalizado = _normalizar_resultado(
        resultado, contrato, mapa_paginas_origem
    )
    artefato = _artefato(
        documento=documento,
        sha256_pdf=sha256_pdf,
        contrato=contrato,
        resultado=resultado_normalizado,
    )
    dados_artefato = _bytes_canonicos(artefato)
    digest = _sha256(dados_artefato)
    relativo = f"{NOME_DIRETORIO_RESPOSTAS}/{documento}/{digest}.json"
    dir_cache = _normalizar_dir_cache(Path(dir_cache))
    lock = _caminho_lock(dir_cache)
    _rejeitar_symlink(lock, "Lock do cache OCR")
    with bloqueio_exclusivo(lock, "o cache OCR"):
        _preparar_raiz(dir_cache, criar=True)
        manifesto, dados_manifesto_anteriores = _carregar_manifesto(dir_cache)
        artefatos_existentes = _validar_manifesto(dir_cache, manifesto)
        documentos = manifesto["documentos"]
        assert type(documentos) is dict
        entrada = documentos.get(documento)
        if entrada is not None:
            if (
                entrada["sha256_pdf"] != sha256_pdf
                or entrada["contrato_requisicao"] != contrato
                or entrada["modelo_retornado"] != resultado_normalizado["modelo_retornado"]
            ):
                raise ValueError(
                    "Documento OCR já está congelado com PDF/contrato/modelo diferente."
                )
            paginas_existentes: dict[int, dict[str, object]] = {}
            for chave, registro in entrada["paginas"].items():
                artefato_existente = artefatos_existentes[
                    (documento, registro["hash_artefato"])
                ]
                paginas_existentes[int(chave)] = next(
                    pagina
                    for pagina in artefato_existente["paginas"]
                    if pagina["indice"] == int(chave)
                )
            for pagina in resultado_normalizado["paginas"]:
                indice = int(pagina["indice"])
                if indice in paginas_existentes and paginas_existentes[indice] != pagina:
                    raise ValueError(
                        f"Página OCR {indice} já foi congelada com conteúdo diferente."
                    )
        else:
            entrada = {
                "sha256_pdf": sha256_pdf,
                "contrato_requisicao": contrato,
                "modelo_retornado": resultado_normalizado["modelo_retornado"],
                "respostas": {},
                "paginas": {},
            }
            documentos[documento] = entrada

        caminho_artefato = _caminho_relativo_seguro(dir_cache, relativo)
        caminho_artefato.parent.mkdir(parents=True, exist_ok=True)
        _rejeitar_symlink(caminho_artefato.parent, "Diretório do documento OCR")
        if caminho_artefato.exists():
            existentes = _ler_arquivo_regular(caminho_artefato, "Resposta OCR")
            if existentes != dados_artefato:
                raise ValueError("Arquivo content-addressed OCR possui conteúdo divergente.")
        else:
            _escrever_atomico(caminho_artefato, dados_artefato)

        respostas = entrada["respostas"]
        paginas_manifesto = entrada["paginas"]
        assert type(respostas) is dict and type(paginas_manifesto) is dict
        novo_registro = {
            "arquivo": relativo,
            "paginas": [pagina["indice"] for pagina in resultado_normalizado["paginas"]],
            "modelo_retornado": resultado_normalizado["modelo_retornado"],
            "usage": resultado_normalizado["usage"],
            "mapa_paginas_origem": resultado_normalizado[
                "mapa_paginas_origem"
            ],
            "sha256_mapa_paginas_origem": artefato[
                "sha256_mapa_paginas_origem"
            ],
        }
        anterior = respostas.get(digest)
        if anterior is not None and anterior != novo_registro:
            raise ValueError("Registro content-addressed OCR diverge do manifesto.")
        respostas[digest] = novo_registro
        for pagina in resultado_normalizado["paginas"]:
            indice = int(pagina["indice"])
            chave = str(indice)
            hash_conteudo = _sha256(_bytes_canonicos(pagina))
            paginas_manifesto[chave] = {
                "arquivo": relativo,
                "hash_artefato": digest,
                "hash_conteudo": hash_conteudo,
                "average_page_confidence_score": pagina[
                    "average_page_confidence_score"
                ],
                "minimum_page_confidence_score": pagina[
                    "minimum_page_confidence_score"
                ],
            }

        dados_manifesto = _bytes_canonicos(manifesto)
        if dados_manifesto != dados_manifesto_anteriores:
            _escrever_atomico(dir_cache / NOME_MANIFESTO_OCR, dados_manifesto)
        # Validação pós-promoção torna bugs de serialização falha fechada.
        manifesto_validado, _ = _carregar_manifesto(dir_cache)
        _validar_manifesto(dir_cache, manifesto_validado)
        del artefatos_existentes
        return caminho_artefato


def carregar_overlay_documento(
    *,
    documento: str,
    sha256_pdf: str,
    modelo: str,
    endpoint: str,
    table_format: str,
    include_blocks: bool,
    confidence: str,
    dir_cache: Path,
) -> tuple[PaginaOCRCongelada, ...]:
    """Carrega páginas congeladas somente se todo o snapshot permanecer íntegro."""

    documento = _validar_documento(documento)
    sha256_pdf = _validar_sha_pdf(sha256_pdf)
    contrato = _parametros_contrato(
        modelo=modelo,
        endpoint=endpoint,
        table_format=table_format,
        include_blocks=include_blocks,
        confidence=confidence,
    )
    dir_cache = _normalizar_dir_cache(Path(dir_cache))
    lock = _caminho_lock(dir_cache)
    _rejeitar_symlink(lock, "Lock do cache OCR")
    with bloqueio_compartilhado(lock, "o cache OCR"):
        _preparar_raiz(dir_cache, criar=False)
        if not dir_cache.exists() or not (dir_cache / NOME_MANIFESTO_OCR).exists():
            return ()
        manifesto, _ = _carregar_manifesto(dir_cache)
        artefatos = _validar_manifesto(dir_cache, manifesto)
        documentos = manifesto["documentos"]
        assert type(documentos) is dict
        entrada = documentos.get(documento)
        if entrada is None:
            return ()
        if (
            entrada["sha256_pdf"] != sha256_pdf
            or entrada["contrato_requisicao"] != contrato
            or not _modelo_observado_compativel(
                str(contrato["modelo"]), str(entrada["modelo_retornado"])
            )
        ):
            raise ValueError("PDF/contrato/modelo diverge do overlay OCR congelado.")
        paginas: list[PaginaOCRCongelada] = []
        for chave in sorted(entrada["paginas"], key=int):
            registro = entrada["paginas"][chave]
            digest = registro["hash_artefato"]
            artefato = artefatos[(documento, digest)]
            pagina = next(
                item for item in artefato["paginas"] if item["indice"] == int(chave)
            )
            paginas.append(
                PaginaOCRCongelada(
                    indice=int(chave),
                    texto=str(pagina["texto"]),
                    modelo=str(artefato["modelo_retornado"]),
                    hash_artefato=digest,
                    average_page_confidence_score=float(
                        pagina["average_page_confidence_score"]
                    ),
                    minimum_page_confidence_score=float(
                        pagina["minimum_page_confidence_score"]
                    ),
                )
            )
        return tuple(paginas)


def hash_manifesto_ocr(dir_cache: Path) -> str:
    """Retorna o SHA-256 canônico do manifesto após validar todos os artefatos."""

    dir_cache = _normalizar_dir_cache(Path(dir_cache))
    lock = _caminho_lock(dir_cache)
    _rejeitar_symlink(lock, "Lock do cache OCR")
    with bloqueio_compartilhado(lock, "o cache OCR"):
        _preparar_raiz(dir_cache, criar=False)
        if not dir_cache.exists() or not (dir_cache / NOME_MANIFESTO_OCR).exists():
            return _sha256(_bytes_canonicos(_manifesto_vazio()))
        manifesto, dados = _carregar_manifesto(dir_cache)
        _validar_manifesto(dir_cache, manifesto)
        assert dados is not None
        return _sha256(dados)


__all__ = [
    "PaginaOCRCongelada",
    "carregar_overlay_documento",
    "hash_manifesto_ocr",
    "persistir_resposta_ocr",
]
