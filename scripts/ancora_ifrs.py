"""Lê o lucro em IFRS das demonstrações publicadas em separado (âncora do G4).

**O problema que este módulo resolve.** O painel vem do arquivo da CVM, que para
estes emissores está em **IFRS** (Resolução CMN 4.818/2020). O relatório
gerencial do Itaú e do Bradesco publica a ponte BRGAAP→IFRS e por isso ancora o
gate sozinho; o do **BB**, do **BTG** e do **Santander** não publica, e comparar
o painel com a linha contábil deles é comparar bases diferentes. A CMN 4.818/2020
obriga os três a publicar demonstrações consolidadas em IFRS **em separado**, e é
dessa peça — a mesma base do arquivo da CVM, impressa por um documento que não é
o release — que sai a âncora daqui.

**Três armadilhas de leitura, e como cada uma é fechada.**

1. *A ordem das colunas não é convenção.* No BB o acumulado do exercício vem
   primeiro e o trimestre isolado depois; no BTG e no Santander é o contrário.
   Ler por posição acertaria três documentos e erraria três, com número
   plausível. Por isso a coluna do trimestre e a do acumulado são identificadas
   pela **identidade aritmética entre documentos**: `acumulado(t) −
   trimestre(t) = acumulado(t−1)`, onde o acumulado anterior vem do documento do
   trimestre anterior. Se mais de um par de colunas satisfizer a identidade, ou
   nenhum, o módulo levanta erro em vez de escolher.
2. *O 4º trimestre não é publicado.* A peça anual traz só o exercício, então o
   4T sai de `exercício − 9 meses` e é marcado como **derivado** — a mesma
   aritmética que o painel usa (RN10), e o gate compara derivado com derivado.
3. *Fonte ilegível é ausência de evidência, não zero.* A demonstração anual do
   BTG vem com fonte embutida sem mapa de caracteres: `pdfplumber` (e o
   `pdftotext` do Poppler) devolvem marcadores de glifo no lugar de letras e
   algarismos. O módulo **mede** isso e devolve o motivo, para o gate registrar
   "sem âncora, porque o documento não é legível" em vez de silenciar a célula.

Toda leitura é feita **por página**: o parser numérico do projeto falha fechado
em texto de documento inteiro, e a procedência exigida pelo gate é por célula.
"""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
DIR_IFRS = RAIZ_PROJETO / "corpus" / "ifrs"
MANIFESTO_IFRS = DIR_IFRS / "manifesto_ifrs.csv"

# Trimestres da janela do corpus (pesquisa técnica 2.4). O `1T2025` também é
# baixado, mas só como **semente** da cadeia: é o acumulado que fecha o 2T.
TRIMESTRES_CORPUS: tuple[str, ...] = ("2T2025", "3T2025", "4T2025", "1T2026")

# Números impressos nas demonstrações: sempre com separador de milhar, o que já
# descarta índice de nota explicativa (`26`, `9.a`) sem precisar de heurística.
# Parênteses são o sinal negativo da convenção contábil.
PADRAO_NUMERO = re.compile(r"\(?\s*\d{1,3}(?:\.\d{3})+\s*\)?")

PADRAO_ANO = re.compile(r"\b(20\d{2})\b")

# Marcador que o extrator devolve quando a fonte embutida não tem mapa para
# Unicode. Contar isso é a diferença entre "o documento não diz" e "não consegui
# ler o documento".
PADRAO_GLIFO_SEM_MAPA = re.compile(r"\(cid:\d+\)")

MIL = 1_000.0


class LeituraIFRSError(RuntimeError):
    """A demonstração não permite ler a linha sem adivinhar — falha em vez de chutar."""


# --------------------------------------------------------------------------- #
# Texto
# --------------------------------------------------------------------------- #


def normalizar(texto: str) -> str:
    """Minúscula, sem acento e sem espaço repetido — para casar rótulo de linha."""
    decomposto = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def proporcao_ilegivel(texto: str) -> float:
    """Fração do texto ocupada por glifos sem mapa para Unicode (0,0 a 1,0)."""
    if not texto:
        return 0.0
    ilegivel = sum(len(m.group(0)) for m in PADRAO_GLIFO_SEM_MAPA.finditer(texto))
    return ilegivel / len(texto)


