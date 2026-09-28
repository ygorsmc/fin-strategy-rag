"""Redline entre releases consecutivos — piloto CAND-02-P.

Protocolo: `resultados/protocolo_cand02p_piloto_ia_2026-09-28.md`. As regras de
B0 e B1 são as do CAND-02 (`resultados/pre_registro_cand02_redline_2026-08-27.md`);
nada neste módulo é aprendido.

Três etapas, todas determinísticas:

1. **Documento → blocos.** Do OCR (markdown por página) saem sentenças de texto
   e linhas de tabela, com página, seção, título, unidade e períodos. Linha que
   se repete em muitas páginas é cabeçalho ou rodapé e sai; número de página e
   artefato de OCR também.
2. **Par → eventos.** Sentença idêntica em qualquer posição do outro documento
   é movimento, não evento. O resto é pareado primeiro pelo esqueleto (períodos
   e números mascarados), depois por semelhança de tokens; o que sobra é adição
   ou remoção. Linha de tabela é pareada pela tabela e pelo rótulo, e vira
   evento se o valor do trimestre do documento mudou ou se um período presente
   nos dois documentos mudou de valor (reapresentação).
3. **B0 e B1.** B0 ordena pela massa de tokens alterados. B1 é lexicográfico:
   número acima da triagem, sinal, negação ou modal; categoria sensível;
   adição ou remoção integral; massa e distância de edição.
"""

from __future__ import annotations

import difflib
import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from typing import Iterable, Sequence

# --- normalização ------------------------------------------------------------------------

_ARTEFATOS_OCR = (
    re.compile(r"!\[[^\]]*\]\([^)]*\)"),  # imagem
    re.compile(r"\^\{[^}]*\}"),  # sobrescrito (nota de rodapé)
    re.compile(r"\$\^\{?[^$]*\}?\$"),  # sobrescrito em LaTeX
    re.compile(r"\[\]"),
)
_NEGRITO = re.compile(r"\*\*|__")
_ESPACOS = re.compile(r"\s+")
_PAGINA = re.compile(r"^(p[áa]gina\s*)?\d{1,3}(\s*(de|/)\s*\d{1,3})?$", re.IGNORECASE)

_MESES = "jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez"
#: Períodos que rolam de um trimestre para o outro. Mascarados no esqueleto:
#: "período automático" é nota 0 na rubrica.
_PERIODO = re.compile(
    rf"\b(?:[1-4]\s?T\s?(?:20)?\d{{2}}|\d{{1,2}}\s?M\s?(?:20)?\d{{2}}|"
    rf"(?:{_MESES})[a-z]*[/\-\s]?(?:20)?\d{{2}}|\d{{1,2}}[/.]\d{{1,2}}[/.](?:20)?\d{{2}}|"
    rf"(?:19|20)\d{{2}})\b",
    re.IGNORECASE,
)
_NUMERO = re.compile(r"\(?-?\d[\d.]*(?:,\d+)?\)?\s?%?")
_UNIDADE = re.compile(
    r"(milhares|milh[õo]es|bilh[õo]es|R\$\s*mil\b|R\$\s*mi\b|R\$\s*bi\b|US\$\s*mil)",
    re.IGNORECASE,
)

_STOP = frozenset(
    "a o as os de da do das dos e em no na nos nas um uma uns umas por para com "
    "que se ao aos à às pelo pela pelos pelas é foi são ou mais menos seu sua "
    "seus suas este esta estes estas esse essa isso também já entre sobre como".split()
)

