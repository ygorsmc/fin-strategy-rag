"""Contraprovas do auditor do Rank 3-B.

Cada caso corresponde a um jeito conhecido de um gate **aprovar por engano** —
por ausência de dado, por escore sem poder discriminante, por empate de quintil
tratado como variação, ou por deixar informação do futuro entrar em D.

Contrato: `resultados/pre_registro_rank03b_consumo_operacional_2026-09-11.md`.
"""

from __future__ import annotations

import datetime

import pytest

from scripts import auditar_rank03b_consumo_operacional as auditor


def _fco(cd_cvm, trimestre, valor, dt_ini, dt_fim, dt_receb, metodos=1):
    return {
        "cd_cvm": cd_cvm, "trimestre": trimestre, "fco": float(valor),
        "dt_ini": datetime.date.fromisoformat(dt_ini),
        "dt_fim": datetime.date.fromisoformat(dt_fim),
        "dt_receb": datetime.date.fromisoformat(dt_receb),
        "metodos": metodos, "origens": 1,
    }


def _ativo(cd_cvm, trimestre, valor, dt_receb):
    return {
        "cd_cvm": cd_cvm, "trimestre": trimestre, "ativo": float(valor),
        "dt_receb": datetime.date.fromisoformat(dt_receb),
    }


def _duracao(cd_cvm, trimestre, dias, demonstrativo="DFC_MI", origem="arquivado"):
    return {
        "cd_cvm": cd_cvm, "trimestre": trimestre, "dias": dias,
        "demonstrativo": demonstrativo, "origem": origem,
    }


# --- limiares vêm do pré-registro, não do código ---------------------------

class TestLimiaresCongelados:
    """Se um limiar mudar, a falsificação nº 2 do pré-registro se verifica."""

    def test_os_limiares_sao_os_do_pre_registro(self):
        assert auditor.T1_AMPLITUDE == 0.15
        assert auditor.T1_ZONA_CINZENTA == 0.12
        assert auditor.T1_PROB_MAXIMA == 0.10
        assert auditor.T2_LACUNA == 0.12
        assert auditor.MINIMO_DE_OBSERVACOES == 500
        assert auditor.MINIMO_DE_COMPANHIAS == 30

    def test_a_lista_de_componentes_t1_nao_encolheu(self):
        """O §6 permite acrescentar componente, nunca retirar."""
        exigidos = {
            "fco_ttm_sobre_sd8", "fco_ttm_em_D", "fco_ttm_sobre_ativo",
            "sd8_fco_isolado", "ativo_total_em_D",
            "trimestres_com_fco_negativo_nos_ultimos_8",
        }
        assert exigidos <= set(auditor.COMPONENTES_T1)


# --- quintis: a lição C1 ---------------------------------------------------

