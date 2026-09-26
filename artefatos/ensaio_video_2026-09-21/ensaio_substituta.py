"""Reconfere a segunda pergunta factual de release do ensaio de 18/09.

Motivo: a narrativa ("por que a margem variou") foi REBAIXADA pela RN02 no
ensaio de 21/09 — o modelo respondeu, e a guarda derrubou por um número fora
dos trechos citados. Logo ela não serve como a resposta do vídeo, e o lugar
dela volta a ser uma factual de release. Esta foi medida contra gabarito em
18/09 (4,93%, pág. 12); temperatura 0 não garante repetição (§4.2 e o próprio
ensaio anterior), então reconferir antes de gravar é barato.

Teto travado pela cota do app (RN03): LIMITE=2.
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

SAIDA = "artefatos/ensaio_video_2026-09-21/respostas_substituta.json"

LIVRE_PAGAS = [
    "Segundo o release do Banco do Brasil, qual foi o índice de inadimplência "
    "acima de 90 dias no 3T2025?",
]

at = AppTest.from_file("app_streamlit.py", default_timeout=300)
at.run()
assert not at.exception, at.exception
registros = []

at.sidebar.radio[0].set_value("Pergunta livre").run()
for p in LIVRE_PAGAS:
    t0 = time.time()
    at.chat_input[0].set_value(p).run()
    hist = at.session_state["historico"]
    msg = dict(hist[-1])
    registros.append(
        {
            "pergunta": p,
            "segundos": round(time.time() - t0, 2),
            "excecao": [str(e.value) for e in at.exception],
            "resposta": msg.get("conteudo"),
            "modo": msg.get("modo"),
            "provedor": msg.get("provedor"),
            "citacoes": msg.get("citacoes"),
            "custo_sessao_usd": at.session_state["custo_usd_acumulado"],
            "chamadas_sessao": at.session_state["perguntas_livres_usadas"],
        }
    )

with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump(registros, f, ensure_ascii=False, indent=2, default=str)
print(
    "ok",
    "chamadas",
    at.session_state["perguntas_livres_usadas"],
    "custo",
    at.session_state["custo_usd_acumulado"],
)
