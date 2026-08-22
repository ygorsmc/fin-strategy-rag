"""OCR pontual de uma demonstração em IFRS ilegível, para fechar o gate G4.

**Por que existe.** A demonstração anual do BTG (`btg_ifrs_4T2025`) vem com fonte
embutida sem mapa de caracteres: `pdfplumber` devolve `(cid:130)(cid:131)...` no
lugar de algarismos. O G4 registrou a célula como **SEM ÂNCORA** — ausência de
evidência, não zero — e deixou a leitura pendente de uma decisão de orçamento
(spec 5.20), não técnica. Este script executa essa decisão.

**Por que não reusa `ocr_batch_mistral.py`.** Aquele processa os 20 documentos do
corpus de releases, conferidos contra `corpus/metadados.csv`. As demonstrações em
IFRS são um corpus à parte, com manifesto próprio (`corpus/ifrs/manifesto_ifrs.csv`)
e finalidade de âncora, não de indexação — misturar os dois faria o cache de OCR
do índice conter páginas que nunca entram em chunk nenhum, e a RNF09 mede o cache
inteiro no fingerprint do índice.

**Disciplina, idêntica à do resto do projeto e pelos mesmos motivos:**

- **Dry-run é o default.** Sem `--permitir-api-paga` nada é enviado; o script
  estima e sai.
- **O hash é conferido contra o manifesto antes do upload.** OCR de bytes que
  ninguém hasheou produz âncora que não corresponde ao documento declarado.
- **Journal write-ahead antes e depois da chamada** (RNF08), para que uma queda
  no meio deixe rastro em vez de silêncio.
- **Faixa de páginas obrigatória.** Mandar 71 páginas quando a DRE mora em uma
  é pagar 70 vezes por nada; a faixa padrão vem da posição medida da DRE nos
  trimestrais legíveis do mesmo emissor (~18% do documento).

    python -m scripts.ocr_ancora_ifrs --documento btg_ifrs_4T2025           # estima
    python -m scripts.ocr_ancora_ifrs --documento btg_ifrs_4T2025 \
        --paginas 8-28 --permitir-api-paga
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.config import DIR_LOGS_EXECUCOES, carregar_config  # noqa: E402
from src.ocr_mistral import ClienteMistralOCR  # noqa: E402

DIR_IFRS = RAIZ / "corpus" / "ifrs"
MANIFESTO = DIR_IFRS / "manifesto_ifrs.csv"
DIR_CACHE = DIR_IFRS / "ocr"
# Preço do endpoint síncrono `/v1/ocr` (o Batch custa metade, mas exige job e
# espera — desproporcional para um documento). Fonte: mesma tabela usada em
# `ocr_batch_mistral.py`.
USD_POR_PAGINA = 0.004


def _paginas(expressao: str) -> tuple[int, ...]:
    """Aceita `8-28`, `8 12 14` ou `8,12,14`; sempre 1-based, como o PDF."""
    numeros: set[int] = set()
    for parte in expressao.replace(",", " ").split():
        if "-" in parte:
            inicio, fim = (int(x) for x in parte.split("-", 1))
            if inicio < 1 or fim < inicio:
                raise ValueError(f"Intervalo inválido: {parte!r}")
            numeros.update(range(inicio, fim + 1))
        else:
            if int(parte) < 1:
                raise ValueError(f"Página inválida: {parte!r}")
            numeros.add(int(parte))
    if not numeros:
        raise ValueError("Nenhuma página selecionada.")
    return tuple(sorted(numeros))


def _item_do_manifesto(documento: str) -> dict:
    with open(MANIFESTO, newline="", encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha["documento"] == documento:
                return linha
    raise SystemExit(f"Documento {documento!r} ausente de {MANIFESTO}.")


def _conferir_hash(caminho: Path, esperado: str) -> str:
    obtido = hashlib.sha256(caminho.read_bytes()).hexdigest()
    if obtido != esperado:
        raise SystemExit(
            f"SHA-256 de {caminho.name} diverge do manifesto.\n"
            f"  manifesto: {esperado}\n  arquivo:   {obtido}\n"
            "Rebaixe o arquivo ou atualize o manifesto — o gate não lê peça "
            "que mudou desde o registro."
        )
    return obtido


def _registrar(evento: dict) -> None:
    from src.avaliacao import registrar_execucao

    registrar_execucao(evento, dir_logs=DIR_LOGS_EXECUCOES, arquivo=None)


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documento", required=True)
    parser.add_argument(
        "--paginas",
        default="8-28",
        help="1-based; padrão cobre a faixa onde a DRE aparece nos "
        "trimestrais legíveis do mesmo emissor",
    )
    parser.add_argument("--permitir-api-paga", action="store_true")
    args = parser.parse_args(argv)

    config = carregar_config()
    item = _item_do_manifesto(args.documento)
    caminho = DIR_IFRS / "raw" / item["arquivo"]
    if not caminho.exists():
        raise SystemExit(f"PDF ausente: {caminho} (rode scripts/baixar_ifrs.py)")
    paginas = _paginas(args.paginas)
    sha = _conferir_hash(caminho, item["hash_sha256"])
    custo = len(paginas) * USD_POR_PAGINA

    print(f"documento : {args.documento} ({item['empresa']} {item['periodo']})")
    print(f"arquivo   : {caminho.name}  sha256 ✓")
    print(f"páginas   : {len(paginas)} -> {paginas[0]}..{paginas[-1]}")
    print(f"custo est.: USD {custo:.3f}  (teto OCR: USD "
          f"{config.mistral_ocr_orcamento_teto_usd:.2f})")

    if custo > config.mistral_ocr_orcamento_teto_usd:
        raise SystemExit("Estimativa acima do teto de OCR configurado.")
    if not args.permitir_api_paga:
        print("\nDRY-RUN — nada foi enviado. Use --permitir-api-paga.")
        return 0
    if not config.mistral_ocr_api_key:
        raise SystemExit("MISTRAL_API_KEY ausente no ambiente.")

    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:10]}"
    base = {
        "run_id": run_id,
        "etapa": "ocr_ancora_ifrs",
        "documento": args.documento,
        "sha256_pdf": sha,
        "paginas": list(paginas),
        "custo_estimado_usd": round(custo, 4),
    }
    _registrar({**base, "fase": "antes"})

    cliente = ClienteMistralOCR(
        api_key=config.mistral_ocr_api_key, timeout_s=300.0, max_retries=2
    )
    # A gravação mora DENTRO do try junto com a chamada, e não depois dela:
    # uma exceção entre "pagou" e "gravou" perde a resposta e obriga a pagar de
    # novo. Aconteceu na primeira execução deste script (AttributeError ao
    # serializar) e custou uma chamada — o custo de aprender isso está no
    # journal, não escondido aqui.
    destino = DIR_CACHE / f"{sha}.json"
    try:
        resultado = cliente.processar_pdf(
            caminho.read_bytes(), pages=[p - 1 for p in paginas]
        )
        DIR_CACHE.mkdir(parents=True, exist_ok=True)
        # ACUMULA por página em vez de sobrescrever. O cache é endereçado pelo
        # hash do PDF, então duas execuções com faixas diferentes do mesmo
        # documento caem no mesmo arquivo — a primeira versão deste script
        # sobrescrevia, e uma faixa já paga foi perdida assim. Página já
        # presente não é reprocessada nem re-cobrada; ela é mantida.
        pagina_por_indice: dict[str, dict] = {}
        if destino.exists():
            anterior = json.loads(destino.read_text(encoding="utf-8"))
            pagina_por_indice = {
                str(p["indice_1based"]): p for p in anterior.get("paginas", [])
            }
        # As TABELAS vêm em campo separado: o markdown da página traz só uma
        # referência (`[tbl-3.html](tbl-3.html)`) e os números moram em
        # `resultado.tabelas`. Guardar só o markdown descarta exatamente a
        # parte que a âncora precisa ler — foi o que aconteceu na primeira
        # versão deste merge, e por isso a tabela é anexada à sua página aqui.
        tabelas_por_pagina: dict[int, list[dict]] = {}
        for tabela in resultado.tabelas:
            tabelas_por_pagina.setdefault(tabela.page_index, []).append(
                tabela.para_dict()
            )
        for i, pagina in enumerate(resultado.pages):
            registro = pagina.para_dict()
            registro["indice_1based"] = paginas[i]
            registro["run_id"] = run_id
            registro["tabelas"] = tabelas_por_pagina.get(pagina.index, [])
            pagina_por_indice[str(paginas[i])] = registro
        payload = {
            "documento": args.documento,
            "sha256_pdf": sha,
            "modelo": resultado.modelo,
            "paginas": [
                pagina_por_indice[k]
                for k in sorted(pagina_por_indice, key=int)
            ],
        }
        destino.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 - o journal precisa do motivo
        _registrar({**base, "fase": "depois", "erro": f"{type(exc).__name__}: {exc}"})
        raise

    _registrar(
        {
            **base,
            "fase": "depois",
            "paginas_retornadas": len(resultado.pages),
            "cache": str(destino.relative_to(RAIZ)),
        }
    )
    print(f"\nOK — {len(resultado.pages)} páginas em {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - execução manual
    raise SystemExit(principal())
