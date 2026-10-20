"""Testes do parser numérico pt-BR e apelidos de banco (seções 5.6 e 5.8).

Exigência do AGENTS.md (etapa 5): este módulo é o pré-requisito do verificador
de exatidão numérica — sem ele, falsos negativos em massa (modo de falha nº 4).

Os testes de contratos ainda não implementados estão marcados com skip
explícito; ao implementar a etapa 5, basta remover o marcador.
"""

from __future__ import annotations

import pytest

from src import normalizacao as norm


# --- Já implementado (deve passar) -------------------------------------------


class TestRemoverAcentos:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("Itaú", "Itau"),
            ("provisão", "provisao"),
            ("inadimplência", "inadimplencia"),
            ("Índice", "Indice"),
            ("sem acento", "sem acento"),
        ],
    )
    def test_casos(self, entrada, esperado):
        assert norm.remover_acentos(entrada) == esperado


class TestNormalizarTextoBm25:
    def test_minusculas_e_acentos(self):
        # Seção 5.6: sem isso, a E1 perde exatamente os termos que deveria achar
        assert norm.normalizar_texto_bm25("Provisão do Itaú") == [
            "provisao",
            "do",
            "itau",
        ]

    def test_pontuacao_descartada(self):
        assert norm.normalizar_texto_bm25("R$ 2,3 bilhões (4T2025)!") == [
            "r",
            "2",
            "3",
            "bilhoes",
            "4t2025",
        ]

    def test_texto_vazio(self):
        assert norm.normalizar_texto_bm25("") == []


class TestTabelaDeApelidos:
    def test_bancos_do_corpus_presentes(self, config_padrao):
        # Todos os bancos configurados têm entrada na tabela de apelidos
        assert set(config_padrao.bancos) <= set(norm.APELIDOS_BANCOS)

    def test_instituicao_armadilha_presente(self):
        # Nubank é a armadilha adversarial (seção 5.2) — precisa ser
        # reconhecível na pergunta mesmo estando fora do corpus
        assert "NUBANK" in norm.APELIDOS_BANCOS

    def test_apelidos_sem_acento_e_minusculos(self):
        # Contrato: matching acontece sobre texto sem acento/minúsculo
        for apelidos in norm.APELIDOS_BANCOS.values():
            for apelido in apelidos:
                assert apelido == norm.remover_acentos(apelido).lower()


# --- Contratos pendentes (etapa 5) -------------------------------------------


class TestNormalizarNumeroPtbr:
    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("R$ 2,3 bilhões", 2_300_000_000.0),
            ("1.234,5 milhões", 1_234_500_000.0),
            ("R$ 1.234", 1_234.0),
            ("1,9 mil", 1_900.0),
            ("R$ 5,4 bi", 5_400_000_000.0),
            ("320 mi", 320_000_000.0),
            ("42", 42.0),
        ],
    )
    def test_valores_monetarios(self, texto, esperado):
        assert norm.normalizar_numero_ptbr(texto) == pytest.approx(esperado)

    @pytest.mark.parametrize(
        "texto,esperado",
        [("23,4%", 0.234), ("3,2 %", 0.032), ("100%", 1.0)],
    )
    def test_percentuais_viram_fracao(self, texto, esperado):
        assert norm.normalizar_numero_ptbr(texto) == pytest.approx(esperado)

    @pytest.mark.parametrize("texto", ["sem número aqui", "", "R$"])
    def test_sem_numero_devolve_none(self, texto):
        assert norm.normalizar_numero_ptbr(texto) is None

    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("R$1.090,4 bilhão", 1_090_400_000_000.0),
            ("R$ 6,3 milhão", 6_300_000.0),
            ("R$1.090,4 bilhao", 1_090_400_000_000.0),
            ("R$ 6,3 milhao", 6_300_000.0),
        ],
    )
    def test_unidades_singulares_com_e_sem_acento(self, texto, esperado):
        assert norm.normalizar_numero_ptbr(texto) == pytest.approx(esperado)


