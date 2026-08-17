"""Contrato dos braços A e B — contenção, RN01/RN02 por código e RN07.

Nenhum teste aqui toca rede, LLM real, DuckDB ou índice: o provedor e a caixa de
ferramentas são duplos. O que estes testes protegem, em ordem de importância:

1. **RN07 é guarda ativa, não ausência.** `prever_risco` não existe na caixa e
   não entra por fábrica, por nome alternativo nem por lista de ferramentas.
2. **RN01/RN02 são verificadas por código sobre o JSON de saída.** Valor sem
   citação, citação que nenhuma ferramenta devolveu, número sem lastro e recusa
   com valor viram **recusa registrada** — nunca resposta publicada.
3. **Os tetos contêm.** Iteração e chamada de ferramenta param o laço, e a
   resposta sai marcada como parcial em vez de o processo seguir pagando token.
4. **O registro é o dos três braços.** `CAMPOS_REGISTRO` é o contrato de
   comparabilidade linha a linha; o braço A grava `veredito_auditor` nulo e o B
   grava um dos três vereditos.
5. **Contestação não elege vencedor** e **não reprodução vira parcial** (5.9.5).

O isolamento de contexto tem arquivo próprio: `tests/test_isolamento.py`.
"""

from __future__ import annotations

import json

import pytest
from crewai.llms.base_llm import BaseLLM

from src import agentes
from src.agentes import (
    CLASSES_DE_FERRAMENTA,
    PAPEL_AGENTE_UNICO,
    PAPEL_AUDITOR,
    PAPEL_INVESTIGADOR,
    ChamadaFerramenta,
    ControleOrcamento,
    FerramentasDoAgente,
    LLMComTetoRigido,
    LLMPonte,
    OrcamentoAgentesExcedidoError,
    TetoIteracoesExcedidoError,
    SaidaInvestigador,
    UsoAgente,
    VEREDITO_CONFIRMA,
    VEREDITO_CONTESTA,
    VEREDITO_NAO_REPRODUZ,
    VIOLACAO_RN01_CITACAO_SEM_LASTRO,
    VIOLACAO_RN01_SEM_CITACAO,
    VIOLACAO_RN02_RECUSA_COM_VALOR,
    VIOLACAO_RN02_SEM_LASTRO,
    VIOLACAO_SAIDA_ILEGIVEL,
    construir_ferramentas,
    extrair_json,
    responder_braco_a,
    responder_braco_b,
    valores_monetarios_do_texto,
    verificar_regras_agente,
)
from src.braco_agente import (
    ORQUESTRADORES,
    executar_braco_agente,
    montar_registro,
    resumo_com_isolamento,
)
from src.braco_determinista import (
    APURACAO_PENDENTE,
    BRACO_A,
    BRACO_B,
    CAMPOS_REGISTRO,
    STATUS_VERIFICADO,
    PerguntaAgentes,
)
from src.config import Config
from src.ferramentas import (
    FERRAMENTAS_DISPONIVEIS,
    FERRAMENTAS_PROIBIDAS,
    RegistroChamada,
    TetoChamadasExcedidoError,
)
from src.geracao import RespostaBrutaLLM, UsoLLM

PERGUNTA = "E o Inter? Quanto ele lucrou no primeiro trimestre de 2026?"
CITACAO = "CVM · INTER & CO, INC. (CD_CVM 080217) · 1T2026 · lucro_liquido_consolidado"


# --------------------------------------------------------------------------- #
# Duplos
# --------------------------------------------------------------------------- #


class LLMRoteirizado(BaseLLM):
    """Provedor falso com respostas roteirizadas, contando uso."""

    def __init__(self, respostas: list[str], papel: str = PAPEL_INVESTIGADOR) -> None:
        super().__init__(model="roteiro", temperature=0.0)
        self.respostas = list(respostas)
        self.papel = papel
        self.chamadas = 0
        self.uso = UsoAgente()

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return False

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
    ) -> str:
        resposta = self.respostas[min(self.chamadas, len(self.respostas) - 1)]
        self.chamadas += 1
        self.uso.chamadas_llm += 1
        self.uso.tokens_entrada += 50
        self.uso.tokens_saida += 20
        self.uso.custo_usd += 0.00001
        return resposta


class CaixaFalsa:
    """Duplo da caixa de ferramentas, com teto de chamadas configurável."""

    def __init__(self, max_chamadas: int = 8) -> None:
        self.registro: list[RegistroChamada] = []
        self.max_chamadas = max_chamadas

    def _reservar(self, ferramenta: str, resumo: str) -> None:
        if len(self.registro) >= self.max_chamadas:
            raise TetoChamadasExcedidoError(
                f"teto de {self.max_chamadas} chamadas de ferramenta atingido"
            )
        self.registro.append(
            RegistroChamada(ferramenta=ferramenta, argumentos={}, resumo=resumo)
        )

    def verificar_cobertura(self, entidade: str, trimestre=None) -> dict:
        self._reservar("verificar_cobertura", "1 entidade: so_painel")
        return {
            "consulta": entidade,
            "entidades": [
                {
                    "termo": entidade,
                    "cobertura": {
                        "estado": "so_painel",
                        "cd_cvm": "080217",
                        "denom_social": "INTER & CO, INC.",
                        "trimestre": "1T2026",
                        "trimestres_painel": ["1T2026"],
                        "trimestres_corpus": [],
                    },
                }
            ],
            "desambiguacao": [],
        }

    def consultar_cvm(self, sql: str) -> dict:
        self._reservar("consultar_cvm", "1 linha(s)")
        return {
            "sql": sql,
            "colunas": ["cd_cvm", "trimestre", "conceito", "valor_reais"],
            "linhas": [["080217", "1T2026", "lucro_liquido_consolidado", 417547000.0]],
            "total_linhas": 1,
        }

    def buscar_trechos(self, pergunta: str, top_k=None) -> list:
        self._reservar("buscar_trechos", "1 trecho(s)")
        return [
            {
                "id": "inter#1",
                "empresa": "INTER",
                "documento": "inter_release_1T2026",
                "trimestre": "1T2026",
                "pagina_inicio": 3,
                "pagina_fim": 3,
                "texto": "lucro líquido gerencial de R$ 430,0 milhões no 1T26",
                "score": 0.8,
                "origem": "semantica",
            }
        ]

    def calcular_indicadores(self, cd_cvm: str, trimestre=None) -> dict:
        self._reservar("calcular_indicadores", "1 trimestre(s)")
        return {"cd_cvm": cd_cvm, "indicadores": [{"roe": 0.14}]}


def final(objeto: dict) -> str:
    return "Thought: pronto\nFinal Answer: " + json.dumps(objeto, ensure_ascii=False)


def saida_valida(**alteracoes) -> dict:
    base = {
        "cobertura": "so_painel",
        "comportamento": "resposta_parcial_marcada",
        "motivo_recusa": "fora_do_corpus",
        "bases": ["contabil_consolidado"],
        "afirmacao": (
            "O lucro consolidado do INTER & CO, INC. (CD_CVM 080217) no 1T2026 "
            "foi de R$ 417,5 milhões. Não há release indexado no corpus."
        ),
        "citacoes": [CITACAO],
        "rastro": ["passo 1: verifiquei a cobertura antes de consultar o valor"],
    }
    base.update(alteracoes)
    return base


