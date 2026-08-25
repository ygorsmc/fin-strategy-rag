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
   deduzir o estado daquele banco. Nenhum agregado **setorial** é calculado —
   essa é a primeira linha e continua valendo.

   Desde 2026-08-25 o panorama carrega, sim, um agregado do **trimestre
   corrente** (recorte `prejuizo_em_t = 0`, centenas de companhias), então a
   frase anterior — "nenhum agregado do trimestre corrente chega a ser
   calculado" — deixou de descrever o desenho e foi corrigida aqui. A guarda
   passou a ser a que faz o trabalho, e por isso ela é sobre FRAÇÃO
   (`BANDA_PUBLICAVEL`) e não sobre contagem: barrar só 0 e "todas" deixava
   passar 2 de 286, que entrega a mesma dedução que 0 de 286.
   `_agregado_seguro` guarda o agregado do painel inteiro pela mesma lógica.
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
    """Uma linha do regime de risco por porte — retrospectiva, sem emissor.

    **Não há recorte setorial aqui, e a ausência é uma retratação (2026-08-25).**
    A primeira versão publicava a tabela separada em "instituição financeira" ×
    "demais", com um gradiente de 0,6% a 29,6% que parecia mostrar o porte
    funcionando como interruptor em banco. Duas auditorias independentes
    derrubaram o achado:

    * a flag de origem (`companhias.is_banco`) significa "usa plano de contas
      de instituição financeira", e entre as 41 entidades marcadas estavam
      GP Investments (private equity), CELGPAR (holding de energia) e Sul 116
      **em liquidação** — **42 dos 49 eventos positivos (85,7%)** do recorte
      vinham de nove entidades que não são banco;
    * limpo o universo sobram **7 eventos**, contra o mínimo de 20 que o
      próprio módulo exige em `desempenho_por_recorte`. Com essa amostra não se
      distingue AUC 0,70 de 0,50 (Hanley & McNeil, 1982);
    * e o teste contínuo mata o efeito: correlação de Spearman entre ativo e
      prejuízo, em bancos de verdade **excluindo os ≥ R$ 500 bi**, é
      ρ = −0,046 (p = 0,83). Fora do topo, porte não prediz nada — o que
      sobrava era uma variável dummy para cinco bancos.

    Os números acima são **reproduzíveis**, e isso é parte da correção: a
    primeira versão desta retratação existia só em prosa, enquanto o número
    retratado tinha artefato versionado. Rode
    `python -m scripts.auditar_recorte_is_banco` — saída em
    `artefatos/modelo/auditoria_is_banco.json`, custo zero.

    O que resta e se sustenta é a tabela do **painel inteiro**, sem recorte de
    setor, com amostra de verdade em cada faixa.
    """

    rotulo: str
    limite_inferior_reais: float
    n_observacoes: int
    taxa_prejuizo: float


@dataclass(frozen=True)
class TrimestreCorrente:
    """Escoragem do trimestre mais recente FECHADO — o que ainda não tem rótulo.

    O bloco existe porque o panorama publicava como "referência" um trimestre
    dois atrás do último dado disponível: o alvo exige T+1 e T+2, e a junção
    que monta o painel descarta quem não os tem. Correto para avaliar, inútil
    para usar — a companhia sobre a qual se quer prever é justamente a sem
    futuro ainda.

    **Restrito a quem está hoje lucrativo, e o denominador vem junto.** Sem o
    recorte, o topo da ordenação é 97,1% composto de companhias já em prejuízo
    em T (decomposição de 2026-08-25) — informação que o leitor tira da própria
    demonstração, sem modelo. `n_ja_em_prejuizo` fica publicado ao lado
    exatamente para que ninguém leia a contagem reduzida como melhora.

    Não há AUC aqui, e não pode haver: o rótulo não existe. O AUC do panorama
    é o do walk-forward, medido em trimestres que já fecharam.
    """

    trimestre: str
    n_hoje_lucrativas: int
    n_ja_em_prejuizo: int
    n_acima_do_limiar: int
    limiar: float

    @property
    def fracao_sinalizada(self) -> float:
        if not self.n_hoje_lucrativas:
            return 0.0
        return self.n_acima_do_limiar / self.n_hoje_lucrativas


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
    #: Escoragem do trimestre ainda sem rótulo. `None` quando o painel não
    #: alcança um trimestre fechado além da janela do alvo.
    trimestre_corrente: TrimestreCorrente | None = None

    @property
    def trimestre_dos_escores(self) -> str:
        """Qual trimestre o escore por emissor descreve.

        Não é `trimestre_referencia`: este é o último fold AVALIADO (tem
        rótulo, serve para o AUC), enquanto o escore por emissor passou a ser
        do trimestre corrente, que é o único ainda prospectivo.
        """
        if self.trimestre_corrente is not None:
            return self.trimestre_corrente.trimestre
        return self.trimestre_referencia

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
        bruto_corrente = dados.pop("trimestre_corrente", None)
        corrente = (
            TrimestreCorrente(**bruto_corrente) if bruto_corrente else None
        )
        return Panorama(
            faixas_de_porte=faixas, trimestre_corrente=corrente, **dados
        )
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


