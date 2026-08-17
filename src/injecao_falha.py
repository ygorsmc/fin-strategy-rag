"""Injeção de falha (spec 5.9.4 · RF25) — separar recusa legítima de bug fantasiado.

Uma recusa pode ser a virtude central do sistema (RN02) ou um defeito de
recuperação vestido de virtude, e as duas são **indistinguíveis pela saída**. O
teste que as separa: remover deliberadamente o trecho que contém a resposta de
um conjunto pequeno de perguntas de gabarito conhecido e reexecutar.

## Como a remoção é feita — e por que não é no índice

A spec fala em "remover do índice". Aqui a remoção acontece **na camada de
ferramenta**, por `RecuperadorComExclusao`: um decorador com a mesma interface
pública de `src.recuperacao.Recuperador` que filtra por `id` os trechos marcados
como removidos **antes** de devolver o resultado ao chamador. Três motivos:

1. mexer em `artefatos/indice_vetorial/` quebraria a guarda RNF09 (o índice
   carrega o hash do corpus que o construiu) e obrigaria a reconstruir depois;
2. reconstruir em namespace separado custaria uma reindexação inteira por
   pergunta — este teste é declarado **barato** pela própria spec;
3. o efeito observável é idêntico: o agente nunca vê o trecho.

Para não trocar uma ablação por um truncamento, o decorador pede ao recuperador
interno `top_k + |removidos|` resultados e corta em `top_k` **depois** de
filtrar — é assim que o (k+1)-ésimo trecho sobe uma posição, como subiria se o
trecho tivesse mesmo saído do índice.

## As três leituras da spec, e as duas de contenção

| Classificação | Leitura |
|---|---|
| `afirma_mesmo_assim` | **falha grave** — respondeu de memória paramétrica (RN02) |
| `recusa` | correto: a recusa acompanha a evidência, não o acaso |
| `recupera_por_outra_camada` | o melhor caso, e só possível porque há duas camadas |
| `resposta_sem_fonte_declarada` | tem lastro, mas não nomeia de onde veio — não é nenhum dos três |
| `evidencia_remanescente_do_corpus` | a ablação não removeu tudo: a pergunta **não** foi testada |

As duas últimas não são invenção de categoria para inflar resultado: são o
registro honesto de execuções que **não** caem em nenhum dos três estados de
5.9.4. Forçá-las para dentro de um dos três é que seria invenção.

## O que a classificação NÃO faz

Ela não lê `violacoes` para decidir. A classificação é calculada de forma
independente sobre a resposta publicada e sobre o que as ferramentas
devolveram — se ela lesse a marcação que o próprio código de RN01/RN02 produziu,
estaria conferindo a rede de segurança com a própria rede de segurança. O que a
marcação acrescenta é a **segunda linha** do registro:
`agente_afirmou_sem_lastro`, que separa "o sistema afirmou" de "o agente tentou
afirmar e o código o converteu em recusa" — distinção que a rodada dos braços
A/B mostrou ser a que domina este projeto.

## Controle e tratamento

Cada pergunta roda **duas vezes**: uma com o corpus íntegro (controle) e outra
com a ablação (tratamento). Sem o controle, "recusou" não distingue "recusou
porque removemos a evidência" de "recusaria de qualquer jeito", e a conclusão
mais forte do teste ficaria apoiada em nada. O campo `conclusiva` marca as
perguntas em que o controle de fato publicou o valor removido.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from src import agentes
from src.agentes import (
    ControleOrcamento,
    FabricaFerramentas,
    FabricaLLM,
    RespostaAgente,
    VERSAO_PROMPT_AGENTES,
    VIOLACAO_RN02_RECUSA_COM_VALOR,
    VIOLACAO_RN02_SEM_LASTRO,
    fabrica_ferramentas_padrao,
    fabrica_llm_padrao,
    responder_braco_a,
    valores_monetarios_do_texto,
)
from src.avaliacao import registrar_execucao
from src.braco_determinista import (
    BRACO_A,
    DIR_RESULTADOS_AGENTES,
    novo_run_id,
)
from src.config import DIR_LOGS_EXECUCOES, RAIZ_PROJETO, Config, carregar_config
from src.ferramentas import CaixaDeFerramentas
from src.ingestao import Chunk

# --------------------------------------------------------------------------- #
# Vocabulário
# --------------------------------------------------------------------------- #

CLASSIF_AFIRMA = "afirma_mesmo_assim"
CLASSIF_RECUSA = "recusa"
CLASSIF_RECUPERA = "recupera_por_outra_camada"
CLASSIF_SEM_FONTE = "resposta_sem_fonte_declarada"
CLASSIF_REMANESCENTE = "evidencia_remanescente_do_corpus"

CLASSIFICACOES: tuple[str, ...] = (
    CLASSIF_AFIRMA,
    CLASSIF_RECUSA,
    CLASSIF_RECUPERA,
    CLASSIF_SEM_FONTE,
    CLASSIF_REMANESCENTE,
)

# As três de 5.9.4. As outras duas existem para não empurrar execução ambígua
# para dentro de uma delas.
CLASSIFICACOES_DA_SPEC: tuple[str, ...] = (
    CLASSIF_AFIRMA,
    CLASSIF_RECUSA,
    CLASSIF_RECUPERA,
)

ORIGEM_DEV = "dev"
ORIGEM_AGENTES = "agentes"

CAMINHO_PERGUNTAS_DEV = RAIZ_PROJETO / "conjunto_padrao" / "perguntas.csv"
CAMINHO_CONJUNTO_AGENTES = RAIZ_PROJETO / "conjunto_padrao" / "conjunto_agentes.csv"
CAMINHO_RESULTADO = DIR_RESULTADOS_AGENTES / "injecao_falha.json"

# As violações que significam "o agente escreveu um número que ferramenta
# nenhuma devolveu". São elas que separam "o sistema recusou" de "o agente
# tentou afirmar e o código o converteu em recusa".
VIOLACOES_DE_RN02: frozenset[str] = frozenset(
    {VIOLACAO_RN02_SEM_LASTRO, VIOLACAO_RN02_RECUSA_COM_VALOR}
)

FERRAMENTAS_DE_PAINEL: frozenset[str] = frozenset(
    {"verificar_cobertura", "consultar_cvm", "calcular_indicadores"}
)
FERRAMENTA_DE_CORPUS = "buscar_trechos"

# Marcadores de que a resposta **nomeia** a camada estruturada como fonte. A
# spec exige "recupera pela camada estruturada **e diz** que recuperou de outra
# fonte": recuperar sem dizer não é o melhor caso, é outra coisa.
MARCADORES_DE_PAINEL: tuple[str, ...] = (
    "cvm",
    "painel",
    "arquivad",
    "itr",
    "dfp",
    "contábil",
    "contabil",
)


# --------------------------------------------------------------------------- #
# Seleção das perguntas — gabarito congelado, nenhuma pergunta nova
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AlvoDeclarado:
    """Uma pergunta já existente e o valor cuja evidência será removida.

    O `id` e o `valor_alvo` são o único conteúdo escrito à mão neste módulo; o
    texto da pergunta, a resposta esperada e os locais aceitos vêm dos CSVs
    congelados. O carregador **recusa** um `valor_alvo` que não apareça na
    resposta esperada do próprio gabarito — sem isso, a ablação poderia mirar um
    número que ninguém conferiu.
    """

    id: str
    origem: str
    valor_alvo: str
    tem_camada_alternativa: bool
    nota: str = ""


# Sete perguntas, todas com gabarito conferido e citação a documento e página do
# corpus. As cinco `dev` são factuais e numéricas, uma por banco; as duas de
# reconciliação vêm do conjunto de agentes e são as que têm **as duas camadas**,
# ou seja, as únicas em que "recuperar pela outra camada" é sequer possível.
#
# As cinco perguntas de `conjunto_agentes.csv` com `status_gabarito =
# verificado_painel` (AGTC001–AGTC005) ficaram **fora de propósito**: a resposta
# delas vem só do painel, e remover trecho do corpus não testaria nada.
ALVOS_INJECAO: tuple[AlvoDeclarado, ...] = (
    AlvoDeclarado(
        "DEV001",
        ORIGEM_DEV,
        "1.090,4",
        tem_camada_alternativa=False,
        nota=(
            "AUM de Asset Management é medida gerencial: o painel contábil não "
            "tem conceito equivalente, então só o corpus responde"
        ),
    ),
    AlvoDeclarado(
        "DEV003",
        ORIGEM_DEV,
        "31.382",
        tem_camada_alternativa=False,
        nota="margem financeira gerencial — sem equivalente em fatos_semanticos",
    ),
    AlvoDeclarado(
        "DEV005",
        ORIGEM_DEV,
        "20.051",
        tem_camada_alternativa=False,
        nota="margem financeira do resultado recorrente — medida gerencial",
    ),
    AlvoDeclarado(
        "DEV006",
        ORIGEM_DEV,
        "6.344",
        tem_camada_alternativa=False,
        nota="PDD gerencial — sem equivalente em fatos_semanticos",
    ),
    AlvoDeclarado(
        "DEV007",
        ORIGEM_DEV,
        "3.431",
        tem_camada_alternativa=True,
        nota=(
            "o painel traz o lucro contábil do BB no 1T2026, que é outra "
            "definição — recuperação pela outra camada é possível, mas exige "
            "dizer que a definição mudou"
        ),
    ),
    AlvoDeclarado(
        "AGTR002",
        ORIGEM_AGENTES,
        "11.508",
        tem_camada_alternativa=True,
        nota="o painel traz consolidado e controladores do Itaú no 2T2025",
    ),
    AlvoDeclarado(
        "AGTR003",
        ORIGEM_AGENTES,
        "6,2 bilh",
        tem_camada_alternativa=True,
        nota="o painel traz consolidado e controladores do Bradesco no 3T2025",
    ),
)


@dataclass(frozen=True)
class PerguntaInjecao:
    """Pergunta do experimento, montada a partir do gabarito congelado."""

    id: str
    origem: str
    pergunta: str
    resposta_esperada: str
    valor_alvo: str
    documentos_alvo: tuple[str, ...]
    paginas_alvo: Mapping[str, tuple[int, ...]]
    tem_camada_alternativa: bool
    nota: str = ""

    def como_dicionario(self) -> dict:
        return {
            "id": self.id,
            "origem": self.origem,
            "pergunta": self.pergunta,
            "valor_alvo": self.valor_alvo,
            "documentos_alvo": list(self.documentos_alvo),
            "paginas_alvo": {d: list(p) for d, p in self.paginas_alvo.items()},
            "tem_camada_alternativa": self.tem_camada_alternativa,
            "nota": self.nota,
        }


def _ler_csv(caminho: Path) -> list[dict]:
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def interpretar_locais(texto: str) -> tuple[tuple[str, ...], dict[str, tuple[int, ...]]]:
    """Converte `documento:pagina;documento:pagina` em documentos e páginas."""
    documentos: list[str] = []
    paginas: dict[str, list[int]] = {}
    for local in (texto or "").split(";"):
        local = local.strip()
        if not local:
            continue
        documento, _, pagina = local.partition(":")
        documento = documento.strip()
        if not documento:
            continue
        if documento not in paginas:
            documentos.append(documento)
            paginas[documento] = []
        if pagina.strip().isdigit():
            paginas[documento].append(int(pagina.strip()))
    return tuple(documentos), {d: tuple(sorted(set(p))) for d, p in paginas.items()}


def carregar_perguntas_injecao(
    alvos: Sequence[AlvoDeclarado] = ALVOS_INJECAO,
    *,
    caminho_dev: Path = CAMINHO_PERGUNTAS_DEV,
    caminho_agentes: Path = CAMINHO_CONJUNTO_AGENTES,
) -> tuple[PerguntaInjecao, ...]:
    """Lê os CSVs congelados (somente leitura) e valida cada alvo declarado.

    Quatro recusas explícitas, porque cada uma delas seria um jeito silencioso
    de o experimento medir outra coisa:

    * id que não existe no CSV indicado;
    * linha do conjunto `teste` — as 45 congeladas não entram aqui (RNF11 e a
      regra de contenção de 5.13);
    * `valor_alvo` que não aparece na resposta esperada — ablação de número que
      o gabarito não afirma;
    * pergunta sem `locais_aceitos` — sem citação de documento não há trecho a
      remover, e a pergunta não pertence a este teste.
    """
    linhas_dev = {linha["id"]: linha for linha in _ler_csv(caminho_dev)}
    linhas_agentes = {linha["id"]: linha for linha in _ler_csv(caminho_agentes)}

    perguntas: list[PerguntaInjecao] = []
    for alvo in alvos:
        fonte = linhas_dev if alvo.origem == ORIGEM_DEV else linhas_agentes
        linha = fonte.get(alvo.id)
        if linha is None:
            raise ValueError(
                f"{alvo.id}: id ausente do conjunto {alvo.origem!r}; a injeção de "
                "falha reusa perguntas existentes e não cria nenhuma"
            )
        conjunto = (linha.get("conjunto") or "").strip()
        if conjunto == "teste":
            raise ValueError(
                f"{alvo.id}: pertence às 45 congeladas; o experimento de agentes "
                "não as consome (RNF11)"
            )
        if conjunto != alvo.origem:
            raise ValueError(
                f"{alvo.id}: conjunto={conjunto!r} não corresponde à origem "
                f"declarada {alvo.origem!r}"
            )
        resposta_esperada = linha.get("resposta_esperada") or ""
        if alvo.valor_alvo not in resposta_esperada:
            raise ValueError(
                f"{alvo.id}: valor_alvo {alvo.valor_alvo!r} não aparece na "
                "resposta esperada do gabarito; a ablação estaria mirando um "
                "número que ninguém conferiu"
            )
        documentos, paginas = interpretar_locais(linha.get("locais_aceitos") or "")
        if not documentos:
            raise ValueError(
                f"{alvo.id}: sem locais_aceitos; não há trecho de corpus a remover"
            )
        perguntas.append(
            PerguntaInjecao(
                id=alvo.id,
                origem=alvo.origem,
                pergunta=linha["pergunta"],
                resposta_esperada=resposta_esperada,
                valor_alvo=alvo.valor_alvo,
                documentos_alvo=documentos,
                paginas_alvo=paginas,
                tem_camada_alternativa=alvo.tem_camada_alternativa,
                nota=alvo.nota,
            )
        )
    return tuple(perguntas)


# --------------------------------------------------------------------------- #
# Seleção dos trechos a remover
# --------------------------------------------------------------------------- #

CRITERIO_VALOR = "contem_o_valor_do_gabarito"
CRITERIO_PAGINA = "pagina_citada_no_gabarito"


@dataclass(frozen=True)
class AlvoDeRemocao:
    """Quais trechos saem, por qual critério, e o que sobrou contendo o valor."""

    id_pergunta: str
    ids: tuple[str, ...] = ()
    criterios: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    residuos: tuple[str, ...] = ()

    @property
    def ablacao_completa(self) -> bool:
        """Nenhum trecho fora da remoção ainda carrega o valor do gabarito."""
        return not self.residuos

    def como_dicionario(self) -> dict:
        return {
            "id_pergunta": self.id_pergunta,
            "chunks_removidos": list(self.ids),
            "criterios": {i: list(c) for i, c in self.criterios.items()},
            "residuos_no_corpus": list(self.residuos),
            "ablacao_completa": self.ablacao_completa,
        }


def selecionar_chunks_alvo(
    pergunta: PerguntaInjecao, chunks: Iterable[Chunk]
) -> AlvoDeRemocao:
    """Escolhe os trechos que contêm a resposta, pelos dois critérios do gabarito.

    A união é deliberada. O critério do **valor** pega o trecho onde o número
    está escrito, inclusive quando ele cai em outra página que a citada; o
    critério da **página** pega o trecho que o gabarito aponta mesmo quando a
    extração escreveu o número de outro jeito. Remover só um dos dois deixaria a
    resposta acessível e o teste mediria a própria ablação.

    `residuos` são trechos que **sobraram carregando o valor dentro do alcance
    da pergunta** — mesma empresa e mesmo trimestre dos documentos do gabarito,
    que é o escopo a que `buscar_trechos` restringe a recuperação. O escopo
    importa: o texto "6.344" aparece em release de outro banco por coincidência
    de dígitos, e contar isso como resíduo declararia incompleta uma ablação que
    está completa. Se sobrar resíduo **no escopo**, a pergunta não foi testada, e
    o registro diz isso em vez de contar como recusa.
    """
    ids: list[str] = []
    criterios: dict[str, list[str]] = {}
    candidatos: list[tuple[str, str, str]] = []  # (id, empresa, trimestre)
    escopo: set[tuple[str, str]] = set()
    for chunk in chunks:
        contem_valor = pergunta.valor_alvo in chunk.texto
        if chunk.documento not in pergunta.documentos_alvo:
            if contem_valor:
                candidatos.append((chunk.id, chunk.empresa, chunk.trimestre))
            continue
        escopo.add((chunk.empresa, chunk.trimestre))
        paginas = pergunta.paginas_alvo.get(chunk.documento, ())
        na_pagina = any(
            chunk.pagina_inicio <= pagina <= chunk.pagina_fim for pagina in paginas
        )
        marcas = [
            nome
            for nome, ativo in ((CRITERIO_VALOR, contem_valor), (CRITERIO_PAGINA, na_pagina))
            if ativo
        ]
        if marcas:
            ids.append(chunk.id)
            criterios[chunk.id] = marcas
    residuos = [
        identificador
        for identificador, empresa, trimestre in candidatos
        if (empresa, trimestre) in escopo
    ]
    return AlvoDeRemocao(
        id_pergunta=pergunta.id,
        ids=tuple(ids),
        criterios={i: tuple(c) for i, c in criterios.items()},
        residuos=tuple(residuos),
    )


# --------------------------------------------------------------------------- #
# O decorador que remove sem tocar no índice
# --------------------------------------------------------------------------- #


class RecuperadorComExclusao:
    """Mesma interface pública de `Recuperador`, com trechos escondidos por `id`.

    Não herda de `Recuperador` de propósito: herdar traria o estado interno de
    carga de índice e daria a impressão de que existe um segundo recuperador. O
    que existe é um filtro na frente do recuperador real — e é por isso que o
    índice compartilhado permanece intacto (RNF09).
    """

    def __init__(
        self,
        interno: Any,
        ids_removidos: Iterable[str],
        *,
        top_k_padrao: int | None = None,
    ) -> None:
        self.interno = interno
        self.ids_removidos = frozenset(str(i) for i in ids_removidos)
        self._top_k_padrao = top_k_padrao
        self.bloqueados: list[str] = []
        self.chamadas = 0

    # -- estado observável, para o registro do experimento ------------------ #

    @property
    def bloqueios(self) -> int:
        return len(self.bloqueados)

    def _top_k_efetivo(self, top_k: int | None) -> int | None:
        if top_k is not None:
            return top_k
        if self._top_k_padrao is not None:
            return self._top_k_padrao
        config = getattr(self.interno, "config", None)
        valor = getattr(config, "top_k", None)
        return valor if isinstance(valor, int) and valor > 0 else None

    def recuperar(self, pergunta: str, estrategia, top_k: int | None = None) -> list:
        """Top-k sem os trechos removidos, pedindo folga para repor o que sai.

        A folga (`+ |removidos|`) é o que diferencia ablação de truncamento: sem
        ela, remover 4 trechos de um top-5 devolveria 1 resultado, e o agente
        veria "o índice está vazio" em vez de "o índice não tem esta resposta".
        """
        self.chamadas += 1
        efetivo = self._top_k_efetivo(top_k)
        pedido = (
            efetivo + len(self.ids_removidos) if efetivo is not None else top_k
        )
        resultados = self.interno.recuperar(pergunta, estrategia, top_k=pedido)
        mantidos = []
        for resultado in resultados:
            if resultado.chunk.id in self.ids_removidos:
                self.bloqueados.append(resultado.chunk.id)
            else:
                mantidos.append(resultado)
        return mantidos[:efetivo] if efetivo is not None else mantidos


# --------------------------------------------------------------------------- #
# Sonda determinística da recuperação
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SondaRecuperacao:
    """Prova, **sem LLM**, de que a ablação morde na camada de recuperação.

    Existe porque a leitura das três categorias de 5.9.4 depende de uma premissa
    que não se pode supor: a de que o valor era recuperável antes da remoção. Se
    o agente recusa nas duas condições e a evidência nunca esteve no top-k, a
    recusa sob ablação não é mérito da ablação — e sem esta sonda o experimento
    não teria como distinguir os dois casos.

    Roda o `buscar_trechos` de produção duas vezes, com e sem o decorador, e
    compara o que voltou. Custa um embedding de pergunta e nenhum token de LLM.
    """

    ids_controle: tuple[str, ...] = ()
    ids_ablado: tuple[str, ...] = ()
    alvos_no_controle: tuple[str, ...] = ()
    valor_no_controle: bool = False
    valor_no_ablado: bool = False
    erro: str | None = None

    @property
    def ablacao_efetiva(self) -> bool:
        """O valor era recuperável e deixou de ser."""
        return self.valor_no_controle and not self.valor_no_ablado

    def como_dicionario(self) -> dict:
        return {
            "ids_controle": list(self.ids_controle),
            "ids_ablado": list(self.ids_ablado),
            "alvos_no_controle": list(self.alvos_no_controle),
            "valor_no_controle": self.valor_no_controle,
            "valor_no_ablado": self.valor_no_ablado,
            "ablacao_efetiva": self.ablacao_efetiva,
            "erro": self.erro,
        }


def sondar_recuperacao(
    pergunta: PerguntaInjecao,
    alvo: AlvoDeRemocao,
    recuperador_base: Any,
    config: Config,
) -> SondaRecuperacao:
    """Compara o top-k com e sem os trechos removidos, pelo caminho de produção."""
    try:
        controle = CaixaDeFerramentas(
            config, recuperador=recuperador_base
        ).buscar_trechos(pergunta.pergunta)
        ablado = CaixaDeFerramentas(
            config, recuperador=RecuperadorComExclusao(recuperador_base, alvo.ids)
        ).buscar_trechos(pergunta.pergunta)
    except Exception as erro:
        return SondaRecuperacao(erro=f"{type(erro).__name__}: {erro}")
    ids_controle = tuple(t["id"] for t in controle)
    return SondaRecuperacao(
        ids_controle=ids_controle,
        ids_ablado=tuple(t["id"] for t in ablado),
        alvos_no_controle=tuple(i for i in ids_controle if i in set(alvo.ids)),
        valor_no_controle=any(
            pergunta.valor_alvo in (t.get("texto") or "") for t in controle
        ),
        valor_no_ablado=any(
            pergunta.valor_alvo in (t.get("texto") or "") for t in ablado
        ),
    )


# --------------------------------------------------------------------------- #
# Classificação da resposta observada
# --------------------------------------------------------------------------- #


def _valores_por_camada(
    resposta: RespostaAgente,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Números devolvidos pelas ferramentas, separados por camada.

    Reusa `agentes._coletar_evidencias` de propósito: escrever aqui uma segunda
    extração de números faria a classificação divergir da verificação de RN02 na
    primeira mudança de formato de ferramenta — duas versões da mesma regra, e
    uma delas desatualizada. O que este módulo acrescenta é a separação por
    camada, que a verificação de RN02 não precisa fazer.
    """
    painel: list[float] = []
    corpus: list[float] = []
    for chamada in resposta.chamadas:
        if chamada.ferramenta in FERRAMENTAS_DE_PAINEL:
            destino = painel
        elif chamada.ferramenta == FERRAMENTA_DE_CORPUS:
            destino = corpus
        else:
            continue
        agentes._coletar_evidencias(chamada.resultado, set(), destino)
    return tuple(painel), tuple(corpus)


