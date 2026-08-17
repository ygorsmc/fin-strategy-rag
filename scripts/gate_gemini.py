"""Gate Gemini — smoke test explícito do provedor de geração via API.

Este gate faz duas chamadas externas. Ele só as inicia com o opt-in literal
``--permitir-api-paga``, reserva um teto conservador para a execução e mantém
um journal append-only sem prompts, respostas ou credenciais.

Uso:
    python scripts/gate_gemini.py --permitir-api-paga
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts.gate_seguranca import (  # noqa: E402
    custo_valido,
    registrar_evento,
    resumir_excecao,
    sanitizar_evidencia,
)
from src.config import Config, carregar_config  # noqa: E402
from src.geracao import (  # noqa: E402
    PROMPT_SISTEMA,
    VERSAO_PROMPT,
    ProvedorLLM,
    RespostaBrutaLLM,
    fabricar_provedor_llm,
)

CAMINHO_RELATORIO = RAIZ / "resultados" / "gate_gemini.md"
CAMINHO_JOURNAL = RAIZ / "resultados" / "gate_gemini_execucoes.jsonl"


class ErroPreflightGate(ValueError):
    """Configuração/custo local recusou a execução antes da próxima chamada."""


def _segredos(config: Config) -> tuple[str, ...]:
    return tuple(
        valor
        for valor in (
            config.gemini_api_key,
            config.azure_openai_api_key,
            config.openai_api_key,
            config.deepseek_api_key,
        )
        if valor
    )


def _validar_fundamentada(objeto: object) -> None:
    campos = {"resposta", "recusa", "motivo_recusa", "citacoes"}
    if not isinstance(objeto, dict) or set(objeto) != campos:
        raise RuntimeError("contrato JSON divergente na resposta fundamentada")

    citacao = {
        "empresa": "BTG",
        "documento": "btg_release_1T2026",
        "trimestre": "1T2026",
        "pagina": 6,
    }
    if not (
        objeto.get("recusa") is False
        and isinstance(objeto.get("resposta"), str)
        and "26,6%" in objeto["resposta"]
        and objeto.get("motivo_recusa") is None
        and objeto.get("citacoes") == [citacao]
    ):
        raise RuntimeError("resposta fundamentada não satisfez o contrato do gate")


def _validar_recusa(objeto: object) -> None:
    campos = {"resposta", "recusa", "motivo_recusa", "citacoes"}
    if not isinstance(objeto, dict) or set(objeto) != campos:
        raise RuntimeError("contrato JSON divergente na recusa")
    if (
        objeto.get("resposta") is not None
        or objeto.get("recusa") is not True
        or objeto.get("citacoes") != []
        or not isinstance(objeto.get("motivo_recusa"), str)
        or not objeto["motivo_recusa"].strip()
    ):
        raise RuntimeError("recusa não satisfez o contrato RN02")


def _prompt(pergunta: str) -> str:
    return f"""TRECHOS:
[BTG | btg_release_1T2026 | 1T2026 | pág. 6]
O ROAE ajustado anualizado foi de 26,6% no 1T2026.

