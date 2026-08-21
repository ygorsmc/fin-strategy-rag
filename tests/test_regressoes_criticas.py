"""Regressões para falhas críticas encontradas na revisão adversarial."""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

import pytest

from scripts import executar_estabilidade
from src import avaliacao, geracao
from src.avaliacao import PerguntaPadrao, ResultadoItem
from src.config import Config
from src.geracao import Citacao
from src.ingestao import Chunk
from src.recuperacao import Estrategia


def _pergunta_factual(
    texto: str,
    resposta_esperada: str,
    *,
    identificador: str = "Q",
) -> PerguntaPadrao:
    return PerguntaPadrao(
        id=identificador,
        conjunto="teste",
        categoria="factual",
        subtipo_adversarial="",
        pergunta=texto,
        resposta_esperada=resposta_esperada,
        classe_verificacao="release_gerencial",
        unidade="n/a",
        origem="tabela",
        locais_aceitos="doc:1",
        pontos_chave="",
        comportamento_aceito="",
    )


def _resposta(texto: str) -> geracao.RespostaGerada:
    return geracao.RespostaGerada(texto, False, None, ())


def _chunk(texto: str, *, trimestre: str = "1T2026") -> Chunk:
    return Chunk(
        id="chunk-1",
        empresa="ITAU",
        trimestre=trimestre,
        documento="doc",
        pagina_inicio=1,
        pagina_fim=1,
        posicao_no_documento=1,
        texto=f"[ITAU | doc | {trimestre} | pág. 1]\n{texto}",
    )


@pytest.mark.parametrize(
    ("pergunta", "esperado", "texto_resposta"),
    [
        (
            "Qual foi o índice de eficiência ajustado?",
            "34,1%",
            "O índice ajustado da carteira foi 34,1%; "
            "o índice de eficiência ajustado foi 99,0%.",
        ),
        (
            "Qual foi o resultado recorrente gerencial?",
            "R$ 11.508 milhões",
            "A carteira foi R$ 11.508 milhões; "
            "o resultado recorrente gerencial foi R$ 9.000 milhões.",
        ),
        (
            "Qual foi o resultado recorrente gerencial?",
            "R$ 11.508 milhões",
            "O resultado recorrente gerencial ficou entre "
            "R$ 10.000 milhões e R$ 11.508 milhões.",
        ),
        (
            "Qual foi o resultado recorrente gerencial?",
            "R$ 11.508 milhões",
            "O resultado recorrente gerencial foi R$ 9.000 milhões, "
            "e não R$ 11.508 milhões.",
        ),
    ],
)
def test_exatidao_nao_aceita_numero_certo_em_contexto_errado(
    pergunta: str,
    esperado: str,
    texto_resposta: str,
):
    assert not avaliacao.avaliar_exatidao_numerica(
        _pergunta_factual(pergunta, esperado),
        _resposta(texto_resposta),
        Config(),
    )


def test_exatidao_distingue_total_de_atribuivel_a_controladores():
    pergunta = _pergunta_factual(
        "Qual foi o resultado líquido IFRS total atribuível a controladores "
        "e não controladores?",
        "R$ 11.875 milhões",
        identificador="TSTF006",
    )
    errada = _resposta(
        "O resultado líquido IFRS atribuível aos controladores "
        "foi R$ 11.875 milhões."
    )
    correta = _resposta(
        "O resultado líquido IFRS total atribuível a controladores e "
        "não controladores foi R$ 11.875 milhões."
    )
    assert not avaliacao.avaliar_exatidao_numerica(pergunta, errada, Config())
    assert avaliacao.avaliar_exatidao_numerica(pergunta, correta, Config())


@pytest.mark.parametrize(
    "texto_resposta",
    [
        "O ROAE ajustado do Itaú foi 20,0%.",
        "O ROAE gerencial do Itaú foi 20,0%.",
        "O ROAE excluindo ágio do Itaú foi 20,0%.",
    ],
)
def test_grounding_rejeita_qualificador_contabil_inventado(texto_resposta: str):
    chunk = _chunk("O ROAE reportado do Itaú foi 20,0%.")
    citacoes = (Citacao("ITAU", "doc", "1T2026", 1),)
    assert not geracao.numeros_da_resposta_estao_fundamentados(
        texto_resposta,
        citacoes,
        [chunk],
        1.0,
    )


def test_grounding_rejeita_metrica_trocada_e_troca_dentro_da_mesma_linha():
    citacoes = (Citacao("ITAU", "doc", "1T2026", 1),)
    resultado = _chunk(
        "O resultado recorrente gerencial foi R$ 11.508 milhões."
    )
    assert not geracao.numeros_da_resposta_estao_fundamentados(
        "A carteira de crédito gerencial foi R$ 11.508 milhões.",
        citacoes,
        [resultado],
        1.0,
    )

    indicadores = _chunk("ROAE reportado: 20,0%; eficiência: 30,0%.")
    assert not geracao.numeros_da_resposta_estao_fundamentados(
        "ROAE reportado: 30,0%; eficiência: 20,0%.",
        citacoes,
        [indicadores],
        1.0,
    )


