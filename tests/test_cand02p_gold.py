"""Contratos do gold adjudicado do CAND-02-P (`scripts/cand02p_gold.py`)."""

from __future__ import annotations

import csv
import json

import pytest

from scripts import cand02p_gold as g
from scripts import cand02p_piloto as p


def _cenario(tmp_path, monkeypatch, humano, claude, adjudicacao):
    monkeypatch.setattr(p, "DESTINO", tmp_path)
    H = tmp_path / "humana"
    H.mkdir()
    (H / "mapa.json").write_text(json.dumps({f"H{n:02d}": {"par": "P", "item": f"E{n:03d}"}
                                             for n in range(1, len(humano) + 1)}))
    with open(H / "rotulos.csv", "w") as f:
        f.write("item,nota,motivo,acao,critico,julgavel,justificativa\n")
        for n, nota in enumerate(humano, 1):
            f.write(f"H{n:02d},{nota},{'numero' if nota else ''},{'verificar' if nota == 2 else ''},false,true,x\n")
    pasta = tmp_path / "rotulos" / "claude" / "teste"
    pasta.mkdir(parents=True)
    with open(pasta / "P.jsonl", "w") as f:
        for n, nota in enumerate(claude, 1):
            f.write(json.dumps({"item": f"E{n:03d}", "nota": nota, "motivo": "numero" if nota else None,
                                "acao": "verificar" if nota == 2 else None, "critico": False,
                                "julgavel": True, "justificativa": "x"}) + "\n")
    with open(H / "adjudicacao.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item", "nota_humano", "nota_claude", "nota_final", "comentario"])
        w.writeheader()
        w.writerows(adjudicacao)


def test_gold_usa_o_acordo_e_a_nota_final_da_adjudicacao(tmp_path, monkeypatch):
    _cenario(tmp_path, monkeypatch, [0, 1, 2], [0, 0, 2],
             [{"item": "H02", "nota_humano": 1, "nota_claude": 0, "nota_final": 0, "comentario": ""}])
    gold = g.montar_gold()
    assert [x["nota_gold"] for x in gold] == [0, 0, 2]
    assert [x["origem"] for x in gold] == ["acordo", "adjudicada", "acordo"]


def test_discordancia_sem_adjudicacao_levanta(tmp_path, monkeypatch):
    _cenario(tmp_path, monkeypatch, [0, 1], [0, 0], [])
    with pytest.raises(ValueError, match="sem adjudicação"):
        g.montar_gold()


def test_adjudicacao_que_nao_bate_com_as_leituras_levanta(tmp_path, monkeypatch):
    _cenario(tmp_path, monkeypatch, [0, 1], [0, 0],
             [{"item": "H02", "nota_humano": 2, "nota_claude": 0, "nota_final": 0, "comentario": ""}])
    with pytest.raises(ValueError, match="sem adjudicação coerente"):
        g.montar_gold()


def test_auc_perfeito_inverso_e_empate():
    itens = [{"n": 2, "pct": {"m": 0.1}}, {"n": 0, "pct": {"m": 0.9}}]
    assert g.auc(itens, "m", "n", 2) == 1.0
    itens[0]["pct"]["m"], itens[1]["pct"]["m"] = 0.9, 0.1
    assert g.auc(itens, "m", "n", 2) == 0.0
    itens[0]["pct"]["m"] = itens[1]["pct"]["m"] = 0.5
    assert g.auc(itens, "m", "n", 2) == 0.5


def test_auc_sem_um_dos_lados_levanta_em_vez_de_inventar():
    with pytest.raises(ZeroDivisionError):
        g.auc([{"n": 0, "pct": {"m": 0.3}}], "m", "n", 2)
