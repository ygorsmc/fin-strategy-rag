"""Auditoria manual de groundedness e estabilidade do benchmark final.

Este módulo nunca chama modelos. Ele prepara uma amostra fixa ligada ao
fingerprint, consolida três repetições já executadas e só promove as métricas
quando os dois contratos de auditoria estiverem completos.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack, contextmanager
from functools import wraps
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Collection

from src.avaliacao import (
    PerguntaPadrao,
    _carregar_checkpoint,
    _construir_cache_demo,
    _escrita_json_atomica,
    _serializar_recuperado,
    _serializar_resposta,
    _serializar_metrica_estrategia,
    _validar_invariantes_resultado_item,
    _validar_modelos_sucesso,
    _validar_conjunto_teste_final,
    carregar_conjunto_padrao,
    consolidar_metricas,
    avaliar_exatidao_numerica,
    avaliar_recall_at_k,
    avaliar_recusa,
    hash_json_canonico,
    validar_estado_material_atual,
    validar_metricas_teste_automaticas,
)
from src.config import DIR_INDICE_VETORIAL, Config
from src.geracao import (
    _escopo_solicitado_esta_coberto,
    citacoes_sao_subconjunto,
    numeros_da_resposta_estao_fundamentados,
)
from src.bloqueio import bloqueio_compartilhado, bloqueio_exclusivo
from src.recuperacao import Estrategia

COTAS_GROUNDEDNESS = {
    "factual": 4,
    "comparativa": 4,
    "qualitativa": 4,
    "adversarial": 3,
}
COTAS_ESTABILIDADE = {
    "factual": 3,
    "comparativa": 3,
    "qualitativa": 2,
    "adversarial": 2,
}


@contextmanager
def _bloquear_snapshot_avaliacao(
    dir_resultados: Path,
    *,
    incluir_estabilidade: bool,
):
    """Impede que checkpoints/métricas mudem durante uma decisão de auditoria."""
    dir_resultados = Path(dir_resultados)
    nomes = [".avaliacao_teste.lock"]
    if incluir_estabilidade:
        nomes.extend(
            f".avaliacao_teste_estabilidade_{repeticao}.lock"
            for repeticao in (1, 2, 3)
        )
    with ExitStack() as pilha:
        caminho_lock_indice = (
            DIR_INDICE_VETORIAL.parent / f".{DIR_INDICE_VETORIAL.name}.lock"
        )
        pilha.enter_context(
            bloqueio_compartilhado(
                caminho_lock_indice,
                f"o snapshot do índice {DIR_INDICE_VETORIAL}",
            )
        )
        for nome in nomes:
            pilha.enter_context(
                bloqueio_exclusivo(
                    dir_resultados / nome,
                    "o snapshot da avaliação final",
                )
            )
        yield


def _com_snapshot_bloqueado(*, incluir_estabilidade: bool):
    def decorador(funcao):
        @wraps(funcao)
        def envolta(config: Config, dir_resultados: Path, *args, **kwargs):
            with _bloquear_snapshot_avaliacao(
                dir_resultados,
                incluir_estabilidade=incluir_estabilidade,
            ):
                return funcao(config, dir_resultados, *args, **kwargs)

        return envolta

    return decorador


def _carregar_json_objeto(caminho: Path, descricao: str) -> dict:
    try:
        objeto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"{descricao} inválido em {caminho}: {type(exc).__name__}"
        ) from exc
    if not isinstance(objeto, dict):
        raise ValueError(f"{descricao} deve ser um objeto JSON.")
    return objeto


def selecionar_ids_estratificados(
    perguntas: list[PerguntaPadrao],
    fingerprint: str,
    cotas: dict[str, int],
) -> list[str]:
    """Seleção fixa, estratificada e reproduzível a partir do fingerprint."""
    if len(fingerprint) != 64:
        raise ValueError("Fingerprint deve ser SHA-256 hexadecimal.")
    selecionados: list[str] = []
    for categoria, quantidade in cotas.items():
        candidatas = [p for p in perguntas if p.categoria == categoria]
        if len(candidatas) < quantidade:
            raise ValueError(
                f"Categoria {categoria!r} não possui {quantidade} perguntas."
            )
        candidatas.sort(
            key=lambda p: (
                hashlib.sha256(
                    f"{fingerprint}:{categoria}:{p.id}".encode()
                ).hexdigest(),
                p.id,
            )
        )
        selecionados.extend(p.id for p in candidatas[:quantidade])
    return selecionados


def _contexto_final(
    config: Config, caminho_metricas: Path
) -> tuple[list[PerguntaPadrao], dict, str, Estrategia, str]:
    perguntas = [
        p for p in carregar_conjunto_padrao(config) if p.conjunto == "teste"
    ]
    _validar_conjunto_teste_final(perguntas)
    metricas = _carregar_json_objeto(caminho_metricas, "Métricas finais")
    meta = validar_metricas_teste_automaticas(
        metricas,
        status_esperados=frozenset({"auditoria_manual_pendente"}),
    )
    validar_estado_material_atual(
        config,
        perguntas,
        meta["fingerprint_componentes"],
    )
    estrategia = Estrategia(meta["estrategia_demo_e_auditoria"])
    provedor = meta["provedor_llm"]
    if config.estrategia_padrao != estrategia.value:
        raise ValueError(
            "ESTRATEGIA_PADRAO atual diverge da rodada automática final."
        )
    if config.llm_provider != provedor:
        raise ValueError("LLM_PROVIDER atual diverge da rodada automática final.")
    _validar_metricas_contra_checkpoint(
        metricas,
        perguntas,
        meta["fingerprint"],
        caminho_metricas.parent / "checkpoint_teste.jsonl",
        config,
    )
    return perguntas, metricas, meta["fingerprint"], estrategia, provedor


def _validar_metricas_contra_checkpoint(
    metricas: dict,
    perguntas: list[PerguntaPadrao],
    fingerprint: str,
    caminho_checkpoint: Path,
    config: Config,
) -> None:
    """Reconstrói E0–E3 e recusa qualquer resumo editado à mão."""
    itens = _carregar_checkpoint(caminho_checkpoint, fingerprint)
    por_id = {pergunta.id: pergunta for pergunta in perguntas}
    ids_esperados = set(por_id)
    if not itens or any(
        item.pergunta_id not in ids_esperados or not item.run_id
        for item in itens
    ):
        raise ValueError("Checkpoint final contém item fora do benchmark.")
    _validar_modelos_sucesso(itens)
    sucessos: dict[tuple[str, Estrategia], object] = {}
    for item in itens:
        _validar_invariantes_resultado_item(item)
        if item.erro is not None:
            continue
        pergunta = por_id[item.pergunta_id]
        if item.categoria != pergunta.categoria:
            raise ValueError("Categoria do checkpoint diverge do benchmark.")
        recall_esperado = None
        exatidao_esperada = None
        recusa_esperada = None
        if pergunta.categoria in {"factual", "comparativa"}:
            if item.estrategia != Estrategia.CLOSED_BOOK:
                recall_esperado = avaliar_recall_at_k(
                    pergunta, item.recuperados, k=5
                )
            if pergunta.categoria == "factual":
                exatidao_esperada = avaliar_exatidao_numerica(
                    pergunta, item.resposta, config
                )
        elif pergunta.categoria == "adversarial":
            recusa_esperada = avaliar_recusa(pergunta, item.resposta)
        if (
            item.recall_ok is not recall_esperado
            or item.exatidao_ok is not exatidao_esperada
            or item.recusa_correta is not recusa_esperada
        ):
            raise ValueError("Flags automáticas do checkpoint foram adulteradas.")

        resposta = item.resposta
        chunks = [resultado.chunk for resultado in item.recuperados]
        if item.estrategia == Estrategia.CLOSED_BOOK:
            if resposta.citacoes:
                raise ValueError("Closed-book contém citação.")
        elif not resposta.recusa:
            if (
                not resposta.citacoes
                or not citacoes_sao_subconjunto(resposta.citacoes, chunks)
                or not numeros_da_resposta_estao_fundamentados(
                    resposta.resposta or "",
                    resposta.citacoes,
                    chunks,
                    config.tolerancia_numerica_pct,
                    pergunta.pergunta,
                )
                or not _escopo_solicitado_esta_coberto(
                    pergunta.pergunta,
                    resposta.citacoes,
                    config,
                    resposta.resposta or "",
                )
            ):
                raise ValueError("Resposta final viola RN01/RN02.")
        elif resposta.resposta is not None or resposta.citacoes:
            raise ValueError("Recusa final viola o contrato estruturado.")
        chave = (item.pergunta_id, item.estrategia)
        if chave in sucessos:
            raise ValueError("Checkpoint final contém sucesso duplicado.")
        sucessos[chave] = item
    chaves_esperadas = {
        (pergunta_id, estrategia)
        for pergunta_id in ids_esperados
        for estrategia in Estrategia
    }
    if set(sucessos) != chaves_esperadas:
        raise ValueError("Checkpoint final não contém exatamente 45 sucessos E0–E3.")
    reconstruidas = consolidar_metricas(list(sucessos.values()), tentativas=itens)
    for estrategia in Estrategia:
        if metricas.get(estrategia.value) != _serializar_metrica_estrategia(
            reconstruidas[estrategia]
        ):
            raise ValueError(
                f"Métricas de {estrategia.value} divergem do checkpoint final."
            )
    run_ids = sorted({item.run_id for item in itens})
    if run_ids != sorted(metricas["_meta"].get("run_ids", [])):
        raise ValueError("Run IDs das métricas divergem do checkpoint final.")


def _sucessos_da_estrategia(
    caminho_checkpoint: Path,
    fingerprint: str,
    estrategia: Estrategia,
    ids_esperados: Collection[str],
) -> dict[str, object]:
    sucessos: dict[str, object] = {}
    for item in _carregar_checkpoint(caminho_checkpoint, fingerprint):
        if item.estrategia != estrategia or item.erro is not None:
            continue
        if item.pergunta_id in sucessos:
            raise ValueError("Checkpoint contém sucessos duplicados.")
        sucessos[item.pergunta_id] = item
    conjunto_esperado = set(ids_esperados)
    if set(sucessos) != conjunto_esperado:
        raise ValueError(
            "Checkpoint não contém exatamente os IDs congelados da estratégia "
            f"{estrategia.value!r}."
        )
    return sucessos


def _registro_groundedness(pergunta: PerguntaPadrao, item) -> dict:
    registro = {
        "pergunta_id": pergunta.id,
        "categoria": pergunta.categoria,
        "pergunta": pergunta.pergunta,
        "resposta": _serializar_resposta(item.resposta),
        "chunks_citados_e_recuperados": [
            _serializar_recuperado(resultado) for resultado in item.recuperados
        ],
    }
    registro["assinatura_contexto"] = hash_json_canonico(registro)
    return registro


@_com_snapshot_bloqueado(incluir_estabilidade=False)
def preparar_auditoria_final(
    config: Config,
    dir_resultados: Path,
    *,
    caminho_groundedness: Path | None = None,
    caminho_plano_estabilidade: Path | None = None,
) -> tuple[Path, Path]:
    """Gera templates; nunca sobrescreve uma auditoria já preenchida."""
    dir_resultados = Path(dir_resultados)
    caminho_metricas = dir_resultados / "metricas_teste.json"
    perguntas, metricas, fingerprint, estrategia, _ = _contexto_final(
        config, caminho_metricas
    )
    sucessos = _sucessos_da_estrategia(
        dir_resultados / "checkpoint_teste.jsonl",
        fingerprint,
        estrategia,
        {pergunta.id for pergunta in perguntas},
    )
    ids_groundedness = selecionar_ids_estratificados(
        perguntas, fingerprint, COTAS_GROUNDEDNESS
    )
    por_id = {p.id: p for p in perguntas}
    auditoria = {
        "_meta": {
            "fingerprint": fingerprint,
            "estrategia": estrategia.value,
            "metodo_amostra": "sha256 estratificado 4/4/4/3",
            "n": 15,
            "status": "preenchimento_manual_pendente",
        },
        "avaliacoes": [
            {
                **_registro_groundedness(
                    por_id[pergunta_id], sucessos[pergunta_id]
                ),
                "grounded": None,
                "auditor_id": "",
                "data_auditoria": "",
                "observacao": "",
            }
            for pergunta_id in ids_groundedness
        ],
    }
    ids_estabilidade = selecionar_ids_estratificados(
        perguntas, fingerprint, COTAS_ESTABILIDADE
    )
    plano = {
        "_meta": {
            "fingerprint_base": fingerprint,
            "estrategia": estrategia.value,
            "metodo_amostra": "sha256 estratificado 3/3/2/2",
            "n_perguntas": 10,
            "repeticoes": 3,
            "temperatura": 0.0,
            "status": "execucao_pendente",
        },
        "pergunta_ids": ids_estabilidade,
    }
    caminho_groundedness = caminho_groundedness or (
        dir_resultados / "auditoria_groundedness.json"
    )
    caminho_plano_estabilidade = caminho_plano_estabilidade or (
        dir_resultados / "plano_estabilidade.json"
    )
    for caminho in (caminho_groundedness, caminho_plano_estabilidade):
        if caminho.exists():
            raise FileExistsError(
                f"{caminho} já existe; remova-o somente após revisão explícita."
            )
    _escrita_json_atomica(caminho_groundedness, auditoria)
    _escrita_json_atomica(caminho_plano_estabilidade, plano)
    return caminho_groundedness, caminho_plano_estabilidade


def _assinatura_item(item) -> str:
    conteudo = {
        "resposta": _serializar_resposta(item.resposta),
        "citacoes": [
            asdict(citacao)
            for citacao in (item.resposta.citacoes if item.resposta else ())
        ],
    }
    canonico = json.dumps(
        conteudo, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonico.encode()).hexdigest()


def validar_plano_estabilidade(
    config: Config,
    dir_resultados: Path,
    *,
    caminho_plano: Path | None = None,
) -> tuple[list[PerguntaPadrao], str, Estrategia, list[str]]:
    """Valida todo o plano fixo antes de qualquer chamada de estabilidade."""
    dir_resultados = Path(dir_resultados)
    perguntas, _, fingerprint, estrategia, _ = _contexto_final(
        config, dir_resultados / "metricas_teste.json"
    )
    caminho_plano = caminho_plano or dir_resultados / "plano_estabilidade.json"
    plano = _carregar_json_objeto(caminho_plano, "Plano de estabilidade")
    meta = plano.get("_meta")
    ids = plano.get("pergunta_ids")
    esperados = selecionar_ids_estratificados(
        perguntas, fingerprint, COTAS_ESTABILIDADE
    )
    if (
        not isinstance(meta, dict)
        or meta.get("fingerprint_base") != fingerprint
        or meta.get("estrategia") != estrategia.value
        or meta.get("metodo_amostra") != "sha256 estratificado 3/3/2/2"
        or meta.get("n_perguntas") != 10
        or meta.get("repeticoes") != 3
        or meta.get("temperatura") != 0.0
        or meta.get("status") != "execucao_pendente"
        or ids != esperados
    ):
        raise ValueError("Plano de estabilidade diverge do benchmark final.")
    return perguntas, fingerprint, estrategia, esperados


def _construir_relatorio_estabilidade(
    config: Config,
    dir_resultados: Path,
    *,
    caminho_plano: Path | None = None,
) -> dict:
    """Reconstrói o relatório 10×3 a partir das fontes de verdade."""
    dir_resultados = Path(dir_resultados)
    perguntas, fingerprint_base, estrategia, esperados = validar_plano_estabilidade(
        config,
        dir_resultados,
        caminho_plano=caminho_plano,
    )
    metricas_base = _carregar_json_objeto(
        dir_resultados / "metricas_teste.json", "Métricas finais"
    )
    componentes_base = metricas_base["_meta"]["fingerprint_componentes"]
    chaves_variaveis = {"repeticao_estabilidade", "perguntas_selecionadas"}
    base_comparavel = {
        chave: valor
        for chave, valor in componentes_base.items()
        if chave not in chaves_variaveis
    }
    ids_esperados = set(esperados)
    perguntas_repeticao = [
        pergunta for pergunta in perguntas if pergunta.id in ids_esperados
    ]
    perguntas_componentes_esperadas = [
        asdict(pergunta) for pergunta in perguntas_repeticao
    ]
    sucessos_base = _sucessos_da_estrategia(
        dir_resultados / "checkpoint_teste.jsonl",
        fingerprint_base,
        estrategia,
        {pergunta.id for pergunta in perguntas},
    )
    modelos_observados = {
        item.modelo
        for item in sucessos_base.values()
        if isinstance(item.modelo, str) and item.modelo.strip()
    }
    if len(modelos_observados) != 1 or any(
        not isinstance(item.modelo, str) or not item.modelo.strip()
        for item in sucessos_base.values()
    ):
        raise ValueError("Rodada base não possui um único modelo observado.")
    resultados: list[dict] = []
    fingerprints_repeticoes: list[str] = []
    run_ids_repeticoes: list[list[str]] = []
    for repeticao in (1, 2, 3):
        metricas_rep = _carregar_json_objeto(
            dir_resultados / f"metricas_estabilidade_{repeticao}.json",
            f"Métricas da repetição {repeticao}",
        )
        meta_rep = metricas_rep.get("_meta")
        if (
            not isinstance(meta_rep, dict)
            or meta_rep.get("status") != "repeticao_estabilidade"
        ):
            raise ValueError(f"Repetição {repeticao} não está concluída.")
        fingerprint_rep = meta_rep.get("fingerprint")
        componentes_rep = meta_rep.get("fingerprint_componentes")
        componentes_comparaveis = (
            {
                chave: valor
                for chave, valor in componentes_rep.items()
                if chave not in chaves_variaveis
            }
            if isinstance(componentes_rep, dict)
            else None
        )
        if (
            not isinstance(fingerprint_rep, str)
            or not isinstance(componentes_rep, dict)
            or hash_json_canonico(componentes_rep) != fingerprint_rep
            or meta_rep.get("fingerprint_componentes_sha256") != fingerprint_rep
            or componentes_rep.get("repeticao_estabilidade") != repeticao
            or componentes_rep.get("perguntas_selecionadas")
            != perguntas_componentes_esperadas
            or componentes_comparaveis != base_comparavel
            or meta_rep.get("estrategia_demo_e_auditoria") != estrategia.value
            or meta_rep.get("provedor_llm") != config.llm_provider
            or meta_rep.get("recall_k") != 5
            or meta_rep.get("temperatura") != 0.0
            or meta_rep.get("avaliacao_automatica") != "completa"
        ):
            raise ValueError(
                f"Repetição {repeticao} diverge do manifesto material base."
            )
        validar_estado_material_atual(
            config,
            perguntas_repeticao,
            componentes_rep,
            repeticao_estabilidade=repeticao,
        )
        metrica_estrategia = metricas_rep.get(estrategia.value)
        if (
            not isinstance(metrica_estrategia, dict)
            or metrica_estrategia.get("n_itens") != 10
            or metrica_estrategia.get("n_erros") != 0
            or metrica_estrategia.get("n_erros_pendentes") != 0
            or any(
                outra.value in metricas_rep
                for outra in Estrategia
                if outra != estrategia
            )
        ):
            raise ValueError(f"Métricas da repetição {repeticao} são divergentes.")
        fingerprints_repeticoes.append(fingerprint_rep)
        itens = _carregar_checkpoint(
            dir_resultados / f"checkpoint_estabilidade_{repeticao}.jsonl",
            fingerprint_rep,
        )
        if any(item.estrategia != estrategia for item in itens):
            raise ValueError(f"Repetição {repeticao} mistura estratégias.")
        run_ids_meta = meta_rep.get("run_ids")
        if (
            not isinstance(run_ids_meta, list)
            or not run_ids_meta
            or len(run_ids_meta) != len(set(run_ids_meta))
            or any(
                not isinstance(run_id, str) or not run_id.strip()
                for run_id in run_ids_meta
            )
        ):
            raise ValueError(f"Run IDs da repetição {repeticao} são inválidos.")
        run_ids = sorted({item.run_id for item in itens if item.run_id})
        if run_ids != sorted(run_ids_meta):
            raise ValueError(f"Run IDs da repetição {repeticao} divergem.")
        run_ids_repeticoes.append(run_ids)
        por_id = {}
        for item in itens:
            if item.estrategia != estrategia or item.erro is not None:
                continue
            if item.pergunta_id in por_id:
                raise ValueError(
                    f"Repetição {repeticao} contém sucesso duplicado."
                )
            por_id[item.pergunta_id] = item
        if set(por_id) != set(esperados):
            raise ValueError(
                f"Repetição {repeticao} não possui exatamente as 10 respostas."
            )
        if any(
            not isinstance(item.modelo, str) or not item.modelo.strip()
            for item in por_id.values()
        ):
            raise ValueError(
                f"Repetição {repeticao} não registra o modelo observado."
            )
        modelos_observados.update(item.modelo for item in por_id.values())
        resultados.extend(
            {
                "pergunta_id": pergunta_id,
                "repeticao": repeticao,
                "run_id": por_id[pergunta_id].run_id,
                "fingerprint_execucao": fingerprint_rep,
                "assinatura_resposta": _assinatura_item(por_id[pergunta_id]),
            }
            for pergunta_id in esperados
        )
    if len(set(fingerprints_repeticoes)) != 3:
        raise ValueError(
            "As três repetições de estabilidade não são independentes."
        )
    if len(modelos_observados) != 1:
        raise ValueError(
            "Rodada base e repetições de estabilidade misturam modelos "
            f"observados: {sorted(modelos_observados)}."
        )
    run_ids_vistos: set[str] = set()
    for run_ids in run_ids_repeticoes:
        if run_ids_vistos & set(run_ids):
            raise ValueError("As repetições reutilizam run_id entre namespaces.")
        run_ids_vistos.update(run_ids)
    variacoes = {
        pergunta_id: len(
            {
                item["assinatura_resposta"]
                for item in resultados
                if item["pergunta_id"] == pergunta_id
            }
        )
        for pergunta_id in esperados
    }
    return {
        "_meta": {
            "fingerprint_base": fingerprint_base,
            "estrategia": estrategia.value,
            "pergunta_ids": esperados,
            "repeticoes": 3,
            "temperatura": 0.0,
            "status": "concluida",
            "fingerprints_repeticoes": fingerprints_repeticoes,
            "run_ids_repeticoes": run_ids_repeticoes,
            "n_perguntas_com_variacao": sum(
                quantidade > 1 for quantidade in variacoes.values()
            ),
        },
        "variantes_distintas_por_pergunta": variacoes,
        "resultados": resultados,
    }


@_com_snapshot_bloqueado(incluir_estabilidade=True)
def consolidar_estabilidade(
    config: Config,
    dir_resultados: Path,
    *,
    caminho_plano: Path | None = None,
    caminho_saida: Path | None = None,
) -> Path:
    """Consolida 10×3 a partir dos checkpoints independentes."""
    dir_resultados = Path(dir_resultados)
    relatorio = _construir_relatorio_estabilidade(
        config,
        dir_resultados,
        caminho_plano=caminho_plano,
    )
    caminho_saida = caminho_saida or (
        dir_resultados / "auditoria_estabilidade.json"
    )
    _escrita_json_atomica(caminho_saida, relatorio)
    return caminho_saida


@_com_snapshot_bloqueado(incluir_estabilidade=True)
def promover_metricas_auditadas(
    config: Config,
    dir_resultados: Path,
    *,
    caminho_groundedness: Path | None = None,
    caminho_estabilidade: Path | None = None,
) -> dict:
    """Promove atomicamente; meta de groundedness não atingida fica bloqueada."""
    dir_resultados = Path(dir_resultados)
    caminho_metricas = dir_resultados / "metricas_teste.json"
    perguntas, metricas, fingerprint, estrategia, provedor = _contexto_final(
        config, caminho_metricas
    )
    caminho_groundedness = caminho_groundedness or (
        dir_resultados / "auditoria_groundedness.json"
    )
    caminho_estabilidade = caminho_estabilidade or (
        dir_resultados / "auditoria_estabilidade.json"
    )
    groundedness = _carregar_json_objeto(
        caminho_groundedness, "Auditoria de groundedness"
    )
    avaliacoes = groundedness.get("avaliacoes")
    ids_esperados = selecionar_ids_estratificados(
        perguntas, fingerprint, COTAS_GROUNDEDNESS
    )
    if (
        not isinstance(groundedness.get("_meta"), dict)
        or groundedness["_meta"].get("fingerprint") != fingerprint
        or groundedness["_meta"].get("estrategia") != estrategia.value
        or groundedness["_meta"].get("n") != 15
        or not isinstance(avaliacoes, list)
        or [item.get("pergunta_id") for item in avaliacoes] != ids_esperados
    ):
        raise ValueError("Auditoria de groundedness não corresponde à amostra fixa.")
    sucessos = _sucessos_da_estrategia(
        dir_resultados / "checkpoint_teste.jsonl",
        fingerprint,
        estrategia,
        {pergunta.id for pergunta in perguntas},
    )
    por_id = {pergunta.id: pergunta for pergunta in perguntas}
    for item, pergunta_id in zip(avaliacoes, ids_esperados, strict=True):
        esperado = _registro_groundedness(
            por_id[pergunta_id], sucessos[pergunta_id]
        )
        if not isinstance(item, dict) or any(
            item.get(campo) != valor for campo, valor in esperado.items()
        ):
            raise ValueError(
                "Contexto da auditoria de groundedness diverge do checkpoint."
            )
        if (
            type(item.get("grounded")) is not bool
            or not isinstance(item.get("auditor_id"), str)
            or not item["auditor_id"].strip()
            or not isinstance(item.get("data_auditoria"), str)
            or not item["data_auditoria"].strip()
            or not isinstance(item.get("observacao"), str)
        ):
            raise ValueError(
                "Cada item de groundedness exige booleano, auditor_id e data."
            )
        try:
            data = datetime.fromisoformat(
                item["data_auditoria"].replace("Z", "+00:00")
            )
            if data.tzinfo is None:
                raise ValueError
        except ValueError as exc:
            raise ValueError("data_auditoria deve usar formato ISO-8601.") from exc
    score = sum(item["grounded"] for item in avaliacoes) / 15

    estabilidade = _carregar_json_objeto(
        caminho_estabilidade, "Auditoria de estabilidade"
    )
    estabilidade_reconstruida = _construir_relatorio_estabilidade(
        config,
        dir_resultados,
    )
    if estabilidade != estabilidade_reconstruida:
        raise ValueError(
            "Auditoria de estabilidade diverge dos checkpoints e métricas "
            "originais das três repetições."
        )
    meta_estabilidade = estabilidade_reconstruida["_meta"]

    cache_atual = _carregar_json_objeto(
        dir_resultados / "respostas_cacheadas.json",
        "Cache final",
    )
    cache_esperado = _construir_cache_demo(
        perguntas,
        list(sucessos.values()),
        provedor,
        estrategia_demo=estrategia,
        fingerprint=fingerprint,
        conjunto="teste",
    )
    if cache_atual != cache_esperado:
        raise ValueError("Cache final diverge do checkpoint auditado.")

    meta = metricas["_meta"]
    meta["groundedness_manual_15"] = "concluida"
    meta["groundedness_manual_score"] = score
    meta["estabilidade_10x3"] = "concluida"
    meta["estabilidade_perguntas_com_variacao"] = meta_estabilidade.get(
        "n_perguntas_com_variacao"
    )
    meta["cache_demo_sha256"] = hash_json_canonico(cache_atual)
    meta["cache_demo_n_itens"] = len(cache_atual)
    meta["data_promocao_utc"] = datetime.now(timezone.utc).isoformat()
    meta["status"] = (
        "completa" if score >= 0.90 else "auditoria_concluida_meta_nao_atingida"
    )
    _escrita_json_atomica(caminho_metricas, metricas)
    return metricas
