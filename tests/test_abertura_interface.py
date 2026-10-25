"""Abertura de cada modo, exemplos clicáveis e recusa que orienta (24/10).

A revisão de experiência de usuário de 24/10 achou quatro defeitos que não
mudam resposta nenhuma e ainda assim deixavam o app parecendo vazio ou hostil:
o modo padrão abria com um aviso amarelo e mais nada à vista; a tela nunca
dizia quais bancos e trimestres o corpus cobre; a ajuda descia para baixo da
conversa a cada pergunta; e a recusa da RN02 mostrava o diagnóstico do código
("Rebaixada por RN02: ...") sem dizer o que tentar.

As contraprovas daqui travam o que as correções NÃO podem custar: exemplo
clicado furar cota ou orçamento, exemplo de um modo disparar em outro, a trava
da auditoria sumir da tela, a recusa repetir o rascunho recusado, e o motivo
técnico deixar de ser rastreável.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import app_streamlit as app
from src.config import carregar_config
from src.avaliacao import carregar_conjunto_padrao
from src.geracao import (
    MOTIVO_RECUSA_SEGURO,
    MOTIVO_RN01_CITACAO_ORFA,
    MOTIVO_RN01_SEM_CITACAO,
    MOTIVO_RN02_AFIRMACAO,
    MOTIVO_RN02_COBERTURA,
    MOTIVO_RN02_NUMERO,
)
from src.recuperacao import Estrategia
from tests.test_app_hardening import _ProvedorFalso, _RecuperadorFalso

MOTIVOS_CONHECIDOS = (
    MOTIVO_RN02_COBERTURA,
    MOTIVO_RN02_NUMERO,
    MOTIVO_RN02_AFIRMACAO,
    MOTIVO_RN01_SEM_CITACAO,
    MOTIVO_RN01_CITACAO_ORFA,
    MOTIVO_RECUSA_SEGURO,
)


def _achatar(no, saida=None) -> list:
    """Elementos da área principal na ordem em que aparecem na tela."""
    saida = [] if saida is None else saida
    for indice in sorted(getattr(no, "children", {}) or {}):
        filho = no.children[indice]
        saida.append(filho)
        _achatar(filho, saida)
    return saida


def _primeiro(elementos, tipo: str, contendo: str = "") -> int:
    for posicao, elemento in enumerate(elementos):
        texto = str(getattr(elemento, "label", "") or getattr(elemento, "value", ""))
        if elemento.type == tipo and contendo in texto:
            return posicao
    raise AssertionError(f"nenhum {tipo!r} com {contendo!r} na tela")


def _app(monkeypatch, *, livre: bool = False) -> AppTest:
    """App sem chave de provedor nem de Langfuse: nada aqui pode gastar."""
    monkeypatch.setenv("HABILITAR_PERGUNTAS_LIVRES", "1" if livre else "0")
    for nome in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    ):
        monkeypatch.setenv(nome, "")
    return AppTest.from_file("app_streamlit.py", default_timeout=120)


def _ajuda(teste) -> list:
    """O expansor de ajuda do modo; a barra lateral tem os seus."""
    return [e for e in teste.expander if e.label.startswith("Como usar o modo")]


def _painel_ou_pula():
    if app.carregar_rota_estruturada() is None:
        pytest.skip("painel contábil da CVM não construído nesta instância")


def _auditoria_pendente_ou_pula():
    metricas = json.loads(app.ARQUIVO_METRICAS_TESTE.read_text(encoding="utf-8"))
    if metricas["_meta"].get("status") != app.STATUS_AUDITORIA_PENDENTE:
        pytest.skip("o status gravado mudou; o caso só vale com auditoria pendente")


class TestEscopoDoCorpus:
    def test_manifesto_real_nomeia_os_cinco_bancos_e_o_intervalo(self):
        assert app.escopo_do_corpus() == {
            "bancos": (
                "Banco do Brasil",
                "Bradesco",
                "BTG Pactual",
                "Itaú Unibanco",
                "Santander",
            ),
            "primeiro": "2T2025",
            "ultimo": "1T2026",
        }

    def test_trimestres_em_ordem_cronologica_e_nao_de_texto(self, tmp_path):
        """Em ordem de texto, 1T2026 viria antes de 2T2025 e seria o "primeiro"."""
        caminho = tmp_path / "metadados.csv"
        caminho.write_text(
            "empresa,trimestre\nITAU,1T2026\nITAU,4T2025\nBB,2T2025\n",
            encoding="utf-8",
        )
        escopo = app.escopo_do_corpus(caminho)
        assert (escopo["primeiro"], escopo["ultimo"]) == ("2T2025", "1T2026")

    def test_contraprova_codigo_sem_nome_conhecido_aparece_como_esta(self, tmp_path):
        caminho = tmp_path / "metadados.csv"
        caminho.write_text("empresa,trimestre\nNOVO,1T2026\n", encoding="utf-8")
        assert app.escopo_do_corpus(caminho)["bancos"] == ("NOVO",)

    def test_contraprova_trimestre_malformado_nao_vira_limite(self, tmp_path):
        caminho = tmp_path / "metadados.csv"
        caminho.write_text(
            "empresa,trimestre\nITAU,2T2025\nITAU,2025\nITAU,9T2030\nITAU,\n",
            encoding="utf-8",
        )
        escopo = app.escopo_do_corpus(caminho)
        assert (escopo["primeiro"], escopo["ultimo"]) == ("2T2025", "2T2025")

    def test_contraprova_manifesto_ausente_ou_vazio_nao_inventa_escopo(
        self, tmp_path
    ):
        assert app.escopo_do_corpus(tmp_path / "nao_existe.csv") is None
        vazio = tmp_path / "vazio.csv"
        vazio.write_text("empresa,trimestre\n", encoding="utf-8")
        assert app.escopo_do_corpus(vazio) is None

    def test_barra_lateral_nomeia_bancos_e_periodo(self, monkeypatch):
        teste = _app(monkeypatch).run()
        assert not teste.exception
        textos = [item.value for item in teste.sidebar.caption]
        assert any(
            "cinco bancos do corpus: Banco do Brasil, Bradesco, BTG Pactual, "
            "Itaú Unibanco e Santander, do 2T2025 ao 1T2026" in texto
            for texto in textos
        )


def _recuperado(empresa: str, trimestre: str):
    return SimpleNamespace(chunk=SimpleNamespace(empresa=empresa, trimestre=trimestre))


def _recusa(motivo: str, rascunho: str | None = None):
    return SimpleNamespace(
        recusa=True, motivo_recusa=motivo, resposta=rascunho, citacoes=()
    )


class TestRecusaQueOrienta:
    @pytest.mark.parametrize("motivo", MOTIVOS_CONHECIDOS)
    def test_motivo_conhecido_vira_texto_sem_jargao(self, motivo):
        texto = app._texto_da_recusa(_recusa(motivo), [_recuperado("ITAU", "1T2026")])
        assert "RN0" not in texto
        assert "Rebaixada" not in texto
        assert "Recusa (" not in texto
        assert "Trechos recuperados" in texto

    def test_cada_motivo_conhecido_tem_explicacao_propria(self):
        """As duas RN01 dizem a mesma coisa ao usuário; as demais, não."""
        textos = {
            motivo: app._texto_da_recusa(_recusa(motivo), [])
            for motivo in MOTIVOS_CONHECIDOS
        }
        assert textos[MOTIVO_RN01_SEM_CITACAO] == textos[MOTIVO_RN01_CITACAO_ORFA]
        assert len(set(textos.values())) == len(MOTIVOS_CONHECIDOS) - 1

    def test_cobertura_diz_de_onde_vieram_os_trechos(self):
        recuperados = [
            _recuperado("ITAU", "1T2026"),
            _recuperado("ITAU", "1T2026"),
            _recuperado("SANTANDER", "1T2026"),
        ]
        texto = app._texto_da_recusa(_recusa(MOTIVO_RN02_COBERTURA), recuperados)
        assert (
            "A busca trouxe 3 trechos, de Itaú Unibanco 1T2026 e Santander 1T2026."
            in texto
        )
        assert "um banco e um trimestre por vez" in texto

    @pytest.mark.parametrize("motivo", MOTIVOS_CONHECIDOS + ("motivo novo",))
    def test_contraprova_rascunho_recusado_nunca_aparece(self, motivo):
        """Número sem lastro não vira exemplo nem citação dentro da recusa."""
        texto = app._texto_da_recusa(
            _recusa(motivo, rascunho="O lucro foi de R$ 987,6 milhões."),
            [_recuperado("BB", "4T2025")],
        )
        assert "987" not in texto

    def test_contraprova_motivo_desconhecido_ainda_recusa_com_texto(self):
        texto = app._texto_da_recusa(_recusa("JSON inválido: campo ausente"), [])
        assert "não pôde ser conferida" in texto
        assert "JSON" not in texto

    def test_sem_trechos_nao_aponta_para_trechos(self):
        texto = app._texto_da_recusa(_recusa(MOTIVO_RN02_NUMERO), [])
        assert "Trechos recuperados" not in texto

    def _responder(self, monkeypatch, resposta):
        import src.geracao as geracao

        monkeypatch.setattr(app, "config", carregar_config())
        monkeypatch.setattr(
            app,
            "_pipeline_ao_vivo",
            lambda identidade: (
                _RecuperadorFalso([]),
                _ProvedorFalso(0.0),
                Estrategia.SEMANTICA,
            ),
        )
        monkeypatch.setattr(
            geracao,
            "gerar_resposta",
            lambda *args, **kwargs: (
                resposta,
                SimpleNamespace(custo_usd=0.0, modelo="modelo-falso"),
            ),
        )
        return app.responder_pergunta_livre("Qual foi a margem financeira no 3T2025?")

    def test_motivo_tecnico_segue_para_a_legenda(self, monkeypatch):
        item = self._responder(monkeypatch, _recusa(MOTIVO_RN02_NUMERO))
        assert "Não consegui conferir" in item["resposta"]
        assert item["motivo_tecnico"] == MOTIVO_RN02_NUMERO

    def test_contraprova_resposta_publicada_nao_tem_motivo_tecnico(
        self, monkeypatch
    ):
        publicada = SimpleNamespace(
            recusa=False, motivo_recusa=None, resposta="Texto.", citacoes=()
        )
        item = self._responder(monkeypatch, publicada)
        assert item["motivo_tecnico"] is None

    def test_legenda_mostra_o_motivo_tecnico(self, monkeypatch):
        teste = _app(monkeypatch)
        teste.session_state["historico"] = [
            {
                "papel": "assistant",
                "conteudo": "Texto da recusa.",
                "motivo_tecnico": MOTIVO_RN02_COBERTURA,
            }
        ]
        teste.run()
        assert not teste.exception
        assert any(
            item.value == f"motivo técnico: {MOTIVO_RN02_COBERTURA}"
            for item in teste.caption
        )


class TestExemplosDaAbertura:
    def test_exemplos_da_pergunta_livre_sao_dev_e_nenhum_e_congelado(self):
        """Exemplo na tela não pode ser uma das 45 congeladas: a demonstração
        viraria vitrine do conjunto de teste."""
        perguntas = carregar_conjunto_padrao(carregar_config())
        dev = {p.pergunta for p in perguntas if p.conjunto == "dev"}
        teste = {p.pergunta for p in perguntas if p.conjunto == "teste"}
        assert {pergunta for _, pergunta in app.EXEMPLOS_LIVRE} <= dev
        todos = (
            app.EXEMPLOS_PAINEL + app.EXEMPLOS_LIVRE + app.EXEMPLOS_AGENTES_ROTULADOS
        )
        assert not {pergunta for _, pergunta in todos} & teste

    def test_rotulos_dos_agentes_apontam_para_os_exemplos_do_rastro(self):
        """`gerar_traces_langfuse` usa `EXEMPLOS_AGENTES`; os rótulos não podem
        apontar para outra pergunta."""
        assert tuple(p for _, p in app.EXEMPLOS_AGENTES_ROTULADOS) == (
            app.EXEMPLOS_AGENTES
        )

    def test_exemplo_do_painel_responde_pelo_mesmo_caminho(self, monkeypatch):
        _painel_ou_pula()
        teste = _app(monkeypatch).run()
        rotulo, pergunta = app.EXEMPLOS_PAINEL[0]
        teste.pills[0].set_value(rotulo).run()
        assert not teste.exception
        historico = teste.session_state["historico"]
        assert historico[0] == {"papel": "user", "conteudo": pergunta}
        assert "painel CVM" in historico[1]["modo"]

    def test_contraprova_exemplo_pago_respeita_a_cota(self, monkeypatch):
        teste = _app(monkeypatch, livre=True).run()
        teste.session_state["perguntas_livres_usadas"] = (
            app.config.limite_perguntas_livres_por_sessao
        )
        for modo in (app.MODO_LIVRE, app.MODO_AGENTES):
            teste.radio[0].set_value(modo).run()
            teste.pills[0].set_value(teste.pills[0].options[0]).run()
            assert not teste.exception
            assert teste.session_state["historico"] == []
            assert any("limite da sessão" in erro.value for erro in teste.error)

    @pytest.mark.parametrize(
        "digitada,pendente,esperada",
        [
            ("Digitada?", ("Pergunta livre", "Exemplo?"), "Digitada?"),
            (None, ("Pergunta livre", "Exemplo?"), "Exemplo?"),
            (None, ("Agentes (Investigador + Auditor)", "Exemplo?"), None),
            (None, None, None),
        ],
    )
    def test_regra_do_turno(self, digitada, pendente, esperada):
        assert app.pergunta_do_turno(digitada, app.MODO_LIVRE, pendente) == esperada

    def test_contraprova_exemplo_de_outro_modo_nao_dispara(self, monkeypatch):
        teste = _app(monkeypatch)
        teste.session_state["exemplo_pendente"] = (
            app.MODO_LIVRE,
            "Qual foi o lucro líquido do Itaú no 3T2025?",
        )
        teste.run()
        assert not teste.exception
        assert teste.session_state["historico"] == []
        assert "exemplo_pendente" not in teste.session_state

    def test_contraprova_texto_digitado_vence_o_exemplo(self, monkeypatch):
        _painel_ou_pula()
        teste = _app(monkeypatch).run()
        teste.session_state["exemplo_pendente"] = (
            app.MODO_DEMONSTRACAO,
            "Qual foi o lucro líquido do Itaú no 3T2025?",
        )
        teste.chat_input[0].set_value("Qual foi o lucro do Nubank no 3T2025?").run()
        perguntas = [
            m["conteudo"]
            for m in teste.session_state["historico"]
            if m["papel"] == "user"
        ]
        assert perguntas == ["Qual foi o lucro do Nubank no 3T2025?"]


class TestAberturaAntesDoHistorico:
    def test_tela_inicial_abre_pelo_painel_e_a_trava_vem_depois(self, monkeypatch):
        _painel_ou_pula()
        _auditoria_pendente_ou_pula()
        teste = _app(monkeypatch).run()
        assert not teste.exception
        elementos = _achatar(teste.main)
        assert _primeiro(elementos, "button_group") < _primeiro(
            elementos, "warning", "aguardando auditoria humana"
        )
        assert not _ajuda(teste)

    def test_com_conversa_a_ajuda_fica_acima_do_historico(self, monkeypatch):
        teste = _app(monkeypatch)
        teste.session_state["historico"] = [
            {"papel": "user", "conteudo": "Pergunta anterior."},
            {"papel": "assistant", "conteudo": "Resposta anterior."},
        ]
        teste.run()
        assert not teste.exception
        elementos = _achatar(teste.main)
        assert _primeiro(elementos, "expander", "Como usar o modo") < _primeiro(
            elementos, "chat_message"
        )
        assert _ajuda(teste)[0].proto.expanded is False

    def test_trocar_de_modo_abre_a_ajuda_do_modo_novo(self, monkeypatch):
        teste = _app(monkeypatch, livre=True)
        teste.session_state["historico"] = [
            {"papel": "assistant", "conteudo": "Resposta anterior."}
        ]
        teste.run()
        teste.radio[0].set_value(app.MODO_AGENTES).run()
        assert not teste.exception
        ajuda = [e for e in teste.expander if e.label == "Como usar o modo Agentes"]
        assert ajuda and ajuda[0].proto.expanded is True

    def test_contraprova_sem_troca_a_ajuda_volta_recolhida(self, monkeypatch):
        teste = _app(monkeypatch, livre=True)
        teste.session_state["historico"] = [
            {"papel": "assistant", "conteudo": "Resposta anterior."}
        ]
        teste.run()
        teste.radio[0].set_value(app.MODO_AGENTES).run()
        teste.run()
        ajuda = [e for e in teste.expander if e.label == "Como usar o modo Agentes"]
        assert ajuda and ajuda[0].proto.expanded is False
