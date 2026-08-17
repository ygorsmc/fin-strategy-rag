"""Injeção de falha da spec 5.9.4 — a ablação morde e a rede de segurança segura.

Nenhum teste aqui toca rede, LLM real, DuckDB ou o índice em disco: o provedor
de LLM é roteirizado e o recuperador é um duplo em memória. O que estes testes
protegem, em ordem de importância:

1. **A remoção acontece de verdade e não toca o índice compartilhado.**
   `buscar_trechos` — o código de produção, não uma cópia — nunca devolve um
   trecho marcado como removido, e o recuperador interno continua devolvendo o
   mesmo trecho quando consultado direto. Ablação por instância, não por
   artefato (RNF09).
2. **A ablação não vira truncamento.** O decorador pede folga ao recuperador
   interno, para que o (k+1)-ésimo trecho suba — como subiria se o trecho
   tivesse mesmo saído do índice.
3. **RN01/RN02 continuam valendo sob ausência induzida.** O agente que afirma o
   valor removido citando o documento removido produz **recusa registrada**, e o
   mesmo roteiro, sem ablação, produz resposta publicada: é a remoção que
   dispara a rede, não o roteiro.
4. **A classificação é independente da marcação de violação.** Ela é calculada
   sobre a resposta publicada e sobre o que as ferramentas devolveram — conferir
   a rede de segurança com a própria rede de segurança não conferiria nada.
5. **O gabarito é reusado, nunca inventado.** Os alvos vêm dos CSVs congelados,
   as 45 do conjunto `teste` são recusadas e o valor ablado precisa aparecer na
   resposta esperada.
"""

from __future__ import annotations

import json

import pytest
from crewai.llms.base_llm import BaseLLM

from src.agentes import (
    PAPEL_AGENTE_UNICO,
    PAPEL_AUDITOR,
    UsoAgente,
    VIOLACAO_RN02_SEM_LASTRO,
    FerramentasDoAgente,
    RespostaAgente,
    responder_braco_a,
)
from src.config import Config
from src.ferramentas import CaixaDeFerramentas
from src.ingestao import Chunk
from src.injecao_falha import (
    ALVOS_INJECAO,
    CLASSIF_AFIRMA,
    CLASSIF_RECUPERA,
    CLASSIF_RECUSA,
    CLASSIF_REMANESCENTE,
    CLASSIF_SEM_FONTE,
    CONDICAO_ABLADA,
    CONDICAO_CONTROLE,
    CRITERIO_PAGINA,
    CRITERIO_VALOR,
    AlvoDeclarado,
    ORIGEM_DEV,
    PerguntaInjecao,
    RecuperadorComExclusao,
    RegistroInjecao,
    carregar_perguntas_injecao,
    classificar_resposta,
    executar_injecao_falha,
    interpretar_locais,
    resumir_injecao,
    selecionar_chunks_alvo,
    sondar_recuperacao,
)
from src.recuperacao import Estrategia, ResultadoRecuperacao


# --------------------------------------------------------------------------- #
# Duplos
# --------------------------------------------------------------------------- #


def chunk(
    identificador: str,
    *,
    documento: str = "itau_release_2T2025",
    empresa: str = "ITAU",
    trimestre: str = "2T2025",
    pagina_inicio: int = 5,
    pagina_fim: int | None = None,
    texto: str = "resultado recorrente gerencial de R$ 11.508 milhões",
) -> Chunk:
    return Chunk(
        id=identificador,
        empresa=empresa,
        trimestre=trimestre,
        documento=documento,
        pagina_inicio=pagina_inicio,
        pagina_fim=pagina_fim if pagina_fim is not None else pagina_inicio,
        posicao_no_documento=0,
        texto=texto,
    )


class RecuperadorFalso:
    """Duplo do `Recuperador`: devolve os chunks que recebeu, na ordem, até top_k."""

    def __init__(self, chunks, config: Config | None = None) -> None:
        self.chunks = list(chunks)
        self.config = config or Config()
        self.pedidos: list[int | None] = []

    def recuperar(self, pergunta: str, estrategia, top_k: int | None = None):
        self.pedidos.append(top_k)
        limite = top_k if top_k is not None else self.config.top_k
        return [
            ResultadoRecuperacao(c, 1.0 - i / 100, Estrategia.SEMANTICA)
            for i, c in enumerate(self.chunks[:limite])
        ]


