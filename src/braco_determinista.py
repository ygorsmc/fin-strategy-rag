"""Braço C do experimento de 5.9.3 — o piso honesto, sem nenhuma chamada de LLM.

Três braços respondem às **mesmas** 15 perguntas de
`conjunto_padrao/conjunto_agentes.csv` (comparação pareada): **A** é um agente
único com todas as ferramentas, **B** é Investigador + Auditor (a hipótese sob
teste) e **C** — este módulo — é resolução de entidade + consulta de cobertura +
resposta por gabarito fixo, **sem modelo nenhum**.

O braço C é construído **antes** dos outros dois de propósito. Ele é o piso
contra o qual a hipótese é medida, e um piso ajustado depois de ver o resultado
do braço que ele deveria testar não mede nada. A spec é explícita: **se C empatar
com B, a conclusão escrita é que isso deveria ser código, e não agente** — e
publicar essa conclusão vale mais que exibir uma orquestração que ninguém mediu.

## O que este módulo faz — e o que ele deliberadamente não faz

Ele **não** reimplementa resolução de entidade (RN11), triagem de cobertura
(RN12), gabarito fixo nem guarda de SQL (RN04/RN09): tudo isso vive em
`src.cobertura` e `src.ferramentas`, já testado, e o braço C chama
`CaixaDeFerramentas.responder_deterministico`. Duas versões da mesma regra
levariam uma delas a ficar desatualizada em silêncio — e seria a versão medida.

O que ele acrescenta é o **arnês do experimento**:

1. rodar as 15 perguntas com orçamento de ferramenta **por pergunta** (5.9.5);
2. verificar RN01/RN02 **por código sobre a saída** — resposta com valor e sem
   citação vira **recusa registrada**, nunca resposta sem citação (5.9.5);
3. apurar acerto contra as colunas de vocabulário fechado do conjunto;
4. registrar por pergunta acerto, custo, latência e chamadas de ferramenta no
   **formato comum aos três braços** (`RegistroBraco`), em JSONL (RNF08).

## Honestidade da apuração: `pendente` não é acerto nem erro

Dez das 15 perguntas têm `status_gabarito` diferente de `verificado_painel` —
falta dupla leitura humana do release. Para elas o braço roda, responde e
registra tudo, mas `apuracao` é `pendente_conferencia_humana` e `acerto` é
`None`: nunca `True`, nunca `False`. Somar acerto sobre gabarito não conferido
contaminaria o experimento inteiro, e a taxa de acerto do resumo é calculada
**só sobre os apurados**, com o denominador declarado.

Os critérios de apuração são seis, todos mecânicos e válidos para qualquer
braço (nenhum depende de julgar texto livre):

| Critério | O que compara | Origem |
|---|---|---|
| `cobertura` | estado observado × `cobertura_esperada` | RN12 |
| `comportamento` | comportamento observado ∈ `comportamento_aceito` | conjunto |
| `motivo` | diagnóstico observado × `motivo_recusa_esperado` | conjunto |
| `base` | `base_esperada` ⊆ bases publicadas (e nenhum valor quando `n/a`) | conjunto |
| `ausencia_nomeada` | recusa `nenhuma` nomeia as duas camadas | RN12 + `pontos_chave` |
| `rn01_rn02` | nenhuma violação detectada por código | RN01/RN02 |

`rota_esperada` é registrada, mas **não** é critério: o braço C não tem rota de
reconciliação nem de acompanhamento de projeções, e reprovar por isso repetiria
15 vezes o que a limitação declarada já diz.

## Custo zero de LLM não é custo zero

O braço C gasta latência e leituras de painel. `custo_usd`, `chamadas_llm` e
`tokens_*` saem zerados **e contabilizados**, no mesmo campo em que A e B vão
gravar os seus, porque o quociente que decide o experimento (custo por resposta
alterada pelo Auditor) precisa dos três medidos do mesmo jeito.
"""

from __future__ import annotations

import csv
import json
import re
import time
import unicodedata
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from src.avaliacao import registrar_execucao
from src.cobertura import (
    MOTIVO_NA,
    EstadoCobertura,
    FatoEstruturado,
    IndiceCobertura,
    LeitorDeFatos,
    RespostaDeterministica,
    Triagem,
    carregar_indice_cobertura,
    formatar_reais,
)
from src.config import DIR_LOGS_EXECUCOES, RAIZ_PROJETO, Config
from src.ferramentas import (
    FERRAMENTAS_PROIBIDAS,
    CaixaDeFerramentas,
    LeitorPainelDuckDB,
)
from src.mapa_contas import CONCEITO_LUCRO_CONTROLADORES

CAMINHO_CONJUNTO_AGENTES = (
    RAIZ_PROJETO / "conjunto_padrao" / "conjunto_agentes.csv"
)
DIR_RESULTADOS_AGENTES = RAIZ_PROJETO / "artefatos" / "resultados_agentes"


# --------------------------------------------------------------------------- #
# Vocabulários congelados
# --------------------------------------------------------------------------- #

BRACO_A = "A"
BRACO_B = "B"
BRACO_C = "C"
BRACOS: tuple[str, ...] = (BRACO_A, BRACO_B, BRACO_C)

# Vocabulário de `comportamento_aceito` do conjunto. O braço C só produz os
# quatro primeiros: `divergencia_registrada` pressupõe confrontar duas camadas e
# `registro_sem_juizo` pressupõe ler a tabela de projeções do release — nenhum
# dos dois existe sem a camada documental, que o braço C não consulta.
COMPORTAMENTO_COMPLETA = "resposta_completa"
COMPORTAMENTO_PARCIAL = "resposta_parcial_marcada"
COMPORTAMENTO_RECUSA = "recusa"
COMPORTAMENTO_DESAMBIGUACAO = "pergunta_de_desambiguacao"
COMPORTAMENTO_DIVERGENCIA = "divergencia_registrada"
COMPORTAMENTO_SEM_JUIZO = "registro_sem_juizo"
COMPORTAMENTOS: frozenset[str] = frozenset(
    {
        COMPORTAMENTO_COMPLETA,
        COMPORTAMENTO_PARCIAL,
        COMPORTAMENTO_RECUSA,
        COMPORTAMENTO_DESAMBIGUACAO,
        COMPORTAMENTO_DIVERGENCIA,
        COMPORTAMENTO_SEM_JUIZO,
    }
)

