"""Piloto documental B-DFC-01J — juros de captação (J) no consolidado IFRS.

Executa o piloto acordado em `resultados/debate_bancos_dfc_2026-09-09.md` e
detalhado em `resultados/plano_piloto_bancos_dfc_2026-09-09.md`: verificar se J
— juros por competência dos instrumentos de captação incluídos no contrato — é
**identificável e reconstruível** para cinco bancos entre 2024T1 e 2025T1.

**Não é treino, não é backtest e não produz observação supervisionada.** É
auditoria documental: cada cifra aceita carrega fonte, página, coluna, unidade,
período e perímetro, e cada decisão semântica carrega motivo.

Três decisões de desenho que fecham modos conhecidos de errar:

1. **Aritmética em `Decimal`, nunca `float`.** `normalizar_numero_ptbr` de
   `src/normalizacao.py` devolve `float` e aplica multiplicadores de escala
   ("mil"/"milhões") — contrato correto para prosa de release, errado para
   reconciliar tabela em milhares de reais. Erro binário de representação em
   soma de bilhões destrói a conferência que é o ponto do piloto.
2. **Ausência de composição não vira zero nem estimativa.** Quando as parcelas
   do contrato são identificadas e sobra residual sem composição (o "Outras
   despesas de juros" do BB), J sai como **intervalo declarado**, nunca ponto.
   Quando nem isso existe — porque a fonte só traz agregado que mistura item
   fora do contrato (atuarial no Santander) ou porque as rubricas são resultado
   líquido em vez de juros (BTG) — J fica **não identificado e sem intervalo**:
   somar rubricas não identificadas produziria um "limite" que soma duas
   decomposições do mesmo total.
3. **Guarda de escopo antes de abrir arquivo.** O holdout 2T2026 é barrado por
   caminho e por período antes de qualquer leitura ou requisição — não depois
   de extrair número.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence

RAIZ = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = "1.0.0"
VERSAO_CONTRATO_J = "B-DFC-01J/2026-09-09"

#: Os cinco bancos do piloto. Chave é `CD_CVM` com zeros preservados (RN11 —
#: companhia resolve por código de registro, nunca por nome ou ticker).
BANCOS: dict[str, str] = {
    "000906": "BCO BRADESCO S.A.",
    "001023": "BCO BRASIL S.A.",
    "019348": "ITAU UNIBANCO HOLDING S.A.",
    "020532": "BCO SANTANDER (BRASIL) S.A.",
    "022616": "BCO BTG PACTUAL S.A.",
}

#: Períodos principais, na convenção `AAAATN` que o plano fixou para artefatos
#: novos. Campos locais antigos usam `1T2024`; a tradução é explícita, nunca
#: inferida da capa do PDF (§ MEMORY: capa não é fonte confiável de período).
PERIODOS: dict[str, tuple[date, date]] = {
    "2024T1": (date(2024, 1, 1), date(2024, 3, 31)),
    "2024T2": (date(2024, 4, 1), date(2024, 6, 30)),
    "2024T3": (date(2024, 7, 1), date(2024, 9, 30)),
    "2024T4": (date(2024, 10, 1), date(2024, 12, 31)),
    "2025T1": (date(2025, 1, 1), date(2025, 3, 31)),
}

#: Períodos de apoio: aparecem como coluna nas fontes e sustentam derivação,
#: mas **não** entram no denominador de 25 pacotes do piloto.
#:
#: A lista é GERADA para 2018–2026 porque a extensão da janela (§ relatório de
#: 2026-09-09) lê documentos de sete anos, e cada um traz colunas comparativas
#: de anos anteriores. Uma lista fixa nos cinco trimestres do piloto recusava
#: 13 documentos válidos com a mensagem "fora do escopo" — a guarda estava
#: certa, o universo é que era estreito. `PERIODOS` continua sendo só os cinco
#: do piloto: o denominador congelado não muda.
def _gerar_periodos_de_apoio() -> dict[str, tuple[date, date]]:
    fins = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    apoio: dict[str, tuple[date, date]] = {}
    # Desde 2016: o anual de 2019 traz coluna comparativa de 2017.
    for ano in range(2016, 2027):
        for trimestre, (mes, dia) in fins.items():
            rotulo = f"{ano}T{trimestre}"
            if rotulo in PERIODOS or rotulo in PERIODOS_PROIBIDOS:
                continue
            inicio = date(ano, 3 * (trimestre - 1) + 1, 1)
            apoio[rotulo] = (inicio, date(ano, mes, dia))
        apoio[f"{ano}S1"] = (date(ano, 1, 1), date(ano, 6, 30))
        apoio[f"{ano}M9"] = (date(ano, 1, 1), date(ano, 9, 30))
        apoio[f"{ano}A"] = (date(ano, 1, 1), date(ano, 12, 31))
    return apoio


#: Multiplicador de cada unidade para reais. A unidade é propriedade da FONTE
#: (o cabeçalho da tabela declara "R$ mil" ou "Em milhões") e nunca é deduzida
#: de palavra solta no meio do texto: o Itaú publica em MILHÕES e os outros
#: quatro bancos em MILHARES. Confundir os dois erra por mil vezes — é a
#: troca `MIL`↔`UNIDADE` que invalidou a rodada A do CAND-04 (§3.11).
MULTIPLICADOR_UNIDADE: dict[str, int] = {
    "milhares_de_reais": 1_000,
    "milhoes_de_reais": 1_000_000,
}

#: Barrado por contrato do piloto. O 2T2026 é o único dado que nenhum ajuste
#: deste projeto viu; gastá-lo aqui destruiria a única coisa que ele tem. Vale
#: também para a extensão: o gerador de períodos de apoio nunca o inclui.
PERIODOS_PROIBIDOS = frozenset({"2026T2", "2T2026", "2026T3", "2026T4"})
CAMINHOS_PROIBIDOS = ("corpus/holdout_2T2026",)

PERIODOS_APOIO: dict[str, tuple[date, date]] = _gerar_periodos_de_apoio()


class ErroEscopo(RuntimeError):
    """Tentativa de sair do escopo fechado do piloto."""


class ErroExtracao(RuntimeError):
    """Falha ao localizar ou interpretar evidência documental."""


def verificar_caminho_permitido(caminho: Path | str) -> None:
    """Barra o holdout ANTES de abrir o arquivo.

    Guarda que só roda depois de ler já falhou uma vez neste projeto: recusar
    depois de gastar não é recusar (§3.6, `TestGuardaProfunda`).
    """
    texto = str(caminho).replace("\\", "/")
    for proibido in CAMINHOS_PROIBIDOS:
        if proibido in texto:
            raise ErroEscopo(
                f"Caminho {caminho} toca o holdout reservado ({proibido}). "
                "O piloto não abre, lista nem baixa esse material."
            )


def verificar_periodo_no_escopo(periodo: str) -> None:
    if periodo in PERIODOS_PROIBIDOS:
        raise ErroEscopo(
            f"Período {periodo} é o holdout reservado; fora do piloto."
        )
    if periodo not in PERIODOS and periodo not in PERIODOS_APOIO:
        raise ErroEscopo(
            f"Período {periodo} não pertence ao escopo fechado "
            f"({sorted(PERIODOS)}) nem aos períodos de apoio declarados."
        )


#: O piloto só escreve aqui. Qualquer outro destino seria mutação de produto,
#: que o plano §3.2 proíbe.
DESTINOS_PERMITIDOS = ("artefatos/b_dfc_01j",)


def verificar_destino_isolado(destino: Path | str) -> None:
    """Impede que a saída do piloto caia sobre artefato de produção."""
    texto = str(destino).replace("\\", "/").rstrip("/")
    if not any(texto.endswith(permitido) for permitido in DESTINOS_PERMITIDOS):
        raise ErroEscopo(
            f"Destino {destino} não é isolado. O piloto grava apenas em "
            f"{DESTINOS_PERMITIDOS}; escrever fora disso seria mutação de "
            "produto."
        )


def fim_do_periodo(periodo: str) -> date:
    if periodo in PERIODOS:
        return PERIODOS[periodo][1]
    return PERIODOS_APOIO[periodo][1]


def periodo_e_do_documento(periodo: str, periodo_documento: str) -> bool:
    """O período pertence à data-base do documento?

    A comparação é por **data de encerramento**, não por rótulo. No documento
    do 3T o trimestre isolado (`2024T3`) e o acumulado de nove meses
    (`2024M9`) encerram os dois em 30/09/2024: ambos são valores originais
    daquele arquivamento. Só as colunas que encerram em outra data — as de
    2023 — são comparativas. Comparar rótulos trataria o acumulado como
    reapresentado e jogaria fora a única evidência point-in-time que existe.
    """
    return fim_do_periodo(periodo) == fim_do_periodo(periodo_documento)


def pacote_id(cd_cvm: str, periodo: str) -> str:
    return f"{cd_cvm}-{periodo}"


def montar_escopo() -> list[dict[str, str]]:
    """Os 25 pacotes existem por construção, não por documento encontrado.

    Construir esta lista a partir dos documentos localizados esconderia
    exatamente a lacuna que o piloto precisa medir.
    """
    linhas = []
    for cd_cvm in sorted(BANCOS):
        for periodo in sorted(PERIODOS):
            inicio, fim = PERIODOS[periodo]
            linhas.append(
                {
                    "pacote_id": pacote_id(cd_cvm, periodo),
                    "cd_cvm": cd_cvm,
                    "emissor": BANCOS[cd_cvm],
                    "periodo": periodo,
                    "inicio": inicio.isoformat(),
                    "fim": fim.isoformat(),
                }
            )
    return linhas


# ---------------------------------------------------------------------------
# Fontes documentais declaradas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fonte:
    """Documento IFRS local, com identidade verificável por hash."""

    fonte_id: str
    cd_cvm: str
    arquivo: str
    hash_sha256: str
    periodo_documento: str
    tipo_documento: str
    base_contabil: str = "IFRS"
    perimetro: str = "consolidado"
    url: str = ""
    data_download: str = ""
    #: Onde o binário mora. O corpus `ifrs` é contrato congelado (§3.15); os
    #: documentos que o piloto baixou ficam em diretório próprio, fora do Git.
    diretorio: str = "corpus/ifrs/raw"
    #: Procedência do catálogo IPE da CVM, quando o documento veio de lá.
    #: `data_entrega` é a data em que o emissor ENTREGOU o documento à CVM —
    #: é ela, e não a data de download, que sustenta disponibilidade histórica.
    data_entrega: str = ""
    versao: int = 0
    protocolo: str = ""
    #: `pdftotext` devolve lixo quando a fonte do PDF não tem mapa de
    #: caracteres; nesses casos a leitura vem do cache de OCR já pago (RNF10),
    #: nunca de uma nova chamada paga.
    texto_por_ocr: bool = False

    @property
    def caminho(self) -> Path:
        return RAIZ / self.diretorio / self.arquivo

    @property
    def tem_procedencia_de_entrega(self) -> bool:
        """Documento recuperado por protocolo/versão, com data de entrega.

        É o que separa "sei quando isto ficou público" de "sei quando eu
        baixei". Sem os três — data, versão e protocolo — não há P3.
        """
        return bool(self.data_entrega and self.versao and self.protocolo)

    @property
    def caminho_ocr(self) -> Path:
        return RAIZ / "corpus" / "ifrs" / "ocr_documento" / f"{self.hash_sha256}.json"


@dataclass(frozen=True)
class Rubrica:
    """Uma linha de nota, com o tratamento que o contrato J lhe dá."""

    rotulo: str
    conceito: str
    #: `incluir` · `excluir` · `total` · `nao_identificado`
    tratamento: str
    motivo: str
    #: Rótulos alternativos, porque o emissor MUDA a redação entre anos. Medido:
    #: o Bradesco publica duas linhas de exclusão em 2024 ("Passivos de contatos
    #: de seguros" e "Provisões técnicas de capitalização") e UMA consolidada em
    #: 2023 ("Provisões técnicas de seguros, previdência e capitalização").
    alternativos: tuple[str, ...] = ()
    #: Rubrica que pode não existir naquele ano. É seguro tornar opcional
    #: **porque a conferência de fechamento existe**: se uma parcela sumir sem
    #: ser contada, a soma não fecha no total impresso e o P2 acusa. Sem essa
    #: rede, "opcional" seria porta para perder dinheiro em silêncio.
    obrigatoria: bool = True
    #: SÓ para `nao_identificado`: declara que a parcela de juros contida nesta
    #: rubrica é **demonstravelmente** entre zero e o valor publicado da linha.
    #: Isso exige que a linha seja de sinal único (só despesa) e que nenhum
    #: componente de sinal oposto possa compensar juros dentro dela.
    #:
    #: Default False, e o default é o ponto: uma linha que mistura juros com
    #: variação cambial ou valor justo **não** limita a parcela de juros, porque
    #: o câmbio tem os dois sinais e pode compensá-la. Achado F1 da revisão
    #: independente de 2026-09-10: com incluída −100, desconhecida +30 e total
    #: −70, o residual líquido dá "intervalo [70,100]", mas a desconhecida pode
    #: ser −20 de juros + 50 de câmbio, e então J = 120, FORA do intervalo.
    #: Limite que não se demonstra é limite inventado, e pior que ausência.
    limite_demonstravel: bool = False

    @property
    def rotulos(self) -> tuple[str, ...]:
        return (self.rotulo, *self.alternativos)


@dataclass(frozen=True)
class NotaExtraida:
    """Uma tabela de nota: página, colunas e rubricas a extrair."""

    fonte_id: str
    pagina_pdf: int
    pagina_impressa: str
    nota: str
    #: Ordem das colunas numéricas, da esquerda para a direita. Declarada a
    #: partir do cabeçalho impresso e conferida por identidade aritmética entre
    #: trimestre isolado e acumulado — nunca suposta.
    colunas: tuple[str, ...]
    rubricas: tuple[Rubrica, ...]
    unidade: str = "milhares_de_reais"
    #: Quantos números à esquerda NÃO são valores. O anual do Santander
    #: imprime a referência da nota ("32") antes das cifras; lê-la como valor
    #: deslocaria todas as colunas em uma casa e atribuiria 2024 ao lugar de
    #: 2023. Foi a guarda de contagem que expôs isso, não uma suposição.
    colunas_ignoradas_a_esquerda: int = 0
    #: Rótulo que abre a seção da tabela. Sem isso, "Total" casaria também com
    #: o total da seção de RECEITAS que a mesma nota publica logo acima —
    #: ambiguidade que devolveria receita no lugar de despesa. A busca por
    #: rubrica passa a valer só da seção para baixo.
    secao: str = ""
    #: Rótulo que FECHA a seção, inclusive. Necessário porque "Total" reaparece
    #: na seção seguinte da mesma página: delimitar só o início deixaria a
    #: rubrica ambígua e a guarda de unicidade recusaria a extração —
    #: corretamente. Nas notas de juros o fecho é o próprio "Total" da tabela,
    #: que é o limite natural da seção.
    secao_fim: str = ""


_INCLUIR = "incluir"
_EXCLUIR = "excluir"
_TOTAL = "total"
_NAO_IDENT = "nao_identificado"

#: Rubricas do BB. A nota decompõe a despesa de juros em três rubricas que
#: correspondem exatamente às famílias do contrato (depósitos/captação de
#: clientes, recursos de instituições financeiras, títulos emitidos) mais um
#: residual sem composição.
_RUBRICAS_BB = (
    Rubrica(
        "Despesas de juros",
        "despesa_juros_total",
        _TOTAL,
        "Total da nota; serve de conferência da soma das parcelas.",
    ),
    Rubrica(
        "Recursos de instituições financeiras",
        "juros_recursos_instituicoes_financeiras",
        _INCLUIR,
        "Captação junto a instituições financeiras: compromissadas, "
        "empréstimos e repasses recebidos — incluídos no contrato J.",
    ),
    Rubrica(
        "Recursos de clientes",
        "juros_recursos_clientes",
        _INCLUIR,
        "Depósitos e demais recursos de clientes — incluídos no contrato J.",
    ),
    # Prefixo, não o rótulo inteiro: no layout de quatro colunas do BB a
    # linha impressa quebra em "…de títulos e valores" / "mobiliários". O
    # prefixo é único na página e o texto realmente lido fica na evidência.
    Rubrica(
        "Recursos de emissões de títulos",
        "juros_titulos_emitidos",
        _INCLUIR,
        "Títulos de dívida emitidos, inclusive subordinados classificados "
        "como passivo — incluídos no contrato J.",
    ),
    Rubrica(
        "Outras despesas de juros",
        "juros_outras_sem_composicao",
        _NAO_IDENT,
        "A nota não abre a composição. Pode conter item do contrato e item "
        "fora dele; o contrato proíbe estimar a parcela ausente.",
    ),
)

#: Rubricas do BTG — **nenhuma serve como parcela de J, e a razão foi medida.**
#:
#: A nota 21 traz DUAS decomposições do MESMO total: uma por instrumento
#: (captação, depósitos, aceites, empréstimos) e outra por natureza (receitas
#: de juros, despesas de juros, mensuração a valor justo). Elas não são pai e
#: filhas.
#:
#: A soma das quatro linhas por instrumento fecha EXATAMENTE em "Despesas de
#: juros" no 2025T1 (14.052.043) e erra por R$ 6,5 bilhões no 2024T1
#: (10.098.636 contra 3.549.360). Uma soma fechar num período não prova a
#: semântica: as linhas por instrumento são **resultado líquido**, que embute
#: mensuração a valor justo — exatamente o que o contrato exclui. Tomá-las
#: como juros por competência produziria J plausível e errado, que é a classe
#: de falha que este projeto existe para combater.
_RUBRICAS_BTG = (
    Rubrica(
        "Despesas de juros",
        "despesa_juros_total_por_natureza",
        _NAO_IDENT,
        "Total por natureza, sem composição por instrumento. Não é possível "
        "separar o que é captação incluída no contrato do que não é.",
    ),
    Rubrica(
        "Captação no mercado",
        "resultado_liquido_captacao_mercado",
        _NAO_IDENT,
        "Resultado líquido por instrumento, não juros por competência: embute "
        "mensuração a valor justo, excluída pelo contrato. A soma das quatro "
        "linhas fecha no total por natureza em 2025T1 e diverge R$ 6,5 bi em "
        "2024T1 — a coincidência de um período não vira identidade.",
    ),
    Rubrica(
        "Depósitos",
        "resultado_liquido_depositos",
        _NAO_IDENT,
        "Resultado líquido por instrumento; ver motivo de "
        "`resultado_liquido_captacao_mercado`.",
    ),
    Rubrica(
        "Recursos de aceites e emissão de títulos",
        "resultado_liquido_titulos_emitidos",
        _NAO_IDENT,
        "Resultado líquido por instrumento; ver motivo de "
        "`resultado_liquido_captacao_mercado`.",
    ),
    Rubrica(
        "Empréstimos, repasses e passivos de arrendamentos",
        "resultado_liquido_emprestimos_repasses_e_arrendamentos",
        _NAO_IDENT,
        "Além de ser resultado líquido, junta empréstimos/repasses recebidos "
        "(incluídos) com passivos de arrendamento (excluídos), e o documento "
        "não divulga o juro de arrendamento em separado.",
    ),
)

#: Santander: a demonstração intermediária traz apenas o agregado
#: "Despesas com juros e similares", sem composição por instrumento.
_RUBRICAS_SANTANDER = (
    Rubrica(
        "Despesas com juros e similares",
        "despesa_juros_e_similares_total",
        _NAO_IDENT,
        "Agregado sem composição por instrumento. A nota de obrigações para "
        "fundos de pensão declara que planos de benefício definido são "
        "reconhecidos NESTA linha — componente atuarial que o contrato exclui, "
        "informado apenas qualitativamente. Mistura não separável.",
    ),
)

#: Rubricas do BRADESCO — a composição mais completa dos cinco bancos.
#:
#: A nota abre TODAS as fontes de despesa de juros, inclusive as que ficam
#: **fora** do contrato, cada uma com valor próprio. Isso é o que permite J
#: como PONTO em vez de intervalo: subtrair as exclusões é leitura de linha
#: publicada, não estimativa.
_RUBRICAS_BRADESCO = (
    Rubrica(
        "Total", "despesa_juros_total", _TOTAL,
        "Total da nota; confere a soma de todas as parcelas.",
    ),
    Rubrica(
        "- Depósitos interfinanceiros", "juros_depositos_interfinanceiros",
        _INCLUIR, "Depósitos interfinanceiros — captação incluída no contrato.",
    ),
    Rubrica(
        "- Captação no mercado aberto", "juros_captacao_mercado_aberto",
        _INCLUIR, "Operações compromissadas — incluídas no contrato.",
    ),
    Rubrica(
        "- Obrigações por empréstimos e repasses",
        "juros_emprestimos_e_repasses", _NAO_IDENT,
        "NÃO É JUROS POR COMPETÊNCIA, mesma classe do 'Recursos de Mercados "
        "Interbancários' do Itaú: no 2T2021 a linha vem CREDORA em "
        "+2.335.452 dentro de uma tabela cujo total é despesa "
        "(-9.652.884) — despesa de captação por competência não é crédito. "
        "É o MESMO trimestre em que a linha equivalente do Itaú virou "
        "credora, o que aponta a causa comum: valorização do real sobre "
        "captação em moeda estrangeira, e o Bradesco tem R$ 30,8 bi de "
        "investimentos no exterior. A evidência aqui é o crédito impresso e "
        "a coincidência de trimestre, NÃO o casamento de magnitude que se "
        "mediu no Itaú — a composição da rubrica por moeda não é publicada, "
        "que é justamente o motivo de não ser separável. Vira NÃO "
        "IDENTIFICADA; estimar a parcela cambial é proibido pelo contrato.",
    ),
    Rubrica(
        "- Poupança", "juros_poupanca", _INCLUIR,
        "Depósitos de poupança — incluídos no contrato.",
    ),
    Rubrica(
        "- A prazo", "juros_depositos_a_prazo", _INCLUIR,
        "Depósitos a prazo — incluídos no contrato.",
    ),
    Rubrica(
        "Recursos de emissão de títulos", "juros_titulos_emitidos", _INCLUIR,
        "Títulos de dívida emitidos — incluídos no contrato.",
    ),
    Rubrica(
        "Dívidas subordinadas", "juros_dividas_subordinadas", _INCLUIR,
        "Dívida subordinada apresentada como PASSIVO nas demonstrações IFRS — "
        "o contrato a inclui explicitamente nessa condição.",
    ),
    Rubrica(
        "Passivos de contatos de seguros", "juros_passivos_de_seguros",
        _EXCLUIR,
        "Passivo de contrato de seguro não é instrumento de captação: é "
        "obrigação com segurado. Fora do contrato, e com valor próprio na "
        "nota — a exclusão é leitura, não estimativa. (O rótulo traz o erro "
        "de digitação 'contatos' na origem; preservado como impresso.)",
        alternativos=("Passivos de contratos de seguros",),
        obrigatoria=False,
    ),
    Rubrica(
        "Provisões técnicas de capitalização", "juros_provisoes_capitalizacao",
        _EXCLUIR,
        "Atualização de provisão técnica, que o contrato exclui nominalmente.",
        obrigatoria=False,
    ),
    Rubrica(
        # Até 2023 o Bradesco consolida seguros, previdência e capitalização
        # numa linha só; de 2024 em diante separa em duas. As três rubricas são
        # opcionais e o fechamento decide qual redação aquele ano usou.
        "Provisões técnicas de seguros, previdência e capitalização",
        "juros_provisoes_tecnicas_consolidadas", _EXCLUIR,
        "Provisão técnica de seguros, previdência e capitalização — nenhuma é "
        "instrumento de captação; o contrato exclui atualização de provisão.",
        obrigatoria=False,
    ),
)

#: Rubricas do ITAÚ. Composição fechada por instrumento, com residual mínimo.
#: **Valores em MILHÕES de reais**, ao contrário dos outros quatro bancos.
_RUBRICAS_ITAU = (
    Rubrica(
        "Total", "despesa_juros_total", _TOTAL,
        "Total da nota 21b; confere a soma das parcelas.",
    ),
    Rubrica(
        "Depósitos", "juros_depositos", _INCLUIR,
        "Depósitos — incluídos no contrato.",
    ),
    Rubrica(
        "Despesas de Captação no Mercado Aberto", "juros_captacao_mercado_aberto",
        _INCLUIR, "Operações compromissadas — incluídas no contrato.",
    ),
    Rubrica(
        "Recursos de Mercados Interbancários", "juros_mercados_interbancarios",
        _NAO_IDENT,
        "NÃO É JUROS POR COMPETÊNCIA: a linha embute a variação cambial do "
        "principal de captação em moeda estrangeira, que o contrato exclui "
        "nominalmente, e o valor do componente não é publicado. MEDIDO na "
        "própria fonte, não suposto: (i) a maior sub-rubrica da Nota 17b é "
        "'Financiamentos à Importação e Exportação', que a nota declara "
        "'geralmente denominadas em moeda estrangeira' — R$ 84.051 de R$ "
        "188.134 em 31/03/2020 e R$ 105.837 de R$ 363.192 em 31/03/2025; "
        "(ii) no 1T2020 esse saldo subiu 30,1% (64.622 -> 84.051, +19.429) "
        "sem emissão que o explique, e a linha de juros saltou 21.119 "
        "(3.111 -> 24.230) — casam dentro de 8%; (iii) a taxa contratual "
        "declarada é '0% a 9,60% a.a.', teto que sobre R$ 84 bi não produz "
        "mais que ~R$ 2 bi de juros no trimestre; (iv) no 2T2021, com o real "
        "valorizando, o saldo CAIU e a linha veio CREDORA (+3.107). Não é "
        "separável por leitura: a Nota 21b é tabela plana sem rodapé, não há "
        "nota de exposição por moeda nos intermediários, e a nota de hedge "
        "nomeia 'Depósitos' e 'Captações no Mercado Aberto' como objetos — "
        "nunca esta rubrica. Estimar a parcela cambial é proibido pelo "
        "contrato, então ela vira NÃO IDENTIFICADA e J vira intervalo.",
    ),
    Rubrica(
        "Recursos de Mercados Institucionais", "juros_mercados_institucionais",
        _INCLUIR,
        "Títulos emitidos e dívida subordinada colocados no mercado "
        "institucional — incluídos no contrato.",
    ),
    Rubrica(
        # Só existe até ~2020, quando a nota do Itaú era mais granular. É
        # opcional porque desaparece depois; a conferência de fechamento é que
        # decide se aquele ano a publica — e ela acusou a ausência: faltavam
        # exatamente 3.912 no 1T2019, o valor desta linha.
        "Despesa Financeira de Provisões Técnicas de Seguros",
        "juros_provisoes_tecnicas_seguros_previdencia", _EXCLUIR,
        "Despesa financeira de provisão técnica de seguros e previdência: "
        "atualização de provisão e componente atuarial, os dois excluídos "
        "nominalmente pelo contrato. Vem em linha própria com valor.",
        obrigatoria=False,
    ),
    Rubrica(
        "Outros", "juros_outros_sem_composicao", _NAO_IDENT,
        "A nota não abre a composição. Pode conter item do contrato e item "
        "fora dele; estimar a parcela ausente é proibido.",
    ),
)

FONTES: tuple[Fonte, ...] = (
    Fonte(
        "bb_ifrs_2025T1", "001023", "bb_ifrs_1T2025.pdf",
        "1f3e89212f0ad62f8cc7a03ebab90ea06510193780f42186bb90e25c1b56c0da",
        "2025T1", "demonstracoes_intermediarias_condensadas",
        url="https://api.mziq.com/mzfilemanager/v2/d/5760dff3-15e1-4962-9e81-322a0b3d0bbd/a4033fa2-0a8e-d6ab-9cd1-a044c3ab904b?origin=2",
        data_download="2026-08-11",
    ),
    Fonte(
        "bb_ifrs_2025T2", "001023", "bb_ifrs_2T2025.pdf",
        "086693858e491b590f33d7d64c3c62881b78ac37b688fea491be5d716aad6f4e",
        "2025T2", "demonstracoes_intermediarias_condensadas",
        data_download="2026-08-11",
    ),
    Fonte(
        "bb_ifrs_2025T3", "001023", "bb_ifrs_3T2025.pdf",
        "ff7bd096fe28834f658c4e16002ad6f98af268c4466c0a4cb6b6641167df8154",
        "2025T3", "demonstracoes_intermediarias_condensadas",
        data_download="2026-08-11",
    ),
    Fonte(
        "bb_ifrs_2025A", "001023", "bb_ifrs_4T2025.pdf",
        "89a146bf4bcbd220b55d084486e802be1e22b66fac50b5a9f9c6e37a0a75bd59",
        "2025A", "demonstracoes_anuais",
        data_download="2026-08-11",
    ),
    Fonte(
        "btg_ifrs_2025T1", "022616", "btg_ifrs_1T2025.pdf",
        "4a5ed513cba220842c75e715cf7f64be0dbfe00dcb05ca9b6b1aadac32abac41",
        "2025T1", "demonstracoes_intermediarias_condensadas",
        data_download="2026-08-11",
    ),
    Fonte(
        "btg_ifrs_2025T2", "022616", "btg_ifrs_2T2025.pdf",
        "a63a796988c1a52137317975904c8cde957cab4d8c954f2ce55d55c0ccc3dcf9",
        "2025T2", "demonstracoes_intermediarias_condensadas",
        data_download="2026-08-11",
    ),
    Fonte(
        "btg_ifrs_2025T3", "022616", "btg_ifrs_3T2025.pdf",
        "5a37e598c585f34690bce68508d0ed85eb90ced2747fea62e2016fe4beab97e9",
        "2025T3", "demonstracoes_intermediarias_condensadas",
        data_download="2026-08-11",
    ),
    Fonte(
        "santander_ifrs_2025T1", "020532", "santander_ifrs_1T2025.pdf",
        "1bdcfffacc5a276d921e5461f2e27c572c5c47e04ccdab79f7940a8f86533f5f",
        "2025T1", "demonstracoes_intermediarias_condensadas",
        url="https://api.mziq.com/mzfilemanager/v2/d/a2595886-9fbb-4339-8a38-71d6ce7c7d36/f6754e68-2d4d-baa9-6490-6251042430e1?origin=2",
        data_download="2026-08-11",
    ),
    Fonte(
        "santander_ifrs_2025T2", "020532", "santander_ifrs_2T2025.pdf",
        "1c42ac36c7a27a9c31e9355ec8a48b09287f81084b6add82cfdf1fe9e5906c2e",
        "2025T2", "demonstracoes_intermediarias_condensadas",
        data_download="2026-08-11",
    ),
    Fonte(
        "santander_ifrs_2025T3", "020532", "santander_ifrs_3T2025.pdf",
        "2cf4945f19ec68825f6d831b685f47723df6a9ed10f1e0ea64a7e7c20168aefb",
        "2025T3", "demonstracoes_intermediarias_condensadas",
        data_download="2026-08-11",
    ),
    # --- Documentos recuperados do catálogo IPE da CVM em 2026-09-09 ---
    # Diferença que importa: estes são os arquivamentos ORIGINAIS de cada
    # trimestre, com protocolo, versão e data de entrega à CVM. Os valores de
    # 2024 aqui são "como reportados na época", não coluna comparativa
    # reapresentada — é o que permite P3.
    Fonte(
        "bradesco_ifrs_2024T1", "000906", "bradesco_2024T1_v1.pdf",
        "a24093bd823acf2435a86d8f82522ce9b4505593dbb567973d151c7fad143591",
        "2024T1", "demonstracoes_intermediarias_condensadas",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1231187&numSequencia=755913&numVersao=1",
        data_download="2026-09-09",
        data_entrega="2024-05-02", versao=1, protocolo="000906IPE310320240104541403-84",
    ),
    Fonte(
        "bradesco_ifrs_2024T2", "000906", "bradesco_2024T2_v1.pdf",
        "a967d962d204bf1e67f2c79a40ceb3d532c534a2a103772be9c3e9cfef74a9a6",
        "2024T2", "demonstracoes_intermediarias_condensadas",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1266522&numSequencia=791248&numVersao=1",
        data_download="2026-09-09",
        data_entrega="2024-08-05", versao=1, protocolo="000906IPE300620240104550904-28",
    ),
    Fonte(
        "bradesco_ifrs_2024T3", "000906", "bradesco_2024T3_v1.pdf",
        "01cccaadf448f0a00c6dc0b5c8a599d73ae883ed84861c457a4f4fc0d94ba990",
        "2024T3", "demonstracoes_intermediarias_condensadas",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1296470&numSequencia=821196&numVersao=1",
        data_download="2026-09-09",
        data_entrega="2024-10-31", versao=1, protocolo="000906IPE300920240104559603-85",
    ),
    Fonte(
        "bradesco_ifrs_2024A", "000906", "bradesco_2024T4_v1.pdf",
        "d970bf6ac105740ed8d15df7b3da1d220b972eb0bb15756c43dc232e680e22b0",
        "2024A", "demonstracoes_anuais",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1331677&numSequencia=856403&numVersao=1",
        data_download="2026-09-09",
        data_entrega="2025-02-07", versao=1, protocolo="000906IPE311220240104569503-89",
    ),
    Fonte(
        "bradesco_ifrs_2025T1", "000906", "bradesco_2025T1_v1.pdf",
        "8a25d1958dbd7fd97cef042705415cb1206b6ef9844fe56d7b19235659f1f0ae",
        "2025T1", "demonstracoes_intermediarias_condensadas",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1373668&numSequencia=898380&numVersao=1",
        data_download="2026-09-09",
        data_entrega="2025-05-07", versao=1, protocolo="000906IPE310320250168989810-79",
    ),
    Fonte(
        "itau_ifrs_2024T1", "019348", "itau_2024T1_v1.pdf",
        "91bb3e4521be4a35abb77caa555c94b08674280f7219d4bd89cfcd4a12d5c3c6",
        "2024T1", "demonstracoes_intermediarias_condensadas",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1233221&numSequencia=757947&numVersao=1",
        data_download="2026-09-09",
        data_entrega="2024-05-06", versao=1, protocolo="019348IPE310320240104541811-52",
    ),
    Fonte(
        "itau_ifrs_2024T2_v1", "019348", "itau_2024T2_v1.pdf",
        "2d19cece5e9cc64d2e29a459218379d3ea6d45b3384e717c18966b0c43b3d932",
        "2024T2", "demonstracoes_intermediarias_condensadas",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1267491&numSequencia=792217&numVersao=1",
        data_download="2026-09-09",
        data_entrega="2024-08-06", versao=1, protocolo="019348IPE300620240104551010-99",
    ),
    Fonte(
        "itau_ifrs_2024T2_v2", "019348", "itau_2024T2_v2.pdf",
        "cd49f3ee71f4aa58c99080a1f3a66558f16c55013033183463d94b5e9796444d",
        "2024T2", "demonstracoes_intermediarias_condensadas",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1267986&numSequencia=792712&numVersao=2",
        data_download="2026-09-09",
        data_entrega="2024-08-07", versao=2, protocolo="019348IPE300620240204545110-99",
    ),
    Fonte(
        "itau_ifrs_2024T3", "019348", "itau_2024T3_v1.pdf",
        "c9d90203030d761ad9a83a360e1f935faae634a7deb57fdfd9ffb1d569dca474",
        "2024T3", "demonstracoes_intermediarias_condensadas",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1297873&numSequencia=822599&numVersao=1",
        data_download="2026-09-09",
        data_entrega="2024-11-04", versao=1, protocolo="019348IPE300920240104560011-30",
    ),
    Fonte(
        "itau_ifrs_2024A", "019348", "itau_2024T4_v1.pdf",
        "9d00cdc3293eaf01c481b0fc93d62d41d7675f4058b22a931c8345b0645e3560",
        "2024A", "demonstracoes_anuais",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1330904&numSequencia=855630&numVersao=1",
        data_download="2026-09-09",
        data_entrega="2025-02-05", versao=1, protocolo="019348IPE311220240104569311-87",
    ),
    Fonte(
        "itau_ifrs_2025T1", "019348", "itau_2025T1_v1.pdf",
        "c4c1e2bf937cb9b139d3700e9c216d2a76fa24ae7d33e8ed505c34af074f88e7",
        "2025T1", "demonstracoes_intermediarias_condensadas",
        diretorio="artefatos/b_dfc_01j/raw",
        url="https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1&numProtocolo=1374565&numSequencia=899277&numVersao=1",
        data_download="2026-09-09",
        data_entrega="2025-05-08", versao=1, protocolo="019348IPE310320250131042013-91",
    ),
    Fonte(
        "santander_ifrs_2025A", "020532", "santander_ifrs_4T2025.pdf",
        "69a6389864fbc0548656c6257cc9a660f6bc1b95fdc70281a69f949c14e4b4e9",
        "2025A", "demonstracoes_anuais",
        data_download="2026-08-11",
    ),
)

NOTAS: tuple[NotaExtraida, ...] = (
    NotaExtraida(
        "bb_ifrs_2025T1", 30, "19", "5 – Receita líquida de juros",
        ("2025T1", "2024T1"), _RUBRICAS_BB,
    ),
    NotaExtraida(
        "bb_ifrs_2025T2", 31, "20", "5 – Receita líquida de juros",
        ("2025S1", "2024S1", "2025T2", "2024T2"), _RUBRICAS_BB,
    ),
    NotaExtraida(
        "bb_ifrs_2025T3", 30, "19", "5 – Receita líquida de juros",
        ("2025M9", "2024M9", "2025T3", "2024T3"), _RUBRICAS_BB,
    ),
    NotaExtraida(
        "bb_ifrs_2025A", 55, "39", "7 – Receita líquida de juros",
        ("2025A", "2024A"), _RUBRICAS_BB,
    ),
    NotaExtraida(
        "btg_ifrs_2025T1", 41, "41", "21 – Resultado líquido com instrumentos financeiros",
        ("2025T1", "2024T1"), _RUBRICAS_BTG,
    ),
    NotaExtraida(
        "btg_ifrs_2025T2", 41, "41", "21 – Resultado líquido com instrumentos financeiros",
        ("2025T2", "2024T2", "2025S1", "2024S1"), _RUBRICAS_BTG,
    ),
    NotaExtraida(
        "btg_ifrs_2025T3", 42, "42", "21 – Resultado líquido com instrumentos financeiros",
        ("2025T3", "2024T3", "2025M9", "2024M9"), _RUBRICAS_BTG,
    ),
    NotaExtraida(
        "santander_ifrs_2025T1", 7, "7", "Demonstração consolidada do resultado",
        ("2025T1", "2024T1"), _RUBRICAS_SANTANDER,
    ),
    NotaExtraida(
        "santander_ifrs_2025T2", 7, "7", "Demonstração consolidada do resultado",
        ("2025T2", "2024T2", "2025S1", "2024S1"), _RUBRICAS_SANTANDER,
    ),
    NotaExtraida(
        "santander_ifrs_2025T3", 7, "7", "Demonstração consolidada do resultado",
        ("2025T3", "2024T3", "2025M9", "2024M9"), _RUBRICAS_SANTANDER,
    ),
    NotaExtraida(
        "santander_ifrs_2025A", 17, "17", "Demonstração Consolidada do Resultado",
        ("2025A", "2024A", "2023A"), _RUBRICAS_SANTANDER,
        colunas_ignoradas_a_esquerda=1,  # referência da nota, não valor
    ),
    # --- Bradesco: nota de juros, em MILHARES ("R$ mil" no cabeçalho) ---
    NotaExtraida(
        "bradesco_ifrs_2024T1", 69, "67", "Resultado líquido de juros",
        ("2024T1", "2023T1"), _RUBRICAS_BRADESCO,
        secao="Despesa de juros e similares",
        secao_fim="Total",
    ),
    NotaExtraida(
        "bradesco_ifrs_2024T2", 72, "70", "Resultado líquido de juros",
        ("2024T2", "2023T2", "2024S1", "2023S1"), _RUBRICAS_BRADESCO,
        secao="Despesa de juros e similares",
        secao_fim="Total",
    ),
    NotaExtraida(
        "bradesco_ifrs_2024T3", 72, "70", "Resultado líquido de juros",
        ("2024T3", "2023T3", "2024M9", "2023M9"), _RUBRICAS_BRADESCO,
        secao="Despesa de juros e similares",
        secao_fim="Total",
    ),
    NotaExtraida(
        "bradesco_ifrs_2024A", 102, "100", "Resultado líquido de juros",
        ("2024A", "2023A", "2022A"), _RUBRICAS_BRADESCO,
        secao="Despesa de juros e similares",
        secao_fim="Total",
    ),
    NotaExtraida(
        "bradesco_ifrs_2025T1", 69, "67", "Resultado líquido de juros",
        ("2025T1", "2024T1"), _RUBRICAS_BRADESCO,
        secao="Despesa de juros e similares",
        secao_fim="Total",
    ),
    # --- Itaú: nota 21b, em MILHÕES ("Em milhões" no cabeçalho) ---
    NotaExtraida(
        "itau_ifrs_2024T1", 67, "67", "Nota 21b - Despesas de Juros e Similares",
        ("2024T1", "2023T1"), _RUBRICAS_ITAU,
        unidade="milhoes_de_reais", secao="b) Despesas de Juros e Similares",
        secao_fim="Total",
    ),
    NotaExtraida(
        "itau_ifrs_2024T2_v1", 71, "71", "Nota 21b - Despesas de Juros e Similares",
        ("2024T2", "2023T2", "2024S1", "2023S1"), _RUBRICAS_ITAU,
        unidade="milhoes_de_reais", secao="b) Despesas de Juros e Similares",
        secao_fim="Total",
    ),
    NotaExtraida(
        "itau_ifrs_2024T2_v2", 72, "72", "Nota 21b - Despesas de Juros e Similares",
        ("2024T2", "2023T2", "2024S1", "2023S1"), _RUBRICAS_ITAU,
        unidade="milhoes_de_reais", secao="b) Despesas de Juros e Similares",
        secao_fim="Total",
    ),
    NotaExtraida(
        "itau_ifrs_2024T3", 67, "67", "Nota 21b - Despesas de Juros e Similares",
        ("2024T3", "2023T3", "2024M9", "2023M9"), _RUBRICAS_ITAU,
        unidade="milhoes_de_reais", secao="b) Despesas de Juros e Similares",
        secao_fim="Total",
    ),
    NotaExtraida(
        "itau_ifrs_2024A", 79, "79", "Nota 21b - Despesas de Juros e Similares",
        ("2024A", "2023A", "2022A"), _RUBRICAS_ITAU,
        unidade="milhoes_de_reais", secao="b) Despesas de Juros e Similares",
        secao_fim="Total",
    ),
    NotaExtraida(
        "itau_ifrs_2025T1", 68, "68", "Nota 21b - Despesas de Juros e Similares",
        ("2025T1", "2024T1"), _RUBRICAS_ITAU,
        unidade="milhoes_de_reais", secao="b) Despesas de Juros e Similares",
        secao_fim="Total",
    ),
)


# ---------------------------------------------------------------------------
# Leitura de evidência
# ---------------------------------------------------------------------------

#: Número em português com separador de milhar por ponto, opcionalmente entre
#: parênteses (convenção contábil para valor negativo). NÃO aceita sufixo de
#: escala: em tabela de demonstração a escala é propriedade do cabeçalho, e
#: interpretá-la por palavra solta foi o defeito que invalidou o CAND-04.
_NUMERO = re.compile(r"\(?-?\d{1,3}(?:\.\d{3})*(?:,\d+)?\)?(?=\s|$)")


def parsear_decimal(texto: str) -> Decimal:
    """Converte o texto exatamente como impresso, preservando sinal.

    Parênteses são negativo contábil. Não há `abs`, não há preenchimento de
    ausente por zero e não há multiplicador implícito.
    """
    bruto = texto.strip()
    negativo = bruto.startswith("(") and bruto.endswith(")")
    nu = bruto.strip("()")
    # Vírgula seguida de EXATAMENTE três dígitos é ambígua: em pt-BR a vírgula
    # é decimal, mas nestas tabelas o separador de milhar é ponto, e três casas
    # decimais não existem em cifra de demonstração. Medido: o Itaú imprime
    # `(41,923)` no total do 2T2023 enquanto as parcelas usam ponto — ler como
    # decimal daria 41,923 no lugar de 41.923, erro de MIL VEZES, que é a classe
    # que invalidou a rodada A do CAND-04.
    #
    # A saída NÃO é adivinhar: as parcelas somarem 41.923 sugere a intenção, mas
    # usar a soma para escolher a leitura seria ajustar o dado ao teste. Recusa-se
    # o valor e declara-se o defeito de origem (§3.3: declarar com procedência,
    # nunca mutar em silêncio).
    if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})*,\d{3}", nu):
        raise ErroExtracao(
            f"Valor {texto!r} tem vírgula seguida de três dígitos: separador "
            "ambíguo. Ler como decimal ou como milhar difere por 1000×; o "
            "valor é recusado e o defeito de origem fica declarado."
        )
    limpo = nu.replace(".", "").replace(",", ".")
    if not limpo or limpo in {"-", "--"}:
        raise ErroExtracao(f"Texto {texto!r} não é valor numérico.")
    valor = Decimal(limpo)
    return -valor if negativo else valor


def numeros_da_linha(linha: str) -> list[tuple[str, Decimal]]:
    """Devolve (texto original, valor) de cada número da linha, na ordem.

    **Token que casa como número mas o parser recusa INTERROMPE a leitura da
    linha.** Descartá-lo em silêncio — o que esta função fazia — encolhe a
    lista e desloca as posições seguintes: a contagem de colunas passa a sair
    errada e cada valor pode ser atribuído à coluna de outro período, sem
    sinal nenhum. Medido no Itaú: no 2T2023 o total imprime três cifras com
    vírgula e sobrava **1** número onde há 4 colunas; no 3T2023 sobravam 2,
    contagem que existe no layout declarado e teria sido aceita.
    """
    achados = []
    for casamento in _NUMERO.finditer(linha):
        bruto = casamento.group(0)
        try:
            achados.append((bruto, parsear_decimal(bruto)))
        except ErroExtracao as erro:
            raise ErroExtracao(
                f"Número {bruto!r} recusado no meio da linha; ler a linha sem "
                f"ele deslocaria as colunas. Causa: {erro}"
            ) from erro
    return achados


#: Um espaço isolado entre dígitos/pontos. **Nunca é separador de coluna** — e
#: isso foi medido, não suposto: nos documentos afetados a distribuição de
#: espaços entre dígitos é 1 (65 casos) e depois salta para 3+ (2.561 casos),
#: com ZERO ocorrências de exatamente 2. Separador de coluna no `-layout` é
#: sempre ≥3 espaços.
_ESPACO_ESPURIO = re.compile(r"(?<=[\d.,]) (?=[\d.,])")


def normalizar_espacos_espurios(texto: str) -> str:
    """Junta números partidos por espaço na extração de texto.

    Documentos mais antigos de Itaú, BB e Bradesco saem do `pdftotext` com
    número quebrado: `(17 .1 77)` em vez de `(17.177)`, `31 /03/2023` em vez de
    `31/03/2023`. Sem reparo, a contagem de colunas acusa "3 números para 2
    colunas" e a extração é recusada — corretamente, mas perdendo o documento.
    
    A reparação é **conservadora por medição**: só colapsa espaço ISOLADO, que
    nos documentos medidos nunca separa colunas. E ela não é confiada: a
    conferência de fechamento (soma das parcelas == total impresso) e as
    identidades trimestrais continuam valendo depois do reparo, e qualquer
    fusão indevida de colunas produziria valor absurdo que elas acusariam.
    """
    return _ESPACO_ESPURIO.sub("", texto)


@dataclass(frozen=True)
class LeituraDeclarada:
    """Um glifo ambíguo na origem, com a leitura declarada e a procedência.

    Segue o padrão que o §3.3 do AGENTS.md fixou em
    `corpus/cvm/correcoes_contabeis.csv`: fonte defeituosa **se declara com
    procedência**, nunca se muta em silêncio e nunca se exclui a célula.

    **Não há dígito alterado.** A mesma sequência de algarismos é lida com o
    separador que o resto da própria tabela usa. O que se declara é a
    convenção do glifo, não um número novo.
    """

    fonte_id: str
    pagina_pdf: int
    #: Exatamente como o extrator devolve, depois do reparo de espaço espúrio.
    impresso: str
    #: A mesma sequência de dígitos com o separador do resto da tabela.
    leitura: str
    justificativa: str

    def __post_init__(self) -> None:
        digitos = lambda t: re.sub(r"\D", "", t)
        if digitos(self.impresso) != digitos(self.leitura):
            raise ErroExtracao(
                f"Leitura declarada de {self.impresso!r} altera dígitos "
                f"para {self.leitura!r}: isso não é leitura, é correção."
            )
        if len(self.justificativa) < 60:
            raise ErroExtracao("Justificativa de leitura declarada é curta.")


#: **Cinco glifos no manifesto inteiro** — medido, não estimado: uma varredura
#: da seção da nota em todos os 65 documentos achou exatamente estes.
#:
#: A justificativa NÃO é que as parcelas somam o total. Usar a soma para
#: escolher a leitura seria ajustar o dado ao teste, e o teste é justamente o
#: fechamento. O argumento é de **desigualdade**: numa soma de parcelas de
#: mesmo sinal o total não pode ser MENOR que a maior parcela. Lido como
#: decimal, `(41,923)` vale 41,9 na mesma tabela em que uma parcela isolada
#: vale 17.842 — a leitura decimal é impossível, não apenas improvável.
LEITURAS_DECLARADAS: tuple[LeituraDeclarada, ...] = (
    LeituraDeclarada(
        "itau_ifrs_2023T2", 81, "(41,923)", "(41.923)",
        "Total do 2T2023 isolado. Maior parcela da mesma coluna: 17.842. "
        "Lido como decimal o total valeria 41,9 e seria menor que uma de "
        "suas parcelas — impossível numa soma de mesmo sinal.",
    ),
    LeituraDeclarada(
        "itau_ifrs_2023T2", 81, "(81,576)", "(81.576)",
        "Total do 1S2023 acumulado. Maior parcela da mesma coluna: 35.019. "
        "Lido como decimal o total valeria 81,6 e seria menor que uma de "
        "suas parcelas — impossível numa soma de mesmo sinal.",
    ),
    LeituraDeclarada(
        "itau_ifrs_2023T2", 81, "(46,025)", "(46.025)",
        "Total do 1S2022 comparativo. Maior parcela da mesma coluna: 19.509. "
        "Lido como decimal o total valeria 46,0 e seria menor que uma de "
        "suas parcelas — impossível numa soma de mesmo sinal.",
    ),
    LeituraDeclarada(
        "itau_ifrs_2023T3", 75, "(39,978)", "(39.978)",
        "Total do 3T2023 isolado. Maior parcela da mesma coluna: 18.964. "
        "Lido como decimal o total valeria 40,0 e seria menor que uma de "
        "suas parcelas — impossível numa soma de mesmo sinal.",
    ),
    LeituraDeclarada(
        "itau_ifrs_2023T3", 75, "(78,406)", "(78.406)",
        "Total do 9M2022 comparativo. Maior parcela da mesma coluna: 35.483. "
        "Lido como decimal o total valeria 78,4 e seria menor que uma de "
        "suas parcelas — impossível numa soma de mesmo sinal.",
    ),
)


def aplicar_leituras_declaradas(texto: str, fonte_id: str, pagina: int) -> str:
    """Troca o glifo ambíguo pela leitura declarada, se ele ainda estiver lá.

    **Guarda anti-porta-dos-fundos**, igual à das correções contábeis: se o
    emissor republicar o documento sem o defeito, o glifo não é encontrado e
    nada é trocado. A declaração nunca cria número que a página não tem.
    """
    for declarada in LEITURAS_DECLARADAS:
        if declarada.fonte_id == fonte_id and declarada.pagina_pdf == pagina:
            texto = texto.replace(declarada.impresso, declarada.leitura)
    return texto


def texto_da_pagina(fonte: Fonte, pagina: int) -> str:
    """Texto de UMA página, por `pdftotext -layout` ou pelo cache de OCR.

    O layout preservado é o que mantém a associação entre rótulo de linha e
    coluna de período — sem ele, número recuperado sem o rótulo da coluna é
    número inútil para citação (spec 5.3).
    """
    verificar_caminho_permitido(fonte.caminho)
    if fonte.texto_por_ocr:
        return _texto_do_cache_ocr(fonte, pagina)
    if not fonte.caminho.is_file():
        raise ErroExtracao(f"Fonte ausente em disco: {fonte.caminho}")
    saida = subprocess.run(
        ["pdftotext", "-f", str(pagina), "-l", str(pagina), "-layout",
         str(fonte.caminho), "-"],
        capture_output=True, text=True, timeout=120,
    )
    if saida.returncode != 0:
        raise ErroExtracao(f"pdftotext falhou em {fonte.arquivo} p.{pagina}")
    return aplicar_leituras_declaradas(
        normalizar_espacos_espurios(saida.stdout), fonte.fonte_id, pagina
    )


def _texto_do_cache_ocr(fonte: Fonte, pagina: int) -> str:
    caminho = fonte.caminho_ocr
    verificar_caminho_permitido(caminho)
    if not caminho.is_file():
        raise ErroExtracao(f"Cache de OCR ausente: {caminho}")
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    paginas = dados.get("ocr", {}).get("pages") or dados.get("paginas") or []
    if pagina - 1 >= len(paginas):
        raise ErroExtracao(
            f"Cache de OCR de {fonte.arquivo} tem {len(paginas)} páginas; "
            f"pedida a {pagina}."
        )
    bloco = paginas[pagina - 1]
    return bloco.get("markdown") or bloco.get("texto") or ""


def hash_do_arquivo(caminho: Path) -> str:
    verificar_caminho_permitido(caminho)
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for pedaco in iter(lambda: arquivo.read(1 << 20), b""):
            digest.update(pedaco)
    return digest.hexdigest()


def localizar_rubrica(texto_pagina: str, rotulo: str) -> tuple[str, str]:
    """Acha (linha do rótulo, linha dos valores), exigindo unicidade.

    Rótulo que casa em duas linhas da mesma página é ambiguidade, não escolha:
    devolver a primeira seria decidir em silêncio qual tabela vale.

    **O rótulo pode quebrar em mais de uma linha** e foi medido, não suposto:
    no layout de quatro colunas do BB (2T e 3T), *"Recursos de emissões de
    títulos e valores mobiliários"* aparece como `…e valores` / linha só com os
    números / `mobiliários`. Exigir rótulo e números na mesma linha perdia a
    rubrica inteira — e perder uma parcela de J em silêncio é exatamente o que
    o contrato proíbe. Por isso os valores são buscados na própria linha e, se
    ela não os tiver, na primeira linha seguinte que tenha.
    """
    # Comparação sem espaços e sem caixa: os mesmos documentos que partem
    # números também partem palavras ("Mercados I nte rbancários", "Mercado A
    # berto"). A exigência de UNICIDADE continua sendo a proteção contra casar
    # a linha errada — relaxar o espaço não relaxa isso.
    def _chave(texto: str) -> str:
        # `l` minúsculo e `I` maiúsculo são o MESMO desenho em várias fontes, e
        # o extrator troca um pelo outro: o Itaú sai com "Recursos de Mercados
        # lnterbancários" e "Aplicações em Depósitos lnterfinanceiros". Dobrar
        # os dois na mesma letra é seguro por MEDIÇÃO, não por suposição: nos
        # 28 rótulos declarados a dobra produz zero colisões, e nas 210 linhas
        # das seis páginas afetadas ela não cria uma única ambiguidade nova.
        # A unicidade exigida logo abaixo continua sendo a trava.
        return re.sub(r"\s+", "", texto).casefold().replace("l", "i")

    alvo = _chave(rotulo)
    linhas = texto_pagina.splitlines()
    casadas = [
        indice for indice, linha in enumerate(linhas)
        if _chave(linha).startswith(alvo)
    ]
    if not casadas:
        raise ErroExtracao(f"Rubrica {rotulo!r} não encontrada na página.")
    if len(casadas) > 1:
        raise ErroExtracao(
            f"Rubrica {rotulo!r} casa em {len(casadas)} linhas; ambígua."
        )
    indice = casadas[0]
    if numeros_da_linha(linhas[indice]):
        return linhas[indice], linhas[indice]
    for seguinte in linhas[indice + 1: indice + 4]:
        if numeros_da_linha(seguinte):
            return linhas[indice], seguinte
    raise ErroExtracao(
        f"Rubrica {rotulo!r} encontrada, mas sem linha de valores adjacente."
    )


# ---------------------------------------------------------------------------
# Extração e construção de J
# ---------------------------------------------------------------------------


@dataclass
class Fato:
    fato_id: str
    pacote_id: str
    fonte_id: str
    conceito: str
    rotulo_original: str
    periodo: str
    coluna_indice: int
    texto_original: str
    valor: Decimal
    unidade: str
    valor_reais: Decimal
    pagina_pdf: int
    pagina_impressa: str
    nota: str
    tratamento: str
    motivo: str
    base_contabil: str
    perimetro: str
    evidencia: str
    #: `propria` = o período é o do próprio documento (valor como reportado na
    #: época). `comparativa` = coluna de período anterior num documento
    #: posterior (as-restated). `derivada` = calculado de dois operandos.
    #: A distinção é o que separa identificação histórica de reapresentada.
    origem_periodo: str = "comparativa"
    cd_cvm_do_fato: str = ""
    #: Data em que ESTE conteúdo ficou público, quando demonstrável por
    #: protocolo e versão. Data de download não serve e fica nula.
    disponivel_em: str | None = None
    #: Propagado da `Rubrica`. Ver `Rubrica.limite_demonstravel` (achado F1).
    limite_demonstravel: bool = False

    def para_json(self) -> dict:
        dados = {k: v for k, v in self.__dict__.items()}
        dados["valor"] = str(self.valor)
        dados["valor_reais"] = str(self.valor_reais)
        dados["schema_version"] = SCHEMA_VERSION
        return dados


def _recortar_secao(texto_pagina: str, secao: str, secao_fim: str = "") -> str:
    """Devolve só o trecho da seção pedida, do rótulo de abertura ao de fecho.

    `secao` aceita alternativas separadas por `|`, porque o mesmo emissor muda
    a redação do título entre anos (o Itaú diz "Rendimentos" até 2020 e
    "Similares" depois).
    """
    linhas = texto_pagina.splitlines()
    alternativas = [a.strip().casefold() for a in secao.split("|") if a.strip()]
    inicio = None
    for indice, linha in enumerate(linhas):
        atual = linha.strip().casefold()
        if any(atual.startswith(a) for a in alternativas):
            inicio = indice
            break
    if inicio is None:
        raise ErroExtracao(f"Seção {secao!r} não encontrada na página.")
    if not secao_fim:
        return "\n".join(linhas[inicio:])
    fecho = secao_fim.casefold()
    for indice in range(inicio + 1, len(linhas)):
        if linhas[indice].strip().casefold().startswith(fecho):
            return "\n".join(linhas[inicio:indice + 1])
    raise ErroExtracao(
        f"Fecho de seção {secao_fim!r} não encontrado depois de {secao!r}."
    )


def alinhar_numeros_por_coluna(
    linha: str, referencia: str, quantidade: int
) -> list[tuple[str, Decimal] | None]:
    """Atribui os números de `linha` às colunas de `referencia` por POSIÇÃO.

    Existe porque **célula em branco existe**: no Itaú de 1T2022 a rubrica
    "Outros" traz `(40)` na coluna do próprio trimestre e **nada** na do ano
    anterior. Contar números e comparar com o número de colunas trata a linha
    como layout mudado e joga a nota inteira fora; ler em ordem atribuiria o
    valor de 2022 à coluna de 2021 — plausível, não nulo e errado.

    O critério é o **alinhamento geométrico de coluna**, a mesma técnica que
    localizou a âncora do BTG 4T2025 quando o texto estava corrompido
    (AGENTS.md §3.3): a estrutura tabular sobrevive onde a leitura sequencial
    não. Cifra nesta tabela é alinhada à DIREITA, então o casamento é pela
    posição final do número.

    Coluna sem número devolve `None` — **ausência não vira zero**. Casamento
    ambíguo ou duas cifras na mesma coluna levantam erro: preencher por
    adivinhação é pior que declarar a lacuna. Quem confere o resultado é o
    fechamento aritmético da nota, que é independente desta atribuição.
    """
    fins_referencia = [c.end() for c in _NUMERO.finditer(referencia)]
    if len(fins_referencia) != quantidade:
        raise ErroExtracao(
            f"Linha de referência tem {len(fins_referencia)} números para "
            f"{quantidade} colunas; não serve de régua."
        )
    if quantidade > 1:
        vaos = [
            b - a for a, b in zip(fins_referencia, fins_referencia[1:])
        ]
        tolerancia = max(2, min(vaos) // 2)
    else:
        tolerancia = 8

    saida: list[tuple[str, Decimal] | None] = [None] * quantidade
    for casamento in _NUMERO.finditer(linha):
        bruto = casamento.group(0)
        distancias = [
            (abs(casamento.end() - fim), indice)
            for indice, fim in enumerate(fins_referencia)
        ]
        distancia, indice = min(distancias)
        if distancia > tolerancia:
            raise ErroExtracao(
                f"Número {bruto!r} termina na coluna {casamento.end()}, a "
                f"{distancia} da coluna mais próxima (tolerância "
                f"{tolerancia}): não se sabe a que período pertence."
            )
        empatados = [d for d, _ in distancias if d == distancia]
        if len(empatados) > 1:
            raise ErroExtracao(
                f"Número {bruto!r} fica à mesma distância de duas colunas."
            )
        if saida[indice] is not None:
            raise ErroExtracao(
                f"Duas cifras casam na coluna {indice}: {saida[indice][0]!r} "
                f"e {bruto!r}."
            )
        saida[indice] = (bruto, parsear_decimal(bruto))
    return saida


def extrair_nota(
    nota: NotaExtraida, fonte: Fonte, fonte_alternativa: bool = False
) -> list[Fato]:
    """Extrai todas as rubricas declaradas de uma nota, coluna a coluna."""
    texto = texto_da_pagina(fonte, nota.pagina_pdf)
    if nota.secao:
        texto = _recortar_secao(texto, nota.secao, nota.secao_fim)
    fatos: list[Fato] = []
    # Régua geométrica: a primeira linha de rubrica que traz TODAS as colunas.
    # Serve para atribuir por posição as linhas com célula em branco.
    regua = ""
    for rubrica in nota.rubricas:
        for rotulo in rubrica.rotulos:
            try:
                candidata = localizar_rubrica(texto, rotulo)[1]
            except ErroExtracao:
                continue
            try:
                quantos = len(
                    numeros_da_linha(candidata)[nota.colunas_ignoradas_a_esquerda:]
                )
            except ErroExtracao:
                break
            if quantos == len(nota.colunas):
                regua = candidata
            break
        if regua:
            break

    for rubrica in nota.rubricas:
        achado = None
        for rotulo in rubrica.rotulos:
            try:
                achado = localizar_rubrica(texto, rotulo)
                break
            except ErroExtracao:
                continue
        if achado is None:
            if rubrica.obrigatoria:
                raise ErroExtracao(
                    f"Rubrica {rubrica.rotulos} não encontrada na página."
                )
            continue
        linha_rotulo, linha = achado
        numeros: list[tuple[str, Decimal] | None]
        numeros = numeros_da_linha(linha)[nota.colunas_ignoradas_a_esquerda:]
        if len(numeros) < len(nota.colunas) and regua:
            # Menos cifras que colunas é célula em branco até prova em
            # contrário; a régua decide a QUAL coluna cada uma pertence.
            numeros = alinhar_numeros_por_coluna(
                linha, regua, len(nota.colunas) + nota.colunas_ignoradas_a_esquerda
            )[nota.colunas_ignoradas_a_esquerda:]
        if len(numeros) != len(nota.colunas):
            raise ErroExtracao(
                f"{fonte.fonte_id} p.{nota.pagina_pdf} rubrica "
                f"{rubrica.rotulo!r}: {len(numeros)} números para "
                f"{len(nota.colunas)} colunas declaradas. Layout mudou; "
                "extrair assim atribuiria valor à coluna errada."
            )
        for indice, (periodo, celula) in enumerate(
            zip(nota.colunas, numeros)
        ):
            if celula is None:
                continue  # célula em branco: não existe fato, e não vira zero
            bruto, valor = celula
            verificar_periodo_no_escopo(periodo)
            fatos.append(
                Fato(
                    fato_id=f"{fonte.fonte_id}|{rubrica.conceito}|{periodo}",
                    pacote_id=pacote_id(fonte.cd_cvm, periodo)
                    if periodo in PERIODOS else "",
                    fonte_id=fonte.fonte_id,
                    conceito=rubrica.conceito,
                    rotulo_original=rubrica.rotulo,
                    periodo=periodo,
                    coluna_indice=indice,
                    texto_original=bruto,
                    valor=valor,
                    unidade=nota.unidade,
                    valor_reais=valor * MULTIPLICADOR_UNIDADE[nota.unidade],
                    pagina_pdf=nota.pagina_pdf,
                    pagina_impressa=nota.pagina_impressa,
                    nota=nota.nota,
                    tratamento=rubrica.tratamento,
                    motivo=rubrica.motivo,
                    limite_demonstravel=rubrica.limite_demonstravel,
                    base_contabil=fonte.base_contabil,
                    perimetro=fonte.perimetro,
                    cd_cvm_do_fato=fonte.cd_cvm,
                    origem_periodo=(
                        "propria"
                        if periodo_e_do_documento(
                            periodo, fonte.periodo_documento
                        )
                        else "comparativa"
                    ),
                    disponivel_em=(
                        fonte.data_entrega
                        if fonte.tem_procedencia_de_entrega
                        and periodo_e_do_documento(
                            periodo, fonte.periodo_documento
                        )
                        else None
                    ),
                    evidencia=(
                        linha_rotulo.strip()
                        if linha_rotulo is linha
                        else f"{linha_rotulo.strip()} ⏎ {linha.strip()}"
                    )[:300],
                )
            )
    return fatos


@dataclass
class ResultadoJ:
    """J como intervalo declarado, nunca como ponto inventado."""

    pacote_id: str
    cd_cvm: str
    periodo: str
    fonte_id: str
    status: str
    total_declarado: Decimal | None
    soma_incluidas: Decimal
    residuo_nao_identificado: Decimal
    excluido_por_contrato: Decimal
    conceitos_excluidos: list[str]
    limite_inferior: Decimal
    limite_superior: Decimal
    fechamento_confere: bool | None
    conceitos_incluidos: list[str]
    conceitos_nao_identificados: list[str]
    observacao: str
    base_temporal: str = "as_restated"
    disponivel_em: str | None = None
    #: Conceitos INCLUÍDOS que vieram credores neste período. Ver
    #: `conformidade_contratual` — não é curiosidade, é não conformidade.
    creditos_em_incluidas: tuple[str, ...] = ()
    #: Conceitos não identificados cujo limite NÃO é demonstrável (achado F1).
    #: Quando não vazio, `status` é `nao_identificado` e os limites saem zero:
    #: J tem piso (a soma das incluídas) mas nenhum teto demonstrável.
    conceitos_sem_limite_demonstravel: tuple[str, ...] = ()
    #: O piso que existiria, preservado para leitura — NUNCA para usar como J
    #: nem como centro de intervalo. Só é preenchido no estado acima.
    soma_incluidas_quando_sem_limite: Decimal | None = None
    #: Unidade em que os valores estão, lida dos fatos que compuseram J.
    #: Achado F8: era constante `milhares_de_reais` no JSON e divergia dos
    #: fatos em 90 de 198 registros.
    unidade: str = "milhares_de_reais"

    @property
    def conformidade_contratual(self) -> str:
        """O contrato exige juros POR COMPETÊNCIA, e despesa não é crédito.

        Uma linha de despesa de juros de captação que vem **credora** não é
        juros por competência: ou embute valor justo/câmbio — que o contrato
        B-DFC-01J exclui nominalmente — ou é reclassificação. Nos dois casos a
        parcela deixa de ser o que o contrato mandou somar, e dizer que J está
        "identificado" seria afirmar conformidade que a evidência nega.

        É a mesma armadilha do BTG, achada do mesmo jeito: olhando mais de um
        período em vez de confiar num fechamento que por acaso deu certo.
        """
        return "nao_demonstrada" if self.creditos_em_incluidas else "aparente"

    @property
    def largura_relativa(self) -> Decimal | None:
        if not self.total_declarado:
            return None
        return (
            (self.limite_superior - self.limite_inferior)
            / abs(self.total_declarado)
        )

    def para_json(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "derivado_id": f"J|{self.pacote_id}|{self.fonte_id}",
            "pacote_id": self.pacote_id,
            "cd_cvm": self.cd_cvm,
            "periodo": self.periodo,
            "fonte_id": self.fonte_id,
            "versao_contrato": VERSAO_CONTRATO_J,
            "status": self.status,
            "total_declarado": _ou_nulo(self.total_declarado),
            "soma_incluidas": str(self.soma_incluidas),
            "residuo_nao_identificado": str(self.residuo_nao_identificado),
            "excluido_por_contrato": str(self.excluido_por_contrato),
            "conceitos_excluidos": self.conceitos_excluidos,
            "limite_inferior": str(self.limite_inferior),
            "limite_superior": str(self.limite_superior),
            "largura_relativa": _ou_nulo(self.largura_relativa),
            "fechamento_confere": self.fechamento_confere,
            "conceitos_incluidos": self.conceitos_incluidos,
            "conceitos_nao_identificados": self.conceitos_nao_identificados,
            "base_temporal": self.base_temporal,
            "disponivel_em": self.disponivel_em,
            "creditos_em_incluidas": list(self.creditos_em_incluidas),
            "conformidade_contratual": self.conformidade_contratual,
            "conceitos_sem_limite_demonstravel": list(
                self.conceitos_sem_limite_demonstravel
            ),
            "soma_incluidas_quando_sem_limite": _ou_nulo(
                self.soma_incluidas_quando_sem_limite
            ),
            # Achado F8: isto era a constante "milhares_de_reais". Medido:
            # 90 de 198 registros declaravam milhares enquanto os fatos do
            # Itaú vêm em MILHÕES. O valor numérico sempre esteve na unidade
            # da publicação; a etiqueta é que mentia — e quem cruzasse dois
            # emissores pela etiqueta erraria por mil.
            "unidade": self.unidade,
            "convencao_de_sinal": (
                "fonte publica despesa como negativo; J é reportado como "
                "despesa positiva, com a troca aplicada UMA vez no agregado"
            ),
            "observacao": self.observacao,
        }


def _ou_nulo(valor: Decimal | None) -> str | None:
    return None if valor is None else str(valor)


def construir_j(
    fatos: Sequence[Fato], periodo: str, fonte: Fonte | None = None
) -> ResultadoJ | None:
    """Monta J do período a partir das parcelas extraídas de UMA fonte.

    O contrato admite soma exaustiva de parcelas documentadas, mas proíbe somar
    as linhas disponíveis e chamar o resultado de total. Por isso o retorno é
    sempre um intervalo: o limite inferior soma só o que é comprovadamente do
    contrato, o superior acrescenta tudo que não foi possível separar.
    """
    do_periodo = [f for f in fatos if f.periodo == periodo]
    if not do_periodo:
        return None
    fonte_id = do_periodo[0].fonte_id
    cd_cvm = (
        fonte.cd_cvm if fonte is not None else _dono(do_periodo[0]).cd_cvm
    )

    incluidas = [f for f in do_periodo if f.tratamento == _INCLUIR]
    excluidas = [f for f in do_periodo if f.tratamento == _EXCLUIR]
    residuais = [f for f in do_periodo if f.tratamento == _NAO_IDENT]
    totais = [f for f in do_periodo if f.tratamento == _TOTAL]

    # Achado F8: a unidade sai dos FATOS, não de uma constante. Unidades
    # mistas dentro do mesmo período seriam soma de grandezas diferentes —
    # falha explícita, nunca escolha silenciosa de uma delas.
    unidades = {f.unidade for f in do_periodo}
    if len(unidades) > 1:
        raise ErroExtracao(
            f"Unidades mistas em {cd_cvm}/{periodo}: {sorted(unidades)}. "
            "Somar milhares com milhões daria número plausível e errado."
        )
    unidade = unidades.pop()

    # Soma preservando o sinal e só depois troca a convenção, uma vez, no
    # agregado. Somar `abs` parcela a parcela transformaria um crédito
    # (reversão) em despesa e inflaria J — o plano §8.1 proíbe expressamente,
    # e o erro seria INVISÍVEL onde não há total declarado para conferir.
    soma_assinada = sum((f.valor for f in incluidas), Decimal(0))
    excluido_assinado = sum((f.valor for f in excluidas), Decimal(0))
    residuo_assinado = sum((f.valor for f in residuais), Decimal(0))
    total_assinado = totais[0].valor if totais else None

    # Despesa é publicada com sinal negativo; J é reportado como despesa
    # positiva. A troca é declarada em `convencao_de_sinal`, não implícita.
    soma_incluidas = -soma_assinada
    excluido = -excluido_assinado
    residuo = -residuo_assinado
    total = -total_assinado if total_assinado is not None else None

    # Crédito em linha de DESPESA de juros. A fonte publica despesa como
    # negativo, então valor > 0 numa parcela incluída é crédito — e despesa de
    # captação por competência não é crédito. Medido: acontece em 3 rubricas
    # de 2 emissores, 2 vezes impresso pelo emissor e 2 vezes produzido pela
    # derivação `A − M9` quando o acumulado anual é MENOR que o de nove meses.
    creditos = tuple(sorted(
        f.conceito for f in do_periodo
        if f.tratamento == _INCLUIR and f.valor > 0
    ))

    origens = {f.origem_periodo for f in do_periodo}
    if origens == {"propria"}:
        base_temporal = "original"
    elif origens == {"derivada"}:
        base_temporal = "derivada_de_originais"
    else:
        base_temporal = "as_restated"
    disponiveis = [f.disponivel_em for f in do_periodo if f.disponivel_em]
    # A data que vale é a MAIS TARDIA entre os fatos usados: antes dela o
    # conjunto não estava completo.
    disponivel_em = max(disponiveis) if len(disponiveis) == len(do_periodo) else None
    if base_temporal == "derivada_de_originais" and disponivel_em is None:
        base_temporal = "derivada_sem_certificacao"

    fechamento = None
    if total is not None:
        # Sem tolerância arbitrária: a nota é publicada em unidades inteiras,
        # então TODAS as parcelas — incluídas, excluídas pelo contrato e não
        # identificadas — têm de fechar EXATO no total impresso. Deixar as
        # excluídas fora da conferência faria uma nota íntegra parecer
        # conflitante justamente onde a composição é mais completa.
        fechamento = (soma_incluidas + excluido + residuo) == total

    if not incluidas:
        status = "nao_identificado"
        observacao = (
            "Nenhuma parcela do contrato foi identificada isoladamente; a "
            "fonte traz apenas agregado que mistura itens fora do contrato."
        )
        # Sem nenhuma parcela identificada não existe intervalo: somar as
        # rubricas não identificadas daria um "limite superior" que soma duas
        # decomposições do MESMO total (por instrumento e por natureza, no
        # BTG). Número que parece limite e não é seria pior que ausência.
        return ResultadoJ(
            pacote_id=pacote_id(cd_cvm, periodo),
            cd_cvm=cd_cvm,
            periodo=periodo,
            fonte_id=fonte_id,
            status=status,
            total_declarado=total,
            soma_incluidas=Decimal(0),
            residuo_nao_identificado=residuo,
            excluido_por_contrato=excluido,
            conceitos_excluidos=[f.conceito for f in excluidas],
            limite_inferior=Decimal(0),
            limite_superior=Decimal(0),
            fechamento_confere=fechamento,
            conceitos_incluidos=[],
            conceitos_nao_identificados=[f.conceito for f in residuais],
            observacao=observacao,
            base_temporal=base_temporal,
            creditos_em_incluidas=creditos,
            disponivel_em=disponivel_em,
            unidade=unidade,
        )
    elif not residuais:
        # `identificado` exige AUSÊNCIA de rubrica não identificada, não
        # residual líquido nulo. Achado F1 da revisão independente: duas
        # desconhecidas de +30 e −30 têm residual líquido ZERO e produziam
        # `identificado` com J = ponto exato — mas cada uma pode conter juros
        # (20 e 10, compensados por câmbio), e J seria 130. Residual líquido
        # nulo não significa ausência de componente desconhecido; significa
        # que os desconhecidos se cancelaram na soma, o que é outra coisa.
        status = "identificado"
        observacao = "Composição exaustiva: nenhuma rubrica não identificada."
    elif all(f.limite_demonstravel for f in residuais) and all(
        f.valor <= 0 for f in residuais
    ):
        # Intervalo SÓ quando cada rubrica não identificada declara limite
        # demonstrável E vem devedora. As duas condições são necessárias: a
        # declaração diz que a linha é de sinal único (nenhum componente de
        # sinal oposto compensa juros dentro dela), e o sinal observado
        # confirma que naquele período ela de fato veio devedora.
        status = "limitado"
        observacao = (
            "Parcelas do contrato identificadas, mas há rubrica não separável "
            "cujo limite É demonstrável (linha de sinal único, devedora); J "
            "fica entre os limites, sem estimar a parcela ausente."
        )
    else:
        # Achado F1: sem limite demonstrável, NÃO existe intervalo. O residual
        # líquido de uma linha que mistura juros e câmbio não limita a parcela
        # de juros, porque o câmbio tem os dois sinais e pode compensá-la —
        # medido na contraprova: incluída −100, desconhecida +30, total −70 dá
        # "[70,100]" enquanto o J verdadeiro pode ser 120. Declarar o intervalo
        # aqui seria inventar limite, e o G0 passaria sem prova.
        sem_limite = sorted(
            f.conceito for f in residuais
            if not f.limite_demonstravel or f.valor > 0
        )
        status = "nao_identificado"
        observacao = (
            "Há rubrica não identificada SEM limite demonstrável "
            f"({', '.join(sem_limite)}): a parcela de juros dentro dela não é "
            "limitada pelo valor líquido da linha, porque componente de sinal "
            "oposto (câmbio, valor justo) pode compensá-la. J não tem limite "
            "superior demonstrável e NÃO é reportado como intervalo."
        )
        return ResultadoJ(
            pacote_id=pacote_id(cd_cvm, periodo),
            cd_cvm=cd_cvm,
            periodo=periodo,
            fonte_id=fonte_id,
            status=status,
            total_declarado=total,
            soma_incluidas=soma_incluidas,
            residuo_nao_identificado=residuo,
            excluido_por_contrato=excluido,
            conceitos_excluidos=[f.conceito for f in excluidas],
            # Limite inferior existe e é a soma das incluídas; o SUPERIOR não
            # existe. Reportar os dois iguais faria parecer ponto exato, então
            # os dois saem ZERO e o `status` manda — a mesma disciplina do
            # ramo "nenhuma parcela identificada" acima.
            limite_inferior=Decimal(0),
            limite_superior=Decimal(0),
            fechamento_confere=fechamento,
            conceitos_incluidos=[f.conceito for f in incluidas],
            conceitos_nao_identificados=[f.conceito for f in residuais],
            observacao=observacao,
            base_temporal=base_temporal,
            creditos_em_incluidas=creditos,
            disponivel_em=disponivel_em,
            unidade=unidade,
            conceitos_sem_limite_demonstravel=tuple(sem_limite),
            soma_incluidas_quando_sem_limite=soma_incluidas,
        )

    return ResultadoJ(
        pacote_id=pacote_id(cd_cvm, periodo),
        cd_cvm=cd_cvm,
        periodo=periodo,
        fonte_id=fonte_id,
        status=status,
        total_declarado=total,
        soma_incluidas=soma_incluidas,
        residuo_nao_identificado=residuo,
        excluido_por_contrato=excluido,
        conceitos_excluidos=[f.conceito for f in excluidas],
        # Ordenado de propósito: residual CREDOR (reversão) reduz J em vez de
        # aumentá-lo, e um "intervalo" com inferior maior que superior não é
        # intervalo. Medido no Itaú de 2020, onde "Outros" vem positivo.
        limite_inferior=min(soma_incluidas, soma_incluidas + residuo),
        limite_superior=max(soma_incluidas, soma_incluidas + residuo),
        fechamento_confere=fechamento,
        conceitos_incluidos=[f.conceito for f in incluidas],
        conceitos_nao_identificados=[f.conceito for f in residuais],
        observacao=observacao,
        base_temporal=base_temporal,
        creditos_em_incluidas=creditos,
        disponivel_em=disponivel_em,
        unidade=unidade,
    )


def _dono(fato: Fato):
    """Recupera o emissor da fonte do fato (mantém CD_CVM como chave)."""
    for fonte in FONTES:
        if fonte.fonte_id == fato.fonte_id:
            return fonte
    raise ErroExtracao(f"Fonte {fato.fonte_id} não declarada.")


@dataclass(frozen=True)
class DerivacaoTrimestre:
    """Trimestre isolado obtido por diferença entre dois acumulados.

    Só existe porque o 4º trimestre **não é divulgado isolado**: o documento
    anual traz o exercício inteiro. `Q4 = 12m − 9m` é a regra do §8.1 do plano
    e só vale com intervalos, conceitos, perímetro e política compatíveis —
    aqui os dois operandos são colunas comparativas de 2024 em documentos de
    2025 do mesmo emissor, na mesma base IFRS consolidada.
    """

    cd_cvm: str
    periodo_alvo: str
    fonte_total: str
    periodo_total: str
    fonte_parcial: str
    periodo_parcial: str
    ressalva: str


DERIVACOES_TRIMESTRE: tuple[DerivacaoTrimestre, ...] = (
    DerivacaoTrimestre(
        "001023", "2024T4",
        "bb_ifrs_2025A", "2024A",
        "bb_ifrs_2025T3", "2024M9",
        "Operandos vêm de DOIS documentos distintos (anual de 2025 e 3T de "
        "2025). Ambos são colunas comparativas de 2024 reapresentadas em "
        "2025; a base de revisão pode diferir entre eles e isso não foi "
        "conferido linha a linha.",
    ),
    DerivacaoTrimestre(
        "020532", "2024T4",
        "santander_ifrs_2025A", "2024A",
        "santander_ifrs_2025T3", "2024M9",
        "Mesma ressalva do BB: operandos em dois documentos de 2025. Aqui o "
        "derivado é do agregado 'juros e similares', que já é J NÃO "
        "identificado — derivar não melhora a identificabilidade.",
    ),
    DerivacaoTrimestre(
        "000906", "2024T4",
        "bradesco_ifrs_2024A", "2024A",
        "bradesco_ifrs_2024T3", "2024M9",
        "Os DOIS operandos são arquivamentos ORIGINAIS, com protocolo, versão "
        "e data de entrega à CVM. O derivado estava calculável em 2025-02-07, "
        "a entrega do anual — é point-in-time, não reapresentação.",
    ),
    DerivacaoTrimestre(
        "019348", "2024T4",
        "itau_ifrs_2024A", "2024A",
        "itau_ifrs_2024T3", "2024M9",
        "Mesma condição do Bradesco: dois arquivamentos originais; o derivado "
        "estava calculável em 2025-02-05.",
    ),
)


def derivar_trimestre(
    fatos: Sequence[Fato], derivacao: DerivacaoTrimestre
) -> tuple[list[Fato], list[dict]]:
    """Constrói o trimestre isolado e devolve os fatos e sua linhagem.

    Operando ausente **impede** a derivação daquele conceito — não vira zero.
    """
    totais = {
        f.conceito: f for f in fatos
        if f.fonte_id == derivacao.fonte_total
        and f.periodo == derivacao.periodo_total
    }
    parciais = {
        f.conceito: f for f in fatos
        if f.fonte_id == derivacao.fonte_parcial
        and f.periodo == derivacao.periodo_parcial
    }

    derivados: list[Fato] = []
    linhagem: list[dict] = []
    for conceito, fato_total in sorted(totais.items()):
        fato_parcial = parciais.get(conceito)
        if fato_parcial is None:
            linhagem.append({
                "schema_version": SCHEMA_VERSION,
                "derivado_id": f"{conceito}|{derivacao.cd_cvm}|{derivacao.periodo_alvo}",
                "status": "indisponivel",
                "motivo": (
                    f"Operando {conceito} ausente em "
                    f"{derivacao.fonte_parcial}/{derivacao.periodo_parcial}; "
                    "derivação não é feita com operando faltando."
                ),
            })
            continue
        valor = fato_total.valor - fato_parcial.valor
        # **Acumulado que ENCOLHE não é diferença de nada.** Se os dois
        # operandos são despesa (negativos) e a diferença sai credora, o
        # acumulado de doze meses é MENOR em módulo que o de nove — o que só
        # acontece por reversão no 4T ou porque o documento anual
        # RECLASSIFICOU a composição, e aí os operandos não são comparáveis
        # mesmo sendo os dois originais. Medido no Bradesco: `depósitos
        # interfinanceiros` sai (521.525) no anual de 2025 contra (2.282.154)
        # nos nove meses, produzindo um 4T credor de +1.760.629 numa rubrica
        # cujo trimestre típico é (52.085). Não se sabe qual das duas causas
        # é, e por isso não se escolhe: a derivação é RECUSADA.
        if fato_total.valor < 0 and fato_parcial.valor < 0 and valor > 0:
            linhagem.append({
                "schema_version": SCHEMA_VERSION,
                "derivado_id": (
                    f"{conceito}|{derivacao.cd_cvm}|{derivacao.periodo_alvo}"
                ),
                "status": "recusada",
                "motivo": (
                    f"{derivacao.periodo_total} ({fato_total.valor}) é MENOR "
                    f"em módulo que {derivacao.periodo_parcial} "
                    f"({fato_parcial.valor}) na rubrica {conceito}: o "
                    f"acumulado encolheu e a diferença sairia credora "
                    f"({valor}). Ou houve reversão no 4T, ou o anual "
                    "reclassificou a composição e os operandos não são "
                    "comparáveis. Derivar aqui inventaria um 4T."
                ),
            })
            continue
        fato = Fato(
            fato_id=f"derivado|{derivacao.cd_cvm}|{conceito}|{derivacao.periodo_alvo}",
            pacote_id=pacote_id(derivacao.cd_cvm, derivacao.periodo_alvo),
            fonte_id=derivacao.fonte_total,
            conceito=conceito,
            rotulo_original=fato_total.rotulo_original,
            periodo=derivacao.periodo_alvo,
            coluna_indice=-1,
            texto_original=(
                f"{fato_total.texto_original} − {fato_parcial.texto_original}"
            ),
            valor=valor,
            unidade=fato_total.unidade,
            valor_reais=valor * MULTIPLICADOR_UNIDADE[fato_total.unidade],
            pagina_pdf=fato_total.pagina_pdf,
            pagina_impressa=fato_total.pagina_impressa,
            nota=f"derivado de {fato_total.nota}",
            tratamento=fato_total.tratamento,
            motivo=fato_total.motivo,
            # Derivado NUNCA herda limite demonstrável: `A − M9` compõe duas
            # incertezas (a da composição da rubrica e a da comparabilidade dos
            # dois operandos, que o achado F6 diz não estar adjudicada). Se a
            # rubrica é não identificada e o período é derivado, não há limite.
            limite_demonstravel=False,
            base_contabil=fato_total.base_contabil,
            perimetro=fato_total.perimetro,
            origem_periodo="derivada",
            cd_cvm_do_fato=derivacao.cd_cvm,
            # §8.2 do plano: a disponibilidade de um derivado é no MÍNIMO o
            # máximo da de todos os operandos. Se os dois operandos são
            # originais com data de entrega, o derivado estava calculável
            # naquela data — e aí é point-in-time de verdade.
            disponivel_em=(
                max(fato_total.disponivel_em, fato_parcial.disponivel_em)
                if fato_total.disponivel_em and fato_parcial.disponivel_em
                else None
            ),
            evidencia=(
                f"{derivacao.periodo_total} − {derivacao.periodo_parcial} "
                f"(RN10: valor derivado, não divulgado isolado)"
            ),
        )
        derivados.append(fato)
        linhagem.append({
            "schema_version": SCHEMA_VERSION,
            "derivado_id": fato.fato_id,
            "conceito": conceito,
            "periodo_resultante": derivacao.periodo_alvo,
            "formula": f"{derivacao.periodo_total} - {derivacao.periodo_parcial}",
            "operandos": [fato_total.fato_id, fato_parcial.fato_id],
            "resultado": str(valor),
            "unidade": fato_total.unidade,
            "marcado_como": "derivado",
            "status": "calculado",
            "ressalva": derivacao.ressalva,
            "disponibilidade": "nao_certificada",
        })
    return derivados, linhagem


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComponenteDFC:
    """Uma linha da DFC e o estoque de balanço com que ela é confrontada.

    Serve à Onda 4 do plano: separar linha que **repete diferença de saldos**
    de linha que traz informação incremental. Igualdade numérica é diagnóstico,
    não prova universal — por isso o registro guarda a fórmula e o resíduo, e
    a classificação distingue "não se provou redundante" de "informação
    incremental provada".
    """

    fonte_id: str
    pagina_dfc: int
    rotulo_dfc: str
    pagina_balanco: int
    secao_balanco: str
    periodo: str
    #: Colunas do balanço: saldo do fim do período e saldo de abertura.
    colunas_balanco: tuple[str, str]


COMPONENTES_DFC: tuple[ComponenteDFC, ...] = (
    ComponenteDFC(
        "bb_ifrs_2025T1", 17, "Variação líquida em recursos de clientes",
        52, "15– Recursos de clientes", "2025T1", ("2025-03-31", "2024-12-31"),
    ),
    ComponenteDFC(
        "bb_ifrs_2025T1", 17,
        "Variação líquida em recursos de instituições financeiras",
        52, "16– Recursos de instituições financeiras", "2025T1",
        ("2025-03-31", "2024-12-31"),
    ),
)


def _saldo_da_secao(texto_balanco: str, secao: str) -> tuple[Decimal, Decimal]:
    """Acha o `Total` que pertence à seção pedida.

    O rótulo "Total" repete várias vezes na página; casá-lo direto pegaria o
    total de outra nota. A âncora é o cabeçalho da seção, e o total é o
    primeiro que aparece depois dele.
    """
    linhas = texto_balanco.splitlines()
    inicio = None
    for indice, linha in enumerate(linhas):
        if linha.strip().casefold().startswith(secao.casefold()):
            inicio = indice
            break
    if inicio is None:
        raise ErroExtracao(f"Seção {secao!r} não encontrada no balanço.")
    for linha in linhas[inicio + 1: inicio + 40]:
        if linha.strip().casefold().startswith("total"):
            numeros = numeros_da_linha(linha)
            if len(numeros) >= 2:
                return numeros[0][1], numeros[1][1]
    raise ErroExtracao(f"Total da seção {secao!r} não localizado.")


def classificar_componentes_dfc() -> list[dict]:
    """Confronta cada linha declarada da DFC com a diferença de estoques."""
    registros: list[dict] = []
    for componente in COMPONENTES_DFC:
        fonte = next(
            f for f in FONTES if f.fonte_id == componente.fonte_id
        )
        texto_dfc = texto_da_pagina(fonte, componente.pagina_dfc)
        _, linha_valores = localizar_rubrica(texto_dfc, componente.rotulo_dfc)
        numeros_dfc = numeros_da_linha(linha_valores)
        # Mesma disciplina de `extrair_nota`: sem conferir a contagem, uma
        # coluna a mais no layout faria a leitura pegar o período errado em
        # silêncio. A DFC do BB tem duas colunas (período e comparativo).
        if len(numeros_dfc) != 2:
            raise ErroExtracao(
                f"{componente.fonte_id} p.{componente.pagina_dfc} "
                f"{componente.rotulo_dfc!r}: {len(numeros_dfc)} números para "
                "2 colunas esperadas (período e comparativo)."
            )
        valor_dfc = numeros_dfc[0][1]

        texto_bp = texto_da_pagina(fonte, componente.pagina_balanco)
        saldo_fim, saldo_inicio = _saldo_da_secao(
            texto_bp, componente.secao_balanco
        )
        diferenca = saldo_fim - saldo_inicio
        residuo = valor_dfc - diferenca

        if residuo == 0:
            classificacao = "repeticao_de_diferenca_de_estoques"
            leitura = (
                "A linha reproduz exatamente a diferença entre os saldos do "
                "balanço; não acrescenta informação a quem já tem o balanço."
            )
        else:
            classificacao = "nao_se_provou_redundante"
            leitura = (
                "A linha difere da variação de estoques. Isso NÃO prova "
                "informação incremental: pode ser efeito de câmbio, de "
                "perímetro ou de classificação ainda não examinado."
            )

        registros.append({
            "schema_version": SCHEMA_VERSION,
            "componente_id": f"{componente.fonte_id}|{componente.rotulo_dfc}",
            "fonte_id": componente.fonte_id,
            "periodo": componente.periodo,
            "rotulo_dfc": componente.rotulo_dfc,
            "pagina_dfc": componente.pagina_dfc,
            "valor_dfc": str(valor_dfc),
            "secao_balanco": componente.secao_balanco,
            "pagina_balanco": componente.pagina_balanco,
            "saldo_fim": str(saldo_fim),
            "saldo_inicio": str(saldo_inicio),
            "data_saldo_fim": componente.colunas_balanco[0],
            "data_saldo_inicio": componente.colunas_balanco[1],
            "formula": "saldo_fim - saldo_inicio",
            "diferenca_de_estoques": str(diferenca),
            "residuo": str(residuo),
            "classificacao": classificacao,
            "leitura": leitura,
            "metodo": "indireto (MI)",
            "natureza": "variacao_liquida",
            "limitacao": (
                "Variação líquida não é emissão bruta nem fluxo de principal; "
                "comparar juros pagos com J exigiria escopos reconciliados, "
                "o que este piloto não fez."
            ),
            "unidade": "milhares_de_reais",
        })
    return registros


def executar_extracao() -> tuple[
    list[Fato], list[ResultadoJ], list[dict], list[dict]
]:
    fatos: list[Fato] = []
    for nota in NOTAS:
        fonte = next(f for f in FONTES if f.fonte_id == nota.fonte_id)
        fatos.extend(extrair_nota(nota, fonte))

    linhagem: list[dict] = []
    for derivacao in DERIVACOES_TRIMESTRE:
        derivados, trilha = derivar_trimestre(fatos, derivacao)
        fatos.extend(derivados)
        linhagem.extend(trilha)

    componentes = classificar_componentes_dfc()

    resultados: list[ResultadoJ] = []
    for fonte in FONTES:
        do_fonte = [f for f in fatos if f.fonte_id == fonte.fonte_id]
        for periodo in sorted({f.periodo for f in do_fonte}):
            if periodo not in PERIODOS:
                continue  # período de apoio não vira pacote
            resultado = construir_j(do_fonte, periodo)
            if resultado is not None:
                resultados.append(resultado)
    return fatos, resultados, linhagem, componentes


def montar_auditoria(
    fatos: Sequence[Fato], resultados: Sequence[ResultadoJ],
    componentes: Sequence[dict] = (),
) -> list[dict]:
    """Uma linha por pacote — os 25, inclusive os sem documento nenhum."""
    # Um pacote pode ser coberto por MAIS DE UMA fonte: o arquivamento
    # original do trimestre e a coluna comparativa de um documento posterior.
    # Escolher "a última que apareceu" deixaria a reapresentada sobrescrever a
    # original e destruiria a única evidência point-in-time que existe. A
    # ordem de preferência é explícita, e empate entre originais fica com a
    # divulgação MAIS ANTIGA — a primeira que o analista pôde conhecer.
    PREFERENCIA = {
        "original": 0, "derivada_de_originais": 1,
        "derivada_sem_certificacao": 2, "as_restated": 3,
    }

    def _chave(resultado: ResultadoJ) -> tuple:
        return (
            PREFERENCIA.get(resultado.base_temporal, 9),
            resultado.disponivel_em or "9999-99-99",
        )

    por_pacote: dict[str, ResultadoJ] = {}
    alternativas: dict[str, int] = {}
    for resultado in resultados:
        alternativas[resultado.pacote_id] = (
            alternativas.get(resultado.pacote_id, 0) + 1
        )
        atual = por_pacote.get(resultado.pacote_id)
        if atual is None or _chave(resultado) < _chave(atual):
            por_pacote[resultado.pacote_id] = resultado
    dfc_por_pacote: dict[str, int] = {}
    for componente in componentes:
        fonte = next(
            f for f in FONTES if f.fonte_id == componente["fonte_id"]
        )
        chave = pacote_id(fonte.cd_cvm, componente["periodo"])
        dfc_por_pacote[chave] = dfc_por_pacote.get(chave, 0) + 1
    fatos_por_pacote: dict[str, int] = {}
    for fato in fatos:
        if fato.pacote_id:
            fatos_por_pacote[fato.pacote_id] = (
                fatos_por_pacote.get(fato.pacote_id, 0) + 1
            )

    linhas = []
    for linha_escopo in montar_escopo():
        pid = linha_escopo["pacote_id"]
        resultado = por_pacote.get(pid)
        tem_fonte = pid in fatos_por_pacote

        if not tem_fonte:
            p0 = "NAO_IDENTIFICADO"
            p1 = p2 = p4 = p3 = "PENDENTE"
            # "Não há documento" e "o documento existe mas não traz a rubrica"
            # são estados diferentes, e confundi-los produziria afirmação que a
            # evidência não sustenta.
            emissor_tem_algum = any(
                f.cd_cvm == linha_escopo["cd_cvm"]
                and f.caminho.is_file()
                for f in FONTES
            )
            if not emissor_tem_algum:
                motivo = (
                    "Nenhuma demonstração IFRS deste emissor está no corpus "
                    "local; recuperar exige rede, não autorizada nesta "
                    "execução. Ausência local não prova inexistência."
                )
            else:
                motivo = (
                    "O emissor tem demonstração IFRS local, mas nenhuma fonte "
                    "declarada cobre este período com a rubrica necessária — "
                    "no anual do BTG as rubricas da nota 21 não aparecem sob "
                    "os mesmos rótulos. Exige curadoria própria, não rede."
                )
        else:
            p0 = "CONFERIDO"
            p1 = {
                "identificado": "CONFERIDO",
                "limitado": "CONFERIDO_COM_RESIDUO",
                "nao_identificado": "NAO_IDENTIFICADO",
            }[resultado.status]
            if resultado.fechamento_confere is None:
                # Sem total declarado não há reconciliação a fazer; chamar isso
                # de conflito confundiria "não confere" com "não se aplica".
                p2 = "NAO_APLICAVEL"
            else:
                p2 = (
                    "CONFERIDO" if resultado.fechamento_confere
                    else "CONFLITANTE"
                )
            p4 = "CONFERIDO" if dfc_por_pacote.get(pid) else "PENDENTE"
            # P3 só passa quando o valor vem do arquivamento ORIGINAL do
            # período (ou de derivação entre originais) e há data de entrega
            # demonstrada por protocolo e versão. Coluna comparativa em
            # documento posterior é as-restated e nunca certifica o histórico.
            if (
                resultado.base_temporal in ("original", "derivada_de_originais")
                and resultado.disponivel_em
            ):
                p3 = "CONFERIDO"
            elif resultado.base_temporal == "original":
                # O documento é do período, mas nada demonstra QUANDO ficou
                # público: os PDFs do corpus `ifrs` vieram de sites de RI e o
                # manifesto só registra a data de download. Saber que o
                # documento é do trimestre não é saber a data em que existiu.
                p3 = "SEM_DATA_DE_PUBLICACAO"
            elif resultado.base_temporal == "as_restated":
                p3 = "NAO_IDENTIFICADO"
            else:
                p3 = "PENDENTE"
            motivo = resultado.observacao

        linhas.append(
            {
                **linha_escopo,
                "fonte_id": resultado.fonte_id if resultado else "",
                "fatos_extraidos": fatos_por_pacote.get(pid, 0),
                "j_status": resultado.status if resultado else "sem_fonte",
                # Total impresso na nota. Coluna própria porque a revisão
                # independente exigiu separar FECHAMENTO de CERTIFICADO
                # SEMÂNTICO: um pacote pode ter total, somar exato nele e
                # ainda assim não ter J identificado. Sem esta coluna a
                # distinção não era auditável a partir do CSV.
                "j_total_declarado": (
                    str(resultado.total_declarado)
                    if resultado and resultado.total_declarado is not None
                    else ""
                ),
                "j_sem_limite_demonstravel": (
                    "|".join(resultado.conceitos_sem_limite_demonstravel)
                    if resultado else ""
                ),
                "j_limite_inferior": str(resultado.limite_inferior)
                if resultado and resultado.status != "nao_identificado" else "",
                "j_limite_superior": str(resultado.limite_superior)
                if resultado and resultado.status != "nao_identificado" else "",
                "j_largura_relativa": (
                    f"{resultado.largura_relativa:.6f}"
                    if resultado and resultado.largura_relativa is not None
                    else ""
                ),
                "p0_integridade": p0,
                "p1_semantica": p1,
                "p2_aritmetica": p2,
                "p3_historico": p3,
                "base_temporal": resultado.base_temporal if resultado else "",
                # Conformidade contratual NÃO é o mesmo que P2 (aritmética).
                # Uma parcela incluída que vem credora fecha a soma e ainda
                # assim não é juros por competência. Sai em coluna própria
                # para que ninguém leia "P2 CONFERIDO" como conformidade.
                "conformidade_contratual": (
                    resultado.conformidade_contratual if resultado else ""
                ),
                "creditos_em_incluidas": (
                    ";".join(resultado.creditos_em_incluidas)
                    if resultado else ""
                ),
                "disponivel_em": (
                    (resultado.disponivel_em or "") if resultado else ""
                ),
                "fontes_alternativas": max(alternativas.get(pid, 0) - 1, 0),
                "p4_dfc": p4,
                "componentes_dfc_classificados": dfc_por_pacote.get(pid, 0),
                "motivo": motivo,
            }
        )
    return linhas


def gravar_artefatos(destino: Path, fatos, resultados, auditoria,
                     linhagem, componentes) -> dict:
    # A saída também é caminho: sem esta guarda, `--diretorio
    # corpus/holdout_2T2026` gravaria DENTRO do reservado, e um destino
    # apontado para `artefatos/indice_vetorial` sobrescreveria produção.
    verificar_caminho_permitido(destino)
    verificar_destino_isolado(destino)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "raw").mkdir(exist_ok=True)

    with open(destino / "escopo.csv", "w", newline="", encoding="utf-8") as saida:
        campos = ["pacote_id", "cd_cvm", "emissor", "periodo", "inicio", "fim"]
        escritor = csv.DictWriter(saida, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(montar_escopo())

    with open(destino / "fontes.jsonl", "w", encoding="utf-8") as saida:
        for fonte in FONTES:
            existe = fonte.caminho.is_file()
            conferido = hash_do_arquivo(fonte.caminho) if existe else None
            if conferido is not None and conferido != fonte.hash_sha256:
                # Calcular o hash e não compará-lo seria teatro: um PDF trocado
                # produziria extração de outro documento com P0 "conferido".
                raise ErroExtracao(
                    f"Hash de {fonte.arquivo} divergiu do declarado: "
                    f"{conferido} != {fonte.hash_sha256}. O documento em disco "
                    "não é o que o manifesto registra."
                )
            saida.write(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "fonte_id": fonte.fonte_id,
                "cd_cvm": fonte.cd_cvm,
                "emissor": BANCOS[fonte.cd_cvm],
                "arquivo": fonte.arquivo,
                "caminho_local": str(fonte.caminho.relative_to(RAIZ)),
                "hash_sha256_declarado": fonte.hash_sha256,
                "hash_sha256_conferido": conferido,
                "periodo_documento": fonte.periodo_documento,
                "tipo_documento": fonte.tipo_documento,
                "base_contabil": fonte.base_contabil,
                "perimetro": fonte.perimetro,
                "url": fonte.url,
                "data_download": fonte.data_download,
                "papel": "principal",
                # Data de publicação original NÃO é conhecida: o manifesto
                # registra quando o arquivo foi baixado, não quando o emissor
                # o publicou. Preencher com a data de coleta seria inventar.
                "data_publicacao_original": None,
                "disponibilidade_historica": "nao_certificada",
            }, ensure_ascii=False) + "\n")

    with open(destino / "fatos.jsonl", "w", encoding="utf-8") as saida:
        for fato in fatos:
            saida.write(json.dumps(fato.para_json(), ensure_ascii=False) + "\n")

    with open(destino / "mapa_j.jsonl", "w", encoding="utf-8") as saida:
        vistos = set()
        for nota in NOTAS:
            for rubrica in nota.rubricas:
                chave = (nota.fonte_id, rubrica.conceito)
                if chave in vistos:
                    continue
                vistos.add(chave)
                saida.write(json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "mapeamento_id": f"{nota.fonte_id}|{rubrica.conceito}",
                    "fonte_id": nota.fonte_id,
                    "nota": nota.nota,
                    "rotulo_original": rubrica.rotulo,
                    "conceito": rubrica.conceito,
                    "tratamento": rubrica.tratamento,
                    "motivo_financeiro": rubrica.motivo,
                    "versao_contrato": VERSAO_CONTRATO_J,
                    "decidido_por": "curadoria_do_piloto",
                    "revisao": "pendente",
                }, ensure_ascii=False) + "\n")

    with open(destino / "derivacoes.jsonl", "w", encoding="utf-8") as saida:
        for registro in linhagem:
            saida.write(json.dumps(registro, ensure_ascii=False) + "\n")
        for resultado in resultados:
            saida.write(
                json.dumps(resultado.para_json(), ensure_ascii=False) + "\n"
            )

    with open(destino / "componentes_dfc.jsonl", "w", encoding="utf-8") as saida:
        for componente in componentes:
            saida.write(json.dumps(componente, ensure_ascii=False) + "\n")

    with open(destino / "auditoria_pacotes.csv", "w", newline="",
              encoding="utf-8") as saida:
        escritor = csv.DictWriter(saida, fieldnames=list(auditoria[0]))
        escritor.writeheader()
        escritor.writerows(auditoria)

    resumo = {
        "schema_version": SCHEMA_VERSION,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "versao_contrato": VERSAO_CONTRATO_J,
        "pacotes_no_escopo": len(auditoria),
        "pacotes_com_fonte": sum(1 for a in auditoria if a["fatos_extraidos"]),
        "pacotes_sem_fonte": sum(
            1 for a in auditoria if not a["fatos_extraidos"]
        ),
        "j_identificado": sum(
            1 for a in auditoria if a["j_status"] == "identificado"
        ),
        "j_limitado": sum(1 for a in auditoria if a["j_status"] == "limitado"),
        "j_nao_identificado": sum(
            1 for a in auditoria if a["j_status"] == "nao_identificado"
        ),
        "p2_conferido": sum(
            1 for a in auditoria if a["p2_aritmetica"] == "CONFERIDO"
        ),
        "rubricas_com_conformidade_nao_demonstrada": sorted({
            conceito for r in resultados for conceito in r.creditos_em_incluidas
        }),
        "p3_historico_conferido": sum(
            1 for a in auditoria if a["p3_historico"] == "CONFERIDO"
        ),
        "fatos_extraidos": len(fatos),
        "componentes_dfc_classificados": len(componentes),
        "componentes_dfc_redundantes": sum(
            1 for c in componentes
            if c["classificacao"] == "repeticao_de_diferenca_de_estoques"
        ),
        # Emissor pode ter documento para um período e não para outro: o
        # Santander e o BTG têm IFRS local só de parte da janela. Chamar isso
        # de "emissor sem documento" seria falso.
        "emissores_sem_nenhum_documento": sorted({
            cd for cd in BANCOS
            if not any(
                a["fatos_extraidos"] for a in auditoria if a["cd_cvm"] == cd
            )
        }),
        "pacotes_sem_fonte_por_emissor": {
            cd: sum(
                1 for a in auditoria
                if a["cd_cvm"] == cd and not a["fatos_extraidos"]
            )
            for cd in sorted(BANCOS)
        },
        "limites": [
            "Identificação é as-restated: valores de 2024 vêm de coluna "
            "comparativa em documento de 2025. Não demonstra disponibilidade "
            "histórica (P3).",
            "Nenhum gate autoriza treino; suficiência estatística não foi "
            "avaliada e não é objeto deste piloto.",
        ],
    }
    (destino / "auditoria.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    caminhos_lidos = sorted({
        str(f.caminho.relative_to(RAIZ)) for f in FONTES if f.caminho.is_file()
    })
    execucao = {
        "schema_version": SCHEMA_VERSION,
        "fim_utc": datetime.now(timezone.utc).isoformat(),
        "versao_contrato": VERSAO_CONTRATO_J,
        "comando": "python -m scripts.piloto_bancos_dfc auditar",
        # A AUDITORIA é offline e determinística: lê PDFs de disco e reescreve
        # os artefatos. A COLETA que trouxe 11 documentos do catálogo IPE em
        # 2026-09-09 usou rede — registrar "rede_utilizada: false" sem essa
        # distinção seria falso sobre como os dados chegaram aqui.
        "rede_utilizada_nesta_execucao": False,
        "rede_utilizada_na_coleta": {
            "data": "2026-09-09",
            "documentos": 11,
            "origem": "catálogo IPE da CVM (dados.cvm.gov.br) e rad.cvm.gov.br",
            "gratuito": True,
            "validacao": (
                "PDF completo (assinatura, %%EOF e parse) mais SHA-256 "
                "conferido contra o declarado antes de cada leitura"
            ),
        },
        "chamadas_pagas": 0,
        "custo_efetivo_usd": 0.0,
        "entradas_somente_leitura": True,
        "arquivos_lidos": caminhos_lidos,
        # Verificado contra os caminhos efetivamente abertos, não declarado
        # por conveniência: o plano proíbe escrever `holdout_acessado=false`
        # sem conferir.
        "holdout_acessado": any(
            proibido in caminho
            for caminho in caminhos_lidos
            for proibido in CAMINHOS_PROIBIDOS
        ),
        "paineis_alterados": [],
        "corpora_alterados": [],
        "revisao_conformidade": "pendente",
    }
    (destino / "execucao.json").write_text(
        json.dumps(execucao, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )

    (destino / "README.md").write_text(_readme(resumo), encoding="utf-8")
    return resumo


def _readme(resumo: dict) -> str:
    return f"""# Artefatos do piloto documental B-DFC-01J