class _ProvedorJson(geracao.ProvedorLLM):
    nome = "fake"

    def __init__(self, resposta: str):
        self._resposta = resposta
        self.chamadas = 0

    def estimar_custo_maximo(self, prompt_sistema, prompt_usuario):
        return 0.05

    def gerar(self, prompt_sistema, prompt_usuario, temperatura=0.0):
        self.chamadas += 1
        return geracao.RespostaBrutaLLM(
            texto=json.dumps(
                {
                    "resposta": self._resposta,
                    "recusa": False,
                    "motivo_recusa": None,
                    "citacoes": [
                        {
                            "empresa": "ITAU",
                            "documento": "doc",
                            "trimestre": "1T2026",
                            "pagina": 1,
                        }
                    ],
                }
            ),
            uso=geracao.UsoLLM(20, 10, 0.05, 0.01),
            modelo="modelo-fixture",
        )


@pytest.mark.parametrize(
    ("evidencia", "resposta", "deve_recusar"),
    [
        (
            "A administração atribuiu a melhora da eficiência à "
            "digitalização dos processos.",
            "A administração atribuiu a melhora da eficiência à "
            "digitalização dos processos.",
            False,
        ),
        (
            "A digitalização elevou custos operacionais.",
            "Houve melhora: a digitalização elevou custos operacionais.",
            True,
        ),
        (
            "A digitalização não reduziu custos operacionais.",
            "A digitalização reduziu custos operacionais.",
            True,
        ),
        (
            "A queda refletiu maiores despesas administrativas.",
            "A alta refletiu maiores despesas administrativas.",
            True,
        ),
    ],
)
def test_grounding_qualitativo_end_to_end_exige_texto_e_polaridade(
    evidencia: str,
    resposta: str,
    deve_recusar: bool,
):
    gerada, _ = geracao.gerar_resposta(
        "O que a administração explicou?",
        [_chunk(evidencia)],
        _ProvedorJson(resposta),
        Config(),
    )
    assert gerada.recusa is deve_recusar
    if deve_recusar:
        assert gerada.motivo_recusa and "RN02" in gerada.motivo_recusa


@pytest.mark.parametrize(
    "resposta",
    [
        "Lucro ajustado: R$ 100 milhões. "
        "A administração anunciou demissões em massa.",
        "Devido a fraudes internas, o lucro ajustado foi R$ 100 milhões.",
        "O lucro ajustado foi R$ 100 milhões, impulsionado por "
        "demissões em massa.",
    ],
)
def test_grounding_misto_nao_oculta_afirmacao_qualitativa_inventada(
    resposta: str,
):
    chunk = _chunk("O lucro ajustado foi R$ 100 milhões.")
    citacoes = (Citacao("ITAU", "doc", "1T2026", 1),)
    assert not geracao.numeros_da_resposta_estao_fundamentados(
        resposta,
        citacoes,
        [chunk],
        1.0,
    )


class TestClausulaNumericaSemConteudoInventado:
    """Guarda da cláusula que já carrega número validado.

    O critério anterior — sequência de tokens idêntica à de UMA linha da
    evidência — só era satisfeito por cópia literal, e nenhuma geração real
    passava. O critério atual recusa conteúdo NOVO e inversão de polaridade,
    que é o que a guarda existe para pegar.
    """

    EVIDENCIA = (
        "O resultado de PDD gerencial totalizou R$ 6.344 milhões no 1T26, "
        "avanço de 3,9% no trimestre."
    )
    PERGUNTA_TOKENS = geracao._tokens_qualitativos(
        "Segundo a demonstração gerencial do Santander qual foi o "
        "resultado de PDD no 1T2026?"
    )

    def test_aceita_parafrase_fiel_com_moldura_vinda_da_pergunta(self):
        # "segundo/demonstracao/gerencial" não estão na evidência, mas são
        # palavras da própria pergunta — moldura do usuário não é fabricação.
        assert geracao._clausula_numerica_sem_conteudo_inventado(
            "Segundo a demonstração gerencial do Santander, o resultado de "
            "PDD no 1T2026 foi de R$ 6.344 milhões.",
            [_chunk(self.EVIDENCIA)],
            self.PERGUNTA_TOKENS,
        )

    def test_recusa_causa_inventada_mesmo_com_numero_correto(self):
        # O número está na evidência; a causa não está em lugar nenhum.
        assert not geracao._clausula_numerica_sem_conteudo_inventado(
            "Devido a fraudes internas, o resultado de PDD foi de "
            "R$ 6.344 milhões.",
            [_chunk(self.EVIDENCIA)],
            self.PERGUNTA_TOKENS,
        )

    def test_recusa_inversao_de_polaridade(self):
        assert not geracao._clausula_numerica_sem_conteudo_inventado(
            "O resultado de PDD gerencial não totalizou R$ 6.344 milhões.",
            [_chunk(self.EVIDENCIA)],
            self.PERGUNTA_TOKENS,
        )

    def test_recusa_token_que_nao_vem_nem_da_evidencia_nem_da_pergunta(self):
        assert not geracao._clausula_numerica_sem_conteudo_inventado(
            "O resultado de PDD gerencial totalizou R$ 6.344 milhões, "
            "impulsionado por demissões em massa.",
            [_chunk(self.EVIDENCIA)],
            self.PERGUNTA_TOKENS,
        )

    def test_sem_chunk_citado_nao_fundamenta(self):
        assert not geracao._clausula_numerica_sem_conteudo_inventado(
            "O resultado de PDD gerencial totalizou R$ 6.344 milhões.",
            [],
            self.PERGUNTA_TOKENS,
        )