#: B1, nível 2: categorias sensíveis do CAND-02, vocabulário fechado.
CATEGORIAS: dict[str, tuple[str, ...]] = {
    "guidance": ("guidance", "projec", "perspectiva", "expectativa", "estimativa",
                 "meta ", "metas", "esperamos", "prevemos", "revisamos", "revisao"),
    "definicao_escopo": ("definicao", "criterio", "metodologia", "perimetro",
                         "reclassific", "passa a ", "passou a ", "deixa de", "deixou de",
                         "nova apresentacao", "consolidacao"),
    "contabilidade": ("reapresent", "ifrs", "brgaap", "4.966", "4966", "cpc ",
                      "politica contabil", "efeito contabil", "ajuste contabil",
                      "retific", "republica"),
    "risco_incerteza": ("risco", "regulat", "banco central", "bacen", "cmn",
                        "resolucao", "incerteza", "contingenc", "judicial",
                        "processo", "litig", "fiscaliz"),
    "capital_liquidez": ("basileia", "capital principal", "cet1", "indice de capital",
                         "nivel i", "liquidez", "lcr", "nsfr", "dividend",
                         "juros sobre capital", "jcp", "payout", "recompra",
                         "remuneracao aos acionistas"),
    "credito": ("inadimpl", "npl", "custo de risco", "custo do credito", "pdd",
                "provisao para", "perda esperada", "estagio 3", "atraso",
                "renegoci", "cobertura", "write-off", "baixa para prejuizo"),
}
_CREDITO = CATEGORIAS["credito"]
_NEGACAO_MODAL = re.compile(
    r"\b(n[ãa]o|nenhum[a]?|sem|nunca|jamais|poder[áa]|pode|podem|dever[áa]|deve|"
    r"devem|espera-se|prev[êe]|poss[íi]vel|eventual)\b",
    re.IGNORECASE,
)
_MOEDA = re.compile(r"(R\$|US\$|€|USD|BRL|EUR)")

#: Triagem numérica do B1 (CAND-02): não é limiar de materialidade legal.
TRIAGEM_BP_GERAL = 50.0
TRIAGEM_BP_CREDITO = 20.0
TRIAGEM_RELATIVA = 0.10


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def limpar(texto: str) -> str:
    """Tira artefato de OCR, negrito e espaço repetido. Números, sinais,
    percentuais, moedas, negações e modais ficam (B0 do CAND-02)."""
    for padrao in _ARTEFATOS_OCR:
        texto = padrao.sub("", texto)
    texto = _NEGRITO.sub("", texto)
    return _ESPACOS.sub(" ", texto).strip()


def chave(texto: str) -> str:
    """Identidade de texto: minúsculas, sem acento, espaço normalizado. O `$`
    solto é delimitador de LaTeX do OCR; o de `R$` e `US$` fica."""
    k = re.sub(r"(?<!r)(?<!us)\$", "", sem_acento(texto).lower())
    return _ESPACOS.sub(" ", k).strip()


def esqueleto(texto: str) -> str:
    """Chave com períodos e números mascarados: pareia o número rolado."""
    k = _PERIODO.sub("<p>", chave(texto))
    return _ESPACOS.sub(" ", _NUMERO.sub("<n>", k)).strip()


def tokens(texto: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9<>%$.,()\-]+", chave(texto))
            if t not in _STOP and t not in {".", ",", "-", "(", ")"}]


# --- números ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Numero:
    valor: float
    percentual: bool
    decimais: int


def ler_numero(texto: str) -> Numero | None:
    """Número pt-BR de célula ou de sentença. Parênteses são negativos."""
    t = limpar(texto).replace(" ", "")
    if not t or t in {"-", "–", "—", "n.a.", "n/a", "na", "nm", "n.m."}:
        return None
    negativo = t.startswith("(") and t.endswith(")") or t.startswith("-") or t.startswith("–")
    percentual = t.endswith("%") or t.lower().endswith("p.p.") or t.lower().endswith("pp")
    t = re.sub(r"[()%–\-]|p\.p\.|pp$", "", t, flags=re.IGNORECASE)
    if not re.fullmatch(r"\d{1,3}(\.\d{3})*(,\d+)?|\d+(,\d+)?", t):
        return None
    decimais = len(t.split(",")[1]) if "," in t else 0
    valor = float(t.replace(".", "").replace(",", "."))
    return Numero(-valor if negativo else valor, percentual, decimais)


def numeros_da_sentenca(texto: str) -> list[Numero]:
    """Números da sentença, sem os que são período (ano, trimestre)."""
    sem_periodo = _PERIODO.sub(" ", limpar(texto))
    saida = []
    for m in _NUMERO.finditer(sem_periodo):
        n = ler_numero(m.group(0))
        if n is not None:
            saida.append(n)
    return saida


