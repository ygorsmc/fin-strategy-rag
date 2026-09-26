"""Plano de consulta por células — as portas que a granularidade abre.

Nenhum caso aqui chama LLM: trava-se o que acontece DEPOIS que ele responde.
Três guardas existem só neste formato, porque a intenção única as tinha de
graça: com um conceito por pergunta não havia como comparar grandezas
diferentes, com um `SELECT` por pergunta não havia comparação parcial, e com um
`IN (...)` o tamanho do plano era o número de companhias citadas. Aqui as três
coisas passaram a depender do que o modelo devolve — então passam a ser
verificadas em código.
"""

from __future__ import annotations

import pytest

from src.cobertura import Companhia, IndiceCobertura
from src.intencao_consulta import ErroDeIntencao, Linha
from src.mapa_contas import (
    CONCEITO_ATIVO_TOTAL,
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITOS,
)
from src.plano_consulta import (
    MAX_CELULAS,
    CacheDeCelulas,
    Celula,
    CelulaPendente,
    CelulaRespondida,
    CelulaResolvida,
    PeriodoIndefinido,
    PlanoBruto,
    PlanoValidado,
    RecusaDeReformulacao,
    assinatura_painel,
    executar_plano,
    interpretar_plano,
    montar_sql_celula,
    pode_eleger_vencedor,
    prompt_plano,
    responder_celula,
    validar_plano,
)

CD_ITAU = "019348"
CD_BB = "001023"
CD_BTG_A = "080004"
CD_BTG_B = "080005"


@pytest.fixture
def indice() -> IndiceCobertura:
    """Dois nomes limpos e um ambíguo — o caso do BTG na rodada de 2026-09-20."""
    return IndiceCobertura(
        companhias=(
            Companhia(CD_ITAU, "ITAU UNIBANCO HOLDING S.A.", True),
            Companhia(CD_BB, "BCO BRASIL S.A.", True),
            Companhia(CD_BTG_A, "BTG PACTUAL PARTICIPATIONS", True),
            Companhia(CD_BTG_B, "BANCO BTG PACTUAL S.A.", True),
        ),
        trimestres_painel={
            CD_ITAU: ("3T2025", "4T2025"),
            CD_BB: ("3T2025", "4T2025"),
            CD_BTG_A: ("3T2025",),
            CD_BTG_B: ("3T2025",),
        },
        trimestres_corpus={CD_ITAU: ("3T2025",)},
    )


def _celula(cd_cvm=CD_ITAU, conceito=CONCEITO_LUCRO_CONTROLADORES, trimestre="3T2025"):
    return CelulaResolvida(
        termo="Itaú",
        cd_cvm=cd_cvm,
        denom_social="ITAU UNIBANCO HOLDING S.A.",
        conceito=conceito,
        trimestre=trimestre,
        sql=montar_sql_celula(cd_cvm, conceito, trimestre),
    )


def _linha(cd_cvm=CD_ITAU, trimestre="3T2025", valor=1.0, origem="arquivado"):
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


class TestLeituraDoPlano:
    def test_uma_consulta_por_celula(self):
        plano = interpretar_plano(
            {
                "consultas": [
                    {"companhia": "Itaú", "conceito": "x", "trimestre": "3T2025"},
                    {"companhia": "BB", "conceito": "x", "trimestre": "3T2025"},
                ],
                "operacao": "comparacao",
            }
        )
        assert len(plano.consultas) == 2
        assert plano.consultas[0] == Celula("Itaú", "x", "3T2025")
        assert plano.operacao == "comparacao"

    def test_trimestre_nulo_chega_vazio_para_a_validacao_recusar(self):
        """A leitura não julga; quem recusa período ausente é `validar_plano`."""
        plano = interpretar_plano(
            {"consultas": [{"companhia": "Itaú", "conceito": "x", "trimestre": None}]}
        )
        assert plano.consultas[0].trimestre == ""

    def test_le_o_campo_de_recusa(self):
        plano = interpretar_plano(
            {"consultas": [], "recusar": True, "motivo": "falta o trimestre"}
        )
        assert plano.recusar
        assert plano.motivo == "falta o trimestre"

    def test_celula_repetida_e_pedida_uma_vez(self):
        plano = interpretar_plano(
            {
                "consultas": [
                    {"companhia": "Itaú", "conceito": "x", "trimestre": "3T2025"},
                    {"companhia": "Itaú", "conceito": "x", "trimestre": "3T2025"},
                ]
            }
        )
        assert len(plano.consultas) == 1

    def test_consultas_nao_lista_levanta(self):
        with pytest.raises(ErroDeIntencao, match="deve ser lista"):
            interpretar_plano({"consultas": {"companhia": "Itaú"}})

    def test_consulta_que_nao_e_objeto_levanta(self):
        with pytest.raises(ErroDeIntencao, match="deve ser objeto"):
            interpretar_plano({"consultas": ["Itaú"]})

    def test_operacao_desconhecida_levanta(self):
        with pytest.raises(ErroDeIntencao, match="operação desconhecida"):
            interpretar_plano({"consultas": [], "operacao": "ranquear"})


