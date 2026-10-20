"""Suíte DeepEval (spec 5.15): faithfulness e answer relevancy no caminho de avaliação.

Três decisões, e o porquê de cada uma:

1. **Lê respostas já geradas; não gera nenhuma.** O DeepEval roda no caminho de
   avaliação (§6), sem camada de agentes, sobre a rodada congelada que o README
   cita: respostas e trechos vêm do `checkpoint_teste.jsonl`, filtrados pelo
   fingerprint publicado em `metricas_teste.json`. Gerar de novo mediria outra
   rodada, a outra temperatura de sorte, e pagaria o gerador duas vezes.
2. **O juiz é um provedor da RNF06, nunca o default da biblioteca.** Sem modelo
   nomeado o DeepEval cai num modelo próprio com chave própria
   (`exigir_modelo_juiz_deepeval`). Aqui ele passa por `fabricar_provedor_llm`,
   com preço próprio, temperatura 0, teto de custo e registro antes e depois de
   cada chamada (RNF08).
3. **O desfecho separa o que se mede.** Resposta publicada, rascunho que a RN02
   descartou e recusa do próprio modelo são coisas diferentes. A recusa do
   modelo não tem afirmação para checar e não é pontuada: a correção dela já é
   medida por código (`taxa_recusa_correta`). O rascunho descartado é pontuado
   porque é ele que diz se a guarda descartou certo.

O que este módulo NÃO é: a métrica de groundedness reportada. A spec 5.15 manda
medir o juiz CONTRA a auditoria humana; `concordancia_com_humano` faz isso, e o
juiz automático continua sendo instrumento, não gabarito.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

# Antes de qualquer import do DeepEval, e não `setdefault`: a telemetria dele
# manda evento para fora, e o autoload de `.env` jogaria as chaves do projeto
# no ambiente do processo (inclusive no da suíte de testes).
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
os.environ["DEEPEVAL_DISABLE_DOTENV"] = "1"
# E nem o arquivo de chaves legado `.deepeval/.deepeval`, que o DeepEval
# também funde no ambiente.
os.environ["DEEPEVAL_DISABLE_LEGACY_KEYFILE"] = "1"


@contextmanager
def _sem_variaveis_vazias():
    """Esconde do DeepEval as variáveis de ambiente vazias, e devolve depois.

    As configurações do DeepEval leem do ambiente nomes que este projeto também
    usa, e validam `AZURE_OPENAI_ENDPOINT` como URL: vazia, a validação falha e
    o import cai. O `.env.example` deixa essa variável vazia, e qualquer
    `load_dotenv` anterior (o app, a suíte) a põe no ambiente assim. Vazia e
    ausente significam o mesmo para este projeto. Serve só para o import:
    depois dele, `env_ignore_empty` resolve de vez (ver abaixo).
    """
    retiradas = {nome: valor for nome, valor in os.environ.items() if valor == ""}
    for nome in retiradas:
        del os.environ[nome]
    try:
        yield
    finally:
        for nome, valor in retiradas.items():
            os.environ.setdefault(nome, valor)


with _sem_variaveis_vazias():
    from deepeval.config.settings import Settings as _ConfiguracoesDeepEval  # noqa: E402
    from deepeval.config.settings import reset_settings as _recarregar_deepeval  # noqa: E402
    from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric  # noqa: E402
    from deepeval.models import DeepEvalBaseLLM  # noqa: E402
    from deepeval.test_case import LLMTestCase  # noqa: E402

# O DeepEval reconstrói as configurações sempre que o ambiente muda, inclusive
# na thread de telemetria e na saída do processo, fora de qualquer `with` daqui.
# `env_ignore_empty` é opção do pydantic-settings, lida a cada construção:
# variável vazia passa a valer como ausente, em qualquer ponto.
_ConfiguracoesDeepEval.model_config["env_ignore_empty"] = True
_recarregar_deepeval()
from pydantic import BaseModel, ValidationError  # noqa: E402

from src.avaliacao import registrar_execucao  # noqa: E402
from src.config import Config, exigir_modelo_juiz_deepeval  # noqa: E402
from src.geracao import ProvedorLLM, fabricar_provedor_llm  # noqa: E402

DESFECHO_PUBLICADA = "publicada"
DESFECHO_DESCARTADA_RN02 = "descartada_rn02"
DESFECHO_RECUSA_MODELO = "recusa_modelo"
DESFECHOS_PONTUADOS = (DESFECHO_PUBLICADA, DESFECHO_DESCARTADA_RN02)

METRICA_FIDELIDADE = "faithfulness"
METRICA_RELEVANCIA = "answer_relevancy"

# Fundamentada = TODAS as afirmações sustentadas pelos trechos. Fixado antes da
# rodada: em dado financeiro, um número sem lastro torna a resposta errada, e
# um limiar abaixo de 1 aceitaria exatamente esse caso.
LIMIAR_FUNDAMENTADA = 1.0

# O faithfulness do DeepEval, por padrão, mede CONTRADIÇÃO, não sustentação: o
# template manda marcar "borderline" a afirmação "não sustentada pelo contexto"
# e o escore conta "borderline" como fiel. Um número que não está em trecho
# nenhum, e que nenhum trecho contradiz, passaria. Para a RN02 isso é
# alucinação, então o escore principal penaliza a afirmação ambígua; o escore
# padrão da biblioteca sai junto, calculado dos mesmos veredictos, sem
# chamada extra (`_detalhe`).
PENALIZAR_AMBIGUAS = True

# Campo de preço por provedor: o juiz herda o mecanismo de custo do provedor,
# só trocando modelo e preço.
_CAMPOS_DO_PROVEDOR: dict[str, tuple[str, str, str]] = {
    "gemini": (
        "gemini_modelo_llm",
        "gemini_preco_entrada_usd_milhao",
        "gemini_preco_saida_usd_milhao",
    ),
    "deepseek": (
        "deepseek_modelo",
        "deepseek_preco_entrada_usd_milhao",
        "deepseek_preco_saida_usd_milhao",
    ),
}

PROMPT_SISTEMA_JUIZ = (
    "Você é um avaliador. Siga a instrução do usuário à risca e responda "
    "somente com o JSON pedido."
)


class OrcamentoJuizExcedidoError(RuntimeError):
    """A próxima chamada do juiz passaria do teto da rodada."""


def config_do_juiz(config: Config) -> Config:
    """A configuração do provedor que faz o papel de juiz.

    Falha, em vez de supor, em dois casos: juiz não nomeado
    (`exigir_modelo_juiz_deepeval`) e preço ausente quando o juiz não é o modelo
    já configurado no provedor dele. O segundo caso é o silencioso: o custo
    sairia com o preço do gerador, e o teto mediria a coisa errada.
    """
    modelo = exigir_modelo_juiz_deepeval(config)
    provedor = config.deepeval_provedor_juiz or config.llm_provider
    if provedor not in _CAMPOS_DO_PROVEDOR:
        raise ValueError(
            f"provedor de juiz sem suporte de preço aqui: {provedor!r} "
            f"(aceitos: {sorted(_CAMPOS_DO_PROVEDOR)})"
        )
    campo_modelo, campo_entrada, campo_saida = _CAMPOS_DO_PROVEDOR[provedor]
    entrada = config.deepeval_preco_entrada_usd_milhao
    saida = config.deepeval_preco_saida_usd_milhao
    if entrada < 0 or saida < 0:
        if getattr(config, campo_modelo) != modelo:
            raise ValueError(
                f"preço do juiz {modelo!r} não informado: defina "
                "DEEPEVAL_PRECO_ENTRADA_USD_MILHAO e "
                "DEEPEVAL_PRECO_SAIDA_USD_MILHAO. Sem eles o custo sairia com "
                f"o preço de {getattr(config, campo_modelo)!r} (§3.1)."
            )
        entrada = getattr(config, campo_entrada)
        saida = getattr(config, campo_saida)
    extras: dict[str, Any] = {}
    if provedor == "deepseek":
        # O custo da DeepSeek cobra o cache hit pelo próprio campo. Sem preço
        # de cache do juiz na configuração, usa-se o de entrada cheio: nunca
        # subestima (achado B1 da auditoria de 20/10).
        extras["deepseek_preco_entrada_cache_hit_usd_milhao"] = entrada
    return replace(
        config,
        llm_provider=provedor,
        **{campo_modelo: modelo, campo_entrada: entrada, campo_saida: saida},
        **extras,
    )


@dataclass
class UsoJuiz:
    chamadas: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    falhas: int = 0
    falhas_transitorias: int = 0
    # Parte de `custo_usd` que é estimativa de tentativa falha, não cobrança
    # medida. Sai separada no relatório.
    debito_conservador_usd: float = 0.0


class JuizDeepEval(DeepEvalBaseLLM):
    """Adaptador: o DeepEval chama `generate`; quem responde é o provedor.

    Cada chamada passa pelo teto antes de sair e é registrada antes e depois
    (RNF08). Erro transitório (503/429) é repetido com espera crescente; erro
    de outro tipo sobe na hora, porque repetir prompt inválido só gasta cota.
    """

    TENTATIVAS = 4
    ESPERA_INICIAL_S = 10.0

    def __init__(
        self,
        provedor: ProvedorLLM,
        *,
        nome_modelo: str,
        teto_usd: float,
        run_id: str,
        registrar: Callable[[dict], Any] = registrar_execucao,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provedor = provedor
        self.nome_modelo = nome_modelo
        self.teto_usd = float(teto_usd)
        self.run_id = run_id
        self.uso = UsoJuiz()
        self.contexto: dict[str, str] = {}
        self._registrar = registrar
        self._dormir = dormir
        super().__init__(nome_modelo)

    def load_model(self) -> ProvedorLLM:
        return self.provedor

    def get_model_name(self) -> str:
        return f"{getattr(self.provedor, 'nome', 'provedor')}/{self.nome_modelo}"

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        bruta = self._gerar_com_reespera(prompt, schema.__name__ if schema else "texto")
        if schema is None:
            return bruta.texto
        try:
            return schema.model_validate(json.loads(_so_o_json(bruta.texto)))
        except (ValueError, ValidationError):
            # O DeepEval tenta de novo a partir do texto (trimAndLoadJson) e,
            # se não houver JSON, falha a métrica — que é o desfecho honesto.
            return bruta.texto

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        return self.generate(prompt, schema)

    def _gerar_com_reespera(self, prompt: str, etapa: str):
        """Uma chamada, com teto e registro a CADA tentativa.

        Tentativa que falha depois de sair é debitada pela estimativa
        conservadora, como em `src.avaliacao`: o provedor pode ter cobrado (o
        DeepSeek que esgota `max_tokens` raciocinando levanta erro depois da
        resposta paga), e sem o débito o teto e o custo do relatório sairiam
        menores que o gasto (achado M3 da auditoria de 20/10).
        """
        espera = self.ESPERA_INICIAL_S
        for tentativa in range(1, self.TENTATIVAS + 1):
            estimativa = float(
                self.provedor.estimar_custo_maximo(PROMPT_SISTEMA_JUIZ, prompt) or 0.0
            )
            if self.uso.custo_usd + estimativa > self.teto_usd:
                raise OrcamentoJuizExcedidoError(
                    f"teto de US$ {self.teto_usd:.2f} do juiz: acumulado "
                    f"US$ {self.uso.custo_usd:.6f}, próxima chamada até "
                    f"US$ {estimativa:.6f}"
                )
            id_chamada = uuid.uuid4().hex
            self._registrar(
                {
                    "evento": "deepeval_juiz_inicio",
                    "run_id": self.run_id,
                    "id_chamada": id_chamada,
                    "modelo_juiz": self.nome_modelo,
                    "etapa": etapa,
                    "tentativa": tentativa,
                    "estimativa_max_usd": estimativa,
                    **self.contexto,
                }
            )
            try:
                bruta = self.provedor.gerar(PROMPT_SISTEMA_JUIZ, prompt, temperatura=0.0)
            except Exception as erro:  # noqa: BLE001 - reclassificado abaixo
                transitorio = any(
                    marca in str(erro)
                    for marca in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")
                )
                self.uso.falhas += 1
                self.uso.falhas_transitorias += int(transitorio)
                self.uso.custo_usd += estimativa
                self.uso.debito_conservador_usd += estimativa
                self._registrar(
                    {
                        "evento": "deepeval_juiz_fim",
                        "run_id": self.run_id,
                        "id_chamada": id_chamada,
                        "erro": type(erro).__name__,
                        "transitorio": transitorio,
                        "debito_conservador_usd": estimativa,
                        **self.contexto,
                    }
                )
                if not transitorio or tentativa == self.TENTATIVAS:
                    raise
                self._dormir(espera)
                espera *= 2
                continue
            custo = float(bruta.uso.custo_usd or 0.0)
            self.uso.chamadas += 1
            self.uso.tokens_entrada += int(bruta.uso.tokens_entrada or 0)
            self.uso.tokens_saida += int(bruta.uso.tokens_saida or 0)
            self.uso.custo_usd += custo
            self._registrar(
                {
                    "evento": "deepeval_juiz_fim",
                    "run_id": self.run_id,
                    "id_chamada": id_chamada,
                    "custo_usd": custo,
                    "tokens_entrada": bruta.uso.tokens_entrada,
                    "tokens_saida": bruta.uso.tokens_saida,
                    **self.contexto,
                }
            )
            return bruta
        raise RuntimeError("inalcançável")


def _so_o_json(texto: str) -> str:
    texto = (texto or "").strip()
    inicio, fim = texto.find("{"), texto.rfind("}")
    return texto[inicio : fim + 1] if 0 <= inicio < fim else texto


# --------------------------------------------------------------------------- #
# Casos: o que cada pergunta da rodada congelada entrega ao juiz
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CasoDeepEval:
    pergunta_id: str
    categoria: str
    estrategia: str
    desfecho: str
    pergunta: str
    texto: str
    contexto: tuple[str, ...]
    recusa_correta: bool | None = None
    exatidao_ok: bool | None = None


def _rascunho(resposta: Mapping[str, Any]) -> str:
    """A resposta que o modelo redigiu antes da guarda, se houve."""
    bruto = resposta.get("bruto")
    if not bruto:
        return ""
    try:
        objeto = json.loads(bruto)
    except (TypeError, json.JSONDecodeError):
        return ""
    return str(objeto.get("resposta") or "").strip() if isinstance(objeto, dict) else ""


def caso_do_registro(registro: Mapping[str, Any]) -> CasoDeepEval:
    """Classifica o desfecho e monta pergunta, texto e trechos.

    Os trechos entram sem score, pela mesma razão do juiz de 2026-08-23: o
    score enviesaria o julgamento para o topo do ranking.
    """
    resposta = registro.get("resposta") or {}
    publicada = str(resposta.get("resposta") or "").strip()
    if not resposta.get("recusa") and publicada:
        desfecho, texto = DESFECHO_PUBLICADA, publicada
    elif _rascunho(resposta):
        desfecho, texto = DESFECHO_DESCARTADA_RN02, _rascunho(resposta)
    else:
        desfecho = DESFECHO_RECUSA_MODELO
        texto = str(resposta.get("motivo_recusa") or "recusa sem motivo declarado")
    contexto = tuple(
        str((item.get("chunk") or {}).get("texto") or "")
        for item in registro.get("recuperados") or ()
        if (item.get("chunk") or {}).get("texto")
    )
    return CasoDeepEval(
        pergunta_id=str(registro["pergunta_id"]),
        categoria=str(registro.get("categoria") or ""),
        estrategia=str(registro.get("estrategia") or ""),
        desfecho=desfecho,
        pergunta=str(registro.get("pergunta") or ""),
        texto=texto,
        contexto=contexto,
        recusa_correta=registro.get("recusa_correta"),
        exatidao_ok=registro.get("exatidao_ok"),
    )


def carregar_casos(
    checkpoint: Path,
    fingerprint: str,
    estrategia: str,
    perguntas: Mapping[str, str],
) -> list[CasoDeepEval]:
    """Os casos de UMA estratégia da rodada `fingerprint`, um por pergunta.

    O checkpoint guarda tentativas de várias rodadas; valem só as da rodada
    publicada. Pergunta repetida (retomada depois de falha) fica com a última
    linha, que é a que o consolidado usou. A pergunta vem do conjunto
    congelado, porque o checkpoint guarda só o id.
    """
    escolhidos: dict[str, Mapping[str, Any]] = {}
    with open(checkpoint, encoding="utf-8") as origem:
        for linha in origem:
            registro = json.loads(linha)
            if registro.get("fingerprint") != fingerprint:
                continue
            if registro.get("estrategia") != estrategia or registro.get("erro"):
                continue
            escolhidos[registro["pergunta_id"]] = registro
    casos = []
    for pergunta_id in sorted(escolhidos):
        if pergunta_id not in perguntas:
            raise ValueError(f"{pergunta_id} não está no conjunto congelado")
        registro = dict(escolhidos[pergunta_id], pergunta=perguntas[pergunta_id])
        casos.append(caso_do_registro(registro))
    return casos


# --------------------------------------------------------------------------- #
# Medição
# --------------------------------------------------------------------------- #


@dataclass
class ResultadoCaso:
    caso: CasoDeepEval
    metricas: dict[str, dict[str, Any]] = field(default_factory=dict)
    custo_usd: float = 0.0
    erro: str | None = None

    def como_dicionario(self) -> dict:
        dados = asdict(self.caso)
        dados.pop("contexto")
        dados["n_trechos"] = len(self.caso.contexto)
        return {**dados, "metricas": self.metricas, "custo_usd": self.custo_usd, "erro": self.erro}


def medir_caso(
    caso: CasoDeepEval,
    juiz: JuizDeepEval,
    *,
    fabricas: Mapping[str, Callable[[JuizDeepEval], Any]] | None = None,
) -> ResultadoCaso:
    """Faithfulness e answer relevancy de um caso, em modo síncrono.

    Síncrono de propósito: o modo assíncrono do DeepEval dispara as chamadas em
    paralelo, e o teto de custo e o limite de taxa do provedor passam a ser
    disputados entre elas. Uma de cada vez, o teto é conferido antes de cada
    uma. Recusa do modelo não é pontuada (ver o docstring do módulo).
    """
    resultado = ResultadoCaso(caso)
    if caso.desfecho not in DESFECHOS_PONTUADOS:
        return resultado
    fabricas = fabricas or {
        # `eval_mode="llm"` fixo: um DEEPEVAL_EVAL_MODE herdado do ambiente
        # ("hybrid") mandaria a decisão a outro modelo, fora deste juiz.
        METRICA_FIDELIDADE: lambda j: FaithfulnessMetric(
            model=j,
            threshold=LIMIAR_FUNDAMENTADA,
            include_reason=True,
            async_mode=False,
            penalize_ambiguous_claims=PENALIZAR_AMBIGUAS,
            eval_mode="llm",
        ),
        METRICA_RELEVANCIA: lambda j: AnswerRelevancyMetric(
            model=j, include_reason=True, async_mode=False, eval_mode="llm"
        ),
    }
    teste = LLMTestCase(
        input=caso.pergunta,
        actual_output=caso.texto,
        retrieval_context=list(caso.contexto),
    )
    antes = juiz.uso.custo_usd
    for nome, fabricar in fabricas.items():
        juiz.contexto = {"pergunta_id": caso.pergunta_id, "metrica": nome}
        try:
            metrica = fabricar(juiz)
            metrica.measure(teste, _show_indicator=False)
        except OrcamentoJuizExcedidoError:
            raise
        except Exception as erro:  # noqa: BLE001 - registrado no resultado
            resultado.erro = f"{nome}: {type(erro).__name__}: {erro}"
            continue
        resultado.metricas[nome] = {
            "score": metrica.score,
            "sucesso": bool(metrica.success),
            "razao": metrica.reason,
            **_detalhe(metrica),
        }
    resultado.custo_usd = juiz.uso.custo_usd - antes
    return resultado


def _detalhe(metrica: Any) -> dict:
    """Contagens que explicam o score, e o escore padrão da biblioteca.

    Fidelidade usa "borderline" para a afirmação sem sustentação; relevância
    usa "idk" para a ambígua. As duas entram em `n_incerto`. O escore padrão
    conta o incerto como aprovado, e é recalculado daqui para que as duas
    leituras venham da mesma chamada.
    """
    veredictos = getattr(metrica, "verdicts", None) or []
    rotulos = [
        str(getattr(v, "verdict", "")).strip().lower().split(".")[-1]
        for v in veredictos
    ]
    sim, nao = rotulos.count("yes"), rotulos.count("no")
    incerto = rotulos.count("borderline") + rotulos.count("idk")
    return {
        "n_veredictos": len(rotulos),
        "n_sim": sim,
        "n_nao": nao,
        "n_incerto": incerto,
        "score_incerto_aprovado": (
            round((sim + incerto) / len(rotulos), 4) if rotulos else None
        ),
    }


def agregar(resultados: Sequence[ResultadoCaso]) -> dict:
    """Médias por desfecho e por métrica, com n explícito ao lado de cada média."""
    saida: dict[str, Any] = {"n_casos": len(resultados)}
    por_desfecho: dict[str, Any] = {}
    for desfecho in (DESFECHO_PUBLICADA, DESFECHO_DESCARTADA_RN02, DESFECHO_RECUSA_MODELO):
        grupo = [r for r in resultados if r.caso.desfecho == desfecho]
        bloco: dict[str, Any] = {"n": len(grupo)}
        for metrica in (METRICA_FIDELIDADE, METRICA_RELEVANCIA):
            notas = [
                r.metricas[metrica]["score"]
                for r in grupo
                if metrica in r.metricas and r.metricas[metrica]["score"] is not None
            ]
            bloco[metrica] = {
                "n_pontuados": len(notas),
                "media": round(sum(notas) / len(notas), 4) if notas else None,
                "n_score_1": sum(1 for n in notas if n >= LIMIAR_FUNDAMENTADA),
            }
        por_desfecho[desfecho] = bloco
    saida["por_desfecho"] = por_desfecho
    saida["n_erros"] = sum(1 for r in resultados if r.erro)
    return saida


def concordancia_com_humano(
    pares: Iterable[tuple[bool, bool]],
) -> dict:
    """Matriz juiz × humano sobre "o sistema fez a coisa certa?" (spec 5.15).

    Cada par é (juiz diz que acertou, humano diz que acertou). A tradução de
    "fundamentada" para "acertou" depende do desfecho e é feita por quem chama
    (`scripts/medir_juiz_groundedness.py::_sistema_acertou`), para os dois
    juízes do projeto usarem a mesma régua.
    """
    pares = list(pares)
    matriz = {
        "ambos_acertou": sum(1 for j, h in pares if j and h),
        "ambos_errou": sum(1 for j, h in pares if not j and not h),
        "juiz_acertou_humano_errou": sum(1 for j, h in pares if j and not h),
        "juiz_errou_humano_acertou": sum(1 for j, h in pares if not j and h),
    }
    return {
        "n": len(pares),
        "matriz": matriz,
        "taxa_concordancia": (
            (matriz["ambos_acertou"] + matriz["ambos_errou"]) / len(pares)
            if pares
            else None
        ),
    }


def fabricar_juiz(config: Config, *, teto_usd: float, run_id: str, **kw) -> JuizDeepEval:
    juiz_config = config_do_juiz(config)
    campo_modelo = _CAMPOS_DO_PROVEDOR[juiz_config.llm_provider][0]
    return JuizDeepEval(
        fabricar_provedor_llm(juiz_config),
        nome_modelo=getattr(juiz_config, campo_modelo),
        teto_usd=teto_usd,
        run_id=run_id,
        **kw,
    )
