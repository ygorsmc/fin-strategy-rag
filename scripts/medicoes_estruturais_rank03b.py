"""Medições estruturais dos lotes B e C do Rank 3-B, reproduzíveis.

Existe por causa da auditoria de conformidade de 2026-09-16 (achado B6):
vários números dos relatórios vinham de consultas avulsas, sem script nem
artefato. Este script refaz todas elas e grava
`artefatos/painel_pesquisa_rank03b/medicoes_estruturais.json`.

**Só estrutura** (O1): contagens de documentos, contas, versões, identidades e
reprodutibilidade. Nenhum valor de FCO é publicado; nenhum rótulo é somado.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import duckdb

from scripts import fonte_zip_cvm as fz
from scripts import painel_pesquisa_rank03b as pp
from scripts import piloto_fonte_rad_rank03b as piloto
from scripts.esqueleto_plano_padrao import documentos_defeituosos

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "artefatos" / "painel_pesquisa_rank03b" / "medicoes_estruturais.json"
PAINEL = RAIZ / "artefatos" / "cvm_treino.duckdb"
CODIGO = ("scripts/medicoes_estruturais_rank03b.py", "scripts/fonte_zip_cvm.py",
          "scripts/painel_pesquisa_rank03b.py", "scripts/piloto_fonte_rad_rank03b.py")


def _um(con, sql, *args):
    return con.execute(sql, list(args)).fetchone()


def _todos(con, sql, *args):
    return con.execute(sql, list(args)).fetchall()


def fonte(con) -> dict:
    """M1 do lote B: contas, descrições, escala, métodos, rótulos e versões."""
    con.execute("CREATE OR REPLACE TEMP TABLE u AS SELECT d.* FROM declaracoes d JOIN universo USING (cd_cvm)")
    saida = {
        "companhias_no_universo": _um(con, "SELECT count(*) FROM universo")[0],
        "conta_fixa": {c: dict(_todos(con, "SELECT conta_fixa, count(*) FROM u WHERE cd_conta = ? GROUP BY 1", c))
                       for c in ("6.01", "1", "2")},
        "descricoes_6_01": [
            {"descricao": d, "linhas": n, "companhias": c}
            for d, n, c in _todos(con, """SELECT ds_conta, count(*), count(DISTINCT cd_cvm) FROM u
                WHERE cd_conta = '6.01' AND ordem = 'ÚLTIMO' GROUP BY 1 ORDER BY 2 DESC""")
        ],
        "companhias_com_6_01_de_seguradora": [
            {"cd_cvm": c, "plano_contas": p} for c, p in _todos(con, """SELECT DISTINCT u.cd_cvm, x.plano_contas
                FROM u JOIN universo x USING (cd_cvm) WHERE u.ds_conta LIKE '%Segurad%' ORDER BY 1""")
        ],
        "companhias_por_plano": dict(_todos(con, "SELECT plano_contas, count(*) FROM universo GROUP BY 1 ORDER BY 2 DESC")),
        "documentos_com_mais_de_uma_escala": _um(con, """SELECT count(*) FROM (SELECT cd_cvm, conjunto, dt_refer, versao
            FROM u GROUP BY ALL HAVING count(DISTINCT escala) > 1)""")[0],
        "documentos_na_fonte": _um(con, "SELECT count(*) FROM (SELECT DISTINCT cd_cvm, conjunto, dt_refer, versao FROM u)")[0],
        "documentos_com_dfc_md_e_dfc_mi": _um(con, """SELECT count(*) FROM (SELECT cd_cvm, conjunto, dt_refer, versao
            FROM u WHERE cd_conta = '6.01' GROUP BY ALL HAVING count(DISTINCT demonstrativo) > 1)""")[0],
        "companhias_que_trocam_de_metodo": _um(con, """SELECT count(*) FROM (SELECT cd_cvm FROM u
            WHERE cd_conta = '6.01' GROUP BY 1 HAVING count(DISTINCT demonstrativo) > 1)""")[0],
        "ativo_ate_1": {
            "zerado_ou_negativo": _um(con, "SELECT count(*) FROM u WHERE cd_conta='1' AND demonstrativo='BPA' AND ordem='ÚLTIMO' AND vl <= 0")[0],
            "entre_0_e_1": _um(con, "SELECT count(*) FROM u WHERE cd_conta='1' AND demonstrativo='BPA' AND ordem='ÚLTIMO' AND vl > 0 AND vl <= 1")[0],
        },
        "identidades_contabeis": pp.identidades_contabeis(con),
    }
    cad = "SELECT c.* FROM cadastro c JOIN universo USING (cd_cvm)"
    saida["versoes"] = {
        "documentos": _um(con, f"SELECT count(*) FROM (SELECT DISTINCT cd_cvm, conjunto, dt_refer FROM ({cad}))")[0],
        "com_mais_de_uma_versao": _um(con, f"""SELECT count(*) FROM (SELECT cd_cvm, conjunto, dt_refer FROM ({cad})
            GROUP BY ALL HAVING count(DISTINCT versao) > 1)""")[0],
        "versoes_antigas": _um(con, f"""SELECT sum(n - 1) FROM (SELECT count(DISTINCT versao) n FROM ({cad})
            GROUP BY cd_cvm, conjunto, dt_refer HAVING count(DISTINCT versao) > 1)""")[0],
        "numero_em_maos_e_a_versao_maxima": dict(zip(("iguais", "total"), _um(con, f"""
            SELECT sum(CASE WHEN x.v = m.vmax THEN 1 ELSE 0 END), count(*) FROM
            (SELECT cd_cvm, conjunto, dt_refer, max(versao) v FROM u GROUP BY ALL) x
            JOIN (SELECT cd_cvm, conjunto, dt_refer, max(versao) vmax FROM ({cad}) GROUP BY ALL) m
            USING (cd_cvm, conjunto, dt_refer)"""))),
        "dias_entre_v1_e_vmax": dict(zip(("mediana", "p90", "maximo"), _um(con, f"""
            SELECT median(d), quantile_cont(d, 0.9), max(d) FROM (
            SELECT max(dt_receb) - min(dt_receb) d FROM ({cad})
            GROUP BY cd_cvm, conjunto, dt_refer HAVING count(DISTINCT versao) > 1)"""))),
    }
    return saida


def rotulos_de_escala(con) -> dict:
    """Perfis de rótulo por companhia, trechos e fronteiras (base do escopo S4)."""
    piloto.preparar(con, PAINEL)
    adjudicados = {(c, j, d, v) for c, j, d, v in documentos_defeituosos()}
    fronteiras = _todos(con, """SELECT cd_cvm, conjunto, CAST(dt_refer AS VARCHAR), versao, escala FROM docs
        WHERE escala <> escala_anterior OR escala <> escala_seguinte""")
    return {
        "companhias_por_perfil": dict(_todos(con, """SELECT CASE WHEN rotulos > 1 THEN 'mista'
            ELSE 'so_' || rotulo_da_companhia END, count(DISTINCT cd_cvm) FROM docs GROUP BY 1""")),
        "documentos_em_companhias_mistas": _um(con, "SELECT count(*) FROM docs WHERE rotulos > 1")[0],
        "documentos_em_companhias_so_unidade": _um(con, "SELECT count(*) FROM docs WHERE rotulos = 1 AND rotulo_da_companhia = 'UNIDADE'")[0],
        "trechos_em_companhias_mistas": dict(zip(("trechos", "de_um_documento"), _um(con, """
            SELECT count(*), sum(CASE WHEN n = 1 THEN 1 ELSE 0 END) FROM
            (SELECT cd_cvm, trecho, count(*) n FROM docs WHERE rotulos > 1 GROUP BY ALL)"""))),
        "fronteiras": {
            "documentos": len(fronteiras),
            "por_escala": dict(_todos(con, """SELECT escala, count(*) FROM docs
                WHERE escala <> escala_anterior OR escala <> escala_seguinte GROUP BY 1""")),
            "ja_adjudicadas_pelo_inventario_v2": sum(1 for r in fronteiras if r[:4] in adjudicados),
        },
    }


def painel_compartilhado_contra_a_fonte(con) -> dict:
    """As linhas arquivadas do `cvm_treino.duckdb` conferidas contra os ZIPs."""
    con.execute(f"ATTACH '{PAINEL}' AS pc (READ_ONLY)")
    saida = {}
    for nome, conta, dem in (("fco", "6.01", "DFC%"), ("ativo", "1", "BPA")):
        z = f"""SELECT d.cd_cvm, d.conjunto, d.dt_refer, d.versao, d.dt_ini, d.dt_fim, d.vl
                FROM declaracoes d JOIN universo USING (cd_cvm)
                WHERE d.cd_conta = '{conta}' AND d.demonstrativo LIKE '{dem}' AND d.ordem = 'ÚLTIMO'"""
        p = f"""SELECT f.cd_cvm, f.conjunto, f.dt_refer, f.versao_documento, f.dt_ini_exerc, f.dt_fim_exerc, f.vl_conta
                FROM pc.fatos_contabeis f JOIN universo USING (cd_cvm)
                WHERE f.cd_conta = '{conta}' AND f.demonstrativo LIKE '{dem}' AND f.origem = 'arquivado'"""
        chaves_z = f"SELECT DISTINCT cd_cvm, conjunto, dt_refer, versao, dt_ini, dt_fim FROM ({z})"
        chaves_p = f"SELECT DISTINCT cd_cvm, conjunto, dt_refer, versao_documento, dt_ini_exerc, dt_fim_exerc FROM ({p})"
        ausentes = _todos(con, f"SELECT * FROM ({chaves_z} EXCEPT {chaves_p})")
        com_outro_documento = sum(
            1 for c, _, _, _, i, f in ausentes
            if _um(con, """SELECT count(*) FROM pc.fatos_contabeis WHERE cd_cvm = ? AND cd_conta = ?
                AND origem = 'arquivado' AND dt_fim_exerc = ? AND dt_ini_exerc IS NOT DISTINCT FROM ?""",
                   c, conta, f, i)[0])
        saida[nome] = {
            "linhas_na_fonte": _um(con, f"SELECT count(*) FROM ({z})")[0],
            "linhas_no_painel_compartilhado": _um(con, f"SELECT count(*) FROM ({p})")[0],
            "linhas_duplicadas_na_fonte": _um(con, f"SELECT count(*) - count(DISTINCT (cd_cvm, conjunto, dt_refer, versao, dt_ini, dt_fim, vl)) FROM ({z})")[0],
            "linhas_do_painel_ausentes_da_fonte": _um(con, f"SELECT count(*) FROM ({p} EXCEPT ALL {z})")[0],
            "chaves_da_fonte_ausentes_do_painel": len(ausentes),
            "das_quais_o_painel_tem_por_outro_documento": com_outro_documento,
            "sem_nenhum_documento_no_painel": [
                {"cd_cvm": c, "conjunto": j, "dt_refer": str(d), "dt_ini": str(i), "dt_fim": str(f)}
                for c, j, d, _, i, f in sorted(ausentes, key=lambda r: tuple(map(str, r)))
                if not _um(con, """SELECT count(*) FROM pc.fatos_contabeis WHERE cd_cvm = ? AND cd_conta = ?
                    AND origem = 'arquivado' AND dt_fim_exerc = ? AND dt_ini_exerc IS NOT DISTINCT FROM ?""",
                           c, conta, f, i)[0]
            ],
        }
    con.execute("DETACH pc")
    return saida


def classificacao_n2() -> dict:
    """Os grupos N2 do recorte do levantamento, por causa (reprodução do §7.2 dele)."""
    from src.dados_estruturados import _derivar_trimestres_intermediarios

    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{PAINEL}' AS p (READ_ONLY)")
    for tabela in ("companhias", "mapa_contas"):
        con.execute(f"CREATE TABLE {tabela} AS SELECT * FROM p.{tabela}")
    con.execute("""CREATE TABLE fatos_contabeis AS SELECT * FROM p.fatos_contabeis
        WHERE origem = 'arquivado' AND demonstrativo IN ('DRE', 'DFC_MD', 'DFC_MI')""")

    class Reter:
        def execute(self, sql, *args):
            if sql.strip() == "DROP TABLE _candidatos_intermediarios":
                return con
            return con.execute(sql, *args)

    _derivar_trimestres_intermediarios(Reter())
    con.execute("""CREATE TEMP TABLE n2 AS SELECT g.cd_cvm, g.demonstrativo, g.trimestre,
        any_value(g.dt_ini_exerc) ini, any_value(g.dt_fim_exerc) fim
        FROM _candidatos_intermediarios g JOIN companhias c USING (cd_cvm)
        WHERE NOT c.is_banco AND c.plano_contas NOT LIKE 'll3_09_%'
          AND g.demonstrativo IN ('DFC_MD', 'DFC_MI') AND g.chave_pareamento LIKE 'conta:6.01|%'
        GROUP BY 1, 2, 3 HAVING NOT bool_or(g.tem_antecedente)""")
    antecedente = """SELECT 1 FROM p.fatos_contabeis f WHERE f.cd_cvm = n2.cd_cvm
        AND f.origem = 'arquivado' AND f.cd_conta = '6.01' AND f.demonstrativo IN ('DFC_MD', 'DFC_MI')
        AND f.dt_ini_exerc = n2.ini AND f.dt_fim_exerc < n2.fim"""
    total, companhias = _um(con, "SELECT count(*), count(DISTINCT cd_cvm) FROM n2")
    return {
        "grupos": total, "companhias": companhias,
        "antecedente_no_outro_metodo": _um(con, f"SELECT count(*) FROM n2 WHERE EXISTS ({antecedente} AND f.demonstrativo <> n2.demonstrativo)")[0],
        "antecedente_no_mesmo_metodo": _um(con, f"SELECT count(*) FROM n2 WHERE EXISTS ({antecedente} AND f.demonstrativo = n2.demonstrativo)")[0],
        "sem_antecedente_no_exercicio": _um(con, f"SELECT count(*) FROM n2 WHERE NOT EXISTS ({antecedente})")[0],
    }


def reprodutibilidade(correcoes: dict | None) -> dict:
    """R2: duas construções independentes, digest comparado."""
    digests = []
    for _ in range(2):
        con = duckdb.connect(":memory:")
        fz.extrair(con)
        pp.preparar_universo(con)
        digests.append(pp.construir(con, correcoes).digest["conjunto"])
    return {"digests": digests, "identicos": digests[0] == digests[1]}


def executar(destino: Path = DESTINO) -> dict:
    from scripts import gates_painel_pesquisa_rank03b as gates

    con = duckdb.connect(":memory:")
    zips = fz.extrair(con)
    pp.preparar_universo(con)
    resultado = {
        "zips_sha256": zips,
        "codigo_sha256": {c: hashlib.sha256((RAIZ / c).read_bytes()).hexdigest() for c in CODIGO},
        "fonte": fonte(con),
        "painel_compartilhado_contra_a_fonte": painel_compartilhado_contra_a_fonte(con),
        "rotulos_de_escala": rotulos_de_escala(con),
        "n2_no_recorte_do_candidato": classificacao_n2(),
        "reprodutibilidade": {
            "sem_correcoes": reprodutibilidade(None),
            "com_correcoes": reprodutibilidade(gates.carregar_correcoes(gates.CORRECOES)),
        },
    }
    piloto._sem_chave_proibida(resultado)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True, default=str),
                       encoding="utf-8")
    return resultado


if __name__ == "__main__":
    r = executar()
    print(json.dumps({k: r[k] for k in ("n2_no_recorte_do_candidato", "reprodutibilidade")},
                     indent=2, default=str))
    sys.exit(0)
