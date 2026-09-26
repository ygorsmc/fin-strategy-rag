"""A1 do adendo da correção RAG: retirar cada checagem derruba ao menos um teste.

Cada mutação troca UM trecho do código da busca, em memória (`mutacao_plugin.py`),
e roda o arquivo de testes da busca. "Morta" = algum teste falhou. O controle roda
o mesmo caminho sem mutação e tem de passar inteiro. Nada no repositório é editado.

Execute da raiz: .venv/bin/python <este arquivo> > <saída>
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

RAIZ = Path(__file__).resolve().parents[3]
CODIGO = RAIZ / "scripts/conferir_alcance_geom1_rank03b.py"
TESTES = "tests/test_conferir_alcance_geom1_rank03b.py"
AQUI = Path(__file__).resolve().parent

MUTACOES = [
    # C1/A1 — estrutura do pin
    ("pin_nao_vazio", "C1", "if not isinstance(fontes, list) or not fontes:", "if not isinstance(fontes, list):"),
    ("pin_id_numerico", "C1", 'and isinstance(fonte.get("id_doc"), str) and re.fullmatch(r"[0-9]+", fonte["id_doc"])',
     'and isinstance(fonte.get("id_doc"), str)'),
    ("pin_hash_bem_formado", "C1", 'and isinstance(fonte.get("sha256"), str) and _SHA256.fullmatch(fonte["sha256"]))',
     'and isinstance(fonte.get("sha256"), str))'),
    ("pin_id_repetido", "C1", 'for campo in ("id_doc", "sha256"):', 'for campo in ("sha256",):'),
    ("pin_hash_repetido", "C1", 'for campo in ("id_doc", "sha256"):', 'for campo in ("id_doc",):'),
    # C1 — vinculação por hash e universo
    ("pin_de_alcance_nao_conferido", "C1", '(BASE / "pin.json", PIN_ALCANCE_SHA256, "pin de alcance"),',
     '(BASE / "pin.json", hashlib.sha256((BASE / "pin.json").read_bytes()).hexdigest(), "pin de alcance"),'),
    ("pin_de_execucao_nao_conferido", "C1",
     '(BASE / "pin_execucao.json", PIN_EXECUCAO_SHA256, "pin de execução do inventário"),',
     '(BASE / "pin_execucao.json", hashlib.sha256((BASE / "pin_execucao.json").read_bytes()).hexdigest(), '
     '"pin de execução do inventário"),'),
    ("selecao_nao_conferida", "C1", '(GEOM / "selecao.json", SELECAO_SHA256, "seleção GEOM-1"),',
     '(GEOM / "selecao.json", hashlib.sha256((GEOM / "selecao.json").read_bytes()).hexdigest(), "seleção GEOM-1"),'),
    ("adendo_da_correcao_nao_conferido", "C1",
     '(rad.RAIZ / ADENDO_CORRECAO, ADENDO_CORRECAO_SHA256, "adendo da correção RAG"),', ""),
    ("pin_de_execucao_de_outro_pin", "C1", 'if execucao.get("pin_sha256") != PIN_ALCANCE_SHA256:', "if False:"),
    ("pin_da_revisao_de_outro_universo", "C1",
     'if pin_revisao.get("pin_alcance_sha256") != PIN_ALCANCE_SHA256 or pin_revisao.get("fontes") != fontes:',
     "if False:"),
    ("universo_com_repeticao", "C1", "if len(set(ids)) != len(ids):", "if False:"),
    ("universo_diferente", "C1", 'if ids != [f["id_doc"] for f in fontes]:', "if False:"),
    ("autoverificacao_vazia", "C1", "if not any(abs(Decimal(v)) >= 1000 for v in valores):", "if False:"),
    ("identidade_sem_autoverificacao", "C3", "    _autoverificar(identidade, comparados)\n", ""),
    ("hash_da_fonte", "C1", 'if hashlib.sha256(dados).hexdigest() != doc["sha256"]:', "if False:"),
    # A6 — versão e leitura única
    ("versao_do_inventario", "A6",
     'if (registro.get("sha256") != por_id[registro["id_doc"]]["sha256"]\n'
     '                or registro.get("sha256_pdf") != pacote.pdf_sha256):', "if False:"),
    ("versao_da_conferencia", "A6",
     'if documento.get("xml_sha256") != pacote.xml_sha256 or documento.get("pdf_sha256") != pacote.pdf_sha256:',
     "if False:"),
    ("pacote_relido_do_disco", "A6", "copias = conferir_fontes(fontes, rad.BRUTOS, copiar_para=Path(pasta))",
     'conferir_fontes(fontes, rad.BRUTOS); copias = {d["id_doc"]: rad.BRUTOS / f"{d[\'id_doc\']}.zip" '
     "for d in fontes}"),
    # A7 — nada gravado antes das recusas
    ("gravar_antes_de_verificar", "A7",
     "    _autoverificar(identidade, comparados)\n    _autoverificar(resultado, comparados)\n"
     "    destino.mkdir(parents=True, exist_ok=True)\n"
     '    pin_revisao.write_text(json.dumps(identidade, ensure_ascii=False, indent=2) + "\\n")\n',
     "    destino.mkdir(parents=True, exist_ok=True)\n"
     '    pin_revisao.write_text(json.dumps(identidade, ensure_ascii=False, indent=2) + "\\n")\n'
     "    _autoverificar(identidade, comparados)\n    _autoverificar(resultado, comparados)\n"),
    # C2/A2–A4 — token e sinal
    ("gramatica_do_token", "C2", "elif not _GRAMATICA_PTBR.fullmatch(texto):", "elif False:"),
    ("separador_a_esquerda", "C2", 'elif inicio > 0 and linha[inicio - 1] in ".,":', "elif False:"),
    ("invisivel_no_token", "A2",
     r"""    return re.compile(rf"\d(?:[.,{re.escape(''.join(sorted(_classes()['invisiveis'])))}]*\d)*")""",
     r"""    return re.compile(r"\d+(?:[.,]\d+)*")"""),
    ("invisivel_no_contexto", "A2", '    if invisivel_esq or invisivel_dir:\n        return None, "invisivel_no_contexto"\n',
     ""),
    ("menos_pelo_nome", "A3",
     r'"menos": frozenset(c for c in sinais if unicodedata.category(c) == "Pd" or nfkc(c) == "\u2212"),',
     r'"menos": frozenset(c for c in sinais if unicodedata.category(c) == "Pd"'
     r' or ("MINUS" in nome(c) and "PLUS" not in nome(c))),'),
    ("mais_pelo_nome", "A3", '"mais": frozenset(c for c in sinais if nfkc(c) == "+"),',
     '"mais": frozenset(c for c in sinais if "PLUS SIGN" in nome(c) and "MINUS" not in nome(c)),'),
    ("outro_sinal_vira_positivo", "A3", '    if tipo == "outro":\n        return None, "outro_sinal"\n', ""),
    ("fecha_qualquer_nao_encerra", "A3", 'elif ch in k["fecha_amplo"] or ch not in k["sinais"]:',
     'elif ch not in k["sinais"]:'),
    ("abre_depois_do_token_vira_sinal", "A3", ' and seguinte not in k["abre_amplo"]', ""),
    ("sinal_depois_seguido_de_digito", "A4",
     'sinal_depois = bool(seguinte) and seguinte in k["sinais"] and seguinte not in k["abre_amplo"]',
     'sinal_depois = bool(seguinte) and seguinte in k["sinais"] and seguinte not in k["abre_amplo"]'
     " and not resto[j + 1:j + 2].isdigit()"),
    ("sinal_seguido_de_espaco", "C2", '    if espaco:\n        return None, "sinal_seguido_de_espaco"\n', ""),
    ("fecha_sem_abre", "C2", '        return (None, "fecha_sem_abre") if fecha else (1, "limpo")',
     '        return 1, "limpo"'),
    ("colado_a_palavra", "C2", '    if colado:\n        return None, "colado_a_palavra"\n', ""),
    ("varios_sinais", "C2", '    if len(nucleo) != 1:\n        return None, "varios_sinais"\n', ""),
    # C3/A5 — autoverificação
    ("isencao_pelo_nome", "C3",
     'if (isencao == "hash" and _SHA256.fullmatch(obj)) or (isencao == "data" and _DATA_ISO.fullmatch(obj)):',
     "if isencao:"),
    ("sem_piso_e_teto", "C3",
     "            protegidas |= {modulo.to_integral_value(rounding=ROUND_FLOOR),\n"
     "                           modulo.to_integral_value(rounding=ROUND_CEILING)}", "            pass"),
    ("chave_nao_varrida", "C3", "if contem(str(k)):  # B1: a chave também é publicada", "if False:"),
    ("tipo_nao_previsto_ignorado", "C3",
     'raise TypeError(f"tipo não previsto na autoverificação: {type(obj).__name__}")', "return"),
    ("mensagem_com_digito", "C3", r'return "raiz" if chave is None else re.sub(r"\d", "#", str(chave))[:80]',
     'return "raiz" if chave is None else str(chave)[:80]'),
    ("trecho_com_digito", "C3", r'if chave == "trecho" and re.search(r"\d", obj):', "if False:"),
    ("numero_grande", "C3", "            if abs(obj) >= 1000:", "            if False:"),
    ("sem_nfkc", "A5", 'normalizado = unicodedata.normalize("NFKC", texto)', "normalizado = texto"),
    ("invisivel_no_publicado", "A5",
     '    return "".join(ch for ch in normalizado\n'
     '                   if not (unicodedata.category(ch) in ("Cf", "Cc") and not ch.isspace()))',
     "    return normalizado"),
    ("separador_so_espacos", "A5", r'separador = rf"(?:[^\w.,]|[_{re.escape(modificadoras)}])"',
     r'separador = r"[ \u00a0\u202f\u2009]"'),
    ("mantissa_so_com_expoente", "A5",
     '    if m["expoente"]:\n        leituras |= {d.scaleb(int(m["expoente"])) for d in leituras}',
     '    if m["expoente"]:\n        return {d.scaleb(int(m["expoente"])) for d in leituras}'),
]


def _rodar(identificador: str, antigo: str, novo: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="mutacao_") as pasta:
        arquivo = Path(pasta) / "mutacao.json"
        arquivo.write_text(json.dumps({"id": identificador, "antigo": antigo, "novo": novo}))
        ambiente = {**os.environ, "MUTACAO_ARQUIVO": str(arquivo), "PYTHONPATH": f"{RAIZ}:{AQUI}",
                    "PYTHONDONTWRITEBYTECODE": "1", "CREWAI_STORAGE_DIR": str(Path(pasta) / "crewai")}
        feito = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                "-p", "mutacao_plugin", TESTES], cwd=RAIZ, env=ambiente,
                               capture_output=True, text=True)
    resumo = (feito.stdout.strip().splitlines() or [""])[-1]
    falhas = int(m.group(1)) if (m := re.search(r"(\d+) failed", resumo)) else 0
    passaram = int(m.group(1)) if (m := re.search(r"(\d+) passed", resumo)) else 0
    erro = feito.returncode not in (0, 1) or ("error" in resumo and not falhas)
    return {"falhas": falhas, "passaram": passaram, "erro_de_execucao": erro,
            "resumo": re.sub(r"\d+\.\d+s", "", resumo).strip()}


def main() -> dict:
    fonte = CODIGO.read_text()
    for identificador, _, antigo, _ in MUTACOES:
        if fonte.count(antigo) != 1:
            raise AssertionError(f"mutação {identificador}: trecho não aparece exatamente uma vez no código")
    controle = _rodar("controle", "", "")
    if controle["falhas"] or controle["erro_de_execucao"] or not controle["passaram"]:
        raise AssertionError(f"controle sem mutação não passou: {controle['resumo']}")
    resultados = []
    for identificador, regra, antigo, novo in MUTACOES:
        r = _rodar(identificador, antigo, novo)
        resultados.append({"id": identificador, "regra": regra, "morta": r["falhas"] > 0 and not r["erro_de_execucao"],
                           **r})
    return {"sentido": "cada checagem retirada em memória; 'morta' = ao menos um teste da busca falhou",
            "codigo_sha256": hashlib.sha256(CODIGO.read_bytes()).hexdigest(),
            "testes_sha256": hashlib.sha256((RAIZ / TESTES).read_bytes()).hexdigest(),
            "plugin_sha256": hashlib.sha256((AQUI / "mutacao_plugin.py").read_bytes()).hexdigest(),
            "controle": controle, "mutacoes": resultados,
            "todas_mortas": all(r["morta"] for r in resultados),
            "sobreviventes": [r["id"] for r in resultados if not r["morta"]]}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
