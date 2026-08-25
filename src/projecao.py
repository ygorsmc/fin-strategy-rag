"""Rota da pergunta prospectiva sobre emissor nomeado — a RN07 no ponto de uso.

**O problema que este módulo resolve.** "Nos próximos trimestres, o banco XYZ
terá lucro ou prejuízo?" é a pergunta natural de quem tem um modelo preditivo
por perto. Ela não é ataque, não é injeção e não é pedido de recomendação — os
scanners de `src.seguranca` corretamente a deixam passar. Mas responder com uma
probabilidade colada a um emissor identificado é juízo prospectivo sobre valor
mobiliário, a mesma fronteira que a RN05 protege no sentido oposto.

**A decisão, e por que ela é condicional ao modo (2026-08-24).** A Res. CVM
20/2021 regula a *atividade* de análise — elaborar relatório destinado a
auxiliar decisão de investimento — e sua mordida está na divulgação a
terceiros. Uma ferramenta que um analista credenciado usa para conferir o
próprio trabalho é insumo do processo dele, não relatório não registrado. Logo:

* **instância pública** (Streamlit aberto, sem autenticação): recusa o número
  por emissor e entrega o que é defensável — histórico arquivado, regime de
  risco por porte e panorama agregado do mercado;
* **modo local/autenticado** (`previsao_por_emissor_habilitada=True`): entrega
  também o escore do emissor, etiquetado como fora de domínio e acompanhado da
  taxa-base do porte, para o analista ver quanto do número é só o regime.

O padrão é o público (RNF12: o modo demonstração abre sem nada configurado).

**Por que o modelo não é importado aqui.** Nem o caminho público nem o local
carregam `src.modelo` em tempo de resposta. Os dois leem um artefato calculado
**offline** por `scripts/gerar_panorama_modelo.py`. Motivos, em ordem: treinar
por pergunta seria absurdo; o deploy enxuto não precisa de scikit-learn
(RNF12); e a isolação da RN07 continua verificável por varredura de import.

**O agregado tem duas armadilhas, e as duas custaram uma auditoria (2026-08-24).**

1. *Vazamento por eliminação.* Publicar "0 das 13 instituições financeiras
   estão acima do limiar" ao lado de uma pergunta sobre um banco permite
   deduzir o estado daquele banco. A proteção **efetiva** é que nenhum
   agregado setorial do trimestre corrente chega a ser calculado — o panorama
   só carrega o agregado do painel inteiro e taxas históricas por porte.
   `_agregado_seguro` é a segunda linha, para o caso de alguém acrescentar um
   recorte depois.
2. *Tautologia com cara de medição.* A primeira versão publicava "o modelo
   colocou 41 de 413 companhias no decil superior" — que é sempre 10% por
   definição de decil, não diz nada sobre o trimestre, e ainda tornava
   `_agregado_seguro` inalcançável (a contagem nunca podia ser 0 nem o total).
   Trocado por contagem acima de um limiar **absoluto**, que varia e informa.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from src.normalizacao import remover_acentos
from src.seguranca import RESOLUCAO_ANALISE, Achado

# --------------------------------------------------------------------------- #
# Detecção
# --------------------------------------------------------------------------- #

SCANNER_PROJECAO = "projecao_resultado"
SUBTIPO_PROJECAO = "projecao_resultado"

#: Caminho padrão do artefato agregado — versionado, seguro para o deploy
#: público. Os escores por companhia vivem em arquivo separado e fora do Git.
CAMINHO_PANORAMA = Path("artefatos/modelo/panorama.json")
CAMINHO_ESCORES = Path("artefatos/modelo/escores_por_companhia.json")

_ALVO = r"(?:lucro|prejuizo|resultado|rentabilidade)"

#: A marca de "prospectivo" é tempo futuro OU referência a período futuro, e
#: sempre junto de um substantivo de resultado. Só o futuro não basta ("o que
#: vai constar no release?" não é projeção) e só o substantivo tampouco ("qual
#: foi o lucro?" é retrospectivo e precisa continuar passando).
_PADROES_PROJECAO: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(rf"\b(?:tera|terao|havera|vai\s+ter|vao\s+ter)\b.{{0,40}}{_ALVO}"),
        "pergunta em tempo futuro sobre resultado de emissor",
    ),
    (
        re.compile(
            r"\b(?:vai|vao|ira|irao|deve|devem|devera|deverao)\s+"
            rf"(?:dar|ter|reportar|apresentar|registrar|apurar|fechar)\b.{{0,25}}{_ALVO}"
        ),
        "pergunta em tempo futuro sobre resultado de emissor",
    ),
    (
        re.compile(
            rf"{_ALVO}.{{0,50}}\b(?:no|nos|do|dos|para\s+os?|em)\s+"
            r"(?:proximos?|proximo|futuros?|vindouros?)\s+"
            r"(?:trimestres?|anos?|exercicios?|periodos?)"
        ),
        "pergunta sobre resultado em período futuro",
    ),
    (
        re.compile(
            r"\b(?:proximos?|futuros?)\s+(?:trimestres?|anos?|exercicios?)"
            rf"\b.{{0,50}}{_ALVO}"
        ),
        "pergunta sobre resultado em período futuro",
    ),
    (
        re.compile(
            rf"\b(?:proje\w+|previsao|previsoes|estimativa\w*|expectativa\w*|"
            rf"probabilidade|chance\w*|risco)\b.{{0,40}}{_ALVO}"
        ),
        "pedido de projeção, probabilidade ou estimativa de resultado",
    ),
    (
        re.compile(
            r"\b(?:continuar\w*|seguir\w*|permanecer\w*|manter\w*)\s+"
            r"(?:no|em|com)\s+(?:prejuizo|lucro)"
        ),
        "pergunta sobre persistência futura do resultado",
    ),
)


def detectar_pergunta_prospectiva(texto: str) -> Achado | None:
    """Primeiro padrão prospectivo encontrado, ou ``None``.

    Devolve um `Achado` com a mesma forma dos scanners de `src.seguranca` para
    que a interface e os logs tratem a rota como qualquer outra decisão
    rastreável — não como um `if` escondido no meio da geração.
    """
    if not isinstance(texto, str) or not texto:
        return None
    normalizado = remover_acentos(texto).casefold()
    for padrao, detalhe in _PADROES_PROJECAO:
        if padrao.search(normalizado):
            return Achado(
                scanner=SCANNER_PROJECAO,
                subtipo=SUBTIPO_PROJECAO,
                detalhe=detalhe,
                ancora_legal=RESOLUCAO_ANALISE,
            )
    return None


# --------------------------------------------------------------------------- #
# Panorama (artefato calculado offline)
# --------------------------------------------------------------------------- #


class PanoramaIndisponivelError(RuntimeError):
    """Artefato do panorama ausente ou malformado.

    Falha fechada de propósito (RNF03): sem o artefato a rota não tem o que
    dizer de agregado, e responder sem ele seria degradar em silêncio.
    """


class PrevisaoPorEmissorDesabilitadaError(RuntimeError):
    """Pediram escore por emissor com a RN07 no modo público."""


@dataclass(frozen=True)
class FaixaDePorte:
    """Uma linha do regime de risco por porte — retrospectiva, sem emissor."""

    rotulo: str
    limite_inferior_reais: float
    instituicao_financeira: bool
    n_observacoes: int
    taxa_prejuizo: float


@dataclass(frozen=True)
class Panorama:
    """Fotografia agregada do painel, calculada offline.

    Tudo aqui é estatística de conjunto ou taxa histórica. Nenhum campo permite
    reconstruir o escore de uma companhia — ver `_agregado_seguro`.
    """

    trimestre_referencia: str
    n_companhias_avaliadas: int
    #: Contagem acima de um limiar ABSOLUTO (o dobro da taxa-base). É o número
    #: publicável: varia de trimestre para trimestre e diz algo sobre o
    #: mercado. `n_no_decil_superior` NÃO serve para isso — é sempre 10% de
    #: `n_companhias_avaliadas` por definição de decil, e publicá-lo como
    #: resultado do modelo seria tautologia com cara de medição (achado da
    #: auditoria de 2026-08-24).
    n_acima_do_dobro_da_base: int
    limiar_dobro_da_base: float
    taxa_base_painel: float
    n_no_decil_superior: int = 0
    faixas_de_porte: tuple[FaixaDePorte, ...] = ()
    n_observacoes_treino: int = 0
    fracao_nao_financeira_treino: float = 0.0
    auc_walk_forward: float | None = None
    alvo: str = "prejuízo em T+1 e T+2"

    @property
    def fracao_acima_do_dobro(self) -> float:
        if not self.n_companhias_avaliadas:
            return 0.0
        return self.n_acima_do_dobro_da_base / self.n_companhias_avaliadas


def carregar_panorama(caminho: Path | str = CAMINHO_PANORAMA) -> Panorama:
    """Lê o artefato agregado. Levanta se faltar — nunca devolve panorama vazio."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise PanoramaIndisponivelError(
            f"panorama do modelo ausente em {caminho}. Gere com "
            "`python -m scripts.gerar_panorama_modelo --painel "
            "artefatos/cvm_treino.duckdb` (custo zero, roda offline)."
        )
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        faixas = tuple(
            FaixaDePorte(**faixa) for faixa in dados.pop("faixas_de_porte", [])
        )
        return Panorama(faixas_de_porte=faixas, **dados)
    except (json.JSONDecodeError, TypeError, ValueError) as erro:
        raise PanoramaIndisponivelError(
            f"panorama do modelo malformado em {caminho}: {erro}"
        ) from erro


