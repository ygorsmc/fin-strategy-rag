"""Ensaio do roteiro do vídeo pelo caminho REAL da interface (AppTest).

Teto de chamadas pagas travado pela própria cota do app (RN03): LIMITE=2.
"""
import json
import os
import sys
import time

RAIZ = "/home/ygor/Antigravity_Projects/fin-strategy-rag"
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)
os.environ["HABILITAR_PERGUNTAS_LIVRES"] = "true"
os.environ["LIMITE_PERGUNTAS_LIVRES_POR_SESSAO"] = "2"
os.environ["MODO_DEMONSTRACAO_CACHEADO"] = "true"

from streamlit.testing.v1 import AppTest  # noqa: E402

SAIDA = sys.argv[1] if len(sys.argv) > 1 else "artefatos/ensaio_video_2026-09-18/respostas.json"

PAINEL = [
    "Qual foi o lucro líquido do Banco do Brasil no 4T2025?",
    "Qual foi o patrimônio líquido do Itaú no 3T2025?",
    "Qual foi o lucro do Banco Inter no 3T2025?",
    "Qual foi o lucro do Nubank no 3T2025?",
]
LIVRE_GRATIS = ["Devo comprar ações do Itaú agora?"]
LIVRE_PAGAS = [
    "Segundo a análise gerencial do Itaú Unibanco qual foi o resultado "
    "recorrente gerencial no 2T2025?",
    "Segundo o release do Banco do Brasil qual foi o índice de inadimplência "
    "acima de 90 dias no 3T2025?",
]

at = AppTest.from_file("app_streamlit.py", default_timeout=300)
at.run()
assert not at.exception, at.exception
registros = []


def ultima(etapa, pergunta, t0):
    hist = at.session_state["historico"]
    msg = dict(hist[-1])
    registros.append(
        {
            "etapa": etapa,
            "pergunta": pergunta,
            "segundos": round(time.time() - t0, 2),
            "excecao": [str(e.value) for e in at.exception],
            "erros_tela": [e.value for e in at.error],
            "resposta": msg.get("conteudo"),
            "modo": msg.get("modo"),
            "provedor": msg.get("provedor"),
            "fontes": msg.get("fontes"),
            "fatos": msg.get("fatos"),
            "citacoes": msg.get("citacoes"),
            "custo_sessao_usd": at.session_state["custo_usd_acumulado"],
            "chamadas_sessao": at.session_state["perguntas_livres_usadas"],
        }
    )


for p in PAINEL:
    t0 = time.time()
    at.chat_input(key="entrada_painel").set_value(p).run()
    ultima("painel (modo demonstração, sem LLM)", p, t0)

at.sidebar.radio[0].set_value("Pergunta livre").run()
for etapa, lista in (("livre · guardrail", LIVRE_GRATIS), ("livre · RAG pago", LIVRE_PAGAS)):
    for p in lista:
        t0 = time.time()
        at.chat_input[0].set_value(p).run()
        ultima(etapa, p, t0)

with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump(registros, f, ensure_ascii=False, indent=2, default=str)
print("ok", len(registros), "chamadas", at.session_state["perguntas_livres_usadas"],
      "custo", at.session_state["custo_usd_acumulado"])
