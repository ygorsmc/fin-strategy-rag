"""Painel contábil da CVM em DuckDB (spec 5.5).

Constrói e consulta o banco analítico local sobre os conjuntos ITR/DFP do portal
de dados abertos da CVM. Três responsabilidades:

1. **Carga com as seis regras de armadilha.** Cada armadilha confirmada nos
   arquivos reais produz número plausível, não nulo e errado, sem erro visível.
   Cada regra tem contagem própria reportada ao final da carga
   (`RelatorioCarga.regras`) — o que não é medido não é auditável.
2. **Camada semântica (RN09).** `cd_conta` não identifica o conceito contábil
   entre companhias; a resolução vem de `src.mapa_contas` sobre `ds_conta`
   normalizada. O consumidor consulta `fatos_semanticos`, nunca
   `fatos_contabeis`.
3. **Guardas de SQL (RN04).** Conexão somente-leitura, lista branca de tabelas,
   bloqueio de DDL/DML por análise sintática *antes* da execução, `LIMIT`
   obrigatório e tempo máximo. Falha de qualquer guarda devolve erro explícito,
   nunca executa.

O 4º trimestre não existe como ITR (RN10): é derivado por DFP anual menos ITR
acumulado do 3T e marcado com `origem='derivado'` — apresentá-lo como número
arquivado pelo regulador seria mentir por omissão.
"""

from __future__ import annotations

import csv
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Collection, Iterable, NamedTuple, Sequence

import duckdb

from src.config import RAIZ_PROJETO, TABELAS_PERMITIDAS_SQL, Config
from src.mapa_contas import (
    BANCO_POR_CD_CVM,
    CD_CVM_CORPUS,
    CONCEITO_ATIVO_TOTAL,
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_LUCRO_NAO_CONTROLADORES,
    CONCEITO_PATRIMONIO_LIQUIDO,
    CONCEITO_RECEITA_INTERMEDIACAO,
    CONCEITOS_DE_FLUXO,
    CONFERENCIA_G4,
    ContaObservada,
    EntradaMapa,
    FRAGMENTOS_NOME_AMBIGUO,
    assinatura_plano_contas,
    resolver_mapa_da_companhia,
)

# --------------------------------------------------------------------------- #
# Erros
# --------------------------------------------------------------------------- #


class ErroCargaCVM(RuntimeError):
    """Falha determinística durante a carga do painel."""


class PainelIndisponivelError(RuntimeError):
    """O arquivo DuckDB não existe — o painel ainda não foi construído."""


class SqlBloqueadoError(ValueError):
    """A consulta violou uma das guardas da RN04 e NÃO foi executada."""


class SqlTempoExcedidoError(RuntimeError):
    """A consulta ultrapassou `SQL_TIMEOUT_S` e foi interrompida."""


# --------------------------------------------------------------------------- #
# Fontes e relatório
# --------------------------------------------------------------------------- #

DEMONSTRATIVOS_SUPORTADOS: frozenset[str] = frozenset(
    {"DRE", "BPA", "BPP", "DFC_MD", "DFC_MI"}
)
CONJUNTOS_SUPORTADOS: frozenset[str] = frozenset({"itr", "dfp"})

#: Demonstrativos de **fluxo** — o valor acumula dentro do exercício, então o 4T
#: não existe como ITR e precisa da derivação da RN10. Saldo de balanço
#: (BPA/BPP) em 31/12 é arquivado, não derivado.
#:
#: A DFC entrou aqui em 2026-08-27 pelo mesmo argumento que já valia para a DRE:
#: a CVM publica o acumulado de nove meses no ITR do 3T e o anual na DFP, e sem
#: a subtração o 4T de caixa simplesmente não existe no painel.
DEMONSTRATIVOS_DE_FLUXO: frozenset[str] = frozenset({"DRE", "DFC_MD", "DFC_MI"})

#: A CVM publica o fluxo de caixa em dois arquivos mutuamente exclusivos por
#: método — direto (MD) e indireto (MI). O indireto domina (465 emissores em
#: 2024 contra 20 do direto), mas a sobreposição **não é vazia**: 9 emissores
#: publicaram os dois em 2024. Somar os dois demonstrativos duplicaria o caixa
#: dessas companhias, então a sobreposição é CONTADA e reportada na carga em
#: vez de suposta ausente.
DEMONSTRATIVOS_DFC: tuple[str, str] = ("DFC_MD", "DFC_MI")

FATORES_ESCALA: dict[str, float] = {
    "MIL": 1_000.0,
    "UNIDADE": 1.0,
    "MILHAO": 1_000_000.0,
}


@dataclass(frozen=True)
class FonteCVM:
    """Um CSV já extraído do ZIP anual, com sua procedência declarada."""

    caminho: Path
    conjunto: str
    demonstrativo: str

    def __post_init__(self) -> None:
        if self.conjunto not in CONJUNTOS_SUPORTADOS:
            raise ValueError(
                f"conjunto desconhecido: {self.conjunto!r}; "
                f"suportados={sorted(CONJUNTOS_SUPORTADOS)}"
            )
        if self.demonstrativo not in DEMONSTRATIVOS_SUPORTADOS:
            raise ValueError(
                f"demonstrativo desconhecido: {self.demonstrativo!r}; "
                f"suportados={sorted(DEMONSTRATIVOS_SUPORTADOS)}"
            )


@dataclass(frozen=True)
class FonteCabecalho:
    """O CSV-cadastro do ZIP (`<conjunto>_cia_aberta_<ano>.csv`).

    Não traz fato contábil nenhum: traz `DT_RECEB`, que é quando o formulário
    chegou à CVM. É a única fonte de data de publicação real no acervo.
    """

    caminho: Path
    conjunto: str

    def __post_init__(self) -> None:
        if self.conjunto not in CONJUNTOS_SUPORTADOS:
            raise ValueError(
                f"conjunto desconhecido: {self.conjunto!r}; "
                f"suportados={sorted(CONJUNTOS_SUPORTADOS)}"
            )


@dataclass(frozen=True)
class RelatorioRegra:
    """Contagem de linhas afetadas por uma regra de armadilha."""

    chave: str
    descricao: str
    linhas_afetadas: int

    def __str__(self) -> str:  # pragma: no cover - formatação
        return f"{self.chave}: {self.linhas_afetadas} linha(s) — {self.descricao}"


@dataclass(frozen=True)
class RelatorioCarga:
    """O que a carga leu, descartou, converteu e derivou."""

    linhas_lidas: int
    linhas_carregadas: int
    companhias: int
    regras: tuple[RelatorioRegra, ...]
    fatos_derivados_4t: int
    conceitos_resolvidos: int
    planos_de_contas: int
    fontes: tuple[str, ...] = ()
    avisos: tuple[str, ...] = field(default=())
    # Fatos em que o próprio arquivo da CVM não fecha: o lucro consolidado
    # difere da soma controladores + não controladores. Não é erro da carga —
    # é defeito da fonte, e fica contado para não virar número silencioso.
    incoerencias_lucro: int = 0
    # Linhas de `documentos` (cadastro com DT_RECEB). Zero significa que nenhum
    # cabeçalho foi passado — o painel funciona, mas NÃO é point-in-time.
    documentos_carregados: int = 0
    # 2T e 3T isolados derivados de acumulado consecutivo (RN10). A CVM publica
    # a DFC só em forma acumulada nesses trimestres; sem isto, fluxo de caixa
    # isolado existe apenas no 1T e no 4T e nenhuma janela TTM se fecha.
    fatos_derivados_intermediarios: int = 0
    # Emissores que publicaram fluxo de caixa pelos DOIS métodos no mesmo
    # trimestre. Somar DFC_MD com DFC_MI duplicaria o caixa deles; o número
    # fica visível para que o consumidor escolha um método, nunca os dois.
    emissores_dfc_ambos_metodos: int = 0

    def regra(self, chave: str) -> RelatorioRegra:
        for regra in self.regras:
            if regra.chave == chave:
                return regra
        raise KeyError(chave)

    def como_texto(self) -> str:
        linhas = [
            f"linhas lidas: {self.linhas_lidas}",
            f"linhas carregadas: {self.linhas_carregadas}",
            f"companhias: {self.companhias} | planos de contas: {self.planos_de_contas}",
            f"conceitos resolvidos (mapa_contas): {self.conceitos_resolvidos}",
            f"fatos derivados do 4T (RN10): {self.fatos_derivados_4t}",
            "fatos derivados do 2T/3T isolado (RN10): "
            f"{self.fatos_derivados_intermediarios}",
            f"fatos com lucro incoerente na fonte: {self.incoerencias_lucro}",
            f"documentos com DT_RECEB (point-in-time): {self.documentos_carregados}",
            "emissores com DFC pelos dois métodos: "
            f"{self.emissores_dfc_ambos_metodos}",
            "regras de armadilha:",
        ]
        linhas.extend(f"  - {regra}" for regra in self.regras)
        linhas.extend(f"  ! {aviso}" for aviso in self.avisos)
        return "\n".join(linhas)


# Descrição de cada armadilha, na ordem da spec 5.5.
DESCRICAO_REGRAS: dict[str, str] = {
    "ordem_exerc_penultimo": (
        "ORDEM_EXERC duplica cada fato em ÚLTIMO/PENÚLTIMO (50/50); as linhas "
        "PENÚLTIMO são o comparativo do ano anterior e foram descartadas"
    ),
    "versao_republicada": (
        "VERSAO chega a 3 por republicação; só a maior versão por companhia × "
        "conjunto × demonstrativo × DT_REFER foi mantida"
    ),
    "escala_moeda_convertida": (
        "ESCALA_MOEDA alterna MIL e UNIDADE no mesmo arquivo; as linhas em MIL "
        "(ou MILHÃO) foram convertidas para reais na carga"
    ),
    "periodo_nao_trimestral": (
        "a partir do 2T convivem acumulado e trimestre isolado; o período foi "
        "escolhido pelo par DT_INI_EXERC/DT_FIM_EXERC e as linhas acumuladas/"
        "anuais ficam fora de fatos_semanticos (mas seguem em fatos_contabeis "
        "para auditoria e para a derivação do 4T)"
    ),
    "trimestre_corrigido": (
        "DT_REFER existe fora do calendário civil (31/05, 31/08); o rótulo do "
        "trimestre foi derivado do intervalo do exercício e divergiu do que o "
        "mês de DT_REFER indicaria nestas linhas"
    ),
    "homonimo_por_nome": (
        "seleção por nome pegaria companhia errada (BTG casa BTG PACTUAL "
        "COMMODITIES SERTRADING; BRASIL casa BCO MERCANTIL DO BRASIL, "
        "HIDROVIAS DO BRASIL, TELEFÔNICA BRASIL); a seleção é por CD_CVM fixado "
        "e estas linhas homônimas não foram atribuídas a nenhum banco do corpus"
    ),
}