def carregar_escores(
    caminho: Path | str = CAMINHO_ESCORES,
) -> Mapping[str, float]:
    """Escores por `cd_cvm`, para o modo local. Fora do Git de propósito.

    O arquivo agregado é publicável; este não é. Manter os dois separados é o
    que permite ao deploy público não ter sequer o dado que a RN07 proíbe
    expor, em vez de tê-lo e prometer não usar.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        raise PanoramaIndisponivelError(
            f"escores por companhia ausentes em {caminho}. São gerados por "
            "`scripts/gerar_panorama_modelo.py --com-escores` e ficam fora do "
            "Git; o modo público não precisa deles."
        )
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return {str(cd): float(valor) for cd, valor in dados.get("escores", {}).items()}


def _agregado_seguro(panorama: Panorama, n_companhias_do_recorte: int) -> bool:
    """O agregado pode ser publicado sem permitir dedução por eliminação?

    Duas condições, e as duas são alcançáveis de verdade:

    1. **Recorte grande.** Só se publica o agregado do painel inteiro (centenas
       de companhias), nunca a contagem de um recorte estreito. "0 das 13
       instituições financeiras estão acima do limiar" revelaria o estado de
       cada uma delas.
    2. **Contagem não-extrema.** `n_acima_do_dobro_da_base` é contagem contra
       limiar ABSOLUTO, então 0 e "todas" são valores possíveis — e nos dois a
       dedução por eliminação funciona. Aí o bloco é suprimido.

    A versão anterior desta guarda testava `n_no_decil_superior`, que por
    definição de decil nunca é 0 nem o total: a condição era inalcançável e a
    proteção era ilusória. Corrigido depois da auditoria de 2026-08-24.
    """
    if n_companhias_do_recorte < 30:
        return False
    return 0 < panorama.n_acima_do_dobro_da_base < panorama.n_companhias_avaliadas


# --------------------------------------------------------------------------- #
# Resposta
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RespostaProjecao:
    """Resposta da rota prospectiva, com o rastro da decisão."""

    texto: str
    achado: Achado
    expos_escore_por_emissor: bool
    blocos: tuple[str, ...] = ()
    escore: float | None = None
    metadados: dict[str, object] = field(default_factory=dict)

    def como_dicionario(self) -> dict[str, object]:
        return {
            "scanner": self.achado.scanner,
            "subtipo": self.achado.subtipo,
            "ancora_legal": self.achado.ancora_legal,
            "expos_escore_por_emissor": self.expos_escore_por_emissor,
            "blocos": list(self.blocos),
            "escore": self.escore,
            **self.metadados,
        }


_CABECALHO_RECUSA = (
    "Não projeto resultado de instituição nomeada. Juízo prospectivo sobre "
    "emissor identificado é análise de valores mobiliários na acepção da "
    "{ancora} — a mesma fronteira pela qual recuso pedidos de recomendação de "
    "compra. O modelo preditivo deste projeto roda offline e não responde por "
    "companhia (RN07)."
)


def _pct(fracao: float, casas: int = 1) -> str:
    """Percentual na convenção pt-BR — vírgula decimal.

    O projeto já trata isso como erro de correção, não de estética: uma
    resposta financeira que troca o separador decimal conforme a máquina é a
    definição de número plausível e errado (ver `cobertura.formatar_reais`).
    """
    return f"{fracao * 100:.{casas}f}".replace(".", ",") + "%"


def _milhar(n: int) -> str:
    """Agrupamento de milhar pt-BR, feito à mão.

    `locale` pt_BR pode não estar instalado no contêiner, e número financeiro
    que troca separador conforme a máquina é a definição de valor plausível e
    errado — mesma razão de `cobertura.formatar_reais`.
    """
    texto, grupos = str(int(n)), []
    while len(texto) > 3:
        grupos.insert(0, texto[-3:])
        texto = texto[:-3]
    grupos.insert(0, texto)
    return ".".join(grupos)


def _bloco_historico(
    denom_social: str,
    cd_cvm: str,
    trimestres: Sequence[str],
    n_prejuizos: int | None,
    n_prejuizos_derivados: int | None = None,
) -> str:
    """Janela e contagem de prejuízos, com a RN10 respeitada.

    `n_prejuizos` conta **só trimestres arquivados**. O 4º trimestre não existe
    como ITR e é derivado por aritmética (DFP anual − ITR acumulado do 3T) —
    no painel carregado ele responde por 420 de 435 linhas do 4T2025. Somar
    derivado ao arquivado e chamar o total de "prejuízo consolidado" é
    exatamente o que a RN10 proíbe, então os dois saem separados.

    Os trimestres precisam chegar **já ordenados por `ordinal_trimestre`**;
    ordenados como texto, `[0]` e `[-1]` publicam uma janela errada.
    """
    if not trimestres:
        return (
            f"**Histórico arquivado — {denom_social} (CD_CVM {cd_cvm})**\n"
            "A companhia não tem trimestres no painel CVM carregado."
        )
    linha = (
        f"**Histórico arquivado — {denom_social} (CD_CVM {cd_cvm})**\n"
        f"{len(trimestres)} trimestres no painel CVM "
        f"({trimestres[0]}–{trimestres[-1]})"
    )
    if n_prejuizos is None:
        return linha + "."
    if n_prejuizos == 0:
        linha += ", **nenhum com prejuízo em trimestre arquivado**"
    else:
        linha += f", **{n_prejuizos} com prejuízo em trimestre arquivado**"
    if n_prejuizos_derivados:
        linha += (
            f", mais {n_prejuizos_derivados} em trimestre **derivado** "
            "(RN10: o 4T não existe como ITR e sai de DFP anual − ITR "
            "acumulado do 3T)"
        )
    return linha + "."


def _bloco_regime(panorama: Panorama, financeira: bool | None) -> str:
    faixas = [
        faixa
        for faixa in panorama.faixas_de_porte
        if financeira is None or faixa.instituicao_financeira == financeira
    ]
    if not faixas:
        return ""
    titulo = "**Regime de risco por porte** (retrospectivo, painel completo)"
    linhas = [
        f"| {faixa.rotulo} | {faixa.n_observacoes} | {_pct(faixa.taxa_prejuizo)} |"
        for faixa in faixas
    ]
    return (
        f"{titulo}\n\n| Porte | Trimestres | Com prejuízo |\n|---|---|---|\n"
        + "\n".join(linhas)
    )


def _bloco_panorama(panorama: Panorama) -> str:
    """Agregado contra limiar absoluto — não contra o decil.

    "N no decil superior" seria sempre 10% do painel e não diria nada sobre o
    trimestre. A contagem acima do dobro da taxa-base varia e informa.
    """
    linha = (
        f"**Panorama do mercado — {panorama.trimestre_referencia}**\n"
        f"De {panorama.n_companhias_avaliadas} companhias avaliadas, "
        f"**{panorama.n_acima_do_dobro_da_base}** "
        f"({_pct(panorama.fracao_acima_do_dobro)}) receberam escore acima do "
        f"dobro da taxa-base do painel (limiar "
        f"{_pct(panorama.limiar_dobro_da_base)}). Taxa-base observada: "
        f"{_pct(panorama.taxa_base_painel)} — alvo: {panorama.alvo}."
    )
    if panorama.auc_walk_forward is not None:
        linha += (
            "\nDesempenho do modelo que produziu esses escores: ROC-AUC "
            + f"{panorama.auc_walk_forward:.3f}".replace(".", ",")
            + " em validação walk-forward."
        )
    return linha


def _bloco_escore(
    denom_social: str, escore: float, panorama: Panorama, faixa: FaixaDePorte | None
) -> str:
    linhas = [
        f"**Sinal do modelo — {denom_social} · USO INTERNO, NÃO PUBLICÁVEL**",
        f"Escore estimado para {panorama.alvo}: **{_pct(escore)}**.",
    ]
    if faixa is not None:
        # A comparação com a taxa-base é o que impede o analista de ler o
        # escore como informação sobre a companhia quando ele é, em boa parte,
        # informação sobre a faixa de porte.
        linhas.append(
            f"Taxa-base histórica do porte ({faixa.rotulo}): "
            f"**{_pct(faixa.taxa_prejuizo)}** — se o escore está perto disso, "
            "o modelo está repetindo o regime, não dizendo algo sobre esta "
            "companhia."
        )
    linhas.append(
        "⚠️ **Fora de domínio:** o modelo foi treinado em "
        f"{_milhar(panorama.n_observacoes_treino)} observações, "
        f"{_pct(panorama.fracao_nao_financeira_treino, 0)} delas de companhias "
        "não financeiras, cuja estrutura patrimonial difere da de um banco."
    )
    linhas.append(
        "⚠️ **Não é recomendação de investimento** e não substitui análise. "
        "Se este número for para relatório publicado, a responsabilidade e as "
        "divulgações são do analista (Res. CVM 20/2021)."
    )
    return "\n".join(linhas)


def responder_projecao(
    pergunta: str,
    *,
    denom_social: str,
    cd_cvm: str,
    trimestres_painel: Sequence[str] = (),
    n_prejuizos: int | None = None,
    n_prejuizos_derivados: int | None = None,
    instituicao_financeira: bool | None = None,
    ativo_total: float | None = None,
    panorama: Panorama,
    previsao_por_emissor_habilitada: bool = False,
    escores: Mapping[str, float] | None = None,
    achado: Achado | None = None,
) -> RespostaProjecao:
    """Monta a resposta da rota prospectiva conforme o modo.

    `previsao_por_emissor_habilitada=False` (padrão, instância pública) devolve
    recusa fundamentada mais os três blocos defensáveis. `True` acrescenta o
    escore do emissor, e só ele muda entre os dois modos — o resto da resposta
    é idêntico, para que o analista veja exatamente o que o público veria.
    """
    achado = achado or detectar_pergunta_prospectiva(pergunta)
    if achado is None:
        raise ValueError(
            "responder_projecao chamada para pergunta que não é prospectiva; "
            "use detectar_pergunta_prospectiva antes de rotear"
        )

    faixa = _faixa_da_companhia(panorama, instituicao_financeira, ativo_total)
    blocos = [_CABECALHO_RECUSA.format(ancora=achado.ancora_legal)]
    nomes = ["recusa"]

    blocos.append(
        _bloco_historico(
            denom_social,
            cd_cvm,
            trimestres_painel,
            n_prejuizos,
            n_prejuizos_derivados,
        )
    )
    nomes.append("historico")

    regime = _bloco_regime(panorama, instituicao_financeira)
    if regime:
        blocos.append(regime)
        nomes.append("regime_por_porte")

    if _agregado_seguro(panorama, panorama.n_companhias_avaliadas):
        blocos.append(_bloco_panorama(panorama))
        nomes.append("panorama")

    escore: float | None = None
    if previsao_por_emissor_habilitada:
        if escores is None:
            raise PrevisaoPorEmissorDesabilitadaError(
                "previsão por emissor habilitada mas nenhum escore foi "
                "carregado; use carregar_escores() ou desligue a opção"
            )
        escore = escores.get(cd_cvm)
        if escore is None:
            blocos.append(
                f"**Sinal do modelo — {denom_social}**\n"
                "Sem escore para esta companhia no trimestre de referência "
                f"({panorama.trimestre_referencia}): ela não tem as features "
                "completas exigidas pelo painel."
            )
            nomes.append("escore_ausente")
        else:
            # A recusa sai do texto quando o modo autoriza a resposta: manter o
            # parágrafo de recusa ao lado do número seria contraditório.
            blocos[0] = (
                "**Modo local/autenticado.** A instância pública recusaria esta "
                f"pergunta pela {achado.ancora_legal} e pela RN07; aqui o "
                "escore é exibido para conferência interna do analista."
            )
            nomes[0] = "aviso_modo_local"
            blocos.append(_bloco_escore(denom_social, escore, panorama, faixa))
            nomes.append("escore_por_emissor")

    return RespostaProjecao(
        texto="\n\n".join(bloco for bloco in blocos if bloco),
        achado=achado,
        expos_escore_por_emissor=escore is not None,
        blocos=tuple(nomes),
        escore=escore,
        metadados={
            "cd_cvm": cd_cvm,
            "trimestre_referencia": panorama.trimestre_referencia,
        },
    )


def _faixa_da_companhia(
    panorama: Panorama,
    instituicao_financeira: bool | None,
    ativo_total: float | None = None,
) -> FaixaDePorte | None:
    """Faixa de porte da companhia — sem inventar porte quando ele falta.

    Com o ativo em mãos, escolhe a faixa cujo piso a companhia alcança. Sem
    ele, devolve a faixa do setor só se houver exatamente uma; caso contrário
    devolve ``None`` e o bloco de escore sai sem a comparação. Comparar com a
    faixa errada seria pior que não comparar: o porte é justamente o que separa
    0,6% de 29,6% em instituição financeira.
    """
    if instituicao_financeira is None:
        return None
    candidatas = [
        faixa
        for faixa in panorama.faixas_de_porte
        if faixa.instituicao_financeira == instituicao_financeira
    ]
    if not candidatas:
        return None
    if ativo_total is None:
        return candidatas[0] if len(candidatas) == 1 else None
    alcancadas = [
        faixa for faixa in candidatas if ativo_total >= faixa.limite_inferior_reais
    ]
    if not alcancadas:
        return None
    return max(alcancadas, key=lambda faixa: faixa.limite_inferior_reais)