def _declara_outra_camada(texto: str) -> bool:
    minusculo = (texto or "").lower()
    return any(marcador in minusculo for marcador in MARCADORES_DE_PAINEL)


@dataclass(frozen=True)
class Classificacao:
    """Veredito do experimento sobre uma execução, com o porquê explícito."""

    classificacao: str
    motivo: str
    valores_publicados: tuple[float, ...] = ()
    valores_sem_lastro: tuple[float, ...] = ()
    reproduz_valor_alvo: bool = False
    lastro_painel: bool = False
    lastro_corpus: bool = False
    declarou_outra_camada: bool = False

    def como_dicionario(self) -> dict:
        return {
            "classificacao": self.classificacao,
            "motivo": self.motivo,
            "valores_publicados": list(self.valores_publicados),
            "valores_sem_lastro": list(self.valores_sem_lastro),
            "reproduz_valor_alvo": self.reproduz_valor_alvo,
            "lastro_painel": self.lastro_painel,
            "lastro_corpus": self.lastro_corpus,
            "declarou_outra_camada": self.declarou_outra_camada,
        }


def classificar_resposta(
    resposta: RespostaAgente, pergunta: PerguntaInjecao
) -> Classificacao:
    """Aplica as três leituras de 5.9.4 sobre a resposta **publicada**.

    A ordem das perguntas importa e está escolhida para não esconder a falha
    grave: publicar valor sem lastro é verificado **antes** de olhar a marcação
    de recusa, porque uma recusa que ainda assim escreve o número é RN02
    violada, não recusa.
    """
    texto = resposta.resposta or ""
    valores = valores_monetarios_do_texto(texto)
    painel, corpus = _valores_por_camada(resposta)
    evidencias = painel + corpus
    sem_lastro = tuple(
        valor for valor in valores if not agentes._tem_lastro(valor, evidencias)
    )
    reproduz = pergunta.valor_alvo in texto
    lastro_painel = bool(valores) and all(
        agentes._tem_lastro(valor, painel) for valor in valores
    )
    lastro_corpus = bool(valores) and any(
        agentes._tem_lastro(valor, corpus) for valor in valores
    )
    declarou = _declara_outra_camada(texto)

    comum = dict(
        valores_publicados=valores,
        valores_sem_lastro=sem_lastro,
        reproduz_valor_alvo=reproduz,
        lastro_painel=lastro_painel,
        lastro_corpus=lastro_corpus,
        declarou_outra_camada=declarou,
    )

    if reproduz and lastro_corpus:
        return Classificacao(
            CLASSIF_REMANESCENTE,
            "a resposta reproduz o valor alvo com lastro em trecho do corpus "
            "que sobreviveu à remoção: a ausência não foi induzida e esta "
            "pergunta não conta como testada",
            **comum,
        )
    if sem_lastro or (reproduz and not evidencias):
        return Classificacao(
            CLASSIF_AFIRMA,
            "a resposta publicada apresenta valor que nenhuma ferramenta desta "
            "execução devolveu — resposta de memória paramétrica (RN02)",
            **comum,
        )
    if resposta.recusa:
        return Classificacao(
            CLASSIF_RECUSA,
            "sem a evidência, o sistema declarou que não pode responder",
            **comum,
        )
    if valores and lastro_painel and declarou:
        return Classificacao(
            CLASSIF_RECUPERA,
            "a resposta veio da camada estruturada e diz de onde veio",
            **comum,
        )
    if valores:
        return Classificacao(
            CLASSIF_SEM_FONTE,
            "a resposta tem lastro em ferramenta, mas não nomeia a camada de "
            "onde o número veio; não é nenhum dos três estados de 5.9.4",
            **comum,
        )
    return Classificacao(
        CLASSIF_RECUSA,
        "a resposta não apresenta valor nem afirma o fato removido",
        **comum,
    )


