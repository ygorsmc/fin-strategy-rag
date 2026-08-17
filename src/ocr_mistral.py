"""Cliente mínimo e auditável para o endpoint oficial do Mistral OCR.

O módulo é deliberadamente isolado da ingestão e da persistência do projeto:
recebe bytes de um PDF, envia uma ``data:`` URL em base64 e devolve somente
objetos serializáveis. O chamador decide se e onde persistir o resultado.

Não há carregamento de ``.env`` nem logging neste módulo. A chave vem por
injeção explícita ou, na ausência dela, diretamente de ``MISTRAL_API_KEY``.
"""

from __future__ import annotations

import base64
import copy
import json
import math
import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import requests


ENDPOINT_MISTRAL_OCR = "https://api.mistral.ai/v1/ocr"
MODELO_MISTRAL_OCR_PADRAO = "mistral-ocr-4-0"
VARIAVEL_CHAVE_MISTRAL = "MISTRAL_API_KEY"

MAX_RETRIES_PERMITIDOS = 5
MAX_ESPERA_RETRY_S = 5.0
MAX_PAGINAS_SOLICITADAS = 1_000
MAX_INDICE_PAGINA = 100_000
MAX_PDF_BYTES_PADRAO = 50 * 1024 * 1024
MAX_RESPOSTA_BYTES_PADRAO = 32 * 1024 * 1024

# Uma resposta 429 confirma que a solicitação foi recusada antes do OCR. Sem
# chave de idempotência documentada, timeout, desconexão e 5xx são ambíguos e
# nunca podem disparar nova cobrança automaticamente.
_STATUS_RETRY_SEGURO = frozenset({429})
_FORMATOS_TABELA = frozenset({"html", "markdown"})
_GRANULARIDADES_CONFIANCA = frozenset({"page", "word"})
_PADRAO_MODELO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class ErroMistralOCR(RuntimeError):
    """Erro base sem incluir chave, PDF ou corpo bruto da resposta."""


class ErroConfiguracaoMistralOCR(ErroMistralOCR):
    """Entrada/configuração local inválida."""


class ErroTransporteMistralOCR(ErroMistralOCR):
    """Falha de rede sem resposta HTTP auditável."""


class ErroHTTPMistralOCR(ErroMistralOCR):
    """Resposta HTTP não bem-sucedida do endpoint oficial."""

    def __init__(self, status: int):
        self.status = status
        super().__init__(f"Mistral OCR respondeu com HTTP {status}.")


class ErroRespostaMistralOCR(ErroMistralOCR):
    """JSON de resposta ausente, ambíguo ou fora do contrato esperado."""


@dataclass(frozen=True)
class RespostaHTTP:
    """Resposta pequena do transporte, fácil de substituir em testes."""

    status: int
    corpo: bytes
    headers: Mapping[str, str]


class TransporteOCR(Protocol):
    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        corpo: bytes,
        timeout_s: float,
        max_resposta_bytes: int,
    ) -> RespostaHTTP: ...


