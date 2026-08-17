"""Contratos de integridade do cache OCR; nenhuma chamada de rede é feita."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.ocr_cache as ocr_cache
from src.ocr_cache import (
    PaginaOCRCongelada,
    carregar_overlay_documento,
    hash_manifesto_ocr,
    persistir_resposta_ocr,
)
from src.ocr_mistral import PaginaOCR, ResultadoOCR, UsoOCR


MODELO_SOLICITADO = "mistral-ocr-4-0"
MODELO_OBSERVADO = "mistral-ocr-4-0-2505"
ENDPOINT = "https://api.mistral.ai/v1/ocr"
SHA_PDF = hashlib.sha256(b"pdf-ficticio-nao-persistido").hexdigest()


def _json_canonico(objeto: object) -> bytes:
    return json.dumps(
        objeto,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _resposta(
    *,
    markdown: str = "Resultados trimestrais.",
    tabelas: list[dict[str, object]] | None = None,
    blocos: list[dict[str, object]] | None = None,
    indice: int = 0,
    modelo: str = MODELO_OBSERVADO,
    doc_size_bytes: int | None = None,
) -> dict[str, object]:
    pagina: dict[str, object] = {
        "index": indice,
        "markdown": markdown,
        "dimensions": {"width": 612, "height": 792, "dpi": 72},
        "confidence_scores": {
            "average_page_confidence_score": 0.991,
            "minimum_page_confidence_score": 0.21,
            "word_confidence_scores": [0.21, 0.991],
        },
        "hyperlinks": [{"url": "https://example.invalid/fonte", "text": "fonte"}],
    }
    if tabelas is not None:
        pagina["tables"] = tabelas
    if blocos is not None:
        pagina["blocks"] = blocos
    return {
        "model": modelo,
        "usage_info": {
            "pages_processed": 1,
            "doc_size_bytes": doc_size_bytes,
            "tokens_processados": 17,
        },
        "pages": [pagina],
        "metadata": {"request_id": "ocr-teste-1"},
    }


def _parametros(
    tmp_path: Path,
    **mudancas: object,
) -> dict[str, object]:
    parametros: dict[str, object] = {
        "documento": "banco_a_1T2026",
        "sha256_pdf": SHA_PDF,
        "modelo": MODELO_SOLICITADO,
        "endpoint": ENDPOINT,
        "table_format": "html",
        "include_blocks": True,
        "confidence": "page",
        "dir_cache": tmp_path / "cache_ocr",
    }
    parametros.update(mudancas)
    return parametros


def _persistir(tmp_path: Path, resposta: object | None = None, **mudancas) -> Path:
    return persistir_resposta_ocr(
        _resposta() if resposta is None else resposta,
        **_parametros(tmp_path, **mudancas),
    )


def test_persiste_snapshot_content_addressed_e_carrega_overlay_zero_based(tmp_path):
    resposta = _resposta(
        markdown="# Página 1\n\nTexto auditável.",
        blocos=[{"type": "text", "text": "Bloco", "bbox": [0, 1, 2, 3]}],
    )

    caminho = _persistir(tmp_path, SimpleNamespace(resposta_bruta=resposta))

    assert caminho.parent == tmp_path / "cache_ocr" / "respostas" / "banco_a_1T2026"
    assert len(caminho.stem) == 64
    assert caminho.suffix == ".json"
    artefato = json.loads(caminho.read_text(encoding="utf-8"))
    assert artefato["resposta_bruta"] == resposta
    assert artefato["resposta_bruta"]["metadata"]["request_id"] == "ocr-teste-1"
    assert artefato["usage"]["doc_size_bytes"] is None
    assert artefato["modelo_retornado"] == MODELO_OBSERVADO
    assert artefato["paginas"][0]["average_page_confidence_score"] == 0.991
    assert artefato["paginas"][0]["minimum_page_confidence_score"] == 0.21
    assert "word_confidence_scores" not in artefato["paginas"][0]
    assert artefato["sha256_resposta_bruta"] == hashlib.sha256(
        _json_canonico(resposta)
    ).hexdigest()

    paginas = carregar_overlay_documento(**_parametros(tmp_path))
    assert paginas == (
        PaginaOCRCongelada(
            indice=0,
            texto="Página 1\nTexto auditável.",
            modelo=MODELO_OBSERVADO,
            hash_artefato=caminho.stem,
            average_page_confidence_score=0.991,
            minimum_page_confidence_score=0.21,
        ),
    )
    assert paginas[0].index == paginas[0].page_index == paginas[0].pagina_index == 0
    manifesto = tmp_path / "cache_ocr" / "manifesto.json"
    pagina_manifesto = json.loads(manifesto.read_text(encoding="utf-8"))[
        "documentos"
    ]["banco_a_1T2026"]["paginas"]["0"]
    assert pagina_manifesto["average_page_confidence_score"] == 0.991
    assert pagina_manifesto["minimum_page_confidence_score"] == 0.21
    assert hash_manifesto_ocr(tmp_path / "cache_ocr") == hashlib.sha256(
        manifesto.read_bytes()
    ).hexdigest()


def test_mapeia_paginas_do_pdf_minimo_sem_adulterar_resposta_bruta(tmp_path):
    resposta = _resposta(markdown="Página relativa zero.")
    segunda = json.loads(json.dumps(resposta["pages"][0]))
    segunda["index"] = 1
    segunda["markdown"] = "Página relativa um."
    resposta["pages"].append(segunda)
    resposta["usage_info"]["pages_processed"] = 2

    caminho = _persistir(
        tmp_path,
        resposta,
        mapa_paginas_origem={0: 4, 1: 9},
    )

    artefato = json.loads(caminho.read_text(encoding="utf-8"))
    assert [pagina["index"] for pagina in artefato["resposta_bruta"]["pages"]] == [
        0,
        1,
    ]
    assert artefato["mapa_paginas_origem"] == {"0": 4, "1": 9}
    assert [pagina["indice"] for pagina in artefato["paginas"]] == [4, 9]
    assert [pagina.indice for pagina in carregar_overlay_documento(
        **_parametros(tmp_path)
    )] == [4, 9]


@pytest.mark.parametrize(
    "mapa",
    [
        {0: 4},
        {0: 4, 1: 4},
        {0: 4, 2: 9},
    ],
)
def test_rejeita_mapa_incompleto_duplicado_ou_com_chave_errada(tmp_path, mapa):
    resposta = _resposta()
    segunda = json.loads(json.dumps(resposta["pages"][0]))
    segunda["index"] = 1
    resposta["pages"].append(segunda)
    resposta["usage_info"]["pages_processed"] = 2

    with pytest.raises(ValueError, match="mapa_paginas_origem"):
        _persistir(tmp_path, resposta, mapa_paginas_origem=mapa)

    assert not (tmp_path / "cache_ocr").exists()


def test_tabela_html_multicoluna_gera_um_fato_por_valor_com_periodo_canonico(
    tmp_path,
):
    html = (
        "<table><thead><tr><th>Indicador</th>"
        "<th>31/mar/26 1T26</th><th>2T26</th></tr></thead>"
        "<tbody><tr><td>Margem Financeira Gerencial</td>"
        "<td>31.382</td><td>32.000</td></tr></tbody></table>"
    )
    caminho = _persistir(
        tmp_path,
        _resposta(
            markdown="Resultados\n\nEm R$ milhões",
            tabelas=[
                {
                    "id": "tabela-1",
                    "format": "html",
                    "content": html,
                    "bbox": [0, 1, 2, 3],
                    "dados_adicionais": {"origem": "provedor"},
                }
            ],
        ),
    )

    texto = carregar_overlay_documento(**_parametros(tmp_path))[0].texto
    fatos = [linha for linha in texto.splitlines() if linha.startswith("Fato tabular OCR")]
    assert fatos == [
        "Fato tabular OCR — Margem Financeira Gerencial, período 1T2026, "
        "valor R$ 31.382 milhões.",
        "Fato tabular OCR — Margem Financeira Gerencial, período 2T2026, "
        "valor R$ 32.000 milhões.",
    ]
    assert all(";" not in fato and "|" not in fato for fato in fatos)
    assert "31/mar/26" not in fatos[0]
    artefato = json.loads(caminho.read_text(encoding="utf-8"))
    assert artefato["paginas"][0]["tabelas"][0]["conteudo"] == html
    assert artefato["resposta_bruta"]["pages"][0]["tables"][0][
        "dados_adicionais"
    ] == {"origem": "provedor"}


def test_tabela_markdown_usa_escala_do_cabecalho(tmp_path):
    tabela = "| Métrica | 3T25 (R$ milhões) |\n| --- | ---: |\n| Receitas | 9.876 |"
    _persistir(
        tmp_path,
        _resposta(
            tabelas=[{"id": "md-1", "format": "markdown", "content": tabela}]
        ),
        table_format="markdown",
    )

    texto = carregar_overlay_documento(
        **_parametros(tmp_path, table_format="markdown")
    )[0].texto
    assert (
        "Fato tabular OCR — Receitas, período 3T2025, "
        "valor R$ 9.876 milhões."
    ) in texto


def test_multiplas_escalas_na_pagina_nao_sao_herdadas(tmp_path):
    html = (
        "<table><tr><th>Métrica</th><th>1T26</th></tr>"
        "<tr><td>Resultado</td><td>123</td></tr></table>"
    )
    _persistir(
        tmp_path,
        _resposta(
            markdown="Quadro A em R$ milhões; quadro B em R$ bilhões.",
            tabelas=[{"format": "html", "content": html}],
        ),
    )
    texto = carregar_overlay_documento(**_parametros(tmp_path))[0].texto
    assert (
        "Fato tabular OCR — Resultado, período 1T2026, "
        "valor 123, escala não informada."
    ) in texto


def test_colspan_ou_rowspan_preserva_tabela_mas_nao_inventa_fatos(tmp_path):
    html = (
        "<table><tr><th rowspan='2'>Métrica</th><th>1T26</th></tr>"
        "<tr><td>123</td></tr></table>"
    )
    _persistir(
        tmp_path,
        _resposta(tabelas=[{"format": "html", "content": html}]),
    )
    texto = carregar_overlay_documento(**_parametros(tmp_path))[0].texto
    assert "Métrica" in texto and "123" in texto
    assert "Fato tabular OCR" not in texto


def test_persistencia_identica_e_idempotente_sem_reescrever(tmp_path):
    resposta = _resposta()
    caminho_1 = _persistir(tmp_path, resposta)
    manifesto = tmp_path / "cache_ocr" / "manifesto.json"
    estado_1 = (
        caminho_1.stat().st_ino,
        caminho_1.stat().st_mtime_ns,
        manifesto.stat().st_ino,
        manifesto.stat().st_mtime_ns,
        manifesto.read_bytes(),
    )

    caminho_2 = _persistir(tmp_path, resposta)

    assert caminho_2 == caminho_1
    assert estado_1 == (
        caminho_2.stat().st_ino,
        caminho_2.stat().st_mtime_ns,
        manifesto.stat().st_ino,
        manifesto.stat().st_mtime_ns,
        manifesto.read_bytes(),
    )
    assert list(caminho_1.parent.glob("*.json")) == [caminho_1]


def test_recusa_recongelar_pagina_com_conteudo_diferente(tmp_path):
    caminho = _persistir(tmp_path, _resposta(markdown="Versão congelada"))
    manifesto = tmp_path / "cache_ocr" / "manifesto.json"
    bytes_manifesto = manifesto.read_bytes()

    with pytest.raises(ValueError, match="conteúdo diferente"):
        _persistir(tmp_path, _resposta(markdown="Versão alterada"))

    assert manifesto.read_bytes() == bytes_manifesto
    assert list(caminho.parent.glob("*.json")) == [caminho]


@pytest.mark.parametrize(
    "mudanca",
    [
        {"sha256_pdf": "0" * 64},
        {"modelo": "mistral-ocr-5-0"},
        {"table_format": "markdown"},
        {"include_blocks": False},
        {"confidence": "word"},
    ],
)
def test_leitura_falha_fechada_quando_contrato_ou_pdf_diverge(tmp_path, mudanca):
    _persistir(tmp_path)
    with pytest.raises(ValueError, match="diverge"):
        carregar_overlay_documento(**_parametros(tmp_path, **mudanca))


def test_modelo_observado_deve_ser_exato_ou_revisao_do_solicitado(tmp_path):
    with pytest.raises(ValueError, match="Modelo retornado"):
        _persistir(tmp_path, _resposta(modelo="outro-modelo-1"))
    assert not (tmp_path / "cache_ocr").exists()


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://api.mistral.ai.evil/v1/ocr",
        "https://evil@api.mistral.ai/v1/ocr",
        "https://api.mistral.ai/v1/ocr//",
        "https://api.mistral.ai:444/v1/ocr",
        "http://api.mistral.ai/v1/ocr",
    ],
)
def test_endpoint_deve_ser_exatamente_o_oficial(tmp_path, endpoint):
    with pytest.raises(ValueError, match="endpoint OCR"):
        _persistir(tmp_path, endpoint=endpoint)


def test_porta_https_explicita_e_canonizada_no_contrato(tmp_path):
    _persistir(tmp_path, endpoint="https://api.mistral.ai:443/v1/ocr")
    assert carregar_overlay_documento(**_parametros(tmp_path))[0].indice == 0


def test_barra_final_e_nulls_da_resposta_sao_normalizados(tmp_path):
    resposta = _resposta()
    resposta["pages"][0]["tables"] = None
    resposta["pages"][0]["blocks"] = None

    _persistir(
        tmp_path,
        resposta,
        endpoint="https://api.mistral.ai/v1/ocr/",
    )

    assert carregar_overlay_documento(**_parametros(tmp_path))[0].indice == 0


def test_adulteracao_do_artefato_e_detectada_antes_da_leitura(tmp_path):
    caminho = _persistir(tmp_path)
    dados = caminho.read_bytes().replace(b"Resultados trimestrais", b"Texto adulterado")
    caminho.write_bytes(dados)

    with pytest.raises(ValueError, match="Checksum"):
        carregar_overlay_documento(**_parametros(tmp_path))


def test_manifesto_com_chave_duplicada_falha_fechado(tmp_path):
    _persistir(tmp_path)
    manifesto = tmp_path / "cache_ocr" / "manifesto.json"
    manifesto.write_bytes(b'{"versao":1,"versao":1,"documentos":{}}')

    with pytest.raises(ValueError, match="chave duplicada"):
        hash_manifesto_ocr(tmp_path / "cache_ocr")


def test_manifesto_nao_aceita_path_traversal(tmp_path):
    _persistir(tmp_path)
    manifesto = tmp_path / "cache_ocr" / "manifesto.json"
    objeto = json.loads(manifesto.read_text(encoding="utf-8"))
    entrada = objeto["documentos"]["banco_a_1T2026"]
    registro = next(iter(entrada["respostas"].values()))
    registro["arquivo"] = "../fora.json"
    manifesto.write_bytes(_json_canonico(objeto))

    with pytest.raises(ValueError, match="caminho inesperado|traversal"):
        carregar_overlay_documento(**_parametros(tmp_path))


def test_rejeita_symlink_em_qualquer_componente_antes_do_lock(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    atalho = tmp_path / "atalho"
    try:
        atalho.symlink_to(real, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("Ambiente sem suporte a symlink.")

    with pytest.raises(ValueError, match="symlink"):
        _persistir(tmp_path, dir_cache=atalho / "cache_ocr")
    assert not (real / ".cache_ocr.lock").exists()


def test_rejeita_artefato_substituido_por_symlink(tmp_path):
    caminho = _persistir(tmp_path)
    copia = tmp_path / "copia.json"
    copia.write_bytes(caminho.read_bytes())
    caminho.unlink()
    try:
        caminho.symlink_to(copia)
    except (NotImplementedError, OSError):
        pytest.skip("Ambiente sem suporte a symlink.")

    with pytest.raises(ValueError, match="symlink"):
        carregar_overlay_documento(**_parametros(tmp_path))


def test_leitura_recusa_artefato_com_hardlink(tmp_path):
    caminho = _persistir(tmp_path)
    hardlink = tmp_path / "copia-hardlink.json"
    try:
        os.link(caminho, hardlink)
    except (NotImplementedError, OSError):
        pytest.skip("Ambiente sem suporte a hardlink.")

    with pytest.raises(ValueError, match="arquivo regular exclusivo"):
        carregar_overlay_documento(**_parametros(tmp_path))


def test_leitura_recusa_fifo_sem_bloquear_e_fecha_descritor(tmp_path, monkeypatch):
    if not hasattr(os, "mkfifo"):
        pytest.skip("Ambiente sem suporte a FIFO.")
    fifo = tmp_path / "resposta.json"
    os.mkfifo(fifo)
    fechar_real = os.close
    descritores_fechados: list[int] = []

    def fechar_registrando(descritor: int) -> None:
        descritores_fechados.append(descritor)
        fechar_real(descritor)

    monkeypatch.setattr(ocr_cache.os, "close", fechar_registrando)

    with pytest.raises(ValueError, match="arquivo regular exclusivo"):
        ocr_cache._ler_arquivo_regular(fifo, "Resposta OCR")

    assert len(descritores_fechados) == 1


def test_troca_para_symlink_no_instante_do_open_falha_fechado(
    tmp_path, monkeypatch
):
    if not hasattr(os, "O_NOFOLLOW"):
        pytest.skip("Plataforma sem O_NOFOLLOW.")
    caminho = tmp_path / "manifesto.json"
    alvo = tmp_path / "conteudo-controlado.json"
    caminho.write_bytes(b'{"documentos":{}}')
    segredo = b"conteudo-que-nao-pode-vazar"
    alvo.write_bytes(segredo)
    abrir_real = os.open
    troca_realizada = False

    def abrir_apos_troca(path, flags, *args, **kwargs):
        nonlocal troca_realizada
        if os.fspath(path) == os.fspath(caminho) and not troca_realizada:
            caminho.unlink()
            caminho.symlink_to(alvo)
            troca_realizada = True
        return abrir_real(path, flags, *args, **kwargs)

    monkeypatch.setattr(ocr_cache.os, "open", abrir_apos_troca)

    with pytest.raises(ValueError) as erro:
        ocr_cache._ler_arquivo_regular(caminho, "Manifesto OCR")

    assert troca_realizada is True
    assert segredo.decode("ascii") not in str(erro.value)


def test_leitura_recusa_arquivo_acima_do_limite_sem_expor_conteudo(
    tmp_path, monkeypatch
):
    caminho = tmp_path / "grande.json"
    conteudo = b"conteudo-confidencial"
    caminho.write_bytes(conteudo)
    monkeypatch.setattr(ocr_cache, "_MAX_ARQUIVO_CACHE_OCR_BYTES", 4)

    with pytest.raises(ValueError, match="limite seguro") as erro:
        ocr_cache._ler_arquivo_regular(caminho, "Resposta OCR")

    assert conteudo.decode("ascii") not in str(erro.value)


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("api_key", "segredo-inaceitavel"),
        ("document_url", "data:application/pdf;base64,JVBERi0="),
        ("image_base64", "iVBORw0KGgoAAAANSUhEUgAAAAE="),
        ("imagem", "data:image/png;base64,iVBORw0KGgo="),
    ],
)
def test_nao_persiste_credencial_pdf_nem_imagem_embutida(tmp_path, campo, valor):
    resposta = _resposta()
    resposta[campo] = valor
    with pytest.raises(ValueError, match="proibid[oa]"):
        _persistir(tmp_path, resposta)
    assert not (tmp_path / "cache_ocr").exists()


def test_image_base64_null_pode_ser_preservado_sem_bytes(tmp_path):
    resposta = _resposta()
    resposta["pages"][0]["image_base64"] = None
    caminho = _persistir(tmp_path, resposta)
    artefato = json.loads(caminho.read_text(encoding="utf-8"))
    assert artefato["resposta_bruta"]["pages"][0]["image_base64"] is None


def test_json_bruto_com_chave_duplicada_e_recusado_sem_escrita(tmp_path):
    resposta = (
        b'{"model":"mistral-ocr-4-0","model":"mistral-ocr-4-0",'
        b'"usage_info":{"pages_processed":1,"doc_size_bytes":null},'
        b'"pages":[{"index":0,"markdown":"x"}]}'
    )
    with pytest.raises(ValueError, match="chave duplicada"):
        _persistir(tmp_path, resposta)
    assert not (tmp_path / "cache_ocr").exists()


def test_serializacao_atual_do_resultado_e_conferida_contra_resposta_bruta(tmp_path):
    bruto = _resposta()
    serializado = {
        "modelo_solicitado": MODELO_SOLICITADO,
        "modelo": MODELO_OBSERVADO,
        "usage": {"pages_processed": 1, "doc_size_bytes": None},
        "pages": [
            {
                "index": 0,
                "markdown": "Resultados trimestrais.",
                "average_page_confidence_score": 0.991,
                "minimum_page_confidence_score": 0.21,
            }
        ],
        "tabelas": [],
        "blocos": [],
        "resposta_bruta": bruto,
    }

    caminho = _persistir(tmp_path, serializado)
    assert json.loads(caminho.read_text(encoding="utf-8"))["resposta_bruta"] == bruto

    serializado["pages"][0]["markdown"] = "campo externo adulterado"
    with pytest.raises(ValueError, match="divergem da resposta bruta"):
        persistir_resposta_ocr(
            serializado,
            **_parametros(tmp_path, documento="outro_documento"),
        )


@pytest.mark.parametrize(
    "mutacao",
    [
        lambda pagina: pagina.pop("confidence_scores"),
        lambda pagina: pagina["confidence_scores"].__setitem__(
            "average_page_confidence_score", float("nan")
        ),
        lambda pagina: pagina["confidence_scores"].__setitem__(
            "average_page_confidence_score", 1.01
        ),
        lambda pagina: pagina["confidence_scores"].__setitem__(
            "minimum_page_confidence_score", -0.01
        ),
    ],
)
def test_cache_rejeita_scores_ausentes_nao_finitos_ou_fora_da_faixa(
    tmp_path, mutacao
):
    resposta = _resposta()
    mutacao(resposta["pages"][0])

    with pytest.raises(ValueError, match="confidence|Número não finito|finito"):
        _persistir(tmp_path, resposta)
    assert not (tmp_path / "cache_ocr").exists()


def test_score_derivado_adulterado_diverge_da_resposta_bruta(tmp_path):
    bruto = _resposta()
    serializado = {
        "modelo_solicitado": MODELO_SOLICITADO,
        "modelo": MODELO_OBSERVADO,
        "usage": {"pages_processed": 1, "doc_size_bytes": None},
        "pages": [
            {
                "index": 0,
                "markdown": "Resultados trimestrais.",
                "average_page_confidence_score": 0.5,
                "minimum_page_confidence_score": 0.21,
            }
        ],
        "tabelas": [],
        "blocos": [],
        "resposta_bruta": bruto,
    }

    with pytest.raises(ValueError, match="divergem da resposta bruta"):
        _persistir(tmp_path, serializado)


def test_manifesto_rejeita_score_adulterado_mesmo_com_json_canonico(tmp_path):
    _persistir(tmp_path)
    manifesto = tmp_path / "cache_ocr" / "manifesto.json"
    objeto = json.loads(manifesto.read_text(encoding="utf-8"))
    pagina = objeto["documentos"]["banco_a_1T2026"]["paginas"]["0"]
    pagina["average_page_confidence_score"] = 0.5
    manifesto.write_bytes(_json_canonico(objeto))

    with pytest.raises(ValueError, match="Confiança do manifesto diverge"):
        carregar_overlay_documento(**_parametros(tmp_path))


def test_cache_v1_sem_scores_derivados_reconstroi_da_resposta_bruta(tmp_path):
    caminho_atual = _persistir(tmp_path)
    artefato = json.loads(caminho_atual.read_text(encoding="utf-8"))
    for pagina in artefato["paginas"]:
        pagina.pop("average_page_confidence_score")
        pagina.pop("minimum_page_confidence_score")
    dados_legados = _json_canonico(artefato)
    digest_legado = hashlib.sha256(dados_legados).hexdigest()
    caminho_legado = caminho_atual.with_name(f"{digest_legado}.json")
    caminho_legado.write_bytes(dados_legados)

    manifesto = caminho_atual.parents[2] / "manifesto.json"
    objeto = json.loads(manifesto.read_text(encoding="utf-8"))
    entrada = objeto["documentos"]["banco_a_1T2026"]
    registro_resposta = next(iter(entrada["respostas"].values()))
    registro_resposta["arquivo"] = (
        f"respostas/banco_a_1T2026/{digest_legado}.json"
    )
    entrada["respostas"] = {digest_legado: registro_resposta}
    for pagina_artefato in artefato["paginas"]:
        registro_pagina = entrada["paginas"][str(pagina_artefato["indice"])]
        registro_pagina.pop("average_page_confidence_score")
        registro_pagina.pop("minimum_page_confidence_score")
        registro_pagina["arquivo"] = registro_resposta["arquivo"]
        registro_pagina["hash_artefato"] = digest_legado
        registro_pagina["hash_conteudo"] = hashlib.sha256(
            _json_canonico(pagina_artefato)
        ).hexdigest()
    manifesto.write_bytes(_json_canonico(objeto))

    pagina = carregar_overlay_documento(**_parametros(tmp_path))[0]
    assert pagina.average_page_confidence_score == 0.991
    assert pagina.minimum_page_confidence_score == 0.21


def test_integra_com_resultado_ocr_real_modelo_canonico_e_doc_size_null(tmp_path):
    bruto = _resposta()
    resultado = ResultadoOCR(
        modelo_solicitado=MODELO_SOLICITADO,
        modelo=MODELO_OBSERVADO,
        usage=UsoOCR(pages_processed=1, doc_size_bytes=None),
        pages=(
            PaginaOCR(
                index=0,
                markdown="Resultados trimestrais.",
                average_page_confidence_score=0.991,
                minimum_page_confidence_score=0.21,
            ),
        ),
        tabelas=(),
        blocos=(),
        resposta_bruta=bruto,
    )

    caminho = _persistir(tmp_path, resultado)

    artefato = json.loads(caminho.read_text(encoding="utf-8"))
    assert resultado.to_dict()["modelo_solicitado"] == MODELO_SOLICITADO
    assert artefato["modelo_retornado"] == MODELO_OBSERVADO
    assert artefato["usage"]["doc_size_bytes"] is None
    assert carregar_overlay_documento(**_parametros(tmp_path))[0].modelo == (
        MODELO_OBSERVADO
    )


def test_documento_nao_pode_ser_path(tmp_path):
    with pytest.raises(ValueError, match="identificador seguro"):
        _persistir(tmp_path, documento="../escape")
    assert not (tmp_path / "cache_ocr").exists()


def test_manifesto_e_resposta_sao_json_canonico_e_sem_temporarios(tmp_path):
    caminho = _persistir(tmp_path)
    manifesto = tmp_path / "cache_ocr" / "manifesto.json"
    assert caminho.read_bytes() == _json_canonico(
        json.loads(caminho.read_text(encoding="utf-8"))
    )
    assert manifesto.read_bytes() == _json_canonico(
        json.loads(manifesto.read_text(encoding="utf-8"))
    )
    assert not list(tmp_path.rglob("*.tmp-*"))
    assert os.access(caminho, os.R_OK)
