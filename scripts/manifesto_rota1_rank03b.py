"""Gera o manifesto de correções POR CONTA a partir das provas conferidas da ROTA vigente.

O nome do arquivo é da primeira versão; a regra vigente é a de `rota.REGRA`
(ROTA-2 desde 27/09), e o destino das evidências é `rota.DESTINO`.

Contrato: `resultados/contratos_caminho_medicao_rank03b_2026-09-27.md`, A1–A2 e
B7–B8. Roda DEPOIS da conferência documental independente: só grava correção
das contas `1` e `6.01` cuja prova a conferência aprovou, e nada se a conferência
recusou alguma correção ou se um controle foi corrigido (parada B7).

A validação é a do consumidor (`correcoes_por_conta_rank03b.validar_linhas`),
chamada pelo produtor antes de gravar e de novo relendo o arquivo gravado.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import adjudicar_escala_rank03b as adj  # noqa: E402
from scripts import correcoes_por_conta_rank03b as pc  # noqa: E402
from scripts import rota_prova_rank03b as rota  # noqa: E402


def gerar(pasta: Path = rota.DESTINO, destino: Path = pc.MANIFESTO) -> dict:
    """Grava o manifesto por conta. Recusa sobrescrever."""
    if destino.exists():
        raise FileExistsError(f"{destino} já existe: o manifesto por conta não é regravado")
    import duckdb

    from scripts import fonte_zip_cvm as fz
    from scripts import gates_painel_pesquisa_rank03b as gates

    registros, sha_ev = rota.ler_evidencias(pasta / "evidencias.jsonl")
    conferencia, sha_conf = rota.ler_conferencia(pasta / "conferencia.json")
    legado = gates.carregar_correcoes(gates.CORRECOES)
    con = duckdb.connect(":memory:")
    fz.extrair(con)
    linhas = pc.linhas_do_manifesto(con, registros, sha_ev, sha_conf)
    origem = pc.escrever(destino, linhas, registros, sha_ev, conferencia, sha_conf,
                         adj.pacotes_integros(), frozenset(legado))
    resumo = {"linhas": len(linhas), "sha256": origem,
              "por_conta": {c: sum(1 for l in linhas if l["conta"] == c) for c in pc.PROVA_DA_CONTA},
              "sha256_evidencias": sha_ev, "sha256_conferencia": sha_conf}
    return resumo


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rota", type=Path, default=rota.DESTINO)
    parser.add_argument("--destino", type=Path, default=pc.MANIFESTO)
    args = parser.parse_args(argv)
    print(json.dumps(gerar(args.rota, args.destino), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
