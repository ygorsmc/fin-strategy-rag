"""Contraprovas do esqueleto do plano padrão de contas.

O risco desta peça é a proposta automática **virar a classificação**. Por isso
os casos travam, antes de tudo, que `classe_confirmada` nasce vazia e que o
sinal separa valor por ação de montante — que é o erro capaz de multiplicar o
Lucro por Ação por mil.
"""

from __future__ import annotations

import csv
import json

import duckdb
import pytest

from scripts import esqueleto_plano_padrao as esqueleto
from scripts import inventariar_escala_cvm as inventario


def _conta(cd_conta, razao, linhas=100, demonstrativo="DRE", ds="Conta",
           mediana=1.0, n_razao=100, total=1000):
    return {
        "demonstrativo": demonstrativo, "cd_conta": cd_conta,
        "linhas": linhas, "companhias": 10, "ds_conta_exemplo": ds,
        "mediana_bruta": mediana, "razao_mediana": razao,
        "n_razao": n_razao, "total_de_linhas": total,
    }


class TestSinalDeMonetariedade:
    def test_valor_por_acao_e_classificado_nao_monetario(self):
        """1e-8 do ativo é ordem de grandeza de valor por ação.

        É o caso que importa: reescalar `3.99` de UNIDADE para MIL
        multiplicaria o Lucro por Ação por mil — o mesmo defeito que a correção
        de escala existe para consertar.
        """
        linha = esqueleto.montar(
            [_conta("3.99.01.01", 9.5e-08, ds="Lucro Básico por Ação")], 1
        )[0]
        assert linha["classe_proposta"] == "nao_monetaria"
        assert "por ação" in linha["evidencia"]

    def test_montante_e_classificado_monetario(self):
        linha = esqueleto.montar([_conta("1", 1.0, ds="Ativo Total")], 1)[0]
        assert linha["classe_proposta"] == "monetaria"

    def test_zona_cinzenta_nao_chuta(self):
        """Entre os dois limiares a peça sinaliza, em vez de decidir."""
        linha = esqueleto.montar([_conta("2.01.06.02.02", 9.98e-05)], 1)[0]
        assert linha["classe_proposta"] == "INDEFINIDA"
        assert "exige decisão humana" in linha["evidencia"]

    def test_sem_ativo_para_comparar_nao_chuta(self):
        linha = esqueleto.montar([_conta("X", None, n_razao=0)], 1)[0]
        assert linha["classe_proposta"] == "INDEFINIDA"

    def test_os_limiares_estao_declarados(self):
        """Se mudarem, a proposta muda — e isso tem de aparecer no diff."""
        assert esqueleto.TETO_NAO_MONETARIA == 1e-6
        assert esqueleto.PISO_MONETARIA == 1e-4
        assert esqueleto.CONTAS_NO_ESQUELETO == 300


class TestAPropostaNaoDecide:
    def test_classe_confirmada_nasce_vazia(self):
        """É o único campo que decide, e o script nunca o preenche."""
        linhas = esqueleto.montar(
            [_conta("1", 1.0), _conta("3.99", 1e-08)], 2
        )
        assert all(l["classe_confirmada"] == "" for l in linhas)

    def test_a_evidencia_acompanha_toda_linha(self):
        """Revisar sem evidência ao lado seria carimbar a proposta."""
        for linha in esqueleto.montar([_conta("1", 1.0), _conta("3.99", 1e-8)], 2):
            assert linha["evidencia"]
            assert linha["razao_sobre_ativo_total"]

    def test_nao_sobrescreve_anotacao_existente(self, tmp_path, monkeypatch):
        """Regerar por engano apagaria horas de anotação humana."""
        destino = tmp_path / "plano.csv"
        destino.write_text("ja anotado", encoding="utf-8")
        monkeypatch.setattr(esqueleto, "DESTINO", destino)
        assert esqueleto.principal() == 1
        assert destino.read_text(encoding="utf-8") == "ja anotado"


