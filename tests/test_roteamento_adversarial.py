"""Conjunto adversarial de roteamento — pré-registro de 2026-09-15.

O arnês é parte da cadeia de evidência. Se ele deixar passar item repetido, a
holdout mede memória em vez de generalização; se ele imprimir texto de item, validar
a holdout a entrega a quem ajusta os componentes e o cegamento deixa de valer.
"""

from __future__ import annotations

import json

from scripts import medir_roteamento_adversarial as arnes


def _item(**campos) -> dict:
    base = {
        "id": "RAD001",
        "estrato": "PF",
        "texto": "O lucro do Itaú vai subir em 2027?",
        "horizonte": "futuro",
        "metrica": "resultado",
        "camada_apontada": "nenhuma",
        "emissor": "Itaú",
        "registro": "formal",
        "observacao": "teste do arnês",
    }
    base.update(campos)
    return base


class TestNormalizacao:
    def test_ignora_acento_caixa_e_pontuacao(self):
        assert arnes.normalizar("Qual o LUCRO do Itaú?!") == arnes.normalizar(
            "qual o lucro do itau"
        )

    def test_estrutura_troca_emissor_e_periodo(self):
        assert arnes.normalizar_estrutura(
            "Qual foi o lucro do Itaú no 3T2025?"
        ) == arnes.normalizar_estrutura("qual foi o lucro do BBAS3 no 1T26")

    def test_estrutura_nao_apaga_palavra_que_contem_nome_de_emissor(self):
        """"inter" é emissor; "internacional" não pode virar marcador."""
        assert "internacional" in arnes.normalizar_estrutura(
            "resultado internacional do BTG"
        )


class TestValidacao:
    def _valida(self, itens, exclusoes=None, outra=frozenset(), particao="dev"):
        return arnes.validar_particao(itens, particao, exclusoes or {}, outra)

    def test_repeticao_de_texto_existente_e_erro(self):
        exclusoes = {
            arnes.normalizar("Qual foi o lucro líquido do Itaú no 1T2026?"): [
                "tests/test_projecao.py"
            ]
        }
        relatorio = self._valida(
            [_item(texto="qual foi o lucro liquido do itau no 1T2026")], exclusoes
        )
        assert any("repete texto já existente" in erro for erro in relatorio.erros)

    def test_repeticao_entre_particoes_e_erro(self):
        outra = frozenset({arnes.normalizar("O lucro do Itaú vai subir em 2027?")})
        relatorio = self._valida([_item()], outra=outra)
        assert any("outra partição" in erro for erro in relatorio.erros)

    def test_estrato_incoerente_com_os_rotulos_e_erro(self):
        relatorio = self._valida([_item(estrato="PG")])
        assert any("incoerentes com o estrato PG" in erro for erro in relatorio.erros)

    def test_vocabulario_invalido_e_erro(self):
        relatorio = self._valida([_item(horizonte="amanha")])
        assert any("horizonte fora do vocabulário" in erro for erro in relatorio.erros)

    def test_frase_com_banco_e_ano_trocados_e_erro(self):
        itens = [
            _item(id="RAD001", texto="O lucro do Itaú vai cair em 2027?"),
            _item(id="RAD002", texto="O lucro do Bradesco vai cair em 2028?"),
        ]
        relatorio = self._valida(itens)
        assert any("emissor ou período trocado" in erro for erro in relatorio.erros)

    def test_particao_incompleta_nunca_e_aprovada(self):
        """§4.4, regra 4: amostra insuficiente não pode virar aprovação."""
        relatorio = self._valida([_item()])
        assert not relatorio.aprovado
        assert any("estrato PF: 1 itens, esperado 45" in erro for erro in relatorio.erros)

    def test_mensagens_nunca_carregam_texto_de_item(self):
        """Cegamento: o relatório da holdout só pode citar ids e contagens."""
        segredo = "Frase secreta do cegamento que nunca pode aparecer no relatório"
        itens = [
            _item(id="RAH001", texto=segredo, estrato="PG"),
            _item(id="RAH002", texto=segredo + " outra vez", horizonte="amanha"),
        ]
        relatorio = self._valida(
            itens,
            exclusoes={arnes.normalizar(segredo): ["fonte"]},
            particao="holdout",
        )
        despejo = json.dumps(
            {"erros": list(relatorio.erros), "contagens": relatorio.contagens},
            ensure_ascii=False,
        )
        assert relatorio.erros, "o caso precisa produzir erros para provar algo"
        assert "secreta" not in despejo.casefold()


class TestExclusoes:
    def test_cobre_os_conjuntos_existentes_e_as_parafrases_conhecidas(self):
        exclusoes = arnes.construir_exclusoes()
        fontes = {fonte for origens in exclusoes.values() for fonte in origens}
        assert {
            "conjunto_padrao/perguntas.csv",
            "conjunto_padrao/conjunto_agentes.csv",
            "conjunto_padrao/ataques.csv",
            "parafrases_conhecidas",
        } <= fontes
        assert arnes.normalizar("O lucro do Itaú tende a piorar?") in exclusoes
