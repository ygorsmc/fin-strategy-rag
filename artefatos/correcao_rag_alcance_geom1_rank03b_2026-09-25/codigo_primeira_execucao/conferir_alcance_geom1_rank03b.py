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

**Correção RAG (25/09,** resultados/contratos_correcao_rag_alcance_geom1_rank03b_2026-09-25.md**):**
toda entrada é conferida por hash antes do uso e o universo tem de ser o do
pin (C1); token inteiro e sinal explícito, com recusa contada (C2);
autoverificação por equivalência numérica e isenção pela forma (C3); limite da
forma dividida por mil declarado (C4). A versão examinada pela conferência de
25/09 está preservada em
`artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/codigo_sob_conferencia/`.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import NamedTuple
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

from scripts import fonte_rad_cvm as rad
from scripts.inventariar_alcance_geom1_rank03b import (CODIGOS_ISO_4217, TIPOS_DE_FLUXO, classe_de_moedas,
                                                       classe_de_sinais, inventariar_texto, trecho_publicavel)
from scripts.piloto_geometria_rank03b import conferir_protegidos
from scripts.reconhecer_geometria_rank03b import anexos_pdf

BASE = rad.RAIZ / "artefatos/alcance_geom1_rank03b_2026-09-24"
GEOM = rad.RAIZ / "artefatos/escala_geometrica_rank03b_2026-09-18"
DESTINO = BASE / "revisao"
CONTRATO = "resultados/contratos_revisao_alcance_geom1_rank03b_2026-09-24.md"
CONTRATO_SHA256 = "fbba1972623100c49995edecd7e158b6df190928bde1429e8f98c118bee70263"
CONTRATO_CORRECAO = "resultados/contratos_correcao_rag_alcance_geom1_rank03b_2026-09-25.md"
CONTRATO_CORRECAO_SHA256 = "6979772114c4eeb0a8ac3ee832329e12e764b3091ec2242435423fc06a839e78"
#: Hash do inventário publicado, registrado pelo auditor em parecer_auditor.json.
INVENTARIO_PUBLICADO_SHA256 = "4bb25cf08b87843c0ccab5610415e49284d306f04307818059b15960716c84b3"
#: N1 (reconferência da auditoria, 25/09): as saídas da execução de 24/09, presas a uma
#: versão. A reconferência de 25/09 foi feita sem esta guarda, pela versão preservada em
#: `revisao/conferir_alcance_reconferencia.py`.
CONFERENCIA_REVISAO_SHA256 = "c19682bfde33480a66caeb088503f098360aebce57b6070a539f5f97a28eb3a3"
PIN_REVISAO_SHA256 = "34139fb65ded85eb152039fe1a57d54f4fd9bcdfee4ef35f9cf6e104ae3db72e"
#: C1 (correção RAG): o pin que define o universo de documentos — o mesmo que
#: `pin_execucao.json` e `revisao/pin_revisao.json` registram —, a referência do
#: código congelado e a dos sete protegidos. Antes, os três eram lidos sem conferência.
PIN_ALCANCE_SHA256 = "0dd42e2f5af489cb3a1a551759a89120c345db874931784e0b0b8f5c53f22853"
PIN_EXECUCAO_SHA256 = "bb2059f3792910b61d057ad271a10a001bd75a070de7fd8a7aa9e795a7055ae2"
SELECAO_SHA256 = "b3e85417f2bcbc5c157f364bafcf8276cf1da7dcb3713535e58f45ca2431452d"
MODOS = ("-layout", "-raw")
CODIGO = ("scripts/conferir_alcance_geom1_rank03b.py", "scripts/inventariar_alcance_geom1_rank03b.py",
          "scripts/reconhecer_geometria_rank03b.py", "scripts/piloto_geometria_rank03b.py",
          "scripts/fonte_rad_cvm.py")