# `ambigua` não é estado da RN12: é a resposta correta quando o nome resolve
# para mais de uma companhia (RN11). O conjunto o trata como quarto valor de
# `cobertura_esperada` exatamente para que um sistema que escolhe sozinho não
# pontue como acerto.
COBERTURA_AMBIGUA = "ambigua"
COBERTURAS_ESPERADAS: frozenset[str] = frozenset(
    {
        EstadoCobertura.AMBAS.value,
        EstadoCobertura.SO_PAINEL.value,
        EstadoCobertura.NENHUMA.value,
        COBERTURA_AMBIGUA,
    }
)

BASE_NA = "n/a"
BASE_GERENCIAL = "gerencial"
BASE_CONTABIL_CONSOLIDADO = "contabil_consolidado"
BASE_CONTABIL_CONTROLADORES = "contabil_controladores"
BASES: frozenset[str] = frozenset(
    {BASE_NA, BASE_GERENCIAL, BASE_CONTABIL_CONSOLIDADO, BASE_CONTABIL_CONTROLADORES}
)

SUBCONJUNTOS: frozenset[str] = frozenset({"cobertura", "reconciliacao", "projecoes"})

STATUS_VERIFICADO = "verificado_painel"
STATUS_PARCIAL_RELEASE = "parcial_pendente_release"
STATUS_PENDENTE_HUMANA = "pendente_conferencia_humana"
STATUS_GABARITO: frozenset[str] = frozenset(
    {STATUS_VERIFICADO, STATUS_PARCIAL_RELEASE, STATUS_PENDENTE_HUMANA}
)

# Vereditos do Auditor (5.9.1). Só o braço B preenche; A e C gravam `None`, e é
# essa diferença que o cruzamento de 5.9.3 usa para achar as discordâncias.
VEREDITO_CONFIRMA = "confirma"
VEREDITO_CONTESTA = "contesta"
VEREDITO_NAO_REPRODUZ = "nao_reproduz"
VEREDITOS: frozenset[str] = frozenset(
    {VEREDITO_CONFIRMA, VEREDITO_CONTESTA, VEREDITO_NAO_REPRODUZ}
)

APURACAO_ACERTO = "acerto"
APURACAO_ERRO = "erro"
APURACAO_PENDENTE = "pendente_conferencia_humana"

CRITERIO_COBERTURA = "cobertura"
CRITERIO_COMPORTAMENTO = "comportamento"
CRITERIO_MOTIVO = "motivo"
CRITERIO_BASE = "base"
CRITERIO_AUSENCIA_NOMEADA = "ausencia_nomeada"
CRITERIO_REGRAS = "rn01_rn02"
CRITERIOS: tuple[str, ...] = (
    CRITERIO_COBERTURA,
    CRITERIO_COMPORTAMENTO,
    CRITERIO_MOTIVO,
    CRITERIO_BASE,
    CRITERIO_AUSENCIA_NOMEADA,
    CRITERIO_REGRAS,
)

# Violações verificadas por código sobre a saída (5.9.5). Não são motivo de
# recusa do vocabulário do conjunto de propósito: uma recusa convertida por
# violação **nunca** pode casar com um motivo esperado, e por isso reprova.
VIOLACAO_RN01_SEM_CITACAO = "rn01_valor_sem_citacao"
VIOLACAO_RN01_CITACAO_INCOMPLETA = "rn01_citacao_nao_cobre_os_fatos"
VIOLACAO_RN02_SEM_LASTRO = "rn02_valor_sem_lastro"
VIOLACAO_RN02_RECUSA_COM_VALOR = "rn02_recusa_apresenta_valor"
MOTIVO_RECUSA_CONVERTIDA = "recusa_convertida_por_violacao"

# Nenhum conceito do painel é gerencial: a camada semântica traz o arquivado na
# CVM. `gerencial` só existe no release, que o braço C não lê — limitação
# declarada, não esquecimento.
BASE_POR_CONCEITO: Mapping[str, str] = {
    CONCEITO_LUCRO_CONTROLADORES: BASE_CONTABIL_CONTROLADORES,
}

_PADRAO_MONETARIO = re.compile(r"R\$\s*-?\d[\d.]*,\d{2}")
_TERMOS_PAINEL = ("painel", "cvm", "itr", "dfp")
_TERMOS_CORPUS = ("corpus", "release", "relatorio")


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


# --------------------------------------------------------------------------- #
# Conjunto de perguntas
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PerguntaAgentes:
    """Uma linha de `conjunto_agentes.csv`, tipada.

    Só as colunas que a execução e a apuração usam viram campo; o resto do
    gabarito (texto esperado, pontos-chave, fonte) fica em `extras` para ir ao
    log sem virar contrato de código.
    """

    id: str
    categoria: str
    subtipo_adversarial: str
    pergunta: str
    comportamento_aceito: tuple[str, ...]
    cobertura_esperada: str
    motivo_recusa_esperado: str
    base_esperada: tuple[str, ...]
    rota_esperada: str
    subconjunto: str
    status_gabarito: str
    extras: Mapping[str, str] = field(default_factory=dict)

    @property
    def gabarito_verificado(self) -> bool:
        """Só o gabarito conferido no painel autoriza declarar acerto ou erro."""
        return self.status_gabarito == STATUS_VERIFICADO

    @property
    def exige_valor(self) -> bool:
        return self.base_esperada != (BASE_NA,)


COLUNAS_OBRIGATORIAS: tuple[str, ...] = (
    "id",
    "conjunto",
    "categoria",
    "subtipo_adversarial",
    "pergunta",
    "comportamento_aceito",
    "cobertura_esperada",
    "motivo_recusa_esperado",
    "base_esperada",
    "rota_esperada",
    "subconjunto",
    "status_gabarito",
)


