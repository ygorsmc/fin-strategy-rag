from __future__ import annotations

import inspect

import pandas as pd

from scripts import auditar_cand04_previsao_fundamentos as cand04
from src.normalizacao import ordinal_trimestre


def _base(n: int = 12) -> pd.DataFrame:
    trimestres = [
        f"{((indice - 1) % 4) + 1}T{2020 + ((indice - 1) // 4)}"
        for indice in range(1, n + 1)
    ]
    quadro = pd.DataFrame(
        {
            "cd_cvm": ["000001"] * n,
            "trimestre": trimestres,
            "lucro": [float(indice * 10) for indice in range(1, n + 1)],
            "ativo": [100.0] * n,
            "origem": ["arquivado"] * n,
            "instituicao_financeira": [False] * n,
            "setor": ["teste"] * n,
        }
    )
    quadro["ordem"] = quadro["trimestre"].map(ordinal_trimestre)
    return quadro


def test_target_usa_ativo_de_t_e_nao_ativo_futuro():
    base = _base()
    base.loc[base["trimestre"] == "4T2021", "ativo"] = 1_000.0

    teste, _ = cand04.construir_quadro_baselines(
        base,
        n_trimestres_teste=5,
        min_historico=3,
    )
    linha = teste[teste["trimestre"] == "3T2021"].iloc[0]

    assert linha["trimestre"] == "3T2021"
    assert linha["trimestre_target"] == "4T2021"
    assert linha["ativo"] == 100.0
    assert linha["ativo_target"] == 1_000.0
    assert linha["y_target_bp"] == 8_000.0


def test_baseline_sazonal_e_exatamente_t_menos_3():
    base = _base()

    teste, _ = cand04.construir_quadro_baselines(
        base,
        n_trimestres_teste=1,
        min_historico=3,
    )
    linha = teste.iloc[0]

    assert linha["trimestre"] == "3T2022"
    assert linha["b1_sazonal"] == 80.0 / 100.0 * 10_000.0


def test_quarter_ausente_nao_casa_com_proxima_linha():
    base = _base()
    ordem_sem_target = ordinal_trimestre("3T2021")
    base = base[base["ordem"] != ordem_sem_target].copy()

    teste, _ = cand04.construir_quadro_baselines(
        base,
        n_trimestres_teste=1,
        min_historico=3,
    )

    assert not (
        (teste["trimestre"] == "2T2021")
        & (teste["trimestre_target"] == "4T2021")
    ).any()


def test_persistencia_abstem_de_direcao_em_vez_de_errar_todas():
    quadro = pd.DataFrame(
        {
            "cd_cvm": ["1", "2"],
            "trimestre_target": ["1T2025", "1T2025"],
            "y_target_bp": [200.0, 50.0],
            "y_atual_bp": [100.0, 100.0],
            "b0_persistencia": [100.0, 100.0],
        }
    )

    metricas = cand04._metricas_baseline(quadro, "b0_persistencia")

    assert metricas["cobertura_direcao"] == 0.0
    assert metricas["n_direcao_emitida"] == 0
    assert metricas["acerto_direcao"] is None


def test_diagnostico_falha_fechado_para_salto_de_ativo_1000x():
    quadro = pd.DataFrame(
        {
            "cd_cvm": ["1", "2"],
            "trimestre_target": ["4T2025", "4T2025"],
            "origem_target": ["derivado", "derivado"],
            "ativo": [100.0, 100.0],
            "ativo_target": [100_000.0, 110.0],
            "y_target_bp": [50_000.0, 100.0],
            "y_atual_bp": [100.0, 100.0],
            "b0_persistencia": [100.0, 100.0],
            "b1_sazonal": [100.0, 100.0],
            "b2_mediana_4t": [100.0, 100.0],
            "b3_combinado": [100.0, 100.0],
            "instituicao_financeira": [False, False],
            "setor": ["a", "b"],
        }
    )

    diagnostico = cand04._diagnosticos(quadro, "b3_combinado")
    escala = diagnostico["descontinuidade_ativo_t_mais_1_sobre_t"]

    assert escala["n"] == 1
    assert escala["companhias"] == 1
    assert escala["fracao_erro_absoluto"] > 0.99


def test_auditor_nao_importa_biblioteca_ou_modulo_de_modelo():
    fonte = inspect.getsource(cand04)
    for proibido in (
        "sklearn",
        "torch",
        "sentence_transformers",
        "src.modelo",
        "RandomForest",
        "LightGBM",
    ):
        assert proibido not in fonte
