"""Contrato da caixa de ferramentas da camada de agentes (RN04 · RN07 · RN09).

Nada aqui toca rede, LLM ou o `artefatos/cvm.duckdb` real: o painel é montado
das fixtures CSV de `tests/fixtures/cvm/` (as mesmas de
`test_dados_estruturados`), o recuperador é um duplo de teste e o índice de
cobertura é injetado.

Três coisas que estes testes travam e que não podem afrouxar:

1. **`prever_risco` não existe** (RN07) — nem como método, nem como nome no
   módulo, nem escondido em outro rótulo.
2. **As guardas de SQL não são reimplementadas aqui** (RN04/RN09): a caixa
   chama `src.dados_estruturados`, e uma consulta a `fatos_contabeis` é
   recusada **antes** de qualquer acesso ao banco.
3. **Teto de chamadas** (5.9.5): estourado, quem chamou tem o registro do que
   foi reunido — nunca um laço aberto pagando token.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cobertura import Companhia, EstadoCobertura, IndiceCobertura
from src.config import TABELAS_PERMITIDAS_SQL
from src.dados_estruturados import (
    FonteCVM,
    PainelIndisponivelError,
    SqlBloqueadoError,
    carregar_painel,
    validar_sql,
)
from src.ferramentas import (
    FERRAMENTA_MODELO,
    FERRAMENTAS_DISPONIVEIS,
    FERRAMENTAS_DO_PRODUTO,
    FERRAMENTAS_PROIBIDAS,
    CaixaDeFerramentas,
    ErroFerramenta,
    LeitorPainelDuckDB,
    TetoChamadasExcedidoError,
    conceitos_consultaveis,
    sql_de_conceito,
)
from src.mapa_contas import (
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
)
from src.projecao import FaixaDePorte, Panorama, TrimestreCorrente
from src.recuperacao import Estrategia, ResultadoRecuperacao

DIR_FIXTURES = Path(__file__).parent / "fixtures" / "cvm"

CD_BB = "001023"
CD_BTG = "022616"
CD_SERTRADING = "027774"
CD_HIDROVIAS = "900001"
CD_ITAU = "019348"
CD_INTER = "080217"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def painel(tmp_path_factory) -> Path:
    """Painel DuckDB montado das fixtures CSV — nunca o painel real."""
    destino = tmp_path_factory.mktemp("painel_ferramentas") / "cvm.duckdb"
    carregar_painel(
        [
            FonteCVM(DIR_FIXTURES / "itr_cia_aberta_DRE_con_amostra.csv", "itr", "DRE"),
            FonteCVM(DIR_FIXTURES / "dfp_cia_aberta_DRE_con_amostra.csv", "dfp", "DRE"),
            FonteCVM(DIR_FIXTURES / "itr_cia_aberta_BPP_con_amostra.csv", "itr", "BPP"),
            FonteCVM(DIR_FIXTURES / "itr_cia_aberta_BPA_con_amostra.csv", "itr", "BPA"),
        ],
        destino,
    )
    return destino


@pytest.fixture
def indice() -> IndiceCobertura:
    """Cobertura fiel ao painel real: Inter só no painel, BTG ambíguo."""
    companhias = (
        Companhia(CD_BTG, "BCO BTG PACTUAL S.A.", True),
        Companhia(CD_SERTRADING, "BTG PACTUAL COMMODITIES SERTRADING S.A.", False),
        Companhia(CD_ITAU, "ITAU UNIBANCO HOLDING S.A.", True),
        Companhia(CD_INTER, "INTER & CO, INC.", True),
        Companhia("025194", "ALARES INTERNET PARTICIPAÇÕES S/A", False),
    )
    trimestres = ("2T2025", "3T2025", "4T2025", "1T2026")
    return IndiceCobertura(
        companhias=companhias,
        trimestres_painel={c.cd_cvm: trimestres for c in companhias},
        trimestres_corpus={CD_BTG: trimestres, CD_ITAU: trimestres},
    )


class RecuperadorFalso:
    """Duplo de teste — devolve chunks fixos e conta as chamadas."""

    def __init__(self, resultados: list[ResultadoRecuperacao]):
        self.resultados = resultados
        self.chamadas: list[tuple[str, Estrategia, int | None]] = []

    def recuperar(self, pergunta, estrategia, top_k=None):
        self.chamadas.append((pergunta, estrategia, top_k))
        return self.resultados


@pytest.fixture
def recuperador(chunks_exemplo) -> RecuperadorFalso:
    return RecuperadorFalso(
        [
            ResultadoRecuperacao(chunk, 0.9 - indice * 0.1, Estrategia.SEMANTICA)
            for indice, chunk in enumerate(chunks_exemplo)
        ]
    )


@pytest.fixture
def caixa(config_padrao, painel, indice, recuperador) -> CaixaDeFerramentas:
    return CaixaDeFerramentas(
        config_padrao,
        indice_cobertura=indice,
        recuperador=recuperador,
        caminho_painel=painel,
        max_chamadas=20,
    )


# --------------------------------------------------------------------------- #
# RN07 — `prever_risco` não existe
# --------------------------------------------------------------------------- #


class TestFerramentaProibida:
    def test_prever_risco_nao_e_metodo_da_caixa(self):
        assert not hasattr(CaixaDeFerramentas, "prever_risco")

    def test_prever_risco_nao_esta_na_lista_de_ferramentas(self):
        assert "prever_risco" not in FERRAMENTAS_DISPONIVEIS
        assert "prever_risco" in FERRAMENTAS_PROIBIDAS

    def test_nenhuma_ferramenta_faz_previsao_sob_outro_nome(self, caixa):
        """RN07 proíbe a funcionalidade, não apenas o nome.

        Desde 2026-10-19 o produto tem `consultar_modelo_prejuizo` (AGENTS
        §3.16), e o nome sozinho não prova nada sobre ela: a funcionalidade
        proibida, escore de companhia nomeada na instância pública, é
        verificada por comportamento em `TestModeloNoProduto`. Aqui o conjunto
        do produto passou a entrar também na varredura de nomes."""
        expostas = {n for n in FERRAMENTAS_DISPONIVEIS} | set(FERRAMENTAS_DO_PRODUTO)
        expostas |= {d["nome"] for d in caixa.descrever(FERRAMENTAS_DO_PRODUTO)}
        proibidos = ("risco", "prever", "previsao", "projec", "recomend")
        assert not [n for n in expostas if any(p in n.lower() for p in proibidos)]

    @pytest.mark.parametrize("modulo", ["ferramentas.py", "cobertura.py"])
    def test_modulos_da_camada_nao_definem_prever_risco(self, modulo):
        caminho = Path(__file__).resolve().parent.parent / "src" / modulo
        assert caminho.is_file()
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            if linha.lstrip().startswith(("def ", "async def ", "class ")):
                assert "prever_risco" not in linha


# --------------------------------------------------------------------------- #
# O modelo no produto (AGENTS §3.16) — RN07 por comportamento
# --------------------------------------------------------------------------- #


def _panorama(n_acima: int = 79) -> Panorama:
    """Panorama sintético, com a forma do artefato real e sem depender dele."""
    return Panorama(
        trimestre_referencia="3T2025",
        n_companhias_avaliadas=413,
        n_acima_do_dobro_da_base=n_acima,
        limiar_dobro_da_base=0.426,
        taxa_base_painel=0.213,
        faixas_de_porte=(
            FaixaDePorte("≥ R$ 500 bi", 5e11, 231, 0.0606),
            FaixaDePorte("< R$ 500 bi", 0.0, 22000, 0.30),
        ),
        n_observacoes_treino=21119,
        fracao_nao_financeira_treino=0.969,
        auc_walk_forward=0.8786,
        trimestre_corrente=TrimestreCorrente("1T2026", 286, 136, 25, 0.161, 0.0807),
    )


class TestModeloNoProduto:
    """O que a RN07 proíbe é escore de companhia nomeada na instância pública.
    Estes casos verificam isso pela saída, não pelo nome da ferramenta."""

    def test_publico_nao_devolve_escore_nem_recebendo_cd_cvm(self, config_padrao, monkeypatch):
        import json

        import src.ferramentas as ferramentas

        def nao_pode_carregar(*_, **__):
            raise AssertionError("a instância pública carregou os escores por companhia")

        monkeypatch.setattr(ferramentas, "carregar_escores", nao_pode_carregar)
        caixa = CaixaDeFerramentas(config_padrao, panorama=_panorama())
        resultado = caixa.consultar_modelo_prejuizo(cd_cvm="906")
        assert resultado["escore_por_emissor"]["exposto"] is False
        assert "escore_pct" not in json.dumps(resultado)

    def test_modo_local_devolve_escore_etiquetado(self, config_padrao):
        from dataclasses import replace

        local = replace(config_padrao, previsao_por_emissor_habilitada=True)
        caixa = CaixaDeFerramentas(local, panorama=_panorama(), escores={"000906": 0.0058})
        escore = caixa.consultar_modelo_prejuizo(cd_cvm="906")["escore_por_emissor"]
        assert escore["exposto"] is True and escore["escore_pct"] == 0.6
        assert escore["trimestre"] == "1T2026" and "USO INTERNO" in escore["etiqueta"]

    def test_ativo_informado_vira_faixa_sem_saber_de_quem_e(self, config_padrao):
        caixa = CaixaDeFerramentas(config_padrao, panorama=_panorama())
        faixa = caixa.consultar_modelo_prejuizo(ativo_total_reais=2.9e12)["faixa_do_ativo_informado"]
        assert faixa == {
            "ativo_total_reais": 2.9e12, "faixa": "≥ R$ 500 bi", "limite_inferior_reais": 5e11,
            "limite_superior_reais": None, "taxa_historica_prejuizo_pct": 6.1,
        }
        assert caixa.registro[-1].argumentos == {"ativo_total_reais": 2.9e12, "cd_cvm": None}

    def test_agregado_extremo_nao_e_publicado(self, config_padrao):
        """Contagem 0 permite dedução por eliminação (`_agregado_seguro`)."""
        caixa = CaixaDeFerramentas(config_padrao, panorama=_panorama(n_acima=0))
        assert "panorama_mercado" not in caixa.consultar_modelo_prejuizo()

    def test_ativo_invalido_e_erro_registrado(self, config_padrao):
        caixa = CaixaDeFerramentas(config_padrao, panorama=_panorama())
        with pytest.raises(ValueError):
            caixa.consultar_modelo_prejuizo(ativo_total_reais=-1)
        assert caixa.registro[-1].erro

    def test_o_experimento_continua_com_quatro_e_o_produto_tem_cinco(self):
        assert len(FERRAMENTAS_DISPONIVEIS) == 4
        assert FERRAMENTAS_DO_PRODUTO == FERRAMENTAS_DISPONIVEIS + (FERRAMENTA_MODELO,)


# --------------------------------------------------------------------------- #
# Contrato da caixa
# --------------------------------------------------------------------------- #


class TestContratoDaCaixa:
    def test_expoe_exatamente_as_quatro_ferramentas(self):
        assert FERRAMENTAS_DISPONIVEIS == (
            "verificar_cobertura",
            "buscar_trechos",
            "consultar_cvm",
            "calcular_indicadores",
        )

    def test_toda_ferramenta_declarada_e_chamavel(self, caixa):
        for nome in FERRAMENTAS_DISPONIVEIS:
            assert callable(getattr(caixa, nome))

    def test_descricao_cobre_as_mesmas_ferramentas(self, caixa):
        assert tuple(d["nome"] for d in caixa.descrever()) == FERRAMENTAS_DISPONIVEIS
        assert all(d["descricao"] for d in caixa.descrever())

    def test_teto_invalido_e_recusado(self, config_padrao):
        with pytest.raises(ValueError):
            CaixaDeFerramentas(config_padrao, max_chamadas=0)

    def test_teto_padrao_vem_da_configuracao(self, config_padrao):
        caixa = CaixaDeFerramentas(config_padrao)
        assert caixa.max_chamadas == config_padrao.agentes_max_chamadas_ferramenta

    def test_auditor_recebe_orcamento_proprio(self, config_padrao, painel, indice):
        """O isolamento de 5.9.1 exige reexecução independente das consultas."""
        investigador = CaixaDeFerramentas(
            config_padrao, indice_cobertura=indice, caminho_painel=painel
        )
        auditor = CaixaDeFerramentas(
            config_padrao, indice_cobertura=indice, caminho_painel=painel
        )
        investigador.verificar_cobertura("Inter")
        assert investigador.chamadas_feitas == 1
        assert auditor.chamadas_feitas == 0
        assert auditor.chamadas_restantes == auditor.max_chamadas


# --------------------------------------------------------------------------- #
# Contenção (5.9.5)
# --------------------------------------------------------------------------- #


class TestTetoDeChamadas:
    def test_conta_cada_chamada(self, caixa):
        caixa.verificar_cobertura("Inter")
        caixa.verificar_cobertura("Itaú")
        assert caixa.chamadas_feitas == 2
        assert caixa.chamadas_restantes == 18

    def test_estourar_o_teto_levanta_erro_especifico(
        self, config_padrao, painel, indice
    ):
        caixa = CaixaDeFerramentas(
            config_padrao,
            indice_cobertura=indice,
            caminho_painel=painel,
            max_chamadas=2,
        )
        caixa.verificar_cobertura("Inter")
        caixa.verificar_cobertura("Itaú")
        assert caixa.teto_atingido is True
        with pytest.raises(TetoChamadasExcedidoError, match="parcial"):
            caixa.verificar_cobertura("BTG")

    def test_registro_sobrevive_ao_estouro(self, config_padrao, painel, indice):
        """A resposta parcial é montada com a evidência reunida até ali."""
        caixa = CaixaDeFerramentas(
            config_padrao,
            indice_cobertura=indice,
            caminho_painel=painel,
            max_chamadas=1,
        )
        caixa.verificar_cobertura("Inter")
        with pytest.raises(TetoChamadasExcedidoError):
            caixa.verificar_cobertura("Itaú")
        assert len(caixa.registro) == 1
        assert caixa.registro[0].ferramenta == "verificar_cobertura"
        assert "so_painel" in caixa.registro[0].resumo

    def test_chamada_bloqueada_tambem_consome_orcamento(self, caixa):
        """Sem isso, um laço de SQL recusado rodaria de graça para sempre."""
        with pytest.raises(SqlBloqueadoError):
            caixa.consultar_cvm("SELECT * FROM fatos_contabeis LIMIT 5")
        assert caixa.chamadas_feitas == 1
        assert caixa.registro[0].falhou is True
        assert "SqlBloqueadoError" in caixa.registro[0].erro

    def test_registro_serializa(self, caixa):
        caixa.verificar_cobertura("Inter")
        dicionario = caixa.registro[0].como_dicionario()
        assert dicionario["ferramenta"] == "verificar_cobertura"
        assert dicionario["argumentos"]["entidade"] == "Inter"


# --------------------------------------------------------------------------- #
# verificar_cobertura (RN11/RN12)
# --------------------------------------------------------------------------- #


class TestVerificarCobertura:
    def test_inter_e_so_painel(self, caixa):
        resultado = caixa.verificar_cobertura("Inter")
        entidade = resultado["entidades"][0]
        assert entidade["cobertura"]["estado"] == EstadoCobertura.SO_PAINEL.value
        assert entidade["cobertura"]["cd_cvm"] == CD_INTER
        assert resultado["desambiguacao"] == []

    def test_itau_esta_em_ambas(self, caixa):
        resultado = caixa.verificar_cobertura("Itaú")
        assert resultado["entidades"][0]["cobertura"]["estado"] == "ambas"

    def test_nubank_e_nenhuma(self, caixa):
        resultado = caixa.verificar_cobertura("Nubank")
        cobertura = resultado["entidades"][0]["cobertura"]
        assert cobertura["estado"] == "nenhuma"
        assert cobertura["cd_cvm"] is None

    def test_btg_devolve_desambiguacao_sem_escolher(self, caixa):
        resultado = caixa.verificar_cobertura("BTG")
        assert len(resultado["desambiguacao"]) == 1
        assert CD_BTG in resultado["desambiguacao"][0]
        assert CD_SERTRADING in resultado["desambiguacao"][0]
        assert resultado["entidades"][0]["cobertura"] is None

    def test_aceita_pergunta_inteira(self, caixa):
        resultado = caixa.verificar_cobertura("e o Inter, vocês cobrem?")
        assert resultado["entidades"][0]["cobertura"]["cd_cvm"] == CD_INTER

    def test_aceita_cd_cvm(self, caixa):
        resultado = caixa.verificar_cobertura(CD_SERTRADING)
        assert resultado["entidades"][0]["cobertura"]["cd_cvm"] == CD_SERTRADING

    def test_trimestre_muda_o_estado(self, caixa):
        assert (
            caixa.verificar_cobertura("Itaú", "3T2025")["entidades"][0]["cobertura"][
                "estado"
            ]
            == "ambas"
        )
        assert (
            caixa.verificar_cobertura("Itaú", "1T2020")["entidades"][0]["cobertura"][
                "estado"
            ]
            == "nenhuma"
        )

    def test_entidade_vazia_e_recusada(self, caixa):
        with pytest.raises(ErroFerramenta):
            caixa.verificar_cobertura("   ")


# --------------------------------------------------------------------------- #
# consultar_cvm (RN04 + RN09)
# --------------------------------------------------------------------------- #


class TestConsultarCvm:
    def test_consulta_valida_sobre_a_visao_semantica(self, caixa):
        resultado = caixa.consultar_cvm(
            "SELECT cd_cvm, trimestre, valor_reais FROM fatos_semanticos "
            f"WHERE cd_cvm = '{CD_BTG}' AND conceito = "
            f"'{CONCEITO_LUCRO_CONSOLIDADO}' ORDER BY trimestre LIMIT 10"
        )
        assert resultado["total_linhas"] >= 1
        assert resultado["colunas"] == ["cd_cvm", "trimestre", "valor_reais"]
        assert all(linha[0] == CD_BTG for linha in resultado["linhas"])

    def test_fatos_contabeis_cru_e_bloqueado(self, caixa):
        """RN09: `cd_conta` não identifica o conceito entre companhias."""
        with pytest.raises(SqlBloqueadoError, match="lista branca"):
            caixa.consultar_cvm("SELECT * FROM fatos_contabeis LIMIT 5")

    def test_cd_conta_e_coluna_bloqueada(self, caixa):
        with pytest.raises(SqlBloqueadoError, match="cd_conta"):
            caixa.consultar_cvm(
                "SELECT cd_conta FROM fatos_semanticos LIMIT 5"
            )

    def test_guarda_roda_antes_de_qualquer_acesso_ao_banco(
        self, config_padrao, indice, tmp_path
    ):
        """Se a guarda executasse depois, o erro seria de painel ausente."""
        caixa = CaixaDeFerramentas(
            config_padrao,
            indice_cobertura=indice,
            caminho_painel=tmp_path / "inexistente.duckdb",
        )
        with pytest.raises(SqlBloqueadoError):
            caixa.consultar_cvm("SELECT * FROM fatos_contabeis LIMIT 5")

    @pytest.mark.parametrize(
        "sql",
        [
            "DROP TABLE companhias",
            "SELECT * FROM fatos_semanticos",  # sem LIMIT
            "SELECT * FROM companhias LIMIT 10; DROP TABLE companhias",
            "SELECT * FROM read_csv('/etc/passwd') LIMIT 1",
            "SELECT * FROM companhias LIMIT 100000",
        ],
    )
    def test_guardas_da_rn04_continuam_valendo_pela_ferramenta(self, sql, caixa):
        with pytest.raises(SqlBloqueadoError):
            caixa.consultar_cvm(sql)

    def test_lista_branca_e_devolvida_na_resposta(self, caixa):
        resultado = caixa.consultar_cvm("SELECT cd_cvm FROM companhias LIMIT 5")
        assert resultado["tabelas_permitidas"] == sorted(TABELAS_PERMITIDAS_SQL)
        assert "fatos_contabeis" not in resultado["tabelas_permitidas"]

    def test_painel_ausente_falha_explicito(self, config_padrao, indice, tmp_path):
        caixa = CaixaDeFerramentas(
            config_padrao,
            indice_cobertura=indice,
            caminho_painel=tmp_path / "inexistente.duckdb",
        )
        with pytest.raises(PainelIndisponivelError):
            caixa.consultar_cvm("SELECT cd_cvm FROM companhias LIMIT 5")


class TestSqlDeConceito:
    def test_sql_gerado_passa_pelas_guardas(self, config_padrao):
        """O atalho não pode emitir o que a guarda recusaria."""
        sql = sql_de_conceito(CD_BTG, CONCEITO_LUCRO_CONSOLIDADO, ("3T2025",))
        assert validar_sql(sql, config_padrao) == sql

    def test_sql_gerado_executa(self, caixa):
        sql = sql_de_conceito(
            [CD_BB, CD_BTG], CONCEITO_LUCRO_CONTROLADORES, ("1T2025",)
        )
        resultado = caixa.consultar_cvm(sql)
        assert {linha[0] for linha in resultado["linhas"]} == {CD_BB, CD_BTG}

    def test_conceito_desconhecido_e_recusado(self):
        with pytest.raises(ErroFerramenta, match="conceito desconhecido"):
            sql_de_conceito(CD_BTG, "lucro_gerencial_ajustado")

    def test_sem_companhia_e_recusado(self):
        with pytest.raises(ErroFerramenta):
            sql_de_conceito([], CONCEITO_LUCRO_CONSOLIDADO)

    def test_conceitos_consultaveis_nao_inclui_gerencial(self):
        """O número gerencial vem do release, nunca da CVM."""
        assert CONCEITO_LUCRO_CONSOLIDADO in conceitos_consultaveis()
        assert "lucro_liquido_gerencial" not in conceitos_consultaveis()


# --------------------------------------------------------------------------- #
# buscar_trechos
# --------------------------------------------------------------------------- #


class TestBuscarTrechos:
    def test_devolve_os_metadados_de_citacao(self, caixa):
        trechos = caixa.buscar_trechos("qual o lucro do Itaú?")
        assert trechos
        for campo in ("empresa", "documento", "trimestre", "pagina_inicio", "pagina_fim"):
            assert all(campo in trecho for trecho in trechos)

    def test_usa_a_estrategia_padrao_da_configuracao(self, caixa, recuperador):
        caixa.buscar_trechos("qual o lucro do Itaú?")
        assert recuperador.chamadas[0][1] is Estrategia.SEMANTICA

    def test_estrategia_explicita_e_respeitada(self, caixa, recuperador):
        caixa.buscar_trechos("lucro", estrategia="hibrida", top_k=3)
        assert recuperador.chamadas[0][1] is Estrategia.HIBRIDA
        assert recuperador.chamadas[0][2] == 3

    def test_closed_book_nao_e_ferramenta(self, caixa):
        with pytest.raises(ErroFerramenta, match="closed_book"):
            caixa.buscar_trechos("lucro", estrategia="closed_book")

    def test_pergunta_vazia_e_recusada(self, caixa):
        with pytest.raises(ErroFerramenta):
            caixa.buscar_trechos("  ")

    def test_estrategia_desconhecida_e_recusada(self, caixa):
        with pytest.raises(ValueError):
            caixa.buscar_trechos("lucro", estrategia="magica")


# --------------------------------------------------------------------------- #
# calcular_indicadores (RN10/RN11)
# --------------------------------------------------------------------------- #


class TestCalcularIndicadores:
    def test_devolve_indicadores_por_codigo(self, caixa):
        resultado = caixa.calcular_indicadores(CD_BTG)
        assert resultado["cd_cvm"] == CD_BTG
        assert resultado["indicadores"]
        assert "roe_trimestral" in resultado["indicadores"][0]

    def test_filtra_por_trimestre(self, caixa):
        resultado = caixa.calcular_indicadores(CD_BTG, "1T2025")
        assert len(resultado["indicadores"]) == 1
        assert resultado["indicadores"][0]["trimestre"] == "1T2025"

    def test_marca_trimestre_derivado(self, caixa):
        """RN10: o 4T sai do DFP anual menos o ITR acumulado, e é declarado."""
        assert caixa.calcular_indicadores(CD_BB, "4T2025")["derivado"] is True
        assert caixa.calcular_indicadores(CD_BB, "3T2025")["derivado"] is False

    @pytest.mark.parametrize("nome", ["BTG", "Banco BTG Pactual", "itau"])
    def test_nome_e_recusado_com_apontamento_para_a_cobertura(self, nome, caixa):
        """RN11: aceitar nome aqui reintroduziria a escolha automática."""
        with pytest.raises(ErroFerramenta, match="verificar_cobertura"):
            caixa.calcular_indicadores(nome)

    def test_codigo_sem_zeros_a_esquerda_e_normalizado(self, caixa):
        assert caixa.calcular_indicadores("22616")["cd_cvm"] == CD_BTG

    def test_liquidez_e_ausencia_declarada(self, caixa):
        resultado = caixa.calcular_indicadores(CD_BTG)
        assert resultado["ausentes_declarados"] == ["liquidez"]
        assert all("liquidez" not in r for r in resultado["indicadores"])


# --------------------------------------------------------------------------- #
# Leitor do painel e braço C
# --------------------------------------------------------------------------- #


class TestLeitorPainelDuckDB:
    def test_le_um_fato_da_visao_semantica(self, config_padrao, painel):
        leitor = LeitorPainelDuckDB(config_padrao, painel)
        fato = leitor.ler(CD_BTG, CONCEITO_LUCRO_CONSOLIDADO, "1T2025")
        assert fato is not None
        assert fato.cd_cvm == CD_BTG
        assert fato.valor_reais == 4_900_000_000.0
        assert fato.derivado is False

    def test_marca_valor_derivado(self, config_padrao, painel):
        leitor = LeitorPainelDuckDB(config_padrao, painel)
        fato = leitor.ler(CD_BB, CONCEITO_LUCRO_CONSOLIDADO, "4T2025")
        assert fato is not None
        assert fato.derivado is True
        assert "DERIVADO" in fato.citacao()

    def test_fato_ausente_devolve_none(self, config_padrao, painel):
        leitor = LeitorPainelDuckDB(config_padrao, painel)
        assert leitor.ler(CD_BTG, CONCEITO_LUCRO_CONSOLIDADO, "1T2020") is None

    def test_normaliza_o_codigo(self, config_padrao, painel):
        leitor = LeitorPainelDuckDB(config_padrao, painel)
        assert leitor.ler("22616", CONCEITO_LUCRO_CONSOLIDADO, "1T2025") is not None


class TestBracoCPelaCaixa:
    def test_responde_cobertura_com_numero_do_painel(
        self, config_padrao, painel, indice
    ):
        caixa = CaixaDeFerramentas(
            config_padrao,
            indice_cobertura=IndiceCobertura(
                companhias=(Companhia(CD_BTG, "BCO BTG PACTUAL S.A.", True),),
                trimestres_painel={CD_BTG: ("1T2025", "2T2025")},
                trimestres_corpus={CD_BTG: ("2T2025",)},
            ),
            caminho_painel=painel,
        )
        resposta = caixa.responder_deterministico(
            "qual o lucro líquido consolidado do BTG no 1T2025?"
        )
        assert resposta.braco == "C"
        assert resposta.recusa is False
        assert "R$ 4.900.000.000,00" in resposta.resposta
        assert resposta.fatos[0].cd_cvm == CD_BTG

    def test_conta_como_chamada_de_ferramenta(self, caixa):
        caixa.responder_deterministico("e o Inter?")
        assert caixa.chamadas_feitas == 1
        assert "braço C" in caixa.registro[0].resumo

    def test_nubank_e_recusa_diagnosticada(self, caixa):
        resposta = caixa.responder_deterministico("e o Nubank?")
        assert resposta.recusa is True
        assert "NYSE" in resposta.resposta

    def test_nao_usa_llm(self, caixa, monkeypatch):
        """O piso honesto é piso porque não paga token nenhum."""
        import src.geracao as geracao

        def explodir(*args, **kwargs):  # pragma: no cover - só se regredir
            raise AssertionError("o braço C não pode chamar o LLM")

        for nome in ("gerar_resposta", "fabricar_provedor_llm"):
            assert hasattr(geracao, nome), (
                f"src.geracao.{nome} sumiu — o teste pararia de provar algo"
            )
            monkeypatch.setattr(geracao, nome, explodir)
        assert caixa.responder_deterministico("e o Inter?").braco == "C"

    def test_cobertura_nao_importa_a_camada_de_geracao(self):
        """Garantia estrutural: o braço C não *pode* chamar LLM.

        Mais forte que um duplo de teste — se `src.cobertura` importasse a
        geração ou um provedor, o piso deixaria de ser piso e ninguém veria.
        """
        texto = (
            Path(__file__).resolve().parent.parent / "src" / "cobertura.py"
        ).read_text(encoding="utf-8")
        importados = [
            linha
            for linha in texto.splitlines()
            if linha.startswith(("import ", "from "))
        ]
        proibidos = ("geracao", "openai", "ollama", "requests", "httpx", "crewai")
        assert not [
            linha for linha in importados if any(p in linha for p in proibidos)
        ]
