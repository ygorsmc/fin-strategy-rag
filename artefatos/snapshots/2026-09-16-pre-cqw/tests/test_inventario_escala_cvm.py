"""Contraprovas do inventário de escala da CVM.

O risco desta peça não é errar um número: é **virar tabela automática de
correção**, que a revisão do Rank 3-B advertiu contra explicitamente. Por isso
os casos aqui verificam sobretudo o que ela se RECUSA a adjudicar.
"""

from __future__ import annotations

import json

import pytest

from scripts import inventariar_escala_cvm as inventario


def _dec(cd_cvm, conjunto, dt_refer, ordem, escala, vl, dt_fim, versao=1):
    return {
        "cd_cvm": cd_cvm, "conjunto": conjunto, "arquivo": f"{conjunto}_x.zip",
        "membro": f"{conjunto}_BPA_con.csv", "dt_refer": dt_refer,
        "versao": versao, "ordem_exerc": ordem, "dt_fim_exerc": dt_fim,
        "escala": escala, "vl_conta": float(vl),
    }


class TestRegraDeAdjudicacao:
    def test_escala_unica_nao_e_conflito(self):
        """Sem conflito não há caso: o inventário não infla o problema."""
        casos = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 100, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "MIL", 100, "2020-12-31"),
        ])
        assert casos == []

    def test_valor_identico_sob_escalas_diferentes_e_adjudicavel_pela_dfp(self):
        """O caso `003549`, em miniatura.

        `19424` não pode ser ao mesmo tempo milhares e reais. Com a DFP anual
        auditada declarando `MIL` de forma única, o rótulo `UNIDADE` do ITR é o
        errado.
        """
        casos = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 19424, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 19424, "2020-12-31"),
            _dec("A", "dfp", "2021-12-31", "PENÚLTIMO", "MIL", 19424, "2020-12-31"),
        ])
        assert len(casos) == 1
        assert casos[0]["veredito"] == "ADJUDICAVEL_PELA_DFP"
        # Contrato E1.6: campo renomeado de `escala_correta`; mesmo valor.
        assert casos[0]["escala_da_referencia_auditada"] == "MIL"
        assert casos[0]["valores_em_conflito"] == [19424.0]

    def test_valor_diferente_nao_e_adjudicavel(self):
        """Escalas diferentes com valores diferentes podem ser redenominação.

        É o caso `003549/2019-12-31`: a declaração `UNIDADE` traz 19.572 e as
        `MIL` trazem 19.491. Sem valor idêntico não há prova de rótulo errado, e
        adjudicar seria inventar a conclusão.
        """
        casos = inventario.adjudicar([
            _dec("A", "dfp", "2019-12-31", "ÚLTIMO", "MIL", 19491, "2019-12-31"),
            _dec("A", "itr", "2020-09-30", "PENÚLTIMO", "UNIDADE", 19572, "2019-12-31"),
        ])
        assert casos[0]["veredito"] == "INDECIDIVEL"
        assert casos[0]["escala_da_referencia_auditada"] is None  # E1.6
        assert casos[0]["valores_em_conflito"] == []

    def test_dfp_ambigua_nao_adjudica(self):
        """Se a própria DFP se contradiz, não há desempate auditado."""
        casos = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 500, "2020-12-31"),
            _dec("A", "dfp", "2021-12-31", "PENÚLTIMO", "UNIDADE", 500, "2020-12-31"),
        ])
        assert casos[0]["veredito"] == "INDECIDIVEL"
        assert casos[0]["escalas_na_dfp"] == ["MIL", "UNIDADE"]

    def test_sem_dfp_nao_adjudica(self):
        """Conflito só entre ITRs não tem instância auditada para decidir."""
        casos = inventario.adjudicar([
            _dec("A", "itr", "2020-06-30", "ÚLTIMO", "MIL", 500, "2020-06-30"),
            _dec("A", "itr", "2021-06-30", "PENÚLTIMO", "UNIDADE", 500, "2020-06-30"),
        ])
        assert casos[0]["veredito"] == "INDECIDIVEL"
        assert casos[0]["escalas_na_dfp"] == []

    def test_maioria_de_votos_NAO_decide(self):
        """Arquivamento repetido não é evidência nova.

        Três ITRs dizendo `UNIDADE` contra uma DFP dizendo `MIL`: a DFP vence,
        porque o critério é a instância auditada, não a contagem.
        """
        casos = inventario.adjudicar([
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 700, "2020-12-31"),
            _dec("A", "itr", "2021-06-30", "PENÚLTIMO", "UNIDADE", 700, "2020-12-31"),
            _dec("A", "itr", "2021-09-30", "PENÚLTIMO", "UNIDADE", 700, "2020-12-31"),
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 700, "2020-12-31"),
        ])
        assert casos[0]["escala_da_referencia_auditada"] == "MIL", (  # E1.6
            "o desempate é a DFP auditada, nunca a maioria de arquivamentos"
        )

    def test_a_saida_e_ordenada_e_deterministica(self):
        """Inventário que muda de ordem entre execuções não é auditável."""
        entrada = [
            _dec("B", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 1, "2020-12-31"),
            _dec("B", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 1, "2020-12-31"),
            _dec("A", "dfp", "2019-12-31", "ÚLTIMO", "MIL", 2, "2019-12-31"),
            _dec("A", "itr", "2020-03-31", "PENÚLTIMO", "UNIDADE", 2, "2019-12-31"),
        ]
        primeiro = inventario.adjudicar(entrada)
        segundo = inventario.adjudicar(list(reversed(entrada)))
        assert [c["cd_cvm"] for c in primeiro] == ["A", "B"]
        assert json.dumps(primeiro, sort_keys=True) == json.dumps(
            segundo, sort_keys=True
        ), "a ordem da entrada não pode mudar o inventário"


