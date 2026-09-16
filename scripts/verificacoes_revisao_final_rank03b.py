"""Verificações da revisão final do lote C do Rank 3-B, gravadas em artefato.

A auditoria de 16/09 apontou números publicados em
`resultados/painel_pesquisa_rank03b_lote_c_2026-09-16.md` §8 sem artefato que
os sustente. Este script os recalcula e grava em
`artefatos/painel_pesquisa_rank03b/verificacoes_revisao_final.json`:

- amostra de desenho (documentos `vmax` do piloto com estrato E1–E4) sob a
  regra final;
- conferência B8 (correções com um único número bruto) por continuidade do
  ativo bruto;
- a máscara de O1.3 sobre os trechos já publicados (quantos mudaria);
- a comparação de uma reexecução da adjudicação (`--reproducao DIR`) com a
  execução governante.

**Não calcula rótulo nem lê FCO para publicar** (O1): valores de caixa só
entram na máscara, e o artefato traz contagens.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

import duckdb

from scripts import adjudicar_escala_rank03b as adj
from scripts import fonte_rad_cvm as rad
from scripts import fonte_zip_cvm as fz
from scripts.piloto_fonte_rad_rank03b import _sem_chave_proibida

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "artefatos" / "painel_pesquisa_rank03b"
ESTRATOS_DE_DESENHO = ("E1", "E2", "E3", "E4")
JANELA_DE_VIZINHOS = 200
CAMPOS_COMPARADOS = ("veredito", "motivo", "escala_do_formulario", "evidencia",
                     "cabecalho", "numerica", "sha256")


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _jsonl(caminho: Path) -> list[dict]:
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines()]


def e_amostra_de_desenho(evidencia_do_piloto: dict) -> bool:
    """Versão máxima, íntegra, com algum estrato E1–E4."""
    estratos = evidencia_do_piloto["estratos"]
    return (evidencia_do_piloto["papel"] == "vmax"
            and evidencia_do_piloto["aquisicao"] == "integro"
            # Código até o "_": com prefixo, "E10_…" passaria por "E1".
            and any(e.split("_")[0] in ESTRATOS_DE_DESENHO for e in estratos))


def amostra_de_desenho(evidencias_piloto: list[dict], ler=None) -> dict:
    ler = ler or (lambda d: rad.ler(rad.BRUTOS / f"{d}.zip", grupos=rad.GRUPOS_NOTAS))
    contagem = Counter()
    for e in evidencias_piloto:
        if not e_amostra_de_desenho(e):
            continue
        r = adj.adjudicar_formulario(ler(e["id_doc"]), e["escala_declarada"])
        contagem[f"{e['escala_declarada']}|{r['veredito']}"] += 1
    return {"populacao": "piloto, papel vmax, integro, algum estrato E1-E4",
            "documentos": sum(contagem.values()), "por_declarada": dict(sorted(contagem.items()))}


def continuidade_b8(painel: duckdb.DuckDBPyConnection, ids: list[str]) -> list[dict]:
    """Razão entre o ativo bruto de cada vizinho declarado `MIL` e o do corrigido."""
    saida = []
    for i in ids:
        linha = painel.execute(
            "SELECT cd_cvm, dt_fim, valor_bruto FROM ativo WHERE id_correcao = ? AND estado = 'valido'",
            [i]).fetchone()
        if linha is None:
            saida.append({"id_correcao": i, "situacao": "sem_ativo_valido"})
            continue
        cd, dt, bruto = linha
        vizinhos = painel.execute(
            f"""SELECT escala_declarada, valor_bruto FROM ativo
                WHERE cd_cvm = ? AND estado = 'valido' AND dt_fim <> ?
                  AND abs(date_diff('day', dt_fim, ?::DATE)) <= {JANELA_DE_VIZINHOS}""",
            [cd, dt, dt]).fetchall()
        razoes = [round(v / bruto, 2) for e, v in vizinhos if e == "MIL" and bruto]
        saida.append({"id_correcao": i, "vizinhos": len(vizinhos),
                      "vizinhos_declarados_mil": len(razoes),
                      "razoes_com_vizinhos_mil": razoes,
                      "situacao": "corroborada" if razoes else "sem_vizinho_mil"})
    return saida


def correcoes_com_um_bruto(manifesto: Path) -> list[str]:
    with open(manifesto, encoding="utf-8", newline="") as fh:
        return [r["id_correcao"] for r in csv.DictReader(fh)
                if r["base"] == "corrigida_documento"
                and json.loads(r["numerica_contagem"])["bruto"] <= 1]


def mascara_sobre_publicados(con, evidencias: list[dict], manifesto: Path) -> dict:
    valores = {}
    for cd, cj, dr, conta, vl in con.execute(
            "SELECT cd_cvm, conjunto, CAST(dt_refer AS VARCHAR), cd_conta, vl FROM declaracoes "
            "WHERE cd_conta LIKE '6%' AND vl IS NOT NULL").fetchall():
        valores.setdefault((cd, cj, dr), []).append((conta, None, date(2000, 1, 1), vl))

    def muda(cd, cj, dr, trecho):
        f = rad.Formulario("f", None, {}, valores.get((cd, cj, dr), []))
        return rad.mascarar_valores_de_caixa(trecho, f) != trecho

    com_trecho = [e for e in evidencias if e.get("evidencia")]
    with open(manifesto, encoding="utf-8", newline="") as fh:
        linhas = [r for r in csv.DictReader(fh) if r["evidencia_trecho"]]
    return {
        "fonte_dos_valores": "ZIPs (versao maxima), contas 6.x",
        "evidencias_com_trecho": len(com_trecho),
        "evidencias_com_valores_de_caixa_na_fonte": sum(
            (e["cd_cvm"], e["conjunto"], e["dt_refer"]) in valores for e in com_trecho),
        "evidencias_que_a_mascara_mudaria": sum(
            muda(e["cd_cvm"], e["conjunto"], e["dt_refer"], e["evidencia"]["trecho"])
            for e in com_trecho),
        "linhas_do_manifesto": len(linhas),
        "linhas_que_a_mascara_mudaria": sum(
            muda(r["cd_cvm"], r["conjunto"], r["dt_refer"], r["evidencia_trecho"]) for r in linhas),
    }


def comparar_reproducao(governante: Path, manifesto: Path, reproducao: Path) -> dict:
    a = {e["id_doc"]: e for e in _jsonl(governante / "evidencias.jsonl")}
    b = {e["id_doc"]: e for e in _jsonl(reproducao / "evidencias.jsonl")}
    diferentes = sorted(i for i in a.keys() | b.keys()
                        if any(a.get(i, {}).get(c) != b.get(i, {}).get(c) for c in CAMPOS_COMPARADOS))
    ra = json.loads((governante / "resumo.json").read_text(encoding="utf-8"))
    rb = json.loads((reproducao / "resumo.json").read_text(encoding="utf-8"))
    ra["manifesto"].pop("sha256", None)
    rb["manifesto"].pop("sha256", None)
    return {
        "documentos": [len(a), len(b)],
        "documentos_diferentes": diferentes,
        "herdados_identicos": _sha(governante / "herdados.jsonl") == _sha(reproducao / "herdados.jsonl"),
        "manifesto_governante_sha256": _sha(manifesto),
        "manifesto_reproduzido_sha256": _sha(reproducao / "correcoes_escala.csv"),
        "manifesto_da_execucao_2_sha256_no_resumo": json.loads(
            (governante / "resumo.json").read_text(encoding="utf-8"))["manifesto"]["sha256"],
        "resumo_identico_fora_o_sha": ra == rb,
        "evidencias_reproduzidas_sha256": _sha(reproducao / "evidencias.jsonl"),
        # O código que RODOU a reexecução não é registrado por ela; o hash abaixo é
        # o do momento desta comparação. Mudanças entre as duas estão no relatório.
        "codigo_da_adjudicacao_sha256_no_momento_da_comparacao": _sha(
            RAIZ / "scripts" / "adjudicar_escala_rank03b.py"),
        "reproducao_mtime_evidencias": (reproducao / "evidencias.jsonl").stat().st_mtime,
    }


def executar(reproducao: Path | None) -> dict:
    con = duckdb.connect(":memory:")
    zips = fz.extrair(con)
    manifesto = adj.MANIFESTO_CORRECOES
    evidencias = _jsonl(adj.DESTINO / "evidencias.jsonl")
    with duckdb.connect(str(PASTA / "painel.duckdb"), read_only=True) as painel:
        b8 = continuidade_b8(painel, correcoes_com_um_bruto(manifesto))
    resultado = {
        "codigo_sha256": {f"scripts/{n}": _sha(RAIZ / "scripts" / n) for n in (
            "verificacoes_revisao_final_rank03b.py", "adjudicar_escala_rank03b.py",
            "fonte_rad_cvm.py", "fonte_zip_cvm.py")},
        "zips_sha256": zips,
        "painel_sha256_do_manifesto": _sha(PASTA / "manifesto_painel.json"),
        "manifesto_de_correcoes_sha256": _sha(manifesto),
        "amostra_de_desenho": amostra_de_desenho(_jsonl(adj.EVIDENCIAS_DO_PILOTO)),
        "b8_correcoes_com_um_bruto": b8,
        "b8_resumo": dict(Counter(x["situacao"] for x in b8)),
        "mascara_o1_3": mascara_sobre_publicados(con, evidencias, manifesto),
        "reproducao_da_adjudicacao": (comparar_reproducao(adj.DESTINO, manifesto, reproducao)
                                      if reproducao else "não fornecida nesta execução"),
    }
    _sem_chave_proibida(resultado)
    destino = PASTA / "verificacoes_revisao_final.json"
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True,
                                  default=str), encoding="utf-8")
    return resultado


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reproducao", type=Path, default=None,
                        help="diretório de uma reexecução de adjudicar_escala_rank03b.executar")
    args = parser.parse_args(argv)
    r = executar(args.reproducao)
    print(json.dumps({k: r[k] for k in ("amostra_de_desenho", "b8_resumo", "mascara_o1_3")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
