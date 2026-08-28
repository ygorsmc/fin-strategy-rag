"""Journal do `scripts/ocr_batch_mistral.py` precisa distinguir LOTES.

Achado em 2026-08-27, ao enriquecer o corpus com 7 emissores novos: o job de
2026-08-10 (20 documentos, concluído, `status=SUCCESS`) ficava sozinho no
journal flat, e uma passagem nova com outros 24 documentos lia "job já
existente" e travava sem criar job nem gastar nada — seguro (não corrompeu
nada, não cobrou duas vezes), mas também não processava o lote novo. O
fingerprint do conjunto exato de `(nome, hash_esperado)` pendente resolve:
mesmo lote → mesmo registro, retomado; lote diferente → chave diferente, job
novo. Este teste trava a correção.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def modulo():
    caminho = RAIZ / "scripts" / "ocr_batch_mistral.py"
    spec = importlib.util.spec_from_file_location("ocr_batch_mistral", caminho)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ocr_batch_mistral"] = mod
    spec.loader.exec_module(mod)
    return mod


def _doc(modulo, nome, hash_esperado, paginas=10):
    return modulo.Documento(
        nome=nome,
        empresa="X",
        trimestre="2T2025",
        caminho=Path(nome),
        hash_esperado=hash_esperado,
        paginas=paginas,
    )


class TestFingerprintPendentes:
    def test_independente_da_ordem(self, modulo):
        a = _doc(modulo, "a", "h1")
        b = _doc(modulo, "b", "h2")
        assert modulo.fingerprint_pendentes([a, b]) == modulo.fingerprint_pendentes(
            [b, a]
        )

    def test_lotes_diferentes_geram_fingerprints_diferentes(self, modulo):
        a = _doc(modulo, "a", "h1")
        b = _doc(modulo, "b", "h2")
        c = _doc(modulo, "c", "h3")
        assert modulo.fingerprint_pendentes(
            [a, b]
        ) != modulo.fingerprint_pendentes([a, c])

    def test_mesmo_nome_hash_diferente_muda_fingerprint(self, modulo):
        # Reprocessamento após correção de conteúdo (hash novo) não pode casar
        # com o registro do conteúdo antigo.
        a_v1 = _doc(modulo, "a", "h1")
        a_v2 = _doc(modulo, "a", "h2")
        assert modulo.fingerprint_pendentes(
            [a_v1]
        ) != modulo.fingerprint_pendentes([a_v2])


class TestMigracaoJournal:
    def test_journal_antigo_flat_migra_para_lotes(self, modulo, tmp_path):
        caminho = tmp_path / "journal_ocr_batch.json"
        caminho.write_text(
            json.dumps({"job_id": "job-antigo", "status": "SUCCESS"}),
            encoding="utf-8",
        )
        original = modulo.CAMINHO_JOURNAL
        modulo.CAMINHO_JOURNAL = caminho
        try:
            migrado = modulo._ler_journal()
        finally:
            modulo.CAMINHO_JOURNAL = original
        assert "lotes" in migrado
        registros = list(migrado["lotes"].values())
        assert len(registros) == 1
        assert registros[0]["job_id"] == "job-antigo"

    def test_journal_ausente_comeca_vazio(self, modulo, tmp_path):
        caminho = tmp_path / "nao_existe.json"
        original = modulo.CAMINHO_JOURNAL
        modulo.CAMINHO_JOURNAL = caminho
        try:
            journal = modulo._ler_journal()
        finally:
            modulo.CAMINHO_JOURNAL = original
        assert journal == {"lotes": {}}

    def test_lote_novo_nao_casa_com_job_antigo_concluido(self, modulo, tmp_path):
        """O cenário exato do achado: job velho concluído não bloqueia lote novo."""
        caminho = tmp_path / "journal_ocr_batch.json"
        caminho.write_text(
            json.dumps({"job_id": "job-2026-08-10", "status": "SUCCESS"}),
            encoding="utf-8",
        )
        original = modulo.CAMINHO_JOURNAL
        modulo.CAMINHO_JOURNAL = caminho
        try:
            journal = modulo._ler_journal()
            lote_novo = modulo.fingerprint_pendentes([_doc(modulo, "novo", "hnovo")])
            registro = journal["lotes"].get(lote_novo)
        finally:
            modulo.CAMINHO_JOURNAL = original
        assert registro is None, (
            "lote novo não pode herdar o job_id de um lote antigo diferente"
        )


class TestGravarResultados:
    def test_documento_ausente_da_saida_vira_falho(self, modulo, tmp_path):
        """Achado em 2026-08-27: a Mistral pode OMITIR a linha de um request
        que falhou, em vez de devolver erro explícito. 23 de 24 gravaram; o
        24º não tinha `custom_id` nenhum na saída, e sem esta checagem
        `falhos` saía vazio — documento sumindo do corpus sem sinal de erro.
        """
        modulo.DIR_CACHE_OCR = tmp_path
        a = _doc(modulo, "a", "ha")
        b = _doc(modulo, "b", "hb")
        documentos = {"a": a, "b": b}
        # Só "a" aparece na saída — "b" falhou de forma catastrófica na API e
        # a Mistral simplesmente não devolveu linha nenhuma para ele.
        linha_a = json.dumps(
            {
                "custom_id": "a",
                "response": {"status_code": 200, "body": {"model": "m"}},
            }
        )
        gravados, falhos = modulo.gravar_resultados(
            (linha_a + "\n").encode("utf-8"), documentos
        )
        assert gravados == ["a"]
        assert any("b" in item and "ausente" in item for item in falhos)

    def test_documento_com_erro_explicito_nao_duplica_em_falhos(
        self, modulo, tmp_path
    ):
        modulo.DIR_CACHE_OCR = tmp_path
        a = _doc(modulo, "a", "ha")
        documentos = {"a": a}
        linha = json.dumps({"custom_id": "a", "error": {"message": "boom"}})
        gravados, falhos = modulo.gravar_resultados(
            (linha + "\n").encode("utf-8"), documentos
        )
        assert gravados == []
        assert len(falhos) == 1
        assert "erro na resposta" in falhos[0]