class TestCelulaDeTabelaHerdaUnidadeVigente:
    """Célula de tabela sem unidade própria é reanalisada com a legenda
    vigente do chunk (5.3) — o par com a propagação de legenda na ingestão.

    Achado real (Bradesco 1T2026, pág. 41): mesmo com "Em R$ milhões" já
    presente no mesmo chunk da tabela (ingestão corrigida em 2026-08-17), a
    RN02 continuava recusando. Causa: `_fatos_numericos_da_linha` tipa cada
    CÉLULA isoladamente — "20.051" sem `R$` na própria célula fica `escalar`
    (20.051), nunca compatível com a resposta do modelo "R$ 20.051 milhões"
    (`monetario`, 2,0051e10). A legenda precisava entrar na reanálise do
    NÚMERO, não só existir em algum lugar do texto do chunk.
    """

    LINHA_TABELA = "|  Margem Financeira Total | 20.051 | 19.245 |"
    LEGENDA = "Em R$ milhões (exceto quando indicado)"

    def test_celula_nua_sozinha_fica_escalar(self):
        fatos = geracao._fatos_numericos_da_linha(self.LINHA_TABELA)
        assert [numero.dimensao for numero, _, _ in fatos] == ["escalar", "escalar"]

    def test_celula_nua_com_legenda_vigente_vira_monetaria(self):
        fatos = geracao._fatos_numericos_da_linha(self.LINHA_TABELA, self.LEGENDA)
        assert [numero.dimensao for numero, _, _ in fatos] == [
            "monetario",
            "monetario",
        ]
        assert fatos[0][0].valor == pytest.approx(20_051_000_000.0)

    def test_rotulo_da_linha_nao_e_contaminado_pela_legenda(self):
        """A legenda não pode virar candidata a rótulo — ela entra só na
        reanálise da célula numérica, nunca antes do split por `|`."""
        fatos = geracao._fatos_numericos_da_linha(self.LINHA_TABELA, self.LEGENDA)
        tokens_esperados = geracao._tokens_metrica_grounding(
            "Margem Financeira Total"
        )
        assert all(tokens == tokens_esperados for _, tokens, _ in fatos)

    def test_celula_ja_com_unidade_propria_nao_e_reanalisada(self):
        """Célula que já tem escala própria não deve ser trocada — evita
        que uma legenda desatualizada sobrescreva um valor já correto."""
        linha = "|  Receita | R$ 500 mil |"
        fatos = geracao._fatos_numericos_da_linha(linha, self.LEGENDA)
        (numero, _, _), = fatos
        assert numero.valor == pytest.approx(500_000.0)

    def test_grounding_end_to_end_aceita_valor_de_tabela_com_legenda_no_chunk(self):
        """O caso real (DEV005): legenda e tabela no MESMO chunk (ingestão
        já garante isso), resposta cita o valor com unidade — RN02 aceita."""
        chunk = Chunk(
            id="c",
            empresa="BRADESCO",
            trimestre="1T2026",
            documento="doc",
            pagina_inicio=41,
            pagina_fim=41,
            posicao_no_documento=1,
            texto=(
                f"[BRADESCO | doc | 1T2026 | pág. 41]\n{self.LEGENDA}\n"
                f"{self.LINHA_TABELA}"
            ),
        )
        citacoes = (Citacao("BRADESCO", "doc", "1T2026", 41),)
        assert geracao.numeros_da_resposta_estao_fundamentados(
            "A margem financeira total foi de R$ 20.051 milhões.",
            citacoes,
            [chunk],
            1.0,
            "qual foi a margem financeira total?",
        )

    def test_grounding_end_to_end_sem_legenda_no_chunk_continua_recusando(self):
        """Contraprova: sem a legenda em lugar nenhum do chunk, a célula nua
        continua `escalar` e a RN02 recusa — não virou permissivo demais."""
        chunk = Chunk(
            id="c",
            empresa="BRADESCO",
            trimestre="1T2026",
            documento="doc",
            pagina_inicio=41,
            pagina_fim=41,
            posicao_no_documento=1,
            texto=f"[BRADESCO | doc | 1T2026 | pág. 41]\n{self.LINHA_TABELA}",
        )
        citacoes = (Citacao("BRADESCO", "doc", "1T2026", 41),)
        assert not geracao.numeros_da_resposta_estao_fundamentados(
            "A margem financeira total foi de R$ 20.051 milhões.",
            citacoes,
            [chunk],
            1.0,
            "qual foi a margem financeira total?",
        )


def _evento_inicio(fingerprint: str, *, call_id: str = "call-1") -> dict:
    return {
        "evento": "inicio",
        "call_id": call_id,
        "fingerprint": fingerprint,
        "run_id": "run-1",
        "pergunta_id": "q1",
        "estrategia": "semantica",
        "tentativa": 1,
        "estimativa_maxima_usd": 0.2,
    }


def _item_journal(
    fingerprint: str,
    *,
    custo: float = 0.2,
    observado: float | None = 0.2,
) -> ResultadoItem:
    return ResultadoItem(
        "q1",
        Estrategia.SEMANTICA,
        _resposta("Resposta"),
        custo_usd=custo,
        custo_observado_usd=observado,
        custo_estimado_falhas_usd=0.0 if observado is not None else custo,
        n_chamadas=1,
        n_chamadas_sem_telemetria=0 if observado is not None else 1,
        tokens_entrada=10 if observado is not None else 0,
        tokens_saida=5 if observado is not None else 0,
        modelo="modelo-fixture",
        erro=None if observado is not None else "falha",
        run_id="run-1",
        fingerprint=fingerprint,
        call_ids=("call-1",),
    )


