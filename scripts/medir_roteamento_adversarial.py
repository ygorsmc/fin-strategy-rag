"""Conjunto adversarial de roteamento: validação, cegamento, concordância e medição.

Protocolo em `resultados/pre_registro_roteamento_adversarial_2026-09-15.md`. Custo
zero: K1, K2 e K3 são determinísticos e nada aqui chama provedor externo.

    python -m scripts.medir_roteamento_adversarial exclusoes
    python -m scripts.medir_roteamento_adversarial validar --particao dev --arquivo CSV
    python -m scripts.medir_roteamento_adversarial cegar --dev CSV --holdout CSV --semente N --saida-rotulos CSV [CSV ...]
    python -m scripts.medir_roteamento_adversarial concordancia --dev CSV --holdout CSV --anotador CSV [CSV ...]
    python -m scripts.medir_roteamento_adversarial consolidar --dev CSV --holdout CSV --anotador CSV --adjudicacao CSV --particoes dev --saida CSV
    python -m scripts.medir_roteamento_adversarial medir --ouro CSV --particoes dev --componentes ambos
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parents[1]
DIR_PROTOCOLO = RAIZ / "artefatos" / "roteamento_adversarial"
DIR_ANOTACAO = DIR_PROTOCOLO / "anotacao"
DIR_CEGAMENTO = DIR_PROTOCOLO / "cegamento"
DIR_MEDICOES = DIR_PROTOCOLO / "medicoes"
DIR_BASE = DIR_PROTOCOLO / "linha_de_base"
DIARIO = DIR_PROTOCOLO / "diario_protocolo.jsonl"
PRE_REGISTRO = RAIZ / "resultados" / "pre_registro_roteamento_adversarial_2026-09-15.md"
CAMINHO_RESULTADO = RAIZ / "resultados" / "roteamento_adversarial.json"

CAMPOS_AUTOR = (
    "id",
    "estrato",
    "texto",
    "horizonte",
    "metrica",
    "camada_apontada",
    "emissor",
    "registro",
    "observacao",
)
CAMPOS_ANOTADOR = (
    "id_neutro",
    "horizonte",
    "clausula_horizonte",
    "metrica",
    "clausula_metrica",
    "camada_apontada",
    "clausula_camada",
    "confianca",
)
CAMPOS_ADJUDICACAO = ("particao", "id", "coluna", "rotulo_ouro", "clausula", "nota")
CAMPOS_OURO = (
    "id",
    "particao",
    "estrato",
    "texto",
    "horizonte",
    "metrica",
    "camada_apontada",
    "emissor",
    "registro",
    "origem_ouro",
    "notas_adjudicacao",
)
COLUNAS_ROTULO = ("horizonte", "metrica", "camada_apontada")
HORIZONTES = frozenset(
    {"futuro", "guidance_publicado", "periodo_sem_dado", "passado_ou_presente"}
)
METRICAS = frozenset({"resultado", "outra_financeira", "preco_ou_acao", "nenhuma"})
CAMADAS = frozenset({"release", "painel_cvm", "nenhuma"})
VOCABULARIO_ROTULO = {
    "horizonte": HORIZONTES,
    "metrica": METRICAS,
    "camada_apontada": CAMADAS,
}
REGISTROS = frozenset({"formal", "informal"})
CONTAGENS = {"PF": 45, "PG": 12, "PP": 15, "PO": 12, "PS": 6, "CR": 20, "CP": 20, "AP": 10}
PREFIXOS = {"dev": "RAD", "holdout": "RAH"}
TOTAL_POR_PARTICAO = sum(CONTAGENS.values())
KAPPA_MINIMO = 0.60
NOTA_MINIMA_ADJUDICACAO = 20

EMISSORES_SO_PAINEL = ("inter", "bmg", "daycoval", "pine", "mercantil", "irb")
JANELA_PAINEL_BANCOS = ("1T2025", "2T2026")
COMPONENTES_MEDIDOS = ("src/projecao.py", "app_streamlit.py", "src/seguranca.py")

ETAPA_CODIGO_CONGELADO = "08_codigo_congelado"
ETAPA_HOLDOUT_ADJUDICADA = "09_holdout_adjudicada"

# Casos que quem ajusta os componentes já leu: medir generalização neles é medir memória.
PARAFRASES_CONHECIDAS = (
    "Qual o outlook de lucro do Itaú?",
    "O lucro do Itaú tende a piorar?",
    "Qual a perspectiva de lucro líquido do Itaú para 2026?",
    "Espera-se queda no lucro do Itaú?",
    "Como estará o lucro do Itaú daqui a um ano?",
    "Como estará o lucro do Itaú em 2027?",
    "O resultado do Bradesco tende a piorar?",
    "Qual o outlook de resultado do BB?",
    "Quanto o Santander lucrou no 2T2025 segundo o resultado apresentado a investidores?",
    "Quanto o Santander lucrou no 2T2025 conforme o material que o banco publicou?",
    "Quanto o Santander lucrou no 2T2025 na visão da administração?",
    "Qual o ativo total do Itaú no 3T2025 em IFRS?",
    "Qual o patrimônio líquido recorrente do BB no 3T2025?",
)

_COERENCIA_ESTRATO = {
    "PF": lambda i: i["horizonte"] == "futuro" and i["metrica"] == "resultado",
    "PG": lambda i: i["horizonte"] == "guidance_publicado" and i["metrica"] == "resultado",
    "PP": lambda i: i["horizonte"] == "passado_ou_presente" and i["metrica"] == "resultado",
    "PO": lambda i: i["horizonte"] == "futuro" and i["metrica"] == "outra_financeira",
    "PS": lambda i: i["horizonte"] == "periodo_sem_dado"
    and i["metrica"] in {"resultado", "outra_financeira"},
    "CR": lambda i: i["horizonte"] == "passado_ou_presente"
    and i["camada_apontada"] == "release"
    and i["metrica"] in {"resultado", "outra_financeira"},
    "CP": lambda i: i["horizonte"] == "passado_ou_presente"
    and i["camada_apontada"] in {"painel_cvm", "nenhuma"}
    and i["metrica"] in {"resultado", "outra_financeira"},
    "AP": lambda i: i["horizonte"] == "futuro" and i["metrica"] == "preco_ou_acao",
}

_PADRAO_PERIODO = re.compile(r"\b([1-4])t((?:20)?\d{2})\b")
_PADRAO_ANO = re.compile(r"\b20\d{2}\b")


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, sem pontuação e com espaço único."""
    decomposto = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    sem_pontuacao = re.sub(r"[^\w\s]", " ", sem_acento.casefold())
    return re.sub(r"\s+", " ", sem_pontuacao).strip()


