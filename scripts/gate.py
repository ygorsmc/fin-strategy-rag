"""Gate G1 — conectividade Azure opcional, somente no pré-deploy.

O gate faz uma chamada mínima de LLM e uma de embeddings. Não cria recursos,
não mede quota/capacidade e só inicia chamadas com ``--permitir-api-paga``.
Como o contrato de configuração não contém preços Azure, ele não finge aplicar
um teto monetário: o journal registra tentativas, mas o custo permanece
indeterminado até conferência no provedor.

Uso:
    python scripts/gate.py --permitir-api-paga
"""

from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts.gate_seguranca import (  # noqa: E402
    registrar_evento,
    resumir_excecao,
    sanitizar_evidencia,
)
from src.config import (  # noqa: E402
    Config,
    carregar_config,
    endpoint_azure_openai_e_oficial,
)
from src.geracao import ProvedorLLM, fabricar_provedor_llm  # noqa: E402
from src.indexacao import ProvedorEmbeddings, fabricar_provedor_embeddings  # noqa: E402

CAMINHO_RELATORIO = RAIZ / "resultados" / "gate.md"
CAMINHO_JOURNAL = RAIZ / "resultados" / "gate_azure_execucoes.jsonl"


def _segredos(config: Config) -> tuple[str, ...]:
    return tuple(
        valor
        for valor in (
            config.azure_openai_api_key,
            config.gemini_api_key,
            config.openai_api_key,
            config.deepseek_api_key,
        )
        if valor
    )


def _preparar_provedores(
    config: Config,
) -> tuple[ProvedorLLM, ProvedorEmbeddings]:
    """Valida os dois alvos e instancia ambos antes de qualquer chamada."""
    faltando = [
        nome
        for nome, valor in (
            ("AZURE_OPENAI_ENDPOINT", config.azure_openai_endpoint),
            ("AZURE_OPENAI_API_KEY", config.azure_openai_api_key),
            ("AZURE_OPENAI_API_VERSION", config.azure_openai_api_version),
            ("AZURE_OPENAI_DEPLOYMENT_LLM", config.azure_openai_deployment_llm),
            (
                "AZURE_OPENAI_DEPLOYMENT_EMBEDDING",
                config.azure_openai_deployment_embedding,
            ),
        )
        if not valor
    ]
    if faltando:
        raise ValueError(f"variáveis Azure ausentes: {faltando}")
    if not endpoint_azure_openai_e_oficial(config.azure_openai_endpoint):
        raise ValueError(
            "AZURE_OPENAI_ENDPOINT deve ser HTTPS, oficial (*.openai.azure.com) "
            "e não conter credenciais"
        )
    config_azure = replace(
        config,
        llm_provider="azure_openai",
        embedding_provider="azure_openai",
    )
    # Os construtores não fazem inferência. Preparar os dois evita cobrar o
    # primeiro alvo e só depois descobrir que o segundo está mal configurado.
    llm = fabricar_provedor_llm(config_azure)
    embeddings = fabricar_provedor_embeddings(config_azure)
    return llm, embeddings


def _executar_alvo(
    *,
    alvo: str,
    chamada: Callable[[], str],
    execucao_id: str,
    config: Config,
    estado: dict[str, int],
) -> str:
    chamada_id = uuid.uuid4().hex
    registrar_evento(
        CAMINHO_JOURNAL,
        {
            "evento": "chamada_iniciada",
            "execucao_id": execucao_id,
            "chamada_id": chamada_id,
            "provedor": "azure_openai",
            "alvo": alvo,
            "custo_observado_usd": None,
            "debito_conservador_usd": None,
        },
    )
    estado["iniciadas"] += 1
    try:
        evidencia = chamada()
    except Exception as exc:
        estado["falhas"] += 1
        registrar_evento(
            CAMINHO_JOURNAL,
            {
                "evento": "chamada_falhou",
                "execucao_id": execucao_id,
                "chamada_id": chamada_id,
                "provedor": "azure_openai",
                "alvo": alvo,
                "erro": resumir_excecao(exc, segredos=_segredos(config)),
                "custo_observado_usd": None,
                "debito_conservador_usd": None,
            },
        )
        raise
    estado["concluidas"] += 1
    registrar_evento(
        CAMINHO_JOURNAL,
        {
            "evento": "chamada_concluida",
            "execucao_id": execucao_id,
            "chamada_id": chamada_id,
            "provedor": "azure_openai",
            "alvo": alvo,
            "custo_observado_usd": None,
            "debito_conservador_usd": None,
        },
    )
    return evidencia


def _chamada_llm(provedor: ProvedorLLM) -> str:
    resposta = provedor.gerar(
        "Responda de forma breve e literal.",
        "Responda apenas: ok",
        temperatura=0.0,
    )
    if (
        not resposta.texto.strip()
        or resposta.uso.tokens_entrada <= 0
        or resposta.uso.tokens_saida <= 0
    ):
        raise RuntimeError("adaptador Azure LLM não devolveu texto/telemetria")
    return (
        f"adaptador {provedor.nome} respondeu; "
        f"tokens={resposta.uso.tokens_entrada}+{resposta.uso.tokens_saida}"
    )


def _chamada_embeddings(provedor: ProvedorEmbeddings) -> str:
    matriz = provedor.embedar(["teste"])
    if matriz.shape != (1, provedor.dimensao):
        raise RuntimeError(
            f"shape inesperado: {matriz.shape}; esperado=(1, {provedor.dimensao})"
        )
    return f"adaptador {provedor.nome} respondeu; dimensão={provedor.dimensao}"


