"""Os instrumentos das medições de 2026-10-20 (ajustes da Etapa 2).

Sem rede, sem LLM e sem painel: travam o que cada número publicado depende.
- `reaplicar_guarda_rn02.desfecho` lê o caminho da resposta pelo motivo que o
  código grava; trocar a frase do motivo sem trocar aqui mudaria a contagem.
- `medir_virada_lucrativas.auc_intra` é o AUC dentro da companhia, com
  bootstrap por companhia (§4.4, regra 8).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts import reaplicar_guarda_rn02 as reaplicar
from src.geracao import RespostaGerada


class TestDesfechoDaReaplicacao:
    @pytest.mark.parametrize(
        "recusa,motivo,invalido,esperado",
        [
            (False, None, False, reaplicar.PUBLICADA),
            (True, "Rebaixada por RN01: afirmação sem citação.", False, reaplicar.RN01),
            (
                True,
                "Rebaixada por RN02: ao menos um valor numérico da resposta não "
                "aparece nos trechos citados.",
                False,
                reaplicar.RN02_NUMERO,
            ),
            (
                True,
                "Rebaixada por RN02: as citações não cobrem todas as "
                "instituições e períodos pedidos.",
                False,
                reaplicar.RN02_ESCOPO,
            ),
            (True, "Não há evidência suficiente nos trechos recuperados.", False, reaplicar.RECUSA_MODELO),
            (True, "JSON inválido", True, reaplicar.JSON_INVALIDO),
        ],
    )
    def test_motivo_gravado_vira_desfecho(self, recusa, motivo, invalido, esperado):
        gravada = {"recusa": recusa, "motivo_recusa": motivo, "json_invalido": invalido}
        assert reaplicar.desfecho(gravada) == esperado
        objeto = RespostaGerada(
            resposta=None if recusa else "r", recusa=recusa, motivo_recusa=motivo,
            citacoes=(), bruto="", json_reparado=False, json_invalido=invalido,
        )
        assert reaplicar.desfecho(objeto) == esperado

    def test_motivos_do_codigo_sao_os_que_a_reaplicacao_conhece(self):
        """Se a geração mudar a frase, este teste cai antes da contagem."""
        import inspect

        from src import geracao

        fonte = inspect.getsource(geracao.aplicar_guardas_pos_llm)
        assert '"Rebaixada por RN01' in fonte
        assert '"Rebaixada por RN02: ao menos um valor numérico' in fonte
        assert '"Rebaixada por RN02: as citações não cobrem' in fonte


class TestAucIntraCompanhia:
    def _dados(self, escores):
        linhas = []
        for cd_cvm, pares in escores.items():
            for rotulo, escore in pares:
                linhas.append({"cd_cvm": cd_cvm, "rotulo": rotulo, "s": escore})
        return pd.DataFrame(linhas)

    def test_ordem_perfeita_dentro_da_companhia_e_um(self):
        from scripts.medir_virada_lucrativas import auc_intra

        dados = self._dados({1: [(1, 0.9), (0, 0.1)], 2: [(1, 0.3), (0, 0.2)]})
        resultado = auc_intra(dados, "s", np.random.default_rng(0))
        assert resultado["auc"] == 1.0 and resultado["n_companhias"] == 2

    def test_escore_constante_por_companhia_e_meio(self):
        """Ordenar companhias e não o momento dá 0,5 por construção."""
        from scripts.medir_virada_lucrativas import auc_intra

        dados = self._dados({1: [(1, 0.9), (0, 0.9)], 2: [(1, 0.1), (0, 0.1), (0, 0.1)]})
        assert auc_intra(dados, "s", np.random.default_rng(0))["auc"] == 0.5

    def test_companhia_sem_as_duas_classes_fica_fora(self):
        from scripts.medir_virada_lucrativas import auc_intra

        dados = self._dados({1: [(1, 0.9), (0, 0.1)], 2: [(0, 0.5), (0, 0.4)]})
        assert auc_intra(dados, "s", np.random.default_rng(0))["n_companhias"] == 1
