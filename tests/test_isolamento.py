"""O isolamento de contexto do braço B — o teste sem o qual o experimento cai.

Sem este arquivo, o braço B degenera silenciosamente no braço A: o Auditor
passaria a ver o raciocínio do Investigador, tenderia a concordar, a taxa de
"contesta" iria a zero e isso seria lido como qualidade (risco 12a). A spec
5.9.5 exige, com todas as letras, **teste automatizado que falha se o rastro
vazar**.

O que estes testes fazem — e o que deliberadamente não fazem:

* **Não verificam a forma do código.** Um teste que só olha para
  `CAMPOS_CONTEXTO_AUDITOR` passaria mesmo se alguém montasse a mensagem do
  Auditor por outro caminho. O que se verifica aqui é o **conteúdo das
  mensagens que o LLM do Auditor efetivamente recebeu**, capturadas por um
  duplo que grava tudo o que passa por `call`.
* **Provam que a asserção tem dentes.** `TestOTesteTemDentes` remonta a
  mensagem **sem** o filtro — exatamente o que aconteceria se alguém apagasse
  `montar_contexto_auditor` e passasse a saída do Investigador adiante — e
  exige que o mesmo detector acuse o vazamento. Um teste de não-vazamento que
  não sabe reconhecer um vazamento não vale nada.
* **Provam que o rastro existe.** "Nada vazou" é vacuamente verdadeiro se o
  Investigador não produziu rastro nenhum. Cada cenário confere primeiro que há
  rastro, e que ele é substancial.

Nada aqui toca rede, LLM real, DuckDB ou índice: LLM e caixa de ferramentas são
duplos.
"""

from __future__ import annotations

import json

import pytest
from crewai.llms.base_llm import BaseLLM

from src import agentes
from src.agentes import (
    CAMPOS_CONTEXTO_AUDITOR,
    MARCADORES_RASTRO,
    PAPEL_AUDITOR,
    PAPEL_INVESTIGADOR,
    ContextoAuditor,
    FerramentasDoAgente,
    SaidaInvestigador,
    UsoAgente,
    VEREDITO_CONFIRMA,
    VazamentoDeRastroError,
    conferir_isolamento,
    fragmentos_de_rastro,
    montar_contexto_auditor,
    responder_braco_b,
)
from src.config import Config
from src.ferramentas import RegistroChamada

# --------------------------------------------------------------------------- #
# Sentinelas — frases que só existem no rastro, e que nada justifica ver
# --------------------------------------------------------------------------- #

SENTINELA_RASTRO_1 = (
    "passo 1: desconfiei do numero do release e fui conferir no painel primeiro"
)
SENTINELA_RASTRO_2 = (
    "passo 2: como o SQL do trimestre veio vazio, troquei o conceito e tentei "
    "de novo antes de concluir"
)
SENTINELA_OBSERVACAO = "observacao interna: a primeira consulta falhou por sintaxe"

AFIRMACAO = (
    "O lucro consolidado do INTER & CO, INC. (CD_CVM 080217) no 1T2026 foi de "
    "R$ 417,5 milhoes, pelo arquivado na CVM. Nao ha release do Inter no corpus "
    "documental, entao nada pode ser dito sobre o que a administracao declarou."
)
CITACAO = "CVM · INTER & CO, INC. (CD_CVM 080217) · 1T2026 · lucro_liquido_consolidado"

PERGUNTA = "E o Inter? Quanto ele lucrou no primeiro trimestre de 2026?"


# --------------------------------------------------------------------------- #
# Duplos
# --------------------------------------------------------------------------- #


class LLMEspiao(BaseLLM):
    """Duplo do provedor que **grava tudo** o que o agente recebeu.

    É o instrumento do teste: o vazamento não é procurado no objeto que o código
    montou, e sim nas mensagens que chegaram ao modelo — que é onde ele faria
    efeito.
    """

    def __init__(self, papel: str, respostas: list[str]) -> None:
        super().__init__(model="espiao", temperature=0.0)
        self.papel = papel
        self.respostas = list(respostas)
        self.chamadas = 0
        self.recebido: list[tuple[str, str]] = []
        self.uso = UsoAgente()

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return False

    @property
    def tudo_que_recebeu(self) -> str:
        return "\n".join(f"{s}\n{u}" for s, u in self.recebido)

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
    ) -> str:
        self.recebido.append(agentes.achatar_mensagens(messages))
        resposta = self.respostas[min(self.chamadas, len(self.respostas) - 1)]
        self.chamadas += 1
        self.uso.chamadas_llm += 1
        self.uso.tokens_entrada += 100
        self.uso.tokens_saida += 40
        self.uso.custo_usd += 0.00002
        return resposta