def _transporte_requests(
    url: str,
    *,
    headers: Mapping[str, str],
    corpo: bytes,
    timeout_s: float,
    max_resposta_bytes: int,
) -> RespostaHTTP:
    """POST HTTPS sem redirects e sem retry implícito da biblioteca."""
    try:
        # Não herdar HTTPS_PROXY, REQUESTS_CA_BUNDLE nem credenciais .netrc:
        # o PDF e o Bearer só podem seguir pelo TLS público do host fixado.
        with requests.Session() as sessao:
            sessao.trust_env = False
            with sessao.post(
                url,
                headers=dict(headers),
                data=corpo,
                timeout=timeout_s,
                allow_redirects=False,
                stream=True,
            ) as resposta:
                headers_resposta = {
                    str(chave).casefold(): str(valor)
                    for chave, valor in resposta.headers.items()
                }
                if not 200 <= resposta.status_code < 300:
                    # O corpo de erro pode ecoar dados do documento. Não o lemos,
                    # não o guardamos e nunca o incluímos em uma exceção.
                    return RespostaHTTP(
                        status=int(resposta.status_code),
                        corpo=b"",
                        headers=headers_resposta,
                    )

                tamanho_declarado = headers_resposta.get("content-length")
                if tamanho_declarado is not None:
                    tamanho: int | None = None
                    try:
                        tamanho = int(tamanho_declarado)
                    except ValueError:
                        pass
                    if tamanho is None:
                        raise ErroRespostaMistralOCR(
                            "Content-Length inválido na resposta do OCR."
                        )
                    if tamanho < 0 or tamanho > max_resposta_bytes:
                        raise ErroRespostaMistralOCR(
                            "Resposta do OCR excede o limite configurado."
                        )

                recebido = bytearray()
                for parte in resposta.iter_content(chunk_size=64 * 1024):
                    if not parte:
                        continue
                    recebido.extend(parte)
                    if len(recebido) > max_resposta_bytes:
                        raise ErroRespostaMistralOCR(
                            "Resposta do OCR excede o limite configurado."
                        )
                return RespostaHTTP(
                    status=int(resposta.status_code),
                    corpo=bytes(recebido),
                    headers=headers_resposta,
                )
    except requests.RequestException:
        # a mensagem original não é propagado: adaptadores/proxies podem ecoar
        # cabeçalhos ou dados da requisição em mensagens próprias.
        raise ErroTransporteMistralOCR(
            "Falha de transporte ao chamar o Mistral OCR."
        ) from None


def _copiar_json(valor):
    """Cópia defensiva depois da validação recursiva de tipos JSON."""
    return copy.deepcopy(valor)


def _validar_valor_json(valor, caminho: str, profundidade: int = 0) -> None:
    if profundidade > 64:
        raise ErroRespostaMistralOCR("Resposta OCR profunda demais.")
    if valor is None or type(valor) in {str, bool, int}:
        return
    if type(valor) is float:
        if not math.isfinite(valor):
            raise ErroRespostaMistralOCR(
                "Número não finito na resposta OCR."
            )
        return
    if type(valor) is list:
        for indice, item in enumerate(valor):
            _validar_valor_json(item, f"{caminho}[{indice}]", profundidade + 1)
        return
    if type(valor) is dict:
        for chave, item in valor.items():
            if type(chave) is not str or not chave:
                raise ErroRespostaMistralOCR(
                    "Resposta OCR contém uma chave JSON inválida."
                )
            _validar_valor_json(
                item, f"{caminho}.{chave}", profundidade + 1
            )
        return
    raise ErroRespostaMistralOCR("Resposta OCR contém um tipo não JSON.")


@dataclass(frozen=True)
class UsoOCR:
    pages_processed: int
    doc_size_bytes: int | None

    def para_dict(self) -> dict[str, int | None]:
        return {
            "pages_processed": self.pages_processed,
            "doc_size_bytes": self.doc_size_bytes,
        }


@dataclass(frozen=True)
class PaginaOCR:
    index: int
    markdown: str
    average_page_confidence_score: float
    minimum_page_confidence_score: float

    def para_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "markdown": self.markdown,
            "average_page_confidence_score": (
                self.average_page_confidence_score
            ),
            "minimum_page_confidence_score": (
                self.minimum_page_confidence_score
            ),
        }


@dataclass(frozen=True)
class TabelaOCR:
    page_index: int
    identificador: str | None
    formato: str
    conteudo: str
    dados: dict[str, object]

    def para_dict(self) -> dict[str, object]:
        return {
            "page_index": self.page_index,
            "identificador": self.identificador,
            "formato": self.formato,
            "conteudo": self.conteudo,
            "dados": _copiar_json(self.dados),
        }


@dataclass(frozen=True)
class BlocoOCR:
    page_index: int
    tipo: str
    conteudo: str | None
    dados: dict[str, object]

    def para_dict(self) -> dict[str, object]:
        return {
            "page_index": self.page_index,
            "tipo": self.tipo,
            "conteudo": self.conteudo,
            "dados": _copiar_json(self.dados),
        }