class TestTetoDeCelulas:
    """O plano é a única coisa desta rota que cresce sem limite natural."""

    def test_plano_acima_do_teto_e_recusado_na_leitura(self):
        consultas = [
            {"companhia": f"Banco {i}", "conceito": "x", "trimestre": "3T2025"}
            for i in range(MAX_CELULAS + 1)
        ]
        with pytest.raises(ErroDeIntencao, match="excede o teto"):
            interpretar_plano({"consultas": consultas})

    def test_plano_acima_do_teto_e_recusado_de_novo_na_validacao(self, indice):
        """Contraprova: quem montar `PlanoBruto` na mão não fura o teto."""
        bruto = PlanoBruto(
            consultas=tuple(
                Celula(f"Banco {i}", CONCEITO_LUCRO_CONTROLADORES, "3T2025")
                for i in range(MAX_CELULAS + 1)
            )
        )
        with pytest.raises(ErroDeIntencao, match="excede o teto"):
            validar_plano(bruto, indice, "pergunta")

    def test_no_teto_exato_passa(self):
        consultas = [
            {"companhia": f"Banco {i}", "conceito": "x", "trimestre": "3T2025"}
            for i in range(MAX_CELULAS)
        ]
        assert len(interpretar_plano({"consultas": consultas}).consultas) == MAX_CELULAS


