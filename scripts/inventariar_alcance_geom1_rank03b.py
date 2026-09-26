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
#: B1 (auditoria de 25/09): polaridade do caixa sem a expressão "atividades
#: operacionais" ("geração de caixa operacional negativa") também tira o trecho.
#: Vocabulário FECHADO e lexical — reduz o canal, não o fecha.
VOCABULARIO_SEM_TRECHO = re.compile(
    r"\b(?:caixa|fluxos?|operaciona\w*|negativ\w*|positiv\w*|aplicad\w*|consumid\w*|consumo|"
    r"gerad\w*|geracao|deficit|superavit)\b")
_NOMES_DE_SINAL = ("HYPHEN", "DASH", "MINUS", "PLUS SIGN", "PARENTHESIS")
#: B1: código de moeda é a lista da ISO 4217 (vigentes e alguns recentes já
#: retirados), não "três maiúsculas" — que engoliria siglas como FCO ou CDI.
CODIGOS_ISO_4217 = frozenset("""
AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD BTN
BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUC CUP CVE CZK DJF DKK DOP DZD EGP
ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HRK HTG HUF IDR ILS INR IQD IRR
ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD
MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR
PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SLL SOS SRD SSP STN SVC SYP SZL
THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VEF VES VND VUV WST
XAF XAG XAU XBA XBB XBC XBD XCD XCG XDR XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWG ZWL
""".split())


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
def classe_de_moedas() -> str:
    """B1: todo símbolo de moeda (categoria `Sc`), não só `R$` e `US$`."""
    return "".join(c for c in map(chr, range(0x110000)) if unicodedata.category(c) == "Sc")


@lru_cache(maxsize=1)
def _parenteses() -> frozenset[str]:
    return frozenset(c for c in classe_de_sinais() if "PARENTHESIS" in unicodedata.name(c, ""))


@lru_cache(maxsize=1)
def _numero_com_entorno() -> re.Pattern:
    # Sinal, espaço e moeda colados ao número saem junto com ele: `(R$ 123)`
    # não pode deixar o parêntese que diz "negativo". Moeda: símbolo com até
    # três maiúsculas de prefixo (R$, US$, C$) ou código ISO 4217.
    codigos = "|".join(sorted(CODIGOS_ISO_4217))
    moeda = rf"[A-Z]{{0,3}}[{re.escape(classe_de_moedas())}]|\b(?:{codigos})\b"
    entorno = rf"(?:[{re.escape(classe_de_sinais())}\s]|{moeda})*"
    return re.compile(rf"{entorno}\d[\d.,]*{entorno}")


def mascarar(texto):
    # Datas do documento ficam nos metadados; em trechos também são mascaradas.
    sem_numeros, mascarados = _numero_com_entorno().subn(" [valor omitido] ", texto)
    if mascarados:
        # B1: parêntese que sobrou longe do número ("(R$ 1,2 milhão)") ainda
        # diria "negativo".
        sem_numeros = "".join(c for c in sem_numeros if c not in _parenteses())
    return " ".join(sem_numeros.split())


def trecho_publicavel(linha: str) -> dict:
    """O trecho mascarado, ou o motivo de não publicá-lo — a mesma política no
    inventário e na busca numérica (B1)."""
    t = normalizar(linha)
    if any(re.search(PADROES[tipo], t) for tipo in TIPOS_DE_FLUXO):
        return {"trecho_omitido": "linha_de_fluxo"}
    if VOCABULARIO_SEM_TRECHO.search(t):
        return {"trecho_omitido": "vocabulario_de_caixa"}
    return {"trecho": mascarar(linha)}


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
            trecho = trecho_publicavel(linha)
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
