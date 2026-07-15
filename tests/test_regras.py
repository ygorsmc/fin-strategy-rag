"""Testes das regras de negócio RN01–RN03 e das guardas RNF08/RNF09.

Cobertura exigida por RNF05 e pelo critério de "pronto" (seção 7):
  - RN01: citação obrigatória — checagem mecânica de subconjunto;
  - RN02: recusa por falta de evidência (contrato da geração);
  - RN03: limite de perguntas livres por sessão (default da config);
  - RNF09: mismatch de modelo de embedding gera erro EXPLÍCITO.
"""

from __future__ import annotations

import csv
import json
from types import SimpleNamespace

import numpy as np
import pytest

from src import avaliacao, geracao, indexacao
from scripts import gate_local
from src.config import Config, carregar_config
from src.geracao import Citacao
from src.ollama import endpoint_ollama_e_loopback
from src.recuperacao import Estrategia



# --- RN01: citação obrigatória (checagem mecânica — já implementada) ----------


class TestRN01CitacaoSubconjunto:
    def test_citacao_de_chunk_recuperado_e_valida(self, chunks_exemplo, citacao_valida):
        assert geracao.citacoes_sao_subconjunto([citacao_valida], chunks_exemplo)

    def test_pagina_dentro_do_intervalo_do_chunk_e_valida(self, chunks_exemplo):
        # O 2º chunk de exemplo cobre págs. 12–13
        citacao = Citacao(
            empresa="ITAU",
            documento="itau_release_4T2025",
            trimestre="4T2025",
            pagina=13,
        )
        assert geracao.citacoes_sao_subconjunto([citacao], chunks_exemplo)

    def test_citacao_orfa_e_violacao(self, chunks_exemplo):
        # Documento jamais recuperado naquela consulta -> violação de RN01
        orfa = Citacao(
            empresa="BRADESCO",
            documento="bradesco_release_4T2025",
            trimestre="4T2025",
            pagina=1,
        )
        assert not geracao.citacoes_sao_subconjunto([orfa], chunks_exemplo)

    def test_pagina_fora_do_intervalo_e_violacao(self, chunks_exemplo):
        citacao = Citacao(
            empresa="ITAU",
            documento="itau_release_4T2025",
            trimestre="4T2025",
            pagina=99,
        )
        assert not geracao.citacoes_sao_subconjunto([citacao], chunks_exemplo)

    def test_lista_vazia_e_valida(self, chunks_exemplo):
        # Recusa legítima vem sem citações — não é violação
        assert geracao.citacoes_sao_subconjunto([], chunks_exemplo)


# --- RNF09: guarda de consistência do índice (já implementada) ----------------


class TestRNF09GuardaDeConsistencia:
    def _metadados(self, **kwargs) -> indexacao.MetadadosIndice:
        base = dict(
            provedor="local",
            modelo="paraphrase-multilingual-MiniLM-L12-v2",
            dimensao=384,
            data_construcao="2026-07-15T00:00:00+00:00",
            hash_corpus="abc123",
            n_chunks=100,
        )
        base.update(kwargs)
        return indexacao.MetadadosIndice(**base)

    def test_par_consistente_passa(self):
        indexacao.validar_consistencia(self._metadados(), indexacao.EmbeddingsLocal())

    def test_modelo_diferente_gera_erro_explicito(self):
        metadados = self._metadados(modelo="outro-modelo", dimensao=384)
        with pytest.raises(indexacao.ErroConsistenciaIndice, match="modelo"):
            indexacao.validar_consistencia(metadados, indexacao.EmbeddingsLocal())

    def test_provedor_diferente_gera_erro_explicito(self):
        metadados = self._metadados(provedor="openai")
        with pytest.raises(indexacao.ErroConsistenciaIndice, match="provedor"):
            indexacao.validar_consistencia(metadados, indexacao.EmbeddingsLocal())

    def test_dimensao_diferente_gera_erro_explicito(self):
        metadados = self._metadados(dimensao=1536)
        with pytest.raises(indexacao.ErroConsistenciaIndice, match="dimensao"):
            indexacao.validar_consistencia(metadados, indexacao.EmbeddingsLocal())

    def test_indice_inexistente_tem_mensagem_clara(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="construa o índice"):
            indexacao.carregar_metadados_indice(tmp_path)

    def test_metadados_sao_persistidos_e_recarregados(self, tmp_path):
        metadados = self._metadados()
        indexacao.salvar_metadados_indice(metadados, tmp_path)
        assert indexacao.carregar_metadados_indice(tmp_path) == metadados

    def test_digest_ollama_diferente_gera_erro_explicito(self, monkeypatch):
        monkeypatch.setattr(
            indexacao,
            "resolver_identidade_modelo_ollama",
            lambda *_: "bge-m3@sha256:digest-novo",
        )
        provedor = indexacao.EmbeddingsOllama(Config())
        metadados = self._metadados(
            provedor="ollama",
            modelo="bge-m3@sha256:digest-antigo",
            dimensao=1024,
        )
        with pytest.raises(indexacao.ErroConsistenciaIndice, match="modelo"):
            indexacao.validar_consistencia(metadados, provedor)


