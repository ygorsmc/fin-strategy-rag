"""Manifesto de correções de escala POR CONTA do painel de pesquisa do Rank 3-B.

Contrato: `resultados/contratos_caminho_medicao_rank03b_2026-09-27.md`, parte A.
Cumpre as condições 1 a 3 do §12-bis do rascunho v2: esquema fechado no produtor
e no consumidor (aqui), G0.3 lido pela escala do ativo e G0.5 pela do FCO (o
construtor aplica a escala por conta) e a regra 3 do §5.5 (executor v2).

**A mesma função valida no produtor e no consumidor** (A2; §4.4, regra 7): uma
linha só é aplicada se a prova que ela cita existe no arquivo de evidências da
ROTA-1 com o hash declarado, se sustenta pela validação da própria ROTA-1 e foi
aprovada pela conferência independente, sem nenhuma correção recusada.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from scripts import adjudicar_escala_rank03b as adj
from scripts import gates_painel_pesquisa_rank03b as gates
from scripts import painel_pesquisa_rank03b as pp
from scripts import rota_prova_rank03b as rota

RAIZ = Path(__file__).resolve().parents[1]
MANIFESTO = RAIZ / "corpus" / "cvm" / "painel_pesquisa_rank03b" / "correcoes_escala_por_conta.csv"

#: A1: exatamente estas colunas, nesta ordem.
COLUNAS = [
    "id_correcao", "cd_cvm", "conjunto", "dt_refer", "versao", "id_doc", "sha256_pacote",
    "conta", "escala_declarada", "escala_aplicada", "base", "prova", "id_prova", "regra",
    "sha256_evidencias", "sha256_conferencia", "impressao_digital",
]
PROVA_DA_CONTA = {"1": "celula_propria", "6.01": "cadeia_dfc"}
BASE = "corrigida_conta"


class ManifestoPorContaInvalido(ValueError):
    """Qualquer falha da A2: nenhuma linha é aplicada."""


class CorrecoesPorConta(dict):
    """`{chave do documento: {conta: linha}}`, só depois de validado (A2)."""

    def __init__(self, correcoes: dict, origem_sha256: str):
        super().__init__(correcoes)
        self.origem_sha256 = origem_sha256
        self.conteudo_sha256 = self.impressao()

    def impressao(self) -> str:
        corpo = json.dumps(sorted((list(k), v) for k, v in self.items()), sort_keys=True, default=str)
        return hashlib.sha256(corpo.encode()).hexdigest()


def _chave(linha: dict) -> tuple:
    return (linha["cd_cvm"], linha["conjunto"], linha["dt_refer"], int(linha["versao"]))


def validar_linhas(linhas: list[dict], registros: list[dict], sha_evidencias: str,
                   conferencia: dict, sha_conferencia: str,
                   integros: dict[str, set[str]], chaves_do_legado=frozenset()) -> None:
    """A2, itens 2 a 6. Levanta antes de qualquer aplicação."""
    try:
        resumo = rota.validar_arquivo(registros)
        if resumo["parada"]:
            raise ManifestoPorContaInvalido("parada B7: controle corrigido na ROTA-1")
        rota.validar_conferencia(conferencia, registros, sha_evidencias)
    except rota.EvidenciaInvalida as erro:
        raise ManifestoPorContaInvalido(f"evidências ou conferência inválidas: {erro}") from None
    por_id = {r["id_prova"]: r for r in registros}
    aprovadas = {i for i, c in (conferencia.get("correcoes") or {}).items()
                 if c.get("resultado") == "aprovada"}
    ids, pares = set(), set()
    for linha in linhas:
        ident = linha.get("id_correcao") or "?"
        if not linha["id_correcao"] or ident in ids:
            raise ManifestoPorContaInvalido(f"{ident}: id_correcao vazio ou repetido")
        ids.add(ident)
        if linha["conta"] not in PROVA_DA_CONTA:
            raise ManifestoPorContaInvalido(f"{ident}: conta fora do contrato")
        if linha["escala_declarada"] not in rota.ESCALAS or linha["escala_aplicada"] not in rota.ESCALAS:
            raise ManifestoPorContaInvalido(f"{ident}: escala fora do vocabulário")
        if linha["escala_aplicada"] == linha["escala_declarada"]:
            raise ManifestoPorContaInvalido(f"{ident}: manifesto só leva o que muda")
        if linha["base"] != BASE or linha["regra"] != rota.REGRA or \
                linha["prova"] != PROVA_DA_CONTA[linha["conta"]]:
            raise ManifestoPorContaInvalido(f"{ident}: base, regra ou prova fora do contrato")
        try:
            chave = _chave(linha)
        except ValueError:
            raise ManifestoPorContaInvalido(f"{ident}: versão não inteira") from None
        par = (chave, linha["conta"])
        if par in pares:
            raise ManifestoPorContaInvalido(f"{ident}: duas linhas para o mesmo documento e conta")
        pares.add(par)
        if chave in chaves_do_legado:
            raise ManifestoPorContaInvalido(f"{ident}: documento também no manifesto por documento")
        if linha["sha256_evidencias"] != sha_evidencias or \
                linha["sha256_conferencia"] != sha_conferencia:
            raise ManifestoPorContaInvalido(f"{ident}: hash de evidências ou de conferência divergente")
        if linha["sha256_pacote"] not in integros.get(str(linha["id_doc"]), set()):
            raise ManifestoPorContaInvalido(f"{ident}: pacote não consta íntegro na aquisição")
        prova = por_id.get(linha["id_prova"])
        if prova is None or prova["conta"] != linha["conta"] or \
                (prova["cd_cvm"], prova["conjunto"], prova["dt_refer"], int(prova["versao"])) != chave or \
                prova["id_doc"] != linha["id_doc"] or prova["sha256_pacote"] != linha["sha256_pacote"]:
            raise ManifestoPorContaInvalido(f"{ident}: prova de outro documento ou conta")
        if prova["veredito"] != "corrigida" or \
                prova["escala_do_formulario"] != linha["escala_aplicada"] or \
                prova["escala_declarada"] != linha["escala_declarada"] or \
                prova["prova"] != linha["prova"]:
            raise ManifestoPorContaInvalido(f"{ident}: a prova não sustenta esta correção")
        if linha["id_prova"] not in aprovadas:
            raise ManifestoPorContaInvalido(f"{ident}: prova sem aprovação na conferência")


def _ler_e_validar_esquema(caminho: Path) -> tuple[list[dict], str]:
    """A2.1: esquema fechado e sintaxe estrita, ANTES de olhar qualquer linha."""
    if not caminho.is_file():
        raise ManifestoPorContaInvalido(f"{caminho} não existe")
    dados = caminho.read_bytes()
    texto = dados.decode("utf-8")
    try:
        gates._validar_sintaxe_csv(texto)
        leitor = csv.DictReader(io.StringIO(texto, newline=""), strict=True)
        colunas = leitor.fieldnames
        if colunas != COLUNAS:
            raise ManifestoPorContaInvalido(
                "esquema do manifesto por conta inválido: colunas ausentes, extras, "
                "duplicadas ou fora de ordem")
        linhas = list(leitor)
    except csv.Error as erro:
        raise ManifestoPorContaInvalido(f"sintaxe CSV: {erro}") from None
    if any(None in r or any(v is None for v in r.values()) for r in linhas):
        raise ManifestoPorContaInvalido("linha com quantidade de campos diferente do cabeçalho")
    return linhas, hashlib.sha256(dados).hexdigest()


def carregar(caminho: Path = MANIFESTO, pasta_rota: Path = rota.DESTINO,
             aquisicao: Path | None = None, chaves_do_legado=frozenset()) -> CorrecoesPorConta:
    """Consumidor: tudo da A2 antes de devolver a primeira correção."""
    linhas, origem = _ler_e_validar_esquema(caminho)
    registros, sha_ev = rota.ler_evidencias(pasta_rota / "evidencias.jsonl")
    conferencia, sha_conf = rota.ler_conferencia(pasta_rota / "conferencia.json")
    validar_linhas(linhas, registros, sha_ev, conferencia, sha_conf,
                   adj.pacotes_integros(aquisicao or adj.rad.MANIFESTO), chaves_do_legado)
    correcoes: dict[tuple, dict] = {}
    for linha in linhas:
        correcoes.setdefault(_chave(linha), {})[linha["conta"]] = dict(linha)
    return CorrecoesPorConta(correcoes, origem)


def linhas_do_manifesto(con, registros: list[dict], sha_evidencias: str,
                        sha_conferencia: str) -> list[dict]:
    """Produtor: uma linha por correção provada das contas `1` e `6.01`."""
    linhas = []
    corrigidas = sorted((r for r in registros
                         if r["veredito"] == "corrigida" and r["conta"] in PROVA_DA_CONTA),
                        key=lambda r: (r["cd_cvm"], r["dt_refer"], r["conjunto"], r["versao"], r["conta"]))
    for n, r in enumerate(corrigidas, start=1):
        brutos = adj._brutos(con, r)
        linhas.append({
            "id_correcao": f"ESCC-{n:04d}", "cd_cvm": r["cd_cvm"], "conjunto": r["conjunto"],
            "dt_refer": r["dt_refer"], "versao": str(r["versao"]), "id_doc": r["id_doc"],
            "sha256_pacote": r["sha256_pacote"], "conta": r["conta"],
            "escala_declarada": r["escala_declarada"], "escala_aplicada": r["escala_do_formulario"],
            "base": BASE, "prova": r["prova"], "id_prova": r["id_prova"], "regra": rota.REGRA,
            "sha256_evidencias": sha_evidencias, "sha256_conferencia": sha_conferencia,
            "impressao_digital": pp.impressao_digital(brutos),
        })
    return linhas


def escrever(caminho: Path, linhas: list[dict], registros: list[dict], sha_evidencias: str,
             conferencia: dict, sha_conferencia: str, integros: dict[str, set[str]],
             chaves_do_legado=frozenset()) -> str:
    """Produtor: valida com a MESMA função do consumidor, grava e confere relendo."""
    validar_linhas(linhas, registros, sha_evidencias, conferencia, sha_conferencia,
                   integros, chaves_do_legado)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=COLUNAS, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)
    relidas, origem = _ler_e_validar_esquema(caminho)
    if relidas != [{k: str(v) for k, v in l.items()} for l in linhas]:
        raise ManifestoPorContaInvalido("o manifesto relido difere do escrito")
    return origem
