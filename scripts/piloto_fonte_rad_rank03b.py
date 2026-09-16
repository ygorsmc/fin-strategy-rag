"""Piloto de fonte do lote B do Rank 3-B: a evidência existe e é legível?

Contrato: `resultados/contratos_lote_b_rank03b_2026-09-16.md`, cláusula P1.

**Não adjudica, não corrige, não mede o alvo** (P1.4, O1). Seleciona documentos
por ESTRUTURA — nunca pelo quão suspeitos parecem —, baixa os formulários,
confere o parser contra os ZIPs e classifica a declaração de unidade das notas.
O critério para estender a aquisição (P1.3) foi fixado no contrato antes deste
código existir, e é aplicado aqui sem alteração.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

from scripts import fonte_rad_cvm as rad
from scripts import fonte_zip_cvm as fz
from scripts.esqueleto_plano_padrao import documentos_defeituosos

RAIZ = Path(__file__).resolve().parents[1]
PAINEL_COMPARTILHADO = RAIZ / "artefatos" / "cvm_treino.duckdb"
DESTINO = RAIZ / "artefatos" / "painel_pesquisa_rank03b" / "piloto"

#: P1.1 — tamanho de cada estrato, fixado no contrato.
ESTRATOS = {
    "E1_fronteira_UNIDADE": 6,
    "E2_fronteira_MIL": 6,
    "E3_interior_de_mista": 6,
    "E4_companhia_so_UNIDADE": 5,
    "E5_companhia_so_MIL": 5,
    "E6_ativo_ate_1_nao_nulo": 3,
    "E7_varias_versoes": 8,
    "E8_dfp": 4,
    "E9_exercicio_2011_2012": 4,
    #: Ressalva RA4: trechos inteiros, para TESTAR a premissa de que o interior
    #: de um trecho tem a escala das pontas. "Até 10 cada" é lido como trechos
    #: de 3 a 10 documentos, baixados por inteiro — um trecho cortado não
    #: testaria a premissa.
    "E10_trecho_completo": 3,
}
TAMANHO_DO_TRECHO_COMPLETO = (3, 10)
#: P1.3 — critério para estender, fixado no contrato.
PISO_DOWNLOAD_INTEGRO = 0.90
PISO_EVIDENCIA_E1_E4 = 0.70
ESTRATOS_DE_EVIDENCIA = ("E1_fronteira_UNIDADE", "E2_fronteira_MIL",
                         "E3_interior_de_mista", "E4_companhia_so_UNIDADE")
#: O1 — nada com estes nomes pode sair deste lote.
CHAVES_PROIBIDAS = frozenset({"y", "rotulo", "taxa_do_evento", "s1", "s2"})


def chave_de_ordem(cd_cvm: str, conjunto: str, dt_refer, versao: int) -> str:
    """Ordem cega ao desfecho: o hash da identidade do documento."""
    return hashlib.sha256(f"{cd_cvm}|{conjunto}|{dt_refer}|{versao}".encode()).hexdigest()


def preparar(con: duckdb.DuckDBPyConnection, painel: Path = PAINEL_COMPARTILHADO) -> None:
    """Tabela `docs`: um documento por linha, com a estrutura que define os estratos."""
    con.execute(f"ATTACH '{painel}' AS compartilhado (READ_ONLY)")
    con.execute(
        """
        CREATE OR REPLACE TABLE universo AS
        SELECT cd_cvm, plano_contas FROM compartilhado.companhias
        WHERE plano_contas NOT LIKE 'll3_09_%' AND NOT is_banco
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE docs AS
        WITH base AS (
            SELECT d.cd_cvm, d.conjunto, d.dt_refer, d.versao,
                   min(d.escala) AS escala, count(DISTINCT d.escala) AS escalas,
                   max(CASE WHEN d.cd_conta = '1' AND d.ordem = 'ÚLTIMO' THEN d.vl END) AS ativo
            FROM declaracoes d JOIN universo USING (cd_cvm)
            GROUP BY ALL
        ), com_id AS (
            SELECT b.*, c.id_doc, c.dt_receb
            FROM base b
            JOIN cadastro c USING (cd_cvm, conjunto, dt_refer, versao)
            QUALIFY count(*) OVER (PARTITION BY b.cd_cvm, b.conjunto, b.dt_refer, b.versao) = 1
        ), perfil AS (
            SELECT cd_cvm, count(DISTINCT escala) AS rotulos, min(escala) AS rotulo
            FROM base GROUP BY 1
        )
        , vizinhos AS (
            SELECT com_id.*, perfil.rotulos, perfil.rotulo AS rotulo_da_companhia,
                   lag(escala) OVER w AS escala_anterior,
                   lead(escala) OVER w AS escala_seguinte,
                   row_number() OVER w AS posicao
            FROM com_id JOIN perfil USING (cd_cvm)
            WINDOW w AS (PARTITION BY cd_cvm ORDER BY dt_refer, conjunto)
        )
        SELECT *,
               -- Trecho: sequência máxima de documentos consecutivos com o
               -- mesmo rótulo (ressalva RA4).
               sum(CASE WHEN escala IS DISTINCT FROM escala_anterior THEN 1 ELSE 0 END)
                   OVER (PARTITION BY cd_cvm ORDER BY posicao ROWS UNBOUNDED PRECEDING)
                   AS trecho
        FROM vizinhos
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE versoes AS
        SELECT c.cd_cvm, c.conjunto, c.dt_refer,
               min(c.versao) AS v1, arg_min(c.id_doc, c.versao) AS id_v1
        FROM cadastro c JOIN universo USING (cd_cvm)
        GROUP BY ALL HAVING count(DISTINCT c.versao) > 1
        """
    )


def _membros_do_estrato(con, nome: str) -> list[dict]:
    filtros = {
        "E1_fronteira_UNIDADE": "escala = 'UNIDADE' AND (escala <> escala_anterior OR escala <> escala_seguinte)",
        "E2_fronteira_MIL": "escala = 'MIL' AND (escala <> escala_anterior OR escala <> escala_seguinte)",
        "E3_interior_de_mista": "rotulos > 1 AND escala = coalesce(escala_anterior, escala) AND escala = coalesce(escala_seguinte, escala)",
        "E4_companhia_so_UNIDADE": "rotulos = 1 AND rotulo_da_companhia = 'UNIDADE'",
        "E5_companhia_so_MIL": "rotulos = 1 AND rotulo_da_companhia = 'MIL'",
        "E6_ativo_ate_1_nao_nulo": "ativo > 0 AND ativo <= 1",
        "E7_varias_versoes": "(cd_cvm, conjunto, dt_refer) IN (SELECT cd_cvm, conjunto, dt_refer FROM versoes)",
        "E8_dfp": "conjunto = 'dfp'",
        "E9_exercicio_2011_2012": "year(dt_refer) IN (2011, 2012)",
    }
    linhas = con.execute(
        f"SELECT cd_cvm, conjunto, CAST(dt_refer AS VARCHAR), versao, id_doc, escala "
        f"FROM docs WHERE {filtros[nome]}"
    ).fetchall()
    membros = [
        {"cd_cvm": c, "conjunto": j, "dt_refer": d, "versao": v, "id_doc": i,
         "escala": e, "ordem": chave_de_ordem(c, j, d, v)}
        for c, j, d, v, i, e in linhas
    ]
    return sorted(membros, key=lambda m: m["ordem"])


def _trechos_completos(con, quantos: int) -> list[list[dict]]:
    """E10: trechos de 3 a 10 documentos em companhias mistas, pela ordem do
    hash da primeira ponta, um por companhia, cada um por inteiro."""
    minimo, maximo = TAMANHO_DO_TRECHO_COMPLETO
    linhas = con.execute(
        f"""
        SELECT cd_cvm, trecho, CAST(dt_refer AS VARCHAR), conjunto, versao, id_doc, escala
        FROM docs
        WHERE rotulos > 1 AND (cd_cvm, trecho) IN (
            SELECT cd_cvm, trecho FROM docs GROUP BY ALL
            HAVING count(*) BETWEEN {minimo} AND {maximo})
        ORDER BY cd_cvm, trecho, posicao
        """
    ).fetchall()
    trechos: dict[tuple, list[dict]] = {}
    for c, t, d, j, v, i, e in linhas:
        trechos.setdefault((c, t), []).append({
            "cd_cvm": c, "conjunto": j, "dt_refer": d, "versao": v, "id_doc": i,
            "escala": e, "ordem": chave_de_ordem(c, j, d, v), "trecho": int(t),
        })
    candidatos = sorted(trechos.values(), key=lambda docs: docs[0]["ordem"])
    escolhidos, companhias = [], set()
    for docs in candidatos:
        if len(escolhidos) == quantos:
            break
        if docs[0]["cd_cvm"] in companhias:
            continue
        companhias.add(docs[0]["cd_cvm"])
        escolhidos.append(docs)
    return escolhidos


def selecionar(con) -> list[dict]:
    """P1.1: por estrato, na ordem do hash, uma entrada por companhia."""
    escolhidos: dict[str, dict] = {}
    for docs in _trechos_completos(con, ESTRATOS["E10_trecho_completo"]):
        for m in docs:
            atual = escolhidos.setdefault(m["id_doc"], {**m, "estratos": [], "papel": "vmax"})
            atual["estratos"].append("E10_trecho_completo")
            atual["trecho"] = m["trecho"]
    for nome, quantos in ESTRATOS.items():
        if nome == "E10_trecho_completo":
            continue
        companhias: set[str] = set()
        tomados = 0
        for m in _membros_do_estrato(con, nome):
            if tomados == quantos:
                break
            if m["cd_cvm"] in companhias:
                continue
            companhias.add(m["cd_cvm"])
            tomados += 1
            atual = escolhidos.setdefault(m["id_doc"], {**m, "estratos": [], "papel": "vmax"})
            atual["estratos"].append(nome)
            if nome == "E7_varias_versoes":
                v1 = con.execute(
                    "SELECT id_v1, v1 FROM versoes WHERE cd_cvm=? AND conjunto=? AND dt_refer=?",
                    [m["cd_cvm"], m["conjunto"], m["dt_refer"]],
                ).fetchone()
                par = escolhidos.setdefault(v1[0], {
                    "cd_cvm": m["cd_cvm"], "conjunto": m["conjunto"],
                    "dt_refer": m["dt_refer"], "versao": v1[1], "id_doc": v1[0],
                    "escala": None, "ordem": m["ordem"], "estratos": [],
                    "papel": "v1", "par_de": m["id_doc"],
                })
                par["estratos"].append(nome)
    return sorted(escolhidos.values(), key=lambda d: (d["ordem"], d["versao"]))


def _zip_do_documento(con, doc: dict) -> dict[tuple, float]:
    linhas = con.execute(
        """
        SELECT cd_conta, dt_ini, dt_fim, vl FROM declaracoes
        WHERE cd_cvm = ? AND conjunto = ? AND dt_refer = ? AND versao = ?
        """,
        [doc["cd_cvm"], doc["conjunto"], doc["dt_refer"], doc["versao"]],
    ).fetchall()
    return {
        (c, None if c in rad.CONTAS_DE_POSICAO else i, f): v
        for c, i, f, v in linhas
    }


def medir_documento(con, doc: dict, adjudicados: set, brutos: Path = rad.BRUTOS,
                    manifesto: Path = rad.MANIFESTO) -> dict:
    registro = rad.adquirir(doc, brutos=brutos, manifesto=manifesto)
    saida = {
        k: doc[k] for k in ("id_doc", "cd_cvm", "conjunto", "dt_refer", "versao",
                            "estratos", "papel")
    }
    saida.update(escala_declarada=doc["escala"], aquisicao=registro["estado"],
                 adjudicado_pelo_inventario=(doc["cd_cvm"], doc["conjunto"],
                                             doc["dt_refer"], doc["versao"]) in adjudicados)
    if registro["estado"] != "integro":
        return saida
    try:
        formulario = rad.ler(brutos / f"{doc['id_doc']}.zip")
        extraido = rad.por_chave(formulario)
    except rad.PacoteInvalido as erro:
        saida.update(leitura="erro", motivo=str(erro))
        return saida
    unidade = rad.classificar_unidade(formulario.anexos)
    notas = rad.texto_das_notas(formulario)
    saida.update(
        formato=formulario.formato,
        grupos_anexos=sorted(set(formulario.grupos_anexos.values())),
        cabecalho_notas=rad.classificar_cabecalho(notas),
        evidencia_numerica=rad.evidencia_numerica(formulario, notas),
        trecho=doc.get("trecho"),
    )
    saida.update(
        leitura="ok",
        codigo_escala_moeda=formulario.codigo_escala_moeda,
        anexos=len(formulario.anexos),
        paginas_de_anexo=sum(len(p) for _, p in formulario.anexos),
        classe_unidade=unidade["classe"],
        contagem_unidade=unidade["contagem"],
        evidencias_unidade=unidade["evidencias"][:5],
    )
    if doc["papel"] == "vmax":
        do_zip = _zip_do_documento(con, doc)
        iguais = [k for k, v in do_zip.items() if extraido.get(k) == v]
        divergentes = [k for k, v in do_zip.items() if k in extraido and extraido[k] != v]
        ausentes = [k for k in do_zip if k not in extraido]
        saida["x13"] = {
            "linhas_no_zip": len(do_zip), "iguais": len(iguais),
            # Só as CHAVES divergentes, nunca os valores (O1).
            "divergentes": [list(map(str, k)) for k in divergentes],
            "ausentes_no_formulario": [list(map(str, k)) for k in ausentes],
        }
    else:
        do_zip = _zip_do_documento(con, {**doc, "versao": con.execute(
            "SELECT max(versao) FROM declaracoes WHERE cd_cvm=? AND conjunto=? AND dt_refer=?",
            [doc["cd_cvm"], doc["conjunto"], doc["dt_refer"]]).fetchone()[0]})
        comuns = [k for k in do_zip if k in extraido]
        saida["v1_contra_vmax"] = {
            "chaves_comuns": len(comuns),
            "iguais": sum(1 for k in comuns if extraido[k] == do_zip[k]),
        }
    return saida


def resumir(registros: list[dict]) -> dict:
    total = len(registros)
    integros = [r for r in registros if r["aquisicao"] == "integro"]
    lidos = [r for r in integros if r.get("leitura") == "ok"]
    vmax = [r for r in lidos if "x13" in r]
    x13_ok = [r for r in vmax if r["x13"]["iguais"] == r["x13"]["linhas_no_zip"]
              and r["x13"]["linhas_no_zip"] > 0]
    mapeamento = Counter(
        f"{r['codigo_escala_moeda']}->{r['escala_declarada']}" for r in vmax
    )
    por_estrato: dict[str, Counter] = defaultdict(Counter)
    concordancia: dict[str, Counter] = defaultdict(Counter)
    for r in lidos:
        for e in r["estratos"]:
            por_estrato[e][r["classe_unidade"]] += 1
            if r["escala_declarada"] and r["classe_unidade"].startswith("declara_"):
                igual = r["classe_unidade"] == f"declara_{r['escala_declarada']}"
                concordancia[e]["concorda" if igual else "discorda"] += 1
    inventario = Counter(
        (r["adjudicado_pelo_inventario"], r["classe_unidade"] == f"declara_{r['escala_declarada']}")
        for r in lidos if r["escala_declarada"] and r["classe_unidade"].startswith("declara_")
    )
    ra3: dict[str, Counter] = defaultdict(Counter)
    for r in lidos:
        par = f"{r['cabecalho_notas']['classe']}|{r['evidencia_numerica']['classe']}"
        for e in r["estratos"]:
            ra3[e][par] += 1
    trechos_completos: dict[str, list] = defaultdict(list)
    for r in sorted((r for r in registros if "E10_trecho_completo" in r["estratos"]),
                    key=lambda r: (r["cd_cvm"], r["dt_refer"], r["conjunto"])):
        trechos_completos[r["cd_cvm"]].append({
            "dt_refer": r["dt_refer"], "conjunto": r["conjunto"],
            "escala_declarada": r["escala_declarada"], "aquisicao": r["aquisicao"],
            "cabecalho": r.get("cabecalho_notas", {}).get("classe"),
            "numerica": r.get("evidencia_numerica", {}).get("classe"),
        })
    evidencia = [r for r in lidos if set(r["estratos"]) & set(ESTRATOS_DE_EVIDENCIA)]
    com_evidencia = [r for r in evidencia if r["classe_unidade"] != "ausente"]
    taxa_download = len(integros) / total if total else 0.0
    taxa_evidencia = len(com_evidencia) / len(evidencia) if evidencia else 0.0
    criterios = {
        "c1_download_integro": {
            "medido": round(taxa_download, 4), "limiar": PISO_DOWNLOAD_INTEGRO,
            "atendido": taxa_download >= PISO_DOWNLOAD_INTEGRO,
        },
        "c2_parser_igual_ao_zip": {
            "medido": f"{len(x13_ok)}/{len(vmax)}", "limiar": "100%",
            "atendido": bool(vmax) and len(x13_ok) == len(vmax),
        },
        "c3_evidencia_de_unidade_E1_E4": {
            "medido": round(taxa_evidencia, 4), "limiar": PISO_EVIDENCIA_E1_E4,
            "atendido": bool(evidencia) and taxa_evidencia >= PISO_EVIDENCIA_E1_E4,
        },
    }
    return {
        "documentos": total,
        "aquisicao": dict(Counter(r["aquisicao"] for r in registros)),
        "leitura": dict(Counter(r.get("leitura", "nao_lido") for r in integros)),
        "x13_documentos_vmax": len(vmax),
        "x13_documentos_identicos": len(x13_ok),
        "x13_linhas": sum(r["x13"]["linhas_no_zip"] for r in vmax),
        "x13_linhas_iguais": sum(r["x13"]["iguais"] for r in vmax),
        "mapeamento_codigo_escala": dict(sorted(mapeamento.items())),
        "classe_unidade_por_estrato": {k: dict(v) for k, v in sorted(por_estrato.items())},
        "concordancia_com_rotulo_por_estrato": {k: dict(v) for k, v in sorted(concordancia.items())},
        "inventario_x_notas": {
            f"adjudicado={a}|notas_concordam_com_rotulo={b}": n
            for (a, b), n in sorted(inventario.items())
        },
        "formatos": dict(Counter(r["formato"] for r in lidos)),
        "cabecalho_e_numerica_por_estrato": {k: dict(v) for k, v in sorted(ra3.items())},
        "trechos_completos": dict(trechos_completos),
        "v1_contra_vmax": [
            {"id_doc": r["id_doc"], **r["v1_contra_vmax"]}
            for r in lidos if "v1_contra_vmax" in r
        ],
        "criterios_P1_3": criterios,
        "estender": all(c["atendido"] for c in criterios.values()),
    }


def _sem_chave_proibida(objeto) -> None:
    if isinstance(objeto, dict):
        proibidas = CHAVES_PROIBIDAS & set(objeto)
        if proibidas:
            raise AssertionError(f"O1 violada: chaves {sorted(proibidas)} no artefato")
        for valor in objeto.values():
            _sem_chave_proibida(valor)
    elif isinstance(objeto, list):
        for valor in objeto:
            _sem_chave_proibida(valor)


def executar(destino: Path = DESTINO) -> dict:
    con = duckdb.connect(":memory:")
    hashes = fz.extrair(con)
    preparar(con)
    adjudicados = {(c, j, d, v) for c, j, d, v in documentos_defeituosos()}
    selecao = selecionar(con)
    registros = [medir_documento(con, doc, adjudicados) for doc in selecao]
    resultado = {
        "contrato": "resultados/contratos_lote_b_rank03b_2026-09-16.md#P1",
        "zips_sha256": hashes,
        "estratos": ESTRATOS,
        **resumir(registros),
    }
    _sem_chave_proibida(resultado)
    _sem_chave_proibida(registros)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "evidencias.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str) + "\n"
                for r in registros),
        encoding="utf-8",
    )
    (destino / "resultado.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return resultado


def principal() -> int:
    resultado = executar()
    print(json.dumps({k: resultado[k] for k in (
        "documentos", "aquisicao", "leitura", "x13_documentos_vmax",
        "x13_documentos_identicos", "mapeamento_codigo_escala",
        "criterios_P1_3", "estender")}, ensure_ascii=False, indent=2))
    return 0 if resultado["estender"] else 3


if __name__ == "__main__":
    raise SystemExit(principal())
