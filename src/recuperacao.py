"""Recuperação top-k com filtro de metadados e subconsulta por banco.

Seção 5.7 (RF06) + estratégias E0–E3 da seção 5.16. A decomposição por
instituição nas perguntas comparativas evita o modo de falha nº 6 (top-k
dominado por um único banco).

O braço semântico usa o filtro nativo do Chroma (``where``): a restrição por
empresa/trimestre entra na própria consulta e o ranqueamento já nasce
restrito. Antes, com FAISS, era preciso rankear a coleção inteira e descartar
o que não passava — filtragem depois do ranqueamento, que é justamente o que a
RF06 proíbe. O braço BM25 continua filtrando em memória porque o `rank_bm25`
não tem índice de metadados: ele pontua a lista inteira de chunks e não há
consulta para onde empurrar a restrição.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from src.config import Config
from src.indexacao import (
    ErroConsistenciaIndice,
    ProvedorEmbeddings,
    calcular_hash_corpus_atual_para_indice,
    carregar_indice_bm25,
    carregar_indice_chroma,
    fabricar_provedor_embeddings,
)
from src.ingestao import Chunk
from src.normalizacao import (
    extrair_bancos_citados,
    extrair_trimestres_citados,
    normalizar_texto_bm25,
    remover_acentos,
)


class Estrategia(str, Enum):
    """Vocabulário idêntico ao aceito em ESTRATEGIA_PADRAO no .env (5.14)."""

    CLOSED_BOOK = "closed_book"  # E0 — diagnóstico, não candidata
    KEYWORD = "keyword"          # E1 — BM25
    SEMANTICA = "semantica"      # E2 — embeddings (estratégia-alvo)
    HIBRIDA = "hibrida"          # E3 — RRF de E1+E2 (Fase 2)
    FATOS = "fatos"              # E4 — tabela de fatos numéricos (5.7)


@dataclass(frozen=True, init=False)
class FiltroMetadados:
    """Restrições extraídas da pergunta (vocabulário fechado — sem NER).

    ``trimestre`` continua aceito no construtor e exposto como propriedade por
    compatibilidade. Internamente o filtro guarda todos os períodos citados,
    combinados com OR.
    """

    empresas: tuple[str, ...]
    trimestres: tuple[str, ...]

    def __init__(
        self,
        empresas: tuple[str, ...] = (),
        trimestre: str | None = None,
        trimestres: tuple[str, ...] = (),
    ) -> None:
        periodos = tuple(dict.fromkeys(
            (*((trimestre,) if trimestre else ()), *trimestres)
        ))
        object.__setattr__(self, "empresas", tuple(dict.fromkeys(empresas)))
        object.__setattr__(self, "trimestres", periodos)

    @property
    def trimestre(self) -> str | None:
        """Primeiro período, apenas para consumidores legados."""
        return self.trimestres[0] if self.trimestres else None

    @property
    def comparativa(self) -> bool:
        """2+ bancos citados => decompor em subconsultas por instituição."""
        return len(self.empresas) >= 2

    @property
    def multiplo_escopo(self) -> bool:
        """Há mais de uma instituição ou período que precisa de cobertura."""
        return len(self.empresas) >= 2 or len(self.trimestres) >= 2


@dataclass(frozen=True)
class ResultadoRecuperacao:
    chunk: Chunk
    score: float
    origem: Estrategia  # qual índice produziu este hit (relevante na híbrida)


_BANCOS_CORPUS_PADRAO = ("BTG", "ITAU", "BRADESCO", "SANTANDER", "BB")
_PADRAO_COMPARATIVA_GENERICA = re.compile(
    r"(?:\b(?:os\s+)?(?:cinco|5)\s+(?:bancos|instituicoes)\b|"
    r"\btodos\s+os\s+bancos\b|\bentre\s+os\s+bancos\b|"
    r"\bdos\s+cinco\s+bancos\b|"
    r"\b(?:qual|que)\s+(?:dos\s+)?(?:banco|instituicao)\b)",
    re.IGNORECASE,
)


def extrair_filtro_metadados(
    pergunta: str,
    bancos_corpus: tuple[str, ...] | None = None,
) -> FiltroMetadados:
    """Extrai empresas e todos os períodos do vocabulário fechado.

    Menções coletivas como "os cinco bancos" são expandidas para o universo
    configurado. Sem isso, justamente as comparativas globais deixam de ser
    decompostas e o top-k tende a ser dominado por uma instituição.
    """
    empresas = tuple(extrair_bancos_citados(pergunta))
    pergunta_normalizada = remover_acentos(pergunta).lower()
    if not empresas and _PADRAO_COMPARATIVA_GENERICA.search(pergunta_normalizada):
        empresas = tuple(bancos_corpus or _BANCOS_CORPUS_PADRAO)
    return FiltroMetadados(
        empresas=empresas,
        trimestres=tuple(extrair_trimestres_citados(pergunta)),
    )


def fusao_reciprocal_rank(
    rankings: list[list[ResultadoRecuperacao]], k: int = 60
) -> list[ResultadoRecuperacao]:
    """Reciprocal Rank Fusion para a estratégia E3 (seção 5.10)."""
    if type(k) is not int or k <= 0:
        raise ValueError("k da RRF deve ser um inteiro positivo.")
    acumulado: dict[str, float] = {}
    primeiro: dict[str, ResultadoRecuperacao] = {}
    for ranking in rankings:
        for posicao, resultado in enumerate(ranking, start=1):
            chave = resultado.chunk.id
            acumulado[chave] = acumulado.get(chave, 0.0) + 1.0 / (k + posicao)
            primeiro.setdefault(chave, resultado)
    return [
        ResultadoRecuperacao(primeiro[chave].chunk, score, primeiro[chave].origem)
        for chave, score in sorted(acumulado.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _passa_filtro(chunk: Chunk, filtro: FiltroMetadados) -> bool:
    if filtro.empresas and chunk.empresa not in filtro.empresas:
        return False
    if filtro.trimestres and chunk.trimestre not in filtro.trimestres:
        return False
    return True


def filtro_where_chroma(filtro: FiltroMetadados) -> dict | None:
    """Traduz o filtro para a cláusula `where` nativa do Chroma (RF06).

    Cada dimensão citada vira um `$in` (OR entre os valores) e as duas, quando
    presentes, são combinadas por `$and`. Sem restrição devolve ``None``, que
    é o "sem filtro" esperado pelo Chroma.
    """
    condicoes = [
        {campo: {"$in": list(valores)}}
        for campo, valores in (
            ("empresa", filtro.empresas),
            ("trimestre", filtro.trimestres),
        )
        if valores
    ]
    if not condicoes:
        return None
    if len(condicoes) == 1:
        return condicoes[0]
    return {"$and": condicoes}


def _como_lista_de_consulta(consulta) -> list[list[float]]:
    """Aceita matriz numpy (1, dim) ou lista de listas e devolve lista."""
    if hasattr(consulta, "tolist"):
        consulta = consulta.tolist()
    if (
        not isinstance(consulta, list)
        or len(consulta) != 1
        or not isinstance(consulta[0], list)
    ):
        raise ValueError(
            "A consulta semântica deve ser uma única linha de embedding."
        )
    return consulta


def _intercalar_por_escopo(
    rankings: list[list[ResultadoRecuperacao]], top_k: int
) -> list[ResultadoRecuperacao]:
    """Round-robin: dá a cada par banco–período a primeira vaga possível."""
    resultado: list[ResultadoRecuperacao] = []
    vistos: set[str] = set()
    maior = max((len(r) for r in rankings), default=0)
    for posicao in range(maior):
        for ranking in rankings:
            if posicao < len(ranking) and ranking[posicao].chunk.id not in vistos:
                vistos.add(ranking[posicao].chunk.id)
                resultado.append(ranking[posicao])
    return resultado[:top_k]


class Recuperador:
    """Fachada única de recuperação usada pela geração, avaliação e interface.

    Recebe os índices já carregados (a carga valida RNF09 em
    `indexacao.carregar_indice_chroma`).
    """

    def __init__(
        self,
        config: Config,
        indice_chroma=None,
        indice_bm25=None,
        provedor_embeddings: ProvedorEmbeddings | None = None,
        hash_corpus_esperado: str | None = None,
        indice_faiss=None,
    ):
        # `indice_faiss` é apelido de transição para os chamadores que ainda
        # não foram atualizados; a implementação por baixo já é Chroma.
        if indice_chroma is not None and indice_faiss is not None:
            raise ValueError(
                "Informe indice_chroma OU indice_faiss (apelido), não ambos."
            )
        self.config = config
        self._chroma = indice_chroma if indice_chroma is not None else indice_faiss
        self._bm25 = indice_bm25    # (BM25Okapi, list[Chunk])
        self._provedor = provedor_embeddings
        self._hash_corpus_esperado = hash_corpus_esperado
        self._chunks_por_id: dict[str, Chunk] | None = None
        self._indice_fatos = None

    def _garantir_provedor(self) -> ProvedorEmbeddings:
        if self._provedor is None:
            self._provedor = fabricar_provedor_embeddings(self.config)
        return self._provedor

    def _garantir_hash_corpus(self) -> str:
        if self._hash_corpus_esperado is None:
            self._hash_corpus_esperado = calcular_hash_corpus_atual_para_indice()
        return self._hash_corpus_esperado

    def _garantir_chroma(self):
        if self._chroma is None:
            self._chroma = carregar_indice_chroma(
                self._garantir_provedor(),
                config=self.config,
                hash_corpus_esperado=self._garantir_hash_corpus(),
            )
        return self._chroma

    def _chunk_por_id(self, chunks: list[Chunk]) -> dict[str, Chunk]:
        """Mapa id->chunk; o Chroma devolve ids, o resto do sistema usa Chunk."""
        if self._chunks_por_id is None:
            self._chunks_por_id = {chunk.id: chunk for chunk in chunks}
        return self._chunks_por_id

    def _garantir_bm25(self):
        if self._bm25 is None:
            self._bm25 = carregar_indice_bm25(
                config=self.config,
                hash_corpus_esperado=self._garantir_hash_corpus()
            )
        return self._bm25

    def _garantir_indice_fatos(self):
        """Tabela de fatos construída sob demanda a partir dos chunks do BM25.

        Usa o conjunto do BM25 porque é a única lista completa de chunks já
        materializada em memória — a coleção Chroma guarda vetores, não texto.
        """
        if self._indice_fatos is None:
            from src.fatos import construir_indice_fatos

            _bm25, chunks = self._garantir_bm25()
            self._indice_fatos = construir_indice_fatos(chunks)
        return self._indice_fatos

    def recuperar(
        self,
        pergunta: str,
        estrategia: Estrategia,
        top_k: int | None = None,
    ) -> list[ResultadoRecuperacao]:
        """Top-k trechos para a pergunta, conforme a estratégia.

        Contrato (seção 5.7):
          - CLOSED_BOOK devolve lista vazia (E0 não recupera nada);
          - filtro por empresa/trimestre é aplicado ANTES de rankear;
          - pergunta comparativa: top-k POR banco detectado, depois fusão —
            garante todas as instituições representadas no resultado.
        """
        if not isinstance(pergunta, str) or not pergunta.strip():
            raise ValueError("pergunta deve ser texto não vazio.")
        top_k = self.config.top_k if top_k is None else top_k
        if type(top_k) is not int or top_k <= 0:
            raise ValueError("top_k deve ser um inteiro positivo.")
        if estrategia == Estrategia.CLOSED_BOOK:
            return []
        filtro = extrair_filtro_metadados(pergunta, self.config.bancos)
        consulta_semantica = None
        if estrategia in (Estrategia.SEMANTICA, Estrategia.HIBRIDA):
            # Uma única pergunta gera um único embedding, mesmo quando a busca
            # é decomposta por banco. Os filtros são aplicados sobre o mesmo
            # vetor e não justificam chamadas repetidas ao provedor.
            self._garantir_chroma()
            consulta_semantica = self._garantir_provedor().embedar([pergunta])
        if filtro.comparativa:
            filtros: list[FiltroMetadados]
            if filtro.empresas and filtro.trimestres:
                filtros = [
                    FiltroMetadados(empresas=(empresa,), trimestres=(trimestre,))
                    for empresa in filtro.empresas
                    for trimestre in filtro.trimestres
                ]
            elif filtro.empresas:
                filtros = [
                    FiltroMetadados(empresas=(empresa,))
                    for empresa in filtro.empresas
                ]
            else:
                filtros = [
                    FiltroMetadados(trimestres=(trimestre,))
                    for trimestre in filtro.trimestres
                ]
            por_escopo = [
                self._recuperar_filtrado(
                    pergunta,
                    estrategia,
                    filtro_especifico,
                    top_k,
                    consulta_semantica,
                )
                for filtro_especifico in filtros
            ]
            return _intercalar_por_escopo(por_escopo, top_k)
        if len(filtro.trimestres) >= 2:
            por_periodo = [
                self._recuperar_filtrado(
                    pergunta,
                    estrategia,
                    FiltroMetadados(
                        empresas=filtro.empresas, trimestres=(trimestre,)
                    ),
                    top_k,
                    consulta_semantica,
                )
                for trimestre in filtro.trimestres
            ]
            return _intercalar_por_escopo(por_periodo, top_k)
        return self._recuperar_filtrado(
            pergunta, estrategia, filtro, top_k, consulta_semantica
        )

    def _recuperar_filtrado(
        self,
        pergunta: str,
        estrategia: Estrategia,
        filtro: FiltroMetadados,
        top_k: int,
        consulta_semantica=None,
    ) -> list[ResultadoRecuperacao]:
        if estrategia == Estrategia.KEYWORD:
            return self._top_bm25(pergunta, filtro, top_k)
        if estrategia == Estrategia.FATOS:
            return self._top_fatos(pergunta, filtro, top_k)
        if estrategia == Estrategia.SEMANTICA:
            return self._top_chroma(
                pergunta, filtro, top_k, consulta_semantica
            )
        if estrategia == Estrategia.HIBRIDA:
            return fusao_reciprocal_rank(
                [
                    self._top_bm25(pergunta, filtro, top_k),
                    self._top_chroma(
                        pergunta, filtro, top_k, consulta_semantica
                    ),
                ]
            )[:top_k]
        raise ValueError(f"Estratégia sem recuperação definida: {estrategia!r}")

    def _top_bm25(
        self, pergunta: str, filtro: FiltroMetadados, top_k: int
    ) -> list[ResultadoRecuperacao]:
        bm25, chunks = self._garantir_bm25()
        scores = bm25.get_scores(normalizar_texto_bm25(pergunta))
        permitidos = [
            i for i, chunk in enumerate(chunks) if _passa_filtro(chunk, filtro)
        ]
        melhores = sorted(permitidos, key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            ResultadoRecuperacao(chunks[i], float(scores[i]), Estrategia.KEYWORD)
            for i in melhores
            if scores[i] > 0.0
        ]

    def _top_fatos(
        self, pergunta: str, filtro: FiltroMetadados, top_k: int
    ) -> list[ResultadoRecuperacao]:
        """E4 — chunk ranqueado por densidade de fatos da métrica perguntada.

        Não se funde com E1/E2 de propósito. Medido em 2026-08-20 sob o mesmo
        orçamento de top-5: o canal sozinho leva o valor exato do gabarito em
        11/15 factuais, contra 9/15 do E3; qualquer combinação dos dois no
        mesmo orçamento cai para 8–9/15, porque dividir cinco vagas entre duas
        listas expulsa justamente o trecho que só uma delas achou. A união só
        vence com dez vagas — o que é outro orçamento de contexto, não outra
        estratégia, e não seria comparável com E1–E3.
        """
        indice = self._garantir_indice_fatos()
        _bm25, chunks = self._garantir_bm25()
        por_id = self._chunk_por_id(chunks)
        pontuados = indice.pontuar_chunks(
            pergunta, filtro.empresas, filtro.trimestres
        )
        resultados: list[ResultadoRecuperacao] = []
        for identificador, pontos in pontuados[:top_k]:
            chunk = por_id.get(identificador)
            if chunk is None:
                raise ErroConsistenciaIndice(
                    f"A tabela de fatos referenciou o chunk {identificador!r}, "
                    "ausente do conjunto persistido (RNF09); reconstrua o "
                    "índice."
                )
            resultados.append(
                ResultadoRecuperacao(chunk, float(pontos), Estrategia.FATOS)
            )
        return resultados

    def _top_chroma(
        self,
        pergunta: str,
        filtro: FiltroMetadados,
        top_k: int,
        consulta=None,
    ) -> list[ResultadoRecuperacao]:
        """Consulta a coleção já restrita pelo `where` nativo (RF06).

        Pede exatamente `top_k` resultados porque a restrição foi aplicada
        antes do ranqueamento — não há mais o padrão antigo de rankear a
        coleção inteira para depois descartar o que não passava no filtro.
        """
        colecao, chunks = self._garantir_chroma()
        if consulta is None:
            consulta = self._garantir_provedor().embedar([pergunta])
        resposta = colecao.query(
            query_embeddings=_como_lista_de_consulta(consulta),
            n_results=top_k,
            where=filtro_where_chroma(filtro),
            include=["distances"],
        )
        ids = list((resposta.get("ids") or [[]])[0])
        distancias = list((resposta.get("distances") or [[]])[0])
        if len(distancias) != len(ids):
            raise ErroConsistenciaIndice(
                "Coleção Chroma devolveu distâncias em quantidade diferente "
                "dos ids retornados."
            )
        por_id = self._chunk_por_id(chunks)
        resultados: list[ResultadoRecuperacao] = []
        for identificador, distancia in zip(ids, distancias):
            chunk = por_id.get(identificador)
            if chunk is None:
                raise ErroConsistenciaIndice(
                    f"Coleção Chroma devolveu o id {identificador!r}, ausente "
                    "dos chunks persistidos (RNF09); reconstrua o índice."
                )
            # Guarda, não filtro: se o `where` nativo deixasse passar um trecho
            # fora do escopo, o resultado seria silenciosamente errado.
            if not _passa_filtro(chunk, filtro):
                raise ErroConsistenciaIndice(
                    f"O filtro nativo do Chroma devolveu o chunk {chunk.id!r} "
                    f"({chunk.empresa}/{chunk.trimestre}) fora do escopo "
                    f"pedido (empresas={filtro.empresas}, "
                    f"trimestres={filtro.trimestres}); reconstrua o índice."
                )
            # Espaço cosseno sobre vetores L2-normalizados: 1 - distância é
            # exatamente o produto interno que o IndexFlatIP devolvia.
            resultados.append(
                ResultadoRecuperacao(
                    chunk, 1.0 - float(distancia), Estrategia.SEMANTICA
                )
            )
        return resultados[:top_k]
