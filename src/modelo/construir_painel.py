"""Painel supervisionado companhia × trimestre a partir do DuckDB da 5.5.

Tarefa (spec 5.10): dada a posição contábil de uma companhia **até** o
trimestre T, ela reportará prejuízo em T+1?

**O que este alvo NÃO é, e a confusão custa caro.** Prejuízo trimestral não é
insolvência: acontece em ~33% dos trimestres-companhia deste painel e muitas
vezes é benigno — sazonalidade, baixa contábil pontual, ciclo de investimento.
A literatura clássica de falência (Altman 1968, Ohlson 1980) trata de evento
**terminal e raro**, de 1–2% de base. Importar as variáveis dela para cá foi
tentado e **não transferiu** (ver `OSCORE_REMOVIDAS_POR_MEDICAO`); a explicação
mais provável é justamente essa — são fenômenos diferentes, não só features
diferentes.

Por isso `construir_painel` aceita `trimestres_consecutivos=2`: exigir prejuízo
em T+1 **e** T+2 aproxima o alvo de deterioração real, separando-a de ruído
contábil de um trimestre só.

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

from dataclasses import dataclass

import duckdb
import pandas as pd

from src.normalizacao import TrimestreInvalidoError, ordinal_trimestre

# --------------------------------------------------------------------------- #
# Ordenação de trimestre
# --------------------------------------------------------------------------- #

# Reexportados de `src.normalizacao`, onde passaram a morar em 2026-08-24. O
# motivo é a RN07: a rota prospectiva do produto também precisa ordenar
# trimestre, e o caminho interativo não pode importar `src.modelo`. Duplicar a
# regra seria pior — foi ordenação por texto que produziu uma janela de
# cobertura errada na primeira versão daquela rota.
__all__ = [
    "COLUNAS_FEATURES",
    "PainelSupervisionado",
    "TrimestreInvalidoError",
    "construir_painel",
    "ordinal_trimestre",
    "trimestres_completos",
]


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
    # --- estrutura sazonal (exige janela longa; ver `trimestres_completos`) - #
    "prejuizo_no_mesmo_trimestre_do_ano_anterior",
    "variacao_lucro_anual",
    "taxa_prejuizos_4t",
    "trimestre_do_ano",
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

#: **RESULTADO NEGATIVO, MEDIDO E REGISTRADO** (2026-08-23, 47 folds
#: walk-forward sobre o painel de 2011–2026).
#:
#: `passivo_sobre_ativo` (TLTA), `variacao_lucro_escalada` (CHIN) e
#: `dois_prejuizos_seguidos` (INTWO) foram acrescentadas por serem análogas do
#: O-score de Ohlson (1980) — argumento de literatura, não medição. No painel
#: curto de um ano elas pareciam somar (+0,010 de AUC), mas o IC 95% incluía
#: zero e isso ficou declarado como "não demonstrado".
#:
#: Com poder estatístico de verdade, o veredito inverteu:
#:
#:   * boosting:  +0,0005  IC95 [-0,0004; +0,0014]  p = 0,135  (nulo)
#:   * logística: −0,0027  IC95 [-0,0040; -0,0013]  p = 3,3e-04 (PIORA)
#:
#: Testar como substituição (tirando `alavancagem` e `delta_roe`, que elas
#: deveriam suplantar) não muda o quadro. Foram removidas das features por
#: parcimônia; o SQL segue calculando-as e elas permanecem no quadro para
#: auditoria. O ganho real da janela larga veio das SAZONAIS, não daqui.
OSCORE_REMOVIDAS_POR_MEDICAO: tuple[str, ...] = (
    "passivo_sobre_ativo",
    "variacao_lucro_escalada",
    "dois_prejuizos_seguidos",
)

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
    #: 1 = prejuízo em T+1; 2 = prejuízo em T+1 E T+2 (alvo persistente).
    trimestres_consecutivos: int = 1

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
        origem,
        -- Controle setorial. `is_banco` é derivado do próprio dado (a
        -- companhia publica Receitas de Intermediação Financeira), não de uma
        -- lista de nomes — vale para as 741 sem fonte externa nenhuma.
        CASE WHEN c.is_banco THEN 1 ELSE 0 END AS instituicao_financeira
    FROM indicadores
    LEFT JOIN companhias c USING (cd_cvm)
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
),
-- Mesma fronteira `<= t.ordem`, restrita à janela móvel de 4 trimestres.
historico_4t AS (
    SELECT
        t.cd_cvm,
        t.ordem,
        sum(CASE WHEN h.lucro < 0 THEN 1 ELSE 0 END)::DOUBLE
            / count(*)                                          AS taxa_prejuizos_4t
    FROM ordenada t
    JOIN ordenada h
      ON h.cd_cvm = t.cd_cvm
     AND h.ordem <= t.ordem
     AND h.ordem > t.ordem - 4
    GROUP BY 1, 2
),
-- Alvo: prejuízo em TODOS os trimestres de T+1 .. T+n.
--
-- Com n = 1 é "prejuízo no próximo trimestre" — evento comum (~33%) que NÃO é
-- insolvência. Com n = 2 exige-se persistência do prejuízo, o que separa
-- deterioração de ruído contábil pontual (baixa isolada, sazonalidade).
alvo AS (
    SELECT
        t.cd_cvm,
        t.ordem,
        sum(CASE WHEN f.lucro < 0 THEN 1 ELSE 0 END)            AS n_prejuizos_futuros,
        max(CASE WHEN f.origem = 'derivado' THEN 1 ELSE 0 END)  AS rotulo_usa_derivado
    FROM ordenada t
    JOIN ordenada f
      ON f.cd_cvm = t.cd_cvm
     AND f.ordem > t.ordem
     AND f.ordem <= t.ordem + {n_alvo}
    GROUP BY 1, 2
    -- exige a janela COMPLETA; rótulo parcial seria rótulo inventado
    HAVING count(*) = {n_alvo}
)
SELECT
    t.cd_cvm,
    t.trimestre,
    t.ordem,
    t.origem                                                    AS origem_features,
    CASE WHEN prox.rotulo_usa_derivado = 1 THEN 'derivado'
         ELSE 'arquivado' END                                   AS origem_rotulo,

    t.roe_trimestral,
    t.lucro / nullif(t.ativo, 0)                                AS roa_trimestral,
    t.alavancagem,
    log10(abs(t.ativo) + 1)                                     AS log_ativo_total,
    t.instituicao_financeira,
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

    -- Estrutura sazonal. Para lucro TRIMESTRAL a referência da literatura é o
    -- *seasonal random walk*: o preditor natural do trimestre alvo (T+1) é o
    -- MESMO trimestre do ano anterior, que é T-3 — não T.
    CASE WHEN ant3.lucro IS NULL THEN NULL
         WHEN ant3.lucro < 0 THEN 1 ELSE 0
    END                                            AS prejuizo_no_mesmo_trimestre_do_ano_anterior,
    -- Variação ano contra ano no MESMO trimestre, escalada como o CHIN.
    -- Compara T com T-4, isolando a sazonalidade da tendência.
    CASE WHEN ant4.lucro IS NULL THEN NULL
         ELSE (t.lucro - ant4.lucro)
              / nullif(abs(t.lucro) + abs(ant4.lucro), 0)
    END                                                         AS variacao_lucro_anual,
    -- Frequência de prejuízo na janela móvel de 4 trimestres: comparável entre
    -- companhias com históricos de comprimentos muito diferentes, o que a
    -- taxa sobre todo o histórico não é quando a janela vai de 2011 a 2026.
    h4.taxa_prejuizos_4t,
    -- Trimestre do ano (1–4). Só é feature LEGÍTIMA com janela longa: com um
    -- ano só ela seria idêntica à identidade do trimestre e o teste teria um
    -- valor nunca visto no treino. Com 61 trimestres, os quatro valores
    -- aparecem no treino, e ela captura o efeito de 4º trimestre que a
    -- literatura de lucro trimestral documenta.
    (t.ordem % 4) + 1                                           AS trimestre_do_ano,

    CASE WHEN prox.n_prejuizos_futuros = {n_alvo} THEN 1 ELSE 0 END AS rotulo,
    -- Sem esta coluna, a junção frouxa do modo inferência produziria `rotulo`
    -- = 0 para quem ainda NÃO tem futuro (NULL cai no ELSE) — rótulo inventado
    -- disfarçado de "lucro". A coluna torna a distinção verificável.
    CASE WHEN prox.n_prejuizos_futuros IS NULL THEN 0 ELSE 1 END AS rotulo_conhecido
FROM ordenada t
JOIN historico h
  ON h.cd_cvm = t.cd_cvm AND h.ordem = t.ordem
-- O alvo cobre T+1 .. T+n por junção explícita, e o `HAVING count(*) = n`
-- exige que TODOS os trimestres da janela existam: companhia que some do
-- painel sai da amostra em vez de receber rótulo parcial.
{juncao_alvo} alvo prox
  ON prox.cd_cvm = t.cd_cvm AND prox.ordem = t.ordem
-- T-1 é opcional: a primeira observação de cada companhia tem lag nulo, e o
-- modelo precisa saber lidar com isso em produção.
LEFT JOIN ordenada ant
  ON ant.cd_cvm = t.cd_cvm AND ant.ordem = t.ordem - 1
-- T-3 é o mesmo trimestre do ano anterior visto do alvo T+1; T-4, visto de T.
LEFT JOIN ordenada ant3
  ON ant3.cd_cvm = t.cd_cvm AND ant3.ordem = t.ordem - 3
LEFT JOIN ordenada ant4
  ON ant4.cd_cvm = t.cd_cvm AND ant4.ordem = t.ordem - 4
JOIN historico_4t h4
  ON h4.cd_cvm = t.cd_cvm AND h4.ordem = t.ordem
ORDER BY t.ordem, t.cd_cvm
"""


