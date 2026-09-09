"""Contrato do carregador de preços da B3 (etapa 19).

Cada caso aqui corresponde a um jeito conhecido de produzir preço plausível e
errado — a classe de falha que o projeto inteiro existe para combater.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.precos import (
    Cotacao,
    ErroPrecos,
    ParTickerCompanhia,
    apenas_digitos,
    escolher_ticker_principal,
    ler_cotahist,
    ler_pares_ticker,
)


def _linha_cotahist(
    ticker: str,
    data: str = "20250102",
    tipo_mercado: str = "010",
    preco_centavos: int = 1234,
    volume_centavos: int = 500000,
    tipo_registro: str = "01",
) -> str:
    """Monta uma linha no layout posicional oficial, campo a campo."""
    linha = list(" " * 245)

    def por(inicio: int, fim: int, valor: str, zeros: bool = False) -> None:
        largura = fim - inicio
        texto = valor.rjust(largura, "0") if zeros else valor.ljust(largura)
        linha[inicio:fim] = list(texto[:largura])

    por(0, 2, tipo_registro)
    por(2, 10, data)
    por(10, 12, "02")
    por(12, 24, ticker)
    por(24, 27, tipo_mercado)
    por(108, 121, str(preco_centavos), zeros=True)
    por(152, 170, "1000", zeros=True)
    por(170, 188, str(volume_centavos), zeros=True)
    return "".join(linha)


class TestLerCotahist:
    def test_le_preco_em_centavos_como_reais(self):
        (cot,) = list(ler_cotahist([_linha_cotahist("PETR4", preco_centavos=3871)]))
        assert cot.ticker == "PETR4"
        assert cot.preco_fechamento == pytest.approx(38.71)
        assert cot.data == date(2025, 1, 2)

    def test_descarta_opcao_e_termo(self):
        """Em 2025 são 2,6 M de linhas de opção contra 335 mil de lote padrão.

        Somar tudo daria "preço" que não é preço de ação.
        """
        linhas = [
            _linha_cotahist("PETR4", tipo_mercado="010"),
            _linha_cotahist("PETRA10", tipo_mercado="070"),
            _linha_cotahist("PETRB10", tipo_mercado="080"),
            _linha_cotahist("PETR4T", tipo_mercado="030"),
        ]
        assert [c.ticker for c in ler_cotahist(linhas)] == ["PETR4"]

    def test_descarta_cabecalho_e_trailer(self):
        linhas = [
            _linha_cotahist("XXXX", tipo_registro="00"),
            _linha_cotahist("PETR4"),
            _linha_cotahist("YYYY", tipo_registro="99"),
        ]
        assert [c.ticker for c in ler_cotahist(linhas)] == ["PETR4"]

    def test_filtra_pelos_tickers_pedidos(self):
        linhas = [_linha_cotahist("PETR4"), _linha_cotahist("VALE3")]
        lidas = list(ler_cotahist(linhas, tickers=frozenset({"VALE3"})))
        assert [c.ticker for c in lidas] == ["VALE3"]

    def test_e_gerador_e_nao_materializa_o_arquivo(self):
        """780 MB por ano: materializar para descartar 90% é lentidão gratuita."""
        import types

        assert isinstance(ler_cotahist([]), types.GeneratorType)


class TestJanelaDeNegociacao:
    def test_preco_antes_do_inicio_nao_vale(self):
        par = ParTickerCompanhia("000094", "PATI3", date(2020, 1, 1), None)
        assert not par.vale_em(date(2019, 12, 31))
        assert par.vale_em(date(2020, 1, 1))

    def test_preco_depois_do_fim_nao_vale(self):
        """Código reaproveitado por outra companhia daria série contínua e errada.

        O preço existe, é do emissor errado, e nada no dado denuncia.
        """
        par = ParTickerCompanhia("000094", "PATI3", None, date(2022, 6, 30))
        assert par.vale_em(date(2022, 6, 30))
        assert not par.vale_em(date(2022, 7, 1))

    def test_janela_aberta_dos_dois_lados_sempre_vale(self):
        par = ParTickerCompanhia("000094", "PATI3", None, None)
        assert par.vale_em(date(1998, 5, 4))
        assert par.vale_em(date(2026, 9, 8))


class TestLerParesTicker:
    def _csv(self, tmp_path: Path, linhas: list[str]) -> Path:
        cabecalho = (
            "CNPJ_Companhia;Valor_Mobiliario;Codigo_Negociacao;"
            "Data_Inicio_Negociacao;Data_Fim_Negociacao"
        )
        caminho = tmp_path / "fca.csv"
        caminho.write_text(
            "\n".join([cabecalho, *linhas]) + "\n", encoding="latin-1"
        )
        return caminho

    def test_resolve_por_cnpj_e_nao_por_nome(self):
        """RN11: nome não é chave. O CNPJ é identificador de registro."""
        assert apenas_digitos("92.693.019/0001-89") == "92693019000189"

    def test_liga_ticker_ao_cd_cvm_pelo_cnpj(self, tmp_path):
        caminho = self._csv(
            tmp_path,
            ["60.746.948/0001-12;Ações Preferenciais;BBDC4;1998-01-02;"],
        )
        mapa = ler_pares_ticker(caminho, {"000906": "60.746.948/0001-12"})
        assert len(mapa.pares) == 1
        assert mapa.pares[0].cd_cvm == "000906"
        assert mapa.pares[0].ticker == "BBDC4"
        assert mapa.pares[0].inicio == date(1998, 1, 2)
        assert mapa.pares[0].fim is None

    def test_debenture_e_nota_comercial_nao_sao_acao(self, tmp_path):
        caminho = self._csv(
            tmp_path,
            [
                "60.746.948/0001-12;Debêntures;BBDCA1;;",
                "60.746.948/0001-12;Nota Comercial;BBDCN1;;",
                "60.746.948/0001-12;Ações Ordinárias;BBDC3;;",
            ],
        )
        mapa = ler_pares_ticker(caminho, {"000906": "60.746.948/0001-12"})
        assert [p.ticker for p in mapa.pares] == ["BBDC3"]

    def test_units_contam_como_acao(self, tmp_path):
        """SANB11 e BPAC11 são Units; excluí-las perderia dois dos cinco bancos."""
        caminho = self._csv(
            tmp_path, ["90.400.888/0001-42;Units;SANB11;;"]
        )
        mapa = ler_pares_ticker(caminho, {"020532": "90.400.888/0001-42"})
        assert [p.ticker for p in mapa.pares] == ["SANB11"]

    def test_cnpj_fora_do_painel_e_ignorado_sem_erro(self, tmp_path):
        caminho = self._csv(
            tmp_path,
            [
                "11.111.111/0001-11;Ações Ordinárias;AAAA3;;",
                "60.746.948/0001-12;Ações Ordinárias;BBDC3;;",
            ],
        )
        mapa = ler_pares_ticker(caminho, {"000906": "60.746.948/0001-12"})
        assert [p.ticker for p in mapa.pares] == ["BBDC3"]

    def test_mapa_vazio_falha_em_vez_de_devolver_nada(self, tmp_path):
        """Sem mapa não há preço — e seguir em silêncio viraria painel vazio."""
        caminho = self._csv(tmp_path, ["11.111.111/0001-11;Debêntures;AAAA1;;"])
        with pytest.raises(ErroPrecos, match="RN11"):
            ler_pares_ticker(caminho, {"000906": "60.746.948/0001-12"})

    def test_codigo_quebrado_e_rejeitado_e_REPORTADO(self, tmp_path):
        """Caso real: o BTG declara `000000` como ticker de 2023 a 2026.

        O correto é `BPAC11`. Cravar o valor certo à mão seria a correção
        silenciosa que o §3.3 proíbe — o que se faz é rejeitar e **reportar**,
        para a companhia aparecer como lacuna declarada em vez de sumir do
        universo sem ninguém notar.
        """
        caminho = self._csv(tmp_path, ["30.306.294/0001-45;Units;000000;;"])
        with pytest.raises(ErroPrecos):
            ler_pares_ticker(caminho, {"022616": "30.306.294/0001-45"})

    def test_codigo_quebrado_nao_contamina_os_validos(self, tmp_path):
        caminho = self._csv(
            tmp_path,
            [
                "30.306.294/0001-45;Units;000000;;",
                "60.746.948/0001-12;Ações Preferenciais;BBDC4;;",
            ],
        )
        mapa = ler_pares_ticker(
            caminho,
            {"022616": "30.306.294/0001-45", "000906": "60.746.948/0001-12"},
        )
        assert [p.ticker for p in mapa.pares] == ["BBDC4"]
        assert ("022616", "000000", "código fora do formato da B3") in (
            mapa.descartados
        )

    def test_varios_anos_de_fca_deduplicam(self, tmp_path):
        """O FCA é reapresentado; par repetido entre anos não vira dois."""
        a = self._csv(tmp_path, ["60.746.948/0001-12;Ações Preferenciais;BBDC4;;"])
        b = tmp_path / "fca_b.csv"
        b.write_text(a.read_text(encoding="latin-1"), encoding="latin-1")
        mapa = ler_pares_ticker([a, b], {"000906": "60.746.948/0001-12"})
        assert len(mapa.pares) == 1


class TestTickerPrincipal:
    def test_escolhe_a_serie_de_maior_volume(self):
        """ON, PN e Unit da mesma companhia: a série usa a de maior volume."""
        pares = [
            ParTickerCompanhia("000906", "BBDC3", None, None),
            ParTickerCompanhia("000906", "BBDC4", None, None),
        ]
        escolha = escolher_ticker_principal(
            pares, {"BBDC3": 25.5e9, "BBDC4": 129.4e9}
        )
        assert escolha["000906"].ticker == "BBDC4"

    def test_volume_e_nao_numero_de_pregoes(self):
        """Contraprova do defeito real: entre blue chips os pregões EMPATAM.

        BBDC3, BBDC4, ITUB3, ITUB4 e BPAC11 negociaram todos os 250 pregões de
        2025. Com "dias" o desempate alfabético escolhia ITUB3 no lugar de
        ITUB4, cuja liquidez é 36× maior.
        """
        pares = [
            ParTickerCompanhia("019348", "ITUB3", None, None),
            ParTickerCompanhia("019348", "ITUB4", None, None),
        ]
        # Volumes reais de 2025, em reais.
        escolha = escolher_ticker_principal(
            pares, {"ITUB3": 5.6e9, "ITUB4": 202.0e9}
        )
        assert escolha["019348"].ticker == "ITUB4"

    def test_ticker_sem_negocio_nao_e_escolhido(self):
        pares = [
            ParTickerCompanhia("000906", "BBDC3", None, None),
            ParTickerCompanhia("000906", "BBDC4", None, None),
        ]
        escolha = escolher_ticker_principal(pares, {"BBDC4": 5.0})
        assert escolha["000906"].ticker == "BBDC4"

    def test_companhia_sem_nenhum_negocio_fica_de_fora(self):
        pares = [ParTickerCompanhia("000094", "PATI3", None, None)]
        assert escolher_ticker_principal(pares, {}) == {}

    def test_escolha_e_deterministica_no_empate(self):
        """Carga que muda de série sozinha torna backtest irreprodutível."""
        pares = [
            ParTickerCompanhia("000906", "BBDC4", None, None),
            ParTickerCompanhia("000906", "BBDC3", None, None),
        ]
        volume = {"BBDC3": 100.0, "BBDC4": 100.0}
        primeira = escolher_ticker_principal(pares, volume)["000906"].ticker
        for _ in range(5):
            assert (
                escolher_ticker_principal(list(reversed(pares)), volume)[
                    "000906"
                ].ticker
                == primeira
            )