class TestCoberturaEOrdem:
    def test_ordena_por_cobertura_e_acumula(self):
        linhas = esqueleto.montar(
            [_conta("A", 1.0, linhas=700, total=1000),
             _conta("B", 1.0, linhas=300, total=1000)], 2
        )
        assert linhas[0]["cobertura_acumulada_pct"] == 70.0
        assert linhas[1]["cobertura_acumulada_pct"] == 100.0

    def test_corta_no_numero_pedido(self):
        entrada = [_conta(str(i), 1.0, linhas=10, total=100) for i in range(10)]
        assert len(esqueleto.montar(entrada, 3)) == 3


class TestContraOArtefatoReal:
    """Checagens contra o CSV gerado — baratas e decisivas."""

    @staticmethod
    def _linhas():
        if not esqueleto.DESTINO.is_file():
            pytest.skip("esqueleto ainda não gerado")
        with esqueleto.DESTINO.open(encoding="utf-8") as arq:
            return list(csv.DictReader(arq))

    def test_ativo_total_tem_razao_um(self):
        """**A checagem de sanidade que achou um bug meu.**

        `Ativo Total` dividido pelo ativo total é 1,0 por construção. Saía
        1e-3 porque eu dividia `vl_conta` bruto por `valor_reais` escalado —
        erro de mil, em silêncio, no próprio sinal.
        """
        ativo = [l for l in self._linhas()
                 if l["demonstrativo"] == "BPA" and l["cd_conta"] == "1"]
        assert ativo, "Ativo Total tem de estar no esqueleto"
        assert float(ativo[0]["razao_sobre_ativo_total"]) == pytest.approx(1.0, rel=1e-3)

    def test_todo_lucro_por_acao_sai_nao_monetario(self):
        por_acao = [l for l in self._linhas() if l["cd_conta"].startswith("3.99")]
        assert por_acao, "as contas 3.99.* têm de estar no esqueleto"
        assert all(l["classe_proposta"] == "nao_monetaria" for l in por_acao)

    def test_nenhuma_classe_confirmada_foi_preenchida_pelo_script(self):
        linhas = self._linhas()
        preenchidas = [l for l in linhas if l["classe_confirmada"]]
        assert not preenchidas or all(
            l["classe_confirmada"] in {"monetaria", "nao_monetaria"}
            for l in preenchidas
        ), "vocabulário de `classe_confirmada` é monetaria | nao_monetaria"


def _decl(conjunto, dt_refer, escala, valor, versao=1):
    return {
        "cd_cvm": "A", "conjunto": conjunto, "arquivo": f"{conjunto}_x.zip",
        "membro": f"{conjunto}_BPA_con.csv", "dt_refer": dt_refer,
        "versao": versao,
        "ordem_exerc": "ÚLTIMO" if conjunto == "dfp" else "PENÚLTIMO",
        "dt_fim_exerc": "2020-12-31", "escala": escala, "vl_conta": float(valor),
    }


def _gravar_inventario(pasta, casos, versao=inventario.VERSAO_DO_ESQUEMA):
    caminho_inventario = pasta / "inventario.jsonl"
    caminho_resumo = pasta / "resumo.json"
    caminho_inventario.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in casos),
        encoding="utf-8",
    )
    caminho_resumo.write_text(
        json.dumps({"versao_do_esquema": versao}), encoding="utf-8"
    )
    return caminho_inventario, caminho_resumo


