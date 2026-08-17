from __future__ import annotations

import json
import csv
from dataclasses import asdict
from types import SimpleNamespace

import numpy as np
import pytest

from src import auditoria, avaliacao, geracao, normalizacao, recuperacao
from src.avaliacao import PerguntaPadrao, ResultadoItem
from src.config import Config
from src.geracao import Citacao
from src.ingestao import Chunk, DocumentoCorpus, validar_manifesto_canonico
from src.recuperacao import Estrategia, ResultadoRecuperacao


def _chunk(
    identificador: str,
    empresa: str,
    trimestre: str,
    texto: str = "ROAE 20%",
) -> Chunk:
    documento = f"{empresa.lower()}_release_{trimestre}"
    return Chunk(
        id=identificador,
        empresa=empresa,
        trimestre=trimestre,
        documento=documento,
        pagina_inicio=1,
        pagina_fim=1,
        posicao_no_documento=1,
        texto=f"[{empresa} | {documento} | {trimestre} | pág. 1]\n{texto}",
    )


def _pergunta(
    identificador: str,
    categoria: str,
    texto: str,
    subtipo: str = "",
) -> PerguntaPadrao:
    return PerguntaPadrao(
        id=identificador,
        conjunto="teste",
        categoria=categoria,
        subtipo_adversarial=subtipo,
        pergunta=texto,
        resposta_esperada="R$ 1 milhão",
        classe_verificacao="release_gerencial",
        unidade="R$ milhões",
        origem="texto",
        locais_aceitos="" if categoria == "adversarial" else "doc:1",
        pontos_chave="ponto" if categoria == "qualitativa" else "",
        comportamento_aceito="recusa" if categoria == "adversarial" else "",
    )


def test_parser_filtra_data_reconhece_r_mm_e_subtracao_binaria():
    assert normalizacao.extrair_numeros_ptbr(
        "O trimestre encerrou em 30 de junho de 2025."
    ) == []
    assert normalizacao.extrair_numeros_ptbr(
        "(em R$mm, a menos que indicado)\nLucro líquido 4.597,1"
    ) == [4_597_100_000.0]
    assert normalizacao.extrair_numeros_ptbr(
        "26,6% - 24,8% = 1,8 p.p."
    ) == pytest.approx([0.266, 0.248, 0.018])


def test_grounding_nao_usa_data_como_moeda():
    chunk = _chunk(
        "a",
        "BTG",
        "2T2025",
        "O trimestre encerrou em 30 de junho de 2025.",
    )


def test_grounding_nao_usa_valor_de_outra_metrica():
    chunk = _chunk(
        "metrica",
        "BTG",
        "2T2025",
        "Ativos totais: R$ 30 bilhões.",
    )
    citacoes = (Citacao("BTG", chunk.documento, "2T2025", 1),)
    assert not geracao.numeros_da_resposta_estao_fundamentados(
        "Lucro do BTG: R$ 30 bilhões.",
        citacoes,
        [chunk],
        1.0,
    )
    assert geracao.numeros_da_resposta_estao_fundamentados(
        "Ativos totais do BTG: R$ 30 bilhões.",
        citacoes,
        [chunk],
        1.0,
    )
    assert not geracao.numeros_da_resposta_estao_fundamentados(
        "BTG teve lucro de R$ 30.",
        (Citacao("BTG", chunk.documento, "2T2025", 1),),
        [chunk],
        1.0,
    )


def test_cobertura_exige_todos_os_bancos_e_periodos():
    citacoes = (Citacao("ITAU", "itau_release_1T2026", "1T2026", 1),)
    config = Config()
    assert not geracao._escopo_solicitado_esta_coberto(
        "Compare Itaú e Nubank no 1T2026.", citacoes, config
    )
    assert not geracao._escopo_solicitado_esta_coberto(
        "Qual banco teve maior ROAE no 1T2026?", citacoes, config
    )


