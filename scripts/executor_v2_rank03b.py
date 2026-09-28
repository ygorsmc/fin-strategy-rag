"""Executor v2 do Rank 3-B — G0, G1, T1, T2 e baselines sobre o painel de pesquisa.

Especificação: `resultados/pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md` (o
rascunho v2) e o contrato de 27/09, parte C
(`resultados/contratos_caminho_medicao_rank03b_2026-09-27.md`). Divergência
entre este arquivo e o pré-registro é defeito DESTE arquivo.

**Dois modos.**

- `estrutural` (padrão): G0, amostra montada SEM rótulo, G0.5 e G1. Grava só o
  que o O1 permite antes do congelamento (§6.1 e §5.5 do rascunho; C8).
- `medicao`: recusa sem o pré-registro congelado (C9). Monta a mesma amostra
  sem rótulo, exige G0 e G1 aprovados, só então soma o rótulo sobre a MESMA
  amostra (chaves conferidas) e mede T1, T2 e baselines.

**Nenhum modelo é carregado.** O `executar()` do auditor de 11/09 não é
reutilizado (§6: ele monta `y` antes de G1). Reutilizam-se, sem cópia, as
funções cuja regra o v2 herda idêntica: `gate_g0` e `gate_g1` (a parte v1),
`teste_t1`, `medir_baselines` e `_auc`.
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import random
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import auditar_rank03b_consumo_operacional as auditor  # noqa: E402
from scripts import painel_pesquisa_rank03b as pp  # noqa: E402
from src.normalizacao import ordinal_trimestre  # noqa: E402

PRE_REGISTRO_RASCUNHO = RAIZ / "resultados" / "pre_registro_rank03b_v2_RASCUNHO_2026-09-16.md"
CONTRATO = RAIZ / "resultados" / "contratos_caminho_medicao_rank03b_2026-09-27.md"
DESTINO = RAIZ / "artefatos" / "executor_v2_rank03b"
DESTINO_PAINEL = RAIZ / "artefatos" / "painel_pesquisa_rank03b_v2"

#: §3.2: o único plano `ll3_13_*` conhecido na decisão. Outro interrompe.
PLANOS_LL3_13_CONHECIDOS = frozenset({"ll3_13_48e4cd07"})
#: §12-bis: erro demonstrado conhecido, listado no artefato de G0.
ERROS_DEMONSTRADOS = (
    {"id_doc": "140867", "cd_cvm": "021520", "conta": "1", "dt_refer": "2024-06-30",
     "fonte": "resultados/alcance_geom1_rank03b_2026-09-24.md"},
)
JANELA = auditor.JANELA_SD
#: §8.1: piso de companhias com os dois rótulos (o mínimo de companhias da v1).
PISO_T2 = auditor.MINIMO_DE_COMPANHIAS
FREQUENCIA_MAXIMA_T2 = auditor.T1_PROB_MAXIMA
ESTADO_REGRA_1 = "escala_heterogenea_nao_adjudicada"

#: §6.1: a ordem fixa dos doze motivos. Cada data sai no primeiro que a remove.
MOTIVOS = (
    "sem_q1_identificavel",
    "q1_repetido_mantido_o_maior_D",
    "historico_insuficiente",
    "janela_com_trimestre_do_5_5",
    "janela_com_lacuna",
    "janela_sem_encadeamento",
    "rotulo_com_trimestre_do_5_5",
    "rotulo_incompleto",
    "rotulo_sem_encadeamento",
    "regra_2_do_5_5",
    "fco_ttm_nao_positivo",
    "sem_ativo_disponivel",
)
#: O1 (§6.1): o motivo 11 não se publica antes do congelamento.
MOTIVO_OMITIDO = "fco_ttm_nao_positivo"
MOTIVOS_DO_5_5 = ("janela_com_trimestre_do_5_5", "rotulo_com_trimestre_do_5_5", "regra_2_do_5_5")
#: Do G0 do auditor, o que NÃO sai antes do congelamento: com as linhas do
#: estado da regra 1, os motivos publicados e as observações finais, recompõe o
#: motivo 11 por subtração sempre que não houver colisão de disponibilidade.
PUBLICACAO_RETIDA_NO_G0 = frozenset({"observacoes_de_fco"})
#: Chaves que nenhum artefato estrutural pode ter (O1.4 do lote B, C8).
CHAVES_PROIBIDAS_ANTES_DO_CONGELAMENTO = frozenset({
    "y", "rotulo", "taxa_do_evento", "s1", "s2", "t1", "t2", "baselines",
    "baselines_triviais", "auc", "auc_agregada", "auc_intra_companhia", "lacuna",
    MOTIVO_OMITIDO, "total_da_grade", "grade", "datas_candidatas",
    "datas_candidatas_por_companhia", *PUBLICACAO_RETIDA_NO_G0,
})


class PlanoDesconhecido(Exception):
    """§3.2: plano `ll3_13_*` que a decisão não conhece — exige decisão nova."""


class NaoCongelado(Exception):
    """C9: o modo de medição exige o pré-registro congelado e os pins."""


class AmostraDivergente(Exception):
    """§6: o rótulo tem de ser somado sobre a MESMA amostra que G0/G1 aprovaram."""


class PublicacaoInsegura(Exception):
    """O1/§6.1: os números publicados recomporiam o motivo 11 por aritmética exata."""


class Congelamento(dict):
    """Registro do congelamento. Só `verificar_congelamento` o emite para dado real;
    `de_teste()` emite o dos testes sintéticos, marcado (reconferência B-a)."""

    def __init__(self, dados: dict, sintetico: bool = False):
        super().__init__(dados)
        self.sintetico = sintetico

    @classmethod
    def de_teste(cls) -> "Congelamento":
        return cls({"sha256": "sintetico", "pre_registro": "teste"}, sintetico=True)


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _data(valor) -> date:
    return auditor._como_data(valor)


def _mais_tres_meses(d: date) -> date:
    return auditor._mais_tres_meses(d)


def _doc(cd: str, o: dict) -> tuple:
    return (cd, o["conjunto"], str(o["dt_refer"]), int(o["versao"]))


# --- população (§3.2) ---------------------------------------------------------------------

def populacao_v2(ativos: list[dict], trimestres: list[dict]) -> dict:
    """Exclui `ll3_13_%` (o painel já exclui `ll3_09_%` e bancos). Falha fechada."""
    planos = {}
    for linha in (*ativos, *trimestres):
        planos.setdefault(linha["cd_cvm"], linha.get("plano_contas"))
    seguradoras = {p for p in planos.values() if str(p or "").startswith("ll3_13_")}
    novos = sorted(seguradoras - PLANOS_LL3_13_CONHECIDOS)
    if novos:
        raise PlanoDesconhecido(f"plano(s) {novos}: a decisão de 26/09 conhece só "
                                f"{sorted(PLANOS_LL3_13_CONHECIDOS)}")
    excluidas = sorted(c for c, p in planos.items() if str(p or "").startswith("ll3_13_"))
    return {"incluidas": frozenset(planos) - set(excluidas), "excluidas": excluidas,
            "planos_ll3_13": sorted(seguradoras)}


# --- §5.5: estados e regras ----------------------------------------------------------------

def docs_do_trimestre(t: dict) -> list[tuple[tuple, str]]:
    """`[(documento, escala aplicada ao FCO)]`, na ordem dos operandos."""
    operandos = json.loads(t["operandos"])
    escalas = t["escalas_aplicadas"].split("+")
    if len(operandos) != len(escalas):
        raise pp.DefeitoDeFonte(f"{t['cd_cvm']} {t['dt_fim']}: operandos e escalas não pareiam")
    return [(_doc(t["cd_cvm"], o), e) for o, e in zip(operandos, escalas)]


def heterogeneo_sem_veredito(docs, decididos_fco) -> bool:
    """O predicado das regras 1 e 2: escalas aplicadas ao FCO diferentes, com
    algum documento sem veredito decidido para o FCO."""
    return len({e for _, e in docs}) > 1 and any(d not in decididos_fco for d, _ in docs)


def regra_3(doc_ativo: tuple, escala_ativo: str, docs_ttm, decididos: dict) -> bool:
    """`fco_ttm_sobre_ativo` ausente: escala do ativo em D diferente da do FCO de
    algum documento do TTM, e um dos dois lados sem veredito para a própria conta."""
    ativo_decidido = doc_ativo in decididos["ativo"]
    return any(e != escala_ativo and (not ativo_decidido or d not in decididos["fco"])
               for d, e in docs_ttm)


def preparar_trimestres(trimestres: list[dict], decididos: dict,
                        populacao: frozenset) -> dict[str, list[dict]]:
    """Por companhia, os trimestres válidos da população, com o estado da regra 1."""
    por_cia = defaultdict(list)
    for t in trimestres:
        if t["estado"] != "valido" or t["cd_cvm"] not in populacao:
            continue
        docs = docs_do_trimestre(t)
        por_cia[t["cd_cvm"]].append({
            **t, "docs": docs, "ordinal": ordinal_trimestre(t["trimestre"]),
            "dt_ini": _data(t["dt_ini"]), "dt_fim": _data(t["dt_fim"]),
            "disponivel_em": _data(t["disponivel_em"]),
            "estado_v2": ESTADO_REGRA_1 if heterogeneo_sem_veredito(docs, decididos["fco"])
            else "valido",
        })
    for linhas in por_cia.values():
        linhas.sort(key=lambda t: (t["ordinal"], t["dt_ini"], t["dt_fim"]))
    return dict(por_cia)


def _contiguos(linhas: list[dict]) -> bool:
    ordens = [t["ordinal"] for t in linhas]
    return ordens == list(range(ordens[0], ordens[0] + len(ordens)))


def _encadeados(linhas: list[dict]) -> bool:
    return all(b["dt_ini"] == a["dt_fim"] + timedelta(days=1) for a, b in zip(linhas, linhas[1:]))


def _procedencia(t: dict) -> dict:
    return {"trimestre": t["trimestre"], "dt_ini": t["dt_ini"], "dt_fim": t["dt_fim"],
            "dt_receb": t["disponivel_em"], "metodos": t["metodos"],
            "docs": [[*d, e] for d, e in t["docs"]]}


def preparar_ativos(ativos: list[dict], populacao: frozenset) -> dict[str, list[dict]]:
    por_cia = defaultdict(list)
    for a in ativos:
        if a["estado"] != "valido" or a["cd_cvm"] not in populacao:
            continue
        por_cia[a["cd_cvm"]].append({**a, "ordinal": ordinal_trimestre(a["trimestre"]),
                                     "disponivel_em": _data(a["disponivel_em"]),
                                     "doc": (a["cd_cvm"], a["conjunto"], str(a["dt_refer"]),
                                             int(a["versao"]))})
    for linhas in por_cia.values():
        linhas.sort(key=lambda a: a["ordinal"])
    return dict(por_cia)


# --- §6.1: a amostra ----------------------------------------------------------------------

def construir_amostra_v2(trimestres: list[dict], ativos: list[dict], decididos: dict,
                         populacao: frozenset, calcular_rotulo: bool = False,
                         congelamento: dict | None = None) -> tuple[list[dict], dict]:
    """Grade do §6.1, janela do §6.2, regras 1–3 do §5.5. Rótulo só se pedido.

    **C10: somar o rótulo exige o registro do congelamento** (o que
    `verificar_congelamento` devolve). Sem ele, pedir o rótulo levanta — a trava
    participa da decisão, não fica só no chamador (§4.4, regra 7). Os testes
    sintéticos passam um registro explícito.

    Devolve a amostra, ordenada por (companhia, D), e o inventário completo. O
    inventário contém o motivo 11 e a grade: quem publica é que omite (C8).
    """
    if calcular_rotulo and not isinstance(congelamento, Congelamento):
        raise NaoCongelado("o rótulo só é somado com o pré-registro congelado (C9/C10)")
    qs_por_cia = preparar_trimestres(trimestres, decididos, populacao)
    at_por_cia = preparar_ativos(ativos, populacao)
    descartes = Counter({m: 0 for m in MOTIVOS})
    amostra: list[dict] = []
    grade = 0
    chaves_afetadas = 0
    regra3 = 0
    alcancaram_4, perderam_no_5_5 = set(), set()
    for cd in sorted(qs_por_cia):
        qs = qs_por_cia[cd]
        datas = sorted({t["disponivel_em"] for t in qs if t["estado_v2"] == "valido"})
        grade += len(datas)
        # Motivo 1 e identificação de q1, só por datas, com o trimestre do §5.5 no lugar.
        por_q1: dict[tuple, list[date]] = defaultdict(list)
        for d in datas:
            futuros = [t for t in qs if t["dt_ini"] > d]
            q1 = min(futuros, key=lambda t: (t["dt_ini"], t["dt_fim"])) if futuros else None
            if q1 is None or q1["dt_ini"] > _mais_tres_meses(d):
                descartes["sem_q1_identificavel"] += 1
                continue
            por_q1[(q1["dt_ini"], q1["dt_fim"])].append(d)
        # Motivo 2: uma observação por (companhia, q1), a da maior D, sem reposição.
        escolhidas = []
        for chave_q1, ds in sorted(por_q1.items()):
            if len(ds) > 1:
                chaves_afetadas += 1
                descartes["q1_repetido_mantido_o_maior_D"] += len(ds) - 1
            escolhidas.append((max(ds), chave_q1))
        por_ordinal = {t["ordinal"]: t for t in qs}
        por_periodo = {(t["dt_ini"], t["dt_fim"]): t for t in qs}
        for d, chave_q1 in sorted(escolhidas):
            passado = [t for t in qs if t["disponivel_em"] <= d]
            if len(passado) < JANELA:
                descartes["historico_insuficiente"] += 1
                continue
            alcancaram_4.add(cd)
            janela = passado[-JANELA:]
            if any(t["estado_v2"] == ESTADO_REGRA_1 for t in janela):
                descartes["janela_com_trimestre_do_5_5"] += 1
                perderam_no_5_5.add(cd)
                continue
            if not _contiguos(janela):
                descartes["janela_com_lacuna"] += 1
                continue
            if not _encadeados(janela):
                descartes["janela_sem_encadeamento"] += 1
                continue
            q1 = por_periodo[chave_q1]
            # As quatro posições do rótulo pelo ordinal (H1.2). O §5.5 é conferido
            # em todas as que existem ANTES da completude: é a ordem fixa do §6.1.
            posicoes = [q1] + [por_ordinal.get(q1["ordinal"] + k) for k in (1, 2, 3)]
            if any(t is not None and t["estado_v2"] == ESTADO_REGRA_1 for t in posicoes):
                descartes["rotulo_com_trimestre_do_5_5"] += 1
                perderam_no_5_5.add(cd)
                continue
            if any(t is None for t in posicoes):
                descartes["rotulo_incompleto"] += 1
                continue
            rotulo = posicoes
            if not _encadeados(rotulo):
                descartes["rotulo_sem_encadeamento"] += 1
                continue
            docs_janela = [x for t in janela for x in t["docs"]]
            docs_s1 = [x for t in rotulo[:2] for x in t["docs"]]
            docs_s2 = [x for t in rotulo[2:] for x in t["docs"]]
            if any(heterogeneo_sem_veredito(ds, decididos["fco"])
                   for ds in (docs_janela, docs_s1, docs_s2)):
                descartes["regra_2_do_5_5"] += 1
                perderam_no_5_5.add(cd)
                continue
            ultimos4 = janela[-4:]
            fco_ttm = sum(t["valor_reais"] for t in ultimos4)
            if fco_ttm <= 0:
                descartes["fco_ttm_nao_positivo"] += 1
                continue
            disponiveis = [a for a in at_por_cia.get(cd, []) if a["disponivel_em"] <= d]
            ativo = disponiveis[-1] if disponiveis else None
            if ativo is None or not ativo["valor_reais"] or ativo["valor_reais"] <= 0:
                descartes["sem_ativo_disponivel"] += 1
                continue
            serie = [t["valor_reais"] for t in janela]
            sd8 = statistics.stdev(serie)
            ausente_por_regra_3 = regra_3(ativo["doc"], ativo["escala_aplicada"],
                                          [x for t in ultimos4 for x in t["docs"]], decididos)
            regra3 += ausente_por_regra_3
            observacao = {
                "cd_cvm": cd, "D": d.isoformat(), "trimestre_ancora": janela[-1]["trimestre"],
                "q1": q1["trimestre"],
                "fco_ttm_em_D": fco_ttm,
                "sd8_fco_isolado": sd8,
                "fco_ttm_sobre_sd8": (fco_ttm / sd8) if sd8 else None,
                "fco_ttm_sobre_ativo": None if ausente_por_regra_3 else fco_ttm / ativo["valor_reais"],
                "ativo_total_em_D": ativo["valor_reais"],
                "trimestres_com_fco_negativo_nos_ultimos_8": sum(1 for v in serie if v < 0),
                "linhagem": {
                    "janela": [_procedencia(t) for t in janela],
                    "rotulo": [_procedencia(t) for t in rotulo],
                    "ativo": {"trimestre": ativo["trimestre"], "dt_ini": None,
                              "dt_fim": _data(ativo["dt_fim"]), "dt_receb": ativo["disponivel_em"],
                              "doc": list(ativo["doc"]), "escala": ativo["escala_aplicada"]},
                },
            }
            if calcular_rotulo:
                s1 = rotulo[0]["valor_reais"] + rotulo[1]["valor_reais"]
                s2 = rotulo[2]["valor_reais"] + rotulo[3]["valor_reais"]
                observacao["y"] = 1 if (s1 < 0 and s2 < 0) else 0
            amostra.append(observacao)
    finais = Counter(o["cd_cvm"] for o in amostra)
    inventario = {
        "descartes": dict(descartes),
        "grade": grade,
        "q1_repetido_chaves_afetadas": chaves_afetadas,
        "regra_3_fco_ttm_sobre_ativo_ausente": regra3,
        "companhias_antes_da_censura": len(alcancaram_4),
        "companhias_que_perdem_observacao_no_5_5": len(perderam_no_5_5),
        # Definição (emenda B9): perderam ao menos uma data no §5.5 e ficaram sem
        # observação final, por qualquer motivo.
        "companhias_com_perda_no_5_5_e_sem_observacao_final": len(
            {c for c in perderam_no_5_5 if not finais[c]}),
        "observacoes_por_companhia": dict(sorted(finais.items())),
    }
    return amostra, inventario


# --- G0 (§5) ------------------------------------------------------------------------------

def _linhas_do_auditor(ativos: list[dict], trimestres: list[dict], populacao: frozenset):
    fco = [{"cd_cvm": t["cd_cvm"], "trimestre": t["trimestre"], "dt_ini": t["dt_ini"],
            "dt_fim": t["dt_fim"], "fco": t["valor_reais"], "dt_receb": t["disponivel_em"],
            "demonstrativo": t["demonstrativo"], "origem": t["origem"], "versao": t["versao"]}
           for t in trimestres if t["estado"] == "valido" and t["cd_cvm"] in populacao]
    ativo = [{"cd_cvm": a["cd_cvm"], "trimestre": a["trimestre"], "ativo": a["valor_reais"],
              "dt_receb": a["disponivel_em"], "versao": a["versao"], "demonstrativo": "BPA",
              "dt_ini": None, "dt_fim": a["dt_fim"]}
             for a in ativos if a["estado"] == "valido" and a["cd_cvm"] in populacao]
    duracoes = [{"cd_cvm": t["cd_cvm"], "trimestre": t["trimestre"],
                 "dias": (_data(t["dt_fim"]) - _data(t["dt_ini"])).days + 1,
                 "demonstrativo": t["demonstrativo"], "origem": t["origem"]}
                for t in trimestres if t["estado"] == "valido" and t["cd_cvm"] in populacao]
    return fco, ativo, duracoes


def g0_1_v2(trimestres: list[dict], populacao: frozenset) -> dict:
    """§5.1, pela linhagem e sem ler valor: unicidade e nenhum valor que combine
    dois acumulados do MESMO período (a soma MD + MI que a v1 temia)."""
    validos = [t for t in trimestres if t["estado"] == "valido" and t["cd_cvm"] in populacao]
    repetidos = sum(n - 1 for n in Counter((t["cd_cvm"], t["trimestre"]) for t in validos).values()
                    if n > 1)
    mesmo_periodo = 0
    entre_metodos = []
    for t in validos:
        periodos = [(o["dt_ini"], o["dt_fim"]) for o in json.loads(t["operandos"])]
        if len(periodos) != len(set(periodos)):
            mesmo_periodo += 1
        if len(set(t["metodos"].split("+"))) > 1:
            entre_metodos.append(t)
    return {
        "trimestres_validos_repetidos": repetidos,
        "trimestres_que_combinam_o_mesmo_periodo": mesmo_periodo,
        "trimestres_validos_derivados_entre_metodos": len(entre_metodos),
        "companhias_com_derivacao_entre_metodos": len({t["cd_cvm"] for t in entre_metodos}),
        "aprovado": not repetidos and not mesmo_periodo,
    }


def g0_v2(ativos: list[dict], trimestres: list[dict], nulos: dict, pop: dict) -> dict:
    populacao = pop["incluidas"]
    fco, ativo, duracoes = _linhas_do_auditor(ativos, trimestres, populacao)
    g0 = auditor.gate_g0(fco, ativo, duracoes, nulos)
    g0["g0_1_v2"] = g0_1_v2(trimestres, populacao)
    if not g0["g0_1_v2"]["aprovado"]:
        g0["aprovado"] = False
    excluidas = frozenset(pop["excluidas"])
    _, ativo_ex, _ = _linhas_do_auditor(ativos, [], excluidas)
    saltos_ex = auditor.gate_g0([], ativo_ex, [], {}) if ativo_ex else {"g0_3_saltos_de_escala": 0}
    g0["efeito_do_3_2"] = {"companhias_excluidas": pop["excluidas"],
                           "saltos_de_escala_nas_excluidas": saltos_ex["g0_3_saltos_de_escala"],
                           "linhas_de_ativo_validas_nas_excluidas": len(ativo_ex)}
    return g0


def erros_demonstrados(correcoes_por_conta: dict) -> list[dict]:
    corrigidos = {(c["id_doc"], conta) for linhas in correcoes_por_conta.values()
                  for conta, c in linhas.items()}
    return [{**e, "estado": ("corrigido_pelo_manifesto_por_conta"
                             if (e["id_doc"], e["conta"]) in corrigidos else "pendente")}
            for e in ERROS_DEMONSTRADOS]


def _ids(id_doc) -> set[str]:
    """`id_doc` do painel pode ser lista separada por vírgula (cadastro repetido)."""
    return {i for i in str(id_doc or "").split(",") if i}


def uso_dos_erros_demonstrados(erros: list[dict], amostra: list[dict], ativos: list[dict],
                               trimestres: list[dict]) -> list[dict]:
    """Emenda AF3 (28/09), §12-bis: erro demonstrado pendente "não é tolerado por
    caber em limiar nenhum". Conta, por erro, as observações que usam o documento
    na conta demonstrada: como ativo em D (conta `1`) ou pelo FCO na janela ou no
    rótulo (conta `6.01`). Contagem estrutural, sem valor."""
    id_do_ativo = {_doc(a["cd_cvm"], a): _ids(a["id_doc"]) for a in ativos}
    id_do_fco: dict[tuple, set[str]] = defaultdict(set)
    for t in trimestres:
        for o in json.loads(t["operandos"]):
            id_do_fco[_doc(t["cd_cvm"], o)] |= _ids(o["id_doc"])
    saida = []
    for e in erros:
        if e["conta"] == "1":
            n = sum(1 for o in amostra
                    if e["id_doc"] in id_do_ativo.get(tuple(o["linhagem"]["ativo"]["doc"]), ()))
        elif e["conta"] == "6.01":
            n = sum(1 for o in amostra if any(
                e["id_doc"] in id_do_fco.get(d, ())
                for d, _ in _docs_da_linhagem([*o["linhagem"]["janela"], *o["linhagem"]["rotulo"]])))
        else:
            raise pp.DefeitoDeFonte(f"erro demonstrado na conta {e['conta']}: sem regra de uso")
        saida.append({**e, "observacoes_que_usam": n})
    return saida


# --- G0.5 e G1 (§§5.5, 6) ------------------------------------------------------------------

def _docs_da_linhagem(linhas: list[dict]) -> list[tuple[tuple, str]]:
    return [(tuple(x[:4]), x[4]) for t in linhas for x in t["docs"]]


def gate_g0_5(amostra: list[dict], decididos: dict, erros_usados: list[dict] = ()) -> dict:
    """Uso zero, recalculado da LINHAGEM e dos vereditos — não das marcas da construção.
    AF3 (28/09): uso de documento com erro demonstrado PENDENTE também reprova."""
    violacoes = Counter({"regra_1": 0, "regra_2": 0, "regra_3": 0,
                         "erro_demonstrado_pendente": sum(
                             e["observacoes_que_usam"] for e in erros_usados
                             if e["estado"] == "pendente")})
    for obs in amostra:
        janela, rotulo = obs["linhagem"]["janela"], obs["linhagem"]["rotulo"]
        if any(heterogeneo_sem_veredito(_docs_da_linhagem([t]), decididos["fco"])
               for t in (*janela, *rotulo)):
            violacoes["regra_1"] += 1
        if any(heterogeneo_sem_veredito(_docs_da_linhagem(parte), decididos["fco"])
               for parte in (janela, rotulo[:2], rotulo[2:])):
            violacoes["regra_2"] += 1
        ativo = obs["linhagem"]["ativo"]
        if obs["fco_ttm_sobre_ativo"] is not None and regra_3(
                tuple(ativo["doc"]), ativo["escala"], _docs_da_linhagem(janela[-4:]), decididos):
            violacoes["regra_3"] += 1
    resultado = {"gate": "G0.5", "violacoes": dict(violacoes), "limiar": "0 (uso), amostra não vazia",
                 "aprovado": bool(amostra) and not any(violacoes.values())}
    if not amostra:
        resultado["motivo"] = "amostra vazia: G0.5 não aprova por ausência de dado (§4.4 regra 4)"
    return resultado


def gate_g1_v2(amostra: list[dict], descartes_publicaveis: dict, provas: dict) -> dict:
    """G1 da v1 (pela linhagem), mais (companhia, q1) única e G1.4 por conta."""
    g1 = auditor.gate_g1(amostra, descartes_publicaveis)
    pares = Counter((o["cd_cvm"], o["q1"]) for o in amostra)
    g1["q1_repetido"] = sum(n - 1 for n in pares.values() if n > 1)
    tardias = 0
    for obs in amostra:
        d = _data(obs["D"])
        docs_fco = {tuple(x[:4]) for t in obs["linhagem"]["janela"] for x in t["docs"]}
        if any(k in provas["fco"] and provas["fco"][k] > d for k in docs_fco) or \
                (tuple(obs["linhagem"]["ativo"]["doc"]) in provas["ativo"]
                 and provas["ativo"][tuple(obs["linhagem"]["ativo"]["doc"])] > d):
            tardias += 1
    g1["g1_4_prova_de_escala_publicada_depois_de_D"] = tardias
    if g1["q1_repetido"] or tardias:
        g1["aprovado"] = False
    return g1


# --- T2 (§8.1) ---------------------------------------------------------------------------

def teste_t2_v2(amostra: list[dict]) -> dict:
    """Lacuna AUC agregada − intra, com piso de 30 companhias e zona de bootstrap."""
    usaveis = [r for r in amostra if r["fco_ttm_sobre_sd8"] is not None]
    escores = [-r["fco_ttm_sobre_sd8"] for r in usaveis]
    if len(set(escores)) <= 1:
        raise auditor.EscoreDegenerado("escore B1 constante: AUC 0,5 por construção")
    eventos = [r["y"] for r in usaveis]
    por_cia: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for s, y, r in zip(escores, eventos, usaveis):
        por_cia[r["cd_cvm"]].append((s, y))
    auc_cia = {}
    for cd, pares in por_cia.items():
        if len({y for _, y in pares}) == 2:
            auc_cia[cd] = auditor._auc([s for s, _ in pares], [y for _, y in pares])
    agregada = auditor._auc(escores, eventos)
    base = {
        "teste": "T2", "escore": "fco_ttm_sobre_sd8", "sentido": -1,
        "companhias_com_os_dois_rotulos": len(auc_cia),
        "companhias_na_amostra": len(por_cia),
        "observacoes_nas_companhias_com_os_dois_rotulos": sum(len(por_cia[c]) for c in auc_cia),
        "limiar": f"< {auditor.T2_LACUNA}", "piso_de_companhias": PISO_T2,
    }
    if agregada is None or len(auc_cia) < PISO_T2:
        return {**base, "aprovado": False, "reprova_numericamente": False, "indecidivel": True,
                "motivo": f"{len(auc_cia)} companhias com os dois rótulos, abaixo do piso {PISO_T2}"}
    intra = statistics.fmean(auc_cia.values())
    lacuna = agregada - intra
    chaves = sorted(por_cia)
    aleatorio = random.Random(auditor.SEMENTE)
    lacunas = []
    for _ in range(auditor.REAMOSTRAGENS):
        sorteadas = [aleatorio.choice(chaves) for _ in chaves]
        pares = [p for c in sorteadas for p in por_cia[c]]
        agg = auditor._auc([s for s, _ in pares], [y for _, y in pares])
        intras = [auc_cia[c] for c in sorteadas if c in auc_cia]
        if agg is None or not intras:
            continue
        lacunas.append(agg - statistics.fmean(intras))
    base.update(auc_agregada=round(agregada, 4), auc_intra_companhia=round(intra, 4),
                lacuna=round(lacuna, 4), reamostragens_validas=len(lacunas))
    if len(lacunas) < auditor.MINIMO_DE_REAMOSTRAGENS_VALIDAS:
        return {**base, "aprovado": False, "reprova_numericamente": False, "indecidivel": True,
                "motivo": "reamostragens válidas abaixo de 40"}
    lacunas.sort()
    frequencia = sum(1 for x in lacunas if x >= auditor.T2_LACUNA) / len(lacunas)
    base.update(frequencia_bootstrap_de_lacuna_no_limiar=round(frequencia, 4),
                ic95=auditor._intervalo(lacunas))
    if lacuna >= auditor.T2_LACUNA:
        return {**base, "aprovado": False, "reprova_numericamente": True, "indecidivel": False}
    if frequencia > FREQUENCIA_MAXIMA_T2:
        return {**base, "aprovado": False, "reprova_numericamente": False, "indecidivel": True,
                "motivo": "lacuna abaixo do limiar, instável no bootstrap"}
    return {**base, "aprovado": True, "reprova_numericamente": False, "indecidivel": False}


def veredito_v2(g0: dict, g0_5: dict, g1: dict, t1: dict | None, t2: dict | None,
                baselines: dict | None) -> str:
    """§10: REPROVADO EM G0/G1 · REJEITADO · INDECIDÍVEL · PRONTO PARA CHALLENGER."""
    if not (g0["aprovado"] and g0_5["aprovado"] and g1["aprovado"]):
        return "REPROVADO EM G0/G1"
    t1, t2, baselines = t1 or {}, t2 or {}, baselines or {}
    if t1.get("reprova_numericamente") or t2.get("reprova_numericamente"):
        return "REJEITADO"
    if t1.get("aprovado") and t2.get("aprovado") and baselines.get("todos_completos"):
        return "PRONTO PARA CHALLENGER"
    return "INDECIDIVEL"


# --- publicação antes do congelamento (C8) ------------------------------------------------

def descartes_publicaveis(inventario: dict) -> dict:
    return {m: ("omitido por O1" if m == MOTIVO_OMITIDO else n)
            for m, n in inventario["descartes"].items()}


def so_unidade(ativos: list[dict], trimestres: list[dict]) -> set[str]:
    escalas = defaultdict(set)
    for a in ativos:
        escalas[a["cd_cvm"]].add(a["escala_declarada"])
    for t in trimestres:
        escalas[t["cd_cvm"]].update(t["escalas_declaradas"].split("+"))
    return {c for c, e in escalas.items() if e == {"UNIDADE"}}


def publicacao_do_5_5(trimestres_prep: dict, amostra: list[dict], inventario: dict,
                      so_u: set[str]) -> dict:
    por_config, por_cia = Counter(), Counter()
    for cd, qs in trimestres_prep.items():
        for t in qs:
            if t["estado_v2"] == ESTADO_REGRA_1:
                declaradas = "declaradas_diferentes" if len(set(t["escalas_declaradas"].split("+"))) > 1 \
                    else "declaradas_iguais"
                aplicadas = "aplicadas_diferentes" if len(set(t["escalas_aplicadas"].split("+"))) > 1 \
                    else "aplicadas_iguais"
                por_config[f"{declaradas}|{aplicadas}"] += 1
                por_cia[cd] += 1
    base = inventario["companhias_antes_da_censura"] or 1
    return {
        "regra_1_trimestres_por_configuracao": dict(sorted(por_config.items())),
        "regra_1_trimestres_por_companhia": dict(sorted(por_cia.items())),
        "observacoes_perdidas": {m: inventario["descartes"][m] for m in MOTIVOS_DO_5_5},
        "companhias_que_perdem_observacao": inventario["companhias_que_perdem_observacao_no_5_5"],
        "companhias_com_perda_no_5_5_e_sem_observacao_final":
            inventario["companhias_com_perda_no_5_5_e_sem_observacao_final"],
        "companhias_antes_da_censura": inventario["companhias_antes_da_censura"],
        "fracao_que_perde": round(inventario["companhias_que_perdem_observacao_no_5_5"] / base, 4),
        "fracao_com_perda_e_sem_observacao_final": round(
            inventario["companhias_com_perda_no_5_5_e_sem_observacao_final"] / base, 4),
        "regra_3_fco_ttm_sobre_ativo_ausente": inventario["regra_3_fco_ttm_sobre_ativo_ausente"],
        "amostra_final_em_companhias_so_unidade": {
            "observacoes": sum(1 for o in amostra if o["cd_cvm"] in so_u),
            "companhias": len({o["cd_cvm"] for o in amostra if o["cd_cvm"] in so_u})},
    }


def folga_do_motivo_11(trimestres: list[dict], decididos: dict, pop: dict) -> int:
    """Reconferência B-b. Os números publicados dão o motivo 11 somado a duas
    parcelas que NÃO se publicam: as colisões de disponibilidade (linhas utilizáveis
    da mesma companhia com a mesma data) e as linhas válidas de FCO das companhias
    excluídas pelo §3.2 (o inventário do painel conta o universo inteiro). Se as
    duas forem zero, a subtração é exata e o artefato não pode sair. Só em memória."""
    prep = preparar_trimestres(trimestres, decididos, pop["incluidas"])
    utilizaveis = sum(1 for qs in prep.values() for q in qs if q["estado_v2"] == "valido")
    grade = sum(len({q["disponivel_em"] for q in qs if q["estado_v2"] == "valido"})
                for qs in prep.values())
    excluidas = set(pop["excluidas"])
    das_excluidas = sum(1 for q in trimestres if q["estado"] == "valido" and q["cd_cvm"] in excluidas)
    return (utilizaveis - grade) + das_excluidas


#: Emenda C8 (27/09): o vocabulário fechado dos estados que o inventário do painel
#: conta. O FCO acumulado não tem constante no painel; os três estados são os que
#: `pp.construir_fco` atribui.
ESTADOS_DO_INVENTARIO = {
    "fco_trimestral_por_estado": pp.ESTADOS_FCO,
    "ativo_por_estado": pp.ESTADOS_ATIVO,
    "fco_acumulado_por_estado": ("ok", "valor_nulo", "conflito_de_declaracoes"),
}


def inventario_publicavel(inventario: dict) -> dict:
    """Emenda C8 (27/09). O inventário do painel conta linhas POR ESTADO, e um estado
    do FCO trimestral se chama `lacuna` — o mesmo nome da estatística do T2 que a
    guarda proíbe como chave. O estado é dado, não chave de resultado: sai como
    lista de pares `{estado, linhas, companhias}`, na ordem do vocabulário, e
    estado fora do vocabulário fechado derruba a publicação. A guarda não muda."""
    saida = {}
    for chave, valor in inventario.items():
        vocabulario = ESTADOS_DO_INVENTARIO.get(chave)
        if vocabulario is None:
            saida[chave] = valor
            continue
        desconhecidos = sorted(set(valor) - set(vocabulario))
        if desconhecidos:
            raise PublicacaoInsegura(f"{chave}: estado(s) fora do vocabulário {desconhecidos}")
        saida[chave] = [{"estado": e, **valor[e]} for e in vocabulario if e in valor]
    return saida


def verificar_publicavel(objeto, caminho="") -> None:
    """C8: nenhuma chave proibida em nível nenhum do artefato estrutural."""
    if isinstance(objeto, dict):
        proibidas = CHAVES_PROIBIDAS_ANTES_DO_CONGELAMENTO & set(objeto)
        if proibidas:
            raise AssertionError(f"O1: chaves {sorted(proibidas)} em {caminho or 'raiz'}")
        for k, v in objeto.items():
            verificar_publicavel(v, f"{caminho}.{k}")
    elif isinstance(objeto, list):
        for i, v in enumerate(objeto):
            verificar_publicavel(v, f"{caminho}[{i}]")


def estrutura(ativos, trimestres, nulos, decididos, provas, correcoes_por_conta) -> dict:
    """G0, amostra sem rótulo, G0.5 e G1 — o que o modo estrutural calcula."""
    pop = populacao_v2(ativos, trimestres)
    g0 = g0_v2(ativos, trimestres, nulos, pop)
    g0["erros_demonstrados"] = erros_demonstrados(correcoes_por_conta)
    amostra, inventario = construir_amostra_v2(trimestres, ativos, decididos, pop["incluidas"])
    if any("y" in o for o in amostra):
        raise AssertionError("O1: a construção sem rótulo devolveu y")
    g0["g0_1_v2"]["observacoes_que_usam_derivacao_entre_metodos"] = sum(
        1 for o in amostra if any(len(set(t["metodos"].split("+"))) > 1
                                  for t in (*o["linhagem"]["janela"], *o["linhagem"]["rotulo"])))
    g0["erros_demonstrados"] = uso_dos_erros_demonstrados(g0["erros_demonstrados"], amostra,
                                                          ativos, trimestres)
    g0_5 = gate_g0_5(amostra, decididos, g0["erros_demonstrados"])
    g1 = gate_g1_v2(amostra, descartes_publicaveis(inventario), provas)
    prep = preparar_trimestres(trimestres, decididos, pop["incluidas"])
    return {"populacao": pop, "g0": g0, "g0_5": g0_5, "g1": g1, "amostra": amostra,
            "inventario": inventario,
            "publicacao_5_5": publicacao_do_5_5(prep, amostra, inventario,
                                                so_unidade(ativos, trimestres))}


def artefato_estrutural(e: dict) -> dict:
    """O que se grava antes do congelamento: sem rótulo, sem grade, sem motivo 11."""
    inv = e["inventario"]
    g1 = {k: v for k, v in e["g1"].items() if k != "descartes"}
    # Motivo 11 (achado da auditoria de 27/09): linhas válidas de FCO da população
    # menos as censuradas pela regra 1, menos os motivos publicados, menos as
    # observações finais dá o motivo 11 EXATO quando não há duas linhas da mesma
    # companhia com a mesma disponibilidade. O número não sai antes do congelamento.
    g0 = {k: v for k, v in e["g0"].items() if k not in PUBLICACAO_RETIDA_NO_G0}
    saida = {
        "modo": "estrutural",
        "populacao": {"excluidas_ll3_13": e["populacao"]["excluidas"],
                      "planos_ll3_13": e["populacao"]["planos_ll3_13"],
                      "companhias_incluidas": len(e["populacao"]["incluidas"])},
        "g0": g0, "g0_5": {**e["g0_5"], "publicacao": e["publicacao_5_5"]}, "g1": g1,
        "amostra_sem_rotulo": {
            "observacoes": len(e["amostra"]),
            "companhias": len({o["cd_cvm"] for o in e["amostra"]}),
            "observacoes_por_companhia": inv["observacoes_por_companhia"],
            "descartes_por_motivo": {m: n for m, n in descartes_publicaveis(inv).items()
                                     if m != MOTIVO_OMITIDO},
            "motivo_11": "omitido por O1 até o congelamento",
            "q1_repetido_chaves_afetadas": inv["q1_repetido_chaves_afetadas"],
            "ordem_dos_motivos": list(MOTIVOS),
        },
        "veredito_estrutural": (
            "G0, G0.5 E G1 APROVADOS" if e["g0"]["aprovado"] and e["g0_5"]["aprovado"]
            and e["g1"]["aprovado"] else "REPROVADO EM G0/G1"),
    }
    verificar_publicavel(saida)
    return saida


# --- trava do congelamento (C9) -----------------------------------------------------------

#: AF1 (28/09): o que conta como linha de status — com ou sem negrito, dentro de
#: citação ou de item de lista, sem distinguir caixa…
LINHA_DE_STATUS = re.compile(r"^[>\s\-*+]*status\s*\**\s*:", re.IGNORECASE)
#: …e a única forma aceita no congelado, casada positivamente em TODAS elas.
STATUS_CONGELADO = re.compile(r"^\*\*Status: CONGELADO em \d{4}-\d{2}-\d{2}\b")


def verificar_congelamento(caminho: Path, sha_informado: str, pins: dict[str, str]) -> dict:
    """C9: nome e título sem RASCUNHO, linhas de status só CONGELADO (AF1), hash
    igual ao informado e os pins no texto."""
    if "RASCUNHO" in caminho.name.upper():
        raise NaoCongelado(f"{caminho.name}: o nome ainda diz RASCUNHO")
    texto = caminho.read_text(encoding="utf-8")
    if "RASCUNHO" in (texto.splitlines() or [""])[0].upper():
        raise NaoCongelado("o título ainda diz RASCUNHO")
    # AF1 (28/09): a marca do rascunho real está na linha de status, não no título.
    # Toda linha de status tem de declarar congelamento com data: acrescentar uma
    # linha CONGELADO e manter a de RASCUNHO não congela.
    linhas = [unicodedata.normalize("NFC", l.strip()) for l in texto.splitlines()]
    status = [l for l in linhas if LINHA_DE_STATUS.match(l)]
    if not status:
        raise NaoCongelado("sem linha de status (`**Status: CONGELADO em AAAA-MM-DD …`)")
    fora = [l for l in status if not STATUS_CONGELADO.match(l)]
    if fora:
        raise NaoCongelado(f"a linha de status não declara congelamento: {fora[0][:80]}")
    obtido = sha256(caminho)
    if obtido != sha_informado:
        raise NaoCongelado("SHA-256 do pré-registro diferente do informado")
    faltam = sorted(nome for nome, h in pins.items() if not h or h not in texto)
    if faltam:
        raise NaoCongelado(f"pins ausentes do pré-registro congelado: {faltam}")
    return Congelamento({"pre_registro": str(caminho), "sha256": obtido,
                         "pins": dict(sorted(pins.items()))})


# --- execução no dado real -----------------------------------------------------------------

#: M3 (auditoria de 27/09): TODO o código que mede entra no pin do congelamento —
#: T1, AUC, baselines, limiares, sementes e gates vivem no auditor de 11/09.
CODIGO_DE_MEDICAO = (
    "scripts/executor_v2_rank03b.py", "scripts/auditar_rank03b_consumo_operacional.py",
    "scripts/painel_pesquisa_rank03b.py", "scripts/gates_painel_pesquisa_rank03b.py",
    "scripts/fonte_zip_cvm.py", "scripts/correcoes_por_conta_rank03b.py",
    "scripts/rota_prova_rank03b.py", "scripts/fonte_rad_cvm.py",
    "scripts/adjudicar_escala_rank03b.py", "scripts/piloto_fonte_rad_rank03b.py",
    "src/normalizacao.py",
)


def _codigo() -> dict[str, str]:
    return {a: sha256(RAIZ / a) for a in CODIGO_DE_MEDICAO}


def digest_do_codigo() -> str:
    """Um hash só sobre o código de medição inteiro (M3)."""
    corpo = "\n".join(f"{a}:{h}" for a, h in sorted(_codigo().items()))
    return hashlib.sha256(corpo.encode()).hexdigest()


class EntradaIncoerente(Exception):
    """Evidência, manifesto e painel não descrevem a mesma coisa (M1, M2, B6)."""


def conferir_decididos_aplicados(painel: pp.Painel, escalas_decididas: dict) -> int:
    """M1: todo (documento, conta) decidido tem de ter, no painel, a escala que a
    prova decidiu. Uma correção provada fora do manifesto — ou um documento
    confirmado que recebeu outra escala — faria o §5.5 tratar como adjudicado um
    valor na escala errada."""
    for (chave, conta), escala in escalas_decididas.items():
        doc = painel.documentos.get(chave)
        if doc is None or doc.escala_de(conta).aplicada != escala:
            raise EntradaIncoerente(
                f"{chave} {conta}: a prova decide {escala}, o painel aplica "
                f"{None if doc is None else doc.escala_de(conta).aplicada}")
    return len(escalas_decididas)


def carregar_entradas(pasta_rota: Path | None, manifesto_por_conta: Path | None) -> dict:
    """Painel construído dos ZIPs pinados, com as correções validadas (A2)."""
    import duckdb

    from scripts import correcoes_por_conta_rank03b as pc
    from scripts import fonte_zip_cvm as fz
    from scripts import gates_painel_pesquisa_rank03b as gates
    from scripts import rota_prova_rank03b as rota

    if (pasta_rota is None) != (manifesto_por_conta is None):
        # M2: um sem o outro seria ignorado em silêncio, e o pin proposto
        # descreveria um painel que não o aplicou.
        raise EntradaIncoerente("a rota de prova e o manifesto por conta entram juntos, ou nenhum")
    legado = gates.carregar_correcoes(gates.CORRECOES)
    decididos = {"ativo": set(), "fco": set()}
    escalas: dict = {}
    por_conta: dict = {}
    entradas_rota = "SEM ROTA DE PROVA"
    if pasta_rota is not None:
        v = rota.vereditos_por_conta(pasta_rota)
        decididos = {"ativo": v["ativo"], "fco": v["fco"]}
        escalas = v["escalas"]
        entradas_rota = {"regra": rota.REGRA, "sha256_evidencias": v["sha256_evidencias"],
                         "sha256_conferencia": v["sha256_conferencia"]}
        por_conta = pc.carregar(manifesto_por_conta, pasta_rota, chaves_do_legado=frozenset(legado))
        # B6: só correção validada entra, e ninguém a mudou depois.
        if not isinstance(por_conta, pc.CorrecoesPorConta) or \
                por_conta.conteudo_sha256 != por_conta.impressao() or \
                por_conta.origem_sha256 != sha256(manifesto_por_conta):
            raise EntradaIncoerente("correções por conta não validadas ou alteradas")
    con = duckdb.connect(":memory:")
    zips = fz.extrair(con)
    hash_treino = pp.preparar_universo(con)
    painel = pp.construir(con, legado, por_conta)
    conferidos = conferir_decididos_aplicados(painel, escalas)
    provas_legado = gates.datas_das_provas(con, legado)
    recepcao = pp.recepcao_por_id_doc(con)
    # B2: a prova de uma correção legada (por documento) vale para as duas contas.
    provas = {"ativo": dict(provas_legado), "fco": dict(provas_legado)}
    for chave, linhas in por_conta.items():
        for conta, linha in linhas.items():
            provas[pp.CONTAS_DA_CORRECAO[conta]][chave] = pp.data_da_prova(linha, recepcao)
    # c3 do lote C confere a disponibilidade do FCO: a prova do FCO por conta entra.
    gates.verificar_falsificacoes(painel, con, {**provas_legado, **provas["fco"]})
    return {
        "painel": painel, "decididos": decididos, "provas": provas, "por_conta": por_conta,
        "nulos": gates.nulos(painel),
        "entradas": {
            "zips_sha256": zips, "cvm_treino_sha256": hash_treino,
            "manifesto_aquisicao_sha256": sha256(RAIZ / "artefatos" / "painel_pesquisa_rank03b"
                                                 / "rad" / "manifesto_aquisicao.jsonl"),
            "correcoes_por_documento": {"sha256": sha256(gates.CORRECOES), "linhas": len(legado)},
            "correcoes_por_conta": ({"caminho": (str(manifesto_por_conta.relative_to(RAIZ))
                                                 if manifesto_por_conta.is_relative_to(RAIZ)
                                                 else str(manifesto_por_conta)),
                                     "sha256": sha256(manifesto_por_conta),
                                     "linhas": sum(len(v) for v in por_conta.values())}
                                    if manifesto_por_conta else "SEM CORREÇÕES POR CONTA"),
            "rota": entradas_rota,
            "decididos_conferidos_contra_o_painel": conferidos,
        },
    }


def pins_do_congelamento(e: dict | None = None, digest_do_painel: str | None = None,
                         manifesto_por_conta: Path | None = None,
                         pasta_rota: Path | None = None) -> dict[str, str]:
    """C9 com M3: o digest do painel, o manifesto, as evidências e o registro da
    conferência da rota de prova, o ADENDO relido do disco e o código de medição
    inteiro. A conferência entra por nome (§13), e não só pela coluna
    `sha256_conferencia` do manifesto, que um manifesto vazio não carregaria."""
    from scripts import rota_prova_rank03b as rota

    if e is not None:
        digest_do_painel = e["painel"].digest["conjunto"]
        por_conta = e["entradas"]["correcoes_por_conta"]
        da_rota = e["entradas"]["rota"]
        manifesto = por_conta["sha256"] if isinstance(por_conta, dict) else ""
        evidencias = da_rota["sha256_evidencias"] if isinstance(da_rota, dict) else ""
        conferencia = da_rota["sha256_conferencia"] if isinstance(da_rota, dict) else ""
    else:
        manifesto = sha256(manifesto_por_conta) if manifesto_por_conta else ""
        evidencias = sha256(pasta_rota / "evidencias.jsonl") if pasta_rota else ""
        conferencia = sha256(pasta_rota / "conferencia.json") if pasta_rota else ""
    adendo = sha256(rota.ADENDO_O1)
    if adendo != rota.ADENDO_O1_SHA256:
        raise NaoCongelado("o adendo ao O1 no disco não é o fixado")
    pins = {"manifesto_por_conta": manifesto, "evidencias_da_rota": evidencias,
            "conferencia_da_rota": conferencia, "adendo_o1": adendo,
            "codigo_de_medicao": digest_do_codigo()}
    if digest_do_painel is not None:
        pins["digest_do_painel"] = digest_do_painel
    return pins


def executar_estrutural(pasta_rota: Path | None, manifesto_por_conta: Path | None,
                        destino: Path = DESTINO, destino_painel: Path = DESTINO_PAINEL) -> dict:
    e = carregar_entradas(pasta_rota, manifesto_por_conta)
    p = e["painel"]
    resultado = estrutura(p.ativo, p.fco_trimestral, e["nulos"], e["decididos"], e["provas"],
                          e["por_conta"])
    if folga_do_motivo_11(p.fco_trimestral, e["decididos"], resultado["populacao"]) <= 0:
        raise PublicacaoInsegura("sem folga: o artefato recomporia o motivo 11 (O1)")
    saida = {
        "executor": "scripts/executor_v2_rank03b.py", "codigo_sha256": _codigo(),
        "digest_do_codigo_de_medicao": digest_do_codigo(),
        "contrato": str(CONTRATO.relative_to(RAIZ)), "contrato_sha256": sha256(CONTRATO),
        "pre_registro_rascunho_sha256": sha256(PRE_REGISTRO_RASCUNHO),
        "entradas": e["entradas"], "digest_do_painel": p.digest,
        "inventario_do_painel": inventario_publicavel(p.inventario),
        "pins_propostos_para_o_congelamento": pins_do_congelamento(e),
        **artefato_estrutural(resultado),
    }
    verificar_publicavel(saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "estrutural.json").write_text(
        json.dumps(saida, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    pp.gravar(p, destino_painel / "painel.duckdb",
              {k: saida[k] for k in ("contrato", "entradas", "codigo_sha256", "digest_do_painel")})
    return saida


def executar_medicao(pre_registro: Path, sha_informado: str, pasta_rota: Path,
                     manifesto_por_conta: Path, destino: Path = DESTINO) -> dict:
    """C9: só com o pré-registro congelado. G0/G1 sem rótulo; `y` só se aprovarem."""
    if (destino / "medicao.json").exists():
        raise FileExistsError("medicao.json já existe: a medição não é refeita sobre a mesma saída")
    verificar_congelamento(pre_registro, sha_informado, pins_do_congelamento(
        manifesto_por_conta=manifesto_por_conta, pasta_rota=pasta_rota))
    e = carregar_entradas(pasta_rota, manifesto_por_conta)
    congelamento = verificar_congelamento(pre_registro, sha_informado, pins_do_congelamento(e))
    if congelamento.sintetico:
        raise NaoCongelado("registro de teste não mede dado real")
    p = e["painel"]
    r = estrutura(p.ativo, p.fco_trimestral, e["nulos"], e["decididos"], e["provas"], e["por_conta"])
    saida = {"modo": "medicao", "congelamento": congelamento, "codigo_sha256": _codigo(),
             "entradas": e["entradas"], "digest_do_painel": p.digest,
             "estrutura": artefato_estrutural(r)}
    t1 = t2 = baselines = None
    if r["g0"]["aprovado"] and r["g0_5"]["aprovado"] and r["g1"]["aprovado"]:
        pop = r["populacao"]
        com_rotulo, _ = construir_amostra_v2(p.fco_trimestral, p.ativo, e["decididos"],
                                             pop["incluidas"], calcular_rotulo=True,
                                             congelamento=congelamento)
        if [(o["cd_cvm"], o["D"]) for o in com_rotulo] != [(o["cd_cvm"], o["D"]) for o in r["amostra"]]:
            raise AmostraDivergente("as chaves (companhia, D) mudaram ao somar o rótulo")
        try:
            t1 = auditor.teste_t1(com_rotulo)
        except auditor.AmostraInsuficiente as erro:
            t1 = {"teste": "T1", "aprovado": False, "indecidivel": True, "reprova_em_aberto": str(erro)}
        try:
            t2 = teste_t2_v2(com_rotulo)
        except auditor.EscoreDegenerado as erro:
            t2 = {"teste": "T2", "aprovado": False, "indecidivel": True, "reprova_em_aberto": str(erro)}
        baselines = auditor.medir_baselines(com_rotulo)
        saida.update(taxa_do_evento=round(statistics.fmean(o["y"] for o in com_rotulo), 4),
                     t1=t1, t2=t2, baselines=baselines,
                     descartes_completos=r["inventario"]["descartes"],
                     grade=r["inventario"]["grade"])
    saida["veredito"] = veredito_v2(r["g0"], r["g0_5"], r["g1"], t1, t2, baselines)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "medicao.json").write_text(
        json.dumps(saida, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return saida


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rota", type=Path, default=None,
                        help="pasta da ROTA-1 (evidências e conferência)")
    parser.add_argument("--correcoes-por-conta", type=Path, default=None)
    parser.add_argument("--medir", action="store_true")
    parser.add_argument("--pre-registro", type=Path, default=None)
    parser.add_argument("--sha256", default=None)
    args = parser.parse_args(argv)
    if args.medir:
        if not (args.pre_registro and args.sha256 and args.rota and args.correcoes_por_conta):
            raise NaoCongelado("--medir exige --pre-registro, --sha256, --rota e --correcoes-por-conta")
        saida = executar_medicao(args.pre_registro, args.sha256, args.rota, args.correcoes_por_conta)
        print(f"VEREDITO: {saida['veredito']}")
        return 0
    saida = executar_estrutural(args.rota, args.correcoes_por_conta)
    g0 = saida["g0"]
    print(f"{saida['veredito_estrutural']}")
    print(f"  G0.3: {g0['g0_3_saltos_de_escala']} saltos ({g0['g0_3_fracao']:.4%}); "
          f"G0.5: {saida['g0_5']['violacoes']}; G1: {saida['g1']['aprovado']}")
    print(f"  amostra sem rótulo: {saida['amostra_sem_rotulo']['observacoes']} observações em "
          f"{saida['amostra_sem_rotulo']['companhias']} companhias")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
