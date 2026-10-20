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
import uuid
from pathlib import Path
from time import perf_counter

import streamlit as st

from src import observabilidade
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


@st.cache_resource(show_spinner=False)
def _ligar_observabilidade() -> observabilidade.Estado:
    """Um cliente Langfuse por processo (5.12). Sem chave, fica desligado."""
    return observabilidade.configurar(config)


estado_observabilidade = _ligar_observabilidade()


INTERVALO_STREAMING_S = 0.012


def _fluxo_de_texto(texto: str):
    """Emite a resposta **já validada**, palavra a palavra, para `write_stream`.

    O que NÃO se faz aqui é transmitir o token cru do provedor, e a razão é a
    garantia central do projeto: a RN02 só pode rebaixar uma resposta depois de
    ver o texto inteiro, porque o grounding confere cada valor numérico contra
    os trechos citados. Transmitir o rascunho poria na tela um número que a
    guarda derrubaria um segundo depois — o usuário teria lido exatamente a
    alucinação que o sistema existe para não afirmar. Aqui a validação acontece
    antes, e o streaming é da resposta que sobreviveu a ela.
    """
    import time

    for indice, palavra in enumerate(str(texto).split(" ")):
        yield palavra if indice == 0 else " " + palavra
        time.sleep(INTERVALO_STREAMING_S)


def _escapar_cifrao(texto: object) -> str:
    """Impede que dois `R$` no mesmo texto virem fórmula LaTeX no markdown.

    O markdown do Streamlit lê `$...$` como matemática: "R$ 3,4 bi e R$ 3,1 bi"
    renderizaria o trecho entre os cifrões em itálico matemático e sumiria com
    os dois símbolos — número financeiro desfigurado na tela.
    """
    return str(texto).replace("$", "\\$")


_IMAGEM_MARKDOWN = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_SOBRESCRITO_LATEX = re.compile(r"\$?\^\{[^}]*\}\$?")
_CELULA_SEPARADORA = re.compile(r":?-{3,}:?")
_MARCADOR_DE_TITULO = re.compile(r"^#{1,6}\s*")


def _limpar_trecho_ocr(texto: str) -> str:
    """Tira do trecho recuperado a marcação do OCR que só polui a leitura.

    Só apresentação: o chunk indexado e o texto que a RN02 confere não passam
    por aqui. Remove referência a imagem (`![img-0.jpeg](img-0.jpeg)`), chamada
    de nota em LaTeX (`^{(1)}`) e marcador de título; linha de tabela vira
    células separadas por ` · `, sem as células `---` do cabeçalho markdown —
    que no OCR às vezes vêm coladas a células de dado, por isso se descarta a
    célula e não a linha.
    """
    linhas: list[str] = []
    for linha in str(texto).splitlines():
        linha = _SOBRESCRITO_LATEX.sub("", _IMAGEM_MARKDOWN.sub("", linha)).strip()
        if linha.startswith("|"):
            celulas = (celula.strip() for celula in linha.strip("|").split("|"))
            linha = " · ".join(
                celula
                for celula in celulas
                if celula and not _CELULA_SEPARADORA.fullmatch(celula)
            )
        linha = _MARCADOR_DE_TITULO.sub("", linha).strip()
        if linha:
            linhas.append(linha)
    return "\n".join(linhas)


# Mora em `src.cobertura`, ao lado de `formatar_reais`, porque a redação
# conversacional do painel precisa dela e o módulo de dados não pode importar a
# interface. Reexportado aqui pelo nome antigo: é assim que a tela e a suíte de
# apresentação a chamam.
from src.cobertura import formatar_reais_legivel  # noqa: E402


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


STATUS_AUDITORIA_PENDENTE = "auditoria_manual_pendente"
_ERRO_DE_STATUS = "Status das métricas de teste não permite esta operação."


def _cache_aguarda_auditoria(
    erro_cache: str, caminho_metricas: Path | None = None
) -> bool:
    """O erro do cache é o estado DECLARADO de auditoria pendente?

    Só nesse caso a tela troca o erro vermelho por aviso: é trava de protocolo,
    não defeito. As duas condições são exigidas juntas — a mensagem ser a do
    status E o status gravado ser o de auditoria pendente —, para que métrica
    corrompida, fingerprint divergente ou qualquer outro status continuem
    aparecendo como erro. Na dúvida (arquivo ilegível), é erro.
    """
    if not erro_cache.endswith(_ERRO_DE_STATUS):
        return False
    try:
        metricas = _carregar_objeto_json(
            Path(caminho_metricas or ARQUIVO_METRICAS_TESTE), "Métricas de teste"
        )
    except (OSError, ValueError):
        return False
    meta = metricas.get("_meta")
    return isinstance(meta, dict) and meta.get("status") == STATUS_AUDITORIA_PENDENTE


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


def _assinatura_do_indice() -> tuple:
    """Tamanho e mtime dos arquivos que identificam o índice em disco.

    Reconstruir o índice reescreve os dois; a assinatura muda e o pipeline em
    cache é descartado, com a guarda RNF09 rodando de novo na carga.
    """
    from src.config import DIR_INDICE_VETORIAL

    assinatura = []
    for nome in ("metadados_construcao.json", "chunks.json"):
        try:
            estado = (DIR_INDICE_VETORIAL / nome).stat()
            assinatura.append((nome, estado.st_size, estado.st_mtime_ns))
        except OSError:
            assinatura.append((nome, None, None))
    return tuple(assinatura)


def _pipeline_ao_vivo(identidade_extracao):
    """Cacheia enquanto manifesto/código OCR e o índice em disco não mudam."""
    return _pipeline_em_cache(identidade_extracao, _assinatura_do_indice())


# Sem `ttl`: com `ttl=300` o índice expirava depois de 5 minutos sem pergunta,
# e a seguinte pagava a carga inteira de novo (4,4 s de carga + 7,3 s da
# primeira recuperação no trace DEV003 de 19/10). Quem invalida agora é a
# chave: identidade de OCR e assinatura do índice. Uma entrada só, para que um
# índice reconstruído não deixe o anterior preso na memória.
# O nome do parâmetro não pode começar com "_": o Streamlit deixa esses
# parâmetros fora da chave do cache, e a assinatura não invalidaria nada.
@st.cache_resource(max_entries=1, show_spinner=False)
def _pipeline_em_cache(identidade_extracao, assinatura_indice):
    return _construir_pipeline_ao_vivo(identidade_extracao)


@st.cache_resource(show_spinner="Preparando o índice para perguntas ao vivo…")
def aquecer_caminho_ao_vivo() -> dict:
    """Paga na subida do app a carga que a primeira pergunta pagava.

    Medido nos traces de 19/10: a primeira pergunta do processo levou 13 s,
    dos quais 1,2 s eram do LLM. O resto era carregar o índice, carregar o
    modelo de embeddings no Ollama na primeira recuperação e, com o Presidio
    ligado, carregar os guardrails (6,7 s). Roda uma vez por processo, só com
    pergunta livre habilitada, sem LLM e sem custo. Falha aqui não derruba a
    página: a pergunta seguinte cai no caminho de sempre e mostra o erro.
    """
    tempos: dict[str, object] = {}

    def medir(nome: str, acao) -> None:
        inicio = perf_counter()
        try:
            acao()
            tempos[nome] = round(perf_counter() - inicio, 2)
        except Exception as exc:  # noqa: BLE001 - aquecimento é opcional
            tempos[nome] = f"falhou ({type(exc).__name__})"
            LOGGER.warning("aquecimento de %s falhou (tipo=%s).", nome, type(exc).__name__)

    medir("guardrails", lambda: guardar_entrada("Qual foi o lucro líquido no trimestre?"))
    if config.embedding_provider in {"ollama", "local"}:
        from src.indexacao import calcular_identidade_extracao

        def recuperar_uma_vez() -> None:
            recuperador, _llm, estrategia = _pipeline_ao_vivo(
                calcular_identidade_extracao(config)
            )
            recuperador.recuperar("lucro líquido do trimestre", estrategia)

        medir("indice_e_embeddings", recuperar_uma_vez)
    LOGGER.info("aquecimento do caminho ao vivo: %s", tempos)
    return tempos


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


def _resumo_guardrail(resultado: ResultadoGuardrail) -> dict:
    """O que o trace guarda de um veredito: decisão e scanners, nunca o detalhe."""
    return {
        "bloqueado": resultado.bloqueado,
        "achados": [f"{a.scanner}/{a.subtipo}" for a in resultado.achados],
        "entidades_pii_anonimizadas": len(resultado.entidades_pii),
    }


