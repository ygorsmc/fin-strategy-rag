"""Adendo 3 da correção RAG: rodada de mutação sobre o código e os testes do adendo 3.

Reusa, sem alterar, a lista do adendo 2 (`../adendo2/verificar_mutacoes.py`, que reusa
o harness e o plugin de `../adendo/`) e acrescenta a vinculação do adendo 3 e um
`limite` incompleto — que o teste de caracterização tem de derrubar.

Execute da raiz: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <este arquivo> > <saída>
"""
import importlib.util
import json
from pathlib import Path

ADENDO2 = Path(__file__).resolve().parents[1] / "adendo2" / "verificar_mutacoes.py"
especificacao = importlib.util.spec_from_file_location("harness_do_adendo2", ADENDO2)
anterior = importlib.util.module_from_spec(especificacao)
especificacao.loader.exec_module(anterior)
harness = anterior.harness

harness.MUTACOES = harness.MUTACOES + [
    ("adendo3_nao_conferido", "adendo3",
     '        (rad.RAIZ / ADENDO3_CORRECAO, ADENDO3_CORRECAO_SHA256, "adendo 3 da correção RAG"),\n', ""),
    ("limite_sem_o_prefixo", "adendo3", "parte o token, e o prefixo pode casar. ", "parte o token. "),
]

if __name__ == "__main__":
    resultado = harness.main()
    resultado["harness_do_adendo2_sha256"] = harness.hashlib.sha256(ADENDO2.read_bytes()).hexdigest()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