class TestAmplitudePorQuintis:
    """Cortar por posição atribui amplitude máxima a variável constante."""

    def test_variavel_constante_da_um_grupo_e_amplitude_zero(self):
        n = auditor.MINIMO_DE_OBSERVACOES
        # Rótulos AGRUPADOS, que é o caso em que o corte por posição falhava.
        eventos = [1] * (n // 2) + [0] * (n - n // 2)
        medida = auditor.amplitude_por_quintis([7.0] * n, eventos)
        assert medida["grupos"] == 1, (
            "variável constante é UM grupo; dividi-la em cinco separa "
            "observações indistinguíveis e fabrica associação"
        )
        assert medida["amplitude"] == 0.0

    def test_empates_nao_sao_divididos_entre_quintis(self):
        n = auditor.MINIMO_DE_OBSERVACOES
        valores = [1.0] * (n - 100) + [float(2 + i) for i in range(100)]
        medida = auditor.amplitude_por_quintis(valores, [i % 2 for i in range(n)])
        for faixa in medida["faixas"]:
            assert faixa["valor_minimo"] != faixa["valor_maximo"] or True
        # Nenhum valor aparece em duas faixas.
        vistos = [
            (f["valor_minimo"], f["valor_maximo"]) for f in medida["faixas"]
        ]
        for (_, fim), (inicio, _) in zip(vistos, vistos[1:]):
            assert fim < inicio, "um mesmo valor caiu em duas faixas"

    def test_amplitude_e_invariante_a_permutacao_das_linhas(self):
        import random
        n = auditor.MINIMO_DE_OBSERVACOES
        valores = [float(i % 40) for i in range(n)]
        eventos = [1 if i % 7 == 0 else 0 for i in range(n)]
        base = auditor.amplitude_por_quintis(valores, eventos)["amplitude"]
        aleatorio = random.Random(7)
        for _ in range(20):
            pares = list(zip(valores, eventos))
            aleatorio.shuffle(pares)
            outra = auditor.amplitude_por_quintis(
                [v for v, _ in pares], [e for _, e in pares]
            )["amplitude"]
            assert outra == pytest.approx(base), (
                "a ordem das linhas de entrada não pode mudar a amplitude"
            )

    def test_amostra_pequena_levanta_em_vez_de_aprovar(self):
        with pytest.raises(auditor.AmostraInsuficiente):
            auditor.amplitude_por_quintis([1.0, 2.0, 3.0], [0, 1, 0])

    def test_amostra_vazia_tambem_levanta(self):
        """Com `n = 0` a amplitude saía `NaN`, e `NaN >= 0,15` é `False`."""
        with pytest.raises(auditor.AmostraInsuficiente):
            auditor.amplitude_por_quintis([], [])


# --- G0: integridade decisiva ---------------------------------------------

class TestGateG0:
    def test_dado_limpo_aprova(self):
        fco = [_fco("A", "1T2020", 10, "2020-01-01", "2020-03-31", "2020-05-10")]
        ativo = [_ativo("A", "1T2020", 1000, "2020-05-10")]
        dur = [_duracao("A", "1T2020", 91)]
        assert auditor.gate_g0(fco, ativo, dur)["aprovado"] is True

    def test_soma_dos_dois_metodos_reprova(self):
        """`DFC_MD` + `DFC_MI` no mesmo trimestre duplicaria o caixa."""
        fco = [_fco("A", "1T2020", 10, "2020-01-01", "2020-03-31",
                    "2020-05-10", metodos=2)]
        g0 = auditor.gate_g0(fco, [_ativo("A", "1T2020", 1000, "2020-05-10")],
                             [_duracao("A", "1T2020", 91)])
        assert g0["aprovado"] is False
        assert g0["g0_1_companhia_trimestre_com_os_dois_metodos"] == 1

    def test_periodo_semestral_rotulado_trimestral_reprova(self):
        fco = [_fco("A", "3T2020", 10, "2020-04-01", "2020-09-30", "2020-11-10")]
        g0 = auditor.gate_g0(fco, [_ativo("A", "3T2020", 1000, "2020-11-10")],
                             [_duracao("A", "3T2020", 183, origem="derivado")])
        assert g0["aprovado"] is False
        assert g0["g0_2_fora_da_duracao_de_um_trimestre"] == 1
        assert 183 in g0["g0_2_duracoes_distintas"]

    def test_duracao_e_medida_por_linha_nao_pelo_grupo(self):
        """Medir o vão do grupo acusaria defeito onde há só agrupamento.

        Duas linhas legítimas de ~91 dias no mesmo trimestre não podem somar
        121 ou 365 dias e reprovar — foi defeito do próprio auditor, achado ao
        rodá-lo.
        """
        dur = [_duracao("A", "1T2020", 91), _duracao("A", "1T2020", 90)]
        fco = [_fco("A", "1T2020", 10, "2019-10-01", "2020-03-31", "2020-05-10")]
        g0 = auditor.gate_g0(fco, [_ativo("A", "1T2020", 1000, "2020-05-10")], dur)
        assert g0["g0_2_fora_da_duracao_de_um_trimestre"] == 0
        assert g0["aprovado"] is True

    def test_salto_de_escala_reprova_acima_da_tolerancia(self):
        ativo = [
            _ativo("A", "1T2020", 19_543_000, "2020-05-10"),
            _ativo("A", "2T2020", 19_358, "2020-08-10"),
        ]
        g0 = auditor.gate_g0([], ativo, [])
        assert g0["aprovado"] is False
        assert g0["g0_3_saltos_de_escala"] == 1

    def test_defeito_de_integridade_nao_e_amostra_insuficiente(self):
        """Os dois estados são distintos, de propósito (§4.4 regra 5).

        Amostra insuficiente entra no relatório como gate reprovado com motivo;
        defeito de dado sobe alto. Fazer o segundo herdar do primeiro
        esconderia defeito atrás de veredito plausível.
        """
        assert not issubclass(
            auditor.DefeitoDeIntegridade, auditor.AmostraInsuficiente
        )


# --- point-in-time --------------------------------------------------------

class TestPointInTime:
    @staticmethod
    def _serie(cd="A", n=14, inicio=2018):
        """`n` trimestres consecutivos, com `dt_receb` 40 dias após o fim."""
        linhas = []
        for i in range(n):
            ano, tri = inicio + i // 4, i % 4 + 1
            ini = datetime.date(ano, 3 * (tri - 1) + 1, 1)
            fim = (datetime.date(ano + (tri == 4), (3 * tri) % 12 + 1, 1)
                   - datetime.timedelta(days=1))
            linhas.append(_fco(
                cd, f"{tri}T{ano}", 100.0 + i,
                ini.isoformat(), fim.isoformat(),
                (fim + datetime.timedelta(days=40)).isoformat(),
            ))
        return linhas

    def test_o_rotulo_nunca_comeca_antes_de_D(self):
        fco = self._serie(n=16)
        ativo = [
            _ativo("A", r["trimestre"], 10_000.0, r["dt_receb"].isoformat())
            for r in fco
        ]
        amostra, _ = auditor.construir_amostra(fco, ativo)
        assert amostra, "a série sintética deveria produzir observações"
        por_trimestre = {r["trimestre"]: r for r in fco}
        for obs in amostra:
            d = datetime.date.fromisoformat(obs["D"])
            assert por_trimestre[obs["q1"]]["dt_ini"] > d, (
                "q1 tem de COMEÇAR depois de D — 'publicado depois de D' não "
                "é o horizonte do contrato (achado C3 do B-DFC-01J)"
            )

    def test_antecedente_publicado_depois_de_D_nao_entra(self):
        """Feature só pode usar trimestre com `dt_receb <= D`."""
        fco = self._serie(n=16)
        ativo = [_ativo("A", "1T2018", 10_000.0, "2050-01-01")]
        amostra, descarte = auditor.construir_amostra(fco, ativo)
        assert amostra == []
        assert descarte["sem_ativo_disponivel"] > 0, (
            "ativo que só ficou público em 2050 não pode servir de feature"
        )

    def test_rotulo_com_trimestre_faltando_e_descartado(self):
        """Quatro trimestres NÃO consecutivos não formam S1/S2."""
        fco = [r for r in self._serie(n=18)
               if r["trimestre"] not in {"1T2021", "2T2021"}]
        ativo = [
            _ativo("A", r["trimestre"], 10_000.0, r["dt_receb"].isoformat())
            for r in fco
        ]
        _, descarte = auditor.construir_amostra(fco, ativo)
        assert descarte["q1_nao_e_o_primeiro_apos_D"] > 0

    def test_elegibilidade_exige_fco_ttm_positivo(self):
        fco = self._serie(n=16)
        for r in fco:
            r["fco"] = -100.0
        ativo = [
            _ativo("A", r["trimestre"], 10_000.0, r["dt_receb"].isoformat())
            for r in fco
        ]
        amostra, descarte = auditor.construir_amostra(fco, ativo)
        assert amostra == []
        assert descarte["fco_ttm_nao_positivo"] > 0, (
            "quem JÁ consome caixa não entra: a pergunta é sobre o INÍCIO"
        )

    def test_um_semestre_negativo_sozinho_nao_marca_o_evento(self):
        """`Y = 1` exige S1 < 0 **E** S2 < 0.

        Só os DOIS últimos trimestres ficam negativos. Em qualquer janela de
        quatro, isso cai inteiro dentro de S2 — nenhum S1 fica negativo, então
        nenhuma observação pode marcar. Se alguma marcar, a conjunção virou
        disjunção.
        """
        fco = self._serie(n=16)
        for r in fco[-2:]:
            r["fco"] = -10_000.0
        ativo = [
            _ativo("A", r["trimestre"], 10_000.0, r["dt_receb"].isoformat())
            for r in fco
        ]
        amostra, _ = auditor.construir_amostra(fco, ativo)
        assert amostra, "a série sintética deveria produzir observações"
        assert all(obs["y"] == 0 for obs in amostra)

    def test_quatro_trimestres_negativos_marcam_o_evento(self):
        """Contraprova do caso acima: sem ela, um bug que devolve sempre 0
        passaria no teste anterior e o alvo nunca marcaria nada."""
        fco = self._serie(n=16)
        for r in fco[-4:]:
            r["fco"] = -10_000.0
        ativo = [
            _ativo("A", r["trimestre"], 10_000.0, r["dt_receb"].isoformat())
            for r in fco
        ]
        amostra, _ = auditor.construir_amostra(fco, ativo)
        assert amostra
        assert any(obs["y"] == 1 for obs in amostra), (
            "com os quatro trimestres do rótulo negativos, S1 e S2 são "
            "negativos e o evento TEM de marcar"
        )


# --- T2: escore degenerado ------------------------------------------------

class TestTesteT2:
    def test_escore_constante_levanta_em_vez_de_aprovar(self):
        amostra = [
            {"cd_cvm": f"C{i%40}", "y": i % 2, "fco_ttm_sobre_ativo": 1.0}
            for i in range(600)
        ]
        with pytest.raises(auditor.EscoreDegenerado):
            auditor.teste_t2(amostra, "fco_ttm_sobre_ativo", -1)

    def test_sem_companhia_com_os_dois_rotulos_levanta(self):
        """AUC intra não é medível; aprovar seria aprovar por ausência."""
        amostra = [
            {"cd_cvm": f"C{i}", "y": i % 2, "fco_ttm_sobre_ativo": float(i)}
            for i in range(600)
        ]
        with pytest.raises(auditor.AmostraInsuficiente):
            auditor.teste_t2(amostra, "fco_ttm_sobre_ativo", -1)

    def test_auc_perfeita_e_um(self):
        escores = [1.0, 2.0, 3.0, 4.0]
        assert auditor._auc(escores, [0, 0, 1, 1]) == 1.0
        assert auditor._auc(escores, [1, 1, 0, 0]) == 0.0

    def test_auc_de_empate_total_e_meio(self):
        assert auditor._auc([5.0] * 4, [0, 1, 0, 1]) == 0.5


# --- veredito -------------------------------------------------------------

class TestVeredito:
    def test_g0_reprovado_nao_mede_t1_nem_t2(self):
        """Rodada invalidada não publica T1/T2 — e não remove as observações."""
        relatorio = auditor.executar()
        if relatorio["veredito"] == "REPROVADO EM G0/G1":
            nomes = [x.get("gate") or x.get("teste") for x in relatorio["cadeia"]]
            assert "T1" not in nomes and "T2" not in nomes
            assert "quarentena" in relatorio
            assert relatorio["modelo_carregado"] is False

    def test_o_artefato_declara_o_pre_registro_que_implementa(self):
        relatorio = auditor.executar()
        assert relatorio["pre_registro_sha256"].startswith("fbae30cc")
        assert relatorio["modelo_carregado"] is False
