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
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from src.modelo import prever
from src.modelo.construir_painel import (
    COLUNAS_DESCARTADAS,
    COLUNAS_FEATURES,
    TrimestreInvalidoError,
    construir_painel,
    construir_painel_para_inferencia,
    exigir_trimestre_sem_rotulo,
    medir_republicacao,
    ordinal_trimestre,
    trimestres_completos,
)
from src.modelo.treinar import (
    GRUPO_SAZONAL,
    _quantil_t,
    ablacao_walk_forward,
    avaliar,
    avaliar_walk_forward,
    comparar_pareado,
    auc_within_companhia,
    composicao_do_topo,
    desempenho_por_estado,
    desempenho_por_recorte,
    escore_identidade_implementavel,
    escore_taxa_recente,
    pontuar_walk_forward,
    construir_gradient_boosting_com_smote,
    construir_gradient_boosting_imputado,
    dividir_walk_forward,
    metricas_de_calibracao,
    metricas_de_ranqueamento,
    escore_passeio_sazonal,
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


def _con_sintetica(
    linhas: list[tuple], bancos: set[str] | None = None
) -> duckdb.DuckDBPyConnection:
    """`indicadores` + `companhias` mínimas em memória.

    `companhias` existe porque o painel passou a trazer o controle setorial
    (`instituicao_financeira`) por junção — sem a tabela a consulta nem monta.
    """
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
    con.execute("CREATE TABLE companhias (cd_cvm VARCHAR, is_banco BOOLEAN)")
    bancos = bancos or set()
    for cd in sorted({linha[0] for linha in linhas}):
        con.execute(
            "INSERT INTO companhias VALUES (?,?)", [cd, cd in bancos]
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


_TRIMESTRES_LONGOS = tuple(
    f"{n}T{ano}" for ano in (2020, 2021, 2022, 2023) for n in (1, 2, 3, 4)
)


def _painel_longo(lucros_por_companhia: dict[str, list[float]]):
    """Painel de 16 trimestres — o mínimo para features sazonais existirem."""
    linhas = []
    for cd, lucros in lucros_por_companhia.items():
        for tri, lucro in zip(_TRIMESTRES_LONGOS, lucros):
            linhas.append((cd, tri, lucro, 1_000.0, 5_000.0))
    return _con_sintetica(linhas)


def _painel_longo_variado(n_companhias: int = 20):
    """Companhias com séries DIFERENTES entre si.

    Séries idênticas produzem folds de classe única — que
    `dividir_walk_forward` descarta com razão, porque AUC não existe neles.
    """
    gerador = np.random.default_rng(11)
    return _painel_longo(
        {
            f"{i:06d}": (gerador.normal(0.4, 3.0, 16)).tolist()
            for i in range(n_companhias)
        }
    )


class TestFeaturesSazonais:
    """A janela larga do painel de treino é o que as torna calculáveis."""

    def test_mesmo_trimestre_do_ano_anterior_olha_para_t_menos_3(self):
        """O alvo é T+1; o mesmo trimestre do ano anterior é T-3, não T-4."""
        # prejuízo isolado em 2T2020 (índice 1)
        lucros = [5.0] * 16
        lucros[1] = -7.0
        quadro = construir_painel(
            _painel_longo({"000001": lucros})
        ).quadro.set_index("trimestre")
        # a linha de T=1T2021 (índice 4) tem alvo 2T2021 e T-3 = 2T2020
        assert (
            quadro.loc["1T2021", "prejuizo_no_mesmo_trimestre_do_ano_anterior"] == 1
        )
        assert (
            quadro.loc["4T2020", "prejuizo_no_mesmo_trimestre_do_ano_anterior"] == 0
        )

    def test_trimestre_do_ano_cobre_os_quatro_valores(self):
        quadro = construir_painel(_painel_longo({"000001": [5.0] * 16})).quadro
        assert set(quadro["trimestre_do_ano"].unique()) == {1, 2, 3, 4}

    def test_taxa_4t_e_janela_movel_e_nao_historico_inteiro(self):
        """Um prejuízo antigo sai da janela; a taxa sobre todo histórico não."""
        lucros = [-1.0] + [5.0] * 15
        quadro = construir_painel(
            _painel_longo({"000001": lucros})
        ).quadro.set_index("trimestre")
        assert quadro.loc["1T2020", "taxa_prejuizos_4t"] == pytest.approx(1.0)
        # quatro trimestres depois o prejuízo já saiu da janela móvel
        assert quadro.loc["1T2021", "taxa_prejuizos_4t"] == pytest.approx(0.0)
        # mas segue contando no histórico completo
        assert quadro.loc["1T2021", "taxa_prejuizos_ate_t"] > 0

    def test_variacao_anual_fica_limitada_a_menos_um_e_um(self):
        gerador = np.random.default_rng(7)
        lucros = (gerador.normal(0, 1e6, 16)).tolist()
        quadro = construir_painel(_painel_longo({"000001": lucros})).quadro
        valores = quadro["variacao_lucro_anual"].dropna()
        assert not valores.empty
        assert valores.between(-1.0, 1.0).all()


class TestOscoreRemovidoPorMedicao:
    """Resultado negativo tem de ficar visível, não sumir do código."""

    def test_features_do_oscore_saem_das_features(self):
        from src.modelo.construir_painel import OSCORE_REMOVIDAS_POR_MEDICAO

        for coluna in OSCORE_REMOVIDAS_POR_MEDICAO:
            assert coluna not in COLUNAS_FEATURES

    def test_seguem_calculadas_no_quadro_para_auditoria(self):
        from src.modelo.construir_painel import OSCORE_REMOVIDAS_POR_MEDICAO

        quadro = construir_painel(_painel_longo({"000001": [5.0] * 16})).quadro
        for coluna in OSCORE_REMOVIDAS_POR_MEDICAO:
            assert coluna in quadro.columns


class TestWalkForward:
    def test_um_fold_por_trimestre_apos_o_minimo(self):
        con = _painel_longo_variado()
        painel = construir_painel(con)
        divisoes = dividir_walk_forward(painel, minimo_trimestres_treino=4)
        assert len(divisoes) >= 8
        # testes em ordem cronológica estrita, sem repetição
        ordens = [d.teste["ordem"].iloc[0] for d in divisoes]
        assert ordens == sorted(ordens)
        assert len(set(ordens)) == len(ordens)

    def test_nenhum_fold_treina_no_futuro_do_seu_teste(self):
        """A guarda que faz o walk-forward valer alguma coisa."""
        con = _painel_longo_variado()
        for divisao in dividir_walk_forward(
            construir_painel(con), minimo_trimestres_treino=4
        ):
            ordem_teste = divisao.teste["ordem"].iloc[0]
            assert divisao.treino["ordem"].max() < ordem_teste
            assert divisao.validacao["ordem"].max() < ordem_teste

    def test_treino_e_expansivel_e_nunca_encolhe(self):
        con = _painel_longo_variado()
        divisoes = dividir_walk_forward(
            construir_painel(con), minimo_trimestres_treino=4
        )
        tamanhos = [len(d.treino) for d in divisoes]
        assert tamanhos == sorted(tamanhos)


class TestAlvoPersistente:
    """Prejuízo em T+1 E T+2 — separa deterioração de ruído contábil."""

    def test_exige_prejuizo_em_todos_os_trimestres_da_janela(self):
        # prejuízo isolado em 2T2020 (índice 1): não basta para o alvo de 2
        lucros = [5.0] * 16
        lucros[1] = -7.0
        quadro = construir_painel(
            _painel_longo({"000001": lucros}), trimestres_consecutivos=2
        ).quadro.set_index("trimestre")
        assert quadro.loc["1T2020", "rotulo"] == 0

    def test_dois_prejuizos_seguidos_marcam_o_alvo(self):
        lucros = [5.0] * 16
        lucros[1] = lucros[2] = -7.0  # 2T2020 e 3T2020
        quadro = construir_painel(
            _painel_longo({"000001": lucros}), trimestres_consecutivos=2
        ).quadro.set_index("trimestre")
        assert quadro.loc["1T2020", "rotulo"] == 1

    def test_janela_incompleta_sai_da_amostra(self):
        """Rótulo parcial seria rótulo inventado."""
        lucros = [5.0] * 16
        painel = construir_painel(
            _painel_longo({"000001": lucros}), trimestres_consecutivos=2
        )
        # com 16 trimestres e alvo de 2, sobram 14 linhas rotuláveis
        assert painel.n_observacoes == 14

    def test_alvo_persistente_e_mais_raro_que_o_de_um_trimestre(self):
        gerador = np.random.default_rng(5)
        lucros = gerador.normal(0.0, 2.0, 16).tolist()
        con_um = _painel_longo({"000001": lucros})
        con_dois = _painel_longo({"000001": lucros})
        um = construir_painel(con_um, trimestres_consecutivos=1)
        dois = construir_painel(con_dois, trimestres_consecutivos=2)
        assert dois.taxa_positivos <= um.taxa_positivos

    def test_zero_trimestres_e_rejeitado(self):
        with pytest.raises(ValueError, match="precisa ser >= 1"):
            construir_painel(
                _painel_longo({"000001": [5.0] * 16}), trimestres_consecutivos=0
            )


class TestMetricasDeRanqueamento:
    """O uso declarado é ORDENAR; ordenação se mede no topo da lista."""

    def test_ordenacao_perfeita_da_precisao_maxima_no_topo(self):
        y = np.array([1] * 10 + [0] * 90)
        escore = np.concatenate([np.linspace(0.9, 0.8, 10), np.linspace(0.5, 0.0, 90)])
        r = metricas_de_ranqueamento(y, escore)
        assert r["precisao_topo_10pct"] == pytest.approx(1.0)
        assert r["lift_topo_10pct"] == pytest.approx(10.0)

    def test_escore_aleatorio_da_lift_perto_de_um(self):
        gerador = np.random.default_rng(1)
        y = (gerador.random(4000) < 0.3).astype(int)
        r = metricas_de_ranqueamento(y, gerador.random(4000))
        assert 0.7 < r["lift_topo_10pct"] < 1.3

    def test_recall_no_topo_cresce_com_a_fatia(self):
        gerador = np.random.default_rng(2)
        y = (gerador.random(1000) < 0.3).astype(int)
        escore = y * 0.6 + gerador.random(1000) * 0.4
        r = metricas_de_ranqueamento(y, escore)
        assert (
            r["recall_topo_5pct"]
            <= r["recall_topo_10pct"]
            <= r["recall_topo_20pct"]
            <= r["recall_topo_30pct"]
        )


class TestCalibracao:
    def test_probabilidade_perfeita_tem_brier_baixo(self):
        y = np.array([1, 1, 0, 0])
        assert metricas_de_calibracao(y, np.array([1.0, 1.0, 0.0, 0.0]))["brier"] == 0.0

    def test_probabilidade_invertida_tem_brier_maximo(self):
        y = np.array([1, 1, 0, 0])
        assert metricas_de_calibracao(y, np.array([0.0, 0.0, 1.0, 1.0]))["brier"] == 1.0

    def test_erro_de_calibracao_flagra_excesso_de_confianca(self):
        """Modelo que diz 0,9 e acerta 0,5 tem de aparecer como descalibrado."""
        gerador = np.random.default_rng(4)
        y = (gerador.random(2000) < 0.5).astype(int)
        escore = np.full(2000, 0.9)
        r = metricas_de_calibracao(y, escore)
        assert r["erro_calibracao_esperado"] > 0.3


class TestSmote:
    def test_pipeline_reamostra_so_no_treino(self):
        """Contraprova de vazamento: SMOTE na predição sintetizaria o teste.

        O `Pipeline` do imblearn garante isso; o do scikit-learn, não. Se
        alguém trocar um pelo outro, o número de predições deixa de bater com
        o número de linhas de entrada.
        """
        con = _painel_longo_variado(n_companhias=40)
        divisao = dividir_walk_forward(
            construir_painel(con), minimo_trimestres_treino=4
        )[-1]
        colunas = list(COLUNAS_FEATURES)
        modelo = construir_gradient_boosting_com_smote()
        modelo.fit(divisao.treino[colunas], divisao.treino["rotulo"].to_numpy(int))
        previsto = modelo.predict_proba(divisao.teste[colunas])
        assert len(previsto) == len(divisao.teste)

    def test_controle_imputado_existe_para_isolar_o_efeito(self):
        """SMOTE exige imputação; comparar com o boosting puro mediria duas coisas."""
        modelo = construir_gradient_boosting_imputado()
        assert "imputacao" in dict(modelo.named_steps)


class TestComparacaoPareada:
    """Os p-valores publicados no relatório saem daqui — precisam de contrato."""

    def test_diferenca_e_pareada_e_nao_diferenca_de_medias(self):
        """O pareamento cancela a variação comum entre folds.

        Dois modelos podem ter médias quase iguais e mesmo assim um vencer o
        outro em todos os folds — é o caso que a comparação solta perderia.
        """
        por_fold = [
            {"a": 0.80 + i * 0.01, "b": 0.79 + i * 0.01} for i in range(10)
        ]
        resultado = comparar_pareado(por_fold, "a", "b")
        assert resultado is not None
        assert resultado["diferenca_media"] == pytest.approx(0.01, abs=1e-9)
        assert resultado["folds_vencidos"] == 10
        assert resultado["ic95_inferior"] > 0

    def test_ic_inclui_zero_quando_nao_ha_diferenca(self):
        gerador = np.random.default_rng(3)
        por_fold = [
            {"a": float(x), "b": float(y)}
            for x, y in zip(
                gerador.normal(0.85, 0.03, 40), gerador.normal(0.85, 0.03, 40)
            )
        ]
        resultado = comparar_pareado(por_fold, "a", "b")
        assert resultado["ic95_inferior"] < 0 < resultado["ic95_superior"]

    def test_devolve_none_com_folds_de_menos(self):
        assert comparar_pareado([{"a": 0.8, "b": 0.7}], "a", "b") is None

    def test_ignora_fold_sem_o_valor_dos_dois(self):
        por_fold = [
            {"a": 0.80, "b": 0.70},
            {"a": 0.81, "b": None},
            {"a": 0.82, "b": 0.72},
            {"a": 0.83, "b": 0.73},
        ]
        assert comparar_pareado(por_fold, "a", "b")["n_folds"] == 3


class TestPainelDeInferencia:
    """Escorar o trimestre corrente sem inventar rótulo (auditoria 2026-08-25).

    `construir_painel` junta o alvo com `JOIN` + `HAVING count(*) = n`: quem
    não tem os n trimestres futuros some. Correto para treinar, errado para
    usar — a companhia sobre a qual se quer prever é justamente essa.
    """

    def test_alcanca_trimestre_que_o_painel_de_treino_descarta(self):
        lucros = {f"{i:06d}": [5.0, -2.0, 4.0, 6.0, 3.0] for i in range(6)}
        lucros["000001"] = [5.0, 4.0, 3.0, 2.0, 1.0]
        con = _painel_cheio(lucros)
        treino = construir_painel(con, trimestres_consecutivos=2)
        inferencia = construir_painel_para_inferencia(
            con, trimestres_consecutivos=2
        )
        ultimo_rotulado = max(treino.quadro["ordem"])
        assert ordinal_trimestre(inferencia.trimestre) > ultimo_rotulado
        assert inferencia.trimestre == _TRIMESTRES[-1]

    def test_rotulo_e_NA_e_nunca_zero(self):
        """O defeito que a junção frouxa criaria se ninguém olhasse.

        `LEFT JOIN` faz `n_prejuizos_futuros` virar NULL, e o `CASE` cairia no
        `ELSE 0` — rótulo "lucro" para quem simplesmente não tem futuro. Isso
        treinaria o modelo a chamar de saudável todo trimestre recente.
        """
        con = _painel_cheio({f"{i:06d}": [5.0, -2.0, 4.0, 6.0, 3.0] for i in range(6)})
        inferencia = construir_painel_para_inferencia(con)
        assert inferencia.quadro["rotulo"].isna().all()
        assert (inferencia.quadro["rotulo_conhecido"] == 0).all()

    def test_recorte_padrao_deixa_so_quem_esta_hoje_lucrativo(self):
        """97,1% do decil superior já está em prejuízo — sem o recorte, o
        escore devolve o que a demonstração já dizia."""
        lucros = {
            "000001": [5.0, 5.0, 5.0, 5.0, 4.0],    # lucrativa em T
            "000002": [5.0, 5.0, 5.0, 5.0, -4.0],   # já em prejuízo em T
            "000003": [1.0, -1.0, 2.0, 3.0, -2.0],  # já em prejuízo em T
        }
        inferencia = construir_painel_para_inferencia(_painel_cheio(lucros))
        assert set(inferencia.quadro["cd_cvm"]) == {"000001"}
        assert inferencia.n_descartadas_por_ja_estar_em_prejuizo == 2
        assert (inferencia.quadro["prejuizo_em_t"] == 0).all()

    def test_o_denominador_descartado_fica_disponivel(self):
        """Queda de volume não pode passar por melhora."""
        lucros = {
            "000001": [5.0, 5.0, 5.0, 5.0, 4.0],
            "000002": [5.0, 5.0, 5.0, 5.0, -4.0],
        }
        con = _painel_cheio(lucros)
        completo = construir_painel_para_inferencia(
            con, somente_hoje_lucrativas=False
        )
        recortado = construir_painel_para_inferencia(con)
        assert completo.n_companhias == 2
        assert (
            recortado.n_companhias
            + recortado.n_descartadas_por_ja_estar_em_prejuizo
            == completo.n_companhias
        )

    def test_falha_fechada_quando_o_trimestre_ja_tem_rotulo(self):
        """A guarda LEVANTA — e este teste chama `pytest.raises` de verdade.

        A primeira versão deste teste tinha esse nome, essa docstring e nenhum
        `raises`: exercitava o caminho feliz e afirmava cobrir a falha fechada.
        Foi achado da auditoria de 2026-08-25 e é o motivo de a guarda ter sido
        extraída para função própria — embutida, a condição é inalcançável e
        não havia como testá-la sem mentir.
        """
        quadro = pd.DataFrame(
            {"cd_cvm": ["000001", "000002"], "rotulo_conhecido": [0, 1]}
        )
        with pytest.raises(ValueError, match="já tem rótulo conhecido"):
            exigir_trimestre_sem_rotulo(quadro, "1T2026")

    def test_guarda_passa_quando_nenhum_rotulo_e_conhecido(self):
        quadro = pd.DataFrame(
            {"cd_cvm": ["000001", "000002"], "rotulo_conhecido": [0, 0]}
        )
        assert exigir_trimestre_sem_rotulo(quadro, "1T2026") is None

    def test_guarda_rejeita_quadro_sem_a_coluna(self):
        """Sem `rotulo_conhecido` não há como separar 'lucro' de 'ainda não
        aconteceu' — passar batido seria pior que levantar."""
        with pytest.raises(ValueError, match="rotulo_conhecido"):
            exigir_trimestre_sem_rotulo(pd.DataFrame({"cd_cvm": ["1"]}), "1T2026")

    def test_janela_encurtada_ainda_escora_trimestre_sem_futuro(self):
        """Contraprova do caminho feliz, agora com o nome que descreve o que é."""
        con = _painel_cheio({f"{i:06d}": [5.0, -2.0, 4.0, 6.0, 3.0] for i in range(4)})
        con.execute(f"DELETE FROM indicadores WHERE trimestre = '{_TRIMESTRES[-1]}'")
        con.execute(f"DELETE FROM indicadores WHERE trimestre = '{_TRIMESTRES[-2]}'")
        inferencia = construir_painel_para_inferencia(con)
        assert inferencia.trimestre == _TRIMESTRES[-3]
        assert (inferencia.quadro["rotulo_conhecido"] == 0).all()

    def test_features_batem_com_as_do_treino(self):
        """Coluna a mais ou a menos aqui é erro de inferência silencioso."""
        con = _painel_cheio({f"{i:06d}": [5.0, -2.0, 4.0, 6.0, 3.0] for i in range(6)})
        treino = construir_painel(con)
        inferencia = construir_painel_para_inferencia(con)
        for coluna in COLUNAS_FEATURES:
            assert coluna in inferencia.quadro.columns
        assert list(treino.quadro[list(COLUNAS_FEATURES)].columns) == list(
            inferencia.quadro[list(COLUNAS_FEATURES)].columns
        )

    def test_nao_e_um_painel_supervisionado(self):
        """Tipo diferente de propósito: passar um pelo outro treinaria sobre
        rótulo inexistente, e o erro precisa aparecer no tipo, não no número."""
        con = _painel_cheio({f"{i:06d}": [5.0, -2.0, 4.0, 6.0, 3.0] for i in range(4)})
        inferencia = construir_painel_para_inferencia(con)
        assert not isinstance(inferencia, type(construir_painel(con)))
        assert not hasattr(inferencia, "taxa_positivos")


class TestViesAsRestated:
    """O viés as-restated passou de declaração a medição (2026-08-25).

    A carga mantém só a maior VERSAO — regra certa para consulta, viés de
    antecipação para o treino. Como não é reversível com o painel carregado, o
    que se exige é medir a exposição e, sobretudo, se ela é assimétrica entre
    as classes: republicação concentrada no prejuízo contaminaria o rótulo.
    """

    @staticmethod
    def _con_com_versoes(versoes: dict[tuple[str, str], int], lucros):
        con = _con_sintetica(lucros)
        con.execute(
            """
            CREATE TABLE fatos_contabeis (
                cd_cvm VARCHAR, trimestre VARCHAR, versao_documento INTEGER
            )
            """
        )
        for (cd, tri), versao in versoes.items():
            con.execute("INSERT INTO fatos_contabeis VALUES (?,?,?)", [cd, tri, versao])
        return con

    def test_conta_a_observacao_e_nao_o_fato(self):
        """Uma companhia×trimestre com 20 linhas republicadas conta UMA vez."""
        con = self._con_com_versoes(
            {("000001", "1T2025"): 1, ("000002", "1T2025"): 3},
            [("000001", "1T2025", 5.0, 100.0, 900.0),
             ("000002", "1T2025", 4.0, 100.0, 900.0)],
        )
        for _ in range(19):
            con.execute("INSERT INTO fatos_contabeis VALUES ('000002','1T2025',3)")
        medida = medir_republicacao(con)
        assert medida["n_observacoes"] == 2
        assert medida["n_republicadas"] == 1
        assert medida["fracao_republicada"] == pytest.approx(0.5)

    def test_versao_um_nao_conta_como_republicacao(self):
        con = self._con_com_versoes(
            {("000001", "1T2025"): 1, ("000002", "1T2025"): 1},
            [("000001", "1T2025", 5.0, 100.0, 900.0),
             ("000002", "1T2025", 4.0, 100.0, 900.0)],
        )
        assert medir_republicacao(con)["n_republicadas"] == 0

    def test_assimetria_entre_classes_e_o_numero_que_importa(self):
        """Republicação SÓ nos trimestres de prejuízo tem de aparecer como tal.

        É o cenário de contaminação: o rótulo negativo só existe porque a
        companhia corrigiu o número depois. Se a medida não separasse por
        classe, este caso ficaria indistinguível de ruído uniforme.
        """
        con = self._con_com_versoes(
            {
                ("000001", "1T2025"): 2,   # prejuízo, republicado
                ("000002", "1T2025"): 2,   # prejuízo, republicado
                ("000003", "1T2025"): 1,   # lucro, original
                ("000004", "1T2025"): 1,   # lucro, original
            },
            [("000001", "1T2025", -5.0, 100.0, 900.0),
             ("000002", "1T2025", -4.0, 100.0, 900.0),
             ("000003", "1T2025", 5.0, 100.0, 900.0),
             ("000004", "1T2025", 4.0, 100.0, 900.0)],
        )
        medida = medir_republicacao(con)
        assert medida["fracao_republicada_em_prejuizo"] == pytest.approx(1.0)
        assert medida["fracao_republicada_em_lucro"] == pytest.approx(0.0)
        assert medida["assimetria_entre_classes"] == pytest.approx(1.0)

    def test_uniforme_entre_classes_da_assimetria_nula(self):
        con = self._con_com_versoes(
            {
                ("000001", "1T2025"): 2,
                ("000002", "1T2025"): 1,
                ("000003", "1T2025"): 2,
                ("000004", "1T2025"): 1,
            },
            [("000001", "1T2025", -5.0, 100.0, 900.0),
             ("000002", "1T2025", -4.0, 100.0, 900.0),
             ("000003", "1T2025", 5.0, 100.0, 900.0),
             ("000004", "1T2025", 4.0, 100.0, 900.0)],
        )
        assert medir_republicacao(con)["assimetria_entre_classes"] == pytest.approx(0.0)

    def test_a_ressalva_acompanha_o_numero(self):
        """Número sem a ressalva ao lado seria lido como "está tudo bem"."""
        con = self._con_com_versoes(
            {("000001", "1T2025"): 1},
            [("000001", "1T2025", 5.0, 100.0, 900.0)],
        )
        assert "as-restated" in medir_republicacao(con)["ressalva"]


class TestQuantilDoIntervalo:
    """O IC usa a t de Student, não o 1,96 da normal (auditoria 2026-08-25).

    O erro padrão é estimado da própria amostra de folds; com amostra pequena
    o quantil normal produz intervalo estreito demais, e IC estreito demais é
    afirmação forte demais. Estes testes travam a correção — sem eles, alguém
    "simplifica" o quantil de volta para 1,96 e nada quebra.
    """

    def test_quantil_e_maior_que_o_da_normal_e_cai_nele_no_limite(self):
        # Com 5 folds a diferença é grosseira; com 1.000 já é indistinguível.
        assert _quantil_t(4) > 2.7
        assert _quantil_t(46) == pytest.approx(2.0129, abs=1e-3)
        assert _quantil_t(1000) == pytest.approx(1.962, abs=1e-3)

    def test_amostra_pequena_alarga_o_intervalo_em_vez_de_estreitar(self):
        """A contraprova direta do defeito: com 1,96 este IC excluiria zero."""
        por_fold = [
            {"a": 0.80, "b": 0.79},
            {"a": 0.82, "b": 0.804},
            {"a": 0.78, "b": 0.769},
            {"a": 0.85, "b": 0.845},
        ]
        resultado = comparar_pareado(por_fold, "a", "b")
        diferencas = np.array([0.01, 0.016, 0.011, 0.005])
        erro_padrao = diferencas.std(ddof=1) / np.sqrt(4)
        assert resultado["quantil_usado"] > 1.96
        assert resultado["ic95_inferior"] == pytest.approx(
            diferencas.mean() - resultado["quantil_usado"] * erro_padrao
        )
        # O que a correção custa: um resultado que a normal chamaria de
        # significativo passa a ficar mais perto da fronteira.
        assert resultado["ic95_inferior"] < diferencas.mean() - 1.96 * erro_padrao

    def test_o_rotulo_enganoso_nao_ressuscita(self):
        """`auc_ic95_*` nomeava percentil de fold como se fosse IC da média.

        Os dois números passaram a existir separados e com nome que diz o que
        cada um é. Este teste falha se alguém reintroduzir o rótulo antigo.
        """
        painel = construir_painel(
            _painel_longo_variado(n_companhias=60), trimestres_consecutivos=1
        )
        bloco = avaliar_walk_forward(painel)["resumo"]["gradient_boosting"]

        assert "auc_ic95_inferior" not in bloco
        assert "auc_ic95_superior" not in bloco
        for chave in (
            "auc_faixa_folds_p2_5",
            "auc_faixa_folds_p97_5",
            "auc_ic95_da_media_inferior",
            "auc_ic95_da_media_superior",
        ):
            assert chave in bloco
        assert bloco["auc_ic95_da_media_inferior"] <= bloco["auc_medio"]
        assert bloco["auc_medio"] <= bloco["auc_ic95_da_media_superior"]

    def test_com_folds_suficientes_a_incerteza_da_media_e_muito_mais_estreita(self):
        """A razão de os dois números não poderem compartilhar rótulo.

        Com os 47 folds da execução publicável, a faixa entre folds é ~7x mais
        larga que a incerteza da média: a primeira diz "existe trimestre ruim",
        a segunda diz "a média publicada vale isto". Chamar a faixa de IC 95%
        exagerava a imprecisão do resultado — conservador, mas errado.

        (Com pouquíssimos folds a relação se inverte, porque o quantil da t
        explode. Por isso a contraprova roda no tamanho real, não no sintético
        de 2 folds.)
        """
        gerador = np.random.default_rng(7)
        vetor = gerador.normal(0.865, 0.033, 47)
        largura_folds = float(
            np.percentile(vetor, 97.5) - np.percentile(vetor, 2.5)
        )
        erro_padrao = float(vetor.std(ddof=1) / np.sqrt(len(vetor)))
        largura_media = 2 * _quantil_t(len(vetor) - 1) * erro_padrao
        assert largura_media < largura_folds / 4


class TestAblacao:
    def test_exige_que_o_grupo_esteja_em_uso(self):
        """Ablação de feature inexistente devolveria diferença zero enganosa."""
        con = _painel_longo_variado()
        with pytest.raises(ValueError, match="nenhuma das features"):
            ablacao_walk_forward(
                construir_painel(con), ("coluna_que_nao_existe",)
            )

    def test_mede_o_grupo_sazonal_e_relata_os_dois_lados(self):
        con = _painel_longo_variado(n_companhias=30)
        resultado = ablacao_walk_forward(
            construir_painel(con), GRUPO_SAZONAL, minimo_trimestres_treino=4
        )
        assert set(resultado["grupo"]) == set(GRUPO_SAZONAL)
        assert 0.0 <= resultado["auc_completo"] <= 1.0
        assert 0.0 <= resultado["auc_sem_o_grupo"] <= 1.0
        assert resultado["comparacao"] is not None


class TestPasseioSazonal:
    def test_repete_o_mesmo_trimestre_do_ano_anterior(self):
        quadro = pd.DataFrame(
            {
                "prejuizo_no_mesmo_trimestre_do_ano_anterior": [1.0, 0.0],
                "prejuizo_em_t": [0.0, 1.0],
            }
        )
        assert list(escore_passeio_sazonal(quadro)) == [1.0, 0.0]

    def test_cai_para_a_persistencia_quando_falta_o_ano_anterior(self):
        """Companhia recém-listada não pode ser excluída silenciosamente."""
        quadro = pd.DataFrame(
            {
                "prejuizo_no_mesmo_trimestre_do_ano_anterior": [np.nan, np.nan],
                "prejuizo_em_t": [1.0, 0.0],
            }
        )
        assert list(escore_passeio_sazonal(quadro)) == [1.0, 0.0]


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


class TestPurga:
    """Rótulo que olha para frente não pode atravessar a fronteira do fold."""

    def test_a_purga_afeta_TAMBEM_o_alvo_de_um_trimestre(self):
        """Uma contraprova anterior deste arquivo afirmava o contrário.

        Ela dizia que com `n = 1` a purga não removia nada, porque o rótulo do
        treino alcançava só a validação. Estava certa sobre o treino e **errada
        sobre o conjunto todo**: a validação em `k−1` tem rótulo igual ao
        desfecho do próprio trimestre de teste, e é dela que sai o limiar. Ou
        seja, o alvo de 1 trimestre também estava contaminado, e a asserção
        antiga travava justamente o comportamento defeituoso.
        """
        con = _painel_longo_variado(n_companhias=20)
        painel = construir_painel(con, trimestres_consecutivos=1)
        com = dividir_walk_forward(painel, purgar=True)
        sem = dividir_walk_forward(painel, purgar=False)
        assert com and sem
        assert sum(len(d.treino) for d in com) < sum(len(d.treino) for d in sem)
        # e o defeito que a purga fecha, exibido diretamente
        for divisao in sem:
            ordem_teste = divisao.teste["ordem"].iloc[0]
            assert divisao.validacao["ordem"].iloc[0] + 1 == ordem_teste, (
                "sem purga, o rótulo da validação É o desfecho do teste"
            )

    def test_alvo_persistente_remove_o_trimestre_que_vaza(self):
        con = _painel_longo_variado(n_companhias=20)
        painel = construir_painel(con, trimestres_consecutivos=2)
        com = dividir_walk_forward(painel, purgar=True)
        sem = dividir_walk_forward(painel, purgar=False)
        assert com, "sem folds não há o que verificar"
        assert sum(len(d.treino) for d in com) < sum(len(d.treino) for d in sem)

    def test_nenhuma_linha_de_treino_tem_rotulo_alcancando_o_teste(self):
        """A invariante, verificada diretamente em vez de inferida."""
        con = _painel_longo_variado(n_companhias=20)
        for n_alvo in (1, 2, 3):
            painel = construir_painel(con, trimestres_consecutivos=n_alvo)
            for divisao in dividir_walk_forward(painel):
                ordem_teste = divisao.teste["ordem"].iloc[0]
                ultima_do_treino = divisao.treino["ordem"].max()
                assert ultima_do_treino + n_alvo < ordem_teste, (
                    f"alvo de {n_alvo} trimestres: linha de treino em "
                    f"{ultima_do_treino} tem rótulo cobrindo até "
                    f"{ultima_do_treino + n_alvo}, alcançando o teste em "
                    f"{ordem_teste}"
                )

    def test_a_VALIDACAO_tambem_nao_alcanca_o_teste(self):
        """O vazamento que sobreviveu ao teste-guarda anterior.

        A versão anterior deste arquivo inspecionava só `divisao.treino`. Com
        alvo de 2 trimestres, a validação em k−1 tem rótulo cobrindo {k, k+1} e
        o teste em k cobre {k+1, k+2} — k+1 é comum, e o limiar F2 sai da
        validação, então todo número dependente de limiar estava contaminado.
        """
        con = _painel_longo_variado(n_companhias=20)
        for n_alvo in (1, 2, 3):
            painel = construir_painel(con, trimestres_consecutivos=n_alvo)
            for divisao in dividir_walk_forward(painel):
                ordem_teste = divisao.teste["ordem"].iloc[0]
                ordem_validacao = divisao.validacao["ordem"].iloc[0]
                assert ordem_validacao + n_alvo < ordem_teste, (
                    f"alvo de {n_alvo} trimestres: validação em "
                    f"{ordem_validacao} tem rótulo cobrindo até "
                    f"{ordem_validacao + n_alvo}, que alcança o teste em "
                    f"{ordem_teste} — o limiar sairia de dado contaminado"
                )

    def test_validacao_e_teste_nunca_sao_o_mesmo_trimestre(self):
        con = _painel_longo_variado(n_companhias=20)
        painel = construir_painel(con, trimestres_consecutivos=2)
        for divisao in dividir_walk_forward(painel):
            assert divisao.trimestre_validacao != divisao.trimestre_teste


class TestSemAjusteImplicito:
    """`early_stopping` não pode selecionar hiperparâmetro por baixo do pano."""

    def test_early_stopping_desligado_explicitamente(self):
        """O padrão `'auto'` liga sozinho com n > 10.000 e ajusta o nº de árvores.

        Isso tornava falsa a ressalva publicada de que nenhum ajuste de
        hiperparâmetro havia sido feito, e desequilibrava a comparação com a
        logística, que não tem ajustador implícito.
        """
        modelo = construir_gradient_boosting()
        assert modelo.early_stopping is False

    def test_todos_os_folds_treinam_o_mesmo_numero_de_arvores(self):
        con = _painel_longo_variado(n_companhias=40)
        painel = construir_painel(con, trimestres_consecutivos=1)
        iteracoes = set()
        for divisao in dividir_walk_forward(painel):
            modelo = construir_gradient_boosting()
            modelo.fit(
                divisao.treino[list(COLUNAS_FEATURES)],
                divisao.treino["rotulo"].to_numpy(int),
            )
            assert getattr(modelo, "do_early_stopping_", False) is False
            iteracoes.add(modelo.n_iter_)
        assert len(iteracoes) == 1, (
            f"o estimador mudou entre folds: n_iter_ observados {iteracoes}"
        )


class TestDesempenhoPorRecorte:
    """Recorte raso não pode virar linha de tabela com AUC bonito."""

    def _pontuado(self):
        # 60 companhias porque a guarda padrão exige 20 eventos da classe
        # minoritária: com 25 a fixture tem 15 positivos e o recorte AMPLO
        # sairia insuficiente, o que mediria o tamanho da fixture em vez do
        # comportamento da função.
        con = _painel_longo_variado(n_companhias=60)
        painel = construir_painel(con, trimestres_consecutivos=1)
        return pontuar_walk_forward(painel)

    def test_recorte_com_poucos_eventos_sai_insuficiente(self):
        pontuado = self._pontuado()
        # Recorte artificialmente estreito: as 60 primeiras linhas, das quais
        # dificilmente 20 são positivas.
        mascara = pd.Series(
            [i < 60 for i in range(len(pontuado))], index=pontuado.index
        )
        saida = desempenho_por_recorte(
            pontuado, {"estreito": mascara}, minimo_positivos=1000
        )
        assert saida["estreito"]["suficiente"] is False
        assert "roc_auc" not in saida["estreito"]
        assert saida["estreito"]["motivo_insuficiente"]

    def test_guarda_olha_a_classe_MINORITARIA(self):
        """Muitos positivos e quase nenhum negativo é igualmente raso."""
        pontuado = self._pontuado()
        so_positivos_e_um = pontuado["rotulo"] == 1
        indices = list(pontuado.index[~so_positivos_e_um.to_numpy()][:2])
        mascara = so_positivos_e_um | pontuado.index.isin(indices)
        saida = desempenho_por_recorte(pontuado, {"desbalanceado": mascara})
        assert saida["desbalanceado"]["suficiente"] is False

    def test_recorte_amplo_traz_auc_e_lift(self):
        pontuado = self._pontuado()
        saida = desempenho_por_recorte(
            pontuado, {"tudo": pontuado["rotulo"].notna()}
        )
        bloco = saida["tudo"]
        assert bloco["suficiente"] is True
        assert 0.0 <= bloco["roc_auc"] <= 1.0
        assert bloco["lift_topo_10pct"] >= 0.0
        assert bloco["n_positivos"] > 0

    def test_por_estado_separa_quem_ja_esta_em_prejuizo(self):
        pontuado = self._pontuado()
        saida = desempenho_por_estado(pontuado, minimo_observacoes=10)
        assert set(saida) == {"ja_em_prejuizo", "lucrativa_hoje"}
        soma = saida["ja_em_prejuizo"]["n"] + saida["lucrativa_hoje"]["n"]
        assert soma == len(pontuado), "os dois estados precisam particionar"


class TestBaselinesHonestos:
    """Os baselines que as auditorias de 2026-08-25 exigiram."""

    def test_identidade_nao_pode_usar_o_futuro(self):
        """O erro que inverteu uma conclusão: baseline também tem fronteira.

        Uma primeira versão desta comparação usou a média do rótulo sobre o
        painel INTEIRO, incluindo os trimestres de teste. Marcou 0,8947 e
        "batia" o modelo. Corrigida para só o passado do fold, cai para 0,8012
        e o modelo a supera por +0,074 em 46/46 folds.
        """
        con = _painel_longo_variado(n_companhias=30)
        painel = construir_painel(con, trimestres_consecutivos=1)
        divisoes = dividir_walk_forward(painel)
        assert divisoes
        divisao = divisoes[-1]
        escore = escore_identidade_implementavel(divisao.treino, divisao.teste)
        # O escore de cada linha tem de ser reproduzível SÓ com o treino.
        esperado = divisao.treino.groupby("cd_cvm")["rotulo"].mean()
        padrao = float(divisao.treino["rotulo"].mean())
        for posicao, cd in enumerate(divisao.teste["cd_cvm"]):
            assert escore[posicao] == pytest.approx(
                float(esperado.get(cd, padrao))
            )

    def test_identidade_sem_historico_cai_na_taxa_base(self):
        con = _painel_longo_variado(n_companhias=20)
        painel = construir_painel(con, trimestres_consecutivos=1)
        divisao = dividir_walk_forward(painel)[-1]
        teste = divisao.teste.copy()
        teste.loc[:, "cd_cvm"] = "999999"  # companhia inexistente no treino
        escore = escore_identidade_implementavel(divisao.treino, teste)
        assert np.allclose(escore, float(divisao.treino["rotulo"].mean()))

    def test_taxa_recente_e_mais_granular_que_a_persistencia(self):
        """A persistência é binária e o AUC pune empate — daí o ganho inflado."""
        con = _painel_longo_variado(n_companhias=30)
        painel = construir_painel(con, trimestres_consecutivos=1)
        divisao = dividir_walk_forward(painel)[-1]
        assert len(np.unique(escore_persistencia(divisao.teste))) <= 2
        assert len(np.unique(escore_taxa_recente(divisao.teste))) > 2


class TestDecomposicao:
    """O par de números que impede ler o agregado como antecipação temporal."""

    def _pontuado(self):
        con = _painel_longo_variado(n_companhias=60)
        painel = construir_painel(con, trimestres_consecutivos=1)
        return pontuar_walk_forward(painel)

    def test_escore_constante_por_companhia_tem_within_meio(self):
        """A contraprova mais curta que existe do ponto.

        Um preditor que só codifica identidade não consegue ordenar nada DENTRO
        da companhia — o AUC intra-companhia dele é 0,5 por construção.
        """
        pontuado = self._pontuado()
        constante = pontuado.copy()
        mapa = {
            cd: i / max(1, pontuado["cd_cvm"].nunique())
            for i, cd in enumerate(sorted(pontuado["cd_cvm"].unique()))
        }
        constante["escore"] = constante["cd_cvm"].map(mapa)
        assert auc_within_companhia(constante)["auc"] == pytest.approx(0.5)

    def test_separa_ordenacao_entre_companhias_da_ordenacao_dentro_delas(self):
        """Caso construído: o escore ordena ao contrário DENTRO de cada companhia.

        Duas companhias, escores que separam A de B mas que, dentro de cada
        uma, põem o rótulo negativo acima do positivo. O AUC intra-companhia é
        0,0 e o agregado não vê isso — é a situação que o par de métricas
        existe para tornar visível.
        """
        quadro = pd.DataFrame(
            {
                "cd_cvm": ["A", "A", "B", "B"],
                "rotulo": [1, 0, 1, 0],
                "escore": [0.9, 0.95, 0.1, 0.15],
                "prejuizo_em_t": [1, 0, 1, 0],
                "taxa_prejuizos_4t": [1.0, 0.0, 1.0, 0.0],
            }
        )
        agregado = roc_auc_score(
            quadro["rotulo"].to_numpy(int), quadro["escore"].to_numpy(float)
        )
        dentro = auc_within_companhia(quadro)
        # Dentro de cada companhia o escore ordena ao CONTRÁRIO do rótulo.
        assert dentro["auc"] == pytest.approx(0.0)
        assert dentro["n_companhias"] == 2
        # E o agregado, que mistura pares entre companhias, não vê isso.
        assert agregado > dentro["auc"]

    def test_companhia_de_classe_unica_nao_entra(self):
        """Sem as duas classes não há par a ordenar; contar seria inventar."""
        quadro = pd.DataFrame(
            {
                "cd_cvm": ["A", "A", "B", "B"],
                "rotulo": [1, 1, 1, 0],
                "escore": [0.9, 0.1, 0.8, 0.2],
                "prejuizo_em_t": [1, 1, 1, 0],
                "taxa_prejuizos_4t": [1.0, 1.0, 1.0, 0.0],
            }
        )
        dentro = auc_within_companhia(quadro)
        assert dentro["n_companhias"] == 1
        assert dentro["n_pares"] == 1

    def test_funciona_no_painel_sintetico(self):
        pontuado = self._pontuado()
        dentro = auc_within_companhia(pontuado)
        assert dentro["auc"] is not None
        assert 0.0 <= dentro["auc"] <= 1.0
        assert dentro["n_companhias"] > 0

    def test_composicao_do_topo_traz_o_qualificador_do_lift(self):
        pontuado = self._pontuado()
        composicao = composicao_do_topo(pontuado)
        assert 0.0 <= composicao["ja_em_prejuizo_no_topo"] <= 1.0
        assert composicao["n_no_topo"] == max(1, round(len(pontuado) * 0.10))
        assert composicao["n_companhias_distintas_no_topo"] > 0


class TestRN07:
    """A fronteira que o módulo se impõe."""

    #: Tudo que participa de responder ao usuário.
    #:
    #: `src/projecao.py` está na lista mesmo sendo a rota que EXPÕE o escore no
    #: modo local — e é justamente por isso. Ela lê um artefato calculado
    #: offline (`artefatos/modelo/panorama.json` e, no modo local, os escores
    #: por companhia), nunca importa `src.modelo` em tempo de resposta. Assim a
    #: RN07 continua verificável por varredura de import mesmo depois de a
    #: regra ter virado condicional ao modo, e o deploy enxuto segue sem
    #: scikit-learn (RNF12).
    CAMINHO_INTERATIVO = (
        "src/agentes.py",
        "src/ferramentas.py",
        "src/braco_agente.py",
        "src/braco_determinista.py",
        "src/geracao.py",
        "src/recuperacao.py",
        "src/cobertura.py",
        "src/seguranca.py",
        "src/projecao.py",
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