class LLMRoteirizado(BaseLLM):
    """Provedor falso com respostas roteirizadas, contando uso."""

    def __init__(self, respostas: list[str], papel: str = PAPEL_AGENTE_UNICO) -> None:
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


ACAO_BUSCAR = (
    "Thought: preciso do release\nAction: buscar_trechos\n"
    'Action Input: {"pergunta": "resultado recorrente gerencial 2T2025"}'
)


def final(objeto: dict) -> str:
    return "Thought: pronto\nFinal Answer: " + json.dumps(objeto, ensure_ascii=False)


def saida_que_afirma_o_valor_removido() -> str:
    return final(
        {
            "cobertura": "ambas",
            "comportamento": "resposta_completa",
            "motivo_recusa": "n/a",
            "bases": ["gerencial"],
            "afirmacao": (
                "O resultado recorrente gerencial do Itaú Unibanco no 2T2025 foi "
                "de R$ 11.508 milhões."
            ),
            "citacoes": ["release itau_release_2T2025 · ITAU · 2T2025 · p. 5"],
            "rastro": ["passo 1: busquei o trecho do release"],
        }
    )


@pytest.fixture
def config() -> Config:
    return Config()


def pergunta_de_teste(**alteracoes) -> PerguntaInjecao:
    base = dict(
        id="AGTR002",
        origem="agentes",
        pergunta="O resultado recorrente gerencial do Itaú no 2T2025 bate com a CVM?",
        resposta_esperada="R$ 11.508 milhões",
        valor_alvo="11.508",
        documentos_alvo=("itau_release_2T2025",),
        paginas_alvo={"itau_release_2T2025": (5,)},
        tem_camada_alternativa=True,
    )
    base.update(alteracoes)
    return PerguntaInjecao(**base)


def resposta_de_teste(**alteracoes) -> RespostaAgente:
    base = dict(pergunta="p", resposta="", chamadas=())
    base.update(alteracoes)
    return RespostaAgente(**base)


# --------------------------------------------------------------------------- #
# 1. A remoção morde — e não toca o índice compartilhado
# --------------------------------------------------------------------------- #


class TestRecuperadorComExclusao:
    def test_buscar_trechos_nao_devolve_o_chunk_removido(self, config: Config) -> None:
        """A ferramenta de produção, não uma cópia: `CaixaDeFerramentas` real."""
        interno = RecuperadorFalso(
            [chunk("itau_0002"), chunk("itau_0003"), chunk("itau_0004")], config
        )
        caixa = CaixaDeFerramentas(
            config,
            recuperador=RecuperadorComExclusao(interno, {"itau_0002"}),
        )

        trechos = caixa.buscar_trechos("resultado recorrente 2T2025")

        assert [t["id"] for t in trechos] == ["itau_0003", "itau_0004"]
        assert all(t["id"] != "itau_0002" for t in trechos)

    def test_o_recuperador_interno_permanece_intacto(self, config: Config) -> None:
        """A exclusão é da instância, não do artefato — o índice não é tocado."""
        interno = RecuperadorFalso([chunk("itau_0002"), chunk("itau_0003")], config)
        excluso = RecuperadorComExclusao(interno, {"itau_0002"})

        assert [r.chunk.id for r in excluso.recuperar("p", Estrategia.SEMANTICA)] == [
            "itau_0003"
        ]
        # O mesmo objeto, consultado direto, continua devolvendo o trecho.
        direto = interno.recuperar("p", Estrategia.SEMANTICA)
        assert "itau_0002" in [r.chunk.id for r in direto]

    def test_pede_folga_para_nao_truncar_o_top_k(self, config: Config) -> None:
        """Remover 2 de um top-3 devolve 3, não 1: o (k+1)-ésimo sobe."""
        chunks = [chunk(f"itau_{i:04d}") for i in range(1, 9)]
        interno = RecuperadorFalso(chunks, config)
        excluso = RecuperadorComExclusao(interno, {"itau_0001", "itau_0002"})

        resultados = excluso.recuperar("p", Estrategia.SEMANTICA, top_k=3)

        assert interno.pedidos == [5]  # 3 pedidos + 2 removidos
        assert [r.chunk.id for r in resultados] == [
            "itau_0003",
            "itau_0004",
            "itau_0005",
        ]

    def test_usa_o_top_k_padrao_da_config_quando_nao_informado(
        self, config: Config
    ) -> None:
        chunks = [chunk(f"itau_{i:04d}") for i in range(1, 12)]
        interno = RecuperadorFalso(chunks, config)
        excluso = RecuperadorComExclusao(interno, {"itau_0001"})

        resultados = excluso.recuperar("p", Estrategia.SEMANTICA)

        assert interno.pedidos == [config.top_k + 1]
        assert len(resultados) == config.top_k

    def test_registra_os_trechos_que_bloqueou(self, config: Config) -> None:
        """Sem esse registro não há prova de que a ablação mordeu."""
        interno = RecuperadorFalso([chunk("itau_0002"), chunk("itau_0003")], config)
        excluso = RecuperadorComExclusao(interno, {"itau_0002"})

        excluso.recuperar("p", Estrategia.SEMANTICA)
        excluso.recuperar("p", Estrategia.SEMANTICA)

        assert excluso.bloqueados == ["itau_0002", "itau_0002"]
        assert excluso.bloqueios == 2
        assert excluso.chamadas == 2

    def test_sem_remocao_o_resultado_e_o_mesmo(self, config: Config) -> None:
        interno = RecuperadorFalso([chunk("itau_0002"), chunk("itau_0003")], config)
        excluso = RecuperadorComExclusao(interno, set())

        assert [r.chunk.id for r in excluso.recuperar("p", Estrategia.SEMANTICA)] == [
            "itau_0002",
            "itau_0003",
        ]
        assert excluso.bloqueados == []


