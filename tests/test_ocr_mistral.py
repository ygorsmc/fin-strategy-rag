"""Testes isolados do cliente Mistral OCR (nenhuma chamada de rede real)."""

from __future__ import annotations

import base64
import json
import traceback

import pytest

from src.ocr_mistral import (
    ENDPOINT_MISTRAL_OCR,
    MODELO_MISTRAL_OCR_PADRAO,
    ClienteMistralOCR,
    ErroConfiguracaoMistralOCR,
    ErroHTTPMistralOCR,
    ErroRespostaMistralOCR,
    ErroTransporteMistralOCR,
    RespostaHTTP,
    _transporte_requests,
)


PDF_TESTE = b"%PDF-1.7\nobjeto confidencial de teste\n%%EOF"
CHAVE_TESTE = "chave-super-secreta-de-teste"


def _corpo_valido(
    *,
    modelo: str = MODELO_MISTRAL_OCR_PADRAO,
    indices: tuple[int, ...] = (0,),
    tabelas: bool = False,
    blocos: bool = False,
    table_format: str = "html",
    doc_size_bytes: int | None = len(PDF_TESTE),
) -> bytes:
    pages = []
    for indice in indices:
        pagina: dict[str, object] = {
            "index": indice,
            "markdown": f"Página {indice}",
            "dimensions": {"width": 612, "height": 792, "dpi": 72},
            "confidence_scores": {
                "average_page_confidence_score": 0.99,
                "minimum_page_confidence_score": 0.25,
                "word_confidence_scores": [0.25, 0.99],
            },
            "hyperlinks": [{"url": "https://example.invalid", "text": "fonte"}],
        }
        if tabelas:
            conteudo = (
                "<table><tr><td>1</td></tr></table>"
                if table_format == "html"
                else "| valor |\n| --- |\n| 1 |"
            )
            pagina["tables"] = [
                {
                    "id": f"tabela-{indice}",
                    "format": table_format,
                    "content": conteudo,
                    "bbox": [0, 1, 2, 3],
                }
            ]
        if blocos:
            pagina["blocks"] = [
                {
                    "type": "text",
                    "text": f"Bloco {indice}",
                    "bbox": [0, 1, 2, 3],
                }
            ]
        pages.append(pagina)
    return json.dumps(
        {
            "model": modelo,
            "usage_info": {
                "pages_processed": len(indices),
                "doc_size_bytes": doc_size_bytes,
            },
            "pages": pages,
            "metadata": {"request_id": "ocr-teste-1"},
        },
        ensure_ascii=False,
    ).encode("utf-8")


def _resposta_valida(**kwargs) -> RespostaHTTP:
    return RespostaHTTP(
        status=200,
        corpo=_corpo_valido(**kwargs),
        headers={"content-type": "application/json; charset=utf-8"},
    )


class TransporteFake:
    def __init__(self, *resultados: object):
        self.resultados = list(resultados)
        self.chamadas: list[dict[str, object]] = []

    def __call__(
        self,
        url: str,
        *,
        headers,
        corpo: bytes,
        timeout_s: float,
        max_resposta_bytes: int,
    ) -> RespostaHTTP:
        self.chamadas.append(
            {
                "url": url,
                "headers": dict(headers),
                "corpo": corpo,
                "timeout_s": timeout_s,
                "max_resposta_bytes": max_resposta_bytes,
            }
        )
        resultado = self.resultados.pop(0)
        if isinstance(resultado, BaseException):
            raise resultado
        return resultado  # type: ignore[return-value]