@dataclass(frozen=True)
class ResultadoOCR:
    """Resultado sem bytes do PDF nem credenciais, pronto para JSON."""

    modelo_solicitado: str
    modelo: str
    usage: UsoOCR
    pages: tuple[PaginaOCR, ...]
    tabelas: tuple[TabelaOCR, ...]
    blocos: tuple[BlocoOCR, ...]
    resposta_bruta: dict[str, object]

    @property
    def model(self) -> str:
        """Alias do nome usado pela API."""
        return self.modelo


    @property
    def modelo_observado(self) -> str:
        return self.modelo

    def para_dict(self) -> dict[str, object]:
        return {
            "modelo_solicitado": self.modelo_solicitado,
            "modelo": self.modelo,
            "usage": self.usage.para_dict(),
            "pages": [pagina.para_dict() for pagina in self.pages],
            "tabelas": [tabela.para_dict() for tabela in self.tabelas],
            "blocos": [bloco.para_dict() for bloco in self.blocos],
            "resposta_bruta": _copiar_json(self.resposta_bruta),
        }

    def to_dict(self) -> dict[str, object]:
        """Alias em inglês para consumidores externos."""
        return self.para_dict()


def _json_sem_chaves_duplicadas(pares: list[tuple[str, object]]) -> dict:
    objeto: dict[str, object] = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ErroRespostaMistralOCR(
                "Resposta OCR contém chave JSON duplicada."
            )
        objeto[chave] = valor
    return objeto


def _constante_json_invalida(_: str):
    raise ErroRespostaMistralOCR(
        "Resposta OCR contém constante numérica JSON inválida."
    )


def _inteiro_nao_negativo(objeto: Mapping[str, object], chave: str) -> int:
    valor = objeto.get(chave)
    if type(valor) is not int or valor < 0:
        raise ErroRespostaMistralOCR(
            f"Campo usage_info.{chave} deve ser inteiro não negativo."
        )
    return valor


def _inteiro_nao_negativo_ou_none(
    objeto: Mapping[str, object], chave: str
) -> int | None:
    valor = objeto.get(chave)
    if valor is None:
        return None
    if type(valor) is not int or valor < 0:
        raise ErroRespostaMistralOCR(
            f"Campo usage_info.{chave} deve ser inteiro não negativo ou null."
        )
    return valor


def _conteudo_tabela(
    tabela: Mapping[str, object], formato_solicitado: str
) -> tuple[str, str]:
    formato = tabela.get("format", formato_solicitado)
    if type(formato) is not str or formato not in _FORMATOS_TABELA:
        raise ErroRespostaMistralOCR(
            "Formato inválido em uma tabela da resposta OCR."
        )
    if formato != formato_solicitado:
        raise ErroRespostaMistralOCR(
            "Formato de tabela devolvido diverge do solicitado."
        )
    candidatos = ("content", formato_solicitado)
    presentes = [tabela.get(chave) for chave in candidatos if chave in tabela]
    if len(presentes) != 1 or type(presentes[0]) is not str:
        raise ErroRespostaMistralOCR(
            "Tabela OCR deve ter exatamente um conteúdo textual reconhecido."
        )
    return formato, presentes[0]


def _validar_tabela(
    bruto: object, page_index: int, formato_solicitado: str
) -> TabelaOCR:
    if type(bruto) is not dict:
        raise ErroRespostaMistralOCR("Cada tabela OCR deve ser um objeto JSON.")
    _validar_valor_json(bruto, "table")
    identificador = bruto.get("id")
    if identificador is not None and (
        type(identificador) is not str or not identificador.strip()
    ):
        raise ErroRespostaMistralOCR("ID de tabela OCR deve ser texto não vazio.")
    formato, conteudo = _conteudo_tabela(bruto, formato_solicitado)
    return TabelaOCR(
        page_index=page_index,
        identificador=identificador,
        formato=formato,
        conteudo=conteudo,
        dados=_copiar_json(bruto),
    )