# --- RNF06: arquitetura plugável (dispatch — já implementada) ------------------


class TestProvedoresPlugaveis:
    def test_llm_provider_desconhecido_falha_com_mensagem_clara(self):
        config = Config(llm_provider="inexistente")
        with pytest.raises(ValueError, match="LLM_PROVIDER desconhecido"):
            geracao.fabricar_provedor_llm(config)

    def test_embedding_provider_desconhecido_falha_com_mensagem_clara(self):
        config = Config(embedding_provider="inexistente")
        with pytest.raises(ValueError, match="EMBEDDING_PROVIDER desconhecido"):
            indexacao.fabricar_provedor_embeddings(config)

    def test_provedor_sem_credencial_falha_ao_instanciar_nao_ao_usar(self):
        # Critério de "pronto" (seção 7): falha com mensagem clara se faltar chave
        config = Config(llm_provider="openai", openai_api_key="")
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            geracao.fabricar_provedor_llm(config)

    def test_azure_sem_variaveis_lista_o_que_falta(self):
        config = Config(llm_provider="azure_openai")
        with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
            geracao.fabricar_provedor_llm(config)

    def test_ollama_local_nao_exige_credencial(self):
        config = Config(llm_provider="ollama", embedding_provider="ollama")
        assert geracao.fabricar_provedor_llm(config).nome == "ollama"
        embeddings = indexacao.fabricar_provedor_embeddings(config)
        assert embeddings.nome == "ollama"
        assert embeddings.modelo == "bge-m3"
        assert embeddings.dimensao == 1024

    def test_ollama_sem_modelo_falha_com_mensagem_clara(self):
        config = Config(llm_provider="ollama", ollama_modelo_llm="")
        with pytest.raises(ValueError, match="OLLAMA_MODELO_LLM"):
            geracao.fabricar_provedor_llm(config)

    def test_gemini_sem_credencial_falha_com_mensagem_clara(self):
        config = Config(llm_provider="gemini", gemini_api_key="")
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            geracao.fabricar_provedor_llm(config)