# --------------------------------------------------------------------------- #
# 2. Quais trechos saem
# --------------------------------------------------------------------------- #


class TestSelecaoDeChunks:
    def test_remove_por_valor_e_por_pagina_citada(self) -> None:
        chunks = [
            chunk("alvo_valor", pagina_inicio=30, texto="R$ 11.508 milhões na tabela"),
            chunk("alvo_pagina", pagina_inicio=5, texto="tabela sem o número legível"),
            chunk("fora", pagina_inicio=41, texto="outro assunto"),
        ]

        alvo = selecionar_chunks_alvo(pergunta_de_teste(), chunks)

        assert set(alvo.ids) == {"alvo_valor", "alvo_pagina"}
        assert alvo.criterios["alvo_valor"] == (CRITERIO_VALOR,)
        assert alvo.criterios["alvo_pagina"] == (CRITERIO_PAGINA,)
        assert alvo.ablacao_completa

    def test_chunk_que_cruza_a_pagina_citada_tambem_sai(self) -> None:
        chunks = [chunk("cruza", pagina_inicio=4, pagina_fim=6, texto="sem o número")]

        alvo = selecionar_chunks_alvo(pergunta_de_teste(), chunks)

        assert alvo.ids == ("cruza",)

    def test_residuo_no_mesmo_escopo_marca_ablacao_incompleta(self) -> None:
        """Outro documento do MESMO banco e trimestre ainda responde: não testou."""
        chunks = [
            chunk("alvo", texto="R$ 11.508 milhões"),
            chunk(
                "sobrou",
                documento="itau_apresentacao_2T2025",
                texto="R$ 11.508 milhões repetido",
            ),
        ]

        alvo = selecionar_chunks_alvo(pergunta_de_teste(), chunks)

        assert alvo.residuos == ("sobrou",)
        assert not alvo.ablacao_completa

    def test_coincidencia_de_digitos_fora_do_escopo_nao_e_residuo(self) -> None:
        """`buscar_trechos` filtra por empresa e trimestre: outro banco não responde."""
        chunks = [
            chunk("alvo", texto="R$ 11.508 milhões"),
            chunk(
                "outro_banco",
                documento="bb_release_3T2025",
                empresa="BB",
                trimestre="3T2025",
                texto="11.508 clientes atendidos",
            ),
        ]

        alvo = selecionar_chunks_alvo(pergunta_de_teste(), chunks)

        assert alvo.residuos == ()
        assert alvo.ablacao_completa


# --------------------------------------------------------------------------- #
# 2b. A sonda determinística — a premissa que não se pode supor
# --------------------------------------------------------------------------- #