def guardar_entrada(pergunta: str) -> ResultadoGuardrail:
    """Varredura de entrada com os scanners configurados (RN05/RN06).

    A etapa do trace não recebe a pergunta: ela é crua aqui, e só o
    `texto_seguro` que sai da varredura pode ir para fora (RN06)."""
    with observabilidade.etapa("guardrail.entrada", tipo="guardrail") as etapa:
        resultado = avaliar_entrada(
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
        etapa.atualizar(
            saida=lambda: {
                **_resumo_guardrail(resultado),
                "texto_seguro": observabilidade.texto_livre(resultado.texto_seguro),
            }
        )
    return resultado


def _tentar_rota(nome: str, rota, pergunta: str, **argumentos) -> dict | None:
    """Chama uma rota opcional dentro de uma etapa do trace.

    Falha da rota vira aviso no log e `None`, como sempre foi: um extra nunca
    derruba o app."""
    item = None
    with observabilidade.etapa(f"rota.{nome.replace(' ', '_')}") as etapa:
        try:
            item = rota(pergunta, **argumentos)
        except Exception as exc:  # nunca derruba o app por um extra
            LOGGER.warning("rota %s falhou: %s", nome, exc)
            etapa.atualizar(metadados={"falha": type(exc).__name__})
        etapa.atualizar(
            saida=lambda: {
                "atendeu": item is not None,
                "modo": (item or {}).get("modo"),
                "encaminhar": bool((item or {}).get("encaminhar")),
                "custo_usd": (item or {}).get("custo_usd", 0.0),
            }
        )
    return item


@st.cache_resource(show_spinner=False)
def carregar_rota_prospectiva() -> dict | None:
    """Índice de cobertura + panorama agregado, carregados uma vez.

    Devolve ``None`` se o panorama não tiver sido gerado — a rota some em vez
    de derrubar o aplicativo, porque ela é um acréscimo e o resto do produto
    não depende dela. O que NÃO pode acontecer em silêncio é a rota responder
    com dado ausente; por isso `carregar_panorama` falha fechado e o erro é
    registrado aqui.
    """
    from src.cobertura import carregar_indice_cobertura
    from src.dados_estruturados import abrir_conexao_somente_leitura
    from src.projecao import PanoramaIndisponivelError, carregar_escores, carregar_panorama

    try:
        panorama = carregar_panorama()
    except PanoramaIndisponivelError as erro:
        LOGGER.warning("rota prospectiva desligada: %s", erro)
        return None

    try:
        indice = carregar_indice_cobertura(config)
        conexao = abrir_conexao_somente_leitura(config)
        try:
            # Prejuízos e porte na mesma varredura: o porte é o que permite
            # comparar o escore com a taxa-base da faixa certa, e sem essa
            # comparação o número por emissor vira só um número.
            # RN10: o 4T não existe como ITR e é derivado por aritmética. No
            # painel carregado ele responde por 420 das 435 linhas de 4T2025 —
            # contar derivado junto com arquivado e apresentar o total como
            # "prejuízos consolidados" seria exatamente o que a RN10 proíbe.
            # Por isso os dois vêm separados e a resposta declara a divisão.
            linhas_painel = conexao.execute(
                "SELECT cd_cvm, "
                "  sum(CASE WHEN lucro_liquido_consolidado < 0 "
                "           AND origem = 'arquivado' THEN 1 ELSE 0 END), "
                "  sum(CASE WHEN lucro_liquido_consolidado < 0 "
                "           AND origem = 'derivado' THEN 1 ELSE 0 END), "
                "  avg(ativo_total) "
                "FROM indicadores WHERE lucro_liquido_consolidado IS NOT NULL "
                "GROUP BY 1"
            ).fetchall()
            prejuizos = {str(cd): int(n) for cd, n, _, _ in linhas_painel}
            prejuizos_derivados = {
                str(cd): int(n) for cd, _, n, _ in linhas_painel
            }
            ativos = {
                str(cd): float(ativo)
                for cd, _, _, ativo in linhas_painel
                if ativo is not None
            }
        finally:
            conexao.close()
    except Exception as erro:  # painel ausente no deploy enxuto (RNF12)
        LOGGER.warning("rota prospectiva sem painel: %s", erro)
        return None

    escores = None
    if config.previsao_por_emissor_habilitada:
        # Falha fechada de propósito: pediram o modo local e o dado não está
        # lá. Degradar para o modo público em silêncio seria pior — o analista
        # leria a recusa achando que é a política, não a falta do arquivo.
        escores = carregar_escores()

    return {
        "panorama": panorama,
        "indice": indice,
        "prejuizos": prejuizos,
        "prejuizos_derivados": prejuizos_derivados,
        "ativos": ativos,
        "escores": escores,
    }


def responder_prospectiva_se_couber(pergunta: str) -> dict | None:
    """Roteia a pergunta prospectiva sobre emissor nomeado (RN07).

    Devolve ``None`` quando a pergunta não é prospectiva ou quando nenhuma
    companhia foi resolvida — nos dois casos o fluxo normal segue. Nunca faz
    chamada externa: custo zero, sempre.
    """
    from src.cobertura import extrair_mencoes, resolver_entidade
    from src.normalizacao import ordinal_trimestre
    from src.projecao import (
        detectar_pergunta_prospectiva,
        recusa_de_ultimo_recurso,
        responder_projecao,
    )

    achado = detectar_pergunta_prospectiva(pergunta)
    if achado is None:
        return None
    recursos = carregar_rota_prospectiva()
    if recursos is None:
        # NÃO cai no fluxo normal. Antes caía, e a pergunta prospectiva
        # terminava no LLM — a rota "sumia" e a RN07 sumia junto. Artefato
        # ausente degrada a RIQUEZA da resposta, nunca a fronteira.
        saida = recusa_de_ultimo_recurso(
            achado, motivo="panorama ou painel indisponível nesta instância"
        )
        return {
            "resposta": saida.texto,
            "fontes": [],
            "modo": "rota prospectiva · RN07 degradada (nenhuma chamada externa)",
            "provedor": "—",
            "custo_usd": 0.0,
        }

    indice = recursos["indice"]
    mencoes = extrair_mencoes(pergunta, indice)
    if not mencoes:
        return None
    resolucao = resolver_entidade(mencoes[0], indice)
    if resolucao.ambigua:
        # RN11: nome que resolve para mais de uma companhia gera pergunta de
        # desambiguação, nunca escolha automática — inclusive aqui.
        return {
            "resposta": resolucao.pergunta_desambiguacao(),
            "fontes": [],
            "modo": "desambiguação (RN11, nenhuma chamada externa)",
            "provedor": "—",
            "custo_usd": 0.0,
        }
    companhia = resolucao.resolvida
    if companhia is None:
        return None

    # `sorted()` puro ordenaria como TEXTO e poria 1T2026 antes de 2T2025 —
    # a janela publicada sairia errada sem levantar erro nenhum.
    trimestres = tuple(
        sorted(
            indice.trimestres_painel.get(companhia.cd_cvm, ()),
            key=ordinal_trimestre,
        )
    )
    saida = responder_projecao(
        pergunta,
        denom_social=companhia.denom_social,
        cd_cvm=companhia.cd_cvm,
        trimestres_painel=trimestres,
        n_prejuizos=recursos["prejuizos"].get(companhia.cd_cvm),
        n_prejuizos_derivados=recursos["prejuizos_derivados"].get(
            companhia.cd_cvm
        ),
        ativo_total=recursos["ativos"].get(companhia.cd_cvm),
        panorama=recursos["panorama"],
        previsao_por_emissor_habilitada=config.previsao_por_emissor_habilitada,
        escores=recursos["escores"],
        achado=achado,
    )
    modo = (
        "rota prospectiva · modo local (escore por emissor exposto)"
        if saida.expos_escore_por_emissor
        else "rota prospectiva · RN07 (nenhuma chamada externa)"
    )
    return {
        "resposta": saida.texto,
        "fontes": [],
        "modo": modo,
        "provedor": "—",
        "custo_usd": 0.0,
        "rastro_projecao": saida.como_dicionario(),
    }


@st.cache_resource(show_spinner=False)
def carregar_rota_estruturada() -> dict | None:
    """Índice de cobertura + leitor do painel, para a rota sem LLM.

    Devolve ``None`` quando o painel não está nesta instância (deploy enxuto da
    RNF12): a rota some e o fluxo documental segue. Some inteira, de propósito
    — meia rota responderia cobertura sem número, que é pior que não responder.
    """
    from src.cobertura import carregar_indice_cobertura
    from src.dados_estruturados import abrir_conexao_somente_leitura
    from src.ferramentas import LeitorPainelDuckDB

    try:
        indice = carregar_indice_cobertura(config)
        # Abre e fecha o painel agora: sem isto, a ausência só apareceria na
        # primeira pergunta, já dentro do fluxo de resposta.
        abrir_conexao_somente_leitura(config).close()
        leitor = LeitorPainelDuckDB(config)
    except Exception as erro:  # painel ausente ou ilegível
        LOGGER.warning("rota estruturada desligada: %s", erro)
        return None
    return {"indice": indice, "leitor": leitor}


# Vocabulário que aponta para a camada DOCUMENTAL. O painel guarda o número
# CONTÁBIL arquivado na CVM; o release publica o número GERENCIAL, e os dois
# divergem de propósito — reconciliar essa divergência é o problema que o
# projeto existe para tratar, não algo a resolver escolhendo um lado calado.
# Medido em 2026-09-14: sem esta deferência a rota sequestrava 5 das 45
# congeladas, e em 3 delas devolvia número materialmente diferente do que a
# pergunta pedia (Santander 2T2025: R$ 1.928 mi contábil contra R$ 3.659 mi
# gerencial). Uma das 5 era adversarial, cuja resposta certa é recusar a
# premissa — respondê-la com um número é exatamente o defeito que a categoria
# adversarial existe para pegar.
# Radicais, não palavras inteiras: "gerencial" não é substring de "gerenciais",
# e a congelada que diz "Segundo os comentários gerenciais do BTG" escapava da
# lista por essa letra só.
_MARCAS_DA_CAMADA_DOCUMENTAL = (
    "release",
    "gerenci",
    "divulga",
    "reconcilia",
    "comparativ",
    "brgaap",
    "ifrs",
    "ajustad",
    "recorrente",
    "por que",
    "porque",
)


# Compactado em 2026-09-20: o aviso ocupava quatro linhas em negrito depois de
# toda resposta e competia com o número. O conteúdo que importa — este é o
# contábil arquivado, o gerencial do release pode divergir — cabe em uma linha.
AVISO_CONTABIL_E_GERENCIAL = (
    "_Número contábil arquivado na CVM (ITR/DFP). O release pode divulgar um "
    "gerencial diferente para o mesmo período; essa leitura não foi consultada "
    "aqui._"
)


def _pergunta_pede_a_camada_documental(pergunta: str) -> bool:
    """Verdadeiro quando o enunciado aponta para o release, não para o painel."""
    from src.normalizacao import remover_acentos

    texto = remover_acentos(pergunta or "").casefold()
    return any(marca in texto for marca in _MARCAS_DA_CAMADA_DOCUMENTAL)


def responder_estruturada_se_couber(pergunta: str) -> dict | None:
    """Responde do painel contábil da CVM, sem nenhuma chamada de LLM.

    Devolve ``None`` quando a pergunta não é do vocabulário contábil fechado —
    narrativa de release não se responde por SQL, e chutar aqui seria pior que
    encaminhar —, e também quando ela pede explicitamente a camada documental.
    Custo zero sempre, então não debita a cota da RN03.

    As guardas de entrada (RN05/RN06) e da RN07 moram AQUI DENTRO, e não só na
    ordem em que os chamadores as invocam: um chamador futuro não pode abrir a
    porta esquecendo de varrer antes (§3.6). "O lucro do banco X vai cair?"
    casa o conceito `lucro` e sairia daqui com números históricos.

    O que a guarda da RN07 NÃO cobre: ela tem o tamanho de
    `detectar_pergunta_prospectiva`. Paráfrases que o detector não casa
    ("qual o outlook de lucro do Itaú?", "o lucro tende a piorar?") atravessam
    e saem com tabela de fatos — 5 de 10 paráfrases na auditoria de
    2026-09-15. Lacuna do detector, registrada no §3.6, não resolvida aqui.
    """
    from src.cobertura import (
        ROTULO_CONCEITO,
        EstadoCobertura,
        formatar_reais,
        redigir_conversacional,
        responder_por_gabarito,
    )
    from src.normalizacao import extrair_periodos_citados
    from src.projecao import (
        detectar_pergunta_prospectiva,
        recusa_de_ultimo_recurso,
    )

    guarda = guardar_entrada(pergunta)
    if guarda.bloqueado:
        return {
            "resposta": texto_de_recusa(guarda),
            "fontes": [],
            "fatos": [],
            "citacoes": [],
            "modo": "painel CVM · recusa por guardrail no portão da consulta",
            "provedor": "—",
            "custo_usd": 0.0,
            "consumiu_chamada": False,
        }
    # RN06: daqui em diante só circula a forma anonimizada.
    pergunta = guarda.texto_seguro

    achado = detectar_pergunta_prospectiva(pergunta)
    if achado is not None:
        saida = recusa_de_ultimo_recurso(
            achado, motivo="rota prospectiva não atendeu esta pergunta"
        )
        return {
            "resposta": saida.texto,
            "fontes": [],
            "fatos": [],
            "citacoes": [],
            "modo": "painel CVM · RN07 no portão da consulta estruturada",
            "provedor": "—",
            "custo_usd": 0.0,
            "consumiu_chamada": False,
        }

    # Deferência à camada documental DEPOIS da RN07 (a fronteira nunca cede a
    # roteamento) e ANTES de abrir o painel: pergunta sobre release não vira
    # consulta contábil nem de leve.
    if _pergunta_pede_a_camada_documental(pergunta):
        return None

    recursos = carregar_rota_estruturada()
    if recursos is None:
        return None

    resposta = responder_por_gabarito(
        pergunta, recursos["indice"], recursos["leitor"]
    )
    # Encaminha ao fluxo documental o que o gabarito fixo não cobre. `parcial`
    # sozinho NÃO encaminha: cobertura `so_painel` é parcial por definição e é
    # justamente a metade verdadeira que a RN12 manda entregar.
    if (
        not resposta.fatos
        and not resposta.recusa
        and not resposta.precisa_desambiguacao
    ):
        return None

    # Pergunta sem período pedia UM número e recebia a série inteira — seis
    # trimestres que ninguém pediu, sem nem dizer que o período faltava. Mesma
    # decisão já tomada para a rota do plano (`PeriodoIndefinido`): perguntar de
    # volta, em uma frase. Só vale quando há mais de um trimestre a devolver;
    # companhia com um trimestre só no painel não tem ambiguidade a resolver.
    if (
        resposta.fatos
        and len(resposta.fatos) > 1
        and not extrair_periodos_citados(pergunta)
    ):
        return {
            "resposta": (
                "De qual período? O painel tem "
                + ", ".join(sorted({f.trimestre for f in resposta.fatos}))
                + " para essa consulta — diga o trimestre (ex.: 3T2025) ou o "
                "semestre (ex.: 2º semestre de 2025)."
            ),
            "fontes": [],
            "fatos": [],
            "citacoes": [],
            "modo": "painel CVM · período não informado (nenhuma chamada externa)",
            "provedor": "—",
            "custo_usd": 0.0,
            "consumiu_chamada": False,
        }

    if resposta.precisa_desambiguacao:
        modo = "painel CVM · desambiguação (RN11, nenhuma chamada externa)"
    elif resposta.recusa:
        modo = "painel CVM · recusa classificada (RN12, nenhuma chamada externa)"
    else:
        modo = "painel CVM · consulta estruturada (nenhuma chamada externa)"

    # A prosa do braço C descreve cobertura e repete companhia e conceito a cada
    # fato — formato do benchmark, não da tela. `redigir_conversacional` diz a
    # mesma evidência uma vez; a procedência da RN01 segue na tabela de fatos e
    # no expansor de citações, logo abaixo.
    texto = redigir_conversacional(resposta, pergunta)
    # Mitigação da lacuna da deferência (auditoria de 2026-09-15): paráfrase
    # que aponta o release sem casar radical ainda chega aqui. Quando a
    # companhia TEM release no corpus, a resposta declara que é o contábil e
    # que o gerencial não foi lido. Sem release (`so_painel`), a triagem da
    # RN12 já diz o que falta, e prometer um release inexistente seria falso.
    codigos_com_release = {
        triagem.cobertura.companhia.cd_cvm
        for triagem in resposta.triagens
        if triagem.cobertura is not None
        and triagem.cobertura.companhia is not None
        and triagem.cobertura.estado is EstadoCobertura.AMBAS
    }
    if any(fato.cd_cvm in codigos_com_release for fato in resposta.fatos):
        texto = f"{texto}\n\n{AVISO_CONTABIL_E_GERENCIAL}"

    return {
        "resposta": texto,
        "fontes": [],
        "fatos": [
            {
                "companhia": fato.denom_social,
                "cd_cvm": fato.cd_cvm,
                "trimestre": fato.trimestre,
                "conceito": ROTULO_CONCEITO.get(fato.conceito, fato.conceito),
                "valor_resumido": formatar_reais_legivel(fato.valor_reais),
                "valor": formatar_reais(fato.valor_reais),
                "origem": "derivado (RN10)" if fato.derivado else "arquivado",
            }
            for fato in resposta.fatos
        ],
        "citacoes": list(resposta.citacoes),
        "modo": modo,
        "provedor": "—",
        "custo_usd": 0.0,
        "consumiu_chamada": False,
    }


@st.cache_resource(show_spinner=False)
def _cache_de_celulas():
    """Cache de (companhia, conceito, trimestre) → linhas, comum às sessões.

    Compartilhar entre sessões é seguro e é o ponto: o conteúdo é número
    contábil público do painel, idêntico para todo mundo, e nada aqui depende
    de quem perguntou. Não há texto de usuário nem PII nesta estrutura — a
    chave é código CVM, conceito e trimestre, e o valor são linhas do painel.

    A validade é do ARQUIVO, não do tempo: `conferir_painel` esvazia tudo se o
    painel for reconstruído, o que um TTL não garantiria.
    """
    from src.plano_consulta import CacheDeCelulas, assinatura_painel

    return CacheDeCelulas(assinatura_painel(config.duckdb_path))


@st.cache_resource(show_spinner=False)
def _interprete_de_plano():
    """Só o provedor de LLM, sem o índice vetorial.

    `_pipeline_ao_vivo` materializa Chroma e BM25, que esta rota não usa: ela
    responde do painel. Carregar o índice aqui pagaria memória e tempo de
    abertura por uma consulta que nunca o consulta.
    """
    from src.geracao import fabricar_provedor_llm

    return fabricar_provedor_llm(config)


def responder_plano_se_couber(
    pergunta: str, orcamento_restante_usd: float | None = None
) -> dict | None:
    """Painel contábil com o LLM como INTÉRPRETE — uma chamada paga por consulta.

    Roda DEPOIS de `responder_estruturada_se_couber`, que cobre o vocabulário
    canônico de graça, e ANTES do fluxo documental. A ordem é a que gasta menos:
    quando o casador fixo resolve, nada é pago; quando ele não resolve, esta
    rota abre comparação, variação e paráfrase, que ele não alcança; e quando
    nem ela resolve, a pergunta segue para o corpus.

    Devolve ``None`` quando a pergunta não é desta rota — e aí o chamador
    encaminha ao corpus. Devolve recusa APRESENTÁVEL quando a pergunta é desta
    rota mas está incompleta (`RecusaDeReformulacao`): período ausente ou réguas
    misturadas não se resolvem no corpus, só reescrevendo, e mandar isso ao RAG
    devolveria uma resposta pior em vez de um pedido de esclarecimento.

    As guardas de entrada (RN05/RN06) e da RN07 moram AQUI DENTRO pelo mesmo
    motivo do §3.6: um chamador futuro não pode abrir a porta esquecendo de
    varrer antes. A guarda de saída também roda, porque o `motivo` da recusa é
    o único texto do modelo que chega à tela nesta rota.
    """
    from src.dados_estruturados import executar_sql
    from src.plano_consulta import (
        ErroDeIntencao,
        RecusaDeReformulacao,
        assinatura_painel,
        executar_plano,
        interpretar_plano,
        prompt_plano,
        redigir_resposta,
        validar_plano,
    )
    from src.intencao_consulta import _texto_json
    from src.projecao import detectar_pergunta_prospectiva, recusa_de_ultimo_recurso

    guarda = guardar_entrada(pergunta)
    if guarda.bloqueado:
        return _item_do_plano(
            texto_de_recusa(guarda),
            "painel CVM (plano) · recusa por guardrail no portão da consulta",
            consumiu_chamada=False,
        )
    pergunta = guarda.texto_seguro  # RN06: só a forma anonimizada circula

    achado = detectar_pergunta_prospectiva(pergunta)
    if achado is not None:
        saida = recusa_de_ultimo_recurso(
            achado, motivo="rota prospectiva não atendeu esta pergunta"
        )
        return _item_do_plano(
            saida.texto,
            "painel CVM (plano) · RN07 no portão da consulta",
            consumiu_chamada=False,
        )

    # Pergunta sobre release não vira consulta contábil, pela mesma razão da
    # rota determinística: o painel guarda o número arquivado, o release publica
    # o gerencial, e os dois divergem de propósito.
    if _pergunta_pede_a_camada_documental(pergunta):
        return None

    recursos = carregar_rota_estruturada()
    if recursos is None:
        return None
    try:
        provedor = _interprete_de_plano()
    except Exception as erro:  # sem chave configurada (RNF12): a rota some
        LOGGER.warning("intérprete de plano indisponível: %s", erro)
        return None

    prompt_sistema = prompt_plano()
    prompt_usuario = f"Pergunta: {pergunta}"
    saldo = _saldo_disponivel(orcamento_restante_usd)
    estimativa = provedor.estimar_custo_maximo(prompt_sistema, prompt_usuario)
    if estimativa is None or not math.isfinite(float(estimativa)):
        raise RuntimeError("O provedor não oferece estimativa auditável.")
    if float(estimativa) > saldo:
        raise RuntimeError("A próxima chamada excederia o orçamento da sessão.")

    resposta_llm = provedor.gerar(prompt_sistema, prompt_usuario, temperatura=0.0)
    custo = float(resposta_llm.uso.custo_usd or 0.0)
    try:
        bruto = interpretar_plano(_texto_json(resposta_llm.texto))
        plano = validar_plano(bruto, recursos["indice"], pergunta)
    except RecusaDeReformulacao as recusa:
        # Volta à tela: só quem perguntou resolve. A chamada foi paga, então a
        # cota conta — não cobrá-la faria a recusa sair de graça e convidaria o
        # laço de tentativas sobre o provedor.
        return _item_do_plano(
            f"**Preciso de mais um detalhe.** {recusa}",
            "painel CVM (plano) · pergunta incompleta",
            custo_usd=custo,
        )
    except ErroDeIntencao as erro:
        # Não é desta rota: o corpus documental pode ter. O custo já foi pago e
        # é devolvido para que o chamador o debite mesmo encaminhando.
        LOGGER.info("plano encaminhou ao corpus: %s", erro)
        return {"encaminhar": True, "custo_usd": custo}

    cache = _cache_de_celulas()
    cache.conferir_painel(assinatura_painel(config.duckdb_path))
    respondidas = executar_plano(
        plano,
        lambda sql: (
            lambda r: (r.colunas, r.linhas)
        )(executar_sql(sql, config, None)),
        cache,
    )
    return _item_do_plano(
        redigir_resposta(plano, respondidas),
        "painel CVM (plano interpretado) · SQL por template, aritmética em Python",
        custo_usd=custo,
        fatos=_fatos_do_plano(respondidas),
        provedor=f"{config.llm_provider}/{resposta_llm.modelo}",
    )


def _saldo_disponivel(orcamento_restante_usd: float | None) -> float:
    """Saldo efetivo desta chamada, nunca acima do teto da sessão."""
    informado = (
        config.orcamento_teto_usd
        if orcamento_restante_usd is None
        else orcamento_restante_usd
    )
    if (
        not isinstance(informado, (int, float))
        or isinstance(informado, bool)
        or not math.isfinite(float(informado))
        or informado < 0
    ):
        raise ValueError("Saldo de orçamento inválido.")
    return min(config.orcamento_teto_usd, float(informado))


def _item_do_plano(
    texto: str,
    modo: str,
    *,
    custo_usd: float = 0.0,
    fatos: list | None = None,
    provedor: str = "—",
    consumiu_chamada: bool = True,
) -> dict:
    """Empacota a saída da rota no formato que o histórico da interface lê.

    A guarda de saída roda aqui, e não só no fluxo documental: o `motivo` de uma
    recusa é texto que o modelo escreveu e que chega à tela sem passar por mais
    ninguém.
    """
    saida = avaliar_saida(
        texto,
        tuple(config.guardrails_ativos),
        presidio_habilitado=config.presidio_habilitado,
        presidio_idioma=config.presidio_idioma,
        presidio_modelo_spacy=config.presidio_modelo_spacy,
    )
    return {
        "resposta": texto_de_recusa(saida) if saida.bloqueado else saida.texto_seguro,
        "fontes": [],
        "fatos": fatos or [],
        "citacoes": [],
        "modo": modo,
        "provedor": provedor,
        "custo_usd": custo_usd,
        "consumiu_chamada": consumiu_chamada,
    }


def _fatos_do_plano(respondidas) -> list[dict]:
    """Tabela de evidência: uma linha por número, com procedência (RN10)."""
    from src.cobertura import ROTULO_CONCEITO, formatar_reais

    return [
        {
            "companhia": linha.denom_social,
            "cd_cvm": linha.cd_cvm,
            "trimestre": linha.trimestre,
            "conceito": ROTULO_CONCEITO.get(linha.conceito, linha.conceito),
            "valor_resumido": formatar_reais_legivel(linha.valor_reais),
            "valor": formatar_reais(linha.valor_reais),
            "origem": (
                "derivado (RN10)" if linha.origem != "arquivado" else "arquivado"
            )
            + (" · corrigido" if linha.corrigido else ""),
        }
        for respondida in respondidas
        for linha in respondida.linhas
    ]


def _mensagem_do_painel(item: dict) -> dict:
    """Converte a saída da rota estruturada na mensagem que o histórico lê."""
    return {
        "papel": "assistant",
        "conteudo": item["resposta"],
        "fontes": item.get("fontes", []),
        "fatos": item.get("fatos", []),
        "citacoes": item.get("citacoes", []),
        "modo": item["modo"],
        "provedor": item["provedor"],
        "streamar": True,
    }


def responder_sem_llm(pergunta: str) -> tuple[str, dict | None]:
    """Cadeia de custo zero: guardrails → RN07 → painel contábil.

    Devolve a pergunta na forma exibível (anonimizada, RN06) e a mensagem de
    resposta, ou ``None`` quando só a camada documental pode responder. É o que
    permite ao modo demonstração aceitar pergunta sem nenhum segredo
    configurado (RNF12), porque nenhuma etapa daqui chama provedor externo.
    """
    guarda = guardar_entrada(pergunta)
    if guarda.bloqueado:
        return guarda.texto_seguro, {
            "papel": "assistant",
            "conteudo": texto_de_recusa(guarda),
            "fontes": [],
            "modo": "recusa por guardrail (nenhuma chamada externa)",
            "provedor": "—",
            "streamar": True,
        }
    segura = guarda.texto_seguro

    item = _tentar_rota("prospectiva", responder_prospectiva_se_couber, segura)
    if item is None:
        item = _tentar_rota("estruturada", responder_estruturada_se_couber, segura)
    if item is None:
        return segura, None
    return segura, _mensagem_do_painel(item)


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


def _fontes_para_exibicao(recuperados, resposta) -> list[dict]:
    """Trechos recuperados, com os que a resposta CITOU primeiro e marcados.

    O top-k inteiro vai para a tela porque é o contexto que o modelo leu, mas
    nem todo trecho recuperado foi usado: no ensaio de 2026-09-18 o sumário do
    release do Itaú (págs. 1–5) aparecia como primeira fonte de uma resposta que
    citava a pág. 5 da tabela. A marca vem da citação que a RN01 já validou —
    documento e página —, nunca de similaridade de texto. Resposta recusada não
    tem citação, e aí nada é marcado.
    """
    citadas = (
        set()
        if getattr(resposta, "recusa", False)
        else {
            (c.documento, int(c.pagina))
            for c in (getattr(resposta, "citacoes", None) or ())
        }
    )
    fontes = []
    for r in recuperados:
        chunk = r.chunk
        citada = any(
            documento == chunk.documento
            and chunk.pagina_inicio <= pagina <= chunk.pagina_fim
            for documento, pagina in citadas
        )
        fontes.append(
            {
                "rotulo": (
                    ("✅ citado na resposta · " if citada else "")
                    + f"{chunk.empresa} · {chunk.documento} · "
                    f"págs. {chunk.pagina_inicio}–{chunk.pagina_fim}"
                ),
                "trecho": _redigir_para_exibicao(
                    _limpar_trecho_ocr(chunk.texto.split("\n", 1)[-1])
                )[:800],
                "citada": citada,
            }
        )
    # `sorted` é estável: dentro de cada grupo, a ordem do ranqueamento fica.
    return sorted(fontes, key=lambda fonte: not fonte["citada"])


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

    # Mesmo portão duplo, agora para a RN07. `responder_prospectiva_se_couber`
    # já atende a rota antes daqui, mas ela depende de artefato, de painel e de
    # o nome resolver no índice de cobertura — três coisas que podem faltar. Se
    # qualquer uma faltar e a guarda morasse só lá, a pergunta prospectiva
    # chegaria ao provedor e seria respondida de memória paramétrica.
    #
    # O detector dispara 0 vezes nas 55 congeladas (`TestFalsoBloqueio`), então
    # fechar aqui não custa falso bloqueio medido.
    from src.projecao import (
        detectar_pergunta_prospectiva,
        recusa_de_ultimo_recurso,
    )

    achado_projecao = detectar_pergunta_prospectiva(pergunta)
    if achado_projecao is not None:
        saida = recusa_de_ultimo_recurso(
            achado_projecao, motivo="rota prospectiva não atendeu esta pergunta"
        )
        return {
            "resposta": saida.texto,
            "fontes": [],
            "modo": "rota prospectiva · RN07 no portão do provedor",
            "provedor": "—",
            "custo_usd": 0.0,
            # A interface usa isto para NÃO debitar a cota da RN03: nenhuma
            # chamada foi feita, e cobrar uma pergunta livre por uma recusa de
            # custo zero é a mesma incoerência que o caminho do guardrail já
            # evita.
            "consumiu_chamada": False,
        }

    if config.embedding_provider not in {"ollama", "local"}:
        raise RuntimeError(
            "Perguntas livres exigem embeddings locais: o custo de embeddings "
            "externos ainda não integra o orçamento da sessão."
        )
    from src.indexacao import calcular_identidade_extracao

    identidade_extracao = calcular_identidade_extracao(config)
    # Etapa própria porque o pipeline é cacheado: a primeira consulta do
    # processo paga a carga do índice, e o trace precisa mostrar isso à parte.
    with observabilidade.etapa("pipeline.carregar"):
        recuperador, provedor_llm, estrategia = _pipeline_ao_vivo(
            identidade_extracao
        )
    if not getattr(provedor_llm, "custo_auditavel", True):
        raise RuntimeError(
            "O provedor não oferece estimativa auditável antes da chamada."
        )
    with observabilidade.etapa(
        "recuperacao",
        tipo="retriever",
        entrada=lambda: {
            "pergunta": observabilidade.texto_livre(pergunta),
            "estrategia": str(estrategia.value),
        },
    ) as etapa_recuperacao:
        recuperados = recuperador.recuperar(pergunta, estrategia)
        etapa_recuperacao.atualizar(
            saida=lambda: [
                {
                    "chunk": r.chunk.id,
                    "fonte": f"{r.chunk.empresa} · {r.chunk.documento} · "
                    f"{r.chunk.trimestre} · pág. {r.chunk.pagina_inicio}",
                    "tipo_bloco": r.chunk.tipo_bloco,
                    "score": round(float(r.score), 4),
                }
                for r in recuperados
            ]
        )
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
        # A chamada ao provedor abre a própria observação `generation`, com
        # tokens e custo (`ProvedorLLM.__init_subclass__`); esta etapa
        # envolve também o parse e as guardas RN01/RN02 que vêm depois dela.
        with observabilidade.etapa(
            "geracao", metadados={"estimativa_maxima_usd": float(estimativa)}
        ) as etapa_geracao:
            resposta, uso = gerar_resposta(
                pergunta,
                chunks,
                provedor_llm,
                config,
                modo_closed_book=modo_closed_book,
            )
            etapa_geracao.atualizar(
                saida=lambda: {
                    "recusa": resposta.recusa,
                    "motivo_recusa": resposta.motivo_recusa,
                    "citacoes": len(resposta.citacoes),
                    "custo_usd": uso.custo_usd,
                }
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
        with observabilidade.etapa("guardrail.saida", tipo="guardrail") as etapa_saida:
            saida = avaliar_saida(
                conteudo,
                tuple(config.guardrails_ativos),
                presidio_habilitado=config.presidio_habilitado,
                presidio_idioma=config.presidio_idioma,
                presidio_modelo_spacy=config.presidio_modelo_spacy,
            )
            etapa_saida.atualizar(saida=lambda: _resumo_guardrail(saida))
        conteudo = (
            texto_de_recusa(saida) if saida.bloqueado else saida.texto_seguro
        )
    except Exception as exc:
        raise FalhaConsultaAoVivo(custo_a_debitar_em_falha) from exc
    return {
        "resposta": conteudo,
        "fontes": _fontes_para_exibicao(recuperados, resposta),
        "custo_usd": float(uso.custo_usd),
        "modelo": uso.modelo,
    }


MODO_AGENTES = "Agentes (Investigador + Auditor)"

# Perguntas de exemplo do modo agentes. Cada uma exige mais de uma ferramenta,
# em ordem: é o que mostra a orquestração, e não um agente que responde a uma
# consulta só.
EXEMPLOS_AGENTES = (
    "Qual foi o lucro líquido do Banco Inter no 3T2025 e em que faixa de porte "
    "de ativo ele se encaixa no modelo preditivo de prejuízo?",
    "O que o release do Itaú diz sobre a margem financeira gerencial no 3T2025, "
    "e quanto o painel da CVM registra de lucro líquido no mesmo trimestre?",
    "Quantas companhias o modelo preditivo sinaliza no trimestre corrente, e com "
    "que AUC ele foi validado?",
)


_ICONE_DO_ESTADO = {"inicio": "⏳", "ok": "✅", "falhou": "⚠️"}


def observador_de_progresso(progresso):
    """Escreve cada ferramenta no `st.status` enquanto o agente trabalha.

    Mostra papel, ferramenta e desfecho, o mesmo que o rastro da resposta já
    mostra no fim; argumentos e resultados não aparecem. O início vira o
    rótulo do quadro e o fim vira uma linha.
    """

    def avisar(papel: str, ferramenta: str, estado: str) -> None:
        texto = f"{_papel_legivel(papel)} · `{ferramenta}`"
        if estado == "inicio":
            progresso.update(label=f"{texto} em andamento…")
        else:
            progresso.write(f"{_ICONE_DO_ESTADO.get(estado, '•')} {texto}")

    return avisar


def _papel_legivel(papel: str) -> str:
    return {"investigador": "Investigador", "auditor": "Auditor"}.get(papel, papel)


def responder_com_agentes(
    pergunta: str,
    orcamento_restante_usd: float | None = None,
    ao_chamar=None,
) -> dict:
    """Pergunta pelos agentes do produto: Investigador + Auditor (spec 5.9, §3.16).

    O Investigador responde com cinco ferramentas (cobertura, trechos do
    corpus no ChromaDB, painel da CVM no DuckDB, indicadores e o modelo
    preditivo lido do artefato agregado). O Auditor recebe só a afirmação e as
    citações e tenta derrubá-las com caixa própria. Guardrails, RN07 e RN01/RN02
    são os de `responder_com_guardrails`, verificados por código.

    Cada chamada de LLM passa por `ControleOrcamento` com o saldo da sessão como
    teto. O custo a debitar é o que esse controle confirmou, também quando a
    execução falha no meio: a chamada feita foi paga.
    """
    from src.agentes import (
        ControleOrcamento,
        fabrica_ferramentas_padrao,
        fabrica_llm_padrao,
        responder_com_guardrails,
    )
    from src.ferramentas import FERRAMENTAS_DO_PRODUTO

    pergunta = validar_pergunta_livre(pergunta)
    saldo = min(
        config.orcamento_teto_usd,
        config.orcamento_teto_usd
        if orcamento_restante_usd is None
        else float(orcamento_restante_usd),
    )
    if not math.isfinite(saldo) or saldo <= 0:
        raise RuntimeError("Sem saldo de orçamento na sessão.")
    # Índice, painel e recuperador vêm dos caches do app: sem isso cada agente
    # abriria o Chroma de novo, e a pergunta pagaria a carga duas vezes.
    rota = carregar_rota_estruturada() or {}
    recuperador = None
    try:
        from src.indexacao import calcular_identidade_extracao

        with observabilidade.etapa("pipeline.carregar"):
            recuperador, _, _ = _pipeline_ao_vivo(calcular_identidade_extracao(config))
    except Exception as exc:  # buscar_trechos devolve o erro ao agente
        LOGGER.warning("agentes sem recuperador pronto (tipo=%s).", type(exc).__name__)
    orcamento = ControleOrcamento(saldo)
    try:
        resposta = responder_com_guardrails(
            pergunta,
            config,
            fabrica_llm=fabrica_llm_padrao(config, orcamento),
            fabrica_ferramentas=fabrica_ferramentas_padrao(
                config,
                indice_cobertura=rota.get("indice"),
                recuperador=recuperador,
                leitor=rota.get("leitor"),
                nomes=FERRAMENTAS_DO_PRODUTO,
                ao_chamar=ao_chamar,
            ),
        )
    except Exception as exc:
        raise FalhaConsultaAoVivo(orcamento.acumulado_usd) from exc

    conteudo = resposta.resposta or "—"
    if resposta.citacoes and not resposta.recusa:
        conteudo += "\n\n" + "\n".join(f"> 📄 {c}" for c in resposta.citacoes)
    if resposta.veredito_auditor:
        conteudo += f"\n\n**Auditor:** {resposta.veredito_auditor.replace('_', ' ')}."
    rastro = [
        f"{_papel_legivel(c.papel)} · `{c.ferramenta}` · "
        + (f"falhou ({c.erro})" if c.erro else (c.resumo or "ok"))
        for c in resposta.chamadas
    ]
    return {
        "pergunta_exibida": resposta.pergunta,
        "resposta": _redigir_para_exibicao(conteudo),
        "rastro_agentes": rastro,
        "veredito_auditor": resposta.veredito_auditor,
        "custo_usd": float(orcamento.acumulado_usd),
        "consumiu_chamada": orcamento.chamadas > 0,
        "modo": "agentes · Investigador + Auditor",
        "provedor": f"{config.llm_provider}/{resposta.uso.modelo or '—'}",
    }


# --- Estado de sessão -------------------------------------------------------
if "historico" not in st.session_state:
    st.session_state.historico = []  # [{papel, conteudo, fontes, provedor, modo}]
if "perguntas_livres_usadas" not in st.session_state:
    st.session_state.perguntas_livres_usadas = 0
if "custo_usd_acumulado" not in st.session_state:
    st.session_state.custo_usd_acumulado = 0.0
if "id_sessao_rastro" not in st.session_state:
    # Agrupa os traces de uma sessão no Langfuse. Aleatório, sem nada do
    # usuário: a instância pública não tem login, e nem deve inventar um.
    st.session_state.id_sessao_rastro = uuid.uuid4().hex

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
cache_aguarda_auditoria = erro_cache is not None and _cache_aguarda_auditoria(
    erro_cache
)

if config.habilitar_perguntas_livres:
    aquecer_caminho_ao_vivo()

modo_livre_disponivel = (
    config.habilitar_perguntas_livres
    and st.session_state.perguntas_livres_usadas
    < config.limite_perguntas_livres_por_sessao
    and st.session_state.custo_usd_acumulado < config.orcamento_teto_usd
)
opcoes_modo = ["Demonstração (cacheado)"]
if config.habilitar_perguntas_livres:
    # Os agentes custam chamadas pagas, então ficam atrás do mesmo opt-in.
    opcoes_modo.extend(["Pergunta livre", MODO_AGENTES])
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
if not estado_observabilidade.ativo:
    _texto_observabilidade = f"desligada ({estado_observabilidade.motivo})."
elif estado_observabilidade.captura_texto:
    _texto_observabilidade = (
        "traces no Langfuse com latência, tokens e custo. Pergunta e resposta "
        "entram depois de anonimizadas pelo Presidio."
    )
else:
    _texto_observabilidade = (
        "traces no Langfuse com latência, tokens e custo. O texto da pergunta "
        "e da resposta fica fora: sem o Presidio, nome de pessoa não seria "
        "anonimizado."
    )
st.sidebar.caption("**Observabilidade:** " + _texto_observabilidade)
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
        # `pop`: a mensagem transmite uma vez, na primeira renderização depois
        # de ter sido produzida. Sem isso, todo rerun (clique, troca de modo)
        # reescreveria o histórico inteiro palavra por palavra.
        if msg.pop("streamar", False):
            st.write_stream(_fluxo_de_texto(_escapar_cifrao(msg["conteudo"])))
        else:
            st.markdown(_escapar_cifrao(msg["conteudo"]))
        if msg.get("fontes"):
            with st.expander(
                "Trechos recuperados — os marcados com ✅ foram citados na resposta"
            ):
                for fonte in msg["fontes"]:
                    if isinstance(fonte, dict):
                        st.markdown(
                            f"**{_escapar_cifrao(fonte.get('rotulo', 'Fonte'))}**"
                        )
                        st.caption(
                            _escapar_cifrao(
                                _redigir_para_exibicao(fonte.get("trecho", ""))
                            ).replace("\n", "  \n")
                        )
                    else:
                        st.markdown(
                            f"- {_escapar_cifrao(_redigir_para_exibicao(fonte))}"
                        )
        if msg.get("fatos"):
            st.dataframe(msg["fatos"], hide_index=True, width="stretch")
            if any("derivado" in f.get("origem", "") for f in msg["fatos"]):
                st.warning(
                    "Há valor **derivado** nesta resposta (RN10): o 4º "
                    "trimestre não existe como ITR e foi obtido por "
                    "DFP anual − ITR acumulado do 3T."
                )
        if msg.get("citacoes"):
            with st.expander("Procedência no painel da CVM (RN01)"):
                for citacao in msg["citacoes"]:
                    st.markdown(f"- {_escapar_cifrao(citacao)}")
        if msg.get("rastro_agentes"):
            with st.expander("Como os agentes chegaram aqui (ferramentas chamadas)"):
                for linha in msg["rastro_agentes"]:
                    st.markdown(f"- {_escapar_cifrao(linha)}")
        if msg.get("gabarito"):
            st.info(f"Gabarito verificado: {msg['gabarito']}")
        if msg.get("modo"):
            st.caption(f"modo: {msg['modo']} · provedor: {msg.get('provedor', '—')}")

# --- Uma consulta do chat ----------------------------------------------------
# Corpo do chat em função, para que o trace da consulta (5.12) feche ANTES do
# `st.rerun()`, que interrompe o script por exceção. A ordem das rotas é a de
# sempre, e `TestOrdemDasRotas` a confere aqui, depois do marcador do corpo.


def responder_no_chat(pergunta: str, rastro: observabilidade.Observacao) -> bool:
    """Atende uma pergunta do modo livre e diz se a tela deve recarregar."""
    try:
        guarda_entrada = guardar_entrada(validar_pergunta_livre(pergunta))
    except ValueError as exc:
        st.error(str(exc))
        return False
    # O trace recebe a pergunta só depois da varredura, já anonimizada, e só
    # se o Presidio estiver ligado; sem ele, só o tamanho (RN06).
    rastro.atualizar(entrada=observabilidade.texto_livre(guarda_entrada.texto_seguro))
    if guarda_entrada.bloqueado:
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
                "streamar": True,
            }
        )
        # Sem débito de cota nem de orçamento: a cota existe para conter
        # gasto, e recusar aqui não gastou nada. Debitá-la faria um falso
        # bloqueio custar ao usuário duas vezes.
        return True
    pergunta = guarda_entrada.texto_seguro
    # Rota prospectiva ANTES de qualquer chamada paga: ela responde de
    # artefato local, custa zero e não debita cota — pelo mesmo motivo da
    # recusa por guardrail acima.
    item_projecao = _tentar_rota(
        "prospectiva", responder_prospectiva_se_couber, pergunta
    )
    if item_projecao is not None:
        st.session_state.historico.append({"papel": "user", "conteudo": pergunta})
        st.session_state.historico.append(
            # `conteudo` é a chave que o laço de renderização lê; anexar só
            # `resposta` estourava KeyError no rerun e derrubava a página
            # inteira — a recusa da RN07 nunca chegava à tela.
            {
                "papel": "assistant",
                "conteudo": item_projecao["resposta"],
                "fontes": item_projecao.get("fontes", []),
                "modo": item_projecao["modo"],
                "provedor": item_projecao["provedor"],
                "streamar": True,
            }
        )
        return True
    # Painel contábil DEPOIS da guarda prospectiva e ANTES do provedor:
    # responde de SQL local, custo zero, sem debitar cota.
    item_painel = _tentar_rota(
        "estruturada", responder_estruturada_se_couber, pergunta
    )
    if item_painel is not None:
        st.session_state.historico.append({"papel": "user", "conteudo": pergunta})
        st.session_state.historico.append(_mensagem_do_painel(item_painel))
        return True
    # Painel com LLM-intérprete: DEPOIS do casador fixo (que é de graça) e
    # ANTES do corpus. Custa uma chamada, então debita cota e orçamento como
    # qualquer outra — inclusive quando encaminha, porque a chamada já foi paga.
    item_plano = _tentar_rota(
        "plano",
        responder_plano_se_couber,
        pergunta,
        orcamento_restante_usd=max(
            0.0, config.orcamento_teto_usd - st.session_state.custo_usd_acumulado
        ),
    )
    if item_plano is not None and item_plano.get("encaminhar"):
        # Não era desta rota; o corpus segue. O custo pago fica.
        st.session_state.custo_usd_acumulado += item_plano["custo_usd"]
        st.session_state.perguntas_livres_usadas += 1
        item_plano = None
    elif item_plano is not None:
        st.session_state.custo_usd_acumulado += item_plano["custo_usd"]
        if item_plano.get("consumiu_chamada", True):
            st.session_state.perguntas_livres_usadas += 1
        st.session_state.historico.append({"papel": "user", "conteudo": pergunta})
        st.session_state.historico.append(_mensagem_do_painel(item_plano))
        return True
    st.session_state.historico.append({"papel": "user", "conteudo": pergunta})
    try:
        item = responder_pergunta_livre(
            pergunta,
            orcamento_restante_usd=max(
                0.0,
                config.orcamento_teto_usd - st.session_state.custo_usd_acumulado,
            ),
        )
        st.session_state.custo_usd_acumulado += item["custo_usd"]
        # A cota da RN03 conta CHAMADA, não tentativa de digitar: o segundo
        # portão da RN07 recusa sem gastar e devolve `consumiu_chamada=False`.
        # Debitar ali cobraria da sessão uma pergunta que nunca chegou ao
        # provedor.
        if item.get("consumiu_chamada", True):
            st.session_state.perguntas_livres_usadas += 1
        st.session_state.historico.append(
            {
                "papel": "assistant",
                "conteudo": item["resposta"],
                "fontes": item.get("fontes", []),
                # Vinha escrito à mão como "inferência ao vivo" e `gemini/—`,
                # o que passou a MENTIR quando a recusa da RN07 sai daqui com
                # custo zero (spec 5.17 exige que a tela diga o modo e o
                # provedor reais).
                "modo": item.get("modo", "pergunta livre (inferência ao vivo)"),
                "provedor": item.get(
                    "provedor",
                    f"{config.llm_provider}/{item.get('modelo', '—')}",
                ),
                "streamar": True,
            }
        )
    except FalhaConsultaAoVivo as exc:
        # Falhou depois de reservar: a chamada foi tentada e paga, então a
        # cota conta.
        st.session_state.perguntas_livres_usadas += 1
        st.session_state.custo_usd_acumulado = _contabilizar_reserva_falha(
            st.session_state.custo_usd_acumulado,
            exc,
            config.orcamento_teto_usd,
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
                "streamar": True,
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
                "streamar": True,
            }
        )
    return True


