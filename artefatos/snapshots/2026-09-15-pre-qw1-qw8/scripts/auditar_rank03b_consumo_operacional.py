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
               f.versao_documento AS versao, f.demonstrativo, f.dt_ini_exerc AS dt_ini
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


def gate_g0(fco: list[dict], ativo: list[dict], duracoes: list[dict]) -> dict:
    """Integridade. Decisivo: reprova a rodada, não é diagnóstico."""
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
    return {
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

def primeiro_trimestre_apos(d) -> str:
    """q(D): o primeiro trimestre fiscal cujo INÍCIO é posterior a `D`.

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


def _contigua(linhas: list[dict]) -> bool:
    """Ordinais consecutivos, sem lacuna (contrato R2.2).

    `passado[-4:]` somava quatro linhas quaisquer: faltando `4T2018`, o "TTM"
    aceito era `2T2018 + 3T2018 + 1T2019 + 2T2019` — quatro linhas num vão de
    cinco trimestres. Janela com buraco não é janela móvel.
    """
    ordens = [ordinal_trimestre(r["trimestre"]) for r in linhas]
    return ordens == list(range(ordens[0], ordens[0] + len(ordens)))


def construir_amostra(fco: list[dict], ativo: list[dict]) -> tuple[list[dict], dict]:
    """Um par (companhia, D) por data de recepção. D = `dt_receb`.

    **A grade de decisão é a chegada do formulário, não o fim do trimestre.**
    Em cada `D` entram só as linhas com `dt_receb <= D`, e cada trimestre é
    resolvido para **uma linha inteira** por `vigente_em` (contrato R1.2) — o
    valor nunca é recombinado com a data de outra linha.
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
        "fco_ttm_nao_positivo": 0,
        "sem_ativo_disponivel": 0,
        "historico_insuficiente": 0,
        "janela_passada_com_lacuna": 0,
        "chave_companhia_D_repetida": 0,
    }
    conflitos_de_valor = 0

    for cd, trimestres in por_cia.items():
        ativos = ativo_por_cia.get(cd, {})
        for linhas in trimestres.values():
            if len({r["fco"] for r in linhas}) > 1:
                conflitos_de_valor += 1
        datas = sorted({r["dt_receb"] for rs in trimestres.values() for r in rs})
        vistos: set[tuple[str, str]] = set()
        for d in datas:
            # R2.4: uma observação por (companhia, D). Duas linhas com a mesma
            # recepção geravam duas observações para a mesma chave declarada.
            if (cd, str(d)) in vistos:
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
            if not _contigua(passado[-JANELA_SD:]):
                descarte["janela_passada_com_lacuna"] += 1
                continue

            # R2.1: o rótulo é q(D) e os três seguintes, por calendário.
            q1 = primeiro_trimestre_apos(d)
            exigidos = [
                f"{(ordinal_trimestre(q1) + i) % 4 + 1}T"
                f"{(ordinal_trimestre(q1) + i) // 4}"
                for i in range(4)
            ]
            rotulo = []
            for periodo in exigidos:
                linhas_q = trimestres.get(periodo)
                # O rótulo é desfecho, não feature: usa a linha mais recente
                # publicada, mas o PERÍODO exigido é o do calendário.
                if not linhas_q:
                    break
                rotulo.append(max(linhas_q, key=lambda r: r["dt_receb"]))
            if len(rotulo) < 4:
                descarte["rotulo_incompleto_em_q_de_D"] += 1
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

            serie = [r["fco"] for r in passado[-JANELA_SD:]]
            sd8 = statistics.stdev(serie)
            negativos = sum(1 for v in serie if v < 0)
            s1 = rotulo[0]["fco"] + rotulo[1]["fco"]
            s2 = rotulo[2]["fco"] + rotulo[3]["fco"]

            vistos.add((cd, str(d)))
            amostra.append({
                "cd_cvm": cd,
                "D": str(d),
                "trimestre_ancora": passado[-1]["trimestre"],
                "q1": rotulo[0]["trimestre"],
                "y": 1 if (s1 < 0 and s2 < 0) else 0,
                "fco_ttm_em_D": fco_ttm,
                "sd8_fco_isolado": sd8,
                # Sem `sd8` não há distância em desvios; `inf` diria
                # "infinitamente longe de zero", que é o oposto do que série
                # constante significa aqui. Fica `None` e sai do componente.
                "fco_ttm_sobre_sd8": (fco_ttm / sd8) if sd8 else None,
                "fco_ttm_sobre_ativo": fco_ttm / linha_ativo["ativo"],
                "ativo_total_em_D": linha_ativo["ativo"],
                "trimestres_com_fco_negativo_nos_ultimos_8": negativos,
            })

    descarte["grupos_com_valores_conflitantes"] = conflitos_de_valor
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
    insuficientes: list[str] = []
    for coluna in COMPONENTES_T1:
        usaveis = [r for r in amostra if r[coluna] is not None]
        companhias_usadas = {r["cd_cvm"] for r in usaveis}
        # Contrato R5: o mínimo registrado vale sobre o suporte EFETIVO, depois
        # dos filtros de disponibilidade. A versão anterior conferia o mínimo
        # de companhias só na amostra GLOBAL e nunca recontava — medido, ela
        # aprovava um componente medido em 570 observações de UMA companhia.
        # Isto não aumenta nenhum mínimo: aplica o que já estava registrado.
        if len(companhias_usadas) < MINIMO_DE_COMPANHIAS:
            resultados[coluna] = {
                "veredito": "INSUFICIENTE",
                "observacoes_usadas": len(usaveis),
                "companhias_usadas": len(companhias_usadas),
                "motivo": (
                    f"{len(companhias_usadas)} companhias no suporte efetivo, "
                    f"abaixo do mínimo {MINIMO_DE_COMPANHIAS}"
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


def _ic_por_companhia(amostra: list[dict], escores: list[float]) -> dict:
    """IC95% da AUC reamostrando COMPANHIAS inteiras — exigência do §8.

    Trimestres do mesmo emissor não são réplicas independentes (§4.4 regra 8).
    """
    por_cia: dict[str, list[tuple[float, int]]] = {}
    for s, r in zip(escores, amostra):
        por_cia.setdefault(r["cd_cvm"], []).append((s, r["y"]))
    chaves = list(por_cia)
    aleatorio = random.Random(SEMENTE)
    medidas = []
    for _ in range(REAMOSTRAGENS):
        sorteadas = [aleatorio.choice(chaves) for _ in chaves]
        pares = [p for k in sorteadas for p in por_cia[k]]
        v = _auc([s for s, _ in pares], [y for _, y in pares])
        if v is not None:
            medidas.append(v)
    if not medidas:
        return {"ic95_inferior": None, "ic95_superior": None,
                "reamostragens_validas": 0}
    medidas.sort()
    return {
        "ic95_inferior": round(medidas[int(0.025 * len(medidas))], 4),
        "ic95_superior": round(medidas[int(0.975 * len(medidas)) - 1], 4),
        "reamostragens_validas": len(medidas),
    }


def medir_baselines(amostra: list[dict]) -> dict:
    """Os quatro triviais do §8, ANTES de qualquer componente aprendido.

    Cada um publica AUC agregada, AUC intra-companhia e precisão no top-10%
    com IC95% por bootstrap agrupado por companhia — as três coisas que o §8
    exige e que a primeira versão não calculava.
    """
    eventos = [r["y"] for r in amostra]
    taxa_base = statistics.fmean(eventos)
    tabela: dict[str, dict] = {
        "B0_classe_majoritaria": {
            "descricao": "Prever sempre 'não vai consumir caixa'",
            "acerto": round(1 - taxa_base, 4),
            # R4.4: as duas coberturas, com o nome dizendo qual é qual.
            # Confundir abstenção de RANQUEAMENTO com ausência de previsão de
            # CLASSE foi ressalva da revisão de 12/09.
            "cobertura_de_ranqueamento": 0.0,
            "cobertura_de_previsao_de_classe": 1.0,
            "observacao": (
                "Escore constante: abstém da ordenação, então AUC não se "
                "aplica. A previsão de CLASSE, porém, cobre tudo. Publicar "
                "cobertura ao lado do acerto é exigência do §3.11."
            ),
            "completo": True,
        },
    }
    incompletos: list[str] = []
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
                "motivo": (
                    f"suporte efetivo abaixo do mínimo registrado "
                    f"({MINIMO_DE_OBSERVACOES} obs, {MINIMO_DE_COMPANHIAS} companhias)"
                ),
            }
            incompletos.append(nome)
            continue
        escores = [sentido * r[coluna] for r in usaveis]
        alvos = [r["y"] for r in usaveis]
        auc = _auc(escores, alvos)
        topo = _precisao_no_topo(escores, alvos, 0.10)
        base_local = statistics.fmean(alvos)
        tabela[nome] = {
            "coluna": coluna,
            "sentido": sentido,
            "observacoes_usadas": len(usaveis),
            "companhias_usadas": len(companhias),
            # R4.5: `if auc` serializava AUC ZERO como `None`.
            "auc_agregada": round(auc, 4) if auc is not None else None,
            **_ic_por_companhia(usaveis, escores),
            **_auc_intra(usaveis, escores),
            "precisao_no_top_10pct": round(topo["precisao"], 4),
            "empates_no_corte": topo["empates_no_corte"],
            "observacoes_no_topo": topo["k"],
            "lift_sobre_a_taxa_base": (
                round(topo["precisao"] / base_local, 3) if base_local else None
            ),
            "completo": True,
        }
    validos = {
        n: v for n, v in tabela.items()
        if n != "B0_classe_majoritaria" and v["completo"]
    }
    melhor = max(
        validos, key=lambda n: validos[n]["auc_agregada"] or 0.0
    ) if validos else None
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
