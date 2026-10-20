"""Os dois achados da rodada real dos agentes no chat (19/10), travados.

1. **RN02 com rótulo.** O Investigador escreveu "margem financeira gerencial de
   R$ 17,2 bilhões" para o Itaú no 3T2025. O número estava no trecho
   recuperado, e era "Despesas não decorrentes de juros": o chunk abre em
   "juros\\nR$ 17,2 bi" e o rótulo ficou no anterior. A RN02 dos agentes só
   perguntava se o número existia. `valores_com_rotulo_trocado` pergunta também
   de que métrica ele é, com o tokenizador e o parser de trecho do caminho livre.
2. **`confirma` responde por cada fonte citada.** O Auditor confirmou "a faixa
   de porte e a taxa histórica no modelo" tendo reexecutado só o painel.

As contraprovas travam o que a correção não pode custar: número certo sob o
rótulo certo continua passando, inclusive pela faixa do modelo, pelo filtro do
SQL e pela oração que não nomeia métrica.

Sem rede, sem LLM e sem índice: os duplos vêm de `tests/test_agentes.py`.
"""

from __future__ import annotations

import pytest

from src import agentes
from src.agentes import (
    FONTE_MODELO,
    FONTE_PAINEL,
    FONTE_RELEASE,
    MARCADORES_RASTRO,
    PAPEL_AUDITOR,
    PAPEL_INVESTIGADOR,
    VEREDITO_CONFIRMA,
    VEREDITO_CONTESTA,
    VEREDITO_NAO_REPRODUZ,
    VIOLACAO_RN02_ROTULO_TROCADO,
    ContextoAuditor,
    FerramentasDoAgente,
    SaidaInvestigador,
    conferir_isolamento,
    fonte_da_citacao,
    instrucao_auditor,
    instrucao_corretiva_auditor,
    responder_braco_b,
    valores_com_rotulo_trocado,
    verificar_regras_agente,
)
from src.config import Config
from src.ferramentas import FERRAMENTAS_DO_PRODUTO, FERRAMENTA_MODELO
from src.projecao import consulta_do_modelo
from tests.test_agentes import (
    ACAO_COBERTURA,
    ACAO_SQL,
    CITACAO,
    PERGUNTA,
    CaixaFalsa,
    final,
    montar_fabricas,
    saida_valida,
)
from tests.test_agentes_no_chat import PANORAMA

PERGUNTA_ITAU = (
    "O que o release do Itaú diz sobre a margem financeira gerencial no 3T2025?"
)
CITACAO_RELEASE_ITAU = "release itau_release_3T2025 · ITAU · 3T2025 · p. 8"

# O trecho como a recuperação o devolveu na rodada real (cabeçalho contextual
# + o começo do chunk, com o rótulo cortado no anterior).
TRECHO_CORTADO = (
    "[ITAU | itau_release_3T2025 | 3T2025 | págs. 8–10]\n"
    "juros\n"
    "R$ 17,2 bi\n"
    "+4,0%\n"
    "3T25\n"
)
TRECHO_COM_ROTULO = (
    "[ITAU | itau_release_3T2025 | 3T2025 | págs. 8–10]\n"
    "Margem financeira gerencial R$ 17,2 bi\n"
)


class CaixaItau(CaixaFalsa):
    def __init__(self, texto: str = TRECHO_CORTADO, **kw):
        super().__init__(**kw)
        self.texto = texto

    def buscar_trechos(self, pergunta: str, top_k=None) -> list:
        self._reservar("buscar_trechos", "1 trecho(s)")
        return [
            {
                "id": "itau_release_3T2025_0020",
                "empresa": "ITAU",
                "documento": "itau_release_3T2025",
                "trimestre": "3T2025",
                "pagina_inicio": 8,
                "pagina_fim": 10,
                "texto": self.texto,
                "score": 0.8,
                "origem": "semantica",
            }
        ]


class CaixaComModelo(CaixaFalsa):
    def consultar_modelo_prejuizo(self, ativo_total_reais=None, cd_cvm=None):
        self._reservar(FERRAMENTA_MODELO, "panorama 3T2025")
        return consulta_do_modelo(PANORAMA, ativo_total_reais=ativo_total_reais)


