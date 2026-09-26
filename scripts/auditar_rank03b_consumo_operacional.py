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

import calendar
import datetime
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
#: Contrato B1.2 (conferência de 15/09): um IC95% percentil só existe se cada
#: cauda de 2,5% contiver ao menos uma reamostragem válida — ⌈1/0,025⌉ = 40.
#: Deriva do nível de 95% registrado, não do dado.
MINIMO_DE_REAMOSTRAGENS_VALIDAS = math.ceil(1 / 0.025)

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
    """FCO trimestral, **uma entrada por LINHA-FONTE**, nunca por grupo.

    Contrato R1.1 (achado R1 da revisão de 12/09). A versão anterior agrupava
    por `(cd_cvm, trimestre)` e tomava `max(valor_reais)`, `min(dt_receb)`,
    `min(dt_ini_exerc)` e `max(dt_fim_exerc)` **independentemente** — os quatro
    atributos podiam vir de linhas diferentes, e a observação resultante não
    correspondia a fato nenhum. Medido: 4 grupos de FCO e 26 de ativo recebiam
    data anterior à chegada da linha que continha o valor. Em `023507/1T2015`,
    `+19.075.000` (recebido em 05/05/2015) saía com disponibilidade de
    **21/10/2014**, herdada de outra linha rotulada com o mesmo trimestre.

    Agora valor, período e procedência viajam juntos, e a escolha do vintage é
    feita em `D` por `vigente_em` — point-in-time em vez de retroativa.

    Duas decisões que permanecem, cada uma de defeito medido:

    - **`tipo_periodo='trimestral'`**: o acumulado somaria o mesmo caixa várias
      vezes numa janela móvel.
    - **`dt_receb` vem de `documentos`**, não de `dt_refer`. Usar `dt_refer`
      como data de publicação enxerga o formulário antes de ele existir: o
      atraso mediano é de 44 dias no ITR e 83 na DFP (AGENTS.md §3.13).
    """
    return con.execute(
        f"""
        WITH elegiveis AS (
            SELECT cd_cvm FROM companhias
            WHERE plano_contas NOT LIKE 'll3_09_%' AND NOT is_banco
        )
        SELECT f.cd_cvm, f.trimestre,
               f.dt_ini_exerc AS dt_ini, f.dt_fim_exerc AS dt_fim,
               f.valor_reais  AS fco,   d.dt_receb,
               f.demonstrativo, f.origem, f.versao_documento AS versao
        FROM fatos_contabeis AS f
        JOIN elegiveis USING (cd_cvm)
        JOIN documentos AS d
          ON d.cd_cvm = f.cd_cvm AND d.conjunto = f.conjunto
         AND d.dt_refer = f.dt_refer AND d.versao = f.versao_documento
        WHERE f.demonstrativo LIKE 'DFC%'
          AND f.cd_conta = '{CONTA_FCO}'
          AND f.tipo_periodo = 'trimestral'
          AND f.valor_reais IS NOT NULL
        ORDER BY f.cd_cvm, f.trimestre, d.dt_receb, f.versao_documento,
                 f.demonstrativo, f.dt_ini_exerc
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
        ORDER BY f.cd_cvm, f.trimestre, f.demonstrativo, f.origem, dias
        """
    ).df().to_dict("records")


#: G0.4 do §4 do pré-registro: as contas cujo `valor_reais` não pode ser nulo,
#: com o predicado que as identifica. Mesmo recorte dos carregadores — sem o
#: filtro de nulo, que é justamente o que se quer medir.
CONTAS_REQUERIDAS = {
    "fco": (
        f"f.demonstrativo LIKE 'DFC%' AND f.cd_conta = '{CONTA_FCO}' "
        "AND f.tipo_periodo = 'trimestral'"
    ),
    "ativo": f"f.demonstrativo = 'BPA' AND f.cd_conta = '{CONTA_ATIVO}'",
}


def carregar_nulos(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, int]]:
    """G0.4: nulos nas contas usadas, medidos **sem** o filtro de nulo.

    **Correção de 2026-09-16 (contrato G4.1).** O §4 do pré-registro congela
    G0.4 desde 11/09 — *`valor_reais` nunca nulo nas contas usadas, 0 nulos* —
    e o código **nunca a implementou**: `gate_g0` publicava contador para G0.1,
    G0.2 e G0.3 e nenhum para G0.4. E não bastaria acrescentá-lo lá dentro: os
    três carregadores filtram `valor_reais IS NOT NULL`, então um contador
    alimentado por eles seria incapaz de ver um nulo **por construção** — guarda
    vazia, não guarda frouxa.

    Medido em 2026-09-16, antes desta correção: FCO `6.01` com 22.034 linhas e
    **0** nulos; Ativo `1` com 22.471 linhas e **0** nulos. Implementar G0.4
    portanto não muda veredito nenhum — o que muda é a guarda deixar de aprovar
    por ausência de medição (§4.4 regra 4).
    """
    medidas: dict[str, dict[str, int]] = {}
    for nome, condicao in CONTAS_REQUERIDAS.items():
        linhas, nulos = con.execute(
            f"""
            WITH elegiveis AS (
                SELECT cd_cvm FROM companhias
                WHERE plano_contas NOT LIKE 'll3_09_%' AND NOT is_banco
            )
            SELECT count(*),
                   coalesce(sum(CASE WHEN f.valor_reais IS NULL THEN 1 ELSE 0 END), 0)
            FROM fatos_contabeis AS f
            JOIN elegiveis USING (cd_cvm)
            WHERE {condicao}
            """
        ).fetchone()
        medidas[nome] = {"linhas": int(linhas), "nulos": int(nulos)}
    return medidas


