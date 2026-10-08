"""Calibração da rubrica v2 do CAND-02-P antes de qualquer releitura geral.

Protocolo: `resultados/protocolo_calibracao_rubrica_v2_cand02p_2026-10-07.md`.

    python -m scripts.cand02p_calibracao sortear   # 4 pares e 60 itens novos; pacote cego
    python -m scripts.cand02p_calibracao medir     # α humano × Claude v2 (portão) e controles

O sorteio exclui os 60 itens que o responsável já rotulou e adjudicou. Os 60
itens novos têm duas notas do Claude, uma com a rubrica v1 (`claude`) e outra
com a v2 (`claude_v2`), e a nota do humano é dada com a v2. Assim dá para
separar a melhora da rubrica da mudança do próprio humano depois da
adjudicação.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import cand02p_piloto as p  # noqa: E402

LEITOR_V2 = "claude_v2"
N_PARES = 4
N_ITENS = 60
LIMIAR = 0.67
PASTA_LEITURA = RAIZ / "conferencia_calibracao_v3"


def escolher_pares(pares_teste: list[str], semente) -> list[str]:
    """Quatro emissores distintos, sorteados, e uma das duas transições de cada."""
    al = random.Random(f"{semente}:calibracao:pares")
    por_emissor: dict[str, list[str]] = {}
    for par in sorted(pares_teste):
        por_emissor.setdefault(par.split("_", 1)[0], []).append(par)
    emissores = al.sample(sorted(por_emissor), N_PARES)
    return sorted(al.choice(por_emissor[e]) for e in emissores)


def escolher_itens(pools: dict[str, list[str]], vistos: set[tuple[str, str]], semente) -> list[tuple[str, str]]:
    """N_ITENS / N_PARES itens por par, nunca um (par, item) já visto pelo humano.
    Devolve (par, item) em ordem embaralhada com semente fixa."""
    por_par = N_ITENS // len(pools)
    escolhidos = []
    for par in sorted(pools):
        livres = sorted(i for i in pools[par] if (par, i) not in vistos)
        if len(livres) < por_par:
            raise ValueError(f"{par}: só {len(livres)} itens não vistos")
        escolhidos += [(par, i) for i in random.Random(f"{semente}:calibracao:{par}").sample(livres, por_par)]
    random.Random(f"{semente}:calibracao:ordem").shuffle(escolhidos)
    return escolhidos


def decidir(alfa) -> str:
    """Portão da calibração. α ausente ou NaN não aprova (AGENTS.md §4.4, regra 4)."""
    if alfa is None or alfa != alfa or not (alfa >= LIMIAR):
        return "RUBRICA_V2_NAO_BASTA"
    return "RUBRICA_V2_APROVADA"


def _pagina(doc: str, n) -> str:
    return f"[{doc}.pdf](pdfs/{doc}.pdf), página {n}" if n is not None else f"`{doc}.pdf` (a frase não existe neste documento)"


def cmd_sortear(_args) -> int:
    cal = p.DESTINO / "calibracao"
    if (cal / "plano.json").exists():
        raise SystemExit("o sorteio já foi feito e congelado; sortear de novo é outro protocolo")
    resumo = json.load(open(p.DESTINO / "resumo_eventos.json"))["pares"]
    pares = escolher_pares([par for par, info in resumo.items() if info["papel"] == "teste"], p.SEMENTE)
    vistos = {(r["par"], r["item"]) for r in json.loads((p.DESTINO / "humana" / "mapa.json").read_text()).values()}
    pools = {par: sorted(json.loads((p.DESTINO / "pool" / "teste" / f"{par}.json").read_text())["itens"]) for par in pares}
    escolhidos = escolher_itens(pools, vistos, p.SEMENTE)
    itens, mapa = [], {}
    for n, (par, item) in enumerate(escolhidos, 1):
        pacote = json.loads((p.DESTINO / "pacotes" / "teste" / f"{par}.json").read_text(encoding="utf-8"))
        conteudo = next(i for i in pacote["itens"] if i["item"] == item)
        novo = f"C{n:02d}"
        itens.append({**conteudo, "item": novo, "documento_anterior": pacote["documento_anterior"],
                      "documento_atual": pacote["documento_atual"]})
        mapa[novo] = {"par": par, "item": item}
    humana = cal / "humana"
    humana.mkdir(parents=True, exist_ok=True)
    (cal / "plano.json").write_text(json.dumps({"pares": pares, "itens_por_par": N_ITENS // N_PARES,
                                                "excluidos_por_ja_vistos": len(vistos)}, indent=1), encoding="utf-8")
    (humana / "pacote.json").write_text(json.dumps({"itens": itens}, ensure_ascii=False, indent=1), encoding="utf-8")
    (humana / "mapa.json").write_text(json.dumps(mapa, indent=1), encoding="utf-8")
    linhas = ["# Calibração da rubrica v2 — pacote cego\n",
              "Rubrica: [rubrica_v2.md](rubrica_v2.md), nesta pasta. Preencha `rotulos.csv` nesta pasta.\n"]
    for it in itens:
        linhas.append(f"\n## {it['item']} — {it['operacao']} ({it['tipo']})\n\n"
                      f"- Anterior: {_pagina(it['documento_anterior'], it['pagina_anterior'])}\n"
                      f"- Atual: {_pagina(it['documento_atual'], it['pagina_atual'])}\n"
                      f"- Seção: {it['secao']}\n"
                      f"\n**Antes:** {it['trecho_anterior'] or '(nada)'}\n\n**Depois:** {it['trecho_atual'] or '(nada)'}\n")
    (humana / "pacote.md").write_text("".join(linhas), encoding="utf-8")
    with open(humana / "rotulos_modelo.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item", "nota", "motivo", "acao", "critico", "julgavel", "justificativa"])
        for it in itens:
            w.writerow([it["item"], "", "", "", "false", "true", ""])
    print(f"pares: {pares}; {len(itens)} itens; pacote em {humana}")
    return 0


def cmd_medir(args) -> int:
    from scripts.auditar_cand02_redline import alpha_krippendorff_ordinal

    import shutil

    cal = p.DESTINO / "calibracao"
    humano = p.ler_rotulos_humanos(Path(args.planilha))
    # Cópia de registro, como entregue, antes de qualquer conta.
    shutil.copyfile(args.planilha, cal / "humana" / "rotulos.csv")
    mapa = json.loads((cal / "humana" / "mapa.json").read_text(encoding="utf-8"))
    if set(humano) != set(mapa):
        raise SystemExit(f"a planilha não cobre exatamente os {len(mapa)} itens da calibração")

    def alfa(a: str, b: str) -> dict:
        notas = []
        for k, ref in sorted(mapa.items()):
            leitura = {"humano": humano[k]}
            for leitor in ("claude", LEITOR_V2):
                leitura[leitor] = p.ler_rotulos(leitor, "teste", ref["par"])[ref["item"]]
            if leitura[a]["julgavel"] and leitura[b]["julgavel"]:
                notas.append((leitura[a]["nota"], leitura[b]["nota"]))
        valor = alpha_krippendorff_ordinal(notas) if notas else None
        return {"itens": len(notas), "alfa": None if valor is None or valor != valor else round(valor, 4),
                "acordo_exato": round(sum(x == y for x, y in notas) / len(notas), 4) if notas else None}

    r = {"portao": {"humano_x_claude_v2": alfa("humano", LEITOR_V2)},
         "controles": {"humano_x_claude_v1": alfa("humano", "claude"), "claude_v1_x_claude_v2": alfa("claude", LEITOR_V2)},
         "limiar": LIMIAR}
    r["decisao"] = decidir(r["portao"]["humano_x_claude_v2"]["alfa"])
    (cal / "resultado.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0


def principal(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("sortear")
    m = sub.add_parser("medir")
    m.add_argument("--planilha", default=str(PASTA_LEITURA / "rotulos.csv"))
    args = ap.parse_args(argv)
    p.configurar("v3")
    return {"sortear": cmd_sortear, "medir": cmd_medir}[args.comando](args)


if __name__ == "__main__":
    sys.exit(principal())