ACAO_COBERTURA = (
    'Thought: cobertura primeiro\nAction: verificar_cobertura\n'
    'Action Input: {"entidade": "Inter"}'
)
ACAO_SQL = (
    'Thought: o número\nAction: consultar_cvm\nAction Input: '
    '{"sql": "SELECT valor_reais FROM fatos_semanticos LIMIT 1"}'
)


def montar_fabricas(respostas_investigador, respostas_auditor=None, *, caixa=None):
    """Fábricas injetáveis; devolve também o que foi criado, para inspeção."""
    criados: dict[str, object] = {}

    def fabrica_llm(papel: str) -> LLMRoteirizado:
        respostas = (
            respostas_auditor
            if papel == PAPEL_AUDITOR and respostas_auditor is not None
            else respostas_investigador
        )
        llm = LLMRoteirizado(list(respostas), papel)
        criados[f"llm_{papel}"] = llm
        return llm

    def fabrica_ferramentas(papel: str) -> FerramentasDoAgente:
        ferramentas = FerramentasDoAgente(caixa or CaixaFalsa(), papel)
        criados[f"ferr_{papel}"] = ferramentas
        return ferramentas

    return fabrica_llm, fabrica_ferramentas, criados


@pytest.fixture
def config() -> Config:
    return Config()


# --------------------------------------------------------------------------- #
# RN07 — o modelo preditivo não é ferramenta de agente
# --------------------------------------------------------------------------- #


class TestRN07:
    def test_prever_risco_nao_existe_na_caixa_do_agente(self):
        assert "prever_risco" in FERRAMENTAS_PROIBIDAS
        assert "prever_risco" not in FERRAMENTAS_DISPONIVEIS
        assert "prever_risco" not in CLASSES_DE_FERRAMENTA

    def test_fabrica_recusa_montar_ferramenta_proibida(self):
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_INVESTIGADOR)
        with pytest.raises(ValueError, match="RN07"):
            construir_ferramentas(ferramentas, ("prever_risco",))

    def test_executor_recusa_chamar_ferramenta_proibida(self):
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_INVESTIGADOR)
        with pytest.raises(Exception, match="RN07"):
            ferramentas.executar("prever_risco", cd_cvm="019348")

    def test_o_agente_so_recebe_as_quatro_ferramentas(self):
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_INVESTIGADOR)
        nomes = [f.name for f in construir_ferramentas(ferramentas)]
        assert nomes == list(FERRAMENTAS_DISPONIVEIS)
        assert not set(nomes) & set(FERRAMENTAS_PROIBIDAS)

    def test_nome_desconhecido_nao_vira_ferramenta(self):
        """Reintroduzir o modelo preditivo com outro nome também não passa."""
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_INVESTIGADOR)
        with pytest.raises(ValueError, match="sem implementação"):
            construir_ferramentas(ferramentas, ("estimar_risco_futuro",))


# --------------------------------------------------------------------------- #
# RN01 / RN02 verificadas por código sobre o JSON de saída (5.9.5)
# --------------------------------------------------------------------------- #


class TestRegrasPorCodigo:
    def test_saida_valida_nao_gera_violacao(self, config):
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert resposta.violacoes == ()
        assert resposta.convertida_em_recusa is False
        assert resposta.recusa is False
        assert "R$ 417,5 milhões" in resposta.resposta

    def test_valor_sem_citacao_vira_recusa_registrada(self, config):
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida(citacoes=[]))]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert VIOLACAO_RN01_SEM_CITACAO in resposta.violacoes
        assert resposta.recusa is True
        assert resposta.convertida_em_recusa is True
        assert resposta.citacoes == ()
        # A saída original é preservada para auditoria, não apagada.
        assert "417" in resposta.resposta_bruta

    def test_citacao_que_nenhuma_ferramenta_devolveu_vira_recusa(self, config):
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [
                ACAO_COBERTURA,
                ACAO_SQL,
                final(
                    saida_valida(
                        citacoes=["Relatório Anual do Banco Zeta 2029, página 3"]
                    )
                ),
            ]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert VIOLACAO_RN01_CITACAO_SEM_LASTRO in resposta.violacoes
        assert resposta.recusa is True

    def test_numero_sem_lastro_vira_recusa(self, config):
        """RN02: valor que nenhuma ferramenta devolveu é alucinação."""
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [
                ACAO_COBERTURA,
                ACAO_SQL,
                final(
                    saida_valida(
                        afirmacao=(
                            "O lucro do INTER & CO, INC. (CD_CVM 080217) no "
                            "1T2026 foi de R$ 987,6 milhões."
                        )
                    )
                ),
            ]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert VIOLACAO_RN02_SEM_LASTRO in resposta.violacoes
        assert resposta.recusa is True

    def test_valor_do_release_recuperado_tem_lastro(self, config):
        """O número do release está no trecho — e o trecho é evidência."""
        acao_trechos = (
            'Thought: preciso do release\nAction: buscar_trechos\n'
            'Action Input: {"pergunta": "lucro gerencial do Inter"}'
        )
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [
                acao_trechos,
                final(
                    saida_valida(
                        afirmacao=(
                            "O release do INTER & CO, INC. (CD_CVM 080217) "
                            "destaca lucro gerencial de R$ 430,0 milhões no "
                            "1T2026."
                        ),
                        citacoes=["inter_release_1T2026 · INTER · 1T2026 · p. 3"],
                        bases=["gerencial"],
                    )
                ),
            ]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert resposta.violacoes == ()

    def test_recusa_que_apresenta_valor_e_violacao(self):
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_INVESTIGADOR)
        ferramentas.executar("consultar_cvm", sql="SELECT 1")
        saida = SaidaInvestigador(
            pergunta=PERGUNTA,
            afirmacao="Não posso responder. Mas o lucro foi de R$ 417,5 milhões.",
            citacoes=(CITACAO,),
            comportamento="recusa",
        )
        violacoes = verificar_regras_agente(saida, ferramentas)
        assert VIOLACAO_RN02_RECUSA_COM_VALOR in violacoes

    def test_saida_fora_do_contrato_json_vira_recusa(self, config):
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [
                ACAO_COBERTURA,
                "Thought: pronto\nFinal Answer: o lucro foi de uns R$ 417,5 milhões",
            ]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert VIOLACAO_SAIDA_ILEGIVEL in resposta.violacoes
        assert resposta.recusa is True

    def test_o_braco_b_nao_paga_auditoria_de_resposta_descartada(self, config):
        """Auditar o que o código já descartou seria chamada jogada fora."""
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida(citacoes=[]))],
            respostas_auditor=[final({"veredito": "confirma"})],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert resposta.convertida_em_recusa is True
        assert resposta.veredito_auditor is None
        assert f"llm_{PAPEL_AUDITOR}" not in criados

    def test_extracao_de_json_tolera_cerca_de_codigo(self):
        objeto = extrair_json('```json\n{"veredito": "confirma"}\n```')
        assert objeto == {"veredito": "confirma"}
        assert extrair_json("sem json aqui") is None

    def test_valores_monetarios_ignoram_percentual_e_data(self):
        valores = valores_monetarios_do_texto(
            "no 1T2026 o lucro caiu 22,8% e ficou em R$ 417,5 milhões"
        )
        assert valores == (417_500_000.0,)