def carregar_conjunto_agentes(
    caminho: Path = CAMINHO_CONJUNTO_AGENTES,
) -> tuple[PerguntaAgentes, ...]:
    """Lê o conjunto próprio da camada de agentes e valida o vocabulário.

    Falha alto em vez de degradar: carregar `perguntas.csv` por engano aqui
    misturaria o benchmark E0–E3 com a camada de agentes, que é exatamente o
    que a RNF11 separa. A checagem de `conjunto == "agentes"` é o que impede o
    acidente.
    """
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    if not linhas:
        raise ValueError(f"conjunto de agentes vazio: {caminho}")
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in linhas[0]]
    if faltando:
        raise ValueError(
            f"{caminho} não tem as colunas obrigatórias {faltando}; este arquivo "
            "não é o conjunto da camada de agentes (spec 5.9.3)"
        )

    perguntas: list[PerguntaAgentes] = []
    for linha in linhas:
        identificador = (linha.get("id") or "").strip()
        if linha.get("conjunto") != "agentes":
            raise ValueError(
                f"{identificador}: coluna 'conjunto' é {linha.get('conjunto')!r} e "
                "deveria ser 'agentes' (RNF11 separa este conjunto das 45)"
            )
        comportamentos = tuple(
            token.strip() for token in linha["comportamento_aceito"].split("|")
        )
        bases = tuple(token.strip() for token in linha["base_esperada"].split("|"))
        for valor, permitidos, nome in (
            (linha["cobertura_esperada"], COBERTURAS_ESPERADAS, "cobertura_esperada"),
            (linha["subconjunto"], SUBCONJUNTOS, "subconjunto"),
            (linha["status_gabarito"], STATUS_GABARITO, "status_gabarito"),
        ):
            if valor not in permitidos:
                raise ValueError(
                    f"{identificador}: {nome}={valor!r} fora do vocabulário "
                    f"{sorted(permitidos)}"
                )
        for token in comportamentos:
            if token not in COMPORTAMENTOS:
                raise ValueError(
                    f"{identificador}: comportamento_aceito={token!r} fora do "
                    f"vocabulário {sorted(COMPORTAMENTOS)}"
                )
        for token in bases:
            if token not in BASES:
                raise ValueError(
                    f"{identificador}: base_esperada={token!r} fora do "
                    f"vocabulário {sorted(BASES)}"
                )
        conhecidas = set(COLUNAS_OBRIGATORIAS)
        perguntas.append(
            PerguntaAgentes(
                id=identificador,
                categoria=linha["categoria"],
                subtipo_adversarial=linha["subtipo_adversarial"],
                pergunta=linha["pergunta"],
                comportamento_aceito=comportamentos,
                cobertura_esperada=linha["cobertura_esperada"],
                motivo_recusa_esperado=linha["motivo_recusa_esperado"],
                base_esperada=bases,
                rota_esperada=linha["rota_esperada"],
                subconjunto=linha["subconjunto"],
                status_gabarito=linha["status_gabarito"],
                extras={
                    chave: valor
                    for chave, valor in linha.items()
                    if chave not in conhecidas
                },
            )
        )
    identificadores = [p.id for p in perguntas]
    if len(set(identificadores)) != len(identificadores):
        raise ValueError("há ids repetidos no conjunto de agentes")
    return tuple(perguntas)


# --------------------------------------------------------------------------- #
# Formato comum aos três braços
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Verificacao:
    """Resultado de um critério de apuração sobre uma resposta.

    `aplicavel=False` é diferente de `passou=False`: um critério que não vale
    para a pergunta não pode reprovar ninguém, e some do denominador.
    """

    criterio: str
    aplicavel: bool
    passou: bool
    esperado: str = ""
    observado: str = ""
    detalhe: str = ""

    def como_dicionario(self) -> dict:
        return {
            "criterio": self.criterio,
            "aplicavel": self.aplicavel,
            "passou": self.passou,
            "esperado": self.esperado,
            "observado": self.observado,
            "detalhe": self.detalhe,
        }


