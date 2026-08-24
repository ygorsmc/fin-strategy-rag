"""Contratos do modelo preditivo (spec 5.10) — inclusive o que ele se proíbe.

O teste mais importante deste arquivo não mede acurácia: é
`TestRN07::test_nenhum_modulo_do_caminho_interativo_importa_o_modelo`, que
falha se alguém ligar o preditor ao caminho que responde ao usuário.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import numpy as np
import pytest

from src.modelo import prever
from src.modelo.construir_painel import (
    COLUNAS_DESCARTADAS,
    COLUNAS_FEATURES,
    TrimestreInvalidoError,
    construir_painel,
    ordinal_trimestre,
    trimestres_completos,
)
from src.modelo.treinar import (
    avaliar,
    construir_gradient_boosting,
    construir_regressao_logistica,
    dividir_temporalmente,
    escolher_limiar_por_f2,
    escore_classe_majoritaria,
    escore_persistencia,
    treinar_e_avaliar,
)

CAMINHO_PAINEL = Path("artefatos/cvm.duckdb")


# --------------------------------------------------------------------------- #
# Fixtures sintéticas — não dependem do painel real
# --------------------------------------------------------------------------- #

_TRIMESTRES = ("1T2025", "2T2025", "3T2025", "4T2025", "1T2026")


def _con_sintetica(linhas: list[tuple]) -> duckdb.DuckDBPyConnection:
    """`indicadores` mínima em memória: (cd_cvm, trimestre, lucro, pl, ativo)."""
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE indicadores (
            cd_cvm VARCHAR, trimestre VARCHAR,
            lucro_liquido_consolidado DOUBLE,
            lucro_liquido_controladores DOUBLE,
            receita_intermediacao DOUBLE,
            patrimonio_liquido DOUBLE,
            ativo_total DOUBLE,
            roe_trimestral DOUBLE,
            margem_liquida DOUBLE,
            alavancagem DOUBLE,
            origem VARCHAR
        )
        """
    )
    for cd, tri, lucro, pl, ativo in linhas:
        con.execute(
            "INSERT INTO indicadores VALUES (?,?,?,?,NULL,?,?,?,NULL,?,'arquivado')",
            [cd, tri, lucro, lucro, pl, ativo, lucro / pl if pl else None,
             ativo / pl if pl else None],
        )
    return con


def _painel_cheio(lucros_por_companhia: dict[str, list[float]]):
    linhas = []
    for cd, lucros in lucros_por_companhia.items():
        for tri, lucro in zip(_TRIMESTRES, lucros):
            linhas.append((cd, tri, lucro, 1_000.0, 5_000.0))
    return _con_sintetica(linhas)


# --------------------------------------------------------------------------- #


class TestOrdinalTrimestre:
    def test_ordena_atravessando_a_virada_de_ano(self):
        """Ordenar como texto poria 1T2026 antes de 3T2025."""
        assert ordinal_trimestre("1T2026") > ordinal_trimestre("3T2025")
        assert "1T2026" < "3T2025"  # a armadilha que o ordinal existe para evitar

    def test_trimestres_consecutivos_diferem_de_um(self):
        assert ordinal_trimestre("2T2025") - ordinal_trimestre("1T2025") == 1
        assert ordinal_trimestre("1T2026") - ordinal_trimestre("4T2025") == 1

    @pytest.mark.parametrize("ruim", ["5T2025", "2025T1", "2T25", "", "T2025"])
    def test_formato_invalido_falha_explicito(self, ruim):
        with pytest.raises(TrimestreInvalidoError):
            ordinal_trimestre(ruim)


class TestTrimestresCompletos:
    def test_trimestre_parcial_fica_de_fora(self):
        """2T2026 real tem 128 companhias contra ~435 — e 17% de prejuízo."""
        linhas = [(f"{i:06d}", tri, 10.0, 100.0, 500.0)
                  for tri in ("1T2025", "2T2025") for i in range(100)]
        linhas += [("999999", "3T2025", 10.0, 100.0, 500.0)]  # trimestre ralo
        completos, descartados = trimestres_completos(_con_sintetica(linhas))
        assert completos == ("1T2025", "2T2025")
        assert descartados == {"3T2025": 1}

    def test_painel_sem_par_de_trimestres_falha(self):
        linhas = [("000001", "1T2025", 10.0, 100.0, 500.0)]
        with pytest.raises(ValueError, match="dois trimestres completos"):
            construir_painel(_con_sintetica(linhas))


