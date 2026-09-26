"""Rota de consulta ao painel com o LLM como INTÉRPRETE, não como autor do SQL.

O casador determinístico de `src.cobertura` responde bem a pergunta canônica
("lucro líquido do Itaú no 3T2025") e degrada em silêncio fora dela: vocabulário
fechado em dez expressões, nenhuma comparação entre companhias, nenhuma
aritmética, e pergunta sem trimestre devolve a série inteira. Este módulo abre
esse alcance sem abrir a porta que a RN09 tranca.

**A divisão de trabalho é a garantia.** O modelo lê a pergunta e devolve
*intenção* — quais companhias, qual conceito, quais trimestres, que operação.
Nada mais. O SQL é montado por `montar_sql`, a partir da intenção já validada,
e a aritmética acontece em Python depois que as linhas voltam. O modelo nunca
escreve SQL, nunca vê número e nunca escolhe conta.

Quatro guardas sustentam isso, e cada uma existe por um defeito concreto:

1. **Companhia do modelo é só um termo de busca.** O `cd_cvm` vem sempre de
   `resolver_entidade` (RN11); nome que resolve para mais de uma companhia gera
   desambiguação, nunca escolha automática. Se o modelo alucinar um código, ele
   é descartado — não chega ao SQL.
2. **Conceito fora de `CONCEITOS` levanta erro**, em vez de virar o conceito
   mais parecido. Aproximar aqui é o mesmo pecado que a RN09 proíbe.
3. **O SQL não agrega.** Medido em 2026-09-20: a visão tem 12 grãos
   (companhia × trimestre × conceito) com duas linhas de valores diferentes —
   um `SUM` sobre eles devolveria número plausível e errado. As linhas voltam
   cruas, a aritmética é feita em código, e grão ambíguo vira recusa explícita.
4. **Marca de procedência é obrigatória no `SELECT`.** `origem` e `corrigido`
   sempre saem, porque a RN10 e a marca de correção não podem depender de o
   modelo lembrar de pedi-las.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.cobertura import IndiceCobertura, resolver_entidade
from src.mapa_contas import (
    CONCEITO_LUCRO_CONSOLIDADO,
    CONCEITO_LUCRO_CONTROLADORES,
    CONCEITO_LUCRO_NAO_CONTROLADORES,
    CONCEITO_LUCRO_PADRAO,
    CONCEITOS,
)
from src.normalizacao import ordinal_trimestre, remover_acentos

# As três leituras de "lucro líquido". Medido em 2026-09-20: o intérprete
# escolhe entre elas de forma INCOERENTE — "lucro líquido do Itaú" veio
# `controladores` e "lucro do Itaú" veio `consolidado`, uma diferença de
# R$ 294 milhões no 3T2025 que não tem nada a ver com a pergunta. O desempate
# é do projeto e está declarado em `mapa_contas`, então ele é aplicado aqui,
# em código: a escolha do modelo só sobrevive quando a PERGUNTA qualifica.
LEITURAS_DE_LUCRO: frozenset[str] = frozenset(
    {
        CONCEITO_LUCRO_CONSOLIDADO,
        CONCEITO_LUCRO_CONTROLADORES,
        CONCEITO_LUCRO_NAO_CONTROLADORES,
    }
)
QUALIFICADORES_DE_LUCRO: tuple[str, ...] = (
    "consolidado",
    "controladora",
    "controladores",
    "minoritario",
    "nao controlador",
)

OPERACOES: tuple[str, ...] = ("valor", "comparacao", "variacao")

_PADRAO_TRIMESTRE = re.compile(r"^[1-4]T\d{4}$")
_AGREGADORES = ("sum(", "avg(", "count(", "min(", "max(", "group by")

LIMITE_LINHAS = 40


class ErroDeIntencao(Exception):
    """Intenção que não passa na validação — nunca vira SQL aproximado."""


@dataclass(frozen=True)
class IntencaoBruta:
    """O que o modelo devolveu, ainda sem validação nenhuma."""

    companhias: tuple[str, ...] = ()
    conceito: str = ""
    trimestres: tuple[str, ...] = ()
    operacao: str = "valor"
    fora_do_painel: bool = False
    motivo: str = ""


@dataclass(frozen=True)
class IntencaoValidada:
    """Intenção pronta para virar SQL: códigos resolvidos, conceito conhecido."""

    codigos: tuple[str, ...]
    conceito: str
    trimestres: tuple[str, ...]
    operacao: str
    resolvidas: Mapping[str, str] = field(default_factory=dict)
    ambiguas: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    nao_resolvidas: tuple[str, ...] = ()


PROMPT_INTERPRETE = """\
Você traduz perguntas sobre resultados de bancos em INTENÇÃO DE CONSULTA a um \
painel contábil. Você NÃO responde a pergunta e NÃO inventa número nenhum.

