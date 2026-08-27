"""Audita precondições do CAND-03 antes de carregar qualquer modelo.

O candidato ordenaria alertas contábeis por prioridade de leitura. Milhões de
linhas contábeis não são milhões de rótulos: esta auditoria mede vintages,
cobertura semântica, metadados, demonstrativos e positivos confirmados antes de
permitir um challenger aprendido.

Uso::

    python -m scripts.auditar_cand03_anomalias
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

CANDIDATO = "CAND-03 — triagem de anomalias contábeis"
PRE_REGISTRO = Path(
    "resultados/pre_registro_cand03_anomalias_contabeis_2026-08-27.md"
)
PAINEL_TREINO = Path("artefatos/cvm_treino.duckdb")
PAINEL_CONSULTA = Path("artefatos/cvm.duckdb")
DIR_CVM_BRUTO = Path("corpus/cvm")
SAIDA = Path("artefatos/cand03/auditoria_precondicoes.json")


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _colunas(
    con: duckdb.DuckDBPyConnection, tabela: str
) -> set[str]:
    return {
        str(linha[0])
        for linha in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = ?
            """,
            [tabela],
        ).fetchall()
    }


def _auditar_painel_treino(caminho: Path) -> dict[str, Any]:
    with duckdb.connect(str(caminho), read_only=True) as con:
        (
            n_linhas,
            n_companhias,
            n_trimestres,
            n_companhia_trimestre,
            n_unidades_linha,
        ) = con.execute(
            """
            SELECT
                count(*),
                count(DISTINCT cd_cvm),
                count(DISTINCT trimestre),
                count(DISTINCT cd_cvm || '|' || trimestre),
                count(DISTINCT cd_cvm || '|' || trimestre || '|' ||
                      demonstrativo || '|' || ds_conta_norm)
            FROM fatos_contabeis
            """
        ).fetchone()
        demonstrativos = {
            str(nome): int(n)
            for nome, n in con.execute(
                """
                SELECT demonstrativo, count(*)
                FROM fatos_contabeis
                GROUP BY 1 ORDER BY 1
                """
            ).fetchall()
        }
        n_linhas_mapeadas = int(
            con.execute(
                """
                SELECT count(*)
                FROM fatos_contabeis AS f
                JOIN companhias AS c USING (cd_cvm)
                WHERE EXISTS (
                    SELECT 1
                    FROM mapa_contas AS m
                    WHERE m.plano_contas = c.plano_contas
                      AND m.cd_conta = f.cd_conta
                      AND m.ds_conta_norm = f.ds_conta_norm
                )
                """
            ).fetchone()[0]
        )
        n_conceitos, n_entradas_mapa = con.execute(
            """
            SELECT count(DISTINCT conceito), count(*)
            FROM mapa_contas
            """
        ).fetchone()
        n_cias, n_setor, n_ticker = con.execute(
            """
            SELECT count(*), count(setor), count(ticker)
            FROM companhias
            """
        ).fetchone()
        n_obs_versao, n_republicadas = con.execute(
            """
            WITH versao AS (
                SELECT cd_cvm, trimestre, max(versao_documento) AS vmax
                FROM fatos_contabeis
                GROUP BY 1, 2
            )
            SELECT count(*), count(*) FILTER (WHERE vmax > 1)
            FROM versao
            """
        ).fetchone()
        n_duplicadas_semanticas, n_conflitantes_semanticas = con.execute(
            """
            SELECT
                count(*),
                count(*) FILTER (WHERE n_valores > 1)
            FROM (
                SELECT
                    cd_cvm,
                    trimestre,
                    conceito,
                    count(DISTINCT valor_reais) AS n_valores
                FROM fatos_semanticos
                GROUP BY 1, 2, 3
                HAVING count(*) > 1
            )
            """
        ).fetchone()
        n_grupos_multiversao = con.execute(
            """
            SELECT count(*)
            FROM (
                SELECT
                    cd_cvm,
                    conjunto,
                    demonstrativo,
                    dt_refer,
                    count(DISTINCT versao_documento) AS n_versoes
                FROM fatos_contabeis
                GROUP BY 1, 2, 3, 4
                HAVING n_versoes > 1
            )
            """
        ).fetchone()[0]
        colunas = _colunas(con, "fatos_contabeis")

    campos_primeira_recepcao = {
        "dt_receb",
        "dt_recebimento",
        "data_recepcao",
        "primeira_recepcao",
    }
    tem_primeira_recepcao = bool(
        {coluna.lower() for coluna in colunas} & campos_primeira_recepcao
    )
    return {
        "arquivo": str(caminho),
        "sha256": _sha256(caminho),
        "linhas_contabeis": int(n_linhas),
        "companhias": int(n_companhias),
        "trimestres": int(n_trimestres),
        "companhia_trimestre": int(n_companhia_trimestre),
        "unidades_linha_distintas": int(n_unidades_linha),
        "demonstrativos": demonstrativos,
        "tem_dfc": any(nome.startswith("DFC") for nome in demonstrativos),
        "tem_data_primeira_recepcao": tem_primeira_recepcao,
        "observacoes_com_versao": int(n_obs_versao),
        "observacoes_com_versao_maior_que_um": int(n_republicadas),
        "fracao_versao_maior_que_um": (
            float(n_republicadas / n_obs_versao) if n_obs_versao else 0.0
        ),
        "grupos_com_multiplas_versoes_numericas": int(
            n_grupos_multiversao
        ),
        "chaves_semanticas_duplicadas": int(n_duplicadas_semanticas),
        "chaves_semanticas_com_valores_conflitantes": int(
            n_conflitantes_semanticas
        ),
        "linhas_com_mapa_semantico": n_linhas_mapeadas,
        "fracao_linhas_com_mapa_semantico": (
            float(n_linhas_mapeadas / n_linhas) if n_linhas else 0.0
        ),
        "conceitos_semanticos": int(n_conceitos),
        "entradas_mapa": int(n_entradas_mapa),
        "companhias_cadastradas": int(n_cias),
        "companhias_com_setor": int(n_setor),
        "fracao_companhias_com_setor": (
            float(n_setor / n_cias) if n_cias else 0.0
        ),
        "companhias_com_ticker": int(n_ticker),
    }


