"""Contrato do gate G4 — painel × linha contábil do release (spec 5.5, RN09).

Nenhum teste aqui lê `corpus/ocr/`, o `artefatos/cvm.duckdb` real ou a rede. As
fixtures são recortes **mínimos** das tabelas verdadeiras, incluindo as duas
patologias que o OCR produziu no corpus e que quase fizeram o gate ler o número
errado sem perceber:

1. **Rótulo de linha perdido.** Na ponte BRGAAP→IFRS do Itaú de 2T2025 e 3T2025
   sobraram só os números; sem rótulo, a leitura por nome de linha falha.
2. **Coluna deslocada.** Em 3T2025 e 4T2025 a tabela vizinha de patrimônio
   líquido vazou para dentro da linha de dados: cabeçalho e linha continuam com o
   mesmo comprimento, e a leitura por índice devolveria o patrimônio no lugar do
   resultado — número plausível, não nulo e errado.

A segunda metade do arquivo cobre `scripts/ancora_ifrs.py`, o leitor das
demonstrações em IFRS publicadas em separado, e a integração dele ao gate.
Nenhum teste abre um PDF: as fixtures reproduzem os cabeçalhos e as linhas
verdadeiros em texto, incluindo os dois que já quebraram a leitura de um emissor
inteiro sem erro visível.

O teste é o contrato: nenhuma asserção aqui pode ser afrouxada para fazer o
extrator passar.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import pytest

from scripts import ancora_ifrs, gate_g4
from src.mapa_contas import (
    BANCOS_CORPUS,
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_LUCRO_NAO_CONTROLADORES,
)

# --------------------------------------------------------------------------- #
# Recortes reais, reduzidos ao mínimo que exercita cada caminho
# --------------------------------------------------------------------------- #

# Itaú 1T2026, pág. 5 — conciliação contábil × gerencial, cabeçalho e linha
# alinhados, rótulo preservado.
CONCILIACAO_ITAU = """## Resultado Gerencial

### Conciliação entre o resultado contábil e gerencial | 1º trimestre de 2026

|  Em R$ milhões | Contábil | Itens Extraordinários | Ajustes gerenciais |   | Gerencial  |
| --- | --- | --- | --- | --- | --- |
|   |   |   |  Efeitos fiscais | Reclassificações  |   |
|  **Resultado antes da Tributação e Participações** | **13.759** | **2.060** | **1.363** | **343** | **17.525**  |
|  **Participações Minoritárias nas Subsidiárias** | **(213)** | **(72)** | **-** | **(19)** | **(305)**  |
|  **Lucro Líquido** | **11.938** | **344** | **-** | **-** | **12.282**  |
"""

# Itaú 1T2026, pág. 29 — ponte BRGAAP→IFRS íntegra: rótulos presentes, colunas
# alinhadas.
PONTE_ITAU_INTEGRA = """# Comparativo BRGAAP¹ e IFRS

|   | Patrimônio Líquido* | Resultado Líquido*  |   |   |
| --- | --- | --- | --- | --- |
|   | 31/mar/26 | 1T26 | 4T25 | 1T25  |
|  **BRGAAP - valores atribuíveis aos acionistas controladores** | **200.098** | **11.938** | **11.937** | **10.894**  |
|  (a) Perda de Crédito Esperada | 1.487 | (25) | (11) | 153  |
|  (b) Classificação de Ativos Financeiros | 169 | (26) | 94 | 768  |
|  **IFRS - valores atribuíveis aos acionistas controladores** | **209.705** | **11.636** | **11.907** | **10.507**  |
|  IFRS - participação dos acionistas não controladores | 10.312 | 239 | 237 | 200  |
|  **IFRS - valores atribuíveis aos acionistas controladores e não controladores** | **220.017** | **11.875** | **12.144** | **10.707**  |
"""

# Itaú 3T2025, pág. 29 — as duas patologias juntas: rótulos perdidos E colunas
# deslocadas em +1 pelo vazamento da tabela de patrimônio líquido.
PONTE_ITAU_MUTILADA = """# Comparativo BRGAAP¹ e IFRS

|   | Resultado Líquido*  |   |   |   |   |
| --- | --- | --- | --- | --- | --- |
|   | 3T25 | 2T25 | 3T24 | 9M25 | 9M24  |
|   | **207.164** | **11.561** | **11.278** | **10.194** | **33.733**  |
|   | 2.495 | 166 | 227 | (292) | 546  |
|   | (3.487) | (103) | 410 | 742 | 1.075  |
|   | **214.918** | **11.306** | **11.137** | **10.366** | **32.950**  |
|   | 9.789 | 294 | 261 | 229 | 755  |
|   | **224.707** | **11.600** | **11.398** | **10.595** | **33.705**  |
"""

# Santander 1T2026, pág. 19 — o rótulo `Contábil` mora na SEGUNDA linha de
# cabeçalho.
CONCILIACAO_SANTANDER = """## Reconciliação dos resultados contábil e gerencial

|  R$ Milhões | 1T26 |   | Reclassificações |   |   |   | 1T26  |   |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|   |  Contábil | Hedge Cambial^{1} | Recup. Crédito^{2} | Amort. do ágio^{3} | Part. no Lucro | Var. Cambiais (Líquidas) | Outros Eventos^{4} | Gerencial  |
|  Participações dos acionistas minoritários | (118) | - | - | - | - | - | - | (118)  |
|  **Lucro Líquido** | **3.725** | - | - | **63** | - | - | - | **3.788**  |
"""

# Banco do Brasil 2T2025, pág. 17 — a coluna é o rótulo do trimestre, o bullet
# virou `II` no OCR e existe uma linha `Lucro Líquido Ajustado` logo acima.
CONCILIACAO_BB = """# Demonstração do Resultado Consolidado

Tabela 3. Demonstração do Resultado com Realocações – R$ milhões

|   | 2T24 | 1T25 | 2T25 | Δ% A/A | Δ% T/T | 1S24 | 1S25 | Δ% Acm.  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  **II Lucro Líquido Ajustado** | **9.502** | **7.374** | **3.784** | **(60,2)** | **(48,7)** | **18.802** | **11.158** | **(40,7)**  |
|  **II Lucro Líquido** | **8.965** | **6.772** | **3.035** | **(66,1)** | **(55,2)** | **17.747** | **9.807** | **(44,7)**  |
"""

# Bradesco 1T2026, pág. 44 — conciliação e ponte na mesma página; a ponte é
# publicada em acumulado nos demais trimestres.
CONCILIACAO_E_PONTE_BRADESCO = """# Resultado Gerencial x Recorrente

## Composição Analítica

|   | 1º trimestre de 2026  |   |   |   |
| --- | --- | --- | --- | --- |
|  R$ milhões | DRE Gerencial ^{(1)} | Reclassificações ^{(2)} | Eventos não Recorrentes | DRE Recorrente ^{(3)}  |
|  **\\\\ Lucro Líquido** | **5.030** | **-** | **1.781** | **6.811**  |

## Comparativo BRGAAP x IFRS

