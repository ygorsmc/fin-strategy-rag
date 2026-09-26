"""Adendo 3: a busca nova contra a do adendo 2, campo a campo — o esperado, fixado antes
de rodar, é que só mudem a identidade (código, data, contratos) e o texto do `limite`.

Lê só saídas publicadas (sem valores). Execute da raiz: .venv/bin/python <este arquivo> > <saída>
"""
import hashlib
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ADENDO = AQUI.parent / "adendo2" / "busca"
REFERENCIA_SHA256 = {"conferencia_revisao.json": "bc1d3dc5c57d53829136b38d9becbe4318ffaa63034e6c619420a3f9f8ccda87",
                     "pin_revisao.json": "cc5f2f8bda397904d095c4887f6888de7b915e53bdf9f16c425127a39b0e8ffc"}


def _ler(pasta: Path, nome: str, sha: str | None = None) -> dict:
    dados = (pasta / nome).read_bytes()
    if sha and hashlib.sha256(dados).hexdigest() != sha:
        raise AssertionError(f"{nome} do adendo 2 diferente do publicado")
    return json.loads(dados)


def main() -> dict:
    saida = {"sentido": "busca do adendo 3 contra a do adendo 2; só nomes de campos e booleanos"}
    for nome, sha in REFERENCIA_SHA256.items():
        antigo, novo = _ler(ADENDO, nome, sha), _ler(AQUI / "busca", nome)
        chaves = sorted(set(antigo) | set(novo))
        saida[nome] = {"campos_diferentes": [k for k in chaves if antigo.get(k) != novo.get(k)],
                       "campos_so_na_nova": [k for k in chaves if k not in antigo]}
    resultado = saida["conferencia_revisao.json"]
    identidade = saida["pin_revisao.json"]
    saida["esperado_cumprido"] = (
        resultado["campos_diferentes"] == ["limite"]
        and set(identidade["campos_diferentes"]) <= {"codigo_sha256", "data", "adendo3_correcao",
                                                       "adendo3_correcao_sha256"})
    return saida


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
