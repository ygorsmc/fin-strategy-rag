"""Presidio como reconhecedor ADICIONAL de PII (spec 5.11) — NER de nome de
pessoa, que nenhum padrão fixo em `src.reconhecedores_br` resolve.

**Por que é um módulo à parte, e não uma opção dentro de `reconhecedores_br`.**
`encontrar_entidades` ali é regex puro: rápido, sem import pesado, e é o que
mantém o modo demonstração de pé sem nenhum modelo baixado (RNF12). Presidio
carrega um modelo spaCy inteiro (`pt_core_news_md`, ~40 MB) — pesado o
suficiente para não pagar esse custo em todo processo que só quer validar um
CPF. Este módulo isola isso, e só é importado quando `Config.presidio_habilitado`
é verdadeiro.

**Por que precisa filtrar contra os apelidos de banco.** Medido antes de
integrar: sobre as 45 congeladas + 10 dev, o modelo marca **"Santander" como
PERSON** (score 0,85). Anonimizar isso corromperia a pergunta em silêncio —
pior que um falso bloqueio, porque não aparece como recusa, aparece como uma
busca que não acha nada. `APELIDOS_BANCOS` (já usado pela resolução de
entidade em `src.cobertura`) é o vocabulário certo para filtrar: qualquer
achado cujo texto normalizado bata com um apelido de banco conhecido é
descartado antes de virar `EntidadePII`.

Só o tipo **PERSON** é aceito. `ORGANIZATION` e `LOCATION` do Presidio
marcariam o próprio banco ou a instituição do release como entidade — que é
o assunto legítimo de toda pergunta deste corpus, não dado pessoal do RN06.
"""

from __future__ import annotations

from functools import lru_cache

from src.normalizacao import APELIDOS_BANCOS, remover_acentos
from src.reconhecedores_br import TIPO_PESSOA, EntidadePII

PRESIDIO_IDIOMA_PADRAO = "pt"
PRESIDIO_MODELO_SPACY_PADRAO = "pt_core_news_md"
_LIMIAR_SCORE = 0.5


class PresidioIndisponivelError(RuntimeError):
    """Falha fechada (RNF03): dizer exatamente o que falta, nunca degradar
    em silêncio quando `presidio_habilitado=True` foi pedido explicitamente."""


def _apelidos_normalizados() -> frozenset[str]:
    nomes: set[str] = set()
    for apelidos in APELIDOS_BANCOS.values():
        for apelido in apelidos:
            nomes.add(remover_acentos(apelido).casefold())
    return frozenset(nomes)


_APELIDOS_NORMALIZADOS = _apelidos_normalizados()


def _e_apelido_de_banco(texto: str) -> bool:
    normalizado = remover_acentos(texto).casefold().strip()
    if normalizado in _APELIDOS_NORMALIZADOS:
        return True
    # "Itaú Unibanco" não bate exato com o apelido "itau unibanco" só se a
    # pontuação variar; comparar por token cobre isso sem exigir igualdade
    # de string byte a byte.
    return any(
        normalizado == apelido or apelido in normalizado.split()
        for apelido in _APELIDOS_NORMALIZADOS
    )


@lru_cache(maxsize=4)
def _motor(idioma: str, modelo_spacy: str):
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
    except ImportError as exc:
        raise PresidioIndisponivelError(
            "PRESIDIO_HABILITADO=true mas presidio-analyzer/spacy não estão "
            "instalados. Instale requirements-guardrails.txt."
        ) from exc
    configuracao = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": idioma, "model_name": modelo_spacy}],
    }
    try:
        provedor = NlpEngineProvider(nlp_configuration=configuracao)
        motor_nlp = provedor.create_engine()
    except (OSError, SystemExit) as exc:
        # Modelo spaCy ausente não levanta OSError aqui: o carregador do
        # spaCy tenta baixar o pacote e, ao falhar (nome inválido, sem rede),
        # a CLI dele encerra o processo com `sys.exit(1)` — SystemExit, não
        # uma exceção comum. Sem capturar os dois, um `pytest` inteiro
        # morreria por um modelo não instalado, em vez de reportar um erro
        # de configuração comum.
        raise PresidioIndisponivelError(
            f"PRESIDIO_HABILITADO=true mas o modelo spaCy {modelo_spacy!r} não "
            f"está baixado. Rode: python -m spacy download {modelo_spacy}"
        ) from exc
    return AnalyzerEngine(nlp_engine=motor_nlp, supported_languages=[idioma])


def presidio_disponivel(
    idioma: str = PRESIDIO_IDIOMA_PADRAO,
    modelo_spacy: str = PRESIDIO_MODELO_SPACY_PADRAO,
) -> bool:
    """Sonda sem lançar — para uso em diagnóstico/UI, nunca no caminho de
    decisão de bloqueio (que deve falhar fechado via `_motor`)."""
    try:
        _motor(idioma, modelo_spacy)
        return True
    except PresidioIndisponivelError:
        return False


def entidades_presidio(
    texto: str,
    *,
    idioma: str = PRESIDIO_IDIOMA_PADRAO,
    modelo_spacy: str = PRESIDIO_MODELO_SPACY_PADRAO,
) -> list[EntidadePII]:
    """Nomes de pessoa encontrados por NER, com os bancos do corpus excluídos.

    Levanta `PresidioIndisponivelError` se o pacote ou o modelo faltarem — o
    chamador (`src.seguranca`) só entra aqui quando `presidio_habilitado` foi
    ligado explicitamente, e nesse caso a ausência é erro de configuração, não
    degradação silenciosa (RNF03).
    """
    if not isinstance(texto, str) or not texto:
        return []
    analisador = _motor(idioma, modelo_spacy)
    resultados = analisador.analyze(
        text=texto, language=idioma, entities=["PERSON"]
    )
    achados: list[EntidadePII] = []
    for resultado in resultados:
        if resultado.score < _LIMIAR_SCORE:
            continue
        trecho = texto[resultado.start : resultado.end]
        if _e_apelido_de_banco(trecho):
            continue
        # O recognizer spaCy da Presidio dá score FIXO (0,85) por tipo, não
        # gradiente de confiança — "CPF" e "João da Silva" saem empatados.
        # Medido: sigla toda maiúscula ("CPF", "CVM", "ROAE") é confundida com
        # nome de pessoa. Nenhum nome de pessoa em português corrido aparece
        # inteiramente em maiúsculas, então `isupper()` separa as duas classes
        # sem custar recall sobre nome real.
        if trecho.isupper():
            continue
        # Medido contra `conjunto_padrao/ataques.csv`: "Ignore todas as
        # instruções..." e "Aja como se..." são marcados PERSON só porque o
        # verbo abre a frase e vem maiúsculo — artefato de capitalização, não
        # nome. Um token só, na posição 0, é exatamente esse padrão. O custo é
        # não anonimizar um primeiro nome isolado quando ele abre a pergunta
        # (raro neste domínio); o benefício é não deixar a anonimização
        # engolir o verbo que o scanner de injeção precisa ver — a anonimização
        # roda ANTES da varredura de conduta, e um "Ignore" apagado é um
        # ataque que passa. PII nunca bloqueia, então esse é o lado seguro do
        # trade-off: perder redação é reversível, perder detecção de injeção
        # não é.
        if resultado.start == 0 and " " not in trecho:
            continue
        achados.append(
            EntidadePII(TIPO_PESSOA, resultado.start, resultado.end, trecho)
        )
    return achados
