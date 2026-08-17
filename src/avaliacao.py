"""Avaliação auditável das estratégias E0–E3 — seções 5.8–5.10.

Recall@5, exatidão e recusa são resultados medidos, não testes de software.
Cada resultado fica ligado por fingerprint ao gabarito, corpus, índice, modelo,
prompt e parâmetros efetivos da execução.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import time
from collections.abc import Collection
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from openai import APIConnectionError, APITimeoutError, APIStatusError, RateLimitError

from src.bloqueio import bloqueio_exclusivo
from src.config import (
    CAMINHO_METADADOS_CORPUS,
    DIR_INDICE_VETORIAL,
    DIR_LOGS_EXECUCOES,
    DIR_RESULTADOS_AVALIACAO,
    Config,
)
from src.geracao import (
    PROMPT_SISTEMA,
    PROMPT_SISTEMA_CLOSED_BOOK,
    VERSAO_PROMPT,
    Citacao,
    ProvedorLLM,
    RespostaGerada,
    gerar_resposta,
    montar_prompt_usuario,
    redigir_dados_pessoais,
    validar_contrato_resposta_gerada,
)
from src.ingestao import Chunk
from src.normalizacao import (
    APELIDOS_BANCOS,
    NumeroPtBR,
    extrair_numeros_ptbr,
    extrair_numeros_ptbr_tipados,
    extrair_bancos_citados,
    extrair_trimestres_citados,
    normalizar_numero_ptbr,
    remover_acentos,
    valores_equivalentes,
)
from src.recuperacao import (
    Estrategia,
    Recuperador,
    ResultadoRecuperacao,
    extrair_filtro_metadados,
)

COLUNAS_CONJUNTO_PADRAO = (
    "id",
    "conjunto",
    "categoria",
    "subtipo_adversarial",
    "pergunta",
    "resposta_esperada",
    "classe_verificacao",
    "unidade",
    "origem",
    "locais_aceitos",
    "pontos_chave",
    "comportamento_aceito",
)

CATEGORIAS = ("factual", "comparativa", "qualitativa", "adversarial")
RECALL_K = 5
# v5: a troca de FAISS por Chroma mudou o armazenamento vetorial, então o
# fingerprint tem de mudar junto — reaproveitar checkpoint construído sobre o
# índice antigo seria comparar execuções que não são comparáveis.
VERSAO_AVALIACAO = "v5"
# O artefato do Chroma (`chroma.sqlite3` e os segmentos HNSW) é reescrito a cada
# abertura da coleção, então hashear o arquivo daria digest instável — passaria
# uma vez e falharia na carga seguinte. A cobertura do índice vetorial vem de
# `metadados_materiais`, que carrega `hash_indice_vetorial`, digest sobre o
# conteúdo lógico da coleção (ids, documentos, metadados e vetores).
_ARQUIVOS_IDENTIDADE_INDICE = (
    "metadados_construcao.json",
    "chunks.json",
)
_STATUS_TRANSITORIOS = {408, 409, 425, 429, 500, 502, 503, 504}


class CustoExcedidoError(RuntimeError):
    """O custo observado atingiu o teto, ou a estimativa segura não cabe nele."""


class AvaliacaoIncompletaError(RuntimeError):
    """Uma ou mais perguntas terminaram com erro e a rodada não é publicável."""


@dataclass(frozen=True)
class PerguntaPadrao:
    id: str
    conjunto: str
    categoria: str
    subtipo_adversarial: str
    pergunta: str
    resposta_esperada: str
    classe_verificacao: str
    unidade: str
    origem: str
    locais_aceitos: str
    pontos_chave: str
    comportamento_aceito: str


@dataclass
class ResultadoItem:
    """Resultado de uma pergunta/estratégia, unidade do checkpoint."""

    pergunta_id: str
    estrategia: Estrategia
    resposta: RespostaGerada | None
    categoria: str = ""
    recuperados: list[ResultadoRecuperacao] = field(default_factory=list)
    recall_ok: bool | None = None
    exatidao_ok: bool | None = None
    recusa_correta: bool | None = None
    # ``custo_usd`` é o débito conservador usado no teto: custo observado da
    # tentativa bem-sucedida + estimativa máxima das tentativas que falharam.
    custo_usd: float | None = 0.0
    custo_observado_usd: float | None = 0.0
    custo_estimado_falhas_usd: float = 0.0
    n_chamadas: int = 0
    n_chamadas_sem_telemetria: int = 0
    latencia_s: float = 0.0
    latencia_a_quente: bool = True
    tokens_entrada: int = 0
    tokens_saida: int = 0
    modelo: str = ""
    erro: str | None = None
    run_id: str = ""
    fingerprint: str = ""
    call_ids: tuple[str, ...] = ()


def _validar_invariantes_resultado_item(item: ResultadoItem) -> None:
    """Rejeita registros capazes de corromper custo, retomada ou métricas."""
    if item.resposta is not None:
        validar_contrato_resposta_gerada(item.resposta)
    for campo in (
        "custo_estimado_falhas_usd",
        "latencia_s",
    ):
        valor = getattr(item, campo)
        if (
            not isinstance(valor, (int, float))
            or isinstance(valor, bool)
            or not math.isfinite(float(valor))
            or valor < 0
        ):
            raise ValueError(f"{campo} deve ser finito e >= 0.")
    for campo in ("custo_usd", "custo_observado_usd"):
        valor = getattr(item, campo)
        if valor is not None and (
            not isinstance(valor, (int, float))
            or isinstance(valor, bool)
            or not math.isfinite(float(valor))
            or valor < 0
        ):
            raise ValueError(f"{campo} deve ser nulo ou finito e >= 0.")
    for campo in (
        "n_chamadas",
        "n_chamadas_sem_telemetria",
        "tokens_entrada",
        "tokens_saida",
    ):
        valor = getattr(item, campo)
        if type(valor) is not int or valor < 0:
            raise ValueError(f"{campo} deve ser inteiro >= 0.")
    if item.n_chamadas != len(item.call_ids):
        raise ValueError("n_chamadas deve coincidir com a quantidade de call_ids.")
    if item.n_chamadas_sem_telemetria > item.n_chamadas:
        raise ValueError("Chamadas sem telemetria excedem chamadas iniciadas.")
    if len(set(item.call_ids)) != len(item.call_ids):
        raise ValueError("ResultadoItem contém call_id duplicado.")
    if any(not isinstance(call_id, str) or not call_id for call_id in item.call_ids):
        raise ValueError("call_ids devem ser strings não vazias.")
    if type(item.latencia_a_quente) is not bool:
        raise ValueError("latencia_a_quente deve ser booleano.")
    for campo in ("recall_ok", "exatidao_ok", "recusa_correta"):
        if getattr(item, campo) is not None and type(getattr(item, campo)) is not bool:
            raise ValueError(f"{campo} deve ser booleano ou nulo.")
    if item.erro is None and (
        item.resposta is None
        or item.n_chamadas < 1
        or item.custo_usd is None
        or item.custo_observado_usd is None
        or not isinstance(item.modelo, str)
        or not item.modelo.strip()
    ):
        raise ValueError(
            "Resultado bem-sucedido exige resposta, chamada, custo observado "
            "e modelo observado."
        )
    if item.custo_usd is not None:
        esperado = float(item.custo_estimado_falhas_usd) + float(
            item.custo_observado_usd or 0.0
        )
        if not math.isclose(float(item.custo_usd), esperado, abs_tol=1e-12):
            raise ValueError("custo_usd diverge de observado + falhas conservadoras.")


def _validar_modelos_sucesso(itens: list[ResultadoItem]) -> None:
    """Um fingerprint não pode consolidar duas versões observadas do modelo."""
    sucessos = [
        item for item in itens if item.erro is None and item.n_chamadas > 0
    ]
    if any(not isinstance(item.modelo, str) or not item.modelo.strip() for item in sucessos):
        raise ValueError("Resultado bem-sucedido não registra modelo observado.")
    modelos = {item.modelo for item in sucessos}
    if len(modelos) > 1:
        raise ValueError(
            "Fingerprint mistura modelos observados entre estratégias: "
            f"{sorted(modelos)}."
        )


@dataclass
class MetricasEstrategia:
    estrategia: Estrategia
    recall_at_5: float | None
    exatidao_numerica: float | None
    taxa_recusa_correta: float | None
    # Alias de compatibilidade: sempre representa o débito conservador.
    custo_medio_usd: float | None
    custo_conservador_medio_usd: float | None
    custo_observado_medio_usd: float | None
    latencia_media_s: float | None
    latencia_p95_s: float | None
    n_json_invalido: int
    # ``n_erros`` permanece como alias publicável de pendências atuais.
    n_erros: int = 0
    n_erros_pendentes: int = 0
    n_erros_historicos: int = 0
    n_itens: int = 0
    n_tentativas: int = 0
    n_tentativas_sem_telemetria: int = 0
    n_chamadas: int = 0
    n_chamadas_sem_telemetria: int = 0
    n_itens_latencia_a_quente: int = 0


def carregar_conjunto_padrao(config: Config) -> list[PerguntaPadrao]:
    """Lê o gabarito e rejeita linhas incompletas ou contratos ambíguos."""
    with open(config.conjunto_padrao_path, newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        if tuple(leitor.fieldnames or ()) != COLUNAS_CONJUNTO_PADRAO:
            raise ValueError(
                f"Esquema inesperado em {config.conjunto_padrao_path}: "
                f"{leitor.fieldnames!r}"
            )
        perguntas: list[PerguntaPadrao] = []
        for numero_linha, linha in enumerate(leitor, start=2):
            if None in linha or any(valor is None for valor in linha.values()):
                raise ValueError(
                    f"Linha {numero_linha} incompleta no conjunto-padrão."
                )
            limpa = {chave: valor.strip() for chave, valor in linha.items()}
            obrigatorios = (
                "id",
                "conjunto",
                "categoria",
                "pergunta",
                "resposta_esperada",
                "classe_verificacao",
                "unidade",
                "origem",
            )
            vazios = [campo for campo in obrigatorios if not limpa[campo]]
            if vazios:
                raise ValueError(
                    f"Linha {numero_linha} possui campos obrigatórios vazios: "
                    f"{vazios}."
                )
            if re.fullmatch(r"[A-Za-z0-9_-]+", limpa["id"]) is None:
                raise ValueError(f"ID inválido na linha {numero_linha}.")
            if limpa["conjunto"] not in {"dev", "teste"}:
                raise ValueError(
                    f"Conjunto inválido na linha {numero_linha}: "
                    f"{limpa['conjunto']!r}."
                )
            if limpa["categoria"] not in CATEGORIAS:
                raise ValueError(
                    f"Categoria inválida na linha {numero_linha}: "
                    f"{limpa['categoria']!r}."
                )
            locais = [
                local.strip()
                for local in limpa["locais_aceitos"].split(";")
                if local.strip()
            ]
            for local in locais:
                documento, separador, pagina = local.rpartition(":")
                if (
                    not separador
                    or not documento
                    or not pagina.isdigit()
                    or int(pagina) <= 0
                ):
                    raise ValueError(
                        f"Local aceito inválido na linha {numero_linha}: {local!r}."
                    )
            if limpa["categoria"] != "adversarial" and not locais:
                raise ValueError(
                    f"Linha {numero_linha} precisa de ao menos um local aceito."
                )
            if limpa["categoria"] == "qualitativa" and not limpa["pontos_chave"]:
                raise ValueError(
                    f"Linha {numero_linha} qualitativa não possui pontos_chave."
                )
            if limpa["categoria"] == "adversarial":
                if not limpa["subtipo_adversarial"]:
                    raise ValueError(
                        f"Linha {numero_linha} adversarial não possui subtipo."
                    )
                comportamentos = {
                    item.strip()
                    for item in limpa["comportamento_aceito"].split("|")
                    if item.strip()
                }
                permitidos = {"recusa", "correcao_fundamentada"}
                if not comportamentos or not comportamentos <= permitidos:
                    raise ValueError(
                        f"Comportamento adversarial inválido na linha "
                        f"{numero_linha}: {sorted(comportamentos)}."
                    )
            perguntas.append(PerguntaPadrao(**limpa))
    if not perguntas:
        raise ValueError("Conjunto-padrão vazio.")
    ids = [pergunta.id for pergunta in perguntas]
    duplicados = sorted({item for item in ids if ids.count(item) > 1})
    if duplicados:
        raise ValueError(f"IDs duplicados no conjunto-padrão: {duplicados}")
    textos = [pergunta.pergunta.casefold() for pergunta in perguntas]
    repetidos = sorted({texto for texto in textos if textos.count(texto) > 1})
    if repetidos:
        raise ValueError("Perguntas duplicadas no conjunto-padrão.")
    return perguntas


def _validar_conjunto_teste_final(perguntas: list[PerguntaPadrao]) -> None:
    """Impede publicar um benchmark parcial com aparência de resultado final."""
    contagens = {
        categoria: sum(p.categoria == categoria for p in perguntas)
        for categoria in CATEGORIAS
    }
    esperado = {
        "factual": 15,
        "comparativa": 10,
        "qualitativa": 10,
        "adversarial": 10,
    }
    if len(perguntas) != 45 or contagens != esperado:
        raise ValueError(
            "O conjunto teste final deve conter exatamente 45 perguntas "
            f"(15/10/10/10); encontrado total={len(perguntas)}, "
            f"categorias={contagens}."
        )
    adversariais_nubank = sum(
        p.categoria == "adversarial"
        and "NUBANK" in extrair_bancos_citados(p.pergunta)
        for p in perguntas
    )
    if adversariais_nubank < 4:
        raise ValueError(
            "O conjunto teste exige ao menos quatro adversariais sobre Nubank; "
            f"encontradas {adversariais_nubank}."
        )


def registrar_execucao(
    registro: dict, dir_logs: Path = DIR_LOGS_EXECUCOES, arquivo: str | None = None
) -> Path:
    """Anexa uma linha JSONL com timestamp UTC (RNF08)."""
    dir_logs.mkdir(parents=True, exist_ok=True)
    nome = arquivo or f"execucao_{datetime.now(timezone.utc):%Y%m%d}.jsonl"
    caminho = dir_logs / nome
    linha = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), **registro}
    with open(caminho, "a", encoding="utf-8") as destino:
        destino.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
        destino.flush()
        os.fsync(destino.fileno())
    return caminho


def avaliar_recall_at_k(
    pergunta: PerguntaPadrao, recuperados: list[ResultadoRecuperacao], k: int = RECALL_K
) -> bool:
    """Aplica a definição operacional factual/comparativa de Recall@k."""
    top = recuperados[:k]
    if pergunta.categoria == "comparativa":
        filtro = extrair_filtro_metadados(pergunta.pergunta)
        presentes = {
            (resultado.chunk.empresa, resultado.chunk.trimestre)
            for resultado in top
        }
        if filtro.empresas and filtro.trimestres:
            exigidos = {
                (empresa, trimestre)
                for empresa in filtro.empresas
                for trimestre in filtro.trimestres
            }
            return exigidos <= presentes
        if filtro.empresas:
            empresas_presentes = {empresa for empresa, _ in presentes}
            return set(filtro.empresas) <= empresas_presentes
        if filtro.trimestres:
            periodos_presentes = {trimestre for _, trimestre in presentes}
            return set(filtro.trimestres) <= periodos_presentes
        return False
    for local in pergunta.locais_aceitos.split(";"):
        local = local.strip()
        if not local or ":" not in local:
            continue
        documento, _, pagina_txt = local.rpartition(":")
        try:
            pagina = int(pagina_txt)
        except ValueError:
            continue
        for resultado in top:
            chunk = resultado.chunk
            if (
                chunk.documento == documento
                and chunk.pagina_inicio <= pagina <= chunk.pagina_fim
            ):
                return True
    return False


def avaliar_exatidao_numerica(
    pergunta: PerguntaPadrao, resposta: RespostaGerada, config: Config
) -> bool:
    """Compara o valor da cláusula que nomeia a métrica perguntada.

    Um número correto atribuído a ``carteira`` não pode validar uma pergunta
    sobre ``resultado recorrente``. A ausência do nome da métrica é tratada de
    forma conservadora como não verificável automaticamente.
    """
    if resposta.recusa or resposta.resposta is None or resposta.json_invalido:
        return False
    esperados = extrair_numeros_ptbr_tipados(pergunta.resposta_esperada)
    if not esperados:
        return False
    tokens_metrica = _tokens_metrica_pergunta(pergunta.pergunta)
    if not tokens_metrica:
        return False
    grupos_metrica = _grupos_metricos(tokens_metrica)
    modificadores = _modificadores_metricos(tokens_metrica)
    bancos_pergunta = set(extrair_bancos_citados(pergunta.pergunta))
    periodos_pergunta = set(extrair_trimestres_citados(pergunta.pergunta))
    limiar = 1 if len(tokens_metrica) == 1 else 2
    esperado = esperados[0]
    obtido: NumeroPtBR | None = None
    for clausula in re.split(r"[;\n]+|(?<=[.!?])\s+", resposta.resposta):
        bancos_clausula = set(extrair_bancos_citados(clausula))
        periodos_clausula = set(extrair_trimestres_citados(clausula))
        if (
            (bancos_pergunta and bancos_clausula and not bancos_clausula <= bancos_pergunta)
            or (
                periodos_pergunta
                and periodos_clausula
                and not periodos_clausula <= periodos_pergunta
            )
        ):
            continue
        tokens_clausula = _tokens_metrica_pergunta(clausula)
        if grupos_metrica:
            if not (grupos_metrica & _grupos_metricos(tokens_clausula)):
                continue
            if not modificadores <= _modificadores_metricos(tokens_clausula):
                continue
        elif len(tokens_clausula & tokens_metrica) < limiar:
            continue
        numeros = [
            numero
            for numero in extrair_numeros_ptbr_tipados(clausula)
            if _dimensoes_numericas_compativeis(esperado, numero)
        ]
        if not numeros:
            continue
        normalizada = remover_acentos(clausula).casefold()
        normalizada_sem_qualificador = re.sub(
            r"\bnao\s+(?:aos?\s+)?controladores?\b",
            "nao_controlador",
            normalizada,
        )
        if len(numeros) != 1 or re.search(
            r"\b(?:nao|nunca|nem|ao\s+contrario|diferente|em\s+vez|"
            r"entre|faixa|intervalo)\b",
            normalizada_sem_qualificador,
        ):
            return False
        obtido = numeros[0]
        break
    if obtido is None:
        return False
    return valores_equivalentes(
        esperado.valor,
        obtido.valor,
        tolerancia_pct=config.tolerancia_numerica_pct,
    ) and _dimensoes_numericas_compativeis(esperado, obtido)


_STOPWORDS_METRICA = {
    "a", "ao", "aos", "as", "com", "conforme", "da", "das", "de", "do",
    "dos", "e", "em", "entre", "foi", "na", "nas", "no", "nos", "o",
    "os", "para", "por", "qual", "quais", "quanto", "quantos", "que",
    "segundo", "sua", "seu", "um", "uma", "valor", "divulgacao", "release",
    "banco", "instituicao", "trimestre", "ano",
    "analise", "comparativo", "demonstracao", "divulgacao", "release",
    "reconciliacao",
}
_TOKENS_BANCOS = {
    token
    for apelidos in APELIDOS_BANCOS.values()
    for apelido in apelidos
    for token in re.findall(r"[a-z][a-z0-9_]*", remover_acentos(apelido).casefold())
}
_GRUPOS_METRICAS_AVALIACAO = {
    "lucro": {"lucro"},
    "resultado_pdd": {"resultado_pdd"},
    "resultado_financeiro": {"resultado_financeiro"},
    "resultado_seguros": {"resultado_seguros"},
    "rentabilidade": {"roae", "roe", "rspl", "rentabilidade"},
    "credito": {"carteira", "credito", "emprestimos"},
    "margem_financeira": {"margem_financeira"},
    "eficiencia": {"eficiencia"},
    "inadimplencia": {"inadimplencia", "npl"},
    "margem": {"margem", "spread", "nim"},
    "receita": {"receita", "faturamento"},
    "despesa": {"despesa", "custo"},
    "ativos": {"ativo", "ativos"},
    "aum": {"aum", "ativos_sob_gestao"},
    "aua": {"aua", "ativos_sob_administracao"},
    "aum_aua": {"aum_aua"},
    "custodia": {"custodia"},
}
_MODIFICADORES_METRICA_DISCRIMINANTES = {
    "acima": "acima", "agio": "agio", "ajustado": "ajustado",
    "ajustada": "ajustado", "ampliada": "expandida",
    "anualizado": "anualizado", "anualizada": "anualizado",
    "atribuivel": "atribuivel", "controlador": "controlador",
    "controladores": "controlador", "dias": "dias",
    "expandida": "expandida", "excluindo": "excluindo",
    "incluindo": "incluindo", "incluido": "incluindo",
    "incluida": "incluindo",
    "fiancas": "fiancas", "gerencial": "gerencial", "ifrs": "ifrs",
    "brgaap": "brgaap", "liquido": "liquido",
    "bruto": "bruto", "bruta": "bruto",
    "consolidado": "consolidado", "consolidada": "consolidado",
    "individual": "individual", "operacional": "operacional",
    "liquida": "liquido", "privados": "privados",
    "recorrente": "recorrente", "reportado": "reportado",
    "reportada": "reportado", "total": "total",
    "titulos": "titulos", "avais": "avais",
}


def _tokens_metrica_pergunta(texto: str) -> set[str]:
    normalizado = remover_acentos(texto).casefold()
    marcador = re.search(
        r"\b(?:qual(?:\s+(?:foi|foram|e|sao|era|eram))?|quant[oa]s?)\b",
        normalizado,
    )
    if marcador is not None:
        normalizado = normalizado[marcador.end():]
    tokens = re.findall(r"[a-z][a-z0-9_]*", normalizado)
    resultado = {
        token
        for token in tokens
        if token not in _STOPWORDS_METRICA
        and token not in _TOKENS_BANCOS
        and not any(caractere.isdigit() for caractere in token)
    }
    tem_combinado = bool(
        re.search(
            r"\bativos?\s+sob\s+gestao\s+e\s+administracao\b",
            normalizado,
        )
    )
    tem_gestao = tem_combinado or bool(
        re.search(r"\bativos?\s+sob\s+gestao\b|\ba[us]m\b", normalizado)
    )
    tem_administracao = tem_combinado or bool(
        re.search(r"\bativos?\s+sob\s+administracao\b|\baua\b", normalizado)
    )
    if tem_gestao and tem_administracao:
        resultado.add("aum_aua")
    elif tem_gestao:
        resultado.add("ativos_sob_gestao")
    elif tem_administracao:
        resultado.add("ativos_sob_administracao")
    if tem_gestao or tem_administracao:
        resultado.difference_update({"ativo", "ativos"})
    if "retorno" in resultado and re.search(
        r"\bsobre\s+(?:o\s+)?patrimonio\b", normalizado
    ):
        resultado.add("rentabilidade")
    return resultado


def _grupos_metricos(tokens: set[str]) -> set[str]:
    especiais: set[str] = set()
    if "resultado" in tokens and tokens & {"liquido", "recorrente"}:
        especiais.add("lucro")
    if "pdd" in tokens or tokens & {"provisao", "provisoes"}:
        especiais.add("resultado_pdd")
    if "resultado" in tokens and "financeiro" in tokens:
        especiais.add("resultado_financeiro")
    if "resultado" in tokens and tokens & {"seguro", "seguros", "seguridade"}:
        especiais.add("resultado_seguros")
    if "margem" in tokens and tokens & {"financeira", "financeiro"}:
        especiais.add("margem_financeira")
    if especiais:
        return especiais
    return {
        nome
        for nome, aliases in _GRUPOS_METRICAS_AVALIACAO.items()
        if tokens & aliases
    }


def _modificadores_metricos(tokens: set[str]) -> set[str]:
    modificadores = {
        _MODIFICADORES_METRICA_DISCRIMINANTES[token]
        for token in tokens
        if token in _MODIFICADORES_METRICA_DISCRIMINANTES
    }
    if "nao" in tokens and tokens & {"controlador", "controladores"}:
        modificadores.add("nao_controlador")
    return modificadores


def _dimensoes_numericas_compativeis(
    esperado: NumeroPtBR, obtido: NumeroPtBR
) -> bool:
    return esperado.dimensao == obtido.dimensao or {
        esperado.dimensao,
        obtido.dimensao,
    } <= {"monetario", "escala"}


def avaliar_recusa(pergunta: PerguntaPadrao, resposta: RespostaGerada) -> bool:
    """Avalia a política adversarial sem chamar mera citação de "correção".

    Uma correção fundamentada só é automaticamente aceita quando todos os
    valores financeiros do gabarito aparecem na resposta. Casos sem valor
    verificável exigem auditoria humana e não recebem sucesso automático.
    """
    aceitos = {
        comportamento.strip()
        for comportamento in pergunta.comportamento_aceito.split("|")
        if comportamento.strip()
    } or {"recusa"}
    if resposta.json_invalido:
        return False
    if resposta.recusa:
        return "recusa" in aceitos
    if (
        "correcao_fundamentada" not in aceitos
        or not resposta.resposta
        or not resposta.citacoes
    ):
        return False
    if pergunta.subtipo_adversarial == "premissa_falsa":
        # Escopo de negação e ironia não é verificável com segurança por regra
        # lexical. A correção continua aceitável no gabarito para auditoria
        # humana, mas nunca recebe sucesso automático; recusa explícita, sim.
        return False
    esperados = extrair_numeros_ptbr_tipados(pergunta.resposta_esperada)
    obtidos = extrair_numeros_ptbr_tipados(resposta.resposta)
    if not esperados or not obtidos:
        return False
    indice_obtido = 0
    for esperado in esperados:
        while indice_obtido < len(obtidos) and not (
            _dimensoes_numericas_compativeis(esperado, obtidos[indice_obtido])
            and valores_equivalentes(
                esperado.valor, obtidos[indice_obtido].valor
            )
        ):
            indice_obtido += 1
        if indice_obtido == len(obtidos):
            return False
        indice_obtido += 1
    return True


def _hash_arquivo(caminho: Path) -> str | None:
    if not caminho.is_file():
        return None
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _modelo_configurado(config: Config, provedor: ProvedorLLM) -> str:
    modelo = getattr(provedor, "_modelo", "")
    if modelo:
        return str(modelo)
    por_provedor = {
        "ollama": config.ollama_modelo_llm,
        "gemini": config.gemini_modelo_llm,
        "azure_openai": config.azure_openai_deployment_llm,
        "openai": config.openai_modelo,
        "deepseek": config.deepseek_modelo,
    }
    return por_provedor.get(provedor.nome, type(provedor).__qualname__)


def _hash_texto(valor: str) -> str:
    """Identifica endpoints sem publicar nomes de recursos nos logs."""
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def _identidade_config_provedor(config: Config, provedor: ProvedorLLM) -> dict:
    """Parâmetros não secretos que podem mudar saída, custo ou retomada."""
    comum = {
        "nome": provedor.nome,
        "modelo": _modelo_configurado(config, provedor),
    }
    if provedor.nome == "gemini":
        comum.update(
            {
                "endpoint_sha256": _hash_texto(config.gemini_base_url),
                "max_tokens": config.gemini_max_tokens,
                "reasoning_effort": config.gemini_reasoning_effort,
                "timeout_s": config.gemini_timeout_s,
                "preco_entrada_usd_milhao": (
                    config.gemini_preco_entrada_usd_milhao
                ),
                "preco_saida_usd_milhao": config.gemini_preco_saida_usd_milhao,
            }
        )
    elif provedor.nome == "ollama":
        resolver = getattr(provedor, "identidade_modelo", None)
        comum.update(
            {
                "endpoint_sha256": _hash_texto(config.ollama_base_url),
                "max_tokens": config.ollama_max_tokens,
                "timeout_s": config.ollama_timeout_s,
                "modelo_imutavel": (
                    resolver() if callable(resolver) else config.ollama_modelo_llm
                ),
            }
        )
    elif provedor.nome == "azure_openai":
        comum.update(
            {
                "endpoint_sha256": _hash_texto(config.azure_openai_endpoint),
                "api_version": config.azure_openai_api_version,
                "max_tokens": 512,
            }
        )
    elif provedor.nome in {"openai", "deepseek"}:
        comum["max_tokens"] = 512
    return comum


def _identidade_indice_material(dir_indice: Path) -> dict:
    dir_indice = Path(dir_indice)
    caminho_metadados = dir_indice / "metadados_construcao.json"
    metadados_materiais: dict | None = None
    if caminho_metadados.is_file():
        try:
            bruto = json.loads(caminho_metadados.read_text(encoding="utf-8"))
            if isinstance(bruto, dict):
                metadados_materiais = {
                    chave: valor
                    for chave, valor in bruto.items()
                    if chave != "data_construcao"
                }
        except (OSError, UnicodeError, json.JSONDecodeError):
            metadados_materiais = None
    return {
        "metadados_materiais": metadados_materiais,
        "arquivos": {
            nome: _hash_arquivo(dir_indice / nome) for nome in ("chunks.json",)
        },
    }


def _hashes_codigo_material() -> dict[str, str | None]:
    raiz = Path(__file__).parent.parent
    caminhos = {
        nome: Path(__file__).with_name(nome)
        for nome in (
            "auditoria.py",
            "avaliacao.py",
            "config.py",
            "geracao.py",
            "indexacao.py",
            "ingestao.py",
            "normalizacao.py",
            "ocr_cache.py",
            "ocr_corpus.py",
            "ocr_mistral.py",
            "ollama.py",
            "recuperacao.py",
        )
    }
    caminhos["app_streamlit.py"] = raiz / "app_streamlit.py"
    return {nome: _hash_arquivo(caminho) for nome, caminho in caminhos.items()}


def _config_provedor_sem_rede(config: Config, nome: str) -> dict:
    modelos = {
        "ollama": config.ollama_modelo_llm,
        "gemini": config.gemini_modelo_llm,
        "azure_openai": config.azure_openai_deployment_llm,
        "openai": config.openai_modelo,
        "deepseek": config.deepseek_modelo,
    }
    identidade = {"nome": nome, "modelo": modelos.get(nome, "")}
    if nome == "gemini":
        identidade.update(
            {
                "endpoint_sha256": _hash_texto(config.gemini_base_url),
                "max_tokens": config.gemini_max_tokens,
                "reasoning_effort": config.gemini_reasoning_effort,
                "timeout_s": config.gemini_timeout_s,
                "preco_entrada_usd_milhao": config.gemini_preco_entrada_usd_milhao,
                "preco_saida_usd_milhao": config.gemini_preco_saida_usd_milhao,
            }
        )
    elif nome == "ollama":
        identidade.update(
            {
                "endpoint_sha256": _hash_texto(config.ollama_base_url),
                "max_tokens": config.ollama_max_tokens,
                "timeout_s": config.ollama_timeout_s,
            }
        )
    elif nome == "azure_openai":
        identidade.update(
            {
                "endpoint_sha256": _hash_texto(config.azure_openai_endpoint),
                "api_version": config.azure_openai_api_version,
                "max_tokens": 512,
            }
        )
    elif nome in {"openai", "deepseek"}:
        identidade["max_tokens"] = 512
    return identidade


def validar_estado_material_atual(
    config: Config,
    perguntas: list[PerguntaPadrao],
    componentes: dict,
    *,
    dir_indice: Path = DIR_INDICE_VETORIAL,
    repeticao_estabilidade: int | None = None,
) -> None:
    """Falha se qualquer material local da rodada publicada mudou."""
    if not isinstance(componentes, dict):
        raise ValueError("Manifesto material do fingerprint é inválido.")
    raiz = Path(__file__).parent.parent
    esperados = {
        "versao_avaliacao": VERSAO_AVALIACAO,
        "versao_prompt": VERSAO_PROMPT,
        "sha256_prompt_rag": hashlib.sha256(PROMPT_SISTEMA.encode()).hexdigest(),
        "sha256_prompt_closed_book": hashlib.sha256(
            PROMPT_SISTEMA_CLOSED_BOOK.encode()
        ).hexdigest(),
        "temperatura": 0.0,
        "recall_k": RECALL_K,
        "tolerancia_numerica_pct": config.tolerancia_numerica_pct,
        "top_k_recuperacao": RECALL_K,
        "repeticao_estabilidade": repeticao_estabilidade,
        "estrategia_demo_e_auditoria": config.estrategia_padrao,
        "provedor_llm": config.llm_provider,
        "embedding_provider": config.embedding_provider,
        "embedding_modelo": (
            config.ollama_modelo_embedding
            if config.embedding_provider == "ollama"
            else config.embedding_provider
        ),
        "bancos": list(config.bancos),
        "sha256_gabarito_completo": _hash_arquivo(config.conjunto_padrao_path),
        "perguntas_selecionadas": [asdict(pergunta) for pergunta in perguntas],
        "sha256_manifesto_corpus": _hash_arquivo(CAMINHO_METADADOS_CORPUS),
        "sha256_codigo_execucao": _hashes_codigo_material(),
        "sha256_dependencias": {
            nome: _hash_arquivo(raiz / nome)
            for nome in ("requirements.txt", "requirements-local.txt")
        },
        "indice": _identidade_indice_material(Path(dir_indice)),
    }
    for chave, esperado in esperados.items():
        if componentes.get(chave) != esperado:
            raise ValueError(
                f"Estado material atual diverge do fingerprint em {chave}."
            )
    config_provedor = componentes.get("config_provedor_llm")
    atual = _config_provedor_sem_rede(config, config.llm_provider)
    if not isinstance(config_provedor, dict) or any(
        config_provedor.get(chave) != valor for chave, valor in atual.items()
    ):
        raise ValueError("Configuração material do provedor mudou desde a rodada.")


def _calcular_fingerprint(
    config: Config,
    perguntas: list[PerguntaPadrao],
    provedor: ProvedorLLM,
    dir_indice_identidade: Path = DIR_INDICE_VETORIAL,
    repeticao_estabilidade: int | None = None,
) -> tuple[str, dict]:
    """Identifica tudo que pode mudar o resultado ou sua pontuação."""
    dir_indice_identidade = Path(dir_indice_identidade)
    indice = _identidade_indice_material(dir_indice_identidade)
    componentes = {
        "versao_avaliacao": VERSAO_AVALIACAO,
        "versao_prompt": VERSAO_PROMPT,
        "sha256_prompt_rag": hashlib.sha256(PROMPT_SISTEMA.encode()).hexdigest(),
        "sha256_prompt_closed_book": hashlib.sha256(
            PROMPT_SISTEMA_CLOSED_BOOK.encode()
        ).hexdigest(),
        "temperatura": 0.0,
        "recall_k": RECALL_K,
        "tolerancia_numerica_pct": config.tolerancia_numerica_pct,
        "top_k_recuperacao": RECALL_K,
        "repeticao_estabilidade": repeticao_estabilidade,
        "estrategia_demo_e_auditoria": config.estrategia_padrao,
        "provedor_llm": provedor.nome,
        "classe_provedor_llm": (
            f"{type(provedor).__module__}.{type(provedor).__qualname__}"
        ),
        "config_provedor_llm": _identidade_config_provedor(config, provedor),
        "embedding_provider": config.embedding_provider,
        "embedding_modelo": (
            config.ollama_modelo_embedding
            if config.embedding_provider == "ollama"
            else config.embedding_provider
        ),
        "bancos": list(config.bancos),
        "sha256_gabarito_completo": _hash_arquivo(config.conjunto_padrao_path),
        "perguntas_selecionadas": [asdict(pergunta) for pergunta in perguntas],
        "sha256_manifesto_corpus": _hash_arquivo(CAMINHO_METADADOS_CORPUS),
        "sha256_codigo_execucao": _hashes_codigo_material(),
        "sha256_dependencias": {
            nome: _hash_arquivo(Path(__file__).parent.parent / nome)
            for nome in ("requirements.txt", "requirements-local.txt")
        },
        "indice": indice,
    }
    canonico = json.dumps(
        componentes, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest(), componentes


def _selecionar_perguntas(
    config: Config,
    conjunto: str,
    pergunta_ids: Collection[str] | None,
    limite_perguntas: int | None,
) -> list[PerguntaPadrao]:
    perguntas = [
        pergunta
        for pergunta in carregar_conjunto_padrao(config)
        if pergunta.conjunto == conjunto
    ]
    if not perguntas:
        raise ValueError(f"Nenhuma pergunta com conjunto={conjunto!r} no gabarito.")
    if pergunta_ids is not None:
        solicitados = set(pergunta_ids)
        existentes = {pergunta.id for pergunta in perguntas}
        ausentes = sorted(solicitados - existentes)
        if ausentes:
            raise ValueError(
                f"Perguntas solicitadas não pertencem ao conjunto {conjunto!r}: {ausentes}"
            )
        perguntas = [p for p in perguntas if p.id in solicitados]
    if limite_perguntas is not None:
        if limite_perguntas <= 0:
            raise ValueError("limite_perguntas deve ser positivo.")
        perguntas = perguntas[:limite_perguntas]
    if not perguntas:
        raise ValueError("O filtro de perguntas produziu um subconjunto vazio.")
    return perguntas


def executar_avaliacao(
    config: Config,
    recuperador: Recuperador,
    provedor_llm: ProvedorLLM,
    estrategias: list[Estrategia],
    conjunto: str = "teste",
    dir_checkpoint: Path = DIR_RESULTADOS_AVALIACAO,
    dir_logs: Path = DIR_LOGS_EXECUCOES,
    pergunta_ids: Collection[str] | None = None,
    limite_perguntas: int | None = None,
    dir_indice_identidade: Path = DIR_INDICE_VETORIAL,
    repeticao_estabilidade: int | None = None,
) -> dict[Estrategia, MetricasEstrategia]:
    """Serializa uma avaliação por namespace para impedir custo duplicado."""
    dir_checkpoint = Path(dir_checkpoint)
    with bloqueio_exclusivo(
        dir_checkpoint
        / (
            f".avaliacao_{conjunto}.lock"
            if repeticao_estabilidade is None
            else f".avaliacao_{conjunto}_estabilidade_{repeticao_estabilidade}.lock"
        ),
        f"a avaliação do conjunto {conjunto!r}",
    ):
        return _executar_avaliacao_bloqueada(
            config,
            recuperador,
            provedor_llm,
            estrategias,
            conjunto=conjunto,
            dir_checkpoint=dir_checkpoint,
            dir_logs=dir_logs,
            pergunta_ids=pergunta_ids,
            limite_perguntas=limite_perguntas,
            dir_indice_identidade=dir_indice_identidade,
            repeticao_estabilidade=repeticao_estabilidade,
        )


def _executar_avaliacao_bloqueada(
    config: Config,
    recuperador: Recuperador,
    provedor_llm: ProvedorLLM,
    estrategias: list[Estrategia],
    conjunto: str = "teste",
    dir_checkpoint: Path = DIR_RESULTADOS_AVALIACAO,
    dir_logs: Path = DIR_LOGS_EXECUCOES,
    pergunta_ids: Collection[str] | None = None,
    limite_perguntas: int | None = None,
    dir_indice_identidade: Path = DIR_INDICE_VETORIAL,
    repeticao_estabilidade: int | None = None,
) -> dict[Estrategia, MetricasEstrategia]:
    """Executa uma rodada retomável, isolada por fingerprint completo.

    ``pergunta_ids``/``limite_perguntas`` permitem um smoke test explícito sem
    transformar ``--amostra`` em dezenas de chamadas. O subconjunto faz parte
    do fingerprint e nunca reaproveita checkpoint de outra seleção.
    """
    if not estrategias:
        raise ValueError("Ao menos uma estratégia deve ser informada.")
    estrategias_unicas = list(dict.fromkeys(estrategias))
    if not getattr(provedor_llm, "custo_auditavel", True):
        raise ValueError(
            f"O provedor {provedor_llm.nome!r} não tem preços configurados; "
            "a avaliação com teto de custo não pode registrar US$ 0 falsamente."
        )

    if repeticao_estabilidade is not None and (
        type(repeticao_estabilidade) is not int
        or repeticao_estabilidade not in {1, 2, 3}
    ):
        raise ValueError("repeticao_estabilidade deve ser 1, 2 ou 3.")
    perguntas = _selecionar_perguntas(
        config, conjunto, pergunta_ids, limite_perguntas
    )
    if conjunto == "teste":
        todas_teste = [
            pergunta
            for pergunta in carregar_conjunto_padrao(config)
            if pergunta.conjunto == "teste"
        ]
        _validar_conjunto_teste_final(todas_teste)
        if repeticao_estabilidade is not None:
            if (
                pergunta_ids is None
                or len(set(pergunta_ids)) != 10
                or limite_perguntas is not None
                or len(estrategias_unicas) != 1
                or estrategias_unicas[0] == Estrategia.CLOSED_BOOK
            ):
                raise ValueError(
                    "Estabilidade exige exatamente 10 IDs, uma estratégia RAG "
                    "e nenhuma seleção por limite."
                )
        elif pergunta_ids is not None or limite_perguntas is not None:
            raise ValueError(
                "O conjunto teste não admite seleção parcial; use conjunto=dev "
                "para smoke tests."
            )
        if repeticao_estabilidade is None and set(estrategias_unicas) != set(Estrategia):
            raise ValueError(
                "A publicação final do conjunto teste exige E0, E1, E2 e E3."
            )
    elif repeticao_estabilidade is not None:
        raise ValueError("Repetições de estabilidade só são válidas no conjunto teste.")
    fingerprint, componentes = _calcular_fingerprint(
        config,
        perguntas,
        provedor_llm,
        dir_indice_identidade,
        repeticao_estabilidade=repeticao_estabilidade,
    )
    run_id = (
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-"
        f"{uuid4().hex[:10]}"
    )

    dir_checkpoint = Path(dir_checkpoint)
    dir_logs = Path(dir_logs)
    dir_checkpoint.mkdir(parents=True, exist_ok=True)
    caminho_checkpoint = dir_checkpoint / (
        f"checkpoint_{conjunto}.jsonl"
        if repeticao_estabilidade is None
        else f"checkpoint_estabilidade_{repeticao_estabilidade}.jsonl"
    )
    ids_selecionados = {pergunta.id for pergunta in perguntas}
    itens_checkpoint = [
        item
        for item in _carregar_checkpoint(caminho_checkpoint, fingerprint)
        if item.pergunta_id in ids_selecionados
    ]
    itens_auditados = [
        item
        for item in _carregar_itens_auditados(dir_logs, fingerprint)
        if item.pergunta_id in ids_selecionados
    ]
    por_tentativa: dict[tuple[str, str, Estrategia], ResultadoItem] = {}
    for item in itens_checkpoint + itens_auditados:
        identidade = (item.run_id, item.pergunta_id, item.estrategia)
        anterior = por_tentativa.get(identidade)
        if anterior is not None and anterior != item:
            raise ValueError(
                "Checkpoint e log RNF08 divergem para a mesma tentativa; "
                "a retomada automática foi recusada."
            )
        por_tentativa[identidade] = item
    tentativas_auditadas = list(por_tentativa.values())
    _validar_modelos_sucesso(tentativas_auditadas)
    if any(item.custo_usd is None for item in tentativas_auditadas):
        raise ValueError(
            "Checkpoint/log contém tentativa iniciada sem custo auditável; "
            "a retomada automática foi recusada para evitar nova cobrança."
        )
    sucessos_por_chave: dict[tuple[str, Estrategia], ResultadoItem] = {}
    for item in tentativas_auditadas:
        if item.erro is not None or item.estrategia not in estrategias_unicas:
            continue
        chave_sucesso = (item.pergunta_id, item.estrategia)
        if chave_sucesso in sucessos_por_chave:
            raise ValueError(
                "Há mais de um sucesso auditado para a mesma pergunta/"
                "estratégia; a consolidação automática foi recusada."
            )
        sucessos_por_chave[chave_sucesso] = item
    itens = list(sucessos_por_chave.values())
    feitos = set(sucessos_por_chave)
    custo_acumulado = sum(
        float(item.custo_usd) for item in tentativas_auditadas
    )
    arquivo_log = f"execucao_{run_id}.jsonl"
    caminho_journal_chamadas = (
        dir_logs / "journal_chamadas" / f"{fingerprint}.jsonl"
    )
    perguntas_por_id = {pergunta.id: pergunta for pergunta in perguntas}
    tentativas_checkpoint = {
        (item.run_id, item.pergunta_id, item.estrategia)
        for item in itens_checkpoint
    }
    tentativas_log = {
        (item.run_id, item.pergunta_id, item.estrategia)
        for item in itens_auditados
    }
    _validar_journal_chamadas(
        caminho_journal_chamadas,
        fingerprint,
        tentativas_auditadas,
    )

    # Reconcilia as duas cópias duráveis antes de qualquer chamada nova. Uma
    # falha entre os appends nunca pode esconder custo nem provocar cobrança 2×.
    for identidade, item in por_tentativa.items():
        if identidade not in tentativas_log:
            registro = _registro_execucao(
                perguntas_por_id[item.pergunta_id],
                item,
                provedor_llm.nome,
                custo_acumulado,
                componentes,
            )
            registro["recuperado_de_checkpoint"] = True
            registrar_execucao(
                registro,
                dir_logs=dir_logs,
                arquivo=arquivo_log,
            )
            tentativas_log.add(identidade)
        if identidade not in tentativas_checkpoint:
            _anexar_checkpoint(caminho_checkpoint, item)
            tentativas_checkpoint.add(identidade)

    erros_da_invocacao: list[ResultadoItem] = []
    estrategias_aquecidas_nesta_invocacao: set[Estrategia] = set()

    for estrategia in estrategias_unicas:
        for pergunta in perguntas:
            chave = (pergunta.id, estrategia)
            if chave in feitos:
                continue
            if custo_acumulado >= config.orcamento_teto_usd:
                raise CustoExcedidoError(
                    f"Gasto acumulado US$ {custo_acumulado:.6f} atingiu o teto "
                    f"ORCAMENTO_TETO_USD={config.orcamento_teto_usd}; checkpoint "
                    f"em {caminho_checkpoint}."
                )

            item = _avaliar_item(
                config,
                recuperador,
                provedor_llm,
                pergunta,
                estrategia,
                run_id=run_id,
                fingerprint=fingerprint,
                orcamento_restante=max(
                    0.0, config.orcamento_teto_usd - custo_acumulado
                ),
                caminho_journal_chamadas=caminho_journal_chamadas,
                latencia_a_quente=(
                    estrategia in estrategias_aquecidas_nesta_invocacao
                ),
            )
            if item.n_chamadas > 0:
                estrategias_aquecidas_nesta_invocacao.add(estrategia)
            if item.custo_usd is not None:
                custo_acumulado += item.custo_usd
            registro = _registro_execucao(
                pergunta,
                item,
                provedor_llm.nome,
                custo_acumulado,
                componentes,
            )
            try:
                registrar_execucao(
                    registro,
                    dir_logs=dir_logs,
                    arquivo=arquivo_log,
                )
            except Exception as erro_log:
                # O checkpoint é a cópia de emergência. A retomada o converte
                # novamente em log antes de fazer qualquer chamada.
                try:
                    _anexar_checkpoint(caminho_checkpoint, item)
                except Exception as erro_checkpoint:
                    raise AvaliacaoIncompletaError(
                        "Falharam log RNF08 e checkpoint após a chamada: "
                        f"log={erro_log}; checkpoint={erro_checkpoint}"
                    ) from erro_checkpoint
                raise AvaliacaoIncompletaError(
                    "Falha ao persistir log RNF08; métricas não foram "
                    "publicadas. Um checkpoint de recuperação foi preservado."
                ) from erro_log

            try:
                _anexar_checkpoint(caminho_checkpoint, item)
            except Exception as exc:
                raise AvaliacaoIncompletaError(
                    "Log RNF08 preservado, mas o checkpoint falhou; a "
                    "retomada será feita pelo journal e nenhuma métrica foi "
                    "publicada nesta invocação."
                ) from exc

            identidade_item = (item.run_id, item.pergunta_id, item.estrategia)
            por_tentativa[identidade_item] = item
            tentativas_auditadas = list(por_tentativa.values())
            _validar_modelos_sucesso(tentativas_auditadas)

            if item.erro is None:
                itens.append(item)
                feitos.add(chave)
            else:
                erros_da_invocacao.append(item)

            if item.custo_usd is None:
                raise AvaliacaoIncompletaError(
                    "A chamada falhou sem custo auditável; a avaliação foi "
                    "interrompida e não publicará métricas."
                )
            if custo_acumulado > config.orcamento_teto_usd:
                raise CustoExcedidoError(
                    f"A última chamada elevou o gasto observado a US$ "
                    f"{custo_acumulado:.6f}, acima do teto "
                    f"ORCAMENTO_TETO_USD={config.orcamento_teto_usd}. O item foi "
                    f"contabilizado e preservado em {caminho_checkpoint}."
                )

    if erros_da_invocacao:
        detalhes = "; ".join(
            f"{item.pergunta_id}/{item.estrategia.value}: {item.erro}"
            for item in erros_da_invocacao
        )
        raise AvaliacaoIncompletaError(
            "Avaliação incompleta; métricas e cache não foram publicados. " + detalhes
        )

    metricas = consolidar_metricas(itens, tentativas=tentativas_auditadas)
    caminho_metricas = (
        dir_checkpoint / f"metricas_{conjunto}.json"
        if repeticao_estabilidade is None
        else dir_checkpoint
        / f"metricas_estabilidade_{repeticao_estabilidade}.json"
    )
    _salvar_metricas(
        metricas,
        caminho_metricas,
        fingerprint=fingerprint,
        run_id=run_id,
        run_ids=sorted({item.run_id for item in tentativas_auditadas if item.run_id}),
        conjunto=("estabilidade" if repeticao_estabilidade is not None else conjunto),
        estrategia_demo_e_auditoria=config.estrategia_padrao,
        provedor_llm=provedor_llm.nome,
        fingerprint_componentes=componentes,
    )
    if repeticao_estabilidade is None:
        _salvar_cache_demo(
            config,
            perguntas,
            itens,
            provedor_llm.nome,
            dir_checkpoint,
            fingerprint=fingerprint,
            run_id=run_id,
            conjunto=conjunto,
        )
    return metricas


def _flags_de_falha(
    pergunta: PerguntaPadrao, estrategia: Estrategia
) -> tuple[bool | None, bool | None, bool | None]:
    recall = (
        False
        if pergunta.categoria in ("factual", "comparativa")
        and estrategia != Estrategia.CLOSED_BOOK
        else None
    )
    exatidao = False if pergunta.categoria == "factual" else None
    recusa = False if pergunta.categoria == "adversarial" else None
    return recall, exatidao, recusa


def _eh_erro_transitorio(exc: Exception) -> bool:
    if isinstance(exc, (RateLimitError, APIConnectionError, APITimeoutError)):
        return True
    status = getattr(exc, "status_code", None)
    if status is None and isinstance(exc, APIStatusError):
        status = exc.status_code
    if status in _STATUS_TRANSITORIOS:
        return True
    return isinstance(exc, (ConnectionError, TimeoutError))


def _retry_after_s(exc: Exception, tentativa: int) -> float:
    resposta = getattr(exc, "response", None)
    headers = getattr(resposta, "headers", None) or getattr(exc, "headers", None)
    valor = headers.get("retry-after") if headers is not None else None
    if valor is not None:
        try:
            return min(60.0, max(0.0, float(valor)))
        except (TypeError, ValueError):
            try:
                instante = parsedate_to_datetime(str(valor))
                if instante.tzinfo is None:
                    instante = instante.replace(tzinfo=timezone.utc)
                segundos = (instante - datetime.now(timezone.utc)).total_seconds()
                return min(60.0, max(0.0, segundos))
            except (TypeError, ValueError, OverflowError):
                pass
    return min(60.0, float(2**tentativa))


def _validar_telemetria_uso(uso) -> None:
    for campo in ("tokens_entrada", "tokens_saida"):
        valor = getattr(uso, campo, None)
        if type(valor) is not int or valor < 0:
            raise ValueError(f"Telemetria inválida: {campo} deve ser inteiro >= 0.")
    custo = getattr(uso, "custo_usd", None)
    if (
        not isinstance(custo, (int, float))
        or isinstance(custo, bool)
        or not math.isfinite(float(custo))
        or custo < 0
    ):
        raise ValueError("Telemetria inválida: custo_usd deve ser finito e >= 0.")
    latencia = getattr(uso, "latencia_s", None)
    if (
        not isinstance(latencia, (int, float))
        or isinstance(latencia, bool)
        or not math.isfinite(float(latencia))
        or latencia < 0
    ):
        raise ValueError("Telemetria inválida: latencia_s deve ser finita e >= 0.")


def _anexar_evento_journal_chamada(caminho: Path, evento: dict) -> None:
    """Persiste intenção/conclusão sem prompt ou resposta antes de prosseguir."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linha = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **evento,
    }
    with caminho.open("a", encoding="utf-8") as destino:
        destino.write(json.dumps(linha, ensure_ascii=False) + "\n")
        destino.flush()
        os.fsync(destino.fileno())


