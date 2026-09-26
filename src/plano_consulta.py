"""Plano de consulta ao painel: o LLM devolve N células atômicas, não uma intenção.

`src.intencao_consulta` faz o modelo devolver **uma** intenção por pergunta —
uma lista de companhias, um conceito, uma lista de trimestres — e o SQL sai com
`cd_cvm IN (...)`. Funciona, e a comparação de 2026-09-20 mediu zero divergência
de valor contra a rota determinística. Mas o formato de intenção única embute
três limitações que só aparecem quando a pergunta toca mais de uma companhia:

1. **Ausência não tem endereço.** Pedidos cinco bancos, voltaram quatro linhas:
   qual faltou? O conjunto de volta não diz, e responder "o maior é X" sem saber
   quem não veio é exatamente o silêncio que a RN12 existe para quebrar.
2. **Uma companhia ambígua derruba a pergunta inteira.** Medido na mesma
   rodada: "qual dos cinco bancos lucrou mais" morreu na desambiguação do BTG
   Pactual, e os outros quatro — já resolvidos, já consultáveis — nunca foram
   ao painel.
3. **A linhagem é do conjunto, não da célula.** Um `SELECT` com cinco códigos
   produz um SQL para cinco respostas; auditar qual consulta sustentou qual
   número exige recompor o casamento à mão.

Aqui o modelo devolve uma **lista de consultas**, uma por
(companhia, conceito, período), numa única chamada. Cada célula vira seu
próprio `SELECT`, com seu próprio resultado e sua própria procedência. Uma
célula vazia é ausência localizada; uma célula pendente de desambiguação não
contamina as outras; e o SQL que sustenta cada número fica ao lado dele.

**O que NÃO muda, porque é o que segura a rota:** o modelo continua sem
escrever SQL, sem ver número e sem escolher conta. `cd_cvm` continua vindo só
de `resolver_entidade` (RN11), conceito continua tendo de estar em `CONCEITOS`,
e a aritmética continua acontecendo em Python.

**Período é obrigatório em toda célula.** Pergunta sem trimestre ("qual o lucro
do Santander?") devolvia a série inteira nas duas rotas anteriores — seis
números onde o usuário pediu um, e nenhum sinal de que a pergunta estava
incompleta. Aqui isso vira recusa com justificativa, e quem pergunta reformula
dizendo o período. A recusa é `PeriodoIndefinido`, que a interface apresenta na
tela em vez de encaminhar ao corpus: só quem perguntou sabe qual trimestre quis.

**Quatro guardas existem só por causa deste formato**, porque granularidade abre
portas que a intenção única mantinha fechadas por construção:

- **Conceito único em comparação e variação.** Na intenção única havia um
  conceito para a pergunta toda. Aqui cada célula traz o seu, e nada impede o
  modelo de pedir `lucro_liquido_controladores` para o Itaú e
  `lucro_liquido_consolidado` para o Santander. A soma fecha, a tabela fica
  bonita e a comparação é entre grandezas diferentes — a falha plausível-e-errada
  que o projeto inteiro existe para combater. Confrontar exige mesma régua.
- **Comparação incompleta não elege vencedor.** Se uma célula ficou pendente ou
  vazia, a ordem entre as que responderam é publicável, mas o superlativo não:
  o ausente pode ser o maior. Dizer "o maior é X" com o BTG de fora é afirmar
  mais do que o dado sustenta.
- **Teto de células.** O plano é gerado por um modelo, e plano é a única coisa
  nesta rota que cresce sem limite natural. Vinte e quatro células cobrem seis
  companhias em quatro trimestres; acima disso a pergunta não é de painel.
- **Período declarado em toda célula**, pelo que está escrito acima.

**Duas famílias de recusa, e a diferença importa para a interface.**
`ErroDeIntencao` significa "esta rota não é a certa" — conceito fora do painel,
narrativa, companhia inexistente — e o chamador encaminha ao corpus documental,
que pode ter a resposta. `RecusaDeReformulacao` significa "a pergunta precisa
ser reescrita" — período ausente, réguas misturadas — e vai para a tela, porque
nenhuma outra camada resolve o que só quem perguntou sabe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from src.cobertura import Companhia, IndiceCobertura, resolver_entidade
from src.intencao_consulta import (
    ErroDeIntencao,
    Linha,
    desempatar_lucro,
    graos_ambiguos,
    linhas_de,
    validar_sql_da_rota,
)
from src.mapa_contas import CONCEITOS
from src.normalizacao import ordinal_trimestre


class RecusaDeReformulacao(ErroDeIntencao):
    """Recusa que o usuário resolve reescrevendo a pergunta.

    Separada de `ErroDeIntencao` porque o destino é outro: esta volta à tela com
    a justificativa, enquanto a genérica encaminha ao corpus documental. Tratar
    as duas igual mandaria ao RAG uma pergunta que o RAG também não sabe
    responder — e o usuário receberia uma resposta pior em vez de um pedido de
    esclarecimento.
    """


class PeriodoIndefinido(RecusaDeReformulacao):
    """A pergunta não diz o trimestre e não há âncora para inferi-lo."""

OPERACOES: tuple[str, ...] = ("valor", "comparacao", "variacao")
OPERACOES_QUE_CONFRONTAM: tuple[str, ...] = ("comparacao", "variacao")

# Seis companhias × quatro trimestres. Acima disso a pergunta deixou de ser
# consulta a painel e virou extração de base — que tem outra porta.
MAX_CELULAS = 24
# Teto por célula: uma companhia, um conceito, e no máximo a série inteira que
# o painel guarda. Serve para a célula sem período declarado.
LIMITE_LINHAS_CELULA = 12

_PADRAO_TRIMESTRE = re.compile(r"^[1-4]T\d{4}$")


@dataclass(frozen=True)
class Celula:
    """Uma consulta atômica, como o modelo a pediu — ainda sem validação.

    `companhia` é o nome que a pergunta usou. É termo de busca, nunca `cd_cvm`:
    o código sai de `resolver_entidade` e de mais nada (RN11). `trimestre` vazio
    é pergunta incompleta, e a validação o recusa.
    """

    companhia: str
    conceito: str
    trimestre: str = ""


@dataclass(frozen=True)
class PlanoBruto:
    """O que o modelo devolveu, sem julgamento de conteúdo."""

    consultas: tuple[Celula, ...] = ()
    operacao: str = "valor"
    recusar: bool = False
    motivo: str = ""


@dataclass(frozen=True)
class CelulaResolvida:
    """Célula pronta para consultar: código resolvido, conceito conhecido."""

    termo: str
    cd_cvm: str
    denom_social: str
    conceito: str
    trimestre: str
    sql: str

    @property
    def chave(self) -> tuple[str, str, str]:
        """Endereço estável da célula — a mesma pergunta reescrita bate aqui."""
        return (self.cd_cvm, self.conceito, self.trimestre)


@dataclass(frozen=True)
class CelulaPendente:
    """Célula que não virou consulta, e o motivo declarado.

    Existe para que a ausência tenha endereço: sem ela, a companhia que não
    resolveu simplesmente não apareceria na resposta.
    """

    termo: str
    estado: str  # "ambigua" | "nao_resolvida"
    candidatas: tuple[str, ...] = ()
    pergunta_desambiguacao: str | None = None


@dataclass(frozen=True)
class PlanoValidado:
    """Plano pronto para executar, com o que ficou de fora declarado."""

    celulas: tuple[CelulaResolvida, ...]
    pendentes: tuple[CelulaPendente, ...]
    operacao: str
    conceito: str

    @property
    def completo(self) -> bool:
        return not self.pendentes


@dataclass(frozen=True)
class CelulaRespondida:
    """Resultado de uma célula: as linhas que voltaram, ou a ausência."""

    celula: CelulaResolvida
    linhas: tuple[Linha, ...] = ()
    graos_ambiguos: tuple[tuple[str, str], ...] = ()

    @property
    def vazia(self) -> bool:
        return not self.linhas

    @property
    def utilizavel(self) -> bool:
        """Uma linha só, sem grão duplicado — o caso em que há um número."""
        return len(self.linhas) == 1 and not self.graos_ambiguos


PROMPT_PLANO = """\
Você traduz perguntas sobre resultados de bancos em um PLANO DE CONSULTA a um \
painel contábil. Você NÃO responde a pergunta e NÃO escreve número nenhum.

