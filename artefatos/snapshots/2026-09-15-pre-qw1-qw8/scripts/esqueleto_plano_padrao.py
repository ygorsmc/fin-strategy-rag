"""Esqueleto do plano padrão de contas da CVM, para anotação humana.

**Isto NÃO classifica contas: propõe uma classificação com a evidência ao lado,
para que a revisão seja barata.** A coluna `classe_confirmada` nasce vazia e é
o único campo que decide — a proposta do script nunca é usada como verdade.

## Por que existe

Duas frentes travaram na mesma lacuna:

- o `mapa_contas` cobre **3,8%** das linhas do painel, o que o §3.8 já apontava
  como o gargalo de qualquer consulta semântica;
- a correção de escala de 2026-09-12 provou **quais documentos** estão com o
  rótulo errado, mas não pode reescalá-los sem saber **quais contas são
  monetárias** — reescalar `3.99` (Lucro por Ação) multiplicaria o LPA por mil.

A anotação do plano padrão resolve as duas.

## Cobertura medida, e uma correção ao §3.8

O §3.8 registra que *"a tabela de 208 contas do plano padrão destrava 85% das
linhas"*. **Não reproduz.** Medido no painel atual, por `(demonstrativo,
cd_conta)`:

| Contas | Cobertura |
|---|---|
| 100 | 40,6% |
| **208** | **77,6%** |
| 300 | 92,9% |
| 500 | 98,3% |

Os 85% ficam entre 208 e 300 contas. O script emite por padrão as **300**, que
é onde a curva achata.

## O sinal de monetariedade, e um sinal que foi testado e descartado

**Descartado:** a fração de linhas declaradas `UNIDADE` dentro de documentos em
`MIL`. Parecia o discriminante óbvio e **mede zero**: das 300 contas, as 300
saíram "monetárias", inclusive `3.99` (Lucro por Ação). A razão é que o LPA é
declarado com a **mesma** escala do documento — o `ESCALA_MOEDA` é metadado do
arquivamento e simplesmente não se aplica às linhas por ação. O rótulo não sabe
o que a conta significa.

**Adotado: a magnitude relativa.** Valor por ação e contagem de ações vivem em
outra ordem de grandeza. Medido:

| Conta | Exemplo | Mediana de `|VL_CONTA|` |
|---|---|---:|
| `3.01` | Receita | 608.572 |
| `3.11` | Lucro Líquido | 62.788 |
| **`3.99.01.01`** | **Lucro Básico por Ação** | **0,418** |

Para ficar livre do porte da companhia, o sinal é a razão entre a mediana da
conta e o **ativo total da mesma companhia no mesmo arquivamento**. Linha por
ação fica em torno de 1e-8 (porque o número de ações é da ordem de milhões);
linha monetária fica entre 1e-4 e 1.

**O sinal é auxílio de revisão, não veredito.** Ele ordena e destaca; quem
decide é a coluna `classe_confirmada`, que nasce vazia.

Os **127 documentos comprovadamente defeituosos** (inventário de escala) ficam
**fora** da medição: incluí-los faria o defeito ensinar a regra.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
PAINEL = RAIZ / "artefatos" / "cvm_treino.duckdb"
INVENTARIO = RAIZ / "artefatos" / "escala_cvm" / "inventario.jsonl"
DESTINO = RAIZ / "corpus" / "cvm" / "plano_padrao_contas.csv"

#: Onde a curva de cobertura achata (92,9%). Acima disso o ganho por conta
#: anotada cai para menos de 0,05 ponto percentual.
CONTAS_NO_ESQUELETO = 300
#: Razão entre a mediana da conta e o ativo total da companhia. Abaixo disto a
#: linha não é montante: é valor por ação ou contagem. O piso vem da ordem de
#: grandeza do número de ações (milhões), não de ajuste ao resultado.
TETO_NAO_MONETARIA = 1e-6
#: Acima disto é montante com folga de duas ordens de grandeza.
PISO_MONETARIA = 1e-4


def documentos_defeituosos() -> set[tuple[str, str, int]]:
    """Os 127 do inventário de escala — excluídos para não ensinarem a regra."""
    if not INVENTARIO.is_file():
        return set()
    por_documento: dict[tuple[str, str, int], set[str]] = {}
    for linha in INVENTARIO.open(encoding="utf-8"):
        caso = json.loads(linha)
        if caso["veredito"] != "ADJUDICAVEL_PELA_DFP":
            continue
        for d in caso["declaracoes"]:
            if d["escala"] != caso["escala_correta"]:
                chave = (caso["cd_cvm"], d["dt_refer"], d["versao"])
                por_documento.setdefault(chave, set()).add(caso["escala_correta"])
    return {k for k, v in por_documento.items() if len(v) == 1}


def levantar(con: duckdb.DuckDBPyConnection, defeituosos) -> list[dict]:
    filtro = " AND ".join(
        f"NOT (cd_cvm = '{cd}' AND dt_refer = DATE '{refer}' "
        f"AND versao_documento = {versao})"
        for cd, refer, versao in sorted(defeituosos)
    ) or "TRUE"
    return con.execute(
        f"""
        WITH limpo AS (
            SELECT * FROM fatos_contabeis
            WHERE origem = 'arquivado' AND ({filtro})
        ),
        escala_do_documento AS (
            -- Escala PREDOMINANTE do documento: a que mais linhas carregam.
            SELECT cd_cvm, dt_refer, versao_documento, escala AS escala_doc
            FROM (
                SELECT cd_cvm, dt_refer, versao_documento, escala, count(*) n,
                       row_number() OVER (
                           PARTITION BY cd_cvm, dt_refer, versao_documento
                           ORDER BY count(*) DESC, escala
                       ) AS posicao
                FROM limpo GROUP BY 1, 2, 3, 4
            ) WHERE posicao = 1
        ),
        marcado AS (
            SELECT l.*, d.escala_doc
            FROM limpo AS l
            JOIN escala_do_documento AS d
              ON d.cd_cvm = l.cd_cvm AND d.dt_refer = l.dt_refer
             AND d.versao_documento = l.versao_documento
        ),
        ativo_do_documento AS (
            SELECT cd_cvm, dt_refer, versao_documento,
                   max(abs(valor_reais)) AS ativo
            FROM limpo WHERE demonstrativo = 'BPA' AND cd_conta = '1'
            GROUP BY 1, 2, 3
        ),
        relativo AS (
            -- `valor_reais` dos DOIS lados. Dividir `vl_conta` bruto pelo
            -- ativo já escalado erra por mil — e o delator é o próprio Ativo
            -- Total, que tem de sair 1,0 e saía 1e-3.
            SELECT m.demonstrativo, m.cd_conta,
                   abs(m.valor_reais) / nullif(a.ativo, 0) AS razao
            FROM marcado AS m
            JOIN ativo_do_documento AS a
              ON a.cd_cvm = m.cd_cvm AND a.dt_refer = m.dt_refer
             AND a.versao_documento = m.versao_documento
            WHERE m.vl_conta <> 0 AND m.escala_doc = 'MIL'
        ),
        magnitude AS (
            SELECT demonstrativo, cd_conta,
                   median(razao) AS razao_mediana, count(*) AS n_razao
            FROM relativo WHERE razao IS NOT NULL GROUP BY 1, 2
        ),
        por_conta AS (
            SELECT m.demonstrativo, m.cd_conta,
                   count(*) AS linhas,
                   count(DISTINCT m.cd_cvm) AS companhias,
                   min(m.ds_conta) AS ds_conta_exemplo,
                   round(median(abs(m.vl_conta)), 4) AS mediana_bruta,
                   any_value(g.razao_mediana) AS razao_mediana,
                   any_value(g.n_razao) AS n_razao
            FROM marcado AS m
            LEFT JOIN magnitude AS g
              ON g.demonstrativo = m.demonstrativo AND g.cd_conta = m.cd_conta
            GROUP BY 1, 2
        )
        SELECT *, sum(linhas) OVER () AS total_de_linhas
        FROM por_conta ORDER BY linhas DESC, demonstrativo, cd_conta
        """
    ).df().to_dict("records")


def montar(contas: list[dict], quantas: int) -> list[dict]:
    total = contas[0]["total_de_linhas"] if contas else 0
    acumulado = 0
    saida: list[dict] = []
    for conta in contas[:quantas]:
        acumulado += conta["linhas"]
        razao = conta["razao_mediana"]
        if razao is None or not conta["n_razao"]:
            proposta = "INDEFINIDA"
            evidencia = "sem ativo total no mesmo arquivamento para comparar"
        elif razao < TETO_NAO_MONETARIA:
            proposta = "nao_monetaria"
            evidencia = (
                f"mediana {razao:.2e} do ativo total (bruta {conta['mediana_bruta']}): "
                "ordem de grandeza de valor por ação ou contagem, não de montante"
            )
        elif razao >= PISO_MONETARIA:
            proposta = "monetaria"
            evidencia = (
                f"mediana {razao:.2e} do ativo total (bruta {conta['mediana_bruta']}): "
                "ordem de grandeza de montante"
            )
        else:
            proposta = "INDEFINIDA"
            evidencia = (
                f"mediana {razao:.2e} do ativo total (bruta {conta['mediana_bruta']}) "
                "— zona cinzenta entre montante e valor por ação, exige decisão humana"
            )
        saida.append({
            "demonstrativo": conta["demonstrativo"],
            "cd_conta": conta["cd_conta"],
            "ds_conta_exemplo": conta["ds_conta_exemplo"],
            "linhas": conta["linhas"],
            "companhias": conta["companhias"],
            "cobertura_acumulada_pct": round(100.0 * acumulado / total, 3) if total else 0,
            "mediana_bruta": conta["mediana_bruta"],
            "razao_sobre_ativo_total": (
                f"{razao:.3e}" if razao is not None else ""
            ),
            "classe_proposta": proposta,
            # **Único campo que decide.** Nasce vazio de propósito: a proposta
            # do script é evidência para a revisão, nunca verdade.
            "classe_confirmada": "",
            "evidencia": evidencia,
        })
    return saida


def executar(quantas: int = CONTAS_NO_ESQUELETO) -> list[dict]:
    con = duckdb.connect(str(PAINEL), read_only=True)
    try:
        return montar(levantar(con, documentos_defeituosos()), quantas)
    finally:
        con.close()


def principal() -> int:
    linhas = executar()
    if DESTINO.exists():
        print(f"{DESTINO} já existe — não sobrescrevo anotação humana.")
        return 1
    with DESTINO.open("w", encoding="utf-8", newline="") as saida:
        escritor = csv.DictWriter(saida, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)
    from collections import Counter
    contagem = Counter(l["classe_proposta"] for l in linhas)
    print(f"{len(linhas)} contas no esqueleto → {DESTINO}")
    print(f"  cobertura acumulada: {linhas[-1]['cobertura_acumulada_pct']}%")
    for classe, n in sorted(contagem.items()):
        print(f"  proposta {classe:16s} {n}")
    print("  `classe_confirmada` está VAZIA: é o único campo que decide.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