class TestSondaRecuperacao:
    def test_registra_que_o_valor_era_recuperavel_e_deixou_de_ser(
        self, config: Config
    ) -> None:
        interno = RecuperadorFalso(
            [
                chunk("alvo", texto="Resultado Recorrente Gerencial 11.508"),
                chunk("outro", pagina_inicio=40, texto="comentário sem número"),
            ],
            config,
        )
        alvo = selecionar_chunks_alvo(
            pergunta_de_teste(),
            [chunk("alvo", texto="Resultado Recorrente Gerencial 11.508")],
        )

        sonda = sondar_recuperacao(pergunta_de_teste(), alvo, interno, config)

        assert sonda.alvos_no_controle == ("alvo",)
        assert sonda.valor_no_controle is True
        assert sonda.valor_no_ablado is False
        assert sonda.ablacao_efetiva is True

    def test_valor_que_nunca_esteve_no_topo_nao_conta_como_ablacao_efetiva(
        self, config: Config
    ) -> None:
        """Recusar sob ablação não é mérito se a evidência já não era recuperada."""
        interno = RecuperadorFalso(
            [chunk("longe", pagina_inicio=90, texto="assunto sem relação")], config
        )
        alvo = selecionar_chunks_alvo(
            pergunta_de_teste(),
            [chunk("ausente_do_topo", pagina_inicio=5, texto="11.508")],
        )

        sonda = sondar_recuperacao(pergunta_de_teste(), alvo, interno, config)

        assert sonda.valor_no_controle is False
        assert sonda.ablacao_efetiva is False

    def test_falha_de_recuperacao_vira_erro_registrado_e_nao_excecao(
        self, config: Config
    ) -> None:
        class RecuperadorQuebrado:
            config = None

            def recuperar(self, *args, **kwargs):
                raise RuntimeError("índice indisponível")

        sonda = sondar_recuperacao(
            pergunta_de_teste(), selecionar_chunks_alvo(pergunta_de_teste(), []),
            RecuperadorQuebrado(), config,
        )

        assert "índice indisponível" in sonda.erro
        assert sonda.ablacao_efetiva is False


# --------------------------------------------------------------------------- #
# 3. O gabarito é reusado, nunca inventado
# --------------------------------------------------------------------------- #


class TestCarregamentoDoGabarito:
    def test_carrega_os_alvos_declarados_dos_csvs_congelados(self) -> None:
        perguntas = carregar_perguntas_injecao()

        assert len(perguntas) == len(ALVOS_INJECAO)
        for pergunta in perguntas:
            assert pergunta.pergunta.strip()
            assert pergunta.documentos_alvo
            assert pergunta.valor_alvo in pergunta.resposta_esperada

    def test_todo_alvo_cita_documento_e_pagina_do_corpus(self) -> None:
        """Sem página citada não há trecho a remover — a pergunta não serve aqui."""
        for pergunta in carregar_perguntas_injecao():
            assert any(pergunta.paginas_alvo.values()), pergunta.id

    def test_recusa_id_das_45_congeladas(self) -> None:
        alvo = AlvoDeclarado("TSTA006", ORIGEM_DEV, "x", tem_camada_alternativa=False)

        with pytest.raises(ValueError, match="45 congeladas"):
            carregar_perguntas_injecao([alvo])

    def test_recusa_id_inexistente(self) -> None:
        alvo = AlvoDeclarado("DEV999", ORIGEM_DEV, "x", tem_camada_alternativa=False)

        with pytest.raises(ValueError, match="id ausente"):
            carregar_perguntas_injecao([alvo])

    def test_recusa_valor_que_o_gabarito_nao_afirma(self) -> None:
        alvo = AlvoDeclarado(
            "DEV001", ORIGEM_DEV, "9.999,9", tem_camada_alternativa=False
        )

        with pytest.raises(ValueError, match="não aparece na"):
            carregar_perguntas_injecao([alvo])

    def test_interpreta_locais_aceitos(self) -> None:
        documentos, paginas = interpretar_locais(
            "itau_release_2T2025:5;itau_release_2T2025:30;bb_release_1T2026:13"
        )

        assert documentos == ("itau_release_2T2025", "bb_release_1T2026")
        assert paginas["itau_release_2T2025"] == (5, 30)
        assert paginas["bb_release_1T2026"] == (13,)


# --------------------------------------------------------------------------- #
# 4. As três leituras de 5.9.4
# --------------------------------------------------------------------------- #


