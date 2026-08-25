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
from collections.abc import Sequence
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


def metricas_de_ranqueamento(
    y_verdadeiro: np.ndarray,
    y_escore: np.ndarray,
    *,
    fracoes: Sequence[float] = (0.05, 0.10, 0.20, 0.30),
) -> dict[str, object]:
    """Precisão e *lift* no topo da lista — a métrica do uso declarado.

    A 5.10 diz que o módulo serve para **ordenar** companhias por atenção
    requerida. Ordenação se mede no topo da lista, não por um limiar global: um
    corte por F2 que sinaliza 60% da base tem recall alto e utilidade baixa,
    porque o analista não consegue ler 60% da base.

    `lift` é a precisão no topo dividida pela taxa-base — quantas vezes melhor
    que sortear.
    """
    y_verdadeiro = np.asarray(y_verdadeiro).astype(int)
    y_escore = np.asarray(y_escore, dtype=float)
    n = len(y_verdadeiro)
    taxa_base = float(y_verdadeiro.mean()) if n else 0.0
    ordem = np.argsort(-y_escore, kind="stable")
    resultado: dict[str, object] = {"taxa_base": taxa_base}
    for fracao in fracoes:
        k = max(1, int(round(n * fracao)))
        topo = y_verdadeiro[ordem[:k]]
        precisao = float(topo.mean())
        resultado[f"precisao_topo_{int(fracao * 100)}pct"] = precisao
        resultado[f"lift_topo_{int(fracao * 100)}pct"] = (
            precisao / taxa_base if taxa_base else 0.0
        )
        resultado[f"recall_topo_{int(fracao * 100)}pct"] = (
            float(topo.sum() / y_verdadeiro.sum()) if y_verdadeiro.sum() else 0.0
        )
    return resultado


def metricas_de_calibracao(
    y_verdadeiro: np.ndarray, y_escore: np.ndarray, *, n_faixas: int = 10
) -> dict[str, object]:
    """Brier e desvio de calibração — publicamos probabilidade, então medimos.

    Escolher limiar sobre uma probabilidade mal calibrada é escolher sobre um
    número que não quer dizer o que aparenta. Até 2026-08-23 isto não era
    medido, e a lacuna estava declarada nas ressalvas.
    """
    y_verdadeiro = np.asarray(y_verdadeiro).astype(int)
    y_escore = np.asarray(y_escore, dtype=float)
    brier = float(np.mean((y_escore - y_verdadeiro) ** 2))

    bordas = np.linspace(0.0, 1.0, n_faixas + 1)
    indices = np.clip(np.digitize(y_escore, bordas[1:-1]), 0, n_faixas - 1)
    faixas: list[dict[str, float]] = []
    erro_absoluto_ponderado = 0.0
    for faixa in range(n_faixas):
        seletor = indices == faixa
        if not seletor.any():
            continue
        previsto = float(y_escore[seletor].mean())
        observado = float(y_verdadeiro[seletor].mean())
        peso = float(seletor.sum()) / len(y_verdadeiro)
        erro_absoluto_ponderado += peso * abs(previsto - observado)
        faixas.append(
            {
                "faixa": faixa,
                "n": int(seletor.sum()),
                "previsto_medio": previsto,
                "observado_medio": observado,
            }
        )
    return {
        "brier": brier,
        "erro_calibracao_esperado": erro_absoluto_ponderado,
        "faixas": faixas,
    }


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
    """Árvores com tratamento nativo de nulo — não precisa imputar.

    **`early_stopping=False` é explícito, e a explicitação corrige um defeito
    (2026-08-25).** O padrão do scikit-learn é `'auto'`, que **liga sozinho
    quando `n > 10.000`. No walk-forward o treino cruza esse limiar no fold 21:
    21 folds treinavam 300 iterações fixas e 25 paravam cedo (o último com 111
    árvores). Três consequências, todas ruins:

    1. o estimador **não era o mesmo objeto** ao longo dos folds;
    2. o critério de parada saía de uma partição **aleatória e não temporal**
       de 10% do treino, misturando trimestres dentro da janela;
    3. a ressalva publicada "nenhum ajuste de hiperparâmetro foi feito" era
       **falsa** — o número de árvores estava sendo selecionado por fold, e a
       comparação boosting × logística não era equivalente, porque um braço
       tinha um ajustador implícito e o outro não.

    Efeito numérico: 0,8787 com `False` contra 0,8797 com `'auto'` (−0,0009,
    p = 0,20) — desprezível, o que só reforça que o problema era de contrato,
    não de desempenho.
    """
    return HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=20,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=SEMENTE,
    )


