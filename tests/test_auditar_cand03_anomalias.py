from __future__ import annotations

import inspect
import zipfile
from pathlib import Path

import duckdb

from scripts import auditar_cand03_anomalias as cand03


def _criar_painel_treino(caminho: Path) -> None:
    with duckdb.connect(str(caminho)) as con:
        con.execute(
            """
            CREATE TABLE fatos_contabeis (
                cd_cvm VARCHAR,
                conjunto VARCHAR,
                trimestre VARCHAR,
                demonstrativo VARCHAR,
                dt_refer DATE,
                ds_conta_norm VARCHAR,
                cd_conta VARCHAR,
                versao_documento INTEGER
            );
            CREATE TABLE companhias (
                cd_cvm VARCHAR,
                plano_contas VARCHAR,
                setor VARCHAR,
                ticker VARCHAR
            );
            CREATE TABLE mapa_contas (
                plano_contas VARCHAR,
                cd_conta VARCHAR,
                ds_conta_norm VARCHAR,
                conceito VARCHAR
            );
            CREATE TABLE fatos_semanticos (
                cd_cvm VARCHAR,
                trimestre VARCHAR,
                conceito VARCHAR,
                valor_reais DOUBLE
            );
            INSERT INTO companhias VALUES
                ('1', 'p1', 'energia', 'AAA3'),
                ('2', 'p2', NULL, NULL);
            INSERT INTO mapa_contas VALUES
                ('p1', '1', 'ativo total', 'ativo_total');
            INSERT INTO fatos_contabeis VALUES
                ('1', 'itr', '1T2025', 'BPA', DATE '2025-03-31',
                 'ativo total', '1', 1),
                ('1', 'itr', '1T2025', 'DRE', DATE '2025-03-31',
                 'lucro', '3', 1),
                ('2', 'itr', '1T2025', 'BPP', DATE '2025-03-31',
                 'passivo', '2', 2);
            INSERT INTO fatos_semanticos VALUES
                ('1', '1T2025', 'ativo_total', 100.0);
            """
        )


def _criar_painel_consulta(caminho: Path) -> None:
    with duckdb.connect(str(caminho)) as con:
        con.execute(
            """
            CREATE TABLE correcoes_contabeis (
                cd_cvm VARCHAR,
                trimestre VARCHAR,
                conceito VARCHAR
            );
            INSERT INTO correcoes_contabeis VALUES
                ('1', '3T2025', 'lucro_controladores'),
                ('1', '3T2025', 'lucro_nao_controladores'),
                ('1', '4T2025', 'lucro_controladores'),
                ('1', '4T2025', 'lucro_nao_controladores');
            """
        )


def test_linhas_corrigidas_nao_viram_quatro_rotulos_independentes(tmp_path):
    treino = tmp_path / "treino.duckdb"
    consulta = tmp_path / "consulta.duckdb"
    _criar_painel_treino(treino)
    _criar_painel_consulta(consulta)

    resultado = cand03.auditar(treino, consulta)
    e1 = resultado["estimandos"]["e1_erro_arquivamento"]

    assert e1["linhas_corrigidas"] == 4
    assert e1["emissores_com_correcao"] == 1
    assert e1["limite_superior_causas_raiz"] == 2
    assert e1["causas_raiz_confirmadas"] is None
    assert e1["gate_e1_aprovado"] is False


def test_sem_vintages_dfc_gold_e_tempo_falha_antes_do_modelo(tmp_path):
    treino = tmp_path / "treino.duckdb"
    consulta = tmp_path / "consulta.duckdb"
    _criar_painel_treino(treino)
    _criar_painel_consulta(consulta)

    resultado = cand03.auditar(treino, consulta)

    assert resultado["modelo_carregado"] is False
    assert resultado["estado_cientifico_ml"] == "INDECIDIVEL"
    assert resultado["decisao_de_engenharia_ml"] == "NAO_IMPLEMENTAR_AGORA"
    assert resultado["baseline_deterministico"] == "NAO_VALIDADO"
    assert not any(resultado["gates"].values())
    assert {
        "primeira_recepcao_e_vintages_ausentes",
        "dfc_ausente_do_painel",
        "gold_humano_e2_ausente",
        "estudo_humano_de_tempo_ausente",
    }.issubset(resultado["razoes"])


def test_auditor_nao_importa_biblioteca_ou_modulo_de_modelo():
    fonte = inspect.getsource(cand03)
    for proibido in (
        "sklearn",
        "torch",
        "sentence_transformers",
        "src.modelo",
        "IsolationForest",
    ):
        assert proibido not in fonte


def test_dt_receb_e_dfc_no_zip_nao_fingem_estar_no_painel(tmp_path):
    treino = tmp_path / "treino.duckdb"
    consulta = tmp_path / "consulta.duckdb"
    bruto = tmp_path / "bruto"
    bruto.mkdir()
    _criar_painel_treino(treino)
    _criar_painel_consulta(consulta)
    with zipfile.ZipFile(bruto / "itr_cia_aberta_2025.zip", "w") as arquivo:
        arquivo.writestr(
            "itr_cia_aberta_2025.csv",
            "CNPJ_CIA;DT_REFER;VERSAO;DT_RECEB\n",
        )
        arquivo.writestr(
            "itr_cia_aberta_DFC_MI_con_2025.csv",
            "CD_CVM;VL_CONTA\n",
        )

    resultado = cand03.auditar(
        treino,
        consulta,
        dir_cvm_bruto=bruto,
    )

    assert resultado["fontes_brutas"]["dt_receb_disponivel_na_fonte"] is True
    assert resultado["fontes_brutas"]["dfc_disponivel_na_fonte"] is True
    assert resultado["painel_treino"]["tem_data_primeira_recepcao"] is False
    assert resultado["painel_treino"]["tem_dfc"] is False
    assert resultado["gates"]["g0_observabilidade"] is False