def registrar_desfecho(rastro: observabilidade.Observacao, tamanho_antes: int) -> None:
    """Saída do trace: a resposta que a consulta pôs no histórico."""
    novas = st.session_state.historico[tamanho_antes:]
    resposta = next(
        (m for m in reversed(novas) if m.get("papel") == "assistant"), None
    )
    if resposta is None:
        return
    rastro.atualizar(
        saida=observabilidade.texto_livre(resposta.get("conteudo")),
        metadados=lambda: {
            "modo": resposta.get("modo"),
            "provedor": resposta.get("provedor"),
            "fontes": len(resposta.get("fontes") or []),
            "custo_acumulado_sessao_usd": round(
                float(st.session_state.custo_usd_acumulado), 6
            ),
        },
    )


def responder_no_chat_com_agentes(
    pergunta: str, rastro: observabilidade.Observacao, ao_chamar=None
) -> bool:
    """Atende uma pergunta do modo agentes e diz se a tela deve recarregar.

    Cota e orçamento seguem a regra do modo livre: debita o que foi pago,
    inclusive numa falha depois de ter chamado o modelo, e não debita a cota
    quando nada chegou ao provedor (guardrail ou RN07 barraram antes).
    """
    try:
        texto = validar_pergunta_livre(pergunta)
    except ValueError as exc:
        st.error(str(exc))
        return False
    try:
        item = responder_com_agentes(
            texto,
            orcamento_restante_usd=max(
                0.0, config.orcamento_teto_usd - st.session_state.custo_usd_acumulado
            ),
            ao_chamar=ao_chamar,
        )
    except FalhaConsultaAoVivo as exc:
        st.session_state.custo_usd_acumulado = _contabilizar_reserva_falha(
            st.session_state.custo_usd_acumulado, exc, config.orcamento_teto_usd
        )
        if exc.custo_reservado_usd > 0:
            st.session_state.perguntas_livres_usadas += 1
        LOGGER.warning(
            "Agentes falharam de forma segura (tipo=%s).", type(exc.__cause__).__name__
        )
        # A pergunta crua não vai para o histórico: sem a resposta dos agentes
        # não há o texto anonimizado, e a RN06 vale para a tela também.
        st.session_state.historico.append(
            {
                "papel": "assistant",
                "conteudo": (
                    "A consulta aos agentes falhou de forma segura. Nenhuma "
                    "resposta financeira foi apresentada; o custo já incorrido "
                    "foi debitado. Tente de novo ou use o modo pergunta livre."
                ),
                "fontes": [],
                "modo": "agentes (falha segura)",
                "provedor": config.llm_provider,
                "streamar": True,
            }
        )
        return True
    except Exception as exc:
        LOGGER.warning("Agentes indisponíveis (tipo=%s).", type(exc).__name__)
        st.error("Os agentes não estão disponíveis nesta instância.")
        return False
    rastro.atualizar(entrada=observabilidade.texto_livre(item["pergunta_exibida"]))
    st.session_state.custo_usd_acumulado += item["custo_usd"]
    if item["consumiu_chamada"]:
        st.session_state.perguntas_livres_usadas += 1
    st.session_state.historico.append(
        {"papel": "user", "conteudo": item["pergunta_exibida"]}
    )
    st.session_state.historico.append(
        {
            "papel": "assistant",
            "conteudo": item["resposta"],
            "rastro_agentes": item["rastro_agentes"],
            "fontes": [],
            "modo": item["modo"],
            "provedor": item["provedor"],
            "streamar": True,
        }
    )
    return True


