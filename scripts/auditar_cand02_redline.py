"""Audita se CAND-02 tem evidência humana suficiente antes de carregar ML.

O candidato é um redline semântico que ordenaria mudanças entre releases
consecutivos por prioridade de leitura. O protocolo pré-registrado exige
dupla leitura completa, adjudicação e estudo de tempo. Sem isso, executar um
modelo produziria um ranking impossível de validar.

Este script deliberadamente não importa nem carrega embeddings ou LLM. Ele
mede o gate anterior ao algoritmo e grava um artefato reproduzível.

Uso::

    python -m scripts.auditar_cand02_redline
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from src.ingestao import DocumentoCorpus, carregar_metadados_corpus
from src.normalizacao import ordinal_trimestre

CANDIDATO = "CAND-02 — redline semântico para prioridade de leitura"
PRE_REGISTRO = Path("resultados/pre_registro_cand02_redline_2026-08-27.md")
PAPEIS_POR_TRANSICAO = {
    ("2T2025", "3T2025"): "desenvolvimento",
    ("3T2025", "4T2025"): "embargo",
    ("4T2025", "1T2026"): "teste",
}
COLUNAS_ANOTACOES = (
    "event_id",
    "pair_id",
    "reader_a",
    "grade_a",
    "critical_a",
    "judgable_a",
    "reader_b",
    "grade_b",
    "critical_b",
    "judgable_b",
    "adjudicator",
    "final_grade",
    "final_critical",
    "source",
)
COLUNAS_LEITURA = (
    "pair_id",
    "reader_a",
    "reader_b",
    "adjudicator",
    "leitura_completa",
)
COLUNAS_TEMPO = (
    "session_id",
    "analyst_id",
    "pair_id",
    "system",
    "duration_seconds",
    "p2_found",
    "errors",
)


@dataclass(frozen=True)
class ParDocumental:
    pair_id: str
    empresa: str
    trimestre_anterior: str
    trimestre_atual: str
    documento_anterior: str
    documento_atual: str
    papel: str


def construir_pares(documentos: Sequence[DocumentoCorpus]) -> list[ParDocumental]:
    """Cria pares adjacentes por empresa sem tratar chunks como réplicas."""
    por_empresa: dict[str, list[DocumentoCorpus]] = defaultdict(list)
    for documento in documentos:
        por_empresa[documento.empresa].append(documento)

    pares: list[ParDocumental] = []
    for empresa in sorted(por_empresa):
        ordenados = sorted(
            por_empresa[empresa], key=lambda item: ordinal_trimestre(item.trimestre)
        )
        for anterior, atual in zip(ordenados, ordenados[1:]):
            if (
                ordinal_trimestre(atual.trimestre)
                != ordinal_trimestre(anterior.trimestre) + 1
            ):
                raise ValueError(
                    f"trimestres não adjacentes para {empresa}: "
                    f"{anterior.trimestre} → {atual.trimestre}"
                )
            transicao = (anterior.trimestre, atual.trimestre)
            papel = PAPEIS_POR_TRANSICAO.get(transicao, "fora_do_protocolo")
            pares.append(
                ParDocumental(
                    pair_id=f"{empresa}:{anterior.trimestre}->{atual.trimestre}",
                    empresa=empresa,
                    trimestre_anterior=anterior.trimestre,
                    trimestre_atual=atual.trimestre,
                    documento_anterior=anterior.documento,
                    documento_atual=atual.documento,
                    papel=papel,
                )
            )
    return pares


def _ler_csv_estrito(caminho: Path, colunas: tuple[str, ...]) -> list[dict[str, str]]:
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        if tuple(leitor.fieldnames or ()) != colunas:
            raise ValueError(
                f"esquema inesperado em {caminho}: {leitor.fieldnames!r}; "
                f"esperado {colunas!r}"
            )
        return [dict(linha) for linha in leitor]


def _inteiro(texto: str, campo: str, *, minimo: int, maximo: int) -> int:
    try:
        valor = int(texto)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{campo} deve ser inteiro") from exc
    if not minimo <= valor <= maximo:
        raise ValueError(f"{campo} fora do intervalo [{minimo}, {maximo}]")
    return valor


def _booleano(texto: str, campo: str) -> bool:
    valor = texto.strip().lower()
    if valor in {"1", "true", "sim"}:
        return True
    if valor in {"0", "false", "nao", "não"}:
        return False
    raise ValueError(f"{campo} deve ser 0/1, true/false ou sim/não")


def alpha_krippendorff_ordinal(pares_notas: Iterable[tuple[int, int]]) -> float:
    """Krippendorff α com distância ordinal e dois leitores por evento."""
    pares = list(pares_notas)
    if not pares:
        return math.nan
    notas = [nota for par in pares for nota in par]
    contagens = Counter(notas)
    categorias = sorted(contagens)

    def distancia(a: int, b: int) -> float:
        if a == b:
            return 0.0
        inferior, superior = sorted((a, b))
        massa = sum(
            contagens[categoria]
            for categoria in categorias
            if inferior <= categoria <= superior
        )
        massa -= (contagens[inferior] + contagens[superior]) / 2.0
        return massa * massa

    observado = sum(distancia(a, b) for a, b in pares) / len(pares)
    n = len(notas)
    if n < 2:
        return math.nan
    esperado = sum(
        contagens[a]
        * (contagens[b] - (1 if a == b else 0))
        * distancia(a, b)
        for a in categorias
        for b in categorias
    ) / (n * (n - 1))
    if esperado == 0:
        return 1.0 if observado == 0 else math.nan
    return 1.0 - observado / esperado


def auditar_anotacoes(
    caminho: Path | None, pares_teste: Sequence[ParDocumental]
) -> dict[str, object]:
    if caminho is None or not caminho.exists():
        return {"presente": False, "gate_aprovado": False}

    linhas = _ler_csv_estrito(caminho, COLUNAS_ANOTACOES)
    ids_esperados = {par.pair_id for par in pares_teste}
    ids_eventos: set[str] = set()
    por_par: Counter[str] = Counter()
    pares_notas: list[tuple[int, int]] = []
    binarios: list[tuple[bool, bool]] = []
    finais: list[tuple[str, int]] = []
    nao_julgaveis = 0

    for numero, linha in enumerate(linhas, start=2):
        event_id = linha["event_id"].strip()
        pair_id = linha["pair_id"].strip()
        if not event_id or event_id in ids_eventos:
            raise ValueError(f"event_id vazio ou duplicado na linha {numero}")
        if pair_id not in ids_esperados:
            raise ValueError(f"pair_id fora do teste na linha {numero}: {pair_id}")
        if (
            not linha["reader_a"].strip()
            or not linha["reader_b"].strip()
            or linha["reader_a"].strip() == linha["reader_b"].strip()
        ):
            raise ValueError(f"leitores ausentes ou iguais na linha {numero}")
        if not linha["adjudicator"].strip():
            raise ValueError(f"adjudicador ausente na linha {numero}")
        julgavel_a = _booleano(linha["judgable_a"], "judgable_a")
        julgavel_b = _booleano(linha["judgable_b"], "judgable_b")
        ids_eventos.add(event_id)
        por_par[pair_id] += 1
        if not (julgavel_a and julgavel_b):
            nao_julgaveis += 1
            continue
        nota_a = _inteiro(linha["grade_a"], "grade_a", minimo=0, maximo=2)
        nota_b = _inteiro(linha["grade_b"], "grade_b", minimo=0, maximo=2)
        nota_final = _inteiro(
            linha["final_grade"], "final_grade", minimo=0, maximo=2
        )
        _booleano(linha["critical_a"], "critical_a")
        _booleano(linha["critical_b"], "critical_b")
        _booleano(linha["final_critical"], "final_critical")
        pares_notas.append((nota_a, nota_b))
        binarios.append((nota_a >= 1, nota_b >= 1))
        finais.append((pair_id, nota_final))

    alpha = alpha_krippendorff_ordinal(pares_notas)
    acordo_bruto = (
        sum(a == b for a, b in binarios) / len(binarios) if binarios else math.nan
    )
    ambos_positivos = sum(a and b for a, b in binarios)
    decisoes_positivas = sum(int(a) + int(b) for a, b in binarios)
    acordo_positivo = (
        2 * ambos_positivos / decisoes_positivas
        if decisoes_positivas
        else math.nan
    )
    positivos = sum(nota >= 1 for _, nota in finais)
    prioridade_2 = sum(nota == 2 for _, nota in finais)
    positivos_por_par = Counter(
        pair_id for pair_id, nota in finais if nota >= 1
    )
    fracao_nao_julgavel = nao_julgaveis / len(linhas) if linhas else 1.0
    gate = (
        len(linhas) >= 300
        and all(por_par[pair_id] >= 60 for pair_id in ids_esperados)
        and math.isfinite(alpha)
        and alpha >= 0.67
        and acordo_bruto >= 0.80
        and acordo_positivo >= 0.75
        and positivos >= 30
        and prioridade_2 >= 30
        and all(positivos_por_par[pair_id] >= 3 for pair_id in ids_esperados)
        and fracao_nao_julgavel <= 0.05
    )
    return {
        "presente": True,
        "n_eventos": len(linhas),
        "eventos_por_par": dict(sorted(por_par.items())),
        "alpha_krippendorff_ordinal": alpha,
        "acordo_binario_bruto": acordo_bruto,
        "acordo_positivo": acordo_positivo,
        "positivos_nota_ge_1": positivos,
        "positivos_nota_2": prioridade_2,
        "positivos_por_par": dict(sorted(positivos_por_par.items())),
        "fracao_nao_julgavel": fracao_nao_julgavel,
        "gate_aprovado": gate,
    }


def auditar_leitura_completa(
    caminho: Path | None, pares_esperados: Sequence[ParDocumental]
) -> dict[str, object]:
    if caminho is None or not caminho.exists():
        return {"presente": False, "gate_aprovado": False}
    linhas = _ler_csv_estrito(caminho, COLUNAS_LEITURA)
    esperados = {par.pair_id for par in pares_esperados}
    observados: set[str] = set()
    for numero, linha in enumerate(linhas, start=2):
        pair_id = linha["pair_id"].strip()
        leitores = (
            linha["reader_a"].strip(),
            linha["reader_b"].strip(),
            linha["adjudicator"].strip(),
        )
        if pair_id not in esperados or pair_id in observados:
            raise ValueError(f"pair_id inválido ou duplicado na linha {numero}")
        if any(not leitor for leitor in leitores) or len(set(leitores[:2])) != 2:
            raise ValueError(f"leitores inválidos na linha {numero}")
        if not _booleano(linha["leitura_completa"], "leitura_completa"):
            continue
        observados.add(pair_id)
    return {
        "presente": True,
        "pares_com_dupla_leitura_completa": sorted(observados),
        "gate_aprovado": observados == esperados,
    }


def auditar_estudo_tempo(
    caminho: Path | None, pares_teste: Sequence[ParDocumental]
) -> dict[str, object]:
    if caminho is None or not caminho.exists():
        return {"presente": False, "gate_aprovado": False}
    linhas = _ler_csv_estrito(caminho, COLUNAS_TEMPO)
    esperados = {par.pair_id for par in pares_teste}
    sessoes: set[str] = set()
    analistas: set[str] = set()
    sistemas: set[str] = set()
    pares: set[str] = set()
    exposicoes: dict[tuple[str, str], set[str]] = defaultdict(set)
    for numero, linha in enumerate(linhas, start=2):
        sessao = linha["session_id"].strip()
        analista = linha["analyst_id"].strip()
        pair_id = linha["pair_id"].strip()
        sistema = linha["system"].strip()
        if not sessao or sessao in sessoes:
            raise ValueError(f"session_id vazio ou duplicado na linha {numero}")
        if not analista or pair_id not in esperados or sistema not in {"B1", "ML"}:
            raise ValueError(f"sessão inválida na linha {numero}")
        if float(linha["duration_seconds"]) <= 0:
            raise ValueError(f"duration_seconds deve ser positivo na linha {numero}")
        _inteiro(linha["p2_found"], "p2_found", minimo=0, maximo=10_000)
        _inteiro(linha["errors"], "errors", minimo=0, maximo=10_000)
        sessoes.add(sessao)
        analistas.add(analista)
        sistemas.add(sistema)
        pares.add(pair_id)
        exposicoes[(analista, pair_id)].add(sistema)
    releitura_cruzada = any(len(vistos) > 1 for vistos in exposicoes.values())
    gate = (
        len(sessoes) >= 30
        and len(analistas) >= 4
        and sistemas == {"B1", "ML"}
        and pares == esperados
        and not releitura_cruzada
    )
    return {
        "presente": True,
        "n_sessoes": len(sessoes),
        "n_analistas": len(analistas),
        "sistemas": sorted(sistemas),
        "pares": sorted(pares),
        "mesmo_analista_releu_mesmo_par_em_outro_braco": releitura_cruzada,
        "gate_aprovado": gate,
    }


def auditar(
    documentos: Sequence[DocumentoCorpus],
    *,
    anotacoes: Path | None = None,
    manifesto_leitura: Path | None = None,
    estudo_tempo: Path | None = None,
) -> dict[str, object]:
    pares = construir_pares(documentos)
    contagem_papeis = Counter(par.papel for par in pares)
    pares_teste = [par for par in pares if par.papel == "teste"]
    docs_dev = {
        documento
        for par in pares
        if par.papel == "desenvolvimento"
        for documento in (par.documento_anterior, par.documento_atual)
    }
    docs_teste = {
        documento
        for par in pares_teste
        for documento in (par.documento_anterior, par.documento_atual)
    }
    compartilhados = sorted(docs_dev & docs_teste)
    estrutura_ok = (
        len(documentos) == 20
        and contagem_papeis
        == Counter({"desenvolvimento": 5, "embargo": 5, "teste": 5})
        and len({par.empresa for par in pares_teste}) == 5
        and not compartilhados
    )
    auditoria_anotacoes = auditar_anotacoes(anotacoes, pares_teste)
    auditoria_leitura = auditar_leitura_completa(manifesto_leitura, pares)
    auditoria_tempo = auditar_estudo_tempo(estudo_tempo, pares_teste)

    razoes: list[str] = []
    if not estrutura_ok:
        razoes.append("split_estrutural_invalido")
    if not auditoria_anotacoes["gate_aprovado"]:
        razoes.append("gabarito_duplo_insuficiente_ou_ausente")
    if not auditoria_leitura["gate_aprovado"]:
        razoes.append("leitura_completa_e_adjudicacao_ausentes")
    if not auditoria_tempo["gate_aprovado"]:
        razoes.append("estudo_humano_de_tempo_ausente")

    pronto = not razoes
    hash_pre_registro = (
        hashlib.sha256(PRE_REGISTRO.read_bytes()).hexdigest()
        if PRE_REGISTRO.exists()
        else None
    )
    return {
        "candidato": CANDIDATO,
        "natureza": "gate anterior ao algoritmo; nenhum modelo foi carregado",
        "pre_registro": {
            "caminho": str(PRE_REGISTRO),
            "sha256": hash_pre_registro,
        },
        "corpus": {
            "n_documentos": len(documentos),
            "n_pares_adjacentes": len(pares),
            "pares_por_papel": dict(sorted(contagem_papeis.items())),
            "clusters_independentes_no_teste": len(
                {par.empresa for par in pares_teste}
            ),
            "documentos_compartilhados_dev_teste": compartilhados,
            "estrutura_aprovada": estrutura_ok,
            "pares": [asdict(par) for par in pares],
        },
        "evidencia_humana": {
            "anotacoes": auditoria_anotacoes,
            "leitura_completa": auditoria_leitura,
            "estudo_tempo": auditoria_tempo,
        },
        "razoes": razoes,
        "estado_cientifico": "PRONTO_PARA_MEDIR" if pronto else "INDECIDIVEL",
        "decisao_de_implementacao_ml": (
            "PODE_EXECUTAR_COMPARACAO_PRE_REGISTRADA"
            if pronto
            else "NAO_IMPLEMENTAR_AGORA"
        ),
        "veredito": (
            "Pré-condições aprovadas; isto ainda não valida o componente aprendido."
            if pronto
            else "CAND-02 aprendido é indecidível e não deve ser implementado agora."
        ),
    }


def principal() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metadados", type=Path, default=Path("corpus/metadados.csv")
    )
    parser.add_argument("--anotacoes", type=Path)
    parser.add_argument("--manifesto-leitura", type=Path)
    parser.add_argument("--estudo-tempo", type=Path)
    parser.add_argument(
        "--saida",
        type=Path,
        default=Path("artefatos/cand02/auditoria_precondicoes.json"),
    )
    args = parser.parse_args()

    documentos = carregar_metadados_corpus(args.metadados)
    resultado = auditar(
        documentos,
        anotacoes=args.anotacoes,
        manifesto_leitura=args.manifesto_leitura,
        estudo_tempo=args.estudo_tempo,
    )
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
