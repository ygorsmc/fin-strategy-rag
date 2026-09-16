"""Correções da guarda RN02 vindas da auditoria manual de 2026-08-22.

A auditoria das 15 achou **5 descartes indevidos e nenhuma alucinação
publicada** — o modo de falha medido é a guarda recusar resposta que ESTAVA
fundamentada. Cada correção abaixo vem com a contraprova de que ela não abriu
buraco: afrouxar a guarda é fácil, e o que a torna útil é continuar recusando
o caso que ela existe para pegar.
"""

from __future__ import annotations

import pytest

from src.config import Config
from src.geracao import (
    Citacao,
    _clausula_numerica_sem_conteudo_inventado,
    _GRUPOS_PERCENTUAIS,
    _numero_tem_dimensao_de_metrica,
    _radical_flexional,
    _rotulo_de_destaque,
    _tokens_qualitativos,
    dividir_em_clausulas,
    fatos_numericos_do_chunk,
    numeros_da_resposta_estao_fundamentados,
)
from src.ingestao import Chunk
from src.normalizacao import extrair_numeros_ptbr_tipados


def _chunk(texto: str, **kwargs) -> Chunk:
    base = dict(
        id="c1",
        empresa="SANTANDER",
        trimestre="4T2025",
        documento="santander_release_4T2025",
        pagina_inicio=3,
        pagina_fim=3,
        posicao_no_documento=1,
    )
    base.update(kwargs)
    return Chunk(texto=texto, **base)


class TestSeparadorDeOracoes:
    """Ponto de abreviação não é fim de frase (medido: 5,2% dos pontos)."""

    @pytest.mark.parametrize(
        "texto",
        [
            "queda de 0,6 p.p. no trimestre e 1,5 p.p. em relação a Set24",
            "cresceu 2,3% a.a. no período",
            "avanço vs. o trimestre anterior",
            "rótulo prev. do painel",
        ],
    )
    def test_abreviacao_nao_parte_a_oracao(self, texto: str):
        assert len([c for c in dividir_em_clausulas(texto) if c.strip()]) == 1

    def test_fim_de_frase_de_verdade_continua_partindo(self):
        """Contraprova: a correção não pode colar duas frases distintas."""
        texto = "A carteira foi R$ 708,2 bilhões. Segundo o Santander, cresceu."
        assert len([c for c in dividir_em_clausulas(texto) if c.strip()]) == 2

    def test_ponto_e_virgula_e_quebra_de_linha_continuam_separando(self):
        assert len(dividir_em_clausulas("um; dois")) == 2
        assert len(dividir_em_clausulas("um\ndois")) == 2
        assert len(dividir_em_clausulas("um\ndois", quebrar_linha=False)) == 1


class TestRadicalFlexional:
    """Concordância de gênero/número do mesmo lexema não é palavra nova."""

    def test_genero_colapsa(self):
        assert _radical_flexional("impulsionado") == _radical_flexional(
            "impulsionada"
        )

    def test_plural_colapsa(self):
        assert _radical_flexional("destacados") == _radical_flexional(
            "destacado"
        )

    @pytest.mark.parametrize(
        "a, b",
        [("casa", "caso"), ("meta", "meto"), ("bola", "bolo")],
    )
    def test_palavra_curta_diferente_nao_colapsa(self, a: str, b: str):
        """Contraprova do piso de 4 caracteres: sem ele, palavras distintas
        viravam a mesma e qualquer token passaria por 'já estava na
        evidência'."""
        assert _radical_flexional(a) != _radical_flexional(b)


class TestConteudoInventado:
    EVIDENCIA = _chunk(
        "A margem financeira foi impulsionada pela evolução das receitas de "
        "crédito no trimestre."
    )

    def test_andaime_de_discurso_nao_e_conteudo_novo(self):
        clausula = (
            "Adicionalmente, a margem financeira foi impulsionado pela "
            "evolução das receitas de crédito"
        )
        assert _clausula_numerica_sem_conteudo_inventado(
            clausula, [self.EVIDENCIA], set()
        )

    def test_causa_inventada_continua_recusada(self):
        """Contraprova: a guarda existe para pegar causa fabricada."""
        clausula = (
            "A margem financeira foi impulsionada por uma fraude contábil "
            "descoberta no trimestre"
        )
        assert not _clausula_numerica_sem_conteudo_inventado(
            clausula, [self.EVIDENCIA], set()
        )

    def test_polaridade_invertida_continua_recusada(self):
        clausula = "A margem financeira não foi impulsionada pelas receitas"
        assert not _clausula_numerica_sem_conteudo_inventado(
            clausula, [self.EVIDENCIA], set()
        )