@dataclass(frozen=True)
class RegistroBraco:
    """Uma pergunta respondida por **um** braço — o formato que os três usam.

    Os campos de custo de modelo (`chamadas_llm`, `tokens_*`, `custo_usd`) e o
    `veredito_auditor` existem aqui mesmo no braço C, que os deixa zerados e
    nulo. É o que torna o JSONL comparável linha a linha: o bootstrap pareado de
    custo e latência de 5.9.3 precisa das três execuções no mesmo esquema, e um
    campo que só aparece em um braço vira exceção no cruzamento.
    """

    id_pergunta: str
    braco: str
    subconjunto: str
    categoria: str
    rota_esperada: str
    pergunta: str

    # Saída
    resposta: str = ""
    resposta_bruta: str = ""
    recusa: bool = False
    motivo_observado: str = MOTIVO_NA
    parcial: bool = False
    precisa_desambiguacao: bool = False
    comportamento_observado: str = ""
    cobertura_observada: str = ""
    entidades_resolvidas: tuple[str, ...] = ()
    bases_publicadas: tuple[str, ...] = ()
    citacoes: tuple[str, ...] = ()
    fatos_publicados: tuple[Mapping[str, Any], ...] = ()

    # Custo e contenção
    chamadas_ferramenta: tuple[Mapping[str, Any], ...] = ()
    leituras_painel: int = 0
    chamadas_llm: int = 0
    iteracoes: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    latencia_s: float = 0.0
    # Parcelas de diagnóstico do provedor. Zero = não reportado por ele, não
    # "não houve": o Gemini, pela compatibilidade OpenAI, não expõe o split de
    # cache, e só a DeepSeek devolve o raciocínio em campo próprio.
    tokens_raciocinio: int = 0
    tokens_entrada_cache_hit: int = 0
    # Raciocínio interno por chamada, para comparar COMO cada modelo reage ao
    # prompt. Já vem redigido de PII do adaptador (RN06) e nunca é reinjetado
    # em prompt — em particular não chega ao Auditor (`conferir_isolamento`).
    raciocinios: tuple[str, ...] = ()

    # Isolamento de contexto (só o braço B preenche)
    veredito_auditor: str | None = None

    # Regras verificadas por código
    violacoes: tuple[str, ...] = ()
    convertida_em_recusa: bool = False

    # Apuração
    status_gabarito: str = STATUS_PENDENTE_HUMANA
    apuracao: str = APURACAO_PENDENTE
    acerto: bool | None = None
    motivo_apuracao: str = ""
    verificacoes: tuple[Verificacao, ...] = ()

    erro_execucao: str | None = None

    def __post_init__(self) -> None:
        if self.braco not in BRACOS:
            raise ValueError(f"braço desconhecido: {self.braco!r}; use {BRACOS}")
        if self.veredito_auditor is not None and self.veredito_auditor not in VEREDITOS:
            raise ValueError(
                f"veredito do Auditor desconhecido: {self.veredito_auditor!r}"
            )
        if self.apuracao == APURACAO_PENDENTE and self.acerto is not None:
            raise ValueError(
                "apuração pendente não pode carregar acerto: gabarito não "
                "conferido não vira nem acerto nem erro"
            )
        if self.apuracao != APURACAO_PENDENTE and self.acerto is None:
            raise ValueError("apuração concluída exige acerto booleano")
        proibidas = {
            chamada.get("ferramenta") for chamada in self.chamadas_ferramenta
        } & set(FERRAMENTAS_PROIBIDAS)
        if proibidas:
            raise ValueError(
                f"ferramenta proibida chamada (RN07): {sorted(proibidas)}"
            )

    @property
    def total_chamadas_ferramenta(self) -> int:
        return len(self.chamadas_ferramenta)

    def como_dicionario(self) -> dict:
        return {
            "id_pergunta": self.id_pergunta,
            "braco": self.braco,
            "subconjunto": self.subconjunto,
            "categoria": self.categoria,
            "rota_esperada": self.rota_esperada,
            "pergunta": self.pergunta,
            "resposta": self.resposta,
            "resposta_bruta": self.resposta_bruta,
            "recusa": self.recusa,
            "motivo_observado": self.motivo_observado,
            "parcial": self.parcial,
            "precisa_desambiguacao": self.precisa_desambiguacao,
            "comportamento_observado": self.comportamento_observado,
            "cobertura_observada": self.cobertura_observada,
            "entidades_resolvidas": list(self.entidades_resolvidas),
            "bases_publicadas": list(self.bases_publicadas),
            "citacoes": list(self.citacoes),
            "fatos_publicados": [dict(f) for f in self.fatos_publicados],
            "chamadas_ferramenta": [dict(c) for c in self.chamadas_ferramenta],
            "total_chamadas_ferramenta": self.total_chamadas_ferramenta,
            "leituras_painel": self.leituras_painel,
            "chamadas_llm": self.chamadas_llm,
            "iteracoes": self.iteracoes,
            "tokens_entrada": self.tokens_entrada,
            "tokens_saida": self.tokens_saida,
            "custo_usd": self.custo_usd,
            "latencia_s": self.latencia_s,
            "tokens_raciocinio": self.tokens_raciocinio,
            "tokens_entrada_cache_hit": self.tokens_entrada_cache_hit,
            "raciocinios": list(self.raciocinios),
            "veredito_auditor": self.veredito_auditor,
            "violacoes": list(self.violacoes),
            "convertida_em_recusa": self.convertida_em_recusa,
            "status_gabarito": self.status_gabarito,
            "apuracao": self.apuracao,
            "acerto": self.acerto,
            "motivo_apuracao": self.motivo_apuracao,
            "verificacoes": [v.como_dicionario() for v in self.verificacoes],
            "erro_execucao": self.erro_execucao,
        }


CAMPOS_REGISTRO: tuple[str, ...] = (
    "id_pergunta",
    "braco",
    "subconjunto",
    "categoria",
    "rota_esperada",
    "pergunta",
    "resposta",
    "resposta_bruta",
    "recusa",
    "motivo_observado",
    "parcial",
    "precisa_desambiguacao",
    "comportamento_observado",
    "cobertura_observada",
    "entidades_resolvidas",
    "bases_publicadas",
    "citacoes",
    "fatos_publicados",
    "chamadas_ferramenta",
    "total_chamadas_ferramenta",
    "leituras_painel",
    "chamadas_llm",
    "iteracoes",
    "tokens_entrada",
    "tokens_saida",
    "custo_usd",
    "latencia_s",
    "tokens_raciocinio",
    "tokens_entrada_cache_hit",
    "raciocinios",
    "veredito_auditor",
    "violacoes",
    "convertida_em_recusa",
    "status_gabarito",
    "apuracao",
    "acerto",
    "motivo_apuracao",
    "verificacoes",
    "erro_execucao",
)


@dataclass(frozen=True)
class ResultadoBraco:
    """Execução completa de um braço sobre o conjunto."""

    braco: str
    run_id: str
    registros: tuple[RegistroBraco, ...]
    preparacao_s: float = 0.0

    @property
    def resumo(self) -> dict:
        return resumir(self.registros)

    def como_dicionario(self) -> dict:
        return {
            "braco": self.braco,
            "run_id": self.run_id,
            "preparacao_s": self.preparacao_s,
            "resumo": self.resumo,
            "registros": [r.como_dicionario() for r in self.registros],
        }


