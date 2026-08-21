"""Contrato da tabela de fatos numéricos e da estratégia E4.

O canal existe porque o E3 recupera a página certa e o trecho errado dentro
dela: o texto corrido arredonda ("R$ 3,4 bilhões") e a tabela com o valor
exato fica fora do top-k. Os testes aqui travam as três propriedades que
sustentam isso — parser único, filtro de metadados antes da pontuação, e
ordenação determinística — mais a recusa de ranquear quando não há métrica.
"""

from __future__ import annotations

import pytest

from src.config import Config
from src.fatos import construir_indice_fatos
from src.ingestao import Chunk
from src.recuperacao import Estrategia, Recuperador


def _chunk(
    identificador: str,
    texto: str,
    empresa: str = "ITAU",
    trimestre: str = "1T2026",
    pagina: int = 7,
) -> Chunk:
    documento = f"{empresa.lower()}_release_{trimestre}"
    return Chunk(
        id=identificador,
        empresa=empresa,
        trimestre=trimestre,
        documento=documento,
        pagina_inicio=pagina,
        pagina_fim=pagina,
        posicao_no_documento=1,
        texto=(
            f"[{empresa} | {documento} | {trimestre} | pág. {pagina}]\n{texto}"
        ),
        tipo_bloco="tabela",
    )


TABELA_LUCRO = (
    "Em R$ milhões\n"
    "| Indicador | Valor |\n"
    "| --- | --- |\n"
    "| Lucro líquido recorrente | 11.508 |\n"
    "| Lucro líquido contábil | 11.301 |\n"
)
TEXTO_ARREDONDADO = (
    "O lucro líquido recorrente do período somou R$ 11,5 bilhões."
)


class TestConstrucaoDaTabelaDeFatos:
    def test_fato_de_tabela_herda_a_metrica_do_rotulo_da_linha(self):
        indice = construir_indice_fatos([_chunk("c1", TABELA_LUCRO)])
        pontuados = indice.pontuar_chunks("Qual foi o lucro líquido?")
        assert [identificador for identificador, _ in pontuados] == ["c1"]
        assert pontuados[0][1] == 2  # as duas linhas de lucro da tabela

    def test_fato_sem_grupo_metrico_nao_entra_na_tabela(self):
        # "Quantidade de agências" não é métrica do vocabulário fechado: o
        # número existe, mas não discrimina chunk nenhum numa consulta.
        indice = construir_indice_fatos(
            [_chunk("c1", "| Quantidade de agências | 3.421 |\n")]
        )
        assert indice.total_de_fatos == 0

    def test_parser_e_o_mesmo_da_guarda_da_rn02(self):
        # Se este teste quebrar, a tabela passou a ler o corpus com um
        # interpretador próprio e vai propor página que o grounding recusa.
        from src.geracao import fatos_numericos_do_chunk

        chunk = _chunk("c1", TABELA_LUCRO)
        indice = construir_indice_fatos([chunk])
        valores_guarda = {
            numero.valor
            for numero, tokens, _ in fatos_numericos_do_chunk(chunk)
            if tokens & {"metrica_lucro"}
        }
        # A legenda "Em R$ milhões" do chunk escala os dois valores — é
        # exatamente o que a guarda faz e o que a tabela precisa herdar.
        assert valores_guarda == {11_508e6, 11_301e6}
        assert indice.pontuar_chunks("lucro líquido")[0][1] == len(
            valores_guarda
        )


class TestPontuacaoRespeitaOFiltroDeMetadados:
    def test_empresa_e_trimestre_restringem_antes_de_pontuar(self):
        indice = construir_indice_fatos(
            [
                _chunk("itau", TABELA_LUCRO, empresa="ITAU"),
                _chunk("bb", TABELA_LUCRO, empresa="BB"),
            ]
        )
        pontuados = indice.pontuar_chunks("lucro líquido", empresas=("BB",))
        assert [identificador for identificador, _ in pontuados] == ["bb"]

    def test_trimestre_fora_do_escopo_nao_pontua(self):
        indice = construir_indice_fatos(
            [
                _chunk("a", TABELA_LUCRO, trimestre="1T2026"),
                _chunk("b", TABELA_LUCRO, trimestre="4T2025"),
            ]
        )
        pontuados = indice.pontuar_chunks(
            "lucro líquido", trimestres=("4T2025",)
        )
        assert [identificador for identificador, _ in pontuados] == ["b"]


