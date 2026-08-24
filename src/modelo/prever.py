"""Aplicação do modelo — e a fronteira da RN07, escrita em código.

**O que este módulo NÃO faz, por decisão registrada (spec 5.10):** responder
"qual a chance de o <banco> reportar prejuízo no próximo trimestre?". Três
motivos, em ordem de peso:

1. **Coerência com o próprio guardrail.** O sistema recusa "vale a pena
   comprar ações do BB?" invocando a Res. CVM 20/2021. Emitir, na pergunta
   seguinte, um juízo prospectivo sobre emissor identificado num aplicativo
   aberto é a mesma fronteira na direção oposta.
2. **A regra de domínio já o anulava.** O modelo é treinado majoritariamente
   sobre companhias não financeiras, cuja estrutura patrimonial difere de um
   banco.
3. **A saída seria constante.** Nenhum dos cinco bancos do corpus reportou
   prejuízo em nenhum trimestre observado.

`prever_para_companhia` existe **para recusar** — deixar a fronteira como
função que levanta erro é mais difícil de contornar por acidente do que
deixá-la como parágrafo de documentação.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

from src.modelo.construir_painel import COLUNAS_FEATURES


class PrevisaoPorCompanhiaBloqueadaError(RuntimeError):
    """RN07: previsão sobre emissor nomeado não é exposta como resposta."""


def prever_para_companhia(*_args: object, **_kwargs: object) -> None:
    """Sempre levanta. É a fronteira da RN07, não um recurso inacabado."""
    raise PrevisaoPorCompanhiaBloqueadaError(
        "RN07: o modelo preditivo não responde sobre companhia nomeada. Ele "
        "roda offline e publica desempenho contra baselines; juízo prospectivo "
        "sobre emissor identificado é a fronteira das Res. CVM 19 e 20/2021, a "
        "mesma que a RN05 protege no sentido oposto."
    )


def pontuar(modelo: object, quadro: pd.DataFrame) -> np.ndarray:
    """Escore contínuo para uso **interno** de avaliação e ordenação agregada.

    Não devolve identificador de companhia de propósito: quem quiser ligar o
    escore a um emissor precisa fazê-lo explicitamente, e aí a RN07 se aplica.
    """
    faltantes = [c for c in COLUNAS_FEATURES if c not in quadro.columns]
    if faltantes:
        raise ValueError(f"features ausentes para pontuar: {faltantes}")
    return np.asarray(
        modelo.predict_proba(quadro[list(COLUNAS_FEATURES)])[:, 1], dtype=float
    )


@dataclass(frozen=True)
class ContrasteCorpusPainel:
    """Leitura retrospectiva de dado arquivado — não é previsão.

    É o segundo entregável da 5.10: as instituições do corpus operaram, na
    janela observada, num regime de risco distinto do mercado como um todo.
    """

    n_observacoes_corpus: int
    n_prejuizos_corpus: int
    n_observacoes_painel: int
    n_prejuizos_painel: int

    @property
    def taxa_corpus(self) -> float:
        if not self.n_observacoes_corpus:
            return 0.0
        return self.n_prejuizos_corpus / self.n_observacoes_corpus

    @property
    def taxa_painel(self) -> float:
        if not self.n_observacoes_painel:
            return 0.0
        return self.n_prejuizos_painel / self.n_observacoes_painel

    def como_dict(self) -> dict[str, object]:
        return {
            "n_observacoes_corpus": self.n_observacoes_corpus,
            "n_prejuizos_corpus": self.n_prejuizos_corpus,
            "taxa_prejuizo_corpus": self.taxa_corpus,
            "n_observacoes_painel": self.n_observacoes_painel,
            "n_prejuizos_painel": self.n_prejuizos_painel,
            "taxa_prejuizo_painel": self.taxa_painel,
        }


def contrastar_corpus_e_painel(
    con: duckdb.DuckDBPyConnection,
) -> ContrasteCorpusPainel:
    """Compara a frequência de prejuízo do corpus com a do painel inteiro.

    As companhias do corpus são as que têm `ticker` registrado — o mesmo
    critério usado na carga para marcar quem entrou pela lista do projeto.
    """
    linha = con.execute(
        """
        WITH marcado AS (
            SELECT
                i.lucro_liquido_consolidado AS lucro,
                (c.ticker IS NOT NULL)      AS do_corpus
            FROM indicadores i
            JOIN companhias c USING (cd_cvm)
            WHERE i.lucro_liquido_consolidado IS NOT NULL
        )
        SELECT
            sum(CASE WHEN do_corpus THEN 1 ELSE 0 END),
            sum(CASE WHEN do_corpus AND lucro < 0 THEN 1 ELSE 0 END),
            count(*),
            sum(CASE WHEN lucro < 0 THEN 1 ELSE 0 END)
        FROM marcado
        """
    ).fetchone()
    return ContrasteCorpusPainel(
        n_observacoes_corpus=int(linha[0] or 0),
        n_prejuizos_corpus=int(linha[1] or 0),
        n_observacoes_painel=int(linha[2] or 0),
        n_prejuizos_painel=int(linha[3] or 0),
    )