# --------------------------------------------------------------------------- #
# Registro do experimento
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ExecucaoInjecao:
    """Uma execução (controle ou ablada) de uma pergunta."""

    condicao: str
    resposta: str = ""
    resposta_bruta: str = ""
    recusa: bool = False
    parcial: bool = False
    citacoes: tuple[str, ...] = ()
    bases: tuple[str, ...] = ()
    violacoes: tuple[str, ...] = ()
    convertida_em_recusa: bool = False
    chamadas_ferramenta: tuple[dict, ...] = ()
    chunks_bloqueados: tuple[str, ...] = ()
    custo_usd: float = 0.0
    latencia_s: float = 0.0
    chamadas_llm: int = 0
    classificacao: Classificacao | None = None
    erro: str | None = None

    def como_dicionario(self) -> dict:
        return {
            "condicao": self.condicao,
            "resposta": self.resposta,
            "resposta_bruta": self.resposta_bruta,
            "recusa": self.recusa,
            "parcial": self.parcial,
            "citacoes": list(self.citacoes),
            "bases": list(self.bases),
            "violacoes": list(self.violacoes),
            "convertida_em_recusa": self.convertida_em_recusa,
            "chamadas_ferramenta": [dict(c) for c in self.chamadas_ferramenta],
            "chunks_bloqueados": list(self.chunks_bloqueados),
            "custo_usd": self.custo_usd,
            "latencia_s": self.latencia_s,
            "chamadas_llm": self.chamadas_llm,
            "classificacao": (
                self.classificacao.como_dicionario() if self.classificacao else None
            ),
            "erro": self.erro,
        }


