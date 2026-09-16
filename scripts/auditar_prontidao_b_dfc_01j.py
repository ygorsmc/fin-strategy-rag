"""Auditoria de prontidão do candidato B-DFC-01J-M, custo zero e sem rede.

Executa, na ordem e com os limiares congelados em
`resultados/pre_registro_b_dfc_01j_modelo_2026-09-09.md`, os gates G0–G3 e os
testes T1/T2 sobre a série de J produzida pela extensão da janela.

**Nenhum modelo é carregado aqui.** O script responde uma pergunta anterior à
do modelo: a série sustenta um componente aprendido? Gate reprovado interrompe
a cadeia — não se mede o seguinte, exatamente como o §3.7 exige.

Reprova em ABERTO é proibido: amostra insuficiente levanta erro, nunca vira
aprovação. É a lição do auditor do Rank 3, que devolvia "T1 aprovado" sobre
amostra vazia porque `NaN >= 0,15` é `False` (AGENTS.md §3.14).
"""

from __future__ import annotations

import datetime
import json
import math
import random
import statistics
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SERIE = RAIZ / "artefatos" / "b_dfc_01j" / "extensao" / "j_por_periodo.jsonl"
RESUMO_EXTENSAO = RAIZ / "artefatos" / "b_dfc_01j" / "extensao" / "resumo.json"
DESTINO = RAIZ / "artefatos" / "b_dfc_01j" / "prontidao"

#: Limiares do pré-registro. Estão aqui como constantes nomeadas para que
#: mudá-los apareça no diff — mudar limiar depois de medir invalida o
#: pré-registro inteiro (§7 dele).
LARGURA_MAXIMA_DA_POPULACAO = 0.05
G2_RUIDO_SOBRE_SINAL = 0.10
G3_MELHORIA_DETECTAVEL = 0.20
T1_AMPLITUDE = 0.15
T2_LACUNA = 0.12
#: Poder 80%, α=0,05, teste bilateral pareado: (1,96 + 0,84) desvios-padrão.
FATOR_DE_PODER = 2.80
MINIMO_PARA_QUINTIS = 25
MINIMO_DE_CLUSTERS = 3
#: O §4 do pré-registro exige B3 (meta Selic point-in-time) como benchmark
#: econômico e diz que sem ele não há aprovação com B0–B2 apenas. A série
#: existe em fonte pública (SGS 432 do BCB) mas NÃO está integrada nem
#: validada aqui. Achado F10: enquanto isto for False, G3 não aprova — antes
#: a exigência era só texto no JSON e não travava nada.
B3_EXECUTADO = False
#: Contrato C6-bis (conferência independente de 11/09, achado R-C6). O achado
#: F3 estabeleceu que a conta de poder reamostra a DISPERSÃO DA PERDA do
#: baseline eleito, e não a DIFERENÇA PAREADA entre desafiante e baseline —
#: que é a quantidade da qual o poder depende. Enquanto isto for False, G3 não
#: aprova, **mesmo que B3 passe a existir e mesmo que a melhoria detectável
#: caiba no limiar**.
#:
#: Por que uma constante e não um `False` embutido na expressão: o veto fica
#: legível no artefato, a contraprova exercita as quatro combinações com B3 sem
#: editar código, e o dia em que F3 for redesenhado a liberação é UMA LINHA
#: DECLARADA — não a remoção de um literal escondido dentro de um `and`.
#:
#: A onda C1–C6 marcou o cálculo como inválido e deixou a decisão intacta: o
#: gate declarava o próprio cálculo inválido e continuava aprovando por ele.
#: Isso é etiqueta, não quarentena — e era o achado F10 repetido dentro do
#: contrato escrito para corrigi-lo.
PODER_REDESENHADO_APOS_F3 = False


class ReprovaEmAberto(Exception):
    """Amostra insuficiente para decidir. NUNCA é aprovação."""


class ErroDeUnidade(Exception):
    """Unidade ausente ou desconhecida na série de J.

    **Deliberadamente NÃO é `ReprovaEmAberto`.** Amostra insuficiente é um
    estado legítimo do mundo e entra na cadeia como gate reprovado com motivo;
    unidade que não dá para interpretar é DEFEITO DE DADO, e virar "gate
    reprovado em aberto" o esconderia atrás de um veredito plausível. Esta
    sobe e derruba a execução — falhar fechado, como a carga do painel faz
    quando falta `DT_RECEB` (AGENTS.md §3.13).
    """


# ---------------------------------------------------------------------------
# População
# ---------------------------------------------------------------------------

#: Mesma ordem de precedência de safra do piloto. Original ganha de
#: reapresentado porque só o original é evidência point-in-time.
PREFERENCIA = {
    "original": 0,
    "derivada_de_originais": 1,
    "derivada_sem_certificacao": 2,
    "as_restated": 3,
}


#: Contrato C2 do parecer de 11/09. O achado F8 corrigiu a ETIQUETA de unidade
#: na exportação e deixou o CONSUMIDOR dividindo os números crus. A série
#: mistura de verdade: 108 registros em milhares (Bradesco, BB) e 90 em milhões
#: (Itaú). Sem conversão, `1.000 milhares` e `1 milhão` — o MESMO montante —
#: produziam `y = ln(1/1000) = −6,9078`, e os quintis de T1 comparavam
#: emissores a grandezas mil vezes diferentes. A canônica é REAIS porque T1
#: compara emissores ENTRE SI; é o mesmo multiplicador do extrator.
MULTIPLICADOR_UNIDADE: dict[str, int] = {
    "milhares_de_reais": 1_000,
    "milhoes_de_reais": 1_000_000,
    "reais": 1,
}


@dataclass(frozen=True)
class Observacao:
    """Um (emissor, trimestre) com J como INTERVALO, nunca como ponto."""

    cd_cvm: str
    periodo: str
    #: **Em REAIS**, já convertidos de `unidade_de_origem` (contrato C2).
    inferior: float
    superior: float
    base_temporal: str
    disponivel_em: str | None
    #: Meia-largura relativa: metade do intervalo sobre o centro dele.
    meia_largura: float
    #: Procedência preservada: a unidade em que o emissor publicou. Converter e
    #: esquecer a origem é o que impede conferir a conversão depois.
    unidade_de_origem: str = "milhares_de_reais"

    @property
    def centro(self) -> float:
        return (self.inferior + self.superior) / 2


def fim_do_trimestre(periodo: str) -> date:
    ano, tri = int(periodo[:4]), int(periodo[5])
    return date(ano, tri * 3, (31, 30, 30, 31)[tri - 1])


