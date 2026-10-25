"""Linguagem da tela e seletor de modo (revisão de UX de 24/10, itens 6 e 11).

O vocabulário do projeto chegava a quem pergunta: códigos de regra (RN01,
RN10) no texto da resposta, nomes de coluna em snake_case, citações com o
identificador do conceito ("lucro_liquido_consolidado"), "o braço
determinístico", "a seleção é sempre por código" e "nao reproduz" sem acento.
E o seletor de modo morava na barra lateral, que no celular abre fechada.

As contraprovas travam o que a troca não pode custar: o código da regra some do
texto, mas continua na legenda técnica; a citação legível não perde companhia,
código, trimestre nem página; formato desconhecido passa intacto; e os
detalhes técnicos continuam na tela, num expansor.
"""

from __future__ import annotations

import re

import pytest
from streamlit.testing.v1 import AppTest

import app_streamlit as app
from src import agentes
from src.cobertura import Companhia, ResolucaoEntidade
from src.config import Config


class TestCitacaoLegivel:
    def test_citacao_do_painel_nomeia_o_conceito(self):
        assert app.citacao_legivel(
            "CVM · INTER & CO, INC. (CD_CVM 080217) · 3T2025 · lucro_liquido_consolidado"
        ) == (
            "Painel da CVM · INTER & CO, INC. (código CVM 080217) · 3T2025 · "
            "lucro líquido consolidado"
        )

    def test_citacao_de_release_nomeia_o_banco(self):
        assert app.citacao_legivel("release itau_release_3T2025 · ITAU · 3T2025 · p. 6") == (
            "Itaú Unibanco · release do 3T2025 · pág. 6"
        )

    @pytest.mark.parametrize(
        "citacao",
        [
            "Modelo preditivo · panorama 3T2025 · regime por porte",
            "bradesco_release_3T2025, p. 45",
            "CVM · SEM CODIGO · 3T2025 · lucro",
        ],
    )
    def test_contraprova_formato_desconhecido_passa_intacto(self, citacao):
        assert app.citacao_legivel(citacao) == citacao

    def _responder(self, monkeypatch, **campos):
        monkeypatch.setattr(app, "config", Config())
        monkeypatch.setattr(app, "carregar_rota_estruturada", lambda: None)
        monkeypatch.setattr(app, "_pipeline_ao_vivo", lambda identidade: (None, None, None))
        monkeypatch.setattr(
            agentes,
            "responder_com_guardrails",
            lambda pergunta, config, **_: agentes.RespostaAgente(pergunta=pergunta, **campos),
        )
        return app.responder_com_agentes("Pergunta?", orcamento_restante_usd=1.0)

    def test_resposta_dos_agentes_mostra_citacao_legivel_e_veredito_acentuado(
        self, monkeypatch
    ):
        item = self._responder(
            monkeypatch,
            resposta="O lucro foi de R$ 356.005.000,00.",
            citacoes=(
                "CVM · INTER & CO, INC. (CD_CVM 080217) · 3T2025 · lucro_liquido_consolidado",
            ),
            veredito_auditor="nao_reproduz",
        )
        assert "lucro_liquido_consolidado" not in item["resposta"]
        assert "(código CVM 080217) · 3T2025 · lucro líquido consolidado" in item["resposta"]
        assert "**Auditor:** não reproduziu." in item["resposta"]
        # Item 8: a escala legível entra ao lado do valor exato.
        assert "R$ 356,00 milhões (R$ 356.005.000,00)" in item["resposta"]


class TestTextosDoPainel:
    def test_desambiguacao_nomeia_as_candidatas_sem_regra_interna(self):
        resolucao = ResolucaoEntidade(
            termo="btg",
            candidatas=(
                Companhia("022616", "BCO BTG PACTUAL S.A.", True),
                Companhia("027774", "BTG PACTUAL COMMODITIES SERTRADING S.A.", False),
            ),
        )
        texto = app.texto_da_desambiguacao(
            app._opcoes(resolucao.candidatas), resolucao.termo
        )
        assert "BCO BTG PACTUAL S.A. (código CVM 022616)" in texto
        assert "BTG PACTUAL COMMODITIES SERTRADING S.A. (código CVM 027774)" in texto
        assert "nunca por nome" not in texto

    @pytest.mark.parametrize("digitada", ["código 027774", "Código CVM 027774"])
    def test_resposta_com_a_palavra_codigo_tambem_escolhe(self, digitada):
        historico = [
            {"papel": "user", "conteudo": "Lucro do BTG no 3T2025?"},
            {
                "papel": "assistant",
                "conteudo": "…",
                "opcoes_desambiguacao": [
                    {"cd_cvm": "022616", "nome": "BCO BTG PACTUAL S.A."},
                    {"cd_cvm": "027774", "nome": "BTG PACTUAL COMMODITIES SERTRADING S.A."},
                ],
            },
        ]
        assert app.completar_escolha(digitada, historico) == (
            "Lucro do BTG no 3T2025? (CD_CVM 027774)"
        )


@pytest.fixture
def rota():
    if app.carregar_rota_estruturada() is None:
        pytest.skip("painel contábil da CVM não construído nesta instância")