# --------------------------------------------------------------------------- #
# Gate de correção de dado — o segundo tiro antes da recusa (5.9.5)
# --------------------------------------------------------------------------- #


def recusa_valida(**alteracoes) -> dict:
    """Uma recusa legítima: sem valor, sem base — a cobertura já a sustenta."""
    base = {
        "cobertura": "nenhuma",
        "comportamento": "recusa",
        "motivo_recusa": "fora_do_corpus",
        "bases": [],
        "afirmacao": (
            "Não encontrei essa companhia nem no painel da CVM nem no corpus de "
            "releases indexados."
        ),
        "citacoes": [],
        "rastro": ["passo 1: triagem de cobertura"],
    }
    base.update(alteracoes)
    return base


class TestGateDeCorrecaoDeDado:
    """O achado do braço A: publicar dado tendo chamado só `verificar_cobertura`.

    `verificar_cobertura` **não devolve valor nenhum** — ela só diz em que camada
    a companhia existe. Uma saída com número, base ou citação apoiada apenas
    nela é resposta de memória paramétrica. RN01/RN02 já a descartavam, e o
    usuário nunca viu nada errado; o problema era de medição: a rede de
    segurança fazia o trabalho da disciplina do agente, e A, B e C empatavam
    porque nenhum braço com LLM chegava a usar as ferramentas de dado.

    O gate dá **um** segundo tiro antes da recusa. Um só, dentro do mesmo teto,
    com a chamada extra na contabilidade normal.
    """

    def test_valor_sem_consulta_de_dado_dispara_uma_reexecucao_corretiva(
        self, config
    ):
        """O caso central: cobertura → resposta com número, sem consultar nada."""
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [
                ACAO_COBERTURA,            # 1ª passagem: só a triagem
                final(saida_valida()),     # ...e já responde com R$ 417,5 mi
                ACAO_SQL,                  # rodada corretiva: consulta o painel
                final(saida_valida()),     # ...e responde de novo
            ]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert resposta.correcao_aplicada is True
        assert resposta.correcao_resultado == agentes.CORRECAO_BEM_SUCEDIDA
        # A correção resolveu: nada foi descartado e a resposta é publicada.
        assert resposta.convertida_em_recusa is False
        assert resposta.violacoes == ()
        assert resposta.recusa is False
        assert "R$ 417,5 milhões" in resposta.resposta
        # E o painel foi de fato consultado, não apenas prometido.
        assert "consultar_cvm" in {c.ferramenta for c in resposta.chamadas}

    def test_a_correcao_e_uma_so_e_a_segunda_falha_vira_recusa_registrada(
        self, config
    ):
        """Segundo tiro, nunca um terceiro: falhou de novo, é recusa."""
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            # O roteiro repete a última resposta indefinidamente: se o gate
            # laçasse, este teste nunca terminaria de gastar chamadas.
            [ACAO_COBERTURA, final(saida_valida())]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        llm = criados[f"llm_{PAPEL_AGENTE_UNICO}"]
        assert resposta.correcao_aplicada is True
        assert resposta.correcao_resultado == agentes.CORRECAO_FALHOU
        # Exatamente uma rodada corretiva: 2 chamadas na primeira passagem + 1
        # na segunda (que já responde direto). Nunca uma terceira passagem.
        assert llm.chamadas == 3
        # E o desfecho é o de sempre — a rede de RN01/RN02 continua no lugar.
        assert resposta.convertida_em_recusa is True
        assert resposta.recusa is True
        assert VIOLACAO_RN02_SEM_LASTRO in resposta.violacoes

    def test_quem_consultou_o_dado_nao_gasta_rodada_corretiva(self, config):
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        llm = criados[f"llm_{PAPEL_AGENTE_UNICO}"]
        assert resposta.correcao_aplicada is False
        assert resposta.correcao_resultado == agentes.CORRECAO_NAO_NECESSARIA
        assert llm.chamadas == 3

    def test_recusa_sem_valor_nao_gasta_rodada_corretiva(self, config):
        """Recusar depois da triagem é o comportamento **correto** (RN12).

        Cobrar uma consulta de dado aqui gastaria uma chamada para confirmar
        uma ausência que a triagem já estabeleceu.
        """
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, final(recusa_valida())]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        llm = criados[f"llm_{PAPEL_AGENTE_UNICO}"]
        assert resposta.correcao_aplicada is False
        assert llm.chamadas == 2
        assert resposta.recusa is True

    def test_a_rodada_corretiva_aparece_na_contabilidade(self, config):
        """Nada de custo invisível: a chamada extra entra em uso e custo."""
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, final(saida_valida()), ACAO_SQL, final(saida_valida())]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        llm = criados[f"llm_{PAPEL_AGENTE_UNICO}"]
        assert llm.chamadas == 4
        assert resposta.uso.chamadas_llm == 4
        assert resposta.uso.custo_usd == pytest.approx(4 * 0.00001)
        assert resposta.uso.tokens_entrada == 4 * 50
        registro = montar_registro(pergunta_sintetica(), BRACO_A, resposta, 1.0)
        assert registro.chamadas_llm == 4
        assert registro.custo_usd == pytest.approx(4 * 0.00001)

    def test_a_rodada_corretiva_divide_o_teto_e_nao_ganha_orcamento_extra(self):
        """O segundo tiro cabe no mesmo `agentes_max_iteracoes`, ou é cortado."""
        config = Config(agentes_max_iteracoes=2)  # teto rígido = 3 chamadas
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [
                ACAO_COBERTURA,          # 1
                final(saida_valida()),   # 2 → dispara o gate
                ACAO_COBERTURA,          # 3 → corretiva ainda sem consultar dado
                ACAO_SQL,                # 4 → NUNCA acontece: teto rígido corta
            ]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        llm = criados[f"llm_{PAPEL_AGENTE_UNICO}"]
        assert llm.chamadas == 3
        assert resposta.correcao_resultado == agentes.CORRECAO_CORTADA_POR_TETO
        assert resposta.parcial_por_teto is True
        # Cortada a correção, o desfecho volta a ser o de sempre.
        assert resposta.recusa is True
        assert VIOLACAO_RN02_SEM_LASTRO in resposta.violacoes

    def test_sem_orcamento_o_gate_nao_tenta_corrigir(self):
        """Teto já atingido: não há segundo tiro sem munição.

        A resposta correta nesse estado é a parcial marcada de 5.9.5 — o sistema
        parou de procurar por decisão de contenção. Gastar uma rodada corretiva
        aqui seria abrir o laço que a contenção acabou de fechar.
        """
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_AGENTE_UNICO)
        ferramentas.executar("verificar_cobertura", entidade="Inter")
        base = dict(
            pergunta=PERGUNTA,
            afirmacao="o lucro foi de R$ 417,5 milhões",
            citacoes=(CITACAO,),
            bases=("contabil_consolidado",),
            comportamento="resposta_completa",
        )
        assert agentes.precisa_correcao_de_dado(
            SaidaInvestigador(**base), ferramentas
        ) is True
        assert agentes.precisa_correcao_de_dado(
            SaidaInvestigador(**base, teto_iteracoes=True), ferramentas
        ) is False
        assert agentes.precisa_correcao_de_dado(
            SaidaInvestigador(**base, teto_ferramenta=True), ferramentas
        ) is False

    def test_primeira_passagem_cortada_pelo_teto_nao_tenta_corrigir(self):
        """Ponta a ponta: cortada a 1ª passagem, a saída é parcial, não recusa."""
        config = Config(agentes_max_iteracoes=1)  # teto rígido = 2 chamadas
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, final(saida_valida())]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        llm = criados[f"llm_{PAPEL_AGENTE_UNICO}"]
        assert llm.chamadas == 2
        assert resposta.correcao_aplicada is False
        assert resposta.parcial_por_teto is True
        assert resposta.recusa is False
        assert resposta.comportamento == "resposta_parcial_marcada"

    def test_gate_ignora_chamada_de_dado_que_falhou(self, config):
        """Consulta recusada pela guarda da RN04 não devolveu valor algum."""
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_AGENTE_UNICO)
        ferramentas.registrar_falha(
            "consultar_cvm", {"sql": "DROP TABLE x"}, "ErroFerramenta: DDL bloqueado"
        )
        assert agentes.consultou_ferramenta_de_dado(ferramentas) is False
        saida = SaidaInvestigador(
            pergunta=PERGUNTA,
            afirmacao="o lucro foi de R$ 417,5 milhões",
            citacoes=(CITACAO,),
            bases=("contabil_consolidado",),
            comportamento="resposta_completa",
        )
        assert agentes.precisa_correcao_de_dado(saida, ferramentas) is True

    def test_verificar_cobertura_sozinho_nunca_conta_como_consulta_de_dado(self):
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_AGENTE_UNICO)
        ferramentas.executar("verificar_cobertura", entidade="Inter")
        assert agentes.consultou_ferramenta_de_dado(ferramentas) is False
        assert "verificar_cobertura" not in agentes.FERRAMENTAS_DE_DADO
        assert agentes.FERRAMENTAS_DE_DADO == frozenset(
            {"buscar_trechos", "consultar_cvm", "calcular_indicadores"}
        )

    def test_o_prompt_traz_a_regra_mecanica_e_um_exemplo_do_protocolo(self):
        """(c) da correção: regra verificável + exemplo em contexto.

        O exemplo usa companhia e valores **fictícios** de propósito: um exemplo
        com número real vazaria resposta para as perguntas do conjunto e o
        experimento passaria a medir o exemplo.
        """
        instrucao = agentes.instrucao_investigador(PERGUNTA)
        assert "REGRA MECÂNICA DO LASTRO" in instrucao
        assert "verificar_cobertura' NÃO devolve valor nenhum" in instrucao
        for marcador in ("Thought:", "Action:", "Action Input:", "Observation:",
                         "Final Answer:"):
            assert marcador in instrucao, f"o exemplo ReAct precisa de {marcador}"
        assert "CONTRAEXEMPLO" in instrucao
        assert "999999" in instrucao and "BANCO EXEMPLO" in instrucao
        # Nenhum dos cinco bancos do corpus aparece no exemplo.
        for banco in ("ITAU", "BRADESCO", "SANTANDER", "BTG", "INTER"):
            assert banco not in agentes.EXEMPLO_REACT

    def test_a_instrucao_corretiva_repete_a_regra_e_nao_o_rastro(self):
        """Reinjeta-se a **regra violada**, jamais o raciocínio da tentativa."""
        corretiva = agentes.instrucao_corretiva_investigador(PERGUNTA)
        assert corretiva.endswith(agentes.instrucao_investigador(PERGUNTA))
        assert "CORREÇÃO OBRIGATÓRIA" in corretiva
        assert "ÚLTIMA tentativa" in corretiva


