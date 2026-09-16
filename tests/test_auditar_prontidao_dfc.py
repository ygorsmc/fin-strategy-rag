"""Contraprovas sintéticas: auditoria estrutural não certifica ML nem PIT."""

from datetime import date

import duckdb
import pytest

from scripts.auditar_prontidao_dfc import auditar, auditar_csv_fco


@pytest.fixture
def con():
    with duckdb.connect() as banco:
        banco.execute("""
            CREATE TABLE fatos_contabeis (
                cd_cvm VARCHAR, conjunto VARCHAR, dt_refer DATE,
                versao_documento INTEGER, demonstrativo VARCHAR,
                origem VARCHAR, trimestre VARCHAR, tipo_periodo VARCHAR,
                dt_ini_exerc DATE, dt_fim_exerc DATE, cd_conta VARCHAR,
                ds_conta_norm VARCHAR, valor_reais DOUBLE
            );
            CREATE TABLE documentos (
                cd_cvm VARCHAR, conjunto VARCHAR, dt_refer DATE,
                versao INTEGER, dt_receb DATE
            );
            CREATE TABLE companhias (cd_cvm VARCHAR, setor VARCHAR);
            INSERT INTO companhias VALUES ('000001', NULL);
            INSERT INTO fatos_contabeis VALUES (
                '000001', 'itr', '2025-06-30', 2, 'DFC_MI', 'arquivado',
                '2T2025', 'acumulado', '2025-01-01', '2025-06-30', '6.01',
                'caixa liquido atividades operacionais', 100
            );
            INSERT INTO documentos VALUES
                ('000001', 'itr', '2025-06-30', 1, '2025-08-10'),
                ('000001', 'itr', '2025-06-30', 2, '2025-10-01');
        """)
        yield banco


def test_mesma_versao_nao_menor_data_do_formulario(con):
    r = auditar(con)
    assert r['recebimento']['recebidos_apos_decisao'] == 1
    assert r['recebimento']['com_recebimento_da_mesma_versao'] == 1
    assert r['vintages']['versoes_cadastradas_sem_fatos_dfc_retidos'] == 1
    assert r['certificacao_point_in_time'] == 'NAO_REALIZADA'
    assert r['modelo_treinado'] is False


def test_recebimento_ausente_nao_e_disponibilidade(con):
    con.execute('DELETE FROM documentos WHERE versao = 2')
    assert auditar(con)['recebimento']['sem_recebimento'] == 1


def test_recebimento_na_data_limite_nao_e_atrasado(con):
    con.execute("UPDATE documentos SET dt_receb='2025-09-30' WHERE versao=2")
    assert auditar(con)['recebimento']['recebidos_apos_decisao'] == 0


def test_codigo_sozinho_nao_resolve_conceito(con):
    con.execute("""UPDATE fatos_contabeis
        SET ds_conta_norm='caixa liquido atividades seguradora resseguradora'""")
    r = auditar(con)
    assert r['fco_codigo_e_descricao']['linhas'] == 0
    assert len(r['descricoes_codigo_6_01']) == 1
    assert r['certificacao_point_in_time'] != 'APROVADO'


def test_metodos_conflitantes_nao_sao_resolvidos_por_max(con):
    con.execute("""INSERT INTO fatos_contabeis
        SELECT * REPLACE ('DFC_MD' AS demonstrativo, 200 AS valor_reais)
        FROM fatos_contabeis""")
    r = auditar(con)['metodos_fco_mesmo_periodo']
    assert r['pares_mi_md'] == 1
    assert r['pares_mi_md_divergentes'] == 1


def test_duplicata_intrametodo_nao_desaparece(con):
    con.execute('INSERT INTO fatos_contabeis SELECT * FROM fatos_contabeis')
    assert auditar(con)['metodos_fco_mesmo_periodo'][
        'grupos_com_duplicata_intrametodo'] == 1


def test_semestre_mal_rotulado_trimestral_e_visivel(con):
    con.execute("""UPDATE fatos_contabeis
        SET tipo_periodo='trimestral', origem='derivado'""")
    assert auditar(con)['duracoes_fco_rotulado_trimestral'] == [
        {'origem': 'derivado', 'meses': 6, 'linhas': 1}
    ]


def test_dados_posteriores_ao_corte_nao_entram(con):
    antes = auditar(con)
    con.execute("""INSERT INTO fatos_contabeis
        SELECT * REPLACE (DATE '2026-06-30' AS dt_refer,
                          '2T2026' AS trimestre, 999999 AS valor_reais)
        FROM fatos_contabeis""")
    assert auditar(con) == antes
    with pytest.raises(ValueError, match='protegido'):
        auditar(con, date(2026, 6, 30))


def test_base_vazia_falha_fechado(con):
    con.execute('DELETE FROM fatos_contabeis')
    with pytest.raises(ValueError, match='Sem DFC'):
        auditar(con)


def test_auditor_so_leitura(con, tmp_path):
    destino = tmp_path / 'painel.duckdb'
    # Cria fixture em arquivo para testar a conexão read_only real.
    caminho_sql = str(destino).replace("'", "''")
    con.execute(f"ATTACH '{caminho_sql}' AS persistido")
    for tabela in ('fatos_contabeis', 'documentos', 'companhias'):
        con.execute(f'CREATE TABLE persistido.{tabela} AS SELECT * FROM {tabela}')
    con.execute('DETACH persistido')
    with duckdb.connect(str(destino), read_only=True) as leitura:
        assert auditar(leitura)['fco_codigo_e_descricao']['linhas'] == 1


def test_versoes_na_fonte_bruta_e_corte(tmp_path):
    fonte = tmp_path / 'dfc.csv'
    fonte.write_text(
        'CD_CVM;DT_REFER;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;ORDEM_EXERC;VERSAO\n'
        '1;2024-03-31;2024-01-01;2024-03-31;6.01;ÚLTIMO;1\n'
        '1;2024-03-31;2024-01-01;2024-03-31;6.01;ÚLTIMO;2\n'
        '1;2024-03-31;2023-01-01;2023-03-31;6.01;PENÚLTIMO;2\n'
        '1;2026-06-30;2026-01-01;2026-06-30;6.01;ÚLTIMO;1\n',
        encoding='latin-1',
    )
    r = auditar_csv_fco(fonte)
    assert r['chaves_codigo_6_01'] == 1
    assert r['chaves_com_multiplas_versoes'] == 1
    assert r['pares_chave_versao'] == 2
    assert len(r['sha256']) == 64


def test_fonte_sem_cabecalho_falha(tmp_path):
    fonte = tmp_path / 'dfc.csv'
    fonte.write_text('CD_CONTA\n6.01\n', encoding='latin-1')
    with pytest.raises(ValueError, match='campos'):
        auditar_csv_fco(fonte)