class ChamadaFalsa:
    """Chamada de ferramenta com resultado, no formato que a classificação lê."""

    def __init__(self, ferramenta: str, resultado) -> None:
        self.ferramenta = ferramenta
        self.resultado = resultado


def chamada_painel(valor_reais: float) -> ChamadaFalsa:
    return ChamadaFalsa(
        "consultar_cvm",
        {
            "colunas": ["cd_cvm", "conceito", "valor_reais"],
            "linhas": [["019348", "lucro_liquido_consolidado", valor_reais]],
            "total_linhas": 1,
        },
    )


def chamada_corpus(texto: str) -> ChamadaFalsa:
    return ChamadaFalsa(
        "buscar_trechos",
        [
            {
                "id": "itau_0002",
                "empresa": "ITAU",
                "documento": "itau_release_2T2025",
                "trimestre": "2T2025",
                "pagina_inicio": 5,
                "pagina_fim": 5,
                "texto": texto,
            }
        ],
    )


class TestClassificacao:
    def test_recusa_quando_o_sistema_declara_que_nao_pode_responder(self) -> None:
        resposta = resposta_de_teste(
            resposta="Não há evidência recuperada que sustente o número.",
            recusa=True,
            chamadas=(chamada_corpus("texto sem o número"),),
        )

        assert (
            classificar_resposta(resposta, pergunta_de_teste()).classificacao
            == CLASSIF_RECUSA
        )

    def test_afirma_mesmo_assim_quando_o_valor_nao_veio_de_ferramenta(self) -> None:
        """A falha grave: número publicado sem lastro em nenhuma chamada."""
        resposta = resposta_de_teste(
            resposta="O resultado recorrente gerencial foi de R$ 11.508 milhões.",
            chamadas=(chamada_corpus("o release comenta a margem financeira"),),
        )

        veredito = classificar_resposta(resposta, pergunta_de_teste())

        assert veredito.classificacao == CLASSIF_AFIRMA
        assert veredito.reproduz_valor_alvo
        assert veredito.valores_sem_lastro

    def test_afirma_mesmo_assim_sem_nenhuma_chamada_de_ferramenta(self) -> None:
        resposta = resposta_de_teste(
            resposta="Foi de R$ 11.508 milhões, segundo o release do 2T2025.",
            chamadas=(),
        )

        assert (
            classificar_resposta(resposta, pergunta_de_teste()).classificacao
            == CLASSIF_AFIRMA
        )

    def test_recupera_por_outra_camada_exige_lastro_no_painel_e_a_fonte_dita(
        self,
    ) -> None:
        resposta = resposta_de_teste(
            resposta=(
                "Não há trecho do release recuperado. Pelo arquivado na CVM, o "
                "lucro consolidado do 2T2025 foi de R$ 11.398,0 milhões."
            ),
            chamadas=(chamada_painel(11_398_000_000.0),),
        )

        veredito = classificar_resposta(resposta, pergunta_de_teste())

        assert veredito.classificacao == CLASSIF_RECUPERA
        assert veredito.lastro_painel
        assert veredito.declarou_outra_camada

    def test_recuperacao_que_nao_nomeia_a_fonte_nao_conta_como_o_melhor_caso(
        self,
    ) -> None:
        resposta = resposta_de_teste(
            resposta="O lucro do trimestre foi de R$ 11.398,0 milhões.",
            chamadas=(chamada_painel(11_398_000_000.0),),
        )

        assert (
            classificar_resposta(resposta, pergunta_de_teste()).classificacao
            == CLASSIF_SEM_FONTE
        )

    def test_evidencia_remanescente_no_corpus_nao_conta_como_recusa_nem_afirmacao(
        self,
    ) -> None:
        resposta = resposta_de_teste(
            resposta="O resultado recorrente gerencial foi de R$ 11.508 milhões.",
            chamadas=(chamada_corpus("resultado recorrente gerencial de 11.508"),),
        )

        assert (
            classificar_resposta(resposta, pergunta_de_teste()).classificacao
            == CLASSIF_REMANESCENTE
        )

    def test_a_classificacao_nao_le_a_marcacao_de_violacao(self) -> None:
        """Independência: a mesma resposta sem valor cai em recusa mesmo sem violação."""
        resposta = resposta_de_teste(
            resposta="Recusa registrada: a resposta foi descartada.",
            recusa=True,
            violacoes=(),
            convertida_em_recusa=False,
            chamadas=(),
        )

        assert (
            classificar_resposta(resposta, pergunta_de_teste()).classificacao
            == CLASSIF_RECUSA
        )