def construir_gradient_boosting_imputado() -> Pipeline:
    """Boosting com imputação explícita — **controle** do braço com SMOTE.

    O SMOTE interpola vizinhos e por isso **não tolera nulo**, enquanto o
    `HistGradientBoosting` trata nulo nativamente. Comparar SMOTE contra o
    boosting puro mediria duas mudanças ao mesmo tempo (reamostragem *e*
    imputação) e atribuiria a soma à reamostragem. Este braço existe para que a
    única diferença contra o braço SMOTE seja o SMOTE.
    """
    return Pipeline(
        [
            ("imputacao", SimpleImputer(strategy="median")),
            ("modelo", construir_gradient_boosting()),
        ]
    )


def construir_gradient_boosting_com_smote() -> "Pipeline":
    """Imputação → SMOTE → boosting.

    O `Pipeline` é o do `imblearn`, não o do scikit-learn, e a diferença é de
    correção: ele aplica a reamostragem **somente no `fit`**. Com o pipeline do
    scikit-learn o SMOTE rodaria também na predição, sintetizando linhas de
    validação e teste — vazamento grosseiro que infla o resultado.

    Sobre a expectativa: van den Goorbergh et al. (JAMIA 2022) mostram que
    reamostragem degrada calibração sem melhorar discriminação, e que deslocar
    o limiar obtém o mesmo ponto de operação. Aqui a classe positiva é 33% —
    desbalanceamento leve, longe do 1–5% para o qual o SMOTE foi desenhado.
    A medição existe para verificar isso no dado do projeto, não para adotá-lo.
    """
    from imblearn.over_sampling import SMOTE
    from imblearn.pipeline import Pipeline as PipelineImb

    return PipelineImb(
        [
            ("imputacao", SimpleImputer(strategy="median")),
            ("smote", SMOTE(random_state=SEMENTE)),
            ("modelo", construir_gradient_boosting()),
        ]
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


def escore_taxa_recente(alvo: pd.DataFrame) -> np.ndarray:
    """`taxa_prejuizos_4t` crua — **o baseline honesto**, e ele é duro.

    A persistência é preditor de **dois valores** e o AUC pune empate: no fold
    3T2025, 33,6% dos pares +/− ficam empatados e contam 0,5 cada. O ganho de
    +0,10 que o relatório publicava contra ela era, em ~87%, artefato de
    granularidade — não capacidade do modelo.

    Esta coluna já existe no painel, tem 7 níveis, e sozinha marca AUC 0,8646
    contra 0,8765 do boosting de 15 features. **A manchete honesta é +0,0138,
    não +0,10.** Com desempate por ROA (duas linhas de código) a diferença some
    de vez: +0,0015 de AUC (p = 0,33) e −0,0049 de AP — o modelo perde em AP.

    Achado das auditorias de 2026-08-25; ver `resultados/debate_modelo_*.md`.
    """
    return alvo["taxa_prejuizos_4t"].to_numpy(dtype=float)


def escore_identidade_implementavel(
    treino: pd.DataFrame, alvo: pd.DataFrame
) -> np.ndarray:
    """Taxa histórica de rótulo da PRÓPRIA companhia, só com o passado do fold.

    É o baseline que responde "o modelo sabe algo além de *quem* é esta
    companhia?". A resposta é sim, e com folga: o modelo bate esta referência
    por **+0,0744 de AUC, vencendo em 46/46 folds**.

    **A palavra "implementável" carrega o achado.** Uma primeira versão desta
    comparação usou a média do rótulo sobre o painel INTEIRO, incluindo os
    trimestres de teste, e marcou 0,8947 — acima do modelo. Era vazamento: essa
    média não é observável no momento da predição. Corrigida, cai para 0,8012.
    A lição vale além daqui: um baseline também precisa passar pela fronteira
    temporal, senão a conclusão inverte.

    Companhia sem histórico no fold recebe a taxa-base do treino.
    """
    por_companhia = treino.groupby("cd_cvm")["rotulo"].mean()
    padrao = float(treino["rotulo"].mean()) if len(treino) else 0.0
    return (
        alvo["cd_cvm"].map(por_companhia).astype(float).fillna(padrao).to_numpy()
    )


def escore_passeio_sazonal(alvo: pd.DataFrame) -> np.ndarray:
    """*Seasonal random walk*: o alvo T+1 repete o MESMO trimestre do ano anterior.

    Este — não a persistência de defasagem 1 — é o benchmark consagrado para
    lucro **trimestral**: a série tem sazonalidade forte, e a autocorrelação
    das diferenças sazonais chega a inverter de sinal na defasagem 4. Publicar
    só contra a persistência deixaria o modelo competir com um adversário
    fraco de propósito.

    Quando o trimestre do ano anterior não existe (companhia recém-listada,
    ~10% das linhas), cai para a persistência de defasagem 1 — é o que um
    analista faria, e deixar nulo excluiria justamente as empresas novas.
    """
    sazonal = alvo["prejuizo_no_mesmo_trimestre_do_ano_anterior"].to_numpy(
        dtype=float
    )
    reserva = alvo["prejuizo_em_t"].to_numpy(dtype=float)
    return np.where(np.isnan(sazonal), reserva, sazonal)


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


def dividir_walk_forward(
    painel: PainelSupervisionado,
    *,
    minimo_trimestres_treino: int = 12,
    purgar: bool = True,
) -> list[Divisao]:
    """Janela expansível: um fold por trimestre, treino sempre só no passado.

    É o desenho que a literatura de dado financeiro exige, e o que a versão
    de partição única não conseguia dar: com um fold só, o IC do AUC tinha
    largura 0,08 e nenhuma comparação de feature ou de modelo era resolvível.

    Para cada trimestre de teste `k`: validação é `k-1` (de onde sai o limiar,
    nunca do teste) e treino é tudo anterior a `k-1`.

    **Purga (`purgar=True`, padrão).** Separar por trimestre não basta quando o
    rótulo olha para frente: uma linha de treino em `o` tem rótulo que cobre
    `o+1 .. o+n`, e com `n = 2` isso alcança o trimestre de TESTE. O treino
    passaria a conter o desfecho do período avaliado — é o que López de Prado
    chama de necessidade de *purging*. A purga remove essas linhas exigindo que
    a janela do rótulo termine antes do teste.

    Para `n = 1` a purga não remove nada (o rótulo do último trimestre de
    treino alcança a validação, nunca o teste), então os números do alvo de um
    trimestre são idênticos com e sem ela — verificado em
    `tests/test_modelo.py::TestPurga`.

    **A validação também é purgada, e isso foi um vazamento real (2026-08-25).**
    A versão anterior punha a validação em `k−1`. Com `n = 2` o rótulo dessa
    linha cobre `{k, k+1}` e o do teste cobre `{k+1, k+2}` — **`k+1` é comum aos
    dois**. Como o limiar F2 sai da validação, *todo número dependente de
    limiar* estava contaminado. Agora a validação fica em
    `ordem_teste − 1 − n_alvo`, de onde a janela do rótulo dela termina antes
    do teste começar.

    Efeito medido no ponto de operação (46 folds, alvo persistente): fração
    sinalizada **42,9% → 34,5%**, recall 0,879 → 0,795, precisão 0,479 →
    0,534, F1 0,614 → **0,627**. A contaminação fazia o modelo parecer *pior*
    no critério que mais se criticava — sinalizar fatia grande demais da base.

    O teste-guarda que existia para isto (`TestPurga`) inspecionava só
    `divisao.treino` e por isso o vazamento sobreviveu a ele; hoje cobre
    `divisao.validacao` também.
    """
    quadro = painel.quadro
    n_alvo = painel.trimestres_consecutivos
    ordens = sorted(quadro["ordem"].unique().tolist())
    divisoes: list[Divisao] = []
    for indice in range(minimo_trimestres_treino + 1, len(ordens)):
        ordem_teste = ordens[indice]
        ordem_validacao = ordens[indice - 1]
        limite_treino = ordem_validacao
        if purgar:
            # Rótulo da validação cobre v+1 .. v+n; exigir v+n < ordem_teste.
            # Vale inclusive para n=1: a validação em k−1 tinha rótulo igual ao
            # desfecho DO PRÓPRIO trimestre de teste.
            ordem_validacao = ordem_teste - 1 - n_alvo
            limite_treino = min(ordem_validacao, ordem_teste - n_alvo)
        teste = quadro[quadro["ordem"] == ordem_teste]
        validacao = quadro[quadro["ordem"] == ordem_validacao]
        treino = quadro[quadro["ordem"] < limite_treino]
        if treino.empty or validacao.empty or teste.empty:
            continue
        if teste["rotulo"].nunique() < 2:
            continue  # AUC indefinido; fold inútil
        divisoes.append(
            Divisao(
                treino=treino,
                validacao=validacao,
                teste=teste,
                trimestre_validacao=str(validacao["trimestre"].iloc[0]),
                trimestre_teste=str(teste["trimestre"].iloc[0]),
            )
        )
    return divisoes


def comparar_pareado(
    por_fold: list[dict[str, object]], a: str, b: str
) -> dict[str, object] | None:
    """Compara dois modelos fold a fold — pareado, que é como tem de ser.

    Comparar médias soltas ignoraria que os folds são os mesmos para os dois e
    que a variação entre trimestres (0,79 a 0,91 de AUC) é muito maior que a
    diferença entre modelos. O pareamento cancela essa variação comum.
    """
    pares = [
        (float(linha[a]), float(linha[b]))
        for linha in por_fold
        if linha.get(a) is not None and linha.get(b) is not None
    ]
    if len(pares) < 3:
        return None
    diferencas = np.array([x - y for x, y in pares], dtype=float)
    n = len(diferencas)
    erro_padrao = float(diferencas.std(ddof=1) / np.sqrt(n))
    resultado: dict[str, object] = {
        "n_folds": n,
        "diferenca_media": float(diferencas.mean()),
        "ic95_inferior": float(diferencas.mean() - 1.96 * erro_padrao),
        "ic95_superior": float(diferencas.mean() + 1.96 * erro_padrao),
        "folds_vencidos": int((diferencas > 0).sum()),
    }

    # Diferença exatamente nula em TODOS os folds é resultado legítimo — é o
    # que a contraprova da purga no alvo de 1 trimestre produz, por construção.
    # O Wilcoxon é indefinido aí e devolve NaN, que `json.dumps` grava como
    # `NaN` — JSON inválido, que quebraria quem for reler o artefato. Então o
    # caso é nomeado em vez de propagado.
    if np.all(diferencas == 0.0):
        resultado["identicos"] = True
        resultado["p_wilcoxon"] = None
        return resultado
    resultado["identicos"] = False

    try:  # scipy é dependência do scikit-learn, mas não vale derrubar o relatório
        from scipy import stats

        p = float(stats.wilcoxon(diferencas).pvalue)
        resultado["p_wilcoxon"] = None if np.isnan(p) else p
    except Exception:  # pragma: no cover - ambiente sem scipy
        resultado["p_wilcoxon"] = None
    return resultado


def pontuar_walk_forward(
    painel: PainelSupervisionado,
    *,
    minimo_trimestres_treino: int = 12,
    colunas: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Empilha as predições de teste de TODOS os folds num quadro só.

    Existe para responder perguntas de recorte — "o modelo funciona em
    instituição financeira?", "e nas companhias hoje lucrativas?" — que por
    fold têm amostra pequena demais para AUC. Empilhar resolve a amostra ao
    custo de misturar trimestres; a contraprova está registrada: no painel
    inteiro o AUC empilhado dá 0,8765 contra 0,8797 da média por fold (alvo de
    2 trimestres, com purga), ou seja, a inflação por empilhamento é
    desprezível aqui.
    """
    colunas = list(colunas or COLUNAS_FEATURES)
    partes: list[pd.DataFrame] = []
    for divisao in dividir_walk_forward(
        painel, minimo_trimestres_treino=minimo_trimestres_treino
    ):
        modelo = construir_gradient_boosting()
        modelo.fit(divisao.treino[colunas], divisao.treino["rotulo"].to_numpy(int))
        parte = divisao.teste.copy()
        parte["escore"] = modelo.predict_proba(divisao.teste[colunas])[:, 1]
        partes.append(parte)
    if not partes:
        return pd.DataFrame(columns=[*colunas, "rotulo", "escore"])
    return pd.concat(partes, ignore_index=True)


def desempenho_por_recorte(
    pontuado: pd.DataFrame,
    recortes: dict[str, "pd.Series[bool]"],
    *,
    minimo_observacoes: int = 50,
    minimo_positivos: int = 20,
) -> dict[str, object]:
    """AUC, taxa-base e lift em cada recorte — com recusa explícita se raso.

    **A guarda que importa é `minimo_positivos`, não `minimo_observacoes`.** O
    recorte `instituição financeira ≥ R$100 bi` tem 189 observações, o que
    passaria folgado em qualquer corte por tamanho — e apenas **5 eventos
    positivos**. O AUC ali sai 0,971, número de aparência esplêndida e conteúdo
    nenhum: bastam dois pares trocados para ele desabar. Deixar isso virar
    linha de tabela seria o erro que este módulo existe para não cometer, então
    o recorte raso sai marcado como insuficiente em vez de marcado como
    excelente.
    """
    resultado: dict[str, object] = {}
    for nome, mascara in recortes.items():
        sub = pontuado[mascara.to_numpy() if hasattr(mascara, "to_numpy") else mascara]
        y = sub["rotulo"].to_numpy(dtype=int)
        n_positivos = int(y.sum())
        n_negativos = int(len(y) - n_positivos)
        if (
            len(sub) < minimo_observacoes
            or len(np.unique(y)) < 2
            or min(n_positivos, n_negativos) < minimo_positivos
        ):
            resultado[nome] = {
                "n": len(sub),
                "n_positivos": n_positivos,
                "suficiente": False,
                "motivo_insuficiente": (
                    "poucos eventos da classe minoritária"
                    if len(sub) >= minimo_observacoes
                    else "amostra pequena"
                ),
            }
            continue
        escore = sub["escore"].to_numpy(dtype=float)
        rank = metricas_de_ranqueamento(y, escore)
        resultado[nome] = {
            "n": len(sub),
            "n_positivos": n_positivos,
            "suficiente": True,
            "taxa_base": float(y.mean()),
            "roc_auc": float(roc_auc_score(y, escore)),
            "lift_topo_10pct": rank["lift_topo_10pct"],
            "precisao_topo_10pct": rank["precisao_topo_10pct"],
        }
    return resultado


def auc_within_companhia(pontuado: pd.DataFrame) -> dict[str, object]:
    """AUC calculado DENTRO de cada companhia, ao longo do tempo.

    **É o número que impede ler o agregado como antecipação temporal**, e a
    diferença entre os dois é o achado central das auditorias de 2026-08-25:
    agregado ~0,88, *within*-companhia ~0,62. O modelo ordena **quais**
    companhias são cronicamente deficitárias, não **quando** uma vira.

    Duas contraprovas que fecham a leitura:

    * `taxa_prejuizos_4t` sozinha tem *within* praticamente idêntico (0,6232
      contra 0,6220) — mesmo dentro da companhia, as 15 features não agregam
      nada sobre uma coluna;
    * um escore constante por companhia tem *within* exatamente 0,5000 por
      construção. Um preditor que marca 0,90 agregado e 0,50 intra-companhia é,
      por definição, métrica entre companhias.

    Conta pares concordantes/discordantes só entre linhas da MESMA companhia,
    ponderando pelo número de pares — companhia sem as duas classes não entra.
    """
    concordantes = empatados = total = 0
    n_companhias = 0
    for _, grupo in pontuado.groupby("cd_cvm"):
        y = grupo["rotulo"].to_numpy(dtype=int)
        if len(np.unique(y)) < 2:
            continue
        n_companhias += 1
        escore = grupo["escore"].to_numpy(dtype=float)
        positivos, negativos = escore[y == 1], escore[y == 0]
        diferenca = positivos[:, None] - negativos[None, :]
        concordantes += int((diferenca > 0).sum())
        empatados += int((diferenca == 0).sum())
        total += diferenca.size
    if not total:
        return {"auc": None, "n_companhias": 0, "n_pares": 0}
    return {
        "auc": float((concordantes + 0.5 * empatados) / total),
        "n_companhias": n_companhias,
        "n_pares": total,
    }


def composicao_do_topo(
    pontuado: pd.DataFrame, *, fracao: float = 0.10
) -> dict[str, object]:
    """Quem está no topo da lista — o número que qualifica todo lift.

    Lift de 3,3 no painel inteiro soa como triagem até se olhar de quem é a
    lista: **97,8% do decil superior já está em prejuízo em T** (contra 33% do
    painel) e 99,9% tem `taxa_prejuizos_4t` ≥ 0,5. Não é alerta antecipado, é
    uma lista de deficitárias crônicas reproduzível por um `WHERE`.

    Por isso lift nunca deve ser publicado sozinho: sem esta linha ao lado, ele
    é lido como capacidade que o módulo não tem.
    """
    n = len(pontuado)
    if not n:
        return {}
    k = max(1, int(round(n * fracao)))
    ordem = np.argsort(-pontuado["escore"].to_numpy(dtype=float), kind="stable")
    topo = pontuado.iloc[ordem[:k]]
    return {
        "fracao": fracao,
        "n_no_topo": int(k),
        "ja_em_prejuizo_no_topo": float(topo["prejuizo_em_t"].mean()),
        "ja_em_prejuizo_no_painel": float(pontuado["prejuizo_em_t"].mean()),
        "taxa_4t_alta_no_topo": float(
            (topo["taxa_prejuizos_4t"] >= 0.5).mean()
        ),
        "n_companhias_distintas_no_topo": int(topo["cd_cvm"].nunique()),
    }


def desempenho_por_estado(
    pontuado: pd.DataFrame, *, minimo_observacoes: int = 50
) -> dict[str, object]:
    """O recorte que responde "o modelo é a persistência com passos extras?".

    A regra de persistência prevê constante zero entre companhias hoje
    lucrativas — AUC indefinido, discriminação nenhuma. Se o modelo ordenar
    bem JUSTAMENTE nesse subconjunto, ele não é a regra simples com verniz. É
    a evidência mais forte de utilidade que o módulo tem, e por isso é função
    e não script solto.
    """
    return desempenho_por_recorte(
        pontuado,
        {
            "ja_em_prejuizo": pontuado["prejuizo_em_t"] == 1,
            "lucrativa_hoje": pontuado["prejuizo_em_t"] == 0,
        },
        minimo_observacoes=minimo_observacoes,
    )


#: Features que só existem com janela longa (ver AGENTS.md §3.5).
GRUPO_SAZONAL: tuple[str, ...] = (
    "prejuizo_no_mesmo_trimestre_do_ano_anterior",
    "variacao_lucro_anual",
    "taxa_prejuizos_4t",
    "trimestre_do_ano",
)


def ablacao_walk_forward(
    painel: PainelSupervisionado,
    grupo: Sequence[str],
    *,
    minimo_trimestres_treino: int = 12,
) -> dict[str, object]:
    """Mede a contribuição de um grupo de features ao longo de todos os folds.

    Existe porque a versão de partição única não conseguia resolver isto: o IC
    da diferença incluía zero e a resposta ficava "não demonstrado".
    """
    completo = list(COLUNAS_FEATURES)
    reduzido = [c for c in completo if c not in set(grupo)]
    if len(reduzido) == len(completo):
        raise ValueError(f"nenhuma das features do grupo está em uso: {grupo!r}")

    por_fold: list[dict[str, object]] = []
    for divisao in dividir_walk_forward(
        painel, minimo_trimestres_treino=minimo_trimestres_treino
    ):
        y_treino = divisao.treino["rotulo"].to_numpy(dtype=int)
        y_teste = divisao.teste["rotulo"].to_numpy(dtype=int)
        linha: dict[str, object] = {"trimestre_teste": divisao.trimestre_teste}
        for rotulo, colunas in (("completo", completo), ("reduzido", reduzido)):
            modelo = construir_gradient_boosting()
            modelo.fit(divisao.treino[colunas], y_treino)
            escore = modelo.predict_proba(divisao.teste[colunas])[:, 1]
            linha[rotulo] = avaliar(rotulo, y_teste, escore, limiar=0.5).roc_auc
        por_fold.append(linha)

    return {
        "grupo": list(grupo),
        "modelo": "gradient_boosting",
        "auc_completo": float(
            np.mean([linha["completo"] for linha in por_fold])
        ),
        "auc_sem_o_grupo": float(
            np.mean([linha["reduzido"] for linha in por_fold])
        ),
        "comparacao": comparar_pareado(por_fold, "completo", "reduzido"),
    }


def avaliar_walk_forward(
    painel: PainelSupervisionado, *, minimo_trimestres_treino: int = 12
) -> dict[str, object]:
    """Roda todos os folds e agrega — média, desvio e IC 95% empírico."""
    colunas = list(COLUNAS_FEATURES)
    por_modelo: dict[str, list[float]] = {}
    por_fold: list[dict[str, object]] = []
    divisoes = dividir_walk_forward(
        painel, minimo_trimestres_treino=minimo_trimestres_treino
    )

    for divisao in divisoes:
        y_treino = divisao.treino["rotulo"].to_numpy(dtype=int)
        y_teste = divisao.teste["rotulo"].to_numpy(dtype=int)
        linha: dict[str, object] = {
            "trimestre_teste": divisao.trimestre_teste,
            "n_treino": len(divisao.treino),
            "n_teste": len(divisao.teste),
        }

        for nome, escore in (
            ("baseline_persistencia", escore_persistencia(divisao.teste)),
            ("baseline_passeio_sazonal", escore_passeio_sazonal(divisao.teste)),
            # Os dois baselines que as auditorias de 2026-08-25 exigiram: um de
            # granularidade equivalente (a persistência é binária e o AUC pune
            # empate) e um que testa se o modelo sabe algo além de QUEM é a
            # companhia. Publicar só contra a persistência inflava o ganho.
            ("baseline_taxa_recente", escore_taxa_recente(divisao.teste)),
            (
                "baseline_identidade",
                escore_identidade_implementavel(divisao.treino, divisao.teste),
            ),
        ):
            auc = avaliar(nome, y_teste, escore, limiar=0.5).roc_auc
            if auc is not None:
                por_modelo.setdefault(nome, []).append(auc)
                linha[nome] = auc

        for nome, modelo in (
            ("regressao_logistica", construir_regressao_logistica()),
            ("gradient_boosting", construir_gradient_boosting()),
        ):
            modelo.fit(divisao.treino[colunas], y_treino)
            escore = modelo.predict_proba(divisao.teste[colunas])[:, 1]
            auc = avaliar(nome, y_teste, escore, limiar=0.5).roc_auc
            if auc is not None:
                por_modelo.setdefault(nome, []).append(auc)
                linha[nome] = auc
        por_fold.append(linha)

    resumo: dict[str, object] = {}
    for nome, valores in por_modelo.items():
        vetor = np.asarray(valores, dtype=float)
        resumo[nome] = {
            "n_folds": int(len(vetor)),
            "auc_medio": float(vetor.mean()),
            "auc_desvio": float(vetor.std(ddof=1)) if len(vetor) > 1 else 0.0,
            "auc_ic95_inferior": float(np.percentile(vetor, 2.5)),
            "auc_ic95_superior": float(np.percentile(vetor, 97.5)),
        }
    ordenados = sorted(resumo, key=lambda n: -resumo[n]["auc_medio"])
    comparacoes: dict[str, object] = {}
    for i, melhor in enumerate(ordenados):
        for pior in ordenados[i + 1:]:
            teste = comparar_pareado(por_fold, melhor, pior)
            if teste is not None:
                comparacoes[f"{melhor} - {pior}"] = teste

    # Decomposição obrigatória: sem ela o leitor lê o agregado como capacidade
    # de antecipação temporal, que o módulo não tem.
    pontuado = pontuar_walk_forward(
        painel, minimo_trimestres_treino=minimo_trimestres_treino
    )
    return {
        "n_folds": len(divisoes),
        "resumo": resumo,
        "comparacoes_pareadas": comparacoes,
        "decomposicao": {
            "auc_within_companhia": auc_within_companhia(pontuado),
            "composicao_do_topo": composicao_do_topo(pontuado),
            "leitura": (
                "AUC agregado alto com AUC within-companhia perto de 0,65 "
                "significa que o modelo ordena QUAIS companhias são "
                "cronicamente deficitárias, não QUANDO uma vira. O decil "
                "superior é majoritariamente composto de companhias que já "
                "estão em prejuízo — lift não deve ser lido como triagem "
                "antecipada sem esta linha ao lado."
            ),
        },
        "por_fold": por_fold,
    }


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
