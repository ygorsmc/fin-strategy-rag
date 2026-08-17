"""Consolida estabilidade 10×3 e promove métricas após auditoria manual."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.auditoria import (  # noqa: E402
    consolidar_estabilidade,
    promover_metricas_auditadas,
)
from src.config import DIR_RESULTADOS_AVALIACAO, carregar_config  # noqa: E402


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir-resultados",
        type=Path,
        default=DIR_RESULTADOS_AVALIACAO,
    )
    parser.add_argument(
        "--somente-estabilidade",
        action="store_true",
        help="gera o relatório 10×3 sem tentar promover metricas_teste.json",
    )
    args = parser.parse_args(argv)
    config = carregar_config()
    try:
        caminho = consolidar_estabilidade(config, args.dir_resultados)
        print(f"Estabilidade consolidada: {caminho}")
        if not args.somente_estabilidade:
            metricas = promover_metricas_auditadas(
                config, args.dir_resultados
            )
            print(
                "Métricas auditadas: "
                f"status={metricas['_meta']['status']}, "
                "groundedness="
                f"{metricas['_meta']['groundedness_manual_score']:.3f}"
            )
    except Exception as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
