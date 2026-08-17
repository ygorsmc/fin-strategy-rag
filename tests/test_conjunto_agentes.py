"""Conjunto próprio da camada de agentes (spec 5.9.3) — esquema e composição.

``conjunto_padrao/conjunto_agentes.csv`` é um benchmark **separado** das 45
congeladas. Ele existe porque o subconjunto pareado de n = 15 exigido por 5.9.3
não é extraível das 45: os requisitos de 5.9.2/5.9.3 nasceram depois do
congelamento de 2026-07-29, e a medição feita em 2026-08-10 achou no máximo 8
perguntas aproveitáveis, sem nenhum caso ``so_painel``. Separar é mais honesto
que fingir uma extração que os dados não sustentam — e a regra de contenção de
5.13 ("acrescente coluna, nunca linha") continua valendo para o conjunto
congelado, que este arquivo não toca.

Estes testes vigiam três coisas: o esquema (as cinco colunas da revisão 2 nascem
**dentro** deste arquivo, não em anotação à parte), a composição de 5.9.3
(5 reconciliação + 6 cobertura + 4 projeções) e a fronteira com o benchmark
E0–E3 (RNF11): nenhum ``id`` colide com os congelados e nenhuma linha se declara
``teste`` ou ``dev``.

Deliberadamente sem ``import src`` — o contrato aqui é o do arquivo CSV, como em
``test_conjunto_padrao_revisao2.py``.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
AGENTES = RAIZ / "conjunto_padrao" / "conjunto_agentes.csv"
GABARITO_CONGELADO = RAIZ / "conjunto_padrao" / "perguntas.csv"
MANIFESTO_CORPUS = RAIZ / "corpus" / "metadados.csv"

# Data em que as 15 perguntas foram fixadas. Vale para enunciado, id e
# composição; os valores marcados como pendentes ainda esperam dupla leitura
# humana, e isso está registrado linha a linha em `status_gabarito`.
DATA_CONGELAMENTO = "2026-08-10"

# As 12 colunas congeladas de `perguntas.csv`, na ordem em que vivem lá, mais
# `camada_esperada` na posição canônica da spec (entre `origem` e
# `locais_aceitos`), as outras quatro da revisão 2 e as três próprias deste
# arquivo.
COLUNAS = (
    "id",
    "conjunto",
    "categoria",
    "subtipo_adversarial",
    "pergunta",
    "resposta_esperada",
    "classe_verificacao",
    "unidade",
    "origem",
    "camada_esperada",
    "locais_aceitos",
    "pontos_chave",
    "comportamento_aceito",
    "cobertura_esperada",
    "motivo_recusa_esperado",
    "base_esperada",
    "rota_esperada",
    "subconjunto",
    "status_gabarito",
    "fonte_gabarito",
)

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

COLUNAS_REVISAO2 = (
    "camada_esperada",
    "cobertura_esperada",
    "motivo_recusa_esperado",
    "base_esperada",
    "rota_esperada",
)

# Composição fixada por 5.9.3. O experimento dos três braços é pareado: mudar
# qualquer um destes números muda o que a comparação A/B/C mede.
COMPOSICAO = {"reconciliacao": 5, "cobertura": 6, "projecoes": 4}

VOCABULARIOS = {
    "conjunto": {"agentes"},
    "categoria": {"factual", "comparativa", "qualitativa", "adversarial"},
    "classe_verificacao": {"cvm", "release_gerencial", "n/a"},
    # `painel` é extensão deste arquivo: o número não vem de tabela nem de texto
    # de documento, vem da camada estruturada. Sem esse valor, uma pergunta
    # `so_painel` teria de mentir a própria procedência.
    "origem": {"tabela", "texto", "painel", "n/a"},
    "camada_esperada": {"documento", "cvm", "ambas"},
    # `ambigua` é extensão deste arquivo, exigida pela RN11: quando o termo
    # resolve para mais de uma companhia, nenhum dos três estados da RN12 é
    # verdadeiro — `src/cobertura.py` devolve `cobertura=None` com
    # `precisa_desambiguacao`. Rotular de `ambas` faria um sistema que escolhe
    # sozinho pontuar como acerto.
    "cobertura_esperada": {"ambas", "so_painel", "nenhuma", "ambigua"},
    "motivo_recusa_esperado": {
        "n/a",
        "fora_do_corpus",
        "periodo_ausente",
        "metrica_nao_divulgada",
        "premissa_falsa",
        "conhecimento_pretreino",
    },
    "rota_esperada": {
        "busca_documental",
        "busca_documental_multiempresa",
        "reconciliacao",
        "triagem_cobertura",
        "recusa_documental",
        # Extensões deste arquivo, uma para cada braço de 5.9.2.
        "desambiguacao_entidade",
        "acompanhamento_projecoes",
    },
    "subconjunto": set(COMPOSICAO),
    "status_gabarito": {
        # Valor conferido por consulta ao painel DuckDB, com a consulta
        # registrada em `fonte_gabarito`.
        "verificado_painel",
        # A metade contábil está conferida; a metade que sai do release veio de
        # UMA leitura automática e espera dupla leitura humana.
        "parcial_pendente_release",
        # Nada foi conferido por consulta: o gabarito inteiro sai de release.
        "pendente_conferencia_humana",
    },
}

# `base_esperada` é composta por `|` quando a resposta precisa apresentar mais
# de uma definição na mesma frase — é o caso das reconciliações, e é exatamente
# a regra que a coluna existe para tornar verificável.
BASES = {
    "n/a",
    "gerencial",
    "contabil_consolidado",
    "contabil_controladores",
}

COMPORTAMENTOS = {
    "resposta_completa",
    # `so_painel`: devolve o número e **nomeia o que falta** (modo de falha 12b).
    "resposta_parcial_marcada",
    "recusa",
    # RN11: a desambiguação correta é perguntar, não escolher.
    "pergunta_de_desambiguacao",
    # O Auditor "contesta": apresenta as duas evidências e marca a resposta como
    # não conciliada, em vez de eleger um vencedor (5.9.5).
    "divergencia_registrada",
    # Restrição de honestidade de 5.9.2(B): o verbo é registrar, nunca avaliar.
    "registro_sem_juizo",
}

MARCADOR_PENDENTE = "PENDENTE"


def _ler(caminho: Path) -> list[dict[str, str]]:
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


@pytest.fixture(scope="module")
def agentes() -> list[dict[str, str]]:
    return _ler(AGENTES)


@pytest.fixture(scope="module")
def congelado() -> list[dict[str, str]]:
    return _ler(GABARITO_CONGELADO)


class TestEsquema:
    def test_cabecalho_exato_e_na_ordem(self):
        with open(AGENTES, newline="", encoding="utf-8") as arquivo:
            assert tuple(next(csv.reader(arquivo))) == COLUNAS

    def test_as_cinco_colunas_da_revisao_2_nascem_neste_arquivo(self):
        """Sem arquivo de anotação à parte: aqui não há fingerprint a proteger.

        Em `perguntas.csv` elas vivem separadas porque mesclar mudaria o hash do
        gabarito e invalidaria checkpoint, journal e cache pagos. Este arquivo
        não entra em nenhum fingerprint de avaliação, então a separação não teria
        função — só custo de leitura.
        """
        assert set(COLUNAS_REVISAO2) <= set(COLUNAS)

    def test_as_doze_colunas_congeladas_mantem_a_ordem_relativa(self):
        ordem = [c for c in COLUNAS if c in COLUNAS_CONGELADAS]
        assert tuple(ordem) == COLUNAS_CONGELADAS

    def test_cabecalho_difere_do_gabarito_congelado(self, congelado):
        """Nenhum dos dois arquivos pode ser usado no lugar do outro por engano."""
        assert tuple(congelado[0]) == COLUNAS_CONGELADAS
        assert tuple(congelado[0]) != COLUNAS

    def test_valores_pertencem_ao_vocabulario(self, agentes):
        fora = [
            (linha["id"], coluna, linha[coluna])
            for linha in agentes
            for coluna, permitidos in VOCABULARIOS.items()
            if linha[coluna] not in permitidos
        ]
        assert fora == []

    def test_base_esperada_e_composta_do_vocabulario_de_bases(self, agentes):
        fora = [
            (linha["id"], token)
            for linha in agentes
            for token in linha["base_esperada"].split("|")
            if token not in BASES
        ]
        assert fora == []

    def test_base_composta_nao_repete_nem_mistura_com_na(self, agentes):
        for linha in agentes:
            tokens = linha["base_esperada"].split("|")
            assert len(tokens) == len(set(tokens)), linha["id"]
            assert "n/a" not in tokens or tokens == ["n/a"], linha["id"]

    def test_comportamento_aceito_pertence_ao_vocabulario(self, agentes):
        fora = [
            (linha["id"], token)
            for linha in agentes
            for token in linha["comportamento_aceito"].split("|")
            if token not in COMPORTAMENTOS
        ]
        assert fora == []

    def test_celula_vazia_so_onde_a_ausencia_e_a_decisao(self, agentes):
        """Vazio é decisão declarada, não esquecimento.

        `subtipo_adversarial` só existe para as adversariais; `locais_aceitos`
        fica vazio exatamente onde a resposta **não pode** citar documento —
        recusa e resposta que sai só do painel.
        """
        for linha in agentes:
            for coluna, valor in linha.items():
                if valor.strip():
                    continue
                assert coluna in {"subtipo_adversarial", "locais_aceitos"}, (
                    linha["id"],
                    coluna,
                )
                if coluna == "subtipo_adversarial":
                    assert linha["categoria"] != "adversarial", linha["id"]
                else:
                    assert linha["comportamento_aceito"] in {
                        "recusa",
                        "resposta_parcial_marcada",
                        "pergunta_de_desambiguacao",
                    }, linha["id"]


class TestComposicao:
    def test_sao_quinze_perguntas(self, agentes):
        assert len(agentes) == 15

    def test_composicao_de_5_9_3(self, agentes):
        contagem = {
            chave: sum(linha["subconjunto"] == chave for linha in agentes)
            for chave in COMPOSICAO
        }
        assert contagem == COMPOSICAO

    def test_ids_unicos_e_prefixados_pelo_subconjunto(self, agentes):
        prefixos = {"reconciliacao": "AGTR", "cobertura": "AGTC", "projecoes": "AGTP"}
        ids = [linha["id"] for linha in agentes]
        assert len(set(ids)) == len(ids)
        for linha in agentes:
            assert linha["id"].startswith(prefixos[linha["subconjunto"]]), linha["id"]

    def test_nenhum_id_colide_com_o_conjunto_congelado(self, agentes, congelado):
        """Ids aparecem em checkpoint, journal e respostas cacheadas."""
        colisoes = {linha["id"] for linha in agentes} & {
            linha["id"] for linha in congelado
        }
        assert colisoes == set()

    def test_a_rota_identifica_o_subconjunto(self, agentes):
        rotas = {
            "reconciliacao": {"reconciliacao"},
            "cobertura": {"triagem_cobertura", "desambiguacao_entidade"},
            "projecoes": {"acompanhamento_projecoes"},
        }
        for linha in agentes:
            assert linha["rota_esperada"] in rotas[linha["subconjunto"]], linha["id"]


class TestFronteiraComOBenchmark:
    """RNF11: o benchmark E0–E3 nunca passa pela camada de agentes.

    A regra não proíbe medir a camada de agentes — obriga (5.9). O que ela
    protege é a separação: este conjunto é dela, e as 45 continuam sendo do
    benchmark de recuperação.
    """

    def test_nenhuma_linha_se_declara_teste_ou_dev(self, agentes):
        assert {linha["conjunto"] for linha in agentes} == {"agentes"}

    def test_o_conjunto_congelado_permanece_intocado(self, congelado):
        teste = [linha for linha in congelado if linha["conjunto"] == "teste"]
        dev = [linha for linha in congelado if linha["conjunto"] == "dev"]
        assert (len(teste), len(dev)) == (45, 10)

    def test_nenhuma_pergunta_foi_copiada_do_conjunto_congelado(
        self, agentes, congelado
    ):
        enunciados = {linha["pergunta"].strip().lower() for linha in congelado}
        repetidas = [
            linha["id"]
            for linha in agentes
            if linha["pergunta"].strip().lower() in enunciados
        ]
        assert repetidas == []


class TestParDeContraste:
    """*"e o Nubank?"* × *"e o Inter?"* — o par que 5.13 exige e as 45 não têm."""

    def test_existe_o_lado_so_painel_e_o_lado_nenhuma(self, agentes):
        estados = [linha["cobertura_esperada"] for linha in agentes]
        assert estados.count("so_painel") >= 1
        assert estados.count("nenhuma") >= 1

    def test_as_duas_perguntas_do_par_sao_equivalentes_para_um_leigo(self, agentes):
        por_id = {linha["id"]: linha for linha in agentes}
        inter, nubank = por_id["AGTC001"], por_id["AGTC002"]
        assert inter["cobertura_esperada"] == "so_painel"
        assert nubank["cobertura_esperada"] == "nenhuma"
        # Mesma frase, trocada a entidade: é isso que torna o par informativo.
        assert inter["pergunta"].replace("Inter", "X") == nubank[
            "pergunta"
        ].replace("Nubank", "X")

    def test_o_lado_so_painel_responde_e_o_lado_nenhuma_recusa(self, agentes):
        for linha in agentes:
            if linha["cobertura_esperada"] == "so_painel":
                assert linha["comportamento_aceito"] == "resposta_parcial_marcada"
                assert linha["camada_esperada"] == "cvm", linha["id"]
                assert linha["base_esperada"] != "n/a", linha["id"]
            if linha["cobertura_esperada"] == "nenhuma":
                assert linha["comportamento_aceito"] == "recusa", linha["id"]
                assert linha["base_esperada"] == "n/a", linha["id"]

    def test_recusa_nomeia_o_subtipo_e_nao_apresenta_numero(self, agentes):
        for linha in agentes:
            if linha["categoria"] == "adversarial":
                assert linha["subtipo_adversarial"], linha["id"]
                assert (
                    linha["motivo_recusa_esperado"] == linha["subtipo_adversarial"]
                ), linha["id"]
                assert linha["base_esperada"] == "n/a", linha["id"]

    def test_estado_de_cobertura_e_exercitado_nos_tres_valores_da_rn12(self, agentes):
        cobertura = [
            linha["cobertura_esperada"]
            for linha in agentes
            if linha["subconjunto"] == "cobertura"
        ]
        assert {"ambas", "so_painel", "nenhuma"} <= set(cobertura)


class TestDesambiguacaoRN11:
    def test_o_caso_ambiguo_pergunta_em_vez_de_escolher(self, agentes):
        ambiguas = [
            linha for linha in agentes if linha["cobertura_esperada"] == "ambigua"
        ]
        assert len(ambiguas) == 1
        linha = ambiguas[0]
        assert linha["comportamento_aceito"] == "pergunta_de_desambiguacao"
        assert linha["rota_esperada"] == "desambiguacao_entidade"
        # Nenhum número pode ser apresentado antes de o usuário escolher.
        assert linha["base_esperada"] == "n/a"
        assert linha["classe_verificacao"] == "n/a"

    def test_o_caso_ambiguo_nomeia_as_duas_companhias_por_cd_cvm(self, agentes):
        linha = next(l for l in agentes if l["cobertura_esperada"] == "ambigua")
        for codigo in ("022616", "027774"):
            assert codigo in linha["resposta_esperada"], codigo


class TestGabaritoRastreavel:
    def test_todo_gabarito_de_classe_cvm_registra_a_consulta_ao_painel(self, agentes):
        for linha in agentes:
            if linha["classe_verificacao"] != "cvm":
                continue
            fonte = linha["fonte_gabarito"]
            assert fonte.startswith("painel "), linha["id"]
            assert "SELECT" in fonte and "FROM" in fonte, linha["id"]

    def test_linha_pendente_carrega_a_marca_de_pendencia(self, agentes):
        """Pendência é declarada no texto, não inferida do status."""
        for linha in agentes:
            pendente = linha["status_gabarito"] != "verificado_painel"
            texto = linha["resposta_esperada"] + " " + linha["fonte_gabarito"]
            assert (MARCADOR_PENDENTE in texto.upper()) is pendente, linha["id"]

    def test_gabarito_verificado_nao_depende_de_leitura_de_release(self, agentes):
        for linha in agentes:
            if linha["status_gabarito"] != "verificado_painel":
                continue
            assert linha["origem"] in {"painel", "n/a"}, linha["id"]
            assert linha["locais_aceitos"] == "", linha["id"]

    def test_locais_aceitos_apontam_documento_do_manifesto_e_pagina_fisica(
        self, agentes
    ):
        documentos = {
            linha["documento"] for linha in _ler(MANIFESTO_CORPUS)
        }
        for linha in agentes:
            if not linha["locais_aceitos"]:
                continue
            for local in linha["locais_aceitos"].split(";"):
                documento, _, pagina = local.partition(":")
                assert documento in documentos, (linha["id"], documento)
                assert pagina.isdigit() and int(pagina) >= 1, (linha["id"], local)

    def test_reconciliacao_cruza_as_duas_camadas(self, agentes):
        for linha in agentes:
            if linha["subconjunto"] != "reconciliacao":
                continue
            assert linha["camada_esperada"] == "ambas", linha["id"]
            assert linha["classe_verificacao"] == "cvm", linha["id"]
            # Duas definições na mesma resposta é o que faz a tarefa composta.
            assert "|" in linha["base_esperada"], linha["id"]

    def test_projecoes_nao_emitem_juizo_nem_projetam(self, agentes):
        """5.9.2(B): o módulo registra o publicado e o entregue; não avalia."""
        for linha in agentes:
            if linha["subconjunto"] != "projecoes":
                continue
            assert "gerencial" in linha["base_esperada"], linha["id"]
            assert linha["comportamento_aceito"] in {
                "registro_sem_juizo",
                "resposta_completa",
            }, linha["id"]

    def test_a_diferenca_consolidado_x_controladores_do_bb_esta_coberta(self, agentes):
        """Ausente das 45, e é onde responder "lucro líquido" erra mais (~23%)."""
        alvo = [
            linha
            for linha in agentes
            if "Banco do Brasil" in linha["pergunta"]
            and "contabil_consolidado" in linha["base_esperada"]
            and "contabil_controladores" in linha["base_esperada"]
        ]
        assert alvo, "nenhuma pergunta exercita consolidado x controladores no BB"
        assert any("22,8%" in linha["resposta_esperada"] for linha in alvo)
