"""Contraprovas da extração congelada dos ZIPs da CVM (lote B do Rank 3-B)."""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile

import duckdb
import pytest

from scripts import fonte_zip_cvm as fz

CAB_DEMO = ["CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP",
            "MOEDA", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC",
            "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA"]
CAB_CAD = ["CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "CATEG_DOC",
           "ID_DOC", "DT_RECEB", "LINK_DOC"]


def _csv(cabecalho, linhas):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(cabecalho)
    w.writerows(linhas)
    return buf.getvalue().encode("latin-1")


def _linha(cd, conta, vl, ordem="ÚLTIMO", ini="2020-01-01", fim="2020-09-30",
           escala="MIL", ds="Caixa Líquido Atividades Operacionais"):
    return ["x", "2020-09-30", "1", "Cia", cd, "g", "REAL", escala, ordem, ini, fim,
            conta, ds, str(vl), "S"]


def _zip(pasta, nome="itr_cia_aberta_2020.zip", dfc=None, bpa=None, ind=None):
    conj, _, _, ano = nome[:-4].split("_")
    caminho = pasta / nome
    with zipfile.ZipFile(caminho, "w") as z:
        for demo in fz.CONTAS_POR_DEMONSTRATIVO:
            linhas = {"DFC_MI": dfc or [], "BPA": bpa or []}.get(demo, [])
            z.writestr(f"{conj}_cia_aberta_{demo}_con_{ano}.csv", _csv(CAB_DEMO, linhas))
            z.writestr(f"{conj}_cia_aberta_{demo}_ind_{ano}.csv",
                       _csv(CAB_DEMO, ind or [] if demo == "DFC_MI" else []))
        z.writestr(f"{conj}_cia_aberta_{ano}.csv", _csv(CAB_CAD, [
            ["x", "2020-09-30", "2", "Cia", "33", "ITR", "900", "2020-11-20", "http://l"],
            ["x", "2020-09-30", "1", "Cia", "33", "ITR", "800", "2020-11-10", "http://l"],
        ]))
    return caminho


def _manifesto(pasta, zips, alterar=None):
    caminho = pasta / "manifesto.csv"
    with open(caminho, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["conjunto", "ano", "arquivo", "url", "data_download",
                    "tamanho_bytes", "hash_sha256"])
        for z in zips:
            h = hashlib.sha256(z.read_bytes()).hexdigest()
            w.writerow(["itr", "2020", z.name, "u", "d", "0",
                        "0" * 64 if alterar == z.name else h])
    return caminho


class TestFonteCongelada:
    def test_zip_diferente_do_pinado_falha(self, tmp_path):
        z = _zip(tmp_path)
        with pytest.raises(fz.FonteAlterada, match="republica"):
            fz.verificar_zips(tmp_path, _manifesto(tmp_path, [z], alterar=z.name))

    def test_zip_pinado_ausente_falha(self, tmp_path):
        z = _zip(tmp_path)
        m = _manifesto(tmp_path, [z])
        z.unlink()
        with pytest.raises(fz.FonteAlterada, match="ausente"):
            fz.verificar_zips(tmp_path, m)

    def test_manifesto_vazio_falha(self, tmp_path):
        m = _manifesto(tmp_path, [])
        with pytest.raises(fz.FonteAlterada):
            fz.verificar_zips(tmp_path, m)

    def test_extracao_nao_acontece_se_a_fonte_mudou(self, tmp_path):
        z = _zip(tmp_path, dfc=[_linha("33", "6.01", 5)])
        con = duckdb.connect(":memory:")
        with pytest.raises(fz.FonteAlterada):
            fz.extrair(con, tmp_path, _manifesto(tmp_path, [z], alterar=z.name))
        assert not con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name='declaracoes'"
        ).fetchone()[0]


class TestExtracao:
    def _extrair(self, tmp_path, **kw):
        z = _zip(tmp_path, **kw)
        con = duckdb.connect(":memory:")
        hashes = fz.extrair(con, tmp_path, _manifesto(tmp_path, [z]))
        return con, hashes

    def test_so_contas_alvo_e_so_consolidado(self, tmp_path):
        con, _ = self._extrair(
            tmp_path,
            dfc=[_linha("33", "6.01", 5), _linha("33", "6.01.01", 9)],
            ind=[_linha("33", "6.01", 777)],
        )
        assert con.execute("SELECT cd_conta, vl FROM declaracoes").fetchall() == [("6.01", 5.0)]

    def test_codigo_cvm_preserva_zeros(self, tmp_path):
        """RN11: companhia resolve por CD_CVM, com os zeros."""
        con, _ = self._extrair(tmp_path, dfc=[_linha("33", "6.01", 5)])
        assert con.execute("SELECT DISTINCT cd_cvm FROM declaracoes").fetchone()[0] == "000033"
        assert con.execute("SELECT DISTINCT cd_cvm FROM cadastro").fetchone()[0] == "000033"

    def test_penultimo_e_mantido(self, tmp_path):
        """É a segunda declaração do período — a carga compartilhada a descarta."""
        con, _ = self._extrair(tmp_path, dfc=[
            _linha("33", "6.01", 5),
            _linha("33", "6.01", 4, ordem="PENÚLTIMO", ini="2019-01-01", fim="2019-09-30"),
        ])
        assert con.execute("SELECT count(DISTINCT ordem) FROM declaracoes").fetchone()[0] == 2

    def test_balanco_sem_inicio_vira_nulo(self, tmp_path):
        con, _ = self._extrair(tmp_path, bpa=[_linha("33", "1", 100, ini="", fim="2020-09-30",
                                                     ds="Ativo Total")])
        assert con.execute("SELECT dt_ini FROM declaracoes").fetchone()[0] is None

    def test_valor_vazio_e_nulo_nem_zero_nem_erro(self, tmp_path):
        """G0.4 só conta o nulo se a extração não morrer nem o transformar em zero."""
        con, _ = self._extrair(tmp_path, dfc=[_linha("33", "6.01", ""), _linha("34", "6.01", 0)])
        assert con.execute("SELECT cd_cvm, vl FROM declaracoes ORDER BY 1").fetchall() == [
            ("000033", None), ("000034", 0.0)]

    def test_cadastro_guarda_todas_as_versoes_em_ordem(self, tmp_path):
        con, hashes = self._extrair(tmp_path, dfc=[_linha("33", "6.01", 5)])
        assert con.execute("SELECT versao, id_doc FROM cadastro").fetchall() == [(1, "800"), (2, "900")]
        assert list(hashes) == ["itr_cia_aberta_2020.zip"]