class TestAdaptadoresOllama:
    def test_llm_preserva_prompts_e_registra_custo_zero(self):
        chamadas = {}

        class Completions:
            def create(self, **kwargs):
                chamadas.update(kwargs)
                return SimpleNamespace(
                    model="qwen2.5:14b",
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content='{"resposta": null, "recusa": true}'
                            )
                        )
                    ],
                    usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7),
                )

        provedor = geracao.LLMOllama(Config())
        provedor._cliente = SimpleNamespace(
            chat=SimpleNamespace(completions=Completions())
        )
        resposta = provedor.gerar("sistema", "usuario", temperatura=0.0)

        assert chamadas["model"] == "qwen2.5:14b"
        assert chamadas["messages"] == [
            {"role": "system", "content": "sistema"},
            {"role": "user", "content": "usuario"},
        ]
        assert chamadas["temperature"] == 0.0
        assert chamadas["response_format"] == {"type": "json_object"}
        assert resposta.texto.startswith("{")
        assert resposta.modelo == "qwen2.5:14b"
        assert resposta.uso.tokens_entrada == 12
        assert resposta.uso.tokens_saida == 7
        assert resposta.uso.custo_usd == 0.0
        assert resposta.uso.latencia_s >= 0.0

    def test_embeddings_normaliza_e_preserva_ordem(self):
        chamadas = []

        class Embeddings:
            def create(self, **kwargs):
                chamadas.append(kwargs)
                return SimpleNamespace(
                    data=[
                        SimpleNamespace(index=1, embedding=[0.0, 4.0, 0.0]),
                        SimpleNamespace(index=0, embedding=[3.0, 0.0, 0.0]),
                    ]
                )

        config = Config(
            ollama_embedding_dimensao=3, ollama_embedding_batch_size=2
        )
        provedor = indexacao.EmbeddingsOllama(config)
        provedor._cliente = SimpleNamespace(embeddings=Embeddings())
        matriz = provedor.embedar(["primeiro", "segundo"])

        assert chamadas == [{"model": "bge-m3", "input": ["primeiro", "segundo"]}]
        assert matriz.dtype == np.float32
        assert matriz.shape == (2, 3)
        np.testing.assert_allclose(matriz, [[1, 0, 0], [0, 1, 0]])
        np.testing.assert_allclose(np.linalg.norm(matriz, axis=1), [1, 1])
        assert provedor.embedar([]).shape == (0, 3)

    def test_embeddings_rejeita_indices_duplicados(self):
        class Embeddings:
            def create(self, **kwargs):
                return SimpleNamespace(
                    data=[
                        SimpleNamespace(index=0, embedding=[1.0, 0.0]),
                        SimpleNamespace(index=0, embedding=[0.0, 1.0]),
                    ]
                )

        provedor = indexacao.EmbeddingsOllama(
            Config(ollama_embedding_dimensao=2, ollama_embedding_batch_size=2)
        )
        provedor._cliente = SimpleNamespace(embeddings=Embeddings())
        with pytest.raises(RuntimeError, match="índices de embeddings inválidos"):
            provedor.embedar(["a", "b"])

    def test_llm_aceita_usage_ausente(self):
        class Completions:
            def create(self, **kwargs):
                return SimpleNamespace(
                    model=None,
                    choices=[
                        SimpleNamespace(message=SimpleNamespace(content="{}"))
                    ],
                    usage=None,
                )

        provedor = geracao.LLMOllama(Config())
        provedor._cliente = SimpleNamespace(
            chat=SimpleNamespace(completions=Completions())
        )
        resposta = provedor.gerar("s", "u")
        assert resposta.modelo == "qwen2.5:14b"
        assert resposta.uso.tokens_entrada == 0
        assert resposta.uso.tokens_saida == 0


class TestAdaptadorGemini:
    def test_gemini_preserva_contrato_e_calcula_custo(self):
        chamadas = {}

        class Completions:
            def create(self, **kwargs):
                chamadas.update(kwargs)
                return SimpleNamespace(
                    model="gemini-3.1-flash-lite",
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content='{"resposta": null, "recusa": true}'
                            )
                        )
                    ],
                    usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
                )

        config = Config(
            llm_provider="gemini",
            gemini_api_key="chave-de-teste",
            gemini_reasoning_effort="low",
        )
        provedor = geracao.LLMGemini(config)
        provedor._cliente = SimpleNamespace(
            chat=SimpleNamespace(completions=Completions())
        )
        resposta = provedor.gerar("sistema", "usuario", temperatura=0.0)

        assert chamadas["model"] == "gemini-3.1-flash-lite"
        assert chamadas["messages"] == [
            {"role": "system", "content": "sistema"},
            {"role": "user", "content": "usuario"},
        ]
        assert chamadas["temperature"] == 0.0
        assert chamadas["max_tokens"] == 512
        assert chamadas["response_format"] == {"type": "json_object"}
        assert chamadas["reasoning_effort"] == "low"
        assert resposta.modelo == "gemini-3.1-flash-lite"
        assert resposta.uso.tokens_entrada == 100
        assert resposta.uso.tokens_saida == 20
        assert resposta.uso.custo_usd == pytest.approx(0.000055)
        assert resposta.uso.latencia_s >= 0.0


