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
    RespostaGerada,
    _clausula_numerica_sem_conteudo_inventado,
    _escopo_solicitado_esta_coberto,
    _GRUPOS_PERCENTUAIS,
    _numero_tem_dimensao_de_metrica,
    _radical_flexional,
    _rotulo_de_destaque,
    _tokens_qualitativos,
    aplicar_guardas_pos_llm,
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


# --- Reaplicação de 2026-10-20 sobre a rodada congelada c3a03ff7 -------------
#
# `scripts/reaplicar_guarda_rn02.py` reaplicou a guarda às 4 × 45 respostas
# gravadas. Os descartes que o DeepEval julgou fiéis vinham, na maioria, de
# evidência que chegava sem rótulo à comparação, e não de arredondamento: o
# infográfico de destaques do release, que o OCR devolve linha a linha.


def _bradesco(texto: str, trimestre: str = "2T2025", pagina: int = 7) -> Chunk:
    return _chunk(
        texto,
        empresa="BRADESCO",
        trimestre=trimestre,
        documento=f"bradesco_release_{trimestre}",
        pagina_inicio=pagina,
        pagina_fim=pagina,
    )


def _fundamenta_em(chunk: Chunk, resposta: str, pergunta: str = "") -> bool:
    return numeros_da_resposta_estao_fundamentados(
        resposta,
        (Citacao(chunk.empresa, chunk.documento, chunk.trimestre, chunk.pagina_inicio),),
        [chunk],
        Config().tolerancia_numerica_pct,
        pergunta,
    )


class TestPainelDeDestaques:
    """Rótulo numa linha, valor na seguinte, sem negrito (TSTF007, TSTF008)."""

    PAINEL = (
        "destaques 2T25\n"
        "lucro líquido recorrente consolidado\n"
        "## R$ 6,1 bi\n"
        "Δ 3,5% t/t Δ 28,6% a/a\n"
        "ROAE 2T25\n"
        "14,6%\n"
        "Δ 0,2 p.p. t/t Δ 3,2 p.p. a/a\n"
    )

    def test_valor_em_titulo_markdown_e_valor_e_nao_titulo(self):
        """`## R$ 6,1 bi` virava título de seção e o número sumia."""
        fatos = fatos_numericos_do_chunk(_bradesco(self.PAINEL))
        do_lucro = [t for n, t, _m in fatos if n.valor == 6_100_000_000.0]
        assert do_lucro and "metrica_lucro" in do_lucro[0]

    def test_valor_solto_herda_o_rotulo_da_linha_de_cima(self):
        fatos = fatos_numericos_do_chunk(_bradesco(self.PAINEL))
        do_roae = [t for n, t, _m in fatos if abs(n.valor - 0.146) < 1e-9]
        assert do_roae and "metrica_rentabilidade" in do_roae[0]
        variacao = [t for n, t, _m in fatos if abs(n.valor - 0.035) < 1e-9]
        assert variacao and "metrica_lucro" in variacao[0]

    def test_resposta_que_repete_o_release_e_aceita(self):
        assert _fundamenta_em(
            _bradesco(self.PAINEL),
            "O lucro líquido recorrente consolidado no 2T2025 foi de R$ 6,1 bi.",
        )

    @pytest.mark.parametrize(
        "resposta",
        [
            # 6,1 bi é lucro, não carteira; 14,6% é ROAE, não inadimplência.
            "A carteira de crédito no 2T2025 foi de R$ 6,1 bi.",
            "A inadimplência acima de 90 dias no 2T2025 foi de 14,6%.",
            "O lucro líquido recorrente consolidado no 2T2025 foi de R$ 6,2 bi.",
        ],
    )
    def test_contraprova_rotulo_herdado_ainda_recusa_troca(self, resposta: str):
        assert not _fundamenta_em(_bradesco(self.PAINEL), resposta)

    def test_linha_de_prosa_encerra_o_painel(self):
        """O rótulo vale para o valor logo abaixo, não para a página toda."""
        chunk = _bradesco(
            "ROAE 2T25\n"
            "Os resultados do trimestre refletem a estratégia de longo prazo.\n"
            "14,6%\n"
        )
        fatos = fatos_numericos_do_chunk(chunk)
        assert all("metrica_rentabilidade" not in t for _n, t, _m in fatos)

    def test_rotulo_nao_sobrescreve_metrica_propria_do_valor(self):
        chunk = _bradesco("ROAE 2T25\nlucro de R$ 6,1 bi\n")
        for _numero, tokens, _mod in fatos_numericos_do_chunk(chunk):
            assert "metrica_rentabilidade" not in tokens

    def test_valor_em_negrito_no_meio_da_moeda(self):
        """`R$ **3,8** bilhões` não era lido como reais (TSTF013)."""
        chunk = _chunk(
            "## Lucro Líquido Ajustado\nR$ **3,8** bilhões - 2T25\n",
            empresa="BB",
            trimestre="2T2025",
            documento="bb_release_2T2025",
            pagina_inicio=10,
            pagina_fim=10,
        )
        assert _fundamenta_em(
            chunk, "O Lucro Líquido Ajustado no 2T25 foi de R$ 3,8 bilhões."
        )
        assert not _fundamenta_em(
            chunk, "O Lucro Líquido Ajustado no 2T25 foi de R$ 3,9 bilhões."
        )