def carregar_ativo(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Ativo total, **uma entrada por LINHA-FONTE** (contrato R1.1).

    Vem de `fatos_contabeis`, e não da tabela `indicadores`, por uma razão de
    contrato: `indicadores` não guarda `dt_refer` nem `versao`, então não há
    como saber quando cada valor ficou disponível. Painel que se diz
    point-in-time e não é seria pior que nenhum.

    Como no FCO, o agrupamento saiu daqui: `max(valor_reais)` com
    `min(dt_receb)` produzia, em 26 grupos, um valor com data de disponibilidade
    que não era a dele.
    """
    return con.execute(
        f"""
        WITH elegiveis AS (
            SELECT cd_cvm FROM companhias
            WHERE plano_contas NOT LIKE 'll3_09_%' AND NOT is_banco
        )
        SELECT f.cd_cvm, f.trimestre, f.valor_reais AS ativo, d.dt_receb,
               f.versao_documento AS versao, f.demonstrativo,
               f.dt_ini_exerc AS dt_ini, f.dt_fim_exerc AS dt_fim
        FROM fatos_contabeis AS f
        JOIN elegiveis USING (cd_cvm)
        JOIN documentos AS d
          ON d.cd_cvm = f.cd_cvm AND d.conjunto = f.conjunto
         AND d.dt_refer = f.dt_refer AND d.versao = f.versao_documento
        WHERE f.demonstrativo = 'BPA' AND f.cd_conta = '{CONTA_ATIVO}'
          AND f.valor_reais IS NOT NULL
        ORDER BY f.cd_cvm, f.trimestre, d.dt_receb, f.versao_documento,
                 f.demonstrativo, f.dt_ini_exerc
        """
    ).df().to_dict("records")


def vigente_em(linhas: list[dict], d) -> dict | None:
    """A linha vigente em `D`: a mais recente entre as já recebidas.

    Contrato R1.2/R1.3. **A escolha do vintage acontece AQUI, na decisão, e não
    na carga** — é o que a torna point-in-time em vez de retroativa. A linha
    devolvida é inteira: valor, período, recepção e procedência saem juntos,
    nunca recombinados.

    Desempate cego ao desfecho, nesta ordem: maior `versao`, depois
    `demonstrativo` alfabético, depois `dt_ini`. Nenhum critério olha o valor
    nem o rótulo — escolher pelo valor foi exatamente o defeito corrigido.
    """
    disponiveis = [r for r in linhas if r["dt_receb"] <= d]
    if not disponiveis:
        return None
    return max(
        disponiveis,
        key=lambda r: (
            r["dt_receb"], r.get("versao") or 0,
            r.get("demonstrativo") or "", r.get("dt_ini"),
        ),
    )


# --- G0 --------------------------------------------------------------------

def diagnosticar_escala(con: duckdb.DuckDBPyConnection) -> dict:
    """Por que o ativo salta 1.000×: caracteriza a causa, não decide o gate.

    **Não altera nenhum limiar do pré-registro.** G0.3 continua sendo a razão
    entre trimestres adjacentes. Isto responde à pergunta seguinte: o salto é
    defeito de escala declarada na fonte, ou redenominação real da companhia?

    O discriminante é `vl_conta`. Se o valor bruto segue contínuo e só a
    `escala` declarada muda, a companhia não mudou de unidade — o campo está
    errado, e `valor_reais` erra por 1.000× ao aplicá-lo fielmente.

    **Correção do achado R7 (revisão de 12/09).** Três precisões que a versão
    anterior não fazia, e que mudam a leitura:

    1. **O que se conta são TRANSIÇÕES, não linhas nem células.** A entrada e a
       saída de uma única célula problemática produzem **dois** sinais. Dizer
       "123 linhas erradas" confunde transição, linha-fonte e adjudicação.
    2. **Há uma terceira classe**, além de contínuo e redenominação: bruto
       anterior **zero**, em que a razão não é definida. É por isso que
       123 + 13 não somava 137.
    3. **Universo e adjacência mudam o número.** Os quatro recortes saem
       publicados lado a lado, para que ninguém escolha o mais favorável
       depois de ver o resultado.

    **Nada aqui é adjudicação.** Continuidade do bruto é *suspeita*, não prova
    de qual valor deve ser corrigido — a função não lê uma segunda demonstração
    para decidir célula por célula. A palavra "aparentemente" na classe de
    redenominação é obrigatória.
    """
    def _medir(universo: str, so_adjacentes: bool) -> dict:
        filtro = (
            "JOIN companhias c USING (cd_cvm) "
            "WHERE c.plano_contas NOT LIKE 'll3_09_%' AND NOT c.is_banco AND "
            if universo == "candidato" else "WHERE "
        )
        linhas = con.execute(
            f"""
            -- `ORDER BY` é por `dt_refer`, que é data. Ordenar `trimestre`
            -- como TEXTO inverte o tempo sem levantar erro nenhum:
            -- '1T2020' vem antes de '2T2019'. É a armadilha que o docstring
            -- de `ordinal_trimestre` documenta, e que derrubou esta função
            -- numa primeira tentativa de reescrita.
            WITH s AS (
                SELECT f.cd_cvm, f.trimestre, f.dt_refer,
                       max(f.escala) AS escala, max(f.vl_conta) AS vl
                FROM fatos_contabeis AS f {filtro}
                  f.demonstrativo = 'BPA' AND f.cd_conta = '{CONTA_ATIVO}'
                GROUP BY 1, 2, 3
            ), p AS (
                SELECT cd_cvm, trimestre, escala, vl,
                       lag(escala) OVER (PARTITION BY cd_cvm ORDER BY dt_refer) AS e0,
                       lag(vl) OVER (PARTITION BY cd_cvm ORDER BY dt_refer) AS vl0,
                       lag(trimestre) OVER (PARTITION BY cd_cvm ORDER BY dt_refer) AS t0
                FROM s
            )
            SELECT cd_cvm, t0, trimestre, escala, e0, vl, vl0
            FROM p WHERE e0 IS NOT NULL AND escala <> e0
            """
        ).df().to_dict("records")
        if so_adjacentes:
            linhas = [
                r for r in linhas
                if ordinal_trimestre(r["trimestre"]) - ordinal_trimestre(r["t0"]) == 1
            ]
        continuo = [r for r in linhas if r["vl0"] and abs(r["vl"] / r["vl0"] - 1) < 0.5]
        redenom = [r for r in linhas if r["vl0"] and abs(r["vl"] / r["vl0"] - 1) >= 0.5]
        indefinido = [r for r in linhas if not r["vl0"]]
        return {
            "transicoes_de_escala": len(linhas),
            "bruto_continuo_suspeita_de_defeito": len(continuo),
            "redenominacao_aparentemente_real": len(redenom),
            "razao_indefinida_bruto_anterior_zero": len(indefinido),
            "companhias_com_transicao_suspeita": len({r["cd_cvm"] for r in continuo}),
        }

    recortes = {
        "painel_inteiro_sucessivos": _medir("painel", False),
        "painel_inteiro_adjacentes": _medir("painel", True),
        "universo_do_candidato_sucessivos": _medir("candidato", False),
        "universo_do_candidato_adjacentes": _medir("candidato", True),
    }
    return {
        "recortes": recortes,
        "recorte_pertinente_a_G0": "universo_do_candidato_adjacentes",
        "leitura": (
            "TRANSIÇÕES suspeitas, não linhas erradas nem células adjudicadas. "
            "Entrada e saída de uma célula produzem dois sinais. Continuidade "
            "do valor bruto é suspeita, não prova de qual valor corrigir: "
            "adjudicar exige ler uma segunda demonstração, caso a caso."
        ),
    }


def gate_g0(
    fco: list[dict], ativo: list[dict], duracoes: list[dict],
    nulos: dict[str, dict[str, int]],
) -> dict:
    """Integridade. Decisivo: reprova a rodada, não é diagnóstico.

    `nulos` é a medição de G0.4 feita por `carregar_nulos`, e é **exigida**
    (contrato G4.2). A função continua pura — recebe listas e dicionários, nunca
    a conexão —, que é o que sustenta as contraprovas de G0.1 a G0.4.
    """
    # G0.1 — `DFC_MD` e `DFC_MI` no mesmo (companhia, trimestre). A contagem
    # agora sai das linhas, porque a carga deixou de agrupar (contrato R1.1);
    # o critério e o limiar são os mesmos do §4 do pré-registro.
    metodos_por_grupo: dict[tuple[str, str], set[str]] = {}
    for r in fco:
        metodos_por_grupo.setdefault(
            (r["cd_cvm"], r["trimestre"]), set()
        ).add(r["demonstrativo"])
    somados = sorted(k for k, v in metodos_por_grupo.items() if len(v) > 1)

    fora_de_duracao = [
        {
            "cd_cvm": r["cd_cvm"], "trimestre": r["trimestre"],
            "dias": int(r["dias"]), "demonstrativo": r["demonstrativo"],
            "origem": r["origem"],
        }
        for r in duracoes
        if not DURACAO_MINIMA_DIAS <= r["dias"] <= DURACAO_MAXIMA_DIAS
    ]
    # Grupo que contém linha de duração válida E linha anômala. **Correção do
    # achado R6:** a versão anterior descrevia estes grupos como contaminados
    # por SEMESTRE. Medido, são períodos CURTOS — 12, 31 e 41 dias —, e nenhum
    # dos nove semestres derivados aparece aqui. Consertar só a derivação
    # semestral não toca nestes grupos.
    grupos_contaminados = sorted({
        (r["cd_cvm"], r["trimestre"]) for r in fora_de_duracao
    } & {
        (r["cd_cvm"], r["trimestre"]) for r in duracoes
        if DURACAO_MINIMA_DIAS <= r["dias"] <= DURACAO_MAXIMA_DIAS
    })

    por_cia: dict[str, list[dict]] = {}
    for r in sorted(ativo, key=lambda r: (r["cd_cvm"], ordinal_trimestre(r["trimestre"]))):
        por_cia.setdefault(r["cd_cvm"], []).append(r)
    # **Correção do achado R6.** O §4 do pré-registro diz "entre trimestres
    # ADJACENTES", e esta função comparava linhas consecutivas na lista
    # ordenada — o que não é a mesma coisa quando a companhia tem lacuna.
    # Medido: dos 136 pares, quatro distavam 3, 5 e até 14 trimestres.
    # Exigir adjacência é implementar o contrato congelado, não afrouxá-lo:
    # sob as duas leituras G0.3 reprova (0,6052% e 0,58855%, contra 0,5%).
    saltos = []
    for cd, linhas in por_cia.items():
        for anterior, atual in zip(linhas, linhas[1:]):
            a, b = anterior["ativo"], atual["ativo"]
            if not a or not b:
                continue
            distancia = (ordinal_trimestre(atual["trimestre"])
                         - ordinal_trimestre(anterior["trimestre"]))
            razao = max(abs(a), abs(b)) / min(abs(a), abs(b))
            if razao >= FATOR_DE_SALTO_DE_ESCALA:
                saltos.append({
                    "cd_cvm": cd, "de": anterior["trimestre"],
                    "para": atual["trimestre"], "razao": round(razao, 1),
                    "distancia_em_trimestres": distancia,
                    "adjacente": distancia == 1,
                })
    nao_adjacentes = [s for s in saltos if not s["adjacente"]]
    saltos = [s for s in saltos if s["adjacente"]]

    fracao_saltos = len(saltos) / len(ativo) if ativo else 0.0

    # G0.0 — **correção de 2026-09-16 (contrato G4.5).** `gate_g0([], [], [])`
    # devolvia `aprovado = True`: sem nada medido, aprovava. É o §4.4 regra 4,
    # a mesma que já obrigara `gate_g1` a reprovar amostra vazia. A reprovação é
    # do universo INTEIRO vazio, não de qualquer fonte vazia (G4.6): há caso de
    # isolamento legítimo que passa `fco = []` de propósito para medir só G0.3,
    # e enfraquecê-lo para fazer esta guarda passar é o que o §4.4 proíbe.
    fontes_vazias = sorted(
        nome for nome, fonte in
        (("fco", fco), ("ativo", ativo), ("duracoes", duracoes)) if not fonte
    )
    universo_vazio = len(fontes_vazias) == 3

    # G0.4 — conta requerida ausente do payload, ou sem linha nenhuma, é
    # ausência de dado: reprova (G4.3/G4.4). Medição que não aconteceu não pode
    # valer por medição limpa.
    por_conta = {
        nome: {
            "linhas": int(nulos.get(nome, {}).get("linhas", 0)),
            "nulos": int(nulos.get(nome, {}).get("nulos", 0)),
        }
        for nome in CONTAS_REQUERIDAS
    }
    sem_linha = sorted(n for n, v in por_conta.items() if not v["linhas"])
    total_de_nulos = sum(v["nulos"] for v in por_conta.values())

    resultado = {
        "gate": "G0",
        "pergunta": "O dado é íntegro?",
        "papel": "decisivo",
        "observacoes_de_fco": len(fco),
        "observacoes_de_ativo": len(ativo),
        "g0_1_companhia_trimestre_com_os_dois_metodos": len(somados),
        "g0_1_inventario": [
            {"cd_cvm": c, "trimestre": q} for c, q in somados
        ],
        "g0_2_fora_da_duracao_de_um_trimestre": len(fora_de_duracao),
        "g0_2_grupos_com_trimestre_e_periodo_mais_longo": len(grupos_contaminados),
        # Contrato M2: **inventário completo e ordenado**, não dez exemplos.
        # `carregar_duracoes` não tinha `ORDER BY`, então `[:10]` publicava
        # subconjuntos diferentes a cada execução — o artefato não era
        # reproduzível byte a byte, ressalva do §7 item 2 da revisão de 12/09.
        "g0_2_inventario": sorted(
            fora_de_duracao,
            key=lambda r: (r["cd_cvm"], r["trimestre"], r["dias"]),
        ),
        "g0_2_duracoes_distintas": sorted(
            {r["dias"] for r in fora_de_duracao}
        ),
        "g0_3_saltos_de_escala": len(saltos),
        "g0_3_pares_nao_adjacentes_descartados": len(nao_adjacentes),
        "g0_3_nao_adjacentes": nao_adjacentes,
        "g0_3_fracao": round(fracao_saltos, 6),
        "g0_3_inventario": sorted(
            saltos, key=lambda r: (r["cd_cvm"], r["de"], r["para"])
        ),
        "g0_0_fontes_vazias": fontes_vazias,
        "g0_4_nulos_nas_contas_usadas": total_de_nulos,
        "g0_4_por_conta": por_conta,
        "g0_4_contas_sem_linha_alguma": sem_linha,
        "limiar": (
            f"0 somas de método duplo · 0 fora de "
            f"{DURACAO_MINIMA_DIAS}–{DURACAO_MAXIMA_DIAS} dias · "
            f"<= {G0_TOLERANCIA_ESCALA:.1%} de saltos de escala · "
            f"0 nulos em {'/'.join(CONTAS_REQUERIDAS)} · universo não vazio"
        ),
        "aprovado": (
            not universo_vazio
            and not somados
            and not fora_de_duracao
            and fracao_saltos <= G0_TOLERANCIA_ESCALA
            and not total_de_nulos
            and not sem_linha
        ),
    }
    if universo_vazio:
        resultado["motivo"] = (
            "universo vazio: G0 não aprova por ausência de dado (§4.4 regra 4)"
        )
    elif sem_linha:
        resultado["motivo"] = (
            f"conta requerida sem linha alguma: {', '.join(sem_linha)} — "
            "G0.4 não pode ser verificada sobre dado que não existe"
        )
    return resultado


# --- construção da amostra -------------------------------------------------

def primeiro_trimestre_apos(d) -> str:
    """Rótulo CIVIL do primeiro trimestre iniciado depois de `D`.

    **Desde 2026-09-15 (contrato H1.1) não é mais o que define o horizonte.**
    O painel rotula trimestres pelo exercício SOCIAL; para exercício não civil
    este rótulo aponta outro período, e casá-lo pelo texto aceitava trimestre
    já iniciado. A construção escolhe q1 pelas DATAS da linha; esta função fica
    como referência do caso civil e como contraprova de que os dois divergem.

    Contrato R2.1 (achado R2). Calculado **pelo calendário**, nunca pelo dado
    disponível. A versão anterior conferia apenas se os quatro períodos
    ENCONTRADOS eram consecutivos — e, faltando `3T2019`, aceitava
    `q1 = 4T2019` para `D = 10/05/2019`. O contrato exige `3T2019`: ausência
    pede **censura**, não deslocamento do horizonte.
    """
    ano, tri = d.year, (d.month - 1) // 3 + 1
    # O trimestre corrente já começou em D (ou antes), então o primeiro a
    # COMEÇAR depois de D é sempre o seguinte.
    return f"1T{ano + 1}" if tri == 4 else f"{tri + 1}T{ano}"


def _como_data(valor) -> datetime.date:
    """`Timestamp`, `datetime`, `date` ou texto ISO → `date` (contrato H1.5).

    Em dado real as datas chegam como `pandas.Timestamp`, e `str(D)` publicava
    `'2013-03-08 00:00:00'`; nos testes chegam como `date`. A identidade temporal
    precisa de um tipo só.
    """
    if isinstance(valor, datetime.datetime):  # `Timestamp` herda de `datetime`
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    return datetime.date.fromisoformat(str(valor)[:10])


def _mais_tres_meses(d: datetime.date) -> datetime.date:
    """`D + 3 meses` de calendário, com o dia limitado ao fim do mês."""
    mes = d.month + 3
    ano = d.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return datetime.date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def _rotulo_do_ordinal(ordem: int) -> str:
    """Inverso de `ordinal_trimestre`."""
    return f"{ordem % 4 + 1}T{ordem // 4}"


def _encadeada(linhas: list[dict]) -> bool:
    """Cada período começa no dia seguinte ao fim do anterior (H1.2/H1.3).

    Ordinal contíguo diz que os RÓTULOS se sucedem; só as datas dizem que os
    PERÍODOS se sucedem. Medido no painel real: 15 pares consecutivos de rótulo
    cujas datas não encadeiam — `019836` rotula "3T2014" um período de
    out–dez/2013.
    """
    return all(
        _como_data(b["dt_ini"]) == _como_data(a["dt_fim"]) + datetime.timedelta(days=1)
        for a, b in zip(linhas, linhas[1:])
    )


def _ou_nulo(valor):
    """`NaT`/`NaN` do pandas viram `None`.

    **Achado da implementação de 2026-09-16, ao exercitar H2.3 contra o painel
    real.** Data ausente chega do `.df()` como `NaT`, e `NaT is None` é
    **falso** — pior, toda comparação com `NaT` devolve falso, então esse
    sentinel atravessa qualquer verificação sem acusar nada. Um saldo de balanço
    não tem início, e "ausente" precisa ter UMA representação para ser
    verificável. Isto normaliza um sentinel; não preenche nem inventa data.
    """
    return None if valor is None or valor != valor else valor


def _procedencia(linha: dict) -> dict:
    return {
        "trimestre": linha["trimestre"], "dt_ini": _ou_nulo(linha["dt_ini"]),
        "dt_fim": _ou_nulo(linha["dt_fim"]),
        "dt_receb": _ou_nulo(linha["dt_receb"]),
    }


def _contigua(linhas: list[dict]) -> bool:
    """Ordinais consecutivos, sem lacuna (contrato R2.2).

    `passado[-4:]` somava quatro linhas quaisquer: faltando `4T2018`, o "TTM"
    aceito era `2T2018 + 3T2018 + 1T2019 + 2T2019` — quatro linhas num vão de
    cinco trimestres. Janela com buraco não é janela móvel.
    """
    ordens = [ordinal_trimestre(r["trimestre"]) for r in linhas]
    return ordens == list(range(ordens[0], ordens[0] + len(ordens)))


def _somas_do_rotulo(rotulo: list[dict]) -> tuple[float, float]:
    """S1 e S2 do §2 do pré-registro — o único lugar onde o desfecho é somado."""
    return rotulo[0]["fco"] + rotulo[1]["fco"], rotulo[2]["fco"] + rotulo[3]["fco"]


def construir_amostra(fco: list[dict], ativo: list[dict],
                      calcular_rotulo: bool = True) -> tuple[list[dict], dict]:
    """Um par (companhia, D) por data de recepção. D = `dt_receb`.

    **`calcular_rotulo=False` (2026-09-16, auditoria dos lotes B/C):** constrói a
    mesma amostra — mesmas censuras, mesma linhagem — sem NUNCA somar o FCO dos
    trimestres do rótulo. É o modo de G1 enquanto o pré-registro não estiver
    aprovado: apagar `y` depois de calculado não é cegueira.

    **A grade de decisão é a chegada do formulário, não o fim do trimestre.**
    Em cada `D` entram só as linhas com `dt_receb <= D`, e cada trimestre é
    resolvido para **uma linha inteira** por `vigente_em` (contrato R1.2) — o
    valor nunca é recombinado com a data de outra linha.

    **Correção de 2026-09-15 (contrato H1): o horizonte vem das DATAS da linha.**
    A carga numera trimestres pelo exercício SOCIAL; `primeiro_trimestre_apos`
    devolve o rótulo CIVIL, e casá-los pelo texto aceitava, em exercício não
    civil, um q1 que já tinha começado. Medido em memória sobre o painel real:
    **322 observações em 15 companhias** com rótulo iniciado antes de D (ex.:
    `009539`, exercício em julho, `D = 2013-09-09` recebia "4T2013" =
    abr–jun/2013). O G1 anterior aprovava por existência.
    """
    por_cia: dict[str, dict[str, list[dict]]] = {}
    for r in fco:
        por_cia.setdefault(r["cd_cvm"], {}).setdefault(
            r["trimestre"], []
        ).append(r)
    ativo_por_cia: dict[str, dict[str, list[dict]]] = {}
    for r in ativo:
        ativo_por_cia.setdefault(r["cd_cvm"], {}).setdefault(
            r["trimestre"], []
        ).append(r)

    amostra: list[dict] = []
    descarte = {
        "rotulo_incompleto_em_q_de_D": 0,
        "identidade_temporal_do_rotulo_nao_confere": 0,
        "fco_ttm_nao_positivo": 0,
        "sem_ativo_disponivel": 0,
        "historico_insuficiente": 0,
        "janela_passada_com_lacuna": 0,
        "identidade_temporal_da_janela_nao_confere": 0,
        "chave_companhia_D_repetida": 0,
    }
    conflitos_de_valor = 0

    for cd, trimestres in por_cia.items():
        ativos = ativo_por_cia.get(cd, {})
        for linhas in trimestres.values():
            if len({r["fco"] for r in linhas}) > 1:
                conflitos_de_valor += 1
        # O rótulo é desfecho, não feature: usa a linha mais recente publicada
        # de cada trimestre.
        publicadas = {
            periodo: max(linhas_q, key=lambda r: r["dt_receb"])
            for periodo, linhas_q in trimestres.items()
        }
        datas = sorted({r["dt_receb"] for rs in trimestres.values() for r in rs})
        vistos: set[tuple[str, str]] = set()
        for d in datas:
            data_d = _como_data(d)
            chave = (cd, data_d.isoformat())
            # R2.4: uma observação por (companhia, D). Duas linhas com a mesma
            # recepção geravam duas observações para a mesma chave declarada.
            if chave in vistos:
                descarte["chave_companhia_D_repetida"] += 1
                continue

            passado = [
                v for v in (
                    vigente_em(rs, d) for rs in trimestres.values()
                ) if v is not None
            ]
            passado.sort(key=lambda r: ordinal_trimestre(r["trimestre"]))
            # R2.3: exatamente `JANELA_SD` antecedentes, que é o que os
            # componentes usam. Exigir `JANELA_SD + 1` era corte não declarado.
            if len(passado) < JANELA_SD:
                descarte["historico_insuficiente"] += 1
                continue
            janela = passado[-JANELA_SD:]
            if not _contigua(janela):
                descarte["janela_passada_com_lacuna"] += 1
                continue
            if not _encadeada(janela):
                # H1.3: rótulos contíguos com períodos que não se sucedem.
                descarte["identidade_temporal_da_janela_nao_confere"] += 1
                continue

            # H1.1: q1 é o trimestre de menor início POSTERIOR a D, e só é
            # q(D) se começar até três meses depois de D — trimestres de três
            # meses começam a cada três meses. Fora disso o trimestre
            # contratual falta: censura, nunca deslocamento (R2.1).
            futuras = [
                r for r in publicadas.values() if _como_data(r["dt_ini"]) > data_d
            ]
            if not futuras:
                descarte["rotulo_incompleto_em_q_de_D"] += 1
                continue
            q1 = min(
                futuras,
                key=lambda r: (_como_data(r["dt_ini"]), ordinal_trimestre(r["trimestre"])),
            )
            if _como_data(q1["dt_ini"]) > _mais_tres_meses(data_d):
                descarte["rotulo_incompleto_em_q_de_D"] += 1
                continue
            # H1.2: q2..q4 pelo ordinal FISCAL, com datas encadeadas.
            ordem_q1 = ordinal_trimestre(q1["trimestre"])
            rotulo = [q1]
            for passo in range(1, 4):
                seguinte = publicadas.get(_rotulo_do_ordinal(ordem_q1 + passo))
                if seguinte is None:
                    break
                rotulo.append(seguinte)
            if len(rotulo) < 4:
                descarte["rotulo_incompleto_em_q_de_D"] += 1
                continue
            if not _encadeada(rotulo):
                descarte["identidade_temporal_do_rotulo_nao_confere"] += 1
                continue

            ultimos4 = passado[-4:]
            if not _contigua(ultimos4):
                descarte["janela_passada_com_lacuna"] += 1
                continue
            fco_ttm = sum(r["fco"] for r in ultimos4)
            if fco_ttm <= 0:
                descarte["fco_ttm_nao_positivo"] += 1
                continue

            linha_ativo = None
            for periodo in sorted(ativos, key=ordinal_trimestre, reverse=True):
                candidato = vigente_em(ativos[periodo], d)
                if candidato is not None:
                    linha_ativo = candidato
                    break
            if linha_ativo is None or not linha_ativo["ativo"] or linha_ativo["ativo"] <= 0:
                descarte["sem_ativo_disponivel"] += 1
                continue

            serie = [r["fco"] for r in janela]
            sd8 = statistics.stdev(serie)
            negativos = sum(1 for v in serie if v < 0)
            vistos.add(chave)
            observacao = {
                "cd_cvm": cd,
                "D": data_d.isoformat(),
                "trimestre_ancora": passado[-1]["trimestre"],
                "q1": rotulo[0]["trimestre"],
                "fco_ttm_em_D": fco_ttm,
                "sd8_fco_isolado": sd8,
                # Sem `sd8` não há distância em desvios; `inf` diria
                # "infinitamente longe de zero", que é o oposto do que série
                # constante significa aqui. Fica `None` e sai do componente.
                "fco_ttm_sobre_sd8": (fco_ttm / sd8) if sd8 else None,
                "fco_ttm_sobre_ativo": fco_ttm / linha_ativo["ativo"],
                "ativo_total_em_D": linha_ativo["ativo"],
                "trimestres_com_fco_negativo_nos_ultimos_8": negativos,
                # H1.4: o que G1 reconfere. Nunca publicado no artefato.
                "linhagem": {
                    "janela": [_procedencia(r) for r in janela],
                    "rotulo": [_procedencia(r) for r in rotulo],
                    # **Correção CQW-02 (contrato H2.2).** Carregava só
                    # `trimestre` e `dt_receb`, contra os quatro campos que
                    # H1.4 exige também do ativo. `dt_ini` sai `None` e assim
                    # fica (H2.3): saldo de balanço é posição numa data, e as
                    # 23.395 linhas de `BPA`/`1` do painel têm início nulo na
                    # origem. Inventar um seria fabricar período.
                    "ativo": _procedencia(linha_ativo),
                },
            }
            if calcular_rotulo:
                s1, s2 = _somas_do_rotulo(rotulo)
                observacao["y"] = 1 if (s1 < 0 and s2 < 0) else 0
            amostra.append(observacao)

    descarte["grupos_com_valores_conflitantes"] = conflitos_de_valor
    return amostra, descarte


def gate_g1(amostra: list[dict], descarte: dict) -> dict:
    """G1 do §5 do pré-registro, **verificado pela linhagem** (contrato H1.6).

    A versão anterior decidia `aprovado = bool(amostra)` — prometia (R2.5)
    conferir horizonte, contiguidade, unicidade e disponibilidade, e não
    conferia nada. Este código é deliberadamente separado da construção: se a
    construção regredir, a contagem aparece aqui.
    """
    contagens = {
        "g1_1_features_recebidas_depois_de_D": 0,
        "g1_2_q1_nao_e_o_primeiro_trimestre_iniciado_apos_D": 0,
        "g1_3_rotulo_com_inicio_nao_posterior_a_D": 0,
        "r2_5_rotulo_sem_contiguidade": 0,
        "r2_5_janela_sem_contiguidade": 0,
        "r2_5_chave_companhia_D_repetida": 0,
        "r2_5_observacao_sem_linhagem": 0,
    }
    vistas: set[tuple[str, str]] = set()
    for obs in amostra:
        chave = (obs["cd_cvm"], obs["D"])
        if chave in vistas:
            contagens["r2_5_chave_companhia_D_repetida"] += 1
        vistas.add(chave)
        linhagem = obs.get("linhagem")
        if not linhagem:
            contagens["r2_5_observacao_sem_linhagem"] += 1
            continue
        d = _como_data(obs["D"])
        janela, rotulo = linhagem["janela"], linhagem["rotulo"]
        contagens["g1_1_features_recebidas_depois_de_D"] += sum(
            1 for r in [*janela, linhagem["ativo"]] if _como_data(r["dt_receb"]) > d
        )
        inicio_q1 = _como_data(rotulo[0]["dt_ini"]) if rotulo else None
        if inicio_q1 is None or not (d < inicio_q1 <= _mais_tres_meses(d)):
            contagens["g1_2_q1_nao_e_o_primeiro_trimestre_iniciado_apos_D"] += 1
        if any(_como_data(r["dt_ini"]) <= d for r in rotulo):
            contagens["g1_3_rotulo_com_inicio_nao_posterior_a_D"] += 1
        if len(rotulo) != 4 or not _contigua(rotulo) or not _encadeada(rotulo):
            contagens["r2_5_rotulo_sem_contiguidade"] += 1
        if len(janela) != JANELA_SD or not _contigua(janela) or not _encadeada(janela):
            contagens["r2_5_janela_sem_contiguidade"] += 1

    resultado = {
        "gate": "G1",
        "pergunta": "É point-in-time E no horizonte exato?",
        "papel": "decisivo",
        "observacoes": len(amostra),
        "companhias": len({r["cd_cvm"] for r in amostra}),
        "descartes": descarte,
        **contagens,
        "construcao": (
            "D = datas distintas de disponibilidade das linhas de FCO fornecidas "
            "ao construtor (campo dt_receb); no painel de pesquisa, inclui a "
            "publicação das provas de escala. Features só disponíveis em D; "
            "q1 = trimestre de menor início posterior a D, até "
            "D + 3 meses; q2..q4 pelo ordinal fiscal com datas encadeadas."
        ),
        "limiar": "zero em cada contagem, sobre amostra NÃO vazia",
        "aprovado": bool(amostra) and not any(contagens.values()),
    }
    if not amostra:
        # §4.4 regra 4: guarda que aprova por ausência de dado é pior que
        # guarda nenhuma.
        resultado["motivo"] = "amostra vazia: G1 não aprova por ausência de dado"
    return resultado


# --- T1 --------------------------------------------------------------------

def amplitude_por_quintis(valores: list[float], eventos: list[int]) -> dict:
    """Amplitude da taxa de evento entre quintis, com empates AGRUPADOS.

    **Cortar por posição atribui amplitude máxima a variável constante** quando
    os rótulos vêm agrupados: o corte cai no meio de um bloco de valores iguais
    e separa em "quintis" observações indistinguíveis. Foi o achado C1 do
    B-DFC-01J. Aqui o corte se estende até o fim do grupo de valor empatado, e
    variável constante devolve exatamente UM grupo, com amplitude 0,0.

    **Correção de 17/09 (contrato Q1, achado RF-03).** A versão anterior forçava
    `fim = max(corte, inicio + 1)`: depois de um empate que engolia vários
    cortes nominais, ela criava assim mesmo as faixas "atrasadas", uma
    observação cada — `[0]*400 + 1..100` saía `[400, 1, 1, 1, 97]` e amplitude
    1,0 com taxas reais de 0,5. Agora os cortes nominais `⌊k·n/5⌋` avançam até o
    fim do empate e os redundantes (em 0, em n, ou não depois do anterior) são
    eliminados.
    """
    if len(valores) < MINIMO_DE_OBSERVACOES:
        raise AmostraInsuficiente(
            f"{len(valores)} observações: menos que o mínimo "
            f"{MINIMO_DE_OBSERVACOES} para quintis."
        )
    ordenados = sorted(zip(valores, eventos), key=lambda t: t[0])
    n = len(ordenados)
    cortes: list[int] = []
    for k in range(1, 5):
        corte = k * n // 5
        while 0 < corte < n and ordenados[corte][0] == ordenados[corte - 1][0]:
            corte += 1
        if 0 < corte < n and (not cortes or corte > cortes[-1]):
            cortes.append(corte)
    faixas: list[dict] = []
    for inicio, fim in zip([0, *cortes], [*cortes, n]):
        recorte = ordenados[inicio:fim]
        faixas.append({
            "quintil": len(faixas) + 1,
            "n": len(recorte),
            "valor_minimo": recorte[0][0],
            "valor_maximo": recorte[-1][0],
            "taxa": statistics.fmean(e for _, e in recorte),
        })
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
        # Q3 (17/09): FREQUÊNCIA entre reamostragens de companhias, não
        # probabilidade posterior sobre a amplitude verdadeira. A regra do §6
        # (> 10% ⇒ INDECIDÍVEL) usa este número como está.
        "frequencia_bootstrap_acima_do_limiar": round(excede, 4),
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
    insuficientes: list[str] = []
    for coluna in COMPONENTES_T1:
        usaveis = [r for r in amostra if r[coluna] is not None]
        companhias_usadas = {r["cd_cvm"] for r in usaveis}
        # Contrato R5: o mínimo registrado vale sobre o suporte EFETIVO, depois
        # dos filtros de disponibilidade. A versão anterior conferia o mínimo
        # de companhias só na amostra GLOBAL e nunca recontava — medido, ela
        # aprovava um componente medido em 570 observações de UMA companhia.
        # Isto não aumenta nenhum mínimo: aplica o que já estava registrado.
        # Contrato S1.1 (conferência de 15/09): o piso de OBSERVAÇÕES vale
        # como o de companhias. Antes, 499 observações lançavam a exceção de
        # `amplitude_por_quintis` e interrompiam T1 inteiro, apagando a
        # medição dos outros componentes.
        if (len(usaveis) < MINIMO_DE_OBSERVACOES
                or len(companhias_usadas) < MINIMO_DE_COMPANHIAS):
            resultados[coluna] = {
                "veredito": "INSUFICIENTE",
                "observacoes_usadas": len(usaveis),
                "companhias_usadas": len(companhias_usadas),
                "motivo": (
                    f"suporte efetivo de {len(usaveis)} observações e "
                    f"{len(companhias_usadas)} companhias, abaixo do mínimo "
                    f"({MINIMO_DE_OBSERVACOES} e {MINIMO_DE_COMPANHIAS})"
                ),
            }
            insuficientes.append(coluna)
            continue
        medida = amplitude_por_quintis(
            [r[coluna] for r in usaveis], [r["y"] for r in usaveis]
        )
        entrada = {
            "amplitude": round(medida["amplitude"], 4),
            "grupos_de_quintil": medida["grupos"],
            "observacoes_usadas": len(usaveis),
            "companhias_usadas": len(companhias_usadas),
            "taxa_por_quintil": [round(f["taxa"], 4) for f in medida["faixas"]],
            "n_por_quintil": [f["n"] for f in medida["faixas"]],
        }
        if medida["amplitude"] >= T1_AMPLITUDE:
            entrada["veredito"] = "REPROVA"
        elif medida["amplitude"] >= T1_ZONA_CINZENTA:
            # Zona cinzenta do §6: o viés da amplitude é PARA CIMA, então passar
            # raspando não é aprovação sem medir a incerteza.
            try:
                entrada["bootstrap"] = _bootstrap_amplitude(amostra, coluna)
            except AmostraInsuficiente as erro:
                # S1.2: sem bootstrap o componente não pode passar — mas a
                # insuficiência é DELE, não de T1 inteiro.
                entrada["veredito"] = "INSUFICIENTE"
                entrada["motivo"] = str(erro)
                insuficientes.append(coluna)
            else:
                entrada["veredito"] = (
                    "INDECIDIVEL"
                    if entrada["bootstrap"]["frequencia_bootstrap_acima_do_limiar"]
                    > T1_PROB_MAXIMA
                    else "PASSA"
                )
        else:
            entrada["veredito"] = "PASSA"
        resultados[coluna] = entrada

    medidos = {k: v for k, v in resultados.items() if "amplitude" in v}
    piores = sorted(
        medidos.items(), key=lambda kv: kv[1]["amplitude"], reverse=True
    )
    vereditos = {v["veredito"] for v in resultados.values()}
    # R4.1: reprovação NUMÉRICA e insuficiência são estados diferentes. Só a
    # primeira rejeita o alvo; a segunda deixa a rodada indecidível.
    reprova_numericamente = "REPROVA" in vereditos
    return {
        "teste": "T1",
        "pergunta": "O alvo fabrica o próprio baseline?",
        "papel": "decisivo",
        "limiar": f"amplitude < {T1_AMPLITUDE} em TODOS os componentes",
        "componentes": resultados,
        "componentes_insuficientes": insuficientes,
        "componente_com_maior_amplitude": piores[0][0] if piores else None,
        "maior_amplitude": piores[0][1]["amplitude"] if piores else None,
        "aprovado": vereditos == {"PASSA"},
        "reprova_numericamente": reprova_numericamente,
        "indecidivel": (
            not reprova_numericamente
            and bool(vereditos & {"INDECIDIVEL", "INSUFICIENTE"})
        ),
    }


# --- T2 --------------------------------------------------------------------

def _auc(escores: list[float], eventos: list[int]) -> float | None:
    """AUC com meio ponto para empate — por postos médios (contrato B1.4).

    Mesmo valor da contagem de pares concordantes, em O(n log n): bootstrapar
    três métricas × `REAMOSTRAGENS` × três baselines por pares seria
    quadrático. A soma é feita com postos DOBRADOS, inteiros, até a divisão
    final — nenhum arredondamento intermediário.
    """
    n_pos = sum(1 for y in eventos if y == 1)
    n_neg = len(eventos) - n_pos
    if not n_pos or not n_neg:
        return None
    ordem = sorted(range(len(escores)), key=escores.__getitem__)
    soma_dos_postos_dobrados = 0
    inicio = 0
    while inicio < len(ordem):
        fim = inicio
        while fim + 1 < len(ordem) and escores[ordem[fim + 1]] == escores[ordem[inicio]]:
            fim += 1
        # Postos 1-based de `inicio+1` a `fim+1`; média dobrada = inicio+fim+2.
        positivos_no_bloco = sum(
            1 for k in range(inicio, fim + 1) if eventos[ordem[k]] == 1
        )
        soma_dos_postos_dobrados += (inicio + fim + 2) * positivos_no_bloco
        inicio = fim + 1
    return (soma_dos_postos_dobrados - n_pos * (n_pos + 1)) / (2 * n_pos * n_neg)


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
    if agregada is None:
        # Com uma companhia de dois rótulos, a amostra tem os dois: não ocorre.
        # Se ocorrer, é defeito — nunca lacuna medida contra zero.
        raise AmostraInsuficiente("AUC agregada não calculável")
    lacuna = agregada - media_intra
    return {
        "teste": "T2",
        "pergunta": "Há sinal temporal ou só ordenação de emissor?",
        "papel": "decisivo",
        "escore": coluna,
        # R6 (17/09): `if agregada` publicava AUC ZERO como ausente.
        "auc_agregada": round(agregada, 4),
        "auc_intra_companhia": round(media_intra, 4),
        "companhias_com_os_dois_rotulos": com_dois_rotulos,
        "companhias_na_amostra": len(por_cia),
        "lacuna": round(lacuna, 4),
        "limiar": f"< {T2_LACUNA}",
        "aprovado": lacuna < T2_LACUNA,
    }


# --- baselines -------------------------------------------------------------

def _precisao_no_topo(escores: list[float], alvos: list[int], fracao: float) -> dict:
    """Precisão no top-k **sem olhar o rótulo** (contrato R3).

    O defeito: `sorted(zip(escores, alvos), reverse=True)` desempata pela
    tupla, ou seja, por `y` decrescente — os positivos iam para a frente
    usando a resposta que o baseline deveria desconhecer. Medido: escore
    constante com 10% de positivos devolvia precisão 1,0 e lift 10,0.

    A correção tem duas partes. A ordenação usa **só o escore**. E quando um
    grupo de empate atravessa o corte, a precisão é a **esperada sob desempate
    aleatório** — a média do grupo entra ponderada pela fração que cabe. Isso
    elimina o vazamento e a arbitrariedade de qual metade entraria.
    """
    k = max(1, int(len(escores) * fracao))
    pares = sorted(zip(escores, alvos), key=lambda par: -par[0])
    acumulado = 0.0
    restantes = k
    empates_no_corte = 0
    i = 0
    while restantes > 0 and i < len(pares):
        j = i
        while j < len(pares) and pares[j][0] == pares[i][0]:
            j += 1
        grupo = pares[i:j]
        if len(grupo) <= restantes:
            acumulado += sum(y for _, y in grupo)
            restantes -= len(grupo)
        else:
            # O grupo atravessa o corte: entra a fração esperada.
            acumulado += statistics.fmean(y for _, y in grupo) * restantes
            empates_no_corte = len(grupo)
            restantes = 0
        i = j
    return {
        "k": k,
        "precisao": acumulado / k,
        "empates_no_corte": empates_no_corte,
    }


def _auc_intra(amostra: list[dict], escores: list[float]) -> dict:
    """AUC intra-companhia por baseline — exigência do §8, que faltava."""
    por_cia: dict[str, list[tuple[float, int]]] = {}
    for s, r in zip(escores, amostra):
        por_cia.setdefault(r["cd_cvm"], []).append((s, r["y"]))
    valores = []
    for pares in por_cia.values():
        if len({y for _, y in pares}) < 2:
            continue
        v = _auc([s for s, _ in pares], [y for _, y in pares])
        if v is not None:
            valores.append(v)
    return {
        "auc_intra_companhia": (
            round(statistics.fmean(valores), 4) if valores else None
        ),
        "companhias_com_os_dois_rotulos": len(valores),
    }


def _intervalo(valores: list[float]) -> dict:
    """IC95% percentil; `None` abaixo de `MINIMO_DE_REAMOSTRAGENS_VALIDAS`."""
    if len(valores) < MINIMO_DE_REAMOSTRAGENS_VALIDAS:
        return {"inferior": None, "superior": None,
                "reamostragens_validas": len(valores)}
    ordenados = sorted(valores)
    return {
        "inferior": round(ordenados[int(0.025 * len(ordenados))], 4),
        "superior": round(ordenados[int(0.975 * len(ordenados)) - 1], 4),
        "reamostragens_validas": len(ordenados),
    }


def _ic_das_metricas(amostra: list[dict], escores: list[float]) -> dict:
    """IC95% das TRÊS métricas do §8, reamostrando COMPANHIAS inteiras.

    Contrato B1.1. A versão anterior intervalava só a AUC agregada, sob nomes
    genéricos (`ic95_inferior`) que não diziam de qual métrica eram. Trimestres
    do mesmo emissor não são réplicas (§4.4 regra 8). Companhias ordenadas:
    o intervalo não pode depender da ordem de entrada.
    """
    por_cia: dict[str, list[tuple[float, int]]] = {}
    for s, r in zip(escores, amostra):
        por_cia.setdefault(r["cd_cvm"], []).append((s, r["y"]))
    chaves = sorted(por_cia)
    auc_da_companhia = {
        k: _auc([s for s, _ in pares], [y for _, y in pares])
        for k, pares in por_cia.items()
    }
    aleatorio = random.Random(SEMENTE)
    medidas: dict[str, list[float]] = {
        "auc_agregada": [], "precisao_no_top_10pct": [], "auc_intra_companhia": [],
    }
    for _ in range(REAMOSTRAGENS):
        sorteadas = [aleatorio.choice(chaves) for _ in chaves]
        pares = [p for k in sorteadas for p in por_cia[k]]
        sorteados = [s for s, _ in pares]
        alvos = [y for _, y in pares]
        auc = _auc(sorteados, alvos)
        if auc is not None:
            medidas["auc_agregada"].append(auc)
        medidas["precisao_no_top_10pct"].append(
            _precisao_no_topo(sorteados, alvos, 0.10)["precisao"]
        )
        intra = [auc_da_companhia[k] for k in sorteadas if auc_da_companhia[k] is not None]
        if intra:
            medidas["auc_intra_companhia"].append(statistics.fmean(intra))
    return {f"{nome}_ic95": _intervalo(valores) for nome, valores in medidas.items()}


def _ic_do_acerto_do_b0(amostra: list[dict]) -> dict:
    """B0.1 (17/09): IC95% do acerto de "sempre não consumir", por companhia.

    Acerto de B0 = fração de `y == 0`. Reamostragem de companhias inteiras, a
    mesma semente e o mesmo mínimo de reamostragens válidas das outras métricas.
    """
    por_cia: dict[str, list[int]] = {}
    for r in amostra:
        por_cia.setdefault(r["cd_cvm"], []).append(r["y"])
    chaves = sorted(por_cia)
    aleatorio = random.Random(SEMENTE)
    medidas = []
    for _ in range(REAMOSTRAGENS):
        eventos = [y for k in (aleatorio.choice(chaves) for _ in chaves) for y in por_cia[k]]
        if eventos:
            medidas.append(1 - statistics.fmean(eventos))
    return _intervalo(medidas)


def medir_baselines(amostra: list[dict]) -> dict:
    """Os quatro triviais do §8, ANTES de qualquer componente aprendido.

    Cada um publica AUC agregada, AUC intra-companhia e precisão no top-10%,
    **cada uma com seu** IC95% por bootstrap agrupado por companhia.

    **Contrato B1.3 (conferência de 15/09):** `completo=True` exige as métricas
    e os intervalos VÁLIDOS, não só o suporte. Antes, B3 medido só em negativos
    — AUC `None`, IC `None`, nenhuma companhia com os dois rótulos — saía
    `completo=True`, e o auditor devolvia `PRONTO PARA CHALLENGER`.
    """
    eventos = [r["y"] for r in amostra]
    taxa_base = statistics.fmean(eventos)
    ic_b0 = _ic_do_acerto_do_b0(amostra)
    tabela: dict[str, dict] = {
        # B0.1 (17/09): o nome diz a regra. "Classe majoritária" sugeria uma
        # classe ESTIMADA; a regra é fixa, "sempre não consumir".
        "B0_sempre_nao_consumir": {
            "descricao": "Prever sempre 'não vai consumir caixa' (regra fixa, não estimada)",
            "acerto": round(1 - taxa_base, 4),
            "acerto_ic95": ic_b0,
            # R4.4: as duas coberturas, com o nome dizendo qual é qual.
            # Confundir abstenção de RANQUEAMENTO com ausência de previsão de
            # CLASSE foi ressalva da revisão de 12/09.
            "cobertura_de_ranqueamento": 0.0,
            "cobertura_de_previsao_de_classe": 1.0,
            "observacao": (
                "Escore constante: abstém da ordenação, então AUC não se "
                "aplica. A previsão de CLASSE, porém, cobre tudo. Publicar "
                "cobertura ao lado do acerto é exigência do §3.11. A cobertura "
                "de classe é 1,0 por construção: sem bootstrap, não há o que variar."
            ),
            "completo": ic_b0["inferior"] is not None,
            "motivos_de_incompletude": (
                [] if ic_b0["inferior"] is not None else
                [f"acerto_ic95 com {ic_b0['reamostragens_validas']} reamostragens válidas, "
                 f"abaixo de {MINIMO_DE_REAMOSTRAGENS_VALIDAS}"]),
        },
    }
    incompletos: list[str] = [] if tabela["B0_sempre_nao_consumir"]["completo"] \
        else ["B0_sempre_nao_consumir"]
    for nome, (coluna, sentido) in BASELINES.items():
        usaveis = [r for r in amostra if r[coluna] is not None]
        companhias = {r["cd_cvm"] for r in usaveis}
        if len(usaveis) < MINIMO_DE_OBSERVACOES or len(companhias) < MINIMO_DE_COMPANHIAS:
            # R5: o mínimo registrado vale sobre o suporte EFETIVO.
            tabela[nome] = {
                "coluna": coluna,
                "observacoes_usadas": len(usaveis),
                "companhias_usadas": len(companhias),
                "completo": False,
                "motivos_de_incompletude": [
                    f"suporte efetivo abaixo do mínimo registrado "
                    f"({MINIMO_DE_OBSERVACOES} obs, {MINIMO_DE_COMPANHIAS} companhias)"
                ],
            }
            incompletos.append(nome)
            continue
        escores = [sentido * r[coluna] for r in usaveis]
        alvos = [r["y"] for r in usaveis]
        auc = _auc(escores, alvos)
        topo = _precisao_no_topo(escores, alvos, 0.10)
        base_local = statistics.fmean(alvos)
        lift = round(topo["precisao"] / base_local, 3) if base_local else None
        intra = _auc_intra(usaveis, escores)
        intervalos = _ic_das_metricas(usaveis, escores)

        motivos: list[str] = []
        if not 0 < base_local < 1:
            motivos.append("o suporte não tem os dois rótulos")
        if auc is None:
            motivos.append("AUC agregada não calculável")
        if intra["auc_intra_companhia"] is None:
            motivos.append(
                "nenhuma companhia com os dois rótulos: AUC intra não calculável"
            )
        if lift is None:
            motivos.append("lift não calculável: taxa-base zero")
        for chave_ic, ic in intervalos.items():
            if ic["inferior"] is None:
                motivos.append(
                    f"{chave_ic} com {ic['reamostragens_validas']} reamostragens "
                    f"válidas, abaixo de {MINIMO_DE_REAMOSTRAGENS_VALIDAS}"
                )
        tabela[nome] = {
            "coluna": coluna,
            "sentido": sentido,
            "observacoes_usadas": len(usaveis),
            "companhias_usadas": len(companhias),
            # R4.5: `if auc` serializava AUC ZERO como `None`.
            "auc_agregada": round(auc, 4) if auc is not None else None,
            **intra,
            "precisao_no_top_10pct": round(topo["precisao"], 4),
            "empates_no_corte": topo["empates_no_corte"],
            "observacoes_no_topo": topo["k"],
            "lift_sobre_a_taxa_base": lift,
            **intervalos,
            "completo": not motivos,
            "motivos_de_incompletude": motivos,
        }
        if motivos:
            incompletos.append(nome)
    validos = {
        n: v for n, v in tabela.items()
        if n != "B0_sempre_nao_consumir" and v["completo"]
    }
    melhor = max(validos, key=lambda n: validos[n]["auc_agregada"]) if validos else None
    return {
        "taxa_base_do_evento": round(taxa_base, 4),
        "baselines": tabela,
        "melhor_trivial": melhor,
        # R4.2: a completude entra na DECISÃO, não fica só publicada.
        "todos_completos": not incompletos,
        "baselines_incompletos": incompletos,
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
        nulos = carregar_nulos(con)
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

    g0 = _medir("G0", lambda: gate_g0(fco, ativo, duracoes, nulos))
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
    g1 = gate_g1(amostra, descarte)
    cadeia.append(g1)
    if not g1["aprovado"]:
        # H1.7: G1 é decisivo como G0. Medir T1, T2 ou baseline sobre amostra
        # que não é point-in-time poria no artefato número que não deveria
        # existir.
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
            "primeiro_reprovado": "G1",
            "veredito": "REPROVADO EM G0/G1",
            "quarentena": (
                "G1 reprovou: a amostra construída não é point-in-time no "
                "horizonte contratual. NENHUM teste posterior foi medido."
            ),
        }

    t1 = _medir("T1", lambda: teste_t1(amostra))
    escore_t2, sentido_t2 = BASELINES[
        max(BASELINES, key=lambda n: 1 if n == "B1_fco_sobre_sd8" else 0)
    ]
    cadeia_t2 = _medir("T2", lambda: teste_t2(amostra, escore_t2, sentido_t2))

    try:
        baselines = medir_baselines(amostra)
    except (ZeroDivisionError, statistics.StatisticsError) as erro:
        # Falha de INSTRUMENTAÇÃO: não é reprovação do alvo nem aprovação.
        baselines = {"reprova_em_aberto": str(erro), "todos_completos": False}

    # --- decisão (contrato R4.1/R4.2) ---------------------------------------
    # Três estados distintos, nunca fundidos: reprovação NUMÉRICA, amostra
    # INSUFICIENTE e falha de INSTRUMENTAÇÃO. Só a primeira rejeita o alvo.
    #
    # A versão anterior errava nos três: `indecidivel and t1["aprovado"]` nunca
    # se satisfazia (T1 não está aprovado justamente por ser inconclusivo), e a
    # falha dos baselines virava `reprova_em_aberto` SEM entrar na conjunção de
    # aprovação — devolvendo `PRONTO PARA CHALLENGER` com baseline falho. É o
    # achado F10 pela quarta vez: exigência que existe como texto e não
    # participa da condição de aprovação (AGENTS.md §4.4, regra 7).
    gates_ok = g0["aprovado"] and g1["aprovado"]
    testes_ok = all(x["aprovado"] for x in cadeia)
    baselines_completos = bool(baselines.get("todos_completos"))
    reprova_numericamente = (
        t1.get("reprova_numericamente", False)
        or (cadeia_t2 is not None and cadeia_t2.get("aprovado") is False
            and "reprova_em_aberto" not in cadeia_t2)
    )
    inconclusivo = (
        t1.get("indecidivel", False)
        or any("reprova_em_aberto" in x for x in cadeia)
        or not baselines_completos
    )
    if not gates_ok:
        veredito = "REPROVADO EM G0/G1"
    elif reprova_numericamente:
        veredito = "REJEITADO"
    elif testes_ok and baselines_completos:
        # R4.2: os quatro triviais têm de estar MEDIDOS e válidos.
        veredito = "PRONTO PARA CHALLENGER"
    else:
        veredito = "INDECIDIVEL"

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
        "estados_da_decisao": {
            "gates_aprovados": gates_ok,
            "testes_aprovados": testes_ok,
            "reprova_numericamente": reprova_numericamente,
            "inconclusivo": inconclusivo,
            "baselines_completos": baselines_completos,
        },
        "veredito": veredito,
    }


def _resumo_para_tela(relatorio: dict) -> tuple[list[str], int]:
    """O que a CLI imprime, e com que código sai — SEM gravar nada.

    Contrato C1.1: a versão anterior gravava o artefato e só depois lia o
    diagnóstico no formato de 11/09 (`defeito_valor_bruto_continuo`), caindo em
    `KeyError` com o arquivo já escrito. Compor antes faz o formato divergente
    falhar antes de qualquer escrita.
    """
    linhas = [f"Candidato: {relatorio['candidato']}"]
    if "populacao" not in relatorio:
        nome = relatorio["primeiro_reprovado"]
        gate = next(x for x in relatorio["cadeia"] if x.get("gate") == nome)
        linhas.append(f"  REPROVA {nome}: {gate['pergunta']}")
        if nome == "G0":
            if gate.get("motivo"):
                linhas.append(f"    {gate['motivo']}")
            if gate.get("g0_4_nulos_nas_contas_usadas"):
                linhas.append(
                    f"    G0.4 — nulos nas contas usadas: "
                    f"{gate['g0_4_por_conta']}"
                )
            linhas.append(
                f"    saltos de escala: {gate['g0_3_saltos_de_escala']} "
                f"({gate['g0_3_fracao']:.2%}), limiar {G0_TOLERANCIA_ESCALA:.2%}"
            )
            diagnostico = gate["diagnostico_de_escala"]
            recorte_nome = diagnostico["recorte_pertinente_a_G0"]
            recorte = diagnostico["recortes"][recorte_nome]
            linhas.append(
                f"    transições suspeitas ({recorte_nome}): "
                f"{recorte['bruto_continuo_suspeita_de_defeito']} de "
                f"{recorte['transicoes_de_escala']} com valor bruto CONTÍNUO, em "
                f"{recorte['companhias_com_transicao_suspeita']} companhias"
            )
        else:
            for chave, valor in gate.items():
                if chave.startswith(("g1_", "r2_5_")) and valor:
                    linhas.append(f"    {chave}: {valor}")
            if "motivo" in gate:
                linhas.append(f"    {gate['motivo']}")
        linhas.append(f"VEREDITO: {relatorio['veredito']}")
        linhas.append("  Nada de T1/T2/baseline foi medido — rodada invalidada.")
        return linhas, 2
    pop = relatorio["populacao"]
    linhas.append(
        f"População: {pop['observacoes']} obs · {pop['companhias']} companhias "
        f"· taxa do evento {pop['taxa_do_evento']}"
    )
    for etapa in relatorio["cadeia"]:
        nome = etapa.get("gate") or etapa.get("teste")
        marca = "APROVA " if etapa["aprovado"] else "REPROVA"
        extra = etapa.get("reprova_em_aberto", "")
        linhas.append(f"  {marca} {nome}: {etapa.get('pergunta', '')} {extra}"[:110])
    t1 = next((x for x in relatorio["cadeia"] if x.get("teste") == "T1"), None)
    if t1 and "componentes" in t1:
        linhas.append("  T1 por componente:")
        # Componente INSUFICIENTE não tem amplitude — ler `["amplitude"]`
        # derrubava a CLI justamente no caso que R5 criou.
        for nome, dados in sorted(
            t1["componentes"].items(), key=lambda kv: -kv[1].get("amplitude", -1.0)
        ):
            amplitude = dados.get("amplitude")
            texto = f"{amplitude:.4f}" if amplitude is not None else "   —  "
            linhas.append(f"    {texto}  {dados['veredito']:<12} {nome}")
    linhas.append(f"VEREDITO: {relatorio['veredito']}")
    return linhas, 0


def principal() -> int:
    relatorio = executar()
    linhas, codigo = _resumo_para_tela(relatorio)
    DESTINO.mkdir(parents=True, exist_ok=True)
    (DESTINO / "auditoria.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print("\n".join(linhas))
    return codigo


if __name__ == "__main__":
    raise SystemExit(principal())