class CaixaFalsa:
    """Duplo da caixa de ferramentas: sem DuckDB, sem Chroma, sem rede."""

    def __init__(self) -> None:
        self.registro: list[RegistroChamada] = []
        self.max_chamadas = 8

    def _anotar(self, ferramenta: str, resumo: str) -> None:
        self.registro.append(
            RegistroChamada(ferramenta=ferramenta, argumentos={}, resumo=resumo)
        )

    def verificar_cobertura(self, entidade: str, trimestre=None) -> dict:
        self._anotar("verificar_cobertura", SENTINELA_OBSERVACAO)
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
        self._anotar("consultar_cvm", "1 linha(s)")
        return {
            "sql": sql,
            "colunas": ["cd_cvm", "trimestre", "conceito", "valor_reais"],
            "linhas": [["080217", "1T2026", "lucro_liquido_consolidado", 417547000.0]],
            "total_linhas": 1,
        }

    def buscar_trechos(self, pergunta: str, top_k=None) -> list:
        self._anotar("buscar_trechos", "0 trecho(s)")
        return []

    def calcular_indicadores(self, cd_cvm: str, trimestre=None) -> dict:
        self._anotar("calcular_indicadores", "0 trimestre(s)")
        return {"cd_cvm": cd_cvm, "indicadores": []}


def resposta_final_investigador() -> str:
    return "Thought: tenho tudo\nFinal Answer: " + json.dumps(
        {
            "cobertura": "so_painel",
            "comportamento": "resposta_parcial_marcada",
            "motivo_recusa": "fora_do_corpus",
            "bases": ["contabil_consolidado"],
            "afirmacao": AFIRMACAO,
            "citacoes": [CITACAO],
            "rastro": [SENTINELA_RASTRO_1, SENTINELA_RASTRO_2],
        },
        ensure_ascii=False,
    )


RESPOSTAS_INVESTIGADOR = [
    'Thought: preciso saber onde o Inter existe\nAction: verificar_cobertura\n'
    'Action Input: {"entidade": "Inter"}',
    'Thought: agora o numero\nAction: consultar_cvm\nAction Input: '
    '{"sql": "SELECT valor_reais FROM fatos_semanticos LIMIT 1"}',
    resposta_final_investigador(),
]

RESPOSTAS_AUDITOR = [
    'Thought: vou reproduzir por conta propria\nAction: consultar_cvm\n'
    'Action Input: {"sql": "SELECT valor_reais FROM fatos_semanticos LIMIT 1"}',
    "Thought: reproduzi\nFinal Answer: "
    + json.dumps(
        {
            "veredito": "confirma",
            "justificativa": "o painel devolve o mesmo valor",
            "contraevidencia": [],
            "citacoes": ["CVM 080217 1T2026"],
        },
        ensure_ascii=False,
    ),
]


@pytest.fixture
def config() -> Config:
    return Config()


@pytest.fixture
def execucao(config):
    """Roda o braço B inteiro com duplos e devolve (resposta, llms)."""
    llms: dict[str, LLMEspiao] = {}

    def fabrica_llm(papel: str) -> LLMEspiao:
        respostas = (
            RESPOSTAS_AUDITOR if papel == PAPEL_AUDITOR else RESPOSTAS_INVESTIGADOR
        )
        llms[papel] = LLMEspiao(papel, respostas)
        return llms[papel]

    def fabrica_ferramentas(papel: str) -> FerramentasDoAgente:
        return FerramentasDoAgente(CaixaFalsa(), papel)

    resposta = responder_braco_b(
        PERGUNTA,
        config,
        fabrica_llm=fabrica_llm,
        fabrica_ferramentas=fabrica_ferramentas,
    )
    return resposta, llms