Responda SOMENTE com um objeto JSON válido, sem texto fora dele:
{
  "companhias": ["<nome como aparece na pergunta>", ...],
  "conceito": "<um dos conceitos permitidos, ou null>",
  "trimestres": ["<NTAAAA>", ...],
  "operacao": "valor" | "comparacao" | "variacao",
  "fora_do_painel": <true|false>,
  "motivo": "<por que está fora do painel, ou null>"
}

Conceitos permitidos (use EXATAMENTE uma destas cadeias):
%(conceitos)s

Regras:
1. "companhias" traz o nome como a pergunta escreveu ("Itaú", "BB", "Nubank"). \
NÃO tente adivinhar código CVM e NÃO julgue se a companhia existe no painel: \
quem resolve as duas coisas é o sistema. Liste o nome mesmo que você ache que \
a companhia não é coberta.
2. Se a pergunta compara bancos sem nomeá-los ("qual dos cinco bancos"), \
liste os cinco: Banco do Brasil, Bradesco, BTG Pactual, Itaú, Santander.
3. "trimestres" usa o formato NTAAAA, como "3T2025". Resolva referências \
relativas quando a pergunta der a âncora ("mesmo trimestre do ano passado" em \
relação a 3T2025 vira ["3T2024", "3T2025"]). Sem trimestre na pergunta, \
devolva lista vazia.
4. "operacao" é "comparacao" quando a pergunta ordena ou confronta companhias, \
"variacao" quando pede crescimento, queda ou diferença entre períodos, e \
"valor" no resto.
5. "fora_do_painel" fala SOMENTE do conceito, nunca da companhia. Marque true \
quando o conceito pedido não está na lista acima (índice de Basileia, \
inadimplência, carteira de crédito) ou quando a pergunta pede narrativa, causa \
ou juízo sobre o futuro; nesses casos "conceito" é null e "motivo" explica em \
uma frase. Se o conceito ESTÁ na lista, "fora_do_painel" é false mesmo que a \
companhia lhe pareça desconhecida — cobertura de companhia não é decisão sua.
6. Pergunta que cita explicitamente o release, a divulgação gerencial ou o \
resultado ajustado é "fora_do_painel": o painel guarda o número contábil \
arquivado, não a leitura gerencial.
"""


def prompt_interprete() -> str:
    """Prompt com o vocabulário fechado interpolado a partir do mapa."""
    return PROMPT_INTERPRETE % {
        "conceitos": "\n".join(f"- {c}" for c in CONCEITOS)
    }


def _texto_json(bruto: str) -> dict[str, Any]:
    """Extrai o objeto JSON da resposta, tolerando cerca de crase."""
    texto = (bruto or "").strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", texto).strip()
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fim <= inicio:
        raise ErroDeIntencao(f"resposta do intérprete não traz JSON: {bruto!r:.200}")
    try:
        objeto = json.loads(texto[inicio : fim + 1])
    except json.JSONDecodeError as erro:
        raise ErroDeIntencao(f"JSON inválido do intérprete: {erro}") from erro
    if not isinstance(objeto, dict):
        raise ErroDeIntencao("o intérprete devolveu algo que não é objeto")
    return objeto


def _lista_de_texto(valor: Any) -> tuple[str, ...]:
    if valor is None:
        return ()
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, (list, tuple)):
        raise ErroDeIntencao(f"esperava lista, veio {type(valor).__name__}")
    return tuple(str(item).strip() for item in valor if str(item).strip())


def interpretar(objeto: Mapping[str, Any]) -> IntencaoBruta:
    """Converte o JSON do modelo em `IntencaoBruta`, sem julgar o conteúdo."""
    operacao = str(objeto.get("operacao") or "valor").strip().lower()
    if operacao not in OPERACOES:
        raise ErroDeIntencao(
            f"operação desconhecida: {operacao!r}; conhecidas={list(OPERACOES)}"
        )
    conceito = objeto.get("conceito")
    return IntencaoBruta(
        companhias=_lista_de_texto(objeto.get("companhias")),
        conceito=(str(conceito).strip() if conceito else ""),
        trimestres=_lista_de_texto(objeto.get("trimestres")),
        operacao=operacao,
        fora_do_painel=bool(objeto.get("fora_do_painel")),
        motivo=str(objeto.get("motivo") or "").strip(),
    )


def desempatar_lucro(conceito: str, pergunta: str) -> str:
    """Aplica `CONCEITO_LUCRO_PADRAO` quando a pergunta não qualifica qual lucro.

    `mapa_contas` declara que o padrão exibido é o dos controladores, por ser a
    convenção de mercado e a base do lucro por ação. Deixar essa escolha com o
    modelo produziu resposta diferente para a mesma pergunta parafraseada.
    """
    if conceito not in LEITURAS_DE_LUCRO:
        return conceito
    texto = remover_acentos(pergunta or "").lower()
    if any(marca in texto for marca in QUALIFICADORES_DE_LUCRO):
        return conceito
    return CONCEITO_LUCRO_PADRAO


def validar(
    bruta: IntencaoBruta, indice: IndiceCobertura, pergunta: str = ""
) -> IntencaoValidada:
    """Resolve companhia por CD_CVM (RN11) e recusa conceito desconhecido.

    O código NUNCA vem do modelo: `resolver_entidade` é a única fonte, e o que
    ela devolver ambíguo vira pergunta de desambiguação em vez de escolha.

    `fora_do_painel` só vale como afirmação sobre o CONCEITO. Cobertura de
    companhia é decidida por `resolver_entidade` e por mais ninguém — medido em
    2026-09-20, o intérprete afirmou que o Banco Inter "não faz parte do painel"
    quando ele está lá (CD_CVM 080217), e acreditar nisso teria transformado
    uma resposta correta em recusa inventada.
    """
    if bruta.fora_do_painel and bruta.conceito not in CONCEITOS:
        raise ErroDeIntencao(bruta.motivo or "fora do vocabulário do painel")
    if bruta.conceito not in CONCEITOS:
        raise ErroDeIntencao(
            f"conceito fora do mapa semântico: {bruta.conceito!r}"
        )
    for trimestre in bruta.trimestres:
        if not _PADRAO_TRIMESTRE.match(trimestre):
            raise ErroDeIntencao(f"trimestre malformado: {trimestre!r}")
        ordinal_trimestre(trimestre)  # levanta se o ordinal não existir

    codigos: list[str] = []
    resolvidas: dict[str, str] = {}
    ambiguas: dict[str, tuple[str, ...]] = {}
    nao_resolvidas: list[str] = []
    for termo in bruta.companhias:
        resolucao = resolver_entidade(termo, indice)
        if resolucao.ambigua:
            ambiguas[termo] = tuple(
                c.cd_cvm for c in (resolucao.candidatas or ())
            )
        elif resolucao.resolvida is not None:
            codigo = resolucao.resolvida.cd_cvm
            resolvidas[termo] = codigo
            if codigo not in codigos:
                codigos.append(codigo)
        else:
            nao_resolvidas.append(termo)

    if not codigos and not ambiguas:
        raise ErroDeIntencao(
            "nenhuma companhia da pergunta existe no painel: "
            + (", ".join(nao_resolvidas) or "nenhuma citada")
        )
    if bruta.operacao == "variacao" and len(bruta.trimestres) < 2:
        raise ErroDeIntencao("variação exige dois trimestres identificados")
    return IntencaoValidada(
        codigos=tuple(codigos),
        conceito=desempatar_lucro(bruta.conceito, pergunta),
        trimestres=tuple(dict.fromkeys(bruta.trimestres)),
        operacao=bruta.operacao,
        resolvidas=resolvidas,
        ambiguas=ambiguas,
        nao_resolvidas=tuple(nao_resolvidas),
    )


def montar_sql(intencao: IntencaoValidada, limite: int = LIMITE_LINHAS) -> str:
    """SQL por template, sem agregação e com procedência obrigatória.

    Não agrega de propósito (ver guarda 3 no topo do módulo): as linhas voltam
    cruas e a conta é feita em Python, onde grão duplicado é detectado em vez de
    somado. `origem`, `corrigido` e `tipo_periodo` saem sempre.
    """
    if not intencao.codigos:
        raise ErroDeIntencao("sem companhia resolvida, não há SQL a montar")
    if intencao.conceito not in CONCEITOS:
        raise ErroDeIntencao(f"conceito inválido: {intencao.conceito!r}")
    if type(limite) is not int or limite <= 0:
        raise ErroDeIntencao("limite deve ser inteiro positivo")
    lista = ", ".join(f"'{codigo}'" for codigo in intencao.codigos)
    filtro = ""
    if intencao.trimestres:
        periodos = ", ".join(f"'{t}'" for t in intencao.trimestres)
        filtro = f"\n  AND trimestre IN ({periodos})"
    return (
        "SELECT cd_cvm, denom_social, trimestre, conceito, valor_reais, "
        "origem, corrigido, tipo_periodo\n"
        "FROM fatos_semanticos\n"
        f"WHERE cd_cvm IN ({lista})\n"
        f"  AND conceito = '{intencao.conceito}'{filtro}\n"
        "ORDER BY cd_cvm, trimestre\n"
        f"LIMIT {limite}"
    )


def validar_sql_da_rota(sql: str) -> str:
    """Segunda guarda, específica desta rota, em cima da RN04.

    A guarda da RN04 protege o painel (somente-leitura, lista branca, sem
    `cd_conta`). Esta protege a RESPOSTA: sem `origem` e `corrigido` no
    `SELECT`, um valor derivado chegaria à tela sem a marca que a RN10 exige; e
    agregação sobre grão duplicado devolveria número plausível e errado.
    """
    texto = (sql or "").lower()
    faltando = [c for c in ("origem", "corrigido") if c not in texto]
    if faltando:
        raise ErroDeIntencao(
            "SELECT sem marca de procedência: falta " + ", ".join(faltando)
        )
    for agregador in _AGREGADORES:
        if agregador in texto:
            raise ErroDeIntencao(
                f"agregação proibida nesta rota: {agregador.strip('(')!r} — "
                "a visão tem grão duplicado e a conta é feita em Python"
            )
    return sql


@dataclass(frozen=True)
class Linha:
    """Uma linha do painel, com a procedência que a resposta precisa citar."""

    cd_cvm: str
    denom_social: str
    trimestre: str
    conceito: str
    valor_reais: float
    origem: str
    corrigido: bool
    tipo_periodo: str


def linhas_de(resultado_colunas: Sequence[str], linhas: Sequence[Sequence[Any]]):
    """Converte o resultado do SQL em `Linha`, por nome de coluna."""
    indice = {nome: i for i, nome in enumerate(resultado_colunas)}
    return tuple(
        Linha(
            cd_cvm=str(linha[indice["cd_cvm"]]),
            denom_social=str(linha[indice["denom_social"]]),
            trimestre=str(linha[indice["trimestre"]]),
            conceito=str(linha[indice["conceito"]]),
            valor_reais=float(linha[indice["valor_reais"]]),
            origem=str(linha[indice["origem"]]),
            corrigido=bool(linha[indice["corrigido"]]),
            tipo_periodo=str(linha[indice["tipo_periodo"]]),
        )
        for linha in linhas
    )


def graos_ambiguos(linhas: Sequence[Linha]) -> tuple[tuple[str, str], ...]:
    """Grãos (companhia, trimestre) com mais de um valor distinto.

    Medido em 12 casos no painel de 2026-09-20. Escolher um deles em silêncio
    seria a falha que o projeto existe para combater, então quem chama recusa.
    """
    por_grao: dict[tuple[str, str], set[float]] = {}
    for linha in linhas:
        por_grao.setdefault((linha.cd_cvm, linha.trimestre), set()).add(
            linha.valor_reais
        )
    return tuple(sorted(grao for grao, valores in por_grao.items() if len(valores) > 1))


__all__ = [
    "CONCEITOS",
    "ErroDeIntencao",
    "IntencaoBruta",
    "IntencaoValidada",
    "LIMITE_LINHAS",
    "Linha",
    "LEITURAS_DE_LUCRO",
    "OPERACOES",
    "desempatar_lucro",
    "graos_ambiguos",
    "interpretar",
    "linhas_de",
    "montar_sql",
    "prompt_interprete",
    "validar",
    "validar_sql_da_rota",
]
