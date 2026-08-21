"""Comparação pareada entre duas estratégias na rodada congelada (RF26, 5.16).

**Custo zero.** Não faz chamada nenhuma: lê o `checkpoint_teste.jsonl` da rodada
publicada, que já contém as 5 estratégias sobre as mesmas 45 perguntas. Medir de
novo seria pagar duas vezes pelo mesmo número — e, pior, um número diferente,
porque a rodada nova teria outro `run_id`.

**Por que McNemar e não diferença de proporções.** As duas estratégias respondem
às MESMAS perguntas; os erros são pareados, não independentes. O que informa é
quantas perguntas uma acerta e a outra erra (as discordâncias), não a diferença
entre duas médias. O limiar de 6 discordâncias na mesma direção foi declarado
ANTES da execução (AGENTS.md §4.2, p = 0,031 no teste exato bilateral) — abaixo
disso o veredito é "indistinguível neste tamanho de amostra", nunca "empate" e
muito menos "a minha ganhou por pouco".

    python -m scripts.comparar_estrategias_pareado --a keyword --b hibrida
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from math import comb
from pathlib import Path
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.config import DIR_RESULTADOS_AVALIACAO  # noqa: E402

CAMINHO_CHECKPOINT = DIR_RESULTADOS_AVALIACAO / "checkpoint_teste.jsonl"
CAMINHO_METRICAS = DIR_RESULTADOS_AVALIACAO / "metricas_teste.json"
DIR_RESULTADOS = RAIZ / "resultados"
LIMIAR_DISCORDANCIAS = 6


def p_mcnemar_exato(n_a: int, n_b: int) -> float:
    """p bilateral do teste exato de McNemar (binomial com p=0,5).

    Só as discordâncias entram: as concordâncias não carregam informação sobre
    qual estratégia é melhor.
    """
    n = n_a + n_b
    if n == 0:
        return 1.0
    k = min(n_a, n_b)
    cauda = sum(comb(n, i) for i in range(0, k + 1)) / (2**n)
    return min(1.0, 2 * cauda)


def _carregar(fingerprint: str) -> list[dict]:
    linhas = [
        json.loads(linha)
        for linha in CAMINHO_CHECKPOINT.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    return [linha for linha in linhas if linha.get("fingerprint") == fingerprint]


def comparar(estrategia_a: str, estrategia_b: str) -> dict:
    metricas = json.loads(CAMINHO_METRICAS.read_text(encoding="utf-8"))
    fingerprint = metricas["_meta"]["fingerprint"]
    registros = _carregar(fingerprint)

    por = {(r["estrategia"], r["pergunta_id"]): r for r in registros}
    ids = sorted({r["pergunta_id"] for r in registros})
    categoria = {r["pergunta_id"]: r["categoria"] for r in registros}

    faltando = [
        (e, i)
        for e in (estrategia_a, estrategia_b)
        for i in ids
        if (e, i) not in por
    ]
    if faltando:
        raise ValueError(f"Checkpoint incompleto para o par: {faltando[:5]}")

    comparacoes: dict[str, dict] = {}
    # `recall_ok` mede a RECUPERAÇÃO — é o número que decide a dependência de
    # embedding, porque é onde a estratégia age. `exatidao_ok` mede a resposta
    # inteira e mistura recuperação com geração.
    for campo, categorias in (
        ("recall_ok", None),
        ("exatidao_ok", ("factual",)),
        ("exatidao_ok", ("comparativa",)),
        ("recusa_correta", ("adversarial",)),
    ):
        rotulo = campo if categorias is None else f"{campo}[{categorias[0]}]"
        so_a: list[str] = []
        so_b: list[str] = []
        ambos = nenhum = ignorados = 0
        for identificador in ids:
            if categorias and categoria[identificador] not in categorias:
                continue
            va = por[(estrategia_a, identificador)][campo]
            vb = por[(estrategia_b, identificador)][campo]
            if va is None or vb is None:
                ignorados += 1
                continue
            if va and vb:
                ambos += 1
            elif va and not vb:
                so_a.append(identificador)
            elif vb and not va:
                so_b.append(identificador)
            else:
                nenhum += 1
        n_pares = ambos + nenhum + len(so_a) + len(so_b)
        p = p_mcnemar_exato(len(so_a), len(so_b))
        maior = max(len(so_a), len(so_b))
        comparacoes[rotulo] = {
            "n_pares": n_pares,
            "ignorados_por_none": ignorados,
            f"acertos_{estrategia_a}": ambos + len(so_a),
            f"acertos_{estrategia_b}": ambos + len(so_b),
            "concordam_acerto": ambos,
            "concordam_erro": nenhum,
            f"so_{estrategia_a}": sorted(so_a),
            f"so_{estrategia_b}": sorted(so_b),
            "discordancias": len(so_a) + len(so_b),
            "maior_direcao": maior,
            "limiar": LIMIAR_DISCORDANCIAS,
            "p_mcnemar_exato": round(p, 4),
            "veredito": (
                f"diferença declarada a favor de "
                f"{estrategia_a if len(so_a) > len(so_b) else estrategia_b}"
                if maior >= LIMIAR_DISCORDANCIAS
                else "indistinguível neste tamanho de amostra"
            ),
        }

    return {
        "run_id": (
            f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:10]}"
        ),
        "fonte": str(CAMINHO_CHECKPOINT),
        "fingerprint": fingerprint,
        "estrategia_a": estrategia_a,
        "estrategia_b": estrategia_b,
        "custo_usd": 0.0,
        "chamadas_llm": 0,
        "limiar_declarado": LIMIAR_DISCORDANCIAS,
        "comparacoes": comparacoes,
    }


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", default="keyword")
    parser.add_argument("--b", default="hibrida")
    parser.add_argument("--saida", type=Path, default=None)
    args = parser.parse_args(argv)

    relatorio = comparar(args.a, args.b)
    destino = args.saida or (
        DIR_RESULTADOS / f"comparacao_{args.a}_x_{args.b}.json"
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    print(f"\nrelatório: {destino}")
    return 0


if __name__ == "__main__":  # pragma: no cover - execução manual
    raise SystemExit(principal())