def test_journal_rejeita_call_ausente_e_custo_terminal_divergente(tmp_path):
    fingerprint = "a" * 64
    journal = tmp_path / "journal.jsonl"
    with pytest.raises(ValueError, match="ausente do journal"):
        avaliacao._validar_journal_chamadas(
            journal, fingerprint, [_item_journal(fingerprint)]
        )

    avaliacao._anexar_evento_journal_chamada(
        journal, _evento_inicio(fingerprint)
    )
    avaliacao._anexar_evento_journal_chamada(
        journal,
        {
            "evento": "fim",
            "call_id": "call-1",
            "fingerprint": fingerprint,
            "run_id": "run-1",
            "resultado": "sucesso",
            "custo_observado_usd": 0.3,
            "tokens_entrada": 10,
            "tokens_saida": 5,
        },
    )
    with pytest.raises(ValueError, match="Custo observado"):
        avaliacao._validar_journal_chamadas(
            journal, fingerprint, [_item_journal(fingerprint)]
        )


@pytest.mark.parametrize("custo", [-1.0, float("nan")])
def test_loader_rejeita_custo_negativo_ou_nan(tmp_path, custo: float):
    fingerprint = "b" * 64
    caminho = tmp_path / "checkpoint.jsonl"
    registro = {
        "fingerprint": fingerprint,
        "run_id": "run",
        "pergunta_id": "q",
        "estrategia": "semantica",
        "custo_usd": custo,
        "custo_observado_usd": custo,
        "custo_estimado_falhas_usd": 0.0,
        "n_chamadas": 0,
        "n_chamadas_sem_telemetria": 0,
        "call_ids": [],
        "latencia_s": 0.0,
        "tokens_entrada": 0,
        "tokens_saida": 0,
        "modelo": "",
        "erro": "adulterado",
        "resposta": None,
        "recuperados": [],
    }
    caminho.write_text(json.dumps(registro) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="finito e >= 0"):
        avaliacao._carregar_checkpoint(caminho, fingerprint)


def test_pos_sucesso_local_nao_repete_chamada_e_preserva_telemetria(
    tmp_path, monkeypatch
):
    class RecuperadorVazio:
        def recuperar(self, pergunta, estrategia, top_k=None):
            return []

    provedor = _ProvedorJson("Lucro líquido: R$ 1 milhão.")
    pergunta = _pergunta_factual("Qual foi o lucro líquido?", "R$ 1 milhão")
    journal = tmp_path / "journal.jsonl"

    def falhar_pontuacao(*args, **kwargs):
        raise RuntimeError("falha local após a resposta remota")

    monkeypatch.setattr(
        avaliacao, "avaliar_exatidao_numerica", falhar_pontuacao
    )
    item = avaliacao._avaliar_item(
        Config(),
        RecuperadorVazio(),
        provedor,
        pergunta,
        Estrategia.CLOSED_BOOK,
        run_id="run-pos-sucesso",
        fingerprint="c" * 64,
        caminho_journal_chamadas=journal,
    )
    eventos = [json.loads(linha) for linha in journal.read_text().splitlines()]
    assert provedor.chamadas == 1
    assert [evento["evento"] for evento in eventos] == ["inicio", "fim"]
    assert eventos[1]["resultado"] == "sucesso"
    assert item.erro == "RuntimeError"
    assert item.custo_observado_usd == pytest.approx(0.05)
    assert item.custo_estimado_falhas_usd == 0.0
    avaliacao._validar_journal_chamadas(journal, "c" * 64, [item])


def _gravar_csv_reconciliacao(caminho: Path) -> None:
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=avaliacao.COLUNAS_CONJUNTO_PADRAO
        )
        escritor.writeheader()
        escritor.writerow(
            {
                "id": "q1",
                "conjunto": "dev",
                "categoria": "factual",
                "subtipo_adversarial": "",
                "pergunta": "Qual foi o lucro?",
                "resposta_esperada": "R$ 1 milhão",
                "classe_verificacao": "release_gerencial",
                "unidade": "R$ milhões",
                "origem": "tabela",
                "locais_aceitos": "doc:1",
                "pontos_chave": "",
                "comportamento_aceito": "",
            }
        )


def test_reconciliacao_orfa_e_idempotente_e_nao_envenena_logs(tmp_path):
    fingerprint = "d" * 64
    journal = tmp_path / "journal.jsonl"
    checkpoint = tmp_path / "checkpoint.jsonl"
    logs = tmp_path / "logs"
    csv_path = tmp_path / "perguntas.csv"
    _gravar_csv_reconciliacao(csv_path)
    avaliacao._anexar_evento_journal_chamada(
        journal, _evento_inicio(fingerprint)
    )
    argumentos = {
        "fingerprint": fingerprint,
        "call_id": "call-1",
        "caminho_journal": journal,
        "caminho_checkpoint": checkpoint,
        "dir_auditoria": logs,
    }
    primeiro = avaliacao.reconciliar_chamada_orfa(
        Config(conjunto_padrao_path=csv_path), **argumentos
    )
    segundo = avaliacao.reconciliar_chamada_orfa(
        Config(conjunto_padrao_path=csv_path), **argumentos
    )
    assert primeiro == segundo
    assert primeiro.custo_usd == pytest.approx(0.2)
    assert len(checkpoint.read_text().splitlines()) == 1
    eventos = [json.loads(linha) for linha in journal.read_text().splitlines()]
    assert sum(evento["evento"] == "fim" for evento in eventos) == 1
    assert avaliacao._carregar_itens_auditados(logs, fingerprint) == []