# --- RN03 + RNF08: defaults e log de execuções (já implementados) --------------


class TestRN03LimitesDeExposicao:
    def test_defaults_da_secao_5_14(self, config_padrao: Config):
        assert config_padrao.limite_perguntas_livres_por_sessao == 5
        assert config_padrao.modo_demonstracao_cacheado is True
        assert config_padrao.orcamento_teto_usd == 10.0

    def test_temperatura_zero_por_padrao(self, config_padrao: Config):
        # Determinismo da avaliação (RNF08)
        assert config_padrao.temperatura == 0.0

    def test_defaults_sao_locais_e_sem_chave(self, config_padrao: Config):
        assert config_padrao.llm_provider == "ollama"
        assert config_padrao.embedding_provider == "ollama"
        assert config_padrao.ollama_base_url == "http://127.0.0.1:11434/v1"
        assert config_padrao.ollama_max_tokens == 512
        assert config_padrao.ollama_embedding_batch_size == 4

    def test_variaveis_ollama_sobrescrevem_defaults(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OLLAMA_MODELO_LLM", "modelo-teste")
        monkeypatch.setenv("OLLAMA_EMBEDDING_DIMENSAO", "768")
        monkeypatch.setenv("OLLAMA_EMBEDDING_BATCH_SIZE", "8")
        config = carregar_config(env_file=tmp_path / "inexistente.env")
        assert config.ollama_modelo_llm == "modelo-teste"
        assert config.ollama_embedding_dimensao == 768
        assert config.ollama_embedding_batch_size == 8

    def test_variaveis_gemini_sobrescrevem_defaults(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GEMINI_MODELO_LLM", "modelo-gemini-teste")
        monkeypatch.setenv("GOOGLE_API_KEY", "chave-teste")
        monkeypatch.setenv("GEMINI_MAX_TOKENS", "256")
        config = carregar_config(env_file=tmp_path / "inexistente.env")
        assert config.gemini_modelo_llm == "modelo-gemini-teste"
        assert config.gemini_api_key == "chave-teste"
        assert config.gemini_max_tokens == 256


class TestGateLocal:
    def test_endpoint_remoto_e_recusado_antes_de_chamada(self):
        config = Config(ollama_base_url="https://ollama.exemplo/v1")
        passou, evidencia = gate_local._testar_runtime(config)
        assert passou is False
        assert "loopback" in evidencia

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1:11434/v1",
            "http://localhost:11434/v1",
            "http://[::1]:11434/v1",
        ],
    )
    def test_endpoint_loopback_e_identificado(self, url):
        assert endpoint_ollama_e_loopback(url)

    def test_resposta_numericamente_errada_nao_passa(self):
        objeto = {
            "resposta": "99%",
            "recusa": False,
            "motivo_recusa": None,
            "citacoes": [
                {
                    "empresa": "BTG",
                    "documento": "btg_release_1T2026",
                    "trimestre": "1T2026",
                    "pagina": 6,
                }
            ],
        }
        with pytest.raises(RuntimeError, match="26,6%"):
            gate_local._validar_resposta_fundamentada(objeto)

    def test_citacao_incompleta_nao_passa(self):
        objeto = {
            "resposta": "26,6%",
            "recusa": False,
            "motivo_recusa": None,
            "citacoes": [
                {"documento": "btg_release_1T2026", "pagina": 6}
            ],
        }
        with pytest.raises(RuntimeError, match="única e exata"):
            gate_local._validar_resposta_fundamentada(objeto)

    def test_recusa_rn02_exige_contrato_completo(self):
        gate_local._validar_resposta_recusa(
            {
                "resposta": None,
                "recusa": True,
                "motivo_recusa": "O trecho não contém essa informação.",
                "citacoes": [],
            }
        )
        with pytest.raises(RuntimeError, match="citacoes"):
            gate_local._validar_resposta_recusa(
                {
                    "resposta": None,
                    "recusa": True,
                    "motivo_recusa": "Sem evidência.",
                    "citacoes": [{"pagina": 1}],
                }
            )


