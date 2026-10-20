"""Recall@5 e valor no top-5 do E4 (`fatos`) nas 45 perguntas congeladas.

O E4 ranqueia chunk pelos fatos que `geracao.fatos_numericos_do_chunk`
extrai, o mesmo parser da guarda da RN02. Mudar a leitura da guarda muda a
ordem do E4, e esta medição diz quanto. Custo zero: usa os chunks do índice
BM25 em disco, sem embeddings e sem LLM.

Duas métricas, porque recall por página engana para julgar chunk (AGENTS.md
§3.4):
- recall@5, a definição da avaliação (página aceita, ou todos os bancos e
  períodos da comparativa no top-5);
- valor no top-5 (factuais): algum dos 5 chunks contém o valor do gabarito.

Para comparar duas versões do parser sem misturar métrica com ranqueamento:
    # 1. versão atual: mede e exporta os chunks
    python -m scripts.medir_recuperacao_e4 --exportar-chunks /tmp/chunks.pkl
    # 2. outra versão de src/ (por exemplo `git archive HEAD src`): só o ranking
    PYTHONPATH=<outra> python scripts/medir_recuperacao_e4.py \\
        --chunks-de /tmp/chunks.pkl --so-ranking --saida /tmp/ranking.json
    # 3. versão atual: métricas sobre o ranking da outra
    python -m scripts.medir_recuperacao_e4 --ranking-de /tmp/ranking.json
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.append(str(RAIZ))

TOP_K = 5


def _perguntas(config):
    from src.avaliacao import carregar_conjunto_padrao

    return [
        pergunta
        for pergunta in carregar_conjunto_padrao(config)
        if pergunta.conjunto == "teste"
        and pergunta.categoria in ("factual", "comparativa")
    ]


def _chunks(config, origem: Path | None):
    if origem is not None:
        with open(origem, "rb") as arquivo:
            return pickle.load(arquivo)
    from src.indexacao import calcular_hash_corpus_atual_para_indice, carregar_indice_bm25

    _bm25, chunks = carregar_indice_bm25(
        config=config, hash_corpus_esperado=calcular_hash_corpus_atual_para_indice()
    )
    return chunks


def ranking_e4(config, chunks) -> dict[str, list[str]]:
    from src.recuperacao import Estrategia, Recuperador

    recuperador = Recuperador(
        config, indice_bm25=(None, chunks), hash_corpus_esperado="externo"
    )
    return {
        pergunta.id: [
            resultado.chunk.id
            for resultado in recuperador.recuperar(
                pergunta.pergunta, Estrategia.FATOS, top_k=TOP_K
            )
        ]
        for pergunta in _perguntas(config)
    }


def metricas(config, chunks, ranking: dict[str, list[str]]) -> dict:
    from src.avaliacao import avaliar_recall_at_k
    from src.normalizacao import extrair_numeros_ptbr_tipados, valores_equivalentes
    from src.recuperacao import Estrategia, ResultadoRecuperacao

    por_id = {chunk.id: chunk for chunk in chunks}
    linhas = {}
    for pergunta in _perguntas(config):
        top = [
            ResultadoRecuperacao(por_id[identificador], 0.0, Estrategia.FATOS)
            for identificador in ranking.get(pergunta.id, [])
        ]
        linha = {
            "categoria": pergunta.categoria,
            "recall_ok": avaliar_recall_at_k(pergunta, top, k=TOP_K),
        }
        if pergunta.categoria == "factual":
            esperados = extrair_numeros_ptbr_tipados(pergunta.resposta_esperada)
            linha["valor_no_top5"] = bool(esperados) and any(
                valores_equivalentes(
                    numero.valor, esperados[0].valor, tolerancia_pct=0.000001
                )
                for resultado in top
                for numero in extrair_numeros_ptbr_tipados(resultado.chunk.texto)
            )
        linhas[pergunta.id] = linha
    factuais = [l for l in linhas.values() if l["categoria"] == "factual"]
    comparativas = [l for l in linhas.values() if l["categoria"] == "comparativa"]
    return {
        "recall5_factual": sum(l["recall_ok"] for l in factuais),
        "recall5_comparativa": sum(l["recall_ok"] for l in comparativas),
        "valor_no_top5_factual": sum(l["valor_no_top5"] for l in factuais),
        "n_factual": len(factuais),
        "n_comparativa": len(comparativas),
        "por_pergunta": linhas,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chunks-de", type=Path)
    parser.add_argument("--exportar-chunks", type=Path)
    parser.add_argument("--ranking-de", type=Path)
    parser.add_argument("--so-ranking", action="store_true")
    parser.add_argument("--saida", type=Path)
    args = parser.parse_args()

    from src.config import carregar_config

    config = carregar_config()
    chunks = _chunks(config, args.chunks_de)
    if args.exportar_chunks:
        with open(args.exportar_chunks, "wb") as arquivo:
            pickle.dump(chunks, arquivo)
    if args.ranking_de:
        ranking = json.loads(args.ranking_de.read_text(encoding="utf-8"))
    else:
        ranking = ranking_e4(config, chunks)
    saida = ranking if args.so_ranking else {"ranking": ranking, **metricas(config, chunks, ranking)}
    if not args.so_ranking:
        print(
            f"recall@5 factual {saida['recall5_factual']}/{saida['n_factual']} · "
            f"comparativa {saida['recall5_comparativa']}/{saida['n_comparativa']} · "
            f"valor no top-5 {saida['valor_no_top5_factual']}/{saida['n_factual']}"
        )
    if args.saida:
        args.saida.write_text(
            json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