class TestGateDeCorrecaoDoAuditor:
    """Conferência sem reexecução não é conferência — é carimbo."""

    def test_auditor_que_confirma_sem_consultar_e_rebaixado_a_nao_reproduz(
        self, config
    ):
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())],
            respostas_auditor=[final({"veredito": "confirma"})],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        auditor = criados[f"llm_{PAPEL_AUDITOR}"]
        # Uma rodada corretiva, e uma só.
        assert auditor.chamadas == 2
        assert resposta.veredito_auditor == VEREDITO_NAO_REPRODUZ
        assert resposta.correcao_aplicada is True
        assert resposta.correcao_resultado == agentes.CORRECAO_FALHOU
        assert resposta.parcial is True

    def test_auditor_corrigido_que_consulta_mantem_o_proprio_veredito(self, config):
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())],
            respostas_auditor=[
                final({"veredito": "confirma"}),  # 1ª: carimbo sem consulta
                ACAO_SQL,                          # corretiva: consulta o painel
                final({"veredito": "confirma"}),
            ],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        auditor = criados[f"llm_{PAPEL_AUDITOR}"]
        assert auditor.chamadas == 3
        assert resposta.veredito_auditor == VEREDITO_CONFIRMA
        assert resposta.correcao_aplicada is True
        assert resposta.correcao_resultado == agentes.CORRECAO_BEM_SUCEDIDA

    def test_nao_reproduz_nao_dispara_correcao(self, config):
        """Cobrar consulta para poder dizer que não conseguiu consultar é circular."""
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())],
            respostas_auditor=[final({"veredito": "nao_reproduz"})],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        auditor = criados[f"llm_{PAPEL_AUDITOR}"]
        assert auditor.chamadas == 1
        assert resposta.veredito_auditor == VEREDITO_NAO_REPRODUZ
        assert resposta.correcao_aplicada is False


# --------------------------------------------------------------------------- #
# Roteamento: o Auditor só audita afirmação de fato (RN11 × 5.9.1)
# --------------------------------------------------------------------------- #


SAIDA_DESAMBIGUACAO = saida_valida(
    cobertura="ambigua",
    comportamento="pergunta_de_desambiguacao",
    motivo_recusa="n/a",
    bases=[],
    citacoes=[],
    afirmacao=(
        "O termo 'BTG' identifica duas companhias no painel da CVM: BCO BTG "
        "PACTUAL S.A. (CD_CVM 022616) e BTG PACTUAL COMMODITIES SERTRADING "
        "S.A. (CD_CVM 027774). Informe qual delas você quer."
    ),
    rastro=["passo 1: verifiquei a cobertura e o nome resolveu para duas"],
)


