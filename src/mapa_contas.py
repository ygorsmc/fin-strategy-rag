"""Mapa semântico conta→conceito do painel contábil da CVM (spec 5.5, RN09).

`CD_CONTA` **não é chave de significado**. O plano de contas da DRE varia com o
tipo de companhia e o mesmo código carrega contas diferentes: `3.09` é o lucro
líquido consolidado no Itaú/Santander/BTG e o *Lucro ou Prejuízo antes das
Participações e Contribuições Estatutárias* no Banco do Brasil/Bradesco, cujo
lucro consolidado está em `3.11`. O mesmo vale no balanço: *Patrimônio Líquido
Consolidado* é `2.07` em BB/Bradesco e `2.08` nos outros três, e `2.03` significa
*Provisões* nos dois primeiros e *Passivos Financeiros ao Custo Amortizado* nos
demais.

Por isso a resolução é feita sobre `DS_CONTA` **normalizada** (sem acento, sem
pontuação, minúscula) e nunca sobre o código. O código entra apenas como guarda
estrutural: `lucro_liquido_controladores` só é aceito se for subconta direta da
linha que carrega o `lucro_liquido_consolidado` da própria companhia.

Este módulo é a camada pura (sem I/O, sem banco) usada por
`src.dados_estruturados` para materializar a tabela `mapa_contas` e a visão
`fatos_semanticos`.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Mapping

# --------------------------------------------------------------------------- #
# Conceitos
# --------------------------------------------------------------------------- #

CONCEITO_LUCRO_CONSOLIDADO = "lucro_liquido_consolidado"
CONCEITO_LUCRO_CONTROLADORES = "lucro_liquido_controladores"
CONCEITO_LUCRO_NAO_CONTROLADORES = "lucro_liquido_nao_controladores"
CONCEITO_RECEITA_INTERMEDIACAO = "receita_intermediacao_financeira"
CONCEITO_DESPESA_INTERMEDIACAO = "despesa_intermediacao_financeira"
CONCEITO_RESULTADO_BRUTO_INTERMEDIACAO = "resultado_bruto_intermediacao"
CONCEITO_RESULTADO_ANTES_TRIBUTOS = "resultado_antes_tributos"
CONCEITO_IMPOSTO_RENDA_CSLL = "imposto_renda_csll"
CONCEITO_PATRIMONIO_LIQUIDO = "patrimonio_liquido_consolidado"
CONCEITO_ATIVO_TOTAL = "ativo_total"
CONCEITO_PASSIVO_TOTAL = "passivo_total"

# "Lucro líquido" tem três leituras (pesquisa técnica 2.5): o gerencial do
# release, o consolidado total e o atribuído aos controladores. O padrão exibido
# é o dos controladores, por ser a convenção de mercado e a base do lucro por
# ação — mas NENHUMA resposta usa "lucro líquido" sem qualificar qual.
CONCEITO_LUCRO_PADRAO = CONCEITO_LUCRO_CONTROLADORES

CONCEITOS: tuple[str, ...] = (
    CONCEITO_ATIVO_TOTAL,
    CONCEITO_DESPESA_INTERMEDIACAO,
    CONCEITO_IMPOSTO_RENDA_CSLL,
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_LUCRO_NAO_CONTROLADORES,
    CONCEITO_PASSIVO_TOTAL,
    CONCEITO_PATRIMONIO_LIQUIDO,
    CONCEITO_RECEITA_INTERMEDIACAO,
    CONCEITO_RESULTADO_ANTES_TRIBUTOS,
    CONCEITO_RESULTADO_BRUTO_INTERMEDIACAO,
)

# Conceitos cuja linha é subconta direta do lucro consolidado. A guarda
# estrutural existe porque a descrição "Atribuído a Sócios da Empresa
# Controladora" é genérica: só vale como lucro dos controladores quando pende da
# linha de resultado consolidado da própria companhia.
CONCEITOS_FILHOS_DO_LUCRO: frozenset[str] = frozenset(
    {CONCEITO_LUCRO_CONTROLADORES, CONCEITO_LUCRO_NAO_CONTROLADORES}
)

# Conceitos de fluxo (DRE) — únicos elegíveis à derivação do 4º trimestre
# (RN10: DFP anual − ITR acumulado do 3T). Saldos de balanço são instantâneos e
# o valor de 31/12 é arquivado, não derivado.
CONCEITOS_DE_FLUXO: frozenset[str] = frozenset(
    {
        CONCEITO_DESPESA_INTERMEDIACAO,
        CONCEITO_IMPOSTO_RENDA_CSLL,
        CONCEITO_LUCRO_CONSOLIDADO,
        CONCEITO_LUCRO_CONTROLADORES,
        CONCEITO_LUCRO_NAO_CONTROLADORES,
        CONCEITO_RECEITA_INTERMEDIACAO,
        CONCEITO_RESULTADO_ANTES_TRIBUTOS,
        CONCEITO_RESULTADO_BRUTO_INTERMEDIACAO,
    }
)

# --------------------------------------------------------------------------- #
# Quebra de série — Resolução CMN 4.966/21 (pesquisa técnica 2.4b)
# --------------------------------------------------------------------------- #

ANO_VIGENCIA_CMN_4966 = 2025
NOTA_QUEBRA_SERIE_4966 = (
    "Comparação atravessa 01/01/2025, data de vigência da Resolução CMN "
    "4.966/21, que substituiu a CMN 2.682/99 e trocou perda incorrida por perda "
    "esperada em três estágios. Os dois lados da comparação seguem "
    "contabilidades diferentes."
)

_PADRAO_TRIMESTRE = re.compile(r"^([1-4])T(\d{4})$")


def ano_do_trimestre(trimestre: str) -> int:
    """Extrai o ano do rótulo `NTAAAA` (ex.: `3T2025` → 2025)."""
    casado = _PADRAO_TRIMESTRE.fullmatch((trimestre or "").strip().upper())
    if casado is None:
        raise ValueError(f"trimestre inválido: {trimestre!r}")
    return int(casado.group(2))


def comparacao_cruza_quebra_4966(trimestre_a: str, trimestre_b: str) -> bool:
    """True se a comparação entre dois trimestres atravessa 01/01/2025.

    Toda a janela do corpus está do lado novo da quebra, mas o `PENÚLTIMO` dos
    arquivos e qualquer variação anual pedida sobre 2024 está do lado velho —
    e o dado não traz nenhuma marca disso.
    """
    ano_a = ano_do_trimestre(trimestre_a)
    ano_b = ano_do_trimestre(trimestre_b)
    return min(ano_a, ano_b) < ANO_VIGENCIA_CMN_4966 <= max(ano_a, ano_b)


# --------------------------------------------------------------------------- #
# Normalização de descrição
# --------------------------------------------------------------------------- #


def normalizar_ds_conta(texto: str | None) -> str:
    """Reduz `DS_CONTA` à forma comparável: sem acento, sem pontuação, minúscula.

    `Lucro/Prejuízo Consolidado do Período` e
    `Lucro ou Prejuízo Líquido Consolidado do Período` são a mesma linha final
    escrita por planos de contas diferentes; a normalização é o que permite
    tratá-las pelo significado em vez do código.
    """
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    apenas_alfanumerico = re.sub(r"[^0-9a-zA-Z]+", " ", sem_acento.lower())
    return " ".join(apenas_alfanumerico.split())


# --------------------------------------------------------------------------- #
# Regras
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RegraConceito:
    """Uma regra de resolução: descrição normalizada → conceito.

    `padrao` casa a descrição inteira (`fullmatch`) de propósito: casamento
    parcial confundiria `Lucro ou Prejuízo antes das Participações e
    Contribuições Estatutárias` com o lucro líquido, que é exatamente a
    armadilha que este módulo existe para impedir.
    """

    conceito: str
    padrao: re.Pattern[str]
    exemplo: str


def _p(expressao: str) -> re.Pattern[str]:
    return re.compile(expressao)


REGRAS: tuple[RegraConceito, ...] = (
    RegraConceito(
        conceito=CONCEITO_LUCRO_CONSOLIDADO,
        padrao=_p(r"lucro (ou )?prejuizo (liquido )?consolidado do periodo"),
        exemplo="Lucro ou Prejuízo Líquido Consolidado do Período",
    ),
    RegraConceito(
        conceito=CONCEITO_LUCRO_CONTROLADORES,
        padrao=_p(r"atribuido a(?:os)? socios da empresa controladora"),
        exemplo="Atribuído aos Sócios da Empresa Controladora",
    ),
    RegraConceito(
        conceito=CONCEITO_LUCRO_NAO_CONTROLADORES,
        padrao=_p(r"atribuido a(?:os)? socios nao controladores"),
        exemplo="Atribuído aos Sócios não Controladores",
    ),
    RegraConceito(
        conceito=CONCEITO_RECEITA_INTERMEDIACAO,
        padrao=_p(r"receitas? (da|de) intermediacao financeira"),
        exemplo="Receitas de Intermediação Financeira",
    ),
    RegraConceito(
        conceito=CONCEITO_DESPESA_INTERMEDIACAO,
        padrao=_p(r"despesas? (da|de) intermediacao financeira"),
        exemplo="Despesas da Intermediação Financeira",
    ),
    RegraConceito(
        conceito=CONCEITO_RESULTADO_BRUTO_INTERMEDIACAO,
        padrao=_p(r"resultado bruto (da |de )?intermediacao financeira"),
        exemplo="Resultado Bruto Intermediação Financeira",
    ),
    RegraConceito(
        conceito=CONCEITO_RESULTADO_ANTES_TRIBUTOS,
        padrao=_p(r"resultado antes (dos|de) tributos sobre o lucro"),
        exemplo="Resultado Antes dos Tributos sobre o Lucro",
    ),
    RegraConceito(
        conceito=CONCEITO_IMPOSTO_RENDA_CSLL,
        padrao=_p(
            r"imposto de renda e contribuicao social sobre o lucro"
        ),
        exemplo="Imposto de Renda e Contribuição Social sobre o Lucro",
    ),
    RegraConceito(
        conceito=CONCEITO_PATRIMONIO_LIQUIDO,
        padrao=_p(r"patrimonio liquido consolidado"),
        exemplo="Patrimônio Líquido Consolidado",
    ),
    RegraConceito(
        conceito=CONCEITO_ATIVO_TOTAL,
        padrao=_p(r"ativo total"),
        exemplo="Ativo Total",
    ),
    RegraConceito(
        conceito=CONCEITO_PASSIVO_TOTAL,
        padrao=_p(r"passivo total"),
        exemplo="Passivo Total",
    ),
)

# Conceitos deliberadamente FORA do mapa, com o motivo — a ausência é decisão,
# não esquecimento. Mapear qualquer um deles hoje produziria comparação entre
# grandezas diferentes, que é a falha silenciosa que a camada existe para
# impedir.
CONCEITOS_RECUSADOS: Mapping[str, str] = {
    "provisao_perda_esperada_credito": (
        "a linha não é comparável entre os cinco bancos: BB e Bradesco a "
        "publicam em 3.04.01 ('Despesa de Provisão para Perda Esperada para "
        "Risco de Crédito'), o BTG em 3.01.02 ('Perdas esperadas decorrentes "
        "de risco de crédito'), o Itaú a divide entre 3.02.02 e 3.02.03 e o "
        "Santander só traz 'Provisões (líquidas)' em 3.04.06.02, que inclui "
        "provisões não creditícias. Somar isso entre bancos seria comparar "
        "escopos diferentes com aparência de linha única."
    ),
    "lucro_liquido_gerencial": (
        "não existe na CVM: é o número ajustado divulgado no release, e a tese "
        "do projeto é justamente que ele diverge do contábil por definição. "
        "Vem da camada documental, nunca desta."
    ),
}


def conceito_de_descricao(ds_conta: str | None) -> str | None:
    """Resolve a descrição da conta em um conceito, ou None se não houver.

    Não recebe `cd_conta` de propósito: o código não participa da resolução
    semântica (RN09). A guarda estrutural por código é aplicada depois, em
    `resolver_mapa_da_companhia`.
    """
    normalizada = normalizar_ds_conta(ds_conta)
    if not normalizada:
        return None
    for regra in REGRAS:
        if regra.padrao.fullmatch(normalizada):
            return regra.conceito
    return None


def e_subconta_direta(cd_conta_filho: str, cd_conta_pai: str) -> bool:
    """True se `3.09.01` pende diretamente de `3.09` (e não de `3.11`)."""
    filho = (cd_conta_filho or "").strip()
    pai = (cd_conta_pai or "").strip()
    if not filho or not pai or filho == pai:
        return False
    resto = filho[len(pai):] if filho.startswith(pai) else ""
    return bool(re.fullmatch(r"\.\d{2}", resto))


# --------------------------------------------------------------------------- #
# Resolução por companhia
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ContaObservada:
    """Uma linha (cd_conta, ds_conta) vista nos arquivos de uma companhia."""

    cd_conta: str
    ds_conta: str


@dataclass(frozen=True)
class EntradaMapa:
    """Uma linha da tabela `mapa_contas`.

    `ds_conta_normalizada` faz parte da chave, e não é redundância: o Santander
    publica `3.09` como *Lucro/Prejuízo Consolidado do Período* no ITR e, na DFP
    do mesmo ano, publica `3.09` como *Lucro ou Prejuízo antes das Participações*
    com o resultado final em `3.11`. Casar só pelo código exporia a linha errada
    como se fosse o lucro (verificado em 2026-08-10).
    """

    conceito: str
    cd_conta: str
    ds_conta_esperada: str

    @property
    def ds_conta_normalizada(self) -> str:
        return normalizar_ds_conta(self.ds_conta_esperada)


class ConflitoMapaContasError(ValueError):
    """O mesmo `cd_conta` resolveria dois conceitos na mesma companhia.

    Não é tratado com escolha automática: seria exatamente o tipo de decisão
    silenciosa que produz número plausível e errado.
    """


def resolver_mapa_da_companhia(
    contas: Iterable[ContaObservada],
) -> tuple[EntradaMapa, ...]:
    """Resolve as contas observadas de UMA companhia em entradas do mapa.

    Passo 1: casa cada descrição normalizada contra as regras.
    Passo 2: aplica a guarda estrutural — `lucro_liquido_controladores` e
    `lucro_liquido_nao_controladores` só valem se forem subconta direta da
    linha que carrega o lucro consolidado desta companhia. É a guarda que
    impede `3.09.01` de ser aceito como lucro dos controladores em uma
    companhia cujo lucro consolidado está em `3.11`.
    """
    candidatos: dict[tuple[str, str, str], EntradaMapa] = {}
    for conta in contas:
        conceito = conceito_de_descricao(conta.ds_conta)
        if conceito is None:
            continue
        cd_conta = (conta.cd_conta or "").strip()
        if not cd_conta:
            continue
        entrada = EntradaMapa(
            conceito=conceito,
            cd_conta=cd_conta,
            ds_conta_esperada=(conta.ds_conta or "").strip(),
        )
        candidatos[(conceito, cd_conta, entrada.ds_conta_normalizada)] = entrada

    codigos_lucro = sorted(
        entrada.cd_conta
        for entrada in candidatos.values()
        if entrada.conceito == CONCEITO_LUCRO_CONSOLIDADO
    )
    resolvidas: list[EntradaMapa] = []
    for entrada in candidatos.values():
        if entrada.conceito in CONCEITOS_FILHOS_DO_LUCRO:
            if not any(
                e_subconta_direta(entrada.cd_conta, pai) for pai in codigos_lucro
            ):
                continue
        resolvidas.append(entrada)

    por_codigo: dict[str, set[str]] = {}
    for entrada in resolvidas:
        por_codigo.setdefault(entrada.cd_conta, set()).add(entrada.conceito)
    conflitos = {
        codigo: sorted(conceitos)
        for codigo, conceitos in por_codigo.items()
        if len(conceitos) > 1
    }
    if conflitos:
        raise ConflitoMapaContasError(
            "o mesmo cd_conta resolveu mais de um conceito na companhia: "
            f"{conflitos}"
        )

    return tuple(
        sorted(resolvidas, key=lambda e: (e.conceito, e.cd_conta))
    )


def assinatura_plano_contas(entradas: Iterable[EntradaMapa]) -> str:
    """Identificador determinístico do plano de contas de uma companhia.

    Duas companhias compartilham plano quando atribuem exatamente os mesmos
    códigos aos mesmos conceitos. O prefixo legível expõe o código do lucro
    consolidado — é o que torna `3.09` × `3.11` visível numa inspeção da tabela
    `mapa_contas` sem precisar decodificar o resumo.
    """
    itens = sorted((e.conceito, e.cd_conta) for e in entradas)
    if not itens:
        return "plano_indefinido"
    codigo_lucro = next(
        (
            cd
            for conceito, cd in itens
            if conceito == CONCEITO_LUCRO_CONSOLIDADO
        ),
        "sem_lucro",
    )
    resumo = hashlib.sha256(
        "|".join(f"{c}={cd}" for c, cd in itens).encode("utf-8")
    ).hexdigest()[:8]
    return f"ll{codigo_lucro.replace('.', '_')}_{resumo}"


# --------------------------------------------------------------------------- #
# Companhias do corpus — seleção por CD_CVM (RN11), nunca por nome
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BancoCorpus:
    """Registro fixo de uma instituição do corpus.

    Filtrar por texto pega companhia errada: `BTG` casa também
    `BTG PACTUAL COMMODITIES SERTRADING S.A.` e `BRASIL` casa
    `BCO MERCANTIL DO BRASIL`, `HIDROVIAS DO BRASIL` e `TELEFÔNICA BRASIL`.
    A seleção é sempre pelo `cd_cvm` desta tabela.
    """

    banco: str
    cd_cvm: str
    cnpj: str
    denom_social: str
    ticker: str
    setor: str


BANCOS_CORPUS: tuple[BancoCorpus, ...] = (
    BancoCorpus("BB", "001023", "00.000.000/0001-91", "BCO BRASIL S.A.", "BBAS3", "Bancos"),
    BancoCorpus("BRADESCO", "000906", "60.746.948/0001-12", "BCO BRADESCO S.A.", "BBDC4", "Bancos"),
    BancoCorpus("BTG", "022616", "30.306.294/0001-45", "BCO BTG PACTUAL S.A.", "BPAC11", "Bancos"),
    BancoCorpus("ITAU", "019348", "60.872.504/0001-23", "ITAU UNIBANCO HOLDING S.A.", "ITUB4", "Bancos"),
    BancoCorpus("SANTANDER", "020532", "90.400.888/0001-42", "BCO SANTANDER (BRASIL) S.A.", "SANB11", "Bancos"),
)

CD_CVM_CORPUS: tuple[str, ...] = tuple(b.cd_cvm for b in BANCOS_CORPUS)
BANCO_POR_CD_CVM: Mapping[str, BancoCorpus] = {b.cd_cvm: b for b in BANCOS_CORPUS}

# Fragmentos que uma seleção ingênua por nome usaria. Servem só para MEDIR
# quantas linhas a regra por `cd_cvm` evitou (armadilha nº 6); nunca para
# selecionar.
FRAGMENTOS_NOME_AMBIGUO: tuple[str, ...] = (
    "BTG",
    "BRASIL",
    "BRADESCO",
    "SANTANDER",
    "ITAU",
)


def normalizar_cd_cvm(bruto: str | int | None) -> str:
    """Padroniza o código para 6 dígitos com zeros à esquerda (`1023` → `001023`)."""
    texto = str(bruto or "").strip()
    if not texto:
        return ""
    if not texto.isdigit():
        raise ValueError(f"cd_cvm não numérico: {bruto!r}")
    return texto.zfill(6)


# --------------------------------------------------------------------------- #
# Gate G4 — conferência manual congelada (pesquisa técnica 2.1 e 2.5)
# --------------------------------------------------------------------------- #

# Códigos conferidos companhia a companhia nos arquivos reais em 2026-08-10.
# O gate G4 compara o mapa resolvido pela carga contra ESTA tabela: se a
# resolução mudar de código sem que alguém atualize a conferência aqui, o gate
# falha em vez de responder um número diferente em silêncio.
#
# Cada conceito aceita um CONJUNTO de códigos porque uma companhia pode publicar
# o mesmo conceito sob códigos diferentes em conjuntos diferentes — ver a nota do
# Santander abaixo. Aceitar um conjunto não afrouxa o gate: `3.09` continua
# inaceitável para o lucro consolidado do BB, do Bradesco e do Itaú.
CONFERENCIA_G4: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "001023": {  # Banco do Brasil — plano 3.11
        CONCEITO_LUCRO_CONSOLIDADO: ("3.11",),
        CONCEITO_LUCRO_CONTROLADORES: ("3.11.01",),
        CONCEITO_LUCRO_NAO_CONTROLADORES: ("3.11.02",),
        CONCEITO_PATRIMONIO_LIQUIDO: ("2.07",),
    },
    "000906": {  # Bradesco — plano 3.11
        CONCEITO_LUCRO_CONSOLIDADO: ("3.11",),
        CONCEITO_LUCRO_CONTROLADORES: ("3.11.01",),
        CONCEITO_LUCRO_NAO_CONTROLADORES: ("3.11.02",),
        CONCEITO_PATRIMONIO_LIQUIDO: ("2.07",),
    },
    "022616": {  # BTG Pactual — plano 3.09
        CONCEITO_LUCRO_CONSOLIDADO: ("3.09",),
        CONCEITO_LUCRO_CONTROLADORES: ("3.09.01",),
        CONCEITO_LUCRO_NAO_CONTROLADORES: ("3.09.02",),
        CONCEITO_PATRIMONIO_LIQUIDO: ("2.08",),
    },
    "019348": {  # Itaú Unibanco — plano 3.09
        CONCEITO_LUCRO_CONSOLIDADO: ("3.09",),
        CONCEITO_LUCRO_CONTROLADORES: ("3.09.01",),
        CONCEITO_LUCRO_NAO_CONTROLADORES: ("3.09.02",),
        CONCEITO_PATRIMONIO_LIQUIDO: ("2.08",),
    },
    # Santander Brasil — ACHADO DE 2026-08-10, medido nos arquivos:
    # o banco usa DOIS planos de contas no mesmo exercício, e a troca vale para
    # a DRE **e** para o balanço.
    #
    #   DRE — no ITR (1T/2T/3T de 2025 e 2026) o lucro consolidado é `3.09`
    #   (*Lucro/Prejuízo Consolidado do Período*); na DFP de 2025 ele passa para
    #   `3.11`, e `3.09` volta a significar *Lucro ou Prejuízo antes das
    #   Participações e Contribuições Estatutárias*.
    #
    #   Balanço — o patrimônio líquido é `2.08` no ITR e `2.07` na DFP de 2025;
    #   e `2.07`, no ITR do mesmo banco, é *Passivos sobre Ativos Não Correntes
    #   a Venda e Descontinuados*.
    #
    # Mesmo código, outro conceito, mesma companhia, mesmo ano. Entre as 470
    # companhias carregadas é a única nessa situação. Ambos os códigos são
    # esperados aqui — e é por isso que a resolução usa a descrição, não o
    # código.
    "020532": {
        CONCEITO_LUCRO_CONSOLIDADO: ("3.09", "3.11"),
        CONCEITO_LUCRO_CONTROLADORES: ("3.09.01", "3.11.01"),
        CONCEITO_LUCRO_NAO_CONTROLADORES: ("3.09.02", "3.11.02"),
        CONCEITO_PATRIMONIO_LIQUIDO: ("2.07", "2.08"),
    },
}
