"""Modelo final do CAND-02-P (destilação do leitor Claude) e o que o M aprendeu.

    python -m scripts.cand02p_modelo_final treinar      # M final nos 64 pares rotulados
    python -m scripts.cand02p_modelo_final importancia  # queda de nDCG@10 por grupo de atributos

**Treinar.** Mesmos atributos e hiperparâmetros do M do v3, agora nos 64 pares
rotulados pelo Claude (v1: 16, v2: 14, v3: 34; treino e teste juntos). É o
modelo para uso. Por construção não tem métrica própria: **o desempenho de
referência é o do teste do v3** (`artefatos/cand02p_v3/resultado_teste.json`),
medido com o M congelado antes de existir rótulo de teste.

**Importância.** Usa o M **congelado do v3** no teste do v3. Embaralha, dentro
de cada par, as colunas de um grupo de atributos e mede quanto cai o nDCG@10
macro contra o rótulo do Claude, em 10 repetições com semente fixa. É
descritivo. Grupos correlacionados dividem o crédito entre si, então a queda
mede o que o modelo perde sem o grupo, não a importância "verdadeira".
"""

from __future__ import annotations

import argparse
import json
import pickle
import random
import statistics
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import cand02p_piloto as p  # noqa: E402
from src import redline as rl  # noqa: E402

DESTINO_FINAL = RAIZ / "artefatos" / "cand02p_final"
PILOTOS = ((RAIZ / "artefatos" / "cand02p", ("treino", "teste")),
           (RAIZ / "artefatos" / "cand02p_v2", ("treino", "teste")),
           (RAIZ / "artefatos" / "cand02p_v3", ("treino", "teste")))
ANCORAS_CURTAS = ("guidance", "politica_contabil", "capital_basileia", "inadimplencia_provisao", "perimetro",
                  "risco_contingencia", "dividendos_recompra", "inversao_tendencia", "metodologia_indicador",
                  "nao_recorrente")
NOMES = (["op_alteracao", "op_adicao", "op_remocao", "tipo_tabela", "b1_nivel1", "b1_nivel2", "b1_nivel3",
          "n_categorias"] + [f"cat_{c}" for c in sorted(rl.CATEGORIAS)]
         + ["reapresentacao", "negacao_modal", "moeda", "max_bp", "max_variacao_relativa", "muda_sinal",
            "muda_ordem_grandeza", "n_mudancas_numericas", "log_massa", "distancia", "pagina_relativa",
            "log_pagina", "log_tamanho_texto"] + [f"sim_{a}" for a in ANCORAS_CURTAS] + ["score_c"])
GRUPOS = {
    "operacao_e_tipo": ["op_alteracao", "op_adicao", "op_remocao", "tipo_tabela"],
    "regras_do_b1": ["b1_nivel1", "b1_nivel2", "b1_nivel3"],
    "categorias_lexicais": ["n_categorias"] + [f"cat_{c}" for c in sorted(rl.CATEGORIAS)]
                           + ["reapresentacao", "negacao_modal", "moeda"],
    "mudanca_numerica": ["max_bp", "max_variacao_relativa", "muda_sinal", "muda_ordem_grandeza", "n_mudancas_numericas"],
    "tamanho_e_posicao": ["log_massa", "distancia", "pagina_relativa", "log_pagina", "log_tamanho_texto"],
    "similaridade_semantica_c": [f"sim_{a}" for a in ANCORAS_CURTAS] + ["score_c"],
}


def dados_rotulados() -> tuple[list, list, dict]:
    X, y, por_par = [], [], {}
    for destino, papeis in PILOTOS:
        with p._Em(destino):
            resumo = json.load(open(p.DESTINO / "resumo_eventos.json"))["pares"]
            for par, info in sorted(resumo.items()):
                if info["papel"] not in papeis:
                    continue
                rot = p.consolidar(info["papel"], par)
                eventos = {e["id"]: e for e in p.ler_eventos(par)}
                c = p._c_do_par(par)
                usados = [(i, r) for i, r in rot.items() if r["julgavel"]]
                por_par[f"{destino.name}/{par}"] = len(usados)
                X += [p.features(eventos[i], c[i]) for i, _ in usados]
                y += [r["ganho"] for _, r in usados]
    return X, y, por_par