BP, DFC = "BalancoPatrimonialAtivo", "DemonstracaoFluxoCaixa"
CONS, IND = "DfConsolidadas", "DfIndividuais"
#: Isenções da autoverificação, como o contrato R3 as descreve ("campos de hash e
#: data"). C3 (correção RAG): a isenção é pela FORMA — sob estas chaves, só data
#: `AAAA-MM-DD`; sob chave terminada em `sha256`, só 64 hexadecimais.
CHAVES_DE_DATA = frozenset({"data", "dt_refer"})
#: Menos que isso numa página é "pouco texto": publicado para qualificar a busca.
MINIMO_DE_CARACTERES = 40
DESTINO_RECONFERENCIA = DESTINO / "reconferencia_pos_auditoria.json"
ADENDO = "resultados/adendo_revisao_alcance_geom1_rank03b_2026-09-25.md"
ADENDO_SHA256 = "f6cbd726879656ebbd0b249e39fcb33320987f80bcc4d72bbd2f87a4526a2f83"
#: GEOM-1 e leitor de fonte não podem ter mudado desde a execução de 24/09.
CODIGO_CONGELADO = ("scripts/reconhecer_geometria_rank03b.py", "scripts/piloto_geometria_rank03b.py",
                    "scripts/fonte_rad_cvm.py")
#: Sem dígitos, de propósito: um texto fixo com número poderia coincidir com um
#: valor comparado e derrubar a autoverificação por acaso.
LIMITE = ("Sem correspondência vale só para estas notas e para tokens inteiros no formato pt-BR com "
          "ponto de milhar; token fora dessa gramática é recusado e contado, e token de sinal ambíguo "
          "não conta como correspondência do ativo. A forma dividida por mil compara exatamente e só "
          "casaria se as notas imprimissem as casas decimais do milhar: não testa a hipótese de XML em "
          "reais com notas em milhares arredondados. Nada disso demonstra ausência em outra fonte. A "
          "identidade de caixa não envolve o FCO e não prova a escala dele.")
EXPOSICAO = ("Repetição da busca de 24/09 nas mesmas fontes, com o analisador corrigido em 25/09. Os "
             "resultados de 24/09 e uma medição em memória do ativo feita em 25/09 eram conhecidos. "
             "Não é teste cego.")

