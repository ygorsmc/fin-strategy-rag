"""Regressões dos gates externos — todos os provedores são fakes locais."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts import gate as gate_azure
from scripts import gate_gemini
from scripts.gate_seguranca import resumir_excecao, sanitizar_evidencia
from src.config import Config
from src.geracao import RespostaBrutaLLM, UsoLLM


class _ProvedorGeminiFake:
    nome = "gemini"
    custo_auditavel = True

    def __init__(self, *, estimativa: float = 0.01, falhar: bool = False):
        self.estimativa = estimativa
        self.falhar = falhar
        self.chamadas = 0

    def estimar_custo_maximo(self, _sistema: str, _usuario: str) -> float:
        return self.estimativa

    def gerar(self, _sistema: str, _usuario: str, temperatura: float = 0.0):
        assert temperatura == 0.0
        self.chamadas += 1
        if self.falhar:
            raise RuntimeError("resposta refletida com api_key=segredo-super-secreto")
        if self.chamadas == 1:
            objeto = {
                "resposta": "26,6%",
                "recusa": False,
                "motivo_recusa": None,
                "citacoes": [
                    {
                        "empresa": "BTG",
                        "documento": "btg_release_1T2026",
                        "trimestre": "1T2026",
                        "pagina": 6,
                    }
                ],
            }
        else:
            objeto = {
                "resposta": None,
                "recusa": True,
                "motivo_recusa": "Não há evidência.",
                "citacoes": [],
            }
        uso = UsoLLM(
            tokens_entrada=20,
            tokens_saida=10,
            custo_usd=0.002,
            latencia_s=0.01,
            modelo="gemini-fake",
        )
        return RespostaBrutaLLM(
            texto=json.dumps(objeto),
            uso=uso,
            modelo="gemini-fake",
        )


def _config_gemini(**mudancas) -> Config:
    base = {
        "llm_provider": "gemini",
        "gemini_api_key": "segredo-super-secreto",
        "gemini_modelo_llm": "gemini-fake",
        "orcamento_teto_usd": 1.0,
    }
    base.update(mudancas)
    return Config(**base)


def _isolar_saida_gemini(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    relatorio = tmp_path / "gate_gemini.md"
    journal = tmp_path / "gate_gemini.jsonl"
    monkeypatch.setattr(gate_gemini, "CAMINHO_RELATORIO", relatorio)
    monkeypatch.setattr(gate_gemini, "CAMINHO_JOURNAL", journal)
    return relatorio, journal


def test_sanitizacao_remove_segredo_conhecido_e_padroes() -> None:
    segredo = "segredo-super-secreto"
    evidencia = sanitizar_evidencia(
        "Authorization: Bearer token-refletido "
        f"api_key={segredo} https://exemplo.invalid/?key=outro-token",
        segredos=(segredo,),
    )
    assert segredo not in evidencia
    assert "token-refletido" not in evidencia
    assert "outro-token" not in evidencia
    assert evidencia.count("[REDACTED]") >= 3


def test_resumo_de_excecao_nao_persiste_mensagem_refletida() -> None:
    segredo = "segredo-super-secreto"
    resumo = resumir_excecao(RuntimeError(f"falhou: {segredo}"), segredos=(segredo,))
    assert resumo == "RuntimeError"
    assert segredo not in resumo


def test_gate_gemini_sem_opt_in_nao_carrega_config_nem_chama_provedor(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        gate_gemini,
        "carregar_config",
        lambda: (_ for _ in ()).throw(AssertionError("não deveria carregar")),
    )
    monkeypatch.setattr(
        gate_gemini,
        "fabricar_provedor_llm",
        lambda _config: (_ for _ in ()).throw(AssertionError("não deveria criar")),
    )
    assert gate_gemini.executar_gate_gemini() is False


def test_preflight_gemini_bloqueia_duas_chamadas_acima_do_teto(
    monkeypatch,
    tmp_path: Path,
) -> None:
    relatorio, journal = _isolar_saida_gemini(monkeypatch, tmp_path)
    provedor = _ProvedorGeminiFake(estimativa=0.06)
    monkeypatch.setattr(gate_gemini, "fabricar_provedor_llm", lambda _c: provedor)

    passou = gate_gemini.executar_gate_gemini(
        _config_gemini(orcamento_teto_usd=0.1),
        permitir_api_paga=True,
    )

    assert passou is False
    assert provedor.chamadas == 0
    assert "preflight recusado" in relatorio.read_text(encoding="utf-8")
    eventos = [json.loads(linha) for linha in journal.read_text().splitlines()]
    assert [evento["evento"] for evento in eventos] == ["execucao_encerrada"]
    assert eventos[0]["iniciadas"] == 0


def test_gate_gemini_fake_registra_antes_depois_e_custo_observado(
    monkeypatch,
    tmp_path: Path,
) -> None:
    relatorio, journal = _isolar_saida_gemini(monkeypatch, tmp_path)
    provedor = _ProvedorGeminiFake()
    monkeypatch.setattr(gate_gemini, "fabricar_provedor_llm", lambda _c: provedor)

    passou = gate_gemini.executar_gate_gemini(
        _config_gemini(),
        permitir_api_paga=True,
    )

    assert passou is True
    assert provedor.chamadas == 2
    eventos = [json.loads(linha) for linha in journal.read_text().splitlines()]
    nomes = [evento["evento"] for evento in eventos]
    assert nomes == [
        "preflight_aprovado",
        "chamada_iniciada",
        "chamada_concluida",
        "chamada_iniciada",
        "chamada_concluida",
        "execucao_encerrada",
    ]
    assert eventos[-1]["custo_observado_usd"] == 0.004
    conteudo = relatorio.read_text(encoding="utf-8")
    assert "Gate Gemini: {'PASSOU'" not in conteudo
    assert "✅ PASSOU" in conteudo
    assert "segredo-super-secreto" not in conteudo


def test_gate_gemini_falha_sem_telemetria_debita_estimativa(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, journal = _isolar_saida_gemini(monkeypatch, tmp_path)
    provedor = _ProvedorGeminiFake(estimativa=0.03, falhar=True)
    monkeypatch.setattr(gate_gemini, "fabricar_provedor_llm", lambda _c: provedor)

    passou = gate_gemini.executar_gate_gemini(
        _config_gemini(),
        permitir_api_paga=True,
    )

    assert passou is False
    eventos = [json.loads(linha) for linha in journal.read_text().splitlines()]
    falha = next(e for e in eventos if e["evento"] == "chamada_falhou")
    assert falha["custo_observado_usd"] is None
    assert falha["debito_conservador_usd"] == 0.03
    assert "segredo-super-secreto" not in json.dumps(eventos)


def test_gate_azure_sem_opt_in_nao_carrega_config(monkeypatch) -> None:
    monkeypatch.setattr(
        gate_azure,
        "carregar_config",
        lambda: (_ for _ in ()).throw(AssertionError("não deveria carregar")),
    )
    assert gate_azure.executar_gate() is False


def test_preflight_azure_exige_os_dois_deployments_antes_de_chamar(
    monkeypatch,
    tmp_path: Path,
) -> None:
    relatorio = tmp_path / "gate.md"
    journal = tmp_path / "gate_azure.jsonl"
    monkeypatch.setattr(gate_azure, "CAMINHO_RELATORIO", relatorio)
    monkeypatch.setattr(gate_azure, "CAMINHO_JOURNAL", journal)
    monkeypatch.setattr(
        gate_azure,
        "fabricar_provedor_llm",
        lambda _c: (_ for _ in ()).throw(AssertionError("não deveria criar")),
    )
    config = Config(
        azure_openai_endpoint="https://recurso.openai.azure.com",
        azure_openai_api_key="segredo-azure",
        azure_openai_api_version="2025-01-01-preview",
        azure_openai_deployment_llm="llm",
        azure_openai_deployment_embedding="",
    )

    passou = gate_azure.executar_gate(config, permitir_api_paga=True)

    assert passou is False
    assert "AZURE_OPENAI_DEPLOYMENT_EMBEDDING" in relatorio.read_text()
    eventos = [json.loads(linha) for linha in journal.read_text().splitlines()]
    assert len(eventos) == 1
    assert eventos[0]["evento"] == "execucao_encerrada"
    assert eventos[0]["iniciadas"] == 0
    assert eventos[0]["concluidas"] == 0
    assert eventos[0]["falhas"] == 0
    assert eventos[0]["custo_observado_usd"] is None
    assert eventos[0]["debito_conservador_usd"] is None
    assert eventos[0]["resultado"] == "falhou"


class _LLMAzureFake:
    nome = "azure_openai"

    def gerar(self, _sistema: str, _usuario: str, temperatura: float = 0.0):
        uso = UsoLLM(3, 1, None, 0.01, "azure-fake")
        return RespostaBrutaLLM("ok", uso, "azure-fake")


class _EmbeddingsAzureFake:
    nome = "azure_openai"
    dimensao = 3

    def embedar(self, _textos: list[str]):
        return np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32)


def test_gate_azure_fake_registra_duas_chamadas_com_custo_indeterminado(
    monkeypatch,
    tmp_path: Path,
) -> None:
    relatorio = tmp_path / "gate.md"
    journal = tmp_path / "gate_azure.jsonl"
    monkeypatch.setattr(gate_azure, "CAMINHO_RELATORIO", relatorio)
    monkeypatch.setattr(gate_azure, "CAMINHO_JOURNAL", journal)
    monkeypatch.setattr(
        gate_azure, "fabricar_provedor_llm", lambda _c: _LLMAzureFake()
    )
    monkeypatch.setattr(
        gate_azure,
        "fabricar_provedor_embeddings",
        lambda _c: _EmbeddingsAzureFake(),
    )
    config = Config(
        azure_openai_endpoint="https://recurso.openai.azure.com",
        azure_openai_api_key="segredo-azure",
        azure_openai_api_version="2025-01-01-preview",
        azure_openai_deployment_llm="llm",
        azure_openai_deployment_embedding="emb",
    )

    passou = gate_azure.executar_gate(config, permitir_api_paga=True)

    assert passou is True
    eventos = [json.loads(linha) for linha in journal.read_text().splitlines()]
    assert [e["evento"] for e in eventos].count("chamada_iniciada") == 2
    assert [e["evento"] for e in eventos].count("chamada_concluida") == 2
    assert all(
        e.get("custo_observado_usd") is None
        for e in eventos
        if e["evento"].startswith("chamada_")
    )
    conteudo = relatorio.read_text(encoding="utf-8")
    assert "✅ PASSOU" in conteudo
    assert "segredo-azure" not in conteudo
