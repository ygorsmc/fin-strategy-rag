"""ROTA-2 — prova de escala por célula própria e cadeia de identidades (Rank 3-B).

Contrato: `resultados/contratos_caminho_medicao_rank03b_2026-09-27.md`, parte B,
com as emendas de 27/09 e a seção "ROTA-2". A ROTA-1 rodou uma vez em 27/09 e a
conferência B8 recusou quatro correções: pela B7, não houve manifesto. O código
da ROTA-1 está preservado ao lado das saídas dela. A ROTA-2 só ESTREITA a regra:
a declaração de apresentação do anexo passa a exigir o objeto da apresentação e
só vale em notas e demonstrações (grupos 193 e 412).

## O que decide

O formulário (XML do pacote) traz o número bruto. As demonstrações e notas que
a companhia anexou ao MESMO pacote imprimem esse número sob uma unidade que ela
declara. Dígitos iguais numa tabela em milhares → formulário em milhares;
dígitos divididos por mil numa tabela em milhares → formulário em reais. Só a
declaração de milhares decide (tabela S2, RC1-bis); qualquer declaração de reais
ou de milhões VETA.

A linha precisa conter DOIS valores exatos da mesma conta no mesmo formulário
(o corrente e uma âncora), o rótulo da conta, e a unidade tem de valer para ela.
É o que fecha o risco de ESC-0101 (um número casado fora de contexto) sem exigir
o layout de duas linhas da v4.

## O1

A prova por célula lê só contas de balanço, em processos separados. A cadeia da
DFC roda no processo principal: `cadeia_dfc` lê as contas 6.x do formulário E a
6.01 do CSV DENTRO da função e devolve só booleanos (parte 2 do adendo ao O1,
fixado por hash). Nenhum valor, resíduo, sinal ou magnitude de 6.x sai dela; os
trechos publicados trocam todo dígito por `#`.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import random
import re
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import fonte_rad_cvm as rad  # noqa: E402
from scripts import painel_pesquisa_rank03b as pp  # noqa: E402
from src.normalizacao import ordinal_trimestre  # noqa: E402

REGRA = "ROTA-2"
DESTINO = RAIZ / "artefatos" / "rota_prova_rank03b_v2_2026-09-27"
#: A versão anterior, que não produziu manifesto (B7), fica como histórico.
VERSAO_ANTERIOR = RAIZ / "artefatos" / "rota_prova_rank03b_2026-09-27"
#: ROTA-2: a declaração de APRESENTAÇÃO só existe nas notas e demonstrações
#: (193 no ITR, 412 na DFP). Em comentário de desempenho e release, só local.
GRUPOS_COM_APRESENTACAO = frozenset({"193", "412"})
CONTRATO = RAIZ / "resultados" / "contratos_caminho_medicao_rank03b_2026-09-27.md"
ADENDO_O1 = RAIZ / "resultados" / "adendo_o1_rank03b_2026-09-26.md"
#: Cláusula 8 da parte 1 e cláusula 6 da parte 2 do adendo: fixado por hash.
ADENDO_O1_SHA256 = "7f51ab27aff2604e8ec2b3a46f7e39cc12dd8aa82d52a44b2bb47dd158414b0f"
#: B1: o conjunto sai do painel governante SEM correções, e só dele.
DIGEST_GOVERNANTE = "6ca635a904f11140fa24c496a11b77e961f841b72f076edd5650212afe12e6cd"
#: K: os controles do escopo v4, fixados em 16/09 (arquivo conferido por hash).
EVIDENCIAS_V4 = RAIZ / "artefatos" / "painel_pesquisa_rank03b" / "adjudicacao" / "evidencias.jsonl"
EVIDENCIAS_V4_SHA256 = "49ea0bc0043218ac2f60be317642fce53449a34b00f485d3aa5674df0ba43103"
#: B6: os 22 documentos da seleção GEOM-1 (hash publicado no relatório de 18/09).
SELECAO_GEOM1 = RAIZ / "artefatos" / "escala_geometrica_rank03b_2026-09-18" / "selecao.json"
SELECAO_GEOM1_SHA256 = "b3e85417f2bcbc5c157f364bafcf8276cf1da7dcb3713535e58f45ca2431452d"
DOCUMENTOS_GEOM1 = 22
#: B2: versão do extrator de texto fixada no contrato.
POPPLER = "24.02.0"

MODULO_MINIMO = Decimal(1000)
#: B4/B5: tolerância ABSOLUTA, em unidades do valor bruto (adendo, parte 2, item 2).
TOLERANCIA = Decimal(1)
#: Parte F do contrato: páginas lidas para escrever a B3.
DESENHO = frozenset({"98282", "98645", "70099", "145753"})
SEMENTE = 20260911
AMOSTRA_DE_CONFIRMACOES = 10
MINIMO_B6 = 10
#: Leitores em paralelo (a extração de texto domina o custo).
LEITORES = 8

CONTAS_PROVADAS = ("1", "1.01.01", "6.01")
PROVAS_DA_CONTA = {
    "1": ("celula_propria",),
    "1.01.01": ("celula_propria", "elo_balanco"),
    "6.01": ("cadeia_dfc",),
}
VEREDITOS = ("confirmada", "corrigida", "indecidivel")
ESCALAS = ("MIL", "UNIDADE")
FORMAS = ("bruto", "dividido")
#: S2/RC1-bis: só a declaração de milhares decide; a forma diz a escala do formulário.
ESCALA_DA_FORMA = {"bruto": "MIL", "dividido": "UNIDADE"}

# --- vocabulários fechados (B3.4 e B3.5), publicados no pin --------------------------

#: B3.4 — rótulos, sem espaços e em minúsculas.
ROTULOS = {
    "1": ("totaldoativo", "ativototal", "totaldosativos", "totalativo"),
    "1.01.01": ("caixaeequivalentesdecaixa", "caixaeequivalentedecaixa"),
}
#: B3.4 — "Total do ativo circulante" não é o ativo total.
PROIBIDO_NO_ROTULO = {"1": ("circulante",), "1.01.01": ()}
#: B3.4 — a linha "total" do caixa procura o título até tantas linhas acima.
JANELA_DO_TITULO = 15
#: B3.4 — palavras de cabeçalho de tabela (perímetro, data, unidade): uma linha só
#: com elas não é título, e a busca do título a atravessa.
PALAVRAS_DE_CABECALHO = frozenset({
    "controladora", "consolidado", "individual", "nota", "notas", "de", "em", "e", "a", "o",
    "r", "mil", "milhares", "reais", "saldo", "saldos", "janeiro", "fevereiro", "março",
    "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
    "dezembro", "valores", "expressos", "exceto", "quando", "indicado", "outra", "forma",
})
#: B3.5 — declaração de milhares de reais.
UNIDADE_MIL = (
    r"milhares de reais",
    r"milhares de r\$",
    r"\br\$ ?mil\b",
    r"\br\$ ?milhares\b",
)
#: B3.5 — declaração de REAIS como unidade: veta. (Emenda pós-auditoria A2: a
#: primeira versão não pegava "Em reais" sem parêntese, "(R$)" nem "Valores em R$".)
UNIDADE_REAIS = (
    r"\bem reais\b(?!\s*mil)",
    r"\bem real\b(?!\s*mil)",
    r"\bem r\$(?!\s*mil)",
    r"\(reais\)",
    r"\bem unidades de reais\b",
    r"\bem unidades monet[áa]rias\b",
)
#: B3.5 — o SÍMBOLO "R$" sozinho (cabeçalho de coluna, "(R$)"): veta, salvo como
#: moeda da própria declaração de milhares no mesmo segmento ("em milhares de
#: reais – R$"). Número depois de "R$" é valor, não unidade. (Reconferência N1.)
UNIDADE_SIMBOLO = (
    r"\(r\$\)",
    r"(?<![\w$])r\$(?!\s*(?:mil|milh|mm|mi\b|bi\b|\d))",
)
#: Reconferência N1: colunas lado a lado viram segmentos separados (três espaços
#: ou mais na linha crua), e cada segmento é classificado sozinho.
SEPARADOR_DE_COLUNAS = re.compile(r"\s{3,}")
#: B3.5 — declaração de MILHÕES ou mais: veta sempre, sem exceção.
UNIDADE_MILHOES = (
    r"milh[õo]es de reais",
    r"milh[õo]es de r\$",
    r"\br\$ ?milh[õo]es\b",
    r"\br\$ ?mm\b",
    r"\br\$ ?mi\b",
    r"\br\$ ?bi\b",
    r"\bem milh[õo]es\b",
    r"\bem bilh[õo]es\b",
    r"\bbilh[õo]es de reais\b",
)
#: B3.5 — a menção de REAIS numa ressalva por ação, na MESMA linha que declara
#: milhares, é a exceção da própria declaração ("em milhares de reais, exceto o
#: lucro por ação, em reais"). Milhões nunca é neutralizado. (Emenda A2.)
POR_ACAO = re.compile(r"por a[çc](?:ão|ões|ao|oes)")
#: RC1: frase de apresentação no título da página ou depois do objeto apresentado.
INICIO_DE_PAGINA = 300
JANELA_DO_OBJETO = 200

_MIL = [re.compile(p) for p in UNIDADE_MIL]
_REAIS = [re.compile(p) for p in UNIDADE_REAIS]
_SIMBOLO = [re.compile(p) for p in UNIDADE_SIMBOLO]
_MILHOES = [re.compile(p) for p in UNIDADE_MILHOES]
#: B3.3 — número inteiro com separador de milhar; nada colado.
TOKEN = re.compile(r"(?<![\d.,])(\(?)(-?)(\d{1,3}(?:\.\d{3})+)(\)?)(?![\d]|[.,]\d)")


class FormularioInvalido(Exception):
    """O formulário se contradiz (dois valores não nulos da mesma conta e data)."""


#: Erros de LEITURA do pacote (reconferência B-c): viram indecisão do documento.
#: Erro de lógica da regra NÃO está aqui — derruba a execução, à vista.
ERROS_DE_LEITURA = (FormularioInvalido, rad.PacoteInvalido, ET.ParseError, zipfile.BadZipFile,
                    OSError, EOFError, UnicodeDecodeError, KeyError, ValueError)


class RotaIncompativel(Exception):
    """Entrada fixada pelo contrato difere da encontrada: a execução não começa."""


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def normalizar(texto: str) -> str:
    return rad._normalizar(texto)


# --- unidade (B3.5) -------------------------------------------------------------------

def classificar_unidade(texto_normalizado: str) -> str | None:
    """`MIL`, `OUTRA` ou `None` para UM segmento já normalizado.

    Milhões vetam sempre. Reais vetam, salvo na ressalva por ação de um segmento
    que declara milhares. O símbolo "R$" sozinho veta, salvo como moeda de uma
    declaração de milhares do mesmo segmento. Milhares só valem se nada vetar.
    """
    t = texto_normalizado
    if any(p.search(t) for p in _MILHOES):
        return "OUTRA"
    mil = any(p.search(t) for p in _MIL)
    if any(p.search(t) for p in _REAIS) and not (mil and POR_ACAO.search(t)):
        return "OUTRA"
    if any(p.search(t) for p in _SIMBOLO) and not mil:
        return "OUTRA"
    return "MIL" if mil else None


def classificar_linha(bruta: str) -> str | None:
    """Uma linha crua: cada coluna (segmento) sozinha; basta um veto (N1)."""
    classes = {classificar_unidade(normalizar(s))
               for s in SEPARADOR_DE_COLUNAS.split(bruta.strip()) if s.strip()}
    return "OUTRA" if "OUTRA" in classes else ("MIL" if "MIL" in classes else None)


def segmentos_publicaveis(bruta: str) -> str:
    """O trecho de unidade publicado guarda as colunas, separadas por " | "."""
    return " | ".join(s.strip() for s in SEPARADOR_DE_COLUNAS.split(bruta.strip()) if s.strip())


def classificar_trecho(trecho: str) -> str | None:
    """Consumidor: a mesma classificação por coluna, sobre o trecho publicado."""
    classes = {classificar_unidade(normalizar(s)) for s in trecho.split(" | ") if s.strip()}
    return "OUTRA" if "OUTRA" in classes else ("MIL" if "MIL" in classes else None)


def classes_da_pagina(linhas: list[str]) -> tuple[list[str | None], list[bool]]:
    """Classe de cada linha e, para cada linha j, se o par (j−1, j) veta.

    Reconferência N1: uma declaração quebrada entre duas linhas ("(Valores
    expressos em" / "reais)") só aparece no par. O par só acrescenta veto — nunca
    faz uma linha valer milhares."""
    classes = [classificar_linha(l) for l in linhas]
    pares = [False] + [classificar_unidade(normalizar(a + " " + b)) == "OUTRA"
                       for a, b in zip(linhas, linhas[1:])]
    return classes, pares


def apresentacao_do_anexo(paginas: list[str], grupo: str | None = None) -> str | None:
    """RC1 no anexo: `MIL` só se toda declaração de apresentação for de milhares.

    Uma linha de OUTRA unidade é de apresentação se começa nos primeiros 300
    caracteres da página ou se o objeto da apresentação aparece nos 200
    caracteres antes dela ou nela; um par de linhas que veta também conta (N1).

    **ROTA-2:** uma linha de MILHARES só é de apresentação com o objeto da
    apresentação por perto — o título da página sozinho não basta, porque ali
    ficam legendas "(R$ mil)" de tabelas (o caso 60719 da conferência B8 da
    ROTA-1). E só há apresentação em notas e demonstrações (193 e 412).
    """
    if grupo is not None and grupo not in GRUPOS_COM_APRESENTACAO:
        return None
    achadas = set()
    for pagina in paginas:
        brutas = pagina.splitlines()
        linhas = [normalizar(l) for l in brutas]
        classes, pares = classes_da_pagina(brutas)
        corrido, posicao, posicoes = "", 0, []
        for linha in linhas:
            posicoes.append(posicao)
            corrido += linha + " "
            posicao = len(corrido)
        for j, linha in enumerate(linhas):
            classe = "OUTRA" if pares[j] else classes[j]
            if classe is None:
                continue
            inicio = posicoes[j - 1] if pares[j] else posicoes[j]
            antes = corrido[max(0, inicio - JANELA_DO_OBJETO):inicio] + " " + linha
            com_objeto = any(o in antes for o in rad.OBJETOS_DA_APRESENTACAO)
            if com_objeto or (classe == "OUTRA" and inicio < INICIO_DE_PAGINA):
                achadas.add(classe)
    if achadas == {"MIL"}:
        return "MIL"
    if not achadas:
        return None
    return "OUTRA" if achadas == {"OUTRA"} else "misto"


# --- números (B3.3) -------------------------------------------------------------------

@dataclass(frozen=True)
class Token:
    inicio: int
    digitos: str
    negativo: bool


def tokens(linha: str) -> list[Token]:
    """Números inteiros com separador de milhar; parêntese só se fechado dos dois lados."""
    saida = []
    for m in TOKEN.finditer(linha):
        abre, menos, digitos, fecha = m.groups()
        if bool(abre) != bool(fecha):
            continue
        saida.append(Token(m.start(), digitos, bool(abre) or bool(menos)))
    return saida


def formatar(inteiro: Decimal) -> str:
    return f"{int(inteiro):,}".replace(",", ".")


def representacoes(valor: Decimal, forma: str) -> set[str]:
    """Como o valor do formulário aparece impresso na forma dada (módulo ≥ 1.000)."""
    modulo = abs(valor)
    if forma == "bruto":
        if modulo != modulo.to_integral_value() or modulo < MODULO_MINIMO:
            return set()
        return {formatar(modulo)}
    if forma == "dividido":
        q = modulo / Decimal(1000)
        candidatos = {q.quantize(Decimal(1), rounding=ROUND_HALF_UP),
                      q.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)}
        return {formatar(c) for c in candidatos if c >= MODULO_MINIMO}
    raise ValueError(f"forma desconhecida: {forma!r}")


def mascarar(texto: str) -> str:
    """Trecho publicável: todo dígito vira `#` (O1 e contrato B9)."""
    return re.sub(r"\d", "#", texto)


# --- leitura do pacote (B2) -----------------------------------------------------------

def _decimal_xml(texto: str | None) -> Decimal:
    t = (texto or "").strip()
    if not t:
        return Decimal(0)
    try:
        return Decimal(t)
    except InvalidOperation:
        raise FormularioInvalido("valor não numérico no formulário") from None


def _decimal_ptbr(texto: str | None) -> Decimal:
    t = (texto or "").strip()
    if not t:
        return Decimal(0)
    negativo = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(".", "").replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        raise FormularioInvalido("valor não numérico no XML único")
    valor = Decimal(t)
    return -valor if negativo else valor


def e_saldo(conta: str) -> bool:
    return conta == "1" or conta == "2" or conta.startswith(("1.", "2."))


@dataclass
class Formulario:
    formato: str
    membro: str
    #: `{(conta, dt_ini, dt_fim): valor}`; saldo tem `dt_ini = None` e é colapsado
    #: por data (o formulário repete a posição em toda coluna que termina no dia).
    consolidado: dict = field(default_factory=dict)
    individual: dict = field(default_factory=dict)

    def saldo(self, perimetro: str, conta: str, data: date) -> Decimal | None:
        valores = self.consolidado if perimetro == "consolidado" else self.individual
        return valores.get((conta, None, data))


def _acumular(brutos: dict, conta: str, dt_ini, dt_fim, valor: Decimal) -> None:
    if e_saldo(conta):
        chave = (conta, None, dt_fim)
        brutos.setdefault(chave, set())
        if valor != 0:
            brutos[chave].add(valor)
    else:
        brutos.setdefault((conta, dt_ini, dt_fim), set()).add(valor)


def _colapsar(brutos: dict) -> dict:
    saida = {}
    for chave, valores in brutos.items():
        if len(valores) > 1:
            raise FormularioInvalido(f"conta {chave[0]}: valores distintos na mesma data")
        saida[chave] = next(iter(valores)) if valores else Decimal(0)
    return saida


def ler_formulario(caminho: Path, conta_aceita) -> Formulario:
    """Só as contas que `conta_aceita` admite: a prova por célula nunca pede 6.x."""
    membro = rad.validar_pacote(caminho)
    with zipfile.ZipFile(caminho) as externo:
        dados = externo.read(membro)
    consolidado, individual = {}, {}
    if rad.XML_UNICO.fullmatch(membro):
        raiz = ET.fromstring(dados)
        cab = raiz.find(rad.RAIZES_XML_UNICO[raiz.tag])
        periodos = rad.periodos_xml_unico(raiz)
        for caminho_xml, destino in (("Formulario/DfConsolidadas", consolidado),
                                     ("Formulario/DfIndividuais", individual)):
            bloco_raiz = cab.find(caminho_xml)
            for bloco in (bloco_raiz if bloco_raiz is not None else []):
                if bloco.tag not in rad.BLOCOS_XML_UNICO:
                    continue
                for conta in bloco.iter("Conta"):
                    codigo = (conta.findtext("CodigoConta") or "").strip()
                    if not conta_aceita(codigo):
                        continue
                    for coluna in conta:
                        if coluna.tag in rad.NAO_VALOR:
                            continue
                        valor = _decimal_ptbr(coluna.text)
                        if coluna.tag not in periodos:
                            if valor != 0:
                                raise FormularioInvalido(f"conta {codigo}: coluna sem período")
                            continue
                        dt_ini, dt_fim = periodos[coluna.tag]
                        _acumular(destino, codigo, dt_ini, dt_fim, valor)
        return Formulario("xml_unico", membro, _colapsar(consolidado), _colapsar(individual))
    with zipfile.ZipFile(io.BytesIO(dados)) as interno:
        periodos = rad._periodos(interno.read("PeriodoDemonstracaoFinanceira.xml"))
        info = interno.read("InfoFinaDFin.xml")
    for _, elemento in ET.iterparse(io.BytesIO(info), events=("end",)):
        if elemento.tag != "InfoFinaDFin":
            continue
        codigo = (elemento.findtext("PlanoConta/NumeroConta") or "").strip()
        tipo = (elemento.findtext(
            "PlanoConta/VersaoPlanoConta/CodigoTipoInformacaoFinanceira") or "").strip()
        if conta_aceita(codigo) and tipo in (rad.CONSOLIDADO, rad.INDIVIDUAL):
            destino = consolidado if tipo == rad.CONSOLIDADO else individual
            for filho in elemento:
                m = re.fullmatch(r"ValorConta(\d+)", filho.tag)
                if not m:
                    continue
                numero = int(m.group(1))
                valor = _decimal_xml(filho.text)
                if numero not in periodos:
                    if valor != 0:
                        raise FormularioInvalido(f"conta {codigo}: coluna sem período")
                    continue
                dt_ini, dt_fim = periodos[numero]
                _acumular(destino, codigo, dt_ini, dt_fim, valor)
        elemento.clear()
    return Formulario("formulario_zip", membro, _colapsar(consolidado), _colapsar(individual))


@dataclass
class Anexo:
    indice: int
    grupo: str
    arquivo: str
    #: `None` se o PDF não pôde ser lido.
    paginas: list[str] | None


def pdftotext(pdf: bytes) -> list[str] | None:
    """B2: texto por página com `pdftotext -layout`, na versão fixada."""
    with tempfile.TemporaryDirectory() as pasta:
        entrada = Path(pasta) / "anexo.pdf"
        entrada.write_bytes(pdf)
        try:
            r = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(entrada), "-"],
                               capture_output=True, timeout=600)
        except subprocess.TimeoutExpired:
            return None
    if r.returncode != 0:
        return None
    paginas = r.stdout.decode("utf-8", errors="replace").split("\f")
    if paginas and not paginas[-1].strip():
        paginas = paginas[:-1]
    return paginas


def ler_anexos(caminho: Path, extrair=pdftotext) -> list[Anexo]:
    """Todos os PDFs anexados, com o índice do extrator (começa em 0, conta só os não
    vazios — a convenção de `rad._anexos`), o grupo e o nome do arquivo."""
    membro = rad.validar_pacote(caminho)
    with zipfile.ZipFile(caminho) as externo:
        dados = externo.read(membro)
    if not rad.XML_UNICO.fullmatch(membro):
        with zipfile.ZipFile(io.BytesIO(dados)) as interno:
            if "AnexoDocumento.xml" not in interno.namelist():
                return []
            dados = interno.read("AnexoDocumento.xml")
    anexos, indice = [], 0
    for _, elemento in ET.iterparse(io.BytesIO(dados), events=("end",)):
        pdf_b64 = elemento.find("ImagemObjetoArquivoPdf")
        if pdf_b64 is None:
            continue
        conteudo = (pdf_b64.text or "").strip()
        grupo = (elemento.findtext("NumeroGrupoRelacionado") or "").strip()
        arquivo = (elemento.findtext("NomeArquivoPdf") or "").strip()
        elemento.clear()
        if not conteudo:
            continue
        nome = re.split(r"[\\/]", arquivo)[-1]
        anexos.append(Anexo(indice, grupo, nome, extrair(base64.b64decode(conteudo))))
        indice += 1
    return anexos


# --- B3: prova por célula própria -------------------------------------------------------

#: B3.6 — ordem dos estágios, para o motivo "mais avançado" da indecisão.
ESTAGIOS = ("sem_valor", "valor_abaixo_do_minimo", "formulario_diferente_do_csv",
            "sem_ancora", "sem_linha_com_os_dois_numeros", "sem_rotulo",
            "linha_de_acoes", "unidade_local_nao_mil", "sem_unidade_de_milhares",
            "conflitante")


def _sem_espaco(texto: str) -> str:
    return re.sub(r"\s+", "", texto.lower())


def _e_cabecalho(linha: str) -> bool:
    """Linha só de perímetro, data ou unidade: não é título."""
    palavras = re.findall(r"[a-zà-ÿ$]+", linha.lower())
    return all(p in PALAVRAS_DE_CABECALHO for p in palavras)


def titulo_mais_proximo(acima: list[str]) -> str | None:
    """B3.4: subindo a partir da linha, a primeira que não é dado, cabeçalho ou vazia."""
    for linha in reversed(acima[-JANELA_DO_TITULO:]):
        if not re.search(r"[a-zà-ÿ]", linha.lower()) or tokens(linha) or _e_cabecalho(linha):
            continue
        return linha
    return None


def _rotulo_confere(conta: str, linha: str, primeiro: int, acima: list[str]) -> bool:
    rotulo = _sem_espaco(linha[:primeiro])
    if any(r in rotulo for r in ROTULOS[conta]):
        return not any(p in rotulo for p in PROIBIDO_NO_ROTULO[conta])
    if conta == "1.01.01" and re.sub(r"[^a-zà-ÿ]", "", rotulo) == "total":
        titulo = titulo_mais_proximo(acima)
        return titulo is not None and any(r in _sem_espaco(titulo) for r in ROTULOS[conta])
    return False


def provar_celula(formulario: Formulario, anexos: list[Anexo], conta: str,
                  dt_refer: date, valor_csv) -> dict:
    """B3 para uma conta de balanço. Devolve `escala_do_formulario`, motivo, linhas."""
    recusas: Counter = Counter()

    def indecidivel(motivo: str, **extra) -> dict:
        return {"escala_do_formulario": None, "motivo": motivo, "linhas": [],
                "contagem": {f: 0 for f in FORMAS}, "recusas": dict(sorted(recusas.items())),
                **extra}

    v = formulario.saldo("consolidado", conta, dt_refer)
    if not v:
        return indecidivel("sem_valor")
    if abs(v) < MODULO_MINIMO or v < 0:
        return indecidivel("valor_abaixo_do_minimo")
    if valor_csv is None or Decimal(str(valor_csv)) != v:
        return indecidivel("formulario_diferente_do_csv")
    ancoras = []
    for (c, _, data), x in sorted(formulario.consolidado.items(), key=lambda kv: str(kv[0])):
        if c == conta and data != dt_refer and x and x != v and abs(x) >= MODULO_MINIMO:
            ancoras.append((f"consolidado:{data.isoformat()}", x))
    individual = formulario.saldo("individual", conta, dt_refer)
    if individual and individual != v and abs(individual) >= MODULO_MINIMO:
        ancoras.append((f"individual:{dt_refer.isoformat()}", individual))
    if not ancoras:
        return indecidivel("sem_ancora")

    alvos = {}
    for forma in FORMAS:
        alvo_v = representacoes(v, forma)
        alvo_a = {nome: representacoes(x, forma) for nome, x in ancoras}
        alvo_a = {k: s for k, s in alvo_a.items() if s}
        if alvo_v and alvo_a:
            alvos[forma] = (alvo_v, alvo_a)

    aceitas, estagio = [], "sem_linha_com_os_dois_numeros"
    for anexo in anexos:
        if anexo.paginas is None:
            recusas["anexo_ilegivel"] += 1
            continue
        apresentacao = apresentacao_do_anexo(anexo.paginas, anexo.grupo)
        for numero_pagina, pagina in enumerate(anexo.paginas, start=1):
            linhas = pagina.splitlines()
            normais = [normalizar(l) for l in linhas]
            classes, pares = classes_da_pagina(linhas)
            pagina_tem_outra = "OUTRA" in classes or any(pares)
            for i, linha in enumerate(linhas):
                toks = tokens(linha)
                if len(toks) < 2:
                    continue
                for forma, (alvo_v, alvo_a) in alvos.items():
                    ks_v = [k for k, t in enumerate(toks) if t.digitos in alvo_v and not t.negativo]
                    if not ks_v:
                        continue
                    par = next(((kv, ka, nome) for kv in ks_v
                                for ka, t in enumerate(toks) if ka != kv and not t.negativo
                                for nome, alvo in alvo_a.items() if t.digitos in alvo), None)
                    if par is None:
                        continue
                    if not _rotulo_confere(conta, linha, toks[0].inicio, linhas[:i]):
                        recusas["sem_rotulo"] += 1
                        estagio = max(estagio, "sem_rotulo", key=ESTAGIOS.index)
                        continue
                    if rad.LINHA_DE_ACOES.search(normais[i]):
                        recusas["linha_de_acoes"] += 1
                        estagio = max(estagio, "linha_de_acoes", key=ESTAGIOS.index)
                        continue
                    local = next((("OUTRA" if pares[j] else classes[j], j)
                                  for j in range(i, -1, -1) if pares[j] or classes[j]), None)
                    if local is not None:
                        if local[0] != "MIL":
                            recusas["unidade_local_nao_mil"] += 1
                            estagio = max(estagio, "unidade_local_nao_mil", key=ESTAGIOS.index)
                            continue
                        unidade = {"origem": "local", "linha": local[1] + 1,
                                   "trecho": mascarar(segmentos_publicaveis(linhas[local[1]]))}
                    elif apresentacao == "MIL" and not pagina_tem_outra:
                        unidade = {"origem": "apresentacao"}
                    else:
                        recusas["sem_unidade_de_milhares"] += 1
                        estagio = max(estagio, "sem_unidade_de_milhares", key=ESTAGIOS.index)
                        continue
                    kv, ka, ancora = par
                    aceitas.append({
                        "anexo": anexo.indice, "grupo": anexo.grupo, "arquivo": anexo.arquivo,
                        "pagina": numero_pagina, "linha": i + 1, "forma": forma,
                        "ancora": ancora, "posicoes": [kv, ka], "unidade": unidade,
                        "trecho": mascarar(" ".join(linha.split())),
                    })
    contagem = {f: sum(1 for a in aceitas if a["forma"] == f) for f in FORMAS}
    formas = {a["forma"] for a in aceitas}
    if not formas:
        return indecidivel(estagio)
    if len(formas) > 1:
        return indecidivel("conflitante", contagem=contagem)
    forma = formas.pop()
    return {"escala_do_formulario": ESCALA_DA_FORMA[forma], "motivo": None,
            "linhas": aceitas[:5], "linhas_aceitas": len(aceitas), "contagem": contagem,
            "recusas": dict(sorted(recusas.items()))}


# --- B4: elo do balanço -----------------------------------------------------------------

FILHO_DIRETO_DE_1_01 = re.compile(r"1\.01\.\d{2}")


def contas_do_balanco(conta: str) -> bool:
    return conta in ("1", "1.01", "1.02", "1.01.01", "2") or bool(FILHO_DIRETO_DE_1_01.fullmatch(conta))


def elo_balanco(formulario: Formulario, dt_refer: date) -> dict[str, bool]:
    """B4: `1 = 1.01 + 1.02` e `1.01 = soma dos filhos diretos`, com |caixa| ≥ 1.000.

    Emenda B4 da auditoria: com tolerância absoluta de 1, uma âncora de módulo
    pequeno não distingue bases; o piso de 1.000 é o mesmo da prova por célula.
    """
    s = lambda c: formulario.saldo("consolidado", c, dt_refer)  # noqa: E731
    total, circulante, nao_circulante = s("1"), s("1.01"), s("1.02")
    filhos = {c: x for (c, _, data), x in formulario.consolidado.items()
              if data == dt_refer and FILHO_DIRETO_DE_1_01.fullmatch(c)}
    caixa = filhos.get("1.01.01")
    b1 = (total is not None and circulante is not None
          and abs(total - (circulante + (nao_circulante or Decimal(0)))) <= TOLERANCIA)
    b2 = (circulante is not None and caixa is not None and abs(caixa) >= MODULO_MINIMO
          and abs(circulante - sum(filhos.values(), Decimal(0))) <= TOLERANCIA)
    return {"b1": bool(b1), "b2": bool(b2)}


# --- B5: cadeia da DFC (O1: só booleanos) -------------------------------------------------

CONTAS_DA_CADEIA = ("6.01", "6.02", "6.03", "6.04", "6.05", "6.05.01", "6.05.02", "1.01.01")
CADEIA_NAO_CALCULADA = {"d1": None, "d2": None, "d3": None, "igual_ao_csv": None}


def periodo_do_fco(con, chave: tuple) -> tuple[date, date] | None:
    """O período corrente da 6.01 no CSV (`ÚLTIMO`, fim na data de referência).
    Só datas — nenhum valor sai daqui."""
    cd, cj, dt, v = chave
    periodos = con.execute(
        """SELECT DISTINCT dt_ini, dt_fim FROM declaracoes
           WHERE cd_cvm=? AND conjunto=? AND CAST(dt_refer AS VARCHAR)=? AND versao=?
           AND ordem='ÚLTIMO' AND cd_conta='6.01' AND dt_fim = dt_refer""",
        [cd, cj, dt, v]).fetchall()
    return tuple(periodos[0]) if len(periodos) == 1 else None


def cadeia_dfc(caminho: Path, periodo: tuple[date, date], con, chave: tuple) -> dict[str, bool]:
    """B5. Lê as contas 6.x do formulário e a 6.01 do CSV DENTRO desta função e
    devolve SÓ booleanos (adendo ao O1, parte 2: lista fechada, tolerância
    absoluta, saída booleana). Nenhum valor, resíduo, sinal ou magnitude sai daqui.
    """
    try:
        formulario = ler_formulario(caminho, lambda c: c in CONTAS_DA_CADEIA)
    except ERROS_DE_LEITURA:
        # Só a LEITURA vira identidade não fechada; erro de lógica derruba.
        return {"d1": False, "d2": False, "d3": False, "igual_ao_csv": False}
    ini, fim = periodo
    f = lambda c: formulario.consolidado.get((c, ini, fim))  # noqa: E731
    zero = Decimal(0)
    caixa = formulario.saldo("consolidado", "1.01.01", fim)
    f601, f605, f60501, f60502 = f("6.01"), f("6.05"), f("6.05.01"), f("6.05.02")
    d1 = (f601 is not None and f605 is not None
          and abs(f601 + (f("6.02") or zero) + (f("6.03") or zero) + (f("6.04") or zero)
                  - f605) <= TOLERANCIA)
    d2 = (None not in (f60501, f605, f60502)
          and abs(f60501 + f605 - f60502) <= TOLERANCIA)
    d3 = (f60502 is not None and caixa is not None and abs(caixa) >= MODULO_MINIMO
          and abs(f60502 - caixa) <= TOLERANCIA)
    cd, cj, dt, v = chave
    no_csv = {x for (x,) in con.execute(
        """SELECT vl FROM declaracoes WHERE cd_cvm=? AND conjunto=?
           AND CAST(dt_refer AS VARCHAR)=? AND versao=? AND ordem='ÚLTIMO'
           AND cd_conta='6.01' AND dt_ini=? AND dt_fim=?""", [cd, cj, dt, v, ini, fim]).fetchall()}
    igual = (f601 is not None and len(no_csv) == 1 and None not in no_csv
             and Decimal(str(next(iter(no_csv)))) == f601)
    return {"d1": bool(d1), "d2": bool(d2), "d3": bool(d3), "igual_ao_csv": bool(igual)}


# --- um documento ------------------------------------------------------------------------

def _veredito(escala: str | None, declarada: str) -> str:
    if escala is None:
        return "indecidivel"
    return "confirmada" if escala == declarada else "corrigida"


def id_prova(id_doc: str, conta: str) -> str:
    return f"{REGRA}-{id_doc}-{conta}"


def _base(doc: dict) -> dict:
    base = {k: doc[k] for k in ("cd_cvm", "conjunto", "dt_refer", "versao", "id_doc",
                                "sha256_pacote", "papeis", "desenho", "geom1",
                                "escala_declarada")}
    base["regra"] = REGRA
    return base


def registro(doc: dict, conta: str, prova: str, escala: str | None, motivo: str | None,
             **extra) -> dict:
    return {**_base(doc), "id_prova": id_prova(doc["id_doc"], conta), "conta": conta,
            "prova": prova, "escala_do_formulario": escala,
            "veredito": _veredito(escala, doc["escala_declarada"]), "motivo": motivo, **extra}


def escalas_do_pacote(caminho: Path) -> dict:
    """Informação para a conferência (ROTA-2, item 4): o código de escala do
    envelope RAD (o que o CSV e o painel carregam) e o do formulário da companhia.
    Não decide nada; a escala declarada da regra é a do painel."""
    saida = {"envelope": None, "formulario": None}
    try:
        with zipfile.ZipFile(caminho) as externo:
            nomes = externo.namelist()
            envelope = next((n for n in nomes if n.startswith(rad.PREFIXO_FORMULARIO)), None)
            if envelope:
                saida["envelope"] = (ET.fromstring(externo.read(envelope)).findtext(".//CodigoEscalaMoeda")
                                     or "").strip() or None
            membro = rad.validar_pacote(caminho)
            dados = externo.read(membro)
        if rad.XML_UNICO.fullmatch(membro):
            raiz = ET.fromstring(dados)
            saida["formulario"] = (raiz.find(rad.RAIZES_XML_UNICO[raiz.tag]).findtext("EscalaMoeda")
                                   or "").strip() or None
        else:
            with zipfile.ZipFile(io.BytesIO(dados)) as interno:
                form = next(n for n in interno.namelist() if n.startswith(rad.PREFIXO_FORMULARIO))
                saida["formulario"] = (ET.fromstring(interno.read(form)).findtext(".//CodigoEscalaMoeda")
                                       or "").strip() or None
    except ERROS_DE_LEITURA + (StopIteration,):
        pass
    return saida


def adjudicar_saldos(doc: dict) -> list[dict]:
    """B3 e B4: os registros das contas `1` e `1.01.01`. Função de módulo, para ir
    a outro processo — e NÃO lê conta 6.x (O1). Erro de um documento vira
    indecisão dele, com o tipo do erro, e não derruba a execução (emenda B8)."""
    if doc.get("sem_pacote"):
        return [registro(doc, c, PROVAS_DA_CONTA[c][0], None, "sem_pacote") for c in ("1", "1.01.01")]
    caminho = rad.BRUTOS / f"{doc['id_doc']}.zip"
    dt_refer = date.fromisoformat(doc["dt_refer"])
    try:
        formulario = ler_formulario(caminho, contas_do_balanco)
        anexos = ler_anexos(caminho)
    except ERROS_DE_LEITURA as erro:  # o tipo vai ao registro; a mensagem, não
        motivo = f"leitura:{type(erro).__name__}"
        return [registro(doc, c, PROVAS_DA_CONTA[c][0], None, motivo) for c in ("1", "1.01.01")]
    membro = formulario.membro
    codigos = escalas_do_pacote(caminho)
    ativo = provar_celula(formulario, anexos, "1", dt_refer, doc["csv"].get("1"))
    caixa = provar_celula(formulario, anexos, "1.01.01", dt_refer, doc["csv"].get("1.01.01"))
    elo = elo_balanco(formulario, dt_refer)
    registros = [registro(doc, "1", "celula_propria", ativo.pop("escala_do_formulario"),
                          ativo.pop("motivo"), xml_membro=membro, codigos_de_escala=codigos, **ativo)]
    if caixa["escala_do_formulario"] is not None:
        registros.append(registro(doc, "1.01.01", "celula_propria", caixa.pop("escala_do_formulario"),
                                  caixa.pop("motivo"), xml_membro=membro, **caixa))
        return registros
    escala_ativo = registros[0]["escala_do_formulario"]
    if escala_ativo is not None and elo["b1"] and elo["b2"]:
        registros.append(registro(doc, "1.01.01", "elo_balanco", escala_ativo, None,
                                  xml_membro=membro,
                                  elo={**elo, "ancora": id_prova(doc["id_doc"], "1")}))
    else:
        motivo = "sem_prova_do_ativo" if escala_ativo is None else "identidade_do_balanco_aberta"
        registros.append(registro(doc, "1.01.01", "celula_propria", None,
                                  f"{caixa['motivo']}|elo:{motivo}", xml_membro=membro,
                                  elo={**elo, "ancora": None}, recusas=caixa["recusas"],
                                  contagem=caixa["contagem"], linhas=[]))
    return registros


def adjudicar_fco(doc: dict, ancora: dict | None, con) -> dict:
    """B5 no processo principal. Sem âncora do caixa, a 6.x nem é lida (O1)."""
    if doc.get("sem_pacote"):
        return registro(doc, "6.01", "cadeia_dfc", None, "sem_pacote",
                        cadeia={**CADEIA_NAO_CALCULADA, "ancora": None})
    referencia = id_prova(doc["id_doc"], "1.01.01")
    if ancora is None or ancora["escala_do_formulario"] is None:
        return registro(doc, "6.01", "cadeia_dfc", None, "sem_ancora_do_caixa",
                        cadeia={**CADEIA_NAO_CALCULADA, "ancora": referencia})
    chave = (doc["cd_cvm"], doc["conjunto"], doc["dt_refer"], int(doc["versao"]))
    periodo = periodo_do_fco(con, chave)
    if periodo is None:
        return registro(doc, "6.01", "cadeia_dfc", None, "sem_periodo_do_fco",
                        cadeia={**CADEIA_NAO_CALCULADA, "ancora": referencia})
    cadeia = cadeia_dfc(rad.BRUTOS / f"{doc['id_doc']}.zip", periodo, con, chave)
    if all(cadeia.values()):
        return registro(doc, "6.01", "cadeia_dfc", ancora["escala_do_formulario"], None,
                        cadeia={**cadeia, "ancora": referencia})
    return registro(doc, "6.01", "cadeia_dfc", None, "cadeia_aberta",
                    cadeia={**cadeia, "ancora": referencia})


# --- validação (produtor E consumidor) --------------------------------------------------

CAMPOS_COMUNS = ("id_prova", "regra", "cd_cvm", "conjunto", "dt_refer", "versao", "id_doc",
                 "sha256_pacote", "papeis", "desenho", "geom1", "conta", "prova",
                 "escala_declarada", "escala_do_formulario", "veredito", "motivo")


class EvidenciaInvalida(AssertionError):
    """Registro da ROTA-1 que não se sustenta sozinho."""


def validar_registro(r: dict) -> None:
    """A mesma função no produtor e no consumidor (contrato A2.4, §4.4 regra 7)."""
    faltam = [k for k in CAMPOS_COMUNS if k not in r]
    if faltam:
        raise EvidenciaInvalida(f"campos ausentes: {faltam}")
    ident = r["id_prova"]
    if r["regra"] != REGRA or r["conta"] not in CONTAS_PROVADAS:
        raise EvidenciaInvalida(f"{ident}: regra ou conta fora do contrato")
    if r["prova"] not in PROVAS_DA_CONTA[r["conta"]]:
        raise EvidenciaInvalida(f"{ident}: prova {r['prova']!r} não serve à conta {r['conta']}")
    if ident != id_prova(r["id_doc"], r["conta"]):
        raise EvidenciaInvalida(f"{ident}: identificador não corresponde ao documento")
    if r["escala_declarada"] not in ESCALAS or r["veredito"] not in VEREDITOS:
        raise EvidenciaInvalida(f"{ident}: vocabulário")
    escala = r["escala_do_formulario"]
    if (escala is None) != (r["veredito"] == "indecidivel"):
        raise EvidenciaInvalida(f"{ident}: veredito e escala não conferem")
    if escala is None:
        return
    if escala not in ESCALAS or r["veredito"] != _veredito(escala, r["escala_declarada"]):
        raise EvidenciaInvalida(f"{ident}: veredito diferente do que a escala implica")
    if r["motivo"] is not None:
        raise EvidenciaInvalida(f"{ident}: decisão com motivo de indecisão")
    if r["prova"] == "celula_propria":
        forma = next(f for f, e in ESCALA_DA_FORMA.items() if e == escala)
        outra = next(f for f in FORMAS if f != forma)
        linhas = r.get("linhas") or []
        contagem = r.get("contagem") or {}
        # Emenda M4: a outra forma tem de ter contagem ZERO; senão é conflito.
        if not linhas or contagem.get(forma, 0) < len(linhas) or contagem.get(outra, 0) != 0:
            raise EvidenciaInvalida(f"{ident}: prova por célula sem linhas só da forma decidida")
        for linha in linhas:
            ok = (linha.get("forma") == forma
                  and type(linha.get("anexo")) is int and linha["anexo"] >= 0
                  and all(type(linha.get(k)) is int and linha[k] > 0 for k in ("pagina", "linha"))
                  and isinstance(linha.get("posicoes"), list) and len(linha["posicoes"]) == 2
                  and linha["posicoes"][0] != linha["posicoes"][1]
                  and isinstance(linha.get("ancora"), str)
                  and re.fullmatch(r"(consolidado|individual):\d{4}-\d{2}-\d{2}", linha["ancora"])
                  and isinstance(linha.get("unidade"), dict)
                  and linha["unidade"].get("origem") in ("local", "apresentacao")
                  # ROTA-2: apresentação só em notas e demonstrações (§4.4, regra 7).
                  and (linha["unidade"]["origem"] == "local"
                       or linha.get("grupo") in GRUPOS_COM_APRESENTACAO)
                  and isinstance(linha.get("trecho"), str) and not re.search(r"\d", linha["trecho"]))
            if linha.get("unidade", {}).get("origem") == "local":
                ok = ok and type(linha["unidade"].get("linha")) is int and \
                    linha["unidade"]["linha"] <= linha["linha"] and \
                    not re.search(r"\d", linha["unidade"].get("trecho", "0")) and \
                    classificar_trecho(linha["unidade"]["trecho"].replace("#", "0")) == "MIL"
            if not ok:
                raise EvidenciaInvalida(f"{ident}: linha de prova fora do escopo da B3")
    elif r["prova"] == "elo_balanco":
        elo = r.get("elo") or {}
        if not (elo.get("b1") is True and elo.get("b2") is True
                and elo.get("ancora") == id_prova(r["id_doc"], "1")):
            raise EvidenciaInvalida(f"{ident}: elo do balanço sem as duas identidades")
    elif r["prova"] == "cadeia_dfc":
        cadeia = r.get("cadeia") or {}
        if not (all(cadeia.get(k) is True for k in ("d1", "d2", "d3", "igual_ao_csv"))
                and cadeia.get("ancora") == id_prova(r["id_doc"], "1.01.01")):
            raise EvidenciaInvalida(f"{ident}: cadeia da DFC sem as identidades fechadas")


def documentos_geom1() -> frozenset[str]:
    """Os 22 ids da seleção GEOM-1, do arquivo conferido por hash (emenda A1:
    a primeira versão tomava o dicionário inteiro como id)."""
    if sha256(SELECAO_GEOM1) != SELECAO_GEOM1_SHA256:
        raise RotaIncompativel("selecao.json da GEOM-1 com hash diferente do publicado")
    selecao = json.loads(SELECAO_GEOM1.read_text(encoding="utf-8"))
    ids = frozenset(str(d["id_doc"]) for k in ("desenho", "verificacao", "sentinelas")
                    for d in selecao[k])
    if len(ids) != DOCUMENTOS_GEOM1:
        raise RotaIncompativel(f"seleção GEOM-1 com {len(ids)} documentos, esperados 22")
    return ids


def controles() -> dict[tuple, str]:
    """K: os 30 controles do escopo v4 (companhias só MIL, ordem de 16/09)."""
    if sha256(EVIDENCIAS_V4) != EVIDENCIAS_V4_SHA256:
        raise RotaIncompativel("evidências v4 com hash diferente do fixado")
    saida = {}
    for linha in EVIDENCIAS_V4.read_text(encoding="utf-8").splitlines():
        r = json.loads(linha)
        if r["papel"] == "controle":
            saida[(r["cd_cvm"], r["conjunto"], r["dt_refer"], int(r["versao"]))] = r["id_doc"]
    if len(saida) != 30:
        raise RotaIncompativel(f"controles: {len(saida)}, esperados 30")
    return saida


def conferir_marcas(registros: list[dict], geom1: frozenset[str] | None = None,
                    chaves_de_controle=None) -> None:
    """Emenda B7: o consumidor recalcula desenho, GEOM-1 e controle das fontes
    fixadas, em vez de confiar nas marcas gravadas."""
    geom1 = documentos_geom1() if geom1 is None else geom1
    chaves_de_controle = set(controles()) if chaves_de_controle is None else set(chaves_de_controle)
    presentes = {(r["cd_cvm"], r["conjunto"], r["dt_refer"], int(r["versao"])) for r in registros}
    if chaves_de_controle - presentes:
        # Reconferência B-d: os controles K têm de estar todos nas evidências.
        raise EvidenciaInvalida(f"{len(chaves_de_controle - presentes)} controles ausentes das evidências")
    for r in registros:
        chave = (r["cd_cvm"], r["conjunto"], r["dt_refer"], int(r["versao"]))
        if r["desenho"] != (r["id_doc"] in DESENHO) or r["geom1"] != (r["id_doc"] in geom1) \
                or ("controle" in r["papeis"]) != (chave in chaves_de_controle):
            raise EvidenciaInvalida(f"{r['id_prova']}: marca de desenho, GEOM-1 ou controle adulterada")


def teste_b6(registros: list[dict]) -> dict:
    """B6: concordância ativo × caixa (ambos por célula própria), fora do desenho."""
    por_doc = defaultdict(dict)
    for r in registros:
        if r["prova"] == "celula_propria" and r["escala_do_formulario"] is not None \
                and not r["desenho"] and not r["geom1"]:
            por_doc[r["id_doc"]][r["conta"]] = r["escala_do_formulario"]
    pares = {d: v for d, v in por_doc.items() if {"1", "1.01.01"} <= v.keys()}
    discordantes = sorted(d for d, v in pares.items() if v["1"] != v["1.01.01"])
    return {"documentos": len(pares), "discordancias": len(discordantes),
            "documentos_discordantes": discordantes, "minimo": MINIMO_B6,
            "aprovado": len(pares) >= MINIMO_B6 and not discordantes}


def aplicar_b6(registros: list[dict]) -> dict:
    """B6 reprovado: elo do balanço e cadeia da DFC não produzem prova (contrato B6)."""
    b6 = teste_b6(registros)
    if not b6["aprovado"]:
        for r in registros:
            if r["prova"] in ("elo_balanco", "cadeia_dfc") and r["escala_do_formulario"] is not None:
                r.update(escala_do_formulario=None, veredito="indecidivel",
                         motivo="teste_b6_reprovado")
    return b6


def validar_arquivo(registros: list[dict], geom1=None, chaves_de_controle=None) -> dict:
    """Arquivo inteiro: marcas, unicidade, âncoras, B6 e parada por controle (B7)."""
    conferir_marcas(registros, geom1, chaves_de_controle)
    vistos = set()
    por_id = {}
    for r in registros:
        validar_registro(r)
        chave = (r["id_doc"], r["conta"])
        if chave in vistos:
            raise EvidenciaInvalida(f"{r['id_prova']}: documento e conta repetidos")
        vistos.add(chave)
        por_id[r["id_prova"]] = r
    b6 = teste_b6(registros)
    for r in registros:
        if r["escala_do_formulario"] is None or r["prova"] == "celula_propria":
            continue
        referencia = (r.get("elo") or r.get("cadeia") or {}).get("ancora")
        ancora = por_id.get(referencia)
        if ancora is None or ancora["escala_do_formulario"] != r["escala_do_formulario"] \
                or ancora["id_doc"] != r["id_doc"]:
            raise EvidenciaInvalida(f"{r['id_prova']}: âncora ausente ou de outra escala")
        if not b6["aprovado"]:
            raise EvidenciaInvalida(f"{r['id_prova']}: elo ou cadeia com o teste B6 reprovado")
    controles_corrigidos = sorted(r["id_prova"] for r in registros
                                  if "controle" in r["papeis"] and r["veredito"] == "corrigida")
    return {"registros": len(registros), "b6": b6,
            "controles_corrigidos": controles_corrigidos,
            "parada": bool(controles_corrigidos)}


def ler_evidencias(caminho: Path) -> tuple[list[dict], str]:
    dados = caminho.read_bytes()
    registros = [json.loads(l) for l in dados.decode("utf-8").splitlines() if l.strip()]
    return registros, hashlib.sha256(dados).hexdigest()


def ler_conferencia(caminho: Path) -> tuple[dict, str]:
    dados = caminho.read_bytes()
    return json.loads(dados.decode("utf-8")), hashlib.sha256(dados).hexdigest()


def correcoes_exigidas(registros: list[dict]) -> list[str]:
    """B8: toda correção passa pela conferência (inclusive a do caixa que ancora o FCO)."""
    return sorted(r["id_prova"] for r in registros if r["veredito"] == "corrigida")


def amostra_de_confirmacoes(registros: list[dict]) -> list[str]:
    """B8: dez confirmações sorteadas com a semente fixa — recalculável por quem confere."""
    confirmacoes = sorted(r["id_prova"] for r in registros if r["veredito"] == "confirmada")
    return sorted(random.Random(SEMENTE).sample(confirmacoes,
                                                min(AMOSTRA_DE_CONFIRMACOES, len(confirmacoes))))


def validar_conferencia(conferencia: dict, registros: list[dict], sha_evidencias: str) -> None:
    """B7/B8: a conferência é destas evidências, cobre toda correção e a amostra de
    confirmações, e não recusou NENHUMA das duas (emenda M5)."""
    if conferencia.get("regra") != REGRA or conferencia.get("sha256_evidencias") != sha_evidencias:
        raise EvidenciaInvalida("conferência de outras evidências")
    for campo, exigidos in (("correcoes", correcoes_exigidas(registros)),
                            ("confirmacoes", amostra_de_confirmacoes(registros))):
        resultados = conferencia.get(campo)
        if not isinstance(resultados, dict):
            raise EvidenciaInvalida(f"conferência sem o campo {campo}")
        faltam = [i for i in exigidos if i not in resultados]
        if faltam:
            raise EvidenciaInvalida(f"{campo} sem conferência: {faltam[:3]}")
        recusadas = sorted(i for i, c in resultados.items() if c.get("resultado") != "aprovada")
        if recusadas:
            raise EvidenciaInvalida(f"a conferência recusou {campo}: {recusadas[:3]}")


def vereditos_por_conta(pasta: Path = DESTINO) -> dict:
    """A4: `{"ativo": {chave}, "fco": {chave}}` dos documentos decididos, SÓ com
    evidências válidas, sem parada e com a conferência aprovada. O FCO só é
    decidido pela cadeia da DFC (§12-bis): prova de saldo não decide o FCO."""
    registros, sha_ev = ler_evidencias(pasta / "evidencias.jsonl")
    resumo = validar_arquivo(registros)
    if resumo["parada"]:
        raise EvidenciaInvalida("parada B7: controle corrigido")
    conferencia, sha_conf = ler_conferencia(pasta / "conferencia.json")
    validar_conferencia(conferencia, registros, sha_ev)
    saida = {"ativo": set(), "fco": set(), "escalas": {},
             "sha256_evidencias": sha_ev, "sha256_conferencia": sha_conf}
    for r in registros:
        if r["escala_do_formulario"] is None:
            continue
        chave = (r["cd_cvm"], r["conjunto"], r["dt_refer"], int(r["versao"]))
        if r["conta"] == "1" and r["prova"] == "celula_propria":
            saida["ativo"].add(chave)
            saida["escalas"][(chave, "ativo")] = r["escala_do_formulario"]
        elif r["conta"] == "6.01" and r["prova"] == "cadeia_dfc":
            saida["fco"].add(chave)
            saida["escalas"][(chave, "fco")] = r["escala_do_formulario"]
    return saida


# --- conjunto (B1) -----------------------------------------------------------------------

def _chave(linha: dict) -> tuple:
    return (linha["cd_cvm"], linha["conjunto"], linha["dt_refer"], int(linha["versao"]))


def populacao_v2(painel: pp.Painel) -> set[str]:
    """§3.2 do rascunho: sem `ll3_13_%` (o painel já exclui `ll3_09_%` e bancos)."""
    return {l["cd_cvm"] for l in painel.ativo + painel.fco_trimestral
            if not str(l.get("plano_contas") or "").startswith("ll3_13_")}


def saltos_do_ativo(linhas_validas: list[dict]) -> list[tuple[dict, dict]]:
    """Os pares do G0.3: linhas válidas consecutivas, ordinais adjacentes, razão ≥ 100."""
    por_cia = defaultdict(list)
    for linha in linhas_validas:
        por_cia[linha["cd_cvm"]].append(linha)
    pares = []
    for cd, linhas in sorted(por_cia.items()):
        linhas.sort(key=lambda l: ordinal_trimestre(l["trimestre"]))
        for a, b in zip(linhas, linhas[1:]):
            if not a["valor_reais"] or not b["valor_reais"]:
                continue
            if ordinal_trimestre(b["trimestre"]) - ordinal_trimestre(a["trimestre"]) != 1:
                continue
            maior = max(abs(a["valor_reais"]), abs(b["valor_reais"]))
            menor = min(abs(a["valor_reais"]), abs(b["valor_reais"]))
            if maior / menor >= 100:
                pares.append((a, b))
    return pares


def conjunto_alvo(painel: pp.Painel) -> dict[tuple, set[str]]:
    """B1: `{chave do documento: {papéis}}` — T_A, T_B e T_C. Só estrutura."""
    populacao = populacao_v2(painel)
    validas = [l for l in painel.ativo if l["estado"] == "valido" and l["cd_cvm"] in populacao]
    pares = saltos_do_ativo(validas)
    papeis: dict[tuple, set[str]] = defaultdict(set)
    for a, b in pares:
        papeis[_chave(a)].add("T_B")
        papeis[_chave(b)].add("T_B")
    no_salto = {id(a) for a, _ in pares}
    por_cia = defaultdict(list)
    for linha in validas:
        por_cia[linha["cd_cvm"]].append(linha)
    com_salto = {a["cd_cvm"] for a, _ in pares}
    for cd in sorted(com_salto):
        linhas = sorted(por_cia[cd], key=lambda l: ordinal_trimestre(l["trimestre"]))
        contagem = Counter(l["escala_declarada"] for l in linhas)
        maximo = max(contagem.values())
        majoritarias = {e for e, n in contagem.items() if n == maximo}
        trechos, atual = [], [linhas[0]]
        for anterior, linha in zip(linhas, linhas[1:]):
            if id(anterior) in no_salto:
                trechos.append(atual)
                atual = []
            atual.append(linha)
        trechos.append(atual)
        for i, trecho in enumerate(trechos):
            toca = i > 0 or i < len(trechos) - 1
            escalas = {l["escala_declarada"] for l in trecho}
            minoritario = len(majoritarias) > 1 or escalas != majoritarias
            if toca and minoritario:
                for linha in trecho:
                    papeis[_chave(linha)].add("T_A")
    for t in painel.fco_trimestral:
        if t["estado"] != "valido" or t["cd_cvm"] not in populacao:
            continue
        if len(set(t["escalas_declaradas"].split("+"))) > 1:
            for o in json.loads(t["operandos"]):
                papeis[(t["cd_cvm"], o["conjunto"], o["dt_refer"], int(o["versao"]))].add("T_C")
    return dict(papeis)


# --- execução ----------------------------------------------------------------------------

def versao_do_poppler() -> str:
    r = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True)
    m = re.search(r"pdftotext version (\S+)", r.stderr + r.stdout)
    return m.group(1) if m else "desconhecida"


def saldos_do_csv(con, chave: tuple) -> dict:
    """B3.1: os saldos que o painel usa, do CSV (`declaracoes`, `ÚLTIMO`). Só contas 1."""
    cd, cj, dt, v = chave
    saldos = {}
    for conta, valor in con.execute(
            """SELECT cd_conta, vl FROM declaracoes WHERE cd_cvm=? AND conjunto=?
               AND CAST(dt_refer AS VARCHAR)=? AND versao=? AND ordem='ÚLTIMO'
               AND cd_conta IN ('1','1.01.01') AND dt_fim = dt_refer""",
            [cd, cj, dt, v]).fetchall():
        saldos.setdefault(conta, set()).add(valor)
    return {c: next(iter(s)) for c, s in saldos.items() if len(s) == 1}


def _codigo() -> dict[str, str]:
    return {str(p.relative_to(RAIZ)): sha256(p) for p in (
        Path(__file__), RAIZ / "scripts" / "painel_pesquisa_rank03b.py",
        RAIZ / "scripts" / "fonte_rad_cvm.py", RAIZ / "scripts" / "fonte_zip_cvm.py",
        RAIZ / "src" / "normalizacao.py")}


def executar(destino: Path = DESTINO, leitores: int = LEITORES) -> dict:
    """Aplica a regra, uma vez, a T ∪ K. Recusa sobrescrever."""
    if destino.exists():
        raise FileExistsError(f"{destino} já existe: a ROTA-1 não reexecuta sobre a mesma saída")
    if sha256(ADENDO_O1) != ADENDO_O1_SHA256:
        raise RotaIncompativel("adendo ao O1 com hash diferente do fixado")
    if versao_do_poppler() != POPPLER:
        raise RotaIncompativel(f"Poppler {versao_do_poppler()}, contrato fixa {POPPLER}")
    import duckdb
    from scripts import adjudicar_escala_rank03b as adj
    from scripts import fonte_zip_cvm as fz

    geom1 = documentos_geom1()
    chaves_de_controle = controles()
    con = duckdb.connect(":memory:")
    zips = fz.extrair(con)
    hash_treino = pp.preparar_universo(con)
    painel = pp.construir(con)
    if painel.digest["conjunto"] != DIGEST_GOVERNANTE:
        raise RotaIncompativel("o painel sem correções não é o governante de 18/09")
    alvos = conjunto_alvo(painel)
    for chave in chaves_de_controle:
        alvos.setdefault(chave, set()).add("controle")
    integros = adj.pacotes_integros()
    documentos = []
    for chave, papeis in sorted(alvos.items()):
        doc = painel.documentos[chave]
        id_doc = doc.id_doc
        pacote = rad.BRUTOS / f"{id_doc}.zip"
        hashes = integros.get(id_doc, set())
        sem_pacote = "," in id_doc or not pacote.is_file() or len(hashes) != 1
        sha_pacote = next(iter(hashes)) if len(hashes) == 1 else None
        if not sem_pacote and sha256(pacote) != sha_pacote:
            raise RotaIncompativel(f"pacote {id_doc} diferente do manifesto de aquisição")
        documentos.append({
            "cd_cvm": chave[0], "conjunto": chave[1], "dt_refer": chave[2], "versao": chave[3],
            "id_doc": id_doc, "sha256_pacote": sha_pacote, "papeis": sorted(papeis),
            "desenho": id_doc in DESENHO, "geom1": id_doc in geom1,
            "escala_declarada": doc.escala_declarada, "sem_pacote": sem_pacote,
            "csv": {} if sem_pacote else saldos_do_csv(con, chave),
        })
    conjunto = [{k: d[k] for k in ("cd_cvm", "conjunto", "dt_refer", "versao", "id_doc",
                                   "papeis", "sem_pacote")} for d in documentos]
    pin = {
        "regra": REGRA, "contrato": str(CONTRATO.relative_to(RAIZ)), "contrato_sha256": sha256(CONTRATO),
        "adendo_o1_sha256": ADENDO_O1_SHA256, "poppler": POPPLER, "codigo_sha256": _codigo(),
        "painel_governante_digest": DIGEST_GOVERNANTE, "zips_sha256": zips,
        "versao_anterior": {"pasta": str(VERSAO_ANTERIOR.relative_to(RAIZ)),
                            "evidencias_sha256": sha256(VERSAO_ANTERIOR / "evidencias.jsonl"),
                            "conferencia_sha256": sha256(VERSAO_ANTERIOR / "conferencia.json"),
                            "pin_sha256": sha256(VERSAO_ANTERIOR / "pin.json"),
                            "codigo_sha256": sha256(VERSAO_ANTERIOR / "codigo_rota_1.py"),
                            "resultado": "B7: quatro recusas na conferência, sem manifesto"},
        "cvm_treino_sha256": hash_treino,
        "manifesto_aquisicao_sha256": sha256(rad.MANIFESTO),
        "conjunto_sha256": hashlib.sha256(json.dumps(conjunto, sort_keys=True).encode()).hexdigest(),
        "conjunto": conjunto,
        "geom1": {"selecao_sha256": SELECAO_GEOM1_SHA256, "documentos": sorted(geom1)},
        "controles": {"evidencias_v4_sha256": EVIDENCIAS_V4_SHA256,
                      "documentos": sorted(chaves_de_controle.values())},
        "vocabularios": {"rotulos": ROTULOS, "proibido_no_rotulo": PROIBIDO_NO_ROTULO,
                         "palavras_de_cabecalho": sorted(PALAVRAS_DE_CABECALHO),
                         "unidade_mil": UNIDADE_MIL, "unidade_reais": UNIDADE_REAIS,
                         "unidade_milhoes": UNIDADE_MILHOES, "unidade_simbolo": UNIDADE_SIMBOLO,
                         "separador_de_colunas": SEPARADOR_DE_COLUNAS.pattern,
                         "grupos_com_apresentacao": sorted(GRUPOS_COM_APRESENTACAO),
                         "objetos_da_apresentacao": list(rad.OBJETOS_DA_APRESENTACAO),
                         "por_acao": POR_ACAO.pattern,
                         "janela_do_titulo": JANELA_DO_TITULO},
        "parametros": {"modulo_minimo": str(MODULO_MINIMO), "tolerancia": str(TOLERANCIA),
                       "desenho": sorted(DESENHO), "minimo_b6": MINIMO_B6,
                       "semente": SEMENTE, "amostra_de_confirmacoes": AMOSTRA_DE_CONFIRMACOES},
    }
    destino.mkdir(parents=True)
    # O pin é gravado ANTES de ler qualquer pacote: conjunto e regra ficam fixos.
    (destino / "pin.json").write_text(json.dumps(pin, ensure_ascii=False, indent=2, sort_keys=True),
                                      encoding="utf-8")
    try:
        if leitores <= 1:
            resultados = [adjudicar_saldos(d) for d in documentos]
        else:
            with ProcessPoolExecutor(max_workers=leitores) as pool:
                resultados = list(pool.map(adjudicar_saldos, documentos, chunksize=2))
        registros = []
        for doc, saldos in zip(documentos, resultados):
            ancora = next((r for r in saldos if r["conta"] == "1.01.01"), None)
            registros += saldos + [adjudicar_fco(doc, ancora, con)]
        registros.sort(key=lambda r: (r["cd_cvm"], r["dt_refer"], r["conjunto"], r["versao"], r["conta"]))
        aplicar_b6(registros)
        resumo_arquivo = validar_arquivo(registros, geom1, chaves_de_controle)
    except Exception as erro:
        # Defeito da regra ou do código: fica registrado ao lado do pin, sem
        # evidência nenhuma. Rodar de novo exige destino novo e declaração.
        (destino / "falha.json").write_text(json.dumps({"erro": type(erro).__name__}),
                                            encoding="utf-8")
        raise
    conteudo = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str) + "\n"
                       for r in registros)
    (destino / "evidencias.jsonl").write_text(conteudo, encoding="utf-8")
    resumo = resumir(registros, resumo_arquivo)
    resumo["sha256_evidencias"] = sha256(destino / "evidencias.jsonl")
    (destino / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2, sort_keys=True),
                                         encoding="utf-8")
    return resumo


def resumir(registros: list[dict], resumo_arquivo: dict) -> dict:
    def contar(filtro, chave):
        return dict(sorted(Counter(chave(r) for r in registros if filtro(r)).items()))

    return {
        "regra": REGRA,
        "documentos": len({r["id_doc"] for r in registros}),
        "por_conta_e_veredito": contar(lambda r: True, lambda r: f"{r['conta']}|{r['prova']}|{r['veredito']}"),
        "por_papel_conta_e_veredito": contar(
            lambda r: True, lambda r: f"{'+'.join(r['papeis'])}|{r['conta']}|{r['veredito']}"),
        "motivos_de_indecisao": contar(lambda r: r["veredito"] == "indecidivel",
                                       lambda r: f"{r['conta']}|{(r['motivo'] or '').split('|')[0]}"),
        "correcoes_para_conferencia": correcoes_exigidas(registros),
        "amostra_de_confirmacoes_para_conferencia": amostra_de_confirmacoes(registros),
        "teste_b6": resumo_arquivo["b6"],
        "controles_corrigidos": resumo_arquivo["controles_corrigidos"],
        "parada": resumo_arquivo["parada"],
    }


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--leitores", type=int, default=LEITORES)
    args = parser.parse_args(argv)
    resumo = executar(leitores=args.leitores)
    print(json.dumps({k: resumo[k] for k in ("documentos", "por_conta_e_veredito", "teste_b6",
                                             "controles_corrigidos", "parada")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