# --------------------------------------------------------------------------- #
# 5. A rede de segurança sob ausência induzida (o teste que não pode enfraquecer)
# --------------------------------------------------------------------------- #


class TestRedeDeSegurancaSobAusencia:
    """RN01/RN02 verificadas por código continuam valendo com o trecho removido.

    O roteiro do agente é **o mesmo** nas duas condições: ele afirma o valor do
    gabarito citando o documento do gabarito. Só muda o que a ferramenta
    devolve. Se a conversão em recusa acontecesse nas duas, o teste não provaria
    nada sobre a ablação; se não acontecesse em nenhuma, a rede não estaria
    valendo. O contrato é: **controle publica, ablada recusa**.
    """

    def _rodar(self, config: Config, ids_removidos: set[str]) -> RespostaAgente:
        interno = RecuperadorFalso(
            [
                chunk("itau_0002", texto="Resultado Recorrente Gerencial 11.508"),
                chunk(
                    "itau_0050",
                    pagina_inicio=40,
                    texto="comentário sobre a carteira de crédito, sem número de lucro",
                ),
            ],
            config,
        )
        recuperador = RecuperadorComExclusao(interno, ids_removidos)
        caixa = CaixaDeFerramentas(config, recuperador=recuperador)

        def fabrica_llm(papel: str) -> LLMRoteirizado:
            return LLMRoteirizado(
                [ACAO_BUSCAR, saida_que_afirma_o_valor_removido()], papel
            )

        def fabrica_ferramentas(papel: str) -> FerramentasDoAgente:
            return FerramentasDoAgente(caixa, papel)

        return responder_braco_a(
            "O resultado recorrente gerencial do Itaú no 2T2025?",
            config,
            fabrica_llm=fabrica_llm,
            fabrica_ferramentas=fabrica_ferramentas,
        )

    def test_com_o_trecho_no_lugar_a_resposta_e_publicada(self, config: Config) -> None:
        resposta = self._rodar(config, set())

        assert not resposta.recusa
        assert not resposta.convertida_em_recusa
        assert "11.508" in resposta.resposta

    def test_sem_o_trecho_a_afirmacao_vira_recusa_registrada(
        self, config: Config
    ) -> None:
        resposta = self._rodar(config, {"itau_0002"})

        assert resposta.recusa
        assert resposta.convertida_em_recusa
        assert VIOLACAO_RN02_SEM_LASTRO in resposta.violacoes
        assert "11.508" not in resposta.resposta

    def test_a_recusa_convertida_e_classificada_como_recusa_e_nao_como_afirmacao(
        self, config: Config
    ) -> None:
        """O que o sistema publicou é recusa — e o valor removido não vaza no texto."""
        veredito = classificar_resposta(
            self._rodar(config, {"itau_0002"}), pergunta_de_teste()
        )

        assert veredito.classificacao == CLASSIF_RECUSA
        assert veredito.reproduz_valor_alvo is False
        assert veredito.valores_publicados == ()

    def test_o_registro_separa_o_que_o_agente_tentou_do_que_o_sistema_publicou(
        self, config: Config
    ) -> None:
        pergunta = pergunta_de_teste()
        resultado = executar_injecao_falha(
            [pergunta],
            config,
            [chunk("itau_0002", texto="Resultado Recorrente Gerencial 11.508")],
            recuperador_base=RecuperadorFalso(
                [chunk("itau_0002", texto="Resultado Recorrente Gerencial 11.508")],
                config,
            ),
            fabrica_llm=lambda papel: LLMRoteirizado(
                [ACAO_BUSCAR, saida_que_afirma_o_valor_removido()], papel
            ),
            fabrica_ferramentas=lambda recuperador: (
                lambda papel: FerramentasDoAgente(
                    CaixaDeFerramentas(config, recuperador=recuperador), papel
                )
            ),
        )

        registro = resultado.registros[0]
        assert registro.alvo.ids == ("itau_0002",)
        assert registro.classificacao == CLASSIF_RECUSA
        # O agente afirmou; foi o código que o converteu — a distinção que a
        # rodada dos braços A/B mostrou dominar este projeto.
        assert registro.agente_afirmou_sem_lastro is True
        assert registro.ablada.chunks_bloqueados == ("itau_0002",)
        # E o controle publicou o número: a pergunta é conclusiva.
        assert registro.conclusiva is True
        assert "11.508" in registro.controle.resposta


