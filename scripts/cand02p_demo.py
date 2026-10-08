"""Demonstração do ordenador de mudanças entre releases (CAND-02-P, destilação do leitor Claude).

Dois modos:

    # Uso real: um par que nenhum modelo viu nem ninguém rotulou, pelo modelo FINAL
    python -m scripts.cand02p_demo novo --emissor SANTANDER --anterior 3T2025 --atual 4T2025

    # Prova: um par do teste do v3 pelo modelo CONGELADO do v3 (que não o viu),
    # com a nota do leitor Claude ao lado de cada item
    python -m scripts.cand02p_demo prova --par SANTANDER_4T2022_1T2023

O modo "novo" faz o caminho inteiro a partir do cache de OCR: extração dos
eventos, regras do B1, similaridades do C (bge-m3 no Ollama local), atributos e
modelo. Nenhuma chamada paga e nenhuma chamada a LLM.

O modelo final viu os 64 pares rotulados. Demonstrá-lo num deles mostraria
memória, não funcionamento; por isso o modo "novo" recusa par rotulado, e o
modo "prova" usa o M do v3, que nunca viu o próprio teste.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import cand02p_modelo_final as mf  # noqa: E402
from scripts import cand02p_piloto as p  # noqa: E402
from src import redline as rl  # noqa: E402

SAIDA = RAIZ / "artefatos" / "cand02p_final" / "demo"


def _pares_rotulados() -> set[tuple[str, str, str]]:
    rotulados = set()
    for destino, _ in mf.PILOTOS:
        for par, info in json.load(open(destino / "resumo_eventos.json"))["pares"].items():
            emissor, ta, td = par.split("_")
            rotulados.add((emissor, ta, td))
    return rotulados


def _trecho(texto: str | None, n: int = 220) -> str:
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def _linha(e: dict, extra: dict) -> dict:
    return {"id": e["id"], "operacao": e["operacao"], "tipo": e["tipo"],
            "pagina_antes": e.get("pagina_antes"), "pagina_depois": e.get("pagina_depois"),
            "secao": e.get("secao_depois") or e.get("secao_antes") or e.get("secao"),
            "antes": _trecho(e.get("antes")), "depois": _trecho(e.get("depois")), **extra}


def cmd_novo(args) -> int:
    import numpy as np

    if (args.emissor, args.anterior, args.atual) in _pares_rotulados():
        raise SystemExit("este par foi rotulado e está no treino do modelo final; use outro, ou o modo prova")
    tempos = {}
    p.configurar("v1")  # o corpus principal e a expansão têm os releases de 2025 e 2026
    m = p.manifesto()
    if (args.emissor, args.anterior) not in m or (args.emissor, args.atual) not in m:
        raise SystemExit("release não encontrado nos manifestos do corpus")
    t0 = time.perf_counter()
    anterior, _ = p.carregar_documento(m[(args.emissor, args.anterior)])
    atual, _ = p.carregar_documento(m[(args.emissor, args.atual)])
    tempos["leitura_do_cache_ocr_s"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    par = f"{args.emissor}_{args.anterior}_{args.atual}"
    eventos = rl.gerar_eventos(par, anterior, atual)
    b1 = {e.id: i for i, e in enumerate(rl.ordenar_b1(eventos), 1)}
    evs = [{**e.para_dict(), "rank_b1": b1[e.id]} for e in eventos]
    tempos["eventos_e_regras_b1_s"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    ancoras = p.embedar(list(p.ANCORAS))
    sims = p.embedar([p.texto_c(e) for e in evs]) @ ancoras.T
    cs = {e["id"]: {"sims": [round(float(s), 4) for s in v], "score_c": round(float(v.max()), 4)} for e, v in zip(evs, sims)}
    tempos["similaridade_c_ollama_s"] = time.perf_counter() - t0
    with open(mf.DESTINO_FINAL / "modelo" / "m.pkl", "rb") as f:
        modelo = pickle.load(f)
    t0 = time.perf_counter()
    prev = modelo.predict(np.asarray([p.features(e, cs[e["id"]]) for e in evs], float))
    tempos["modelo_s"] = time.perf_counter() - t0
    ordem = sorted(zip(evs, prev), key=lambda z: (-z[1], z[0]["rank_b1"]))
    saida = {"modo": "novo", "par": par, "modelo": "final (64 pares)", "paginas": [anterior.paginas, atual.paginas],
             "eventos": len(evs), "tempos": {k: round(v, 3) for k, v in tempos.items()},
             "top_m": [_linha(e, {"rank_m": i, "score_m": round(float(s), 3), "rank_b1": e["rank_b1"]})
                       for i, (e, s) in enumerate(ordem[: args.top], 1)],
             "top_b1": [_linha(e, {"rank_b1": e["rank_b1"]}) for e in sorted(evs, key=lambda e: e["rank_b1"])[: args.top]]}
    return _gravar(saida)


def cmd_prova(args) -> int:
    with p._Em(mf.PILOTOS[2][0]):
        resumo = json.load(open(p.DESTINO / "resumo_eventos.json"))["pares"]
        if resumo.get(args.par, {}).get("papel") != "teste":
            raise SystemExit("o modo prova aceita só pares de teste do v3")
        eventos = {e["id"]: e for e in p.ler_eventos(args.par)}
        rot = p.consolidar("teste", args.par)
        notas = {i: r["notas"][0] for i, r in rot.items() if r["julgavel"]}
        ranks = {b: p.ranks_do_braco(args.par, b) for b in ("b1", "m")}
    r = json.load(open(mf.PILOTOS[2][0] / "resultado_teste.json"))["por_par"][args.par]

    def topo(braco):
        ids = sorted(ranks[braco], key=ranks[braco].get)
        ids = [i for i in ids if i in notas or i not in rot][: args.top]
        return [_linha(eventos[i], {"rank": ranks[braco][i], "nota_claude": notas.get(i)}) for i in ids]

    saida = {"modo": "prova", "par": args.par, "modelo": "M congelado do v3 (não viu este par)",
             "eventos": len(eventos), "ndcg10": {"m": round(r["m"]["ndcg10"], 3), "b1": round(r["b1"]["ndcg10"], 3)},
             "top_m": topo("m"), "top_b1": topo("b1")}
    return _gravar(saida)


def _gravar(saida: dict) -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / f"{saida['modo']}_{saida['par']}.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n== {saida['par']} — {saida['modelo']} — {saida['eventos']} eventos ==")
    if "tempos" in saida:
        print("tempos:", saida["tempos"])
    if "ndcg10" in saida:
        print("nDCG@10 (rótulo do Claude):", saida["ndcg10"])
    for nome in ("top_m", "top_b1"):
        print(f"\n-- {'MODELO' if nome == 'top_m' else 'REGRAS (B1)'} --")
        for i, l in enumerate(saida[nome], 1):
            marca = f" [Claude: {l['nota_claude']}]" if "nota_claude" in l else ""
            pag = l["pagina_depois"] or l["pagina_antes"]
            print(f"{i:>2}. {l['operacao']:<9} p.{pag}{marca}  {l['depois'] or '(removido) ' + l['antes']}"[:260])
    return 0


def principal(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="comando", required=True)
    n = sub.add_parser("novo")
    n.add_argument("--emissor", required=True)
    n.add_argument("--anterior", required=True)
    n.add_argument("--atual", required=True)
    n.add_argument("--top", type=int, default=10)
    pr = sub.add_parser("prova")
    pr.add_argument("--par", required=True)
    pr.add_argument("--top", type=int, default=10)
    args = ap.parse_args(argv)
    return {"novo": cmd_novo, "prova": cmd_prova}[args.comando](args)


if __name__ == "__main__":
    sys.exit(principal())