class TestSegmentoFechaOPainel:
    """O ROAE do Grupo Segurador não fundamenta o ROAE do Bradesco (TSTC004).

    A primeira versão da leitura de painel publicava, na estratégia híbrida,
    "o Bradesco apresentou ROAE de 21,6%": o 21,6% é do segmento de seguros e
    o consolidado é 15,8%. O infográfico emenda os dois painéis sem quebra.
    """

    PAINEL = (
        "Inadimplência acima de 90 dias\n"
        "4,2%\n"
        "Grupo Segurador\n"
        "Lucro Líquido Recorrente\n"
        "R$ 2,8 bi\n"
        "∇ 1,5% t/t Δ 13,0% a/a\n"
        "ROAE\n"
        "21,6%\n"
    )

    def test_valor_do_segmento_nao_herda_rotulo(self):
        fatos = fatos_numericos_do_chunk(_bradesco(self.PAINEL, "1T2026", 6))
        for numero, tokens, _mod in fatos:
            if abs(numero.valor - 0.216) < 1e-9 or numero.valor == 2_800_000_000.0:
                assert not tokens & {"metrica_rentabilidade", "metrica_lucro"}

    def test_rentabilidade_do_segmento_nao_vira_a_do_banco(self):
        assert not _fundamenta_em(
            _bradesco(self.PAINEL, "1T2026", 6),
            "No 1T2026, o Bradesco apresentou ROAE de 21,6%.",
        )

    def test_painel_consolidado_antes_do_segmento_continua_valendo(self):
        assert _fundamenta_em(
            _bradesco(self.PAINEL, "1T2026", 6),
            "No 1T2026, a inadimplência acima de 90 dias do Bradesco foi de 4,2%.",
        )

    def test_cabecalho_generico_reabre_o_painel(self):
        chunk = _bradesco(self.PAINEL + "destaques 1T26\nROAE 1T26\n15,8%\n", "1T2026", 6)
        assert _fundamenta_em(chunk, "No 1T2026, o ROAE do Bradesco foi de 15,8%.")

    def test_legenda_de_unidade_nao_e_cabecalho_de_painel(self):
        """`R$ milhões` classificada como segmento apagava a escala da tabela
        (TSTF006 e TSTF012 caíam na reaplicação)."""
        chunk = _chunk(
            "R$ milhões\n"
            "|  | 4T25 |\n"
            "| --- | --- |\n"
            "| Lucro líquido gerencial | 3.882 |\n"
        )
        assert _fundamenta_em(
            chunk, "O lucro líquido gerencial no 4T25 foi de R$ 3.882 milhões."
        )


class TestCelulaQueNomeiaAMetrica:
    """Coluna mesclada com PALAVRA (`| Desempenho | Retorno ... |`), TSTC008."""

    TABELA = (
        "Em R$ milhões (exceto onde indicado)\n"
        "|   |  | 1T26 | 4T25 | 1T25  |\n"
        "| --- | --- | --- | --- | --- |\n"
        "|  BRF | Resultado Recorrente Gerencial | 12.282 | 12.317 | 11.128  |\n"
        "|  Desempenho | Retorno Recorrente Gerencial sobre o Patrimônio Líquido "
        "Médio anualizado - Consolidado ^{(3)} | 24,8% | 24,4% | 22,5%  |\n"
    )

    def _itau(self) -> Chunk:
        return _chunk(
            self.TABELA,
            empresa="ITAU",
            trimestre="1T2026",
            documento="itau_release_1T2026",
            pagina_inicio=5,
            pagina_fim=5,
        )

    def test_retorno_sobre_patrimonio_ganha_a_metrica(self):
        assert _fundamenta_em(
            self._itau(),
            "No 1T2026, o retorno recorrente gerencial sobre o patrimônio "
            "líquido médio anualizado consolidado do Itaú foi de 24,8%.",
        )

    def test_contraprova_coluna_e_metrica_continuam_conferidas(self):
        # 24,4% é a coluna do 4T25; 24,8% não é margem.
        assert not _fundamenta_em(
            self._itau(),
            "No 1T2026, o retorno recorrente gerencial sobre o patrimônio "
            "líquido do Itaú foi de 24,4%.",
        )
        assert not _fundamenta_em(
            self._itau(), "No 1T2026, a margem financeira do Itaú foi de 24,8%."
        )