def _ferramentas(caixa, *chamadas, nomes=None) -> FerramentasDoAgente:
    ferramentas = FerramentasDoAgente(
        caixa, PAPEL_INVESTIGADOR, *(() if nomes is None else (nomes,))
    )
    for nome, argumentos in chamadas:
        ferramentas.executar(nome, **argumentos)
    return ferramentas


def _saida(afirmacao: str, citacoes=(CITACAO,)) -> SaidaInvestigador:
    return SaidaInvestigador(
        pergunta=PERGUNTA,
        afirmacao=afirmacao,
        citacoes=tuple(citacoes),
        comportamento="resposta_completa",
    )


# --------------------------------------------------------------------------- #
# 1. RN02 com rótulo
# --------------------------------------------------------------------------- #


class TestRotuloDoValor:
    def test_o_caso_do_itau_vira_violacao(self):
        """A afirmação da rodada real, contra o trecho da rodada real."""
        ferramentas = _ferramentas(
            CaixaItau(), ("buscar_trechos", {"pergunta": "margem financeira gerencial"})
        )
        saida = _saida(
            "No release do 3T2025, o Itaú reportou margem financeira gerencial de "
            "R$ 17,2 bilhões (crescimento de 4,0% em relação ao 2T2025).",
            citacoes=(CITACAO_RELEASE_ITAU,),
        )
        violacoes = verificar_regras_agente(saida, ferramentas)
        assert violacoes == (VIOLACAO_RN02_ROTULO_TROCADO,)
        assert "margem financeira" in valores_com_rotulo_trocado(saida, ferramentas)[0]

    def test_o_mesmo_numero_sob_o_rotulo_certo_passa(self):
        ferramentas = _ferramentas(
            CaixaItau(TRECHO_COM_ROTULO),
            ("buscar_trechos", {"pergunta": "margem financeira gerencial"}),
        )
        saida = _saida(
            "No release do 3T2025, o Itaú reportou margem financeira gerencial de "
            "R$ 17,2 bilhões.",
            citacoes=(CITACAO_RELEASE_ITAU,),
        )
        assert verificar_regras_agente(saida, ferramentas) == ()

    def test_a_unidade_nao_empresta_rotulo(self):
        """O único token do número cortado era "bi": escrever "17,2 bi" na
        resposta não pode bastar para casar."""
        ferramentas = _ferramentas(
            CaixaItau(), ("buscar_trechos", {"pergunta": "margem"})
        )
        saida = _saida(
            "A margem financeira do Itaú foi de R$ 17,2 bi no 3T2025.",
            citacoes=(CITACAO_RELEASE_ITAU,),
        )
        assert VIOLACAO_RN02_ROTULO_TROCADO in verificar_regras_agente(saida, ferramentas)

    def test_linha_do_painel_de_outra_conta_nao_lastreia_a_metrica(self):
        class CaixaAtivo(CaixaFalsa):
            def consultar_cvm(self, sql):
                self._reservar("consultar_cvm", "1 linha(s)")
                return {
                    "sql": sql,
                    "colunas": ["cd_cvm", "trimestre", "conceito", "valor_reais"],
                    "linhas": [["080217", "1T2026", "ativo_total", 417547000.0]],
                    "total_linhas": 1,
                }

        ferramentas = _ferramentas(CaixaAtivo(), ("consultar_cvm", {"sql": "SELECT 1"}))
        saida = _saida(
            "O lucro consolidado do INTER & CO, INC. (CD_CVM 080217) no 1T2026 foi "
            "de R$ 417,5 milhões."
        )
        assert VIOLACAO_RN02_ROTULO_TROCADO in verificar_regras_agente(saida, ferramentas)

    def test_linha_do_painel_da_mesma_conta_passa(self):
        ferramentas = _ferramentas(CaixaFalsa(), ("consultar_cvm", {"sql": "SELECT 1"}))
        saida = _saida(saida_valida()["afirmacao"])
        assert verificar_regras_agente(saida, ferramentas) == ()

    def test_o_rotulo_do_filtro_sql_vale_quando_a_linha_nao_nomeia(self):
        """`SELECT valor_reais ... WHERE conceito = 'lucro…'`: o rótulo está
        no filtro. Sem ler o literal, a consulta mais enxuta seria acusada."""

        class CaixaSoValor(CaixaFalsa):
            def consultar_cvm(self, sql):
                self._reservar("consultar_cvm", "1 linha(s)")
                return {
                    "sql": sql,
                    "colunas": ["valor_reais"],
                    "linhas": [[417547000.0]],
                    "total_linhas": 1,
                }

        sql = (
            "SELECT valor_reais FROM fatos_semanticos WHERE cd_cvm = '080217' "
            "AND conceito = 'lucro_liquido_consolidado'"
        )
        ferramentas = _ferramentas(CaixaSoValor(), ("consultar_cvm", {"sql": sql}))
        saida = _saida(saida_valida()["afirmacao"])
        # Só a regra do rótulo: a linha sem célula de texto não dá rótulo
        # CITÁVEL, e a RN01 a cobra à parte (`rotulos_de_evidencia`).
        assert valores_com_rotulo_trocado(saida, ferramentas) == ()

    def test_filtro_com_dois_conceitos_nao_empresta_rotulo_a_linha_que_nomeia(self):
        """Com o conceito na linha, os literais do SQL não entram: senão a
        linha do ativo herdaria o rótulo do lucro pelo `IN (...)`."""

        class CaixaDuasLinhas(CaixaFalsa):
            def consultar_cvm(self, sql):
                self._reservar("consultar_cvm", "2 linha(s)")
                return {
                    "sql": sql,
                    "colunas": ["conceito", "valor_reais"],
                    "linhas": [["ativo_total", 417547000.0], ["lucro_liquido_consolidado", 12.0]],
                    "total_linhas": 2,
                }

        sql = (
            "SELECT conceito, valor_reais FROM fatos_semanticos WHERE conceito IN "
            "('ativo_total', 'lucro_liquido_consolidado')"
        )
        ferramentas = _ferramentas(CaixaDuasLinhas(), ("consultar_cvm", {"sql": sql}))
        saida = _saida(
            "O lucro consolidado do INTER & CO, INC. (CD_CVM 080217) no 1T2026 foi "
            "de R$ 417,5 milhões."
        )
        assert VIOLACAO_RN02_ROTULO_TROCADO in verificar_regras_agente(saida, ferramentas)

    def test_marcador_de_nota_na_primeira_celula_nao_rouba_o_rotulo(self):
        """A linha real do release do Itaú 4T2025 (p. 5): o parser do caminho
        livre rotulava o 12.317 com "A4", e a resposta certa era acusada.
        Achado na reexecução das rodadas gravadas
        (`scripts/medir_guarda_rotulo_agentes.py`)."""
        texto = (
            "[ITAU | itau_release_4T2025 | 4T2025 | pág. 5]\n"
            "|  Em R$ milhões (exceto onde indicado) |   | 4T25 | 3T25 | 4T24 |\n"
            "| --- | --- | --- | --- | --- |\n"
            "|  A4 | Resultado Recorrente Gerencial | 12.317 | 11.876 | 10.884 |\n"
        )
        ferramentas = _ferramentas(CaixaItau(texto), ("buscar_trechos", {"pergunta": "lucro"}))
        saida = _saida(
            "O release dos resultados 4T25 reporta Resultado Recorrente Gerencial "
            "de R$ 12.317 milhões.",
            citacoes=("release itau_release_4T2025 · ITAU · 4T2025 · p. 5",),
        )
        assert valores_com_rotulo_trocado(saida, ferramentas) == ()

    def test_oracao_sem_metrica_nao_e_julgada(self):
        """Sem métrica nomeada não há rótulo para trocar; o valor segue
        julgado só pela RN02 sem rótulo."""
        ferramentas = _ferramentas(
            CaixaItau(), ("buscar_trechos", {"pergunta": "release"})
        )
        saida = _saida(
            "O release do Itaú no 3T2025 registra R$ 17,2 bilhões na página 8.",
            citacoes=(CITACAO_RELEASE_ITAU,),
        )
        assert valores_com_rotulo_trocado(saida, ferramentas) == ()

    def test_faixa_do_modelo_sem_ativo_informado_passa(self):
        """Os limites do regime por porte são de ativo, e a chave diz isso
        (`ativo_minimo_reais`). Com `limite_inferior_reais` a frase correta
        abaixo era acusada: a chave não nomeava métrica nenhuma."""
        ferramentas = _ferramentas(
            CaixaComModelo(),
            (FERRAMENTA_MODELO, {}),
            nomes=FERRAMENTAS_DO_PRODUTO,
        )
        saida = _saida(
            "Companhias com ativo entre R$ 10 bi e R$ 100 bi tiveram prejuízo em "
            "21,8% dos trimestres do painel.",
            citacoes=("Modelo preditivo · panorama 3T2025 · regime por porte",),
        )
        assert valores_com_rotulo_trocado(saida, ferramentas) == ()

    def test_as_tres_respostas_da_rodada_real_que_estavam_certas_passam(self):
        """A resposta do Inter, como saiu na rodada real, sobre o duplo."""

        class CaixaInter(CaixaComModelo):
            def consultar_cvm(self, sql):
                self._reservar("consultar_cvm", "3 linha(s)")
                return {
                    "sql": sql,
                    "colunas": ["trimestre", "conceito", "valor_reais"],
                    "linhas": [
                        ["3T2025", "lucro_liquido_consolidado", 356005000.0],
                        ["3T2025", "lucro_liquido_controladores", 336345000.0],
                        ["3T2025", "ativo_total", 91808508000.0],
                    ],
                    "total_linhas": 3,
                }

        ferramentas = _ferramentas(
            CaixaInter(),
            ("consultar_cvm", {"sql": "SELECT 1"}),
            (FERRAMENTA_MODELO, {"ativo_total_reais": 91808508000.0}),
            nomes=FERRAMENTAS_DO_PRODUTO,
        )
        saida = _saida(
            "No 3T2025, o lucro líquido consolidado da INTER & CO, INC. (CD_CVM "
            "080217) foi de R$ 356.005.000,00 e o lucro líquido atribuível aos "
            "controladores foi de R$ 336.345.000,00, conforme dados arquivados na "
            "CVM. Com um ativo total de R$ 91.808.508.000,00 no mesmo período, a "
            "companhia enquadra-se na faixa de porte de ativo entre R$ 10 bi e "
            "R$ 100 bi, faixa que registrou uma taxa histórica de prejuízo de "
            "21,8% no painel da CVM.",
            citacoes=(
                "CVM · INTER & CO, INC. (CD_CVM 080217) · 3T2025 · lucro_liquido_consolidado",
                "Modelo preditivo · panorama 3T2025 · regime por porte",
            ),
        )
        assert verificar_regras_agente(saida, ferramentas) == ()

    def test_no_braco_b_a_resposta_acusada_nao_vai_ao_auditor(self, config):
        acao = (
            'Thought: o release\nAction: buscar_trechos\n'
            'Action Input: {"pergunta": "margem financeira gerencial"}'
        )
        afirmacao = (
            "No release do 3T2025, o Itaú reportou margem financeira gerencial de "
            "R$ 17,2 bilhões."
        )
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [acao, final(saida_valida(afirmacao=afirmacao, citacoes=[CITACAO_RELEASE_ITAU],
                                      cobertura="ambas", bases=["gerencial"]))],
            respostas_auditor=[final({"veredito": "confirma"})],
            caixa=CaixaItau(),
        )
        resposta = responder_braco_b(
            PERGUNTA_ITAU, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert resposta.violacoes == (VIOLACAO_RN02_ROTULO_TROCADO,)
        assert resposta.recusa is True and resposta.convertida_em_recusa is True
        assert "17,2" not in resposta.resposta
        assert f"llm_{PAPEL_AUDITOR}" not in criados


# --------------------------------------------------------------------------- #
# 2. `confirma` responde por cada fonte citada
# --------------------------------------------------------------------------- #

ACAO_TRECHOS = (
    'Thought: o release\nAction: buscar_trechos\n'
    'Action Input: {"pergunta": "lucro gerencial do Inter"}'
)
ACAO_MODELO = (
    'Thought: o modelo\nAction: consultar_modelo_prejuizo\n'
    'Action Input: {"ativo_total_reais": null, "cd_cvm": null}'
)
CITACAO_RELEASE_INTER = "release inter_release_1T2026 · INTER · 1T2026 · p. 3"
CITACAO_MODELO = "Modelo preditivo · panorama 3T2025 · regime por porte"


def _saida_painel_e_release() -> dict:
    return saida_valida(
        cobertura="ambas",
        afirmacao=(
            "O lucro consolidado do INTER & CO, INC. (CD_CVM 080217) no 1T2026 "
            "foi de R$ 417,5 milhões; o release destaca lucro gerencial de "
            "R$ 430,0 milhões."
        ),
        citacoes=[CITACAO, CITACAO_RELEASE_INTER],
        bases=["contabil_consolidado", "gerencial"],
    )


@pytest.fixture
def config() -> Config:
    return Config()


class TestFonteDaCitacao:
    @pytest.mark.parametrize(
        ("citacao", "fonte"),
        [
            (CITACAO, FONTE_PAINEL),
            ("CVM · ITAU UNIBANCO HOLDING S.A. (CD_CVM 019348) · 3T2025 · lucro_liquido_consolidado", FONTE_PAINEL),
            (CITACAO_RELEASE_ITAU, FONTE_RELEASE),
            ("inter_release_1T2026 · INTER · 1T2026 · p. 3", FONTE_RELEASE),
            (CITACAO_MODELO, FONTE_MODELO),
            ("Modelo preditivo · panorama do painel da CVM", FONTE_MODELO),
            ("nota explicativa sem formato", None),
        ],
    )
    def test_os_tres_formatos_do_prompt(self, citacao, fonte):
        assert fonte_da_citacao(citacao) == fonte


class TestConfirmarCadaFonte:
    def test_confirma_sem_reconsultar_o_release_ganha_um_segundo_tiro_e_cai(self, config):
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_SQL, ACAO_TRECHOS, final(_saida_painel_e_release())],
            respostas_auditor=[ACAO_SQL, final({"veredito": "confirma"})],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        auditor = criados[f"llm_{PAPEL_AUDITOR}"]
        # 1ª passagem (2 chamadas) + corretiva, que repete o roteiro sem
        # consultar o release (o roteiro esgotado devolve o último item).
        assert auditor.chamadas >= 3
        assert resposta.veredito_auditor == VEREDITO_NAO_REPRODUZ
        assert resposta.correcao_aplicada is True
        assert resposta.correcao_resultado == agentes.CORRECAO_FALHOU
        assert "release (buscar_trechos)" in resposta.resposta
        assert resposta.parcial is True

    def test_auditor_que_reconsulta_o_que_faltava_mantem_o_confirma(self, config):
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_SQL, ACAO_TRECHOS, final(_saida_painel_e_release())],
            respostas_auditor=[
                ACAO_SQL,
                final({"veredito": "confirma"}),  # 1ª: só o painel
                ACAO_TRECHOS,                      # corretiva: o release
                final({"veredito": "confirma"}),
            ],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert resposta.veredito_auditor == VEREDITO_CONFIRMA
        assert resposta.correcao_resultado == agentes.CORRECAO_BEM_SUCEDIDA
        feitas = [c.ferramenta for c in criados[f"ferr_{PAPEL_AUDITOR}"].chamadas]
        assert "consultar_cvm" in feitas and "buscar_trechos" in feitas

    def test_confirma_com_todas_as_fontes_nao_gasta_correcao(self, config):
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_SQL, ACAO_TRECHOS, final(_saida_painel_e_release())],
            respostas_auditor=[ACAO_SQL, ACAO_TRECHOS, final({"veredito": "confirma"})],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert criados[f"llm_{PAPEL_AUDITOR}"].chamadas == 3
        assert resposta.veredito_auditor == VEREDITO_CONFIRMA
        assert resposta.correcao_aplicada is False

    def test_contesta_nao_precisa_de_todas_as_fontes(self, config):
        """Uma contraevidência basta para contestar."""
        fabrica_llm, fabrica_ferr, criados = montar_fabricas(
            [ACAO_SQL, ACAO_TRECHOS, final(_saida_painel_e_release())],
            respostas_auditor=[
                ACAO_SQL,
                final({
                    "veredito": "contesta",
                    "justificativa": "o painel devolve outro valor",
                    "contraevidencia": ["fatos_semanticos 080217 1T2026 = 394.788.000"],
                }),
            ],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert criados[f"llm_{PAPEL_AUDITOR}"].chamadas == 2
        assert resposta.veredito_auditor == VEREDITO_CONTESTA

    def test_o_caso_do_inter_no_produto(self, config):
        """A rodada real: confirmou o modelo reexecutando só o painel."""
        afirmacao = (
            "O lucro consolidado do INTER & CO, INC. (CD_CVM 080217) no 1T2026 "
            "foi de R$ 417,5 milhões. Companhias com ativo entre R$ 10 bi e "
            "R$ 100 bi tiveram prejuízo em 21,8% dos trimestres do painel."
        )

        def fabrica_ferr(papel):
            return FerramentasDoAgente(CaixaComModelo(), papel, FERRAMENTAS_DO_PRODUTO)

        fabrica_llm, _, criados = montar_fabricas(
            [ACAO_SQL, ACAO_MODELO, final(saida_valida(afirmacao=afirmacao, citacoes=[CITACAO, CITACAO_MODELO]))],
            respostas_auditor=[
                ACAO_SQL,
                final({"veredito": "confirma"}),  # 1ª: só o painel
                ACAO_MODELO,                       # corretiva: o modelo
                final({"veredito": "confirma"}),
            ],
        )
        resposta = responder_braco_b(
            PERGUNTA, config, fabrica_llm=fabrica_llm, fabrica_ferramentas=fabrica_ferr
        )
        assert resposta.violacoes == ()
        assert resposta.veredito_auditor == VEREDITO_CONFIRMA
        assert resposta.correcao_resultado == agentes.CORRECAO_BEM_SUCEDIDA

    def test_fonte_que_a_caixa_nao_alcanca_rebaixa_sem_segundo_tiro(self):
        """No experimento o Auditor não tem o modelo: pagar uma corretiva para
        ele reconsultar o modelo seria um tiro impossível."""
        contexto = ContextoAuditor(
            pergunta=PERGUNTA,
            afirmacao=saida_valida()["afirmacao"],
            citacoes=(CITACAO, CITACAO_MODELO),
        )
        fabrica_llm, _, criados = montar_fabricas(
            [], respostas_auditor=[ACAO_SQL, final({"veredito": "confirma"})]
        )
        llm = fabrica_llm(PAPEL_AUDITOR)
        ferramentas = FerramentasDoAgente(CaixaFalsa(), PAPEL_AUDITOR)
        veredito = agentes.executar_auditor(contexto, Config(), ferramentas, llm)
        assert llm.chamadas == 2
        assert veredito.veredito == VEREDITO_NAO_REPRODUZ
        assert "modelo preditivo" in veredito.justificativa
        assert veredito.correcao_aplicada is False


class TestTextoDoAuditor:
    def test_a_regra_por_fonte_esta_no_prompt_e_o_modelo_so_no_produto(self):
        contexto = ContextoAuditor(pergunta=PERGUNTA, afirmacao="x", citacoes=(CITACAO,))
        experimento = instrucao_auditor(contexto)
        produto = instrucao_auditor(contexto, com_modelo=True)
        assert "CONFIRMAR É CONFERIR CADA FONTE CITADA" in experimento
        assert "consultar_modelo_prejuizo" not in experimento
        assert "consultar_modelo_prejuizo" in produto

    def test_a_corretiva_por_fonte_nomeia_a_falta_e_nao_vaza_rastro(self):
        saida = SaidaInvestigador(
            pergunta=PERGUNTA,
            afirmacao=saida_valida()["afirmacao"],
            citacoes=(CITACAO, CITACAO_RELEASE_INTER),
            rastro=("passo 1: consultei o painel da CVM e depois o release do Inter",),
        )
        contexto = agentes.montar_contexto_auditor(saida)
        texto = instrucao_corretiva_auditor(
            contexto, faltantes=frozenset({FONTE_RELEASE}), com_modelo=True
        )
        assert "Faltou reconsultar: release (buscar_trechos)" in texto
        assert conferir_isolamento(texto, saida) == ()
        assert not any(m in texto.lower() for m in MARCADORES_RASTRO)
