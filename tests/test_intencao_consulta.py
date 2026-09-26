"""Rota do painel com LLM-intérprete — as guardas que o modelo não pode furar.

Nenhum caso aqui chama LLM: o que se trava é o que acontece DEPOIS que ele
responde. Três defeitos reais, medidos na comparação de 2026-09-20, viraram
caso de teste: o intérprete escolheu `lucro_liquido_consolidado` para "lucro do
Itaú" e `lucro_liquido_controladores` para "lucro líquido do Itaú" (R$ 294
milhões de diferença na mesma pergunta parafraseada); afirmou que o Banco Inter
não está no painel quando está; e a visão tem 12 grãos com dois valores, onde
agregar devolveria número plausível e errado.
"""

from __future__ import annotations

import pytest

from src.cobertura import Companhia, IndiceCobertura
from src.intencao_consulta import (
    ErroDeIntencao,
    IntencaoBruta,
    IntencaoValidada,
    Linha,
    desempatar_lucro,
    graos_ambiguos,
    interpretar,
    linhas_de,
    montar_sql,
    prompt_interprete,
    validar,
    validar_sql_da_rota,
    _texto_json,
)
from src.mapa_contas import (
    CONCEITO_ATIVO_TOTAL,
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_LUCRO_NAO_CONTROLADORES,
    CONCEITOS,
)

CD_ITAU = "019348"
CD_BB = "001023"


@pytest.fixture
def indice() -> IndiceCobertura:
    return IndiceCobertura(
        companhias=(
            Companhia(CD_ITAU, "ITAU UNIBANCO HOLDING S.A.", True),
            Companhia(CD_BB, "BCO BRASIL S.A.", True),
        ),
        trimestres_painel={
            CD_ITAU: ("3T2025", "4T2025"),
            CD_BB: ("3T2025", "4T2025"),
        },
        trimestres_corpus={CD_ITAU: ("3T2025",)},
    )


class TestLeituraDaSaidaDoModelo:
    def test_aceita_json_em_cerca_de_crase(self):
        objeto = _texto_json('```json\n{"conceito": "ativo_total"}\n```')
        assert objeto["conceito"] == "ativo_total"

    def test_texto_sem_json_levanta(self):
        with pytest.raises(ErroDeIntencao, match="não traz JSON"):
            _texto_json("desculpe, não entendi a pergunta")

    def test_operacao_desconhecida_levanta(self):
        with pytest.raises(ErroDeIntencao, match="operação desconhecida"):
            interpretar({"operacao": "somar_tudo"})


class TestDesempateDeLucro:
    """O projeto declara o padrão em `mapa_contas`; o modelo não decide isso."""

    @pytest.mark.parametrize(
        "conceito_do_modelo",
        [
            CONCEITO_LUCRO_CONSOLIDADO,
            CONCEITO_LUCRO_CONTROLADORES,
            CONCEITO_LUCRO_NAO_CONTROLADORES,
        ],
    )
    def test_pergunta_sem_qualificador_cai_no_padrao(self, conceito_do_modelo):
        assert (
            desempatar_lucro(conceito_do_modelo, "Qual o lucro do Itaú?")
            == CONCEITO_LUCRO_CONTROLADORES
        )

    @pytest.mark.parametrize(
        ("pergunta", "esperado"),
        [
            ("Qual o lucro consolidado do Itaú?", CONCEITO_LUCRO_CONSOLIDADO),
            (
                "Qual o lucro dos não controladores do Itaú?",
                CONCEITO_LUCRO_NAO_CONTROLADORES,
            ),
            (
                "Lucro atribuído à controladora do Itaú?",
                CONCEITO_LUCRO_CONTROLADORES,
            ),
        ],
    )
    def test_pergunta_que_qualifica_preserva_a_escolha(self, pergunta, esperado):
        assert desempatar_lucro(esperado, pergunta) == esperado

    def test_contraprova_conceito_que_nao_e_lucro_passa_intacto(self):
        assert (
            desempatar_lucro(CONCEITO_ATIVO_TOTAL, "Qual o ativo total do Itaú?")
            == CONCEITO_ATIVO_TOTAL
        )

    def test_o_desempate_vale_na_validacao_inteira(self, indice):
        """Regressão da divergência medida: paráfrase não pode mudar o número."""
        bruta = IntencaoBruta(
            companhias=("Itaú",),
            conceito=CONCEITO_LUCRO_CONSOLIDADO,
            trimestres=("3T2025",),
        )
        validada = validar(bruta, indice, "Qual o lucro do Itaú no 3T2025?")
        assert validada.conceito == CONCEITO_LUCRO_CONTROLADORES


