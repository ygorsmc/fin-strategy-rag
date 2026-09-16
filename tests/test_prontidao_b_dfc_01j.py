"""Contratos do auditor de prontidão do candidato B-DFC-01J-M.

Cada caso corresponde a um jeito conhecido de um gate **aprovar por engano** —
por ausência de dado, por escore sem poder discriminante, por tratar trimestre
do mesmo banco como réplica independente, ou por deixar ausência virar zero.
"""

from __future__ import annotations

import datetime
import io
import json
import math
import random
from unittest import mock

import pytest

from scripts import auditar_prontidao_b_dfc_01j as prontidao


def _serie_em_memoria(registros):
    """`SERIE` falsa: JSONL em memória, sem tocar o artefato em disco.

    Os testes dos contratos C1–C6 precisam exercitar `carregar_populacao` com
    entradas sintéticas. Escrever arquivo temporário funcionaria, mas manter
    tudo em memória garante que nenhuma execução de teste possa sobrescrever
    `artefatos/b_dfc_01j/extensao/j_por_periodo.jsonl` por engano.
    """

    class SerieFalsa:
        def is_file(self):
            return True

        def open(self, **_kwargs):
            return io.StringIO(
                "\n".join(json.dumps(r) for r in registros)
            )

    return SerieFalsa()


def _obs(cd_cvm, periodo, inferior, superior, data="2025-02-07",
         base="original"):
    centro = (inferior + superior) / 2
    return prontidao.Observacao(
        cd_cvm=cd_cvm, periodo=periodo, inferior=inferior, superior=superior,
        base_temporal=base, disponivel_em=data,
        meia_largura=(superior - inferior) / 2 / abs(centro) if centro else 0,
    )


def _alvo(cd_cvm, base, alvo, y, largura=0.0, dbase="2024-05-01",
          dalvo="2024-08-01"):
    return prontidao.Alvo(
        cd_cvm=cd_cvm, periodo_base=base, periodo_alvo=alvo,
        y_inferior=y - largura, y_superior=y + largura, y_centro=y,
        j_base_centro=1000.0, j_alvo_centro=1000.0 * math.exp(y),
        disponivel_base=dbase, disponivel_alvo=dalvo,
        largura_do_rotulo=largura,
    )


class TestReprovaEmAberto:
    """Amostra insuficiente levanta erro. NUNCA vira aprovação.

    O auditor do Rank 3 devolvia "T1 aprovado" sobre amostra vazia porque com
    `n = 0` a amplitude saía `NaN` e `NaN >= 0,15` é `False` (AGENTS.md
    §3.14). Guarda que aprova por ausência de dado é pior que guarda nenhuma.
    """

    def test_quintil_com_amostra_pequena_levanta_em_vez_de_aprovar(self):
        with pytest.raises(prontidao.ReprovaEmAberto) as erro:
            prontidao.amplitude_por_quintis([1.0, 2.0, 3.0], [0, 1, 0])
        assert "insuficiente" in str(erro.value)

    def test_quintil_vazio_nao_passa_como_amplitude_zero(self):
        with pytest.raises(prontidao.ReprovaEmAberto):
            prontidao.amplitude_por_quintis([], [])

    def test_g3_com_menos_de_tres_emissores_levanta(self):
        alvos = [_alvo("000906", f"2024T{t}", f"2024T{t+1}", 0.1)
                 for t in (1, 2, 3)]
        with pytest.raises(prontidao.ReprovaEmAberto) as erro:
            prontidao.gate_g3(alvos, prontidao.previsoes_dos_baselines(alvos))
        assert "clusters independentes" in str(erro.value)


class TestEscoreConstanteNaoDecide:
    """AUC de escore constante é 0,5 por construção — não é sinal temporal."""

    def test_t2_recusa_escore_constante(self):
        alvos = [_alvo("000906", f"2024T{t}", f"2024T{t+1}", 0.1 * (-1) ** t)
                 for t in (1, 2, 3)]
        previsoes = {"B0": {(a.cd_cvm, a.periodo_base): 0.0 for a in alvos}}
        with pytest.raises(prontidao.ReprovaEmAberto) as erro:
            prontidao.teste_t2(alvos, previsoes, "B0")
        assert "constante" in str(erro.value)
        assert "não por haver sinal temporal" in str(erro.value)

    def test_auc_abaixo_de_meio_e_marcada_como_nao_informativa(self):
        """Lacuna pequena entre dois números ruins não é evidência."""
        alvos = [
            _alvo("000906", "2024T1", "2024T2", +0.2),
            _alvo("000906", "2024T2", "2024T3", -0.2),
            _alvo("001023", "2024T1", "2024T2", +0.2),
            _alvo("001023", "2024T2", "2024T3", -0.2),
        ]
        # Escore invertido de propósito: aponta para baixo quando y sobe.
        previsoes = {"B2": {
            (a.cd_cvm, a.periodo_base): -a.y_centro for a in alvos
        }}
        resultado = prontidao.teste_t2(alvos, previsoes, "B2")
        assert resultado["auc_agregada"] < 0.5
        assert resultado["informativo"] is False
        assert "pior que o acaso" in resultado["ressalva"]


