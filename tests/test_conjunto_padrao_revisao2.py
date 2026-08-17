"""Colunas da revisão 2/3 do gabarito (spec 5.13) — esquema e coerência.

As colunas vivem hoje em ``conjunto_padrao/anotacoes_revisao2.csv``, ligadas por
``id`` às linhas congeladas de ``perguntas.csv`` (decisão registrada no
``conjunto_padrao/README.md``). Estes testes valem para os dois estados: com o
arquivo separado e depois de uma eventual fusão das colunas no gabarito.

Deliberadamente sem ``import src`` — o contrato aqui é o dos arquivos CSV, e o
teste não deve quebrar por causa de refatoração de módulo.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
GABARITO = RAIZ / "conjunto_padrao" / "perguntas.csv"
ANOTACOES = RAIZ / "conjunto_padrao" / "anotacoes_revisao2.csv"

COLUNAS_CONGELADAS = (
    "id",
    "conjunto",
    "categoria",
    "subtipo_adversarial",
    "pergunta",
    "resposta_esperada",
    "classe_verificacao",
    "unidade",
    "origem",
    "locais_aceitos",
    "pontos_chave",
    "comportamento_aceito",
)

COLUNAS_ANOTACAO = (
    "id",
    "camada_esperada",
    "cobertura_esperada",
    "motivo_recusa_esperado",
    "base_esperada",
    "rota_esperada",
)

VOCABULARIOS = {
    # ``pendente_conferencia`` é sentinela explícita, não um valor de negócio:
    # marca a única linha cujo valor depende de decisão humana em aberto.
    "camada_esperada": {"documento", "cvm", "ambas", "pendente_conferencia"},
    "cobertura_esperada": {"ambas", "so_painel", "nenhuma"},
    "motivo_recusa_esperado": {
        "n/a",
        "fora_do_corpus",
        "periodo_ausente",
        "metrica_nao_divulgada",
        "premissa_falsa",
        "conhecimento_pretreino",
    },
    "base_esperada": {
        "n/a",
        "gerencial",
        "contabil_consolidado",
        "contabil_controladores",
    },
    "rota_esperada": {
        "busca_documental",
        "busca_documental_multiempresa",
        "reconciliacao",
        "triagem_cobertura",
        "recusa_documental",
    },
}

# Único valor pendente de conferência humana: a janela temporal do painel CVM
# ainda não foi decidida (a fonte tem histórico desde 2011). Se o painel ingerir
# mais do que a janela do corpus, o 1T2020 do Santander deixa de estar ausente
# na camada estruturada e a recusa congelada de TSTA006 fica errada pela metade.
PENDENTES = {"TSTA006": "camada_esperada"}


def _ler(caminho: Path) -> list[dict[str, str]]:
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


@pytest.fixture(scope="module")
def gabarito() -> list[dict[str, str]]:
    return _ler(GABARITO)


@pytest.fixture(scope="module")
def anotacoes() -> list[dict[str, str]]:
    return _ler(ANOTACOES)


class TestCongelamentoPreservado:
    """A anotação acrescenta coluna; nunca linha, nunca reordenação."""

    def test_gabarito_mantem_as_colunas_congeladas_na_ordem(self, gabarito):
        presentes = tuple(gabarito[0])
        assert set(COLUNAS_CONGELADAS) <= set(presentes)
        ordem = [c for c in presentes if c in COLUNAS_CONGELADAS]
        assert tuple(ordem) == COLUNAS_CONGELADAS

    def test_conjunto_teste_continua_15_10_10_10(self, gabarito):
        teste = [linha for linha in gabarito if linha["conjunto"] == "teste"]
        contagens = {
            categoria: sum(linha["categoria"] == categoria for linha in teste)
            for categoria in ("factual", "comparativa", "qualitativa", "adversarial")
        }
        assert len(teste) == 45
        assert contagens == {
            "factual": 15,
            "comparativa": 10,
            "qualitativa": 10,
            "adversarial": 10,
        }

    def test_quatro_adversariais_de_teste_sao_sobre_o_banco_fora_do_corpus(
        self, gabarito
    ):
        nubank = [
            linha
            for linha in gabarito
            if linha["conjunto"] == "teste"
            and linha["categoria"] == "adversarial"
            and "NUBANK" in linha["pergunta"].upper()
        ]
        assert len(nubank) >= 4


class TestLigacaoComOGabarito:
    def test_cabecalho_da_anotacao_e_o_esperado(self):
        with open(ANOTACOES, newline="", encoding="utf-8") as arquivo:
            assert tuple(next(csv.reader(arquivo))) == COLUNAS_ANOTACAO

    def test_anotacao_cobre_exatamente_as_linhas_congeladas_na_mesma_ordem(
        self, gabarito, anotacoes
    ):
        assert [linha["id"] for linha in anotacoes] == [
            linha["id"] for linha in gabarito
        ]

    def test_nenhuma_celula_fica_vazia(self, anotacoes):
        vazias = [
            (linha["id"], coluna)
            for linha in anotacoes
            for coluna, valor in linha.items()
            if not valor.strip()
        ]
        assert vazias == []

    def test_valores_pertencem_ao_vocabulario(self, anotacoes):
        fora = [
            (linha["id"], coluna, linha[coluna])
            for linha in anotacoes
            for coluna, permitidos in VOCABULARIOS.items()
            if linha[coluna] not in permitidos
        ]
        assert fora == []

    def test_pendencia_de_conferencia_e_declarada_e_nao_se_espalha(self, anotacoes):
        marcadas = {
            (linha["id"], coluna)
            for linha in anotacoes
            for coluna in VOCABULARIOS
            if linha[coluna] == "pendente_conferencia"
        }
        assert marcadas == {(chave, valor) for chave, valor in PENDENTES.items()}

    def test_fusao_futura_nao_pode_divergir_da_anotacao(self, gabarito, anotacoes):
        """Se as colunas forem mescladas no gabarito, os dois arquivos batem.

        Enquanto a fusão não acontece, ``mescladas`` é vazio e o teste vigia sem
        custo — não é um skip esperando implementação.
        """
        mescladas = [c for c in COLUNAS_ANOTACAO if c != "id" and c in gabarito[0]]
        por_id = {linha["id"]: linha for linha in anotacoes}
        divergentes = [
            (linha["id"], coluna)
            for linha in gabarito
            for coluna in mescladas
            if linha[coluna] != por_id[linha["id"]][coluna]
        ]
        assert divergentes == []


class TestCoerenciaSemantica:
    """`cobertura_esperada` é sobre a entidade; `camada_esperada`, sobre a fonte."""

    def test_cobertura_nenhuma_so_para_entidade_fora_das_duas_camadas(
        self, gabarito, anotacoes
    ):
        por_id = {linha["id"]: linha for linha in gabarito}
        for linha in anotacoes:
            pergunta = por_id[linha["id"]]["pergunta"].upper()
            esperado = "nenhuma" if "NUBANK" in pergunta else "ambas"
            assert linha["cobertura_esperada"] == esperado, linha["id"]

    def test_entidade_do_corpus_permanece_coberta_mesmo_quando_a_resposta_nao_existe(
        self, gabarito, anotacoes
    ):
        """Recusar por 'fato ausente' não é recusar por 'banco desconhecido'."""
        por_id = {linha["id"]: linha for linha in anotacoes}
        for linha in gabarito:
            if linha["categoria"] != "adversarial":
                continue
            if linha["subtipo_adversarial"] == "fora_do_corpus":
                continue
            assert por_id[linha["id"]]["cobertura_esperada"] == "ambas", linha["id"]

    def test_motivo_de_recusa_nomeia_o_subtipo_adversarial(self, gabarito, anotacoes):
        por_id = {linha["id"]: linha for linha in anotacoes}
        for linha in gabarito:
            motivo = por_id[linha["id"]]["motivo_recusa_esperado"]
            if linha["categoria"] == "adversarial":
                assert motivo == linha["subtipo_adversarial"], linha["id"]
            else:
                assert motivo == "n/a", linha["id"]

    def test_base_contabil_so_aparece_onde_a_verificacao_e_cvm(
        self, gabarito, anotacoes
    ):
        por_id = {linha["id"]: linha for linha in anotacoes}
        for linha in gabarito:
            base = por_id[linha["id"]]["base_esperada"]
            if linha["classe_verificacao"] == "cvm":
                assert base.startswith("contabil_"), linha["id"]
            else:
                assert not base.startswith("contabil_"), linha["id"]

    def test_metrica_gerencial_declara_base_gerencial(self, gabarito, anotacoes):
        por_id = {linha["id"]: linha for linha in anotacoes}
        for linha in gabarito:
            if linha["classe_verificacao"] == "release_gerencial":
                assert por_id[linha["id"]]["base_esperada"] == "gerencial", linha["id"]

    def test_recusa_pura_nao_pode_apresentar_numero(self, gabarito, anotacoes):
        """Sem resposta esperada, não há base numérica a declarar."""
        por_id = {linha["id"]: linha for linha in anotacoes}
        for linha in gabarito:
            if (
                linha["categoria"] == "adversarial"
                and linha["comportamento_aceito"] == "recusa"
            ):
                assert por_id[linha["id"]]["base_esperada"] == "n/a", linha["id"]

    def test_rota_de_reconciliacao_exige_as_duas_camadas(self, gabarito, anotacoes):
        por_id = {linha["id"]: linha for linha in gabarito}
        for linha in anotacoes:
            if linha["rota_esperada"] == "reconciliacao":
                assert linha["camada_esperada"] == "ambas", linha["id"]
                assert por_id[linha["id"]]["classe_verificacao"] == "cvm", linha["id"]

    def test_comparativa_roteia_pela_subconsulta_por_banco(self, gabarito, anotacoes):
        """Modo de falha nº 6: comparativa sem fan-out recupera um banco só."""
        por_id = {linha["id"]: linha for linha in anotacoes}
        for linha in gabarito:
            if linha["categoria"] == "comparativa":
                assert (
                    por_id[linha["id"]]["rota_esperada"]
                    == "busca_documental_multiempresa"
                ), linha["id"]

    def test_triagem_de_cobertura_responde_por_entidade_e_periodo(
        self, gabarito, anotacoes
    ):
        por_id = {linha["id"]: linha for linha in gabarito}
        for linha in anotacoes:
            if linha["rota_esperada"] != "triagem_cobertura":
                continue
            origem = por_id[linha["id"]]
            assert origem["categoria"] == "adversarial", linha["id"]
            assert origem["subtipo_adversarial"] in {
                "fora_do_corpus",
                "periodo_ausente",
            }, linha["id"]


class TestLacunasConhecidas:
    """Documenta, em código, o que as 45 congeladas ainda não cobrem.

    Estes testes passam descrevendo a lacuna. Quando o Ygor decidir descongelar
    e cobrir o subconjunto, eles falham e obrigam a atualizar o registro — é o
    oposto de deixar a lacuna sumir num comentário.
    """

    def test_par_de_contraste_de_cobertura_ainda_nao_existe(self, anotacoes):
        so_painel = [
            linha["id"] for linha in anotacoes if linha["cobertura_esperada"] == "so_painel"
        ]
        assert so_painel == [], (
            "Surgiu linha `so_painel`: o par de contraste Nubank × Inter passou a "
            "existir. Atualizar conjunto_padrao/README.md e este registro."
        )

    def test_subconjunto_de_reconciliacao_esta_abaixo_do_minimo_da_spec(
        self, gabarito, anotacoes
    ):
        por_id = {linha["id"]: linha for linha in gabarito}
        reconciliacao = [
            linha["id"] for linha in anotacoes if linha["rota_esperada"] == "reconciliacao"
        ]
        comparativas = [
            pid for pid in reconciliacao if por_id[pid]["categoria"] == "comparativa"
        ]
        assert len(reconciliacao) == 2 and comparativas == [], (
            "A spec 5.13 exige >=5 perguntas de reconciliação dentro das "
            "comparativas; hoje há 2, ambas factuais. Se isso mudou, atualizar "
            "conjunto_padrao/README.md."
        )
