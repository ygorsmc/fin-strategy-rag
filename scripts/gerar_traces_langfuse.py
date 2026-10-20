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

    # Só as perguntas do modo agentes (Investigador + Auditor, com o modelo)
    python -m scripts.gerar_traces_langfuse --permitir-api-paga --conjunto agentes

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

MODO_LIVRE = "Pergunta livre"
MODO_AGENTES = "Agentes (Investigador + Auditor)"

# As três perguntas de exemplo do modo agentes (`app_streamlit.EXEMPLOS_AGENTES`).
# Repetidas aqui porque importar o app fora do AppTest ligaria o Langfuse por
# fora dele. Cada uma exige mais de uma ferramenta, em ordem.
PERGUNTAS_AGENTES: tuple[tuple[str, str, bool], ...] = (
    (
        "agentes_painel_e_modelo",
        "Qual foi o lucro líquido do Banco Inter no 3T2025 e em que faixa de porte "
        "de ativo ele se encaixa no modelo preditivo de prejuízo?",
        True,
    ),
    (
        "agentes_release_e_painel",
        "O que o release do Itaú diz sobre a margem financeira gerencial no 3T2025, "
        "e quanto o painel da CVM registra de lucro líquido no mesmo trimestre?",
        True,
    ),
    (
        "agentes_modelo",
        "Quantas companhias o modelo preditivo sinaliza no trimestre corrente, e com "
        "que AUC ele foi validado?",
        True,
    ),
)


def _journal(caminho: Path, evento: dict) -> None:
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"em": datetime.now(timezone.utc).isoformat(), **evento}, ensure_ascii=False) + "\n")


CAMPOS_API = "core,basic,usage,model,metrics"


def _resumir(dados: list[dict], custo_local_usd: float) -> dict:
    """O que o servidor registrou de um trace, e se fecha com o app."""
    raiz = [o for o in dados if o.get("isRootObservation")]
    geracoes = [o for o in dados if o.get("type") == "GENERATION"]
    custo_servidor = sum(float((g.get("costDetails") or {}).get("total", 0.0)) for g in geracoes)
    resumo = {
        "observacoes": len(dados),
        "tipos": sorted({str(o.get("type")) for o in dados}),
        "latencia_raiz_s": raiz[0].get("latency") if raiz else None,
        "geracoes": [
            {
                "modelo": g.get("model"),
                "tokens": g.get("usageDetails"),
                "custo_usd": (g.get("costDetails") or {}).get("total"),
                "latencia_s": g.get("latency"),
            }
            for g in geracoes
        ],
        "custo_servidor_usd": round(custo_servidor, 7),
        # O custo do app vem arredondado a 6 casas no resumo.
        "custo_confere_com_o_app": abs(custo_servidor - custo_local_usd) <= 1e-6,
    }
    faltas = []
    if not raiz or raiz[0].get("endTime") is None:
        faltas.append("sem raiz fechada")
    if custo_local_usd > 0 and not geracoes:
        faltas.append("chamada paga sem geração")
    if custo_local_usd > 0 and any((g.get("costDetails") or {}).get("total") is None for g in geracoes):
        faltas.append("geração sem custo")
    if not resumo["custo_confere_com_o_app"]:
        faltas.append("custo do servidor difere do app")
    resumo["completo"] = not faltas
    resumo["faltas"] = faltas
    return resumo


def _conferir_no_servidor(cliente, esperados: dict[str, float], prazo_s: float) -> dict[str, dict]:
    """Espera cada trace chegar inteiro na API e confere contra o app.

    A ingestão do Langfuse é assíncrona: `flush` garante a entrega, não a
    leitura, e as observações de um trace aparecem aos poucos. A primeira
    versão deste script aceitava o trace ao ver a primeira observação, e
    registrou como conferidos dois traces que ainda não tinham a raiz nem a
    geração. Agora um trace só conta quando tem a raiz fechada, a geração com
    custo se a pergunta foi paga, o custo igual ao do app, e a mesma contagem
    de observações em duas leituras seguidas.
    """
    conferidos: dict[str, dict] = {}
    contagem_anterior: dict[str, int] = {}
    limite = time.monotonic() + prazo_s
    pendentes = list(esperados)
    while pendentes and time.monotonic() < limite:
        for id_trace in list(pendentes):
            try:
                resposta = cliente.api.observations.get_many(trace_id=id_trace, fields=CAMPOS_API)
            except Exception as exc:
                conferidos[id_trace] = {"completo": False, "faltas": [f"erro na API ({type(exc).__name__})"]}
                continue
            dados = [o.dict() if hasattr(o, "dict") else dict(o) for o in getattr(resposta, "data", [])]
            resumo = _resumir(dados, esperados[id_trace])
            resumo["observacoes_brutas"] = dados
            conferidos[id_trace] = resumo
            estavel = contagem_anterior.get(id_trace) == len(dados)
            contagem_anterior[id_trace] = len(dados)
            if resumo["completo"] and estavel:
                pendentes.remove(id_trace)
        if pendentes:
            time.sleep(5)
    for id_trace in pendentes:
        conferidos.setdefault(id_trace, {"completo": False, "faltas": []})
        conferidos[id_trace]["faltas"] = conferidos[id_trace].get("faltas", []) + ["prazo esgotado"]
        conferidos[id_trace]["completo"] = False
    return conferidos