def recusa_de_ultimo_recurso(achado: Achado, *, motivo: str) -> RespostaProjecao:
    """Recusa da RN07 que NÃO depende de artefato, painel ou índice nenhum.

    Fecha o buraco que a auditoria de 2026-08-25 apontou: a rota prospectiva
    vivia só no ramo do Streamlit e "sumia" quando o panorama ou o painel não
    estavam presentes — no deploy enxuto (RNF12), por exemplo. Sumir significa
    a pergunta cair no caminho normal e o LLM projetar resultado de emissor
    nomeado, que é exatamente o que a RN07 proíbe. Degradação de uma camada
    acessória não pode virar permissão.

    A recusa aqui é deliberadamente **pobre**: só a fronteira legal e o que
    falta. Nenhum número — sem os artefatos não há número conferível, e
    preencher a recusa com valor de memória paramétrica seria trocar uma
    violação da RN07 por uma da RN02.
    """
    texto = (
        _CABECALHO_RECUSA.format(ancora=achado.ancora_legal)
        + "\n\n"
        + f"Também não consigo entregar o material agregado que normalmente "
        f"acompanha esta recusa ({motivo}). Sem ele, a resposta seria número "
        f"sem lastro — prefiro declarar a ausência."
    )
    return RespostaProjecao(
        texto=texto,
        achado=achado,
        expos_escore_por_emissor=False,
        blocos=("recusa",),
        metadados={"degradado": True, "motivo_degradacao": motivo},
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


def _bloco_regime(panorama: Panorama) -> str:
    """Regime por porte do PAINEL INTEIRO — sem recorte setorial.

    Ver `FaixaDePorte` para a retratação: a versão separada por setor não
    sobreviveu à auditoria e foi retirada, não corrigida.
    """
    if not panorama.faixas_de_porte:
        return ""
    linhas = [
        f"| {faixa.rotulo} | {faixa.n_observacoes} | {_pct(faixa.taxa_prejuizo)} |"
        for faixa in panorama.faixas_de_porte
    ]
    return (
        "**Regime de risco por porte** (retrospectivo, painel completo, todos "
        "os setores)\n\n| Porte | Trimestres | Com prejuízo |\n|---|---|---|\n"
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


#: Banda em que a contagem do trimestre corrente pode ser publicada.
#:
#: Endurecida em 2026-08-25 depois de a auditoria mostrar que a guarda anterior
#: — que só barrava 0 e "todas" — deixava passar **2 de 286**, que é zero para
#: qualquer efeito prático: publicar isso ao lado de uma pergunta sobre um
#: emissor entrega, com 99,3% de confiança, que aquele emissor está abaixo do
#: limiar. A fronteira aritmética não protegia a propriedade que dizia
#: proteger. A banda é sobre FRAÇÃO, não sobre contagem.
BANDA_PUBLICAVEL = (0.05, 0.95)


def _bloco_trimestre_corrente(panorama: Panorama) -> str:
    """O trimestre que ainda não fechou o rótulo — agregado, nunca por emissor.

    Suprimido quando o recorte é pequeno ou a fração sinalizada cai fora de
    `BANDA_PUBLICAVEL`, pela mesma razão de `_agregado_seguro`: "quase ninguém
    de N" ao lado de uma pergunta sobre uma companhia revela o estado dela por
    eliminação tão bem quanto "0 de N".

    **Consequência assumida:** com o painel de 2026-08-25 (2 de 286 em
    `1T2026`, 0,7%) este bloco NÃO é publicado. A escoragem do trimestre
    corrente segue valendo pelo escore por emissor no modo local, que é o
    consumidor principal dela; o agregado público volta a aparecer num
    trimestre em que mais companhias sejam sinalizadas. Guarda que nunca
    dispara é guarda decorativa — esta dispara.
    """
    corrente = panorama.trimestre_corrente
    if corrente is None or corrente.n_hoje_lucrativas < 30:
        return ""
    piso, teto = BANDA_PUBLICAVEL
    if not piso <= corrente.fracao_sinalizada <= teto:
        return ""
    return (
        f"**Trimestre corrente — {corrente.trimestre}** (escorado, ainda sem "
        "resultado conhecido)\n"
        f"Entre as **{corrente.n_hoje_lucrativas}** companhias que fecharam "
        f"{corrente.trimestre} **com lucro**, "
        f"**{corrente.n_acima_do_limiar}** "
        f"({_pct(corrente.fracao_sinalizada)}) receberam escore acima de "
        f"{_pct(corrente.limiar)} para {panorama.alvo}.\n"
        f"Outras {corrente.n_ja_em_prejuizo} companhias do trimestre já estão "
        "em prejuízo e ficam fora desta contagem de propósito: para elas o "
        "escore alto repete o que a própria demonstração já diz.\n"
        "Este bloco não tem AUC porque o resultado ainda não aconteceu — o "
        "desempenho citado acima é de trimestres já fechados."
    )


def _bloco_escore(
    denom_social: str, escore: float, panorama: Panorama, faixa: FaixaDePorte | None
) -> str:
    linhas = [
        f"**Sinal do modelo — {denom_social} · USO INTERNO, NÃO PUBLICÁVEL**",
        f"Escore estimado para {panorama.alvo}, a partir de "
        f"{panorama.trimestre_dos_escores}: **{_pct(escore)}**.",
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

    faixa = _faixa_da_companhia(panorama, ativo_total)
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

    regime = _bloco_regime(panorama)
    if regime:
        blocos.append(regime)
        nomes.append("regime_por_porte")

    if _agregado_seguro(panorama, panorama.n_companhias_avaliadas):
        blocos.append(_bloco_panorama(panorama))
        nomes.append("panorama")

    corrente = _bloco_trimestre_corrente(panorama)
    if corrente:
        blocos.append(corrente)
        nomes.append("trimestre_corrente")

    escore: float | None = None
    if previsao_por_emissor_habilitada:
        if escores is None:
            raise PrevisaoPorEmissorDesabilitadaError(
                "previsão por emissor habilitada mas nenhum escore foi "
                "carregado; use carregar_escores() ou desligue a opção"
            )
        escore = escores.get(cd_cvm)
        if escore is None:
            # O trimestre certo a citar é o dos ESCORES, não o do panorama:
            # desde 2026-08-25 o escore é do trimestre corrente e o panorama
            # continua ancorado no último fold avaliado. Citar o do panorama
            # mandaria o analista conferir o trimestre errado.
            blocos.append(
                f"**Sinal do modelo — {denom_social}**\n"
                "Sem escore para esta companhia no trimestre escorado "
                f"({panorama.trimestre_dos_escores}): ela não tem as features "
                "completas exigidas pelo painel, ou já estava em prejuízo no "
                "próprio trimestre e ficou fora do recorte prospectivo."
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
            # Os dois, separados, porque desde 2026-08-25 são trimestres
            # DIFERENTES: o de referência é o último fold avaliado (tem AUC),
            # o dos escores é o corrente (é o que a resposta cita). Gravar só
            # o primeiro carimbava o escore de 1T2026 como se fosse 3T2025 no
            # log da RNF08 — o mesmo defeito que o texto já tinha corrigido,
            # sobrevivendo na parte legível por máquina.
            "trimestre_dos_escores": panorama.trimestre_dos_escores,
        },
    )


def _faixa_da_companhia(
    panorama: Panorama, ativo_total: float | None = None
) -> FaixaDePorte | None:
    """Faixa de porte da companhia — sem inventar porte quando ele falta.

    Sem o ativo em mãos devolve ``None`` e o bloco de escore sai sem a
    comparação com a taxa-base, o que é preferível a comparar com a faixa
    errada. Não há mais escolha por setor: ver a retratação em `FaixaDePorte`.
    """
    if ativo_total is None or not panorama.faixas_de_porte:
        return None
    alcancadas = [
        faixa
        for faixa in panorama.faixas_de_porte
        if ativo_total >= faixa.limite_inferior_reais
    ]
    if not alcancadas:
        return None
    return max(alcancadas, key=lambda faixa: faixa.limite_inferior_reais)
