"""G0 e G1 do Rank 3-B sobre o painel de pesquisa — sem T1, T2 nem baseline.

Contrato: `resultados/contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md`,
cláusulas G1-pp a G7-pp. Cegueira ao desfecho: cláusula O1 do lote B.

**Nenhuma lógica de gate é copiada.** Este executor só traduz as linhas VÁLIDAS
do painel de pesquisa para as formas que os carregadores do auditor produzem e
chama `gate_g0`, `construir_amostra` e `gate_g1` do próprio auditor. Se o
auditor mudar, este executor mede com a regra nova.

**O rótulo não é calculado** (G6-pp; correção A1 de 16/09 — antes, `y` era
calculado em memória e apagado depois): a amostra do G1 é montada com
`construir_amostra(..., calcular_rotulo=False)`, e a contagem de descartes por
`FCO_TTM ≤ 0` sai omitida. O que sai daqui é estrutura: contagens de G0, de G1
e de perdas.

**Correções de 17/09 (contratos RF-01 a RF-08):** correções só entram
validadas (`CorrecoesValidadas`, V1); o G1 reconfere, **pelo manifesto e pelo
cadastro**, que a prova de cada escala corrigida já existia em D (P6); e o
diagnóstico G0.5 olha a escala APLICADA, não só a declarada (G5.1).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import duckdb

from scripts import auditar_rank03b_consumo_operacional as auditor
from scripts import fonte_zip_cvm as fz
from scripts import painel_pesquisa_rank03b as pp
from scripts.piloto_fonte_rad_rank03b import _sem_chave_proibida

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "artefatos" / "painel_pesquisa_rank03b"
CORRECOES = RAIZ / "corpus" / "cvm" / "painel_pesquisa_rank03b" / "correcoes_escala.csv"
CODIGO = ("scripts/painel_pesquisa_rank03b.py", "scripts/gates_painel_pesquisa_rank03b.py",
          "scripts/fonte_zip_cvm.py", "scripts/auditar_rank03b_consumo_operacional.py")


ADJUDICACAO = DESTINO / "adjudicacao"


class ManifestoDeCorrecoesAusente(FileNotFoundError):
    """O painel final não se constrói sem o manifesto de correções declarado."""


class CorrecoesValidadas(dict):
    """Correções que passaram pelas validações do produtor (V1, 17/09).

    O executor recusa um `dict` comum: montar correções à mão, sem as
    condições 11, 12 e 14 e sem os pacotes conferidos, era possível pelo caminho
    programático — só a CLI validava.
    """

    def __init__(self, correcoes: dict, origem_sha256: str):
        super().__init__(correcoes)
        self.origem_sha256 = origem_sha256
        self.conteudo_sha256 = self.impressao()

    def impressao(self) -> str:
        """Hash do CONTEÚDO: mudar uma linha depois de validar também é recusado."""
        corpo = json.dumps(sorted((list(k), v) for k, v in self.items()), sort_keys=True,
                           default=str)
        return hashlib.sha256(corpo.encode()).hexdigest()


class CorrecoesNaoValidadas(TypeError):
    """Correções que não vieram de `carregar_correcoes`."""


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def carregar_correcoes(caminho: Path, tabela: dict | None = None,
                       exigir_escala_nas_pontas: bool = True,
                       aquisicao: Path | None = None,
                       exigir_evidencia_numerica: bool = True,
                       exigir_escopo_v4: bool = True) -> CorrecoesValidadas:
    """Manifesto da parte 2 do contrato, **validado antes de aplicar**.

    Ausente é ERRO, não "nenhuma correção". **Correção da auditoria de 16/09
    (M1):** o consumidor aplicava qualquer linha com a impressão digital certa —
    uma escala `MILHAO` sem evidência nenhuma passava. Agora as condições 11, 12
    e 14 e a existência dos pacotes citados são conferidas aqui também, e não
    só no produtor (§4.4 regra 7).
    """
    from scripts import adjudicar_escala_rank03b as adj

    if not caminho.is_file():
        raise ManifestoDeCorrecoesAusente(
            f"{caminho} não existe. Sem ele o painel aplicaria só os rótulos "
            "declarados em silêncio; para isso existe `--sem-correcoes`, explícito."
        )
    with open(caminho, encoding="utf-8", newline="") as fh:
        linhas = list(csv.DictReader(fh))
    correcoes = {}
    for r in linhas:
        chave = (r["cd_cvm"], r["conjunto"], r["dt_refer"], int(r["versao"]))
        if chave in correcoes:
            raise ValueError(f"correção duplicada para {chave}")
        correcoes[chave] = r
    adj.validar_manifesto(linhas, tabela, exigir_escala_nas_pontas,
                          exigir_evidencia_numerica, exigir_escopo_v4)
    adj.conferir_pacotes(linhas, adj.pacotes_integros(aquisicao or adj.rad.MANIFESTO))
    return CorrecoesValidadas(correcoes, _sha256(caminho))


def datas_das_provas(con, correcoes: dict) -> dict[tuple, object]:
    """P6: `{documento: recepção mais tardia das provas}`, recalculado do manifesto
    e do cadastro — **não** da data que o construtor gravou no painel."""
    recepcao: dict[str, object] = {}
    for i, r in con.execute("SELECT id_doc, dt_receb FROM cadastro").fetchall():
        if type(r) is not date:
            raise ProvasAusentes(f"recepção inválida no cadastro da prova {i}")
        recepcao[str(i)] = max(r, recepcao.get(str(i), r))
    saida = {}
    for chave, c in correcoes.items():
        ids = ([c["id_doc"]] if c["base"] == "corrigida_documento"
               else [p["id_doc"] for p in json.loads(c["pontas"])])
        faltando = [i for i in ids if str(i) not in recepcao]
        if faltando:
            raise PainelViolaContrato({"c9_prova_sem_cadastro": faltando})
        saida[chave] = max(recepcao[str(i)] for i in ids)
    return saida


def g1_provas_depois_de_d(amostra: list[dict], painel: pp.Painel,
                          provas: dict[tuple, object]) -> int:
    """P6: observações que usam, em D, um documento cuja prova de escala é posterior.

    A linhagem da observação diz QUAIS trimestres e qual ativo entraram; o painel
    diz de quais documentos eles vêm; a data da prova vem de `provas`.
    """
    _exigir_provas(painel, provas)
    provas = provas or {}
    trimestres = {(t["cd_cvm"], str(t["dt_ini"]), str(t["dt_fim"])): t
                  for t in painel.fco_trimestral if t["estado"] == "valido"}
    ativos = {(a["cd_cvm"], str(a["dt_fim"])): a
              for a in painel.ativo if a["estado"] == "valido"}
    violadas = 0
    for obs in amostra:
        d = auditor._como_data(obs["D"])
        chaves = []
        for r in obs["linhagem"]["janela"]:
            t = trimestres[(obs["cd_cvm"], str(r["dt_ini"]), str(r["dt_fim"]))]
            chaves += [(obs["cd_cvm"], o["conjunto"], o["dt_refer"], int(o["versao"]))
                       for o in json.loads(t["operandos"])]
        a = ativos[(obs["cd_cvm"], str(obs["linhagem"]["ativo"]["dt_fim"]))]
        chaves.append((obs["cd_cvm"], a["conjunto"], a["dt_refer"], int(a["versao"])))
        if any(chave in provas and auditor._como_data(provas[chave]) > d for chave in chaves):
            violadas += 1
    return violadas


# --- tradução para as formas do auditor ------------------------------------------

def linhas_fco(painel: pp.Painel) -> list[dict]:
    """Forma de `auditor.carregar_fco`."""
    return [
        {"cd_cvm": t["cd_cvm"], "trimestre": t["trimestre"], "dt_ini": t["dt_ini"],
         "dt_fim": t["dt_fim"], "fco": t["valor_reais"], "dt_receb": t["disponivel_em"],
         "demonstrativo": t["demonstrativo"], "origem": t["origem"], "versao": t["versao"]}
        for t in painel.fco_trimestral if t["estado"] == "valido"
    ]


def linhas_ativo(painel: pp.Painel, incluir_nao_informativo: bool = False) -> list[dict]:
    """Forma de `auditor.carregar_ativo`."""
    estados = {"valido", "nao_informativo"} if incluir_nao_informativo else {"valido"}
    return [
        {"cd_cvm": a["cd_cvm"], "trimestre": a["trimestre"], "ativo": a["valor_reais"],
         "dt_receb": a["disponivel_em"], "versao": a["versao"], "demonstrativo": "BPA",
         "dt_ini": None, "dt_fim": a["dt_fim"]}
        for a in painel.ativo if a["estado"] in estados
    ]


def duracoes(painel: pp.Painel) -> list[dict]:
    """Forma de `auditor.carregar_duracoes` — a duração é RECOMPUTADA das datas (G2-pp)."""
    return [
        {"cd_cvm": t["cd_cvm"], "trimestre": t["trimestre"],
         "dias": (t["dt_fim"] - t["dt_ini"]).days + 1,
         "demonstrativo": t["demonstrativo"], "origem": t["origem"]}
        for t in painel.fco_trimestral if t["estado"] == "valido"
    ]


def nulos(painel: pp.Painel) -> dict[str, dict[str, int]]:
    """Forma de `auditor.carregar_nulos`, contada em TODOS os candidatos (G5-pp)."""
    return {
        "fco": {"linhas": len(painel.fco_acumulado),
                "nulos": sum(1 for a in painel.fco_acumulado if a["estado"] == "valor_nulo")},
        "ativo": {"linhas": len(painel.ativo),
                  "nulos": sum(1 for a in painel.ativo if a["estado"] == "valor_nulo")},
    }


def unicidade(fco: list[dict]) -> int:
    """G3-pp: um valor por (companhia, trimestre)."""
    chaves = [(r["cd_cvm"], r["trimestre"]) for r in fco]
    return len(chaves) - len(set(chaves))


#: Contagens de descarte que O1 proíbe publicar antes do pré-registro: a de
#: FCO TTM não positivo é um agregado de sinal de FCO (O1.1).
DESCARTES_NAO_PUBLICADOS = ("fco_ttm_nao_positivo",)


def g1_cego(fco: list[dict], ativo: list[dict], painel: pp.Painel | None = None,
            provas: dict[tuple, object] | None = None) -> dict:
    """Constrói a amostra SEM calcular o rótulo e mede G1 (G6-pp).

    **Correção da auditoria de 16/09:** a versão anterior chamava a construção
    completa — que soma S1 e S2 e calcula `y` — e só apagava `y` depois. Agora
    o rótulo nunca é somado. E a contagem de FCO TTM não positivo, que a
    construção usa como filtro de elegibilidade, não sai no artefato.
    """
    if painel is None:
        raise ProvasAusentes("G1.4 exige painel para verificar cobertura das provas")
    _exigir_provas(painel, provas)
    amostra, descarte = auditor.construir_amostra(fco, ativo, calcular_rotulo=False)
    if any("y" in o for o in amostra):
        raise AssertionError("O1: a construção cega devolveu rótulo")
    resultado = auditor.gate_g1(amostra, descarte)
    # P6: a disponibilidade da prova de escala, reconferida fora do construtor.
    resultado["g1_4_prova_de_escala_publicada_depois_de_D"] = (
        g1_provas_depois_de_d(amostra, painel, provas or {}))
    if resultado["g1_4_prova_de_escala_publicada_depois_de_D"]:
        resultado["aprovado"] = False
    resultado["descartes"] = {
        k: ("omitido por O1" if k in DESCARTES_NAO_PUBLICADOS else v)
        for k, v in resultado["descartes"].items()
    }
    return resultado


def documentos_decididos(pasta: Path) -> set[tuple]:
    """Documentos com veredito de escala decidido (confirmado, corrigido ou herdado)."""
    decididos = set()
    for nome in ("evidencias.jsonl", "herdados.jsonl"):
        caminho = pasta / nome
        if not caminho.is_file():
            raise FileNotFoundError(f"{caminho}: o diagnóstico G0.5 exige a adjudicação")
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            r = json.loads(linha)
            if r["veredito"] != "indecidivel":
                decididos.add((r["cd_cvm"], r["conjunto"], r["dt_refer"], int(r["versao"])))
    return decididos


def _configuracao_de_escala(t: dict) -> str:
    declaradas = "declaradas_diferentes" if len(set(t["escalas_declaradas"].split("+"))) > 1 \
        else "declaradas_iguais"
    aplicadas = "aplicadas_diferentes" if len(set(t["escalas_aplicadas"].split("+"))) > 1 \
        else "aplicadas_iguais"
    return f"{declaradas}|{aplicadas}"


def diagnostico_g0_5(painel: pp.Painel, decididos: set[tuple]) -> dict:
    """Proposta G0.5 do pré-registro v2 — medida, NÃO governa este lote.

    **G5.1 (17/09):** trimestre válido com operandos heterogêneos na escala
    declarada **ou aplicada**, em que algum operando não tem veredito decidido.
    A versão de 16/09 olhava só a declarada e deixava fora a correção parcial
    (declaradas iguais, aplicadas diferentes). Publicado por configuração.
    """
    validos = [t for t in painel.fco_trimestral if t["estado"] == "valido"]
    por_configuracao = {}
    arriscados = 0
    for t in validos:
        config = _configuracao_de_escala(t)
        entrada = por_configuracao.setdefault(config, {"trimestres": 0, "sem_veredito": 0})
        entrada["trimestres"] += 1
        if config == "declaradas_iguais|aplicadas_iguais":
            continue
        if any((t["cd_cvm"], o["conjunto"], o["dt_refer"], int(o["versao"])) not in decididos
               for o in json.loads(t["operandos"])):
            entrada["sem_veredito"] += 1
            arriscados += 1
    heterogeneos = sum(v["trimestres"] for k, v in por_configuracao.items()
                       if k != "declaradas_iguais|aplicadas_iguais")
    return {
        "trimestres_validos": len(validos),
        "com_escalas_heterogeneas": heterogeneos,
        "por_configuracao": dict(sorted(por_configuracao.items())),
        "sem_veredito_em_algum_operando": arriscados,
        "fracao": round(arriscados / len(validos), 6) if validos else None,
        "limiar": ("[DECIDIR] — 0,5% seria política NOVA para outro evento e outro "
                   "denominador; não é herdado de G0.3"),
        "governa_este_lote": False,
    }


class ProvasAusentes(Exception):
    """Painel com escala corrigida e sem datas de prova: G1.4 não aprova no escuro."""


def _exigir_provas(painel: pp.Painel, provas: dict | None) -> None:
    """CRF-02: cobertura integral, inclusive nas entradas profundas do G1.

    A data independente vem de datas_das_provas; NÃO usar dt_prova do painel
    para completar/verificar este mapa: isso esconderia um construtor errado.
    """
    exigidas = {(d.cd_cvm, d.conjunto, d.dt_refer, d.versao)
                for d in painel.documentos.values() if d.base_escala != "declarada"}
    provas = {} if provas is None else provas
    faltam = exigidas - provas.keys()
    invalidas = {k for k in exigidas & provas.keys() if type(provas[k]) is not date}
    if faltam or invalidas:
        raise ProvasAusentes(
            f"provas incompletas: {len(faltam)} ausentes, {len(invalidas)} datas inválidas; "
            "passe `datas_das_provas(con, correcoes)`")


class PainelViolaContrato(Exception):
    """O construtor violou uma condição de falsificação da parte 1.

    Defeito do instrumento derruba a execução (§4.4 regra 5): não produz
    veredito de gate.
    """


def verificar_falsificacoes(painel: pp.Painel, con=None,
                            provas: dict[tuple, object] | None = None) -> dict[str, int]:
    """Condições 1–5 e 8 da parte 1 do contrato do lote C, sobre o painel real.

    c3 (P6, 17/09): o operando mais tardio conta a recepção **e** a prova da
    escala, esta recalculada por `datas_das_provas`.
    """
    _exigir_provas(painel, provas)
    validos = [t for t in painel.fco_trimestral if t["estado"] == "valido"]
    minimo, maximo = pp.BANDA_DIAS
    provas = provas or {}
    receb = {}
    for d in painel.documentos.values():
        chave = (d.cd_cvm, d.conjunto, d.dt_refer, d.versao)
        receb[chave] = max(d.dt_receb, provas.get(chave, d.dt_receb))
    disponibilidade_errada = inicio_errado = sem_documento = 0
    for t in painel.fco_trimestral:
        operandos = json.loads(t["operandos"])
        datas = [receb.get((t["cd_cvm"], o["conjunto"], o["dt_refer"], int(o["versao"])))
                 for o in operandos]
        if any(d is None for d in datas):
            sem_documento += 1
        elif t["disponivel_em"] != max(datas):
            disponibilidade_errada += 1
        if {o["dt_ini"] for o in operandos} != {str(t["dt_ini_exercicio"])}:
            inicio_errado += 1
    por_estado = sum(v["linhas"] for v in painel.inventario["fco_trimestral_por_estado"].values())
    violacoes = {
        "c1_valido_fora_da_banda": sum(
            1 for t in validos if not minimo <= (t["dt_fim"] - t["dt_ini"]).days + 1 <= maximo),
        "c2_trimestre_valido_repetido": unicidade(linhas_fco(painel)),
        "c3_disponibilidade_diferente_do_operando_mais_tardio": disponibilidade_errada,
        "c4_subtracao_entre_exercicios": inicio_errado,
        "c8_operando_sem_documento": sem_documento,
        "c5_candidato_sem_destino": abs(len(painel.fco_trimestral) - len(painel.fco_acumulado))
        + abs(por_estado - len(painel.fco_trimestral)),
    }
    if con is not None:
        # M4 (auditoria): a exclusão de LINHAS também é falsificação, não só a
        # de documentos. Toda declaração `ÚLTIMO` da fonte tem de estar contada.
        fonte_fco = con.execute(
            "SELECT count(*) FROM declaracoes d JOIN universo USING (cd_cvm) "
            "WHERE d.cd_conta = '6.01' AND d.demonstrativo LIKE 'DFC%' "
            "AND d.ordem = 'ÚLTIMO'").fetchone()[0]
        fonte_ativo = con.execute(
            "SELECT count(*) FROM declaracoes d JOIN universo USING (cd_cvm) "
            "WHERE d.cd_conta = '1' AND d.demonstrativo = 'BPA' "
            "AND d.ordem = 'ÚLTIMO'").fetchone()[0]
        violacoes["c8_linha_de_fco_fora_do_painel"] = abs(
            fonte_fco - sum(a["declaracoes"] for a in painel.fco_acumulado))
        violacoes["c8_linha_de_ativo_fora_do_painel"] = abs(
            fonte_ativo - sum(a["declaracoes"] for a in painel.ativo))
        na_fonte = con.execute(
            "SELECT count(*) FROM (SELECT DISTINCT d.cd_cvm, d.conjunto, d.dt_refer, d.versao "
            "FROM declaracoes d JOIN universo USING (cd_cvm))").fetchone()[0]
        violacoes["c8_documento_fora_do_painel"] = na_fonte - len(painel.documentos)
    if any(violacoes.values()):
        raise PainelViolaContrato(violacoes)
    return violacoes


def medir(painel: pp.Painel, decididos: set[tuple] | None = None,
          provas: dict[tuple, object] | None = None) -> dict:
    _exigir_provas(painel, provas)
    fco, ativo, dur = linhas_fco(painel), linhas_ativo(painel), duracoes(painel)
    g0 = auditor.gate_g0(fco, ativo, dur, nulos(painel))
    g0["g3_pp_trimestres_repetidos"] = unicidade(fco)
    if g0["g3_pp_trimestres_repetidos"]:
        g0["aprovado"] = False
    # Diagnóstico declarado, não governa: o efeito da regra A2 sobre G0.3.
    com_nao_informativo = auditor.gate_g0(
        fco, linhas_ativo(painel, incluir_nao_informativo=True), dur, nulos(painel))
    g0["diagnostico_a2"] = {
        "ativos_nao_informativos": sum(1 for a in painel.ativo if a["estado"] == "nao_informativo"),
        "saltos_de_escala_se_fossem_incluidos": com_nao_informativo["g0_3_saltos_de_escala"],
    }
    # B4 (auditoria): o efeito de tirar da série os ativos em conflito ou ambíguos.
    todos_os_ativos = [
        {**linha, "estado": "valido"} for linha in painel.ativo
        if linha["estado"] in ("valido", "conflito_de_declaracoes", "ambiguo_exercicio")
    ]
    com_conflito = auditor.gate_g0(
        fco, linhas_ativo(pp.Painel(todos_os_ativos, [], [], {}, {})), dur, nulos(painel))
    g0["diagnostico_conflito_e_ambiguo"] = {
        "ativos_fora_da_serie": sum(1 for a in painel.ativo if a["estado"] in (
            "conflito_de_declaracoes", "ambiguo_exercicio")),
        "saltos_de_escala_se_fossem_incluidos": com_conflito["g0_3_saltos_de_escala"],
    }
    # M5 (auditoria): a leitura literal da v1 contaria como G0.1 os trimestres
    # derivados de acumulados de métodos diferentes. Publicado para a decisão.
    g0["diagnostico_g0_1_literal"] = {
        "trimestres_validos_com_operandos_de_metodos_diferentes": sum(
            1 for t in painel.fco_trimestral
            if t["estado"] == "valido" and len(set(t["metodos"].split("+"))) > 1),
        "companhias": len({
            t["cd_cvm"] for t in painel.fco_trimestral
            if t["estado"] == "valido" and len(set(t["metodos"].split("+"))) > 1}),
    }
    if decididos is not None:
        g0["diagnostico_g0_5_proposto"] = diagnostico_g0_5(painel, decididos)
    g1 = g1_cego(fco, ativo, painel, provas)
    primeiro = next((g["gate"] for g in (g0, g1) if not g["aprovado"]), None)
    return {
        "cadeia": [g0, g1],
        "primeiro_reprovado": primeiro,
        "veredito": "G0 E G1 APROVADOS" if primeiro is None else f"REPROVADO EM {primeiro}",
        "observacao": (
            "G1 é medido mesmo com G0 reprovado, como diagnóstico estrutural: "
            "contagens de observações e de violações, sem rótulo."
        ),
    }


def executar(correcoes: dict[tuple, dict], caminho_correcoes: Path | None,
             destino: Path = DESTINO, adjudicacao: Path = ADJUDICACAO,
             nome: str | None = None, gravar_painel: bool = True) -> dict:
    """`nome` e `gravar_painel` existem para o diagnóstico da execução 1 (RC1):
    medido ao lado, sem sobrescrever o painel governante."""
    if correcoes and not isinstance(correcoes, CorrecoesValidadas):
        raise CorrecoesNaoValidadas(
            "correções precisam vir de `carregar_correcoes` (V1): um dict montado "
            "à mão não passou pelas condições 11, 12 e 14 nem pela conferência de pacotes")
    if correcoes and caminho_correcoes is None:
        # M2 (17/09): o artefato registraria "SEM CORREÇÕES" num painel corrigido.
        raise CorrecoesNaoValidadas("correções sem o caminho do manifesto de origem")
    if isinstance(correcoes, CorrecoesValidadas) and caminho_correcoes is not None \
            and correcoes.origem_sha256 != _sha256(caminho_correcoes):
        raise CorrecoesNaoValidadas("o manifesto mudou depois de validado")
    if isinstance(correcoes, CorrecoesValidadas) and \
            correcoes.conteudo_sha256 != correcoes.impressao():
        raise CorrecoesNaoValidadas("as correções mudaram em memória depois de validadas")
    con = duckdb.connect(":memory:")
    zips = fz.extrair(con)
    hash_compartilhado = pp.preparar_universo(con)
    painel = pp.construir(con, correcoes)
    provas = datas_das_provas(con, correcoes)
    falsificacoes = verificar_falsificacoes(painel, con, provas)
    resultado = {
        "falsificacoes_parte_1": falsificacoes,
        "contrato": "resultados/contratos_lote_c_painel_pesquisa_rank03b_2026-09-16.md",
        "entradas": {
            "zips_sha256": zips,
            "cvm_treino_sha256": hash_compartilhado,
            # R1 (auditoria): o manifesto de aquisição também é entrada.
            "manifesto_aquisicao_sha256": _sha256(fz.RAIZ / "artefatos" / "painel_pesquisa_rank03b"
                                                  / "rad" / "manifesto_aquisicao.jsonl"),
            "correcoes_escala": (
                {"caminho": str(caminho_correcoes.relative_to(RAIZ)),
                 "sha256": _sha256(caminho_correcoes), "linhas": len(correcoes)}
                if caminho_correcoes else "SEM CORREÇÕES (--sem-correcoes)"
            ),
        },
        "codigo_sha256": {c: _sha256(RAIZ / c) for c in CODIGO},
        "parametros": {"banda_dias": pp.BANDA_DIAS,
                       "piso_nao_informativo": pp.PISO_NAO_INFORMATIVO},
        "digest_do_painel": painel.digest,
        "inventario": painel.inventario,
        **medir(painel, documentos_decididos(adjudicacao) if caminho_correcoes else None,
                provas),
    }
    _sem_chave_proibida(resultado)
    destino.mkdir(parents=True, exist_ok=True)
    nome = nome or ("gates_g0_g1.json" if caminho_correcoes else "gates_g0_g1_sem_correcoes.json")
    (destino / nome).write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    if not gravar_painel:
        return resultado
    pp.gravar(painel, destino / "painel.duckdb" if caminho_correcoes
              else destino / "painel_sem_correcoes.duckdb",
              {k: resultado[k] for k in ("contrato", "entradas", "codigo_sha256",
                                         "parametros", "digest_do_painel")})
    return resultado


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--correcoes", type=Path, default=None)
    grupo.add_argument("--sem-correcoes", action="store_true")
    grupo.add_argument("--diagnostico-execucao-1", action="store_true",
                        help="mede G0/G1 com o manifesto da execução 1 (RC1), sem gravar painel")
    args = parser.parse_args(argv)
    if args.diagnostico_execucao_1:
        from scripts import adjudicar_escala_rank03b as adj
        pasta = ADJUDICACAO / "execucao1"
        caminho = pasta / "correcoes_escala.csv"
        correcoes = carregar_correcoes(caminho, tabela=adj.TABELA_S2_EXECUCAO_1,
                                       exigir_escala_nas_pontas=False,
                                       exigir_evidencia_numerica=False)
        resultado = executar(correcoes, caminho, adjudicacao=pasta,
                             nome="gates_g0_g1_diagnostico_execucao1.json", gravar_painel=False)
        print(f"diagnóstico execução 1: {resultado['veredito']}")
        return 0
    if args.sem_correcoes:
        correcoes, caminho = {}, None
    else:
        caminho = args.correcoes.resolve()
        correcoes = carregar_correcoes(caminho)
    resultado = executar(correcoes, caminho)
    g0, g1 = resultado["cadeia"]
    print(f"veredito: {resultado['veredito']}")
    print(f"  G0: saltos {g0['g0_3_saltos_de_escala']} ({g0['g0_3_fracao']:.4%}), "
          f"fora da banda {g0['g0_2_fora_da_duracao_de_um_trimestre']}, "
          f"métodos somados {g0['g0_1_companhia_trimestre_com_os_dois_metodos']}, "
          f"nulos {g0['g0_4_nulos_nas_contas_usadas']}")
    print(f"  G1: {g1['observacoes']} observações em {g1['companhias']} companhias, "
          f"aprovado={g1['aprovado']}")
    return 0 if resultado["primeiro_reprovado"] is None else 2


if __name__ == "__main__":
    sys.exit(principal())