PERGUNTA:
{pergunta}"""


def _chamadas_do_gate() -> tuple[tuple[str, str, Callable[[object], None]], ...]:
    return (
        (
            "resposta_fundamentada",
            _prompt("Qual foi o ROAE ajustado anualizado do BTG no 1T2026?"),
            _validar_fundamentada,
        ),
        (
            "recusa_rn02",
            _prompt("Qual foi a receita do Nubank no 1T2026?"),
            _validar_recusa,
        ),
    )


def _preflight_custo(
    provedor: ProvedorLLM,
    config: Config,
) -> tuple[tuple[float, ...], float]:
    """Reserva o pior caso das duas chamadas antes de iniciar a primeira."""
    if not provedor.custo_auditavel:
        raise ErroPreflightGate("provedor Gemini sem custo auditável")
    if (
        config.gemini_preco_entrada_usd_milhao == 0
        and config.gemini_preco_saida_usd_milhao == 0
    ):
        raise ErroPreflightGate(
            "preços Gemini zerados; o gate não declarará custo zero"
        )

    estimativas: list[float] = []
    for _, prompt_usuario, _ in _chamadas_do_gate():
        estimativa = provedor.estimar_custo_maximo(PROMPT_SISTEMA, prompt_usuario)
        if not custo_valido(estimativa):
            raise ErroPreflightGate(
                "provedor não forneceu estimativa conservadora válida"
            )
        estimativas.append(float(estimativa))
    total = sum(estimativas)
    if total > config.orcamento_teto_usd:
        raise ErroPreflightGate(
            "preflight recusado: pior caso das duas chamadas "
            f"(US$ {total:.6f}) excede ORCAMENTO_TETO_USD "
            f"(US$ {config.orcamento_teto_usd:.6f})"
        )
    return tuple(estimativas), total


def _executar_chamada(
    provedor: ProvedorLLM,
    *,
    nome: str,
    prompt_usuario: str,
    validar: Callable[[object], None],
    estimativa_maxima: float,
    execucao_id: str,
    config: Config,
    estado: dict[str, float | int],
) -> RespostaBrutaLLM:
    chamada_id = uuid.uuid4().hex
    registrar_evento(
        CAMINHO_JOURNAL,
        {
            "evento": "chamada_iniciada",
            "execucao_id": execucao_id,
            "chamada_id": chamada_id,
            "alvo": nome,
            "provedor": "gemini",
            "modelo_configurado": sanitizar_evidencia(
                config.gemini_modelo_llm,
                segredos=_segredos(config),
            ),
            "custo_maximo_usd": estimativa_maxima,
        },
    )
    estado["iniciadas"] += 1
    resposta: RespostaBrutaLLM | None = None
    try:
        resposta = provedor.gerar(
            PROMPT_SISTEMA,
            prompt_usuario,
            temperatura=0.0,
        )
        if resposta.uso.tokens_entrada <= 0 or resposta.uso.tokens_saida <= 0:
            raise RuntimeError("telemetria de tokens ausente ou inválida")
        if not custo_valido(resposta.uso.custo_usd):
            raise RuntimeError("telemetria de custo ausente ou inválida")
        validar(json.loads(resposta.texto))
    except Exception as exc:
        observado = None
        if resposta is not None and custo_valido(resposta.uso.custo_usd):
            observado = float(resposta.uso.custo_usd)
            estado["custo_observado_usd"] += observado
        debito = observado if observado is not None else estimativa_maxima
        estado["debito_conservador_usd"] += debito
        estado["falhas"] += 1
        registrar_evento(
            CAMINHO_JOURNAL,
            {
                "evento": "chamada_falhou",
                "execucao_id": execucao_id,
                "chamada_id": chamada_id,
                "alvo": nome,
                "erro": resumir_excecao(exc, segredos=_segredos(config)),
                "custo_observado_usd": observado,
                "debito_conservador_usd": debito,
                "custo_maximo_usd": estimativa_maxima,
            },
        )
        raise

    custo = float(resposta.uso.custo_usd)
    estado["concluidas"] += 1
    estado["custo_observado_usd"] += custo
    estado["debito_conservador_usd"] += custo
    registrar_evento(
        CAMINHO_JOURNAL,
        {
            "evento": "chamada_concluida",
            "execucao_id": execucao_id,
            "chamada_id": chamada_id,
            "alvo": nome,
            "tokens_entrada": resposta.uso.tokens_entrada,
            "tokens_saida": resposta.uso.tokens_saida,
            "custo_observado_usd": custo,
            "debito_conservador_usd": custo,
        },
    )
    return resposta


def executar_gate_gemini(
    config: Config | None = None,
    *,
    permitir_api_paga: bool = False,
) -> bool:
    """Executa o gate somente após opt-in explícito e preflight de custo."""
    if not permitir_api_paga:
        print(
            "Gate Gemini não executado: confirme a cobrança com "
            "--permitir-api-paga.",
            file=sys.stderr,
        )
        return False

    config = config or carregar_config()
    inicio_utc = datetime.now(timezone.utc)
    execucao_id = uuid.uuid4().hex
    estado: dict[str, float | int] = {
        "iniciadas": 0,
        "concluidas": 0,
        "falhas": 0,
        "custo_observado_usd": 0.0,
        "debito_conservador_usd": 0.0,
    }
    passou = False
    evidencia = ""
    preflight_maximo: float | None = None
    inicio = perf_counter()
    try:
        if config.llm_provider != "gemini":
            raise ErroPreflightGate(
                f"LLM_PROVIDER deve ser gemini: recebido={config.llm_provider!r}"
            )
        faltando = [
            nome
            for nome, valor in (
                ("GEMINI_API_KEY/GOOGLE_API_KEY", config.gemini_api_key),
                ("GEMINI_MODELO_LLM", config.gemini_modelo_llm),
                ("GEMINI_BASE_URL", config.gemini_base_url),
            )
            if not valor
        ]
        if faltando:
            raise ErroPreflightGate(f"variáveis Gemini ausentes: {faltando}")
        provedor = fabricar_provedor_llm(config)
        estimativas, preflight_maximo = _preflight_custo(provedor, config)
        registrar_evento(
            CAMINHO_JOURNAL,
            {
                "evento": "preflight_aprovado",
                "execucao_id": execucao_id,
                "provedor": "gemini",
                "versao_prompt": VERSAO_PROMPT,
                "n_chamadas": len(estimativas),
                "custo_maximo_execucao_usd": preflight_maximo,
                "orcamento_teto_execucao_usd": config.orcamento_teto_usd,
            },
        )

        respostas: list[RespostaBrutaLLM] = []
        chamadas = _chamadas_do_gate()
        for indice, ((nome, prompt_usuario, validar), estimativa) in enumerate(
            zip(chamadas, estimativas, strict=True)
        ):
            reserva_restante = sum(estimativas[indice:])
            if (
                float(estado["debito_conservador_usd"]) + reserva_restante
                > config.orcamento_teto_usd
            ):
                raise ErroPreflightGate(
                    "próxima chamada recusada: custo já debitado mais a reserva "
                    "restante excede ORCAMENTO_TETO_USD"
                )
            respostas.append(
                _executar_chamada(
                    provedor,
                    nome=nome,
                    prompt_usuario=prompt_usuario,
                    validar=validar,
                    estimativa_maxima=estimativa,
                    execucao_id=execucao_id,
                    config=config,
                    estado=estado,
                )
            )
        tokens_entrada = sum(r.uso.tokens_entrada for r in respostas)
        tokens_saida = sum(r.uso.tokens_saida for r in respostas)
        evidencia = (
            "resposta factual/citação + recusa RN02 válidas; "
            f"tokens={tokens_entrada}+{tokens_saida}; "
            f"latência={perf_counter() - inicio:.3f}s"
        )
        passou = True
    except ErroPreflightGate as exc:
        # Erros de preflight são produzidos localmente e podem manter o motivo.
        evidencia = sanitizar_evidencia(str(exc), segredos=_segredos(config))
    except Exception as exc:
        # Mensagens/corpos externos podem refletir prompt ou chave: não persistir.
        evidencia = resumir_excecao(exc, segredos=_segredos(config))

    fim_utc = datetime.now(timezone.utc)
    try:
        registrar_evento(
            CAMINHO_JOURNAL,
            {
                "evento": "execucao_encerrada",
                "execucao_id": execucao_id,
                "resultado": "passou" if passou else "falhou",
                **estado,
            },
        )
    except OSError:
        passou = False
        evidencia = "falha ao persistir o encerramento do journal"

    preflight_texto = (
        f"US$ {preflight_maximo:.6f}"
        if preflight_maximo is not None
        else "não aprovado; nenhuma reserva criada"
    )
    CAMINHO_RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_RELATORIO.write_text(
        f"""# Gate Gemini — geração via API

