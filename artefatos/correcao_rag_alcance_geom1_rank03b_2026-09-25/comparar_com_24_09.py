"""C6.5 da correção RAG: a nova busca (25/09) contra a publicada em 24/09.

Lê só as duas saídas publicadas, que não contêm valores, e publica booleanos e
contagens. As expectativas foram fixadas no contrato antes de rodar a busca:
`resultados/contratos_correcao_rag_alcance_geom1_rank03b_2026-09-25.md`, C6.3.
Os nomes `_x1000`/`_div1000` de 24/09 viraram `_vezes_mil`/`_sobre_mil` no
adendo de 25/09 (B1) e são normalizados antes de comparar.

Execute da raiz: .venv/bin/python <este arquivo> > <saída>
"""
import hashlib
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PUBLICADA = RAIZ / "artefatos/alcance_geom1_rank03b_2026-09-24/revisao/conferencia_revisao.json"
PUBLICADA_SHA256 = "c19682bfde33480a66caeb088503f098360aebce57b6070a539f5f97a28eb3a3"
NOVA = Path(__file__).resolve().parent / "busca/conferencia_revisao.json"
MODOS = ("-layout", "-raw")


def _nome(chave: str) -> str:
    return chave.replace("_x1000", "_vezes_mil").replace("_div1000", "_sobre_mil")


def _posicoes(ocorrencias: dict) -> dict:
    return {_nome(k): [(a["pagina"], a["linha"], a["coluna"], a["tokens"]) for a in v]
            for k, v in ocorrencias.items()}


def _trechos(ocorrencias: dict) -> dict:
    return {_nome(k): [a.get("trecho", a.get("trecho_omitido")) for a in v] for k, v in ocorrencias.items()}


def main() -> dict:
    dados = PUBLICADA.read_bytes()
    if hashlib.sha256(dados).hexdigest() != PUBLICADA_SHA256:
        raise AssertionError("saída de 24/09 diferente da publicada")
    antiga, nova = json.loads(dados), json.loads(NOVA.read_text())
    if [d["id_doc"] for d in antiga["documentos"]] != [d["id_doc"] for d in nova["documentos"]]:
        raise AssertionError("universos diferentes")
    documentos = []
    for velho, novo in zip(antiga["documentos"], nova["documentos"]):
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
                "fco_mesmas_paginas": {_nome(k): x for k, x in v["fco_paginas"].items()} == n["fco_paginas"],
                "fco_paginas_com_correspondencia": sorted({p for x in n["fco_paginas"].values() for p in x}),
                "tokens_fora_da_gramatica": sum(n["tokens_fora_da_gramatica_por_pagina"].values()),
                "paginas_com_token_fora_da_gramatica": len(n["tokens_fora_da_gramatica_por_pagina"]),
                "tokens_com_sinal_ambiguo": sum(n["tokens_com_sinal_ambiguo_por_pagina"].values()),
                # A saída de 24/09 não tinha este campo (entrou no B2): publica-se o
                # novo, sem comparar — comparar com um padrão seria aprovar por ausência.
                "paginas_com_pouco_texto_na_nova": n["paginas_com_pouco_texto"],
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
    todos_os_modos = [m for d in documentos for m in d["modos"].values()]
    esperado = {
        "ativo_140867_nas_mesmas_paginas_e_linhas": all(
            m["ativo_mesmas_paginas_e_linhas"] and m["ativo_ocorrencias"] > 0 for m in por_id["140867"]["modos"].values()),
        "nenhuma_ocorrencia_ambigua_do_ativo": all(m["ativo_ambiguos"] == 0 for m in todos_os_modos),
        "fco_dos_dois_e_ativo_de_142900_sem_correspondencia": (
            all(not m["fco_paginas_com_correspondencia"] for m in todos_os_modos)
            and all(m["ativo_ocorrencias"] == 0 for m in por_id["142900"]["modos"].values())),
        "coluna_so_mudaria_pelo_novo_sentido": all(m["ativo_mesmas_colunas_e_tokens"] for m in todos_os_modos),
    }
    return {"sentido": "nova busca de 25/09 contra a publicada em 24/09; só booleanos e contagens",
            "publicada_sha256": PUBLICADA_SHA256,
            "nova_sha256": hashlib.sha256(NOVA.read_bytes()).hexdigest(),
            "documentos": documentos, "expectativas_do_contrato_c6_3": esperado,
            "todas_as_expectativas_cumpridas": all(esperado.values())}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