def test_modelo_observado_nao_pode_mudar_entre_estrategias():
    itens = [
        ResultadoItem(
            f"q-{estrategia.value}",
            estrategia,
            _resposta("ok"),
            custo_usd=0.0,
            custo_observado_usd=0.0,
            n_chamadas=1,
            modelo=modelo,
            call_ids=(f"call-{estrategia.value}",),
        )
        for estrategia, modelo in (
            (Estrategia.CLOSED_BOOK, "modelo-a"),
            (Estrategia.SEMANTICA, "modelo-b"),
        )
    ]
    with pytest.raises(ValueError, match="entre estratégias"):
        avaliacao._validar_modelos_sucesso(itens)


def test_estado_material_atual_detecta_adulteracao(tmp_path):
    class ProvedorOllama:
        nome = "ollama"

        def identidade_modelo(self):
            return "qwen2.5:14b@sha256:fixture"

    indice = tmp_path / "indice"
    indice.mkdir()
    (indice / "metadados_construcao.json").write_text(
        json.dumps({"modelo": "fixture", "data_construcao": "ignorada"}),
        encoding="utf-8",
    )
    (indice / "chunks.json").write_text("[]", encoding="utf-8")
    (indice / "indice.faiss").write_bytes(b"faiss-fixture")
    pergunta = _pergunta_factual("Qual foi o lucro?", "R$ 1 milhão")
    config = Config(conjunto_padrao_path=tmp_path / "gabarito-ausente.csv")
    _, componentes = avaliacao._calcular_fingerprint(
        config,
        [pergunta],
        ProvedorOllama(),
        indice,
    )
    avaliacao.validar_estado_material_atual(
        config, [pergunta], componentes, dir_indice=indice
    )

    adulterados = copy.deepcopy(componentes)
    adulterados["versao_prompt"] = "adulterada"
    with pytest.raises(ValueError, match="versao_prompt"):
        avaliacao.validar_estado_material_atual(
            config, [pergunta], adulterados, dir_indice=indice
        )
    (indice / "chunks.json").write_text("[{}]", encoding="utf-8")
    with pytest.raises(ValueError, match="indice"):
        avaliacao.validar_estado_material_atual(
            config, [pergunta], componentes, dir_indice=indice
        )


def test_gemini_rejeita_preco_total_zero_e_estima_overhead_conservador():
    with pytest.raises(ValueError, match="ambos zero"):
        geracao.LLMGemini(
            Config(
                gemini_api_key="chave-fixture",
                gemini_preco_entrada_usd_milhao=0.0,
                gemini_preco_saida_usd_milhao=0.0,
            )
        )

    provedor = object.__new__(geracao.LLMGemini)
    provedor._config = Config(
        gemini_preco_entrada_usd_milhao=2.0,
        gemini_preco_saida_usd_milhao=10.0,
        gemini_max_tokens=100,
    )
    sistema = "á"
    usuario = "teste"
    esperado = (
        (len((sistema + usuario).encode("utf-8")) + 256) * 2.0
        + 100 * 10.0
    ) / 1_000_000
    assert provedor.estimar_custo_maximo(sistema, usuario) == pytest.approx(
        esperado
    )


def test_precalculo_estabilidade_usa_mesma_ordem_canonica_da_avaliacao():
    perguntas = [
        _pergunta_factual("Qual foi A?", "1", identificador="A"),
        _pergunta_factual("Qual foi B?", "2", identificador="B"),
        _pergunta_factual("Qual foi C?", "3", identificador="C"),
    ]
    selecionadas = executar_estabilidade._perguntas_na_ordem_canonica(
        perguntas, ["C", "A"]
    )
    assert [pergunta.id for pergunta in selecionadas] == ["A", "C"]


def test_aliases_reais_do_conjunto_sao_discriminados_no_grounding():
    grupos_aum = geracao._tokens_metrica_grounding(
        "ativos sob gestão e administração"
    )
    assert "metrica_aum_aua" in grupos_aum
    assert "metrica_aum" not in grupos_aum
    assert "metrica_aua" not in grupos_aum

    grupos_retorno = geracao._tokens_metrica_grounding(
        "retorno recorrente anualizado sobre o patrimônio líquido médio"
    )
    assert "metrica_rentabilidade" in grupos_retorno
    assert geracao._modificadores_metrica_grounding(
        "resultado operacional"
    ) >= {"operacional"}

    tokens_avaliacao = avaliacao._tokens_metrica_pergunta(
        "qual foi o retorno sobre o patrimônio?"
    )
    assert "rentabilidade" in avaliacao._grupos_metricos(tokens_avaliacao)


