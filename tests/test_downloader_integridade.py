"""Integridade da primeira coleta e limites de espera do downloader."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from scripts import baixar_corpus
from src.ingestao import COLUNAS_METADADOS_CORPUS


class _SessaoFalsa:
    def __init__(self) -> None:
        self.fechada = False

    def close(self) -> None:
        self.fechada = True


def _preparar_manifesto(
    tmp_path: Path,
    monkeypatch,
    *,
    hash_sha256: str = "",
) -> tuple[Path, Path, _SessaoFalsa]:
    manifesto = tmp_path / "metadados.csv"
    raw = tmp_path / "raw"
    raw.mkdir()
    linha = {
        "empresa": "BANCO DO BRASIL",
        "trimestre": "1T2026",
        "documento": "documento_teste",
        "url": "https://api.mziq.com/documento.pdf",
        "hash_sha256": hash_sha256,
        "data_coleta": "2026-01-01" if hash_sha256 else "",
    }
    with manifesto.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=COLUNAS_METADADOS_CORPUS,
        )
        escritor.writeheader()
        escritor.writerow(linha)

    sessao = _SessaoFalsa()
    monkeypatch.setattr(baixar_corpus, "CAMINHO_METADADOS_CORPUS", manifesto)
    monkeypatch.setattr(baixar_corpus, "DIR_CORPUS_RAW", raw)
    monkeypatch.setattr(baixar_corpus, "_validar_manifesto", lambda *_: None)
    monkeypatch.setattr(baixar_corpus, "_validar_pdf", lambda *_: None)
    monkeypatch.setattr(baixar_corpus, "_criar_sessao", lambda: sessao)
    return manifesto, raw / "documento_teste.pdf", sessao


def _ler_linha(manifesto: Path) -> dict[str, str]:
    with manifesto.open(newline="", encoding="utf-8") as arquivo:
        return next(csv.DictReader(arquivo))


def test_hash_vazio_ignora_pdf_local_e_confia_apenas_no_download(
    tmp_path,
    monkeypatch,
):
    manifesto, destino, sessao = _preparar_manifesto(tmp_path, monkeypatch)
    conteudo_local = b"%PDF-local-preexistente"
    conteudo_baixado = b"%PDF-baixado-e-validado"
    destino.write_bytes(conteudo_local)
    chamadas: list[str] = []

    def baixar(url, caminho_destino, sessao_recebida):
        chamadas.append(url)
        assert caminho_destino == destino
        assert sessao_recebida is sessao
        assert destino.read_bytes() == conteudo_local
        temporario = destino.parent / ".download-validado.part"
        temporario.write_bytes(conteudo_baixado)
        return temporario

    monkeypatch.setattr(
        baixar_corpus,
        "_baixar_para_temporario",
        baixar,
    )

    assert baixar_corpus.baixar_corpus(amostra=True)

    linha = _ler_linha(manifesto)
    assert chamadas == ["https://api.mziq.com/documento.pdf"]
    assert destino.read_bytes() == conteudo_baixado
    assert linha["hash_sha256"] == hashlib.sha256(conteudo_baixado).hexdigest()
    assert linha["hash_sha256"] != hashlib.sha256(conteudo_local).hexdigest()
    assert linha["data_coleta"] != ""
    assert sessao.fechada


def test_falha_na_primeira_coleta_preserva_local_e_nao_pina_hash(
    tmp_path,
    monkeypatch,
):
    manifesto, destino, sessao = _preparar_manifesto(tmp_path, monkeypatch)
    conteudo_local = b"%PDF-local-preexistente"
    destino.write_bytes(conteudo_local)

    def falhar(*_args):
        raise RuntimeError("origem indisponível")

    monkeypatch.setattr(
        baixar_corpus,
        "_baixar_para_temporario",
        falhar,
    )

    assert not baixar_corpus.baixar_corpus(amostra=True)

    linha = _ler_linha(manifesto)
    assert destino.read_bytes() == conteudo_local
    assert linha["hash_sha256"] == ""
    assert linha["data_coleta"] == ""
    assert sessao.fechada


def test_hash_pinado_e_local_correspondente_dispensam_download(
    tmp_path,
    monkeypatch,
):
    conteudo = b"%PDF-ja-pinado"
    hash_esperado = hashlib.sha256(conteudo).hexdigest()
    manifesto, destino, sessao = _preparar_manifesto(
        tmp_path,
        monkeypatch,
        hash_sha256=hash_esperado,
    )
    destino.write_bytes(conteudo)

    def nao_deve_baixar(*_args):
        raise AssertionError("PDF com hash pinado e válido não deve ser rebaixado")

    monkeypatch.setattr(
        baixar_corpus,
        "_baixar_para_temporario",
        nao_deve_baixar,
    )

    assert baixar_corpus.baixar_corpus(amostra=True)

    linha = _ler_linha(manifesto)
    assert linha["hash_sha256"] == hash_esperado
    assert linha["data_coleta"] == "2026-01-01"
    assert destino.read_bytes() == conteudo
    assert sessao.fechada


def test_retry_after_e_backoff_tem_limite_explicito(monkeypatch):
    sessao = baixar_corpus._criar_sessao()
    try:
        retry = sessao.get_adapter("https://").max_retries
        esperas: list[float] = []
        monkeypatch.setattr("urllib3.util.retry.time.sleep", esperas.append)

        class Resposta:
            headers = {"Retry-After": "999999999"}

        assert retry.total == 3
        assert retry.backoff_max == baixar_corpus.MAX_ESPERA_RETRY_S
        assert retry.retry_after_max == baixar_corpus.MAX_ESPERA_RETRY_S
        assert (
            retry.parse_retry_after("999999999")
            == baixar_corpus.MAX_ESPERA_RETRY_S
        )
        retry.sleep(Resposta())
        assert esperas == [baixar_corpus.MAX_ESPERA_RETRY_S]
    finally:
        sessao.close()
