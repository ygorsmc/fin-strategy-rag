"""Mede a CONCORDÂNCIA entre um LLM-juiz e a auditoria humana já feita (5.15).

O que este script NÃO é: um substituto da guarda RN02 nem da leitura humana.
A spec 5.15/5.23 é explícita — um detector automático de alucinação tem a mesma
fragilidade que está sendo medida, então a auditoria manual continua sendo a
métrica de groundedness reportada. **O resultado de interesse aqui é a
divergência**: a matriz de concordância entre juiz e humano, com os casos
discordantes nomeados.

Por isso ele roda sobre uma auditoria humana **já preenchida**, e nunca sobre
uma pendente: o veredito humano precisa ter sido dado às cegas para que a
concordância signifique alguma coisa. Rodar o juiz antes da leitura ancoraria
o auditor e transformaria a matriz em artefato.

O juiz recebe pergunta, resposta e os trechos recuperados **sem os scores** —
o score enviesaria para o trecho melhor ranqueado, que é justamente o que se
quer testar.

Uso::

    python -m scripts.medir_juiz_groundedness \\
        --auditoria artefatos/resultados_avaliacao/auditoria_groundedness_a0bea525.json \\
        --permitir-api-paga
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.avaliacao import registrar_execucao  # noqa: E402
from src.config import (  # noqa: E402
    DIR_RESULTADOS_AVALIACAO,
    carregar_config,
    exigir_modelo_juiz_deepeval,
)
from src.geracao import LLMGemini  # noqa: E402

PROMPT_SISTEMA = """\
Você audita respostas de um assistente de research financeiro.

Recebe uma PERGUNTA, a RESPOSTA que o assistente produziu e os TRECHOS de
documento que ele tinha disponíveis. Sua tarefa é decidir duas coisas
independentes, olhando SOMENTE os trechos fornecidos:

1. fundamentada — cada número e cada afirmação de causa da resposta aparece
   nos trechos? Um número que não está em nenhum trecho torna a resposta NÃO
   fundamentada, mesmo que pareça plausível. Valor obtido por conta explícita
   entre dois números que ESTÃO nos trechos conta como fundamentado.
2. responde_completamente — a resposta cobre o que a pergunta pediu? Uma
   resposta fundamentada mas parcial (responde um banco de dois, ou dá o valor
   sem o recorte pedido) é fundamentada e NÃO completa.

Se a resposta for uma recusa, avalie se a recusa procede: quando os trechos
NÃO contêm o que a pergunta pede, `fundamentada` é true e
`responde_completamente` é false.

Não use conhecimento próprio sobre os bancos. Se o trecho não diz, não conta.

