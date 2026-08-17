"""Gate G4 — o mapa semântico resolve a linha certa do lucro? (spec 5.5, RN09)

O gate tem duas partes e só a segunda estava pendente.

**Parte A — mapa × conferência congelada.** `conferir_mapa_g4` compara o mapa
resolvido pela carga contra `CONFERENCIA_G4`: os cinco bancos resolvem o
conceito certo e `3.09` e `3.11` não são tratados como equivalentes. Já estava
aprovada; aqui é reexecutada para que o relatório não repouse em memória.

**Parte B — bloqueante — painel × linha contábil da tabela de conciliação.**
A pesquisa técnica 2.1 é explícita sobre a armadilha da formulação óbvia: ancorar
o gate no **número de capa** do release reprovaria os cinco bancos, porque a capa
traz o gerencial/ajustado e a tese do projeto é justamente que ele não bate com o
contábil — por definição, não por erro. Por isso a âncora é a **linha do
resultado contábil da tabela de conciliação** publicada no próprio relatório
gerencial.

Esta passagem só ficou possível depois do OCR do corpus (2026-08-11): o texto de
cada release está em `corpus/ocr/<hash>.json`, com as tabelas reconstruídas em
markdown. O gate lê esse cache, nunca a rede, e roda a custo zero.

**Achado que muda a leitura do resultado (medido aqui, 2026-08-11).** Existe uma
terceira base contábil além do par gerencial × contábil que o projeto já
documenta: a conciliação dos releases parte do **BRGAAP/COSIF**, enquanto as
demonstrações consolidadas arquivadas na CVM — a fonte do painel — estão em
**IFRS** (Resolução CMN 4.818/2020; o BB declara isso em texto nas notas do
próprio release). Onde o release publica a ponte BRGAAP→IFRS (Itaú e Bradesco), o
painel casa com a linha IFRS **até o último dígito impresso**. Onde o release não
publica essa ponte (BB, BTG e Santander), a comparação contra a linha contábil
compara duas bases diferentes e **não decide nada**.

**A âncora que faltava a esses três (integrada em 2026-08-11).** A mesma CMN
4.818/2020 obriga cada emissor a publicar demonstrações consolidadas em IFRS
**em separado**. Elas foram baixadas para `corpus/ifrs/`, com URL, data e
SHA-256 em `manifesto_ifrs.csv`, e `scripts/ancora_ifrs.py` as lê resolvendo a
cadeia trimestral por identidade aritmética entre documentos — nunca por posição
de coluna, porque a ordem entre isolado e acumulado muda de emissor para
emissor. O gate confere o hash antes de abrir cada peça: uma demonstração
republicada depois do congelamento vira ausência com motivo, nunca âncora
silenciosamente diferente da registrada.

**A distinção que o veredito carrega.** *Sem âncora* é ausência de evidência;
*divergente* é evidência medida que não bate. As duas impedem a aprovação, por
motivos opostos, e o relatório nunca as funde. Quando uma célula diverge, o gate
ainda pergunta **onde** — se o total consolidado bate e só a atribuição entre
sócios não, e se o trio do painel fecha entre si — para separar defeito de mapa
de defeito da origem do dado.

Nada aqui ajusta o mapa nem descarta célula: o módulo é somente-leitura sobre
`src/mapa_contas.py` e sobre o painel. Um mapa ajustado até o número fechar seria
um rótulo errado treinando um modelo confiantemente errado, que é o que o G4
existe para impedir.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import ancora_ifrs  # noqa: E402
from src.config import RAIZ_PROJETO  # noqa: E402
from src.dados_estruturados import conferir_mapa_g4  # noqa: E402
from src.mapa_contas import (  # noqa: E402
    BANCOS_CORPUS,
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_LUCRO_NAO_CONTROLADORES,
    normalizar_ds_conta,
)
from src.normalizacao import normalizar_numero_ptbr  # noqa: E402

DIR_CACHE_OCR = RAIZ_PROJETO / "corpus" / "ocr"
CAMINHO_PAINEL = RAIZ_PROJETO / "artefatos" / "cvm.duckdb"
DESTINO = RAIZ_PROJETO / "resultados" / "gate_g4.md"

# Janela do corpus (pesquisa técnica 2.4), na ordem cronológica.
TRIMESTRES_CORPUS: tuple[str, ...] = ("2T2025", "3T2025", "4T2025", "1T2026")

# Deslocamentos de coluna admitidos ao realinhar uma tabela que o OCR entregou
# com uma célula a mais. Só um deles pode explicar a âncora, e a âncora é sempre
# outro número do MESMO documento — nunca o valor do painel.
DESLOCAMENTOS_ADMITIDOS: tuple[int, ...] = (0, 1, -1)


class ExtracaoAmbiguaError(RuntimeError):
    """A tabela não permite ler a célula sem adivinhar — falha em vez de chutar."""


# --------------------------------------------------------------------------- #
# Tabelas em markdown
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TabelaMarkdown:
    """Uma tabela de pipes reconstruída pelo OCR, já dividida em células.

    As linhas de cabeçalho não são separadas das de dados de propósito: o
    Santander publica o rótulo `Contábil` na **segunda** linha de cabeçalho e o
    Itaú na primeira. Quem procura uma coluna varre todas as linhas e usa a que
    casar, o que dispensa saber de antemão quantos níveis de cabeçalho a tabela
    tem.
    """

    pagina: int
    linhas: tuple[tuple[str, ...], ...]


_SEPARADOR_TABELA = re.compile(r"^\|[\s:|-]*\|$")


def _dividir_linha(bruta: str) -> tuple[str, ...]:
    corpo = bruta.strip()
    corpo = corpo[1:] if corpo.startswith("|") else corpo
    corpo = corpo[:-1] if corpo.endswith("|") else corpo
    return tuple(celula.strip() for celula in corpo.split("|"))


def tabelas_da_pagina(markdown: str, pagina: int = 0) -> tuple[TabelaMarkdown, ...]:
    """Quebra o markdown de UMA página nas tabelas de pipes que ela contém.

    Trabalha sempre por página, nunca por documento inteiro: o parser numérico do
    projeto falha fechado em texto grande (as 476 mil chars do Itaú 1T2026 rendem
    zero números) e a sentinela da spec 5.4 é definida por página de qualquer
    forma.
    """
    tabelas: list[TabelaMarkdown] = []
    acumulado: list[tuple[str, ...]] = []
    for bruta in markdown.splitlines():
        texto = bruta.strip()
        if texto.startswith("|") and texto.endswith("|") and texto.count("|") >= 2:
            if _SEPARADOR_TABELA.fullmatch(texto):
                continue
            acumulado.append(_dividir_linha(texto))
            continue
        if acumulado:
            tabelas.append(TabelaMarkdown(pagina=pagina, linhas=tuple(acumulado)))
            acumulado = []
    if acumulado:
        tabelas.append(TabelaMarkdown(pagina=pagina, linhas=tuple(acumulado)))
    return tuple(tabelas)


_MARCAS_MARKDOWN = re.compile(r"[*\\]+")
_NOTA_DE_RODAPE = re.compile(r"\^\{[^}]*\}|\[\]")


def normalizar_rotulo(celula: str) -> str:
    """Reduz uma célula à forma comparável, sem as marcas do markdown/OCR.

    Remove ênfase (`**`), barras invertidas que o Bradesco usa como marcador de
    lista (`\\\\ Lucro Líquido`) e marcadores de nota (`^{1}`), e então aplica a
    mesma normalização de `DS_CONTA` usada pelo mapa semântico — sem acento, sem
    pontuação, minúscula. O prefixo `II`, que o OCR produz no lugar do bullet do
    Banco do Brasil, **não** é removido aqui: quem quiser tolerá-lo declara isso
    no próprio padrão da receita, para que a tolerância fique visível.
    """
    limpo = _NOTA_DE_RODAPE.sub(" ", celula or "")
    limpo = _MARCAS_MARKDOWN.sub(" ", limpo)
    return normalizar_ds_conta(limpo)


def valor_da_celula(celula: str) -> float | None:
    """Lê o número de UMA célula, com o parser pt-BR do projeto.

    Célula é texto curto, então a guarda de notação ambígua não dispara — é
    exatamente o modo de uso para o qual `extrair_numeros_ptbr` foi escrito.
    `(1.465)` vira −1465 e `-` vira `None`.
    """
    limpo = _MARCAS_MARKDOWN.sub("", celula or "").strip()
    if not limpo or limpo in {"-", "--", "—"}:
        return None
    return normalizar_numero_ptbr(limpo)


def casas_decimais(celula: str) -> int:
    """Quantas casas decimais o release imprimiu nesta célula.

    Define a meia-unidade do último dígito, que é a tolerância legítima ao
    comparar um valor impresso em R$ milhões com o painel em reais. Sem isso a
    escolha da tolerância seria arbitrária — e tolerância arbitrária é onde um
    gate esconde erro.
    """
    limpo = _MARCAS_MARKDOWN.sub("", celula or "")
    casado = re.search(r",(\d+)", limpo)
    return len(casado.group(1)) if casado else 0


def _fmt(valor: float | None, casas: int = 1) -> str:
    """Formata em pt-BR: ponto no milhar, vírgula no decimal."""
    if valor is None:
        return "—"
    return (
        f"{valor:,.{casas}f}"
        .replace(",", "\x00")
        .replace(".", ",")
        .replace("\x00", ".")
    )


def _sinal(valor: float | None, casas: int = 1) -> str:
    """Como `_fmt`, mas sempre com sinal explícito — é sempre um delta."""
    if valor is None:
        return "—"
    return ("+" if valor >= 0 else "−") + _fmt(abs(valor), casas)


# --------------------------------------------------------------------------- #
# Localização de célula dentro da tabela
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CelulaLocalizada:
    """Uma célula lida da tabela, com tudo que um humano precisa para auditá-la."""

    pagina: int
    rotulo_linha: str
    rotulo_coluna: str
    bruto: str
    valor: float
    deslocamento: int = 0

    @property
    def meia_unidade(self) -> float:
        return 0.5 * (10.0 ** (-casas_decimais(self.bruto)))


def _indice_da_coluna(
    tabela: TabelaMarkdown, padrao: re.Pattern[str]
) -> tuple[int, int]:
    """Devolve `(linha_do_cabecalho, coluna)` da primeira célula que casar."""
    achados = [
        (i, j)
        for i, linha in enumerate(tabela.linhas)
        for j, celula in enumerate(linha)
        if padrao.fullmatch(normalizar_rotulo(celula))
    ]
    if not achados:
        raise ExtracaoAmbiguaError(f"coluna não encontrada: {padrao.pattern!r}")
    if len({j for _, j in achados}) > 1:
        raise ExtracaoAmbiguaError(
            f"coluna {padrao.pattern!r} casou em posições diferentes: "
            f"{sorted({j for _, j in achados})}"
        )
    return achados[0]


def _indice_da_linha(tabela: TabelaMarkdown, padrao: re.Pattern[str]) -> int:
    achados = [
        i
        for i, linha in enumerate(tabela.linhas)
        if linha and padrao.fullmatch(normalizar_rotulo(linha[0]))
    ]
    if not achados:
        raise ExtracaoAmbiguaError(f"linha não encontrada: {padrao.pattern!r}")
    return achados[0]


def ler_celula(
    tabela: TabelaMarkdown,
    padrao_linha: re.Pattern[str],
    padrao_coluna: re.Pattern[str],
    deslocamento: int = 0,
) -> CelulaLocalizada:
    """Lê a célula no cruzamento de uma linha e de uma coluna nomeadas.

    Exige que a linha de dados tenha o mesmo número de células da linha de
    cabeçalho usada para achar a coluna. Quando não tem, a leitura por índice
    seria um chute com aparência de número — e é aí que nasce o valor plausível e
    errado que este projeto inteiro persegue. Nesse caso o erro é levantado.
    """
    i_cabecalho, j = _indice_da_coluna(tabela, padrao_coluna)
    i_linha = _indice_da_linha(tabela, padrao_linha)
    cabecalho = tabela.linhas[i_cabecalho]
    dados = tabela.linhas[i_linha]
    if len(dados) != len(cabecalho):
        raise ExtracaoAmbiguaError(
            f"linha {padrao_linha.pattern!r} tem {len(dados)} células e o "
            f"cabeçalho tem {len(cabecalho)}: leitura por índice seria chute"
        )
    alvo = j + deslocamento
    if not 0 <= alvo < len(dados):
        raise ExtracaoAmbiguaError(
            f"deslocamento {deslocamento} sai da linha {padrao_linha.pattern!r}"
        )
    bruto = dados[alvo]
    valor = valor_da_celula(bruto)
    if valor is None:
        raise ExtracaoAmbiguaError(
            f"célula sem número em {padrao_linha.pattern!r} × "
            f"{padrao_coluna.pattern!r}: {bruto!r}"
        )
    return CelulaLocalizada(
        pagina=tabela.pagina,
        rotulo_linha=normalizar_rotulo(dados[0]),
        rotulo_coluna=normalizar_rotulo(cabecalho[j]),
        bruto=bruto,
        valor=valor,
        deslocamento=deslocamento,
    )


# --------------------------------------------------------------------------- #
# Receitas de extração, banco a banco
# --------------------------------------------------------------------------- #


def _p(expressao: str) -> re.Pattern[str]:
    return re.compile(expressao)


# Rótulo da linha do lucro em cada release. `fullmatch` de propósito: no Banco do
# Brasil a linha `Lucro Líquido Ajustado` fica logo acima da linha `Lucro
# Líquido`, e casamento parcial pegaria a errada. O prefixo `ii` é o bullet do BB
# que o OCR transcreveu como letras — tolerado aqui, e só aqui, de forma visível.
LINHA_LUCRO_CONTABIL: dict[str, re.Pattern[str]] = {
    "BB": _p(r"(?:ii )?lucro liquido"),
    "BRADESCO": _p(r"lucro liquido"),
    "BTG": _p(r"lucro liquido"),
    "ITAU": _p(r"lucro liquido"),
    "SANTANDER": _p(r"lucro liquido"),
}

# Coluna do resultado contábil. O Santander e o Itaú nomeiam a coluna `Contábil`;
# o BTG a nomeia `1T 2026 Contábil`; o BB usa o rótulo do trimestre, porque a
# tabela é a própria DRE societária com realocações — e realocação, por
# definição, não muda o lucro líquido; o Bradesco nomeia `DRE Gerencial` a coluna
# cujo lucro líquido é o contábil, o que a nota explicativa 37 do mesmo documento
# confirma ao publicar `DRE Contábil` e `DRE Gerencial` com o mesmo lucro.
COLUNA_CONTABIL: dict[str, re.Pattern[str]] = {
    "BRADESCO": _p(r"dre gerencial( \d+)?"),
    "BTG": _p(r"(?:.* )?contabil"),
    "ITAU": _p(r"contabil"),
    "SANTANDER": _p(r"contabil"),
}

# Coluna do número gerencial/ajustado — medição NÃO bloqueante (pesquisa 2.1):
# registra o delta contábil × gerencial por banco e trimestre, que já é metade do
# gabarito do subconjunto de reconciliação. `{q}` é substituído pelo rótulo do
# trimestre no formato do release ("1t 2026"): o BTG publica duas colunas
# `Ajustado` na mesma tabela — a do trimestre e a do acumulado do ano —, e um
# padrão frouxo casaria as duas, o que o gate recusa por ambiguidade.
COLUNA_GERENCIAL: dict[str, str] = {
    "BB": r"{q_curto}",
    "BRADESCO": r"dre recorrente( \d+)?",
    "BTG": r"{q} ajustado",
    "ITAU": r"gerencial",
    "SANTANDER": r"gerencial",
}

# No Banco do Brasil o número gerencial não é outra coluna e sim outra **linha**:
# a tabela é a própria DRE societária, e o destaque do release é o `Lucro Líquido
# Ajustado`, logo acima da linha contábil.
LINHA_LUCRO_GERENCIAL: dict[str, re.Pattern[str]] = {
    "BB": _p(r"(?:ii )?lucro liquido ajustado"),
}


def rotulo_trimestre(trimestre: str, curto: bool = False) -> str:
    """`2T2025` → `2t 2025` (como o BTG imprime) ou `2t25` (como BB e Itaú)."""
    numero, ano = trimestre[0], trimestre[2:]
    return f"{numero.lower()}t{ano[-2:]}" if curto else f"{numero.lower()}t {ano}"

# Título da página que carrega a tabela de conciliação, por banco.
PAGINA_CONCILIACAO: dict[str, re.Pattern[str]] = {
    "BB": _p(r"demonstracao do resultado com realocacoes"),
    "BRADESCO": _p(r"composicao analitica"),
    "BTG": _p(r"lucro liquido e roae ajustado"),
    "ITAU": _p(r"conciliacao entre o resultado contabil e gerencial"),
    "SANTANDER": _p(r"reconciliacao dos resultados contabil e gerencial"),
}

# Ponte BRGAAP → IFRS, onde o release a publica. O painel vem do arquivo da CVM,
# que está em IFRS (Resolução CMN 4.818/2020); é esta tabela que torna as duas
# bases comparáveis. BB, BTG e Santander não a publicam no release.
PAGINA_PONTE_IFRS: dict[str, re.Pattern[str]] = {
    "BRADESCO": _p(r"comparativo brgaap x ifrs"),
    "ITAU": _p(r"comparativo brgaap. e ifrs"),
}

LINHA_PONTE: dict[str, dict[str, re.Pattern[str]]] = {
    "BRADESCO": {
        "brgaap": _p(r"brgaap"),
        "ifrs_controladores": _p(r"ifrs"),
    },
}

# Rótulo esperado da linha de IFRS na ponte do Itaú. É conferido **quando o OCR
# preservou o rótulo**; em 2T2025 e 3T2025 ele se perdeu, e a linha é
# identificada pela aritmética da própria tabela (ver
# `extrair_ponte_por_identidade`).
ROTULO_IFRS_ITAU = _p(r"ifrs valores atribuiveis aos acionistas controladores")

# Rótulo da coluna do período em cada tabela, por banco e trimestre. O Bradesco
# publica a ponte em valores **acumulados** (1S25, 9M25, 12M25); o trimestre
# isolado sai da diferença entre dois documentos do próprio corpus, e o custo
# disso é somar as duas meias-unidades de arredondamento.
COLUNA_PERIODO: dict[str, str] = {
    "2T2025": "2t25",
    "3T2025": "3t25",
    "4T2025": "4t25",
    "1T2026": "1t26",
}

ACUMULADO_BRADESCO: dict[str, str] = {
    "2T2025": "1s25",
    "3T2025": "9m25",
    "4T2025": "12m25",
    "1T2026": "1t26",
}

# Trimestre isolado = acumulado deste documento − acumulado do anterior.
ANTERIOR_BRADESCO: dict[str, str] = {
    "3T2025": "2T2025",
    "4T2025": "3T2025",
}


# --------------------------------------------------------------------------- #
# Leitura do cache de OCR
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DocumentoOCR:
    documento: str
    empresa: str
    trimestre: str
    hash_pdf: str
    paginas: tuple[tuple[int, str], ...]


def carregar_cache_ocr(diretorio: Path = DIR_CACHE_OCR) -> tuple[DocumentoOCR, ...]:
    """Lê o cache versionado de OCR; não toca em rede nem em PDF."""
    documentos: list[DocumentoOCR] = []
    for caminho in sorted(diretorio.glob("*.json")):
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        paginas = tuple(
            (int(pagina.get("index", i)), pagina.get("markdown") or "")
            for i, pagina in enumerate(dados["ocr"].get("pages") or [])
        )
        documentos.append(
            DocumentoOCR(
                documento=dados["documento"],
                empresa=dados["empresa"],
                trimestre=dados["trimestre"],
                hash_pdf=dados.get("hash_pdf", ""),
                paginas=paginas,
            )
        )
    return tuple(documentos)


def paginas_que_casam(
    documento: DocumentoOCR, padrao: re.Pattern[str]
) -> tuple[tuple[int, str], ...]:
    return tuple(
        (indice, markdown)
        for indice, markdown in documento.paginas
        if padrao.search(normalizar_rotulo(markdown))
    )


def _tabelas_candidatas(
    documento: DocumentoOCR, padrao_pagina: re.Pattern[str]
) -> tuple[TabelaMarkdown, ...]:
    tabelas: list[TabelaMarkdown] = []
    for indice, markdown in paginas_que_casam(documento, padrao_pagina):
        tabelas.extend(tabelas_da_pagina(markdown, pagina=indice))
    return tuple(tabelas)


def _primeira_leitura(
    tabelas: tuple[TabelaMarkdown, ...],
    padrao_linha: re.Pattern[str],
    padrao_coluna: re.Pattern[str],
    deslocamento: int = 0,
) -> CelulaLocalizada:
    erros: list[str] = []
    for tabela in tabelas:
        try:
            return ler_celula(tabela, padrao_linha, padrao_coluna, deslocamento)
        except ExtracaoAmbiguaError as exc:
            erros.append(f"pág. {tabela.pagina}: {exc}")
    raise ExtracaoAmbiguaError("; ".join(erros) or "nenhuma tabela candidata")


# --------------------------------------------------------------------------- #
# Extração por documento
# --------------------------------------------------------------------------- #


# De onde veio a linha IFRS que ancora a célula. A distinção não é decorativa:
# a ponte é publicada pelo próprio release que também traz o número contábil, e a
# demonstração em separado é outra peça, com outro hash e outra data de download.
# Quem audita o gate meses depois precisa saber qual das duas leu.
FONTE_PONTE_RELEASE = "ponte BRGAAP→IFRS do próprio release"
FONTE_DEMONSTRACAO_SEPARADA = "demonstração consolidada em IFRS publicada em separado"


@dataclass(frozen=True)
class LeituraRelease:
    """O que o release publica sobre o lucro deste trimestre.

    Os campos `ifrs_*` guardam a âncora na base do painel, venha ela da ponte do
    próprio release (Itaú, Bradesco) ou da demonstração em IFRS publicada em
    separado (BB, BTG, Santander). `ifrs_ausencia` guarda o **motivo** de não
    haver âncora, que é informação diferente de não haver campo preenchido:
    "o emissor não publica" e "a peça existe e não é legível" levam a decisões
    diferentes de quem for fechar o gate.
    """

    documento: str
    empresa: str
    trimestre: str
    contabil: CelulaLocalizada | None = None
    gerencial: CelulaLocalizada | None = None
    ifrs_controladores: float | None = None
    ifrs_consolidado: float | None = None
    ifrs_nao_controladores: float | None = None
    ifrs_tolerancia: float = 0.0
    ifrs_procedencia: str = ""
    ifrs_fonte: str = FONTE_PONTE_RELEASE
    ifrs_ausencia: str = ""
    notas: tuple[str, ...] = ()


def extrair_contabil(documento: DocumentoOCR) -> tuple[CelulaLocalizada | None, str]:
    """Lê a linha do resultado contábil da tabela de conciliação do release."""
    banco = documento.empresa
    tabelas = _tabelas_candidatas(documento, PAGINA_CONCILIACAO[banco])
    if not tabelas:
        return None, "página da tabela de conciliação não localizada"
    coluna = COLUNA_CONTABIL.get(banco) or _p(COLUNA_PERIODO[documento.trimestre])
    try:
        return _primeira_leitura(tabelas, LINHA_LUCRO_CONTABIL[banco], coluna), ""
    except ExtracaoAmbiguaError as exc:
        return None, str(exc)


def extrair_gerencial(documento: DocumentoOCR) -> CelulaLocalizada | None:
    """Lê o número gerencial/ajustado — medição não bloqueante."""
    banco = documento.empresa
    modelo = COLUNA_GERENCIAL.get(banco)
    if modelo is None:
        return None
    coluna = _p(
        modelo.format(
            q=rotulo_trimestre(documento.trimestre),
            q_curto=rotulo_trimestre(documento.trimestre, curto=True),
        )
    )
    linha = LINHA_LUCRO_GERENCIAL.get(banco, LINHA_LUCRO_CONTABIL[banco])
    tabelas = _tabelas_candidatas(documento, PAGINA_CONCILIACAO[banco])
    try:
        return _primeira_leitura(tabelas, linha, coluna)
    except ExtracaoAmbiguaError:
        return None


@dataclass(frozen=True)
class PonteIdentidade:
    """A ponte BRGAAP→IFRS lida sem depender do rótulo da linha."""

    pagina: int
    linha_brgaap: int
    linha_ifrs: int
    deslocamento: int
    controladores: float
    nao_controladores: float
    consolidado: float
    tolerancia: float
    rotulo_conferido: bool


# Tolerância da identidade `controladores + não controladores = consolidado`
# dentro da tabela: três valores já arredondados para R$ milhões na fonte.
TOLERANCIA_IDENTIDADE_MI = 1.5


def extrair_ponte_por_identidade(
    tabela: TabelaMarkdown,
    padrao_coluna: re.Pattern[str],
    ancora: float,
    tolerancia_ancora: float,
) -> PonteIdentidade:
    """Identifica as linhas de IFRS pela aritmética da própria tabela.

    O OCR **perdeu os rótulos de linha** da ponte do Itaú em 2T2025 e 3T2025:
    sobraram só os números, e em 3T2025/4T2025 ainda por cima deslocados de uma
    coluna porque a tabela vizinha de patrimônio líquido vazou para dentro. Ler
    por índice de cabeçalho devolveria `207.164` (patrimônio) no lugar de
    `11.561` (resultado) — número plausível, não nulo e errado, que é
    exatamente o que este gate existe para impedir.

    A identificação usa duas âncoras, **ambas do próprio documento**:

    1. a linha do BRGAAP é a única cuja célula, em algum deslocamento admitido,
       reproduz a linha contábil da conciliação da página inicial do release;
    2. abaixo dela, o trio de linhas consecutivas em que
       `controladores + não controladores = consolidado` — a identidade que a
       própria tabela publica — é único.

    Nenhuma das duas usa valor do painel: realinhar a tabela pelo número que se
    quer confirmar seria ajustar o instrumento ao resultado.
    """
    _, j = _indice_da_coluna(tabela, padrao_coluna)

    ancoras = [
        (i, deslocamento)
        for deslocamento in DESLOCAMENTOS_ADMITIDOS
        for i, linha in enumerate(tabela.linhas)
        if 0 <= j + deslocamento < len(linha)
        and (valor := valor_da_celula(linha[j + deslocamento])) is not None
        and abs(valor - ancora) <= tolerancia_ancora
    ]
    if len(ancoras) != 1:
        raise ExtracaoAmbiguaError(
            f"a linha BRGAAP não é única na tabela: {len(ancoras)} candidatas "
            f"para a âncora {ancora}"
        )
    i_brgaap, deslocamento = ancoras[0]

    def valor_em(i: int) -> float | None:
        linha = tabela.linhas[i]
        alvo = j + deslocamento
        return valor_da_celula(linha[alvo]) if 0 <= alvo < len(linha) else None

    trios: list[tuple[int, float, float, float]] = []
    for k in range(i_brgaap + 1, len(tabela.linhas) - 2):
        a, b, c = valor_em(k), valor_em(k + 1), valor_em(k + 2)
        if a is None or b is None or c is None:
            continue
        if abs(a + b - c) <= TOLERANCIA_IDENTIDADE_MI:
            trios.append((k, a, b, c))
    if len(trios) != 1:
        raise ExtracaoAmbiguaError(
            f"a identidade controladores+não controladores=consolidado não "
            f"identifica um trio único: {len(trios)} candidatos"
        )
    k, controladores, nao_controladores, consolidado = trios[0]
    rotulo = normalizar_rotulo(tabela.linhas[k][0])
    bruto_ifrs = tabela.linhas[k][j + deslocamento]
    return PonteIdentidade(
        pagina=tabela.pagina,
        linha_brgaap=i_brgaap,
        linha_ifrs=k,
        deslocamento=deslocamento,
        controladores=controladores,
        nao_controladores=nao_controladores,
        consolidado=consolidado,
        tolerancia=0.5 * (10.0 ** (-casas_decimais(bruto_ifrs))),
        rotulo_conferido=bool(ROTULO_IFRS_ITAU.fullmatch(rotulo)),
    )


def extrair_ponte_itau(
    documento: DocumentoOCR, ancora: CelulaLocalizada
) -> tuple[float | None, float | None, float, str]:
    """Lê a ponte BRGAAP→IFRS do Itaú.

    Devolve `(ifrs_controladores, ifrs_consolidado, tolerancia, procedência)`.
    """
    tabelas = _tabelas_candidatas(documento, PAGINA_PONTE_IFRS["ITAU"])
    rotulo_coluna = COLUNA_PERIODO[documento.trimestre]
    coluna = _p(rotulo_coluna)
    for tabela in tabelas:
        try:
            ponte = extrair_ponte_por_identidade(
                tabela, coluna, ancora.valor, ancora.meia_unidade
            )
        except ExtracaoAmbiguaError:
            continue
        identidade = (
            f"{_fmt(ponte.controladores, 0)} + "
            f"{_fmt(ponte.nao_controladores, 0)} = "
            f"{_fmt(ponte.consolidado, 0)}"
        )
        procedencia = (
            f"ponte BRGAAP→IFRS, pág. {ponte.pagina}, coluna {rotulo_coluna}, "
            f"linhas {ponte.linha_ifrs}–{ponte.linha_ifrs + 2} ({identidade})"
        )
        procedencia += (
            "; rótulo da linha conferido"
            if ponte.rotulo_conferido
            else "; rótulo perdido no OCR — linha identificada pela identidade "
            "da própria tabela"
        )
        if ponte.deslocamento:
            procedencia += (
                f"; tabela realinhada em {ponte.deslocamento:+d} coluna pela "
                "linha BRGAAP, fixada pela conciliação do próprio release"
            )
        return ponte.controladores, ponte.consolidado, ponte.tolerancia, procedencia
    return None, None, 0.0, ""


def _acumulado_bradesco(
    documento: DocumentoOCR, linha: re.Pattern[str], rotulo: str
) -> CelulaLocalizada:
    tabelas = _tabelas_candidatas(documento, PAGINA_PONTE_IFRS["BRADESCO"])
    return _primeira_leitura(tabelas, linha, _p(rotulo))


def extrair_ponte_bradesco(
    documento: DocumentoOCR, anteriores: dict[str, DocumentoOCR]
) -> tuple[float | None, float | None, float, str]:
    """Lê a ponte BRGAAP→IFRS do Bradesco, que é publicada em acumulado.

    O trimestre isolado sai da diferença entre o acumulado deste documento e o do
    documento do trimestre anterior — os dois no corpus, os dois auditáveis. A
    tolerância vira a soma das duas meias-unidades, porque cada parcela já vem
    arredondada para R$ milhões na fonte.
    """
    linha = LINHA_PONTE["BRADESCO"]["ifrs_controladores"]
    rotulo = ACUMULADO_BRADESCO[documento.trimestre]
    try:
        atual = _acumulado_bradesco(documento, linha, rotulo)
    except ExtracaoAmbiguaError:
        return None, None, 0.0, ""

    if documento.trimestre == "1T2026":
        return (
            atual.valor,
            None,
            atual.meia_unidade,
            f"ponte BRGAAP→IFRS, pág. {atual.pagina}, coluna {rotulo}",
        )

    if documento.trimestre == "2T2025":
        # 1S25 − 1T25; o 1T25 vem da coluna comparativa do release do 1T2026.
        anterior = anteriores.get("1T2026")
        rotulo_anterior = "1t25"
    else:
        anterior = anteriores.get(ANTERIOR_BRADESCO[documento.trimestre])
        rotulo_anterior = ACUMULADO_BRADESCO[ANTERIOR_BRADESCO[documento.trimestre]]
    if anterior is None:
        return None, None, 0.0, ""
    try:
        base = _acumulado_bradesco(anterior, linha, rotulo_anterior)
    except ExtracaoAmbiguaError:
        return None, None, 0.0, ""
    return (
        atual.valor - base.valor,
        None,
        atual.meia_unidade + base.meia_unidade,
        (
            f"ponte BRGAAP→IFRS: {rotulo} (pág. {atual.pagina} de "
            f"{documento.documento}) − {rotulo_anterior} (pág. {base.pagina} de "
            f"{anterior.documento})"
        ),
    )


def ler_release(
    documento: DocumentoOCR, por_trimestre: dict[str, DocumentoOCR]
) -> LeituraRelease:
    """Junta tudo que o release publica sobre o lucro contábil do trimestre."""
    contabil, motivo = extrair_contabil(documento)
    notas: list[str] = []
    if contabil is None:
        notas.append(f"linha contábil não extraída — {motivo}")
    gerencial = extrair_gerencial(documento)

    ifrs_ctrl = ifrs_cons = None
    tolerancia = 0.0
    procedencia = ""
    if documento.empresa == "ITAU" and contabil is not None:
        ifrs_ctrl, ifrs_cons, tolerancia, procedencia = extrair_ponte_itau(
            documento, contabil
        )
    elif documento.empresa == "BRADESCO":
        ifrs_ctrl, ifrs_cons, tolerancia, procedencia = extrair_ponte_bradesco(
            documento, por_trimestre
        )
    return LeituraRelease(
        documento=documento.documento,
        empresa=documento.empresa,
        trimestre=documento.trimestre,
        contabil=contabil,
        gerencial=gerencial,
        ifrs_controladores=ifrs_ctrl,
        ifrs_consolidado=ifrs_cons,
        ifrs_tolerancia=tolerancia,
        ifrs_procedencia=procedencia,
        notas=tuple(notas),
    )


# --------------------------------------------------------------------------- #
# Comparação com o painel
# --------------------------------------------------------------------------- #

MILHAO = 1_000_000.0

SITUACAO_CONFERIDO_IFRS = "CONFERIDO (linha IFRS da ponte do próprio release)"
SITUACAO_CONFERIDO_IFRS_SEPARADA = (
    "CONFERIDO (linha IFRS da demonstração publicada em separado)"
)
SITUACAO_CONFERIDO_CONTABIL = "CONFERIDO (linha contábil da conciliação)"
SITUACAO_SEM_ANCORA = "SEM ÂNCORA (release não publica linha na base do painel)"
SITUACAO_SEM_ANCORA_ILEGIVEL = "SEM ÂNCORA (demonstração em IFRS não legível)"
SITUACAO_DIVERGENTE = "DIVERGENTE"
SITUACAO_SEM_EXTRACAO = "SEM EXTRAÇÃO"

SITUACAO_CONFERIDO_POR_FONTE: dict[str, str] = {
    FONTE_PONTE_RELEASE: SITUACAO_CONFERIDO_IFRS,
    FONTE_DEMONSTRACAO_SEPARADA: SITUACAO_CONFERIDO_IFRS_SEPARADA,
}


def aplicar_ancora_externa(
    leitura: LeituraRelease,
    ancora: "ancora_ifrs.AncoraIFRS | None",
    ausencia: str = "",
) -> LeituraRelease:
    """Anexa à leitura a âncora IFRS vinda de fora do release.

    Só age sobre emissor que **não publica a ponte no próprio release**. O
    critério é o emissor, declarado em `PAGINA_PONTE_IFRS` — não o resultado da
    extração. A diferença importa: se a leitura da ponte do Itaú falhasse num
    trimestre e o gate caísse silenciosamente noutro documento, a mesma coluna
    do relatório passaria a comparar duas evidências distintas conforme o dia,
    e ninguém veria. Bridge que falha vira erro visível, nunca troca de fonte.

    Sem âncora, o motivo é preservado: o gate precisa distinguir "o emissor não
    publica esta linha" de "a peça foi baixada e não é legível".
    """
    if leitura.empresa in PAGINA_PONTE_IFRS or leitura.ifrs_controladores is not None:
        return leitura
    if ancora is None:
        return replace(leitura, ifrs_ausencia=ausencia)

    def em_milhoes(valor: float | None) -> float | None:
        return None if valor is None else valor / MILHAO

    return replace(
        leitura,
        ifrs_controladores=ancora.valor_reais / MILHAO,
        ifrs_consolidado=em_milhoes(ancora.consolidado_reais),
        ifrs_nao_controladores=em_milhoes(ancora.nao_controladores_reais),
        ifrs_tolerancia=ancora.tolerancia_reais / MILHAO,
        ifrs_procedencia=ancora.procedencia,
        ifrs_fonte=FONTE_DEMONSTRACAO_SEPARADA,
    )


def diagnosticar_divergencia(
    leitura: LeituraRelease,
    painel_consolidado: float | None,
    gap_fechamento_reais: float | None,
) -> str:
    """Localiza a divergência entre painel e âncora — medindo, não supondo.

    Duas perguntas, ambas respondidas por número do próprio material:

    1. O **total consolidado** do painel bate com o da âncora? Se bate, o que
       diverge não é o resultado do período e sim a repartição dele entre sócios
       controladores e não controladores.
    2. O trio do painel **fecha entre si** (`consolidado = controladores + não
       controladores`)? Se não fecha, o arquivo da CVM se contradiz nesta célula,
       e um mapa que resolveu o conceito certo não tem como salvar o número.

    Nada aqui conserta o painel. Um mapa ajustado até o número fechar seria o
    rótulo errado treinando um modelo confiantemente errado.
    """
    partes: list[str] = []
    if painel_consolidado is not None and leitura.ifrs_consolidado is not None:
        delta_total = painel_consolidado / MILHAO - leitura.ifrs_consolidado
        if abs(delta_total) <= max(leitura.ifrs_tolerancia, 1e-9):
            partes.append(
                "O total consolidado do painel reproduz o da âncora "
                f"({_fmt(leitura.ifrs_consolidado)} R$ mi, Δ = "
                f"{_sinal(delta_total, 3)}): o que diverge é a **atribuição** "
                "entre sócios controladores e não controladores, não o resultado "
                "do período"
            )
        else:
            partes.append(
                f"O total consolidado do painel também diverge da âncora "
                f"(Δ = {_sinal(delta_total)} R$ mi)"
            )
    if gap_fechamento_reais is not None and abs(gap_fechamento_reais) > 1_000:
        partes.append(
            "e o próprio arquivo da CVM não fecha nesta célula — consolidado − "
            f"(controladores + não controladores) = "
            f"{_sinal(gap_fechamento_reais / 1_000, 0)} R$ mil —, o que localiza o "
            "defeito na origem do dado, não no mapa semântico"
        )
    return "; ".join(partes)


@dataclass(frozen=True)
class Conferencia:
    """Uma célula do gate: um banco, um trimestre, um veredito."""

    empresa: str
    trimestre: str
    documento: str
    origem_painel: str
    painel_controladores: float | None
    painel_consolidado: float | None
    contabil_release: float | None
    gerencial_release: float | None
    ifrs_release: float | None
    situacao: str
    ifrs_fonte: str = ""
    detalhe: str = ""
    procedencia: str = ""
    notas: tuple[str, ...] = field(default_factory=tuple)
    # Busca pelo valor do painel no release inteiro; só é preenchida quando a
    # situação é SEM ÂNCORA, para medir a ausência em vez de afirmá-la.
    varredura: "Varredura | None" = None

    @property
    def aprovado(self) -> bool:
        return self.situacao.startswith("CONFERIDO")

    @property
    def reprovado(self) -> bool:
        return self.situacao == SITUACAO_DIVERGENTE

    @property
    def sem_ancora(self) -> bool:
        """Ausência de evidência — que **não** é evidência que diverge."""
        return self.situacao.startswith("SEM ÂNCORA")

    def delta_ifrs_mi(self) -> float | None:
        if self.painel_controladores is None or self.ifrs_release is None:
            return None
        return self.painel_controladores / MILHAO - self.ifrs_release

    def delta_contabil_mi(self) -> float | None:
        if self.painel_controladores is None or self.contabil_release is None:
            return None
        return self.painel_controladores / MILHAO - self.contabil_release

    def delta_gerencial_mi(self) -> float | None:
        if self.contabil_release is None or self.gerencial_release is None:
            return None
        return self.gerencial_release - self.contabil_release


def classificar(
    leitura: LeituraRelease,
    painel_controladores: float | None,
    painel_consolidado: float | None,
    origem_painel: str,
    gap_fechamento_reais: float | None = None,
) -> Conferencia:
    """Decide o veredito de um banco × trimestre, sem arredondar a favor.

    A ordem das perguntas importa. Primeiro a linha contábil da conciliação —
    é a âncora que a pesquisa técnica 2.1 prescreve. Se ela não bate, a segunda
    pergunta é se existe âncora na base do painel: a ponte BRGAAP→IFRS do próprio
    release (Itaú, Bradesco) ou a demonstração em IFRS publicada em separado (BB,
    BTG, Santander). Se existe e bate, o mapa está certo e a diferença contra a
    conciliação é de base contábil. Se existe e **não** bate, o gate reprova a
    célula — e `diagnosticar_divergencia` mede *onde* está a diferença, sem
    mexer no painel. Se não existe âncora, o gate declara que não sabe, que é
    diferente de aprovar.
    """
    comum = {
        "empresa": leitura.empresa,
        "trimestre": leitura.trimestre,
        "documento": leitura.documento,
        "origem_painel": origem_painel,
        "painel_controladores": painel_controladores,
        "painel_consolidado": painel_consolidado,
        "contabil_release": leitura.contabil.valor if leitura.contabil else None,
        "gerencial_release": leitura.gerencial.valor if leitura.gerencial else None,
        "ifrs_release": leitura.ifrs_controladores,
        "ifrs_fonte": leitura.ifrs_fonte if leitura.ifrs_controladores else "",
        "notas": leitura.notas,
    }
    if leitura.contabil is None or painel_controladores is None:
        return Conferencia(
            **comum,
            situacao=SITUACAO_SEM_EXTRACAO,
            detalhe="sem linha contábil no release ou sem conceito no painel",
        )

    painel_mi = painel_controladores / MILHAO
    delta_contabil = painel_mi - leitura.contabil.valor
    procedencia = (
        f"conciliação contábil × gerencial, pág. {leitura.contabil.pagina}, "
        f"linha “{leitura.contabil.rotulo_linha}”, coluna "
        f"“{leitura.contabil.rotulo_coluna}”, célula {leitura.contabil.bruto!r}"
    )
    if abs(delta_contabil) <= leitura.contabil.meia_unidade:
        detalhe = (
            f"Δ = {_sinal(delta_contabil, 3)} R$ mi, dentro da meia-unidade do "
            f"último dígito impresso ({_fmt(leitura.contabil.meia_unidade, 3)})"
        )
        if leitura.ifrs_controladores is not None:
            detalhe += (
                f"; neste trimestre a linha IFRS da ponte coincide com a "
                f"contábil ({_fmt(leitura.ifrs_controladores)} R$ mi), logo as "
                "duas bases dão o mesmo número"
            )
        return Conferencia(
            **comum,
            situacao=SITUACAO_CONFERIDO_CONTABIL,
            detalhe=detalhe,
            procedencia=procedencia,
        )

    if leitura.ifrs_controladores is None:
        base = (
            f"Δ contra a linha contábil = {_sinal(delta_contabil)} R$ mi "
            f"({_sinal(delta_contabil / leitura.contabil.valor * 100)}%); o "
            "release não publica a ponte BRGAAP→IFRS, e o arquivo da CVM "
            "está em IFRS — as duas grandezas não são comparáveis"
        )
        if leitura.ifrs_ausencia:
            return Conferencia(
                **comum,
                situacao=SITUACAO_SEM_ANCORA_ILEGIVEL,
                detalhe=(
                    f"{base}. A demonstração em IFRS publicada em separado, que "
                    f"seria a âncora, não pôde ser lida: {leitura.ifrs_ausencia}"
                ),
                procedencia=procedencia,
            )
        return Conferencia(
            **comum,
            situacao=SITUACAO_SEM_ANCORA,
            detalhe=base,
            procedencia=procedencia,
        )

    delta_ifrs = painel_mi - leitura.ifrs_controladores
    if abs(delta_ifrs) <= max(leitura.ifrs_tolerancia, 1e-9):
        return Conferencia(
            **comum,
            situacao=SITUACAO_CONFERIDO_POR_FONTE[leitura.ifrs_fonte],
            detalhe=(
                f"Δ contra a linha IFRS = {_sinal(delta_ifrs, 3)} R$ mi (tolerância "
                f"de arredondamento {_fmt(leitura.ifrs_tolerancia, 3)}); Δ contra "
                f"a linha contábil BRGAAP = {_sinal(delta_contabil)} R$ mi; âncora "
                f"na {leitura.ifrs_fonte}"
            ),
            procedencia=f"{procedencia}; {leitura.ifrs_procedencia}",
        )
    diagnostico = diagnosticar_divergencia(
        leitura, painel_consolidado, gap_fechamento_reais
    )
    return Conferencia(
        **comum,
        situacao=SITUACAO_DIVERGENTE,
        detalhe=(
            f"Δ contra a âncora IFRS = {_sinal(delta_ifrs)} R$ mi "
            f"({_sinal(delta_ifrs / leitura.ifrs_controladores * 100)}%), muito "
            f"além da tolerância de arredondamento "
            f"({_fmt(leitura.ifrs_tolerancia, 3)}); Δ contra a linha contábil "
            f"BRGAAP = {_sinal(delta_contabil)} R$ mi; âncora na "
            f"{leitura.ifrs_fonte}"
            + (f". {diagnostico}" if diagnostico else "")
        ),
        procedencia=f"{procedencia}; {leitura.ifrs_procedencia}",
    )


@dataclass(frozen=True)
class Varredura:
    """O que a busca pelo valor do painel encontrou no release inteiro."""

    paginas: tuple[int, ...]
    melhor_pagina: int | None
    melhor_valor: float | None
    melhor_distancia_pct: float | None


def varrer_valor_no_release(
    documento: DocumentoOCR, valor: float, tolerancia_pct: float = 0.05
) -> Varredura:
    """Varre o release atrás de QUALQUER número equivalente a `valor`.

    Serve a uma pergunta só, e ela é do tipo que só vale medida: quando o gate
    conclui que o release não publica linha na base do painel, esta varredura
    mostra que o número do painel de fato **não aparece** no documento — e não
    que ele esteja em outra tabela que a receita de extração não procurou.

    Trabalha **página a página** porque o parser pt-BR do projeto falha fechado
    em texto de documento inteiro (a guarda de notação ambígua dispara e ele
    devolve zero números). Tolera as três escalas de impressão (reais, R$ mil,
    R$ milhões).

    Devolve também o número **mais próximo** encontrado e a distância relativa
    até ele, porque a lista de páginas sozinha engana: em documento de trezentas
    páginas um número de quatro dígitos cai dentro de 0,05% por coincidência. Com
    a distância à vista, quem lê separa a coincidência (0,03% de um número que a
    demonstração imprimiria exato em R$ mil) da publicação de fato.
    """
    from src.normalizacao import extrair_numeros_ptbr, valores_equivalentes

    alvos = [valor, valor / 1e3, valor / 1e6]
    encontradas: list[int] = []
    melhor: tuple[float, int, float] | None = None
    for indice, markdown in documento.paginas:
        numeros = extrair_numeros_ptbr(markdown)
        if not numeros:
            continue
        casou = False
        for numero in numeros:
            for alvo in alvos:
                if alvo == 0:
                    continue
                distancia = abs(numero - alvo) / abs(alvo) * 100.0
                if melhor is None or distancia < melhor[0]:
                    melhor = (distancia, indice, numero)
                if valores_equivalentes(alvo, numero, tolerancia_pct):
                    casou = True
        if casou:
            encontradas.append(indice)
    return Varredura(
        paginas=tuple(encontradas),
        melhor_pagina=None if melhor is None else melhor[1],
        melhor_valor=None if melhor is None else melhor[2],
        melhor_distancia_pct=None if melhor is None else melhor[0],
    )


def lucros_do_painel(
    caminho: Path = CAMINHO_PAINEL,
) -> dict[tuple[str, str], tuple[float | None, float | None, float | None, str]]:
    """Lê `fatos_semanticos` — nunca `fatos_contabeis` (RN09, spec 5.5)."""
    import duckdb

    con = duckdb.connect(str(caminho), read_only=True)
    try:
        linhas = con.execute(
            f"""
            SELECT cd_cvm, trimestre,
                   max(CASE WHEN conceito = '{CONCEITO_LUCRO_CONTROLADORES}'
                            THEN valor_reais END),
                   max(CASE WHEN conceito = '{CONCEITO_LUCRO_CONSOLIDADO}'
                            THEN valor_reais END),
                   max(CASE WHEN conceito = '{CONCEITO_LUCRO_NAO_CONTROLADORES}'
                            THEN valor_reais END),
                   max(origem)
            FROM fatos_semanticos
            WHERE cd_cvm IN (SELECT unnest(?))
            GROUP BY cd_cvm, trimestre
            """,
            [[banco.cd_cvm for banco in BANCOS_CORPUS]],
        ).fetchall()
    finally:
        con.close()
    por_cd = {banco.cd_cvm: banco.banco for banco in BANCOS_CORPUS}
    return {
        (por_cd[cd_cvm], trimestre): (ctrl, cons, nao_ctrl, origem or "")
        for cd_cvm, trimestre, ctrl, cons, nao_ctrl, origem in linhas
    }


# --------------------------------------------------------------------------- #
# Relatório
# --------------------------------------------------------------------------- #


VEREDITO_APROVADO = "APROVADO"
VEREDITO_REPROVADO = "REPROVADO"
VEREDITO_PARCIAL = "PARCIAL"

# Causa apurada de cada célula divergente, registrada por quem a investigou.
#
# Existe para impedir a saída preguiçosa: uma divergência que ninguém entendeu
# não pode herdar a explicação da divergência ao lado. Célula divergente **sem**
# verbete aqui sai no relatório como "causa não identificada", em vez de sair
# com uma narrativa que soa boa e não foi apurada. Nada nesta tabela muda um
# número: ela é prosa auditável ao lado da medição, nunca no lugar dela.
_SEM_CAUSA = (
    "**divergência real, causa não identificada**. A medição está feita e não "
    "bate; ninguém apurou por quê. Este é o estado honesto de uma célula "
    "divergente ainda não investigada — e é diferente de ausência de âncora, "
    "porque aqui existe evidência e ela contradiz o painel."
)

INVESTIGACAO_DIVERGENCIA: dict[tuple[str, str], str] = {
    ("SANTANDER", "3T2025"): (
        "Erro na origem, localizado no arquivo da CVM e não no mapa. No ITR de "
        "`DT_REFER=2025-09-30` (`VERSAO=1`, `DT_RECEB=2025-10-29`), tanto no "
        "período acumulado (jan–set) quanto no trimestre isolado (jul–set), a "
        "conta `3.09` (`Lucro/Prejuízo Consolidado do Período`) reproduz a "
        "demonstração em IFRS **até o último milhar** — 9.021.926 e 3.882.410 "
        "R$ mil —, mas as contas filhas não: `3.09.01` traz 8.501.317 e "
        "3.464.450 onde a demonstração publica 8.865.071 e 3.828.204, e "
        "`3.09.02` traz 163.700 e 61.051 onde a demonstração publica 156.855 e "
        "54.206. O arquivo se contradiz sozinho: `3.09.01 + 3.09.02 − 3.09` dá "
        "−356.909 R$ mil nos dois períodos. Três hipóteses foram descartadas "
        "com evidência: (a) **erro de mapa** — o mesmo `mapa_contas`, no mesmo "
        "emissor, resolve 2T2025 e 1T2026 ao milhar exato, e a `DS_CONTA` "
        "resolvida (`Atribuído a Sócios da Empresa Controladora`) é a mesma "
        "linha que a demonstração rotula `Lucro atribuível à Controladora`; "
        "(b) **retificadora** — o conjunto ITR/DFP baixado (hash em "
        "`corpus/cvm/manifesto_cvm.csv`) traz apenas `VERSAO=1` para esse "
        "`DT_REFER`, embora traga `VERSAO=2` para o 1T2025 do mesmo emissor, o "
        "que mostra que a regra de maior versão está funcionando e que "
        "simplesmente não há reapresentação do 3T; (c) **outro conceito** — não "
        "há linha na DRE do próprio arquivo cujo valor seja 3.464.450, e a "
        "conta irmã diverge junto, o que exclui troca de conceito. A DFP anual "
        "do mesmo emissor **está certa**: `3.11.01` = 12.766.035 R$ mil, igual "
        "à demonstração em IFRS ao milhar, e fecha com `3.11.02`."
    ),
    ("SANTANDER", "4T2025"): (
        "Erro herdado, de sinal invertido. O 4T não existe como ITR e é "
        "derivado por `exercício − 9 meses` (RN10); como o subtraendo é o "
        "acumulado de nove meses defeituoso do 3T2025, a mesma diferença de "
        "363.754 R$ mil reaparece com o sinal trocado. O minuendo está correto "
        "(a DFP anual bate com a demonstração em IFRS ao milhar), e por isso os "
        "dois erros se anulam no total do exercício — que é justamente o que "
        "torna a falha invisível para quem só olha o número anual."
    ),
}

# Código de saída por veredito. `PARCIAL` **não** sai 0: o G4 é bloqueante, e
# sair 0 sem âncora faria um pipeline automatizado ler como aprovação o que é
# ausência de evidência.
SAIDA_POR_VEREDITO: dict[str, int] = {
    VEREDITO_APROVADO: 0,
    VEREDITO_REPROVADO: 1,
    VEREDITO_PARCIAL: 2,
}


def veredito_do_gate(conferencias: list[Conferencia], parte_a: str) -> str:
    """REPROVADO se algo diverge; PARCIAL se falta âncora; APROVADO só no resto."""
    if parte_a != VEREDITO_APROVADO:
        return VEREDITO_REPROVADO
    if any(c.reprovado for c in conferencias):
        return VEREDITO_REPROVADO
    if not conferencias or not all(c.aprovado for c in conferencias):
        return VEREDITO_PARCIAL
    return VEREDITO_APROVADO


def montar_relatorio(
    conferencias: list[Conferencia],
    parte_a: str,
    fechamento: list[tuple[str, str, float]],
) -> str:
    aprovadas = [c for c in conferencias if c.aprovado]
    reprovadas = [c for c in conferencias if c.reprovado]
    sem_ancora = [c for c in conferencias if c.sem_ancora]
    sem_extracao = [c for c in conferencias if c.situacao == SITUACAO_SEM_EXTRACAO]
    veredito = f"**{veredito_do_gate(conferencias, parte_a)}**"

    linhas = [
        "# Gate G4 — mapa semântico × linha contábil do release (spec 5.5, RN09)",
        "",
        "Medição local sobre o cache de OCR congelado (`corpus/ocr/`), as "
        "demonstrações em IFRS de `corpus/ifrs/` (conferidas por hash contra "
        "`manifesto_ifrs.csv` antes de cada leitura) e o painel "
        "`artefatos/cvm.duckdb`. Sem chamada de API, sem rede.",
        "",
        f"## Veredito: {veredito}",
        "",
        f"- Parte A (mapa × conferência congelada): **{parte_a}**",
        f"- Parte B (painel × âncora na mesma base contábil): "
        f"{len(aprovadas)}/{len(conferencias)} conferidos, "
        f"{len(reprovadas)} divergentes, {len(sem_ancora)} sem âncora, "
        f"{len(sem_extracao)} sem extração",
        "",
        "**Divergente e sem âncora não são a mesma coisa**, e o veredito depende "
        "de qual é qual. *Sem âncora* é ausência de evidência: nada foi medido, "
        "e aprovar seria inventar prova. *Divergente* é evidência medida que não "
        "bate: alguma coisa está errada e o gate diz qual número, contra qual "
        "documento e de quanto. Uma célula divergente reprova o gate; uma célula "
        "sem âncora o deixa incompleto.",
        "",
        "Bloqueiam o gate: "
        + (
            ", ".join(f"**{c.empresa} {c.trimestre}** (diverge)" for c in reprovadas)
            or "nenhuma célula por divergência"
        )
        + " · "
        + (
            ", ".join(f"**{c.empresa} {c.trimestre}** (sem âncora)" for c in sem_ancora)
            or "nenhuma célula por falta de âncora"
        )
        + ". A Parte A separa a pergunta que dá nome ao gate: o mapa semântico "
        "resolve o conceito certo em todos os emissores, e nenhuma das células "
        "abaixo é reprovada por erro de mapeamento. Quem consumir estes rótulos "
        "— o modelo preditivo da spec 5.10 em primeiro lugar — sabe nominalmente "
        f"quais células estão conferidas ({len(aprovadas)}), quais têm valor "
        f"errado medido ({len(reprovadas)}) e quais não foram medidas "
        f"({len(sem_ancora)}).",
        "",
        "## Banco a banco, trimestre a trimestre",
        "",
        "Valores em R$ milhões. `painel` é `fatos_semanticos."
        "lucro_liquido_controladores` (o padrão da spec 5.5, por ser a convenção "
        "de mercado); `contábil` é a linha do resultado contábil da tabela de "
        "conciliação do release, em BRGAAP; `âncora IFRS` é a linha na **mesma "
        "base do painel**, vinda da ponte do próprio release (Itaú, Bradesco) ou "
        "da demonstração em IFRS publicada em separado (BB, BTG, Santander); "
        "`gerencial` é a linha na coluna gerencial/ajustada — medição não "
        "bloqueante.",
        "",
        "| banco | trimestre | origem | painel | contábil (release) | "
        "Δ painel−contábil | âncora IFRS | Δ painel−IFRS | gerencial | "
        "Δ ger−cont | situação |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in conferencias:
        painel_mi = (
            None if c.painel_controladores is None else c.painel_controladores / MILHAO
        )
        linhas.append(
            f"| {c.empresa} | {c.trimestre} | {c.origem_painel} | "
            f"{_fmt(painel_mi)} | {_fmt(c.contabil_release)} | "
            f"{_fmt(c.delta_contabil_mi())} | {_fmt(c.ifrs_release)} | "
            f"{_fmt(c.delta_ifrs_mi(), 3)} | {_fmt(c.gerencial_release)} | "
            f"{_fmt(c.delta_gerencial_mi())} | {c.situacao.split(' (')[0]} |"
        )

    linhas += [
        "",
        "## Por que a linha contábil do release não serve de âncora sozinha",
        "",
        "Existe uma **terceira base contábil** além do par gerencial × contábil "
        "que a spec 5.5 já documenta, e ela não estava prevista: a conciliação "
        "publicada nos releases parte do **BRGAAP/COSIF**, enquanto as "
        "demonstrações consolidadas arquivadas na CVM — a fonte deste painel — "
        "estão em **IFRS**, por força da Resolução CMN 4.818/2020. O Banco do "
        "Brasil declara isso em texto, na nota *Declaração de conformidade* do "
        "próprio release: as demonstrações em Cosif “estão sendo apresentadas "
        "‘adicionalmente’ às demonstrações contábeis consolidadas no padrão "
        "contábil internacional – IFRS”.",
        "",
        "Itaú e Bradesco publicam a ponte BRGAAP→IFRS dentro do próprio release, "
        "e por isso ancoram o gate sozinhos. BB, BTG e Santander não a publicam — "
        "mas a mesma CMN 4.818/2020 os obriga a publicar **demonstrações "
        "consolidadas em IFRS em separado**, que é a peça de onde sai a âncora "
        "deles. São 15 documentos registrados em `corpus/ifrs/manifesto_ifrs.csv` "
        "com URL, data de download e SHA-256; o gate confere o hash antes de "
        "abrir cada um e recusa ler uma peça que tenha mudado desde o registro. "
        "O PDF fica fora do Git, como o resto do corpus bruto — o manifesto é que "
        "é versionado.",
        "",
        "A leitura dessas demonstrações não usa posição de coluna: a ordem entre "
        "trimestre isolado e acumulado do exercício **não é convenção** (no BB o "
        "acumulado vem primeiro; no BTG e no Santander, depois), e ler por "
        "posição acertaria metade dos documentos com número plausível. A coluna "
        "do trimestre é identificada pela identidade `acumulado(t) − isolado(t) = "
        "acumulado(t−1)`, com o acumulado anterior vindo do documento do "
        "trimestre anterior, e a leitura falha se mais de um par de colunas — ou "
        "nenhum — satisfizer a identidade. O 4T sai de `exercício − 9 meses`, a "
        "mesma aritmética que o painel usa (RN10): o gate compara derivado com "
        "derivado.",
        "",
        "### Onde ainda não há âncora nenhuma",
        "",
        "A varredura abaixo mede a ausência em vez de afirmá-la: procura, "
        "página a página, qualquer número do release equivalente (±0,05%, "
        "tolerando as três escalas de impressão) ao valor que o painel resolve, "
        "e informa o número **mais próximo** que achou. Uma demonstração "
        "financeira imprime a linha exata em R$ mil; distância de centésimos de "
        "por cento é coincidência de documento longo, não publicação.",
        "",
        "| banco | trimestre | painel (R$ mi) | páginas dentro de ±0,05% | "
        "número mais próximo no release | distância |",
        "|---|---|---|---|---|---|",
    ]
    sem_varredura = True
    for c in conferencias:
        if c.varredura is None:
            continue
        sem_varredura = False
        painel_mi = (
            None if c.painel_controladores is None else c.painel_controladores / MILHAO
        )
        paginas = (
            "**nenhuma**"
            if not c.varredura.paginas
            else ", ".join(str(p) for p in c.varredura.paginas)
        )
        distancia = f"{_fmt(c.varredura.melhor_distancia_pct, 4)}%"
        proximo = (
            "—"
            if c.varredura.melhor_valor is None
            else f"{_fmt(c.varredura.melhor_valor, 0)} (pág. "
            f"{c.varredura.melhor_pagina})"
        )
        linhas.append(
            f"| {c.empresa} | {c.trimestre} | {_fmt(painel_mi)} | {paginas} | "
            f"{proximo} | {distancia} |"
        )
    if sem_varredura:
        linhas.append("| — | — | — | — | — | toda célula tem âncora medida |")

    if reprovadas:
        linhas += [
            "",
            "## Onde o painel diverge da âncora",
            "",
            "Estas células têm evidência medida **e ela não bate**. É o oposto de "
            "ausência de âncora, e é o caso que o G4 existe para pegar: um rótulo "
            "errado treina um modelo confiantemente errado. O gate mede a "
            "divergência e a localiza; **não** ajusta o mapa nem descarta a "
            "célula até a causa ser entendida.",
            "",
            "| banco | trimestre | painel (R$ mi) | âncora IFRS (R$ mi) | Δ | Δ % |",
            "|---|---|---|---|---|---|",
        ]
        for c in reprovadas:
            painel_mi = (
                None
                if c.painel_controladores is None
                else c.painel_controladores / MILHAO
            )
            delta = c.delta_ifrs_mi()
            pct = (
                None
                if delta is None or not c.ifrs_release
                else delta / c.ifrs_release * 100
            )
            linhas.append(
                f"| {c.empresa} | {c.trimestre} | {_fmt(painel_mi)} | "
                f"{_fmt(c.ifrs_release)} | {_sinal(delta)} | {_sinal(pct, 2)}% |"
            )
        linhas += [
            "",
            "O diagnóstico automático de cada uma está na seção de procedência, "
            "célula a célula, com as duas perguntas que separam defeito de mapa "
            "de defeito de origem: (1) o **total consolidado** do painel reproduz "
            "o da âncora? (2) o trio do painel **fecha entre si** — `consolidado "
            "= controladores + não controladores`? Quando o total bate e o trio "
            "não fecha, o mapa resolveu o conceito certo e quem se contradiz é o "
            "arquivo da CVM.",
            "",
            "### Causa apurada, célula a célula",
            "",
        ]
        for c in reprovadas:
            causa = INVESTIGACAO_DIVERGENCIA.get((c.empresa, c.trimestre))
            linhas.append(f"**{c.empresa} {c.trimestre}** — {causa or _SEM_CAUSA}")
            linhas.append("")

    faltantes = sorted(
        {c.empresa for c in sem_ancora} | {c.empresa for c in sem_extracao}
    )
    if faltantes:
        linhas += [
            "",
            "## O que falta para fechar o gate",
            "",
            "Segue sem âncora, em " + ", ".join(faltantes) + ", a **linha IFRS** — "
            "a mesma base do arquivo da CVM. Restam duas fontes, nesta ordem de "
            "preferência:",
            "",
            "1. a **demonstração consolidada em IFRS** publicada em separado (a "
            "CMN 4.818/2020 a torna obrigatória), quando ela existe e é legível. "
            "Onde o PDF vem com fonte embutida sem mapa de caracteres, extrair "
            "exigiria **OCR pago** — decisão de orçamento (spec 5.20), não "
            "técnica, e por isso não tomada aqui;",
            "2. na falta dela, o próprio **ITR/DFP da CVM** em PDF, que é a peça "
            "de onde o painel foi carregado — anexo mais fraco, porque confere a "
            "fonte contra si mesma e só pega erro de carga, não erro de conceito.",
            "",
            "Enquanto isso não existir, o veredito honesto para essas células é "
            "**não sei** — e o modelo preditivo (spec 5.10) treina sabendo "
            "exatamente quais rótulos estão conferidos, quais divergem e quais "
            "não foram medidos.",
        ]

    linhas += ["", "## Detalhe e procedência de cada célula", ""]
    for c in conferencias:
        linhas.append(f"**{c.empresa} {c.trimestre}** — {c.situacao}")
        linhas.append(f"- {c.detalhe}")
        if c.procedencia:
            linhas.append(f"- fonte: {c.documento}, {c.procedencia}")
        for nota in c.notas:
            linhas.append(f"- nota: {nota}")
        linhas.append("")

    linhas += [
        "## Fechamento interno do painel (consolidado = controladores + não "
        "controladores)",
        "",
        "Checagem que não depende do release: se a soma não fecha, quem não fecha "
        "é o arquivo da CVM — a carga conta e reporta, não conserta nem descarta. "
        "Esta checagem já acusava o defeito antes de existir âncora que o "
        "nomeasse: o gap era o sintoma, e a demonstração em IFRS publicada em "
        "separado é que disse **qual** das três linhas está errada.",
        "",
        "| banco | trimestre | gap (R$ mil) |",
        "|---|---|---|",
    ]
    for empresa, trimestre, gap in fechamento:
        linhas.append(f"| {empresa} | {trimestre} | {_fmt(gap / 1_000, 0)} |")
    if not fechamento:
        linhas.append("| — | — | nenhum gap acima de R$ 1 mil |")
    linhas.append("")
    return "\n".join(linhas)


def main() -> int:
    resultado_a = conferir_mapa_g4(CAMINHO_PAINEL)
    parte_a = VEREDITO_APROVADO if resultado_a.aprovado else VEREDITO_REPROVADO
    if not resultado_a.aprovado:
        for divergencia in resultado_a.divergencias:
            print(f"  parte A: {divergencia}")

    documentos = carregar_cache_ocr()
    painel = lucros_do_painel()
    # Âncoras vindas de fora do release, para os emissores que não publicam a
    # ponte BRGAAP→IFRS. Cada PDF é conferido por hash contra o manifesto antes
    # de ser lido; peça alterada vira ausência com motivo, nunca âncora silenciosa.
    print("Lendo as demonstrações em IFRS de corpus/ifrs/ (confere hash)…")
    ancoras, ausencias = ancora_ifrs.carregar_ancoras()
    conferencias: list[Conferencia] = []
    fechamento: list[tuple[str, str, float]] = []

    for banco in BANCOS_CORPUS:
        do_banco = {
            doc.trimestre: doc
            for doc in documentos
            if doc.empresa == banco.banco and doc.trimestre in TRIMESTRES_CORPUS
        }
        for trimestre in TRIMESTRES_CORPUS:
            documento = do_banco.get(trimestre)
            if documento is None:
                continue
            leitura = aplicar_ancora_externa(
                ler_release(documento, do_banco),
                ancoras.get((banco.banco, trimestre)),
                ausencias.get((banco.banco, trimestre), ""),
            )
            ctrl, cons, nao_ctrl, origem = painel.get(
                (banco.banco, trimestre), (None, None, None, "")
            )
            gap = None
            if cons is not None and ctrl is not None and nao_ctrl is not None:
                gap = cons - (ctrl + nao_ctrl)
                if abs(gap) > 1_000:
                    fechamento.append((banco.banco, trimestre, gap))
            conferencia = classificar(leitura, ctrl, cons, origem, gap)
            if conferencia.sem_ancora and ctrl is not None:
                conferencia = replace(
                    conferencia,
                    varredura=varrer_valor_no_release(documento, ctrl),
                )
            conferencias.append(conferencia)
            print(
                f"{banco.banco:10s} {trimestre} "
                f"painel={_fmt(None if ctrl is None else ctrl / MILHAO):>10s} "
                f"contábil={_fmt(conferencia.contabil_release):>10s} "
                f"ifrs={_fmt(conferencia.ifrs_release):>10s} "
                f"→ {conferencia.situacao}"
            )

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        montar_relatorio(conferencias, parte_a, fechamento), encoding="utf-8"
    )
    veredito = veredito_do_gate(conferencias, parte_a)
    print(f"\nVeredito G4: {veredito}")
    print(f"Relatório: {DESTINO}")
    return SAIDA_POR_VEREDITO[veredito]


if __name__ == "__main__":
    raise SystemExit(main())
