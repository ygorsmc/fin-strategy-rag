"""Painel de pesquisa do Rank 3-B: FCO trimestral e ativo total, com linhagem.

Contrato: `resultados/contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md`,
parte 1 (U, T, F, A, P, R). **Não calcula rótulo, taxa de evento, T1, T2 nem
baseline** (O1 do lote B).

## Por que um painel separado

Decisão do responsável em 16/09: o painel compartilhado (`cvm_treino.duckdb`)
alimenta a etapa 10 e carrega a derivação com os defeitos N2/N3; reconstruí-lo
quebraria hash e alcançaria o único modelo treinado. Este painel lê a fonte
primária (os ZIPs pinados), só as contas que o candidato consome, e publica o
que recusou.

## As três decisões que resolvem o que o painel compartilhado não resolve

1. **Período por DATAS, rótulo derivado** (T1/T2). O N3 era dois períodos sob o
   mesmo rótulo fiscal com desempate arbitrário; aqui a chave é a data, e
   colisão de rótulo não se desempata — os dois saem (T3).
2. **Método fora da identidade** (F2). O caixa operacional é o mesmo pelos dois
   métodos; parear por demonstrativo fabricava antecedente ausente nas 53
   companhias que trocam de método.
3. **Disponibilidade conservadora** (P1). O número em mãos é o da maior versão;
   ele só é usado a partir da recepção dela — em derivação, da mais tardia
   entre os operandos. Não vaza; custa perda, e a perda é medida (P2).
   **Correção de 17/09 (contrato P4):** a escala corrigida também é
   informação — o documento só fica disponível quando as PROVAS da escala
   aplicada existem. Uma correção herdada depende das duas pontas do trecho, e
   a ponta final pode ser publicada anos depois do documento interior.

**Correção por conta (27/09, contrato A de
`resultados/contratos_caminho_medicao_rank03b_2026-09-27.md`).** Uma prova do
ativo não prova o FCO do mesmo documento (§12-bis do rascunho v2). A escala
aplicada, a base e a data da prova passam a existir por conta: as linhas de
ativo usam as do ativo, os acumulados de FCO as do FCO. Sem correção por
conta, as duas herdam as do documento, e o painel sai idêntico ao de antes.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PAINEL_COMPARTILHADO = RAIZ / "artefatos" / "cvm_treino.duckdb"

#: F4/F5 — banda de duração de um trimestre, a mesma do pré-registro (G0.2).
BANDA_DIAS = (80, 100)
#: A2 — módulo máximo, na unidade declarada, de um Ativo Total não informativo.
PISO_NAO_INFORMATIVO = 1.0
FATOR_DA_ESCALA = {"UNIDADE": 1.0, "MIL": 1_000.0, "MILHAO": 1_000_000.0}
CONTA_FCO = "6.01"
CONTA_ATIVO = "1"

ESTADOS_FCO = (
    "valido", "primeiro_periodo_nao_trimestral", "lacuna", "curto",
    "conflito_de_declaracoes", "valor_nulo", "operando_indisponivel",
    "ambiguo_exercicio",
)
ESTADOS_ATIVO = (
    "valido", "nao_informativo", "conflito_de_declaracoes", "valor_nulo",
    "ambiguo_exercicio",
)
BASES_DE_ESCALA = ("declarada", "corrigida_documento", "herdada_trecho", "corrigida_conta")
#: Contas do manifesto por conta (contrato A1) → a conta do painel que corrigem.
CONTAS_DA_CORRECAO = {CONTA_ATIVO: "ativo", CONTA_FCO: "fco"}


class DefeitoDeFonte(Exception):
    """A fonte contradiz uma premissa medida (ex.: escala não uniforme no documento)."""


class CorrecaoObsoleta(Exception):
    """A correção de escala não confere mais com a fonte — a CVM republicou."""


def rotulo_civil(d: date) -> str:
    """T2: trimestre civil da data de fim."""
    return f"{(d.month - 1) // 3 + 1}T{d.year}"


def _fator(escala: str) -> float:
    try:
        return FATOR_DA_ESCALA[escala]
    except KeyError:
        raise DefeitoDeFonte(f"ESCALA_MOEDA desconhecida: {escala!r}") from None


def _chave_doc(cd_cvm, conjunto, dt_refer, versao) -> tuple:
    return (cd_cvm, conjunto, str(dt_refer), int(versao))


# --- documentos -------------------------------------------------------------------

@dataclass
class EscalaDaConta:
    """Escala aplicada a UMA conta do documento, com a base e a data da prova."""
    aplicada: str
    base: str
    id_correcao: str | None = None
    dt_prova: date | None = None


@dataclass
class Documento:
    cd_cvm: str
    conjunto: str
    dt_refer: str
    versao: int
    id_doc: str
    dt_receb: date
    dt_receb_v1: date
    escala_declarada: str
    escala_aplicada: str
    base_escala: str
    id_correcao: str | None = None
    #: P4: recepção mais tardia entre os pacotes que provam a escala aplicada.
    dt_prova: date | None = None
    #: Contrato A3 (27/09): correção de UMA conta (`"ativo"` ou `"fco"`), que
    #: sobrepõe a escala do documento só nela.
    por_conta: dict = field(default_factory=dict)

    @property
    def disponivel_em(self) -> date:
        return max(self.dt_receb, self.dt_prova or self.dt_receb)

    @property
    def disponivel_em_v1(self) -> date:
        return max(self.dt_receb_v1, self.dt_prova or self.dt_receb_v1)

    def escala_de(self, conta: str) -> EscalaDaConta:
        """A escala da conta: a corrigida por conta, se houver; senão a do documento."""
        if conta not in ("ativo", "fco"):
            raise ValueError(f"conta do painel desconhecida: {conta!r}")
        return self.por_conta.get(conta) or EscalaDaConta(
            self.escala_aplicada, self.base_escala, self.id_correcao, self.dt_prova)

    def disponivel_em_de(self, conta: str) -> date:
        """P4 por conta: a recepção ou a prova da escala DESTA conta, a mais tardia.

        Sem correção por conta, é exatamente `disponivel_em` — e passa por ele,
        para que as contraprovas que sabotam essa propriedade (G1.4, CRF-02)
        continuem alcançando o construtor.
        """
        self.escala_de(conta)  # valida o nome da conta
        if conta not in self.por_conta:
            return self.disponivel_em
        prova = self.por_conta[conta].dt_prova
        return max(self.dt_receb, prova or self.dt_receb)

    def disponivel_em_v1_de(self, conta: str) -> date:
        self.escala_de(conta)
        if conta not in self.por_conta:
            return self.disponivel_em_v1
        prova = self.por_conta[conta].dt_prova
        return max(self.dt_receb_v1, prova or self.dt_receb_v1)


def impressao_digital(linhas: list[tuple]) -> str:
    """Hash dos valores brutos das contas monetárias de um documento.

    Guarda da correção (parte 2 do contrato, padrão do §3.3): se a CVM
    republicar o arquivo, a impressão muda e a correção deixa de valer.
    """
    corpo = "\n".join(
        f"{c}|{o}|{i or ''}|{f}|{'' if v is None else repr(float(v))}"
        for c, o, i, f, v in sorted(linhas, key=lambda t: tuple(str(x) for x in t))
    )
    return hashlib.sha256(corpo.encode()).hexdigest()


def recepcao_por_id_doc(con) -> dict[str, date]:
    """`{id_doc: dt_receb}` do cadastro inteiro; repetido vale o mais tardio."""
    saida: dict[str, date] = {}
    for i, r in con.execute("SELECT id_doc, dt_receb FROM cadastro").fetchall():
        saida[str(i)] = max(r, saida.get(str(i), r))
    return saida


def pacotes_da_prova(correcao: dict) -> list[str]:
    """P4: os documentos cuja publicação a escala aplicada exige.

    Na correção por conta da ROTA-1 a prova está no próprio pacote do documento.
    """
    if correcao["base"] in ("corrigida_documento", "corrigida_conta"):
        return [str(correcao["id_doc"])]
    if correcao["base"] == "herdada_trecho":
        return [str(p["id_doc"]) for p in json.loads(correcao["pontas"])]
    raise DefeitoDeFonte(f"{correcao.get('id_correcao')}: base desconhecida {correcao['base']!r}")


def data_da_prova(correcao: dict, recepcao: dict[str, date]) -> date:
    """P4/P5: a recepção mais tardia entre as provas; prova sem cadastro derruba."""
    datas = []
    for i in pacotes_da_prova(correcao):
        if i not in recepcao:
            raise DefeitoDeFonte(
                f"{correcao.get('id_correcao')}: prova {i} ausente do cadastro — "
                "sem data, a disponibilidade da correção não é demonstrável")
        datas.append(recepcao[i])
    return max(datas)


def carregar_documentos(con, correcoes: dict | None = None,
                        correcoes_por_conta: dict | None = None) -> dict[tuple, Documento]:
    """Um `Documento` por versão NUMÉRICA (a que os ZIPs trazem), com a escala aplicada.

    `correcoes_por_conta`: `{chave do documento: {conta: linha}}`, com `conta`
    em `CONTAS_DA_CORRECAO` (contrato A). Documento corrigido por conta não
    pode ter correção por documento.
    """
    correcoes = correcoes or {}
    correcoes_por_conta = correcoes_por_conta or {}
    recepcao = recepcao_por_id_doc(con) if (correcoes or correcoes_por_conta) else {}
    linhas = con.execute(
        """
        SELECT d.cd_cvm, d.conjunto, CAST(d.dt_refer AS VARCHAR), d.versao,
               list(DISTINCT d.escala ORDER BY d.escala)
        FROM declaracoes d JOIN universo USING (cd_cvm)
        GROUP BY ALL
        """
    ).fetchall()
    cadastro = defaultdict(list)
    for cd, cj, dt, v, id_doc, receb in con.execute(
        """
        SELECT c.cd_cvm, c.conjunto, CAST(c.dt_refer AS VARCHAR), c.versao, c.id_doc, c.dt_receb
        FROM cadastro c JOIN universo USING (cd_cvm)
        """
    ).fetchall():
        cadastro[(cd, cj, dt)].append((v, id_doc, receb))
    brutos = defaultdict(list)
    for cd, cj, dt, v, conta, ordem, ini, fim, vl in con.execute(
        """
        SELECT d.cd_cvm, d.conjunto, CAST(d.dt_refer AS VARCHAR), d.versao, d.cd_conta,
               d.ordem, d.dt_ini, d.dt_fim, d.vl
        FROM declaracoes d JOIN universo USING (cd_cvm)
        WHERE d.cd_conta IN ('1', '6.01')
        """
    ).fetchall():
        brutos[(cd, cj, dt, v)].append((conta, ordem, ini, fim, vl))

    documentos: dict[tuple, Documento] = {}
    usadas = set()
    usadas_por_conta = set()
    for cd, cj, dt, v, escalas in linhas:
        if len(escalas) != 1:
            raise DefeitoDeFonte(
                f"{cd} {cj} {dt} v{v}: escalas {escalas} no mesmo documento — "
                "a premissa medida em 16/09 (0 de 22.486) não vale mais"
            )
        versoes = cadastro.get((cd, cj, dt), [])
        desta = [(i, r) for vv, i, r in versoes if vv == v]
        if not desta:
            raise DefeitoDeFonte(f"{cd} {cj} {dt} v{v}: versão numérica ausente do cadastro")
        chave = _chave_doc(cd, cj, dt, v)
        escala = escalas[0]
        aplicada, base, id_correcao, dt_prova = escala, "declarada", None, None
        if chave in correcoes:
            c = correcoes[chave]
            if c["escala_declarada"] != escala or c["impressao_digital"] != impressao_digital(brutos[chave]):
                raise CorrecaoObsoleta(
                    f"{chave}: a correção {c['id_correcao']} foi escrita para outra "
                    "versão da fonte — não se aplica às cegas"
                )
            aplicada, base, id_correcao = c["escala_aplicada"], c["base"], c["id_correcao"]
            dt_prova = data_da_prova(c, recepcao)
            usadas.add(chave)
        _fator(aplicada)
        por_conta = {}
        if chave in correcoes_por_conta:
            if chave in correcoes:
                raise CorrecaoObsoleta(
                    f"{chave}: correção por documento e por conta no mesmo documento")
            for conta, c in sorted(correcoes_por_conta[chave].items()):
                nome = CONTAS_DA_CORRECAO.get(conta)
                if nome is None or c.get("base") != "corrigida_conta":
                    raise DefeitoDeFonte(f"{chave}: correção por conta inválida ({conta!r})")
                if c["escala_declarada"] != escala or \
                        c["impressao_digital"] != impressao_digital(brutos[chave]):
                    raise CorrecaoObsoleta(
                        f"{chave}: a correção {c['id_correcao']} foi escrita para outra "
                        "versão da fonte — não se aplica às cegas"
                    )
                _fator(c["escala_aplicada"])
                por_conta[nome] = EscalaDaConta(
                    c["escala_aplicada"], "corrigida_conta", c["id_correcao"],
                    data_da_prova(c, recepcao))
            usadas_por_conta.add(chave)
        documentos[chave] = Documento(
            cd_cvm=cd, conjunto=cj, dt_refer=dt, versao=int(v),
            # Cadastro com a mesma versão repetida (1 caso medido): vale a
            # recepção mais TARDIA — conservador para disponibilidade.
            id_doc=",".join(sorted(i for i, _ in desta)),
            dt_receb=max(r for _, r in desta),
            dt_receb_v1=min(r for _, _, r in versoes),
            escala_declarada=escala, escala_aplicada=aplicada,
            base_escala=base, id_correcao=id_correcao, dt_prova=dt_prova,
            por_conta=por_conta,
        )
    sobrando = set(correcoes) - usadas
    if sobrando:
        raise CorrecaoObsoleta(f"correções sem documento correspondente: {sorted(sobrando)[:3]}")
    sobrando = set(correcoes_por_conta) - usadas_por_conta
    if sobrando:
        raise CorrecaoObsoleta(
            f"correções por conta sem documento correspondente: {sorted(sobrando)[:3]}")
    return documentos


# --- ativo --------------------------------------------------------------------------

def construir_ativo(con, documentos: dict[tuple, Documento]) -> list[dict]:
    linhas = con.execute(
        """
        SELECT d.cd_cvm, d.conjunto, CAST(d.dt_refer AS VARCHAR), d.versao, d.dt_fim, d.vl
        FROM declaracoes d JOIN universo USING (cd_cvm)
        WHERE d.demonstrativo = 'BPA' AND d.cd_conta = ? AND d.ordem = 'ÚLTIMO'
        """,
        [CONTA_ATIVO],
    ).fetchall()
    por_data: dict[tuple, list[dict]] = defaultdict(list)
    for cd, cj, dt, v, fim, vl in linhas:
        doc = documentos[_chave_doc(cd, cj, dt, v)]
        por_data[(cd, fim)].append({
            "cd_cvm": cd, "dt_fim": fim, "valor_bruto": vl,
            "valor_reais": None if vl is None else vl * _fator(doc.escala_de("ativo").aplicada),
            "doc": doc,
        })
    saida = []
    for (cd, fim), decls in sorted(por_data.items()):
        decls.sort(key=lambda r: (r["doc"].disponivel_em_de("ativo"), r["doc"].conjunto,
                                  r["doc"].id_doc))
        primeira = decls[0]
        valores = {r["valor_reais"] for r in decls}
        if any(r["valor_bruto"] is None for r in decls):
            estado = "valor_nulo"
        elif len(valores) > 1:
            estado = "conflito_de_declaracoes"
        elif 0 < primeira["valor_bruto"] <= PISO_NAO_INFORMATIVO:
            # A2: só positivo. "Zero e negativo seguem como estão" — a
            # elegibilidade do alvo (ativo > 0) já os trata. (Auditoria de 16/09,
            # B3: a versão anterior usava `abs` e contrariava o contrato.)
            estado = "nao_informativo"
        else:
            estado = "valido"
        doc = primeira["doc"]
        escala = doc.escala_de("ativo")
        saida.append({
            "cd_cvm": cd, "dt_fim": fim, "trimestre": rotulo_civil(fim),
            "valor_bruto": primeira["valor_bruto"], "valor_reais": primeira["valor_reais"],
            "escala_declarada": doc.escala_declarada, "escala_aplicada": escala.aplicada,
            "base_escala": escala.base, "id_correcao": escala.id_correcao,
            "conjunto": doc.conjunto, "dt_refer": doc.dt_refer, "versao": doc.versao,
            "id_doc": doc.id_doc, "disponivel_em": doc.disponivel_em_de("ativo"),
            "disponivel_em_v1": doc.disponivel_em_v1_de("ativo"),
            "dt_prova_escala": escala.dt_prova,
            "declaracoes": len(decls),
            "estado": estado,
        })
    _marcar_colisoes(saida)
    return saida


def _marcar_colisoes(linhas: list[dict]) -> None:
    """T3: rótulo repetido entre linhas válidas da mesma companhia — nenhuma fica."""
    grupos = defaultdict(list)
    for linha in linhas:
        if linha["estado"] == "valido":
            grupos[(linha["cd_cvm"], linha["trimestre"])].append(linha)
    for grupo in grupos.values():
        if len(grupo) > 1:
            for linha in grupo:
                linha["estado"] = "ambiguo_exercicio"


# --- FCO ----------------------------------------------------------------------------

def construir_fco(con, documentos: dict[tuple, Documento]) -> tuple[list[dict], list[dict]]:
    """Acumulados (F1/F3) e trimestres candidatos (F4/F5)."""
    linhas = con.execute(
        """
        SELECT d.cd_cvm, d.conjunto, CAST(d.dt_refer AS VARCHAR), d.versao,
               d.demonstrativo, d.dt_ini, d.dt_fim, d.vl
        FROM declaracoes d JOIN universo USING (cd_cvm)
        WHERE d.demonstrativo IN ('DFC_MD', 'DFC_MI') AND d.cd_conta = ?
          AND d.ordem = 'ÚLTIMO'
        """,
        [CONTA_FCO],
    ).fetchall()
    por_periodo: dict[tuple, list[dict]] = defaultdict(list)
    for cd, cj, dt, v, dem, ini, fim, vl in linhas:
        doc = documentos[_chave_doc(cd, cj, dt, v)]
        por_periodo[(cd, ini, fim)].append({
            "valor_bruto": vl, "metodo": dem, "doc": doc,
            "valor_reais": None if vl is None else vl * _fator(doc.escala_de("fco").aplicada),
        })
    acumulados = []
    for (cd, ini, fim), decls in sorted(por_periodo.items()):
        decls.sort(key=lambda r: (r["doc"].disponivel_em_de("fco"), r["doc"].conjunto,
                                  r["doc"].id_doc))
        primeira = decls[0]
        if any(r["valor_bruto"] is None for r in decls):
            estado = "valor_nulo"
        elif len({r["valor_reais"] for r in decls}) > 1:
            estado = "conflito_de_declaracoes"
        else:
            estado = "ok"
        doc = primeira["doc"]
        escala = doc.escala_de("fco")
        acumulados.append({
            "cd_cvm": cd, "dt_ini": ini, "dt_fim": fim,
            "valor_reais": primeira["valor_reais"], "metodo": primeira["metodo"],
            "escala_declarada": doc.escala_declarada, "escala_aplicada": escala.aplicada,
            "base_escala": escala.base, "conjunto": doc.conjunto,
            "dt_refer": doc.dt_refer, "versao": doc.versao, "id_doc": doc.id_doc,
            "disponivel_em": doc.disponivel_em_de("fco"),
            "disponivel_em_v1": doc.disponivel_em_v1_de("fco"),
            "dt_prova_escala": escala.dt_prova,
            "declaracoes": len(decls), "estado": estado,
        })

    por_exercicio = defaultdict(list)
    for a in acumulados:
        por_exercicio[(a["cd_cvm"], a["dt_ini"])].append(a)
    minimo, maximo = BANDA_DIAS
    trimestres = []
    for (cd, ini_ex), serie in sorted(por_exercicio.items()):
        serie.sort(key=lambda a: a["dt_fim"])
        anterior = None
        for k, atual in enumerate(serie):
            operandos = [atual] if anterior is None else [anterior, atual]
            inicio = ini_ex if anterior is None else anterior["dt_fim"] + timedelta(days=1)
            dias = (atual["dt_fim"] - inicio).days + 1
            valor = None
            # F5, na ordem do contrato: o estado do próprio acumulado primeiro,
            # depois o do antecedente, depois a duração.
            if atual["estado"] != "ok":
                estado = atual["estado"]
            elif anterior is not None and anterior["estado"] != "ok":
                estado = "operando_indisponivel"
            else:
                valor = atual["valor_reais"] - (anterior["valor_reais"] if anterior else 0.0)
                if anterior is None and not minimo <= dias <= maximo:
                    estado = "primeiro_periodo_nao_trimestral"
                elif dias < minimo:
                    estado = "curto"
                elif dias > maximo:
                    estado = "lacuna"
                else:
                    estado = "valido"
            trimestres.append({
                "cd_cvm": cd, "dt_ini": inicio, "dt_fim": atual["dt_fim"],
                "dt_ini_exercicio": ini_ex, "posicao_no_exercicio": k + 1,
                "dias": dias, "trimestre": rotulo_civil(atual["dt_fim"]),
                "valor_reais": valor,
                "origem": "arquivado" if anterior is None else "derivado",
                "metodos": "+".join(o["metodo"] for o in operandos),
                "escalas_aplicadas": "+".join(o["escala_aplicada"] for o in operandos),
                "escalas_declaradas": "+".join(o["escala_declarada"] for o in operandos),
                "operandos": json.dumps([
                    {"dt_ini": str(o["dt_ini"]), "dt_fim": str(o["dt_fim"]),
                     "conjunto": o["conjunto"], "dt_refer": o["dt_refer"],
                     "versao": o["versao"], "id_doc": o["id_doc"]}
                    for o in operandos
                ], sort_keys=True),
                "versao": atual["versao"], "demonstrativo": atual["metodo"],
                "disponivel_em": max(o["disponivel_em"] for o in operandos),
                "disponivel_em_v1": max(o["disponivel_em_v1"] for o in operandos),
                "estado": estado,
            })
            anterior = atual
    _marcar_colisoes(trimestres)
    return acumulados, trimestres


# --- inventário, digest e gravação ---------------------------------------------------

def inventario(ativo: list[dict], trimestres: list[dict], acumulados: list[dict],
               con) -> dict:
    def por_estado(linhas):
        contagem = defaultdict(lambda: {"linhas": 0, "companhias": set()})
        for linha in linhas:
            contagem[linha["estado"]]["linhas"] += 1
            contagem[linha["estado"]]["companhias"].add(linha["cd_cvm"])
        return {k: {"linhas": v["linhas"], "companhias": len(v["companhias"])}
                for k, v in sorted(contagem.items())}

    validos = [t for t in trimestres if t["estado"] == "valido"]
    cegos = [t for t in validos if t["disponivel_em_v1"] < t["disponivel_em"]]
    decisoes = defaultdict(list)
    for cd, receb in con.execute(
        "SELECT DISTINCT c.cd_cvm, c.dt_receb FROM cadastro c JOIN universo USING (cd_cvm)"
    ).fetchall():
        decisoes[cd].append(receb)
    # RF-07 (17/09): a soma conta PARES (trimestre, D) — uma decisão cai em
    # mais de um intervalo. As chaves (companhia, D) distintas saem ao lado.
    pares_no_cego = [
        (t["cd_cvm"], d) for t in cegos for d in decisoes[t["cd_cvm"]]
        if t["disponivel_em_v1"] <= d < t["disponivel_em"]
    ]
    # F6: lacunas que um `PENÚLTIMO` fecharia — contadas, não usadas.
    penultimos = {
        (cd, ini, fim) for cd, ini, fim in con.execute(
            """
            SELECT DISTINCT d.cd_cvm, d.dt_ini, d.dt_fim FROM declaracoes d
            JOIN universo USING (cd_cvm)
            WHERE d.demonstrativo IN ('DFC_MD', 'DFC_MI') AND d.cd_conta = ?
              AND d.ordem = 'PENÚLTIMO'
            """, [CONTA_FCO],
        ).fetchall()
    }
    ultimos = {(a["cd_cvm"], a["dt_ini"], a["dt_fim"]) for a in acumulados}
    so_penultimo = penultimos - ultimos
    fechariam = sum(
        1 for t in trimestres if t["estado"] in ("lacuna", "primeiro_periodo_nao_trimestral")
        and any(cd == t["cd_cvm"] and ini == t["dt_ini_exercicio"] and t["dt_ini"] <= fim < t["dt_fim"]
                for cd, ini, fim in so_penultimo if cd == t["cd_cvm"])
    )
    return {
        "fco_trimestral_por_estado": por_estado(trimestres),
        "ativo_por_estado": por_estado(ativo),
        "fco_acumulado_por_estado": por_estado(acumulados),
        "escala_por_base": {
            base: sum(1 for a in ativo if a["base_escala"] == base) for base in BASES_DE_ESCALA
        },
        "p2_trimestres_validos_com_intervalo_cego": len(cegos),
        "p2_pares_trimestre_decisao_no_intervalo_cego": len(pares_no_cego),
        "p2_chaves_companhia_D_distintas_no_intervalo_cego": len(set(pares_no_cego)),
        "f6_periodos_so_como_penultimo": len(so_penultimo),
        "f6_perdas_que_um_penultimo_fecharia": fechariam,
    }


TABELAS = ("ativo", "fco_acumulado", "fco_trimestral")


def _para_df(linhas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(linhas)
    return df.drop(columns=[c for c in ("doc",) if c in df.columns])


def digest(tabelas: dict[str, list[dict]]) -> dict[str, str]:
    """R2: SHA-256 de cada tabela exportada em ordem total, e do conjunto."""
    saida = {}
    for nome in TABELAS:
        df = _para_df(tabelas[nome])
        df = df.reindex(sorted(df.columns), axis=1)
        df = df.sort_values(list(df.columns), kind="mergesort", na_position="first")
        buf = io.StringIO()
        df.to_csv(buf, index=False, lineterminator="\n", float_format="%.6f")
        saida[nome] = hashlib.sha256(buf.getvalue().encode()).hexdigest()
    saida["conjunto"] = hashlib.sha256(
        "|".join(saida[n] for n in TABELAS).encode()
    ).hexdigest()
    return saida


@dataclass
class Painel:
    ativo: list[dict]
    fco_acumulado: list[dict]
    fco_trimestral: list[dict]
    inventario: dict
    digest: dict[str, str]
    documentos: dict = field(default_factory=dict)


def identidades_contabeis(con) -> dict[str, int]:
    """A3: identidades publicadas para leitura — nenhuma linha é removida por elas."""
    def um(sql):
        return int(con.execute(sql).fetchone()[0])
    base = """FROM declaracoes d JOIN universo USING (cd_cvm) WHERE d.ordem = 'ÚLTIMO'"""
    return {
        "documentos_com_ativo_diferente_do_passivo": um(f"""
            SELECT count(*) FROM (SELECT d.cd_cvm, d.conjunto, d.dt_refer, d.versao,
              max(CASE WHEN d.cd_conta = '1' AND d.demonstrativo = 'BPA' THEN d.vl END) a,
              max(CASE WHEN d.cd_conta = '2' AND d.demonstrativo = 'BPP' THEN d.vl END) p
            {base} GROUP BY ALL) WHERE abs(a - p) > 1"""),
        "periodos_dfc_em_que_a_soma_nao_fecha": um(f"""
            SELECT count(*) FROM (SELECT d.cd_cvm, d.conjunto, d.dt_refer, d.versao, d.demonstrativo,
              d.dt_ini, d.dt_fim,
              -- Máximo POR CONTA antes de somar: a fonte tem linhas duplicadas
              -- (60 por conta, medido), e somá-las dobraria o fluxo.
              coalesce(max(CASE WHEN d.cd_conta = '6.01' THEN d.vl END), 0)
              + coalesce(max(CASE WHEN d.cd_conta = '6.02' THEN d.vl END), 0)
              + coalesce(max(CASE WHEN d.cd_conta = '6.03' THEN d.vl END), 0)
              + coalesce(max(CASE WHEN d.cd_conta = '6.04' THEN d.vl END), 0) s,
              max(CASE WHEN d.cd_conta = '6.05' THEN d.vl END) c5
            {base} AND d.demonstrativo LIKE 'DFC%' GROUP BY ALL) WHERE abs(s - c5) > 1"""),
        "periodos_dfc_em_que_o_saldo_nao_fecha": um(f"""
            SELECT count(*) FROM (SELECT d.cd_cvm, d.conjunto, d.dt_refer, d.versao, d.demonstrativo,
              d.dt_ini, d.dt_fim,
              max(CASE WHEN d.cd_conta = '6.05' THEN d.vl END) c5,
              max(CASE WHEN d.cd_conta = '6.05.01' THEN d.vl END) ini,
              max(CASE WHEN d.cd_conta = '6.05.02' THEN d.vl END) fim
            {base} AND d.demonstrativo LIKE 'DFC%' GROUP BY ALL)
            WHERE ini IS NOT NULL AND fim IS NOT NULL AND abs(fim - ini - c5) > 1"""),
    }


def construir(con, correcoes: dict | None = None,
              correcoes_por_conta: dict | None = None) -> Painel:
    """Espera `declaracoes`, `cadastro` (de `fonte_zip_cvm.extrair`) e `universo`."""
    documentos = carregar_documentos(con, correcoes, correcoes_por_conta)
    ativo = construir_ativo(con, documentos)
    acumulados, trimestres = construir_fco(con, documentos)
    # U2: o painel não decide elegibilidade, mas carrega o plano de contas.
    planos = dict(con.execute("SELECT cd_cvm, plano_contas FROM universo").fetchall())
    for linha in (*ativo, *trimestres):
        linha["plano_contas"] = planos.get(linha["cd_cvm"])
    tabelas = {"ativo": ativo, "fco_acumulado": acumulados, "fco_trimestral": trimestres}
    return Painel(
        ativo=ativo, fco_acumulado=acumulados, fco_trimestral=trimestres,
        inventario={**inventario(ativo, trimestres, acumulados, con),
                    "a3_identidades_contabeis": identidades_contabeis(con)},
        digest=digest(tabelas), documentos=documentos,
    )


def preparar_universo(con, painel: Path = PAINEL_COMPARTILHADO) -> str:
    """U1: universo lido do painel compartilhado, somente leitura. Devolve o hash dele."""
    con.execute(f"ATTACH '{painel}' AS compartilhado (READ_ONLY)")
    con.execute(
        """
        CREATE OR REPLACE TABLE universo AS
        SELECT cd_cvm, plano_contas FROM compartilhado.companhias
        WHERE plano_contas NOT LIKE 'll3_09_%' AND NOT is_banco
        """
    )
    con.execute("DETACH compartilhado")
    h = hashlib.sha256()
    with open(painel, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def caminho_do_manifesto(destino: Path) -> Path:
    """`painel.duckdb` → `manifesto_painel.json`; `painel_X.duckdb` →
    `manifesto_painel_X.json`. Um manifesto por painel: com nome fixo, a
    execução sem correções sobrescrevia o manifesto do painel governante
    (achado de 16/09)."""
    return destino.with_name(f"manifesto_{destino.stem}.json")


def gravar(painel: Painel, destino: Path, manifesto: dict) -> None:
    """Grava as tabelas num DuckDB e o manifesto (R4) ao lado, com nome próprio."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.unlink(missing_ok=True)
    with duckdb.connect(str(destino)) as saida:
        for nome in TABELAS:
            df = _para_df(getattr(painel, nome))
            saida.register("_df", df)
            saida.execute(f"CREATE TABLE {nome} AS SELECT * FROM _df")
            saida.unregister("_df")
    caminho_do_manifesto(destino).write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