def test_gemini_recusa_resposta_sem_usage_auditavel():
    provedor = object.__new__(geracao.LLMGemini)
    provedor._config = Config(
        gemini_api_key="segredo-falso",
        gemini_modelo_llm="modelo",
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    resposta = SimpleNamespace(
        model="modelo",
        choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
        usage=None,
    )
    provedor._cliente = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_: resposta)
        )
    )
    with pytest.raises(RuntimeError, match="telemetria"):
        provedor.gerar("sistema", "usuario")


def test_recuperacao_intercala_cartesiano_banco_periodo():
    chunks = [
        _chunk(f"{banco}_{periodo}", banco, periodo)
        for banco in ("ITAU", "BTG")
        for periodo in ("4T2025", "1T2026")
    ]

    class BM25:
        def get_scores(self, _tokens):
            return np.ones(len(chunks), dtype=float)

    recuperador = recuperacao.Recuperador(
        Config(), indice_bm25=(BM25(), chunks)
    )
    resultados = recuperador.recuperar(
        "Compare Itaú e BTG no 4T2025 e no 1T2026",
        Estrategia.KEYWORD,
        top_k=4,
    )
    assert {
        (resultado.chunk.empresa, resultado.chunk.trimestre)
        for resultado in resultados
    } == {
        ("ITAU", "4T2025"),
        ("ITAU", "1T2026"),
        ("BTG", "4T2025"),
        ("BTG", "1T2026"),
    }


def test_recall_comparativo_rejeita_par_banco_periodo_ausente():
    pergunta = _pergunta(
        "cmp",
        "comparativa",
        "Compare Itaú e BTG no 4T2025 e no 1T2026",
    )
    recuperados = [
        ResultadoRecuperacao(
            _chunk(f"{banco}_{periodo}", banco, periodo),
            1.0,
            Estrategia.SEMANTICA,
        )
        for banco, periodo in (
            ("ITAU", "4T2025"),
            ("ITAU", "1T2026"),
            ("BTG", "4T2025"),
        )
    ]
    assert not avaliacao.avaliar_recall_at_k(pergunta, recuperados)


def test_consolidacao_inclui_falha_historica_no_debito():
    falha = ResultadoItem(
        "q1",
        Estrategia.SEMANTICA,
        None,
        custo_usd=0.75,
        custo_observado_usd=None,
        erro="timeout",
        run_id="r1",
    )
    sucesso = ResultadoItem(
        "q1",
        Estrategia.SEMANTICA,
        geracao.RespostaGerada("ok", False, None, ()),
        custo_usd=0.10,
        custo_observado_usd=0.10,
        run_id="r2",
    )
    metrica = avaliacao.consolidar_metricas(
        [sucesso], tentativas=[falha, sucesso]
    )[Estrategia.SEMANTICA]
    assert metrica.custo_conservador_medio_usd == pytest.approx(0.85)
    assert metrica.custo_observado_medio_usd == pytest.approx(0.10)
    assert metrica.n_erros == 0
    assert metrica.n_erros_pendentes == 0
    assert metrica.n_erros_historicos == 1
    assert metrica.n_tentativas_sem_telemetria == 1


def test_exatidao_nao_usa_numero_de_outra_metrica():
    pergunta = _pergunta(
        "fat",
        "factual",
        "Qual foi o resultado recorrente no 1T2026?",
    )
    pergunta = PerguntaPadrao(
        **{
            **pergunta.__dict__,
            "resposta_esperada": "R$ 11.508 milhões",
        }
    )
    resposta = geracao.RespostaGerada(
        "A carteira foi R$ 11.508 milhões; "
        "o resultado recorrente foi R$ 9.000 milhões.",
        False,
        None,
        (),
    )
    assert not avaliacao.avaliar_exatidao_numerica(
        pergunta, resposta, Config()
    )


