"""Revalida provas e mede G0/G1 após fechamento local do consumidor, sem y.

A adjudicação 4b NÃO é reescrita: comprova-se por AST que a única mudança
no módulo foi a guarda de prova serializada, e todas as provas passam de novo.
"""
import ast
import csv
import hashlib
import json
from pathlib import Path

from scripts import adjudicar_escala_rank03b as adj
from scripts import fonte_rad_cvm as rad
from scripts import gates_painel_pesquisa_rank03b as gates
from scripts import auditar_rank03b_consumo_operacional as auditor

DESTINO = Path("artefatos/correcao_crf_rank03b_2026-09-17")
RAD = Path("scripts/fonte_rad_cvm.py")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sem_validador(texto):
    arvore = ast.parse(texto)
    arvore.body = [n for n in arvore.body
                  if not isinstance(n, ast.FunctionDef) or n.name != "validar_escopo_numerico_v4"]
    return ast.dump(arvore, include_attributes=False)


def proibido(*args, **kwargs):
    raise AssertionError("Cegueira CRF: rótulo real proibido")


def gravar(nome, obj):
    (DESTINO / nome).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n")


def main():
    auditor._somas_do_rotulo = proibido
    pin = json.loads((DESTINO / "antes_execucao4b.json").read_text())
    anterior = DESTINO / "codigo_pre_fecho_consumidor/fonte_rad_cvm.py"
    assert sha(anterior) == pin["codigo"][str(RAD)]
    assert sem_validador(anterior.read_text()) == sem_validador(RAD.read_text())
    for p, h in pin["codigo"].items():
        if p != str(RAD):
            assert sha(p) == h, f"Código mudou fora da guarda: {p}"
    # Nada publicado por regra antiga é certificado pela v4.
    evidencias = [json.loads(l) for l in (adj.DESTINO / "evidencias.jsonl").read_text().splitlines()]
    provas = 0
    for e in evidencias:
        assert e.get("regra") == "v4"
        for c in e["numerica"]["casamentos"]:
            rad.validar_escopo_numerico_v4(c, e["dt_refer"])
            provas += 1
    with adj.MANIFESTO_CORRECOES.open() as f:
        manifesto = list(csv.DictReader(f))
    adj.validar_manifesto(manifesto)
    gravar("antes_gates_fecho_consumidor.json", {
        "pin_adjudicacao": sha(DESTINO / "antes_execucao4b.json"),
        "codigo_final": {p: sha(p) for p in pin["codigo"]},
        "somente_funcao_validadora_mudou": True,
        "documentos_revalidados": len(evidencias), "provas_revalidadas": provas,
        "manifesto_sha256": sha(adj.MANIFESTO_CORRECOES),
        "nota": "Traço corrente não é prova; produtor já o recusava. Todas as provas revalidadas.",
    })
    r = gates.executar(gates.carregar_correcoes(gates.CORRECOES), gates.CORRECOES)
    saida = {"veredito": r["veredito"], "digest": r["digest_do_painel"],
             "g0": r["cadeia"][0], "g1": r["cadeia"][1]}
    gravar("resumo_painel.json", saida)
    integridade = {p: sha(p) == h for p, h in pin["protegidos"].items()}
    gravar("integridade_painel.json", integridade)
    assert all(integridade.values())
    print(json.dumps({"veredito": r["veredito"], "digest": r["digest_do_painel"],
                      "g0_3": r["cadeia"][0]["g0_3_saltos_de_escala"],
                      "observacoes": r["cadeia"][1]["observacoes"],
                      "companhias": r["cadeia"][1]["companhias"]}), flush=True)


if __name__ == "__main__":
    main()
