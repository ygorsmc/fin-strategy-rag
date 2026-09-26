"""Extensão GEOM-1 pinada e offline; publica candidatas, não aplica correções."""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from scripts import fonte_rad_cvm as rad
from scripts import provas_geometricas_rank03b as geom
from scripts.piloto_geometria_rank03b import CODIGO, conferir_protegidos
from scripts.reconhecer_geometria_rank03b import BASE, EVIDENCIAS

PARECER = BASE / "parecer_piloto_verificacao.json"
CONTRATO = Path("resultados/contratos_extensao_geom1_rank03b_2026-09-18.md")


def chave_prova(doc, prova):
    return {"id_doc": doc["id_doc"], "anexo": prova["anexo"],
            "pagina": prova["pagina"], "conta": prova["conta"],
            "sha256_prova": hashlib.sha256(
                json.dumps(prova, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}


def validar_precondicoes(piloto, parecer, pin):
    if piloto["etapa"] != "verificacao" or piloto["regra"] != geom.REGRA:
        raise AssertionError("piloto incompatível")
    aceitas = [chave_prova(d, p) for d in piloto["registros"]
               if d["escala_proposta"] is not None
               for p in d["evidencia"]["provas"]]
    if (not aceitas or parecer.get("veredito") != "sem_erro_nas_aceitacoes_conferidas"
            or parecer.get("provas_conferidas") != aceitas):
        raise AssertionError("falta conferência independente de todas as aceitações")
    if parecer["piloto_sha256"] != rad.sha256(BASE / "piloto_verificacao.json"):
        raise AssertionError("parecer de outro piloto")
    if piloto["pin_sha256"] != rad.sha256(BASE / "pin_verificacao.json"):
        raise AssertionError("pin diferente do piloto")
    if pin["selecao_sha256"] != rad.sha256(BASE / "selecao.json"):
        raise AssertionError("seleção diferente do pin")
    if set(pin["codigo_sha256"]) != set(CODIGO):
        raise AssertionError("pin sem o conjunto completo de código/contratos")
    for nome, esperado in pin["codigo_sha256"].items():
        if rad.sha256(Path(nome)) != esperado:
            raise AssertionError(f"código/contrato mudou desde o piloto: {nome}")


def extrair(doc):
    r = {k: doc[k] for k in ("id_doc", "cd_cvm", "conjunto", "dt_refer", "versao",
                            "formato", "escala_declarada", "sha256", "papel", "trecho")}
    try:
        ev = geom.extrair_documento(rad.BRUTOS / f"{doc['id_doc']}.zip", doc["dt_refer"], doc["sha256"])
        escala = {"bruto": "MIL", "dividido": "UNIDADE"}.get(ev["classe"])
        r.update(estado="lido", evidencia=ev, escala_proposta=escala,
                 resultado="abstencao" if escala is None else
                 "confirmacao_candidata" if escala == doc["escala_declarada"] else "correcao_candidata")
    except (ET.ParseError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as erro:
        r.update(estado="falha_de_leitura", erro=type(erro).__name__,
                 escala_proposta=None, resultado="falha_de_leitura")
    return r


def executar():
    selecao = json.loads((BASE / "selecao.json").read_text())
    protegidos = conferir_protegidos(selecao)
    piloto = json.loads((BASE / "piloto_verificacao.json").read_text())
    parecer = json.loads(PARECER.read_text())
    pin_piloto = json.loads((BASE / "pin_verificacao.json").read_text())
    validar_precondicoes(piloto, parecer, pin_piloto)
    docs = [json.loads(l) for l in EVIDENCIAS.read_text().splitlines()]
    if len(docs) != 405 or len({d["id_doc"] for d in docs}) != 405:
        raise AssertionError("escopo não é o conjunto de 405 documentos pinados")
    versao = subprocess.run(["pdftotext", "-v"], capture_output=True, check=True).stderr.decode().splitlines()[0]
    if versao != pin_piloto["poppler"]:
        raise AssertionError("Poppler diferente do piloto")
    destino = BASE / "extensao"
    destino.mkdir(exist_ok=False)
    codigo = (*CODIGO, str(Path(__file__).relative_to(rad.RAIZ)), str(CONTRATO))
    pin = {"codigo_sha256": {p: rad.sha256(Path(p)) for p in codigo},
           "entradas_sha256": {str(p): rad.sha256(p) for p in (
               BASE / "selecao.json", BASE / "piloto_verificacao.json", PARECER, EVIDENCIAS)},
           "documentos": 405, "poppler": versao, "protegidos_antes": protegidos}
    (destino / "pin.json").write_text(json.dumps(pin, ensure_ascii=False, indent=2) + "\n")
    registros = []
    with (destino / "evidencias.jsonl").open("x") as saida, ThreadPoolExecutor(max_workers=3) as pool:
        for r in pool.map(extrair, sorted(docs, key=lambda d: d["id_doc"])):
            saida.write(json.dumps(r, ensure_ascii=False) + "\n")
            saida.flush()
            registros.append(r)
            if len(registros) % 25 == 0:
                print(len(registros), "/ 405", dict(Counter(d["resultado"] for d in registros)), flush=True)
    resumo = {"regra": geom.REGRA, "documentos": len(registros),
              "resultados": dict(Counter(d["resultado"] for d in registros)),
              "por_estrato": dict(Counter(f"{d['formato']}|{d['escala_declarada']}|{d['resultado']}"
                                         for d in registros)),
              "paginas_recusadas": dict(sum((Counter(d.get("evidencia", {}).get("recusas", {}))
                                             for d in registros), Counter())),
              "evidencias_sha256": rad.sha256(destino / "evidencias.jsonl"),
              "pin_sha256": rad.sha256(destino / "pin.json"),
              "protegidos_depois": conferir_protegidos(selecao),
              "promovido_ao_manifesto": False, "heranca_executada": False, "g0_medido": False}
    (destino / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n")
    return resumo


if __name__ == "__main__":
    print(json.dumps(executar(), ensure_ascii=False, indent=2))
