"""C6.2 da correção RAG: as contraprovas da conferência de 25/09 contra o código corrigido.

Importa `reproduzir_achados.py` da conferência SEM alterá-lo e roda cada função
dele; depois roda cada caso sintético dele isoladamente, porque as funções param
no primeiro caso que deixa de reproduzir. Os casos são copiados literalmente de
`artefatos/conferencia_revisao_alcance_geom1_rank03b_2026-09-25/reproduzir_achados.py`.
Só números inventados; o cenário de pin usa diretório temporário e lê o
inventário publicado sem alterá-lo. Não lê valor de FCO.

Execute da raiz: PYTHONPATH=. .venv/bin/python <este arquivo> > <saída>
"""
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re

from scripts import conferir_alcance_geom1_rank03b as c

RAIZ = Path(__file__).resolve().parents[2]
CONFERENCIA = RAIZ / "artefatos/conferencia_revisao_alcance_geom1_rank03b_2026-09-25/reproduzir_achados.py"
CONFERENCIA_SHA256 = "4fdb7f898ece68054bd94cea0f264e02e0d09e697b8b6c62a0d4ad541138eaa9"


def _mascarar(texto: str) -> str:
    return re.sub(r"\d", "#", texto)


def _desfecho(funcao) -> dict:
    try:
        funcao()
    except AssertionError as erro:
        if str(erro).startswith("Contraprova deixou de reproduzir"):
            return {"desfecho": "nao_reproduz", "motivo": _mascarar(str(erro))}
        return {"desfecho": "recusado_pela_guarda", "excecao": type(erro).__name__, "motivo": _mascarar(str(erro))}
    return {"desfecho": "reproduz"}


def main() -> dict:
    if hashlib.sha256(CONFERENCIA.read_bytes()).hexdigest() != CONFERENCIA_SHA256:
        raise AssertionError("contraprovas da conferência diferentes das publicadas")
    especificacao = importlib.util.spec_from_file_location("reproduzir_achados", CONFERENCIA)
    conferencia = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(conferencia)

    funcoes = {nome: _desfecho(getattr(conferencia, nome)) for nome in ("pin_vazio", "parser", "autoverificacao")}

    casos_parser = []
    for nome, texto, valor in [("prefixo_de_numero_malformado", "Total 1.234.5678", "1234567"),
                               ("menos_com_dois_espacos", "Total -  1.234", "1234"),
                               ("parenteses_com_moeda", "Total (R$ 1.234)", "1234")]:
        achados = c.ocorrencias([texto], {"sintetico": Decimal(valor)}, por_modulo=False)["sintetico"]
        casos_parser.append({"caso": nome, "correspondencia_positiva_indevida": bool(achados)})
    controles_parser = {
        "positivo_inteiro_casa": bool(c.ocorrencias(["Total 1.234"], {"a": Decimal(1234)}, por_modulo=False)["a"]),
        "negativo_simples_nao_casa_positivo": not c.ocorrencias(["Total -1.234"], {"a": Decimal(1234)},
                                                                 por_modulo=False)["a"],
    }

    casos_autoverificacao = []
    for texto, valor in [("1.234.567,00", "1234567"), ("1234567.00", "1234567"), ("1 234 567,00", "1234567"),
                         ("1.234.567,50", "1234567.5")]:
        for local in ("texto", "chave"):
            saida = {"nota": texto} if local == "texto" else {texto: True}
            try:
                c.verificar_sem_valores(saida, [Decimal(valor)])
                passou = True
            except c.VazamentoDeValor:
                passou = False
            casos_autoverificacao.append({"representacao": _mascarar(texto), "local": local,
                                          "passou_indevidamente": passou})
    try:
        c.verificar_sem_valores({"nota": "1.234.567"}, [Decimal(1234567)])
        controle_autoverificacao = False
    except c.VazamentoDeValor:
        controle_autoverificacao = True

    return {
        "sentido": "defeitos da conferência de 25/09 contra o código corrigido; 'nao_reproduz' é o esperado",
        "contraprovas_da_conferencia_sha256": CONFERENCIA_SHA256,
        "codigo_sha256": {p: c.rad.sha256(c.rad.RAIZ / p) for p in c.CODIGO},
        "funcoes_da_conferencia": funcoes,
        "casos_rag02": casos_parser, "controles_rag02": controles_parser,
        "casos_rag03": casos_autoverificacao, "controle_rag03_forma_ja_barrada": controle_autoverificacao,
        "nenhum_reproduz": (all(f["desfecho"] != "reproduz" for f in funcoes.values())
                            and not any(x["correspondencia_positiva_indevida"] for x in casos_parser)
                            and not any(x["passou_indevidamente"] for x in casos_autoverificacao)),
        "sem_valores_reais_de_fco": True,
    }


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