Responda SOMENTE com JSON:
{"fundamentada": true|false, "responde_completamente": true|false,
 "justificativa": "uma frase citando o trecho decisivo ou o número ausente"}"""


def _prompt_usuario(registro: dict) -> str:
    resposta = registro["resposta"]
    bruto = {}
    if resposta.get("bruto"):
        try:
            bruto = json.loads(resposta["bruto"])
        except json.JSONDecodeError:
            bruto = {}
    texto = bruto.get("resposta") or resposta.get("resposta")
    if not texto:
        texto = (
            "[O assistente RECUSOU responder. Motivo declarado: "
            f"{resposta.get('motivo_recusa') or 'não informado'}]"
        )
    partes = [f"PERGUNTA:\n{registro['pergunta']}\n", f"RESPOSTA:\n{texto}\n", "TRECHOS:"]
    for indice, recuperado in enumerate(
        registro["chunks_citados_e_recuperados"], start=1
    ):
        chunk = recuperado["chunk"]
        faixa = (
            f"{chunk['pagina_inicio']}-{chunk['pagina_fim']}"
            if chunk["pagina_fim"] != chunk["pagina_inicio"]
            else chunk["pagina_inicio"]
        )
        # Sem score, de propósito: ele enviesaria o juiz para o topo do ranking.
        partes.append(
            f"\n[trecho {indice}] {chunk['empresa']} · {chunk['documento']} · "
            f"pág. {faixa}\n{chunk['texto']}"
        )
    return "\n".join(partes)


_TENTATIVAS = 4
_ESPERA_INICIAL_S = 20.0
# O juiz é limitado a 5 requisições por minuto. Na medição de 2026-08-23 a
# latência de cada chamada (11–13 s) já espaçava o suficiente sozinha, mas isso
# é acidente da latência, não garantia: prompt mais curto ou modelo mais rápido
# estouraria o teto. O intervalo mínimo torna a cadência explícita, em vez de
# depender do backoff reativo — que gasta a janela do dia esperando 429.
_INTERVALO_MINIMO_S = 12.5


def _aguardar_cadencia(instante_anterior: float | None) -> float:
    if instante_anterior is not None:
        restante = _INTERVALO_MINIMO_S - (time.monotonic() - instante_anterior)
        if restante > 0:
            time.sleep(restante)
    return time.monotonic()


def _gerar_com_backoff(juiz, prompt_sistema: str, prompt_usuario: str):
    """Repete em 503/429 — sobrecarga e limite de taxa são transitórios.

    A cota do juiz é diária e pequena (5.15), então desistir na primeira
    sobrecarga desperdiçaria a janela do dia. Erro que não seja de
    disponibilidade sobe na hora: repetir um prompt inválido só gastaria cota.
    """
    espera = _ESPERA_INICIAL_S
    for tentativa in range(1, _TENTATIVAS + 1):
        try:
            return juiz.gerar(prompt_sistema, prompt_usuario, temperatura=0.0)
        except Exception as exc:  # noqa: BLE001 - reclassificado abaixo
            transitorio = any(
                marca in str(exc) for marca in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")
            )
            if not transitorio or tentativa == _TENTATIVAS:
                raise
            print(f"      sobrecarga ({tentativa}/{_TENTATIVAS}); aguardando {espera:.0f}s")
            time.sleep(espera)
            espera *= 2
    raise RuntimeError("inalcançável")


def _extrair_json(texto: str) -> dict:
    achado = re.search(r"\{.*\}", texto, re.S)
    if achado is None:
        raise ValueError(f"Juiz não devolveu JSON: {texto[:200]!r}")
    return json.loads(achado.group(0))


def _houve_resposta_gerada(registro: dict) -> bool:
    """O modelo chegou a redigir resposta, ainda que ela tenha sido descartada."""
    bruto = registro["resposta"].get("bruto")
    if not bruto:
        return False
    try:
        return bool(json.loads(bruto).get("resposta"))
    except json.JSONDecodeError:
        return False


def _sistema_acertou(registro: dict, fundamentada: bool) -> bool:
    """Traduz o veredito do juiz para a MESMA pergunta que o humano respondeu.

    O humano marcou "o sistema fez a coisa certa?". São TRÊS casos, e colapsar
    os dois últimos inverte o veredito — foi o que o teste de fumaça pegou em
    TSTA002, onde juiz e humano concordavam e a tradução acusou divergência:

    - **publicou** → acertou se a resposta publicada está fundamentada;
    - **RN02 descartou** uma resposta que o modelo redigiu → acertou apenas se
      essa resposta NÃO estava fundamentada (descartar resposta boa é o erro);
    - **o modelo recusou** e não redigiu nada → não há resposta a fundamentar;
      o juiz avalia se a recusa procede, e `fundamentada=True` já significa
      "procede".
    """
    resposta = registro["resposta"]
    if not resposta.get("recusa"):
        return fundamentada
    if _houve_resposta_gerada(registro):
        return not fundamentada
    return fundamentada


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--auditoria",
        type=Path,
        required=True,
        help="auditoria_groundedness*.json JÁ PREENCHIDA pelo humano.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=DIR_RESULTADOS_AVALIACAO / "concordancia_juiz_humano.json",
    )
    parser.add_argument(
        "--ids",
        default="",
        help="Subconjunto de pergunta_id separado por vírgula (economiza cota).",
    )
    parser.add_argument("--permitir-api-paga", action="store_true")
    args = parser.parse_args(argv)

    config = carregar_config()
    modelo_juiz = exigir_modelo_juiz_deepeval(config)
    auditoria = json.loads(args.auditoria.read_text(encoding="utf-8"))
    avaliacoes = auditoria["avaliacoes"]

    faltando = [a["pergunta_id"] for a in avaliacoes if not isinstance(a.get("grounded"), bool)]
    if faltando:
        print(
            "FALHOU: auditoria humana incompleta em "
            f"{faltando} — o juiz só roda sobre veredito dado às cegas."
        )
        return 1

    if args.ids:
        alvo = {i.strip() for i in args.ids.split(",") if i.strip()}
        avaliacoes = [a for a in avaliacoes if a["pergunta_id"] in alvo]
        if not avaliacoes:
            print("FALHOU: nenhum pergunta_id do filtro existe na auditoria.")
            return 1

    if not args.permitir_api_paga:
        print(
            f"Ensaio: {len(avaliacoes)} chamadas ao juiz {modelo_juiz!r} "
            "seriam feitas. Use --permitir-api-paga para executar."
        )
        return 0

    # Mesmo provedor plugável da RNF06, só trocando o modelo pelo do juiz.
    juiz = LLMGemini(replace(config, gemini_modelo_llm=modelo_juiz))
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-juiz"
    resultados = []
    custo_total = 0.0
    ultimo_envio: float | None = None

    for indice, registro in enumerate(avaliacoes, start=1):
        pergunta_id = registro["pergunta_id"]
        prompt_usuario = _prompt_usuario(registro)
        registrar_execucao(
            {
                "evento": "juiz_inicio",
                "run_id": run_id,
                "pergunta_id": pergunta_id,
                "modelo_juiz": modelo_juiz,
            }
        )
        try:
            ultimo_envio = _aguardar_cadencia(ultimo_envio)
            bruta = _gerar_com_backoff(juiz, PROMPT_SISTEMA, prompt_usuario)
            veredito = _extrair_json(bruta.texto)
            fundamentada = bool(veredito["fundamentada"])
            completa = bool(veredito["responde_completamente"])
        except Exception as exc:  # noqa: BLE001 - registrado e reportado
            print(f"  [{indice}/{len(avaliacoes)}] {pergunta_id}: ERRO {exc}")
            resultados.append(
                {
                    "pergunta_id": pergunta_id,
                    "erro": f"{type(exc).__name__}: {exc}",
                    "humano_grounded": registro["grounded"],
                }
            )
            registrar_execucao(
                {"evento": "juiz_fim", "run_id": run_id, "pergunta_id": pergunta_id, "erro": str(exc)}
            )
            continue

        custo = getattr(bruta.uso, "custo_usd", None) or 0.0
        custo_total += custo
        acertou_juiz = _sistema_acertou(registro, fundamentada)
        concorda = acertou_juiz == registro["grounded"]
        resultados.append(
            {
                "pergunta_id": pergunta_id,
                "categoria": registro["categoria"],
                "sistema_publicou": not registro["resposta"].get("recusa"),
                "juiz_fundamentada": fundamentada,
                "juiz_responde_completamente": completa,
                "juiz_justificativa": veredito.get("justificativa", ""),
                "juiz_sistema_acertou": acertou_juiz,
                "humano_grounded": registro["grounded"],
                "humano_observacao": registro.get("observacao", ""),
                "concorda": concorda,
                "custo_usd": custo,
            }
        )
        registrar_execucao(
            {
                "evento": "juiz_fim",
                "run_id": run_id,
                "pergunta_id": pergunta_id,
                "custo_usd": custo,
                "concorda": concorda,
            }
        )
        marca = "=" if concorda else "≠"
        print(
            f"  [{indice}/{len(avaliacoes)}] {pergunta_id} {marca} "
            f"juiz={acertou_juiz} humano={registro['grounded']}"
        )

    validos = [r for r in resultados if "erro" not in r]
    matriz = {
        "ambos_acertou": sum(1 for r in validos if r["juiz_sistema_acertou"] and r["humano_grounded"]),
        "ambos_errou": sum(1 for r in validos if not r["juiz_sistema_acertou"] and not r["humano_grounded"]),
        "juiz_acertou_humano_errou": sum(1 for r in validos if r["juiz_sistema_acertou"] and not r["humano_grounded"]),
        "juiz_errou_humano_acertou": sum(1 for r in validos if not r["juiz_sistema_acertou"] and r["humano_grounded"]),
    }
    concordancia = (
        (matriz["ambos_acertou"] + matriz["ambos_errou"]) / len(validos)
        if validos
        else None
    )
    relatorio = {
        "_meta": {
            "auditoria_humana": str(args.auditoria.name),
            "fingerprint": auditoria["_meta"]["fingerprint"],
            "modelo_juiz": modelo_juiz,
            "modelo_gerador": config.gemini_modelo_llm,
            "juiz_igual_ao_gerador": modelo_juiz == config.gemini_modelo_llm,
            "temperatura": 0.0,
            "n": len(validos),
            "n_erros": len(resultados) - len(validos),
            "custo_total_usd": round(custo_total, 6),
            "run_id": run_id,
            "data_utc": datetime.now(timezone.utc).isoformat(),
            "aviso": (
                "Métrica de groundedness reportada continua sendo a auditoria "
                "humana (spec 5.15). Este relatório mede a DIVERGÊNCIA."
            ),
        },
        "matriz_concordancia": matriz,
        "taxa_concordancia": concordancia,
        "discordantes": [r["pergunta_id"] for r in validos if not r["concorda"]],
        "avaliacoes": resultados,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print()
    print(f"concordância: {concordancia:.3f}" if concordancia is not None else "sem casos válidos")
    print(f"matriz: {matriz}")
    print(f"discordantes: {relatorio['discordantes']}")
    print(f"custo: USD {custo_total:.6f}")
    print(f"relatório: {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
