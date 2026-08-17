"""Ingestão e chunking dos releases em PDF (seções 5.3 e 5.4 — RF02, RF03).

Dois extratores atrás da mesma interface (`Extrator.extrair(pdf) -> [Pagina]`):
``mistral_ocr``, que lê o cache versionado em `corpus/ocr/` (RNF10), e
``pdfplumber``, o extrator por biblioteca — alternativa real, usada também como
fallback do teste-sentinela (5.4), nunca código morto.

Em qualquer um deles o texto sai por página, preservando a numeração, é
dividido em chunks de ~CHUNK_TAMANHO_TOKENS com sobreposição — respeitando
limites de parágrafo **e de bloco**, para não partir tabela ao meio —, prefixado
com o cabeçalho contextual `[EMPRESA | documento | trimestre | pág. N]` e
validado antes de qualquer indexação (testes estruturais + teste-sentinela).
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import math
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import tiktoken

from src.config import (
    CAMINHO_METADADOS_CORPUS,
    DIR_CORPUS_RAW,
    Config,
)
from src.normalizacao import MULTIPLICADORES, remover_acentos, valores_equivalentes
from src.ocr_corpus import DIR_CACHE_OCR, ErroCacheOCR, carregar_documento_ocr

# Mesmo tokenizador da família OpenAI-compatible usada pelos provedores (5.3).
_ENCODER = tiktoken.get_encoding("cl100k_base")

# Esquema do manifesto do corpus — fonte de verdade (seção 5.2).
COLUNAS_METADADOS_CORPUS = (
    "empresa",
    "trimestre",
    "documento",
    "url",
    "data_coleta",
    "hash_sha256",
)
CAMINHO_ANCORAS_SENTINELA = CAMINHO_METADADOS_CORPUS.with_name(
    "ancoras_sentinela.csv"
)
COLUNAS_ANCORAS_SENTINELA = ("documento", "valor_ancora")
_ANCORAS_AUTOMATICAS = object()

# Tipos de bloco reconhecidos no texto extraído (5.3). Deliberadamente dois: a
# distinção que muda o chunking e o diagnóstico é "isto é uma tabela ou não".
TIPOS_BLOCO = ("tabela", "texto")
EXTRATORES = ("mistral_ocr", "pdfplumber")


@dataclass(frozen=True)
class DocumentoCorpus:
    """Uma linha do `corpus/metadados.csv`."""

    empresa: str
    trimestre: str
    documento: str
    url: str
    data_coleta: str
    hash_sha256: str

    @property
    def caminho_pdf(self) -> str:
        return f"{self.documento}.pdf"


@dataclass(frozen=True)
class PaginaExtraida:
    documento: DocumentoCorpus
    numero: int  # 1-indexado, como impresso no leitor de PDF
    texto: str
    provedor_extracao: str = "local"
    modelo_extracao: str = ""
    hash_artefato_extracao: str = ""
    confianca_media_ocr: float | None = None
    confianca_minima_ocr: float | None = None


@dataclass(frozen=True)
class Chunk:
    """Unidade de indexação/citação. Todos os campos de metadado são
    obrigatórios (RN01 depende deles) — a validação de qualidade rejeita
    chunk com campo vazio."""

    id: str  # ex.: "ITAU_4T2025_release_0007"
    empresa: str
    trimestre: str
    documento: str
    pagina_inicio: int
    pagina_fim: int  # == pagina_inicio quando o chunk não cruza página
    posicao_no_documento: int
    texto: str  # JÁ inclui o cabeçalho contextual na primeira linha
    # Tipos de bloco que compõem o chunk (5.3), derivados da estrutura do texto
    # extraído: "texto", "tabela" ou "tabela+texto". É o campo que permite
    # separar erro de extração de tabela de erro de recuperação (5.4).
    tipo_bloco: str = "texto"
    # Proveniência material agregada das páginas que compõem o chunk. Listas
    # são codificadas como strings ordenadas para manter JSON/loads estáveis.
    provedores_extracao: str = "local"
    modelos_extracao: str = ""
    hashes_artefatos_extracao: str = ""
    # Para chunks que cruzam páginas, ambos são o menor score entre as páginas
    # OCR envolvidas (agregação conservadora e determinística).
    confianca_media_ocr: float | None = None
    confianca_minima_ocr: float | None = None


@dataclass
class RelatorioQualidade:
    """Resultado da validação RF03. Falha em um documento não derruba o
    pipeline: o documento é marcado aqui e a execução segue (seção 5.4)."""

    documentos_ok: list[str] = field(default_factory=list)
    documentos_falhos: dict[str, str] = field(default_factory=dict)  # doc -> motivo
    avisos: list[str] = field(default_factory=list)

    @property
    def aprovado(self) -> bool:
        return not self.documentos_falhos


def carregar_metadados_corpus(
    caminho: Path = CAMINHO_METADADOS_CORPUS,
) -> list[DocumentoCorpus]:
    """Lê o manifesto e valida esquema, caminhos, hashes e unicidade.

    ``documento`` é um identificador (não um caminho). Essa distinção evita
    que uma linha malformada escape de ``corpus/raw`` quando ``caminho_pdf`` é
    resolvido. O SHA-256 é obrigatório porque o manifesto é a fonte de verdade
    do corpus, não apenas uma lista de URLs.
    """
    with open(caminho, newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        if tuple(leitor.fieldnames or ()) != COLUNAS_METADADOS_CORPUS:
            raise ValueError(
                f"Esquema inesperado em {caminho}: {leitor.fieldnames!r} "
                f"(esperado {COLUNAS_METADADOS_CORPUS})"
            )
        documentos: list[DocumentoCorpus] = []
        documentos_vistos: dict[str, int] = {}
        periodos_vistos: dict[tuple[str, str], int] = {}
        for numero_linha, linha in enumerate(leitor, start=2):
            if None in linha or any(
                linha.get(coluna) is None or not linha[coluna].strip()
                for coluna in COLUNAS_METADADOS_CORPUS
            ):
                raise ValueError(
                    f"Linha {numero_linha} incompleta em {caminho}."
                )
            linha = {chave: valor.strip() for chave, valor in linha.items()}
            nome = linha["documento"]
            if (
                Path(nome).name != nome
                or "/" in nome
                or "\\" in nome
                or nome in {".", ".."}
                or "\x00" in nome
                or nome.lower().endswith(".pdf")
            ):
                raise ValueError(
                    f"documento inválido na linha {numero_linha}: {nome!r}; "
                    "use somente o identificador sem caminho e sem extensão .pdf"
                )
            digest = linha["hash_sha256"]
            if re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None:
                raise ValueError(
                    f"hash_sha256 inválido na linha {numero_linha}: "
                    "esperado SHA-256 hexadecimal com 64 caracteres"
                )
            if nome in documentos_vistos:
                raise ValueError(
                    f"documento duplicado nas linhas "
                    f"{documentos_vistos[nome]} e {numero_linha}: {nome!r}"
                )
            periodo = (linha["empresa"], linha["trimestre"])
            if periodo in periodos_vistos:
                raise ValueError(
                    "empresa/trimestre duplicado nas linhas "
                    f"{periodos_vistos[periodo]} e {numero_linha}: {periodo!r}"
                )
            documentos_vistos[nome] = numero_linha
            periodos_vistos[periodo] = numero_linha
            linha["hash_sha256"] = digest.lower()
            documentos.append(DocumentoCorpus(**linha))
    if not documentos:
        raise ValueError(f"Manifesto vazio: {caminho}")
    return documentos


def calcular_hash_corpus(documentos: Sequence[DocumentoCorpus]) -> str:
    """SHA-256 canônico dos documentos efetivamente usados na construção.

    A ordenação torna o digest independente da ordem física do CSV; incluir o
    hash de cada PDF faz qualquer troca de conteúdo invalidar o índice. Em uma
    execução ``--amostra``, o chamador deve passar somente os documentos que
    originaram os chunks daquela amostra.
    """
    if not documentos:
        raise ValueError("Não é possível calcular hash de corpus vazio.")
    linhas = [
        {coluna: getattr(documento, coluna) for coluna in COLUNAS_METADADOS_CORPUS}
        for documento in sorted(
            documentos,
            key=lambda d: tuple(
                getattr(d, coluna) for coluna in COLUNAS_METADADOS_CORPUS
            ),
        )
    ]
    serializado = json.dumps(
        linhas,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serializado).hexdigest()


def validar_manifesto_canonico(
    documentos: Sequence[DocumentoCorpus],
    bancos: Sequence[str],
    trimestres_por_banco: int = 4,
) -> None:
    """Valida a interseção integral: mesmos 4 períodos para os 5 bancos."""
    bancos_esperados = set(bancos)
    por_banco = {
        banco: {doc.trimestre for doc in documentos if doc.empresa == banco}
        for banco in bancos_esperados
    }
    encontrados = {doc.empresa for doc in documentos}
    if encontrados != bancos_esperados:
        raise ValueError(
            "Manifesto integral com empresas inesperadas/ausentes: "
            f"esperadas={sorted(bancos_esperados)}, "
            f"encontradas={sorted(encontrados)}."
        )
    total_esperado = len(bancos_esperados) * trimestres_por_banco
    if len(documentos) != total_esperado:
        raise ValueError(
            f"Manifesto integral deve conter {total_esperado} documentos; "
            f"encontrados {len(documentos)}."
        )
    conjuntos_periodos = list(por_banco.values())
    if any(len(periodos) != trimestres_por_banco for periodos in conjuntos_periodos):
        raise ValueError(
            "Cada banco deve possuir exatamente "
            f"{trimestres_por_banco} trimestres: "
            f"{ {banco: sorted(periodos) for banco, periodos in por_banco.items()} }."
        )
    if any(periodos != conjuntos_periodos[0] for periodos in conjuntos_periodos[1:]):
        raise ValueError(
            "Os bancos não compartilham a mesma interseção de trimestres: "
            f"{ {banco: sorted(periodos) for banco, periodos in por_banco.items()} }."
        )


def carregar_ancoras_sentinela(
    caminho: Path,
    documentos: Sequence[DocumentoCorpus],
) -> dict[str, list[float]]:
    """Carrega âncoras de extração de uma fonte independente do benchmark.

    O CSV usa valores já canônicos (por exemplo ``10900000000`` ou ``0.266``)
    e aceita uma ou duas linhas por documento. Deliberadamente não lê
    ``conjunto_padrao``: usar o gabarito como sentinela vazaria o teste para a
    ingestão.
    """
    conhecidos = {documento.documento for documento in documentos}
    ancoras: dict[str, list[float]] = {}
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        if tuple(leitor.fieldnames or ()) != COLUNAS_ANCORAS_SENTINELA:
            raise ValueError(
                f"Esquema inesperado em {caminho}: {leitor.fieldnames!r} "
                f"(esperado {COLUNAS_ANCORAS_SENTINELA})"
            )
        for numero_linha, linha in enumerate(leitor, start=2):
            nome = (linha.get("documento") or "").strip()
            bruto = (linha.get("valor_ancora") or "").strip()
            if not nome or not bruto:
                raise ValueError(
                    f"Linha {numero_linha} incompleta em {caminho}."
                )
            if nome not in conhecidos:
                raise ValueError(
                    f"Âncora na linha {numero_linha} referencia documento "
                    f"fora do manifesto: {nome!r}"
                )
            try:
                valor = float(bruto)
            except ValueError as exc:
                raise ValueError(
                    f"valor_ancora inválido na linha {numero_linha}: {bruto!r}; "
                    "use o valor canônico com ponto decimal"
                ) from exc
            if not math.isfinite(valor) or valor == 0.0:
                raise ValueError(
                    f"valor_ancora deve ser finito e não zero na linha "
                    f"{numero_linha}."
                )
            valores = ancoras.setdefault(nome, [])
            if valor in valores:
                raise ValueError(
                    f"Âncora duplicada para {nome!r} na linha {numero_linha}."
                )
            valores.append(valor)
            if len(valores) > 2:
                raise ValueError(
                    f"Mais de duas âncoras para {nome!r}; o contrato RF03 "
                    "prevê 1–2 valores verificados por documento."
                )
    if not ancoras:
        raise ValueError(f"Arquivo de âncoras vazio: {caminho}")
    return ancoras


def montar_cabecalho_contextual(
    empresa: str, documento: str, trimestre: str, pagina_inicio: int, pagina_fim: int
) -> str:
    """Cabeçalho prefixado ao texto indexado (seção 5.3).

    Torna banco/trimestre "buscáveis" mesmo quando o parágrafo não os repete e
    entrega o dado de citação ao LLM dentro do próprio trecho. Chunk que cruza
    páginas registra o intervalo (`págs. 12–13`).
    """
    if pagina_fim == pagina_inicio:
        pagina = f"pág. {pagina_inicio}"
    else:
        pagina = f"págs. {pagina_inicio}–{pagina_fim}"
    return f"[{empresa} | {documento} | {trimestre} | {pagina}]"


def extrair_paginas(
    caminho_pdf: Path, doc: DocumentoCorpus, parser: str = "pypdf"
) -> list[PaginaExtraida]:
    """Extrai texto página a página. `parser` alterna pypdf ↔ pdfplumber —
    o fallback é acionado quando o teste-sentinela reprova o documento
    (seção 5.4, modo de falha nº 2)."""
    if parser == "pypdf":
        from pypdf import PdfReader

        leitor = PdfReader(str(caminho_pdf))
        return [
            PaginaExtraida(
                doc,
                i + 1,
                pagina.extract_text() or "",
                provedor_extracao="local",
                modelo_extracao=f"pypdf@{importlib.metadata.version('pypdf')}",
            )
            for i, pagina in enumerate(leitor.pages)
        ]
    if parser == "pdfplumber":
        import pdfplumber

        with pdfplumber.open(caminho_pdf) as pdf:
            return [
                PaginaExtraida(
                    doc,
                    i + 1,
                    pagina.extract_text() or "",
                    provedor_extracao="local",
                    modelo_extracao=(
                        f"pdfplumber@{importlib.metadata.version('pdfplumber')}"
                    ),
                )
                for i, pagina in enumerate(pdf.pages)
            ]
    raise ValueError(f"parser desconhecido: {parser!r} (use pypdf ou pdfplumber)")


class Extrator(ABC):
    """Interface única de extração (spec 5.3): ``extrair(pdf) -> [Pagina]``.

    As duas implementações são intercambiáveis do ponto de vista do chunking:
    devolvem páginas 1-indexadas, na ordem do documento, com a proveniência
    material preenchida. O que muda é a fonte — cache congelado ou o PDF.
    """

    nome: str
    exige_pdf: bool

    @abstractmethod
    def extrair(
        self, pdf: Path, doc: DocumentoCorpus
    ) -> list[PaginaExtraida]:  # pragma: no cover - contrato
        ...


class ExtratorBiblioteca(Extrator):
    """Extrator posicional por biblioteca (``EXTRATOR=pdfplumber``).

    ``parser`` alterna pypdf ↔ pdfplumber: o primeiro é o padrão e o segundo
    entra quando o teste-sentinela ou a validação estrutural reprovam o
    documento (5.4, modo de falha nº 2). O nome do extrator segue a spec 5.20;
    a proveniência gravada por página registra qual parser produziu o texto.
    """

    nome = "pdfplumber"
    exige_pdf = True

    def __init__(self, parser: str = "pypdf") -> None:
        if parser not in {"pypdf", "pdfplumber"}:
            raise ValueError(
                f"parser desconhecido: {parser!r} (use pypdf ou pdfplumber)"
            )
        self.parser = parser

    def extrair(self, pdf: Path, doc: DocumentoCorpus) -> list[PaginaExtraida]:
        return extrair_paginas(pdf, doc, parser=self.parser)


class ExtratorMistralOCR(Extrator):
    """Extrator primário (``EXTRATOR=mistral_ocr``) — lê `corpus/ocr/`.

    Deliberadamente **não** importa nem conhece o cliente HTTP: uma ingestão ou
    reindexação nunca pode gerar custo nem enviar documento por consequência de
    uma variável de ambiente. A chamada paga vive em `scripts/ocr_batch_mistral.py`.

    ``pdf`` é aceito para respeitar a interface, mas não é lido: o cache é
    endereçado pelo SHA-256 registrado no manifesto, então o extrator roda em um
    clone sem `corpus/raw/`.
    """

    nome = "mistral_ocr"
    exige_pdf = False

    def __init__(
        self, config: Config, dir_cache: Path = DIR_CACHE_OCR
    ) -> None:
        self._modelo = config.mistral_ocr_modelo
        self._dir_cache = Path(dir_cache)

    def extrair(self, pdf: Path, doc: DocumentoCorpus) -> list[PaginaExtraida]:
        del pdf  # ver docstring: a fonte é o cache, não o arquivo
        documento = carregar_documento_ocr(
            documento=doc.documento,
            empresa=doc.empresa,
            trimestre=doc.trimestre,
            sha256_pdf=doc.hash_sha256.lower(),
            modelo_esperado=self._modelo,
            dir_cache=self._dir_cache,
        )
        return [
            PaginaExtraida(
                doc,
                pagina.numero,
                pagina.markdown,
                provedor_extracao="mistral",
                modelo_extracao=documento.modelo,
                hash_artefato_extracao=documento.hash_artefato,
                confianca_media_ocr=pagina.confianca_media,
                confianca_minima_ocr=pagina.confianca_minima,
            )
            for pagina in documento.paginas
        ]


def fabricar_extrator(
    config: Config, dir_cache_ocr: Path = DIR_CACHE_OCR
) -> Extrator:
    """Seleciona o extrator ativo (`EXTRATOR`), falhando em valor desconhecido."""
    if config.extrator == "mistral_ocr":
        return ExtratorMistralOCR(config, dir_cache_ocr)
    if config.extrator == "pdfplumber":
        return ExtratorBiblioteca()
    raise ValueError(
        f"EXTRATOR desconhecido: {config.extrator!r} (use {' ou '.join(EXTRATORES)})."
    )


@dataclass(frozen=True)
class BlocoTexto:
    """Bloco contíguo de uma página, já classificado (5.3).

    ``cabecalho`` só é preenchido em tabela: são as linhas repetidas em cada
    parte quando a tabela não cabe inteira em um chunk.
    """

    tipo: str
    linhas: tuple[str, ...]
    cabecalho: tuple[str, ...] = ()


def _e_linha_de_tabela(linha: str) -> bool:
    """Linha de tabela markdown: pelo menos duas barras delimitando células.

    Mesmo critério usado na medição do gate G3, para que "quantidade de tabela
    reconstruída" e "tabela preservada no chunk" falem da mesma coisa.
    """
    return linha.count("|") >= 2


def _e_separador_markdown(linha: str) -> bool:
    """Linha `| --- | --- |` que separa o cabeçalho do corpo da tabela."""
    if not _e_linha_de_tabela(linha) or "-" not in linha:
        return False
    celulas = [celula.strip() for celula in linha.strip().strip("|").split("|")]
    return bool(celulas) and all(
        re.fullmatch(r":?-{2,}:?", celula) is not None for celula in celulas
    )


def segmentar_blocos(texto: str) -> list[BlocoTexto]:
    """Divide o texto de uma página em blocos de tabela e de texto.

    A classificação é derivada do markdown porque é isso que o extrator de OCR
    devolve — e as tabelas que ele marca como bloco `table` são exatamente estas
    grades. Um extrator posicional praticamente nunca produz grade markdown, e
    por isso suas páginas saem como blocos de texto: o campo é honesto sobre o
    que a extração conseguiu estruturar.
    """
    linhas = [linha.strip() for linha in texto.splitlines()]
    linhas = [linha for linha in linhas if linha]
    blocos: list[BlocoTexto] = []
    atual: list[str] = []
    tipo_atual = ""
    for linha in linhas:
        tipo = "tabela" if _e_linha_de_tabela(linha) else "texto"
        if tipo != tipo_atual and atual:
            blocos.append(_montar_bloco(tipo_atual, atual))
            atual = []
        tipo_atual = tipo
        atual.append(linha)
    if atual:
        blocos.append(_montar_bloco(tipo_atual, atual))
    return blocos


def _montar_bloco(tipo: str, linhas: list[str]) -> BlocoTexto:
    cabecalho: tuple[str, ...] = ()
    if tipo == "tabela":
        # O separador pode vir na 1ª ou na 2ª linha (o OCR às vezes emite a
        # linha de dados antes dele). Sem separador, repete-se a primeira linha.
        for posicao in (1, 0):
            if posicao < len(linhas) and _e_separador_markdown(linhas[posicao]):
                cabecalho = tuple(linhas[: posicao + 1])
                break
        else:
            cabecalho = (linhas[0],)
    return BlocoTexto(tipo=tipo, linhas=tuple(linhas), cabecalho=cabecalho)


def gerar_chunks(
    paginas: list[PaginaExtraida], config: Config
) -> list[Chunk]:
    """Divide em chunks de ~config.chunk_tamanho_tokens com
    config.chunk_sobreposicao_tokens de overlap, respeitando limites de
    parágrafo **e de bloco**, e prefixa o cabeçalho contextual.

    Limite de bloco (5.3): uma tabela não é dividida se couber no chunk; se não
    couber, cada parte carrega o cabeçalho da tabela. É a razão declarada de ter
    trocado o extrator — número recuperado sem o rótulo da coluna é número
    inútil para citação.

    Contagem de tokens via tiktoken (mesmo tokenizador do provedor default).
    """
    _validar_config_chunking(config)
    chunks: list[Chunk] = []
    por_documento: dict[str, list[PaginaExtraida]] = {}
    for pagina in paginas:
        por_documento.setdefault(pagina.documento.documento, []).append(pagina)

    for pags in por_documento.values():
        doc = pags[0].documento
        proveniencia_por_pagina = {
            pagina.numero: (
                pagina.provedor_extracao,
                pagina.modelo_extracao,
                pagina.hash_artefato_extracao,
                pagina.confianca_media_ocr,
                pagina.confianca_minima_ocr,
            )
            for pagina in pags
        }
        sobre = config.chunk_sobreposicao_tokens
        numeros_paginas = [p.numero for p in pags] or [1]
        pagina_maxima = max(numeros_paginas)
        # O intervalo costuma ser ligeiramente maior que o cabeçalho de página
        # única. Reservar o maior dos dois garante o teto inclusive em chunks
        # que carregam overlap de uma página anterior.
        cab_reserva = max(
            len(
                _ENCODER.encode(
                    montar_cabecalho_contextual(
                        doc.empresa,
                        doc.documento,
                        doc.trimestre,
                        pagina,
                        fim,
                    )
                    + "\n"
                )
            )
            for pagina, fim in ((pagina_maxima, pagina_maxima), (1, pagina_maxima))
        )
        max_corpo = config.chunk_tamanho_tokens - cab_reserva
        if max_corpo <= 0:
            raise ValueError(
                "CHUNK_TAMANHO_TOKENS é pequeno demais para o cabeçalho "
                f"contextual de {doc.documento!r}."
            )
        if sobre >= max_corpo:
            raise ValueError(
                "CHUNK_SOBREPOSICAO_TOKENS deve ser menor que o orçamento "
                f"do corpo ({max_corpo} tokens para {doc.documento!r})."
            )

        # Fragmentos guardam tokens, página E tipo de bloco. Assim, a cauda de
        # overlap que veio da página 1 continua atribuída à página 1 no chunk
        # seguinte, e o tipo de bloco do chunk é a união do que ele contém.
        atual: list[tuple[list[int], int, str]] = []
        n_tokens = 0
        novos_desde_emissao = 0
        posicao = 0

        def emitir() -> None:
            nonlocal posicao, atual, n_tokens, novos_desde_emissao
            if not atual or novos_desde_emissao <= 0:
                return
            posicao += 1
            pag_ini = min(pagina for _, pagina, _ in atual)
            pag_fim = max(pagina for _, pagina, _ in atual)
            tokens_corpo = [
                token
                for tokens_fragmento, _, _ in atual
                for token in tokens_fragmento
            ]
            tipo_bloco = "+".join(sorted({tipo for _, _, tipo in atual}))
            corpo = _ENCODER.decode(tokens_corpo).strip()
            cabecalho = montar_cabecalho_contextual(
                doc.empresa, doc.documento, doc.trimestre, pag_ini, pag_fim
            )
            texto_chunk = f"{cabecalho}\n{corpo}"
            if len(_ENCODER.encode(texto_chunk)) > config.chunk_tamanho_tokens:
                raise RuntimeError(
                    "Chunk excedeu o limite após contabilizar o cabeçalho: "
                    f"{doc.documento}, posição {posicao}."
                )
            proveniencias = [
                proveniencia_por_pagina[pagina]
                for pagina in sorted({pagina for _, pagina, _ in atual})
            ]
            provedores = "+".join(
                sorted(
                    {
                        provedor
                        for provedor, _, _, _, _ in proveniencias
                        if provedor
                    }
                )
            )
            modelos = "+".join(
                sorted(
                    {
                        modelo
                        for _, modelo, _, _, _ in proveniencias
                        if modelo
                    }
                )
            )
            hashes = ";".join(
                sorted(
                    {
                        digest
                        for _, _, digest, _, _ in proveniencias
                        if digest
                    }
                )
            )
            medias_ocr = [
                float(media)
                for provedor, _, _, media, _ in proveniencias
                if "mistral" in provedor.split("+") and media is not None
            ]
            minimas_ocr = [
                float(minima)
                for provedor, _, _, _, minima in proveniencias
                if "mistral" in provedor.split("+") and minima is not None
            ]
            chunks.append(
                Chunk(
                    id=f"{doc.documento}_{posicao:04d}",
                    empresa=doc.empresa,
                    trimestre=doc.trimestre,
                    documento=doc.documento,
                    pagina_inicio=pag_ini,
                    pagina_fim=pag_fim,
                    posicao_no_documento=posicao,
                    texto=texto_chunk,
                    tipo_bloco=tipo_bloco,
                    provedores_extracao=provedores or "local",
                    modelos_extracao=modelos,
                    hashes_artefatos_extracao=hashes,
                    confianca_media_ocr=(min(medias_ocr) if medias_ocr else None),
                    confianca_minima_ocr=(
                        min(minimas_ocr) if minimas_ocr else None
                    ),
                )
            )

            if sobre == 0:
                # ``tokens[-0:]`` devolveria o corpo inteiro.
                atual = []
            else:
                restantes = sobre
                cauda_reversa: list[tuple[list[int], int, str]] = []
                for tokens_fragmento, pagina, tipo in reversed(atual):
                    if restantes <= 0:
                        break
                    fatia = tokens_fragmento[-restantes:]
                    if fatia:
                        cauda_reversa.append((fatia, pagina, tipo))
                        restantes -= len(fatia)
                atual = list(reversed(cauda_reversa))
            n_tokens = sum(
                len(tokens_fragmento) for tokens_fragmento, _, _ in atual
            )
            novos_desde_emissao = 0

        def adicionar(tokens: list[int], pagina: int, tipo: str) -> None:
            """Adiciona um bloco sem overlap interno; ``emitir`` é a única
            fonte de repetição entre chunks."""
            nonlocal n_tokens, novos_desde_emissao
            cursor = 0
            while cursor < len(tokens):
                capacidade = max_corpo - n_tokens
                if capacidade <= 0:
                    emitir()
                    capacidade = max_corpo - n_tokens
                quantidade = min(capacidade, len(tokens) - cursor)
                fatia = tokens[cursor : cursor + quantidade]
                atual.append((fatia, pagina, tipo))
                n_tokens += quantidade
                novos_desde_emissao += quantidade
                cursor += quantidade
                if cursor < len(tokens) and n_tokens >= max_corpo:
                    emitir()

        def zerar_acumulado() -> None:
            """Descarta a cauda de sobreposição para começar um chunk limpo."""
            nonlocal atual, n_tokens
            atual = []
            n_tokens = 0

        def adicionar_tabela(bloco: BlocoTexto, pagina: int, primeira: bool) -> bool:
            """Insere uma tabela sem parti-la enquanto ela couber (5.3).

            Quando nem um chunk vazio comporta a tabela, ela é dividida por
            linhas e **cada parte carrega o cabeçalho** — a alternativa seria
            entregar números sem o rótulo da coluna. A integridade da tabela tem
            precedência sobre a sobreposição: se a cauda do chunk anterior não
            deixar espaço, ela é descartada em vez de partir a grade.
            """
            prefixo = "" if primeira else "\n"
            tokens_tabela = _ENCODER.encode(prefixo + "\n".join(bloco.linhas))
            if len(tokens_tabela) <= max_corpo:
                if n_tokens + len(tokens_tabela) > max_corpo:
                    emitir()
                    if n_tokens + len(tokens_tabela) > max_corpo:
                        zerar_acumulado()
                adicionar(tokens_tabela, pagina, "tabela")
                return False

            emitir()
            zerar_acumulado()
            cabecalho = list(bloco.cabecalho)
            if cabecalho and len(
                _ENCODER.encode("\n".join(cabecalho))
            ) > max_corpo // 3:
                # Medido no corpus: há páginas em duas colunas que o OCR
                # devolve como tabela cuja "primeira linha" é um parágrafo
                # inteiro. Repetir isso em cada parte não rotula coluna
                # nenhuma — só duplica texto e gera chunks idênticos.
                cabecalho = []
            corpo = list(bloco.linhas[len(cabecalho) :])
            if not corpo:
                # Tabela de uma linha só maior que o chunk: repetir a própria
                # linha como cabeçalho duplicaria conteúdo sem informar nada.
                cabecalho, corpo = [], list(bloco.linhas)
            parte: list[str] = []

            def emitir_parte(linhas_parte: list[str]) -> None:
                adicionar(
                    _ENCODER.encode("\n".join(cabecalho + linhas_parte)),
                    pagina,
                    "tabela",
                )
                emitir()
                zerar_acumulado()

            for linha in corpo:
                candidata = parte + [linha]
                excede = (
                    len(_ENCODER.encode("\n".join(cabecalho + candidata)))
                    > max_corpo
                )
                if parte and excede:
                    emitir_parte(parte)
                    parte = [linha]
                else:
                    parte = candidata
            if parte:
                emitir_parte(parte)
            return False

        primeira_linha = True
        for pag in sorted(pags, key=lambda p: p.numero):
            for bloco in segmentar_blocos(pag.texto):
                if bloco.tipo == "tabela":
                    primeira_linha = adicionar_tabela(
                        bloco, pag.numero, primeira_linha
                    )
                    continue
                for linha in bloco.linhas:
                    prefixo = "" if primeira_linha else "\n"
                    tokens_linha = _ENCODER.encode(prefixo + linha)
                    primeira_linha = False
                    # Se o parágrafo cabe inteiro depois do overlap, começá-lo
                    # no próximo chunk evita uma quebra desnecessária.
                    if (
                        atual
                        and novos_desde_emissao > 0
                        and len(tokens_linha) <= max_corpo - sobre
                        and n_tokens + len(tokens_linha) > max_corpo
                    ):
                        emitir()
                    adicionar(tokens_linha, pag.numero, bloco.tipo)
        # Não emite um chunk composto apenas pela cauda do anterior.
        emitir()

    return chunks


def _validar_config_chunking(config: Config) -> None:
    tamanho = config.chunk_tamanho_tokens
    overlap = config.chunk_sobreposicao_tokens
    if isinstance(tamanho, bool) or not isinstance(tamanho, int) or tamanho <= 0:
        raise ValueError("CHUNK_TAMANHO_TOKENS deve ser um inteiro positivo.")
    if isinstance(overlap, bool) or not isinstance(overlap, int) or overlap < 0:
        raise ValueError(
            "CHUNK_SOBREPOSICAO_TOKENS deve ser um inteiro não negativo."
        )
    if overlap >= tamanho:
        raise ValueError(
            "CHUNK_SOBREPOSICAO_TOKENS deve ser menor que "
            "CHUNK_TAMANHO_TOKENS."
        )


def validar_qualidade(
    chunks: list[Chunk],
    documentos: list[DocumentoCorpus],
    minimo_chunks_por_pagina: float = 0.5,
    paginas_extraidas: list[PaginaExtraida] | None = None,
    limiar_confianca_ocr: float | None = None,
) -> RelatorioQualidade:
    """Validação estrutural RF03 (seção 5.4):
      - nenhum chunk vazio ou só com caracteres de controle;
      - todo documento do manifesto gerou >= limiar mínimo de chunks;
      - todo chunk tem os 5 campos de metadado preenchidos;
      - nenhuma página extraída duplicada dentro do mesmo documento.

    ``limiar_confianca_ocr`` não bloqueia nada: a spec 5.4 é explícita em que a
    confiança de OCR é sinal de diagnóstico, e chunk abaixo do limiar — ou sem
    escore nenhum — entra em ``avisos``. O que falha fechado é escore presente e
    estruturalmente inválido, que é adulteração ou mudança de contrato.
    """
    if minimo_chunks_por_pagina < 0:
        raise ValueError("minimo_chunks_por_pagina não pode ser negativo.")
    if limiar_confianca_ocr is not None and not (
        isinstance(limiar_confianca_ocr, (int, float))
        and not isinstance(limiar_confianca_ocr, bool)
        and math.isfinite(limiar_confianca_ocr)
        and 0.0 <= float(limiar_confianca_ocr) <= 1.0
    ):
        raise ValueError("limiar_confianca_ocr deve ser finito entre 0 e 1.")
    relatorio = RelatorioQualidade()
    conhecidos = {d.documento for d in documentos}
    manifesto_por_nome = {d.documento: d for d in documentos}
    por_documento: dict[str, list[Chunk]] = {d.documento: [] for d in documentos}
    ids_vistos: dict[str, str] = {}
    for chunk in chunks:
        if chunk.documento not in conhecidos:
            relatorio.documentos_falhos.setdefault(
                chunk.documento,
                f"chunk {chunk.id} referencia documento fora do manifesto: "
                f"{chunk.documento!r}",
            )
            continue
        por_documento[chunk.documento].append(chunk)
        if chunk.id in ids_vistos:
            relatorio.documentos_falhos.setdefault(
                chunk.documento,
                f"id de chunk duplicado: {chunk.id} "
                f"(também em {ids_vistos[chunk.id]})",
            )
        else:
            ids_vistos[chunk.id] = chunk.documento

    paginas_por_documento: dict[str, list[PaginaExtraida]] = {
        d.documento: [] for d in documentos
    }
    for pagina in paginas_extraidas or []:
        if pagina.documento.documento in paginas_por_documento:
            paginas_por_documento[pagina.documento.documento].append(pagina)

    for nome, chunks_doc in por_documento.items():
        motivos: list[str] = []
        doc_manifesto = manifesto_por_nome[nome]
        if not chunks_doc:
            motivos.append("nenhum chunk gerado")
        corpos_vistos: dict[str, Chunk] = {}
        for chunk in chunks_doc:
            corpo = chunk.texto.split("\n", 1)[1] if "\n" in chunk.texto else ""
            anterior = corpos_vistos.get(corpo)
            if not re.sub(r"[\s\x00-\x1f\x7f]+", "", corpo):
                motivos.append(f"chunk vazio ou só controle: {chunk.id}")
            elif anterior is not None:
                # Corpo repetido nas MESMAS páginas é patologia de extração ou
                # do chunker — o mesmo conteúdo emitido duas vezes. Em páginas
                # diferentes é legítimo e medido no corpus: um release repete o
                # mesmo bloco de notas de rodapé sob tabelas de páginas
                # distintas. Reprovar isso jogaria o documento inteiro no
                # extrator alternativo por causa de uma nota de rodapé.
                mesmas_paginas = (
                    anterior.pagina_inicio,
                    anterior.pagina_fim,
                ) == (chunk.pagina_inicio, chunk.pagina_fim)
                if mesmas_paginas:
                    motivos.append(
                        f"página/chunk duplicada (corpo repetido) no chunk {chunk.id}"
                    )
                else:
                    relatorio.avisos.append(
                        f"{nome}: bloco repetido em páginas diferentes "
                        f"({anterior.id} pág. {anterior.pagina_inicio} e "
                        f"{chunk.id} pág. {chunk.pagina_inicio})"
                    )
            corpos_vistos.setdefault(corpo, chunk)
            metadados = (
                chunk.id,
                chunk.empresa,
                chunk.trimestre,
                chunk.documento,
                chunk.pagina_inicio,
                chunk.pagina_fim,
                chunk.posicao_no_documento,
            )
            if any(campo in ("", None) for campo in metadados):
                motivos.append(f"metadado de citação vazio no chunk {chunk.id}")
            if not isinstance(chunk.provedores_extracao, str) or not re.fullmatch(
                r"[a-z0-9_.+-]+", chunk.provedores_extracao
            ):
                motivos.append(
                    f"provedores de extração inválidos no chunk {chunk.id}"
                )
            if not isinstance(chunk.modelos_extracao, str) or any(
                ord(char) < 32 for char in chunk.modelos_extracao
            ):
                motivos.append(f"modelos de extração inválidos no chunk {chunk.id}")
            hashes_extracao = (
                chunk.hashes_artefatos_extracao.split(";")
                if isinstance(chunk.hashes_artefatos_extracao, str)
                and chunk.hashes_artefatos_extracao
                else []
            )
            if (
                not isinstance(chunk.hashes_artefatos_extracao, str)
                or hashes_extracao != sorted(set(hashes_extracao))
                or any(re.fullmatch(r"[0-9a-f]{64}", h) is None for h in hashes_extracao)
                or (
                    "mistral" in chunk.provedores_extracao.split("+")
                    and not hashes_extracao
                )
            ):
                motivos.append(
                    f"hashes de artefatos de extração inválidos no chunk {chunk.id}"
                )
            tipos_do_chunk = (
                chunk.tipo_bloco.split("+")
                if isinstance(chunk.tipo_bloco, str) and chunk.tipo_bloco
                else []
            )
            if (
                not tipos_do_chunk
                or tipos_do_chunk != sorted(set(tipos_do_chunk))
                or any(tipo not in TIPOS_BLOCO for tipo in tipos_do_chunk)
            ):
                motivos.append(f"tipo de bloco inválido no chunk {chunk.id}")
            usa_mistral = "mistral" in chunk.provedores_extracao.split("+")
            scores_ocr = (
                chunk.confianca_media_ocr,
                chunk.confianca_minima_ocr,
            )
            sem_score = scores_ocr == (None, None)
            scores_validos = all(
                not isinstance(score, bool)
                and isinstance(score, (int, float))
                and math.isfinite(score)
                and 0.0 <= float(score) <= 1.0
                for score in scores_ocr
            ) and (
                not all(isinstance(score, (int, float)) for score in scores_ocr)
                or float(scores_ocr[1]) <= float(scores_ocr[0])
            )
            # Chunk sem OCR nunca pode exibir escore — seria proveniência
            # inventada. Chunk de OCR pode não ter escore (o artefato do cache
            # pode não trazer `confidence_scores`), mas se tiver, tem de ser
            # coerente. A ausência vira aviso, logo abaixo, nunca silêncio.
            if (usa_mistral and not (sem_score or scores_validos)) or (
                not usa_mistral and not sem_score
            ):
                motivos.append(
                    f"scores de confiança OCR inválidos no chunk {chunk.id}"
                )
            if (
                chunk.empresa != doc_manifesto.empresa
                or chunk.trimestre != doc_manifesto.trimestre
            ):
                motivos.append(
                    f"metadado diverge do manifesto no chunk {chunk.id}"
                )
            if (
                not isinstance(chunk.pagina_inicio, int)
                or not isinstance(chunk.pagina_fim, int)
                or chunk.pagina_inicio <= 0
                or chunk.pagina_fim < chunk.pagina_inicio
            ):
                motivos.append(f"intervalo de páginas inválido no chunk {chunk.id}")
            cabecalho_esperado = montar_cabecalho_contextual(
                chunk.empresa,
                chunk.documento,
                chunk.trimestre,
                chunk.pagina_inicio,
                chunk.pagina_fim,
            )
            if not chunk.texto.startswith(cabecalho_esperado + "\n"):
                motivos.append(f"cabeçalho contextual inválido no chunk {chunk.id}")

        paginas_doc = paginas_por_documento[nome]
        textos_de_pagina: dict[str, int] = {}
        for pagina in paginas_doc:
            texto_normalizado = re.sub(
                r"\s+", " ", remover_acentos(pagina.texto).lower()
            ).strip()
            if not texto_normalizado:
                continue
            if texto_normalizado in textos_de_pagina:
                motivos.append(
                    "página duplicada na extração: páginas "
                    f"{textos_de_pagina[texto_normalizado]} e {pagina.numero}"
                )
            else:
                textos_de_pagina[texto_normalizado] = pagina.numero
        if chunks_doc:
            n_paginas = (
                len({p.numero for p in paginas_doc})
                if paginas_doc
                else max(c.pagina_fim for c in chunks_doc)
            )
            if len(chunks_doc) < minimo_chunks_por_pagina * n_paginas:
                motivos.append(
                    f"apenas {len(chunks_doc)} chunks para {n_paginas} páginas "
                    f"(limiar {minimo_chunks_por_pagina}/pág.)"
                )
        motivo_preexistente = relatorio.documentos_falhos.get(nome)
        if motivo_preexistente:
            motivos.insert(0, motivo_preexistente)
        if motivos:
            relatorio.documentos_falhos[nome] = "; ".join(motivos)
        else:
            relatorio.documentos_ok.append(nome)
        relatorio.avisos.extend(_avisos_confianca_ocr(nome, chunks_doc, limiar_confianca_ocr))
    return relatorio


def _avisos_confianca_ocr(
    documento: str,
    chunks_doc: list[Chunk],
    limiar: float | None,
) -> list[str]:
    """Relatório de confiança de OCR por documento (spec 5.4).

    Não bloqueia a indexação — é o sinal que permite, depois, verificar se os
    erros de exatidão numérica se concentram nas páginas de baixa confiança.
    """
    de_ocr = [
        chunk
        for chunk in chunks_doc
        if "mistral" in chunk.provedores_extracao.split("+")
    ]
    if not de_ocr:
        return []
    avisos: list[str] = []
    sem_escore = [chunk for chunk in de_ocr if chunk.confianca_media_ocr is None]
    if sem_escore:
        avisos.append(
            f"{documento}: {len(sem_escore)} de {len(de_ocr)} chunks de OCR sem "
            "escore de confiança — o artefato do cache não traz "
            "`confidence_scores`; a limitação é declarada, não estimada."
        )
    if limiar is not None:
        abaixo = [
            chunk
            for chunk in de_ocr
            if chunk.confianca_media_ocr is not None
            and float(chunk.confianca_media_ocr) < float(limiar)
        ]
        if abaixo:
            amostra = ", ".join(chunk.id for chunk in abaixo[:5])
            avisos.append(
                f"{documento}: {len(abaixo)} chunks de OCR abaixo do limiar de "
                f"confiança {limiar} (não bloqueia a indexação — 5.4): {amostra}"
                + (" ..." if len(abaixo) > 5 else "")
            )
    return avisos


def teste_sentinela(
    chunks_do_documento: list[Chunk], valores_ancora: list[float]
) -> bool:
    """Confere 1–2 valores-âncora conhecidos (ex.: lucro líquido de capa) no
    texto extraído, após normalização numérica pt-BR. Se o valor-âncora não
    aparece, a extração falhou de forma relevante mesmo com os testes
    estruturais passando (seção 5.4)."""
    if not valores_ancora:
        raise ValueError(
            "teste-sentinela exige ao menos um valor-âncora verificado; "
            "não é seguro aprovar por lista vazia"
        )
    if any(
        isinstance(valor, bool)
        or not isinstance(valor, (int, float))
        or not math.isfinite(float(valor))
        for valor in valores_ancora
    ):
        raise ValueError("valores-âncora devem ser números finitos.")

    unidades = "|".join(
        sorted((re.escape(u) for u in MULTIPLICADORES), key=len, reverse=True)
    )
    padrao_numero = re.compile(
        rf"(?<!\w)(?P<moeda>r\$\s*)?"
        rf"(?P<numero>(?:\d{{1,3}}(?:\.\d{{3}})+(?:,\d+)?)|(?:\d+(?:,\d+)?))"
        rf"\s*(?P<unidade>%|{unidades})?(?!\w)",
        re.IGNORECASE,
    )
    valores_no_texto: list[float] = []
    for chunk in chunks_do_documento:
        texto = remover_acentos(chunk.texto).lower()
        for m in padrao_numero.finditer(texto):
            # Números soltos do cabeçalho (trimestre/página) não são âncoras
            # financeiras. Exigimos moeda, percentual ou unidade explícita.
            moeda = m.group("moeda")
            unidade = (m.group("unidade") or "").lower()
            if not moeda and not unidade:
                continue
            valor = float(
                m.group("numero").replace(".", "").replace(",", ".")
            )
            if unidade == "%":
                valor /= 100.0
            elif unidade in MULTIPLICADORES:
                valor *= MULTIPLICADORES[unidade]
            valores_no_texto.append(valor)
    return all(
        any(valores_equivalentes(ancora, v) for v in valores_no_texto)
        for ancora in valores_ancora
    )


def _conferir_hash_pdf(caminho: Path, doc: DocumentoCorpus) -> None:
    """O PDF só é lido depois de bater com o manifesto (fonte de verdade)."""
    digest_obtido = _sha256_arquivo(caminho)
    if digest_obtido != doc.hash_sha256.lower():
        raise ValueError(
            "SHA-256 divergente: "
            f"manifesto={doc.hash_sha256.lower()}, arquivo={digest_obtido}"
        )


def _extrair_com_biblioteca(
    caminho: Path,
    doc: DocumentoCorpus,
    config: Config,
    valores_ancora: list[float],
) -> tuple[list[PaginaExtraida], list[Chunk]]:
    """Extração por biblioteca com o fallback pypdf ↔ pdfplumber (5.4).

    Lógica preservada da versão anterior: o parser alternativo entra quando o
    primário erra, esvazia páginas demais, reprova a estrutura ou perde o
    valor-âncora; com âncora conhecida, o alternativo só é aceito se ele próprio
    passar no sentinela.
    """
    erro_primario: Exception | None = None
    try:
        paginas = extrair_paginas(caminho, doc, parser="pypdf")
        chunks_doc = gerar_chunks(paginas, config)
    except Exception as exc:
        erro_primario = exc
        paginas = []
        chunks_doc = []

    relatorio_primario = validar_qualidade(
        chunks_doc, [doc], paginas_extraidas=paginas
    )
    estrutura_primaria_ok = relatorio_primario.aprovado
    motivo_primario = relatorio_primario.documentos_falhos.get(
        doc.documento, "erro de extração"
    )

    sentinela_primario_ok = (
        teste_sentinela(chunks_doc, valores_ancora)
        if valores_ancora and chunks_doc
        else not valores_ancora
    )
    precisa_fallback = (
        erro_primario is not None
        or _fracao_paginas_vazias(paginas) > 0.2
        or not sentinela_primario_ok
        or not estrutura_primaria_ok
    )
    if not precisa_fallback:
        return paginas, chunks_doc

    try:
        alternativa = extrair_paginas(caminho, doc, parser="pdfplumber")
        chunks_alternativa = gerar_chunks(alternativa, config)
    except Exception as erro_alternativo:
        raise RuntimeError(
            "ambos os parsers falharam; "
            f"pypdf={erro_primario!r}, "
            f"pdfplumber={erro_alternativo!r}"
        ) from erro_alternativo

    relatorio_alternativo = validar_qualidade(
        chunks_alternativa, [doc], paginas_extraidas=alternativa
    )
    estrutura_alternativa_ok = relatorio_alternativo.aprovado
    motivo_alternativo = relatorio_alternativo.documentos_falhos.get(
        doc.documento, "erro estrutural"
    )
    sentinela_alternativo_ok = (
        teste_sentinela(chunks_alternativa, valores_ancora)
        if valores_ancora and chunks_alternativa
        else not valores_ancora
    )
    if valores_ancora:
        if not sentinela_alternativo_ok or not estrutura_alternativa_ok:
            raise ValueError(
                "fallback pdfplumber reprovado; "
                f"sentinela_ok={sentinela_alternativo_ok}, "
                f"RF03={motivo_alternativo}; "
                f"pypdf_RF03={motivo_primario}"
            )
        return alternativa, chunks_alternativa
    if estrutura_alternativa_ok and (
        erro_primario is not None
        or not estrutura_primaria_ok
        or _fracao_paginas_vazias(alternativa) < _fracao_paginas_vazias(paginas)
    ):
        return alternativa, chunks_alternativa
    if erro_primario is not None or not estrutura_primaria_ok:
        raise ValueError(
            "RF03 reprovou pypdf e pdfplumber; "
            f"pypdf={motivo_primario}; "
            f"pdfplumber={motivo_alternativo}"
        )
    return paginas, chunks_doc


def _extrair_com_ocr(
    extrator: Extrator,
    doc: DocumentoCorpus,
    config: Config,
    valores_ancora: list[float],
    caminho_pdf: Path,
) -> tuple[list[PaginaExtraida], list[Chunk]]:
    """Extrai do cache versionado; só cai na biblioteca se o OCR reprovar.

    A troca de extrator nunca é silenciosa: ela é impressa como aviso e fica
    gravada na proveniência de cada página, que por sua vez entra na identidade
    do índice. Se o cache reprovar e o PDF não estiver disponível, o documento
    é reprovado — inventar uma extração alternativa que ninguém pode conferir
    seria pior que a falha.
    """
    paginas = extrator.extrair(caminho_pdf, doc)
    chunks_doc = gerar_chunks(paginas, config)
    relatorio = validar_qualidade(
        chunks_doc,
        [doc],
        paginas_extraidas=paginas,
        limiar_confianca_ocr=config.mistral_ocr_limiar_confianca_media,
    )
    sentinela_ok = (
        teste_sentinela(chunks_doc, valores_ancora)
        if valores_ancora and chunks_doc
        else not valores_ancora
    )
    if relatorio.aprovado and sentinela_ok:
        return paginas, chunks_doc

    motivo = relatorio.documentos_falhos.get(doc.documento, "estrutura aprovada")
    diagnostico = f"sentinela_ok={sentinela_ok}, RF03={motivo}"
    if not caminho_pdf.exists():
        raise ValueError(
            f"extração por cache de OCR reprovada ({diagnostico}) e o PDF não "
            f"está em {caminho_pdf.parent} para tentar o extrator alternativo "
            "(5.4); rode scripts/baixar_corpus.py ou reprocesse o OCR"
        )
    print(
        f"AVISO RF03: {doc.documento} reprovou no cache de OCR ({diagnostico}); "
        "tentando o extrator alternativo por biblioteca (5.4)."
    )
    _conferir_hash_pdf(caminho_pdf, doc)
    return _extrair_com_biblioteca(caminho_pdf, doc, config, valores_ancora)


def ingerir_corpus(
    config: Config,
    amostra: bool = False,
    caminho_metadados: Path = CAMINHO_METADADOS_CORPUS,
    dir_raw: Path = DIR_CORPUS_RAW,
    valores_ancora_por_documento: Mapping[str, Sequence[float]] | None = None,
    caminho_ancoras_sentinela: Path | None | object = _ANCORAS_AUTOMATICAS,
    exigir_cobertura_sentinela: bool = False,
    exigir_todos_documentos: bool = False,
    exigir_manifesto_canonico: bool = False,
    dir_cache_ocr: Path = DIR_CACHE_OCR,
) -> list[Chunk]:
    """Pipeline de ingestão completo: manifesto -> páginas -> chunks -> RF03.

    `amostra=True` processa 1 banco × 1 trimestre (smoke test, RNF01).
    Por padrão, as âncoras são procuradas ao lado do manifesto recebido;
    ``None`` as desabilita explicitamente. Assim, manifestos sintéticos ou
    alternativos nunca são acoplados silenciosamente ao corpus canônico.
    As falhas são sempre coletadas depois de tentar todos os PDFs; em execução
    produtiva, ``exigir_todos_documentos=True`` impede indexar corpus parcial.
    """
    _validar_config_chunking(config)
    todos_documentos = carregar_metadados_corpus(caminho_metadados)
    if exigir_manifesto_canonico:
        if amostra:
            raise ValueError(
                "exigir_manifesto_canonico não é compatível com amostra=True."
            )
        validar_manifesto_canonico(todos_documentos, config.bancos)
    if caminho_ancoras_sentinela is _ANCORAS_AUTOMATICAS:
        caminho_ancoras: Path | None = Path(caminho_metadados).with_name(
            CAMINHO_ANCORAS_SENTINELA.name
        )
    elif caminho_ancoras_sentinela is None:
        caminho_ancoras = None
    elif isinstance(caminho_ancoras_sentinela, (str, Path)):
        caminho_ancoras = Path(caminho_ancoras_sentinela)
    else:
        raise TypeError("caminho_ancoras_sentinela deve ser Path, str ou None.")

    if valores_ancora_por_documento is not None:
        ancoras = {
            nome: list(valores)
            for nome, valores in valores_ancora_por_documento.items()
        }
        origem_ancoras_ausente: str | None = None
    elif caminho_ancoras is not None and caminho_ancoras.exists():
        ancoras = carregar_ancoras_sentinela(
            caminho_ancoras, todos_documentos
        )
        origem_ancoras_ausente = None
    else:
        ancoras = {}
        origem_ancoras_ausente = (
            f"arquivo ausente: {caminho_ancoras}"
            if caminho_ancoras is not None
            else "fonte de âncoras desabilitada"
        )

    nomes_manifesto = {d.documento for d in todos_documentos}
    desconhecidos = set(ancoras) - nomes_manifesto
    if desconhecidos:
        raise ValueError(
            "Valores-âncora referenciam documentos fora do manifesto: "
            f"{sorted(desconhecidos)}"
        )
    for nome, valores in ancoras.items():
        if not 1 <= len(valores) <= 2:
            raise ValueError(
                f"Esperadas 1–2 âncoras verificadas para {nome!r}; "
                f"recebidas {len(valores)}."
            )
        if any(
            isinstance(valor, bool)
            or not isinstance(valor, (int, float))
            or not math.isfinite(float(valor))
            or valor == 0.0
            for valor in valores
        ):
            raise ValueError(
                f"Valores-âncora de {nome!r} devem ser finitos e não zero."
            )

    documentos = todos_documentos
    if amostra:
        empresa = documentos[0].empresa
        trimestre = next(
            d.trimestre for d in documentos if d.empresa == empresa
        )
        documentos = [
            d
            for d in documentos
            if d.empresa == empresa and d.trimestre == trimestre
        ]
    nomes_selecionados = {d.documento for d in documentos}
    ancoras = {
        nome: valores for nome, valores in ancoras.items() if nome in nomes_selecionados
    }
    sem_cobertura = sorted(nomes_selecionados - set(ancoras))
    if origem_ancoras_ausente or sem_cobertura:
        detalhes = origem_ancoras_ausente or (
            f"sem âncora para {len(sem_cobertura)} documento(s): "
            + ", ".join(sem_cobertura)
        )
        mensagem = (
            "Teste-sentinela não terá cobertura completa — " + detalhes + "."
        )
        if exigir_cobertura_sentinela:
            raise ValueError(mensagem)
        print(f"AVISO RF03: {mensagem}")

    extrator = fabricar_extrator(config, dir_cache_ocr)
    chunks: list[Chunk] = []
    paginas_extraidas: list[PaginaExtraida] = []
    falhas_extracao: dict[str, str] = {}
    paginas_vindas_do_ocr = 0
    for doc in documentos:
        caminho = Path(dir_raw) / doc.caminho_pdf
        valores_ancora = list(ancoras.get(doc.documento, ()))
        try:
            if extrator.nome == "mistral_ocr":
                paginas, chunks_doc = _extrair_com_ocr(
                    extrator, doc, config, valores_ancora, caminho
                )
            else:
                if not caminho.exists():
                    raise FileNotFoundError(
                        "PDF ausente — rode scripts/baixar_corpus.py"
                    )
                _conferir_hash_pdf(caminho, doc)
                paginas, chunks_doc = _extrair_com_biblioteca(
                    caminho, doc, config, valores_ancora
                )
            paginas_vindas_do_ocr += sum(
                1 for pagina in paginas if pagina.provedor_extracao == "mistral"
            )
            paginas_extraidas.extend(paginas)
            chunks.extend(chunks_doc)
        except Exception as exc:
            # RF03 é continue-on-fail por documento. Uma falha local não pode
            # impedir a validação dos demais documentos.
            falhas_extracao[doc.documento] = f"{type(exc).__name__}: {exc}"

    # Declarar o extrator primário e indexar zero página dele seria a pior
    # combinação possível: um índice que se apresenta como OCR e não é.
    if config.extrator == "mistral_ocr" and chunks and paginas_vindas_do_ocr == 0:
        raise RuntimeError(
            "EXTRATOR=mistral_ocr, mas nenhuma página indexada veio do cache "
            "em corpus/ocr/ — todos os documentos caíram no extrator "
            "alternativo. Confira o cache antes de construir qualquer índice."
        )

    relatorio = validar_qualidade(
        chunks,
        documentos,
        paginas_extraidas=paginas_extraidas,
        limiar_confianca_ocr=config.mistral_ocr_limiar_confianca_media,
    )
    for nome, motivo in falhas_extracao.items():
        anterior = relatorio.documentos_falhos.get(nome)
        relatorio.documentos_falhos[nome] = (
            f"{motivo}; {anterior}" if anterior else motivo
        )
        if nome in relatorio.documentos_ok:
            relatorio.documentos_ok.remove(nome)
    for nome, motivo in relatorio.documentos_falhos.items():
        print(f"AVISO RF03: documento {nome} reprovado — {motivo}")
    for aviso in relatorio.avisos:
        print(f"AVISO RF03: {aviso}")
    if exigir_todos_documentos and relatorio.documentos_falhos:
        nomes = ", ".join(sorted(relatorio.documentos_falhos))
        raise RuntimeError(
            "Ingestão incompleta: "
            f"{len(relatorio.documentos_falhos)} documento(s) reprovaram RF03 "
            f"({nomes}). Nenhum índice deve ser construído com corpus parcial."
        )
    return [c for c in chunks if c.documento not in relatorio.documentos_falhos]


def _fracao_paginas_vazias(paginas: list[PaginaExtraida]) -> float:
    if not paginas:
        return 1.0
    vazias = sum(1 for p in paginas if len(p.texto.strip()) < 20)
    return vazias / len(paginas)


def _sha256_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()