def _linhas_jsonl_relevantes(
    caminho: Path,
    fingerprint: str | None,
    descricao: str,
) -> list[dict]:
    """Lê JSONL filtrando snapshots antigos antes do parse.

    Uma última linha sem newline pode ser um append interrompido e é ignorada;
    qualquer corrupção relevante anterior continua sendo erro de integridade.
    """
    if not caminho.exists():
        return []
    try:
        linhas = caminho.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"{descricao} ilegível em {caminho}: {type(exc).__name__}") from exc
    marcador = fingerprint
    registros: list[dict] = []
    for indice, linha in enumerate(linhas):
        if not linha.strip():
            continue
        if marcador is not None and marcador not in linha:
            continue
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError as exc:
            eh_ultima_truncada = indice == len(linhas) - 1 and not linha.endswith("\n")
            if eh_ultima_truncada:
                continue
            raise ValueError(
                f"{descricao} inválido em {caminho}, linha {indice + 1}: {exc}"
            ) from exc
        if not isinstance(registro, dict):
            raise ValueError(
                f"{descricao} inválido em {caminho}, linha {indice + 1}: "
                "registro deve ser objeto JSON."
            )
        if fingerprint is not None and registro.get("fingerprint") != fingerprint:
            continue
        registros.append(registro)
    return registros