class TestIdentificadorDeDocumentoNaFrase:
    """`no documento bb_release_2T2025` é metadado, não conteúdo (TSTF013)."""

    CHUNK = (
        "## Lucro Líquido Ajustado\n"
        "R$ **3,8** bilhões - 2T25\n"
    )

    def _bb(self) -> Chunk:
        return _chunk(
            self.CHUNK,
            empresa="BB",
            trimestre="2T2025",
            documento="bb_release_2T2025",
            pagina_inicio=10,
            pagina_fim=10,
        )

    @pytest.mark.parametrize(
        "resposta",
        [
            "Segundo o Banco do Brasil, no documento bb_release_2T2025 (pág. 10), "
            "o Lucro Líquido Ajustado foi de R$ 3,8 bilhões no 2T25.",
            "Segundo o Banco do Brasil | bb_release_2T2025 | 2T2025 | pág. 10, "
            "o Lucro Líquido Ajustado foi de R$ 3,8 bilhões no 2T25.",
        ],
    )
    def test_identificador_copiado_nao_derruba_a_resposta(self, resposta: str):
        assert _fundamenta_em(self._bb(), resposta)

    def test_contraprova_numero_da_pagina_nao_vira_valor_nem_some_o_resto(self):
        assert not _fundamenta_em(
            self._bb(),
            "Segundo o documento bb_release_2T2025, o Lucro Líquido Ajustado "
            "foi de R$ 4,1 bilhões no 2T25.",
        )


# Três correções de 2026-10-20, das perguntas livres `dev` recusadas na rodada
# real pelo app (`resultados/recusas_dev_2026-10-20.md`). As perguntas são de
# desenvolvimento: corrigir a partir delas não toca as 45 congeladas.


class TestPeriodoBaseDaComparacao:
    """`ante o 4T2025` é a base da variação, não um período pedido (DEV004).

    O release do 1T2026 já compara com o trimestre anterior. Exigir citação de
    um documento do 4T2025 recusava a resposta certa, que citava a página do
    1T2026 onde a comparação está. Os números continuam conferidos contra o
    trecho citado pela guarda numérica; só a exigência de citação muda.
    """

    PERGUNTA = (
        "Segundo a análise gerencial do Itaú Unibanco por que o NPL total de "
        "15 a 90 dias aumentou no 1T2026 ante o 4T2025?"
    )
    RESPOSTA = (
        "No Itaú Unibanco, o índice de inadimplência entre 15 e 90 dias "
        "(NPL 15-90) total aumentou em relação ao trimestre anterior devido ao "
        "crescimento de 0,23 p.p. no índice da carteira de pessoas físicas no "
        "Brasil, por conta da sazonalidade típica do período."
    )

    @staticmethod
    def _citacao(trimestre: str = "1T2026") -> tuple[Citacao, ...]:
        return (Citacao("ITAU", f"itau_release_{trimestre}", trimestre, 14),)

    def test_base_da_comparacao_nao_exige_citacao_propria(self):
        assert _escopo_solicitado_esta_coberto(
            self.PERGUNTA, self._citacao(), Config(), self.RESPOSTA
        )

    @pytest.mark.parametrize(
        "base",
        [
            "em relação ao 4T2025",
            "frente ao 4T25",
            "na comparação com o 4T2025",
            "comparado ao quarto trimestre de 2025",
        ],
    )
    def test_outras_formas_de_escrever_a_base(self, base: str):
        pergunta = f"Por que o NPL do Itaú aumentou no 1T2026 {base}?"
        assert _escopo_solicitado_esta_coberto(
            pergunta, self._citacao(), Config(), self.RESPOSTA
        )

    def test_contraprova_dois_periodos_pedidos_continuam_exigidos(self):
        assert not _escopo_solicitado_esta_coberto(
            "Qual foi o NPL de 15 a 90 dias do Itaú no 1T2026 e no 4T2025?",
            self._citacao(),
            Config(),
        )

    def test_contraprova_base_posterior_nao_e_base(self):
        # O release do 4T2025 não traz o 1T2026: só é base o período anterior
        # a outro que a pergunta pede.
        assert not _escopo_solicitado_esta_coberto(
            "Por que o NPL do Itaú mudou no 4T2025 ante o 1T2026?",
            self._citacao("4T2025"),
            Config(),
        )

    def test_contraprova_periodo_pedido_segue_exigido(self):
        assert not _escopo_solicitado_esta_coberto(
            self.PERGUNTA, self._citacao("4T2025"), Config(), self.RESPOSTA
        )

    def test_contraprova_resposta_nao_pode_trocar_de_trimestre(self):
        assert not _escopo_solicitado_esta_coberto(
            self.PERGUNTA,
            self._citacao(),
            Config(),
            "No 3T2025, o NPL de 15 a 90 dias do Itaú subiu 0,23 p.p.",
        )

    def test_mencao_a_trimestre_anterior_nao_vira_base(self):
        # "em relação ao trimestre anterior, no 1T2026" não nomeia período
        # depois da preposição: o 1T2026 continua sendo o pedido.
        assert not _escopo_solicitado_esta_coberto(
            "Quanto o NPL do Itaú subiu em relação ao trimestre anterior, "
            "no 1T2026?",
            self._citacao("4T2025"),
            Config(),
        )