def mudanca_numerica(a: Numero, b: Numero, credito: bool, unidades_de_tolerancia: float = 0.5
                     ) -> dict:
    """Uma comparação da triagem do B1: bp em percentual, relativa em valor.

    `unidades_de_tolerancia` é medida na última casa exibida. No mesmo período
    em dois releases usa-se 1: arredondamento diferente não é reapresentação."""
    percentual = a.percentual or b.percentual
    tolerancia = 10 ** -min(a.decimais, b.decimais)
    igual = abs(a.valor - b.valor) <= tolerancia * unidades_de_tolerancia + 1e-12
    bp = abs(b.valor - a.valor) * 100 if percentual else None
    relativa = (abs(b.valor - a.valor) / abs(a.valor)) if a.valor and not percentual else None
    sinal = (a.valor < 0) != (b.valor < 0) and a.valor != 0 and b.valor != 0
    ordem = bool(a.valor and b.valor and not percentual
                 and abs(math.log10(abs(b.valor) / abs(a.valor))) >= 1)
    if igual:
        acima = False
    elif percentual:
        acima = bp >= (TRIAGEM_BP_CREDITO if credito else TRIAGEM_BP_GERAL)
    else:
        acima = relativa is None or relativa >= TRIAGEM_RELATIVA
    return {"antes": a.valor, "depois": b.valor, "percentual": percentual, "bp": bp,
            "relativa": relativa, "sinal": sinal, "ordem_de_grandeza": ordem,
            "acima_da_triagem": bool(acima or sinal or ordem), "igual": igual}


# --- documento → blocos ------------------------------------------------------------------

_TRIMESTRE_DOC = re.compile(r"([1-4])T(\d{4})")


def periodo_canonico(celula: str) -> str | None:
    """'3T 2024', '3T24', '9M25', '2025', '30/09/2025', 'set/25' → forma única."""
    t = sem_acento(limpar(celula)).upper().replace(" ", "")
    if m := re.fullmatch(r"([1-4])T(?:20)?(\d{2})", t):
        return f"{m.group(1)}T20{m.group(2)}"
    if m := re.fullmatch(r"(\d{1,2})M(?:20)?(\d{2})", t):
        return f"{int(m.group(1))}M20{m.group(2)}"
    if m := re.fullmatch(r"((?:19|20)\d{2})", t):
        return f"A{m.group(1)}"
    if m := re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](?:20)?(\d{2})", t):
        return f"20{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    meses = {m: i for i, m in enumerate(_MESES.upper().split("|"), start=1)}
    if m := re.fullmatch(rf"({_MESES.upper()})[A-Z]*[/\-]?(?:20)?(\d{{2}})", t):
        return f"20{m.group(2)}-{meses[m.group(1)]:02d}"
    return None


@dataclass(frozen=True)
class Sentenca:
    pagina: int
    secao: str
    texto: str
    chave: str
    esqueleto: str
    ordem: int


@dataclass(frozen=True)
class LinhaTabela:
    pagina: int
    secao: str
    titulo: str
    unidade: str
    cabecalho: tuple[str, ...]
    periodos: tuple[str | None, ...]
    rotulo: str
    celulas: tuple[str, ...]
    chave_tabela: str
    chave_linha: str
    ordem: int

    def texto(self) -> str:
        return f"{self.rotulo}: " + " | ".join(self.celulas)


@dataclass(frozen=True)
class Documento:
    nome: str
    empresa: str
    trimestre: str
    paginas: int
    sentencas: tuple[Sentenca, ...]
    linhas: tuple[LinhaTabela, ...]
    ruido: tuple[str, ...] = ()


def _linhas_repetidas(paginas: Sequence[str]) -> set[str]:
    """Cabeçalho e rodapé: a mesma linha curta em muitas páginas."""
    contagem: Counter[str] = Counter()
    for md in paginas:
        contagem.update({l.strip() for l in md.splitlines() if l.strip()})
    minimo = max(3, int(0.2 * len(paginas)))
    return {l for l, n in contagem.items()
            if n >= minimo and len(l) <= 160 and not l.startswith("|")}


