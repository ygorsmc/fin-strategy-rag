"""Escolha na desambiguação e ausência de release na tela (revisão de UX, 24/10).

A pergunta "qual o lucro do BTG?" recebia a lista das duas companhias e o
pedido "responda com o CD_CVM"; a resposta "022616" chegava sem a pergunta de
antes e virava "nenhuma companhia identificada". E o lucro do Inter chegava à
tela sem dizer que não há release dele (RN12).

As contraprovas travam o que a correção não pode custar: escolher por conta
própria (RN11), reabrir conversa encerrada, tratar qualquer número como
escolha, e declarar ausência que não foi verificada.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

import app_streamlit as app
from src import agentes
from src.cobertura import Companhia, ResolucaoEntidade
from src.config import Config

PERGUNTA_BTG = "Qual foi o lucro do BTG no 3T2025?"
OPCOES_BTG = [
    {"cd_cvm": "022616", "nome": "BCO BTG PACTUAL S.A."},
    {"cd_cvm": "027774", "nome": "BTG PACTUAL COMMODITIES SERTRADING S.A."},
]
# Texto da AGTC003 na rodada real de 20/10 (`traces_2026-10-20T213509Z`).
TEXTO_DOS_AGENTES = (
    "'btg' identifica 2 companhias no painel da CVM: BCO BTG PACTUAL S.A. "
    "(CD_CVM 022616); BTG PACTUAL COMMODITIES SERTRADING S.A. (CD_CVM 027774). "
    "Qual delas? Responda com o CD_CVM — a seleção é sempre por código, nunca "
    "por nome."
)


def _historico(opcoes=OPCOES_BTG):
    return [
        {"papel": "user", "conteudo": PERGUNTA_BTG},
        {
            "papel": "assistant",
            "conteudo": TEXTO_DOS_AGENTES,
            "opcoes_desambiguacao": opcoes,
        },
    ]


class TestEscolhas:
    def test_cada_candidata_refaz_a_pergunta_com_o_codigo(self):
        assert app.escolhas_de_desambiguacao(_historico()) == {
            "BCO BTG PACTUAL S.A. (CD_CVM 022616)": f"{PERGUNTA_BTG} (CD_CVM 022616)",
            "BTG PACTUAL COMMODITIES SERTRADING S.A. (CD_CVM 027774)": (
                f"{PERGUNTA_BTG} (CD_CVM 027774)"
            ),
        }

    def test_contraprova_desambiguacao_antiga_nao_reabre(self):
        historico = _historico() + [
            {"papel": "user", "conteudo": "Qual foi o lucro do Itaú no 3T2025?"},
            {"papel": "assistant", "conteudo": "R$ 11,31 bilhões."},
        ]
        assert app.escolhas_de_desambiguacao(historico) == {}

    def test_contraprova_sem_candidatas_nao_ha_escolha(self):
        assert app.escolhas_de_desambiguacao(_historico(opcoes=[])) == {}
        assert app.escolhas_de_desambiguacao([]) == {}

    @pytest.mark.parametrize(
        "digitada,codigo",
        [
            ("022616", "022616"),
            ("22616", "022616"),
            ("CD_CVM 027774", "027774"),
            ("cd cvm: 027774.", "027774"),
        ],
    )
    def test_codigo_digitado_vira_a_escolha(self, digitada, codigo):
        assert app.completar_escolha(digitada, _historico()) == (
            f"{PERGUNTA_BTG} (CD_CVM {codigo})"
        )

    @pytest.mark.parametrize(
        "digitada",
        ["999999", "Qual foi o lucro do Itaú no 3T2025?", "o primeiro", "2025 022616"],
    )
    def test_contraprova_o_resto_e_pergunta_nova(self, digitada):
        assert app.completar_escolha(digitada, _historico()) == digitada

    def test_contraprova_codigo_sem_desambiguacao_pendente_segue_como_esta(self):
        assert app.completar_escolha("022616", []) == "022616"

    def test_turno_aplica_a_escolha_ao_texto_digitado(self):
        assert app.pergunta_do_turno(
            "022616", app.MODO_DEMONSTRACAO, None, _historico()
        ) == f"{PERGUNTA_BTG} (CD_CVM 022616)"


class TestOpcoesNoTextoDosAgentes:
    def test_texto_real_dos_agentes_da_as_duas_candidatas(self):
        assert app.opcoes_no_texto(TEXTO_DOS_AGENTES) == OPCOES_BTG

    def test_formato_e_o_da_pergunta_de_desambiguacao_do_codigo(self):
        """Contrato com o produtor: a pergunta que a cobertura escreve é lida
        de volta com as mesmas candidatas."""
        resolucao = ResolucaoEntidade(
            termo="btg",
            candidatas=(
                Companhia("022616", "BCO BTG PACTUAL S.A.", True),
                Companhia("020532", "BCO SANTANDER (BRASIL) S.A.", True),
            ),
        )
        assert app.opcoes_no_texto(resolucao.pergunta_desambiguacao()) == [
            {"cd_cvm": "022616", "nome": "BCO BTG PACTUAL S.A."},
            {"cd_cvm": "020532", "nome": "BCO SANTANDER (BRASIL) S.A."},
        ]

    def test_contraprova_uma_companhia_so_nao_e_escolha(self):
        assert app.opcoes_no_texto("O lucro de X S.A. (CD_CVM 019348) foi...") == []

    def _responder(self, monkeypatch, resposta):
        monkeypatch.setattr(app, "config", Config())
        monkeypatch.setattr(app, "carregar_rota_estruturada", lambda: None)
        monkeypatch.setattr(
            app, "_pipeline_ao_vivo", lambda identidade: (None, None, None)
        )
        monkeypatch.setattr(
            agentes, "responder_com_guardrails", lambda pergunta, config, **_: resposta
        )
        return app.responder_com_agentes(PERGUNTA_BTG, orcamento_restante_usd=1.0)

    def test_agentes_que_pedem_desambiguacao_levam_as_opcoes(self, monkeypatch):
        item = self._responder(
            monkeypatch,
            agentes.RespostaAgente(
                pergunta=PERGUNTA_BTG,
                resposta=TEXTO_DOS_AGENTES,
                precisa_desambiguacao=True,
            ),
        )
        assert item["opcoes_desambiguacao"] == OPCOES_BTG
        # Visto ao vivo em 24/10: o agente copia a frase da ferramenta.
        assert "nunca por nome" not in item["resposta"]
        assert item["resposta"].startswith("“btg” corresponde a 2 companhias")

    def test_contraprova_resposta_comum_nao_vira_escolha(self, monkeypatch):
        """Resposta que cita duas companhias com código não é pergunta."""
        item = self._responder(
            monkeypatch,
            agentes.RespostaAgente(pergunta=PERGUNTA_BTG, resposta=TEXTO_DOS_AGENTES),
        )
        assert item["opcoes_desambiguacao"] == []


def _app(monkeypatch) -> AppTest:
    monkeypatch.setenv("HABILITAR_PERGUNTAS_LIVRES", "0")
    for nome in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.setenv(nome, "")
    return AppTest.from_file("app_streamlit.py", default_timeout=120)


@pytest.fixture
def painel():
    if app.carregar_rota_estruturada() is None:
        pytest.skip("painel contábil da CVM não construído nesta instância")


def _ultima_resposta(teste) -> dict:
    return teste.session_state["historico"][-1]


@pytest.mark.usefixtures("painel")
class TestNaTela:
    def test_clicar_na_candidata_responde_a_pergunta_original(self, monkeypatch):
        teste = _app(monkeypatch).run()
        teste.chat_input[0].set_value(PERGUNTA_BTG).run()
        candidatas = [p for p in teste.pills if p.label == "Companhias candidatas"]
        assert len(candidatas) == 1
        assert candidatas[0].options == [
            "BCO BTG PACTUAL S.A. (CD_CVM 022616)",
            "BTG PACTUAL COMMODITIES SERTRADING S.A. (CD_CVM 027774)",
        ]
        candidatas[0].set_value(candidatas[0].options[0]).run()
        assert not teste.exception
        historico = teste.session_state["historico"]
        assert historico[-2]["conteudo"] == f"{PERGUNTA_BTG} (CD_CVM 022616)"
        assert "BCO BTG PACTUAL S.A." in _ultima_resposta(teste)["conteudo"]
        assert not _ultima_resposta(teste).get("opcoes_desambiguacao")

    def test_digitar_o_codigo_responde_a_pergunta_original(self, monkeypatch):
        teste = _app(monkeypatch).run()
        teste.chat_input[0].set_value(PERGUNTA_BTG).run()
        teste.chat_input[0].set_value("027774").run()
        assert not teste.exception
        assert "BTG PACTUAL COMMODITIES SERTRADING S.A." in (
            _ultima_resposta(teste)["conteudo"]
        )

    def test_contraprova_resposta_respondida_some_dos_botoes(self, monkeypatch):
        teste = _app(monkeypatch).run()
        teste.chat_input[0].set_value(PERGUNTA_BTG).run()
        teste.chat_input[0].set_value("022616").run()
        assert not [p for p in teste.pills if p.label == "Companhias candidatas"]

    def test_inter_diz_que_nao_ha_release(self, monkeypatch):
        teste = _app(monkeypatch).run()
        teste.chat_input[0].set_value("Qual foi o lucro do Banco Inter no 3T2025?").run()
        assert not teste.exception
        assert "Não há release de INTER & CO, INC. no corpus documental" in (
            _ultima_resposta(teste)["conteudo"]
        )
