"""Contratos do rastreamento Langfuse do caminho interativo (`src/observabilidade.py`).

Os testes usam o SDK real com um exportador em memória no lugar do envio
HTTP. O que se inspeciona é exatamente o que sairia para o Langfuse.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# O app liga a observabilidade ao ser importado. Importado aqui, antes de
# qualquer fixture, para não desligar o cliente que o teste acabou de abrir.
import app_streamlit as app
from src import observabilidade
from src.config import Config
from src.geracao import ProvedorLLM, RespostaBrutaLLM, UsoLLM

RAIZ = Path(__file__).resolve().parents[1]
CPF = "123.456.789-09"
NOME = "Joaquim Pereira da Silva"
RECUSA_JSON = json.dumps(
    {"resposta": None, "recusa": True, "motivo_recusa": "sem evidência", "citacoes": []}
)


def _config_com_chave(**campos) -> Config:
    return Config(langfuse_public_key="pk-lf-teste", langfuse_secret_key="sk-lf-teste", **campos)


@pytest.fixture
def exportador():
    exp = InMemorySpanExporter()
    estado = observabilidade.configurar(_config_com_chave(), exportador=exp)
    assert estado.ativo, estado
    yield exp
    observabilidade.desligar()


def _spans(exp: InMemorySpanExporter) -> dict:
    observabilidade.descarregar()
    return {s.name: s for s in exp.get_finished_spans()}


def _tudo_que_sai(exp: InMemorySpanExporter) -> str:
    """Todo texto exportado: atributos, eventos, nomes e mensagens de status."""
    observabilidade.descarregar()
    partes = []
    for s in exp.get_finished_spans():
        partes.append(s.name)
        partes.append(str(s.status.description))
        partes.extend(f"{k}={v}" for k, v in (s.attributes or {}).items())
        for evento in s.events:
            partes.extend(f"{k}={v}" for k, v in (evento.attributes or {}).items())
    return "\n".join(partes)


class ProvedorFalso(ProvedorLLM):
    """Subclasse comum: herda a instrumentação por `__init_subclass__`."""

    nome = "falso"

    def __init__(self, texto: str = RECUSA_JSON, custo: float = 0.0012) -> None:
        self.texto = texto
        self.custo = custo
        self.chamadas = 0

    def estimar_custo_maximo(self, prompt_sistema, prompt_usuario):
        return 0.01

    def gerar(self, prompt_sistema, prompt_usuario, temperatura=0.0):
        self.chamadas += 1
        uso = UsoLLM(
            tokens_entrada=120,
            tokens_saida=30,
            custo_usd=self.custo,
            latencia_s=0.2,
            modelo="modelo-falso",
            tokens_raciocinio=10,
        )
        return RespostaBrutaLLM(texto=self.texto, uso=uso, modelo="modelo-falso")


class ProvedorQueDelega(ProvedorFalso):
    """`gerar_texto` próprio que chama `gerar`: uma geração, não duas."""

    def gerar_texto(self, prompt_sistema, prompt_usuario, temperatura=0.0):
        return self.gerar(prompt_sistema, prompt_usuario, temperatura)


# --------------------------------------------------------------------------- #
# Contrato 1 — sem chave, nada
# --------------------------------------------------------------------------- #


class TestSemChave:
    def test_sem_chave_tudo_vira_no_op(self):
        estado = observabilidade.configurar(Config())
        assert not estado.ativo and "sem chave" in estado.motivo
        with observabilidade.consulta("pergunta_livre") as rastro:
            rastro.atualizar(entrada="x", saida="y")
            with observabilidade.etapa("recuperacao", tipo="retriever") as etapa:
                etapa.atualizar(saida=[1, 2])
            assert ProvedorFalso().gerar("s", "u").texto == RECUSA_JSON

    def test_sem_chave_o_sdk_nem_e_importado(self):
        """RNF12: o modo demonstração sobe sem o pacote ser tocado."""
        codigo = (
            "import sys; from src import observabilidade; import src.geracao;"
            "from src.config import Config; observabilidade.configurar(Config());"
            "print('langfuse' in sys.modules)"
        )
        saida = subprocess.run(
            [sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, check=True
        )
        assert saida.stdout.strip() == "False"


# --------------------------------------------------------------------------- #
# Estrutura do trace
# --------------------------------------------------------------------------- #


class TestEstrutura:
    def test_consulta_vira_trace_com_etapas_filhas(self, exportador):
        with observabilidade.consulta("pergunta_livre", sessao="sessao-1", tags=("pergunta_livre",)):
            with observabilidade.etapa("guardrail.entrada", tipo="guardrail"):
                pass
            with observabilidade.etapa("recuperacao", tipo="retriever"):
                pass
        spans = _spans(exportador)
        raiz = spans["pergunta_livre"]
        assert raiz.parent is None
        for nome, tipo in (("guardrail.entrada", "guardrail"), ("recuperacao", "retriever")):
            assert spans[nome].parent.span_id == raiz.context.span_id
            assert spans[nome].attributes["langfuse.observation.type"] == tipo
            assert spans[nome].attributes["session.id"] == "sessao-1"
            assert spans[nome].context.trace_id == raiz.context.trace_id

    def test_geracao_registra_modelo_tokens_e_custo(self, exportador):
        with observabilidade.consulta("pergunta_livre"):
            ProvedorFalso().gerar("sistema", "usuário", 0.0)
        geracao = _spans(exportador)["llm.falso"]
        atributos = geracao.attributes
        assert atributos["langfuse.observation.type"] == "generation"
        assert atributos["langfuse.observation.model.name"] == "modelo-falso"
        assert json.loads(atributos["langfuse.observation.usage_details"]) == {
            "input": 120, "output": 30, "total": 150
        }
        assert json.loads(atributos["langfuse.observation.cost_details"]) == {"total": 0.0012}
        assert geracao.end_time > geracao.start_time

    def test_geracao_que_delega_nao_duplica(self, exportador):
        provedor_base, provedor_proprio = ProvedorFalso(), ProvedorQueDelega()
        with observabilidade.consulta("pergunta_livre"):
            provedor_base.gerar_texto("s", "u")  # `gerar_texto` herdado de ProvedorLLM
            provedor_proprio.gerar_texto("s", "u")  # `gerar_texto` próprio
        observabilidade.descarregar()
        geracoes = [s for s in exportador.get_finished_spans() if s.name == "llm.falso"]
        assert len(geracoes) == 2
        assert provedor_base.chamadas == provedor_proprio.chamadas == 1

    def test_provedor_nao_muda_de_tipo(self):
        """O tipo entra na identidade da avaliação (`src/avaliacao.py`)."""
        from src.geracao import LLMGemini

        assert LLMGemini.__qualname__ == "LLMGemini" and LLMGemini.__module__ == "src.geracao"
        assert LLMGemini.gerar._observado and LLMGemini.gerar_texto._observado
        assert type(ProvedorFalso()).__qualname__ == "ProvedorFalso"


# --------------------------------------------------------------------------- #
# Contrato 2 — o caminho de avaliação não vira trace
# --------------------------------------------------------------------------- #


class TestCaminhoDeAvaliacao:
    def test_fora_de_consulta_nada_sai(self, exportador):
        with observabilidade.etapa("recuperacao", tipo="retriever") as etapa:
            etapa.atualizar(saida="x")
        ProvedorFalso().gerar("s", "u")
        assert _spans(exportador) == {}


# --------------------------------------------------------------------------- #
# Contrato 3 — RN06 no ponto de saída
# --------------------------------------------------------------------------- #


class TestRN06:
    def test_entrada_saida_e_metadados_saem_redigidos(self, exportador):
        with observabilidade.consulta("pergunta_livre") as rastro:
            rastro.atualizar(
                entrada=f"meu CPF é {CPF}",
                saida={"lista": [f"cpf {CPF}"]},
                metadados={"contato": "fulano@exemplo.com.br"},
            )
            ProvedorFalso(texto=f"resposta com {CPF}").gerar("sistema", f"usuário {CPF}")
        exportado = _tudo_que_sai(exportador)
        assert CPF not in exportado and "123.456.789" not in exportado
        assert "fulano@exemplo.com.br" not in exportado

    def test_excecao_sai_so_pelo_tipo(self, exportador):
        with pytest.raises(ValueError, match=CPF):  # o chamador recebe a exceção intacta
            with observabilidade.consulta("pergunta_livre"):
                with observabilidade.etapa("geracao"):
                    raise ValueError(f"falhou com {CPF}")
        spans = _spans(exportador)
        assert all(not s.events for s in spans.values())
        atributos = spans["geracao"].attributes
        assert atributos["langfuse.observation.level"] == "ERROR"
        assert atributos["langfuse.observation.status_message"] == "ValueError"
        assert CPF not in _tudo_que_sai(exportador)

    def test_sem_presidio_nome_de_pessoa_nao_vai_para_o_trace(self, exportador, monkeypatch):
        """Achado M1 da auditoria de 2026-10-19: sem o Presidio o guardrail não
        detecta nome, e a pergunta ia inteira para o trace."""
        monkeypatch.setattr(app, "responder_prospectiva_se_couber", lambda p: None)
        monkeypatch.setattr(app, "responder_estruturada_se_couber", lambda p: None)
        pergunta = f"Sou {NOME}, cliente do banco. Qual o lucro líquido do Itaú no 3T2025?"
        assert not observabilidade.estado().captura_texto
        with observabilidade.consulta("painel_cvm") as rastro:
            exibida, _ = app.responder_sem_llm(pergunta)
            rastro.atualizar(entrada=observabilidade.texto_livre(exibida))
            ProvedorFalso(texto=f"Olá, {NOME}.").gerar("sistema", f"Pergunta: {pergunta}")
        exportado = _tudo_que_sai(exportador)
        assert "Joaquim" not in exportado
        assert "texto omitido" in exportado  # o tamanho fica, o texto não

    def test_com_presidio_o_texto_entra_redigido(self):
        exp = InMemorySpanExporter()
        estado = observabilidade.configurar(_config_com_chave(presidio_habilitado=True), exportador=exp)
        try:
            assert estado.captura_texto
            with observabilidade.consulta("pergunta_livre") as rastro:
                rastro.atualizar(entrada=observabilidade.texto_livre("lucro do Itaú no 3T2025"))
                rastro.atualizar(saida=observabilidade.texto_livre(f"cpf {CPF}"))
            atributos = _spans(exp)["pergunta_livre"].attributes
            assert atributos["langfuse.observation.input"] == "lucro do Itaú no 3T2025"
            assert CPF not in atributos["langfuse.observation.output"]  # a máscara segue valendo
        finally:
            observabilidade.desligar()

    def test_cadeia_do_app_nao_vaza_cpf(self, exportador, monkeypatch):
        """Contraprova no código do app, não só no módulo: guardrail e rotas."""
        monkeypatch.setattr(app, "responder_prospectiva_se_couber", lambda p: None)
        monkeypatch.setattr(app, "responder_estruturada_se_couber", lambda p: None)
        with observabilidade.consulta("painel_cvm") as rastro:
            exibida, _ = app.responder_sem_llm(f"Meu CPF é {CPF}. Qual o lucro do Itaú no 3T2025?")
            rastro.atualizar(entrada=exibida)
        spans = _spans(exportador)
        assert {"guardrail.entrada", "rota.prospectiva", "rota.estruturada"} <= set(spans)
        assert spans["guardrail.entrada"].attributes["langfuse.observation.type"] == "guardrail"
        assert CPF not in _tudo_que_sai(exportador)


# --------------------------------------------------------------------------- #
# O fluxo de pergunta livre inteiro
# --------------------------------------------------------------------------- #


class _RecuperadorFalso:
    def __init__(self, recuperados):
        self.recuperados = recuperados

    def recuperar(self, pergunta, estrategia):
        return self.recuperados


class TestFluxoInterativo:
    def test_pergunta_livre_gera_a_arvore_completa(self, exportador, monkeypatch, chunks_exemplo):
        from src.recuperacao import Estrategia, ResultadoRecuperacao

        recuperados = [ResultadoRecuperacao(c, 0.9, Estrategia.SEMANTICA) for c in chunks_exemplo]
        provedor = ProvedorFalso()
        monkeypatch.setattr(app, "config", Config())
        monkeypatch.setattr(
            app,
            "_pipeline_ao_vivo",
            lambda identidade: (_RecuperadorFalso(recuperados), provedor, Estrategia.SEMANTICA),
        )
        with observabilidade.consulta("pergunta_livre"):
            item = app.responder_pergunta_livre("Qual foi o lucro do Itaú no 4T2025?")
        assert item["custo_usd"] == pytest.approx(0.0012)

        spans = _spans(exportador)
        raiz = spans["pergunta_livre"].context.span_id
        for nome in ("guardrail.entrada", "pipeline.carregar", "recuperacao", "geracao", "guardrail.saida"):
            assert spans[nome].parent.span_id == raiz, nome
        assert spans["llm.falso"].parent.span_id == spans["geracao"].context.span_id
        recuperacao = json.loads(spans["recuperacao"].attributes["langfuse.observation.output"])
        assert [r["chunk"] for r in recuperacao] == [c.id for c in chunks_exemplo]
        assert json.loads(spans["llm.falso"].attributes["langfuse.observation.cost_details"]) == {
            "total": 0.0012
        }


class _CaixaFalsa:
    """O mínimo de `CaixaDeFerramentas` que `FerramentasDoAgente` usa."""

    def __init__(self):
        from src.ferramentas import RegistroChamada

        self._RegistroChamada = RegistroChamada
        self.registro: list = []

    def buscar_trechos(self, pergunta, top_k=None):
        self.registro.append(
            self._RegistroChamada("buscar_trechos", {"pergunta": pergunta}, resumo=f"2 trechos para {pergunta}")
        )
        return ["t1", "t2"]


class TestFerramentasDeAgente:
    def test_chamada_de_ferramenta_vira_span_tool_sem_texto_livre(self, exportador):
        from src.agentes import PAPEL_INVESTIGADOR, FerramentasDoAgente

        ferramentas = FerramentasDoAgente(_CaixaFalsa(), PAPEL_INVESTIGADOR)
        with observabilidade.consulta("pergunta_livre"):
            assert ferramentas.executar("buscar_trechos", pergunta=f"lucro do {NOME}") == ["t1", "t2"]
        span = _spans(exportador)["ferramenta.buscar_trechos"]
        assert span.attributes["langfuse.observation.type"] == "tool"
        assert json.loads(span.attributes["langfuse.observation.output"])["falhou"] is False
        assert "Joaquim" not in _tudo_que_sai(exportador)


# --------------------------------------------------------------------------- #
# Contrato 4 — isolamento do OpenTelemetry
# --------------------------------------------------------------------------- #


class TestIsolamento:
    def test_provider_global_nao_e_tocado(self):
        from opentelemetry import trace

        antes = trace.get_tracer_provider()
        observabilidade.configurar(_config_com_chave(), exportador=InMemorySpanExporter())
        try:
            assert trace.get_tracer_provider() is antes
        finally:
            observabilidade.desligar()

    def test_span_de_outra_biblioteca_nao_sai(self, exportador):
        """Filtro de export: só o escopo do SDK do Langfuse vai para fora.

        O span imita um instrumentador de LLM (escopo `litellm`, atributo
        `gen_ai.*`), que o filtro padrão do SDK exportaria: sem o filtro
        explícito este teste falha (achado B2 da auditoria de 2026-10-19)."""
        provider = observabilidade._cliente._resources.tracer_provider
        with observabilidade.consulta("pergunta_livre"):
            with provider.get_tracer("litellm").start_as_current_span(
                "chamada_litellm", attributes={"gen_ai.system": "openai"}
            ):
                pass
        spans = _spans(exportador)
        assert "pergunta_livre" in spans  # controle positivo: o export funciona
        assert "chamada_litellm" not in spans

    def test_otel_sdk_disabled_desliga_com_motivo_visivel(self, monkeypatch):
        monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
        estado = observabilidade.configurar(_config_com_chave())
        assert not estado.ativo and "OTEL_SDK_DISABLED" in estado.motivo

    def test_importar_agentes_nao_desliga_o_otel_e_crewai_fica_mudo(self):
        """O CrewAI desligava o OpenTelemetry do processo, e o Langfuse junto."""
        ambiente = {
            k: v for k, v in os.environ.items()
            if not k.startswith(("OTEL_", "CREWAI_"))
        }
        codigo = (
            "import os; import src.agentes;"
            "from crewai.telemetry.telemetry import Telemetry;"
            "print(os.environ.get('OTEL_SDK_DISABLED'), Telemetry._is_telemetry_disabled(),"
            " os.environ.get('CREWAI_DISABLE_TRACKING'))"
        )
        saida = subprocess.run(
            [sys.executable, "-c", codigo], cwd=RAIZ, env=ambiente,
            capture_output=True, text=True, check=True,
        )
        assert saida.stdout.strip().splitlines()[-1] == "None True true"


# --------------------------------------------------------------------------- #
# Contrato 5 — rastrear nunca derruba a resposta
# --------------------------------------------------------------------------- #


class TestRobustez:
    def test_falha_do_sdk_nao_derruba_a_etapa(self, exportador, monkeypatch):
        def quebra(**_):
            raise RuntimeError("SDK fora do ar")

        monkeypatch.setattr(observabilidade._cliente, "start_as_current_observation", quebra)
        with observabilidade.consulta("pergunta_livre") as rastro:
            rastro.atualizar(entrada="x")
            with observabilidade.etapa("recuperacao") as etapa:
                etapa.atualizar(saida="y")
                valor = 42
            resposta = ProvedorFalso().gerar("s", "u")
        assert valor == 42 and resposta.texto == RECUSA_JSON

    def test_resumo_nao_roda_com_rastreamento_desligado(self):
        """Regressão achada na suíte: o resumo da recuperação rodava sem
        Langfuse e quebrava num objeto sem `score`, derrubando a resposta."""
        observabilidade.configurar(Config())
        chamado = []
        with observabilidade.consulta("pergunta_livre"):
            with observabilidade.etapa("recuperacao", entrada=lambda: chamado.append("e")) as etapa:
                etapa.atualizar(saida=lambda: chamado.append("s") or 1 / 0)
        assert chamado == []

    def test_resumo_que_falha_nao_derruba(self, exportador):
        with observabilidade.consulta("pergunta_livre"):
            with observabilidade.etapa("recuperacao") as etapa:
                etapa.atualizar(saida=lambda: object().score)
        spans = _spans(exportador)
        assert "langfuse.observation.output" not in spans["recuperacao"].attributes

    def test_uso_incompleto_nao_derruba_a_geracao(self, exportador):
        """Achado B1: as conversões de `concluir_geracao` ficavam fora do `try`."""

        class ProvedorSemLatencia(ProvedorFalso):
            def gerar(self, prompt_sistema, prompt_usuario, temperatura=0.0):
                bruta = super().gerar(prompt_sistema, prompt_usuario, temperatura)
                return RespostaBrutaLLM(
                    texto=bruta.texto,
                    uso=UsoLLM(tokens_entrada=1, tokens_saida=1, custo_usd=0.0, latencia_s=None),
                    modelo="m",
                )

        with observabilidade.consulta("pergunta_livre"):
            assert ProvedorSemLatencia().gerar("s", "u").texto == RECUSA_JSON
        assert "llm.falso" in _spans(exportador)

    def test_rerun_do_streamlit_nao_marca_erro(self, exportador):
        class RerunException(Exception):
            """Mesmo nome da exceção de controle de fluxo do Streamlit."""

        with pytest.raises(RerunException):
            with observabilidade.consulta("pergunta_livre"):
                raise RerunException()
        atributos = _spans(exportador)["pergunta_livre"].attributes
        assert "langfuse.observation.level" not in atributos

    def test_texto_longo_e_cortado_com_aviso(self, exportador):
        with observabilidade.consulta("pergunta_livre") as rastro:
            rastro.atualizar(saida="a" * (observabilidade.TAMANHO_MAXIMO_TEXTO + 500))
        saida = _spans(exportador)["pergunta_livre"].attributes["langfuse.observation.output"]
        assert "500 caracteres omitidos" in saida
        assert len(saida) < observabilidade.TAMANHO_MAXIMO_TEXTO + 100
