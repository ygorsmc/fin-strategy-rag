"""Adendo 2 da correção RAG: rodada de mutação sobre o código e os testes do adendo 2.

Reusa, sem alterar, o harness e o plugin de `../adendo/` (mesma regra: cada trecho
trocado em memória tem de aparecer exatamente uma vez; "morta" = algum teste falhou;
o controle sem mutação passa inteiro). A lista é a do adendo com duas mudanças:
- `gravar_antes_de_verificar` passa a mirar o bloco de gravação novo (B4);
- entram as mutações do B1 (parêntese pelo nome), do B3 (sem DOTALL), do B4
  (serializar depois de gravar) e a vinculação do adendo 2.

Execute da raiz: .venv/bin/python <este arquivo> > <saída>
"""
import importlib.util
import json
from pathlib import Path

ADENDO = Path(__file__).resolve().parents[1] / "adendo" / "verificar_mutacoes.py"

especificacao = importlib.util.spec_from_file_location("harness_do_adendo", ADENDO)
harness = importlib.util.module_from_spec(especificacao)
especificacao.loader.exec_module(harness)

_GRAVAR_ANTES = (
    "gravar_antes_de_verificar", "A7",
    "    _autoverificar(identidade, comparados)\n    _autoverificar(resultado, comparados)\n"
    '    texto_da_identidade = json.dumps(identidade, ensure_ascii=False, indent=2) + "\\n"\n'
    '    texto_do_resultado = json.dumps(resultado, ensure_ascii=False, indent=2) + "\\n"\n'
    "    destino.mkdir(parents=True, exist_ok=True)\n"
    "    pin_revisao.write_text(texto_da_identidade)\n",
    '    texto_da_identidade = json.dumps(identidade, ensure_ascii=False, indent=2) + "\\n"\n'
    "    destino.mkdir(parents=True, exist_ok=True)\n"
    "    pin_revisao.write_text(texto_da_identidade)\n"
    "    _autoverificar(identidade, comparados)\n    _autoverificar(resultado, comparados)\n"
    '    texto_do_resultado = json.dumps(resultado, ensure_ascii=False, indent=2) + "\\n"\n')

NOVAS = [
    ("abre_pelo_nome", "B1", '"abre": frozenset(c for c in sinais if nfkc(c) == "("),',
     '"abre": frozenset(c for c in sinais if "PARENTHESIS" in nome(c) and "LEFT" in nome(c)),'),
    ("fecha_pelo_nome", "B1", '"fecha": frozenset(c for c in sinais if nfkc(c) == ")"),',
     '"fecha": frozenset(c for c in sinais if "PARENTHESIS" in nome(c) and "RIGHT" in nome(c)),'),
    ("sem_dotall", "B3", ", representacao, re.DOTALL)", ", representacao)"),
    ("serializar_depois_de_gravar", "B4",
     '    texto_da_identidade = json.dumps(identidade, ensure_ascii=False, indent=2) + "\\n"\n'
     '    texto_do_resultado = json.dumps(resultado, ensure_ascii=False, indent=2) + "\\n"\n'
     "    destino.mkdir(parents=True, exist_ok=True)\n"
     "    pin_revisao.write_text(texto_da_identidade)\n"
     "    saida_json.write_text(texto_do_resultado)\n",
     "    destino.mkdir(parents=True, exist_ok=True)\n"
     '    pin_revisao.write_text(json.dumps(identidade, ensure_ascii=False, indent=2) + "\\n")\n'
     '    saida_json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\\n")\n'),
    ("adendo2_nao_conferido", "B",
     '        (rad.RAIZ / ADENDO2_CORRECAO, ADENDO2_CORRECAO_SHA256, "adendo 2 da correção RAG"),\n', ""),
]

harness.MUTACOES = [_GRAVAR_ANTES if m[0] == "gravar_antes_de_verificar" else m for m in harness.MUTACOES] + NOVAS

if __name__ == "__main__":
    resultado = harness.main()
    resultado["harness_do_adendo_sha256"] = harness.hashlib.sha256(ADENDO.read_bytes()).hexdigest()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