class TestRotuloDeDestaque:
    def test_rotulo_em_negrito_e_reconhecido(self):
        assert _rotulo_de_destaque("**Carteira de crédito ampliada**") == (
            "Carteira de crédito ampliada"
        )

    @pytest.mark.parametrize(
        "linha",
        [
            "**220.017**",
            "| **Total** | 100 |",
            "**Lucro de 2025**",
            "texto comum sem negrito",
            "**parcial** no meio da frase",
        ],
    )
    def test_linha_que_nao_e_rotulo_puro_e_recusada(self, linha: str):
        """Contraprova: valor em negrito e célula de tabela não podem virar
        rótulo de seção — herdariam métrica para a página inteira."""
        assert _rotulo_de_destaque(linha) == ""

    def test_valor_do_painel_herda_a_metrica_do_rotulo(self):
        chunk = _chunk(
            "## Destaques financeiros | 4T25\n"
            "**Carteira de crédito ampliada**\n"
            "R$ 708,2 bilhões (+2,8% QoQ e +3,7% YoY)\n"
        )
        grupos = {
            grupo
            for _numero, tokens, _mod in fatos_numericos_do_chunk(chunk)
            for grupo in tokens
            if grupo.startswith("metrica_")
        }
        assert "metrica_credito" in grupos

    def test_rotulo_nao_sobrescreve_metrica_propria_da_linha(self):
        """Preenche lacuna, nunca sobrescreve — senão trocar de métrica
        deixaria de ser recusa."""
        chunk = _chunk(
            "**Carteira de crédito ampliada**\n"
            "O lucro líquido somou R$ 3.882 milhões no trimestre\n"
        )
        for _numero, tokens, _mod in fatos_numericos_do_chunk(chunk):
            if "metrica_lucro" in tokens:
                assert "metrica_credito" not in tokens


class TestDimensaoDeMargem:
    def test_margem_aceita_valor_monetario(self):
        (numero,) = extrair_numeros_ptbr_tipados("R$ 0,3 bilhão")
        assert _numero_tem_dimensao_de_metrica(numero, {"metrica_margem"})

    def test_margem_continua_aceitando_percentual(self):
        (numero,) = extrair_numeros_ptbr_tipados("12,5%")
        assert _numero_tem_dimensao_de_metrica(numero, {"metrica_margem"})

    @pytest.mark.parametrize(
        "grupo",
        ["metrica_rentabilidade", "metrica_eficiencia", "metrica_inadimplencia"],
    )
    def test_indice_puro_continua_recusando_valor_em_reais(self, grupo: str):
        """Contraprova: ROE, eficiência e inadimplência não existem em reais.
        Se este teste cair, a correção da margem vazou para os índices."""
        assert grupo in _GRUPOS_PERCENTUAIS
        (numero,) = extrair_numeros_ptbr_tipados("R$ 0,3 bilhão")
        assert not _numero_tem_dimensao_de_metrica(numero, {grupo})


class TestDeltaPercentualSegueExigido:
    """A auditoria marcou TSTC008 como descarte indevido, mas a medição diz o
    contrário: a diferença entre duas taxas é em PONTOS PERCENTUAIS. O modelo
    escreveu "= 1,8%" e a guarda recusou — corretamente. Fica travado para que
    nenhuma correção futura afrouxe isso por engano."""

    def _fundamenta(self, resposta: str) -> bool:
        chunk = _chunk(
            "O ROAE anualizado do BTG foi de 26,6% e o do Itaú foi de 24,8%."
        )
        return numeros_da_resposta_estao_fundamentados(
            resposta,
            (Citacao("SANTANDER", "santander_release_4T2025", "4T2025", 3),),
            [chunk],
            Config().tolerancia_numerica_pct,
            "qual foi a diferença",
        )

    def test_diferenca_de_taxas_escrita_em_porcento_e_recusada(self):
        assert not self._fundamenta("Cálculo: 26,6% - 24,8% = 1,8%")


