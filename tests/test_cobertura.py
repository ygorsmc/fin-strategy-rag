"""Contrato da resolução de entidade e da triagem de cobertura (RN11 · RN12).

Nenhum teste aqui toca rede, LLM ou o `artefatos/cvm.duckdb` real. As fixtures
são sintéticas, mas **fiéis ao painel medido em 2026-08-10** — razões sociais,
`CD_CVM` e distribuição de tokens copiados do dado real, porque um índice
mínimo resolveria bonito e mediria outra coisa:

* `INTER & CO, INC.` é `080217` e é a **única** companhia cujo nome tem `inter`
  como token; `ALARES INTERNET`, `LOG-IN LOGÍSTICA INTERMODAL`, `INTERCEMENT
  BRASIL`, `INTERNATIONAL MEAL COMPANY` e `LM TRANSPORTES INTERESTADUAIS`
  contêm a substring e **não** podem casar;
* `BTG` resolve para **duas** companhias — `022616` (BCO BTG PACTUAL) e
  `027774` (BTG PACTUAL COMMODITIES SERTRADING);
* `brasil` aparece em muitas razões sociais (27 das 470 no painel real) e por
  isso não identifica ninguém;
* o painel cobre `1T2025`–`2T2026` e o corpus documental cobre `2T2025`–
  `1T2026`: as duas janelas **não** coincidem, e é isso que faz `1T2025` ser um
  caso `so_painel` por trimestre;
* o Nubank não está em nenhuma das duas camadas.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import duckdb
import pytest

from src.config import Config
from src.cobertura import (
    ESTADOS_RN12,
    MOTIVO_FORA_DO_CORPUS,
    MOTIVO_NA,
    MOTIVO_PERIODO_AUSENTE,
    Cobertura,
    Companhia,
    EstadoCobertura,
    FatoEstruturado,
    IndiceCobertura,
    carregar_indice_cobertura,
    companhias_do_corpus,
    companhias_so_no_painel,
    descrever_cobertura,
    extrair_conceito,
    extrair_mencoes,
    formatar_reais,
    resolver_entidade,
    responder_por_gabarito,
    tokenizar_nome,
    triagem_cobertura,
    triar_entidade,
)
from src.dados_estruturados import criar_esquema
from src.mapa_contas import (
    CONCEITO_ATIVO_TOTAL,
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_PATRIMONIO_LIQUIDO,
)

# --------------------------------------------------------------------------- #
# Fixtures fiéis ao painel real
# --------------------------------------------------------------------------- #

CD_BB = "001023"
CD_BRADESCO = "000906"
CD_ITAU = "019348"
CD_SANTANDER = "020532"
CD_BTG = "022616"
CD_SERTRADING = "027774"
CD_INTER = "080217"
CD_ALARES = "025194"
CD_BMG = "024600"
CD_DAYCOVAL = "020796"
CD_MERCANTIL = "001325"

CD_CVM_CORPUS_FIXTURE = (CD_BB, CD_BRADESCO, CD_ITAU, CD_SANTANDER, CD_BTG)

# Razões sociais exatamente como o painel real as traz.
COMPANHIAS_FIXTURE: tuple[Companhia, ...] = (
    Companhia(CD_BRADESCO, "BCO BRADESCO S.A.", True),
    Companhia(CD_BB, "BCO BRASIL S.A.", True),
    Companhia(CD_MERCANTIL, "BCO MERCANTIL DO BRASIL S.A.", True),
    Companhia(CD_ITAU, "ITAU UNIBANCO HOLDING S.A.", True),
    Companhia(CD_SANTANDER, "BCO SANTANDER (BRASIL) S.A.", True),
    Companhia(CD_BTG, "BCO BTG PACTUAL S.A.", True),
    Companhia(CD_SERTRADING, "BTG PACTUAL COMMODITIES SERTRADING S.A.", False),
    Companhia(CD_INTER, "INTER & CO, INC.", True),
    Companhia(CD_BMG, "BANCO BMG S/A", True),
    Companhia(CD_DAYCOVAL, "BCO DAYCOVAL S.A.", True),
    Companhia("020567", "BCO PINE S.A", True),
    Companhia("024180", "IRB - BRASIL RESSEGUROS S.A.", False),
    # Ruído de substring que um `LIKE '%INTER%'` pegaria — todas reais.
    Companhia(CD_ALARES, "ALARES INTERNET PARTICIPAÇÕES S/A", False),
    Companhia("020710", "LOG-IN LOGISTICA INTERMODAL S.A.", False),
    Companhia("025992", "INTERCEMENT BRASIL S.A. - EM RECUPERAÇÃO JUDICIAL", False),
    Companhia("023574", "INTERNATIONAL MEAL COMPANY ALIMENTACAO S.A.", False),
    Companhia("024880", "LM TRANSPORTES INTERESTADUAIS SERVIÇOS E COMÉRCIO S.A.", False),
    # Ruído de "brasil": no painel real são 27 companhias, e é isso que impede
    # o token de identificar alguém.
    Companhia("017671", "TELEFÔNICA BRASIL S.A", False),
    Companhia("019763", "EDP - ENERGIAS DO BRASIL S.A.", False),
    Companhia("021342", "OSX BRASIL S.A. - EM RECUPERAÇÃO JUDICIAL", False),
    Companhia("021466", "BANCO RCI BRASIL S.A.", True),
)

TRIMESTRES_PAINEL = ("1T2025", "2T2025", "3T2025", "4T2025", "1T2026", "2T2026")
TRIMESTRES_CORPUS = ("2T2025", "3T2025", "4T2025", "1T2026")


@pytest.fixture(scope="module")
def indice() -> IndiceCobertura:
    return IndiceCobertura(
        companhias=COMPANHIAS_FIXTURE,
        trimestres_painel={c.cd_cvm: TRIMESTRES_PAINEL for c in COMPANHIAS_FIXTURE},
        trimestres_corpus={cd: TRIMESTRES_CORPUS for cd in CD_CVM_CORPUS_FIXTURE},
    )


class LeitorFalso:
    """Duplo de teste do painel — nenhum acesso a DuckDB, nenhuma rede."""

    def __init__(self, fatos: dict[tuple[str, str, str], FatoEstruturado]):
        self.fatos = fatos
        self.chamadas: list[tuple[str, str, str]] = []

    def ler(self, cd_cvm: str, conceito: str, trimestre: str):
        self.chamadas.append((cd_cvm, conceito, trimestre))
        return self.fatos.get((cd_cvm, conceito, trimestre))


@pytest.fixture
def leitor() -> LeitorFalso:
    # Valores reais do painel (medidos em 2026-08-10).
    return LeitorFalso(
        {
            (CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "3T2025"): FatoEstruturado(
                cd_cvm=CD_ITAU,
                denom_social="ITAU UNIBANCO HOLDING S.A.",
                trimestre="3T2025",
                conceito=CONCEITO_LUCRO_CONTROLADORES,
                valor_reais=11_306_000_000.0,
                origem="arquivado",
            ),
            (CD_INTER, CONCEITO_LUCRO_CONTROLADORES, "3T2025"): FatoEstruturado(
                cd_cvm=CD_INTER,
                denom_social="INTER & CO, INC.",
                trimestre="3T2025",
                conceito=CONCEITO_LUCRO_CONTROLADORES,
                valor_reais=336_345_000.0,
                origem="arquivado",
            ),
            (CD_INTER, CONCEITO_LUCRO_CONTROLADORES, "4T2025"): FatoEstruturado(
                cd_cvm=CD_INTER,
                denom_social="INTER & CO, INC.",
                trimestre="4T2025",
                conceito=CONCEITO_LUCRO_CONTROLADORES,
                valor_reais=374_392_000.0,
                origem="derivado",
                ds_conta="Atribuído aos Sócios da Empresa Controladora",
            ),
        }
    )


# --------------------------------------------------------------------------- #
# Tokenização — token inteiro, nunca substring
# --------------------------------------------------------------------------- #


class TestTokenizacao:
    @pytest.mark.parametrize(
        "razao_social,esperado",
        [
            ("INTER & CO, INC.", ("inter", "co", "inc")),
            ("ALARES INTERNET PARTICIPAÇÕES S/A", ("alares", "internet", "participacoes", "s", "a")),
            ("BCO BTG PACTUAL S.A.", ("bco", "btg", "pactual", "s", "a")),
            ("", ()),
            (None, ()),
        ],
    )
    def test_tokenizar_nome(self, razao_social, esperado):
        assert tokenizar_nome(razao_social) == esperado

    @pytest.mark.parametrize(
        "razao_social",
        [
            "ALARES INTERNET PARTICIPAÇÕES S/A",
            "LOG-IN LOGISTICA INTERMODAL S.A.",
            "INTERCEMENT BRASIL S.A. - EM RECUPERAÇÃO JUDICIAL",
            "INTERNATIONAL MEAL COMPANY ALIMENTACAO S.A.",
            "LM TRANSPORTES INTERESTADUAIS SERVIÇOS E COMÉRCIO S.A.",
        ],
    )
    def test_inter_e_substring_mas_nao_token(self, razao_social):
        """As cinco casam `LIKE '%INTER%'` no painel real e nenhuma é "Inter"."""
        assert "inter" in razao_social.lower()
        assert "inter" not in tokenizar_nome(razao_social)


# --------------------------------------------------------------------------- #
# Resolução de entidade (RN11)
# --------------------------------------------------------------------------- #


class TestResolucaoPorCodigo:
    @pytest.mark.parametrize("termo", ["Inter", "banco inter", "Inter & Co", "INTER"])
    def test_variantes_do_inter_resolvem_para_080217(self, termo, indice):
        resolucao = resolver_entidade(termo, indice)
        assert [c.cd_cvm for c in resolucao.candidatas] == [CD_INTER]
        assert resolucao.resolvida is not None
        assert resolucao.resolvida.cd_cvm == CD_INTER

    def test_inter_nunca_casa_alares_internet(self, indice):
        codigos = {c.cd_cvm for c in resolver_entidade("Inter", indice).candidatas}
        assert CD_ALARES not in codigos
        assert codigos == {CD_INTER}

    @pytest.mark.parametrize(
        "termo,esperado",
        [
            ("022616", CD_BTG),
            ("22616", CD_BTG),          # sem zeros à esquerda
            ("080217", CD_INTER),
            ("027774", CD_SERTRADING),
        ],
    )
    def test_cd_cvm_explicito_resolve_direto(self, termo, esperado, indice):
        """É assim que o usuário responde à pergunta de desambiguação."""
        resolucao = resolver_entidade(termo, indice)
        assert resolucao.resolvida is not None
        assert resolucao.resolvida.cd_cvm == esperado

    @pytest.mark.parametrize("termo", ["BB", "Banco do Brasil", "banco do brasil"])
    def test_banco_do_brasil_resolve_apesar_de_brasil_ser_token_comum(
        self, termo, indice
    ):
        """Risco 12c: sem o apelido conferido, o BB cairia em `nenhuma`.

        `bco` e `brasil` são tokens compartilhados demais para identificar
        alguém, então nenhum caminho de token resolve o Banco do Brasil.
        """
        resolucao = resolver_entidade(termo, indice)
        assert [c.cd_cvm for c in resolucao.candidatas] == [CD_BB]

    def test_brasil_sozinho_nao_identifica_companhia(self, indice):
        assert "brasil" not in indice.tokens_distintivos

    def test_termo_vazio_nao_resolve_nada(self, indice):
        assert resolver_entidade("   ", indice).candidatas == ()


class TestDesambiguacaoBTG:
    """RN11: nome que resolve para mais de uma companhia PERGUNTA, não escolhe."""

    @pytest.mark.parametrize("termo", ["BTG", "btg", "BTG Pactual", "btg pactual s.a."])
    def test_btg_resolve_para_duas_companhias(self, termo, indice):
        resolucao = resolver_entidade(termo, indice)
        assert [c.cd_cvm for c in resolucao.candidatas] == [CD_BTG, CD_SERTRADING]

    def test_ticker_e_identificador_e_resolve_sozinho(self, indice):
        """`BPAC11` designa uma companhia só — ticker é código, não nome."""
        resolucao = resolver_entidade("bpac11", indice)
        assert resolucao.resolvida is not None
        assert resolucao.resolvida.cd_cvm == CD_BTG

    def test_btg_nunca_escolhe_a_mais_provavel(self, indice):
        resolucao = resolver_entidade("BTG", indice)
        assert resolucao.ambigua is True
        assert resolucao.resolvida is None

    def test_pergunta_de_desambiguacao_nomeia_os_dois_codigos(self, indice):
        pergunta = resolver_entidade("BTG", indice).pergunta_desambiguacao()
        assert pergunta is not None
        assert CD_BTG in pergunta and CD_SERTRADING in pergunta
        assert "BCO BTG PACTUAL S.A." in pergunta
        assert "BTG PACTUAL COMMODITIES SERTRADING S.A." in pergunta
        assert "CD_CVM" in pergunta

    def test_termo_sem_ambiguidade_nao_gera_pergunta(self, indice):
        assert resolver_entidade("Inter", indice).pergunta_desambiguacao() is None

    @pytest.mark.parametrize(
        "resposta,esperado",
        [
            ("027774", CD_SERTRADING),
            ("BTG Pactual Commodities", CD_SERTRADING),
            ("Sertrading", CD_SERTRADING),
            ("022616", CD_BTG),
        ],
    )
    def test_resposta_do_usuario_desambigua(self, resposta, esperado, indice):
        """A desambiguação fecha por código OU por nome suficientemente específico."""
        resolucao = resolver_entidade(resposta, indice)
        assert resolucao.resolvida is not None
        assert resolucao.resolvida.cd_cvm == esperado

    def test_triagem_de_termo_ambiguo_nao_produz_cobertura(self, indice):
        triagem = triar_entidade("BTG", indice)
        assert triagem.precisa_desambiguacao is True
        assert triagem.cobertura is None


class TestResolucaoVaziaVaiParaLog:
    """Risco 12c: ausência silenciosa é o modo de falha, não a ausência."""

    def test_nubank_nao_resolve_e_registra_no_log(self, indice, caplog):
        with caplog.at_level(logging.WARNING, logger="src.cobertura"):
            resolucao = resolver_entidade("Nubank", indice)
        assert resolucao.vazia is True
        assert any(
            "não resolveu nenhum CD_CVM" in registro.getMessage()
            for registro in caplog.records
        )

    def test_nubank_traz_motivo_declarado_da_ausencia(self, indice):
        resolucao = resolver_entidade("Nubank", indice)
        assert resolucao.motivo_ausencia is not None
        assert "NYSE" in resolucao.motivo_ausencia
        assert "não arquiva" in resolucao.motivo_ausencia

    def test_nome_desconhecido_tambem_vai_para_log(self, indice, caplog):
        with caplog.at_level(logging.WARNING, logger="src.cobertura"):
            resolucao = resolver_entidade("Banco Inexistente XPTO", indice)
        assert resolucao.vazia is True
        assert resolucao.motivo_ausencia is None
        assert caplog.records


class TestExtrairMencoes:
    def test_pergunta_sobre_inter(self, indice):
        mencoes = extrair_mencoes("e o Inter?", indice)
        assert len(mencoes) == 1
        assert resolver_entidade(mencoes[0], indice).resolvida.cd_cvm == CD_INTER

    def test_pergunta_sobre_nubank(self, indice):
        """A menção é devolvida na **forma de superfície**, não no slug.

        O slug perde informação e reintroduz ambiguidade que o texto não tinha
        (ver `test_frase_banco_do_brasil_...`). O que importa é a propriedade:
        o Nubank é reconhecido como menção, para poder ser resolvido a
        `nenhuma` em vez de sumir da triagem.
        """
        assert extrair_mencoes("e o Nubank?", indice) == ("nubank",)
        assert resolver_entidade("nubank", indice).candidatas == ()

    def test_mencao_ao_pais_nao_vira_companhia(self, indice):
        """O token `brasil` está em razão social demais para identificar alguém."""
        assert extrair_mencoes(
            "qual instituição financeira no Brasil cresceu mais?", indice
        ) == ()

    def test_frase_banco_do_brasil_e_reivindicada_pelo_apelido_conferido(
        self, indice
    ):
        """Limitação herdada, declarada: o apelido casa a frase literal.

        `APELIDOS_BANCOS` (usado pela recuperação desde a etapa 6) mapeia
        "banco do brasil" para o BB, então a frase é lida como menção mesmo
        quando o autor queria dizer "banco brasileiro". Preferir o apelido
        conferido a inventar aqui uma segunda tabela de nomes é a decisão; o
        efeito colateral fica registrado em teste em vez de escondido.

        A menção sai na **forma de superfície**, e isso não é cosmético:
        devolver o slug `BB` fazia o termo casar o token distintivo `bb`, que
        designa também BB SEGURIDADE (023159), e o sistema passava a pedir
        desambiguação de um nome inequívoco — a inversão do risco 12c. A forma
        longa tem como único token não genérico `brasil`, presente em 27
        companhias e portanto fora do índice distintivo, então só o apelido
        conferido responde.
        """
        assert extrair_mencoes("qual banco do Brasil cresceu mais?", indice) == (
            "banco do brasil",
        )
        resolucao = resolver_entidade("banco do brasil", indice)
        assert [c.cd_cvm for c in resolucao.candidatas] == ["001023"]

    def test_preposicao_nao_vira_mencao_de_companhia(self, indice):
        """Razão social abrevia *comércio* como "COM" e o AERIS contém "PARA".

        Sem palavras funcionais no conjunto genérico, "compare o Itaú **com** o
        Bradesco" extraía `com` como companhia e disparava desambiguação
        espúria com chamada de painel inútil.
        """
        assert extrair_mencoes(
            "compare o lucro do Itaú com o do Bradesco", indice
        ) == ("itau", "bradesco")
        assert extrair_mencoes(
            "qual o resultado para o Santander no 1T2026?", indice
        ) == ("santander",)

    def test_ambiguidade_real_do_btg_sobrevive(self, indice):
        """A correção acima não pode apagar a ambiguidade que o painel tem.

        "BTG" designa duas companhias distintas (RN11) e a resposta correta é
        perguntar. Um conserto que resolvesse tudo para uma só teria trocado um
        falso positivo por um falso negativo, que é pior.
        """
        assert [
            c.cd_cvm for c in resolver_entidade("btg", indice).candidatas
        ] == ["022616", "027774"]

    def test_comparativa_produz_uma_mencao_por_banco(self, indice):
        mencoes = extrair_mencoes(
            "compare o lucro do Itaú e do Bradesco no 3T2025", indice
        )
        codigos = {
            resolver_entidade(m, indice).resolvida.cd_cvm for m in mencoes
        }
        assert codigos == {CD_ITAU, CD_BRADESCO}

    def test_mencoes_equivalentes_nao_duplicam(self, indice):
        """"BTG" e "pactual" apontam para as mesmas duas companhias."""
        assert len(extrair_mencoes("o BTG Pactual divulgou", indice)) == 1

    def test_pergunta_sem_companhia(self, indice):
        assert extrair_mencoes("qual foi o lucro no trimestre?", indice) == ()


# --------------------------------------------------------------------------- #
# Triagem de cobertura (RN12)
# --------------------------------------------------------------------------- #


class TestTresEstados:
    def test_vocabulario_bate_com_o_gabarito_congelado(self):
        """Os três estados são o vocabulário de `cobertura_esperada`."""
        assert {e.value for e in ESTADOS_RN12} == {"ambas", "so_painel", "nenhuma"}

    def test_banco_do_corpus_esta_em_ambas(self, indice):
        cobertura = triar_entidade("Itaú", indice).cobertura
        assert cobertura.estado is EstadoCobertura.AMBAS
        assert cobertura.motivo == MOTIVO_NA
        assert cobertura.no_painel and cobertura.no_corpus

    def test_inter_e_so_painel_e_nunca_nenhuma(self, indice):
        """O erro invertido do risco 12c: `nenhuma` para quem ESTÁ no painel."""
        cobertura = triar_entidade("Inter", indice).cobertura
        assert cobertura.estado is EstadoCobertura.SO_PAINEL
        assert cobertura.estado is not EstadoCobertura.NENHUMA
        assert cobertura.companhia.cd_cvm == CD_INTER
        assert cobertura.motivo == MOTIVO_FORA_DO_CORPUS

    @pytest.mark.parametrize(
        "nome,codigo",
        [("Inter", CD_INTER), ("BMG", CD_BMG), ("Daycoval", CD_DAYCOVAL)],
    )
    def test_instituicoes_do_painel_fora_do_corpus(self, nome, codigo, indice):
        cobertura = triar_entidade(nome, indice).cobertura
        assert cobertura.estado is EstadoCobertura.SO_PAINEL
        assert cobertura.companhia.cd_cvm == codigo

    def test_nubank_e_nenhuma(self, indice):
        cobertura = triar_entidade("Nubank", indice).cobertura
        assert cobertura.estado is EstadoCobertura.NENHUMA
        assert cobertura.companhia is None
        assert cobertura.motivo == MOTIVO_FORA_DO_CORPUS

    def test_nubank_e_inter_tem_respostas_diferentes(self, indice):
        """A pergunta é a mesma para o leigo; a resposta correta não é."""
        nubank = triar_entidade("Nubank", indice).cobertura
        inter = triar_entidade("Inter", indice).cobertura
        assert nubank.estado is not inter.estado


class TestCoberturaPorTrimestre:
    """As duas janelas não coincidem — o estado depende do trimestre pedido."""

    def test_trimestre_nas_duas_camadas(self, indice):
        cobertura = triar_entidade("Itaú", indice, "3T2025").cobertura
        assert cobertura.estado is EstadoCobertura.AMBAS

    @pytest.mark.parametrize("trimestre", ["1T2025", "2T2026"])
    def test_trimestre_so_no_painel(self, trimestre, indice):
        """`1T2025` e `2T2026` existem no painel e não têm release indexado."""
        cobertura = triar_entidade("Itaú", indice, trimestre).cobertura
        assert cobertura.estado is EstadoCobertura.SO_PAINEL
        assert cobertura.motivo == MOTIVO_PERIODO_AUSENTE

    def test_trimestre_fora_das_duas_camadas(self, indice):
        cobertura = triar_entidade("Santander", indice, "1T2020").cobertura
        assert cobertura.estado is EstadoCobertura.NENHUMA
        assert cobertura.motivo == MOTIVO_PERIODO_AUSENTE
        assert cobertura.companhia.cd_cvm == CD_SANTANDER

    def test_trimestre_da_pergunta_e_usado_sem_ser_informado(self, indice):
        triagens = triagem_cobertura("lucro do Itaú no 1T2025", indice)
        assert len(triagens) == 1
        assert triagens[0].cobertura.trimestre == "1T2025"
        assert triagens[0].cobertura.estado is EstadoCobertura.SO_PAINEL


class TestEstadoDeInconsistencia:
    """`so_corpus` não é estado da RN12 — é inconsistência, e é declarada."""

    @pytest.fixture
    def indice_inconsistente(self) -> IndiceCobertura:
        return IndiceCobertura(
            companhias=(Companhia(CD_ITAU, "ITAU UNIBANCO HOLDING S.A.", True),),
            trimestres_painel={},
            trimestres_corpus={CD_ITAU: TRIMESTRES_CORPUS},
        )

    def test_release_sem_painel_nao_vira_ambas_nem_nenhuma(
        self, indice_inconsistente
    ):
        cobertura = triar_entidade("Itaú", indice_inconsistente).cobertura
        assert cobertura.estado is EstadoCobertura.SO_CORPUS
        assert cobertura.estado not in ESTADOS_RN12
        assert cobertura.no_corpus is True
        assert cobertura.no_painel is False

    def test_inconsistencia_vai_para_log(self, indice_inconsistente, caplog):
        with caplog.at_level(logging.WARNING, logger="src.cobertura"):
            triar_entidade("Itaú", indice_inconsistente)
        assert any("inconsistência" in r.getMessage() for r in caplog.records)

    def test_corpus_e_painel_reais_nunca_produzem_so_corpus(self, indice):
        estados = {
            triar_entidade(c.cd_cvm, indice).cobertura.estado
            for c in indice.companhias
        }
        assert EstadoCobertura.SO_CORPUS not in estados
        assert estados <= ESTADOS_RN12


class TestListasDeCobertura:
    def test_companhias_do_corpus_sao_os_cinco_bancos(self, indice):
        codigos = [c.cd_cvm for c in companhias_do_corpus(indice)]
        assert codigos == sorted(CD_CVM_CORPUS_FIXTURE)

    def test_bancos_so_no_painel_incluem_inter_bmg_daycoval(self, indice):
        codigos = {c.cd_cvm for c in companhias_so_no_painel(indice)}
        assert {CD_INTER, CD_BMG, CD_DAYCOVAL, CD_MERCANTIL} <= codigos
        assert codigos.isdisjoint(CD_CVM_CORPUS_FIXTURE)


# --------------------------------------------------------------------------- #
# Braço C — determinístico, sem LLM
# --------------------------------------------------------------------------- #


class TestBracoCDeterministico:
    def test_nubank_e_recusa_que_nomeia_a_ausencia(self, indice, leitor):
        resposta = responder_por_gabarito("e o Nubank?", indice, leitor)
        assert resposta.braco == "C"
        assert resposta.recusa is True
        assert resposta.motivo_recusa == MOTIVO_FORA_DO_CORPUS
        assert "NYSE" in resposta.resposta
        assert leitor.chamadas == []

    def test_inter_responde_o_numero_e_diz_o_que_falta(self, indice, leitor):
        resposta = responder_por_gabarito(
            "qual o lucro líquido do Inter no 3T2025?", indice, leitor
        )
        assert resposta.recusa is False
        assert "não há release indexado" in resposta.resposta.lower()
        assert "R$ 336.345.000,00" in resposta.resposta
        assert resposta.parcial is True

    def test_so_painel_cita_a_fonte_estruturada(self, indice, leitor):
        resposta = responder_por_gabarito(
            "qual o lucro líquido do Inter no 3T2025?", indice, leitor
        )
        assert len(resposta.citacoes) == 1
        citacao = resposta.citacoes[0]
        assert CD_INTER in citacao
        assert "3T2025" in citacao
        assert "arquivado" in citacao

    def test_valor_derivado_sai_marcado(self, indice, leitor):
        """RN10: o 4T não existe como ITR e não pode passar por arquivado."""
        resposta = responder_por_gabarito(
            "qual o lucro líquido do Inter no 4T2025?", indice, leitor
        )
        assert resposta.fatos[0].derivado is True
        assert "RN10" in resposta.resposta
        assert "DERIVADO" in resposta.citacoes[0]
        assert "DFP anual − ITR acumulado do 3T" in resposta.citacoes[0]

    def test_btg_devolve_desambiguacao_e_nao_responde(self, indice, leitor):
        resposta = responder_por_gabarito(
            "qual o lucro do BTG no 3T2025?", indice, leitor
        )
        assert resposta.precisa_desambiguacao is True
        assert resposta.recusa is False
        assert CD_BTG in resposta.resposta and CD_SERTRADING in resposta.resposta
        assert resposta.fatos == ()
        assert leitor.chamadas == []

    def test_ambas_traz_o_numero_contabil(self, indice, leitor):
        resposta = responder_por_gabarito(
            "qual o lucro líquido do Itaú no 3T2025?", indice, leitor
        )
        assert resposta.fatos[0].valor_reais == 11_306_000_000.0
        assert "R$ 11.306.000.000,00" in resposta.resposta

    def test_sem_leitor_a_resposta_e_parcial(self, indice):
        resposta = responder_por_gabarito(
            "qual o lucro líquido do Itaú no 3T2025?", indice
        )
        assert resposta.parcial is True
        assert resposta.fatos == ()

    def test_trimestre_fora_das_camadas_e_recusa_diagnosticada(self, indice, leitor):
        resposta = responder_por_gabarito(
            "qual o lucro do Santander no 1T2020?", indice, leitor
        )
        assert resposta.recusa is True
        assert resposta.motivo_recusa == MOTIVO_PERIODO_AUSENTE

    def test_pergunta_sem_companhia_e_recusa_declarada(self, indice, leitor):
        resposta = responder_por_gabarito("qual foi o lucro?", indice, leitor)
        assert resposta.recusa is True
        assert resposta.triagens == ()

    def test_conceito_ausente_no_painel_marca_parcial(self, indice, leitor):
        resposta = responder_por_gabarito(
            "qual o patrimônio líquido do Itaú no 3T2025?", indice, leitor
        )
        assert resposta.fatos == ()
        assert resposta.parcial is True
        assert "não traz" in resposta.resposta

    def test_dicionario_e_serializavel(self, indice, leitor):
        dicionario = responder_por_gabarito("e o Inter?", indice, leitor).como_dicionario()
        assert dicionario["braco"] == "C"
        assert dicionario["triagens"][0]["cobertura"]["estado"] == "so_painel"

    @pytest.mark.parametrize(
        "pergunta",
        [
            "qual o lucro líquido do Itaú no 3T2025?",
            "qual o lucro líquido do Inter no 3T2025?",
            "qual o lucro líquido do Inter no 4T2025?",
            "e o Nubank?",
            "qual o lucro do BTG no 3T2025?",
            "qual o lucro do Santander no 1T2020?",
        ],
    )
    def test_todo_numero_publicado_vem_com_citacao(self, pergunta, indice, leitor):
        """RN01 verificada por código sobre a saída, nunca confiada ao modelo.

        O braço C não tem modelo nenhum, mas a invariante é a mesma: se um
        valor aparece na resposta, a fonte estruturada que o produziu está
        citada. Resposta com número e sem citação seria recusa registrada.
        """
        resposta = responder_por_gabarito(pergunta, indice, leitor)
        if "R$" in resposta.resposta:
            assert resposta.citacoes
            assert len(resposta.citacoes) == len(resposta.fatos)
        else:
            assert resposta.fatos == ()


class TestConceitoEFormatacao:
    @pytest.mark.parametrize(
        "pergunta,esperado",
        [
            ("qual o lucro líquido do Itaú?", CONCEITO_LUCRO_CONTROLADORES),
            ("qual o lucro líquido consolidado?", CONCEITO_LUCRO_CONSOLIDADO),
            ("qual o patrimônio líquido?", CONCEITO_PATRIMONIO_LIQUIDO),
            ("qual o ativo total?", CONCEITO_ATIVO_TOTAL),
            ("o que a administração disse sobre crédito?", None),
        ],
    )
    def test_extrair_conceito(self, pergunta, esperado):
        assert extrair_conceito(pergunta) == esperado

    def test_lucro_liquido_e_sempre_qualificado_na_resposta(self, indice, leitor):
        """"Lucro líquido" tem três leituras; nenhuma resposta o usa sem dizer qual."""
        resposta = responder_por_gabarito(
            "qual o lucro líquido do Itaú no 3T2025?", indice, leitor
        )
        assert "atribuído aos sócios da empresa controladora" in resposta.resposta.lower()

    @pytest.mark.parametrize(
        "valor,esperado",
        [
            (11_306_000_000.0, "R$ 11.306.000.000,00"),
            (336_345_000.0, "R$ 336.345.000,00"),
            (0.0, "R$ 0,00"),
            (-1234.5, "R$ -1.234,50"),
            (999.999, "R$ 1.000,00"),
        ],
    )
    def test_formatar_reais(self, valor, esperado):
        assert formatar_reais(valor) == esperado


class TestTextoDeCobertura:
    def test_so_painel_diz_que_nada_pode_ser_dito_sobre_o_release(self, indice):
        texto = descrever_cobertura(triar_entidade("Inter", indice))
        assert "administração" in texto
        assert CD_INTER in texto

    def test_ambiguidade_devolve_a_pergunta(self, indice):
        assert "Qual delas?" in descrever_cobertura(triar_entidade("BTG", indice))


# --------------------------------------------------------------------------- #
# Carga do índice a partir de painel + manifesto
# --------------------------------------------------------------------------- #


def _montar_painel(caminho: Path) -> None:
    """Painel DuckDB mínimo, montado pelo esquema real de `dados_estruturados`."""
    conexao = duckdb.connect(str(caminho))
    try:
        criar_esquema(conexao)
        conexao.executemany(
            "INSERT INTO companhias VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (CD_ITAU, "60.872.504/0001-23", "ITAU UNIBANCO HOLDING S.A.",
                 "Bancos", "ITUB4", True, "plano_309"),
                (CD_INTER, "18.945.670/0001-46", "INTER & CO, INC.",
                 None, None, True, "plano_309"),
                (CD_ALARES, "05.827.301/0001-52", "ALARES INTERNET PARTICIPAÇÕES S/A",
                 None, None, False, "plano_309"),
            ],
        )
        conexao.execute(
            "INSERT INTO mapa_contas VALUES "
            "('plano_309', ?, '3.09.01', 'Atribuído aos Sócios da Empresa "
            "Controladora', 'atribuido aos socios da empresa controladora')",
            [CONCEITO_LUCRO_CONTROLADORES],
        )
        linhas = []
        for cd_cvm, trimestres in (
            (CD_ITAU, ("2T2025", "3T2025")),
            (CD_INTER, ("2T2025", "3T2025")),
            (CD_ALARES, ("3T2025",)),
        ):
            for trimestre in trimestres:
                linhas.append(
                    (
                        cd_cvm, "itr", "DRE", trimestre, "trimestral",
                        "2025-09-30", "2025-07-01", "2025-09-30",
                        "3.09.01", "Atribuído aos Sócios da Empresa Controladora",
                        "atribuido aos socios da empresa controladora",
                        1000.0, "MIL", 1_000_000.0, 1, "arquivado",
                    )
                )
        conexao.executemany(
            "INSERT INTO fatos_contabeis VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            linhas,
        )
    finally:
        conexao.close()


def _montar_manifesto(caminho: Path) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(
            ["empresa", "trimestre", "documento", "url", "data_coleta", "hash_sha256"]
        )
        for trimestre in ("2T2025", "3T2025"):
            escritor.writerow(
                [
                    "ITAU",
                    trimestre,
                    f"itau_release_{trimestre}",
                    f"https://exemplo.invalido/itau_{trimestre}",
                    "2026-07-15",
                    "0" * 64,
                ]
            )


@pytest.fixture(scope="module")
def carregado(tmp_path_factory) -> IndiceCobertura:
    """Índice montado a partir de um painel DuckDB e um manifesto de verdade."""
    base = tmp_path_factory.mktemp("cobertura")
    painel = base / "cvm.duckdb"
    manifesto = base / "metadados.csv"
    _montar_painel(painel)
    _montar_manifesto(manifesto)
    return carregar_indice_cobertura(Config(), painel, manifesto)


class TestCargaDoIndice:
    def test_le_as_companhias_do_painel(self, carregado):
        assert {c.cd_cvm for c in carregado.companhias} == {
            CD_ITAU, CD_INTER, CD_ALARES
        }

    def test_le_os_trimestres_da_visao_semantica(self, carregado):
        assert carregado.trimestres_painel[CD_INTER] == ("2T2025", "3T2025")

    def test_liga_o_manifesto_ao_cd_cvm_e_nao_ao_nome(self, carregado):
        """A ponte slug→CD_CVM vem de `BANCOS_CORPUS`, conferido (RN11)."""
        assert carregado.trimestres_corpus == {CD_ITAU: ("2T2025", "3T2025")}

    def test_itau_ambas_inter_so_painel_sobre_dado_carregado(self, carregado):
        assert triar_entidade("Itaú", carregado).cobertura.estado is (
            EstadoCobertura.AMBAS
        )
        assert triar_entidade("Inter", carregado).cobertura.estado is (
            EstadoCobertura.SO_PAINEL
        )

    def test_painel_inexistente_falha_explicito(self, tmp_path):
        from src.dados_estruturados import PainelIndisponivelError

        with pytest.raises(PainelIndisponivelError):
            carregar_indice_cobertura(Config(), tmp_path / "nao_existe.duckdb")


class TestIndiceCobertura:
    def test_cd_cvm_duplicado_e_recusado(self):
        with pytest.raises(ValueError, match="duplicado"):
            IndiceCobertura(
                companhias=(
                    Companhia(CD_ITAU, "ITAU UNIBANCO HOLDING S.A."),
                    Companhia(CD_ITAU, "OUTRA COISA S.A."),
                )
            )

    def test_companhia_sem_codigo_e_recusada(self):
        with pytest.raises(ValueError, match="cd_cvm"):
            Companhia("", "SEM CÓDIGO S.A.")

    def test_cobertura_serializa_para_dicionario(self, indice):
        dicionario = triar_entidade("Inter", indice).cobertura.como_dicionario()
        assert dicionario["estado"] == "so_painel"
        assert dicionario["cd_cvm"] == CD_INTER
        assert dicionario["trimestres_corpus"] == []

    def test_estado_nenhuma_sem_companhia(self):
        cobertura = Cobertura(
            estado=EstadoCobertura.NENHUMA, motivo=MOTIVO_FORA_DO_CORPUS
        )
        assert cobertura.no_painel is False
        assert cobertura.no_corpus is False
