"""Ensaio das perguntas 4 e 5 do vídeo pelo caminho REAL da interface (AppTest).

Mesmo método do ensaio de 2026-09-18: `streamlit.testing.v1.AppTest` sobre
`app_streamlit.py`, não o arnês de avaliação. Evidência de que a pergunta se
comporta na tela como o roteiro promete — NÃO é métrica de exatidão (§4.2).

Teto de chamadas pagas travado pela própria cota do app (RN03): LIMITE=4.
As duas perguntas trazem marca da camada documental ("release", "por que"), então
esperam-se 2 chamadas; o teto de 4 é folga caso alguma caia na rota de plano
antes do corpus.
"""
import json
import os
import sys
import time

RAIZ = "/home/ygor/Antigravity_Projects/fin-strategy-rag"
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)
os.environ["HABILITAR_PERGUNTAS_LIVRES"] = "true"
os.environ["LIMITE_PERGUNTAS_LIVRES_POR_SESSAO"] = "4"
os.environ["MODO_DEMONSTRACAO_CACHEADO"] = "true"

from streamlit.testing.v1 import AppTest  # noqa: E402

SAIDA = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "artefatos/ensaio_video_2026-09-21/respostas.json"
)

# P4: narrativa de release — o painel não responde isso por SQL de jeito nenhum.
# P5: período FORA da janela do corpus (2025–2026). A recuperação traz trecho do
#     período errado e o prompt obriga a recusar em vez de responder com o que
#     estiver por perto. É a recusa que o vídeo quer mostrar.
LIVRE_PAGAS = [
    "Segundo o release do Bradesco, por que a margem financeira variou no 3T2025?",
    "Segundo o release do Santander, qual foi o resultado gerencial no 2T2019?",
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


at.sidebar.radio[0].set_value("Pergunta livre").run()
for p in LIVRE_PAGAS:
    t0 = time.time()
    at.chat_input[0].set_value(p).run()
    ultima("livre · porta 4 (RAG pago)", p, t0)

with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump(registros, f, ensure_ascii=False, indent=2, default=str)
print(
    "ok",
    len(registros),
    "chamadas",
    at.session_state["perguntas_livres_usadas"],
    "custo",
    at.session_state["custo_usd_acumulado"],
)
