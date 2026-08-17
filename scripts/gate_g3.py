"""Gate G3 — o OCR de documento supera o parser posicional NESTE corpus? (spec 5.3)

A spec autoriza reverter a decisão de trocar o extrator se o OCR não superar
visivelmente o `pdfplumber` neste corpus específico. O gate é o que produz a
evidência dessa decisão, em vez de aceitá-la por reputação do fornecedor.

Duas medições, e a segunda é a que importa:

1. **Valor-âncora por documento** (`corpus/ancoras_sentinela.csv`): o número de
   capa aparece no texto extraído, após normalização pt-BR? Mede se o extrator
   acha o dado que as perguntas factuais perseguem.
2. **Densidade de estrutura de tabela**: quantas linhas de tabela cada extrator
   reconstrói. É onde o modo de falha nº 2 vive — *"extração de PDF quebra em
   tabelas, que é onde os números moram"* — e onde um parser posicional
   reconstrói a ordem de leitura por heurística de coordenadas.

Não chama API: lê o cache de OCR já congelado em `corpus/ocr/` (RNF10) e roda o
`pdfplumber` localmente. Custo zero.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DIR_CORPUS_RAW, RAIZ_PROJETO  # noqa: E402

DIR_CACHE_OCR = RAIZ_PROJETO / "corpus" / "ocr"
CAMINHO_ANCORAS = RAIZ_PROJETO / "corpus" / "ancoras_sentinela.csv"
DESTINO = RAIZ_PROJETO / "resultados" / "gate_g3.md"
# Mesma tolerância que a avaliação aplica ao gabarito (spec 5.13).
TOLERANCIA_PCT = 1.0


def _normalizar(texto: str) -> str:
    """Minúsculas sem acento, para casar 'Itaú'/'Itau' e 'provisão'/'provisao'."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def _escalas_plausiveis(valor: float) -> list[float]:
    """Escalas em que o mesmo fato pode estar impresso no release.

    O valor-âncora é registrado em unidade canônica — reais para valores
    absolutos, fração para razões. O documento imprime em outra escala: R$ 11,5
    **bilhões** no texto de capa e 11.500 em tabela cujo cabeçalho diz
    *R$ milhões*; um ROE de 0,271 aparece como 27,1 **%**. Comparar só a forma
    canônica produziria falso negativo em massa — foi o que a primeira versão
    deste gate fez, achando 4/20 para os dois extratores.
    """
    if abs(valor) < 1:  # razão: procura também a forma percentual
        return [valor, valor * 100]
    return [valor, valor / 1e3, valor / 1e6, valor / 1e9]


def ancora_presente(
    paginas: list[str], valor: float, tolerancia_pct: float
) -> tuple[bool, bool]:
    """Procura a âncora **página a página**, canonicamente e com escala tolerada.

    Duas descobertas obrigaram este desenho, e as duas valem registro:

    1. **O parser do projeto falha fechado em texto de documento inteiro.**
       `contem_notacao_numerica_nao_suportada` dispara em qualquer trecho
       ambíguo, e `extrair_numeros_ptbr` devolve lista vazia. Medido: as 476 mil
       chars do Itaú 1T2026 rendem **zero** números; os primeiros mil rendem 23.
       É correto para o uso pretendido — comparar *uma resposta* —, e é a razão
       de a sentinela ser definida por página (spec 5.4).
    2. **Comparar por string quebra no arredondamento.** A âncora é o valor
       divulgado arredondado (R$ 11,5 bi) e a tabela imprime 11.499.

    Devolve `(canonico, com_escala)`. O primeiro é o critério estrito: o parser
    canoniza "R$ 12,3 bilhões" e "12.300" sob cabeçalho *em milhões* para a
    mesma grandeza. O segundo tolera a escala perdida quando o cabeçalho da
    tabela ficou noutra página — é mais frouxo, e por isso reportado à parte,
    nunca somado ao primeiro.
    """
    from src.normalizacao import extrair_numeros_ptbr, valores_equivalentes

    escalas = _escalas_plausiveis(valor)
    canonico = False
    com_escala = False
    for pagina in paginas:
        if not pagina.strip():
            continue
        encontrados = extrair_numeros_ptbr(pagina)
        if not encontrados:
            continue
        for observado in encontrados:
            if valores_equivalentes(valor, observado, tolerancia_pct):
                return True, True
            if not com_escala and any(
                valores_equivalentes(alvo, observado, tolerancia_pct)
                for alvo in escalas
            ):
                com_escala = True
    return canonico, com_escala


def paginas_do_ocr(documento: str) -> list[str]:
    for caminho in DIR_CACHE_OCR.glob("*.json"):
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if dados.get("documento") != documento:
            continue
        return [(p.get("markdown") or "") for p in (dados["ocr"].get("pages") or [])]
    return []


def paginas_do_pdfplumber(documento: str) -> list[str]:
    import pdfplumber

    caminho = DIR_CORPUS_RAW / f"{documento}.pdf"
    with pdfplumber.open(str(caminho)) as pdf:
        return [(pagina.extract_text() or "") for pagina in pdf.pages]