# --------------------------------------------------------------------------- #
# Esquema
# --------------------------------------------------------------------------- #

ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS companhias (
    cd_cvm        VARCHAR PRIMARY KEY,
    cnpj          VARCHAR,
    denom_social  VARCHAR NOT NULL,
    setor         VARCHAR,
    ticker        VARCHAR,
    is_banco      BOOLEAN NOT NULL,
    plano_contas  VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fatos_contabeis (
    cd_cvm            VARCHAR NOT NULL REFERENCES companhias(cd_cvm),
    conjunto          VARCHAR NOT NULL,
    demonstrativo     VARCHAR NOT NULL,
    trimestre         VARCHAR NOT NULL,
    tipo_periodo      VARCHAR NOT NULL,
    dt_refer          DATE    NOT NULL,
    dt_ini_exerc      DATE,
    dt_fim_exerc      DATE    NOT NULL,
    cd_conta          VARCHAR NOT NULL,
    ds_conta          VARCHAR NOT NULL,
    ds_conta_norm     VARCHAR NOT NULL,
    vl_conta          DOUBLE  NOT NULL,
    escala            VARCHAR NOT NULL,
    valor_reais       DOUBLE  NOT NULL,
    versao_documento  INTEGER NOT NULL,
    origem            VARCHAR NOT NULL
);

-- Cadastro do DOCUMENTO, não do fato. Existe para tornar backtest
-- *point-in-time* possível: `dt_receb` é a data em que a CVM RECEBEU o
-- formulário, que é quando a informação passou a existir para o mercado.
--
-- Sem esta tabela, qualquer avaliação temporal usa `dt_refer` (o fim do
-- exercício) como se fosse a data de publicação — e o formulário do 1T chega
-- ~40 dias depois do trimestre fechar. Foi a falha que reprovou o gate G1 no
-- CAND-04 e no Rank 5, e ela não depende de qual alvo se escolhe: contamina
-- qualquer um.
--
-- Guarda-se TODA versão, não só a maior: `fatos_contabeis` mantém a última
-- (regra de armadilha `versao_republicada`), mas quem quiser reconstruir o que
-- era conhecido numa data passada precisa saber quando cada versão chegou.
CREATE TABLE IF NOT EXISTS documentos (
    cd_cvm    VARCHAR NOT NULL,
    conjunto  VARCHAR NOT NULL,
    dt_refer  DATE    NOT NULL,
    versao    INTEGER NOT NULL,
    id_doc    VARCHAR NOT NULL,
    dt_receb  DATE    NOT NULL,
    link_doc  VARCHAR,
    PRIMARY KEY (cd_cvm, conjunto, dt_refer, versao)
);

CREATE TABLE IF NOT EXISTS mapa_contas (
    plano_contas       VARCHAR NOT NULL,
    conceito           VARCHAR NOT NULL,
    cd_conta           VARCHAR NOT NULL,
    ds_conta_esperada  VARCHAR NOT NULL,
    ds_conta_norm      VARCHAR NOT NULL,
    PRIMARY KEY (plano_contas, cd_conta, ds_conta_norm)
);

-- Correções com procedência (gate G4). Existe porque o arquivo da CVM pode
-- estar errado, e o painel não pode nem repetir o erro nem consertá-lo em
-- silêncio: `valor_original_reais` PRENDE a correção ao valor exatamente
-- observado quando ela foi revisada. Se a CVM republicar e o valor cru mudar,
-- a correção deixa de casar e a carga FALHA — em vez de aplicar às cegas um
-- ajuste que ninguém revisou contra o dado novo.
CREATE TABLE IF NOT EXISTS correcoes_contabeis (
    cd_cvm                VARCHAR NOT NULL REFERENCES companhias(cd_cvm),
    trimestre             VARCHAR NOT NULL,
    conceito              VARCHAR NOT NULL,
    valor_original_reais  DOUBLE  NOT NULL,
    valor_corrigido_reais DOUBLE  NOT NULL,
    fonte_documento       VARCHAR NOT NULL,
    fonte_pagina          INTEGER NOT NULL,
    fonte_sha256          VARCHAR NOT NULL,
    evidencia             VARCHAR NOT NULL,
    motivo                VARCHAR NOT NULL,
    data_utc              VARCHAR NOT NULL,
    PRIMARY KEY (cd_cvm, trimestre, conceito)
);
"""

# A normalização precisa ser IDÊNTICA à de `src.mapa_contas.normalizar_ds_conta`:
# ela é aplicada em SQL sobre centenas de milhares de linhas e em Python sobre o
# conjunto distinto de contas, e o join entre as duas só fecha se coincidirem.
# `test_normalizacao_sql_equivale_a_python` trava esse contrato.
_SQL_NORMALIZAR_DS_CONTA = (
    "trim(regexp_replace(lower(regexp_replace("
    "strip_accents({coluna}), '[^0-9a-zA-Z]+', ' ', 'g')), '\\s+', ' ', 'g'))"
)

# A visão semântica é a ÚNICA porta de entrada do agente aos fatos: resolve o
# conceito pelo mapa e expõe só o grão companhia × trimestre × conceito.
# `cd_conta` não aparece de propósito — quem consulta não deve poder escolher
# um código de conta (RN09/RN04).
VISAO_FATOS_SEMANTICOS_SQL = """
CREATE OR REPLACE VIEW fatos_semanticos AS
SELECT
    f.cd_cvm            AS cd_cvm,
    c.denom_social      AS denom_social,
    f.trimestre         AS trimestre,
    m.conceito          AS conceito,
    coalesce(k.valor_corrigido_reais, f.valor_reais) AS valor_reais,
    f.valor_reais       AS valor_reais_arquivo,
    (k.cd_cvm IS NOT NULL) AS corrigido,
    k.motivo            AS correcao_motivo,
    k.fonte_documento   AS correcao_fonte,
    k.fonte_pagina      AS correcao_fonte_pagina,
    f.origem            AS origem,
    f.tipo_periodo      AS tipo_periodo,
    f.demonstrativo     AS demonstrativo,
    f.dt_ini_exerc      AS dt_ini_exerc,
    f.dt_fim_exerc      AS dt_fim_exerc,
    f.ds_conta          AS ds_conta
FROM fatos_contabeis AS f
JOIN companhias AS c
  ON c.cd_cvm = f.cd_cvm
JOIN mapa_contas AS m
  ON m.plano_contas = c.plano_contas
 AND m.cd_conta = f.cd_conta
 AND m.ds_conta_norm = f.ds_conta_norm
LEFT JOIN correcoes_contabeis AS k
  ON k.cd_cvm = f.cd_cvm
 AND k.trimestre = f.trimestre
 AND k.conceito = m.conceito
WHERE f.tipo_periodo IN ('trimestral', 'instantaneo');
"""


def criar_esquema(con: duckdb.DuckDBPyConnection) -> None:
    """Cria tabelas e a visão semântica; idempotente."""
    con.execute(ESQUEMA_SQL)
    con.execute(VISAO_FATOS_SEMANTICOS_SQL)


# --------------------------------------------------------------------------- #
# Correções com procedência (gate G4)
# --------------------------------------------------------------------------- #

CAMINHO_CORRECOES = RAIZ_PROJETO / "corpus" / "cvm" / "correcoes_contabeis.csv"

CAMPOS_CORRECAO: tuple[str, ...] = (
    "cd_cvm",
    "trimestre",
    "conceito",
    "valor_original_reais",
    "valor_corrigido_reais",
    "fonte_documento",
    "fonte_pagina",
    "fonte_sha256",
    "evidencia",
    "motivo",
    "data_utc",
)

# Tamanho mínimo de texto livre. Não é burocracia: "erro na origem" não permite
# a ninguém reconferir a correção daqui a seis meses, e a procedência é a
# única coisa que separa correção de ajuste conveniente.
_MIN_EVIDENCIA = 60
_MIN_MOTIVO = 60


class ErroCorrecaoInvalida(ValueError):
    """Correção sem procedência completa, ou que não casa com o dado atual."""


def carregar_correcoes(
    caminho: Path = CAMINHO_CORRECOES,
) -> tuple[dict[str, object], ...]:
    """Lê e valida o CSV de correções — falha fechado em qualquer lacuna.

    **Por que o CSV é a fonte de verdade, e não linhas inseridas na tabela.**
    Uma correção precisa aparecer em `git diff` e ser revisável por outra
    pessoa antes de valer. Inserção direta no DuckDB seria invisível: o banco
    está fora do Git (é regenerável), então uma correção que morasse só nele
    não deixaria rastro nenhum de quem a fez, quando e por quê.
    """
    if not caminho.exists():
        return ()
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    if linhas and set(linhas[0]) != set(CAMPOS_CORRECAO):
        raise ErroCorrecaoInvalida(
            f"Colunas de {caminho.name} divergem do contrato.\n"
            f"  esperado: {sorted(CAMPOS_CORRECAO)}\n"
            f"  obtido:   {sorted(linhas[0])}"
        )
    correcoes: list[dict[str, object]] = []
    vistas: set[tuple[str, str, str]] = set()
    for numero, linha in enumerate(linhas, start=2):
        faltando = [c for c in CAMPOS_CORRECAO if not str(linha.get(c, "")).strip()]
        if faltando:
            raise ErroCorrecaoInvalida(
                f"Linha {numero} de {caminho.name} sem procedência completa: "
                f"campos vazios {faltando}"
            )
        chave = (linha["cd_cvm"], linha["trimestre"], linha["conceito"])
        if chave in vistas:
            raise ErroCorrecaoInvalida(
                f"Linha {numero}: correção duplicada para {chave}"
            )
        vistas.add(chave)
        if len(linha["evidencia"].strip()) < _MIN_EVIDENCIA:
            raise ErroCorrecaoInvalida(
                f"Linha {numero}: `evidencia` precisa demonstrar POR QUE o "
                f"valor do arquivo está errado (mínimo {_MIN_EVIDENCIA} "
                "caracteres); a aritmética que não fecha é o padrão."
            )
        if len(linha["motivo"].strip()) < _MIN_MOTIVO:
            raise ErroCorrecaoInvalida(
                f"Linha {numero}: `motivo` precisa dizer o que foi apurado e o "
                f"que foi descartado (mínimo {_MIN_MOTIVO} caracteres)."
            )
        try:
            original = float(linha["valor_original_reais"])
            corrigido = float(linha["valor_corrigido_reais"])
            pagina = int(linha["fonte_pagina"])
        except ValueError as exc:
            raise ErroCorrecaoInvalida(f"Linha {numero}: {exc}") from exc
        if pagina < 1:
            raise ErroCorrecaoInvalida(f"Linha {numero}: página deve ser 1-based.")
        if original == corrigido:
            raise ErroCorrecaoInvalida(
                f"Linha {numero}: correção que não muda nada é ruído no rastro."
            )
        if len(linha["fonte_sha256"].strip()) != 64:
            raise ErroCorrecaoInvalida(
                f"Linha {numero}: `fonte_sha256` deve ser um SHA-256 completo — "
                "é o que prende a correção ao documento exato que a justifica."
            )
        correcoes.append(
            {
                **{c: linha[c].strip() for c in CAMPOS_CORRECAO},
                "valor_original_reais": original,
                "valor_corrigido_reais": corrigido,
                "fonte_pagina": pagina,
            }
        )
    return tuple(correcoes)


def aplicar_correcoes(
    con: duckdb.DuckDBPyConnection, caminho: Path = CAMINHO_CORRECOES
) -> int:
    """Carrega as correções conferindo cada uma contra o dado atual.

    A conferência do `valor_original_reais` é a guarda que impede a tabela de
    virar porta dos fundos: a correção só entra se o valor que ela diz corrigir
    ainda for exatamente o que está no painel. Republicação da CVM, recarga com
    outro mapa ou mudança de escala fazem a correção parar de casar — e o erro
    é levantado, não engolido.
    """
    correcoes = carregar_correcoes(caminho)
    con.execute("DELETE FROM correcoes_contabeis")
    if not correcoes:
        return 0
    divergencias: list[str] = []
    for correcao in correcoes:
        atual = con.execute(
            """
            SELECT f.valor_reais
            FROM fatos_contabeis AS f
            JOIN companhias AS c ON c.cd_cvm = f.cd_cvm
            JOIN mapa_contas AS m
              ON m.plano_contas = c.plano_contas
             AND m.cd_conta = f.cd_conta
             AND m.ds_conta_norm = f.ds_conta_norm
            WHERE f.cd_cvm = ? AND f.trimestre = ? AND m.conceito = ?
              AND f.tipo_periodo IN ('trimestral', 'instantaneo')
            """,
            [correcao["cd_cvm"], correcao["trimestre"], correcao["conceito"]],
        ).fetchall()
        chave = (
            f"{correcao['cd_cvm']}/{correcao['trimestre']}/"
            f"{correcao['conceito']}"
        )
        if not atual:
            divergencias.append(f"{chave}: nenhuma linha no painel para corrigir")
            continue
        if len(atual) > 1:
            divergencias.append(f"{chave}: {len(atual)} linhas — correção ambígua")
            continue
        observado = float(atual[0][0])
        esperado = float(correcao["valor_original_reais"])
        if abs(observado - esperado) > 0.5:
            divergencias.append(
                f"{chave}: valor_original_reais={esperado:,.0f} não bate com o "
                f"painel atual ({observado:,.0f}). A correção foi revisada "
                "contra outro dado; reconfira antes de reaplicar."
            )
    if divergencias:
        raise ErroCorrecaoInvalida(
            "Correções não puderam ser aplicadas:\n  - "
            + "\n  - ".join(divergencias)
        )
    con.executemany(
        "INSERT INTO correcoes_contabeis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [[correcao[c] for c in CAMPOS_CORRECAO] for correcao in correcoes],
    )
    return len(correcoes)


# --------------------------------------------------------------------------- #
# Carga
# --------------------------------------------------------------------------- #

_COLUNAS_STAGING = (
    "conjunto",
    "demonstrativo",
    "origem_arquivo",
    "cnpj_cia",
    "dt_refer",
    "versao",
    "denom_cia",
    "cd_cvm",
    "moeda",
    "escala_moeda",
    "ordem_exerc",
    "dt_ini_exerc",
    "dt_fim_exerc",
    "cd_conta",
    "ds_conta",
    "vl_conta",
)

_COLUNAS_OBRIGATORIAS_CSV = (
    "CNPJ_CIA",
    "DT_REFER",
    "VERSAO",
    "DENOM_CIA",
    "CD_CVM",
    "MOEDA",
    "ESCALA_MOEDA",
    "ORDEM_EXERC",
    "DT_FIM_EXERC",
    "CD_CONTA",
    "DS_CONTA",
    "VL_CONTA",
)


def _cabecalho_csv(caminho: Path) -> tuple[str, ...]:
    """Lê só o cabeçalho, na codificação real dos arquivos (ISO-8859-1)."""
    with open(caminho, "r", encoding="iso-8859-1") as arquivo:
        primeira = arquivo.readline()
    if not primeira.strip():
        raise ErroCargaCVM(f"arquivo sem cabeçalho: {caminho}")
    return tuple(c.strip().upper() for c in primeira.rstrip("\r\n").split(";"))


def _sql_staging(fonte: FonteCVM) -> str:
    colunas = _cabecalho_csv(fonte.caminho)
    faltantes = [c for c in _COLUNAS_OBRIGATORIAS_CSV if c not in colunas]
    if faltantes:
        raise ErroCargaCVM(
            f"{fonte.caminho.name}: colunas ausentes no cabeçalho: {faltantes}"
        )
    # BPA/BPP não têm DT_INI_EXERC (são saldos instantâneos, não fluxo).
    dt_ini = "DT_INI_EXERC" if "DT_INI_EXERC" in colunas else "NULL"
    return f"""
        INSERT INTO _bruto BY NAME
        SELECT
            ? AS conjunto,
            ? AS demonstrativo,
            ? AS origem_arquivo,
            CNPJ_CIA AS cnpj_cia,
            DT_REFER AS dt_refer,
            VERSAO AS versao,
            DENOM_CIA AS denom_cia,
            CD_CVM AS cd_cvm,
            MOEDA AS moeda,
            ESCALA_MOEDA AS escala_moeda,
            ORDEM_EXERC AS ordem_exerc,
            {dt_ini} AS dt_ini_exerc,
            DT_FIM_EXERC AS dt_fim_exerc,
            CD_CONTA AS cd_conta,
            DS_CONTA AS ds_conta,
            VL_CONTA AS vl_conta
        FROM read_csv(
            ?,
            delim = ';',
            header = true,
            encoding = 'latin-1',
            all_varchar = true
        )
    """


def _contar(con: duckdb.DuckDBPyConnection, tabela: str) -> int:
    return int(con.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0])


def _resolver_mapa_e_companhias(
    con: duckdb.DuckDBPyConnection,
) -> tuple[list[tuple[Any, ...]], list[tuple[str, ...]], int]:
    """Resolve o mapa semântico companhia a companhia sobre `_limpo`.

    Devolve as linhas de `companhias`, as de `mapa_contas` e a quantidade de
    planos de contas distintos. A resolução é feita em Python porque depende das
    regras de `src.mapa_contas` (descrição normalizada + guarda estrutural de
    subconta), não de casamento de código.
    """
    observadas = con.execute(
        """
        SELECT cd_cvm, cd_conta, ds_conta_norm, max(ds_conta) AS ds_conta
        FROM _limpo
        GROUP BY cd_cvm, cd_conta, ds_conta_norm
        ORDER BY cd_cvm, cd_conta, ds_conta_norm
        """
    ).fetchall()
    identificacao = con.execute(
        """
        SELECT cd_cvm,
               max(cnpj_cia)  AS cnpj,
               max(denom_cia) AS denom_social
        FROM _limpo
        GROUP BY cd_cvm
        ORDER BY cd_cvm
        """
    ).fetchall()

    contas_por_companhia: dict[str, list[ContaObservada]] = {}
    for cd_cvm, cd_conta, _ds_norm, ds_conta in observadas:
        contas_por_companhia.setdefault(cd_cvm, []).append(
            ContaObservada(cd_conta=cd_conta, ds_conta=ds_conta)
        )

    mapa_por_plano: dict[str, dict[tuple[str, str, str], EntradaMapa]] = {}
    linhas_companhias: list[tuple[Any, ...]] = []
    for cd_cvm, cnpj, denom_social in identificacao:
        entradas = resolver_mapa_da_companhia(contas_por_companhia.get(cd_cvm, ()))
        plano = assinatura_plano_contas(entradas)
        destino = mapa_por_plano.setdefault(plano, {})
        for entrada in entradas:
            destino[
                (entrada.conceito, entrada.cd_conta, entrada.ds_conta_normalizada)
            ] = entrada
        banco = BANCO_POR_CD_CVM.get(cd_cvm)
        # `is_banco` significa "usa plano de contas de instituição financeira":
        # é derivado do próprio dado (a companhia publica Receitas de
        # Intermediação Financeira), não de uma lista de nomes.
        usa_plano_financeiro = any(
            e.conceito == CONCEITO_RECEITA_INTERMEDIACAO for e in entradas
        )
        linhas_companhias.append(
            (
                cd_cvm,
                banco.cnpj if banco else cnpj,
                banco.denom_social if banco else denom_social,
                banco.setor if banco else None,
                banco.ticker if banco else None,
                bool(banco) or usa_plano_financeiro,
                plano,
            )
        )

    linhas_mapa: list[tuple[str, ...]] = []
    for plano, entradas in sorted(mapa_por_plano.items()):
        for entrada in sorted(
            entradas.values(), key=lambda e: (e.conceito, e.cd_conta)
        ):
            linhas_mapa.append(
                (
                    plano,
                    entrada.conceito,
                    entrada.cd_conta,
                    entrada.ds_conta_esperada,
                    entrada.ds_conta_normalizada,
                )
            )
    return linhas_companhias, linhas_mapa, len(mapa_por_plano)


def _carregar_documentos(
    con: duckdb.DuckDBPyConnection,
    cabecalhos: Sequence[FonteCabecalho],
) -> int:
    """Carrega o cadastro de documentos (`DT_RECEB`) — a chave point-in-time.

    Falha fechado se um cabeçalho não tiver `DT_RECEB`: um painel que se diz
    point-in-time e não é seria pior que nenhum, porque o defeito ficaria
    invisível dentro de qualquer backtest construído em cima.

    Mantém TODA versão do formulário, não só a maior. `fatos_contabeis` guarda
    a última (regra `versao_republicada`); aqui a série completa é o que
    permite responder "o que se sabia em D?" — inclusive que a versão vigente
    naquela data foi depois substituída.
    """
    for cabecalho in cabecalhos:
        colunas = _cabecalho_csv(cabecalho.caminho)
        faltantes = [c for c in ("CD_CVM", "DT_REFER", "VERSAO", "DT_RECEB")
                     if c not in colunas]
        if faltantes:
            raise ErroCargaCVM(
                f"{cabecalho.caminho.name}: cabeçalho sem {faltantes}; sem "
                "DT_RECEB o painel não é point-in-time e a carga falha em vez "
                "de gravar um painel que promete o que não tem"
            )
        tem_id = "ID_DOC" in colunas
        tem_link = "LINK_DOC" in colunas
        con.execute(
            f"""
            INSERT INTO documentos BY NAME
            SELECT DISTINCT
                trim(CD_CVM)                       AS cd_cvm,
                ?                                  AS conjunto,
                try_cast(DT_REFER AS DATE)         AS dt_refer,
                try_cast(VERSAO AS INTEGER)        AS versao,
                {"trim(ID_DOC)" if tem_id else "''"} AS id_doc,
                try_cast(DT_RECEB AS DATE)         AS dt_receb,
                {"LINK_DOC" if tem_link else "NULL"} AS link_doc
            FROM read_csv(
                ?, delim = ';', header = true,
                encoding = 'latin-1', all_varchar = true
            )
            WHERE try_cast(DT_RECEB AS DATE) IS NOT NULL
              AND try_cast(DT_REFER AS DATE) IS NOT NULL
              AND try_cast(VERSAO AS INTEGER) IS NOT NULL
            ON CONFLICT DO NOTHING
            """,
            [cabecalho.conjunto, str(cabecalho.caminho)],
        )
    return _contar(con, "documentos")


def _contar_dfc_ambos_metodos(con: duckdb.DuckDBPyConnection) -> int:
    """Emissores que publicaram fluxo de caixa pelos DOIS métodos.

    Somar `DFC_MD` com `DFC_MI` duplicaria o caixa dessas companhias. O número
    é reportado em vez de suposto zero porque ele **não é** zero: medido em
    2026-08-27, 9 emissores publicaram os dois em 2024.
    """
    linha = con.execute(
        """
        SELECT count(*) FROM (
            SELECT cd_cvm, trimestre
            FROM fatos_contabeis
            WHERE demonstrativo IN ('DFC_MD', 'DFC_MI')
            GROUP BY 1, 2
            HAVING count(DISTINCT demonstrativo) > 1
        )
        """
    ).fetchone()
    return int(linha[0]) if linha else 0


def carregar_painel(
    fontes: Sequence[FonteCVM],
    destino: Path,
    *,
    cd_cvm_permitidos: Collection[str] | None = None,
    cabecalhos: Sequence[FonteCabecalho] = (),
) -> RelatorioCarga:
    """Constrói o painel DuckDB a partir dos CSVs da CVM já extraídos.

    A carga é transacional: ou o banco fica completo e consistente, ou nada é
    gravado. `cd_cvm_permitidos` restringe as companhias carregadas (RN11 —
    seleção por código, nunca por nome); `None` carrega todas as companhias
    abertas do período, que é o que dá volume amostral ao modelo preditivo.

    `cabecalhos` alimenta a tabela `documentos` com `DT_RECEB`. É opcional para
    não quebrar chamador antigo, mas **sem ele o painel não é point-in-time** —
    e `RelatorioCarga.documentos_carregados` sai zero justamente para que a
    ausência seja legível em vez de silenciosa.
    """
    if not fontes:
        raise ErroCargaCVM("nenhuma fonte informada")
    for fonte in fontes:
        if not fonte.caminho.is_file():
            raise ErroCargaCVM(f"fonte inexistente: {fonte.caminho}")

    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        destino.unlink()

    avisos: list[str] = []
    con = duckdb.connect(str(destino))
    try:
        con.execute(
            "CREATE TEMP TABLE _bruto ("
            + ", ".join(f"{coluna} VARCHAR" for coluna in _COLUNAS_STAGING)
            + ")"
        )
        for fonte in fontes:
            con.execute(
                _sql_staging(fonte),
                [
                    fonte.conjunto,
                    fonte.demonstrativo,
                    fonte.caminho.name,
                    str(fonte.caminho),
                ],
            )
        linhas_lidas = _contar(con, "_bruto")
        if linhas_lidas == 0:
            raise ErroCargaCVM("as fontes informadas não produziram nenhuma linha")

        escalas = {
            (linha[0] or "").strip().upper()
            for linha in con.execute(
                "SELECT DISTINCT upper(strip_accents(trim(escala_moeda))) FROM _bruto"
            ).fetchall()
        }
        desconhecidas = sorted(escalas - set(FATORES_ESCALA))
        if desconhecidas:
            raise ErroCargaCVM(
                "ESCALA_MOEDA desconhecida nos arquivos: "
                f"{desconhecidas}; conhecidas={sorted(FATORES_ESCALA)}. "
                "Converter às cegas somaria grandezas com fator de mil entre si."
            )

        # --- Armadilha 2: ORDEM_EXERC (ÚLTIMO × PENÚLTIMO) --------------------
        con.execute(
            """
            CREATE TEMP TABLE _e1 AS
            SELECT * REPLACE (
                lpad(regexp_replace(trim(cd_cvm), '[^0-9]', '', 'g'), 6, '0')
                    AS cd_cvm
            )
            FROM _bruto
            WHERE upper(strip_accents(trim(ordem_exerc))) = 'ULTIMO'
              AND upper(strip_accents(trim(moeda))) = 'REAL'
              AND regexp_matches(trim(cd_cvm), '^[0-9]+$')
              AND TRY_CAST(vl_conta AS DOUBLE) IS NOT NULL
              AND TRY_CAST(dt_refer AS DATE) IS NOT NULL
              AND TRY_CAST(dt_fim_exerc AS DATE) IS NOT NULL
              AND TRY_CAST(versao AS INTEGER) IS NOT NULL
              AND nullif(trim(cd_conta), '') IS NOT NULL
            """
        )
        descartadas_penultimo = int(
            con.execute(
                "SELECT count(*) FROM _bruto "
                "WHERE upper(strip_accents(trim(ordem_exerc))) <> 'ULTIMO'"
            ).fetchone()[0]
        )
        descartadas_invalidas = linhas_lidas - descartadas_penultimo - _contar(con, "_e1")
        if descartadas_invalidas:
            avisos.append(
                f"{descartadas_invalidas} linha(s) descartada(s) por campo "
                "obrigatório ausente/inválido (valor, data, versão, moeda ou "
                "CD_CVM não numérico)"
            )

        # --- Armadilha 1: VERSAO (republicação) -------------------------------
        con.execute(
            """
            CREATE TEMP TABLE _e2 AS
            SELECT * EXCLUDE (versao_max)
            FROM (
                SELECT *,
                       max(TRY_CAST(versao AS INTEGER)) OVER (
                           PARTITION BY cd_cvm, conjunto, demonstrativo, dt_refer
                       ) AS versao_max
                FROM _e1
            )
            WHERE TRY_CAST(versao AS INTEGER) = versao_max
            """
        )
        descartadas_versao = _contar(con, "_e1") - _contar(con, "_e2")

        # Mesma versão, mesmo fato, arquivos diferentes: dedupe determinístico.
        con.execute(
            """
            CREATE TEMP TABLE _e3 AS
            SELECT * EXCLUDE (origem_arquivo)
            FROM _e2
            QUALIFY row_number() OVER (
                PARTITION BY cd_cvm, demonstrativo, dt_refer, cd_conta,
                             dt_ini_exerc, dt_fim_exerc
                ORDER BY TRY_CAST(versao AS INTEGER) DESC, conjunto, origem_arquivo
            ) = 1
            """
        )
        duplicadas = _contar(con, "_e2") - _contar(con, "_e3")
        if duplicadas:
            avisos.append(
                f"{duplicadas} linha(s) idêntica(s) entre arquivos removida(s) "
                "na deduplicação"
            )

        # --- Armadilhas 3, 4 e 5: escala, período e rótulo do trimestre -------
        con.execute(
            """
            CREATE TEMP TABLE _e4 AS
            WITH tipado AS (
                SELECT
                    conjunto, demonstrativo, cnpj_cia, denom_cia, cd_cvm,
                    cd_conta,
                    -- Defeito de origem, medido em 2026-08-27: 4 linhas do
                    -- `itr_cia_aberta_DFC_MI_con_2014.csv` têm DS_CONTA vazio.
                    -- São conta LIVRE (`ST_CONTA_FIXA=N`) de um emissor que
                    -- criou a linha e não a nomeou, todas com valor 0,0.
                    -- Descartar em silêncio esconderia dado da fonte; deixar
                    -- nulo quebra a carga. O marcador preserva a linha para
                    -- auditoria e, por não casar com `mapa_contas`, NUNCA
                    -- resolve conceito — que é o comportamento certo pela RN09.
                    coalesce(
                        nullif(trim(ds_conta), ''), '(sem descrição na fonte)'
                    ) AS ds_conta,
                    upper(strip_accents(trim(escala_moeda))) AS escala,
                    CAST(dt_refer AS DATE)      AS dt_refer,
                    TRY_CAST(dt_ini_exerc AS DATE) AS dt_ini_exerc,
                    CAST(dt_fim_exerc AS DATE)  AS dt_fim_exerc,
                    CAST(vl_conta AS DOUBLE)    AS vl_conta,
                    CAST(versao AS INTEGER)     AS versao_documento
                FROM _e3
            ),
            com_exercicio AS (
                SELECT *,
                       min(dt_ini_exerc) OVER (
                           PARTITION BY cd_cvm, dt_refer
                       ) AS inicio_exercicio
                FROM tipado
            ),
            derivado AS (
                SELECT *,
                       CASE
                           WHEN dt_ini_exerc IS NULL THEN NULL
                           ELSE datediff(
                               'month', dt_ini_exerc, dt_fim_exerc + INTERVAL 1 DAY
                           )
                       END AS meses_periodo,
                       CASE
                           WHEN inicio_exercicio IS NOT NULL THEN CAST(ceil(
                               datediff(
                                   'month',
                                   inicio_exercicio,
                                   dt_fim_exerc + INTERVAL 1 DAY
                               ) / 3.0
                           ) AS INTEGER)
                           ELSE CAST(ceil(month(dt_fim_exerc) / 3.0) AS INTEGER)
                       END AS ordinal_trimestre,
                       CASE
                           WHEN inicio_exercicio IS NOT NULL
                               THEN year(
                                   inicio_exercicio
                                   + INTERVAL 1 YEAR - INTERVAL 1 DAY
                               )
                           ELSE year(dt_fim_exerc)
                       END AS ano_exercicio
                FROM com_exercicio
            )
            SELECT
                conjunto, demonstrativo, cnpj_cia, denom_cia, cd_cvm,
                cd_conta, ds_conta,
                """
            + _SQL_NORMALIZAR_DS_CONTA.format(coluna="ds_conta")
            + """ AS ds_conta_norm,
                escala, dt_refer, dt_ini_exerc,
                dt_fim_exerc, vl_conta, versao_documento, meses_periodo,
                ordinal_trimestre, ano_exercicio,
                vl_conta * CASE escala
                    WHEN 'MIL' THEN 1000.0
                    WHEN 'MILHAO' THEN 1000000.0
                    ELSE 1.0
                END AS valor_reais,
                CASE
                    WHEN dt_ini_exerc IS NULL THEN 'instantaneo'
                    WHEN meses_periodo <= 3 THEN 'trimestral'
                    WHEN meses_periodo = 12 THEN 'anual'
                    ELSE 'acumulado'
                END AS tipo_periodo,
                CAST(ordinal_trimestre AS VARCHAR) || 'T'
                    || CAST(ano_exercicio AS VARCHAR) AS trimestre,
                CAST(CAST(ceil(month(dt_refer) / 3.0) AS INTEGER) AS VARCHAR)
                    || 'T' || CAST(year(dt_refer) AS VARCHAR) AS trimestre_por_dt_refer
            FROM derivado
            """
        )
        inconsistentes = int(
            con.execute(
                """
                SELECT count(*) FROM _e4
                WHERE ordinal_trimestre IS NULL
                   OR ordinal_trimestre < 1
                   OR ordinal_trimestre > 4
                   OR (meses_periodo IS NOT NULL AND meses_periodo <= 0)
                """
            ).fetchone()[0]
        )
        if inconsistentes:
            avisos.append(
                f"{inconsistentes} linha(s) com intervalo de exercício "
                "inconsistente descartada(s) — trimestre não derivável"
            )
        con.execute(
            """
            CREATE TEMP TABLE _e5 AS
            SELECT * FROM _e4
            WHERE ordinal_trimestre BETWEEN 1 AND 4
              AND (meses_periodo IS NULL OR meses_periodo > 0)
            """
        )
        convertidas_escala = int(
            con.execute(
                "SELECT count(*) FROM _e5 WHERE escala <> 'UNIDADE'"
            ).fetchone()[0]
        )
        periodo_nao_trimestral = int(
            con.execute(
                "SELECT count(*) FROM _e5 WHERE tipo_periodo IN ('acumulado', 'anual')"
            ).fetchone()[0]
        )
        trimestre_corrigido = int(
            con.execute(
                "SELECT count(*) FROM _e5 WHERE trimestre <> trimestre_por_dt_refer"
            ).fetchone()[0]
        )
        dt_refer_fora_calendario = int(
            con.execute(
                "SELECT count(*) FROM _e5 WHERE month(dt_refer) NOT IN (3, 6, 9, 12)"
            ).fetchone()[0]
        )
        if dt_refer_fora_calendario:
            avisos.append(
                f"{dt_refer_fora_calendario} linha(s) com DT_REFER fora do "
                "calendário civil (exercício social deslocado)"
            )

        # --- Armadilha 6: seleção de companhia --------------------------------
        padrao_nome = "|".join(FRAGMENTOS_NOME_AMBIGUO)
        homonimos = con.execute(
            f"""
            SELECT count(*), count(DISTINCT cd_cvm)
            FROM _e5
            WHERE cd_cvm NOT IN ({','.join('?' * len(CD_CVM_CORPUS))})
              AND regexp_matches(upper(strip_accents(denom_cia)), '{padrao_nome}')
            """,
            list(CD_CVM_CORPUS),
        ).fetchone()
        linhas_homonimas, companhias_homonimas = int(homonimos[0]), int(homonimos[1])
        if companhias_homonimas:
            avisos.append(
                f"{companhias_homonimas} companhia(s) homônima(s) NÃO atribuída(s) "
                "a nenhum banco do corpus (seleção por CD_CVM, RN11)"
            )

        if cd_cvm_permitidos is None:
            con.execute("CREATE TEMP TABLE _limpo AS SELECT * FROM _e5")
        else:
            permitidos = sorted({str(c) for c in cd_cvm_permitidos})
            if not permitidos:
                raise ErroCargaCVM("cd_cvm_permitidos vazio")
            con.execute(
                "CREATE TEMP TABLE _limpo AS SELECT * FROM _e5 "
                f"WHERE cd_cvm IN ({','.join('?' * len(permitidos))})",
                permitidos,
            )
            if _contar(con, "_limpo") == 0:
                raise ErroCargaCVM(
                    "nenhuma linha sobrou para os cd_cvm informados: " f"{permitidos}"
                )

        # --- Camada semântica + gravação --------------------------------------
        criar_esquema(con)
        linhas_companhias, linhas_mapa, planos = _resolver_mapa_e_companhias(con)
        con.execute("BEGIN TRANSACTION")
        con.executemany(
            "INSERT INTO companhias VALUES (?, ?, ?, ?, ?, ?, ?)", linhas_companhias
        )
        con.executemany("INSERT INTO mapa_contas VALUES (?, ?, ?, ?, ?)", linhas_mapa)
        con.execute(
            """
            INSERT INTO fatos_contabeis
            SELECT cd_cvm, conjunto, demonstrativo, trimestre, tipo_periodo,
                   dt_refer, dt_ini_exerc, dt_fim_exerc, cd_conta, ds_conta,
                   ds_conta_norm, vl_conta, escala, valor_reais,
                   versao_documento, 'arquivado' AS origem
            FROM _limpo
            """
        )
        derivacao_intermediaria = _derivar_trimestres_intermediarios(con)
        derivados = _derivar_quarto_trimestre(con)
        _materializar_indicadores(con)
        incoerencias = _contar_incoerencias_do_lucro(con)
        documentos = _carregar_documentos(con, cabecalhos)
        dfc_ambos = _contar_dfc_ambos_metodos(con)
        con.execute("COMMIT")
        if not cabecalhos:
            avisos.append(
                "nenhum cabeçalho informado: a tabela `documentos` está vazia "
                "e este painel NÃO é point-in-time — `dt_refer` é fim de "
                "exercício, não data de publicação"
            )
        if derivacao_intermediaria.recusados:
            # Contrato D1.2. Sem este aviso a correção seria silenciosa.
            avisos.append(
                f"{derivacao_intermediaria.recusados} derivação(ões) de trimestre "
                "intermediário RECUSADAS por cobrirem mais de um trimestre "
                "(falta o acumulado imediatamente anterior): o isolado NÃO "
                "existe para esses períodos, em vez de existir errado"
            )
        if derivacao_intermediaria.sem_antecedente:
            # Contrato D2.2: causa DISTINTA da recusa pela banda, aviso próprio.
            avisos.append(
                f"{derivacao_intermediaria.sem_antecedente} trimestre(s) "
                "intermediário(s) SEM ANTECEDENTE: há o acumulado, mas nenhum "
                "acumulado anterior do mesmo exercício com o mesmo conceito (ou, "
                "sem conceito, o mesmo código E descrição) — não há aritmética "
                "possível, e o isolado NÃO existe"
            )
        if dfc_ambos:
            avisos.append(
                f"{dfc_ambos} companhia–trimestre(s) com fluxo de caixa pelos "
                "DOIS métodos (DFC_MD e DFC_MI); somar os dois duplica o caixa "
                "— escolha um método ao consultar"
            )
        if incoerencias:
            avisos.append(
                f"{incoerencias} fato(s) em que o lucro consolidado NÃO é a soma "
                "de controladores + não controladores: a incoerência está no "
                "arquivo da CVM, não na carga"
            )

        linhas_carregadas = _contar(con, "fatos_contabeis")
        companhias = _contar(con, "companhias")
        conceitos = int(
            con.execute("SELECT count(*) FROM mapa_contas").fetchone()[0]
        )
    except Exception:
        con.close()
        destino.unlink(missing_ok=True)
        raise
    else:
        con.close()

    regras = (
        RelatorioRegra(
            "ordem_exerc_penultimo",
            DESCRICAO_REGRAS["ordem_exerc_penultimo"],
            descartadas_penultimo,
        ),
        RelatorioRegra(
            "versao_republicada",
            DESCRICAO_REGRAS["versao_republicada"],
            descartadas_versao,
        ),
        RelatorioRegra(
            "escala_moeda_convertida",
            DESCRICAO_REGRAS["escala_moeda_convertida"],
            convertidas_escala,
        ),
        RelatorioRegra(
            "periodo_nao_trimestral",
            DESCRICAO_REGRAS["periodo_nao_trimestral"],
            periodo_nao_trimestral,
        ),
        RelatorioRegra(
            "trimestre_corrigido",
            DESCRICAO_REGRAS["trimestre_corrigido"],
            trimestre_corrigido,
        ),
        RelatorioRegra(
            "homonimo_por_nome",
            DESCRICAO_REGRAS["homonimo_por_nome"],
            linhas_homonimas,
        ),
    )
    return RelatorioCarga(
        linhas_lidas=linhas_lidas,
        linhas_carregadas=linhas_carregadas,
        companhias=companhias,
        regras=regras,
        fatos_derivados_4t=derivados,
        conceitos_resolvidos=conceitos,
        planos_de_contas=planos,
        fontes=tuple(f.caminho.name for f in fontes),
        avisos=tuple(avisos),
        incoerencias_lucro=incoerencias,
        documentos_carregados=documentos,
        emissores_dfc_ambos_metodos=dfc_ambos,
        fatos_derivados_intermediarios=derivacao_intermediaria.criados,
    )


#: Um trimestre fiscal dura ~91 dias. A banda existe porque exercício de 13
#: semanas desloca o fim do período em poucos dias, e `date_diff('month', …)`
#: contaria 2 meses entre 29/03 e 28/06 — recusando derivação legítima.
#:
#: **A banda separa o que foi medido em 2026-09-12:** os 7.734 derivados
#: anômalos (182, 183, 184 e 273 dias) caem fora, e os 701.357 derivados em
#: disco dentro dela. Nenhum caso ambíguo foi observado. **Ressalva de
#: 2026-09-15:** os 701.357 são TODOS os derivados trimestrais do painel,
#: inclusive 319.049 do 4T, que outra função produz — não provam que a função
#: corrigida preserva cada derivado legítimo, só que a banda não os cortaria.
DIAS_MINIMOS_DE_UM_TRIMESTRE = 80
DIAS_MAXIMOS_DE_UM_TRIMESTRE = 100


class ResultadoDaDerivacao(NamedTuple):
    """Contrato D2.3: três estados, nunca somados."""

    criados: int
    recusados: int
    sem_antecedente: int


def _derivar_trimestres_intermediarios(
    con: duckdb.DuckDBPyConnection,
) -> ResultadoDaDerivacao:
    """Deriva 2T e 3T isolados de demonstrativo de fluxo (RN10).

    **Achado de 2026-08-27, e é o motivo de esta função existir:** a CVM publica
    a DRE do 2T e do 3T em DUAS formas — acumulada e isolada — mas a **DFC só
    em acumulada**. Medido: `6.01` tem 5.767 linhas de 2T e 5.603 de 3T, todas
    `acumulado`, e **zero** isoladas; a DRE, no mesmo recorte, tem 5.747 e
    5.582 isoladas.

    Sem esta derivação o fluxo de caixa isolado só existe no 1T (que a CVM
    publica como 3 meses) e no 4T (derivado por `_derivar_quarto_trimestre`).
    Dois trimestres por ano **nunca formam janela móvel de quatro**, e qualquer
    métrica TTM de caixa — conversão, FCF, qualidade do lucro — fica impossível.

    A aritmética é a mesma da RN10, dentro do próprio ITR:

        isolado(q) = acumulado(q) − acumulado(q−1)

    onde `acumulado(1T)` é a linha de três meses que a CVM já publica como
    `trimestral`. O período anterior é o de **mesmo início de exercício** com o
    maior `dt_fim_exerc` estritamente menor — nunca "a linha de cima", que
    casaria exercícios diferentes.

    Não toca a DFP anual: aquela subtração é o 4T e tem função própria. Aqui só
    entra `acumulado`, então as duas não se sobrepõem.

    **Correção de 2026-09-12 (contrato D1): só deriva trimestre quem cobre um
    trimestre.** O `lag` pareia o período anterior *disponível*, e faltando um
    acumulado intermediário a diferença cobria mais de um trimestre — saindo
    rotulada `trimestral`. Medido no painel inteiro: **7.734 linhas** em 513
    companhias e 111 contas, com 182, 183, 184 ou 273 dias (507 companhias é só
    o grupo de 183 dias — corrigido em 2026-09-15). Exemplo:
    `025887/3T2024` = 19.289.000 (jan–set) − 1.992.000 (jan–mar) =
    **17.297.000 de abr–set**, publicado como trimestre isolado.

    A promessa antiga desta docstring — *"o de mesmo início de exercício com o
    maior `dt_fim_exerc` estritamente menor"* — era verdadeira e **insuficiente**:
    nada garantia que esse período fosse o trimestre anterior.

    Devolve `(criados, recusados, sem_antecedente)`. A recusa é **contada e
    reportada em aviso**, nunca silenciosa: painel que perde linha sem sinal é o
    defeito que o §3.15 descreve como *"pior que sumir com erro"*.

    **Correção de 2026-09-15 (contrato D2, conferência QW6): uma relação só.**
    A contagem de recusas usava `coalesce(conceito, cd_conta)` e a inserção
    `coalesce(conceito, cd_conta|descrição)` — identidades diferentes. Com a
    mesma conta no 1T e no 3T e outra descrição no 2T, a recusa acontecia e
    **não era contada** (e o aviso não saía). Agora candidatos, inserção e
    contagens saem da MESMA tabela, e a contagem é por grupo
    `(companhia, demonstrativo, trimestre, chave)` — a unidade do `QUALIFY`.

    **Antecedente inexistente é estado próprio** (`sem_antecedente`), contado
    à parte: não há aritmética possível, que é causa diferente de a aritmética
    cobrir mais de um trimestre. Medido sobre os arquivados do painel de treino:
    ~140 mil grupos — boa parte porque a descrição normalizada muda entre
    arquivamentos e parte a partição. Curar essa deriva muda a identidade de
    pareamento (RN09) e todos os consumidores: contrato próprio, não feito.
    """
    antes = _contar(con, "fatos_contabeis")
    fluxo = ", ".join(f"'{d}'" for d in sorted(DEMONSTRATIVOS_DE_FLUXO))
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _candidatos_intermediarios AS
        WITH resolvido AS (
            SELECT
                f.*,
                coalesce(
                    m.conceito,
                    'conta:' || f.cd_conta || '|' || f.ds_conta_norm
                ) AS chave_pareamento
            FROM fatos_contabeis AS f
            JOIN companhias AS c ON c.cd_cvm = f.cd_cvm
            LEFT JOIN mapa_contas AS m
              ON m.plano_contas = c.plano_contas
             AND m.cd_conta = f.cd_conta
             AND m.ds_conta_norm = f.ds_conta_norm
            WHERE f.demonstrativo IN ({fluxo})
              AND f.tipo_periodo IN ('acumulado', 'trimestral')
              AND f.dt_ini_exerc IS NOT NULL
        ),
        com_anterior AS (
            SELECT
                a.*,
                lag(a.valor_reais) OVER janela  AS valor_anterior,
                lag(a.dt_fim_exerc) OVER janela AS fim_anterior
            FROM resolvido AS a
            WINDOW janela AS (
                PARTITION BY a.cd_cvm, a.demonstrativo,
                             a.chave_pareamento, a.dt_ini_exerc
                ORDER BY a.dt_fim_exerc
            )
        )
        SELECT
            a.*,
            (a.fim_anterior IS NOT NULL AND a.valor_anterior IS NOT NULL)
                AS tem_antecedente,
            -- Contrato D1.1: o período derivado tem de durar um trimestre.
            (a.fim_anterior IS NOT NULL AND a.valor_anterior IS NOT NULL
             AND (a.dt_fim_exerc - a.fim_anterior)
                 BETWEEN {DIAS_MINIMOS_DE_UM_TRIMESTRE}
                     AND {DIAS_MAXIMOS_DE_UM_TRIMESTRE})
                AS na_banda
        FROM com_anterior AS a
        WHERE a.tipo_periodo = 'acumulado'
          AND NOT EXISTS (
              SELECT 1 FROM fatos_contabeis AS ja
              WHERE ja.cd_cvm = a.cd_cvm
                AND ja.demonstrativo = a.demonstrativo
                AND ja.cd_conta = a.cd_conta
                AND ja.ds_conta_norm = a.ds_conta_norm
                AND ja.trimestre = a.trimestre
                AND ja.tipo_periodo = 'trimestral'
          )
        """
    )
    derivaveis, recusados, sem_antecedente = con.execute(
        """
        SELECT count(*) FILTER (WHERE na_banda),
               count(*) FILTER (WHERE tem_antecedente AND NOT na_banda),
               count(*) FILTER (WHERE NOT tem_antecedente)
        FROM (
            SELECT bool_or(tem_antecedente) AS tem_antecedente,
                   bool_or(na_banda)        AS na_banda
            FROM _candidatos_intermediarios
            GROUP BY cd_cvm, demonstrativo, trimestre, chave_pareamento
        )
        """
    ).fetchone()
    con.execute(
        """
        INSERT INTO fatos_contabeis
        SELECT
            a.cd_cvm,
            a.conjunto,
            a.demonstrativo,
            a.trimestre,
            'trimestral' AS tipo_periodo,
            a.dt_refer,
            a.fim_anterior + INTERVAL 1 DAY AS dt_ini_exerc,
            a.dt_fim_exerc,
            a.cd_conta,
            a.ds_conta,
            a.ds_conta_norm,
            a.valor_reais - a.valor_anterior AS vl_conta,
            'UNIDADE' AS escala,
            a.valor_reais - a.valor_anterior AS valor_reais,
            a.versao_documento,
            'derivado' AS origem
        FROM _candidatos_intermediarios AS a
        WHERE a.na_banda
        QUALIFY row_number() OVER (
            PARTITION BY a.cd_cvm, a.demonstrativo, a.trimestre,
                         a.chave_pareamento
            ORDER BY a.cd_conta
        ) = 1
        """
    )
    con.execute("DROP TABLE _candidatos_intermediarios")
    criados = _contar(con, "fatos_contabeis") - antes
    if criados != derivaveis:
        # Inserção e contagem saem da mesma relação; divergirem é defeito deste
        # código, e painel com contagem errada é pior que carga que falha.
        raise ErroCargaCVM(
            f"derivação intermediária inseriu {criados} linhas, mas a relação de "
            f"candidatos tem {derivaveis} grupos deriváveis"
        )
    return ResultadoDaDerivacao(criados, recusados, sem_antecedente)


