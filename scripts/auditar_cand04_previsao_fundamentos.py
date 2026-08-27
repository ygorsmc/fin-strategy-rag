"""Calcula o alvo e os baselines do CAND-04 antes de qualquer modelo.

O auditor prevê ROA trimestral de T+1 sobre o ativo conhecido em T. Ele mede
persistência, sazonalidade e mediana móvel no mesmo universo, mas falha fechado
para confirmação porque o painel atual não preserva `DT_RECEB` nem vintages.

Uso::

    python -m scripts.auditar_cand04_previsao_fundamentos
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from src.normalizacao import ordinal_trimestre

CANDIDATO = "CAND-04 — previsão interpretável de fundamentos"
PRE_REGISTRO = Path(
    "resultados/pre_registro_cand04_previsao_fundamentos_2026-08-27.md"
)
PAINEL = Path("artefatos/cvm_treino.duckdb")
DIR_CVM_BRUTO = Path("corpus/cvm")
SAIDA = Path("artefatos/cand04/auditoria_baselines.json")
BASELINES = ("b0_persistencia", "b1_sazonal", "b2_mediana_4t", "b3_combinado")


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _trimestres_completos(
    con: duckdb.DuckDBPyConnection, fracao_minima: float = 0.5
) -> tuple[list[str], dict[str, int]]:
    linhas = con.execute(
        "SELECT trimestre, count(*) AS n FROM indicadores GROUP BY 1"
    ).fetchall()
    contagens = {str(trimestre): int(n) for trimestre, n in linhas}
    if not contagens:
        return [], {}
    mediana = float(np.median(list(contagens.values())))
    limite = mediana * fracao_minima
    completos = sorted(
        [trimestre for trimestre, n in contagens.items() if n >= limite],
        key=ordinal_trimestre,
    )
    descartados = {
        trimestre: n for trimestre, n in contagens.items() if n < limite
    }
    return completos, descartados


def _carregar_base(
    con: duckdb.DuckDBPyConnection,
) -> tuple[pd.DataFrame, list[str], dict[str, int], dict[str, Any]]:
    completos, descartados = _trimestres_completos(con)
    if not completos:
        raise ValueError("painel sem trimestre completo")
    placeholders = ",".join("?" for _ in completos)
    quadro = con.execute(
        f"""
        SELECT
            i.cd_cvm,
            i.trimestre,
            i.lucro_liquido_consolidado AS lucro,
            i.ativo_total AS ativo,
            i.origem,
            coalesce(c.is_banco, false) AS instituicao_financeira,
            c.setor
        FROM indicadores AS i
        LEFT JOIN companhias AS c USING (cd_cvm)
        WHERE i.trimestre IN ({placeholders})
          AND i.lucro_liquido_consolidado IS NOT NULL
          AND i.ativo_total IS NOT NULL
        ORDER BY i.cd_cvm, i.trimestre
        """,
        completos,
    ).df()
    quadro["ordem"] = quadro["trimestre"].map(ordinal_trimestre).astype(int)
    duplicadas = int(quadro.duplicated(["cd_cvm", "ordem"]).sum())
    if duplicadas:
        raise ValueError(
            f"{duplicadas} duplicidades em companhia × trimestre nos indicadores"
        )
    colunas_fatos = {
        str(linha[0]).lower()
        for linha in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'fatos_contabeis'
            """
        ).fetchall()
    }
    n_setor, n_cias = con.execute(
        "SELECT count(setor), count(*) FROM companhias"
    ).fetchone()
    procedencia = {
        "tem_dt_receb_no_painel": "dt_receb" in colunas_fatos,
        "companhias_com_setor": int(n_setor),
        "companhias": int(n_cias),
        "fracao_companhias_com_setor": float(n_setor / n_cias) if n_cias else 0.0,
    }
    return quadro, completos, descartados, procedencia


def _anexar_defasagem(
    atual: pd.DataFrame,
    base: pd.DataFrame,
    *,
    deslocamento: int,
    nome: str,
) -> pd.DataFrame:
    fonte = base[["cd_cvm", "ordem", "lucro"]].copy()
    # Para casar com T, a linha da fonte em T-deslocamento recebe chave T.
    fonte["ordem"] = fonte["ordem"] + deslocamento
    fonte = fonte.rename(columns={"lucro": nome})
    return atual.merge(fonte, on=["cd_cvm", "ordem"], how="left", validate="1:1")