def linhas_de_tabela_ocr(texto: str) -> int:
    """Conta linhas de tabela reconstruídas (markdown `|` ou HTML `<tr>`)."""
    return len(re.findall(r"<tr[ >]", texto)) + len(
        [ln for ln in texto.splitlines() if ln.count("|") >= 2]
    )


def linhas_de_tabela_pdfplumber(documento: str) -> int:
    import pdfplumber

    caminho = DIR_CORPUS_RAW / f"{documento}.pdf"
    total = 0
    with pdfplumber.open(str(caminho)) as pdf:
        for pagina in pdf.pages:
            for tabela in pagina.extract_tables() or []:
                total += len(tabela)
    return total


def main() -> int:
    ancoras = list(csv.DictReader(open(CAMINHO_ANCORAS, encoding="utf-8")))
    linhas_relatorio: list[str] = []
    canon = {"ocr": 0, "pdfplumber": 0}
    escala = {"ocr": 0, "pdfplumber": 0}
    tabelas = {"ocr": 0, "pdfplumber": 0}

    for registro in ancoras:
        documento = registro["documento"]
        valor = float(registro["valor_ancora"])

        pgs_ocr = paginas_do_ocr(documento)
        pgs_pdf = paginas_do_pdfplumber(documento)

        can_ocr, esc_ocr = ancora_presente(pgs_ocr, valor, TOLERANCIA_PCT)
        can_pdf, esc_pdf = ancora_presente(pgs_pdf, valor, TOLERANCIA_PCT)
        canon["ocr"] += can_ocr
        canon["pdfplumber"] += can_pdf
        escala["ocr"] += esc_ocr
        escala["pdfplumber"] += esc_pdf

        tab_ocr = linhas_de_tabela_ocr("\n".join(pgs_ocr))
        tab_pdf = linhas_de_tabela_pdfplumber(documento)
        tabelas["ocr"] += tab_ocr
        tabelas["pdfplumber"] += tab_pdf

        def marca(canonico: bool, com_escala: bool) -> str:
            return "sim" if canonico else ("escala" if com_escala else "**não**")

        linhas_relatorio.append(
            f"| {documento} | {len(pgs_ocr)}/{len(pgs_pdf)} | "
            f"{marca(can_ocr, esc_ocr)} | {marca(can_pdf, esc_pdf)} | "
            f"{tab_ocr} | {tab_pdf} |"
        )
        print(
            f"{documento:28s} ancora OCR={marca(can_ocr, esc_ocr):7s} "
            f"plumber={marca(can_pdf, esc_pdf):7s} "
            f"| tabelas {tab_ocr:6d} vs {tab_pdf:6d}"
        )

    n = len(ancoras)
    print(f"\nÂncora canônica  — OCR: {canon['ocr']}/{n} · "
          f"pdfplumber: {canon['pdfplumber']}/{n}")
    print(f"Âncora c/ escala — OCR: {escala['ocr']}/{n} · "
          f"pdfplumber: {escala['pdfplumber']}/{n}")
    print(f"Linhas de tabela — OCR: {tabelas['ocr']} · "
          f"pdfplumber: {tabelas['pdfplumber']}")

    vencedor = (
        "OCR de documento" if canon["ocr"] > canon["pdfplumber"]
        else "pdfplumber" if canon["pdfplumber"] > canon["ocr"]
        else "empate no critério canônico"
    )
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        "# Gate G3 — OCR de documento × pdfplumber (spec 5.3)\n\n"
        "Medição local sobre o cache de OCR congelado (`corpus/ocr/`) e o "
        "`pdfplumber` rodando nos mesmos PDFs. Sem chamada de API.\n\n"
        "A âncora é procurada **página a página**: o parser pt-BR do projeto "
        "falha fechado em texto de documento inteiro (a guarda de notação "
        "ambígua dispara e ele devolve zero números), e a sentinela da spec 5.4 "
        "é definida por página de qualquer forma. `sim` = casou no valor "
        "canônico; `escala` = só casou tolerando a escala perdida quando o "
        "cabeçalho da tabela ficou noutra página — critério mais frouxo, "
        "reportado à parte e nunca somado ao canônico.\n\n"
        "| documento | pág. OCR/plumber | âncora OCR | âncora plumber | "
        "linhas tab. OCR | linhas tab. plumber |\n"
        "|---|---|---|---|---|---|\n"
        + "\n".join(linhas_relatorio)
        + f"\n\n**Âncora canônica:** OCR {canon['ocr']}/{n} · "
        f"pdfplumber {canon['pdfplumber']}/{n}\n\n"
        f"**Âncora tolerando escala:** OCR {escala['ocr']}/{n} · "
        f"pdfplumber {escala['pdfplumber']}/{n}\n\n"
        f"**Linhas de tabela reconstruídas:** OCR {tabelas['ocr']} · "
        f"pdfplumber {tabelas['pdfplumber']}\n\n"
        f"**Veredito na âncora:** {vencedor}\n",
        encoding="utf-8",
    )
    print(f"\nRelatório: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
