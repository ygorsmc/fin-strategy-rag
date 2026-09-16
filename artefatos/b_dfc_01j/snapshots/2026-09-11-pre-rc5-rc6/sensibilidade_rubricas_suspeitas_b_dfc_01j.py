"""Sensibilidade do gate G3 às três rubricas de conformidade não demonstrada.

**Por que este script existe.** O relatório de prontidão publicou "seriam
necessários ~128 emissores" como se fosse limite estrutural do universo de
bancos. Não é: o número vem quase todo da dispersão do MAE entre emissores, e
essa dispersão vem quase toda de UMA rubrica — a mesma que o G0 reprovou. Medir
os dois cenários é o que separa "o alvo precisa de 128 bancos" de "o alvo
precisa que o defeito do G0 seja resolvido".

**Isto NÃO é rerrodada dos gates pré-registrados.** É diagnóstico da condição de
reabertura do §8 do relatório. Nenhum limiar foi alterado e nenhuma conclusão
do pré-registro é substituída por aqui.

Dois cenários, os dois declarados:

- **pessimista** — as três rubricas viram NÃO IDENTIFICADAS. É o que acontece
  se o componente de câmbio/valor justo **não** for separável na nota: a
  parcela não é excluída (excluir exigiria saber o valor dela), ela vira
  desconhecida e engorda o intervalo de J.
- **diagnóstico de volatilidade** — soma só as parcelas limpas, como PONTO,
  ignorando o alargamento. **Não é J** (falta uma parcela) e não serve de
  rótulo; serve só para responder se as parcelas limpas do Itaú oscilam como as
  dos outros dois emissores.
"""

from __future__ import annotations

import collections
import json
import math
import random
import statistics
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FATOS = RAIZ / "artefatos" / "b_dfc_01j" / "extensao" / "fatos.jsonl"
DESTINO = RAIZ / "artefatos" / "b_dfc_01j" / "prontidao"

#: As três rubricas que o G0 reprovou por vir credoras em algum trimestre.
RUBRICAS_SUSPEITAS = frozenset({
    "juros_mercados_interbancarios",
    "juros_depositos_interfinanceiros",
    "juros_emprestimos_e_repasses",
})

#: Mesmos parâmetros do auditor de prontidão — importados por valor e não por
#: cópia solta justamente para que uma divergência apareça no teste.
from scripts.auditar_prontidao_b_dfc_01j import (  # noqa: E402
    FATOR_DE_PODER, G3_MELHORIA_DETECTAVEL, LARGURA_MAXIMA_DA_POPULACAO,
    MINIMO_DE_CLUSTERS, PREFERENCIA, proximo_trimestre,
)

SEMENTE = 20260909
REAMOSTRAGENS = 2000


def _carregar() -> dict[tuple[str, str, str], list[dict]]:
    grupos: dict[tuple[str, str, str], list[dict]] = collections.defaultdict(list)
    for linha in FATOS.open(encoding="utf-8"):
        fato = json.loads(linha)
        periodo = fato["periodo"]
        if len(periodo) != 6 or periodo[4] != "T":
            continue
        grupos[
            (fato["cd_cvm_do_fato"], periodo, fato["fonte_id"])
        ].append(fato)
    return grupos


def _safra(grupo: list[dict]) -> tuple[str, str | None]:
    origens = {f["origem_periodo"] for f in grupo}
    base = (
        "original" if origens == {"propria"}
        else "derivada_de_originais" if origens == {"derivada"}
        else "as_restated"
    )
    datas = [f["disponivel_em"] for f in grupo if f["disponivel_em"]]
    data = max(datas) if len(datas) == len(grupo) else None
    if base == "derivada_de_originais" and data is None:
        base = "derivada_sem_certificacao"
    return base, data


def _soma(fatos: list[dict]) -> Decimal:
    return sum(Decimal(f["valor"]) for f in fatos)