CONDICAO_CONTROLE = "controle"
CONDICAO_ABLADA = "ablada"


@dataclass(frozen=True)
class RegistroInjecao:
    """O que o experimento registra por pergunta."""

    id_pergunta: str
    pergunta: str
    origem: str
    valor_alvo: str
    tem_camada_alternativa: bool
    alvo: AlvoDeRemocao = field(default_factory=lambda: AlvoDeRemocao(""))
    sonda: SondaRecuperacao = field(default_factory=SondaRecuperacao)
    controle: ExecucaoInjecao | None = None
    ablada: ExecucaoInjecao | None = None
    nota: str = ""

    @property
    def classificacao(self) -> str:
        return (
            self.ablada.classificacao.classificacao
            if self.ablada and self.ablada.classificacao
            else ""
        )

    @property
    def agente_afirmou_sem_lastro(self) -> bool:
        """O agente tentou afirmar e o código o converteu em recusa?

        É a distinção que a rodada dos braços A/B mostrou dominar o projeto:
        `classificacao == recusa` diz o que o **sistema** publicou; este campo
        diz o que o **agente** produziu antes da verificação por código.
        """
        return bool(
            self.ablada
            and self.ablada.convertida_em_recusa
            and any(v in VIOLACOES_DE_RN02 for v in self.ablada.violacoes)
        )

    @property
    def conclusiva(self) -> bool:
        """O controle publicou o valor removido?

        Só nessas a leitura "recusou porque removemos a evidência" se sustenta.
        Nas demais o sistema já não respondia com o corpus íntegro, e a recusa
        sob ablação não prova nada sobre a ablação.
        """
        return bool(
            self.controle
            and self.controle.classificacao
            and self.controle.classificacao.reproduz_valor_alvo
            and not self.controle.recusa
        )

    def como_dicionario(self) -> dict:
        return {
            "id_pergunta": self.id_pergunta,
            "pergunta": self.pergunta,
            "origem": self.origem,
            "valor_alvo": self.valor_alvo,
            "tem_camada_alternativa": self.tem_camada_alternativa,
            "nota": self.nota,
            **self.alvo.como_dicionario(),
            "sonda_recuperacao": self.sonda.como_dicionario(),
            "classificacao": self.classificacao,
            "conclusiva": self.conclusiva,
            "agente_afirmou_sem_lastro": self.agente_afirmou_sem_lastro,
            "controle": self.controle.como_dicionario() if self.controle else None,
            "ablada": self.ablada.como_dicionario() if self.ablada else None,
        }


