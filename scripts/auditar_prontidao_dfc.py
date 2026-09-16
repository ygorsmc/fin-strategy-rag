"""Auditoria estrutural de DFC, sem alvo, treino ou acesso ao holdout.

Não certifica point-in-time: mede lacunas do painel as-restated. O corte
máximo é 1T2026, inclusive se o painel receber novos dados posteriormente.
Consultas por código + descrição servem à auditoria offline, não substituem
o mapa semântico validado exigido pela RN09 no produto.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import duckdb

CORTE_MAXIMO = date(2026, 3, 31)
DESCRICOES_FCO = (
    "caixa liquido atividades operacionais",
    "caixa liquido das atividades operacionais",
)


def sha256(caminho: Path) -> str:
    with caminho.open("rb") as arquivo:
        return hashlib.file_digest(arquivo, "sha256").hexdigest()


def auditar_csv_fco(caminho: Path) -> dict:
    """Conta vintages em UMA fonte bruta; não supõe completude do arquivo."""
    versoes = defaultdict(set)
    campos = {
        "CD_CVM", "DT_REFER", "DT_INI_EXERC", "DT_FIM_EXERC",
        "CD_CONTA", "ORDEM_EXERC", "VERSAO",
    }
    with caminho.open(encoding="latin-1", newline="") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")
        if not campos.issubset(leitor.fieldnames or []):
            raise ValueError("CSV não contém os campos necessários à auditoria")
        for linha in leitor:
            if (linha["CD_CONTA"] != "6.01"
                    or linha["ORDEM_EXERC"].upper() not in ("ÚLTIMO", "ULTIMO")
                    or date.fromisoformat(linha["DT_REFER"]) > CORTE_MAXIMO):
                continue
            chave = tuple(linha[c] for c in (
                "CD_CVM", "DT_REFER", "DT_INI_EXERC", "DT_FIM_EXERC"
            ))
            versoes[chave].add(linha["VERSAO"])
    if not versoes:
        raise ValueError("CSV sem FCO no recorte permitido")
    return {
        "caminho": str(caminho), "sha256": sha256(caminho),
        "chaves_codigo_6_01": len(versoes),
        "chaves_com_multiplas_versoes": sum(len(v) > 1 for v in versoes.values()),
        "pares_chave_versao": sum(map(len, versoes.values())),
        "nota": "Amostra de fonte, não inventário de todos os vintages históricos.",
    }


def auditar(con: duckdb.DuckDBPyConnection, corte: date = CORTE_MAXIMO) -> dict:
    """Somente SELECTs; nenhuma taxa de evento futuro é calculada."""
    if corte > CORTE_MAXIMO:
        raise ValueError("Corte invade período protegido posterior a 1T2026")

    def linhas(sql: str, parametros: list | None = None) -> list[dict]:
        resultado = con.execute(sql, [corte] if parametros is None else parametros)
        nomes = [item[0] for item in resultado.description]
        return [dict(zip(nomes, linha)) for linha in resultado.fetchall()]

    dfc = """SELECT * FROM fatos_contabeis
        WHERE demonstrativo IN ('DFC_MI', 'DFC_MD') AND dt_refer <= ?"""
    fco = f"""SELECT * FROM ({dfc})
        WHERE cd_conta = '6.01' AND ds_conta_norm IN (?, ?)"""
    parametros_fco = [corte, *DESCRICOES_FCO]
    cobertura = linhas(f"""
        SELECT demonstrativo, origem, count(*) AS linhas,
               count(DISTINCT cd_cvm) AS companhias
        FROM ({dfc}) GROUP BY 1, 2 ORDER BY 1, 2
    """)
    if not cobertura:
        raise ValueError("Sem DFC no recorte: auditoria não pode aprovar base vazia")

    recebimento = linhas(f"""
        WITH f AS (
            SELECT DISTINCT cd_cvm, conjunto, dt_refer, versao_documento
            FROM ({dfc}) WHERE origem = 'arquivado'
        )
        SELECT count(*) AS formularios_com_dfc,
               count(d.dt_receb) AS com_recebimento_da_mesma_versao,
               count(*) FILTER (WHERE d.dt_receb IS NULL) AS sem_recebimento,
               count(*) FILTER (WHERE d.dt_receb >
                   last_day(f.dt_refer + INTERVAL 3 MONTH)) AS recebidos_apos_decisao,
               count(*) FILTER (WHERE f.versao_documento > 1) AS versao_maior_que_1
        FROM f LEFT JOIN documentos d
          ON d.cd_cvm = f.cd_cvm AND d.conjunto = f.conjunto
         AND d.dt_refer = f.dt_refer AND d.versao = f.versao_documento
    """)[0]
    recebimento["regra_decisao_diagnostica"] = "last_day(dt_refer + 3 meses)"
    recebimento["nota"] = (
        "Diagnóstico por formulário, não amostra de ML; excluí-los não "
        "reconstrói versões anteriores nem a procedência dos derivados."
    )

    vintages = linhas(f"""
        WITH f AS (
            SELECT DISTINCT cd_cvm, conjunto, dt_refer, versao_documento
            FROM ({dfc}) WHERE origem = 'arquivado'
        )
        SELECT count(*) AS versoes_cadastradas_sem_fatos_dfc_retidos
        FROM documentos d
        WHERE EXISTS (
            SELECT 1 FROM f WHERE f.cd_cvm = d.cd_cvm
              AND f.conjunto = d.conjunto AND f.dt_refer = d.dt_refer
        ) AND NOT EXISTS (
            SELECT 1 FROM f WHERE f.cd_cvm = d.cd_cvm
              AND f.conjunto = d.conjunto AND f.dt_refer = d.dt_refer
              AND f.versao_documento = d.versao
        )
    """)[0]
    vintages["nota"] = (
        "Ausência nesta tabela, não prova de que cada versão histórica "
        "continha DFC ou de que os arquivos brutos não a preservam."
    )

    duracoes = linhas(f"""
        SELECT origem,
               date_diff('month', dt_ini_exerc,
                         dt_fim_exerc + INTERVAL 1 DAY) AS meses,
               count(*) AS linhas
        FROM ({fco}) WHERE tipo_periodo = 'trimestral'
        GROUP BY 1, 2 ORDER BY 1, 2
    """, parametros_fco)
    metodos = linhas(f"""
        WITH p AS (
            SELECT cd_cvm, trimestre, tipo_periodo, dt_ini_exerc, dt_fim_exerc,
                   count(DISTINCT demonstrativo) AS metodos,
                   count(*) AS linhas, min(valor_reais) AS menor,
                   max(valor_reais) AS maior
            FROM ({fco}) GROUP BY 1, 2, 3, 4, 5
        )
        SELECT count(*) FILTER (WHERE metodos > 1) AS pares_mi_md,
               count(*) FILTER (WHERE metodos > 1 AND maior - menor > 0.5)
                   AS pares_mi_md_divergentes,
               count(*) FILTER (WHERE linhas > metodos)
                   AS grupos_com_duplicata_intrametodo
        FROM p
    """, parametros_fco)[0]
    conceitos = linhas(f"""
        SELECT ds_conta_norm, count(*) AS linhas,
               count(DISTINCT cd_cvm) AS companhias
        FROM ({dfc}) WHERE cd_conta = '6.01'
        GROUP BY 1 ORDER BY 1
    """)
    resumo_fco = linhas(f"""
        SELECT count(*) AS linhas, count(DISTINCT cd_cvm) AS companhias
        FROM ({fco})
    """, parametros_fco)[0]
    setor = linhas("""
        SELECT count(*) AS companhias, count(setor) AS com_setor_preenchido
        FROM companhias
    """, [])[0]
    return {
        "tipo": "auditoria_estrutural_sem_modelo",
        "corte_referencia_inclusivo": corte.isoformat(),
        "holdout_acessado": False,
        "modelo_treinado": False,
        "certificacao_point_in_time": "NAO_REALIZADA",
        "cobertura_dfc": cobertura,
        "fco_codigo_e_descricao": resumo_fco,
        "descricoes_codigo_6_01": conceitos,
        "recebimento": recebimento,
        "vintages": vintages,
        "duracoes_fco_rotulado_trimestral": duracoes,
        "metodos_fco_mesmo_periodo": metodos,
        "cadastro_setorial_atual_nao_historico": setor,
    }


def principal() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--painel", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--csv-dfc-amostra", type=Path)
    args = parser.parse_args()
    entradas = [args.painel, args.csv_dfc_amostra, Path(__file__)]
    if args.saida.resolve() in [p.resolve() for p in entradas if p]:
        parser.error("saída não pode sobrescrever uma entrada ou o auditor")
    hash_antes = sha256(args.painel)
    with duckdb.connect(str(args.painel), read_only=True) as con:
        resultado = auditar(con)
    if hash_antes != sha256(args.painel):
        raise RuntimeError("Painel mudou durante a auditoria; resultado descartado")
    resultado["painel"] = {"caminho": str(args.painel), "sha256": hash_antes}
    if args.csv_dfc_amostra:
        resultado["amostra_fonte_bruta"] = auditar_csv_fco(args.csv_dfc_amostra)
    resultado["auditor_sha256"] = sha256(Path(__file__))
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