def _auditar_rotulos_e1(caminho: Path) -> dict[str, Any]:
    with duckdb.connect(str(caminho), read_only=True) as con:
        n_linhas, n_emissores, n_companhia_trimestre = con.execute(
            """
            SELECT
                count(*),
                count(DISTINCT cd_cvm),
                count(DISTINCT cd_cvm || '|' || trimestre)
            FROM correcoes_contabeis
            """
        ).fetchone()
    # Sem `cause_id`, nem companhia-trimestre prova independência. Este é
    # deliberadamente um limite superior, já suficiente para testar o gate 30.
    limite_superior = int(n_companhia_trimestre)
    return {
        "arquivo": str(caminho),
        "sha256": _sha256(caminho),
        "linhas_corrigidas": int(n_linhas),
        "emissores_com_correcao": int(n_emissores),
        "companhia_trimestre_com_correcao": int(n_companhia_trimestre),
        "causas_raiz_confirmadas": None,
        "limite_superior_causas_raiz": limite_superior,
        "observacao": (
            "Linhas corrigidas e companhia-trimestre são unidades aninhadas. "
            "A tabela não possui cause_id; o número reportado é só limite "
            "superior, não quantidade de rótulos independentes."
        ),
        "gate_e1_aprovado": (
            limite_superior >= 30
            and int(n_emissores) >= 10
        ),
    }


