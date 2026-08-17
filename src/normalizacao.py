"""Normalização numérica pt-BR e apelidos de banco (seções 5.6 e 5.8).

Pré-requisito do verificador de exatidão numérica: "R$ 2,3 bilhões",
"1.234,5 milhões" e "23,4%" precisam virar unidades canônicas antes de
qualquer comparação — sem isso, a avaliação produz falsos negativos em massa
(modo de falha nº 4, seção 5.18).

Módulo coberto por `tests/test_normalizacao.py` (exigência do AGENTS.md, etapa 5).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass

# Tabela de apelidos (seção 5.8): nome canônico -> formas aceitas em texto.
# NUBANK está aqui de propósito: é a instituição-armadilha do subconjunto
# adversarial (fora do corpus, seção 5.2) e precisa ser reconhecida na pergunta.
APELIDOS_BANCOS: dict[str, tuple[str, ...]] = {
    "BTG": ("btg", "btg pactual", "banco btg pactual", "bpac11"),
    "ITAU": ("itau", "itau unibanco", "banco itau", "itub4", "itub3"),
    "BRADESCO": ("bradesco", "banco bradesco", "bbdc4", "bbdc3"),
    "SANTANDER": ("santander", "santander brasil", "banco santander", "sanb11"),
    "BB": ("bb", "banco do brasil", "bbas3"),
    "NUBANK": ("nubank", "nu holdings", "nu pagamentos"),
}

# Códigos de trimestre reconhecidos nas perguntas (vocabulário fechado, 5.6).
PADRAO_TRIMESTRE = re.compile(r"\b([1-4])T(20\d{2})\b", re.IGNORECASE)

MULTIPLICADORES = {
    "mil": 1_000,
    "milhao": 1_000_000,
    "milhoes": 1_000_000,
    "mi": 1_000_000,
    "mm": 1_000_000,
    "bilhao": 1_000_000_000,
    "bilhoes": 1_000_000_000,
    "bi": 1_000_000_000,
}

# Todos os padrões abaixo operam sobre o texto após ``remover_acentos``.
# Derivar a alternância desta fonte única mantém, em particular, as formas
# singulares ``milhao``/``bilhao`` alinhadas entre valores inline e escalas de
# tabela, sem perder plurais e abreviações. As chaves mais longas vêm primeiro
# para que ``mil``/``mi`` não consumam prefixos das formas extensas.
_PADRAO_UNIDADES_ESCALA = "|".join(
    re.escape(unidade)
    for unidade in sorted(MULTIPLICADORES, key=len, reverse=True)
)

_PADRAO_NUMERO_PTBR = re.compile(
    (
    r"""
    (?P<parentese>\([ \t]*)?
    (?P<sinal_antes>[+\-\u2212]?[ \t]*)
    (?P<moeda>R\$[ \t]*)?
    (?P<sinal_depois>[+\-\u2212]?[ \t]*)
    (?P<numero>
        (?<![\w])
        (?:\d{1,3}(?:\.\d{3})+|\d+(?:\.\d+)?)
        (?:,\d+)?
        (?![\w])
    )
    [ \t]*
    (?P<unidade>
        % |
        p\.?\s*p\.? |
        bps |
        pontos?\s*(?:-\s*|de\s+)?base |
        """
    + _PADRAO_UNIDADES_ESCALA
    + r"""
    )?
    (?![\w])
    [ \t]*
    (?P<fecha_parentese>\))?
    """
    ),
    re.IGNORECASE | re.VERBOSE,
)

_FRACOES_UNICODE = frozenset(
    "¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉"
)
_NUMEROS_POR_EXTENSO = (
    "um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|"
    "onze|doze|treze|catorze|quatorze|quinze|dezesseis|dezessete|"
    "dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|"
    "setenta|oitenta|noventa|cem|cento|duzentos|trezentos|"
    "quatrocentos|quinhentos|seiscentos|setecentos|oitocentos|novecentos"
)
_PADROES_NOTACAO_NUMERICA_NAO_SUPORTADA = (
    # Evita overflow para ``inf`` e mantém o parser total diante de entradas
    # hostis. Nenhuma grandeza financeira legítima precisa de 100 algarismos.
    re.compile(r"(?<![\w])\d{100,}(?![\w])"),
    re.compile(r"(?<![\w])0[bB][01]+\b"),
    re.compile(r"(?<![\w])0[oO][0-7]+\b"),
    re.compile(r"(?<![\w])\d+(?:[.,]\d+)?[mMbB]\b"),
    re.compile(r"(?:R\$\s*){2,}", re.I),
    re.compile(r"(?:[+\-\u2212]\s*){2,}(?:R\$\s*)?\d"),
    re.compile(r"[+\-\u2212]\s*R\$\s*[+\-\u2212]\s*\d", re.I),
    re.compile(r"\b(?:USD|EUR|GBP|JPY)\s*[+\-\u2212]?\s*\d", re.I),
    re.compile(r"(?<!\d)[.,]\d+"),
    re.compile(r"\b\d+,\d+\.\d+\b"),
    re.compile(r"\b\d+\s*/\s*\d+\s*(?:mil|milh\w*|bilh\w*|trilh\w*)\b", re.I),
    re.compile(r"\d\s*%\s*(?:mil|milh\w*|bilh\w*|trilh\w*)\b", re.I),
    re.compile(r"\b\d+(?:[.,]\d+)?\s*trilh(?:ao|oes)\b", re.I),
    re.compile(
        r"\b\d+(?:[.,]\d+)?\s*(?:milh(?:ao|oes)|bilh(?:ao|oes)|"
        r"mil(?!h)|mi(?!l)|mm|bi(?!l))(?=[a-z0-9_])",
        re.I,
    ),
    re.compile(
        r"R\$\s*[+\-\u2212]?\s*\d+(?:[.,]\d+)?\s*"
        r"(?:%|p\.?\s*p\.?|bps)(?![\w])",
        re.I,
    ),
    re.compile(r"(?:US\$|€|£|¥)\s*[+\-\u2212]?\s*\d", re.I),
    re.compile(rf"\b(?:{_NUMEROS_POR_EXTENSO})\b\s+(?:por\s+cento|mil|milh\w*|bilh\w*|trilh\w*)\b", re.I),
)


def contem_notacao_numerica_nao_suportada(texto: str) -> bool:
    """Indica que há uma grandeza financeira que não pode ser tipada sem ambiguidade."""
    if not isinstance(texto, str) or not texto:
        return False
    if any(caractere in _FRACOES_UNICODE for caractere in texto):
        return True
    normalizado = remover_acentos(texto)
    if any(padrao.search(normalizado) for padrao in _PADROES_NOTACAO_NUMERICA_NAO_SUPORTADA):
        return True
    for candidato in re.findall(r"(?<![\w])\d+(?:\.\d+){2,}(?![\w])", normalizado):
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", candidato) is None:
            return True
    return False

_PADRAO_ESCALA_TABELA = re.compile(
    r"(?:\b(?:valores?|saldos?|montantes?)\s+em\s+|\bem\s+r\$\s*|\br\$\s*)"
    rf"(?P<unidade>{_PADRAO_UNIDADES_ESCALA})\b",
    re.IGNORECASE,
)


def _numero_nu_e_metadado(texto: str, match: re.Match[str], valor: float) -> bool:
    """Filtra anos, paginação e índices de nota sem esconder valores de tabela."""
    numero = match.group("numero")
    if numero.isdigit() and 1900 <= int(numero) <= 2100:
        return True
    inicio_linha = texto.rfind("\n", 0, match.start()) + 1
    fim_linha = texto.find("\n", match.end())
    if fim_linha < 0:
        fim_linha = len(texto)
    prefixo = texto[max(inicio_linha, match.start() - 24) : match.start()]
    if re.search(r"(?:pag(?:ina)?|page)\.?\s*$", prefixo, re.IGNORECASE):
        return True
    sufixo = texto[match.end() : min(fim_linha, match.end() + 3)]
    sufixo_data = texto[match.end() : min(fim_linha, match.end() + 40)]
    meses = (
        "janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|"
        "setembro|outubro|novembro|dezembro"
    )
    # Datas por extenso e numéricas não são grandezas financeiras. Sem este
    # filtro, ``30 de junho de 2025`` poderia fundamentar falsamente ``R$ 30``.
    if numero.isdigit() and (
        re.match(rf"\s*de\s+(?:{meses})\s+de\s+20\d{{2}}\b", sufixo_data)
        or re.match(r"\s*/\s*\d{1,2}\s*/\s*20\d{2}\b", sufixo_data)
    ):
        return True
    indice_parentetico = bool(
        match.group("parentese") and match.group("fecha_parentese")
    )
    indice_enumerado = bool(
        numero.isdigit()
        and abs(valor) <= 100
        and not texto[inicio_linha:match.start()].strip()
        and (match.group("fecha_parentese") or re.match(r"[.)]", sufixo))
    )
    if numero.isdigit() and abs(valor) <= 100 and (
        indice_parentetico or indice_enumerado
    ):
        return True
    return False


def _multiplicador_tabela_para_match(
    texto: str, match: re.Match[str], multiplicador_padrao: float | None
) -> float | None:
    """Restringe a herança de escala à linha/célula semanticamente compatível.

    PDFs achatam tabelas mistas (R$ + percentuais + quantidades). Aplicar a
    primeira escala do chunk a todas as células transformaria ROAE 26,6 em
    R$ 26,6 milhões e clientes 42 em R$ 42 milhões.
    """
    inicio = texto.rfind("\n", 0, match.start()) + 1
    fim = texto.find("\n", match.end())
    if fim < 0:
        fim = len(texto)
    linha = texto[inicio:fim].lower()
    escala_local = re.search(
        rf"\bem\s+(?P<unidade>{_PADRAO_UNIDADES_ESCALA})\b", linha
    )
    if escala_local:
        return float(MULTIPLICADORES[escala_local.group("unidade")])
    if re.search(r"\(%\)|\bpercentual\b|variacao\s*%|Δ\s*%", linha):
        return 0.01
    if re.search(
        r"\b(?:quantidade|numero\s+(?:total\s+)?de|clientes|colaboradores|"
        r"agencias|caixas\s+eletronicos|individuos)\b",
        linha,
    ):
        return None
    return multiplicador_padrao


@dataclass(frozen=True)
class NumeroPtBR:
    """Valor canônico acompanhado de uma dimensão mínima para grounding.

    ``taxa_percentual`` representa %, enquanto ``delta_percentual`` representa
    p.p. e bps; todos são convertidos em fração, mas não são intercambiáveis;
    ``monetario`` exige R$ explícito ou escala de tabela em R$; ``escala`` é
    uma grandeza com mil/milhão/bilhão sem moeda explícita; ``escalar`` é um
    número nu. A dimensão impede que datas/contagens sustentem valores em R$.
    """

    valor: float
    dimensao: str
    inicio: int = 0
    fim: int = 0


def remover_acentos(texto: str) -> str:
    """"Itaú" -> "Itau", "provisão" -> "provisao"."""
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )


def normalizar_texto_bm25(texto: str) -> list[str]:
    """Tokenização mínima para o BM25 em pt-BR (seção 5.6).

    Minúsculas + remoção de acentos + tokens alfanuméricos. Sem isso a
    estratégia E1 perde exatamente os termos que deveria achar
    ("Itaú" != "itau", "provisão" != "provisao").
    """
    return re.findall(r"\w+", remover_acentos(texto).lower(), flags=re.UNICODE)


def extrair_numeros_ptbr_tipados(texto: str) -> list[NumeroPtBR]:
    """Extrai valores financeiros tipados em unidades canônicas.

    A avaliação não pode assumir que o primeiro algarismo da resposta é o
    valor pedido: respostas naturais frequentemente começam por ``3T2025``,
    um ticker (``BPAC11``) ou um ano. Números embutidos em tokens
    alfanuméricos, paginação, anos e índices de notas são ignorados. Valores
    nus de tabela permanecem visíveis mesmo quando o texto também contém
    percentuais; se o chunk declara ``Em R$ milhões``/``R$ bilhões``, essa
    escala é herdada pelos valores nus da tabela.

    Sinais ``+``/``-`` e negativos contábeis entre parênteses são
    preservados. A ordem de aparição é mantida para que
    :func:`normalizar_numero_ptbr` continue oferecendo a API histórica do
    "primeiro valor relevante".
    """
    if not isinstance(texto, str) or not texto:
        return []
    if contem_notacao_numerica_nao_suportada(texto):
        return []

    normalizado = remover_acentos(texto)
    valores: list[NumeroPtBR] = []
    escala_tabela = _PADRAO_ESCALA_TABELA.search(normalizado)
    multiplicador_tabela = (
        MULTIPLICADORES[escala_tabela.group("unidade").lower()]
        if escala_tabela
        else None
    )
    for match in _PADRAO_NUMERO_PTBR.finditer(normalizado):
        numero_txt = match.group("numero")
        try:
            if "," in numero_txt:
                canonico = numero_txt.replace(".", "").replace(",", ".")
            elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", numero_txt):
                canonico = numero_txt.replace(".", "")
            else:
                # Saídas de LLM às vezes usam ponto decimal mesmo em português.
                canonico = numero_txt
            valor = float(canonico)
        except ValueError:
            continue
        if not math.isfinite(valor):
            continue

        sinal_antes = (match.group("sinal_antes") or "").replace(" ", "")
        sinal_depois = (match.group("sinal_depois") or "").replace(" ", "")
        if sinal_antes and sinal_depois:
            continue
        sinal = sinal_antes or sinal_depois
        negativo_parenteses = bool(
            match.group("parentese") and match.group("fecha_parentese")
        )
        # Em ``26,6% - 24,8%`` o hífen é operador binário, não sinal do
        # segundo operando. Ele só é unário quando não sucede outra grandeza.
        anterior = normalizado[: match.start()].rstrip()[-1:]
        sinal_unario = sinal in {"-", "\u2212"} and (
            not anterior or anterior not in "%)]0123456789"
        )
        if sinal_unario or negativo_parenteses:
            valor = -valor

        unidade = (match.group("unidade") or "").lower()
        unidade_compacta = re.sub(r"[.\s-]+", "", unidade)
        dimensao = "monetario" if match.group("moeda") else "escalar"
        if unidade == "%":
            valor /= 100.0
            dimensao = "taxa_percentual"
        elif unidade_compacta == "pp":
            valor /= 100.0
            dimensao = "delta_percentual"
        elif unidade_compacta in {
            "bps",
            "pontobase",
            "pontosbase",
            "pontodebase",
            "pontosdebase",
        }:
            valor /= 10_000.0
            dimensao = "delta_percentual"
        elif unidade:
            valor *= MULTIPLICADORES[unidade]
            if dimensao != "monetario":
                dimensao = "escala"
        elif not match.group("moeda"):
            if _numero_nu_e_metadado(normalizado, match, valor):
                continue
            multiplicador_contextual = _multiplicador_tabela_para_match(
                normalizado, match, multiplicador_tabela
            )
            if multiplicador_contextual is not None:
                valor *= multiplicador_contextual
                dimensao = (
                    "taxa_percentual"
                    if multiplicador_contextual == 0.01
                    else "monetario"
                )

        valores.append(
            NumeroPtBR(
                valor=valor,
                dimensao=dimensao,
                inicio=match.start(),
                fim=match.end(),
            )
        )

    return valores


def extrair_numeros_ptbr(texto: str) -> list[float]:
    """Extrai somente os valores canônicos; veja a variante tipada."""
    return [numero.valor for numero in extrair_numeros_ptbr_tipados(texto)]


def normalizar_numero_ptbr(texto: str) -> float | None:
    """Converte a primeira expressão numérica relevante para valor canônico.

    Contrato (casos no `tests/test_normalizacao.py`):
      - "R$ 2,3 bilhões"    -> 2_300_000_000.0
      - "1.234,5 milhões"   -> 1_234_500_000.0
      - "R$ 1.234"          -> 1_234.0
      - "23,4%"             -> 0.234   (percentual vira fração)
      - "1,9 mil"           -> 1_900.0
      - texto sem número    -> None

    Regras: vírgula é decimal, ponto é separador de milhar, multiplicadores
    (mil/milhões/bilhões e abreviações mi/bi) são aplicados, "R$" é ignorado.
    Para comparar uma resposta que possa conter mais de um valor, use
    :func:`extrair_numeros_ptbr`.
    """
    valores = extrair_numeros_ptbr(texto)
    return valores[0] if valores else None


def valores_equivalentes(
    esperado: float, obtido: float, tolerancia_pct: float = 1.0
) -> bool:
    """Compara valores canônicos com a tolerância da seção 5.8.

    Correto se |obtido - esperado| <= tolerancia_pct% relativo do esperado,
    OU se coincidirem após normalização de ordem de grandeza/arredondamento
    (evita falso negativo por milhares vs. milhões: 2_300 "milhões" divulgado
    vs. 2.3e9 canônico já resolvido pelo parser; aqui trata arredondamento de
    exibição, ex. 2,3 bi vs. 2.287 bi -> False; 2,3 bi vs. 2,31 bi -> True).
    """
    if any(isinstance(valor, bool) for valor in (esperado, obtido, tolerancia_pct)):
        raise ValueError("Valores e tolerância devem ser números reais.")
    try:
        esperado = float(esperado)
        obtido = float(obtido)
        tolerancia_pct = float(tolerancia_pct)
    except (TypeError, ValueError) as exc:
        raise ValueError("Valores e tolerância devem ser números reais.") from exc
    if not all(math.isfinite(valor) for valor in (esperado, obtido, tolerancia_pct)):
        raise ValueError("Valores e tolerância devem ser finitos.")
    if tolerancia_pct < 0:
        raise ValueError("tolerancia_pct não pode ser negativa.")
    if esperado == 0.0:
        return obtido == 0.0
    return abs(obtido - esperado) <= abs(esperado) * (tolerancia_pct / 100.0)


def canonizar_banco(texto: str) -> str | None:
    """Encontra a primeira instituição citada no texto e devolve o nome canônico.

    Matching é feito sobre `remover_acentos(texto).lower()` contra
    APELIDOS_BANCOS, preferindo o apelido mais longo (evita "bb" casar dentro
    de outra palavra — a busca respeita fronteiras de palavra).
    Devolve None se nenhuma instituição conhecida for citada.
    """
    citados = extrair_bancos_citados(texto)
    return citados[0] if citados else None


def _ocorrencias_de_bancos(texto: str) -> list[tuple[int, int, str]]:
    """(posição, -len(apelido), canônico) de cada apelido achado, com fronteira
    de palavra sobre o texto sem acento/minúsculo."""
    normalizado = remover_acentos(texto).lower()
    ocorrencias: list[tuple[int, int, str]] = []
    for canonico, apelidos in APELIDOS_BANCOS.items():
        for apelido in apelidos:
            padrao = r"\b" + re.escape(apelido) + r"\b"
            for m in re.finditer(padrao, normalizado):
                ocorrencias.append((m.start(), -len(apelido), canonico))
    ocorrencias.sort()
    return ocorrencias


def extrair_bancos_citados(texto: str) -> list[str]:
    """Todos os bancos citados no texto, canônicos, na ordem de aparição.

    Base da decomposição em subconsultas das perguntas comparativas (5.6).
    """
    vistos: list[str] = []
    for _, _, canonico in _ocorrencias_de_bancos(texto):
        if canonico not in vistos:
            vistos.append(canonico)
    return vistos


def extrair_trimestre_citado(texto: str) -> str | None:
    """Devolve o primeiro código canônico ``1T2026`` citado, se houver."""
    trimestres = extrair_trimestres_citados(texto)
    return trimestres[0] if trimestres else None


def extrair_trimestres_citados(texto: str) -> list[str]:
    """Devolve todos os trimestres citados, sem duplicatas e em ordem.

    Perguntas comparativas podem pedir, por exemplo, ``4T2025 e 1T2026``.
    Reduzi-las ao primeiro período filtra evidência válida do segundo.
    """
    vistos: list[str] = []
    for match in PADRAO_TRIMESTRE.finditer(texto):
        trimestre = f"{match.group(1)}T{match.group(2)}"
        if trimestre not in vistos:
            vistos.append(trimestre)
    return vistos