def _derivar_quarto_trimestre(con: duckdb.DuckDBPyConnection) -> int:
    """Deriva o 4T por DFP anual − ITR acumulado do 3T (RN10).

    O pareamento é feito pelo **conceito resolvido**, com o par
    código+descrição apenas como reserva para as contas que o mapa não cobre.
    Parear por `cd_conta` seria reintroduzir a falha da RN09 dentro da própria
    derivação: o Santander publica o lucro consolidado como `3.09` no ITR e como
    `3.11` na DFP do mesmo ano, e o join por código casaria o acumulado de nove
    meses do lucro com a linha anual *antes das participações* — número
    plausível, não nulo e errado, sem erro visível (medido em 2026-08-10).

    Só para contas de fluxo (`DEMONSTRATIVOS_DE_FLUXO` — DRE e as duas DFC):
    saldo de balanço em 31/12 é arquivado, não derivado. As linhas entram com
    `origem='derivado'` e escala `UNIDADE`, porque o valor já nasce em reais da
    subtração.

    A DFC entrou em 2026-08-27. O argumento é idêntico ao da DRE e a mecânica
    também — mas há uma armadilha PRÓPRIA do fluxo de caixa que a subtração
    resolve por acidente e que convém deixar dita: `Saldo Inicial` e `Saldo
    Final de Caixa` **não são fluxo**, são saldo instantâneo, e subtrair
    anual − 9 meses neles produz lixo. Eles sobrevivem à subtração porque a
    linha derivada só entra quando não existe já um trimestral equivalente, e
    o consumidor que precisa de saldo deve ler `origem='arquivado'`. Quem for
    calcular conversão de caixa usa as linhas de *Caixa Líquido das Atividades*
    (operacional, investimento, financiamento), que são fluxo de verdade.
    """
    antes = _contar(con, "fatos_contabeis")
    # Lista literal e não parâmetro: os valores são constantes do módulo, nunca
    # entrada externa, e um `IN (?)` de DuckDB não expande sequência aqui.
    fluxo = ", ".join(f"'{d}'" for d in sorted(DEMONSTRATIVOS_DE_FLUXO))
    con.execute(
        f"""
        INSERT INTO fatos_contabeis
        WITH resolvido AS (
            SELECT
                f.*,
                coalesce(
                    m.conceito,
                    'conta:' || f.cd_conta || '|' || f.ds_conta_norm
                ) AS chave_pareamento
            FROM fatos_contabeis AS f
            JOIN companhias AS c ON c.cd_cvm = f.cd_cvm
            LEFT JOIN mapa_contas AS m
              ON m.plano_contas = c.plano_contas
             AND m.cd_conta = f.cd_conta
             AND m.ds_conta_norm = f.ds_conta_norm
            WHERE f.demonstrativo IN ({fluxo})
        ),
        anual AS (
            SELECT * FROM resolvido WHERE tipo_periodo = 'anual'
        ),
        nove_meses AS (
            SELECT * FROM resolvido
            WHERE tipo_periodo = 'acumulado'
              AND datediff(
                      'month', dt_ini_exerc, dt_fim_exerc + INTERVAL 1 DAY
                  ) = 9
        )
        SELECT
            a.cd_cvm,
            a.conjunto,
            a.demonstrativo,
            a.trimestre,
            'trimestral' AS tipo_periodo,
            a.dt_refer,
            n.dt_fim_exerc + INTERVAL 1 DAY AS dt_ini_exerc,
            a.dt_fim_exerc,
            a.cd_conta,
            a.ds_conta,
            a.ds_conta_norm,
            a.valor_reais - n.valor_reais AS vl_conta,
            'UNIDADE' AS escala,
            a.valor_reais - n.valor_reais AS valor_reais,
            a.versao_documento,
            'derivado' AS origem
        FROM anual AS a
        JOIN nove_meses AS n
          ON n.cd_cvm = a.cd_cvm
         AND n.chave_pareamento = a.chave_pareamento
         AND n.dt_ini_exerc = a.dt_ini_exerc
        WHERE NOT EXISTS (
            SELECT 1 FROM fatos_contabeis AS ja
            WHERE ja.cd_cvm = a.cd_cvm
              AND ja.demonstrativo = a.demonstrativo
              AND ja.cd_conta = a.cd_conta
              AND ja.ds_conta_norm = a.ds_conta_norm
              AND ja.trimestre = a.trimestre
              AND ja.tipo_periodo = 'trimestral'
        )
        QUALIFY row_number() OVER (
            PARTITION BY a.cd_cvm, a.trimestre, a.chave_pareamento
            ORDER BY a.cd_conta, n.cd_conta
        ) = 1
        """
    )
    return _contar(con, "fatos_contabeis") - antes


