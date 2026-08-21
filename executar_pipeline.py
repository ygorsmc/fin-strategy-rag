"""Orquestrador único do pipeline (RNF01) — `python executar_pipeline.py`.

Etapas, na ordem do AGENTS.md: testes (pytest) -> ingestão/qualidade ->
indexação -> avaliação (E0–E3) -> consolidação para o README. A flag
`--amostra` roda 1 banco × 1 trimestre em um namespace separado, sem substituir
o índice nem o cache da execução integral.

`--conjunto {dev,teste}` é independente de `--amostra`: escolhe qual conjunto
de perguntas a etapa de avaliação usa. Sem `--amostra`, `--conjunto dev` roda
as perguntas dev contra o **índice integral** — o caminho que faltava para
medir recall real na etapa 9 (plano §7) sem tocar nas 45 congeladas. Sozinho,
`--amostra` continua valendo dev contra o índice de amostra (RNF01); combinar
`--amostra` com `--conjunto teste` é rejeitado, porque o índice de amostra não
cobre o corpus que o congelado exige.

O pipeline é fail-fast: teste falho ou contrato ainda pendente interrompe as
etapas seguintes e resulta em código de saída diferente de zero.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

RAIZ = Path(__file__).resolve().parent
DIR_AMOSTRA = RAIZ / "artefatos" / "amostra"
DIR_AMOSTRA_INDICE = DIR_AMOSTRA / "indice_vetorial"
DIR_AMOSTRA_RESULTADOS = DIR_AMOSTRA / "resultados_avaliacao"
DIR_AMOSTRA_LOGS = DIR_AMOSTRA / "logs_execucoes"

from src.config import Config, carregar_config  # noqa: E402

if TYPE_CHECKING:
    from src.indexacao import IdentidadeExtracaoIndice

# Reuso estritamente efêmero dentro de uma invocação do orquestrador. A etapa
# de indexação continua autônoma quando executada sozinha, mas o fluxo completo
# não extrai os mesmos 20 PDFs duas vezes seguidas.
_CHUNKS_DA_EXECUCAO: (
    tuple[Config, bool, list, IdentidadeExtracaoIndice] | None
) = None


def etapa_testes(config: Config, amostra: bool) -> str:
    """Roda o pytest (regras de formatação/chunking — passa/falha).
    Métricas de avaliação NÃO vivem aqui (honestidade de avaliação, AGENTS §3)."""
    resultado = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=RAIZ, check=False
    )
    if resultado.returncode != 0:
        raise RuntimeError("pytest falhou — corrija antes de seguir")
    return "pytest ok"


def etapa_ingestao(config: Config, amostra: bool) -> str:
    from src.ingestao import ingerir_corpus
    from src.indexacao import calcular_identidade_extracao

    global _CHUNKS_DA_EXECUCAO
    # Uma falha nesta nova ingestão não pode deixar um snapshot anterior
    # elegível para reuso por uma chamada programática subsequente.
    _CHUNKS_DA_EXECUCAO = None
    identidade_antes = calcular_identidade_extracao(config)
    chunks = ingerir_corpus(
        config,
        amostra=amostra,
        exigir_cobertura_sentinela=True,
        exigir_todos_documentos=True,
        exigir_manifesto_canonico=not amostra,
    )
    identidade_depois = calcular_identidade_extracao(config)
    if identidade_antes != identidade_depois:
        raise RuntimeError(
            "A identidade da extração mudou durante a ingestão; descarte os "
            "chunks e repita a etapa."
        )
    _CHUNKS_DA_EXECUCAO = (config, amostra, chunks, identidade_depois)
    return f"{len(chunks)} chunks gerados e validados"


def etapa_indexacao(config: Config, amostra: bool) -> str:
    from src.indexacao import (
        calcular_identidade_extracao,
        construir_indice_chroma,
        fabricar_provedor_embeddings,
    )
    from src.ingestao import (
        calcular_hash_corpus,
        carregar_metadados_corpus,
        ingerir_corpus,
    )

    global _CHUNKS_DA_EXECUCAO
    if (
        _CHUNKS_DA_EXECUCAO is not None
        and _CHUNKS_DA_EXECUCAO[0] == config
        and _CHUNKS_DA_EXECUCAO[1] == amostra
    ):
        chunks = _CHUNKS_DA_EXECUCAO[2]
        identidade_ingestao = _CHUNKS_DA_EXECUCAO[3]
        _CHUNKS_DA_EXECUCAO = None
    else:
        identidade_antes = calcular_identidade_extracao(config)
        chunks = ingerir_corpus(
            config,
            amostra=amostra,
            exigir_cobertura_sentinela=True,
            exigir_todos_documentos=True,
            exigir_manifesto_canonico=not amostra,
        )
        identidade_ingestao = calcular_identidade_extracao(config)
        if identidade_antes != identidade_ingestao:
            raise RuntimeError(
                "A identidade da extração mudou durante a ingestão; descarte "
                "os chunks e repita a etapa."
            )
    identidade_antes_embeddings = calcular_identidade_extracao(config)
    if identidade_ingestao != identidade_antes_embeddings:
        raise RuntimeError(
            "A identidade da extração mudou antes dos embeddings; o índice "
            "não será construído com chunks obsoletos."
        )
    provedor = fabricar_provedor_embeddings(config)
    dir_saida = DIR_AMOSTRA_INDICE if amostra else None
    documentos_usados = {chunk.documento for chunk in chunks}
    documentos = [
        doc
        for doc in carregar_metadados_corpus()
        if doc.documento in documentos_usados
    ]
    hash_corpus = calcular_hash_corpus(documentos)
    if dir_saida is None:
        metadados = construir_indice_chroma(
            chunks,
            provedor,
            hash_corpus=hash_corpus,
            identidade_extracao=identidade_antes_embeddings,
        )
    else:
        metadados = construir_indice_chroma(
            chunks,
            provedor,
            hash_corpus=hash_corpus,
            dir_saida=dir_saida,
            identidade_extracao=identidade_antes_embeddings,
        )
    namespace = "amostra isolada" if amostra else "integral"
    return (
        f"índices {namespace} construídos "
        f"({metadados.n_chunks} chunks, {metadados.modelo})"
    )


def _conjunto_efetivo(amostra: bool, conjunto: str | None) -> str:
    """Decide o conjunto de perguntas da avaliação, desacoplado do smoke test
    de ingestão. Sem `--conjunto`, preserva o comportamento anterior (dev com
    `--amostra`, teste sem). `--amostra` + `--conjunto teste` é rejeitado: o
    índice de amostra (1 banco × 1 trimestre) não cobre o corpus que as 45
    perguntas congeladas exigem."""
    if conjunto is None:
        return "dev" if amostra else "teste"
    if amostra and conjunto == "teste":
        raise ValueError(
            "--amostra (smoke test RNF01, 1 banco × 1 trimestre) é "
            "incompatível com --conjunto teste: o índice de amostra não "
            "cobre o corpus que as 45 perguntas congeladas exigem. Rode "
            "sem --amostra para avaliar teste."
        )
    return conjunto


def _selecionar_ids_perguntas_amostra(
    config: Config, documentos: set[str], conjunto: str
) -> set[str]:
    from src.avaliacao import carregar_conjunto_padrao

    perguntas = sorted(
        (
            pergunta
            for pergunta in carregar_conjunto_padrao(config)
            if pergunta.conjunto == conjunto
        ),
        key=lambda pergunta: pergunta.id,
    )
    factual = next(
        (
            pergunta
            for pergunta in perguntas
            if pergunta.categoria == "factual"
            and any(
                local.strip().rpartition(":")[0] in documentos
                for local in pergunta.locais_aceitos.split(";")
                if ":" in local
            )
        ),
        None,
    )
    adversarial = next(
        (p for p in perguntas if p.categoria == "adversarial"), None
    )
    if factual is None or adversarial is None:
        raise RuntimeError(
            "A amostra exige uma pergunta factual localizada no documento "
            f"selecionado e uma pergunta adversarial no conjunto {conjunto!r}."
        )
    return {factual.id, adversarial.id}


def etapa_avaliacao(
    config: Config, amostra: bool, conjunto: str | None = None
) -> str:
    from src.avaliacao import executar_avaliacao
    from src.bloqueio import bloqueio_exclusivo
    from src.config import DIR_INDICE_VETORIAL
    from src.geracao import fabricar_provedor_llm
    from src.indexacao import (
        calcular_hash_corpus_atual_para_indice,
        carregar_indice_bm25,
        carregar_indice_chroma,
        fabricar_provedor_embeddings,
    )
    from src.recuperacao import Estrategia, Recuperador

    estrategias = [
        Estrategia.CLOSED_BOOK,
        Estrategia.KEYWORD,
        Estrategia.SEMANTICA,
        Estrategia.HIBRIDA,
        Estrategia.FATOS,
    ]
    conjunto_efetivo = _conjunto_efetivo(amostra, conjunto)
    dir_indice = DIR_AMOSTRA_INDICE if amostra else DIR_INDICE_VETORIAL
    caminho_lock_indice = dir_indice.parent / f".{dir_indice.name}.lock"

    # O lock permanece durante fingerprint + avaliação: assim o snapshot
    # carregado e os hashes publicados nunca pertencem a gerações diferentes.
    # Toda validação RNF09 acontece antes de instanciar/chamar a LLM paga.
    with bloqueio_exclusivo(
        caminho_lock_indice,
        f"o snapshot do índice {dir_indice}",
    ):
        provedor_embeddings = fabricar_provedor_embeddings(config)
        hash_corpus_esperado = calcular_hash_corpus_atual_para_indice(
            dir_indice,
            integral=not amostra,
            bancos=config.bancos,
        )
        indice_chroma = carregar_indice_chroma(
            provedor_embeddings,
            config=config,
            dir_indice=dir_indice,
            hash_corpus_esperado=hash_corpus_esperado,
        )
        indice_bm25 = carregar_indice_bm25(
            config=config,
            dir_indice=dir_indice,
            hash_corpus_esperado=hash_corpus_esperado,
        )
        recuperador = Recuperador(
            config,
            indice_chroma=indice_chroma,
            indice_bm25=indice_bm25,
            provedor_embeddings=provedor_embeddings,
            hash_corpus_esperado=hash_corpus_esperado,
        )
        argumentos = {
            "config": config,
            "recuperador": recuperador,
            "provedor_llm": fabricar_provedor_llm(config),
            "estrategias": estrategias,
            "conjunto": conjunto_efetivo,
            "dir_indice_identidade": dir_indice,
        }
        if amostra:
            argumentos.update(
                {
                    "dir_checkpoint": DIR_AMOSTRA_RESULTADOS,
                    "dir_logs": DIR_AMOSTRA_LOGS,
                    "pergunta_ids": _selecionar_ids_perguntas_amostra(
                        config,
                        {chunk.documento for chunk in indice_chroma[1]},
                        conjunto_efetivo,
                    ),
                }
            )
        metricas = executar_avaliacao(**argumentos)
    return f"avaliação concluída ({conjunto_efetivo}): {len(metricas)} estratégias"


ETAPAS = {
    "testes": etapa_testes,
    "ingestao": etapa_ingestao,
    "indexacao": etapa_indexacao,
    "avaliacao": etapa_avaliacao,
}


def _ordenar_etapas(solicitadas: list[str] | None) -> list[str]:
    """Deduplica e sempre preserva a ordem segura definida em ``ETAPAS``."""
    if not solicitadas:
        return list(ETAPAS)
    conjunto = set(solicitadas)
    return [nome for nome in ETAPAS if nome in conjunto]


def _validar_precondicoes(
    config: Config,
    amostra: bool,
    nomes: list[str],
    permitir_api_paga: bool = False,
    conjunto: str | None = None,
) -> None:
    """Falha antes de etapas caras, externas ou sem contabilidade completa."""
    embeddings_externos = {"openai", "azure_openai"}
    usa_embeddings = bool({"indexacao", "avaliacao"} & set(nomes))
    provedores_externos: list[str] = []
    if "avaliacao" in nomes and config.llm_provider != "ollama":
        provedores_externos.append(f"LLM={config.llm_provider}")
    if usa_embeddings and config.embedding_provider in embeddings_externos:
        provedores_externos.append(
            f"embeddings={config.embedding_provider}"
        )
    if provedores_externos and not permitir_api_paga:
        raise RuntimeError(
            "A execução usaria provedor(es) externo(s): "
            + ", ".join(provedores_externos)
            + ". Repita com --permitir-api-paga somente após revisar o "
            "escopo e o teto ORCAMENTO_TETO_USD."
        )

    if "avaliacao" not in nomes:
        return
    from src.avaliacao import carregar_conjunto_padrao

    conjunto_efetivo = _conjunto_efetivo(amostra, conjunto)
    perguntas = carregar_conjunto_padrao(config)
    if not any(pergunta.conjunto == conjunto_efetivo for pergunta in perguntas):
        complemento = (
            "Use --amostra ou --conjunto dev para avaliar o conjunto dev."
            if conjunto_efetivo != "dev"
            else "Adicione perguntas dev ao gabarito configurado."
        )
        raise RuntimeError(
            f"Nenhuma pergunta com conjunto={conjunto_efetivo!r}; avaliação não "
            f"iniciada. {complemento}"
        )
    if config.embedding_provider in embeddings_externos:
        raise RuntimeError(
            "Avaliação com embeddings externos está bloqueada: o custo das "
            "consultas de recuperação ainda não integra o journal RNF08 nem "
            "o teto por pergunta. Use EMBEDDING_PROVIDER=ollama ou local."
        )


def principal(argv: list[str] | None = None) -> int:
    global _CHUNKS_DA_EXECUCAO
    _CHUNKS_DA_EXECUCAO = None
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--amostra",
        action="store_true",
        help="smoke test: 1 banco × 1 trimestre, conjunto dev (RNF01)",
    )
    parser.add_argument(
        "--etapa",
        choices=sorted(ETAPAS),
        action="append",
        help="roda só a(s) etapa(s) indicada(s); padrão: todas, em ordem",
    )
    parser.add_argument(
        "--permitir-api-paga",
        action="store_true",
        help=(
            "confirma explicitamente chamadas externas na etapa de avaliação; "
            "dispensável quando LLM_PROVIDER=ollama"
        ),
    )
    parser.add_argument(
        "--conjunto",
        choices=["dev", "teste"],
        default=None,
        help=(
            "conjunto de perguntas para a etapa de avaliação, desacoplado do "
            "smoke test de ingestão; padrão: dev com --amostra, teste sem. "
            "'--conjunto dev' sem '--amostra' roda dev contra o índice "
            "integral"
        ),
    )
    args = parser.parse_args(argv)

    config = carregar_config()
    nomes = _ordenar_etapas(args.etapa)
    resumo: list[tuple[str, str, str]] = []
    try:
        _validar_precondicoes(
            config,
            args.amostra,
            nomes,
            permitir_api_paga=args.permitir_api_paga,
            conjunto=args.conjunto,
        )
    except Exception as exc:
        print(f"FALHOU na pré-validação: {exc}")
        return 1

    for nome in nomes:
        print(f"\n=== Etapa: {nome} {'(amostra)' if args.amostra else ''} ===")
        try:
            detalhe = (
                etapa_avaliacao(config, args.amostra, conjunto=args.conjunto)
                if nome == "avaliacao"
                else ETAPAS[nome](config, args.amostra)
            )
            resumo.append((nome, "OK", detalhe))
        except Exception as exc:
            resumo.append((nome, "FALHOU", f"{type(exc).__name__}: {exc}"))
            print(f"FALHOU: {exc}")
            break

    print("\n=== Resumo do pipeline ===")
    for nome, status, detalhe in resumo:
        print(f"  {status:8s} {nome:12s} {detalhe}")
    executou_tudo = len(resumo) == len(nomes)
    _CHUNKS_DA_EXECUCAO = None
    return (
        0
        if executou_tudo and all(status == "OK" for _, status, _ in resumo)
        else 1
    )


if __name__ == "__main__":
    sys.exit(principal())