Gerados por `scripts/piloto_bancos_dfc.py`. **Não são amostra supervisionada**
e nenhum gate aqui autoriza treino.

## Regeneração

```bash
python -m scripts.piloto_bancos_dfc auditar
```

Roda offline, sem rede e sem chamada paga: lê os PDFs já versionados do corpus
`ifrs` e reescreve todos os arquivos abaixo de forma determinística.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `escopo.csv` | Os {resumo['pacotes_no_escopo']} pacotes do escopo, por construção |
| `fontes.jsonl` | Documentos usados, com hash conferido |
| `fatos.jsonl` | Cada cifra com página, coluna, unidade, período e evidência |
| `mapa_j.jsonl` | Decisão semântica por rubrica, com motivo financeiro |
| `derivacoes.jsonl` | Linhagem dos derivados e o J de cada pacote |
| `componentes_dfc.jsonl` | Linhas da DFC confrontadas com o balanço |
| `auditoria_pacotes.csv` | Uma linha por pacote, inclusive os sem documento |
| `auditoria.json` | Contagens derivadas da tabela, nunca digitadas |
| `execucao.json` | Rede, custo, arquivos lidos e exposição ao holdout |

## Limites que não podem ser lidos a menos

- A identificação é **as-restated**: os valores de 2024 vêm de coluna
  comparativa em documento de 2025. Nenhum pacote tem P3 conferido.
