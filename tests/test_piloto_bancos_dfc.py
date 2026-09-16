"""Contratos do piloto documental B-DFC-01J.

Cada caso corresponde a um jeito conhecido de produzir J plausível e errado.
Fixtures sintéticas exercitam o software; os casos com PDF local exercitam a
extração real — uma categoria não substitui a outra.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import replace
from decimal import Decimal

import pytest

from scripts import piloto_bancos_dfc as piloto


# ---------------------------------------------------------------------------
# Escopo e guardas
# ---------------------------------------------------------------------------


class TestEscopo:
    def test_os_25_pacotes_existem_por_construcao(self):
        """Escopo montado a partir de documento encontrado esconderia a lacuna.

        Os 25 têm de existir mesmo que nenhum documento seja localizado — é o
        denominador que torna a cobertura mensurável.
        """
        escopo = piloto.montar_escopo()
        assert len(escopo) == 25
        assert len({linha["pacote_id"] for linha in escopo}) == 25

    def test_cd_cvm_preserva_zeros_a_esquerda(self):
        """`000906` virando `906` quebraria a resolução por registro (RN11)."""
        escopo = piloto.montar_escopo()
        assert all(len(linha["cd_cvm"]) == 6 for linha in escopo)
        assert any(linha["cd_cvm"] == "000906" for linha in escopo)

    def test_cinco_bancos_por_cinco_periodos(self):
        escopo = piloto.montar_escopo()
        assert len({linha["cd_cvm"] for linha in escopo}) == 5
        assert len({linha["periodo"] for linha in escopo}) == 5


class TestGuardaDeHoldout:
    def test_caminho_do_holdout_e_barrado(self):
        with pytest.raises(piloto.ErroEscopo, match="holdout"):
            piloto.verificar_caminho_permitido(
                "corpus/holdout_2T2026/raw/qualquer.pdf"
            )

    def test_guarda_vale_para_caminho_absoluto_e_windows(self):
        with pytest.raises(piloto.ErroEscopo):
            piloto.verificar_caminho_permitido(
                "/home/x/projeto/corpus/holdout_2T2026/manifesto.csv"
            )
        with pytest.raises(piloto.ErroEscopo):
            piloto.verificar_caminho_permitido(
                r"C:\projeto\corpus\holdout_2T2026\raw\x.pdf"
            )

    def test_periodo_do_holdout_e_barrado_nas_duas_convencoes(self):
        for periodo in ("2026T2", "2T2026"):
            with pytest.raises(piloto.ErroEscopo):
                piloto.verificar_periodo_no_escopo(periodo)

    def test_periodo_fora_do_escopo_e_barrado(self):
        """`2015T1` está fora do universo gerado (2018–2026)."""
        with pytest.raises(piloto.ErroEscopo, match="escopo"):
            piloto.verificar_periodo_no_escopo("2015T1")

    def test_caminho_legitimo_passa(self):
        piloto.verificar_caminho_permitido("corpus/ifrs/raw/bb_ifrs_1T2025.pdf")
        piloto.verificar_periodo_no_escopo("2024T1")
        piloto.verificar_periodo_no_escopo("2024A")  # período de apoio


# ---------------------------------------------------------------------------
# Leitura numérica
# ---------------------------------------------------------------------------


class TestParseDecimal:
    def test_parenteses_sao_negativo_contabil(self):
        assert piloto.parsear_decimal("(9.705.067)") == Decimal("-9705067")

    def test_valor_positivo_sem_parenteses(self):
        assert piloto.parsear_decimal("23.767.880") == Decimal("23767880")

    def test_nao_aplica_multiplicador_de_escala(self):
        """`normalizar_numero_ptbr` transformaria "1.234" com "mil" em 1,2 M.

        Em tabela de demonstração a escala é propriedade do cabeçalho; deduzi-la
        de palavra solta foi o defeito que invalidou a rodada A do CAND-04.
        """
        assert piloto.parsear_decimal("1.234") == Decimal("1234")

    def test_zero_explicito_nao_e_ausente(self):
        assert piloto.parsear_decimal("0") == Decimal("0")
        with pytest.raises(piloto.ErroExtracao):
            piloto.parsear_decimal("--")

    def test_decimal_nao_float(self):
        """Erro binário em soma de bilhões destruiria a reconciliação."""
        valor = piloto.parsear_decimal("168.990.827")
        assert isinstance(valor, Decimal)
        assert valor * 1000 == Decimal("168990827000")

    def test_nao_ha_coercao_por_abs(self):
        """Despesa negativa que vira positiva por `abs` esconde reversão."""
        assert piloto.parsear_decimal("(221.899)") < 0

    def test_numeros_da_linha_preserva_ordem_e_texto(self):
        linha = "  Recursos de clientes    (16.773.383)     (14.487.775)"
        achados = piloto.numeros_da_linha(linha)
        assert [texto for texto, _ in achados] == [
            "(16.773.383)", "(14.487.775)"
        ]
        assert [valor for _, valor in achados] == [
            Decimal("-16773383"), Decimal("-14487775")
        ]


class TestLocalizarRubrica:
    def test_rotulo_ambiguo_falha_em_vez_de_escolher(self):
        """Duas linhas com o mesmo rótulo são tabelas diferentes.

        Devolver a primeira decidiria em silêncio qual tabela vale.
        """
        pagina = "Depósitos   (1.000)\noutra coisa\nDepósitos   (2.000)\n"
        with pytest.raises(piloto.ErroExtracao, match="ambígua"):
            piloto.localizar_rubrica(pagina, "Depósitos")

    def test_rotulo_ausente_falha(self):
        with pytest.raises(piloto.ErroExtracao, match="não encontrada"):
            piloto.localizar_rubrica("nada aqui\n", "Depósitos")

    def test_rotulo_quebrado_em_duas_linhas_e_recuperado(self):
        """Caso real do BB no layout de quatro colunas.

        O rótulo quebra e os números ficam na linha seguinte; exigir os dois
        juntos perderia a parcela inteira — e perder parcela de J em silêncio
        é exatamente o que o contrato proíbe.
        """
        pagina = (
            "  Recursos de emissões de títulos e valores\n"
            "                       (21.080.376)   (14.191.760)\n"
            "  mobiliários\n"
        )
        rotulo, valores = piloto.localizar_rubrica(
            pagina, "Recursos de emissões de títulos"
        )
        assert "e valores" in rotulo
        assert piloto.numeros_da_linha(valores)[0][1] == Decimal("-21080376")

    def test_rotulo_sem_valores_adjacentes_falha(self):
        pagina = "Depósitos\n\n\n\n\n\ntexto sem número\n"
        with pytest.raises(piloto.ErroExtracao, match="sem linha de valores"):
            piloto.localizar_rubrica(pagina, "Depósitos")


# ---------------------------------------------------------------------------
# Construção de J
# ---------------------------------------------------------------------------


def _fato(conceito, valor, tratamento, periodo="2024T1", fonte="bb_ifrs_2025T1",
          limite_demonstravel=False):
    return piloto.Fato(
        fato_id=f"{fonte}|{conceito}|{periodo}",
        pacote_id="001023-" + periodo,
        fonte_id=fonte,
        conceito=conceito,
        rotulo_original=conceito,
        periodo=periodo,
        coluna_indice=0,
        texto_original=str(valor),
        valor=Decimal(valor),
        unidade="milhares_de_reais",
        valor_reais=Decimal(valor) * 1000,
        pagina_pdf=30,
        pagina_impressa="19",
        nota="nota de teste",
        tratamento=tratamento,
        motivo="fixture",
        base_contabil="IFRS",
        perimetro="consolidado",
        evidencia="fixture",
        limite_demonstravel=limite_demonstravel,
    )


class TestConstruirJ:
    def test_composicao_exaustiva_sem_residual_e_identificada(self):
        fatos = [
            _fato("total", "-300", "total"),
            _fato("a", "-100", "incluir"),
            _fato("b", "-200", "incluir"),
        ]
        resultado = piloto.construir_j(fatos, "2024T1")
        assert resultado.status == "identificado"
        assert resultado.limite_inferior == resultado.limite_superior

    def test_residual_COM_limite_demonstravel_vira_intervalo(self):
        """Intervalo é legítimo SÓ quando o limite da rubrica se demonstra.

        **Este caso já afirmava o contrário e estava errado.** Ele se chamava
        `test_residual_sem_composicao_vira_intervalo_nao_ponto` e exigia
        intervalo para QUALQUER residual — o defeito F1 da revisão
        independente de 2026-09-10. O contrato que o caso realmente protege
        («proíbe somar as linhas disponíveis e chamar de total») continua
        verificado; o que mudou é que o intervalo passou a exigir a declaração
        de limite demonstrável, sem a qual não há teto.
        """
        fatos = [
            _fato("total", "-300", "total"),
            _fato("a", "-100", "incluir"),
            _fato("b", "-190", "incluir"),
            _fato("outras", "-10", "nao_identificado",
                  limite_demonstravel=True),
        ]
        resultado = piloto.construir_j(fatos, "2024T1")
        assert resultado.status == "limitado"
        assert resultado.limite_inferior == Decimal("290")
        assert resultado.limite_superior == Decimal("300")
        assert resultado.conceitos_sem_limite_demonstravel == ()

    def test_residual_SEM_limite_demonstravel_nao_produz_intervalo(self):
        """Achado F1: residual líquido não limita a parcela de juros.

        Contraprova exata da revisão independente: incluída −100, desconhecida
        +30, total −70. O programa fechava a nota e declarava «[70, 100]», mas
        a desconhecida pode ser −20 de juros + 50 de ganho cambial, e então J
        vale 120 — FORA do intervalo, com o fechamento ainda exato. Limite que
        não se demonstra é limite inventado.
        """
        fatos = [
            _fato("total", "-70", "total"),
            _fato("incluida", "-100", "incluir"),
            _fato("mistura_juros_e_cambio", "30", "nao_identificado"),
        ]
        resultado = piloto.construir_j(fatos, "2024T1")
        assert resultado.status == "nao_identificado"
        # O fechamento CONTINUA exato: é o que torna o defeito invisível.
        assert resultado.fechamento_confere is True
        # Nenhum limite é publicado, para que ninguém o use como J.
        assert resultado.limite_inferior == Decimal(0)
        assert resultado.limite_superior == Decimal(0)
        assert resultado.conceitos_sem_limite_demonstravel == (
            "mistura_juros_e_cambio",
        )
        # O piso fica legível, mas fora dos campos de limite.
        assert resultado.soma_incluidas_quando_sem_limite == Decimal("100")

    def test_duas_desconhecidas_que_se_anulam_nao_viram_ponto(self):
        """Achado F1, segunda contraprova: residual líquido zero ≠ ausência.

        Desconhecidas de +30 e −30 somam zero e produziam `identificado` com J
        como PONTO exato. Mas cada uma pode conter juros (20 e 10) compensados
        por câmbio, e J seria 130. `identificado` passou a exigir ausência de
        rubrica não identificada, não residual líquido nulo.
        """
        fatos = [
            _fato("total", "-100", "total"),
            _fato("incluida", "-100", "incluir"),
            _fato("d1", "30", "nao_identificado"),
            _fato("d2", "-30", "nao_identificado"),
        ]
        resultado = piloto.construir_j(fatos, "2024T1")
        assert resultado.status != "identificado"
        assert resultado.status == "nao_identificado"
        assert resultado.residuo_nao_identificado == Decimal(0)
        assert resultado.limite_superior == Decimal(0)

    def test_sem_parcela_incluida_nao_produz_limite_falso(self):
        """Somar rubricas não identificadas daria "limite" que não é limite.

        No BTG as duas decomposições (por instrumento e por natureza) descrevem
        o MESMO total; somá-las contaria o mesmo dinheiro duas vezes.
        """
        fatos = [
            _fato("por_natureza", "-300", "nao_identificado"),
            _fato("por_instrumento_a", "-100", "nao_identificado"),
            _fato("por_instrumento_b", "-200", "nao_identificado"),
        ]
        resultado = piloto.construir_j(fatos, "2024T1")
        assert resultado.status == "nao_identificado"
        assert resultado.limite_superior == Decimal(0)
        assert resultado.conceitos_incluidos == []

    def test_soma_que_nao_fecha_no_total_fica_visivel(self):
        """Divergência vira conflito, nunca `max`, média ou escolha silenciosa."""
        fatos = [
            _fato("total", "-300", "total"),
            _fato("a", "-100", "incluir"),
            _fato("b", "-150", "incluir"),
        ]
        resultado = piloto.construir_j(fatos, "2024T1")
        assert resultado.fechamento_confere is False

    def test_periodo_sem_fato_nao_inventa_pacote(self):
        assert piloto.construir_j([_fato("a", "-1", "incluir")], "2024T3") is None


class TestDerivacaoTrimestre:
    def _fatos_base(self):
        return [
            _fato("total", "-1000", "total", "2024A", "bb_ifrs_2025A"),
            _fato("a", "-800", "incluir", "2024A", "bb_ifrs_2025A"),
            _fato("total", "-700", "total", "2024M9", "bb_ifrs_2025T3"),
            _fato("a", "-560", "incluir", "2024M9", "bb_ifrs_2025T3"),
        ]

    def _derivacao(self):
        return piloto.DerivacaoTrimestre(
            "001023", "2024T4", "bb_ifrs_2025A", "2024A",
            "bb_ifrs_2025T3", "2024M9", "ressalva de teste",
        )

    def test_q4_e_a_diferenca_entre_acumulados(self):
        derivados, _ = piloto.derivar_trimestre(
            self._fatos_base(), self._derivacao()
        )
        por_conceito = {f.conceito: f.valor for f in derivados}
        assert por_conceito["total"] == Decimal("-300")
        assert por_conceito["a"] == Decimal("-240")

    def test_derivado_guarda_todos_os_operandos(self):
        _, linhagem = piloto.derivar_trimestre(
            self._fatos_base(), self._derivacao()
        )
        calculados = [r for r in linhagem if r["status"] == "calculado"]
        assert calculados
        assert all(len(r["operandos"]) == 2 for r in calculados)
        assert all(r["marcado_como"] == "derivado" for r in calculados)

    def test_operando_ausente_impede_derivacao_e_nao_vira_zero(self):
        """Dividir anual por quatro ou inferir zero de célula vazia é proibido."""
        fatos = [f for f in self._fatos_base()
                 if not (f.conceito == "a" and f.periodo == "2024M9")]
        derivados, linhagem = piloto.derivar_trimestre(fatos, self._derivacao())
        assert [f.conceito for f in derivados] == ["total"]
        indisponiveis = [r for r in linhagem if r["status"] == "indisponivel"]
        assert len(indisponiveis) == 1
        assert "ausente" in indisponiveis[0]["motivo"]

    def test_derivado_nao_e_certificado_como_historico(self):
        _, linhagem = piloto.derivar_trimestre(
            self._fatos_base(), self._derivacao()
        )
        calculados = [r for r in linhagem if r["status"] == "calculado"]
        assert all(
            r["disponibilidade"] == "nao_certificada" for r in calculados
        )


# ---------------------------------------------------------------------------
# Extração real contra os PDFs locais
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def extracao():
    """Extração real contra os documentos IFRS já versionados.

    Não versiona PDF como fixture: usa os que o manifesto do corpus `ifrs` já
    declara, pelo caminho e hash registrados.
    """
    fonte = next(f for f in piloto.FONTES if f.fonte_id == "bb_ifrs_2025T1")
    if not fonte.caminho.is_file():
        pytest.skip(f"PDF do corpus IFRS ausente: {fonte.caminho}")
    return piloto.executar_extracao()


@pytest.fixture(scope="module")
def auditoria(extracao):
    fatos, resultados, _, _ = extracao
    return piloto.montar_auditoria(fatos, resultados)


class TestExtracaoReal:
    def test_bb_fecha_a_composicao_no_total_impresso(self, extracao):
        """Sem tolerância escolhida: a nota é publicada em milhares inteiros."""
        _, resultados, _, _ = extracao
        bb = [r for r in resultados if r.cd_cvm == "001023"]
        assert bb, "nenhum resultado do BB"
        assert all(r.fechamento_confere for r in bb)

    def test_bb_tem_os_cinco_periodos_do_escopo(self, extracao):
        _, resultados, _, _ = extracao
        periodos = {r.periodo for r in resultados if r.cd_cvm == "001023"}
        assert periodos == set(piloto.PERIODOS)

    def test_trimestres_isolados_de_2024_somam_ao_acumulado(self, extracao):
        """Contraprova entre TRÊS documentos distintos.

        T1 vem do documento do 1T2025, T2 do 2T2025 e T3 do 3T2025; o acumulado
        de nove meses é impresso no 3T2025. Fecharem exatamente valida o
        mapeamento de colunas — se uma coluna estivesse trocada, não fecharia.
        """
        fatos, _, _, _ = extracao

        def valor(fonte_id, periodo):
            return next(
                f.valor for f in fatos
                if f.fonte_id == fonte_id
                and f.conceito == "despesa_juros_total"
                and f.periodo == periodo
            )

        soma = (
            valor("bb_ifrs_2025T1", "2024T1")
            + valor("bb_ifrs_2025T2", "2024T2")
            + valor("bb_ifrs_2025T3", "2024T3")
        )
        assert soma == valor("bb_ifrs_2025T3", "2024M9")

    def test_btg_nao_produz_j_apesar_de_uma_soma_fechar(self, extracao):
        """A soma das linhas por instrumento fecha em 2025T1 e erra em 2024T1.

        Aceitar o fechamento de um período como identidade produziria J
        plausível e errado — a falha exata que o projeto existe para combater.
        """
        _, resultados, _, _ = extracao
        btg = [r for r in resultados if r.cd_cvm == "022616"]
        assert btg
        assert all(r.status == "nao_identificado" for r in btg)
        assert all(r.limite_superior == Decimal(0) for r in btg)

    def test_santander_nao_produz_j_por_mistura_atuarial(self, extracao):
        """A nota de fundos de pensão declara que o atuarial entra NESTA linha.

        A informação é qualitativa: não autoriza inventar montante a subtrair.
        """
        _, resultados, _, _ = extracao
        santander = [r for r in resultados if r.cd_cvm == "020532"]
        assert santander
        assert all(r.status == "nao_identificado" for r in santander)

    def test_toda_cifra_tem_procedencia(self, extracao):
        fatos, _, _, _ = extracao
        for fato in fatos:
            assert fato.pagina_pdf > 0
            assert fato.evidencia
            # A unidade é propriedade da FONTE: o Itaú publica em milhões e os
            # outros quatro em milhares. Fixar uma só aqui esconderia a
            # armadilha de escala em vez de travá-la.
            assert fato.unidade in piloto.MULTIPLICADOR_UNIDADE
            assert fato.valor_reais == (
                fato.valor * piloto.MULTIPLICADOR_UNIDADE[fato.unidade]
            )
            assert fato.base_contabil == "IFRS"
            assert fato.perimetro == "consolidado"


class TestAuditoria:
    def test_nenhum_pacote_desaparece(self, auditoria):
        """Pacote sem documento continua no denominador, com motivo."""
        assert len(auditoria) == 25
        sem_fonte = [a for a in auditoria if a["fatos_extraidos"] == 0]
        assert sem_fonte
        assert all(a["motivo"] for a in sem_fonte)

    def test_pacote_sem_documento_nao_e_aprovado(self, auditoria):
        for linha in auditoria:
            if linha["fatos_extraidos"] == 0:
                assert linha["p0_integridade"] == "NAO_IDENTIFICADO"
                assert linha["j_status"] == "sem_fonte"

    def test_as_restated_nunca_recebe_p3_conferido(self, auditoria):
        """Coluna comparativa em documento posterior não certifica histórico.

        Este teste já afirmou que NENHUM pacote poderia ter P3 conferido. Isso
        deixou de valer em 2026-09-09, quando os arquivamentos originais de
        Itaú e Bradesco foram recuperados do catálogo IPE com data de entrega
        à CVM. O contrato que permanece é mais estreito e é o que importa:
        `as_restated` **nunca** vira CONFERIDO.
        """
        restated = [a for a in auditoria if a["base_temporal"] == "as_restated"]
        assert restated, "sem caso as-restated, o teste não prova nada"
        assert all(a["p3_historico"] != "CONFERIDO" for a in restated)

    def test_p3_conferido_exige_data_de_publicacao_demonstrada(self, auditoria):
        """Saber que o documento é do trimestre não é saber quando existiu.

        Os PDFs do corpus `ifrs` vieram de sites de RI e o manifesto só tem a
        data de download; eles ficam em `SEM_DATA_DE_PUBLICACAO`, nunca em
        CONFERIDO.
        """
        for linha in auditoria:
            if linha["p3_historico"] == "CONFERIDO":
                assert linha["disponivel_em"], (
                    f"{linha['pacote_id']} conferiu P3 sem data de publicação"
                )
            if linha["base_temporal"] == "original" and not linha["disponivel_em"]:
                assert linha["p3_historico"] == "SEM_DATA_DE_PUBLICACAO"

    def test_p2_sem_total_e_nao_aplicavel_nao_conflito(self, auditoria):
        """"Não confere" e "não se aplica" são estados diferentes."""
        sem_total = [
            a for a in auditoria
            if a["fatos_extraidos"] and not a["j_total_declarado"]
        ]
        assert all(a["p2_aritmetica"] == "NAO_APLICAVEL" for a in sem_total)

    def test_fechamento_aritmetico_e_certificado_semantico_sao_INDEPENDENTES(
        self, auditoria
    ):
        """P2 mede a soma; `j_status` mede se J foi identificado. São dois.

        **Este caso nasceu de um erro do caso acima.** Ele afirmava que todo
        pacote `nao_identificado` tem P2 `NAO_APLICAVEL` — verdade acidental,
        de quando `nao_identificado` só acontecia sem nenhuma parcela incluída.
        Depois da correção do achado F1, um pacote pode ter total declarado,
        somar EXATO nele (P2 CONFERIDO) e ainda assim não ter J identificado,
        porque uma rubrica não separável não tem limite demonstrável.

        É a separação que a revisão independente exigiu: fechar a aritmética
        não certifica a semântica. Confundir os dois é o que fez o G0 passar.
        """
        com_total = [a for a in auditoria if a["j_total_declarado"]]
        assert com_total, "sem pacote com total declarado o caso não mede nada"
        # Existe pelo menos um pacote que FECHA e cujo J NÃO é identificado.
        assert any(
            a["p2_aritmetica"] == "CONFERIDO"
            and a["j_status"] == "nao_identificado"
            for a in com_total
        )
        # E P2 nunca é NAO_APLICAVEL quando há total: aí ele é mensurável.
        assert all(a["p2_aritmetica"] != "NAO_APLICAVEL" for a in com_total)

    def test_contagens_do_resumo_batem_com_a_tabela(self, auditoria):
        com_fonte = sum(1 for a in auditoria if a["fatos_extraidos"])
        sem_fonte = sum(1 for a in auditoria if not a["fatos_extraidos"])
        assert com_fonte + sem_fonte == 25

    def test_nenhum_gate_autoriza_treino(self, auditoria):
        """Não existe mínimo aprovado que autorize modelo a partir daqui."""
        assert all("aprovado_para_treino" not in linha for linha in auditoria)


class TestComponentesDFC:
    def test_saldo_da_secao_nao_pega_total_de_outra_nota(self):
        """"Total" repete na página; a âncora tem de ser o cabeçalho da seção."""
        pagina = (
            "14– Outra coisa\n"
            "Total     111     222\n"
            "15– Recursos de clientes\n"
            "Total     864.972.382     873.710.691\n"
        )
        fim, inicio = piloto._saldo_da_secao(pagina, "15– Recursos de clientes")
        assert fim == Decimal("864972382")
        assert inicio == Decimal("873710691")

    def test_secao_ausente_falha(self):
        with pytest.raises(piloto.ErroExtracao, match="não encontrada"):
            piloto._saldo_da_secao("nada\n", "99– Inexistente")

    def test_linha_da_dfc_que_repete_o_balanco_e_classificada_como_redundante(
        self, extracao
    ):
        """Caso medido do BB: as duas linhas reproduzem a diferença de saldos.

        Isso é contraprova ao argumento de que qualquer linha da DFC já traz
        informação nova — não prova que a DFC inteira seja redundante.
        """
        _, _, _, componentes = extracao
        assert componentes
        for componente in componentes:
            assert componente["residuo"] == "0"
            assert (
                componente["classificacao"]
                == "repeticao_de_diferenca_de_estoques"
            )

    def test_componente_guarda_formula_e_residuo(self, extracao):
        _, _, _, componentes = extracao
        for componente in componentes:
            assert componente["formula"] == "saldo_fim - saldo_inicio"
            assert "residuo" in componente
            assert componente["limitacao"]

    def test_classificacao_separa_nao_provado_de_provado(self, extracao):
        """"Não se provou redundante" não é "informação incremental provada"."""
        _, _, _, componentes = extracao
        for componente in componentes:
            assert componente["classificacao"] in {
                "repeticao_de_diferenca_de_estoques",
                "nao_se_provou_redundante",
            }


class TestGuardasAcrescentadasNaRevisao:
    """Defeitos encontrados pela revisão de conformidade de 2026-09-09."""

    def test_destino_de_saida_dentro_do_holdout_e_barrado(self):
        """A saída também é caminho: gravar no reservado o contaminaria."""
        with pytest.raises(piloto.ErroEscopo):
            piloto.verificar_caminho_permitido("corpus/holdout_2T2026/x")

    def test_destino_fora_do_diretorio_isolado_e_barrado(self):
        """`--diretorio artefatos/indice_vetorial` sobrescreveria produção."""
        with pytest.raises(piloto.ErroEscopo, match="isolado"):
            piloto.verificar_destino_isolado("artefatos/indice_vetorial")

    def test_destino_isolado_passa(self):
        piloto.verificar_destino_isolado("artefatos/b_dfc_01j")
        piloto.verificar_destino_isolado("/qualquer/raiz/artefatos/b_dfc_01j/")

    def test_credito_nao_vira_despesa_por_abs(self):
        """Somar `abs` parcela a parcela inflaria J com uma reversão.

        Duas despesas de -300 e uma reversão de +50 dão J = 250, não 350. O
        erro seria invisível onde não há total declarado para conferir.
        """
        fatos = [
            _fato("a", "-200", "incluir"),
            _fato("b", "-100", "incluir"),
            _fato("reversao", "50", "incluir"),
        ]
        resultado = piloto.construir_j(fatos, "2024T1")
        assert resultado.soma_incluidas == Decimal("250")

    def test_convencao_de_sinal_e_declarada_no_artefato(self):
        fatos = [_fato("a", "-100", "incluir")]
        registro = piloto.construir_j(fatos, "2024T1").para_json()
        assert "convencao_de_sinal" in registro

    def test_coluna_de_nota_nao_e_lida_como_valor(self):
        """O anual do Santander imprime a referência da nota antes das cifras.

        Lê-la como valor deslocaria as colunas e atribuiria 2024 ao lugar de
        2023 — em silêncio, porque a contagem passaria a fechar.
        """
        nota = next(
            n for n in piloto.NOTAS if n.fonte_id == "santander_ifrs_2025A"
        )
        assert nota.colunas_ignoradas_a_esquerda == 1

    def test_pacote_sem_fonte_diz_QUAL_dos_dois_estados_e(self, auditoria):
        """"Não existe documento" e "documento não traz a rubrica" diferem.

        Depois da recuperação de Itaú e Bradesco sobrou só o segundo caso: o
        anual do BTG está em disco e legível, mas as rubricas da nota 21 não
        aparecem sob os mesmos rótulos. O motivo tem de dizer isso, e não
        culpar a rede por uma lacuna de curadoria.
        """
        sem_fonte = [a for a in auditoria if not a["fatos_extraidos"]]
        assert sem_fonte
        for linha in sem_fonte:
            assert "rede" not in linha["motivo"] or "não rede" in linha["motivo"]
            assert "curadoria" in linha["motivo"]

    def test_santander_tem_os_cinco_periodos(self, extracao):
        """Contraprova do defeito: os PDFs 2T/3T/4T existiam e não estavam
        declarados, e o relatório dizia que o período dependia de rede."""
        _, resultados, _, _ = extracao
        periodos = {r.periodo for r in resultados if r.cd_cvm == "020532"}
        assert periodos == set(piloto.PERIODOS)


class TestRecuperacaoItauBradesco:
    """Contratos que só passaram a existir com os arquivamentos originais."""

    def test_periodo_do_documento_compara_data_base_nao_rotulo(self):
        """No documento do 3T, isolado e acumulado são AMBOS originais.

        `2024T3` e `2024M9` encerram os dois em 30/09/2024. Comparar rótulos
        trataria o acumulado como reapresentado e jogaria fora a evidência
        point-in-time que permite derivar o 4º trimestre.
        """
        assert piloto.periodo_e_do_documento("2024T3", "2024T3")
        assert piloto.periodo_e_do_documento("2024M9", "2024T3")
        assert not piloto.periodo_e_do_documento("2023T3", "2024T3")

    def test_multiplicador_de_unidade_e_declarado_por_fonte(self):
        """O Itaú publica em milhões; os outros quatro em milhares."""
        itau = next(n for n in piloto.NOTAS if n.fonte_id == "itau_ifrs_2025T1")
        bradesco = next(
            n for n in piloto.NOTAS if n.fonte_id == "bradesco_ifrs_2025T1"
        )
        assert itau.unidade == "milhoes_de_reais"
        assert bradesco.unidade == "milhares_de_reais"
        assert piloto.MULTIPLICADOR_UNIDADE[itau.unidade] == 1_000_000

    def test_fechamento_conta_as_linhas_EXCLUIDAS_pelo_contrato(self):
        """Excluída pelo contrato continua sendo parcela do total impresso.

        Deixá-la fora da conferência faria a nota mais completa dos cinco
        bancos — a do Bradesco, que abre até passivo de seguro — parecer
        conflitante.
        """
        fatos = [
            _fato("total", "-300", "total"),
            _fato("captacao", "-200", "incluir"),
            _fato("seguros", "-100", "excluir"),
        ]
        resultado = piloto.construir_j(fatos, "2024T1")
        assert resultado.fechamento_confere is True
        assert resultado.soma_incluidas == Decimal("200")
        assert resultado.excluido_por_contrato == Decimal("100")
        assert resultado.status == "identificado"

    def test_exclusao_documentada_e_subtraida_exata(self, extracao):
        """Bradesco: as exclusões são nomeadas com valor e saem por leitura.

        **Este caso já afirmou que o Bradesco dava J como PONTO.** Deixou de
        afirmar em 2026-09-10, quando a leitura das notas mostrou que
        `Obrigações por empréstimos e repasses` embute variação cambial e
        passou a NÃO IDENTIFICADA — J do Bradesco virou intervalo de 3,9% a
        6,3%. O contrato que este caso realmente protege **não** mudou e
        continua verificado aqui: exclusão publicada é subtraída EXATA, sem
        estimativa, e o fechamento confere. Trocar `identificado` por
        `limitado` não enfraquece a asserção — o que caiu foi um fato sobre a
        fonte, não a régua.
        """
        _, resultados, _, _ = extracao
        bradesco = [r for r in resultados if r.cd_cvm == "000906"]
        assert bradesco
        # As exclusões continuam nomeadas e subtraídas com valor próprio.
        assert all(r.conceitos_excluidos for r in bradesco)
        assert all(r.excluido_por_contrato > 0 for r in bradesco)
        # E a aritmética da nota continua fechando exato.
        assert all(r.fechamento_confere is True for r in bradesco)
        # O que mudou DE NOVO, em 2026-09-10 pela revisão independente
        # (achado F1): nem intervalo. A rubrica cambial não tem limite
        # demonstrável — o residual líquido dela não limita a parcela de
        # juros, porque câmbio tem os dois sinais —, então J do Bradesco é
        # `nao_identificado`. O contrato protegido por este caso continua
        # intacto nas três asserções acima; é o terceiro fato consecutivo
        # sobre a FONTE que muda, não a régua.
        assert all(r.status == "nao_identificado" for r in bradesco)
        assert all(
            "juros_emprestimos_e_repasses"
            in r.conceitos_sem_limite_demonstravel
            for r in bradesco
        )
        assert all(
            "juros_emprestimos_e_repasses" in r.conceitos_nao_identificados
            for r in bradesco
        )
        # Nenhum limite é publicado: intervalo sem teto demonstrável seria
        # limite inventado, e é exatamente o que o achado F1 proibiu.
        assert all(r.limite_inferior == r.limite_superior == 0 for r in bradesco)
        # Mas o piso permanece legível, fora dos campos de limite.
        assert all(
            r.soma_incluidas_quando_sem_limite > 0 for r in bradesco
        )

    def test_original_vence_reapresentada_na_escolha_da_fonte(self, auditoria):
        """Dois documentos cobrem 2024T1; o original não pode ser sobrescrito.

        O arquivamento de maio/2024 e a coluna comparativa do documento de
        2025 descrevem o mesmo trimestre. Pegar "a última que apareceu"
        destruiria a única evidência point-in-time.
        """
        linha = next(a for a in auditoria if a["pacote_id"] == "000906-2024T1")
        assert linha["base_temporal"] == "original"
        assert linha["fontes_alternativas"] >= 1

    def test_derivado_de_dois_originais_certifica_disponibilidade(self, auditoria):
        """Q4 = anual − 9M, ambos originais: calculável na entrega do anual."""
        linha = next(a for a in auditoria if a["pacote_id"] == "000906-2024T4")
        assert linha["base_temporal"] == "derivada_de_originais"
        assert linha["disponivel_em"] == "2025-02-07"
        assert linha["p3_historico"] == "CONFERIDO"

    def test_derivado_sem_operando_datado_nao_certifica(self, auditoria):
        """O 2024T4 do BB deriva de comparativas: não vira point-in-time."""
        linha = next(a for a in auditoria if a["pacote_id"] == "001023-2024T4")
        assert linha["base_temporal"] == "derivada_sem_certificacao"
        assert linha["p3_historico"] == "PENDENTE"

    def test_versoes_do_mesmo_periodo_ficam_ambas_registradas(self, extracao):
        """O Itaú reapresentou o 2T2024 um dia depois; guardar as duas.

        Aqui a republicação NÃO mudou J — e só se afirma isso porque as duas
        versões foram lidas, não porque se supôs estabilidade.
        """
        _, resultados, _, _ = extracao
        versoes = [
            r for r in resultados
            if r.periodo == "2024T2" and r.cd_cvm == "019348"
        ]
        assert {r.fonte_id for r in versoes} == {
            "itau_ifrs_2024T2_v1", "itau_ifrs_2024T2_v2"
        }
        assert len({r.limite_inferior for r in versoes}) == 1


class TestRegistroDeExecucao:
    def test_execucao_declara_a_coleta_em_rede(self, tmp_path, extracao):
        """A auditoria é offline, mas os dados chegaram por rede.

        Registrar só "rede_utilizada: false" seria verdade sobre o comando e
        mentira sobre a procedência dos documentos.
        """
        import json
        fatos, resultados, linhagem, componentes = extracao
        auditoria = piloto.montar_auditoria(fatos, resultados, componentes)
        destino = tmp_path / "artefatos/b_dfc_01j"
        piloto.gravar_artefatos(
            destino, fatos, resultados, auditoria, linhagem, componentes
        )
        execucao = json.loads((destino / "execucao.json").read_text())
        assert execucao["rede_utilizada_nesta_execucao"] is False
        assert execucao["rede_utilizada_na_coleta"]["documentos"] == 11
        assert execucao["chamadas_pagas"] == 0
        assert execucao["holdout_acessado"] is False


class TestExtensaoDaJanela:
    """A automação que permitiu escalar de 5 para dezenas de trimestres."""

    def test_papeis_de_coluna_resolvem_periodos_concretos(self):
        assert piloto.periodos_dos_papeis(
            ("iso", "iso_aa", "acum", "acum_aa"), "2024T3"
        ) == ("2024T3", "2023T3", "2024M9", "2023M9")

    def test_ordem_das_colunas_difere_por_emissor(self):
        """O BB imprime acumulado primeiro; o Itaú imprime isolado primeiro.

        `scripts/gate_g4.py` já registrou que a ordem "muda de emissor para
        emissor". Confiar em posição sem declarar por emissor atribuiria o
        trimestre à coluna do semestre.
        """
        assert piloto.LAYOUTS_POR_EMISSOR["001023"][4][0] == "acum"
        assert piloto.LAYOUTS_POR_EMISSOR["019348"][4][0] == "iso"

    def test_documento_anual_nao_tem_coluna_de_trimestre_isolado(self):
        """Anual publica exercício inteiro; o 4T sai por derivação."""
        assert piloto.periodos_dos_papeis(("iso", "iso_aa"), "2024A") == (
            "2024A", "2023A"
        )

    def test_pdf_truncado_e_rejeitado(self, tmp_path):
        """Caso real: `HTTP 200`, corpo começando com `%PDF` e sem `%%EOF`."""
        truncado = tmp_path / "truncado.pdf"
        truncado.write_bytes(b"%PDF-1.7\n" + b"0" * 4096)
        assert not piloto._pdf_esta_integro(truncado)

    def test_arquivo_que_nao_e_pdf_e_rejeitado(self, tmp_path):
        html = tmp_path / "erro.pdf"
        html.write_bytes(b"<html><body>Erro</body></html>")
        assert not piloto._pdf_esta_integro(html)

    def test_pdf_real_do_corpus_passa_na_validacao(self):
        fonte = next(f for f in piloto.FONTES if f.fonte_id == "bb_ifrs_2025T1")
        if not fonte.caminho.is_file():
            pytest.skip("PDF do corpus IFRS ausente")
        assert piloto._pdf_esta_integro(fonte.caminho)

    def test_pagina_da_nota_e_localizada_e_confere_com_a_curadoria(self):
        """Contraprova da automação contra as páginas declaradas à mão.

        Se a localização automática divergisse de uma única declaração manual,
        não haveria motivo para confiar nela nos documentos onde não há
        curadoria para comparar.
        """
        conferidos = 0
        for nota in piloto.NOTAS:
            fonte = next(
                f for f in piloto.FONTES if f.fonte_id == nota.fonte_id
            )
            if fonte.cd_cvm not in piloto.ANCORAS_POR_EMISSOR:
                continue
            if not fonte.caminho.is_file():
                continue
            sonda = piloto.ANCORAS_POR_EMISSOR[fonte.cd_cvm][0]
            assert piloto.localizar_pagina_da_nota(fonte.caminho, sonda) == (
                nota.pagina_pdf
            ), f"{nota.fonte_id}: página automática divergiu da declarada"
            papeis = piloto.LAYOUTS_POR_EMISSOR[fonte.cd_cvm][len(nota.colunas)]
            assert piloto.periodos_dos_papeis(
                papeis, fonte.periodo_documento
            ) == nota.colunas, f"{nota.fonte_id}: colunas divergiram"
            conferidos += 1
        assert conferidos >= 15, f"só {conferidos} notas conferidas"

    def test_identidade_trimestral_confere_entre_documentos(self, extracao):
        """T1+T2 = S1 e T1+T2+T3 = M9, com operandos de documentos DIFERENTES.

        É o que valida o mapeamento de colunas sem confiar em posição: se uma
        coluna estivesse trocada, a soma não fecharia.
        """
        fatos, _, _, _ = extracao
        conferencias = piloto.conferir_identidade_trimestral(fatos)
        assert conferencias, "nenhuma identidade pôde ser conferida"
        # `None` é "não verificável por mistura de vintages" e é um estado
        # legítimo; `False` é divergência de mapeamento e não pode existir.
        divergentes = [c for c in conferencias if c["confere"] is False]
        assert not divergentes, f"identidades divergentes: {divergentes}"
        assert any(c["confere"] is True for c in conferencias)

    def test_identidade_detecta_coluna_trocada(self):
        """Contraprova: com a soma errada, a conferência tem de reprovar."""
        base = [
            _fato("despesa_juros_total", "-100", "total", "2024T1"),
            _fato("despesa_juros_total", "-100", "total", "2024T2"),
            _fato("despesa_juros_total", "-999", "total", "2024S1"),
        ]
        for fato in base:
            object.__setattr__(fato, "cd_cvm_do_fato", "001023")
        conferencias = piloto.conferir_identidade_trimestral(base)
        assert any(not c["confere"] for c in conferencias)


class TestVintages:
    def test_espaco_espurio_e_colapsado_e_separador_de_coluna_preservado(self):
        """Medido: espaço isolado nunca separa coluna; separador é ≥3 espaços.

        Distribuição real de espaços entre dígitos nos documentos afetados:
        1 espaço em 65 casos, 3+ em 2.561, e **zero** casos de exatamente 2.
        """
        assert piloto.normalizar_espacos_espurios("(17 .1 77)") == "(17.177)"
        assert piloto.normalizar_espacos_espurios(
            "Depósitos    (1.234)     (5.678)"
        ) == "Depósitos    (1.234)     (5.678)"

    def test_reparo_nao_altera_o_resultado_do_piloto(self):
        """Contraprova: onde a extração já funcionava, o reparo é inócuo.

        Se o colapso de espaços mudasse um único número dos 25 pacotes
        congelados, ele estaria fundindo colunas em vez de reparar dígitos.
        """
        fonte = next(f for f in piloto.FONTES if f.fonte_id == "bb_ifrs_2025T1")
        if not fonte.caminho.is_file():
            pytest.skip("PDF do corpus IFRS ausente")
        _, resultados, _, _ = piloto.executar_extracao()
        bb = next(
            r for r in resultados
            if r.cd_cvm == "001023" and r.periodo == "2025T1"
        )
        assert bb.total_declarado == Decimal("47952209")
        assert bb.soma_incluidas == Decimal("47629112")

    def test_rotulo_partido_por_espaco_ainda_casa(self):
        """Os mesmos PDFs partem palavras: "Mercados I nte rbancários"."""
        pagina = "  Recursos de Mercados I nte rbancários   (8.843)  (8.094)\n"
        _, valores = piloto.localizar_rubrica(
            pagina, "Recursos de Mercados Interbancários"
        )
        assert piloto.numeros_da_linha(valores)[0][1] == Decimal("-8843")

    def test_reapresentacao_e_medida_e_nao_sobrescrita(self, extracao):
        """Bradesco 2022: o mesmo período tem valores diferentes por vintage.

        Registrar os dois é a entrega; escolher um sem dizer qual seria perder
        a distinção entre as-restated e as-originally-reported.
        """
        fatos, _, _, _ = extracao
        divergencias = piloto.divergencias_de_vintage(fatos)
        for registro in divergencias:
            assert Decimal(registro["amplitude"]) > 0
            assert len(registro["valores_por_fonte"]) >= 2

    def test_identidade_com_vintages_mistos_nao_vira_divergencia(self):
        """Somar reapresentado com original mede reapresentação, não mapeamento.

        Era o defeito: a conferência acusava "diverge" no Bradesco de 2022,
        quando a causa era o emissor ter reapresentado o período.
        """
        fatos = []
        for periodo, valor, fonte, origem in (
            ("2022T1", "-100", "doc_2023T1", "comparativa"),
            ("2022T2", "-100", "doc_2022T2", "propria"),
            ("2022S1", "-250", "doc_2022T2", "propria"),
        ):
            fato = _fato("despesa_juros_total", valor, "total", periodo, fonte)
            object.__setattr__(fato, "cd_cvm_do_fato", "000906")
            object.__setattr__(fato, "origem_periodo", origem)
            fatos.append(fato)
        conferencias = piloto.conferir_identidade_trimestral(fatos)
        mistas = [c for c in conferencias if c.get("base") == "mista"]
        assert mistas, "deveria haver identidade não verificável"
        assert all(c["confere"] is None for c in mistas)


# ---------------------------------------------------------------------------
# Derivação automática do 4º trimestre — a fatia que faltava na série
# ---------------------------------------------------------------------------


def _fonte_sintetica(fonte_id, periodo_documento, data_entrega="2025-02-07"):
    return piloto.Fonte(
        fonte_id=fonte_id,
        cd_cvm="001023",
        arquivo=f"{fonte_id}.pdf",
        hash_sha256="0" * 64,
        periodo_documento=periodo_documento,
        tipo_documento="demonstracoes_anuais",
        url="https://exemplo.invalido",
        data_download="2026-09-09",
        data_entrega=data_entrega,
        versao=1,
        protocolo=f"proto-{fonte_id}",
    )


def _fato_datado(conceito, valor, periodo, fonte, origem, data=None):
    return dataclasses.replace(
        _fato(conceito, valor, piloto._INCLUIR, periodo, fonte),
        origem_periodo=origem, disponivel_em=data, cd_cvm_do_fato="001023",
    )


class TestDerivacaoAutomaticaDo4T:
    """Sem o 4T a série perde um trimestre em cada quatro.

    Nenhum dos emissores publica o 4º trimestre isolado — o documento anual
    traz o exercício inteiro. É o mesmo defeito medido no §3.14 do AGENTS.md,
    quando dois trimestres por ano nunca fechavam janela de doze meses.
    """

    def _cenario(self, origem_anual, origem_9m, ano_doc_anual="2024A",
                 ano_doc_9m="2024T3"):
        fontes = [
            _fonte_sintetica("anual", ano_doc_anual),
            _fonte_sintetica("nove_meses", ano_doc_9m, "2024-11-08"),
        ]
        fatos = [
            _fato_datado("juros_depositos", "-1000", "2024A", "anual",
                         origem_anual, "2025-02-07"),
            _fato_datado("juros_depositos", "-700", "2024M9", "nove_meses",
                         origem_9m, "2024-11-08"),
        ]
        return fatos, fontes

    def test_deriva_quando_as_duas_safras_sao_originais(self):
        fatos, fontes = self._cenario("propria", "propria")
        derivacoes, recusas = piloto.derivacoes_automaticas(fatos, fontes)
        assert len(derivacoes) == 1 and not recusas
        assert derivacoes[0].periodo_alvo == "2024T4"
        assert "point-in-time" in derivacoes[0].ressalva

    def test_safra_mista_e_recusada_com_o_motivo(self):
        """Anual original menos 9M reapresentado não é a diferença de nada.

        A reapresentação do Bradesco de 2022 mediu 3,6% entre as duas safras
        do mesmo semestre: subtrair bases distintas produz um 4T inventado.
        """
        fatos, fontes = self._cenario("propria", "comparativa")
        derivacoes, recusas = piloto.derivacoes_automaticas(fatos, fontes)
        assert not derivacoes
        assert len(recusas) == 1
        assert "safra" in recusas[0]["motivo"].lower()
        assert recusas[0]["periodo_alvo"] == "2024T4"

    def test_operando_ausente_recusa_em_vez_de_zerar(self):
        fatos, fontes = self._cenario("propria", "propria")
        fatos = [f for f in fatos if f.periodo != "2024M9"]
        derivacoes, recusas = piloto.derivacoes_automaticas(fatos, fontes)
        assert not derivacoes and len(recusas) == 1
        assert "ausente" in recusas[0]["motivo"]

    def test_derivado_nao_certifica_data_de_safra_comparativa(self):
        """Duas comparativas do mesmo exercício derivam, sem certificar data."""
        fatos, fontes = self._cenario("comparativa", "comparativa",
                                      "2025A", "2025T3")
        derivacoes, _ = piloto.derivacoes_automaticas(fatos, fontes)
        assert len(derivacoes) == 1
        assert "não é certificada" in derivacoes[0].ressalva

    def test_os_quatro_trimestres_fecham_no_anual(self):
        """Contraprova aritmética: T1+T2+T3+T4 tem de dar o anual, exato."""
        fontes = [
            _fonte_sintetica("anual", "2024A"),
            _fonte_sintetica("nove_meses", "2024T3", "2024-11-08"),
        ]
        fatos = [
            _fato_datado("j", "-1000", "2024A", "anual", "propria",
                         "2025-02-07"),
            _fato_datado("j", "-700", "2024M9", "nove_meses", "propria",
                         "2024-11-08"),
        ]
        derivacoes, _ = piloto.derivacoes_automaticas(fatos, fontes)
        derivados, _ = piloto.derivar_trimestre(fatos, derivacoes[0])
        assert len(derivados) == 1
        # 9M (-700) + 4T derivado tem de reconstituir o anual (-1000).
        assert derivados[0].valor == Decimal("-300")
        assert derivados[0].origem_periodo == "derivada"

    def test_derivado_nunca_serve_de_operando_de_outro_derivado(self):
        """Cascata de derivação esconderia a linhagem de dois passos atrás."""
        fontes = [
            _fonte_sintetica("anual", "2024A"),
            _fonte_sintetica("nove_meses", "2024T3", "2024-11-08"),
        ]
        fatos = [
            _fato_datado("j", "-1000", "2024A", "anual", "propria"),
            _fato_datado("j", "-700", "2024M9", "nove_meses", "propria"),
            _fato_datado("j", "-300", "2024T4", "anual", "derivada"),
        ]
        derivacoes, recusas = piloto.derivacoes_automaticas(fatos, fontes)
        # O 4T já presente como "derivada" não vira operando: a função só olha
        # colunas A e M9, e a safra "derivada" não casa com "propria".
        assert all(d.periodo_alvo == "2024T4" for d in derivacoes)


# ---------------------------------------------------------------------------
# Número ambíguo não pode deslocar coluna
# ---------------------------------------------------------------------------


class TestNumeroAmbiguoNaoDesloca:
    """Descartar um número recusado no meio da linha desloca as colunas.

    Era o comportamento anterior: `numeros_da_linha` engolia o erro e seguia.
    A lista encurtava, a contagem de colunas saía errada e cada cifra podia
    ser atribuída ao período de outra coluna — plausível, não nulo e errado.
    """

    def test_token_ambiguo_interrompe_a_linha_inteira(self):
        with pytest.raises(piloto.ErroExtracao) as erro:
            piloto.numeros_da_linha("Total   (39.978)   (32.381)   (78,406)")
        assert "deslocaria" in str(erro.value)

    def test_linha_sem_ambiguidade_continua_lida_normalmente(self):
        lidos = piloto.numeros_da_linha("Total   (39.978)   (32.381)")
        assert [v for _, v in lidos] == [Decimal("-39978"), Decimal("-32381")]

    def test_contagem_de_colunas_nunca_sai_de_linha_com_recusa(self):
        """A contagem de 5 cifras não pode virar 2 por descarte silencioso."""
        linha = "Total  (41,923)  (21.543)  (81,576)  (46,025)"
        with pytest.raises(piloto.ErroExtracao):
            piloto.numeros_da_linha(linha)


# ---------------------------------------------------------------------------
# Dobra I <-> l: mesmo desenho, letras diferentes
# ---------------------------------------------------------------------------


class TestDobraDeLetraNaRubrica:
    def test_l_minusculo_casa_com_i_maiusculo(self):
        """O extrator devolve "lnterbancários" com L minúsculo."""
        texto = (
            "Depósitos                       (17.177)   (8.592)\n"
            "Recursos de Mercados lnterbancários   (8.843)   (8.094)\n"
        )
        _, linha = piloto.localizar_rubrica(
            texto, "Recursos de Mercados Interbancários"
        )
        assert "(8.843)" in linha

    def test_dobra_nao_cria_colisao_entre_os_rotulos_declarados(self):
        """Contraprova medida: 28 rótulos, zero colisões pela dobra.

        Se a dobra juntasse dois rótulos distintos, a unicidade exigida por
        `localizar_rubrica` passaria a reprovar notas íntegras.
        """
        import re as _re

        rotulos = set()
        for _, (_, _, _, familia, _) in piloto.ANCORAS_POR_EMISSOR.items():
            for rubrica in familia:
                rotulos.update(rubrica.rotulos)
        for familias in piloto.PERFIS_ALTERNATIVOS.values():
            for familia in familias:
                for rubrica in familia:
                    rotulos.update(rubrica.rotulos)

        def chave(t):
            return _re.sub(r"\s+", "", t).casefold()

        agrupado = {}
        for rotulo in rotulos:
            agrupado.setdefault(chave(rotulo).replace("l", "i"), set()).add(
                chave(rotulo)
            )
        colididos = {k: v for k, v in agrupado.items() if len(v) > 1}
        assert not colididos, f"a dobra colidiu: {colididos}"

    def test_unicidade_continua_sendo_a_trava(self):
        texto = (
            "Recursos de Mercados Interbancários   (1)\n"
            "Recursos de Mercados lnterbancários   (2)\n"
        )
        with pytest.raises(piloto.ErroExtracao) as erro:
            piloto.localizar_rubrica(texto, "Recursos de Mercados Interbancários")
        assert "ambígua" in str(erro.value)


# ---------------------------------------------------------------------------
# Alinhamento geométrico: célula em branco existe
# ---------------------------------------------------------------------------


class TestAlinhamentoGeometrico:
    #: Régua real do Itaú 1T2022 p.82, com as duas colunas preenchidas.
    REGUA = "Total                          (30.373)        (15.334)"

    def test_celula_em_branco_devolve_ausente_nunca_zero(self):
        linha = "Outros                            (40)"
        casado = piloto.alinhar_numeros_por_coluna(linha, self.REGUA, 2)
        assert casado[0][0] == "(40)"
        assert casado[1] is None, "coluna vazia virou valor"

    def test_valor_vai_para_a_coluna_da_direita_quando_alinha_a_direita(self):
        linha = "Outros                                          (63)"
        casado = piloto.alinhar_numeros_por_coluna(linha, self.REGUA, 2)
        assert casado[0] is None
        assert casado[1][0] == "(63)"

    def test_cifra_que_nao_alinha_com_coluna_nenhuma_e_recusada(self):
        linha = "Outros    (99)"
        with pytest.raises(piloto.ErroExtracao) as erro:
            piloto.alinhar_numeros_por_coluna(linha, self.REGUA, 2)
        assert "não se sabe a que período pertence" in str(erro.value)

    def test_duas_cifras_na_mesma_coluna_e_recusado(self):
        linha = "Outros                         (40) (41)"
        with pytest.raises(piloto.ErroExtracao):
            piloto.alinhar_numeros_por_coluna(linha, self.REGUA, 2)

    def test_regua_incompleta_nao_serve_de_regua(self):
        with pytest.raises(piloto.ErroExtracao) as erro:
            piloto.alinhar_numeros_por_coluna("Outros (40)", "Total (30.373)", 2)
        assert "não serve de régua" in str(erro.value)


# ---------------------------------------------------------------------------
# Leitura declarada de glifo ambíguo
# ---------------------------------------------------------------------------


class TestLeiturasDeclaradas:
    def test_leitura_declarada_nao_pode_alterar_digito(self):
        """Trocar dígito é correção, não leitura — e correção exige outra via."""
        with pytest.raises(piloto.ErroExtracao) as erro:
            piloto.LeituraDeclarada(
                "x", 1, "(41,923)", "(41.924)",
                "justificativa suficientemente longa para passar do mínimo "
                "de sessenta caracteres exigido pelo contrato.",
            )
        assert "altera dígitos" in str(erro.value)

    def test_justificativa_curta_e_recusada(self):
        with pytest.raises(piloto.ErroExtracao):
            piloto.LeituraDeclarada("x", 1, "(41,923)", "(41.923)", "porque")

    def test_glifo_ausente_nao_troca_nada(self):
        """Se o emissor republicar sem o defeito, nada é inventado."""
        texto = "Total   (41.923)   (21.543)"
        assert piloto.aplicar_leituras_declaradas(
            texto, "itau_ifrs_2023T2", 81
        ) == texto

    def test_glifo_presente_e_lido_com_o_separador_da_tabela(self):
        texto = "Total   (41,923)   (21.543)"
        lido = piloto.aplicar_leituras_declaradas(
            texto, "itau_ifrs_2023T2", 81
        )
        assert "(41.923)" in lido and "(41,923)" not in lido

    def test_declaracao_de_outra_fonte_nao_vaza(self):
        texto = "Total   (41,923)"
        assert piloto.aplicar_leituras_declaradas(
            texto, "bb_ifrs_2025A", 81
        ) == texto

    def test_toda_declarada_tem_procedencia_completa(self):
        for declarada in piloto.LEITURAS_DECLARADAS:
            assert declarada.fonte_id and declarada.pagina_pdf > 0
            assert len(declarada.justificativa) >= 60
            # A justificativa é de DESIGUALDADE, não de soma: usar a soma das
            # parcelas para escolher a leitura seria ajustar o dado ao teste.
            assert "parcela" in declarada.justificativa

    def test_as_cinco_declaradas_sao_as_medidas_no_manifesto(self):
        """Cinco glifos na varredura dos 65 documentos — nem mais, nem menos."""
        assert len(piloto.LEITURAS_DECLARADAS) == 5
        assert {d.fonte_id for d in piloto.LEITURAS_DECLARADAS} == {
            "itau_ifrs_2023T2", "itau_ifrs_2023T3"
        }


# ---------------------------------------------------------------------------
# Conformidade contratual: despesa de juros não é crédito
# ---------------------------------------------------------------------------


_FONTE_DE_TESTE = piloto.Fonte(
    fonte_id="bb_ifrs_2025T1",
    cd_cvm="001023",
    arquivo="bb_2025T1.pdf",
    hash_sha256="0" * 64,
    periodo_documento="2025T1",
    tipo_documento="demonstracoes_intermediarias_condensadas",
    url="https://exemplo.invalido",
    data_download="2026-09-09",
)


class TestCreditoEmParcelaIncluida:
    """Parcela incluída que vem CREDORA não é juros por competência.

    O contrato B-DFC-01J exclui nominalmente valor justo, câmbio e
    derivativos. Uma linha de despesa de captação publicada como crédito
    embute um desses — ou é reclassificação. Nos dois casos ela deixou de ser
    o que o contrato mandou somar, e a soma pode fechar do mesmo jeito: é a
    armadilha do BTG outra vez, achada do mesmo modo, olhando mais períodos.
    """

    def _resultado(self, valor_interbancario):
        fatos = [
            _fato("total", "-10000", piloto._TOTAL),
            _fato("juros_depositos", "-6000", piloto._INCLUIR),
            _fato("juros_interbancarios", valor_interbancario, piloto._INCLUIR),
        ]
        # O total é ajustado para que o FECHAMENTO continue conferindo: o
        # ponto do teste é que aritmética íntegra não prova semântica.
        soma = sum(Decimal(f.valor) for f in fatos[1:])
        fatos[0] = _fato("total", str(soma), piloto._TOTAL)
        return piloto.construir_j(fatos, "2024T1", _FONTE_DE_TESTE)

    def test_credito_marca_conformidade_como_nao_demonstrada(self):
        resultado = self._resultado("4000")
        assert resultado.fechamento_confere is True, "a aritmética fecha"
        assert resultado.creditos_em_incluidas == ("juros_interbancarios",)
        assert resultado.conformidade_contratual == "nao_demonstrada"

    def test_despesa_normal_nao_e_marcada(self):
        resultado = self._resultado("-4000")
        assert resultado.creditos_em_incluidas == ()
        assert resultado.conformidade_contratual == "aparente"

    def test_a_marca_viaja_no_json(self):
        dados = self._resultado("4000").para_json()
        assert dados["conformidade_contratual"] == "nao_demonstrada"
        assert dados["creditos_em_incluidas"] == ["juros_interbancarios"]

    def test_fechamento_conferido_nao_certifica_conformidade(self):
        """A confusão que este campo existe para impedir.

        `fechamento_confere is True` e `conformidade_contratual` são
        perguntas diferentes: a primeira é sobre soma, a segunda sobre o que
        foi somado. Um J pode fechar exato e não ser J.
        """
        resultado = self._resultado("4000")
        assert resultado.fechamento_confere is True
        assert resultado.conformidade_contratual != "aparente"

    def test_credito_em_linha_EXCLUIDA_nao_e_nao_conformidade(self):
        """Exclusão credora é normal: ela é subtraída, não somada em J."""
        fatos = [
            _fato("total", "-6000", piloto._TOTAL),
            _fato("juros_depositos", "-6500", piloto._INCLUIR),
            _fato("provisoes_tecnicas", "500", piloto._EXCLUIR),
        ]
        resultado = piloto.construir_j(fatos, "2024T1", _FONTE_DE_TESTE)
        assert resultado.creditos_em_incluidas == ()
        assert resultado.conformidade_contratual == "aparente"


# ---------------------------------------------------------------------------
# Resolução do G0: variação cambial dentro da linha de juros
# ---------------------------------------------------------------------------


class TestRubricasComCambioEmbutido:
    """As duas rubricas cuja natureza foi apurada na fonte e NÃO é juros.

    O contrato B-DFC-01J exclui câmbio nominalmente. A leitura das notas
    mostrou que a variação cambial do principal de captação em moeda
    estrangeira entra na linha de juros e **não é publicada separada** — nem
    por rodapé da nota, nem por nota de exposição por moeda no intermediário,
    nem pela tabela de hedge, que nomeia outros objetos. Estimar a parcela é
    proibido, então a rubrica é NÃO IDENTIFICADA e J vira intervalo.
    """

    def _rubrica(self, familia, conceito):
        achadas = [r for r in familia if r.conceito == conceito]
        assert len(achadas) == 1, f"{conceito} não é única em {familia!r}"
        return achadas[0]

    def test_interbancario_do_itau_nao_entra_em_J(self):
        rubrica = self._rubrica(
            piloto._RUBRICAS_ITAU, "juros_mercados_interbancarios"
        )
        assert rubrica.tratamento == piloto._NAO_IDENT

    def test_emprestimos_do_bradesco_nao_entra_em_J(self):
        rubrica = self._rubrica(
            piloto._RUBRICAS_BRADESCO, "juros_emprestimos_e_repasses"
        )
        assert rubrica.tratamento == piloto._NAO_IDENT

    def test_o_motivo_cita_a_medicao_e_nao_so_a_conclusao(self):
        """Motivo sem número é opinião. O do Itaú tem o casamento medido."""
        rubrica = self._rubrica(
            piloto._RUBRICAS_ITAU, "juros_mercados_interbancarios"
        )
        for evidencia in ("84.051", "19.429", "21.119", "9,60%", "17b"):
            assert evidencia in rubrica.motivo, f"falta {evidencia}"

    def test_o_motivo_do_bradesco_declara_que_a_evidencia_e_mais_fraca(self):
        """Não afirmar casamento de magnitude onde ele não foi medido."""
        rubrica = self._rubrica(
            piloto._RUBRICAS_BRADESCO, "juros_emprestimos_e_repasses"
        )
        assert "NÃO o casamento de magnitude" in rubrica.motivo

    def test_interfinanceiros_do_bradesco_CONTINUA_em_J(self):
        """A evidência ali é de DERIVAÇÃO, não da rubrica.

        O único crédito da rubrica é um 4T derivado. Condenar a rubrica por
        isso confundiria "esta subtração não vale" com "esta linha não é
        juros" — e a segunda afirmação não foi demonstrada.
        """
        rubrica = self._rubrica(
            piloto._RUBRICAS_BRADESCO, "juros_depositos_interfinanceiros"
        )
        assert rubrica.tratamento == piloto._INCLUIR

    def test_as_rubricas_limpas_dos_tres_emissores_continuam_incluidas(self):
        """A reclassificação não pode vazar para as parcelas em reais."""
        for familia, conceitos in (
            (piloto._RUBRICAS_ITAU,
             ("juros_depositos", "juros_captacao_mercado_aberto",
              "juros_mercados_institucionais")),
            (piloto._RUBRICAS_BRADESCO,
             ("juros_poupanca", "juros_depositos_a_prazo",
              "juros_titulos_emitidos", "juros_dividas_subordinadas")),
        ):
            for conceito in conceitos:
                assert self._rubrica(familia, conceito).tratamento == (
                    piloto._INCLUIR
                ), conceito


class TestDerivacaoComAcumuladoQueEncolhe:
    """Acumulado de doze meses menor que o de nove não é diferença de nada."""

    def _derivar(self, valor_anual, valor_nove_meses):
        fontes = [
            _fonte_sintetica("anual", "2025A"),
            _fonte_sintetica("nove_meses", "2025T3", "2025-11-07"),
        ]
        fatos = [
            _fato_datado("j", valor_anual, "2025A", "anual", "propria",
                         "2026-02-05"),
            _fato_datado("j", valor_nove_meses, "2025M9", "nove_meses",
                         "propria", "2025-11-07"),
        ]
        derivacao = piloto.DerivacaoTrimestre(
            "001023", "2025T4", "anual", "2025A", "nove_meses", "2025M9", "x",
        )
        return piloto.derivar_trimestre(fatos, derivacao)

    def test_derivacao_credora_entre_dois_debitos_e_recusada(self):
        derivados, linhagem = self._derivar("-521525", "-2282154")
        assert derivados == [], "derivou um 4T credor a partir de dois débitos"
        assert linhagem[0]["status"] == "recusada"
        assert "encolheu" in linhagem[0]["motivo"]

    def test_derivacao_normal_continua_funcionando(self):
        derivados, linhagem = self._derivar("-2500000", "-2000000")
        assert len(derivados) == 1
        assert derivados[0].valor == Decimal("-500000")
        assert linhagem[0]["status"] == "calculado"

    def test_o_motivo_da_recusa_nomeia_as_duas_causas_possiveis(self):
        """Não escolher entre reversão e reclassificação sem evidência."""
        _, linhagem = self._derivar("-521525", "-2282154")
        motivo = linhagem[0]["motivo"]
        assert "reversão" in motivo and "reclassificou" in motivo


class TestContraprovasDaRevisaoIndependente:
    """Contraprovas do relatório de revisão de 2026-09-10, achados F8 e F11."""

    def test_F8_a_unidade_do_json_vem_dos_fatos_nao_de_constante(self):
        """Era a constante `milhares_de_reais`, e divergia em 90 de 198.

        O valor numérico sempre esteve na unidade da publicação; a ETIQUETA
        mentia. Quem cruzasse dois emissores por ela erraria por mil.
        """
        fatos = [
            _fato("total", "-300", "total"),
            _fato("a", "-300", "incluir"),
        ]
        for f in fatos:
            object.__setattr__(f, "unidade", "milhoes_de_reais")
        resultado = piloto.construir_j(fatos, "2024T1")
        assert resultado.unidade == "milhoes_de_reais"
        assert resultado.para_json()["unidade"] == "milhoes_de_reais"

    def test_F8_unidades_mistas_falham_em_vez_de_escolher_uma(self):
        """Somar milhares com milhões daria número plausível e errado."""
        a = _fato("a", "-100", "incluir")
        b = _fato("b", "-200", "incluir")
        object.__setattr__(b, "unidade", "milhoes_de_reais")
        with pytest.raises(piloto.ErroExtracao, match="Unidades mistas"):
            piloto.construir_j([a, b], "2024T1")

    def test_F11_identidade_com_operando_derivado_nao_e_independente(self):
        """`M9 + (A − M9) = A` fecha por construção; não é contraprova.

        O relatório publicou «15 de 15 identidades anuais» como certificado de
        mapeamento de colunas. Uma identidade cujo T4 saiu de `A − M9` não
        verifica nada: é álgebra. O artefato agora diz qual é qual.
        """
        def total(valor, periodo, fonte, origem):
            f = _fato("despesa_juros_total", valor, "total", periodo, fonte)
            object.__setattr__(f, "origem_periodo", origem)
            object.__setattr__(f, "cd_cvm_do_fato", "000906")
            return f

        # Mesma fonte para todos, de propósito: assim a identidade chega ao
        # ramo aritmético e FECHA — é justamente aí que chamá-la de
        # verificação seria enganoso.
        fatos = [
            total("-100", "2023T1", "dA", "propria"),
            total("-100", "2023T2", "dA", "propria"),
            total("-100", "2023T3", "dA", "propria"),
            # T4 derivado do próprio anual: torna a identidade tautológica.
            total("-100", "2023T4", "dA", "derivada"),
            total("-400", "2023A", "dA", "propria"),
        ]
        conferencias = piloto.conferir_identidade_trimestral(fatos)
        anual = [
            c for c in conferencias
            if c["identidade"] == "T1+T2+T3+T4 = A"
        ]
        assert anual, "a identidade anual tem de ser avaliada"
        # Ela FECHA — e é exatamente por isso que o campo importa.
        assert all(c["confere"] is True for c in anual)
        # Fechar por construção NÃO é verificação independente.
        assert all(c.get("independente") is False for c in anual)
        assert all(c.get("motivo_nao_independente") for c in anual)

    def test_F11_identidade_toda_original_continua_independente(self):
        """A correção não pode desqualificar a conferência legítima."""
        def total(valor, periodo, fonte):
            f = _fato("despesa_juros_total", valor, "total", periodo, fonte)
            object.__setattr__(f, "origem_periodo", "propria")
            object.__setattr__(f, "cd_cvm_do_fato", "000906")
            return f

        fatos = [
            total("-100", "2023T1", "d1"),
            total("-100", "2023T2", "d2"),
            total("-200", "2023S1", "d2"),
        ]
        conferencias = piloto.conferir_identidade_trimestral(fatos)
        s1 = [c for c in conferencias if c["identidade"] == "T1+T2 = S1"]
        assert s1
        assert all(c["confere"] is True for c in s1)
        assert all(c["independente"] is True for c in s1)


class TestContratoC5Linhagem:
    """Contrato C5 do parecer de 2026-09-11: linhagem de TODOS os operandos.

    F11 fez `conferir_identidade_trimestral` marcar como não independente a
    identidade com PARCELA derivada, e inspecionou `escolhido[:-1]` — que
    exclui justamente o acumulado. Uma soma comparada a um acumulado derivado
    DELA fecha por construção: é a mesma tautologia, na outra ponta.
    """

    def _fato_total(self, periodo, valor, origem="comparativa"):
        fato = _fato("despesa_juros_total", valor, "incluida", periodo,
                     fonte="dA")
        return replace(fato, origem_periodo=origem, cd_cvm_do_fato="019348",
                       disponivel_em="2024-05-02")

    def test_C5_acumulado_derivado_nao_e_conferencia_independente(self):
        """A contraprova exata do parecer."""
        conferencias = piloto.conferir_identidade_trimestral([
            self._fato_total("2024T1", "-100"),
            self._fato_total("2024T2", "-100"),
            self._fato_total("2024S1", "-200", origem="derivada"),
        ])
        assert len(conferencias) == 1
        conferencia = conferencias[0]
        # A aritmética fecha — e é justamente isso que torna o certificado
        # perigoso: fechar por construção não prova mapeamento de coluna.
        assert conferencia["confere"] is True
        assert conferencia["independente"] is False
        assert conferencia["operandos_derivados"] == [
            "S1 (despesa_juros_total)"
        ]
        assert "ACUMULADO" in conferencia["motivo_nao_independente"]

    def test_C5_identidade_toda_original_continua_independente(self):
        """Não-regressão: a guarda não pode condenar o caso legítimo."""
        conferencias = piloto.conferir_identidade_trimestral([
            self._fato_total("2024T1", "-100"),
            self._fato_total("2024T2", "-100"),
            self._fato_total("2024S1", "-200"),
        ])
        assert conferencias[0]["confere"] is True
        assert conferencias[0]["independente"] is True
        assert conferencias[0]["motivo_nao_independente"] is None
        assert conferencias[0]["operandos_derivados"] == []

    def test_C5_parcela_derivada_continua_sendo_pega(self):
        """O comportamento que F11 instalou não pode ter se perdido."""
        conferencias = piloto.conferir_identidade_trimestral([
            self._fato_total("2024T1", "-100", origem="derivada"),
            self._fato_total("2024T2", "-100"),
            self._fato_total("2024S1", "-200"),
        ])
        assert conferencias[0]["independente"] is False
        assert conferencias[0]["operandos_derivados"] == [
            "T1 (despesa_juros_total)"
        ]

    def test_C5_o_resumo_separa_fechamento_de_independencia(self):
        """Contagem de fechamento não é contagem de certificado.

        O resumo contava `confere is True` sem olhar `independente`, e G0
        recebia esse número. Hoje as duas contagens coincidem; o contrato
        existe para que uma identidade futura que feche por construção não
        volte a ser contada como conferida.
        """
        resumo = json.loads(
            (piloto.DIR_EXTENSAO / "resumo.json").read_text(
                encoding="utf-8"
            )
        )
        assert "identidades_conferidas" in resumo
        assert "identidades_conferidas_independentes" in resumo
        assert (
            resumo["identidades_conferidas_independentes"]
            <= resumo["identidades_conferidas"]
        )
        # Toda identidade contada como conferida mas NÃO independente tem de
        # estar nomeada, com o operando culpado.
        for caso in resumo["identidades_que_fecham_por_construcao"]:
            assert caso["operandos_derivados"]