def _contar_incoerencias_do_lucro(
    con: duckdb.DuckDBPyConnection, tolerancia_relativa: float = 0.005
) -> int:
    """Conta fatos em que o consolidado ≠ controladores + não controladores.

    A identidade é aritmética e vale por definição contábil, então quando ela
    falha o defeito está na fonte. Verificado em 2026-08-10: o ITR do 3T2025 do
    Santander traz `3.09` = 9.021.926 mil e `3.09.01` + `3.09.02` = 8.665.017
    mil — 356.909 mil de diferença, no arquivo bruto da CVM, sem nenhum sinal.
    A carga não conserta e não descarta: **conta e reporta**, porque um número
    que não fecha e ninguém vê é a falha que esta camada existe para combater.
    """
    return int(
        con.execute(
            f"""
            WITH painel AS (
                SELECT
                    cd_cvm, trimestre,
                    max(CASE WHEN conceito = '{CONCEITO_LUCRO_CONSOLIDADO}'
                             THEN valor_reais END) AS consolidado,
                    max(CASE WHEN conceito = '{CONCEITO_LUCRO_CONTROLADORES}'
                             THEN valor_reais END) AS controladores,
                    max(CASE WHEN conceito = '{CONCEITO_LUCRO_NAO_CONTROLADORES}'
                             THEN valor_reais END) AS nao_controladores
                FROM fatos_semanticos
                GROUP BY cd_cvm, trimestre
            )
            SELECT count(*) FROM painel
            WHERE consolidado IS NOT NULL
              AND controladores IS NOT NULL
              AND nao_controladores IS NOT NULL
              AND abs(consolidado - (controladores + nao_controladores))
                  > greatest(1.0, {tolerancia_relativa} * abs(consolidado))
            """
        ).fetchone()[0]
    )