def numeros_da_linha(linha: str) -> tuple[float, ...]:
    """Valores de uma linha, na escala impressa (milhares de reais).

    `(3.558)` vira −3558. Índice de nota não vira número porque não tem
    separador de milhar.
    """
    valores: list[float] = []
    for casado in PADRAO_NUMERO.finditer(linha):
        bruto = casado.group(0).strip()
        negativo = bruto.startswith("(")
        digitos = bruto.strip("()").strip().replace(".", "")
        valores.append(-float(digitos) if negativo else float(digitos))
    return tuple(valores)


def rotulo_da_linha(linha: str) -> str:
    """Texto normalizado que antecede o primeiro número da linha."""
    casado = PADRAO_NUMERO.search(linha)
    return normalizar(linha[: casado.start()] if casado else linha)


# Rótulos das três linhas que interessam. São `search` sobre o rótulo
# normalizado, e cada um exige a palavra que o distingue da linha vizinha: sem o
# `lucro` antes de `atribuivel a controladora`, o *Total do Resultado Abrangente
# Atribuível à Controladora* entraria no lugar do resultado.
ROTULO_CONSOLIDADO = re.compile(
    r"lucro liquido (?:consolidado )?do (?:periodo|exercicio)"
)
ROTULO_CONTROLADORES = re.compile(
    r"(?:^|\b)(?:lucro liquido )?atribuivel aos acionistas controladores"
    r"|^lucro atribuivel a controladora"
)
ROTULO_NAO_CONTROLADORES = re.compile(
    r"atribuivel aos acionistas nao controladores"
    r"|atribuivel as participacoes nao[- ]controladoras"
)

# Tolerância das identidades, na escala impressa (milhares de reais). Uma
# unidade cobre o arredondamento de cada parcela já publicada arredondada; o
# Santander imprime `5.036.867` onde `1.928.066 + 3.108.800` dá `5.036.866`.
TOLERANCIA_MIL = 1.5


@dataclass(frozen=True)
class LinhasDRE:
    """As três linhas de resultado de uma demonstração, já em colunas."""

    consolidado: tuple[float, ...]
    controladores: tuple[float, ...]
    nao_controladores: tuple[float, ...]
    cabecalho: tuple[str, ...]
    rotulo_controladores: str

    @property
    def colunas(self) -> int:
        return len(self.controladores)

    def identidade_fecha(self, coluna: int) -> bool:
        """`consolidado = controladores + não controladores` na coluna dada."""
        soma = self.controladores[coluna] + self.nao_controladores[coluna]
        return abs(self.consolidado[coluna] - soma) <= TOLERANCIA_MIL


def ler_dre_da_pagina(texto: str) -> LinhasDRE | None:
    """Extrai as três linhas de resultado de UMA página, ou `None` se não houver.

    Devolve `None` — e não erro — quando a página simplesmente não é a
    demonstração do resultado: quem varre o documento precisa distinguir "não é
    aqui" de "é aqui e está ilegível".
    """
    linhas = texto.splitlines()
    achados: dict[str, tuple[float, ...]] = {}
    rotulo_controladores = ""
    cabecalho: list[str] = []
    for linha in linhas:
        valores = numeros_da_linha(linha)
        rotulo = rotulo_da_linha(linha)
        if not valores:
            cabecalho.append(linha)
            continue
        if ROTULO_CONSOLIDADO.search(rotulo):
            achados.setdefault("consolidado", valores)
        elif ROTULO_CONTROLADORES.search(rotulo):
            if "controladores" not in achados:
                rotulo_controladores = rotulo
            achados.setdefault("controladores", valores)
        elif ROTULO_NAO_CONTROLADORES.search(rotulo):
            achados.setdefault("nao_controladores", valores)
        else:
            if "consolidado" not in achados:
                cabecalho.append(linha)
    if len(achados) != 3:
        return None
    tamanhos = {len(v) for v in achados.values()}
    if len(tamanhos) != 1:
        raise LeituraIFRSError(
            "as três linhas de resultado têm números de colunas diferentes: "
            f"{ {k: len(v) for k, v in achados.items()} }"
        )
    return LinhasDRE(
        consolidado=achados["consolidado"],
        controladores=achados["controladores"],
        nao_controladores=achados["nao_controladores"],
        cabecalho=tuple(cabecalho),
        rotulo_controladores=rotulo_controladores,
    )