def _validar_bloco(bruto: object, page_index: int) -> BlocoOCR:
    if type(bruto) is not dict:
        raise ErroRespostaMistralOCR("Cada bloco OCR deve ser um objeto JSON.")
    _validar_valor_json(bruto, "block")
    tipo = bruto.get("type")
    if type(tipo) is not str or not tipo.strip():
        raise ErroRespostaMistralOCR(
            "Cada bloco OCR deve ter type textual não vazio."
        )
    campos_conteudo = [
        bruto[chave]
        for chave in ("content", "text", "markdown", "html")
        if chave in bruto
    ]
    if len(campos_conteudo) > 1 or any(
        valor is not None and type(valor) is not str
        for valor in campos_conteudo
    ):
        raise ErroRespostaMistralOCR(
            "Bloco OCR possui conteúdo textual ambíguo ou inválido."
        )
    conteudo = campos_conteudo[0] if campos_conteudo else None
    return BlocoOCR(
        page_index=page_index,
        tipo=tipo,
        conteudo=conteudo,
        dados=_copiar_json(bruto),
    )


def _validar_lista(objeto: Mapping[str, object], chave: str, caminho: str) -> list:
    valor = objeto.get(chave, [])
    if valor is None:
        return []
    if type(valor) is not list:
        raise ErroRespostaMistralOCR(f"{caminho}.{chave} deve ser lista.")
    return valor


def _score_confianca(valor: object, caminho: str) -> float:
    """Normaliza um score numérico real no intervalo fechado ``[0, 1]``."""

    if (
        isinstance(valor, bool)
        or not isinstance(valor, (int, float))
        or not math.isfinite(valor)
        or not 0.0 <= float(valor) <= 1.0
    ):
        raise ErroRespostaMistralOCR(
            f"{caminho} deve ser número finito entre 0 e 1."
        )
    return float(valor)


def _desserializar_confidence_scores(
    bruto: object, caminho: str
) -> tuple[float, float]:
    """Valida scores oficiais sem duplicar a lista potencialmente grande por palavra."""

    if type(bruto) is not dict:
        raise ErroRespostaMistralOCR(f"{caminho} deve ser um objeto JSON.")
    obrigatorias = {
        "average_page_confidence_score",
        "minimum_page_confidence_score",
    }
    if not obrigatorias <= set(bruto):
        raise ErroRespostaMistralOCR(
            f"{caminho} não contém os scores de página obrigatórios."
        )
    media = _score_confianca(
        bruto["average_page_confidence_score"],
        f"{caminho}.average_page_confidence_score",
    )
    minimo = _score_confianca(
        bruto["minimum_page_confidence_score"],
        f"{caminho}.minimum_page_confidence_score",
    )
    if minimo > media:
        raise ErroRespostaMistralOCR(
            f"{caminho}.minimum_page_confidence_score não pode exceder a média."
        )
    palavras = bruto.get("word_confidence_scores")
    if palavras is not None:
        if type(palavras) is not list:
            raise ErroRespostaMistralOCR(
                f"{caminho}.word_confidence_scores deve ser lista ou null."
            )
        for indice, score in enumerate(palavras):
            _score_confianca(
                score, f"{caminho}.word_confidence_scores[{indice}]"
            )
    return media, minimo


