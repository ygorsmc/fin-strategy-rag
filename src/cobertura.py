"""Resolução de entidade e triagem de cobertura (spec 5.9.2 · RN11 · RN12).

Três responsabilidades, todas puras o bastante para serem testadas sem LLM:

1. **Resolução de entidade por `CD_CVM`, nunca por nome (RN11).** O nome é
   chave de busca; o que identifica a companhia é o código. Nome que resolve
   para mais de uma companhia **gera pergunta de desambiguação** — nunca
   escolha automática pela mais provável. Verificado no painel real em
   2026-08-10: `BTG` resolve para `022616` (BCO BTG PACTUAL) **e** `027774`
   (BTG PACTUAL COMMODITIES SERTRADING).

2. **Triagem de cobertura em três estados (RN12).** "Não sei" tem três valores,
   porque as duas camadas do sistema têm coberturas diferentes: `ambas`,
   `so_painel` e `nenhuma`. Para um leitor fora do mercado *"e o Nubank?"* e
   *"e o Inter?"* são a mesma pergunta e têm respostas corretas **diferentes**
   — o Inter & Co arquiva na CVM (`080217`) e não tem release indexado; a Nu
   Holdings é listada na NYSE e não arquiva ITR. Tratar as duas como recusa
   joga fora metade de uma resposta verdadeira.

3. **Braço C do experimento de 5.9.3** — determinístico, sem LLM: resolução de
   entidade + consulta de cobertura + resposta por gabarito fixo. É o **piso
   honesto** contra o qual os braços com agente são medidos, e existe
   justamente porque pode derrubar os outros dois.

**Risco 12c, declarado:** devolver `nenhuma` para companhia que **está** no
painel é a mesma classe de erro que o projeto combate, invertida. Por isso toda
resolução vazia vai para o log — a ausência silenciosa é o modo de falha, não a
ausência.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Protocol

from src.config import CAMINHO_METADADOS_CORPUS, Config
from src.dados_estruturados import abrir_conexao_somente_leitura
from src.ingestao import carregar_metadados_corpus
from src.mapa_contas import (
    BANCOS_CORPUS,
    CONCEITO_ATIVO_TOTAL,
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_LUCRO_NAO_CONTROLADORES,
    CONCEITO_PATRIMONIO_LIQUIDO,
    CONCEITO_RECEITA_INTERMEDIACAO,
    CONCEITOS_DE_FLUXO,
    normalizar_cd_cvm,
)
from src.normalizacao import (
    APELIDOS_BANCOS,
    PeriodoPedido,
    canonizar_banco,
    extrair_bancos_citados,
    extrair_periodos_citados,
    extrair_trimestres_citados,
    remover_acentos,
)

registrador = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Vocabulário congelado
# --------------------------------------------------------------------------- #


class EstadoCobertura(str, Enum):
    """Os três valores de "não sei" da RN12 — mais um estado de inconsistência.

    Os três primeiros são o vocabulário congelado de `cobertura_esperada` em
    `conjunto_padrao/anotacoes_revisao2.csv`, e são os únicos que a relação real
    entre corpus e painel produz.

    `SO_CORPUS` **não** pertence a esse vocabulário e é declaradamente um
    estado de inconsistência de dados: uma companhia com release indexado e
    ausente do painel. Ele existe para que essa situação não seja empurrada
    para dentro de `ambas` (mentira: o número contábil não existe) nem de
    `nenhuma` (mentira: o release existe). Se aparecer, é defeito de carga do
    painel ou de recorte da janela, e vai para o log.
    """

    AMBAS = "ambas"
    SO_PAINEL = "so_painel"
    NENHUMA = "nenhuma"
    SO_CORPUS = "so_corpus"


ESTADOS_RN12: frozenset[EstadoCobertura] = frozenset(
    {EstadoCobertura.AMBAS, EstadoCobertura.SO_PAINEL, EstadoCobertura.NENHUMA}
)

# Vocabulário de `motivo_recusa_esperado` (`anotacoes_revisao2.csv`). Reusado
# aqui de propósito: uma recusa diagnosticada só é medível contra o gabarito se
# usar as mesmas palavras que ele.
MOTIVO_NA = "n/a"
MOTIVO_FORA_DO_CORPUS = "fora_do_corpus"
MOTIVO_PERIODO_AUSENTE = "periodo_ausente"

# Ausências que o projeto **sabe explicar**. Não são resolução (a companhia
# continua sem `CD_CVM`) — são o que transforma "não encontrei" em recusa que
# nomeia o tipo de ausência, como a RN12 exige. A chave é o nome canônico de
# `src.normalizacao.APELIDOS_BANCOS`, para cobrir todas as formas de superfície
# já mapeadas ali ("nubank", "nu holdings", "nu pagamentos").
MOTIVO_AUSENCIA_DECLARADO: Mapping[str, str] = {
    "NUBANK": (
        "a Nu Holdings Ltd. é listada na NYSE e não arquiva ITR/DFP na CVM, "
        "logo não existe no painel contábil; e não há release dela no corpus "
        "documental, que cobre cinco bancos brasileiros"
    ),
}


# --------------------------------------------------------------------------- #
# Tokenização de nome de companhia
# --------------------------------------------------------------------------- #

# Um token compartilhado por muitas companhias não identifica nenhuma: "brasil"
# aparece em 27 das 470 do painel (BCO BRASIL, BCO MERCANTIL DO BRASIL,
# HIDROVIAS DO BRASIL, TELEFÔNICA BRASIL...), e tratá-lo como menção produziria
# desambiguação de 27 candidatas em qualquer pergunta que cite o país. Medido no
# painel real em 2026-08-10; com o limiar em 3, "inter" (1 companhia) e "btg"
# (2 companhias) continuam distintivos — e é a segunda que expõe a RN11.
#
# **Limitação declarada:** o limiar é absoluto e a distintividade depende do
# painel carregado. Num painel pequeno, "brasil" volta a ser raro e passa a ser
# tratado como menção. Não é bug do resolvedor, é propriedade do dado — por isso
# as fixtures de teste reproduzem a distribuição real de tokens em vez de uma
# amostra mínima, que resolveria bonito e mediria outra coisa.
MAX_COMPANHIAS_POR_TOKEN_DISTINTIVO = 3

# Forma jurídica e ruído de razão social. A raridade já elimina quase todos
# (`participacoes` está em 58 companhias), mas a lista declara a intenção e
# protege contra o caso em que um deles fique raro num painel menor.
TOKENS_GENERICOS: frozenset[str] = frozenset(
    {
        "a", "banco", "bco", "cia", "co", "companhia", "corp", "de", "da",
        "das", "do", "dos", "e", "em", "empresa", "epp", "group", "grupo",
        "holding", "holdings", "inc", "judicial", "ltda", "me", "part",
        "participacao", "participacoes", "recuperacao", "s", "sa", "the",
        # Palavras funcionais do português e abreviações de razão social que
        # colidem com elas. Sem isto, a pergunta "compare o Itaú **com** o
        # Bradesco" extrai `com` como menção de companhia — o token existe no
        # índice distintivo porque razões sociais abreviam *comércio* como
        # "COM" (M.DIAS BRANCO IND COM) — e "resultado **para** o Santander"
        # extrai `para` (AERIS ... PARA GER. DE ENG.). Uma preposição virando
        # companhia produz desambiguação espúria e chamada de painel inútil.
        "ao", "aos", "as", "com", "como", "contra", "entre", "ind", "na",
        "nas", "no", "nos", "num", "numa", "o", "os", "ou", "para", "pela",
        "pelas", "pelo", "pelos", "por", "qual", "quais", "que", "sem",
        "seu", "seus", "sob", "sobre", "sua", "suas", "um", "uma",
    }
)

_PADRAO_NAO_ALFANUMERICO = re.compile(r"[^0-9a-zA-Z]+")


def tokenizar_nome(texto: str | None) -> tuple[str, ...]:
    """Reduz uma razão social a tokens comparáveis, sem acento e minúsculos.

    O casamento é **por token inteiro**, nunca por substring: é o que impede
    "Inter" de casar `ALARES INTERNET PARTICIPAÇÕES S/A`, `LOG-IN LOGÍSTICA
    INTERMODAL` ou `INTERCEMENT BRASIL` — as três estão no painel real e as
    três casariam num `LIKE '%INTER%'`.
    """
    if not texto:
        return ()
    sem_acento = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return tuple(_PADRAO_NAO_ALFANUMERICO.sub(" ", sem_acento.lower()).split())


# --------------------------------------------------------------------------- #
# Estruturas
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Companhia:
    """Uma companhia do painel, identificada pelo `CD_CVM` (RN11)."""

    cd_cvm: str
    denom_social: str
    is_banco: bool = False

    def __post_init__(self) -> None:
        if not self.cd_cvm or not str(self.cd_cvm).strip():
            raise ValueError("cd_cvm é obrigatório: a companhia é o código")

    @property
    def rotulo(self) -> str:
        return f"{self.denom_social} (CD_CVM {self.cd_cvm})"


@dataclass(frozen=True)
class ResolucaoEntidade:
    """O que um termo resolveu no painel — zero, uma ou várias companhias.

    Nunca escolhe: quando há mais de uma candidata, o resultado correto é a
    pergunta de desambiguação (RN11).
    """

    termo: str
    candidatas: tuple[Companhia, ...] = ()
    motivo_ausencia: str | None = None

    @property
    def resolvida(self) -> Companhia | None:
        return self.candidatas[0] if len(self.candidatas) == 1 else None

    @property
    def ambigua(self) -> bool:
        return len(self.candidatas) > 1

    @property
    def vazia(self) -> bool:
        return not self.candidatas

    @property
    def assinatura(self) -> frozenset[str]:
        """Conjunto de códigos — usado para deduplicar menções equivalentes."""
        return frozenset(c.cd_cvm for c in self.candidatas)

    def pergunta_desambiguacao(self) -> str | None:
        """A pergunta que o sistema devolve em vez de adivinhar (RN11)."""
        if not self.ambigua:
            return None
        opcoes = "; ".join(c.rotulo for c in self.candidatas)
        return (
            f"'{self.termo}' identifica {len(self.candidatas)} companhias no "
            f"painel da CVM: {opcoes}. Qual delas? Responda com o CD_CVM — a "
            "seleção é sempre por código, nunca por nome."
        )

    def como_dicionario(self) -> dict:
        return {
            "termo": self.termo,
            "candidatas": [
                {
                    "cd_cvm": c.cd_cvm,
                    "denom_social": c.denom_social,
                    "is_banco": c.is_banco,
                }
                for c in self.candidatas
            ],
            "ambigua": self.ambigua,
            "motivo_ausencia": self.motivo_ausencia,
            "pergunta_desambiguacao": self.pergunta_desambiguacao(),
        }


@dataclass(frozen=True)
class Cobertura:
    """Em quais camadas a companhia (e, se pedido, o trimestre) existe."""

    estado: EstadoCobertura
    motivo: str
    companhia: Companhia | None = None
    trimestre: str | None = None
    trimestres_painel: tuple[str, ...] = ()
    trimestres_corpus: tuple[str, ...] = ()

    @property
    def no_painel(self) -> bool:
        return self.estado in (EstadoCobertura.AMBAS, EstadoCobertura.SO_PAINEL)

    @property
    def no_corpus(self) -> bool:
        return self.estado in (EstadoCobertura.AMBAS, EstadoCobertura.SO_CORPUS)

    def como_dicionario(self) -> dict:
        return {
            "estado": self.estado.value,
            "motivo": self.motivo,
            "cd_cvm": self.companhia.cd_cvm if self.companhia else None,
            "denom_social": self.companhia.denom_social if self.companhia else None,
            "trimestre": self.trimestre,
            "trimestres_painel": list(self.trimestres_painel),
            "trimestres_corpus": list(self.trimestres_corpus),
        }


@dataclass(frozen=True)
class Triagem:
    """Resolução + cobertura de um termo. `cobertura` é None se for ambíguo."""

    termo: str
    resolucao: ResolucaoEntidade
    cobertura: Cobertura | None

    @property
    def precisa_desambiguacao(self) -> bool:
        return self.resolucao.ambigua

    def pergunta_desambiguacao(self) -> str | None:
        return self.resolucao.pergunta_desambiguacao()

    def como_dicionario(self) -> dict:
        return {
            "termo": self.termo,
            "resolucao": self.resolucao.como_dicionario(),
            "cobertura": self.cobertura.como_dicionario() if self.cobertura else None,
            "precisa_desambiguacao": self.precisa_desambiguacao,
        }


# --------------------------------------------------------------------------- #
# Índice de cobertura
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class IndiceCobertura:
    """Fotografia das duas camadas: quem existe onde, e em quais trimestres.

    Construído uma vez e consultado em memória. `trimestres_corpus` vem do
    manifesto versionado (`corpus/metadados.csv`), que é a fonte de verdade
    declarada do corpus; o índice vetorial é amarrado a ele pelo hash da RNF09,
    então divergir dos dois seria sintoma de índice desatualizado, não de
    cobertura diferente.
    """

    companhias: tuple[Companhia, ...] = ()
    trimestres_painel: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    trimestres_corpus: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "companhias", tuple(self.companhias))
        for campo in ("trimestres_painel", "trimestres_corpus"):
            object.__setattr__(
                self,
                campo,
                {
                    cd: tuple(sorted(ts))
                    for cd, ts in dict(getattr(self, campo) or {}).items()
                },
            )
        por_codigo: dict[str, Companhia] = {}
        for companhia in self.companhias:
            if companhia.cd_cvm in por_codigo:
                raise ValueError(
                    f"cd_cvm duplicado no índice de cobertura: {companhia.cd_cvm}"
                )
            por_codigo[companhia.cd_cvm] = companhia
        object.__setattr__(self, "_por_codigo", por_codigo)

        frequencia: Counter[str] = Counter()
        for companhia in self.companhias:
            for token in set(tokenizar_nome(companhia.denom_social)):
                if token in TOKENS_GENERICOS or len(token) < 2:
                    continue
                frequencia[token] += 1
        por_token: dict[str, tuple[str, ...]] = {}
        for companhia in self.companhias:
            for token in set(tokenizar_nome(companhia.denom_social)):
                if frequencia.get(token, 0) > MAX_COMPANHIAS_POR_TOKEN_DISTINTIVO:
                    continue
                if token in TOKENS_GENERICOS or len(token) < 2:
                    continue
                por_token[token] = por_token.get(token, ()) + (companhia.cd_cvm,)
        object.__setattr__(
            self, "_por_token", {t: tuple(sorted(set(v))) for t, v in por_token.items()}
        )

        # Corpus sem contrapartida no painel: não é um estado da RN12, é
        # inconsistência. Fica no log em vez de virar `ambas` silenciosamente.
        orfas = sorted(set(self.trimestres_corpus) - por_codigo.keys())
        if orfas:
            registrador.warning(
                "cobertura: %d companhia(s) do corpus ausente(s) do painel "
                "(cd_cvm=%s) — estado 'so_corpus', fora do vocabulário da RN12",
                len(orfas),
                ",".join(orfas),
            )

    @property
    def por_codigo(self) -> Mapping[str, Companhia]:
        return getattr(self, "_por_codigo")

    @property
    def tokens_distintivos(self) -> Mapping[str, tuple[str, ...]]:
        return getattr(self, "_por_token")

    def companhia(self, cd_cvm: str) -> Companhia | None:
        return self.por_codigo.get(str(cd_cvm).strip())


# SQL fixo, escrito à mão e somente-leitura: não passa por `validar_sql` de
# propósito. As guardas da RN04 existem para SQL **gerado por modelo**, e o
# `LIMIT` obrigatório de lá (teto de `SQL_LIMITE_LINHAS=50`) não cabe num
# inventário de 470 companhias. A conexão é a mesma, somente-leitura.
_SQL_COMPANHIAS = """
    SELECT cd_cvm, denom_social, is_banco
    FROM companhias
    ORDER BY cd_cvm
