"""Camada de segurança: PII, injeção de prompt e tópico proibido (spec 5.11).

Três scanners, três motivos distintos de bloquear, e **nenhum deles confiado ao
modelo** — a RN05 e a RN06 são verificadas por código, como toda regra de
negócio deste projeto.

- **PII (RN06).** O que o usuário digita é anonimizado ANTES de qualquer
  chamada externa, e a forma anonimizada é a única que entra em log, trace ou
  cache. Reconhecedores em `src.reconhecedores_br`, com dígito verificador —
  ver lá por que a forma sozinha não basta.
- **Tópico proibido (RN05).** Recomendação de investimento, preço-alvo e
  aconselhamento pessoal ficam fora. Cada subtipo mapeia à sua âncora legal:
  **Res. CVM 20/2021** para atividade de analista (recomendar, precificar,
  classificar) e **Res. CVM 19/2021** para consultoria (aconselhar uma pessoa
  determinada sobre a carteira dela).
- **Injeção de prompt.** Padrões determinísticos aqui; o Llama Prompt Guard 2
  entra atrás da mesma interface quando os pesos estiverem embutidos na
  imagem. `HF_TOKEN` é segredo de **build**, nunca de runtime — se o contêiner
  precisar de token para subir, a RNF12 está quebrada.

**Falso bloqueio é defeito, não zelo.** A meta declarada da etapa 14 é zero
bloqueio indevido nas 45 perguntas legítimas congeladas. Por isso todo padrão
aqui é escrito para exigir o VERBO da conduta proibida, não o assunto: "qual
foi o lucro" e "qual o preço-alvo" falam ambos de dinheiro, e só o segundo é
atividade regulada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from src.normalizacao import remover_acentos
from src.reconhecedores_br import EntidadePII, encontrar_entidades


# --- Vocabulário de decisão ------------------------------------------------

SCANNER_PII = "pii"
SCANNER_TOPICO = "topico_proibido"
SCANNER_INJECAO = "injection"

RESOLUCAO_ANALISE = "Resolução CVM 20/2021"
RESOLUCAO_CONSULTORIA = "Resolução CVM 19/2021"

SUBTIPO_RECOMENDACAO = "recomendacao"
SUBTIPO_PRECO_ALVO = "preco_alvo"
SUBTIPO_CONSULTORIA = "consultoria_pessoal"

# Cada subtipo declara a norma que o proíbe. Guardar isso em código, e não no
# prompt, é o que permite a interface explicar a recusa citando a resolução.
ANCORA_LEGAL: dict[str, str] = {
    SUBTIPO_RECOMENDACAO: RESOLUCAO_ANALISE,
    SUBTIPO_PRECO_ALVO: RESOLUCAO_ANALISE,
    SUBTIPO_CONSULTORIA: RESOLUCAO_CONSULTORIA,
}


@dataclass(frozen=True)
class Achado:
    """Uma razão para bloquear, com o rastro que a justifica."""

    scanner: str
    subtipo: str
    detalhe: str
    ancora_legal: str = ""


@dataclass(frozen=True)
class ResultadoGuardrail:
    """Veredito do conjunto de scanners sobre um texto.

    ``texto_seguro`` é o que pode seguir para o provedor externo e para o log:
    já anonimizado, sempre — inclusive quando ``bloqueado`` é falso.
    """

    bloqueado: bool
    texto_seguro: str
    achados: tuple[Achado, ...] = ()
    entidades_pii: tuple[EntidadePII, ...] = field(default=())

    @property
    def motivo(self) -> str:
        if not self.achados:
            return ""
        primeiro = self.achados[0]
        if primeiro.ancora_legal:
            return (
                f"{primeiro.detalhe} (fora do escopo pela "
                f"{primeiro.ancora_legal})"
            )
        return primeiro.detalhe


# --- PII (RN06) ------------------------------------------------------------


def _substituir_entidades(
    texto: str, entidades: tuple[EntidadePII, ...]
) -> str:
    """Substitui de trás para frente para que os índices das ocorrências
    anteriores continuem válidos durante a troca."""
    saida = texto
    for entidade in reversed(entidades):
        saida = (
            saida[: entidade.inicio]
            + f"[{entidade.tipo} ANONIMIZADO]"
            + saida[entidade.fim :]
        )
    return saida


def anonimizar(
    texto: str,
    *,
    presidio_habilitado: bool = False,
    presidio_idioma: str = "pt",
    presidio_modelo_spacy: str = "pt_core_news_md",
) -> tuple[str, tuple[EntidadePII, ...]]:
    """Substitui cada identificador por um marcador do seu tipo.

    ``presidio_habilitado=False`` (padrão) usa só os reconhecedores por
    regex/dígito verificador de `src.reconhecedores_br` — rápidos, sem
    dependência pesada, é o que mantém o modo demonstração de pé sem nenhum
    modelo baixado (RNF12).

    ``presidio_habilitado=True`` funde o NER de nome de pessoa do Presidio
    (spec 5.11) por cima — reconhecedor ADICIONAL, não substituto — e falha
    fechado (`PresidioIndisponivelError`) se o pacote ou o modelo faltarem,
    porque ligar a flag é decisão explícita, não degradação silenciosa
    (RNF03).
    """
    from src.reconhecedores_br import combinar_sem_sobreposicao

    achados = list(encontrar_entidades(texto))
    if presidio_habilitado:
        from src.reconhecedor_presidio import entidades_presidio

        achados += entidades_presidio(
            texto,
            idioma=presidio_idioma,
            modelo_spacy=presidio_modelo_spacy,
        )
    entidades = tuple(combinar_sem_sobreposicao(achados))
    if not entidades:
        return texto, ()
    return _substituir_entidades(texto, entidades), entidades


# --- Tópico proibido (RN05) ------------------------------------------------

# Recomendar comprar/vender/manter — atividade de analista (Res. CVM 20/2021).
_PADRAO_RECOMENDACAO = re.compile(
    r"\b(?:"
    r"recomend\w*|indic(?:a|e|ar|aria)\s+(?:a\s+)?(?:compra|venda|acao|ativo)|"
    r"vale\s+a\s+pena\s+(?:comprar|vender|investir)|"
    r"(?:devo|deveria|posso)\s+(?:eu\s+)?(?:comprar|vender|investir|aplicar)|"
    r"compr(?:o|ar)\s+ou\s+(?:vend|nao)\w*|"
    r"melhor\s+(?:acao|ativo|investimento|papel)\s+para\s+(?:comprar|investir)|"
    r"vale\s+investir"
    r")\b"
)
# Precificar/classificar — também atividade de analista.
_PADRAO_PRECO_ALVO = re.compile(
    r"\b(?:"
    r"preco[-\s]?alvo|target\s+price|"
    r"(?:qual|quanto)\s+(?:sera|vai\s+ser|ficara)\s+(?:o\s+)?preco|"
    # O sujeito costuma vir entre o "quanto" e o verbo ("quanto a ação do BTG
    # vai subir"), então a janela precisa admitir o intervalo. O gatilho
    # continua sendo o par verbo-de-futuro + movimento de preço, nunca o
    # assunto: "quanto foi o lucro" não casa com nenhuma alternativa.
    r"quanto\s+(?:\S+\s+){0,5}?(?:vai|ira|deve|podera)\s+"
    r"(?:subir|cair|valorizar|desvalorizar|render|retornar)|"
    r"(?:acao|acoes|cotacao|papel)\s+(?:\S+\s+){0,4}?"
    r"(?:vai|ira|deve|podera)\s+(?:subir|cair|valorizar|desvalorizar)|"
    r"projec\w*\s+de\s+(?:preco|cotacao)|"
    r"(?:rating|classificacao)\s+(?:de\s+)?(?:compra|venda|neutro)|"
    r"esta\s+(?:barata|cara|subvalorizada|sobrevalorizada)"
    r")\b"
)
# Aconselhamento a uma pessoa determinada — consultoria (Res. CVM 19/2021).
_PADRAO_CONSULTORIA = re.compile(
    r"\b(?:"
    r"minha\s+carteira|meu\s+portfolio|meus?\s+investimentos?|"
    r"(?:monte|montar|sugira|sugerir)\s+(?:uma\s+)?carteira|"
    r"meu\s+perfil\s+(?:de\s+)?(?:investidor|risco)|"
    r"onde\s+(?:eu\s+)?(?:devo|deveria)\s+(?:investir|aplicar|colocar)|"
    r"quanto\s+(?:eu\s+)?(?:devo|deveria)\s+(?:investir|aplicar)|"
    r"tenho\s+R\$\s?[\d.,]+\s+para\s+investir"
    r")\b"
)

_PADROES_TOPICO: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        _PADRAO_CONSULTORIA,
        SUBTIPO_CONSULTORIA,
        "pedido de aconselhamento pessoal de investimento",
    ),
    (
        _PADRAO_PRECO_ALVO,
        SUBTIPO_PRECO_ALVO,
        "pedido de preço-alvo, projeção de preço ou classificação",
    ),
    (
        _PADRAO_RECOMENDACAO,
        SUBTIPO_RECOMENDACAO,
        "pedido de recomendação de compra, venda ou manutenção",
    ),
)


def detectar_topico_proibido(texto: str) -> Achado | None:
    """Primeiro subtipo proibido encontrado, ou ``None``.

    A ordem é do mais específico para o mais genérico: "onde devo investir" é
    consultoria antes de ser recomendação, e a âncora legal muda com isso.
    """
    if not isinstance(texto, str) or not texto:
        return None
    normalizado = remover_acentos(texto).casefold()
    for padrao, subtipo, detalhe in _PADROES_TOPICO:
        casamento = padrao.search(normalizado)
        if casamento:
            return Achado(
                scanner=SCANNER_TOPICO,
                subtipo=subtipo,
                detalhe=detalhe,
                ancora_legal=ANCORA_LEGAL[subtipo],
            )
    return None


# --- Injeção de prompt -----------------------------------------------------

_PADROES_INJECAO: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:ignore|ignora|desconsidere|esqueca)\s+(?:todas?\s+)?"
            r"(?:as\s+)?(?:instru\w*|regras?|orienta\w*|mensagens?)"
        ),
        "pedido de ignorar instruções anteriores",
    ),
    (
        re.compile(
            r"\b(?:voce\s+agora\s+e|aja\s+como|finja\s+ser|assuma\s+o\s+papel|"
            r"a\s+partir\s+de\s+agora\s+voce)\b"
        ),
        "tentativa de redefinir o papel do sistema",
    ),
    (
        re.compile(
            # Determinantes encadeados ("o seu system prompt") são a forma
            # natural do pedido; aceitar só um artigo deixava o ataque passar.
            r"\b(?:revele|mostre|imprima|repita|liste|qual\s+e)\s+"
            r"(?:(?:o|a|os|as|seu|sua|seus|suas)\s+){0,3}"
            r"(?:prompt|system\s+prompt|instru\w*\s+(?:do\s+sistema|que\s+voce)|"
            r"regras\s+internas)"
        ),
        "tentativa de extrair o prompt do sistema",
    ),
    (
        re.compile(
            r"\b(?:sem\s+(?:as\s+)?restric\w*|sem\s+filtro|modo\s+desenvolvedor|"
            r"developer\s+mode|jailbreak|dan\s+mode)\b"
        ),
        "pedido de operar sem restrições",
    ),
    (
        re.compile(r"</?(?:system|assistant|user)>|\[/?INST\]|<\|im_start\|>"),
        "marcador de turno de conversa embutido no texto",
    ),
)


def detectar_injecao(texto: str) -> Achado | None:
    """Detector determinístico de injeção.

    O Llama Prompt Guard 2 (spec 5.11) cobre o que padrão fixo não pega —
    paráfrase, outro idioma, ofuscação. Ele entra como scanner adicional; este
    continua valendo sem ele, porque o modo demonstração precisa subir sem
    nenhum modelo baixado (RNF12).
    """
    if not isinstance(texto, str) or not texto:
        return None
    normalizado = remover_acentos(texto).casefold()
    for padrao, detalhe in _PADROES_INJECAO:
        if padrao.search(normalizado):
            return Achado(
                scanner=SCANNER_INJECAO,
                subtipo="injecao_prompt",
                detalhe=detalhe,
            )
    return None


# --- Orquestração ----------------------------------------------------------


def avaliar_entrada(
    texto: str,
    scanners_ativos: tuple[str, ...] | None = None,
    *,
    presidio_habilitado: bool = False,
    presidio_idioma: str = "pt",
    presidio_modelo_spacy: str = "pt_core_news_md",
    prompt_guard_habilitado: bool = False,
    prompt_guard_modelo: str = "",
    prompt_guard_revisao: str = "",
    prompt_guard_limiar: float = 0.85,
) -> ResultadoGuardrail:
    """Aplica os scanners configurados e devolve o veredito.

    ``scanners_ativos`` espelha `Config.guardrails_ativos`. Um scanner desligado
    não roda — e é por isso que a configuração é validada em `src.config`:
    desligar por engano é decisão, não acidente.

    **PII nunca bloqueia.** Um CPF na pergunta não é ataque; é dado que não pode
    vazar. Ele é anonimizado e a pergunta segue. Bloquear aqui transformaria a
    proteção do usuário em recusa de atendimento.
    """
    ativos = (
        (SCANNER_INJECAO, SCANNER_TOPICO, SCANNER_PII)
        if scanners_ativos is None
        else tuple(scanners_ativos)
    )
    entidades: tuple[EntidadePII, ...] = ()
    texto_seguro = texto if isinstance(texto, str) else ""
    if SCANNER_PII in ativos:
        texto_seguro, entidades = anonimizar(
            texto_seguro,
            presidio_habilitado=presidio_habilitado,
            presidio_idioma=presidio_idioma,
            presidio_modelo_spacy=presidio_modelo_spacy,
        )

    achados: list[Achado] = []
    # A varredura de conduta roda sobre o texto ANONIMIZADO: o marcador
    # `[CPF ANONIMIZADO]` não introduz nem apaga verbo de recomendação, e assim
    # nenhum scanner enxerga o dado pessoal original.
    if SCANNER_INJECAO in ativos:
        achado = detectar_injecao(texto_seguro)
        if achado is None and prompt_guard_habilitado:
            # Só chama o classificador quando o regex NÃO achou nada — mesmo
            # resultado, sem pagar a inferência duas vezes. A composição é OR:
            # cada um cobre o que o outro não pega (ver src.prompt_guard).
            from src.prompt_guard import avaliar_injecao_ml

            kwargs = {"limiar": prompt_guard_limiar}
            if prompt_guard_modelo:
                kwargs["modelo"] = prompt_guard_modelo
            if prompt_guard_revisao:
                kwargs["revisao"] = prompt_guard_revisao
            achado = avaliar_injecao_ml(texto_seguro, **kwargs)
        if achado:
            achados.append(achado)
    if SCANNER_TOPICO in ativos:
        achado = detectar_topico_proibido(texto_seguro)
        if achado:
            achados.append(achado)
    return ResultadoGuardrail(
        bloqueado=bool(achados),
        texto_seguro=texto_seguro,
        achados=tuple(achados),
        entidades_pii=entidades,
    )


def texto_de_recusa(resultado: ResultadoGuardrail) -> str:
    """Mensagem publicável de uma recusa por guardrail.

    Vive aqui, e não na interface, porque a recusa precisa sair igual pelos dois
    caminhos que a produzem — o Streamlit e a camada de agentes. Uma recusa por
    conduta regulada **cita a resolução** e diz o que o assistente faz em vez
    disso: recusar sem oferecer a alternativa legítima é o que transforma
    guardrail em atrito.
    """
    if not resultado.achados:
        return ""
    achado = resultado.achados[0]
    if achado.scanner == SCANNER_TOPICO:
        return (
            f"**Fora do escopo.** Esta pergunta é {achado.detalhe}, atividade "
            f"regulada pela {achado.ancora_legal} — o assistente relata o que "
            "os documentos publicados informam e não emite juízo de "
            "investimento.\n\n"
            "Posso responder, por exemplo, qual foi a métrica no trimestre, "
            "em que página do release ela aparece e como ela variou."
        )
    if achado.scanner == SCANNER_INJECAO:
        return (
            "**Pedido não processado.** A mensagem contém "
            f"{achado.detalhe}. As instruções do sistema não são alteráveis "
            "por quem pergunta.\n\n"
            "Reformule como pergunta sobre os releases do corpus."
        )
    return achado.detalhe


def avaliar_saida(
    texto: str,
    scanners_ativos: tuple[str, ...] | None = None,
    *,
    presidio_habilitado: bool = False,
    presidio_idioma: str = "pt",
    presidio_modelo_spacy: str = "pt_core_news_md",
) -> ResultadoGuardrail:
    """Guarda de saída: o modelo não publica o que a entrada não podia pedir.

    Mesmo com a entrada limpa, a resposta pode escorregar para recomendação
    ("portanto, é um bom momento para comprar"). A RN05 vale nos dois sentidos,
    e a injeção não é verificada aqui — ela é ataque de entrada.
    """
    ativos = (
        (SCANNER_TOPICO, SCANNER_PII)
        if scanners_ativos is None
        else tuple(scanners_ativos)
    )
    entidades: tuple[EntidadePII, ...] = ()
    texto_seguro = texto if isinstance(texto, str) else ""
    if SCANNER_PII in ativos:
        texto_seguro, entidades = anonimizar(
            texto_seguro,
            presidio_habilitado=presidio_habilitado,
            presidio_idioma=presidio_idioma,
            presidio_modelo_spacy=presidio_modelo_spacy,
        )
    achados: list[Achado] = []
    if SCANNER_TOPICO in ativos:
        achado = detectar_topico_proibido(texto_seguro)
        if achado:
            achados.append(achado)
    return ResultadoGuardrail(
        bloqueado=bool(achados),
        texto_seguro=texto_seguro,
        achados=tuple(achados),
        entidades_pii=entidades,
    )