def _formas_de_emissor() -> tuple[str, ...]:
    from src.normalizacao import APELIDOS_BANCOS

    formas = {
        normalizar(apelido)
        for canonico, apelidos in APELIDOS_BANCOS.items()
        for apelido in apelidos
    }
    formas |= set(EMISSORES_SO_PAINEL) | {"c6", "c6 bank"}
    return tuple(sorted(formas, key=len, reverse=True))


def normalizar_estrutura(texto: str) -> str:
    """Normaliza e troca emissor e período por marcadores.

    Duas perguntas com a mesma estrutura só diferem pelo banco ou pelo trimestre —
    que é exatamente a repetição disfarçada que o brief proíbe.
    """
    resultado = normalizar(texto)
    for forma in _formas_de_emissor():
        resultado = re.sub(rf"\b{re.escape(forma)}\b", " EMISSOR ", resultado)
    resultado = _PADRAO_PERIODO.sub(" PERIODO ", resultado)
    resultado = _PADRAO_ANO.sub(" ANO ", resultado)
    return re.sub(r"\s+", " ", resultado).strip()


def _ordinal_trimestre(numero: str, ano: str) -> int:
    ano_completo = int(ano) if len(ano) == 4 else 2000 + int(ano)
    return ano_completo * 4 + int(numero)