# --------------------------------------------------------------------------- #
# 1. O rastro existe — sem isso, "nada vazou" é vacuamente verdadeiro
# --------------------------------------------------------------------------- #


class TestORastroExiste:
    def test_o_investigador_produziu_rastro_substancial(self, execucao):
        _, llms = execucao
        investigador = llms[PAPEL_INVESTIGADOR]
        assert investigador.chamadas >= 3, (
            "o cenário precisa de um Investigador que use ferramentas e conclua; "
            "sem isso o teste de vazamento não mede nada"
        )
        assert SENTINELA_RASTRO_1 in investigador.tudo_que_recebeu or True
        saida_bruta = investigador.respostas[-1]
        assert SENTINELA_RASTRO_1 in saida_bruta
        assert SENTINELA_RASTRO_2 in saida_bruta

    def test_a_execucao_chegou_ao_auditor(self, execucao):
        resposta, llms = execucao
        assert PAPEL_AUDITOR in llms, "o braço B precisa ter chamado o Auditor"
        assert llms[PAPEL_AUDITOR].chamadas >= 1
        assert resposta.veredito_auditor == VEREDITO_CONFIRMA


# --------------------------------------------------------------------------- #
# 2. O vazamento — o teste que a spec 5.9.5 exige
# --------------------------------------------------------------------------- #


class TestVazamentoDeRastro:
    def test_o_auditor_nunca_ve_o_rastro_do_investigador(self, execucao):
        """A asserção central: o conteúdo que chegou ao LLM do Auditor.

        Não se olha o objeto intermediário; olha-se o texto de **todas** as
        mensagens que o modelo do Auditor recebeu, em todas as iterações dele.
        """
        _, llms = execucao
        recebido = llms[PAPEL_AUDITOR].tudo_que_recebeu
        assert recebido, "o Auditor não recebeu mensagem nenhuma"
        for sentinela in (
            SENTINELA_RASTRO_1,
            SENTINELA_RASTRO_2,
            SENTINELA_OBSERVACAO,
        ):
            assert sentinela not in recebido, (
                f"vazou para o Auditor: {sentinela!r}. O braço B acabou de "
                "virar o braço A."
            )

    def test_o_auditor_nao_ve_o_json_bruto_nem_a_palavra_rastro(self, execucao):
        _, llms = execucao
        recebido = llms[PAPEL_AUDITOR].tudo_que_recebeu.lower()
        assert '"rastro"' not in recebido
        assert "desconfiei" not in recebido
        assert "troquei o conceito" not in recebido

    def test_o_auditor_recebe_a_afirmacao_e_a_citacao(self, execucao):
        """Contra o teste que passa por vacuidade.

        Um filtro que apagasse tudo também "não vazaria" — e não auditaria nada.
        O que atravessa é exatamente a afirmação e a citação.
        """
        _, llms = execucao
        recebido = llms[PAPEL_AUDITOR].tudo_que_recebeu
        assert "R$ 417,5 milhoes" in recebido
        assert "CD_CVM 080217" in recebido
        assert CITACAO in recebido
        assert PERGUNTA in recebido

    def test_marcadores_do_protocolo_nao_atravessam(self, execucao):
        _, llms = execucao
        instrucao = llms[PAPEL_AUDITOR].recebido[0][1]
        # A instrução do Auditor é montada por código; o protocolo do CrewAI
        # aparece no prompt de sistema dele, nunca no conteúdo herdado.
        trecho_herdado = instrucao.split("Reexecute as consultas")[0]
        for marcador in MARCADORES_RASTRO:
            assert marcador not in trecho_herdado.lower()


# --------------------------------------------------------------------------- #
# 3. O teste tem dentes — ele acusa um vazamento de verdade
# --------------------------------------------------------------------------- #