def _desserializar_resultado(
    corpo: bytes,
    *,
    modelo_solicitado: str,
    paginas_solicitadas: tuple[int, ...] | None,
    formato_tabela: str,
    include_blocks: bool,
) -> ResultadoOCR:
    texto: str | None = None
    try:
        texto = corpo.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if texto is None:
        raise ErroRespostaMistralOCR("Resposta OCR não está em UTF-8 válido.")

    bruto: object = None
    json_invalido = False
    try:
        bruto = json.loads(
            texto,
            object_pairs_hook=_json_sem_chaves_duplicadas,
            parse_constant=_constante_json_invalida,
        )
    except ErroRespostaMistralOCR:
        raise
    except (json.JSONDecodeError, RecursionError):
        json_invalido = True
    if json_invalido:
        raise ErroRespostaMistralOCR("Resposta OCR não contém JSON válido.")
    if type(bruto) is not dict:
        raise ErroRespostaMistralOCR("Resposta OCR deve ser um objeto JSON.")
    _validar_valor_json(bruto, "response")

    modelo = bruto.get("model")
    if type(modelo) is not str or not modelo.strip():
        raise ErroRespostaMistralOCR("Resposta OCR não informa um modelo válido.")
    if not _modelos_compativeis(modelo_solicitado, modelo):
        raise ErroRespostaMistralOCR(
            "Modelo observado na resposta diverge do modelo solicitado."
        )

    usage_bruto = bruto.get("usage_info")
    if type(usage_bruto) is not dict:
        raise ErroRespostaMistralOCR(
            "Resposta OCR não contém usage_info válido."
        )
    usage = UsoOCR(
        pages_processed=_inteiro_nao_negativo(usage_bruto, "pages_processed"),
        doc_size_bytes=_inteiro_nao_negativo_ou_none(
            usage_bruto, "doc_size_bytes"
        ),
    )

    paginas_brutas = bruto.get("pages")
    if type(paginas_brutas) is not list:
        raise ErroRespostaMistralOCR("Resposta OCR não contém pages válido.")
    if len(paginas_brutas) > MAX_PAGINAS_SOLICITADAS:
        raise ErroRespostaMistralOCR("Resposta OCR contém páginas demais.")

    paginas: list[PaginaOCR] = []
    tabelas: list[TabelaOCR] = []
    blocos: list[BlocoOCR] = []
    indices: list[int] = []
    for posicao, pagina_bruta in enumerate(paginas_brutas):
        if type(pagina_bruta) is not dict:
            raise ErroRespostaMistralOCR(
                f"pages[{posicao}] deve ser um objeto JSON."
            )
        indice = pagina_bruta.get("index")
        markdown = pagina_bruta.get("markdown")
        if type(indice) is not int or indice < 0 or indice > MAX_INDICE_PAGINA:
            raise ErroRespostaMistralOCR(
                f"pages[{posicao}].index deve ser inteiro não negativo."
            )
        if type(markdown) is not str:
            raise ErroRespostaMistralOCR(
                f"pages[{posicao}].markdown deve ser texto."
            )
        media_confianca, minima_confianca = _desserializar_confidence_scores(
            pagina_bruta.get("confidence_scores"),
            f"pages[{posicao}].confidence_scores",
        )
        if indice in indices:
            raise ErroRespostaMistralOCR("Resposta OCR repete índice de página.")
        indices.append(indice)
        paginas.append(
            PaginaOCR(
                index=indice,
                markdown=markdown,
                average_page_confidence_score=media_confianca,
                minimum_page_confidence_score=minima_confianca,
            )
        )
        tabelas.extend(
            _validar_tabela(item, indice, formato_tabela)
            for item in _validar_lista(pagina_bruta, "tables", f"pages[{posicao}]")
        )
        blocos_pagina = _validar_lista(
            pagina_bruta, "blocks", f"pages[{posicao}]"
        )
        if blocos_pagina and not include_blocks:
            raise ErroRespostaMistralOCR(
                "Resposta OCR incluiu blocos que não foram solicitados."
            )
        blocos.extend(
            _validar_bloco(item, indice) for item in blocos_pagina
        )

    if indices != sorted(indices):
        raise ErroRespostaMistralOCR("Páginas OCR estão fora de ordem.")
    if paginas_solicitadas is not None and tuple(indices) != paginas_solicitadas:
        raise ErroRespostaMistralOCR(
            "Páginas devolvidas divergem das páginas solicitadas."
        )
    if usage.pages_processed != len(paginas):
        raise ErroRespostaMistralOCR(
            "usage_info.pages_processed diverge do número de páginas."
        )

    return ResultadoOCR(
        modelo_solicitado=modelo_solicitado,
        modelo=modelo,
        usage=usage,
        pages=tuple(paginas),
        tabelas=tuple(tabelas),
        blocos=tuple(blocos),
        resposta_bruta=_copiar_json(bruto),
    )