def carregar_populacao() -> tuple[list[Observacao], dict]:
    """Aplica os critérios §3 do pré-registro, contando cada exclusão."""
    if not SERIE.is_file():
        raise ReprovaEmAberto(f"Série ausente em {SERIE}.")
    registros = [json.loads(linha) for linha in SERIE.open(encoding="utf-8")]

    contagem = {
        "registros_na_serie": len(registros),
        "descartados_nao_isolado": 0,
        "descartados_sem_fechamento": 0,
        "descartados_status": 0,
        "descartados_safra_pior": 0,
        "descartados_largura": 0,
    }
    melhor: dict[tuple[str, str], dict] = {}
    for registro in registros:
        periodo = registro["periodo"]
        if len(periodo) != 6 or periodo[4] != "T":
            contagem["descartados_nao_isolado"] += 1
            continue
        if registro["fechamento_confere"] is not True:
            contagem["descartados_sem_fechamento"] += 1
            continue
        if registro["status"] not in ("identificado", "limitado"):
            contagem["descartados_status"] += 1
            continue
        chave = (registro["cd_cvm"], periodo)
        atual = melhor.get(chave)
        def posto(reg: dict) -> tuple:
            return (
                PREFERENCIA.get(reg["base_temporal"], 9),
                reg["disponivel_em"] or "9999-99-99",
            )
        if atual is None or posto(registro) < posto(atual):
            if atual is not None:
                contagem["descartados_safra_pior"] += 1
            melhor[chave] = registro
        else:
            contagem["descartados_safra_pior"] += 1

    observacoes = []
    for (cd_cvm, periodo), registro in sorted(melhor.items()):
        # Contrato C2: converter ANTES de qualquer aritmética. Unidade ausente
        # ou fora do vocabulário levanta erro — nunca é suposta, porque supor
        # milhares para um emissor que publica em milhões erra por mil vezes
        # (é a troca MIL↔UNIDADE que invalidou a rodada A do CAND-04).
        unidade = registro.get("unidade")
        if unidade not in MULTIPLICADOR_UNIDADE:
            raise ErroDeUnidade(
                f"{cd_cvm}/{periodo}: unidade {unidade!r} ausente ou fora do "
                f"vocabulário {sorted(MULTIPLICADOR_UNIDADE)}. Supor uma "
                "unidade aqui erra por três ordens de grandeza sem sinal."
            )
        escala = MULTIPLICADOR_UNIDADE[unidade]
        inferior = float(registro["limite_inferior"]) * escala
        superior = float(registro["limite_superior"]) * escala
        centro = (inferior + superior) / 2
        if centro == 0:
            contagem["descartados_largura"] += 1
            continue
        meia_largura = (superior - inferior) / 2 / abs(centro)
        if meia_largura > LARGURA_MAXIMA_DA_POPULACAO:
            contagem["descartados_largura"] += 1
            continue
        observacoes.append(Observacao(
            cd_cvm, periodo, inferior, superior,
            registro["base_temporal"], registro["disponivel_em"], meia_largura,
            unidade,
        ))
    contagem["observacoes_de_J"] = len(observacoes)
    return observacoes, contagem


@dataclass(frozen=True)
class Alvo:
    """`y = ln(J(t+1)/J(t))` propagado como INTERVALO, não como ponto."""

    cd_cvm: str
    periodo_base: str
    periodo_alvo: str
    y_inferior: float
    y_superior: float
    #: Só para ranquear baselines; a conclusão usa o intervalo.
    y_centro: float
    j_base_centro: float
    j_alvo_centro: float
    disponivel_base: str | None
    disponivel_alvo: str | None
    largura_do_rotulo: float


def proximo_trimestre(periodo: str) -> str:
    ano, tri = int(periodo[:4]), int(periodo[5])
    return f"{ano + 1}T1" if tri == 4 else f"{ano}T{tri + 1}"


def trimestre_anterior(periodo: str) -> str:
    ano, tri = int(periodo[:4]), int(periodo[5])
    return f"{ano - 1}T4" if tri == 1 else f"{ano}T{tri - 1}"


def inicio_do_trimestre(periodo: str) -> datetime.date:
    """Primeiro dia do trimestre. Usado para medir o horizonte contratual."""
    ano, tri = int(periodo[:4]), int(periodo[5])
    return datetime.date(ano, 3 * (tri - 1) + 1, 1)


def primeiro_trimestre_apos(d: datetime.date) -> str:
    """q(D): o PRIMEIRO trimestre inteiro que começa depois de `d`.

    Contrato C3. É a função que faltava: sem ela só dava para perguntar
    "começa depois de D?", que é satisfeito por infinitos trimestres.
    """
    ano, tri = d.year, (d.month - 1) // 3 + 1
    # O trimestre corrente já começou (seu início é <= d), logo q(D) é sempre
    # o seguinte — inclusive quando `d` cai no primeiro dia do trimestre.
    return f"{ano + 1}T1" if tri == 4 else f"{ano}T{tri + 1}"


def horizonte_contratual_respeitado(alvo: "Alvo") -> bool | None:
    """O trimestre-alvo É q(D) — o primeiro que começa depois de D?

    Achado F2 da revisão independente, e contrato C3 do parecer de 11/09.

    A 1ª versão só checava se a base foi publicada antes do alvo, o que é
    ordenação de publicações, não horizonte. Medido: Bradesco 2024T1 ficou
    disponível em 02/05/2024 e o par aponta para 2024T2, que COMEÇOU em
    01/04/2024 — um mês antes de a base existir.

    A 2ª versão exigiu `inicio_do_trimestre(alvo) > D`. Corrigiu o caso do
    trimestre já em curso e deixou passar o OPOSTO: para D = 02/05/2024
    aprovava 2024T4 e 2025T1, que pulam q(D). Prever dois ou três trimestres à
    frente é outra tarefa, com outra dificuldade; aceitar as duas na mesma
    população mistura horizontes e torna o erro médio incomparável.

    O contrato é **igualdade com q(D)**, não desigualdade. Data de base
    ausente continua devolvendo `None` — não sei, nunca "sim".
    """
    if not alvo.disponivel_base:
        return None
    base = datetime.date.fromisoformat(alvo.disponivel_base)
    return alvo.periodo_alvo == primeiro_trimestre_apos(base)


def montar_alvos(observacoes: list[Observacao]) -> tuple[list[Alvo], dict]:
    por_chave = {(o.cd_cvm, o.periodo): o for o in observacoes}
    alvos, contagem = [], {"pares_sem_trimestre_seguinte": 0, "pares_com_sinal_trocado": 0}
    for obs in observacoes:
        seguinte = por_chave.get((obs.cd_cvm, proximo_trimestre(obs.periodo)))
        if seguinte is None:
            contagem["pares_sem_trimestre_seguinte"] += 1
            continue
        # J é despesa reportada positiva. Sinal trocado quebraria o log e
        # indicaria defeito de leitura, não observação legítima.
        if obs.inferior <= 0 or seguinte.inferior <= 0:
            contagem["pares_com_sinal_trocado"] += 1
            continue
        y_inf = math.log(seguinte.inferior / obs.superior)
        y_sup = math.log(seguinte.superior / obs.inferior)
        alvos.append(Alvo(
            obs.cd_cvm, obs.periodo, seguinte.periodo, y_inf, y_sup,
            math.log(seguinte.centro / obs.centro),
            obs.centro, seguinte.centro,
            obs.disponivel_em, seguinte.disponivel_em,
            (y_sup - y_inf) / 2,
        ))
    contagem["alvos"] = len(alvos)
    return alvos, contagem


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


