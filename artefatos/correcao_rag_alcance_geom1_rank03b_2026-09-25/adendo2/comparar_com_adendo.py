"""Adendo 2: a busca nova contra a do adendo, campo a campo — o esperado, fixado antes
de rodar, é que só mudem a identidade (código, data, contratos) e o texto do `limite`.

Lê só saídas publicadas (sem valores). Execute da raiz: .venv/bin/python <este arquivo> > <saída>
"""
import hashlib
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ADENDO = AQUI.parent / "adendo" / "busca"
REFERENCIA_SHA256 = {"conferencia_revisao.json": "bd946cad6cf5b56dc26917a620b9617aa42e635af04fde191f55341fa037933f",
                     "pin_revisao.json": "c9db52e8a70b07e6e61c5398d4940cc80588b8b1540513e0d911c355300006db"}


def _ler(pasta: Path, nome: str, sha: str | None = None) -> dict:
    dados = (pasta / nome).read_bytes()
    if sha and hashlib.sha256(dados).hexdigest() != sha:
        raise AssertionError(f"{nome} do adendo diferente do publicado")
    return json.loads(dados)


def main() -> dict:
    saida = {"sentido": "busca do adendo 2 contra a do adendo; só nomes de campos e booleanos"}
    for nome, sha in REFERENCIA_SHA256.items():
        antigo, novo = _ler(ADENDO, nome, sha), _ler(AQUI / "busca", nome)
        chaves = sorted(set(antigo) | set(novo))
        saida[nome] = {"campos_diferentes": [k for k in chaves if antigo.get(k) != novo.get(k)],
                       "campos_so_na_nova": [k for k in chaves if k not in antigo]}
    resultado = saida["conferencia_revisao.json"]
    identidade = saida["pin_revisao.json"]
    saida["esperado_cumprido"] = (
        resultado["campos_diferentes"] == ["limite"]
        and set(identidade["campos_diferentes"]) <= {"codigo_sha256", "data", "adendo2_correcao",
                                                       "adendo2_correcao_sha256"})
    return saida


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