def resumir(registros: Sequence[RegistroBraco]) -> dict:
    """Agrega um braço sem nunca transformar pendência em acerto.

    `taxa_acerto` tem o denominador declarado (`apurados`) e é `None` quando não
    há nenhum gabarito conferido — média sobre zero apurado seria número
    inventado. As pendências aparecem em campo próprio para que a leitura do
    resumo não confunda "não errou" com "acertou".
    """
    total = len(registros)
    apurados = [r for r in registros if r.apuracao != APURACAO_PENDENTE]
    acertos = sum(1 for r in apurados if r.acerto)
    pendentes = total - len(apurados)
    criterios_falhos: Counter[str] = Counter()
    for registro in registros:
        for verificacao in registro.verificacoes:
            if verificacao.aplicavel and not verificacao.passou:
                criterios_falhos[verificacao.criterio] += 1
    latencias = [r.latencia_s for r in registros]
    return {
        "n": total,
        "por_subconjunto": dict(
            sorted(Counter(r.subconjunto for r in registros).items())
        ),
        "apurados": len(apurados),
        "acertos": acertos,
        "erros": len(apurados) - acertos,
        "pendentes": pendentes,
        "base_da_taxa": "apurados",
        "taxa_acerto": (acertos / len(apurados)) if apurados else None,
        "criterios_falhos": dict(sorted(criterios_falhos.items())),
        "custo_usd_total": sum(r.custo_usd for r in registros),
        "chamadas_llm_total": sum(r.chamadas_llm for r in registros),
        "tokens_total": sum(r.tokens_entrada + r.tokens_saida for r in registros),
        "latencia_s_total": sum(latencias),
        "latencia_s_media": (sum(latencias) / total) if total else None,
        "latencia_s_max": max(latencias) if latencias else None,
        "chamadas_ferramenta_total": sum(
            r.total_chamadas_ferramenta for r in registros
        ),
        "leituras_painel_total": sum(r.leituras_painel for r in registros),
        "violacoes_total": sum(len(r.violacoes) for r in registros),
        "convertidas_em_recusa": sum(1 for r in registros if r.convertida_em_recusa),
        "erros_execucao": sum(1 for r in registros if r.erro_execucao),
        "vereditos_auditor": dict(
            sorted(
                Counter(
                    r.veredito_auditor
                    for r in registros
                    if r.veredito_auditor is not None
                ).items()
            )
        ),
        "recusas": sum(1 for r in registros if r.recusa),
        "desambiguacoes": sum(1 for r in registros if r.precisa_desambiguacao),
    }


# --------------------------------------------------------------------------- #
# Leitura da saída determinística
# --------------------------------------------------------------------------- #


def comportamento_de(resposta: RespostaDeterministica) -> str:
    """Traduz a saída para o vocabulário de `comportamento_aceito`.

    A ordem importa: desambiguação antes de recusa porque perguntar qual
    companhia **não** é recusar (RN11), e recusa antes de parcial porque uma
    recusa é completa no que promete.
    """
    if resposta.precisa_desambiguacao:
        return COMPORTAMENTO_DESAMBIGUACAO
    if resposta.recusa:
        return COMPORTAMENTO_RECUSA
    if resposta.parcial:
        return COMPORTAMENTO_PARCIAL
    return COMPORTAMENTO_COMPLETA


def cobertura_de(resposta: RespostaDeterministica) -> str:
    """Estado de cobertura observado, no vocabulário de `cobertura_esperada`.

    Qualquer entidade ambígua domina: a resposta publicada é a pergunta de
    desambiguação e nada mais, então dizer que o estado foi `ambas` descreveria
    uma resposta que não foi dada. Sem entidade nenhuma resolvida o estado é
    `nenhuma` — mas o texto pode não nomear a ausência, e é o critério
    `ausencia_nomeada` que separa os dois casos.
    """
    if resposta.precisa_desambiguacao:
        return COBERTURA_AMBIGUA
    estados = sorted(
        {t.cobertura.estado.value for t in resposta.triagens if t.cobertura}
    )
    if not estados:
        return EstadoCobertura.NENHUMA.value
    if len(estados) == 1:
        return estados[0]
    return "|".join(estados)


def motivo_de(resposta: RespostaDeterministica) -> str:
    """Diagnóstico observado, para comparar com `motivo_recusa_esperado`.

    Não é só o motivo da recusa: uma resposta `so_painel` **não recusa** e ainda
    assim diagnostica `fora_do_corpus`, e é esse diagnóstico que o conjunto
    cobra na coluna. Ler apenas `resposta.motivo_recusa` reprovaria toda
    pergunta do par de contraste que responde em vez de recusar.
    """
    if resposta.recusa:
        return resposta.motivo_recusa
    motivos = sorted(
        {
            t.cobertura.motivo
            for t in resposta.triagens
            if t.cobertura and t.cobertura.motivo != MOTIVO_NA
        }
    )
    if not motivos:
        return MOTIVO_NA
    return "|".join(motivos)


def base_do_conceito(conceito: str) -> str:
    """Base contábil de um conceito do painel.

    Tudo que sai da camada semântica é arquivado na CVM: a única distinção que a
    coluna `base_esperada` faz dentro dela é consolidado × controladores.
    """
    return BASE_POR_CONCEITO.get(conceito, BASE_CONTABIL_CONSOLIDADO)


def bases_de(fatos: Iterable[FatoEstruturado]) -> tuple[str, ...]:
    return tuple(sorted({base_do_conceito(fato.conceito) for fato in fatos}))


def entidades_de(triagens: Iterable[Triagem]) -> tuple[str, ...]:
    codigos = {
        t.cobertura.companhia.cd_cvm
        for t in triagens
        if t.cobertura and t.cobertura.companhia
    }
    return tuple(sorted(codigos))


def valores_monetarios(texto: str) -> tuple[str, ...]:
    """Valores em reais citados no texto, normalizados para comparação."""
    return tuple(
        re.sub(r"\s+", " ", achado).strip()
        for achado in _PADRAO_MONETARIO.findall(texto or "")
    )


def nomeia_as_duas_camadas(texto: str) -> bool:
    """A recusa nomeia o tipo de ausência nas duas camadas (RN12)?

    Operacionaliza o `pontos_chave` das perguntas `nenhuma` ("nomear a ausência
    nas duas camadas"). É a diferença entre a recusa do Nubank e um "não sei"
    genérico — e é ela que impede o par de contraste de virar duas recusas
    iguais.
    """
    normalizado = _sem_acento(texto)
    tem_painel = any(termo in normalizado for termo in _TERMOS_PAINEL)
    tem_corpus = any(termo in normalizado for termo in _TERMOS_CORPUS)
    return tem_painel and tem_corpus