def gate_g0(contagem: dict) -> dict:
    """Integridade: fechamento, zero divergências e conformidade contratual.

    Integridade aritmética não é conformidade semântica. Uma parcela incluída
    que vem CREDORA fecha a soma e ainda assim não é juros por competência:
    despesa de captação não é crédito. O gate reprova por isso.
    """
    resumo = json.loads(RESUMO_EXTENSAO.read_text(encoding="utf-8"))
    divergentes = len(resumo["identidades_divergentes"])
    creditos = resumo.get("periodos_com_credito_em_parcela_incluida", [])
    rubricas_suspeitas = resumo.get(
        "rubricas_com_conformidade_nao_demonstrada", []
    )
    # Contrato C5-bis (achado R-C5). A onda C1–C6 fez o produtor separar
    # fechamento independente de fechamento por construção, publicou a
    # contagem aqui — e não a usou para decidir. Com zero independentes, ou com
    # o campo AUSENTE, G0 aprovava: "não sei" virando "sim", que é a
    # guarda-que-aprova-por-ausência-de-dado do §3.14 do AGENTS.md.
    #
    # O piso é deliberadamente o mínimo que não inventa limiar: o contrato
    # C5-B pediu a marcação de linhagem e as duas contagens, e NÃO fixou
    # cobertura mínima. Exigir percentual, ou exigir que todas as identidades
    # anuais fechem, seria política nova escolhida aqui — e 17 das anuais são
    # não verificáveis por estado da fonte, não por defeito do instrumento.
    independentes = resumo.get("identidades_conferidas_independentes")
    # `bool` é subclasse de `int`: descartada explicitamente para que um
    # `true` no JSON não passe por contagem.
    evidencia_independente = (
        isinstance(independentes, int)
        and not isinstance(independentes, bool)
        and independentes > 0
    )
    # Por construção da população nenhum registro sem fechamento entra; o que
    # o gate mede é se ALGUM foi descartado por isso e quantas identidades
    # trimestrais independentes divergiram.
    return {
        "gate": "G0",
        "pergunta": "O dado é íntegro?",
        "fechamento_na_populacao": 1.0,
        "descartados_por_nao_fechar": contagem["descartados_sem_fechamento"],
        # Contrato C5-B: certificação lê a contagem INDEPENDENTE. Identidade
        # que fecha por construção é álgebra, não contraprova de mapeamento.
        "identidades_conferidas": resumo["identidades_conferidas"],
        "identidades_conferidas_independentes": independentes,
        "tem_evidencia_independente": evidencia_independente,
        "requisito_de_evidencia_independente": (
            "G0 só certifica com `identidades_conferidas_independentes` "
            "presente, inteiro e maior que zero. Campo ausente é «não sei» e "
            "NÃO certifica. Fechamento por construção é álgebra, não "
            "contraprova de mapeamento. Deliberadamente sem cobertura mínima: "
            "o contrato C5-B não fixou percentual e esta onda não o inventa."
        ),
        "identidades_que_fecham_por_construcao": len(
            resumo.get("identidades_que_fecham_por_construcao", [])
        ),
        "identidades_divergentes": divergentes,
        "periodos_com_credito_em_parcela_incluida": creditos,
        "rubricas_com_conformidade_contratual_nao_demonstrada":
            rubricas_suspeitas,
        "limiar": (
            "100% de fechamento, 0 divergências, 0 rubricas incluídas com "
            "conformidade contratual não demonstrada e pelo menos uma "
            "identidade conferida de forma INDEPENDENTE (contrato C5-bis)"
        ),
        "aprovado": (
            divergentes == 0
            and contagem["observacoes_de_J"] > 0
            and not rubricas_suspeitas
            and evidencia_independente
        ),
    }


def gate_g1(alvos: list[Alvo]) -> dict:
    """Point-in-time: os dois trimestres datados e em ordem."""
    if not alvos:
        raise ReprovaEmAberto("Nenhum alvo: G1 não é decidível.")
    datados = [a for a in alvos if a.disponivel_base and a.disponivel_alvo]
    em_ordem = [a for a in datados if a.disponivel_base < a.disponivel_alvo]
    # Achado F2: ordenação de publicações NÃO é o horizonte do contrato.
    no_horizonte = [a for a in em_ordem if horizonte_contratual_respeitado(a)]
    fracao_ordem = len(em_ordem) / len(alvos)
    fracao = len(no_horizonte) / len(alvos)
    return {
        "gate": "G1",
        "pergunta": "É point-in-time E no horizonte contratual?",
        "alvos": len(alvos),
        "com_as_duas_datas": len(datados),
        "com_datas_em_ordem": len(em_ordem),
        "fracao_com_datas_em_ordem": round(fracao_ordem, 4),
        "com_horizonte_contratual": len(no_horizonte),
        "fracao_certificada": round(fracao, 4),
        "o_que_mudou": (
            "Antes o gate media só se a base foi publicada antes do alvo "
            f"({round(fracao_ordem, 4)}). Achado F2: o contrato exige o "
            "primeiro trimestre inteiro que COMEÇA depois de a base ficar "
            "pública — q(D), por IGUALDADE, não por 'algum posterior' "
            "(contrato C3) — e por esse critério a fração é "
            f"{round(fracao, 4)}. Prever trimestre já em curso é outra "
            "tarefa, com outra data de corte — não a declarada no pré-registro."
        ),
        "limiar": "100%",
        "aprovado": fracao >= 1.0,
        "fora_do_horizonte_q_de_d": sorted(
            f"{a.cd_cvm}:{a.periodo_base}->{a.periodo_alvo}"
            f" (base {a.disponivel_base}, alvo começa "
            f"{inicio_do_trimestre(a.periodo_alvo).isoformat()}, "
            f"q(D)={primeiro_trimestre_apos(datetime.date.fromisoformat(a.disponivel_base))})"
            for a in em_ordem if not horizonte_contratual_respeitado(a)
        ),
        "sem_data": sorted(
            f"{a.cd_cvm}:{a.periodo_base}->{a.periodo_alvo}"
            for a in alvos if a not in datados
        ),
    }


def gate_g2(alvos: list[Alvo]) -> dict:
    """O erro do rótulo é menor que o sinal a prever?"""
    if len(alvos) < MINIMO_DE_CLUSTERS:
        raise ReprovaEmAberto("Alvos insuficientes para medir ruído/sinal.")
    ruido = statistics.median(a.largura_do_rotulo for a in alvos)
    sinal = statistics.median(abs(a.y_centro) for a in alvos)
    if sinal == 0:
        raise ReprovaEmAberto("Sinal mediano nulo: razão indefinida.")
    razao = ruido / sinal
    return {
        "gate": "G2",
        "pergunta": "O rótulo tem erro menor que o sinal?",
        "meia_largura_mediana_do_rotulo": round(ruido, 6),
        "movimento_mediano_a_prever": round(sinal, 6),
        "razao_ruido_sobre_sinal": round(razao, 4),
        "limiar": f"< {G2_RUIDO_SOBRE_SINAL}",
        "aprovado": razao < G2_RUIDO_SOBRE_SINAL,
        "alvos_cujo_rotulo_cobre_o_zero": sum(
            1 for a in alvos if a.y_inferior <= 0 <= a.y_superior
        ),
    }