class TestValoresEquivalentes:
    def test_dentro_da_tolerancia_de_1_pct(self):
        assert norm.valores_equivalentes(1_000.0, 1_009.0, tolerancia_pct=1.0)

    def test_fora_da_tolerancia(self):
        assert not norm.valores_equivalentes(1_000.0, 1_020.0, tolerancia_pct=1.0)

    def test_arredondamento_de_exibicao(self):
        # "R$ 2,3 bi" divulgado vs. 2.31e9 apurado -> equivalentes (seção 5.8)
        assert norm.valores_equivalentes(2.3e9, 2.31e9, tolerancia_pct=1.0)

    def test_ordem_de_grandeza_diferente_nao_equivale(self):
        # milhares vs. milhões SEM parser correto não pode "passar"
        assert not norm.valores_equivalentes(2_300.0, 2_300_000.0)


class TestCanonizarBanco:
    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("Qual o ROE do Itaú Unibanco?", "ITAU"),
            ("lucro do itau no 4T2025", "ITAU"),
            ("resultado do Banco do Brasil", "BB"),
            ("BBAS3 divulgou resultado", "BB"),
            ("carteira do BTG Pactual", "BTG"),
            ("provisões do Bradesco", "BRADESCO"),
            ("Santander Brasil no trimestre", "SANTANDER"),
            ("qual o lucro do Nubank?", "NUBANK"),
        ],
    )
    def test_apelidos(self, texto, esperado):
        assert norm.canonizar_banco(texto) == esperado

    def test_sem_banco_devolve_none(self):
        assert norm.canonizar_banco("qual foi a inflação do período?") is None

    def test_bb_exige_fronteira_de_palavra(self):
        # "bb" não pode casar dentro de outra palavra
        assert norm.canonizar_banco("o clube ABBA anunciou") is None


class TestExtrairBancosCitados:
    def test_comparativa_dois_bancos_na_ordem(self):
        texto = "Quem teve maior ROE no 4T2025: Itaú ou Bradesco?"
        assert norm.extrair_bancos_citados(texto) == ["ITAU", "BRADESCO"]

    def test_sem_duplicatas(self):
        texto = "O Itaú (Itaú Unibanco) reportou lucro"
        assert norm.extrair_bancos_citados(texto) == ["ITAU"]


class TestExtrairTrimestreCitado:
    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("lucro no 4T2025", "4T2025"),
            ("resultado do 1t2026", "1T2026"),
            ("resultado do ano de 2019", None),  # ano sem trimestre não é filtro
            ("qual o ROE médio?", None),
        ],
    )
    def test_casos(self, texto, esperado):
        assert norm.extrair_trimestre_citado(texto) == esperado


