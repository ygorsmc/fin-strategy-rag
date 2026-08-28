"""Extrai os CSVs dos ZIPs da CVM e constrói o painel DuckDB.

Este passo existia só como comando avulso; virou script porque a etapa 10
passou a precisar de **dois painéis distintos**, e reproduzir isso na mão é
como se perde a procedência:

- **painel consultável** (`artefatos/cvm.duckdb`) — casado com o corpus
  (`CVM_ANO_INICIAL=2025`), é o que a camada interativa consulta. A decisão de
  mantê-lo estreito continua valendo.
- **painel de treino** (`artefatos/cvm_treino.duckdb`) — janela larga, só para
  o modelo supervisionado offline (RN07). Sem ele, o split temporal tem uma
  única partição e nenhuma comparação é resolvível.

Uso:
    python -m scripts.construir_painel_cvm --anos 2011-2026 \\
        --destino artefatos/cvm_treino.duckdb
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.config import DIR_CVM_BRUTO  # noqa: E402
from src.dados_estruturados import (  # noqa: E402
    FonteCabecalho,
    FonteCVM,
    carregar_painel,
)

#: Só os demonstrativos que a carga consome; o ZIP traz muitos outros.
#:
#: `DFC_MD`/`DFC_MI` entraram em 2026-08-27. O fluxo de caixa sempre esteve nos
#: ZIPs já baixados — o painel é que não o lia, e sem ele não há conversão de
#: caixa, nem qualidade do lucro, nem FCF. Cobertura medida: 465 de 476
#: emissores (97,7%) no ITR de 2024.
DEMONSTRATIVOS = ("DRE", "BPA", "BPP", "DFC_MD", "DFC_MI")
CONJUNTOS = ("itr", "dfp")
DIR_EXTRACAO = RAIZ / "artefatos" / "cvm"


def _faixa_de_anos(texto: str) -> list[int]:
    """Aceita `2011-2026` ou `2011,2012,2013`."""
    if "-" in texto:
        inicio, fim = (int(p) for p in texto.split("-", 1))
        if inicio > fim:
            raise argparse.ArgumentTypeError(f"faixa invertida: {texto}")
        return list(range(inicio, fim + 1))
    return [int(p) for p in texto.split(",") if p.strip()]


#: Faixa C1: bytes que o ISO-8859-1 deixa **indefinidos** e o DuckDB recusa.
_FAIXA_C1 = range(0x80, 0xA0)


def _sanear_c1(caminho: Path) -> int:
    """Troca bytes C1 por `?`, devolvendo quantos foram trocados.

    Achado de 2026-08-23: `itr_cia_aberta_BPA_con_2020.csv` não é legível como
    latin-1 e **não** está em outra codificação — está com *mojibake* na
    origem. O trecho `CrÃƒÂ©ditos` é "Créditos" codificado em UTF-8 duas vezes,
    e o resíduo `0x83` cai na faixa que o latin-1 não define.

    A troca é segura para o que este painel usa: o estrago está em `DS_CONTA`,
    campo **descritivo**. `CD_CONTA`, `VL_CONTA`, datas e códigos são ASCII, e
    a resolução de conceito passa por `mapa_contas` (RN09), nunca pelo texto.
    Sanear aqui mantém a carga de produção intocada — ela continua exigindo
    latin-1 estrito, e é ela que constrói o painel consultável.
    """
    bruto = caminho.read_bytes()
    trocados = sum(1 for b in bruto if b in _FAIXA_C1)
    if not trocados:
        return 0
    caminho.write_bytes(
        bytes(0x3F if b in _FAIXA_C1 else b for b in bruto)
    )
    return trocados


def extrair(
    anos: list[int], destino: Path
) -> tuple[list[FonteCVM], list[FonteCabecalho]]:
    """Extrai os CSVs de fato e o CSV-cadastro de cada ZIP.

    Devolve dois grupos porque eles alimentam tabelas diferentes: os fatos vão
    para `fatos_contabeis`; o cadastro (`<conjunto>_cia_aberta_<ano>.csv`) vai
    para `documentos`, e é ele que carrega `DT_RECEB` — a data em que a CVM
    recebeu o formulário, sem a qual nenhum backtest é point-in-time.
    """
    destino.mkdir(parents=True, exist_ok=True)
    fontes: list[FonteCVM] = []
    cabecalhos: list[FonteCabecalho] = []
    ausentes: list[str] = []
    saneados: list[tuple[str, int]] = []
    for conjunto in CONJUNTOS:
        for ano in anos:
            zip_path = DIR_CVM_BRUTO / f"{conjunto}_cia_aberta_{ano}.zip"
            if not zip_path.is_file():
                ausentes.append(zip_path.name)
                continue
            with zipfile.ZipFile(zip_path) as arquivo:
                nomes = set(arquivo.namelist())
                for demonstrativo in DEMONSTRATIVOS:
                    alvo = (
                        f"{conjunto}_cia_aberta_{demonstrativo}_con_{ano}.csv"
                    )
                    if alvo not in nomes:
                        ausentes.append(f"{zip_path.name}:{alvo}")
                        continue
                    saida = destino / alvo
                    if not saida.is_file():
                        saida.write_bytes(arquivo.read(alvo))
                        trocados = _sanear_c1(saida)
                        if trocados:
                            saneados.append((alvo, trocados))
                    fontes.append(FonteCVM(saida, conjunto, demonstrativo))
                cadastro = f"{conjunto}_cia_aberta_{ano}.csv"
                if cadastro in nomes:
                    saida = destino / cadastro
                    if not saida.is_file():
                        saida.write_bytes(arquivo.read(cadastro))
                        _sanear_c1(saida)
                    cabecalhos.append(FonteCabecalho(saida, conjunto))
                else:
                    ausentes.append(f"{zip_path.name}:{cadastro}")
    if ausentes:
        print(f"aviso: {len(ausentes)} arquivos ausentes (ex.: {ausentes[:3]})")
    for nome, trocados in saneados:
        print(f"aviso: {nome} tinha {trocados} bytes fora do latin-1 (mojibake "
              "na origem, em campo descritivo) — trocados por '?'")
    return fontes, cabecalhos


def principal() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--anos", type=_faixa_de_anos, required=True)
    analisador.add_argument("--destino", type=Path, required=True)
    analisador.add_argument(
        "--dir-extracao", type=Path, default=DIR_EXTRACAO,
        help="onde os CSVs são descompactados (regenerável, fora do Git)",
    )
    argumentos = analisador.parse_args()

    fontes, cabecalhos = extrair(argumentos.anos, argumentos.dir_extracao)
    if not fontes:
        print("nenhuma fonte encontrada; rode scripts/baixar_cvm.py antes")
        return 1
    print(
        f"{len(fontes)} fontes CSV e {len(cabecalhos)} cadastros; "
        f"construindo {argumentos.destino}..."
    )

    relatorio = carregar_painel(
        fontes, argumentos.destino, cabecalhos=cabecalhos
    )
    print(relatorio.como_texto())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(principal())