def anos_das_colunas(cabecalho: tuple[str, ...], colunas: int) -> tuple[int, ...]:
    """Anos das colunas, lidos da última linha de cabeçalho que os nomeia todos.

    "última" porque o título costuma citar anos em prosa (*Períodos findos em 31
    de março de 2026 e de 2025*) antes de a linha de rótulos das colunas
    aparecer; é a de baixo que está alinhada com os números.
    """
    for linha in reversed(cabecalho):
        # **O texto original vem primeiro, e a ordem não é estilo.** Colar os
        # espaços antes de procurar funde `1º Trimestre/2025 1º Trimestre/2024`
        # em `...Trimestre/20251ºTrimestre/2024`: o `2025` passa a ser seguido
        # de `1`, a fronteira de palavra de `\b(20\d{2})\b` deixa de valer e o
        # ano some. Isso derrubava a leitura do BB e do Santander inteiros.
        #
        # A colagem sobrevive só como **último recurso**, para o caso em que o
        # extrator parte o próprio ano com um espaço espúrio (`Exercício/20 25`),
        # que nenhuma fronteira de palavra recupera. Medido em 2026-08-11: dos
        # 14 documentos legíveis do manifesto, todos resolvem pelo texto
        # original — inclusive `No ta 3 0/06/2025`, onde a barra já basta de
        # fronteira. O recurso fica porque é barato e só age quando o caminho
        # principal falhou.
        anos = tuple(int(a) for a in PADRAO_ANO.findall(linha))
        if len(anos) != colunas:
            anos = tuple(int(a) for a in PADRAO_ANO.findall(linha.replace(" ", "")))
        if len(anos) == colunas:
            return anos
    raise LeituraIFRSError(
        f"nenhuma linha de cabeçalho nomeia {colunas} períodos: {cabecalho[-4:]}"
    )


def coluna_do_ano(anos: tuple[int, ...], alvo: int) -> int:
    """Índice da única coluna do ano pedido; ambiguidade é erro, não escolha."""
    indices = [i for i, ano in enumerate(anos) if ano == alvo]
    if len(indices) != 1:
        raise LeituraIFRSError(
            f"o ano {alvo} aparece em {len(indices)} colunas de {anos} — "
            "a leitura por rótulo não decide"
        )
    return indices[0]


def separar_trimestre_e_acumulado(
    dre: LinhasDRE, acumulado_anterior: float
) -> tuple[int, int]:
    """Descobre qual coluna é o trimestre e qual é o acumulado do exercício.

    Usa a única identidade que não depende de convenção de diagramação nem do
    valor que o gate quer confirmar: `acumulado(t) − trimestre(t)` tem de
    reproduzir o acumulado publicado no documento do trimestre **anterior**.
    Exige solução única.
    """
    pares = [
        (j_q, j_a)
        for j_a in range(dre.colunas)
        for j_q in range(dre.colunas)
        if j_a != j_q
        and abs(
            (dre.controladores[j_a] - dre.controladores[j_q]) - acumulado_anterior
        )
        <= TOLERANCIA_MIL
    ]
    if len(pares) != 1:
        raise LeituraIFRSError(
            f"a identidade acumulado − trimestre = {acumulado_anterior:.0f} "
            f"não separa as colunas: {len(pares)} pares candidatos"
        )
    return pares[0]


# --------------------------------------------------------------------------- #
# Documento
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DemonstracaoIFRS:
    """Uma demonstração publicada, já reduzida à página do resultado."""

    empresa: str
    periodo: str
    documento: str
    pagina: int
    dre: LinhasDRE


@dataclass(frozen=True)
class DocumentoIlegivel:
    """A peça existe, foi baixada e não pode ser lida — motivo registrado."""

    empresa: str
    periodo: str
    documento: str
    motivo: str