- `j_limite_inferior` e `j_limite_superior` delimitam J; não há ponto estimado.
  Onde J não foi identificado os dois campos ficam **vazios**, não zero.
- Cobertura documental não é tamanho de amostra nem poder estatístico.
"""


def inventariar_documentos(painel: Path, destino: Path) -> dict:
    """Onda 1: cruza os 25 pacotes com o cadastro `documentos` da CVM.

    Cadastro de arquivamento **não é** peça IFRS: o ITR/DFP da CVM é BRGAAP e
    não fornece a composição de J. O inventário serve para saber quais versões
    existem e quando foram recebidas, não para extrair valor.
    """
    import duckdb  # dependência já instalada; import local mantém o resto leve

    verificar_caminho_permitido(painel)
    verificar_caminho_permitido(destino)
    verificar_destino_isolado(destino)
    if not painel.is_file():
        raise ErroExtracao(f"Painel não encontrado: {painel}")

    conexao = duckdb.connect(str(painel), read_only=True)
    try:
        registros = conexao.execute(
            """
            SELECT cd_cvm, conjunto, dt_refer, versao, id_doc, dt_receb
            FROM documentos
            WHERE cd_cvm IN (?, ?, ?, ?, ?)
            ORDER BY cd_cvm, dt_refer, conjunto, versao
            """,
            list(BANCOS),
        ).fetchall()
    finally:
        conexao.close()

    fins = {periodo: fim for periodo, (_, fim) in PERIODOS.items()}
    por_pacote: dict[str, list[dict]] = {}
    for cd_cvm, conjunto, dt_refer, versao, id_doc, dt_receb in registros:
        periodo = next(
            (p for p, fim in fins.items() if fim == dt_refer), None
        )
        if periodo is None:
            continue
        por_pacote.setdefault(pacote_id(cd_cvm, periodo), []).append({
            "conjunto": conjunto,
            "dt_refer": dt_refer.isoformat(),
            "versao": versao,
            "id_doc": str(id_doc),
            "dt_receb": dt_receb.isoformat() if dt_receb else None,
        })

    destino.mkdir(parents=True, exist_ok=True)
    linhas = []
    for linha in montar_escopo():
        arquivamentos = por_pacote.get(linha["pacote_id"], [])
        linhas.append({
            "schema_version": SCHEMA_VERSION,
            **linha,
            "arquivamentos_cvm": len(arquivamentos),
            "versoes": sorted({a["versao"] for a in arquivamentos}),
            "detalhe": arquivamentos,
            "base_contabil_do_cadastro": "BRGAAP (ITR/DFP da CVM)",
            "serve_para_J": False,
            "motivo": (
                "Cadastro de arquivamento dá versão e data de recepção; a "
                "composição de J vive nas notas das demonstrações IFRS, que "
                "são documento separado."
            ),
        })
    with open(destino / "inventario_cvm.jsonl", "w", encoding="utf-8") as saida:
        for linha in linhas:
            saida.write(json.dumps(linha, ensure_ascii=False) + "\n")

    return {
        "pacotes": len(linhas),
        "pacotes_com_arquivamento": sum(
            1 for l in linhas if l["arquivamentos_cvm"]
        ),
        "arquivamentos": sum(l["arquivamentos_cvm"] for l in linhas),
        "pacotes_multiversao": sum(
            1 for l in linhas if len(l["versoes"]) > 1
        ),
    }


def _cli() -> argparse.ArgumentParser:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "comando",
        choices=["inventariar", "coletar", "auditar", "estender"]
    )
    analisador.add_argument(
        "--diretorio", default="artefatos/b_dfc_01j",
        help="Destino dos artefatos do piloto.",
    )
    analisador.add_argument(
        "--painel", default="artefatos/cvm_treino.duckdb",
        help="Painel DuckDB, aberto SOMENTE LEITURA, para o inventário.",
    )
    analisador.add_argument(
        "--permitir-rede", action="store_true",
        help="Sem esta opção nenhuma etapa baixa nada (contrato do piloto).",
    )
    return analisador


def main(argv: Sequence[str] | None = None) -> int:
    args = _cli().parse_args(argv)
    destino = RAIZ / args.diretorio

    if args.comando == "coletar" and not args.permitir_rede:
        print(
            "Coleta exige --permitir-rede. Nenhuma requisição foi feita.\n"
            "Os pacotes de Itaú e Bradesco e os trimestres de 2024 originais "
            "dependem de recuperação em rede, que não foi autorizada."
        )
        return 0
    if args.comando == "coletar":
        print(
            "Coleta em rede não implementada nesta onda: o piloto foi "
            "concluído com as fontes locais e a lacuna está declarada em "
            "auditoria_pacotes.csv (P0=NAO_IDENTIFICADO)."
        )
        return 0

    if args.comando == "estender":
        resumo = executar_extensao(args.permitir_rede)
        print(f"Documentos no manifesto: {resumo['documentos_no_manifesto']}")
        print(f"  coletados:             {resumo['documentos_coletados']}")
        print(f"  extraídos:             {resumo['documentos_extraidos']}")
        print(f"Pares emissor-trimestre: "
              f"{resumo['pares_emissor_trimestre_distintos']}  "
              f"({resumo['janela']})")
        print(f"  registros (com safras): {resumo['registros_utilizaveis']}")
        print(f"  por emissor:           {resumo['trimestres_por_emissor']}")
        print(f"  4T derivados:          "
              f"{resumo['quartos_trimestres_derivados']} "
              f"(recusados: {len(resumo['quartos_trimestres_recusados'])})")
        print(f"Identidades conferidas:  {resumo['identidades_conferidas']} "
              f"(divergentes: {len(resumo['identidades_divergentes'])})")
        if resumo["documentos_faltando"]:
            print(f"FALTANDO: {len(resumo['documentos_faltando'])}")
        return 0

    if args.comando == "inventariar":
        resumo = inventariar_documentos(RAIZ / args.painel, destino)
        print(f"Pacotes: {resumo['pacotes']}")
        print(f"  com arquivamento na CVM: {resumo['pacotes_com_arquivamento']}")
        print(f"  multiversão:             {resumo['pacotes_multiversao']}")
        print(f"Arquivamentos listados:    {resumo['arquivamentos']}")
        print(f"Inventário em {destino / 'inventario_cvm.jsonl'}")
        return 0

    fatos, resultados, linhagem, componentes = executar_extracao()
    auditoria = montar_auditoria(fatos, resultados, componentes)
    resumo = gravar_artefatos(
        destino, fatos, resultados, auditoria, linhagem, componentes
    )

    print(f"Pacotes no escopo: {resumo['pacotes_no_escopo']}")
    print(f"  com fonte local: {resumo['pacotes_com_fonte']}")
    print(f"  sem fonte:       {resumo['pacotes_sem_fonte']}")
    print(f"J identificado:      {resumo['j_identificado']}")
    print(f"J limitado:          {resumo['j_limitado']}")
    print(f"J não identificado:  {resumo['j_nao_identificado']}")
    print(f"P3 (histórico) conferido: {resumo['p3_historico_conferido']}")
    print(f"Artefatos em {destino}")
    return 0




# ---------------------------------------------------------------------------
# Extensão da janela (2026-09-09) — onda separada, escopo próprio
# ---------------------------------------------------------------------------
#
# O piloto congelou 25 pacotes (5 emissores × 2024T1–2025T1) e esse denominador
# NÃO muda: mexer nele invalidaria o resultado publicado. A extensão é uma onda
# nova, com escopo, artefatos e relatório próprios.
#
# Duas decisões de desenho, e as duas vêm de erro já medido neste projeto:
#
# 1. **A página da nota é LOCALIZADA, não declarada.** Fixar número de página
#    para ~50 documentos de sete anos seria curadoria impossível de auditar, e
#    o número muda a cada trimestre.
# 2. **A ordem das colunas é declarada por emissor e CONFERIDA por identidade
#    aritmética.** `scripts/gate_g4.py` já registrou que a ordem entre isolado
#    e acumulado "muda de emissor para emissor" — o BB imprime acumulado
#    primeiro, o Itaú imprime isolado primeiro. Confiar em posição sem conferir
#    atribuiria o trimestre à coluna do semestre em silêncio.

#: Papéis de coluna. `iso` = período isolado do documento; `acum` = acumulado
#: do exercício até a data-base; sufixo `_aa` = mesmo papel no ano anterior.
LAYOUTS_POR_EMISSOR: dict[str, dict[int, tuple[str, ...]]] = {
    # Itaú: isolado primeiro, depois acumulado.
    "019348": {2: ("iso", "iso_aa"), 4: ("iso", "iso_aa", "acum", "acum_aa"),
               3: ("acum", "acum_aa", "acum_aa2")},
    # Bradesco: mesma ordem do Itaú.
    "000906": {2: ("iso", "iso_aa"), 4: ("iso", "iso_aa", "acum", "acum_aa"),
               3: ("acum", "acum_aa", "acum_aa2")},
    # BB: ACUMULADO primeiro — a diferença que a conferência tem de pegar.
    "001023": {2: ("iso", "iso_aa"), 4: ("acum", "acum_aa", "iso", "iso_aa"),
               3: ("acum", "acum_aa", "acum_aa2")},
}

#: Âncora de seção e rubricas por emissor, para a extensão.
#: Rubricas do BB na era 2020–2023, quando a nota era MAIS granular: separava
#: compromissadas, depósitos, títulos emitidos, instituições financeiras e —
#: melhor para o contrato — **passivos de arrendamento** em linha própria, que
#: o contrato exclui nominalmente. De 2024 em diante o BB consolidou tudo em
#: três rubricas mais amplas.
_RUBRICAS_BB_2020_2023 = (
    Rubrica(
        "Despesas de juros", "despesa_juros_total", _TOTAL,
        "Total da nota; confere a soma das parcelas.",
    ),
    Rubrica(
        "Obrigações por operações compromissadas",
        "juros_compromissadas", _INCLUIR,
        "Operações compromissadas — captação incluída no contrato.",
    ),
    Rubrica(
        "Depósitos de clientes", "juros_depositos_clientes", _INCLUIR,
        "Depósitos de clientes — incluídos no contrato.",
    ),
    Rubrica(
        "Obrigações com instituições financeiras",
        "juros_obrigacoes_instituicoes_financeiras", _INCLUIR,
        "Captação junto a instituições financeiras — incluída no contrato.",
    ),
    Rubrica(
        "Obrigações por emissão de títulos",
        "juros_titulos_emitidos_e_outras_obrigacoes", _NAO_IDENT,
        "A linha impressa é 'Obrigações por emissão de títulos e valores "
        "mobiliários E OUTRAS OBRIGAÇÕES': junta títulos emitidos (incluídos) "
        "com um residual sem composição. O contrato proíbe estimar a parcela "
        "ausente, então ela entra como não identificada e J sai como intervalo.",
    ),
    Rubrica(
        "Passivos de arrendamento", "juros_arrendamento", _EXCLUIR,
        "Juros de arrendamento, que o contrato exclui nominalmente. Aqui vem "
        "em linha própria com valor — a exclusão é leitura, não estimativa.",
    ),
)

#: Por emissor: (sonda de PÁGINA, início da SEÇÃO, fim da seção, rubricas,
#: unidade). A sonda é regex e precisa ser exclusiva da nota — "Despesa de
#: juros e similares" sozinha também casa na DRE, e "Recursos de emissões de
#: títulos" aparece em nove páginas do BB. Página e seção são coisas
#: diferentes: uma acha o lugar, a outra delimita a tabela.
#: Perfis alternativos por emissor, tentados em ordem. O emissor MUDA a
#: estrutura da nota entre eras — o BB era mais granular até 2023 — e um perfil
#: único recusaria oito documentos válidos. A conferência de fechamento decide
#: qual perfil serve àquele ano: se a soma não der o total impresso, o perfil
#: está errado e o documento não passa.
PERFIS_ALTERNATIVOS: dict[str, tuple[tuple[Rubrica, ...], ...]] = {
    "001023": (_RUBRICAS_BB_2020_2023,),
}

ANCORAS_POR_EMISSOR: dict[
    str, tuple[str, str, str, tuple[Rubrica, ...], str]
] = {
    "000906": (
        # O título numerado da nota é estável de 2022 a 2026; a linha de
        # exclusão que servia de sonda ("Provisões técnicas de capitalização")
        # só existe nos documentos recentes e recusava 24 documentos válidos.
        # `$` exclui a linha do SUMÁRIO, com pontilhado e número de página.
        r"\d+\)\s*RESULTADO LÍQUIDO DE JUROS\s*$",
        "Despesa de juros e similares", "Total",
        _RUBRICAS_BRADESCO, "milhares_de_reais",
    ),
    "019348": (
        # Até 2020 o Itaú chamava a rubrica de "Rendimentos"; de 2021 em
        # diante, "Similares". Mesma nota (21b), redação diferente.
        r"b\)\s*Despesas de Juros e (Similares|Rendimentos)",
        "b) Despesas de Juros e Similares|b) Despesas de Juros e Rendimentos",
        "Total",
        _RUBRICAS_ITAU, "milhoes_de_reais",
    ),
    "001023": (
        # `$` no fim exclui a linha do SUMÁRIO, que traz pontilhado e o
        # número da página depois do mesmo título.
        # `\s*` em volta do travessão: o BB imprime "5– " nos documentos
        # recentes e "5 – " nos de 2022. `$` exclui a linha do SUMÁRIO.
        r"\d+\s*[–-]\s*Receita líquida de juros\s*$",
        "Despesas de juros", "Receita líquida de juros",
        _RUBRICAS_BB, "milhares_de_reais",
    ),
}


def localizar_pagina_da_nota(
    caminho: Path, ancora: str, maximo_paginas: int = 400
) -> int:
    """Acha a única página em que a seção da nota começa.

    Exige unicidade: âncora que aparece em duas páginas é ambiguidade, e
    escolher a primeira decidiria em silêncio qual tabela vale.
    """
    verificar_caminho_permitido(caminho)
    if not caminho.is_file():
        raise ErroExtracao(f"Documento ausente: {caminho}")
    info = subprocess.run(
        ["pdfinfo", str(caminho)], capture_output=True, text=True, timeout=120
    ).stdout
    casamento = re.search(r"Pages:\s+(\d+)", info)
    if not casamento:
        raise ErroExtracao(f"Não foi possível contar páginas de {caminho}")
    total = min(int(casamento.group(1)), maximo_paginas)

    # A sonda é uma expressão regular ancorada no início da linha: o BB
    # numera a nota ("5– Receita líquida de juros" no trimestral, "7– …" no
    # anual) e um prefixo fixo não serviria para os dois.
    padrao = re.compile(ancora, re.IGNORECASE)
    achadas = []
    for pagina in range(1, total + 1):
        texto = subprocess.run(
            ["pdftotext", "-f", str(pagina), "-l", str(pagina), "-layout",
             str(caminho), "-"],
            capture_output=True, text=True, timeout=120,
        ).stdout
        if any(padrao.match(l.strip()) for l in texto.splitlines()):
            achadas.append(pagina)
    if not achadas:
        raise ErroExtracao(f"Âncora {ancora!r} não encontrada em {caminho.name}")
    if len(achadas) > 1:
        raise ErroExtracao(
            f"Âncora {ancora!r} aparece em {len(achadas)} páginas de "
            f"{caminho.name} ({achadas}); ambígua."
        )
    return achadas[0]


def periodos_dos_papeis(
    papeis: Sequence[str], periodo_documento: str
) -> tuple[str, ...]:
    """Traduz papéis de coluna em períodos concretos.

    `2024T3` como período do documento produz `iso`=2024T3, `acum`=2024M9,
    `iso_aa`=2023T3, `acum_aa`=2023M9.
    """
    ano = int(periodo_documento[:4])
    marca = periodo_documento[4:]
    anual = not marca.startswith("T")
    trimestre = int(marca[1]) if marca.startswith("T") else 4
    acumulados = {1: "T1", 2: "S1", 3: "M9", 4: "A"}

    def montar(ano_alvo: int, papel: str) -> str:
        # Demonstração ANUAL não publica coluna de trimestre isolado: todas as
        # colunas são o exercício inteiro. Tratar a primeira como "4º
        # trimestre" rotularia o ano inteiro de trimestre — e o 4T sai por
        # derivação (anual − 9M), nunca por leitura direta.
        if papel.startswith("iso") and not anual:
            return f"{ano_alvo}T{trimestre}"
        return f"{ano_alvo}{acumulados[trimestre]}"

    saida = []
    for papel in papeis:
        deslocamento = 2 if papel.endswith("aa2") else 1 if papel.endswith("aa") else 0
        saida.append(montar(ano - deslocamento, papel))
    return tuple(saida)


DIR_EXTENSAO = RAIZ / "artefatos" / "b_dfc_01j" / "extensao"
DIR_EXTENSAO_RAW = RAIZ / "artefatos" / "b_dfc_01j" / "raw"


#: Sessão do `rad.cvm.gov.br`. **Não é enfeite:** o host emite
#: `ASP.NET_SessionId` e cookies de balanceador, e requisição sem sessão
#: estabelecida devolve página HTML de erro em vez do documento. Medido: com
#: cookie novo veio "Erro" de 4 KB; com a sessão aquecida, o PDF de 2,4 MB.
COOKIES_CVM = RAIZ / "artefatos" / "b_dfc_01j" / "extensao" / ".cookies_cvm"

#: Identificação honesta do agente. Sem `User-Agent` próprio o host trata a
#: requisição de forma diferente; declarar quem está pedindo é o mínimo.
AGENTE_HTTP = "Mozilla/5.0 (compatible; pesquisa academica; dados publicos CVM)"


def baixar_documento(url: str, destino: Path, tentativas: int = 5) -> str:
    """Baixa e VALIDA estruturalmente, devolvendo o SHA-256.

    A validação não é zelo: o `rad.cvm.gov.br` responde `HTTP 200` com
    `Content-Type: text/html`, entrega um corpo que **começa** com `%PDF` e
    corta a conexão no meio. Como usa `Transfer-Encoding: chunked` não há
    `Content-Length` para conferir, e `Range` não é honrado — só a estrutura
    do PDF denuncia o truncamento. Medido: 1,78 MB aceitos no lugar de 2,41 MB.

    O truncamento é **intermitente**, então a retomada é por nova tentativa
    inteira com espera crescente. Documento que não fecha depois de todas as
    tentativas é registrado como falha de ACESSO — nunca como inexistente.
    """
    verificar_caminho_permitido(destino)
    COOKIES_CVM.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".parcial")
    for tentativa in range(1, tentativas + 1):
        subprocess.run(
            ["curl", "-sS", "--max-time", "420", "--http1.1",
             "-c", str(COOKIES_CVM), "-b", str(COOKIES_CVM),
             "-A", AGENTE_HTTP, "-o", str(parcial), url],
            capture_output=True, text=True,
        )
        if parcial.is_file() and _pdf_esta_integro(parcial):
            parcial.replace(destino)
            return hash_do_arquivo(destino)
        if tentativa < tentativas:
            time.sleep(4 * tentativa)
    parcial.unlink(missing_ok=True)
    raise ErroExtracao(
        f"Download de {destino.name} não produziu PDF íntegro em "
        f"{tentativas} tentativas. Falha de ACESSO — não é prova de que o "
        "documento não exista."
    )


def _pdf_esta_integro(caminho: Path) -> bool:
    with open(caminho, "rb") as arquivo:
        if arquivo.read(5)[:4] != b"%PDF":
            return False
        arquivo.seek(max(0, caminho.stat().st_size - 2048))
        if b"%%EOF" not in arquivo.read():
            return False
    return subprocess.run(
        ["pdfinfo", str(caminho)], capture_output=True
    ).returncode == 0


def divergencias_de_vintage(fatos: Sequence[Fato]) -> list[dict]:
    """Períodos cujo valor MUDA conforme o documento que os publica.

    Não é defeito de leitura: é reapresentação do emissor, e medi-la é entrega.
    Medido no Bradesco de 2022 — o 1º semestre sai `-59.901.357` no próprio
    documento de 2022 e `-57.759.632` como comparativo no de 2023, diferença de
    3,6%. É a prova concreta de que *as-restated* não é *as-originally-reported*.
    """
    por_periodo: dict[tuple[str, str], list[Fato]] = {}
    for fato in fatos:
        if fato.conceito != "despesa_juros_total":
            continue
        por_periodo.setdefault((fato.cd_cvm_do_fato, fato.periodo), []).append(fato)

    saida = []
    for (cd_cvm, periodo), lista in sorted(por_periodo.items()):
        valores = {f.valor for f in lista}
        if len(valores) < 2:
            continue
        original = next(
            (f for f in lista if f.origem_periodo == "propria"), None
        )
        saida.append({
            "schema_version": SCHEMA_VERSION,
            "cd_cvm": cd_cvm,
            "periodo": periodo,
            "conceito": "despesa_juros_total",
            "valores_por_fonte": {
                f.fonte_id: {
                    "valor": str(f.valor),
                    "origem": f.origem_periodo,
                    "disponivel_em": f.disponivel_em,
                }
                for f in sorted(lista, key=lambda x: x.fonte_id)
            },
            "valor_original": str(original.valor) if original else None,
            "amplitude": str(max(valores) - min(valores)),
            "leitura": (
                "Reapresentação do emissor. O valor original e o reapresentado "
                "ficam ambos registrados; nenhum sobrescreve o outro."
            ),
        })
    return saida


def conferir_identidade_trimestral(fatos: Sequence[Fato]) -> list[dict]:
    """Confere que os trimestres isolados somam ao acumulado publicado.

    É a contraprova que valida o mapeamento de colunas SEM confiar em posição:
    T1+T2 tem de dar S1, e T1+T2+T3 tem de dar M9 — com os operandos vindo de
    documentos DIFERENTES. Se a ordem das colunas estivesse trocada, não
    fecharia. É o mesmo método que `scripts/ancora_ifrs.py` já usa para
    resolver a cadeia trimestral.

    **A identidade só vale dentro do mesmo vintage.** Somar um trimestre
    reapresentado com um semestre original acusaria divergência que é do
    emissor, não do mapeamento — foi o que aconteceu no Bradesco de 2022 e por
    isso a conferência agora exige base consistente e, quando não há, devolve
    `nao_verificavel` em vez de `diverge`.
    """
    por_chave: dict[tuple[str, str], list[Fato]] = {}
    for fato in fatos:
        if fato.conceito != "despesa_juros_total":
            continue
        por_chave.setdefault((fato.cd_cvm_do_fato, fato.periodo), []).append(fato)

    conferencias = []
    anos = sorted({p[:4] for (_, p) in por_chave})
    for cd_cvm in sorted({c for (c, _) in por_chave}):
        for ano in anos:
            def candidatos(marca: str) -> list[Fato]:
                return por_chave.get((cd_cvm, f"{ano}{marca}"), [])

            for acumulado, parcelas in (("S1", ("T1", "T2")),
                                        ("M9", ("T1", "T2", "T3")),
                                        ("A", ("T1", "T2", "T3", "T4"))):
                grupos = [candidatos(m) for m in (*parcelas, acumulado)]
                if any(not g for g in grupos):
                    continue

                escolhido, base = None, None
                # 1ª preferência: todos os operandos no vintage ORIGINAL.
                if all(any(f.origem_periodo == "propria" for f in g)
                       for g in grupos):
                    escolhido = [
                        next(f for f in g if f.origem_periodo == "propria")
                        for g in grupos
                    ]
                    base = "original"
                else:
                    # 2ª: todos vindos do MESMO documento comparativo.
                    comuns = set.intersection(
                        *({f.fonte_id for f in g} for g in grupos)
                    )
                    if comuns:
                        fonte = sorted(comuns)[0]
                        escolhido = [
                            next(f for f in g if f.fonte_id == fonte)
                            for g in grupos
                        ]
                        base = f"comparativa_de_{fonte}"

                registro = {
                    "schema_version": SCHEMA_VERSION,
                    "cd_cvm": cd_cvm,
                    "ano": ano,
                    "identidade": f"{'+'.join(parcelas)} = {acumulado}",
                }
                if escolhido is None:
                    conferencias.append({
                        **registro,
                        "base": "mista",
                        "confere": None,
                        # Achado F11: identidade não verificável certamente não
                        # é verificação independente. O campo sai explícito nos
                        # DOIS ramos, para que filtrar por ele dê a resposta
                        # certa sem ter de saber por qual ramo o registro veio.
                        "independente": False,
                        "motivo_nao_independente": (
                            "Identidade não verificável: operandos em vintages "
                            "diferentes, nada foi conferido."
                        ),
                        "motivo": (
                            "Operandos só existem em vintages diferentes; somar "
                            "reapresentado com original mediria reapresentação, "
                            "não o mapeamento de colunas."
                        ),
                    })
                    continue
                soma = sum((f.valor for f in escolhido[:-1]), Decimal(0))
                alvo = escolhido[-1].valor
                # Achado F11: uma identidade cujo operando foi DERIVADO do
                # próprio acumulado fecha por construção. `T4 = A − M9` torna
                # `M9 + T4 = A` uma tautologia algébrica, não uma contraprova
                # independente do mapeamento de colunas. Publicar as duas
                # como se fossem a mesma coisa foi o que produziu o
                # "15 de 15 identidades anuais" que o artefato não contém.
                # Contrato C5 do parecer de 11/09: isto inspecionava
                # `escolhido[:-1]`, que EXCLUI o acumulado — justamente o
                # operando que pode ter sido derivado das parcelas. Contraprova
                # do parecer: T1=−100, T2=−100 e S1=−200 com S1 derivado saía
                # `confere=True, independente=True`. Uma soma comparada a um
                # acumulado derivado DELA fecha por construção; é a mesma
                # tautologia do F11, na outra ponta da identidade.
                rotulos = [*parcelas, acumulado]
                derivadas = [
                    f"{rotulos[i]} ({f.conceito})"
                    for i, f in enumerate(escolhido)
                    if f.origem_periodo == "derivada"
                ]
                independente = not derivadas
                conferencias.append({
                    **registro,
                    "base": base,
                    "fontes": [f.fonte_id for f in escolhido],
                    "soma_das_parcelas": str(soma),
                    "acumulado_publicado": str(alvo),
                    "residuo": str(soma - alvo),
                    "confere": soma == alvo,
                    "independente": independente,
                    "motivo_nao_independente": None if independente else (
                        "Operando(s) derivado(s): "
                        f"{', '.join(derivadas)}. Identidade com operando "
                        "derivado fecha por construção e NÃO é contraprova "
                        "independente do mapeamento de colunas — vale tanto "
                        "para parcela quanto para o ACUMULADO (contrato C5)."
                    ),
                    "operandos_derivados": derivadas,
                })
    return conferencias


def _fontes_da_extensao() -> list[Fonte]:
    """Lê o manifesto da extensão e monta as fontes, sem página declarada."""
    caminho = DIR_EXTENSAO / "manifesto_extensao.csv"
    if not caminho.is_file():
        raise ErroExtracao(f"Manifesto da extensão ausente: {caminho}")
    fontes = []
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            fontes.append(Fonte(
                fonte_id=linha["fonte_id"],
                cd_cvm=linha["cd_cvm"],
                arquivo=linha["arquivo"],
                hash_sha256="",  # preenchido na coleta
                periodo_documento=linha["periodo_documento"],
                tipo_documento=(
                    "demonstracoes_anuais"
                    if linha["periodo_documento"].endswith("A")
                    else "demonstracoes_intermediarias_condensadas"
                ),
                diretorio="artefatos/b_dfc_01j/raw",
                url=linha["url"],
                data_download="2026-09-09",
                data_entrega=linha["data_entrega"],
                versao=int(linha["versao"]),
                protocolo=linha["protocolo"],
            ))
    return fontes


def derivacoes_automaticas(
    fatos: Sequence[Fato], fontes: Sequence[Fonte]
) -> tuple[list[DerivacaoTrimestre], list[dict]]:
    """Gera `Q4 = A − M9` para todo (emissor, ano) cujos operandos existam.

    **O 4º trimestre não é publicado isolado por nenhum dos emissores:** a
    demonstração anual traz o exercício inteiro. Sem derivar, um trimestre em
    cada quatro falta na série e **nenhuma janela de doze meses fecha** — é o
    mesmo defeito medido no §3.14 do AGENTS.md, quando a DFC isolada só existia
    no 1T e no 4T e dois trimestres por ano nunca fechavam TTM.

    A derivação é **recusada** quando os dois operandos não estão na mesma
    safra. Subtrair um acumulado de nove meses reapresentado de um anual
    original devolve um número que não é a diferença de nada: a reapresentação
    do Bradesco de 2022 mediu **3,6%** entre as duas safras do mesmo semestre.
    A recusa é registrada com o motivo — lacuna declarada, nunca silenciosa.
    """
    ano_do_documento = {f.fonte_id: f.periodo_documento[:4] for f in fontes}
    por_periodo: dict[tuple[str, str, str], list[Fato]] = collections.defaultdict(list)
    for fato in fatos:
        por_periodo[(fato.cd_cvm_do_fato, fato.periodo, fato.fonte_id)].append(fato)

    def safras(cd_cvm: str, periodo: str) -> dict[str, str]:
        """fonte_id → safra da coluna, para os candidatos a operando."""
        saida = {}
        for (cd, per, fonte_id), grupo in por_periodo.items():
            if cd != cd_cvm or per != periodo:
                continue
            origens = {f.origem_periodo for f in grupo}
            # Coluna com origem ambígua não entra: a safra tem de ser uma só.
            if len(origens) == 1:
                saida[fonte_id] = origens.pop()
        return saida

    anos = sorted({
        (f.cd_cvm_do_fato, f.periodo[:4]) for f in fatos if f.periodo.endswith("A")
    })
    derivacoes: list[DerivacaoTrimestre] = []
    recusas: list[dict] = []
    for cd_cvm, ano in anos:
        totais = safras(cd_cvm, f"{ano}A")
        parciais = safras(cd_cvm, f"{ano}M9")
        if not totais or not parciais:
            recusas.append({
                "schema_version": SCHEMA_VERSION,
                "cd_cvm": cd_cvm,
                "periodo_alvo": f"{ano}T4",
                "status": "recusada",
                "motivo": (
                    f"Operando ausente: {ano}A em {len(totais)} fonte(s), "
                    f"{ano}M9 em {len(parciais)}. Derivar exige os dois."
                ),
            })
            continue

        candidatos = []
        for fonte_total, safra_total in sorted(totais.items()):
            for fonte_parcial, safra_parcial in sorted(parciais.items()):
                if safra_total != safra_parcial:
                    continue  # safra mista: recusado abaixo
                if safra_total == "propria":
                    candidatos.append((0, fonte_total, fonte_parcial, safra_total))
                elif ano_do_documento.get(fonte_total) == ano_do_documento.get(
                    fonte_parcial
                ):
                    # Duas colunas comparativas reapresentadas no MESMO
                    # exercício: base de revisão provavelmente igual, mas isso
                    # não foi conferido linha a linha — vira ressalva.
                    candidatos.append((1, fonte_total, fonte_parcial, safra_total))
        if not candidatos:
            recusas.append({
                "schema_version": SCHEMA_VERSION,
                "cd_cvm": cd_cvm,
                "periodo_alvo": f"{ano}T4",
                "status": "recusada",
                "motivo": (
                    "Nenhum par de operandos na mesma safra. Safras de "
                    f"{ano}A: {sorted(set(totais.values()))}; de {ano}M9: "
                    f"{sorted(set(parciais.values()))}. Misturar safra "
                    "produziria diferença entre bases distintas, não o 4T."
                ),
            })
            continue

        posto, fonte_total, fonte_parcial, safra = min(candidatos)
        ressalva = (
            "Os DOIS operandos são arquivamentos ORIGINAIS do próprio "
            "exercício: o derivado estava calculável na entrega do anual e é "
            "point-in-time."
            if posto == 0 else
            "Os dois operandos são colunas COMPARATIVAS de documentos do "
            f"exercício {ano_do_documento.get(fonte_total)}. Mesma safra "
            "aparente, não conferida linha a linha: a disponibilidade não é "
            "certificada."
        )
        derivacoes.append(DerivacaoTrimestre(
            cd_cvm, f"{ano}T4", fonte_total, f"{ano}A",
            fonte_parcial, f"{ano}M9", ressalva,
        ))
    return derivacoes, recusas


def executar_extensao(permitir_rede: bool) -> dict:
    """Baixa, extrai e confere a janela estendida.

    A extensão é onda separada: **não toca** os 25 pacotes congelados do
    piloto. Ela responde uma pergunta diferente — "até onde a série de J vai" —
    e por isso tem escopo, artefatos e denominador próprios.
    """
    DIR_EXTENSAO.mkdir(parents=True, exist_ok=True)
    fontes = _fontes_da_extensao()

    coletados, faltando, hashes = [], [], {}
    for fonte in fontes:
        if fonte.caminho.is_file():
            hashes[fonte.fonte_id] = hash_do_arquivo(fonte.caminho)
            coletados.append(fonte.fonte_id)
            continue
        if not permitir_rede:
            faltando.append(fonte.fonte_id)
            continue
        try:
            hashes[fonte.fonte_id] = baixar_documento(fonte.url, fonte.caminho)
            coletados.append(fonte.fonte_id)
        except ErroExtracao as erro:
            faltando.append(f"{fonte.fonte_id}: {erro}")
        time.sleep(2)  # coleta serial e educada com o host

    fatos: list[Fato] = []
    extraidos, sem_nota = [], []
    for fonte in fontes:
        if fonte.fonte_id not in hashes:
            continue
        if fonte.cd_cvm not in ANCORAS_POR_EMISSOR:
            continue
        sonda, secao, fim, rubricas, unidade = ANCORAS_POR_EMISSOR[fonte.cd_cvm]
        try:
            pagina = localizar_pagina_da_nota(fonte.caminho, sonda)
            texto = texto_da_pagina(fonte, pagina)
            if secao:
                texto = _recortar_secao(texto, secao, fim)
            colunas_brutas = numeros_da_linha(
                localizar_rubrica(texto, rubricas[0].rotulo)[1]
            )
            papeis = LAYOUTS_POR_EMISSOR[fonte.cd_cvm].get(len(colunas_brutas))
            if papeis is None:
                sem_nota.append(
                    f"{fonte.fonte_id}: {len(colunas_brutas)} colunas sem "
                    "layout declarado para este emissor"
                )
                continue
            familias = (rubricas, *PERFIS_ALTERNATIVOS.get(fonte.cd_cvm, ()))
            novos, ultimo_erro = None, None
            for familia in familias:
                nota = NotaExtraida(
                    fonte_id=fonte.fonte_id, pagina_pdf=pagina,
                    pagina_impressa=str(pagina),
                    nota="nota de juros (página localizada automaticamente)",
                    colunas=periodos_dos_papeis(papeis, fonte.periodo_documento),
                    rubricas=familia, unidade=unidade,
                    secao=secao, secao_fim=fim,
                )
                try:
                    novos = extrair_nota(nota, fonte, fonte_alternativa=True)
                    break
                except ErroExtracao as erro:
                    ultimo_erro = erro
            if novos is None:
                raise ultimo_erro
            fatos.extend(novos)
            extraidos.append(fonte.fonte_id)
        except (ErroExtracao, ErroEscopo) as erro:
            sem_nota.append(f"{fonte.fonte_id}: {erro}")

    # O 4T sai por derivação ou não sai — nenhum emissor o publica isolado.
    # Deriva-se de um retrato dos fatos LIDOS, para que um derivado nunca sirva
    # de operando de outro derivado.
    lidos = list(fatos)
    derivacoes, recusas_de_derivacao = derivacoes_automaticas(lidos, fontes)
    linhagem: list[dict] = []
    for derivacao in derivacoes:
        novos, trilha = derivar_trimestre(lidos, derivacao)
        fatos.extend(novos)
        linhagem.extend(trilha)

    conferencias = conferir_identidade_trimestral(fatos)
    vintages = divergencias_de_vintage(fatos)
    resultados = []
    for fonte in fontes:
        do_fonte = [f for f in fatos if f.fonte_id == fonte.fonte_id]
        for periodo in sorted({f.periodo for f in do_fonte}):
            resultado = construir_j(do_fonte, periodo, fonte)
            if resultado is not None:
                resultados.append(resultado)

    with open(DIR_EXTENSAO / "fatos.jsonl", "w", encoding="utf-8") as saida:
        for fato in fatos:
            saida.write(json.dumps(fato.para_json(), ensure_ascii=False) + "\n")
    with open(DIR_EXTENSAO / "j_por_periodo.jsonl", "w", encoding="utf-8") as saida:
        for resultado in resultados:
            saida.write(
                json.dumps(resultado.para_json(), ensure_ascii=False) + "\n"
            )
    with open(DIR_EXTENSAO / "conferencias.jsonl", "w", encoding="utf-8") as saida:
        for conferencia in conferencias:
            saida.write(json.dumps(conferencia, ensure_ascii=False) + "\n")
    with open(DIR_EXTENSAO / "vintages.jsonl", "w", encoding="utf-8") as saida:
        for registro in vintages:
            saida.write(json.dumps(registro, ensure_ascii=False) + "\n")
    with open(DIR_EXTENSAO / "derivacoes.jsonl", "w", encoding="utf-8") as saida:
        for registro in [*linhagem, *recusas_de_derivacao]:
            saida.write(json.dumps(registro, ensure_ascii=False) + "\n")

    # Usável exige FECHAMENTO. Contar um trimestre como usável quando a soma
    # das parcelas não dá o total impresso seria publicar cobertura que a
    # aritmética não sustenta — a composição incompleta significa que alguma
    # parcela não foi capturada, e J estaria errado por essa parcela.
    trimestres = {
        f"{a}T{t}" for a in range(2016, 2027) for t in (1, 2, 3, 4)
    }
    utilizaveis = [
        r for r in resultados
        if r.status in ("identificado", "limitado")
        and r.fechamento_confere is True
        and r.periodo in trimestres
    ]
    resumo = {
        "schema_version": SCHEMA_VERSION,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "documentos_no_manifesto": len(fontes),
        "documentos_coletados": len(coletados),
        "documentos_faltando": faltando,
        "documentos_extraidos": len(extraidos),
        "documentos_sem_nota_legivel": sem_nota,
        "fatos": len(fatos),
        # DOIS números, porque não são a mesma coisa: o mesmo trimestre pode
        # aparecer em mais de um documento (safras distintas). Publicar só a
        # contagem de registros infla a cobertura — foi o que este resumo fazia.
        "registros_utilizaveis": len(utilizaveis),
        "pares_emissor_trimestre_distintos": len(
            {(r.cd_cvm, r.periodo) for r in utilizaveis}
        ),
        "trimestres_por_emissor": {
            cd: len({r.periodo for r in utilizaveis if r.cd_cvm == cd})
            for cd in sorted({r.cd_cvm for r in utilizaveis})
        },
        "janela": (
            f"{min((r.periodo for r in utilizaveis), default='-')} .. "
            f"{max((r.periodo for r in utilizaveis), default='-')}"
        ),
        # Contrato C5-B: o resumo contava `confere is True` sem olhar
        # `independente`, e G0 recebia essa contagem sem distinguir as duas
        # classes. Hoje elas coincidem; uma identidade futura que feche por
        # construção voltaria a ser contada como conferida. As duas passam a
        # ser publicadas, e quem certifica lê a SEGUNDA.
        "identidades_conferidas": sum(
            1 for c in conferencias if c["confere"] is True
        ),
        "identidades_conferidas_independentes": sum(
            1 for c in conferencias
            if c["confere"] is True and c.get("independente") is True
        ),
        "identidades_que_fecham_por_construcao": [
            {k: c[k] for k in ("cd_cvm", "ano", "identidade", "operandos_derivados")}
            for c in conferencias
            if c["confere"] is True and c.get("independente") is not True
        ],
        "identidades_divergentes": [
            c for c in conferencias if c["confere"] is False
        ],
        "identidades_nao_verificaveis": sum(
            1 for c in conferencias if c["confere"] is None
        ),
        "periodos_reapresentados": len(vintages),
        # Não conformidade contratual: parcela INCLUÍDA que veio credora.
        # Despesa de juros por competência não é crédito — a parcela embute
        # algo que o contrato exclui (valor justo/câmbio) ou é
        # reclassificação. Fica contado, nunca silencioso.
        "periodos_com_credito_em_parcela_incluida": [
            {
                "cd_cvm": r.cd_cvm, "periodo": r.periodo,
                "fonte_id": r.fonte_id,
                "conceitos": list(r.creditos_em_incluidas),
            }
            for r in resultados if r.creditos_em_incluidas
        ],
        "rubricas_com_conformidade_nao_demonstrada": sorted({
            conceito for r in resultados for conceito in r.creditos_em_incluidas
        }),
        "quartos_trimestres_derivados": len(derivacoes),
        "quartos_trimestres_recusados": recusas_de_derivacao,
        "limite": (
            "Extensão NÃO altera os 25 pacotes congelados do piloto e não "
            "autoriza treino: mede até onde a série de J existe, nada além."
        ),
    }
    (DIR_EXTENSAO / "resumo.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return resumo

if __name__ == "__main__":
    raise SystemExit(main())
