"""Mede a RN02 com rótulo dos agentes sobre as respostas reais já gravadas.

A guarda nova (`valores_com_rotulo_trocado`, 2026-10-19) acusa valor que só
existe na evidência sob outra métrica. Antes de ela valer no chat, a pergunta
é quanto ela acusa resposta que a RN02 antiga aprovava: cada acusação vira
recusa registrada para o usuário.

Custo zero e sem LLM: lê `artefatos/resultados_agentes/`, reexecuta as
chamadas de ferramenta do Investigador (ou do agente único) na caixa local —
painel DuckDB, índice Chroma, embeddings Ollama — e aplica as duas RN02 à
resposta gravada. O que a reexecução não reproduz (o índice mudou depois de
agosto, §3.4) sai como **deriva de evidência** e fica fora da conta, porque ali
a RN02 antiga também reprovaria.

Uso:
    python scripts/medir_guarda_rotulo_agentes.py [--saida ARQUIVO]
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.agentes import (  # noqa: E402
    PAPEL_AGENTE_UNICO,
    PAPEL_INVESTIGADOR,
    VIOLACAO_RN02_SEM_LASTRO,
    ChamadaFerramenta,
    FerramentasDoAgente,
    SaidaInvestigador,
    _tem_lastro,
    fabrica_ferramentas_padrao,
    valores_com_rotulo_trocado,
    valores_monetarios_do_texto,
)
from src.config import carregar_config  # noqa: E402

DIR_RESULTADOS = RAIZ / "artefatos" / "resultados_agentes"
PAPEIS = {PAPEL_INVESTIGADOR, PAPEL_AGENTE_UNICO}


def _registros():
    for arquivo in sorted(glob.glob(str(DIR_RESULTADOS / "**" / "*.json"), recursive=True)):
        try:
            dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for registro in (dados.get("registros") if isinstance(dados, dict) else None) or ():
            yield Path(arquivo).relative_to(RAIZ).as_posix(), registro


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", type=Path, default=None)
    args = parser.parse_args()

    config = carregar_config()
    caixa = fabrica_ferramentas_padrao(config)(PAPEL_INVESTIGADOR).caixa
    cache: dict[str, tuple[object, str | None]] = {}

    def reexecutar(ferramenta: str, argumentos: dict):
        chave = json.dumps([ferramenta, argumentos], sort_keys=True, ensure_ascii=False)
        if chave not in cache:
            # Uma caixa só para a medição inteira: o teto de chamadas é do
            # agente, não da reexecução, e o registro é zerado a cada uma.
            caixa._registro.clear()
            try:
                cache[chave] = (getattr(caixa, ferramenta)(**argumentos), None)
            except Exception as erro:  # a falha original também é evidência nula
                cache[chave] = (None, type(erro).__name__)
        return cache[chave]

    vistos: set[tuple[str, str]] = set()
    contagem: Counter[str] = Counter()
    acusadas: list[dict] = []
    for arquivo, registro in _registros():
        resposta = registro.get("resposta") or ""
        if registro.get("violacoes") or registro.get("recusa"):
            continue
        valores = valores_monetarios_do_texto(resposta)
        if not valores:
            continue
        chave = (registro.get("pergunta", ""), resposta)
        if chave in vistos:
            contagem["duplicada"] += 1
            continue
        vistos.add(chave)
        ferramentas = FerramentasDoAgente.__new__(FerramentasDoAgente)
        ferramentas.chamadas = []
        for chamada in registro.get("chamadas_ferramenta") or ():
            if chamada.get("papel") not in PAPEIS or chamada.get("erro"):
                continue
            resultado, erro = reexecutar(chamada["ferramenta"], dict(chamada.get("argumentos") or {}))
            ferramentas.chamadas.append(
                ChamadaFerramenta(
                    papel=chamada["papel"],
                    ferramenta=chamada["ferramenta"],
                    argumentos=dict(chamada.get("argumentos") or {}),
                    erro=erro,
                    resultado=resultado,
                )
            )
        evidencias = ferramentas.valores_de_evidencia()
        if any(not _tem_lastro(v, evidencias) for v in valores):
            contagem["deriva_de_evidencia"] += 1
            continue
        contagem["avaliadas"] += 1
        saida = SaidaInvestigador(
            pergunta=registro.get("pergunta", ""),
            afirmacao=resposta,
            citacoes=tuple(registro.get("citacoes") or ()),
            comportamento=registro.get("comportamento_observado", ""),
        )
        oracoes = valores_com_rotulo_trocado(saida, ferramentas)
        apuracao = registro.get("apuracao") or "sem_apuracao"
        contagem[f"avaliadas_{apuracao}"] += 1
        if oracoes:
            contagem["acusadas"] += 1
            contagem[f"acusadas_{apuracao}"] += 1
            acusadas.append(
                {
                    "arquivo": arquivo,
                    "id_pergunta": registro.get("id_pergunta"),
                    "apuracao": apuracao,
                    "pergunta": registro.get("pergunta"),
                    "oracoes_acusadas": list(oracoes),
                }
            )

    relatorio = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ"),
        "regra": "valores_com_rotulo_trocado (RN02 com rótulo, agentes)",
        "custo_usd": 0.0,
        "contagem": dict(sorted(contagem.items())),
        "acusadas": acusadas,
        "nota": (
            "Respostas sem violação na RN02 antiga e com valor em dinheiro, "
            "deduplicadas por (pergunta, resposta). 'deriva_de_evidencia' = a "
            "reexecução local não devolveu o número que a resposta usou; fica "
            "fora da conta. Cada acusação precisa de leitura humana: acusar é "
            "virar recusa registrada."
        ),
    }
    texto = json.dumps(relatorio, ensure_ascii=False, indent=2)
    if args.saida:
        args.saida.write_text(texto + "\n", encoding="utf-8")
    print(json.dumps(relatorio["contagem"], ensure_ascii=False))
    for item in acusadas:
        print(f"- {item['id_pergunta']} [{item['apuracao']}] {item['arquivo']}")
        for oracao in item["oracoes_acusadas"]:
            print(f"    {oracao[:220]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
