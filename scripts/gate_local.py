"""Gate L1 — prova mínima do ramo de inferência 100% local.

Valida embeddings e geração estruturada usando os provedores configurados,
sem acessar Azure ou qualquer API paga. O Gate G1 de Azure permanece em
``scripts/gate.py`` e só será executado no pré-deploy.

Uso:
    python scripts/gate_local.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.config import Config, carregar_config  # noqa: E402
from src.geracao import (  # noqa: E402
    PROMPT_SISTEMA,
    VERSAO_PROMPT,
    fabricar_provedor_llm,
)
from src.indexacao import fabricar_provedor_embeddings  # noqa: E402
from src.ollama import (  # noqa: E402
    endpoint_ollama_e_loopback,
    obter_versao_ollama,
    resolver_identidade_modelo_ollama,
)

CAMINHO_RELATORIO = RAIZ / "resultados" / "gate_local.md"
PROVEDOR_LOCAL = "ollama"


def _sanitizar_evidencia(texto: str) -> str:
    """Mantém a tabela Markdown válida e evita relatórios gigantes."""
    return (
        texto.replace("|", "\\|").replace("`", "\\`").replace("\n", " ")[:700]
    )


def _testar_runtime(config: Config) -> tuple[bool, str]:
    """Prova que o gate chamará somente um daemon Ollama em loopback."""
    try:
        if config.llm_provider != PROVEDOR_LOCAL:
            raise RuntimeError(f"LLM_PROVIDER não local: {config.llm_provider!r}")
        if config.embedding_provider != PROVEDOR_LOCAL:
            raise RuntimeError(
                f"EMBEDDING_PROVIDER não local: {config.embedding_provider!r}"
            )
        if not endpoint_ollama_e_loopback(config.ollama_base_url):
            raise RuntimeError(
                "Gate L1 aceita somente OLLAMA_BASE_URL em loopback; "
                f"recebido={config.ollama_base_url!r}"
            )
        versao = obter_versao_ollama(
            config.ollama_base_url, config.ollama_timeout_s
        )
        endpoint = urlsplit(config.ollama_base_url)
        return True, f"Ollama {versao}; endpoint={endpoint.scheme}://{endpoint.netloc} (loopback)"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _validar_resposta_fundamentada(objeto: object) -> None:
    if not isinstance(objeto, dict):
        raise RuntimeError("resposta do LLM não é um objeto JSON")
    campos = {"resposta", "recusa", "motivo_recusa", "citacoes"}
    if set(objeto) != campos:
        raise RuntimeError(
            f"campos JSON divergentes: esperado={sorted(campos)}, "
            f"recebido={sorted(objeto)}"
        )
    if objeto["recusa"] is not False:
        raise RuntimeError(f"resposta fundamentada foi recusada: {objeto!r}")
    if not isinstance(objeto["resposta"], str) or "26,6%" not in objeto["resposta"]:
        raise RuntimeError(f"valor esperado 26,6% ausente: {objeto['resposta']!r}")
    if objeto["motivo_recusa"] is not None:
        raise RuntimeError("resposta fundamentada trouxe motivo_recusa")
    citacao_esperada = {
        "empresa": "BTG",
        "documento": "btg_release_1T2026",
        "trimestre": "1T2026",
        "pagina": 6,
    }
    if objeto["citacoes"] != [citacao_esperada]:
        raise RuntimeError(
            f"citação deve ser única e exata: recebido={objeto['citacoes']!r}"
        )


def _validar_resposta_recusa(objeto: object) -> None:
    if not isinstance(objeto, dict):
        raise RuntimeError("recusa do LLM não é um objeto JSON")
    campos = {"resposta", "recusa", "motivo_recusa", "citacoes"}
    if set(objeto) != campos:
        raise RuntimeError(
            f"campos JSON divergentes na recusa: esperado={sorted(campos)}, "
            f"recebido={sorted(objeto)}"
        )
    if objeto.get("recusa") is not True:
        raise RuntimeError(f"pergunta sem evidência não foi recusada: {objeto!r}")
    if objeto.get("resposta") is not None:
        raise RuntimeError("recusa deve ter resposta=null")
    if objeto.get("citacoes") != []:
        raise RuntimeError("recusa deve ter citacoes=[]")
    motivo = objeto.get("motivo_recusa")
    if not isinstance(motivo, str) or not motivo.strip():
        raise RuntimeError("recusa deve explicar motivo_recusa")


def _validar_telemetria(resposta, modelo_configurado: str) -> None:
    modelos_aceitos = {modelo_configurado}
    if ":" not in modelo_configurado:
        modelos_aceitos.add(f"{modelo_configurado}:latest")
    if resposta.modelo not in modelos_aceitos:
        raise RuntimeError(
            f"modelo inesperado: esperado={modelos_aceitos}, recebido={resposta.modelo!r}"
        )
    if resposta.uso.tokens_entrada <= 0 or resposta.uso.tokens_saida <= 0:
        raise RuntimeError(f"contagem de tokens inválida: {resposta.uso!r}")
    if resposta.uso.custo_usd != 0.0:
        raise RuntimeError(f"custo de API local deve ser zero: {resposta.uso!r}")


def _testar_embeddings(config: Config) -> tuple[bool, str]:
    if config.embedding_provider != PROVEDOR_LOCAL:
        return False, f"provedor não local: {config.embedding_provider!r}"
    try:
        inicio = perf_counter()
        provedor = fabricar_provedor_embeddings(config)
        matriz = provedor.embedar(
            ["margem financeira", "carteira de crédito ampliada"]
        )
        latencia_s = perf_counter() - inicio
        esperado = (2, provedor.dimensao)
        if matriz.shape != esperado:
            raise RuntimeError(
                f"shape inesperado: esperado={esperado}, recebido={matriz.shape}"
            )
        normas = np.linalg.norm(matriz, axis=1)
        if not np.isfinite(matriz).all():
            raise RuntimeError("embeddings contêm valores não finitos")
        if not np.allclose(normas, 1.0, atol=1e-5):
            raise RuntimeError(f"vetores não normalizados: normas={normas.tolist()}")
        if np.allclose(matriz[0], matriz[1]):
            raise RuntimeError("textos distintos produziram embeddings idênticos")
        identidade = provedor.identidade_modelo()
        return True, (
            f"{provedor.nome}/{identidade}; dimensão={provedor.dimensao}; "
            f"2 textos em {latencia_s:.3f}s; normas L2=1"
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _testar_llm(config: Config) -> tuple[bool, str]:
    if config.llm_provider != PROVEDOR_LOCAL:
        return False, f"provedor não local: {config.llm_provider!r}"
    try:
        provedor = fabricar_provedor_llm(config)
        prompt_usuario = """TRECHOS:
[BTG | btg_release_1T2026 | 1T2026 | pág. 6]
O ROAE ajustado anualizado foi de 26,6% no 1T2026.

PERGUNTA:
Qual foi o ROAE ajustado anualizado do BTG no 1T2026?"""
        resposta = provedor.gerar(PROMPT_SISTEMA, prompt_usuario, temperatura=0.0)
        objeto = json.loads(resposta.texto)
        _validar_resposta_fundamentada(objeto)
        _validar_telemetria(resposta, config.ollama_modelo_llm)

        prompt_recusa = """TRECHOS:
[BTG | btg_release_1T2026 | 1T2026 | pág. 6]
O ROAE ajustado anualizado foi de 26,6% no 1T2026.

PERGUNTA:
Qual foi a receita do Nubank no 1T2026?"""
        recusa = provedor.gerar(PROMPT_SISTEMA, prompt_recusa, temperatura=0.0)
        _validar_resposta_recusa(json.loads(recusa.texto))
        _validar_telemetria(recusa, config.ollama_modelo_llm)

        identidade = resolver_identidade_modelo_ollama(
            config.ollama_base_url,
            config.ollama_modelo_llm,
            config.ollama_timeout_s,
        )
        tokens_entrada = resposta.uso.tokens_entrada + recusa.uso.tokens_entrada
        tokens_saida = resposta.uso.tokens_saida + recusa.uso.tokens_saida
        latencia_s = resposta.uso.latencia_s + recusa.uso.latencia_s
        return True, (
            f"{provedor.nome}/{identidade}; resposta 26,6% com citação exata + "
            f"recusa RN02 válidas; tokens={tokens_entrada}+{tokens_saida}; "
            f"latência ponta a ponta={latencia_s:.3f}s; custo de API=US$ 0,00"
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def executar_gate_local(config: Config | None = None) -> bool:
    config = config or carregar_config()
    inicio_utc = datetime.now(timezone.utc)
    runtime_ok, runtime_evidencia = _testar_runtime(config)
    if runtime_ok:
        emb_ok, emb_evidencia = _testar_embeddings(config)
        llm_ok, llm_evidencia = _testar_llm(config)
    else:
        emb_ok = llm_ok = False
        emb_evidencia = llm_evidencia = "não executado: runtime local inválido"
    passou = runtime_ok and emb_ok and llm_ok
    fim_utc = datetime.now(timezone.utc)

    CAMINHO_RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_RELATORIO.write_text(
        f"""# Gate L1 — inferência local

- **Início (UTC):** {inicio_utc.isoformat()}
- **Fim (UTC):** {fim_utc.isoformat()}
- **Resultado:** {"✅ PASSOU" if passou else "❌ FALHOU"}
- **Chamadas externas pagas/Azure:** não realizadas pelo Gate L1
- **Configuração:** prompt={VERSAO_PROMPT}; temperatura=0; max_tokens={config.ollama_max_tokens}; lote_embeddings={config.ollama_embedding_batch_size}

## Evidências

| Teste | Status | Evidência |
|-------|--------|-----------|
| Runtime local | {"✅" if runtime_ok else "❌"} | `{_sanitizar_evidencia(runtime_evidencia)}` |
| Embeddings locais | {"✅" if emb_ok else "❌"} | `{_sanitizar_evidencia(emb_evidencia)}` |
| LLM local | {"✅" if llm_ok else "❌"} | `{_sanitizar_evidencia(llm_evidencia)}` |

## Decisão de ramo

**Ramo local-first ativo:** `LLM_PROVIDER={config.llm_provider}` e
`EMBEDDING_PROVIDER={config.embedding_provider}`. O Gate G1 de Azure fica
deliberadamente adiado até o pré-deploy, após testes, avaliação e interface
funcionarem localmente.

> Evidência regenerável por `python scripts/gate_local.py`. O ramo Ollama não
> exige nem envia credenciais reais ou segredos.
> As latências refletem o estado de cache encontrado no daemon; o gate não
> força cold ou warm start.
""",
        encoding="utf-8",
    )
    print(f"Gate L1: {'PASSOU' if passou else 'FALHOU'}")
    print(f"Relatório: {CAMINHO_RELATORIO}")
    return passou


if __name__ == "__main__":
    raise SystemExit(0 if executar_gate_local() else 1)