@pytest.mark.usefixtures("rota")
class TestRotaDoPainelSemJargao:
    def test_derivado_sem_codigo_de_regra_no_texto(self):
        item = app.responder_estruturada_se_couber(
            "Qual o lucro líquido consolidado do Banco do Brasil no 4T2025?"
        )
        assert "valor derivado" in item["resposta"]
        assert "(RN" not in item["resposta"]
        assert item["fatos"][0]["origem"] == "derivado"
        assert "nenhuma chamada externa" in item["modo"]

    def test_pergunta_sem_companhia_nao_fala_do_braco(self):
        item = app.responder_estruturada_se_couber(
            "Qual foi o lucro líquido no 3T2025?"
        )
        if item is None:
            pytest.skip("a rota encaminhou a pergunta; o texto não se aplica")
        assert "braço" not in item["resposta"]

    def test_contraprova_recusa_classificada_mantem_o_motivo(self):
        item = app.responder_estruturada_se_couber("Qual foi o lucro do Nubank no 3T2025?")
        assert "NYSE" in item["resposta"]
        assert item["resposta"] != app.TEXTO_SEM_COMPANHIA

    def test_desambiguacao_do_painel_usa_o_texto_da_tela(self):
        item = app.responder_estruturada_se_couber("Qual foi o lucro do BTG no 3T2025?")
        assert "Escolha abaixo ou responda com o código" in item["resposta"]
        assert len(item["opcoes_desambiguacao"]) == 2


def _app(monkeypatch, livre=False) -> AppTest:
    monkeypatch.setenv("HABILITAR_PERGUNTAS_LIVRES", "1" if livre else "0")
    for nome in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.setenv(nome, "")
    return AppTest.from_file("app_streamlit.py", default_timeout=120)


class TestTela:
    def test_seletor_de_modo_fica_na_area_principal(self, monkeypatch):
        teste = _app(monkeypatch, livre=True).run()
        assert not teste.exception
        assert not teste.sidebar.radio
        assert teste.radio[0].options == [
            app.MODO_DEMONSTRACAO, app.MODO_LIVRE, app.MODO_AGENTES
        ]

    def test_barra_lateral_fala_em_protecoes_e_guarda_os_ids_no_expansor(
        self, monkeypatch
    ):
        teste = _app(monkeypatch, livre=True).run()
        visiveis = " ".join(c.value for c in teste.sidebar.caption)
        assert "anonimização de dados pessoais" in visiveis
        detalhes = [e for e in teste.sidebar.expander if e.label == "Detalhes técnicos"]
        assert detalhes
        tecnicos = " ".join(c.value for c in detalhes[0].caption)
        assert "`topico_proibido`" in tecnicos
        assert "Observabilidade" in tecnicos
        info = " ".join(i.value for i in teste.sidebar.info)
        # O cifrão sai escapado: dois "US$" sem escape viravam fórmula LaTeX.
        assert re.search(
            r"Orçamento restante:\*\* US\\\$ \d+,\d{2} de US\\\$ \d+,\d{2}", info
        )

    def test_legenda_sem_provedor_nao_mostra_traco(self, monkeypatch):
        teste = _app(monkeypatch)
        teste.session_state["historico"] = [
            {"papel": "assistant", "conteudo": "Resposta.", "modo": "painel CVM", "provedor": "—"},
            {"papel": "assistant", "conteudo": "Outra.", "modo": "pergunta livre", "provedor": "gemini/x"},
        ]
        teste.run()
        legendas = [c.value for c in teste.caption]
        assert "modo: painel CVM" in legendas
        assert "modo: pergunta livre · provedor: gemini/x" in legendas

    def test_procedencia_sem_codigo_de_regra(self, monkeypatch):
        teste = _app(monkeypatch)
        teste.session_state["historico"] = [
            {"papel": "assistant", "conteudo": "R$ 1.", "citacoes": ["CVM · X"]}
        ]
        teste.run()
        assert [e.label for e in teste.expander if e.label.startswith("Procedência")] == [
            "Procedência no painel da CVM"
        ]


# Textos reais da rodada ao vivo de 24/10 (Gemini, pelo caminho da tela).
DEV008_AO_VIVO = (
    "Segundo o Santander, a queda trimestral da carteira de crédito ampliada no "
    "1T2026 se deve especialmente à sazonalidade em cartões e à variação cambial "
    "[SANTANDER | santander_release_1T2026 | 1T2026 | pág. 3]. O crescimento anual "
    "da carteira de crédito ampliada no 1T2026 foi de 3,4% "
    "[SANTANDER | santander_release_1T2026 | 1T2026 | pág. 3], sendo os destaques "
    "a financeira com avanço de 14,2% [SANTANDER | santander_release_1T2026 | "
    "1T2026 | pág. 15]."
)


class TestAchadosDaRodadaAoVivo:
    def test_marcador_de_trecho_vira_banco_e_pagina(self):
        texto = app.sem_marcadores_de_trecho(DEV008_AO_VIVO)
        assert "[SANTANDER |" not in texto
        assert "variação cambial (Santander, pág. 3)." in texto
        assert "14,2% (Santander, pág. 15)." in texto

    def test_contraprova_nenhum_numero_some(self):
        antes = re.findall(r"\d+,\d+%", DEV008_AO_VIVO)
        assert re.findall(r"\d+,\d+%", app.sem_marcadores_de_trecho(DEV008_AO_VIVO)) == antes

    def test_contraprova_texto_sem_marcador_fica_igual(self):
        texto = "A margem foi de R$ 20.051 milhões [nota do autor]."
        assert app.sem_marcadores_de_trecho(texto) == texto

    def test_recusa_de_cobertura_diz_que_a_resposta_nao_citou(self):
        from src.geracao import MOTIVO_RN02_COBERTURA
        from types import SimpleNamespace

        texto = app._texto_da_recusa(
            SimpleNamespace(recusa=True, motivo_recusa=MOTIVO_RN02_COBERTURA, resposta=None),
            [SimpleNamespace(chunk=SimpleNamespace(empresa=b, trimestre="1T2026"))
             for b in ("BTG", "ITAU", "BRADESCO", "SANTANDER", "BB")],
        )
        assert "não citou" in texto
        assert "Faltou evidência" not in texto
