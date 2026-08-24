"""Painel supervisionado companhia × trimestre a partir do DuckDB da 5.5.

Tarefa (spec 5.10): dada a posição contábil de uma companhia **até** o
trimestre T, ela reportará prejuízo em T+1?

Três disciplinas que este módulo existe para tornar auditáveis:

1. **Nenhuma feature olha para depois de T.** Toda coluna derivada de história
   é construída por junção explícita em `ordem - k`, nunca por `LAG`/`LEAD`
   sobre a linha vizinha — se um trimestre faltar para aquela companhia, a
   junção devolve nulo em vez de pegar silenciosamente um trimestre distante.
   `tests/test_modelo.py::TestVazamentoTemporal` trava isso.
2. **O rótulo sai de `fatos_semanticos`, nunca de `cd_conta`** (RN09). A
   tabela `indicadores` já resolve o conceito pelo mapa semântico validado
   pelo gate G4; aqui só se lê o resultado.
3. **Trimestre incompleto não entra.** A CVM recebe declarações ao longo de
   meses: no painel carregado, `2T2026` tem 128 companhias contra ~435 dos
   trimestres fechados — e **17% de prejuízo contra ~29%**. Quem declara cedo
   é sistematicamente mais saudável, então admitir um trimestre parcial não
   adiciona amostra: adiciona viés de seleção com cara de amostra.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import duckdb
import pandas as pd

# --------------------------------------------------------------------------- #
# Ordenação de trimestre
# --------------------------------------------------------------------------- #

_PADRAO_TRIMESTRE = re.compile(r"^([1-4])T(\d{4})$")


class TrimestreInvalidoError(ValueError):
    """Rótulo de trimestre fora do formato `<n>T<ano>`."""


def ordinal_trimestre(trimestre: str) -> int:
    """`'3T2025'` → inteiro monotônico, para que T+1 seja `ordem + 1`.

    Ordenar `trimestre` como texto colocaria `1T2026` antes de `3T2025`, o que
    inverteria a direção do tempo sem levantar erro nenhum.
    """
    casado = _PADRAO_TRIMESTRE.match(trimestre.strip())
    if casado is None:
        raise TrimestreInvalidoError(
            f"trimestre {trimestre!r} não está no formato <n>T<ano> (ex.: 3T2025)"
        )
    numero, ano = int(casado.group(1)), int(casado.group(2))
    return ano * 4 + (numero - 1)


# --------------------------------------------------------------------------- #
# Features
# --------------------------------------------------------------------------- #

#: Colunas oferecidas ao modelo. Todas calculadas com dados de períodos ≤ T.
COLUNAS_FEATURES: tuple[str, ...] = (
    "roe_trimestral",
    "roa_trimestral",
    "alavancagem",
    "log_ativo_total",
    "patrimonio_negativo",
    "prejuizo_em_t",
    "prejuizo_em_t_menos_1",
    "taxa_prejuizos_ate_t",
    "delta_roe",
    "delta_lucro_sobre_ativo",
    "delta_patrimonio_relativo",
    # --- análogas do O-score de Ohlson (1980) ------------------------------ #
    "passivo_sobre_ativo",
    "variacao_lucro_escalada",
    "dois_prejuizos_seguidos",
)

#: Correspondência com as nove variáveis do O-score (Ohlson, 1980), que a
#: literatura de insolvência trata como referência. Registrada aqui para que a
#: escolha de feature seja rastreável a algo publicado, não ao meu gosto.
#:
#:   SIZE   → log_ativo_total
#:   TLTA   → passivo_sobre_ativo
#:   NITA   → roa_trimestral
#:   OENEG  → patrimonio_negativo
#:   INTWO  → dois_prejuizos_seguidos
#:   CHIN   → variacao_lucro_escalada
#:
#: WCTA, CLCA e FUTL **não são calculáveis** neste painel: as duas primeiras
#: exigem a separação circulante/não circulante, que a demonstração de
#: instituição financeira arquivada na CVM não traz (mesmo motivo pelo qual
#: `liquidez` não existe em `indicadores`), e FUTL exige demonstração de fluxo
#: de caixa, que não está carregada. Faltam declaradamente.
OSCORE_DISPONIVEIS: tuple[str, ...] = (
    "log_ativo_total",
    "passivo_sobre_ativo",
    "roa_trimestral",
    "patrimonio_negativo",
    "dois_prejuizos_seguidos",
    "variacao_lucro_escalada",
)
OSCORE_INDISPONIVEIS: dict[str, str] = {
    "WCTA": "capital de giro exige circulante/não circulante, ausente no painel",
    "CLCA": "idem WCTA",
    "FUTL": "exige demonstração de fluxo de caixa, não carregada",
}

#: Descartadas de propósito, com o motivo — não é omissão.
COLUNAS_DESCARTADAS: dict[str, str] = {
    "receita_intermediacao": (
        "preenchida em 77 de 2.321 linhas (3%) — é conceito de instituição "
        "financeira e o painel é majoritariamente não financeiro; imputar "
        "97% de uma coluna é inventar variável, não tratá-la"
    ),
    "margem_liquida": (
        "derivada de receita_intermediacao, herda o mesmo 3% de preenchimento"
    ),
    "lucro_liquido_controladores": (
        "colinear com o lucro consolidado, que é a base do rótulo; entra "
        "indiretamente pela razão de participação, que não é estável quando o "
        "denominador passa perto de zero"
    ),
    "n_trimestres_observados": (
        "confundida com o tempo: como o painel começa em 1T2025, a "
        "profundidade de histórico é determinada pelo trimestre (1 em 1T2025, "
        "4 em 4T2025). O split temporal põe profundidade 1–3 no treino e 4 no "
        "teste, então o valor de teste NUNCA foi visto no treino e qualquer "
        "corte de árvore nessa coluna extrapola. Fica no quadro para auditoria, "
        "fora das features"
    ),
    "n_prejuizos_ate_t": (
        "contagem limitada pela profundidade, herda a mesma confusão com o "
        "tempo; substituída por `taxa_prejuizos_ate_t`, que é comparável entre "
        "profundidades diferentes"
    ),
}


@dataclass(frozen=True)
class PainelSupervisionado:
    """Painel pronto para treino, com a fronteira temporal explícita."""

    quadro: pd.DataFrame
    trimestres_usados: tuple[str, ...]
    trimestres_descartados: dict[str, int]

    @property
    def n_observacoes(self) -> int:
        return len(self.quadro)

    @property
    def taxa_positivos(self) -> float:
        if self.quadro.empty:
            return 0.0
        return float(self.quadro["rotulo"].mean())


def trimestres_completos(
    con: duckdb.DuckDBPyConnection, *, fracao_minima: float = 0.5
) -> tuple[tuple[str, ...], dict[str, int]]:
    """Separa trimestres fechados dos que ainda estão recebendo declaração.

    O corte é relativo à mediana de companhias por trimestre, não um número
    fixo: se o painel for recarregado com outra janela, a regra continua
    valendo sem edição.
    """
    linhas = con.execute(
        "SELECT trimestre, count(*) AS n FROM indicadores GROUP BY 1"
    ).fetchall()
    if not linhas:
        return (), {}

    contagens = {trimestre: int(n) for trimestre, n in linhas}
    ordenadas = sorted(contagens.values())
    meio = len(ordenadas) // 2
    mediana = (
        ordenadas[meio]
        if len(ordenadas) % 2
        else (ordenadas[meio - 1] + ordenadas[meio]) / 2
    )
    limite = mediana * fracao_minima

    completos = sorted(
        (t for t, n in contagens.items() if n >= limite), key=ordinal_trimestre
    )
    descartados = {t: n for t, n in contagens.items() if n < limite}
    return tuple(completos), descartados


_SQL_PAINEL = """
WITH base AS (
    SELECT
        cd_cvm,
        trimestre,
        lucro_liquido_consolidado          AS lucro,
        patrimonio_liquido                 AS pl,
        ativo_total                        AS ativo,
        roe_trimestral,
        alavancagem,
        origem
    FROM indicadores
    WHERE trimestre IN {lista_trimestres}
      AND lucro_liquido_consolidado IS NOT NULL
      AND ativo_total IS NOT NULL
      AND patrimonio_liquido IS NOT NULL
),
ordenada AS (
    SELECT *, {caso_ordem} AS ordem FROM base
),
-- Histórico acumulado ATÉ T. A condição `h.ordem <= t.ordem` é a fronteira
-- temporal inteira deste módulo: nada além dela entra em feature.
historico AS (
    SELECT
        t.cd_cvm,
        t.ordem,
        count(*)                                                AS n_trimestres_observados,
        sum(CASE WHEN h.lucro < 0 THEN 1 ELSE 0 END)            AS n_prejuizos_ate_t
    FROM ordenada t
    JOIN ordenada h
      ON h.cd_cvm = t.cd_cvm AND h.ordem <= t.ordem
    GROUP BY 1, 2
)
SELECT
    t.cd_cvm,
    t.trimestre,
    t.ordem,
    t.origem                                                    AS origem_features,
    prox.origem                                                 AS origem_rotulo,

    t.roe_trimestral,
    t.lucro / nullif(t.ativo, 0)                                AS roa_trimestral,
    t.alavancagem,
    log10(abs(t.ativo) + 1)                                     AS log_ativo_total,
    CASE WHEN t.pl < 0 THEN 1 ELSE 0 END                        AS patrimonio_negativo,
    CASE WHEN t.lucro < 0 THEN 1 ELSE 0 END                     AS prejuizo_em_t,
    CASE WHEN ant.lucro IS NULL THEN NULL
         WHEN ant.lucro < 0 THEN 1 ELSE 0 END                   AS prejuizo_em_t_menos_1,
    h.n_prejuizos_ate_t,
    h.n_trimestres_observados,
    h.n_prejuizos_ate_t::DOUBLE
        / nullif(h.n_trimestres_observados, 0)                  AS taxa_prejuizos_ate_t,
    t.roe_trimestral - ant.roe_trimestral                       AS delta_roe,
    (t.lucro - ant.lucro) / nullif(t.ativo, 0)                  AS delta_lucro_sobre_ativo,
    (t.pl - ant.pl) / nullif(abs(ant.pl), 0)                    AS delta_patrimonio_relativo,

    -- TLTA: passivo total sobre ativo. Preferível a `alavancagem` (ativo/PL),
    -- que explode e troca de sinal quando o patrimônio passa por zero; este
    -- fica bem definido mesmo com PL negativo (valor > 1 = insolvente).
    (t.ativo - t.pl) / nullif(t.ativo, 0)                       AS passivo_sobre_ativo,
    -- CHIN: variação do lucro escalada, limitada a [-1, 1]. Trata troca de
    -- sinal com elegância, ao contrário de razões que dividem por um lucro
    -- anterior perto de zero.
    CASE WHEN ant.lucro IS NULL THEN NULL
         ELSE (t.lucro - ant.lucro)
              / nullif(abs(t.lucro) + abs(ant.lucro), 0)
    END                                                         AS variacao_lucro_escalada,
    -- INTWO: dois períodos seguidos de prejuízo.
    CASE WHEN ant.lucro IS NULL THEN NULL
         WHEN t.lucro < 0 AND ant.lucro < 0 THEN 1 ELSE 0
    END                                                         AS dois_prejuizos_seguidos,

    CASE WHEN prox.lucro < 0 THEN 1 ELSE 0 END                  AS rotulo