def ler_demonstracao(
    caminho: Path, empresa: str, periodo: str, documento: str
) -> DemonstracaoIFRS | DocumentoIlegivel:
    """Acha a página da demonstração do resultado e lê as três linhas.

    Quando mais de uma página se qualifica, vence a **primeira** cuja identidade
    `controladores + não controladores = consolidado` fecha em todas as colunas:
    a demonstração do resultado abrangente repete rótulos parecidos, e a
    identidade é o que separa uma da outra sem depender de título.
    """
    import pdfplumber

    ilegiveis = 0
    total = 0
    with pdfplumber.open(caminho) as pdf:
        for indice, pagina in enumerate(pdf.pages, start=1):
            texto = pagina.extract_text() or ""
            total += 1
            if proporcao_ilegivel(texto) > 0.5:
                ilegiveis += 1
                continue
            dre = ler_dre_da_pagina(texto)
            if dre is None:
                continue
            if not all(dre.identidade_fecha(j) for j in range(dre.colunas)):
                continue
            return DemonstracaoIFRS(
                empresa=empresa,
                periodo=periodo,
                documento=documento,
                pagina=indice,
                dre=dre,
            )
    if total and ilegiveis / total > 0.5:
        return DocumentoIlegivel(
            empresa=empresa,
            periodo=periodo,
            documento=documento,
            motivo=(
                f"{ilegiveis} de {total} páginas sem mapa de caracteres na fonte "
                "embutida — pdfplumber e pdftotext devolvem marcador de glifo no "
                "lugar de letras e algarismos; ler exigiria OCR pago"
            ),
        )
    return DocumentoIlegivel(
        empresa=empresa,
        periodo=periodo,
        documento=documento,
        motivo="demonstração do resultado não localizada no documento",
    )


# --------------------------------------------------------------------------- #
# Cadeia de períodos
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AncoraIFRS:
    """O lucro em IFRS de um trimestre, com procedência.

    `valor_reais` é o dos **controladores** — a convenção de mercado e o padrão
    da spec 5.5. As outras duas linhas do trio viajam junto porque são o que
    permite ao gate dizer *onde* uma divergência mora: quando o total consolidado
    bate e a atribuição não, o defeito está na repartição entre sócios, e isso é
    medição, não interpretação.
    """

    empresa: str
    trimestre: str
    valor_reais: float
    derivado: bool
    tolerancia_reais: float
    procedencia: str
    consolidado_reais: float | None = None
    nao_controladores_reais: float | None = None


def milhar(valor: float) -> str:
    """`12766035` → `12.766.035`, com o separador de milhar pt-BR.

    Existe como função porque a forma óbvia — `f"...{v:,.0f}...".replace(",", ".")`
    aplicada à frase inteira — troca também as vírgulas da prosa e devolve
    procedência ilegível (`documento. pág. 7. linha ...`).
    """
    return f"{valor:,.0f}".replace(",", ".")


def _procedencia(
    demonstracao: DemonstracaoIFRS, coluna: int, anos: tuple[int, ...] | None = None
) -> str:
    valor = demonstracao.dre.controladores[coluna]
    rotulo_coluna = "" if anos is None else f", coluna do exercício {anos[coluna]}"
    return (
        f"{demonstracao.documento}, pág. {demonstracao.pagina}, linha "
        f"“{demonstracao.dre.rotulo_controladores}”{rotulo_coluna}, "
        f"célula {milhar(valor)} (R$ mil)"
    )


