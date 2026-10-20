"""Comportamento do corpo do chat (`app_streamlit.responder_no_chat`).

O corpo saiu do laço da interface em 2026-10-19, para o trace da consulta
fechar antes do `st.rerun()`. A auditoria daquela onda conferiu a equivalência
por diff e pelo AppTest nas rotas gratuitas, e os ramos pagos só por leitura.
Estes casos travam, ramo a ramo, o que cada um debita da cota de perguntas
(RN03) e do orçamento, e se a tela recarrega.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app_streamlit as app
from src import observabilidade
from src.config import Config

PERGUNTA = "Por que o NPL do Itaú aumentou no 1T2026?"


class _StFalso:
    """O que `responder_no_chat` usa do Streamlit: estado de sessão e erro."""

    def __init__(self):
        self.session_state = SimpleNamespace(
            historico=[], perguntas_livres_usadas=0, custo_usd_acumulado=0.0
        )
        self.erros: list[str] = []

    def error(self, mensagem):
        self.erros.append(mensagem)


@pytest.fixture
def st(monkeypatch):
    falso = _StFalso()
    monkeypatch.setattr(app, "st", falso)
    monkeypatch.setattr(app, "config", Config())
    for rota in ("responder_prospectiva_se_couber", "responder_estruturada_se_couber", "responder_plano_se_couber"):
        monkeypatch.setattr(app, rota, lambda pergunta, **_: None)
    return falso


def _responder(pergunta: str = PERGUNTA) -> bool:
    with observabilidade.consulta("pergunta_livre") as rastro:  # sem chave: no-op
        return app.responder_no_chat(pergunta, rastro)


def _item_painel(**extra) -> dict:
    return {"resposta": "valor do painel", "modo": "painel", "provedor": "—", **extra}


def _estado(st) -> tuple[int, float, str | None]:
    ultima = st.session_state.historico[-1] if st.session_state.historico else {}
    return st.session_state.perguntas_livres_usadas, st.session_state.custo_usd_acumulado, ultima.get("modo")


def test_entrada_vazia_mostra_erro_e_nao_recarrega(st):
    assert _responder("   ") is False
    assert st.erros and st.session_state.historico == []


def test_guardrail_recusa_sem_debito(st):
    assert _responder("Devo comprar ações do Itaú agora?") is True
    cota, custo, modo = _estado(st)
    assert (cota, custo) == (0, 0.0) and "guardrail" in modo


def test_rota_prospectiva_sem_debito(st, monkeypatch):
    monkeypatch.setattr(app, "responder_prospectiva_se_couber", lambda p: _item_painel(modo="RN07"))
    assert _responder() is True
    assert _estado(st) == (0, 0.0, "RN07")


def test_painel_sem_debito(st, monkeypatch):
    monkeypatch.setattr(app, "responder_estruturada_se_couber", lambda p: _item_painel())
    assert _responder() is True
    assert _estado(st) == (0, 0.0, "painel")


def test_plano_que_atende_debita_a_chamada(st, monkeypatch):
    monkeypatch.setattr(app, "responder_plano_se_couber", lambda p, **_: _item_painel(custo_usd=0.002))
    assert _responder() is True
    assert _estado(st) == (1, 0.002, "painel")


def test_plano_que_recusa_sem_chamar_nao_debita_cota(st, monkeypatch):
    monkeypatch.setattr(
        app, "responder_plano_se_couber",
        lambda p, **_: _item_painel(custo_usd=0.0, consumiu_chamada=False),
    )
    assert _responder() is True
    assert _estado(st) == (0, 0.0, "painel")


def test_plano_que_encaminha_debita_e_o_corpus_debita_de_novo(st, monkeypatch):
    monkeypatch.setattr(
        app, "responder_plano_se_couber", lambda p, **_: {"encaminhar": True, "custo_usd": 0.002}
    )
    monkeypatch.setattr(
        app, "responder_pergunta_livre",
        lambda p, orcamento_restante_usd: {"resposta": "r", "custo_usd": 0.003, "modelo": "m"},
    )
    assert _responder() is True
    cota, custo, _ = _estado(st)
    assert cota == 2 and custo == pytest.approx(0.005)


def test_corpus_recusa_da_rn07_nao_debita_cota(st, monkeypatch):
    monkeypatch.setattr(
        app, "responder_pergunta_livre",
        lambda p, orcamento_restante_usd: {
            "resposta": "r", "custo_usd": 0.0, "consumiu_chamada": False, "modo": "RN07 no portão",
        },
    )
    assert _responder() is True
    assert _estado(st) == (0, 0.0, "RN07 no portão")


def test_falha_depois_de_reservar_debita_cota_e_reserva(st, monkeypatch):
    def falha(p, orcamento_restante_usd):
        raise app.FalhaConsultaAoVivo(0.25)

    monkeypatch.setattr(app, "responder_pergunta_livre", falha)
    assert _responder() is True
    assert _estado(st) == (1, 0.25, "pergunta livre (falha segura)")


def test_falha_antes_da_geracao_nao_debita(st, monkeypatch):
    def falha(p, orcamento_restante_usd):
        raise RuntimeError("índice ausente")

    monkeypatch.setattr(app, "responder_pergunta_livre", falha)
    assert _responder() is True
    assert _estado(st) == (0, 0.0, "pergunta livre (falha segura)")


def test_orcamento_restante_passado_ao_corpus_desconta_o_gasto(st, monkeypatch):
    recebido = []
    st.session_state.custo_usd_acumulado = 1.5
    monkeypatch.setattr(
        app, "responder_pergunta_livre",
        lambda p, orcamento_restante_usd: recebido.append(orcamento_restante_usd)
        or {"resposta": "r", "custo_usd": 0.0, "modelo": "m"},
    )
    _responder()
    assert recebido == [pytest.approx(Config().orcamento_teto_usd - 1.5)]