O plano é uma LISTA de consultas atômicas. Cada consulta pede exatamente uma \
companhia, um conceito e um período. Se a pergunta toca cinco bancos, o plano \
tem cinco consultas; se pede dois trimestres da mesma companhia, tem duas.

Responda SOMENTE com um objeto JSON válido, sem texto fora dele:
{
  "consultas": [
    {"companhia": "<nome como a pergunta escreveu>",
     "conceito": "<um dos conceitos permitidos>",
     "trimestre": "<NTAAAA>"}
  ],
  "operacao": "valor" | "comparacao" | "variacao",
  "recusar": <true|false>,
  "motivo": "<uma frase dizendo por que recusa, ou null>"
}

Conceitos permitidos (use EXATAMENTE uma destas cadeias):
%(conceitos)s

Regras:
1. "companhia" traz o nome como a pergunta escreveu ("Itaú", "BB", "Nubank"). \
NÃO tente adivinhar código CVM e NÃO julgue se a companhia existe no painel: \
quem resolve as duas coisas é o sistema. Inclua a consulta mesmo que você ache \
que a companhia não é coberta.
2. Se a pergunta compara bancos sem nomeá-los ("qual dos cinco bancos"), gere \
uma consulta para cada um: Banco do Brasil, Bradesco, BTG Pactual, Itaú, \
Santander.
3. "trimestre" é OBRIGATÓRIO e usa o formato NTAAAA, como "3T2025". Vale para \
UMA consulta só: dois períodos são duas consultas. Resolva referências \
relativas quando a pergunta der a âncora ("mesmo trimestre do ano passado" em \
relação a 3T2025 vira duas consultas, uma com "3T2024" e outra com "3T2025"). \
Se a pergunta NÃO disser o período e não houver âncora para deduzi-lo, não \
invente: marque "recusar" e diga no motivo que falta o trimestre.
4. "operacao" é "comparacao" quando a pergunta ordena ou confronta companhias, \
"variacao" quando pede crescimento, queda ou diferença entre períodos, e \
"valor" no resto.
5. Em "comparacao" e "variacao" TODAS as consultas usam o MESMO conceito: \
confrontar duas grandezas diferentes produz número que parece certo e não é.
6. Marque "recusar" com "consultas" vazia e um "motivo" de uma frase quando: o \
conceito pedido não está na lista acima (índice de Basileia, inadimplência, \
carteira de crédito); a pergunta pede narrativa, causa ou juízo sobre o futuro; \
a pergunta cita o release, a divulgação gerencial ou o resultado ajustado (o \
painel guarda o número contábil arquivado, não a leitura gerencial); ou falta o \
período, pela regra 3.
7. "recusar" fala do CONCEITO e do PERÍODO, nunca da companhia. Se o conceito \
está na lista e o período está definido, "recusar" é false mesmo que a \
companhia lhe pareça desconhecida — cobertura de companhia não é decisão sua.
"""


def prompt_plano() -> str:
    """Prompt com o vocabulário fechado interpolado a partir do mapa."""
    return PROMPT_PLANO % {"conceitos": "\n".join(f"- {c}" for c in CONCEITOS)}


def interpretar_plano(objeto: Mapping[str, Any]) -> PlanoBruto:
    """Converte o JSON do modelo em `PlanoBruto`, sem julgar o conteúdo."""
    operacao = str(objeto.get("operacao") or "valor").strip().lower()
    if operacao not in OPERACOES:
        raise ErroDeIntencao(
            f"operação desconhecida: {operacao!r}; conhecidas={list(OPERACOES)}"
        )
    cruas = objeto.get("consultas")
    if cruas is None:
        cruas = []
    if not isinstance(cruas, (list, tuple)):
        raise ErroDeIntencao(
            f"'consultas' deve ser lista, veio {type(cruas).__name__}"
        )
    if len(cruas) > MAX_CELULAS:
        raise ErroDeIntencao(
            f"plano com {len(cruas)} consultas excede o teto de {MAX_CELULAS}"
        )
    celulas: list[Celula] = []
    for item in cruas:
        if not isinstance(item, Mapping):
            raise ErroDeIntencao(
                f"consulta deve ser objeto, veio {type(item).__name__}"
            )
        celula = Celula(
            companhia=str(item.get("companhia") or "").strip(),
            conceito=str(item.get("conceito") or "").strip(),
            trimestre=str(item.get("trimestre") or "").strip(),
        )
        if celula not in celulas:  # o mesmo pedido duas vezes é um pedido
            celulas.append(celula)
    return PlanoBruto(
        consultas=tuple(celulas),
        operacao=operacao,
        recusar=bool(objeto.get("recusar")),
        motivo=str(objeto.get("motivo") or "").strip(),
    )


def montar_sql_celula(
    cd_cvm: str,
    conceito: str,
    trimestre: str,
    limite: int = LIMITE_LINHAS_CELULA,
) -> str:
    """SQL de uma célula: uma companhia, um conceito, um período.

    Sem agregação e com procedência obrigatória, pelas mesmas razões do template
    de `intencao_consulta` — a visão tem grão duplicado, e `origem`/`corrigido`
    não podem depender de o modelo lembrar de pedi-los (RN10).

    Os três valores são obrigatórios, e `trimestre` é obrigatório aqui também,
    não só na validação: um template capaz de montar consulta sem período seria
    a porta pela qual a série inteira voltaria a sair em silêncio.

    Nenhum deles é texto livre do modelo: `cd_cvm` vem do painel via
    `resolver_entidade`, `conceito` é conferido contra `CONCEITOS` e `trimestre`
    passa pelo padrão `NTAAAA`. A conferência é repetida aqui mesmo assim,
    porque o template é público e um chamador futuro pode não ter validado.
    """
    if not cd_cvm or not str(cd_cvm).strip():
        raise ErroDeIntencao("célula sem companhia resolvida não vira SQL")
    if conceito not in CONCEITOS:
        raise ErroDeIntencao(f"conceito inválido: {conceito!r}")
    if not trimestre:
        raise PeriodoIndefinido("célula sem trimestre não vira SQL")
    if not _PADRAO_TRIMESTRE.match(trimestre):
        raise ErroDeIntencao(f"trimestre malformado: {trimestre!r}")
    if type(limite) is not int or limite <= 0:
        raise ErroDeIntencao("limite deve ser inteiro positivo")
    return (
        "SELECT cd_cvm, denom_social, trimestre, conceito, valor_reais, "
        "origem, corrigido, tipo_periodo\n"
        "FROM fatos_semanticos\n"
        f"WHERE cd_cvm = '{cd_cvm}'\n"
        f"  AND conceito = '{conceito}'\n"
        f"  AND trimestre = '{trimestre}'\n"
        "ORDER BY trimestre\n"
        f"LIMIT {limite}"
    )


def _conceito_unico(celulas: Sequence[CelulaResolvida], operacao: str) -> str:
    """Confrontar exige mesma régua — conceito misturado é recusa, não ajuste.

    Guarda que só existe no formato de plano: com uma intenção por pergunta, o
    conceito era necessariamente um. Com uma célula por companhia, o modelo pode
    pedir leituras diferentes de lucro para bancos diferentes, e a comparação
    entre elas fecha a aritmética enquanto compara coisas distintas.
    """
    conceitos = {c.conceito for c in celulas}
    if len(conceitos) <= 1:
        return next(iter(conceitos), "")
    if operacao in OPERACOES_QUE_CONFRONTAM:
        raise RecusaDeReformulacao(
            f"{operacao} com conceitos diferentes entre as consultas "
            f"({', '.join(sorted(conceitos))}): confrontar exige a mesma régua. "
            "Refaça a pergunta pedindo uma grandeza de cada vez."
        )
    return ""


def validar_plano(
    bruto: PlanoBruto, indice: IndiceCobertura, pergunta: str = ""
) -> PlanoValidado:
    """Resolve cada célula por `CD_CVM` e declara o que ficou pendente.

    Diferença central em relação à intenção única: companhia ambígua **não
    derruba o plano**. Ela vira `CelulaPendente` e as demais células seguem para
    o painel. Isso não afrouxa a RN11 — nada é escolhido automaticamente, a
    pergunta de desambiguação continua sendo devolvida —, mas impede que uma
    ambiguidade em um nome apague quatro respostas que já estavam prontas.

    `recusar` continua valendo só como afirmação sobre o CONCEITO e o PERÍODO:
    cobertura de companhia é decidida por `resolver_entidade` e por mais ninguém.

    Célula sem trimestre levanta `PeriodoIndefinido` mesmo quando o modelo não
    marcou recusa. A guarda é de código porque o prompt já pede o período e o
    modelo pode simplesmente omiti-lo — e a série inteira devolvida em silêncio
    é justamente o defeito que esta versão fecha.
    """
    if bruto.recusar and not bruto.consultas:
        raise ErroDeIntencao(bruto.motivo or "fora do vocabulário do painel")
    if not bruto.consultas:
        raise ErroDeIntencao("plano sem nenhuma consulta")
    sem_periodo = [c.companhia for c in bruto.consultas if not c.trimestre]
    if sem_periodo:
        raise PeriodoIndefinido(
            "a pergunta não indica o trimestre de "
            + ", ".join(dict.fromkeys(sem_periodo))
            + ". Refaça dizendo o período, no formato 3T2025."
        )
    if len(bruto.consultas) > MAX_CELULAS:
        raise ErroDeIntencao(
            f"plano com {len(bruto.consultas)} consultas excede o teto "
            f"de {MAX_CELULAS}"
        )

    resolucoes: dict[str, Any] = {}
    celulas: list[CelulaResolvida] = []
    pendentes: list[CelulaPendente] = []
    vistas: set[tuple[str, str, str]] = set()

    for crua in bruto.consultas:
        conceito = desempatar_lucro(crua.conceito, pergunta)
        if conceito not in CONCEITOS:
            raise ErroDeIntencao(
                f"conceito fora do mapa semântico: {crua.conceito!r}"
            )
        if not _PADRAO_TRIMESTRE.match(crua.trimestre):
            raise ErroDeIntencao(f"trimestre malformado: {crua.trimestre!r}")
        ordinal_trimestre(crua.trimestre)  # levanta se o ordinal não existir

        if crua.companhia not in resolucoes:
            resolucoes[crua.companhia] = resolver_entidade(crua.companhia, indice)
        resolucao = resolucoes[crua.companhia]

        if resolucao.ambigua:
            pendencia = CelulaPendente(
                termo=crua.companhia,
                estado="ambigua",
                candidatas=tuple(c.cd_cvm for c in resolucao.candidatas),
                pergunta_desambiguacao=resolucao.pergunta_desambiguacao(),
            )
            if pendencia not in pendentes:
                pendentes.append(pendencia)
            continue

        companhia: Companhia | None = resolucao.resolvida
        if companhia is None:
            pendencia = CelulaPendente(
                termo=crua.companhia, estado="nao_resolvida"
            )
            if pendencia not in pendentes:
                pendentes.append(pendencia)
            continue

        chave = (companhia.cd_cvm, conceito, crua.trimestre)
        if chave in vistas:
            continue
        vistas.add(chave)
        celulas.append(
            CelulaResolvida(
                termo=crua.companhia,
                cd_cvm=companhia.cd_cvm,
                denom_social=companhia.denom_social,
                conceito=conceito,
                trimestre=crua.trimestre,
                sql=validar_sql_da_rota(
                    montar_sql_celula(companhia.cd_cvm, conceito, crua.trimestre)
                ),
            )
        )

    if not celulas:
        termos = ", ".join(p.termo for p in pendentes) or "nenhuma citada"
        raise ErroDeIntencao(
            f"nenhuma companhia da pergunta virou consulta: {termos}"
        )
    if bruto.operacao == "variacao" and len(celulas) < 2:
        raise ErroDeIntencao("variação exige dois períodos identificados")

    return PlanoValidado(
        celulas=tuple(celulas),
        pendentes=tuple(pendentes),
        operacao=bruto.operacao,
        conceito=_conceito_unico(celulas, bruto.operacao),
    )


def responder_celula(
    celula: CelulaResolvida,
    colunas: Sequence[str],
    linhas_cruas: Sequence[Sequence[Any]],
) -> CelulaRespondida:
    """Casa o resultado do SQL de volta na célula que o pediu."""
    linhas = linhas_de(colunas, linhas_cruas)
    return CelulaRespondida(
        celula=celula, linhas=linhas, graos_ambiguos=graos_ambiguos(linhas)
    )


def assinatura_painel(caminho: str | Path) -> tuple[str, int, int]:
    """Identidade do arquivo do painel: caminho, tamanho e mtime em nanossegundos.

    O cache de células guarda número contábil, e o painel é reconstruído por
    script. Um cache que sobrevivesse à reconstrução serviria o valor antigo
    sem nenhum sinal — a mesma classe de falha que a guarda anti-porta-dos-fundos
    das correções contábeis (§3.3) existe para impedir. Painel ausente devolve
    assinatura própria, para que ele reaparecer também invalide.
    """
    destino = Path(caminho)
    try:
        info = destino.stat()
    except OSError:
        return (str(destino), -1, -1)
    return (str(destino), info.st_size, info.st_mtime_ns)


class CacheDeCelulas:
    """Memória de (cd_cvm, conceito, trimestre) → linhas, presa a um painel.

    A célula é a unidade certa de cache porque o endereço dela é estável: duas
    perguntas escritas de formas diferentes que peçam o lucro do Itaú no 3T2025
    produzem a mesma chave e a segunda não volta ao painel. Guardar por pergunta
    não teria esse efeito, e guardar por plano inteiro erraria sempre que uma
    célula mudasse.

    Não guarda recusa nem célula pendente: só resultado de consulta executada.
    O que é caro aqui é o disco, e o que varia é o painel — memorizar decisão de
    validação faria o cache carregar regra de negócio, que é o lugar errado.
    """

    def __init__(self, assinatura: tuple[str, int, int]) -> None:
        self._assinatura = assinatura
        self._memoria: dict[tuple[str, str, str], tuple[Linha, ...]] = {}
        self.acertos = 0
        self.faltas = 0

    @property
    def tamanho(self) -> int:
        return len(self._memoria)

    def conferir_painel(self, assinatura: tuple[str, int, int]) -> bool:
        """Esvazia tudo se o painel mudou. Devolve True quando esvaziou."""
        if assinatura == self._assinatura:
            return False
        self._assinatura = assinatura
        self._memoria.clear()
        self.acertos = 0
        self.faltas = 0
        return True

    def obter(self, chave: tuple[str, str, str]) -> tuple[Linha, ...] | None:
        guardado = self._memoria.get(chave)
        if guardado is None:
            self.faltas += 1
            return None
        self.acertos += 1
        return guardado

    def guardar(
        self, chave: tuple[str, str, str], linhas: Sequence[Linha]
    ) -> None:
        self._memoria[chave] = tuple(linhas)


def executar_plano(
    plano: PlanoValidado,
    executar: Callable[[str], tuple[Sequence[str], Sequence[Sequence[Any]]]],
    cache: CacheDeCelulas | None = None,
) -> tuple[CelulaRespondida, ...]:
    """Roda cada célula, consultando o painel só para o que não está em cache.

    `executar` recebe o SQL e devolve (colunas, linhas). É injetado para que o
    módulo não dependa de DuckDB nem da interface — e para que o cache possa ser
    verificado sem painel.
    """
    respondidas: list[CelulaRespondida] = []
    for celula in plano.celulas:
        guardado = cache.obter(celula.chave) if cache is not None else None
        if guardado is None:
            colunas, linhas_cruas = executar(celula.sql)
            respondida = responder_celula(celula, colunas, linhas_cruas)
            if cache is not None:
                cache.guardar(celula.chave, respondida.linhas)
        else:
            respondida = CelulaRespondida(
                celula=celula,
                linhas=guardado,
                graos_ambiguos=graos_ambiguos(guardado),
            )
        respondidas.append(respondida)
    return tuple(respondidas)


def pode_eleger_vencedor(
    plano: PlanoValidado, respondidas: Sequence[CelulaRespondida]
) -> bool:
    """Superlativo exige que todos os concorrentes tenham comparecido.

    Com uma célula pendente ou vazia, a ordem entre as que responderam continua
    publicável — mas "o maior é X" não, porque o ausente pode ser o maior.
    Declarar o vencedor sobre um conjunto incompleto é afirmar mais do que o
    dado sustenta, e o usuário não tem como saber disso lendo a resposta.
    """
    if plano.pendentes:
        return False
    return bool(respondidas) and all(r.utilizavel for r in respondidas)


def _marca(linha: Linha) -> str:
    partes = []
    if linha.origem != "arquivado":
        partes.append(linha.origem)
    if linha.corrigido:
        partes.append("corrigido")
    return f" ({', '.join(partes)})" if partes else ""


def _avisos(
    plano: PlanoValidado, respondidas: Sequence[CelulaRespondida]
) -> str:
    """O que não veio, nomeado. Ausência sem endereço é o defeito que o formato
    de célula existe para fechar, então ela nunca sai calada."""
    texto = ""
    vazias = [r for r in respondidas if r.vazia]
    if vazias:
        faltando = "; ".join(
            f"{r.celula.denom_social} em {r.celula.trimestre}" for r in vazias
        )
        texto += f" Sem dado no painel para: {faltando}."
    ambiguas = [r for r in respondidas if r.graos_ambiguos]
    if ambiguas:
        grafia = "; ".join(
            f"{c} em {t}" for r in ambiguas for c, t in r.graos_ambiguos
        )
        texto += (
            f" Recusado por grão duplicado no painel ({grafia}): escolher um "
            "valor em silêncio seria adivinhar."
        )
    if plano.pendentes:
        partes = [
            (
                f"{p.termo} (identifica {len(p.candidatas)} companhias — "
                "falta desambiguar, RN11)"
                if p.estado == "ambigua"
                else f"{p.termo} (não está no painel)"
            )
            for p in plano.pendentes
        ]
        texto += " Ficaram de fora: " + "; ".join(partes) + "."
    return texto


def redigir_resposta(
    plano: PlanoValidado, respondidas: Sequence[CelulaRespondida]
) -> str:
    """Aritmética e redação em Python — o modelo não vê número nenhum.

    A separação é o que sustenta a RN02 nesta rota: o texto que chega à tela é
    montado por código a partir das linhas do painel, e não há caminho pelo qual
    um número escrito pelo modelo alcance o usuário.
    """
    from src.cobertura import formatar_reais

    uteis = [r for r in respondidas if r.utilizavel]
    avisos = _avisos(plano, respondidas)

    if plano.operacao == "comparacao" and uteis:
        ordenadas = sorted(
            uteis, key=lambda r: r.linhas[0].valor_reais, reverse=True
        )
        corpo = "; ".join(
            f"{r.linhas[0].denom_social} "
            f"{formatar_reais(r.linhas[0].valor_reais)}{_marca(r.linhas[0])}"
            for r in ordenadas
        )
        if pode_eleger_vencedor(plano, respondidas):
            return (
                f"Maior: {ordenadas[0].linhas[0].denom_social}. "
                f"Ordem decrescente: {corpo}.{avisos}"
            )
        return (
            f"Comparação incompleta — sem eleger o maior. Ordem entre os "
            f"{len(ordenadas)} que responderam: {corpo}.{avisos}"
        )

    if plano.operacao == "variacao" and len(uteis) >= 2:
        ordenadas = sorted(
            uteis, key=lambda r: (r.celula.cd_cvm, r.celula.trimestre)
        )
        antes, depois = ordenadas[0].linhas[0], ordenadas[-1].linhas[0]
        delta = depois.valor_reais - antes.valor_reais
        pct = (delta / abs(antes.valor_reais) * 100) if antes.valor_reais else None
        variacao = f"{pct:+.1f}%".replace(".", ",") if pct is not None else "n/d"
        derivado = (
            " Valor derivado envolvido (RN10)."
            if any(l.origem != "arquivado" for l in (antes, depois))
            else ""
        )
        return (
            f"{antes.denom_social}: {antes.trimestre} "
            f"{formatar_reais(antes.valor_reais)}{_marca(antes)} → "
            f"{depois.trimestre} {formatar_reais(depois.valor_reais)}"
            f"{_marca(depois)}. Variação {variacao} "
            f"({formatar_reais(delta)}).{derivado}{avisos}"
        )

    corpo = "; ".join(
        f"{l.denom_social} em {l.trimestre}: "
        f"{formatar_reais(l.valor_reais)}{_marca(l)}"
        for r in respondidas
        for l in r.linhas
    )
    return (corpo or "Nenhuma célula do plano trouxe dado.") + avisos


__all__ = [
    "CacheDeCelulas",
    "Celula",
    "CelulaPendente",
    "CelulaRespondida",
    "CelulaResolvida",
    "ErroDeIntencao",
    "LIMITE_LINHAS_CELULA",
    "MAX_CELULAS",
    "OPERACOES",
    "PeriodoIndefinido",
    "PlanoBruto",
    "PlanoValidado",
    "RecusaDeReformulacao",
    "assinatura_painel",
    "executar_plano",
    "interpretar_plano",
    "montar_sql_celula",
    "pode_eleger_vencedor",
    "prompt_plano",
    "redigir_resposta",
    "responder_celula",
    "validar_plano",
]