class TestMarcadorDeNotaNoRotuloDaLinha:
    """Chamada de nota de rodapé no rótulo não pode apagar a métrica da linha.

    Achado real na rodada congelada de 2026-08-18 (TSTF011, Santander pág. 11):
    ``| ROAE gerencial excluindo ágio - anualizado^{1} | 17,5% | ...`` — o
    ``^{1}`` faz a célula do rótulo parecer numérica, ela é descartada como
    candidata a rótulo, e a linha inteira fica sem token de métrica. Nenhum
    valor dela fundamenta resposta, embora seja o nome da conta. Medido no
    índice: 454 linhas de tabela recuperam o rótulo só com esta remoção.
    """

    LINHA = "|  ROAE gerencial excluindo ágio - anualizado^{1} | 17,5% | 16,4% |"

    def test_rotulo_com_marcador_de_nota_ainda_da_tokens_de_metrica(self):
        fatos = geracao._fatos_numericos_da_linha(self.LINHA)
        assert fatos, "a linha deveria produzir fatos numéricos"
        for _, tokens, _ in fatos:
            assert "metrica_rentabilidade" in tokens

    def test_sem_a_remocao_o_rotulo_se_perderia(self):
        """Contraprova: é o marcador que quebra, não outra coisa da linha."""
        assert geracao._sem_marcador_de_nota(
            "ágio - anualizado^{1}"
        ) == "ágio - anualizado"

    def test_parenteses_contabil_nao_e_tratado_como_nota(self):
        """`(1.234)` é NEGATIVO em demonstração contábil, não nota de rodapé.

        Removê-lo trocaria o sinal de valores reais: `(N)` devolveria o rótulo
        de zero linhas do índice e apareceria em 6.034 linhas onde o parêntese
        é negativo. Por isso a remoção cobre apenas `^{N}`.
        """
        assert geracao._sem_marcador_de_nota("(18,1)") == "(18,1)"
        assert geracao._sem_marcador_de_nota("Custo do Crédito (1)") == (
            "Custo do Crédito (1)"
        )


class TestMarcadorDeCitacaoNoTextoDaResposta:
    """A citação que o modelo repete no texto não é afirmação numérica.

    O modelo imita o cabeçalho do trecho e escreve
    ``[SANTANDER, santander_release_3T2025, 3T2025, pág. 11]`` dentro da
    resposta. O split de cláusulas quebra em ``... pág.`` + ``11].``, e a
    segunda cláusula fica com um número e nenhuma métrica — a resposta inteira
    cai. Medido nas 45 congeladas: 9 respostas traziam o marcador e as **9**
    foram recusadas. A citação auditável é o campo `citacoes`, conferido pela
    RN01 em `citacoes_sao_validas`.
    """

    def test_marcador_de_citacao_e_removido(self):
        texto = (
            "O ROAE foi de 17,5% "
            "[SANTANDER, santander_release_3T2025, 3T2025, pág. 11]."
        )
        limpo = geracao._sem_marcador_de_citacao(texto)
        assert "pág. 11" not in limpo
        assert "17,5%" in limpo

    def test_colchete_sem_marca_de_pagina_permanece(self):
        """Contraprova: só o colchete de citação sai. Um número entre
        colchetes continua sujeito ao grounding — afrouxar isso deixaria
        inventar valor dentro de `[...]`."""
        texto = "A margem foi de [1.234] milhões."
        assert geracao._sem_marcador_de_citacao(texto) == texto

    def test_resposta_com_citacao_inline_continua_fundamentada(self):
        chunk = Chunk(
            id="santander_release_3T2025_0001",
            empresa="SANTANDER",
            trimestre="3T2025",
            documento="santander_release_3T2025",
            pagina_inicio=11,
            pagina_fim=11,
            posicao_no_documento=1,
            texto=(
                "[SANTANDER | santander_release_3T2025 | 3T2025 | pág. 11]\n"
                "|  ROAE gerencial excluindo ágio - anualizado^{1} | 17,5% |"
            ),
        )
        citacoes = (
            Citacao(
                empresa="SANTANDER",
                documento="santander_release_3T2025",
                trimestre="3T2025",
                pagina=11,
            ),
        )
        resposta = (
            "Segundo o Santander, o ROAE gerencial excluindo ágio - anualizado "
            "no 3T2025 foi de 17,5% "
            "[SANTANDER, santander_release_3T2025, 3T2025, pág. 11]."
        )
        assert geracao.numeros_da_resposta_estao_fundamentados(
            resposta,
            citacoes,
            [chunk],
            1.0,
            "Segundo a demonstração gerencial do Santander qual foi o ROAE "
            "anualizado excluindo o ágio no 3T2025?",
        )

    def test_valor_inventado_continua_recusado_apesar_da_citacao_inline(self):
        """A remoção do marcador não pode virar porta de entrada: o número
        fabricado fora do colchete continua sem lastro."""
        chunk = Chunk(
            id="santander_release_3T2025_0001",
            empresa="SANTANDER",
            trimestre="3T2025",
            documento="santander_release_3T2025",
            pagina_inicio=11,
            pagina_fim=11,
            posicao_no_documento=1,
            texto=(
                "[SANTANDER | santander_release_3T2025 | 3T2025 | pág. 11]\n"
                "|  ROAE gerencial excluindo ágio - anualizado^{1} | 17,5% |"
            ),
        )
        citacoes = (
            Citacao(
                empresa="SANTANDER",
                documento="santander_release_3T2025",
                trimestre="3T2025",
                pagina=11,
            ),
        )
        resposta = (
            "Segundo o Santander, o ROAE gerencial excluindo ágio - anualizado "
            "no 3T2025 foi de 99,9% "
            "[SANTANDER, santander_release_3T2025, 3T2025, pág. 11]."
        )
        assert not geracao.numeros_da_resposta_estao_fundamentados(
            resposta,
            citacoes,
            [chunk],
            1.0,
            "Segundo a demonstração gerencial do Santander qual foi o ROAE "
            "anualizado excluindo o ágio no 3T2025?",
        )