class TestConceitoUnicoAoConfrontar:
    """Confrontar exige a mesma régua — a guarda que só este formato precisa."""

    @pytest.mark.parametrize("operacao", ["comparacao", "variacao"])
    def test_conceitos_diferentes_recusam(self, indice, operacao):
        bruto = PlanoBruto(
            consultas=(
                Celula("Itaú", CONCEITO_LUCRO_CONSOLIDADO, "3T2025"),
                Celula("BB", CONCEITO_ATIVO_TOTAL, "3T2025"),
            ),
            operacao=operacao,
        )
        with pytest.raises(ErroDeIntencao, match="mesma régua"):
            validar_plano(bruto, indice, "Compare o lucro consolidado e o ativo")

    def test_operacao_valor_tolera_conceitos_diferentes(self, indice):
        """Listar duas grandezas lado a lado é legítimo; confrontá-las não é."""
        bruto = PlanoBruto(
            consultas=(
                Celula("Itaú", CONCEITO_LUCRO_CONSOLIDADO, "3T2025"),
                Celula("Itaú", CONCEITO_ATIVO_TOTAL, "3T2025"),
            ),
            operacao="valor",
        )
        plano = validar_plano(bruto, indice, "Lucro consolidado e ativo do Itaú")
        assert len(plano.celulas) == 2
        assert plano.conceito == ""

    def test_o_desempate_de_lucro_roda_por_celula(self, indice):
        """Sem qualificador, as três leituras de lucro convergem no padrão.

        É o que impede a heterogeneidade mais provável: o modelo escolhendo
        leituras diferentes de "lucro" para bancos diferentes na mesma pergunta.
        """
        bruto = PlanoBruto(
            consultas=(
                Celula("Itaú", CONCEITO_LUCRO_CONSOLIDADO, "3T2025"),
                Celula("BB", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
            ),
            operacao="comparacao",
        )
        plano = validar_plano(bruto, indice, "Quem lucrou mais no 3T2025?")
        assert plano.conceito == CONCEITO_LUCRO_CONTROLADORES
        assert {c.conceito for c in plano.celulas} == {CONCEITO_LUCRO_CONTROLADORES}


class TestPendenciaNaoDerrubaOPlano:
    """O ganho central do formato: ambiguidade em um nome não apaga os outros."""

    def test_companhia_ambigua_vira_pendencia_e_as_outras_seguem(self, indice):
        bruto = PlanoBruto(
            consultas=(
                Celula("Itaú", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
                Celula("BB", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
                Celula("BTG Pactual", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
            ),
            operacao="comparacao",
        )
        plano = validar_plano(bruto, indice, "Qual dos bancos lucrou mais?")
        assert {c.cd_cvm for c in plano.celulas} == {CD_ITAU, CD_BB}
        assert [p.termo for p in plano.pendentes] == ["BTG Pactual"]
        assert plano.pendentes[0].estado == "ambigua"
        assert not plano.completo

    def test_a_pergunta_de_desambiguacao_continua_sendo_devolvida(self, indice):
        """RN11 não é afrouxada: nada foi escolhido, a pergunta vai junto."""
        bruto = PlanoBruto(
            consultas=(
                Celula("Itaú", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
                Celula("BTG Pactual", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
            ),
            operacao="comparacao",
        )
        plano = validar_plano(bruto, indice, "pergunta")
        pendente = plano.pendentes[0]
        assert pendente.candidatas == (CD_BTG_A, CD_BTG_B)
        assert "CD_CVM" in (pendente.pergunta_desambiguacao or "")

    def test_companhia_desconhecida_vira_pendencia_nomeada(self, indice):
        bruto = PlanoBruto(
            consultas=(
                Celula("Itaú", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
                Celula("Nubank", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
            ),
            operacao="comparacao",
        )
        plano = validar_plano(bruto, indice, "pergunta")
        assert [(p.termo, p.estado) for p in plano.pendentes] == [
            ("Nubank", "nao_resolvida")
        ]

    def test_plano_todo_pendente_recusa(self, indice):
        bruto = PlanoBruto(
            consultas=(Celula("Nubank", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),)
        )
        with pytest.raises(ErroDeIntencao, match="nenhuma companhia"):
            validar_plano(bruto, indice, "pergunta")

    def test_codigo_inventado_pelo_modelo_nao_vira_celula(self, indice):
        """Companhia é termo de busca; `cd_cvm` vem de `resolver_entidade`."""
        bruto = PlanoBruto(
            consultas=(Celula("999999", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),)
        )
        with pytest.raises(ErroDeIntencao, match="nenhuma companhia"):
            validar_plano(bruto, indice, "pergunta")


class TestVencedorExigeConjuntoCompleto:
    """Superlativo sobre conjunto incompleto afirma mais do que o dado sustenta."""

    def _plano(self, pendentes=()):
        return PlanoValidado(
            celulas=(_celula(), _celula(cd_cvm=CD_BB)),
            pendentes=pendentes,
            operacao="comparacao",
            conceito=CONCEITO_LUCRO_CONTROLADORES,
        )

    def test_todos_presentes_elege(self):
        respondidas = (
            CelulaRespondida(_celula(), (_linha(valor=2.0),)),
            CelulaRespondida(_celula(cd_cvm=CD_BB), (_linha(CD_BB, valor=1.0),)),
        )
        assert pode_eleger_vencedor(self._plano(), respondidas)

    def test_pendencia_impede_eleger(self):
        respondidas = (
            CelulaRespondida(_celula(), (_linha(valor=2.0),)),
            CelulaRespondida(_celula(cd_cvm=CD_BB), (_linha(CD_BB, valor=1.0),)),
        )
        pendente = (CelulaPendente("BTG Pactual", "ambigua", (CD_BTG_A, CD_BTG_B)),)
        assert not pode_eleger_vencedor(self._plano(pendente), respondidas)

    def test_celula_vazia_impede_eleger(self):
        """O banco sem dado no painel pode ser justamente o maior."""
        respondidas = (
            CelulaRespondida(_celula(), (_linha(valor=2.0),)),
            CelulaRespondida(_celula(cd_cvm=CD_BB), ()),
        )
        assert not pode_eleger_vencedor(self._plano(), respondidas)

    def test_grao_ambiguo_impede_eleger(self):
        respondidas = (
            CelulaRespondida(_celula(), (_linha(valor=2.0),)),
            CelulaRespondida(
                _celula(cd_cvm=CD_BB),
                (_linha(CD_BB, valor=1.0), _linha(CD_BB, valor=9.0)),
                graos_ambiguos=((CD_BB, "3T2025"),),
            ),
        )
        assert not pode_eleger_vencedor(self._plano(), respondidas)

    def test_sem_respondidas_nao_elege(self):
        assert not pode_eleger_vencedor(self._plano(), ())


class TestSqlDaCelula:
    def test_marcas_de_procedencia_sao_obrigatorias(self):
        sql = montar_sql_celula(CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "3T2025")
        assert "origem" in sql and "corrigido" in sql
        assert f"cd_cvm = '{CD_ITAU}'" in sql
        assert "trimestre = '3T2025'" in sql

    def test_sem_trimestre_nao_monta_sql(self):
        """SUBSTITUI `test_sem_trimestre_nao_filtra_periodo`.

        A versão anterior afirmava que célula sem período montava consulta sem
        filtro de trimestre — o que devolvia a série inteira. O contrato mudou:
        período virou obrigatório e o template recusa montar sem ele, para que a
        série inteira não possa voltar a sair por esta porta.
        """
        with pytest.raises(PeriodoIndefinido, match="sem trimestre"):
            montar_sql_celula(CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "")

    def test_nao_agrega(self):
        sql = montar_sql_celula(CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "3T2025")
        baixo = sql.lower()
        assert "group by" not in baixo
        assert not any(f"{f}(" in baixo for f in ("sum", "avg", "count", "max", "min"))

    def test_passa_na_guarda_da_rn04(self):
        from src.config import carregar_config
        from src.dados_estruturados import validar_sql

        sql = montar_sql_celula(CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "3T2025")
        assert validar_sql(sql, carregar_config())

    def test_conceito_invalido_nao_monta_sql(self):
        with pytest.raises(ErroDeIntencao, match="conceito inválido"):
            montar_sql_celula(CD_ITAU, "ebitda_ajustado", "3T2025")

    def test_trimestre_malformado_nao_monta_sql(self):
        with pytest.raises(ErroDeIntencao, match="malformado"):
            montar_sql_celula(CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "2025-Q3")

    def test_sem_companhia_nao_monta_sql(self):
        with pytest.raises(ErroDeIntencao, match="sem companhia"):
            montar_sql_celula("", CONCEITO_LUCRO_CONTROLADORES, "3T2025")

    def test_cada_celula_carrega_o_proprio_sql(self, indice):
        """Linhagem por número: auditar qual consulta sustentou qual valor."""
        bruto = PlanoBruto(
            consultas=(
                Celula("Itaú", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
                Celula("BB", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
            ),
            operacao="comparacao",
        )
        plano = validar_plano(bruto, indice, "pergunta")
        assert len({c.sql for c in plano.celulas}) == 2
        assert all(c.cd_cvm in c.sql for c in plano.celulas)


class TestAusenciaTemEndereco:
    def test_celula_vazia_sabe_quem_nao_respondeu(self):
        celula = _celula(cd_cvm=CD_BB, trimestre="4T2025")
        respondida = responder_celula(celula, ("cd_cvm",), [])
        assert respondida.vazia
        assert respondida.celula.cd_cvm == CD_BB
        assert respondida.celula.trimestre == "4T2025"

    def test_grao_duplicado_e_detectado_dentro_da_celula(self):
        colunas = (
            "cd_cvm", "denom_social", "trimestre", "conceito",
            "valor_reais", "origem", "corrigido", "tipo_periodo",
        )
        linhas = [
            (CD_ITAU, "ITAU", "3T2025", CONCEITO_LUCRO_CONTROLADORES,
             1.0, "arquivado", False, "trimestral"),
            (CD_ITAU, "ITAU", "3T2025", CONCEITO_LUCRO_CONTROLADORES,
             2.0, "arquivado", False, "trimestral"),
        ]
        respondida = responder_celula(_celula(), colunas, linhas)
        assert respondida.graos_ambiguos == ((CD_ITAU, "3T2025"),)
        assert not respondida.utilizavel

    def test_chave_da_celula_e_estavel(self):
        """A mesma célula pedida por outra pergunta tem o mesmo endereço."""
        assert _celula().chave == (
            CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "3T2025",
        )


class TestPeriodoObrigatorio:
    """Pergunta sem trimestre vira recusa — era série inteira em silêncio."""

    def test_celula_sem_periodo_recusa_com_justificativa(self, indice):
        bruto = PlanoBruto(
            consultas=(Celula("Santander", CONCEITO_LUCRO_CONTROLADORES, ""),)
        )
        with pytest.raises(PeriodoIndefinido, match="não indica o trimestre"):
            validar_plano(bruto, indice, "Qual o lucro do Santander?")

    def test_a_justificativa_diz_o_formato_esperado(self, indice):
        """Quem vai reformular precisa saber como escrever o período."""
        bruto = PlanoBruto(
            consultas=(Celula("Itaú", CONCEITO_LUCRO_CONTROLADORES, ""),)
        )
        with pytest.raises(PeriodoIndefinido, match=r"3T2025"):
            validar_plano(bruto, indice, "Qual o lucro do Itaú?")

    def test_uma_celula_sem_periodo_recusa_o_plano_inteiro(self, indice):
        """Responder as completas e calar a incompleta esconderia a lacuna."""
        bruto = PlanoBruto(
            consultas=(
                Celula("Itaú", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),
                Celula("BB", CONCEITO_LUCRO_CONTROLADORES, ""),
            ),
            operacao="comparacao",
        )
        with pytest.raises(PeriodoIndefinido):
            validar_plano(bruto, indice, "Compare Itaú no 3T2025 com o BB")

    def test_recusa_do_modelo_sem_consultas_e_respeitada(self, indice):
        bruto = PlanoBruto(
            consultas=(), recusar=True, motivo="a pergunta não diz o trimestre"
        )
        with pytest.raises(ErroDeIntencao, match="não diz o trimestre"):
            validar_plano(bruto, indice, "Qual o lucro do Itaú?")

    def test_recusa_do_modelo_com_consultas_validas_e_ignorada(self, indice):
        """Regressão do Banco Inter: cobertura nunca é decisão do modelo."""
        bruto = PlanoBruto(
            consultas=(Celula("Itaú", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),),
            recusar=True,
            motivo="essa companhia não me parece coberta",
        )
        plano = validar_plano(bruto, indice, "Qual o lucro do Itaú no 3T2025?")
        assert [c.cd_cvm for c in plano.celulas] == [CD_ITAU]


class TestFamiliasDeRecusa:
    """Uma volta à tela, a outra encaminha ao corpus — e o tipo é a diferença."""

    def test_periodo_indefinido_pede_reformulacao(self, indice):
        bruto = PlanoBruto(
            consultas=(Celula("Itaú", CONCEITO_LUCRO_CONTROLADORES, ""),)
        )
        with pytest.raises(RecusaDeReformulacao):
            validar_plano(bruto, indice, "Qual o lucro do Itaú?")

    def test_conceito_misturado_pede_reformulacao(self, indice):
        bruto = PlanoBruto(
            consultas=(
                Celula("Itaú", CONCEITO_LUCRO_CONSOLIDADO, "3T2025"),
                Celula("BB", CONCEITO_ATIVO_TOTAL, "3T2025"),
            ),
            operacao="comparacao",
        )
        with pytest.raises(RecusaDeReformulacao):
            validar_plano(bruto, indice, "Compare o lucro consolidado e o ativo")

    def test_conceito_fora_do_painel_nao_pede_reformulacao(self, indice):
        """Basileia não se resolve reescrevendo: o corpus é que pode ter."""
        bruto = PlanoBruto(consultas=(), recusar=True, motivo="Basileia não está")
        with pytest.raises(ErroDeIntencao) as capturado:
            validar_plano(bruto, indice, "Qual o índice de Basileia?")
        assert not isinstance(capturado.value, RecusaDeReformulacao)

    def test_companhia_inexistente_nao_pede_reformulacao(self, indice):
        bruto = PlanoBruto(
            consultas=(Celula("Nubank", CONCEITO_LUCRO_CONTROLADORES, "3T2025"),)
        )
        with pytest.raises(ErroDeIntencao) as capturado:
            validar_plano(bruto, indice, "Qual o lucro do Nubank no 3T2025?")
        assert not isinstance(capturado.value, RecusaDeReformulacao)


class TestCacheDeCelulas:
    COLUNAS = (
        "cd_cvm", "denom_social", "trimestre", "conceito",
        "valor_reais", "origem", "corrigido", "tipo_periodo",
    )

    def _linhas_de(self, valor):
        return [
            (CD_ITAU, "ITAU", "3T2025", CONCEITO_LUCRO_CONTROLADORES,
             valor, "arquivado", False, "trimestral")
        ]

    def _plano(self, celulas):
        return PlanoValidado(
            celulas=celulas,
            pendentes=(),
            operacao="valor",
            conceito=CONCEITO_LUCRO_CONTROLADORES,
        )

    def test_celula_repetida_nao_volta_ao_painel(self):
        chamadas = []

        def executar(sql):
            chamadas.append(sql)
            return self.COLUNAS, self._linhas_de(1.0)

        cache = CacheDeCelulas(("painel", 1, 1))
        plano = self._plano((_celula(),))
        primeira = executar_plano(plano, executar, cache)
        segunda = executar_plano(plano, executar, cache)

        assert len(chamadas) == 1
        assert primeira[0].linhas == segunda[0].linhas
        assert (cache.acertos, cache.faltas) == (1, 1)

    def test_celulas_distintas_consultam_separado(self):
        chamadas = []

        def executar(sql):
            chamadas.append(sql)
            return self.COLUNAS, self._linhas_de(1.0)

        cache = CacheDeCelulas(("painel", 1, 1))
        plano = self._plano((_celula(), _celula(trimestre="4T2025")))
        executar_plano(plano, executar, cache)
        assert len(chamadas) == 2
        assert cache.tamanho == 2

    def test_painel_reconstruido_esvazia_o_cache(self):
        """Cache que sobrevive à reconstrução serve número velho sem avisar."""
        cache = CacheDeCelulas(("painel", 10, 100))
        cache.guardar(_celula().chave, (_linha(),))
        assert cache.tamanho == 1

        assert cache.conferir_painel(("painel", 10, 200))
        assert cache.tamanho == 0
        assert cache.obter(_celula().chave) is None

    def test_painel_inalterado_preserva_o_cache(self):
        cache = CacheDeCelulas(("painel", 10, 100))
        cache.guardar(_celula().chave, (_linha(),))
        assert not cache.conferir_painel(("painel", 10, 100))
        assert cache.tamanho == 1

    def test_grao_ambiguo_e_recalculado_a_partir_do_cache(self):
        """O cache guarda linhas; a detecção de grão duplicado não some nele."""
        def executar(sql):
            return self.COLUNAS, self._linhas_de(1.0) + self._linhas_de(2.0)

        cache = CacheDeCelulas(("painel", 1, 1))
        plano = self._plano((_celula(),))
        executar_plano(plano, executar, cache)
        do_cache = executar_plano(plano, executar, cache)
        assert do_cache[0].graos_ambiguos == ((CD_ITAU, "3T2025"),)
        assert not do_cache[0].utilizavel

    def test_sem_cache_continua_funcionando(self):
        chamadas = []

        def executar(sql):
            chamadas.append(sql)
            return self.COLUNAS, self._linhas_de(1.0)

        plano = self._plano((_celula(),))
        executar_plano(plano, executar, None)
        executar_plano(plano, executar, None)
        assert len(chamadas) == 2

    def test_assinatura_muda_quando_o_arquivo_muda(self, tmp_path):
        painel = tmp_path / "cvm.duckdb"
        painel.write_bytes(b"a")
        antes = assinatura_painel(painel)
        painel.write_bytes(b"conteudo diferente e maior")
        assert assinatura_painel(painel) != antes

    def test_assinatura_de_painel_ausente_e_propria(self, tmp_path):
        """Painel que reaparece também precisa invalidar o cache."""
        ausente = assinatura_painel(tmp_path / "nao_existe.duckdb")
        (tmp_path / "nao_existe.duckdb").write_bytes(b"a")
        assert assinatura_painel(tmp_path / "nao_existe.duckdb") != ausente


class TestPromptDoPlano:
    def test_vocabulario_vem_do_mapa_e_nao_de_lista_paralela(self):
        prompt = prompt_plano()
        for conceito in CONCEITOS:
            assert conceito in prompt

    def test_prompt_proibe_o_modelo_de_julgar_cobertura(self):
        assert "cobertura de companhia não é decisão sua" in prompt_plano()

    def test_prompt_exige_conceito_unico_ao_confrontar(self):
        """A guarda está em código; o prompt evita a recusa evitável."""
        assert "MESMO conceito" in prompt_plano()

    def test_prompt_exige_periodo_e_proibe_inventa_lo(self):
        prompt = prompt_plano()
        assert "OBRIGATÓRIO" in prompt
        assert "não invente" in prompt
