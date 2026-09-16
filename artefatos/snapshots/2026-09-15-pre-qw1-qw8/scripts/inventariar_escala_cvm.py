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

Fixada antes de classificar, e deliberadamente conservadora:

1. **Conflito** = mesmo `(cd_cvm, cd_conta, dt_fim_exerc)` declarado com mais de
   uma `ESCALA_MOEDA`.
2. **Prova de que um rótulo está errado** = entre as declarações conflitantes,
   existe **valor bruto idêntico** sob escalas diferentes. Sem isso pode ser
   redenominação real, e o caso NÃO é adjudicável por aqui.
3. **Desempate** = a escala que a **DFP** declara, por ser a demonstração anual
   auditada. Se a DFP declarar mais de uma escala para o mesmo período, ou se
   não houver declaração na DFP, o caso sai **INDECIDÍVEL** e exige outra fonte.

**O que a regra NÃO faz:** não decide por maioria de votos (arquivamento
repetido não é evidência nova), não infere pela plausibilidade do valor, e não
corrige nada. Caso indecidível permanece indecidível.

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


def adjudicar(declaracoes) -> list[dict]:
    """Um caso por `(companhia, demonstrativo, conta, período)` conflitante.

    Aceita a lista crua (usada pelas contraprovas) ou o dicionário já agrupado
    que `coletar_declaracoes` devolve.
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
        por_valor: dict[float, set[str]] = defaultdict(set)
        for r in rs:
            por_valor[r["vl_conta"]].add(r["escala"])
        valores_em_conflito = sorted(
            v for v, e in por_valor.items() if len(e) > 1
        )
        escalas_na_dfp = sorted({r["escala"] for r in rs if r["conjunto"] == "dfp"})

        if not valores_em_conflito:
            veredito, escala_correta, motivo = (
                "INDECIDIVEL",
                None,
                "escalas diferem mas nenhum valor bruto coincide: pode ser "
                "redenominação real, e não há prova de rótulo errado",
            )
        elif len(escalas_na_dfp) == 1:
            veredito, escala_correta = "ADJUDICAVEL_PELA_DFP", escalas_na_dfp[0]
            motivo = (
                f"valor bruto idêntico declarado sob {sorted(escalas)}; a DFP "
                f"anual auditada declara {escalas_na_dfp[0]} de forma única"
            )
        else:
            veredito, escala_correta = "INDECIDIVEL", None
            motivo = (
                "valor bruto idêntico sob escalas diferentes, mas a DFP "
                + (f"declara {escalas_na_dfp}" if escalas_na_dfp
                   else "não declara este período")
                + ": exige outra fonte para adjudicar"
            )

        casos.append({
            "cd_cvm": cd_cvm,
            "demonstrativo": demonstrativo,
            "cd_conta": cd_conta,
            "dt_ini_exerc": dt_ini,
            "dt_fim_exerc": dt_fim,
            "veredito": veredito,
            "escala_correta": escala_correta,
            "motivo": motivo,
            "escalas_declaradas": sorted(escalas),
            "escalas_na_dfp": escalas_na_dfp,
            "valores_em_conflito": valores_em_conflito,
            "declaracoes": sorted(
                (
                    {
                        "arquivo": r["arquivo"], "membro": r["membro"],
                        "dt_refer": r["dt_refer"], "versao": r["versao"],
                        "ordem_exerc": r["ordem_exerc"], "conjunto": r["conjunto"],
                        "escala": r["escala"], "vl_conta": r["vl_conta"],
                    }
                    for r in rs
                ),
                key=lambda r: (r["dt_refer"], r["versao"], r["ordem_exerc"]),
            ),
        })
    return casos


def executar() -> dict:
    zips = sorted(ZIPS.glob("*_cia_aberta_*.zip"))
    if not zips:
        raise FileNotFoundError(f"nenhum ZIP da CVM em {ZIPS}")
    agrupadas, fontes, lidas = coletar_declaracoes(zips)
    casos = adjudicar(agrupadas)
    contagem = Counter(c["veredito"] for c in casos)
    adjudicados = [c for c in casos if c["veredito"] == "ADJUDICAVEL_PELA_DFP"]
    return {
        "natureza": (
            "INVENTÁRIO COM EVIDÊNCIA. Não é tabela de correção: nenhum valor "
            "foi alterado, nenhum painel foi tocado, nenhuma correção foi "
            "aplicada. Adjudicar cada caso e decidir a correção são passos "
            "seguintes, com contrato próprio."
        ),
        "escopo": (
            "TODAS as contas de TODOS os demonstrativos consolidados, em todos "
            "os 31 ZIPs. Cada (companhia, demonstrativo, conta, período) é "
            "adjudicado pela PRÓPRIA evidência — sem heurística sobre o que é "
            "conta monetária."
        ),
        "linhas_lidas": lidas,
        "casos_com_escala_conflitante": len(casos),
        "direcao_da_adjudicacao": dict(sorted(
            Counter(c["escala_correta"] for c in adjudicados).items()
        )),
        "por_veredito": dict(sorted(contagem.items())),
        "companhias_envolvidas": len({c["cd_cvm"] for c in casos}),
        "companhias_adjudicaveis": len({
            c["cd_cvm"] for c in casos
            if c["veredito"] == "ADJUDICAVEL_PELA_DFP"
        }),
        "regra_de_adjudicacao": (
            "conflito = mesma (cd_cvm, cd_conta, dt_fim_exerc) sob mais de uma "
            "ESCALA_MOEDA · prova de rótulo errado = valor bruto IDÊNTICO sob "
            "escalas diferentes · desempate = a escala que a DFP anual auditada "
            "declara, se ela declarar uma só. Sem prova ou sem desempate, "
            "INDECIDÍVEL — nunca maioria de votos nem plausibilidade do valor."
        ),
        "fontes_sha256": fontes,
        "casos": casos,
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