class TestStopwordsDeConectivoEUnidade:
    """Conectivo e palavra de moeda não são conteúdo inventado (RN02).

    Medido nas 45 congeladas: ``conforme`` derrubou TSTF009 e ``reais``
    derrubou TSTF006 — as duas com o número certo e a página certa. A unidade
    já é verificada pela dimensão do número; exigi-la também no texto recusava
    o modelo por escrever "11.875 milhões de reais" em vez de "R$ 11.875
    milhões".
    """

    @pytest.mark.parametrize("token", ["conforme", "segundo", "reais", "real"])
    def test_token_nao_conta_como_conteudo(self, token):
        assert token not in geracao._tokens_qualitativos(
            f"o lucro {token} apurado"
        )

    def test_termo_de_conteudo_continua_valendo(self):
        """Contraprova: a lista não pode engolir vocabulário de negócio."""
        tokens = geracao._tokens_qualitativos(
            "inadimplencia da carteira ampliada"
        )
        assert {"inadimplencia", "carteira", "ampliada"} <= tokens


class TestPeriodoDaColunaDaTabela:
    """Coluna de acumulado não fundamenta afirmação sobre trimestre (RN02).

    Achado real na rodada congelada de 2026-08-18 (TSTC005): o release do Itaú
    publica a MESMA métrica em dois lugares — pág. 5 com colunas
    ``2T25 | 1T25 | ...`` (2T25 = 23,3%) e pág. 38 com colunas
    ``1S25 | 1S24 | Variação`` (1S25 = 22,8%). O modelo respondeu **22,8%** a
    uma pergunta sobre o **2T2025**: número real, métrica certa, período
    errado. Sem distinguir coluna, qualquer célula da linha fundamentava
    qualquer período — é a armadilha que a RN10 já nomeia no painel da CVM,
    aqui dentro do release.
    """

    def test_cabecalho_distingue_trimestre_de_acumulado(self):
        periodos = geracao._periodos_das_colunas(
            "|   | 2T25 | 1T25 | 1S25 | Variação  |"
        )
        assert periodos[2] == ("trimestre", "2T2025")
        assert periodos[3] == ("trimestre", "1T2025")
        assert periodos[4] == ("acumulado", "1S2025")

    def test_ano_de_dois_digitos_e_normalizado(self):
        periodos = geracao._periodos_das_colunas("|  | 2T 2025 | 6M 2025 |")
        assert periodos[2] == ("trimestre", "2T2025")
        assert periodos[3] == ("acumulado", "6M2025")

    def test_clausula_com_trimestre_unico_define_alvo(self):
        assert (
            geracao._trimestre_alvo_da_clausula("no 2T2025 o ROAE foi de 22,8%")
            == "2T2025"
        )

    def test_clausula_comparativa_nao_restringe(self):
        """Duas datas na mesma cláusula: restringir recusaria comparação
        legítima, então a guarda se cala."""
        assert (
            geracao._trimestre_alvo_da_clausula(
                "o lucro subiu do 1T2025 para o 2T2025"
            )
            is None
        )

    def test_clausula_que_fala_em_acumulado_nao_restringe(self):
        assert (
            geracao._trimestre_alvo_da_clausula(
                "no primeiro semestre de 2025 o resultado acumulado foi de 22,6"
            )
            is None
        )

    def test_coluna_de_acumulado_nao_serve_a_trimestre(self):
        assert not geracao._coluna_serve_ao_trimestre(
            ("acumulado", "1S2025"), "2T2025"
        )

    def test_coluna_de_outro_trimestre_nao_serve(self):
        assert not geracao._coluna_serve_ao_trimestre(
            ("trimestre", "1T2025"), "2T2025"
        )

    def test_coluna_do_proprio_trimestre_serve(self):
        assert geracao._coluna_serve_ao_trimestre(
            ("trimestre", "2T2025"), "2T2025"
        )

    def test_sem_informacao_de_um_dos_lados_nao_restringe(self):
        """Falha ABERTO por desenho: a maioria das tabelas do corpus não nomeia
        período no cabeçalho, e restringir sem informação recusaria em massa."""
        assert geracao._coluna_serve_ao_trimestre(None, "2T2025")
        assert geracao._coluna_serve_ao_trimestre(("acumulado", "1S2025"), None)

    def test_celula_de_coluna_acumulada_e_descartada_na_linha(self):
        linha = "|  Retorno Recorrente Gerencial | 22,8% | 22,0% |"
        periodos = {2: ("acumulado", "1S2025"), 3: ("acumulado", "1S2024")}
        assert not geracao._fatos_numericos_da_linha(
            linha, "", periodos, "2T2025"
        )
        # Sem trimestre alvo, a mesma linha continua valendo.
        assert geracao._fatos_numericos_da_linha(linha, "", periodos, None)