# --- baselines ---------------------------------------------------------------


def _serie_por_emissor(alvos: list[Alvo]) -> dict[str, list[Alvo]]:
    por: dict[str, list[Alvo]] = {}
    for alvo in alvos:
        por.setdefault(alvo.cd_cvm, []).append(alvo)
    for lista in por.values():
        lista.sort(key=lambda a: fim_do_trimestre(a.periodo_base))
    return por


def previsoes_dos_baselines(alvos: list[Alvo]) -> dict[str, dict]:
    """B0, B1 e B2 do pré-registro. B3 exige série de juros e não roda aqui."""
    por_emissor = _serie_por_emissor(alvos)
    indices = {
        (a.cd_cvm, a.periodo_base): i
        for lista in por_emissor.values()
        for i, a in enumerate(lista)
    }
    previsoes: dict[str, dict] = {"B0": {}, "B1": {}, "B2": {}}
    for cd_cvm, lista in por_emissor.items():
        for i, alvo in enumerate(lista):
            chave = (cd_cvm, alvo.periodo_base)
            previsoes["B0"][chave] = 0.0

            # Contrato C4: um antecedente só pode entrar na previsão se o
            # RESULTADO dele já era conhecido na data de decisão deste alvo.
            # O calendário corrigido em F9 garantia adjacência real e nada
            # dizia sobre disponibilidade: a contraprova do parecer usava
            # quatro antecedentes de 2023 cujo desfecho só saiu em 01/01/2025
            # para decidir em 02/05/2024, e B1/B2 opinavam com informação que
            # não existia em D. Antecedente sem data é INUTILIZÁVEL — ausência
            # de data nunca vira "estava disponível".
            def conhecido_em_d(a: "Alvo") -> bool:
                if not alvo.disponivel_base or not a.disponivel_alvo:
                    return False
                return a.disponivel_alvo <= alvo.disponivel_base

            # B1: mesmo trimestre do ano anterior. Exige adjacência real de
            # calendário — quatro passos atrás na LISTA não é um ano atrás se
            # houver buraco na série.
            alvo_anterior = next(
                (a for a in lista
                 if a.periodo_base == f"{int(alvo.periodo_base[:4]) - 1}"
                                      f"{alvo.periodo_base[4:]}"),
                None,
            )
            previsoes["B1"][chave] = (
                alvo_anterior.y_centro
                if alvo_anterior and conhecido_em_d(alvo_anterior) else None
            )
            # Achado F9: isto era `lista[max(0, i - 4):i]` — até quatro LINHAS
            # DISPONÍVEIS, aceitando menos de quatro e sem exigir adjacência de
            # calendário. Contraprova da revisão: com 2020T1 e 2024T1 na série,
            # usava 2020T1 para prever 2024T1 e chamava isso de "mediana dos
            # quatro trimestres anteriores". Agora exige os QUATRO trimestres
            # imediatamente anteriores, existentes na série; faltando um, B2
            # não opina — ausência nunca vira previsão.
            # Contrato C4: o dicionário de antecedentes de B2 só contém os
            # que já eram conhecidos em D. Faltando um, B2 não opina — a
            # regra de F9 (ausência nunca vira previsão) passa a valer também
            # para "existe na série mas ainda não era público".
            por_periodo = {
                a.periodo_base: a.y_centro
                for a in lista if conhecido_em_d(a)
            }
            exigidos = []
            cursor = alvo.periodo_base
            for _ in range(4):
                cursor = trimestre_anterior(cursor)
                exigidos.append(cursor)
            anteriores = [por_periodo.get(q) for q in exigidos]
            previsoes["B2"][chave] = (
                statistics.median(anteriores)
                if all(v is not None for v in anteriores) else None
            )
    return previsoes


def erros_absolutos(alvos: list[Alvo], previsao: dict) -> list[tuple[str, float]]:
    """(emissor, erro) só onde o baseline tem previsão. Ausente não vira zero."""
    saida = []
    for alvo in alvos:
        p = previsao.get((alvo.cd_cvm, alvo.periodo_base))
        if p is None:
            continue
        saida.append((alvo.cd_cvm, abs(alvo.y_centro - p)))
    return saida


def mae_macro(erros: list[tuple[str, float]]) -> float | None:
    """Média dos MAE POR EMISSOR: o emissor com mais trimestres não domina."""
    por: dict[str, list[float]] = {}
    for cd_cvm, erro in erros:
        por.setdefault(cd_cvm, []).append(erro)
    if not por:
        return None
    return statistics.fmean(statistics.fmean(v) for v in por.values())


