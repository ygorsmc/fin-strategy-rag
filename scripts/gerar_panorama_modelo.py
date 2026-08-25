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

from src.modelo.construir_painel import (  # noqa: E402
    COLUNAS_FEATURES,
    construir_painel,
    construir_painel_para_inferencia,
)
from src.modelo.treinar import (  # noqa: E402
    avaliar,
    construir_gradient_boosting,
    dividir_walk_forward,
)

#: Faixas de porte do regime de risco, aplicadas ao PAINEL INTEIRO.
#:
#: Os cortes vieram de uma leitura descritiva de 2026-08-24 que parecia mostrar
#: porte funcionando como interruptor em instituição financeira — leitura
#: RETRATADA em 2026-08-25 (ver `_regime_por_porte`). Os cortes em si continuam
#: úteis e a tabela do painel inteiro se sustenta com amostra em cada faixa:
#: 6,1% (≥R$500bi, n=231) · 21,9% (100–500bi, n=506) · 21,8% (10–100bi,
#: n=5.365) · 37,4% (<R$10bi, n=16.760).
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
    """Taxa histórica de prejuízo por faixa de porte — PAINEL INTEIRO.

    **Sem recorte setorial, e isso é retratação (2026-08-25).** A primeira
    versão separava "instituição financeira" das demais e publicava um
    gradiente de 0,6% a 29,6% para as financeiras. A flag de origem significa
    "usa plano de contas de instituição financeira": 42 dos 49 eventos
    positivos do recorte (85,7%) vinham de GP Investments, Sul 116 (em
    liquidação), CELGPAR, PPLA e mais cinco. Limpo o universo sobram 7
    positivos — abaixo do mínimo de 20 do próprio módulo — e o teste contínuo
    mata o efeito (ρ = −0,046, p = 0,83 entre bancos de verdade fora do topo).
    Reproduzível: `python -m scripts.auditar_recorte_is_banco`. Ver também
    `src/projecao.py::FaixaDePorte`.
    """
    caso = "CASE " + " ".join(
        f"WHEN i.ativo_total >= {limite} THEN '{rotulo}'"
        for rotulo, limite in FAIXAS
        if limite > 0
    ) + f" ELSE '{FAIXAS[-1][0]}' END"
    linhas = con.execute(
        f"""
        SELECT {caso} AS faixa,
               count(*) AS n,
               sum(CASE WHEN i.lucro_liquido_consolidado < 0 THEN 1 ELSE 0 END)
                   ::DOUBLE / count(*) AS taxa
        FROM indicadores i
        WHERE i.lucro_liquido_consolidado IS NOT NULL
          AND i.ativo_total IS NOT NULL
        GROUP BY 1
        """
    ).fetchall()
    ordem = {rotulo: indice for indice, (rotulo, _) in enumerate(FAIXAS)}
    limites = dict(FAIXAS)
    saida = [
        {
            "rotulo": faixa,
            "limite_inferior_reais": float(limites[faixa]),
            "n_observacoes": int(n),
            "taxa_prejuizo": float(taxa),
        }
        for faixa, n, taxa in linhas
    ]
    saida.sort(key=lambda item: ordem[item["rotulo"]])
    return saida