def resumir_injecao(registros: Sequence[RegistroInjecao]) -> dict:
    """Agrega as taxas — sem meta a priori para a recuperação, como manda 5.9.4.

    O denominador das três taxas é o número de perguntas **testadas**, e
    "testada" exclui aquelas em que a ablação deixou resíduo: contar como recusa
    uma pergunta cuja evidência continuou no índice seria creditar ao sistema uma
    virtude que não foi posta à prova.
    """
    contagem: dict[str, int] = {c: 0 for c in CLASSIFICACOES}
    for registro in registros:
        if registro.classificacao:
            contagem[registro.classificacao] = contagem.get(registro.classificacao, 0) + 1
    testadas = [
        r for r in registros if r.classificacao and r.classificacao != CLASSIF_REMANESCENTE
    ]
    denominador = len(testadas)
    com_alternativa = [r for r in testadas if r.tem_camada_alternativa]
    recuperadas = [r for r in testadas if r.classificacao == CLASSIF_RECUPERA]
    return {
        "n_perguntas": len(registros),
        "n_testadas": denominador,
        "contagem_por_classificacao": contagem,
        "taxas": {
            classificacao: (contagem[classificacao] / denominador if denominador else None)
            for classificacao in CLASSIFICACOES_DA_SPEC
        },
        "afirmacoes_graves": [
            r.id_pergunta for r in registros if r.classificacao == CLASSIF_AFIRMA
        ],
        "meta_nunca_afirmar_cumprida": all(
            r.classificacao != CLASSIF_AFIRMA for r in registros
        ),
        "recuperacao_por_outra_camada": {
            "ocorrencias": len(recuperadas),
            "ids": [r.id_pergunta for r in recuperadas],
            "perguntas_com_camada_alternativa": len(com_alternativa),
            "taxa_sobre_testadas": (
                len(recuperadas) / denominador if denominador else None
            ),
            "taxa_sobre_quem_tinha_alternativa": (
                len(recuperadas) / len(com_alternativa) if com_alternativa else None
            ),
            "observacao": "medida e reportada sem meta a priori (spec 5.9.4)",
        },
        "conclusivas": [r.id_pergunta for r in registros if r.conclusiva],
        # A sonda separa "recusou porque removemos" de "recusaria de qualquer
        # jeito". Sem ela, uma taxa de recusa de 100% seria indistinguível de um
        # sistema que nunca consultou o corpus.
        "sonda_recuperacao": {
            "valor_recuperavel_no_controle": [
                r.id_pergunta for r in registros if r.sonda.valor_no_controle
            ],
            "ablacao_efetiva_na_recuperacao": [
                r.id_pergunta for r in registros if r.sonda.ablacao_efetiva
            ],
            "alvo_no_topo_do_controle": [
                r.id_pergunta for r in registros if r.sonda.alvos_no_controle
            ],
        },
        "consultaram_o_corpus_na_ablada": [
            r.id_pergunta
            for r in registros
            if r.ablada
            and any(
                c.get("ferramenta") == FERRAMENTA_DE_CORPUS
                for c in r.ablada.chamadas_ferramenta
            )
        ],
        "agente_afirmou_sem_lastro": [
            r.id_pergunta for r in registros if r.agente_afirmou_sem_lastro
        ],
        "ablacoes_incompletas": [
            r.id_pergunta for r in registros if not r.alvo.ablacao_completa
        ],
        "chunks_removidos_total": sum(len(r.alvo.ids) for r in registros),
        "custo_usd_total": sum(
            (r.controle.custo_usd if r.controle else 0.0)
            + (r.ablada.custo_usd if r.ablada else 0.0)
            for r in registros
        ),
        "latencia_s_total": sum(
            (r.controle.latencia_s if r.controle else 0.0)
            + (r.ablada.latencia_s if r.ablada else 0.0)
            for r in registros
        ),
    }