# --------------------------------------------------------------------------- #
# RN01 e RN02 verificadas por código sobre a saída (5.9.5)
# --------------------------------------------------------------------------- #


def verificar_regras(resposta: RespostaDeterministica) -> tuple[str, ...]:
    """Violações de RN01/RN02 encontradas na saída — sem julgar texto livre.

    Quatro checagens, todas mecânicas:

    1. valor publicado sem nenhuma citação (RN01);
    2. citações que não cobrem os fatos publicados (RN01);
    3. valor no texto que não corresponde a nenhum fato lido do painel — número
       sem lastro é a definição operacional de alucinação aqui (RN02);
    4. recusa que ainda assim apresenta valor (RN02).

    O braço C não tem modelo para "esquecer" de citar, e é justamente por isso
    que a verificação vale: ela roda igual nos três braços, e no braço C mede o
    piso — se falhar aqui, falhou por defeito de código, não por alucinação.
    """
    violacoes: list[str] = []
    valores_texto = valores_monetarios(resposta.resposta)
    valores_fatos = {formatar_reais(f.valor_reais) for f in resposta.fatos}

    if valores_texto and not resposta.citacoes:
        violacoes.append(VIOLACAO_RN01_SEM_CITACAO)
    if len(resposta.citacoes) != len(resposta.fatos):
        violacoes.append(VIOLACAO_RN01_CITACAO_INCOMPLETA)
    if any(valor not in valores_fatos for valor in valores_texto):
        violacoes.append(VIOLACAO_RN02_SEM_LASTRO)
    if resposta.recusa and (resposta.fatos or valores_texto):
        violacoes.append(VIOLACAO_RN02_RECUSA_COM_VALOR)
    return tuple(violacoes)


def converter_em_recusa(
    resposta: RespostaDeterministica, violacoes: Sequence[str]
) -> RespostaDeterministica:
    """Transforma saída que violou RN01/RN02 em **recusa registrada** (5.9.5).

    A resposta original não é apagada: quem executa precisa dela para depurar, e
    o registro guarda as duas. O que não pode acontecer é a resposta sem citação
    chegar ao usuário como resposta.
    """
    return RespostaDeterministica(
        pergunta=resposta.pergunta,
        resposta=(
            "Recusa registrada: a resposta foi descartada por violar as regras "
            f"verificadas em código sobre a saída ({', '.join(violacoes)}). "
            "Nenhum valor é apresentado sem citação da fonte que o produziu "
            "(RN01/RN02)."
        ),
        recusa=True,
        motivo_recusa=MOTIVO_RECUSA_CONVERTIDA,
        parcial=True,
        precisa_desambiguacao=resposta.precisa_desambiguacao,
        triagens=resposta.triagens,
        fatos=(),
        braco=resposta.braco,
    )


# --------------------------------------------------------------------------- #
# Apuração
# --------------------------------------------------------------------------- #


def apurar(
    pergunta: PerguntaAgentes,
    *,
    cobertura_observada: str,
    comportamento_observado: str,
    motivo_observado: str,
    bases_publicadas: Sequence[str],
    tem_valor_publicado: bool,
    resposta_texto: str,
    violacoes: Sequence[str],
) -> tuple[str, bool | None, str, tuple[Verificacao, ...]]:
    """Aplica os seis critérios e devolve (apuração, acerto, motivo, detalhes).

    **Regra dura:** gabarito não conferido no painel nunca vira acerto nem erro.
    As verificações continuam sendo calculadas e registradas — a dupla leitura
    humana vai precisar delas —, mas o veredito é `pendente_conferencia_humana`
    e `acerto` é `None`, que não soma em média nenhuma.
    """
    verificacoes: list[Verificacao] = []

    verificacoes.append(
        Verificacao(
            criterio=CRITERIO_COBERTURA,
            aplicavel=True,
            passou=cobertura_observada == pergunta.cobertura_esperada,
            esperado=pergunta.cobertura_esperada,
            observado=cobertura_observada,
        )
    )
    verificacoes.append(
        Verificacao(
            criterio=CRITERIO_COMPORTAMENTO,
            aplicavel=True,
            passou=comportamento_observado in pergunta.comportamento_aceito,
            esperado="|".join(pergunta.comportamento_aceito),
            observado=comportamento_observado,
        )
    )
    verificacoes.append(
        Verificacao(
            criterio=CRITERIO_MOTIVO,
            aplicavel=True,
            passou=motivo_observado == pergunta.motivo_recusa_esperado,
            esperado=pergunta.motivo_recusa_esperado,
            observado=motivo_observado,
        )
    )

    if pergunta.exige_valor:
        faltando = sorted(set(pergunta.base_esperada) - set(bases_publicadas))
        verificacoes.append(
            Verificacao(
                criterio=CRITERIO_BASE,
                aplicavel=True,
                passou=not faltando,
                esperado="|".join(pergunta.base_esperada),
                observado="|".join(bases_publicadas) or "nenhuma",
                detalhe=f"bases não apresentadas: {faltando}" if faltando else "",
            )
        )
    else:
        verificacoes.append(
            Verificacao(
                criterio=CRITERIO_BASE,
                aplicavel=True,
                passou=not tem_valor_publicado and not bases_publicadas,
                esperado="nenhum valor (base_esperada=n/a)",
                observado="|".join(bases_publicadas) or "nenhum valor",
                detalhe=(
                    "valor apresentado onde o gabarito exige que nenhum seja"
                    if tem_valor_publicado
                    else ""
                ),
            )
        )

    exige_ausencia_nomeada = (
        pergunta.cobertura_esperada == EstadoCobertura.NENHUMA.value
    )
    verificacoes.append(
        Verificacao(
            criterio=CRITERIO_AUSENCIA_NOMEADA,
            aplicavel=exige_ausencia_nomeada,
            passou=(
                nomeia_as_duas_camadas(resposta_texto)
                if exige_ausencia_nomeada
                else True
            ),
            esperado="recusa nomeia painel e corpus",
            observado=(
                "nomeia" if nomeia_as_duas_camadas(resposta_texto) else "não nomeia"
            ),
        )
    )
    verificacoes.append(
        Verificacao(
            criterio=CRITERIO_REGRAS,
            aplicavel=True,
            passou=not violacoes,
            esperado="sem violação de RN01/RN02",
            observado="|".join(violacoes) or "sem violação",
        )
    )

    reprovados = [
        v.criterio for v in verificacoes if v.aplicavel and not v.passou
    ]
    if not pergunta.gabarito_verificado:
        return (
            APURACAO_PENDENTE,
            None,
            (
                f"gabarito {pergunta.status_gabarito}: acerto não apurado até a "
                "dupla leitura humana do release. Critérios que já divergem: "
                f"{reprovados or 'nenhum'}"
            ),
            tuple(verificacoes),
        )
    if reprovados:
        return (
            APURACAO_ERRO,
            False,
            f"critérios reprovados: {reprovados}",
            tuple(verificacoes),
        )
    return (
        APURACAO_ACERTO,
        True,
        "todos os critérios aplicáveis passaram",
        tuple(verificacoes),
    )