_SQL_REPUBLICACAO = """
WITH versao_por_obs AS (
    SELECT cd_cvm, trimestre, max(versao_documento) AS versao_max
    FROM fatos_contabeis
    GROUP BY 1, 2
)
SELECT
    CASE WHEN i.lucro_liquido_consolidado < 0 THEN 1 ELSE 0 END AS prejuizo,
    count(*)                                                    AS n,
    sum(CASE WHEN v.versao_max > 1 THEN 1 ELSE 0 END)           AS n_republicado
FROM indicadores i
JOIN versao_por_obs v USING (cd_cvm, trimestre)
WHERE i.lucro_liquido_consolidado IS NOT NULL
GROUP BY 1
"""


def medir_republicacao(con: duckdb.DuckDBPyConnection) -> dict[str, object]:
    """Mede o viés *as-restated* em vez de apenas declará-lo.

    A armadilha 1 da carga mantém só a maior VERSAO por companhia × trimestre,
    que é a regra certa para consulta — o número corrigido é o número correto.
    Para o modelo, porém, ela cria viés de antecipação: parte do painel de
    treino é composta de valores que **não estavam disponíveis** na data em que
    o trimestre fechou, porque só apareceram na republicação.

    Não dá para desfazer isso com o painel carregado (as versões anteriores são
    descartadas na carga, e recuperá-las exigiria reler os ZIPs por versão).
    O que dá — e é o que esta função faz — é medir o tamanho da exposição e,
    principalmente, se ela é **assimétrica entre as classes**. Republicação
    concentrada nos trimestres de prejuízo seria contaminação direta do rótulo;
    republicação uniforme é ruído que não empurra o modelo para um lado.

    Medido em 2026-08-25 no painel de treino (2011–2026): 16,36% das
    observações, com 16,81% nos trimestres de prejuízo contra 16,14% nos de
    lucro — diferença de 0,67 ponto, sem concentração na classe positiva.
    """
    linhas = con.execute(_SQL_REPUBLICACAO).fetchall()
    por_classe = {
        int(prejuizo): {"n": int(n), "n_republicado": int(n_rep or 0)}
        for prejuizo, n, n_rep in linhas
    }
    total = sum(bloco["n"] for bloco in por_classe.values())
    total_rep = sum(bloco["n_republicado"] for bloco in por_classe.values())

    def _taxa(classe: int) -> float | None:
        bloco = por_classe.get(classe)
        if not bloco or bloco["n"] == 0:
            return None
        return bloco["n_republicado"] / bloco["n"]

    taxa_prejuizo, taxa_lucro = _taxa(1), _taxa(0)
    assimetria = (
        None
        if taxa_prejuizo is None or taxa_lucro is None
        else taxa_prejuizo - taxa_lucro
    )
    return {
        "n_observacoes": total,
        "n_republicadas": total_rep,
        "fracao_republicada": (total_rep / total) if total else 0.0,
        "fracao_republicada_em_prejuizo": taxa_prejuizo,
        "fracao_republicada_em_lucro": taxa_lucro,
        "assimetria_entre_classes": assimetria,
        "ressalva": (
            "Parte do painel usa valores que só existiram após republicação e "
            "não estavam disponíveis no fechamento do trimestre (viés "
            "as-restated). Não é reversível com o painel carregado — a carga "
            "mantém só a maior VERSAO. A exposição é medida e a assimetria "
            "entre classes é o que importa: republicação concentrada no "
            "prejuízo contaminaria o rótulo; uniforme, não."
        ),
    }


