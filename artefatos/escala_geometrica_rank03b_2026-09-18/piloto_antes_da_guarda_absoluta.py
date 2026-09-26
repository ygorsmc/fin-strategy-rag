"""Piloto GEOM-1 offline e separado da cadeia governante. Sem G0 ou alvo."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from scripts import fonte_rad_cvm as rad
from scripts import provas_geometricas_rank03b as geom
from scripts.reconhecer_geometria_rank03b import BASE

CODIGO = ("scripts/reconhecer_geometria_rank03b.py", "scripts/provas_geometricas_rank03b.py",
          "scripts/piloto_geometria_rank03b.py", "scripts/fonte_rad_cvm.py",
          "resultados/contratos_escala_geometrica_rank03b_2026-09-18.md",
          "resultados/adendo_escala_geometrica_rank03b_2026-09-18.md")


def conferir_protegidos(selecao):
    # Os artefatos vigentes e as fontes não são destino deste piloto.
    caminhos = [p for p in selecao["entradas_sha256"]
                if p.startswith(("artefatos/painel_pesquisa_rank03b/", "artefatos/cvm",
                                 "corpus/cvm/painel_pesquisa_rank03b/"))]
    resultado = {p: rad.sha256(Path(p)) == selecao["entradas_sha256"][p] for p in caminhos}
    if not all(resultado.values()):
        raise AssertionError("fonte ou cadeia governante mudou desde o pin")
    return resultado


def executar(etapa):
    if etapa not in ("desenho", "verificacao"):
        raise ValueError(etapa)
    selecao = json.loads((BASE / "selecao.json").read_text())
    protegidos = conferir_protegidos(selecao)
    pin = BASE / f"pin_{etapa}.json"
    destino = BASE / f"piloto_{etapa}.json"
    if pin.exists() or destino.exists():
        raise FileExistsError("passagem já registrada; não sobrescrever nem ajustar silenciosamente")
    versao = subprocess.run(["pdftotext", "-v"], capture_output=True, check=True).stderr.decode().splitlines()[0]
    identidade = {"codigo_sha256": {p: rad.sha256(Path(p)) for p in CODIGO},
                  "selecao_sha256": rad.sha256(BASE / "selecao.json"), "poppler": versao,
                  "protegidos_antes": protegidos}
    pin.write_text(json.dumps(identidade, ensure_ascii=False, indent=2) + "\n")
    registros = []
    for doc in selecao[etapa] + selecao["sentinelas"]:
        registro = dict(doc)
        try:
            r = geom.extrair_documento(rad.BRUTOS / f"{doc['id_doc']}.zip", doc["dt_refer"], doc["sha256"])
            registro.update(estado="lido", evidencia=r,
                            escala_proposta={"bruto": "MIL", "dividido": "UNIDADE"}.get(r["classe"]))
        except (ET.ParseError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as erro:
            registro.update(estado="falha_de_leitura", erro=type(erro).__name__, escala_proposta=None)
        registro["papel"] = etapa if doc in selecao[etapa] else "sentinela"
        registros.append(registro)
        print(doc["id_doc"], registro["estado"], registro["escala_proposta"], flush=True)
    suporte = [r for r in registros if r["papel"] == etapa]
    resumo = {"etapa": etapa, "regra": geom.REGRA, "documentos": len(suporte),
              "por_estrato": dict(Counter(f"{r['formato']}|{r['escala_declarada']}|"
                                         f"{r['escala_proposta'] or r['estado']}" for r in suporte)),
              "com_prova": sum(r["escala_proposta"] is not None for r in suporte),
              "falhas_de_leitura": sum(r["estado"] != "lido" for r in suporte),
              "registros": registros, "pin_sha256": rad.sha256(pin),
              "protegidos_depois": conferir_protegidos(selecao),
              "promovido_ao_manifesto": False, "g0_medido": False}
    destino.write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n")
    return resumo


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("etapa", choices=("desenho", "verificacao"))
    r = executar(parser.parse_args().etapa)
    print(json.dumps({k: r[k] for k in ("documentos", "com_prova", "falhas_de_leitura", "por_estrato")},
                     ensure_ascii=False, indent=2))