def _validar_journal_chamadas(
    caminho: Path,
    fingerprint: str,
    itens_contabilizados: list[ResultadoItem],
) -> None:
    itens_por_call_id: dict[str, ResultadoItem] = {}
    for item in itens_contabilizados:
        _validar_invariantes_resultado_item(item)
        for call_id in item.call_ids:
            if call_id in itens_por_call_id:
                raise ValueError("call_id foi contabilizado em mais de um item.")
            itens_por_call_id[call_id] = item
    inicios: dict[str, dict] = {}
    finais: dict[str, dict] = {}
    for registro in _linhas_jsonl_relevantes(
        caminho, fingerprint, "Journal write-ahead de chamadas"
    ):
        evento = registro.get("evento")
        call_id = registro.get("call_id")
        if evento not in {"inicio", "fim"} or not isinstance(call_id, str) or not call_id:
            raise ValueError("Journal write-ahead contém evento fora do contrato.")
        destino = inicios if evento == "inicio" else finais
        if call_id in destino:
            raise ValueError(
                "Journal write-ahead contém evento duplicado para uma chamada."
            )
        destino[call_id] = registro
    for call_id, inicio in inicios.items():
        estimativa = inicio.get("estimativa_maxima_usd")
        if (
            inicio.get("fingerprint") != fingerprint
            or not isinstance(inicio.get("run_id"), str)
            or not inicio["run_id"]
            or not isinstance(inicio.get("pergunta_id"), str)
            or not inicio["pergunta_id"]
            or inicio.get("estrategia") not in {e.value for e in Estrategia}
            or type(inicio.get("tentativa")) is not int
            or inicio["tentativa"] <= 0
            or (
                estimativa is not None
                and (
                    not isinstance(estimativa, (int, float))
                    or isinstance(estimativa, bool)
                    or not math.isfinite(float(estimativa))
                    or estimativa < 0
                )
            )
        ):
            raise ValueError(f"Intenção write-ahead inválida: {call_id}.")
    if set(finais) - set(inicios):
        raise ValueError("Journal write-ahead contém conclusão sem intenção prévia.")
    if set(itens_por_call_id) - set(inicios):
        raise ValueError("ResultadoItem contém call_id ausente do journal.")
    for call_id, inicio in inicios.items():
        item = itens_por_call_id.get(call_id)
        if item is not None and (
            item.run_id,
            item.pergunta_id,
            item.estrategia.value,
        ) != (
            inicio.get("run_id"),
            inicio.get("pergunta_id"),
            inicio.get("estrategia"),
        ):
            raise ValueError("ResultadoItem diverge da intenção write-ahead.")
        fim = finais.get(call_id)
        if fim is not None and (
            fim.get("fingerprint") != fingerprint
            or fim.get("run_id") != inicio.get("run_id")
            or fim.get("resultado") not in {"sucesso", "erro"}
        ):
            raise ValueError("Conclusão write-ahead diverge da intenção.")
        if fim is not None:
            campo_custo = (
                "custo_observado_usd"
                if fim["resultado"] == "sucesso"
                else "debito_conservador_usd"
            )
            custo = fim.get(campo_custo)
            if (
                not isinstance(custo, (int, float))
                or isinstance(custo, bool)
                or not math.isfinite(float(custo))
                or custo < 0
            ):
                raise ValueError("Conclusão write-ahead contém custo inválido.")
            if fim["resultado"] == "erro":
                estimativa = inicio.get("estimativa_maxima_usd")
                if (
                    not isinstance(estimativa, (int, float))
                    or isinstance(estimativa, bool)
                    or not math.isclose(
                        float(fim["debito_conservador_usd"]),
                        float(estimativa),
                        abs_tol=1e-12,
                    )
                ):
                    raise ValueError(
                        "Débito de erro diverge da estimativa write-ahead."
                    )
            else:
                estimativa = inicio.get("estimativa_maxima_usd")
                if estimativa is not None and float(custo) > float(estimativa) + 1e-12:
                    raise ValueError(
                        "Custo observado excede a estimativa write-ahead."
                    )
                if (
                    type(fim.get("tokens_entrada")) is not int
                    or fim["tokens_entrada"] < 0
                    or type(fim.get("tokens_saida")) is not int
                    or fim["tokens_saida"] < 0
                ):
                    raise ValueError("Conclusão de sucesso contém tokens inválidos.")
    for item in itens_contabilizados:
        finais_item = [finais.get(call_id) for call_id in item.call_ids]
        sucessos = [
            fim for fim in finais_item if fim and fim["resultado"] == "sucesso"
        ]
        erros = [
            fim for fim in finais_item if fim and fim["resultado"] == "erro"
        ]
        ausentes = sum(fim is None for fim in finais_item)
        if len(sucessos) > 1:
            raise ValueError("ResultadoItem possui mais de um fim de sucesso.")
        if not ausentes:
            if item.erro is None and len(sucessos) != 1:
                raise ValueError(
                    "ResultadoItem bem-sucedido não possui fim de sucesso."
                )
            custo_observado = sum(
                float(fim["custo_observado_usd"]) for fim in sucessos
            )
            debitos = [fim["debito_conservador_usd"] for fim in erros]
            custo_falhas = sum(float(debito) for debito in debitos)
            if not math.isclose(
                custo_falhas,
                float(item.custo_estimado_falhas_usd),
                abs_tol=1e-12,
            ):
                raise ValueError("Débitos do journal divergem do item.")
            if not math.isclose(
                custo_observado,
                float(item.custo_observado_usd or 0.0),
                abs_tol=1e-12,
            ):
                raise ValueError("Custo observado do journal diverge do item.")
            if len(erros) != item.n_chamadas_sem_telemetria:
                raise ValueError("Contagem sem telemetria diverge do journal.")
            if sucessos and (
                sucessos[0].get("tokens_entrada") != item.tokens_entrada
                or sucessos[0].get("tokens_saida") != item.tokens_saida
            ):
                raise ValueError("Tokens do journal divergem do item.")
    nao_contabilizadas = set(inicios) - set(itens_por_call_id)
    if nao_contabilizadas:
        raise AvaliacaoIncompletaError(
            "Há chamada(s) com intenção durável, mas sem ResultadoItem "
            "reconciliado. A retomada automática foi bloqueada para evitar "
            "repetição/cobrança após queda abrupta; faça reconciliação manual. "
            f"Quantidade: {len(nao_contabilizadas)}."
        )


