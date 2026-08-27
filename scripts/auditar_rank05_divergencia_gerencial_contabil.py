"""Audita as pré-condições do rank 5 antes de qualquer componente aprendido.

O candidato pretende priorizar reconciliações gerencial × contábil para
revisão humana. O pré-registro separa dois universos que não compartilham
ontologia nem rótulo:

* L: LAJIDA/LAJIR de companhias não financeiras, sob a Resolução CVM 156;
* K: KPIs e resultados ajustados de bancos.

Este script mede somente observabilidade, tamanho amostral, existência de gold
e procedência point-in-time. Uma página detectada é candidata à anotação, não
um exemplo positivo. Nenhum modelo, embedding ou LLM é importado ou carregado.

Uso::

    python -m scripts.auditar_rank05_divergencia_gerencial_contabil
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


CANDIDATO = "Rank 5 — risco de divergência gerencial × contábil"
RANKING = Path("resultados/ranking_candidatos_ml_value_investing.md")
PRE_REGISTRO = Path(
    "resultados/pre_registro_rank05_divergencia_gerencial_contabil_2026-08-27.md"
)
GOLD_PADRAO = Path("conjunto_padrao/rank05_divergencia_gerencial_contabil.csv")
TERMOS_L = re.compile(r"\b(?:lajida|lajir|ebitda|ebit)\b", re.IGNORECASE)
TERMOS_KPI = (
    "inadimplencia",
    "npl",
    "custo do credito",
    "basileia",
    "capital principal",
    "indice de eficiencia",
    "margem financeira",
)


@dataclass(frozen=True)
class Documento:
    empresa: str
    trimestre: str
    documento: str
    url: str
    data_coleta: str
    hash_sha256: str


@dataclass(frozen=True)
class EvidenciaDocumento:
    empresa: str
    trimestre: str
    documento: str
    paginas_total: int
    paginas_lajida_lajir: tuple[int, ...]
    paginas_ponte_explicita_contabil_gerencial: tuple[int, ...]
    paginas_ponte_resultado_ajustado: tuple[int, ...]
    paginas_resultado_recorrente_ou_ajustado: tuple[int, ...]
    paginas_kpi_bancario: tuple[int, ...]


def _normalizar(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(
        caractere for caractere in decomposto if not unicodedata.combining(caractere)
    )
    return " ".join(sem_acentos.casefold().split())


def _linhas_tabela(markdown: str) -> list[str]:
    return [
        linha.strip()
        for linha in markdown.splitlines()
        if linha.strip().startswith("|") and linha.count("|") >= 4
    ]


def _tabela_tem_numeros(linhas: Sequence[str]) -> bool:
    return any(len(re.findall(r"(?<![A-Za-z])\d[\d.,%]*", linha)) >= 2 for linha in linhas)


def _rotulos_tabela(linhas: Sequence[str]) -> list[str]:
    rotulos: list[str] = []
    for linha in linhas:
        for celula in linha.strip("|").split("|"):
            limpa = re.sub(r"[*_`{}^]", "", celula)
            limpa = re.sub(r"\([^)]*\)|\[[^]]*\]", "", limpa)
            rotulo = _normalizar(limpa).strip(" :-")
            if rotulo and not set(rotulo) <= {"-", ":"}:
                rotulos.append(rotulo)
    return rotulos


def detectar_ponte_explicita(markdown: str) -> bool:
    """Detecta tabela numérica que nomeia contábil e gerencial no cabeçalho."""
    linhas = _linhas_tabela(markdown)
    if not _tabela_tem_numeros(linhas):
        return False
    return any(
        "contabil" in _normalizar(linha) and "gerencial" in _normalizar(linha)
        for linha in linhas
    )


def detectar_ponte_resultado_ajustado(markdown: str) -> bool:
    """Detecta uma ponte numérica, sem promover menção narrativa a rótulo."""
    linhas = _linhas_tabela(markdown)
    if not _tabela_tem_numeros(linhas):
        return False
    if detectar_ponte_explicita(markdown):
        return True

    # Formato BTG: colunas do mesmo período chamadas Contábil e Ajustado.
    if any(
        "contabil" in _normalizar(linha) and "ajustad" in _normalizar(linha)
        for linha in linhas
    ):
        texto = _normalizar(markdown)
        if "lucro" in texto or "resultado" in texto or "dre" in texto:
            return True

    # Formato Banco do Brasil: três linhas fecham a reconciliação.
    rotulos = _rotulos_tabela(linhas)
    tem_lucro_ajustado = any(
        rotulo.startswith("lucro liquido ajustado") for rotulo in rotulos
    )
    tem_ajuste = any(
        rotulo.startswith(termo)
        for rotulo in rotulos
        for termo in (
            "itens extraordinarios",
            "itens nao recorrentes",
            "ajustes extraordinarios",
        )
    )
    tem_lucro_sem_qualificador = any(rotulo == "lucro liquido" for rotulo in rotulos)
    return tem_lucro_ajustado and tem_ajuste and tem_lucro_sem_qualificador


def _paginas_ocr(caminho: Path) -> list[tuple[int, str]]:
    carga = json.loads(caminho.read_text(encoding="utf-8"))
    paginas = carga.get("ocr", {}).get("pages")
    if not isinstance(paginas, list):
        raise ValueError(f"cache OCR sem lista de páginas: {caminho}")
    resultado: list[tuple[int, str]] = []
    for posicao, pagina in enumerate(paginas):
        indice = pagina.get("index", posicao)
        markdown = pagina.get("markdown", "")
        if not isinstance(indice, int) or not isinstance(markdown, str):
            raise ValueError(f"página OCR inválida em {caminho}")
        resultado.append((indice + 1, markdown))
    return resultado


def carregar_metadados(caminho: Path) -> tuple[list[Documento], tuple[str, ...]]:
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        colunas = tuple(leitor.fieldnames or ())
        obrigatorias = {campo.name for campo in Documento.__dataclass_fields__.values()}
        if not obrigatorias <= set(colunas):
            raise ValueError(f"metadados sem colunas obrigatórias: {sorted(obrigatorias)}")
        documentos = [
            Documento(**{campo: linha[campo].strip() for campo in obrigatorias})
            for linha in leitor
        ]
    return documentos, colunas


def auditar_documento(documento: Documento, diretorio_ocr: Path) -> EvidenciaDocumento:
    caminho = diretorio_ocr / f"{documento.hash_sha256}.json"
    if not caminho.exists():
        raise FileNotFoundError(f"cache OCR ausente para {documento.documento}: {caminho}")
    paginas = _paginas_ocr(caminho)

    def selecionar(predicado: Callable[[str], bool]) -> tuple[int, ...]:
        return tuple(
            pagina
            for pagina, markdown in paginas
            if predicado(markdown)
        )

    def resultado_recorrente_ajustado(markdown: str) -> bool:
        texto = _normalizar(markdown)
        return ("lucro" in texto or "resultado" in texto) and (
            "recorrente" in texto or "ajustad" in texto
        )

    def kpi_bancario(markdown: str) -> bool:
        texto = _normalizar(markdown)
        return any(termo in texto for termo in TERMOS_KPI)

    return EvidenciaDocumento(
        empresa=documento.empresa,
        trimestre=documento.trimestre,
        documento=documento.documento,
        paginas_total=len(paginas),
        paginas_lajida_lajir=selecionar(lambda texto: bool(TERMOS_L.search(texto))),
        paginas_ponte_explicita_contabil_gerencial=selecionar(
            detectar_ponte_explicita
        ),
        paginas_ponte_resultado_ajustado=selecionar(
            detectar_ponte_resultado_ajustado
        ),
        paginas_resultado_recorrente_ou_ajustado=selecionar(
            resultado_recorrente_ajustado
        ),
        paginas_kpi_bancario=selecionar(kpi_bancario),
    )


def _hash(caminho: Path) -> str | None:
    return hashlib.sha256(caminho.read_bytes()).hexdigest() if caminho.exists() else None


def auditar(
    documentos: Sequence[Documento],
    colunas_metadados: Sequence[str],
    *,
    diretorio_ocr: Path,
    gold: Path | None = None,
) -> dict[str, object]:
    evidencias = [auditar_documento(documento, diretorio_ocr) for documento in documentos]
    empresas = sorted({item.empresa for item in evidencias})
    trimestres = sorted({item.trimestre for item in evidencias})

    def docs_com(campo: str) -> list[EvidenciaDocumento]:
        return [item for item in evidencias if getattr(item, campo)]

    docs_l = docs_com("paginas_lajida_lajir")
    docs_explicita = docs_com("paginas_ponte_explicita_contabil_gerencial")
    docs_ajustada = docs_com("paginas_ponte_resultado_ajustado")
    docs_recorrente = docs_com("paginas_resultado_recorrente_ou_ajustado")
    docs_kpi = docs_com("paginas_kpi_bancario")
    caminho_gold = gold or GOLD_PADRAO
    gold_presente = caminho_gold.exists()
    tem_data_publicacao = "data_publicacao_original" in colunas_metadados
    tem_versao = "versao_documento" in colunas_metadados
    pit_aprovado = tem_data_publicacao and tem_versao
    amostra_aprovada = len(evidencias) >= 30 and len(empresas) >= 10

    gates = {
        "G0_L_observabilidade_lajida_lajir": len(docs_l) > 0,
        "G0_K_observabilidade_ponte_bancaria": len(docs_ajustada) > 0,
        "G1_procedencia_point_in_time": pit_aprovado,
        "G2_gold_duplo_adjudicado": gold_presente,
        "G3_baselines_pontuados_no_gold": False,
        "G4_amostra_minima_30_releases_10_emissores": amostra_aprovada,
        "G5_incrementalidade_do_aprendido": False,
        "G6_estudo_de_fluxo_humano": False,
    }
    razoes = [
        nome for nome, aprovado in gates.items() if not aprovado
    ]
    contagem_empresas_ajustada = Counter(item.empresa for item in docs_ajustada)

    return {
        "candidato": CANDIDATO,
        "natureza": (
            "auditoria de pré-condições; páginas são candidatas à anotação, "
            "não rótulos; nenhum modelo foi carregado"
        ),
        "fontes_normativas": {
            "ranking": {"caminho": str(RANKING), "sha256": _hash(RANKING)},
            "pre_registro": {
                "caminho": str(PRE_REGISTRO),
                "sha256": _hash(PRE_REGISTRO),
            },
        },
        "corpus": {
            "n_documentos": len(evidencias),
            "n_empresas": len(empresas),
            "empresas": empresas,
            "n_trimestres": len(trimestres),
            "trimestres": trimestres,
            "n_paginas": sum(item.paginas_total for item in evidencias),
            "colunas_metadados": list(colunas_metadados),
            "tem_data_publicacao_original": tem_data_publicacao,
            "tem_versao_documento": tem_versao,
        },
        "observabilidade": {
            "L_lajida_lajir": {
                "documentos": len(docs_l),
                "empresas": sorted({item.empresa for item in docs_l}),
                "paginas": sum(len(item.paginas_lajida_lajir) for item in docs_l),
            },
            "K_ponte_explicita_contabil_gerencial": {
                "documentos": len(docs_explicita),
                "empresas": sorted({item.empresa for item in docs_explicita}),
                "paginas": sum(
                    len(item.paginas_ponte_explicita_contabil_gerencial)
                    for item in docs_explicita
                ),
            },
            "K_ponte_resultado_ajustado": {
                "documentos": len(docs_ajustada),
                "empresas": sorted({item.empresa for item in docs_ajustada}),
                "documentos_por_empresa": dict(sorted(contagem_empresas_ajustada.items())),
                "paginas": sum(
                    len(item.paginas_ponte_resultado_ajustado)
                    for item in docs_ajustada
                ),
            },
            "resultado_recorrente_ou_ajustado": {
                "documentos": len(docs_recorrente),
                "empresas": sorted({item.empresa for item in docs_recorrente}),
            },
            "K_kpis_bancarios": {
                "documentos": len(docs_kpi),
                "empresas": sorted({item.empresa for item in docs_kpi}),
            },
        },
        "evidencia_humana": {
            "caminho_gold": str(caminho_gold),
            "gold_presente": gold_presente,
            "observacao": "contagem de páginas/documentos não substitui dupla leitura",
        },
        "limiares_pre_registrados": {
            "piloto_minimo_releases": 30,
            "confirmatorio_minimo_releases": 100,
            "confirmatorio_minimo_emissores": 10,
            "eventos_P2_P3_antes_de_congelar_piloto": 30,
        },
        "gates": gates,
        "razoes": razoes,
        "modelo_carregado": False,
        "estado_cientifico_ml": "INDECIDIVEL",
        "decisao_de_engenharia_ml": "NAO_IMPLEMENTAR_ML_AGORA",
        "proxima_etapa_autorizada": (
            "extrator determinístico de pontes e construção de gold humano; "
            "K exige ontologia própria e não herda o alvo L"
        ),
    }


def principal() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadados", type=Path, default=Path("corpus/metadados.csv"))
    parser.add_argument("--ocr", type=Path, default=Path("corpus/ocr"))
    parser.add_argument("--gold", type=Path)
    parser.add_argument(
        "--saida",
        type=Path,
        default=Path("artefatos/rank05/auditoria_precondicoes.json"),
    )
    args = parser.parse_args()
    documentos, colunas = carregar_metadados(args.metadados)
    resultado = auditar(
        documentos,
        colunas,
        diretorio_ocr=args.ocr,
        gold=args.gold,
    )
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
