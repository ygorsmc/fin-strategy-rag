"""Contrato do braço C — o piso honesto de 5.9.3, sem nenhuma chamada de LLM.

Nenhum teste aqui toca rede, LLM ou o `artefatos/cvm.duckdb` real: o índice de
cobertura e o leitor de painel são duplos, fiéis ao painel medido em 2026-08-10
(razões sociais e `CD_CVM` copiados do dado real, incluindo os dois BTG que a
RN11 exige desambiguar). O único arquivo real lido é
`conjunto_padrao/conjunto_agentes.csv`, que é versionado e é o contrato.

O que estes testes protegem, em ordem de importância:

1. **Pendência não vira acerto.** Dez das 15 perguntas esperam dupla leitura
   humana; nenhuma delas pode entrar em média de acerto, nem quando todos os
   critérios passam, nem quando todos falham.
2. **Os três estados da RN12 e a desambiguação da RN11** saem certos e distintos
   — o par de contraste vale exatamente porque as duas recusas são diferentes.
3. **RN01/RN02 verificadas por código sobre a saída**: valor sem citação vira
   recusa registrada, nunca resposta sem citação.
4. **O formato do registro é o dos três braços**, não o do braço C: os campos de
   custo de modelo e o veredito do Auditor existem aqui, zerados e nulo.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from src.braco_determinista import (
    APURACAO_ACERTO,
    APURACAO_ERRO,
    APURACAO_PENDENTE,
    BASE_CONTABIL_CONSOLIDADO,
    BASE_CONTABIL_CONTROLADORES,
    BASE_GERENCIAL,
    BASE_NA,
    BRACO_A,
    BRACO_B,
    BRACO_C,
    CAMPOS_REGISTRO,
    COBERTURA_AMBIGUA,
    COMPORTAMENTO_COMPLETA,
    COMPORTAMENTO_DESAMBIGUACAO,
    COMPORTAMENTO_PARCIAL,
    COMPORTAMENTO_RECUSA,
    CRITERIO_AUSENCIA_NOMEADA,
    CRITERIO_BASE,
    CRITERIO_COBERTURA,
    CRITERIO_REGRAS,
    MOTIVO_RECUSA_CONVERTIDA,
    STATUS_PARCIAL_RELEASE,
    STATUS_PENDENTE_HUMANA,
    STATUS_VERIFICADO,
    VEREDITO_CONTESTA,
    VIOLACAO_RN01_SEM_CITACAO,
    VIOLACAO_RN02_RECUSA_COM_VALOR,
    VIOLACAO_RN02_SEM_LASTRO,
    LeitorContado,
    PerguntaAgentes,
    RegistroBraco,
    ResultadoBraco,
    Verificacao,
    apurar,
    base_do_conceito,
    carregar_conjunto_agentes,
    cobertura_de,
    comportamento_de,
    executar_braco_c,
    motivo_de,
    nomeia_as_duas_camadas,
    registrar_resultado,
    resumir,
    salvar_resultado,
    valores_monetarios,
    verificar_regras,
)
from src.cobertura import (
    MOTIVO_FORA_DO_CORPUS,
    MOTIVO_NA,
    MOTIVO_PERIODO_AUSENTE,
    Companhia,
    FatoEstruturado,
    IndiceCobertura,
    RespostaDeterministica,
)
from src.config import Config
from src.ferramentas import TetoChamadasExcedidoError
from src.mapa_contas import (
    CONCEITO_ATIVO_TOTAL,
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_PATRIMONIO_LIQUIDO,
)

# --------------------------------------------------------------------------- #
# Duplos fiéis ao painel real
# --------------------------------------------------------------------------- #

CD_BB = "001023"
CD_BRADESCO = "000906"
CD_ITAU = "019348"
CD_SANTANDER = "020532"
CD_BTG = "022616"
CD_SERTRADING = "027774"
CD_INTER = "080217"
CD_MERCANTIL = "001325"

CD_CVM_CORPUS = (CD_BB, CD_BRADESCO, CD_ITAU, CD_SANTANDER, CD_BTG)

COMPANHIAS = (
    Companhia(CD_BRADESCO, "BCO BRADESCO S.A.", True),
    Companhia(CD_BB, "BCO BRASIL S.A.", True),
    Companhia(CD_MERCANTIL, "BCO MERCANTIL DO BRASIL S.A.", True),
    Companhia(CD_ITAU, "ITAU UNIBANCO HOLDING S.A.", True),
    Companhia(CD_SANTANDER, "BCO SANTANDER (BRASIL) S.A.", True),
    # RN11: "BTG" designa duas companhias, e a resposta correta é perguntar.
    Companhia(CD_BTG, "BCO BTG PACTUAL S.A.", True),
    Companhia(CD_SERTRADING, "BTG PACTUAL COMMODITIES SERTRADING S.A.", False),
    Companhia(CD_INTER, "INTER & CO, INC.", True),
    # Ruído de substring que um `LIKE '%INTER%'` pegaria — todas reais.
    Companhia("025194", "ALARES INTERNET PARTICIPAÇÕES S/A", False),
    Companhia("025992", "INTERCEMENT BRASIL S.A. - EM RECUPERAÇÃO JUDICIAL", False),
    Companhia("017671", "TELEFÔNICA BRASIL S.A", False),
)

TRIMESTRES_PAINEL = ("1T2025", "2T2025", "3T2025", "4T2025", "1T2026")
TRIMESTRES_CORPUS = ("2T2025", "3T2025", "4T2025", "1T2026")

# Valores reais do painel (medidos em 2026-08-10).
FATOS = {
    (CD_INTER, CONCEITO_LUCRO_CONTROLADORES, "1T2026"): 394_788_000.0,
    (CD_INTER, CONCEITO_LUCRO_CONSOLIDADO, "1T2026"): 417_547_000.0,
    (CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "3T2025"): 11_306_000_000.0,
    (CD_SANTANDER, CONCEITO_LUCRO_CONTROLADORES, "1T2026"): 3_217_994_000.0,
}


class LeitorFalso:
    """Duplo do painel — nenhum DuckDB, nenhuma rede."""

    def __init__(self, fatos: dict) -> None:
        self.fatos = fatos
        self.chamadas: list[tuple[str, str, str]] = []

    def ler(self, cd_cvm: str, conceito: str, trimestre: str):
        self.chamadas.append((cd_cvm, conceito, trimestre))
        valor = self.fatos.get((cd_cvm, conceito, trimestre))
        if valor is None:
            return None
        denom = next(c.denom_social for c in COMPANHIAS if c.cd_cvm == cd_cvm)
        return FatoEstruturado(
            cd_cvm=cd_cvm,
            denom_social=denom,
            trimestre=trimestre,
            conceito=conceito,
            valor_reais=valor,
            origem="arquivado",
        )


@pytest.fixture(scope="module")
def indice() -> IndiceCobertura:
    return IndiceCobertura(
        companhias=COMPANHIAS,
        trimestres_painel={c.cd_cvm: TRIMESTRES_PAINEL for c in COMPANHIAS},
        trimestres_corpus={cd: TRIMESTRES_CORPUS for cd in CD_CVM_CORPUS},
    )


@pytest.fixture
def leitor() -> LeitorFalso:
    return LeitorFalso(dict(FATOS))


@pytest.fixture
def config() -> Config:
    return Config()


def pergunta_sintetica(
    identificador: str,
    texto: str,
    *,
    cobertura: str,
    comportamento: str,
    motivo: str = MOTIVO_NA,
    bases: tuple[str, ...] = (BASE_NA,),
    status: str = STATUS_VERIFICADO,
    subconjunto: str = "cobertura",
    rota: str = "triagem_cobertura",
) -> PerguntaAgentes:
    return PerguntaAgentes(
        id=identificador,
        categoria="factual",
        subtipo_adversarial="",
        pergunta=texto,
        comportamento_aceito=(comportamento,),
        cobertura_esperada=cobertura,
        motivo_recusa_esperado=motivo,
        base_esperada=bases,
        rota_esperada=rota,
        subconjunto=subconjunto,
        status_gabarito=status,
    )


def rodar(perguntas, config, indice, leitor, **extras) -> ResultadoBraco:
    """Executa o braço C com relógio determinístico (1 s por medição)."""
    contador = iter(range(0, 10_000))
    return executar_braco_c(
        list(perguntas),
        config,
        indice=indice,
        leitor=leitor,
        relogio=lambda: float(next(contador)),
        **extras,
    )


# --------------------------------------------------------------------------- #
# Conjunto de perguntas
# --------------------------------------------------------------------------- #


class TestCarregamentoDoConjunto:
    def test_carrega_as_quinze_com_a_composicao_de_5_9_3(self):
        perguntas = carregar_conjunto_agentes()
        assert len(perguntas) == 15
        contagem = {
            chave: sum(p.subconjunto == chave for p in perguntas)
            for chave in ("cobertura", "reconciliacao", "projecoes")
        }
        assert contagem == {"cobertura": 6, "reconciliacao": 5, "projecoes": 4}

    def test_o_par_de_contraste_e_o_caso_ambiguo_estao_tipados(self):
        por_id = {p.id: p for p in carregar_conjunto_agentes()}
        assert por_id["AGTC001"].cobertura_esperada == "so_painel"
        assert por_id["AGTC002"].cobertura_esperada == "nenhuma"
        assert por_id["AGTC003"].cobertura_esperada == COBERTURA_AMBIGUA
        assert por_id["AGTC003"].comportamento_aceito == (
            COMPORTAMENTO_DESAMBIGUACAO,
        )

    def test_base_composta_vira_tupla(self):
        por_id = {p.id: p for p in carregar_conjunto_agentes()}
        assert BASE_GERENCIAL in por_id["AGTR001"].base_esperada
        assert BASE_CONTABIL_CONSOLIDADO in por_id["AGTR001"].base_esperada
        assert por_id["AGTC002"].base_esperada == (BASE_NA,)
        assert por_id["AGTC002"].exige_valor is False

    def test_so_cinco_gabaritos_estao_conferidos_no_painel(self):
        """Dez esperam dupla leitura humana — e é isso que trava a apuração."""
        perguntas = carregar_conjunto_agentes()
        verificados = [p.id for p in perguntas if p.gabarito_verificado]
        assert len(verificados) == 5
        assert set(verificados) == {
            "AGTC001",
            "AGTC002",
            "AGTC003",
            "AGTC004",
            "AGTC005",
        }

    def test_recusa_carregar_o_conjunto_congelado_por_engano(self, tmp_path):
        """RNF11: o benchmark E0–E3 não entra na camada de agentes."""
        caminho = tmp_path / "perguntas.csv"
        caminho.write_text(
            "id,conjunto,categoria,subtipo_adversarial,pergunta,"
            "comportamento_aceito,cobertura_esperada,motivo_recusa_esperado,"
            "base_esperada,rota_esperada,subconjunto,status_gabarito\n"
            "TST001,teste,factual,,x,resposta_completa,ambas,n/a,n/a,"
            "triagem_cobertura,cobertura,verificado_painel\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="conjunto"):
            carregar_conjunto_agentes(caminho)

    def test_recusa_arquivo_sem_as_colunas_do_conjunto(self, tmp_path):
        caminho = tmp_path / "outro.csv"
        caminho.write_text("id,pergunta\nTST001,x\n", encoding="utf-8")
        with pytest.raises(ValueError, match="colunas obrigatórias"):
            carregar_conjunto_agentes(caminho)

    def test_recusa_vocabulario_desconhecido(self, tmp_path):
        caminho = tmp_path / "conjunto.csv"
        caminho.write_text(
            "id,conjunto,categoria,subtipo_adversarial,pergunta,"
            "comportamento_aceito,cobertura_esperada,motivo_recusa_esperado,"
            "base_esperada,rota_esperada,subconjunto,status_gabarito\n"
            "AGT001,agentes,factual,,x,resposta_completa,talvez,n/a,n/a,"
            "triagem_cobertura,cobertura,verificado_painel\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="cobertura_esperada"):
            carregar_conjunto_agentes(caminho)


# --------------------------------------------------------------------------- #
# Os três estados e a desambiguação
# --------------------------------------------------------------------------- #


class TestTresEstadosEDesambiguacao:
    def test_so_painel_responde_o_numero_e_diz_o_que_falta(
        self, config, indice, leitor
    ):
        pergunta = pergunta_sintetica(
            "AGTC001",
            "qual o lucro líquido do Inter no 1T2026?",
            cobertura="so_painel",
            comportamento=COMPORTAMENTO_PARCIAL,
            motivo=MOTIVO_FORA_DO_CORPUS,
            bases=(BASE_CONTABIL_CONTROLADORES,),
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        assert registro.cobertura_observada == "so_painel"
        assert registro.comportamento_observado == COMPORTAMENTO_PARCIAL
        assert registro.entidades_resolvidas == (CD_INTER,)
        assert registro.bases_publicadas == (BASE_CONTABIL_CONTROLADORES,)
        assert "R$ 394.788.000,00" in registro.resposta
        assert registro.citacoes and CD_INTER in registro.citacoes[0]
        assert registro.apuracao == APURACAO_ACERTO

    def test_nenhuma_recusa_nomeando_a_ausencia(self, config, indice, leitor):
        pergunta = pergunta_sintetica(
            "AGTC002",
            "E o Nubank? Quanto ele lucrou no 1T2026?",
            cobertura="nenhuma",
            comportamento=COMPORTAMENTO_RECUSA,
            motivo=MOTIVO_FORA_DO_CORPUS,
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        assert registro.recusa is True
        assert registro.cobertura_observada == "nenhuma"
        assert registro.comportamento_observado == COMPORTAMENTO_RECUSA
        assert registro.fatos_publicados == ()
        assert "NYSE" in registro.resposta
        assert registro.apuracao == APURACAO_ACERTO

    def test_o_par_de_contraste_produz_respostas_diferentes(
        self, config, indice, leitor
    ):
        """*"e o Inter?"* e *"e o Nubank?"* não podem virar a mesma recusa."""
        inter = pergunta_sintetica(
            "INTER",
            "E o Inter? Quanto ele lucrou no 1T2026?",
            cobertura="so_painel",
            comportamento=COMPORTAMENTO_PARCIAL,
            motivo=MOTIVO_FORA_DO_CORPUS,
            bases=(BASE_CONTABIL_CONTROLADORES,),
        )
        nubank = pergunta_sintetica(
            "NUBANK",
            "E o Nubank? Quanto ele lucrou no 1T2026?",
            cobertura="nenhuma",
            comportamento=COMPORTAMENTO_RECUSA,
            motivo=MOTIVO_FORA_DO_CORPUS,
        )
        registros = rodar([inter, nubank], config, indice, leitor).registros
        assert registros[0].recusa is False and registros[1].recusa is True
        assert registros[0].fatos_publicados and not registros[1].fatos_publicados
        assert registros[0].cobertura_observada != registros[1].cobertura_observada

    def test_ambas_responde_o_numero_contabil(self, config, indice, leitor):
        pergunta = pergunta_sintetica(
            "AGTC006",
            "E o Santander? Qual o lucro líquido no 1T2026?",
            cobertura="ambas",
            comportamento=COMPORTAMENTO_COMPLETA,
            bases=(BASE_CONTABIL_CONTROLADORES,),
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        assert registro.cobertura_observada == "ambas"
        assert "R$ 3.217.994.000,00" in registro.resposta
        assert registro.apuracao == APURACAO_ACERTO

    def test_btg_pergunta_em_vez_de_escolher(self, config, indice, leitor):
        """RN11: nome que resolve para duas companhias devolve a pergunta."""
        pergunta = pergunta_sintetica(
            "AGTC003",
            "Quanto o BTG lucrou no 1T2026?",
            cobertura=COBERTURA_AMBIGUA,
            comportamento=COMPORTAMENTO_DESAMBIGUACAO,
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        assert registro.precisa_desambiguacao is True
        assert registro.cobertura_observada == COBERTURA_AMBIGUA
        assert registro.comportamento_observado == COMPORTAMENTO_DESAMBIGUACAO
        assert CD_BTG in registro.resposta and CD_SERTRADING in registro.resposta
        assert registro.fatos_publicados == ()
        assert valores_monetarios(registro.resposta) == ()
        assert registro.apuracao == APURACAO_ACERTO
        assert leitor.chamadas == []

    def test_trimestre_fora_da_janela_e_recusa_diagnosticada(
        self, config, indice, leitor
    ):
        pergunta = pergunta_sintetica(
            "PERIODO",
            "qual o lucro do Santander no 1T2020?",
            cobertura="nenhuma",
            comportamento=COMPORTAMENTO_RECUSA,
            motivo=MOTIVO_PERIODO_AUSENTE,
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        assert registro.motivo_observado == MOTIVO_PERIODO_AUSENTE
        assert registro.apuracao == APURACAO_ACERTO


# --------------------------------------------------------------------------- #
# Apuração — pendência nunca vira acerto
# --------------------------------------------------------------------------- #


class TestApuracaoPendente:
    @pytest.mark.parametrize(
        "status", [STATUS_PARCIAL_RELEASE, STATUS_PENDENTE_HUMANA]
    )
    def test_gabarito_nao_conferido_nao_vira_acerto(
        self, status, config, indice, leitor
    ):
        """Todos os critérios passam — e ainda assim não é acerto."""
        pergunta = pergunta_sintetica(
            "PENDENTE",
            "E o Nubank? Quanto ele lucrou no 1T2026?",
            cobertura="nenhuma",
            comportamento=COMPORTAMENTO_RECUSA,
            motivo=MOTIVO_FORA_DO_CORPUS,
            status=status,
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        assert all(v.passou for v in registro.verificacoes if v.aplicavel)
        assert registro.apuracao == APURACAO_PENDENTE
        assert registro.acerto is None
        assert status in registro.motivo_apuracao

    def test_gabarito_nao_conferido_tambem_nao_vira_erro(
        self, config, indice, leitor
    ):
        """Divergência sobre gabarito pendente é registrada, não pontuada."""
        pergunta = pergunta_sintetica(
            "PENDENTE",
            "E o Nubank? Quanto ele lucrou no 1T2026?",
            cobertura="ambas",  # diverge do que o braço vai responder
            comportamento=COMPORTAMENTO_COMPLETA,
            status=STATUS_PENDENTE_HUMANA,
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        reprovados = [
            v.criterio for v in registro.verificacoes if v.aplicavel and not v.passou
        ]
        assert CRITERIO_COBERTURA in reprovados
        assert registro.apuracao == APURACAO_PENDENTE
        assert registro.acerto is None
        assert "Critérios que já divergem" in registro.motivo_apuracao

    def test_pendencia_fica_fora_da_taxa_de_acerto(self, config, indice, leitor):
        certa = pergunta_sintetica(
            "OK",
            "E o Nubank? Quanto ele lucrou no 1T2026?",
            cobertura="nenhuma",
            comportamento=COMPORTAMENTO_RECUSA,
            motivo=MOTIVO_FORA_DO_CORPUS,
        )
        pendente = pergunta_sintetica(
            "PEND",
            "E o Nubank? Quanto ele lucrou no 1T2026?",
            cobertura="nenhuma",
            comportamento=COMPORTAMENTO_RECUSA,
            motivo=MOTIVO_FORA_DO_CORPUS,
            status=STATUS_PENDENTE_HUMANA,
        )
        resumo = rodar([certa, pendente], config, indice, leitor).resumo
        assert resumo["n"] == 2
        assert resumo["apurados"] == 1
        assert resumo["acertos"] == 1
        assert resumo["pendentes"] == 1
        assert resumo["taxa_acerto"] == 1.0
        assert resumo["base_da_taxa"] == "apurados"

    def test_resumo_sem_apurado_nao_inventa_taxa(self):
        registros = (
            RegistroBraco(
                id_pergunta="X",
                braco=BRACO_C,
                subconjunto="projecoes",
                categoria="qualitativa",
                rota_esperada="acompanhamento_projecoes",
                pergunta="?",
                status_gabarito=STATUS_PENDENTE_HUMANA,
            ),
        )
        resumo = resumir(registros)
        assert resumo["taxa_acerto"] is None
        assert resumo["pendentes"] == 1

    def test_registro_recusa_pendencia_com_acerto(self):
        with pytest.raises(ValueError, match="pendente"):
            RegistroBraco(
                id_pergunta="X",
                braco=BRACO_C,
                subconjunto="cobertura",
                categoria="factual",
                rota_esperada="triagem_cobertura",
                pergunta="?",
                apuracao=APURACAO_PENDENTE,
                acerto=True,
            )


class TestApuracaoConcluida:
    def test_base_divergente_reprova(self, config, indice, leitor):
        """Número certo na base errada não é resposta certa (mapa de contas)."""
        pergunta = pergunta_sintetica(
            "BASE",
            "qual o lucro líquido do Inter no 1T2026?",
            cobertura="so_painel",
            comportamento=COMPORTAMENTO_PARCIAL,
            motivo=MOTIVO_FORA_DO_CORPUS,
            bases=(BASE_CONTABIL_CONSOLIDADO,),
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        assert registro.bases_publicadas == (BASE_CONTABIL_CONTROLADORES,)
        assert registro.apuracao == APURACAO_ERRO
        assert registro.acerto is False
        assert CRITERIO_BASE in registro.motivo_apuracao

    def test_valor_apresentado_onde_o_gabarito_proibe_reprova(self):
        pergunta = pergunta_sintetica(
            "AMBIGUA",
            "quanto o BTG lucrou?",
            cobertura=COBERTURA_AMBIGUA,
            comportamento=COMPORTAMENTO_DESAMBIGUACAO,
        )
        apuracao, acerto, _, verificacoes = apurar(
            pergunta,
            cobertura_observada=COBERTURA_AMBIGUA,
            comportamento_observado=COMPORTAMENTO_DESAMBIGUACAO,
            motivo_observado=MOTIVO_NA,
            bases_publicadas=[BASE_CONTABIL_CONSOLIDADO],
            tem_valor_publicado=True,
            resposta_texto="BCO BTG PACTUAL lucrou R$ 4.935.166.000,00",
            violacoes=(),
        )
        assert (apuracao, acerto) == (APURACAO_ERRO, False)
        base = next(v for v in verificacoes if v.criterio == CRITERIO_BASE)
        assert base.passou is False

    def test_recusa_que_nao_nomeia_as_duas_camadas_reprova(self):
        """RN12: recusar sem dizer o tipo de ausência é meia resposta."""
        pergunta = pergunta_sintetica(
            "C6",
            "E o C6 Bank?",
            cobertura="nenhuma",
            comportamento=COMPORTAMENTO_RECUSA,
            motivo=MOTIVO_FORA_DO_CORPUS,
        )
        apuracao, acerto, _, verificacoes = apurar(
            pergunta,
            cobertura_observada="nenhuma",
            comportamento_observado=COMPORTAMENTO_RECUSA,
            motivo_observado=MOTIVO_FORA_DO_CORPUS,
            bases_publicadas=[],
            tem_valor_publicado=False,
            resposta_texto="Nenhuma companhia foi identificada na pergunta.",
            violacoes=(),
        )
        assert (apuracao, acerto) == (APURACAO_ERRO, False)
        criterio = next(
            v for v in verificacoes if v.criterio == CRITERIO_AUSENCIA_NOMEADA
        )
        assert (criterio.aplicavel, criterio.passou) == (True, False)

    def test_ausencia_nomeada_nao_se_aplica_fora_da_recusa(self):
        pergunta = pergunta_sintetica(
            "AMBAS",
            "qual o lucro do Itaú no 3T2025?",
            cobertura="ambas",
            comportamento=COMPORTAMENTO_COMPLETA,
            bases=(BASE_CONTABIL_CONTROLADORES,),
        )
        _, acerto, _, verificacoes = apurar(
            pergunta,
            cobertura_observada="ambas",
            comportamento_observado=COMPORTAMENTO_COMPLETA,
            motivo_observado=MOTIVO_NA,
            bases_publicadas=[BASE_CONTABIL_CONTROLADORES],
            tem_valor_publicado=True,
            resposta_texto="Lucro de R$ 11.306.000.000,00.",
            violacoes=(),
        )
        criterio = next(
            v for v in verificacoes if v.criterio == CRITERIO_AUSENCIA_NOMEADA
        )
        assert criterio.aplicavel is False
        assert acerto is True

    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("não há release no corpus e ela não arquiva na CVM", True),
            ("não está no painel nem tem release indexado", True),
            ("Nenhuma companhia foi identificada na pergunta.", False),
            ("não encontrei nada sobre isso", False),
            ("não há release indexado no corpus documental", False),
        ],
    )
    def test_nomeia_as_duas_camadas(self, texto, esperado):
        assert nomeia_as_duas_camadas(texto) is esperado


# --------------------------------------------------------------------------- #
# RN01 e RN02 verificadas por código sobre a saída
# --------------------------------------------------------------------------- #


class TestRegrasPorCodigo:
    def test_valor_sem_citacao_e_violacao(self):
        resposta = RespostaDeterministica(
            pergunta="?",
            resposta="O lucro foi de R$ 1.000,00 no trimestre.",
        )
        assert VIOLACAO_RN01_SEM_CITACAO in verificar_regras(resposta)

    def test_valor_sem_lastro_no_painel_e_violacao(self, leitor):
        """Número que não corresponde a fato lido é alucinação, por definição."""
        fato = leitor.ler(CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "3T2025")
        resposta = RespostaDeterministica(
            pergunta="?",
            resposta="O lucro foi de R$ 99.999.999,00.",
            fatos=(fato,),
        )
        assert VIOLACAO_RN02_SEM_LASTRO in verificar_regras(resposta)

    def test_valor_com_lastro_e_citacao_passa(self, leitor):
        fato = leitor.ler(CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "3T2025")
        resposta = RespostaDeterministica(
            pergunta="?",
            resposta="O lucro foi de R$ 11.306.000.000,00.",
            fatos=(fato,),
        )
        assert verificar_regras(resposta) == ()

    def test_recusa_que_apresenta_valor_e_violacao(self, leitor):
        fato = leitor.ler(CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "3T2025")
        resposta = RespostaDeterministica(
            pergunta="?",
            resposta="Não posso responder. Mas o lucro foi R$ 11.306.000.000,00.",
            recusa=True,
            fatos=(fato,),
        )
        assert VIOLACAO_RN02_RECUSA_COM_VALOR in verificar_regras(resposta)

    def test_violacao_vira_recusa_registrada_e_preserva_a_original(
        self, config, indice
    ):
        """5.9.5: quem viola RN01 não produz resposta sem citação — produz recusa."""

        class CaixaQueViola:
            registro = ()

            def responder_deterministico(self, pergunta):
                return RespostaDeterministica(
                    pergunta=pergunta,
                    resposta="O lucro do Itaú foi de R$ 11.306.000.000,00.",
                )

        pergunta = pergunta_sintetica(
            "VIOLA",
            "qual o lucro do Itaú no 3T2025?",
            cobertura="ambas",
            comportamento=COMPORTAMENTO_COMPLETA,
            bases=(BASE_CONTABIL_CONTROLADORES,),
        )
        resultado = executar_braco_c(
            [pergunta],
            config,
            indice=indice,
            fabrica_caixa=CaixaQueViola,
            relogio=lambda: 0.0,
        )
        registro = resultado.registros[0]
        assert registro.convertida_em_recusa is True
        assert VIOLACAO_RN01_SEM_CITACAO in registro.violacoes
        assert registro.recusa is True
        assert valores_monetarios(registro.resposta) == ()
        assert "R$ 11.306.000.000,00" in registro.resposta_bruta
        assert registro.motivo_observado == MOTIVO_RECUSA_CONVERTIDA
        assert registro.apuracao == APURACAO_ERRO
        assert CRITERIO_REGRAS in registro.motivo_apuracao

    def test_toda_resposta_do_conjunto_respeita_rn01(self, config, indice, leitor):
        """Invariante sobre a execução inteira: valor publicado, fonte citada."""
        perguntas = [
            pergunta_sintetica(
                f"Q{i}",
                texto,
                cobertura="ambas",
                comportamento=COMPORTAMENTO_COMPLETA,
            )
            for i, texto in enumerate(
                [
                    "qual o lucro líquido do Itaú no 3T2025?",
                    "qual o lucro líquido do Inter no 1T2026?",
                    "E o Nubank?",
                    "Quanto o BTG lucrou no 1T2026?",
                    "qual o patrimônio líquido do Itaú no 3T2025?",
                ]
            )
        ]
        for registro in rodar(perguntas, config, indice, leitor).registros:
            assert registro.violacoes == ()
            if valores_monetarios(registro.resposta):
                assert registro.citacoes
                assert len(registro.citacoes) == len(registro.fatos_publicados)
            else:
                assert registro.fatos_publicados == ()


# --------------------------------------------------------------------------- #
# Custo, latência e contenção
# --------------------------------------------------------------------------- #


class TestCustoLatenciaEContencao:
    def test_nenhuma_chamada_de_llm_e_custo_zero_contabilizado(
        self, config, indice, leitor
    ):
        perguntas = carregar_conjunto_agentes()
        resultado = rodar(perguntas, config, indice, leitor)
        assert len(resultado.registros) == 15
        for registro in resultado.registros:
            assert registro.chamadas_llm == 0
            assert registro.tokens_entrada == registro.tokens_saida == 0
            assert registro.custo_usd == 0.0
            assert registro.veredito_auditor is None
        resumo = resultado.resumo
        assert resumo["custo_usd_total"] == 0.0
        assert resumo["chamadas_llm_total"] == 0
        assert resumo["vereditos_auditor"] == {}

    def test_latencia_e_medida_por_pergunta_fora_da_preparacao(
        self, config, indice, leitor
    ):
        perguntas = [
            pergunta_sintetica(
                "A",
                "E o Nubank?",
                cobertura="nenhuma",
                comportamento=COMPORTAMENTO_RECUSA,
                motivo=MOTIVO_FORA_DO_CORPUS,
            ),
            pergunta_sintetica(
                "B",
                "E o Nubank?",
                cobertura="nenhuma",
                comportamento=COMPORTAMENTO_RECUSA,
                motivo=MOTIVO_FORA_DO_CORPUS,
            ),
        ]
        resultado = rodar(perguntas, config, indice, leitor)
        # Relógio determinístico: cada leitura avança 1 s.
        assert [r.latencia_s for r in resultado.registros] == [1.0, 1.0]
        assert resultado.preparacao_s == 1.0
        assert resultado.resumo["latencia_s_total"] == 2.0
        assert resultado.resumo["latencia_s_media"] == 1.0

    def test_o_orcamento_de_ferramenta_e_por_pergunta(self, config, indice, leitor):
        """5.9.5: teto por consulta. Reusar a caixa estouraria na nona pergunta."""
        config_apertado = Config(agentes_max_chamadas_ferramenta=1)
        perguntas = carregar_conjunto_agentes()
        resultado = rodar(perguntas, config_apertado, indice, leitor)
        assert [r.erro_execucao for r in resultado.registros] == [None] * 15
        assert all(r.total_chamadas_ferramenta == 1 for r in resultado.registros)

    def test_leituras_do_painel_sao_contadas_alem_das_ferramentas(
        self, config, indice, leitor
    ):
        pergunta = pergunta_sintetica(
            "LEITURA",
            "qual o lucro líquido do Inter no 1T2026?",
            cobertura="so_painel",
            comportamento=COMPORTAMENTO_PARCIAL,
            motivo=MOTIVO_FORA_DO_CORPUS,
            bases=(BASE_CONTABIL_CONTROLADORES,),
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        assert registro.total_chamadas_ferramenta == 1
        assert registro.leituras_painel == 1
        assert len(leitor.chamadas) == 1

    def test_leitor_contado_nao_altera_o_que_e_lido(self, leitor):
        contado = LeitorContado(leitor)
        fato = contado.ler(CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "3T2025")
        assert fato is not None and fato.valor_reais == 11_306_000_000.0
        assert contado.ler(CD_ITAU, CONCEITO_LUCRO_CONTROLADORES, "9T9999") is None
        assert contado.leituras == 2

    def test_excecao_em_uma_pergunta_nao_derruba_a_execucao(self, config, indice):
        class CaixaQueEstoura:
            registro = ()

            def responder_deterministico(self, pergunta):
                raise TetoChamadasExcedidoError("teto atingido")

        perguntas = [
            pergunta_sintetica(
                "X",
                "?",
                cobertura="ambas",
                comportamento=COMPORTAMENTO_COMPLETA,
            ),
            pergunta_sintetica(
                "Y",
                "?",
                cobertura="ambas",
                comportamento=COMPORTAMENTO_COMPLETA,
                status=STATUS_PENDENTE_HUMANA,
            ),
        ]
        resultado = executar_braco_c(
            perguntas,
            config,
            indice=indice,
            fabrica_caixa=CaixaQueEstoura,
            relogio=lambda: 0.0,
        )
        assert len(resultado.registros) == 2
        primeiro, segundo = resultado.registros
        assert "TetoChamadasExcedidoError" in primeiro.erro_execucao
        assert primeiro.recusa is True
        assert primeiro.apuracao == APURACAO_ERRO
        # A falha também não pode virar acerto nem erro sobre gabarito pendente.
        assert segundo.apuracao == APURACAO_PENDENTE
        assert resultado.resumo["erros_execucao"] == 2

    def test_nenhuma_ferramenta_proibida_e_chamada(self, config, indice, leitor):
        """RN07: `prever_risco` não existe e não volta sob outro nome."""
        resultado = rodar(carregar_conjunto_agentes(), config, indice, leitor)
        chamadas = {
            chamada["ferramenta"]
            for registro in resultado.registros
            for chamada in registro.chamadas_ferramenta
        }
        assert chamadas == {"verificar_cobertura"}

    def test_registro_recusa_ferramenta_proibida(self):
        with pytest.raises(ValueError, match="RN07"):
            RegistroBraco(
                id_pergunta="X",
                braco=BRACO_C,
                subconjunto="cobertura",
                categoria="factual",
                rota_esperada="triagem_cobertura",
                pergunta="?",
                chamadas_ferramenta=({"ferramenta": "prever_risco"},),
            )


# --------------------------------------------------------------------------- #
# O formato é dos três braços, não do braço C
# --------------------------------------------------------------------------- #


class TestFormatoComumAosTresBracos:
    def test_o_dicionario_tem_exatamente_os_campos_do_contrato(
        self, config, indice, leitor
    ):
        pergunta = pergunta_sintetica(
            "F",
            "E o Nubank?",
            cobertura="nenhuma",
            comportamento=COMPORTAMENTO_RECUSA,
            motivo=MOTIVO_FORA_DO_CORPUS,
        )
        dicionario = rodar([pergunta], config, indice, leitor).registros[0]
        assert tuple(dicionario.como_dicionario()) == CAMPOS_REGISTRO

    def test_os_campos_de_agente_existem_no_formato(self):
        """A e B preenchem o que C zera — mesmo esquema, mesma linha JSONL."""
        for campo in (
            "chamadas_llm",
            "iteracoes",
            "tokens_entrada",
            "tokens_saida",
            "custo_usd",
            "veredito_auditor",
            "total_chamadas_ferramenta",
            "latencia_s",
        ):
            assert campo in CAMPOS_REGISTRO

    def test_o_registro_aceita_os_tres_bracos(self):
        for braco in (BRACO_A, BRACO_B, BRACO_C):
            registro = RegistroBraco(
                id_pergunta="X",
                braco=braco,
                subconjunto="cobertura",
                categoria="factual",
                rota_esperada="triagem_cobertura",
                pergunta="?",
            )
            assert registro.braco == braco
        with pytest.raises(ValueError, match="braço desconhecido"):
            RegistroBraco(
                id_pergunta="X",
                braco="D",
                subconjunto="cobertura",
                categoria="factual",
                rota_esperada="triagem_cobertura",
                pergunta="?",
            )

    def test_veredito_do_auditor_usa_o_vocabulario_de_5_9_1(self):
        registro = RegistroBraco(
            id_pergunta="X",
            braco=BRACO_B,
            subconjunto="cobertura",
            categoria="factual",
            rota_esperada="triagem_cobertura",
            pergunta="?",
            veredito_auditor=VEREDITO_CONTESTA,
        )
        assert resumir((registro,))["vereditos_auditor"] == {VEREDITO_CONTESTA: 1}
        with pytest.raises(ValueError, match="veredito"):
            RegistroBraco(
                id_pergunta="X",
                braco=BRACO_B,
                subconjunto="cobertura",
                categoria="factual",
                rota_esperada="triagem_cobertura",
                pergunta="?",
                veredito_auditor="concordo",
            )

    def test_o_registro_e_serializavel_em_jsonl(self, config, indice, leitor):
        pergunta = pergunta_sintetica(
            "S",
            "qual o lucro líquido do Inter no 1T2026?",
            cobertura="so_painel",
            comportamento=COMPORTAMENTO_PARCIAL,
            motivo=MOTIVO_FORA_DO_CORPUS,
            bases=(BASE_CONTABIL_CONTROLADORES,),
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        linha = json.loads(json.dumps(registro.como_dicionario(), ensure_ascii=False))
        assert linha["braco"] == "C"
        assert linha["verificacoes"][0]["criterio"] == CRITERIO_COBERTURA
        assert linha["fatos_publicados"][0]["cd_cvm"] == CD_INTER

    def test_verificacao_distingue_inaplicavel_de_reprovado(self):
        inaplicavel = Verificacao(
            criterio=CRITERIO_AUSENCIA_NOMEADA, aplicavel=False, passou=True
        )
        reprovada = Verificacao(
            criterio=CRITERIO_COBERTURA, aplicavel=True, passou=False
        )
        resumo = resumir(
            (
                RegistroBraco(
                    id_pergunta="X",
                    braco=BRACO_C,
                    subconjunto="cobertura",
                    categoria="factual",
                    rota_esperada="triagem_cobertura",
                    pergunta="?",
                    verificacoes=(inaplicavel, reprovada),
                ),
            )
        )
        assert resumo["criterios_falhos"] == {CRITERIO_COBERTURA: 1}


class TestPersistencia:
    def test_jsonl_tem_uma_linha_por_pergunta_mais_o_resumo(
        self, config, indice, leitor, tmp_path
    ):
        perguntas = [
            pergunta_sintetica(
                "A",
                "E o Nubank?",
                cobertura="nenhuma",
                comportamento=COMPORTAMENTO_RECUSA,
                motivo=MOTIVO_FORA_DO_CORPUS,
            ),
            pergunta_sintetica(
                "B",
                "qual o lucro líquido do Inter no 1T2026?",
                cobertura="so_painel",
                comportamento=COMPORTAMENTO_PARCIAL,
                motivo=MOTIVO_FORA_DO_CORPUS,
                bases=(BASE_CONTABIL_CONTROLADORES,),
            ),
        ]
        resultado = rodar(perguntas, config, indice, leitor)
        caminho = registrar_resultado(resultado, dir_logs=tmp_path)
        linhas = [
            json.loads(linha)
            for linha in Path(caminho).read_text(encoding="utf-8").splitlines()
        ]
        assert len(linhas) == 3
        assert [l["tipo"] for l in linhas] == [
            "registro_braco",
            "registro_braco",
            "resumo_braco",
        ]
        assert {l["run_id"] for l in linhas} == {resultado.run_id}
        assert all("timestamp_utc" in l for l in linhas)
        assert linhas[-1]["resumo"]["n"] == 2
        assert resultado.run_id in caminho.name

    def test_json_do_resultado_carrega_registros_e_resumo(
        self, config, indice, leitor, tmp_path
    ):
        pergunta = pergunta_sintetica(
            "A",
            "E o Nubank?",
            cobertura="nenhuma",
            comportamento=COMPORTAMENTO_RECUSA,
            motivo=MOTIVO_FORA_DO_CORPUS,
        )
        resultado = rodar([pergunta], config, indice, leitor)
        destino = salvar_resultado(resultado, tmp_path / "braco_c.json")
        conteudo = json.loads(destino.read_text(encoding="utf-8"))
        assert conteudo["braco"] == "C"
        assert conteudo["resumo"]["n"] == 1
        assert len(conteudo["registros"]) == 1


# --------------------------------------------------------------------------- #
# Leituras da saída — funções puras
# --------------------------------------------------------------------------- #


class TestLeiturasDaSaida:
    @pytest.mark.parametrize(
        "kwargs,esperado",
        [
            ({"precisa_desambiguacao": True}, COMPORTAMENTO_DESAMBIGUACAO),
            ({"recusa": True}, COMPORTAMENTO_RECUSA),
            ({"parcial": True}, COMPORTAMENTO_PARCIAL),
            ({}, COMPORTAMENTO_COMPLETA),
            # Desambiguar não é recusar (RN11).
            (
                {"precisa_desambiguacao": True, "recusa": True},
                COMPORTAMENTO_DESAMBIGUACAO,
            ),
        ],
    )
    def test_comportamento_observado(self, kwargs, esperado):
        resposta = RespostaDeterministica(pergunta="?", resposta="", **kwargs)
        assert comportamento_de(resposta) == esperado

    def test_desambiguacao_domina_o_estado_de_cobertura(self, config, indice, leitor):
        """A resposta publicada é a pergunta, e nada mais foi respondido."""
        pergunta = pergunta_sintetica(
            "MISTA",
            "compare o BTG e o Inter no 1T2026",
            cobertura=COBERTURA_AMBIGUA,
            comportamento=COMPORTAMENTO_DESAMBIGUACAO,
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        assert registro.cobertura_observada == COBERTURA_AMBIGUA
        assert registro.fatos_publicados == ()

    def test_sem_entidade_o_estado_e_nenhuma(self):
        resposta = RespostaDeterministica(
            pergunta="?", resposta="não identifiquei companhia", recusa=True
        )
        assert cobertura_de(resposta) == "nenhuma"

    def test_motivo_observado_le_o_diagnostico_de_quem_nao_recusou(
        self, config, indice, leitor
    ):
        """`so_painel` não recusa e ainda assim diagnostica `fora_do_corpus`."""
        pergunta = pergunta_sintetica(
            "DIAG",
            "qual o lucro líquido do Inter no 1T2026?",
            cobertura="so_painel",
            comportamento=COMPORTAMENTO_PARCIAL,
            motivo=MOTIVO_FORA_DO_CORPUS,
            bases=(BASE_CONTABIL_CONTROLADORES,),
        )
        registro = rodar([pergunta], config, indice, leitor).registros[0]
        assert registro.recusa is False
        assert registro.motivo_observado == MOTIVO_FORA_DO_CORPUS

    def test_motivo_de_recusa_convertida_nunca_casa_com_o_esperado(self):
        resposta = RespostaDeterministica(
            pergunta="?",
            resposta="recusa registrada",
            recusa=True,
            motivo_recusa=MOTIVO_RECUSA_CONVERTIDA,
        )
        assert motivo_de(resposta) == MOTIVO_RECUSA_CONVERTIDA
        assert MOTIVO_RECUSA_CONVERTIDA not in {
            MOTIVO_NA,
            MOTIVO_FORA_DO_CORPUS,
            MOTIVO_PERIODO_AUSENTE,
        }

    @pytest.mark.parametrize(
        "conceito,esperado",
        [
            (CONCEITO_LUCRO_CONTROLADORES, BASE_CONTABIL_CONTROLADORES),
            (CONCEITO_LUCRO_CONSOLIDADO, BASE_CONTABIL_CONSOLIDADO),
            (CONCEITO_PATRIMONIO_LIQUIDO, BASE_CONTABIL_CONSOLIDADO),
            (CONCEITO_ATIVO_TOTAL, BASE_CONTABIL_CONSOLIDADO),
        ],
    )
    def test_base_do_conceito(self, conceito, esperado):
        assert base_do_conceito(conceito) == esperado

    def test_o_braco_c_nunca_publica_base_gerencial(self, config, indice, leitor):
        """Gerencial só existe no release, e o braço C não lê release."""
        resultado = rodar(carregar_conjunto_agentes(), config, indice, leitor)
        publicadas = {
            base for r in resultado.registros for base in r.bases_publicadas
        }
        assert BASE_GERENCIAL not in publicadas

    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("R$ 1.000,00", ("R$ 1.000,00",)),
            ("de R$ 11.306.000.000,00 no 3T2025", ("R$ 11.306.000.000,00",)),
            ("R$ -1.234,50", ("R$ -1.234,50",)),
            ("o CD_CVM 080217 no 1T2026", ()),
            ("", ()),
        ],
    )
    def test_valores_monetarios(self, texto, esperado):
        assert valores_monetarios(texto) == esperado


# --------------------------------------------------------------------------- #
# "Sem LLM" é propriedade estrutural, não promessa
# --------------------------------------------------------------------------- #


class TestSemLLM:
    def test_o_modulo_nao_importa_nenhum_cliente_de_modelo(self):
        """O piso não pode chamar modelo — nem por descuido de import.

        Checagem sintática sobre o próprio arquivo: se alguém acrescentar um
        cliente de LLM ao braço C, o experimento perde o piso e este teste é o
        que avisa.
        """
        import src.braco_determinista as modulo

        fonte = Path(modulo.__file__).read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        importados: set[str] = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                importados.update(alias.name for alias in no.names)
            elif isinstance(no, ast.ImportFrom) and no.module:
                importados.add(no.module)
        proibidos = {
            "openai",
            "google",
            "anthropic",
            "crewai",
            "src.geracao",
            "src.ollama",
        }
        assert importados & proibidos == set()