def _escorar_trimestre_corrente(
    con: duckdb.DuckDBPyConnection,
    painel,
    *,
    limiar_absoluto: float,
) -> tuple[dict[str, object] | None, dict[str, float]]:
    """Escora o último trimestre FECHADO — o que ainda não tem rótulo.

    **Sobre a fronteira temporal — a versão anterior desta docstring afirmava
    demais.** Ela dizia que "todo rótulo que existe está estritamente no
    passado do trimestre escorado". É falso: com `TRIMESTRES_CONSECUTIVOS = 2`
    a última linha rotulada é `3T2025`, e o rótulo dela é definido pelos
    desfechos de `4T2025` **e `1T2026`** — o próprio trimestre escorado. O
    modelo vê, sim, informação de `1T2026` pela via do rótulo.

    Isso **não é vazamento**, e a razão é outra: no instante da escoragem
    `1T2026` já fechou e é público, então é exatamente a informação que um
    usuário teria em produção. Mais: as companhias escoradas têm
    `prejuizo_em_t = 0`, que é o próprio critério de inclusão — o rótulo de
    `3T2025` delas só confirma o que o filtro já sabe. O alvo real da
    escoragem (`2T2026`/`3T2026`) não existe em lugar nenhum do treino.

    A distinção importa para quem for mexer na janela: a garantia não vem de
    "nenhum rótulo toca o trimestre escorado", vem de "o trimestre escorado já
    é passado realizado quando o escore é calculado".

    Devolve `(agregado_publicavel, escores_por_cd_cvm)`. O primeiro entra no
    `panorama.json` versionado; o segundo só é gravado com `--com-escores` e
    fica fora do Git (RN07, §3.6).
    """
    colunas = list(COLUNAS_FEATURES)
    try:
        inferencia = construir_painel_para_inferencia(
            con, trimestres_consecutivos=TRIMESTRES_CONSECUTIVOS
        )
    except ValueError as erro:
        # Painel curto ou já rotulado até o fim: o bloco some, o resto fica.
        print(f"  trimestre corrente não escorado: {erro}")
        return None, {}

    modelo = construir_gradient_boosting()
    modelo.fit(painel.quadro[colunas], painel.quadro["rotulo"].to_numpy(int))
    escores = modelo.predict_proba(inferencia.quadro[colunas])[:, 1]

    agregado = {
        "trimestre": inferencia.trimestre,
        "n_hoje_lucrativas": int(inferencia.n_companhias),
        "n_ja_em_prejuizo": int(inferencia.n_descartadas_por_ja_estar_em_prejuizo),
        "n_acima_do_limiar": int((escores >= limiar_absoluto).sum()),
        "limiar": float(limiar_absoluto),
    }
    por_companhia = {
        str(cd): float(valor)
        for cd, valor in zip(inferencia.quadro["cd_cvm"], escores)
    }
    return agregado, por_companhia


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
        bloco_corrente, escores_corrente = _escorar_trimestre_corrente(
            con, painel, limiar_absoluto=limiar
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
            "trimestre_corrente": bloco_corrente,
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

        if bloco_corrente is not None:
            print(
                f"  trimestre corrente {bloco_corrente['trimestre']}: "
                f"{bloco_corrente['n_acima_do_limiar']}/"
                f"{bloco_corrente['n_hoje_lucrativas']} hoje lucrativas acima "
                f"do limiar ({bloco_corrente['n_ja_em_prejuizo']} já em "
                "prejuízo, fora da contagem)"
            )

        if argumentos.com_escores:
            # Prefere o trimestre CORRENTE: é o único escore que ainda é
            # previsão. O do último fold é retrospectivo — o resultado dele já
            # aconteceu, e entregá-lo ao analista como "o escore da companhia"
            # seria vender leitura de arquivo como projeção.
            if escores_corrente:
                por_companhia = escores_corrente
                trimestre_escores = bloco_corrente["trimestre"]
                natureza = "prospectivo (rótulo ainda não existe)"
            else:
                por_companhia = {
                    str(cd): float(valor)
                    for cd, valor in zip(quadro["cd_cvm"], quadro["escore"])
                }
                trimestre_escores = ultimo.trimestre_teste
                natureza = "retrospectivo (rótulo já conhecido)"
            argumentos.saida_escores.write_text(
                json.dumps(
                    {
                        "trimestre_referencia": trimestre_escores,
                        "natureza": natureza,
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
                f"({len(por_companhia)} companhias, {trimestre_escores}, "
                f"{natureza}) — FORA DO GIT"
            )
    finally:
        con.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(principal())
