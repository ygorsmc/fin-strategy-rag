from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import app_streamlit as app
from src.avaliacao import hash_json_canonico
from src.config import Config
from src.ingestao import Chunk
from src.recuperacao import Estrategia


COMPONENTES_FINGERPRINT = {"fixture": "test_app_hardening-v1"}
FINGERPRINT = hash_json_canonico(COMPONENTES_FINGERPRINT)
ESTRATEGIA_DEMO = Estrategia.SEMANTICA.value
PROVEDOR_LLM = "teste"


def _metricas(
    cache: dict | None = None,
    *,
    componentes: dict | None = None,
    status: str = "completa",
) -> dict:
    componentes = componentes or COMPONENTES_FINGERPRINT
    fingerprint = hash_json_canonico(componentes)
    cache = cache if cache is not None else _cache(fingerprint=fingerprint)
    resultado = {
        "_meta": {
            "fingerprint": fingerprint,
            "fingerprint_componentes": componentes,
            "fingerprint_componentes_sha256": hash_json_canonico(componentes),
            "status": status,
            "avaliacao_automatica": "completa",
            "groundedness_manual_15": "concluida",
            "groundedness_manual_score": 1.0,
            "estabilidade_10x3": "concluida",
            "estabilidade_perguntas_com_variacao": 0,
            "recall_k": 5,
            "temperatura": 0.0,
            "run_ids": ["run-teste"],
            "estrategia_demo_e_auditoria": ESTRATEGIA_DEMO,
            "provedor_llm": PROVEDOR_LLM,
            "cache_demo_sha256": hash_json_canonico(cache),
            "cache_demo_n_itens": len(cache),
        },
    }
    resultado.update(
        {
            estrategia: {
                "recall_at_5": 0.90,
                "exatidao_numerica": 0.95,
                "taxa_recusa_correta": 1.0,
                "custo_medio_usd": 0.01,
                "custo_conservador_medio_usd": 0.012,
                "custo_observado_medio_usd": 0.009,
                "latencia_media_s": 0.5,
                "latencia_p95_s": 0.8,
                "n_json_invalido": 0,
                "n_itens": 45,
                "n_erros": 0,
                "n_erros_pendentes": 0,
                "n_erros_historicos": 0,
                "n_tentativas": 45,
                "n_tentativas_sem_telemetria": 0,
                "n_chamadas": 45,
                "n_chamadas_sem_telemetria": 0,
                "n_itens_latencia_a_quente": 45,
            }
            for estrategia in app.ESTRATEGIAS_AVALIACAO
        }
    )
    return resultado


def _cache(fingerprint: str = FINGERPRINT, resposta: str = "Resposta A") -> dict:
    return {
        "Qual foi o resultado?": {
            "resposta": resposta,
            "fontes": ["BANCO · documento · 4T2025 · pág. 1"],
            "citacoes": [
                {
                    "empresa": "BANCO",
                    "documento": "documento",
                    "trimestre": "4T2025",
                    "pagina": 1,
                }
            ],
            "trechos_recuperados": ["Trecho público do documento."],
            "provedor": PROVEDOR_LLM,
            "modelo": "modelo-teste",
            "gabarito": "Resposta esperada",
            "fingerprint": fingerprint,
            "run_id": "run-teste",
            "conjunto": "teste",
            "validacao_automatica": True,
            "pergunta_id": "TSTF001",
            "estrategia": ESTRATEGIA_DEMO,
        }
    }