"""
_SQL_TRIMESTRES = """
    SELECT cd_cvm, trimestre
    FROM fatos_semanticos
    GROUP BY cd_cvm, trimestre
    ORDER BY cd_cvm, trimestre
"""


def carregar_indice_cobertura(
    config: Config,
    caminho_painel: Path | None = None,
    caminho_manifesto: Path = CAMINHO_METADADOS_CORPUS,
) -> IndiceCobertura:
    """Lê painel (DuckDB) e manifesto do corpus e monta o índice de cobertura."""
    conexao = abrir_conexao_somente_leitura(config, caminho_painel)
    try:
        companhias = tuple(
            Companhia(cd_cvm=cd, denom_social=denom, is_banco=bool(banco))
            for cd, denom, banco in conexao.execute(_SQL_COMPANHIAS).fetchall()
        )
        painel: dict[str, set[str]] = {}
        for cd, trimestre in conexao.execute(_SQL_TRIMESTRES).fetchall():
            painel.setdefault(cd, set()).add(trimestre)
    finally:
        conexao.close()

    codigo_por_slug = {b.banco: b.cd_cvm for b in BANCOS_CORPUS}
    corpus: dict[str, set[str]] = {}
    for documento in carregar_metadados_corpus(caminho_manifesto):
        cd_cvm = codigo_por_slug.get(documento.empresa)
        if cd_cvm is None:
            # Sem `CD_CVM` conferido não há como atribuir o documento a uma
            # companhia sem escolher por nome — que é o que a RN11 proíbe.
            registrador.warning(
                "cobertura: manifesto cita empresa %r sem CD_CVM conferido em "
                "BANCOS_CORPUS; documento %r ficou fora da cobertura documental",
                documento.empresa,
                documento.documento,
            )
            continue
        corpus.setdefault(cd_cvm, set()).add(documento.trimestre)

    return IndiceCobertura(
        companhias=companhias,
        trimestres_painel=painel,
        trimestres_corpus=corpus,
    )


# --------------------------------------------------------------------------- #
# Resolução de entidade (RN11)
# --------------------------------------------------------------------------- #


def _codigos_por_apelido_do_corpus(termo: str) -> tuple[str, ...]:
    """Códigos que o apelido de corpus (`APELIDOS_BANCOS`) já conhece.

    Reusa a tabela de apelidos da recuperação e a de `CD_CVM` conferidos em
    `BANCOS_CORPUS`. Compor as duas evita uma terceira tabela de nomes — e
    "BB" ou "Banco do Brasil" não têm token distintivo no painel (`bco` está em
    9 companhias, `brasil` em 27), então sem esse caminho o Banco do Brasil
    cairia em `nenhuma`: exatamente o risco 12c.

    O apelido só vale quando **cobre o termo inteiro**, não quando aparece
    dentro dele. A tabela de apelidos existe para rotear busca documental, onde
    "BTG" é único porque o corpus tem um só BTG; ela é grossa demais para
    identificar companhia num painel de 470. Sem essa restrição, "BTG Pactual
    Commodities" — que é justamente como o usuário responde à desambiguação com
    palavras — voltaria a ser ambíguo por causa do apelido "btg pactual" que
    ele contém.
    """
    slug = canonizar_banco(termo)
    if slug is None:
        return ()
    tokens_termo = {t for t in tokenizar_nome(termo) if t not in TOKENS_GENERICOS}
    cobre_o_termo = any(
        tokens_termo <= set(tokenizar_nome(apelido))
        for apelido in APELIDOS_BANCOS.get(slug, ())
    )
    if not cobre_o_termo:
        return ()
    return tuple(b.cd_cvm for b in BANCOS_CORPUS if b.banco == slug)


def _candidatos(termo: str, indice: IndiceCobertura) -> tuple[Companhia, ...]:
    """Companhias que o termo pode designar — sem julgar e sem registrar log.

    Três caminhos, **unidos** e nunca intersectados: código explícito, apelido
    conferido do corpus e token distintivo da razão social. A união é o que
    mantém a regra honesta: um caminho pode acrescentar candidata, nenhum pode
    remover. Fosse o apelido do corpus a última palavra, "BTG" resolveria
    sozinho para `022616` (o único BTG do corpus documental) e a ambiguidade
    real do painel — `022616` e `027774` — sumiria sem ninguém ver.
    """
    codigos: list[str] = []

    # 1. O termo já é um CD_CVM (é assim que o usuário responde à desambiguação).
    apenas_digitos = termo.replace(".", "").replace("-", "").strip()
    if apenas_digitos.isdigit():
        codigos.append(normalizar_cd_cvm(apenas_digitos))

    # 2. Apelido de corpus conferido.
    codigos.extend(_codigos_por_apelido_do_corpus(termo))

    # 3. Tokens distintivos da razão social. Todos os tokens não genéricos do
    #    termo precisam apontar para a mesma companhia: "BTG Pactual
    #    Commodities" exige `btg` E `pactual` E `commodities`, o que resolve a
    #    ambiguidade sem o sistema ter escolhido nada.
    tokens = [t for t in tokenizar_nome(termo) if t not in TOKENS_GENERICOS]
    conjuntos = [
        conjunto
        for conjunto in (
            set(indice.tokens_distintivos.get(token, ())) for token in tokens
        )
        if conjunto
    ]
    if conjuntos:
        codigos.extend(sorted(set.intersection(*conjuntos)))

    unicas = {
        codigo: indice.companhia(codigo)
        for codigo in codigos
        if indice.companhia(codigo) is not None
    }
    return tuple(sorted(unicas.values(), key=lambda c: c.cd_cvm))


def resolver_entidade(termo: str, indice: IndiceCobertura) -> ResolucaoEntidade:
    """Resolve um termo em companhias do painel — por `CD_CVM` (RN11).

    Ponto único de registro: **toda** resolução vazia vai para o log, porque
    devolver `nenhuma` para companhia que está no painel é a mesma classe de
    erro que o projeto combate, invertida (risco 12c).
    """
    bruto = (termo or "").strip()
    if not bruto:
        return ResolucaoEntidade(termo=bruto)

    candidatas = _candidatos(bruto, indice)
    if candidatas:
        return ResolucaoEntidade(termo=bruto, candidatas=candidatas)

    slug = canonizar_banco(bruto)
    motivo = MOTIVO_AUSENCIA_DECLARADO.get(slug or "")
    registrador.warning(
        "cobertura: termo %r não resolveu nenhum CD_CVM no painel "
        "(%d companhias indexadas); motivo declarado=%s",
        bruto,
        len(indice.companhias),
        motivo or "desconhecido",
    )
    return ResolucaoEntidade(termo=bruto, motivo_ausencia=motivo)


def extrair_mencoes(pergunta: str, indice: IndiceCobertura) -> tuple[str, ...]:
    """Termos de companhia citados na pergunta, na ordem de aparição.

    Duas fontes: os apelidos de corpus já mapeados em `APELIDOS_BANCOS` (que
    incluem `NUBANK` justamente para a pergunta adversarial) e os tokens
    distintivos das razões sociais do painel — que é o que faz "e o Inter?"
    virar uma menção sem transformar "no Brasil" em outra.
    """
    texto = remover_acentos(pergunta or "").lower()
    achados: list[tuple[int, str]] = []
    for slug in extrair_bancos_citados(pergunta or ""):
        ocorrencias = [
            (texto.find(apelido), apelido)
            for apelido in APELIDOS_BANCOS.get(slug, ())
            if apelido in texto
        ]
        if not ocorrencias:
            achados.append((len(texto), slug))
            continue
        # Preserva a **forma de superfície**, nunca o slug. O slug perde
        # informação e reintroduz ambiguidade que o texto não tinha: "Banco do
        # Brasil" reduzido a "BB" passa a casar o token distintivo `bb`, que
        # designa também BB SEGURIDADE (023159) — e o sistema pede
        # desambiguação de um nome que era inequívoco. Já a forma longa tem
        # como único token não genérico `brasil`, presente em 27 companhias e
        # portanto fora do índice distintivo, então só o apelido conferido
        # responde. É a inversão do risco 12c: alegar ambiguidade onde não há.
        posicao = min(p for p, _ in ocorrencias)
        mais_especifico = max(
            (a for p, a in ocorrencias if p == posicao), key=len
        )
        achados.append((posicao, mais_especifico))
    for token in indice.tokens_distintivos:
        casado = re.search(r"\b" + re.escape(token) + r"\b", texto)
        if casado is not None:
            achados.append((casado.start(), token))
    achados.sort()

    # Dedupe pelo conjunto de códigos, não pelo texto: "BTG", "btg" e "pactual"
    # apontam para as mesmas duas companhias e são uma menção só. Usa
    # `_candidatos` em vez de `resolver_entidade` para não registrar a mesma
    # ausência duas vezes — o log da resolução vazia é responsabilidade de
    # `resolver_entidade`, chamado depois pela triagem.
    mencoes: list[str] = []
    assinaturas: list[frozenset[str]] = []
    for _, termo in achados:
        assinatura = frozenset(c.cd_cvm for c in _candidatos(termo, indice))
        if assinatura and assinatura in assinaturas:
            continue
        if not assinatura and termo in mencoes:
            continue
        assinaturas.append(assinatura)
        mencoes.append(termo)
    return tuple(mencoes)


# --------------------------------------------------------------------------- #
# Triagem de cobertura (RN12)
# --------------------------------------------------------------------------- #


def _classificar(
    companhia: Companhia,
    trimestre: str | None,
    no_painel: tuple[str, ...],
    no_corpus: tuple[str, ...],
) -> tuple[EstadoCobertura, str]:
    """Estado e motivo para uma companhia resolvida, com ou sem trimestre."""
    if trimestre is None:
        if no_painel and no_corpus:
            return EstadoCobertura.AMBAS, MOTIVO_NA
        if no_painel:
            return EstadoCobertura.SO_PAINEL, MOTIVO_FORA_DO_CORPUS
        if no_corpus:
            registrador.warning(
                "cobertura: %s tem release indexado e nenhum fato no painel — "
                "inconsistência, não estado da RN12",
                companhia.rotulo,
            )
            return EstadoCobertura.SO_CORPUS, MOTIVO_NA
        return EstadoCobertura.NENHUMA, MOTIVO_FORA_DO_CORPUS

    tem_painel = trimestre in no_painel
    tem_corpus = trimestre in no_corpus
    if tem_painel and tem_corpus:
        return EstadoCobertura.AMBAS, MOTIVO_NA
    if tem_painel:
        # A companhia pode estar nas duas camadas e ainda assim o trimestre
        # pedido só existir no painel: as duas janelas não coincidem. Responder
        # `ambas` aqui autorizaria a resposta a falar do release que não existe.
        motivo = MOTIVO_FORA_DO_CORPUS if not no_corpus else MOTIVO_PERIODO_AUSENTE
        return EstadoCobertura.SO_PAINEL, motivo
    if tem_corpus:
        registrador.warning(
            "cobertura: %s tem release de %s indexado sem fato correspondente "
            "no painel — inconsistência, não estado da RN12",
            companhia.rotulo,
            trimestre,
        )
        return EstadoCobertura.SO_CORPUS, MOTIVO_NA
    return EstadoCobertura.NENHUMA, MOTIVO_PERIODO_AUSENTE


def triar_entidade(
    termo: str,
    indice: IndiceCobertura,
    trimestre: str | None = None,
) -> Triagem:
    """Resolve o termo e classifica a cobertura (RN11 + RN12)."""
    resolucao = resolver_entidade(termo, indice)
    if resolucao.ambigua:
        return Triagem(termo=termo, resolucao=resolucao, cobertura=None)
    companhia = resolucao.resolvida
    if companhia is None:
        return Triagem(
            termo=termo,
            resolucao=resolucao,
            cobertura=Cobertura(
                estado=EstadoCobertura.NENHUMA,
                motivo=MOTIVO_FORA_DO_CORPUS,
                trimestre=trimestre,
            ),
        )
    no_painel = tuple(indice.trimestres_painel.get(companhia.cd_cvm, ()))
    no_corpus = tuple(indice.trimestres_corpus.get(companhia.cd_cvm, ()))
    estado, motivo = _classificar(companhia, trimestre, no_painel, no_corpus)
    return Triagem(
        termo=termo,
        resolucao=resolucao,
        cobertura=Cobertura(
            estado=estado,
            motivo=motivo,
            companhia=companhia,
            trimestre=trimestre,
            trimestres_painel=no_painel,
            trimestres_corpus=no_corpus,
        ),
    )


def triagem_cobertura(
    pergunta: str,
    indice: IndiceCobertura,
    trimestre: str | None = None,
) -> tuple[Triagem, ...]:
    """Triagem de todas as companhias citadas numa pergunta.

    O trimestre, quando não informado, é o primeiro citado na própria pergunta
    (vocabulário fechado de `src.normalizacao`).
    """
    periodos = extrair_trimestres_citados(pergunta or "")
    alvo = trimestre if trimestre is not None else (periodos[0] if periodos else None)
    return tuple(
        triar_entidade(termo, indice, alvo)
        for termo in extrair_mencoes(pergunta, indice)
    )


# --------------------------------------------------------------------------- #
# Braço C — determinístico, sem LLM (spec 5.9.3)
# --------------------------------------------------------------------------- #

# Vocabulário fechado de conceito, com casamento por trecho mais longo. Não é
# uma tentativa de entender a pergunta: é o gabarito fixo do braço C, e o que
# não estiver aqui produz resposta parcial declarada em vez de chute.
CONCEITOS_POR_EXPRESSAO: tuple[tuple[str, str], ...] = (
    ("lucro liquido consolidado", CONCEITO_LUCRO_CONSOLIDADO),
    ("lucro consolidado", CONCEITO_LUCRO_CONSOLIDADO),
    ("lucro liquido atribuido aos controladores", CONCEITO_LUCRO_CONTROLADORES),
    ("lucro liquido", CONCEITO_LUCRO_CONTROLADORES),
    ("lucro", CONCEITO_LUCRO_CONTROLADORES),
    ("patrimonio liquido", CONCEITO_PATRIMONIO_LIQUIDO),
    ("ativo total", CONCEITO_ATIVO_TOTAL),
    ("ativos totais", CONCEITO_ATIVO_TOTAL),
    ("receita de intermediacao financeira", CONCEITO_RECEITA_INTERMEDIACAO),
    ("receitas de intermediacao financeira", CONCEITO_RECEITA_INTERMEDIACAO),
)

# Como cada conceito é dito na resposta. "Lucro líquido" tem três leituras
# (gerencial, consolidado, controladores) e nenhuma resposta o usa sem
# qualificar qual — a regra vem de `src.mapa_contas`.
ROTULO_CONCEITO: Mapping[str, str] = {
    CONCEITO_LUCRO_CONSOLIDADO: "lucro líquido consolidado",
    CONCEITO_LUCRO_CONTROLADORES: (
        "lucro líquido atribuído aos sócios da empresa controladora"
    ),
    CONCEITO_PATRIMONIO_LIQUIDO: "patrimônio líquido consolidado",
    CONCEITO_ATIVO_TOTAL: "ativo total",
    CONCEITO_RECEITA_INTERMEDIACAO: "receita de intermediação financeira",
}


def extrair_conceito(pergunta: str) -> str | None:
    """Conceito contábil pedido, pelo trecho mais longo que casar."""
    texto = remover_acentos(pergunta or "").lower()
    melhor: tuple[int, str] | None = None
    for expressao, conceito in CONCEITOS_POR_EXPRESSAO:
        if expressao in texto and (melhor is None or len(expressao) > melhor[0]):
            melhor = (len(expressao), conceito)
    return melhor[1] if melhor else None


@dataclass(frozen=True)
class FatoEstruturado:
    """Um valor do painel com a procedência que a RN01/RN10 exigem citar."""

    cd_cvm: str
    denom_social: str
    trimestre: str
    conceito: str
    valor_reais: float
    origem: str = "arquivado"
    ds_conta: str = ""

    @property
    def derivado(self) -> bool:
        return self.origem == "derivado"

    def citacao(self) -> str:
        base = (
            f"CVM · {self.denom_social} (CD_CVM {self.cd_cvm}) · {self.trimestre} "
            f"· {ROTULO_CONCEITO.get(self.conceito, self.conceito)}"
        )
        if self.derivado:
            # RN10: o 4T não existe como ITR; sai marcado, com a conta dita.
            conta = f" a partir de {self.ds_conta}" if self.ds_conta else ""
            return f"{base} · valor DERIVADO (DFP anual − ITR acumulado do 3T){conta}"
        return f"{base} · arquivado"


class LeitorDeFatos(Protocol):
    """Fonte de valores do painel usada pelo braço C.

    Protocolo em vez de dependência direta de `src.dados_estruturados`: mantém
    `cobertura.py` puro e testável sem DuckDB, e deixa a implementação real em
    `src.ferramentas`, que é quem já carrega o painel.
    """

    def ler(
        self, cd_cvm: str, conceito: str, trimestre: str
    ) -> FatoEstruturado | None:  # pragma: no cover - protocolo
        ...


def formatar_reais(valor: float) -> str:
    """Formata em reais na convenção pt-BR: milhar com `.`, decimal com `,`.

    Agrupamento feito à mão em vez de `locale`: o locale pt_BR pode não estar
    instalado no contêiner, e uma resposta financeira que troca o separador
    decimal conforme a máquina é a definição de número plausível e errado.
    """
    inteiro, _, decimais = f"{abs(float(valor)):.2f}".partition(".")
    grupos: list[str] = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    sinal = "-" if valor < 0 else ""
    return f"R$ {sinal}{'.'.join(grupos)},{decimais}"


def formatar_reais_legivel(valor: float) -> str:
    """`R$ 5,24 bilhões` para leitura; o valor exato segue ao lado na tela.

    Arredonda para duas casas na escala — é para ler em voz alta, nunca para
    conferir. Por isso a resposta do painel mostra os dois, e a coluna `valor`
    da tabela continua exata.
    """
    absoluto = abs(float(valor))
    for escala, singular, plural in (
        (1e12, "trilhão", "trilhões"),
        (1e9, "bilhão", "bilhões"),
        (1e6, "milhão", "milhões"),
    ):
        if absoluto >= escala:
            numero = f"{absoluto / escala:.2f}".replace(".", ",")
            # Norma culta: "1,5 bilhão", "2 bilhões" — singular abaixo de dois.
            unidade = singular if absoluto / escala < 2 else plural
            sinal = "-" if valor < 0 else ""
            return f"{sinal}R$ {numero} {unidade}"
    return formatar_reais(valor)


@dataclass(frozen=True)
class RespostaDeterministica:
    """Saída do braço C — montada por gabarito fixo, sem nenhuma chamada de LLM.

    `parcial` marca o que o gabarito não cobre: o braço C responde cobertura e
    número contábil, e **não** responde narrativa de release. Marcar isso é o
    que torna a comparação com os braços A e B honesta — um piso que fingisse
    responder tudo não seria piso, seria ruído.
    """

    pergunta: str
    resposta: str
    recusa: bool = False
    motivo_recusa: str = MOTIVO_NA
    parcial: bool = False
    precisa_desambiguacao: bool = False
    triagens: tuple[Triagem, ...] = ()
    fatos: tuple[FatoEstruturado, ...] = ()
    braco: str = "C"

    @property
    def citacoes(self) -> tuple[str, ...]:
        return tuple(fato.citacao() for fato in self.fatos)

    def como_dicionario(self) -> dict:
        return {
            "braco": self.braco,
            "pergunta": self.pergunta,
            "resposta": self.resposta,
            "recusa": self.recusa,
            "motivo_recusa": self.motivo_recusa,
            "parcial": self.parcial,
            "precisa_desambiguacao": self.precisa_desambiguacao,
            "citacoes": list(self.citacoes),
            "triagens": [t.como_dicionario() for t in self.triagens],
        }


def _texto_ambas(cobertura: Cobertura) -> str:
    companhia = cobertura.companhia
    assert companhia is not None
    periodo = (
        f" em {cobertura.trimestre}" if cobertura.trimestre else ""
    )
    return (
        f"{companhia.rotulo} está nas duas camadas{periodo}: há release "
        f"indexado ({', '.join(cobertura.trimestres_corpus) or 'nenhum trimestre'}) "
        f"e fatos contábeis no painel da CVM "
        f"({', '.join(cobertura.trimestres_painel) or 'nenhum trimestre'})."
    )


def _texto_so_painel(cobertura: Cobertura) -> str:
    companhia = cobertura.companhia
    assert companhia is not None
    periodo = f" para {cobertura.trimestre}" if cobertura.trimestre else ""
    return (
        f"{companhia.rotulo} arquiva na CVM e o painel cobre "
        f"{', '.join(cobertura.trimestres_painel) or 'nenhum trimestre'}, mas "
        f"NÃO há release indexado{periodo} no corpus documental. Logo, o número "
        "contábil é respondível e nada pode ser dito sobre o que a "
        "administração declarou no release."
    )


def _texto_nenhuma(triagem: Triagem, cobertura: Cobertura) -> str:
    if cobertura.companhia is None:
        motivo = triagem.resolucao.motivo_ausencia
        explicacao = (
            f" Motivo: {motivo}."
            if motivo
            else (
                " Nenhuma companhia com esse nome foi encontrada no painel da "
                "CVM, e não há release dela no corpus documental."
            )
        )
        return (
            f"Não há cobertura para '{triagem.termo}' em nenhuma das duas "
            f"camadas.{explicacao}"
        )
    companhia = cobertura.companhia
    return (
        f"{companhia.rotulo} existe no painel, mas o trimestre "
        f"{cobertura.trimestre} não está em nenhuma das duas camadas: o painel "
        f"cobre {', '.join(cobertura.trimestres_painel) or 'nenhum trimestre'} e "
        f"o corpus documental cobre "
        f"{', '.join(cobertura.trimestres_corpus) or 'nenhum trimestre'}."
    )


def _texto_so_corpus(cobertura: Cobertura) -> str:
    companhia = cobertura.companhia
    assert companhia is not None
    return (
        f"{companhia.rotulo} tem release indexado "
        f"({', '.join(cobertura.trimestres_corpus) or 'nenhum trimestre'}) e "
        "nenhum fato correspondente no painel da CVM. Esse estado não pertence "
        "ao vocabulário da RN12 e indica inconsistência entre as camadas — a "
        "resposta fica limitada ao documento."
    )


def descrever_cobertura(triagem: Triagem) -> str:
    """Frase de gabarito para o estado de cobertura de uma triagem."""
    if triagem.precisa_desambiguacao:
        return triagem.pergunta_desambiguacao() or ""
    cobertura = triagem.cobertura
    assert cobertura is not None
    if cobertura.estado is EstadoCobertura.AMBAS:
        return _texto_ambas(cobertura)
    if cobertura.estado is EstadoCobertura.SO_PAINEL:
        return _texto_so_painel(cobertura)
    if cobertura.estado is EstadoCobertura.SO_CORPUS:
        return _texto_so_corpus(cobertura)
    return _texto_nenhuma(triagem, cobertura)


def responder_por_gabarito(
    pergunta: str,
    indice: IndiceCobertura,
    leitor: LeitorDeFatos | None = None,
) -> RespostaDeterministica:
    """Braço C: resolução de entidade + cobertura + gabarito fixo, sem LLM.

    Regras, na ordem em que valem:

    1. **Ambiguidade primeiro.** Nome que resolve para mais de uma companhia
       devolve a pergunta de desambiguação e para (RN11). Não há resposta
       "provável".
    2. **`nenhuma` é recusa que nomeia a ausência** (RN12), com o motivo do
       vocabulário congelado (`fora_do_corpus` ou `periodo_ausente`).
    3. **`so_painel` responde o número e diz o que falta** — é a metade
       verdadeira que a arquitetura anterior jogava fora.
    4. **`ambas` devolve o estado e o número contábil**; a leitura do release
       exige a camada documental e sai marcada como parcial.
    """
    triagens = triagem_cobertura(pergunta, indice)
    if not triagens:
        return RespostaDeterministica(
            pergunta=pergunta,
            resposta=(
                "Nenhuma companhia foi identificada na pergunta. O braço "
                "determinístico responde cobertura e número contábil por "
                "companhia; sem companhia não há o que consultar."
            ),
            recusa=True,
            motivo_recusa=MOTIVO_FORA_DO_CORPUS,
            parcial=True,
        )

    ambiguas = [t for t in triagens if t.precisa_desambiguacao]
    if ambiguas:
        return RespostaDeterministica(
            pergunta=pergunta,
            resposta=" ".join(
                t.pergunta_desambiguacao() or "" for t in ambiguas
            ).strip(),
            precisa_desambiguacao=True,
            parcial=True,
            triagens=triagens,
        )

    trimestres = extrair_trimestres_citados(pergunta or "")
    conceito = extrair_conceito(pergunta)
    partes: list[str] = []
    fatos: list[FatoEstruturado] = []
    parcial = False
    for triagem in triagens:
        partes.append(descrever_cobertura(triagem))
        cobertura = triagem.cobertura
        assert cobertura is not None
        if not cobertura.no_painel or cobertura.companhia is None:
            continue
        if conceito is None:
            parcial = True
            continue
        if leitor is None:
            parcial = True
            partes.append(
                "O valor não foi consultado: o braço determinístico foi "
                "executado sem leitor do painel."
            )
            continue
        alvos = trimestres or list(cobertura.trimestres_painel)
        for alvo in alvos:
            fato = leitor.ler(cobertura.companhia.cd_cvm, conceito, alvo)
            if fato is None:
                parcial = True
                partes.append(
                    f"O painel não traz "
                    f"{ROTULO_CONCEITO.get(conceito, conceito)} de "
                    f"{cobertura.companhia.rotulo} em {alvo}."
                )
                continue
            fatos.append(fato)
            marca = " (valor derivado, RN10)" if fato.derivado else ""
            partes.append(
                f"{ROTULO_CONCEITO.get(conceito, conceito).capitalize()} de "
                f"{cobertura.companhia.denom_social} em {alvo}: "
                f"{formatar_reais(fato.valor_reais)}{marca}."
            )

    estados = {t.cobertura.estado for t in triagens if t.cobertura is not None}
    recusa = estados == {EstadoCobertura.NENHUMA}
    motivo = MOTIVO_NA
    if recusa:
        motivos = {
            t.cobertura.motivo for t in triagens if t.cobertura is not None
        }
        motivo = motivos.pop() if len(motivos) == 1 else MOTIVO_FORA_DO_CORPUS
    if EstadoCobertura.SO_PAINEL in estados or EstadoCobertura.SO_CORPUS in estados:
        parcial = True
    return RespostaDeterministica(
        pergunta=pergunta,
        resposta=" ".join(p for p in partes if p),
        recusa=recusa,
        motivo_recusa=motivo,
        parcial=parcial and not recusa,
        triagens=triagens,
        fatos=tuple(fatos),
    )


# Rótulo de prosa. `ROTULO_CONCEITO` é preciso e serve à auditoria — é ele que
# vai para a tabela de fatos e para a citação da RN01. Repetido dentro de cada
# frase, porém, era metade do que tornava a resposta ilegível: "lucro líquido
# atribuído aos sócios da empresa controladora" seis vezes seguidas.
#
# O parêntese em "lucro líquido (controladores)" fica de propósito. As três
# leituras de lucro diferem em centenas de milhões (medido: R$ 294 mi no
# 3T2025 do Itaú), e chamar a leitura dos controladores só de "lucro líquido"
# economizaria uma palavra ao preço da distinção que o projeto existe para
# manter.
ROTULO_CURTO_CONCEITO: Mapping[str, str] = {
    CONCEITO_LUCRO_CONSOLIDADO: "lucro líquido consolidado",
    CONCEITO_LUCRO_CONTROLADORES: "lucro líquido (controladores)",
    CONCEITO_LUCRO_NAO_CONTROLADORES: "lucro líquido dos não controladores",
    CONCEITO_PATRIMONIO_LIQUIDO: "patrimônio líquido",
    CONCEITO_ATIVO_TOTAL: "ativo total",
    CONCEITO_RECEITA_INTERMEDIACAO: "receita de intermediação financeira",
}


def rotulo_curto(conceito: str) -> str:
    """Nome do conceito para prosa, com queda para o rótulo de auditoria."""
    return ROTULO_CURTO_CONCEITO.get(
        conceito, ROTULO_CONCEITO.get(conceito, conceito)
    )


def _valor_com_marca(fato: FatoEstruturado) -> str:
    """`R$ 11,91 bilhões (derivado)` — legível, com a marca da RN10 colada."""
    legivel = formatar_reais_legivel(fato.valor_reais)
    return f"{legivel} (derivado)" if fato.derivado else legivel


def _enumerar(partes: list[str]) -> str:
    """`a`, `a e b`, `a, b e c` — enumeração em português, não lista de log."""
    if len(partes) <= 1:
        return "".join(partes)
    return f"{', '.join(partes[:-1])} e {partes[-1]}"


def _frase_do_grupo(
    fatos: tuple[FatoEstruturado, ...], intervalo: PeriodoPedido | None
) -> str:
    """Uma frase para um (companhia, conceito) — somando só quando é lícito."""
    conceito = fatos[0].conceito
    rotulo = rotulo_curto(conceito)
    empresa = fatos[0].denom_social

    if len(fatos) == 1:
        fato = fatos[0]
        exato = formatar_reais(fato.valor_reais)
        marca = " — valor derivado (RN10)" if fato.derivado else ""
        return (
            f"O {rotulo} de {empresa} em {fato.trimestre} foi de "
            f"{formatar_reais_legivel(fato.valor_reais)} ({exato}){marca}."
        )

    cobre_o_intervalo = intervalo is not None and {
        f.trimestre for f in fatos
    } == set(intervalo.trimestres)
    partes = _enumerar(
        [f"{_valor_com_marca(f)} em {f.trimestre}" for f in fatos]
    )

    # Somar trimestres só vale para conta de resultado. Saldo de balanço é
    # instantâneo: somar dois 31/12 não produz patrimônio nenhum, produz um
    # número plausível e sem significado — a falha exata que o projeto combate.
    if cobre_o_intervalo and conceito in CONCEITOS_DE_FLUXO:
        total = sum(f.valor_reais for f in fatos)
        houve_derivado = any(f.derivado for f in fatos)
        nota = " Inclui valor derivado (RN10)." if houve_derivado else ""
        return (
            f"O {rotulo} de {empresa} no {intervalo.rotulo} foi de "
            f"{formatar_reais_legivel(total)} ({formatar_reais(total)}), "
            f"soma de {partes}.{nota}"
        )
    if cobre_o_intervalo:
        return (
            f"{rotulo.capitalize()} é saldo de balanço e não se soma entre "
            f"trimestres. De {empresa}: {partes}."
        )
    return f"O {rotulo} de {empresa}: {partes}."


def redigir_conversacional(
    resposta: RespostaDeterministica, pergunta: str = ""
) -> str:
    """Resposta do painel em prosa direta, para a interface.

    `RespostaDeterministica.resposta` descreve **cobertura** e depois enfileira
    uma frase completa por fato — formato certo para o braço C, que é medido
    contra os braços com agente e precisa expor o que sabe. Na tela do produto
    isso virava uma parede: nome da companhia e do conceito repetidos a cada
    trimestre, precedidos de um parágrafo sobre camadas que ninguém perguntou.

    Aqui a mesma evidência é dita uma vez. O que sustenta as regras não sai da
    tela, muda de lugar: a procedência da RN01 vive na tabela de fatos e no
    expansor de citações, a marca da RN10 fica colada ao valor, e a ausência da
    RN12 continua sendo declarada — quando há o que declarar.
    """
    if resposta.precisa_desambiguacao or resposta.recusa or not resposta.fatos:
        # Desambiguação, recusa classificada e "o painel não traz X em Y" já
        # são curtas e carregam o motivo; reescrevê-las só perderia informação.
        return resposta.resposta

    periodos = extrair_periodos_citados(pergunta or "")
    intervalo = (
        periodos[0] if len(periodos) == 1 and periodos[0].e_intervalo else None
    )

    grupos: dict[tuple[str, str], list[FatoEstruturado]] = {}
    for fato in resposta.fatos:
        grupos.setdefault((fato.cd_cvm, fato.conceito), []).append(fato)

    return " ".join(
        _frase_do_grupo(tuple(fatos), intervalo) for fatos in grupos.values()
    )


def companhias_do_corpus(indice: IndiceCobertura) -> tuple[Companhia, ...]:
    """Companhias com release indexado, na ordem do código."""
    return tuple(
        companhia
        for companhia in sorted(indice.companhias, key=lambda c: c.cd_cvm)
        if indice.trimestres_corpus.get(companhia.cd_cvm)
    )


def companhias_so_no_painel(
    indice: IndiceCobertura, apenas_bancos: bool = True
) -> tuple[Companhia, ...]:
    """Companhias que arquivam na CVM e não têm release indexado.

    É a lista que torna o estado `so_painel` verificável contra o painel real:
    Inter & Co (080217), BMG (024600), Daycoval (020796), Mercantil do Brasil
    (001325), Pine (020567) e IRB (024180) estão aqui; nenhuma no corpus.
    """
    return tuple(
        companhia
        for companhia in sorted(indice.companhias, key=lambda c: c.cd_cvm)
        if not indice.trimestres_corpus.get(companhia.cd_cvm)
        and (companhia.is_banco or not apenas_bancos)
    )


__all__ = [
    "CONCEITOS_POR_EXPRESSAO",
    "Cobertura",
    "Companhia",
    "EstadoCobertura",
    "ESTADOS_RN12",
    "FatoEstruturado",
    "IndiceCobertura",
    "LeitorDeFatos",
    "MOTIVO_AUSENCIA_DECLARADO",
    "MOTIVO_FORA_DO_CORPUS",
    "MOTIVO_NA",
    "MOTIVO_PERIODO_AUSENTE",
    "ResolucaoEntidade",
    "RespostaDeterministica",
    "ROTULO_CONCEITO",
    "TOKENS_GENERICOS",
    "Triagem",
    "carregar_indice_cobertura",
    "companhias_do_corpus",
    "companhias_so_no_painel",
    "descrever_cobertura",
    "extrair_conceito",
    "extrair_mencoes",
    "formatar_reais",
    "resolver_entidade",
    "responder_por_gabarito",
    "tokenizar_nome",
    "triagem_cobertura",
    "triar_entidade",
]