class TestPoderUsaEmissorComoCluster:
    def test_trimestre_do_mesmo_banco_nao_e_replica_independente(self):
        """Tratar 30 trimestres de um banco como 30 réplicas infla o poder.

        A contraprova mede as duas contas na MESMA amostra: a agrupada por
        emissor tem de ser mais conservadora que a ingênua.
        """
        # Erros diferentes por emissor e NÃO periódicos, para que nenhum
        # baseline acerte exato (o que tornaria a melhoria relativa indefinida).
        alvos = []
        for indice, (cd, escala) in enumerate(
            (("000906", 0.02), ("001023", 0.30), ("019348", 0.05))
        ):
            for passo, (ano, t) in enumerate(
                (a, q) for a in (2023, 2024, 2025) for q in range(1, 5)
            ):
                alvos.append(_alvo(
                    cd, f"{ano}T{t}",
                    f"{ano}T{t + 1}" if t < 4 else f"{ano + 1}T1",
                    escala * math.sin(passo * 1.7 + indice),
                ))
        resultado = prontidao.gate_g3(
            alvos, prontidao.previsoes_dos_baselines(alvos)
        )
        agrupada = resultado["melhoria_minima_detectavel_relativa"]
        ingenua = resultado[
            "melhoria_minima_detectavel_se_trimestre_fosse_replica"
        ]
        assert agrupada > ingenua, (
            "a conta agrupada por emissor ficou MENOS conservadora que a "
            "ingênua: o agrupamento não está sendo aplicado"
        )

    def test_mae_macro_nao_deixa_o_emissor_com_mais_trimestres_dominar(self):
        erros = [("A", 1.0)] * 100 + [("B", 0.0)]
        assert prontidao.mae_macro(erros) == pytest.approx(0.5)
        # O agregado, por contraste, é dominado pelo emissor grande.
        assert sum(e for _, e in erros) / len(erros) > 0.98


class TestAusenciaNaoViraZero:
    def test_baseline_sem_previsao_nao_conta_como_acerto_perfeito(self):
        alvos = [_alvo("000906", "2024T1", "2024T2", 0.1)]
        erros = prontidao.erros_absolutos(alvos, {("000906", "2024T1"): None})
        assert erros == [], "previsão ausente entrou como erro zero"

    def test_baseline_sem_cobertura_devolve_mae_nulo_nao_zero(self):
        assert prontidao.mae_macro([]) is None


class TestPopulacaoEAlvo:
    def test_alvo_exige_adjacencia_de_calendario(self):
        """Pular um buraco na série mediria dois trimestres, não um."""
        observacoes = [
            _obs("000906", "2024T1", 100.0, 100.0),
            _obs("000906", "2024T3", 121.0, 121.0),
        ]
        alvos, contagem = prontidao.montar_alvos(observacoes)
        assert alvos == []
        assert contagem["pares_sem_trimestre_seguinte"] == 2

    def test_intervalo_de_y_usa_extremos_opostos(self):
        """O pior caso de uma razão combina teto de cima com piso de baixo."""
        observacoes = [
            _obs("000906", "2024T1", 90.0, 110.0),
            _obs("000906", "2024T2", 180.0, 220.0),
        ]
        alvos, _ = prontidao.montar_alvos(observacoes)
        assert len(alvos) == 1
        alvo = alvos[0]
        assert alvo.y_inferior == pytest.approx(math.log(180.0 / 110.0))
        assert alvo.y_superior == pytest.approx(math.log(220.0 / 90.0))
        assert alvo.y_inferior < alvo.y_centro < alvo.y_superior

    def test_j_nao_positivo_nao_entra_no_log(self):
        observacoes = [
            _obs("000906", "2024T1", 0.0, 0.0),
            _obs("000906", "2024T2", 100.0, 100.0),
        ]
        alvos, contagem = prontidao.montar_alvos(observacoes)
        assert alvos == []
        assert contagem["pares_com_sinal_trocado"] == 1

    def test_corte_de_largura_e_o_do_pre_registro(self):
        """5% está congelado no pré-registro; mudá-lo aparece no diff."""
        assert prontidao.LARGURA_MAXIMA_DA_POPULACAO == 0.05


class TestT1SeparaFuturoDePresente:
    def test_componente_indisponivel_na_previsao_e_marcado(self):
        alvos = [
            _alvo("000906" if i % 3 == 0 else "001023" if i % 3 == 1 else "019348",
                  f"202{2 + i // 4}T{i % 4 + 1}", f"202{2 + i // 4}T{i % 4 + 2}",
                  0.05 * (i % 7 - 3))
            for i in range(30)
        ]
        resultado = prontidao.teste_t1(alvos)
        componentes = resultado["componentes"]
        assert componentes["J_no_trimestre_base"][
            "disponivel_na_data_da_previsao"] is True
        assert componentes["J_no_trimestre_alvo"][
            "disponivel_na_data_da_previsao"] is False
        assert "defeito_do_proprio_pre_registro" in resultado

    def test_alvo_cujo_intervalo_cobre_zero_sai_do_binario(self):
        """Se o intervalo do rótulo cobre zero, "subiu" não é decidível."""
        alvos = [_alvo("000906", "2024T1", "2024T2", 0.01, largura=0.5)]
        # y nunca exatamente zero: rótulo pontual em zero também cobriria zero
        # e sairia do binário, confundindo a contagem que este caso mede.
        alvos += [
            _alvo("00090" + str(i % 3), f"202{3 + i // 4}T{i % 4 + 1}",
                  f"202{3 + i // 4}T{i % 4 + 2}",
                  0.04 * (i % 5 - 2) + 0.011)
            for i in range(30)
        ]
        resultado = prontidao.teste_t1(alvos)
        assert resultado["observacoes_cujo_intervalo_cobre_zero"] == 1
        assert resultado["observacoes_decidiveis"] == len(alvos) - 1


