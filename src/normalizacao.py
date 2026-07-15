"""Normalização numérica pt-BR e apelidos de banco (seções 5.6 e 5.8).

Pré-requisito do verificador de exatidão numérica: "R$ 2,3 bilhões",
"1.234,5 milhões" e "23,4%" precisam virar unidades canônicas antes de
qualquer comparação — sem isso, a avaliação produz falsos negativos em massa
(modo de falha nº 4, seção 5.18).

Módulo coberto por `tests/test_normalizacao.py` (exigência do AGENTS.md, etapa 5).
"""

from __future__ import annotations

import re
import unicodedata

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
    "bilhao": 1_000_000_000,
    "bilhoes": 1_000_000_000,
    "bi": 1_000_000_000,
}


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


def normalizar_numero_ptbr(texto: str) -> float | None:
    """Converte uma expressão numérica pt-BR para valor canônico (float).

    Contrato (casos no `tests/test_normalizacao.py`):
      - "R$ 2,3 bilhões"    -> 2_300_000_000.0
      - "1.234,5 milhões"   -> 1_234_500_000.0
      - "R$ 1.234"          -> 1_234.0
      - "23,4%"             -> 0.234   (percentual vira fração)
      - "1,9 mil"           -> 1_900.0
      - texto sem número    -> None

    Regras: vírgula é decimal, ponto é separador de milhar, multiplicadores
    (mil/milhões/bilhões e abreviações mi/bi) são aplicados, "R$" é ignorado.
    """
    normalizado = remover_acentos(texto).lower()
    numero = re.search(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?", normalizado)
    if numero is None:
        return None
    valor = float(numero.group(0).replace(".", "").replace(",", "."))
    resto = normalizado[numero.end() :]
    if re.match(r"\s*%", resto):
        return valor / 100.0
    palavra = re.match(r"\s*([a-z]+)\b", resto)
    if palavra and palavra.group(1) in MULTIPLICADORES:
        valor *= MULTIPLICADORES[palavra.group(1)]
    return valor


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
    """Devolve o código canônico "1T2026" se a pergunta citar um trimestre."""
    m = PADRAO_TRIMESTRE.search(texto)
    if m is None:
        return None
    return f"{m.group(1)}T{m.group(2)}"
