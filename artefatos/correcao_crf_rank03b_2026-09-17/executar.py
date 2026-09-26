"""Execução CRF offline por etapas, sem rótulo. Rodar da raiz com PYTHONPATH=."""
import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from scripts import adjudicar_escala_rank03b as adj
from scripts import auditar_rank03b_consumo_operacional as auditor
from scripts import gates_painel_pesquisa_rank03b as gates

RAIZ = Path.cwd()
BASE = Path("artefatos/painel_pesquisa_rank03b")
DESTINO = Path("artefatos/correcao_crf_rank03b_2026-09-17")
CODIGO = ["scripts/fonte_rad_cvm.py", "scripts/adjudicar_escala_rank03b.py",
          "scripts/gates_painel_pesquisa_rank03b.py", "scripts/painel_pesquisa_rank03b.py",
          "scripts/fonte_zip_cvm.py", "scripts/piloto_fonte_rad_rank03b.py",
          "scripts/auditar_rank03b_consumo_operacional.py",
          "scripts/verificacoes_revisao_final_rank03b.py",
          "resultados/contratos_correcao_crf01_crf03_rank03b_2026-09-17.md",
          "resultados/adendo_contratos_crf_2026-09-18.md",
          "artefatos/correcao_crf_rank03b_2026-09-17/executar.py"]
PROTEGIDOS = ["artefatos/cvm.duckdb", "artefatos/cvm_treino.duckdb",
             "artefatos/painel_pesquisa_rank03b/rad/manifesto_aquisicao.jsonl"]

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()

def gravar(nome, r):
    DESTINO.mkdir(exist_ok=True, parents=True)
    (DESTINO / nome).write_text(json.dumps(r, ensure_ascii=False, indent=2, default=str) + "\n")

def proibido(*args, **kwargs):
    raise AssertionError("Cegueira CRF: rótulo real proibido")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("etapa", choices=["adjudicar", "painel", "verificar"])
    parser.add_argument("--retomada-auditoria", action="store_true",
                        help="4b: defeito de implementação corrigido antes de G0, preserva pin 4")
    args = parser.parse_args()
    nome_pin = "antes_execucao4b.json" if args.retomada_auditoria else "antes_execucao4.json"
    os.environ["RAD_SEM_REDE"] = "1"
    auditor._somas_do_rotulo = proibido
    if args.etapa == "adjudicar":
        pin = DESTINO / nome_pin
        if pin.exists():
            raise RuntimeError("Pin já existe; execução não pode sobrescrever registro anterior")
        gravar(pin.name, {"codigo": {p: sha(p) for p in CODIGO},
                         "protegidos": {p: sha(p) for p in PROTEGIDOS}})
        r = adj.executar()
        anterior_path = BASE / "adjudicacao/execucao3/artefatos/painel_pesquisa_rank03b/adjudicacao/evidencias.jsonl"
        anterior = {r["id_doc"]: r for r in map(json.loads, anterior_path.read_text().splitlines())}
        atual = list(map(json.loads, (BASE / "adjudicacao/evidencias.jsonl").read_text().splitlines()))
        transicoes = Counter((anterior[a["id_doc"]]["veredito"], a["veredito"]) for a in atual)
        resumo = {"regra": r["regra_numerica"], "manifesto": r["manifesto"],
                  "premissa_s5": r["premissa_s5"], "documentos": len(atual),
                  "vereditos": dict(Counter(a["veredito"] for a in atual)),
                  "transicoes": {" -> ".join(k): v for k, v in transicoes.items()},
                  "casos_conhecidos": {a["id_doc"]: {"veredito": a["veredito"], "motivo": a.get("motivo")}
                                       for a in atual if a["id_doc"] in ("76468", "152742")}}
        gravar("readjudicacao.json", resumo)
        print(json.dumps(resumo, ensure_ascii=False), flush=True)
    elif args.etapa == "painel":
        pin = json.loads((DESTINO / nome_pin).read_text())
        if any(sha(p) != h for p, h in pin["codigo"].items()):
            raise RuntimeError("Código mudou depois do pin da execução; explicar e reconciliar antes do gate")
        r = gates.executar(gates.carregar_correcoes(gates.CORRECOES), gates.CORRECOES)
        gravar("resumo_painel.json", {"veredito": r["veredito"], "digest": r["digest_do_painel"],
                                   "g0": r["cadeia"][0], "g1": r["cadeia"][1]})
        print(json.dumps({"veredito": r["veredito"], "digest": r["digest_do_painel"],
                          "g0_3": r["cadeia"][0]["g0_3_saltos_de_escala"],
                          "observacoes": r["cadeia"][1]["observacoes"],
                          "companhias": r["cadeia"][1]["companhias"]}), flush=True)
    else:
        from scripts import verificacoes_revisao_final_rank03b as vr
        r = vr.executar(None)
        print(json.dumps({"versao": r["versao"], "amostra": r["amostra_de_desenho"]}), flush=True)
    pin = json.loads((DESTINO / nome_pin).read_text())
    integridade = {p: sha(p) == h for p, h in pin["protegidos"].items()}
    gravar("integridade_" + args.etapa + ".json", integridade)
    if not all(integridade.values()):
        raise AssertionError("Arquivo protegido mudou")

if __name__ == "__main__":
    main()
