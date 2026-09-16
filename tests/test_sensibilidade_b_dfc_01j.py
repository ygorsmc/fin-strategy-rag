"""Contratos do diagnóstico de sensibilidade às rubricas suspeitas.

O script existe porque o "~128 emissores" publicado no relatório de prontidão
não é limite do universo de bancos: é sintoma do mesmo defeito que o G0
reprovou. Estes casos travam a leitura correta dos dois cenários — inclusive o
jeito de ler errado o cenário pessimista, que **parece** melhorar o poder.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import auditar_prontidao_b_dfc_01j as prontidao
from scripts import sensibilidade_rubricas_suspeitas_b_dfc_01j as sens

ARTEFATO = (
    Path(__file__).resolve().parents[1]
    / "artefatos" / "b_dfc_01j" / "prontidao" / "sensibilidade.json"
)


class TestParametrosNaoSaoCopiaSolta:
    """Limiar duplicado é limiar que divergirá em silêncio."""

    def test_usa_os_limiares_do_auditor(self):
        assert sens.G3_MELHORIA_DETECTAVEL is prontidao.G3_MELHORIA_DETECTAVEL
        assert sens.FATOR_DE_PODER is prontidao.FATOR_DE_PODER
        assert (
            sens.LARGURA_MAXIMA_DA_POPULACAO
            is prontidao.LARGURA_MAXIMA_DA_POPULACAO
        )
        assert sens.MINIMO_DE_CLUSTERS is prontidao.MINIMO_DE_CLUSTERS

    def test_as_tres_suspeitas_sao_as_que_o_g0_reprovou(self):
        assert sens.RUBRICAS_SUSPEITAS == {
            "juros_mercados_interbancarios",
            "juros_depositos_interfinanceiros",
            "juros_emprestimos_e_repasses",
        }


class TestPoucosClustersNaoViraBoaNoticia:
    """O jeito errado de ler o cenário pessimista.

    Perder o emissor que se comportava diferente derruba a variância entre
    clusters e produz "emissores necessários ~1". Isso é artefato de amostra,
    não poder — e tem de vir marcado como não decidível.
    """

    def test_dois_clusters_saem_marcados_como_nao_decidiveis(self):
        resultado = sens._poder({"A": [0.10, 0.11], "B": [0.10, 0.12]})
        assert resultado["emissores"] == 2
        assert resultado["decidivel"] is False
        assert "abaixo do mínimo" in resultado["ressalva"]

    def test_tres_clusters_bastam_em_numero_mas_a_conta_segue_invalidada(self):
        """Contrato C6: clusters suficientes NÃO tornam a conta válida.

        Este teste afirmava `decidivel is True` e `ressalva is None` para três
        clusters — e era exatamente por isso que a sensibilidade publicava
        `16` e `60` emissores com selo de decidível, apesar de F3 ter
        invalidado a fórmula. A asserção antiga não é enfraquecida: ela é
        SUBSTITUÍDA por uma mais forte, que exige a marcação de invalidez. O
        que o teste media (contagem de clusters) continua medido, agora no
        campo que carrega esse significado.
        """
        resultado = sens._poder(
            {"A": [0.10, 0.11], "B": [0.20, 0.22], "C": [0.30, 0.31]}
        )
        assert resultado["clusters_suficientes"] is True
        assert resultado["decidivel"] is False
        assert resultado["calculo_de_poder_invalidado_por"] == "F3"
        assert "F3" in resultado["ressalva"]
        # Os números seguem publicados — invalidar não é apagar.
        assert resultado["emissores_necessarios"] is not None

    def test_dispersao_e_o_que_move_o_numero_de_emissores(self):
        """Mesma média de erro, dispersão diferente: exigência diferente.

        É o mecanismo inteiro do achado: o "~128 emissores" não mede quantos
        bancos existem, mede o quanto os três medidos discordam entre si.
        """
        junto = sens._poder({"A": [0.20], "B": [0.20], "C": [0.20]})
        espalhado = sens._poder({"A": [0.05], "B": [0.20], "C": [0.35]})
        assert junto["emissores_necessarios"] == 0, (
            "erro idêntico entre emissores tem dispersão zero — e zero é "
            "resultado, não ausência de medição"
        )
        assert espalhado["emissores_necessarios"] > junto["emissores_necessarios"]


class TestArtefatoPublicado:
    """O artefato é a evidência do que o relatório afirma."""

    def test_o_artefato_existe_e_declara_que_e_diagnostico(self):
        dados = json.loads(ARTEFATO.read_text(encoding="utf-8"))
        assert "DIAGNÓSTICO" in dados["natureza"]
        assert "Não substitui gate" in dados["natureza"]
        # A inversão de sentido dos cenários fica declarada no próprio
        # artefato: sem isso, alguém compararia v1 com v2 achando que a conta
        # mudou, quando o que mudou foi qual estado é o real.
        assert "inverteu" in dados["o_que_mudou"]

    def test_nenhum_cenario_de_intervalo_publica_limite_sem_demonstracao(self):
        """Guarda contra o retorno do achado F1 — em QUALQUER dos cenários.

        **Este caso substitui dois que afirmavam o contrário.** Eles se
        chamavam `test_a_conformidade_derrubou_o_rotulo_abaixo_do_sinal` e
        `test_o_g2_que_passava_era_comprado_pelo_defeito`, e travavam a leitura
        de que o J conforme tem «rótulo mais ruidoso que o sinal» (G2 1,0464)
        contra um estado anterior que «passava com folga de 48×».

        A revisão independente de 2026-09-10 mostrou que **as duas leituras
        vinham de limites inventados**: o residual líquido de uma rubrica que
        mistura juros e câmbio não limita a parcela de juros. Sem limite
        demonstrável não há intervalo, não há centro para servir de rótulo e
        não há largura para chamar de ruído — então não há razão G2 nenhuma a
        publicar. Era o achado F12: o 1,0464 reproduzia, mas não media o que
        se dizia que media.

        O caso agora trava o que importa: se um `g2_razao_ruido_sobre_sinal`
        reaparecer num cenário de intervalo, os limites fabricados voltaram.
        """
        dados = json.loads(ARTEFATO.read_text(encoding="utf-8"))
        cenarios = [
            dados["intervalo_conforme"],
            dados["intervalo_estado_anterior_nao_conforme"],
        ]
        for cenario in cenarios:
            assert "g2_razao_ruido_sobre_sinal" not in cenario, (
                "razão G2 publicada sobre intervalo cujo limite não se "
                "demonstra: o defeito F1 voltou"
            )
            assert "g2_meia_largura_mediana" not in cenario
        # E o cenário conforme não sobra população alguma: toda rubrica não
        # identificada da série carece de limite demonstrável.
        assert dados["intervalo_conforme"]["observacoes"] == 0
        assert dados["intervalo_conforme"]["alvos"] == 0
        assert dados["intervalo_conforme"]["emissores_restantes"] == []

    def test_o_cenario_anterior_tambem_colapsa_e_isso_e_o_ponto(self):
        """Nem forçar as suspeitas de volta a J salva a população.

        Antes, devolver as rubricas cambiais a J reconstituía um cenário com
        3 emissores e 55 alvos, usado para medir «o que a conformidade
        custou». Com a correção do F1 esse cenário também colapsa — sobra
        **um** emissor —, porque as OUTRAS rubricas não identificadas da série
        continuam sem limite demonstrável.

        Isso desmonta a comparação inteira: não havia dois estados a comparar,
        havia dois conjuntos de limites inventados de tamanhos diferentes.
        """
        dados = json.loads(ARTEFATO.read_text(encoding="utf-8"))
        anterior = dados["intervalo_estado_anterior_nao_conforme"]
        assert len(anterior["emissores_restantes"]) < prontidao.MINIMO_DE_CLUSTERS
        assert "veredito" in anterior
        assert "destrói a população" in anterior["veredito"]

    def test_metade_da_volatilidade_do_itau_era_a_rubrica_cambial(self):
        """O que corrige o "~128 emissores" publicado antes."""
        dados = json.loads(ARTEFATO.read_text(encoding="utf-8"))
        com = dados["volatilidade_estado_anterior_nao_conforme"]
        limpo = dados["volatilidade_conforme"]
        assert com["mae_por_emissor"]["019348"] > (
            1.8 * limpo["mae_por_emissor"]["019348"]
        ), "a rubrica cambial respondia por perto da metade da oscilação"
        assert limpo["dispersao_max_sobre_min"] < com["dispersao_max_sobre_min"]
        # **Substituição declarada pelo contrato C6.** As duas asserções que
        # vinham aqui — `emissores_necessarios` cai, e continua acima de 3 —
        # afirmavam uma conclusão que a revisão independente invalidou em F3:
        # a conta reamostra a dispersão da perda do baseline, não a diferença
        # pareada. Trancá-la no contrato era o que mantinha o "16/60" com selo
        # de válido mesmo depois de o pacote de 10/09 declarar F3 adiado.
        #
        # A perda DESCRITIVA continua asseverada acima (MAE e dispersão); o
        # que sai é a leitura dela como poder. Asserção fraca sobre número sem
        # validade vira asserção forte sobre a marcação de invalidez.
        for cenario in (limpo, com):
            assert cenario["decidivel"] is False
            assert cenario["calculo_de_poder_invalidado_por"] == "F3"
            assert "F3" in cenario["ressalva"]
            # Publicado e marcado, não apagado.
            assert cenario["emissores_necessarios"] is not None

    def test_o_diagnostico_de_volatilidade_avisa_que_nao_e_J(self):
        dados = json.loads(ARTEFATO.read_text(encoding="utf-8"))
        for chave in ("volatilidade_conforme",
                      "volatilidade_estado_anterior_nao_conforme"):
            assert "NÃO é J" in dados[chave]["aviso"]