def construir_painel(
    con: duckdb.DuckDBPyConnection,
    *,
    fracao_minima: float = 0.5,
    trimestres_consecutivos: int = 1,
) -> PainelSupervisionado:
    """Monta o painel supervisionado a partir da tabela `indicadores`.

    `trimestres_consecutivos` define o alvo: 1 = prejuízo em T+1 (evento comum,
    ~33%); 2 = prejuízo em T+1 **e** T+2, que exige persistência e por isso
    separa deterioração de ruído contábil pontual.
    """
    if trimestres_consecutivos < 1:
        raise ValueError("trimestres_consecutivos precisa ser >= 1")
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
    sql = _SQL_PAINEL.format(
        lista_trimestres=lista,
        caso_ordem=caso_ordem,
        n_alvo=trimestres_consecutivos,
        juncao_alvo="JOIN",
    )
    quadro = con.execute(sql).df()

    faltantes = [c for c in COLUNAS_FEATURES if c not in quadro.columns]
    if faltantes:
        raise RuntimeError(f"features ausentes na consulta: {faltantes}")

    return PainelSupervisionado(
        quadro=quadro,
        trimestres_usados=completos,
        trimestres_descartados=descartados,
        trimestres_consecutivos=trimestres_consecutivos,
    )


def exigir_trimestre_sem_rotulo(quadro: pd.DataFrame, trimestre: str) -> None:
    """Levanta se o trimestre a escorar já tiver desfecho conhecido.

    Função separada de propósito. Embutida em
    `construir_painel_para_inferencia`, a condição é **inalcançável** hoje: o
    trimestre escolhido é o último de `completos`, e o alvo só existe quando há
    trimestre posterior dentro da mesma janela. Uma guarda inalcançável não é
    testável, e guarda não testável é comentário — foi o que a auditoria de
    2026-08-25 apontou, junto com um teste meu que dizia verificar a falha
    fechada e na verdade exercitava o caminho feliz.

    Ela continua existindo porque a escolha do trimestre é uma linha
    (`alvo = completos[-1]`) que qualquer parametrização futura muda — escorar
    um trimestre já resolvido entregaria retrospectiva com cara de previsão.
    Extraída, a guarda passa a ser exercitada diretamente pelo teste, sem
    depender de o SQL um dia deixá-la alcançável.
    """
    if "rotulo_conhecido" not in quadro.columns:
        raise ValueError(
            "quadro sem a coluna `rotulo_conhecido`; sem ela não há como "
            "distinguir 'lucro' de 'ainda não aconteceu'"
        )
    n_com_rotulo = int(quadro["rotulo_conhecido"].sum())
    if n_com_rotulo:
        raise ValueError(
            f"o trimestre {trimestre!r} já tem rótulo conhecido para "
            f"{n_com_rotulo} companhias — não é o trimestre corrente; use "
            "`construir_painel` para avaliar"
        )


