"""Extração congelada das contas do Rank 3-B a partir dos ZIPs anuais da CVM.

Contrato: `resultados/contratos_lote_b_rank03b_2026-09-16.md`. Serve ao piloto
do lote B e à construção do painel de pesquisa do lote C.

**Por que ler os ZIPs, e não o painel compartilhado.** O painel descarta o
comparativo `PENÚLTIMO` (a segunda declaração do mesmo período, que permite
conferir valor e escala) e carrega a derivação com os defeitos N2/N3. Ler a
fonte primária dá ao painel de pesquisa uma origem independente desses
defeitos — e permite **conferir** o painel compartilhado em vez de herdá-lo.

**Fonte congelada:** cada ZIP é conferido contra o SHA-256 de
`corpus/cvm/manifesto_cvm.csv` antes de ser aberto. ZIP diferente do pinado
levanta erro; a CVM republica esses arquivos, e ler uma versão nova em silêncio
mudaria o painel sem declaração.

Só o **consolidado** (`_con_`), a mesma regra da carga compartilhada — é o
universo sobre o qual o pré-registro de 11/09 foi escrito.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from pathlib import Path

import duckdb
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DIR_ZIPS = RAIZ / "corpus" / "cvm"
MANIFESTO_ZIPS = DIR_ZIPS / "manifesto_cvm.csv"

#: Contas do candidato e contas de identidade contábil, por demonstrativo.
#: Sem `ds_conta` como chave: `6.01`, `1` e `2` são contas FIXAS do plano
#: (`ST_CONTA_FIXA = 'S'` em todas as linhas do universo, medido em 16/09).
CONTAS_POR_DEMONSTRATIVO = {
    "BPA": ("1", "1.01.01"),
    "BPP": ("2",),
    "DFC_MD": ("6.01", "6.02", "6.03", "6.04", "6.05", "6.05.01", "6.05.02"),
    "DFC_MI": ("6.01", "6.02", "6.03", "6.04", "6.05", "6.05.01", "6.05.02"),
}

COLUNAS_DECLARACOES = [
    "arquivo", "conjunto", "demonstrativo", "cd_cvm", "dt_refer", "versao",
    "ordem", "dt_ini", "dt_fim", "cd_conta", "ds_conta", "escala", "moeda",
    "vl", "conta_fixa",
]
COLUNAS_CADASTRO = [
    "arquivo", "conjunto", "cd_cvm", "dt_refer", "versao", "id_doc",
    "dt_receb", "link_doc",
]


class FonteAlterada(Exception):
    """ZIP ausente ou diferente do pinado no manifesto."""


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def verificar_zips(diretorio: Path = DIR_ZIPS,
                   manifesto: Path = MANIFESTO_ZIPS) -> dict[str, str]:
    """`{arquivo: sha256}` dos ZIPs pinados, conferidos um a um."""
    with open(manifesto, encoding="utf-8", newline="") as fh:
        pinados = {r["arquivo"]: r["hash_sha256"] for r in csv.DictReader(fh)}
    if not pinados:
        raise FonteAlterada(f"{manifesto} não pina arquivo nenhum")
    for nome, esperado in pinados.items():
        caminho = diretorio / nome
        if not caminho.is_file():
            raise FonteAlterada(f"{nome} pinado no manifesto e ausente do disco")
        obtido = _sha256(caminho)
        if obtido != esperado:
            raise FonteAlterada(
                f"{nome}: SHA-256 {obtido[:12]}… difere do pinado {esperado[:12]}… — "
                "a CVM republica estes arquivos; ler outra versão em silêncio "
                "mudaria o painel sem declaração"
            )
    return dict(sorted(pinados.items()))


def _linhas(arq: zipfile.ZipFile, membro: str):
    with arq.open(membro) as fh:
        yield from csv.DictReader(
            io.TextIOWrapper(fh, encoding="latin-1", newline=""), delimiter=";"
        )


def _valor(texto: str | None) -> float | None:
    """Célula vazia é NULO, não zero e não erro.

    Quebrar aqui impediria o G0.4 de contar o nulo; virar zero o esconderia.
    """
    t = (texto or "").strip()
    return float(t) if t else None


def ler_zip(caminho: Path) -> tuple[list[tuple], list[tuple]]:
    """Declarações das contas-alvo e o cadastro de documentos de um ZIP."""
    conjunto, _, _, ano = caminho.stem.split("_")
    declaracoes, cadastro = [], []
    with zipfile.ZipFile(caminho) as arq:
        for demonstrativo, contas in CONTAS_POR_DEMONSTRATIVO.items():
            membro = f"{conjunto}_cia_aberta_{demonstrativo}_con_{ano}.csv"
            for r in _linhas(arq, membro):
                if r["CD_CONTA"] not in contas:
                    continue
                declaracoes.append((
                    caminho.name, conjunto, demonstrativo, r["CD_CVM"].zfill(6),
                    r["DT_REFER"], int(r["VERSAO"]), r["ORDEM_EXERC"],
                    r.get("DT_INI_EXERC") or None, r["DT_FIM_EXERC"],
                    r["CD_CONTA"], r["DS_CONTA"], r["ESCALA_MOEDA"], r["MOEDA"],
                    _valor(r["VL_CONTA"]), r.get("ST_CONTA_FIXA"),
                ))
        for r in _linhas(arq, f"{conjunto}_cia_aberta_{ano}.csv"):
            cadastro.append((
                caminho.name, conjunto, r["CD_CVM"].zfill(6), r["DT_REFER"],
                int(r["VERSAO"]), r["ID_DOC"], r["DT_RECEB"], r["LINK_DOC"],
            ))
    return declaracoes, cadastro


def extrair(con: duckdb.DuckDBPyConnection, diretorio: Path = DIR_ZIPS,
            manifesto: Path = MANIFESTO_ZIPS) -> dict[str, str]:
    """Cria `declaracoes` e `cadastro` em `con`, em ordem determinística.

    Devolve os hashes conferidos, para o manifesto de quem consome.
    """
    hashes = verificar_zips(diretorio, manifesto)
    todas_decl, todo_cad = [], []
    for nome in hashes:
        declaracoes, cadastro = ler_zip(diretorio / nome)
        todas_decl += declaracoes
        todo_cad += cadastro
    decl = pd.DataFrame(todas_decl, columns=COLUNAS_DECLARACOES)
    cad = pd.DataFrame(todo_cad, columns=COLUNAS_CADASTRO)
    con.register("_decl", decl)
    con.register("_cad", cad)
    con.execute(
        """
        CREATE OR REPLACE TABLE declaracoes AS
        SELECT arquivo, conjunto, demonstrativo, cd_cvm, CAST(dt_refer AS DATE) dt_refer,
               versao, ordem, CAST(dt_ini AS DATE) dt_ini, CAST(dt_fim AS DATE) dt_fim,
               cd_conta, ds_conta, escala, moeda, vl, conta_fixa
        FROM _decl
        ORDER BY cd_cvm, conjunto, dt_refer, versao, demonstrativo, cd_conta,
                 ordem, dt_ini NULLS FIRST, dt_fim
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE cadastro AS
        SELECT arquivo, conjunto, cd_cvm, CAST(dt_refer AS DATE) dt_refer, versao,
               id_doc, CAST(dt_receb AS DATE) dt_receb, link_doc
        FROM _cad
        ORDER BY cd_cvm, conjunto, dt_refer, versao, id_doc
        """
    )
    con.unregister("_decl")
    con.unregister("_cad")
    return hashes