def _auditar_fontes_brutas(diretorio: Path | None) -> dict[str, Any]:
    """Confere se o bloqueio é de fonte ou da seleção feita pelo carregador."""
    pacotes = (
        sorted(diretorio.glob("*_cia_aberta_*.zip"))
        if diretorio and diretorio.is_dir()
        else []
    )
    com_geral = 0
    com_dt_receb = 0
    com_dfc = 0
    anos: set[int] = set()
    versoes_por_arquivamento: dict[
        tuple[str, str, str], list[tuple[int, date]]
    ] = defaultdict(list)
    n_linhas_metadados = 0
    for pacote in pacotes:
        partes = pacote.stem.split("_")
        tipo = partes[0]
        ano = int(partes[-1])
        anos.add(ano)
        nome_geral = f"{tipo}_cia_aberta_{ano}.csv"
        with zipfile.ZipFile(pacote) as arquivo:
            nomes = set(arquivo.namelist())
            if nome_geral in nomes:
                com_geral += 1
                with arquivo.open(nome_geral) as geral:
                    texto = io.TextIOWrapper(
                        geral, encoding="latin-1", errors="strict", newline=""
                    )
                    leitor = csv.DictReader(texto, delimiter=";")
                    campos = set(leitor.fieldnames or ())
                    if "DT_RECEB" in campos:
                        com_dt_receb += 1
                    for linha in leitor:
                        n_linhas_metadados += 1
                        chave = (
                            tipo,
                            str(linha["CD_CVM"]).strip(),
                            str(linha["DT_REFER"]).strip(),
                        )
                        versoes_por_arquivamento[chave].append(
                            (
                                int(linha["VERSAO"]),
                                date.fromisoformat(linha["DT_RECEB"]),
                            )
                        )
            if any(
                nome in nomes
                for nome in (
                    f"{tipo}_cia_aberta_DFC_MD_con_{ano}.csv",
                    f"{tipo}_cia_aberta_DFC_MI_con_{ano}.csv",
                )
            ):
                com_dfc += 1
    reapresentados = [
        versoes
        for versoes in versoes_por_arquivamento.values()
        if len({versao for versao, _ in versoes}) > 1
    ]
    atrasos = sorted(
        (max(data for _, data in versoes) - min(data for _, data in versoes)).days
        for versoes in reapresentados
    )
    if atrasos:
        posicao_p95 = (len(atrasos) - 1) * 0.95
        inferior = math.floor(posicao_p95)
        superior = math.ceil(posicao_p95)
        p95 = atrasos[inferior] + (
            atrasos[superior] - atrasos[inferior]
        ) * (posicao_p95 - inferior)
    else:
        p95 = None
    return {
        "diretorio": str(diretorio) if diretorio else None,
        "pacotes": len(pacotes),
        "anos": sorted(anos),
        "pacotes_com_arquivo_geral": com_geral,
        "pacotes_com_dt_receb": com_dt_receb,
        "pacotes_com_dfc_consolidada": com_dfc,
        "linhas_metadados_documento_versao": n_linhas_metadados,
        "arquivamentos_logicos": len(versoes_por_arquivamento),
        "arquivamentos_reapresentados": len(reapresentados),
        "fracao_arquivamentos_reapresentados": (
            len(reapresentados) / len(versoes_por_arquivamento)
            if versoes_por_arquivamento
            else 0.0
        ),
        "versao_maxima": max(
            (
                versao
                for versoes in versoes_por_arquivamento.values()
                for versao, _ in versoes
            ),
            default=None,
        ),
        "atraso_reapresentacao_dias": {
            "mediana": (
                statistics.median(atrasos) if atrasos else None
            ),
            "p95": round(p95, 1) if p95 is not None else None,
            "maximo": max(atrasos) if atrasos else None,
        },
        "dt_receb_disponivel_na_fonte": (
            bool(pacotes) and com_dt_receb == len(pacotes)
        ),
        "dfc_disponivel_na_fonte": (
            bool(pacotes) and com_dfc == len(pacotes)
        ),
        "observacao": (
            "Disponibilidade no ZIP não aprova G0: o painel precisa preservar "
            "DT_RECEB, cada versão e DFC na unidade usada pelo experimento."
        ),
    }