if modo == "Demonstração (cacheado)":
    if cache_aguarda_auditoria:
        st.warning(
            "**Respostas pré-computadas: aguardando auditoria humana.** Ainda "
            "não há cache final validado: o conjunto de teste congelado já foi "
            "avaliado, mas as respostas só aparecem aqui depois da conferência "
            "manual de fundamentação — é a trava que impede publicar resposta "
            "não auditada. Enquanto isso, consulte o painel contábil abaixo ou "
            "use o modo **Pergunta livre**."
        )
    elif erro_cache:
        st.error(f"Cache de demonstração inválido: {erro_cache}")
    elif not cache_demo:
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
                    "streamar": True,
                }
            )
            st.rerun()

    # Consulta ao painel contábil da CVM: sem LLM, sem segredo e sem custo, o
    # que a torna elegível ao modo demonstração (RNF12). O cache de respostas
    # pode estar travado pela auditoria pendente e esta consulta segue de pé —
    # ela não depende da rodada congelada.
    if carregar_rota_estruturada() is None:
        st.info(
            "O painel contábil da CVM não está disponível nesta instância, "
            "então a consulta a dados estruturados está desligada."
        )
    else:
        with st.expander("O que dá para perguntar ao painel contábil"):
            st.markdown(
                "Este canal lê os formulários **ITR/DFP arquivados na CVM** — "
                "não os releases. Ele responde valor por companhia e "
                "trimestre, sem chamar modelo de linguagem e sem custo:\n\n"
                "- `Qual foi o lucro líquido do Itaú no 3T2025?`\n"
                "- `Qual o lucro líquido consolidado do Banco do Brasil no "
                "4T2025?` — vem **marcado como derivado**, porque o 4º "
                "trimestre não existe como ITR\n"
                "- `Qual foi o lucro do Banco Inter no 3T2025?` — está no "
                "painel do regulador e **fora** do corpus de releases; o "
                "sistema entrega o número e declara o que falta\n"
                "- `Qual foi o lucro do Nubank no 3T2025?` — **recusa**, "
                "dizendo por quê\n\n"
                "Conceitos reconhecidos: lucro líquido (controladores ou "
                "consolidado), patrimônio líquido, ativo total e receita de "
                "intermediação financeira. Narrativa de release — *por que* "
                "algo variou — exige o modo pergunta livre."
            )
        pergunta_painel = st.chat_input(
            "Consulte o painel contábil da CVM (ex.: lucro líquido do Banco "
            "do Brasil no 4T2025)",
            key="entrada_painel",
        )
        if pergunta_painel:
            try:
                texto = validar_pergunta_livre(pergunta_painel)
            except ValueError as exc:
                st.error(str(exc))
                texto = None
            if texto is not None:
                tamanho_antes = len(st.session_state.historico)
                with observabilidade.consulta(
                    "painel_cvm",
                    sessao=st.session_state.id_sessao_rastro,
                    tags=("painel_cvm",),
                ) as rastro:
                    exibida, mensagem = responder_sem_llm(texto)
                    rastro.atualizar(entrada=observabilidade.texto_livre(exibida))
                    st.session_state.historico.append(
                        {"papel": "user", "conteudo": exibida}
                    )
                    st.session_state.historico.append(
                        mensagem
                        if mensagem is not None
                        else {
                            "papel": "assistant",
                            "conteudo": (
                                "Esta pergunta depende da leitura dos releases, "
                                "que exige o modo **pergunta livre**. O painel "
                                "contábil responde valor por companhia e "
                                "trimestre: lucro líquido, patrimônio líquido, "
                                "ativo total e receita de intermediação "
                                "financeira."
                            ),
                            "fontes": [],
                            "modo": "painel CVM · fora do vocabulário contábil",
                            "provedor": "—",
                            "streamar": True,
                        }
                    )
                    registrar_desfecho(rastro, tamanho_antes)
                st.rerun()