def test_premissa_falsa_rejeita_direcao_e_ordem_invertidas():
    pergunta = _pergunta(
        "adv",
        "adversarial",
        "Por que o lucro caiu?",
        subtipo="premissa_falsa",
    )
    pergunta = PerguntaPadrao(
        **{
            **pergunta.__dict__,
            "resposta_esperada": (
                "A premissa é falsa: subiu de R$ 3.785 milhões para "
                "R$ 5.742 milhões, alta de 51,7%."
            ),
            "comportamento_aceito": "recusa|correcao_fundamentada",
        }
    )
    resposta = geracao.RespostaGerada(
        "A premissa é falsa: caiu de R$ 5.742 milhões para "
        "R$ 3.785 milhões, queda de 51,7%.",
        False,
        None,
        (Citacao("BB", "doc", "4T2025", 1),),
    )
    assert not avaliacao.avaliar_recusa(pergunta, resposta)


def test_write_ahead_bloqueia_chamada_sem_resultado(tmp_path):
    journal = tmp_path / "journal.jsonl"
    avaliacao._anexar_evento_journal_chamada(
        journal,
        {
            "evento": "inicio",
            "call_id": "call-1",
            "fingerprint": "f" * 64,
            "run_id": "run",
            "pergunta_id": "q1",
            "estrategia": "semantica",
            "tentativa": 1,
            "estimativa_maxima_usd": 0.2,
        },
    )
    with pytest.raises(avaliacao.AvaliacaoIncompletaError, match="reconciliação"):
        avaliacao._validar_journal_chamadas(journal, "f" * 64, [])
    avaliacao._anexar_evento_journal_chamada(
        journal,
        {
            "evento": "fim",
            "call_id": "call-1",
            "fingerprint": "f" * 64,
            "run_id": "run",
            "resultado": "erro",
            "erro": "InterrupcaoReconciliada",
            "debito_conservador_usd": 0.2,
        },
    )
    item = ResultadoItem(
        "q1",
        Estrategia.SEMANTICA,
        None,
        custo_usd=0.2,
        custo_observado_usd=None,
        custo_estimado_falhas_usd=0.2,
        n_chamadas=1,
        n_chamadas_sem_telemetria=1,
        erro="InterrupcaoReconciliada",
        run_id="run",
        fingerprint="f" * 64,
        call_ids=("call-1",),
    )
    avaliacao._validar_journal_chamadas(
        journal,
        "f" * 64,
        [item],
    )


def test_loader_ignora_corrupcao_de_outro_fingerprint_e_cauda_truncada(tmp_path):
    caminho = tmp_path / "checkpoint.jsonl"
    caminho.write_text(
        '{"fingerprint":"antigo",isto-nao-e-json\n'
        '{"fingerprint":"atual"',
        encoding="utf-8",
    )
    assert avaliacao._carregar_checkpoint(caminho, "atual") == []


def test_serializacao_redige_pii_de_chunk_e_resposta():
    chunk = _chunk(
        "pii",
        "BTG",
        "1T2026",
        "CPF 123.456.789-00\ncontato pessoa@example.com",
    )
    serializado = avaliacao._serializar_recuperado(
        ResultadoRecuperacao(chunk, 1.0, Estrategia.KEYWORD)
    )
    texto = json.dumps(serializado, ensure_ascii=False)
    assert "123.456.789-00" not in texto
    assert "pessoa@example.com" not in texto


def test_manifesto_canonico_exige_intersecao_5_por_4():
    bancos = Config().bancos
    documentos = [
        DocumentoCorpus(
            empresa=banco,
            trimestre=periodo,
            documento=f"{banco}_{periodo}",
            url="https://example.invalid/doc.pdf",
            data_coleta="2026-01-01",
            hash_sha256="a" * 64,
        )
        for banco in bancos
        for periodo in ("2T2025", "3T2025", "4T2025", "1T2026")
    ]
    validar_manifesto_canonico(documentos, bancos)
    with pytest.raises(ValueError, match="20 documentos"):
        validar_manifesto_canonico(documentos[:-1], bancos)


def test_conjunto_teste_final_rejeita_distribuicao_parcial():
    with pytest.raises(ValueError, match="45 perguntas"):
        avaliacao._validar_conjunto_teste_final(
            [_pergunta("q1", "factual", "Qual foi o valor?")]
        )


