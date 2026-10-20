"""Agentes no chat (passo 2 da Etapa 2): Investigador + Auditor com o modelo.

Três contratos:

1. **Experimento intacto.** Os braços A/B/C seguem com quatro ferramentas e o
   mesmo prompt `a3`; o modelo só entra pelo conjunto do produto.
2. **Tarefa composta coordenada.** Com o conjunto do produto, o Investigador
   obtém o ativo no painel e só então consulta o modelo com esse valor; RN01 e
   RN02 passam por código, e o Auditor reproduz com caixa própria.
3. **Trace inteiro.** As gerações e ferramentas do CrewAI caem dentro do span
   de cada agente. A auditoria de 2026-10-19 deixou isto como dúvida: se o
   CrewAI rodasse o laço noutra thread, a consulta aberta não chegaria lá e as
   chamadas sumiriam do trace sem aviso.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import app_streamlit as app
from src import agentes, observabilidade
from src.agentes import (
    INSTRUCAO_INVESTIGADOR_ESTAVEL,
    INSTRUCAO_MODELO,
    PAPEL_AUDITOR,
    PAPEL_INVESTIGADOR,
    VERSAO_PROMPT_AGENTES,
    FerramentasDoAgente,
    LLMPonte,
    construir_ferramentas,
    instrucao_investigador,
    responder_braco_b,
)
from src.config import Config
from src.ferramentas import (
    FERRAMENTA_MODELO,
    FERRAMENTAS_DISPONIVEIS,
    FERRAMENTAS_DO_PRODUTO,
    RegistroChamada,
)
from src.geracao import ProvedorLLM, RespostaBrutaLLM, UsoLLM
from src.projecao import FaixaDePorte, Panorama, consulta_do_modelo

CD_INTER = "080217"
ATIVO_INTER = 63_000_000_000.0
PANORAMA = Panorama(
    trimestre_referencia="3T2025",
    n_companhias_avaliadas=413,
    n_acima_do_dobro_da_base=79,
    limiar_dobro_da_base=0.426,
    taxa_base_painel=0.213,
    # As quatro faixas contíguas do artefato real (`artefatos/modelo/panorama.json`).
    faixas_de_porte=(
        FaixaDePorte("≥ R$ 500 bi", 5e11, 231, 0.0606),
        FaixaDePorte("R$ 100–500 bi", 1e11, 506, 0.2194),
        FaixaDePorte("R$ 10–100 bi", 1e10, 5365, 0.2185),
        FaixaDePorte("< R$ 10 bi", 0.0, 16760, 0.3742),
    ),
    n_observacoes_treino=21119,
    fracao_nao_financeira_treino=0.969,
    auc_walk_forward=0.8786,
)


class CaixaComModelo:
    """Duplo da caixa com as ferramentas que a tarefa composta usa."""

    def __init__(self):
        self._registro: list[RegistroChamada] = []

    @property
    def registro(self):
        return tuple(self._registro)

    def _anotar(self, ferramenta, argumentos, resumo):
        self._registro.append(RegistroChamada(ferramenta, dict(argumentos), resumo))

    def verificar_cobertura(self, entidade, trimestre=None):
        self._anotar("verificar_cobertura", {"entidade": entidade}, "1 entidade: so_painel")
        return {
            "entidades": [{"termo": entidade, "cobertura": {
                "estado": "so_painel", "cd_cvm": CD_INTER, "denom_social": "INTER & CO, INC.",
                "trimestres_painel": ["3T2025"], "trimestres_corpus": [],
            }}],
            "desambiguacao": [],
        }

    def consultar_cvm(self, sql):
        self._anotar("consultar_cvm", {"sql": sql}, "1 linha(s)")
        return {
            "sql": sql,
            "colunas": ["cd_cvm", "denom_social", "trimestre", "conceito", "valor_reais"],
            "linhas": [[CD_INTER, "INTER & CO, INC.", "3T2025", "ativo_total", ATIVO_INTER]],
            "total_linhas": 1,
        }

    def consultar_modelo_prejuizo(self, ativo_total_reais=None, cd_cvm=None):
        self._anotar(FERRAMENTA_MODELO, {"ativo_total_reais": ativo_total_reais}, "panorama 3T2025")
        return consulta_do_modelo(PANORAMA, ativo_total_reais=ativo_total_reais, cd_cvm=cd_cvm)


class ProvedorRoteirizado(ProvedorLLM):
    """Provedor plugável de verdade (herda a instrumentação de geração)."""

    nome = "roteiro"

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.vez = 0
        self.prompts: list[str] = []

    def estimar_custo_maximo(self, prompt_sistema, prompt_usuario):
        return 0.001

    def gerar(self, prompt_sistema, prompt_usuario, temperatura=0.0):
        self.prompts.append(prompt_sistema + "\n" + prompt_usuario)
        texto = self.respostas[min(self.vez, len(self.respostas) - 1)]
        self.vez += 1
        uso = UsoLLM(tokens_entrada=100, tokens_saida=20, custo_usd=0.0002, latencia_s=0.01, modelo="roteiro")
        return RespostaBrutaLLM(texto=texto, uso=uso, modelo="roteiro")


def _acao(nome, argumentos):
    return f"Thought: preciso de {nome}\nAction: {nome}\nAction Input: {json.dumps(argumentos)}"


def _final(objeto):
    return "Thought: pronto\nFinal Answer: " + json.dumps(objeto, ensure_ascii=False)


CITACAO_CVM = f"CVM · INTER & CO, INC. (CD_CVM {CD_INTER}) · 3T2025 · ativo_total"
CITACAO_MODELO = "Modelo preditivo · panorama 3T2025 · regime por porte"
ROTEIRO_INVESTIGADOR = [
    _acao("verificar_cobertura", {"entidade": "Banco Inter", "trimestre": "3T2025"}),
    _acao("consultar_cvm", {"sql": "SELECT * FROM fatos_semanticos WHERE conceito = 'ativo_total' LIMIT 1"}),
    _acao(FERRAMENTA_MODELO, {"ativo_total_reais": ATIVO_INTER}),
    _final({
        "cobertura": "so_painel",
        "comportamento": "resposta_parcial_marcada",
        "motivo_recusa": "fora_do_corpus",
        "bases": ["contabil_consolidado"],
        "afirmacao": (
            f"O ativo total do INTER & CO, INC. (CD_CVM {CD_INTER}) no 3T2025 foi de "
            "R$ 63,0 bilhões. Companhias com ativo nessa faixa (R$ 10–100 bi) tiveram "
            "prejuízo em 21,9% dos trimestres do painel. Não há release indexado."
        ),
        "citacoes": [CITACAO_CVM, CITACAO_MODELO],
        "rastro": ["passo 1: cobertura", "passo 2: ativo no painel", "passo 3: faixa no modelo"],
    }),
]
ROTEIRO_AUDITOR = [
    _acao("consultar_cvm", {"sql": "SELECT * FROM fatos_semanticos WHERE conceito = 'ativo_total' LIMIT 1"}),
    _acao(FERRAMENTA_MODELO, {"ativo_total_reais": ATIVO_INTER}),
    _final({
        "veredito": "confirma",
        "justificativa": "o ativo e a faixa de porte se reproduzem",
        "contraevidencia": [],
        "citacoes": [CITACAO_CVM, CITACAO_MODELO],
    }),
]


def _fabricas(nomes=FERRAMENTAS_DO_PRODUTO):
    provedores = {
        PAPEL_INVESTIGADOR: ProvedorRoteirizado(ROTEIRO_INVESTIGADOR),
        PAPEL_AUDITOR: ProvedorRoteirizado(ROTEIRO_AUDITOR),
    }
    criados = {}

    def fabrica_llm(papel):
        return LLMPonte(provedores[papel], papel=papel)

    def fabrica_ferramentas(papel):
        criados[papel] = FerramentasDoAgente(CaixaComModelo(), papel, nomes)
        return criados[papel]

    return fabrica_llm, fabrica_ferramentas, provedores, criados


# --------------------------------------------------------------------------- #
# 1. Experimento intacto
# --------------------------------------------------------------------------- #


class TestExperimentoIntacto:
    def test_envelope_padrao_tem_as_quatro_e_o_do_produto_as_cinco(self):
        padrao = FerramentasDoAgente(CaixaComModelo(), PAPEL_INVESTIGADOR)
        produto = FerramentasDoAgente(CaixaComModelo(), PAPEL_INVESTIGADOR, FERRAMENTAS_DO_PRODUTO)
        assert [f.name for f in construir_ferramentas(padrao)] == list(FERRAMENTAS_DISPONIVEIS)
        assert [f.name for f in construir_ferramentas(produto)] == list(FERRAMENTAS_DO_PRODUTO)

    def test_envelope_padrao_recusa_chamar_o_modelo(self):
        padrao = FerramentasDoAgente(CaixaComModelo(), PAPEL_INVESTIGADOR)
        with pytest.raises(Exception, match="desconhecida"):
            padrao.executar(FERRAMENTA_MODELO, ativo_total_reais=1.0)

    def test_envelope_recusa_ferramenta_proibida_mesmo_no_produto(self):
        with pytest.raises(ValueError, match="RN07"):
            FerramentasDoAgente(CaixaComModelo(), PAPEL_INVESTIGADOR, FERRAMENTAS_DO_PRODUTO + ("prever_risco",))

    def test_prompt_do_experimento_nao_muda(self):
        """O parágrafo do modelo só entra com a ferramenta, depois do bloco
        estável: o prefixo cacheável e a versão `a3` ficam como estavam."""
        experimento = instrucao_investigador("pergunta")
        produto = instrucao_investigador("pergunta", com_modelo=True)
        assert INSTRUCAO_MODELO not in experimento and INSTRUCAO_MODELO in produto
        assert experimento.startswith(INSTRUCAO_INVESTIGADOR_ESTAVEL)
        assert produto.startswith(INSTRUCAO_INVESTIGADOR_ESTAVEL)
        assert VERSAO_PROMPT_AGENTES == "a3"


# --------------------------------------------------------------------------- #
# 2 e 3. Tarefa composta coordenada, e o trace inteiro
# --------------------------------------------------------------------------- #


@pytest.fixture
def exportador():
    exp = InMemorySpanExporter()
    cfg = Config(langfuse_public_key="pk-lf-teste", langfuse_secret_key="sk-lf-teste")
    assert observabilidade.configurar(cfg, exportador=exp).ativo
    yield exp
    observabilidade.desligar()


class TestTarefaComposta:
    def test_investigador_encadeia_painel_e_modelo_e_o_auditor_confirma(self, exportador):
        fabrica_llm, fabrica_ferramentas, provedores, criados = _fabricas()
        with observabilidade.consulta("agentes"):
            resposta = responder_braco_b(
                "Qual o ativo do Banco Inter no 3T2025 e em que faixa de porte ele cai no modelo?",
                Config(),
                fabrica_llm=fabrica_llm,
                fabrica_ferramentas=fabrica_ferramentas,
            )
        assert resposta.violacoes == () and not resposta.recusa
        assert resposta.veredito_auditor == "confirma"
        ordem = [c.ferramenta for c in criados[PAPEL_INVESTIGADOR].chamadas]
        assert ordem == ["verificar_cobertura", "consultar_cvm", FERRAMENTA_MODELO]
        modelo = criados[PAPEL_INVESTIGADOR].chamadas[-1].resultado
        assert modelo["faixa_do_ativo_informado"]["taxa_historica_prejuizo_pct"] == 21.9
        # O Investigador do produto recebeu o parágrafo do modelo; o Auditor
        # trabalhou com caixa própria, que também tem o modelo.
        assert any(INSTRUCAO_MODELO in p for p in provedores[PAPEL_INVESTIGADOR].prompts)
        assert FERRAMENTA_MODELO in [c.ferramenta for c in criados[PAPEL_AUDITOR].chamadas]

        observabilidade.descarregar()
        spans = list(exportador.get_finished_spans())
        por_nome = {}
        for span in spans:
            por_nome.setdefault(span.name, []).append(span)
        investigador = por_nome["agente.investigador"][0]
        auditor = por_nome["agente.auditor"][0]
        assert investigador.attributes["langfuse.observation.type"] == "agent"

        def dentro(span, pai):
            ids = {s.context.span_id: s for s in spans}
            atual = span
            while atual.parent is not None:
                if atual.parent.span_id == pai.context.span_id:
                    return True
                atual = ids[atual.parent.span_id]
            return False

        # Cada geração e cada ferramenta caiu dentro do agente que a fez: o
        # laço do CrewAI roda na mesma thread e herda a consulta aberta.
        geracoes = por_nome["llm.roteiro"]
        assert len(geracoes) == provedores[PAPEL_INVESTIGADOR].vez + provedores[PAPEL_AUDITOR].vez
        assert sum(dentro(g, investigador) for g in geracoes) == provedores[PAPEL_INVESTIGADOR].vez
        assert sum(dentro(g, auditor) for g in geracoes) == provedores[PAPEL_AUDITOR].vez
        ferramenta_modelo = por_nome[f"ferramenta.{FERRAMENTA_MODELO}"]
        assert {dentro(f, investigador) or dentro(f, auditor) for f in ferramenta_modelo} == {True}
        assert ferramenta_modelo[0].attributes["langfuse.observation.type"] == "tool"


# --------------------------------------------------------------------------- #
# App: custo e cota do modo agentes
# --------------------------------------------------------------------------- #


class _StFalso:
    def __init__(self):
        self.session_state = SimpleNamespace(historico=[], perguntas_livres_usadas=0, custo_usd_acumulado=0.0)
        self.erros = []

    def error(self, mensagem):
        self.erros.append(mensagem)


@pytest.fixture
def st(monkeypatch):
    falso = _StFalso()
    monkeypatch.setattr(app, "st", falso)
    monkeypatch.setattr(app, "config", Config())
    return falso


def _item(custo, consumiu=True):
    return {
        "pergunta_exibida": "pergunta anonimizada", "resposta": "r", "rastro_agentes": ["Investigador · x"],
        "veredito_auditor": "confirma", "custo_usd": custo, "consumiu_chamada": consumiu,
        "modo": "agentes · Investigador + Auditor", "provedor": "gemini/m",
    }


def _responder():
    with observabilidade.consulta("agentes") as rastro:
        return app.responder_no_chat_com_agentes("Qual o ativo do Inter?", rastro)


class TestCotaDosAgentes:
    def test_resposta_debita_custo_e_uma_pergunta(self, st, monkeypatch):
        monkeypatch.setattr(app, "responder_com_agentes", lambda p, orcamento_restante_usd: _item(0.012))
        assert _responder() is True
        assert (st.session_state.perguntas_livres_usadas, st.session_state.custo_usd_acumulado) == (1, 0.012)
        assert st.session_state.historico[-1]["rastro_agentes"] == ["Investigador · x"]

    def test_recusa_antes_do_provedor_nao_debita_cota(self, st, monkeypatch):
        monkeypatch.setattr(app, "responder_com_agentes", lambda p, orcamento_restante_usd: _item(0.0, False))
        _responder()
        assert (st.session_state.perguntas_livres_usadas, st.session_state.custo_usd_acumulado) == (0, 0.0)

    def test_falha_depois_de_pagar_debita_o_que_foi_pago(self, st, monkeypatch):
        def falha(p, orcamento_restante_usd):
            raise app.FalhaConsultaAoVivo(0.004)

        monkeypatch.setattr(app, "responder_com_agentes", falha)
        assert _responder() is True
        assert (st.session_state.perguntas_livres_usadas, st.session_state.custo_usd_acumulado) == (1, 0.004)
        assert st.session_state.historico[-1]["modo"] == "agentes (falha segura)"
        # A pergunta crua não entra no histórico sem passar pela anonimização.
        assert all(m["papel"] != "user" for m in st.session_state.historico)

    def test_falha_sem_gasto_nao_debita_cota(self, st, monkeypatch):
        def falha(p, orcamento_restante_usd):
            raise app.FalhaConsultaAoVivo(0.0)

        monkeypatch.setattr(app, "responder_com_agentes", falha)
        _responder()
        assert (st.session_state.perguntas_livres_usadas, st.session_state.custo_usd_acumulado) == (0, 0.0)


class TestCustoDosAgentes:
    def test_falha_no_meio_devolve_o_custo_confirmado_pelo_orcamento(self, monkeypatch):
        """O custo a debitar é o que o `ControleOrcamento` confirmou, não zero."""
        monkeypatch.setattr(app, "config", Config())
        monkeypatch.setattr(app, "carregar_rota_estruturada", lambda: None)
        monkeypatch.setattr(app, "_pipeline_ao_vivo", lambda identidade: (None, None, None))
        capturado = {}
        original = agentes.fabrica_llm_padrao

        def fabrica_llm(config, orcamento=None):
            capturado["orcamento"] = orcamento
            return original(config, orcamento)

        def gasta_e_falha(pergunta, config, *, fabrica_llm, fabrica_ferramentas):
            orcamento = capturado["orcamento"]
            orcamento.confirmar(orcamento.autorizar("investigador", 0.01), "investigador", 0.0031)
            raise RuntimeError("provedor caiu")

        monkeypatch.setattr(agentes, "fabrica_llm_padrao", fabrica_llm)
        monkeypatch.setattr(agentes, "responder_com_guardrails", gasta_e_falha)
        with pytest.raises(app.FalhaConsultaAoVivo) as erro:
            app.responder_com_agentes("Qual o ativo do Inter?", orcamento_restante_usd=1.0)
        assert erro.value.custo_reservado_usd == pytest.approx(0.0031)

    def test_o_teto_do_orcamento_e_o_saldo_da_sessao(self, monkeypatch):
        monkeypatch.setattr(app, "config", Config())
        monkeypatch.setattr(app, "carregar_rota_estruturada", lambda: None)
        monkeypatch.setattr(app, "_pipeline_ao_vivo", lambda identidade: (None, None, None))
        tetos = []
        original = agentes.fabrica_llm_padrao
        monkeypatch.setattr(
            agentes, "fabrica_llm_padrao",
            lambda config, orcamento=None: tetos.append(orcamento.teto_usd) or original(config, orcamento),
        )
        monkeypatch.setattr(
            agentes, "responder_com_guardrails",
            lambda pergunta, config, **_: agentes.RespostaAgente(pergunta=pergunta, resposta="ok"),
        )
        app.responder_com_agentes("Qual o ativo do Inter?", orcamento_restante_usd=0.37)
        assert tetos == [0.37]