def _melhor_safra(grupos, construir):
    """Uma linha por (emissor, trimestre), com a safra de maior precedência."""
    melhor: dict[tuple[str, str], tuple] = {}
    for (cd_cvm, periodo, _), grupo in grupos.items():
        valor = construir(grupo)
        if valor is None:
            continue
        base, data = _safra(grupo)
        posto = (PREFERENCIA.get(base, 9), data or "9999-99-99")
        atual = melhor.get((cd_cvm, periodo))
        if atual is None or posto < atual[0]:
            melhor[(cd_cvm, periodo)] = (posto, valor)
    return {chave: v for chave, (_, v) in melhor.items()}


def _poder(erros_por_emissor: dict[str, list[float]]) -> dict:
    """Mesma conta do G3: bootstrap agrupado por EMISSOR."""
    mae = statistics.fmean(
        statistics.fmean(v) for v in erros_por_emissor.values()
    )
    aleatorio = random.Random(SEMENTE)
    chaves = list(erros_por_emissor)
    medias = [
        statistics.fmean(
            statistics.fmean(erros_por_emissor[aleatorio.choice(chaves)])
            for _ in chaves
        )
        for _ in range(REAMOSTRAGENS)
    ]
    relativa = FATOR_DE_PODER * statistics.stdev(medias) / mae if mae else None
    maes = sorted(statistics.fmean(v) for v in erros_por_emissor.values())
    # Contrato C6 do parecer de 11/09. O achado F3 estabeleceu que esta conta
    # reamostra a DISPERSÃO DA PERDA do baseline, não a DIFERENÇA PAREADA
    # entre desafiante e baseline — que é a quantidade da qual o poder
    # depende. O pacote de 10/09 declarou F3 adiado e disse que a conta ficara
    # inócua por não haver população; **não ficou**: os cenários de
    # volatilidade continuavam produzindo `decidivel=true`, `ressalva=null` e
    # "16 emissores necessários" com selo de válido.
    #
    # A quarentena PUBLICA E INVALIDA, em vez de apagar (recomendação R1 da
    # revisão da conferência): os números seguem no artefato, marcados. Só a
    # afirmação de decidibilidade sai.
    clusters_ok = len(chaves) >= MINIMO_DE_CLUSTERS
    motivos = [
        "F3: a conta reamostra a dispersão da perda do baseline eleito, não "
        "a diferença pareada entre desafiante e baseline. Enquanto não for "
        "redesenhada, os números abaixo NÃO estimam poder."
    ]
    # **Menos clusters que o mínimo torna a conta NÃO DECIDÍVEL, e não
    # otimista.** Dois emissores que por acaso têm MAE parecido produzem
    # variância entre clusters quase nula, erro padrão minúsculo e um
    # "emissores necessários ~1" que é artefato de ter perdido justamente o
    # emissor que se comportava diferente. Ler esse 1 como boa notícia
    # seria a armadilha de aprovar por ausência de dado (AGENTS.md §3.14).
    if not clusters_ok:
        motivos.append(
            f"{len(chaves)} clusters, abaixo do mínimo {MINIMO_DE_CLUSTERS}: "
            "a melhoria detectável e o número de emissores necessários NÃO "
            "são interpretáveis neste cenário."
        )
    return {
        "decidivel": False,
        "clusters_suficientes": clusters_ok,
        "calculo_de_poder_invalidado_por": "F3",
        "ressalva": " | ".join(motivos),
        "emissores": len(chaves),
        "mae_macro": round(mae, 6),
        "mae_por_emissor": {
            cd: round(statistics.fmean(v), 6)
            for cd, v in sorted(erros_por_emissor.items())
        },
        "dispersao_max_sobre_min": round(maes[-1] / maes[0], 3) if maes[0] else None,
        # `if relativa` transformaria um zero legítimo — todos os emissores
        # com o mesmo erro — em "não medido". Zero é resultado, não ausência.
        "melhoria_minima_detectavel_relativa": (
            round(relativa, 4) if relativa is not None else None
        ),
        # Mantidos no artefato e marcados, não removidos: o revisor pediu
        # "o cálculo continua publicado, mas está invalidado" em vez de
        # "deixou de existir".
        "emissores_necessarios": (
            math.ceil(len(chaves) * (relativa / G3_MELHORIA_DETECTAVEL) ** 2)
            if relativa is not None else None
        ),
        "leitura_dos_dois_campos_acima": (
            "INVALIDADOS por F3. Preservados para auditoria do que foi "
            "publicado, não para uso como estimativa de poder."
        ),
    }


