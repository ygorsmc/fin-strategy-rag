"""Reproduz a retratação do recorte setorial `is_banco` (2026-08-25).

**Por que este script existe.** O relatório de robustez de 2026-08-24 publicou
"instituições financeiras: AUC 0,883, lift 5,10" com artefato versionado
(`artefatos/modelo/robustez.json`). O debate de 2026-08-25 derrubou o número —
mas só em prosa. Uma medição com artefato anulada por medição sem artefato é
exatamente a assimetria que o §4.2 do plano proíbe, e foi achado de auditoria.

O que ele mede, tudo a partir do painel de treino local (custo zero):

1. Quantas entidades marcadas `is_banco` não são banco, e quantos dos eventos
   positivos do recorte vêm delas.
2. O gradiente de prejuízo por faixa de porte no universo marcado, e o que
   sobra dele depois de limpo.
3. A correlação de Spearman entre porte e prejuízo entre os bancos de verdade,
   fora da faixa do topo — o teste contínuo que mata o "interruptor do porte".
4. Quantos eventos positivos sobram no universo limpo, contra o mínimo de 20
   que o próprio relatório de robustez estabelece.

    python -m scripts.auditar_recorte_is_banco --painel artefatos/cvm_treino.duckdb

`is_banco` é derivado da presença de Receitas de Intermediação Financeira, não
de uma lista de nomes — o que é a decisão certa para 741 companhias sem fonte
externa. A lista abaixo NÃO é a definição da flag: é a enumeração manual e
auditável das entidades marcadas que, por leitura da denominação social, não
são instituição bancária. Está aqui em código para que a retratação seja
conferível linha a linha em vez de acreditada.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

#: Entidades marcadas `is_banco` que não são banco, com o motivo declarado.
#: Conferidas uma a uma contra a denominação social em 2026-08-25.
NAO_SAO_BANCO: dict[str, str] = {
    "080020": "GP INVESTMENTS — private equity",
    "080152": "PPLA PARTICIPATIONS — veículo de participações",
    "016438": "SUL 116 PARTICIPAÇÕES — em liquidação",
    "021393": "CELGPAR — holding de participações do setor elétrico",
    "017922": "BRAZILIAN FINANCE E REAL ESTATE — crédito imobiliário",
    "021512": "ÁQUILLA SECURITIZADORA — securitizadora",
    "022950": "AR CAPITAL SECURITIES — securitizadora",
    "026417": "OLIVEIRA TRUST — agente fiduciário",
    "019402": "GLOBAL BRASIL — participações",
}

#: Mesmo mínimo que `desempenho_por_recorte` aplica em `src/modelo/treinar.py`.
MINIMO_POSITIVOS = 20


def _spearman(x: list[float], y: list[float]) -> tuple[float | None, float | None]:
    try:
        from scipy import stats
    except Exception:  # pragma: no cover - ambiente sem scipy
        return None, None
    if len(x) < 3:
        return None, None
    resultado = stats.spearmanr(x, y)
    return float(resultado.statistic), float(resultado.pvalue)


def auditar(con: duckdb.DuckDBPyConnection) -> dict[str, object]:
    """Mede sobre o MESMO recorte que o relatório de 2026-08-24 publicou.

    O denominador importa e a primeira versão deste script errou o dele: media
    sobre todas as linhas de `indicadores`, e não sobre o painel supervisionado
    com alvo de 2 trimestres — que é o que a linha "instituições financeiras:
    n=535, positivos=35" do relatório usava. Números de denominadores
    diferentes não retratam nada; só somam confusão.
    """
    from src.modelo.construir_painel import construir_painel

    marcadas = con.execute(
        "SELECT cd_cvm, denom_social FROM companhias WHERE is_banco ORDER BY 2"
    ).fetchall()
    codigos = {str(cd) for cd, _ in marcadas}
    intrusas = {cd for cd in NAO_SAO_BANCO if cd in codigos}
    faltando = set(NAO_SAO_BANCO) - codigos

    painel = construir_painel(con, trimestres_consecutivos=2)
    quadro = painel.quadro
    recorte = quadro[quadro["instituicao_financeira"] == 1].copy()
    recorte["cd_cvm"] = recorte["cd_cvm"].astype(str)
    e_intrusa = recorte["cd_cvm"].isin(intrusas)

    positivos_total = int(recorte["rotulo"].sum())
    positivos_intrusas = int(recorte.loc[e_intrusa, "rotulo"].sum())
    limpo = recorte[~e_intrusa]
    positivos_limpos = int(limpo["rotulo"].sum())

    # Teste contínuo, fora da faixa do topo: é onde o "interruptor" morre.
    por_companhia = (
        limpo[limpo["log_ativo_total"] < 11.7]  # ~R$ 500 bi em log10
        .groupby("cd_cvm")
        .agg(ativo=("log_ativo_total", "mean"), taxa=("rotulo", "mean"))
    )
    rho, p = _spearman(
        por_companhia["ativo"].tolist(), por_companhia["taxa"].tolist()
    )

    atinge_minimo = positivos_limpos >= MINIMO_POSITIVOS
    fracao_intrusa = (
        positivos_intrusas / positivos_total if positivos_total else None
    )
    # Veredito CALCULADO. A primeira versão trazia a conclusão escrita à mão e
    # ela contradizia os próprios números que o script imprimia — o defeito
    # exato que este projeto existe para não cometer.
    partes = []
    if fracao_intrusa is not None and fracao_intrusa >= 0.5:
        partes.append(
            f"{positivos_intrusas} dos {positivos_total} eventos positivos "
            f"({fracao_intrusa:.1%}) vêm de entidades que não são banco"
        )
    if not atinge_minimo:
        partes.append(
            f"o universo limpo tem {positivos_limpos} positivos, abaixo do "
            f"mínimo de {MINIMO_POSITIVOS} que o próprio módulo exige"
        )
    if rho is not None and p is not None and p > 0.05:
        partes.append(
            f"e entre os bancos de verdade fora do topo o porte não se "
            f"correlaciona com prejuízo (ρ = {rho:+.3f}, p = {p:.2f})"
        )
    veredito = (
        "O recorte setorial NÃO se sustenta: " + "; ".join(partes) + "."
        if partes
        else "Nenhuma das condições de retratação se verifica nesta execução."
    )

    return {
        "recorte": "painel supervisionado, alvo de 2 trimestres (mesmo do relatório de 2026-08-24)",
        "n_entidades_marcadas": len(marcadas),
        "n_marcadas_que_nao_sao_banco": len(intrusas),
        "codigos_nao_banco_ausentes_do_painel": sorted(faltando),
        "n_observacoes_no_recorte": int(len(recorte)),
        "eventos_positivos_no_recorte_marcado": positivos_total,
        "eventos_positivos_vindos_de_nao_bancos": positivos_intrusas,
        "fracao_dos_eventos_vinda_de_nao_bancos": fracao_intrusa,
        "eventos_positivos_no_universo_limpo": positivos_limpos,
        "minimo_de_positivos_exigido": MINIMO_POSITIVOS,
        "universo_limpo_atinge_o_minimo": atinge_minimo,
        "spearman_porte_x_prejuizo_fora_do_topo": {
            "n_companhias": int(len(por_companhia)),
            "rho": rho,
            "p": p,
        },
        "veredito": veredito,
    }


def principal() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--painel", type=Path, default=Path("artefatos/cvm_treino.duckdb")
    )
    analisador.add_argument(
        "--saida", type=Path, default=Path("artefatos/modelo/auditoria_is_banco.json")
    )
    argumentos = analisador.parse_args()

    con = duckdb.connect(str(argumentos.painel), read_only=True)
    try:
        resultado = auditar(con)
    finally:
        con.close()

    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    argumentos.saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    print(f"\n→ {argumentos.saida}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(principal())
