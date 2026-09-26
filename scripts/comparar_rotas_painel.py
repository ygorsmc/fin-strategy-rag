#!/usr/bin/env python3
"""Compara as três rotas de consulta ao painel, sobre as mesmas perguntas.

1. **determinística** (`app_streamlit.responder_estruturada_se_couber`) — casa a
   pergunta contra um vocabulário fechado de dez expressões, sem LLM.
2. **intenção única** (`src.intencao_consulta`) — o LLM extrai UMA intenção por
   pergunta (companhias, conceito, trimestres, operação) e o SQL sai com
   `cd_cvm IN (...)`.
3. **plano de células** (`src.plano_consulta`) — o LLM devolve, na mesma única
   chamada, uma lista de consultas atômicas, uma por (companhia, conceito,
   período). Cada célula vira seu próprio `SELECT`.

Nas três, o SQL é montado por template e a aritmética acontece em Python: o
modelo nunca escreve SQL, nunca vê número e nunca escolhe conta.

O ponto da comparação não é eleger uma vencedora, e sim medir onde uma rota
ALCANÇA o que a outra não alcançava, onde duas respondem e DIVERGEM (o caso
perigoso, que vira alarme) e quanto custa a diferença.

Chamada paga: exige `--permitir-api-paga`, como qualquer execução com custo.
O dry-run (padrão) roda só a rota determinística e imprime o que seria pedido.

    python scripts/comparar_rotas_painel.py
    python scripts/comparar_rotas_painel.py --permitir-api-paga
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.config import carregar_config  # noqa: E402
from src.cobertura import carregar_indice_cobertura, formatar_reais  # noqa: E402
from src.dados_estruturados import executar_sql  # noqa: E402
from src.intencao_consulta import (  # noqa: E402
    ErroDeIntencao,
    graos_ambiguos,
    interpretar,
    linhas_de,
    montar_sql,
    prompt_interprete,
    validar,
    validar_sql_da_rota,
    _texto_json,
)
from src.plano_consulta import (  # noqa: E402
    CacheDeCelulas,
    assinatura_painel,
    executar_plano,
    interpretar_plano,
    prompt_plano,
    redigir_resposta,
    validar_plano,
)

# Cada pergunta declara o que ela existe para testar. As quatro primeiras são o
# terreno onde a rota determinística já funciona (controle: a nova não pode
# piorá-lo); as demais são as lacunas medidas em 2026-09-20.
PERGUNTAS: tuple[tuple[str, str], ...] = (
    ("canônica", "Qual foi o lucro líquido do Itaú no 3T2025?"),
    ("canônica", "Qual foi o patrimônio líquido do Bradesco no 2T2025?"),
    ("cobertura parcial", "Qual foi o lucro do Banco Inter no 3T2025?"),
    ("recusa (RN12)", "Qual foi o lucro do Nubank no 3T2025?"),
    ("derivado (RN10)", "Qual foi o lucro líquido do Banco do Brasil no 4T2025?"),
    ("comparação", "Qual dos cinco bancos teve o maior lucro no 3T2025?"),
    ("comparação", "Entre Itaú e Santander, quem lucrou mais no 2T2025?"),
    ("variação", "Quanto o lucro do Itaú cresceu do 3T2025 para o 4T2025?"),
    ("paráfrase", "Me diga quanto o Bradesco ganhou de lucro no terceiro trimestre de 2025"),
    ("sem período", "Qual o lucro do Santander?"),
    ("fora do vocabulário", "Qual foi o índice de Basileia do Itaú no 3T2025?"),
    ("deferência ao release", "Segundo a análise gerencial do Itaú, qual foi o resultado recorrente no 2T2025?"),
)


def rota_deterministica(pergunta: str) -> dict:
    """A rota atual da interface, sem LLM."""
    import app_streamlit as app

    item = app.responder_estruturada_se_couber(pergunta)
    if item is None:
        return {"atendeu": False, "resposta": "(encaminhou ao fluxo documental)"}
    return {
        "atendeu": True,
        "resposta": item["resposta"],
        "valores": {
            f"{f['cd_cvm']}·{f['trimestre']}": f["valor"]
            for f in (item.get("fatos") or [])
        },
    }


def rota_interpretada(pergunta: str, indice, config, provedor) -> dict:
    """LLM extrai intenção; SQL por template; aritmética em Python."""
    resposta_llm = provedor.gerar_texto(
        prompt_interprete(), f"Pergunta: {pergunta}", temperatura=0.0
    )
    custo = float(resposta_llm.uso.custo_usd or 0.0)
    try:
        bruta = interpretar(_texto_json(resposta_llm.texto))
        intencao = validar(bruta, indice, pergunta)
    except ErroDeIntencao as erro:
        return {
            "atendeu": False,
            "resposta": f"(recusa da intenção) {erro}",
            "custo_usd": custo,
        }

    if intencao.ambiguas:
        termos = ", ".join(intencao.ambiguas)
        return {
            "atendeu": True,
            "resposta": f"Desambiguação necessária (RN11) para: {termos}",
            "custo_usd": custo,
            "valores": {},
        }

    sql = validar_sql_da_rota(montar_sql(intencao))
    resultado = executar_sql(sql, config, None)
    linhas = linhas_de(resultado.colunas, resultado.linhas)
    if not linhas:
        return {
            "atendeu": True,
            "resposta": "O painel não traz esse conceito para o período pedido.",
            "custo_usd": custo,
            "valores": {},
            "sql": sql,
        }

    ambiguos = graos_ambiguos(linhas)
    if ambiguos:
        grafia = "; ".join(f"{c} em {t}" for c, t in ambiguos)
        return {
            "atendeu": True,
            "resposta": (
                "Recusa: o painel tem mais de um valor para o mesmo grão "
                f"({grafia}). Escolher um em silêncio seria adivinhar."
            ),
            "custo_usd": custo,
            "valores": {},
            "sql": sql,
        }

    valores = {
        f"{l.cd_cvm}·{l.trimestre}": formatar_reais(l.valor_reais) for l in linhas
    }
    texto = _redigir(intencao, linhas)
    return {
        "atendeu": True,
        "resposta": texto,
        "custo_usd": custo,
        "valores": valores,
        "sql": sql,
        "intencao": {
            "conceito": intencao.conceito,
            "codigos": list(intencao.codigos),
            "trimestres": list(intencao.trimestres),
            "operacao": intencao.operacao,
        },
    }


def _marca(linha) -> str:
    partes = []
    if linha.origem != "arquivado":
        partes.append(linha.origem)
    if linha.corrigido:
        partes.append("corrigido")
    return f" ({', '.join(partes)})" if partes else ""


def _redigir(intencao, linhas) -> str:
    """Aritmética e redação em Python: o modelo não vê número nenhum."""
    if intencao.operacao == "comparacao":
        ordenadas = sorted(linhas, key=lambda l: l.valor_reais, reverse=True)
        topo = ordenadas[0]
        corpo = "; ".join(
            f"{l.denom_social} {formatar_reais(l.valor_reais)}{_marca(l)}"
            for l in ordenadas
        )
        return f"Maior: {topo.denom_social}. Ordem decrescente: {corpo}."
    if intencao.operacao == "variacao" and len(linhas) >= 2:
        ordenadas = sorted(linhas, key=lambda l: (l.cd_cvm, l.trimestre))
        antes, depois = ordenadas[0], ordenadas[-1]
        delta = depois.valor_reais - antes.valor_reais
        pct = (delta / abs(antes.valor_reais) * 100) if antes.valor_reais else None
        variacao = f"{pct:+.1f}%".replace(".", ",") if pct is not None else "n/d"
        derivado = " Valor derivado envolvido (RN10)." if any(
            l.origem != "arquivado" for l in ordenadas
        ) else ""
        return (
            f"{antes.denom_social}: {antes.trimestre} "
            f"{formatar_reais(antes.valor_reais)}{_marca(antes)} → "
            f"{depois.trimestre} {formatar_reais(depois.valor_reais)}"
            f"{_marca(depois)}. Variação {variacao} "
            f"({formatar_reais(delta)}).{derivado}"
        )
    return "; ".join(
        f"{l.denom_social} em {l.trimestre}: "
        f"{formatar_reais(l.valor_reais)}{_marca(l)}"
        for l in linhas
    )


# Um cache por execução do arnês: mede o efeito real sobre 12 perguntas que se
# sobrepõem em companhia e trimestre, sem persistir nada entre execuções.
_CACHE = CacheDeCelulas(assinatura_painel(carregar_config().duckdb_path))


def rota_planejada(pergunta: str, indice, config, provedor) -> dict:
    """Uma chamada ao LLM devolve N consultas atômicas; cada uma vira um SELECT."""
    resposta_llm = provedor.gerar(
        prompt_plano(), f"Pergunta: {pergunta}", temperatura=0.0
    )
    custo = float(resposta_llm.uso.custo_usd or 0.0)
    try:
        bruto = interpretar_plano(_texto_json(resposta_llm.texto))
        plano = validar_plano(bruto, indice, pergunta)
    except ErroDeIntencao as erro:
        return {
            "atendeu": False,
            "resposta": f"(recusa do plano) {erro}",
            "custo_usd": custo,
        }

    respondidas = executar_plano(
        plano,
        lambda sql: (lambda r: (r.colunas, r.linhas))(
            executar_sql(sql, config, None)
        ),
        _CACHE,
    )

    valores = {
        f"{r.celula.cd_cvm}·{l.trimestre}": formatar_reais(l.valor_reais)
        for r in respondidas
        for l in r.linhas
    }
    return {
        "atendeu": True,
        "resposta": redigir_resposta(plano, respondidas),
        "custo_usd": custo,
        "valores": valores,
        "n_celulas": len(plano.celulas),
        "n_pendentes": len(plano.pendentes),
        "celulas": [
            {
                "termo": r.celula.termo,
                "cd_cvm": r.celula.cd_cvm,
                "conceito": r.celula.conceito,
                "trimestre": r.celula.trimestre or None,
                "n_linhas": len(r.linhas),
                "sql": r.celula.sql,
            }
            for r in respondidas
        ],
        "pendentes": [
            {"termo": p.termo, "estado": p.estado, "candidatas": list(p.candidatas)}
            for p in plano.pendentes
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--permitir-api-paga", action="store_true")
    parser.add_argument(
        "--saida",
        default="artefatos/comparacao_rotas_painel.json",
        help="onde gravar o resultado completo",
    )
    args = parser.parse_args()

    config = carregar_config()
    indice = carregar_indice_cobertura(config)
    provedor = None
    if args.permitir_api_paga:
        from src.geracao import fabricar_provedor_llm

        provedor = fabricar_provedor_llm(config)

    registros = []
    custo_total = 0.0
    for categoria, pergunta in PERGUNTAS:
        det = rota_deterministica(pergunta)
        if provedor is None:
            ausente = {"atendeu": None, "resposta": "(dry-run: sem chamada paga)"}
            llm, plano = dict(ausente), dict(ausente)
        else:
            llm = _protegido(rota_interpretada, pergunta, indice, config, provedor)
            plano = _protegido(rota_planejada, pergunta, indice, config, provedor)
        custo_total += float(llm.get("custo_usd") or 0.0)
        custo_total += float(plano.get("custo_usd") or 0.0)

        divergencias = {
            "det×llm": _divergencia(det, llm),
            "det×plano": _divergencia(det, plano),
            "llm×plano": _divergencia(llm, plano),
        }
        divergencias = {k: v for k, v in divergencias.items() if v}
        registros.append(
            {
                "categoria": categoria,
                "pergunta": pergunta,
                "deterministica": det,
                "interpretada": llm,
                "planejada": plano,
                "valores_divergentes": divergencias or None,
            }
        )
        print(f"\n■ [{categoria}] {pergunta}")
        print(f"  determinística: {_resumo(det)}")
        print(f"  intenção única: {_resumo(llm)}")
        print(f"  plano células:  {_resumo(plano)}")
        if plano.get("n_celulas"):
            print(
                f"                  ({plano['n_celulas']} células, "
                f"{plano.get('n_pendentes', 0)} pendentes)"
            )
        for par, chaves in divergencias.items():
            print(f"  ⚠ DIVERGÊNCIA de valor [{par}] em: {chaves}")

    saida = RAIZ / args.saida
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(
        json.dumps(
            {
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "modelo": getattr(provedor, "_modelo", None)
                or config.llm_provider,
                "custo_total_usd": round(custo_total, 6),
                "n_perguntas": len(PERGUNTAS),
                "rotas": ["deterministica", "interpretada", "planejada"],
                "chamadas_llm_por_pergunta": 0 if provedor is None else 2,
                "registros": registros,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\ncusto total: US$ {custo_total:.4f} · gravado em {args.saida}")
    return 0


def _protegido(funcao, pergunta, indice, config, provedor) -> dict:
    """Uma pergunta que explode não derruba a comparação inteira."""
    try:
        return funcao(pergunta, indice, config, provedor)
    except Exception as erro:
        return {
            "atendeu": False,
            "resposta": f"(erro) {type(erro).__name__}: {erro}",
            "custo_usd": 0.0,
        }


def _divergencia(esquerda: dict, direita: dict) -> list[str]:
    """Chaves (companhia·trimestre) em que as duas rotas dão valores diferentes.

    É o alarme central da comparação: duas rotas que respondem e discordam
    significam que pelo menos uma está errada, e nenhuma delas avisa o usuário.
    """
    if not (esquerda.get("atendeu") and direita.get("atendeu")):
        return []
    a, b = esquerda.get("valores") or {}, direita.get("valores") or {}
    return sorted(k for k in set(a) & set(b) if a[k] != b[k])


def _resumo(rota: dict) -> str:
    texto = (rota.get("resposta") or "").replace("\n", " ")
    return texto[:160] + ("…" if len(texto) > 160 else "")


if __name__ == "__main__":
    raise SystemExit(main())
