"""Reexecuta a conferência estrutural anterior sobre a cadeia CRF atual.

Somente leitura dos dados e reconstrução em memória; sem y real.
Grava apenas o resultado da conferência nesta pasta, sem alterar os pins.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import xml.etree.ElementTree as ET


BASE = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    fonte = Path("artefatos/conferencia_rf01_rf08_rank03b_2026-09-17/reproduzir_estrutura.py")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        runpy.run_path(str(fonte), run_name="__main__")
    resultado = json.loads(output.getvalue())
    pin = json.loads((BASE / "antes_execucao4b.json").read_text())
    resultado["protegidos_inalterados"] = {
        path: sha(path) == expected for path, expected in pin["protegidos"].items()
    }
    resultado["script_conferencia_sha256"] = sha(fonte)
    resultado["script_envoltoria_sha256"] = sha(__file__)
    suite = ET.parse(BASE / "pytest_final.xml").getroot().find("testsuite")
    resultado["suite_final"] = dict(suite.attrib)
    for flag in ("digest_confere", "cadeia_confere", "datas_das_provas_conferem"):
        assert resultado[flag], flag
    assert all(resultado["protegidos_inalterados"].values())
    assert not any(resultado["diferencas_linhas_persistidas"].values())
    assert resultado["ativos_antes_da_prova"] == 0
    # As ligações são registradas, não presumidas: podem detectar uma atualização
    # ainda em curso no verificador e devem ser conferidas antes da entrega.
    destino = BASE / "conferencia_estrutura_final.json"
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str) + "\n")
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
