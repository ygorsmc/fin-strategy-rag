"""Treino, baselines e métricas do classificador de prejuízo em T+1 (5.10).

Três regras que o módulo impõe por construção, não por disciplina do operador:

1. **Split temporal, nunca aleatório.** Embaralhar companhia × trimestre
   colocaria o mesmo emissor nos dois lados e mediria memorização.
2. **O limiar é escolhido na validação, jamais no teste.** Escolher o corte
   olhando o teste é a forma mais comum de inflar recall sem ganho real; aqui
   o trimestre de validação é anterior ao de teste e o limiar sai dele.
3. **Baseline obrigatório antes de qualquer celebração.** A regra de
   persistência ("teve prejuízo em T, terá em T+1") é forte em dado contábil.
   Um modelo que não a supere não agrega, e o relatório precisa dizer isso.

Métrica prioritária é **recall** (spec 5.10): deixar de sinalizar deterioração
custa mais, em research, do que sinalizar uma que o analista descarta em cinco
minutos. O limiar é escolhido maximizando **F2** na validação — F2 pondera
recall com o dobro do peso da precisão, e é a tradução declarada dessa
preferência.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.modelo.construir_painel import COLUNAS_FEATURES, PainelSupervisionado

SEMENTE = 20260823


# --------------------------------------------------------------------------- #
# Split temporal
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Divisao:
    """Treino / validação / teste separados por trimestre, nesta ordem."""

    treino: pd.DataFrame
    validacao: pd.DataFrame
    teste: pd.DataFrame
    trimestre_validacao: str
    trimestre_teste: str

    def como_resumo(self) -> dict[str, object]:
        return {
            "n_treino": len(self.treino),
            "n_validacao": len(self.validacao),
            "n_teste": len(self.teste),
            "trimestres_treino": sorted(self.treino["trimestre"].unique().tolist()),
            "trimestre_validacao": self.trimestre_validacao,
            "trimestre_teste": self.trimestre_teste,
            "taxa_positivos_treino": float(self.treino["rotulo"].mean()),
            "taxa_positivos_validacao": float(self.validacao["rotulo"].mean()),
            "taxa_positivos_teste": float(self.teste["rotulo"].mean()),
        }


def dividir_temporalmente(painel: PainelSupervisionado) -> Divisao:
    """Último trimestre vira teste; o penúltimo, validação do limiar."""
    quadro = painel.quadro
    ordens = sorted(quadro["ordem"].unique().tolist())
    if len(ordens) < 3:
        raise ValueError(
            "split temporal exige ao menos três trimestres de observação "
            f"(treino, validação, teste); recebido {len(ordens)}"
        )
    ordem_teste, ordem_validacao = ordens[-1], ordens[-2]
    teste = quadro[quadro["ordem"] == ordem_teste]
    validacao = quadro[quadro["ordem"] == ordem_validacao]
    treino = quadro[quadro["ordem"] < ordem_validacao]
    return Divisao(
        treino=treino,
        validacao=validacao,
        teste=teste,
        trimestre_validacao=str(validacao["trimestre"].iloc[0]),
        trimestre_teste=str(teste["trimestre"].iloc[0]),
    )


# --------------------------------------------------------------------------- #
# Métricas
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Metricas:
    """Conjunto completo exigido pela 5.10 — nenhuma reportada sozinha."""

    nome: str
    limiar: float
    n: int
    acuracia: float
    precisao: float
    recall: float
    f1: float
    roc_auc: float | None
    verdadeiro_positivo: int
    falso_positivo: int
    verdadeiro_negativo: int
    falso_negativo: int

    @property
    def matriz_confusao(self) -> list[list[int]]:
        return [
            [self.verdadeiro_negativo, self.falso_positivo],
            [self.falso_negativo, self.verdadeiro_positivo],
        ]


def _divisao_segura(numerador: float, denominador: float) -> float:
    return float(numerador / denominador) if denominador else 0.0


def avaliar(
    nome: str,
    y_verdadeiro: np.ndarray,
    y_escore: np.ndarray,
    *,
    limiar: float,
) -> Metricas:
    """Calcula tudo a partir do escore contínuo e do limiar declarado."""
    y_verdadeiro = np.asarray(y_verdadeiro).astype(int)
    y_escore = np.asarray(y_escore, dtype=float)
    predito = (y_escore >= limiar).astype(int)

    vp = int(np.sum((predito == 1) & (y_verdadeiro == 1)))
    fp = int(np.sum((predito == 1) & (y_verdadeiro == 0)))
    vn = int(np.sum((predito == 0) & (y_verdadeiro == 0)))
    fn = int(np.sum((predito == 0) & (y_verdadeiro == 1)))

    precisao = _divisao_segura(vp, vp + fp)
    recall = _divisao_segura(vp, vp + fn)
    f1 = _divisao_segura(2 * precisao * recall, precisao + recall)

    # AUC exige as duas classes presentes e escore não constante.
    auc: float | None
    if len(np.unique(y_verdadeiro)) < 2 or len(np.unique(y_escore)) < 2:
        auc = None
    else:
        auc = float(roc_auc_score(y_verdadeiro, y_escore))

    return Metricas(
        nome=nome,
        limiar=float(limiar),
        n=int(len(y_verdadeiro)),
        acuracia=_divisao_segura(vp + vn, len(y_verdadeiro)),
        precisao=precisao,
        recall=recall,
        f1=f1,
        roc_auc=auc,
        verdadeiro_positivo=vp,
        falso_positivo=fp,
        verdadeiro_negativo=vn,
        falso_negativo=fn,
    )


def escolher_limiar_por_f2(
    y_verdadeiro: np.ndarray, y_escore: np.ndarray, *, beta: float = 2.0
) -> float:
    """Limiar que maximiza F-beta na validação (beta=2 favorece recall).

    Deixar o limiar em 0,5 seria adotar por omissão a preferência simétrica
    entre falso positivo e falso negativo — exatamente o que a 5.10 proíbe.
    """
    y_verdadeiro = np.asarray(y_verdadeiro).astype(int)
    y_escore = np.asarray(y_escore, dtype=float)
    candidatos = np.unique(np.round(y_escore, 4))
    melhor_limiar, melhor_valor = 0.5, -1.0
    beta2 = beta * beta
    for limiar in candidatos:
        predito = (y_escore >= limiar).astype(int)
        vp = float(np.sum((predito == 1) & (y_verdadeiro == 1)))
        fp = float(np.sum((predito == 1) & (y_verdadeiro == 0)))
        fn = float(np.sum((predito == 0) & (y_verdadeiro == 1)))
        precisao = _divisao_segura(vp, vp + fp)
        recall = _divisao_segura(vp, vp + fn)
        denominador = beta2 * precisao + recall
        fbeta = _divisao_segura((1 + beta2) * precisao * recall, denominador)
        if fbeta > melhor_valor:
            melhor_limiar, melhor_valor = float(limiar), fbeta
    return melhor_limiar


# --------------------------------------------------------------------------- #
# Modelos
# --------------------------------------------------------------------------- #


def construir_regressao_logistica() -> Pipeline:
    """Imputação + padronização + regressão logística.

    A imputação é ajustada **só no treino** — calcular a mediana sobre o painel
    inteiro vazaria estatística do futuro para dentro do passado.
    """
    return Pipeline(
        [
            ("imputacao", SimpleImputer(strategy="median")),
            ("escala", StandardScaler()),
            (
                "modelo",
                LogisticRegression(max_iter=2000, random_state=SEMENTE),
            ),
        ]
    )


def construir_gradient_boosting() -> HistGradientBoostingClassifier:
    """Árvores com tratamento nativo de nulo — não precisa imputar."""
    return HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=20,
        l2_regularization=1.0,
        random_state=SEMENTE,
    )


# --------------------------------------------------------------------------- #
# Baselines
# --------------------------------------------------------------------------- #


def escore_classe_majoritaria(treino: pd.DataFrame, alvo: pd.DataFrame) -> np.ndarray:
    """Prevê sempre a classe majoritária do treino — constante."""
    majoritaria = float(treino["rotulo"].mean() >= 0.5)
    return np.full(len(alvo), majoritaria, dtype=float)


def escore_persistencia(alvo: pd.DataFrame) -> np.ndarray:
    """"Teve prejuízo em T, terá em T+1" — a regra simples a bater."""
    return alvo["prejuizo_em_t"].to_numpy(dtype=float)


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #


def precisao_a_recall_alvo(
    y_verdadeiro: np.ndarray, y_escore: np.ndarray, *, recall_alvo: float
) -> dict[str, float]:
    """Compara maçã com maçã: qual a precisão do modelo NO MESMO recall.

    Sem isto, "recall 0,94 contra 0,66" é comparação enviesada — o modelo
    comprou recall baixando o limiar, e a pergunta honesta é quanto de falso
    alarme ele cobra para detectar tanto quanto a regra simples.
    """
    y_verdadeiro = np.asarray(y_verdadeiro).astype(int)
    y_escore = np.asarray(y_escore, dtype=float)
    for limiar in np.unique(np.round(y_escore, 4))[::-1]:
        metrica = avaliar("alvo", y_verdadeiro, y_escore, limiar=float(limiar))
        if metrica.recall >= recall_alvo:
            return {
                "limiar": metrica.limiar,
                "recall": metrica.recall,
                "precisao": metrica.precisao,
            }
    return {"limiar": 0.0, "recall": 1.0, "precisao": float(y_verdadeiro.mean())}


#: Features que codificam histórico de prejuízo — o que a persistência já usa.
_FEATURES_DE_HISTORICO = (
    "prejuizo_em_t",
    "prejuizo_em_t_menos_1",
    "taxa_prejuizos_ate_t",
)


def ablacao_sem_historico_de_prejuizo(divisao: Divisao) -> dict[str, float]:
    """O modelo ainda ordena se lhe tirarmos o sinal da regra simples?

    Se o desempenho colapsar, o modelo é a persistência com passos extras.
    """
    colunas = [c for c in COLUNAS_FEATURES if c not in _FEATURES_DE_HISTORICO]
    y_treino = divisao.treino["rotulo"].to_numpy(dtype=int)
    y_teste = divisao.teste["rotulo"].to_numpy(dtype=int)
    resultado: dict[str, float] = {}
    for nome, modelo in (
        ("regressao_logistica", construir_regressao_logistica()),
        ("gradient_boosting", construir_gradient_boosting()),
    ):
        modelo.fit(divisao.treino[colunas], y_treino)
        escore = modelo.predict_proba(divisao.teste[colunas])[:, 1]
        resultado[nome] = float(roc_auc_score(y_teste, escore))
    return resultado


@dataclass
class Relatorio:
    divisao: dict[str, object]
    features: list[str] = field(default_factory=list)
    metricas: list[dict[str, object]] = field(default_factory=list)
    analises: dict[str, object] = field(default_factory=dict)
    observacoes: list[str] = field(default_factory=list)

    def gravar(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _linha(m: Metricas, conjunto: str) -> dict[str, object]:
    dados = asdict(m)
    dados["conjunto"] = conjunto
    dados["matriz_confusao"] = m.matriz_confusao
    return dados


def treinar_e_avaliar(painel: PainelSupervisionado) -> Relatorio:
    """Roda baselines e modelos sob o mesmo split e devolve tudo junto."""
    divisao = dividir_temporalmente(painel)
    colunas = list(COLUNAS_FEATURES)

    x_treino = divisao.treino[colunas]
    y_treino = divisao.treino["rotulo"].to_numpy(dtype=int)
    x_validacao = divisao.validacao[colunas]
    y_validacao = divisao.validacao["rotulo"].to_numpy(dtype=int)
    x_teste = divisao.teste[colunas]
    y_teste = divisao.teste["rotulo"].to_numpy(dtype=int)

    relatorio = Relatorio(divisao=divisao.como_resumo(), features=colunas)

    # --- baselines, sempre primeiro -------------------------------------- #
    relatorio.metricas.append(
        _linha(
            avaliar(
                "baseline_classe_majoritaria",
                y_teste,
                escore_classe_majoritaria(divisao.treino, divisao.teste),
                limiar=0.5,
            ),
            "teste",
        )
    )
    metrica_persistencia = avaliar(
        "baseline_persistencia",
        y_teste,
        escore_persistencia(divisao.teste),
        limiar=0.5,
    )
    relatorio.metricas.append(_linha(metrica_persistencia, "teste"))
    comparacao_justa: dict[str, object] = {
        "recall_alvo": metrica_persistencia.recall,
        "precisao_da_persistencia": metrica_persistencia.precisao,
    }

    # --- modelos ---------------------------------------------------------- #
    for nome, modelo in (
        ("regressao_logistica", construir_regressao_logistica()),
        ("gradient_boosting", construir_gradient_boosting()),
    ):
        modelo.fit(x_treino, y_treino)
        escore_validacao = modelo.predict_proba(x_validacao)[:, 1]
        limiar = escolher_limiar_por_f2(y_validacao, escore_validacao)
        relatorio.metricas.append(
            _linha(
                avaliar(nome, y_validacao, escore_validacao, limiar=limiar),
                "validacao",
            )
        )
        escore_teste = modelo.predict_proba(x_teste)[:, 1]
        relatorio.metricas.append(
            _linha(avaliar(nome, y_teste, escore_teste, limiar=limiar), "teste")
        )
        # Contraprova do limiar: o mesmo modelo em 0,5, para deixar visível
        # quanto da diferença veio da escolha do corte e quanto do modelo.
        relatorio.metricas.append(
            _linha(
                avaliar(f"{nome}_limiar_0.5", y_teste, escore_teste, limiar=0.5),
                "teste",
            )
        )
        comparacao_justa[nome] = precisao_a_recall_alvo(
            y_teste, escore_teste, recall_alvo=metrica_persistencia.recall
        )

    relatorio.analises["precisao_ao_recall_da_persistencia"] = comparacao_justa
    relatorio.analises["ablacao_sem_historico_de_prejuizo"] = (
        ablacao_sem_historico_de_prejuizo(divisao)
    )
    return relatorio
