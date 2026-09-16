"""Contrato da camada de dados estruturados da CVM (spec 5.5).

Nenhum teste aqui depende de rede, de chave real ou do `.duckdb` construído com
os arquivos verdadeiros. As fixtures em `tests/fixtures/cvm/` reproduzem o
formato real (ISO-8859-1, separador `;`, decimal `.`) e contêm, de propósito,
**cada uma das seis armadilhas** confirmadas nos arquivos da CVM:

======================  ==========================================================
Armadilha               Como aparece na fixture
======================  ==========================================================
`VERSAO` republicada    BB, DT_REFER 2025-06-30, versões 1 e 2; a v1 traz valores
                        preliminares (+111.000) que não podem sobreviver
`ORDEM_EXERC`           todas as companhias têm linhas `PENÚLTIMO` (comparativo do
                        ano anterior) ao lado das `ÚLTIMO`
`ESCALA_MOEDA`          BB publica em `MIL`, BTG em `UNIDADE`, no mesmo painel
acumulado × isolado     DT_REFER 2025-06-30 tem 2025-01-01→06-30 (semestre) e
                        2025-04-01→06-30 (trimestre), com a mesma conta
`DT_REFER` fora do      HIDROVIAS DO BRASIL tem exercício social iniciando em
calendário civil        01/09 e DT_REFER 31/05 — que é seu 3º trimestre, não o 2º
seleção por nome        `BTG PACTUAL COMMODITIES SERTRADING` e `HIDROVIAS DO
                        BRASIL` casam os fragmentos "BTG" e "BRASIL"
======================  ==========================================================

E a armadilha central da RN09: `3.09` é o lucro líquido consolidado no BTG e o
*Lucro antes das Participações* no BB — número maior, não nulo e plausível.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from src import dados_estruturados
from src.config import TABELAS_PERMITIDAS_SQL, Config
from src.dados_estruturados import (
    ErroCargaCVM,
    FonteCabecalho,
    FonteCVM,
    PainelIndisponivelError,
    SqlBloqueadoError,
    carregar_painel,
    conferir_mapa_g4,
    executar_sql,
    lucro_por_banco,
    validar_sql,
)
from src.mapa_contas import (
    BANCOS_CORPUS,
    CONCEITO_ATIVO_TOTAL,
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_LUCRO_NAO_CONTROLADORES,
    CONCEITO_LUCRO_PADRAO,
    CONCEITO_PATRIMONIO_LIQUIDO,
    CONCEITO_RECEITA_INTERMEDIACAO,
    CONCEITOS_RECUSADOS,
    CONFERENCIA_G4,
    ContaObservada,
    ConflitoMapaContasError,
    assinatura_plano_contas,
    comparacao_cruza_quebra_4966,
    conceito_de_descricao,
    e_subconta_direta,
    normalizar_cd_cvm,
    normalizar_ds_conta,
    resolver_mapa_da_companhia,
)

DIR_FIXTURES = Path(__file__).parent / "fixtures" / "cvm"

CD_BB = "001023"
CD_BTG = "022616"
CD_SERTRADING = "027774"
CD_HIDROVIAS = "900001"


@pytest.fixture(scope="module")
def fontes() -> tuple[FonteCVM, ...]:
    return (
        FonteCVM(DIR_FIXTURES / "itr_cia_aberta_DRE_con_amostra.csv", "itr", "DRE"),
        FonteCVM(DIR_FIXTURES / "dfp_cia_aberta_DRE_con_amostra.csv", "dfp", "DRE"),
        FonteCVM(DIR_FIXTURES / "itr_cia_aberta_BPP_con_amostra.csv", "itr", "BPP"),
        FonteCVM(DIR_FIXTURES / "itr_cia_aberta_BPA_con_amostra.csv", "itr", "BPA"),
    )


@pytest.fixture(scope="module")
def painel(fontes, tmp_path_factory) -> tuple[Path, object]:
    destino = tmp_path_factory.mktemp("painel") / "cvm.duckdb"
    relatorio = carregar_painel(list(fontes), destino)
    return destino, relatorio


@pytest.fixture
def con(painel):
    caminho, _ = painel
    conexao = duckdb.connect(str(caminho), read_only=True)
    try:
        yield conexao
    finally:
        conexao.close()


# --------------------------------------------------------------------------- #
# Normalização e resolução de conceito (camada pura)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("Lucro/Prejuízo Consolidado do Período", "lucro prejuizo consolidado do periodo"),
        ("Atribuído aos Sócios da Empresa Controladora", "atribuido aos socios da empresa controladora"),
        ("Patrimônio Líquido Consolidado", "patrimonio liquido consolidado"),
        ("  Ativo   Total  ", "ativo total"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalizar_ds_conta(bruto, esperado):
    assert normalizar_ds_conta(bruto) == esperado


@pytest.mark.parametrize(
    "descricao,conceito",
    [
        ("Lucro ou Prejuízo Líquido Consolidado do Período", CONCEITO_LUCRO_CONSOLIDADO),
        ("Lucro/Prejuízo Consolidado do Período", CONCEITO_LUCRO_CONSOLIDADO),
        ("Atribuído aos Sócios da Empresa Controladora", CONCEITO_LUCRO_CONTROLADORES),
        ("Atribuído a Sócios da Empresa Controladora", CONCEITO_LUCRO_CONTROLADORES),
        ("Atribuído aos Sócios não Controladores", CONCEITO_LUCRO_NAO_CONTROLADORES),
        ("Atribuído a Sócios Não Controladores", CONCEITO_LUCRO_NAO_CONTROLADORES),
        ("Receitas de Intermediação Financeira", CONCEITO_RECEITA_INTERMEDIACAO),
        ("Receitas da Intermediação Financeira", CONCEITO_RECEITA_INTERMEDIACAO),
        ("Patrimônio Líquido Consolidado", CONCEITO_PATRIMONIO_LIQUIDO),
        ("Ativo Total", CONCEITO_ATIVO_TOTAL),
    ],
)
def test_conceito_de_descricao_resolve_as_variantes_reais(descricao, conceito):
    assert conceito_de_descricao(descricao) == conceito


@pytest.mark.parametrize(
    "descricao",
    [
        # A armadilha central: linha ANTERIOR ao resultado final, no BB/Bradesco.
        "Lucro ou Prejuízo antes das Participações e Contribuições Estatutárias",
        "Lucro ou Prejuízo das Operações Continuadas",
        "Resultado Líquido das Operações Continuadas",
        "Resultado Líquido das Operações Descontinuadas",
        "Lucro/Prejuízo Líquido das Operações Descontinuadas",
        "Lucro Básico por Ação",
        "Lucro Diluído por Ação",
        "Lucro por Ação - (R$ / Ação)",
        "Participações nos Lucros e Contribuições Estatutárias",
        "Provisões",
        "Passivos Financeiros ao Custo Amortizado",
    ],
)
def test_conceito_de_descricao_recusa_linhas_vizinhas(descricao):
    """Nenhuma linha vizinha do lucro pode ser confundida com ele."""
    assert conceito_de_descricao(descricao) not in {
        CONCEITO_LUCRO_CONSOLIDADO,
        CONCEITO_LUCRO_CONTROLADORES,
        CONCEITO_LUCRO_NAO_CONTROLADORES,
        CONCEITO_PATRIMONIO_LIQUIDO,
    }


@pytest.mark.parametrize(
    "filho,pai,esperado",
    [
        ("3.09.01", "3.09", True),
        ("3.11.01", "3.11", True),
        ("3.09.01", "3.11", False),
        ("3.11.01", "3.09", False),
        ("3.09.01.01", "3.09", False),
        ("3.09", "3.09", False),
        ("3.091", "3.09", False),
    ],
)
def test_e_subconta_direta(filho, pai, esperado):
    assert e_subconta_direta(filho, pai) is esperado


def test_guarda_estrutural_rejeita_controladores_de_outro_plano():
    """`3.09.01` não vale como controladores se o lucro está em `3.11`.

    É a guarda que impede o mapa de casar a subconta certa com o pai errado
    quando uma companhia publica ambos os códigos.
    """
    entradas = resolver_mapa_da_companhia(
        [
            ContaObservada("3.11", "Lucro ou Prejuízo Líquido Consolidado do Período"),
            ContaObservada("3.11.01", "Atribuído aos Sócios da Empresa Controladora"),
            ContaObservada("3.09.01", "Atribuído a Sócios da Empresa Controladora"),
        ]
    )
    controladores = {
        e.cd_conta for e in entradas if e.conceito == CONCEITO_LUCRO_CONTROLADORES
    }
    assert controladores == {"3.11.01"}


def test_resolver_mapa_recusa_conflito_de_codigo():
    with pytest.raises(ConflitoMapaContasError):
        resolver_mapa_da_companhia(
            [
                ContaObservada("3.11", "Lucro ou Prejuízo Líquido Consolidado do Período"),
                ContaObservada("3.11", "Ativo Total"),
            ]
        )


def test_assinatura_do_plano_separa_3_09_de_3_11():
    plano_bb = assinatura_plano_contas(
        resolver_mapa_da_companhia(
            [
                ContaObservada("3.11", "Lucro ou Prejuízo Líquido Consolidado do Período"),
                ContaObservada("3.11.01", "Atribuído aos Sócios da Empresa Controladora"),
            ]
        )
    )
    plano_btg = assinatura_plano_contas(
        resolver_mapa_da_companhia(
            [
                ContaObservada("3.09", "Lucro/Prejuízo Consolidado do Período"),
                ContaObservada("3.09.01", "Atribuído a Sócios da Empresa Controladora"),
            ]
        )
    )
    assert plano_bb != plano_btg
    assert plano_bb.startswith("ll3_11_")
    assert plano_btg.startswith("ll3_09_")


def test_lucro_padrao_e_o_dos_controladores():
    """Convenção de mercado: "lucro líquido do banco" = atribuído aos controladores."""
    assert CONCEITO_LUCRO_PADRAO == CONCEITO_LUCRO_CONTROLADORES


def test_conceitos_recusados_tem_motivo_declarado():
    """Ausência de conceito é decisão documentada, não esquecimento."""
    assert "provisao_perda_esperada_credito" in CONCEITOS_RECUSADOS
    for motivo in CONCEITOS_RECUSADOS.values():
        assert len(motivo) > 80


@pytest.mark.parametrize(
    "bruto,esperado", [("1023", "001023"), ("001023", "001023"), (1023, "001023")]
)
def test_normalizar_cd_cvm(bruto, esperado):
    assert normalizar_cd_cvm(bruto) == esperado


def test_normalizar_cd_cvm_recusa_texto():
    with pytest.raises(ValueError):
        normalizar_cd_cvm("BCO BRASIL")


@pytest.mark.parametrize(
    "a,b,esperado",
    [
        ("4T2024", "1T2025", True),
        ("3T2024", "3T2025", True),
        ("1T2025", "4T2025", False),
        ("2T2025", "1T2026", False),
        ("1T2023", "4T2024", False),
    ],
)
def test_quebra_de_serie_cmn_4966(a, b, esperado):
    """Comparação que atravessa 01/01/2025 cruza duas contabilidades."""
    assert comparacao_cruza_quebra_4966(a, b) is esperado


def test_bancos_do_corpus_sao_selecionados_por_cd_cvm():
    cds = {b.cd_cvm for b in BANCOS_CORPUS}
    assert cds == {"001023", "000906", "022616", "019348", "020532"}
    assert len({b.banco for b in BANCOS_CORPUS}) == 5


# --------------------------------------------------------------------------- #
# Carga — as seis regras de armadilha, com contagem
# --------------------------------------------------------------------------- #


def test_carga_reporta_as_seis_regras(painel):
    _, relatorio = painel
    chaves = [regra.chave for regra in relatorio.regras]
    assert chaves == [
        "ordem_exerc_penultimo",
        "versao_republicada",
        "escala_moeda_convertida",
        "periodo_nao_trimestral",
        "trimestre_corrigido",
        "homonimo_por_nome",
    ]
    for regra in relatorio.regras:
        assert regra.linhas_afetadas > 0, f"{regra.chave} não exercitada na fixture"
        assert regra.descricao


def test_contagens_exatas_por_regra(painel):
    """As contagens são o contrato: mudou o número, mudou a regra."""
    _, relatorio = painel
    assert relatorio.linhas_lidas == 103
    assert relatorio.regra("ordem_exerc_penultimo").linhas_afetadas == 32
    assert relatorio.regra("versao_republicada").linhas_afetadas == 10
    assert relatorio.regra("escala_moeda_convertida").linhas_afetadas == 41
    assert relatorio.regra("periodo_nao_trimestral").linhas_afetadas == 25
    assert relatorio.regra("trimestre_corrigido").linhas_afetadas == 4
    assert relatorio.regra("homonimo_por_nome").linhas_afetadas == 7
    assert relatorio.companhias == 4
    assert relatorio.linhas_carregadas == 66


def test_penultimo_nao_entra_no_painel(con):
    """`PENÚLTIMO` é o comparativo do ano anterior — e está do lado velho da
    quebra da Resolução CMN 4.966. Nenhuma linha de 2024 pode ter sobrevivido."""
    anteriores = con.execute(
        "SELECT count(*) FROM fatos_contabeis WHERE year(dt_fim_exerc) < 2025"
    ).fetchone()[0]
    assert anteriores == 0


def test_versao_republicada_vence_a_preliminar(con):
    """O 2T do BB foi republicado: só a versão 2 pode estar no painel."""
    linhas = con.execute(
        """
        SELECT DISTINCT versao_documento
        FROM fatos_contabeis
        WHERE cd_cvm = ? AND dt_refer = DATE '2025-06-30'
        """,
        [CD_BB],
    ).fetchall()
    assert [linha[0] for linha in linhas] == [2]

    # o valor preliminar (+111.000 mil) não pode aparecer em lugar nenhum
    preliminar = con.execute(
        "SELECT count(*) FROM fatos_contabeis WHERE valor_reais = ?",
        [(3_500_000 + 111_000) * 1000.0],
    ).fetchone()[0]
    assert preliminar == 0


def test_escala_convertida_para_reais(con):
    """BB publica em MIL e BTG em UNIDADE; ambos saem em reais."""
    bb = con.execute(
        """
        SELECT valor_reais FROM fatos_semanticos
        WHERE cd_cvm = ? AND trimestre = '1T2025' AND conceito = ?
        """,
        [CD_BB, CONCEITO_LUCRO_CONSOLIDADO],
    ).fetchone()[0]
    btg = con.execute(
        """
        SELECT valor_reais FROM fatos_semanticos
        WHERE cd_cvm = ? AND trimestre = '1T2025' AND conceito = ?
        """,
        [CD_BTG, CONCEITO_LUCRO_CONSOLIDADO],
    ).fetchone()[0]
    assert bb == pytest.approx(3_000_000 * 1000.0)
    assert btg == pytest.approx(4_900_000_000.0)


def test_trimestre_isolado_nao_e_o_acumulado(con):
    """O 2T é R$ 3,5 bi (trimestre), não R$ 6,5 bi (semestre acumulado)."""
    valor = con.execute(
        """
        SELECT valor_reais FROM fatos_semanticos
        WHERE cd_cvm = ? AND trimestre = '2T2025' AND conceito = ?
        """,
        [CD_BB, CONCEITO_LUCRO_CONSOLIDADO],
    ).fetchall()
    assert len(valor) == 1
    assert valor[0][0] == pytest.approx(3_500_000 * 1000.0)

    # o acumulado continua auditável na tabela crua, fora da visão semântica
    acumulado = con.execute(
        """
        SELECT valor_reais FROM fatos_contabeis
        WHERE cd_cvm = ? AND trimestre = '2T2025' AND cd_conta = '3.11'
          AND tipo_periodo = 'acumulado'
        """,
        [CD_BB],
    ).fetchone()[0]
    assert acumulado == pytest.approx(6_500_000 * 1000.0)


def test_trimestre_vem_do_intervalo_nao_do_mes_de_dt_refer(con):
    """Exercício social iniciando em 01/09: DT_REFER 31/05 é o 3º trimestre.

    Derivar do mês de `DT_REFER` daria `2T2025` — rótulo errado, sem erro.
    """
    linhas = con.execute(
        """
        SELECT DISTINCT trimestre FROM fatos_contabeis
        WHERE cd_cvm = ? ORDER BY trimestre
        """,
        [CD_HIDROVIAS],
    ).fetchall()
    assert [linha[0] for linha in linhas] == ["3T2025"]


def test_homonimos_nao_viram_bancos_do_corpus(con):
    """`BTG PACTUAL COMMODITIES SERTRADING` e `HIDROVIAS DO BRASIL` existem no
    painel como companhias próprias — e nenhuma delas é um banco do corpus."""
    homonimos = con.execute(
        "SELECT cd_cvm, is_banco FROM companhias WHERE cd_cvm IN (?, ?) ORDER BY cd_cvm",
        [CD_SERTRADING, CD_HIDROVIAS],
    ).fetchall()
    assert homonimos == [(CD_SERTRADING, False), (CD_HIDROVIAS, False)]

    denominacoes = con.execute(
        "SELECT denom_social FROM companhias WHERE is_banco ORDER BY cd_cvm"
    ).fetchall()
    assert [d[0] for d in denominacoes] == [
        "BCO BRASIL S.A.",
        "BCO BTG PACTUAL S.A.",
    ]


# --------------------------------------------------------------------------- #
# RN09 — cd_conta não é chave de significado
# --------------------------------------------------------------------------- #


def test_consulta_ingenua_por_cd_conta_devolve_numero_errado_e_nao_nulo(con):
    """Prova da armadilha, dentro da suíte.

    `WHERE cd_conta = '3.09'` devolve o lucro do BTG e, no BB, o *Lucro antes
    das Participações* — maior, não nulo e sem nenhum sinal de erro. É o que a
    camada semântica existe para impedir.
    """
    ingenuo = dict(
        con.execute(
            """
            SELECT cd_cvm, valor_reais FROM fatos_contabeis
            WHERE cd_conta = '3.09' AND trimestre = '1T2025'
              AND tipo_periodo = 'trimestral'
            """
        ).fetchall()
    )
    semantico = dict(
        con.execute(
            """
            SELECT cd_cvm, valor_reais FROM fatos_semanticos
            WHERE conceito = ? AND trimestre = '1T2025'
            """,
            [CONCEITO_LUCRO_CONSOLIDADO],
        ).fetchall()
    )
    # no BTG o código coincide com o conceito...
    assert ingenuo[CD_BTG] == semantico[CD_BTG]
    # ...e no BB devolve outro número, maior e não nulo
    assert ingenuo[CD_BB] is not None
    assert ingenuo[CD_BB] != semantico[CD_BB]
    assert ingenuo[CD_BB] > semantico[CD_BB]


def test_mapa_resolve_codigos_diferentes_para_o_mesmo_conceito(con):
    linhas = con.execute(
        """
        SELECT c.cd_cvm, m.cd_conta
        FROM companhias AS c
        JOIN mapa_contas AS m ON m.plano_contas = c.plano_contas
        WHERE m.conceito = ? AND c.cd_cvm IN (?, ?)
        ORDER BY c.cd_cvm
        """,
        [CONCEITO_LUCRO_CONSOLIDADO, CD_BB, CD_BTG],
    ).fetchall()
    assert linhas == [(CD_BB, "3.11"), (CD_BTG, "3.09")]


def test_mesma_armadilha_no_balanco_patrimonial(con):
    """`2.03` é *Provisões* no BB e *Passivos ao Custo Amortizado* no BTG; o
    patrimônio líquido está em `2.07` num e `2.08` no outro."""
    linhas = con.execute(
        """
        SELECT c.cd_cvm, m.cd_conta
        FROM companhias AS c
        JOIN mapa_contas AS m ON m.plano_contas = c.plano_contas
        WHERE m.conceito = ? ORDER BY c.cd_cvm
        """,
        [CONCEITO_PATRIMONIO_LIQUIDO],
    ).fetchall()
    assert linhas == [(CD_BB, "2.07"), (CD_BTG, "2.08")]

    # e `2.03` nunca foi promovido a conceito nenhum
    promovido = con.execute(
        "SELECT count(*) FROM mapa_contas WHERE cd_conta = '2.03'"
    ).fetchone()[0]
    assert promovido == 0


def test_grao_da_visao_semantica_e_unico(con):
    """Uma linha por companhia × trimestre × conceito — sem duplicar acumulado."""
    duplicados = con.execute(
        """
        SELECT count(*) FROM (
            SELECT cd_cvm, trimestre, conceito
            FROM fatos_semanticos
            GROUP BY cd_cvm, trimestre, conceito
            HAVING count(*) > 1
        )
        """
    ).fetchone()[0]
    assert duplicados == 0


def test_visao_semantica_nao_expoe_cd_conta(con):
    colunas = {
        linha[0]
        for linha in con.execute("DESCRIBE fatos_semanticos").fetchall()
    }
    assert "cd_conta" not in colunas
    assert {"cd_cvm", "trimestre", "conceito", "valor_reais", "origem"} <= colunas


# --------------------------------------------------------------------------- #
# RN10 — o 4º trimestre é derivado, e diz que é
# --------------------------------------------------------------------------- #


def test_quarto_trimestre_e_derivado_por_subtracao(con, painel):
    """DFP anual (16.500.000) − ITR acumulado 3T (10.500.000) = 6.000.000 mil."""
    _, relatorio = painel
    assert relatorio.fatos_derivados_4t == 5

    linha = con.execute(
        """
        SELECT valor_reais, origem FROM fatos_semanticos
        WHERE cd_cvm = ? AND trimestre = '4T2025' AND conceito = ?
        """,
        [CD_BB, CONCEITO_LUCRO_CONSOLIDADO],
    ).fetchall()
    assert len(linha) == 1
    valor, origem = linha[0]
    assert valor == pytest.approx((16_500_000 - 10_500_000) * 1000.0)
    assert origem == "derivado"


def test_sem_par_de_derivacao_nao_ha_quarto_trimestre(con):
    """O BTG tem DFP anual mas não tem o acumulado de 9M nesta amostra.

    A resposta correta é não existir a linha — nunca inventar o número a partir
    do anual sozinho.
    """
    linhas = con.execute(
        "SELECT count(*) FROM fatos_semanticos WHERE cd_cvm = ? AND trimestre = '4T2025'",
        [CD_BTG],
    ).fetchone()[0]
    assert linhas == 0


def test_anual_nao_vaza_como_trimestre_na_visao(con):
    """A linha anual segue em `fatos_contabeis`, mas nunca em `fatos_semanticos`."""
    tipos = con.execute(
        "SELECT DISTINCT tipo_periodo FROM fatos_semanticos ORDER BY tipo_periodo"
    ).fetchall()
    assert [t[0] for t in tipos] == ["instantaneo", "trimestral"]

    anual = con.execute(
        "SELECT count(*) FROM fatos_contabeis WHERE tipo_periodo = 'anual'"
    ).fetchone()[0]
    assert anual > 0


def test_indicadores_derivam_de_fatos_semanticos(con):
    linha = con.execute(
        """
        SELECT lucro_liquido_consolidado, patrimonio_liquido, ativo_total,
               roe_trimestral, alavancagem, origem
        FROM indicadores
        WHERE cd_cvm = ? AND trimestre = '1T2025'
        """,
        [CD_BB],
    ).fetchone()
    lucro, pl, ativo, roe, alavancagem, origem = linha
    assert lucro == pytest.approx(3_000_000 * 1000.0)
    assert pl == pytest.approx(200_000_000 * 1000.0)
    assert roe == pytest.approx(lucro / pl)
    assert alavancagem == pytest.approx(ativo / pl)
    assert origem == "arquivado"


def test_indicadores_marcam_origem_derivada(con):
    origem = con.execute(
        "SELECT origem FROM indicadores WHERE cd_cvm = ? AND trimestre = '4T2025'",
        [CD_BB],
    ).fetchone()[0]
    assert origem == "derivado"


def test_lucro_por_banco_expoe_as_duas_leituras(painel):
    caminho, _ = painel
    linhas = lucro_por_banco(caminho, trimestres=["1T2025"])
    por_banco = {linha[0]: linha for linha in linhas}
    assert set(por_banco) == {"BB", "BTG"}

    _, _, _, consolidado_bb, controladores_bb, delta_bb = por_banco["BB"]
    assert consolidado_bb > controladores_bb
    assert delta_bb == pytest.approx(-23.0, abs=0.5)

    _, _, _, consolidado_btg, controladores_btg, delta_btg = por_banco["BTG"]
    assert consolidado_btg > controladores_btg
    assert delta_btg == pytest.approx(-3.5, abs=0.5)


# --------------------------------------------------------------------------- #
# Gate G4
# --------------------------------------------------------------------------- #


def test_g4_aprova_o_mapa_das_companhias_presentes(painel):
    caminho, _ = painel
    conferencia = {
        cd: dict(CONFERENCIA_G4[cd]) for cd in (CD_BB, CD_BTG)
    }
    resultado = conferir_mapa_g4(caminho, conferencia)
    assert resultado.aprovado, resultado.divergencias
    assert resultado.resolvido[CD_BB][CONCEITO_LUCRO_CONSOLIDADO] == {"3.11"}
    assert resultado.resolvido[CD_BTG][CONCEITO_LUCRO_CONSOLIDADO] == {"3.09"}


def test_g4_reprova_se_3_09_e_3_11_forem_tratados_como_equivalentes(painel):
    """Se alguém "consertar" o mapa trocando o código, o gate tem de barrar."""
    caminho, _ = painel
    conferencia = {CD_BB: {CONCEITO_LUCRO_CONSOLIDADO: "3.09"}}
    resultado = conferir_mapa_g4(caminho, conferencia)
    assert not resultado.aprovado
    assert any("3.11" in d and "3.09" in d for d in resultado.divergencias)


def test_g4_reprova_companhia_ausente(painel):
    caminho, _ = painel
    resultado = conferir_mapa_g4(caminho, {"000906": {CONCEITO_LUCRO_CONSOLIDADO: "3.11"}})
    assert not resultado.aprovado
    assert "ausente" in resultado.divergencias[0]


def test_conferencia_g4_cobre_os_cinco_bancos():
    assert set(CONFERENCIA_G4) == {b.cd_cvm for b in BANCOS_CORPUS}
    codigos = {
        cd: conceitos[CONCEITO_LUCRO_CONSOLIDADO]
        for cd, conceitos in CONFERENCIA_G4.items()
    }
    assert codigos["001023"] == ("3.11",)  # Banco do Brasil
    assert codigos["000906"] == ("3.11",)  # Bradesco
    assert codigos["022616"] == ("3.09",)  # BTG
    assert codigos["019348"] == ("3.09",)  # Itaú
    # Santander publica os DOIS: 3.09 no ITR e 3.11 na DFP de 2025
    # (achado de 2026-08-10, medido nos arquivos reais).
    assert codigos["020532"] == ("3.09", "3.11")


# --------------------------------------------------------------------------- #
# Guardas de SQL (RN04)
# --------------------------------------------------------------------------- #


@pytest.fixture
def config() -> Config:
    return Config()


def test_consulta_valida_passa(config):
    sql = (
        "SELECT cd_cvm, trimestre, valor_reais FROM fatos_semanticos "
        "WHERE conceito = 'lucro_liquido_controladores' LIMIT 10"
    )
    assert validar_sql(sql, config) == sql


@pytest.mark.parametrize(
    "sql,motivo",
    [
        ("DROP TABLE companhias", "DDL"),
        ("DELETE FROM companhias LIMIT 1", "DML"),
        ("UPDATE companhias SET setor = 'x' LIMIT 1", "DML"),
        ("INSERT INTO companhias VALUES (1) LIMIT 1", "DML"),
        ("SELECT 1; DROP TABLE companhias", "duas instruções"),
        ("SELECT * FROM companhias LIMIT 5 -- comentário", "comentário"),
        ("SELECT /* oculto */ * FROM companhias LIMIT 5", "comentário"),
        ("ATTACH 'outro.db' AS x", "attach"),
        ("PRAGMA database_list", "pragma"),
        ("SELECT * FROM fatos_contabeis LIMIT 5", "tabela fora da lista branca"),
        ("SELECT * FROM read_csv('/etc/passwd') LIMIT 5", "função de tabela"),
        ("SELECT * FROM information_schema.tables LIMIT 5", "catálogo"),
        ("SELECT * FROM main.companhias LIMIT 5", "nome qualificado"),
        ("SELECT * FROM companhias", "sem LIMIT"),
        ("SELECT * FROM companhias LIMIT 5000", "LIMIT acima do teto"),
        ("SELECT * FROM companhias LIMIT 0", "LIMIT não positivo"),
        ("SELECT cd_conta FROM mapa_contas LIMIT 5", "cd_conta"),
        ("SELECT * FROM fatos_semanticos WHERE cd_conta = '3.09' LIMIT 5", "cd_conta"),
        ("", "vazia"),
        ("   ", "vazia"),
    ],
)
def test_guardas_bloqueiam_antes_de_executar(sql, motivo, config):
    with pytest.raises(SqlBloqueadoError):
        validar_sql(sql, config)


def test_fatos_contabeis_esta_fora_da_lista_branca():
    """A tabela crua não é consultável pelo agente — só a visão semântica."""
    assert "fatos_contabeis" not in TABELAS_PERMITIDAS_SQL
    assert "fatos_semanticos" in TABELAS_PERMITIDAS_SQL


def test_with_e_alias_sao_aceitos(config):
    sql = (
        "WITH base AS (SELECT cd_cvm, valor_reais FROM fatos_semanticos LIMIT 10) "
        "SELECT cd_cvm FROM base LIMIT 5"
    )
    assert validar_sql(sql, config) == sql


def test_cte_nao_abre_caminho_para_tabela_proibida(config):
    """Aceitar o nome da CTE em FROM não pode aceitar o que ela lê."""
    with pytest.raises(SqlBloqueadoError):
        validar_sql(
            "WITH base AS (SELECT * FROM fatos_contabeis LIMIT 5) "
            "SELECT * FROM base LIMIT 5",
            config,
        )


def test_alias_nao_disfarca_funcao_de_tabela(config):
    with pytest.raises(SqlBloqueadoError):
        validar_sql(
            "SELECT * FROM read_csv('/etc/passwd') AS companhias LIMIT 5", config
        )


def test_join_entre_tabelas_permitidas(config):
    sql = (
        "SELECT c.denom_social, f.valor_reais FROM fatos_semanticos AS f "
        "JOIN companhias AS c ON c.cd_cvm = f.cd_cvm LIMIT 20"
    )
    assert validar_sql(sql, config) == sql


def test_literal_com_ponto_e_virgula_nao_burla_a_guarda(config):
    with pytest.raises(SqlBloqueadoError):
        validar_sql(
            "SELECT * FROM companhias WHERE setor = 'a'; DROP TABLE companhias' LIMIT 5",
            config,
        )


def test_executar_sql_devolve_o_sql_junto_do_resultado(painel, config):
    """SQL gerado por modelo é verificável quando fica visível (RN01)."""
    caminho, _ = painel
    sql = (
        "SELECT cd_cvm, valor_reais FROM fatos_semanticos "
        "WHERE conceito = 'lucro_liquido_consolidado' AND trimestre = '1T2025' "
        "ORDER BY cd_cvm LIMIT 10"
    )
    resultado = executar_sql(sql, config, caminho)
    assert resultado.sql == sql
    assert resultado.colunas == ("cd_cvm", "valor_reais")
    # HIDROVIAS não aparece: seu 1º trimestre fiscal não é `1T2025`.
    assert [linha[0] for linha in resultado.linhas] == [
        CD_BB,
        CD_BTG,
        CD_SERTRADING,
    ]
    assert resultado.total_linhas == 3


def test_executar_sql_bloqueado_nao_toca_no_banco(painel, config):
    caminho, _ = painel
    with pytest.raises(SqlBloqueadoError):
        executar_sql("SELECT * FROM fatos_contabeis LIMIT 5", config, caminho)


def test_conexao_e_somente_leitura(painel, config):
    """Mesmo uma escrita que passasse pela análise sintática morre na conexão."""
    caminho, _ = painel
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        with pytest.raises(duckdb.Error):
            con.execute("DELETE FROM companhias")
    finally:
        con.close()


def test_painel_ausente_falha_claro(tmp_path, config):
    with pytest.raises(PainelIndisponivelError):
        executar_sql(
            "SELECT cd_cvm FROM companhias LIMIT 1", config, tmp_path / "nao_existe.duckdb"
        )


# --------------------------------------------------------------------------- #
# Carga — erros
# --------------------------------------------------------------------------- #


def test_carga_sem_fontes_falha(tmp_path):
    with pytest.raises(ErroCargaCVM):
        carregar_painel([], tmp_path / "cvm.duckdb")


def test_carga_com_fonte_inexistente_falha(tmp_path):
    with pytest.raises(ErroCargaCVM):
        carregar_painel(
            [FonteCVM(tmp_path / "nao_existe.csv", "itr", "DRE")],
            tmp_path / "cvm.duckdb",
        )


def test_fonte_recusa_conjunto_desconhecido(tmp_path):
    with pytest.raises(ValueError):
        FonteCVM(tmp_path / "x.csv", "fre", "DRE")


def test_fonte_recusa_demonstrativo_desconhecido(tmp_path):
    with pytest.raises(ValueError):
        FonteCVM(tmp_path / "x.csv", "itr", "DMPL")


def test_escala_desconhecida_interrompe_a_carga(tmp_path):
    """Converter escala desconhecida às cegas somaria grandezas diferentes."""
    origem = (DIR_FIXTURES / "itr_cia_aberta_DRE_con_amostra.csv").read_text(
        encoding="iso-8859-1"
    )
    adulterado = origem.replace(";MIL;", ";CENTENA;", 1)
    caminho = tmp_path / "escala_ruim.csv"
    caminho.write_text(adulterado, encoding="iso-8859-1")
    with pytest.raises(ErroCargaCVM, match="ESCALA_MOEDA"):
        carregar_painel([FonteCVM(caminho, "itr", "DRE")], tmp_path / "cvm.duckdb")


def test_cabecalho_incompleto_interrompe_a_carga(tmp_path):
    caminho = tmp_path / "sem_colunas.csv"
    caminho.write_text("CNPJ_CIA;DT_REFER\n1;2025-03-31\n", encoding="iso-8859-1")
    with pytest.raises(ErroCargaCVM, match="colunas ausentes"):
        carregar_painel([FonteCVM(caminho, "itr", "DRE")], tmp_path / "cvm.duckdb")


def test_filtro_por_cd_cvm_restringe_o_painel(fontes, tmp_path):
    """RN11: a seleção é por código; os homônimos simplesmente não entram."""
    destino = tmp_path / "so_bancos.duckdb"
    carregar_painel(list(fontes), destino, cd_cvm_permitidos=[CD_BB, CD_BTG])
    con = duckdb.connect(str(destino), read_only=True)
    try:
        cds = [
            linha[0]
            for linha in con.execute(
                "SELECT cd_cvm FROM companhias ORDER BY cd_cvm"
            ).fetchall()
        ]
    finally:
        con.close()
    assert cds == [CD_BB, CD_BTG]


def test_carga_falha_nao_deixa_banco_pela_metade(tmp_path):
    caminho = tmp_path / "vazio.csv"
    caminho.write_text("CNPJ_CIA;DT_REFER\n", encoding="iso-8859-1")
    destino = tmp_path / "cvm.duckdb"
    with pytest.raises(ErroCargaCVM):
        carregar_painel([FonteCVM(caminho, "itr", "DRE")], destino)
    assert not destino.exists()


# --------------------------------------------------------------------------- #
# Download e manifesto (risco 15d) — nenhum teste toca a rede
# --------------------------------------------------------------------------- #

from scripts.baixar_cvm import (  # noqa: E402
    COLUNAS_MANIFESTO,
    baixar_cvm,
    extrair_csvs,
    ler_manifesto,
    membros_desejados,
    nome_do_arquivo,
    salvar_manifesto,
    sha256_do_arquivo,
    url_do_conjunto,
    validar_url,
    validar_zip,
)


def _zip_cvm(destino: Path, membros: dict[str, bytes] | None = None) -> Path:
    """ZIP mínimo no formato do portal, para exercitar as guardas sem rede."""
    conteudo = membros or {
        "itr_cia_aberta_2025.csv": b"CNPJ_CIA;DT_REFER\n",
        "itr_cia_aberta_DRE_con_2025.csv": b"CNPJ_CIA;DT_REFER\n",
        "itr_cia_aberta_BPA_con_2025.csv": b"CNPJ_CIA;DT_REFER\n",
        "itr_cia_aberta_BPP_con_2025.csv": b"CNPJ_CIA;DT_REFER\n",
        "itr_cia_aberta_DRE_ind_2025.csv": b"CNPJ_CIA;DT_REFER\n",
    }
    import zipfile

    with zipfile.ZipFile(destino, "w") as pacote:
        for nome, dados in conteudo.items():
            pacote.writestr(nome, dados)
    return destino


@pytest.mark.parametrize(
    "conjunto,ano,esperado",
    [
        (
            "itr",
            2025,
            "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/"
            "itr_cia_aberta_2025.zip",
        ),
        (
            "dfp",
            2025,
            "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/"
            "dfp_cia_aberta_2025.zip",
        ),
    ],
)
def test_url_oficial_do_conjunto(conjunto, ano, esperado):
    assert url_do_conjunto(conjunto, ano) == esperado


@pytest.mark.parametrize(
    "conjunto,ano",
    [("fre", 2025), ("itr", 1999), ("itr", 2101), ("itr", True)],
)
def test_url_recusa_parametro_invalido(conjunto, ano):
    with pytest.raises(ValueError):
        url_do_conjunto(conjunto, ano)


@pytest.mark.parametrize(
    "url",
    [
        "http://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/x.zip",
        "https://exemplo.invalido/dados/CIA_ABERTA/DOC/ITR/DADOS/x.zip",
        "https://user:senha@dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/x.zip",
        "https://dados.cvm.gov.br/outro/caminho/x.zip",
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/x.zip?token=1",
        "https://dados.cvm.gov.br:8443/dados/CIA_ABERTA/DOC/ITR/DADOS/x.zip",
    ],
)
def test_validar_url_recusa_origem_nao_oficial(url):
    with pytest.raises(ValueError):
        validar_url(url)


def test_validar_zip_aceita_pacote_da_cvm(tmp_path):
    membros = validar_zip(_zip_cvm(tmp_path / "itr_cia_aberta_2025.zip"))
    assert "itr_cia_aberta_DRE_con_2025.csv" in membros


@pytest.mark.parametrize(
    "nome",
    ["../fora.csv", "/etc/passwd", "itr_cia_aberta_2025.exe", "qualquer.csv"],
)
def test_validar_zip_recusa_membro_inseguro_ou_fora_do_padrao(tmp_path, nome):
    caminho = _zip_cvm(tmp_path / "ruim.zip", {nome: b"x"})
    with pytest.raises(ValueError):
        validar_zip(caminho)


def test_validar_zip_recusa_arquivo_que_nao_e_zip(tmp_path):
    caminho = tmp_path / "falso.zip"
    caminho.write_bytes(b"nao sou um zip")
    with pytest.raises(ValueError):
        validar_zip(caminho)


def test_membros_desejados_pega_so_o_consolidado():
    escolhidos = membros_desejados(
        [
            "itr_cia_aberta_2025.csv",
            "itr_cia_aberta_DRE_con_2025.csv",
            "itr_cia_aberta_DRE_ind_2025.csv",
            "itr_cia_aberta_BPA_con_2025.csv",
            "itr_cia_aberta_DMPL_con_2025.csv",
        ]
    )
    assert escolhidos == [
        "itr_cia_aberta_BPA_con_2025.csv",
        "itr_cia_aberta_DRE_con_2025.csv",
    ]


def test_extrair_csvs_traz_apenas_o_necessario(tmp_path):
    caminho = _zip_cvm(tmp_path / "itr_cia_aberta_2025.zip")
    extraidos = extrair_csvs(caminho, tmp_path / "saida")
    assert sorted(p.name for p in extraidos) == [
        "itr_cia_aberta_BPA_con_2025.csv",
        "itr_cia_aberta_BPP_con_2025.csv",
        "itr_cia_aberta_DRE_con_2025.csv",
    ]
    assert all(p.is_file() for p in extraidos)


def _linha_manifesto(caminho_zip: Path, conjunto="itr", ano=2025) -> dict[str, str]:
    return {
        "conjunto": conjunto,
        "ano": str(ano),
        "arquivo": nome_do_arquivo(conjunto, ano),
        "url": url_do_conjunto(conjunto, ano),
        "data_download": "2026-08-10",
        "tamanho_bytes": str(caminho_zip.stat().st_size),
        "hash_sha256": sha256_do_arquivo(caminho_zip),
    }


def test_manifesto_registra_url_data_e_hash(tmp_path):
    """Risco 15d: sem hash, o gabarito da classe `cvm` muda sozinho."""
    zip_path = _zip_cvm(tmp_path / "itr_cia_aberta_2025.zip")
    manifesto = tmp_path / "manifesto_cvm.csv"
    salvar_manifesto([_linha_manifesto(zip_path)], manifesto)

    assert manifesto.read_text(encoding="utf-8").splitlines()[0] == ",".join(
        COLUNAS_MANIFESTO
    )
    lidas = ler_manifesto(manifesto)
    assert len(lidas) == 1
    assert lidas[0]["url"].startswith("https://dados.cvm.gov.br/")
    assert len(lidas[0]["hash_sha256"]) == 64
    assert lidas[0]["data_download"] == "2026-08-10"


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("hash_sha256", "abc"),
        ("hash_sha256", ""),
        ("url", "https://exemplo.invalido/x.zip"),
        ("conjunto", "fre"),
        ("arquivo", "outro_nome.zip"),
        ("tamanho_bytes", "0"),
        ("data_download", "10/08/2026"),
    ],
)
def test_manifesto_recusa_linha_invalida(tmp_path, campo, valor):
    zip_path = _zip_cvm(tmp_path / "itr_cia_aberta_2025.zip")
    linha = _linha_manifesto(zip_path)
    linha[campo] = valor
    manifesto = tmp_path / "manifesto_cvm.csv"
    salvar_manifesto([linha], manifesto)
    with pytest.raises(ValueError):
        ler_manifesto(manifesto)


def test_verificacao_confirma_hash_pinado_sem_rede(tmp_path):
    zip_path = _zip_cvm(tmp_path / "itr_cia_aberta_2025.zip")
    manifesto = tmp_path / "manifesto_cvm.csv"
    salvar_manifesto([_linha_manifesto(zip_path)], manifesto)

    assert baixar_cvm(
        [2025],
        ["itr"],
        somente_verificar=True,
        caminho_manifesto=manifesto,
        dir_destino=tmp_path,
    )


def test_republicacao_do_portal_e_detectada_nao_absorvida(tmp_path):
    """O portal republica semanalmente; hash divergente é PROBLEMA reportado."""
    zip_path = _zip_cvm(tmp_path / "itr_cia_aberta_2025.zip")
    linha = _linha_manifesto(zip_path)
    manifesto = tmp_path / "manifesto_cvm.csv"
    salvar_manifesto([linha], manifesto)

    # o portal publicou outro conteúdo sob o mesmo nome
    _zip_cvm(
        zip_path,
        {"itr_cia_aberta_DRE_con_2025.csv": b"CNPJ_CIA;DT_REFER\nconteudo novo\n"},
    )
    assert not baixar_cvm(
        [2025],
        ["itr"],
        somente_verificar=True,
        caminho_manifesto=manifesto,
        dir_destino=tmp_path,
    )
    # e o manifesto NÃO foi reescrito com o hash novo
    assert ler_manifesto(manifesto)[0]["hash_sha256"] == linha["hash_sha256"]


def test_zip_local_sem_hash_no_manifesto_nao_e_promovido(tmp_path):
    """Cópia local sem hash pinado não vira verdade por presença (TOFU)."""
    _zip_cvm(tmp_path / "itr_cia_aberta_2025.zip")
    manifesto = tmp_path / "manifesto_cvm.csv"
    assert not baixar_cvm(
        [2025],
        ["itr"],
        somente_verificar=True,
        caminho_manifesto=manifesto,
        dir_destino=tmp_path,
    )


# --------------------------------------------------------------------------- #
# Companhia que troca de plano entre ITR e DFP (achado de 2026-08-10)
# --------------------------------------------------------------------------- #

CD_PLANO_TROCADO = "020532"


@pytest.fixture(scope="module")
def painel_plano_trocado(tmp_path_factory):
    """O Santander publica o lucro consolidado como `3.09` no ITR e como `3.11`
    na DFP do mesmo exercício — e na DFP `3.09` volta a ser *Lucro antes das
    Participações*. Mesma companhia, mesmo ano, mesmo código, outro conceito."""
    destino = tmp_path_factory.mktemp("plano_trocado") / "cvm.duckdb"
    relatorio = carregar_painel(
        [
            FonteCVM(
                DIR_FIXTURES / "itr_cia_aberta_DRE_con_plano_trocado.csv", "itr", "DRE"
            ),
            FonteCVM(
                DIR_FIXTURES / "dfp_cia_aberta_DRE_con_plano_trocado.csv", "dfp", "DRE"
            ),
        ],
        destino,
    )
    return destino, relatorio


@pytest.fixture
def con_trocado(painel_plano_trocado):
    caminho, _ = painel_plano_trocado
    conexao = duckdb.connect(str(caminho), read_only=True)
    try:
        yield conexao
    finally:
        conexao.close()


def test_mapa_aceita_dois_codigos_para_o_mesmo_conceito(con_trocado):
    codigos = {
        linha[0]
        for linha in con_trocado.execute(
            "SELECT cd_conta FROM mapa_contas WHERE conceito = ?",
            [CONCEITO_LUCRO_CONSOLIDADO],
        ).fetchall()
    }
    assert codigos == {"3.09", "3.11"}


def test_linha_antes_das_participacoes_nao_vira_lucro(con_trocado):
    """`3.09` da DFP tem a descrição de outra conta e não pode entrar no mapa
    como lucro — é o mesmo código, com outro significado."""
    descricoes = {
        linha[0]
        for linha in con_trocado.execute(
            "SELECT ds_conta_esperada FROM mapa_contas WHERE cd_conta = '3.09'"
        ).fetchall()
    }
    assert descricoes == {"Lucro/Prejuízo Consolidado do Período"}


def test_grao_permanece_unico_com_plano_trocado(con_trocado):
    duplicados = con_trocado.execute(
        """
        SELECT count(*) FROM (
            SELECT cd_cvm, trimestre, conceito FROM fatos_semanticos
            GROUP BY 1, 2, 3 HAVING count(*) > 1
        )
        """
    ).fetchone()[0]
    assert duplicados == 0


def test_derivacao_do_4t_pareia_por_conceito_nao_por_codigo(con_trocado):
    """Regressão: parear por `cd_conta` casaria o anual `3.11.01` com nada e o
    lucro dos controladores do 4T sumiria — e o consolidado casaria a linha
    *antes das participações* com o acumulado do lucro."""
    linhas = dict(
        con_trocado.execute(
            """
            SELECT conceito, valor_reais FROM fatos_semanticos
            WHERE cd_cvm = ? AND trimestre = '4T2025' AND origem = 'derivado'
            """,
            [CD_PLANO_TROCADO],
        ).fetchall()
    )
    assert linhas[CONCEITO_LUCRO_CONSOLIDADO] == pytest.approx(
        (12_965_123 - 9_021_926) * 1000.0
    )
    assert linhas[CONCEITO_LUCRO_CONTROLADORES] == pytest.approx(
        (12_766_035 - 8_501_317) * 1000.0
    )


def test_g4_aceita_os_dois_codigos_do_santander(painel_plano_trocado):
    caminho, _ = painel_plano_trocado
    resultado = conferir_mapa_g4(
        caminho,
        {
            CD_PLANO_TROCADO: {
                CONCEITO_LUCRO_CONSOLIDADO: CONFERENCIA_G4[CD_PLANO_TROCADO][
                    CONCEITO_LUCRO_CONSOLIDADO
                ],
                CONCEITO_LUCRO_CONTROLADORES: CONFERENCIA_G4[CD_PLANO_TROCADO][
                    CONCEITO_LUCRO_CONTROLADORES
                ],
            }
        },
    )
    assert resultado.aprovado, resultado.divergencias


def test_g4_ainda_reprova_3_09_em_banco_de_plano_3_11(painel_plano_trocado):
    """Aceitar conjunto de códigos não pode afrouxar o gate."""
    caminho, _ = painel_plano_trocado
    resultado = conferir_mapa_g4(
        caminho, {CD_PLANO_TROCADO: {CONCEITO_LUCRO_CONSOLIDADO: ("3.11",)}}
    )
    assert not resultado.aprovado


def test_normalizacao_sql_equivale_a_python():
    """A normalização roda em SQL sobre o painel e em Python sobre o mapa.

    Se as duas divergirem, o join da visão semântica perde linhas em silêncio —
    então a equivalência é contrato, não detalhe de implementação.
    """
    from src.dados_estruturados import _SQL_NORMALIZAR_DS_CONTA

    descricoes = [
        "Lucro ou Prejuízo Líquido Consolidado do Período",
        "Lucro/Prejuízo Consolidado do Período",
        "Atribuído aos Sócios da Empresa Controladora",
        "Atribuído a Sócios Não Controladores",
        "Patrimônio Líquido Consolidado",
        "Provisões (Líquidas)",
        "Provisões (líquidas)",
        "Ganhos / (Perdas) Líquidos de Operações de Câmbio",
        "Outras   Despesas    de Administrativas",
        "Lucro por Ação - (R$ / Ação)",
        "Despesas detarifas e comissões",
        "  Ativo Total  ",
        "",
    ]
    con = duckdb.connect()
    try:
        for descricao in descricoes:
            obtido = con.execute(
                "SELECT " + _SQL_NORMALIZAR_DS_CONTA.format(coluna="?"), [descricao]
            ).fetchone()[0]
            assert obtido == normalizar_ds_conta(descricao), descricao
    finally:
        con.close()


def test_incoerencia_do_lucro_na_fonte_e_contada(tmp_path):
    """Quando o próprio arquivo da CVM não fecha, a carga conta e reporta.

    A identidade `consolidado = controladores + não controladores` é aritmética.
    Verificado em 2026-08-10: o ITR do 3T2025 do Santander traz 9.021.926 mil no
    consolidado e 8.665.017 mil na soma das duas parcelas. A carga não conserta
    e não descarta — torna visível.
    """
    cabecalho = (
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;"
        "ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;"
        "ST_CONTA_FIXA"
    )
    grupo = "DF Consolidado - Demonstração do Resultado"

    def linha(cd, ds, valor):
        return (
            f"90.400.888/0001-42;2025-09-30;1;BCO SANTANDER (BRASIL) S.A.;020532;"
            f"{grupo};REAL;MIL;ÚLTIMO;2025-07-01;2025-09-30;{cd};{ds};"
            f"{valor}.0000000000;S"
        )

    caminho = tmp_path / "incoerente.csv"
    caminho.write_text(
        "\n".join(
            [
                cabecalho,
                linha("3.09", "Lucro/Prejuízo Consolidado do Período", 9021926),
                linha("3.09.01", "Atribuído a Sócios da Empresa Controladora", 8501317),
                linha("3.09.02", "Atribuído a Sócios Não Controladores", 163700),
            ]
        )
        + "\n",
        encoding="iso-8859-1",
    )
    relatorio = carregar_painel(
        [FonteCVM(caminho, "itr", "DRE")], tmp_path / "cvm.duckdb"
    )
    assert relatorio.incoerencias_lucro == 1
    assert any("NÃO é a soma" in aviso for aviso in relatorio.avisos)


def test_lucro_coerente_nao_gera_incoerencia(painel):
    _, relatorio = painel
    assert relatorio.incoerencias_lucro == 0


# --------------------------------------------------------------------------- #
# Fluxo de caixa (DFC) e cadastro de documento (point-in-time)
#
# Acrescentados em 2026-08-27. O fluxo de caixa SEMPRE esteve nos ZIPs já
# baixados — o painel é que só lia DRE, BPA e BPP. Sem DFC não há conversão de
# caixa, qualidade do lucro nem FCF; sem `DT_RECEB` nenhum backtest é
# point-in-time, porque `dt_refer` é fim de exercício e não data de publicação.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def fontes_com_fluxo() -> tuple[FonteCVM, ...]:
    return (
        FonteCVM(DIR_FIXTURES / "itr_cia_aberta_DRE_con_amostra.csv", "itr", "DRE"),
        FonteCVM(DIR_FIXTURES / "dfp_cia_aberta_DRE_con_amostra.csv", "dfp", "DRE"),
        FonteCVM(
            DIR_FIXTURES / "itr_cia_aberta_DFC_MI_con_amostra.csv", "itr", "DFC_MI"
        ),
        FonteCVM(
            DIR_FIXTURES / "dfp_cia_aberta_DFC_MI_con_amostra.csv", "dfp", "DFC_MI"
        ),
        FonteCVM(
            DIR_FIXTURES / "itr_cia_aberta_DFC_MD_con_amostra.csv", "itr", "DFC_MD"
        ),
    )


@pytest.fixture(scope="module")
def cabecalhos() -> tuple[FonteCabecalho, ...]:
    return (
        FonteCabecalho(DIR_FIXTURES / "itr_cia_aberta_amostra.csv", "itr"),
        FonteCabecalho(DIR_FIXTURES / "dfp_cia_aberta_amostra.csv", "dfp"),
    )


@pytest.fixture(scope="module")
def painel_fluxo(fontes_com_fluxo, cabecalhos, tmp_path_factory):
    destino = tmp_path_factory.mktemp("painel_fluxo") / "cvm.duckdb"
    relatorio = carregar_painel(
        list(fontes_com_fluxo), destino, cabecalhos=list(cabecalhos)
    )
    return destino, relatorio


@pytest.fixture
def con_fluxo(painel_fluxo):
    caminho, _ = painel_fluxo
    conexao = duckdb.connect(str(caminho), read_only=True)
    try:
        yield conexao
    finally:
        conexao.close()


class TestFluxoDeCaixa:
    def test_dfc_entra_no_painel(self, con_fluxo):
        linhas = con_fluxo.execute(
            "SELECT count(*) FROM fatos_contabeis "
            "WHERE demonstrativo IN ('DFC_MI', 'DFC_MD')"
        ).fetchone()[0]
        assert linhas > 0, "o fluxo de caixa não foi carregado"

    def test_penultimo_da_dfc_tambem_e_descartado(self, con_fluxo):
        """A regra de armadilha vale para a DFC como vale para a DRE."""
        anteriores = con_fluxo.execute(
            "SELECT count(*) FROM fatos_contabeis "
            "WHERE demonstrativo LIKE 'DFC%' AND dt_fim_exerc < DATE '2025-01-01'"
        ).fetchone()[0]
        assert anteriores == 0

    def test_escala_da_dfc_convertida_para_reais(self, con_fluxo):
        """BB publica em MIL; 9.000.000 MIL têm de virar 9e9 reais.

        Qualificado pelo trimestre: a fixture tem DOIS acumulados (1S e 9M),
        porque é assim que a CVM publica a DFC — e é o que a derivação de
        trimestre intermediário consome.
        """
        valor = con_fluxo.execute(
            """
            SELECT valor_reais FROM fatos_contabeis
            WHERE cd_cvm = '001023' AND demonstrativo = 'DFC_MI'
              AND cd_conta = '6.01' AND tipo_periodo = 'acumulado'
              AND trimestre = '3T2025'
            """
        ).fetchone()[0]
        assert valor == pytest.approx(9_000_000_000.0)

    def test_quarto_trimestre_da_dfc_e_derivado(self, con_fluxo):
        """RN10 sobre fluxo de caixa: anual (13e9) − 9 meses (9e9) = 4e9."""
        linha = con_fluxo.execute(
            """
            SELECT valor_reais, origem FROM fatos_contabeis
            WHERE cd_cvm = '001023' AND demonstrativo = 'DFC_MI'
              AND cd_conta = '6.01' AND trimestre = '4T2025'
              AND tipo_periodo = 'trimestral'
            """
        ).fetchone()
        assert linha is not None, "o 4T do fluxo de caixa não foi derivado"
        assert linha[0] == pytest.approx(4_000_000_000.0)
        assert linha[1] == "derivado", "RN10 exige a marcação explícita"

    def test_derivacao_nao_inventa_4t_de_balanco(self, con_fluxo):
        """Contraprova: saldo de balanço em 31/12 é arquivado, nunca derivado."""
        derivados_de_balanco = con_fluxo.execute(
            "SELECT count(*) FROM fatos_contabeis "
            "WHERE origem = 'derivado' AND demonstrativo IN ('BPA', 'BPP')"
        ).fetchone()[0]
        assert derivados_de_balanco == 0

    def test_sobreposicao_md_x_mi_e_contada_nao_suposta(self, painel_fluxo):
        """O BB publica pelos dois métodos no 3T2025 — somar duplicaria o caixa.

        A fixture reproduz o caso real: 9 emissores publicaram MD e MI em 2024.
        """
        _, relatorio = painel_fluxo
        assert relatorio.emissores_dfc_ambos_metodos == 1
        assert any("DOIS métodos" in aviso for aviso in relatorio.avisos)


class TestDocumentosPointInTime:
    def test_dt_receb_carregada(self, painel_fluxo, con_fluxo):
        _, relatorio = painel_fluxo
        assert relatorio.documentos_carregados == 6
        linha = con_fluxo.execute(
            "SELECT dt_receb FROM documentos "
            "WHERE cd_cvm = '001023' AND dt_refer = DATE '2025-03-31'"
        ).fetchone()
        assert str(linha[0]) == "2025-05-12"

    def test_publicacao_vem_depois_do_fim_do_exercicio(self, con_fluxo):
        """O ponto inteiro da tabela: `dt_refer` NÃO é data de publicação.

        Se alguém usar `dt_refer` como se fosse, todo backtest enxerga o
        trimestre ~40 dias antes de ele existir. Foi a falha do gate G1.
        """
        atraso = con_fluxo.execute(
            "SELECT min(datediff('day', dt_refer, dt_receb)) FROM documentos"
        ).fetchone()[0]
        assert atraso > 0, "dt_receb nunca pode preceder o fim do exercício"

    def test_todas_as_versoes_sao_preservadas(self, con_fluxo):
        """`fatos_contabeis` guarda só a maior versão; `documentos`, todas.

        Sem isso não dá para responder "o que se sabia em D?" — inclusive que a
        versão vigente naquela data foi depois substituída.
        """
        versoes = con_fluxo.execute(
            "SELECT count(*) FROM documentos "
            "WHERE cd_cvm = '001023' AND dt_refer = DATE '2025-06-30'"
        ).fetchone()[0]
        assert versoes == 2

    def test_cabecalho_sem_dt_receb_falha_fechado(self, tmp_path):
        """Painel que se diz point-in-time e não é seria pior que nenhum."""
        with pytest.raises(ErroCargaCVM, match="DT_RECEB"):
            carregar_painel(
                [
                    FonteCVM(
                        DIR_FIXTURES / "itr_cia_aberta_DRE_con_amostra.csv",
                        "itr",
                        "DRE",
                    )
                ],
                tmp_path / "cvm.duckdb",
                cabecalhos=[
                    FonteCabecalho(
                        DIR_FIXTURES / "itr_cia_aberta_sem_dt_receb.csv", "itr"
                    )
                ],
            )

    def test_sem_cabecalho_o_painel_avisa_que_nao_e_point_in_time(self, painel):
        """Ausência tem de ser legível, não silenciosa."""
        _, relatorio = painel
        assert relatorio.documentos_carregados == 0
        assert any("NÃO é point-in-time" in aviso for aviso in relatorio.avisos)


class TestDerivacaoDeTrimestreIntermediario:
    """A CVM publica a DFC do 2T/3T só em forma ACUMULADA (achado 2026-08-27).

    Sem derivar o isolado, fluxo de caixa existe apenas no 1T e no 4T — dois
    trimestres por ano nunca fecham uma janela móvel de quatro, e toda métrica
    TTM de caixa fica impossível.
    """

    def test_2t_isolado_e_derivado_do_acumulado(self, con_fluxo):
        """1T = 3.000.000 MIL; acumulado do 1S = 5.500.000 → 2T = 2.500.000."""
        linha = con_fluxo.execute(
            """
            SELECT valor_reais, origem, dt_ini_exerc FROM fatos_contabeis
            WHERE cd_cvm = '001023' AND demonstrativo = 'DFC_MI'
              AND cd_conta = '6.01' AND trimestre = '2T2025'
              AND tipo_periodo = 'trimestral'
            """
        ).fetchone()
        assert linha is not None, "o 2T isolado do fluxo de caixa não foi derivado"
        assert linha[0] == pytest.approx(2_500_000_000.0)
        assert linha[1] == "derivado"
        assert str(linha[2]) == "2025-04-01", "o período tem de começar após o 1T"

    def test_nao_sobrescreve_isolado_que_a_cvm_publica(self, con_fluxo):
        """A DRE já vem com isolado; a derivação não pode duplicar nem trocar.

        No 2T2025 o BB publica receita isolada de verdade — tem de continuar
        `arquivado`, e existir uma única linha.
        """
        linhas = con_fluxo.execute(
            """
            SELECT origem FROM fatos_contabeis
            WHERE cd_cvm = '001023' AND demonstrativo = 'DRE'
              AND cd_conta = '3.01' AND trimestre = '2T2025'
              AND tipo_periodo = 'trimestral'
            """
        ).fetchall()
        assert len(linhas) == 1, "a derivação duplicou uma linha já publicada"
        assert linhas[0][0] == "arquivado"

    def test_derivacao_nao_atravessa_exercicios(self, con_fluxo):
        """Só subtrai períodos de MESMO início de exercício.

        Parear "a linha anterior" casaria o acumulado de um exercício com o de
        outro e produziria número plausível e errado — a falha que a RN09
        combate, na aritmética em vez de no código de conta.
        """
        atravessou = con_fluxo.execute(
            """
            SELECT count(*) FROM fatos_contabeis
            WHERE origem = 'derivado' AND dt_ini_exerc IS NOT NULL
              AND dt_ini_exerc > dt_fim_exerc
            """
        ).fetchone()[0]
        assert atravessou == 0


class TestDerivacaoSoCobreUmTrimestre:
    """Contrato D1 — `contratos_correcao_derivacao_intermediaria_2026-09-12.md`.

    O `lag` da derivação pareia o período anterior **disponível**, não o
    trimestre imediatamente anterior. Faltando um acumulado intermediário, a
    diferença cobria mais de um trimestre e saía rotulada `trimestral`.

    Medido no painel de treino antes da correção: **7.734 linhas** em 513
    companhias e 111 contas, com 182, 183, 184 ou 273 dias. (Dizia 507, que é
    só o grupo de 183 dias — corrigido em 2026-09-15, conferência §3.3.)
    """

    @staticmethod
    def _painel(acumulados):
        """Painel mínimo em memória, com o schema real de `fatos_contabeis`.

        Em memória, e não sobre a fixture de CSV, porque o que se exercita aqui
        é a presença ou ausência de UM acumulado intermediário — construir isso
        por arquivo-fonte esconderia o caso atrás da carga inteira.
        """
        con = duckdb.connect(":memory:")
        con.execute(
            "CREATE TABLE companhias (cd_cvm VARCHAR, plano_contas VARCHAR)"
        )
        con.execute("INSERT INTO companhias VALUES ('001023', 'plano_x')")
        con.execute(
            "CREATE TABLE mapa_contas (plano_contas VARCHAR, conceito VARCHAR, "
            "cd_conta VARCHAR, ds_conta_norm VARCHAR)"
        )
        con.execute(
            """
            CREATE TABLE fatos_contabeis (
                cd_cvm VARCHAR, conjunto VARCHAR, demonstrativo VARCHAR,
                trimestre VARCHAR, tipo_periodo VARCHAR, dt_refer DATE,
                dt_ini_exerc DATE, dt_fim_exerc DATE, cd_conta VARCHAR,
                ds_conta VARCHAR, ds_conta_norm VARCHAR, vl_conta DOUBLE,
                escala VARCHAR, valor_reais DOUBLE, versao_documento INTEGER,
                origem VARCHAR
            )
            """
        )
        for trimestre, tipo, fim, valor in acumulados:
            con.execute(
                """
                INSERT INTO fatos_contabeis VALUES
                ('001023', 'itr', 'DFC_MI', ?, ?, ?, DATE '2025-01-01', ?,
                 '6.01', 'Caixa Operacional', 'caixa operacional',
                 ?, 'UNIDADE', ?, 1, 'arquivado')
                """,
                [trimestre, tipo, fim, fim, valor, valor],
            )
        return con

    def test_sem_o_trimestre_anterior_a_derivacao_e_recusada(self):
        """1T e acumulado de 9M presentes, **1S ausente**: nada de `3T` derivado.

        Docstring corrigida em 2026-09-15 (conferência QW6): dizia "1T ausente,
        acumulado do 1S presente", mas os dados sempre foram 1T e 9M sem o 1S.
        As asserções são as mesmas.

        O caso do parecer, em miniatura: `19.289.000` (jan–set) menos
        `1.992.000` (jan–mar) produzia `17.297.000 de abr–set` **rotulado
        trimestral**.
        """
        con = self._painel([
            ("1T2025", "trimestral", "2025-03-31", 1_000.0),
            ("3T2025", "acumulado", "2025-09-30", 9_000.0),
        ])
        # Contrato D2.3: retorno de três estados — desempacotamento adaptado.
        criados, recusados, sem_antecedente = (
            dados_estruturados._derivar_trimestres_intermediarios(con)
        )
        assert criados == 0, (
            "de jan–mar para jan–set a diferença cobre SEIS meses: não é "
            "trimestre isolado"
        )
        assert recusados == 1, "a recusa tem de ser contada, não silenciosa"
        assert sem_antecedente == 0, "há antecedente: é recusa pela banda"
        con.close()

    def test_com_o_trimestre_anterior_a_derivacao_acontece(self):
        """**Não-regressão obrigatória.** Sem este caso, recusar tudo passaria
        no teste acima — e a função existe justamente para derivar."""
        con = self._painel([
            ("1T2025", "trimestral", "2025-03-31", 1_000.0),
            ("2T2025", "acumulado", "2025-06-30", 3_000.0),
        ])
        criados, recusados, sem_antecedente = (  # D2.3
            dados_estruturados._derivar_trimestres_intermediarios(con)
        )
        assert criados == 1
        assert recusados == 0
        assert sem_antecedente == 0
        linha = con.execute(
            """
            SELECT valor_reais, dt_ini_exerc, dt_fim_exerc, origem, tipo_periodo
            FROM fatos_contabeis
            WHERE origem = 'derivado' AND trimestre = '2T2025'
            """
        ).fetchone()
        assert linha[0] == pytest.approx(2_000.0)
        assert str(linha[1]) == "2025-04-01"
        assert str(linha[2]) == "2025-06-30"
        assert linha[3] == "derivado" and linha[4] == "trimestral"
        con.close()

    def test_nenhum_derivado_sai_com_duracao_fora_da_banda(self):
        """Varre os três acumulados juntos: 1T, 1S e 9M.

        O 2T deriva (1S − 1T) e o 3T deriva (9M − 1S). Nenhum dos dois pode
        sair com duração de semestre.
        """
        con = self._painel([
            ("1T2025", "trimestral", "2025-03-31", 1_000.0),
            ("2T2025", "acumulado", "2025-06-30", 3_000.0),
            ("3T2025", "acumulado", "2025-09-30", 6_000.0),
        ])
        criados, _, _ = dados_estruturados._derivar_trimestres_intermediarios(con)  # D2.3
        assert criados == 2
        fora = con.execute(
            f"""
            SELECT count(*) FROM fatos_contabeis WHERE origem = 'derivado'
              AND (dt_fim_exerc - dt_ini_exerc + 1) NOT BETWEEN
                  {dados_estruturados.DIAS_MINIMOS_DE_UM_TRIMESTRE}
                  AND {dados_estruturados.DIAS_MAXIMOS_DE_UM_TRIMESTRE}
            """
        ).fetchone()[0]
        assert fora == 0
        con.close()

    def test_so_o_acumulado_sem_antecedente_nao_e_recusa(self):
        """Contrato D2.2: o caso literal "só o 1S" que a conferência testou.

        Não há aritmética possível — não é recusa pela banda. É estado próprio,
        contado à parte, para que a ausência não seja silenciosa.
        """
        con = self._painel([("2T2025", "acumulado", "2025-06-30", 3_000.0)])
        resultado = dados_estruturados._derivar_trimestres_intermediarios(con)
        assert resultado == (0, 0, 1)
        assert resultado.sem_antecedente == 1
        con.close()

    def test_recusa_e_contada_com_a_identidade_da_insercao(self):
        """Contraprova B da conferência: outra descrição no 2T escondia a recusa.

        A contagem usava `coalesce(conceito, cd_conta)`; a inserção,
        `coalesce(conceito, cd_conta|descrição)`. Com a mesma conta no 1T e no
        3T e outra descrição no 2T, a recusa acontecia e saía `(0, 0)`. Agora
        a recusa é contada, e o 2T de outra descrição é `sem_antecedente`.
        """
        for descricao_diferente, esperado in ((False, (0, 1, 0)), (True, (0, 1, 1))):
            linhas = [
                ("1T2025", "trimestral", "2025-03-31", 1_000.0),
                ("3T2025", "acumulado", "2025-09-30", 9_000.0),
            ]
            if descricao_diferente:
                linhas.insert(1, ("2T2025", "acumulado", "2025-06-30", 3_000.0))
            con = self._painel(linhas)
            if descricao_diferente:
                con.execute(
                    "UPDATE fatos_contabeis SET ds_conta = 'Outra conta', "
                    "ds_conta_norm = 'outra conta' WHERE trimestre = '2T2025'"
                )
            assert (
                dados_estruturados._derivar_trimestres_intermediarios(con) == esperado
            ), descricao_diferente
            con.close()

    def test_a_banda_esta_declarada_e_cobre_um_trimestre(self):
        """Se a banda mudar, a falsificação nº 1 do contrato se verifica."""
        assert dados_estruturados.DIAS_MINIMOS_DE_UM_TRIMESTRE == 80
        assert dados_estruturados.DIAS_MAXIMOS_DE_UM_TRIMESTRE == 100


class TestAvisosDaDerivacaoNoCarregador:
    """Contrato D2.4 — o critério 6 do contrato D1 (*"o aviso aparece quando
    houve recusa, e não aparece quando não houve"*) nunca tinha sido testado no
    CARREGADOR: os casos D1 olhavam só o retorno da função. Foi assim que a
    recusa silenciosa de QW6 passou.
    """

    def test_sem_recusa_nao_ha_aviso_de_recusa(self, painel_fluxo):
        _, relatorio = painel_fluxo
        assert not any("RECUSADAS" in aviso for aviso in relatorio.avisos)

    def test_sem_antecedente_e_avisado(self, painel_fluxo):
        """A fixture tem `6.02` só no acumulado de 9M: não há de onde derivar."""
        _, relatorio = painel_fluxo
        assert any("SEM ANTECEDENTE" in aviso for aviso in relatorio.avisos)
        assert not any(
            "SEM ANTECEDENTE" in aviso and "RECUSADAS" in aviso
            for aviso in relatorio.avisos
        ), "as duas causas não podem sair no mesmo aviso"

    def test_recusa_pela_banda_e_avisada(self, fontes_com_fluxo, cabecalhos, tmp_path):
        """Sem o acumulado do 1S de `6.01`, o 9M menos o 1T cobriria seis meses."""
        original = DIR_FIXTURES / "itr_cia_aberta_DFC_MI_con_amostra.csv"
        linhas = original.read_text(encoding="latin-1").splitlines(keepends=True)
        sem_1s = [
            linha for linha in linhas
            if not (";2025-06-30;" in linha and ";6.01;" in linha and ";001023;" in linha)
        ]
        assert len(sem_1s) == len(linhas) - 1, "a fixture mudou: o 1S não é mais único"
        modificada = tmp_path / original.name
        modificada.write_text("".join(sem_1s), encoding="latin-1")
        fontes = [
            FonteCVM(modificada, "itr", "DFC_MI") if original.name in repr(fonte) else fonte
            for fonte in fontes_com_fluxo
        ]
        assert sum(original.name in repr(f) for f in fontes_com_fluxo) == 1
        relatorio = carregar_painel(
            fontes, tmp_path / "cvm.duckdb", cabecalhos=list(cabecalhos)
        )
        recusas = [aviso for aviso in relatorio.avisos if "RECUSADAS" in aviso]
        assert len(recusas) == 1
        assert recusas[0].startswith("1 derivação")
