"""Braços A e B do experimento de 5.9.3 — o arnês de medição, não a orquestração.

O braço **A** é um agente único com todas as ferramentas; o **B** é Investigador
+ Auditor com isolamento de contexto. A orquestração dos dois vive em
`src.agentes`; aqui está só o que transforma uma resposta em **medição
comparável** com o braço C:

1. rodar as mesmas 15 perguntas de `conjunto_padrao/conjunto_agentes.csv`, com
   orçamento de ferramenta e de iteração **por pergunta** (5.9.5);
2. apurar acerto pelos **mesmos seis critérios** do braço C — o módulo reusa
   `src.braco_determinista.apurar` de propósito: duas réguas fariam a comparação
   pareada medir a régua, não o braço;
3. registrar por pergunta acerto, custo, latência, chamadas de ferramenta e
   **veredito do Auditor** no formato comum (`RegistroBraco`), em JSONL (RNF08).

## O que muda entre os braços, e o que não pode mudar

Muda só a orquestração: mesmo prompt de investigação, mesma temperatura, mesmo
provedor, mesmas ferramentas, mesmas perguntas, mesma apuração. O braço B
acrescenta uma segunda passagem cujo contexto é montado por código
(`montar_contexto_auditor`) — e é essa a hipótese sob teste.

## Onde a medição de A/B difere da de C, declarado

* **`cobertura`, `comportamento`, `motivo` e `bases` são declarados pelo
  agente**, no vocabulário fechado que o prompt entrega; no braço C eles são
  derivados por código. É a diferença entre um sistema que classifica e outro
  que é classificado — e o gabarito contra o qual os dois são medidos é o mesmo.
* **`tem_valor_publicado`** usa o extrator pt-BR completo, não o regex estrito do
  braço C: o agente escreve "R$ 417,5 milhões" em prosa, e o regex estrito
  deixaria passar como "nenhum valor publicado" — erro na direção errada.
* **`leituras_painel`** conta chamadas de ferramenta que tocam o painel, não
  leituras do leitor de fatos: o agente não usa o `LeitorDeFatos`.
* **`fatos_publicados`** fica vazio: o agente não emite fato estruturado. A
  procedência dele está nas citações e no log de chamadas.

## Honestidade da apuração (idêntica à do braço C)

Dez das 15 perguntas têm `status_gabarito` diferente de `verificado_painel`.
Para elas o braço roda, responde e registra tudo, mas `apuracao` é
`pendente_conferencia_humana` e `acerto` é `None` — nunca `True`, nunca `False`.
A taxa de acerto do resumo é calculada só sobre os apurados, com o denominador
declarado.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from src.agentes import (
    PAPEL_AGENTE_UNICO,
    PAPEL_AUDITOR,
    PAPEL_INVESTIGADOR,
    ControleOrcamento,
    FabricaFerramentas,
    FabricaLLM,
    OrcamentoAgentesExcedidoError,
    RespostaAgente,
    UsoAgente,
    VERSAO_PROMPT_AGENTES,
    fabrica_ferramentas_padrao,
    fabrica_llm_padrao,
    responder_braco_a,
    responder_braco_b,
    valores_monetarios_do_texto,
)
from src.braco_determinista import (
    APURACAO_ERRO,
    APURACAO_PENDENTE,
    BRACO_A,
    BRACO_B,
    DIR_RESULTADOS_AGENTES,
    PerguntaAgentes,
    RegistroBraco,
    ResultadoBraco,
    apurar,
    carregar_conjunto_agentes,
    novo_run_id,
    registrar_resultado,
    resumir,
    salvar_resultado,
)
from src.cobertura import MOTIVO_NA
from src.config import DIR_LOGS_EXECUCOES, Config, carregar_config

# Ferramentas cuja execução lê o painel contábil. `buscar_trechos` fica de fora:
# ela lê o índice documental, que tem outro custo e outra latência.
FERRAMENTAS_DE_PAINEL: frozenset[str] = frozenset(
    {"verificar_cobertura", "consultar_cvm", "calcular_indicadores"}
)

Orquestrador = Callable[..., RespostaAgente]

ORQUESTRADORES: dict[str, Orquestrador] = {
    BRACO_A: responder_braco_a,
    BRACO_B: responder_braco_b,
}


def _entidades_resolvidas(resposta: RespostaAgente) -> tuple[str, ...]:
    """Códigos CVM que as ferramentas efetivamente resolveram na pergunta.

    Sai do resultado das chamadas, não do texto: o que interessa registrar é o
    que o sistema **consultou**, não o que ele disse ter consultado.
    """
    codigos: set[str] = set()

    def percorrer(objeto: Any) -> None:
        if isinstance(objeto, dict):
            for chave, valor in objeto.items():
                if chave == "cd_cvm" and isinstance(valor, str) and valor.strip():
                    codigos.add(valor.strip())
                else:
                    percorrer(valor)
        elif isinstance(objeto, (list, tuple)):
            for item in objeto:
                percorrer(item)

    for chamada in resposta.chamadas:
        percorrer(chamada.resultado)
    return tuple(sorted(codigos))


def _leituras_painel(resposta: RespostaAgente) -> int:
    return sum(
        1 for c in resposta.chamadas if c.ferramenta in FERRAMENTAS_DE_PAINEL
    )


def montar_registro(
    pergunta: PerguntaAgentes,
    braco: str,
    resposta: RespostaAgente,
    latencia_s: float,
    *,
    erro_execucao: str | None = None,
) -> RegistroBraco:
    """Traduz a resposta do agente para o formato comum aos três braços."""
    valores = valores_monetarios_do_texto(resposta.resposta)
    apuracao, acerto, motivo_apuracao, verificacoes = apurar(
        pergunta,
        cobertura_observada=resposta.cobertura,
        comportamento_observado=resposta.comportamento,
        motivo_observado=resposta.motivo_recusa or MOTIVO_NA,
        bases_publicadas=resposta.bases,
        tem_valor_publicado=bool(valores),
        resposta_texto=resposta.resposta,
        violacoes=resposta.violacoes,
    )
    uso = resposta.uso or UsoAgente()
    return RegistroBraco(
        id_pergunta=pergunta.id,
        braco=braco,
        subconjunto=pergunta.subconjunto,
        categoria=pergunta.categoria,
        rota_esperada=pergunta.rota_esperada,
        pergunta=pergunta.pergunta,
        resposta=resposta.resposta,
        resposta_bruta=resposta.resposta_bruta,
        recusa=resposta.recusa,
        motivo_observado=resposta.motivo_recusa or MOTIVO_NA,
        parcial=resposta.parcial,
        precisa_desambiguacao=resposta.precisa_desambiguacao,
        comportamento_observado=resposta.comportamento,
        cobertura_observada=resposta.cobertura,
        entidades_resolvidas=_entidades_resolvidas(resposta),
        bases_publicadas=tuple(resposta.bases),
        citacoes=tuple(resposta.citacoes),
        # O agente não emite fato estruturado; a procedência dele está nas
        # citações e no log de chamadas de ferramenta.
        fatos_publicados=(),
        chamadas_ferramenta=tuple(c.como_dicionario() for c in resposta.chamadas),
        leituras_painel=_leituras_painel(resposta),
        chamadas_llm=uso.chamadas_llm,
        iteracoes=uso.chamadas_llm,
        tokens_entrada=uso.tokens_entrada,
        tokens_saida=uso.tokens_saida,
        custo_usd=uso.custo_usd,
        latencia_s=latencia_s,
        tokens_raciocinio=uso.tokens_raciocinio,
        tokens_entrada_cache_hit=uso.tokens_entrada_cache_hit,
        raciocinios=uso.raciocinios,
        veredito_auditor=resposta.veredito_auditor,
        violacoes=tuple(resposta.violacoes),
        convertida_em_recusa=resposta.convertida_em_recusa,
        status_gabarito=pergunta.status_gabarito,
        apuracao=apuracao,
        acerto=acerto,
        motivo_apuracao=motivo_apuracao,
        verificacoes=verificacoes,
        erro_execucao=erro_execucao or resposta.erro,
    )


def _registro_de_falha(
    pergunta: PerguntaAgentes, braco: str, erro: str, latencia_s: float
) -> RegistroBraco:
    """Uma pergunta que explodiu não pode derrubar as outras catorze."""
    return RegistroBraco(
        id_pergunta=pergunta.id,
        braco=braco,
        subconjunto=pergunta.subconjunto,
        categoria=pergunta.categoria,
        rota_esperada=pergunta.rota_esperada,
        pergunta=pergunta.pergunta,
        resposta=(
            "Recusa registrada: a execução do agente falhou "
            f"({erro}). Nenhuma evidência foi reunida."
        ),
        recusa=True,
        motivo_observado="recusa_convertida_por_violacao",
        parcial=True,
        comportamento_observado="recusa",
        cobertura_observada="",
        latencia_s=latencia_s,
        status_gabarito=pergunta.status_gabarito,
        apuracao=(
            APURACAO_PENDENTE if not pergunta.gabarito_verificado else APURACAO_ERRO
        ),
        acerto=None if not pergunta.gabarito_verificado else False,
        motivo_apuracao=f"execução falhou: {erro}",
        erro_execucao=erro,
    )


def executar_braco_agente(
    braco: str,
    perguntas: Sequence[PerguntaAgentes],
    config: Config,
    *,
    fabrica_llm: FabricaLLM | None = None,
    fabrica_ferramentas: FabricaFerramentas | None = None,
    orcamento: ControleOrcamento | None = None,
    relogio: Callable[[], float] = time.perf_counter,
    run_id: str | None = None,
) -> ResultadoBraco:
    """Roda o braço A ou B sobre o conjunto e devolve um registro por pergunta.

    Três decisões de medição:

    * **Uma caixa de ferramentas e um contador de LLM por papel e por
      pergunta.** O teto de 5.9.5 é por consulta; herdar o orçamento gasto pela
      pergunta anterior faria a nona estourar sem motivo, e o Auditor precisa
      reexecutar com orçamento próprio (5.9.1).
    * **Nenhuma pergunta derruba a execução.** Exceção vira registro com
      `erro_execucao` e recusa — perder 14 medições por causa de uma é pior que
      registrar a falha.
    * **Teto de gasto para a execução inteira.** Estourado o
      `ORCAMENTO_TETO_USD`, a execução **para** e devolve o que já mediu.
      Continuar seria o laço aberto pagando token que a 5.9.5 proíbe.
    """
    if braco not in ORQUESTRADORES:
        raise ValueError(f"braço sem orquestrador: {braco!r}; use A ou B")
    orquestrar = ORQUESTRADORES[braco]
    identificador = run_id or novo_run_id()
    if fabrica_llm is None:
        fabrica_llm = fabrica_llm_padrao(config, orcamento)
    if fabrica_ferramentas is None:
        fabrica_ferramentas = fabrica_ferramentas_padrao(config)

    registros: list[RegistroBraco] = []
    for pergunta in perguntas:
        inicio = relogio()
        try:
            resposta = orquestrar(
                pergunta.pergunta,
                config,
                fabrica_llm=fabrica_llm,
                fabrica_ferramentas=fabrica_ferramentas,
            )
        except OrcamentoAgentesExcedidoError as erro:
            registros.append(
                _registro_de_falha(
                    pergunta, braco, f"OrcamentoAgentesExcedidoError: {erro}",
                    relogio() - inicio,
                )
            )
            break
        except Exception as erro:  # contenção: a execução continua
            registros.append(
                _registro_de_falha(
                    pergunta, braco, f"{type(erro).__name__}: {erro}",
                    relogio() - inicio,
                )
            )
            continue
        registros.append(
            montar_registro(pergunta, braco, resposta, relogio() - inicio)
        )

    return ResultadoBraco(
        braco=braco, run_id=identificador, registros=tuple(registros)
    )


def resumo_com_isolamento(resultado: ResultadoBraco) -> dict:
    """Resumo do braço + o que o experimento de 5.9.3 pergunta explicitamente.

    A distribuição dos vereditos já vem de `resumir`. O que se acrescenta aqui é
    a contagem de **respostas alteradas pelo Auditor** — o numerador da métrica
    que decide o experimento (custo por resposta alterada). Auditor que nunca
    discorda é **resultado negativo declarado**, não sucesso (risco 12a), e por
    isso o número aparece mesmo quando é zero.
    """
    base = resumir(resultado.registros)
    alteradas = sum(
        1
        for r in resultado.registros
        if r.veredito_auditor in ("contesta", "nao_reproduz")
    )
    base["respostas_alteradas_pelo_auditor"] = alteradas
    base["parciais"] = sum(1 for r in resultado.registros if r.parcial)
    base["custo_por_resposta_alterada_usd"] = (
        (base["custo_usd_total"] / alteradas) if alteradas else None
    )
    return base


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - manual
    """Executa um braço contra o painel, o índice e o LLM reais."""
    parser = argparse.ArgumentParser(description="Braços A e B da spec 5.9.3")
    parser.add_argument("--braco", choices=[BRACO_A, BRACO_B], required=True)
    parser.add_argument(
        "--permitir-api-paga",
        action="store_true",
        help="opt-in explícito para chamada externa paga (§4.3 do plano)",
    )
    parser.add_argument("--limite", type=int, default=0, help="rodar só as N primeiras")
    argumentos = parser.parse_args(argv)

    config = carregar_config()
    if not argumentos.permitir_api_paga:
        print(
            "chamada externa paga exige --permitir-api-paga; nada foi executado"
        )
        return 2

    perguntas = list(carregar_conjunto_agentes())
    if argumentos.limite:
        perguntas = perguntas[: argumentos.limite]
    run_id = novo_run_id()
    journal = (
        Path(DIR_LOGS_EXECUCOES)
        / "journal_agentes"
        / f"{argumentos.braco.lower()}_{run_id}.jsonl"
    )
    orcamento = ControleOrcamento(
        config.orcamento_teto_usd, caminho_journal=journal
    )
    resultado = executar_braco_agente(
        argumentos.braco, perguntas, config, orcamento=orcamento, run_id=run_id
    )
    caminho_log = registrar_resultado(resultado)
    caminho_json = salvar_resultado(resultado)
    resumo = resumo_com_isolamento(resultado)
    resumo["gasto_acumulado_usd"] = orcamento.acumulado_usd
    resumo["versao_prompt_agentes"] = VERSAO_PROMPT_AGENTES
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    print(f"log RNF08: {caminho_log}")
    print(f"journal: {journal}")
    print(f"resultado: {caminho_json}")
    return 0


if __name__ == "__main__":  # pragma: no cover - execução manual
    raise SystemExit(main())


__all__ = [
    "DIR_RESULTADOS_AGENTES",
    "FERRAMENTAS_DE_PAINEL",
    "ORQUESTRADORES",
    "PAPEL_AGENTE_UNICO",
    "PAPEL_AUDITOR",
    "PAPEL_INVESTIGADOR",
    "executar_braco_agente",
    "montar_registro",
    "resumo_com_isolamento",
]
