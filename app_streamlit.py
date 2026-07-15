"""Interface de consulta (Streamlit, estilo chat) — seções 5.11 e 5.13 (RF10, RF11).

Transparência de demonstração: a interface SEMPRE exibe em qual modo está
(demonstração cacheada vs. pergunta livre) e qual provedor gerou a resposta —
ninguém confunde resposta cacheada com inferência ao vivo.

Padrão de deploy (RN03/5.13): abre em modo demonstração cacheado, que funciona
SEM nenhum segredo configurado; pergunta livre é limitada por sessão e o
controle real de custo é o teto no lado do provedor.
"""

from __future__ import annotations

import json

import streamlit as st

from src.config import DIR_RESULTADOS_AVALIACAO, carregar_config

ARQUIVO_CACHE_DEMO = DIR_RESULTADOS_AVALIACAO / "respostas_cacheadas.json"

st.set_page_config(page_title="Assistente de Research Financeiro", page_icon="📊")
config = carregar_config()


@st.cache_data
def carregar_cache_demo() -> dict:
    """Respostas pré-computadas das 45 perguntas do conjunto-padrão
    (geradas pela etapa de avaliação — custo zero em produção)."""
    if ARQUIVO_CACHE_DEMO.exists():
        return json.loads(ARQUIVO_CACHE_DEMO.read_text(encoding="utf-8"))
    return {}


@st.cache_resource
def _pipeline_ao_vivo():
    """Recuperador (índices carregados com guarda RNF09) + provedor LLM,
    instanciados uma única vez por processo."""
    from src.geracao import fabricar_provedor_llm
    from src.recuperacao import Estrategia, Recuperador

    return (
        Recuperador(config),
        fabricar_provedor_llm(config),
        Estrategia(config.estrategia_padrao),
    )


def responder_pergunta_livre(pergunta: str) -> dict:
    """Recuperação + geração ao vivo (uma chamada real de API por consulta).

    Embeddings da consulta SEMPRE com o mesmo modelo do índice (RNF09/5.13)."""
    from src.geracao import gerar_resposta

    recuperador, provedor_llm, estrategia = _pipeline_ao_vivo()
    recuperados = recuperador.recuperar(pergunta, estrategia)
    resposta, _ = gerar_resposta(
        pergunta, [r.chunk for r in recuperados], provedor_llm, config
    )
    if resposta.recusa:
        conteudo = "**Recusa (RN02):** " + (
            resposta.motivo_recusa or "sem evidência suficiente no corpus."
        )
    else:
        conteudo = resposta.resposta or "—"
        if resposta.citacoes:
            conteudo += "\n\n" + "\n".join(
                f"> 📄 {c.empresa} · {c.documento} · {c.trimestre} · pág. {c.pagina}"
                for c in resposta.citacoes
            )
    return {
        "resposta": conteudo,
        "fontes": [
            f"{r.chunk.empresa} · {r.chunk.documento} · "
            f"págs. {r.chunk.pagina_inicio}–{r.chunk.pagina_fim}"
            for r in recuperados
        ],
    }


# --- Estado de sessão -------------------------------------------------------
if "historico" not in st.session_state:
    st.session_state.historico = []  # [{papel, conteudo, fontes, provedor, modo}]
if "perguntas_livres_usadas" not in st.session_state:
    st.session_state.perguntas_livres_usadas = 0

# --- Barra lateral: modo e transparência ------------------------------------
st.sidebar.title("Assistente de Research Financeiro")
st.sidebar.caption(
    "RAG sobre releases de resultado públicos dos 5 maiores bancos do Brasil. "
    "Toda resposta cita a fonte; sem evidência no corpus, o sistema recusa."
)

cache_demo = carregar_cache_demo()
modo_livre_disponivel = (
    st.session_state.perguntas_livres_usadas
    < config.limite_perguntas_livres_por_sessao
)
modo = st.sidebar.radio(
    "Modo",
    ["Demonstração (cacheado)", "Pergunta livre"],
    index=0 if config.modo_demonstracao_cacheado else 1,
)
st.sidebar.info(
    f"**Modo ativo:** {modo}\n\n"
    f"**Provedor LLM:** `{config.llm_provider}` · "
    f"**Embeddings:** `{config.embedding_provider}`\n\n"
    f"Perguntas livres restantes na sessão: "
    f"{max(0, config.limite_perguntas_livres_por_sessao - st.session_state.perguntas_livres_usadas)}"
)

# --- Corpo -------------------------------------------------------------------
st.title("📊 Consulta ao corpus de releases")

for msg in st.session_state.historico:
    with st.chat_message(msg["papel"]):
        st.markdown(msg["conteudo"])
        if msg.get("fontes"):
            with st.expander("Trechos recuperados (empresa · documento · página)"):
                for fonte in msg["fontes"]:
                    st.markdown(f"- {fonte}")
        if msg.get("modo"):
            st.caption(f"modo: {msg['modo']} · provedor: {msg.get('provedor', '—')}")

if modo == "Demonstração (cacheado)":
    if not cache_demo:
        st.warning(
            "Cache de demonstração ainda não gerado — rode a etapa de avaliação "
            "(`python executar_pipeline.py --etapa avaliacao`) para pré-computar "
            "as respostas do conjunto-padrão."
        )
    else:
        escolha = st.selectbox(
            "Escolha uma pergunta do conjunto-padrão (resposta pré-computada "
            "lado a lado com o gabarito):",
            sorted(cache_demo),
        )
        if st.button("Ver resposta cacheada"):
            item = cache_demo[escolha]
            st.session_state.historico.append(
                {"papel": "user", "conteudo": escolha}
            )
            st.session_state.historico.append(
                {
                    "papel": "assistant",
                    "conteudo": item.get("resposta", "—"),
                    "fontes": item.get("fontes", []),
                    "modo": "demonstração cacheada",
                    "provedor": item.get("provedor", "—"),
                }
            )
            st.rerun()
else:
    pergunta = st.chat_input(
        "Pergunte sobre os releases (ex.: lucro líquido do banco X no 4T2025)"
    )
    if pergunta:
        if not modo_livre_disponivel:
            st.error(
                "Limite de perguntas livres desta sessão atingido (RN03). "
                "O modo demonstração continua disponível."
            )
        else:
            st.session_state.historico.append({"papel": "user", "conteudo": pergunta})
            try:
                item = responder_pergunta_livre(pergunta)
                st.session_state.perguntas_livres_usadas += 1
                st.session_state.historico.append(
                    {
                        "papel": "assistant",
                        "conteudo": item["resposta"],
                        "fontes": item.get("fontes", []),
                        "modo": "pergunta livre (inferência ao vivo)",
                        "provedor": config.llm_provider,
                    }
                )
            except NotImplementedError as exc:
                st.warning(f"Funcionalidade pendente no boilerplate: {exc}")
            st.rerun()
