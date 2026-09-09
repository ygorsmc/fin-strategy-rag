"""Preços de fechamento da B3 com disciplina *point-in-time* (etapa 19).

Existe para responder a **única** condição de reabertura de ML que o §3.8 deixou
aberta. Ele nomeia três destravadores — *"DFC, preços point-in-time, ou
documentos além dos 20"* — e dois já foram feitos (§3.13, §3.15). Preço é o
terceiro, e é a única família de dado do projeto que **ainda não foi medida e
reprovada**.

Três decisões de desenho que não são estilo, e cada uma fecha um jeito conhecido
de produzir número plausível e errado:

1. **Ticker resolve por CNPJ, nunca por nome (RN11).** A tabela
   `fca_cia_aberta_valor_mobiliario` da CVM é a fonte autoritativa: ela liga
   `Codigo_Negociacao` ao CNPJ da companhia, e o painel tem `cnpj` em 741/741.
   Casar "PANATLANTICA S.A." com "PATI3" por semelhança de nome é exatamente o
   que a RN11 existe para impedir.
2. **A janela de validade do ticker é respeitada.** O mesmo código pode ter sido
   de outra companhia antes, e uma companhia pode ter deixado de negociar.
   `Data_Inicio_Negociacao`/`Data_Fim_Negociacao` delimitam cada par, e preço
   fora da janela **não entra**.
3. **Só lote padrão (`tpmerc='010'`).** O COTAHIST mistura opções e termo no
   mesmo arquivo — em 2025 são 335.874 linhas de lote padrão contra 2,6 milhões
   de opções. Somar tudo daria "preço" que não é preço de ação.

**O que este módulo NÃO faz:** não escolhe preço por proximidade de calendário
contábil. Quem consome pede o preço do primeiro pregão **em ou depois** da data
em que o dado passou a existir (`documentos.dt_receb`), que é a única definição
que não enxerga o formulário antes de ele existir — o §3.13 mediu que 41% dos
documentos chegam mais de 45 dias depois do fim do exercício.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator, Sequence

#: Layout posicional do COTAHIST (série histórica da B3), registro tipo `01`.
#: Posições são 0-based e fechadas à esquerda, como o layout oficial define.
CAMPOS_COTAHIST: dict[str, tuple[int, int]] = {
    "tipo_registro": (0, 2),
    "data": (2, 10),
    "cod_bdi": (10, 12),
    "ticker": (12, 24),
    "tipo_mercado": (24, 27),
    "preco_ultimo": (108, 121),
    "quantidade": (152, 170),
    "volume": (170, 188),
}

#: Lote padrão. O arquivo traz opções (`070`/`080`) e termo no mesmo lugar.
TIPO_MERCADO_LOTE_PADRAO = "010"

#: Registro de cotação. `00` é cabeçalho e `99` é *trailer*.
TIPO_REGISTRO_COTACAO = "01"

#: Papéis que representam participação na companhia. Debênture e nota comercial
#: também aparecem em `fca_cia_aberta_valor_mobiliario` e não são ação.
VALORES_MOBILIARIOS_DE_ACAO: frozenset[str] = frozenset(
    {"Ações Ordinárias", "Ações Preferenciais", "Units"}
)

#: Ticker da B3: quatro letras e um ou dois dígitos (`PETR4`, `BPAC11`).
#:
#: A guarda existe por defeito medido na fonte autoritativa: o BTG declara
#: `Codigo_Negociacao = '000000'` em `fca_cia_aberta_valor_mobiliario` de **2023
#: a 2026** — o correto é `BPAC11`. Cravar o valor certo à mão seria a correção
#: silenciosa que o §3.3 proíbe; o que se faz é **rejeitar e reportar**, para que
#: a companhia apareça como lacuna declarada em vez de sumir do universo sem
#: ninguém notar. Fechar a lacuna exige correção com procedência, como
#: `corpus/cvm/correcoes_contabeis.csv` faz para o Santander.
TICKER_VALIDO = re.compile(r"^[A-Z]{4}\d{1,2}$")


class ErroPrecos(RuntimeError):
    """Falha que interrompe a carga em vez de gravar preço não confiável."""


@dataclass(frozen=True)
class ParTickerCompanhia:
    """Um ticker válido para uma companhia dentro de uma janela de datas."""

    cd_cvm: str
    ticker: str
    inicio: date | None
    fim: date | None

    def vale_em(self, quando: date) -> bool:
        """Ticker fora da própria janela de negociação não vale.

        Sem isso, um código reaproveitado por outra companhia depois do
        encerramento produziria série contínua e errada — o preço existe, é do
        emissor errado, e nada no dado denuncia.
        """
        if self.inicio is not None and quando < self.inicio:
            return False
        if self.fim is not None and quando > self.fim:
            return False
        return True


@dataclass(frozen=True)
class Cotacao:
    ticker: str
    data: date
    preco_fechamento: float
    volume_reais: float


@dataclass(frozen=True)
class MapaTickers:
    """Pares aceitos e o que foi rejeitado, com motivo.

    `descartados` não é diagnóstico opcional: é a diferença entre "esta
    companhia não tem ação registrada" e "o arquivo da CVM traz o código dela
    quebrado". As duas coisas produzem ausência de preço, e só a segunda é
    consertável.
    """

    pares: tuple[ParTickerCompanhia, ...]
    descartados: tuple[tuple[str, str, str], ...]


def apenas_digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def _data_cotahist(bruto: str) -> date:
    return date(int(bruto[0:4]), int(bruto[4:6]), int(bruto[6:8]))


def _data_iso_ou_nada(bruto: str | None) -> date | None:
    texto = (bruto or "").strip()
    if not texto:
        return None
    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        return None


def ler_pares_ticker(
    caminhos_fca: Path | Sequence[Path], cnpj_por_cd_cvm: dict[str, str]
) -> MapaTickers:
    """Liga ticker a `cd_cvm` pelo CNPJ, respeitando a janela de negociação.

    `cnpj_por_cd_cvm` vem do painel (`companhias`), não do nome no arquivo de
    preço: é o que mantém a resolução de entidade na chave de registro (RN11).

    Aceita vários anos de FCA porque o formulário é reapresentado: um par que
    aparece só em 2023 continua valendo para a série histórica. Pares idênticos
    entre anos são deduplicados.
    """
    if isinstance(caminhos_fca, Path):
        caminhos_fca = [caminhos_fca]
    por_cnpj: dict[str, str] = {}
    for cd_cvm, cnpj in cnpj_por_cd_cvm.items():
        chave = apenas_digitos(cnpj)
        if len(chave) == 14:
            por_cnpj[chave] = cd_cvm

    vistos: dict[tuple[str, str, date | None, date | None], ParTickerCompanhia] = {}
    descartados: dict[tuple[str, str, str], None] = {}
    for caminho in caminhos_fca:
        with open(caminho, encoding="latin-1", newline="") as arquivo:
            for linha in csv.DictReader(arquivo, delimiter=";"):
                if (linha.get("Valor_Mobiliario") or "").strip() not in (
                    VALORES_MOBILIARIOS_DE_ACAO
                ):
                    continue
                cd_cvm = por_cnpj.get(apenas_digitos(linha.get("CNPJ_Companhia")))
                if cd_cvm is None:
                    continue
                bruto = (linha.get("Codigo_Negociacao") or "").strip().upper()
                if not bruto:
                    descartados[(cd_cvm, "", "código ausente")] = None
                    continue
                if TICKER_VALIDO.fullmatch(bruto) is None:
                    descartados[(cd_cvm, bruto, "código fora do formato da B3")] = None
                    continue
                par = ParTickerCompanhia(
                    cd_cvm=cd_cvm,
                    ticker=bruto,
                    inicio=_data_iso_ou_nada(linha.get("Data_Inicio_Negociacao")),
                    fim=_data_iso_ou_nada(linha.get("Data_Fim_Negociacao")),
                )
                vistos[(par.cd_cvm, par.ticker, par.inicio, par.fim)] = par
    if not vistos:
        raise ErroPrecos(
            f"Nenhum par ticker–companhia saiu de {[str(c) for c in caminhos_fca]}. "
            "Sem mapa não há preço, e adivinhar por nome quebra a RN11."
        )
    return MapaTickers(
        pares=tuple(vistos.values()), descartados=tuple(descartados)
    )


def ler_cotahist(
    linhas: Iterable[str], tickers: frozenset[str] | None = None
) -> Iterator[Cotacao]:
    """Lê o COTAHIST posicional, só lote padrão e só os tickers pedidos.

    Gerador de propósito: o arquivo de um ano tem ~780 MB de texto e 3,2 milhões
    de linhas de cotação. Materializar tudo para descartar 90% é desperdício que
    aparece como lentidão inexplicável na carga.
    """
    for linha in linhas:
        if linha[0:2] != TIPO_REGISTRO_COTACAO:
            continue
        if linha[24:27] != TIPO_MERCADO_LOTE_PADRAO:
            continue
        ticker = linha[12:24].strip().upper()
        if tickers is not None and ticker not in tickers:
            continue
        # O COTAHIST grava valor em centavos, sem separador decimal.
        yield Cotacao(
            ticker=ticker,
            data=_data_cotahist(linha[2:10]),
            preco_fechamento=int(linha[108:121]) / 100,
            volume_reais=int(linha[170:188]) / 100,
        )


def escolher_ticker_principal(
    pares: Sequence[ParTickerCompanhia], volume_por_ticker: dict[str, float]
) -> dict[str, ParTickerCompanhia]:
    """Uma companhia pode ter ON, PN e Unit; a série usa a MAIS LÍQUIDA.

    **Critério é volume financeiro, não número de pregões** — e a diferença foi
    medida, não suposta. Entre blue chips o número de pregões **empata em
    perfeição**: BBDC3, BBDC4, ITUB3, ITUB4 e BPAC11 negociaram todos os 250
    pregões de 2025, então "dias com negócio" não discrimina e o desempate
    alfabético escolhia a série ERRADA (BBDC3 no lugar de BBDC4, ITUB3 no lugar
    de ITUB4). Em volume a separação é limpa: ITUB4 movimentou R$ 202 bi contra
    R$ 5,6 bi de ITUB3, e BBDC4 R$ 129 bi contra R$ 25 bi de BBDC3.

    Empate real desempata pelo ticker, para que a escolha seja determinística
    entre execuções — carga que muda de série sozinha entre duas rodadas torna
    qualquer backtest irreprodutível.
    """
    melhor: dict[str, ParTickerCompanhia] = {}
    for par in sorted(pares, key=lambda p: p.ticker):
        volume = volume_por_ticker.get(par.ticker, 0.0)
        if volume <= 0:
            continue
        atual = melhor.get(par.cd_cvm)
        if atual is None or volume > volume_por_ticker.get(atual.ticker, 0.0):
            melhor[par.cd_cvm] = par
    return melhor