def construir_quadro_baselines(
    base: pd.DataFrame,
    *,
    n_trimestres_teste: int = 8,
    min_historico: int = 8,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Constrói target e B0–B3 com junções explícitas por ordinal."""
    atual = base.copy()
    futuro = base[
        ["cd_cvm", "ordem", "trimestre", "lucro", "ativo", "origem"]
    ].copy()
    futuro["ordem"] = futuro["ordem"] - 1
    futuro = futuro.rename(
        columns={
            "trimestre": "trimestre_target",
            "lucro": "lucro_target",
            "ativo": "ativo_target",
            "origem": "origem_target",
        }
    )
    atual = atual.merge(
        futuro, on=["cd_cvm", "ordem"], how="left", validate="1:1"
    )
    for deslocamento in range(1, max(min_historico, 3) + 1):
        atual = _anexar_defasagem(
            atual,
            base,
            deslocamento=deslocamento,
            nome=f"lucro_t_menos_{deslocamento}",
        )

    atual = atual[
        (atual["ativo"] > 0)
        & np.isfinite(atual["ativo"])
        & np.isfinite(atual["lucro"])
        & np.isfinite(atual["lucro_target"])
    ].copy()
    colunas_historico = [
        f"lucro_t_menos_{deslocamento}"
        for deslocamento in range(1, min_historico + 1)
    ]
    universo_com_target = len(atual)
    atual = atual.dropna(subset=colunas_historico)
    universo_com_historico = len(atual)

    escala = 10_000.0 / atual["ativo"]
    atual["y_target_bp"] = atual["lucro_target"] * escala
    atual["y_atual_bp"] = atual["lucro"] * escala
    atual["b0_persistencia"] = atual["lucro"] * escala
    atual["b1_sazonal"] = atual["lucro_t_menos_3"] * escala
    quatro = atual[
        [
            "lucro",
            "lucro_t_menos_1",
            "lucro_t_menos_2",
            "lucro_t_menos_3",
        ]
    ]
    atual["b2_mediana_4t"] = quatro.median(axis=1) * escala
    atual["b3_combinado"] = atual[
        ["b0_persistencia", "b1_sazonal", "b2_mediana_4t"]
    ].median(axis=1)

    ordens_target = sorted(
        atual["trimestre_target"].map(ordinal_trimestre).dropna().unique()
    )
    if len(ordens_target) < n_trimestres_teste:
        raise ValueError(
            f"apenas {len(ordens_target)} targets; teste pede {n_trimestres_teste}"
        )
    ordens_teste = set(ordens_target[-n_trimestres_teste:])
    atual["ordem_target"] = atual["trimestre_target"].map(ordinal_trimestre)
    teste = atual[atual["ordem_target"].isin(ordens_teste)].copy()
    metadados = {
        "universo_com_target": universo_com_target,
        "universo_com_historico_consecutivo": universo_com_historico,
        "n_trimestres_teste": n_trimestres_teste,
        "ordens_target_teste": sorted(int(valor) for valor in ordens_teste),
        "trimestres_target_teste": sorted(
            teste["trimestre_target"].unique(), key=ordinal_trimestre
        ),
    }
    return teste, metadados


def _correlacao(a: pd.Series, b: pd.Series) -> float | None:
    if len(a) < 2 or a.nunique() < 2 or b.nunique() < 2:
        return None
    valor = float(a.corr(b))
    return valor if math.isfinite(valor) else None


def _metricas_baseline(
    quadro: pd.DataFrame, coluna: str
) -> dict[str, Any]:
    erro = quadro[coluna] - quadro["y_target_bp"]
    absoluto = erro.abs()
    por_companhia = absoluto.groupby(quadro["cd_cvm"]).mean()
    direcao_real = np.sign(quadro["y_target_bp"] - quadro["y_atual_bp"])
    direcao_prevista = np.sign(quadro[coluna] - quadro["y_atual_bp"])
    mascara_direcao_real = direcao_real != 0
    mascara_direcao_emitida = mascara_direcao_real & (direcao_prevista != 0)

    alvo_intra = quadro["y_target_bp"] - quadro.groupby("cd_cvm")[
        "y_target_bp"
    ].transform("mean")
    previsto_intra = quadro[coluna] - quadro.groupby("cd_cvm")[coluna].transform(
        "mean"
    )
    por_fold = []
    for trimestre, bloco in quadro.groupby("trimestre_target", sort=False):
        erro_fold = (bloco[coluna] - bloco["y_target_bp"]).abs()
        macro_fold = erro_fold.groupby(bloco["cd_cvm"]).mean().mean()
        por_fold.append(
            {
                "trimestre_target": str(trimestre),
                "n": len(bloco),
                "companhias": int(bloco["cd_cvm"].nunique()),
                "mae_macro_bp": float(macro_fold),
            }
        )
    return {
        "n": len(quadro),
        "companhias": int(quadro["cd_cvm"].nunique()),
        "mae_macro_companhia_bp": float(por_companhia.mean()),
        "mae_micro_bp": float(absoluto.mean()),
        "mediana_erro_absoluto_bp": float(absoluto.median()),
        "rmse_bp": float(np.sqrt(np.mean(np.square(erro)))),
        "vies_assinado_bp": float(erro.mean()),
        "cobertura_direcao": (
            float(mascara_direcao_emitida.sum() / mascara_direcao_real.sum())
            if mascara_direcao_real.any()
            else None
        ),
        "n_direcao_emitida": int(mascara_direcao_emitida.sum()),
        "acerto_direcao": (
            float(
                (
                    direcao_real[mascara_direcao_emitida]
                    == direcao_prevista[mascara_direcao_emitida]
                ).mean()
            )
            if mascara_direcao_emitida.any()
            else None
        ),
        "correlacao_agregada": _correlacao(
            quadro[coluna], quadro["y_target_bp"]
        ),
        "correlacao_intra_companhia": _correlacao(
            previsto_intra, alvo_intra
        ),
        "por_fold": sorted(
            por_fold, key=lambda item: ordinal_trimestre(item["trimestre_target"])
        ),
    }


def _resumo_sensibilidade(
    quadro: pd.DataFrame,
) -> dict[str, dict[str, float | int | None]]:
    resumo = {}
    for baseline in BASELINES:
        metricas = _metricas_baseline(quadro, baseline)
        resumo[baseline] = {
            "n": metricas["n"],
            "mae_macro_companhia_bp": metricas["mae_macro_companhia_bp"],
            "mae_micro_bp": metricas["mae_micro_bp"],
            "mediana_erro_absoluto_bp": metricas[
                "mediana_erro_absoluto_bp"
            ],
            "correlacao_intra_companhia": metricas[
                "correlacao_intra_companhia"
            ],
        }
    return resumo


def _diagnosticos(quadro: pd.DataFrame, melhor_baseline: str) -> dict[str, Any]:
    quantis = quadro["y_target_bp"].quantile(
        [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    )
    erro_absoluto = (
        quadro[melhor_baseline] - quadro["y_target_bp"]
    ).abs()
    erro_total = float(erro_absoluto.sum())
    razao_ativo = quadro["ativo_target"] / quadro["ativo"]
    descontinuidade_ativo = (
        ~np.isfinite(razao_ativo)
        | (razao_ativo <= 0)
        | (razao_ativo < 0.01)
        | (razao_ativo > 100.0)
    )
    target_extremo = quadro["y_target_bp"].abs() > 10_000.0

    cauda = {}
    for nome, fracao in {
        "top_10pct": 0.10,
        "top_5pct": 0.05,
        "top_1pct": 0.01,
        "top_0_5pct": 0.005,
    }.items():
        n_cauda = max(1, math.ceil(len(quadro) * fracao))
        soma_cauda = float(erro_absoluto.nlargest(n_cauda).sum())
        cauda[nome] = {
            "n": n_cauda,
            "fracao_erro_absoluto": (
                soma_cauda / erro_total if erro_total else None
            ),
        }

    por_trimestre = {}
    for trimestre, bloco in quadro.groupby("trimestre_target", sort=False):
        erro = (
            bloco[melhor_baseline] - bloco["y_target_bp"]
        ).abs()
        por_trimestre[str(trimestre)] = {
            "n": len(bloco),
            "mae_bp": float(erro.mean()),
            "mediana_erro_absoluto_bp": float(erro.median()),
            "target_abs_max_bp": float(bloco["y_target_bp"].abs().max()),
        }

    por_origem_target = {}
    for origem, bloco in quadro.groupby("origem_target", dropna=False):
        erro = (
            bloco[melhor_baseline] - bloco["y_target_bp"]
        ).abs()
        por_origem_target[str(origem)] = {
            "n": len(bloco),
            "mae_bp": float(erro.mean()),
            "mediana_erro_absoluto_bp": float(erro.median()),
        }

    quintil = pd.qcut(
        quadro["ativo"].rank(method="first"),
        q=5,
        labels=False,
    )
    por_quintil_ativo = {}
    for indice in range(5):
        bloco = quadro[quintil == indice]
        erro = (
            bloco[melhor_baseline] - bloco["y_target_bp"]
        ).abs()
        por_quintil_ativo[str(indice + 1)] = {
            "n": len(bloco),
            "ativo_min": float(bloco["ativo"].min()),
            "ativo_max": float(bloco["ativo"].max()),
            "mae_bp": float(erro.mean()),
            "mediana_erro_absoluto_bp": float(erro.median()),
        }

    erro_por_companhia = erro_absoluto.groupby(quadro["cd_cvm"]).sum()
    maiores_companhias = []
    for cd_cvm, soma in erro_por_companhia.nlargest(10).items():
        maiores_companhias.append(
            {
                "cd_cvm": str(cd_cvm),
                "erro_absoluto_soma_bp": float(soma),
                "fracao_erro_absoluto": (
                    float(soma / erro_total) if erro_total else None
                ),
            }
        )

    por_regime = {}
    for nome, mascara in {
        "lucro": quadro["y_target_bp"] >= 0,
        "prejuizo": quadro["y_target_bp"] < 0,
        "instituicao_financeira": quadro["instituicao_financeira"].astype(bool),
        "nao_financeira": ~quadro["instituicao_financeira"].astype(bool),
    }.items():
        bloco = quadro[mascara]
        por_regime[nome] = {
            "n": len(bloco),
            "companhias": int(bloco["cd_cvm"].nunique()),
            "target_mediana_bp": (
                float(bloco["y_target_bp"].median()) if len(bloco) else None
            ),
        }
    return {
        "target_bp_quantis": {
            str(indice): float(valor) for indice, valor in quantis.items()
        },
        "melhor_baseline_auditado": melhor_baseline,
        "concentracao_erro_absoluto": cauda,
        "descontinuidade_ativo_t_mais_1_sobre_t": {
            "criterio": (
                "ativo_T_mais_1_sobre_ativo_T fora de [0.01, 100] ou nao "
                "positivo/finito; usa ativo futuro apenas como auditoria, "
                "nunca como feature ou denominador do alvo"
            ),
            "n": int(descontinuidade_ativo.sum()),
            "fracao_linhas": float(descontinuidade_ativo.mean()),
            "companhias": int(
                quadro.loc[descontinuidade_ativo, "cd_cvm"].nunique()
            ),
            "fracao_erro_absoluto": (
                float(erro_absoluto[descontinuidade_ativo].sum() / erro_total)
                if erro_total
                else None
            ),
        },
        "target_abs_maior_10000_bp": {
            "n": int(target_extremo.sum()),
            "fracao_linhas": float(target_extremo.mean()),
            "fracao_erro_absoluto": (
                float(erro_absoluto[target_extremo].sum() / erro_total)
                if erro_total
                else None
            ),
        },
        "por_trimestre_target": por_trimestre,
        "por_origem_target": por_origem_target,
        "por_quintil_ativo_t": por_quintil_ativo,
        "companhias_com_maior_erro_absoluto": maiores_companhias,
        "sensibilidade_sem_descontinuidade_ativo_100x": {
            "uso": "diagnostico_pos_resultado; nao substitui o teste congelado",
            "linhas_removidas": int(descontinuidade_ativo.sum()),
            "baselines": _resumo_sensibilidade(
                quadro.loc[~descontinuidade_ativo]
            ),
        },
        "por_regime": por_regime,
        "setor_preenchido_nas_linhas": int(quadro["setor"].notna().sum()),
        "setor_preenchido_fracao": float(quadro["setor"].notna().mean()),
    }


def _fonte_bruta_tem_dt_receb(diretorio: Path) -> bool:
    pacotes = sorted(diretorio.glob("*_cia_aberta_*.zip"))
    if not pacotes:
        return False
    for pacote in pacotes:
        tipo = pacote.stem.split("_")[0]
        ano = pacote.stem.split("_")[-1]
        geral = f"{tipo}_cia_aberta_{ano}.csv"
        with zipfile.ZipFile(pacote) as arquivo:
            if geral not in arquivo.namelist():
                return False
            with arquivo.open(geral) as fluxo:
                cabecalho = fluxo.readline().decode("latin-1").strip().split(";")
            if "DT_RECEB" not in cabecalho:
                return False
    return True


def auditar(
    painel: Path = PAINEL,
    *,
    dir_cvm_bruto: Path = DIR_CVM_BRUTO,
    n_trimestres_teste: int = 8,
    min_historico: int = 8,
) -> dict[str, Any]:
    if not PRE_REGISTRO.is_file():
        raise FileNotFoundError(PRE_REGISTRO)
    if not painel.is_file():
        raise FileNotFoundError(painel)
    with duckdb.connect(str(painel), read_only=True) as con:
        base, completos, descartados, procedencia = _carregar_base(con)
    teste, metadados = construir_quadro_baselines(
        base,
        n_trimestres_teste=n_trimestres_teste,
        min_historico=min_historico,
    )
    metricas = {
        baseline: _metricas_baseline(teste, baseline)
        for baseline in BASELINES
    }
    melhor = min(
        BASELINES,
        key=lambda nome: metricas[nome]["mae_macro_companhia_bp"],
    )
    diagnosticos = _diagnosticos(teste, melhor)
    cobertura_b1 = float(teste["b1_sazonal"].notna().mean()) if len(teste) else 0.0
    gate_g0_amostra = (
        len(teste) >= 500
        and teste["cd_cvm"].nunique() >= 100
        and cobertura_b1 >= 0.80
    )
    gate_g0_integridade_escala = (
        diagnosticos["descontinuidade_ativo_t_mais_1_sobre_t"]["n"] == 0
    )
    gate_g0 = gate_g0_amostra and gate_g0_integridade_escala
    fonte_tem_dt_receb = _fonte_bruta_tem_dt_receb(dir_cvm_bruto)
    gate_g1 = bool(procedencia["tem_dt_receb_no_painel"])
    gate_g2 = all(metricas[nome]["n"] == len(teste) for nome in BASELINES)

    razoes = []
    if not gate_g0_amostra:
        razoes.append("amostra_ou_cobertura_do_alvo_insuficiente")
    if not gate_g0_integridade_escala:
        razoes.append("alvo_contaminado_por_descontinuidade_de_escala")
    if not gate_g1:
        razoes.append("painel_sem_dt_receb_e_vintages_numericos")
    if procedencia["fracao_companhias_com_setor"] < 0.95:
        razoes.append("setor_insuficiente_para_heterogeneidade")
    razoes.extend(
        [
            "intervalos_ainda_nao_calibrados",
            "limiar_de_erro_acionavel_nao_medido",
            "estudo_humano_de_utilidade_ausente",
        ]
    )
    return {
        "candidato": CANDIDATO,
        "pre_registro": {
            "arquivo": str(PRE_REGISTRO),
            "sha256": _sha256(PRE_REGISTRO),
        },
        "painel": {"arquivo": str(painel), "sha256": _sha256(painel)},
        "modelo_carregado": False,
        "alvo": {
            "formula": (
                "10000 * lucro_liquido_consolidado_T_mais_1 "
                "/ ativo_total_T"
            ),
            "unidade": "pontos_base_de_ativo_T",
            **metadados,
            "n_teste": len(teste),
            "companhias_teste": int(teste["cd_cvm"].nunique()),
            "cobertura_baseline_sazonal": cobertura_b1,
        },
        "trimestres_completos": completos,
        "trimestres_descartados": descartados,
        "procedencia": {
            **procedencia,
            "fonte_bruta_tem_dt_receb": fonte_tem_dt_receb,
        },
        "diagnosticos": diagnosticos,
        "baselines": metricas,
        "melhor_baseline_por_mae_macro": melhor,
        "gates": {
            "g0_alvo_e_amostra": gate_g0,
            "g0_amostra_e_cobertura": gate_g0_amostra,
            "g0_integridade_escala": gate_g0_integridade_escala,
            "g1_point_in_time": gate_g1,
            "g2_baselines_executados": gate_g2,
            "g3_intervalos": False,
            "g4_utilidade_humana": False,
        },
        "estado_cientifico_ml": "INDECIDIVEL",
        "decisao_de_engenharia_ml": "NAO_CARREGAR_MODELO_AGORA",
        "razoes": razoes,
        "nota": (
            "Os erros são diagnóstico as-restated. A sensibilidade não "
            "substitui o teste congelado. Falha de escala ou de point-in-time "
            "não autoriza comparação de ML."
        ),
    }


def principal() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--painel", type=Path, default=PAINEL)
    parser.add_argument("--dir-cvm-bruto", type=Path, default=DIR_CVM_BRUTO)
    parser.add_argument("--trimestres-teste", type=int, default=8)
    parser.add_argument("--min-historico", type=int, default=8)
    parser.add_argument("--saida", type=Path, default=SAIDA)
    args = parser.parse_args()
    resultado = auditar(
        args.painel,
        dir_cvm_bruto=args.dir_cvm_bruto,
        n_trimestres_teste=args.trimestres_teste,
        min_historico=args.min_historico,
    )
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
