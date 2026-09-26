"""GEOM-1: provas de escala por célula, ainda fora do consumidor governante.

Contrato e adendo de escala geométrica de 18/09. Extração somente local;
provas mascaradas e validadas por replay da fonte pinada. Não calcula alvo.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import math
from pathlib import Path
import re
import unicodedata

from scripts import fonte_rad_cvm as rad
from scripts.reconhecer_geometria_rank03b import anexos_pdf, paginas_bbox

REGRA = "GEOM-1"
PERIMETROS = {"controladora", "consolidado", "individual", "companhia"}
ROTULOS = {unicodedata.normalize("NFKD", k).encode("ascii", "ignore").decode(): v
           for k, v in rad.ROTULOS_SALDOS_V4.items()}
ROTULOS["total de caixa e equivalentes de caixa"] = "1.01.01"
SECOES = {"ativo", "passivo", "circulante", "nao circulante", "custo amortizado",
          "ativos financeiros"}
UNIDADE = re.compile(r"\(?(?:valores )?(?:(?:expressos|apresentados) )?em milhares de reais"
                     r"(?:,? exceto (?:quando )?indicado de outra forma)?\)?\.?$")
NUMERO = re.compile(rad.NUMERO_CELULA_V4)
TRACOS = {"-", "–", "—"}


def norm(texto):
    return " ".join(unicodedata.normalize("NFKD", texto).encode("ascii", "ignore")
                    .decode().lower().split())


def texto(linha):
    return " ".join(w["texto"] for w in linha)


def _data(t):
    for formato, padrao in (("%d/%m/%Y", r"\d{2}/\d{2}/\d{4}"),
                            ("%d.%m.%Y", r"\d{2}\.\d{2}\.\d{4}"),
                            ("%Y-%m-%d", r"\d{4}-\d{2}-\d{2}")):
        if re.fullmatch(padrao, t):
            try:
                return datetime.strptime(t, formato).date().isoformat()
            except ValueError:
                return None
    return None


def linhas_horizontais(pagina):
    """A ordem de blocos do PDF não define ordem de coluna."""
    if not all(math.isfinite(pagina[k]) and pagina[k] > 0 for k in ("largura", "altura")):
        raise ValueError("dimensões inválidas; página não certificável")
    palavras = [w for linha in pagina["linhas"] for w in linha]
    for w in palavras:
        coords = [w[k] for k in ("xMin", "yMin", "xMax", "yMax")]
        if (not all(math.isfinite(x) for x in coords)
                or not 0 <= w["xMin"] < w["xMax"] <= pagina["largura"]
                or not 0 <= w["yMin"] < w["yMax"] <= pagina["altura"]):
            raise ValueError("caixa inválida; página não certificável")
    grupos = []
    for w in sorted(palavras, key=lambda w: (w["yMin"], w["xMin"])):
        if not grupos or w["yMin"] - grupos[-1][0]["yMin"] > 1.5:
            grupos.append([])
        grupos[-1].append(w)
    return [sorted(g, key=lambda w: w["xMin"]) for g in grupos]


def _caixa(w):
    return [round(w[k], 6) for k in ("xMin", "yMin", "xMax", "yMax")]


def _publicar(linha, mascarada=False):
    return [{"texto": re.sub(r"\d[\d.,]*", "[valor omitido]", w["texto"])
             if mascarada else w["texto"], "bbox": _caixa(w)} for w in linha]


def cabecalho(linhas, i, corrente):
    datas = [(w, _data(w["texto"])) for w in linhas[i] if _data(w["texto"])]
    outras = [w for w in linhas[i] if not _data(w["texto"])]
    if not datas or i == 0 or len(outras) > 1:
        return None
    if outras and (norm(outras[0]["texto"]) not in ("nota", "notas")
                   or outras[0]["xMax"] >= datas[0][0]["xMin"]):
        return None
    per = linhas[i - 1]
    if (not all(norm(w["texto"]) in PERIMETROS for w in per)
            or sum(norm(w["texto"]) == "consolidado" for w in per) != 1
            or linhas[i][0]["yMin"] - per[0]["yMin"] > 24
            or len(datas) % len(per)):
        return None
    n = len(datas) // len(per)
    grupos = [datas[j * n:(j + 1) * n] for j in range(len(per))]
    sequencia = [d for _, d in grupos[0]]
    if (len(sequencia) != len(set(sequencia)) or corrente not in sequencia
            or any(d > corrente for d in sequencia)
            or any([d for _, d in g] != sequencia for g in grupos)):
        return None
    for w, g in zip(per, grupos):
        centro = (w["xMin"] + w["xMax"]) / 2
        if not g[0][0]["xMin"] - 12 <= centro <= g[-1][0]["xMax"] + 12:
            return None
    unidades = [(j, l) for j, l in enumerate(linhas[:i - 1])
                if l[0]["yMin"] <= 200 and UNIDADE.fullmatch(norm(texto(l)))]
    if not unidades:
        return None
    ui, unidade = unidades[-1]
    coluna = next(j for j, w in enumerate(per) if norm(w["texto"]) == "consolidado") * n + sequencia.index(corrente)
    return {"datas": datas, "perimetros": per, "coluna": coluna,
            "unidade": unidade, "indice_unidade": ui, "nota": outras}


def _celulas(linha, cab):
    celulas, usadas = [], set()
    for dw, _ in cab["datas"]:
        candidatas = [(j, w) for j, w in enumerate(linha)
                      if NUMERO.fullmatch(w["texto"])
                      and abs(w["xMax"] - dw["xMax"]) <= 12]
        if len(candidatas) != 1 or candidatas[0][0] in usadas:
            return None
        j, w = candidatas[0]
        if w["texto"].startswith("(") != w["texto"].endswith(")"):
            return None
        celulas.append(w)
        usadas.add(j)
    if cab["nota"]:
        nw = cab["nota"][0]
        candidatas = [j for j, w in enumerate(linha) if re.fullmatch(r"\d+", w["texto"])
                      and abs(w["xMax"] - nw["xMax"]) <= 12 and j not in usadas]
        if len(candidatas) > 1:
            return None
        usadas.update(candidatas)
    restante = [w for j, w in enumerate(linha) if j not in usadas]
    if not restante or max(w["xMax"] for w in restante) >= min(w["xMin"] for w in celulas):
        return None
    rotulo = norm(texto(restante))
    rotulo = re.sub(r"\s*(?:\(nota \d+\)|- nota \d+)$", "", rotulo).strip()
    return rotulo, celulas


def _contraria(linha):
    t = norm(texto(linha))
    if UNIDADE.fullmatch(t):
        return False
    # Uma declaração de unidade desconhecida não é ausência de declaração.
    inicio = re.match(r"\(?(?:em\b|valores\b|montantes\b|express[oa]s?\b|unidade\b|moeda\b)", t)
    termos = re.search(r"milhares|milhoes|centavos|unidades|dolares|libras|ienes|euros|"
                       r"us\$|usd|eur|em reais\b|por acao|percentua", t)
    return bool(inicio or termos)


def _numero(t):
    if t in TRACOS:
        return None
    return abs(Decimal(t.strip("()").replace(".", "").replace(",", ".")))


def candidatas_pagina(pagina, corrente):
    linhas = linhas_horizontais(pagina)
    saida = []
    for i, linha in enumerate(linhas):
        cab = cabecalho(linhas, i, corrente)
        if cab is None:
            continue
        if any(_contraria(l) for l in linhas[cab["indice_unidade"] + 1:i]):
            continue
        anterior_y = linha[0]["yMin"]
        for j in range(i + 1, len(linhas)):
            row = linhas[j]
            y = row[0]["yMin"]
            if (y - linha[0]["yMin"] > 300 or y - anterior_y > 30
                    or any(_data(w["texto"]) or norm(w["texto"]) in PERIMETROS for w in row)
                    or _contraria(row) or UNIDADE.fullmatch(norm(texto(row)))):
                break
            anterior_y = y
            extraida = _celulas(row, cab)
            if extraida is None:
                if norm(texto(row)).rstrip(":") in SECOES:
                    continue
                break
            rotulo, celulas = extraida
            conta = ROTULOS.get(rotulo)
            if conta is None:
                continue
            valor = _numero(celulas[cab["coluna"]]["texto"])
            if not valor:
                continue
            saida.append({"conta": conta, "valor": valor,
                          "decimal": "," in celulas[cab["coluna"]]["texto"],
                          "prova": {"regra": REGRA, "conta": conta,
                                    "dt_fim": corrente, "perimetro": "consolidado",
                                    "unidade": "MIL", "coluna": cab["coluna"] + 1,
                                    "datas": [d for _, d in cab["datas"]],
                                    "linha_unidade": _publicar(cab["unidade"]),
                                    "linha_perimetros": _publicar(cab["perimetros"]),
                                    "linha_datas": _publicar(linha),
                                    "linha_saldo": _publicar(row, mascarada=True),
                                    "celula": _caixa(celulas[cab["coluna"]])}})
    return saida


def evidencia(formulario, anexos, corrente):
    """`anexos`: (índice, hash PDF, páginas com palavras e coordenadas)."""
    corrente = date.fromisoformat(str(corrente)).isoformat()
    candidatos = {}
    for c, _, fim, valor in formulario.valores:
        if c in ROTULOS.values() and fim.isoformat() == corrente and valor is not None:
            candidatos.setdefault(c, set()).add(Decimal(str(valor)))
    valores = {c: abs(next(iter(v))) for c, v in candidatos.items()
               if len(v) == 1 and next(iter(v)).is_finite() and abs(next(iter(v))) >= 1000}
    outras = {}
    for c, _, _, v in (*formulario.valores, *formulario.valores_individuais):
        if c not in ROTULOS.values():
            continue  # Fluxos nem participam da comparação de escala GEOM-1.
        if v and math.isfinite(v):
            for forma, t in rad._formas_de(v).items():
                outras.setdefault(c, {}).setdefault(forma, set()).add(t)
    provas, recusas = [], Counter()
    for anexo, sha, paginas in anexos:
        for pagina, dados in enumerate(paginas, 1):
            try:
                linhas = candidatas_pagina(dados, corrente)
            except ValueError:
                recusas["coordenadas_invalidas"] += 1
                continue
            for r in linhas:
                conta = r["conta"]
                if conta not in valores:
                    continue
                for forma, fator in (("bruto", Decimal(1)), ("dividido", Decimal("0.001")),
                                     ("multiplicado", Decimal(1000))):
                    esperado = valores[conta] * fator
                    if forma == "dividido" and esperado < 1000:
                        continue
                    alvo = esperado if r["decimal"] else esperado.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
                    concorrentes = set().union(*(v for f, v in outras.get(conta, {}).items() if f != forma))
                    if r["valor"] == alvo:
                        if rad._inteiro_ptbr(float(r["valor"])) in concorrentes:
                            recusas["multiplicadores_ambiguos"] += 1
                        else:
                            provas.append({**r["prova"], "forma": forma, "anexo": anexo,
                                           "pagina": pagina, "sha256_pdf": sha})
    formas = {p["forma"] for p in provas}
    return {"regra": REGRA, "classe": "nenhum" if not formas else next(iter(formas))
            if len(formas) == 1 else "conflitante", "provas": provas,
            "contagem": {f: len({p["conta"] for p in provas if p["forma"] == f}) for f in rad.FORMAS},
            "recusas": dict(recusas)}


def extrair_documento(caminho: Path, corrente: str, hash_esperado: str):
    if rad.sha256(caminho) != hash_esperado:
        raise AssertionError("pacote diferente da fonte pinada")
    formulario = rad.ler(caminho, com_anexos=False)
    anexos = [(i, hashlib.sha256(pdf).hexdigest(), paginas_bbox(pdf))
              for i, _, pdf in anexos_pdf(caminho)]
    return evidencia(formulario, anexos, corrente)


def conferir_prova(prova, caminho, corrente, hash_esperado):
    """Consumidor: compara todos os campos com replay do PDF, não só metadata."""
    resultado = extrair_documento(caminho, corrente, hash_esperado)
    if prova not in resultado["provas"] or resultado["classe"] in ("nenhum", "conflitante"):
        raise AssertionError("prova não reproduzida na fonte pinada ou fonte conflitante")
    return True