class TestDesambiguacaoNaoVaiAoAuditor:
    """Pergunta não é alegação — não há o que falsificar (achado de 2026-08-13).

    Em AGTC003 ("BTG") o Investigador faz exatamente o que a RN11 manda:
    devolve a escolha ao usuário em vez de eleger a companhia mais provável.
    Mandar essa saída ao Auditor pede que ele reproduza uma evidência que não
    existe; o desfecho mecânico é `nao_reproduz` — cujo texto publicado afirma
    que "a conferência não conseguiu reproduzir a evidência desta afirmação" —
    e a resposta correta é rebaixada a parcial. O braço A acertava a mesma
    pergunta, e a discordância A×B era **artefato de roteamento**.

    A correção é de código, como o isolamento: nada que dependa de o modelo se
    comportar.
    """

    def test_a_fabrica_de_llm_do_auditor_nao_e_sequer_chamada(self, config):
        """A asserção central: o Auditor não existe nesta execução.

        Não se olha o veredito publicado — olha-se se o **papel** chegou a ser
        instanciado. Um roteamento que criasse o Auditor e depois descartasse o
        veredito continuaria pagando a chamada, que é metade do defeito.
        """
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, final(SAIDA_DESAMBIGUACAO)],
            respostas_auditor=[final({"veredito": "nao_reproduz"})],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert f"llm_{PAPEL_AUDITOR}" not in criados, (
            "a desambiguação foi roteada ao Auditor: ele não tem papel aqui e "
            "a chamada é paga"
        )
        assert f"ferr_{PAPEL_AUDITOR}" not in criados
        assert criados[f"llm_{PAPEL_INVESTIGADOR}"].chamadas == 2
        # E a conta fecha do lado do custo: nenhuma chamada de LLM além das do
        # Investigador entrou no uso publicado.
        assert resposta.uso.chamadas_llm == 2

    def test_a_resposta_publicada_e_a_desambiguacao_intacta(self, config):
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [ACAO_COBERTURA, final(SAIDA_DESAMBIGUACAO)],
            respostas_auditor=[final({"veredito": "nao_reproduz"})],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert resposta.comportamento == "pergunta_de_desambiguacao"
        assert resposta.precisa_desambiguacao is True
        assert resposta.parcial is False
        assert resposta.recusa is False
        assert resposta.nao_conciliada is False
        # `veredito_auditor` nulo, como no braço A e como já acontece quando a
        # verificação por código barra antes da auditoria.
        assert resposta.veredito_auditor is None
        assert resposta.contexto_auditor is None
        assert "022616" in resposta.resposta and "027774" in resposta.resposta
        assert "RESPOSTA PARCIAL" not in resposta.resposta
        # RN11: nenhuma das duas companhias foi escolhida por conta própria.
        assert valores_monetarios_do_texto(resposta.resposta) == ()

    def test_montar_contexto_auditor_recusa_a_desambiguacao(self):
        """O ponto de passagem barra o desvio — em qualquer caminho.

        `montar_contexto_auditor` é a única porta do Investigador para o
        Auditor. Barrar nela faz o roteamento errado **falhar alto** em
        produção, no arnês de medição e em teste, em vez de degenerar de volta
        no defeito medido.
        """
        saida = SaidaInvestigador(
            pergunta=PERGUNTA,
            afirmacao=SAIDA_DESAMBIGUACAO["afirmacao"],
            comportamento="pergunta_de_desambiguacao",
            cobertura="ambigua",
        )
        assert agentes.dispensa_auditoria(saida) is True
        with pytest.raises(agentes.AuditoriaNaoAplicavelError):
            agentes.montar_contexto_auditor(saida)

    def test_afirmacao_de_fato_continua_indo_ao_auditor(self, config):
        """Contra o teste que passa por vacuidade.

        Um roteamento que nunca chamasse o Auditor também passaria nas
        asserções acima — e apagaria o braço B inteiro. Mesmo cenário, saída de
        fato: o Auditor é instanciado e o veredito é publicado.
        """
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())],
            respostas_auditor=[ACAO_SQL, final({"veredito": "confirma"})],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert f"llm_{PAPEL_AUDITOR}" in criados
        assert criados[f"llm_{PAPEL_AUDITOR}"].chamadas >= 1
        assert resposta.veredito_auditor == VEREDITO_CONFIRMA

    def test_dispensa_auditoria_so_vale_para_quem_nao_afirma(self):
        """A lista é fechada: resposta com fato **precisa** ser auditada."""
        assert agentes.COMPORTAMENTOS_SEM_AUDITORIA == frozenset(
            {"pergunta_de_desambiguacao"}
        )
        for comportamento in ("resposta_completa", "resposta_parcial_marcada",
                              "divergencia_registrada", "registro_sem_juizo"):
            saida = SaidaInvestigador(
                pergunta=PERGUNTA,
                afirmacao="o lucro foi de R$ 417,5 milhões",
                comportamento=comportamento,
            )
            assert agentes.dispensa_auditoria(saida) is False, (
                f"{comportamento} afirma fato e precisa passar pelo Auditor"
            )


# --------------------------------------------------------------------------- #
# Contenção: tetos de iteração e de chamada de ferramenta (5.9.5)
# --------------------------------------------------------------------------- #