def reconciliar_chamada_orfa(
    config: Config,
    *,
    fingerprint: str,
    call_id: str,
    caminho_journal: Path,
    caminho_checkpoint: Path,
    dir_auditoria: Path,
) -> ResultadoItem:
    """Materializa uma intenção órfã como erro debitado, sem repetir a API."""
    if re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None or not call_id:
        raise ValueError("fingerprint/call_id inválido para reconciliação.")
    registros = _linhas_jsonl_relevantes(
        Path(caminho_journal), fingerprint, "Journal write-ahead de chamadas"
    )
    inicios = [
        registro
        for registro in registros
        if registro.get("evento") == "inicio" and registro.get("call_id") == call_id
    ]
    finais = [
        registro
        for registro in registros
        if registro.get("evento") == "fim" and registro.get("call_id") == call_id
    ]
    if len(inicios) != 1 or len(finais) > 1:
        raise ValueError("call_id não identifica uma única intenção reconciliável.")
    inicio = inicios[0]
    if inicio.get("fingerprint") != fingerprint:
        raise ValueError("Intenção pertence a outro fingerprint.")
    try:
        estrategia = Estrategia(inicio["estrategia"])
    except (KeyError, ValueError) as exc:
        raise ValueError("Estratégia da intenção é inválida.") from exc
    perguntas = {
        pergunta.id: pergunta for pergunta in carregar_conjunto_padrao(config)
    }
    pergunta = perguntas.get(inicio.get("pergunta_id"))
    if pergunta is None:
        raise ValueError("Pergunta da intenção não existe no conjunto configurado.")

    itens = _carregar_checkpoint(Path(caminho_checkpoint), fingerprint)
    try:
        _validar_journal_chamadas(Path(caminho_journal), fingerprint, itens)
    except AvaliacaoIncompletaError:
        # Esta é precisamente a condição reconciliável. Erros estruturais
        # continuam propagando antes de qualquer append durável.
        pass
    mesmo_call = [item for item in itens if call_id in item.call_ids]
    mesma_tentativa = [
        item
        for item in itens
        if (item.run_id, item.pergunta_id, item.estrategia)
        == (inicio.get("run_id"), pergunta.id, estrategia)
    ]
    if len(mesmo_call) > 1 or len(mesma_tentativa) > 1:
        raise ValueError("Checkpoint contém reconciliação ambígua.")
    if mesma_tentativa and not mesmo_call:
        raise ValueError("Tentativa já existe sem o call_id órfão.")

    fim = finais[0] if finais else None
    if fim is not None and fim.get("resultado") == "erro":
        estimativa_inicio = inicio.get("estimativa_maxima_usd")
        debito_fim = fim.get("debito_conservador_usd")
        if (
            not isinstance(estimativa_inicio, (int, float))
            or isinstance(estimativa_inicio, bool)
            or not isinstance(debito_fim, (int, float))
            or isinstance(debito_fim, bool)
            or not math.isclose(
                float(debito_fim), float(estimativa_inicio), abs_tol=1e-12
            )
        ):
            raise ValueError("Fim órfão subconta a estimativa write-ahead.")
    if mesmo_call:
        item = mesmo_call[0]
    else:
        estimativa = inicio.get("estimativa_maxima_usd")
        if fim is not None and fim.get("resultado") == "sucesso":
            custo_observado = fim.get("custo_observado_usd")
            custo_estimado = 0.0
            n_sem_telemetria = 0
            tokens_entrada = fim.get("tokens_entrada")
            tokens_saida = fim.get("tokens_saida")
            if (
                not isinstance(custo_observado, (int, float))
                or isinstance(custo_observado, bool)
                or not math.isfinite(float(custo_observado))
                or custo_observado < 0
                or type(tokens_entrada) is not int
                or tokens_entrada < 0
                or type(tokens_saida) is not int
                or tokens_saida < 0
            ):
                raise ValueError("Fim de sucesso órfão não possui telemetria válida.")
        else:
            custo_observado = None
            custo_estimado = (
                fim.get("debito_conservador_usd") if fim is not None else estimativa
            )
            n_sem_telemetria = 1
            tokens_entrada = 0
            tokens_saida = 0
        if (
            custo_estimado is None
            or not isinstance(custo_estimado, (int, float))
            or isinstance(custo_estimado, bool)
            or not math.isfinite(float(custo_estimado))
            or custo_estimado < 0
        ):
            raise ValueError(
                "Intenção órfã não possui débito conservador finito; "
                "a retomada permanece bloqueada."
            )
        recall, exatidao, recusa = _flags_de_falha(pergunta, estrategia)
        item = ResultadoItem(
            pergunta_id=pergunta.id,
            estrategia=estrategia,
            resposta=None,
            categoria=pergunta.categoria,
            recuperados=[],
            recall_ok=recall,
            exatidao_ok=exatidao,
            recusa_correta=recusa,
            custo_usd=float(custo_estimado) + float(custo_observado or 0.0),
            custo_observado_usd=(
                None if custo_observado is None else float(custo_observado)
            ),
            custo_estimado_falhas_usd=float(custo_estimado),
            n_chamadas=1,
            n_chamadas_sem_telemetria=n_sem_telemetria,
            tokens_entrada=tokens_entrada,
            tokens_saida=tokens_saida,
            modelo="indisponivel-apos-queda",
            erro="InterrupcaoReconciliada: resposta indisponível após queda",
            run_id=inicio["run_id"],
            fingerprint=fingerprint,
            call_ids=(call_id,),
        )
        _anexar_checkpoint(Path(caminho_checkpoint), item)
        itens.append(item)

    if fim is None:
        evento_fim = {
            "evento": "fim",
            "call_id": call_id,
            "fingerprint": fingerprint,
            "run_id": item.run_id,
            "resultado": (
                "sucesso" if item.custo_observado_usd is not None else "erro"
            ),
        }
        if item.custo_observado_usd is not None:
            evento_fim.update(
                {
                    "custo_observado_usd": item.custo_observado_usd,
                    "tokens_entrada": item.tokens_entrada,
                    "tokens_saida": item.tokens_saida,
                }
            )
        else:
            evento_fim.update(
                {
                    "erro": "InterrupcaoReconciliada",
                    "debito_conservador_usd": item.custo_estimado_falhas_usd,
                }
            )
        _anexar_evento_journal_chamada(Path(caminho_journal), evento_fim)

    try:
        _validar_journal_chamadas(
            Path(caminho_journal),
            fingerprint,
            _carregar_checkpoint(Path(caminho_checkpoint), fingerprint),
        )
    except AvaliacaoIncompletaError:
        # A chamada escolhida já está contabilizada; outras órfãs continuam
        # bloqueando a avaliação e podem ser reconciliadas uma a uma.
        pass
    registrar_execucao(
        {
            "evento": "reconciliacao_chamada_orfa",
            "fingerprint": fingerprint,
            "call_id": call_id,
            "run_id": item.run_id,
            "pergunta_id": item.pergunta_id,
            "estrategia": item.estrategia.value,
            "debito_conservador_usd": item.custo_usd,
        },
        dir_logs=Path(dir_auditoria),
    )
    return item