def gate_g3(alvos: list[Alvo], previsoes: dict) -> dict:
    """A amostra decide algo? Poder com clusters = EMISSORES, não trimestres."""
    emissores = sorted({a.cd_cvm for a in alvos})
    if len(emissores) < MINIMO_DE_CLUSTERS:
        raise ReprovaEmAberto(
            f"{len(emissores)} emissor(es): menos que o mínimo "
            f"{MINIMO_DE_CLUSTERS} de clusters independentes."
        )
    tabela = {}
    for nome, previsao in previsoes.items():
        erros = erros_absolutos(alvos, previsao)
        tabela[nome] = {
            "observacoes_cobertas": len(erros),
            "mae_macro": round(mae_macro(erros), 6) if erros else None,
            "mae_agregado": round(statistics.fmean(e for _, e in erros), 6)
            if erros else None,
        }
    # §3.11 do AGENTS.md, literal: "B0 prevê mudança zero e, portanto, abstém
    # da direção; publicar cobertura junto do acerto." Acerto de direção sem
    # cobertura ao lado deixaria um baseline que se cala parecer perfeito.
    for nome, previsao in previsoes.items():
        opinou = acertou = 0
        for alvo in alvos:
            p = previsao.get((alvo.cd_cvm, alvo.periodo_base))
            if p is None or p == 0:
                continue
            opinou += 1
            acertou += (p > 0) == (alvo.y_centro > 0)
        tabela[nome]["direcao_cobertura"] = round(opinou / len(alvos), 4)
        tabela[nome]["direcao_acerto"] = (
            round(acertou / opinou, 4) if opinou else None
        )
    validos = {k: v for k, v in tabela.items() if v["mae_macro"] is not None}
    if not validos:
        raise ReprovaEmAberto("Nenhum baseline produziu previsão.")
    # Achado F9: a eleição comparava MAE em SUPORTES DIFERENTES. Contraprova da
    # revisão: B0 com MAE 7 em nove observações perdia para B1 com MAE 2 em
    # três, embora B0 medisse 1 nessas mesmas três. Comparar erro médio de
    # conjuntos distintos não é comparar previsores. A eleição passa a usar a
    # INTERSEÇÃO onde todos os baselines válidos opinam.
    comum = [
        a for a in alvos
        if all(
            previsoes[n].get((a.cd_cvm, a.periodo_base)) is not None
            for n in validos
        )
    ]
    for nome in validos:
        erros_c = erros_absolutos(comum, previsoes[nome])
        tabela[nome]["mae_macro_no_suporte_comum"] = (
            round(mae_macro(erros_c), 6) if erros_c else None
        )
    tabela["suporte_comum"] = {
        "observacoes": len(comum),
        "criterio": (
            "alvos em que TODOS os baselines válidos opinam; a eleição usa "
            "este suporte porque MAE de conjuntos diferentes não se compara "
            "(achado F9)"
        ),
    }
    if not comum:
        raise ReprovaEmAberto(
            "Suporte comum vazio: os baselines não opinam sobre nenhum alvo "
            "em comum, então nenhuma eleição entre eles é comparável."
        )
    melhor = min(
        validos, key=lambda k: tabela[k]["mae_macro_no_suporte_comum"]
    )
    mae_melhor = validos[melhor]["mae_macro"]

    # Poder por bootstrap AGRUPADO POR EMISSOR: reamostra emissores inteiros,
    # porque trimestres do mesmo banco não são réplicas independentes.
    erros_melhor = erros_absolutos(alvos, previsoes[melhor])
    por_emissor: dict[str, list[float]] = {}
    for cd_cvm, erro in erros_melhor:
        por_emissor.setdefault(cd_cvm, []).append(erro)
    # Contrato S.1 (achado R-SUPORTE). Com UMA observação no suporte do eleito,
    # `statistics.stdev` levantava `StatisticsError` — que `_medir` NÃO captura
    # — e a execução morria levando junto G0, G1 e G2 já medidos. Amostra
    # insuficiente é `ReprovaEmAberto`: entra na cadeia como gate reprovado com
    # o motivo e preserva o que já havia sido apurado.
    #
    # Dívida ANTERIOR a C4, não regressão dela: a chamada que estourava vem
    # antes, no arquivo, de qualquer linha que C4-B introduziu.
    #
    # `StatisticsError` continua sem ser capturada por `_medir`, de propósito:
    # converter qualquer defeito estatístico futuro em veredito plausível de
    # gate é o que a separação `ErroDeUnidade` × `ReprovaEmAberto` existe para
    # impedir.
    if len(erros_melhor) < 2:
        raise ReprovaEmAberto(
            f"O baseline eleito ({melhor}) cobre {len(erros_melhor)} "
            "observação(ões): menos que as duas necessárias para estimar "
            "dispersão. Amostra insuficiente para decidir o poder."
        )
    aleatorio = random.Random(20260909)
    medias = []
    chaves = list(por_emissor)
    for _ in range(2000):
        sorteados = [aleatorio.choice(chaves) for _ in chaves]
        medias.append(statistics.fmean(
            statistics.fmean(por_emissor[k]) for k in sorteados
        ))
    erro_padrao = statistics.stdev(medias)
    detectavel = FATOR_DE_PODER * erro_padrao
    relativa = detectavel / mae_melhor if mae_melhor else float("inf")

    # Contraprova declarada: o MESMO cálculo tratando trimestre como réplica
    # independente. Se só ele passar, o gate reprova (§5 do pré-registro).
    todos = [e for _, e in erros_melhor]
    erro_padrao_ingenuo = statistics.stdev(todos) / math.sqrt(len(todos))
    # Baseline com erro ZERO não é boa notícia: melhoria relativa fica
    # indefinida e nenhum modelo pode superá-lo. Dividir por zero aqui
    # derrubava o auditor em vez de dizer isso.
    if not mae_melhor:
        raise ReprovaEmAberto(
            f"O melhor baseline ({melhor}) tem erro ZERO nesta amostra: "
            "melhoria relativa é indefinida e nenhum componente aprendido "
            "pode superá-lo. Isso normalmente indica alvo ou população "
            "degenerados, não um baseline excelente."
        )
    relativa_ingenua = FATOR_DE_PODER * erro_padrao_ingenuo / mae_melhor

    # Quantos emissores seriam necessários para o gate decidir? O erro padrão
    # agrupado cai com a raiz do número de clusters, então a conta é direta.
    # **Estimativa frágil por construção:** a variância entre emissores está
    # medida sobre TRÊS clusters. Serve para dizer a ordem de grandeza do que
    # falta, não para prometer um número exato.
    # Contrato C4-B: a conta de poder e a contagem publicada têm de usar os
    # emissores que EFETIVAMENTE entram no erro do baseline eleito, não os da
    # população. Contraprova do revisor: três bancos na população e eleito
    # cobrindo só um devolvia `emissores_independentes = 3` ao lado de
    # `trimestres_por_emissor = {'A': 2}` — e "emissores necessários = 0".
    # Contar quem não está na comparação infla o poder aparente.
    emissores_usados = sorted(por_emissor)
    fator = relativa / G3_MELHORIA_DETECTAVEL
    emissores_necessarios = math.ceil(len(emissores_usados) * fator ** 2)

    # Referência POST-HOC, declarada como tal: prever sempre "subiu", que é a
    # classe majoritária. Não é baseline do pré-registro; entra porque só
    # ENDURECE a barra, nunca resgata o candidato.
    decidiveis = [a for a in alvos if not (a.y_inferior <= 0 <= a.y_superior)]
    taxa_base = (
        statistics.fmean(1 if a.y_centro > 0 else 0 for a in decidiveis)
        if decidiveis else None
    )

    # Contrato C6-bis.3: o estado de C6 tem o MESMO vocabulário nos dois
    # consumidores. A sensibilidade já publicava estes três campos; G3 só tinha
    # a etiqueta `calculo_de_poder_invalidado_por`, sem nada que decidisse.
    clusters_suficientes = len(emissores_usados) >= MINIMO_DE_CLUSTERS
    motivos = []
    if not PODER_REDESENHADO_APOS_F3:
        motivos.append(
            "F3: a conta reamostra a dispersão da perda do baseline eleito, "
            "não a diferença pareada entre desafiante e baseline. Enquanto "
            "não for redesenhada, os números de poder NÃO estimam poder e o "
            "gate não pode aprovar por eles."
        )
    if not clusters_suficientes:
        # Os emissores contados aqui são os que ENTRAM no erro do eleito
        # (contrato C4-B), não os da população: dois emissores com MAE
        # parecido produzem erro padrão minúsculo e um "emissores necessários
        # ~1" que é artefato de ter perdido quem se comportava diferente.
        motivos.append(
            f"{len(emissores_usados)} emissor(es) no erro do baseline eleito, "
            f"abaixo do mínimo {MINIMO_DE_CLUSTERS}: a melhoria detectável e o "
            "número de emissores necessários não são interpretáveis."
        )
    if not B3_EXECUTADO:
        motivos.append(
            "B3 (benchmark econômico do §4 do pré-registro) não executado."
        )

    return {
        "gate": "G3",
        "pergunta": "A amostra decide algo?",
        "emissores_independentes": len(emissores_usados),
        "emissores_na_populacao": len(emissores),
        "emissores_fora_do_erro_do_eleito": sorted(
            set(emissores) - set(emissores_usados)
        ),
        "mae_macro_por_emissor": {
            cd: round(statistics.fmean(
                e for c, e in erros_melhor if c == cd
            ), 6)
            for cd in sorted(por_emissor)
        },
        "trimestres_por_emissor": {
            cd: len(v) for cd, v in sorted(por_emissor.items())
        },
        "referencia_post_hoc_classe_majoritaria": {
            "descricao": (
                "Prever sempre 'o custo subiu'. NÃO é baseline do "
                "pré-registro: entra depois de medir e só endurece a barra."
            ),
            "acerto_de_direcao": round(taxa_base, 4) if taxa_base else None,
            "cobertura": 1.0,
            "compara_com": {
                nome: tabela[nome]["direcao_acerto"] for nome in validos
            },
        },
        # Contrato C6: o MESMO cálculo invalidado por F3 vive aqui. Publicado
        # e marcado, nunca apresentado como estimativa de poder válida.
        "emissores_necessarios_para_o_gate_decidir": emissores_necessarios,
        "calculo_de_poder_invalidado_por": (
            "F3" if not PODER_REDESENHADO_APOS_F3 else None
        ),
        "decidivel": PODER_REDESENHADO_APOS_F3 and clusters_suficientes,
        "clusters_suficientes": clusters_suficientes,
        "ressalva": " | ".join(motivos) if motivos else None,
        "leitura_do_poder": (
            "INVALIDADO por F3: a conta reamostra a dispersão da perda do "
            "baseline eleito, não a diferença pareada entre desafiante e "
            "baseline. `melhoria_minima_detectavel_relativa` e "
            "`emissores_necessarios_para_o_gate_decidir` ficam publicados "
            "para auditoria, não para uso. O redesenho é tarefa de protocolo."
        ),
        "baselines": tabela,
        "b3_benchmark_economico": (
            "NÃO EXECUTADO: exige a série da meta Selic com disciplina "
            "point-in-time, que não está no repositório. A série existe em "
            "fonte pública oficial (SGS 432 do BCB), então 'não implementado' "
            "não é 'só existe dado pago' — correção do achado F10. O §4 do "
            "pré-registro fixa a consequência: sem B3 o candidato não pode "
            "ser aprovado com B0–B2 apenas."
        ),
        # Achado F10: essa exigência do pré-registro só existia como TEXTO e
        # não participava da condição de aprovação. Permissão falsa latente:
        # não liberou esta rodada, que reprova por outros motivos, mas
        # liberaria uma rodada futura em que G3 passasse.
        "b3_executado": B3_EXECUTADO,
        "poder_redesenhado_apos_f3": PODER_REDESENHADO_APOS_F3,
        "melhor_baseline": melhor,
        "mae_macro_do_melhor": mae_melhor,
        "erro_padrao_agrupado_por_emissor": round(erro_padrao, 6),
        "melhoria_minima_detectavel_relativa": round(relativa, 4),
        "melhoria_minima_detectavel_se_trimestre_fosse_replica": round(
            relativa_ingenua, 4
        ),
        "limiar": (
            f"<= {G3_MELHORIA_DETECTAVEL} E B3 executado "
            "(exigência do §4 do pré-registro) E método de poder não "
            "invalidado por F3 (contrato C6-bis)"
        ),
        # Contrato C6-bis.1: TRÊS vetos independentes, cada um suficiente para
        # reprovar sozinho. Nenhum deles é literal fixo — as quatro combinações
        # de B3 × F3 são exercitadas por contraprova.
        "aprovado": (
            relativa <= G3_MELHORIA_DETECTAVEL
            and B3_EXECUTADO
            and PODER_REDESENHADO_APOS_F3
        ),
    }