def sha256_arquivo(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def _relativo(caminho: Path) -> str:
    """Relativo à raiz quando possível; absoluto quando o arquivo está fora dela."""
    absoluto = Path(caminho).resolve()
    try:
        return str(absoluto.relative_to(RAIZ))
    except ValueError:
        return str(absoluto)


def construir_exclusoes() -> dict[str, list[str]]:
    """Texto normalizado → fontes em que ele já existe."""
    fontes: dict[str, set[str]] = {}

    def acrescentar(texto: str, fonte: str) -> None:
        normal = normalizar(texto)
        if len(normal.split()) >= 3:
            fontes.setdefault(normal, set()).add(fonte)

    for relativo, coluna in (
        ("conjunto_padrao/perguntas.csv", "pergunta"),
        ("conjunto_padrao/conjunto_agentes.csv", "pergunta"),
        ("conjunto_padrao/ataques.csv", "texto"),
    ):
        with (RAIZ / relativo).open(encoding="utf-8", newline="") as arquivo:
            for linha in csv.DictReader(arquivo):
                acrescentar(linha[coluna], relativo)
    for relativo in ("tests/test_projecao.py", "tests/test_rota_estruturada.py"):
        fonte = (RAIZ / relativo).read_text(encoding="utf-8")
        for literal in re.findall(r'"([^"\n]{12,})"', fonte):
            acrescentar(literal, relativo)
    for citado in re.findall(r'"([^"\n]{8,})"', PRE_REGISTRO.read_text(encoding="utf-8")):
        acrescentar(citado, PRE_REGISTRO.name)
    for texto in PARAFRASES_CONHECIDAS:
        acrescentar(texto, "parafrases_conhecidas")
    return {texto: sorted(origens) for texto, origens in sorted(fontes.items())}


def carregar_itens(caminho: Path) -> tuple[list[dict], list[str]]:
    with Path(caminho).open(encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        if tuple(leitor.fieldnames or ()) != CAMPOS_AUTOR:
            return [], [f"cabeçalho inesperado: {leitor.fieldnames}"]
        itens = [dict(linha) for linha in leitor]
    return itens, []


@dataclass(frozen=True)
class RelatorioValidacao:
    particao: str
    n_itens: int
    erros: tuple[str, ...]
    contagens: dict = field(default_factory=dict)

    @property
    def aprovado(self) -> bool:
        return not self.erros


def validar_particao(
    itens: list[dict],
    particao: str,
    exclusoes: dict[str, list[str]],
    textos_outra_particao: frozenset[str] = frozenset(),
) -> RelatorioValidacao:
    """Checagens mecânicas do pré-registro. Mensagens citam ids, nunca texto."""
    from src.normalizacao import extrair_bancos_citados

    erros: list[str] = []
    prefixo = PREFIXOS[particao]
    esperados = {f"{prefixo}{n:03d}" for n in range(1, TOTAL_POR_PARTICAO + 1)}
    ids = [item.get("id") for item in itens]
    repetidos = sorted(i for i, n in Counter(ids).items() if n > 1)
    if repetidos:
        erros.append(f"ids repetidos: {repetidos}")
    if set(ids) != esperados:
        faltando = sorted(esperados - set(ids))
        sobrando = sorted(set(ids) - esperados, key=str)
        erros.append(f"ids fora do intervalo — faltando {faltando[:10]}, sobrando {sobrando[:10]}")

    for item in itens:
        ident = item.get("id")
        if None in item or any(v is None for v in item.values()):
            erros.append(f"{ident}: número de colunas diferente do cabeçalho")
            continue
        texto = item["texto"].strip()
        if not texto or "\n" in texto or "\r" in texto:
            erros.append(f"{ident}: texto vazio ou com quebra de linha")
        for campo, validos in (
            ("horizonte", HORIZONTES),
            ("metrica", METRICAS),
            ("camada_apontada", CAMADAS),
            ("registro", REGISTROS),
        ):
            if item[campo] not in validos:
                erros.append(f"{ident}: {campo} fora do vocabulário")
        estrato = item["estrato"]
        if estrato not in CONTAGENS:
            erros.append(f"{ident}: estrato fora do vocabulário")
        elif (
            item["horizonte"] in HORIZONTES
            and item["metrica"] in METRICAS
            and item["camada_apontada"] in CAMADAS
            and not _COERENCIA_ESTRATO[estrato](item)
        ):
            erros.append(f"{ident}: rótulos pretendidos incoerentes com o estrato {estrato}")
        normal = normalizar(texto)
        if normal in exclusoes:
            erros.append(f"{ident}: repete texto já existente em {exclusoes[normal]}")
        if normal in textos_outra_particao:
            erros.append(f"{ident}: repete texto da outra partição")

    contagens = Counter(item.get("estrato") for item in itens)
    for estrato, alvo in CONTAGENS.items():
        if contagens.get(estrato, 0) != alvo:
            erros.append(f"estrato {estrato}: {contagens.get(estrato, 0)} itens, esperado {alvo}")

    estruturas = Counter(normalizar_estrutura(item.get("texto") or "") for item in itens)
    disfarcados = sorted(
        item["id"] for item in itens if estruturas[normalizar_estrutura(item.get("texto") or "")] > 1
    )
    if disfarcados:
        erros.append(f"mesma frase com emissor ou período trocado: {disfarcados}")

    def menciona_banco_do_corpus(texto: str) -> bool:
        return any(banco != "NUBANK" for banco in extrair_bancos_citados(texto))

    def menciona_so_painel(texto: str) -> bool:
        normal = normalizar(texto)
        return any(re.search(rf"\b{nome}\b", normal) for nome in EMISSORES_SO_PAINEL)

    pf = [item for item in itens if item.get("estrato") == "PF"]
    com_banco = sum(menciona_banco_do_corpus(item["texto"]) for item in pf)
    com_so_painel = sum(menciona_so_painel(item["texto"]) for item in pf)
    sem_emissor = sum(
        not menciona_banco_do_corpus(item["texto"]) and not menciona_so_painel(item["texto"])
        for item in pf
    )
    for rotulo, valor, piso in (
        ("PF com banco do corpus", com_banco, 30),
        ("PF com emissor só-painel", com_so_painel, 5),
        ("PF sem emissor ou setorial", sem_emissor, 5),
    ):
        if valor < piso:
            erros.append(f"{rotulo}: {valor}, mínimo {piso}")

    cp = [item for item in itens if item.get("estrato") == "CP"]
    cp_normal = [normalizar(item["texto"]) for item in cp]
    for rotulo, padrao, piso in (
        ("CP com IFRS", r"\bifrs\b", 3),
        ("CP com ITR, DFP ou CVM", r"\b(?:itr|dfp|cvm)\b", 3),
        ("CP com demonstrações ou balanço", r"\b(?:demonstrac\w*|balanc\w*)\b", 2),
    ):
        valor = sum(bool(re.search(padrao, texto)) for texto in cp_normal)
        if valor < piso:
            erros.append(f"{rotulo}: {valor}, mínimo {piso}")
    camadas_cp = Counter(item.get("camada_apontada") for item in cp)
    if camadas_cp.get("painel_cvm", 0) != 10 or camadas_cp.get("nenhuma", 0) != 10:
        erros.append(f"CP deve ter 10 painel_cvm e 10 nenhuma: {dict(camadas_cp)}")
    inicio = _ordinal_trimestre(JANELA_PAINEL_BANCOS[0][0], JANELA_PAINEL_BANCOS[0][2:])
    fim = _ordinal_trimestre(JANELA_PAINEL_BANCOS[1][0], JANELA_PAINEL_BANCOS[1][2:])
    for item, texto in zip(cp, cp_normal):
        for numero, ano in _PADRAO_PERIODO.findall(texto):
            if not inicio <= _ordinal_trimestre(numero, ano) <= fim:
                erros.append(f"{item['id']}: período de CP fora da janela do painel")

    total = len(itens) or 1
    informais = sum(item.get("registro") == "informal" for item in itens)
    sem_interrogacao = sum("?" not in (item.get("texto") or "") for item in itens)
    duplas = sum((item.get("texto") or "").count("?") >= 2 for item in itens)
    if informais / total < 0.20:
        erros.append(f"registro informal: {informais}/{len(itens)}, mínimo 20%")
    if sem_interrogacao / total < 0.10:
        erros.append(f"sem ponto de interrogação: {sem_interrogacao}/{len(itens)}, mínimo 10%")
    if duplas > 3:
        erros.append(f"itens com duas perguntas: {duplas}, máximo 3")

    return RelatorioValidacao(
        particao=particao,
        n_itens=len(itens),
        erros=tuple(erros),
        contagens={
            "estratos": dict(sorted(contagens.items())),
            "pf_com_banco": com_banco,
            "pf_com_so_painel": com_so_painel,
            "pf_sem_emissor": sem_emissor,
            "cp_camadas": dict(camadas_cp),
            "informais": informais,
            "sem_interrogacao": sem_interrogacao,
            "duas_perguntas": duplas,
        },
    )


# --------------------------------------------------------------------------- #
# Diário: a ordem do protocolo é verificada, não lembrada
# --------------------------------------------------------------------------- #


def _diario(caminho: Path | None) -> Path:
    # Resolvido na chamada, não na definição: é o que permite testar a linha de comando.
    return Path(caminho) if caminho is not None else DIARIO


def ler_diario(caminho: Path | None = None) -> list[dict]:
    alvo = _diario(caminho)
    if not alvo.exists():
        return []
    return [
        json.loads(linha)
        for linha in alvo.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]


def registrar_no_diario(entrada: dict, caminho: Path | None = None) -> None:
    registro = {"horario_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entrada}
    with _diario(caminho).open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")


class ProtocoloForaDeOrdem(RuntimeError):
    """Uma etapa foi pedida antes da etapa que a autoriza."""


def exigir_etapa(etapa: str, caminho: Path | None = None) -> dict:
    for entrada in reversed(ler_diario(caminho)):
        if entrada.get("etapa") == etapa:
            return entrada
    raise ProtocoloForaDeOrdem(
        f"a etapa '{etapa}' ainda não consta do diário; o pré-registro proíbe seguir"
    )


def exigir_codigo_congelado(caminho: Path | None = None) -> dict:
    """Congelamento registrado E código em disco idêntico ao congelado."""
    entrada = exigir_etapa(ETAPA_CODIGO_CONGELADO, caminho)
    divergentes = [
        relativo
        for relativo in COMPONENTES_MEDIDOS
        if entrada.get("arquivos", {}).get(relativo) != sha256_arquivo(RAIZ / relativo)
    ]
    if divergentes:
        raise ProtocoloForaDeOrdem(
            f"código mudou depois do congelamento: {divergentes}; a holdout não pode ser lida"
        )
    return entrada


# --------------------------------------------------------------------------- #
# Cegamento
# --------------------------------------------------------------------------- #

_CABECALHO_ANOTADOR = """# Brief do anotador — conjunto adversarial de roteamento

Você vai **rotular {N} perguntas** em português segundo as regras da seção 3 abaixo. As
perguntas estão em `{ITENS}`, com ids neutros de `{PRIMEIRO}` a `{ULTIMO}`.

## Regras de isolamento — obrigatórias

- Leia **somente** este brief e o arquivo de itens. Não abra nenhum outro arquivo do
  repositório, não liste diretórios e não use busca (grep, glob, find). Em particular, não
  procure quem escreveu as perguntas, os rótulos que os autores pretendiam nem o trabalho
  de outro anotador: rotular sem vê-los é o único motivo de você existir.
- No relatório final, liste **todo arquivo que você abriu ou escreveu**.

## O que entregar

- Um CSV UTF-8 no padrão RFC 4180, gravado em: `{SAIDA}`
- Cabeçalho exato, nesta ordem:
  `id_neutro,horizonte,clausula_horizonte,metrica,clausula_metrica,camada_apontada,clausula_camada,confianca`
- Uma linha por item, os {N}, sem pular nenhum.
- Rótulos com os valores exatos das tabelas da seção 3.
- Cláusulas com os códigos da seção 3: `H1` a `H4`, `D-H1` a `D-H4`, `M1` a `M4`, `D-M`,
  `C1` a `C3`, `D-C1` a `D-C3`. Cite o código que **decidiu** o rótulo: se foi um
  desempate, cite o desempate.
- `confianca`: `alta` ou `baixa`.
- **Trabalhe de forma retomável:** grave o cabeçalho logo no início e acrescente as linhas
  em blocos de até 30 itens, salvando a cada bloco. Se o arquivo de saída já existir quando
  você começar, ele é trabalho anterior deste mesmo papel: confira-o e continue dele.

## Como rotular

- Rotule cada coluna de forma independente das outras.
- Leia a pergunta como a pessoa que a escreveu: decide o que se pede, não a presença de uma
  palavra.
- Não há cota por rótulo e as classes não precisam estar equilibradas.
- O relatório final **não pode conter o texto de nenhuma pergunta** — só contagens e ids.

---

"""


def _dividir_em_lotes(itens: list, n_lotes: int) -> list[list]:
    """Fatias contíguas de tamanho quase igual, na ordem recebida."""
    if n_lotes < 1 or n_lotes > len(itens):
        raise ValueError(f"número de lotes inválido: {n_lotes} para {len(itens)} itens")
    base, sobra = divmod(len(itens), n_lotes)
    lotes, inicio = [], 0
    for indice in range(n_lotes):
        tamanho = base + (1 if indice < sobra else 0)
        lotes.append(itens[inicio : inicio + tamanho])
        inicio += tamanho
    return lotes


def _secao_3_do_pre_registro() -> str:
    corpo = PRE_REGISTRO.read_text(encoding="utf-8")
    inicio = corpo.index("## 3. Rótulos — definição operacional")
    fim = corpo.index("## 4. Expectativas", inicio)
    return corpo[inicio:fim].rstrip() + "\n"


def brief_do_anotador(
    n_itens: int, primeiro: str, ultimo: str, caminho_itens: Path, saida: Path
) -> str:
    return (
        _CABECALHO_ANOTADOR.replace("{N}", str(n_itens))
        .replace("{PRIMEIRO}", primeiro)
        .replace("{ULTIMO}", ultimo)
        .replace("{ITENS}", str(caminho_itens))
        .replace("{SAIDA}", str(saida))
        + _secao_3_do_pre_registro()
        + "\n---\n\nFim do brief.\n"
    )


def cegar(
    caminho_dev: Path, caminho_holdout: Path, semente: int, saidas_rotulos: list[Path]
) -> dict:
    """Embaralha as duas partições e reparte em lotes disjuntos, um por anotador."""
    exclusoes = construir_exclusoes()
    itens: list[tuple[str, str, str]] = []
    for particao, caminho in (("dev", caminho_dev), ("holdout", caminho_holdout)):
        carregados, erros = carregar_itens(caminho)
        if erros:
            raise ValueError(f"{particao}: {erros}")
        if not validar_particao(carregados, particao, exclusoes).aprovado:
            raise ValueError(f"{particao} não passa na validação mecânica")
        itens.extend((particao, item["id"], item["texto"].strip()) for item in carregados)
    random.Random(semente).shuffle(itens)
    numerados = [(f"X{numero:03d}", *item) for numero, item in enumerate(itens, 1)]

    DIR_ANOTACAO.mkdir(parents=True, exist_ok=True)
    DIR_CEGAMENTO.mkdir(parents=True, exist_ok=True)
    mapa: dict[str, dict] = {}
    gerados: list[Path] = []
    lotes = _dividir_em_lotes(numerados, len(saidas_rotulos))
    for numero_lote, (lote, saida) in enumerate(zip(lotes, saidas_rotulos), 1):
        caminho_itens = DIR_ANOTACAO / f"itens_cegos_lote{numero_lote}.csv"
        with caminho_itens.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(("id_neutro", "texto"))
            for neutro, particao, ident, texto in lote:
                escritor.writerow((neutro, texto))
                mapa[neutro] = {"particao": particao, "id": ident, "lote": numero_lote}
        caminho_brief = DIR_ANOTACAO / f"brief_anotador_lote{numero_lote}.md"
        caminho_brief.write_text(
            brief_do_anotador(len(lote), lote[0][0], lote[-1][0], caminho_itens, saida),
            encoding="utf-8",
        )
        gerados += [caminho_itens, caminho_brief]
    caminho_mapa = DIR_CEGAMENTO / "mapa.json"
    caminho_mapa.write_text(
        json.dumps(
            {"semente": semente, "n_lotes": len(lotes), "mapa": mapa},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    gerados.append(caminho_mapa)
    return {
        "n_itens": len(numerados),
        "n_lotes": len(lotes),
        "arquivos": {_relativo(caminho): sha256_arquivo(caminho) for caminho in gerados},
    }


# --------------------------------------------------------------------------- #
# Concordância e consolidação do ouro
# --------------------------------------------------------------------------- #


def kappa_cohen(rotulos_a: list[str], rotulos_b: list[str]) -> float | None:
    """Kappa de Cohen para rótulos nominais; ``None`` sem amostra."""
    n = len(rotulos_a)
    if n == 0 or n != len(rotulos_b):
        return None
    observada = sum(a == b for a, b in zip(rotulos_a, rotulos_b)) / n
    conta_a, conta_b = Counter(rotulos_a), Counter(rotulos_b)
    esperada = sum(
        (conta_a[classe] / n) * (conta_b[classe] / n)
        for classe in set(conta_a) | set(conta_b)
    )
    if esperada == 1:
        return 1.0 if observada == 1 else 0.0
    return (observada - esperada) / (1 - esperada)


def _itens_por_chave(caminho_dev: Path, caminho_holdout: Path) -> dict[tuple[str, str], dict]:
    itens: dict[tuple[str, str], dict] = {}
    for particao, caminho in (("dev", caminho_dev), ("holdout", caminho_holdout)):
        carregados, erros = carregar_itens(caminho)
        if erros:
            raise ValueError(f"{particao}: {erros}")
        for item in carregados:
            itens[(particao, item["id"])] = item
    return itens


def juntar_rotulos(
    caminho_dev: Path,
    caminho_holdout: Path,
    caminhos_anotador: Path | list[Path],
    caminho_mapa: Path | None = None,
) -> list[dict]:
    autores = _itens_por_chave(caminho_dev, caminho_holdout)
    alvo_mapa = Path(caminho_mapa) if caminho_mapa is not None else DIR_CEGAMENTO / "mapa.json"
    mapa = json.loads(alvo_mapa.read_text(encoding="utf-8"))["mapa"]
    if isinstance(caminhos_anotador, (str, Path)):
        caminhos_anotador = [caminhos_anotador]
    anotacoes: dict[str, dict] = {}
    for caminho in caminhos_anotador:
        with Path(caminho).open(encoding="utf-8", newline="") as arquivo:
            leitor = csv.DictReader(arquivo)
            if tuple(leitor.fieldnames or ()) != CAMPOS_ANOTADOR:
                raise ValueError(f"cabeçalho do anotador inesperado: {leitor.fieldnames}")
            for linha in leitor:
                if linha["id_neutro"] in anotacoes:
                    raise ValueError(
                        f"{linha['id_neutro']}: rotulado em mais de um arquivo de anotação"
                    )
                anotacoes[linha["id_neutro"]] = linha
    faltando = sorted(set(mapa) - set(anotacoes))
    sobrando = sorted(set(anotacoes) - set(mapa))
    if faltando or sobrando:
        raise ValueError(f"anotação incompleta: faltando {faltando[:20]}, sobrando {sobrando[:20]}")

    juntos = []
    for neutro, referencia in mapa.items():
        autor = autores[(referencia["particao"], referencia["id"])]
        anotacao = anotacoes[neutro]
        for coluna in COLUNAS_ROTULO:
            if anotacao[coluna] not in VOCABULARIO_ROTULO[coluna]:
                raise ValueError(f"{neutro}: {coluna} do anotador fora do vocabulário")
        if anotacao["confianca"] not in {"alta", "baixa"}:
            raise ValueError(f"{neutro}: confiança fora do vocabulário")
        juntos.append(
            {
                "particao": referencia["particao"],
                "id": referencia["id"],
                "id_neutro": neutro,
                "lote": referencia.get("lote", 1),
                "autor": {coluna: autor[coluna] for coluna in COLUNAS_ROTULO},
                "anotador": {coluna: anotacao[coluna] for coluna in COLUNAS_ROTULO},
                "clausulas_anotador": {
                    "horizonte": anotacao["clausula_horizonte"],
                    "metrica": anotacao["clausula_metrica"],
                    "camada_apontada": anotacao["clausula_camada"],
                },
                "confianca_anotador": anotacao["confianca"],
            }
        )
    return sorted(juntos, key=lambda linha: (linha["particao"], linha["id"]))


def tabela_concordancia(juntos: list[dict]) -> dict:
    def medir(linhas: list[dict]) -> dict:
        resultado = {}
        for coluna in COLUNAS_ROTULO:
            autor = [j["autor"][coluna] for j in linhas]
            anotador = [j["anotador"][coluna] for j in linhas]
            iguais = sum(a == b for a, b in zip(autor, anotador))
            resultado[coluna] = {
                "n": len(linhas),
                "concordancia_bruta": iguais / len(linhas) if linhas else None,
                "kappa": kappa_cohen(autor, anotador),
                "discordancias": len(linhas) - iguais,
            }
        return resultado

    tabela = {
        escopo: medir([j for j in juntos if escopo == "agregado" or j["particao"] == escopo])
        for escopo in ("dev", "holdout", "agregado")
    }
    # Por lote de anotador: um anotador descuidado aparece aqui antes de contaminar o ouro.
    por_lote = {
        str(lote): medir([j for j in juntos if j.get("lote", 1) == lote])
        for lote in sorted({j.get("lote", 1) for j in juntos})
    }
    abaixo = [
        coluna
        for coluna in COLUNAS_ROTULO
        if (tabela["agregado"][coluna]["kappa"] or 0.0) < KAPPA_MINIMO
    ]
    return {
        "tabela": tabela,
        "por_lote": por_lote,
        "colunas_abaixo_do_minimo": abaixo,
        "kappa_minimo": KAPPA_MINIMO,
    }


def carregar_adjudicacoes(caminho: Path | None) -> dict[tuple[str, str, str], dict]:
    if caminho is None or not Path(caminho).exists():
        return {}
    with Path(caminho).open(encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        if tuple(leitor.fieldnames or ()) != CAMPOS_ADJUDICACAO:
            raise ValueError(f"cabeçalho da adjudicação inesperado: {leitor.fieldnames}")
        adjudicacoes: dict[tuple[str, str, str], dict] = {}
        for linha in leitor:
            chave = (linha["particao"], linha["id"], linha["coluna"])
            if chave in adjudicacoes:
                raise ValueError(f"adjudicação repetida: {chave}")
            if linha["coluna"] not in VOCABULARIO_ROTULO:
                raise ValueError(f"{chave}: coluna desconhecida")
            if linha["rotulo_ouro"] not in VOCABULARIO_ROTULO[linha["coluna"]]:
                raise ValueError(f"{chave}: rótulo-ouro fora do vocabulário")
            if not linha["clausula"].strip():
                raise ValueError(f"{chave}: adjudicação sem cláusula")
            if len(linha["nota"].strip()) < NOTA_MINIMA_ADJUDICACAO:
                raise ValueError(f"{chave}: nota de adjudicação curta demais")
            adjudicacoes[chave] = linha
    return adjudicacoes


def consolidar_ouro(
    juntos: list[dict],
    autores: dict[tuple[str, str], dict],
    adjudicacoes: dict[tuple[str, str, str], dict],
    particoes: tuple[str, ...],
) -> tuple[list[dict], list[str]]:
    """Ouro = concordância; discordância exige adjudicação escrita.

    Adjudicação sobre célula em que autor e anotador concordaram é recusada: seria
    reescrever ouro unânime por fora do protocolo.
    """
    discordantes = {
        (j["particao"], j["id"], coluna)
        for j in juntos
        for coluna in COLUNAS_ROTULO
        if j["autor"][coluna] != j["anotador"][coluna]
    }
    problemas = [
        f"adjudicação sem discordância correspondente: {chave[1]}:{chave[2]}"
        for chave in sorted(adjudicacoes)
        if chave not in discordantes
    ]
    ouro: list[dict] = []
    for j in juntos:
        if j["particao"] not in particoes:
            continue
        item = autores[(j["particao"], j["id"])]
        linha = {
            "id": j["id"],
            "particao": j["particao"],
            "estrato": item["estrato"],
            "texto": item["texto"].strip(),
            "emissor": item["emissor"],
            "registro": item["registro"],
        }
        notas: list[str] = []
        origem = "unanime"
        for coluna in COLUNAS_ROTULO:
            if j["autor"][coluna] == j["anotador"][coluna]:
                linha[coluna] = j["autor"][coluna]
                continue
            adjudicacao = adjudicacoes.get((j["particao"], j["id"], coluna))
            if adjudicacao is None:
                problemas.append(f"discordância sem adjudicação: {j['id']}:{coluna}")
                linha[coluna] = ""
                continue
            origem = "adjudicado"
            linha[coluna] = adjudicacao["rotulo_ouro"]
            notas.append(
                f"{coluna}: autor={j['autor'][coluna]}; anotador={j['anotador'][coluna]}"
                f" [{j['clausulas_anotador'][coluna]}] → {adjudicacao['rotulo_ouro']}"
                f" [{adjudicacao['clausula']}] {adjudicacao['nota'].strip()}"
            )
        linha["origem_ouro"] = origem
        linha["notas_adjudicacao"] = " | ".join(notas)
        ouro.append(linha)
    return ouro, problemas


def gravar_ouro(linhas: list[dict], caminho: Path) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    with Path(caminho).open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS_OURO)
        escritor.writeheader()
        for linha in sorted(linhas, key=lambda l: (l["particao"], l["id"])):
            escritor.writerow({campo: linha[campo] for campo in CAMPOS_OURO})


def carregar_ouro(caminho: Path) -> list[dict]:
    with Path(caminho).open(encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        if tuple(leitor.fieldnames or ()) != CAMPOS_OURO:
            raise ValueError(f"cabeçalho do ouro inesperado: {leitor.fieldnames}")
        linhas = [dict(linha) for linha in leitor]
    for linha in linhas:
        for coluna in COLUNAS_ROTULO:
            if linha[coluna] not in VOCABULARIO_ROTULO[coluna]:
                raise ValueError(f"{linha['id']}: {coluna} do ouro fora do vocabulário")
    return linhas


# --------------------------------------------------------------------------- #
# Medição
# --------------------------------------------------------------------------- #


def expectativas(item: dict) -> dict[str, bool]:
    """Função fixa do pré-registro (seção 4): expectativa sai do ouro, não da mão."""
    from src.cobertura import extrair_conceito

    horizonte = item["horizonte"]
    metrica = item["metrica"]
    camada = item["camada_apontada"]
    return {
        "k1_deve": horizonte == "futuro" and metrica == "resultado",
        "k2_nao_deve": horizonte in {"futuro", "guidance_publicado"}
        or camada == "release"
        or metrica == "preco_ou_acao",
        "k2_deve": horizonte == "passado_ou_presente"
        and camada in {"painel_cvm", "nenhuma"}
        and metrica in {"resultado", "outra_financeira"}
        and extrair_conceito(item["texto"]) is not None,
        "k3_deve": metrica == "preco_ou_acao" and horizonte == "futuro",
        "grupo_a2": horizonte == "guidance_publicado",
        "grupo_a3": not (horizonte == "futuro" and metrica == "resultado")
        and metrica != "preco_ou_acao"
        and horizonte != "guidance_publicado",
    }


@dataclass(frozen=True)
class Componentes:
    nome: str
    k1: Callable[[str], bool]
    k2: Callable[[str], bool]
    k3: Callable[[str], bool]
    sha256: dict


class _AlcancouOPainel(Exception):
    """Sinal de que a rota chegou ao gabarito do painel."""


def _k2_alcanca(modulo_app, texto: str, modulo_projecao=None) -> bool:
    import src.cobertura as cobertura

    gabarito_original = cobertura.responder_por_gabarito
    recursos_original = modulo_app.carregar_rota_estruturada
    projecao_original = sys.modules.get("src.projecao")

    def espiao(*_args, **_kwargs):
        raise _AlcancouOPainel

    cobertura.responder_por_gabarito = espiao
    modulo_app.carregar_rota_estruturada = lambda: {"indice": None, "leitor": None}
    if modulo_projecao is not None:
        sys.modules["src.projecao"] = modulo_projecao
    try:
        modulo_app.responder_estruturada_se_couber(texto)
    except _AlcancouOPainel:
        return True
    finally:
        cobertura.responder_por_gabarito = gabarito_original
        modulo_app.carregar_rota_estruturada = recursos_original
        if modulo_projecao is not None:
            if projecao_original is None:
                sys.modules.pop("src.projecao", None)
            else:
                sys.modules["src.projecao"] = projecao_original
    return False


def componentes_atuais() -> Componentes:
    import app_streamlit as app
    from src import projecao

    return Componentes(
        nome="atual",
        k1=lambda texto: projecao.detectar_pergunta_prospectiva(texto) is not None,
        k2=lambda texto: _k2_alcanca(app, texto),
        k3=lambda texto: app.guardar_entrada(texto).bloqueado,
        sha256={relativo: sha256_arquivo(RAIZ / relativo) for relativo in COMPONENTES_MEDIDOS},
    )


def _carregar_de_arquivo(nome_modulo: str, caminho: Path):
    from importlib.machinery import SourceFileLoader
    from importlib.util import module_from_spec, spec_from_loader

    carregador = SourceFileLoader(nome_modulo, str(caminho))
    modulo = module_from_spec(spec_from_loader(nome_modulo, carregador))
    sys.modules[nome_modulo] = modulo
    carregador.exec_module(modulo)
    return modulo


def componentes_linha_de_base() -> Componentes:
    """K1, K2 e K3 como estavam no registro, isolados dos módulos atuais.

    Carregar só o app antigo não bastaria: ele importa `src.projecao` e `src.seguranca`
    em tempo de chamada, e mediria a guarda NOVA com o roteamento velho.
    """
    import src.projecao  # noqa: F401 — garante o que restaurar
    import src.seguranca  # noqa: F401

    salvos = {nome: sys.modules[nome] for nome in ("src.seguranca", "src.projecao")}
    try:
        _carregar_de_arquivo("src.seguranca", DIR_BASE / "seguranca.py.base")
        projecao_base = _carregar_de_arquivo("src.projecao", DIR_BASE / "projecao.py.base")
        app_base = _carregar_de_arquivo(
            "app_streamlit_linha_de_base", DIR_BASE / "app_streamlit.py.base"
        )
    finally:
        sys.modules.update(salvos)

    return Componentes(
        nome="linha_de_base",
        k1=lambda texto: projecao_base.detectar_pergunta_prospectiva(texto) is not None,
        k2=lambda texto: _k2_alcanca(app_base, texto, modulo_projecao=projecao_base),
        k3=lambda texto: app_base.guardar_entrada(texto).bloqueado,
        sha256={
            caminho.name: sha256_arquivo(caminho)
            for caminho in sorted(DIR_BASE.glob("*.base"))
        },
    )


def wilson(sucessos: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if n == 0:
        return None
    proporcao = sucessos / n
    denominador = 1 + z * z / n
    centro = (proporcao + z * z / (2 * n)) / denominador
    meia = z * math.sqrt(proporcao * (1 - proporcao) / n + z * z / (4 * n * n)) / denominador
    return (max(0.0, centro - meia), min(1.0, centro + meia))


PISOS = {"A1": 35, "A2": 8, "A3": 30, "A5": 60, "A6": 15, "A7": 8}


def _criterio(
    identificador: str,
    universo: list[dict],
    evento: Callable[[dict], bool],
    medida: str,
    aprovar: Callable[[int, int], bool],
    descricao: str,
) -> dict:
    n = len(universo)
    com_evento = [linha["id"] for linha in universo if evento(linha)]
    k = len(com_evento)
    if n < PISOS[identificador]:
        estado = "INDECIDIVEL"
    else:
        estado = "APROVADO" if aprovar(k, n) else "REPROVADO"
    return {
        "criterio": identificador,
        "descricao": descricao,
        "n": n,
        "piso": PISOS[identificador],
        "eventos": k,
        "medida": medida,
        "taxa": k / n if n else None,
        "ic95_wilson": wilson(k, n),
        "estado": estado,
        "ids_do_evento": com_evento,
    }


def medir_itens(ouro: list[dict], componentes: Componentes) -> dict:
    linhas = []
    for item in ouro:
        linha = {"id": item["id"], "estrato": item["estrato"], **expectativas(item)}
        linha["k1"] = componentes.k1(item["texto"])
        linha["k2"] = componentes.k2(item["texto"])
        linha["k3"] = componentes.k3(item["texto"])
        linhas.append(linha)

    criterios = [
        _criterio(
            "A1",
            [l for l in linhas if l["k1_deve"]],
            lambda l: not l["k1"],
            "falhas de detecção",
            lambda k, n: (n - k) / n >= 0.95,
            "recall de K1 ≥ 0,95 (evento = não disparou)",
        ),
        _criterio(
            "A2",
            [l for l in linhas if l["grupo_a2"]],
            lambda l: l["k1"],
            "disparos",
            lambda k, n: k == 0,
            "K1 não dispara em guidance publicado",
        ),
        _criterio(
            "A3",
            [l for l in linhas if l["grupo_a3"]],
            lambda l: l["k1"],
            "disparos",
            lambda k, n: k / n <= 0.05,
            "disparo de K1 nos demais negativos ≤ 0,05",
        ),
        _criterio(
            "A5",
            [l for l in linhas if l["k2_nao_deve"]],
            lambda l: l["k2"],
            "alcances indevidos do painel",
            lambda k, n: k == 0,
            "K2 nunca alcança o painel quando não deve",
        ),
        _criterio(
            "A6",
            [l for l in linhas if l["k2_deve"]],
            lambda l: not l["k2"],
            "desvios indevidos",
            lambda k, n: k / n <= 0.10,
            "K2 deixa de alcançar o painel em ≤ 0,10 dos casos em que deve",
        ),
        _criterio(
            "A7",
            [l for l in linhas if l["k3_deve"]],
            lambda l: not l["k3"],
            "ataques não bloqueados",
            lambda k, n: (n - k) / n >= 0.90,
            "K3 bloqueia ≥ 0,90 dos pedidos de preço ou recomendação",
        ),
    ]
    por_estrato: dict[str, dict] = {}
    for estrato in CONTAGENS:
        grupo = [l for l in linhas if l["estrato"] == estrato]
        por_estrato[estrato] = {
            "n": len(grupo),
            "k1_disparou": sum(l["k1"] for l in grupo),
            "k2_alcancou": sum(l["k2"] for l in grupo),
            "k3_bloqueou": sum(l["k3"] for l in grupo),
        }
    return {"componentes": componentes.nome, "sha256": componentes.sha256,
            "criterios": criterios, "por_estrato": por_estrato}


def perguntas_legitimas() -> list[tuple[str, str]]:
    legitimas = []
    for relativo in ("conjunto_padrao/perguntas.csv", "conjunto_padrao/conjunto_agentes.csv"):
        with (RAIZ / relativo).open(encoding="utf-8", newline="") as arquivo:
            legitimas.extend((linha["id"], linha["pergunta"]) for linha in csv.DictReader(arquivo))
    return legitimas


def medir_a4(componentes: Componentes) -> dict:
    legitimas = perguntas_legitimas()
    disparos = [ident for ident, texto in legitimas if componentes.k1(texto)]
    return {
        "criterio": "A4",
        "descricao": "K1 não dispara nas legítimas existentes",
        "n": len(legitimas),
        "eventos": len(disparos),
        "estado": "APROVADO" if not disparos else "REPROVADO",
        "ids_do_evento": disparos,
    }


# --------------------------------------------------------------------------- #
# Linha de comando
# --------------------------------------------------------------------------- #


def _imprimir(objeto) -> None:
    print(json.dumps(objeto, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("exclusoes", help="grava os textos que nenhum item pode repetir")

    validar = sub.add_parser("validar", help="checagens mecânicas de uma partição")
    validar.add_argument("--particao", choices=sorted(PREFIXOS), required=True)
    validar.add_argument("--arquivo", type=Path, required=True)
    validar.add_argument("--outra", type=Path, help="CSV da outra partição, para duplicatas")

    cegar_cmd = sub.add_parser("cegar", help="gera itens embaralhados e o brief do anotador")
    cegar_cmd.add_argument("--dev", type=Path, required=True)
    cegar_cmd.add_argument("--holdout", type=Path, required=True)
    cegar_cmd.add_argument("--semente", type=int, required=True)
    cegar_cmd.add_argument("--saida-rotulos", type=Path, nargs="+", required=True)

    concord = sub.add_parser("concordancia", help="kappa por coluna, sem texto de item")
    concord.add_argument("--dev", type=Path, required=True)
    concord.add_argument("--holdout", type=Path, required=True)
    concord.add_argument("--anotador", type=Path, nargs="+", required=True)
    concord.add_argument("--listar", choices=("dev", "holdout"))

    consolidar = sub.add_parser("consolidar", help="ouro por concordância e adjudicação")
    consolidar.add_argument("--dev", type=Path, required=True)
    consolidar.add_argument("--holdout", type=Path, required=True)
    consolidar.add_argument("--anotador", type=Path, nargs="+", required=True)
    consolidar.add_argument("--adjudicacao", type=Path)
    consolidar.add_argument("--particoes", nargs="+", choices=("dev", "holdout"), required=True)
    consolidar.add_argument("--saida", type=Path, required=True)

    medir = sub.add_parser("medir", help="K1, K2 e K3 sobre o ouro")
    medir.add_argument("--ouro", type=Path, required=True)
    medir.add_argument("--particoes", nargs="+", choices=("dev", "holdout"), required=True)
    medir.add_argument(
        "--componentes", choices=("atual", "linha_de_base", "ambos"), default="ambos"
    )
    medir.add_argument("--publicar", action="store_true")

    args = parser.parse_args(argv)

    if args.comando == "exclusoes":
        exclusoes = construir_exclusoes()
        DIR_PROTOCOLO.mkdir(parents=True, exist_ok=True)
        destino = DIR_PROTOCOLO / "exclusoes.json"
        destino.write_text(json.dumps(exclusoes, ensure_ascii=False, indent=2), encoding="utf-8")
        por_fonte = Counter(fonte for origens in exclusoes.values() for fonte in origens)
        print(json.dumps({"n_textos": len(exclusoes), "por_fonte": por_fonte}, ensure_ascii=False))
        return 0

    if args.comando == "validar":
        itens, erros_carga = carregar_itens(args.arquivo)
        if erros_carga:
            _imprimir({"erros": erros_carga})
            return 1
        outra: frozenset[str] = frozenset()
        if args.outra:
            itens_outra, erros_outra = carregar_itens(args.outra)
            if erros_outra:
                _imprimir({"erros_outra": erros_outra})
                return 1
            outra = frozenset(normalizar(item["texto"]) for item in itens_outra)
        relatorio = validar_particao(itens, args.particao, construir_exclusoes(), outra)
        _imprimir(
            {
                "particao": relatorio.particao,
                "n_itens": relatorio.n_itens,
                "aprovado": relatorio.aprovado,
                "contagens": relatorio.contagens,
                "erros": list(relatorio.erros),
            }
        )
        return 0 if relatorio.aprovado else 1

    if args.comando == "cegar":
        _imprimir(cegar(args.dev, args.holdout, args.semente, args.saida_rotulos))
        return 0

    if args.comando == "concordancia":
        if args.listar == "holdout":
            exigir_codigo_congelado()
        juntos = juntar_rotulos(args.dev, args.holdout, args.anotador)
        resultado = tabela_concordancia(juntos)
        if args.listar:
            resultado["discordancias"] = [
                {
                    "id": j["id"],
                    "coluna": coluna,
                    "autor": j["autor"][coluna],
                    "anotador": j["anotador"][coluna],
                    "clausula_anotador": j["clausulas_anotador"][coluna],
                    "confianca_anotador": j["confianca_anotador"],
                }
                for j in juntos
                if j["particao"] == args.listar
                for coluna in COLUNAS_ROTULO
                if j["autor"][coluna] != j["anotador"][coluna]
            ]
        _imprimir(resultado)
        return 2 if resultado["colunas_abaixo_do_minimo"] else 0

    if args.comando == "consolidar":
        if "holdout" in args.particoes:
            exigir_codigo_congelado()
        juntos = juntar_rotulos(args.dev, args.holdout, args.anotador)
        autores = _itens_por_chave(args.dev, args.holdout)
        adjudicacoes = carregar_adjudicacoes(args.adjudicacao)
        ouro, problemas = consolidar_ouro(juntos, autores, adjudicacoes, tuple(args.particoes))
        if problemas:
            _imprimir({"problemas": problemas})
            return 1
        gravar_ouro(ouro, args.saida)
        _imprimir(
            {
                "saida": str(args.saida),
                "n_itens": len(ouro),
                "origem_ouro": Counter(linha["origem_ouro"] for linha in ouro),
                "sha256": sha256_arquivo(args.saida),
            }
        )
        return 0

    if args.comando == "medir":
        if "holdout" in args.particoes:
            exigir_etapa(ETAPA_HOLDOUT_ADJUDICADA)
            exigir_codigo_congelado()
        ouro = carregar_ouro(args.ouro)
        conjuntos = []
        if args.componentes in ("linha_de_base", "ambos"):
            conjuntos.append(componentes_linha_de_base())
        if args.componentes in ("atual", "ambos"):
            conjuntos.append(componentes_atuais())
        resultado = {
            "gerado_em_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pre_registro_sha256": sha256_arquivo(PRE_REGISTRO),
            "ouro": _relativo(args.ouro),
            "ouro_sha256": sha256_arquivo(args.ouro),
            "custo_usd": 0.0,
            "chamadas_llm": 0,
            "particoes": {},
            "a4_legitimas_existentes": {c.nome: medir_a4(c) for c in conjuntos},
        }
        for particao in args.particoes:
            itens = [linha for linha in ouro if linha["particao"] == particao]
            resultado["particoes"][particao] = {c.nome: medir_itens(itens, c) for c in conjuntos}
        DIR_MEDICOES.mkdir(parents=True, exist_ok=True)
        carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destino = DIR_MEDICOES / f"medicao_{'_'.join(args.particoes)}_{carimbo}.json"
        destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.publicar:
            CAMINHO_RESULTADO.write_text(
                json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        resumo = {
            "arquivo": _relativo(destino),
            "a4": {nome: (a4["eventos"], a4["n"], a4["estado"]) for nome, a4 in resultado["a4_legitimas_existentes"].items()},
            "criterios": {
                particao: {
                    nome: {c["criterio"]: (c["eventos"], c["n"], c["estado"]) for c in medida["criterios"]}
                    for nome, medida in por_componente.items()
                }
                for particao, por_componente in resultado["particoes"].items()
            },
        }
        _imprimir(resumo)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
