"""Gold adjudicado da conferência humana do CAND-02-P v3 e comparação descritiva dos braços.

O gold tem 60 itens. Onde o responsável e o leitor Claude deram a mesma nota
às cegas, vale essa nota. Onde discordaram, vale a nota final da adjudicação
(`humana/adjudicacao.csv`), feita **depois** de o α do §6 ter sido medido e
congelado. A adjudicação foi feita vendo a nota e a justificativa do Claude,
então a concordância do gold com o Claude é inflada por construção. O α do
protocolo continua sendo o cego.

A comparação dos braços é descritiva e post hoc e não muda veredito nenhum.
Para cada item, toma-se o percentil do evento no ranking completo de cada
braço dentro do par, e mede-se o AUC (chance de um item relevante ficar acima
de um não relevante) contra o gold e contra o rótulo Claude.

    python -m scripts.cand02p_gold
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import cand02p_piloto as p  # noqa: E402

BRACOS = ("b0", "b1", "c", "m")
REAMOSTRAGENS = 4000


def montar_gold() -> list[dict]:
    H = p.DESTINO / "humana"
    humano = p.ler_rotulos_humanos(H / "rotulos.csv")
    mapa = json.loads((H / "mapa.json").read_text(encoding="utf-8"))
    adj = {r["item"]: r for r in csv.DictReader(open(H / "adjudicacao.csv", encoding="utf-8"))}
    linhas = []
    for k, ref in sorted(mapa.items()):
        ia = p.ler_rotulos("claude", "teste", ref["par"])[ref["item"]]
        if humano[k]["nota"] == ia["nota"]:
            if k in adj:
                raise ValueError(f"{k}: há acordo, mas o item aparece na adjudicação")
            gold, origem = humano[k]["nota"], "acordo"
        else:
            r = adj.get(k)
            if r is None or int(r["nota_humano"]) != humano[k]["nota"] or int(r["nota_claude"]) != ia["nota"]:
                raise ValueError(f"{k}: discordância sem adjudicação coerente com as duas leituras")
            gold, origem = int(r["nota_final"]), "adjudicada"
        linhas.append({"item_humano": k, "par": ref["par"], "item": ref["item"], "nota_humano": humano[k]["nota"],
                       "nota_claude": ia["nota"], "nota_gold": gold, "origem": origem})
    return linhas


def auc(itens: list[dict], braco: str, alvo: str, limiar: int) -> float:
    """P(item com nota ≥ limiar fica acima de item abaixo do limiar); empate vale meio."""
    pos = [i["pct"][braco] for i in itens if int(i[alvo]) >= limiar]
    neg = [i["pct"][braco] for i in itens if int(i[alvo]) < limiar]
    if not pos or not neg:
        raise ZeroDivisionError("um dos lados está vazio")
    return sum((a < b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


def percentis(gold: list[dict]) -> None:
    pools, ranks = {}, {}
    for g in gold:
        par = g["par"]
        if par not in pools:
            pools[par] = json.loads((p.DESTINO / "pool" / "teste" / f"{par}.json").read_text())["itens"]
            ranks[par] = {b: p.ranks_do_braco(par, b) for b in BRACOS}
        ev = pools[par][g["item"]]
        g["pct"] = {b: ranks[par][b][ev] / len(ranks[par][b]) for b in BRACOS}


def principal() -> int:
    from scripts.auditar_cand02_redline import alpha_krippendorff_ordinal as alfa

    p.configurar("v3")
    gold = montar_gold()
    H = p.DESTINO / "humana"
    with open(H / "gold.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(gold[0]))
        w.writeheader()
        w.writerows(gold)
    percentis(gold)
    resultado = {
        "aviso": "descritivo e post hoc; o veredito do §6 é o α cego (0,652, INDECIDÍVEL)",
        "itens": len(gold), "origem": dict(Counter(g["origem"] for g in gold)),
        "notas_gold": {str(k): v for k, v in sorted(Counter(g["nota_gold"] for g in gold).items())},
        "alfa_gold_x_claude": round(alfa([(g["nota_gold"], g["nota_claude"]) for g in gold]), 4),
        "alfa_gold_x_humano_cego": round(alfa([(g["nota_gold"], g["nota_humano"]) for g in gold]), 4),
        "auc": {alvo: {f"nota_ge_{lim}": {b: round(auc(gold, b, alvo, lim), 4) for b in BRACOS} for lim in (1, 2)}
                for alvo in ("nota_gold", "nota_claude")},
    }
    al, difs = random.Random(p.SEMENTE), []
    for _ in range(REAMOSTRAGENS):
        s = [al.choice(gold) for _ in gold]
        try:
            difs.append(auc(s, "m", "nota_gold", 2) - auc(s, "b1", "nota_gold", 2))
        except ZeroDivisionError:
            pass
    difs.sort()
    resultado["delta_auc_m_b1_gold_nota2"] = {
        "ponto": round(resultado["auc"]["nota_gold"]["nota_ge_2"]["m"] - resultado["auc"]["nota_gold"]["nota_ge_2"]["b1"], 4),
        "ic95_bootstrap_item": [round(difs[int(0.025 * len(difs))], 4), round(difs[int(0.975 * len(difs))], 4)],
        "reamostragens_validas": len(difs)}
    (H / "gold_descritivo.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