class TestTrimestrePorExtenso:
    """Regressão de 2026-09-20: "segundo trimestre de 2024" não casava em
    nada, `extrair_trimestres_citados` devolvia `[]`, e o gabarito lia lista
    vazia como "pergunta sem período" — despejando os seis trimestres do
    painel em vez de dizer, numa frase, que 2T2024 não está lá. O usuário
    tinha dito o período; o sistema não sabia ler a forma em que foi dito.
    """

    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("qual o lucro do Itaú no segundo trimestre de 2024?", "2T2024"),
            ("resultado do primeiro trimestre de 2025", "1T2025"),
            ("balanço do terceiro trimestre de 2025", "3T2025"),
            ("lucro do quarto trimestre de 2025", "4T2025"),
            # Ano com dois dígitos, mesma canonização da forma abreviada.
            ("segundo trimestre de 24", "2T2024"),
            # Sem "de": forma igualmente comum em português falado.
            ("segundo trimestre 2024", "2T2024"),
            # Símbolo de ordinal, com e sem o erro comum do sinal de grau.
            ("no 2º trimestre de 2024", "2T2024"),
            ("no 2° trimestre de 2024", "2T2024"),
            ("no 1o trimestre de 2025", "1T2025"),
            # Maiúsculas soltas não quebram o reconhecimento.
            ("Segundo Trimestre de 2024", "2T2024"),
        ],
    )
    def test_formas_por_extenso_sao_canonizadas(self, texto, esperado):
        assert norm.extrair_trimestre_citado(texto) == esperado

    @pytest.mark.parametrize(
        "texto",
        [
            "no primeiro trimestre do ano",  # sem ano numérico: nada a ancorar
            "nos dois primeiros trimestres de 2024",  # plural: é intervalo, não ponto
            "o trimestre foi bom para o Itaú",  # sem ordinal: não é referência
        ],
    )
    def test_formas_ambiguas_nao_viram_filtro(self, texto):
        """Mesma disciplina de "ano sem trimestre não é filtro": preferir
        devolver nada a inventar um período que o texto não determina."""
        assert norm.extrair_trimestre_citado(texto) is None

    def test_ordem_de_aparicao_mistura_as_duas_grafias(self):
        """Comparativa com uma forma de cada tipo preserva a ordem do texto."""
        texto = "Compare o quarto trimestre de 2025 com 1T2026"
        assert norm.extrair_trimestres_citados(texto) == ["4T2025", "1T2026"]

    def test_mesma_referencia_nas_duas_formas_nao_duplica(self):
        texto = "no 2T2024, ou seja, no segundo trimestre de 2024"
        assert norm.extrair_trimestres_citados(texto) == ["2T2024"]


