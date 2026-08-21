"""Tabela de fatos numéricos do corpus — a via de recuperação exata (E4).

Motivo de existir, medido em 2026-08-20 sobre as 15 factuais congeladas: o
E3 recupera a **página** certa em 12/15, mas o chunk que ele traz contém o
valor exato do gabarito em apenas 9/15. A diferença é a classe de falha do
DEV007 — a página certa é recuperada pelo texto corrido, que arredonda
("R$ 3,4 bilhões"), enquanto a tabela com `3.431` fica fora do top-k. Um canal
que ranqueia chunk por **quantos fatos da métrica perguntada ele contém**
inverte essa preferência: mede 11/15 no mesmo orçamento de top-5.

O que este módulo NÃO é: uma tabela de respostas. Medido no mesmo dia — o
valor do gabarito está entre os candidatos de uma consulta em 14/15, mas é o
mais frequente em só 4/15, com 70 a 700 valores distintos por consulta.
Ranquear valor é ruído; ranquear chunk funciona. Por isso a saída daqui são
trechos para o mesmo prompt de geração, e a guarda da RN02 continua sendo
quem decide se o número respondido está fundamentado.

O parser é o de `geracao.fatos_numericos_do_chunk` — o MESMO que a guarda da
RN02 usa. Um segundo interpretador divergiria da guarda e este canal passaria
a propor páginas que o grounding depois recusa.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter, defaultdict

from src.geracao import (
    _GRUPOS_METRICAS,
    _numero_tem_dimensao_de_metrica,
    _tokens_metrica_grounding,
    fatos_numericos_do_chunk,
)
from src.ingestao import Chunk
from src.normalizacao import NumeroPtBR


@dataclass(frozen=True)
class FatoNumerico:
    """Um número do corpus com a métrica que o governa e sua procedência.

    ``grupos`` é o vocabulário fechado de `_GRUPOS_METRICAS` — não os tokens
    livres da linha. O canal ranqueia chunk, não valor, e para ranquear basta
    a métrica coarse; guardar os tokens livres dos 163 mil fatos custaria
    memória sem mudar a ordem.
    """

    chunk_id: str
    numero: NumeroPtBR
    grupos: frozenset[str]


class IndiceFatos:
    """Fatos agrupados por (empresa, trimestre) — a chave que a RF06 filtra.

    O agrupamento é o próprio filtro de metadados: a restrição por
    empresa/período acontece ANTES de qualquer pontuação, como a RF06 exige,
    porque só os baldes pedidos são varridos.
    """

    def __init__(self, por_escopo: dict[tuple[str, str], list[FatoNumerico]]):
        self._por_escopo = por_escopo
        self._empresas = tuple(sorted({e for e, _ in por_escopo}))
        self._trimestres = tuple(sorted({t for _, t in por_escopo}))

    @property
    def total_de_fatos(self) -> int:
        return sum(len(fatos) for fatos in self._por_escopo.values())

    def pontuar_chunks(
        self,
        pergunta: str,
        empresas: tuple[str, ...] = (),
        trimestres: tuple[str, ...] = (),
    ) -> list[tuple[str, float]]:
        """Chunks ordenados por quantidade de fatos da métrica perguntada.

        Sem métrica reconhecida na pergunta o canal devolve lista vazia em vez
        de ranquear por densidade numérica bruta: "qual banco tem a melhor
        governança" não tem resposta em tabela, e devolver o chunk com mais
        números seria ruído com aparência de resultado.

        Empate é desfeito pelo id do chunk — a avaliação compara estratégias e
        não pode depender da ordem de iteração de um dicionário.
        """
        grupos_pergunta = _tokens_metrica_grounding(pergunta) & set(
            _GRUPOS_METRICAS
        )
        if not grupos_pergunta:
            return []
        contagem: Counter[str] = Counter()
        for empresa in empresas or self._empresas:
            for trimestre in trimestres or self._trimestres:
                for fato in self._por_escopo.get((empresa, trimestre), ()):
                    if not (fato.grupos & grupos_pergunta):
                        continue
                    if not _numero_tem_dimensao_de_metrica(
                        fato.numero, grupos_pergunta
                    ):
                        continue
                    contagem[fato.chunk_id] += 1
        return sorted(contagem.items(), key=lambda par: (-par[1], par[0]))


def construir_indice_fatos(chunks: list[Chunk]) -> IndiceFatos:
    """Materializa a tabela de fatos a partir dos chunks já indexados.

    Deriva dos chunks, não do PDF: assim a unidade de recuperação do canal é a
    mesma que o E1/E2/E3 devolvem, e a comparação entre estratégias mede a
    ordenação, não uma granularidade diferente de trecho.

    Custo medido no corpus atual (7.574 chunks): ~38 s e 163 mil fatos. Não é
    persistido de propósito — um artefato em disco derivado dos chunks criaria
    a classe de defeito "índice novo, fatos velhos", que exigiria sua própria
    guarda de consistência. Construir sob demanda torna a incoerência
    impossível por construção.
    """
    por_escopo: dict[tuple[str, str], list[FatoNumerico]] = defaultdict(list)
    for chunk in chunks:
        for numero, tokens, _modificadores in fatos_numericos_do_chunk(chunk):
            grupos = tokens & set(_GRUPOS_METRICAS)
            if not grupos:
                # Fato sem métrica nomeada não discrimina chunk nenhum: entra
                # em toda consulta com o mesmo peso. Guardá-lo quadruplicaria
                # a tabela sem mudar uma única ordenação.
                continue
            por_escopo[(chunk.empresa, chunk.trimestre)].append(
                FatoNumerico(chunk.id, numero, frozenset(grupos))
            )
    return IndiceFatos(dict(por_escopo))