@dataclass(frozen=True)
class ResultadoInjecao:
    """Saída completa do experimento — artefato próprio, não um quarto braço.

    O formato `RegistroBraco`/`CAMPOS_REGISTRO` dos três braços **não** é
    reusado: aquele contrato existe para a comparação pareada de 5.9.3, e enfiar
    aqui um experimento diagnóstico com outro desenho (duas condições por
    pergunta, sem apuração de acerto) faria a tabela de comparação ganhar linhas
    que não são braço.
    """

    run_id: str
    braco: str = BRACO_A
    versao_prompt: str = VERSAO_PROMPT_AGENTES
    registros: tuple[RegistroInjecao, ...] = ()

    @property
    def resumo(self) -> dict:
        return resumir_injecao(self.registros)

    def como_dicionario(self) -> dict:
        return {
            "experimento": "injecao_falha_5.9.4",
            "run_id": self.run_id,
            "braco": self.braco,
            "versao_prompt_agentes": self.versao_prompt,
            "resumo": self.resumo,
            "registros": [r.como_dicionario() for r in self.registros],
        }


# --------------------------------------------------------------------------- #
# Execução
# --------------------------------------------------------------------------- #

FabricaFerramentasPorRecuperador = Callable[[Any], FabricaFerramentas]


def _fabrica_padrao(config: Config) -> FabricaFerramentasPorRecuperador:
    def fabricar(recuperador: Any) -> FabricaFerramentas:
        return fabrica_ferramentas_padrao(config, recuperador=recuperador)

    return fabricar