def cenario_intervalo(grupos, forcar_suspeitas_em_J: bool) -> dict:
    """J como intervalo, com o corte de largura do pré-registro.

    `forcar_suspeitas_em_J=False` é o **estado conforme** — o que o pipeline
    faz hoje, com as rubricas de câmbio embutido como NÃO IDENTIFICADAS.
    `True` reconstrói o **estado anterior, não conforme**, somando-as em J
    como se fossem juros por competência.

    A comparação já foi feita no outro sentido, quando as rubricas ainda
    estavam dentro de J e a pergunta era "e se saírem?". Depois que a leitura
    das notas respondeu que a parcela cambial **não é separável**, elas saíram
    de verdade — e o script inverteu, para continuar medindo **o que a
    conformidade custou** em vez de comparar o estado atual consigo mesmo.
    """

    def construir(grupo):
        incluidas = [f for f in grupo if f["tratamento"] == "incluir"]
        residuais = [f for f in grupo if f["tratamento"] == "nao_identificado"]
        if forcar_suspeitas_em_J:
            # Devolve as suspeitas a J, reconstituindo o estado não conforme.
            voltando = [
                f for f in residuais if f["conceito"] in RUBRICAS_SUSPEITAS
            ]
            incluidas = incluidas + voltando
            residuais = [
                f for f in residuais if f["conceito"] not in RUBRICAS_SUSPEITAS
            ]
        totais = [f for f in grupo if f["tratamento"] == "total"]
        if not incluidas or not totais:
            return None
        soma = -_soma(incluidas)
        residuo = -_soma(residuais)
        excluido = -_soma([f for f in grupo if f["tratamento"] == "excluir"])
        # Fechamento continua sendo pré-condição: mover parcela entre
        # categorias não pode fazer a soma deixar de dar o total impresso.
        if soma + excluido + residuo != -_soma(totais):
            return None
        # Achado F1 da revisão independente de 2026-09-10, aplicado aqui
        # TAMBÉM. Este script reimplementava a regra de limites do extrator —
        # `min/max(soma, soma+residuo)` — e portanto herdou o mesmo defeito:
        # o residual LÍQUIDO de uma rubrica que mistura juros e câmbio não
        # limita a parcela de juros, porque câmbio tem os dois sinais. Sem
        # limite demonstrável não há intervalo, e o par sai da população.
        #
        # Lógica duplicada é o que fez o defeito precisar de duas correções.
        if residuais and not all(
            f.get("limite_demonstravel") and Decimal(f["valor"]) <= 0
            for f in residuais
        ):
            return None
        return float(min(soma, soma + residuo)), float(max(soma, soma + residuo))

    bruto = _melhor_safra(grupos, construir)
    observacoes, cortados = {}, 0
    for chave, (inferior, superior) in bruto.items():
        centro = (inferior + superior) / 2
        if centro <= 0 or (superior - inferior) / 2 / abs(centro) > (
            LARGURA_MAXIMA_DA_POPULACAO
        ):
            cortados += 1
            continue
        observacoes[chave] = (inferior, superior, centro)

    erros: dict[str, list[float]] = collections.defaultdict(list)
    ruidos, sinais = [], []
    for (cd_cvm, periodo), (inferior, superior, centro) in observacoes.items():
        seguinte = observacoes.get((cd_cvm, proximo_trimestre(periodo)))
        if seguinte is None or inferior <= 0 or seguinte[0] <= 0:
            continue
        y_inferior = math.log(seguinte[0] / superior)
        y_superior = math.log(seguinte[1] / inferior)
        y_centro = math.log(seguinte[2] / centro)
        ruidos.append((y_superior - y_inferior) / 2)
        sinais.append(abs(y_centro))
        erros[cd_cvm].append(abs(y_centro))  # B0 prevê zero
    if not ruidos or len(erros) < 2:
        return {
            "pares_antes_do_corte": len(bruto),
            "cortados_por_largura": cortados,
            "observacoes": len(observacoes),
            "alvos": len(ruidos),
            "emissores_restantes": sorted(erros),
            "veredito": (
                "cenário destrói a população: não sobram emissores ou alvos "
                "suficientes para medir poder"
            ),
        }
    ruido, sinal = statistics.median(ruidos), statistics.median(sinais)
    return {
        "pares_antes_do_corte": len(bruto),
        "cortados_por_largura": cortados,
        "observacoes": len(observacoes),
        "alvos": len(ruidos),
        "g2_meia_largura_mediana": round(ruido, 6),
        "g2_movimento_mediano": round(sinal, 6),
        "g2_razao_ruido_sobre_sinal": round(ruido / sinal, 4) if sinal else None,
        **_poder(erros),
    }