class TestRotulo:
    def test_rotulo_e_o_sinal_do_lucro_em_t_mais_1(self):
        con = _painel_cheio({"000001": [5.0, 5.0, -3.0, 5.0, 5.0]})
        quadro = construir_painel(con).quadro.set_index("trimestre")
        # o prejuízo está em 3T2025 → rotula a linha de 2T2025
        assert quadro.loc["2T2025", "rotulo"] == 1
        assert quadro.loc["1T2025", "rotulo"] == 0
        assert quadro.loc["3T2025", "rotulo"] == 0

    def test_companhia_sem_t_mais_1_sai_do_painel(self):
        """Sem rótulo não há observação — nunca rotular por omissão."""
        linhas = [("000001", t, 5.0, 100.0, 500.0) for t in _TRIMESTRES]
        linhas += [("000002", t, 5.0, 100.0, 500.0) for t in ("1T2025", "2T2025")]
        # 000002 some depois de 2T2025: sua última linha rotulável é 1T2025
        quadro = construir_painel(_con_sintetica(linhas)).quadro
        do_dois = quadro[quadro["cd_cvm"] == "000002"]["trimestre"].tolist()
        assert do_dois == ["1T2025"]

    def test_rotulo_nao_pula_trimestre_ausente(self):
        """Buraco no meio não pode virar T+1 vindo de um trimestre distante."""
        linhas = [("000001", "1T2025", 5.0, 100.0, 500.0),
                  ("000001", "3T2025", -9.0, 100.0, 500.0),
                  ("000001", "4T2025", 5.0, 100.0, 500.0)]
        # 1T2025 não tem 2T2025 → não pode ser rotulado pelo prejuízo de 3T2025
        quadro = construir_painel(_con_sintetica(linhas), fracao_minima=0.1).quadro
        assert "1T2025" not in quadro["trimestre"].tolist()


class TestVazamentoTemporal:
    def test_features_nao_mudam_quando_o_futuro_muda(self):
        """A prova direta: só o rótulo pode reagir ao valor de T+1."""
        base = {"000001": [5.0, 5.0, 5.0, 5.0, 5.0]}
        futuro_ruim = {"000001": [5.0, 5.0, 5.0, 5.0, -999.0]}
        a = construir_painel(_painel_cheio(base)).quadro
        b = construir_painel(_painel_cheio(futuro_ruim)).quadro

        linha_a = a[a["trimestre"] == "4T2025"].iloc[0]
        linha_b = b[b["trimestre"] == "4T2025"].iloc[0]
        for coluna in COLUNAS_FEATURES:
            assert linha_a[coluna] == pytest.approx(linha_b[coluna], nan_ok=True), (
                f"a feature {coluna} reagiu a uma mudança em T+1 — há vazamento"
            )
        assert linha_a["rotulo"] == 0 and linha_b["rotulo"] == 1

    def test_historico_conta_apenas_ate_t(self):
        con = _painel_cheio({"000001": [-1.0, 5.0, 5.0, 5.0, 5.0]})
        quadro = construir_painel(con).quadro.set_index("trimestre")
        # um prejuízo em 1T2025, dentro de 1 trimestre observado
        assert quadro.loc["1T2025", "taxa_prejuizos_ate_t"] == pytest.approx(1.0)
        # em 4T2025 já são 4 trimestres com 1 prejuízo
        assert quadro.loc["4T2025", "taxa_prejuizos_ate_t"] == pytest.approx(0.25)

    def test_split_nao_deixa_trimestre_de_teste_no_treino(self):
        con = _painel_cheio({f"{i:06d}": [5.0, -1.0, 5.0, -1.0, 5.0]
                             for i in range(30)})
        divisao = dividir_temporalmente(construir_painel(con))
        ordens_treino = set(divisao.treino["ordem"])
        assert max(ordens_treino) < min(divisao.validacao["ordem"])
        assert max(divisao.validacao["ordem"]) < min(divisao.teste["ordem"])


