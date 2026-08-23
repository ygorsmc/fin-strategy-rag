"""Reconcilia uma chamada órfã sem repetir a API nem apagar o journal."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.avaliacao import reconciliar_chamada_orfa  # noqa: E402
from src.bloqueio import bloqueio_exclusivo  # noqa: E402
from src.config import (  # noqa: E402
    DIR_LOGS_EXECUCOES,
    DIR_RESULTADOS_AVALIACAO,
    carregar_config,
)


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fingerprint", required=True)
    parser.add_argument("--call-id", required=True)
    parser.add_argument("--conjunto", choices=("dev", "teste"), required=True)
    parser.add_argument(
        "--repeticao-estabilidade", type=int, choices=(1, 2, 3)
    )
    parser.add_argument(
        "--confirmar-debito-conservador",
        action="store_true",
        help="Confirma que uma resposta perdida será marcada como erro e debitada.",
    )
    parser.add_argument(
        "--dir-resultados", type=Path, default=DIR_RESULTADOS_AVALIACAO
    )
    parser.add_argument("--dir-logs", type=Path, default=DIR_LOGS_EXECUCOES)
    args = parser.parse_args(argv)
    if not args.confirmar_debito_conservador:
        print(
            "FALHOU: use --confirmar-debito-conservador após conferir "
            "fingerprint, call_id e estimativa no journal."
        )
        return 1
    if args.repeticao_estabilidade is not None and args.conjunto != "teste":
        print("FALHOU: repetição de estabilidade exige --conjunto teste.")
        return 1
    sufixo = (
        f"_estabilidade_{args.repeticao_estabilidade}"
        if args.repeticao_estabilidade is not None
        else ""
    )
    checkpoint = args.dir_resultados / (
        f"checkpoint{sufixo}.jsonl"
        if sufixo
        else f"checkpoint_{args.conjunto}.jsonl"
    )
    journal = args.dir_logs / "journal_chamadas" / f"{args.fingerprint}.jsonl"
    lock = args.dir_resultados / (
        f".avaliacao_{args.conjunto}{sufixo}.lock"
    )
    try:
        with bloqueio_exclusivo(lock, "a reconciliação da avaliação"):
            item = reconciliar_chamada_orfa(
                carregar_config(),
                fingerprint=args.fingerprint,
                call_id=args.call_id,
                caminho_journal=journal,
                caminho_checkpoint=checkpoint,
                dir_auditoria=args.dir_logs / "reconciliacoes",
            )
        print(
            "OK: chamada reconciliada como erro; débito contabilizado US$ "
            f"{item.custo_usd:.6f} em {checkpoint}."
        )
        return 0
    except Exception as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(principal())
