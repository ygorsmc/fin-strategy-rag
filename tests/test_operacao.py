"""Regressões dos scripts operacionais e dos guardrails de custo."""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

import executar_pipeline
from scripts import baixar_corpus
from src.bloqueio import bloqueio_exclusivo
from src.config import Config


class _RespostaRedirect:
    status_code = 302
    headers = {"Location": "http://127.0.0.1/segredo"}

    def close(self):
        return None


class _SessaoRedirect:
    def __init__(self):
        self.chamadas = 0

    def get(self, *args, **kwargs):
        self.chamadas += 1
        assert kwargs["allow_redirects"] is False
        return _RespostaRedirect()


def test_downloader_valida_cada_redirect_antes_de_seguir(tmp_path):
    sessao = _SessaoRedirect()
    with pytest.raises(ValueError, match="HTTPS|allowlist"):
        baixar_corpus._baixar_para_temporario(
            "https://api.mziq.com/arquivo.pdf",
            tmp_path / "arquivo.pdf",
            sessao,
        )
    assert sessao.chamadas == 1
    assert not list(tmp_path.glob("*.part"))


def test_manifesto_nao_pode_ser_afrouxado_pelo_env(monkeypatch):
    monkeypatch.setenv("BANCOS", "NUBANK")
    caminho = Path("corpus/metadados.csv")
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        linhas = list(leitor)
        campos = leitor.fieldnames
    baixar_corpus._validar_manifesto(linhas, campos)


def test_pipeline_exige_confirmacao_explicita_para_api_paga():
    config = Config(llm_provider="gemini")
    with pytest.raises(RuntimeError, match="--permitir-api-paga"):
        executar_pipeline._validar_precondicoes(
            config, True, ["avaliacao"], permitir_api_paga=False
        )
    executar_pipeline._validar_precondicoes(
        config, True, ["avaliacao"], permitir_api_paga=True
    )


def test_pipeline_local_nao_exige_flag_de_api_paga():
    executar_pipeline._validar_precondicoes(
        Config(llm_provider="ollama"),
        True,
        ["avaliacao"],
        permitir_api_paga=False,
    )


def test_pipeline_exige_opt_in_para_embedding_externo_na_indexacao():
    config = Config(llm_provider="ollama", embedding_provider="openai")
    with pytest.raises(RuntimeError, match="--permitir-api-paga"):
        executar_pipeline._validar_precondicoes(
            config, False, ["indexacao"], permitir_api_paga=False
        )
    executar_pipeline._validar_precondicoes(
        config, False, ["indexacao"], permitir_api_paga=True
    )


def test_avaliacao_bloqueia_embedding_externo_sem_contabilidade():
    config = Config(llm_provider="ollama", embedding_provider="openai")
    with pytest.raises(RuntimeError, match="journal RNF08"):
        executar_pipeline._validar_precondicoes(
            config, True, ["avaliacao"], permitir_api_paga=True
        )


def test_conjunto_efetivo_preserva_comportamento_padrao_sem_flag():
    assert executar_pipeline._conjunto_efetivo(True, None) == "dev"
    assert executar_pipeline._conjunto_efetivo(False, None) == "teste"


def test_conjunto_efetivo_desacopla_dev_do_indice_de_amostra():
    # --conjunto dev sem --amostra: dev contra o índice integral — o caminho
    # que faltava para medir recall antes do congelado (plano §7, etapa 9).
    assert executar_pipeline._conjunto_efetivo(False, "dev") == "dev"
    assert executar_pipeline._conjunto_efetivo(False, "teste") == "teste"
    assert executar_pipeline._conjunto_efetivo(True, "dev") == "dev"


def test_conjunto_efetivo_rejeita_amostra_com_teste():
    with pytest.raises(ValueError, match="incompatível"):
        executar_pipeline._conjunto_efetivo(True, "teste")


def test_precondicoes_aceitam_conjunto_dev_contra_indice_integral():
    executar_pipeline._validar_precondicoes(
        Config(llm_provider="ollama"),
        False,
        ["avaliacao"],
        permitir_api_paga=False,
        conjunto="dev",
    )


def test_precondicoes_propagam_a_rejeicao_de_amostra_com_conjunto_teste():
    with pytest.raises(ValueError, match="incompatível"):
        executar_pipeline._validar_precondicoes(
            Config(llm_provider="ollama"),
            True,
            ["avaliacao"],
            permitir_api_paga=False,
            conjunto="teste",
        )


def test_lock_impede_duas_mutacoes_do_mesmo_namespace(tmp_path):
    caminho = tmp_path / ".recurso.lock"
    with bloqueio_exclusivo(caminho, "recurso de teste"):
        with pytest.raises(RuntimeError, match="Outra execução"):
            with bloqueio_exclusivo(caminho, "recurso de teste"):
                raise AssertionError("não deve adquirir o segundo lock")


def test_lock_rejeita_symlink_sem_alterar_o_alvo(tmp_path):
    alvo = tmp_path / "alvo.txt"
    alvo.write_text("não alterar", encoding="utf-8")
    caminho = tmp_path / ".recurso.lock"
    caminho.symlink_to(alvo)

    with pytest.raises(RuntimeError, match="inseguro"):
        with bloqueio_exclusivo(caminho, "recurso de teste"):
            raise AssertionError("symlink não deve ser adquirido")

    assert alvo.read_text(encoding="utf-8") == "não alterar"


def test_lock_rejeita_hardlink_e_forca_permissao_privada(tmp_path):
    alvo = tmp_path / "alvo.txt"
    alvo.write_text("não alterar", encoding="utf-8")
    hardlink = tmp_path / ".hardlink.lock"
    os.link(alvo, hardlink)

    with pytest.raises(RuntimeError, match="inseguro"):
        with bloqueio_exclusivo(hardlink, "recurso de teste"):
            raise AssertionError("hardlink não deve ser adquirido")
    assert alvo.read_text(encoding="utf-8") == "não alterar"

    caminho = tmp_path / ".privado.lock"
    with bloqueio_exclusivo(caminho, "recurso de teste"):
        assert caminho.stat().st_mode & 0o777 == 0o600