FROM ordenada t
JOIN historico h
  ON h.cd_cvm = t.cd_cvm AND h.ordem = t.ordem
-- T+1 por junção explícita em `ordem + 1`: se o trimestre seguinte não existir
-- para aquela companhia, ela sai do painel em vez de receber rótulo de um
-- trimestre distante.
JOIN ordenada prox
  ON prox.cd_cvm = t.cd_cvm AND prox.ordem = t.ordem + 1
-- T-1 é opcional: a primeira observação de cada companhia tem lag nulo, e o
-- modelo precisa saber lidar com isso em produção.
LEFT JOIN ordenada ant
  ON ant.cd_cvm = t.cd_cvm AND ant.ordem = t.ordem - 1
ORDER BY t.ordem, t.cd_cvm
"""


def construir_painel(
    con: duckdb.DuckDBPyConnection, *, fracao_minima: float = 0.5
) -> PainelSupervisionado:
    """Monta o painel supervisionado a partir da tabela `indicadores`."""
    completos, descartados = trimestres_completos(
        con, fracao_minima=fracao_minima
    )
    if len(completos) < 2:
        raise ValueError(
            "painel precisa de ao menos dois trimestres completos para formar "
            f"um par T→T+1; completos={completos!r}, descartados={descartados!r}"
        )

    lista = "(" + ", ".join(f"'{t}'" for t in completos) + ")"
    caso_ordem = (
        "CASE "
        + " ".join(
            f"WHEN trimestre = '{t}' THEN {ordinal_trimestre(t)}" for t in completos
        )
        + " END"
    )
    sql = _SQL_PAINEL.format(lista_trimestres=lista, caso_ordem=caso_ordem)
    quadro = con.execute(sql).df()

    faltantes = [c for c in COLUNAS_FEATURES if c not in quadro.columns]
    if faltantes:
        raise RuntimeError(f"features ausentes na consulta: {faltantes}")

    return PainelSupervisionado(
        quadro=quadro,
        trimestres_usados=completos,
        trimestres_descartados=descartados,
    )
