"""Plugin pytest do A1 (adendo da correção RAG): aplica UMA mutação textual ao código
da busca, em memória, antes de os testes o importarem. Não edita arquivo nenhum.

A mutação vem do JSON apontado por MUTACAO_ARQUIVO: {"id", "antigo", "novo"}.
O trecho `antigo` tem de aparecer exatamente uma vez no código; `antigo` vazio é o
controle (código sem mutação, pelo mesmo caminho de importação).
"""
import json
import os
from pathlib import Path
import sys
import types

NOME = "scripts.conferir_alcance_geom1_rank03b"


def pytest_configure(config):
    arquivo = os.environ.get("MUTACAO_ARQUIVO")
    if not arquivo:
        return
    mutacao = json.loads(Path(arquivo).read_text())
    import scripts  # pacote de namespace: sem __init__.py
    caminho = Path(list(scripts.__path__)[0]) / "conferir_alcance_geom1_rank03b.py"
    fonte = caminho.read_text()
    if mutacao["antigo"]:
        if fonte.count(mutacao["antigo"]) != 1:
            raise RuntimeError(f"mutação {mutacao['id']}: trecho não aparece exatamente uma vez")
        fonte = fonte.replace(mutacao["antigo"], mutacao["novo"])
    modulo = types.ModuleType(NOME)
    modulo.__file__ = str(caminho)
    modulo.__package__ = "scripts"
    sys.modules[NOME] = modulo
    exec(compile(fonte, str(caminho), "exec"), modulo.__dict__)
    scripts.conferir_alcance_geom1_rank03b = modulo