def _gravar_conjunto_final(caminho):
    categorias = (
        [("factual", "", 15), ("comparativa", "", 10),
         ("qualitativa", "", 10), ("adversarial", "fora_do_corpus", 10)]
    )
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=avaliacao.COLUNAS_CONJUNTO_PADRAO
        )
        escritor.writeheader()
        contador = 0
        for categoria, subtipo, quantidade in categorias:
            for indice in range(quantidade):
                contador += 1
                nubank = categoria == "adversarial" and indice < 4
                escritor.writerow(
                    {
                        "id": f"Q{contador:03d}",
                        "conjunto": "teste",
                        "categoria": categoria,
                        "subtipo_adversarial": subtipo,
                        "pergunta": (
                            f"Qual foi o lucro "
                            + ("do Nubank" if nubank else "divulgado")
                            + f" na pergunta {contador}?"
                        ),
                        "resposta_esperada": "R$ 1 milhão",
                        "classe_verificacao": "release_gerencial",
                        "unidade": "R$ milhões",
                        "origem": "texto",
                        "locais_aceitos": (
                            "" if categoria == "adversarial" else "doc:1"
                        ),
                        "pontos_chave": (
                            "ponto" if categoria == "qualitativa" else ""
                        ),
                        "comportamento_aceito": (
                            "recusa" if categoria == "adversarial" else ""
                        ),
                    }
                )


def _item_auditoria(
    pergunta: PerguntaPadrao,
    fingerprint: str,
    run_id: str,
    *,
    call_id: str,
    estrategia: Estrategia = Estrategia.SEMANTICA,
    modelo: str = "modelo-fixture",
) -> ResultadoItem:
    adversarial = pergunta.categoria == "adversarial"
    qualitativa = pergunta.categoria == "qualitativa"
    chunk = Chunk(
        id=f"chunk-{pergunta.id}",
        empresa="ITAU",
        trimestre="1T2026",
        documento="doc",
        pagina_inicio=1,
        pagina_fim=1,
        posicao_no_documento=1,
        texto=(
            "[ITAU | doc | 1T2026 | pág. 1]\n"
            + ("Ponto qualitativo." if qualitativa else "Lucro: R$ 1 milhão.")
        ),
    )
    recuperados = (
        []
        if estrategia == Estrategia.CLOSED_BOOK
        else [ResultadoRecuperacao(chunk, 1.0, estrategia)]
    )
    citacoes = (
        ()
        if adversarial or estrategia == Estrategia.CLOSED_BOOK
        else (Citacao("ITAU", "doc", "1T2026", 1),)
    )
    resposta = geracao.RespostaGerada(
        None if adversarial else ("Ponto qualitativo." if qualitativa else "Lucro: R$ 1 milhão."),
        adversarial,
        "Informação não consta no corpus." if adversarial else None,
        citacoes,
    )
    recall_ok = (
        avaliacao.avaliar_recall_at_k(pergunta, recuperados)
        if pergunta.categoria in {"factual", "comparativa"}
        and estrategia != Estrategia.CLOSED_BOOK
        else None
    )
    exatidao_ok = (
        avaliacao.avaliar_exatidao_numerica(pergunta, resposta, Config())
        if pergunta.categoria == "factual"
        else None
    )
    recusa_correta = (
        avaliacao.avaliar_recusa(pergunta, resposta) if adversarial else None
    )
    return ResultadoItem(
        pergunta.id,
        estrategia,
        resposta,
        categoria=pergunta.categoria,
        recuperados=recuperados,
        recall_ok=recall_ok,
        exatidao_ok=exatidao_ok,
        recusa_correta=recusa_correta,
        custo_usd=0.01,
        custo_observado_usd=0.01,
        n_chamadas=1,
        tokens_entrada=10,
        tokens_saida=5,
        modelo=modelo,
        run_id=run_id,
        fingerprint=fingerprint,
        call_ids=(call_id,),
    )


