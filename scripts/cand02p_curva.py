"""Curva de aprendizado do M no teste do CAND-02-P v2 — análise DESCRITIVA.

Pergunta: aumentar o número de pares de treino melhora o M? E o ganho vem do
volume ou de ter pares da mesma transição do teste (4T→1T)?

Reusa o teste do v2, então **não muda veredito nenhum** e não substitui um
teste novo. O M congelado (`artefatos/cand02p_v2/modelo/`) não é tocado: cada
ponto da curva treina um modelo novo com os mesmos hiperparâmetros.

    python -m scripts.cand02p_curva
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import cand02p_piloto as p  # noqa: E402
from src import redline as rl  # noqa: E402

V1 = RAIZ / "artefatos" / "cand02p"
V2 = RAIZ / "artefatos" / "cand02p_v2"
SORTEIOS = 10


def carregar_treino() -> dict[str, dict]:
    """par → (X, y, transição) para os 22 pares de treino disponíveis."""
    saida = {}
    for destino, papeis in ((V1, ("treino", "teste")), (V2, ("treino",))):
        with p._Em(destino):
            resumo = json.load(open(p.DESTINO / "resumo_eventos.json"))["pares"]
            for par, info in sorted(resumo.items()):
                if info["papel"] not in papeis:
                    continue
                rot = p.consolidar(info["papel"], par)
                eventos = {e["id"]: e for e in p.ler_eventos(par)}
                c = p._c_do_par(par)
                usados = [(i, r) for i, r in rot.items() if r["julgavel"]]
                saida[par] = {"X": [p.features(eventos[i], c[i]) for i, _ in usados],
                              "y": [r["ganho"] for _, r in usados],
                              "transicao": "2T→3T" if "_2T2025_3T2025" in par else "4T→1T"}
    return saida


def carregar_teste() -> dict[str, dict]:
    saida = {}
    with p._Em(V2):
        resumo = json.load(open(p.DESTINO / "resumo_eventos.json"))["pares"]
        for par, info in sorted(resumo.items()):
            if info["papel"] != "teste":
                continue
            rot = p.consolidar("teste", par)
            eventos = p.ler_eventos(par)
            c = p._c_do_par(par)
            excluidos = {i for i, r in rot.items() if not r["julgavel"]}
            saida[par] = {
                "eventos": [e for e in eventos if e["id"] not in excluidos],
                "X": [p.features(e, c[e["id"]]) for e in eventos if e["id"] not in excluidos],
                "ganhos": {i: r["ganho"] for i, r in rot.items() if r["julgavel"]},
                "b1": {k: rl.ndcg([i for i, _ in sorted(p.ranks_do_braco(par, "b1").items(),
                                                        key=lambda t: t[1]) if i not in excluidos],
                                  {i: r["ganho"] for i, r in rot.items() if r["julgavel"]}, k)
                       for k in (10, 20)},
            }
    return saida


def avaliar(pares_treino: list[str], treino: dict, teste: dict) -> dict:
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor

    X = [x for par in pares_treino for x in treino[par]["X"]]
    y = [v for par in pares_treino for v in treino[par]["y"]]
    m = HistGradientBoostingRegressor(**p.HIPERPARAMETROS_M).fit(np.asarray(X, float), np.asarray(y))
    n10, n20, vencidos = [], [], 0
    for par, t in teste.items():
        prev = m.predict(np.asarray(t["X"], float))
        ordem = [e["id"] for e, _ in sorted(zip(t["eventos"], prev), key=lambda z: (-z[1], z[0]["rank_b1"]))]
        a, b = rl.ndcg(ordem, t["ganhos"], 10), rl.ndcg(ordem, t["ganhos"], 20)
        n10.append(a); n20.append(b)
        vencidos += a > t["b1"][10]
    b1_10 = statistics.fmean(t["b1"][10] for t in teste.values())
    return {"pares": len(pares_treino), "eventos": len(y), "ndcg10": round(statistics.fmean(n10), 4),
            "ndcg20": round(statistics.fmean(n20), 4), "delta10_sobre_b1": round(statistics.fmean(n10) - b1_10, 4),
            "pares_vencidos": vencidos}


def principal() -> int:
    treino, teste = carregar_treino(), carregar_teste()
    todos = sorted(treino)
    por_tipo = {t: [par for par in todos if treino[par]["transicao"] == t] for t in ("2T→3T", "4T→1T")}
    resultado = {"aviso": "descritivo; reusa o teste do v2; não muda veredito", "por_tipo": {}, "por_volume": {}}
    for nome, pares in (("só 2T→3T", por_tipo["2T→3T"]), ("só 4T→1T", por_tipo["4T→1T"]), ("todos", todos)):
        resultado["por_tipo"][nome] = avaliar(pares, treino, teste)
        print(nome, resultado["por_tipo"][nome], flush=True)
    for n in (8, 12, 16, 22):
        pontos = [avaliar(random.Random(f"{p.SEMENTE}:curva:{n}:{s}").sample(todos, n), treino, teste)
                  for s in range(SORTEIOS if n < 22 else 1)]
        resultado["por_volume"][n] = {
            "ndcg10_media": round(statistics.fmean(x["ndcg10"] for x in pontos), 4),
            "ndcg10_min": min(x["ndcg10"] for x in pontos), "ndcg10_max": max(x["ndcg10"] for x in pontos),
            "delta10_media": round(statistics.fmean(x["delta10_sobre_b1"] for x in pontos), 4),
            "pares_vencidos_media": round(statistics.fmean(x["pares_vencidos"] for x in pontos), 2),
            "sorteios": len(pontos)}
        print(n, resultado["por_volume"][n], flush=True)
    (V2 / "curva_aprendizado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