elif modo == MODO_AGENTES:
    with st.expander("Como funcionam os agentes, e o que perguntar"):
        st.markdown(
            "Dois agentes trabalham em sequência. O **Investigador** responde "
            "com ferramentas: os releases indexados (ChromaDB), o painel "
            "contábil da CVM (DuckDB), os indicadores e o **modelo preditivo "
            "de prejuízo**, lido do artefato agregado. O **Auditor** recebe só "
            "a afirmação e as citações, sem o raciocínio do Investigador, e "
            "refaz as consultas para confirmar, contestar ou dizer que não "
            "reproduz. Cada resposta custa algumas chamadas ao modelo de "
            "linguagem.\n\nPerguntas que exigem mais de uma ferramenta:\n\n"
            + "\n".join(f"- `{exemplo}`" for exemplo in EXEMPLOS_AGENTES)
        )
    pergunta = st.chat_input(
        "Pergunte aos agentes (ex.: lucro do Banco Inter no 3T2025 e a faixa "
        "de porte no modelo preditivo)",
        key="entrada_agentes",
    )
    if pergunta:
        if not modo_livre_disponivel:
            st.error(
                "Perguntas livres estão desabilitadas ou o limite da sessão foi "
                "atingido. O modo demonstração continua disponível."
            )
        else:
            tamanho_antes = len(st.session_state.historico)
            with observabilidade.consulta(
                "agentes",
                sessao=st.session_state.id_sessao_rastro,
                tags=("agentes", config.llm_provider),
            ) as rastro:
                with st.status(
                    "Investigador e Auditor trabalhando…", expanded=True
                ) as progresso:
                    recarregar = responder_no_chat_com_agentes(
                        pergunta, rastro, ao_chamar=observador_de_progresso(progresso)
                    )
                    progresso.update(
                        label="Investigador e Auditor terminaram.",
                        state="complete",
                        expanded=False,
                    )
                registrar_desfecho(rastro, tamanho_antes)
            if recarregar:
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
            tamanho_antes = len(st.session_state.historico)
            with observabilidade.consulta(
                "pergunta_livre",
                sessao=st.session_state.id_sessao_rastro,
                tags=("pergunta_livre", config.llm_provider),
            ) as rastro:
                recarregar = responder_no_chat(pergunta, rastro)
                registrar_desfecho(rastro, tamanho_antes)
            if recarregar:
                st.rerun()