class TestPontuacaoRecusaRanquearSemMetrica:
    @pytest.mark.parametrize(
        "pergunta",
        [
            "Qual banco tem a melhor governança corporativa?",
            "Comente a estratégia da instituição.",
        ],
    )
    def test_pergunta_sem_metrica_devolve_lista_vazia(self, pergunta):
        # Ranquear por densidade numérica bruta devolveria o chunk com mais
        # números — ruído com aparência de resultado.
        indice = construir_indice_fatos([_chunk("c1", TABELA_LUCRO)])
        assert indice.pontuar_chunks(pergunta) == []

    def test_metrica_percentual_nao_casa_com_evidencia_monetaria(self):
        indice = construir_indice_fatos(
            [_chunk("c1", "| Índice de eficiência | 4.512 |\n")]
        )
        assert indice.pontuar_chunks("Qual foi o índice de eficiência?") == []


class TestOrdenacaoDeterministica:
    def test_empate_e_desfeito_pelo_id_do_chunk(self):
        indice = construir_indice_fatos(
            [
                _chunk("zzz", TABELA_LUCRO),
                _chunk("aaa", TABELA_LUCRO),
                _chunk("mmm", TABELA_LUCRO),
            ]
        )
        pontuados = indice.pontuar_chunks("lucro líquido")
        assert [identificador for identificador, _ in pontuados] == [
            "aaa",
            "mmm",
            "zzz",
        ]

    def test_chunk_com_mais_fatos_da_metrica_vem_antes(self):
        indice = construir_indice_fatos(
            [
                _chunk("tabela", TABELA_LUCRO),
                _chunk("prosa", TEXTO_ARREDONDADO),
            ]
        )
        assert [i for i, _ in indice.pontuar_chunks("lucro líquido")] == [
            "tabela",
            "prosa",
        ]


class _BM25Falso:
    """Duplo do índice BM25: pontua zero, para provar que E4 não o usa."""

    def get_scores(self, _tokens):
        return [0.0]


class TestEstrategiaE4NoRecuperador:
    def _recuperador(self, chunks: list[Chunk]) -> Recuperador:
        return Recuperador(
            config=Config(),
            indice_bm25=(_BM25Falso(), chunks),
            hash_corpus_esperado="irrelevante-neste-teste",
        )

    def test_e4_devolve_resultados_com_origem_fatos(self):
        chunks = [_chunk("tabela", TABELA_LUCRO)]
        resultados = self._recuperador(chunks).recuperar(
            "Qual foi o lucro líquido do Itaú no 1T2026?", Estrategia.FATOS
        )
        assert [r.chunk.id for r in resultados] == ["tabela"]
        assert all(r.origem is Estrategia.FATOS for r in resultados)

    def test_e4_prefere_a_tabela_a_prosa_arredondada(self):
        # A falha que motivou o canal: a prosa cita a página certa com o valor
        # arredondado e empurra a tabela com o valor exato para fora do top-k.
        chunks = [
            _chunk("prosa", TEXTO_ARREDONDADO, pagina=10),
            _chunk("tabela", TABELA_LUCRO, pagina=13),
        ]
        resultados = self._recuperador(chunks).recuperar(
            "Qual foi o lucro líquido recorrente do Itaú no 1T2026?",
            Estrategia.FATOS,
            top_k=1,
        )
        assert [r.chunk.id for r in resultados] == ["tabela"]

    def test_e4_nao_se_funde_com_bm25(self):
        # Medido em 2026-08-20: sob o mesmo orçamento de top-5 a fusão cai de
        # 11/15 para 8–9/15 porque divide as vagas entre duas listas. Se
        # alguém fundir E4 com E1, o BM25 falso (score zero) apareceria aqui.
        chunks = [_chunk("tabela", TABELA_LUCRO)]
        resultados = self._recuperador(chunks).recuperar(
            "Qual foi o lucro líquido?", Estrategia.FATOS
        )
        assert all(r.score > 0.0 for r in resultados)

    def test_e4_decompoe_pergunta_comparativa_por_banco(self):
        chunks = [
            _chunk("itau_a", TABELA_LUCRO, empresa="ITAU"),
            _chunk("itau_b", TABELA_LUCRO, empresa="ITAU"),
            _chunk("bb_a", TABELA_LUCRO, empresa="BB"),
        ]
        resultados = self._recuperador(chunks).recuperar(
            "Qual foi o lucro líquido do Itaú Unibanco e do Banco do Brasil "
            "no 1T2026?",
            Estrategia.FATOS,
            top_k=2,
        )
        assert {r.chunk.empresa for r in resultados} == {"ITAU", "BB"}

    def test_e4_sem_metrica_na_pergunta_devolve_vazio(self):
        chunks = [_chunk("tabela", TABELA_LUCRO)]
        resultados = self._recuperador(chunks).recuperar(
            "Recomende uma ação para eu comprar.", Estrategia.FATOS
        )
        assert resultados == []

    def test_closed_book_continua_sem_recuperar_nada(self):
        chunks = [_chunk("tabela", TABELA_LUCRO)]
        assert (
            self._recuperador(chunks).recuperar(
                "Qual foi o lucro líquido?", Estrategia.CLOSED_BOOK
            )
            == []
        )
