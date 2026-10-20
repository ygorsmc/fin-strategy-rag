"""DeepEval (faithfulness, answer relevancy) sobre a rodada congelada (spec 5.15).

Dois modos:

* **conjunto congelado** (padrão): as 45 perguntas `teste`, uma estratégia da
  rodada publicada em `metricas_teste.json` (padrão: a do produto,
  `estrategia_demo_e_auditoria`). Lê respostas e trechos do checkpoint; não
  gera resposta nenhuma.
* **concordância** (`--concordancia AUDITORIA.json`): a mesma métrica de
  faithfulness sobre os itens que um humano auditou às cegas, e a matriz juiz ×
  humano, com a régua de `scripts/medir_juiz_groundedness.py`. É o que a spec
  5.15 chama de medir o DeepEval contra a auditoria humana.

Sem `--permitir-api-paga` é ensaio: conta casos e chamadas, mostra o juiz e o
preço que seriam usados, e não chama nada. Com ela, cada chamada do juiz passa
pelo teto (`--teto-usd`) e é registrada antes e depois em
`artefatos/logs_execucoes/` (RNF08).

Uso:
    python -m scripts.avaliar_deepeval
    python -m scripts.avaliar_deepeval --permitir-api-paga --teto-usd 1.0
    python -m scripts.avaliar_deepeval --concordancia \\
        artefatos/resultados_avaliacao/auditoria_groundedness_a0bea525.json --permitir-api-paga
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src import avaliacao_deepeval as de  # noqa: E402
from src.avaliacao import carregar_conjunto_padrao, registrar_execucao  # noqa: E402
from src.config import DIR_RESULTADOS_AVALIACAO, carregar_config  # noqa: E402

CHAMADAS_POR_CASO = 7  # faithfulness: verdades, afirmações, veredictos, razão; relevância: 3


def _versao_deepeval() -> str:
    from importlib.metadata import version

    return version("deepeval")


def _casos_do_congelado(config, estrategia: str | None):
    metricas = json.loads((DIR_RESULTADOS_AVALIACAO / "metricas_teste.json").read_text(encoding="utf-8"))
    meta = metricas["_meta"]
    estrategia = estrategia or meta["estrategia_demo_e_auditoria"]
    perguntas = {p.id: p.pergunta for p in carregar_conjunto_padrao(config) if p.conjunto == "teste"}
    casos = de.carregar_casos(
        DIR_RESULTADOS_AVALIACAO / "checkpoint_teste.jsonl",
        meta["fingerprint"],
        estrategia,
        perguntas,
    )
    if len(casos) != len(perguntas):
        raise SystemExit(
            f"FALHOU: {len(casos)} casos para {len(perguntas)} perguntas congeladas "
            f"na estratégia {estrategia!r}; a rodada publicada está incompleta."
        )
    return casos, meta["fingerprint"], estrategia, meta.get("status") or meta.get("avaliacao_automatica")


def _casos_da_auditoria(caminho: Path):
    auditoria = json.loads(caminho.read_text(encoding="utf-8"))
    faltando = [a["pergunta_id"] for a in auditoria["avaliacoes"] if not isinstance(a.get("grounded"), bool)]
    if faltando:
        raise SystemExit(f"FALHOU: auditoria humana incompleta em {faltando}.")
    casos, humano = [], {}
    for item in auditoria["avaliacoes"]:
        registro = {
            "pergunta_id": item["pergunta_id"],
            "categoria": item.get("categoria"),
            "estrategia": auditoria["_meta"].get("estrategia", ""),
            "pergunta": item["pergunta"],
            "resposta": item["resposta"],
            "recuperados": item["chunks_citados_e_recuperados"],
        }
        casos.append(de.caso_do_registro(registro))
        humano[item["pergunta_id"]] = item
    return casos, humano, auditoria["_meta"]["fingerprint"]


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--estrategia", default=None)
    parser.add_argument("--concordancia", type=Path, default=None)
    parser.add_argument("--limite", type=int, default=None, help="só os N primeiros casos pontuados")
    parser.add_argument("--teto-usd", type=float, default=1.0)
    parser.add_argument("--saida", type=Path, default=None)
    parser.add_argument("--sobrescrever", action="store_true", help="permite substituir relatório existente")
    parser.add_argument("--permitir-api-paga", action="store_true")
    args = parser.parse_args(argv)

    config = carregar_config()
    if not 0 < args.teto_usd <= config.orcamento_teto_usd:
        raise SystemExit(
            f"FALHOU: --teto-usd {args.teto_usd} fora de (0, ORCAMENTO_TETO_USD={config.orcamento_teto_usd}]."
        )
    try:
        juiz_config = de.config_do_juiz(config)
    except ValueError as erro:
        # No ensaio o problema de configuração é relatado e a contagem segue;
        # na rodada paga ele barra antes de qualquer chamada.
        if args.permitir_api_paga:
            raise
        print(f"Juiz NÃO configurável: {erro}")
        juiz_config = None
    descricao_juiz = {}
    if juiz_config is not None:
        campo_modelo, campo_entrada, campo_saida = de._CAMPOS_DO_PROVEDOR[juiz_config.llm_provider]
        prefixo = campo_modelo.split("_")[0]
        descricao_juiz = {
            "provedor": juiz_config.llm_provider,
            "modelo": getattr(juiz_config, campo_modelo),
            "preco_entrada_usd_milhao": getattr(juiz_config, campo_entrada),
            "preco_saida_usd_milhao": getattr(juiz_config, campo_saida),
            # Parâmetros da chamada (RNF08): mudam o veredito e o custo.
            "reasoning_effort": getattr(juiz_config, f"{prefixo}_reasoning_effort", None),
            "max_tokens": getattr(juiz_config, f"{prefixo}_max_tokens", None),
        }
        if juiz_config.llm_provider == "deepseek":
            descricao_juiz["preco_entrada_cache_hit_usd_milhao"] = (
                juiz_config.deepseek_preco_entrada_cache_hit_usd_milhao
            )
    gerador = config.gemini_modelo_llm if config.llm_provider == "gemini" else config.llm_provider

    humano: dict = {}
    if args.concordancia:
        casos, humano, fingerprint = _casos_da_auditoria(args.concordancia)
        estrategia, status = casos[0].estrategia if casos else "", "auditoria_humana"
    else:
        casos, fingerprint, estrategia, status = _casos_do_congelado(config, args.estrategia)
    pontuados = [c for c in casos if c.desfecho in de.DESFECHOS_PONTUADOS]
    if args.limite is not None:
        manter = {c.pergunta_id for c in pontuados[: args.limite]}
        casos = [c for c in casos if c.desfecho not in de.DESFECHOS_PONTUADOS or c.pergunta_id in manter]
        pontuados = [c for c in casos if c.pergunta_id in manter]

    contagem = {d: sum(1 for c in casos if c.desfecho == d) for d in
                (de.DESFECHO_PUBLICADA, de.DESFECHO_DESCARTADA_RN02, de.DESFECHO_RECUSA_MODELO)}
    caracteres_contexto = sum(len("".join(c.contexto)) for c in pontuados)
    print(f"Rodada {fingerprint[:8]} · estratégia {estrategia!r} · {len(casos)} casos {contagem}")
    print(f"Juiz: {descricao_juiz} · gerador: {gerador}")
    print(
        f"{len(pontuados)} pontuados × {CHAMADAS_POR_CASO} chamadas = "
        f"{len(pontuados) * CHAMADAS_POR_CASO} chamadas; {caracteres_contexto:,} caracteres de trecho"
    )
    if not args.permitir_api_paga:
        print("Ensaio: nenhuma chamada feita. Use --permitir-api-paga para executar.")
        return 0

    sufixo = "concordancia" if args.concordancia else estrategia
    saida = args.saida or DIR_RESULTADOS_AVALIACAO / f"deepeval_{fingerprint[:8]}_{sufixo}.json"
    if saida.exists() and not args.sobrescrever:
        # Antes de gastar: o relatório anterior é evidência de outra rodada.
        raise SystemExit(f"FALHOU: {saida} já existe; use --sobrescrever ou --saida.")

    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-deepeval"
    juiz = de.fabricar_juiz(config, teto_usd=args.teto_usd, run_id=run_id)
    registrar_execucao({"evento": "deepeval_inicio", "run_id": run_id, "fingerprint": fingerprint,
                        "estrategia": estrategia, "juiz": descricao_juiz, "n_pontuados": len(pontuados),
                        "teto_usd": args.teto_usd})
    resultados: list[de.ResultadoCaso] = []
    interrompido = None
    for indice, caso in enumerate(casos, start=1):
        try:
            resultado = de.medir_caso(caso, juiz)
        except de.OrcamentoJuizExcedidoError as erro:
            interrompido = str(erro)
            print(f"PAROU no teto: {erro}")
            break
        resultados.append(resultado)
        if caso.desfecho in de.DESFECHOS_PONTUADOS:
            notas = {m: round(v["score"], 3) if v["score"] is not None else None
                     for m, v in resultado.metricas.items()}
            print(f"  [{indice}/{len(casos)}] {caso.pergunta_id} {caso.desfecho}: {notas}"
                  f"{' ERRO ' + resultado.erro if resultado.erro else ''} · US$ {resultado.custo_usd:.5f}")

    relatorio = {
        "_meta": {
            "run_id": run_id,
            "data_utc": datetime.now(timezone.utc).isoformat(),
            "fingerprint": fingerprint,
            "status_da_rodada": status,
            "estrategia": estrategia,
            "juiz": descricao_juiz,
            "modelo_gerador": gerador,
            "juiz_igual_ao_gerador": descricao_juiz.get("modelo") == gerador,
            "deepeval": _versao_deepeval(),
            "temperatura": 0.0,
            "limiar_fundamentada": de.LIMIAR_FUNDAMENTADA,
            "teto_usd": args.teto_usd,
            "custo_total_usd": round(juiz.uso.custo_usd, 6),
            "chamadas_juiz": juiz.uso.chamadas,
            "tokens_entrada": juiz.uso.tokens_entrada,
            "tokens_saida": juiz.uso.tokens_saida,
            "falhas": juiz.uso.falhas,
            "falhas_transitorias": juiz.uso.falhas_transitorias,
            "debito_conservador_usd": round(juiz.uso.debito_conservador_usd, 6),
            "interrompido_no_teto": interrompido,
            "aviso": (
                "Instrumento, não gabarito: a groundedness reportada continua "
                "sendo a auditoria humana (spec 5.15). Recusa do modelo não é "
                "pontuada; rascunho descartado pela RN02 é."
            ),
        },
        "agregado": de.agregar(resultados),
        "casos": [r.como_dicionario() for r in resultados],
    }
    if args.concordancia:
        from scripts.medir_juiz_groundedness import _sistema_acertou

        pares, por_item = [], []
        for resultado in resultados:
            fidelidade = resultado.metricas.get(de.METRICA_FIDELIDADE)
            item = humano[resultado.caso.pergunta_id]
            if resultado.caso.desfecho == de.DESFECHO_RECUSA_MODELO:
                continue  # sem afirmação: o juiz do DeepEval não tem o que dizer
            if not fidelidade or fidelidade["score"] is None:
                continue
            fundamentada = fidelidade["score"] >= de.LIMIAR_FUNDAMENTADA
            juiz_acertou = _sistema_acertou(item, fundamentada)
            pares.append((juiz_acertou, bool(item["grounded"])))
            por_item.append({"pergunta_id": item["pergunta_id"], "desfecho": resultado.caso.desfecho,
                             "faithfulness": fidelidade["score"], "juiz_sistema_acertou": juiz_acertou,
                             "humano_grounded": item["grounded"], "concorda": juiz_acertou == item["grounded"]})
        relatorio["concordancia"] = {**de.concordancia_com_humano(pares), "itens": por_item,
                                     "fora_da_matriz": "recusas do próprio modelo (sem afirmação a julgar)"}
        print(f"concordância DeepEval × humano: {relatorio['concordancia']['taxa_concordancia']} "
              f"{relatorio['concordancia']['matriz']}")

    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    exibida = saida.resolve().relative_to(RAIZ) if saida.resolve().is_relative_to(RAIZ) else saida
    registrar_execucao({"evento": "deepeval_fim", "run_id": run_id, "custo_total_usd": juiz.uso.custo_usd,
                        "chamadas": juiz.uso.chamadas, "saida": str(exibida)})
    print(json.dumps(relatorio["agregado"], ensure_ascii=False))
    print(f"custo: US$ {juiz.uso.custo_usd:.6f} em {juiz.uso.chamadas} chamadas · {exibida}")
    return 1 if interrompido else 0


if __name__ == "__main__":
    raise SystemExit(principal())
