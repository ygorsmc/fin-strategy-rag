"""Nenhum chunk pode ABRIR com linhas de valor sem a linha que nomeia a coluna.

Achado da auditoria de 2026-08-23, rastreado a partir do TSTF006: o modelo
respondeu ``R$ 12.144 milhões`` (coluna 4T25) a uma pergunta sobre o 1T2026,
cujo valor é ``11.875``. As duas colunas chegaram ao contexto na MESMA linha e
**sem cabeçalho** — não havia como acertar por leitura.

A tabela estava montada corretamente pelo OCR. Quem a quebrou foi o chunker,
por dois caminhos independentes:

1. **A cauda de sobreposição** copiava os últimos tokens do chunk emitido sem
   olhar o tipo do bloco; terminando em tabela, o chunk seguinte abria no meio
   da grade.
2. **A partição de tabela grande** media a parte sem contar a legenda de
   unidade que ela mesma emite junto; a parte estourava o orçamento na emissão
   e era repartida por tokens, sem repetir o cabeçalho.

Medido no corpus: **101 chunks** abriam com 3+ colunas de valor sem cabeçalho
(18 das 45 perguntas congeladas recebiam um deles no top-5). Depois das duas
correções: **zero**.
"""

from __future__ import annotations

import re

import pytest

from src import ingestao
from src.config import Config
from src.ingestao import PaginaExtraida


def _e_separador(linha: str) -> bool:
    return re.match(r"^\s*\|[\s:|-]*---[\s:|-]*\|", linha) is not None


def abre_com_tabela_orfa(texto: str) -> bool:
    """Chunk que começa em linha de tabela sem o par cabeçalho+separador.

    Layout íntegro: linha 0 é o cabeçalho e linha 1 o separador (o extrator às
    vezes emite o separador primeiro). Qualquer outro arranjo significa linha
    de valor sem a linha que nomeia a coluna.
    """
    linhas = [l for l in texto.splitlines()[1:] if l.strip()]
    if not linhas or not linhas[0].lstrip().startswith("|"):
        return False
    if _e_separador(linhas[0]):
        return False
    return not (len(linhas) > 1 and _e_separador(linhas[1]))


def _tabela(n_linhas: int, colunas: int = 3, legenda: bool = False) -> str:
    cabecalho = "| Métrica | " + " | ".join(
        f"{t}" for t in ("1T26", "4T25", "1T25", "1S25", "1S24")[:colunas]
    ) + " |"
    separador = "| --- |" + " --- |" * colunas
    corpo = "\n".join(
        "| Linha %d | " % i
        + " | ".join(f"{i}.{c}00" for c in range(colunas))
        + " |"
        for i in range(n_linhas)
    )
    prefixo = "Em R$ milhões\n" if legenda else ""
    return f"{prefixo}{cabecalho}\n{separador}\n{corpo}"


class TestCaudaDeSobreposicao:
    def test_overlap_nunca_abre_chunk_no_meio_de_tabela(self, documento_exemplo):
        """Causa 1: o chunk emitido termina em tabela e a cauda a reparte."""
        config = Config(chunk_tamanho_tokens=260, chunk_sobreposicao_tokens=60)
        pagina = PaginaExtraida(
            documento_exemplo,
            1,
            f"{_tabela(6)}\n\nParágrafo posterior que força a emissão do chunk.",
        )
        for chunk in ingestao.gerar_chunks([pagina], config):
            assert not abre_com_tabela_orfa(chunk.texto), (
                f"{chunk.id} abre com linha de valor sem cabeçalho:\n"
                + "\n".join(chunk.texto.splitlines()[:3])
            )

    def test_overlap_de_prosa_continua_atravessando(self, documento_exemplo):
        """Contraprova: a correção não pode matar a sobreposição de texto.

        O overlap existe para costurar prosa entre chunks; descartar tabela da
        cauda não pode virar descartar a cauda inteira.
        """
        config = Config(chunk_tamanho_tokens=200, chunk_sobreposicao_tokens=50)
        paragrafos = "\n".join(
            f"Paragrafo {i} sobre o resultado do trimestre, com extensão "
            "suficiente para ocupar espaço no chunk."
            for i in range(14)
        )
        chunks = ingestao.gerar_chunks(
            [PaginaExtraida(documento_exemplo, 1, paragrafos)], config
        )
        assert len(chunks) > 1
        corpos = [
            "\n".join(chunk.texto.splitlines()[1:]) for chunk in chunks
        ]
        assert any(
            any(
                linha and linha in corpos[i + 1]
                for linha in corpos[i].splitlines()[-1:]
            )
            for i in range(len(corpos) - 1)
        ), "nenhuma sobreposição de prosa sobreviveu entre chunks"


class TestParticaoDeTabelaGrande:
    @pytest.mark.parametrize("legenda", [False, True])
    def test_toda_parte_carrega_o_cabecalho(self, documento_exemplo, legenda):
        """Causa 2: a legenda não entrava no orçamento da parte."""
        config = Config(chunk_tamanho_tokens=240, chunk_sobreposicao_tokens=40)
        pagina = PaginaExtraida(
            documento_exemplo, 1, _tabela(40, colunas=5, legenda=legenda)
        )
        chunks = ingestao.gerar_chunks([pagina], config)
        partes = [c for c in chunks if "tabela" in c.tipo_bloco]
        assert len(partes) > 1, "a tabela deveria ter sido dividida"
        for parte in partes:
            assert not abre_com_tabela_orfa(parte.texto), (
                f"{parte.id} abre sem cabeçalho:\n"
                + "\n".join(parte.texto.splitlines()[:3])
            )

    def test_nenhuma_linha_do_corpo_se_perde_na_particao(
        self, documento_exemplo
    ):
        """Contraprova: repetir cabeçalho não pode custar linha de dado."""
        config = Config(chunk_tamanho_tokens=240, chunk_sobreposicao_tokens=40)
        tabela = _tabela(40, colunas=5, legenda=True)
        chunks = ingestao.gerar_chunks(
            [PaginaExtraida(documento_exemplo, 1, tabela)], config
        )
        corpo = [
            l
            for l in tabela.splitlines()
            if l.startswith("| Linha ")
        ]
        for linha in corpo:
            assert any(linha in c.texto for c in chunks), f"perdida: {linha}"


class TestCorpusReal:
    """A guarda que interessa: o índice publicável, não uma fixture."""

    def test_nenhum_chunk_do_indice_abre_com_tabela_orfa(self):
        import json
        from pathlib import Path

        caminho = Path("artefatos/indice_vetorial/chunks.json")
        if not caminho.exists():
            pytest.skip("índice não construído neste ambiente")
        chunks = json.loads(caminho.read_text(encoding="utf-8"))
        culpados = [
            c["id"]
            for c in chunks
            if abre_com_tabela_orfa(c["texto"])
            and sum(
                1
                for celula in [
                    x.strip()
                    for x in [
                        l for l in c["texto"].splitlines()[1:] if l.strip()
                    ][0].split("|")
                    if x.strip()
                ]
                if re.search(r"\d", celula)
            )
            >= 3
        ]
        assert not culpados, (
            f"{len(culpados)} chunks abrem com colunas de valor sem "
            f"cabeçalho: {culpados[:10]}"
        )