class TestRNF08LogDeExecucoes:
    def test_registro_vira_linha_jsonl_com_timestamp(self, tmp_path):
        caminho = avaliacao.registrar_execucao(
            {"modelo": "teste", "estrategia": "semantica"},
            dir_logs=tmp_path,
            arquivo="execucao_teste.jsonl",
        )
        linhas = caminho.read_text(encoding="utf-8").splitlines()
        assert len(linhas) == 1
        registro = json.loads(linhas[0])
        assert registro["modelo"] == "teste"
        assert "timestamp_utc" in registro

    def test_execucoes_sucessivas_sao_anexadas(self, tmp_path):
        for i in range(3):
            caminho = avaliacao.registrar_execucao(
                {"i": i}, dir_logs=tmp_path, arquivo="e.jsonl"
            )
        assert len(caminho.read_text(encoding="utf-8").splitlines()) == 3


# --- Esquemas versionados ------------------------------------------------------


class TestEsquemaConjuntoPadrao:
    def test_perguntas_csv_tem_o_esquema_da_secao_5_8(self, config_padrao: Config):
        with open(config_padrao.conjunto_padrao_path, newline="", encoding="utf-8") as f:
            cabecalho = tuple(next(csv.reader(f)))
        assert cabecalho == avaliacao.COLUNAS_CONJUNTO_PADRAO

    def test_estrategias_cobrem_o_vocabulario_do_env(self):
        # ESTRATEGIA_PADRAO aceita: closed_book | keyword | semantica | hibrida
        assert {e.value for e in Estrategia} == {
            "closed_book",
            "keyword",
            "semantica",
            "hibrida",
        }


# --- RN02: recusa por falta de evidência (contratos pendentes) ------------------


class TestRN02Recusa:
    def test_json_de_recusa_tem_resposta_nula_e_sem_citacoes(self):
        bruto = json.dumps(
            {
                "resposta": None,
                "recusa": True,
                "motivo_recusa": "os trechos não citam o Nubank",
                "citacoes": [],
            }
        )
        resposta = geracao.parsear_resposta_llm(bruto)
        assert resposta.recusa is True
        assert resposta.resposta is None
        assert resposta.citacoes == ()

    def test_json_invalido_tem_uma_unica_tentativa_de_reparo(self):
        # Modo de falha nº 7: nunca re-tentado até passar
        resposta = geracao.parsear_resposta_llm("isto não é JSON {")
        assert resposta.json_invalido is True
        assert resposta.recusa is True  # conservador: lixo conta como erro

    @pytest.mark.parametrize(
        "citacoes",
        [
            [],  # afirmação sem citação nenhuma
            [
                {
                    "empresa": "BRADESCO",  # citação órfã: doc nunca recuperado
                    "documento": "bradesco_release_4T2025",
                    "trimestre": "4T2025",
                    "pagina": 1,
                }
            ],
        ],
    )
    def test_resposta_afirmativa_sem_citacao_e_rebaixada(
        self, chunks_exemplo, citacoes
    ):
        # RN01 mecânico dentro de gerar_resposta: afirmação sem citação
        # de chunk recuperado não pode sair como resposta válida
        class ProvedorFake(geracao.ProvedorLLM):
            nome = "fake"

            def gerar(self, prompt_sistema, prompt_usuario, temperatura=0.0):
                return geracao.RespostaBrutaLLM(
                    texto=json.dumps(
                        {
                            "resposta": "O lucro foi R$ 10,9 bilhões.",
                            "recusa": False,
                            "motivo_recusa": None,
                            "citacoes": citacoes,
                        }
                    ),
                    uso=geracao.UsoLLM(10, 5, 0.0, 0.01),
                    modelo="fake-1",
                )

        resposta, uso = geracao.gerar_resposta(
            "Qual o lucro do Itaú?", chunks_exemplo, ProvedorFake(), Config()
        )
        assert resposta.recusa is True
        assert resposta.resposta is None
        assert resposta.citacoes == ()
        assert "RN01" in resposta.motivo_recusa
        assert uso.tokens_entrada == 10