def test_monta_payload_e_devolve_objeto_serializavel_sem_persistir(tmp_path):
    transporte = TransporteFake(
        _resposta_valida(
            indices=(0, 2), tabelas=True, blocos=True, table_format="html"
        )
    )
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        timeout_s=12.5,
        max_retries=0,
        transporte=transporte,
    )

    resultado = cliente.processar_pdf(
        PDF_TESTE,
        pages=[0, 2],
        table_format="html",
        include_blocks=True,
        confidence_scores_granularity="word",
    )

    assert len(transporte.chamadas) == 1
    chamada = transporte.chamadas[0]
    assert chamada["url"] == ENDPOINT_MISTRAL_OCR
    assert chamada["timeout_s"] == 12.5
    assert chamada["headers"]["authorization"] == f"Bearer {CHAVE_TESTE}"

    payload = json.loads(chamada["corpo"])
    assert payload["model"] == MODELO_MISTRAL_OCR_PADRAO
    assert payload["pages"] == [0, 2]
    assert payload["table_format"] == "html"
    assert payload["include_blocks"] is True
    assert payload["include_image_base64"] is False
    assert payload["confidence_scores_granularity"] == "word"
    prefixo = "data:application/pdf;base64,"
    documento = payload["document"]["document_url"]
    assert documento.startswith(prefixo)
    assert base64.b64decode(documento.removeprefix(prefixo)) == PDF_TESTE

    serializado = resultado.to_dict()
    assert resultado.modelo == MODELO_MISTRAL_OCR_PADRAO
    assert resultado.model == MODELO_MISTRAL_OCR_PADRAO
    assert resultado.modelo_solicitado == MODELO_MISTRAL_OCR_PADRAO
    assert resultado.modelo_observado == MODELO_MISTRAL_OCR_PADRAO
    assert resultado.resposta_bruta["metadata"]["request_id"] == "ocr-teste-1"
    assert resultado.resposta_bruta["pages"][0]["dimensions"]["width"] == 612
    assert resultado.usage.pages_processed == 2
    assert [pagina.index for pagina in resultado.pages] == [0, 2]
    assert resultado.pages[0].average_page_confidence_score == 0.99
    assert resultado.pages[0].minimum_page_confidence_score == 0.25
    assert "word_confidence_scores" not in serializado["pages"][0]
    assert resultado.resposta_bruta["pages"][0]["confidence_scores"][
        "word_confidence_scores"
    ] == [0.25, 0.99]
    assert [tabela.page_index for tabela in resultado.tabelas] == [0, 2]
    assert [bloco.conteudo for bloco in resultado.blocos] == [
        "Bloco 0",
        "Bloco 2",
    ]
    assert json.loads(json.dumps(serializado, ensure_ascii=False)) == serializado
    assert list(tmp_path.iterdir()) == []
    assert CHAVE_TESTE not in repr(cliente)
    assert PDF_TESTE.decode("ascii") not in repr(cliente)


def test_pages_omitido_nao_e_enviado():
    transporte = TransporteFake(_resposta_valida())
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE, max_retries=0, transporte=transporte
    )

    cliente.processar_pdf(PDF_TESTE)

    payload = json.loads(transporte.chamadas[0]["corpo"])
    assert "pages" not in payload


def test_aceita_modelo_pinavel_e_markdown():
    modelo = "mistral-ocr-4-0-2026-07"
    transporte = TransporteFake(
        _resposta_valida(modelo=modelo, tabelas=True, table_format="markdown")
    )
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        modelo=modelo,
        max_retries=0,
        transporte=transporte,
    )

    resultado = cliente.processar_pdf(PDF_TESTE, table_format="markdown")

    assert resultado.modelo == modelo
    assert resultado.tabelas[0].formato == "markdown"
    assert transporte.chamadas[0]["headers"]["content-type"] == "application/json"


def test_endpoint_oficial_injetado_modelo_canonico_e_usage_nulo():
    modelo_observado = MODELO_MISTRAL_OCR_PADRAO + "-20260731"
    transporte = TransporteFake(
        _resposta_valida(modelo=modelo_observado, doc_size_bytes=None)
    )
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        endpoint="  https://api.mistral.ai:443/v1/ocr/  ",
        transporte=transporte,
    )

    resultado = cliente.processar_pdf(PDF_TESTE)

    assert transporte.chamadas[0]["url"] == "https://api.mistral.ai:443/v1/ocr/"
    assert resultado.modelo_solicitado == MODELO_MISTRAL_OCR_PADRAO
    assert resultado.modelo_observado == modelo_observado
    assert resultado.usage.doc_size_bytes is None
    assert resultado.to_dict()["resposta_bruta"]["usage_info"]["doc_size_bytes"] is None


