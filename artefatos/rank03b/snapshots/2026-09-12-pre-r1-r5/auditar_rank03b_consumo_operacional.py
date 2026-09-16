"""Auditor do Rank 3-B — início de consumo operacional persistente.

**Implementa literalmente o contrato de
`resultados/pre_registro_rank03b_consumo_operacional_2026-09-11.md`, congelado
antes de este arquivo existir (SHA-256 `fbae30cc…`).** Divergência entre os dois
é defeito DESTE arquivo, nunca licença para reinterpretar o contrato.

**Nenhum modelo é carregado.** O que se mede é se o alvo sobrevive a G0, G1, T1
e T2, e o que os quatro baselines triviais entregam. O painel é aberto
**somente leitura**.

Alvo (§2 do pré-registro):

    q1 = primeiro trimestre fiscal cujo INÍCIO é posterior a D
    S1 = FCO(q1) + FCO(q2)      S2 = FCO(q3) + FCO(q4)
    Y  = 1 se S1 < 0 E S2 < 0

Elegibilidade: `FCO_TTM` conhecido em D > 0, companhia não financeira,
`ativo_total` conhecido em D > 0, e os quatro trimestres do rótulo existindo
como trimestre isolado.
"""

from __future__ import annotations

import json
import math
import random
import statistics
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.normalizacao import ordinal_trimestre  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
PAINEL = RAIZ / "artefatos" / "cvm_treino.duckdb"
DESTINO = RAIZ / "artefatos" / "rank03b"

#: Fluxo de caixa operacional no plano padrão da CVM.
CONTA_FCO = "6.01"
#: Ativo total no BPA.
CONTA_ATIVO = "1"

# --- limiares, todos do pré-registro; nenhum escolhido aqui ----------------
T1_AMPLITUDE = 0.15
#: Zona em que o viés para cima da amplitude por quintis exige bootstrap.
T1_ZONA_CINZENTA = 0.12
#: P(amplitude verdadeira > 0,15) acima disso ⇒ INDECIDÍVEL, não aprovado.
T1_PROB_MAXIMA = 0.10
T2_LACUNA = 0.12
MINIMO_DE_OBSERVACOES = 500
MINIMO_DE_COMPANHIAS = 30
#: Janela da volatilidade própria do FCO (mesma do C1, por comparabilidade).
JANELA_SD = 8
REAMOSTRAGENS = 2000
SEMENTE = 20260911

#: G0.2 — um trimestre fiscal tem de durar ~1 trimestre. Fluxo semestral
#: rotulado trimestral foi achado no painel pela auditoria de 2026-09-08.
DURACAO_MINIMA_DIAS = 80
DURACAO_MAXIMA_DIAS = 100
#: G0.3 — salto de escala entre trimestres adjacentes (troca MIL↔UNIDADE).
FATOR_DE_SALTO_DE_ESCALA = 100
G0_TOLERANCIA_ESCALA = 0.005

#: Componentes de T1, na ordem do §6 do pré-registro. A lista NÃO pode encolher.
COMPONENTES_T1 = (
    "fco_ttm_sobre_sd8",
    "fco_ttm_em_D",
    "fco_ttm_sobre_ativo",
    "sd8_fco_isolado",
    "ativo_total_em_D",
    "trimestres_com_fco_negativo_nos_ultimos_8",
)

#: Baselines triviais do §8. `sentido` diz se o escore ordena por risco
#: crescente (+1) ou decrescente (-1) — quanto MENOR `fco/sd8`, maior o risco.
BASELINES = {
    "B1_fco_sobre_sd8": ("fco_ttm_sobre_sd8", -1),
    "B2_trimestres_negativos": ("trimestres_com_fco_negativo_nos_ultimos_8", +1),
    "B3_fco_sobre_ativo": ("fco_ttm_sobre_ativo", -1),
}


class AmostraInsuficiente(Exception):
    """Amostra pequena para decidir. NUNCA é aprovação.

    O auditor do Rank 3 devolvia "T1 aprovado" sobre amostra vazia porque com
    `n = 0` a amplitude saía `NaN` e `NaN >= 0,15` é `False` (AGENTS.md §4.4,
    regra 4). Guarda que aprova por ausência de dado é pior que guarda nenhuma.
    """


class EscoreDegenerado(Exception):
    """Escore constante não pode "passar" T2 por ter lacuna zero.

    Foi o defeito do instrumento do B-DFC-01J: T2 aprovava por AUSÊNCIA de
    poder discriminante, porque um escore constante dá AUC 0,5 por construção.
    """