def _dividir_sentencas(paragrafo: str) -> list[str]:
    partes = re.split(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ(\"“•\-0-9])", paragrafo)
    return [p.strip(" •-") for p in partes if p.strip(" •-")]


def _celulas(linha: str) -> list[str]:
    partes = [c.strip() for c in linha.strip().strip("|").split("|")]
    return partes


def _eh_separador(celulas: list[str]) -> bool:
    return bool(celulas) and all(re.fullmatch(r":?-{3,}:?", c) for c in celulas if c)


def _tabela(linhas_md: list[str], titulo: str, unidade_pagina: str, pagina: int,
            secao: str, inicio_ordem: int) -> list[LinhaTabela]:
    linhas = [_celulas(l) for l in linhas_md]
    if not linhas:
        return []
    largura = max(len(c) for c in linhas)
    linhas = [c + [""] * (largura - len(c)) for c in linhas]
    sep = next((i for i, c in enumerate(linhas) if _eh_separador(c)), None)
    cabecalho_linhas = linhas[:sep] if sep is not None else linhas[:1]
    corpo = linhas[sep + 1:] if sep is not None else linhas[1:]
    # Continuação do cabeçalho: primeira célula vazia e o resto com períodos.
    while corpo and not limpar(corpo[0][0]) and sum(
            periodo_canonico(c) is not None for c in corpo[0][1:]) >= max(1, (largura - 1) // 2):
        cabecalho_linhas.append(corpo.pop(0))
    # Célula mesclada: no markdown o texto fica só na primeira coluna do grupo.
    # Nas linhas de cabeçalho de cima ele vale para as vazias à direita — é o
    # que impede "Variação % para 3T25 | (vazio)" de virar um período.
    preenchidas = []
    for n, linha in enumerate(cabecalho_linhas):
        if n < len(cabecalho_linhas) - 1:
            linha = list(linha)
            for j in range(2, largura):
                if not limpar(linha[j]) and limpar(linha[j - 1]):
                    linha[j] = linha[j - 1]
        preenchidas.append(linha)
    cabecalho = tuple(limpar(" ".join(l[j] for l in preenchidas if l[j])) for j in range(largura))
    periodos = [periodo_da_coluna(rotulo) for rotulo in cabecalho]
    variacao = {j for j, r in enumerate(cabecalho) if j and _COLUNA_DE_VARIACAO.search(r)}
    numericas = set()
    for j in range(1, largura):
        valores = [ler_numero(l[j]) for l in corpo if limpar(l[j])]
        if valores and sum(v is not None for v in valores) >= 0.6 * len(valores):
            numericas.add(j)
    candidatas = ({j for j, p in enumerate(periodos) if p} | numericas) - variacao - {0}
    # Rótulo: só as colunas antes da primeira coluna de valor. Coluna de
    # variação e coluna de texto depois dela não são rótulo nem valor.
    primeira = min(candidatas) if candidatas else largura
    colunas_de_rotulo = set(range(primeira))
    colunas_de_valor = {j for j in candidatas if j >= primeira}
    # Título: o parágrafo logo acima, se for curto; senão a seção. A chave da
    # tabela junta o título e a primeira célula do cabeçalho, com números e
    # períodos mascarados ("Tabela 4" que vira "Tabela 5" continua a mesma).
    titulo_limpo = limpar(titulo) if len(limpar(titulo)) <= 160 else secao
    unidade = ""
    for fonte in (titulo, " ".join(cabecalho), unidade_pagina):
        if m := _UNIDADE.search(fonte or ""):
            unidade = chave(m.group(1))
            break
    titulo_chave = _ENUMERADOR.sub("", titulo_limpo)
    chave_tab = f"{esqueleto(titulo_chave)[:160]} || {esqueleto(cabecalho[0])[:120]}"
    saida: list[LinhaTabela] = []
    for i, celulas in enumerate(corpo):
        rotulos = [limpar(celulas[j]) for j in sorted(colunas_de_rotulo) if limpar(celulas[j])]
        if len(rotulos) > 1:
            rotulos = [r for r in rotulos if not re.fullmatch(r"\d{1,3}", r)] or rotulos
        rotulo = " ".join(rotulos)
        valores = tuple(limpar(celulas[j]) for j in sorted(colunas_de_valor))
        # Linha de dado tem ao menos um número; sub-cabeçalho ("Receitas |
        # Taxa Anual") não tem.
        if not rotulo or not any(ler_numero(v) is not None for v in valores):
            continue
        saida.append(LinhaTabela(
            pagina=pagina, secao=secao, titulo=titulo_limpo, unidade=unidade,
            cabecalho=tuple(cabecalho[j] for j in sorted(colunas_de_valor)),
            periodos=tuple(periodos[j] for j in sorted(colunas_de_valor)),
            rotulo=rotulo, celulas=valores, chave_tabela=chave_tab,
            chave_linha=esqueleto(rotulo), ordem=inicio_ordem + i))
    return saida


#: Coluna de variação ('4T25 x 3T25', 'Δ', 'Var. %'): derivada, fica fora.
_COLUNA_DE_VARIACAO = re.compile(r"(\bvar|Δ|\bx\b|\bvs\.?\b|%)", re.IGNORECASE)
#: Letra ou número de item no começo do título ("i) ...", "l) ...", "4.2 ..."),
#: que muda entre trimestres sem mudar a tabela.
_ENUMERADOR = re.compile(r"^\s*(\(?[a-z]{1,2}\)|\(?[ivxl]{1,5}\)|\d+(\.\d+)*[.)]?)\s+", re.IGNORECASE)


def periodo_da_coluna(rotulo: str) -> str | None:
    """Período de uma coluna de valor. Coluna de variação não é período."""
    if _COLUNA_DE_VARIACAO.search(rotulo):
        return None
    achados = [periodo_canonico(m.group(0)) for m in _PERIODO.finditer(rotulo)]
    achados = [p for p in achados if p]
    return achados[0] if len(achados) == 1 else None


def documento_de_paginas(nome: str, empresa: str, trimestre: str,
                         paginas_md: Sequence[str]) -> Documento:
    """Blocos de um documento a partir do markdown de cada página."""
    ruido = _linhas_repetidas(paginas_md)
    sentencas: list[Sentenca] = []
    linhas_tab: list[LinhaTabela] = []
    secao = ""
    ordem = 0
    for numero, md in enumerate(paginas_md, start=1):
        unidade_pagina = next((l for l in md.splitlines() if _UNIDADE.search(l) and len(l) < 200), "")
        bruto = [l.rstrip() for l in md.splitlines()]
        paragrafo: list[str] = []
        tabela: list[str] = []
        ultimo_texto = ""

        def fechar_paragrafo():
            nonlocal paragrafo, ordem, ultimo_texto
            if not paragrafo:
                return
            texto = ""
            for linha in paragrafo:
                if texto.endswith("-") and linha[:1].islower():
                    texto = texto[:-1] + linha
                else:
                    texto = f"{texto} {linha}".strip()
            texto = limpar(texto)
            ultimo_texto = texto
            for s in _dividir_sentencas(texto):
                if len(tokens(s)) < 4:
                    continue
                ordem += 1
                sentencas.append(Sentenca(numero, secao, s, chave(s), esqueleto(s), ordem))
            paragrafo = []

        def fechar_tabela():
            nonlocal tabela, ordem
            if tabela:
                novas = _tabela(tabela, ultimo_texto, unidade_pagina, numero, secao, ordem)
                ordem += len(tabela)
                linhas_tab.extend(novas)
            tabela = []

        for linha in bruto:
            s = linha.strip()
            if s.startswith("|"):
                fechar_paragrafo()
                tabela.append(s)
                continue
            fechar_tabela()
            if not s:
                fechar_paragrafo()
                continue
            if s in ruido or _PAGINA.fullmatch(limpar(s)):
                continue
            if s.startswith("#"):
                fechar_paragrafo()
                secao = limpar(s.lstrip("#"))[:160]
                ultimo_texto = secao
                continue
            paragrafo.append(s)
        fechar_paragrafo()
        fechar_tabela()
    # Rótulo repetido na mesma tabela (ou em tabelas de mesma chave): ocorrência
    # contada no documento inteiro, na ordem de leitura.
    vistos: Counter[tuple[str, str]] = Counter()
    numeradas = []
    for l in linhas_tab:
        vistos[(l.chave_tabela, l.chave_linha)] += 1
        numeradas.append(replace(l, chave_linha=f"{l.chave_linha}#{vistos[(l.chave_tabela, l.chave_linha)]}"))
    return Documento(nome, empresa, trimestre, len(paginas_md), tuple(sentencas),
                     tuple(numeradas), tuple(sorted(ruido)))


# --- par → eventos -----------------------------------------------------------------------

@dataclass
class Evento:
    id: str
    par: str
    operacao: str  # adicao | remocao | alteracao
    tipo: str  # texto | tabela
    pagina_antes: int | None
    pagina_depois: int | None
    secao: str
    antes: str
    depois: str
    titulo: str = ""
    unidade: str = ""
    cabecalho_antes: tuple[str, ...] = ()
    cabecalho_depois: tuple[str, ...] = ()
    rotulo: str = ""
    mudancas_numericas: list[dict] = field(default_factory=list)
    reapresentacao: bool = False
    categorias: list[str] = field(default_factory=list)
    negacao_modal: bool = False
    moeda: bool = False
    massa: int = 0
    distancia: float = 0.0
    pagina_relativa: float = 0.0

    # --- B1 ---
    @property
    def nivel1(self) -> bool:
        return self.operacao == "alteracao" and (
            self.reapresentacao or self.negacao_modal or self.moeda
            or any(m["acima_da_triagem"] for m in self.mudancas_numericas))

    @property
    def nivel2(self) -> bool:
        return bool(self.categorias)

    @property
    def nivel3(self) -> bool:
        return self.operacao in ("adicao", "remocao")

    def para_dict(self) -> dict:
        d = asdict(self)
        d.update(b1_nivel1=self.nivel1, b1_nivel2=self.nivel2, b1_nivel3=self.nivel3)
        return d


def _id_evento(par: str, operacao: str, antes: str, depois: str, pa, pd, n: int) -> str:
    base = f"{par}|{operacao}|{pa}|{pd}|{antes}|{depois}|{n}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def _categorias(texto: str) -> list[str]:
    k = chave(texto) + " "
    return sorted(nome for nome, termos in CATEGORIAS.items() if any(t in k for t in termos))


def _massa_e_distancia(antes: str, depois: str) -> tuple[int, float]:
    ta, td = Counter(tokens(antes)), Counter(tokens(depois))
    massa = sum(((ta - td) + (td - ta)).values())
    distancia = 1.0 - difflib.SequenceMatcher(None, chave(antes), chave(depois)).ratio()
    return massa, round(distancia, 4)


def _negacao_modal_mudou(antes: str, depois: str) -> bool:
    return (Counter(m.lower() for m in _NEGACAO_MODAL.findall(antes))
            != Counter(m.lower() for m in _NEGACAO_MODAL.findall(depois)))


def _moeda_mudou(antes: str, depois: str) -> bool:
    return Counter(_MOEDA.findall(antes)) != Counter(_MOEDA.findall(depois))


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 0.0


def _parear_sentencas(antes: list[Sentenca], depois: list[Sentenca], limiar: float
                      ) -> tuple[list[tuple[Sentenca, Sentenca]], list[Sentenca], list[Sentenca]]:
    """Esqueleto igual primeiro, depois semelhança de tokens com índice invertido."""
    pares: list[tuple[Sentenca, Sentenca]] = []
    por_esqueleto: dict[str, list[Sentenca]] = defaultdict(list)
    for s in antes:
        por_esqueleto[s.esqueleto].append(s)
    restantes_depois: list[Sentenca] = []
    usados: set[int] = set()
    for s in depois:
        candidatos = [c for c in por_esqueleto.get(s.esqueleto, []) if c.ordem not in usados]
        if candidatos:
            c = min(candidatos, key=lambda c: (c.secao != s.secao, abs(c.ordem - s.ordem)))
            usados.add(c.ordem)
            pares.append((c, s))
        else:
            restantes_depois.append(s)
    restantes_antes = [s for s in antes if s.ordem not in usados]
    conj = {s.ordem: set(esqueleto(s.texto).split()) - _STOP for s in restantes_antes}
    indice: dict[str, set[int]] = defaultdict(set)
    for o, toks in conj.items():
        for t in toks:
            indice[t].add(o)
    frequencia = {t: len(v) for t, v in indice.items()}
    por_ordem = {s.ordem: s for s in restantes_antes}
    sobra_depois: list[Sentenca] = []
    for s in restantes_depois:
        toks = set(esqueleto(s.texto).split()) - _STOP
        raros = sorted(toks, key=lambda t: frequencia.get(t, 0))[:6]
        candidatos = set().union(*(indice.get(t, set()) for t in raros)) - usados if raros else set()
        melhor, nota = None, limiar
        for o in candidatos:
            j = _jaccard(toks, conj[o])
            if j > nota or (j == nota and melhor is not None and o < melhor):
                melhor, nota = o, j
        if melhor is not None and nota >= limiar:
            usados.add(melhor)
            pares.append((por_ordem[melhor], s))
        else:
            sobra_depois.append(s)
    sobra_antes = [s for s in restantes_antes if s.ordem not in usados]
    return pares, sobra_antes, sobra_depois


def _principal(linha: LinhaTabela, trimestre_doc: str) -> int | None:
    alvo = trimestre_doc
    if alvo in linha.periodos:
        return linha.periodos.index(alvo)
    trimestres = [(p, j) for j, p in enumerate(linha.periodos) if p and re.fullmatch(r"[1-4]T\d{4}", p)]
    if not trimestres:
        return None
    return max(trimestres, key=lambda t: (t[0][2:], t[0][0]))[1]


def gerar_eventos(par: str, anterior: Documento, atual: Documento,
                  limiar_semelhanca: float = 0.5) -> list[Evento]:
    """Universo de eventos do par: o mesmo para os quatro braços."""
    eventos: list[Evento] = []
    contagem_ids: Counter[str] = Counter()

    def novo(**kw) -> Evento:
        base = (kw["operacao"], kw["antes"], kw["depois"], kw["pagina_antes"], kw["pagina_depois"])
        contagem_ids[str(base)] += 1
        ev = Evento(id=_id_evento(par, *base, contagem_ids[str(base)]), par=par, **kw)
        ev.categorias = _categorias(f"{ev.titulo} {ev.rotulo} {ev.antes} {ev.depois}")
        ev.massa, ev.distancia = _massa_e_distancia(ev.antes, ev.depois)
        pagina = ev.pagina_depois if ev.pagina_depois is not None else ev.pagina_antes
        paginas = atual.paginas if ev.pagina_depois is not None else anterior.paginas
        ev.pagina_relativa = round((pagina or 1) / max(1, paginas), 4)
        eventos.append(ev)
        return ev

    # Texto: idêntico em qualquer posição é movimento.
    chaves_atual = Counter(s.chave for s in atual.sentencas)
    chaves_anterior = Counter(s.chave for s in anterior.sentencas)
    comuns = chaves_atual & chaves_anterior
    restam_a, restam_d = Counter(comuns), Counter(comuns)
    antes = []
    for s in anterior.sentencas:
        if restam_a[s.chave] > 0:
            restam_a[s.chave] -= 1
        else:
            antes.append(s)
    depois = []
    for s in atual.sentencas:
        if restam_d[s.chave] > 0:
            restam_d[s.chave] -= 1
        else:
            depois.append(s)
    pares, removidas, adicionadas = _parear_sentencas(antes, depois, limiar_semelhanca)
    for a, d in pares:
        credito = any(t in chave(a.texto + " " + d.texto) for t in _CREDITO)
        na, nd = numeros_da_sentenca(a.texto), numeros_da_sentenca(d.texto)
        if len(na) == len(nd):
            mudancas = [mudanca_numerica(x, y, credito) for x, y in zip(na, nd)]
            mudancas = [m for m in mudancas if not m["igual"]]
        else:
            mudancas = [{"antes": None, "depois": None, "percentual": False, "bp": None,
                         "relativa": None, "sinal": False, "ordem_de_grandeza": False,
                         "acima_da_triagem": True, "igual": False}]
        if a.esqueleto == d.esqueleto and not mudancas:
            continue  # só o período rolou: "período automático"
        novo(operacao="alteracao", tipo="texto", pagina_antes=a.pagina, pagina_depois=d.pagina,
             secao=d.secao or a.secao, antes=a.texto, depois=d.texto,
             mudancas_numericas=mudancas,
             negacao_modal=_negacao_modal_mudou(a.texto, d.texto),
             moeda=_moeda_mudou(a.texto, d.texto))
    for s in removidas:
        novo(operacao="remocao", tipo="texto", pagina_antes=s.pagina, pagina_depois=None,
             secao=s.secao, antes=s.texto, depois="")
    for s in adicionadas:
        novo(operacao="adicao", tipo="texto", pagina_antes=None, pagina_depois=s.pagina,
             secao=s.secao, antes="", depois=s.texto)

    # Tabelas: pareadas por (tabela, rótulo); sem tabela, pelo rótulo único.
    indice_antes = {(l.chave_tabela, l.chave_linha): l for l in anterior.linhas}
    por_rotulo_antes: dict[str, list[LinhaTabela]] = defaultdict(list)
    for l in anterior.linhas:
        por_rotulo_antes[l.chave_linha].append(l)
    usados: set[tuple[str, str]] = set()
    for d in atual.linhas:
        a = indice_antes.get((d.chave_tabela, d.chave_linha))
        if a is None or (a.chave_tabela, a.chave_linha) in usados:
            candidatos = [c for c in por_rotulo_antes.get(d.chave_linha, [])
                          if (c.chave_tabela, c.chave_linha) not in usados]
            a = candidatos[0] if len(candidatos) == 1 else None
        if a is None:
            novo(operacao="adicao", tipo="tabela", pagina_antes=None, pagina_depois=d.pagina,
                 secao=d.secao, antes="", depois=d.texto(), titulo=d.titulo,
                 unidade=d.unidade, cabecalho_depois=d.cabecalho, rotulo=d.rotulo)
            continue
        usados.add((a.chave_tabela, a.chave_linha))
        credito = any(t in chave(f"{d.titulo} {d.rotulo}") for t in _CREDITO)
        mudancas: list[dict] = []
        reapresentacao = False
        if a.unidade == d.unidade:
            ja, jd = _principal(a, anterior.trimestre), _principal(d, atual.trimestre)
            if ja is not None and jd is not None:
                na, nd = ler_numero(a.celulas[ja]), ler_numero(d.celulas[jd])
                if na is not None and nd is not None:
                    m = mudanca_numerica(na, nd, credito)
                    if not m["igual"]:
                        mudancas.append({**m, "coluna": "principal"})
            for j, p in enumerate(d.periodos):
                if p and p in a.periodos:
                    na = ler_numero(a.celulas[a.periodos.index(p)])
                    nd = ler_numero(d.celulas[j])
                    if na is not None and nd is not None:
                        m = mudanca_numerica(na, nd, credito, unidades_de_tolerancia=1.0)
                        if not m["igual"]:
                            reapresentacao = True
                            mudancas.append({**m, "coluna": f"mesmo_periodo:{p}"})
        if not mudancas and esqueleto(a.texto()) == esqueleto(d.texto()):
            continue
        if not mudancas and a.celulas == d.celulas:
            continue
        novo(operacao="alteracao", tipo="tabela", pagina_antes=a.pagina, pagina_depois=d.pagina,
             secao=d.secao or a.secao, antes=a.texto(), depois=d.texto(), titulo=d.titulo,
             unidade=d.unidade, cabecalho_antes=a.cabecalho, cabecalho_depois=d.cabecalho,
             rotulo=d.rotulo, mudancas_numericas=mudancas, reapresentacao=reapresentacao)
    for a in anterior.linhas:
        if (a.chave_tabela, a.chave_linha) not in usados:
            novo(operacao="remocao", tipo="tabela", pagina_antes=a.pagina, pagina_depois=None,
                 secao=a.secao, antes=a.texto(), depois="", titulo=a.titulo,
                 unidade=a.unidade, cabecalho_antes=a.cabecalho, rotulo=a.rotulo)
    return eventos


# --- B0 e B1 -----------------------------------------------------------------------------

def _pagina(ev: Evento) -> int:
    return ev.pagina_depois if ev.pagina_depois is not None else (ev.pagina_antes or 0)


def ordenar_b0(eventos: Iterable[Evento]) -> list[Evento]:
    """Massa de tokens alterados; desempate estável por página e id."""
    return sorted(eventos, key=lambda e: (-e.massa, _pagina(e), e.id))


def chave_b1(ev: Evento) -> tuple:
    return (not ev.nivel1, not ev.nivel2, not ev.nivel3, -ev.massa, -ev.distancia,
            _pagina(ev), ev.id)


def ordenar_b1(eventos: Iterable[Evento]) -> list[Evento]:
    """Lexicográfico do CAND-02, sem peso aprendido."""
    return sorted(eventos, key=chave_b1)


# --- métricas ----------------------------------------------------------------------------

GANHO = {0: 0.0, 1: 1.0, 2: 3.0}


def dcg(ganhos: Sequence[float], k: int) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(ganhos[:k]))


def ndcg(ordem_ids: Sequence[str], ganho_por_id: dict[str, float], k: int) -> float | None:
    """nDCG@k sobre os eventos julgados. Evento não julgado conta ganho zero;
    o ideal usa todos os julgados do par. Sem ganho positivo, `None`."""
    ideal = sorted(ganho_por_id.values(), reverse=True)
    idcg = dcg(ideal, k)
    if idcg <= 0:
        return None
    return dcg([ganho_por_id.get(i, 0.0) for i in ordem_ids], k) / idcg