class TestColunasDescartadas:
    def test_colunas_confundidas_com_o_tempo_ficam_fora(self):
        """Profundidade de histórico é determinada pelo trimestre no painel."""
        assert "n_trimestres_observados" not in COLUNAS_FEATURES
        assert "n_prejuizos_ate_t" not in COLUNAS_FEATURES
        assert "taxa_prejuizos_ate_t" in COLUNAS_FEATURES

    def test_todo_descarte_tem_motivo_escrito(self):
        for coluna, motivo in COLUNAS_DESCARTADAS.items():
            assert coluna not in COLUNAS_FEATURES
            assert len(motivo) >= 40, f"{coluna} descartada sem motivo suficiente"

    def test_profundidade_segue_no_quadro_para_auditoria(self):
        con = _painel_cheio({"000001": [5.0] * 5})
        assert "n_trimestres_observados" in construir_painel(con).quadro.columns


class TestMetricas:
    def test_valores_conferidos_na_mao(self):
        y = np.array([1, 1, 0, 0])
        escore = np.array([0.9, 0.4, 0.8, 0.1])
        m = avaliar("t", y, escore, limiar=0.5)
        assert (m.verdadeiro_positivo, m.falso_positivo) == (1, 1)
        assert (m.verdadeiro_negativo, m.falso_negativo) == (1, 1)
        assert m.precisao == pytest.approx(0.5)
        assert m.recall == pytest.approx(0.5)
        assert m.f1 == pytest.approx(0.5)
        assert m.acuracia == pytest.approx(0.5)

    def test_auc_none_quando_escore_e_constante(self):
        """Classe majoritária não tem AUC — reportar 0,5 seria inventar."""
        m = avaliar("t", np.array([1, 0, 1, 0]), np.zeros(4), limiar=0.5)
        assert m.roc_auc is None

    def test_matriz_de_confusao_na_ordem_declarada(self):
        m = avaliar("t", np.array([1, 0]), np.array([1.0, 0.0]), limiar=0.5)
        assert m.matriz_confusao == [[1, 0], [0, 1]]


class TestLimiar:
    def test_f2_prefere_recall_a_precisao(self):
        """O limiar escolhido não pode ser 0,5 por omissão (5.10)."""
        y = np.array([1] * 20 + [0] * 80)
        escore = np.concatenate([np.linspace(0.2, 0.9, 20),
                                 np.linspace(0.0, 0.6, 80)])
        limiar = escolher_limiar_por_f2(y, escore)
        recall_f2 = avaliar("f2", y, escore, limiar=limiar).recall
        recall_meio = avaliar("meio", y, escore, limiar=0.5).recall
        assert recall_f2 >= recall_meio

    def test_limiar_sai_da_validacao_nao_do_teste(self):
        """Contraprova de leitura: o relatório precisa usar o mesmo limiar."""
        con = _painel_cheio({f"{i:06d}": [5.0, -1.0, 5.0, -1.0, 5.0]
                             for i in range(40)})
        relatorio = treinar_e_avaliar(construir_painel(con))
        por_nome = {}
        for m in relatorio.metricas:
            por_nome.setdefault(m["nome"], {})[m["conjunto"]] = m
        for nome in ("regressao_logistica", "gradient_boosting"):
            assert por_nome[nome]["validacao"]["limiar"] == por_nome[nome]["teste"]["limiar"]


class TestBaselines:
    def test_classe_majoritaria_e_constante(self):
        con = _painel_cheio({f"{i:06d}": [5.0] * 5 for i in range(10)})
        divisao = dividir_temporalmente(construir_painel(con))
        escore = escore_classe_majoritaria(divisao.treino, divisao.teste)
        assert len(set(escore.tolist())) == 1

    def test_persistencia_copia_o_sinal_de_t(self):
        con = _painel_cheio({"000001": [-1.0, 5.0, -1.0, 5.0, -1.0]})
        quadro = construir_painel(con).quadro
        escore = escore_persistencia(quadro)
        assert list(escore) == list(quadro["prejuizo_em_t"].astype(float))

    def test_relatorio_sempre_traz_os_dois_baselines(self):
        con = _painel_cheio({f"{i:06d}": [5.0, -1.0, 5.0, -1.0, 5.0]
                             for i in range(40)})
        nomes = {m["nome"] for m in treinar_e_avaliar(construir_painel(con)).metricas}
        assert "baseline_classe_majoritaria" in nomes
        assert "baseline_persistencia" in nomes