def test_retry_zero_por_padrao():
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE, transporte=TransporteFake(_resposta_valida())
    )

    assert cliente.max_retries == 0



def test_chave_vem_do_ambiente_sem_carregar_dotenv(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "chave-do-ambiente")
    transporte = TransporteFake(_resposta_valida())

    cliente = ClienteMistralOCR(max_retries=0, transporte=transporte)
    cliente.processar_pdf(PDF_TESTE)

    assert transporte.chamadas[0]["headers"]["authorization"] == (
        "Bearer chave-do-ambiente"
    )


def test_chave_injetada_prevalece_sobre_ambiente(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "nao-deve-ser-usada")
    transporte = TransporteFake(_resposta_valida())

    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE, max_retries=0, transporte=transporte
    )
    cliente.processar_pdf(PDF_TESTE)

    autorizacao = transporte.chamadas[0]["headers"]["authorization"]
    assert autorizacao == f"Bearer {CHAVE_TESTE}"
    assert "nao-deve-ser-usada" not in autorizacao


@pytest.mark.parametrize("chave", [None, "", " ", " segredo", "segredo\n"])
def test_rejeita_chave_ausente_ou_insegura(monkeypatch, chave):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    with pytest.raises(ErroConfiguracaoMistralOCR):
        ClienteMistralOCR(api_key=chave)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("modelo", "modelo/com/barra"),
        ("modelo", ""),
        ("modelo", "mistral-ocr-latest"),
        ("endpoint", "http://api.mistral.ai/v1/ocr"),
        ("endpoint", "https://api.mistral.ai.evil.invalid/v1/ocr"),
        ("endpoint", "https://chave@api.mistral.ai/v1/ocr"),
        ("endpoint", "https://api.mistral.ai/v1/ocr?redirect=1"),
        ("timeout_s", 0),
        ("timeout_s", float("nan")),
        ("timeout_s", 301),
        ("max_retries", -1),
        ("max_retries", 6),
        ("max_retries", True),
        ("backoff_inicial_s", 0),
        ("max_pdf_bytes", 0),
        ("max_resposta_bytes", False),
        ("transporte", "não-chamável"),
        ("dormir", None),
    ],
)
def test_rejeita_configuracao_fora_dos_limites(campo, valor):
    argumentos = {"api_key": CHAVE_TESTE, campo: valor}

    with pytest.raises(ErroConfiguracaoMistralOCR):
        ClienteMistralOCR(**argumentos)


@pytest.mark.parametrize(
    "pdf",
    [b"", "não é PDF".encode("utf-8"), "texto", b" \nconteudo"],
)
def test_rejeita_pdf_invalido(pdf):
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        max_retries=0,
        transporte=TransporteFake(_resposta_valida()),
    )

    with pytest.raises(ErroConfiguracaoMistralOCR):
        cliente.processar_pdf(pdf)


def test_rejeita_pdf_acima_do_limite():
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        max_pdf_bytes=8,
        transporte=TransporteFake(_resposta_valida()),
    )

    with pytest.raises(ErroConfiguracaoMistralOCR):
        cliente.processar_pdf(PDF_TESTE)


@pytest.mark.parametrize(
    "pages",
    [[], [1, 0], [0, 0], [-1], [100_001], [True], ["0"], "0"],
)
def test_rejeita_selecao_de_paginas_ambigua(pages):
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        transporte=TransporteFake(_resposta_valida()),
    )

    with pytest.raises(ErroConfiguracaoMistralOCR):
        cliente.processar_pdf(PDF_TESTE, pages=pages)


