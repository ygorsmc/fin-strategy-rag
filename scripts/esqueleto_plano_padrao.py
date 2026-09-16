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

Os documentos com **declaração adjudicada** pelo inventário de escala ficam
**fora** da medição: incluí-los faria o defeito ensinar a regra.

## Correção de 2026-09-15 (conferência das quatro ondas, QW1/QW8)

- **Eram "127 documentos comprovadamente defeituosos"; não eram.** 14 só
  tinham zero como prova e 2 foram condenados por extrapolação. A exclusão
  passou a ler o estado de cada declaração no inventário v2 e a identificar o
  documento por `(cd_cvm, conjunto, dt_refer, versao)` — o `conjunto` faltava
  (efeito medido nulo: zero colisões ITR×DFP).
- **Inventário ausente ou de esquema anterior FALHA**, em vez de devolver
  conjunto vazio e medir sobre tudo prometendo excluir.
- **Denominador da cobertura:** linhas com `origem = 'arquivado'` fora dos
  documentos excluídos. Medido na regeneração de 15/09 (111 documentos
  excluídos), as mesmas 300 chaves cobrem:

  | Universo | Linhas cobertas / total | Cobertura |
  |---|---:|---:|
  | **Do gerador** — arquivados fora dos excluídos | 5.981.271 / 6.438.964 | **92,892%** |
  | Todos os arquivados | 6.008.928 / 6.468.614 | 92,894% |
  | Painel inteiro, com derivados | 6.680.366 / 7.177.705 | 93,071% |

  A tabela de 100/208/300/500 contas acima é do universo do gerador (40,611%,
  77,614%, 92,892%, 98,277%). Não é cobertura de conceitos: agrupar por `(demonstrativo, cd_conta)` com
  `min(ds_conta)` não resolve semântica por plano (DRE/3.04 mostra "Despesas
  Administrativas", 218 ocorrências, onde "Despesas/Receitas Operacionais"
  aparece 33.598 vezes). **A chave deste esqueleto não é semântica entre
  planos (RN09):** o contrato de correção não pode juntar por código sozinho.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb

from scripts.inventariar_escala_cvm import (
    ADJUDICA,
    ESTADOS_DE_DECLARACAO,
    VERSAO_DO_ESQUEMA,
)

RAIZ = Path(__file__).resolve().parents[1]
PAINEL = RAIZ / "artefatos" / "cvm_treino.duckdb"
INVENTARIO = RAIZ / "artefatos" / "escala_cvm" / "inventario.jsonl"
RESUMO_DO_INVENTARIO = RAIZ / "artefatos" / "escala_cvm" / "resumo.json"
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


class InventarioAusente(FileNotFoundError):
    """Sem inventário não há o que excluir — e medir sobre tudo prometendo
    excluir é o defeito QW8. Estado distinto de inventário válido e vazio."""


class InventarioIncompativel(ValueError):
    """Inventário de esquema anterior. Lê-lo com a regra antiga condenaria
    declarações por extrapolação (QW2). Esquema não reconhecido é *não sei*."""


def documentos_defeituosos(
    inventario: Path | None = None, resumo: Path | None = None
) -> set[tuple[str, str, str, int]]:
    """Documentos com ao menos uma declaração ADJUDICADA pelo inventário v2.

    Identidade `(cd_cvm, conjunto, dt_refer, versao)`. Só o estado
    `ADJUDICA` de cada declaração conta: zero, montante equivalente em reais,
    coincidência só entre ITRs e escala divergente com outro valor **não**
    condenam documento.
    """
    inventario = inventario or INVENTARIO
    resumo = resumo or RESUMO_DO_INVENTARIO
    for caminho in (inventario, resumo):
        if not caminho.is_file():
            raise InventarioAusente(
                f"{caminho} não existe: rode `python -m scripts.inventariar_escala_cvm` "
                "— sem ele a exclusão prometida não acontece"
            )
    versao = json.loads(resumo.read_text(encoding="utf-8")).get("versao_do_esquema")
    if versao != VERSAO_DO_ESQUEMA:
        raise InventarioIncompativel(
            f"inventário com versão de esquema {versao!r}; este consumidor lê "
            f"só a {VERSAO_DO_ESQUEMA} (adjudicação por declaração)"
        )
    documentos: set[tuple[str, str, str, int]] = set()
    with inventario.open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            caso = json.loads(linha)
            for d in caso["declaracoes"]:
                if "adjudicacao" not in d:
                    raise InventarioIncompativel(
                        "declaração sem o campo `adjudicacao`: o resumo diz v2, "
                        "mas o inventário é de outra versão"
                    )
                # **Correção CQW-01 (contrato E2).** Conferir só a EXISTÊNCIA
                # da chave fazia estado inválido — `None`, texto desconhecido,
                # tipo errado, o estado adjudicante com um espaço a mais —
                # significar "não adjudica", devolvendo `set()` em silêncio. Se
                # fossem os únicos registros do documento, ele voltava ao
                # universo do gerador. O vocabulário de E1.2 existia e não
                # participava da decisão: §4.4 regra 7, terceira reincidência.
                # Não normalizar (E2.3): espaço sobrando é inventário
                # corrompido, não estado mal digitado.
                if d["adjudicacao"] not in ESTADOS_DE_DECLARACAO:
                    raise InventarioIncompativel(
                        f"declaração com `adjudicacao` fora do vocabulário "
                        f"fechado: {d['adjudicacao']!r}. Os estados válidos são "
                        f"{ESTADOS_DE_DECLARACAO}"
                    )
                if d["adjudicacao"] == ADJUDICA:
                    documentos.add(
                        (caso["cd_cvm"], d["conjunto"], d["dt_refer"], d["versao"])
                    )
    return documentos


def levantar(con: duckdb.DuckDBPyConnection, defeituosos) -> list[dict]:
    filtro = " AND ".join(
        f"NOT (cd_cvm = '{cd}' AND conjunto = '{conjunto}' "
        f"AND dt_refer = DATE '{refer}' AND versao_documento = {versao})"
        for cd, conjunto, refer, versao in sorted(defeituosos)
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
    # Recusa ANTES de calcular: não há por que ler painel e inventário para
    # depois não gravar — e o teste da recusa deixa de depender deles.
    if DESTINO.exists():
        print(f"{DESTINO} já existe — não sobrescrevo anotação humana.")
        return 1
    linhas = executar()
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