def _validar_chave(api_key: str | None) -> str:
    chave = os.environ.get(VARIAVEL_CHAVE_MISTRAL) if api_key is None else api_key
    if type(chave) is not str or not chave or chave != chave.strip():
        raise ErroConfiguracaoMistralOCR(
            f"Defina {VARIAVEL_CHAVE_MISTRAL} ou injete api_key não vazia."
        )
    if any(ord(caractere) < 32 or ord(caractere) == 127 for caractere in chave):
        raise ErroConfiguracaoMistralOCR("A chave Mistral contém controle inválido.")
    return chave


def _validar_modelo(modelo: str) -> str:
    if (
        type(modelo) is not str
        or modelo.endswith("-latest")
        or _PADRAO_MODELO.fullmatch(modelo) is None
    ):
        raise ErroConfiguracaoMistralOCR(
            "Nome de modelo Mistral inválido ou não pinado."
        )
    return modelo


def _modelos_compativeis(solicitado: str, observado: str) -> bool:
    """Aceita identidade exata ou versão canônica prefixada pelo modelo pinado."""
    return observado == solicitado or (
        observado.startswith(solicitado + "-")
        and _PADRAO_MODELO.fullmatch(observado) is not None
    )


def _validar_endpoint(endpoint: str) -> str:
    if type(endpoint) is not str or not endpoint.strip():
        raise ErroConfiguracaoMistralOCR("Endpoint Mistral OCR inválido.")
    normalizado = endpoint.strip()
    try:
        partes = urlsplit(normalizado)
        porta = partes.port
    except ValueError:
        raise ErroConfiguracaoMistralOCR(
            "Endpoint Mistral OCR inválido."
        ) from None
    if not (
        partes.scheme == "https"
        and (partes.hostname or "").lower() == "api.mistral.ai"
        and partes.path.rstrip("/") == "/v1/ocr"
        and not partes.query
        and not partes.fragment
        and not partes.username
        and not partes.password
        and porta in (None, 443)
    ):
        raise ErroConfiguracaoMistralOCR(
            "Endpoint deve ser exatamente o OCR HTTPS oficial da Mistral."
        )
    return normalizado


def _validar_paginas(pages: Sequence[int] | None) -> tuple[int, ...] | None:
    if pages is None:
        return None
    if isinstance(pages, (str, bytes, bytearray)):
        raise ErroConfiguracaoMistralOCR("pages deve ser uma sequência de inteiros.")
    try:
        paginas = tuple(pages)
    except TypeError:
        raise ErroConfiguracaoMistralOCR(
            "pages deve ser uma sequência de inteiros."
        ) from None
    if not paginas or len(paginas) > MAX_PAGINAS_SOLICITADAS:
        raise ErroConfiguracaoMistralOCR(
            "pages deve conter entre 1 e 1000 índices."
        )
    if any(
        type(pagina) is not int or pagina < 0 or pagina > MAX_INDICE_PAGINA
        for pagina in paginas
    ):
        raise ErroConfiguracaoMistralOCR(
            "Cada página deve ser um inteiro não negativo dentro do limite."
        )
    if len(set(paginas)) != len(paginas):
        raise ErroConfiguracaoMistralOCR("pages não pode repetir índices.")
    if paginas != tuple(sorted(paginas)):
        raise ErroConfiguracaoMistralOCR("pages deve estar em ordem crescente.")
    return paginas


def _numero_finito_positivo(valor: object, nome: str, maximo: float) -> float:
    if isinstance(valor, bool):
        raise ErroConfiguracaoMistralOCR(f"{nome} deve ser numérico positivo.")
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroConfiguracaoMistralOCR(
            f"{nome} deve ser numérico positivo."
        ) from None
    if not math.isfinite(numero) or numero <= 0 or numero > maximo:
        raise ErroConfiguracaoMistralOCR(
            f"{nome} deve estar entre 0 e {maximo}."
        )
    return numero


def _inteiro_positivo(valor: object, nome: str) -> int:
    if type(valor) is not int or valor <= 0:
        raise ErroConfiguracaoMistralOCR(f"{nome} deve ser inteiro positivo.")
    return valor