class TestContencao:
    def test_teto_de_iteracoes_para_o_laco_e_marca_parcial(self, config):
        """Agente que **nunca** conclui: o laço para mesmo assim.

        Este teste existe porque o `max_iter` do CrewAI não é um teto: ao
        atingi-lo, o framework anexa um pedido de resposta final ao histórico e
        **continua** iterando, contando com a cooperação do modelo
        (`handle_max_iterations_exceeded`). Um modelo que ignore o pedido —
        saída malformada, provedor de fallback, mau momento — mantém o laço
        aberto pagando token, que é exatamente o que a 5.9.5 proíbe. O
        `LLMComTetoRigido` corta por contagem, sem depender de cooperação.

        O duplo aqui nunca emite `Final Answer`. Sem o teto rígido, este teste
        não falha: ele **trava**.
        """
        config = Config(agentes_max_iteracoes=3)
        fabrica_llm, fabrica_ferr, criados = montar_fabricas([ACAO_SQL])
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        llm = criados[f"llm_{PAPEL_AGENTE_UNICO}"]
        # No máximo max_iter + 1 chamadas: a margem é o pedido de resposta
        # final do próprio framework, e nada além dela.
        assert llm.chamadas <= config.agentes_max_iteracoes + 1
        assert resposta.parcial_por_teto is True
        assert resposta.parcial is True
        # Parcial marcada, não recusa: o sistema parou de procurar por decisão
        # de contenção, e não por ausência de evidência (5.9.4 separa as duas).
        assert resposta.recusa is False
        assert resposta.comportamento == "resposta_parcial_marcada"
        assert "teto de passos" in resposta.resposta
        # A resposta parcial é gerada por código e não publica número nenhum.
        assert valores_monetarios_do_texto(resposta.resposta) == ()

    def test_teto_rigido_corta_por_contagem_de_chamadas(self):
        """A guarda em si, sem framework no meio."""
        interno = LLMRoteirizado(["seguindo"], PAPEL_INVESTIGADOR)
        contido = LLMComTetoRigido(interno, 2)
        assert contido.call("a") == "seguindo"
        assert contido.call("b") == "seguindo"
        with pytest.raises(TetoIteracoesExcedidoError):
            contido.call("c")
        assert contido.teto_atingido is True
        assert interno.chamadas == 2
        # A contabilidade continua sendo a do provedor real: o envelope conta
        # passos, não custo.
        assert contido.uso is interno.uso

    def test_teto_rigido_no_auditor_vira_nao_reproduz(self, config):
        """O Auditor que não fecha o laço não confirma nada."""
        config = Config(agentes_max_iteracoes=2)
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())],
            respostas_auditor=[ACAO_SQL],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert resposta.veredito_auditor == VEREDITO_NAO_REPRODUZ
        assert resposta.parcial is True

    def test_teto_de_chamadas_de_ferramenta_nao_e_ultrapassado(self, config):
        # As consultas precisam ser **distintas**: o CrewAI bloqueia a repetição
        # literal do mesmo par ferramenta/argumento antes de executá-la, e um
        # roteiro com quatro consultas idênticas mediria essa proteção do
        # framework em vez do teto de orçamento deste projeto.
        acoes = [
            'Thought: consulta {i}\nAction: consultar_cvm\nAction Input: '
            '{{"sql": "SELECT valor_reais FROM fatos_semanticos LIMIT {i}"}}'.format(
                i=i
            )
            for i in range(1, 5)
        ]
        caixa = CaixaFalsa(max_chamadas=2)
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            acoes + [final(saida_valida())],
            caixa=caixa,
        )
        config = Config(agentes_max_iteracoes=6)
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert len(caixa.registro) <= 2
        assert resposta.parcial_por_teto is True

    def test_teto_devolve_instrucao_em_vez_de_explodir(self):
        """Ferramenta estourada vira observação, não exceção no laço."""
        caixa = CaixaFalsa(max_chamadas=1)
        ferramentas = FerramentasDoAgente(caixa, PAPEL_INVESTIGADOR)
        ferramenta = construir_ferramentas(ferramentas, ("consultar_cvm",))[0]
        ferramenta.run(sql="SELECT 1")
        segunda = ferramenta.run(sql="SELECT 1")
        assert "teto_de_chamadas_atingido" in segunda
        assert ferramentas.teto_atingido is True

    def test_orcamento_bloqueia_chamada_que_nao_cabe_no_teto(self, tmp_path):
        journal = tmp_path / "journal.jsonl"
        orcamento = ControleOrcamento(0.001, caminho_journal=journal)

        class ProvedorCaro:
            nome = "caro"

            def estimar_custo_maximo(self, sistema, usuario):
                return 0.9

            def gerar_texto(self, sistema, usuario, temperatura=0.0):
                raise AssertionError("não deveria chamar")

        ponte = LLMPonte(
            ProvedorCaro(), papel=PAPEL_INVESTIGADOR, orcamento=orcamento
        )
        with pytest.raises(OrcamentoAgentesExcedidoError):
            ponte.call([{"role": "user", "content": "oi"}])
        eventos = [json.loads(l) for l in journal.read_text().splitlines()]
        assert [e["evento"] for e in eventos] == ["intencao", "bloqueio_por_teto"]

    def test_journal_registra_intencao_antes_e_conclusao_depois(self, tmp_path):
        journal = tmp_path / "journal.jsonl"
        orcamento = ControleOrcamento(1.0, caminho_journal=journal)

        class ProvedorFalso:
            nome = "falso"

            def estimar_custo_maximo(self, sistema, usuario):
                return 0.01

            def gerar_texto(self, sistema, usuario, temperatura=0.0):
                return RespostaBrutaLLM(
                    texto="ok",
                    uso=UsoLLM(
                        tokens_entrada=10,
                        tokens_saida=5,
                        custo_usd=0.002,
                        latencia_s=0.1,
                        modelo="falso",
                    ),
                    modelo="falso",
                )

        ponte = LLMPonte(
            ProvedorFalso(), papel=PAPEL_INVESTIGADOR, orcamento=orcamento
        )
        assert ponte.call([{"role": "user", "content": "oi"}]) == "ok"
        eventos = [json.loads(l) for l in journal.read_text().splitlines()]
        assert [e["evento"] for e in eventos] == ["intencao", "conclusao"]
        assert orcamento.acumulado_usd == pytest.approx(0.002)
        assert ponte.uso.tokens_entrada == 10
        assert ponte.uso.custo_usd == pytest.approx(0.002)


# --------------------------------------------------------------------------- #
# Vereditos do Auditor (5.9.1 e 5.9.5)
# --------------------------------------------------------------------------- #


class TestVereditos:
    def _rodar(self, config, veredito_json):
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())],
            respostas_auditor=[ACAO_SQL, final(veredito_json)],
        )
        return responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )

    def test_confirma_preserva_a_resposta(self, config):
        resposta = self._rodar(
            config,
            {"veredito": "confirma", "justificativa": "reproduzi", "citacoes": []},
        )
        assert resposta.veredito_auditor == VEREDITO_CONFIRMA
        assert resposta.nao_conciliada is False
        assert "R$ 417,5 milhões" in resposta.resposta

    def test_contesta_marca_nao_conciliada_e_mostra_as_duas_evidencias(self, config):
        """5.9.5: o sistema não elege vencedor."""
        resposta = self._rodar(
            config,
            {
                "veredito": "contesta",
                "justificativa": "o painel devolve outro valor",
                "contraevidencia": ["fatos_semanticos 080217 1T2026 = 394.788.000"],
                "citacoes": ["CVM 080217"],
            },
        )
        assert resposta.veredito_auditor == VEREDITO_CONTESTA
        assert resposta.nao_conciliada is True
        assert resposta.parcial is True
        assert "NÃO CONCILIADA" in resposta.resposta
        assert "394.788.000" in resposta.resposta
        assert CITACAO in resposta.resposta

    def test_contestacao_sem_contraevidencia_vira_nao_reproduz(self, config):
        """'Contesta com contraevidência citada' — sem ela, não é contestação."""
        resposta = self._rodar(
            config, {"veredito": "contesta", "justificativa": "não gostei"}
        )
        assert resposta.veredito_auditor == VEREDITO_NAO_REPRODUZ

    def test_nao_reproduz_vira_resposta_parcial_marcada(self, config):
        resposta = self._rodar(
            config,
            {"veredito": "nao_reproduz", "justificativa": "a consulta não voltou"},
        )
        assert resposta.veredito_auditor == VEREDITO_NAO_REPRODUZ
        assert resposta.parcial is True
        assert resposta.comportamento == "resposta_parcial_marcada"
        assert "não conseguiu reproduzir" in resposta.resposta

    def test_veredito_ilegivel_nao_vira_confirmacao(self, config):
        """Ausência de confirmação não é confirmação."""
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())],
            respostas_auditor=["Thought: fim\nFinal Answer: achei tudo certo"],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert resposta.veredito_auditor == VEREDITO_NAO_REPRODUZ


# --------------------------------------------------------------------------- #
# Formato do registro — comparabilidade linha a linha (5.9.3)
# --------------------------------------------------------------------------- #


def pergunta_sintetica(identificador: str = "AGTC001") -> PerguntaAgentes:
    return PerguntaAgentes(
        id=identificador,
        categoria="factual",
        subtipo_adversarial="",
        pergunta=PERGUNTA,
        comportamento_aceito=("resposta_parcial_marcada",),
        cobertura_esperada="so_painel",
        motivo_recusa_esperado="fora_do_corpus",
        base_esperada=("contabil_consolidado",),
        rota_esperada="triagem_cobertura",
        subconjunto="cobertura",
        status_gabarito=STATUS_VERIFICADO,
    )