_XML_PTBR = re.compile(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


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


# --- C1: entradas vinculadas antes do uso --------------------------------------------------------

def _ler_fixados(entradas: list[tuple[Path, str, str]]) -> list[bytes]:
    """Lê cada entrada uma vez e confere o hash dos MESMOS bytes que serão
    interpretados. Confere todas antes de o chamador interpretar qualquer uma."""
    lidos = []
    for caminho, esperado, rotulo in entradas:
        dados = caminho.read_bytes()
        if hashlib.sha256(dados).hexdigest() != esperado:
            raise AssertionError(f"{rotulo} diferente da versão fixada ({caminho.name})")
        lidos.append(dados)
    return lidos


def validar_fontes(pin) -> list[dict]:
    """C1: o universo do pin — não vazio, cada fonte com hash, nada repetido.

    Pin sem fontes não é "nada a corrigir": é nada examinado (§4.4, regra 4).
    """
    fontes = pin.get("fontes") if isinstance(pin, dict) else None
    if not isinstance(fontes, list) or not fontes:
        raise AssertionError("pin sem fontes: nada examinado não é aprovação")
    for fonte in fontes:
        if not (isinstance(fonte, dict)
                and isinstance(fonte.get("id_doc"), str) and re.fullmatch(r"[0-9]+", fonte["id_doc"])
                and isinstance(fonte.get("sha256"), str) and _SHA256.fullmatch(fonte["sha256"])):
            raise AssertionError("fonte do pin malformada")
    for campo in ("id_doc", "sha256"):
        if len({f[campo] for f in fontes}) != len(fontes):
            raise AssertionError(f"fonte repetida no pin ({campo})")
    return fontes


def exigir_mesmo_universo(fontes: list[dict], registros, rotulo: str) -> None:
    """C1: mesmos documentos do pin, na mesma ordem, sem repetição nem sobra."""
    if not isinstance(registros, list) or not all(isinstance(r, dict) for r in registros):
        raise AssertionError(f"{rotulo}: registros malformados")
    ids = [r.get("id_doc") for r in registros]
    if len(set(ids)) != len(ids):
        raise AssertionError(f"{rotulo}: documento repetido")
    if ids != [f["id_doc"] for f in fontes]:
        raise AssertionError(f"{rotulo}: documentos diferentes das fontes do pin")


def conferir_fontes(fontes: list[dict], brutos: Path) -> None:
    for doc in fontes:
        if rad.sha256(brutos / f"{doc['id_doc']}.zip") != doc["sha256"]:
            raise AssertionError("fonte diferente do pin de 24/09")


# --- C2: token inteiro e sinal explícito ---------------------------------------------------------

#: Token: sequência máxima de dígitos separados por um único `.` ou `,` entre dígitos.
_TOKEN = re.compile(r"\d+(?:[.,]\d+)*")
#: Só o token INTEIRO nesta gramática é comparado; o resto é recusado e contado.
_GRAMATICA_PTBR = re.compile(r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")


class Token(NamedTuple):
    coluna: int  # ordem entre TODOS os tokens da linha, aceitos ou recusados
    modulo: Decimal | None  # None: fora da gramática — nunca comparado
    sinal: int | None  # +1 ou -1; None: ambíguo, ou token recusado


@lru_cache(maxsize=1)
def _tracos() -> frozenset[str]:
    """Sinais que negam: traço (Pd) ou menos. `+` e `±` não negam."""
    return frozenset(c for c in classe_de_sinais()
                     if unicodedata.category(c) == "Pd"
                     or ("MINUS" in unicodedata.name(c, "") and "PLUS" not in unicodedata.name(c, "")))


@lru_cache(maxsize=1)
def _classes() -> dict[str, frozenset[str]]:
    def nome(c):
        return unicodedata.name(c, "")
    sinais = frozenset(classe_de_sinais())
    return {
        "sinais": sinais,
        "abre": frozenset(c for c in sinais if "PARENTHESIS" in nome(c) and "LEFT" in nome(c)),
        "fecha": frozenset(c for c in sinais if "PARENTHESIS" in nome(c) and "RIGHT" in nome(c)),
        "menos": _tracos(),
        "mais": frozenset(c for c in sinais if "PLUS SIGN" in nome(c) and "MINUS" not in nome(c)),
        "moedas": frozenset(classe_de_moedas()),
    }


def _contexto_esquerdo(linha: str, inicio: int) -> tuple[list[tuple[str, bool]], bool]:
    """O que separa o token da palavra anterior, da esquerda para a direita.

    Itens: `moeda` (símbolo `Sc` com até três maiúsculas de prefixo, ou código
    ISO 4217 inteiro), `abre`, `menos`, `mais` e `outro` (demais sinais), cada um
    com "há espaço logo depois". Parêntese de fechamento encerra o contexto: é
    de algo anterior. Devolve também se o primeiro item vem colado a uma
    palavra ou número (`2024-2025`, `Total(1.234)`).
    """
    k = _classes()
    itens: list[tuple[str, bool]] = []
    i, espaco = inicio, False
    while i > 0:
        ch = linha[i - 1]
        if ch.isspace():
            espaco, i = True, i - 1
            continue
        if ch in k["moedas"]:
            j = i - 1
            while j > 0 and i - 1 - j < 3 and "A" <= linha[j - 1] <= "Z":
                j -= 1
            tipo, i_antes = "moeda", j
        elif (i >= 3 and linha[i - 3:i] in CODIGOS_ISO_4217
              and (i == 3 or not linha[i - 4].isalnum()) and not linha[i:i + 1].isalpha()):
            # Colado ao número (`−USD1.234`) ainda é moeda; colado a letra, não.
            tipo, i_antes = "moeda", i - 3
        elif ch in k["abre"]:
            tipo, i_antes = "abre", i - 1
        elif ch in k["menos"]:
            tipo, i_antes = "menos", i - 1
        elif ch in k["mais"]:
            tipo, i_antes = "mais", i - 1
        elif ch in k["sinais"] and ch not in k["fecha"]:
            tipo, i_antes = "outro", i - 1
        else:
            break
        itens.append((tipo, espaco))
        espaco, i = False, i_antes
    itens.reverse()
    return itens, bool(itens) and i > 0 and not espaco


def _sinal(linha: str, inicio: int, fim: int) -> int | None:
    """+1, -1 ou None (ambíguo). Só as formas do contrato C2 têm sinal; o resto é recusa explícita.

    - positivo: nenhum sinal ou parêntese no contexto, ou `+` colado ao que o segue;
    - negativo: parênteses equilibrados em volta do token (qualquer espaço, moeda
      dentro), ou traço/menos colado ao que o segue — o token ou a moeda;
    - ambíguo: sinal seguido de espaço, parêntese com sinal, parêntese sem par,
      sinal colado a palavra anterior, sinal depois do token, `±` e afins.
    """
    k = _classes()
    itens, colado = _contexto_esquerdo(linha, inicio)
    resto = linha[fim:]
    j = len(resto) - len(resto.lstrip())
    fecha = j < len(resto) and resto[j] in k["fecha"]
    if fecha:
        solto, depois = resto[j + 1:j + 2], resto[j + 2:j + 3]
    else:
        solto, depois = resto[:1], resto[1:2]
        if solto in k["abre"]:
            solto = ""
    if solto and solto in k["sinais"] and not depois.isdigit():
        return None  # sinal depois do token ou do parêntese: forma não suportada
    nucleo = [(tipo, espaco) for tipo, espaco in itens if tipo != "moeda"]
    if not nucleo:
        return None if fecha else 1
    if len(nucleo) != 1 or colado:
        return None
    tipo, espaco = nucleo[0]
    if tipo == "abre":
        return -1 if fecha else None
    if fecha or espaco or tipo == "outro":
        return None
    return -1 if tipo == "menos" else 1


def tokens_da_linha(linha: str) -> list[Token]:
    """Todos os tokens numéricos da linha, na ordem; recusados ficam com módulo None."""
    saida = []
    for coluna, m in enumerate(_TOKEN.finditer(linha), 1):
        texto, inicio = m.group(), m.start()
        if (inicio > 0 and linha[inicio - 1] in ".,") or not _GRAMATICA_PTBR.fullmatch(texto):
            saida.append(Token(coluna, None, None))
            continue
        modulo = Decimal(texto.replace(".", "").replace(",", "."))
        saida.append(Token(coluna, modulo, _sinal(linha, inicio, m.end())))
    return saida


def _varrer(paginas: list[str], alvos: dict[str, Decimal], casa) -> dict[str, list[dict]]:
    achados: dict[str, list[dict]] = {nome: [] for nome in alvos}
    for p, pagina in enumerate(paginas, 1):
        for n, linha in enumerate(pagina.splitlines(), 1):
            tokens = tokens_da_linha(linha)
            for nome, alvo in alvos.items():
                if alvo == 0:
                    continue
                for t in tokens:
                    if t.modulo is not None and casa(t, alvo):
                        achados[nome].append({"pagina": p, "linha": n, "coluna": t.coluna,
                                              "tokens": len(tokens), "texto": linha})
    return achados


def ocorrencias(paginas: list[str], alvos: dict[str, Decimal], *, por_modulo: bool) -> dict[str, list[dict]]:
    """Onde cada alvo aparece. Zero nunca é procurado: zero não prova escala.

    Com sinal (ativo), só token de sinal explícito casa; por módulo (FCO), o sinal
    não importa. Token fora da gramática nunca casa, nem por prefixo.
    """
    if por_modulo:
        return _varrer(paginas, alvos, lambda t, alvo: t.modulo == abs(alvo))
    return _varrer(paginas, alvos, lambda t, alvo: t.sinal is not None and t.sinal * t.modulo == alvo)


def ocorrencias_de_sinal_ambiguo(paginas: list[str], alvos: dict[str, Decimal]) -> dict[str, list[dict]]:
    """C2: token de mesmo módulo e sinal ambíguo. Publicado à parte — NUNCA é
    correspondência; existe para que a ausência de correspondência não seja muda."""
    return _varrer(paginas, alvos, lambda t, alvo: t.sinal is None and t.modulo == abs(alvo))


def contagem_de_tokens(paginas: list[str]) -> dict[str, dict[str, int]]:
    """C2: recusas e sinais ambíguos por página, independentes do alvo. Por página
    porque um total pode passar de mil, e a autoverificação barra número assim."""
    recusados: dict[str, int] = {}
    ambiguos: dict[str, int] = {}
    for p, pagina in enumerate(paginas, 1):
        for linha in pagina.splitlines():
            for t in tokens_da_linha(linha):
                if t.modulo is None:
                    recusados[str(p)] = recusados.get(str(p), 0) + 1
                elif t.sinal is None:
                    ambiguos[str(p)] = ambiguos.get(str(p), 0) + 1
    return {"tokens_fora_da_gramatica_por_pagina": recusados, "tokens_com_sinal_ambiguo_por_pagina": ambiguos}


def formas_que_so_casam_com_decimais(alvos: dict[str, Decimal]) -> list[str]:
    """C4: alvo não inteiro só casaria se as notas imprimissem as casas decimais.
    Só para o ativo: calcular isso sobre o FCO seria ler mais que igualdade (O1)."""
    return [nome for nome, alvo in alvos.items() if alvo != alvo.to_integral_value()]


def publicar_ativo(achados: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """B1: o trecho segue a mesma política do inventário (linha de fluxo ou de
    vocabulário de caixa não publica trecho)."""
    return {nome: [{"pagina": a["pagina"], "linha": a["linha"], "coluna": a["coluna"],
                    "tokens": a["tokens"], **trecho_publicavel(a["texto"])} for a in lista]
            for nome, lista in achados.items()}


def publicar_fco(achados: dict[str, list[dict]]) -> dict[str, list[int]]:
    """Só páginas: nem coluna, nem linha, nem trecho (O1)."""
    return {nome: sorted({a["pagina"] for a in lista}) for nome, lista in achados.items()}


# --- C3: autoverificação por equivalência numérica -----------------------------------------------

_ESPACOS_DE_MILHAR = "    "
#: Representação numérica publicada: dígitos com `.`/`,` entre dígitos, ou grupos
#: de três separados por espaço; expoente opcional.
_NUMERO_PUBLICADO = re.compile(
    rf"\d+(?:[.,]\d+|[{_ESPACOS_DE_MILHAR}]\d{{3}}(?!\d))*(?:[eE][+-]?\d{{1,3}})?")


def _leituras(representacao: str) -> set[Decimal]:
    """Os valores que a representação pode estar dizendo: todo `.`/`,` como milhar;
    ou o último como decimal e os outros como milhar."""
    m = re.fullmatch(r"(?P<mantissa>[^eE]+)(?:[eE](?P<expoente>[+-]?\d+))?", representacao)
    mantissa = re.sub(f"[{_ESPACOS_DE_MILHAR}]", "", m["mantissa"])
    leituras = {Decimal(re.sub(r"[.,]", "", mantissa))}
    corte = max(mantissa.rfind("."), mantissa.rfind(","))
    if corte >= 0:
        leituras.add(Decimal(re.sub(r"[.,]", "", mantissa[:corte]) + "." + mantissa[corte + 1:]))
    return {d.scaleb(int(m["expoente"] or 0)) for d in leituras}


def _magnitudes_protegidas(valores) -> set[Decimal]:
    """Módulo de cada valor comparado >= 1.000; se não é inteiro, também piso e teto."""
    protegidas = set()
    for v in valores:
        modulo = abs(Decimal(v))
        if modulo < 1000:
            continue
        protegidas.add(modulo)
        if modulo != modulo.to_integral_value():
            protegidas |= {modulo.to_integral_value(rounding=ROUND_FLOOR),
                           modulo.to_integral_value(rounding=ROUND_CEILING)}
    return protegidas


def _rotulo(chave) -> str:
    """Nome de campo para mensagem de erro, com dígitos mascarados."""
    return "raiz" if chave is None else re.sub(r"\d", "#", str(chave))[:80]


def _isencao(chave, herdada: str | None) -> str | None:
    if str(chave).endswith("sha256"):
        return "hash"
    if chave in CHAVES_DE_DATA:
        return "data"
    return herdada


def verificar_sem_valores(saida, valores) -> None:
    """Recusa a saída se algum valor comparado (módulo >= 1.000) estiver nela.

    C3: em qualquer grafia (equivalência numérica, não lista de formas), em texto
    e em chave. Isenção pela forma: hash só se for hash; data só se for data.
    Tipo não previsto derruba — ignorá-lo seria aprovar sem olhar.
    """
    protegidas = _magnitudes_protegidas(valores)

    def contem(texto: str) -> bool:
        return any(leitura in protegidas
                   for m in _NUMERO_PUBLICADO.finditer(texto) for leitura in _leituras(m.group()))

    def visita(obj, chave=None, isencao=None):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if contem(str(k)):  # B1: a chave também é publicada
                    raise VazamentoDeValor(f"valor comparado publicado como nome de campo, sob {_rotulo(chave)}")
                visita(v, k, _isencao(k, isencao))
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                visita(v, chave, isencao)
        elif isinstance(obj, bool) or obj is None:
            return
        elif isinstance(obj, (int, float, Decimal)):
            if abs(obj) >= 1000:
                raise VazamentoDeValor(f"número de módulo >= mil publicado em {_rotulo(chave)}")
        elif isinstance(obj, str):
            if (isencao == "hash" and _SHA256.fullmatch(obj)) or (isencao == "data" and _DATA_ISO.fullmatch(obj)):
                return
            if chave == "trecho" and re.search(r"\d", obj):
                raise VazamentoDeValor("dígito em trecho publicado")
            if contem(obj):
                raise VazamentoDeValor(f"valor comparado publicado em {_rotulo(chave)}")
        else:
            raise TypeError(f"tipo não previsto na autoverificação: {type(obj).__name__}")
    visita(saida)


def _autoverificar(saida, valores) -> None:
    """C1: autoverificação sem valor verificável não certifica nada — falha."""
    if not any(abs(Decimal(v)) >= 1000 for v in valores):
        raise AssertionError("autoverificação sem valor verificável: não se certifica por ausência")
    verificar_sem_valores(saida, valores)


# --- leitura do formulário e dos PDFs ------------------------------------------------------------

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
    ilegiveis = [n for n, pagina in enumerate(paginas, 1) if "(cid:" in pagina or "�" in pagina]
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
    """O que os dois extratores têm de concordar: páginas/colunas do ativo (também
    as de sinal ambíguo, desde C2) e páginas do FCO. Saída anterior a C2 não tem a
    chave dos ambíguos."""
    def posicoes(ocorrencias_publicadas):
        return {k: [(a["pagina"], a["coluna"]) for a in v] for k, v in ocorrencias_publicadas.items()}
    return (posicoes(modo["ativo"]), posicoes(modo.get("ativo_modulo_com_sinal_ambiguo", {})),
            modo["fco_paginas"])


def _pdftotext_layout(pdf: bytes) -> str:
    return subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf, capture_output=True,
                          check=True).stdout.decode()


# --- execução e reconferência --------------------------------------------------------------------

def executar(destino: Path = DESTINO) -> dict:
    pin_revisao, saida_json = destino / "pin_revisao.json", destino / "conferencia_revisao.json"
    if pin_revisao.exists() or saida_json.exists():
        raise FileExistsError("revisão já registrada; não sobrescrever")
    # C1: tudo conferido antes de qualquer interpretação.
    inventario_bytes, execucao_bytes, pin_bytes, selecao_bytes, *_ = _ler_fixados([
        (BASE / "inventario_textual.json", INVENTARIO_PUBLICADO_SHA256, "inventário publicado"),
        (BASE / "pin_execucao.json", PIN_EXECUCAO_SHA256, "pin de execução do inventário"),
        (BASE / "pin.json", PIN_ALCANCE_SHA256, "pin de alcance"),
        (GEOM / "selecao.json", SELECAO_SHA256, "seleção GEOM-1"),
        (rad.RAIZ / CONTRATO, CONTRATO_SHA256, "contrato de 24/09"),
        (rad.RAIZ / CONTRATO_CORRECAO, CONTRATO_CORRECAO_SHA256, "contrato da correção RAG"),
    ])
    execucao = json.loads(execucao_bytes)
    if any(rad.sha256(rad.RAIZ / p) != execucao["codigo_sha256"][p] for p in CODIGO_CONGELADO):
        raise AssertionError("código GEOM-1 ou leitor de fonte mudou desde 24/09")
    fontes = validar_fontes(json.loads(pin_bytes))
    if execucao.get("pin_sha256") != PIN_ALCANCE_SHA256:
        raise AssertionError("pin de execução não aponta para o pin de alcance fixado")
    inventario = json.loads(inventario_bytes)
    exigir_mesmo_universo(fontes, inventario.get("registros"), "inventário publicado")
    conferir_fontes(fontes, rad.BRUTOS)
    selecao = json.loads(selecao_bytes)
    # Valores do XML lidos em memória ANTES de gravar qualquer coisa: a identidade
    # também é publicada e passa pela mesma autoverificação (C3).
    formularios, comparados = {}, []
    for doc in fontes:
        nome, sha_xml, form, escala = formulario(rad.BRUTOS / f"{doc['id_doc']}.zip")
        alvos = (alvos_ativo(form), alvos_fco(form), saldos_de_caixa(form))
        formularios[doc["id_doc"]] = (nome, sha_xml, escala, *alvos)
        comparados += [*alvos[0].values(), *alvos[1].values(), *alvos[2]]
    versao = subprocess.run(["pdftotext", "-v"], capture_output=True, check=True).stderr.decode().splitlines()[0]
    identidade = {
        "data": date.today().isoformat(),
        "contrato": CONTRATO, "contrato_sha256": CONTRATO_SHA256,
        "contrato_correcao": CONTRATO_CORRECAO, "contrato_correcao_sha256": CONTRATO_CORRECAO_SHA256,
        "pin_alcance_sha256": PIN_ALCANCE_SHA256, "pin_execucao_sha256": PIN_EXECUCAO_SHA256,
        "selecao_sha256": SELECAO_SHA256, "inventario_publicado_sha256": INVENTARIO_PUBLICADO_SHA256,
        "poppler": versao, "codigo_sha256": {p: rad.sha256(rad.RAIZ / p) for p in CODIGO},
        "fontes": fontes, "protegidos_antes": conferir_protegidos(selecao), "exposicao": EXPOSICAO,
    }
    _autoverificar(identidade, comparados)
    destino.mkdir(parents=True, exist_ok=True)
    pin_revisao.write_text(json.dumps(identidade, ensure_ascii=False, indent=2) + "\n")

    publicado = {r["id_doc"]: r for r in inventario["registros"]}
    documentos = []
    for doc in fontes:
        nome, sha_xml, escala, ativo, fco, caixa = formularios[doc["id_doc"]]
        (indice, grupo, pdf), = anexos_pdf(rad.BRUTOS / f"{doc['id_doc']}.zip")
        por_modo = {}
        for modo in MODOS:
            paginas = paginas_pdf(pdf, modo)
            exigir_texto_legivel(paginas)
            por_modo[modo] = {"paginas": len(paginas), "paginas_com_pouco_texto": paginas_com_pouco_texto(paginas),
                              **contagem_de_tokens(paginas),
                              "ativo": publicar_ativo(ocorrencias(paginas, ativo, por_modulo=False)),
                              "ativo_modulo_com_sinal_ambiguo": publicar_ativo(
                                  ocorrencias_de_sinal_ambiguo(paginas, ativo)),
                              "fco_paginas": publicar_fco(ocorrencias(paginas, fco, por_modulo=True))}
        novo = inventariar_texto(_pdftotext_layout(pdf))
        documentos.append({
            "id_doc": doc["id_doc"], "nome_xml": nome, "xml_sha256": sha_xml, "escala_moeda_codigo": escala,
            "anexo": indice, "grupo": grupo, "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
            "modos": por_modo,
            "modos_concordam": _posicoes(por_modo["-layout"]) == _posicoes(por_modo["-raw"]),
            "ativo_formas_que_so_casam_com_decimais": formas_que_so_casam_com_decimais(ativo),
            "identidade_saldo_final_dfc_igual_caixa_bp": caixa[0] == caixa[1],
            "reinventario_mascara_r4": comparar_inventarios(publicado[doc["id_doc"]]["paginas"], novo),
        })
    resultado = {
        "estado": "busca_numerica_exata_nao_adjudica",
        "documentos": documentos,
        "limite": LIMITE,
        "protegidos_depois": conferir_protegidos(selecao),
        "escala_promovida": False, "gates_medidos": False,
    }
    _autoverificar(resultado, comparados)
    saida_json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")
    return resultado


def reconferir_publicados(destino: Path = DESTINO_RECONFERENCIA) -> dict:
    """Adendo de 25/09: os artefatos já publicados sob as regras novas.

    Não regrava nada de 24/09. Relê fontes e XML em memória, como a execução;
    publica só booleanos, contagens e páginas. C1 (correção RAG): o universo vem
    do pin fixado e tem de ser o mesmo nas saídas e no inventário.
    """
    if destino.exists():
        raise FileExistsError("reconferência já registrada; não sobrescrever")
    entradas = [(DESTINO / "conferencia_revisao.json", CONFERENCIA_REVISAO_SHA256),
                (DESTINO / "pin_revisao.json", PIN_REVISAO_SHA256),
                (BASE / "inventario_textual.json", INVENTARIO_PUBLICADO_SHA256),
                (BASE / "pin.json", PIN_ALCANCE_SHA256),
                (GEOM / "selecao.json", SELECAO_SHA256),
                (rad.RAIZ / ADENDO, ADENDO_SHA256),
                (rad.RAIZ / CONTRATO_CORRECAO, CONTRATO_CORRECAO_SHA256)]
    conferencia_bytes, pin_rev_bytes, inventario_bytes, pin_bytes, selecao_bytes, *_ = _ler_fixados(
        [(caminho, esperado, "entrada") for caminho, esperado in entradas])
    conferencia, pin_revisao = json.loads(conferencia_bytes), json.loads(pin_rev_bytes)
    fontes = validar_fontes(json.loads(pin_bytes))
    if pin_revisao.get("pin_alcance_sha256") != PIN_ALCANCE_SHA256 or pin_revisao.get("fontes") != fontes:
        raise AssertionError("pin da revisão aponta para outro pin ou outras fontes")
    exigir_mesmo_universo(fontes, conferencia.get("documentos"), "conferência publicada")
    inventario_doc = json.loads(inventario_bytes)
    exigir_mesmo_universo(fontes, inventario_doc.get("registros"), "inventário publicado")
    conferir_fontes(fontes, rad.BRUTOS)
    selecao = json.loads(selecao_bytes)
    publicados = {"conferencia_revisao.json": conferencia, "pin_revisao.json": pin_revisao}
    executados = {d["id_doc"]: d for d in conferencia["documentos"]}
    inventario = {r["id_doc"]: r["paginas"] for r in inventario_doc["registros"]}
    comparados, documentos = [], []
    for doc in fontes:
        pacote = rad.BRUTOS / f"{doc['id_doc']}.zip"
        _, _, form, _ = formulario(pacote)
        comparados += [*alvos_ativo(form).values(), *alvos_fco(form).values(), *saldos_de_caixa(form)]
        (_, _, pdf), = anexos_pdf(pacote)
        executado = executados[doc["id_doc"]]
        qualidade, trechos = {}, {"mantidos": 0, "diferentes": 0}
        for modo in MODOS:
            paginas = paginas_pdf(pdf, modo)
            qualidade[modo] = {
                "texto_ilegivel": any("(cid:" in p or "�" in p for p in paginas),
                "paginas_com_pouco_texto": paginas_com_pouco_texto(paginas)}
            for lista in executado["modos"][modo]["ativo"].values():
                for a in lista:
                    linha = paginas[a["pagina"] - 1].splitlines()[a["linha"] - 1]
                    trechos["mantidos" if trecho_publicavel(linha) == {"trecho": a["trecho"]} else "diferentes"] += 1
        novo = inventariar_texto(_pdftotext_layout(pdf))
        documentos.append({"id_doc": doc["id_doc"], "qualidade_do_texto": qualidade,
                           "trechos_do_ativo_sob_a_politica_nova": trechos,
                           "inventario_sob_a_politica_nova": efeito_da_politica(inventario[doc["id_doc"]], novo)})
    autoverificacao = {}
    for nome, conteudo in publicados.items():
        try:
            _autoverificar(conteudo, comparados)
            autoverificacao[nome] = True
        except VazamentoDeValor:
            autoverificacao[nome] = False
    resultado = {
        "data": date.today().isoformat(), "adendo": ADENDO, "adendo_sha256": ADENDO_SHA256,
        "contrato_correcao": CONTRATO_CORRECAO, "contrato_correcao_sha256": CONTRATO_CORRECAO_SHA256,
        "entradas_sha256": {caminho.name: esperado for caminho, esperado in entradas},
        "codigo_sha256": {p: rad.sha256(rad.RAIZ / p) for p in CODIGO},
        "autoverificacao_estrita_nos_publicados": autoverificacao, "documentos": documentos,
        "protegidos": conferir_protegidos(selecao),
        "limite": "Reconferência em memória; nenhum artefato de 24/09 foi regravado.",
    }
    _autoverificar(resultado, comparados)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")
    return resultado


if __name__ == "__main__":
    import argparse
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--reconferir", action="store_true",
                            help="reconfere os artefatos publicados de 24/09 em vez de executar a busca")
    argumentos.add_argument("--destino", type=Path,
                            help="pasta da busca ou arquivo da reconferência; nunca sobrescreve")
    opcoes = argumentos.parse_args()
    if opcoes.reconferir:
        r = reconferir_publicados(opcoes.destino or DESTINO_RECONFERENCIA)
        print(json.dumps({"autoverificacao": r["autoverificacao_estrita_nos_publicados"],
                          "documentos": [d["id_doc"] for d in r["documentos"]]}, ensure_ascii=False))
        raise SystemExit(0)
    r = executar(opcoes.destino or DESTINO)
    print(json.dumps({"estado": r["estado"], "documentos": [d["id_doc"] for d in r["documentos"]]},
                     ensure_ascii=False))
