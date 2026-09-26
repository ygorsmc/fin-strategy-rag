"""Adendo da correção RAG: a autoverificação nova (A5) sobre as saídas da primeira
execução da correção (`../busca/`), que foram gravadas sob a autoverificação anterior.

Lê as duas saídas conferindo o hash registrado no relatório da onda, relê em
memória os valores comparados das fontes fixadas (como a reconferência faz, O1:
o FCO só para barrar publicação) e publica só booleanos. Não regrava nada.

Execute da raiz: PYTHONPATH=. .venv/bin/python <este arquivo> > <saída>
"""
import json
from pathlib import Path

from scripts import conferir_alcance_geom1_rank03b as c

PRIMEIRA = Path(__file__).resolve().parents[1] / "busca"
PUBLICADAS = {"pin_revisao.json": "5a98d2e212608dc6149d622d18e2cd2e93f19034095b7d038c7c20d125886413",
              "conferencia_revisao.json": "b42c7bced791ef3d1fdc07b8df293d8c90b5347ced7005251ce564bdd41e651f"}


def main() -> dict:
    lidos = c._ler_fixados([(PRIMEIRA / nome, sha, "saída da primeira execução") for nome, sha in PUBLICADAS.items()]
                           + [(c.BASE / "pin.json", c.PIN_ALCANCE_SHA256, "pin de alcance")])
    saidas = {nome: json.loads(dados) for nome, dados in zip(PUBLICADAS, lidos)}
    fontes = c.validar_fontes(json.loads(lidos[-1]))
    for nome in PUBLICADAS:
        documentos = saidas[nome].get("fontes") if nome == "pin_revisao.json" else saidas[nome]["documentos"]
        c.exigir_mesmo_universo(fontes, documentos, nome)
    pacotes = c._ler_pacotes(fontes)
    comparados = []
    for fonte in fontes:
        form = pacotes[fonte["id_doc"]].form
        comparados += [*c.alvos_ativo(form).values(), *c.alvos_fco(form).values(), *c.saldos_de_caixa(form)]
    resultado = {}
    for nome, saida in saidas.items():
        try:
            c._autoverificar(saida, comparados)
            resultado[nome] = True
        except c.VazamentoDeValor:
            resultado[nome] = False
    return {"sentido": "autoverificação do adendo (A5) sobre as saídas da primeira execução; só booleanos",
            "saidas_sha256": PUBLICADAS,
            "codigo_sha256": c.rad.sha256(c.rad.RAIZ / "scripts/conferir_alcance_geom1_rank03b.py"),
            "autoverificacao": resultado}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