class TestFormatoDoRegistro:
    def test_o_registro_tem_exatamente_os_campos_dos_tres_bracos(self, config):
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        registro = montar_registro(pergunta_sintetica(), BRACO_A, resposta, 1.5)
        assert tuple(registro.como_dicionario()) == CAMPOS_REGISTRO + (
            "total_chamadas_ferramenta",
        ) or set(registro.como_dicionario()) >= set(CAMPOS_REGISTRO)
        assert set(CAMPOS_REGISTRO) <= set(registro.como_dicionario())
        assert registro.braco == BRACO_A
        assert registro.veredito_auditor is None
        assert registro.latencia_s == 1.5
        assert registro.chamadas_llm >= 1
        assert registro.custo_usd > 0
        assert registro.entidades_resolvidas == ("080217",)
        assert registro.leituras_painel == 2

    def test_o_braco_b_grava_o_veredito(self, config):
        """O log traz as chamadas dos dois papéis, distinguíveis por `papel`."""
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())],
            respostas_auditor=[ACAO_SQL, final({"veredito": "confirma"})],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        registro = montar_registro(pergunta_sintetica(), BRACO_B, resposta, 2.0)
        assert registro.veredito_auditor == VEREDITO_CONFIRMA
        assert registro.chamadas_llm >= 4  # investigador + auditor
        assert any(
            c["papel"] == PAPEL_AUDITOR for c in registro.chamadas_ferramenta
        )

    def test_pendencia_nunca_vira_acerto(self, config):
        """A regra dura da apuração vale igual nos três braços."""
        pergunta = PerguntaAgentes(
            **{
                **{
                    campo: getattr(pergunta_sintetica(), campo)
                    for campo in PerguntaAgentes.__dataclass_fields__
                    if campo != "status_gabarito"
                },
                "status_gabarito": "pendente_conferencia_humana",
            }
        )
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())]
        )
        resposta = responder_braco_a(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        registro = montar_registro(pergunta, BRACO_A, resposta, 1.0)
        assert registro.apuracao == APURACAO_PENDENTE
        assert registro.acerto is None

    def test_registro_recusa_ferramenta_proibida_no_log(self):
        """A guarda da RN07 também vale para o que foi registrado."""
        from src.braco_determinista import RegistroBraco

        with pytest.raises(ValueError, match="RN07"):
            RegistroBraco(
                id_pergunta="X",
                braco=BRACO_A,
                subconjunto="cobertura",
                categoria="factual",
                rota_esperada="triagem_cobertura",
                pergunta=PERGUNTA,
                chamadas_ferramenta=({"ferramenta": "prever_risco"},),
            )


# --------------------------------------------------------------------------- #
# Execução do braço sobre um conjunto
# --------------------------------------------------------------------------- #


class TestExecucaoDoBraco:
    def test_roda_o_conjunto_e_resume(self, config):
        perguntas = [pergunta_sintetica("AGTC001"), pergunta_sintetica("AGTC004")]
        fabrica_llm, fabrica_ferr, _ = montar_fabricas(
            [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())],
            # O Auditor consulta o painel ANTES de contestar: o gate de dado
            # rebaixa para `nao_reproduz` quem contesta sem ter reexecutado
            # nada, e um Auditor que contesta de fato reexecutou.
            respostas_auditor=[
                ACAO_SQL,
                final(
                    {
                        "veredito": "contesta",
                        "justificativa": "diverge",
                        "contraevidencia": ["painel devolve outro valor"],
                    }
                ),
            ],
        )
        resultado = executar_braco_agente(
            BRACO_B,
            perguntas,
            config,
            fabrica_llm=fabrica_llm,
            fabrica_ferramentas=fabrica_ferr,
            relogio=iter(range(0, 100)).__next__,
        )
        assert [r.id_pergunta for r in resultado.registros] == ["AGTC001", "AGTC004"]
        resumo = resumo_com_isolamento(resultado)
        assert resumo["n"] == 2
        assert resumo["vereditos_auditor"] == {VEREDITO_CONTESTA: 2}
        assert resumo["respostas_alteradas_pelo_auditor"] == 2
        assert resumo["custo_por_resposta_alterada_usd"] > 0

    def test_uma_pergunta_que_explode_nao_derruba_as_outras(self, config):
        chamadas = {"n": 0}

        def fabrica_llm(papel: str):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise RuntimeError("provedor fora do ar")
            return LLMRoteirizado(
                [ACAO_COBERTURA, ACAO_SQL, final(saida_valida())], papel
            )

        def fabrica_ferramentas(papel: str) -> FerramentasDoAgente:
            return FerramentasDoAgente(CaixaFalsa(), papel)

        resultado = executar_braco_agente(
            BRACO_A,
            [pergunta_sintetica("AGTC001"), pergunta_sintetica("AGTC004")],
            config,
            fabrica_llm=fabrica_llm,
            fabrica_ferramentas=fabrica_ferramentas,
        )
        assert len(resultado.registros) == 2
        assert resultado.registros[0].erro_execucao is not None
        assert resultado.registros[0].recusa is True
        assert resultado.registros[1].erro_execucao is None

    def test_estouro_de_orcamento_para_a_execucao(self, config, tmp_path):
        """Nunca um laço aberto pagando token: a execução para e devolve o medido."""
        orcamento = ControleOrcamento(
            0.00001, caminho_journal=tmp_path / "j.jsonl"
        )

        def fabrica_llm(papel: str):
            class ProvedorCaro:
                nome = "caro"

                def estimar_custo_maximo(self, sistema, usuario):
                    return 1.0

                def gerar_texto(self, sistema, usuario, temperatura=0.0):
                    raise AssertionError("não deveria chamar")

            return LLMPonte(ProvedorCaro(), papel=papel, orcamento=orcamento)

        resultado = executar_braco_agente(
            BRACO_A,
            [pergunta_sintetica("AGTC001"), pergunta_sintetica("AGTC004")],
            config,
            fabrica_llm=fabrica_llm,
            fabrica_ferramentas=lambda papel: FerramentasDoAgente(
                CaixaFalsa(), papel
            ),
            orcamento=orcamento,
        )
        assert len(resultado.registros) == 1
        assert "Orcamento" in (resultado.registros[0].erro_execucao or "")

    def test_so_existem_orquestradores_para_a_e_b(self, config):
        assert set(ORQUESTRADORES) == {BRACO_A, BRACO_B}
        with pytest.raises(ValueError, match="braço"):
            executar_braco_agente("C", [], config)


# --------------------------------------------------------------------------- #
# Ponte com o provedor do projeto
# --------------------------------------------------------------------------- #