def resolver_cadeia(
    empresa: str,
    demonstracoes: dict[str, DemonstracaoIFRS | DocumentoIlegivel],
) -> tuple[dict[str, AncoraIFRS], dict[str, str]]:
    """Resolve o lucro IFRS de cada trimestre da janela do corpus.

    Devolve `(âncoras, motivos_de_ausência)`. Nada é estimado: um período sem
    documento legível sai na segunda estrutura, com o motivo, e o gate o
    registra como ausência de âncora.
    """
    ancoras: dict[str, AncoraIFRS] = {}
    ausencias: dict[str, str] = {}

    def obter(periodo: str) -> DemonstracaoIFRS | None:
        item = demonstracoes.get(periodo)
        if isinstance(item, DemonstracaoIFRS):
            return item
        if item is None:
            ausencias[periodo] = "demonstração em IFRS não baixada"
        else:
            ausencias[periodo] = item.motivo
        return None

    def trio(demonstracao: DemonstracaoIFRS, coluna: int) -> tuple[float, float, float]:
        """`(controladores, consolidado, não controladores)` de uma coluna."""
        return (
            demonstracao.dre.controladores[coluna],
            demonstracao.dre.consolidado[coluna],
            demonstracao.dre.nao_controladores[coluna],
        )

    # Semente: o 1T do exercício é o próprio acumulado, e a coluna sai do ano.
    semente = obter("1T2025")
    acumulado: tuple[float, float, float] | None = None
    if semente is not None:
        anos = anos_das_colunas(semente.dre.cabecalho, semente.dre.colunas)
        acumulado = trio(semente, coluna_do_ano(anos, 2025))

    for periodo, anterior in (("2T2025", "1T2025"), ("3T2025", "2T2025")):
        demonstracao = obter(periodo)
        if demonstracao is None or acumulado is None:
            if acumulado is None and periodo not in ausencias:
                ausencias[periodo] = f"cadeia interrompida em {anterior}"
            acumulado = None
            continue
        coluna_q, coluna_a = separar_trimestre_e_acumulado(
            demonstracao.dre, acumulado[0]
        )
        controladores, consolidado, nao_controladores = trio(demonstracao, coluna_q)
        ancoras[periodo] = AncoraIFRS(
            empresa=empresa,
            trimestre=periodo,
            valor_reais=controladores * MIL,
            derivado=False,
            tolerancia_reais=0.5 * MIL,
            procedencia=(
                f"{_procedencia(demonstracao, coluna_q)}; coluna do trimestre "
                f"isolado identificada pela identidade acumulado − trimestre = "
                f"acumulado publicado em {anterior}"
            ),
            consolidado_reais=consolidado * MIL,
            nao_controladores_reais=nao_controladores * MIL,
        )
        acumulado = trio(demonstracao, coluna_a)

    anual = obter("4T2025")
    if anual is not None and acumulado is not None:
        anos = anos_das_colunas(anual.dre.cabecalho, anual.dre.colunas)
        coluna = coluna_do_ano(anos, 2025)
        exercicio = trio(anual, coluna)
        ancoras["4T2025"] = AncoraIFRS(
            empresa=empresa,
            trimestre="4T2025",
            valor_reais=(exercicio[0] - acumulado[0]) * MIL,
            derivado=True,
            # Duas parcelas impressas ⇒ duas meias-unidades.
            tolerancia_reais=1.0 * MIL,
            procedencia=(
                f"{_procedencia(anual, coluna, anos)} − acumulado de nove meses "
                f"({milhar(acumulado[0])} R$ mil); 4T não é publicado — derivado, "
                "como o do painel (RN10)"
            ),
            consolidado_reais=(exercicio[1] - acumulado[1]) * MIL,
            nao_controladores_reais=(exercicio[2] - acumulado[2]) * MIL,
        )
    elif anual is not None and "4T2025" not in ausencias:
        ausencias["4T2025"] = "cadeia do acumulado de nove meses interrompida"

    primeiro_2026 = obter("1T2026")
    if primeiro_2026 is not None:
        anos = anos_das_colunas(
            primeiro_2026.dre.cabecalho, primeiro_2026.dre.colunas
        )
        coluna = coluna_do_ano(anos, 2026)
        conferencia = ""
        if semente is not None and 2025 in anos:
            comparativo = primeiro_2026.dre.controladores[coluna_do_ano(anos, 2025)]
            anos_semente = anos_das_colunas(
                semente.dre.cabecalho, semente.dre.colunas
            )
            publicado = semente.dre.controladores[coluna_do_ano(anos_semente, 2025)]
            if abs(comparativo - publicado) > TOLERANCIA_MIL:
                raise LeituraIFRSError(
                    f"{empresa}: a coluna comparativa de 2025 no documento de "
                    f"1T2026 ({comparativo:.0f}) não reproduz o 1T2025 publicado "
                    f"({publicado:.0f}) — a ordem das colunas não é a suposta"
                )
            conferencia = (
                "; coluna comparativa confere com o 1T2025 publicado, o que "
                "fixa a ordem das colunas"
            )
        controladores, consolidado, nao_controladores = trio(primeiro_2026, coluna)
        ancoras["1T2026"] = AncoraIFRS(
            empresa=empresa,
            trimestre="1T2026",
            valor_reais=controladores * MIL,
            derivado=False,
            tolerancia_reais=0.5 * MIL,
            procedencia=_procedencia(primeiro_2026, coluna, anos) + conferencia,
            consolidado_reais=consolidado * MIL,
            nao_controladores_reais=nao_controladores * MIL,
        )
    return ancoras, ausencias


# --------------------------------------------------------------------------- #
# Manifesto — a evidência do gate é pinada por hash
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ItemManifesto:
    """Uma peça baixada, com a procedência que a torna auditável."""

    empresa: str
    cd_cvm: str
    periodo: str
    documento: str
    arquivo: str
    url: str
    data_download: str
    hash_sha256: str