class TestRN07:
    """A fronteira que o módulo se impõe."""

    #: Tudo que participa de responder ao usuário.
    CAMINHO_INTERATIVO = (
        "src/agentes.py",
        "src/ferramentas.py",
        "src/braco_agente.py",
        "src/braco_determinista.py",
        "src/geracao.py",
        "src/recuperacao.py",
        "src/cobertura.py",
        "src/seguranca.py",
        "app_streamlit.py",
    )

    def test_previsao_por_companhia_sempre_recusa(self):
        with pytest.raises(prever.PrevisaoPorCompanhiaBloqueadaError):
            prever.prever_para_companhia("019348", "1T2026")

    def test_nenhum_modulo_do_caminho_interativo_importa_o_modelo(self):
        padrao = re.compile(r"^\s*(from|import)\s+src\.modelo\b", re.MULTILINE)
        culpados = [
            caminho
            for caminho in self.CAMINHO_INTERATIVO
            if Path(caminho).is_file()
            and padrao.search(Path(caminho).read_text(encoding="utf-8"))
        ]
        assert not culpados, (
            "RN07: o modelo preditivo não pode ser alcançável pelo caminho que "
            f"responde ao usuário; importado em {culpados}"
        )

    def test_pontuar_nao_devolve_identificador_de_companhia(self):
        con = _painel_cheio({f"{i:06d}": [5.0, -1.0, 5.0, -1.0, 5.0]
                             for i in range(30)})
        painel = construir_painel(con)
        divisao = dividir_temporalmente(painel)
        modelo = construir_regressao_logistica()
        modelo.fit(divisao.treino[list(COLUNAS_FEATURES)], divisao.treino["rotulo"])
        escores = prever.pontuar(modelo, divisao.teste)
        assert isinstance(escores, np.ndarray)
        assert escores.ndim == 1


@pytest.mark.skipif(
    not CAMINHO_PAINEL.is_file(), reason="painel CVM não construído neste ambiente"
)
class TestPainelReal:
    """Integração contra o DuckDB de verdade."""

    def test_painel_bate_com_o_volume_do_gate_g2(self):
        con = duckdb.connect(str(CAMINHO_PAINEL), read_only=True)
        painel = construir_painel(con)
        assert painel.n_observacoes > 1_000
        # G2 mediu ~29% de positivos; a faixa protege contra inversão de rótulo
        assert 0.20 < painel.taxa_positivos < 0.40

    def test_rotulo_embaralhado_derruba_o_auc_para_o_acaso(self):
        """Contraprova de vazamento: sem sinal real, não pode haver acerto."""
        from sklearn.metrics import roc_auc_score

        con = duckdb.connect(str(CAMINHO_PAINEL), read_only=True)
        divisao = dividir_temporalmente(construir_painel(con))
        gerador = np.random.default_rng(20260823)
        y_treino = gerador.permutation(divisao.treino["rotulo"].to_numpy())
        modelo = construir_gradient_boosting()
        modelo.fit(divisao.treino[list(COLUNAS_FEATURES)], y_treino)
        escore = modelo.predict_proba(divisao.teste[list(COLUNAS_FEATURES)])[:, 1]
        auc = roc_auc_score(divisao.teste["rotulo"].to_numpy(), escore)
        assert 0.40 < auc < 0.60, f"AUC {auc:.3f} com rótulo embaralhado — vazamento"

    def test_modelo_supera_a_persistencia_em_auc(self):
        """O critério que a 5.10 exige: provar que o modelo agrega."""
        con = duckdb.connect(str(CAMINHO_PAINEL), read_only=True)
        relatorio = treinar_e_avaliar(construir_painel(con))
        por = {(m["nome"], m["conjunto"]): m for m in relatorio.metricas}
        persistencia = por[("baseline_persistencia", "teste")]["roc_auc"]
        for nome in ("regressao_logistica", "gradient_boosting"):
            assert por[(nome, "teste")]["roc_auc"] > persistencia