@pytest.mark.parametrize(
    "opcoes",
    [
        {"table_format": "csv"},
        {"table_format": []},
        {"confidence_scores_granularity": "line"},
        {"confidence_scores_granularity": None},
        {"include_blocks": 1},
    ],
)
def test_rejeita_opcoes_de_extracao_invalidas(opcoes):
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        transporte=TransporteFake(_resposta_valida()),
    )

    with pytest.raises(ErroConfiguracaoMistralOCR):
        cliente.processar_pdf(PDF_TESTE, **opcoes)


def test_retry_restrito_respeita_retry_after_limitado():
    transporte = TransporteFake(
        RespostaHTTP(status=429, corpo=b"erro secreto", headers={"Retry-After": "99"}),
        _resposta_valida(),
    )
    esperas: list[float] = []
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        max_retries=1,
        transporte=transporte,
        dormir=esperas.append,
    )

    resultado = cliente.processar_pdf(PDF_TESTE)

    assert resultado.usage.pages_processed == 1
    assert len(transporte.chamadas) == 2
    assert esperas == [5.0]


def test_nao_repete_timeout_e_sanitiza_traceback():
    transporte = TransporteFake(
        TimeoutError(f"vazou {CHAVE_TESTE} {PDF_TESTE!r}"),
        _resposta_valida(),
    )
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        max_retries=5,
        transporte=transporte,
        dormir=lambda _: pytest.fail("timeout não deve ser repetido"),
    )

    with pytest.raises(ErroTransporteMistralOCR) as capturado:
        cliente.processar_pdf(PDF_TESTE)

    renderizado = "".join(
        traceback.format_exception(
            type(capturado.value), capturado.value, capturado.value.__traceback__
        )
    )
    assert len(transporte.chamadas) == 1
    assert CHAVE_TESTE not in renderizado
    assert "objeto confidencial" not in renderizado
    assert capturado.value.__context__ is None
    assert capturado.value.__cause__ is None



@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_nao_repete_erros_http_permanentes_nem_expoe_corpo(status):
    corpo_sensivel = CHAVE_TESTE.encode() + PDF_TESTE
    transporte = TransporteFake(
        RespostaHTTP(status=status, corpo=corpo_sensivel, headers={})
    )
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        max_retries=3,
        transporte=transporte,
        dormir=lambda _: pytest.fail("não deve esperar"),
    )

    with pytest.raises(ErroHTTPMistralOCR) as capturado:
        cliente.processar_pdf(PDF_TESTE)

    assert len(transporte.chamadas) == 1
    assert capturado.value.status == status
    assert CHAVE_TESTE not in str(capturado.value)
    assert "objeto confidencial" not in str(capturado.value)


@pytest.mark.parametrize("status", [408, 500, 502, 503, 504])
def test_nao_repete_status_http_de_processamento_ambiguo(status):
    transporte = TransporteFake(
        RespostaHTTP(status=status, corpo=b"", headers={}),
        _resposta_valida(),
    )
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        max_retries=5,
        transporte=transporte,
        dormir=lambda _: pytest.fail("status ambíguo não deve ser repetido"),
    )

    with pytest.raises(ErroHTTPMistralOCR):
        cliente.processar_pdf(PDF_TESTE)

    assert len(transporte.chamadas) == 1


@pytest.mark.parametrize(
    "resposta",
    [
        RespostaHTTP(status=200, corpo=b"nao-json", headers={}),
        RespostaHTTP(status=200, corpo=b"\xff", headers={}),
        RespostaHTTP(status=200, corpo=b"[]", headers={}),
        RespostaHTTP(status=200, corpo=b'{"model":"a","model":"b"}', headers={}),
        RespostaHTTP(status=200, corpo=b'{"valor":NaN}', headers={}),
        RespostaHTTP(status=200, corpo=b"{}", headers={}),
        RespostaHTTP(
            status=200,
            corpo=_corpo_valido(modelo="modelo-inesperado"),
            headers={},
        ),
    ],
)
def test_rejeita_resposta_json_invalida_sem_retry(resposta):
    transporte = TransporteFake(resposta)
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        max_retries=3,
        transporte=transporte,
        dormir=lambda _: pytest.fail("não deve repetir JSON inválido"),
    )

    with pytest.raises(ErroRespostaMistralOCR):
        cliente.processar_pdf(PDF_TESTE)

    assert len(transporte.chamadas) == 1


