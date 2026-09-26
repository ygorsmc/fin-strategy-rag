"""Revisão do alcance GEOM-1: busca numérica exata nas notas; NÃO adjudica escala.

Contrato: resultados/contratos_revisao_alcance_geom1_rank03b_2026-09-24.md
(R3 e R4). Compara em memória valores do XML com os números impressos nas notas
(grupos 193/412) do mesmo pacote, nas fontes fixadas no pin de 24/09. XML lido
direto, sem o leitor do painel nem o replay GEOM. O FCO só é comparado em
memória (O1): o artefato publica páginas, nunca montante ou sinal, e uma
autoverificação recusa gravar saída que contenha algum valor comparado.
"Sem correspondência" vale para estas notas, não para outra fonte.

**Adendo de 25/09 (pós-auditoria):** trecho do ativo segue a política do
inventário; autoverificação estrita (chaves, milhar com espaço, só hash e data
isentos); texto ilegível derruba. A execução de 24/09 foi feita pela versão
anterior, preservada em
`artefatos/alcance_geom1_rank03b_2026-09-24/revisao/conferir_alcance_executado.py`.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

from scripts import fonte_rad_cvm as rad
from scripts.inventariar_alcance_geom1_rank03b import (TIPOS_DE_FLUXO, classe_de_sinais, inventariar_texto,
                                                       trecho_publicavel)
from scripts.piloto_geometria_rank03b import conferir_protegidos
from scripts.reconhecer_geometria_rank03b import anexos_pdf

BASE = rad.RAIZ / "artefatos/alcance_geom1_rank03b_2026-09-24"
GEOM = rad.RAIZ / "artefatos/escala_geometrica_rank03b_2026-09-18"
DESTINO = BASE / "revisao"
CONTRATO = "resultados/contratos_revisao_alcance_geom1_rank03b_2026-09-24.md"
#: Hash do inventário publicado, registrado pelo auditor em parecer_auditor.json.
INVENTARIO_PUBLICADO_SHA256 = "4bb25cf08b87843c0ccab5610415e49284d306f04307818059b15960716c84b3"
MODOS = ("-layout", "-raw")
CODIGO = ("scripts/conferir_alcance_geom1_rank03b.py", "scripts/inventariar_alcance_geom1_rank03b.py",
          "scripts/reconhecer_geometria_rank03b.py", "scripts/piloto_geometria_rank03b.py",
          "scripts/fonte_rad_cvm.py")
BP, DFC = "BalancoPatrimonialAtivo", "DemonstracaoFluxoCaixa"
CONS, IND = "DfConsolidadas", "DfIndividuais"
#: Fora da autoverificação só ficam campos de DATA e todo campo cujo nome termina em
#: `sha256` — o que o contrato R3 diz. B1 (25/09): a versão executada em 24/09 isentava
#: também caminho, versão e chaves de documento, com as subárvores.
CHAVES_LIVRES = frozenset({"data", "dt_refer"})
#: Menos que isso numa página é "pouco texto": publicado para qualificar a busca.
MINIMO_DE_CARACTERES = 40
DESTINO_RECONFERENCIA = DESTINO / "reconferencia_pos_auditoria.json"
ADENDO = "resultados/adendo_revisao_alcance_geom1_rank03b_2026-09-25.md"
#: GEOM-1 e leitor de fonte não podem ter mudado desde a execução de 24/09.
CODIGO_CONGELADO = ("scripts/reconhecer_geometria_rank03b.py", "scripts/piloto_geometria_rank03b.py",
                    "scripts/fonte_rad_cvm.py")

_XML_PTBR = re.compile(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")


class VazamentoDeValor(AssertionError):
    """A saída carrega um valor comparado — não grava."""


def decimal_ptbr(texto: str) -> Decimal:
    """Número do XML da CVM (milhar com ponto, decimal com vírgula).

    A mensagem de erro nunca repete o texto: o campo pode ser de FCO (O1).
    """
    s = (texto or "").strip()
    if not _XML_PTBR.fullmatch(s):
        raise ValueError("número fora do formato pt-BR (valor omitido)")
    try:
        d = Decimal(s.lstrip("-").replace(".", "").replace(",", "."))
    except InvalidOperation:  # pragma: no cover — o fullmatch já garante o formato
        raise ValueError("número ilegível (valor omitido)") from None
    return -d if s.startswith("-") else d


@lru_cache(maxsize=1)
def _tracos() -> frozenset[str]:
    """Sinais que negam: traço (Pd) ou menos. `+` e `±` não negam."""
    return frozenset(c for c in classe_de_sinais()
                     if unicodedata.category(c) == "Pd"
                     or ("MINUS" in unicodedata.name(c, "") and "PLUS" not in unicodedata.name(c, "")))


@lru_cache(maxsize=1)
def _padrao_do_pdf() -> re.Pattern:
    sinais = re.escape("".join(c for c in classe_de_sinais() if "PARENTHESIS" not in unicodedata.name(c, "")))
    return re.compile(rf"([(\uff08\ufe59]?)\s?([{sinais}]?)\s?(\d{{1,3}}(?:\.\d{{3}})+(?:,\d+)?|\d+(?:,\d+)?)"
                      rf"\s?([)\uff09\ufe5a]?)")


def numeros_da_linha(linha: str) -> list[tuple[int, Decimal]]:
    """[(coluna, valor)] na ordem da linha; parênteses ou traço/menos = negativo."""
    saida = []
    for coluna, (abre, sinal, digitos, fecha) in enumerate(_padrao_do_pdf().findall(linha), 1):
        v = Decimal(digitos.replace(".", "").replace(",", "."))
        negativo = bool(abre and fecha) or sinal in _tracos()
        saida.append((coluna, -v if negativo else v))
    return saida


def ocorrencias(paginas: list[str], alvos: dict[str, Decimal], *, por_modulo: bool) -> dict[str, list[dict]]:
    """Onde cada alvo aparece. Zero nunca é procurado: zero não prova escala."""
    achados: dict[str, list[dict]] = {nome: [] for nome in alvos}
    for p, pagina in enumerate(paginas, 1):
        for n, linha in enumerate(pagina.splitlines(), 1):
            numeros = numeros_da_linha(linha)
            for nome, alvo in alvos.items():
                if alvo == 0:
                    continue
                for coluna, v in numeros:
                    if (abs(v) == abs(alvo)) if por_modulo else (v == alvo):
                        achados[nome].append({"pagina": p, "linha": n, "coluna": coluna,
                                              "tokens": len(numeros), "texto": linha})
    return achados


def publicar_ativo(achados: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """B1: o trecho segue a mesma política do inventário (linha de fluxo ou de
    vocabulário de caixa não publica trecho)."""
    return {nome: [{"pagina": a["pagina"], "linha": a["linha"], "coluna": a["coluna"],
                    "tokens": a["tokens"], **trecho_publicavel(a["texto"])} for a in lista]
            for nome, lista in achados.items()}


def publicar_fco(achados: dict[str, list[dict]]) -> dict[str, list[int]]:
    """Só páginas: nem coluna, nem linha, nem trecho (O1)."""
    return {nome: sorted({a["pagina"] for a in lista}) for nome, lista in achados.items()}


def _formas(a: Decimal) -> set[str]:
    inteiro = int(a)
    # B1: milhar com ponto, espaço, espaço inseparável, espaço fino ou vírgula.
    formas = {f"{inteiro:,}".replace(",", sep) for sep in (".", " ", "\u00a0", "\u202f", ",")}
    formas.add(str(inteiro))
    if a != inteiro:
        fracao = format(a, "f").split(".")[1].rstrip("0")
        formas |= {f"{f}{sep}{fracao}" for f in list(formas) for sep in (",", ".")}
    return formas


def verificar_sem_valores(saida, valores) -> None:
    """Recusa a saída se algum valor comparado (módulo >= 1.000) estiver nela."""
    formas = set()
    for v in valores:
        if abs(v) >= 1000:
            formas |= _formas(abs(v))
    padroes = [re.compile(rf"(?<![\d.,]){re.escape(f)}(?![\d]|[.,]\d)") for f in formas]

    def visita(obj, chave=None):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if any(p.search(str(k)) for p in padroes):  # B1: a chave também é publicada
                    raise VazamentoDeValor("valor comparado publicado como nome de campo")
                if k in CHAVES_LIVRES or str(k).endswith("sha256"):
                    continue
                visita(v, k)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                visita(v, chave)
        elif isinstance(obj, bool) or obj is None:
            return
        elif isinstance(obj, (int, float, Decimal)):
            if abs(obj) >= 1000:
                raise VazamentoDeValor(f"número >= 1.000 publicado em {chave!r}")
        elif isinstance(obj, str):
            if chave == "trecho" and re.search(r"\d", obj):
                raise VazamentoDeValor("dígito em trecho publicado")
            if any(p.search(obj) for p in padroes):
                raise VazamentoDeValor(f"valor comparado publicado em {chave!r}")
    visita(saida)


def formulario(pacote: Path):
    nome = rad.validar_pacote(pacote)
    if not rad.XML_UNICO.fullmatch(nome):
        raise ValueError("formato de pacote não previsto nesta revisão")
    with zipfile.ZipFile(pacote) as z:
        dados = z.read(nome)
    raiz = ET.fromstring(dados)
    cabecalho = raiz.find(rad.RAIZES_XML_UNICO[raiz.tag])
    return nome, hashlib.sha256(dados).hexdigest(), cabecalho.find("Formulario"), cabecalho.findtext("EscalaMoeda")


def valor_xml(form, perimetro: str, bloco: str, conta: str, campo: str) -> Decimal:
    contas = [c for c in form.find(f"{perimetro}/{bloco}").iter("Conta")
              if (c.findtext("CodigoConta") or "").strip() == conta]
    if len(contas) != 1:
        raise ValueError(f"{perimetro}/{bloco}/{conta}: {len(contas)} contas com esse código")
    texto = contas[0].findtext(campo)
    if texto is None:
        raise ValueError(f"{perimetro}/{bloco}/{conta}/{campo} ausente")
    return decimal_ptbr(texto)


def alvos_ativo(form) -> dict[str, Decimal]:
    t = valor_xml(form, CONS, BP, "1", "TrimestreAtual")
    return {"consolidado_corrente": t,
            "consolidado_comparativo": valor_xml(form, CONS, BP, "1", "ExercicioAnterior"),
            "individual_corrente": valor_xml(form, IND, BP, "1", "TrimestreAtual"),
            "individual_comparativo": valor_xml(form, IND, BP, "1", "ExercicioAnterior"),
            "consolidado_corrente_vezes_mil": t * 1000, "consolidado_corrente_sobre_mil": t / 1000}


def alvos_fco(form) -> dict[str, Decimal]:
    f = valor_xml(form, CONS, DFC, "6.01", "AcumuladoAtualExercicio")
    return {"consolidado_acumulado_corrente": f,
            "consolidado_acumulado_anterior": valor_xml(form, CONS, DFC, "6.01", "AcumuladoExercicioAnterior"),
            "individual_acumulado_corrente": valor_xml(form, IND, DFC, "6.01", "AcumuladoAtualExercicio"),
            "consolidado_corrente_vezes_mil": f * 1000, "consolidado_corrente_sobre_mil": f / 1000}


def saldos_de_caixa(form) -> tuple[Decimal, Decimal]:
    """Saldo final de caixa da DFC e caixa do balanço, em bruto. Não envolve 6.01."""
    return (valor_xml(form, CONS, DFC, "6.05.02", "AcumuladoAtualExercicio"),
            valor_xml(form, CONS, BP, "1.01.01", "TrimestreAtual"))


def exigir_texto_legivel(paginas: list[str]) -> None:
    """B2: glifo sem mapa (`(cid:`) ou caractere de substituição derrubam a
    execução — senão virariam "sem correspondência" em silêncio (§3.3, BTG)."""
    ilegiveis = [n for n, pagina in enumerate(paginas, 1) if "(cid:" in pagina or "\ufffd" in pagina]
    if ilegiveis:
        raise AssertionError(f"texto ilegível nas páginas {ilegiveis}")


def paginas_com_pouco_texto(paginas: list[str]) -> list[int]:
    return [n for n, pagina in enumerate(paginas, 1)
            if len("".join(pagina.split())) < MINIMO_DE_CARACTERES]


def paginas_pdf(pdf: bytes, modo: str) -> list[str]:
    info = subprocess.run(["pdfinfo", "-"], input=pdf, capture_output=True, check=True).stdout.decode()
    n = int(re.search(r"^Pages:\s+(\d+)$", info, re.M).group(1))
    texto = subprocess.run(["pdftotext", modo, "-", "-"], input=pdf, capture_output=True, check=True).stdout.decode()
    paginas = texto.split("\f")
    if paginas and paginas[-1].strip() == "":
        paginas.pop()
    if len(paginas) != n:
        raise AssertionError("paginação textual não coincide com o PDF")
    return paginas


def comparar_inventarios(publicado: list[dict], novo: list[dict]) -> dict[str, int]:
    """R4: a regra nova só pode diferir do publicado retirando trecho de linha de fluxo."""
    retirados = inesperadas = comparados = 0
    if [p["pagina"] for p in publicado] != [p["pagina"] for p in novo]:
        return {"registros_comparados": 0, "trechos_retirados_por_fluxo": 0, "diferencas_inesperadas": 1}
    for antigo, atual in zip(publicado, novo):
        # A omissão só é legítima na linha que tem menção de fluxo (R4: restrição da linha).
        de_fluxo = {m["linha"] for m in atual["mencoes"] if m["tipo"] in TIPOS_DE_FLUXO}
        for campo in ("declaracoes_de_unidade", "mencoes"):
            a, b = antigo[campo], atual[campo]
            comparados += len(b)
            if len(a) != len(b):
                inesperadas += 1
                continue
            for x, y in zip(a, b):
                if y.get("trecho_omitido") == "linha_de_fluxo" and "trecho" in x and y["linha"] in de_fluxo:
                    x = {k: v for k, v in x.items() if k != "trecho"}
                    y = {k: v for k, v in y.items() if k != "trecho_omitido"}
                    retirados += 1
                inesperadas += x != y
    return {"registros_comparados": comparados, "trechos_retirados_por_fluxo": retirados,
            "diferencas_inesperadas": inesperadas}


def _sem_trecho(registro: dict) -> dict:
    return {k: v for k, v in registro.items() if k not in ("trecho", "trecho_omitido")}


def efeito_da_politica(publicado: list[dict], novo: list[dict]) -> dict[str, int]:
    """Adendo de 25/09: como a política de trecho nova trata cada registro publicado."""
    contagem = dict.fromkeys(("registros", "trecho_identico", "trecho_alterado", "omitido_por_fluxo",
                              "omitido_por_vocabulario", "estrutura_diferente"), 0)
    if [p["pagina"] for p in publicado] != [p["pagina"] for p in novo]:
        contagem["estrutura_diferente"] += 1
        return contagem
    for antigo, atual in zip(publicado, novo):
        for campo in ("declaracoes_de_unidade", "mencoes"):
            if len(antigo[campo]) != len(atual[campo]):
                contagem["estrutura_diferente"] += 1
                continue
            for x, y in zip(antigo[campo], atual[campo]):
                contagem["registros"] += 1
                if _sem_trecho(x) != _sem_trecho(y):
                    contagem["estrutura_diferente"] += 1
                elif "trecho" in y:
                    contagem["trecho_identico" if y["trecho"] == x.get("trecho") else "trecho_alterado"] += 1
                elif y["trecho_omitido"] == "linha_de_fluxo":
                    contagem["omitido_por_fluxo"] += 1
                else:
                    contagem["omitido_por_vocabulario"] += 1
    return contagem


def _posicoes(modo: dict) -> tuple:
    """O que os dois extratores têm de concordar: páginas/colunas do ativo, páginas do FCO."""
    return ({k: [(a["pagina"], a["coluna"]) for a in v] for k, v in modo["ativo"].items()},
            modo["fco_paginas"])


def conferir_fontes(fontes: list[dict], brutos: Path) -> None:
    for doc in fontes:
        if rad.sha256(brutos / f"{doc['id_doc']}.zip") != doc["sha256"]:
            raise AssertionError("fonte diferente do pin de 24/09")


def executar(destino: Path = DESTINO) -> dict:
    pin_revisao, saida_json = destino / "pin_revisao.json", destino / "conferencia_revisao.json"
    if pin_revisao.exists() or saida_json.exists():
        raise FileExistsError("revisão já registrada; não sobrescrever")
    pin = json.loads((BASE / "pin.json").read_text())
    if rad.sha256(BASE / "inventario_textual.json") != INVENTARIO_PUBLICADO_SHA256:
        raise AssertionError("inventário publicado diferente do conferido pelo auditor")
    conferir_fontes(pin["fontes"], rad.BRUTOS)
    executado = json.loads((BASE / "pin_execucao.json").read_text())["codigo_sha256"]
    if any(rad.sha256(rad.RAIZ / p) != executado[p] for p in CODIGO_CONGELADO):
        raise AssertionError("código GEOM-1 ou leitor de fonte mudou desde 24/09")
    selecao = json.loads((GEOM / "selecao.json").read_text())
    versao = subprocess.run(["pdftotext", "-v"], capture_output=True, check=True).stderr.decode().splitlines()[0]
    identidade = {
        "data": "2026-09-24", "contrato": CONTRATO, "contrato_sha256": rad.sha256(rad.RAIZ / CONTRATO),
        "pin_alcance_sha256": rad.sha256(BASE / "pin.json"),
        "inventario_publicado_sha256": INVENTARIO_PUBLICADO_SHA256, "poppler": versao,
        "codigo_sha256": {p: rad.sha256(rad.RAIZ / p) for p in CODIGO},
        "fontes": pin["fontes"], "protegidos_antes": conferir_protegidos(selecao),
        "exposicao": ("Busca executada uma vez durante a revisão, em memória e sem contrato; "
                      "resultados conhecidos antes deste pin. Não é teste cego."),
    }
    destino.mkdir(parents=True, exist_ok=True)
    pin_revisao.write_text(json.dumps(identidade, ensure_ascii=False, indent=2) + "\n")

    publicado = {r["id_doc"]: r for r in json.loads((BASE / "inventario_textual.json").read_text())["registros"]}
    comparados, documentos = [], []
    for doc in pin["fontes"]:
        nome, sha_xml, form, escala = formulario(rad.BRUTOS / f"{doc['id_doc']}.zip")
        ativo, fco, caixa = alvos_ativo(form), alvos_fco(form), saldos_de_caixa(form)
        comparados += [*ativo.values(), *fco.values(), *caixa]
        (indice, grupo, pdf), = anexos_pdf(rad.BRUTOS / f"{doc['id_doc']}.zip")
        por_modo = {}
        for modo in MODOS:
            paginas = paginas_pdf(pdf, modo)
            exigir_texto_legivel(paginas)
            por_modo[modo] = {"paginas": len(paginas), "paginas_com_pouco_texto": paginas_com_pouco_texto(paginas),
                              "ativo": publicar_ativo(ocorrencias(paginas, ativo, por_modulo=False)),
                              "fco_paginas": publicar_fco(ocorrencias(paginas, fco, por_modulo=True))}
        novo = inventariar_texto(subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf,
                                                capture_output=True, check=True).stdout.decode())
        documentos.append({
            "id_doc": doc["id_doc"], "nome_xml": nome, "xml_sha256": sha_xml, "escala_moeda_codigo": escala,
            "anexo": indice, "grupo": grupo, "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
            "modos": por_modo,
            "modos_concordam": _posicoes(por_modo["-layout"]) == _posicoes(por_modo["-raw"]),
            "identidade_saldo_final_dfc_igual_caixa_bp": caixa[0] == caixa[1],
            "reinventario_mascara_r4": comparar_inventarios(publicado[doc["id_doc"]]["paginas"], novo),
        })
    resultado = {
        "estado": "busca_numerica_exata_nao_adjudica",
        "documentos": documentos,
        "limite": ("Sem correspondência vale só para estas notas e para números no formato pt-BR com "
                   "ponto de milhar; não demonstra ausência em outra fonte. A identidade de caixa não "
                   "envolve 6.01 e não prova a escala do FCO."),
        "protegidos_depois": conferir_protegidos(selecao),
        "escala_promovida": False, "gates_medidos": False,
    }
    verificar_sem_valores(resultado, comparados)
    saida_json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")
    return resultado


def reconferir_publicados(destino: Path = DESTINO_RECONFERENCIA) -> dict:
    """Adendo de 25/09: os artefatos já publicados sob as regras novas.

    Não regrava nada de 24/09. Relê fontes e XML em memória, como a execução;
    publica só booleanos, contagens e páginas.
    """
    if destino.exists():
        raise FileExistsError("reconferência já registrada; não sobrescrever")
    pin = json.loads((BASE / "pin.json").read_text())
    conferir_fontes(pin["fontes"], rad.BRUTOS)
    publicados = {nome: json.loads((DESTINO / nome).read_text())
                  for nome in ("conferencia_revisao.json", "pin_revisao.json")}
    inventario = {r["id_doc"]: r["paginas"]
                  for r in json.loads((BASE / "inventario_textual.json").read_text())["registros"]}
    comparados, documentos = [], []
    for doc in pin["fontes"]:
        pacote = rad.BRUTOS / f"{doc['id_doc']}.zip"
        _, _, form, _ = formulario(pacote)
        comparados += [*alvos_ativo(form).values(), *alvos_fco(form).values(), *saldos_de_caixa(form)]
        (_, _, pdf), = anexos_pdf(pacote)
        executado = next(d for d in publicados["conferencia_revisao.json"]["documentos"]
                         if d["id_doc"] == doc["id_doc"])
        qualidade, trechos = {}, {"mantidos": 0, "diferentes": 0}
        for modo in MODOS:
            paginas = paginas_pdf(pdf, modo)
            qualidade[modo] = {
                "texto_ilegivel": any("(cid:" in p or "\ufffd" in p for p in paginas),
                "paginas_com_pouco_texto": paginas_com_pouco_texto(paginas)}
            for lista in executado["modos"][modo]["ativo"].values():
                for a in lista:
                    linha = paginas[a["pagina"] - 1].splitlines()[a["linha"] - 1]
                    trechos["mantidos" if trecho_publicavel(linha) == {"trecho": a["trecho"]} else "diferentes"] += 1
        novo = inventariar_texto(subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf,
                                                capture_output=True, check=True).stdout.decode())
        documentos.append({"id_doc": doc["id_doc"], "qualidade_do_texto": qualidade,
                           "trechos_do_ativo_sob_a_politica_nova": trechos,
                           "inventario_sob_a_politica_nova": efeito_da_politica(inventario[doc["id_doc"]], novo)})
    autoverificacao = {}
    for nome, conteudo in publicados.items():
        try:
            verificar_sem_valores(conteudo, comparados)
            autoverificacao[nome] = True
        except VazamentoDeValor:
            autoverificacao[nome] = False
    resultado = {
        "data": "2026-09-25", "adendo": ADENDO, "adendo_sha256": rad.sha256(rad.RAIZ / ADENDO),
        "codigo_sha256": {p: rad.sha256(rad.RAIZ / p) for p in CODIGO},
        "autoverificacao_estrita_nos_publicados": autoverificacao, "documentos": documentos,
        "protegidos": conferir_protegidos(json.loads((GEOM / "selecao.json").read_text())),
        "limite": "Reconferência em memória; nenhum artefato de 24/09 foi regravado.",
    }
    verificar_sem_valores(resultado, comparados)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")
    return resultado


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--reconferir"]:
        r = reconferir_publicados()
        print(json.dumps({"autoverificacao": r["autoverificacao_estrita_nos_publicados"]}, ensure_ascii=False))
        raise SystemExit(0)
    r = executar()
    print(json.dumps({"estado": r["estado"], "documentos": [d["id_doc"] for d in r["documentos"]]},
                     ensure_ascii=False))