def carregar_manifesto(caminho: Path = MANIFESTO_IFRS) -> tuple[ItemManifesto, ...]:
    """Lê `corpus/ifrs/manifesto_ifrs.csv`, a fonte de verdade destas peças.

    O manifesto é versionado; os PDFs não (a mesma regra do resto do corpus). Ele
    é o que permite a alguém refazer o gate meses depois e provar que leu **o
    mesmo documento** — as demonstrações são republicadas sem aviso.
    """
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return tuple(
            ItemManifesto(
                empresa=linha["empresa"],
                cd_cvm=linha["cd_cvm"],
                periodo=linha["periodo"],
                documento=linha["documento"],
                arquivo=linha["arquivo"],
                url=linha["url"],
                data_download=linha["data_download"],
                hash_sha256=linha["hash_sha256"],
            )
            for linha in csv.DictReader(arquivo)
        )


def hash_do_arquivo(caminho: Path) -> str:
    """SHA-256 do arquivo, lido em blocos (as peças passam de 8 MB)."""
    digestor = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            digestor.update(bloco)
    return digestor.hexdigest()


def carregar_demonstracoes(
    empresa: str,
    manifesto: tuple[ItemManifesto, ...],
    diretorio: Path = DIR_IFRS / "raw",
) -> dict[str, DemonstracaoIFRS | DocumentoIlegivel]:
    """Lê as peças de uma companhia, **conferindo o hash antes de ler**.

    Hash divergente não é lido: seria o gate mudando de veredito sozinho porque
    o emissor republicou o PDF depois do congelamento (risco 15d do projeto). A
    peça vira ausência com motivo explícito — visível no relatório —, nunca uma
    âncora silenciosamente diferente da que foi registrada.
    """
    demonstracoes: dict[str, DemonstracaoIFRS | DocumentoIlegivel] = {}
    for item in manifesto:
        if item.empresa != empresa:
            continue
        caminho = diretorio / item.arquivo
        if not caminho.exists():
            demonstracoes[item.periodo] = DocumentoIlegivel(
                empresa=empresa,
                periodo=item.periodo,
                documento=item.documento,
                motivo=(
                    f"{item.arquivo} está no manifesto mas não no disco — "
                    "rebaixe pelo script de download antes de rodar o gate"
                ),
            )
            continue
        obtido = hash_do_arquivo(caminho)
        if obtido != item.hash_sha256:
            demonstracoes[item.periodo] = DocumentoIlegivel(
                empresa=empresa,
                periodo=item.periodo,
                documento=item.documento,
                motivo=(
                    f"hash de {item.arquivo} não confere com o manifesto "
                    f"(esperado {item.hash_sha256[:12]}…, obtido {obtido[:12]}…) "
                    "— a peça no disco não é a que foi registrada"
                ),
            )
            continue
        demonstracoes[item.periodo] = ler_demonstracao(
            caminho, empresa, item.periodo, item.documento
        )
    return demonstracoes


def carregar_ancoras(
    manifesto: tuple[ItemManifesto, ...] | None = None,
    diretorio: Path = DIR_IFRS / "raw",
) -> tuple[dict[tuple[str, str], AncoraIFRS], dict[tuple[str, str], str]]:
    """Resolve a âncora IFRS de cada companhia × trimestre do manifesto.

    Devolve `(âncoras, ausências)` chaveadas por `(empresa, trimestre)`. Só a
    janela do corpus sai: o `1T2025` é semente da cadeia, não célula do gate.
    """
    itens = carregar_manifesto() if manifesto is None else manifesto
    ancoras: dict[tuple[str, str], AncoraIFRS] = {}
    ausencias: dict[tuple[str, str], str] = {}
    for empresa in sorted({item.empresa for item in itens}):
        demonstracoes = carregar_demonstracoes(empresa, itens, diretorio)
        resolvidas, faltantes = resolver_cadeia(empresa, demonstracoes)
        for trimestre in TRIMESTRES_CORPUS:
            if trimestre in resolvidas:
                ancoras[(empresa, trimestre)] = resolvidas[trimestre]
            elif trimestre in faltantes:
                ausencias[(empresa, trimestre)] = faltantes[trimestre]
    return ancoras, ausencias
