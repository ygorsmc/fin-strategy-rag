"""Reexecuta adjudicação de documentos corrigidos, sem aquisição ou escrita."""
import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts import adjudicar_escala_rank03b as adj
from scripts import fonte_rad_cvm as rad


base = Path("artefatos/painel_pesquisa_rank03b")
manifesto = Path("corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv")
linhas = list(csv.DictReader(manifesto.open()))
atuais = {r["id_doc"]: r for r in map(json.loads, (base / "adjudicacao/evidencias.jsonl").read_text().splitlines())}
ids = sorted({r["id_doc"] for r in linhas if r["base"] == "corrigida_documento"} | {"152742"})


def conferir(i):
    r = atuais[i]
    caminho = base / "rad/brutos" / f"{i}.zip"
    hash_ok = hashlib.sha256(caminho.read_bytes()).hexdigest() == r["sha256"]
    f = rad.ler(caminho, grupos=rad.GRUPOS_NOTAS)
    novo = adj.adjudicar_formulario(f, r["escala_declarada"], r["dt_refer"])
    campos = ("veredito", "escala_do_formulario", "numerica", "cabecalho", "evidencia", "motivo")
    return {"id_doc": i, "sha_confere": hash_ok,
            "campos_divergentes": [c for c in campos if novo[c] != r[c]],
            "veredito": novo["veredito"]}


with ThreadPoolExecutor(max_workers=4) as pool:
    resultados = list(pool.map(conferir, ids))
print(json.dumps({"documentos": len(ids), "resultados": resultados}, ensure_ascii=False, indent=2))
