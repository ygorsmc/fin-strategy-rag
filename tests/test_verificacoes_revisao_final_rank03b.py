"""Contraprovas das verificações da revisão final do lote C (Rank 3-B)."""
from __future__ import annotations

import csv
import json
from datetime import date

import duckdb

from scripts import verificacoes_revisao_final_rank03b as vr


def _piloto(papel="vmax", estratos=("E1_fronteira_UNIDADE",), aquisicao="integro"):
    return {"papel": papel, "estratos": list(estratos), "aquisicao": aquisicao,
            "id_doc": "1", "escala_declarada": "UNIDADE"}


class TestAmostraDeDesenho:
    def test_so_vmax_integro_e_e1_a_e4(self):
        """A tabela publicada misturou os 50 vmax do piloto com os 23 de E1–E4
        (auditoria de 16/09): a população tem de ser uma só."""
        assert vr.e_amostra_de_desenho(_piloto())
        assert vr.e_amostra_de_desenho(_piloto(estratos=("E7_varias_versoes", "E3_interior")))
        assert not vr.e_amostra_de_desenho(_piloto(papel="v1"))
        assert not vr.e_amostra_de_desenho(_piloto(aquisicao="falha_de_acesso"))
        assert not vr.e_amostra_de_desenho(_piloto(estratos=("E5_companhia_so_MIL",)))
        assert not vr.e_amostra_de_desenho(_piloto(estratos=("E10_trecho_completo",)))

    def test_conta_so_a_populacao(self, monkeypatch):
        monkeypatch.setattr(vr.adj, "adjudicar_formulario",
                            lambda f, d: {"veredito": "corrigida"})
        r = vr.amostra_de_desenho([_piloto(), _piloto(papel="v1"),
                                   _piloto(estratos=("E5_x",))], ler=lambda d: None)
        assert r["documentos"] == 1
        assert r["por_declarada"] == {"UNIDADE|corrigida": 1}


class TestContinuidadeB8:
    def _painel(self, linhas):
        con = duckdb.connect(":memory:")
        con.execute("CREATE TABLE ativo (id_correcao VARCHAR, cd_cvm VARCHAR, dt_fim DATE, "
                    "valor_bruto DOUBLE, escala_declarada VARCHAR, estado VARCHAR)")
        if linhas:
            con.executemany("INSERT INTO ativo VALUES (?, ?, ?, ?, ?, ?)", linhas)
        return con

    def test_corroborada_so_por_vizinho_mil_dentro_da_janela(self):
        con = self._painel([
            ("ESC-1", "A", date(2020, 6, 30), 100.0, "UNIDADE", "valido"),
            (None, "A", date(2020, 3, 31), 110.0, "MIL", "valido"),
            (None, "A", date(2019, 1, 31), 100.0, "MIL", "valido"),   # fora da janela
            (None, "A", date(2020, 9, 30), 100.0, "UNIDADE", "valido"),
        ])
        [r] = vr.continuidade_b8(con, ["ESC-1"])
        assert r["situacao"] == "corroborada"
        assert r["razoes_com_vizinhos_mil"] == [1.1]
        assert r["vizinhos"] == 2

    def test_sem_vizinho_mil_nao_e_corroborada(self):
        con = self._painel([
            ("ESC-2", "B", date(2025, 9, 30), 5.0, "UNIDADE", "valido"),
            (None, "B", date(2025, 6, 30), 5.0, "UNIDADE", "valido"),
        ])
        [r] = vr.continuidade_b8(con, ["ESC-2"])
        assert r["situacao"] == "sem_vizinho_mil" and r["vizinhos_declarados_mil"] == 0

    def test_correcao_sem_ativo_valido_e_declarada(self):
        [r] = vr.continuidade_b8(self._painel([]), ["ESC-9"])
        assert r["situacao"] == "sem_ativo_valido"

    def test_seleciona_so_correcoes_por_documento_com_um_bruto(self, tmp_path):
        caminho = tmp_path / "m.csv"
        with open(caminho, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["id_correcao", "base", "numerica_contagem"])
            w.writeheader()
            w.writerow({"id_correcao": "a", "base": "corrigida_documento",
                        "numerica_contagem": json.dumps({"bruto": 1})})
            w.writerow({"id_correcao": "b", "base": "corrigida_documento",
                        "numerica_contagem": json.dumps({"bruto": 2})})
            w.writerow({"id_correcao": "c", "base": "herdada_trecho",
                        "numerica_contagem": json.dumps({"bruto": 0})})
        assert vr.correcoes_com_um_bruto(caminho) == ["a"]


class TestComparacaoDaReproducao:
    def _pasta(self, raiz, evidencias, manifesto="x"):
        raiz.mkdir()
        (raiz / "evidencias.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in evidencias), encoding="utf-8")
        (raiz / "herdados.jsonl").write_text("", encoding="utf-8")
        (raiz / "resumo.json").write_text(
            json.dumps({"manifesto": {"linhas": 1, "sha256": manifesto}}), encoding="utf-8")
        (raiz / "correcoes_escala.csv").write_text("m", encoding="utf-8")
        return raiz

    def test_identica(self, tmp_path):
        e = [{"id_doc": "1", "veredito": "corrigida"}]
        gov = self._pasta(tmp_path / "g", e, "antigo")
        rep = self._pasta(tmp_path / "r", e, "novo")
        r = vr.comparar_reproducao(gov, gov / "correcoes_escala.csv", rep)
        assert r["documentos_diferentes"] == [] and r["resumo_identico_fora_o_sha"]
        assert r["manifesto_da_execucao_2_sha256_no_resumo"] == "antigo"

    def test_documento_ausente_ou_diferente_aparece(self, tmp_path):
        gov = self._pasta(tmp_path / "g", [{"id_doc": "1", "veredito": "corrigida"},
                                           {"id_doc": "2", "veredito": "confirmada"}])
        rep = self._pasta(tmp_path / "r", [{"id_doc": "1", "veredito": "indecidivel"}])
        r = vr.comparar_reproducao(gov, gov / "correcoes_escala.csv", rep)
        assert r["documentos_diferentes"] == ["1", "2"]