def test_rejeita_resposta_maior_que_limite_e_content_type_errado():
    corpo = _corpo_valido()
    transporte = TransporteFake(
        RespostaHTTP(status=200, corpo=corpo, headers={})
    )
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        max_resposta_bytes=len(corpo) - 1,
        transporte=transporte,
    )
    with pytest.raises(ErroRespostaMistralOCR):
        cliente.processar_pdf(PDF_TESTE)

    transporte = TransporteFake(
        RespostaHTTP(
            status=200,
            corpo=corpo,
            headers={"Content-Type": "text/html"},
        )
    )
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE, transporte=transporte
    )
    with pytest.raises(ErroRespostaMistralOCR):
        cliente.processar_pdf(PDF_TESTE)


def test_rejeita_paginas_inconsistentes_com_solicitacao_e_usage():
    transporte = TransporteFake(_resposta_valida(indices=(0, 1)))
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE, transporte=transporte
    )
    with pytest.raises(ErroRespostaMistralOCR, match="páginas solicitadas"):
        cliente.processar_pdf(PDF_TESTE, pages=[0, 2])

    bruto = json.loads(_corpo_valido())
    bruto["usage_info"]["pages_processed"] = 2
    transporte = TransporteFake(
        RespostaHTTP(status=200, corpo=json.dumps(bruto).encode(), headers={})
    )
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE, transporte=transporte
    )
    with pytest.raises(ErroRespostaMistralOCR, match="pages_processed"):
        cliente.processar_pdf(PDF_TESTE)


@pytest.mark.parametrize(
    "mutacao",
    [
        lambda pagina: pagina.pop("confidence_scores"),
        lambda pagina: pagina["confidence_scores"].pop(
            "average_page_confidence_score"
        ),
        lambda pagina: pagina["confidence_scores"].pop(
            "minimum_page_confidence_score"
        ),
        lambda pagina: pagina["confidence_scores"].__setitem__(
            "average_page_confidence_score", float("nan")
        ),
        lambda pagina: pagina["confidence_scores"].__setitem__(
            "average_page_confidence_score", -0.01
        ),
        lambda pagina: pagina["confidence_scores"].__setitem__(
            "minimum_page_confidence_score", 1.01
        ),
        lambda pagina: pagina["confidence_scores"].__setitem__(
            "minimum_page_confidence_score", True
        ),
        lambda pagina: pagina["confidence_scores"].__setitem__(
            "word_confidence_scores", [0.5, float("inf")]
        ),
        lambda pagina: pagina["confidence_scores"].__setitem__(
            "word_confidence_scores", "0.9"
        ),
    ],
)
def test_rejeita_confidence_scores_ausentes_nao_finitos_ou_fora_da_faixa(
    mutacao,
):
    bruto = json.loads(_corpo_valido())
    mutacao(bruto["pages"][0])
    corpo = json.dumps(bruto, allow_nan=True).encode("utf-8")
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        transporte=TransporteFake(RespostaHTTP(status=200, corpo=corpo, headers={})),
    )

    with pytest.raises(
        ErroRespostaMistralOCR,
        match="confidence|Número não finito|constante numérica",
    ):
        cliente.processar_pdf(PDF_TESTE)