def test_selecao_de_auditoria_e_promocao_sao_fixas_e_fail_closed(
    tmp_path, monkeypatch
):
    caminho_csv = tmp_path / "perguntas.csv"
    _gravar_conjunto_final(caminho_csv)
    config = Config(
        conjunto_padrao_path=caminho_csv,
        estrategia_padrao="semantica",
    )
    perguntas = avaliacao.carregar_conjunto_padrao(config)
    componentes_base = {
        "fixture": "auditoria-integral",
        "repeticao_estabilidade": None,
        "perguntas_selecionadas": [asdict(pergunta) for pergunta in perguntas],
    }
    fingerprint = avaliacao.hash_json_canonico(componentes_base)
    primeira = auditoria.selecionar_ids_estratificados(
        perguntas, fingerprint, auditoria.COTAS_GROUNDEDNESS
    )
    assert len(primeira) == 15
    assert primeira == auditoria.selecionar_ids_estratificados(
        perguntas, fingerprint, auditoria.COTAS_GROUNDEDNESS
    )

    monkeypatch.setattr(
        auditoria,
        "validar_estado_material_atual",
        lambda *args, **kwargs: None,
    )
    itens_base = [
        _item_auditoria(
            pergunta,
            fingerprint,
            "run-base",
            call_id=f"base-{estrategia.value}-{pergunta.id}",
            estrategia=estrategia,
        )
        for pergunta in perguntas
        for estrategia in Estrategia
    ]
    for item in itens_base:
        avaliacao._anexar_checkpoint(tmp_path / "checkpoint_teste.jsonl", item)
    avaliacao._salvar_metricas(
        avaliacao.consolidar_metricas(itens_base, tentativas=itens_base),
        tmp_path / "metricas_teste.json",
        fingerprint=fingerprint,
        run_id="run-base",
        run_ids=["run-base"],
        conjunto="teste",
        estrategia_demo_e_auditoria="semantica",
        provedor_llm="ollama",
        fingerprint_componentes=componentes_base,
    )
    cache = avaliacao._construir_cache_demo(
        perguntas,
        itens_base,
        "ollama",
        estrategia_demo=Estrategia.SEMANTICA,
        fingerprint=fingerprint,
        conjunto="teste",
    )
    (tmp_path / "respostas_cacheadas.json").write_text(
        json.dumps(cache), encoding="utf-8"
    )

    caminho_groundedness, caminho_plano = auditoria.preparar_auditoria_final(
        config, tmp_path
    )
    groundedness = json.loads(caminho_groundedness.read_text(encoding="utf-8"))
    for registro in groundedness["avaliacoes"]:
        registro.update(
            {
                "grounded": True,
                "auditor_id": "segunda-leitura",
                "data_auditoria": "2026-07-29T12:00:00-03:00",
                "observacao": "Conferido contra os chunks imutáveis.",
            }
        )
    caminho_groundedness.write_text(json.dumps(groundedness), encoding="utf-8")

    plano = json.loads(caminho_plano.read_text(encoding="utf-8"))
    ids_estabilidade = set(plano["pergunta_ids"])
    perguntas_repeticao = [
        pergunta for pergunta in perguntas if pergunta.id in ids_estabilidade
    ]
    for repeticao in (1, 2, 3):
        componentes_rep = {
            **componentes_base,
            "repeticao_estabilidade": repeticao,
            "perguntas_selecionadas": [
                asdict(pergunta) for pergunta in perguntas_repeticao
            ],
        }
        fingerprint_rep = avaliacao.hash_json_canonico(componentes_rep)
        run_id = f"run-rep-{repeticao}"
        itens_repeticao = [
            _item_auditoria(
                pergunta,
                fingerprint_rep,
                run_id,
                call_id=f"rep-{repeticao}-{pergunta.id}",
            )
            for pergunta in perguntas_repeticao
        ]
        for item in itens_repeticao:
            avaliacao._anexar_checkpoint(
                tmp_path / f"checkpoint_estabilidade_{repeticao}.jsonl",
                item,
            )
        avaliacao._salvar_metricas(
            avaliacao.consolidar_metricas(
                itens_repeticao, tentativas=itens_repeticao
            ),
            tmp_path / f"metricas_estabilidade_{repeticao}.json",
            fingerprint=fingerprint_rep,
            run_id=run_id,
            run_ids=[run_id],
            conjunto="estabilidade",
            estrategia_demo_e_auditoria="semantica",
            provedor_llm="ollama",
            fingerprint_componentes=componentes_rep,
        )

    caminho_metricas_rep1 = tmp_path / "metricas_estabilidade_1.json"
    metricas_rep1_originais = json.loads(
        caminho_metricas_rep1.read_text(encoding="utf-8")
    )
    metricas_rep1_adulteradas = json.loads(
        json.dumps(metricas_rep1_originais)
    )
    metricas_rep1_adulteradas["_meta"]["fingerprint_componentes"][
        "fixture"
    ] = "outro-codigo-ou-indice"
    fingerprint_adulterado = avaliacao.hash_json_canonico(
        metricas_rep1_adulteradas["_meta"]["fingerprint_componentes"]
    )
    metricas_rep1_adulteradas["_meta"]["fingerprint"] = (
        fingerprint_adulterado
    )
    metricas_rep1_adulteradas["_meta"][
        "fingerprint_componentes_sha256"
    ] = fingerprint_adulterado
    caminho_metricas_rep1.write_text(
        json.dumps(metricas_rep1_adulteradas), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="manifesto material base"):
        auditoria.consolidar_estabilidade(config, tmp_path)
    caminho_metricas_rep1.write_text(
        json.dumps(metricas_rep1_originais), encoding="utf-8"
    )

    caminho_checkpoint_rep1 = tmp_path / "checkpoint_estabilidade_1.jsonl"
    checkpoint_rep1_original = caminho_checkpoint_rep1.read_text(
        encoding="utf-8"
    )
    linhas_rep1 = checkpoint_rep1_original.splitlines()
    primeiro_item_rep1 = json.loads(linhas_rep1[0])
    primeiro_item_rep1["modelo"] = "modelo-alias-alterado"
    linhas_rep1[0] = json.dumps(primeiro_item_rep1)
    caminho_checkpoint_rep1.write_text(
        "\n".join(linhas_rep1) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="misturam modelos"):
        auditoria.consolidar_estabilidade(config, tmp_path)
    caminho_checkpoint_rep1.write_text(
        checkpoint_rep1_original, encoding="utf-8"
    )

    auditoria.consolidar_estabilidade(config, tmp_path)
    metricas_originais = json.loads(
        (tmp_path / "metricas_teste.json").read_text(encoding="utf-8")
    )
    metricas_adulteradas = json.loads(json.dumps(metricas_originais))
    metricas_adulteradas["semantica"]["recall_at_5"] = 0.123
    (tmp_path / "metricas_teste.json").write_text(
        json.dumps(metricas_adulteradas), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="divergem do checkpoint"):
        auditoria.promover_metricas_auditadas(config, tmp_path)
    (tmp_path / "metricas_teste.json").write_text(
        json.dumps(metricas_originais), encoding="utf-8"
    )
    original = json.loads(caminho_groundedness.read_text(encoding="utf-8"))
    adulterado = json.loads(json.dumps(original))
    adulterado["avaliacoes"][0]["pergunta"] = "Contexto adulterado"
    caminho_groundedness.write_text(json.dumps(adulterado), encoding="utf-8")
    with pytest.raises(ValueError, match="Contexto da auditoria"):
        auditoria.promover_metricas_auditadas(config, tmp_path)
    caminho_groundedness.write_text(json.dumps(original), encoding="utf-8")

    promovidas = auditoria.promover_metricas_auditadas(config, tmp_path)
    assert promovidas["_meta"]["status"] == "completa"
    assert promovidas["_meta"]["groundedness_manual_score"] == 1.0
    assert promovidas["_meta"]["cache_demo_sha256"] == (
        avaliacao.hash_json_canonico(cache)
    )
