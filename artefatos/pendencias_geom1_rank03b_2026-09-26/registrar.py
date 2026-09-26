"""Registro reproduzível: hashes e esquema, nunca consulta valores do painel."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import unicodedata

from scripts import gates_painel_pesquisa_rank03b as gates
from scripts.piloto_geometria_rank03b import conferir_protegidos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fase", choices=("antes_testes", "depois_testes"))
    args = parser.parse_args()
    pasta = Path(__file__).resolve().parent
    destino = pasta / f"verificacao_{args.fase}.json"
    if destino.exists():
        raise FileExistsError("registro já existe")
    raiz = pasta.parents[1]
    selecao = json.loads((raiz / "artefatos/escala_geometrica_rank03b_2026-09-18/selecao.json").read_text())
    protegidos = conferir_protegidos(selecao)
    assert len(protegidos) == 7 and all(protegidos.values())
    correcoes = gates.carregar_correcoes(gates.CORRECOES)
    assert len(correcoes) == 0, "universo governante mudou: interromper"
    fontes = [
        "scripts/conferir_alcance_geom1_rank03b.py", "scripts/gates_painel_pesquisa_rank03b.py",
        "tests/test_conferir_alcance_geom1_rank03b.py", "tests/test_gates_painel_pesquisa_rank03b.py",
        "tests/test_pendencias_geom1_rank03b.py",
        "resultados/contratos_pendencias_geom1_rank03b_2026-09-26.md",
        "resultados/adendo_pendencias_geom1_rank03b_2026-09-26.md",
        "resultados/decisoes_executor_v2_rank03b_2026-09-26.md",
        str(Path(__file__).resolve().relative_to(raiz)),
    ]
    fontes += [str(p.relative_to(raiz)) for p in sorted((pasta / "antes").rglob("*.py"))]
    resultado = {
        "fase": args.fase, "python": platform.python_version(), "unicode": unicodedata.unidata_version,
        "protegidos_inalterados": protegidos,
        "protegidos_sha256": {p: selecao["entradas_sha256"][p] for p in protegidos},
        "manifesto_governante": {"schema_aceito": True, "correcoes": len(correcoes),
                                 "sha256": correcoes.origem_sha256},
        "arquivos_sha256": {p: hashlib.sha256((raiz / p).read_bytes()).hexdigest() for p in fontes},
        "busca_real_executada": False, "gates_reexecutados": False, "treino_executado": False,
    }
    with destino.open("x", encoding="utf-8") as fh:
        json.dump(resultado, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(json.dumps({"fase": args.fase, "protegidos": len(protegidos), "schema_aceito": True}))


if __name__ == "__main__":
    main()