class TestNaoEhTabelaDeCorrecao:
    """A advertência da revisão: detector de suspeita não vira correção."""

    def test_o_inventario_nao_declara_valor_corrigido(self):
        casos = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 19424, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 19424, "2020-12-31"),
        ])
        assert "valor_corrigido_reais" not in casos[0], (
            "adjudicar a ESCALA não é decidir o valor corrigido de cada célula"
        )
        assert "escala_da_referencia_auditada" in casos[0]  # E1.6

    def test_toda_declaracao_carrega_a_procedencia(self):
        """Sem arquivo, membro, versão e ordem não há como reconferir."""
        casos = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 19424, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 19424, "2020-12-31"),
        ])
        for d in casos[0]["declaracoes"]:
            for campo in ("arquivo", "membro", "dt_refer", "versao",
                          "ordem_exerc", "escala", "vl_conta"):
                assert campo in d, campo


def _itr(caso, valor):
    """Estado da declaração de ITR com o valor bruto dado."""
    return next(
        d["adjudicacao"] for d in caso["declaracoes"]
        if d["conjunto"] == "itr" and d["vl_conta"] == float(valor)
    )


class TestAdjudicacaoPorDeclaracao:
    """Contrato E1 — `resultados/contratos_correcao_qw1_qw8_2026-09-15.md`.

    A v1 adjudicava o CASO por qualquer coincidência de valor bruto, inclusive
    ZERO, e o consumidor condenava toda declaração de escala divergente mesmo
    com outro valor. Medido na conferência de 15/09: 6.736 dos 10.261 casos só
    tinham zero como prova; 292 declarações eram condenadas por extrapolação.
    """

    def test_zero_sob_duas_escalas_nao_adjudica(self):
        """`0 × 1.000 = 0 × 1`: a coincidência não identifica escala (C.1)."""
        caso = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 0, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 0, "2020-12-31"),
        ])[0]
        assert caso["veredito"] == "INDECIDIVEL"
        assert caso["declaracoes_adjudicadas"] == 0
        assert caso["evidencia_informativa_nao_nula"] is False
        assert "ZERO" in caso["motivo"]
        assert _itr(caso, 0) == "zero_nao_informativo"

    def test_montante_equivalente_em_reais_nao_e_condenado(self):
        """Contraprova C.2: `100000 UNIDADE` é exatamente o montante de `100 MIL`.

        Só a declaração `100 UNIDADE` — o MESMO número bruto da DFP sob outra
        escala — é adjudicada. A v1 condenava as duas.
        """
        caso = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 100, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 100_000, "2020-12-31"),
            _dec("A", "itr", "2021-06-30", "PENÚLTIMO", "UNIDADE", 100, "2020-12-31"),
        ])[0]
        assert caso["veredito"] == "ADJUDICAVEL_PELA_DFP"
        assert _itr(caso, 100_000) == "equivalente_em_reais_a_dfp"
        assert _itr(caso, 100) == inventario.ADJUDICA
        assert caso["declaracoes_adjudicadas"] == 1

    def test_dfp_com_outro_valor_nao_prova(self):
        caso = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 100, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 250, "2020-12-31"),
        ])[0]
        assert caso["veredito"] == "INDECIDIVEL"
        assert _itr(caso, 250) == "sem_prova"

    def test_reapresentacao_na_dfp_nao_fabrica_nem_impede_prova(self):
        """DFP v1 `100 MIL`, v2 `110 MIL`: identidade com uma versão auditada
        adjudica; valor que não bate com nenhuma não prova nada."""
        caso = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 100, "2020-12-31", versao=1),
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 110, "2020-12-31", versao=2),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 100, "2020-12-31"),
            _dec("A", "itr", "2021-06-30", "PENÚLTIMO", "UNIDADE", 105, "2020-12-31"),
        ])[0]
        assert _itr(caso, 100) == inventario.ADJUDICA
        assert _itr(caso, 105) == "sem_prova"
        assert caso["declaracoes_adjudicadas"] == 1

    def test_coincidencia_so_entre_itrs_nao_adjudica(self):
        """Prova que ALGUM rótulo erra, não QUAL — os 124 casos da conferência."""
        caso = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 100, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 300, "2020-12-31"),
            _dec("A", "itr", "2021-06-30", "PENÚLTIMO", "MIL", 300, "2020-12-31"),
        ])[0]
        assert caso["veredito"] == "INDECIDIVEL"
        assert caso["evidencia_informativa_nao_nula"] is True
        assert caso["declaracoes_adjudicadas"] == 0

    def test_evidencia_contraditoria_nao_adjudica(self):
        """A própria DFP traz `100` e `100000` em MIL: `100000 UNIDADE` é idêntico
        a um e equivale em reais ao outro. Não há como decidir."""
        caso = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 100, "2020-12-31", versao=1),
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 100_000, "2020-12-31", versao=2),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 100_000, "2020-12-31"),
        ])[0]
        assert _itr(caso, 100_000) == "evidencia_contraditoria"
        assert caso["veredito"] == "INDECIDIVEL"

    def test_escala_desconhecida_falha_em_vez_de_comparar(self):
        with pytest.raises(ValueError, match="ESCALA_MOEDA desconhecida"):
            inventario.adjudicar([
                _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 5, "2020-12-31"),
                _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "BILHAO", 5, "2020-12-31"),
            ])

    def test_o_campo_de_grupo_antigo_nao_existe_mais(self):
        """E1.6: consumidor que lia `escala_correta` tem de falhar alto, não
        continuar condenando por extrapolação."""
        caso = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 19424, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 19424, "2020-12-31"),
        ])[0]
        assert "escala_correta" not in caso

    def test_todo_estado_pertence_ao_vocabulario_fechado(self):
        casos = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 100, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 100_000, "2020-12-31"),
            _dec("A", "itr", "2021-06-30", "PENÚLTIMO", "UNIDADE", 0, "2020-12-31"),
            _dec("A", "itr", "2021-09-30", "PENÚLTIMO", "MIL", 7, "2020-12-31"),
            _dec("B", "itr", "2020-06-30", "ÚLTIMO", "MIL", 5, "2020-06-30"),
            _dec("B", "itr", "2021-06-30", "PENÚLTIMO", "UNIDADE", 5, "2020-06-30"),
        ])
        for caso in casos:
            for d in caso["declaracoes"]:
                assert d["adjudicacao"] in inventario.ESTADOS_DE_DECLARACAO

    def test_o_resumo_publica_a_chave_que_o_codigo_usa(self):
        """Fecha o §9.1 do dossiê: o resumo dizia `(cd_cvm, cd_conta,
        dt_fim_exerc)` enquanto o código agrupava por cinco campos."""
        casos = inventario.adjudicar([
            _dec("A", "dfp", "2020-12-31", "ÚLTIMO", "MIL", 19424, "2020-12-31"),
            _dec("A", "itr", "2021-03-31", "PENÚLTIMO", "UNIDADE", 19424, "2020-12-31"),
        ])
        resumo = inventario.resumir(casos)
        for campo in ("demonstrativo", "dt_ini_exerc", "dt_fim_exerc"):
            assert campo in resumo["regra_de_adjudicacao"]
        assert resumo["versao_do_esquema"] == inventario.VERSAO_DO_ESQUEMA == 2
        assert resumo["documentos_com_declaracao_adjudicada"] == 1
        assert resumo["declaracoes_por_estado"][inventario.ADJUDICA] == 1
