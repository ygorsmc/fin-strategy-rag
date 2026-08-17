"""Testes do CLI OCR explícito; nenhum deles usa rede real."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from scripts import preprocessar_ocr_mistral as cli
from src.config import Config
from src.ocr_cache import carregar_overlay_documento
from tests.fixtures.pdf_sintetico import criar_pdf


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _ambiente(
    tmp_path: Path,
    *,
    n_paginas: int = 2,
    chave: str = "",
    preco: float = 4.0,
    teto: float = 1.0,
) -> tuple[Config, Path, Path, Path, Path]:
    raw = tmp_path / "raw"
    raw.mkdir()
    pdf = criar_pdf(
        raw / "doc_dev.pdf",
        [f"Conteúdo local da página {pagina}" for pagina in range(1, n_paginas + 1)],
    )
    manifesto = tmp_path / "metadados.csv"
    with manifesto.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=(
                "empresa",
                "trimestre",
                "documento",
                "url",
                "data_coleta",
                "hash_sha256",
            ),
        )
        escritor.writeheader()
        escritor.writerow(
            {
                "empresa": "ITAU",
                "trimestre": "1T2026",
                "documento": "doc_dev",
                "url": "https://exemplo.invalid/doc.pdf",
                "data_coleta": "2026-07-15",
                "hash_sha256": _sha256(pdf),
            }
        )
    perguntas = tmp_path / "perguntas.csv"
    with perguntas.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=("conjunto", "categoria", "locais_aceitos", "pergunta"),
        )
        escritor.writeheader()
        escritor.writerows(
            [
                {
                    "conjunto": "dev",
                    "categoria": "factual",
                    "locais_aceitos": "doc_dev:1;doc_dev:1;doc_dev:2",
                    "pergunta": "não deve ser interpretada",
                },
                {
                    "conjunto": "dev",
                    "categoria": "qualitativa",
                    "locais_aceitos": "isto-não-é-um-local",
                    "pergunta": "linha não factual deve ser ignorada",
                },
                {
                    "conjunto": "teste",
                    "categoria": "factual",
                    "locais_aceitos": "doc_dev:2",
                    "pergunta": "teste congelado",
                },
            ]
        )
    config = replace(
        Config(),
        conjunto_padrao_path=perguntas,
        mistral_ocr_api_key=chave,
        mistral_ocr_preco_usd_mil_paginas=preco,
        mistral_ocr_orcamento_teto_usd=teto,
    )
    return config, manifesto, raw, tmp_path / "cache", tmp_path / "journal.jsonl"


class ClienteFake:
    def __init__(self, chamadas: list[dict], *, falha: Exception | None = None):
        self._chamadas = chamadas
        self._falha = falha

    def processar_pdf(self, pdf, **kwargs):
        self._chamadas.append({"pdf": pdf, **kwargs})
        if self._falha is not None:
            raise self._falha
        indices = tuple(kwargs["pages"])
        resposta_bruta = {
            "model": "mistral-ocr-4-0",
            "usage_info": {
                "pages_processed": len(indices),
                "doc_size_bytes": len(pdf),
            },
            "pages": [
                {
                    "index": indice,
                    "markdown": f"Texto OCR da página {indice}",
                    "confidence_scores": {
                        "average_page_confidence_score": 0.99,
                        "minimum_page_confidence_score": 0.2,
                        "word_confidence_scores": [],
                    },
                }
                for indice in indices
            ],
        }
        return SimpleNamespace(
            modelo="mistral-ocr-4-0",
            pages=tuple(SimpleNamespace(index=indice) for indice in indices),
            usage=SimpleNamespace(
                pages_processed=len(indices), doc_size_bytes=len(pdf)
            ),
            resposta_bruta=resposta_bruta,
        )


class FabricaFake:
    def __init__(self, *, falha: Exception | None = None):
        self.inicializacoes: list[dict] = []
        self.chamadas: list[dict] = []
        self.falha = falha

    def __call__(self, **kwargs):
        self.inicializacoes.append(kwargs)
        return ClienteFake(self.chamadas, falha=self.falha)


def _principal(
    argv: list[str],
    ambiente,
    *,
    fabrica=None,
) -> int:
    config, manifesto, raw, cache, journal = ambiente
    return cli.principal(
        argv,
        config=config,
        caminho_manifesto=manifesto,
        dir_raw=raw,
        dir_cache=cache,
        caminho_journal=journal,
        cliente_factory=fabrica or FabricaFake(),
    )


def test_sem_selecao_explica_e_nunca_instancia_cliente(tmp_path, monkeypatch, capsys):
    ambiente = _ambiente(tmp_path)
    fabrica = FabricaFake()
    monkeypatch.setattr(
        cli,
        "_carregar_overlay_cache",
        lambda **kwargs: pytest.fail("cache não deveria ser consultado"),
    )
    monkeypatch.setattr(
        cli,
        "carregar_metadados_corpus",
        lambda caminho: pytest.fail(
            f"manifesto não deveria ser lido sem seleção: {caminho}"
        ),
    )

    assert _principal([], ambiente, fabrica=fabrica) == 1

    assert fabrica.inicializacoes == []
    assert "Escolha exatamente um modo" in capsys.readouterr().out


def test_dry_run_valida_pdf_e_custo_mas_faz_zero_chamadas(
    tmp_path, monkeypatch, capsys
):
    ambiente = _ambiente(tmp_path)
    fabrica = FabricaFake()
    monkeypatch.setattr(cli, "_carregar_overlay_cache", lambda **kwargs: ())

    assert (
        _principal(
            ["--documento", "doc_dev", "--paginas", "1"],
            ambiente,
            fabrica=fabrica,
        )
        == 0
    )

    assert fabrica.inicializacoes == []
    assert fabrica.chamadas == []
    assert "DRY-RUN" in capsys.readouterr().out
    assert not ambiente[-1].exists()


@pytest.mark.parametrize(
    "paginas,alterar_pdf",
    [
        ((3,), False),
        ((1,), True),
    ],
)
def test_limite_de_pagina_e_sha_divergente_bloqueiam_antes_do_cache_e_cliente(
    tmp_path, monkeypatch, paginas, alterar_pdf
):
    ambiente = _ambiente(tmp_path)
    fabrica = FabricaFake()
    if alterar_pdf:
        pdf = ambiente[2] / "doc_dev.pdf"
        pdf.write_bytes(pdf.read_bytes() + b"alteracao-posterior-ao-manifesto")
    monkeypatch.setattr(
        cli,
        "_carregar_overlay_cache",
        lambda **kwargs: pytest.fail("validação deve ocorrer antes do cache"),
    )

    argv = ["--documento", "doc_dev", "--paginas", *(str(p) for p in paginas)]
    assert _principal(argv, ambiente, fabrica=fabrica) == 1

    assert fabrica.inicializacoes == []
    assert fabrica.chamadas == []


def test_factual_dev_deduplica_e_ignora_outras_categorias_e_teste(tmp_path):
    config, *_ = _ambiente(tmp_path)

    assert cli.selecionar_paginas_factuais(
        config.conjunto_padrao_path, conjunto="dev"
    ) == {"doc_dev": (1, 2)}
    assert cli.selecionar_paginas_factuais(
        config.conjunto_padrao_path, conjunto="teste"
    ) == {"doc_dev": (2,)}


def test_teste_congelado_e_todas_paginas_exigem_confirmacoes(
    tmp_path, monkeypatch
):
    ambiente = _ambiente(tmp_path)
    fabrica = FabricaFake()
    monkeypatch.setattr(
        cli,
        "_carregar_overlay_cache",
        lambda **kwargs: pytest.fail("gate deve ocorrer antes do cache"),
    )

    assert (
        _principal(
            ["--paginas-factuais", "--conjunto", "teste"],
            ambiente,
            fabrica=fabrica,
        )
        == 1
    )
    assert _principal(["--todas-paginas"], ambiente, fabrica=fabrica) == 1
    assert (
        _principal(
            ["--todas-paginas", "--confirmar-todas-paginas"],
            ambiente,
            fabrica=fabrica,
        )
        == 1
    )
    assert (
        _principal(
            ["--documento", "doc_dev", "--paginas", "2"],
            ambiente,
            fabrica=fabrica,
        )
        == 1
    )
    assert fabrica.inicializacoes == []


@pytest.mark.parametrize(
    "chave,preco,teto",
    [
        ("", 4.0, 1.0),  # sem chave
        ("chave-secreta", 1_000.0, 0.5),  # uma página custa US$ 1
    ],
)
def test_gates_de_chave_e_orcamento_ocorrem_antes_do_cliente(
    tmp_path, monkeypatch, chave, preco, teto
):
    ambiente = _ambiente(tmp_path, chave=chave, preco=preco, teto=teto)
    fabrica = FabricaFake()
    monkeypatch.setattr(cli, "_carregar_overlay_cache", lambda **kwargs: ())

    assert (
        _principal(
            [
                "--documento",
                "doc_dev",
                "--paginas",
                "1",
                "--permitir-api-paga",
            ],
            ambiente,
            fabrica=fabrica,
        )
        == 1
    )

    assert fabrica.inicializacoes == []
    assert fabrica.chamadas == []


def test_execucao_converte_pagina_um_para_zero_persiste_e_fecha_journal(
    tmp_path, monkeypatch
):
    ambiente = _ambiente(tmp_path, chave="chave-super-secreta")
    fabrica = FabricaFake()
    persistidos: list[dict] = []
    monkeypatch.setattr(cli, "_carregar_overlay_cache", lambda **kwargs: ())
    monkeypatch.setattr(
        cli,
        "_persistir_resultado_cache",
        lambda resultado, **kwargs: persistidos.append(
            {"resultado": resultado, **kwargs}
        ),
    )

    assert (
        _principal(
            [
                "--documento",
                "doc_dev",
                "--paginas",
                "1",
                "--permitir-api-paga",
            ],
            ambiente,
            fabrica=fabrica,
        )
        == 0
    )

    assert len(fabrica.inicializacoes) == 1
    assert fabrica.inicializacoes[0]["max_retries"] == 0
    assert len(fabrica.chamadas) == 1
    assert fabrica.chamadas[0]["pages"] == (0,)
    pdf_transmitido = fabrica.chamadas[0]["pdf"]
    assert pdf_transmitido != (ambiente[2] / "doc_dev.pdf").read_bytes()
    assert len(PdfReader(BytesIO(pdf_transmitido)).pages) == 1
    assert fabrica.chamadas[0]["confidence_scores_granularity"] == "page"
    assert len(persistidos) == 1
    assert persistidos[0]["documento"] == "doc_dev"
    assert persistidos[0]["mapa_paginas_origem"] == {0: 0}
    eventos = [
        json.loads(linha) for linha in ambiente[-1].read_text().splitlines()
    ]
    assert [evento["evento"] for evento in eventos] == ["inicio", "fim"]
    assert eventos[0]["paginas_zero_based"] == [0]
    assert eventos[0]["paginas_payload_zero_based"] == [0]
    assert eventos[0]["mapa_paginas_origem"] == {"0": 0}
    assert eventos[0]["sha256_payload_pdf"] == hashlib.sha256(
        pdf_transmitido
    ).hexdigest()
    assert eventos[0]["bytes_payload_pdf"] == len(pdf_transmitido)
    assert eventos[1]["resultado"] == "sucesso"
    assert eventos[1]["custo_estimado_debitado_usd"] == pytest.approx(0.004)
    serializado = ambiente[-1].read_text(encoding="utf-8")
    assert "chave-super-secreta" not in serializado
    assert "Conteúdo local" not in serializado


def test_lote_materializa_todos_os_pdfs_antes_de_cliente_e_journal(
    tmp_path, monkeypatch
):
    ambiente = _ambiente(tmp_path, chave="chave")
    config, manifesto, raw, cache, journal = ambiente
    documento = cli.carregar_metadados_corpus(manifesto)[0]
    itens = tuple(
        cli.DocumentoPlanejado(
            documento=documento,
            caminho_pdf=raw / "doc_dev.pdf",
            total_paginas=2,
            paginas_solicitadas=(pagina,),
            paginas_faltantes=(pagina,),
        )
        for pagina in (1, 2)
    )
    plano = cli.PlanoOCR(
        documentos=itens,
        n_paginas_faltantes=2,
        custo_planejado_usd=0.008,
        custo_historico_usd=0.0,
        custo_total_conservador_usd=0.008,
        teto_usd=1.0,
    )
    fabrica = FabricaFake()
    construir_original = cli._construir_pdf_minimo
    construcoes: list[tuple[int, ...]] = []

    def construir_com_falha_no_segundo(item):
        construcoes.append(item.paginas_faltantes)
        if len(construcoes) == 2:
            raise cli.ErroPreprocessamentoOCR("falha local no segundo payload")
        return construir_original(item)

    monkeypatch.setattr(cli, "_construir_pdf_minimo", construir_com_falha_no_segundo)
    monkeypatch.setattr(
        cli,
        "_anexar_evento_journal",
        lambda *args, **kwargs: pytest.fail(
            f"journal não deve ser escrito: {args!r} {kwargs!r}"
        ),
    )

    with pytest.raises(
        cli.ErroPreprocessamentoOCR, match="falha local no segundo payload"
    ):
        cli._executar_plano(
            plano,
            config,
            caminho_journal=journal,
            dir_cache=cache,
            cliente_factory=fabrica,
        )

    assert construcoes == [(1,), (2,)]
    assert fabrica.inicializacoes == []
    assert fabrica.chamadas == []
    assert not journal.exists()


def test_pdf_minimizado_acima_do_limite_falha_localmente_sem_cliente_ou_journal(
    tmp_path, monkeypatch
):
    ambiente = _ambiente(tmp_path, chave="chave")
    config, manifesto, raw, cache, journal = ambiente
    documento = cli.carregar_metadados_corpus(manifesto)[0]
    item = cli.DocumentoPlanejado(
        documento=documento,
        caminho_pdf=raw / "doc_dev.pdf",
        total_paginas=2,
        paginas_solicitadas=(1,),
        paginas_faltantes=(1,),
    )
    plano = cli.PlanoOCR(
        documentos=(item,),
        n_paginas_faltantes=1,
        custo_planejado_usd=0.004,
        custo_historico_usd=0.0,
        custo_total_conservador_usd=0.004,
        teto_usd=1.0,
    )
    fabrica = FabricaFake()
    monkeypatch.setattr(cli, "MAX_PDF_BYTES_PADRAO", 1)

    with pytest.raises(
        cli.ErroPreprocessamentoOCR, match="PDF minimizado excede o limite seguro"
    ):
        cli._executar_plano(
            plano,
            config,
            caminho_journal=journal,
            dir_cache=cache,
            cliente_factory=fabrica,
        )

    assert fabrica.inicializacoes == []
    assert fabrica.chamadas == []
    assert not journal.exists()


def test_pdf_minimo_mapeia_indice_relativo_para_pagina_original(
    tmp_path, monkeypatch
):
    ambiente = _ambiente(tmp_path, chave="chave")
    fabrica = FabricaFake()
    persistidos: list[dict] = []
    monkeypatch.setattr(cli, "_carregar_overlay_cache", lambda **kwargs: ())
    monkeypatch.setattr(
        cli,
        "_persistir_resultado_cache",
        lambda resultado, **kwargs: persistidos.append(kwargs),
    )

    assert (
        _principal(
            [
                "--documento",
                "doc_dev",
                "--paginas",
                "2",
                "--confirmar-teste-congelado",
                "--permitir-api-paga",
            ],
            ambiente,
            fabrica=fabrica,
        )
        == 0
    )

    assert fabrica.chamadas[0]["pages"] == (0,)
    leitor = PdfReader(BytesIO(fabrica.chamadas[0]["pdf"]))
    assert len(leitor.pages) == 1
    texto = leitor.pages[0].extract_text()
    assert "página 2" in texto
    assert "página 1" not in texto
    assert persistidos[0]["mapa_paginas_origem"] == {0: 1}


def test_pdf_minimo_remove_conteudo_oculto_ativo_e_preserva_visual(tmp_path):
    base = criar_pdf(tmp_path / "base.pdf", ["CONTEUDO_VISUAL_PRESERVADO"])
    fonte = tmp_path / "fonte_ativa.pdf"
    escritor = PdfWriter()
    escritor.clone_document_from_reader(PdfReader(base))

    def stream(marcador: bytes):
        objeto = DecodedStreamObject()
        objeto.set_data(marcador)
        return escritor._add_object(objeto)

    def acao(marcador: str):
        return escritor._add_object(
            DictionaryObject(
                {
                    NameObject("/S"): NameObject("/JavaScript"),
                    NameObject("/JS"): TextStringObject(marcador),
                }
            )
        )

    catalogo = escritor.root_object
    catalogo[NameObject("/Metadata")] = stream(b"SEGREDO_XMP_DOCUMENTO")
    catalogo[NameObject("/Thumb")] = stream(b"SEGREDO_THUMB_DOCUMENTO")
    catalogo[NameObject("/OpenAction")] = acao("SEGREDO_OPEN_ACTION")
    catalogo[NameObject("/AA")] = DictionaryObject(
        {NameObject("/WC"): acao("SEGREDO_AA_DOCUMENTO")}
    )
    catalogo[NameObject("/PieceInfo")] = DictionaryObject(
        {NameObject("/Privado"): TextStringObject("SEGREDO_PIECE_DOCUMENTO")}
    )
    catalogo[NameObject("/Annots")] = ArrayObject(
        [TextStringObject("SEGREDO_ANNOTS_DOCUMENTO")]
    )
    escritor.add_metadata({"/Title": "SEGREDO_INFO_DOCUMENTO"})
    escritor.add_attachment(
        "anexo-privado.txt", b"SEGREDO_ANEXO_EMBUTIDO"
    )

    pagina = escritor.pages[0]
    pagina[NameObject("/Metadata")] = stream(b"SEGREDO_XMP_PAGINA")
    pagina[NameObject("/Thumb")] = stream(b"SEGREDO_THUMB_PAGINA")
    pagina[NameObject("/AA")] = DictionaryObject(
        {NameObject("/O"): acao("SEGREDO_AA_PAGINA")}
    )
    pagina[NameObject("/PieceInfo")] = DictionaryObject(
        {NameObject("/Privado"): TextStringObject("SEGREDO_PIECE_PAGINA")}
    )
    anotacao = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Text"),
            NameObject("/Rect"): ArrayObject(
                [NumberObject(0), NumberObject(0), NumberObject(10), NumberObject(10)]
            ),
            NameObject("/Contents"): TextStringObject("SEGREDO_ANOTACAO"),
        }
    )
    pagina[NameObject("/Annots")] = ArrayObject(
        [escritor._add_object(anotacao)]
    )
    escritor.write(fonte)

    marcadores = (
        b"SEGREDO_XMP_DOCUMENTO",
        b"SEGREDO_THUMB_DOCUMENTO",
        b"SEGREDO_OPEN_ACTION",
        b"SEGREDO_AA_DOCUMENTO",
        b"SEGREDO_PIECE_DOCUMENTO",
        b"SEGREDO_ANNOTS_DOCUMENTO",
        b"SEGREDO_INFO_DOCUMENTO",
        b"SEGREDO_ANEXO_EMBUTIDO",
        b"SEGREDO_XMP_PAGINA",
        b"SEGREDO_THUMB_PAGINA",
        b"SEGREDO_AA_PAGINA",
        b"SEGREDO_PIECE_PAGINA",
        b"SEGREDO_ANOTACAO",
    )
    representacoes = tuple(
        (marcador, marcador.replace(b"_", b"\\137"))
        for marcador in marcadores
    )
    fonte_bytes = fonte.read_bytes()
    assert all(
        any(representacao in fonte_bytes for representacao in alternativas)
        for alternativas in representacoes
    )

    documento = cli.DocumentoCorpus(
        empresa="ITAU",
        trimestre="1T2026",
        documento="fonte_ativa",
        url="https://exemplo.invalid/fonte.pdf",
        data_coleta="2026-08-09",
        hash_sha256=hashlib.sha256(fonte_bytes).hexdigest(),
    )
    item = cli.DocumentoPlanejado(
        documento=documento,
        caminho_pdf=fonte,
        total_paginas=1,
        paginas_solicitadas=(1,),
        paginas_faltantes=(1,),
    )

    payload, mapa = cli._construir_pdf_minimo(item)

    assert mapa == {0: 0}
    assert all(
        representacao not in payload
        for alternativas in representacoes
        for representacao in alternativas
    )
    leitor = PdfReader(BytesIO(payload), strict=True)
    assert len(leitor.pages) == 1
    assert "CONTEUDO_VISUAL_PRESERVADO" in leitor.pages[0].extract_text()
    assert leitor.metadata is None or "/Title" not in leitor.metadata
    pagina_saida = leitor.pages[0]
    for chave in cli._CHAVES_EXCLUIDAS_PAGINA_OCR:
        assert chave not in pagina_saida
    catalogo_saida = leitor.trailer["/Root"]
    for chave in cli._CHAVES_EXCLUIDAS_CATALOGO_OCR:
        assert chave not in catalogo_saida
    nomes = catalogo_saida.get("/Names")
    assert nomes is None or "/EmbeddedFiles" not in nomes.get_object()


def test_intencao_orfa_bloqueia_antes_de_cache_e_cliente(
    tmp_path, monkeypatch, capsys
):
    ambiente = _ambiente(tmp_path, chave="chave")
    config, manifesto, raw, cache, journal = ambiente
    documento = cli.carregar_metadados_corpus(manifesto)[0]
    item = cli.DocumentoPlanejado(
        documento=documento,
        caminho_pdf=raw / "doc_dev.pdf",
        total_paginas=2,
        paginas_solicitadas=(1,),
        paginas_faltantes=(1,),
    )
    payload, mapa = cli._construir_pdf_minimo(item)
    cli._anexar_evento_journal(
        journal,
        cli._evento_inicio(
            item,
            config,
            call_id="call-orfa",
            custo_estimado_usd=0.004,
            mapa_paginas_origem=mapa,
            sha256_payload_pdf=hashlib.sha256(payload).hexdigest(),
            bytes_payload_pdf=len(payload),
        ),
    )
    fabrica = FabricaFake()
    monkeypatch.setattr(
        cli,
        "_carregar_overlay_cache",
        lambda **kwargs: pytest.fail("órfã deve bloquear antes do cache"),
    )

    assert (
        _principal(
            ["--documento", "doc_dev", "--paginas", "1"],
            ambiente,
            fabrica=fabrica,
        )
        == 1
    )

    assert fabrica.inicializacoes == []
    assert "intenção órfã" in capsys.readouterr().out


def test_journal_rejeita_chaves_json_duplicadas(tmp_path):
    journal = tmp_path / "journal.jsonl"
    journal.write_text(
        '{"evento":"inicio","evento":"fim","call_id":"duplicada"}\n',
        encoding="utf-8",
    )

    with pytest.raises(cli.ErroPreprocessamentoOCR, match="linha 1"):
        cli._carregar_estado_journal(journal)


@pytest.mark.parametrize("usar_hardlink", [False, True])
def test_journal_rejeita_links_sem_alterar_alvo(tmp_path, usar_hardlink):
    alvo = tmp_path / "alvo.txt"
    alvo.write_text("não alterar", encoding="utf-8")
    journal = tmp_path / "journal.jsonl"
    if usar_hardlink:
        os.link(alvo, journal)
    else:
        journal.symlink_to(alvo)

    with pytest.raises(cli.ErroPreprocessamentoOCR, match="Journal OCR"):
        cli._carregar_estado_journal(journal)
    with pytest.raises(cli.ErroPreprocessamentoOCR, match="Journal OCR"):
        cli._anexar_evento_journal(journal, {"evento": "fim"})

    assert alvo.read_text(encoding="utf-8") == "não alterar"


def test_timeout_nao_repete_e_debita_estimativa_no_terminal(
    tmp_path, monkeypatch
):
    ambiente = _ambiente(tmp_path, chave="chave")
    fabrica = FabricaFake(falha=TimeoutError("não imprimir payload"))
    monkeypatch.setattr(cli, "_carregar_overlay_cache", lambda **kwargs: ())

    assert (
        _principal(
            [
                "--documento",
                "doc_dev",
                "--paginas",
                "1",
                "--permitir-api-paga",
            ],
            ambiente,
            fabrica=fabrica,
        )
        == 1
    )

    assert len(fabrica.chamadas) == 1
    eventos = [
        json.loads(linha) for linha in ambiente[-1].read_text().splitlines()
    ]
    assert eventos[1]["resultado"] == "erro"
    assert eventos[1]["debito_conservador_usd"] == pytest.approx(
        eventos[0]["custo_estimado_usd"]
    )


def test_corpus_integral_2790_paginas_nao_cabe_no_teto_default():
    config = Config()
    custo = cli._custo_paginas(
        2_790, config.mistral_ocr_preco_usd_mil_paginas
    )

    assert custo == pytest.approx(11.16)
    assert custo > config.mistral_ocr_orcamento_teto_usd


def test_paginas_ja_cacheadas_sao_removidas_do_plano_sem_exigir_chave(
    tmp_path, monkeypatch
):
    ambiente = _ambiente(tmp_path, chave="")
    fabrica = FabricaFake()
    monkeypatch.setattr(
        cli,
        "_carregar_overlay_cache",
        lambda **kwargs: (SimpleNamespace(indice=0),),
    )

    assert (
        _principal(
            [
                "--documento",
                "doc_dev",
                "--paginas",
                "1",
                "--permitir-api-paga",
            ],
            ambiente,
            fabrica=fabrica,
        )
        == 0
    )
    assert fabrica.inicializacoes == []
    assert fabrica.chamadas == []


def test_sucesso_persiste_no_cache_real_e_reexecucao_faz_zero_chamadas(
    tmp_path,
):
    ambiente = _ambiente(tmp_path, chave="chave-apenas-do-teste")
    fabrica = FabricaFake()
    argv = [
        "--documento",
        "doc_dev",
        "--paginas",
        "1",
        "--permitir-api-paga",
    ]

    assert _principal(argv, ambiente, fabrica=fabrica) == 0
    assert len(fabrica.chamadas) == 1

    config, _, raw, cache, _ = ambiente
    paginas = carregar_overlay_documento(
        documento="doc_dev",
        sha256_pdf=_sha256(raw / "doc_dev.pdf"),
        modelo=config.mistral_ocr_modelo,
        endpoint=config.mistral_ocr_endpoint,
        table_format=config.mistral_ocr_table_format,
        include_blocks=config.mistral_ocr_include_blocks,
        confidence=config.mistral_ocr_confidence_granularity,
        dir_cache=cache,
    )
    assert tuple(pagina.indice for pagina in paginas) == (0,)

    def cliente_proibido(**kwargs):
        pytest.fail(f"cache íntegro não deve instanciar cliente: {sorted(kwargs)}")

    assert _principal(argv, ambiente, fabrica=cliente_proibido) == 0