def _materializar_indicadores(con: duckdb.DuckDBPyConnection) -> None:
    """Tabela derivada de indicadores por companhia × trimestre.

    `liquidez` NÃO existe aqui de propósito: o balanço de instituição
    financeira publicado na CVM não traz a separação circulante/não circulante
    que o índice pressupõe, e produzir um número a partir de contas que não são
    essas seria inventar. O que é calculável a partir de `fatos_semanticos`
    está aqui; o que não é, falta — declaradamente.
    """
    con.execute("DROP TABLE IF EXISTS indicadores")
    con.execute(
        f"""
        CREATE TABLE indicadores AS
        WITH painel AS (
            SELECT
                cd_cvm,
                trimestre,
                max(CASE WHEN conceito = '{CONCEITO_LUCRO_CONSOLIDADO}'
                         THEN valor_reais END) AS lucro_liquido_consolidado,
                max(CASE WHEN conceito = '{CONCEITO_LUCRO_CONTROLADORES}'
                         THEN valor_reais END) AS lucro_liquido_controladores,
                max(CASE WHEN conceito = '{CONCEITO_RECEITA_INTERMEDIACAO}'
                         THEN valor_reais END) AS receita_intermediacao,
                max(CASE WHEN conceito = '{CONCEITO_PATRIMONIO_LIQUIDO}'
                         THEN valor_reais END) AS patrimonio_liquido,
                max(CASE WHEN conceito = '{CONCEITO_ATIVO_TOTAL}'
                         THEN valor_reais END) AS ativo_total,
                max(CASE WHEN origem = 'derivado' THEN 1 ELSE 0 END) AS tem_derivado
            FROM fatos_semanticos
            GROUP BY cd_cvm, trimestre
        )
        SELECT
            cd_cvm,
            trimestre,
            lucro_liquido_consolidado,
            lucro_liquido_controladores,
            receita_intermediacao,
            patrimonio_liquido,
            ativo_total,
            lucro_liquido_consolidado / nullif(patrimonio_liquido, 0)
                AS roe_trimestral,
            lucro_liquido_consolidado / nullif(receita_intermediacao, 0)
                AS margem_liquida,
            ativo_total / nullif(patrimonio_liquido, 0) AS alavancagem,
            CASE WHEN tem_derivado = 1 THEN 'derivado' ELSE 'arquivado' END AS origem
        FROM painel
        """
    )