@dataclass(frozen=True)
class PainelDeInferencia:
    """O trimestre corrente: tem feature, ainda não tem rótulo.

    Deliberadamente NÃO é um `PainelSupervisionado`. Os dois têm as mesmas
    colunas de feature e seria fácil passar um onde se espera o outro — e a
    consequência disso seria treinar sobre linhas cujo `rotulo` é 0 só porque
    o futuro ainda não aconteceu. Tipo diferente para que o erro não compile.
    """

    quadro: pd.DataFrame
    trimestre: str
    trimestres_consecutivos: int
    #: Quantas linhas do trimestre foram removidas por já estarem em prejuízo.
    n_descartadas_por_ja_estar_em_prejuizo: int = 0

    @property
    def n_companhias(self) -> int:
        return len(self.quadro)


def construir_painel_para_inferencia(
    con: duckdb.DuckDBPyConnection,
    *,
    fracao_minima: float = 0.5,
    trimestres_consecutivos: int = 1,
    somente_hoje_lucrativas: bool = True,
) -> PainelDeInferencia:
    """Features do trimestre mais recente FECHADO, sem exigir rótulo.

    Fecha o defeito estrutural apontado em 2026-08-25: `construir_painel` junta
    o alvo com `JOIN` e `HAVING count(*) = n`, então qualquer companhia sem os
    n trimestres futuros some da amostra. Isso é correto para treinar e
    avaliar — e é exatamente errado para *usar* o modelo, porque a companhia
    sobre a qual se quer prever é justamente a que não tem futuro ainda. O
    efeito prático era o panorama publicar um trimestre de referência dois
    trimestres atrás do último dado completo disponível.

    **`somente_hoje_lucrativas=True` é o padrão, e não é conveniência.** A
    decomposição de 2026-08-25 mostrou que 97,1% do decil superior já está em
    prejuízo no próprio trimestre T: ordenar o painel inteiro devolve
    majoritariamente companhias cujo prejuízo qualquer um lê na demonstração,
    sem modelo nenhum. Restringir a `prejuizo_em_t = 0` é o único recorte em
    que o escore carrega informação que o leitor não tinha — e o denominador
    honesto (quantas companhias sobraram) sai junto, para que a queda de
    volume não passe despercebida.

    O treino não precisa de guarda temporal explícita aqui: o rótulo do
    trimestre devolvido **não existe**, então nenhum fold pode tê-lo visto.
    """
    if trimestres_consecutivos < 1:
        raise ValueError("trimestres_consecutivos precisa ser >= 1")
    completos, _ = trimestres_completos(con, fracao_minima=fracao_minima)
    if not completos:
        raise ValueError("painel sem trimestre completo para inferência")

    lista = "(" + ", ".join(f"'{t}'" for t in completos) + ")"
    caso_ordem = (
        "CASE "
        + " ".join(
            f"WHEN trimestre = '{t}' THEN {ordinal_trimestre(t)}" for t in completos
        )
        + " END"
    )
    quadro = con.execute(
        _SQL_PAINEL.format(
            lista_trimestres=lista,
            caso_ordem=caso_ordem,
            n_alvo=trimestres_consecutivos,
            juncao_alvo="LEFT JOIN",
        )
    ).df()

    alvo = completos[-1]
    quadro = quadro[quadro["trimestre"] == alvo].copy()
    if quadro.empty:
        raise ValueError(f"nenhuma linha para o trimestre {alvo!r}")

    exigir_trimestre_sem_rotulo(quadro, alvo)
    # O `rotulo` que a consulta emite aqui é 0 por construção (NULL cai no
    # ELSE). Zerá-lo para NA é o que impede alguém treinar sobre isto.
    quadro["rotulo"] = pd.NA

    n_descartadas = 0
    if somente_hoje_lucrativas:
        antes = len(quadro)
        quadro = quadro[quadro["prejuizo_em_t"] == 0].copy()
        n_descartadas = antes - len(quadro)

    return PainelDeInferencia(
        quadro=quadro.reset_index(drop=True),
        trimestre=alvo,
        trimestres_consecutivos=trimestres_consecutivos,
        n_descartadas_por_ja_estar_em_prejuizo=n_descartadas,
    )