class ClienteMistralOCR:
    """Cliente síncrono, sem persistência e com transporte injetável."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        modelo: str = MODELO_MISTRAL_OCR_PADRAO,
        endpoint: str = ENDPOINT_MISTRAL_OCR,
        timeout_s: float = 60.0,
        max_retries: int = 0,
        backoff_inicial_s: float = 0.25,
        max_pdf_bytes: int = MAX_PDF_BYTES_PADRAO,
        max_resposta_bytes: int = MAX_RESPOSTA_BYTES_PADRAO,
        transporte: TransporteOCR | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = _validar_chave(api_key)
        self.modelo = _validar_modelo(modelo)
        self.endpoint = _validar_endpoint(endpoint)
        self.timeout_s = _numero_finito_positivo(timeout_s, "timeout_s", 300.0)
        if (
            type(max_retries) is not int
            or max_retries < 0
            or max_retries > MAX_RETRIES_PERMITIDOS
        ):
            raise ErroConfiguracaoMistralOCR(
                f"max_retries deve estar entre 0 e {MAX_RETRIES_PERMITIDOS}."
            )
        self.max_retries = max_retries
        self.backoff_inicial_s = _numero_finito_positivo(
            backoff_inicial_s, "backoff_inicial_s", MAX_ESPERA_RETRY_S
        )
        self.max_pdf_bytes = _inteiro_positivo(max_pdf_bytes, "max_pdf_bytes")
        self.max_resposta_bytes = _inteiro_positivo(
            max_resposta_bytes, "max_resposta_bytes"
        )
        if transporte is not None and not callable(transporte):
            raise ErroConfiguracaoMistralOCR("transporte deve ser chamável.")
        if not callable(dormir):
            raise ErroConfiguracaoMistralOCR("dormir deve ser chamável.")
        self._transporte = transporte or _transporte_requests
        self._dormir = dormir

    def __repr__(self) -> str:
        return (
            f"ClienteMistralOCR(modelo={self.modelo!r}, "
            f"endpoint={self.endpoint!r}, timeout_s={self.timeout_s!r}, "
            f"max_retries={self.max_retries!r})"
        )

    @staticmethod
    def _validar_pdf(pdf: bytes | bytearray | memoryview, limite: int) -> bytes:
        if not isinstance(pdf, (bytes, bytearray, memoryview)):
            raise ErroConfiguracaoMistralOCR("pdf deve ser bytes.")
        dados = bytes(pdf)
        if not dados or len(dados) > limite:
            raise ErroConfiguracaoMistralOCR(
                "PDF vazio ou acima do limite configurado."
            )
        if not dados.lstrip(b"\t\r\n ").startswith(b"%PDF-"):
            raise ErroConfiguracaoMistralOCR(
                "Conteúdo não possui assinatura de PDF."
            )
        return dados

    def _espera_retry(self, resposta: RespostaHTTP | None, tentativa: int) -> float:
        headers = (
            {str(k).casefold(): str(v) for k, v in resposta.headers.items()}
            if resposta is not None
            else {}
        )
        retry_after = headers.get("retry-after")
        if retry_after is not None:
            try:
                valor = float(retry_after)
            except ValueError:
                valor = -1.0
            if math.isfinite(valor) and valor >= 0:
                return min(valor, MAX_ESPERA_RETRY_S)
        return min(
            self.backoff_inicial_s * (2**tentativa), MAX_ESPERA_RETRY_S
        )

    @staticmethod
    def _normalizar_resposta_http(resposta: object) -> RespostaHTTP:
        if not isinstance(resposta, RespostaHTTP):
            raise ErroRespostaMistralOCR(
                "Transporte OCR devolveu um objeto fora do contrato."
            )
        if (
            type(resposta.status) is not int
            or not 100 <= resposta.status <= 599
            or type(resposta.corpo) is not bytes
            or not isinstance(resposta.headers, Mapping)
            or any(
                type(chave) is not str or type(valor) is not str
                for chave, valor in resposta.headers.items()
            )
        ):
            raise ErroRespostaMistralOCR(
                "Transporte OCR devolveu campos fora do contrato."
            )
        return resposta

    def processar_pdf(
        self,
        pdf: bytes | bytearray | memoryview,
        *,
        pages: Sequence[int] | None = None,
        table_format: str = "html",
        include_blocks: bool = False,
        confidence_scores_granularity: str = "page",
    ) -> ResultadoOCR:
        """Processa um PDF em memória e não persiste request ou resposta."""
        dados_pdf = self._validar_pdf(pdf, self.max_pdf_bytes)
        paginas = _validar_paginas(pages)
        if type(table_format) is not str or table_format not in _FORMATOS_TABELA:
            raise ErroConfiguracaoMistralOCR(
                "table_format deve ser 'html' ou 'markdown'."
            )
        if type(include_blocks) is not bool:
            raise ErroConfiguracaoMistralOCR(
                "include_blocks deve ser booleano."
            )
        if (
            type(confidence_scores_granularity) is not str
            or confidence_scores_granularity not in _GRANULARIDADES_CONFIANCA
        ):
            raise ErroConfiguracaoMistralOCR(
                "confidence_scores_granularity deve ser page ou word."
            )

        documento = "data:application/pdf;base64," + base64.b64encode(
            dados_pdf
        ).decode("ascii")
        payload: dict[str, object] = {
            "model": self.modelo,
            "document": {
                "type": "document_url",
                "document_url": documento,
            },
            "table_format": table_format,
            "include_blocks": include_blocks,
            "include_image_base64": False,
            "confidence_scores_granularity": confidence_scores_granularity,
        }
        if paginas is not None:
            payload["pages"] = list(paginas)
        corpo = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        headers = {
            "authorization": f"Bearer {self._api_key}",
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "assistente-research-financeiro/ocr",
        }

        for tentativa in range(self.max_retries + 1):
            falha_transporte = False
            try:
                resposta = self._normalizar_resposta_http(
                    self._transporte(
                        self.endpoint,
                        headers=headers,
                        corpo=corpo,
                        timeout_s=self.timeout_s,
                        max_resposta_bytes=self.max_resposta_bytes,
                    )
                )
            except ErroRespostaMistralOCR:
                raise
            except Exception:
                falha_transporte = True
            if falha_transporte:
                # O erro original pode carregar Authorization ou o corpo base64.
                # O raise fora do except elimina também __context__/__cause__.
                raise ErroTransporteMistralOCR(
                    "Falha de transporte ao chamar o Mistral OCR."
                )

            if resposta.status in _STATUS_RETRY_SEGURO:
                if tentativa < self.max_retries:
                    self._dormir(self._espera_retry(resposta, tentativa))
                    continue
                raise ErroHTTPMistralOCR(resposta.status)
            if not 200 <= resposta.status < 300:
                raise ErroHTTPMistralOCR(resposta.status)
            if len(resposta.corpo) > self.max_resposta_bytes:
                raise ErroRespostaMistralOCR(
                    "Resposta do OCR excede o limite configurado."
                )
            content_type = {
                str(k).casefold(): str(v) for k, v in resposta.headers.items()
            }.get("content-type")
            if (
                content_type is not None
                and "application/json" not in content_type.casefold()
            ):
                raise ErroRespostaMistralOCR(
                    "Resposta OCR possui Content-Type inesperado."
                )
            return _desserializar_resultado(
                resposta.corpo,
                modelo_solicitado=self.modelo,
                paginas_solicitadas=paginas,
                formato_tabela=table_format,
                include_blocks=include_blocks,
            )

        raise AssertionError("Laço de tentativas OCR terminou sem resultado.")


__all__ = [
    "BlocoOCR",
    "ClienteMistralOCR",
    "ENDPOINT_MISTRAL_OCR",
    "ErroConfiguracaoMistralOCR",
    "ErroHTTPMistralOCR",
    "ErroMistralOCR",
    "ErroRespostaMistralOCR",
    "ErroTransporteMistralOCR",
    "MODELO_MISTRAL_OCR_PADRAO",
    "PaginaOCR",
    "RespostaHTTP",
    "ResultadoOCR",
    "TabelaOCR",
    "UsoOCR",
]