class TestPonteDeProvedor:
    def test_mensagens_do_crewai_viram_par_sistema_usuario(self):
        sistema, usuario = agentes.achatar_mensagens(
            [
                {"role": "system", "content": "regras"},
                {"role": "user", "content": "pergunta"},
                {"role": "assistant", "content": "Thought: x"},
            ]
        )
        assert sistema == "regras"
        assert "pergunta" in usuario and "Thought: x" in usuario

    def test_ponte_usa_gerar_texto_e_nao_gerar(self):
        """O laço ReAct não aceita `response_format=json_object`."""
        registro: list[str] = []

        class Provedor:
            nome = "duplo"

            def gerar(self, sistema, usuario, temperatura=0.0):
                registro.append("gerar")
                raise AssertionError("o agente não pode passar por aqui")

            def gerar_texto(self, sistema, usuario, temperatura=0.0):
                registro.append("gerar_texto")
                return RespostaBrutaLLM(
                    texto="ok",
                    uso=UsoLLM(
                        tokens_entrada=1,
                        tokens_saida=1,
                        custo_usd=0.0,
                        latencia_s=0.0,
                    ),
                    modelo="duplo",
                )

        ponte = LLMPonte(Provedor(), papel=PAPEL_INVESTIGADOR)
        assert ponte.call("oi") == "ok"
        assert registro == ["gerar_texto"]

    def test_provedor_sem_preco_conta_como_sem_telemetria(self):
        class Provedor:
            nome = "sem_preco"

            def gerar_texto(self, sistema, usuario, temperatura=0.0):
                return RespostaBrutaLLM(
                    texto="ok",
                    uso=UsoLLM(
                        tokens_entrada=1,
                        tokens_saida=1,
                        custo_usd=None,
                        latencia_s=0.0,
                    ),
                    modelo="sem_preco",
                )

        ponte = LLMPonte(Provedor(), papel=PAPEL_INVESTIGADOR)
        ponte.call("oi")
        assert ponte.uso.sem_telemetria == 1
        assert ponte.uso.custo_usd == 0.0

    def test_erro_transitorio_reespera_e_erro_de_contrato_nao(self, monkeypatch):
        """429 do provedor não é comportamento de agente (5.9.4).

        Deixar a cota estourada virar "o agente não respondeu" confundiria
        falha de infraestrutura com recusa — a confusão que a injeção de falha
        existe para desfazer.
        """
        import httpx
        from openai import RateLimitError

        resposta_429 = httpx.Response(
            429, request=httpx.Request("POST", "https://exemplo.invalido/v1")
        )
        monkeypatch.setattr(agentes.time, "sleep", lambda _: None)
        tentativas = {"n": 0}

        class ProvedorInstavel:
            nome = "instavel"

            def gerar_texto(self, sistema, usuario, temperatura=0.0):
                tentativas["n"] += 1
                if tentativas["n"] == 1:
                    raise RateLimitError(
                        "cota", response=resposta_429, body=None
                    )
                return RespostaBrutaLLM(
                    texto="ok",
                    uso=UsoLLM(
                        tokens_entrada=1,
                        tokens_saida=1,
                        custo_usd=0.0,
                        latencia_s=0.0,
                    ),
                    modelo="instavel",
                )

        ponte = LLMPonte(ProvedorInstavel(), papel=PAPEL_INVESTIGADOR)
        assert ponte.call("oi") == "ok"
        assert tentativas["n"] == 2
        # Uma chamada bem-sucedida, ainda que na segunda tentativa: a
        # contabilidade registra o que foi cobrado, não o que foi tentado.
        assert ponte.uso.chamadas_llm == 1

        class ProvedorQuebrado:
            nome = "quebrado"

            def gerar_texto(self, sistema, usuario, temperatura=0.0):
                raise ValueError("contrato violado")

        with pytest.raises(ValueError, match="contrato"):
            LLMPonte(ProvedorQuebrado(), papel=PAPEL_INVESTIGADOR).call("oi")

    def test_corte_em_parada_descarta_observacao_inventada(self):
        """A observação é o que a ferramenta devolve, não o que o modelo escreve."""
        texto = (
            'Thought: vou consultar\nAction: consultar_cvm\n'
            'Action Input: {"sql": "SELECT 1"}\n'
            "Observation: lucro de R$ 999,9 milhões\n"
            "Final Answer: pronto"
        )
        cortado = agentes.cortar_em_parada(texto, ["\nObservation:"])
        assert cortado.endswith('{"sql": "SELECT 1"}')
        assert "999,9" not in cortado
        # Contrato REFORÇADO em 2026-08-14: a observação fabricada é cortada
        # mesmo sem o executor registrar parada. Antes, lista vazia devolvia o
        # texto inteiro — e uma evidência inventada passava direto. A guarda
        # não depende mais de o framework lembrar de pedir a parada.
        assert "999,9" not in agentes.cortar_em_parada(texto, [])

    def test_corte_pega_observacao_em_notacao_alternativa(self):
        """Notação diferente não pode ser rota de fuga da parada.

        Medido em 2026-08-14 (DeepSeek v4-flash, `reasoning_effort=max`,
        AGTC004): o modelo escreveu o protocolo em tags XML e fabricou dentro
        de `<Observation>` um retorno completo de `verificar_cobertura`, com
        CD_CVM e razão social que nenhuma ferramenta devolveu. `<Observation>`
        não casa com o literal `Observation:`, então nada cortava.
        """
        xml = (
            "<Thought>\nvou verificar\n</Thought>\n"
            "<Action>\nverificar_cobertura\n</Action>\n"
            "<Observation>\n"
            '{"cd_cvm": "906637", "denom_social": "INVENTADO S.A."}\n'
            "</Observation>"
        )
        cortado = agentes.cortar_em_parada(xml, ["\nObservation:"])
        assert "906637" not in cortado
        assert "INVENTADO" not in cortado
        assert cortado.rstrip().endswith("</Action>")

        for variante in (
            "Thought: ok\n**Observation:** inventado",
            "Thought: ok\nObservação: inventado",
            "Thought: ok\n[Observation] inventado",
        ):
            assert "inventado" not in agentes.cortar_em_parada(variante, [])

    def test_corte_nao_mutila_a_palavra_no_meio_de_frase(self):
        """A guarda casa marcador de protocolo, não vocabulário legítimo."""
        legitimo = 'Final Answer: {"rastro": ["fiz uma observação sobre o painel"]}'
        assert agentes.cortar_em_parada(legitimo, []) == legitimo

    def test_uso_de_dois_papeis_soma_sem_se_confundir(self):
        a = UsoAgente(chamadas_llm=2, tokens_entrada=10, custo_usd=0.1)
        b = UsoAgente(chamadas_llm=3, tokens_entrada=5, custo_usd=0.2)
        total = a.somar(b)
        assert total.chamadas_llm == 5
        assert total.tokens_entrada == 15
        assert total.custo_usd == pytest.approx(0.3)


# --------------------------------------------------------------------------- #
# Evidência disponível — a base do lastro
# --------------------------------------------------------------------------- #


class TestEvidencia:
    def test_rotulos_saem_de_chaves_conhecidas_e_nao_do_json_inteiro(self):
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_INVESTIGADOR)
        ferramentas.executar("verificar_cobertura", entidade="Inter")
        rotulos = ferramentas.rotulos_de_evidencia()
        assert "080217" in rotulos
        assert "inter & co, inc." in rotulos
        # A chave do JSON não é rótulo: se fosse, qualquer citação com a palavra
        # "trimestre" passaria e a verificação viraria carimbo.
        assert "denom_social" not in rotulos
        assert "consulta" not in rotulos

    def test_pagina_de_trecho_nao_lastreia_valor(self):
        """Página 3 não pode sustentar "R$ 3 milhões"."""
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_INVESTIGADOR)
        ferramentas.executar("buscar_trechos", pergunta="lucro")
        valores = ferramentas.valores_de_evidencia()
        assert 3.0 not in valores
        assert 430_000_000.0 in valores

    def test_chamada_registrada_guarda_papel_e_ferramenta(self):
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_AUDITOR)
        ferramentas.executar("consultar_cvm", sql="SELECT 1")
        chamada = ferramentas.chamadas[0]
        assert isinstance(chamada, ChamadaFerramenta)
        assert chamada.como_dicionario()["papel"] == PAPEL_AUDITOR
        assert chamada.como_dicionario()["ferramenta"] == "consultar_cvm"