class TestRegressoesNumerosFinanceiros:
    def test_prioriza_valor_com_unidade_e_ignora_trimestre_ticker_e_ano(self):
        texto = "No 3T2025, BPAC11 reportou lucro de R$ 31.382 milhões."
        assert norm.extrair_numeros_ptbr(texto) == pytest.approx([31_382_000_000.0])
        assert norm.normalizar_numero_ptbr(texto) == pytest.approx(31_382_000_000.0)

    def test_extrai_todos_os_valores_qualificados(self):
        texto = "ROAE de 24,8% no Itaú e 26,6% no BTG; lucro de R$ 2,3 bi."
        assert norm.extrair_numeros_ptbr(texto) == pytest.approx(
            [0.248, 0.266, 2_300_000_000.0]
        )

    def test_nao_descarta_numero_nu_quando_ha_valor_qualificado(self):
        texto = "BTG: R$ 2 bilhões; Itaú: 999.000.000"
        assert norm.extrair_numeros_ptbr(texto) == pytest.approx(
            [2_000_000_000.0, 999_000_000.0]
        )

    def test_tabela_herda_escala_declarada(self):
        texto = (
            "Em R$ milhões (exceto onde indicado) 3T25 2T25\n"
            "Margem Financeira Gerencial 31.382 31.177\n"
            "ROAE 23,3% 22,7%"
        )
        assert norm.extrair_numeros_ptbr(texto) == pytest.approx(
            [31_382_000_000.0, 31_177_000_000.0, 0.233, 0.227]
        )

    @pytest.mark.parametrize(
        "cabecalho,multiplicador",
        [("Em R$ milhão", 1_000_000.0), ("Em R$ bilhão", 1_000_000_000.0)],
    )
    def test_tabela_herda_escala_singular(self, cabecalho, multiplicador):
        texto = f"{cabecalho}\nLucro 6,3\nPrejuízo (1,2)"
        assert norm.extrair_numeros_ptbr(texto) == pytest.approx(
            [6.3 * multiplicador, -1.2 * multiplicador]
        )

    def test_bps_e_pontos_base_viram_fracao(self):
        assert norm.extrair_numeros_ptbr(
            "alta de 404 bps e queda de 12 pontos-base"
        ) == pytest.approx([0.0404, 0.0012])

    def test_enumeracoes_nao_viram_valores_financeiros(self):
        assert norm.extrair_numeros_ptbr("1) sazonalidade\n2. câmbio") == []

    def test_escala_monetaria_nao_contamina_percentual_ou_quantidade(self):
        texto = (
            "Em R$ milhões\nLucro 500\nROAE (%) 26,6\n"
            "Quantidade de clientes 42"
        )
        assert norm.extrair_numeros_ptbr(texto) == pytest.approx(
            [500_000_000.0, 0.266, 42.0]
        )

    def test_ano_e_pagina_nao_viram_valores_mesmo_com_moeda(self):
        texto = "pág. 5\nEm 2025, o lucro foi de R$ 2 bilhões."
        assert norm.extrair_numeros_ptbr(texto) == pytest.approx(
            [2_000_000_000.0]
        )

    def test_preserva_sinais_e_negativo_contabil(self):
        assert norm.extrair_numeros_ptbr(
            "A margem variou -3,2% e a perda foi (R$ 1,5 milhão)."
        ) == pytest.approx([-0.032, -1_500_000.0])

    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("crescimento da margem (+14,8%) no trimestre", [0.148]),
            ("Volume médio (+ R$ 0,5 bilhão), com impacto", [500_000_000.0]),
            ("Mix de produtos (- R$ 0,3 bilhão), devido", [-300_000_000.0]),
            ("a perda foi (R$ 1,5 milhão).", [-1_500_000.0]),
        ],
    )
    def test_sinal_explicito_entre_parenteses_vence_negativo_contabil(
        self, texto, esperado
    ):
        """`(+14,8%)` é variação positiva; sem sinal, o parêntese segue negativo."""
        assert norm.extrair_numeros_ptbr(texto) == pytest.approx(esperado)

    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("R$ -6,3 milhão", -6_300_000.0),
            ("(R$ 1.090,4 bilhão)", -1_090_400_000_000.0),
        ],
    )
    def test_unidades_singulares_preservam_negativos(self, texto, esperado):
        assert norm.normalizar_numero_ptbr(texto) == pytest.approx(esperado)

    @pytest.mark.parametrize(
        "texto",
        [
            "R$ 6,3 milhãoextra",
            "R$ 6,3 bilhãoextra",
            "R$ 6,3 milhoesextra",
            "R$ 6,3 bilhoesextra",
        ],
    )
    def test_unidade_parcial_recusa_em_vez_de_casar_prefixo(self, texto):
        assert norm.contem_notacao_numerica_nao_suportada(texto)
        assert norm.normalizar_numero_ptbr(texto) is None

    def test_numero_gigante_recusa_sem_overflow_ou_excecao(self):
        texto = "R$ " + "9" * 400 + " milhões"
        assert norm.contem_notacao_numerica_nao_suportada(texto)
        assert norm.extrair_numeros_ptbr_tipados(texto) == []

    def test_ticker_e_trimestre_sozinhos_nao_sao_numeros(self):
        assert norm.extrair_numeros_ptbr("BPAC11 no 4T2025") == []

    def test_extrai_multiplos_trimestres_sem_duplicata(self):
        assert norm.extrair_trimestres_citados(
            "Compare 4T2025 com 1t2026 e novamente 4T2025"
        ) == ["4T2025", "1T2026"]

    @pytest.mark.parametrize(
        "esperado,obtido,tolerancia",
        [
            (float("nan"), 1.0, 1.0),
            (1.0, float("inf"), 1.0),
            (1.0, 1.0, -0.1),
            (True, 1.0, 1.0),
        ],
    )
    def test_comparador_rejeita_valores_e_tolerancia_invalidos(
        self, esperado, obtido, tolerancia
    ):
        with pytest.raises(ValueError):
            norm.valores_equivalentes(esperado, obtido, tolerancia)

    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("ROAE de 26.6%", 0.266),
            ("aumento de 0,1 p.p.", 0.001),
            ("R$ 1.234", 1234.0),
        ],
    )
    def test_ponto_decimal_de_llm_sem_quebrar_milhar(self, texto, esperado):
        assert norm.normalizar_numero_ptbr(texto) == pytest.approx(esperado)
