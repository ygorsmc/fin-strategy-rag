"""Testes do parser numérico pt-BR e apelidos de banco (seções 5.6 e 5.8).

Exigência do AGENTS.md (etapa 5): este módulo é o pré-requisito do verificador
de exatidão numérica — sem ele, falsos negativos em massa (modo de falha nº 4).

Os testes de contratos ainda não implementados estão marcados com skip
explícito; ao implementar a etapa 5, basta remover o marcador.
"""

from __future__ import annotations

import pytest

from src import normalizacao as norm

pendente = pytest.mark.skip(
    reason="Boilerplate: implementação pendente — AGENTS.md etapa 5 (normalização)"
)


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


@pendente
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


@pendente
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


@pendente
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


@pendente
class TestExtrairBancosCitados:
    def test_comparativa_dois_bancos_na_ordem(self):
        texto = "Quem teve maior ROE no 4T2025: Itaú ou Bradesco?"
        assert norm.extrair_bancos_citados(texto) == ["ITAU", "BRADESCO"]

    def test_sem_duplicatas(self):
        texto = "O Itaú (Itaú Unibanco) reportou lucro"
        assert norm.extrair_bancos_citados(texto) == ["ITAU"]


@pendente
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