class TestIdentidadeCanonicaDaEmpresaNaCitacao:
    """Citar `Itaú Unibanco` sobre um chunk `ITAU` não é citação órfã.

    O corpus identifica a empresa por sigla; o modelo cita pelo nome que lê no
    documento. Exigir igualdade literal zerava a lista de chunks citados e
    derrubava a resposta inteira, com número certo e página certa. Medido no
    congelado de 2026-08-19: 8 de 106 citações (8%) não casavam — duas delas
    só por caixa (`Bradesco` × `BRADESCO`).
    """

    @pytest.mark.parametrize(
        ("citada", "do_chunk"),
        [
            ("Itaú", "ITAU"),
            ("Itaú Unibanco", "ITAU"),
            ("Banco do Brasil", "BB"),
            ("Bradesco", "BRADESCO"),
            ("BTG Pactual", "BTG"),
            ("ITAU", "ITAU"),
        ],
    )
    def test_nomes_da_mesma_instituicao_casam(self, citada, do_chunk):
        assert geracao._mesma_empresa(citada, do_chunk)

    @pytest.mark.parametrize(
        ("citada", "do_chunk"),
        [
            ("Itaú", "BRADESCO"),
            ("Banco do Brasil", "BTG"),
            ("Santander", "ITAU"),
            ("Empresa Inexistente S.A.", "ITAU"),
            ("", "ITAU"),
        ],
    )
    def test_instituicao_diferente_continua_orfa(self, citada, do_chunk):
        """Contraprova: a normalização não pode virar porta para citar um
        banco e responder sobre outro — é o núcleo da RN01."""
        assert not geracao._mesma_empresa(citada, do_chunk)

    def test_citacao_com_nome_por_extenso_e_subconjunto_valido(self):
        chunk = _chunk("Lucro líquido de R$ 10 milhões.")
        citacoes = (Citacao("Itaú Unibanco", "doc", "1T2026", 1),)
        assert geracao.citacoes_sao_subconjunto(citacoes, [chunk])

    def test_citacao_de_outro_banco_continua_invalida(self):
        chunk = _chunk("Lucro líquido de R$ 10 milhões.")
        citacoes = (Citacao("Bradesco", "doc", "1T2026", 1),)
        assert not geracao.citacoes_sao_subconjunto(citacoes, [chunk])


class TestNaoControladoresNaoEhNegacao:
    """`sócios não controladores` é conta contábil, não negação lógica.

    `_e_modal` já normalizava o termo; `_tem_negacao` não, e por isso lia a
    cláusula como negada, perdia o casamento de polaridade com a evidência e
    derrubava a resposta. O termo aparece em 270 chunks do corpus.
    """

    def test_termo_contabil_nao_conta_como_negacao(self):
        assert not geracao._tem_negacao(
            "valores atribuíveis aos acionistas controladores e não controladores"
        )

    def test_negacao_de_verdade_continua_detectada(self):
        assert geracao._tem_negacao("a digitalização não reduziu custos")
        assert geracao._tem_negacao("o banco nunca divulgou esse número")


class TestGrupoMetricoHerdadoDoTituloDaSecao:
    """A métrica pode estar no título da seção, não na linha do número.

    "O indicador acima de 90 dias encerrou setembro em 4,93%" não contém a
    palavra *inadimplência* — ela está em `### Indicadores de Inadimplência`.
    Sem herdar, a evidência fica sem grupo métrico e nada casa.
    """

    LINHA = "O indicador acima de 90 dias encerrou setembro em 4,93%."

    def test_sem_titulo_a_linha_nao_tem_grupo(self):
        fatos = geracao._fatos_numericos_da_linha(self.LINHA)
        assert fatos
        assert all(
            not (tokens & set(geracao._GRUPOS_METRICAS))
            for _, tokens, _ in fatos
        )

    def test_titulo_preenche_o_grupo_ausente(self):
        fatos = geracao._fatos_numericos_da_linha(
            self.LINHA, "", None, None, "Indicadores de Inadimplência"
        )
        assert fatos
        assert any(
            "metrica_inadimplencia" in tokens for _, tokens, _ in fatos
        )

    def test_titulo_nao_sobrescreve_grupo_proprio_da_linha(self):
        """Contraprova: o título preenche lacuna, nunca troca a métrica —
        senão bastaria a seção certa para validar qualquer número dela."""
        linha = "|  Lucro líquido | R$ 100 milhões |"
        fatos = geracao._fatos_numericos_da_linha(
            linha, "", None, None, "Indicadores de Inadimplência"
        )
        assert fatos
        for _, tokens, _ in fatos:
            assert "metrica_lucro" in tokens
            assert "metrica_inadimplencia" not in tokens

    def test_titulo_de_secao_e_reconhecido(self):
        assert (
            geracao._titulo_de_secao("### Indicadores de Inadimplência")
            == "Indicadores de Inadimplência"
        )
        assert geracao._titulo_de_secao("texto comum") == ""


class TestStopwordsDeAtribuicao:
    """Verbo de atribuição não é conteúdo inventado (RN02).

    "conforme informado pelo Banco do Brasil" diz de ONDE veio o fato já
    verificado; não afirma fato novo. Derrubava TSTF014 no congelado.
    """

    @pytest.mark.parametrize(
        "token", ["pelo", "pela", "informado", "divulgado", "reportado"]
    )
    def test_atribuicao_nao_conta_como_conteudo(self, token):
        assert token not in geracao._tokens_qualitativos(
            f"o lucro {token} pela instituicao"
        )

    def test_vocabulario_de_negocio_continua_valendo(self):
        tokens = geracao._tokens_qualitativos(
            "inadimplencia da carteira ampliada com garantias"
        )
        assert {"inadimplencia", "carteira", "ampliada", "garantias"} <= tokens