class TestLimiaresCongelados:
    """Mudar limiar depois de medir invalida o pré-registro (§7 dele).

    Os valores vivem como constantes nomeadas justamente para que a mudança
    apareça no diff em vez de escondida numa comparação inline.
    """

    def test_os_limiares_sao_os_pre_registrados(self):
        assert prontidao.G2_RUIDO_SOBRE_SINAL == 0.10
        assert prontidao.G3_MELHORIA_DETECTAVEL == 0.20
        assert prontidao.T1_AMPLITUDE == 0.15
        assert prontidao.T2_LACUNA == 0.12
        assert prontidao.MINIMO_DE_CLUSTERS == 3

    def test_fator_de_poder_e_de_80_por_cento(self):
        # 1,96 (α=0,05 bilateral) + 0,84 (poder 80%) = 2,80
        assert prontidao.FATOR_DE_PODER == pytest.approx(2.80)


class TestContraprovasDaRevisaoIndependente:
    """Contraprovas do relatório de 2026-09-10, uma por achado.

    Cada caso reproduz o defeito exato que a revisão nomeou, para que voltar
    atrás quebre a suíte em vez de voltar em silêncio. Nenhum destes números
    pertence ao painel financeiro real — são construções mínimas.
    """

    def test_F7_variavel_constante_nao_recebe_associacao_maxima(self):
        """`sorted(zip(valores, eventos))` desempatava pelo próprio rótulo.

        Uma coluna constante não ordena nada e tem de medir amplitude ZERO.
        Antes media 1,0 — associação perfeita — porque o desempate levava o
        evento para dentro da ordenação, produzindo quintis [0, 0, 0.5, 1, 1].
        """
        amplitude, faixas = prontidao.amplitude_por_quintis(
            [1.0] * 50, [0, 1] * 25
        )
        assert amplitude == 0.0
        assert all(f["taxa"] == 0.5 for f in faixas)

    def test_F7_variavel_que_de_fato_ordena_continua_medindo_amplitude(self):
        """Contraprova do contrário: a correção não pode cegar o teste."""
        valores = [float(i) for i in range(50)]
        eventos = [0] * 25 + [1] * 25
        amplitude, _ = prontidao.amplitude_por_quintis(valores, eventos)
        assert amplitude == 1.0

    def test_F2_alvo_iniciado_antes_da_base_nao_respeita_o_horizonte(self):
        """O caso real do Bradesco: base pública em 02/05, alvo começa em 01/04.

        O contrato exige o primeiro trimestre inteiro que COMEÇA depois de a
        base ficar pública. O gate media só a ordem das publicações, e por isso
        contava como certificado um par cujo alvo já estava em curso.
        """
        alvo = _alvo("000906", "2024T1", "2024T2", 0.05,
                     dbase="2024-05-02", dalvo="2024-08-05")
        assert prontidao.horizonte_contratual_respeitado(alvo) is False
        # 2024T3 começa em 01/07/2024, depois de 02/05: esse respeita.
        respeita = _alvo("000906", "2024T1", "2024T3", 0.05,
                         dbase="2024-05-02", dalvo="2024-11-05")
        assert prontidao.horizonte_contratual_respeitado(respeita) is True

    def test_F2_o_gate_g1_reprova_o_par_fora_do_horizonte(self):
        """Datas em ordem não bastam para o gate aprovar."""
        alvos = [
            _alvo("000906", "2024T1", "2024T2", 0.05,
                  dbase="2024-05-02", dalvo="2024-08-05"),
        ]
        g1 = prontidao.gate_g1(alvos)
        assert g1["com_datas_em_ordem"] == 1
        assert g1["com_horizonte_contratual"] == 0
        assert g1["fracao_certificada"] == 0.0
        assert g1["aprovado"] is False
        # Campo renomeado pelo contrato C3: o diagnóstico deixou de ser
        # "alvo já iniciado" e passou a ser "fora de q(D)", que cobre os dois
        # lados do defeito — o trimestre em curso E o trimestre distante.
        assert g1["fora_do_horizonte_q_de_d"]

    def test_F9_B2_exige_quatro_trimestres_consecutivos(self):
        """Buraco na série não pode virar «mediana dos quatro anteriores».

        Contraprova da revisão: com 2020T1 e 2024T1 na série, B2 usava 2020T1
        para prever 2024T1. Agora exige os quatro trimestres imediatamente
        anteriores; faltando um, B2 não opina.
        """
        alvos = [
            _alvo("000906", "2020T1", "2020T2", 0.5),
            _alvo("000906", "2024T1", "2024T2", 0.2),
        ]
        previsoes = prontidao.previsoes_dos_baselines(alvos)
        assert previsoes["B2"][("000906", "2024T1")] is None

    def test_F9_B2_opina_quando_os_quatro_existem(self):
        """A correção não pode zerar B2 onde ele é legítimo.

        **A asserção (0,25) é a mesma; a fixture é que ganhou datas.** Ela usava
        o padrão de `_alvo` para todos os cinco alvos, o que punha o desfecho
        dos antecedentes em 01/08/2024 — DEPOIS da decisão de 01/05/2024. Sob o
        contrato C4 isso passou a ser corretamente recusado. Declarar as datas
        reais de cada antecedente é o que o teste sempre deveria ter feito:
        sem elas, ele não distinguia "B2 opina" de "B2 opina com informação do
        futuro". O par negativo está em `test_C4_...` logo abaixo.
        """
        alvos = [
            _alvo("000906", f"2023T{q}", f"2023T{q + 1}", 0.1 * q,
                  dbase=f"2023-0{q + 1}-15", dalvo=f"2023-0{q + 4}-15")
            for q in (1, 2, 3)
        ] + [
            _alvo("000906", "2023T4", "2024T1", 0.4,
                  dbase="2023-11-15", dalvo="2024-03-15"),
            _alvo("000906", "2024T1", "2024T2", 0.9,
                  dbase="2024-05-01", dalvo="2024-08-01"),
        ]
        previsoes = prontidao.previsoes_dos_baselines(alvos)
        # Os quatro anteriores a 2024T1 são 2023T1..T4: y = 0,1/0,2/0,3/0,4,
        # e os quatro desfechos (até 15/03/2024) precedem a decisão (01/05).
        assert previsoes["B2"][("000906", "2024T1")] == pytest.approx(0.25)

    def test_F10_T2_nao_informativo_nao_aprova(self):
        """A ressalva existia; a trava não.

        Escore que ordena o evento pior que o acaso produzia lacuna pequena
        por ser ruim, e `aprovado=True` ao lado de um texto dizendo «não leia
        como aprovação».
        """
        alvos = [
            _alvo("000906", f"2023T{q}", f"2023T{q + 1}", y)
            for q, y in ((1, 0.3), (2, -0.2), (3, 0.4))
        ] + [
            _alvo("001023", f"2023T{q}", f"2023T{q + 1}", y)
            for q, y in ((1, -0.3), (2, 0.25), (3, -0.4))
        ]
        # Escore = -y: ordena o evento exatamente ao contrário do certo.
        previsoes = {"BX": {
            (a.cd_cvm, a.periodo_base): -a.y_centro for a in alvos
        }}
        resultado = prontidao.teste_t2(alvos, previsoes, "BX")
        assert resultado["informativo"] is False
        assert resultado["aprovado"] is False, (
            "escore pior que o acaso não pode aprovar T2"
        )

    def test_F10_B3_ausente_impede_aprovacao_do_G3(self):
        """O §4 do pré-registro exigia B3 e a exigência era só texto."""
        assert prontidao.B3_EXECUTADO is False, (
            "se B3 passar a existir, este caso precisa medir o contrário"
        )
        # Amostra confortável: o que reprova é a ausência de B3, não o poder.
        alvos = [
            _alvo(cd, f"2023T{q}", f"2023T{q + 1}", 0.10)
            for cd in ("000906", "001023", "019348")
            for q in (1, 2, 3)
        ]
        previsoes = prontidao.previsoes_dos_baselines(alvos)
        g3 = prontidao.gate_g3(alvos, previsoes)
        assert g3["b3_executado"] is False
        assert g3["aprovado"] is False
        assert "B3" in g3["limiar"]