# --------------------------------------------------------------------------- #
# Guardas de SQL (RN04)
# --------------------------------------------------------------------------- #

_PALAVRAS_PROIBIDAS: frozenset[str] = frozenset(
    {
        "alter", "analyze", "attach", "begin", "call", "checkpoint", "comment",
        "commit", "copy", "create", "delete", "detach", "drop", "execute",
        "export", "force", "grant", "import", "insert", "install", "load",
        "merge", "pivot", "pragma", "prepare", "reset", "revoke", "rollback",
        "set", "start", "transaction", "truncate", "unpivot", "update",
        "vacuum", "use",
    }
)

# Funções de tabela e catálogos que dariam acesso a fora da lista branca.
_IDENTIFICADORES_PROIBIDOS: frozenset[str] = frozenset(
    {
        "csv_scan", "duckdb_settings", "duckdb_tables", "duckdb_views",
        "getenv", "glob", "information_schema", "parquet_scan", "pg_catalog",
        "read_blob", "read_csv", "read_csv_auto", "read_json",
        "read_json_auto", "read_parquet", "read_text", "sniff_csv",
        "sqlite_scan", "system", "temp",
    }
)

# `cd_conta` é rejeitado de propósito: quem escolhe o código da conta contorna a
# camada semântica e reintroduz exatamente a falha da RN09.
_COLUNAS_PROIBIDAS: frozenset[str] = frozenset({"cd_conta"})

