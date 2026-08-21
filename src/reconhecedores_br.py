"""Reconhecedores de identificadores brasileiros para a RN06 (spec 5.11).

**Por que não bastam expressões regulares.** Um CPF tem a forma de onze
dígitos, e um release financeiro está cheio de onze dígitos: `1.296.511` de
carteira, `220.017` de patrimônio, códigos de conta, datas concatenadas. Um
reconhecedor que só olhe a forma marca todos eles como dado pessoal — e o
projeto tem meta declarada de **zero falso bloqueio** nas 45 perguntas
legítimas. Por isso CPF e CNPJ aqui são validados pelo **dígito verificador**,
que é o que separa "tem cara de CPF" de "é um CPF".

O Presidio (spec 5.11) entra como reconhecedor adicional atrás da mesma
interface, não como substituto: ele traz NER de nome de pessoa, que expressão
regular nenhuma resolve. Estes reconhecedores continuam valendo mesmo sem ele,
porque a RNF12 exige que o modo demonstração suba **sem nenhum segredo nem
modelo baixado**.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


TIPO_CPF = "CPF"
TIPO_CNPJ = "CNPJ"
TIPO_EMAIL = "EMAIL"
TIPO_TELEFONE = "TELEFONE_BR"
TIPO_CEP = "CEP"
# Nome de pessoa: nenhum destes reconhecedores por regex resolve NER. Só entra
# via `src.reconhecedor_presidio`, que é reconhecedor ADICIONAL (spec 5.11) —
# ver lá por que precisa filtrar contra os apelidos de banco antes de aceitar.
TIPO_PESSOA = "PESSOA"

TIPOS_CONHECIDOS: frozenset[str] = frozenset(
    {TIPO_CPF, TIPO_CNPJ, TIPO_EMAIL, TIPO_TELEFONE, TIPO_CEP, TIPO_PESSOA}
)


@dataclass(frozen=True)
class EntidadePII:
    """Uma ocorrência localizada, com posição para anonimização estável."""

    tipo: str
    inicio: int
    fim: int
    texto: str


def _apenas_digitos(bruto: str) -> str:
    return "".join(caractere for caractere in bruto if caractere.isdigit())


def _digito_verificador(digitos: str, pesos: range | list[int]) -> int:
    soma = sum(int(d) * p for d, p in zip(digitos, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cpf(bruto: str) -> bool:
    """True quando os dois dígitos verificadores fecham.

    Sequências repetidas (`111.111.111-11`) passam na aritmética e são
    rejeitadas à parte: são inválidas por norma e aparecem em documento como
    exemplo/preenchimento, nunca como dado de pessoa real.
    """
    digitos = _apenas_digitos(bruto)
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    primeiro = _digito_verificador(digitos[:9], range(10, 1, -1))
    segundo = _digito_verificador(digitos[:10], range(11, 1, -1))
    return digitos[9] == str(primeiro) and digitos[10] == str(segundo)


def validar_cnpj(bruto: str) -> bool:
    """True quando os dois dígitos verificadores fecham.

    Vale para CNPJ de instituição também — a RN06 protege o usuário, e um CNPJ
    digitado numa pergunta é dado de cadastro, não conteúdo do release.
    """
    digitos = _apenas_digitos(bruto)
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False
    pesos_primeiro = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_segundo = [6] + pesos_primeiro
    primeiro = _digito_verificador(digitos[:12], pesos_primeiro)
    segundo = _digito_verificador(digitos[:13], pesos_segundo)
    return digitos[12] == str(primeiro) and digitos[13] == str(segundo)


# `(?<!\d)` e `(?!\d)` impedem casar o miolo de um número maior: sem eles,
# um saldo de quinze dígitos ofereceria uma janela de onze que por acaso
# fecha o dígito verificador.
_PADRAO_CPF = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
_PADRAO_CNPJ = re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)")
_PADRAO_EMAIL = re.compile(
    r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])", re.IGNORECASE
)
# Exige DDD entre parênteses ou o prefixo +55, ou o hífen separando os blocos.
# Um `2025 1234` solto num texto financeiro não vira telefone por acidente.
_PADRAO_TELEFONE = re.compile(
    r"(?<!\d)(?:\+55\s?)?(?:\(\d{2}\)\s?|\d{2}\s)?9?\d{4}-\d{4}(?!\d)"
    r"|(?<!\d)\+55\s?\(?\d{2}\)?\s?9?\d{4}[\s-]?\d{4}(?!\d)"
)
_PADRAO_CEP = re.compile(r"(?<!\d)\d{5}-\d{3}(?!\d)")


def _varrer(
    texto: str, padrao: re.Pattern[str], tipo: str, validador=None
) -> list[EntidadePII]:
    achados: list[EntidadePII] = []
    for casamento in padrao.finditer(texto):
        bruto = casamento.group(0)
        if validador is not None and not validador(bruto):
            continue
        achados.append(
            EntidadePII(tipo, casamento.start(), casamento.end(), bruto)
        )
    return achados


def combinar_sem_sobreposicao(
    achados: list[EntidadePII],
) -> list[EntidadePII]:
    """Funde listas de reconhecedores diferentes num único trilho de posições.

    Em empate de posição vence a entidade mais longa: `12.345.678/0001-95` é
    CNPJ inteiro, não um CPF de onze dígitos escondido dentro dele. Reusado
    por `src.reconhecedor_presidio` para fundir NER com os regex daqui, sem
    duplicar a regra de desempate.
    """
    ordenados = sorted(achados, key=lambda e: (e.inicio, -(e.fim - e.inicio)))
    sem_sobreposicao: list[EntidadePII] = []
    limite = -1
    for entidade in ordenados:
        if entidade.inicio >= limite:
            sem_sobreposicao.append(entidade)
            limite = entidade.fim
    return sem_sobreposicao


def encontrar_entidades(texto: str) -> list[EntidadePII]:
    """Reconhecedores por regex/dígito verificador — rápidos, sem dependência
    pesada. NER de nome de pessoa (Presidio) é uma camada adicional em
    `src.reconhecedor_presidio`, deliberadamente fora daqui: esta função
    continua funcionando em qualquer ambiente, inclusive o de demonstração
    sem nenhum modelo baixado (RNF12)."""
    if not isinstance(texto, str) or not texto:
        return []
    achados: list[EntidadePII] = []
    achados += _varrer(texto, _PADRAO_CNPJ, TIPO_CNPJ, validar_cnpj)
    achados += _varrer(texto, _PADRAO_CPF, TIPO_CPF, validar_cpf)
    achados += _varrer(texto, _PADRAO_EMAIL, TIPO_EMAIL)
    achados += _varrer(texto, _PADRAO_TELEFONE, TIPO_TELEFONE)
    achados += _varrer(texto, _PADRAO_CEP, TIPO_CEP)
    return combinar_sem_sobreposicao(achados)