class DefeitoDeIntegridade(Exception):
    """G0 reprovou. Deliberadamente NÃO é `AmostraInsuficiente`.

    Amostra insuficiente é estado legítimo do mundo e entra no relatório como
    gate reprovado com motivo. Defeito de dado tem de subir alto, senão fica
    escondido atrás de um veredito plausível (AGENTS.md §4.4, regra 5).
    """


# --- carga -----------------------------------------------------------------

def carregar_fco(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """FCO por companhia–trimestre isolado, com `dt_receb` e período exato.

    Três decisões que vêm de defeito medido, não de preferência:

    - **`max(valor_reais)`, não `sum`**: 5 companhia–trimestres publicam pelos
      dois métodos (`DFC_MD` e `DFC_MI`) e somá-los duplicaria o caixa
      (AGENTS.md §3.13). Os dois medem a mesma grandeza.
    - **`tipo_periodo='trimestral'`**: o acumulado somaria o mesmo caixa várias
      vezes numa janela móvel.
    - **`dt_receb` vem de `documentos`**, não de `dt_refer`. Usar `dt_refer`
      como data de publicação enxerga o formulário antes de ele existir: o
      atraso mediano é de 44 dias no ITR e 83 na DFP, e 41% dos documentos
      chegam depois de 45 dias (AGENTS.md §3.13).
    """
    return con.execute(
        f"""
        WITH elegiveis AS (
            SELECT cd_cvm FROM companhias
            WHERE plano_contas NOT LIKE 'll3_09_%' AND NOT is_banco
        ),
        bruto AS (
            SELECT f.cd_cvm, f.trimestre, f.dt_ini_exerc, f.dt_fim_exerc,
                   f.valor_reais, d.dt_receb,
                   f.demonstrativo, f.origem
            FROM fatos_contabeis AS f
            JOIN elegiveis USING (cd_cvm)
            JOIN documentos AS d
              ON d.cd_cvm = f.cd_cvm AND d.conjunto = f.conjunto
             AND d.dt_refer = f.dt_refer AND d.versao = f.versao_documento
            WHERE f.demonstrativo LIKE 'DFC%'
              AND f.cd_conta = '{CONTA_FCO}'
              AND f.tipo_periodo = 'trimestral'
              AND f.valor_reais IS NOT NULL
        )
        SELECT cd_cvm, trimestre,
               min(dt_ini_exerc) AS dt_ini,
               max(dt_fim_exerc) AS dt_fim,
               max(valor_reais)  AS fco,
               min(dt_receb)     AS dt_receb,
               count(DISTINCT demonstrativo) AS metodos,
               count(DISTINCT origem)        AS origens
        FROM bruto
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    ).df().to_dict("records")


def carregar_duracoes(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Duração de cada linha de FCO trimestral, **antes** de qualquer `GROUP BY`.

    Medir duração sobre o grupo (companhia, trimestre) seria defeito do próprio
    auditor: com duas linhas de períodos distintos no mesmo grupo, o vão entre
    `min(dt_ini)` e `max(dt_fim)` infla para 121 ou 365 dias e acusa defeito
    onde há só agrupamento. Aqui cada linha responde pela sua própria duração.
    """
    return con.execute(
        f"""
        WITH elegiveis AS (
            SELECT cd_cvm FROM companhias
            WHERE plano_contas NOT LIKE 'll3_09_%' AND NOT is_banco
        )
        SELECT f.cd_cvm, f.trimestre, f.demonstrativo, f.origem,
               (f.dt_fim_exerc - f.dt_ini_exerc + 1) AS dias
        FROM fatos_contabeis AS f
        JOIN elegiveis USING (cd_cvm)
        WHERE f.demonstrativo LIKE 'DFC%'
          AND f.cd_conta = '{CONTA_FCO}'
          AND f.tipo_periodo = 'trimestral'
          AND f.valor_reais IS NOT NULL
        """
    ).df().to_dict("records")


def carregar_ativo(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Ativo total por companhia–trimestre, com `dt_receb` próprio.

    Vem de `fatos_contabeis`, e não da tabela `indicadores`, por uma razão de
    contrato: `indicadores` não guarda `dt_refer` nem `versao`, então não há como
    saber quando cada valor ficou disponível. Painel que se diz point-in-time e
    não é seria pior que nenhum.
    """
    return con.execute(
        f"""
        WITH elegiveis AS (
            SELECT cd_cvm FROM companhias
            WHERE plano_contas NOT LIKE 'll3_09_%' AND NOT is_banco
        )
        SELECT f.cd_cvm, f.trimestre,
               max(f.valor_reais) AS ativo,
               min(d.dt_receb)    AS dt_receb
        FROM fatos_contabeis AS f
        JOIN elegiveis USING (cd_cvm)
        JOIN documentos AS d
          ON d.cd_cvm = f.cd_cvm AND d.conjunto = f.conjunto
         AND d.dt_refer = f.dt_refer AND d.versao = f.versao_documento
        WHERE f.demonstrativo = 'BPA' AND f.cd_conta = '{CONTA_ATIVO}'
          AND f.valor_reais IS NOT NULL
        GROUP BY 1, 2
        """
    ).df().to_dict("records")


# --- G0 --------------------------------------------------------------------

def diagnosticar_escala(con: duckdb.DuckDBPyConnection) -> dict:
    """Por que o ativo salta 1.000×: caracteriza a causa, não decide o gate.

    **Não altera nenhum limiar do pré-registro** — G0.3 continua sendo a razão
    entre trimestres adjacentes. Isto responde à pergunta seguinte: o salto é
    defeito de escala declarada na fonte, ou redenominação real da companhia?

    O discriminante é `vl_conta`. Se o valor bruto segue contínuo e só a
    `escala` declarada muda, a companhia não mudou de unidade — o campo está
    errado, e `valor_reais` erra por 1.000× ao aplicá-lo fielmente. Se
    `vl_conta` salta junto, a mudança é real e `valor_reais` continua certo.
    """
    return con.execute(
        f"""
        WITH s AS (
            SELECT cd_cvm, dt_refer, max(escala) AS escala,
                   max(vl_conta) AS vl
            FROM fatos_contabeis
            WHERE demonstrativo = 'BPA' AND cd_conta = '{CONTA_ATIVO}'
            GROUP BY 1, 2
        ), p AS (
            SELECT cd_cvm, dt_refer, escala, vl,
                   lag(escala) OVER (PARTITION BY cd_cvm ORDER BY dt_refer) AS e0,
                   lag(vl)     OVER (PARTITION BY cd_cvm ORDER BY dt_refer) AS vl0
            FROM s
        )
        SELECT
          count(*) FILTER (WHERE escala <> e0) AS trocas_de_escala,
          count(*) FILTER (
            WHERE escala <> e0 AND vl0 > 0 AND abs(vl / vl0 - 1) < 0.5
          ) AS defeito_valor_bruto_continuo,
          count(*) FILTER (
            WHERE escala <> e0 AND vl0 > 0 AND abs(vl / vl0 - 1) >= 0.5
          ) AS redenominacao_aparentemente_real,
          count(DISTINCT cd_cvm) FILTER (
            WHERE escala <> e0 AND vl0 > 0 AND abs(vl / vl0 - 1) < 0.5
          ) AS companhias_com_defeito
        FROM p WHERE e0 IS NOT NULL
        """
    ).df().to_dict("records")[0]


def gate_g0(fco: list[dict], ativo: list[dict], duracoes: list[dict]) -> dict:
    """Integridade. Decisivo: reprova a rodada, não é diagnóstico."""
    somados = [r for r in fco if r["metodos"] > 1]

    fora_de_duracao = [
        {
            "cd_cvm": r["cd_cvm"], "trimestre": r["trimestre"],
            "dias": int(r["dias"]), "demonstrativo": r["demonstrativo"],
            "origem": r["origem"],
        }
        for r in duracoes
        if not DURACAO_MINIMA_DIAS <= r["dias"] <= DURACAO_MAXIMA_DIAS
    ]
    # Um grupo (companhia, trimestre) que contenha linha trimestral E linha de
    # duração semestral é pior que a linha solta: o `max(valor_reais)` da carga
    # pode eleger o semestre. Contado à parte porque é outro defeito.
    grupos_contaminados = sorted({
        (r["cd_cvm"], r["trimestre"]) for r in fora_de_duracao
    } & {
        (r["cd_cvm"], r["trimestre"]) for r in duracoes
        if DURACAO_MINIMA_DIAS <= r["dias"] <= DURACAO_MAXIMA_DIAS
    })

    por_cia: dict[str, list[dict]] = {}
    for r in sorted(ativo, key=lambda r: (r["cd_cvm"], ordinal_trimestre(r["trimestre"]))):
        por_cia.setdefault(r["cd_cvm"], []).append(r)
    saltos = []
    for cd, linhas in por_cia.items():
        for anterior, atual in zip(linhas, linhas[1:]):
            a, b = anterior["ativo"], atual["ativo"]
            if not a or not b:
                continue
            razao = max(abs(a), abs(b)) / min(abs(a), abs(b))
            if razao >= FATOR_DE_SALTO_DE_ESCALA:
                saltos.append({
                    "cd_cvm": cd, "de": anterior["trimestre"],
                    "para": atual["trimestre"], "razao": round(razao, 1),
                })

    fracao_saltos = len(saltos) / len(ativo) if ativo else 0.0
    return {
        "gate": "G0",
        "pergunta": "O dado é íntegro?",
        "papel": "decisivo",
        "observacoes_de_fco": len(fco),
        "observacoes_de_ativo": len(ativo),
        "g0_1_companhia_trimestre_com_os_dois_metodos": len(somados),
        "g0_2_fora_da_duracao_de_um_trimestre": len(fora_de_duracao),
        "g0_2_grupos_com_trimestre_e_periodo_mais_longo": len(grupos_contaminados),
        "g0_2_exemplos": fora_de_duracao[:10],
        "g0_2_duracoes_distintas": sorted(
            {r["dias"] for r in fora_de_duracao}
        ),
        "g0_3_saltos_de_escala": len(saltos),
        "g0_3_fracao": round(fracao_saltos, 6),
        "g0_3_exemplos": saltos[:10],
        "limiar": (
            f"0 somas de método duplo · 0 fora de "
            f"{DURACAO_MINIMA_DIAS}–{DURACAO_MAXIMA_DIAS} dias · "
            f"<= {G0_TOLERANCIA_ESCALA:.1%} de saltos de escala"
        ),
        "aprovado": (
            not somados
            and not fora_de_duracao
            and fracao_saltos <= G0_TOLERANCIA_ESCALA
        ),
    }


# --- construção da amostra -------------------------------------------------

def construir_amostra(fco: list[dict], ativo: list[dict]) -> tuple[list[dict], dict]:
    """Um par (companhia, D) por documento recebido. D = `dt_receb`.

    **A grade de decisão é a chegada do formulário, não o fim do trimestre.**
    Em cada D entram só os trimestres com `dt_receb <= D`; o rótulo sai dos
    quatro trimestres cujo início é posterior a D.
    """
    por_cia: dict[str, list[dict]] = {}
    for r in fco:
        por_cia.setdefault(r["cd_cvm"], []).append(r)
    ativo_por_cia: dict[str, list[dict]] = {}
    for r in ativo:
        ativo_por_cia.setdefault(r["cd_cvm"], []).append(r)

    amostra: list[dict] = []
    descarte = {
        "sem_quatro_trimestres_de_rotulo": 0,
        "fco_ttm_nao_positivo": 0,
        "sem_ativo_disponivel": 0,
        "sem_historico_para_sd8": 0,
        "q1_nao_e_o_primeiro_apos_D": 0,
    }

    for cd, linhas in por_cia.items():
        linhas = sorted(linhas, key=lambda r: ordinal_trimestre(r["trimestre"]))
        ativos = sorted(
            ativo_por_cia.get(cd, []),
            key=lambda r: ordinal_trimestre(r["trimestre"]),
        )
        for ancora in linhas:
            d = ancora["dt_receb"]
            # G1.1: passado = só o que chegou até D.
            passado = [r for r in linhas if r["dt_receb"] <= d]
            # G1.2/G1.3: futuro = trimestres cujo INÍCIO é posterior a D.
            futuro = [r for r in linhas if r["dt_ini"] > d]
            futuro.sort(key=lambda r: ordinal_trimestre(r["trimestre"]))

            if len(passado) < JANELA_SD + 1:
                descarte["sem_historico_para_sd8"] += 1
                continue
            if len(futuro) < 4:
                descarte["sem_quatro_trimestres_de_rotulo"] += 1
                continue

            rotulo = futuro[:4]
            # G1.2 exata: os quatro têm de ser consecutivos a partir de q1.
            ordens = [ordinal_trimestre(r["trimestre"]) for r in rotulo]
            if ordens != list(range(ordens[0], ordens[0] + 4)):
                descarte["q1_nao_e_o_primeiro_apos_D"] += 1
                continue

            ultimos4 = passado[-4:]
            fco_ttm = sum(r["fco"] for r in ultimos4)
            if fco_ttm <= 0:
                descarte["fco_ttm_nao_positivo"] += 1
                continue

            disponiveis = [r for r in ativos if r["dt_receb"] <= d]
            if not disponiveis:
                descarte["sem_ativo_disponivel"] += 1
                continue
            ativo_em_d = disponiveis[-1]["ativo"]
            if not ativo_em_d or ativo_em_d <= 0:
                descarte["sem_ativo_disponivel"] += 1
                continue

            serie = [r["fco"] for r in passado[-JANELA_SD:]]
            sd8 = statistics.stdev(serie)
            negativos = sum(1 for v in serie if v < 0)

            s1 = rotulo[0]["fco"] + rotulo[1]["fco"]
            s2 = rotulo[2]["fco"] + rotulo[3]["fco"]

            amostra.append({
                "cd_cvm": cd,
                "D": str(d),
                "trimestre_ancora": ancora["trimestre"],
                "q1": rotulo[0]["trimestre"],
                "y": 1 if (s1 < 0 and s2 < 0) else 0,
                "fco_ttm_em_D": fco_ttm,
                "sd8_fco_isolado": sd8,
                # Sem `sd8` não há distância em desvios; `inf` diria "infinitamente
                # longe de zero", que é o oposto do que série constante significa
                # para este alvo. Fica `None` e a observação sai do componente.
                "fco_ttm_sobre_sd8": (fco_ttm / sd8) if sd8 else None,
                "fco_ttm_sobre_ativo": fco_ttm / ativo_em_d,
                "ativo_total_em_D": ativo_em_d,
                "trimestres_com_fco_negativo_nos_ultimos_8": negativos,
            })

    return amostra, descarte


# --- T1 --------------------------------------------------------------------

def amplitude_por_quintis(valores: list[float], eventos: list[int]) -> dict:
    """Amplitude da taxa de evento entre quintis, com empates AGRUPADOS.

    **Cortar por posição atribui amplitude máxima a variável constante** quando
    os rótulos vêm agrupados: o corte cai no meio de um bloco de valores iguais
    e separa em "quintis" observações indistinguíveis. Foi o achado C1 do
    B-DFC-01J. Aqui o corte se estende até o fim do grupo de valor empatado, e
    variável constante devolve exatamente UM grupo, com amplitude 0,0.
    """
    if len(valores) < MINIMO_DE_OBSERVACOES:
        raise AmostraInsuficiente(
            f"{len(valores)} observações: menos que o mínimo "
            f"{MINIMO_DE_OBSERVACOES} para quintis."
        )
    ordenados = sorted(zip(valores, eventos), key=lambda t: t[0])
    tamanho = len(ordenados) / 5
    faixas: list[dict] = []
    inicio = 0
    for q in range(5):
        if inicio >= len(ordenados):
            break
        fim = max(int((q + 1) * tamanho), inicio + 1)
        while fim < len(ordenados) and ordenados[fim][0] == ordenados[fim - 1][0]:
            fim += 1
        recorte = ordenados[inicio:fim]
        faixas.append({
            "quintil": len(faixas) + 1,
            "n": len(recorte),
            "valor_minimo": recorte[0][0],
            "valor_maximo": recorte[-1][0],
            "taxa": statistics.fmean(e for _, e in recorte),
        })
        inicio = fim
    taxas = [f["taxa"] for f in faixas]
    return {
        "amplitude": max(taxas) - min(taxas),
        "faixas": faixas,
        "grupos": len(faixas),
    }


def _bootstrap_amplitude(amostra: list[dict], coluna: str) -> dict:
    """IC da amplitude reamostrando COMPANHIAS inteiras, nunca observações.

    Trimestres do mesmo emissor não são réplicas independentes (§4.4 regra 8).
    Reamostrar observações produziria um IC estreito e falso.
    """
    por_cia: dict[str, list[dict]] = {}
    for r in amostra:
        if r[coluna] is not None:
            por_cia.setdefault(r["cd_cvm"], []).append(r)
    chaves = list(por_cia)
    aleatorio = random.Random(SEMENTE)
    medidas: list[float] = []
    for _ in range(REAMOSTRAGENS):
        sorteadas = [aleatorio.choice(chaves) for _ in chaves]
        linhas = [r for k in sorteadas for r in por_cia[k]]
        if len(linhas) < MINIMO_DE_OBSERVACOES:
            continue
        try:
            medidas.append(amplitude_por_quintis(
                [r[coluna] for r in linhas], [r["y"] for r in linhas]
            )["amplitude"])
        except AmostraInsuficiente:
            continue
    if not medidas:
        raise AmostraInsuficiente(
            f"bootstrap de {coluna} não produziu nenhuma reamostragem válida."
        )
    medidas.sort()
    excede = sum(1 for m in medidas if m > T1_AMPLITUDE) / len(medidas)
    return {
        "reamostragens_validas": len(medidas),
        "ic95_inferior": round(medidas[int(0.025 * len(medidas))], 4),
        "ic95_superior": round(medidas[int(0.975 * len(medidas)) - 1], 4),
        "probabilidade_de_exceder_o_limiar": round(excede, 4),
    }


def teste_t1(amostra: list[dict]) -> dict:
    """T1 sobre os SEIS componentes do §6. A lista não pode encolher."""
    companhias = {r["cd_cvm"] for r in amostra}
    if len(companhias) < MINIMO_DE_COMPANHIAS:
        raise AmostraInsuficiente(
            f"{len(companhias)} companhias: menos que o mínimo "
            f"{MINIMO_DE_COMPANHIAS}."
        )
    resultados: dict[str, dict] = {}
    for coluna in COMPONENTES_T1:
        usaveis = [r for r in amostra if r[coluna] is not None]
        medida = amplitude_por_quintis(
            [r[coluna] for r in usaveis], [r["y"] for r in usaveis]
        )
        entrada = {
            "amplitude": round(medida["amplitude"], 4),
            "grupos_de_quintil": medida["grupos"],
            "observacoes_usadas": len(usaveis),
            "taxa_por_quintil": [round(f["taxa"], 4) for f in medida["faixas"]],
            "n_por_quintil": [f["n"] for f in medida["faixas"]],
        }
        if medida["amplitude"] >= T1_AMPLITUDE:
            entrada["veredito"] = "REPROVA"
        elif medida["amplitude"] >= T1_ZONA_CINZENTA:
            # Zona cinzenta do §6: o viés da amplitude é PARA CIMA, então passar
            # raspando não é aprovação sem medir a incerteza.
            entrada["bootstrap"] = _bootstrap_amplitude(amostra, coluna)
            entrada["veredito"] = (
                "INDECIDIVEL"
                if entrada["bootstrap"]["probabilidade_de_exceder_o_limiar"]
                > T1_PROB_MAXIMA
                else "PASSA"
            )
        else:
            entrada["veredito"] = "PASSA"
        resultados[coluna] = entrada

    piores = sorted(
        resultados.items(), key=lambda kv: kv[1]["amplitude"], reverse=True
    )
    vereditos = {v["veredito"] for v in resultados.values()}
    return {
        "teste": "T1",
        "pergunta": "O alvo fabrica o próprio baseline?",
        "papel": "decisivo",
        "limiar": f"amplitude < {T1_AMPLITUDE} em TODOS os componentes",
        "componentes": resultados,
        "componente_com_maior_amplitude": piores[0][0],
        "maior_amplitude": piores[0][1]["amplitude"],
        "aprovado": vereditos == {"PASSA"},
        "indecidivel": "INDECIDIVEL" in vereditos and "REPROVA" not in vereditos,
    }


# --- T2 --------------------------------------------------------------------

def _auc(escores: list[float], eventos: list[int]) -> float | None:
    """AUC por contagem de pares concordantes, com meio ponto para empate."""
    positivos = [s for s, y in zip(escores, eventos) if y == 1]
    negativos = [s for s, y in zip(escores, eventos) if y == 0]
    if not positivos or not negativos:
        return None
    ganhos = sum(
        1.0 if p > n else 0.5 if p == n else 0.0
        for p in positivos for n in negativos
    )
    return ganhos / (len(positivos) * len(negativos))


def teste_t2(amostra: list[dict], coluna: str, sentido: int) -> dict:
    """Lacuna entre AUC agregada e AUC intra-companhia."""
    usaveis = [r for r in amostra if r[coluna] is not None]
    escores = [sentido * r[coluna] for r in usaveis]
    if len(set(escores)) <= 1:
        raise EscoreDegenerado(
            f"{coluna} é constante nesta amostra: AUC 0,5 por construção e "
            "lacuna zero. Aprovar seria aprovar por ausência de poder."
        )
    eventos = [r["y"] for r in usaveis]
    agregada = _auc(escores, eventos)

    por_cia: dict[str, list[tuple[float, int]]] = {}
    for s, y, r in zip(escores, eventos, usaveis):
        por_cia.setdefault(r["cd_cvm"], []).append((s, y))
    intra, com_dois_rotulos = [], 0
    for pares in por_cia.values():
        if len({y for _, y in pares}) < 2:
            continue
        com_dois_rotulos += 1
        valor = _auc([s for s, _ in pares], [y for _, y in pares])
        if valor is not None:
            intra.append(valor)
    if not intra:
        raise AmostraInsuficiente(
            "nenhuma companhia tem os dois rótulos: AUC intra não é medível."
        )
    media_intra = statistics.fmean(intra)
    lacuna = (agregada or 0.0) - media_intra
    return {
        "teste": "T2",
        "pergunta": "Há sinal temporal ou só ordenação de emissor?",
        "papel": "decisivo",
        "escore": coluna,
        "auc_agregada": round(agregada, 4) if agregada else None,
        "auc_intra_companhia": round(media_intra, 4),
        "companhias_com_os_dois_rotulos": com_dois_rotulos,
        "companhias_na_amostra": len(por_cia),
        "lacuna": round(lacuna, 4),
        "limiar": f"< {T2_LACUNA}",
        "aprovado": lacuna < T2_LACUNA,
    }


# --- baselines -------------------------------------------------------------

def medir_baselines(amostra: list[dict]) -> dict:
    """Os quatro triviais do §8, ANTES de qualquer componente aprendido."""
    eventos = [r["y"] for r in amostra]
    taxa_base = statistics.fmean(eventos)
    tabela: dict[str, dict] = {
        "B0_classe_majoritaria": {
            "descricao": "Prever sempre 'não vai consumir caixa'",
            "acerto": round(1 - taxa_base, 4),
            "cobertura_de_direcao": 0.0,
            "observacao": (
                "Escore constante: abstém da ordenação, então AUC não se aplica. "
                "Publicar cobertura ao lado do acerto é exigência do §3.11."
            ),
        },
    }
    for nome, (coluna, sentido) in BASELINES.items():
        usaveis = [r for r in amostra if r[coluna] is not None]
        escores = [sentido * r[coluna] for r in usaveis]
        alvos = [r["y"] for r in usaveis]
        auc = _auc(escores, alvos)
        ordenados = sorted(zip(escores, alvos), reverse=True)
        corte = max(1, len(ordenados) // 10)
        tabela[nome] = {
            "coluna": coluna,
            "sentido": sentido,
            "observacoes": len(usaveis),
            "auc_agregada": round(auc, 4) if auc else None,
            "precisao_no_top_10pct": round(
                statistics.fmean(y for _, y in ordenados[:corte]), 4
            ),
            "lift_sobre_a_taxa_base": round(
                statistics.fmean(y for _, y in ordenados[:corte]) / taxa_base, 3
            ) if taxa_base else None,
        }
    melhor = max(
        (n for n in BASELINES),
        key=lambda n: tabela[n]["auc_agregada"] or 0.0,
    )
    return {
        "taxa_base_do_evento": round(taxa_base, 4),
        "baselines": tabela,
        "melhor_trivial": melhor,
        "nota": (
            "Nenhum componente aprendido foi executado. Para autorizar um, o "
            "desafiante tem de superar o melhor trivial por margem cujo IC 95% "
            "pareado exclua zero (§8 do pré-registro)."
        ),
    }


# --- orquestração ----------------------------------------------------------

def executar() -> dict:
    con = duckdb.connect(str(PAINEL), read_only=True)
    try:
        fco = carregar_fco(con)
        ativo = carregar_ativo(con)
        duracoes = carregar_duracoes(con)
        escala = diagnosticar_escala(con)
    finally:
        con.close()

    cadeia: list[dict] = []
    decisivo = None

    def _medir(nome: str, funcao):
        nonlocal decisivo
        try:
            resultado = funcao()
        except (AmostraInsuficiente, EscoreDegenerado) as erro:
            # Amostra insuficiente num teste NÃO apaga os anteriores: entra na
            # cadeia como reprovado com o motivo.
            resultado = {
                "teste": nome, "aprovado": False,
                "reprova_em_aberto": str(erro),
            }
        cadeia.append(resultado)
        if decisivo is None and not resultado["aprovado"]:
            decisivo = nome
        return resultado

    g0 = _medir("G0", lambda: gate_g0(fco, ativo, duracoes))
    g0["diagnostico_de_escala"] = escala
    if not g0["aprovado"]:
        # G0 é decisivo: a rodada para aqui, e as observações reprovadas NÃO são
        # removidas para salvar o teste (§4.4 regra 9). Mas o §4 do pré-registro
        # exige que a quarentena seja **publicada e congelada** — então o
        # artefato é gravado com o motivo, em vez de só ir para a tela.
        return {
            "candidato": "Rank 3-B — início de consumo operacional persistente",
            "pre_registro": (
                "resultados/pre_registro_rank03b_consumo_operacional_2026-09-11.md"
            ),
            "pre_registro_sha256": (
                "fbae30cce2bde9b3ece5ccf254e300ce99ba11946568720441193b0a3ac644cc"
            ),
            "modelo_carregado": False,
            "cadeia": cadeia,
            "primeiro_reprovado": "G0",
            "veredito": "REPROVADO EM G0/G1",
            "quarentena": (
                "As observações reprovadas por G0.3 NÃO foram removidas e "
                "NENHUM teste posterior foi medido. Nada de T1, T2 ou baseline "
                "existe nesta rodada — a rodada está invalidada. Retomar exige "
                "adjudicar a escala contra a fonte e um pré-registro novo."
            ),
        }

    amostra, descarte = construir_amostra(fco, ativo)
    companhias = sorted({r["cd_cvm"] for r in amostra})
    g1 = {
        "gate": "G1",
        "pergunta": "É point-in-time E no horizonte exato?",
        "papel": "decisivo",
        "observacoes": len(amostra),
        "companhias": len(companhias),
        "descartes": descarte,
        "construcao": (
            "D = dt_receb de cada documento. Features só de trimestres com "
            "dt_receb <= D; rótulo só de trimestres com dt_ini > D; os quatro "
            "consecutivos a partir de q1, conferidos por ordinal."
        ),
        "limiar": "100% por construção da amostra",
        "aprovado": bool(amostra),
    }
    cadeia.append(g1)
    if decisivo is None and not g1["aprovado"]:
        decisivo = "G1"

    t1 = _medir("T1", lambda: teste_t1(amostra))
    escore_t2, sentido_t2 = BASELINES[
        max(BASELINES, key=lambda n: 1 if n == "B1_fco_sobre_sd8" else 0)
    ]
    _medir("T2", lambda: teste_t2(amostra, escore_t2, sentido_t2))

    try:
        baselines = medir_baselines(amostra)
    except (ZeroDivisionError, statistics.StatisticsError) as erro:
        baselines = {"reprova_em_aberto": str(erro)}

    aprovados = all(x["aprovado"] for x in cadeia)
    indecidivel = t1.get("indecidivel") or any(
        "reprova_em_aberto" in x for x in cadeia
    )
    if aprovados:
        veredito = "PRONTO PARA CHALLENGER"
    elif not g0["aprovado"] or not g1["aprovado"]:
        veredito = "REPROVADO EM G0/G1"
    elif indecidivel and t1["aprovado"]:
        veredito = "INDECIDIVEL"
    else:
        veredito = "REJEITADO"

    return {
        "candidato": "Rank 3-B — início de consumo operacional persistente",
        "pre_registro": (
            "resultados/pre_registro_rank03b_consumo_operacional_2026-09-11.md"
        ),
        "pre_registro_sha256": (
            "fbae30cce2bde9b3ece5ccf254e300ce99ba11946568720441193b0a3ac644cc"
        ),
        "modelo_carregado": False,
        "populacao": {
            "observacoes": len(amostra),
            "companhias": len(companhias),
            "taxa_do_evento": round(
                statistics.fmean(r["y"] for r in amostra), 4
            ) if amostra else None,
            "criterio_de_exclusao": (
                "plano_contas LIKE 'll3_09_%' OU is_banco — exclusão "
                "estrutural por plano de contas de instituição financeira; "
                "setor está preenchido em 5 de 741 e NÃO foi usado"
            ),
        },
        "cadeia": cadeia,
        "baselines_triviais": baselines,
        "primeiro_reprovado": decisivo,
        "veredito": veredito,
    }


def principal() -> int:
    relatorio = executar()
    DESTINO.mkdir(parents=True, exist_ok=True)
    (DESTINO / "auditoria.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    if "populacao" not in relatorio:
        g0 = relatorio["cadeia"][0]
        print(f"Candidato: {relatorio['candidato']}")
        print(f"  REPROVA G0: {g0['pergunta']}")
        print(f"    saltos de escala: {g0['g0_3_saltos_de_escala']} "
              f"({g0['g0_3_fracao']:.2%}), limiar {G0_TOLERANCIA_ESCALA:.2%}")
        d = g0["diagnostico_de_escala"]
        print(f"    causa: {d['defeito_valor_bruto_continuo']} de "
              f"{d['trocas_de_escala']} trocas de escala têm valor bruto "
              f"CONTÍNUO, em {d['companhias_com_defeito']} companhias")
        print(f"VEREDITO: {relatorio['veredito']}")
        print("  Nada de T1/T2/baseline foi medido — rodada invalidada.")
        return 2
    pop = relatorio["populacao"]
    print(f"Candidato: {relatorio['candidato']}")
    print(f"População: {pop['observacoes']} obs · {pop['companhias']} companhias "
          f"· taxa do evento {pop['taxa_do_evento']}")
    for etapa in relatorio["cadeia"]:
        nome = etapa.get("gate") or etapa.get("teste")
        marca = "APROVA " if etapa["aprovado"] else "REPROVA"
        extra = etapa.get("reprova_em_aberto", "")
        print(f"  {marca} {nome}: {etapa.get('pergunta', '')} {extra}"[:110])
    t1 = next((x for x in relatorio["cadeia"] if x.get("teste") == "T1"), None)
    if t1 and "componentes" in t1:
        print("  T1 por componente:")
        for nome, dados in sorted(
            t1["componentes"].items(), key=lambda kv: -kv[1]["amplitude"]
        ):
            print(f"    {dados['amplitude']:.4f}  {dados['veredito']:<11} {nome}")
    print(f"VEREDITO: {relatorio['veredito']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
