"""Adjudicação de escala por documento, com fonte, para o painel de pesquisa.

Contrato: `resultados/contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md`,
parte 2 (S1–S10). **Congelada antes de rodar sobre a extensão**: a linha de base
sem correção já mostrava G0.3 em 0,5875%, e uma regra ajustada depois de ver o
G0 seria escolhida pelo resultado (S10).

**O que decide** (S2): a unidade que a própria companhia declara no cabeçalho das
notas explicativas **e** a forma como os números do formulário aparecem nesse
texto — como estão, divididos ou multiplicados por mil. Uma sem a outra é
indecidível.

**O que não se publica** (O1): valor de FCO. A evidência numérica sai como
contagem; o trecho literal é o do cabeçalho.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

from scripts import fonte_rad_cvm as rad
from scripts import fonte_zip_cvm as fz
from scripts import painel_pesquisa_rank03b as pp
from scripts import piloto_fonte_rad_rank03b as piloto

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "artefatos" / "painel_pesquisa_rank03b" / "adjudicacao"
MANIFESTO_CORRECOES = RAIZ / "corpus" / "cvm" / "painel_pesquisa_rank03b" / "correcoes_escala.csv"
EVIDENCIAS_DO_PILOTO = RAIZ / "artefatos" / "painel_pesquisa_rank03b" / "piloto" / "evidencias.jsonl"

#: S4 — companhias só `MIL` de controle.
CONTROLES = 30
#: S2, na forma da ressalva RC1-bis: só o cabeçalho `MIL` é evidência de
#: escala. Qualquer par fora da tabela é indecidível.
TABELA_S2 = {
    ("MIL", "bruto"): "MIL",
    ("MIL", "dividido"): "UNIDADE",
}
#: A tabela da primeira execução, preservada para reproduzi-la.
TABELA_S2_EXECUCAO_1 = {
    ("MIL", "bruto"): "MIL",
    ("MIL", "dividido"): "UNIDADE",
    ("UNIDADE", "bruto"): "UNIDADE",
    ("UNIDADE", "multiplicado"): "MIL",
}
VEREDITOS = ("confirmada", "corrigida", "indecidivel")
COLUNAS_MANIFESTO = [
    "id_correcao", "cd_cvm", "conjunto", "dt_refer", "versao", "id_doc",
    "sha256_pacote", "escala_declarada", "escala_aplicada", "base",
    "impressao_digital", "cabecalho_classe", "cabecalho_contagem",
    "numerica_classe", "numerica_contagem", "trecho", "evidencia_anexo",
    "evidencia_pagina", "evidencia_trecho", "pontas",
]


def veredito(cabecalho: str, numerica: str, declarada: str | None) -> tuple[str | None, str]:
    """S2: `(escala_do_formulario, veredito)`."""
    escala = TABELA_S2.get((cabecalho, numerica))
    if escala is None:
        return None, "indecidivel"
    if declarada is None:
        return escala, "indecidivel"
    return escala, "confirmada" if escala == declarada else "corrigida"


def adjudicar_formulario(formulario: rad.Formulario, declarada: str | None) -> dict:
    notas = rad.texto_das_notas(formulario)
    # RC1: cabeçalho DE APRESENTAÇÃO, não a frase em qualquer ponto das notas.
    cab = rad.classificar_cabecalho_de_apresentacao(formulario)
    num = rad.evidencia_numerica(formulario, notas)
    escala, estado = veredito(cab["classe"], num["classe"], declarada)
    literal, motivo = None, None
    if estado != "indecidivel":
        literal = rad.evidencia_de_cabecalho(formulario, cab["classe"])
        if literal is None:
            # S8: sem trecho literal não há como registrar a decisão.
            escala, estado, motivo = None, "indecidivel", "sem_trecho_literal_do_cabecalho"
    elif escala is None:
        motivo = f"par_fora_da_tabela:{cab['classe']}|{num['classe']}"
    else:
        motivo = "escala_declarada_desconhecida"
    return {
        "cabecalho": cab, "numerica": num, "escala_do_formulario": escala,
        "veredito": estado, "motivo": motivo, "evidencia": literal,
        "formato": formulario.formato, "codigo_escala_moeda": formulario.codigo_escala_moeda,
    }


# --- escopo (S4) -----------------------------------------------------------------

def _ordem(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def escopo(con) -> list[dict]:
    """Documentos a adquirir: pontas dos trechos suspeitos e controles só `MIL`."""
    trechos = con.execute(
        """
        SELECT cd_cvm, trecho, CAST(dt_refer AS VARCHAR), conjunto, versao, id_doc,
               escala, posicao, rotulos, rotulo_da_companhia
        FROM docs
        WHERE rotulos > 1 OR rotulo_da_companhia = 'UNIDADE'
        ORDER BY cd_cvm, posicao
        """
    ).fetchall()
    por_trecho = defaultdict(list)
    for linha in trechos:
        por_trecho[(linha[0], linha[1])].append(linha)
    documentos = {}
    for (cd, trecho), linhas in sorted(por_trecho.items()):
        pontas = [linhas[0]] if len(linhas) == 1 else [linhas[0], linhas[-1]]
        for papel, (c, t, d, j, v, i, e, _, rot, _) in zip(
                ["ponta_inicial", "ponta_final"], pontas):
            documentos[i] = {
                "cd_cvm": c, "conjunto": j, "dt_refer": d, "versao": v, "id_doc": i,
                "escala": e, "trecho": int(t), "tamanho_do_trecho": len(linhas),
                "papel": "unica" if len(linhas) == 1 else papel,
                "perfil": "mista" if rot > 1 else "so_UNIDADE",
            }
    controles = con.execute(
        """
        SELECT cd_cvm FROM docs WHERE rotulos = 1 AND rotulo_da_companhia = 'MIL'
        GROUP BY 1
        """
    ).fetchall()
    for (cd,) in sorted(controles, key=lambda r: _ordem(r[0]))[:CONTROLES]:
        linhas = con.execute(
            "SELECT CAST(dt_refer AS VARCHAR), conjunto, versao, id_doc, escala, trecho "
            "FROM docs WHERE cd_cvm = ?", [cd]).fetchall()
        d, j, v, i, e, t = min(linhas, key=lambda r: piloto.chave_de_ordem(cd, r[1], r[0], r[2]))
        documentos[i] = {
            "cd_cvm": cd, "conjunto": j, "dt_refer": d, "versao": v, "id_doc": i,
            "escala": e, "trecho": int(t), "tamanho_do_trecho": None,
            "papel": "controle", "perfil": "so_MIL",
        }
    return sorted(documentos.values(), key=lambda x: (x["cd_cvm"], x["dt_refer"], x["conjunto"]))


# --- herança (S5) ------------------------------------------------------------------

def premissa_do_trecho(registros_e10: list[dict]) -> dict:
    """S5(2): nos trechos completos do piloto, algum interior discorda das pontas?

    Só conta trecho cujos documentos tenham TODOS veredito decidido; os outros
    não testam nada e são publicados à parte.
    """
    por_trecho = defaultdict(list)
    for r in registros_e10:
        por_trecho[(r["cd_cvm"], r["trecho"])].append(r)
    testados, discordantes, nao_testaveis = [], [], []
    for chave, docs in sorted(por_trecho.items()):
        docs.sort(key=lambda r: (r["dt_refer"], r["conjunto"]))
        escalas = [r.get("escala_do_formulario") for r in docs]
        if len(docs) < 3 or any(e is None for e in escalas):
            nao_testaveis.append(list(chave))
            continue
        testados.append(list(chave))
        # Com três ou mais documentos, qualquer escala diferente — inclusive
        # pontas que discordam entre si — deixa algum documento com escala
        # diferente de uma das pontas: a leitura literal e conservadora de S5(2).
        if len(set(escalas)) > 1:
            discordantes.append(list(chave))
    return {
        "trechos_testados": testados, "trechos_nao_testaveis": nao_testaveis,
        "trechos_com_interior_discordante": discordantes,
        "heranca_permitida": bool(testados) and not discordantes,
    }


def herdar(con, adjudicados: dict[str, dict], heranca_permitida: bool) -> list[dict]:
    """Interiores que recebem a escala das pontas (S5)."""
    if not heranca_permitida:
        return []
    pontas = defaultdict(dict)
    for r in adjudicados.values():
        if r["papel"] in ("ponta_inicial", "ponta_final"):
            pontas[(r["cd_cvm"], r["trecho"])][r["papel"]] = r
    herdados = []
    for (cd, trecho), par in sorted(pontas.items()):
        if set(par) != {"ponta_inicial", "ponta_final"}:
            continue
        inicio, fim = par["ponta_inicial"], par["ponta_final"]
        if inicio["veredito"] == "indecidivel" or fim["veredito"] == "indecidivel":
            continue
        if inicio["escala_do_formulario"] != fim["escala_do_formulario"]:
            continue
        interiores = con.execute(
            """
            SELECT CAST(dt_refer AS VARCHAR), conjunto, versao, id_doc, escala FROM docs
            WHERE cd_cvm = ? AND trecho = ? ORDER BY posicao
            """, [cd, trecho]).fetchall()[1:-1]
        for d, j, v, i, e in interiores:
            if i in adjudicados:
                continue  # documento com veredito próprio não herda
            herdados.append({
                "cd_cvm": cd, "conjunto": j, "dt_refer": d, "versao": v, "id_doc": i,
                "escala_declarada": e, "escala_do_formulario": inicio["escala_do_formulario"],
                "trecho": trecho, "pontas": [inicio["id_doc"], fim["id_doc"]],
                "veredito": "corrigida" if e != inicio["escala_do_formulario"] else "confirmada",
            })
    return herdados


# --- manifesto (S8) --------------------------------------------------------------

def _brutos(con, doc) -> list[tuple]:
    """As mesmas linhas que o construtor usa para a impressão digital."""
    return con.execute(
        """
        SELECT cd_conta, ordem, dt_ini, dt_fim, vl FROM declaracoes
        WHERE cd_cvm = ? AND conjunto = ? AND dt_refer = ? AND versao = ?
          AND cd_conta IN ('1', '6.01')
        """, [doc["cd_cvm"], doc["conjunto"], doc["dt_refer"], doc["versao"]]).fetchall()


def linhas_do_manifesto(con, adjudicados: dict[str, dict], herdados: list[dict]) -> list[dict]:
    linhas = []
    for r in sorted(adjudicados.values(), key=lambda r: (r["cd_cvm"], r["dt_refer"], r["conjunto"])):
        if r["veredito"] != "corrigida":
            continue
        ev = r["evidencia"]
        linhas.append({
            "cd_cvm": r["cd_cvm"], "conjunto": r["conjunto"], "dt_refer": r["dt_refer"],
            "versao": r["versao"], "id_doc": r["id_doc"], "sha256_pacote": r["sha256"],
            "escala_declarada": r["escala_declarada"],
            "escala_aplicada": r["escala_do_formulario"], "base": "corrigida_documento",
            "impressao_digital": pp.impressao_digital(_brutos(con, r)),
            "cabecalho_classe": r["cabecalho"]["classe"],
            "cabecalho_contagem": json.dumps(r["cabecalho"]["contagem"], sort_keys=True),
            "numerica_classe": r["numerica"]["classe"],
            "numerica_contagem": json.dumps(r["numerica"]["contagem"], sort_keys=True),
            "trecho": r["trecho"], "evidencia_anexo": ev["anexo"],
            "evidencia_pagina": ev["pagina"], "evidencia_trecho": ev["trecho"], "pontas": "",
        })
    for h in herdados:
        if h["veredito"] != "corrigida":
            continue
        pontas = [adjudicados[i] for i in h["pontas"]]
        linhas.append({
            "cd_cvm": h["cd_cvm"], "conjunto": h["conjunto"], "dt_refer": h["dt_refer"],
            "versao": h["versao"], "id_doc": h["id_doc"], "sha256_pacote": "",
            "escala_declarada": h["escala_declarada"],
            "escala_aplicada": h["escala_do_formulario"], "base": "herdada_trecho",
            "impressao_digital": pp.impressao_digital(_brutos(con, h)),
            "cabecalho_classe": "", "cabecalho_contagem": "", "numerica_classe": "",
            "numerica_contagem": "", "trecho": h["trecho"],
            "evidencia_anexo": "", "evidencia_pagina": "",
            "evidencia_trecho": " || ".join(
                f"[{p['id_doc']} p.{p['evidencia']['pagina']}] {p['evidencia']['trecho']}"
                for p in pontas),
            "pontas": json.dumps([{"id_doc": p["id_doc"], "sha256_pacote": p["sha256"],
                                   "dt_refer": p["dt_refer"], "veredito": p["veredito"],
                                   "escala_do_formulario": p["escala_do_formulario"]}
                                  for p in pontas], sort_keys=True),
        })
    linhas.sort(key=lambda r: (r["cd_cvm"], r["dt_refer"], r["conjunto"]))
    for n, linha in enumerate(linhas, start=1):
        linha["id_correcao"] = f"ESC-{n:04d}"
    return linhas


BASES_DO_MANIFESTO = ("corrigida_documento", "herdada_trecho")


def validar_manifesto(linhas: list[dict], tabela: dict | None = None,
                      exigir_escala_nas_pontas: bool = True) -> None:
    """Condições de falsificação 11, 12 e 14 — no produtor E no consumidor.

    `tabela` e `exigir_escala_nas_pontas` existem só para reler o manifesto da
    execução 1, escrito com a tabela anterior e sem a escala das pontas.
    """
    tabela = TABELA_S2 if tabela is None else tabela
    for r in linhas:
        ident = r.get("id_correcao", "?")
        if r["escala_declarada"] not in pp.FATOR_DA_ESCALA or \
                r["escala_aplicada"] not in pp.FATOR_DA_ESCALA:
            raise AssertionError(f"{ident}: escala fora do vocabulário")
        if r["escala_aplicada"] == r["escala_declarada"]:
            raise AssertionError(f"{ident}: manifesto só leva o que muda")
        if r["base"] == "corrigida_documento":
            par = (r["cabecalho_classe"], r["numerica_classe"])
            if tabela.get(par) != r["escala_aplicada"]:
                raise AssertionError(f"{ident}: correção sem as duas evidências {par}")
            if str(r["evidencia_anexo"]) == "" or not str(r["evidencia_pagina"]) or \
                    len(r["evidencia_trecho"]) < rad.TRECHO_MINIMO:
                raise AssertionError(f"{ident}: sem trecho literal/anexo/página")
            if len(r.get("sha256_pacote", "")) != 64:
                raise AssertionError(f"{ident}: sem pacote de origem")
        elif r["base"] == "herdada_trecho":
            pontas = json.loads(r["pontas"])
            if len(pontas) != 2 or any(p["veredito"] == "indecidivel" for p in pontas):
                raise AssertionError(f"{ident}: herança sem duas pontas decididas")
            if any(len(p.get("sha256_pacote") or "") != 64 for p in pontas):
                raise AssertionError(f"{ident}: ponta sem pacote de origem")
            if exigir_escala_nas_pontas and any(
                    p.get("escala_do_formulario") != r["escala_aplicada"] for p in pontas):
                # Condição 12: um trecho tem um único rótulo declarado; pontas com
                # escalas de formulário diferentes não transmitem nada.
                raise AssertionError(f"{ident}: pontas com escala diferente da herdada")
        else:
            raise AssertionError(f"{ident}: base desconhecida {r['base']!r}")


def pacotes_integros(manifesto: Path = rad.MANIFESTO) -> dict[str, set[str]]:
    """`{id_doc: {sha256}}` dos pacotes registrados como íntegros."""
    saida: dict[str, set[str]] = defaultdict(set)
    for linha in manifesto.read_text(encoding="utf-8").splitlines():
        r = json.loads(linha)
        if r.get("estado") == "integro" and r.get("sha256"):
            saida[str(r["id_doc"])].add(r["sha256"])
    return saida


def conferir_pacotes(linhas: list[dict], integros: dict[str, set[str]]) -> None:
    """Todo pacote citado como evidência existe, íntegro, com esse hash."""
    for r in linhas:
        citados = []
        if r["base"] == "corrigida_documento":
            citados.append((r["id_doc"], r["sha256_pacote"]))
        else:
            citados += [(p["id_doc"], p["sha256_pacote"]) for p in json.loads(r["pontas"])]
        for id_doc, digest in citados:
            if digest not in integros.get(str(id_doc), set()):
                raise AssertionError(
                    f"{r.get('id_correcao')}: pacote {id_doc} ({digest[:12]}…) não consta "
                    "íntegro no manifesto de aquisição")


def reescrever_manifesto(pasta: Path = DESTINO, manifesto: Path = MANIFESTO_CORRECOES) -> dict:
    """Regrava o manifesto a partir da evidência JÁ adjudicada, sem reler PDF.

    Existe para a correção M2 da auditoria (escala das pontas no manifesto):
    muda o formato, não a decisão — e confere isso.
    """
    con = duckdb.connect(":memory:")
    fz.extrair(con)
    adjudicados = {}
    for linha in (pasta / "evidencias.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(linha)
        adjudicados[r["id_doc"]] = r
    herdados = [json.loads(l) for l in
                (pasta / "herdados.jsonl").read_text(encoding="utf-8").splitlines()]
    antes = {}
    if manifesto.is_file():
        with open(manifesto, encoding="utf-8", newline="") as fh:
            antes = {(r["cd_cvm"], r["conjunto"], r["dt_refer"], r["versao"]):
                     (r["escala_aplicada"], r["base"]) for r in csv.DictReader(fh)}
    linhas = linhas_do_manifesto(con, adjudicados, herdados)
    validar_manifesto(linhas)
    conferir_pacotes(linhas, pacotes_integros())
    depois = {(r["cd_cvm"], r["conjunto"], r["dt_refer"], str(r["versao"])):
              (r["escala_aplicada"], r["base"]) for r in linhas}
    if antes and antes != depois:
        raise AssertionError("a regravação mudaria decisões — não é só formato")
    with open(manifesto, "w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=COLUNAS_MANIFESTO, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)
    return {"linhas": len(linhas), "decisoes_identicas": bool(antes) and antes == depois,
            "sha256": hashlib.sha256(manifesto.read_bytes()).hexdigest()}


# --- execução ------------------------------------------------------------------------

#: Conexões simultâneas ao RAD na aquisição. Modesto para um servidor público;
#: cada trabalhador tem sessão própria.
TRABALHADORES = 3


def pre_adquirir(documentos: list[dict], trabalhadores: int = TRABALHADORES,
                 adquirir=None) -> dict[str, str]:
    """Baixa em paralelo; a adjudicação depois reaproveita os pacotes em disco.

    Devolve `{id_doc: estado}`. Cada documento é pedido uma única vez.
    """
    from concurrent.futures import ThreadPoolExecutor

    adquirir = adquirir or rad.adquirir
    unicos = {d["id_doc"]: d for d in documentos}
    trabalhador_de = {}

    def tarefa(item):
        indice, doc = item
        cookies = rad.DIRETORIO / f".cookies_cvm_{indice % trabalhadores}"
        return doc["id_doc"], adquirir(doc, cookies=cookies)["estado"]

    with ThreadPoolExecutor(max_workers=trabalhadores) as pool:
        for id_doc, estado in pool.map(tarefa, enumerate(sorted(unicos.values(),
                                                               key=lambda d: d["id_doc"]))):
            trabalhador_de[id_doc] = estado
    return trabalhador_de

def _motivo(registro: dict) -> str:
    """Motivo agregável: erros de aquisição/leitura truncados, pares S2 inteiros."""
    motivo = registro.get("motivo") or "sem_motivo"
    if motivo.startswith(("aquisicao:", "leitura:")):
        tipo, _, resto = motivo.partition(":")
        return f"{tipo}:{resto[:40]}"
    return motivo


#: Processos de leitura de PDF (a leitura do anexo de notas domina o custo).
LEITORES = 10


def _adjudicar_um(doc: dict) -> dict:
    """Um documento: aquisição (reaproveitada), leitura só das notas, S2.

    Função de módulo para poder ir a outro processo.
    """
    registro = rad.adquirir(doc)
    base = {**doc, "escala_declarada": doc["escala"], "aquisicao": registro["estado"],
            "sha256": registro.get("sha256")}
    if registro["estado"] != "integro":
        return {**base, "veredito": "indecidivel", "motivo": f"aquisicao:{registro['estado']}",
                "escala_do_formulario": None, "evidencia": None}
    try:
        formulario = rad.ler(rad.BRUTOS / f"{doc['id_doc']}.zip", grupos=rad.GRUPOS_NOTAS)
    except rad.PacoteInvalido as erro:
        return {**base, "veredito": "indecidivel", "motivo": f"leitura:{erro}",
                "escala_do_formulario": None, "evidencia": None}
    return {**base, **adjudicar_formulario(formulario, doc["escala"])}


def adjudicar_documentos(documentos: list[dict], leitores: int = LEITORES,
                         adjudicar_um=_adjudicar_um) -> dict[str, dict]:
    """Todos os documentos do escopo, em paralelo, com resultado em ordem fixa."""
    from concurrent.futures import ProcessPoolExecutor

    unicos = sorted({d["id_doc"]: d for d in documentos}.values(), key=lambda d: d["id_doc"])
    if leitores <= 1:
        resultados = [adjudicar_um(d) for d in unicos]
    else:
        with ProcessPoolExecutor(max_workers=leitores) as pool:
            resultados = list(pool.map(adjudicar_um, unicos, chunksize=4))
    return {r["id_doc"]: r for r in resultados}


def documentos_do_piloto(caminho: Path, con) -> list[dict]:
    """S4: os documentos (versão numérica) já adjudicáveis pelo piloto."""
    saida = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        r = json.loads(linha)
        if r["papel"] != "vmax":
            continue
        atual = con.execute(
            "SELECT trecho, escala FROM docs WHERE id_doc = ?", [r["id_doc"]]).fetchone()
        if atual is None:
            continue
        saida.append({
            "cd_cvm": r["cd_cvm"], "conjunto": r["conjunto"], "dt_refer": r["dt_refer"],
            "versao": r["versao"], "id_doc": r["id_doc"], "escala": atual[1],
            "trecho": int(atual[0]), "tamanho_do_trecho": None, "papel": "piloto",
            "perfil": "piloto:" + "+".join(sorted(r["estratos"])),
        })
    return saida

def _registros_e10(caminho: Path, con=None) -> list[dict]:
    """Os documentos do estrato E10 do piloto, readjudicados com a regra ATUAL.

    RC1: as classes gravadas pelo piloto são da regra v1; o teste da premissa
    tem de usar a mesma regra que decide a herança.
    """
    if not caminho.is_file():
        raise FileNotFoundError(f"{caminho}: o teste da premissa (S5) exige o piloto")
    saida = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        r = json.loads(linha)
        if "E10_trecho_completo" not in r["estratos"]:
            continue
        escala = None
        if r.get("leitura") == "ok":
            formulario = rad.ler(rad.BRUTOS / f"{r['id_doc']}.zip", grupos=rad.GRUPOS_NOTAS)
            escala = adjudicar_formulario(formulario, r["escala_declarada"])["escala_do_formulario"]
        saida.append({**r, "escala_do_formulario": escala})
    return saida


def executar(destino: Path = DESTINO, manifesto: Path = MANIFESTO_CORRECOES,
             evidencias_piloto: Path = EVIDENCIAS_DO_PILOTO) -> dict:
    con = duckdb.connect(":memory:")
    zips = fz.extrair(con)
    piloto.preparar(con)
    premissa = premissa_do_trecho(_registros_e10(evidencias_piloto, con))
    documentos = escopo(con)
    ja = {d["id_doc"] for d in documentos}
    documentos += [d for d in documentos_do_piloto(evidencias_piloto, con) if d["id_doc"] not in ja]
    adjudicados = adjudicar_documentos(documentos)
    herdados = herdar(con, adjudicados, premissa["heranca_permitida"])
    linhas = linhas_do_manifesto(con, adjudicados, herdados)
    validar_manifesto(linhas)
    conferir_pacotes(linhas, pacotes_integros())

    def contagem(registros, chave):
        return dict(sorted(Counter(chave(r) for r in registros).items()))

    resumo = {
        "contrato": "resultados/contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md#parte-2",
        "execucao": "2 (ressalvas RC1 e RC1-bis)",
        "zips_sha256": zips,
        "premissa_s5": premissa,
        "documentos_no_escopo": len(documentos),
        "por_papel": contagem(adjudicados.values(), lambda r: r["papel"]),
        "aquisicao": contagem(adjudicados.values(), lambda r: r["aquisicao"]),
        "veredito_por_perfil": contagem(adjudicados.values(),
                                        lambda r: f"{r['perfil']}|{r['veredito']}"),
        "veredito_por_declarada": contagem(adjudicados.values(),
                                           lambda r: f"{r['escala_declarada']}|{r['veredito']}"),
        "motivos_de_indecisao": contagem(
            [r for r in adjudicados.values() if r["veredito"] == "indecidivel"], _motivo),
        "controles_corrigidos": sum(1 for r in adjudicados.values()
                                    if r["papel"] == "controle" and r["veredito"] == "corrigida"),
        "herdados": contagem(herdados, lambda r: r["veredito"]),
        "manifesto": {"linhas": len(linhas),
                      "por_base": contagem(linhas, lambda r: r["base"])},
    }
    piloto._sem_chave_proibida(resumo)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "evidencias.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str) + "\n"
                for r in sorted(adjudicados.values(),
                                key=lambda r: (r["cd_cvm"], r["dt_refer"], r["conjunto"]))),
        encoding="utf-8")
    (destino / "herdados.jsonl").write_text(
        "".join(json.dumps(h, ensure_ascii=False, sort_keys=True) + "\n" for h in herdados),
        encoding="utf-8")
    manifesto.parent.mkdir(parents=True, exist_ok=True)
    with open(manifesto, "w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=COLUNAS_MANIFESTO, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)
    resumo["manifesto"]["sha256"] = hashlib.sha256(manifesto.read_bytes()).hexdigest()
    (destino / "resumo.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8")
    return resumo


def principal(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--apenas-adquirir", action="store_true",
                        help="só baixa o escopo S4, em paralelo; não adjudica")
    args = parser.parse_args(argv)
    if args.apenas_adquirir:
        con = duckdb.connect(":memory:")
        fz.extrair(con)
        piloto.preparar(con)
        documentos = escopo(con)
        estados = pre_adquirir(documentos)
        print(json.dumps({"documentos": len(estados),
                          "estados": dict(Counter(estados.values()))}, indent=2))
        return 0
    resumo = executar()
    print(json.dumps({k: resumo[k] for k in (
        "premissa_s5", "documentos_no_escopo", "aquisicao", "veredito_por_perfil",
        "controles_corrigidos", "herdados", "manifesto")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