def cenario_volatilidade(grupos, com_suspeitas: bool) -> dict:
    """Parcelas somadas como PONTO. Não é J — mede só oscilação."""

    def construir(grupo):
        incluidas = [f for f in grupo if f["tratamento"] == "incluir"]
        if com_suspeitas:
            incluidas = incluidas + [
                f for f in grupo
                if f["tratamento"] == "nao_identificado"
                and f["conceito"] in RUBRICAS_SUSPEITAS
            ]
        if not incluidas:
            return None
        return float(-_soma(incluidas))

    serie = _melhor_safra(grupos, construir)
    erros: dict[str, list[float]] = collections.defaultdict(list)
    for (cd_cvm, periodo), valor in serie.items():
        seguinte = serie.get((cd_cvm, proximo_trimestre(periodo)))
        if seguinte is None or valor <= 0 or seguinte <= 0:
            continue
        erros[cd_cvm].append(abs(math.log(seguinte / valor)))
    if len(erros) < 2:
        return {"veredito": "amostra insuficiente"}
    return {
        "aviso": (
            "NÃO é J: falta uma parcela. Serve só para responder se as "
            "parcelas limpas oscilam como as dos outros emissores."
        ),
        "trimestres_por_emissor": {cd: len(v) for cd, v in sorted(erros.items())},
        **_poder(erros),
    }


def executar() -> dict:
    grupos = _carregar()
    return {
        "schema_version": "2.0.0",
        "candidato": "B-DFC-01J-M",
        "natureza": (
            "DIAGNÓSTICO de quanto a conformidade contratual custou ao rótulo. "
            "Não substitui gate nem altera limiar do pré-registro."
        ),
        "rubricas_suspeitas": sorted(RUBRICAS_SUSPEITAS),
        "o_que_mudou": (
            "A v1 deste artefato perguntava 'e se as rubricas de câmbio "
            "embutido saírem de J?'. A leitura das notas respondeu que a "
            "parcela cambial NÃO é separável, então elas saíram de verdade e "
            "a pergunta inverteu: quanto o estado conforme custa em relação "
            "ao anterior. Os dois cenários trocaram de nome, não de conta."
        ),
        "intervalo_conforme": cenario_intervalo(grupos, False),
        "intervalo_estado_anterior_nao_conforme": cenario_intervalo(
            grupos, True
        ),
        "volatilidade_conforme": cenario_volatilidade(grupos, False),
        "volatilidade_estado_anterior_nao_conforme": cenario_volatilidade(
            grupos, True
        ),
    }


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    relatorio = executar()
    (DESTINO / "sensibilidade.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    for chave in (
        "intervalo_conforme",
        "intervalo_estado_anterior_nao_conforme",
        "volatilidade_conforme",
        "volatilidade_estado_anterior_nao_conforme",
    ):
        dados = relatorio[chave]
        print(f"\n─── {chave} ───")
        for k, v in dados.items():
            if k in ("aviso", "natureza"):
                continue
            print(f"   {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