_TABELA_APOS = frozenset({"from", "join"})
_LIMITE_CARACTERES_SQL = 4_000

_PADRAO_LITERAL = re.compile(r"'(?:[^']|'')*'")
_PADRAO_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*|[(),.;*]|\S")
_PADRAO_LIMIT = re.compile(r"\blimit\s+(\d+)\b", re.IGNORECASE)


def _tokenizar(sql_sem_literais: str) -> list[str]:
    return _PADRAO_TOKEN.findall(sql_sem_literais)


def validar_sql(sql: str, config: Config) -> str:
    """Aplica as guardas da RN04 e devolve o SQL aprovado.

    Qualquer violação levanta `SqlBloqueadoError` ANTES de qualquer execução —
    a análise é sintática, não uma tentativa protegida.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise SqlBloqueadoError("consulta vazia")
    bruto = sql.strip()
    if len(bruto) > _LIMITE_CARACTERES_SQL:
        raise SqlBloqueadoError(
            f"consulta excede {_LIMITE_CARACTERES_SQL} caracteres"
        )
    if "\x00" in bruto:
        raise SqlBloqueadoError("consulta contém byte nulo")
    if "--" in bruto or "/*" in bruto or "*/" in bruto:
        raise SqlBloqueadoError(
            "comentários não são aceitos: escondem carga útil da análise sintática"
        )

    # Literais viram um marcador que NÃO é identificador: o conteúdo do texto
    # não pode virar nome de tabela na análise, e o que sobrar de aspa depois
    # disso é literal não fechado.
    sem_literais = _PADRAO_LITERAL.sub("?", bruto)
    if "'" in sem_literais:
        raise SqlBloqueadoError("literal de texto não fechado")
    corpo = sem_literais.rstrip()
    if corpo.endswith(";"):
        corpo = corpo[:-1].rstrip()
    if ";" in corpo:
        raise SqlBloqueadoError("apenas uma instrução por consulta")

    tokens = _tokenizar(corpo)
    if not tokens:
        raise SqlBloqueadoError("consulta vazia")
    minusculos = [t.lower() for t in tokens]
    if minusculos[0] not in {"select", "with"}:
        raise SqlBloqueadoError(
            f"consulta deve começar por SELECT ou WITH; começa por {tokens[0]!r}"
        )

    proibidas = sorted(set(minusculos) & _PALAVRAS_PROIBIDAS)
    if proibidas:
        raise SqlBloqueadoError(f"instrução de DDL/DML bloqueada: {proibidas}")
    identificadores = sorted(set(minusculos) & _IDENTIFICADORES_PROIBIDOS)
    if identificadores:
        raise SqlBloqueadoError(
            f"identificador fora da lista branca: {identificadores}"
        )
    colunas = sorted(set(minusculos) & _COLUNAS_PROIBIDAS)
    if colunas:
        raise SqlBloqueadoError(
            f"coluna bloqueada: {colunas}. O código da conta não identifica o "
            "conceito contábil entre companhias (RN09) — consulte "
            "fatos_semanticos por 'conceito'."
        )

    # Alvos de FROM/JOIN: nome nu da lista branca, ou subconsulta entre
    # parênteses. Nome qualificado (esquema.tabela) é recusado.
    # Nomes locais que podem aparecer em FROM/JOIN sem serem tabelas reais:
    # aliases (`... AS c`) e CTEs (`WITH base AS (...)`, cujo nome vem ANTES do
    # AS). Nenhum deles amplia o acesso: a CTE só pode ler o que já passou pela
    # lista branca.
    aliases: set[str] = set()
    for indice, token in enumerate(minusculos):
        if token != "as":
            continue
        if indice + 1 < len(minusculos) and minusculos[indice + 1] != "(":
            aliases.add(minusculos[indice + 1])
        elif indice >= 1:
            aliases.add(minusculos[indice - 1])
    referenciadas: set[str] = set()
    for indice, token in enumerate(minusculos):
        if token not in _TABELA_APOS:
            continue
        if indice + 1 >= len(minusculos):
            raise SqlBloqueadoError(f"{token.upper()} sem alvo")
        alvo = minusculos[indice + 1]
        if alvo == "(":
            continue
        if indice + 2 < len(minusculos) and minusculos[indice + 2] == ".":
            raise SqlBloqueadoError(
                f"nome qualificado não é aceito em {token.upper()}: {alvo!r}"
            )
        referenciadas.add(alvo)
    fora = sorted(referenciadas - set(TABELAS_PERMITIDAS_SQL) - aliases)
    if fora:
        raise SqlBloqueadoError(
            f"tabela fora da lista branca: {fora}; "
            f"permitidas={sorted(TABELAS_PERMITIDAS_SQL)}"
        )

    casado = _PADRAO_LIMIT.search(corpo)
    if casado is None:
        raise SqlBloqueadoError(
            "LIMIT é obrigatório: o resultado é reinjetado no contexto do "
            "agente e uma consulta larga viraria truncamento silencioso"
        )
    limite = int(casado.group(1))
    if limite <= 0:
        raise SqlBloqueadoError("LIMIT deve ser positivo")
    if limite > config.sql_limite_linhas:
        raise SqlBloqueadoError(
            f"LIMIT {limite} excede SQL_LIMITE_LINHAS={config.sql_limite_linhas}"
        )
    return bruto


@dataclass(frozen=True)
class ResultadoSQL:
    """Resultado de uma consulta aprovada, junto do SQL que a produziu.

    O SQL viaja com o resultado porque a interface o exibe: consulta gerada por
    modelo de linguagem é verificável quando fica visível (RN01).
    """

    sql: str
    colunas: tuple[str, ...]
    linhas: tuple[tuple[Any, ...], ...]

    @property
    def total_linhas(self) -> int:
        return len(self.linhas)


def abrir_conexao_somente_leitura(
    config: Config, caminho: Path | None = None
) -> duckdb.DuckDBPyConnection:
    """Abre o painel em modo somente-leitura; falha claro se ele não existe."""
    destino = Path(caminho) if caminho is not None else Path(config.duckdb_path)
    if not destino.is_file():
        raise PainelIndisponivelError(
            f"painel CVM não encontrado em {destino}; rode "
            "scripts/baixar_cvm.py e a carga antes de consultar"
        )
    return duckdb.connect(str(destino), read_only=True)


def executar_sql(
    sql: str,
    config: Config,
    caminho: Path | None = None,
) -> ResultadoSQL:
    """Valida e executa a consulta em conexão somente-leitura, com tempo máximo."""
    aprovado = validar_sql(sql, config)
    con = abrir_conexao_somente_leitura(config, caminho)
    estourou = threading.Event()

    def _interromper() -> None:
        estourou.set()
        try:
            con.interrupt()
        except Exception:  # pragma: no cover - conexão já encerrada
            pass

    vigia = threading.Timer(config.sql_timeout_s, _interromper)
    vigia.daemon = True
    vigia.start()
    try:
        cursor = con.execute(aprovado)
        linhas = cursor.fetchall()
        colunas = tuple(desc[0] for desc in (cursor.description or ()))
    except Exception as exc:
        if estourou.is_set():
            raise SqlTempoExcedidoError(
                f"consulta interrompida após SQL_TIMEOUT_S={config.sql_timeout_s}s"
            ) from exc
        raise
    finally:
        vigia.cancel()
        con.close()
    return ResultadoSQL(
        sql=aprovado,
        colunas=colunas,
        linhas=tuple(tuple(linha) for linha in linhas),
    )


# --------------------------------------------------------------------------- #
# Gate G4
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ResultadoG4:
    """Conferência do mapa semântico para as companhias do corpus."""

    aprovado: bool
    divergencias: tuple[str, ...]
    resolvido: dict[str, dict[str, set[str]]]

    def como_texto(self) -> str:
        cabecalho = "G4 APROVADO" if self.aprovado else "G4 REPROVADO"
        if self.aprovado:
            return cabecalho
        return "\n".join([cabecalho, *(f"  - {d}" for d in self.divergencias)])


def conferir_mapa_g4(
    caminho: Path,
    conferencia: dict[str, dict[str, str | tuple[str, ...]]] | None = None,
) -> ResultadoG4:
    """Compara o mapa resolvido contra a conferência manual congelada.

    É a parte verificável do gate G4 sem a tabela de conciliação do release: o
    conceito certo resolve para o código certo em cada banco, e `3.09` e `3.11`
    não são tratados como equivalentes. A comparação contra a linha contábil da
    tabela de conciliação continua pendente e é a parte bloqueante restante.
    """
    esperado = dict(conferencia or CONFERENCIA_G4)
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        linhas = con.execute(
            """
            SELECT c.cd_cvm, m.conceito, m.cd_conta
            FROM companhias AS c
            JOIN mapa_contas AS m ON m.plano_contas = c.plano_contas
            WHERE c.cd_cvm IN (SELECT unnest(?))
            ORDER BY c.cd_cvm, m.conceito
            """,
            [sorted(esperado)],
        ).fetchall()
    finally:
        con.close()

    resolvido: dict[str, dict[str, set[str]]] = {}
    for cd_cvm, conceito, cd_conta in linhas:
        resolvido.setdefault(cd_cvm, {}).setdefault(conceito, set()).add(cd_conta)

    divergencias: list[str] = []
    for cd_cvm, conceitos in sorted(esperado.items()):
        banco = BANCO_POR_CD_CVM.get(cd_cvm)
        rotulo = f"{banco.banco if banco else cd_cvm} ({cd_cvm})"
        obtidos = resolvido.get(cd_cvm)
        if obtidos is None:
            divergencias.append(f"{rotulo}: companhia ausente do painel")
            continue
        for conceito, cd_esperado in sorted(conceitos.items()):
            aceitos = (
                {cd_esperado} if isinstance(cd_esperado, str) else set(cd_esperado)
            )
            cd_obtido = obtidos.get(conceito)
            if not cd_obtido:
                divergencias.append(
                    f"{rotulo}: conceito {conceito} não resolvido"
                )
            elif cd_obtido != aceitos:
                divergencias.append(
                    f"{rotulo}: {conceito} resolveu "
                    f"{sorted(cd_obtido)}, esperado {sorted(aceitos)}"
                )
    return ResultadoG4(
        aprovado=not divergencias,
        divergencias=tuple(divergencias),
        resolvido=resolvido,
    )


def lucro_por_banco(
    caminho: Path,
    trimestres: Iterable[str] | None = None,
) -> list[tuple[str, str, str, float | None, float | None, float | None]]:
    """Lucro consolidado × controladores por banco do corpus e trimestre.

    Devolve `(banco, cd_cvm, trimestre, consolidado, controladores, delta_pct)`.
    A diferença entre as duas linhas é de 1–4% em quatro bancos e de ~23% no
    Banco do Brasil (participações minoritárias relevantes) — nunca se responde
    "lucro líquido" sem dizer qual das duas.
    """
    filtro_trimestres = sorted(set(trimestres)) if trimestres else None
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        sql = f"""
            SELECT cd_cvm, trimestre,
                   max(CASE WHEN conceito = '{CONCEITO_LUCRO_CONSOLIDADO}'
                            THEN valor_reais END) AS consolidado,
                   max(CASE WHEN conceito = '{CONCEITO_LUCRO_CONTROLADORES}'
                            THEN valor_reais END) AS controladores
            FROM fatos_semanticos
            WHERE cd_cvm IN (SELECT unnest(?))
            GROUP BY cd_cvm, trimestre
            ORDER BY cd_cvm, trimestre
        """
        linhas = con.execute(sql, [list(CD_CVM_CORPUS)]).fetchall()
    finally:
        con.close()

    saida: list[tuple[str, str, str, float | None, float | None, float | None]] = []
    for cd_cvm, trimestre, consolidado, controladores in linhas:
        if filtro_trimestres is not None and trimestre not in filtro_trimestres:
            continue
        banco = BANCO_POR_CD_CVM.get(cd_cvm)
        delta = None
        if consolidado not in (None, 0) and controladores is not None:
            delta = (controladores - consolidado) / consolidado * 100.0
        saida.append(
            (
                banco.banco if banco else cd_cvm,
                cd_cvm,
                trimestre,
                consolidado,
                controladores,
                delta,
            )
        )
    saida.sort(key=lambda item: (item[0], item[2]))
    return saida


__all__ = [
    "CONCEITOS_DE_FLUXO",
    "ErroCargaCVM",
    "FonteCVM",
    "PainelIndisponivelError",
    "RelatorioCarga",
    "RelatorioRegra",
    "ResultadoG4",
    "ResultadoSQL",
    "SqlBloqueadoError",
    "SqlTempoExcedidoError",
    "abrir_conexao_somente_leitura",
    "carregar_painel",
    "conferir_mapa_g4",
    "criar_esquema",
    "executar_sql",
    "lucro_por_banco",
    "validar_sql",
]
