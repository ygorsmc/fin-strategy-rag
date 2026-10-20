"""Gera traces reais no Langfuse pelo chat do app (spec 5.12, Etapa 2 da disciplina).

Dirige o próprio `app_streamlit.py` com o `AppTest` do Streamlit: cada
pergunta entra pelo campo do chat e percorre o mesmo código de um usuário. Os
traces são do produto, não de uma cópia dele.

    # Só as rotas de custo zero (guardrail, RN07, painel): confere a conexão
    python -m scripts.gerar_traces_langfuse

    # Inclui as perguntas que chegam ao corpus e chamam o Gemini (centavos)
    python -m scripts.gerar_traces_langfuse --permitir-api-paga

    # Com o texto de pergunta e resposta no trace, anonimizado pelo Presidio
    python -m scripts.gerar_traces_langfuse --permitir-api-paga --capturar-texto

Sem `--permitir-api-paga`, as chaves de todos os provedores pagos são
esvaziadas para esta execução: uma pergunta que escape das rotas gratuitas
falha fechada, sem gastar, qualquer que seja o `LLM_PROVIDER`.

Sem `--capturar-texto`, o trace leva estrutura, latência, tokens e custo, e
no lugar de cada texto só o tamanho (`observabilidade.texto_livre`). A flag
liga o Presidio nesta execução, que é a condição para o texto sair (RN06).

O resumo vai para `artefatos/observabilidade/`, versionado. O Langfuse retém
30 dias, e o resumo é o registro que sobrevive a isso (RNF08). O journal é
escrito antes de cada pergunta e depois dela.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

SAIDA = RAIZ / "artefatos" / "observabilidade"

# Chaves esvaziadas sem `--permitir-api-paga`. O Ollama é local e fica.
CHAVES_PAGAS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "MISTRAL_API_KEY",
)

# (rótulo, pergunta, chama o provedor?). As de custo zero exercitam o
# guardrail, a anonimização (RN06), a recusa prospectiva (RN07) e o painel.
# As pagas são perguntas `dev`, nunca as 45 congeladas: aqui não se mede nada.
PERGUNTAS: tuple[tuple[str, str, bool], ...] = (
    ("guardrail_rn05", "Devo comprar ações do Itaú agora?", False),
    ("prospectiva_rn07", "O lucro do Itaú vai cair no próximo trimestre?", False),
    ("painel_cvm", "Qual foi o lucro líquido do Banco do Brasil no 4T2025?", False),
    (
        "anonimizacao_rn06",
        "Meu CPF é 123.456.789-09. Qual foi o lucro líquido do Itaú no 3T2025?",
        False,
    ),
    ("DEV003", "Segundo a análise gerencial do Itaú Unibanco qual foi a Margem Financeira Gerencial total no 3T2025?", True),
    ("DEV005", "Segundo a demonstração do resultado recorrente do Bradesco qual foi a margem financeira total no 1T2026?", True),
    ("DEV004", "Segundo a análise gerencial do Itaú Unibanco por que o NPL total de 15 a 90 dias aumentou no 1T2026 ante o 4T2025?", True),
    ("DEV008", "Segundo o Santander quais fatores explicaram a queda trimestral e o crescimento anual da carteira de crédito ampliada no 1T2026?", True),
    ("DEV009", "No 1T2026 qual banco teve o maior indicador anualizado de rentabilidade gerencial sobre o patrimônio como divulgado em cada release?", True),
)


def _journal(caminho: Path, evento: dict) -> None:
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"em": datetime.now(timezone.utc).isoformat(), **evento}, ensure_ascii=False) + "\n")


def _conferir_no_servidor(cliente, ids: list[str], prazo_s: float) -> dict[str, dict]:
    """Espera cada trace aparecer na API e resume suas observações.

    A ingestão do Langfuse é assíncrona: `flush` garante a entrega, não a
    leitura. Por isso há prazo e nova tentativa, em vez de uma espera fixa.
    """
    conferidos: dict[str, dict] = {}
    limite = time.monotonic() + prazo_s
    pendentes = list(ids)
    while pendentes and time.monotonic() < limite:
        for id_trace in list(pendentes):
            try:
                resposta = cliente.api.observations.get_many(trace_id=id_trace)
            except Exception as exc:
                conferidos[id_trace] = {"erro": type(exc).__name__}
                continue
            dados = [
                # Sem prompt nem resposta: o versionado guarda identidade,
                # tempo, tokens e custo. O conteúdo fica no Langfuse.
                {k: v for k, v in (o.dict() if hasattr(o, "dict") else dict(o)).items() if k not in ("input", "output")}
                for o in getattr(resposta, "data", [])
            ]
            if not dados:
                continue
            conferidos[id_trace] = {
                "observacoes": len(dados),
                "tipos": sorted({str(o.get("type")) for o in dados}),
                "amostra_campos": sorted(dados[0])[:40],
                "observacoes_brutas": dados,
            }
            pendentes.remove(id_trace)
        if pendentes:
            time.sleep(5)
    for id_trace in pendentes:
        conferidos.setdefault(id_trace, {"erro": "não apareceu na API dentro do prazo"})
    return conferidos


def principal(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--permitir-api-paga", action="store_true")
    ap.add_argument("--capturar-texto", action="store_true")
    ap.add_argument("--prazo-conferencia-s", type=float, default=120.0)
    args = ap.parse_args(argv)

    # Antes de o app carregar o `.env`: `load_dotenv` não sobrescreve o que
    # já está no ambiente.
    os.environ["LIMITE_PERGUNTAS_LIVRES_POR_SESSAO"] = str(4 * len(PERGUNTAS))
    os.environ["HABILITAR_PERGUNTAS_LIVRES"] = "true"
    if not args.permitir_api_paga:
        for chave in CHAVES_PAGAS:
            os.environ[chave] = ""
    if args.capturar_texto:
        os.environ["PRESIDIO_HABILITADO"] = "true"

    from streamlit.testing.v1 import AppTest

    from src import observabilidade

    perguntas = [p for p in PERGUNTAS if args.permitir_api_paga or not p[2]]
    app = AppTest.from_file(str(RAIZ / "app_streamlit.py"), default_timeout=300).run()
    estado = observabilidade.estado()
    if not estado.ativo:
        print(f"Langfuse desligado: {estado.motivo}. Nada a gerar.")
        return 1
    if args.capturar_texto and not estado.captura_texto:
        print("--capturar-texto pedido, mas o Presidio não ficou ligado. Nada a gerar.")
        return 1
    print(f"Langfuse ativo em {estado.host}. {len(perguntas)} perguntas; texto no trace: {estado.captura_texto}.")
    app.sidebar.radio[0].set_value("Pergunta livre").run()

    SAIDA.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    journal = SAIDA / f"journal_{carimbo}.jsonl"
    linhas = []
    for rotulo, pergunta, paga in perguntas:
        _journal(journal, {"evento": "inicio", "rotulo": rotulo, "paga": paga})
        antes = len(observabilidade.traces_recentes())
        custo_antes = app.session_state["custo_usd_acumulado"]
        inicio = time.perf_counter()
        app.chat_input[0].set_value(pergunta).run()
        duracao = time.perf_counter() - inicio
        novos = observabilidade.traces_recentes()[antes:]
        historico = app.session_state["historico"]
        resposta = next((m for m in reversed(historico) if m["papel"] == "assistant"), {})
        exibida = next((m for m in reversed(historico) if m["papel"] == "user"), {})
        linha = {
            "rotulo": rotulo,
            "pergunta_exibida": exibida.get("conteudo"),
            "modo": resposta.get("modo"),
            "provedor": resposta.get("provedor"),
            "custo_usd": round(app.session_state["custo_usd_acumulado"] - custo_antes, 6),
            "duracao_no_app_s": round(duracao, 2),
            "traces": [id_trace for _, id_trace in novos],
            "resposta_inicio": (resposta.get("conteudo") or "")[:300],
        }
        linhas.append(linha)
        _journal(journal, {"evento": "fim", "rotulo": rotulo, "custo_usd": linha["custo_usd"], "traces": linha["traces"]})
        print(f"- {rotulo}: {linha['modo']} · US$ {linha['custo_usd']:.6f} · {duracao:.1f} s · trace {linha['traces']}")

    observabilidade.descarregar()
    cliente = observabilidade._cliente
    ids = [t for linha in linhas for t in linha["traces"]]
    conferidos = _conferir_no_servidor(cliente, ids, args.prazo_conferencia_s)
    for linha in linhas:
        linha["no_servidor"] = {t: {k: v for k, v in conferidos.get(t, {}).items() if k != "observacoes_brutas"} for t in linha["traces"]}
        try:
            linha["urls"] = [cliente.get_trace_url(trace_id=t) for t in linha["traces"]]
        except Exception as exc:
            linha["urls"] = [f"indisponível ({type(exc).__name__})"]
    resumo = {
        "gerado_em": carimbo,
        "host": estado.host,
        "api_paga": args.permitir_api_paga,
        "captura_texto": estado.captura_texto,
        "sessao": app.session_state["id_sessao_rastro"],
        "custo_total_usd": round(sum(linha["custo_usd"] for linha in linhas), 6),
        "perguntas": linhas,
    }
    destino = SAIDA / f"traces_{carimbo}.json"
    destino.write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    brutas = SAIDA / f"observacoes_{carimbo}.json"
    brutas.write_text(
        json.dumps({t: c.get("observacoes_brutas") for t, c in conferidos.items()}, ensure_ascii=False, indent=1, default=str),
        encoding="utf-8",
    )
    chegaram = sum(1 for t in ids if "observacoes" in conferidos.get(t, {}))
    print(f"\n{chegaram}/{len(ids)} traces conferidos na API. Custo total US$ {resumo['custo_total_usd']:.6f}.")
    print(f"Resumo: {destino.relative_to(RAIZ)}")
    observabilidade.desligar()
    return 0 if chegaram == len(ids) else 2


if __name__ == "__main__":
    sys.exit(principal())