# --- T1 e T2 ----------------------------------------------------------------


def amplitude_por_quintis(
    valores: list[float], eventos: list[int]
) -> tuple[float, list[dict]]:
    """Maior amplitude da taxa de evento entre quintis do componente."""
    if len(valores) < MINIMO_PARA_QUINTIS:
        raise ReprovaEmAberto(
            f"{len(valores)} observações: abaixo do mínimo "
            f"{MINIMO_PARA_QUINTIS} para quintil. Amplitude sobre amostra "
            "insuficiente sai NaN, e NaN >= limiar é False — isso aprovaria "
            "por ausência de dado."
        )
    # Achado F7 da revisão independente, e contrato C1 do parecer de 11/09.
    #
    # A 1ª versão fazia `sorted(zip(valores, eventos))`, que desempata pelo
    # PRÓPRIO EVENTO: valores todos 1.0 com eventos 0,1 alternados devolvia
    # amplitude 1,0 — associação MÁXIMA para variável que não ordena nada.
    #
    # A 2ª versão desempatou pela posição original. Removeu o uso EXPLÍCITO do
    # rótulo e não o implícito: `[0]*25+[1]*25` continuava medindo 1,0 sobre a
    # MESMA distribuição, só reordenada. Posição de linha carrega emissor e
    # tempo, e os quintis passavam a ser criados pela ordem das linhas.
    #
    # O contrato agora é outro: duas observações com valor IDÊNTICO são
    # indistinguíveis PELA VARIÁVEL, então nenhuma política pode separá-las em
    # faixas diferentes. Os grupos são formados por VALOR — corta-se no limite
    # de quintil e estende-se até o fim do grupo de empate. Variável constante
    # vira UMA faixa e mede amplitude 0,0, que é a leitura correta: ela não
    # fabrica baseline nenhum. A amplitude passa a ser invariante à permutação
    # das linhas, e há contraprova disso.
    ordenados = sorted(zip(valores, eventos), key=lambda t: t[0])
    tamanho = len(ordenados) / 5
    faixas: list[dict] = []
    inicio = 0
    for q in range(5):
        if inicio >= len(ordenados):
            break
        fim = max(int((q + 1) * tamanho), inicio + 1)
        # Estende o corte até o fim do grupo de empate: um mesmo valor nunca
        # atravessa duas faixas.
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
    # Uma faixa só significa variável sem variação: nada a comparar, amplitude
    # zero. `max - min` sobre lista de um elemento já daria 0,0; o campo
    # `faixas_formadas` existe para que o leitor veja que os quintis
    # degeneraram em vez de supor cinco.
    taxas = [f["taxa"] for f in faixas]
    for f in faixas:
        f["faixas_formadas"] = len(faixas)
    return max(taxas) - min(taxas), faixas