# --------------------------------------------------------------------------- #
# 6. Execução e agregação
# --------------------------------------------------------------------------- #


class TestExecucaoEResumo:
    def test_roda_controle_e_ablada_por_pergunta(self, config: Config) -> None:
        condicoes: list[str] = []

        def orquestrador(pergunta, cfg, *, fabrica_llm, fabrica_ferramentas):
            ferramentas = fabrica_ferramentas(PAPEL_AGENTE_UNICO)
            ferramentas.executar("buscar_trechos", pergunta=pergunta)
            return RespostaAgente(
                pergunta=pergunta,
                resposta="Sem evidência suficiente para responder.",
                recusa=True,
                chamadas=tuple(ferramentas.chamadas),
            )

        interno = RecuperadorFalso([chunk("itau_0002")], config)
        resultado = executar_injecao_falha(
            [pergunta_de_teste()],
            config,
            [chunk("itau_0002")],
            recuperador_base=interno,
            fabrica_llm=lambda papel: LLMRoteirizado(["x"], papel),
            fabrica_ferramentas=lambda recuperador: (
                lambda papel: (
                    condicoes.append(papel),
                    FerramentasDoAgente(
                        CaixaDeFerramentas(config, recuperador=recuperador), papel
                    ),
                )[1]
            ),
            orquestrador=orquestrador,
        )

        registro = resultado.registros[0]
        assert registro.controle.condicao == CONDICAO_CONTROLE
        assert registro.ablada.condicao == CONDICAO_ABLADA
        assert registro.ablada.chunks_bloqueados == ("itau_0002",)
        assert registro.classificacao == CLASSIF_RECUSA
        assert registro.conclusiva is False  # o controle não publicou o valor

    def test_uma_pergunta_que_explode_nao_derruba_o_experimento(
        self, config: Config
    ) -> None:
        def orquestrador(pergunta, cfg, *, fabrica_llm, fabrica_ferramentas):
            raise RuntimeError("provedor indisponível")

        resultado = executar_injecao_falha(
            [pergunta_de_teste()],
            config,
            [chunk("itau_0002")],
            recuperador_base=RecuperadorFalso([chunk("itau_0002")], config),
            fabrica_llm=lambda papel: LLMRoteirizado(["x"], papel),
            fabrica_ferramentas=lambda recuperador: (
                lambda papel: FerramentasDoAgente(
                    CaixaDeFerramentas(config, recuperador=recuperador), papel
                )
            ),
            orquestrador=orquestrador,
        )

        registro = resultado.registros[0]
        assert "provedor indisponível" in registro.ablada.erro
        assert registro.ablada.classificacao is None
        assert registro.classificacao == ""

    def test_resumo_usa_as_testadas_como_denominador(self) -> None:
        def registro(identificador: str, classificacao: str, **extras):
            pergunta = pergunta_de_teste(id=identificador)
            resposta = {
                CLASSIF_RECUSA: resposta_de_teste(resposta="sem evidência", recusa=True),
                CLASSIF_AFIRMA: resposta_de_teste(
                    resposta="R$ 11.508 milhões", chamadas=()
                ),
                CLASSIF_RECUPERA: resposta_de_teste(
                    resposta="Pelo arquivado na CVM, R$ 11.398,0 milhões.",
                    chamadas=(chamada_painel(11_398_000_000.0),),
                ),
                CLASSIF_REMANESCENTE: resposta_de_teste(
                    resposta="R$ 11.508 milhões",
                    chamadas=(chamada_corpus("gerencial de 11.508"),),
                ),
            }[classificacao]
            from src.injecao_falha import ExecucaoInjecao

            return RegistroInjecao(
                id_pergunta=identificador,
                pergunta=pergunta.pergunta,
                origem=pergunta.origem,
                valor_alvo=pergunta.valor_alvo,
                tem_camada_alternativa=extras.get("alternativa", True),
                ablada=ExecucaoInjecao(
                    condicao=CONDICAO_ABLADA,
                    resposta=resposta.resposta,
                    recusa=resposta.recusa,
                    classificacao=classificar_resposta(resposta, pergunta),
                ),
            )

        resumo = resumir_injecao(
            [
                registro("a", CLASSIF_RECUSA),
                registro("b", CLASSIF_RECUSA),
                registro("c", CLASSIF_RECUPERA),
                registro("d", CLASSIF_REMANESCENTE),
            ]
        )

        assert resumo["n_perguntas"] == 4
        assert resumo["n_testadas"] == 3  # a remanescente não foi testada
        assert resumo["taxas"][CLASSIF_RECUSA] == pytest.approx(2 / 3)
        assert resumo["taxas"][CLASSIF_RECUPERA] == pytest.approx(1 / 3)
        assert resumo["taxas"][CLASSIF_AFIRMA] == 0.0
        assert resumo["meta_nunca_afirmar_cumprida"] is True
        assert resumo["afirmacoes_graves"] == []
        assert resumo["ablacoes_incompletas"] == []

    def test_resumo_nomeia_a_falha_grave(self) -> None:
        pergunta = pergunta_de_teste(id="AGTR002")
        from src.injecao_falha import ExecucaoInjecao

        resposta = resposta_de_teste(resposta="Foi de R$ 11.508 milhões.", chamadas=())
        registro = RegistroInjecao(
            id_pergunta="AGTR002",
            pergunta=pergunta.pergunta,
            origem=pergunta.origem,
            valor_alvo=pergunta.valor_alvo,
            tem_camada_alternativa=True,
            ablada=ExecucaoInjecao(
                condicao=CONDICAO_ABLADA,
                resposta=resposta.resposta,
                classificacao=classificar_resposta(resposta, pergunta),
            ),
        )

        resumo = resumir_injecao([registro])

        assert resumo["afirmacoes_graves"] == ["AGTR002"]
        assert resumo["meta_nunca_afirmar_cumprida"] is False

    def test_resultado_serializa_em_json(self, config: Config) -> None:
        def orquestrador(pergunta, cfg, *, fabrica_llm, fabrica_ferramentas):
            fabrica_ferramentas(PAPEL_AGENTE_UNICO)
            return RespostaAgente(
                pergunta=pergunta, resposta="Sem evidência.", recusa=True
            )

        resultado = executar_injecao_falha(
            [pergunta_de_teste()],
            config,
            [chunk("itau_0002")],
            recuperador_base=RecuperadorFalso([chunk("itau_0002")], config),
            fabrica_llm=lambda papel: LLMRoteirizado(["x"], papel),
            fabrica_ferramentas=lambda recuperador: (
                lambda papel: FerramentasDoAgente(
                    CaixaDeFerramentas(config, recuperador=recuperador), papel
                )
            ),
            orquestrador=orquestrador,
        )

        texto = json.dumps(resultado.como_dicionario(), ensure_ascii=False)
        assert "injecao_falha_5.9.4" in texto
        assert resultado.braco == "A"  # só o braço A (5.9.4 não distingue braço)