def _avaliar_item(
    config: Config,
    recuperador: Recuperador,
    provedor_llm: ProvedorLLM,
    pergunta: PerguntaPadrao,
    estrategia: Estrategia,
    tentativas: int = 3,
    *,
    run_id: str = "",
    fingerprint: str = "",
    orcamento_restante: float | None = None,
    caminho_journal_chamadas: Path | None = None,
    latencia_a_quente: bool = True,
) -> ResultadoItem:
    """Mede recuperação+geração; repete somente falhas transitórias."""
    if tentativas <= 0:
        raise ValueError("tentativas deve ser positivo.")
    inicio_total = perf_counter()
    recuperados: list[ResultadoRecuperacao] | None = None
    ultimo_erro: Exception | None = None
    custo_estimado_falhas = 0.0
    houve_chamada_sem_estimativa = False
    chamadas_iniciadas = 0
    chamadas_sem_telemetria = 0
    call_ids: list[str] = []
    ultimo_uso_concluido = None

    for tentativa in range(tentativas):
        estimativa: float | None = None
        chamada_iniciada = False
        fim_registrado = False
        uso_concluido = None
        try:
            if recuperados is None:
                recuperados = recuperador.recuperar(
                    pergunta.pergunta, estrategia, top_k=RECALL_K
                )
            modo_closed_book = estrategia == Estrategia.CLOSED_BOOK
            chunks = [resultado.chunk for resultado in recuperados]
            prompt_sistema = (
                PROMPT_SISTEMA_CLOSED_BOOK if modo_closed_book else PROMPT_SISTEMA
            )
            prompt_usuario = montar_prompt_usuario(
                pergunta.pergunta, chunks, modo_closed_book
            )
            estimativa = provedor_llm.estimar_custo_maximo(
                prompt_sistema, prompt_usuario
            )
            if estimativa is None:
                raise ValueError(
                    "Estimativa de custo deve existir antes de qualquer chamada."
                )
            if (
                not isinstance(estimativa, (int, float))
                or isinstance(estimativa, bool)
                or not math.isfinite(float(estimativa))
                or estimativa < 0
            ):
                raise ValueError("Estimativa de custo deve ser finita e >= 0.")
            if estimativa is not None:
                if (
                    orcamento_restante is not None
                    and custo_estimado_falhas + estimativa > orcamento_restante
                ):
                    erro_teto = CustoExcedidoError(
                        f"Estimativa conservadora da próxima chamada "
                        f"(US$ {estimativa:.6f}; falhas já reservadas: "
                        f"US$ {custo_estimado_falhas:.6f}) excede o saldo do teto "
                        f"(US$ {orcamento_restante:.6f}); nenhuma chamada foi feita."
                    )
                    if custo_estimado_falhas > 0:
                        ultimo_erro = erro_teto
                        break
                    raise erro_teto
            call_id = uuid4().hex
            if caminho_journal_chamadas is not None:
                _anexar_evento_journal_chamada(
                    caminho_journal_chamadas,
                    {
                        "evento": "inicio",
                        "call_id": call_id,
                        "fingerprint": fingerprint,
                        "run_id": run_id,
                        "pergunta_id": pergunta.id,
                        "estrategia": estrategia.value,
                        "tentativa": tentativa + 1,
                        "estimativa_maxima_usd": estimativa,
                    },
                )
            call_ids.append(call_id)
            chamada_iniciada = True
            chamadas_iniciadas += 1
            resposta, uso = gerar_resposta(
                pergunta.pergunta,
                chunks,
                provedor_llm,
                config,
                temperatura=0.0,
                modo_closed_book=modo_closed_book,
            )
            _validar_telemetria_uso(uso)
            uso_concluido = uso
            ultimo_uso_concluido = uso
            if caminho_journal_chamadas is not None:
                # Marque antes do append: se o fsync falhar depois de escrever,
                # nunca tente persistir um segundo evento terminal conflitante.
                fim_registrado = True
                _anexar_evento_journal_chamada(
                    caminho_journal_chamadas,
                    {
                        "evento": "fim",
                        "call_id": call_id,
                        "fingerprint": fingerprint,
                        "run_id": run_id,
                        "resultado": "sucesso",
                        "custo_observado_usd": uso.custo_usd,
                        "tokens_entrada": uso.tokens_entrada,
                        "tokens_saida": uso.tokens_saida,
                    },
                )
            if float(uso.custo_usd) > float(estimativa) + 1e-12:
                raise ValueError(
                    "Telemetria inválida: custo observado excede a estimativa."
                )
            item = ResultadoItem(
                pergunta_id=pergunta.id,
                estrategia=estrategia,
                resposta=resposta,
                categoria=pergunta.categoria,
                recuperados=recuperados,
                custo_usd=(
                    None
                    if uso.custo_usd is None
                    else uso.custo_usd + custo_estimado_falhas
                ),
                custo_observado_usd=uso.custo_usd,
                custo_estimado_falhas_usd=custo_estimado_falhas,
                latencia_s=perf_counter() - inicio_total,
                latencia_a_quente=latencia_a_quente,
                tokens_entrada=uso.tokens_entrada,
                tokens_saida=uso.tokens_saida,
                modelo=uso.modelo,
                run_id=run_id,
                fingerprint=fingerprint,
                n_chamadas=chamadas_iniciadas,
                n_chamadas_sem_telemetria=chamadas_sem_telemetria,
                call_ids=tuple(call_ids),
            )
            if pergunta.categoria in ("factual", "comparativa"):
                if estrategia != Estrategia.CLOSED_BOOK:
                    item.recall_ok = avaliar_recall_at_k(
                        pergunta, recuperados, k=RECALL_K
                    )
                if pergunta.categoria == "factual":
                    item.exatidao_ok = avaliar_exatidao_numerica(
                        pergunta, resposta, config
                    )
            elif pergunta.categoria == "adversarial":
                item.recusa_correta = avaliar_recusa(pergunta, resposta)
            return item
        except CustoExcedidoError:
            raise
        except Exception as exc:  # noqa: BLE001 - classificado abaixo
            if chamada_iniciada:
                if uso_concluido is None:
                    chamadas_sem_telemetria += 1
                if (
                    uso_concluido is None
                    and caminho_journal_chamadas is not None
                    and not fim_registrado
                ):
                    try:
                        fim_registrado = True
                        _anexar_evento_journal_chamada(
                            caminho_journal_chamadas,
                            {
                                "evento": "fim",
                                "call_id": call_ids[-1],
                                "fingerprint": fingerprint,
                                "run_id": run_id,
                                "resultado": "erro",
                                "erro": _resumir_erro(exc),
                                "debito_conservador_usd": estimativa,
                            },
                        )
                    except Exception as erro_journal:  # noqa: BLE001
                        exc = erro_journal
                if uso_concluido is None and estimativa is None:
                    houve_chamada_sem_estimativa = True
                elif uso_concluido is None:
                    # A API pode ter processado/cobrado mesmo sem devolver
                    # telemetria. Toda tentativa iniciada, inclusive a final,
                    # reserva o limite conservador no teto e no journal.
                    custo_estimado_falhas += float(estimativa)
            ultimo_erro = exc
            if (
                uso_concluido is not None
                or not _eh_erro_transitorio(exc)
                or tentativa == tentativas - 1
            ):
                break
            if estimativa is None:
                # Sem limite a priori não há como provar que um retry respeita
                # RN03; falhar é preferível a cobrar novamente às cegas.
                break
            time.sleep(_retry_after_s(exc, tentativa))

    recall, exatidao, recusa = _flags_de_falha(pergunta, estrategia)
    erro = _resumir_erro(ultimo_erro)
    custo_observado = (
        None
        if ultimo_uso_concluido is None
        else float(ultimo_uso_concluido.custo_usd)
    )
    return ResultadoItem(
        pergunta_id=pergunta.id,
        estrategia=estrategia,
        resposta=None,
        categoria=pergunta.categoria,
        recuperados=recuperados or [],
        recall_ok=recall,
        exatidao_ok=exatidao,
        recusa_correta=recusa,
        custo_usd=(
            None
            if houve_chamada_sem_estimativa
            else custo_estimado_falhas + (custo_observado or 0.0)
        ),
        custo_observado_usd=custo_observado,
        custo_estimado_falhas_usd=custo_estimado_falhas,
        latencia_s=perf_counter() - inicio_total,
        latencia_a_quente=latencia_a_quente,
        tokens_entrada=(
            0
            if ultimo_uso_concluido is None
            else ultimo_uso_concluido.tokens_entrada
        ),
        tokens_saida=(
            0
            if ultimo_uso_concluido is None
            else ultimo_uso_concluido.tokens_saida
        ),
        modelo=(
            _modelo_configurado(config, provedor_llm)
            if ultimo_uso_concluido is None
            else ultimo_uso_concluido.modelo
        ),
        erro=erro,
        run_id=run_id,
        fingerprint=fingerprint,
        n_chamadas=chamadas_iniciadas,
        n_chamadas_sem_telemetria=chamadas_sem_telemetria,
        call_ids=tuple(call_ids),
    )