def teste_t1(alvos: list[Alvo]) -> dict:
    """O alvo fabrica o próprio baseline? Testa TODO componente definidor."""
    decidiveis = [
        a for a in alvos if not (a.y_inferior <= 0 <= a.y_superior)
    ]
    eventos = [1 if a.y_centro > 0 else 0 for a in decidiveis]
    # Os dois componentes que definem mecanicamente `y` — e eles NÃO têm o
    # mesmo papel. `J(t)` é conhecido na data da previsão e portanto pode
    # fabricar baseline, que é o que o T1 existe para pegar. `J(t+1)` é o
    # futuro: ele define o alvo mas não está disponível para prever nada.
    componentes = {
        "J_no_trimestre_base": {
            "valores": [a.j_base_centro for a in decidiveis],
            "disponivel_na_data_da_previsao": True,
        },
        "J_no_trimestre_alvo": {
            "valores": [a.j_alvo_centro for a in decidiveis],
            "disponivel_na_data_da_previsao": False,
        },
    }
    saida, reprovas, reprovas_utilizaveis = {}, [], []
    for nome, dados in componentes.items():
        amplitude, faixas = amplitude_por_quintis(dados["valores"], eventos)
        saida[nome] = {
            "amplitude": round(amplitude, 4),
            "disponivel_na_data_da_previsao": dados[
                "disponivel_na_data_da_previsao"
            ],
            "quintis": faixas,
        }
        if amplitude >= T1_AMPLITUDE:
            reprovas.append(nome)
            if dados["disponivel_na_data_da_previsao"]:
                reprovas_utilizaveis.append(nome)
    return {
        "teste": "T1",
        "pergunta": "O alvo fabrica o próprio baseline?",
        "observacoes_decidiveis": len(decidiveis),
        "observacoes_cujo_intervalo_cobre_zero": len(alvos) - len(decidiveis),
        "taxa_do_evento": round(statistics.fmean(eventos), 4),
        "componentes": saida,
        "limiar": f"< {T1_AMPLITUDE}",
        "componentes_reprovados": reprovas,
        "componentes_reprovados_que_seriam_usaveis_como_baseline":
            reprovas_utilizaveis,
        "defeito_do_proprio_pre_registro": (
            "O §5 do pré-registro manda testar 'cada componente que define "
            "mecanicamente o alvo' e nomeia J(t) e J(t+1). J(t+1) É o futuro: "
            "reprovar por ele diria apenas que o futuro prevê o futuro, que "
            "não é o defeito que o T1 procura. As duas leituras ficam "
            "publicadas — a literal, que reprova, e a restrita ao que está "
            "disponível na data da previsão. O veredito NÃO muda por isso: "
            "G1 e G3 já reprovam por conta própria, então esta distinção é "
            "diagnóstico, não resgate."
        ),
        "aprovado": not reprovas,
        "aprovado_na_leitura_restrita": not reprovas_utilizaveis,
    }


def auc(escores: list[float], eventos: list[int]) -> float | None:
    positivos = [e for e, y in zip(escores, eventos) if y == 1]
    negativos = [e for e, y in zip(escores, eventos) if y == 0]
    if not positivos or not negativos:
        return None
    ganhos = sum(
        1.0 if p > n else 0.5 if p == n else 0.0
        for p in positivos for n in negativos
    )
    return ganhos / (len(positivos) * len(negativos))


def teste_t2(alvos: list[Alvo], previsoes: dict, melhor: str) -> dict:
    """Há sinal temporal ou só ordenação de emissor?"""
    previsao = previsoes[melhor]
    pontos = [
        (a, previsao.get((a.cd_cvm, a.periodo_base)))
        for a in alvos if not (a.y_inferior <= 0 <= a.y_superior)
    ]
    pontos = [(a, p) for a, p in pontos if p is not None]
    if not pontos:
        raise ReprovaEmAberto(
            f"Baseline {melhor} não pontua nenhuma observação decidível."
        )
    escores = [p for _, p in pontos]
    eventos = [1 if a.y_centro > 0 else 0 for a, _ in pontos]
    # **Escore constante não decide nada.** B0 prevê 0 para tudo: a AUC sai
    # exatamente 0,5 em todo recorte e a lacuna sai 0, o que passaria no
    # limiar por AUSÊNCIA de poder discriminante. Guarda que aprova por
    # ausência de dado é pior que guarda nenhuma (AGENTS.md §3.14).
    if len(set(escores)) == 1:
        raise ReprovaEmAberto(
            f"O melhor baseline ({melhor}) prevê o mesmo valor para todas as "
            f"{len(escores)} observações. AUC de escore constante é 0,5 por "
            "construção e a lacuna sai 0: o T2 passaria por não ter poder "
            "discriminante nenhum, não por haver sinal temporal."
        )
    agregada = auc(escores, eventos)
    intra = []
    for cd_cvm in sorted({a.cd_cvm for a, _ in pontos}):
        recorte = [(a, p) for a, p in pontos if a.cd_cvm == cd_cvm]
        valor = auc([p for _, p in recorte],
                    [1 if a.y_centro > 0 else 0 for a, _ in recorte])
        if valor is not None:
            intra.append((cd_cvm, len(recorte), valor))
    if agregada is None or not intra:
        raise ReprovaEmAberto("AUC indefinida: uma das classes está vazia.")
    media_intra = statistics.fmean(v for _, _, v in intra)
    lacuna = agregada - media_intra
    # A lacuna só é evidência de sinal temporal se o escore tiver poder
    # discriminante. Escore que ordena o evento PIOR que o acaso (AUC < 0,5)
    # produz lacuna pequena por ser ruim, não por haver sinal no tempo —
    # aprovar por isso seria a mesma armadilha do escore constante.
    informativo = agregada > 0.5
    return {
        "teste": "T2",
        "informativo": informativo,
        "ressalva": None if informativo else (
            f"AUC agregada {agregada:.4f} <= 0,5: o escore ordena o evento "
            "pior que o acaso. A lacuna abaixo do limiar NÃO é evidência de "
            "sinal temporal — é a diferença entre dois números ruins. Ler "
            "este T2 como aprovação de sinal seria erro de leitura."
        ),
        "pergunta": "Há sinal temporal ou só ordenação de emissor?",
        "escore_usado": f"baseline {melhor}",
        "auc_agregada": round(agregada, 4),
        "auc_intra_emissor": [
            {"cd_cvm": c, "n": n, "auc": round(v, 4)} for c, n, v in intra
        ],
        "auc_intra_media": round(media_intra, 4),
        "lacuna": round(lacuna, 4),
        "limiar": f"< {T2_LACUNA}",
        # Achado F10: a ressalva existia, a TRAVA não. Com escores `-y` a
        # contraprova produzia AUC agregada e intra iguais, `informativo=False`
        # e `aprovado=True` — o relatório dizia "não leia como aprovação" e o
        # campo dizia aprovado. Agora escore não informativo REPROVA: lacuna
        # pequena entre dois números ruins não é evidência de nada.
        "aprovado": informativo and lacuna < T2_LACUNA,
    }


