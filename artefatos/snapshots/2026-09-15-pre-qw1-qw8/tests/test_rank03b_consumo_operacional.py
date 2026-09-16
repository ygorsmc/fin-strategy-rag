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


def _fco(cd_cvm, trimestre, valor, dt_ini, dt_fim, dt_receb,
         demonstrativo="DFC_MI", versao=1, origem="arquivado"):
    """Uma LINHA-FONTE de FCO (contrato R1.1), não um grupo agregado."""
    return {
        "cd_cvm": cd_cvm, "trimestre": trimestre, "fco": float(valor),
        "dt_ini": datetime.date.fromisoformat(dt_ini),
        "dt_fim": datetime.date.fromisoformat(dt_fim),
        "dt_receb": datetime.date.fromisoformat(dt_receb),
        "demonstrativo": demonstrativo, "versao": versao, "origem": origem,
    }


def _ativo(cd_cvm, trimestre, valor, dt_receb, versao=1):
    return {
        "cd_cvm": cd_cvm, "trimestre": trimestre, "ativo": float(valor),
        "dt_receb": datetime.date.fromisoformat(dt_receb),
        "versao": versao, "demonstrativo": "BPA", "dt_ini": None,
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
        # **Substituição declarada (contrato M1).** Aqui havia
        # `assert ... or True`, que é sempre verdadeira — asserção inútil
        # apontada pela revisão de 12/09. Trocada pela verificação real: o
        # bloco empatado de 400 linhas tem de caber INTEIRO numa faixa.
        maior = max(medida["faixas"], key=lambda f: f["n"])
        assert maior["valor_minimo"] == maior["valor_maximo"] == 1.0
        assert maior["n"] == n - 100, (
            "o bloco de valores empatados tem de ficar inteiro numa faixa"
        )
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
        fco = [
            _fco("A", "1T2020", 10, "2020-01-01", "2020-03-31",
                 "2020-05-10", demonstrativo="DFC_MI"),
            _fco("A", "1T2020", 10, "2020-01-01", "2020-03-31",
                 "2020-05-10", demonstrativo="DFC_MD"),
        ]
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
        # Nome do motivo mudou com o contrato R2.1 (era
        # `q1_nao_e_o_primeiro_apos_D`); a asserção é a mesma.
        assert descarte["rotulo_incompleto_em_q_de_D"] > 0

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


# --- correções R1–R5 da revisão de 2026-09-12 ------------------------------

class TestContratosR1aR5:
    """Contraprovas dos cinco achados de implementação da revisão de 12/09.

    Contratos: `resultados/contratos_correcao_r1_r5_rank03b_2026-09-12.md`.
    Cada caso exercita **a decisão**, não o JSON publicado — foi por asserções
    sobre o artefato que os defeitos de C5/C6 do B-DFC-01J passaram.
    """

    # --- R1: identidade da observação ---------------------------------------

    def test_R1_valor_periodo_e_data_vem_da_MESMA_linha(self):
        """O caso `023507/1T2015`, em miniatura.

        Duas linhas rotuladas com o mesmo trimestre: uma antiga de valor
        pequeno, outra recente de valor grande. O agrupamento anterior tomava
        `max(valor_reais)` e `min(dt_receb)` independentemente, e publicava o
        valor grande com a data da linha antiga — disponibilidade que ele
        nunca teve.
        """
        antiga = _fco("A", "1T2015", -4_337_000, "2014-04-10", "2014-06-30",
                      "2014-10-21")
        recente = _fco("A", "1T2015", 19_075_000, "2015-01-01", "2015-03-31",
                       "2015-05-05")
        escolhida = auditor.vigente_em([antiga, recente], recente["dt_receb"])
        assert escolhida["fco"] == 19_075_000
        assert escolhida["dt_receb"] == recente["dt_receb"], (
            "o valor não pode herdar a data de outra linha"
        )
        # Em 21/10/2014 só a antiga existia: o valor grande NÃO pode aparecer.
        em_outubro = auditor.vigente_em([antiga, recente], antiga["dt_receb"])
        assert em_outubro["fco"] == -4_337_000

    def test_R1_nada_disponivel_em_D_devolve_None(self):
        linha = _fco("A", "1T2020", 10, "2020-01-01", "2020-03-31", "2020-05-10")
        assert auditor.vigente_em([linha], datetime.date(2020, 1, 1)) is None

    def test_R1_desempate_e_cego_ao_valor_e_ao_rotulo(self):
        """Mesma recepção: decide a `versao`, nunca o valor."""
        baixa = _fco("A", "1T2020", 1, "2020-01-01", "2020-03-31",
                     "2020-05-10", versao=1)
        alta = _fco("A", "1T2020", 999, "2020-01-01", "2020-03-31",
                    "2020-05-10", versao=3)
        for ordem in ([baixa, alta], [alta, baixa]):
            escolhida = auditor.vigente_em(ordem, datetime.date(2020, 5, 10))
            assert escolhida["versao"] == 3, (
                "o desempate tem de ser determinístico e independente da "
                "ordem de entrada"
            )

    # --- R2: horizonte exato e janelas contíguas ----------------------------

    def test_R2_q_de_D_nas_bordas_do_trimestre(self):
        q = auditor.primeiro_trimestre_apos
        assert q(datetime.date(2019, 3, 31)) == "2T2019"
        assert q(datetime.date(2019, 4, 1)) == "3T2019", (
            "o 2T já começou em 01/04; o primeiro a COMEÇAR depois é o 3T"
        )
        assert q(datetime.date(2019, 5, 10)) == "3T2019"
        assert q(datetime.date(2019, 12, 31)) == "1T2020"
        assert q(datetime.date(2020, 1, 1)) == "2T2020"

    def test_R2_trimestre_contratual_ausente_censura_em_vez_de_deslocar(self):
        """Sem `3T2019`, `D=10/05/2019` não produz observação.

        A versão anterior aceitava `q1=4T2019` — deslocava o horizonte
        contratual em silêncio e media outro estimando.
        """
        fco = [r for r in TestPointInTime._serie(n=24, inicio=2016)
               if r["trimestre"] != "3T2019"]
        ativo = [_ativo("A", r["trimestre"], 10_000.0, r["dt_receb"].isoformat())
                 for r in fco]
        amostra, descarte = auditor.construir_amostra(fco, ativo)
        assert [r for r in amostra if r["D"] == "2019-05-10"] == []
        assert descarte["rotulo_incompleto_em_q_de_D"] > 0

    def test_R2_janela_passada_com_lacuna_e_descartada(self):
        """Sem `4T2018`, o "TTM" somaria quatro linhas num vão de cinco."""
        fco = [r for r in TestPointInTime._serie(n=24, inicio=2016)
               if r["trimestre"] != "4T2018"]
        ativo = [_ativo("A", r["trimestre"], 10_000.0, r["dt_receb"].isoformat())
                 for r in fco]
        amostra, descarte = auditor.construir_amostra(fco, ativo)
        assert [r for r in amostra if r["D"] == "2019-08-09"] == []
        assert descarte["janela_passada_com_lacuna"] > 0

    def test_R2_serie_completa_continua_produzindo_observacoes(self):
        """Não-regressão: sem este caso, descartar tudo passaria nos dois
        testes acima."""
        fco = TestPointInTime._serie(n=24, inicio=2016)
        ativo = [_ativo("A", r["trimestre"], 10_000.0, r["dt_receb"].isoformat())
                 for r in fco]
        amostra, _ = auditor.construir_amostra(fco, ativo)
        assert amostra, "série regular e completa tem de render observações"
        for obs in amostra:
            esperado = auditor.primeiro_trimestre_apos(
                datetime.date.fromisoformat(obs["D"])
            )
            assert obs["q1"] == esperado

    def test_R2_chave_companhia_D_e_unica(self):
        fco = TestPointInTime._serie(n=24, inicio=2016)
        ativo = [_ativo("A", r["trimestre"], 10_000.0, r["dt_receb"].isoformat())
                 for r in fco]
        amostra, _ = auditor.construir_amostra(fco, ativo)
        chaves = [(r["cd_cvm"], r["D"]) for r in amostra]
        assert len(chaves) == len(set(chaves))

    # --- R3: o ranking não desempata pelo rótulo ----------------------------

    @staticmethod
    def _linhas(n, positivos, valor):
        return [
            {"cd_cvm": f"C{i % 60}", "y": int(i < positivos),
             **{c: (valor(i)) for c in auditor.COMPONENTES_T1}}
            for i in range(n)
        ]

    def test_R3_escore_constante_nao_ganha_precisao_do_rotulo(self):
        """Era precisão 1,0 e lift 10,0 com escore que não discrimina nada."""
        linhas = self._linhas(600, 60, lambda i: 1.0)
        b = auditor.medir_baselines(linhas)["baselines"]["B2_trimestres_negativos"]
        assert b["auc_agregada"] == 0.5
        assert b["precisao_no_top_10pct"] == pytest.approx(0.1), (
            "escore constante tem de devolver a taxa-base, não 1,0"
        )
        assert b["lift_sobre_a_taxa_base"] == pytest.approx(1.0)
        assert b["empates_no_corte"] == 600

    def test_R3_escore_discriminante_nao_e_achatado(self):
        """Não-regressão: a correção não pode apagar sinal real."""
        linhas = self._linhas(600, 60, lambda i: 1000.0 - i)
        b = auditor.medir_baselines(linhas)["baselines"]["B2_trimestres_negativos"]
        assert b["precisao_no_top_10pct"] == 1.0
        assert b["auc_agregada"] == 1.0
        assert b["empates_no_corte"] == 0

    def test_R3_metricas_sao_invariantes_a_permutacao(self):
        import random
        linhas = self._linhas(600, 60, lambda i: float(i % 7))
        base = auditor.medir_baselines(linhas)["baselines"]
        for semente in range(3):
            outra = list(linhas)
            random.Random(semente).shuffle(outra)
            atual = auditor.medir_baselines(outra)["baselines"]
            for nome in auditor.BASELINES:
                assert (atual[nome]["precisao_no_top_10pct"]
                        == base[nome]["precisao_no_top_10pct"])

    def test_R4_auc_zero_sai_como_zero_e_nao_None(self):
        """`if auc` serializava AUC ZERO — ordenação perfeitamente errada —
        como «não medido»."""
        linhas = self._linhas(600, 60, lambda i: float(i))
        b = auditor.medir_baselines(linhas)["baselines"]["B2_trimestres_negativos"]
        assert b["auc_agregada"] == 0.0

    def test_R4_B0_publica_as_duas_coberturas(self):
        linhas = self._linhas(600, 60, lambda i: float(i))
        b0 = auditor.medir_baselines(linhas)["baselines"]["B0_classe_majoritaria"]
        assert b0["cobertura_de_ranqueamento"] == 0.0
        assert b0["cobertura_de_previsao_de_classe"] == 1.0, (
            "abstenção de RANQUEAR não é ausência de previsão de CLASSE"
        )

    def test_R4_baselines_publicam_as_metricas_do_paragrafo_8(self):
        linhas = self._linhas(600, 60, lambda i: float(i % 7))
        b = auditor.medir_baselines(linhas)["baselines"]["B2_trimestres_negativos"]
        for campo in ("ic95_inferior", "ic95_superior", "auc_intra_companhia",
                      "companhias_usadas", "observacoes_usadas"):
            assert campo in b, f"o §8 exige {campo}"

    # --- R4: os estados da decisão ------------------------------------------

    @staticmethod
    def _veredito(t1, baseline_falha=False):
        import statistics as _s
        from contextlib import ExitStack
        from unittest import mock as _m
        linhas = TestContratosR1aR5._linhas(600, 60, lambda i: float(i % 7))
        with ExitStack() as pilha:
            pilha.enter_context(_m.patch.object(
                auditor.duckdb, "connect", return_value=_m.MagicMock()))
            for nome, valor in {
                "carregar_fco": [], "carregar_ativo": [],
                "carregar_duracoes": [], "diagnosticar_escala": {},
                "gate_g0": {"aprovado": True, "pergunta": "x"},
                "construir_amostra": (linhas, {}),
                "teste_t2": {"aprovado": True},
            }.items():
                pilha.enter_context(
                    _m.patch.object(auditor, nome, return_value=valor))
            pilha.enter_context(_m.patch.object(auditor, "teste_t1", return_value=t1))
            if baseline_falha:
                pilha.enter_context(_m.patch.object(
                    auditor, "medir_baselines",
                    side_effect=_s.StatisticsError("baseline sem suporte")))
            return auditor.executar()["veredito"]

    def test_R4_insuficiencia_de_T1_e_INDECIDIVEL_e_nao_rejeicao(self):
        """Amostra insuficiente não refuta o alvo — ele não foi testado."""
        assert self._veredito({
            "aprovado": False, "indecidivel": True,
            "reprova_numericamente": False,
        }) == "INDECIDIVEL"

    def test_R4_reprovacao_numerica_continua_rejeitando(self):
        """Não-regressão: a correção não pode apagar a rejeição legítima."""
        assert self._veredito({
            "aprovado": False, "indecidivel": False,
            "reprova_numericamente": True,
        }) == "REJEITADO"

    def test_R4_baseline_falho_nao_autoriza_challenger(self):
        """O pior defeito da versão anterior: prontidão falsa.

        A falha dos baselines virava `reprova_em_aberto` e **não entrava na
        conjunção de aprovação** — o gate declarava o instrumento quebrado e
        autorizava o challenger mesmo assim. É o achado F10 pela quarta vez
        neste projeto (AGENTS.md §4.4, regra 7).
        """
        assert self._veredito(
            {"aprovado": True, "indecidivel": False,
             "reprova_numericamente": False},
            baseline_falha=True,
        ) != "PRONTO PARA CHALLENGER"

    def test_R4_com_tudo_valido_o_challenger_e_autorizado(self):
        """Sem este caso, um `False` fixo passaria nos três anteriores."""
        assert self._veredito({
            "aprovado": True, "indecidivel": False,
            "reprova_numericamente": False,
        }) == "PRONTO PARA CHALLENGER"

    # --- R5: o mínimo vale sobre o suporte efetivo --------------------------

    def test_R5_componente_de_uma_companhia_nao_e_aprovado(self):
        """570 observações de UMA companhia não são 570 réplicas."""
        linhas = [
            {"cd_cvm": "A" if i < 570 else f"C{i}", "y": i % 2,
             **{c: 1.0 for c in auditor.COMPONENTES_T1}}
            for i in range(600)
        ]
        for linha in linhas[570:]:
            linha["fco_ttm_sobre_sd8"] = None
        t1 = auditor.teste_t1(linhas)
        componente = t1["componentes"]["fco_ttm_sobre_sd8"]
        assert componente["veredito"] == "INSUFICIENTE"
        assert componente["companhias_usadas"] == 1
        assert t1["aprovado"] is False
        assert t1["indecidivel"] is True, (
            "suporte insuficiente é INDECIDÍVEL, não reprovação do alvo"
        )

    def test_R5_suporte_pleno_continua_sendo_avaliado(self):
        """Não-regressão: o piso não pode reprovar componente com suporte."""
        linhas = self._linhas(600, 60, lambda i: float(i % 40))
        t1 = auditor.teste_t1(linhas)
        for nome, dados in t1["componentes"].items():
            assert dados["veredito"] != "INSUFICIENTE", nome
            assert dados["companhias_usadas"] == 60