# --------------------------------------------------------------------------- #
# Execução
# --------------------------------------------------------------------------- #


class LeitorContado(LeitorDeFatos):
    """Envelope que conta leituras do painel sem alterar o que é lido.

    A `CaixaDeFerramentas` conta chamadas de ferramenta, não leituras do painel
    feitas dentro de uma delas. Sem esta contagem, o braço C apareceria com "uma
    chamada por pergunta" e o custo real de I/O ficaria invisível na comparação
    com A e B.
    """

    def __init__(self, base: LeitorDeFatos) -> None:
        self.base = base
        self.leituras = 0

    def ler(self, cd_cvm: str, conceito: str, trimestre: str):
        self.leituras += 1
        return self.base.ler(cd_cvm, conceito, trimestre)


def novo_run_id() -> str:
    """Identificador de execução no formato já usado pelos logs RNF08."""
    return (
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:10]}"
    )


def executar_braco_c(
    perguntas: Sequence[PerguntaAgentes],
    config: Config,
    *,
    indice: IndiceCobertura | None = None,
    leitor: LeitorDeFatos | None = None,
    caminho_painel: Path | None = None,
    fabrica_caixa: Callable[[], Any] | None = None,
    relogio: Callable[[], float] = time.perf_counter,
    run_id: str | None = None,
) -> ResultadoBraco:
    """Roda o braço C sobre o conjunto e devolve um registro por pergunta.

    Duas decisões de medição, ambas necessárias para a comparação pareada:

    * **Uma caixa de ferramentas por pergunta.** O teto de 5.9.5 é por consulta;
      reaproveitar a instância faria a nona pergunta herdar o orçamento gasto
      pelas oito anteriores e estourar sem motivo.
    * **Um índice de cobertura para a execução inteira.** Carregá-lo dentro do
      relógio somaria o custo do painel à latência de cada pergunta, e é custo de
      partida, não de resposta. Ele é medido à parte, em `preparacao_s`.

    Nenhuma pergunta derruba a execução: exceção vira registro com
    `erro_execucao` e recusa, porque perder 14 medições por causa de uma é pior
    que registrar a falha.

    `fabrica_caixa` existe para os testes injetarem um duplo; quando ela é
    passada, `leituras_painel` fica em zero — o envelope que conta as leituras
    pertence à fábrica padrão, e inventar uma contagem para uma caixa
    desconhecida seria número sem medição.
    """
    inicio_preparacao = relogio()
    if indice is None:
        indice = carregar_indice_cobertura(config, caminho_painel)
    contado: LeitorContado | None = None
    fabrica = fabrica_caixa
    if fabrica is None:
        base = leitor if leitor is not None else LeitorPainelDuckDB(
            config, caminho_painel
        )
        contado = LeitorContado(base)
        indice_fixo = indice

        def fabrica() -> CaixaDeFerramentas:  # noqa: D401 - fábrica local
            return CaixaDeFerramentas(
                config,
                indice_cobertura=indice_fixo,
                leitor=contado,
                caminho_painel=caminho_painel,
            )

    preparacao_s = relogio() - inicio_preparacao

    registros: list[RegistroBraco] = []
    for pergunta in perguntas:
        caixa = fabrica()
        antes = contado.leituras if contado is not None else 0
        inicio = relogio()
        erro_execucao: str | None = None
        resposta: RespostaDeterministica | None = None
        try:
            resposta = caixa.responder_deterministico(pergunta.pergunta)
        except Exception as erro:  # contenção: a execução continua
            erro_execucao = f"{type(erro).__name__}: {erro}"
        latencia = relogio() - inicio
        leituras = (contado.leituras - antes) if contado is not None else 0
        chamadas = tuple(
            chamada.como_dicionario() for chamada in getattr(caixa, "registro", ())
        )

        if resposta is None:
            resposta = RespostaDeterministica(
                pergunta=pergunta.pergunta,
                resposta=(
                    "Recusa registrada: a execução determinística falhou "
                    f"({erro_execucao}). Nenhuma evidência foi reunida."
                ),
                recusa=True,
                motivo_recusa=MOTIVO_RECUSA_CONVERTIDA,
                parcial=True,
            )

        violacoes = verificar_regras(resposta)
        bruta = ""
        if violacoes:
            bruta = resposta.resposta
            resposta = converter_em_recusa(resposta, violacoes)

        bases = bases_de(resposta.fatos)
        comportamento = comportamento_de(resposta)
        cobertura = cobertura_de(resposta)
        motivo = motivo_de(resposta)
        apuracao, acerto, motivo_apuracao, verificacoes = apurar(
            pergunta,
            cobertura_observada=cobertura,
            comportamento_observado=comportamento,
            motivo_observado=motivo,
            bases_publicadas=bases,
            tem_valor_publicado=bool(valores_monetarios(resposta.resposta)),
            resposta_texto=resposta.resposta,
            violacoes=violacoes,
        )

        registros.append(
            RegistroBraco(
                id_pergunta=pergunta.id,
                braco=BRACO_C,
                subconjunto=pergunta.subconjunto,
                categoria=pergunta.categoria,
                rota_esperada=pergunta.rota_esperada,
                pergunta=pergunta.pergunta,
                resposta=resposta.resposta,
                resposta_bruta=bruta,
                recusa=resposta.recusa,
                motivo_observado=motivo,
                parcial=resposta.parcial,
                precisa_desambiguacao=resposta.precisa_desambiguacao,
                comportamento_observado=comportamento,
                cobertura_observada=cobertura,
                entidades_resolvidas=entidades_de(resposta.triagens),
                bases_publicadas=bases,
                citacoes=resposta.citacoes,
                fatos_publicados=tuple(
                    {
                        "cd_cvm": fato.cd_cvm,
                        "denom_social": fato.denom_social,
                        "trimestre": fato.trimestre,
                        "conceito": fato.conceito,
                        "valor_reais": fato.valor_reais,
                        "origem": fato.origem,
                    }
                    for fato in resposta.fatos
                ),
                chamadas_ferramenta=chamadas,
                leituras_painel=leituras,
                # O braço C não chama modelo nenhum: os campos existem zerados
                # para que o JSONL dos três braços tenha o mesmo esquema.
                chamadas_llm=0,
                iteracoes=0,
                tokens_entrada=0,
                tokens_saida=0,
                custo_usd=0.0,
                latencia_s=latencia,
                veredito_auditor=None,
                violacoes=violacoes,
                convertida_em_recusa=bool(violacoes),
                status_gabarito=pergunta.status_gabarito,
                apuracao=apuracao,
                acerto=acerto,
                motivo_apuracao=motivo_apuracao,
                verificacoes=verificacoes,
                erro_execucao=erro_execucao,
            )
        )

    return ResultadoBraco(
        braco=BRACO_C,
        run_id=run_id or novo_run_id(),
        registros=tuple(registros),
        preparacao_s=preparacao_s,
    )


