"""Reconhecimento offline de layouts; não adjudica escala nem calcula alvo.

Contrato: resultados/contratos_escala_geometrica_rank03b_2026-09-18.md.
Saída mascarada. As notas permanecem nos pacotes originais; não publica texto
integral nem valores de caixa. Poppler é uma ferramenta local, sem rede.
"""
from __future__ import annotations

import argparse
import base64
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from scripts import fonte_rad_cvm as rad

BASE = Path("artefatos/escala_geometrica_rank03b_2026-09-18")
EVIDENCIAS = Path("artefatos/painel_pesquisa_rank03b/adjudicacao/evidencias.jsonl")
CONTRATO = Path("resultados/contratos_escala_geometrica_rank03b_2026-09-18.md")


def escolher(registros):
    estratos = defaultdict(list)
    for r in registros:
        estratos[(r["formato"], r["escala_declarada"])].append(r)
    def ordem(r):
        chave = "|".join(str(r[k]) for k in ("cd_cvm", "conjunto", "dt_refer", "versao"))
        return hashlib.sha256(("geometria-2026-09-18|" + chave).encode()).hexdigest()
    saida = {"desenho": [], "verificacao": [], "sentinelas": []}
    cias_desenho = set()
    def retirar(rs, n, excluidas):
        cias, escolhidos = set(excluidas), []
        for r in sorted(rs, key=ordem):
            if r["cd_cvm"] in cias:
                continue
            escolhidos.append({k: r[k] for k in (
                "id_doc", "cd_cvm", "conjunto", "dt_refer", "versao", "formato",
                "escala_declarada", "sha256")})
            cias.add(r["cd_cvm"])
            if len(escolhidos) == n:
                break
        return escolhidos
    for _, rs in sorted(estratos.items()):
        ds = retirar(rs, 2, set())
        saida["desenho"].extend(ds)
        cias_desenho.update(r["cd_cvm"] for r in ds)
    for _, rs in sorted(estratos.items()):
        saida["verificacao"].extend(retirar(rs, 3, cias_desenho))
    for r in registros:
        if r["id_doc"] in ("76468", "152742"):
            saida["sentinelas"].extend(retirar([r], 1, set()))
    return saida


def anexos_pdf(caminho):
    """Mesmo índice original que rad._anexos; inclui apenas notas."""
    nome = rad.validar_pacote(caminho)
    with zipfile.ZipFile(caminho) as externo:
        dados = externo.read(nome)
    if not rad.XML_UNICO.fullmatch(nome):
        with zipfile.ZipFile(io.BytesIO(dados)) as interno:
            if "AnexoDocumento.xml" not in interno.namelist():
                return
            dados = interno.read("AnexoDocumento.xml")
    indice = 0
    for _, e in ET.iterparse(io.BytesIO(dados), events=("end",)):
        pdf = e.find("ImagemObjetoArquivoPdf")
        if pdf is None:
            continue
        conteudo = (pdf.text or "").strip()
        grupo = (e.findtext("NumeroGrupoRelacionado") or "").strip()
        e.clear()
        if not conteudo:
            continue
        if grupo in rad.GRUPOS_NOTAS:
            yield indice, grupo, base64.b64decode(conteudo, validate=True)
        indice += 1


def paginas_bbox(pdf):
    p = subprocess.run(["pdftotext", "-bbox-layout", "-", "-"], input=pdf,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=True)
    raiz = ET.fromstring(p.stdout)
    ns = {"h": "http://www.w3.org/1999/xhtml"}
    paginas = []
    for pagina in raiz.findall(".//h:page", ns):
        linhas = []
        for linha in pagina.findall(".//h:line", ns):
            palavras = [dict(texto=w.text or "", **{k: float(w.get(k)) for k in
                        ("xMin", "yMin", "xMax", "yMax")}) for w in linha.findall("h:word", ns)]
            if palavras:
                linhas.append(palavras)
        paginas.append({"largura": float(pagina.get("width")),
                        "altura": float(pagina.get("height")), "linhas": linhas})
    return paginas


def mascarar(texto):
    # Datas identificadas são metadados permitidos; todos os demais números
    # são mascarados, inclusive saldos, notas de rodapé e contas por ação.
    tokens = re.split(r"(\b\d{2}/\d{2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b)", texto)
    return "".join(t if i % 2 else re.sub(r"\d[\d.,]*", "[n]", t)
                   for i, t in enumerate(tokens))


def reconhecer(doc):
    caminho = rad.BRUTOS / f"{doc['id_doc']}.zip"
    if rad.sha256(caminho) != doc["sha256"]:
        raise AssertionError("pacote diverge do pin")
    saida = {"id_doc": doc["id_doc"], "dt_refer": doc["dt_refer"], "paginas": []}
    for indice, grupo, pdf in anexos_pdf(caminho):
        for numero, pagina in enumerate(paginas_bbox(pdf), 1):
            linhas = pagina["linhas"]
            alvos = [w for w in linhas if re.search(
                r"ativo total|total do ativo|caixa e equivalentes de caixa|total do passivo",
                " ".join(p["texto"] for p in w).lower())]
            if not alvos:
                continue
            saida["paginas"].append({
                "anexo": indice, "grupo": grupo, "pagina": numero,
                "largura": pagina["largura"], "altura": pagina["altura"],
                "linhas": [{"texto": mascarar(" ".join(p["texto"] for p in w)),
                            "x": round(w[0]["xMin"], 2), "fim_x": round(w[-1]["xMax"], 2),
                            "y": round(w[0]["yMin"], 2)}
                           for w in linhas if w[0]["yMin"] < 220 or any(
                               abs(w[0]["yMin"] - a[0]["yMin"]) < 70 for a in alvos)]})
    return saida


def main():
    p = argparse.ArgumentParser()
    p.add_argument("etapa", choices=("selecionar", "desenho"))
    args = p.parse_args()
    BASE.mkdir(parents=True, exist_ok=True)
    destino = BASE / "selecao.json"
    if args.etapa == "selecionar":
        if destino.exists():
            raise FileExistsError("seleção já pinada; não sobrescrever")
        registros = [json.loads(l) for l in EVIDENCIAS.read_text().splitlines()]
        s = escolher(registros)
        s["entradas_sha256"] = {str(c): rad.sha256(c) for c in (
            EVIDENCIAS, CONTRATO, Path(__file__), Path("artefatos/cvm.duckdb"),
            Path("artefatos/cvm_treino.duckdb"), rad.MANIFESTO,
            Path("corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv"),
            Path("artefatos/painel_pesquisa_rank03b/painel.duckdb"),
            Path("artefatos/painel_pesquisa_rank03b/gates_g0_g1.json"))}
        destino.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: [(r["id_doc"], r["cd_cvm"], r["formato"], r["escala_declarada"])
                             for r in s[k]] for k in ("desenho", "verificacao", "sentinelas")}))
    else:
        selecao = json.loads(destino.read_text())
        for doc in selecao["desenho"] + selecao["sentinelas"]:
            try:
                r = reconhecer(doc)
                r["estado"] = "lido"
            except (ET.ParseError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as erro:
                r = {"id_doc": doc["id_doc"], "estado": "falha_de_leitura",
                     "erro": type(erro).__name__, "paginas": []}
            r["codigo_sha256"] = rad.sha256(Path(__file__))
            (BASE / f"layout_{doc['id_doc']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n")
            print(doc["id_doc"], r["estado"], len(r["paginas"]), "páginas com rótulo candidato", flush=True)


if __name__ == "__main__":
    main()
