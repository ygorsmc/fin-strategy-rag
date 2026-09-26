"""Auditoria estrutural, somente leitura e memória; não calcula y real."""
import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd

from scripts import auditar_rank03b_consumo_operacional as a
from scripts import fonte_zip_cvm as fz
from scripts import gates_painel_pesquisa_rank03b as g
from scripts import painel_pesquisa_rank03b as pp
from scripts import verificacoes_revisao_final_rank03b as v


def proibido(*args, **kwargs):
    raise AssertionError("Esta revisão não permite calcular rótulo real")


a._somas_do_rotulo = proibido
base = Path("artefatos/painel_pesquisa_rank03b")
con = duckdb.connect(":memory:")
zips = fz.extrair(con)
compartilhado = pp.preparar_universo(con)
correcoes = g.carregar_correcoes(g.CORRECOES)
p = pp.construir(con, correcoes)
provas = g.datas_das_provas(con, correcoes)
falsificacoes = g.verificar_falsificacoes(p, con, provas)
medido = g.medir(p, g.documentos_decididos(g.ADJUDICACAO), provas)
salvo = json.loads((base / "gates_g0_g1.json").read_text())
verificacao = json.loads((base / "verificacoes_revisao_final.json").read_text())
saida = {
    "zips_conferidos": len(zips),
    "compartilhado_sha256": compartilhado,
    "digest_reconstruido": p.digest,
    "digest_confere": p.digest == salvo["digest_do_painel"],
    "falsificacoes": falsificacoes,
    "cadeia_confere": json.loads(json.dumps(medido["cadeia"], default=str)) == salvo["cadeia"],
    "resumo_gates": {
        "veredito": medido["veredito"],
        "g0_3_saltos": medido["cadeia"][0]["g0_3_saltos_de_escala"],
        "g1_observacoes": medido["cadeia"][1]["observacoes"],
        "g1_companhias": medido["cadeia"][1]["companhias"],
        "g1_4": medido["cadeia"][1]["g1_4_prova_de_escala_publicada_depois_de_D"],
        "g05": medido["cadeia"][0]["diagnostico_g0_5_proposto"],
    },
    "versao_verificacao_confere": v.ligacao_de_versao(base, g.CORRECOES) == verificacao["versao"],
    "hashes_codigo_verificacao": {
        caminho: hashlib.sha256(Path(caminho).read_bytes()).hexdigest() == esperado
        for caminho, esperado in verificacao["codigo_sha256"].items()
    },
}
# Comparação exaustiva das três tabelas, nos dois sentidos.
con.execute("ATTACH 'artefatos/painel_pesquisa_rank03b/painel.duckdb' AS salvo (READ_ONLY)")
diferencas = {}
for nome in pp.TABELAS:
    con.register("_reconstruida", pd.DataFrame(getattr(p, nome)))
    diferencas[nome] = con.execute(f"""
        SELECT count(*) FROM (
          (SELECT * FROM _reconstruida EXCEPT ALL SELECT * FROM salvo.{nome})
          UNION ALL
          (SELECT * FROM salvo.{nome} EXCEPT ALL SELECT * FROM _reconstruida)
        )
    """).fetchone()[0]
    con.unregister("_reconstruida")
saida["diferencas_linhas_persistidas"] = diferencas
# P4/P6 independentemente: datas da prova consultadas pelo ID na origem.
receb = dict(con.execute("SELECT id_doc, max(dt_receb) FROM cadastro GROUP BY id_doc").fetchall())
limites = {}
for chave, r in correcoes.items():
    ids = [r["id_doc"]] if r["base"] == "corrigida_documento" else [i["id_doc"] for i in json.loads(r["pontas"])]
    limites[chave] = max(receb[i] for i in ids)
saida["datas_das_provas_conferem"] = provas == limites
saida["ativos_antes_da_prova"] = sum(
    row["disponivel_em"] < limites[(row["cd_cvm"], row["conjunto"], row["dt_refer"], row["versao"])]
    for row in p.ativo
    if (row["cd_cvm"], row["conjunto"], row["dt_refer"], row["versao"]) in limites
)
saida["esc_0101_anterior"] = [
    {k: row[k] for k in ("cd_cvm", "id_doc", "valor_bruto", "valor_reais", "escala_aplicada", "base_escala")}
    for row in p.ativo if row["id_doc"] == "152742"
]
print(json.dumps(saida, indent=2, ensure_ascii=False, default=str))
