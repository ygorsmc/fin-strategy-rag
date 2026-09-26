"""Adendo da correção RAG (C6.5, A8b): uma execução da busca contra outra já publicada.

Lê só as duas saídas publicadas, que não contêm valores, e publica booleanos e
contagens. A referência é conferida pelo hash registrado. As expectativas foram
fixadas no adendo antes de rodar
(`resultados/adendo_correcao_rag_alcance_geom1_rank03b_2026-09-25.md`, Execução).
Os nomes `_x1000`/`_div1000` de 24/09 viraram `_vezes_mil`/`_sobre_mil` no adendo de
25/09 (B1) e são normalizados antes de comparar.

Uso, da raiz: .venv/bin/python <este arquivo> REFERENCIA SHA256_DA_REFERENCIA NOVA > <saída>
"""
import hashlib
import json
from pathlib import Path
import sys

MODOS = ("-layout", "-raw")
MUDANCA_DE_SENTIDO = {
    "coluna": ("Desde a correção RAG, ordem do token entre todos os tokens numéricos da linha, aceitos ou "
               "recusados. Na busca de 24/09, ordem entre os casamentos da expressão antiga, que partia token "
               "malformado em pedaços; as duas só diferem em linha com token assim."),
    "tokens": ("Desde a correção RAG, quantos tokens numéricos a linha tem, aceitos ou recusados. Na busca de "
               "24/09, quantos casamentos da expressão antiga."),
}


def _nome(chave: str) -> str:
    return chave.replace("_x1000", "_vezes_mil").replace("_div1000", "_sobre_mil")


def _posicoes(ocorrencias: dict) -> dict:
    return {_nome(k): [(a["pagina"], a["linha"], a["coluna"], a["tokens"]) for a in v]
            for k, v in ocorrencias.items()}


def _trechos(ocorrencias: dict) -> dict:
    return {_nome(k): [a.get("trecho", a.get("trecho_omitido")) for a in v] for k, v in ocorrencias.items()}


def comparar(referencia: Path, referencia_sha256: str, nova: Path) -> dict:
    dados = referencia.read_bytes()
    if hashlib.sha256(dados).hexdigest() != referencia_sha256:
        raise AssertionError("referência diferente da publicada")
    antiga, atual = json.loads(dados), json.loads(nova.read_text())
    if [d["id_doc"] for d in antiga["documentos"]] != [d["id_doc"] for d in atual["documentos"]]:
        raise AssertionError("universos diferentes")
    documentos = []
    for velho, novo in zip(antiga["documentos"], atual["documentos"]):
        modos = {}
        for modo in MODOS:
            v, n = velho["modos"][modo], novo["modos"][modo]
            pv, pn = _posicoes(v["ativo"]), _posicoes(n["ativo"])
            modos[modo] = {
                "paginas_iguais": v["paginas"] == n["paginas"],
                "ativo_mesmas_paginas_e_linhas": ({k: [x[:2] for x in lst] for k, lst in pv.items()}
                                                  == {k: [x[:2] for x in lst] for k, lst in pn.items()}),
                "ativo_mesmas_colunas_e_tokens": pv == pn,
                "ativo_mesmos_trechos": _trechos(v["ativo"]) == _trechos(n["ativo"]),
                "ativo_ocorrencias": sum(len(x) for x in pn.values()),
                "ativo_ambiguos": sum(len(x) for x in n["ativo_modulo_com_sinal_ambiguo"].values()),
                "ativo_ambiguos_na_referencia": (sum(len(x) for x in v["ativo_modulo_com_sinal_ambiguo"].values())
                                                 if "ativo_modulo_com_sinal_ambiguo" in v else None),
                "fco_mesmas_paginas": {_nome(k): x for k, x in v["fco_paginas"].items()} == n["fco_paginas"],
                "fco_paginas_com_correspondencia": sorted({p for x in n["fco_paginas"].values() for p in x}),
                "tokens_fora_da_gramatica": sum(n["tokens_fora_da_gramatica_por_pagina"].values()),
                "tokens_fora_da_gramatica_na_referencia": (
                    sum(v["tokens_fora_da_gramatica_por_pagina"].values())
                    if "tokens_fora_da_gramatica_por_pagina" in v else None),
                "tokens_com_sinal_ambiguo": sum(n["tokens_com_sinal_ambiguo_por_pagina"].values()),
                "tokens_com_sinal_ambiguo_na_referencia": (
                    sum(v["tokens_com_sinal_ambiguo_por_pagina"].values())
                    if "tokens_com_sinal_ambiguo_por_pagina" in v else None),
                "paginas_com_pouco_texto": n["paginas_com_pouco_texto"],
            }
        documentos.append({
            "id_doc": novo["id_doc"], "modos": modos,
            "modos_concordam": [velho["modos_concordam"], novo["modos_concordam"]],
            "identidade_de_caixa_igual": (velho["identidade_saldo_final_dfc_igual_caixa_bp"]
                                          == novo["identidade_saldo_final_dfc_igual_caixa_bp"]),
            "reinventario_igual": velho["reinventario_mascara_r4"] == novo["reinventario_mascara_r4"],
            "xml_e_pdf_iguais": (velho["xml_sha256"], velho["pdf_sha256"]) == (novo["xml_sha256"], novo["pdf_sha256"]),
            "ativo_formas_que_so_casam_com_decimais": novo["ativo_formas_que_so_casam_com_decimais"],
        })
    por_id = {d["id_doc"]: d for d in documentos}
    todos = [m for d in documentos for m in d["modos"].values()]
    esperado = {
        "ativo_140867_nas_mesmas_paginas_linhas_colunas_e_trechos": all(
            m["ativo_mesmas_colunas_e_tokens"] and m["ativo_mesmos_trechos"] and m["ativo_ocorrencias"] > 0
            for m in por_id["140867"]["modos"].values()),
        "nenhuma_ocorrencia_ambigua_do_ativo": all(m["ativo_ambiguos"] == 0 for m in todos),
        "fco_dos_dois_e_ativo_de_142900_sem_correspondencia": (
            all(not m["fco_paginas_com_correspondencia"] for m in todos)
            and all(m["ativo_ocorrencias"] == 0 for m in por_id["142900"]["modos"].values())),
    }
    return {"sentido": "execução nova contra a publicada; só booleanos e contagens",
            "referencia": str(referencia.relative_to(Path(__file__).resolve().parents[3])),
            "referencia_sha256": referencia_sha256, "nova_sha256": hashlib.sha256(nova.read_bytes()).hexdigest(),
            "mudanca_de_sentido": MUDANCA_DE_SENTIDO, "sentido_de_coluna_na_nova": atual.get("sentido_de_coluna"),
            "documentos": documentos, "expectativas_do_adendo": esperado,
            "todas_as_expectativas_cumpridas": all(esperado.values())}


if __name__ == "__main__":
    referencia, sha, nova = sys.argv[1:]
    print(json.dumps(comparar(Path(referencia).resolve(), sha, Path(nova).resolve()), ensure_ascii=False, indent=2))
