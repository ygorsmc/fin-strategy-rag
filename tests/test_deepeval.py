"""Suíte DeepEval (spec 5.15) — contrato, sem rede e sem LLM.

O que estes casos protegem:

1. **O juiz nunca é o default da biblioteca nem paga com o preço errado.**
   `config_do_juiz` falha sem modelo nomeado e sem preço quando o juiz não é o
   modelo já configurado no provedor dele.
2. **Cada chamada do juiz passa pelo teto antes de sair e fica registrada
   antes e depois** (RNF03, RNF08). Erro transitório é repetido; o resto sobe.
3. **O desfecho separa o que se mede.** Publicada e rascunho descartado pela
   RN02 são pontuados; recusa do modelo não chama o juiz.
4. **Lê a rodada publicada, não outra:** fingerprint e estratégia filtram o
   checkpoint, e a última tentativa de cada pergunta é a que vale.
5. **As métricas reais do DeepEval rodam sobre o adaptador**, com um provedor
   roteirizado no lugar do LLM.
6. **Nada sai pela biblioteca:** telemetria desligada, `.env` não autoload, e
   o plugin de pytest dela fora da suíte.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest

from src import avaliacao_deepeval as de
from src.config import Config
from src.geracao import RespostaBrutaLLM, UsoLLM


# --------------------------------------------------------------------------- #
# Duplos
# --------------------------------------------------------------------------- #


class ProvedorRoteirizado:
    """Responde por etapa do DeepEval, reconhecida pelo texto do prompt."""

    nome = "roteiro"

    def __init__(self, respostas=None, *, custo=0.001, estimativa=0.002, falhas=()):
        self.respostas = respostas or {}
        self.custo = custo
        self.estimativa = estimativa
        self.falhas = list(falhas)
        self.prompts: list[str] = []

    def estimar_custo_maximo(self, sistema, usuario):
        return self.estimativa

    def gerar(self, sistema, usuario, temperatura=0.0):
        assert temperatura == 0.0
        self.prompts.append(usuario)
        if self.falhas:
            raise self.falhas.pop(0)
        texto = "{}"
        for marca, resposta in self.respostas.items():
            if marca in usuario:
                texto = json.dumps(resposta, ensure_ascii=False)
                break
        return RespostaBrutaLLM(
            texto=texto,
            uso=UsoLLM(tokens_entrada=100, tokens_saida=20, custo_usd=self.custo, latencia_s=0.01),
            modelo="roteiro",
        )


def _juiz(provedor, *, teto=1.0, eventos=None, dormidas=None):
    return de.JuizDeepEval(
        provedor,
        nome_modelo="juiz-teste",
        teto_usd=teto,
        run_id="teste",
        registrar=(eventos.append if eventos is not None else (lambda _e: None)),
        dormir=(dormidas.append if dormidas is not None else (lambda _s: None)),
    )


# Respostas que as etapas do DeepEval 4.2.8 pedem, reconhecidas pela frase do
# próprio template. Duas afirmações: uma sustentada, outra que o contexto não
# sustenta nem contradiz ("borderline"). Penalizando a ambígua, fidelidade 0,5;
# pelo padrão da biblioteca, 1,0.
ROTEIRO_FIDELIDADE_METADE = {
    "generate a comprehensive list of FACTUAL": {"truths": ["O lucro foi R$ 10 bi no 1T2026."]},
    "inferred from the provided actual AI output": {
        "claims": ["O lucro foi R$ 10 bi.", "A margem foi R$ 31 bi."]
    },
    "whether EACH claim contradicts": {
        "verdicts": [
            {"verdict": "yes", "reason": None},
            {"verdict": "borderline", "reason": "o contexto não traz a margem"},
        ]
    },
    "Below is a list of Contradictions": {"reason": "uma afirmação sem lastro"},
    # Relevância: duas afirmações, ambas sobre o que foi perguntado.
    "breakdown and generate a list of statements": {"statements": ["lucro", "margem"]},
    "determine whether each statement is relevant": {
        "verdicts": [{"verdict": "yes", "reason": None}, {"verdict": "yes", "reason": None}]
    },
    "Given the answer relevancy score": {"reason": "responde ao perguntado"},
}


# --------------------------------------------------------------------------- #
# 1. O juiz configurado
# --------------------------------------------------------------------------- #


class TestConfigDoJuiz:
    def test_sem_juiz_nomeado_falha(self):
        with pytest.raises(ValueError, match="DEEPEVAL_MODELO_JUIZ"):
            de.config_do_juiz(Config(llm_provider="gemini"))

    def test_juiz_diferente_sem_preco_falha(self):
        """O caso silencioso: o custo sairia com o preço do gerador."""
        config = Config(llm_provider="gemini", deepeval_modelo_juiz="gemini-3.7-flash")
        with pytest.raises(ValueError, match="preço do juiz"):
            de.config_do_juiz(config)

    def test_juiz_diferente_com_preco_usa_o_preco_dele(self):
        config = Config(
            llm_provider="gemini",
            deepeval_modelo_juiz="gemini-3.7-flash",
            deepeval_preco_entrada_usd_milhao=0.5,
            deepeval_preco_saida_usd_milhao=3.0,
        )
        juiz = de.config_do_juiz(config)
        assert juiz.gemini_modelo_llm == "gemini-3.7-flash"
        assert (juiz.gemini_preco_entrada_usd_milhao, juiz.gemini_preco_saida_usd_milhao) == (0.5, 3.0)

    def test_juiz_de_outra_familia(self):
        config = Config(
            llm_provider="gemini",
            deepeval_provedor_juiz="deepseek",
            deepeval_modelo_juiz="deepseek-flash",
            deepeval_preco_entrada_usd_milhao=0.44,
            deepeval_preco_saida_usd_milhao=1.32,
        )
        juiz = de.config_do_juiz(config)
        assert juiz.llm_provider == "deepseek" and juiz.deepseek_modelo == "deepseek-flash"
        assert juiz.deepseek_preco_saida_usd_milhao == 1.32

    def test_cache_hit_do_juiz_deepseek_nao_subestima(self):
        """Achado B1: o custo da DeepSeek cobra o cache hit por campo próprio,
        que ficava com o preço do gerador."""
        config = Config(
            llm_provider="gemini",
            deepeval_provedor_juiz="deepseek",
            deepeval_modelo_juiz="deepseek-flash",
            deepeval_preco_entrada_usd_milhao=0.44,
            deepeval_preco_saida_usd_milhao=1.32,
        )
        assert de.config_do_juiz(config).deepseek_preco_entrada_cache_hit_usd_milhao == 0.44

    def test_juiz_igual_ao_modelo_do_provedor_herda_o_preco(self):
        config = Config(llm_provider="gemini", deepeval_modelo_juiz=Config().gemini_modelo_llm)
        juiz = de.config_do_juiz(config)
        assert juiz.gemini_preco_saida_usd_milhao == Config().gemini_preco_saida_usd_milhao

    def test_provedor_sem_preco_conhecido_aqui_falha(self):
        config = Config(llm_provider="ollama", deepeval_modelo_juiz="qwen")
        with pytest.raises(ValueError, match="sem suporte de preço"):
            de.config_do_juiz(config)


# --------------------------------------------------------------------------- #
# 2. Teto, registro e reespera
# --------------------------------------------------------------------------- #


class TestJuizDeepEval:
    def test_devolve_o_schema_preenchido_e_acumula_custo(self):
        from deepeval.metrics.faithfulness.schema import Claims

        juiz = _juiz(ProvedorRoteirizado({"x": {"claims": ["a", "b"]}}, custo=0.003))
        resultado = juiz.generate("x", schema=Claims)
        assert isinstance(resultado, Claims) and resultado.claims == ["a", "b"]
        assert juiz.uso.chamadas == 1 and juiz.uso.custo_usd == pytest.approx(0.003)

    def test_teto_barra_antes_de_chamar(self):
        provedor = ProvedorRoteirizado(estimativa=0.6)
        juiz = _juiz(provedor, teto=1.0)
        juiz.uso.custo_usd = 0.5
        with pytest.raises(de.OrcamentoJuizExcedidoError):
            juiz.generate("x")
        assert provedor.prompts == []

    def test_registra_antes_e_depois_e_a_falha_e_debitada(self):
        """Contrato mudado em 20/10 (achado M3 da auditoria): antes, a
        tentativa que falhava deixava só o `inicio` no registro e não entrava
        no custo. Agora ela fecha com `fim` marcado com o erro e debita a
        estimativa conservadora, porque o provedor pode ter cobrado."""
        eventos: list[dict] = []
        provedor = ProvedorRoteirizado(falhas=[ValueError("prompt inválido")], estimativa=0.002)
        juiz = _juiz(provedor, eventos=eventos)
        with pytest.raises(ValueError):
            juiz.generate("x")
        assert [e["evento"] for e in eventos] == ["deepeval_juiz_inicio", "deepeval_juiz_fim"]
        assert eventos[-1]["erro"] == "ValueError" and eventos[-1]["debito_conservador_usd"] == 0.002
        assert juiz.uso.custo_usd == pytest.approx(0.002)
        assert juiz.uso.debito_conservador_usd == pytest.approx(0.002)
        juiz.generate("x")
        assert [e["evento"] for e in eventos][-2:] == ["deepeval_juiz_inicio", "deepeval_juiz_fim"]
        assert "erro" not in eventos[-1]

    def test_transitorio_e_repetido_com_espera_crescente(self):
        dormidas: list[float] = []
        provedor = ProvedorRoteirizado(falhas=[RuntimeError("503 UNAVAILABLE"), RuntimeError("429")])
        juiz = _juiz(provedor, dormidas=dormidas)
        assert juiz.generate("x") == "{}"
        assert dormidas == [10.0, 20.0]
        assert (juiz.uso.falhas, juiz.uso.falhas_transitorias) == (2, 2)
        # Duas tentativas debitadas pela estimativa e a terceira pelo custo medido.
        assert juiz.uso.custo_usd == pytest.approx(2 * provedor.estimativa + provedor.custo)

    def test_a_reespera_tambem_passa_pelo_teto(self):
        provedor = ProvedorRoteirizado(falhas=[RuntimeError("503")], estimativa=0.6)
        juiz = _juiz(provedor, teto=1.0)
        with pytest.raises(de.OrcamentoJuizExcedidoError):
            juiz.generate("x")
        assert len(provedor.prompts) == 1

    def test_erro_nao_transitorio_sobe_na_hora(self):
        dormidas: list[float] = []
        juiz = _juiz(ProvedorRoteirizado(falhas=[ValueError("400")]), dormidas=dormidas)
        with pytest.raises(ValueError):
            juiz.generate("x")
        assert dormidas == []


# --------------------------------------------------------------------------- #
# 3 e 4. Casos da rodada
# --------------------------------------------------------------------------- #


def _registro(pid="TSTF001", *, fingerprint="fp", estrategia="semantica", resposta=None, erro=None):
    return {
        "fingerprint": fingerprint,
        "pergunta_id": pid,
        "categoria": "factual",
        "estrategia": estrategia,
        "recusa_correta": None,
        "exatidao_ok": True,
        "erro": erro,
        "resposta": resposta or {"resposta": "O lucro foi R$ 10 bi.", "recusa": False, "bruto": ""},
        "recuperados": [{"chunk": {"texto": "Lucro de R$ 10 bi."}, "score": 0.9}],
    }


class TestCasos:
    def test_tres_desfechos(self):
        publicada = de.caso_do_registro(dict(_registro(), pergunta="p"))
        descartada = de.caso_do_registro(dict(_registro(resposta={
            "resposta": None, "recusa": True, "motivo_recusa": "RN02",
            "bruto": json.dumps({"resposta": "Rascunho: R$ 12 bi."}),
        }), pergunta="p"))
        recusa = de.caso_do_registro(dict(_registro(resposta={
            "resposta": None, "recusa": True, "motivo_recusa": "sem evidência",
            "bruto": json.dumps({"resposta": None, "recusa": True}),
        }), pergunta="p"))
        assert (publicada.desfecho, publicada.texto) == (de.DESFECHO_PUBLICADA, "O lucro foi R$ 10 bi.")
        assert (descartada.desfecho, descartada.texto) == (de.DESFECHO_DESCARTADA_RN02, "Rascunho: R$ 12 bi.")
        assert recusa.desfecho == de.DESFECHO_RECUSA_MODELO

    def test_trechos_entram_sem_score(self):
        caso = de.caso_do_registro(dict(_registro(), pergunta="p"))
        assert caso.contexto == ("Lucro de R$ 10 bi.",)

    def test_carrega_so_a_rodada_e_a_estrategia_e_a_ultima_tentativa(self, tmp_path):
        linhas = [
            _registro("TSTF001", fingerprint="outra"),
            _registro("TSTF001", estrategia="fatos"),
            _registro("TSTF001", resposta={"resposta": "primeira", "recusa": False}),
            _registro("TSTF001", resposta={"resposta": "última", "recusa": False}),
            _registro("TSTF002", erro="503"),
        ]
        checkpoint = tmp_path / "checkpoint.jsonl"
        checkpoint.write_text("\n".join(json.dumps(l) for l in linhas) + "\n", encoding="utf-8")
        casos = de.carregar_casos(checkpoint, "fp", "semantica", {"TSTF001": "Qual o lucro?", "TSTF002": "?"})
        assert [(c.pergunta_id, c.texto, c.pergunta) for c in casos] == [("TSTF001", "última", "Qual o lucro?")]

    def test_id_fora_do_conjunto_congelado_falha(self, tmp_path):
        checkpoint = tmp_path / "checkpoint.jsonl"
        checkpoint.write_text(json.dumps(_registro("XYZ")) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="conjunto congelado"):
            de.carregar_casos(checkpoint, "fp", "semantica", {})

    def test_a_rodada_publicada_tem_os_45(self):
        """Contra o artefato versionado: a estratégia do produto tem uma linha
        por pergunta congelada na rodada que `metricas_teste.json` publica."""
        from src.avaliacao import carregar_conjunto_padrao
        from src.config import DIR_RESULTADOS_AVALIACAO

        meta = json.loads((DIR_RESULTADOS_AVALIACAO / "metricas_teste.json").read_text())["_meta"]
        perguntas = {p.id: p.pergunta for p in carregar_conjunto_padrao(Config()) if p.conjunto == "teste"}
        casos = de.carregar_casos(
            DIR_RESULTADOS_AVALIACAO / "checkpoint_teste.jsonl",
            meta["fingerprint"],
            meta["estrategia_demo_e_auditoria"],
            perguntas,
        )
        assert len(casos) == len(perguntas) == 45


# --------------------------------------------------------------------------- #
# 5. As métricas reais sobre o adaptador
# --------------------------------------------------------------------------- #


class TestMedicao:
    def test_faithfulness_real_conta_a_afirmacao_sem_lastro(self):
        provedor = ProvedorRoteirizado(ROTEIRO_FIDELIDADE_METADE)
        juiz = _juiz(provedor)
        caso = de.caso_do_registro(dict(_registro(), pergunta="Qual o lucro?"))
        resultado = de.medir_caso(caso, juiz)
        assert resultado.erro is None, resultado.erro
        fidelidade = resultado.metricas[de.METRICA_FIDELIDADE]
        # O número sem sustentação derruba o escore principal, e o escore
        # padrão da biblioteca (incerto aprovado) sai junto, da mesma chamada.
        assert fidelidade["score"] == 0.5 and fidelidade["sucesso"] is False
        assert (fidelidade["n_sim"], fidelidade["n_nao"], fidelidade["n_incerto"]) == (1, 0, 1)
        assert fidelidade["score_incerto_aprovado"] == 1.0
        assert resultado.metricas[de.METRICA_RELEVANCIA]["score"] == 1.0
        # Sete chamadas por caso: 4 de fidelidade e 3 de relevância, e o
        # custo do caso é a soma delas.
        assert len(provedor.prompts) == 7
        assert resultado.custo_usd == pytest.approx(7 * provedor.custo)

    def test_sem_penalizar_a_ambigua_o_numero_sem_lastro_passaria(self):
        """Contraprova da escolha: com o padrão da biblioteca o mesmo roteiro
        dá 1,0. É por isso que `PENALIZAR_AMBIGUAS` existe."""
        juiz = _juiz(ProvedorRoteirizado(ROTEIRO_FIDELIDADE_METADE))
        caso = de.caso_do_registro(dict(_registro(), pergunta="Qual o lucro?"))
        resultado = de.medir_caso(
            caso,
            juiz,
            fabricas={
                de.METRICA_FIDELIDADE: lambda j: de.FaithfulnessMetric(
                    model=j, include_reason=True, async_mode=False
                )
            },
        )
        assert resultado.metricas[de.METRICA_FIDELIDADE]["score"] == 1.0

    def test_recusa_do_modelo_nao_chama_o_juiz(self):
        provedor = ProvedorRoteirizado()
        caso = de.caso_do_registro(dict(_registro(resposta={
            "resposta": None, "recusa": True, "motivo_recusa": "sem evidência", "bruto": "",
        }), pergunta="p"))
        resultado = de.medir_caso(caso, _juiz(provedor))
        assert resultado.metricas == {} and provedor.prompts == []

    def test_modo_de_avaliacao_herdado_nao_desvia_o_juiz(self, monkeypatch):
        """`eval_mode="llm"` fixo: um DEEPEVAL_EVAL_MODE do ambiente não manda
        a decisão a outro modelo."""
        monkeypatch.setenv("DEEPEVAL_EVAL_MODE", "hybrid")
        provedor = ProvedorRoteirizado(ROTEIRO_FIDELIDADE_METADE)
        caso = de.caso_do_registro(dict(_registro(), pergunta="Qual o lucro?"))
        resultado = de.medir_caso(caso, _juiz(provedor))
        assert resultado.erro is None, resultado.erro
        assert len(provedor.prompts) == 7

    def test_teto_atravessa_a_metrica_e_para_a_rodada(self):
        """O DeepEval engole exceção de métrica? O teto não pode ser engolido."""
        caso = de.caso_do_registro(dict(_registro(), pergunta="p"))
        with pytest.raises(de.OrcamentoJuizExcedidoError):
            de.medir_caso(caso, _juiz(ProvedorRoteirizado(estimativa=5.0), teto=1.0))

    def test_agregado_por_desfecho_com_n(self):
        caso = de.caso_do_registro(dict(_registro(), pergunta="p"))
        resultados = [
            de.ResultadoCaso(caso, {de.METRICA_FIDELIDADE: {"score": 1.0}, de.METRICA_RELEVANCIA: {"score": 0.5}}),
            de.ResultadoCaso(caso, {de.METRICA_FIDELIDADE: {"score": 0.5}}),
        ]
        bloco = de.agregar(resultados)["por_desfecho"][de.DESFECHO_PUBLICADA]
        assert bloco["n"] == 2
        assert bloco[de.METRICA_FIDELIDADE] == {"n_pontuados": 2, "media": 0.75, "n_score_1": 1}
        assert bloco[de.METRICA_RELEVANCIA]["n_pontuados"] == 1

    def test_matriz_de_concordancia(self):
        r = de.concordancia_com_humano([(True, True), (False, False), (False, True), (True, False)])
        assert r["matriz"] == {
            "ambos_acertou": 1, "ambos_errou": 1,
            "juiz_acertou_humano_errou": 1, "juiz_errou_humano_acertou": 1,
        }
        assert r["taxa_concordancia"] == 0.5


class TestCriterioDePeriodo:
    """G-Eval de período e coluna (2026-10-20), fixado antes de qualquer rodada.

    O faithfulness deu 1,0 ao número da coluna errada (TSTF006). O critério
    novo só vale se o que ele mede for o que está escrito no código: passos
    prontos, limiar fixo, uma chamada por caso.
    """

    MARCA = "Evaluation Steps:"

    def test_padrao_continua_sendo_faithfulness_e_relevancia(self):
        assert list(de.fabricas_de_metricas()) == [de.METRICA_FIDELIDADE, de.METRICA_RELEVANCIA]

    def test_metrica_desconhecida_falha(self):
        with pytest.raises(ValueError, match="desconhecida"):
            de.fabricas_de_metricas(["coerencia"])

    def test_uma_chamada_com_os_passos_escritos_no_codigo(self):
        provedor = ProvedorRoteirizado({self.MARCA: {"score": 2, "reason": "coluna do 4T25"}})
        caso = de.caso_do_registro(dict(_registro(), pergunta="Qual o lucro no 1T2026?"))
        resultado = de.medir_caso(
            caso, _juiz(provedor), fabricas=de.fabricas_de_metricas([de.METRICA_PERIODO])
        )
        assert resultado.erro is None, resultado.erro
        assert len(provedor.prompts) == 1
        assert all(passo in provedor.prompts[0] for passo in de.PASSOS_PERIODO)
        periodo = resultado.metricas[de.METRICA_PERIODO]
        # Nota 2 de 10 vira 0,2, abaixo do limiar pré-registrado.
        assert periodo["score"] == pytest.approx(0.2) and periodo["sucesso"] is False
        assert de.CHAMADAS_POR_METRICA[de.METRICA_PERIODO] == 1

    def test_limiar_e_o_padrao_do_g_eval(self):
        assert de.LIMIAR_PERIODO == 0.5

    def test_agregado_so_traz_as_metricas_medidas(self):
        caso = de.caso_do_registro(dict(_registro(), pergunta="p"))
        bloco = de.agregar([de.ResultadoCaso(caso, {de.METRICA_PERIODO: {"score": 0.8}})])[
            "por_desfecho"
        ][de.DESFECHO_PUBLICADA]
        assert de.METRICA_FIDELIDADE not in bloco
        assert bloco[de.METRICA_PERIODO]["n_no_limiar"] == 1


class TestRegraDaConcordancia:
    """Com o período medido, a regra pré-registrada é faithfulness E período."""

    def test_regras_calculaveis(self):
        from scripts import avaliar_deepeval as script

        so_fidelidade = script._regras({de.METRICA_FIDELIDADE: 1.0, de.METRICA_PERIODO: None})
        assert so_fidelidade == {script.REGRA_FIDELIDADE: True}
        ambas = script._regras({de.METRICA_FIDELIDADE: 1.0, de.METRICA_PERIODO: 0.2})
        assert ambas == {
            script.REGRA_FIDELIDADE: True,
            script.REGRA_PERIODO: False,
            script.REGRA_COMBINADA: False,
        }
        assert script.REGRAS_PRIMARIAS[0] == script.REGRA_COMBINADA

    def test_fidelidade_lida_de_relatorio_anterior(self, tmp_path):
        from scripts import avaliar_deepeval as script

        anterior = tmp_path / "anterior.json"
        anterior.write_text(json.dumps({"casos": [
            {"pergunta_id": "TSTF006", "metricas": {de.METRICA_FIDELIDADE: {"score": 1.0}}},
            {"pergunta_id": "TSTA002", "metricas": {}},
        ]}), encoding="utf-8")
        assert script._fidelidade_de(anterior) == {"TSTF006": 1.0}

    def test_ensaio_do_periodo_conta_uma_chamada_por_caso(self, monkeypatch, capsys):
        from scripts import avaliar_deepeval as script

        config = Config(llm_provider="gemini", deepeval_modelo_juiz=Config().gemini_modelo_llm)
        monkeypatch.setattr(script, "carregar_config", lambda: config)
        monkeypatch.setattr(script.de, "fabricar_juiz", lambda *a, **k: pytest.fail("chamou"))
        assert script.principal(["--metricas", de.METRICA_PERIODO]) == 0
        assert "28 pontuados × 1 chamadas" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# 6. Nada sai pela biblioteca, e o script sem opt-in não chama ninguém
# --------------------------------------------------------------------------- #


class TestIsolamento:
    def test_telemetria_e_autoload_desligados(self):
        assert os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] == "YES"
        assert os.environ["DEEPEVAL_DISABLE_DOTENV"] == "1"
        assert os.environ["DEEPEVAL_DISABLE_LEGACY_KEYFILE"] == "1"
        from deepeval.telemetry.client import telemetry_opt_out

        assert telemetry_opt_out() is True

    def test_variavel_vazia_no_ambiente_nao_derruba_a_metrica(self, monkeypatch):
        """O `.env.example` deixa `AZURE_OPENAI_ENDPOINT` vazia, e o DeepEval a
        valida como URL. Achado rodando a suíte inteira: um teste anterior
        carregava o `.env` e a coleta deste arquivo caía."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
        caso = de.caso_do_registro(dict(_registro(), pergunta="Qual o lucro?"))
        resultado = de.medir_caso(caso, _juiz(ProvedorRoteirizado(ROTEIRO_FIDELIDADE_METADE)))
        assert resultado.erro is None, resultado.erro
        assert os.environ["AZURE_OPENAI_ENDPOINT"] == ""
        # E fora da métrica também: a telemetria do DeepEval relê as
        # configurações numa thread e na saída do processo.
        from deepeval.config.settings import get_settings

        assert get_settings().AZURE_OPENAI_ENDPOINT is None

    def test_plugin_de_pytest_do_deepeval_fora_da_suite(self, pytestconfig):
        assert not pytestconfig.pluginmanager.has_plugin("deepeval")

    def test_ensaio_nao_fabrica_juiz(self, monkeypatch, capsys):
        from scripts import avaliar_deepeval as script

        config = Config(llm_provider="gemini", deepeval_modelo_juiz=Config().gemini_modelo_llm)
        monkeypatch.setattr(script, "carregar_config", lambda: config)

        def proibido(*a, **k):
            raise AssertionError("o ensaio fabricou o juiz")

        monkeypatch.setattr(script.de, "fabricar_juiz", proibido)
        assert script.principal([]) == 0
        saida = capsys.readouterr().out
        assert "Ensaio" in saida and "196 chamadas" in saida

    def test_teto_acima_do_orcamento_do_projeto_barra(self, monkeypatch):
        from scripts import avaliar_deepeval as script

        config = Config(llm_provider="gemini", deepeval_modelo_juiz=Config().gemini_modelo_llm)
        monkeypatch.setattr(script, "carregar_config", lambda: config)
        with pytest.raises(SystemExit, match="ORCAMENTO_TETO_USD"):
            script.principal(["--teto-usd", str(config.orcamento_teto_usd + 1)])

    def test_relatorio_existente_nao_e_sobrescrito_antes_de_gastar(self, monkeypatch, tmp_path):
        from scripts import avaliar_deepeval as script

        config = Config(llm_provider="gemini", deepeval_modelo_juiz=Config().gemini_modelo_llm)
        monkeypatch.setattr(script, "carregar_config", lambda: config)
        monkeypatch.setattr(script.de, "fabricar_juiz", lambda *a, **k: pytest.fail("gastou"))
        existente = tmp_path / "anterior.json"
        existente.write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit, match="já existe"):
            script.principal(["--permitir-api-paga", "--saida", str(existente)])

    def test_rodada_paga_sem_preco_barra_antes_de_chamar(self, monkeypatch):
        from scripts import avaliar_deepeval as script

        config = Config(llm_provider="gemini", deepeval_modelo_juiz="gemini-3.7-flash")
        monkeypatch.setattr(script, "carregar_config", lambda: config)
        monkeypatch.setattr(script.de, "fabricar_juiz", lambda *a, **k: pytest.fail("chamou"))
        with pytest.raises(ValueError, match="preço do juiz"):
            script.principal(["--permitir-api-paga"])
