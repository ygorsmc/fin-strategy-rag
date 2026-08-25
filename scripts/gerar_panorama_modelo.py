"""Calcula OFFLINE o que a rota prospectiva do produto pode dizer (RN07).

Dois artefatos, e a separação entre eles é a fronteira da RN07 em disco:

* `artefatos/modelo/panorama.json` — **agregado**, versionado, seguro para o
  deploy público: contagem no decil superior sobre o painel inteiro, taxa-base
  e o regime de risco por porte. Nada aqui identifica companhia.
* `artefatos/modelo/escores_por_companhia.json` — **por emissor**, FORA do Git,
  gerado só com `--com-escores`. É o que o modo local/autenticado consome.

O deploy público não precisa nem receber o segundo arquivo: assim ele não tem o
dado que a RN07 proíbe expor, em vez de tê-lo e prometer não usar.

    python -m scripts.gerar_panorama_modelo --painel artefatos/cvm_treino.duckdb

Custo de API: zero.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.modelo.construir_painel import COLUNAS_FEATURES, construir_painel  # noqa: E402
from src.modelo.treinar import (  # noqa: E402
    avaliar,
    construir_gradient_boosting,
    dividir_walk_forward,
)

#: Faixas de porte do regime de risco. Os cortes vêm da leitura descritiva de
#: 2026-08-24 que mostrou porte funcionando como interruptor em instituição
#: financeira (0,6% acima de R$500 bi contra 29,6% abaixo de R$10 bi) e quase
#: nada nas demais (21,0% contra 37,5%).
FAIXAS = (
    ("≥ R$ 500 bi", 5e11),
    ("R$ 100–500 bi", 1e11),
    ("R$ 10–100 bi", 1e10),
    ("< R$ 10 bi", 0.0),
)

#: Alvo publicado. O de dois trimestres consecutivos venceu o de um em todas as
#: dimensões práticas (lift no top-10% 2,55 → 3,36) — ver
#: `resultados/revisoes_modelo_2026-08-23.md`.
TRIMESTRES_CONSECUTIVOS = 2


def _regime_por_porte(con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    """Taxa histórica de prejuízo por faixa de porte × setor — retrospectivo."""
    caso = "CASE " + " ".join(
        f"WHEN i.ativo_total >= {limite} THEN '{rotulo}'"
        for rotulo, limite in FAIXAS
        if limite > 0
    ) + f" ELSE '{FAIXAS[-1][0]}' END"
    linhas = con.execute(
        f"""
        SELECT {caso} AS faixa,
               c.is_banco,
               count(*) AS n,
               sum(CASE WHEN i.lucro_liquido_consolidado < 0 THEN 1 ELSE 0 END)
                   ::DOUBLE / count(*) AS taxa
        FROM indicadores i
        JOIN companhias c USING (cd_cvm)
        WHERE i.lucro_liquido_consolidado IS NOT NULL
          AND i.ativo_total IS NOT NULL
        GROUP BY 1, 2
        """
    ).fetchall()
    ordem = {rotulo: indice for indice, (rotulo, _) in enumerate(FAIXAS)}
    limites = dict(FAIXAS)
    saida = [
        {
            "rotulo": faixa,
            "limite_inferior_reais": float(limites[faixa]),
            "instituicao_financeira": bool(is_banco),
            "n_observacoes": int(n),
            "taxa_prejuizo": float(taxa),
        }
        for faixa, is_banco, n, taxa in linhas
    ]
    saida.sort(key=lambda item: (not item["instituicao_financeira"], ordem[item["rotulo"]]))
    return saida


def principal() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--painel", type=Path, required=True)
    analisador.add_argument(
        "--saida", type=Path, default=Path("artefatos/modelo/panorama.json")
    )
    analisador.add_argument(
        "--saida-escores",
        type=Path,
        default=Path("artefatos/modelo/escores_por_companhia.json"),
    )
    analisador.add_argument(
        "--com-escores",
        action="store_true",
        help="grava também o escore por companhia (fora do Git; modo local)",
    )
    argumentos = analisador.parse_args()

    con = duckdb.connect(str(argumentos.painel), read_only=True)
    colunas = list(COLUNAS_FEATURES)
    try:
        painel = construir_painel(
            con, trimestres_consecutivos=TRIMESTRES_CONSECUTIVOS
        )
        divisoes = dividir_walk_forward(painel)
        if not divisoes:
            raise SystemExit("painel sem folds suficientes para gerar panorama")

        # AUC médio de todos os folds — o número que acompanha o panorama para
        # que ninguém leia o escore sem saber o quanto ele vale.
        aucs = []
        for divisao in divisoes:
            modelo = construir_gradient_boosting()
            modelo.fit(
                divisao.treino[colunas], divisao.treino["rotulo"].to_numpy(int)
            )
            escore = modelo.predict_proba(divisao.teste[colunas])[:, 1]
            metrica = avaliar(
                "fold", divisao.teste["rotulo"].to_numpy(int), escore, limiar=0.5
            )
            if metrica.roc_auc is not None:
                aucs.append(metrica.roc_auc)

        # O trimestre de referência é o último fold: treino estritamente no
        # passado dele, como em qualquer outro ponto do desenho.
        ultimo = divisoes[-1]
        modelo = construir_gradient_boosting()
        modelo.fit(ultimo.treino[colunas], ultimo.treino["rotulo"].to_numpy(int))
        escores = modelo.predict_proba(ultimo.teste[colunas])[:, 1]
        quadro = ultimo.teste.copy()
        quadro["escore"] = escores
        k = max(1, int(round(len(quadro) * 0.10)))
        no_decil = quadro.nlargest(k, "escore")

        # Limiar ABSOLUTO — o dobro da taxa-base do trimestre. A contagem no
        # decil superior é sempre 10% do painel por definição e não pode ser
        # publicada como resultado do modelo; esta varia com o trimestre e diz
        # algo. Ver `src/projecao.py::_bloco_panorama`.
        taxa_base = float(quadro["rotulo"].mean())
        limiar = 2.0 * taxa_base
        acima = int((quadro["escore"] >= limiar).sum())

        fracao_nao_financeira = float(
            1.0 - painel.quadro["instituicao_financeira"].mean()
        )
        panorama = {
            "trimestre_referencia": ultimo.trimestre_teste,
            "n_companhias_avaliadas": int(len(quadro)),
            "n_acima_do_dobro_da_base": acima,
            "limiar_dobro_da_base": limiar,
            "n_no_decil_superior": int(len(no_decil)),
            "taxa_base_painel": taxa_base,
            "n_observacoes_treino": int(painel.n_observacoes),
            "fracao_nao_financeira_treino": fracao_nao_financeira,
            "auc_walk_forward": float(np.mean(aucs)) if aucs else None,
            "alvo": "prejuízo em T+1 e T+2",
            "faixas_de_porte": _regime_por_porte(con),
        }
        argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
        argumentos.saida.write_text(
            json.dumps(panorama, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"panorama agregado → {argumentos.saida}")
        print(
            f"  {ultimo.trimestre_teste}: {len(no_decil)}/{len(quadro)} no decil "
            f"superior · AUC walk-forward {panorama['auc_walk_forward']:.3f}"
        )

        if argumentos.com_escores:
            por_companhia = {
                str(cd): float(valor)
                for cd, valor in zip(quadro["cd_cvm"], quadro["escore"])
            }
            argumentos.saida_escores.write_text(
                json.dumps(
                    {
                        "trimestre_referencia": ultimo.trimestre_teste,
                        "alvo": panorama["alvo"],
                        "escores": por_companhia,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(
                f"escores por companhia → {argumentos.saida_escores} "
                f"({len(por_companhia)} companhias) — FORA DO GIT"
            )
    finally:
        con.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(principal())