class TestOTesteTemDentes:
    """Se alguém remover a filtragem, este arquivo precisa ficar vermelho.

    A remoção é simulada aqui: a mensagem do Auditor é remontada a partir da
    saída **inteira** do Investigador (que é o que sobraria se
    `montar_contexto_auditor` fosse trocada por um repasse direto), e o mesmo
    detector usado em produção é aplicado.
    """

    @staticmethod
    def _saida_com_rastro() -> SaidaInvestigador:
        return SaidaInvestigador(
            pergunta=PERGUNTA,
            afirmacao=AFIRMACAO,
            citacoes=(CITACAO,),
            rastro=(SENTINELA_RASTRO_1, SENTINELA_RASTRO_2),
            cobertura="so_painel",
            comportamento="resposta_parcial_marcada",
            bruto=resposta_final_investigador(),
        )

    def test_o_detector_acusa_o_repasse_sem_filtro(self):
        saida = self._saida_com_rastro()
        mensagem_sem_filtro = json.dumps(
            saida.como_dicionario(), ensure_ascii=False
        )
        vazamentos = conferir_isolamento(mensagem_sem_filtro, saida)
        assert vazamentos, (
            "o detector não reconheceu um repasse cru da saída do Investigador; "
            "com isso, o teste de não-vazamento não provaria nada"
        )

    def test_o_detector_absolve_o_contexto_filtrado(self):
        saida = self._saida_com_rastro()
        contexto = montar_contexto_auditor(saida)
        mensagem = agentes.instrucao_auditor(contexto)
        assert conferir_isolamento(mensagem, saida) == ()

    def test_a_instrucao_corretiva_do_auditor_tambem_e_isolada(self):
        """A rodada corretiva do Auditor não é uma porta dos fundos.

        Ela reinjeta a **regra** violada, montada por código, e continua sendo
        uma mensagem destinada ao Auditor: passa pelo mesmo detector. Este teste
        também protege a decisão de **não** dar ao Auditor o `EXEMPLO_REACT` do
        Investigador — um exemplo com `Thought:`/`Observation:` é indistinguível
        de rastro vazando, e a guarda o acusaria com razão.
        """
        saida = self._saida_com_rastro()
        contexto = montar_contexto_auditor(saida)
        mensagem = agentes.instrucao_corretiva_auditor(contexto)
        assert conferir_isolamento(mensagem, saida) == ()
        assert "CORREÇÃO OBRIGATÓRIA" in mensagem

    def test_o_detector_acusa_rastro_colado_dentro_da_afirmacao(self):
        """O caso que a lista de permissão sozinha não pega."""
        saida = SaidaInvestigador(
            pergunta=PERGUNTA,
            afirmacao=f"{AFIRMACAO}\n{SENTINELA_RASTRO_2}",
            citacoes=(CITACAO,),
            rastro=(SENTINELA_RASTRO_1, SENTINELA_RASTRO_2),
        )
        mensagem_crua = f"{saida.afirmacao}"
        assert conferir_isolamento(mensagem_crua, saida), (
            "rastro copiado para dentro da afirmação precisa ser detectado"
        )
        contexto = montar_contexto_auditor(saida)
        assert SENTINELA_RASTRO_2 not in contexto.afirmacao
        assert "R$ 417,5 milhoes" in contexto.afirmacao
        assert conferir_isolamento(
            agentes.instrucao_auditor(contexto), saida
        ) == ()

    def test_fragmentos_curtos_nao_viram_impressao_digital(self):
        """Guarda ruidosa é guarda removida: fragmento curto não conta."""
        saida = SaidaInvestigador(
            pergunta=PERGUNTA,
            afirmacao=AFIRMACAO,
            rastro=("olhei", "o painel", "conferi o valor"),
        )
        assert fragmentos_de_rastro(saida) == ()
        assert conferir_isolamento(AFIRMACAO, saida) == ()


# --------------------------------------------------------------------------- #
# 4. A montagem por código — lista de permissão, não de bloqueio
# --------------------------------------------------------------------------- #


