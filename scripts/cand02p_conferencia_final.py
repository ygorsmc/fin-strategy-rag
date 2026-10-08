"""Conferência final da rubrica v2 do CAND-02-P: amostra estratificada pela nota do Claude v2.

Protocolo: `resultados/protocolo_conferencia_final_rubrica_v2_cand02p_2026-10-07.md`.
É a última tentativa e tem resultado vinculante.

    python -m scripts.cand02p_conferencia_final poder     # simulação de poder (antes do sorteio)
    python -m scripts.cand02p_conferencia_final sortear   # 30 itens de cada nota do Claude v2, nunca vistos
    python -m scripts.cand02p_conferencia_final medir     # portões G1 e G2, e descritivos

A calibração anterior sorteou ao acaso e ficou quase sem nota 2. Aqui cada
nota do Claude v2 tem 30 itens. O α desta amostra mede a concordância com as
três notas igualmente representadas e **não se compara** com os α das
conferências anteriores, que vieram de amostras dominadas pela nota 0.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import statistics
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import cand02p_calibracao as cal  # noqa: E402
from scripts import cand02p_piloto as p  # noqa: E402

N_POR_NOTA = 30
LIMIAR_ALFA = 0.67
LIMIAR_PRIORIDADE = 0.70
PASTA_LEITURA = RAIZ / "conferencia_final_v3"

#: P(nota humana | nota do Claude), hipóteses de planejamento do poder. "base"
#: vem das duas conferências anteriores (ver protocolo); "pessimista" e "acaso"
#: são cenários de contraste.
CENARIOS = {
    "base": {0: (0.88, 0.11, 0.01), 1: (0.29, 0.62, 0.09), 2: (0.11, 0.22, 0.67)},
    "pessimista": {0: (0.85, 0.14, 0.01), 1: (0.40, 0.50, 0.10), 2: (0.25, 0.35, 0.40)},
    "acaso": {c: (1 / 3, 1 / 3, 1 / 3) for c in (0, 1, 2)},
}


def estratificar(disponiveis: dict[int, list[tuple[str, str]]], n: int, semente) -> list[tuple[str, str]]:
    """n itens de cada nota do Claude, sorteados; levanta se faltar item."""
    escolhidos = []
    for nota in (0, 1, 2):
        lista = sorted(disponiveis.get(nota, []))
        if len(lista) < n:
            raise ValueError(f"nota {nota}: só {len(lista)} itens disponíveis para {n}")
        escolhidos += random.Random(f"{semente}:final:{nota}").sample(lista, n)
    random.Random(f"{semente}:final:ordem").shuffle(escolhidos)
    return escolhidos


def prioridade_reconhecida(pares: list[tuple[int, int]]) -> float | None:
    """Fração dos itens com nota 2 do Claude que o humano marcou com 1 ou 2.
    `pares` = (humano, claude). Sem item de nota 2 do Claude, devolve None."""
    dois = [h for h, c in pares if c == 2]
    return sum(h >= 1 for h in dois) / len(dois) if dois else None


def decidir(alfa, prioridade) -> str:
    """Os dois portões juntos. Ausência ou NaN reprova (AGENTS.md §4.4, regra 4)."""
    ok_alfa = alfa is not None and alfa == alfa and alfa >= LIMIAR_ALFA
    ok_prio = prioridade is not None and prioridade == prioridade and prioridade >= LIMIAR_PRIORIDADE
    return "RUBRICA_V2_APROVADA" if ok_alfa and ok_prio else "RUBRICA_V2_REPROVADA"


def simular(cond: dict, n: int, reps: int, semente) -> dict:
    from scripts.auditar_cand02_redline import alpha_krippendorff_ordinal as alfa

    al, alfas, aprov = random.Random(semente), [], 0
    for _ in range(reps):
        pares = [(al.choices((0, 1, 2), cond[c])[0], c) for c in (0, 1, 2) for _ in range(n)]
        a = alfa(pares)
        alfas.append(a)
        aprov += decidir(a, prioridade_reconhecida(pares)) == "RUBRICA_V2_APROVADA"
    alfas.sort()
    return {"alfa_mediano": round(statistics.median(alfas), 3),
            "faixa95": [round(alfas[int(0.025 * reps)], 3), round(alfas[int(0.975 * reps)], 3)],
            "p_aprovar": round(aprov / reps, 3)}


def cmd_poder(_args) -> int:
    saida = {nome: simular(cond, N_POR_NOTA, 2000, f"{p.SEMENTE}:poder:{nome}") for nome, cond in CENARIOS.items()}
    destino = p.DESTINO / "conferencia_final"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "poder.json").write_text(json.dumps({"n_por_nota": N_POR_NOTA, "cenarios": CENARIOS, "resultado": saida},
                                                   indent=1), encoding="utf-8")
    print(json.dumps(saida, indent=1))
    return 0


def cmd_sortear(_args) -> int:
    destino = p.DESTINO / "conferencia_final"
    if (destino / "plano.json").exists():
        raise SystemExit("o sorteio já foi feito e congelado")
    pares = json.loads((p.DESTINO / "calibracao" / "plano.json").read_text())["pares"]
    vistos = {(r["par"], r["item"]) for f in (p.DESTINO / "humana" / "mapa.json",
                                               p.DESTINO / "calibracao" / "humana" / "mapa.json")
              for r in json.loads(f.read_text()).values()}
    disponiveis: dict[int, list[tuple[str, str]]] = {}
    for par in pares:
        for item, r in p.ler_rotulos(cal.LEITOR_V2, "teste", par).items():
            if (par, item) not in vistos and r["julgavel"]:
                disponiveis.setdefault(r["nota"], []).append((par, item))
    escolhidos = estratificar(disponiveis, N_POR_NOTA, p.SEMENTE)
    itens, mapa = [], {}
    for n, (par, item) in enumerate(escolhidos, 1):
        pacote = json.loads((p.DESTINO / "pacotes" / "teste" / f"{par}.json").read_text(encoding="utf-8"))
        conteudo = next(i for i in pacote["itens"] if i["item"] == item)
        novo = f"F{n:02d}"
        itens.append({**conteudo, "item": novo, "documento_anterior": pacote["documento_anterior"],
                      "documento_atual": pacote["documento_atual"]})
        mapa[novo] = {"par": par, "item": item}
    humana = destino / "humana"
    humana.mkdir(parents=True, exist_ok=True)
    (destino / "plano.json").write_text(json.dumps({"pares": pares, "n_por_nota": N_POR_NOTA,
                                                    "disponiveis": {str(k): len(v) for k, v in sorted(disponiveis.items())},
                                                    "excluidos_por_ja_vistos": len(vistos)}, indent=1), encoding="utf-8")
    (humana / "pacote.json").write_text(json.dumps({"itens": itens}, ensure_ascii=False, indent=1), encoding="utf-8")
    (humana / "mapa.json").write_text(json.dumps(mapa, indent=1), encoding="utf-8")
    linhas = ["# Conferência final — pacote cego\n",
              "Rubrica: [rubrica_v2.md](rubrica_v2.md), nesta pasta. Preencha `rotulos.csv` nesta pasta.\n"]
    for it in itens:
        linhas.append(f"\n## {it['item']} — {it['operacao']} ({it['tipo']})\n\n"
                      f"- Anterior: {cal._pagina(it['documento_anterior'], it['pagina_anterior'])}\n"
                      f"- Atual: {cal._pagina(it['documento_atual'], it['pagina_atual'])}\n"
                      f"- Seção: {it['secao']}\n"
                      f"\n**Antes:** {it['trecho_anterior'] or '(nada)'}\n\n**Depois:** {it['trecho_atual'] or '(nada)'}\n")
    (humana / "pacote.md").write_text("".join(linhas), encoding="utf-8")
    with open(humana / "rotulos_modelo.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item", "nota", "motivo", "acao", "critico", "julgavel", "justificativa"])
        for it in itens:
            w.writerow([it["item"], "", "", "", "false", "true", ""])
    print(f"{len(itens)} itens ({N_POR_NOTA} por nota do Claude v2); pacote em {humana}")
    return 0


def cmd_medir(args) -> int:
    from scripts.auditar_cand02_redline import alpha_krippendorff_ordinal as alfa

    destino = p.DESTINO / "conferencia_final"
    humano = p.ler_rotulos_humanos(Path(args.planilha))
    mapa = json.loads((destino / "humana" / "mapa.json").read_text(encoding="utf-8"))
    if set(humano) != set(mapa):
        raise SystemExit(f"a planilha não cobre exatamente os {len(mapa)} itens")
    shutil.copyfile(args.planilha, destino / "humana" / "rotulos.csv")  # registro, como entregue
    linhas = []
    for k, ref in sorted(mapa.items()):
        v1 = p.ler_rotulos("claude", "teste", ref["par"])[ref["item"]]
        v2 = p.ler_rotulos(cal.LEITOR_V2, "teste", ref["par"])[ref["item"]]
        if humano[k]["julgavel"] and v2["julgavel"]:
            linhas.append((humano[k]["nota"], v2["nota"], v1["nota"] if v1["julgavel"] else None))
    pares_v2 = [(h, c2) for h, c2, _ in linhas]
    a = alfa(pares_v2) if pares_v2 else None
    a = None if a is None or a != a else round(a, 4)
    prio = prioridade_reconhecida(pares_v2)
    conf = Counter(pares_v2)
    r = {"itens": len(linhas),
         "portoes": {"G1_alfa_humano_x_claude_v2": a, "G2_prioridade_reconhecida": None if prio is None else round(prio, 4)},
         "limiares": {"G1": LIMIAR_ALFA, "G2": LIMIAR_PRIORIDADE},
         "descritivos": {
             "matriz_humano_linha_x_claude_v2_coluna": [[conf[(h, c)] for c in (0, 1, 2)] for h in (0, 1, 2)],
             "acordo_exato": round(sum(h == c for h, c in pares_v2) / len(pares_v2), 4),
             "humano_2_onde_claude_0": sum(1 for h, c in pares_v2 if h == 2 and c == 0),
             "alfa_humano_x_claude_v1": round(alfa([(h, c1) for h, _, c1 in linhas if c1 is not None]), 4)}}
    r["decisao"] = decidir(a, prio)
    (destino / "resultado.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0


def principal(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("poder")
    sub.add_parser("sortear")
    m = sub.add_parser("medir")
    m.add_argument("--planilha", default=str(PASTA_LEITURA / "rotulos.csv"))
    args = ap.parse_args(argv)
    p.configurar("v3")
    return {"poder": cmd_poder, "sortear": cmd_sortear, "medir": cmd_medir}[args.comando](args)


if __name__ == "__main__":
    sys.exit(principal())
