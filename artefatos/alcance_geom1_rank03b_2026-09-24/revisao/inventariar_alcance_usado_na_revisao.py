"""Inventário textual de alcance; NÃO adjudica escala ou ausência de informação.

Contrato de 24/09. Busca auxiliar desenvolvida após reconhecimento das notas;
não é extensão da regra congelada GEOM-1 nem nova avaliação de cobertura.
Não extrai valores contábeis do XML, não faz cálculo de FCO e mascara números.

**R4 (revisão de 24/09):** o sinal é uma CLASSE Unicode, não uma lista de
variantes, e linha de fluxo de caixa não publica trecho — "gerado", "aplicado"
ou "negativo" revelam a polaridade do FCO mesmo com os números mascarados.
O inventário publicado foi gerado pela versão anterior, preservada em
`artefatos/alcance_geom1_rank03b_2026-09-24/revisao/inventariar_alcance_executado.py`.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata

from scripts import fonte_rad_cvm as rad
from scripts.piloto_geometria_rank03b import conferir_protegidos
from scripts.reconhecer_geometria_rank03b import anexos_pdf

BASE = rad.RAIZ / "artefatos/alcance_geom1_rank03b_2026-09-24"
GEOM = rad.RAIZ / "artefatos/escala_geometrica_rank03b_2026-09-18"
PADROES = {
    "ativo_total": r"\b(?:ativo total|total do ativo|total de ativos|ativos totais)\b",
    "atividades_operacionais": r"\batividades operacionais\b",
    "mencao_dfc": r"\b(?:fluxos? de caixa|demonstracao d[oe]s? fluxos?)\b",
}
#: R4: linha que casa um destes tipos não publica trecho em NENHUMA menção,
#: inclusive a declaração de unidade — a restrição é da linha, não do tipo.
TIPOS_DE_FLUXO = frozenset({"atividades_operacionais", "mencao_dfc"})
_NOMES_DE_SINAL = ("HYPHEN", "DASH", "MINUS", "PLUS SIGN", "PARENTHESIS")


def normalizar(texto):
    return " ".join(unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().split())


@lru_cache(maxsize=1)
def classe_de_sinais() -> str:
    """Todo caractere de traço, hífen, menos, mais ou parêntese (R4).

    A versão de 24/09 enumerava `+ - − – — ( )` e deixava passar U+2010,
    U+2011, U+2012, U+FE63 e U+FF0D. Letras e dígitos nunca entram.
    """
    return "".join(
        c for c in map(chr, range(0x110000))
        if unicodedata.category(c)[0] not in "LN"
        and (unicodedata.category(c) == "Pd"
             or any(nome in unicodedata.name(c, "") for nome in _NOMES_DE_SINAL))
    )


@lru_cache(maxsize=1)
def _numero_com_entorno() -> re.Pattern:
    # Sinal, espaço e moeda colados ao número saem junto com ele: `(R$ 123)`
    # não pode deixar o parêntese que diz "negativo".
    entorno = rf"(?:[{re.escape(classe_de_sinais())}\s]|(?:US|R)?\$)*"
    return re.compile(rf"{entorno}\d[\d.,]*{entorno}")


def mascarar(texto):
    # Datas do documento ficam nos metadados; em trechos também são mascaradas.
    sem_numeros = _numero_com_entorno().sub(" [valor omitido] ", texto)
    return " ".join(sem_numeros.split())


def inventariar_texto(texto):
    paginas = texto.split("\f")
    if paginas[-1].strip() == "":
        paginas.pop()
    saida = []
    for n, pagina in enumerate(paginas, 1):
        unidades, mencoes = [], []
        for i, linha in enumerate(pagina.splitlines(), 1):
            t = normalizar(linha)
            tipos = [tipo for tipo, padrao in PADROES.items() if re.search(padrao, t)]
            if TIPOS_DE_FLUXO.intersection(tipos):
                trecho = {"trecho_omitido": "linha_de_fluxo"}
            else:
                trecho = {"trecho": mascarar(linha)}
            if "em milhares de reais" in t:
                unidades.append({"linha": i, **trecho})
            for tipo in tipos:
                mencoes.append({"tipo": tipo, "linha": i, **trecho})
        saida.append({"pagina": n, "declaracoes_de_unidade": unidades, "mencoes": mencoes})
    return saida


def executar():
    pin = json.loads((BASE / "pin.json").read_text())
    contrato = rad.RAIZ / pin["contrato"]
    if rad.sha256(contrato) != pin["contrato_sha256"]:
        raise AssertionError("contrato diferente do pin")
    if rad.sha256(rad.RAIZ / pin["origem"]) != pin["origem_sha256"]:
        raise AssertionError("candidatas diferentes do pin")
    selecao = json.loads((GEOM / "selecao.json").read_text())
    protegido = conferir_protegidos(selecao)
    destino = BASE / "inventario_textual.json"
    pin_execucao = BASE / "pin_execucao.json"
    if destino.exists() or pin_execucao.exists():
        raise FileExistsError("execução já registrada; não sobrescrever")
    versao = subprocess.run(["pdftotext", "-v"], capture_output=True, check=True).stderr.decode().splitlines()[0]
    fontes = [(doc, rad.BRUTOS / f"{doc['id_doc']}.zip") for doc in pin["fontes"]]
    for doc, path in fontes:
        if rad.sha256(path) != doc["sha256"]:
            raise AssertionError("fonte diferente do pin")
    identidade = {"pin_sha256": rad.sha256(BASE / "pin.json"), "poppler": versao,
                  "codigo_sha256": {p: rad.sha256(rad.RAIZ / p) for p in (
                      "scripts/inventariar_alcance_geom1_rank03b.py", "scripts/reconhecer_geometria_rank03b.py",
                      "scripts/piloto_geometria_rank03b.py", "scripts/fonte_rad_cvm.py")},
                  "protegidos_antes": protegido}
    pin_execucao.write_text(json.dumps(identidade, ensure_ascii=False, indent=2) + "\n")
    registros = []
    for doc, path in fontes:
        for indice, grupo, pdf in anexos_pdf(path):
            info = subprocess.run(["pdfinfo", "-"], input=pdf, capture_output=True, check=True).stdout.decode()
            n = int(re.search(r"^Pages:\s+(\d+)$", info, re.M).group(1))
            texto = subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf,
                                   capture_output=True, check=True).stdout.decode()
            paginas = inventariar_texto(texto)
            if len(paginas) != n:
                raise AssertionError("paginação textual não coincide com PDF")
            registros.append({**doc, "anexo": indice, "grupo": grupo,
                              "sha256_pdf": hashlib.sha256(pdf).hexdigest(), "paginas": paginas})
    resultado = {"estado": "inventario_textual_nao_adjudicado", "registros": registros,
                 "limite": "Busca lexical pode perder sinônimos ou texto fragmentado; ausência de match NÃO demonstra ausência da informação.",
                 "protegidos_depois": conferir_protegidos(selecao),
                 "escala_promovida": False, "gates_medidos": False}
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")
    return resultado


if __name__ == "__main__":
    r = executar()
    print(json.dumps({"estado": r["estado"], "anexos": len(r["registros"]),
                      "paginas": sum(len(d["paginas"]) for d in r["registros"])}, ensure_ascii=False))
