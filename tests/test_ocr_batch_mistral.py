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


class TestPaginasNoCache:
    def test_schema_do_lote(self, modulo, tmp_path):
        caminho = tmp_path / "a.json"
        caminho.write_text(
            json.dumps({"ocr": {"pages": [{}, {}, {}]}}), encoding="utf-8"
        )
        assert modulo.paginas_no_cache(caminho) == 3

    def test_schema_da_ancora(self, modulo, tmp_path):
        caminho = tmp_path / "a.json"
        caminho.write_text(json.dumps({"paginas": [{}, {}]}), encoding="utf-8")
        assert modulo.paginas_no_cache(caminho) == 2

    def test_schema_desconhecido_devolve_none(self, modulo, tmp_path):
        caminho = tmp_path / "a.json"
        caminho.write_text(json.dumps({"outra_coisa": 1}), encoding="utf-8")
        assert modulo.paginas_no_cache(caminho) is None

    def test_json_corrompido_devolve_none(self, modulo, tmp_path):
        caminho = tmp_path / "a.json"
        caminho.write_text("{nao é json", encoding="utf-8")
        assert modulo.paginas_no_cache(caminho) is None


class TestSepararPendentes:
    def _fonte(self, modulo, tmp_path):
        return modulo.FonteCorpus(
            nome="t",
            manifesto=tmp_path / "m.csv",
            dir_raw=tmp_path / "raw",
            dir_cache=tmp_path / "cache",
            coluna_periodo="trimestre",
        )

    def test_cache_ausente_e_pendente(self, modulo, tmp_path):
        fonte = self._fonte(modulo, tmp_path)
        fonte.dir_cache.mkdir()
        doc = _doc(modulo, "a", "ha", paginas=10)
        pendentes, incompletos, indet = modulo.separar_pendentes([doc], fonte)
        assert [d.nome for d in pendentes] == ["a"]
        assert incompletos == [] and indet == []

    def test_cache_completo_nao_e_pendente(self, modulo, tmp_path):
        fonte = self._fonte(modulo, tmp_path)
        fonte.dir_cache.mkdir()
        doc = _doc(modulo, "a", "ha", paginas=3)
        (fonte.dir_cache / "ha.json").write_text(
            json.dumps({"ocr": {"pages": [{}, {}, {}]}}), encoding="utf-8"
        )
        pendentes, incompletos, indet = modulo.separar_pendentes([doc], fonte)
        assert pendentes == [] and incompletos == [] and indet == []

    def test_cache_parcial_volta_a_ser_pendente(self, modulo, tmp_path):
        """O caso real: 8 de 71 páginas do BTG 4T2025 no cache de âncora.

        "Arquivo existe" não é "documento processado". Sem esta checagem, 63
        páginas ficariam fora do cache sem nenhum sinal de erro.
        """
        fonte = self._fonte(modulo, tmp_path)
        fonte.dir_cache.mkdir()
        doc = _doc(modulo, "btg_ifrs_4T2025", "hbtg", paginas=71)
        (fonte.dir_cache / "hbtg.json").write_text(
            json.dumps({"paginas": [{} for _ in range(8)]}), encoding="utf-8"
        )
        pendentes, incompletos, indet = modulo.separar_pendentes([doc], fonte)
        assert [d.nome for d in pendentes] == ["btg_ifrs_4T2025"]
        assert incompletos == ["btg_ifrs_4T2025 (8/71 pp)"]
        assert indet == []

    def test_schema_desconhecido_nao_gasta_por_acidente(self, modulo, tmp_path):
        """Formato que não sei ler é "não sei", nunca "está incompleto".

        Tratar desconhecido como incompleto faria uma mudança de schema virar
        reprocessamento pago do corpus inteiro, sem ninguém pedir.
        """
        fonte = self._fonte(modulo, tmp_path)
        fonte.dir_cache.mkdir()
        doc = _doc(modulo, "a", "ha", paginas=10)
        (fonte.dir_cache / "ha.json").write_text(
            json.dumps({"formato_novo": []}), encoding="utf-8"
        )
        pendentes, incompletos, indet = modulo.separar_pendentes([doc], fonte)
        assert pendentes == []
        assert indet == ["a"]


class TestFonteIFRS:
    def test_cache_ifrs_nao_colide_com_o_de_ancora(self, modulo):
        """O cache de âncora é evidência de um gate APROVADO.

        Ele é endereçado pelo mesmo hash de PDF, então gravar o documento
        inteiro no mesmo diretório sobrescreveria a evidência do G4 com um
        arquivo de outro schema.
        """
        ifrs = modulo.FONTES["ifrs"]
        assert ifrs.dir_cache.name == "ocr_documento"
        assert ifrs.dir_cache != ifrs.dir_raw.parent / "ocr"

    def test_fonte_principal_permanece_o_default(self, modulo):
        assert modulo.carregar_documentos.__defaults__[0] is modulo.FONTES["principal"]


class TestGravarResultados:
    def test_documento_ausente_da_saida_vira_falho(self, modulo, tmp_path):
        """Achado em 2026-08-27: a Mistral pode OMITIR a linha de um request
        que falhou, em vez de devolver erro explícito. 23 de 24 gravaram; o
        24º não tinha `custom_id` nenhum na saída, e sem esta checagem
        `falhos` saía vazio — documento sumindo do corpus sem sinal de erro.
        """
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
        # `dir_cache` vai EXPLÍCITO. Atribuir `modulo.DIR_CACHE_OCR = tmp_path`
        # não funciona — o default do parâmetro é vinculado na definição da
        # função, então a atribuição não o alcança e a gravação cai no cache
        # REAL. Foi assim que uma versão anterior deste teste escreveu
        # `corpus/ocr/ha.json` no cache do projeto e mudou o `hash_cache_ocr`
        # que a RNF09 usa para validar o índice publicável.
        gravados, falhos = modulo.gravar_resultados(
            (linha_a + "\n").encode("utf-8"), documentos, tmp_path
        )
        assert gravados == ["a"]
        assert any("b" in item and "ausente" in item for item in falhos)
        assert (tmp_path / "ha.json").is_file()

    def test_documento_com_erro_explicito_nao_duplica_em_falhos(
        self, modulo, tmp_path
    ):
        a = _doc(modulo, "a", "ha")
        documentos = {"a": a}
        linha = json.dumps({"custom_id": "a", "error": {"message": "boom"}})
        gravados, falhos = modulo.gravar_resultados(
            (linha + "\n").encode("utf-8"), documentos, tmp_path
        )
        assert gravados == []
        assert len(falhos) == 1
        assert "erro na resposta" in falhos[0]

    def test_nao_escreve_fora_do_dir_cache_recebido(self, modulo, tmp_path):
        """Contraprova da poluição: nada sai do diretório passado.

        O cache real do projeto é evidência versionada (RNF10) e entra no
        `hash_cache_ocr` do índice (RNF09) — um teste que escreve nele
        invalida o índice publicável sem ninguém notar.
        """
        cache_real = modulo.DIR_CACHE_OCR
        antes = {p.name for p in cache_real.glob("*.json")}
        doc = _doc(modulo, "z", "hz")
        linha = json.dumps(
            {
                "custom_id": "z",
                "response": {"status_code": 200, "body": {"model": "m"}},
            }
        )
        modulo.gravar_resultados(
            (linha + "\n").encode("utf-8"), {"z": doc}, tmp_path
        )
        depois = {p.name for p in cache_real.glob("*.json")}
        assert antes == depois, "gravar_resultados escreveu fora do dir_cache"