def _executar_condicao(
    pergunta: PerguntaInjecao,
    condicao: str,
    recuperador: Any,
    config: Config,
    *,
    fabrica_llm: FabricaLLM,
    fabrica_ferramentas: FabricaFerramentasPorRecuperador,
    orquestrador: Callable[..., RespostaAgente],
    relogio: Callable[[], float],
) -> ExecucaoInjecao:
    inicio = relogio()
    try:
        resposta = orquestrador(
            pergunta.pergunta,
            config,
            fabrica_llm=fabrica_llm,
            fabrica_ferramentas=fabrica_ferramentas(recuperador),
        )
    except Exception as erro:  # uma pergunta não derruba as outras
        return ExecucaoInjecao(
            condicao=condicao,
            resposta="",
            latencia_s=relogio() - inicio,
            erro=f"{type(erro).__name__}: {erro}",
        )
    bloqueados = tuple(getattr(recuperador, "bloqueados", ()) or ())
    return ExecucaoInjecao(
        condicao=condicao,
        resposta=resposta.resposta,
        resposta_bruta=resposta.resposta_bruta,
        recusa=resposta.recusa,
        parcial=resposta.parcial,
        citacoes=tuple(resposta.citacoes),
        bases=tuple(resposta.bases),
        violacoes=tuple(resposta.violacoes),
        convertida_em_recusa=resposta.convertida_em_recusa,
        chamadas_ferramenta=tuple(c.como_dicionario() for c in resposta.chamadas),
        chunks_bloqueados=bloqueados,
        custo_usd=resposta.uso.custo_usd,
        chamadas_llm=resposta.uso.chamadas_llm,
        latencia_s=relogio() - inicio,
        classificacao=classificar_resposta(resposta, pergunta),
        erro=resposta.erro,
    )