def auditar(
    painel_treino: Path = PAINEL_TREINO,
    painel_consulta: Path = PAINEL_CONSULTA,
    *,
    dir_cvm_bruto: Path | None = None,
    anotacoes_e2: Path | None = None,
    estudo_tempo: Path | None = None,
    eventos_e3: Path | None = None,
) -> dict[str, Any]:
    """Retorna o gate estrutural; não calcula score nem importa ML."""
    for caminho in (PRE_REGISTRO, painel_treino, painel_consulta):
        if not caminho.is_file():
            raise FileNotFoundError(caminho)

    treino = _auditar_painel_treino(painel_treino)
    e1 = _auditar_rotulos_e1(painel_consulta)
    fontes_brutas = _auditar_fontes_brutas(dir_cvm_bruto)
    anotacoes_presentes = bool(anotacoes_e2 and anotacoes_e2.is_file())
    tempo_presente = bool(estudo_tempo and estudo_tempo.is_file())
    eventos_e3_presentes = bool(eventos_e3 and eventos_e3.is_file())

    catalogo_material_presente = False
    gate_observabilidade = (
        treino["tem_data_primeira_recepcao"]
        and treino["tem_dfc"]
        and treino["fracao_companhias_com_setor"] >= 0.95
        and catalogo_material_presente
    )
    gate_e2 = anotacoes_presentes and tempo_presente
    gate_e3 = (
        eventos_e3_presentes
        and treino["tem_data_primeira_recepcao"]
    )

    razoes: list[str] = []
    if not treino["tem_data_primeira_recepcao"]:
        razoes.append("primeira_recepcao_e_vintages_ausentes")
    if not treino["tem_dfc"]:
        razoes.append("dfc_ausente_do_painel")
    if treino["fracao_companhias_com_setor"] < 0.95:
        razoes.append("controle_setorial_insuficiente")
    if not catalogo_material_presente:
        razoes.append("cobertura_de_contas_materiais_nao_auditada")
    if not e1["gate_e1_aprovado"]:
        razoes.append("rotulos_e1_independentes_insuficientes")
    if not anotacoes_presentes:
        razoes.append("gold_humano_e2_ausente")
    if not tempo_presente:
        razoes.append("estudo_humano_de_tempo_ausente")
    if not eventos_e3_presentes:
        razoes.append("eventos_externos_e3_ausentes")

    return {
        "candidato": CANDIDATO,
        "pre_registro": {
            "arquivo": str(PRE_REGISTRO),
            "sha256": _sha256(PRE_REGISTRO),
        },
        "modelo_carregado": False,
        "painel_treino": treino,
        "fontes_brutas": fontes_brutas,
        "estimandos": {
            "e1_erro_arquivamento": e1,
            "e2_prioridade_leitura": {
                "anotacoes_duplas_presentes": anotacoes_presentes,
                "estudo_tempo_presente": tempo_presente,
                "gate_e2_aprovado": gate_e2,
            },
            "e3_evento_futuro": {
                "eventos_externos_datados_presentes": eventos_e3_presentes,
                "gate_e3_aprovado": gate_e3,
            },
        },
        "gates": {
            "g0_observabilidade": gate_observabilidade,
            "g1_e1_rotulo": e1["gate_e1_aprovado"],
            "g1_e2_gold": gate_e2,
            "g1_e3_rotulo": gate_e3,
            "g2_baseline_validado": False,
        },
        "baseline_deterministico": "NAO_VALIDADO",
        "estado_cientifico_ml": "INDECIDIVEL",
        "decisao_de_engenharia_ml": "NAO_IMPLEMENTAR_AGORA",
        "razoes": razoes,
        "nota": (
            "A decisão impede carregar ML antes dos gates. Não rejeita a "
            "utilidade potencial de uma triagem determinística nem prova que "
            "um challenger aprendido perderia após novos dados e gold."
        ),
    }


def principal() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--painel-treino", type=Path, default=PAINEL_TREINO)
    parser.add_argument("--painel-consulta", type=Path, default=PAINEL_CONSULTA)
    parser.add_argument("--dir-cvm-bruto", type=Path, default=DIR_CVM_BRUTO)
    parser.add_argument("--anotacoes-e2", type=Path)
    parser.add_argument("--estudo-tempo", type=Path)
    parser.add_argument("--eventos-e3", type=Path)
    parser.add_argument("--saida", type=Path, default=SAIDA)
    args = parser.parse_args()

    resultado = auditar(
        args.painel_treino,
        args.painel_consulta,
        dir_cvm_bruto=args.dir_cvm_bruto,
        anotacoes_e2=args.anotacoes_e2,
        estudo_tempo=args.estudo_tempo,
        eventos_e3=args.eventos_e3,
    )
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