def _pergunta_padrao(**campos) -> avaliacao.PerguntaPadrao:
    base = dict(
        id="q1",
        conjunto="dev",
        categoria="adversarial",
        subtipo_adversarial="fora_do_corpus",
        pergunta="Qual o lucro do Nubank no 4T2025?",
        resposta_esperada="n/a",
        classe_verificacao="n/a",
        unidade="n/a",
        origem="n/a",
        locais_aceitos="",
        pontos_chave="",
        comportamento_aceito="recusa",
    )
    base.update(campos)
    return avaliacao.PerguntaPadrao(**base)


def _resposta(recusa: bool, citacoes=(), texto="R$ 1,0 bilhão") -> geracao.RespostaGerada:
    return geracao.RespostaGerada(
        resposta=None if recusa else texto,
        recusa=recusa,
        motivo_recusa="sem evidência" if recusa else None,
        citacoes=tuple(citacoes),
    )


class ProvedorContado(geracao.ProvedorLLM):
    """Fake determinístico que conta chamadas e custa `custo_usd` por chamada."""

    nome = "fake"

    def __init__(self, custo_usd: float = 0.0):
        self.chamadas = 0
        self._custo = custo_usd

    def gerar(self, prompt_sistema, prompt_usuario, temperatura=0.0):
        self.chamadas += 1
        return geracao.RespostaBrutaLLM(
            texto=json.dumps(
                {
                    "resposta": None,
                    "recusa": True,
                    "motivo_recusa": "sem evidência no contexto",
                    "citacoes": [],
                }
            ),
            uso=geracao.UsoLLM(10, 5, self._custo, 0.01),
            modelo="fake-1",
        )


def _csv_conjunto(tmp_path, n_perguntas: int):
    caminho = tmp_path / "perguntas.csv"
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=avaliacao.COLUNAS_CONJUNTO_PADRAO)
        escritor.writeheader()
        for i in range(1, n_perguntas + 1):
            escritor.writerow(
                {
                    "id": f"q{i}",
                    "conjunto": "dev",
                    "categoria": "factual",
                    "subtipo_adversarial": "",
                    "pergunta": f"Pergunta {i}?",
                    "resposta_esperada": "R$ 1,0 bilhão",
                    "classe_verificacao": "release_gerencial",
                    "unidade": "R$ milhões",
                    "origem": "tabela",
                    "locais_aceitos": "doc_x:1",
                    "pontos_chave": "",
                    "comportamento_aceito": "",
                }
            )
    return caminho