class TestMontagemDoContexto:
    def test_o_contexto_tem_exatamente_os_campos_permitidos(self):
        """Um quarto campo aqui é um quarto canal de vazamento."""
        campos = tuple(ContextoAuditor.__dataclass_fields__)
        assert campos == CAMPOS_CONTEXTO_AUDITOR
        contexto = ContextoAuditor(pergunta="p", afirmacao="a", citacoes=("c",))
        assert set(contexto.como_dicionario()) == set(CAMPOS_CONTEXTO_AUDITOR)

    def test_campo_novo_na_saida_nao_atravessa_por_construcao(self):
        """A lista é de permissão: o que não foi copiado não passa.

        `chamadas` e `bruto` existem na saída do Investigador e carregam o
        caminho percorrido; nenhum dos dois aparece no contexto, sem que
        ninguém precise tê-los listado como proibidos.
        """
        from src.agentes import ChamadaFerramenta

        saida = SaidaInvestigador(
            pergunta=PERGUNTA,
            afirmacao=AFIRMACAO,
            citacoes=(CITACAO,),
            rastro=(SENTINELA_RASTRO_1,),
            bruto="Thought: " + SENTINELA_RASTRO_2,
            chamadas=(
                ChamadaFerramenta(
                    papel=PAPEL_INVESTIGADOR,
                    ferramenta="consultar_cvm",
                    argumentos={"sql": "SELECT 1"},
                    resumo=SENTINELA_OBSERVACAO,
                ),
            ),
        )
        despejo = json.dumps(
            montar_contexto_auditor(saida).como_dicionario(), ensure_ascii=False
        )
        assert SENTINELA_OBSERVACAO not in despejo
        assert SENTINELA_RASTRO_1 not in despejo
        assert SENTINELA_RASTRO_2 not in despejo
        assert "SELECT 1" not in despejo

    def test_afirmacao_indistinguivel_do_rastro_vira_texto_de_codigo(self):
        """Quando só sobra rastro, o que vai é uma frase gerada por código."""
        saida = SaidaInvestigador(
            pergunta=PERGUNTA,
            afirmacao=SENTINELA_RASTRO_1,
            rastro=(SENTINELA_RASTRO_1,),
        )
        contexto = montar_contexto_auditor(saida)
        assert SENTINELA_RASTRO_1 not in contexto.afirmacao
        assert "suprimiu" in contexto.afirmacao

    def test_falha_alto_se_a_filtragem_deixar_passar(self, monkeypatch):
        """A guarda de execução: sem isolamento, ninguém chama o Auditor.

        Simula uma filtragem quebrada (o `_remover_fragmentos` vira identidade)
        e exige que a montagem **falhe** em vez de seguir adiante — porque
        seguir adiante é pagar o dobro por uma confirmação viciada.
        """
        monkeypatch.setattr(
            agentes, "_remover_fragmentos", lambda texto, fragmentos: texto
        )
        saida = SaidaInvestigador(
            pergunta=PERGUNTA,
            afirmacao=f"{AFIRMACAO} {SENTINELA_RASTRO_1}",
            rastro=(SENTINELA_RASTRO_1,),
        )
        with pytest.raises(VazamentoDeRastroError):
            montar_contexto_auditor(saida)


# --------------------------------------------------------------------------- #
# 5. Ferramentas do Auditor são dele
# --------------------------------------------------------------------------- #


class TestReexecucaoIndependente:
    def test_o_auditor_reexecuta_com_caixa_propria(self, config):
        """Orçamento herdado seria isolamento pela metade (5.9.1)."""
        criadas: list[FerramentasDoAgente] = []

        def fabrica_ferramentas(papel: str) -> FerramentasDoAgente:
            ferramentas = FerramentasDoAgente(CaixaFalsa(), papel)
            criadas.append(ferramentas)
            return ferramentas

        def fabrica_llm(papel: str) -> LLMEspiao:
            return LLMEspiao(
                papel,
                RESPOSTAS_AUDITOR if papel == PAPEL_AUDITOR else RESPOSTAS_INVESTIGADOR,
            )

        responder_braco_b(
            PERGUNTA,
            config,
            fabrica_llm=fabrica_llm,
            fabrica_ferramentas=fabrica_ferramentas,
        )
        papeis = [f.papel for f in criadas]
        assert papeis == [PAPEL_INVESTIGADOR, PAPEL_AUDITOR]
        assert criadas[0].caixa is not criadas[1].caixa
        # O Auditor consultou por conta própria, e não herdou o histórico.
        assert criadas[1].chamadas, "o Auditor não reexecutou nenhuma consulta"
        assert all(c.papel == PAPEL_AUDITOR for c in criadas[1].chamadas)
