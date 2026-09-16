"""Inventário das declarações conflitantes de escala nos arquivos da CVM.

**Isto é inventário com evidência, NÃO tabela de correção.** A revisão do Rank
3-B advertiu explicitamente contra *"converter um detector de suspeitas em
tabela automática de correções"*, e este script não escreve correção nenhuma,
não toca painel e não altera valor.

## O defeito

O campo `ESCALA_MOEDA` dos arquivos da CVM diz se `VL_CONTA` está em reais
(`UNIDADE`) ou em milhares (`MIL`). Em parte dos arquivamentos ele **contradiz
outro arquivamento do mesmo período**: o ITR declara `UNIDADE` onde a DFP
declara `MIL`, com o **valor bruto idêntico**. Como `19491` milhares não é
`19491` reais, um dos dois rótulos está errado — e o painel aplica os dois
fielmente, errando por 1.000×.

## Por que os CSVs primários, e não o painel

A adjudicação exige uma **segunda declaração independente do mesmo período**, e
é justamente ela que o painel descarta: a carga aplica a regra de armadilha e
mantém só `ORDEM_EXERC = 'ÚLTIMO'`. As declarações `PENÚLTIMO` — o mesmo período
reaparecendo como comparativo no arquivamento seguinte — vivem **só** nos CSVs
primários. Sem elas há suspeita; com elas há evidência.

## A regra de adjudicação, declarada

**Versão 2 (2026-09-15), por DECLARAÇÃO — contrato
`resultados/contratos_correcao_qw1_qw8_2026-09-15.md`, E1.** A versão 1
adjudicava o CASO inteiro a partir de qualquer coincidência de valor bruto —
inclusive **zero**, e `0 × 1.000 = 0 × 1` não identifica escala — e o consumidor
condenava toda declaração de escala diferente, **mesmo com outro valor**
(`100.000 UNIDADE` é exatamente o montante de `100 MIL`). A conferência de 15/09
mediu: 6.736 dos 10.261 casos adjudicados só tinham o zero como prova, e 292
declarações eram condenadas por extrapolação.

1. **Conflito de metadado** = mesma `(cd_cvm, demonstrativo, cd_conta,
   dt_ini_exerc, dt_fim_exerc)` sob mais de uma `ESCALA_MOEDA`.
2. **Evidência informativa não nula** = algum valor bruto **≠ 0** aparece sob
   escalas diferentes. Prova que ALGUM rótulo do caso está errado — não QUAL.
3. **Adjudicação por declaração** = uma declaração que não é da DFP, de escala
   diferente da que a DFP declara de forma única, cujo valor bruto **não nulo** é
   **idêntico** ao de uma declaração da DFP. É o único estado que adjudica.
   **Premissa, não prova:** a DFP anual auditada tem o rótulo certo.

**O que a regra NÃO faz:** não decide por maioria de votos (arquivamento
repetido não é evidência nova), não infere pela plausibilidade do valor, não
propaga a escala da DFP para declarações de outro valor, e não corrige nada.
Caso indecidível permanece indecidível.

**Nota de método, declarada:** a exploração dos CSVs veio antes de escrever esta
regra — foi ela que revelou que as declarações `PENÚLTIMO` existem e servem de
segunda fonte. Não há hipótese sob teste aqui: o produto é um inventário, e
nenhum limiar foi escolhido por desempenho observado.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ZIPS = RAIZ / "corpus" / "cvm"
DESTINO = RAIZ / "artefatos" / "escala_cvm"

#: **Escopo ampliado em 2026-09-12, com a MESMA regra.** A primeira versão usou
#: o ativo total como DETECTOR e registrava o documento, deixando em aberto
#: quais contas dele a correção alcançaria — porque escala não é uniforme dentro
#: de um documento (16.248 de 23.407 misturam `MIL` e `UNIDADE` legitimamente:
#: dinheiro em milhares, ações em unidades).
#:
#: Medido que a varredura completa custa ~2,3 min, a lacuna deixou de existir:
#: **cada `(companhia, demonstrativo, conta, período)` é adjudicado pela própria
#: evidência**, sem heurística nenhuma sobre o que é "conta monetária".
#:
#: Só consolidado (`_con_`): o individual é outra entidade contábil e não serve
#: de segunda declaração do mesmo fato.
SUFIXO_CONSOLIDADO = "_con_"
#: Tolerância de igualdade do valor bruto. Duas casas decimais: o campo vem com
#: dez, e diferença abaixo de um centavo não é redenominação.
CASAS = 2
#: Fator de cada `ESCALA_MOEDA` para reais. Escala fora daqui FALHA (contrato
#: E1.8): comparar montante com fator inventado seria pior que não comparar.
FATOR_DA_ESCALA = {"UNIDADE": 1.0, "MIL": 1_000.0, "MILHAO": 1_000_000.0}
#: Consumidor que não reconhecer esta versão tem de falhar, não reinterpretar.
VERSAO_DO_ESQUEMA = 2
#: **O único estado que adjudica** (contrato E1.2).
ADJUDICA = "rotulo_divergente_com_valor_identico_ao_da_dfp"
#: Vocabulário FECHADO do estado de cada declaração.
ESTADOS_DE_DECLARACAO = (
    "referencia_auditada",
    "dfp_ambigua",
    "sem_referencia_auditada",
    "mesma_escala_da_referencia",
    "zero_nao_informativo",
    ADJUDICA,
    "equivalente_em_reais_a_dfp",
    "evidencia_contraditoria",
    "sem_prova",
)
PREMISSA = (
    "Adjudicar supõe que a DFP anual auditada tem o rótulo certo quando o mesmo "
    "valor bruto NÃO NULO aparece sob outra escala. É premissa, não prova."
)


def _membros(arq: zipfile.ZipFile) -> list[str]:
    return sorted(m for m in arq.namelist() if SUFIXO_CONSOLIDADO in m)


def _demonstrativo(membro: str) -> str:
    """`itr_cia_aberta_BPA_con_2020.csv` → `BPA`.

    Entra na chave porque o mesmo `CD_CONTA` designa contas diferentes em
    demonstrativos diferentes — a armadilha que a RN09 combate.
    """
    return membro.split("_cia_aberta_")[-1].split(SUFIXO_CONSOLIDADO)[0]


def _varrer(zips: list[Path]):
    """Gera `(chave, declaração)` para cada linha consolidada dos ZIPs."""
    for caminho in sorted(zips):
        conjunto = "itr" if caminho.name.startswith("itr") else "dfp"
        with zipfile.ZipFile(caminho) as arq:
            for membro in _membros(arq):
                demonstrativo = _demonstrativo(membro)
                with arq.open(membro) as fh:
                    fluxo = io.TextIOWrapper(fh, encoding="latin-1", newline="")
                    for r in csv.DictReader(fluxo, delimiter=";"):
                        # `DT_INI_EXERC` só existe em DRE/DFC; balanço é
                        # posição, não período. Sem ele na chave, o acumulado
                        # e o isolado que terminam no mesmo dia colapsavam
                        # num caso só — e, tendo valores legitimamente
                        # diferentes, saíam todos INDECIDÍVEIS. Era por isso
                        # que nenhum caso de DRE ou DFC aparecia adjudicável.
                        dt_ini = r.get("DT_INI_EXERC") or ""
                        chave = (
                            r["CD_CVM"], demonstrativo, r["CD_CONTA"],
                            dt_ini, r["DT_FIM_EXERC"],
                        )
                        yield chave, {
                            "cd_cvm": r["CD_CVM"], "conjunto": conjunto,
                            "demonstrativo": demonstrativo,
                            "cd_conta": r["CD_CONTA"], "arquivo": caminho.name,
                            "membro": membro, "dt_refer": r["DT_REFER"],
                            "versao": int(r["VERSAO"]),
                            "ordem_exerc": r["ORDEM_EXERC"],
                            "dt_ini_exerc": dt_ini,
                            "dt_fim_exerc": r["DT_FIM_EXERC"],
                            "escala": r["ESCALA_MOEDA"],
                            "vl_conta": round(float(r["VL_CONTA"]), CASAS),
                        }


def coletar_declaracoes(zips: list[Path]) -> tuple[dict, dict, int]:
    """Duas passagens: acha as chaves conflitantes, depois só elas.

    A primeira passagem guarda apenas o conjunto de escalas por chave — compacto
    o bastante para os ~5,5 milhões de linhas. A segunda recolhe a procedência
    completa **só** das chaves que conflitam. Carregar tudo de uma vez estouraria
    a memória sem necessidade.
    """
    fontes = {
        caminho.name: hashlib.sha256(caminho.read_bytes()).hexdigest()
        for caminho in sorted(zips)
    }
    escalas_por_chave: dict[tuple, set[str]] = defaultdict(set)
    lidas = 0
    for chave, decl in _varrer(zips):
        escalas_por_chave[chave].add(decl["escala"])
        lidas += 1
    conflitantes = {k for k, v in escalas_por_chave.items() if len(v) > 1}
    del escalas_por_chave

    coletadas: dict[tuple, list[dict]] = defaultdict(list)
    for chave, decl in _varrer(zips):
        if chave in conflitantes:
            coletadas[chave].append(decl)
    return coletadas, fontes, lidas


def _fator(escala: str) -> float:
    try:
        return FATOR_DA_ESCALA[escala]
    except KeyError:
        raise ValueError(
            f"ESCALA_MOEDA desconhecida: {escala!r} — sem fator declarado não se "
            "compara montante"
        ) from None


def _estado_da_declaracao(r: dict, escala_ref: str | None,
                          dfp_nao_nulas: list[dict]) -> str:
    """Estado de UMA declaração (contrato E1.2). Só `ADJUDICA` adjudica.

    `escala_ref` é a escala que a DFP declara de forma única, ou `None`.
    `dfp_nao_nulas` são as declarações da DFP com valor bruto não nulo — zero
    não serve de termo de comparação (E1.4).
    """
    if r["conjunto"] == "dfp":
        return "referencia_auditada" if escala_ref else "dfp_ambigua"
    if escala_ref is None:
        return "sem_referencia_auditada"
    if r["escala"] == escala_ref:
        return "mesma_escala_da_referencia"
    if r["vl_conta"] == 0:
        return "zero_nao_informativo"
    identico = any(x["vl_conta"] == r["vl_conta"] for x in dfp_nao_nulas)
    # Mesmo montante em reais, na precisão da escala mais grossa: meia unidade
    # dela. Só contra declaração de valor bruto DIFERENTE — senão toda
    # identidade de valor pequeno contradiria a si mesma.
    tolerancia = 0.5 * max(_fator(escala_ref), _fator(r["escala"]))
    reais = r["vl_conta"] * _fator(r["escala"])
    equivalente = any(
        x["vl_conta"] != r["vl_conta"]
        and abs(x["vl_conta"] * _fator(escala_ref) - reais) <= tolerancia
        for x in dfp_nao_nulas
    )
    if identico and equivalente:
        return "evidencia_contraditoria"
    if identico:
        return ADJUDICA
    if equivalente:
        return "equivalente_em_reais_a_dfp"
    return "sem_prova"


def adjudicar(declaracoes) -> list[dict]:
    """Um caso por `(companhia, demonstrativo, conta, período)` conflitante.

    Aceita a lista crua (usada pelas contraprovas) ou o dicionário já agrupado
    que `coletar_declaracoes` devolve.

    **A decisão é por declaração** (contrato E1): o caso só é adjudicável se ao
    menos uma declaração estiver em `ADJUDICA`, e o consumidor tem de ler o
    campo `adjudicacao` de cada uma — nunca comparar toda declaração com a
    escala do grupo, que foi o defeito QW2.
    """
    if isinstance(declaracoes, dict):
        por_periodo = declaracoes
    else:
        por_periodo = defaultdict(list)
        for r in declaracoes:
            por_periodo[(
                r["cd_cvm"], r.get("demonstrativo", "BPA"),
                r.get("cd_conta", "1"), r.get("dt_ini_exerc", ""),
                r["dt_fim_exerc"],
            )].append(r)

    casos: list[dict] = []
    for (cd_cvm, demonstrativo, cd_conta, dt_ini, dt_fim), rs in sorted(
        por_periodo.items()
    ):
        escalas = {r["escala"] for r in rs}
        if len(escalas) < 2:
            continue
        for escala in escalas:
            _fator(escala)  # E1.8: escala desconhecida falha antes de decidir
        por_valor: dict[float, set[str]] = defaultdict(set)
        for r in rs:
            por_valor[r["vl_conta"]].add(r["escala"])
        valores_em_conflito = sorted(
            v for v, e in por_valor.items() if len(e) > 1
        )
        nao_nulos = [v for v in valores_em_conflito if v != 0]
        escalas_na_dfp = sorted({r["escala"] for r in rs if r["conjunto"] == "dfp"})
        escala_ref = escalas_na_dfp[0] if len(escalas_na_dfp) == 1 else None
        dfp_nao_nulas = [
            r for r in rs if r["conjunto"] == "dfp" and r["vl_conta"] != 0
        ]
        estados = [_estado_da_declaracao(r, escala_ref, dfp_nao_nulas) for r in rs]
        adjudicadas = sum(1 for e in estados if e == ADJUDICA)

        if adjudicadas:
            veredito = "ADJUDICAVEL_PELA_DFP"
            motivo = (
                f"{adjudicadas} declaração(ões) com valor bruto não nulo idêntico "
                f"ao da DFP sob escala diferente de {escala_ref}, que a DFP "
                f"declara de forma única. {PREMISSA}"
            )
        elif not valores_em_conflito:
            veredito, motivo = "INDECIDIVEL", (
                "escalas diferem mas nenhum valor bruto coincide: pode ser "
                "redenominação real, e não há prova de rótulo errado"
            )
        elif not nao_nulos:
            veredito, motivo = "INDECIDIVEL", (
                "a única coincidência de valor bruto é ZERO, que não identifica "
                "escala (0 × 1.000 = 0 × 1)"
            )
        elif escala_ref is None:
            veredito = "INDECIDIVEL"
            motivo = (
                "valor bruto não nulo idêntico sob escalas diferentes, mas a DFP "
                + (f"declara {escalas_na_dfp}" if escalas_na_dfp
                   else "não declara este período")
                + ": exige outra fonte para adjudicar"
            )
        elif "evidencia_contraditoria" in estados:
            veredito, motivo = "INDECIDIVEL", (
                "evidência contraditória: a declaração coincide com um valor da "
                "DFP e equivale em reais a outro valor da própria DFP"
            )
        else:
            veredito, motivo = "INDECIDIVEL", (
                "a coincidência não nula não envolve valor declarado pela DFP: "
                "prova que algum rótulo está errado, não qual"
            )

        casos.append({
            "cd_cvm": cd_cvm,
            "demonstrativo": demonstrativo,
            "cd_conta": cd_conta,
            "dt_ini_exerc": dt_ini,
            "dt_fim_exerc": dt_fim,
            "veredito": veredito,
            # E1.6: o nome antigo (`escala_correta`) afirmava a escala certa do
            # GRUPO e foi lido como condenação de toda declaração divergente.
            # Só é preenchida quando alguma declaração foi adjudicada; a escala
            # da DFP em qualquer caso está em `escalas_na_dfp`.
            "escala_da_referencia_auditada": escala_ref if adjudicadas else None,
            "motivo": motivo,
            "escalas_declaradas": sorted(escalas),
            "escalas_na_dfp": escalas_na_dfp,
            "valores_em_conflito": valores_em_conflito,
            "evidencia_informativa_nao_nula": bool(nao_nulos),
            "declaracoes_adjudicadas": adjudicadas,
            "declaracoes": sorted(
                (
                    {
                        "arquivo": r["arquivo"], "membro": r["membro"],
                        "dt_refer": r["dt_refer"], "versao": r["versao"],
                        "ordem_exerc": r["ordem_exerc"], "conjunto": r["conjunto"],
                        "escala": r["escala"], "vl_conta": r["vl_conta"],
                        "adjudicacao": estado,
                    }
                    for r, estado in zip(rs, estados)
                ),
                # Chave completa: com empate em (dt_refer, versao, ordem), a
                # ordem de entrada decidia a saída.
                key=lambda r: (
                    r["dt_refer"], r["versao"], r["ordem_exerc"], r["conjunto"],
                    r["escala"], r["vl_conta"], r["arquivo"], r["membro"],
                ),
            ),
        })
    return casos


def executar() -> dict:
    zips = sorted(ZIPS.glob("*_cia_aberta_*.zip"))
    if not zips:
        raise FileNotFoundError(f"nenhum ZIP da CVM em {ZIPS}")
    agrupadas, fontes, lidas = coletar_declaracoes(zips)
    casos = adjudicar(agrupadas)
    return {**resumir(casos), "linhas_lidas": lidas, "fontes_sha256": fontes,
            "casos": casos}


def resumir(casos: list[dict]) -> dict:
    """Contagens do inventário. Separada de `executar` para ser recalculável
    a partir dos casos persistidos, sem revarrer os ZIPs."""
    contagem = Counter(c["veredito"] for c in casos)
    adjudicados = [c for c in casos if c["veredito"] == "ADJUDICAVEL_PELA_DFP"]
    declaracoes_adjudicadas = [
        (c, d) for c in casos for d in c["declaracoes"] if d["adjudicacao"] == ADJUDICA
    ]
    documentos = {
        (c["cd_cvm"], d["conjunto"], d["dt_refer"], d["versao"])
        for c, d in declaracoes_adjudicadas
    }
    return {
        "natureza": (
            "INVENTÁRIO COM EVIDÊNCIA. Não é tabela de correção: nenhum valor "
            "foi alterado, nenhum painel foi tocado, nenhuma correção foi "
            "aplicada. Adjudicar cada caso e decidir a correção são passos "
            "seguintes, com contrato próprio."
        ),
        "versao_do_esquema": VERSAO_DO_ESQUEMA,
        "escopo": (
            "TODAS as contas de TODOS os demonstrativos consolidados, em todos "
            "os 31 ZIPs. Cada declaração de cada (companhia, demonstrativo, "
            "conta, período) conflitante recebe um estado próprio — sem "
            "heurística sobre o que é conta monetária."
        ),
        "casos_com_escala_conflitante": len(casos),
        "casos_com_evidencia_informativa_nao_nula": sum(
            1 for c in casos if c["evidencia_informativa_nao_nula"]
        ),
        "direcao_da_adjudicacao": dict(sorted(
            Counter(c["escala_da_referencia_auditada"] for c in adjudicados).items()
        )),
        "por_veredito": dict(sorted(contagem.items())),
        "declaracoes_por_estado": dict(sorted(
            Counter(d["adjudicacao"] for c in casos for d in c["declaracoes"]).items()
        )),
        "declaracoes_adjudicadas_por_ordem_exerc": dict(sorted(
            Counter(d["ordem_exerc"] for _, d in declaracoes_adjudicadas).items()
        )),
        "demonstrativos_adjudicados": dict(sorted(
            Counter(c["demonstrativo"] for c in adjudicados).items()
        )),
        "companhias_envolvidas": len({c["cd_cvm"] for c in casos}),
        "companhias_adjudicaveis": len({c["cd_cvm"] for c in adjudicados}),
        "documentos_com_declaracao_adjudicada": len(documentos),
        "identidade_do_documento": "(cd_cvm, conjunto, dt_refer, versao)",
        "regra_de_adjudicacao": (
            "chave = (cd_cvm, demonstrativo, cd_conta, dt_ini_exerc, "
            "dt_fim_exerc) · conflito de metadado = a chave sob mais de uma "
            "ESCALA_MOEDA · evidência informativa = valor bruto NÃO NULO sob "
            "escalas diferentes (prova que algum rótulo erra, não qual) · "
            f"adjudica UMA declaração ({ADJUDICA}) quando ela não é da DFP, tem "
            "escala diferente da que a DFP declara de forma única e valor bruto "
            "não nulo IDÊNTICO ao de uma declaração da DFP. Zero nunca prova; "
            "montante equivalente em reais é evidência de rótulo certo; nunca "
            "maioria de votos, plausibilidade ou propagação para outro valor."
        ),
        "premissa": PREMISSA,
    }


def principal() -> int:
    relatorio = executar()
    DESTINO.mkdir(parents=True, exist_ok=True)
    casos = relatorio.pop("casos")
    # Inventário COMPLETO em JSONL — uma linha por caso, streamável. O JSON
    # único passava de 60 MB e ninguém abriria; o resumo ao lado dá as
    # contagens sem exigir a leitura do todo.
    with (DESTINO / "inventario.jsonl").open("w", encoding="utf-8") as saida:
        for caso in casos:
            saida.write(json.dumps(caso, ensure_ascii=False) + "\n")
    (DESTINO / "resumo.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    relatorio["casos"] = casos
    print(f"Linhas lidas: {relatorio['linhas_lidas']}")
    print(f"Casos com escala conflitante: "
          f"{relatorio['casos_com_escala_conflitante']} "
          f"em {relatorio['companhias_envolvidas']} companhias")
    print(f"Direção da adjudicação: {relatorio['direcao_da_adjudicacao']}")
    for veredito, n in relatorio["por_veredito"].items():
        print(f"  {veredito:22s} {n}")
    print(f"Companhias adjudicáveis pela DFP: "
          f"{relatorio['companhias_adjudicaveis']}")
    print("NADA foi corrigido: este é inventário, não tabela de correção.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