class TestAvaliacaoDeRecusa:
    def test_adversarial_recusada_conta_como_correta(self):
        pergunta = _pergunta_padrao(comportamento_aceito="recusa")
        assert avaliacao.avaliar_recusa(pergunta, _resposta(recusa=True))
        assert not avaliacao.avaliar_recusa(pergunta, _resposta(recusa=False))

    def test_premissa_falsa_aceita_recusa_ou_correcao_fundamentada(
        self, citacao_valida
    ):
        # Seção 5.8: comportamento_aceito da pergunta decide
        pergunta = _pergunta_padrao(
            subtipo_adversarial="premissa_falsa",
            comportamento_aceito="recusa|correcao_fundamentada",
        )
        assert avaliacao.avaliar_recusa(pergunta, _resposta(recusa=True))
        assert avaliacao.avaliar_recusa(
            pergunta, _resposta(recusa=False, citacoes=[citacao_valida])
        )
        # correção sem citação não é fundamentada
        assert not avaliacao.avaliar_recusa(pergunta, _resposta(recusa=False))

    def test_custo_excedido_pausa_e_reporta(self, tmp_path):
        # RNF03: atingiu ORCAMENTO_TETO_USD -> CustoExcedidoError, nunca estoura
        config = Config(
            conjunto_padrao_path=_csv_conjunto(tmp_path, 3),
            orcamento_teto_usd=0.5,
        )
        from src.recuperacao import Recuperador

        with pytest.raises(avaliacao.CustoExcedidoError, match="teto"):
            avaliacao.executar_avaliacao(
                config,
                Recuperador(config),
                ProvedorContado(custo_usd=1.0),
                [Estrategia.CLOSED_BOOK],
                conjunto="dev",
                dir_checkpoint=tmp_path / "resultados",
            )

    def test_checkpoint_por_pergunta_e_retomavel(self, tmp_path):
        # Modo de falha nº 8: execução interrompida não é perdida nem paga 2×
        from src.recuperacao import Recuperador

        config = Config(conjunto_padrao_path=_csv_conjunto(tmp_path, 2))
        dir_checkpoint = tmp_path / "resultados"
        provedor = ProvedorContado()
        avaliacao.executar_avaliacao(
            config,
            Recuperador(config),
            provedor,
            [Estrategia.CLOSED_BOOK],
            conjunto="dev",
            dir_checkpoint=dir_checkpoint,
        )
        assert provedor.chamadas == 2

        retomada = ProvedorContado()
        metricas = avaliacao.executar_avaliacao(
            config,
            Recuperador(config),
            retomada,
            [Estrategia.CLOSED_BOOK],
            conjunto="dev",
            dir_checkpoint=dir_checkpoint,
        )
        assert retomada.chamadas == 0  # tudo veio do checkpoint
        assert Estrategia.CLOSED_BOOK in metricas

    def test_recall_comparativa_exige_todas_as_instituicoes_no_top_k(
        self, chunks_exemplo
    ):
        # Definição operacional da seção 5.9
        from src.recuperacao import ResultadoRecuperacao

        pergunta = _pergunta_padrao(
            categoria="comparativa",
            pergunta="Quem teve maior ROE no 4T2025: Itaú ou Bradesco?",
            comportamento_aceito="",
        )
        so_itau = [
            ResultadoRecuperacao(c, 1.0, Estrategia.SEMANTICA)
            for c in chunks_exemplo
        ]
        assert not avaliacao.avaliar_recall_at_k(pergunta, so_itau, k=5)

        bradesco = ingestao_chunk_bradesco()
        com_ambos = so_itau + [
            ResultadoRecuperacao(bradesco, 0.9, Estrategia.SEMANTICA)
        ]
        assert avaliacao.avaliar_recall_at_k(pergunta, com_ambos, k=5)


def ingestao_chunk_bradesco():
    from src.ingestao import Chunk

    return Chunk(
        id="BRADESCO_4T2025_release_0001",
        empresa="BRADESCO",
        trimestre="4T2025",
        documento="bradesco_release_4T2025",
        pagina_inicio=5,
        pagina_fim=5,
        posicao_no_documento=1,
        texto=(
            "[BRADESCO | bradesco_release_4T2025 | 4T2025 | pág. 5]\n"
            "O ROE do período foi de 11,3%."
        ),
    )