|  Atribuível ao Controlador | Patrimônio Líquido | Lucro Líquido  |   |
| --- | --- | --- | --- |
|  R$ milhões | Mar26 | 1T26 | 1T25  |
|  **\\\\ BRGAAP** | **173.549** | **5.030** | **5.802**  |
|  **\\\\ IFRS** | **179.763** | **5.178** | **5.604**  |
|  **\\\\ Diferença IFRS vs. BRGAAP** | **6.214** | **148** | **(198)**  |
"""


def _documento(empresa: str, trimestre: str, paginas: list[tuple[int, str]]):
    return gate_g4.DocumentoOCR(
        documento=f"{empresa.lower()}_release_{trimestre}",
        empresa=empresa,
        trimestre=trimestre,
        hash_pdf="0" * 64,
        paginas=tuple(paginas),
    )


# --------------------------------------------------------------------------- #
# Parsing de tabela e de célula
# --------------------------------------------------------------------------- #


def test_tabelas_da_pagina_separa_tabelas_e_descarta_o_separador():
    tabelas = gate_g4.tabelas_da_pagina(CONCILIACAO_E_PONTE_BRADESCO, pagina=44)
    assert len(tabelas) == 2
    assert all(t.pagina == 44 for t in tabelas)
    # A linha `| --- | --- |` não vira dado.
    assert all("---" not in celula for t in tabelas for l in t.linhas for celula in l)


def test_tabelas_da_pagina_nao_inventa_tabela_em_texto_corrido():
    assert gate_g4.tabelas_da_pagina("Nenhuma tabela aqui.\nSó prosa.") == ()


@pytest.mark.parametrize(
    "celula, esperado",
    [
        ("**11.938**", 11938.0),
        ("(1.465)", -1465.0),
        ("**4.570,4**", 4570.4),
        ("**(4.231,1)**", -4231.1),
        ("-", None),
        ("", None),
        ("   ", None),
    ],
)
def test_valor_da_celula(celula, esperado):
    assert gate_g4.valor_da_celula(celula) == esperado


@pytest.mark.parametrize(
    "celula, esperado",
    [("**11.938**", 0), ("4.570,4", 1), ("5.030,151", 3), ("-", 0)],
)
def test_casas_decimais_define_a_meia_unidade(celula, esperado):
    assert gate_g4.casas_decimais(celula) == esperado


def test_normalizar_rotulo_remove_enfase_barra_e_nota_mas_nao_o_bullet_do_bb():
    assert gate_g4.normalizar_rotulo("**\\\\ Lucro Líquido**") == "lucro liquido"
    assert gate_g4.normalizar_rotulo("Hedge Cambial^{1}") == "hedge cambial"
    # `II` é o bullet do BB transcrito como letras: NÃO é removido em silêncio —
    # quem tolera declara no padrão da receita, para a tolerância ficar visível.
    assert gate_g4.normalizar_rotulo("**II Lucro Líquido**") == "ii lucro liquido"


# --------------------------------------------------------------------------- #
# Leitura de célula por nome de linha e de coluna
# --------------------------------------------------------------------------- #


def test_ler_celula_encontra_a_linha_contabil_do_itau():
    (tabela,) = gate_g4.tabelas_da_pagina(CONCILIACAO_ITAU, pagina=5)
    celula = gate_g4.ler_celula(
        tabela, re.compile(r"lucro liquido"), re.compile(r"contabil")
    )
    assert celula.valor == 11938.0
    assert celula.rotulo_coluna == "contabil"
    assert celula.meia_unidade == 0.5


def test_ler_celula_acha_coluna_na_segunda_linha_de_cabecalho_do_santander():
    (tabela,) = gate_g4.tabelas_da_pagina(CONCILIACAO_SANTANDER, pagina=19)
    assert (
        gate_g4.ler_celula(
            tabela, re.compile(r"lucro liquido"), re.compile(r"contabil")
        ).valor
        == 3725.0
    )
    assert (
        gate_g4.ler_celula(
            tabela, re.compile(r"lucro liquido"), re.compile(r"gerencial")
        ).valor
        == 3788.0
    )


def test_ler_celula_nao_confunde_lucro_liquido_com_lucro_liquido_ajustado():
    """A armadilha do BB: a linha ajustada fica logo acima da contábil."""
    (tabela,) = gate_g4.tabelas_da_pagina(CONCILIACAO_BB, pagina=17)
    celula = gate_g4.ler_celula(
        tabela, re.compile(r"(?:ii )?lucro liquido"), re.compile(r"2t25")
    )
    assert celula.valor == 3035.0, "pegou a linha do lucro ajustado (3.784)"


def test_ler_celula_recusa_linha_com_comprimento_diferente_do_cabecalho():
    """Linha desalinhada é leitura por chute — e chute vira número plausível."""
    tabela = gate_g4.TabelaMarkdown(
        pagina=1,
        linhas=(
            ("", "1T26", "4T25"),
            ("Lucro Líquido", "1", "2", "3"),
        ),
    )
    with pytest.raises(gate_g4.ExtracaoAmbiguaError, match="chute"):
        gate_g4.ler_celula(
            tabela, re.compile(r"lucro liquido"), re.compile(r"1t26")
        )


def test_ler_celula_recusa_coluna_inexistente():
    (tabela,) = gate_g4.tabelas_da_pagina(CONCILIACAO_ITAU, pagina=5)
    with pytest.raises(gate_g4.ExtracaoAmbiguaError, match="coluna não encontrada"):
        gate_g4.ler_celula(
            tabela, re.compile(r"lucro liquido"), re.compile(r"ifrs")
        )


def test_ler_celula_recusa_celula_sem_numero():
    (tabela,) = gate_g4.tabelas_da_pagina(CONCILIACAO_SANTANDER, pagina=19)
    with pytest.raises(gate_g4.ExtracaoAmbiguaError, match="sem número"):
        gate_g4.ler_celula(
            tabela,
            re.compile(r"lucro liquido"),
            re.compile(r"hedge cambial"),
        )


# --------------------------------------------------------------------------- #
# Ponte BRGAAP → IFRS
# --------------------------------------------------------------------------- #


def test_ponte_por_identidade_le_a_tabela_integra_e_confere_o_rotulo():
    (tabela,) = gate_g4.tabelas_da_pagina(PONTE_ITAU_INTEGRA, pagina=29)
    ponte = gate_g4.extrair_ponte_por_identidade(
        tabela, re.compile(r"1t26"), ancora=11938.0, tolerancia_ancora=0.5
    )
    assert ponte.deslocamento == 0
    assert (ponte.controladores, ponte.nao_controladores, ponte.consolidado) == (
        11636.0,
        239.0,
        11875.0,
    )
    assert ponte.rotulo_conferido is True


def test_ponte_por_identidade_recupera_tabela_sem_rotulo_e_com_coluna_deslocada():
    """A leitura por índice devolveria 207.164 (patrimônio) em vez de 11.561."""
    (tabela,) = gate_g4.tabelas_da_pagina(PONTE_ITAU_MUTILADA, pagina=29)
    ponte = gate_g4.extrair_ponte_por_identidade(
        tabela, re.compile(r"3t25"), ancora=11561.0, tolerancia_ancora=0.5
    )
    assert ponte.deslocamento == 1
    assert ponte.controladores == 11306.0
    assert ponte.nao_controladores == 294.0
    assert ponte.consolidado == 11600.0
    assert ponte.rotulo_conferido is False


def test_ponte_por_identidade_falha_quando_a_ancora_nao_existe_na_tabela():
    (tabela,) = gate_g4.tabelas_da_pagina(PONTE_ITAU_INTEGRA, pagina=29)
    with pytest.raises(gate_g4.ExtracaoAmbiguaError, match="BRGAAP não é única"):
        gate_g4.extrair_ponte_por_identidade(
            tabela, re.compile(r"1t26"), ancora=99999.0, tolerancia_ancora=0.5
        )


def test_ponte_por_identidade_falha_quando_a_identidade_nao_identifica_um_trio():
    """Sem `controladores + não controladores = consolidado`, não há leitura."""
    tabela = gate_g4.TabelaMarkdown(
        pagina=1,
        linhas=(
            ("", "1T26"),
            ("BRGAAP", "11.938"),
            ("a", "1"),
            ("b", "2"),
            ("c", "9"),
        ),
    )
    with pytest.raises(gate_g4.ExtracaoAmbiguaError, match="identidade"):
        gate_g4.extrair_ponte_por_identidade(
            tabela, re.compile(r"1t26"), ancora=11938.0, tolerancia_ancora=0.5
        )


def test_extrair_ponte_bradesco_subtrai_acumulados_de_dois_documentos():
    """3T isolado = 9M25 − 1S25, cada parcela impressa em R$ milhões."""
    doc_3t = _documento(
        "BRADESCO",
        "3T2025",
        [
            (
                47,
                CONCILIACAO_E_PONTE_BRADESCO.replace("1T26 | 1T25", "9M25 | 9M24")
                .replace("**5.178**", "**17.172**")
                .replace("**5.030**", "**18.074**"),
            )
        ],
    )
    doc_2t = _documento(
        "BRADESCO",
        "2T2025",
        [
            (
                47,
                CONCILIACAO_E_PONTE_BRADESCO.replace("1T26 | 1T25", "1S25 | 1S24")
                .replace("**5.178**", "**11.671**")
                .replace("**5.030**", "**11.869**"),
            )
        ],
    )
    ifrs, _, tolerancia, procedencia = gate_g4.extrair_ponte_bradesco(
        doc_3t, {"3T2025": doc_3t, "2T2025": doc_2t}
    )
    assert ifrs == pytest.approx(5501.0)
    # Duas parcelas arredondadas ⇒ duas meias-unidades de tolerância.
    assert tolerancia == pytest.approx(1.0)
    assert "9m25" in procedencia and "1s25" in procedencia


# --------------------------------------------------------------------------- #
# Extração por documento
# --------------------------------------------------------------------------- #


def test_ler_release_do_itau_traz_contabil_gerencial_e_ifrs():
    documento = _documento(
        "ITAU", "1T2026", [(5, CONCILIACAO_ITAU), (29, PONTE_ITAU_INTEGRA)]
    )
    leitura = gate_g4.ler_release(documento, {"1T2026": documento})
    assert leitura.contabil is not None and leitura.contabil.valor == 11938.0
    assert leitura.gerencial is not None and leitura.gerencial.valor == 12282.0
    assert leitura.ifrs_controladores == 11636.0
    assert leitura.ifrs_consolidado == 11875.0


def test_ler_release_sem_ponte_deixa_ifrs_vazio_e_registra_o_contabil():
    documento = _documento("SANTANDER", "1T2026", [(19, CONCILIACAO_SANTANDER)])
    leitura = gate_g4.ler_release(documento, {"1T2026": documento})
    assert leitura.contabil is not None and leitura.contabil.valor == 3725.0
    assert leitura.ifrs_controladores is None


def test_ler_release_registra_nota_quando_a_pagina_nao_existe():
    documento = _documento("BTG", "1T2026", [(1, "Sem tabela nenhuma.")])
    leitura = gate_g4.ler_release(documento, {"1T2026": documento})
    assert leitura.contabil is None
    assert any("não extraída" in nota for nota in leitura.notas)


# --------------------------------------------------------------------------- #
# Classificação — o coração do gate
# --------------------------------------------------------------------------- #


def _leitura(**kwargs) -> gate_g4.LeituraRelease:
    padrao = {
        "documento": "x_release_1T2026",
        "empresa": "X",
        "trimestre": "1T2026",
    }
    return gate_g4.LeituraRelease(**{**padrao, **kwargs})


def _celula(valor: float, bruto: str = "") -> gate_g4.CelulaLocalizada:
    return gate_g4.CelulaLocalizada(
        pagina=5,
        rotulo_linha="lucro liquido",
        rotulo_coluna="contabil",
        bruto=bruto or f"{valor:.0f}",
        valor=valor,
    )


def test_classificar_aprova_quando_o_painel_bate_com_a_linha_contabil():
    conferencia = gate_g4.classificar(
        _leitura(contabil=_celula(6067.0)),
        6_066_721_000.0,
        6_139_265_000.0,
        "arquivado",
    )
    assert conferencia.aprovado
    assert conferencia.situacao == gate_g4.SITUACAO_CONFERIDO_CONTABIL


def test_classificar_aprova_pela_linha_ifrs_quando_a_contabil_e_outra_base():
    conferencia = gate_g4.classificar(
        _leitura(
            contabil=_celula(11938.0),
            ifrs_controladores=11636.0,
            ifrs_tolerancia=0.5,
        ),
        11_636_000_000.0,
        11_875_000_000.0,
        "arquivado",
    )
    assert conferencia.aprovado
    assert conferencia.situacao == gate_g4.SITUACAO_CONFERIDO_IFRS
    assert conferencia.delta_contabil_mi() == pytest.approx(-302.0)


def test_classificar_nao_aprova_quando_o_release_nao_publica_a_base_do_painel():
    """Sem âncora não é aprovação: aprovar aqui seria inventar evidência."""
    conferencia = gate_g4.classificar(
        _leitura(contabil=_celula(3725.0)),
        3_217_994_000.0,
        3_281_550_000.0,
        "arquivado",
    )
    assert conferencia.situacao == gate_g4.SITUACAO_SEM_ANCORA
    assert not conferencia.aprovado
    assert not conferencia.reprovado


def test_classificar_reprova_quando_a_ponte_existe_e_o_painel_nao_fecha():
    """O caso que o gate existe para pegar: mapa resolveu a linha errada."""
    conferencia = gate_g4.classificar(
        _leitura(
            contabil=_celula(11938.0),
            ifrs_controladores=11636.0,
            ifrs_tolerancia=0.5,
        ),
        13_759_000_000.0,  # resultado antes da tributação, não o lucro
        11_875_000_000.0,
        "arquivado",
    )
    assert conferencia.reprovado
    assert conferencia.situacao == gate_g4.SITUACAO_DIVERGENTE


def test_classificar_nao_aceita_diferenca_maior_que_a_meia_unidade_impressa():
    """Tolerância é a meia-unidade do dígito impresso, não folga arbitrária."""
    conferencia = gate_g4.classificar(
        _leitura(contabil=_celula(4570.4, bruto="4.570,4")),
        4_570_460_000.0,  # 0,06 R$ mi acima — passa da meia-unidade 0,05
        None,
        "arquivado",
    )
    assert conferencia.situacao == gate_g4.SITUACAO_SEM_ANCORA


def test_classificar_sem_extracao_quando_falta_a_linha_contabil():
    conferencia = gate_g4.classificar(_leitura(), 1.0, 2.0, "arquivado")
    assert conferencia.situacao == gate_g4.SITUACAO_SEM_EXTRACAO
    assert not conferencia.aprovado and not conferencia.reprovado


def test_delta_gerencial_e_medicao_nao_bloqueante():
    """A capa é gerencial e não bate por definição — medir, nunca ancorar."""
    conferencia = gate_g4.classificar(
        _leitura(contabil=_celula(11938.0), gerencial=_celula(12282.0)),
        11_938_000_000.0,
        None,
        "arquivado",
    )
    assert conferencia.aprovado
    assert conferencia.delta_gerencial_mi() == pytest.approx(344.0)


# --------------------------------------------------------------------------- #
# Varredura pelo valor do painel dentro do release
# --------------------------------------------------------------------------- #


def test_varredura_acha_o_valor_em_qualquer_escala_e_mede_a_distancia():
    documento = _documento(
        "X",
        "1T2026",
        [(1, "Lucro de R$ 11.636 milhões."), (2, "Nada aqui.")],
    )
    varredura = gate_g4.varrer_valor_no_release(documento, 11_636_000_000.0)
    assert varredura.paginas == (1,)
    assert varredura.melhor_distancia_pct == pytest.approx(0.0)


def test_varredura_devolve_ausencia_mas_ainda_informa_o_mais_proximo():
    documento = _documento("X", "1T2026", [(1, "Despesa de R$ 1.928 milhões.")])
    varredura = gate_g4.varrer_valor_no_release(documento, 4_760_641_000.0)
    assert varredura.paginas == ()
    assert varredura.melhor_valor is not None
    assert varredura.melhor_distancia_pct > 0.05


# --------------------------------------------------------------------------- #
# Painel — fixture mínima em DuckDB temporário, nunca o arquivo real
# --------------------------------------------------------------------------- #


@pytest.fixture
def painel_minimo(tmp_path: Path) -> Path:
    caminho = tmp_path / "painel.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute(
        "CREATE TABLE fatos_semanticos ("
        "cd_cvm VARCHAR, trimestre VARCHAR, conceito VARCHAR, "
        "valor_reais DOUBLE, origem VARCHAR)"
    )
    con.executemany(
        "INSERT INTO fatos_semanticos VALUES (?, ?, ?, ?, ?)",
        [
            ("019348", "1T2026", CONCEITO_LUCRO_CONTROLADORES, 11.636e9, "arquivado"),
            ("019348", "1T2026", CONCEITO_LUCRO_CONSOLIDADO, 11.875e9, "arquivado"),
            (
                "019348",
                "1T2026",
                CONCEITO_LUCRO_NAO_CONTROLADORES,
                0.239e9,
                "arquivado",
            ),
            ("022616", "4T2025", CONCEITO_LUCRO_CONTROLADORES, 4.386070e9, "derivado"),
            ("022616", "4T2025", CONCEITO_LUCRO_CONSOLIDADO, 4.502928e9, "derivado"),
        ],
    )
    con.close()
    return caminho


def test_lucros_do_painel_le_a_visao_semantica_e_nomeia_os_bancos(painel_minimo):
    painel = gate_g4.lucros_do_painel(painel_minimo)
    assert painel[("ITAU", "1T2026")][0] == pytest.approx(11.636e9)
    assert painel[("ITAU", "1T2026")][1] == pytest.approx(11.875e9)
    assert painel[("BTG", "4T2025")][3] == "derivado"


def test_lucros_do_painel_nao_consulta_fatos_contabeis(painel_minimo, monkeypatch):
    """RN09: o consumidor consulta `fatos_semanticos`, nunca a tabela crua."""
    executadas: list[str] = []
    original = duckdb.DuckDBPyConnection.execute

    def espiao(self, sql, *args, **kwargs):
        executadas.append(sql)
        return original(self, sql, *args, **kwargs)

    monkeypatch.setattr(duckdb.DuckDBPyConnection, "execute", espiao)
    gate_g4.lucros_do_painel(painel_minimo)
    assert executadas
    assert not any("fatos_contabeis" in sql for sql in executadas)


# --------------------------------------------------------------------------- #
# Cache de OCR e relatório
# --------------------------------------------------------------------------- #


def test_carregar_cache_ocr_le_documento_empresa_trimestre_e_paginas(tmp_path: Path):
    (tmp_path / "abc.json").write_text(
        json.dumps(
            {
                "documento": "itau_release_1T2026",
                "empresa": "ITAU",
                "trimestre": "1T2026",
                "hash_pdf": "a" * 64,
                "ocr": {"pages": [{"index": 5, "markdown": CONCILIACAO_ITAU}]},
            }
        ),
        encoding="utf-8",
    )
    (documento,) = gate_g4.carregar_cache_ocr(tmp_path)
    assert documento.empresa == "ITAU"
    assert documento.paginas[0][0] == 5


def test_relatorio_reprova_o_conjunto_quando_uma_celula_diverge():
    divergente = gate_g4.classificar(
        _leitura(
            contabil=_celula(11938.0),
            ifrs_controladores=11636.0,
            ifrs_tolerancia=0.5,
        ),
        13_759_000_000.0,
        None,
        "arquivado",
    )
    texto = gate_g4.montar_relatorio([divergente], "APROVADO", [])
    assert "## Veredito: **REPROVADO**" in texto


def test_relatorio_e_parcial_quando_falta_ancora_e_nada_diverge():
    sem_ancora = gate_g4.classificar(
        _leitura(contabil=_celula(3725.0)), 3_217_994_000.0, None, "arquivado"
    )
    texto = gate_g4.montar_relatorio([sem_ancora], "APROVADO", [])
    assert "## Veredito: **PARCIAL**" in texto
    assert "REPROVADO" not in texto.split("## Detalhe")[0]


def test_relatorio_aprova_so_quando_todas_as_celulas_conferem():
    conferida = gate_g4.classificar(
        _leitura(contabil=_celula(6067.0)), 6_066_721_000.0, None, "arquivado"
    )
    texto = gate_g4.montar_relatorio([conferida], "APROVADO", [])
    assert "## Veredito: **APROVADO**" in texto


def test_relatorio_expoe_o_gap_de_fechamento_do_painel():
    conferida = gate_g4.classificar(
        _leitura(contabil=_celula(6067.0)), 6_066_721_000.0, None, "arquivado"
    )
    texto = gate_g4.montar_relatorio(
        [conferida], "APROVADO", [("SANTANDER", "3T2025", 356_909_000.0)]
    )
    assert "| SANTANDER | 3T2025 | 356.909 |" in texto


def test_receitas_cobrem_os_cinco_bancos_do_corpus():
    """Receita faltando é banco silenciosamente fora do gate."""
    esperados = {"BB", "BRADESCO", "BTG", "ITAU", "SANTANDER"}
    assert set(gate_g4.PAGINA_CONCILIACAO) == esperados
    assert set(gate_g4.LINHA_LUCRO_CONTABIL) == esperados
    assert set(gate_g4.COLUNA_PERIODO) == set(gate_g4.TRIMESTRES_CORPUS)


def test_veredito_parcial_nao_sai_com_codigo_zero():
    """Sair 0 sem âncora faria automação ler ausência de prova como aprovação."""
    assert gate_g4.SAIDA_POR_VEREDITO[gate_g4.VEREDITO_APROVADO] == 0
    assert gate_g4.SAIDA_POR_VEREDITO[gate_g4.VEREDITO_PARCIAL] != 0
    assert gate_g4.SAIDA_POR_VEREDITO[gate_g4.VEREDITO_REPROVADO] != 0


def test_veredito_reprova_quando_a_parte_a_reprova():
    """Mapa errado reprova o gate inteiro, mesmo com a parte B toda conferida."""
    conferida = gate_g4.classificar(
        _leitura(contabil=_celula(6067.0)), 6_066_721_000.0, None, "arquivado"
    )
    assert (
        gate_g4.veredito_do_gate([conferida], gate_g4.VEREDITO_REPROVADO)
        == gate_g4.VEREDITO_REPROVADO
    )


def test_veredito_nao_aprova_conjunto_vazio():
    """Zero conferência não é aprovação — é gate que não rodou."""
    assert gate_g4.veredito_do_gate([], gate_g4.VEREDITO_APROVADO) != (
        gate_g4.VEREDITO_APROVADO
    )


@pytest.mark.parametrize(
    "trimestre, curto, esperado",
    [
        ("2T2025", False, "2t 2025"),
        ("2T2025", True, "2t25"),
        ("1T2026", False, "1t 2026"),
        ("1T2026", True, "1t26"),
    ],
)
def test_rotulo_trimestre_cobre_os_dois_formatos_de_release(
    trimestre, curto, esperado
):
    assert gate_g4.rotulo_trimestre(trimestre, curto=curto) == esperado


def test_gerencial_do_bb_vem_de_outra_linha_e_nao_de_outra_coluna():
    """No BB o destaque é `Lucro Líquido Ajustado`, logo acima do contábil."""
    documento = _documento("BB", "2T2025", [(17, CONCILIACAO_BB)])
    leitura = gate_g4.ler_release(documento, {"2T2025": documento})
    assert leitura.contabil is not None and leitura.contabil.valor == 3035.0
    assert leitura.gerencial is not None and leitura.gerencial.valor == 3784.0


def test_gerencial_do_btg_nao_confunde_o_trimestre_com_o_acumulado_do_ano():
    """A tabela do BTG tem duas colunas `Ajustado`; casar as duas é ambiguidade."""
    pagina = """# Lucro líquido e ROAE Ajustado (não auditados)