@pytest.mark.parametrize(
    "mutacao",
    [
        lambda bruto: bruto["pages"].__setitem__(
            0, {"index": True, "markdown": "texto"}
        ),
        lambda bruto: bruto["pages"][0].__setitem__("markdown", 1),
        lambda bruto: bruto["pages"][0].__setitem__("tables", "não-lista"),
        lambda bruto: bruto["pages"][0].__setitem__(
            "tables", [{"format": "html", "content": "x", "html": "y"}]
        ),
        lambda bruto: bruto["pages"][0].__setitem__(
            "tables", [{"format": "markdown", "content": "x"}]
        ),
        lambda bruto: bruto["pages"][0].__setitem__(
            "tables", [{"format": [], "content": "x"}]
        ),
        lambda bruto: bruto["pages"][0].__setitem__(
            "blocks", [{"type": "text", "text": "x"}]
        ),
        lambda bruto: bruto["pages"][0].__setitem__(
            "blocks", [{"type": "", "text": "x"}]
        ),
        lambda bruto: bruto["pages"][0].__setitem__(
            "blocks", [{"type": "text", "text": "x", "content": "y"}]
        ),
    ],
)
def test_rejeita_estruturas_de_pagina_tabela_e_bloco_ambiguas(mutacao):
    bruto = json.loads(_corpo_valido())
    mutacao(bruto)
    transporte = TransporteFake(
        RespostaHTTP(
            status=200,
            corpo=json.dumps(bruto).encode("utf-8"),
            headers={},
        )
    )
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        max_retries=0,
        transporte=transporte,
    )

    with pytest.raises(ErroRespostaMistralOCR):
        cliente.processar_pdf(PDF_TESTE)


@pytest.mark.parametrize(
    "resposta",
    [
        object(),
        RespostaHTTP(status=True, corpo=b"{}", headers={}),
        RespostaHTTP(status=99, corpo=b"{}", headers={}),
        RespostaHTTP(status=200, corpo="{}", headers={}),
        RespostaHTTP(status=200, corpo=b"{}", headers={1: "x"}),
    ],
)
def test_rejeita_transporte_fora_do_contrato(resposta):
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        transporte=TransporteFake(resposta),
    )

    with pytest.raises(ErroRespostaMistralOCR):
        cliente.processar_pdf(PDF_TESTE)


def test_aceita_listas_nullable_previstas_pelo_schema_oficial():
    bruto = json.loads(_corpo_valido())
    bruto["pages"][0]["tables"] = None
    bruto["pages"][0]["blocks"] = None
    cliente = ClienteMistralOCR(
        api_key=CHAVE_TESTE,
        transporte=TransporteFake(
            RespostaHTTP(
                status=200,
                corpo=json.dumps(bruto).encode("utf-8"),
                headers={"content-type": "application/json"},
            )
        ),
    )

    resultado = cliente.processar_pdf(PDF_TESTE, include_blocks=True)

    assert resultado.tabelas == ()
    assert resultado.blocos == ()
    assert resultado.resposta_bruta["pages"][0]["tables"] is None


def test_transporte_nao_herda_proxy_ca_ou_netrc(monkeypatch):
    corpo = _corpo_valido()

    class RespostaFake:
        status_code = 200
        headers = {
            "content-type": "application/json",
            "content-length": str(len(corpo)),
        }

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def iter_content(self, *, chunk_size):
            assert chunk_size == 64 * 1024
            yield corpo

    class SessaoFake:
        def __init__(self):
            self.trust_env = True
            self.chamadas = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, **kwargs):
            assert self.trust_env is False
            self.chamadas.append((url, kwargs))
            return RespostaFake()

    sessao = SessaoFake()
    monkeypatch.setattr("src.ocr_mistral.requests.Session", lambda: sessao)

    resposta = _transporte_requests(
        ENDPOINT_MISTRAL_OCR,
        headers={"authorization": f"Bearer {CHAVE_TESTE}"},
        corpo=b"{}",
        timeout_s=10,
        max_resposta_bytes=len(corpo),
    )

    assert resposta.corpo == corpo
    assert len(sessao.chamadas) == 1
    assert sessao.chamadas[0][1]["allow_redirects"] is False