def _gravar_json(caminho: Path, objeto: dict) -> None:
    caminho.write_text(json.dumps(objeto), encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolar_validacao_material(monkeypatch):
    """Isola o cache unitário do índice e do checkpoint integrais do workspace."""
    import src.auditoria as auditoria

    monkeypatch.setattr(
        app,
        "validar_estado_material_atual",
        lambda config, perguntas, componentes: None,
    )
    monkeypatch.setattr(
        auditoria,
        "_validar_metricas_contra_checkpoint",
        lambda metricas, perguntas, fingerprint, caminho, config: None,
    )

    def carregar_checkpoint_sintetico(caminho, fingerprint):
        caminho_cache = Path(caminho).parent / "respostas_cacheadas.json"
        return json.loads(caminho_cache.read_text(encoding="utf-8"))

    monkeypatch.setattr(app, "_carregar_checkpoint", carregar_checkpoint_sintetico)
    monkeypatch.setattr(
        app,
        "_construir_cache_demo",
        lambda perguntas, itens, provedor, **kwargs: itens,
    )


def test_cache_demo_exige_metricas_completas_e_mesmo_fingerprint(tmp_path):
    caminho_cache = tmp_path / "respostas_cacheadas.json"
    caminho_metricas = tmp_path / "metricas_teste.json"
    cache = _cache()
    _gravar_json(caminho_cache, cache)
    _gravar_json(caminho_metricas, _metricas(cache))

    assert app.carregar_cache_demo(caminho_cache, caminho_metricas) == cache

    outros_componentes = {"fixture": "outra-rodada-material"}
    _gravar_json(
        caminho_metricas,
        _metricas(cache, componentes=outros_componentes),
    )
    with pytest.raises(ValueError, match="automaticamente validada"):
        app.carregar_cache_demo(caminho_cache, caminho_metricas)

    _gravar_json(caminho_metricas, _metricas(cache, status="parcial"))
    with pytest.raises(ValueError, match="Status das métricas"):
        app.carregar_cache_demo(caminho_cache, caminho_metricas)


def test_cache_demo_e_relido_e_rejeita_rodada_parcial(tmp_path):
    caminho_cache = tmp_path / "respostas_cacheadas.json"
    caminho_metricas = tmp_path / "metricas_teste.json"
    cache_primeiro = _cache(resposta="Primeira")
    _gravar_json(caminho_metricas, _metricas(cache_primeiro))
    _gravar_json(caminho_cache, cache_primeiro)
    assert app.carregar_cache_demo(caminho_cache, caminho_metricas)[
        "Qual foi o resultado?"
    ]["resposta"] == "Primeira"

    cache_segundo = _cache(resposta="Segunda")
    _gravar_json(caminho_cache, cache_segundo)
    _gravar_json(caminho_metricas, _metricas(cache_segundo))
    assert app.carregar_cache_demo(caminho_cache, caminho_metricas)[
        "Qual foi o resultado?"
    ]["resposta"] == "Segunda"

    metricas_parciais = _metricas(cache_segundo)
    metricas_parciais["semantica"]["n_itens"] = 44
    _gravar_json(caminho_metricas, metricas_parciais)
    with pytest.raises(ValueError, match="E0–E3.*45 respostas"):
        app.carregar_cache_demo(caminho_cache, caminho_metricas)


def test_cache_demo_rejeita_adulteracao_posterior_ao_hash_auditado(tmp_path):
    caminho_cache = tmp_path / "respostas_cacheadas.json"
    caminho_metricas = tmp_path / "metricas_teste.json"
    cache_auditado = _cache(resposta="Resposta auditada")
    _gravar_json(caminho_cache, cache_auditado)
    _gravar_json(caminho_metricas, _metricas(cache_auditado))

    cache_adulterado = _cache(resposta="Resposta modificada após a auditoria")
    _gravar_json(caminho_cache, cache_adulterado)

    with pytest.raises(ValueError, match="diverge do hash auditado"):
        app.carregar_cache_demo(caminho_cache, caminho_metricas)


def test_cache_demo_rejeita_estado_material_alterado(monkeypatch, tmp_path):
    caminho_cache = tmp_path / "respostas_cacheadas.json"
    caminho_metricas = tmp_path / "metricas_teste.json"
    cache = _cache()
    _gravar_json(caminho_cache, cache)
    _gravar_json(caminho_metricas, _metricas(cache))

    def falhar_por_material(config, perguntas, componentes):
        assert componentes == COMPONENTES_FINGERPRINT
        assert len(perguntas) == 45
        assert all(pergunta.conjunto == "teste" for pergunta in perguntas)
        raise ValueError("Estado material atual diverge da rodada auditada.")

    monkeypatch.setattr(app, "validar_estado_material_atual", falhar_por_material)

    with pytest.raises(ValueError, match="Estado material atual diverge"):
        app.carregar_cache_demo(caminho_cache, caminho_metricas)


def test_cache_demo_fail_closed_enquanto_auditoria_manual_esta_pendente(
    tmp_path,
):
    caminho_cache = tmp_path / "respostas_cacheadas.json"
    caminho_metricas = tmp_path / "metricas_teste.json"
    cache = _cache()
    _gravar_json(caminho_cache, cache)
    metricas = _metricas(cache, status="auditoria_manual_pendente")
    metricas["_meta"]["groundedness_manual_15"] = "pendente"
    metricas["_meta"]["estabilidade_10x3"] = "pendente"
    _gravar_json(caminho_metricas, metricas)

    with pytest.raises(ValueError, match="Status das métricas"):
        app.carregar_cache_demo(caminho_cache, caminho_metricas)

    metricas["_meta"]["status"] = "completa"
    _gravar_json(caminho_metricas, metricas)
    with pytest.raises(ValueError, match="Resultados das auditorias finais"):
        app.carregar_cache_demo(caminho_cache, caminho_metricas)

    metricas["_meta"]["groundedness_manual_15"] = "concluida"
    metricas["_meta"]["estabilidade_10x3"] = "concluida"
    _gravar_json(caminho_metricas, metricas)
    assert app.carregar_cache_demo(caminho_cache, caminho_metricas) == cache

    metricas["_meta"]["status"] = "automatica_completa"
    _gravar_json(caminho_metricas, metricas)
    with pytest.raises(ValueError, match="Status das métricas"):
        app.carregar_cache_demo(caminho_cache, caminho_metricas)


def test_cache_demo_rejeita_groundedness_abaixo_da_meta(tmp_path):
    caminho_cache = tmp_path / "respostas_cacheadas.json"
    caminho_metricas = tmp_path / "metricas_teste.json"
    cache = _cache()
    _gravar_json(caminho_cache, cache)
    metricas = _metricas(cache)
    metricas["_meta"]["groundedness_manual_score"] = 0.89
    _gravar_json(caminho_metricas, metricas)

    with pytest.raises(ValueError, match="Resultados das auditorias finais"):
        app.carregar_cache_demo(caminho_cache, caminho_metricas)


def test_pipeline_live_carrega_indice_vetorial_e_bm25_sob_o_mesmo_lock(
    monkeypatch, tmp_path
):
    import src.bloqueio as bloqueio
    import src.config as modulo_config
    import src.geracao as geracao
    import src.indexacao as indexacao
    import src.recuperacao as recuperacao

    eventos: list[str] = []
    estado = {"bloqueado": False}
    dir_indice = tmp_path / "indice"
    provedor_embeddings = object()
    indice_chroma = (object(), [object()])
    indice_bm25 = (object(), [object()])
    provedor_llm = object()

    @contextmanager
    def lock_falso(caminho, recurso):
        assert caminho == tmp_path / ".indice.lock"
        assert "snapshot" in recurso
        estado["bloqueado"] = True
        eventos.append("lock")
        try:
            yield
        finally:
            eventos.append("unlock")
            estado["bloqueado"] = False

    def exigir_lock(nome, retorno):
        def funcao(*args, **kwargs):
            assert estado["bloqueado"] is True
            eventos.append(nome)
            return retorno

        return funcao

    class RecuperadorFalso:
        def __init__(self, config, **kwargs):
            assert estado["bloqueado"] is True
            assert kwargs == {
                "indice_chroma": indice_chroma,
                "indice_bm25": indice_bm25,
                "provedor_embeddings": provedor_embeddings,
                "hash_corpus_esperado": "c" * 64,
            }
            eventos.append("recuperador")

    monkeypatch.setattr(modulo_config, "DIR_INDICE_VETORIAL", dir_indice)
    monkeypatch.setattr(bloqueio, "bloqueio_exclusivo", lock_falso)
    monkeypatch.setattr(
        indexacao,
        "fabricar_provedor_embeddings",
        exigir_lock("provedor_embeddings", provedor_embeddings),
    )
    monkeypatch.setattr(
        indexacao,
        "calcular_hash_corpus_atual_para_indice",
        exigir_lock("hash", "c" * 64),
    )
    monkeypatch.setattr(
        indexacao,
        "carregar_indice_chroma",
        exigir_lock("chroma", indice_chroma),
    )
    monkeypatch.setattr(
        indexacao,
        "carregar_indice_bm25",
        exigir_lock("bm25", indice_bm25),
    )
    monkeypatch.setattr(recuperacao, "Recuperador", RecuperadorFalso)
    monkeypatch.setattr(geracao, "fabricar_provedor_llm", lambda config: provedor_llm)
    monkeypatch.setattr(app, "config", Config())

    recuperador_criado, llm_criado, estrategia = app._construir_pipeline_ao_vivo()

    assert isinstance(recuperador_criado, RecuperadorFalso)
    assert llm_criado is provedor_llm
    assert estrategia == Estrategia.SEMANTICA
    assert eventos == [
        "lock",
        "provedor_embeddings",
        "hash",
        "chroma",
        "bm25",
        "recuperador",
        "unlock",
    ]


def test_pipeline_live_aborta_mismatch_ocr_antes_de_provedores(
    monkeypatch, tmp_path
):
    import src.bloqueio as bloqueio
    import src.config as modulo_config
    import src.geracao as geracao
    import src.indexacao as indexacao

    @contextmanager
    def lock_falso(*_):
        yield

    esperada = indexacao.IdentidadeExtracaoIndice("pdfplumber")
    atual = indexacao.IdentidadeExtracaoIndice(
        "mistral_overlay", "a" * 64, "b" * 64
    )
    monkeypatch.setattr(
        modulo_config, "DIR_INDICE_VETORIAL", tmp_path / "indice"
    )
    monkeypatch.setattr(bloqueio, "bloqueio_exclusivo", lock_falso)
    monkeypatch.setattr(
        indexacao, "calcular_identidade_extracao", lambda *_: atual
    )
    monkeypatch.setattr(
        indexacao,
        "fabricar_provedor_embeddings",
        lambda *_: pytest.fail("mismatch deve preceder provedor de embeddings"),
    )
    monkeypatch.setattr(
        geracao,
        "fabricar_provedor_llm",
        lambda *_: pytest.fail("mismatch deve preceder a LLM"),
    )
    monkeypatch.setattr(app, "config", Config())

    with pytest.raises(RuntimeError, match="identidade OCR mudou"):
        app._construir_pipeline_ao_vivo(esperada)


class _RecuperadorFalso:
    def __init__(self, recuperados=()):
        self.recuperados = list(recuperados)

    def recuperar(self, pergunta, estrategia):
        return self.recuperados


class _ProvedorFalso:
    custo_auditavel = True

    def __init__(self, estimativa=0.25):
        self.estimativa = estimativa
        self.prompts = []

    def estimar_custo_maximo(self, prompt_sistema, prompt_usuario):
        self.prompts.append((prompt_sistema, prompt_usuario))
        return self.estimativa


def test_closed_book_usa_prompt_e_modo_corretos(monkeypatch):
    import src.geracao as geracao
    from src.indexacao import calcular_identidade_extracao

    provedor = _ProvedorFalso(0.0)
    chamadas = []
    identidades_cache = []

    def gerar_falso(*args, **kwargs):
        chamadas.append((args, kwargs))
        return (
            SimpleNamespace(
                recusa=True,
                motivo_recusa="controle sem fontes",
                resposta=None,
                citacoes=(),
            ),
            SimpleNamespace(custo_usd=0.0, modelo="modelo-falso"),
        )

    config_app = replace(Config(), estrategia_padrao="closed_book")
    monkeypatch.setattr(app, "config", config_app)
    monkeypatch.setattr(
        app,
        "_pipeline_ao_vivo",
        lambda identidade: identidades_cache.append(identidade)
        or (_RecuperadorFalso(), provedor, Estrategia.CLOSED_BOOK),
    )
    monkeypatch.setattr(geracao, "gerar_resposta", gerar_falso)

    resposta = app.responder_pergunta_livre("Qual foi o resultado?")

    assert resposta["custo_usd"] == 0.0
    assert provedor.prompts[0][0] == geracao.PROMPT_SISTEMA_CLOSED_BOOK
    assert "<INICIO_TRECHOS>" not in provedor.prompts[0][1]
    assert chamadas[0][1]["modo_closed_book"] is True
    # O app tem de passar a identidade de extração ATUAL para a chave do cache
    # do pipeline — é o que impede servir um índice construído com outro
    # extrator depois de trocar EXTRATOR (RNF09).
    assert identidades_cache == [calcular_identidade_extracao(config_app)]


def test_falha_apos_inicio_da_geracao_carrega_reserva_de_custo(monkeypatch):
    import src.geracao as geracao

    provedor = _ProvedorFalso(0.25)
    monkeypatch.setattr(app, "config", Config())
    monkeypatch.setattr(
        app,
        "_pipeline_ao_vivo",
        lambda identidade: (
            _RecuperadorFalso(),
            provedor,
            Estrategia.SEMANTICA,
        ),
    )

    def falhar(*args, **kwargs):
        raise TimeoutError("falha sintética sem rede")

    monkeypatch.setattr(geracao, "gerar_resposta", falhar)

    with pytest.raises(app.FalhaConsultaAoVivo) as capturada:
        app.responder_pergunta_livre(
            "Qual foi o resultado?", orcamento_restante_usd=0.30
        )

    assert capturada.value.custo_reservado_usd == pytest.approx(0.25)
    assert app._contabilizar_reserva_falha(
        0.10, capturada.value, 1.0
    ) == pytest.approx(0.35)


def test_trecho_recuperado_e_redigido_antes_de_ser_exposto(monkeypatch):
    import src.geracao as geracao

    chunk = Chunk(
        id="BANCO_4T2025_doc_0001",
        empresa="ITAU",
        trimestre="4T2025",
        documento="doc",
        pagina_inicio=1,
        pagina_fim=1,
        posicao_no_documento=1,
        texto=(
            "[ITAU | doc | 4T2025 | pág. 1]\n"
            "Assinado por Pessoa Exemplo CPF 123.456.789-00; "
            "contato pessoa@example.com."
        ),
    )
    recuperado = SimpleNamespace(chunk=chunk)
    provedor = _ProvedorFalso(0.0)
    monkeypatch.setattr(app, "config", Config())
    monkeypatch.setattr(
        app,
        "_pipeline_ao_vivo",
        lambda identidade: (
            _RecuperadorFalso([recuperado]),
            provedor,
            Estrategia.SEMANTICA,
        ),
    )
    monkeypatch.setattr(
        geracao,
        "gerar_resposta",
        lambda *args, **kwargs: (
            SimpleNamespace(
                recusa=True,
                motivo_recusa="sem evidência suficiente",
                resposta=None,
                citacoes=(),
            ),
            SimpleNamespace(custo_usd=0.0, modelo="modelo-falso"),
        ),
    )

    item = app.responder_pergunta_livre("Qual foi o resultado?")
    trecho = item["fontes"][0]["trecho"]
    assert "123.456.789-00" not in trecho
    assert "pessoa@example.com" not in trecho
    assert "Pessoa Exemplo" not in trecho
    assert "REDIGIDO" in trecho


def test_sidebar_descreve_o_corpus_sem_ranking_mercadologico():
    teste = AppTest.from_file("app_streamlit.py", default_timeout=20).run()
    assert not teste.exception
    textos = [item.value for item in teste.caption]
    assert any("cinco bancos do corpus" in texto for texto in textos)
    assert all("5 maiores bancos" not in texto for texto in textos)
    documentacao = " ".join((app.__doc__ or "").split())
    assert "teto no lado do provedor" not in documentacao
    assert "não sobrevive a um encerramento abrupto" in documentacao
