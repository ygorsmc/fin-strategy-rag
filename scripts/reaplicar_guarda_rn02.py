"""Reaplica as guardas RN01/RN02 às respostas gravadas de uma rodada.

Mede o que uma mudança na guarda de evidência faz, sem gerar resposta de
novo: o checkpoint guarda a saída bruta do LLM (`resposta.bruto`) e os trechos
recuperados de cada pergunta, e `aplicar_guardas_pos_llm` é a mesma função que
`gerar_resposta` chama. Custo zero, sem LLM e sem índice.

Para cada resposta, compara o desfecho gravado com o reaplicado e recalcula a
exatidão automática (factual e comparativa) e a recusa correta (adversarial)
com as funções da própria avaliação. O que importa numa guarda afrouxada é a
coluna "publicada e errada": resposta que a guarda passou a soltar e que o
gabarito reprova.

Duas réguas externas entram quando existem para a rodada:
- a auditoria humana às cegas (`auditoria_groundedness_<fp>.json`);
- o faithfulness do DeepEval (`deepeval_<fp>_<estrategia>.json`).

Uso:
    python -m scripts.reaplicar_guarda_rn02 [--fingerprint c3a03ff7]
        [--estrategias semantica,keyword,hibrida,fatos] [--saida ARQUIVO]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.avaliacao import (  # noqa: E402
    avaliar_exatidao_comparativa,
    avaliar_exatidao_numerica,
    avaliar_recusa,
    carregar_conjunto_padrao,
)
from src.config import carregar_config  # noqa: E402
from src.geracao import (  # noqa: E402
    RespostaGerada,
    aplicar_guardas_pos_llm,
    parsear_resposta_llm,
)
from src.ingestao import Chunk  # noqa: E402

DIR_AVALIACAO = RAIZ / "artefatos" / "resultados_avaliacao"
CHECKPOINT = DIR_AVALIACAO / "checkpoint_teste.jsonl"
ESTRATEGIAS_RAG = ("keyword", "semantica", "hibrida", "fatos")

PUBLICADA = "publicada"
RN01 = "rn01"
RN02_NUMERO = "rn02_numero"
RN02_ESCOPO = "rn02_escopo"
RECUSA_MODELO = "recusa_modelo"
JSON_INVALIDO = "json_invalido"


def desfecho(resposta: RespostaGerada | dict) -> str:
    """O caminho que a resposta tomou, lido do motivo que o código grava."""
    if isinstance(resposta, dict):
        recusa = bool(resposta.get("recusa"))
        motivo = str(resposta.get("motivo_recusa") or "")
        invalido = bool(resposta.get("json_invalido"))
    else:
        recusa, motivo = resposta.recusa, resposta.motivo_recusa or ""
        invalido = resposta.json_invalido
    if not recusa:
        return PUBLICADA
    if invalido:
        return JSON_INVALIDO
    if motivo.startswith("Rebaixada por RN01"):
        return RN01
    if motivo.startswith("Rebaixada por RN02: ao menos um valor"):
        return RN02_NUMERO
    if motivo.startswith("Rebaixada por RN02"):
        return RN02_ESCOPO
    return RECUSA_MODELO


def _registros(fingerprint: str, estrategias: tuple[str, ...]) -> dict:
    """Última linha sem erro por (estratégia, pergunta), como o consolidado."""
    escolhidos: dict[tuple[str, str], dict] = {}
    with open(CHECKPOINT, encoding="utf-8") as origem:
        for linha in origem:
            registro = json.loads(linha)
            if not str(registro.get("fingerprint", "")).startswith(fingerprint):
                continue
            if registro.get("estrategia") not in estrategias or registro.get("erro"):
                continue
            chave = (registro["estrategia"], registro["pergunta_id"])
            escolhidos[chave] = registro
    return escolhidos


def _auditoria_humana(fingerprint: str) -> dict[str, bool]:
    """pergunta_id → o sistema fez a coisa certa, segundo o humano."""
    for caminho in sorted(DIR_AVALIACAO.glob("auditoria_groundedness_*.json")):
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        meta = dados.get("_meta") or {}
        if not str(meta.get("fingerprint", "")).startswith(fingerprint):
            continue
        if meta.get("status") != "preenchida":
            continue
        return {
            item["pergunta_id"]: bool(item["grounded"])
            for item in dados.get("avaliacoes") or ()
        }
    return {}


def _faithfulness(fingerprint: str, estrategia: str) -> dict[str, float]:
    caminho = DIR_AVALIACAO / f"deepeval_{fingerprint[:8]}_{estrategia}.json"
    if not caminho.exists():
        return {}
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    saida = {}
    for caso in dados.get("casos") or ():
        escore = ((caso.get("metricas") or {}).get("faithfulness") or {}).get("score")
        if escore is not None:
            saida[caso["pergunta_id"]] = float(escore)
    return saida


def _automatico(pergunta, resposta: RespostaGerada, config) -> bool | None:
    if pergunta.categoria == "factual":
        return avaliar_exatidao_numerica(pergunta, resposta, config)
    if pergunta.categoria == "comparativa":
        return avaliar_exatidao_comparativa(pergunta, resposta, config)
    if pergunta.categoria == "adversarial":
        return avaliar_recusa(pergunta, resposta)
    return None


def reaplicar(fingerprint: str, estrategias: tuple[str, ...]) -> dict:
    config = carregar_config()
    perguntas = {
        pergunta.id: pergunta
        for pergunta in carregar_conjunto_padrao(config)
        if pergunta.conjunto == "teste"
    }
    humano = _auditoria_humana(fingerprint)
    itens = []
    for (estrategia, pergunta_id), registro in sorted(
        _registros(fingerprint, estrategias).items()
    ):
        pergunta = perguntas[pergunta_id]
        gravada = registro.get("resposta") or {}
        chunks = [Chunk(**item["chunk"]) for item in registro.get("recuperados") or ()]
        reaplicada = aplicar_guardas_pos_llm(
            parsear_resposta_llm(str(gravada.get("bruto") or "")),
            pergunta.pergunta,
            chunks,
            config,
        )
        automatico_gravado = (
            registro.get("recusa_correta")
            if pergunta.categoria == "adversarial"
            else registro.get("exatidao_ok")
        )
        itens.append(
            {
                "pergunta_id": pergunta_id,
                "estrategia": estrategia,
                "categoria": pergunta.categoria,
                "desfecho_gravado": desfecho(gravada),
                "desfecho_reaplicado": desfecho(reaplicada),
                "automatico_gravado": automatico_gravado,
                "automatico_reaplicado": _automatico(pergunta, reaplicada, config),
                "humano_sistema_acertou": humano.get(pergunta_id)
                if estrategia == "semantica"
                else None,
                "resposta_reaplicada": reaplicada.resposta,
            }
        )
    faithfulness = {
        estrategia: _faithfulness(fingerprint, estrategia) for estrategia in estrategias
    }
    for item in itens:
        item["faithfulness_deepeval"] = faithfulness[item["estrategia"]].get(
            item["pergunta_id"]
        )
    return {"itens": itens, "resumo": resumir(itens)}


def resumir(itens: list[dict]) -> dict:
    """Transições de desfecho e o que a guarda passou a soltar ou a reter."""
    por_estrategia: dict[str, dict] = {}
    for estrategia in sorted({item["estrategia"] for item in itens}):
        grupo = [item for item in itens if item["estrategia"] == estrategia]
        soltas = [
            item
            for item in grupo
            if item["desfecho_gravado"] != PUBLICADA
            and item["desfecho_reaplicado"] == PUBLICADA
        ]
        retidas = [
            item
            for item in grupo
            if item["desfecho_gravado"] == PUBLICADA
            and item["desfecho_reaplicado"] != PUBLICADA
        ]
        por_estrategia[estrategia] = {
            "n": len(grupo),
            "desfecho_gravado": dict(Counter(i["desfecho_gravado"] for i in grupo)),
            "desfecho_reaplicado": dict(
                Counter(i["desfecho_reaplicado"] for i in grupo)
            ),
            "passaram_a_publicar": sorted(i["pergunta_id"] for i in soltas),
            "passaram_a_publicar_e_gabarito_reprova": sorted(
                i["pergunta_id"] for i in soltas if i["automatico_reaplicado"] is False
            ),
            "passaram_a_publicar_sem_gabarito_automatico": sorted(
                i["pergunta_id"] for i in soltas if i["automatico_reaplicado"] is None
            ),
            "deixaram_de_publicar": sorted(i["pergunta_id"] for i in retidas),
            "acerto_automatico_gravado": sum(
                1 for i in grupo if i["automatico_gravado"] is True
            ),
            "acerto_automatico_reaplicado": sum(
                1 for i in grupo if i["automatico_reaplicado"] is True
            ),
        }
    return por_estrategia


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fingerprint", default="c3a03ff7")
    parser.add_argument("--estrategias", default=",".join(ESTRATEGIAS_RAG))
    parser.add_argument("--saida", type=Path)
    args = parser.parse_args()
    estrategias = tuple(e for e in args.estrategias.split(",") if e)
    desconhecidas = set(estrategias) - set(ESTRATEGIAS_RAG)
    if desconhecidas:
        parser.error(f"estratégia sem guarda RN02: {sorted(desconhecidas)}")

    resultado = reaplicar(args.fingerprint, estrategias)
    resultado["_meta"] = {
        "fingerprint": args.fingerprint,
        "estrategias": list(estrategias),
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "custo_usd": 0.0,
    }
    for estrategia, resumo in resultado["resumo"].items():
        print(f"\n[{estrategia}] n={resumo['n']}")
        print(f"  gravado:    {resumo['desfecho_gravado']}")
        print(f"  reaplicado: {resumo['desfecho_reaplicado']}")
        print(f"  passaram a publicar: {resumo['passaram_a_publicar']}")
        print(
            "    e o gabarito reprova: "
            f"{resumo['passaram_a_publicar_e_gabarito_reprova']}"
        )
        print(f"  deixaram de publicar: {resumo['deixaram_de_publicar']}")
        print(
            "  acerto automático: "
            f"{resumo['acerto_automatico_gravado']} → "
            f"{resumo['acerto_automatico_reaplicado']}"
        )
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        exibido = (
            args.saida.resolve().relative_to(RAIZ)
            if args.saida.resolve().is_relative_to(RAIZ)
            else args.saida
        )
        print(f"\nGravado em {exibido}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
