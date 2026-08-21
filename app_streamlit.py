"""Interface de consulta (Streamlit, estilo chat) — seções 5.11 e 5.13 (RF10, RF11).

Transparência de demonstração: a interface SEMPRE exibe em qual modo está
(demonstração cacheada vs. pergunta livre) e qual provedor gerou a resposta —
ninguém confunde resposta cacheada com inferência ao vivo.

Padrão de deploy (RN03/5.13): abre em modo demonstração cacheado, que funciona
SEM nenhum segredo configurado; pergunta livre é limitada por sessão e o
app reserva/debita custo conservadoramente por sessão. Esse estado não
sobrevive a um encerramento abrupto e não substitui um teto externo do provedor.
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path

import streamlit as st

from src.avaliacao import (
    _carregar_checkpoint,
    _construir_cache_demo,
    carregar_conjunto_padrao,
    hash_json_canonico,
    validar_estado_material_atual,
    validar_metricas_teste_automaticas,
)
from src.bloqueio import bloqueio_compartilhado
from src.config import (
    DIR_INDICE_VETORIAL,
    DIR_RESULTADOS_AVALIACAO,
    carregar_config,
)
from src.seguranca import (
    ResultadoGuardrail,
    avaliar_entrada,
    avaliar_saida,
    texto_de_recusa,
)

ARQUIVO_CACHE_DEMO = DIR_RESULTADOS_AVALIACAO / "respostas_cacheadas.json"
ARQUIVO_METRICAS_TESTE = DIR_RESULTADOS_AVALIACAO / "metricas_teste.json"
LOGGER = logging.getLogger(__name__)
ESTRATEGIAS_AVALIACAO = frozenset(
    {"closed_book", "keyword", "semantica", "hibrida", "fatos"}
)

try:
    from src.geracao import redigir_dados_pessoais as _redator_central
except ImportError:
    _redator_central = None

_PADROES_PII_FALLBACK = (
    re.compile(
        r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])",
        re.IGNORECASE,
    ),
    re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"),
    re.compile(r"(?<!\d)(?:\+55\s*)?\(\d{2}\)\s*\d{4,5}-\d{4}(?!\d)"),
)

st.set_page_config(page_title="Assistente de Research Financeiro", page_icon="📊")
config = carregar_config()


def _redigir_para_exibicao(texto: object) -> str:
    """Redige PII antes de um trecho recuperado chegar ao navegador.

    A implementação central, quando disponível, é a fonte de verdade. O
    fallback cobre formatos inequívocos para que o app continue seguro durante
    atualizações desacopladas dos módulos do pipeline.
    """
    if not isinstance(texto, str):
        return ""
    if _redator_central is not None:
        redigido = _redator_central(texto)
        if not isinstance(redigido, str):
            raise TypeError("O redator central deve devolver texto.")
        return redigido
    for padrao in _PADROES_PII_FALLBACK:
        texto = padrao.sub("[DADO PESSOAL REDIGIDO]", texto)
    return texto


def _carregar_objeto_json(caminho: Path, nome: str) -> dict:
    objeto = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if not isinstance(objeto, dict):
        raise ValueError(f"{nome} deve ser um objeto JSON.")
    return objeto


def _validar_metricas_publicaveis(
    metricas: dict,
) -> tuple[str, frozenset[str], str, str, str, int]:
    meta = validar_metricas_teste_automaticas(
        metricas,
        status_esperados=frozenset({"completa"}),
        exigir_auditorias=True,
    )
    return (
        meta["fingerprint"],
        frozenset(meta["run_ids"]),
        meta["estrategia_demo_e_auditoria"],
        meta["provedor_llm"],
        meta["cache_demo_sha256"],
        meta["cache_demo_n_itens"],
    )


def carregar_cache_demo(
    caminho_cache: Path | None = None,
    caminho_metricas: Path | None = None,
) -> dict:
    """Carrega um cache final coerente com as métricas publicadas.

    Não há cache de processo aqui: os arquivos são pequenos e relidos em cada
    rerun do Streamlit. Assim, uma publicação ou invalidação não fica retida
    indefinidamente por um worker antigo.
    """
    caminho_cache = Path(caminho_cache or ARQUIVO_CACHE_DEMO)
    caminho_metricas = Path(caminho_metricas or ARQUIVO_METRICAS_TESTE)
    if not caminho_cache.exists():
        return {}
    objeto = _carregar_objeto_json(caminho_cache, "Cache de demonstração")
    if not objeto:
        return {}
    if not caminho_metricas.exists():
        raise ValueError(
            "Cache de demonstração existe sem metricas_teste.json correspondente."
        )
    metricas = _carregar_objeto_json(caminho_metricas, "Métricas de teste")
    (
        fingerprint_metricas,
        run_ids_metricas,
        estrategia_metricas,
        provedor_metricas,
        hash_cache_esperado,
        n_cache_esperado,
    ) = _validar_metricas_publicaveis(metricas)
    config = carregar_config()
    perguntas_teste = [
        pergunta
        for pergunta in carregar_conjunto_padrao(config)
        if pergunta.conjunto == "teste"
    ]
    caminho_lock_indice = (
        DIR_INDICE_VETORIAL.parent / f".{DIR_INDICE_VETORIAL.name}.lock"
    )
    with bloqueio_compartilhado(
        caminho_lock_indice,
        f"o snapshot do índice {DIR_INDICE_VETORIAL}",
    ):
        validar_estado_material_atual(
            config,
            perguntas_teste,
            metricas["_meta"]["fingerprint_componentes"],
        )
        from src.auditoria import _validar_metricas_contra_checkpoint
        from src.recuperacao import Estrategia

        caminho_checkpoint = caminho_metricas.parent / "checkpoint_teste.jsonl"
        _validar_metricas_contra_checkpoint(
            metricas,
            perguntas_teste,
            fingerprint_metricas,
            caminho_checkpoint,
            config,
        )
        itens_checkpoint = _carregar_checkpoint(
            caminho_checkpoint, fingerprint_metricas
        )
        cache_reconstruido = _construir_cache_demo(
            perguntas_teste,
            itens_checkpoint,
            provedor_metricas,
            estrategia_demo=Estrategia(estrategia_metricas),
            fingerprint=fingerprint_metricas,
            conjunto="teste",
        )
        if objeto != cache_reconstruido:
            raise ValueError("Cache diverge da reconstrução do checkpoint final.")
    if (
        hash_json_canonico(objeto) != hash_cache_esperado
        or len(objeto) != n_cache_esperado
    ):
        raise ValueError("Cache de demonstração diverge do hash auditado.")
    campos_obrigatorios = {
        "resposta",
        "fontes",
        "citacoes",
        "trechos_recuperados",
        "provedor",
        "modelo",
        "gabarito",
        "fingerprint",
        "run_id",
        "conjunto",
        "validacao_automatica",
        "pergunta_id",
        "estrategia",
    }
    for pergunta, item in objeto.items():
        if not isinstance(pergunta, str) or not pergunta.strip():
            raise ValueError("Cache contém pergunta vazia ou inválida.")
        if not isinstance(item, dict) or not campos_obrigatorios <= set(item):
            raise ValueError(f"Item inválido no cache para a pergunta {pergunta!r}.")
        if (
            not isinstance(item["resposta"], str)
            or not item["resposta"].strip()
            or not isinstance(item["fontes"], list)
            or any(not isinstance(fonte, str) for fonte in item["fontes"])
            or not isinstance(item["citacoes"], list)
            or not isinstance(item["trechos_recuperados"], list)
            or any(
                not isinstance(trecho, str)
                for trecho in item["trechos_recuperados"]
            )
            or item["conjunto"] != "teste"
            or item["validacao_automatica"] is not True
            or item["fingerprint"] != fingerprint_metricas
            or item["run_id"] not in run_ids_metricas
            or item["estrategia"] != estrategia_metricas
            or item["provedor"] != provedor_metricas
            or any(
                not isinstance(item[campo], str) or not item[campo].strip()
                for campo in (
                    "provedor",
                    "modelo",
                    "gabarito",
                    "fingerprint",
                    "run_id",
                    "pergunta_id",
                    "estrategia",
                )
            )
        ):
            raise ValueError(
                f"Cache não é uma resposta de teste automaticamente validada: "
                f"{pergunta!r}."
            )
        citacoes_esperadas: list[str] = []
        for citacao in item["citacoes"]:
            if (
                not isinstance(citacao, dict)
                or set(citacao) != {"empresa", "documento", "trimestre", "pagina"}
                or any(
                    not isinstance(citacao[campo], str)
                    or not citacao[campo].strip()
                    for campo in ("empresa", "documento", "trimestre")
                )
                or type(citacao["pagina"]) is not int
                or citacao["pagina"] <= 0
            ):
                raise ValueError(f"Citação inválida no cache: {pergunta!r}.")
            citacoes_esperadas.append(
                f"{citacao['empresa']} · {citacao['documento']} · "
                f"{citacao['trimestre']} · pág. {citacao['pagina']}"
            )
        if item["fontes"] != citacoes_esperadas:
            raise ValueError(
                f"Fontes exibidas divergem das citações exatas: {pergunta!r}."
            )
    seguro: dict[str, dict] = {}
    for pergunta, item in objeto.items():
        pergunta_segura = _redigir_para_exibicao(pergunta)
        if pergunta_segura in seguro:
            raise ValueError("Redação de PII produziu perguntas duplicadas no cache.")
        item_seguro = dict(item)
        item_seguro["resposta"] = _redigir_para_exibicao(item["resposta"])
        item_seguro["gabarito"] = _redigir_para_exibicao(item["gabarito"])
        item_seguro["fontes"] = [
            _redigir_para_exibicao(fonte) for fonte in item["fontes"]
        ]
        item_seguro["trechos_recuperados"] = [
            _redigir_para_exibicao(trecho)
            for trecho in item["trechos_recuperados"]
        ]
        seguro[pergunta_segura] = item_seguro
    return seguro


def _construir_pipeline_ao_vivo(identidade_extracao_esperada=None):
    """Recuperador (índices carregados com guarda RNF09) + provedor LLM,
    materializados como um único snapshot coerente em memória."""
    from src.bloqueio import bloqueio_exclusivo
    from src.config import DIR_INDICE_VETORIAL
    from src.geracao import fabricar_provedor_llm
    from src.indexacao import (
        calcular_identidade_extracao,
        calcular_hash_corpus_atual_para_indice,
        carregar_indice_bm25,
        carregar_indice_chroma,
        fabricar_provedor_embeddings,
    )
    from src.recuperacao import Estrategia, Recuperador

    caminho_lock = (
        DIR_INDICE_VETORIAL.parent / f".{DIR_INDICE_VETORIAL.name}.lock"
    )
    with bloqueio_exclusivo(
        caminho_lock,
        f"o snapshot do índice {DIR_INDICE_VETORIAL}",
    ):
        if identidade_extracao_esperada is not None:
            identidade_atual = calcular_identidade_extracao(config)
            if identidade_atual != identidade_extracao_esperada:
                raise RuntimeError(
                    "A identidade OCR mudou durante a materialização do "
                    "pipeline ao vivo; tente novamente."
                )
        provedor_embeddings = fabricar_provedor_embeddings(config)
        hash_corpus = calcular_hash_corpus_atual_para_indice(
            DIR_INDICE_VETORIAL,
            integral=True,
            bancos=config.bancos,
        )
        indice_chroma = carregar_indice_chroma(
            provedor_embeddings,
            config=config,
            dir_indice=DIR_INDICE_VETORIAL,
            hash_corpus_esperado=hash_corpus,
        )
        indice_bm25 = carregar_indice_bm25(
            config=config,
            dir_indice=DIR_INDICE_VETORIAL,
            hash_corpus_esperado=hash_corpus,
        )
        recuperador = Recuperador(
            config,
            indice_chroma=indice_chroma,
            indice_bm25=indice_bm25,
            provedor_embeddings=provedor_embeddings,
            hash_corpus_esperado=hash_corpus,
        )
    return (
        recuperador,
        fabricar_provedor_llm(config),
        Estrategia(config.estrategia_padrao),
    )


@st.cache_resource(ttl=300)
def _pipeline_ao_vivo(identidade_extracao):
    """Cacheia somente enquanto manifesto/código OCR mantêm a identidade."""
    return _construir_pipeline_ao_vivo(identidade_extracao)


class FalhaConsultaAoVivo(RuntimeError):
    """Falha após iniciar a geração, com débito conservador a contabilizar."""

    def __init__(self, custo_reservado_usd: float):
        super().__init__("A geração ao vivo falhou após a reserva de orçamento.")
        self.custo_reservado_usd = custo_reservado_usd


def _contabilizar_reserva_falha(
    custo_atual_usd: float,
    falha: FalhaConsultaAoVivo,
    teto_usd: float,
) -> float:
    """Registra o gasto/reserva integral, inclusive se o provedor violar o teto."""
    del teto_usd  # o teto limita novas chamadas; não pode truncar a contabilidade
    return custo_atual_usd + falha.custo_reservado_usd


class PerguntaBloqueada(ValueError):
    """Entrada barrada por guardrail, antes de qualquer chamada externa.

    Carrega o veredito inteiro — e não só uma mensagem — porque a interface
    precisa da âncora legal para explicar a recusa citando a resolução.
    """

    def __init__(self, resultado: ResultadoGuardrail):
        super().__init__(resultado.motivo)
        self.resultado = resultado


def guardar_entrada(pergunta: str) -> ResultadoGuardrail:
    """Varredura de entrada com os scanners configurados (RN05/RN06)."""
    return avaliar_entrada(
        pergunta,
        tuple(config.guardrails_ativos),
        presidio_habilitado=config.presidio_habilitado,
        presidio_idioma=config.presidio_idioma,
        presidio_modelo_spacy=config.presidio_modelo_spacy,
        prompt_guard_habilitado=config.prompt_guard_habilitado,
        prompt_guard_modelo=config.prompt_guard_modelo,
        prompt_guard_revisao=config.guardrails_modelo_injecao_revision,
        prompt_guard_limiar=config.guardrails_limiar_injection,
    )


def validar_pergunta_livre(pergunta: str) -> str:
    """Normaliza a entrada e impede chamadas vazias ou desproporcionalmente caras."""
    pergunta = pergunta.strip()
    if not pergunta:
        raise ValueError("Digite uma pergunta não vazia.")
    if len(pergunta) > config.limite_caracteres_pergunta:
        raise ValueError(
            "Pergunta excede o limite de "
            f"{config.limite_caracteres_pergunta} caracteres."
        )
    return pergunta


def responder_pergunta_livre(
    pergunta: str, orcamento_restante_usd: float | None = None
) -> dict:
    """Recuperação + geração ao vivo (uma chamada real de API por consulta).

    Embeddings da consulta SEMPRE com o mesmo modelo do índice (RNF09/5.13)."""
    from src.geracao import (
        PROMPT_SISTEMA,
        PROMPT_SISTEMA_CLOSED_BOOK,
        gerar_resposta,
        montar_prompt_usuario,
    )
    from src.recuperacao import Estrategia

    pergunta = validar_pergunta_livre(pergunta)
    # Portão duplo, de propósito: a interface já barrou antes de debitar a cota,
    # mas a guarda que importa é a que mora na função que fala com o provedor.
    # Um chamador futuro não pode contornar a RN05 esquecendo de varrer antes.
    entrada = guardar_entrada(pergunta)
    if entrada.bloqueado:
        raise PerguntaBloqueada(entrada)
    pergunta = entrada.texto_seguro
    if config.embedding_provider not in {"ollama", "local"}:
        raise RuntimeError(
            "Perguntas livres exigem embeddings locais: o custo de embeddings "
            "externos ainda não integra o orçamento da sessão."
        )
    from src.indexacao import calcular_identidade_extracao

    identidade_extracao = calcular_identidade_extracao(config)
    recuperador, provedor_llm, estrategia = _pipeline_ao_vivo(
        identidade_extracao
    )
    if not getattr(provedor_llm, "custo_auditavel", True):
        raise RuntimeError(
            "O provedor não oferece estimativa auditável antes da chamada."
        )
    recuperados = recuperador.recuperar(pergunta, estrategia)
    chunks = [resultado.chunk for resultado in recuperados]
    modo_closed_book = estrategia == Estrategia.CLOSED_BOOK
    prompt_sistema = (
        PROMPT_SISTEMA_CLOSED_BOOK if modo_closed_book else PROMPT_SISTEMA
    )
    prompt_usuario = montar_prompt_usuario(
        pergunta, chunks, modo_closed_book=modo_closed_book
    )
    saldo_informado = (
        config.orcamento_teto_usd
        if orcamento_restante_usd is None
        else orcamento_restante_usd
    )
    if (
        not isinstance(saldo_informado, (int, float))
        or isinstance(saldo_informado, bool)
        or not math.isfinite(float(saldo_informado))
        or saldo_informado < 0
    ):
        raise ValueError("Saldo de orçamento inválido.")
    saldo = min(config.orcamento_teto_usd, float(saldo_informado))
    estimativa = provedor_llm.estimar_custo_maximo(
        prompt_sistema, prompt_usuario
    )
    if estimativa is None:
        raise RuntimeError(
            "O provedor não oferece estimativa auditável antes da chamada."
        )
    if (
        not isinstance(estimativa, (int, float))
        or isinstance(estimativa, bool)
        or not math.isfinite(float(estimativa))
        or estimativa < 0
    ):
        raise RuntimeError("Estimativa de custo inválida.")
    if estimativa > saldo:
        raise RuntimeError("A próxima chamada excederia o orçamento da sessão.")

    custo_a_debitar_em_falha = float(estimativa)
    try:
        resposta, uso = gerar_resposta(
            pergunta,
            chunks,
            provedor_llm,
            config,
            modo_closed_book=modo_closed_book,
        )
        if (
            uso.custo_usd is None
            or not isinstance(uso.custo_usd, (int, float))
            or isinstance(uso.custo_usd, bool)
            or not math.isfinite(float(uso.custo_usd))
            or uso.custo_usd < 0
        ):
            raise RuntimeError("A chamada não retornou custo auditável.")
        custo_a_debitar_em_falha = float(uso.custo_usd)
        if (
            custo_a_debitar_em_falha > float(estimativa) + 1e-12
            or custo_a_debitar_em_falha > saldo + 1e-12
        ):
            raise RuntimeError(
                "Custo observado excedeu a estimativa ou o saldo reservado."
            )
        if resposta.recusa:
            conteudo = "**Recusa (RN02):** " + (
                resposta.motivo_recusa or "sem evidência suficiente no corpus."
            )
        else:
            conteudo = resposta.resposta or "—"
            if resposta.citacoes:
                conteudo += "\n\n" + "\n".join(
                    f"> 📄 {c.empresa} · {c.documento} · "
                    f"{c.trimestre} · pág. {c.pagina}"
                    for c in resposta.citacoes
                )
        conteudo = _redigir_para_exibicao(conteudo)
        # Guarda de saída (RN05 nos dois sentidos): entrada limpa não garante
        # resposta limpa. Bloquear aqui NÃO desfaz o débito — a chamada já foi
        # paga, e o custo continua sendo contabilizado abaixo.
        saida = avaliar_saida(
            conteudo,
            tuple(config.guardrails_ativos),
            presidio_habilitado=config.presidio_habilitado,
            presidio_idioma=config.presidio_idioma,
            presidio_modelo_spacy=config.presidio_modelo_spacy,
        )
        conteudo = (
            texto_de_recusa(saida) if saida.bloqueado else saida.texto_seguro
        )
    except Exception as exc:
        raise FalhaConsultaAoVivo(custo_a_debitar_em_falha) from exc
    return {
        "resposta": conteudo,
        "fontes": [
            {
                "rotulo": (
                    f"{r.chunk.empresa} · {r.chunk.documento} · "
                    f"págs. {r.chunk.pagina_inicio}–{r.chunk.pagina_fim}"
                ),
                "trecho": _redigir_para_exibicao(
                    r.chunk.texto.split("\n", 1)[-1]
                )[:800],
            }
            for r in recuperados
        ],
        "custo_usd": float(uso.custo_usd),
        "modelo": uso.modelo,
    }


# --- Estado de sessão -------------------------------------------------------
if "historico" not in st.session_state:
    st.session_state.historico = []  # [{papel, conteudo, fontes, provedor, modo}]
if "perguntas_livres_usadas" not in st.session_state:
    st.session_state.perguntas_livres_usadas = 0
if "custo_usd_acumulado" not in st.session_state:
    st.session_state.custo_usd_acumulado = 0.0

# --- Barra lateral: modo e transparência ------------------------------------
st.sidebar.title("Assistente de Research Financeiro")
st.sidebar.caption(
    "RAG sobre releases de resultado públicos dos cinco bancos do corpus. "
    "Toda resposta cita a fonte; sem evidência no corpus, o sistema recusa."
)
st.sidebar.caption(
    "Uso educacional e demonstrativo. Não constitui recomendação de investimento."
)

try:
    cache_demo = carregar_cache_demo()
    erro_cache = None
except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
    cache_demo = {}
    erro_cache = f"{type(exc).__name__}: {exc}"

modo_livre_disponivel = (
    config.habilitar_perguntas_livres
    and st.session_state.perguntas_livres_usadas
    < config.limite_perguntas_livres_por_sessao
    and st.session_state.custo_usd_acumulado < config.orcamento_teto_usd
)
opcoes_modo = ["Demonstração (cacheado)"]
if config.habilitar_perguntas_livres:
    opcoes_modo.append("Pergunta livre")
modo = st.sidebar.radio(
    "Modo",
    opcoes_modo,
    index=(
        0
        if config.modo_demonstracao_cacheado or len(opcoes_modo) == 1
        else 1
    ),
)
st.sidebar.info(
    f"**Modo ativo:** {modo}\n\n"
    f"**Provedor LLM:** `{config.llm_provider}` · "
    f"**Embeddings:** `{config.embedding_provider}`\n\n"
    f"Perguntas livres restantes na sessão: "
    f"{max(0, config.limite_perguntas_livres_por_sessao - st.session_state.perguntas_livres_usadas)}\n\n"
    f"Orçamento restante da sessão: US$ "
    f"{max(0.0, config.orcamento_teto_usd - st.session_state.custo_usd_acumulado):.4f}"
)
st.sidebar.caption(
    "**Guardrails ativos:** "
    + (", ".join(f"`{s}`" for s in config.guardrails_ativos) or "_nenhum_")
    + ". Pedido de recomendação, preço-alvo ou aconselhamento pessoal é "
    "recusado antes de qualquer chamada externa (Res. CVM 20/2021 e 19/2021); "
    "identificadores pessoais são anonimizados e não entram em log."
)
if not config.habilitar_perguntas_livres:
    st.sidebar.warning(
        "Perguntas livres estão desabilitadas por segurança. "
        "Ative-as explicitamente apenas em ambiente controlado."
    )

# --- Corpo -------------------------------------------------------------------
st.title("📊 Consulta ao corpus de releases")
st.caption(
    "Demonstração técnica sobre documentos públicos; não é aconselhamento financeiro."
)

for msg in st.session_state.historico:
    with st.chat_message(msg["papel"]):
        st.markdown(msg["conteudo"])
        if msg.get("fontes"):
            with st.expander(
                "Trechos recuperados (não equivalem necessariamente às citações usadas)"
            ):
                for fonte in msg["fontes"]:
                    if isinstance(fonte, dict):
                        st.markdown(f"**{fonte.get('rotulo', 'Fonte')}**")
                        st.caption(_redigir_para_exibicao(fonte.get("trecho", "")))
                    else:
                        st.markdown(f"- {_redigir_para_exibicao(fonte)}")
        if msg.get("gabarito"):
            st.info(f"Gabarito verificado: {msg['gabarito']}")
        if msg.get("modo"):
            st.caption(f"modo: {msg['modo']} · provedor: {msg.get('provedor', '—')}")

if modo == "Demonstração (cacheado)":
    if erro_cache:
        st.error(f"Cache de demonstração inválido: {erro_cache}")
    if not cache_demo:
        st.warning(
            "Ainda não há cache final validado do conjunto de teste congelado. "
            "O modo será habilitado somente após a segunda leitura, o congelamento "
            "e uma avaliação completa com fingerprint."
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
                    "gabarito": item.get("gabarito"),
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
                "Perguntas livres estão desabilitadas ou o limite da sessão foi "
                "atingido. O modo demonstração continua disponível."
            )
        else:
            try:
                guarda_entrada = guardar_entrada(
                    validar_pergunta_livre(pergunta)
                )
            except ValueError as exc:
                st.error(str(exc))
                guarda_entrada = None
            if guarda_entrada is not None and guarda_entrada.bloqueado:
                # A pergunta original NUNCA entra no histórico: o que aparece na
                # tela e no estado de sessão é a forma anonimizada (RN06).
                st.session_state.historico.append(
                    {"papel": "user", "conteudo": guarda_entrada.texto_seguro}
                )
                st.session_state.historico.append(
                    {
                        "papel": "assistant",
                        "conteudo": texto_de_recusa(guarda_entrada),
                        "fontes": [],
                        "modo": "recusa por guardrail (nenhuma chamada externa)",
                        "provedor": "—",
                    }
                )
                # Sem débito de cota nem de orçamento: a cota existe para conter
                # gasto, e recusar aqui não gastou nada. Debitá-la faria um falso
                # bloqueio custar ao usuário duas vezes.
                st.rerun()
            elif guarda_entrada is not None:
                pergunta = guarda_entrada.texto_seguro
                st.session_state.perguntas_livres_usadas += 1
                st.session_state.historico.append(
                    {"papel": "user", "conteudo": pergunta}
                )
                try:
                    item = responder_pergunta_livre(
                        pergunta,
                        orcamento_restante_usd=max(
                            0.0,
                            config.orcamento_teto_usd
                            - st.session_state.custo_usd_acumulado,
                        ),
                    )
                    st.session_state.custo_usd_acumulado += item["custo_usd"]
                    st.session_state.historico.append(
                        {
                            "papel": "assistant",
                            "conteudo": item["resposta"],
                            "fontes": item.get("fontes", []),
                            "modo": "pergunta livre (inferência ao vivo)",
                            "provedor": (
                                f"{config.llm_provider}/{item.get('modelo', '—')}"
                            ),
                        }
                    )
                except FalhaConsultaAoVivo as exc:
                    st.session_state.custo_usd_acumulado = (
                        _contabilizar_reserva_falha(
                            st.session_state.custo_usd_acumulado,
                            exc,
                            config.orcamento_teto_usd,
                        )
                    )
                    LOGGER.warning(
                        "Geração ao vivo falhou após reserva; custo conservador "
                        "contabilizado (tipo=%s).",
                        type(exc.__cause__).__name__,
                    )
                    st.session_state.historico.append(
                        {
                            "papel": "assistant",
                            "conteudo": (
                                "A consulta ao vivo falhou de forma segura. "
                                "Nenhuma resposta financeira foi apresentada; "
                                "a reserva conservadora de custo foi debitada. "
                                "Tente novamente mais tarde ou use o modo cacheado."
                            ),
                            "fontes": [],
                            "modo": "pergunta livre (falha segura)",
                            "provedor": config.llm_provider,
                        }
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "Falha segura antes da geração ao vivo (tipo=%s).",
                        type(exc).__name__,
                    )
                    st.session_state.historico.append(
                        {
                            "papel": "assistant",
                            "conteudo": (
                                "A consulta ao vivo falhou de forma segura. "
                                "Nenhuma resposta financeira foi apresentada; "
                                "tente novamente mais tarde ou use o modo cacheado."
                            ),
                            "fontes": [],
                            "modo": "pergunta livre (falha segura)",
                            "provedor": config.llm_provider,
                        }
                    )
                st.rerun()