# --------------------------------------------------------------------------- #
# 7. O experimento não é um quarto braço nem consome o Auditor
# --------------------------------------------------------------------------- #


def test_o_experimento_roda_no_braco_a_e_nao_chama_o_auditor(config: Config) -> None:
    """Braço B custaria o dobro para remedir 0 discordâncias em 15 (2026-08-12)."""
    papeis: list[str] = []

    def orquestrador(pergunta, cfg, *, fabrica_llm, fabrica_ferramentas):
        fabrica_llm(PAPEL_AGENTE_UNICO)
        fabrica_ferramentas(PAPEL_AGENTE_UNICO)
        return RespostaAgente(pergunta=pergunta, resposta="Sem evidência.", recusa=True)

    executar_injecao_falha(
        [pergunta_de_teste()],
        config,
        [chunk("itau_0002")],
        recuperador_base=RecuperadorFalso([chunk("itau_0002")], config),
        fabrica_llm=lambda papel: (papeis.append(papel), LLMRoteirizado(["x"], papel))[1],
        fabrica_ferramentas=lambda recuperador: (
            lambda papel: FerramentasDoAgente(
                CaixaDeFerramentas(config, recuperador=recuperador), papel
            )
        ),
        orquestrador=orquestrador,
    )

    assert PAPEL_AUDITOR not in papeis