class TestParafraseQualitativaFiel:
    """Frase sem número que reescreve uma oração da evidência (DEV008).

    A regra anterior exigia a mesma sequência de palavras de uma LINHA inteira
    do trecho, com o mesmo banco e o mesmo trimestre escritos nela. O release
    diz "A redução no trimestre se deve especialmente à sazonalidade em cartões
    e à variação cambial", e a resposta certa, "a queda trimestral da carteira
    ... no 1T2026 se deve especialmente à sazonalidade em cartões e à variação
    cambial", era recusada. A regra nova: toda palavra de conteúdo que não vem
    da pergunta sai da MESMA oração da evidência; banco e trimestre não escritos
    na oração vêm do documento citado; negação e direção (queda × alta) batem.
    """

    EVIDENCIA = (
        "A carteira de crédito ampliada recuou 0,4% no trimestre, porém com "
        "avanço de 3,4% no ano, encerrando o período em R$ 705.582 milhões. "
        "A redução no trimestre se deve especialmente à sazonalidade em cartões "
        "e à variação cambial. As despesas seguem sob rigoroso controle, "
        "estáveis no trimestre e com incremento de 0,9% no ano."
    )
    PERGUNTA = (
        "Segundo o Santander quais fatores explicaram a queda trimestral e o "
        "crescimento anual da carteira de crédito ampliada no 1T2026?"
    )

    def _santander(self) -> Chunk:
        return _chunk(
            self.EVIDENCIA,
            trimestre="1T2026",
            documento="santander_release_1T2026",
        )

    def test_parafrase_fiel_com_moldura_da_pergunta(self):
        assert _fundamenta_em(
            self._santander(),
            "Segundo o Santander, a queda trimestral da carteira de crédito "
            "ampliada no 1T2026 se deve especialmente à sazonalidade em cartões "
            "e à variação cambial.",
            self.PERGUNTA,
        )

    def test_contraprova_direcao_trocada_com_palavra_da_pergunta(self):
        # "crescimento" é palavra da pergunta, mas a oração da evidência fala
        # em redução: premissa falsa não vira resposta.
        assert not _fundamenta_em(
            self._santander(),
            "O crescimento trimestral da carteira se deve especialmente à "
            "sazonalidade em cartões e à variação cambial.",
            self.PERGUNTA,
        )

    def test_contraprova_juntar_duas_oracoes_da_evidencia(self):
        assert not _fundamenta_em(
            self._santander(),
            "A redução no trimestre se deve especialmente ao rigoroso controle "
            "das despesas.",
            self.PERGUNTA,
        )

    def test_contraprova_atribuir_a_outro_banco(self):
        assert not _fundamenta_em(
            self._santander(),
            "Segundo o Itaú, a queda trimestral da carteira se deve "
            "especialmente à sazonalidade em cartões e à variação cambial.",
            self.PERGUNTA,
        )

    def test_contraprova_atribuir_a_outro_trimestre(self):
        assert not _fundamenta_em(
            self._santander(),
            "No 4T2025, a queda trimestral da carteira se deve especialmente à "
            "sazonalidade em cartões e à variação cambial.",
            self.PERGUNTA,
        )

    def test_contraprova_negacao(self):
        assert not _fundamenta_em(
            self._santander(),
            "A redução no trimestre não se deve à sazonalidade em cartões nem "
            "à variação cambial.",
            self.PERGUNTA,
        )

    def test_contraprova_palavra_inventada(self):
        assert not _fundamenta_em(
            self._santander(),
            "A queda trimestral se deve especialmente à sazonalidade em cartões "
            "e à alta da inadimplência.",
            self.PERGUNTA,
        )


