"""Gera a amostra fixa de groundedness e o plano 10×3 de estabilidade."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.auditoria import preparar_auditoria_final  # noqa: E402
from src.config import DIR_RESULTADOS_AVALIACAO, carregar_config  # noqa: E402


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir-resultados",
        type=Path,
        default=DIR_RESULTADOS_AVALIACAO,
    )
    args = parser.parse_args(argv)
    try:
        groundedness, estabilidade = preparar_auditoria_final(
            carregar_config(), args.dir_resultados
        )
    except Exception as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}")
        return 1
    print(f"Template de groundedness: {groundedness}")
    print(f"Plano de estabilidade: {estabilidade}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
