"""Respostas legíveis (revisão de UX de 24/10, itens 8, 9, 10 e 12).

- 8: os agentes misturavam "R$ 11.600.000.000,00" e "R$ 31.382 milhões" na
  frase que compara os dois.
- 9: "lucro do Inter" dava R$ 336,35 milhões no painel (controladores) e
  R$ 356,0 milhões nos agentes (consolidado).
- 10: a resposta prospectiva vinha numa parede de texto, com "trimestre
  corrente" para um trimestre anterior ao último do painel.
- 12: trimestres em ordem de texto ("1T2025, 1T2026, 2T2025") e o botão
  "Deploy" do Streamlit à vista de quem usa o app.

As contraprovas travam o que a correção não pode custar: o valor exato some, a
escala é aplicada duas vezes, a pergunta qualificada recebe o que não pediu, e
o contexto do modelo sai da tela em vez de só mudar de lugar.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

import app_streamlit as app
from src.cobertura import FatoEstruturado, RespostaDeterministica, redigir_conversacional
from src.mapa_contas import (
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_PATRIMONIO_LIQUIDO,
)
from src.projecao import responder_projecao
from tests.test_projecao import _panorama

RAIZ = Path(__file__).resolve().parent.parent
CD_INTER = "080217"


class TestValoresLegiveis:
    def test_valor_com_todos_os_digitos_ganha_a_escala(self):
        assert app.valores_legiveis("lucro de R$ 11.600.000.000,00.") == (
            "lucro de R$ 11,60 bilhões (R$ 11.600.000.000,00)."
        )

    def test_prejuizo_mantem_o_sinal(self):
        assert app.valores_legiveis("R$ -1.234.567.890,00") == (
            "-R$ 1,23 bilhão (R$ -1.234.567.890,00)"
        )

    @pytest.mark.parametrize(
        "texto",
        [
            "margem de R$ 31.382 milhões",
            "R$ 6,02 bilhões (R$ 6.015.079.000,00)",
            "abaixo de um milhão: R$ 999.999,00",
            "sem valor nenhum",
        ],
    )
    def test_contraprova_o_resto_fica_como_esta(self, texto):
        assert app.valores_legiveis(texto) == texto


class _Leitor:
    def __init__(self, fatos):
        self.fatos = {(f.cd_cvm, f.conceito, f.trimestre): f for f in fatos}

    def ler(self, cd_cvm, conceito, trimestre):
        return self.fatos.get((cd_cvm, conceito, trimestre))


def _fato(conceito, valor, trimestre="3T2025"):
    return FatoEstruturado(
        cd_cvm=CD_INTER,
        denom_social="INTER & CO, INC.",
        trimestre=trimestre,
        conceito=conceito,
        valor_reais=valor,
    )


CONTROLADORES = _fato(CONCEITO_LUCRO_CONTROLADORES, 336_345_000.0)
CONSOLIDADO = _fato(CONCEITO_LUCRO_CONSOLIDADO, 356_005_000.0)


def _resposta(*fatos):
    return RespostaDeterministica(pergunta="", resposta="", fatos=tuple(fatos))


class TestLucroNasDuasBases:
    def test_lucro_sem_qualificador_traz_as_duas_bases_citadas(self):
        resposta = app._lucro_nas_duas_bases(
            _resposta(CONTROLADORES),
            "Qual foi o lucro do Banco Inter no 3T2025?",
            _Leitor([CONTROLADORES, CONSOLIDADO]),
        )
        assert resposta.fatos == (CONTROLADORES, CONSOLIDADO)
        assert len(resposta.citacoes) == 2
        assert "lucro líquido consolidado" in resposta.citacoes[1]

    @pytest.mark.parametrize(
        "pergunta",
        [
            "Qual o lucro líquido atribuído aos controladores do Inter no 3T2025?",
            "Qual o lucro consolidado do Inter no 3T2025?",
            "Lucro dos sócios controladores do Inter no 3T2025",
        ],
    )
    def test_contraprova_pergunta_qualificada_recebe_so_o_que_pediu(self, pergunta):
        resposta = _resposta(CONTROLADORES)
        assert app._lucro_nas_duas_bases(
            resposta, pergunta, _Leitor([CONTROLADORES, CONSOLIDADO])
        ) is resposta

    def test_contraprova_outro_conceito_nao_ganha_lucro(self):
        patrimonio = _fato(CONCEITO_PATRIMONIO_LIQUIDO, 10_000_000_000.0)
        resposta = _resposta(patrimonio)
        assert app._lucro_nas_duas_bases(
            resposta, "patrimônio do Inter no 3T2025", _Leitor([CONSOLIDADO])
        ) is resposta

    def test_contraprova_sem_consolidado_no_painel_nada_se_inventa(self):
        resposta = app._lucro_nas_duas_bases(
            _resposta(CONTROLADORES), "lucro do Inter no 3T2025", _Leitor([CONTROLADORES])
        )
        assert resposta.fatos == (CONTROLADORES,)


class TestOrdemDeCalendario:
    def test_serie_sai_em_ordem_de_calendario(self):
        fatos = [
            _fato(CONCEITO_LUCRO_CONTROLADORES, 1e9, "2T2026"),
            _fato(CONCEITO_LUCRO_CONTROLADORES, 2e9, "1T2026"),
            _fato(CONCEITO_LUCRO_CONTROLADORES, 3e9, "2T2025"),
        ]
        texto = redigir_conversacional(_resposta(*fatos), "lucro do Inter em 3T2025 e 4T2025")
        assert texto.index("2T2025") < texto.index("1T2026") < texto.index("2T2026")


@pytest.fixture
def painel():
    if app.carregar_rota_estruturada() is None:
        pytest.skip("painel contábil da CVM não construído nesta instância")


@pytest.mark.usefixtures("painel")
class TestNaRotaDoPainel:
    def test_inter_sai_nas_duas_bases(self):
        item = app.responder_estruturada_se_couber("Qual foi o lucro do Banco Inter no 3T2025?")
        conceitos = [f["conceito"] for f in item["fatos"]]
        assert len(conceitos) == 2 and len(item["citacoes"]) == 2
        assert "R$ 336,35 milhões" in item["resposta"]
        assert "R$ 356,00 milhões" in item["resposta"]

    def test_contraprova_consolidado_pedido_vem_sozinho(self):
        item = app.responder_estruturada_se_couber(
            "Qual o lucro líquido consolidado do Banco do Brasil no 4T2025?"
        )
        assert len(item["fatos"]) == 1

    def test_periodo_pedido_de_volta_em_ordem_de_calendario(self):
        item = app.responder_estruturada_se_couber("lucro do itau")
        assert "1T2025, 2T2025, 3T2025, 4T2025, 1T2026" in item["resposta"]


class TestRespostaProspectiva:
    def _resposta(self):
        return responder_projecao(
            "O Itaú terá prejuízo nos próximos trimestres?",
            denom_social="ITAU UNIBANCO HOLDING S.A.",
            cd_cvm="019348",
            trimestres_painel=("1T2025", "2T2025"),
            n_prejuizos=0,
            panorama=_panorama(),
        )

    def test_secoes_reproduzem_o_texto_inteiro(self):
        """Separar não pode perder bloco: as seções juntas são o texto."""
        resposta = self._resposta()
        assert "\n\n".join(t for _, t in resposta.secoes) == resposta.texto
        assert tuple(n for n, _ in resposta.secoes) == resposta.blocos

    def test_rotulos_dizem_que_trimestre_e_cada_um(self):
        texto = self._resposta().texto
        assert "último trimestre com resultado conhecido" in texto
        assert "Trimestre corrente" not in texto

    def test_a_tela_separa_resposta_e_contexto(self):
        saida = self._resposta()
        principal = [t for n, t in saida.secoes if n not in app.CONTEXTO_DA_PROJECAO]
        contexto = [t for n, t in saida.secoes if n in app.CONTEXTO_DA_PROJECAO]
        assert principal and contexto
        assert "Não projeto resultado" in principal[0]
        assert any("Regime de risco por porte" in t for t in contexto)

    @pytest.mark.usefixtures("painel")
    def test_item_da_rota_leva_o_contexto_no_complemento(self):
        item = app.responder_prospectiva_se_couber(
            "O lucro do Itaú vai cair no próximo trimestre?"
        )
        if item is None or not item.get("complemento"):
            pytest.skip("panorama do modelo não disponível nesta instância")
        assert "Histórico arquivado" in item["resposta"]
        assert "Regime de risco por porte" not in item["resposta"]
        assert "Regime de risco por porte" in item["complemento"]


class TestBarraDeFerramentas:
    def test_quem_usa_o_app_nao_ve_o_deploy(self):
        config = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text())
        assert config["client"]["toolbarMode"] == "viewer"
