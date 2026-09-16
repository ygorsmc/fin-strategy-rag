"""Contrato da curadoria IA de 15/09: anotação contextual não vira permissão.

Não testa acerto contábil por autoavaliação: protege procedência, limites,
preservação do CSV anterior e casos dimensionais explicitamente revisados.
"""

import csv
import json
from collections import Counter
from pathlib import Path

import pytest


RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "artefatos/curadoria_plano_contas/2026-09-15"
CSV = RAIZ / "corpus/cvm/plano_padrao_contas.csv"


def _linhas():
    with CSV.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def _contextos():
    return {
        c["id_evidencia"]: c
        for c in map(json.loads, (PASTA / "contextos.jsonl").read_text().splitlines())
    }


def test_os_onze_campos_originais_e_a_ordem_nao_mudam():
    antes = json.loads((PASTA / "antes.json").read_text())
    assert len(antes["campos"]) == 11
    assert len(antes["linhas"]) == len(_linhas()) == 300
    assert [{k: r[k] for k in antes["campos"]} for r in _linhas()] == antes["linhas"]


def test_anotacao_nao_promove_classe_operacional():
    assert all(r["classe_confirmada"] == "" for r in _linhas())
    assert all(r["anotador_ia"] == "Codex (IA)" for r in _linhas())
    assert all(r["data_anotacao_ia"] == "2026-09-15" for r in _linhas())


def test_classe_status_e_dimensao_tem_vocabulario_fechado():
    permitidos = {
        ("monetaria", "montante_em_moeda", "anotada_ia_nao_validada_humanamente"),
        ("nao_monetaria", "moeda_por_acao", "anotada_ia_nao_validada_humanamente"),
        ("", "", "inconclusiva_descricao"),
    }
    for r in _linhas():
        assert (r["classe_anotada_ia"], r["dimensao_anotada_ia"],
                r["status_anotacao_ia"]) in permitidos
    assert Counter(r["classe_anotada_ia"] for r in _linhas()) == {
        "monetaria": 284, "nao_monetaria": 7, "": 9,
    }


def test_marcadores_sem_descricao_nao_recebem_classe_por_magnitude():
    for r in _linhas():
        if r["ds_conta_exemplo"] in {"0", "-"}:
            assert r["classe_anotada_ia"] == ""
            assert r["status_anotacao_ia"] == "inconclusiva_descricao"


def test_cada_linha_tem_evidencia_distinta_do_sinal_de_magnitude():
    contextos = _contextos()
    assert len(contextos) == 300
    assert len({r["evidencia_contextual_ia"] for r in _linhas()}) == 300
    for r in _linhas():
        arquivo, identificador = r["evidencia_contextual_ia"].split("#")
        assert (RAIZ / arquivo).is_file()
        c = contextos[identificador]
        assert (r["demonstrativo"], r["cd_conta"], r["ds_conta_exemplo"]) == (
            c["demonstrativo"], c["cd_conta"], c["ds_conta"],
        )
        assert r["classe_anotada_ia"] == c["classe_anotada_ia"]
        assert r["escopo_anotacao_ia"] == c["escopo"] == (
            "descricao_exemplar_na_declaracao_identificada"
        )
        assert len(r["fundamento_anotacao_ia"]) >= 60
        assert r["fonte_anotacao_ia"]
        assert c["cd_cvm"] and c["conjunto"] and c["dt_refer"]
        assert c["versao_documento"] >= 1 and c["dt_fim_exerc"]
        assert len(c["sha256_painel"]) == 64


@pytest.mark.parametrize("conta", ["2.01.06.02.02", "2.02.04.02.02"])
def test_provisao_pequena_e_montante_sem_apagar_proposta_original(conta):
    r = next(r for r in _linhas() if r["demonstrativo"] == "BPP" and r["cd_conta"] == conta)
    assert r["ds_conta_exemplo"] == "Provisões para Reestruturação"
    assert r["classe_proposta"] == "INDEFINIDA"
    assert r["classe_anotada_ia"] == "monetaria"
    assert r["fonte_anotacao_ia"].startswith("CPC25:")


@pytest.mark.parametrize("conta", ["3.99.01.02", "3.99.02.02"])
def test_on_depende_do_pai_da_declaracao_nao_de_exemplo_agregado(conta):
    r = next(r for r in _linhas() if r["demonstrativo"] == "DRE" and r["cd_conta"] == conta)
    c = _contextos()[r["evidencia_contextual_ia"].split("#")[1]]
    assert r["ds_conta_exemplo"] == "ON"
    assert "por Ação" in c["pai"] and "Ação" in c["avo"]
    assert r["classe_anotada_ia"] == "nao_monetaria"
    assert c["cd_conta_pai"] == conta.rsplit(".", 1)[0]


def test_ancestral_nao_e_a_propria_conta():
    for c in _contextos().values():
        for nivel in ["pai", "avo"]:
            codigo = c[f"cd_conta_{nivel}"]
            if codigo is None:
                assert c[nivel] is None
            else:
                assert codigo != c["cd_conta"]
                assert c["cd_conta"].startswith(codigo + ".")


def test_ambiguidades_textuais_possuem_contexto_de_origem():
    ambiguas = {"ON", "Corrente", "Diferido", "Outros", "Danos", "ANEEL",
                "Carteira Própria", "Carteira de Terceiros",
                "Em Moeda Nacional", "Em Moeda Estrangeira"}
    for c in _contextos().values():
        if c["ds_conta"] in ambiguas:
            assert c["pai"] and c["pai_mesma_declaracao"] is True


def test_acoes_em_tesouraria_no_balanco_nao_sao_contagem():
    linhas = [r for r in _linhas() if r["demonstrativo"] == "BPP"
              and r["ds_conta_exemplo"].lower() == "ações em tesouraria"]
    assert linhas
    assert all(r["classe_anotada_ia"] == "monetaria" for r in linhas)