|  Lucro Líquido e ROAE Ajustado (não auditado) | 2T 2025 Contábil | Itens Não Recorrentes & Ágio | 2T 2025 Ajustado | 6M 2025 Ajustado  |
| --- | --- | --- | --- | --- |
|  **Lucro líquido** | **4.009,2** | **172,9** | **4.182,1** | **7.549,1**  |
"""
    documento = _documento("BTG", "2T2025", [(5, pagina)])
    leitura = gate_g4.ler_release(documento, {"2T2025": documento})
    assert leitura.contabil is not None and leitura.contabil.valor == 4009.2
    assert leitura.gerencial is not None
    assert leitura.gerencial.valor == 4182.1, "pegou o acumulado 6M (7.549,1)"


def test_relatorio_diz_o_que_falta_quando_o_gate_fica_parcial():
    sem_ancora = gate_g4.classificar(
        _leitura(empresa="SANTANDER", contabil=_celula(3725.0)),
        3_217_994_000.0,
        None,
        "arquivado",
    )
    texto = gate_g4.montar_relatorio([sem_ancora], "APROVADO", [])
    assert "## O que falta para fechar o gate" in texto
    assert "SANTANDER" in texto.split("## O que falta")[1].split("##")[0]


# =========================================================================== #
# scripts/ancora_ifrs.py — leitura das demonstrações em IFRS
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Anos das colunas: a regressão que apagou dois emissores inteiros
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "cabecalho, colunas, esperado",
    [
        # Banco do Brasil: o ano é seguido do ordinal da coluna seguinte. Colar
        # os espaços antes de procurar funde `2025 1º` em `20251º`, mata a
        # fronteira de palavra e devolve UM ano onde há dois — o bug que fazia o
        # BB e o Santander inteiros deixarem de resolver, sem erro visível.
        ("Nota 1º Trimestre/2025 1º Trimestre/2024", 2, (2025, 2024)),
        ("Nota 1º Trimestre/2026 1º Trimestre/2025", 2, (2026, 2025)),
        ("Nota Exercício/2025 Exercício/2024", 2, (2025, 2024)),
        # BTG: o extrator parte a data (`No ta`, `3 0/06/2025`). A barra já é
        # fronteira de palavra suficiente — o texto original resolve.
        ("No ta 3 0/06/2025 3 0/06/2024 30/06/2025 3 0/06/2024", 4, (2025, 2024, 2025, 2024)),
        ("No ta 31/03/2025 31/03/2024", 2, (2025, 2024)),
        # Santander anual: três exercícios comparativos, sem barra nenhuma.
        ("Nota Explicativa 2025 2024 2023", 3, (2025, 2024, 2023)),
    ],
)
def test_anos_das_colunas_le_o_cabecalho_real_de_cada_emissor(
    cabecalho, colunas, esperado
):
    assert ancora_ifrs.anos_das_colunas((cabecalho,), colunas) == esperado


def test_anos_das_colunas_nao_cola_espacos_quando_o_texto_original_ja_resolve():
    """A regressão, isolada: colar espaços aqui devolveria só `(2025,)`."""
    linha = "Nota 1º Trimestre/2025 1º Trimestre/2024"
    colado = ancora_ifrs.PADRAO_ANO.findall(linha.replace(" ", ""))
    assert colado == ["2024"], "premissa do teste mudou: a colagem não perde mais o ano"
    assert ancora_ifrs.anos_das_colunas((linha,), 2) == (2025, 2024)


def test_anos_das_colunas_ainda_cola_espacos_quando_o_ano_vem_partido():
    """A colagem sobrevive como último recurso, não como caminho principal."""
    assert ancora_ifrs.anos_das_colunas(("Exercício/20 25 | Exercício/20 24",), 2) == (
        2025,
        2024,
    )


def test_anos_das_colunas_usa_a_ultima_linha_que_nomeia_todas_as_colunas():
    """O título cita anos em prosa antes do cabeçalho real, que fica embaixo."""
    cabecalho = (
        "Comparativo dos exercícios de 2024 e 2023",
        "Nota 31/03/2026 31/03/2025",
    )
    assert ancora_ifrs.anos_das_colunas(cabecalho, 2) == (2026, 2025)


def test_anos_das_colunas_falha_em_vez_de_devolver_lista_incompleta():
    with pytest.raises(ancora_ifrs.LeituraIFRSError, match="nenhuma linha de cabeçalho"):
        ancora_ifrs.anos_das_colunas(("Nota 31/03/2026",), 2)


@pytest.mark.parametrize(
    "anos, alvo, esperado", [((2026, 2025), 2026, 0), ((2025, 2024, 2023), 2024, 1)]
)
def test_coluna_do_ano_devolve_a_unica_coluna(anos, alvo, esperado):
    assert ancora_ifrs.coluna_do_ano(anos, alvo) == esperado


@pytest.mark.parametrize("anos, alvo", [((2025, 2025), 2025), ((2026, 2025), 2024)])
def test_coluna_do_ano_recusa_ambiguidade_e_ausencia(anos, alvo):
    """Ano repetido ou ausente é erro — escolher seria chutar a coluna."""
    with pytest.raises(ancora_ifrs.LeituraIFRSError):
        ancora_ifrs.coluna_do_ano(anos, alvo)


# --------------------------------------------------------------------------- #
# Leitura da página da DRE
# --------------------------------------------------------------------------- #

# Recorte da DRE consolidada em IFRS, no formato que o `pdfplumber` devolve:
# texto corrido, número com separador de milhar, parênteses no negativo. Duas
# colunas (trimestre isolado, comparativo). A linha do **resultado abrangente**
# está presente de propósito: o rótulo dela é quase o da linha de resultado, e
# confundir as duas devolveria número plausível e errado.
PAGINA_DRE_IFRS = """Demonstração Consolidada do Resultado
Nota 1º Trimestre/2026 1º Trimestre/2025
Receitas com juros e similares 42.434.400 38.750.550
Impostos sobre a renda 12 (1.428.535) (1.468.284)
Lucro líquido consolidado do período 3.281.550 3.151.583
Atribuível aos acionistas controladores 3.217.994 3.108.800
Atribuível aos acionistas não controladores 63.556 42.783
Total do resultado abrangente atribuível à controladora 9.999.999 8.888.888
"""


def test_ler_dre_da_pagina_separa_as_tres_linhas_do_trio():
    dre = ancora_ifrs.ler_dre_da_pagina(PAGINA_DRE_IFRS)
    assert dre is not None
    assert dre.consolidado == (3_281_550.0, 3_151_583.0)
    assert dre.controladores == (3_217_994.0, 3_108_800.0)
    assert dre.nao_controladores == (63_556.0, 42_783.0)


def test_ler_dre_da_pagina_nao_confunde_resultado_com_resultado_abrangente():
    """`Total do resultado abrangente atribuível à controladora` é outra linha."""
    dre = ancora_ifrs.ler_dre_da_pagina(PAGINA_DRE_IFRS)
    assert dre is not None
    assert 9_999_999.0 not in dre.controladores


def test_ler_dre_da_pagina_confere_a_identidade_do_trio():
    dre = ancora_ifrs.ler_dre_da_pagina(PAGINA_DRE_IFRS)
    assert dre is not None
    assert all(dre.identidade_fecha(j) for j in range(dre.colunas))


def test_ler_dre_da_pagina_devolve_none_quando_a_pagina_nao_e_a_dre():
    """"Não é aqui" é diferente de "é aqui e está ilegível"."""
    assert ancora_ifrs.ler_dre_da_pagina("Notas explicativas\nNada de resultado.") is None


def test_ler_dre_da_pagina_recusa_linhas_com_numeros_de_colunas_diferentes():
    pagina = (
        "Lucro líquido consolidado do período 3.281.550 3.151.583\n"
        "Atribuível aos acionistas controladores 3.217.994\n"
        "Atribuível aos acionistas não controladores 63.556 42.783\n"
    )
    with pytest.raises(ancora_ifrs.LeituraIFRSError, match="colunas diferentes"):
        ancora_ifrs.ler_dre_da_pagina(pagina)


@pytest.mark.parametrize(
    "linha, esperado",
    [
        ("Impostos sobre a renda 12 (1.428.535) (1.468.284)", (-1428535.0, -1468284.0)),
        ("Lucro por ação básico e diluído (R$) 2,40 4,62", ()),
        ("Nota 26 sem valor", ()),
    ],
)
def test_numeros_da_linha_ignora_indice_de_nota_e_le_o_parentese_como_negativo(
    linha, esperado
):
    assert ancora_ifrs.numeros_da_linha(linha) == esperado


def test_proporcao_ilegivel_mede_glifo_sem_mapa_de_caracteres():
    """A peça anual do BTG cai aqui: 63 de 71 páginas sem mapa na fonte."""
    assert ancora_ifrs.proporcao_ilegivel("Lucro líquido 3.281.550") == 0.0
    assert ancora_ifrs.proporcao_ilegivel("(cid:41)(cid:42)(cid:43)") > 0.5
    assert ancora_ifrs.proporcao_ilegivel("") == 0.0


# --------------------------------------------------------------------------- #
# Separação trimestre × acumulado — a ordem das colunas NÃO é convenção
# --------------------------------------------------------------------------- #


def _dre(
    controladores: tuple[float, ...],
    consolidado: tuple[float, ...] | None = None,
    nao_controladores: tuple[float, ...] | None = None,
    cabecalho: tuple[str, ...] = (),
) -> ancora_ifrs.LinhasDRE:
    nao = nao_controladores or tuple(0.0 for _ in controladores)
    cons = consolidado or tuple(c + n for c, n in zip(controladores, nao))
    return ancora_ifrs.LinhasDRE(
        consolidado=cons,
        controladores=controladores,
        nao_controladores=nao,
        cabecalho=cabecalho,
        rotulo_controladores="atribuivel aos acionistas controladores",
    )


def test_separar_colunas_resolve_o_acumulado_primeiro_como_no_bb():
    """No BB o acumulado do exercício vem antes do trimestre isolado."""
    dre = _dre((5_019_384.0, 2_782_083.0))
    assert ancora_ifrs.separar_trimestre_e_acumulado(dre, 2_237_301.0) == (1, 0)


def test_separar_colunas_resolve_o_trimestre_primeiro_como_no_santander():
    """No BTG e no Santander a ordem é a inversa — ler por posição erraria um."""
    dre = _dre((1_928_066.0, 5_036_867.0))
    assert ancora_ifrs.separar_trimestre_e_acumulado(dre, 3_108_800.0) == (0, 1)


def test_separar_colunas_recusa_quando_mais_de_um_par_satisfaz_a_identidade():
    dre = _dre((100.0, 300.0, 500.0, 700.0))
    with pytest.raises(ancora_ifrs.LeituraIFRSError, match="pares candidatos"):
        ancora_ifrs.separar_trimestre_e_acumulado(dre, 200.0)


def test_separar_colunas_recusa_quando_nenhum_par_satisfaz_a_identidade():
    dre = _dre((1_928_066.0, 5_036_867.0))
    with pytest.raises(ancora_ifrs.LeituraIFRSError, match="pares candidatos"):
        ancora_ifrs.separar_trimestre_e_acumulado(dre, 42.0)


# --------------------------------------------------------------------------- #
# Cadeia de períodos, ponta a ponta, sem abrir PDF
# --------------------------------------------------------------------------- #


def _demonstracao(
    periodo: str, dre: ancora_ifrs.LinhasDRE, pagina: int = 7
) -> ancora_ifrs.DemonstracaoIFRS:
    return ancora_ifrs.DemonstracaoIFRS(
        empresa="SANTANDER",
        periodo=periodo,
        documento=f"santander_ifrs_{periodo}",
        pagina=pagina,
        dre=dre,
    )


@pytest.fixture
def cadeia_santander() -> dict[str, object]:
    """Os números reais do Santander, em R$ mil, na ordem em que ele publica.

    O trimestre isolado vem **antes** do acumulado, e o 4T não é publicado.
    """
    return {
        "1T2025": _demonstracao(
            "1T2025",
            _dre(
                (3_108_800.0, 3_052_046.0),
                nao_controladores=(42_783.0, 8_882.0),
                cabecalho=("Explicativas 31/03/2025 31/03/2024",),
            ),
        ),
        "2T2025": _demonstracao(
            "2T2025",
            _dre(
                (1_928_066.0, 3_617_479.0, 5_036_867.0, 6_669_523.0),
                nao_controladores=(59_866.0, 15_949.0, 102_649.0, 24_831.0),
            ),
        ),
        "3T2025": _demonstracao(
            "3T2025",
            _dre(
                (3_828_204.0, 3_637_202.0, 8_865_071.0, 10_306_727.0),
                nao_controladores=(54_206.0, 12_342.0, 156_855.0, 37_173.0),
            ),
        ),
        "4T2025": _demonstracao(
            "4T2025",
            _dre(
                (12_766_035.0, 13_365_506.0, 9_449_313.0),
                nao_controladores=(199_088.0, 48_257.0, 49_499.0),
                cabecalho=("Nota Explicativa 2025 2024 2023",),
            ),
            pagina=17,
        ),
        "1T2026": _demonstracao(
            "1T2026",
            _dre(
                (3_217_994.0, 3_108_800.0),
                nao_controladores=(63_556.0, 42_783.0),
                cabecalho=("Explicativas 31/03/2026 31/03/2025",),
            ),
            pagina=11,
        ),
    }


def test_resolver_cadeia_devolve_os_quatro_trimestres_da_janela(cadeia_santander):
    ancoras, ausencias = ancora_ifrs.resolver_cadeia("SANTANDER", cadeia_santander)
    assert ausencias == {}
    assert ancoras["2T2025"].valor_reais == pytest.approx(1_928_066_000.0)
    assert ancoras["3T2025"].valor_reais == pytest.approx(3_828_204_000.0)
    assert ancoras["1T2026"].valor_reais == pytest.approx(3_217_994_000.0)


def test_resolver_cadeia_deriva_o_quarto_trimestre_por_exercicio_menos_nove_meses(
    cadeia_santander,
):
    """RN10: o 4T não existe como peça própria e sai marcado como derivado."""
    ancoras, _ = ancora_ifrs.resolver_cadeia("SANTANDER", cadeia_santander)
    quarto = ancoras["4T2025"]
    assert quarto.derivado is True
    assert quarto.valor_reais == pytest.approx((12_766_035.0 - 8_865_071.0) * 1_000)
    # Duas parcelas impressas ⇒ duas meias-unidades de R$ mil.
    assert quarto.tolerancia_reais == pytest.approx(1_000.0)
    assert "derivado" in quarto.procedencia


def test_resolver_cadeia_carrega_o_trio_para_localizar_divergencia(cadeia_santander):
    """Sem consolidado e não controladores, o gate não sabe DIZER onde erra."""
    ancoras, _ = ancora_ifrs.resolver_cadeia("SANTANDER", cadeia_santander)
    terceiro = ancoras["3T2025"]
    assert terceiro.consolidado_reais == pytest.approx(3_882_410_000.0)
    assert terceiro.nao_controladores_reais == pytest.approx(54_206_000.0)


def test_procedencia_preserva_as_virgulas_da_prosa(cadeia_santander):
    """Regressão: `.replace(",", ".")` na frase inteira comia a pontuação.

    O separador de milhar do número é ponto em pt-BR, mas trocar a vírgula na
    frase toda devolvia `documento. pág. 7. linha …` e destruía a procedência,
    que é justamente o que faz o gate auditável.
    """
    ancoras, _ = ancora_ifrs.resolver_cadeia("SANTANDER", cadeia_santander)
    procedencia = ancoras["3T2025"].procedencia
    assert "santander_ifrs_3T2025, pág. 7, linha" in procedencia
    assert "3.828.204 (R$ mil)" in procedencia


def test_milhar_formata_sem_tocar_no_resto_da_frase():
    assert ancora_ifrs.milhar(12_766_035.0) == "12.766.035"
    assert ancora_ifrs.milhar(-356_909.0) == "-356.909"


def test_resolver_cadeia_registra_ausencia_com_motivo_em_vez_de_estimar(
    cadeia_santander,
):
    """Peça ilegível não vira zero nem interpolação: vira ausência com motivo."""
    cadeia_santander["4T2025"] = ancora_ifrs.DocumentoIlegivel(
        empresa="SANTANDER",
        periodo="4T2025",
        documento="santander_ifrs_4T2025",
        motivo="63 de 71 páginas sem mapa de caracteres na fonte embutida",
    )
    ancoras, ausencias = ancora_ifrs.resolver_cadeia("SANTANDER", cadeia_santander)
    assert "4T2025" not in ancoras
    assert "sem mapa de caracteres" in ausencias["4T2025"]


def test_resolver_cadeia_falha_se_a_coluna_comparativa_nao_reproduz_a_semente(
    cadeia_santander,
):
    """Última trava contra ordem de coluna suposta em vez de conferida."""
    cadeia_santander["1T2026"] = _demonstracao(
        "1T2026",
        _dre(
            (3_217_994.0, 9_999_999.0),
            cabecalho=("Explicativas 31/03/2026 31/03/2025",),
        ),
        pagina=11,
    )
    with pytest.raises(ancora_ifrs.LeituraIFRSError, match="não reproduz o 1T2025"):
        ancora_ifrs.resolver_cadeia("SANTANDER", cadeia_santander)


# --------------------------------------------------------------------------- #
# Manifesto e hash — a evidência do gate é pinada
# --------------------------------------------------------------------------- #


@pytest.fixture
def manifesto_minimo(tmp_path: Path) -> tuple[Path, Path]:
    raw = tmp_path / "raw"
    raw.mkdir()
    peca = raw / "x_ifrs_1T2026.pdf"
    peca.write_bytes(b"conteudo da peca")
    csv = tmp_path / "manifesto_ifrs.csv"
    csv.write_text(
        "empresa,cd_cvm,periodo,documento,titulo_publicado,arquivo,url,"
        "data_download,tamanho_bytes,hash_sha256\n"
        "X,000001,1T2026,x_ifrs_1T2026,Título,x_ifrs_1T2026.pdf,https://ex/a,"
        f"2026-08-11,16,{ancora_ifrs.hash_do_arquivo(peca)}\n",
        encoding="utf-8",
    )
    return csv, raw


def test_carregar_manifesto_le_url_data_e_hash(manifesto_minimo):
    csv, _ = manifesto_minimo
    (item,) = ancora_ifrs.carregar_manifesto(csv)
    assert item.empresa == "X"
    assert item.url == "https://ex/a"
    assert item.data_download == "2026-08-11"
    assert len(item.hash_sha256) == 64


def test_hash_confere_e_a_peca_e_lida(manifesto_minimo, monkeypatch):
    csv, raw = manifesto_minimo
    lidas: list[str] = []

    def falso_ler(caminho, empresa, periodo, documento):
        lidas.append(documento)
        return ancora_ifrs.DocumentoIlegivel(empresa, periodo, documento, "stub")

    monkeypatch.setattr(ancora_ifrs, "ler_demonstracao", falso_ler)
    ancora_ifrs.carregar_demonstracoes("X", ancora_ifrs.carregar_manifesto(csv), raw)
    assert lidas == ["x_ifrs_1T2026"]


def test_hash_divergente_nao_e_lido_e_vira_ausencia_com_motivo(
    manifesto_minimo, monkeypatch
):
    """Risco 15d: o emissor republica o PDF e o gate mudaria de veredito sozinho."""
    csv, raw = manifesto_minimo
    (raw / "x_ifrs_1T2026.pdf").write_bytes(b"outro conteudo, republicado")

    def nunca(*_args, **_kwargs):  # pragma: no cover - o teste falha se rodar
        raise AssertionError("leu uma peça cujo hash não confere com o manifesto")

    monkeypatch.setattr(ancora_ifrs, "ler_demonstracao", nunca)
    demonstracoes = ancora_ifrs.carregar_demonstracoes(
        "X", ancora_ifrs.carregar_manifesto(csv), raw
    )
    item = demonstracoes["1T2026"]
    assert isinstance(item, ancora_ifrs.DocumentoIlegivel)
    assert "hash" in item.motivo


def test_peca_ausente_no_disco_vira_ausencia_com_motivo(manifesto_minimo):
    csv, raw = manifesto_minimo
    (raw / "x_ifrs_1T2026.pdf").unlink()
    demonstracoes = ancora_ifrs.carregar_demonstracoes(
        "X", ancora_ifrs.carregar_manifesto(csv), raw
    )
    item = demonstracoes["1T2026"]
    assert isinstance(item, ancora_ifrs.DocumentoIlegivel)
    assert "não no disco" in item.motivo


def test_carregar_ancoras_nao_exporta_a_semente_de_1t2025(monkeypatch):
    """`1T2025` é semente da cadeia, não célula do gate: fora da janela."""
    monkeypatch.setattr(
        ancora_ifrs, "carregar_demonstracoes", lambda *_a, **_k: {}
    )
    monkeypatch.setattr(
        ancora_ifrs,
        "resolver_cadeia",
        lambda empresa, _d: (
            {
                periodo: ancora_ifrs.AncoraIFRS(
                    empresa=empresa,
                    trimestre=periodo,
                    valor_reais=1.0,
                    derivado=False,
                    tolerancia_reais=500.0,
                    procedencia="",
                )
                for periodo in ("1T2025", "2T2025")
            },
            {},
        ),
    )
    manifesto = (
        ancora_ifrs.ItemManifesto("X", "1", "1T2025", "d", "a.pdf", "u", "d", "h"),
    )
    ancoras, _ = ancora_ifrs.carregar_ancoras(manifesto)
    assert set(ancoras) == {("X", "2T2025")}


# =========================================================================== #
# Integração: a âncora externa no gate
# =========================================================================== #


def _ancora(valor_reais: float, **extras) -> ancora_ifrs.AncoraIFRS:
    padrao = {
        "empresa": "SANTANDER",
        "trimestre": "3T2025",
        "derivado": False,
        "tolerancia_reais": 500.0,
        "procedencia": "santander_ifrs_3T2025, pág. 7, linha “x”",
    }
    return ancora_ifrs.AncoraIFRS(valor_reais=valor_reais, **{**padrao, **extras})


def test_ancora_externa_preenche_a_leitura_e_registra_a_fonte():
    leitura = _leitura(contabil=_celula(3944.0))
    com_ancora = gate_g4.aplicar_ancora_externa(leitura, _ancora(3_828_204_000.0))
    assert com_ancora.ifrs_controladores == pytest.approx(3828.204)
    assert com_ancora.ifrs_tolerancia == pytest.approx(0.0005)
    assert com_ancora.ifrs_fonte == gate_g4.FONTE_DEMONSTRACAO_SEPARADA
    assert "santander_ifrs_3T2025" in com_ancora.ifrs_procedencia


def test_ancora_externa_sem_ancora_guarda_o_motivo_da_ausencia():
    leitura = gate_g4.aplicar_ancora_externa(
        _leitura(contabil=_celula(4390.5)), None, "63 de 71 páginas sem mapa"
    )
    assert leitura.ifrs_controladores is None
    assert "sem mapa" in leitura.ifrs_ausencia


@pytest.mark.parametrize(
    "pagina_ponte, trimestre, contabil, painel_reais, situacao_esperada",
    [
        (
            PONTE_ITAU_INTEGRA,
            "1T2026",
            11938.0,
            11_636_000_000.0,
            gate_g4.SITUACAO_CONFERIDO_IFRS,
        ),
        (
            PONTE_ITAU_MUTILADA,
            "3T2025",
            11561.0,
            11_306_000_000.0,
            gate_g4.SITUACAO_CONFERIDO_IFRS,
        ),
    ],
)
def test_ancora_externa_nao_altera_celula_ja_conferida_pela_ponte_do_release(
    pagina_ponte, trimestre, contabil, painel_reais, situacao_esperada
):
    """Itaú e Bradesco já fecham pela ponte do próprio release — não se mexe.

    A âncora intrusa é absurda de propósito (R$ 1,00): se a integração deixasse
    a peça externa sobrepor a ponte, a célula viraria DIVERGENTE e o teste
    quebraria. O gate tem de preferir a evidência do mesmo documento.
    """
    conciliacao = CONCILIACAO_ITAU.replace("11.938", f"{contabil:,.0f}".replace(",", "."))
    documento = _documento("ITAU", trimestre, [(5, conciliacao), (29, pagina_ponte)])
    leitura = gate_g4.ler_release(documento, {trimestre: documento})

    antes = gate_g4.classificar(leitura, painel_reais, None, "arquivado")
    depois = gate_g4.classificar(
        gate_g4.aplicar_ancora_externa(leitura, _ancora(1.0)),
        painel_reais,
        None,
        "arquivado",
    )
    assert antes.situacao == situacao_esperada
    assert depois == antes


def test_ancora_externa_nao_altera_a_celula_conferida_pela_linha_contabil():
    """Bradesco 2T2025: a linha contábil já bate e a ponte coincide com ela."""
    documento = _documento(
        "BRADESCO", "2T2025", [(47, CONCILIACAO_E_PONTE_BRADESCO)]
    )
    leitura = gate_g4.ler_release(documento, {"2T2025": documento})
    antes = gate_g4.classificar(leitura, 5_030_000_000.0, None, "arquivado")
    depois = gate_g4.classificar(
        gate_g4.aplicar_ancora_externa(leitura, _ancora(1.0)),
        5_030_000_000.0,
        None,
        "arquivado",
    )
    assert antes.situacao == gate_g4.SITUACAO_CONFERIDO_CONTABIL
    assert depois == antes


def test_fonte_da_ancora_e_declarada_por_emissor_nao_pelo_acaso_da_extracao():
    """Emissor que publica a ponte nunca recebe âncora de outro documento.

    Nem quando a extração da ponte falha: cair noutra fonte em silêncio faria a
    mesma coluna do relatório comparar evidências diferentes conforme o dia.
    """
    for banco in BANCOS_CORPUS:
        sem_ponte_extraida = _leitura(empresa=banco.banco, contabil=_celula(1.0))
        resultado = gate_g4.aplicar_ancora_externa(sem_ponte_extraida, _ancora(7.0))
        if banco.banco in gate_g4.PAGINA_PONTE_IFRS:
            assert resultado.ifrs_controladores is None, banco.banco
        else:
            assert resultado.ifrs_fonte == gate_g4.FONTE_DEMONSTRACAO_SEPARADA
            assert resultado.ifrs_controladores == pytest.approx(7e-6)


def test_toda_situacao_conferida_tem_rotulo_de_fonte():
    """Sem rótulo por fonte, o relatório diria CONFERIDO sem dizer contra o quê."""
    assert set(gate_g4.SITUACAO_CONFERIDO_POR_FONTE) == {
        gate_g4.FONTE_PONTE_RELEASE,
        gate_g4.FONTE_DEMONSTRACAO_SEPARADA,
    }
    assert len(set(gate_g4.SITUACAO_CONFERIDO_POR_FONTE.values())) == 2


def test_classificar_aprova_pela_demonstracao_publicada_em_separado():
    """BB, BTG e Santander: a âncora vem de fora, e o relatório diz de onde."""
    leitura = gate_g4.aplicar_ancora_externa(
        _leitura(empresa="BB", contabil=_celula(3035.0)), _ancora(2_782_083_000.0)
    )
    conferencia = gate_g4.classificar(leitura, 2_782_083_000.0, None, "arquivado")
    assert conferencia.aprovado
    assert conferencia.situacao == gate_g4.SITUACAO_CONFERIDO_IFRS_SEPARADA
    assert conferencia.ifrs_fonte == gate_g4.FONTE_DEMONSTRACAO_SEPARADA


def test_classificar_separa_sem_ancora_por_ilegibilidade_de_sem_ancora_por_omissao():
    """"O emissor não publica" e "não consegui ler" levam a decisões diferentes."""
    omissao = gate_g4.classificar(
        _leitura(contabil=_celula(3725.0)), 3_217_994_000.0, None, "arquivado"
    )
    ilegivel = gate_g4.classificar(
        gate_g4.aplicar_ancora_externa(
            _leitura(contabil=_celula(4390.5)), None, "63 de 71 páginas sem mapa"
        ),
        4_386_070_000.0,
        None,
        "arquivado",
    )
    assert omissao.situacao == gate_g4.SITUACAO_SEM_ANCORA
    assert ilegivel.situacao == gate_g4.SITUACAO_SEM_ANCORA_ILEGIVEL
    assert "63 de 71 páginas" in ilegivel.detalhe
    # As duas são ausência de evidência, e nenhuma das duas aprova.
    assert omissao.sem_ancora and ilegivel.sem_ancora
    assert not omissao.aprovado and not ilegivel.aprovado
    assert not omissao.reprovado and not ilegivel.reprovado


def test_classificar_reprova_a_celula_que_diverge_da_ancora_externa():
    """Santander 3T2025: −363,8 R$ mi contra a demonstração auditada."""
    leitura = gate_g4.aplicar_ancora_externa(
        _leitura(empresa="SANTANDER", trimestre="3T2025", contabil=_celula(3944.0)),
        _ancora(3_828_204_000.0, consolidado_reais=3_882_410_000.0),
    )
    conferencia = gate_g4.classificar(
        leitura, 3_464_450_000.0, 3_882_410_000.0, "arquivado", 356_909_000.0
    )
    assert conferencia.reprovado
    assert conferencia.delta_ifrs_mi() == pytest.approx(-363.754)


def test_diagnostico_localiza_a_divergencia_na_atribuicao_entre_socios():
    """O total bate e o trio não fecha ⇒ o defeito é da origem, não do mapa."""
    leitura = gate_g4.aplicar_ancora_externa(
        _leitura(empresa="SANTANDER", trimestre="3T2025", contabil=_celula(3944.0)),
        _ancora(3_828_204_000.0, consolidado_reais=3_882_410_000.0),
    )
    diagnostico = gate_g4.diagnosticar_divergencia(
        leitura, 3_882_410_000.0, 356_909_000.0
    )
    assert "atribuição" in diagnostico
    assert "356.909" in diagnostico
    assert "não no mapa semântico" in diagnostico


def test_diagnostico_diz_quando_o_proprio_total_consolidado_diverge():
    """Se nem o total bate, a divergência não é só de repartição."""
    leitura = gate_g4.aplicar_ancora_externa(
        _leitura(empresa="X", contabil=_celula(3944.0)),
        _ancora(3_828_204_000.0, consolidado_reais=3_882_410_000.0),
    )
    diagnostico = gate_g4.diagnosticar_divergencia(leitura, 9_000_000_000.0, None)
    assert "total consolidado do painel também diverge" in diagnostico


# --------------------------------------------------------------------------- #
# Relatório: sem âncora e divergente nunca se confundem
# --------------------------------------------------------------------------- #


def _divergente(empresa: str = "SANTANDER", trimestre: str = "3T2025"):
    leitura = gate_g4.aplicar_ancora_externa(
        _leitura(empresa=empresa, trimestre=trimestre, contabil=_celula(3944.0)),
        _ancora(3_828_204_000.0, consolidado_reais=3_882_410_000.0),
    )
    return gate_g4.classificar(
        leitura, 3_464_450_000.0, 3_882_410_000.0, "arquivado", 356_909_000.0
    )


def test_relatorio_conta_divergente_e_sem_ancora_em_baldes_diferentes():
    sem_ancora = gate_g4.classificar(
        gate_g4.aplicar_ancora_externa(
            _leitura(empresa="BTG", trimestre="4T2025", contabil=_celula(4390.5)),
            None,
            "63 de 71 páginas sem mapa",
        ),
        4_386_070_000.0,
        None,
        "arquivado",
    )
    texto = gate_g4.montar_relatorio([_divergente(), sem_ancora], "APROVADO", [])
    assert "1 divergentes, 1 sem âncora" in texto
    assert "## Onde o painel diverge da âncora" in texto


def test_relatorio_publica_a_causa_apurada_da_celula_divergente():
    texto = gate_g4.montar_relatorio([_divergente()], "APROVADO", [])
    causa = gate_g4.INVESTIGACAO_DIVERGENCIA[("SANTANDER", "3T2025")]
    assert "### Causa apurada, célula a célula" in texto
    assert causa in texto


def test_relatorio_nao_herda_causa_para_divergencia_nao_investigada():
    """Uma divergência nova não pode pegar carona na explicação da vizinha."""
    nova = _divergente(empresa="BTG", trimestre="2T2025")
    assert ("BTG", "2T2025") not in gate_g4.INVESTIGACAO_DIVERGENCIA
    texto = gate_g4.montar_relatorio([nova], "APROVADO", [])
    assert "causa não identificada" in texto


def test_investigacao_registrada_aponta_para_celulas_que_existem():
    """Verbete órfão é explicação sem célula — e ninguém percebe."""
    bancos = {banco.banco for banco in BANCOS_CORPUS}
    for empresa, trimestre in gate_g4.INVESTIGACAO_DIVERGENCIA:
        assert empresa in bancos
        assert trimestre in gate_g4.TRIMESTRES_CORPUS


def test_relatorio_registra_quando_toda_celula_tem_ancora_medida():
    conferida = gate_g4.classificar(
        _leitura(contabil=_celula(6067.0)), 6_066_721_000.0, None, "arquivado"
    )
    texto = gate_g4.montar_relatorio([conferida], "APROVADO", [])
    assert "toda célula tem âncora medida" in texto


def test_tabela_do_relatorio_expoe_a_ancora_ifrs_e_o_delta_contra_ela():
    texto = gate_g4.montar_relatorio([_divergente()], "APROVADO", [])
    assert "| âncora IFRS | Δ painel−IFRS |" in texto
    assert "3.828,2" in texto