def cmd_treinar(_args) -> int:
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor

    pasta = DESTINO_FINAL / "modelo"
    if (pasta / "congelado.json").exists():
        raise SystemExit("o modelo final já está congelado")
    X, y, por_par = dados_rotulados()
    modelo = HistGradientBoostingRegressor(**p.HIPERPARAMETROS_M).fit(np.asarray(X, float), np.asarray(y))
    pasta.mkdir(parents=True, exist_ok=True)
    with open(pasta / "m.pkl", "wb") as f:
        pickle.dump(modelo, f)
    congelado = {"pares": len(por_par), "observacoes": len(y), "observacoes_por_par": por_par,
                 "hiperparametros": p.HIPERPARAMETROS_M, "atributos": NOMES,
                 "desempenho_de_referencia": "teste do v3 (artefatos/cand02p_v3/resultado_teste.json); este modelo não tem teste próprio",
                 "m_pkl_sha256": p.sha256_arquivo(pasta / "m.pkl"),
                 "script_sha256": p.sha256_arquivo(Path(__file__)),
                 "piloto_sha256": p.sha256_arquivo(RAIZ / "scripts" / "cand02p_piloto.py"),
                 "redline_sha256": p.sha256_arquivo(RAIZ / "src" / "redline.py")}
    (pasta / "congelado.json").write_text(json.dumps(congelado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in congelado.items() if k not in ("observacoes_por_par", "atributos")}, indent=2))
    return 0


def _teste_v3() -> list[dict]:
    pares = []
    with p._Em(PILOTOS[2][0]):
        resumo = json.load(open(p.DESTINO / "resumo_eventos.json"))["pares"]
        for par, info in sorted(resumo.items()):
            if info["papel"] != "teste":
                continue
            rot = p.consolidar("teste", par)
            excluidos = {i for i, r in rot.items() if not r["julgavel"]}
            eventos = [e for e in p.ler_eventos(par) if e["id"] not in excluidos]
            c = p._c_do_par(par)
            pares.append({"eventos": eventos, "X": [p.features(e, c[e["id"]]) for e in eventos],
                          "ganhos": {i: r["ganho"] for i, r in rot.items() if r["julgavel"]}})
    return pares


def _ndcg10_macro(modelo, pares, X_por_par) -> float:
    import numpy as np

    valores = []
    for t, X in zip(pares, X_por_par):
        prev = modelo.predict(np.asarray(X, float))
        ordem = [e["id"] for e, _ in sorted(zip(t["eventos"], prev), key=lambda z: (-z[1], z[0]["rank_b1"]))]
        valores.append(rl.ndcg(ordem, t["ganhos"], 10))
    return statistics.fmean(v for v in valores if v is not None)


def cmd_importancia(_args) -> int:
    with open(PILOTOS[2][0] / "modelo" / "m.pkl", "rb") as f:
        modelo = pickle.load(f)
    pares = _teste_v3()
    base = _ndcg10_macro(modelo, pares, [t["X"] for t in pares])
    oficial = json.load(open(PILOTOS[2][0] / "resultado_teste.json"))["macro"]["m"]["ndcg10"]
    if abs(base - oficial) > 1e-9:
        raise SystemExit(f"o nDCG@10 recalculado ({base}) não reproduz o publicado ({oficial})")
    al = random.Random(f"{p.SEMENTE}:importancia")
    saida = {}
    for grupo, nomes in GRUPOS.items():
        cols = [NOMES.index(n) for n in nomes]
        quedas = []
        for _ in range(10):
            X_perm = []
            for t in pares:
                linhas = [list(x) for x in t["X"]]
                ordem = list(range(len(linhas)))
                al.shuffle(ordem)
                X_perm.append([[linhas[ordem[i]][j] if j in cols else v for j, v in enumerate(linha)]
                               for i, linha in enumerate(linhas)])
            quedas.append(base - _ndcg10_macro(modelo, pares, X_perm))
        saida[grupo] = {"queda_media_ndcg10": round(statistics.fmean(quedas), 4),
                        "min": round(min(quedas), 4), "max": round(max(quedas), 4), "atributos": len(cols)}
    r = {"aviso": "descritivo; M congelado do v3 no teste do v3, contra o rótulo do Claude",
         "ndcg10_base": round(base, 4), "grupos": dict(sorted(saida.items(), key=lambda kv: -kv[1]["queda_media_ndcg10"]))}
    DESTINO_FINAL.mkdir(parents=True, exist_ok=True)
    (DESTINO_FINAL / "importancia.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0


def principal(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("treinar")
    sub.add_parser("importancia")
    args = ap.parse_args(argv)
    return {"treinar": cmd_treinar, "importancia": cmd_importancia}[args.comando](args)


if __name__ == "__main__":
    sys.exit(principal())
