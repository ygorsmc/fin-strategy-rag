"""Apresentação na tela — defeitos achados no ensaio do vídeo (2026-09-18).

`resultados/ensaio_roteiro_video_2026-09-18.md` achou três defeitos que não
mudam resposta nenhuma e ainda assim fariam o sistema parecer quebrado: erro
vermelho em toda tela do modo demonstração, fonte com marcação crua do OCR, e
valor contábil ilegível em voz alta. Cada correção é só de apresentação; as
contraprovas daqui travam o que ela NÃO pode custar — número perdido do trecho,
valor exato sumindo da tela, erro verdadeiro de cache virando aviso.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import app_streamlit as app
from tests.test_rota_estruturada import rota  # noqa: F401  (fixture)

TRECHO_OCR_ITAU = (
    "![img-0.jpeg](img-0.jpeg)\n"
    "# Resultados 2T25\n"
    "|  Em R$ milhões (exceto onde indicado) |   | 2T25 | 1T25 | 2T24  |\n"
    "| --- | --- | --- | --- | --- |\n"
    "|  2025 | Resultado Recorrente Gerencial | 11.508 | 11.128 | 10.072  |\n"
    "|   |  Produto Bancário ^{(1)} | 45.728 | 44.537 | 41.811  |\n"
    "| --- | --- | **(2,2)** | **24.476** |\n"
    "(1) Saldo da carteira no estágio sobre a carteira total.$^{1}$"
)


def _numeros(texto: str) -> list[str]:
    return re.findall(r"\d[\d.,]*", texto)


class TestLimpezaDoTrechoOCR:
    def test_remove_marcacao_que_so_polui(self):
        limpo = app._limpar_trecho_ocr(TRECHO_OCR_ITAU)
        assert "![" not in limpo and "img-0.jpeg" not in limpo
        assert "^{" not in limpo and "$^" not in limpo
        assert "---" not in limpo
        assert "|" not in limpo
        assert not any(linha.startswith("#") for linha in limpo.splitlines())

    def test_linha_de_tabela_vira_celulas_legiveis(self):
        limpo = app._limpar_trecho_ocr(TRECHO_OCR_ITAU)
        assert (
            "2025 · Resultado Recorrente Gerencial · 11.508 · 11.128 · 10.072"
            in limpo
        )

    def test_contraprova_nenhum_numero_de_dado_se_perde(self):
        """Célula de dado colada à linha separadora (defeito real do OCR do BB)
        sobrevive: descarta-se a célula `---`, nunca a linha inteira."""
        limpo = app._limpar_trecho_ocr(TRECHO_OCR_ITAU)
        sem_notas = re.sub(r"\^\{[^}]*\}", "", TRECHO_OCR_ITAU)
        sem_imagens = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", sem_notas)
        assert _numeros(limpo) == _numeros(sem_imagens)
        assert "**(2,2)** · **24.476**" in limpo


class TestValorLegivel:
    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [
            (5_239_936_000.0, "R$ 5,24 bilhões"),
            (224_707_000_000.0, "R$ 224,71 bilhões"),
            (336_345_000.0, "R$ 336,35 milhões"),
            (1_000_000_000.0, "R$ 1,00 bilhão"),
            (1_500_000_000_000.0, "R$ 1,50 trilhão"),
            (1_990_000_000.0, "R$ 1,99 bilhão"),
            (-2_100_000_000.0, "-R$ 2,10 bilhões"),
        ],
    )
    def test_escala(self, valor, esperado):
        assert app.formatar_reais_legivel(valor) == esperado

    def test_abaixo_de_um_milhao_fica_exato(self):
        from src.cobertura import formatar_reais

        assert app.formatar_reais_legivel(987_654.32) == formatar_reais(987_654.32)

    def test_trilhao_no_plural_quando_passa_de_um(self):
        assert app.formatar_reais_legivel(2_000_000_000_000.0) == "R$ 2,00 trilhões"


class TestPainelMostraOsDois:
    def test_texto_traz_o_legivel_e_o_exato(self, rota):  # noqa: F811
        item = app.responder_estruturada_se_couber(
            "Qual foi o lucro líquido do Itaú no 3T2025?"
        )
        assert "R$ 11,31 bilhões (R$ 11.306.000.000,00)" in item["resposta"]

    def test_contraprova_coluna_valor_continua_exata(self, rota):  # noqa: F811
        item = app.responder_estruturada_se_couber(
            "Qual foi o lucro líquido do Itaú no 3T2025?"
        )
        fato = item["fatos"][0]
        assert fato["valor"] == "R$ 11.306.000.000,00"
        assert fato["valor_resumido"] == "R$ 11,31 bilhões"


def _chunk(documento, inicio, fim, texto="cabeçalho\ncorpo"):
    return SimpleNamespace(
        chunk=SimpleNamespace(
            empresa="ITAU",
            documento=documento,
            pagina_inicio=inicio,
            pagina_fim=fim,
            texto=texto,
        )
    )


def _resposta(citacoes=(), recusa=False):
    return SimpleNamespace(
        recusa=recusa,
        citacoes=tuple(
            SimpleNamespace(
                empresa="ITAU", documento=d, trimestre="2T2025", pagina=p
            )
            for d, p in citacoes
        ),
    )


class TestFontesCitadasPrimeiro:
    RECUPERADOS = (
        _chunk("itau_release_2T2025", 1, 4),  # sumário: recuperado, não citado
        _chunk("itau_release_2T2025", 8, 11),
        _chunk("itau_release_2T2025", 5, 5),  # a tabela citada
        _chunk("itau_release_1T2025", 5, 5),  # mesma página, OUTRO documento
    )

    def test_citada_vem_primeiro_e_marcada(self):
        fontes = app._fontes_para_exibicao(
            self.RECUPERADOS, _resposta([("itau_release_2T2025", 5)])
        )
        assert fontes[0]["rotulo"].startswith("✅ citado na resposta")
        assert "págs. 5–5" in fontes[0]["rotulo"]
        assert [f["citada"] for f in fontes] == [True, False, False, False]

    def test_contraprova_mesma_pagina_de_outro_documento_nao_e_marcada(self):
        fontes = app._fontes_para_exibicao(
            self.RECUPERADOS, _resposta([("itau_release_2T2025", 5)])
        )
        outro = [f for f in fontes if "1T2025" in f["rotulo"]]
        assert outro and not outro[0]["citada"]

    def test_nao_citadas_mantem_a_ordem_do_ranqueamento(self):
        fontes = app._fontes_para_exibicao(
            self.RECUPERADOS, _resposta([("itau_release_2T2025", 5)])
        )
        assert [f["rotulo"].split("págs. ")[1] for f in fontes[1:]] == [
            "1–4",
            "8–11",
            "5–5",
        ]

    def test_recusa_nao_marca_nada_e_nao_reordena(self):
        fontes = app._fontes_para_exibicao(
            self.RECUPERADOS,
            _resposta([("itau_release_2T2025", 5)], recusa=True),
        )
        assert not any(f["citada"] for f in fontes)
        assert fontes[0]["rotulo"].endswith("págs. 1–4")

    def test_trecho_sai_limpo_e_redigido(self):
        texto = "cabeçalho\n![img-1.jpeg](img-1.jpeg)\nContato: pessoa@example.com"
        fontes = app._fontes_para_exibicao(
            [_chunk("d", 1, 1, texto)], _resposta()
        )
        assert "img-1" not in fontes[0]["trecho"]
        assert "pessoa@example.com" not in fontes[0]["trecho"]


class TestCifrao:
    def test_dois_cifroes_nao_viram_formula(self):
        assert app._escapar_cifrao("R$ 3,4 bi e R$ 3,1 bi") == (
            "R\\$ 3,4 bi e R\\$ 3,1 bi"
        )

    def test_historico_renderiza_com_cifrao_escapado(self):
        """Ponta a ponta na tela: a mensagem já exibida e a que transmite.

        O escape mora no ponto de exibição, não no gerador — o gerador tem
        contrato próprio de devolver o texto intacto (`TestStreaming`)."""
        teste = AppTest.from_file("app_streamlit.py", default_timeout=60)
        teste.session_state["historico"] = [
            {"papel": "assistant", "conteudo": "Lucro de R$ 1 bi e R$ 2 bi."},
            {
                "papel": "assistant",
                "conteudo": "Transmitido: R$ 3 bi e R$ 4 bi.",
                "streamar": True,
            },
        ]
        teste.run()
        assert not teste.exception
        textos = [m.value for m in teste.markdown]
        assert "Lucro de R\\$ 1 bi e R\\$ 2 bi." in textos
        assert any("R\\$ 3 bi e R\\$ 4 bi" in t for t in textos)


def _metricas(tmp_path, status):
    caminho = tmp_path / "metricas_teste.json"
    caminho.write_text(json.dumps({"_meta": {"status": status}}), encoding="utf-8")
    return caminho


ERRO_STATUS = "ValueError: " + app._ERRO_DE_STATUS


class TestAvisoDeAuditoriaPendente:
    def test_status_pendente_com_erro_de_status_e_aviso(self, tmp_path):
        caminho = _metricas(tmp_path, app.STATUS_AUDITORIA_PENDENTE)
        assert app._cache_aguarda_auditoria(ERRO_STATUS, caminho)

    def test_contraprova_outro_erro_continua_erro_mesmo_com_status_pendente(
        self, tmp_path
    ):
        caminho = _metricas(tmp_path, app.STATUS_AUDITORIA_PENDENTE)
        assert not app._cache_aguarda_auditoria(
            "ValueError: Manifesto material não corresponde ao fingerprint.",
            caminho,
        )

    def test_contraprova_erro_de_status_com_outro_status_continua_erro(
        self, tmp_path
    ):
        caminho = _metricas(tmp_path, "invalidada")
        assert not app._cache_aguarda_auditoria(ERRO_STATUS, caminho)

    def test_contraprova_metricas_ilegiveis_continuam_erro(self, tmp_path):
        caminho = tmp_path / "metricas_teste.json"
        caminho.write_text("{quebrado", encoding="utf-8")
        assert not app._cache_aguarda_auditoria(ERRO_STATUS, caminho)
        assert not app._cache_aguarda_auditoria(
            ERRO_STATUS, tmp_path / "nao_existe.json"
        )

    def test_tela_do_modo_demonstracao_nao_mostra_erro_vermelho(self):
        """Estado real do repositório: auditoria pendente. A tela mostra o
        aviso, não o erro — e só enquanto o status gravado for esse."""
        metricas = json.loads(app.ARQUIVO_METRICAS_TESTE.read_text(encoding="utf-8"))
        if metricas["_meta"].get("status") != app.STATUS_AUDITORIA_PENDENTE:
            pytest.skip("o status gravado mudou; o caso só vale com auditoria pendente")
        teste = AppTest.from_file("app_streamlit.py", default_timeout=60).run()
        assert not teste.exception
        assert not [e for e in teste.error if "Cache de demonstração" in e.value]
        assert any("aguardando auditoria humana" in w.value for w in teste.warning)
