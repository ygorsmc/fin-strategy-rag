from dataclasses import replace

import pytest
from streamlit.testing.v1 import AppTest

from src.config import (
    Config,
    _env_bool,
    _validar_config,
    carregar_config,
    endpoint_mistral_ocr_e_oficial,
)


def test_config_rejeita_overlap_invalido():
    with pytest.raises(ValueError, match="SOBREPOSICAO"):
        _validar_config(
            replace(Config(), chunk_tamanho_tokens=100, chunk_sobreposicao_tokens=100)
        )


def test_config_rejeita_nan_e_top_k_zero():
    with pytest.raises(ValueError, match="TOP_K.*ORCAMENTO_TETO_USD"):
        _validar_config(replace(Config(), top_k=0, orcamento_teto_usd=float("nan")))


def test_extrator_padrao_e_o_primario_da_spec_5_3(tmp_path):
    """O default tem de ser `mistral_ocr`.

    O cache de OCR é versionado (RNF10) e `corpus/raw/` não é: num clone limpo,
    só o extrator primário roda — e é com ele que o índice publicado é
    construído, então qualquer outro default faria os loaders recusarem o índice
    de deploy por divergência de extrator (RNF09).
    """
    config = carregar_config(env_file=tmp_path / "inexistente.env")
    assert config.extrator == "mistral_ocr"


def test_variavel_de_extracao_aposentada_falha_com_instrucao_de_migracao(
    monkeypatch, tmp_path
):
    """Sem alias: `mistral_overlay` não tem sucessor, e um alias parcial
    escolheria em silêncio um extrator que ninguém pediu."""
    monkeypatch.setenv("EXTRACAO_PDF_MODO", "local")
    with pytest.raises(ValueError, match="EXTRACAO_PDF_MODO.*EXTRATOR"):
        carregar_config(env_file=tmp_path / "inexistente.env")


def test_extrator_e_lido_do_ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("EXTRATOR", "pdfplumber")
    assert (
        carregar_config(env_file=tmp_path / "inexistente.env").extrator
        == "pdfplumber"
    )


def test_booleano_de_ambiente_e_estrito(monkeypatch):
    monkeypatch.setenv("FLAG_TESTE", "talvez")
    with pytest.raises(ValueError, match="FLAG_TESTE deve ser booleano"):
        _env_bool("FLAG_TESTE", False)


def test_repr_da_config_nao_expoe_chaves():
    config = Config(
        gemini_api_key="segredo-gemini",
        azure_openai_api_key="segredo-azure",
        openai_api_key="segredo-openai",
        deepseek_api_key="segredo-deepseek",
        mistral_ocr_api_key="segredo-mistral",
    )
    representacao = repr(config)
    assert "segredo-" not in representacao


@pytest.mark.parametrize("limiar", [-0.01, 1.01, float("nan"), True])
def test_config_rejeita_limiar_confianca_ocr_fora_do_contrato(limiar):
    with pytest.raises(ValueError, match="LIMIAR_CONFIANCA_MEDIA"):
        _validar_config(
            replace(Config(), mistral_ocr_limiar_confianca_media=limiar)
        )


@pytest.mark.parametrize(
    "config,trecho",
    [
        (
            replace(
                Config(),
                llm_provider="gemini",
                gemini_base_url="https://exemplo.invalid/v1",
            ),
            "GEMINI_BASE_URL",
        ),
        (
            replace(Config(), ollama_base_url="https://ollama.exemplo.invalid/v1"),
            "loopback",
        ),
        (
            replace(Config(), bancos=("BTG",)),
            "corpus canônico",
        ),
        (
            replace(
                Config(),
                azure_openai_endpoint="https://coletor.exemplo.invalid",
            ),
            "AZURE_OPENAI_ENDPOINT",
        ),
        (
            replace(
                Config(),
                mistral_ocr_endpoint="https://api.mistral.ai.evil.invalid/v1/ocr",
            ),
            "MISTRAL_OCR_ENDPOINT",
        ),
        (
            replace(Config(), mistral_ocr_modelo="mistral-ocr-latest"),
            "versão pinada",
        ),
        (
            replace(Config(), mistral_ocr_modelo="-mistral-ocr-4-0"),
            "versão pinada",
        ),
        (
            replace(Config(), extrator="chamar_api_durante_ingestao"),
            "EXTRATOR",
        ),
        # O valor antigo não vale como novo: aceitá-lo escolheria um extrator
        # que ninguém pediu (ver VARIAVEIS_APOSENTADAS).
        (replace(Config(), extrator="local"), "EXTRATOR"),
        (replace(Config(), extrator="mistral_overlay"), "EXTRATOR"),
    ],
)
def test_config_rejeita_endpoint_ou_corpus_inseguro(config, trecho):
    with pytest.raises(ValueError, match=trecho):
        _validar_config(config)


@pytest.mark.parametrize(
    "endpoint,esperado",
    [
        ("https://api.mistral.ai/v1/ocr", True),
        ("https://api.mistral.ai:443/v1/ocr/", True),
        ("http://api.mistral.ai/v1/ocr", False),
        ("https://api.mistral.ai/v1/ocr?destino=outro", False),
        ("https://chave@api.mistral.ai/v1/ocr", False),
        ("https://api.mistral.ai.evil.invalid/v1/ocr", False),
    ],
)
def test_endpoint_mistral_ocr_e_estritamente_oficial(endpoint, esperado):
    assert endpoint_mistral_ocr_e_oficial(endpoint) is esperado


def test_app_cacheado_sobe_sem_habilitar_respostas_dev_como_finais():
    app = AppTest.from_file("app_streamlit.py", default_timeout=20).run()
    assert not app.exception
    assert len(app.radio) == 1
    assert app.radio[0].options == ["Demonstração (cacheado)"]
    assert not app.selectbox
    assert not app.button
    assert any("cache final validado" in item.value for item in app.warning)
    assert any("Não constitui recomendação" in item.value for item in app.caption)
