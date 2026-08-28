"""Passagem completa de OCR do corpus pela Batch API da Mistral (spec 5.3, RNF10).

Por que um script separado do `preprocessar_ocr_mistral.py`: aquele congela
páginas isoladas pelo endpoint síncrono `/v1/ocr`, para auditoria pontual. Este
processa os 20 documentos inteiros pela Batch API, que custa metade (USD 2 por
1000 páginas em vez de USD 4) e é o caminho previsto para a passagem única que
alimenta o índice.

Regras duras, todas motivadas por dinheiro real:

- **Nada é enviado sem `--permitir-api-paga`.** O default de qualquer execução é
  o dry-run, que estima e não gasta.
- **O hash local é conferido contra `corpus/metadados.csv` antes do upload.**
  OCR de bytes que ninguém hasheou produziria um cache que não corresponde ao
  corpus declarado — o manifesto é a fonte de verdade, não o arquivo em disco.
- **O job criado é persistido em journal antes de qualquer espera.** Uma
  reexecução retoma o job existente em vez de criar outro: criar um segundo job
  cobraria a passagem duas vezes, e é o erro mais caro possível aqui.
- **Documento já presente em `corpus/ocr/` não é reprocessado** (RNF10). Só
  `--reprocessar-ocr` força, e ainda assim respeitando o teto.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (  # noqa: E402
    CAMINHO_METADADOS_CORPUS,
    DIR_CORPUS_RAW,
    RAIZ_PROJETO,
    carregar_config,
)

BASE = "https://api.mistral.ai/v1"
DIR_CACHE_OCR = RAIZ_PROJETO / "corpus" / "ocr"
CAMINHO_JOURNAL = RAIZ_PROJETO / "artefatos" / "logs_execucoes" / "journal_ocr_batch.json"
# A Batch API cobra metade do preço do endpoint síncrono.
FATOR_BATCH = 0.5


class ErroBatchOCR(RuntimeError):
    """Falha que interrompe a passagem sem deixar cobrança pendente ambígua."""


@dataclass(frozen=True)
class Documento:
    nome: str
    empresa: str
    trimestre: str
    caminho: Path
    hash_esperado: str
    paginas: int


def _cabecalhos(chave: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {chave}"}


def _hash_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _contar_paginas(caminho: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(str(caminho)).pages)


def carregar_documentos() -> list[Documento]:
    """Lê o manifesto e confere a integridade de cada PDF local.

    Hash divergente é erro, nunca aviso: o cache de OCR passa a ser versionado e
    citado como evidência, então ele tem de corresponder exatamente ao documento
    que o manifesto declara.
    """
    import csv

    documentos: list[Documento] = []
    divergentes: list[str] = []
    ausentes: list[str] = []
    with open(CAMINHO_METADADOS_CORPUS, encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            caminho = DIR_CORPUS_RAW / f"{linha['documento']}.pdf"
            if not caminho.is_file():
                ausentes.append(linha["documento"])
                continue
            observado = _hash_arquivo(caminho)
            if observado != linha["hash_sha256"]:
                divergentes.append(linha["documento"])
                continue
            documentos.append(
                Documento(
                    nome=linha["documento"],
                    empresa=linha["empresa"],
                    trimestre=linha["trimestre"],
                    caminho=caminho,
                    hash_esperado=observado,
                    paginas=_contar_paginas(caminho),
                )
            )
    if ausentes:
        raise ErroBatchOCR(
            f"PDFs ausentes em {DIR_CORPUS_RAW}: {ausentes}. "
            "Rode `python scripts/baixar_corpus.py` antes."
        )
    if divergentes:
        raise ErroBatchOCR(
            f"Hash divergente do manifesto: {divergentes}. "
            "O corpus em disco não é o corpus declarado — investigue antes de "
            "gastar OCR sobre bytes não auditados."
        )
    return documentos


def custo_estimado_usd(paginas: int, preco_mil: float) -> float:
    return paginas / 1000 * preco_mil * FATOR_BATCH


def fingerprint_pendentes(pendentes: list[Documento]) -> str:
    """Identifica O LOTE, não só "existe algum job".

    Duas passagens diferentes (documentos diferentes) não podem casar o mesmo
    registro de journal — foi o que aconteceu na prática: o journal de
    2026-08-10 (job concluído, 20 documentos) fazia uma passagem nova, com
    outros 24 documentos, ser lida como "já existe, retomando" e travava sem
    criar job nem gastar nada. Seguro (não corrompeu nada, não cobrou
    duas vezes), mas também não processava. O fingerprint do conjunto exato de
    `(nome, hash_esperado)` resolve: mesmo lote pendente → mesmo registro,
    retomado; lote diferente → chave diferente, job novo.
    """
    chave = sorted((doc.nome, doc.hash_esperado) for doc in pendentes)
    bruto = json.dumps(chave, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(bruto).hexdigest()[:16]


def _ler_journal() -> dict:
    if not CAMINHO_JOURNAL.is_file():
        return {"lotes": {}}
    dados = json.loads(CAMINHO_JOURNAL.read_text(encoding="utf-8"))
    if "lotes" not in dados:
        # Formato antigo (um único job flat, sem fingerprint de lote):
        # migrado para dentro de "lotes" sob uma chave própria, preservado
        # como histórico em vez de descartado (RNF08 — evidência de execução).
        job_id = dados.get("job_id")
        chave_legado = f"legado-{job_id}" if job_id else "legado-vazio"
        dados = {"lotes": {chave_legado: dados}} if dados else {"lotes": {}}
    return dados


def _gravar_journal(dados: dict) -> None:
    CAMINHO_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_JOURNAL.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def subir_pdf(chave: str, doc: Documento, timeout: float) -> str:
    with open(doc.caminho, "rb") as arquivo:
        resposta = requests.post(
            f"{BASE}/files",
            headers=_cabecalhos(chave),
            files={"file": (doc.caminho.name, arquivo, "application/pdf")},
            data={"purpose": "ocr"},
            timeout=timeout,
        )
    if not resposta.ok:
        raise ErroBatchOCR(f"upload de {doc.nome} falhou: HTTP {resposta.status_code}")
    return resposta.json()["id"]


def url_assinada(chave: str, file_id: str, timeout: float) -> str:
    resposta = requests.get(
        f"{BASE}/files/{file_id}/url",
        headers=_cabecalhos(chave),
        params={"expiry": 24},
        timeout=timeout,
    )
    if not resposta.ok:
        raise ErroBatchOCR(f"URL assinada falhou: HTTP {resposta.status_code}")
    return resposta.json()["url"]


def montar_jsonl(config, documentos: list[Documento], urls: dict[str, str]) -> bytes:
    """Uma linha por documento; `custom_id` liga o resultado de volta ao PDF."""
    linhas = []
    for doc in documentos:
        # O corpo tem de espelhar o do cliente síncrono (`src/ocr_mistral.py`).
        # A passagem de 2026-08-11 omitiu `confidence_scores_granularity` e
        # voltou com `confidence_scores` **vazio nas 2.790 páginas** — os blocos
        # vieram pelo default, a confiança não. Isso custou um dos dois sinais
        # de diagnóstico que a spec 5.3 dá como razão para preferir OCR de
        # documento a um LLM de visão genérico, e desliga o limiar de
        # confiança da 5.4. Reprocessar para recuperá-lo custa outra passagem
        # inteira, então o parâmetro fica explícito aqui.
        corpo = {
            "model": config.mistral_ocr_modelo,
            "document": {"type": "document_url", "document_url": urls[doc.nome]},
            "table_format": config.mistral_ocr_table_format,
            "include_blocks": config.mistral_ocr_include_blocks,
            "include_image_base64": False,
            "confidence_scores_granularity": (
                config.mistral_ocr_confidence_granularity
            ),
        }
        linhas.append(
            json.dumps({"custom_id": doc.nome, "body": corpo}, ensure_ascii=False)
        )
    return ("\n".join(linhas) + "\n").encode("utf-8")


def criar_job(chave: str, conteudo: bytes, config, timeout: float) -> str:
    envio = requests.post(
        f"{BASE}/files",
        headers=_cabecalhos(chave),
        files={"file": ("ocr_corpus.jsonl", conteudo, "application/jsonl")},
        data={"purpose": "batch"},
        timeout=timeout,
    )
    if not envio.ok:
        raise ErroBatchOCR(f"upload do JSONL falhou: HTTP {envio.status_code}")
    input_id = envio.json()["id"]

    criacao = requests.post(
        f"{BASE}/batch/jobs",
        headers={**_cabecalhos(chave), "Content-Type": "application/json"},
        json={
            "input_files": [input_id],
            "endpoint": "/v1/ocr",
            "model": config.mistral_ocr_modelo,
            "metadata": {"projeto": "assistente-research-financeiro"},
            "timeout_hours": 24,
        },
        timeout=timeout,
    )
    if not criacao.ok:
        raise ErroBatchOCR(
            f"criação do job falhou: HTTP {criacao.status_code} {criacao.text[:300]}"
        )
    return criacao.json()["id"]


def estado_job(chave: str, job_id: str, timeout: float) -> dict:
    resposta = requests.get(
        f"{BASE}/batch/jobs/{job_id}", headers=_cabecalhos(chave), timeout=timeout
    )
    if not resposta.ok:
        raise ErroBatchOCR(f"consulta do job falhou: HTTP {resposta.status_code}")
    return resposta.json()


def baixar_arquivo(chave: str, file_id: str, timeout: float) -> bytes:
    resposta = requests.get(
        f"{BASE}/files/{file_id}/content",
        headers=_cabecalhos(chave),
        timeout=timeout,
    )
    if not resposta.ok:
        raise ErroBatchOCR(f"download de {file_id} falhou: HTTP {resposta.status_code}")
    return resposta.content


def gravar_resultados(
    bruto: bytes, documentos: dict[str, Documento]
) -> tuple[list[str], list[str]]:
    """Grava um JSON por documento em `corpus/ocr/<hash-do-pdf>.json` (RNF10)."""
    DIR_CACHE_OCR.mkdir(parents=True, exist_ok=True)
    gravados: list[str] = []
    falhos: list[str] = []
    for linha in bruto.decode("utf-8").splitlines():
        if not linha.strip():
            continue
        item = json.loads(linha)
        nome = item.get("custom_id")
        doc = documentos.get(nome)
        if doc is None:
            falhos.append(f"{nome} (custom_id desconhecido)")
            continue
        if item.get("error") or (item.get("response") or {}).get("status_code") != 200:
            falhos.append(f"{nome} (erro na resposta)")
            continue
        corpo = item["response"]["body"]
        destino = DIR_CACHE_OCR / f"{doc.hash_esperado}.json"
        destino.write_text(
            json.dumps(
                {
                    "documento": doc.nome,
                    "empresa": doc.empresa,
                    "trimestre": doc.trimestre,
                    "hash_pdf": doc.hash_esperado,
                    "modelo": corpo.get("model"),
                    "ocr": corpo,
                },
                ensure_ascii=False,
                indent=1,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        gravados.append(doc.nome)

    # A Mistral pode OMITIR a linha inteira de um request que falhou de forma
    # catastrófica, em vez de devolver uma linha com `error`/status != 200.
    # Achado na prática (2026-08-27): 23 de 24 gravaram, a saída não tinha
    # `custom_id` nenhum para o 24º, e o loop acima — que só reage a linhas
    # PRESENTES — devolvia `falhos=[]` e código de saída 0. Documento sumindo
    # do corpus sem nenhum sinal de erro é pior que sumir com erro.
    vistos = set(gravados) | {item.split(" ", 1)[0] for item in falhos}
    for nome in documentos:
        if nome not in vistos:
            falhos.append(f"{nome} (ausente da saída do job)")

    return gravados, falhos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--permitir-api-paga", action="store_true")
    parser.add_argument("--reprocessar-ocr", action="store_true")
    parser.add_argument(
        "--aguardar",
        action="store_true",
        help="Acompanha o job até o fim; sem isso, cria e devolve o controle.",
    )
    parser.add_argument("--intervalo-s", type=float, default=60.0)
    args = parser.parse_args()

    config = carregar_config()
    chave = config.mistral_ocr_api_key or os.environ.get("MISTRAL_API_KEY", "")
    if not chave:
        raise ErroBatchOCR("MISTRAL_API_KEY ausente — configure o `.env` (RNF04).")

    documentos = carregar_documentos()
    if not args.reprocessar_ocr:
        pendentes = [
            d
            for d in documentos
            if not (DIR_CACHE_OCR / f"{d.hash_esperado}.json").is_file()
        ]
    else:
        pendentes = documentos

    paginas = sum(d.paginas for d in pendentes)
    custo = custo_estimado_usd(paginas, config.mistral_ocr_preco_usd_mil_paginas)
    print(f"Documentos pendentes: {len(pendentes)} de {len(documentos)}")
    print(f"Páginas a processar: {paginas}")
    print(f"Custo estimado (Batch, 50%): USD {custo:.2f}")
    print(f"Teto configurado: USD {config.mistral_ocr_orcamento_teto_usd:.2f}")

    if not pendentes:
        print("Nada pendente — cache completo (RNF10). Nenhuma chamada paga.")
        return 0
    if custo > config.mistral_ocr_orcamento_teto_usd:
        raise ErroBatchOCR(
            f"Custo estimado USD {custo:.2f} excede o teto "
            f"USD {config.mistral_ocr_orcamento_teto_usd:.2f}. Ajuste "
            "MISTRAL_OCR_ORCAMENTO_TETO_USD conscientemente ou reduza o escopo."
        )
    if not args.permitir_api_paga:
        print("\nDry-run: nada foi enviado. Repita com --permitir-api-paga.")
        return 0

    journal = _ler_journal()
    lote = fingerprint_pendentes(pendentes)
    registro = journal["lotes"].get(lote)
    job_id = registro.get("job_id") if registro else None
    if job_id:
        print(
            f"\nJob já existente no journal para este lote ({lote}): {job_id} — "
            "retomando, não recriando."
        )
    else:
        print("\nSubindo PDFs e criando o job...")
        urls: dict[str, str] = {}
        for doc in pendentes:
            file_id = subir_pdf(chave, doc, config.mistral_ocr_timeout_s)
            urls[doc.nome] = url_assinada(chave, file_id, config.mistral_ocr_timeout_s)
            print(f"  {doc.nome}: {doc.paginas} pp")
        conteudo = montar_jsonl(config, pendentes, urls)
        job_id = criar_job(chave, conteudo, config, config.mistral_ocr_timeout_s)
        journal["lotes"][lote] = {
            "job_id": job_id,
            "criado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "documentos": [d.nome for d in pendentes],
            "paginas": paginas,
            "custo_estimado_usd": round(custo, 4),
            "modelo": config.mistral_ocr_modelo,
        }
        _gravar_journal(journal)
        print(f"Job criado: {job_id} (registrado em {CAMINHO_JOURNAL.name})")

    if not args.aguardar:
        print("Use --aguardar para acompanhar até o fim.")
        return 0

    while True:
        estado = estado_job(chave, job_id, config.mistral_ocr_timeout_s)
        situacao = estado.get("status")
        print(
            f"  status={situacao} "
            f"sucesso={estado.get('succeeded_requests')} "
            f"falha={estado.get('failed_requests')} "
            f"total={estado.get('total_requests')}"
        )
        if situacao in {"SUCCESS", "FAILED", "TIMEOUT_EXCEEDED", "CANCELLED"}:
            break
        time.sleep(args.intervalo_s)

    if situacao != "SUCCESS":
        raise ErroBatchOCR(f"Job terminou em {situacao} — nada gravado no cache.")

    bruto = baixar_arquivo(chave, estado["output_file"], config.mistral_ocr_timeout_s)
    gravados, falhos = gravar_resultados(bruto, {d.nome: d for d in pendentes})
    print(f"\nGravados em corpus/ocr/: {len(gravados)}")
    if falhos:
        print(f"Falhos (não gravados): {falhos}")
    return 0 if not falhos else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ErroBatchOCR as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        raise SystemExit(2) from None
