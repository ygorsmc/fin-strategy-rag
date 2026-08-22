"""Correções com procedência (gate G4, RN09).

Esta tabela é a peça com maior potencial de dano do painel: ela permite trocar
um número vindo do arquivo oficial da CVM. Sem guarda, vira porta dos fundos
para ajustar dado inconveniente — exatamente o oposto do que o G4 existe para
impedir. Os testes abaixo travam as quatro propriedades que a tornam defensável:

1. **Procedência é obrigatória e completa.** Nenhum campo vazio, evidência e
   motivo com substância, SHA-256 do documento que justifica.
2. **A correção é presa ao valor observado.** `valor_original_reais` tem de
   bater com o painel atual; se a CVM republicar, a correção para de valer e
   FALHA em vez de aplicar às cegas.
3. **A correção é visível, não silenciosa.** A visão marca `corrigido=true` e
   preserva `valor_reais_arquivo` — quem consulta vê os dois números.
4. **O CSV é a fonte de verdade**, versionado, revisável em `git diff`.
"""

from __future__ import annotations

import csv
from pathlib import Path

import duckdb
import pytest

from src.dados_estruturados import (
    CAMINHO_CORRECOES,
    CAMPOS_CORRECAO,
    ErroCorrecaoInvalida,
    aplicar_correcoes,
    carregar_correcoes,
    criar_esquema,
)


def _escrever(caminho: Path, linhas: list[dict]) -> Path:
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS_CORRECAO)
        escritor.writeheader()
        escritor.writerows(linhas)
    return caminho


def _linha_valida(**sobrescreve) -> dict:
    base = {
        "cd_cvm": "020532",
        "trimestre": "3T2025",
        "conceito": "lucro_liquido_controladores",
        "valor_original_reais": "1000000",
        "valor_corrigido_reais": "2000000",
        "fonte_documento": "santander_ifrs_3T2025",
        "fonte_pagina": "7",
        "fonte_sha256": "a" * 64,
        "evidencia": (
            "A soma das contas filhas nao fecha com a conta pai no arquivo da "
            "CVM, e a demonstracao em IFRS fecha exata."
        ),
        "motivo": (
            "Arquivo da CVM se contradiz internamente; hipoteses de erro de "
            "mapa e de retificadora foram descartadas com evidencia."
        ),
        "data_utc": "2026-08-21T00:00:00Z",
    }
    base.update({k: str(v) for k, v in sobrescreve.items()})
    return base


class TestProcedenciaObrigatoria:
    @pytest.mark.parametrize("campo", CAMPOS_CORRECAO)
    def test_campo_vazio_e_recusado(self, campo: str, tmp_path: Path):
        caminho = _escrever(
            tmp_path / "c.csv", [_linha_valida(**{campo: ""})]
        )
        with pytest.raises(ErroCorrecaoInvalida, match="procedência completa"):
            carregar_correcoes(caminho)

    def test_evidencia_rasa_e_recusada(self, tmp_path: Path):
        """"Erro na origem" não permite reconferir a correção depois."""
        caminho = _escrever(
            tmp_path / "c.csv", [_linha_valida(evidencia="erro na origem")]
        )
        with pytest.raises(ErroCorrecaoInvalida, match="evidencia|evidência"):
            carregar_correcoes(caminho)

    def test_motivo_raso_e_recusado(self, tmp_path: Path):
        caminho = _escrever(
            tmp_path / "c.csv", [_linha_valida(motivo="estava errado")]
        )
        with pytest.raises(ErroCorrecaoInvalida, match="motivo"):
            carregar_correcoes(caminho)

    def test_sha256_truncado_e_recusado(self, tmp_path: Path):
        caminho = _escrever(
            tmp_path / "c.csv", [_linha_valida(fonte_sha256="abc123")]
        )
        with pytest.raises(ErroCorrecaoInvalida, match="SHA-256"):
            carregar_correcoes(caminho)

    def test_correcao_que_nao_muda_nada_e_recusada(self, tmp_path: Path):
        caminho = _escrever(
            tmp_path / "c.csv",
            [_linha_valida(valor_original_reais=5, valor_corrigido_reais=5)],
        )
        with pytest.raises(ErroCorrecaoInvalida, match="não muda nada"):
            carregar_correcoes(caminho)

    def test_duplicata_e_recusada(self, tmp_path: Path):
        caminho = _escrever(
            tmp_path / "c.csv", [_linha_valida(), _linha_valida()]
        )
        with pytest.raises(ErroCorrecaoInvalida, match="duplicada"):
            carregar_correcoes(caminho)

    def test_coluna_a_mais_e_recusada(self, tmp_path: Path):
        """O contrato é exato: coluna nova sem revisão do carregador seria
        procedência que ninguém valida."""
        with open(tmp_path / "c.csv", "w", newline="", encoding="utf-8") as f:
            campos = list(CAMPOS_CORRECAO) + ["observacao"]
            escritor = csv.DictWriter(f, fieldnames=campos)
            escritor.writeheader()
            escritor.writerow({**_linha_valida(), "observacao": "x"})
        with pytest.raises(ErroCorrecaoInvalida, match="Colunas"):
            carregar_correcoes(tmp_path / "c.csv")