class TestMotivoDaRecusaQualitativa:
    """A recusa de frase sem número dizia que "um valor numérico" não aparecia
    no trecho (DEV008). O motivo agora nomeia o que falhou; a decisão não muda."""

    CHUNK = _chunk(
        "A redução no trimestre se deve especialmente à sazonalidade em "
        "cartões. O lucro foi de R$ 3.788 milhões.",
        trimestre="1T2026",
        documento="santander_release_1T2026",
    )

    def _aplicar(self, texto: str) -> RespostaGerada:
        citacao = Citacao("SANTANDER", "santander_release_1T2026", "1T2026", 3)
        return aplicar_guardas_pos_llm(
            RespostaGerada(
                resposta=texto, recusa=False, motivo_recusa=None, citacoes=(citacao,)
            ),
            "O que explicou a queda da carteira do Santander no 1T2026?",
            [self.CHUNK],
            Config(),
        )

    def test_afirmacao_sem_numero_tem_motivo_proprio(self):
        final = self._aplicar("A queda se deve à fraude contábil descoberta.")
        assert final.recusa
        assert "afirmação" in final.motivo_recusa
        assert "valor numérico" not in final.motivo_recusa

    def test_numero_sem_lastro_mantem_o_motivo_numerico(self):
        final = self._aplicar("O lucro foi de R$ 9.999 milhões.")
        assert final.recusa
        assert "valor numérico" in final.motivo_recusa


class TestLegendaComNotaDeRodape:
    """`Brasil¹ (em R$ milhões, ao final do período)` dá a escala à tabela (DEV003).

    A legenda era colada inteira ao número para dar unidade à célula, e o
    sobrescrito da nota de rodapé ("¹") faz o parser recusar o texto todo:
    a margem do segmento Brasil, R$ 28.550 milhões, saía sem unidade e não
    fundamentava a resposta. A legenda vigente agora guarda só a unidade.
    """

    TABELA = (
        "Brasil¹ (em R$ milhões, ao final do período)\n"
        "|   | 3T25 | 2T25 | Δ |\n"
        "| --- | --- | --- | --- |\n"
        "|  Margem Financeira Gerencial | 28.550 | 28.327 | 0,8% |\n"
    )

    def _itau(self) -> Chunk:
        return _chunk(
            self.TABELA,
            empresa="ITAU",
            trimestre="3T2025",
            documento="itau_release_3T2025",
            pagina_inicio=26,
            pagina_fim=26,
        )

    def test_valor_da_tabela_ganha_a_escala_da_legenda(self):
        valores = {
            (numero.valor, numero.dimensao)
            for numero, _, _ in fatos_numericos_do_chunk(self._itau(), "3T2025")
        }
        assert (28_550_000_000.0, "monetario") in valores

    def test_resposta_com_o_valor_da_tabela_se_fundamenta(self):
        assert _fundamenta_em(
            self._itau(),
            "A Margem Financeira Gerencial no Brasil no 3T2025 foi de "
            "R$ 28.550 milhões.",
        )

    def test_contraprova_coluna_de_outro_trimestre(self):
        assert not _fundamenta_em(
            self._itau(),
            "A Margem Financeira Gerencial no Brasil no 3T2025 foi de "
            "R$ 28.327 milhões.",
        )

    def test_contraprova_escala_errada(self):
        assert not _fundamenta_em(
            self._itau(),
            "A Margem Financeira Gerencial no Brasil no 3T2025 foi de "
            "R$ 28.550 mil.",
        )
