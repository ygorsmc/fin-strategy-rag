"""A8(d) do adendo da correção RAG: por que os tokens reais são recusados ou ambíguos.

Só contagens, independentes de qualquer alvo: lê os PDFs de notas das fontes
fixadas no pin (hash conferido, cópia privada), nunca o XML. Sustenta as frases
do relatório sobre recusas (datas, formas fora da gramática) e ambíguos (traços
de colunas vizinhas).

Execute da raiz: PYTHONPATH=. .venv/bin/python <este arquivo> > <saída>
"""
from collections import Counter
import json
from pathlib import Path
import re
import tempfile

from scripts import conferir_alcance_geom1_rank03b as c

DATA = re.compile(r"\d{1,2}\.\d{1,2}\.\d{2,4}")


def main() -> dict:
    (pin_bytes,) = c._ler_fixados([(c.BASE / "pin.json", c.PIN_ALCANCE_SHA256, "pin de alcance")])
    fontes = c.validar_fontes(json.loads(pin_bytes))
    documentos = []
    with tempfile.TemporaryDirectory(prefix="perfil_geom1_") as pasta:
        copias = c.conferir_fontes(fontes, c.rad.BRUTOS, copiar_para=Path(pasta))
        for fonte in fontes:
            (_, _, pdf), = c.anexos_pdf(copias[fonte["id_doc"]])
            modos = {}
            for modo in c.MODOS:
                aceitos, recusados, ambiguos = Counter(), Counter(), Counter()
                total = datas = 0
                for pagina in c.paginas_pdf(pdf, modo):
                    for linha in pagina.splitlines():
                        textos = [m.group() for m in c._padrao_de_token().finditer(linha)]
                        for texto, token in zip(textos, c.tokens_da_linha(linha), strict=True):
                            total += 1
                            if token.modulo is None:
                                recusados[token.motivo] += 1
                                datas += bool(DATA.fullmatch(texto))
                            elif token.sinal is None:
                                ambiguos[token.motivo] += 1
                            else:
                                aceitos[token.motivo] += 1
                modos[modo] = {"tokens": total, "aceitos_com_sinal": dict(sorted(aceitos.items())),
                               "recusados": dict(sorted(recusados.items())), "recusados_com_forma_de_data": datas,
                               "ambiguos": dict(sorted(ambiguos.items()))}
            documentos.append({"id_doc": fonte["id_doc"], "modos": modos})
    return {"sentido": "motivos dos tokens nas notas; independe de alvo; sem leitura do XML",
            "codigo_sha256": c.rad.sha256(c.rad.RAIZ / "scripts/conferir_alcance_geom1_rank03b.py"),
            "documentos": documentos}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