class TestDependenciaDoInventario:
    """Contrato K1 — QW8 e QW1/QW2 da conferência de 15/09.

    A exclusão prometida no docstring dependia de um arquivo cuja ausência
    virava `set()` em silêncio — e o esqueleto media sobre tudo.
    """

    def test_inventario_ausente_falha(self, tmp_path):
        with pytest.raises(esqueleto.InventarioAusente):
            esqueleto.documentos_defeituosos(
                tmp_path / "nao_existe.jsonl", tmp_path / "nao_existe.json"
            )

    def test_inventario_ausente_falha_pelo_caminho_padrao(self, tmp_path, monkeypatch):
        """A contraprova E da conferência, pelo mesmo caminho que `executar` usa."""
        monkeypatch.setattr(esqueleto, "INVENTARIO", tmp_path / "nao.jsonl")
        monkeypatch.setattr(esqueleto, "RESUMO_DO_INVENTARIO", tmp_path / "nao.json")
        with pytest.raises(esqueleto.InventarioAusente):
            esqueleto.documentos_defeituosos()

    def test_esquema_anterior_falha(self, tmp_path):
        casos = inventario.adjudicar([
            _decl("dfp", "2020-12-31", "MIL", 7), _decl("itr", "2021-03-31", "UNIDADE", 7),
        ])
        caminhos = _gravar_inventario(tmp_path, casos, versao=None)
        with pytest.raises(esqueleto.InventarioIncompativel):
            esqueleto.documentos_defeituosos(*caminhos)

    def test_declaracao_sem_estado_falha_mesmo_com_resumo_v2(self, tmp_path):
        """Resumo e inventário de versões diferentes não podem se misturar."""
        casos = inventario.adjudicar([
            _decl("dfp", "2020-12-31", "MIL", 7), _decl("itr", "2021-03-31", "UNIDADE", 7),
        ])
        for d in casos[0]["declaracoes"]:
            d.pop("adjudicacao")
        with pytest.raises(esqueleto.InventarioIncompativel):
            esqueleto.documentos_defeituosos(*_gravar_inventario(tmp_path, casos))

    def test_inventario_valido_sem_adjudicacao_devolve_vazio(self, tmp_path):
        """Válido e vazio é estado DIFERENTE de ausente: não levanta."""
        casos = inventario.adjudicar([
            _decl("dfp", "2020-12-31", "MIL", 0), _decl("itr", "2021-03-31", "UNIDADE", 0),
        ])
        assert esqueleto.documentos_defeituosos(*_gravar_inventario(tmp_path, casos)) == set()

    def test_so_a_declaracao_adjudicada_exclui_o_documento(self, tmp_path):
        """O `100000 UNIDADE` equivalente em reais não condena o documento dele."""
        casos = inventario.adjudicar([
            _decl("dfp", "2020-12-31", "MIL", 100),
            _decl("itr", "2021-03-31", "UNIDADE", 100_000),
            _decl("itr", "2021-06-30", "UNIDADE", 100),
        ])
        assert esqueleto.documentos_defeituosos(*_gravar_inventario(tmp_path, casos)) == {
            ("A", "itr", "2021-06-30", 1)
        }

    def test_a_exclusao_no_painel_respeita_o_conjunto(self):
        """ITR e DFP da mesma companhia, data e versão são documentos distintos."""
        con = duckdb.connect(":memory:")
        con.execute(
            "CREATE TABLE fatos_contabeis (cd_cvm VARCHAR, conjunto VARCHAR, "
            "demonstrativo VARCHAR, dt_refer DATE, versao_documento INTEGER, "
            "cd_conta VARCHAR, ds_conta VARCHAR, vl_conta DOUBLE, "
            "valor_reais DOUBLE, escala VARCHAR, origem VARCHAR)"
        )
        for conjunto in ("itr", "dfp"):
            con.execute(
                "INSERT INTO fatos_contabeis VALUES ('A', ?, 'BPA', "
                "DATE '2022-12-31', 1, '1', 'Ativo Total', 10, 10000, 'MIL', "
                "'arquivado')",
                [conjunto],
            )
        linhas = esqueleto.levantar(con, {("A", "itr", "2022-12-31", 1)})
        con.close()
        assert sum(l["linhas"] for l in linhas) == 1, "sai o ITR; a DFP fica"