class TestRotuloDeLinhaComColunaMesclada:
    """Célula mesclada do sumário fazia a linha inteira perder a métrica.

    Achado em 2026-09-14, com a pergunta congelada TSTF004. O modelo respondeu
    `R$ 11.508 milhões` — o valor do gabarito —, citou a página 5, que é a
    página certa, e a RN02 rebaixou.

    A causa não estava na guarda e sim na evidência que chegava até ela. O
    sumário do Itaú tem a primeira coluna mesclada, e o OCR a devolve como um
    ano solto: `| 2025 | Resultado Recorrente Gerencial | 11.508 | ...`. O
    seletor de rótulo pegava a primeira célula sem número — o ano —, que não
    produz token de métrica nenhum. A linha chegava anônima à comparação e
    `metricas_compativeis` não tinha como casar. Rótulo agora exige letra.
    """

    LINHA_SUMARIO = (
        "|  Em R$ milhões (exceto onde indicado) |   | 2T25 | 1T25 | 2T24  |\n"
        "| --- | --- | --- | --- | --- |\n"
        "|  2025 | Resultado Recorrente Gerencial | 11.508 | 11.128 | 10.072  |\n"
        "|   |  Margem Financeira Gerencial | 31.177 | 30.322 | 27.665  |\n"
    )

    def _fundamenta(self, resposta: str) -> bool:
        chunk = _chunk(
            self.LINHA_SUMARIO,
            empresa="ITAU",
            trimestre="2T2025",
            documento="itau_release_2T2025",
            pagina_inicio=5,
            pagina_fim=5,
        )
        return numeros_da_resposta_estao_fundamentados(
            resposta,
            (Citacao("ITAU", "itau_release_2T2025", "2T2025", 5),),
            [chunk],
            Config().tolerancia_numerica_pct,
            "Segundo a análise gerencial do Itaú Unibanco qual foi o "
            "resultado recorrente gerencial no 2T2025?",
        )

    def test_a_linha_com_ano_na_primeira_coluna_mantem_a_metrica(self):
        chunk = _chunk(self.LINHA_SUMARIO, empresa="ITAU")
        tokens_do_valor = [
            tokens
            for numero, tokens, _mod in fatos_numericos_do_chunk(chunk)
            if numero.valor == 11_508_000_000.0
        ]
        assert tokens_do_valor, "o valor do sumário sumiu da evidência"
        assert "metrica_lucro" in tokens_do_valor[0], (
            "a célula mesclada voltou a ser eleita rótulo e a linha perdeu o "
            "grupo métrico"
        )

    def test_resposta_com_valor_e_pagina_certos_e_aceita(self):
        assert self._fundamenta(
            "O resultado recorrente gerencial no 2T25 foi de R$ 11.508 milhões."
        )

    @pytest.mark.parametrize(
        "resposta",
        [
            # O 11.508 é do resultado recorrente, não da margem financeira.
            "A margem financeira gerencial no 2T25 foi de R$ 11.508 milhões.",
            "O resultado recorrente gerencial no 2T25 foi de R$ 99.999 milhões.",
            "O resultado recorrente gerencial no 2T24 foi de R$ 11.508 milhões.",
        ],
    )
    def test_contraprova_a_guarda_nao_ficou_permissiva(self, resposta: str):
        """Recuperar o rótulo certo precisa RECUSAR o que não bate com ele."""
        assert not self._fundamenta(resposta)

    def test_celula_sem_letra_nunca_e_rotulo(self):
        """Ano, traço e marcador de nota não nomeiam métrica."""
        chunk = _chunk(
            "|  2024 | - | Lucro líquido recorrente | 3.882 |\n",
            empresa="SANTANDER",
        )
        tokens = [t for _n, t, _m in fatos_numericos_do_chunk(chunk)]
        assert any("metrica_lucro" in t for t in tokens)
