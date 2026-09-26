"""Inventário textual de alcance; NÃO adjudica escala ou ausência de informação.

Contrato de 24/09. Busca auxiliar desenvolvida após reconhecimento das notas;
não é extensão da regra congelada GEOM-1 nem nova avaliação de cobertura.
Não extrai valores contábeis do XML, não faz cálculo de FCO e mascara números.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata

from scripts import fonte_rad_cvm as rad
from scripts.piloto_geometria_rank03b import conferir_protegidos
from scripts.reconhecer_geometria_rank03b import anexos_pdf

BASE = rad.RAIZ / "artefatos/alcance_geom1_rank03b_2026-09-24"
GEOM = rad.RAIZ / "artefatos/escala_geometrica_rank03b_2026-09-18"
PADROES = {
    "ativo_total": r"\b(?:ativo total|total do ativo|total de ativos|ativos totais)\b",
    "atividades_operacionais": r"\batividades operacionais\b",
    "mencao_dfc": r"\b(?:fluxos? de caixa|demonstracao d[oe]s? fluxos?)\b",
}


def normalizar(texto):
    return " ".join(unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().split())


def mascarar(texto):
    # Datas do documento ficam nos metadados; em trechos também são mascaradas.
    # Retira sinal e parênteses junto do número, não expõe polaridade de FCO.
    return re.sub(r"\(?\s*[-+−]?\s*\d[\d.,]*\s*\)?", " [valor omitido] ", texto).strip()


def inventariar_texto(texto):
    paginas = texto.split("\f")
    if paginas[-1].strip() == "":
        paginas.pop()
    saida = []
    for n, pagina in enumerate(paginas, 1):
        unidades, mencoes = [], []
        for i, linha in enumerate(pagina.splitlines(), 1):
            t = normalizar(linha)
            if "em milhares de reais" in t:
                unidades.append({"linha": i, "trecho": mascarar(linha)})
            for tipo, padrao in PADROES.items():
                if re.search(padrao, t):
                    mencoes.append({"tipo": tipo, "linha": i, "trecho": mascarar(linha)})
        saida.append({"pagina": n, "declaracoes_de_unidade": unidades, "mencoes": mencoes})
    return saida


def executar():
    pin = json.loads((BASE / "pin.json").read_text())
    contrato = rad.RAIZ / pin["contrato"]
    if rad.sha256(contrato) != pin["contrato_sha256"]:
        raise AssertionError("contrato diferente do pin")
    if rad.sha256(rad.RAIZ / pin["origem"]) != pin["origem_sha256"]:
        raise AssertionError("candidatas diferentes do pin")
    selecao = json.loads((GEOM / "selecao.json").read_text())
    protegido = conferir_protegidos(selecao)
    destino = BASE / "inventario_textual.json"
    pin_execucao = BASE / "pin_execucao.json"
    if destino.exists() or pin_execucao.exists():
        raise FileExistsError("execução já registrada; não sobrescrever")
    versao = subprocess.run(["pdftotext", "-v"], capture_output=True, check=True).stderr.decode().splitlines()[0]
    fontes = [(doc, rad.BRUTOS / f"{doc['id_doc']}.zip") for doc in pin["fontes"]]
    for doc, path in fontes:
        if rad.sha256(path) != doc["sha256"]:
            raise AssertionError("fonte diferente do pin")
    identidade = {"pin_sha256": rad.sha256(BASE / "pin.json"), "poppler": versao,
                  "codigo_sha256": {p: rad.sha256(rad.RAIZ / p) for p in (
                      "scripts/inventariar_alcance_geom1_rank03b.py", "scripts/reconhecer_geometria_rank03b.py",
                      "scripts/piloto_geometria_rank03b.py", "scripts/fonte_rad_cvm.py")},
                  "protegidos_antes": protegido}
    pin_execucao.write_text(json.dumps(identidade, ensure_ascii=False, indent=2) + "\n")
    registros = []
    for doc, path in fontes:
        for indice, grupo, pdf in anexos_pdf(path):
            info = subprocess.run(["pdfinfo", "-"], input=pdf, capture_output=True, check=True).stdout.decode()
            n = int(re.search(r"^Pages:\s+(\d+)$", info, re.M).group(1))
            texto = subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf,
                                   capture_output=True, check=True).stdout.decode()
            paginas = inventariar_texto(texto)
            if len(paginas) != n:
                raise AssertionError("paginação textual não coincide com PDF")
            registros.append({**doc, "anexo": indice, "grupo": grupo,
                              "sha256_pdf": hashlib.sha256(pdf).hexdigest(), "paginas": paginas})
    resultado = {"estado": "inventario_textual_nao_adjudicado", "registros": registros,
                 "limite": "Busca lexical pode perder sinônimos ou texto fragmentado; ausência de match NÃO demonstra ausência da informação.",
                 "protegidos_depois": conferir_protegidos(selecao),
                 "escala_promovida": False, "gates_medidos": False}
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")
    return resultado


if __name__ == "__main__":
    r = executar()
    print(json.dumps({"estado": r["estado"], "anexos": len(r["registros"]),
                      "paginas": sum(len(d["paginas"]) for d in r["registros"])}, ensure_ascii=False))