class TestCorrecaoPresaAoValorObservado:
    """A guarda que impede a porta dos fundos."""

    @pytest.fixture
    def painel(self) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect(":memory:")
        criar_esquema(con)
        con.execute(
            "INSERT INTO companhias VALUES "
            "('020532','x','BCO SANTANDER (BRASIL) S.A.','banco','SANB11',"
            "true,'cosif')"
        )
        con.execute(
            "INSERT INTO mapa_contas VALUES "
            "('cosif','lucro_liquido_controladores','3.09.01','x','x')"
        )
        con.execute(
            "INSERT INTO fatos_contabeis VALUES "
            "('020532','ITR','DRE','3T2025','trimestral','2025-09-30',"
            "'2025-07-01','2025-09-30','3.09.01','x','x',1000.0,'mil',"
            "1000000.0,1,'arquivado')"
        )
        return con

    def test_valor_original_divergente_falha(
        self, painel: duckdb.DuckDBPyConnection, tmp_path: Path
    ):
        caminho = _escrever(
            tmp_path / "c.csv", [_linha_valida(valor_original_reais=999)]
        )
        with pytest.raises(ErroCorrecaoInvalida, match="não bate com o painel"):
            aplicar_correcoes(painel, caminho)

    def test_valor_original_correto_aplica(
        self, painel: duckdb.DuckDBPyConnection, tmp_path: Path
    ):
        caminho = _escrever(tmp_path / "c.csv", [_linha_valida()])
        assert aplicar_correcoes(painel, caminho) == 1

    def test_celula_inexistente_falha(
        self, painel: duckdb.DuckDBPyConnection, tmp_path: Path
    ):
        caminho = _escrever(
            tmp_path / "c.csv", [_linha_valida(trimestre="1T2020")]
        )
        with pytest.raises(ErroCorrecaoInvalida, match="nenhuma linha"):
            aplicar_correcoes(painel, caminho)

    def test_visao_expoe_os_dois_numeros(
        self, painel: duckdb.DuckDBPyConnection, tmp_path: Path
    ):
        """Corrigir em silêncio é o que o G4 existe para impedir."""
        aplicar_correcoes(painel, _escrever(tmp_path / "c.csv", [_linha_valida()]))
        linha = painel.execute(
            "SELECT valor_reais, valor_reais_arquivo, corrigido, "
            "correcao_fonte FROM fatos_semanticos WHERE cd_cvm='020532'"
        ).fetchone()
        assert linha[0] == 2000000.0
        assert linha[1] == 1000000.0
        assert linha[2] is True
        assert linha[3] == "santander_ifrs_3T2025"

    def test_sem_correcao_a_visao_nao_marca_nada(
        self, painel: duckdb.DuckDBPyConnection
    ):
        linha = painel.execute(
            "SELECT valor_reais, valor_reais_arquivo, corrigido "
            "FROM fatos_semanticos WHERE cd_cvm='020532'"
        ).fetchone()
        assert linha[0] == linha[1] == 1000000.0
        assert linha[2] is False


class TestCorrecoesVersionadasDoProjeto:
    """O CSV real, não uma fixture — se ele quebrar, o painel quebra."""

    def test_arquivo_versionado_e_valido(self):
        correcoes = carregar_correcoes(CAMINHO_CORRECOES)
        assert correcoes, "o arquivo de correções do projeto está vazio"
        for correcao in correcoes:
            assert correcao["cd_cvm"] == "020532", (
                "toda correção viva hoje é do Santander (G4); uma nova exige "
                "revisão explícita deste teste"
            )

    def test_toda_correcao_cita_documento_do_manifesto_ifrs(self):
        """Não se cita documento que o repositório não registra."""
        manifesto = {
            linha["documento"]: linha["hash_sha256"]
            for linha in csv.DictReader(
                open(
                    "corpus/ifrs/manifesto_ifrs.csv",
                    newline="",
                    encoding="utf-8",
                )
            )
        }
        for correcao in carregar_correcoes(CAMINHO_CORRECOES):
            documento = correcao["fonte_documento"]
            assert documento in manifesto, f"{documento} fora do manifesto IFRS"
            assert correcao["fonte_sha256"] == manifesto[documento], (
                f"SHA-256 da correção de {documento} diverge do manifesto — "
                "a peça mudou desde a revisão"
            )