def _ramo_fallback(config: Config) -> str:
    if config.llm_provider == "gemini" and config.gemini_api_key:
        return "Gemini (validar separadamente com gate_gemini.py)"
    if config.llm_provider == "ollama":
        return "Ollama local (validar separadamente com gate_local.py)"
    return f"LLM_PROVIDER={config.llm_provider!r}, sem evidência produzida por este gate"


def executar_gate(
    config: Config | None = None,
    *,
    permitir_api_paga: bool = False,
) -> bool:
    """Executa as duas chamadas Azure somente após confirmação explícita."""
    if not permitir_api_paga:
        print(
            "Gate Azure não executado: confirme possíveis cobranças com "
            "--permitir-api-paga.",
            file=sys.stderr,
        )
        return False

    config = config or carregar_config()
    agora = datetime.now(timezone.utc)
    execucao_id = uuid.uuid4().hex
    estado = {"iniciadas": 0, "concluidas": 0, "falhas": 0}
    llm_ok = emb_ok = False
    llm_evidencia = emb_evidencia = "não executado: preflight incompleto"
    evidencia_geral = ""
    try:
        llm, embeddings = _preparar_provedores(config)
        registrar_evento(
            CAMINHO_JOURNAL,
            {
                "evento": "preflight_aprovado",
                "execucao_id": execucao_id,
                "provedor": "azure_openai",
                "n_chamadas": 2,
                "teto_monetario_aplicavel": False,
                "motivo": "preços Azure ausentes do contrato de configuração",
            },
        )
        try:
            llm_evidencia = _executar_alvo(
                alvo="llm",
                chamada=lambda: _chamada_llm(llm),
                execucao_id=execucao_id,
                config=config,
                estado=estado,
            )
            llm_ok = True
        except Exception as exc:
            llm_evidencia = resumir_excecao(exc, segredos=_segredos(config))

        try:
            emb_evidencia = _executar_alvo(
                alvo="embeddings",
                chamada=lambda: _chamada_embeddings(embeddings),
                execucao_id=execucao_id,
                config=config,
                estado=estado,
            )
            emb_ok = True
        except Exception as exc:
            emb_evidencia = resumir_excecao(exc, segredos=_segredos(config))
    except ValueError as exc:
        evidencia_geral = sanitizar_evidencia(str(exc), segredos=_segredos(config))
    except Exception as exc:
        evidencia_geral = resumir_excecao(exc, segredos=_segredos(config))

    passou = llm_ok and emb_ok
    try:
        registrar_evento(
            CAMINHO_JOURNAL,
            {
                "evento": "execucao_encerrada",
                "execucao_id": execucao_id,
                "resultado": "passou" if passou else "falhou",
                **estado,
                "custo_observado_usd": None,
                "debito_conservador_usd": None,
            },
        )
    except OSError:
        passou = False
        evidencia_geral = "falha ao persistir o encerramento do journal"

    if passou:
        decisao = (
            "**Conectividade dos dois deployments configurados foi observada.** "
            "Isso não ativa Azure no pipeline e não mede quota, capacidade "
            "regional, throughput ou custo."
        )
    else:
        decisao = (
            "**Azure não foi habilitado por este gate.** Perfil alternativo "
            f"declarado: {_ramo_fallback(config)}."
        )

    detalhe_preflight = (
        f"\n\nFalha anterior às chamadas: {evidencia_geral}"
        if evidencia_geral
        else ""
    )
    CAMINHO_RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_RELATORIO.write_text(
        f"""# Gate G1 — conectividade Azure no pré-deploy

- **Data/hora (UTC):** {agora.isoformat()}
- **Resultado:** {"✅ PASSOU" if passou else "❌ FALHOU / não disponível"}
- **Chamadas iniciadas/concluídas/falhas:** {estado["iniciadas"]} /
  {estado["concluidas"]} / {estado["falhas"]}
- **Custo observado:** indeterminado (SDK/adaptador não fornece faturamento)
- **Teto monetário:** não aplicável; preços Azure não estão configurados

## Evidências sanitizadas

| Teste | Status | Evidência |
|-------|--------|-----------|
| Azure OpenAI — LLM | {"✅" if llm_ok else "❌"} | `{sanitizar_evidencia(llm_evidencia, segredos=_segredos(config))}` |
| Azure OpenAI — Embeddings | {"✅" if emb_ok else "❌"} | `{sanitizar_evidencia(emb_evidencia, segredos=_segredos(config))}` |
{detalhe_preflight}

## Decisão

{decisao}

O opt-in confirma possíveis cobranças, mas **não as limita** neste gate. Confira
custos/quota no Azure antes e depois da execução. O journal append-only em
`resultados/gate_azure_execucoes.jsonl` registra o antes e o depois de cada
chamada sem prompts/respostas. Uma interrupção entre a resposta do serviço e o
registro final deixa o custo indeterminado; o journal não garante exactly-once.
""",
        encoding="utf-8",
    )
    print(f"Gate G1: {'PASSOU' if passou else 'FALHOU (fallback documentado)'}")
    print(f"Relatório: {CAMINHO_RELATORIO}")
    return passou


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--permitir-api-paga",
        action="store_true",
        help="confirma explicitamente as duas chamadas Azure e possíveis custos",
    )
    args = parser.parse_args(argv)
    return 0 if executar_gate(permitir_api_paga=args.permitir_api_paga) else 1


if __name__ == "__main__":
    raise SystemExit(principal())