def _resumir_erro(exc: Exception | None) -> str:
    """Retém diagnóstico estrutural sem persistir corpo remoto refletido."""
    if exc is None:
        return "Erro desconhecido"
    nome = type(exc).__name__
    mensagem = str(exc)
    prefixos_internos = (
        "Telemetria inválida:",
        "Estimativa de custo deve",
    )
    if isinstance(exc, ValueError) and mensagem.startswith(prefixos_internos):
        return f"{nome}: {mensagem}"
    detalhes: list[str] = []
    status = getattr(exc, "status_code", None)
    if type(status) is int:
        detalhes.append(f"status={status}")
    request_id = getattr(exc, "request_id", None)
    if isinstance(request_id, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", request_id):
        detalhes.append(f"request_id={request_id}")
    return nome + (f" ({', '.join(detalhes)})" if detalhes else "")


def _serializar_recuperado(resultado: ResultadoRecuperacao) -> dict:
    chunk = asdict(resultado.chunk)
    chunk["texto"] = redigir_dados_pessoais(chunk["texto"])
    return {
        "chunk": chunk,
        "score": resultado.score,
        "origem": resultado.origem.value,
    }


def _serializar_resposta(resposta: RespostaGerada | None) -> dict | None:
    if resposta is None:
        return None
    return {
        "resposta": redigir_dados_pessoais(resposta.resposta or "")
        if resposta.resposta is not None
        else None,
        "recusa": resposta.recusa,
        "motivo_recusa": redigir_dados_pessoais(resposta.motivo_recusa or "")
        if resposta.motivo_recusa is not None
        else None,
        "citacoes": [asdict(citacao) for citacao in resposta.citacoes],
        "bruto": redigir_dados_pessoais(resposta.bruto),
        "json_reparado": resposta.json_reparado,
        "json_invalido": resposta.json_invalido,
    }


def _anexar_checkpoint(caminho: Path, item: ResultadoItem) -> None:
    _validar_invariantes_resultado_item(item)
    registro = {
        "fingerprint": item.fingerprint,
        "run_id": item.run_id,
        "pergunta_id": item.pergunta_id,
        "categoria": item.categoria,
        "estrategia": item.estrategia.value,
        "recall_ok": item.recall_ok,
        "exatidao_ok": item.exatidao_ok,
        "recusa_correta": item.recusa_correta,
        "custo_usd": item.custo_usd,
        "custo_observado_usd": item.custo_observado_usd,
        "custo_estimado_falhas_usd": item.custo_estimado_falhas_usd,
        "n_chamadas": item.n_chamadas,
        "n_chamadas_sem_telemetria": item.n_chamadas_sem_telemetria,
        "call_ids": list(item.call_ids),
        "latencia_s": item.latencia_s,
        "latencia_a_quente": item.latencia_a_quente,
        "tokens_entrada": item.tokens_entrada,
        "tokens_saida": item.tokens_saida,
        "modelo": item.modelo,
        "erro": item.erro,
        "resposta": _serializar_resposta(item.resposta),
        "recuperados": [
            _serializar_recuperado(resultado) for resultado in item.recuperados
        ],
    }
    with open(caminho, "a", encoding="utf-8") as destino:
        destino.write(json.dumps(registro, ensure_ascii=False) + "\n")
        destino.flush()
        os.fsync(destino.fileno())


def _desserializar_resposta(bruto: dict | None) -> RespostaGerada | None:
    if bruto is None:
        return None
    return RespostaGerada(
        resposta=bruto["resposta"],
        recusa=bruto["recusa"],
        motivo_recusa=bruto["motivo_recusa"],
        citacoes=tuple(Citacao(**citacao) for citacao in bruto["citacoes"]),
        bruto=bruto.get("bruto", ""),
        json_reparado=bruto["json_reparado"],
        json_invalido=bruto["json_invalido"],
    )


def _desserializar_recuperados(brutos: list[dict]) -> list[ResultadoRecuperacao]:
    return [
        ResultadoRecuperacao(
            chunk=Chunk(**bruto["chunk"]),
            score=float(bruto["score"]),
            origem=Estrategia(bruto["origem"]),
        )
        for bruto in brutos
    ]


def _desserializar_call_ids(brutos: object) -> tuple[str, ...]:
    if not isinstance(brutos, (list, tuple)) or any(
        not isinstance(item, str) or not item for item in brutos
    ):
        raise ValueError("call_ids deve ser uma lista de strings não vazias.")
    if len(set(brutos)) != len(brutos):
        raise ValueError("call_ids contém duplicata.")
    return tuple(brutos)


def _item_de_registro(registro: dict, *, formato_log: bool) -> ResultadoItem:
    item = ResultadoItem(
        pergunta_id=registro["pergunta_id"],
        estrategia=Estrategia(registro["estrategia"]),
        resposta=_desserializar_resposta(registro.get("resposta")),
        categoria=registro.get("categoria", ""),
        recuperados=_desserializar_recuperados(
            registro.get(
                "chunks_recuperados" if formato_log else "recuperados", []
            )
        ),
        recall_ok=registro.get("recall_ok"),
        exatidao_ok=registro.get("exatidao_ok"),
        recusa_correta=registro.get("recusa_correta"),
        custo_usd=registro.get("custo_usd"),
        custo_observado_usd=registro.get("custo_observado_usd"),
        custo_estimado_falhas_usd=registro.get(
            "custo_estimado_falhas_usd", 0.0
        ),
        n_chamadas=registro.get("n_chamadas", 1 if registro.get("erro") is None else 0),
        n_chamadas_sem_telemetria=registro.get("n_chamadas_sem_telemetria", 0),
        call_ids=_desserializar_call_ids(registro.get("call_ids", ())),
        latencia_s=registro.get(
            "latencia_ponta_a_ponta_s" if formato_log else "latencia_s", 0.0
        ),
        latencia_a_quente=registro.get("latencia_a_quente", True),
        tokens_entrada=registro.get("tokens_entrada", 0),
        tokens_saida=registro.get("tokens_saida", 0),
        modelo=registro.get("modelo", ""),
        erro=registro.get("erro"),
        run_id=registro.get("run_id", ""),
        fingerprint=registro.get("fingerprint", ""),
    )
    _validar_invariantes_resultado_item(item)
    return item


def _carregar_checkpoint(
    caminho: Path, fingerprint: str | None = None
) -> list[ResultadoItem]:
    por_tentativa: dict[tuple[str, str, Estrategia], ResultadoItem] = {}
    for registro in _linhas_jsonl_relevantes(caminho, fingerprint, "Checkpoint"):
        try:
            item = _item_de_registro(registro, formato_log=False)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Checkpoint inválido em {caminho}: {exc}"
            ) from exc
        identidade = (item.run_id, item.pergunta_id, item.estrategia)
        anterior = por_tentativa.get(identidade)
        if anterior is not None and anterior != item:
            raise ValueError("Checkpoint contém tentativas duplicadas conflitantes.")
        por_tentativa[identidade] = item
    return list(por_tentativa.values())