class TestContratosC1aC6:
    """Contraprovas dos seis contratos abertos pelo parecer de 2026-09-11.

    Cada uma reproduz a ENTRADA que o parecer usou para demonstrar o defeito e
    exige a saída do contrato registrado em
    `resultados/contratos_correcao_c1_c6_b_dfc_01j_2026-09-11.md`, escrito
    antes da implementação.
    """

    # --- C1: empates não podem fabricar quintil ---------------------------

    def test_C1_constante_com_rotulos_agrupados_nao_recebe_associacao(self):
        """O caso exato do parecer: mesma distribuição, só reordenada.

        A correção anterior (desempate por posição) devolvia 0,0 para
        `[0,1]*25` e **1,0** para `[0]*25+[1]*25`. Publiquei o primeiro como
        prova de que F7 estava morto; era um caso aprovado apresentado como
        propriedade geral.
        """
        alternado, _ = prontidao.amplitude_por_quintis([1.0] * 50, [0, 1] * 25)
        agrupado, _ = prontidao.amplitude_por_quintis(
            [1.0] * 50, [0] * 25 + [1] * 25
        )
        assert alternado == 0.0
        assert agrupado == 0.0, (
            "variável constante não ordena nada; amplitude > 0 aqui significa "
            "que os quintis foram criados pela ordem das linhas"
        )

    def test_C1_amplitude_e_invariante_a_permutacao_das_linhas(self):
        """Invariância, não aleatoriedade.

        O parecer avisa que randomizar empates não demonstra invariância, só a
        esconde atrás de uma semente. Aqui ela é medida.
        """
        valores = [float(i // 10) for i in range(50)]
        eventos = [1 if i < 25 else 0 for i in range(50)]
        medidas = set()
        for semente in range(25):
            indices = list(range(50))
            random.Random(semente).shuffle(indices)
            amplitude, _ = prontidao.amplitude_por_quintis(
                [valores[i] for i in indices], [eventos[i] for i in indices]
            )
            medidas.add(round(amplitude, 12))
        assert len(medidas) == 1, f"amplitude varia com a ordem: {medidas}"

    def test_C1_empate_nunca_atravessa_duas_faixas(self):
        valores = [float(i // 10) for i in range(50)]
        _, faixas = prontidao.amplitude_por_quintis(valores, [0, 1] * 25)
        for faixa in faixas:
            assert faixa["valor_minimo"] == faixa["valor_maximo"], (
                "uma faixa contém dois valores distintos de um mesmo grupo de "
                "empate, ou um grupo foi partido"
            )

    def test_C1_variavel_que_ordena_de_fato_continua_medindo(self):
        """Não-regressão: a correção não pode cegar o teste T1."""
        amplitude, _ = prontidao.amplitude_por_quintis(
            [float(i) for i in range(50)], [0] * 25 + [1] * 25
        )
        assert amplitude == 1.0

    # --- C2: unidade tem de ser convertida, não só etiquetada -------------

    def test_C2_mesmo_montante_em_unidades_diferentes_nao_move_y(self):
        """1.000 milhares e 1 milhão são o MESMO dinheiro.

        O parecer mediu `y = −6,907755278982137`, que é `ln(1/1000)`: o
        consumidor dividia os números crus. F8 corrigiu a etiqueta na
        exportação e deixou a aritmética intacta.
        """
        observacoes = [
            prontidao.Observacao(
                "A", "2023T1", 1000.0 * 1000, 1000.0 * 1000,
                "original", "2023-05-01", 0.0, "milhares_de_reais",
            ),
            prontidao.Observacao(
                "A", "2023T2", 1.0 * 1_000_000, 1.0 * 1_000_000,
                "original", "2023-08-01", 0.0, "milhoes_de_reais",
            ),
        ]
        alvos, _ = prontidao.montar_alvos(observacoes)
        assert alvos[0].y_centro == pytest.approx(0.0, abs=1e-12)

    def test_C2_unidade_ausente_ou_desconhecida_levanta_erro(self):
        """Supor unidade erra por três ordens de grandeza sem sinal."""
        for unidade in (None, "bilhoes_de_pesos"):
            registro = {
                "cd_cvm": "A", "periodo": "2023T1", "status": "identificado",
                "fechamento_confere": True, "base_temporal": "original",
                "disponivel_em": "2023-05-01",
                "limite_inferior": "100", "limite_superior": "100",
            }
            if unidade is not None:
                registro["unidade"] = unidade
            with mock.patch.object(
                prontidao, "SERIE", _serie_em_memoria([registro])
            ):
                with pytest.raises(prontidao.ErroDeUnidade):
                    prontidao.carregar_populacao()

    def test_C2_erro_de_unidade_nao_e_reprova_em_aberto(self):
        """Defeito de dado não pode virar veredito de gate.

        `ReprovaEmAberto` é capturada por `_medir` e vira "gate reprovado com
        motivo" — um estado legítimo. Unidade impossível de interpretar não é
        isso: esconder o defeito atrás de um veredito plausível é pior que
        derrubar a execução.
        """
        assert not issubclass(prontidao.ErroDeUnidade, prontidao.ReprovaEmAberto)

    def test_C2_largura_relativa_e_invariante_a_escala(self):
        """Não-regressão: o corte de largura é razão e não pode se mover."""
        registros = [
            {
                "cd_cvm": "A", "periodo": periodo, "status": "identificado",
                "fechamento_confere": True, "base_temporal": "original",
                "disponivel_em": "2023-05-01", "unidade": unidade,
                "limite_inferior": "99", "limite_superior": "101",
            }
            for periodo, unidade in (
                ("2023T1", "milhares_de_reais"),
                ("2023T2", "milhoes_de_reais"),
            )
        ]
        with mock.patch.object(
            prontidao, "SERIE", _serie_em_memoria(registros)
        ):
            observacoes, _ = prontidao.carregar_populacao()
        larguras = {o.periodo: round(o.meia_largura, 12) for o in observacoes}
        assert larguras["2023T1"] == larguras["2023T2"] == 0.01
        # E a conversão realmente aconteceu.
        centros = {o.periodo: o.centro for o in observacoes}
        assert centros["2023T2"] == 1000 * centros["2023T1"]

    # --- C3: horizonte é IGUALDADE com q(D) -------------------------------

    def test_C3_somente_q_de_d_respeita_o_horizonte(self):
        """A tabela do parecer, item por item.

        D = 02/05/2024. A versão anterior exigia só `início > D`, e aprovava
        2024T4 e 2025T1 — que pulam q(D). Prever três trimestres à frente é
        outra tarefa, com outra dificuldade.
        """
        esperado = {
            "2024T2": False,   # já começou
            "2024T3": True,    # é q(D)
            "2024T4": False,   # pulou q(D)
            "2025T1": False,   # pulou q(D)
        }
        for periodo, respeita in esperado.items():
            alvo = _alvo("000906", "2024T1", periodo, 0.05,
                         dbase="2024-05-02", dalvo="2025-02-01")
            assert prontidao.horizonte_contratual_respeitado(alvo) is respeita
            assert prontidao.gate_g1([alvo])["aprovado"] is respeita

    def test_C3_q_de_d_nas_bordas_do_trimestre(self):
        """Primeiro e último dia do trimestre dão o mesmo q(D)."""
        assert prontidao.primeiro_trimestre_apos(
            datetime.date(2024, 4, 1)) == "2024T3"
        assert prontidao.primeiro_trimestre_apos(
            datetime.date(2024, 6, 30)) == "2024T3"
        # Virada de ano.
        assert prontidao.primeiro_trimestre_apos(
            datetime.date(2024, 10, 1)) == "2025T1"
        assert prontidao.primeiro_trimestre_apos(
            datetime.date(2024, 12, 31)) == "2025T1"

    def test_C3_sem_data_de_base_continua_sendo_nao_sei(self):
        alvo = _alvo("000906", "2024T1", "2024T3", 0.05, dbase=None)
        assert prontidao.horizonte_contratual_respeitado(alvo) is None

    # --- C4: disponibilidade dos antecedentes e contagem do usado ---------

    def test_C4_antecedente_ainda_nao_publico_nao_alimenta_B1_nem_B2(self):
        """A contraprova do parecer: decisão em 05/2024, histórico de 2025."""
        historico = [
            _alvo("000906", f"2023T{q}", prontidao.proximo_trimestre(f"2023T{q}"),
                  0.2 * q, dbase="2023-05-01", dalvo="2025-01-01")
            for q in (1, 2, 3, 4)
        ]
        corrente = _alvo("000906", "2024T1", "2024T3", 0.15,
                         dbase="2024-05-02", dalvo="2024-11-01")
        previsoes = prontidao.previsoes_dos_baselines(historico + [corrente])
        assert previsoes["B1"][("000906", "2024T1")] is None
        assert previsoes["B2"][("000906", "2024T1")] is None

    def test_C4_antecedente_sem_data_nunca_e_presumido_disponivel(self):
        historico = [
            _alvo("000906", f"2023T{q}", prontidao.proximo_trimestre(f"2023T{q}"),
                  0.2 * q, dbase="2023-05-01", dalvo=None)
            for q in (1, 2, 3, 4)
        ]
        corrente = _alvo("000906", "2024T1", "2024T3", 0.15,
                         dbase="2024-05-02", dalvo="2024-11-01")
        previsoes = prontidao.previsoes_dos_baselines(historico + [corrente])
        assert previsoes["B2"][("000906", "2024T1")] is None

    def test_C4_g3_conta_os_emissores_que_entram_na_comparacao(self):
        """Contraprova do revisor: 3 bancos, eleito cobrindo 1.

        G3 devolvia `emissores_independentes = 3` ao lado de
        `trimestres_por_emissor = {'A': 2}` — e "emissores necessários = 0".
        Contar quem não está na comparação infla o poder aparente.
        """
        alvos = [
            _alvo("A", periodo, prontidao.proximo_trimestre(periodo),
                  0.1 + 0.02 * i, dbase=dbase, dalvo=dalvo)
            for i, (periodo, dbase, dalvo) in enumerate([
                ("2023T1", "2023-05-01", "2023-08-01"),
                ("2023T2", "2023-08-01", "2023-11-01"),
                ("2023T3", "2023-11-01", "2024-02-01"),
                ("2023T4", "2024-02-01", "2024-05-01"),
                ("2024T1", "2024-05-01", "2024-08-01"),
                ("2024T2", "2024-08-01", "2024-11-01"),
            ])
        ] + [
            _alvo("B", "2024T1", "2024T2", 0.3,
                  dbase="2024-05-01", dalvo="2024-08-01"),
            _alvo("C", "2024T1", "2024T2", 0.4,
                  dbase="2024-05-01", dalvo="2024-08-01"),
        ]
        g3 = prontidao.gate_g3(alvos, prontidao.previsoes_dos_baselines(alvos))
        usados = set(g3["trimestres_por_emissor"])
        assert g3["emissores_independentes"] == len(usados)
        assert g3["emissores_na_populacao"] == 3
        assert set(g3["emissores_fora_do_erro_do_eleito"]) == {"B", "C"} - usados
        assert g3["aprovado"] is False

    # --- C6: o cálculo de poder sai marcado como invalidado ---------------

    def test_C6_gate_g3_marca_o_poder_como_invalidado_por_F3(self):
        alvos = [
            _alvo(cd, "2024T1", "2024T2", y,
                  dbase="2024-05-01", dalvo="2024-08-01")
            for cd, y in (("A", 0.1), ("B", 0.3), ("C", 0.5))
        ] + [
            _alvo(cd, "2023T4", "2024T1", y,
                  dbase="2024-02-01", dalvo="2024-05-01")
            for cd, y in (("A", 0.2), ("B", 0.4), ("C", 0.6))
        ]
        g3 = prontidao.gate_g3(alvos, prontidao.previsoes_dos_baselines(alvos))
        assert g3["calculo_de_poder_invalidado_por"] == "F3"
        assert "INVALIDADO" in g3["leitura_do_poder"]
        # Publicado e marcado, não apagado.
        assert g3["melhoria_minima_detectavel_relativa"] is not None
        assert g3["emissores_necessarios_para_o_gate_decidir"] is not None

    def test_C6_a_marcacao_nao_e_o_que_reprova_o_gate(self):
        """Cada veto de G3 bloqueia POR SI — a matriz completa está em C6-bis.

        **Substituição declarada.** Este caso tinha uma única asserção,
        `B3_EXECUTADO is False`, que é exatamente o que a conferência
        independente de 11/09 apontou: verificar a constante atual não testa a
        conjunção dos vetos. A intenção que ele protegia — o veto de B3 é
        independente da quarentena — está preservada e generalizada em
        `TestContratosRC5RC6.test_RC6_a_aprovacao_de_g3_exige_os_tres_vetos`,
        que exerce as quatro combinações de B3 × F3.

        O título ficou como estava e passou a ser FALSO sob C6-bis: a
        marcação de F3 **é** um dos motivos da reprovação, por contrato. Fica
        aqui só a parte que continua verdadeira e que o nome original queria
        proteger.
        """
        assert prontidao.B3_EXECUTADO is False
        assert prontidao.PODER_REDESENHADO_APOS_F3 is False


class TestContratosRC5RC6:
    """Contraprovas da conferência independente de 2026-09-11.

    Os três achados têm o mesmo formato: a onda C1–C6 implementou o PRODUTOR
    do campo de estado, publicou o campo, e deixou o predicado de decisão do
    consumidor intacto. Por isso cada caso aqui exercita **a decisão**, não o
    JSON: asserção sobre o artefato publicado prova o produtor e não prova
    nada sobre o consumidor.

    Contratos: `resultados/contratos_correcao_rc5_rc6_b_dfc_01j_2026-09-11.md`.
    """

    # --- R-C6: a quarentena de F3 governa a aprovação de G3 ---------------

    @staticmethod
    def _alvos_com_poder_folgado():
        """Amostra em que o LIMIAR não é o que reprova.

        Três emissores com erro idêntico dão melhoria detectável zero, então
        `relativa <= G3_MELHORIA_DETECTAVEL` é verdadeiro e o que resta em
        teste é exclusivamente o veto.
        """
        return [
            _alvo(cd, "2024T1", "2024T2", 0.1,
                  dbase="2024-05-01", dalvo="2024-08-01")
            for cd in ("A", "B", "C")
        ]

    def _g3(self, b3: bool, f3: bool) -> dict:
        alvos = self._alvos_com_poder_folgado()
        previsoes = {
            nome: {(a.cd_cvm, a.periodo_base): 0.0 for a in alvos}
            for nome in ("B0", "B3")
        }
        with mock.patch.object(prontidao, "B3_EXECUTADO", b3), \
             mock.patch.object(prontidao, "PODER_REDESENHADO_APOS_F3", f3):
            return prontidao.gate_g3(alvos, previsoes)

    def test_RC6_a_aprovacao_de_g3_exige_os_tres_vetos(self):
        """As quatro combinações de B3 × F3, com o poder folgado nas quatro.

        O caso (B3 presente, F3 vigente) é o do parecer: G3 aprovava embora
        declarasse o próprio cálculo inválido. O caso (B3 ausente, F3
        redesenhado) prova que o veto de B3 não foi substituído pelo novo. E o
        caso (True, True) prova que nenhum dos dois é um `False` fixo
        disfarçado — sem ele, um gate travado com literal passaria nos outros
        três e pareceria correto.
        """
        assert self._g3(b3=False, f3=False)["aprovado"] is False
        assert self._g3(b3=True, f3=False)["aprovado"] is False, (
            "F3 vigente tem de vetar mesmo com B3 executado: um gate que "
            "declara o próprio cálculo de poder inválido não pode aprovar "
            "por ele"
        )
        assert self._g3(b3=False, f3=True)["aprovado"] is False, (
            "B3 ausente tem de vetar mesmo sem F3 — o veto novo não pode ter "
            "substituído o antigo"
        )
        assert self._g3(b3=True, f3=True)["aprovado"] is True, (
            "com os dois vetos levantados e poder folgado, G3 tem de aprovar; "
            "se não aprova, algum veto virou literal fixo e os outros três "
            "casos não provam nada"
        )

    def test_RC6_g3_publica_o_estado_de_c6_no_mesmo_vocabulario(self):
        """`decidivel`, `clusters_suficientes` e `ressalva` — como `_poder`.

        O contrato C6 fixou estes três campos como vocabulário comum aos dois
        consumidores. A sensibilidade os implementou; G3 ficou só com a
        etiqueta `calculo_de_poder_invalidado_por`, que não decidia nada.
        """
        g3 = self._g3(b3=False, f3=False)
        assert g3["decidivel"] is False
        assert g3["clusters_suficientes"] is True, (
            "três emissores no erro do eleito bastam em NÚMERO; o que "
            "invalida a conta é F3, e os dois estados são distintos"
        )
        assert "F3" in g3["ressalva"]
        assert "B3" in g3["ressalva"]
        assert g3["poder_redesenhado_apos_f3"] is False
        # Publicado e invalidado, nunca apagado.
        assert g3["melhoria_minima_detectavel_relativa"] is not None
        assert g3["emissores_necessarios_para_o_gate_decidir"] is not None

    def test_RC6_redesenhar_o_poder_limpa_a_marcacao_de_invalidez(self):
        """A etiqueta acompanha a constante, em vez de ser texto fixo.

        Se `calculo_de_poder_invalidado_por` continuasse dizendo "F3" depois
        do redesenho, o artefato mentiria no sentido oposto.
        """
        g3 = self._g3(b3=True, f3=True)
        assert g3["calculo_de_poder_invalidado_por"] is None
        assert g3["decidivel"] is True
        assert g3["ressalva"] is None

    # --- R-C5: G0 só certifica com evidência independente -----------------

    @staticmethod
    def _g0(independentes, *, com_campo=True) -> dict:
        """`gate_g0` sobre um resumo sintético, sem tocar o artefato real.

        Os demais critérios saem todos limpos de propósito: o que se mede
        aqui é exclusivamente o efeito da evidência independente.
        """
        resumo = {
            "identidades_conferidas": 1,
            "identidades_divergentes": [],
            "rubricas_com_conformidade_nao_demonstrada": [],
            "identidades_que_fecham_por_construcao": [
                {
                    "cd_cvm": "A", "ano": "2024", "identidade": "T1+T2 = S1",
                    "operandos_derivados": ["S1 (despesa_juros_total)"],
                },
            ],
        }
        if com_campo:
            resumo["identidades_conferidas_independentes"] = independentes
        leitor = mock.Mock()
        leitor.read_text.return_value = json.dumps(resumo)
        with mock.patch.object(prontidao, "RESUMO_EXTENSAO", leitor):
            return prontidao.gate_g0(
                {"observacoes_de_J": 2, "descartados_sem_fechamento": 0}
            )

    def test_RC5_zero_verificacoes_independentes_nao_certifica(self):
        """Tudo que fecha, fecha por construção — que é álgebra, não prova.

        Uma identidade que fecha porque um operando foi DERIVADO dos outros
        fecha por definição; não demonstra que o mapeamento de conta está
        certo. Certificar integridade com zero evidência independente é o que
        o contrato C5-B existia para impedir.
        """
        g0 = self._g0(0)
        assert g0["aprovado"] is False
        assert g0["tem_evidencia_independente"] is False
        assert g0["identidades_conferidas_independentes"] == 0

    def test_RC5_campo_ausente_e_recusa_nao_permissao(self):
        """Artefato sem o campo é «não sei», nunca «sim».

        Produtor antigo, schema trocado ou leitura parcial não podem produzir
        certificação — é a guarda-que-aprova-por-ausência-de-dado do §3.14.
        """
        g0 = self._g0(None, com_campo=False)
        assert g0["aprovado"] is False
        assert g0["tem_evidencia_independente"] is False
        assert g0["identidades_conferidas_independentes"] is None

    def test_RC5_com_evidencia_independente_o_piso_nao_reprova(self):
        """Não-regressão: o piso não pode virar reprovação universal.

        Sem este caso, fixar `aprovado: False` em G0 passaria nos dois testes
        anteriores.
        """
        g0 = self._g0(1)
        assert g0["aprovado"] is True
        assert g0["tem_evidencia_independente"] is True

    def test_RC5_booleano_no_json_nao_conta_como_evidencia(self):
        """`True` não é contagem, embora `bool` seja subclasse de `int`.

        Sem a checagem explícita, `identidades_conferidas_independentes: true`
        num artefato malformado certificaria como se fosse uma identidade.
        """
        assert self._g0(True)["aprovado"] is False

    def test_RC5_o_piso_nao_exige_cobertura_total(self):
        """O contrato recusa inventar limiar que C5-B não fixou.

        Uma identidade independente entre muitas conferidas certifica. Exigir
        `independentes == conferidas` seria política nova, escolhida depois de
        ver o dado — e reprovaria população legítima com mistura de
        fechamentos independentes e por construção.
        """
        resumo = {
            "identidades_conferidas": 40,
            "identidades_conferidas_independentes": 1,
            "identidades_divergentes": [],
            "rubricas_com_conformidade_nao_demonstrada": [],
            "identidades_que_fecham_por_construcao": [{"cd_cvm": "A"}] * 39,
        }
        leitor = mock.Mock()
        leitor.read_text.return_value = json.dumps(resumo)
        with mock.patch.object(prontidao, "RESUMO_EXTENSAO", leitor):
            g0 = prontidao.gate_g0(
                {"observacoes_de_J": 2, "descartados_sem_fechamento": 0}
            )
        assert g0["aprovado"] is True

    def test_RC5_os_outros_criterios_de_g0_seguem_vetando(self):
        """Evidência independente não resgata rubrica suspeita nem J vazio."""
        resumo = {
            "identidades_conferidas": 24,
            "identidades_conferidas_independentes": 24,
            "identidades_divergentes": [],
            "rubricas_com_conformidade_nao_demonstrada": [
                "juros_mercados_interbancarios",
            ],
            "identidades_que_fecham_por_construcao": [],
        }
        leitor = mock.Mock()
        leitor.read_text.return_value = json.dumps(resumo)
        with mock.patch.object(prontidao, "RESUMO_EXTENSAO", leitor):
            com_rubrica = prontidao.gate_g0(
                {"observacoes_de_J": 2, "descartados_sem_fechamento": 0}
            )
            resumo["rubricas_com_conformidade_nao_demonstrada"] = []
            leitor.read_text.return_value = json.dumps(resumo)
            sem_j = prontidao.gate_g0(
                {"observacoes_de_J": 0, "descartados_sem_fechamento": 0}
            )
        assert com_rubrica["aprovado"] is False
        assert sem_j["aprovado"] is False

    # --- R-SUPORTE: um único erro é amostra insuficiente ------------------

    def test_RSUPORTE_eleito_com_um_unico_erro_reprova_em_aberto(self):
        """`StatisticsError` derrubava o relatório inteiro.

        Três emissores na população, B0 cobrindo os três e outro baseline
        cobrindo uma única observação: o segundo vence no suporte comum e a
        conta de dispersão estoura. `_medir` captura `ReprovaEmAberto`, não
        `StatisticsError` — então a execução morria levando junto G0, G1 e G2
        que já haviam sido medidos.

        Dívida ANTERIOR a C4-B: a chamada que estourava vem antes, no
        arquivo, de qualquer linha que C4-B introduziu.
        """
        alvos = [
            _alvo(cd, "2024T1", "2024T2", 0.9,
                  dbase="2024-05-01", dalvo="2024-08-01")
            for cd in ("A", "B", "C")
        ]
        previsoes = {
            "B0": {(a.cd_cvm, a.periodo_base): 0.0 for a in alvos},
            "BX": {("A", "2024T1"): 0.8},
        }
        with pytest.raises(prontidao.ReprovaEmAberto) as erro:
            prontidao.gate_g3(alvos, previsoes)
        assert "BX" in str(erro.value)
        assert "1 observação" in str(erro.value)

    def test_RSUPORTE_e_capturavel_pelo_medir_da_cadeia(self):
        """O ponto do contrato é preservar os gates já medidos.

        `_medir` converte `ReprovaEmAberto` em «gate reprovado com o motivo».
        Se a exceção não fosse dessa família, a conversão não aconteceria e o
        relatório continuaria caindo inteiro.
        """
        assert issubclass(prontidao.ReprovaEmAberto, Exception)
        assert not issubclass(prontidao.ErroDeUnidade, prontidao.ReprovaEmAberto), (
            "defeito de dado continua tendo de subir alto, em vez de virar "
            "veredito plausível de gate"
        )

    def test_RSUPORTE_dois_erros_seguem_sendo_calculados(self):
        """Não-regressão: a guarda não pode reprovar suporte suficiente."""
        alvos = [
            _alvo(cd, "2024T1", "2024T2", 0.9,
                  dbase="2024-05-01", dalvo="2024-08-01")
            for cd in ("A", "B", "C")
        ]
        previsoes = {
            "B0": {(a.cd_cvm, a.periodo_base): 0.0 for a in alvos},
            "BX": {("A", "2024T1"): 0.8, ("B", "2024T1"): 0.7},
        }
        g3 = prontidao.gate_g3(alvos, previsoes)
        assert g3["melhoria_minima_detectavel_relativa"] is not None
        assert g3["clusters_suficientes"] is False, (
            "dois emissores no erro do eleito ficam abaixo do mínimo de "
            "clusters — o número sai, mas marcado como não interpretável"
        )
