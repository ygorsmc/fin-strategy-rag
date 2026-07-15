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

import pytest

from src import avaliacao, geracao, indexacao
from src.config import Config
from src.geracao import Citacao
from src.recuperacao import Estrategia

pendente_geracao = pytest.mark.skip(
    reason="Boilerplate: implementação pendente — AGENTS.md etapa 8 (geração)"
)
pendente_avaliacao = pytest.mark.skip(
    reason="Boilerplate: implementação pendente — AGENTS.md etapa 9 (avaliação)"
)


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


# --- RN03 + RNF08: defaults e log de execuções (já implementados) --------------


class TestRN03LimitesDeExposicao:
    def test_defaults_da_secao_5_14(self, config_padrao: Config):
        assert config_padrao.limite_perguntas_livres_por_sessao == 5
        assert config_padrao.modo_demonstracao_cacheado is True
        assert config_padrao.orcamento_teto_usd == 10.0

    def test_temperatura_zero_por_padrao(self, config_padrao: Config):
        # Determinismo da avaliação (RNF08)
        assert config_padrao.temperatura == 0.0


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


@pendente_geracao
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

    def test_resposta_afirmativa_sem_citacao_e_rebaixada(self):
        # RN01 mecânico dentro de gerar_resposta: afirmação sem citação
        # de chunk recuperado não pode sair como resposta válida
        raise AssertionError("implementar em gerar_resposta")


@pendente_avaliacao
class TestAvaliacaoDeRecusa:
    def test_adversarial_recusada_conta_como_correta(self):
        raise AssertionError("implementar avaliar_recusa")

    def test_premissa_falsa_aceita_recusa_ou_correcao_fundamentada(self):
        # Seção 5.8: comportamento_aceito da pergunta decide
        raise AssertionError("implementar avaliar_recusa")

    def test_custo_excedido_pausa_e_reporta(self):
        # RNF03: atingiu ORCAMENTO_TETO_USD -> CustoExcedidoError, nunca estoura
        with pytest.raises(avaliacao.CustoExcedidoError):
            raise AssertionError("implementar executar_avaliacao")

    def test_checkpoint_por_pergunta_e_retomavel(self):
        # Modo de falha nº 8: execução interrompida não é perdida nem paga 2×
        raise AssertionError("implementar executar_avaliacao")

    def test_recall_comparativa_exige_todas_as_instituicoes_no_top_k(self):
        # Definição operacional da seção 5.9
        raise AssertionError("implementar avaliar_recall_at_k")