def _carregar_itens_auditados(
    dir_logs: Path, fingerprint: str
) -> list[ResultadoItem]:
    """Lê o journal RNF08 para recuperar item cujo checkpoint falhou."""
    por_tentativa: dict[tuple[str, str, Estrategia], ResultadoItem] = {}
    if not dir_logs.exists():
        return []
    for caminho in sorted(dir_logs.glob("*.jsonl")):
        for registro in _linhas_jsonl_relevantes(
            caminho, fingerprint, "Log RNF08"
        ):
            if registro.get("evento") == "reconciliacao_chamada_orfa":
                continue
            try:
                item = _item_de_registro(registro, formato_log=True)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Log RNF08 inválido em {caminho}: {exc}"
                ) from exc
            identidade = (item.run_id, item.pergunta_id, item.estrategia)
            anterior = por_tentativa.get(identidade)
            if anterior is not None and anterior != item:
                raise ValueError("Logs RNF08 contêm tentativas duplicadas conflitantes.")
            por_tentativa[identidade] = item
    return list(por_tentativa.values())


def _registro_execucao(
    pergunta: PerguntaPadrao,
    item: ResultadoItem,
    provedor: str,
    custo_acumulado: float,
    componentes_fingerprint: dict,
) -> dict:
    _validar_invariantes_resultado_item(item)
    return {
        "run_id": item.run_id,
        "fingerprint": item.fingerprint,
        "fingerprint_componentes": componentes_fingerprint,
        "pergunta_id": pergunta.id,
        "pergunta": redigir_dados_pessoais(pergunta.pergunta),
        "resposta_esperada": redigir_dados_pessoais(pergunta.resposta_esperada),
        "conjunto": pergunta.conjunto,
        "categoria": pergunta.categoria,
        "estrategia": item.estrategia.value,
        "provedor": provedor,
        "modelo": item.modelo,
        "versao_prompt": VERSAO_PROMPT,
        "versao_avaliacao": VERSAO_AVALIACAO,
        "temperatura": 0.0,
        "top_k": RECALL_K,
        "tokens_entrada": item.tokens_entrada,
        "tokens_saida": item.tokens_saida,
        "resposta": _serializar_resposta(item.resposta),
        "chunks_recuperados": [
            _serializar_recuperado(resultado) for resultado in item.recuperados
        ],
        "recall_ok": item.recall_ok,
        "exatidao_ok": item.exatidao_ok,
        "recusa_correta": item.recusa_correta,
        "custo_usd": item.custo_usd,
        "custo_observado_usd": item.custo_observado_usd,
        "custo_estimado_falhas_usd": item.custo_estimado_falhas_usd,
        "n_chamadas": item.n_chamadas,
        "n_chamadas_sem_telemetria": item.n_chamadas_sem_telemetria,
        "call_ids": list(item.call_ids),
        "custo_acumulado_usd": custo_acumulado,
        "latencia_ponta_a_ponta_s": item.latencia_s,
        "latencia_a_quente": item.latencia_a_quente,
        "erro": item.erro,
    }


def _media_binaria(valores: list[bool | None]) -> float | None:
    definidos = [valor for valor in valores if valor is not None]
    if not definidos:
        return None
    return sum(definidos) / len(definidos)


def consolidar_metricas(
    itens: list[ResultadoItem],
    *,
    tentativas: list[ResultadoItem] | None = None,
) -> dict[Estrategia, MetricasEstrategia]:
    """Agrega sucessos e contabiliza separadamente todas as tentativas."""
    metricas: dict[Estrategia, MetricasEstrategia] = {}
    tentativas = itens if tentativas is None else tentativas
    presentes = {item.estrategia for item in itens}
    for estrategia in Estrategia:
        if estrategia not in presentes:
            continue
        grupo = [item for item in itens if item.estrategia == estrategia]
        grupo_tentativas = [
            item for item in tentativas if item.estrategia == estrategia
        ]
        perguntas_com_sucesso = {
            item.pergunta_id for item in grupo if item.erro is None
        }
        erros_historicos = [
            item for item in grupo_tentativas if item.erro is not None
        ]
        erros_pendentes = {
            item.pergunta_id
            for item in erros_historicos
            if item.pergunta_id not in perguntas_com_sucesso
        }
        latencias = sorted(
            item.latencia_s for item in grupo if item.latencia_a_quente
        )
        indice_p95 = (
            max(0, math.ceil(0.95 * len(latencias)) - 1)
            if latencias
            else None
        )
        custos = [
            item.custo_usd
            for item in grupo_tentativas
            if item.custo_usd is not None
        ]
        custo_conservador = (
            sum(custos) / len(grupo)
            if len(custos) == len(grupo_tentativas)
            else None
        )
        custos_observados = [
            item.custo_observado_usd
            for item in grupo_tentativas
            if item.custo_observado_usd is not None
        ]
        custo_observado = (
            sum(custos_observados) / len(grupo)
            if custos_observados
            else None
        )
        metricas[estrategia] = MetricasEstrategia(
            estrategia=estrategia,
            recall_at_5=_media_binaria([item.recall_ok for item in grupo]),
            exatidao_numerica=_media_binaria(
                [item.exatidao_ok for item in grupo]
            ),
            taxa_recusa_correta=_media_binaria(
                [item.recusa_correta for item in grupo]
            ),
            custo_medio_usd=custo_conservador,
            custo_conservador_medio_usd=custo_conservador,
            custo_observado_medio_usd=custo_observado,
            latencia_media_s=(sum(latencias) / len(latencias)) if latencias else None,
            latencia_p95_s=(
                latencias[indice_p95] if indice_p95 is not None else None
            ),
            n_json_invalido=sum(
                1
                for item in grupo
                if item.resposta is not None and item.resposta.json_invalido
            ),
            n_erros=len(erros_pendentes),
            n_erros_pendentes=len(erros_pendentes),
            n_erros_historicos=len(erros_historicos),
            n_itens=len(grupo),
            n_tentativas=len(grupo_tentativas),
            n_tentativas_sem_telemetria=sum(
                item.custo_observado_usd is None for item in grupo_tentativas
            ),
            n_chamadas=sum(item.n_chamadas for item in grupo_tentativas),
            n_chamadas_sem_telemetria=sum(
                item.n_chamadas_sem_telemetria for item in grupo_tentativas
            ),
            n_itens_latencia_a_quente=len(latencias),
        )
    return metricas