class TestCoberturaNaoEDoModelo:
    def test_fora_do_painel_com_conceito_valido_e_ignorado(self, indice):
        """O intérprete disse que o Inter não está no painel; ele está.

        A afirmação do modelo sobre cobertura não pode virar recusa: quem
        decide é `resolver_entidade`.
        """
        bruta = IntencaoBruta(
            companhias=("Itaú",),
            conceito=CONCEITO_LUCRO_CONTROLADORES,
            trimestres=("3T2025",),
            fora_do_painel=True,
            motivo="essa companhia não me parece coberta",
        )
        validada = validar(bruta, indice, "Qual o lucro do Itaú no 3T2025?")
        assert validada.codigos == (CD_ITAU,)

    def test_fora_do_painel_por_conceito_continua_recusando(self, indice):
        bruta = IntencaoBruta(
            companhias=("Itaú",),
            conceito="",
            fora_do_painel=True,
            motivo="índice de Basileia não está no painel",
        )
        with pytest.raises(ErroDeIntencao, match="Basileia"):
            validar(bruta, indice, "Qual o índice de Basileia do Itaú?")

    def test_codigo_inventado_pelo_modelo_nao_chega_ao_sql(self, indice):
        """Companhia do modelo é termo de busca, nunca `cd_cvm`."""
        bruta = IntencaoBruta(
            companhias=("999999",),
            conceito=CONCEITO_LUCRO_CONTROLADORES,
        )
        with pytest.raises(ErroDeIntencao, match="nenhuma companhia"):
            validar(bruta, indice, "Qual o lucro de 999999?")


class TestValidacaoDaIntencao:
    def test_conceito_fora_do_mapa_levanta(self, indice):
        bruta = IntencaoBruta(companhias=("Itaú",), conceito="ebitda_ajustado")
        with pytest.raises(ErroDeIntencao, match="fora do mapa semântico"):
            validar(bruta, indice, "Qual o EBITDA do Itaú?")

    def test_trimestre_malformado_levanta(self, indice):
        bruta = IntencaoBruta(
            companhias=("Itaú",),
            conceito=CONCEITO_LUCRO_CONTROLADORES,
            trimestres=("2025-Q3",),
        )
        with pytest.raises(ErroDeIntencao, match="malformado"):
            validar(bruta, indice, "Qual o lucro do Itaú?")

    def test_variacao_sem_dois_trimestres_levanta(self, indice):
        bruta = IntencaoBruta(
            companhias=("Itaú",),
            conceito=CONCEITO_LUCRO_CONTROLADORES,
            trimestres=("3T2025",),
            operacao="variacao",
        )
        with pytest.raises(ErroDeIntencao, match="dois trimestres"):
            validar(bruta, indice, "Quanto cresceu?")


