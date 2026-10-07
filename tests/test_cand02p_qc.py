"""Contratos do controle de qualidade do CAND-02-P (`scripts/cand02p_qc.py`).

O detector de acesso já falhou uma vez: só olhava caminho absoluto e não viu o
`cd docs; grep ... bradesco_release_*.md` que expôs um documento de teste no
v2. Cada caso abaixo é um desvio real visto num leitor, ou a contraprova de que
o uso permitido não é marcado.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import cand02p_piloto as p
from scripts import cand02p_qc as qc

RAIZ = Path("/repo")
D = RAIZ / "artefatos" / "cand02p_v3"
OK = {str(D / "rubrica.md"), str(D / "pacotes" / "treino" / "P.json"), str(D / "docs" / "a.md"),
      str(D / "docs" / "b.md"), str(D / "rotulos" / "claude" / "treino" / "P.jsonl")}


def _achados(cmd: str) -> list[str]:
    return qc.estranhos_no_bash(cmd, OK, RAIZ)


def test_curinga_relativo_depois_do_cd_e_marcado():
    assert any(a.startswith("curinga") for a in _achados(f"cd {D}/docs; grep -n 'x' bradesco_release_*.md"))


def test_listar_a_pasta_de_rotulos_e_marcado():
    assert any(a.startswith("listagem") for a in _achados(f"ls -la {D}/rotulos/claude/treino/"))


def test_ls_do_proprio_arquivo_nao_e_marcado():
    assert _achados(f"ls -la {D}/rotulos/claude/treino/P.jsonl 2>&1") == []


def test_caminho_relativo_permitido_nao_e_marcado():
    assert _achados(f"cd {D}; python3 -c \"open('pacotes/treino/P.json')\"; sed -n 1,9p docs/a.md") == []


def test_documento_de_outro_par_e_marcado_mesmo_relativo():
    assert "fora: artefatos/cand02p_v3/docs/c.md" in _achados(f"cd {D}/docs && sed -n 1,5p c.md")


def test_rascunho_fora_do_repositorio_nao_e_marcado():
    assert _achados("python3 /tmp/claude-1000/x/scratchpad/g.py 'risco'") == []


def _rotulos(pasta: Path, notas: list[int]) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    with open(pasta / "P.jsonl", "w") as f:
        for n, nota in enumerate(notas, 1):
            f.write(json.dumps({"item": f"E{n:03d}", "nota": nota, "motivo": "numero" if nota else None,
                                "acao": "verificar" if nota == 2 else None, "critico": False,
                                "julgavel": True, "justificativa": "x"}) + "\n")


def test_reteste_identico_da_alfa_um_e_conta_a_confusao(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "DESTINO", tmp_path)
    notas = [0, 0, 1, 2, 0, 1, 2, 0] * 4
    _rotulos(tmp_path / "rotulos" / "claude" / "treino", notas)
    _rotulos(tmp_path / "rotulos" / qc.LEITOR_RETESTE / "treino", notas)
    r = qc.medir_reteste("P")
    assert r["alfa_ordinal"] == pytest.approx(1.0) and r["acordo_exato"] == 1.0
    assert r["confusao_primeira_x_releitura"] == {"0->0": 16, "1->1": 8, "2->2": 8}


def test_reteste_com_itens_diferentes_levanta(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "DESTINO", tmp_path)
    _rotulos(tmp_path / "rotulos" / "claude" / "treino", [0, 1, 2])
    _rotulos(tmp_path / "rotulos" / qc.LEITOR_RETESTE / "treino", [0, 1])
    with pytest.raises(SystemExit, match="mesmos itens"):
        qc.medir_reteste("P")