def _serializar_metrica_estrategia(metrica: MetricasEstrategia) -> dict:
    """Representação canônica usada tanto na gravação quanto na auditoria."""
    return {
        "recall_at_5": metrica.recall_at_5,
        "exatidao_numerica": metrica.exatidao_numerica,
        "taxa_recusa_correta": metrica.taxa_recusa_correta,
        "custo_medio_usd": metrica.custo_medio_usd,
        "custo_conservador_medio_usd": metrica.custo_conservador_medio_usd,
        "custo_observado_medio_usd": metrica.custo_observado_medio_usd,
        "latencia_media_s": metrica.latencia_media_s,
        "latencia_p95_s": metrica.latencia_p95_s,
        "n_json_invalido": metrica.n_json_invalido,
        "n_erros": metrica.n_erros,
        "n_erros_pendentes": metrica.n_erros_pendentes,
        "n_erros_historicos": metrica.n_erros_historicos,
        "n_itens": metrica.n_itens,
        "n_tentativas": metrica.n_tentativas,
        "n_tentativas_sem_telemetria": metrica.n_tentativas_sem_telemetria,
        "n_chamadas": metrica.n_chamadas,
        "n_chamadas_sem_telemetria": metrica.n_chamadas_sem_telemetria,
        "n_itens_latencia_a_quente": metrica.n_itens_latencia_a_quente,
    }


def _escrita_json_atomica(caminho: Path, conteudo: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporario.replace(caminho)


def hash_json_canonico(conteudo: object) -> str:
    """SHA-256 do conteúdo JSON, independente de espaços/ordem de chaves."""
    canonico = json.dumps(
        conteudo,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def validar_metricas_teste_automaticas(
    metricas: dict,
    *,
    status_esperados: set[str] | frozenset[str],
    exigir_auditorias: bool = False,
) -> dict:
    """Valida o contrato publicável comum à auditoria e ao Streamlit."""
    if not isinstance(metricas, dict) or not isinstance(metricas.get("_meta"), dict):
        raise ValueError("Métricas de teste não possuem _meta válido.")
    meta = metricas["_meta"]
    fingerprint = meta.get("fingerprint")
    if (
        not isinstance(fingerprint, str)
        or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
    ):
        raise ValueError("Fingerprint das métricas de teste é inválido.")
    componentes = meta.get("fingerprint_componentes")
    if (
        not isinstance(componentes, dict)
        or meta.get("fingerprint_componentes_sha256")
        != hash_json_canonico(componentes)
        or hash_json_canonico(componentes) != fingerprint
    ):
        raise ValueError("Manifesto material não corresponde ao fingerprint.")
    if meta.get("status") not in status_esperados:
        raise ValueError("Status das métricas de teste não permite esta operação.")
    if (
        meta.get("avaliacao_automatica") != "completa"
        or meta.get("recall_k") != RECALL_K
        or meta.get("temperatura") != 0.0
    ):
        raise ValueError("Métricas não seguem o protocolo automático final.")
    estrategia = meta.get("estrategia_demo_e_auditoria")
    try:
        estrategia_enum = Estrategia(estrategia)
    except (TypeError, ValueError) as exc:
        raise ValueError("Estratégia de demo/auditoria ausente ou inválida.") from exc
    if estrategia_enum == Estrategia.CLOSED_BOOK:
        raise ValueError("Demo e auditoria exigem uma estratégia com recuperação.")
    provedor = meta.get("provedor_llm")
    if not isinstance(provedor, str) or not provedor.strip():
        raise ValueError("Provedor LLM da rodada final não foi registrado.")
    run_ids = meta.get("run_ids")
    if (
        not isinstance(run_ids, list)
        or not run_ids
        or len(run_ids) != len(set(run_ids))
        or any(not isinstance(run_id, str) or not run_id.strip() for run_id in run_ids)
    ):
        raise ValueError("Métricas de teste não possuem run_ids auditáveis.")
    for estrategia_final in Estrategia:
        registro = metricas.get(estrategia_final.value)
        campos_scores = {
            "recall_at_5",
            "exatidao_numerica",
            "taxa_recusa_correta",
        }
        campos_valores = {
            "custo_medio_usd",
            "custo_conservador_medio_usd",
            "custo_observado_medio_usd",
            "latencia_media_s",
            "latencia_p95_s",
        }
        campos_contagens = {
            "n_json_invalido",
            "n_erros",
            "n_erros_pendentes",
            "n_erros_historicos",
            "n_itens",
            "n_tentativas",
            "n_tentativas_sem_telemetria",
            "n_chamadas",
            "n_chamadas_sem_telemetria",
            "n_itens_latencia_a_quente",
        }
        if (
            not isinstance(registro, dict)
            or set(registro) != campos_scores | campos_valores | campos_contagens
            or type(registro.get("n_itens")) is not int
            or registro["n_itens"] != 45
            or type(registro.get("n_erros")) is not int
            or registro["n_erros"] != 0
            or type(registro.get("n_erros_pendentes")) is not int
            or registro["n_erros_pendentes"] != 0
            or registro.get("n_erros") != registro.get("n_erros_pendentes")
            or type(registro.get("n_erros_historicos")) is not int
            or registro["n_erros_historicos"] < 0
            or any(
                valor is not None
                and (
                    not isinstance(valor, (int, float))
                    or isinstance(valor, bool)
                    or not math.isfinite(float(valor))
                    or not 0.0 <= float(valor) <= 1.0
                )
                for valor in (registro.get(campo) for campo in campos_scores)
            )
            or any(
                valor is not None
                and (
                    not isinstance(valor, (int, float))
                    or isinstance(valor, bool)
                    or not math.isfinite(float(valor))
                    or float(valor) < 0.0
                )
                for valor in (registro.get(campo) for campo in campos_valores)
            )
            or any(
                type(registro.get(campo)) is not int
                or registro[campo] < 0
                for campo in campos_contagens
            )
            or registro.get("n_json_invalido", 46) > 45
        ):
            raise ValueError(
                "Métricas finais devem conter E0–E3, cada uma com 45 "
                "respostas e zero erros."
            )
    if exigir_auditorias:
        score = meta.get("groundedness_manual_score")
        variacoes = meta.get("estabilidade_perguntas_com_variacao")
        if (
            meta.get("groundedness_manual_15") != "concluida"
            or meta.get("estabilidade_10x3") != "concluida"
            or type(score) not in {int, float}
            or not math.isfinite(score)
            or not 0.90 <= score <= 1.0
            or type(variacoes) is not int
            or not 0 <= variacoes <= 10
        ):
            raise ValueError("Resultados das auditorias finais são inválidos.")
        cache_hash = meta.get("cache_demo_sha256")
        if (
            not isinstance(cache_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", cache_hash) is None
            or type(meta.get("cache_demo_n_itens")) is not int
            or meta["cache_demo_n_itens"] < 0
        ):
            raise ValueError("Hash do cache final está ausente ou inválido.")
    return meta


def _salvar_metricas(
    metricas: dict[Estrategia, MetricasEstrategia],
    caminho: Path,
    *,
    fingerprint: str = "",
    run_id: str = "",
    run_ids: list[str] | None = None,
    conjunto: str = "dev",
    estrategia_demo_e_auditoria: str = "",
    provedor_llm: str = "",
    fingerprint_componentes: dict | None = None,
) -> None:
    run_ids = sorted(set(run_ids or ([run_id] if run_id else [])))
    status = (
        "auditoria_manual_pendente"
        if conjunto == "teste"
        else "repeticao_estabilidade"
        if conjunto == "estabilidade"
        else "desenvolvimento"
    )
    serializavel = {
        "_meta": {
            "fingerprint": fingerprint,
            "consolidation_run_id": run_id,
            "run_id": run_ids[0] if len(run_ids) == 1 else None,
            "run_ids": run_ids,
            "status": status,
            "avaliacao_automatica": "completa",
            "groundedness_manual_15": "pendente" if conjunto == "teste" else "nao_aplicavel",
            "estabilidade_10x3": "pendente" if conjunto == "teste" else "nao_aplicavel",
            "recall_k": RECALL_K,
            "temperatura": 0.0,
            "estrategia_demo_e_auditoria": estrategia_demo_e_auditoria,
            "provedor_llm": provedor_llm,
            "fingerprint_componentes": fingerprint_componentes or {},
            "fingerprint_componentes_sha256": hash_json_canonico(
                fingerprint_componentes or {}
            ),
            "definicao_custo_usd": (
                "custo observado da tentativa bem-sucedida mais o limite "
                "conservador das tentativas transitórias sem telemetria"
            ),
        }
    }
    serializavel.update(
        {
            estrategia.value: _serializar_metrica_estrategia(metrica)
            for estrategia, metrica in metricas.items()
        }
    )
    _escrita_json_atomica(caminho, serializavel)


def _construir_cache_demo(
    perguntas: list[PerguntaPadrao],
    itens: list[ResultadoItem],
    provedor: str,
    *,
    estrategia_demo: Estrategia,
    fingerprint: str = "",
    run_id: str = "",
    conjunto: str = "teste",
) -> dict[str, dict]:
    """Publica somente respostas com validação automática suficiente.

    Comparativas e qualitativas não têm verificador automático de conteúdo;
    portanto não entram no cache por simples ausência de erro.
    """
    por_id = {pergunta.id: pergunta for pergunta in perguntas}
    cache: dict[str, dict] = {}
    if estrategia_demo == Estrategia.CLOSED_BOOK:
        return cache

    for item in itens:
        pergunta = por_id.get(item.pergunta_id)
        if (
            pergunta is None
            or item.estrategia != estrategia_demo
            or item.erro is not None
            or item.resposta is None
            or item.resposta.json_invalido
            or pergunta.categoria in ("comparativa", "qualitativa")
        ):
            continue
        validado = (
            pergunta.categoria == "factual"
            and item.recall_ok is True
            and item.exatidao_ok is True
        ) or (
            pergunta.categoria == "adversarial"
            and item.recusa_correta is True
            and item.resposta.recusa is True
        )
        if not validado:
            continue
        if item.resposta.recusa:
            conteudo = (
                "**Recusa (RN02):** "
                + (item.resposta.motivo_recusa or "sem evidência no corpus.")
            )
        else:
            conteudo = item.resposta.resposta or "—"
        citacoes = [asdict(citacao) for citacao in item.resposta.citacoes]
        fontes = [
            f"{citacao['empresa']} · {citacao['documento']} · "
            f"{citacao['trimestre']} · pág. {citacao['pagina']}"
            for citacao in citacoes
        ]
        trechos_recuperados = [
            f"{r.chunk.empresa} · {r.chunk.documento} · "
            f"págs. {r.chunk.pagina_inicio}–{r.chunk.pagina_fim}"
            for r in item.recuperados
        ]
        pergunta_cache = redigir_dados_pessoais(pergunta.pergunta)
        if pergunta_cache in cache:
            raise ValueError("Redação de PII produziu perguntas duplicadas no cache.")
        cache[pergunta_cache] = {
            "pergunta_id": pergunta.id,
            "resposta": redigir_dados_pessoais(conteudo),
            "fontes": fontes,
            "citacoes": citacoes,
            "trechos_recuperados": trechos_recuperados,
            "provedor": provedor,
            "modelo": item.modelo,
            "gabarito": redigir_dados_pessoais(pergunta.resposta_esperada),
            "fingerprint": fingerprint,
            "run_id": item.run_id or run_id,
            "estrategia": estrategia_demo.value,
            "conjunto": conjunto,
            "validacao_automatica": True,
        }
    return cache


def _salvar_cache_demo(
    config: Config,
    perguntas: list[PerguntaPadrao],
    itens: list[ResultadoItem],
    provedor: str,
    dir_saida: Path,
    *,
    fingerprint: str = "",
    run_id: str = "",
    conjunto: str = "teste",
) -> None:
    cache = _construir_cache_demo(
        perguntas,
        itens,
        provedor,
        estrategia_demo=Estrategia(config.estrategia_padrao),
        fingerprint=fingerprint,
        run_id=run_id,
        conjunto=conjunto,
    )
    nome_cache = (
        "respostas_cacheadas.json"
        if conjunto == "teste"
        else "respostas_cacheadas_dev.json"
    )
    caminho_cache = dir_saida / nome_cache
    _escrita_json_atomica(caminho_cache, cache)