def _gravar(resumo: dict, conferidos: dict[str, dict], cliente, carimbo: str) -> int:
    for linha in resumo["perguntas"]:
        linha["no_servidor"] = {
            t: {k: v for k, v in conferidos.get(t, {}).items() if k != "observacoes_brutas"}
            for t in linha["traces"]
        }
        if not linha.get("urls") or any(str(u).startswith("indisponível") for u in linha["urls"]):
            try:
                linha["urls"] = [cliente.get_trace_url(trace_id=t) for t in linha["traces"]]
            except Exception as exc:
                linha["urls"] = [f"indisponível ({type(exc).__name__})"]
    ids = [t for linha in resumo["perguntas"] for t in linha["traces"]]
    resumo["traces_completos"] = sum(1 for t in ids if conferidos.get(t, {}).get("completo"))
    resumo["traces_total"] = len(ids)
    destino = SAIDA / f"traces_{carimbo}.json"
    destino.write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    brutas = SAIDA / f"observacoes_{carimbo}.json"
    brutas.write_text(
        # Só identidade, tempo, modelo, tokens e custo: sem `io` na consulta,
        # prompt e resposta ficam no Langfuse e fora do versionado.
        json.dumps({t: c.get("observacoes_brutas") for t, c in conferidos.items()}, ensure_ascii=False, indent=1, default=str),
        encoding="utf-8",
    )
    print(f"\n{resumo['traces_completos']}/{len(ids)} traces completos na API. Custo total US$ {resumo['custo_total_usd']:.6f}.")
    for linha in resumo["perguntas"]:
        for t in linha["traces"]:
            c = conferidos.get(t, {})
            print(f"- {linha['rotulo']}: {'completo' if c.get('completo') else 'INCOMPLETO ' + str(c.get('faltas'))}"
                  f" · {c.get('observacoes')} observações · raiz {c.get('latencia_raiz_s')} s")
    print(f"Resumo: {destino.relative_to(RAIZ)}")
    return 0 if resumo["traces_completos"] == len(ids) else 2


def _reconferir(caminho: Path, prazo_s: float) -> int:
    """Confere de novo, no servidor, os traces de um resumo já gravado. Sem custo."""
    from src import observabilidade
    from src.config import carregar_config

    resumo = json.loads(caminho.read_text(encoding="utf-8"))
    estado = observabilidade.configurar(carregar_config())
    if not estado.ativo:
        print(f"Langfuse desligado: {estado.motivo}.")
        return 1
    esperados = {t: float(linha["custo_usd"]) for linha in resumo["perguntas"] for t in linha["traces"]}
    conferidos = _conferir_no_servidor(observabilidade._cliente, esperados, prazo_s)
    resumo["reconferido_em"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    codigo = _gravar(resumo, conferidos, observabilidade._cliente, resumo["gerado_em"])
    observabilidade.desligar()
    return codigo


def principal(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--permitir-api-paga", action="store_true")
    ap.add_argument("--capturar-texto", action="store_true")
    ap.add_argument("--conjunto", choices=("chat", "agentes", "todos"), default="chat")
    ap.add_argument("--prazo-conferencia-s", type=float, default=180.0)
    ap.add_argument("--reconferir", type=Path, help="resumo já gravado: só confere no servidor, sem perguntar de novo")
    args = ap.parse_args(argv)
    if args.reconferir:
        return _reconferir(args.reconferir, args.prazo_conferencia_s)

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

    selecionadas = []
    if args.conjunto in ("chat", "todos"):
        selecionadas += [(*p, MODO_LIVRE) for p in PERGUNTAS]
    if args.conjunto in ("agentes", "todos"):
        selecionadas += [(*p, MODO_AGENTES) for p in PERGUNTAS_AGENTES]
    perguntas = [p for p in selecionadas if args.permitir_api_paga or not p[2]]
    if not perguntas:
        print("Nenhuma pergunta sem custo neste conjunto; use --permitir-api-paga.")
        return 1
    app = AppTest.from_file(str(RAIZ / "app_streamlit.py"), default_timeout=300).run()
    estado = observabilidade.estado()
    if not estado.ativo:
        print(f"Langfuse desligado: {estado.motivo}. Nada a gerar.")
        return 1
    if args.capturar_texto and not estado.captura_texto:
        print("--capturar-texto pedido, mas o Presidio não ficou ligado. Nada a gerar.")
        return 1
    print(f"Langfuse ativo em {estado.host}. {len(perguntas)} perguntas; texto no trace: {estado.captura_texto}.")
    modo_atual = None

    SAIDA.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    journal = SAIDA / f"journal_{carimbo}.jsonl"
    linhas = []
    for rotulo, pergunta, paga, modo in perguntas:
        if modo != modo_atual:
            app.sidebar.radio[0].set_value(modo).run()
            modo_atual = modo
        _journal(journal, {"evento": "inicio", "rotulo": rotulo, "paga": paga, "modo": modo})
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
            "rastro_agentes": resposta.get("rastro_agentes"),
        }
        linhas.append(linha)
        _journal(journal, {"evento": "fim", "rotulo": rotulo, "custo_usd": linha["custo_usd"], "traces": linha["traces"]})
        print(f"- {rotulo}: {linha['modo']} · US$ {linha['custo_usd']:.6f} · {duracao:.1f} s · trace {linha['traces']}")

    observabilidade.descarregar()
    esperados = {t: linha["custo_usd"] for linha in linhas for t in linha["traces"]}
    conferidos = _conferir_no_servidor(observabilidade._cliente, esperados, args.prazo_conferencia_s)
    resumo = {
        "gerado_em": carimbo,
        "host": estado.host,
        "api_paga": args.permitir_api_paga,
        "captura_texto": estado.captura_texto,
        "sessao": app.session_state["id_sessao_rastro"],
        "custo_total_usd": round(sum(linha["custo_usd"] for linha in linhas), 6),
        "perguntas": linhas,
    }
    codigo = _gravar(resumo, conferidos, observabilidade._cliente, carimbo)
    observabilidade.desligar()
    return codigo


if __name__ == "__main__":
    sys.exit(principal())