class TestSqlPorTemplate:
    INTENCAO = IntencaoValidada(
        codigos=(CD_ITAU, CD_BB),
        conceito=CONCEITO_LUCRO_CONTROLADORES,
        trimestres=("3T2025",),
        operacao="comparacao",
    )

    def test_marcas_de_procedencia_sao_obrigatorias(self):
        sql = montar_sql(self.INTENCAO)
        assert "origem" in sql and "corrigido" in sql
        assert validar_sql_da_rota(sql) is sql

    def test_select_sem_marca_e_recusado(self):
        """Contraprova: sem `origem`, um derivado chegaria sem aviso (RN10)."""
        with pytest.raises(ErroDeIntencao, match="marca de procedência"):
            validar_sql_da_rota(
                "SELECT cd_cvm, valor_reais FROM fatos_semanticos LIMIT 5"
            )

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT sum(valor_reais), origem, corrigido FROM fatos_semanticos",
            "SELECT valor_reais, origem, corrigido FROM fatos_semanticos "
            "GROUP BY cd_cvm",
            "SELECT max(valor_reais), origem, corrigido FROM fatos_semanticos",
        ],
    )
    def test_agregacao_e_recusada(self, sql):
        """A visão tem 12 grãos duplicados: agregar devolve número errado."""
        with pytest.raises(ErroDeIntencao, match="agregação proibida"):
            validar_sql_da_rota(sql)

    def test_passa_na_guarda_da_rn04(self):
        from src.config import carregar_config
        from src.dados_estruturados import validar_sql

        assert validar_sql(montar_sql(self.INTENCAO), carregar_config())

    def test_sem_companhia_nao_monta_sql(self):
        vazia = IntencaoValidada(
            codigos=(), conceito=CONCEITO_LUCRO_CONTROLADORES,
            trimestres=(), operacao="valor",
        )
        with pytest.raises(ErroDeIntencao, match="sem companhia"):
            montar_sql(vazia)

    def test_conceito_invalido_nao_monta_sql(self):
        with pytest.raises(ErroDeIntencao, match="conceito inválido"):
            montar_sql(
                IntencaoValidada(
                    codigos=(CD_ITAU,), conceito="inventado",
                    trimestres=(), operacao="valor",
                )
            )


def _linha(cd_cvm, trimestre, valor, origem="arquivado"):
    return Linha(
        cd_cvm=cd_cvm,
        denom_social="COMPANHIA TESTE",
        trimestre=trimestre,
        conceito=CONCEITO_LUCRO_CONTROLADORES,
        valor_reais=valor,
        origem=origem,
        corrigido=False,
        tipo_periodo="trimestral",
    )


class TestGraoAmbiguo:
    def test_dois_valores_no_mesmo_grao_sao_apontados(self):
        linhas = (
            _linha(CD_ITAU, "3T2025", 1.0),
            _linha(CD_ITAU, "3T2025", 2.0),
            _linha(CD_BB, "3T2025", 3.0),
        )
        assert graos_ambiguos(linhas) == ((CD_ITAU, "3T2025"),)

    def test_mesmo_valor_repetido_nao_e_ambiguo(self):
        linhas = (_linha(CD_ITAU, "3T2025", 1.0), _linha(CD_ITAU, "3T2025", 1.0))
        assert graos_ambiguos(linhas) == ()

    def test_graos_distintos_nao_sao_ambiguos(self):
        linhas = (_linha(CD_ITAU, "3T2025", 1.0), _linha(CD_ITAU, "4T2025", 2.0))
        assert graos_ambiguos(linhas) == ()


class TestConversaoDeLinhas:
    def test_le_por_nome_de_coluna_e_nao_por_posicao(self):
        colunas = (
            "tipo_periodo", "corrigido", "origem", "valor_reais",
            "conceito", "trimestre", "denom_social", "cd_cvm",
        )
        linhas = linhas_de(
            colunas,
            [("trimestral", False, "derivado", 10.0, "ativo_total",
              "4T2025", "X S.A.", CD_BB)],
        )
        assert linhas[0].cd_cvm == CD_BB
        assert linhas[0].origem == "derivado"
        assert linhas[0].valor_reais == 10.0


class TestPrompt:
    def test_vocabulario_vem_do_mapa_e_nao_de_lista_paralela(self):
        """Conceito novo no mapa precisa aparecer no prompt sem edição manual."""
        prompt = prompt_interprete()
        for conceito in CONCEITOS:
            assert conceito in prompt

    def test_prompt_proibe_o_modelo_de_julgar_cobertura(self):
        prompt = prompt_interprete()
        assert "cobertura de companhia não é decisão sua" in prompt