- **Início (UTC):** {inicio_utc.isoformat()}
- **Fim (UTC):** {fim_utc.isoformat()}
- **Resultado:** {"✅ PASSOU" if passou else "❌ FALHOU"}
- **Azure:** não utilizado
- **Provedor/modelo configurado:** LLM_PROVIDER={config.llm_provider} /
  {sanitizar_evidencia(config.gemini_modelo_llm, segredos=_segredos(config))}
- **Versão do prompt:** {VERSAO_PROMPT}
- **Pior caso reservado no preflight:** {preflight_texto}
- **Teto desta execução:** US$ {config.orcamento_teto_usd:.6f}
- **Chamadas iniciadas/concluídas/falhas:** {estado["iniciadas"]} /
  {estado["concluidas"]} / {estado["falhas"]}
- **Custo observado:** US$ {estado["custo_observado_usd"]:.6f}
- **Débito conservador:** US$ {estado["debito_conservador_usd"]:.6f}

## Evidência sanitizada

{sanitizar_evidencia(evidencia, segredos=_segredos(config))}

O teto acima vale para **uma execução** deste gate; invocá-lo novamente pode
gerar nova cobrança. O journal append-only em
`resultados/gate_gemini_execucoes.jsonl` registra o antes e o depois de cada
chamada sem salvar prompts/respostas. Se o processo morrer após o provedor
responder e antes do segundo registro, o custo fica indeterminado e o pior caso
pré-reservado deve ser tratado como débito. Isso não é garantia exactly-once.

O custo observado usa a telemetria e os preços configurados em
`GEMINI_PRECO_ENTRADA_USD_MILHAO` e
`GEMINI_PRECO_SAIDA_USD_MILHAO`.
""",
        encoding="utf-8",
    )
    print(f"Gate Gemini: {'PASSOU' if passou else 'FALHOU'}")
    print(f"Relatório: {CAMINHO_RELATORIO}")
    return passou


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--permitir-api-paga",
        action="store_true",
        help="confirma explicitamente as duas chamadas externas e seu custo",
    )
    args = parser.parse_args(argv)
    return 0 if executar_gate_gemini(permitir_api_paga=args.permitir_api_paga) else 1


if __name__ == "__main__":
    raise SystemExit(principal())
