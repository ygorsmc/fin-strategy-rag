"""Contraprovas do inventário de escala da CVM.

O risco desta peça não é errar um número: é **virar tabela automática de
correção**, que a revisão do Rank 3-B advertiu contra explicitamente. Por isso
os casos aqui verificam sobretudo o que ela se RECUSA a adjudicar.
"""

from __future__ import annotations

import json

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
        assert casos[0]["escala_correta"] == "MIL"
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
        assert casos[0]["escala_correta"] is None
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
        assert casos[0]["escala_correta"] == "MIL", (
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
        assert "escala_correta" in casos[0]

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