# ---------------------------------------------------------------------------


#: Pergunta de cada gate, para que a reprova em aberto ainda diga o que se
#: estava tentando medir.
PERGUNTAS = {
    "G0": "O dado é íntegro?",
    "G1": "É point-in-time?",
    "G2": "O rótulo tem erro menor que o sinal?",
    "G3": "A amostra decide algo?",
    "T1": "O alvo fabrica o próprio baseline?",
    "T2": "Há sinal temporal ou só ordenação de emissor?",
}

#: Ordem da cadeia, para separar gate decisivo de medição de diagnóstico.
_CADEIA = ("G0", "G1", "G2", "G3", "T1", "T2")


def _ordem(nome: str) -> int:
    return _CADEIA.index(nome) if nome in _CADEIA else len(_CADEIA)


def executar() -> dict:
    observacoes, contagem = carregar_populacao()
    alvos, contagem_alvos = montar_alvos(observacoes)
    contagem.update(contagem_alvos)

    relatorio: dict = {
        "schema_version": "1.0.0",
        "candidato": "B-DFC-01J-M",
        "pre_registro": (
            "resultados/pre_registro_b_dfc_01j_modelo_2026-09-09.md"
        ),
        "populacao": contagem,
        "emissores": sorted({o.cd_cvm for o in observacoes}),
        "janela": (
            f"{min((o.periodo for o in observacoes), default='-')} .. "
            f"{max((o.periodo for o in observacoes), default='-')}"
        ),
        "gates": [],
        "interrompido_em": None,
    }

    # A cadeia PARA no primeiro gate reprovado — é o que o §5 do pré-registro
    # manda. Mas parar de medir não é a mesma coisa que parar de decidir: o
    # que vem depois continua sendo medido e publicado como DIAGNÓSTICO, para
    # que a reprovação diga o tamanho do que falta em vez de só dizer que
    # falta. Só os gates até a interrupção contam para o veredito.
    cadeia = []
    decisivos_ate = None
    if True:
        # **Amostra insuficiente num gate não pode apagar os anteriores.**
        # `ReprovaEmAberto` continua sendo o oposto de aprovação — ela entra na
        # cadeia como gate REPROVADO com o motivo, em vez de derrubar o
        # relatório inteiro e levar consigo o que já havia sido medido.
        #
        # Passou a cobrir G0/G1/G2 também, e não só G3/T1/T2: quando a
        # correção do achado F1 zerou a população, `gate_g1` levantou
        # `ReprovaEmAberto` e o relatório saiu SEM o G0 que já estava medido —
        # o mesmo defeito, que só estava meio corrigido.
        def _medir(nome: str, funcao):
            nonlocal decisivos_ate
            try:
                resultado = funcao()
            except ReprovaEmAberto as erro:
                resultado = {
                    "gate" if nome.startswith("G") else "teste": nome,
                    "pergunta": PERGUNTAS[nome],
                    "aprovado": False,
                    "reprova_em_aberto": str(erro),
                }
            cadeia.append(resultado)
            if decisivos_ate is None and not resultado["aprovado"]:
                decisivos_ate = nome
            return resultado

        if True:
            _medir("G0", lambda: gate_g0(contagem))
            _medir("G1", lambda: gate_g1(alvos))
            _medir("G2", lambda: gate_g2(alvos))
            previsoes = previsoes_dos_baselines(alvos)
            g3 = _medir("G3", lambda: gate_g3(alvos, previsoes))
            _medir("T1", lambda: teste_t1(alvos))
            # T2 exige escore que varie. Se o melhor baseline for constante,
            # mede-se no melhor baseline NÃO degenerado e a substituição fica
            # declarada — em vez de colher um 0,5 vazio.
            def _t2():
                escolhido = g3.get("melhor_baseline")
                if escolhido is None:
                    raise ReprovaEmAberto(
                        "G3 não chegou a eleger baseline: sem escore, T2 não "
                        "é medível."
                    )
                try:
                    return teste_t2(alvos, previsoes, escolhido)
                except ReprovaEmAberto as erro:
                    candidatos = [
                        n for n in ("B2", "B1")
                        if len({
                            v for v in previsoes[n].values() if v is not None
                        }) > 1
                    ]
                    if not candidatos:
                        raise
                    substituto = min(
                        candidatos,
                        key=lambda n: (
                            g3["baselines"][n]["mae_macro"] or float("inf")
                        ),
                    )
                    resultado = teste_t2(alvos, previsoes, substituto)
                    resultado["substituicao_de_escore"] = str(erro)
                    return resultado

            _medir("T2", _t2)

    relatorio["interrompido_em"] = decisivos_ate
    for gate in cadeia:
        nome = gate.get("gate") or gate.get("teste")
        gate["papel"] = (
            "diagnostico_apos_a_interrupcao"
            if decisivos_ate is not None
            and _ordem(nome) > _ordem(decisivos_ate)
            else "decisivo"
        )
    relatorio["gates"] = cadeia
    reprovados = [
        g.get("gate") or g.get("teste")
        for g in cadeia if not g["aprovado"] and g["papel"] == "decisivo"
    ]
    relatorio["reprovados_no_diagnostico"] = [
        g.get("gate") or g.get("teste")
        for g in cadeia
        if not g["aprovado"] and g["papel"] != "decisivo"
    ]
    relatorio["reprovados"] = reprovados
    relatorio["veredito"] = (
        "AUTORIZA EXECUTAR COMPONENTE APRENDIDO CONTRA OS BASELINES"
        if not reprovados and relatorio["interrompido_em"] is None
        else "NAO AUTORIZA TREINO"
    )
    return relatorio


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    try:
        relatorio = executar()
    except ReprovaEmAberto as erro:
        relatorio = {
            "schema_version": "1.0.0",
            "candidato": "B-DFC-01J-M",
            "veredito": "NAO AUTORIZA TREINO",
            "reprova_em_aberto": str(erro),
        }
        (DESTINO / "gates.json").write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        print(f"REPROVA EM ABERTO: {erro}")
        return 1

    (DESTINO / "gates.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"Candidato: {relatorio['candidato']}")
    print(f"População: {relatorio['populacao']['observacoes_de_J']} "
          f"observações de J, {relatorio['populacao']['alvos']} alvos, "
          f"{len(relatorio['emissores'])} emissores ({relatorio['janela']})")
    for gate in relatorio["gates"]:
        nome = gate.get("gate") or gate.get("teste")
        marca = "" if gate["papel"] == "decisivo" else "  [diagnóstico]"
        print(f"  {'APROVA' if gate['aprovado'] else 'REPROVA'}  {nome}: "
              f"{gate['pergunta']}{marca}")
    print(f"VEREDITO: {relatorio['veredito']}")
    if relatorio["reprovados"]:
        print(f"  reprovados: {', '.join(relatorio['reprovados'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