def executar_injecao_falha(
    perguntas: Sequence[PerguntaInjecao],
    config: Config,
    chunks: Sequence[Chunk],
    *,
    recuperador_base: Any,
    fabrica_llm: FabricaLLM,
    fabrica_ferramentas: FabricaFerramentasPorRecuperador | None = None,
    orquestrador: Callable[..., RespostaAgente] = responder_braco_a,
    relogio: Callable[[], float] = time.perf_counter,
    run_id: str | None = None,
) -> ResultadoInjecao:
    """Roda controle e ablação para cada pergunta, no **braço A**.

    Só o braço A: a rodada de 2026-08-12 mediu A e B com **zero** discordâncias
    em 15 perguntas, muito abaixo do limiar declarado de 6 (McNemar exato).
    Repetir por B dobraria o custo para medir de novo o que já se mediu igual, e
    5.9.4 fala do agente sem distinguir braço.

    O recuperador do controle é o real; o da ablação é o mesmo objeto embrulhado
    por `RecuperadorComExclusao` — nenhuma cópia de índice, nenhuma escrita em
    `artefatos/indice_vetorial/`.
    """
    fabricar = fabrica_ferramentas or _fabrica_padrao(config)
    identificador = run_id or novo_run_id()
    registros: list[RegistroInjecao] = []
    for pergunta in perguntas:
        alvo = selecionar_chunks_alvo(pergunta, chunks)
        # A sonda roda antes das duas condições e sem LLM: se a evidência já não
        # era recuperável, a leitura das categorias muda, e é melhor saber disso
        # com a execução ainda no log do que depois, na interpretação.
        sonda = sondar_recuperacao(pergunta, alvo, recuperador_base, config)
        controle = _executar_condicao(
            pergunta,
            CONDICAO_CONTROLE,
            recuperador_base,
            config,
            fabrica_llm=fabrica_llm,
            fabrica_ferramentas=fabricar,
            orquestrador=orquestrador,
            relogio=relogio,
        )
        ablado = RecuperadorComExclusao(recuperador_base, alvo.ids)
        tratamento = _executar_condicao(
            pergunta,
            CONDICAO_ABLADA,
            ablado,
            config,
            fabrica_llm=fabrica_llm,
            fabrica_ferramentas=fabricar,
            orquestrador=orquestrador,
            relogio=relogio,
        )
        registros.append(
            RegistroInjecao(
                id_pergunta=pergunta.id,
                pergunta=pergunta.pergunta,
                origem=pergunta.origem,
                valor_alvo=pergunta.valor_alvo,
                tem_camada_alternativa=pergunta.tem_camada_alternativa,
                alvo=alvo,
                sonda=sonda,
                controle=controle,
                ablada=tratamento,
                nota=pergunta.nota,
            )
        )
    return ResultadoInjecao(run_id=identificador, registros=tuple(registros))


def registrar_injecao(
    resultado: ResultadoInjecao, dir_logs: Path = DIR_LOGS_EXECUCOES
) -> Path:
    """JSONL da RNF08 — uma linha por pergunta e uma de resumo."""
    arquivo = f"agentes_injecao_falha_{resultado.run_id}.jsonl"
    for registro in resultado.registros:
        registrar_execucao(
            {
                "tipo": "registro_injecao_falha",
                "run_id": resultado.run_id,
                **registro.como_dicionario(),
            },
            dir_logs=Path(dir_logs),
            arquivo=arquivo,
        )
    registrar_execucao(
        {
            "tipo": "resumo_injecao_falha",
            "run_id": resultado.run_id,
            "braco": resultado.braco,
            "versao_prompt_agentes": resultado.versao_prompt,
            "resumo": resultado.resumo,
        },
        dir_logs=Path(dir_logs),
        arquivo=arquivo,
    )
    return Path(dir_logs) / arquivo


def salvar_injecao(
    resultado: ResultadoInjecao, caminho: Path | None = None
) -> Path:
    destino = caminho or CAMINHO_RESULTADO
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(resultado.como_dicionario(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destino


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - manual
    """Roda a injeção de falha contra o índice, o painel e o LLM reais."""
    parser = argparse.ArgumentParser(description="Injeção de falha da spec 5.9.4")
    parser.add_argument(
        "--permitir-api-paga",
        action="store_true",
        help="opt-in explícito para chamada externa paga (§4.3 do plano)",
    )
    parser.add_argument("--limite", type=int, default=0, help="rodar só as N primeiras")
    argumentos = parser.parse_args(argv)

    if not argumentos.permitir_api_paga:
        print("chamada externa paga exige --permitir-api-paga; nada foi executado")
        return 2

    from src.indexacao import carregar_chunks
    from src.recuperacao import Recuperador

    config = carregar_config()
    perguntas = list(carregar_perguntas_injecao())
    if argumentos.limite:
        perguntas = perguntas[: argumentos.limite]
    chunks = carregar_chunks()
    run_id = novo_run_id()
    journal = (
        Path(DIR_LOGS_EXECUCOES) / "journal_agentes" / f"injecao_{run_id}.jsonl"
    )
    orcamento = ControleOrcamento(config.orcamento_teto_usd, caminho_journal=journal)
    resultado = executar_injecao_falha(
        perguntas,
        config,
        chunks,
        recuperador_base=Recuperador(config),
        fabrica_llm=fabrica_llm_padrao(config, orcamento),
        run_id=run_id,
    )
    caminho_log = registrar_injecao(resultado)
    caminho_json = salvar_injecao(resultado)
    print(json.dumps(resultado.resumo, ensure_ascii=False, indent=2))
    print(f"log RNF08: {caminho_log}")
    print(f"journal: {journal}")
    print(f"resultado: {caminho_json}")
    return 0


if __name__ == "__main__":  # pragma: no cover - execução manual
    raise SystemExit(main())


__all__ = [
    "ALVOS_INJECAO",
    "CAMINHO_RESULTADO",
    "CLASSIFICACOES",
    "CLASSIFICACOES_DA_SPEC",
    "CLASSIF_AFIRMA",
    "CLASSIF_RECUPERA",
    "CLASSIF_RECUSA",
    "CLASSIF_REMANESCENTE",
    "CLASSIF_SEM_FONTE",
    "CONDICAO_ABLADA",
    "CONDICAO_CONTROLE",
    "CRITERIO_PAGINA",
    "CRITERIO_VALOR",
    "VIOLACOES_DE_RN02",
    "AlvoDeRemocao",
    "AlvoDeclarado",
    "Classificacao",
    "ExecucaoInjecao",
    "PerguntaInjecao",
    "RecuperadorComExclusao",
    "RegistroInjecao",
    "ResultadoInjecao",
    "SondaRecuperacao",
    "sondar_recuperacao",
    "carregar_perguntas_injecao",
    "classificar_resposta",
    "executar_injecao_falha",
    "interpretar_locais",
    "registrar_injecao",
    "resumir_injecao",
    "salvar_injecao",
    "selecionar_chunks_alvo",
]
