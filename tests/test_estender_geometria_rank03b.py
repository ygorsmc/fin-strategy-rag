"""Orquestração da extensão: dados sintéticos, sem executar fontes reais."""
from copy import deepcopy
import json
import subprocess
import xml.etree.ElementTree as ET

import pytest

from scripts import estender_geometria_rank03b as e


def documentos():
    return [dict(id_doc=str(i), cd_cvm=str(i), conjunto="itr", dt_refer="2024-09-30",
                 versao=1, formato="xml_unico", escala_declarada="MIL", sha256="hash",
                 papel="controle", trecho=1) for i in range(405)]


def piloto_fixture():
    prova = dict(anexo=1, pagina=3, conta="1.01.01", forma="bruto")
    d = dict(id_doc="1", papel="verificacao", escala_proposta="MIL", evidencia={"provas": [prova]})
    piloto = dict(etapa="verificacao", regra="GEOM-1", registros=[d], pin_sha256="hash")
    parecer = dict(veredito="sem_erro_nas_aceitacoes_conferidas", piloto_sha256="hash",
                   provas_conferidas=[e.chave_prova(d, prova)])
    pin = dict(selecao_sha256="hash", codigo_sha256={n: "hash" for n in e.CODIGO}, poppler="poppler fixture")
    return piloto, parecer, pin


@pytest.mark.parametrize("mutacao", [None, "sem_aceitacao", "sem_parecer", "prova_omitida",
                                    "prova_alterada", "outro_piloto", "outro_pin", "outra_selecao", "outro_codigo",
                                    "pin_vazio", "pin_parcial", "sentinela_sem_parecer", "sentinela_conferida"])
def test_precondicoes_fechadas(monkeypatch, mutacao):
    p, a, pin = piloto_fixture()
    monkeypatch.setattr(e.rad, "sha256", lambda p: "hash")
    if mutacao == "sem_aceitacao": p["registros"][0]["escala_proposta"] = None
    if mutacao == "sem_parecer": a["veredito"] = "pendente"
    if mutacao == "prova_omitida": a["provas_conferidas"] = []
    if mutacao == "prova_alterada": a["provas_conferidas"][0]["conta"] = "1"
    if mutacao == "outro_piloto": a["piloto_sha256"] = "outro"
    if mutacao == "outro_pin": p["pin_sha256"] = "outro"
    if mutacao == "outra_selecao": pin["selecao_sha256"] = "outro"
    if mutacao == "outro_codigo": pin["codigo_sha256"][e.CODIGO[0]] = "outro"
    if mutacao == "pin_vazio": pin["codigo_sha256"] = {}
    if mutacao == "pin_parcial": del pin["codigo_sha256"][e.CODIGO[0]]
    if mutacao in ("sentinela_sem_parecer", "sentinela_conferida"):
        d = deepcopy(p["registros"][0])
        d.update(papel="sentinela", id_doc="historico")
        p["registros"].append(d)
        if mutacao == "sentinela_conferida":
            a["provas_conferidas"].append(e.chave_prova(d, d["evidencia"]["provas"][0]))
    if mutacao in (None, "sentinela_conferida"):
        e.validar_precondicoes(p, a, pin)
    else:
        with pytest.raises(AssertionError): e.validar_precondicoes(p, a, pin)


@pytest.mark.parametrize("classe,resultado", [("bruto", "confirmacao_candidata"),
                                            ("dividido", "correcao_candidata"),
                                            ("multiplicado", "abstencao"),
                                            ("conflitante", "abstencao"), ("nenhum", "abstencao")])
def test_nao_aplica_candidatas(monkeypatch, classe, resultado):
    monkeypatch.setattr(e.geom, "extrair_documento", lambda *a: {"classe": classe, "provas": []})
    d = documentos()[0]
    antes = deepcopy(d)
    assert e.extrair(d)["resultado"] == resultado
    assert d == antes


@pytest.mark.parametrize("erro", [ET.ParseError("x"), subprocess.CalledProcessError(1, "fixture"),
                                  subprocess.TimeoutExpired("fixture", 120)])
def test_falha_permanece_no_denominador(monkeypatch, erro):
    def falhar(*args): raise erro
    monkeypatch.setattr(e.geom, "extrair_documento", falhar)
    assert e.extrair(documentos()[0])["resultado"] == "falha_de_leitura"


def test_hash_errado_nao_vira_abstencao(monkeypatch):
    def falhar(*args): raise AssertionError("hash")
    monkeypatch.setattr(e.geom, "extrair_documento", falhar)
    with pytest.raises(AssertionError, match="hash"): e.extrair(documentos()[0])


@pytest.mark.parametrize("mutacao", [None, "escopo_incompleto", "id_duplicado", "outra_versao"])
def test_execucao_pinada_integral_sem_sobrescrita(monkeypatch, tmp_path, mutacao):
    p, a, pin = piloto_fixture()
    monkeypatch.setattr(e, "BASE", tmp_path)
    monkeypatch.setattr(e, "PARECER", tmp_path / "parecer.json")
    monkeypatch.setattr(e, "EVIDENCIAS", tmp_path / "origem.jsonl")
    monkeypatch.setattr(e.rad, "sha256", lambda p: "hash")
    chamadas_guarda = []
    monkeypatch.setattr(e, "conferir_protegidos", lambda s: chamadas_guarda.append(s) or {"intacto": True})
    docs = documentos()
    if mutacao == "escopo_incompleto": docs.pop()
    if mutacao == "id_duplicado": docs[1]["id_doc"] = docs[0]["id_doc"]
    e.EVIDENCIAS.write_text("\n".join(json.dumps(d) for d in docs))
    for nome, obj in (("selecao.json", {}), ("piloto_verificacao.json", p),
                      ("pin_verificacao.json", pin), ("parecer.json", a)):
        (tmp_path / nome).write_text(json.dumps(obj))
    class Processo:
        stderr = b"outra versao" if mutacao == "outra_versao" else b"poppler fixture"
    monkeypatch.setattr(e.subprocess, "run", lambda *a, **k: Processo())
    lidos = []
    def extrair(doc):
        assert (tmp_path / "extensao/pin.json").exists()
        assert len(chamadas_guarda) >= 1
        lidos.append(doc["id_doc"])
        return {**doc, "resultado": "abstencao"}
    monkeypatch.setattr(e, "extrair", extrair)
    if mutacao:
        with pytest.raises(AssertionError): e.executar()
        assert lidos == []
        return
    r = e.executar()
    assert len(lidos) == len(set(lidos)) == r["documentos"] == 405
    assert len(chamadas_guarda) == 2
    assert not any(r[k] for k in ("promovido_ao_manifesto", "heranca_executada", "g0_medido"))
    with pytest.raises(FileExistsError): e.executar()
    assert len(lidos) == 405