def registrar_resultado(
    resultado: ResultadoBraco, dir_logs: Path = DIR_LOGS_EXECUCOES
) -> Path:
    """Grava o JSONL da execução (RNF08): uma linha por pergunta + o resumo.

    Reusa `src.avaliacao.registrar_execucao` — mesmo `fsync`, mesmo carimbo UTC.
    O arquivo é próprio da camada de agentes: o benchmark E0–E3 não passa por
    aqui (RNF11), e misturar as duas execuções no mesmo arquivo apagaria a
    separação que a regra existe para manter.
    """
    arquivo = f"agentes_braco_{resultado.braco.lower()}_{resultado.run_id}.jsonl"
    caminho = Path(dir_logs) / arquivo
    for registro in resultado.registros:
        registrar_execucao(
            {
                "tipo": "registro_braco",
                "run_id": resultado.run_id,
                **registro.como_dicionario(),
            },
            dir_logs=Path(dir_logs),
            arquivo=arquivo,
        )
    registrar_execucao(
        {
            "tipo": "resumo_braco",
            "run_id": resultado.run_id,
            "braco": resultado.braco,
            "preparacao_s": resultado.preparacao_s,
            "resumo": resultado.resumo,
        },
        dir_logs=Path(dir_logs),
        arquivo=arquivo,
    )
    return caminho


def salvar_resultado(
    resultado: ResultadoBraco, caminho: Path | None = None
) -> Path:
    """Escreve o resultado completo em JSON, para o cruzamento entre braços."""
    destino = caminho or (
        DIR_RESULTADOS_AGENTES / f"braco_{resultado.braco.lower()}.json"
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(resultado.como_dicionario(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destino


def main() -> None:  # pragma: no cover - execução manual
    """Roda o braço C contra o painel real e grava log + resultado."""
    from src.config import carregar_config

    config = carregar_config()
    perguntas = carregar_conjunto_agentes()
    resultado = executar_braco_c(perguntas, config)
    caminho_log = registrar_resultado(resultado)
    caminho_json = salvar_resultado(resultado)
    print(json.dumps(resultado.resumo, ensure_ascii=False, indent=2))
    print(f"log RNF08: {caminho_log}")
    print(f"resultado: {caminho_json}")


if __name__ == "__main__":  # pragma: no cover - execução manual
    main()


__all__ = [
    "APURACAO_ACERTO",
    "APURACAO_ERRO",
    "APURACAO_PENDENTE",
    "BASES",
    "BASE_CONTABIL_CONSOLIDADO",
    "BASE_CONTABIL_CONTROLADORES",
    "BASE_GERENCIAL",
    "BASE_NA",
    "BRACOS",
    "BRACO_A",
    "BRACO_B",
    "BRACO_C",
    "CAMINHO_CONJUNTO_AGENTES",
    "CAMPOS_REGISTRO",
    "COBERTURA_AMBIGUA",
    "COMPORTAMENTOS",
    "COMPORTAMENTO_COMPLETA",
    "COMPORTAMENTO_DESAMBIGUACAO",
    "COMPORTAMENTO_PARCIAL",
    "COMPORTAMENTO_RECUSA",
    "CRITERIOS",
    "DIR_RESULTADOS_AGENTES",
    "LeitorContado",
    "MOTIVO_RECUSA_CONVERTIDA",
    "PerguntaAgentes",
    "RegistroBraco",
    "ResultadoBraco",
    "STATUS_VERIFICADO",
    "VEREDITOS",
    "VIOLACAO_RN01_SEM_CITACAO",
    "VIOLACAO_RN02_SEM_LASTRO",
    "Verificacao",
    "apurar",
    "base_do_conceito",
    "bases_de",
    "carregar_conjunto_agentes",
    "cobertura_de",
    "comportamento_de",
    "converter_em_recusa",
    "executar_braco_c",
    "motivo_de",
    "nomeia_as_duas_camadas",
    "novo_run_id",
    "registrar_resultado",
    "resumir",
    "salvar_resultado",
    "valores_monetarios",
    "verificar_regras",
]
