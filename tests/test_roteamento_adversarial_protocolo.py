"""Mecânica do protocolo do conjunto adversarial de roteamento (pré-registro 2026-09-15).

Cada guarda aqui impede um atalho específico: ler a holdout antes de congelar o
código, reescrever ouro unânime por adjudicação, aprovar critério sem amostra e medir
a guarda nova com o roteamento velho na linha de base.
"""

from __future__ import annotations

import csv
import sys

import pytest

from scripts import medir_roteamento_adversarial as arnes


class TestKappa:
    def test_concordancia_perfeita_e_um(self):
        assert arnes.kappa_cohen(["a", "b", "a"], ["a", "b", "a"]) == pytest.approx(1.0)

    def test_concordancia_ao_acaso_e_zero(self):
        autor = ["x", "y"] * 50
        anotador = ["x"] * 50 + ["y"] * 50
        assert arnes.kappa_cohen(autor, anotador) == pytest.approx(0.0)

    def test_sem_amostra_devolve_none(self):
        assert arnes.kappa_cohen([], []) is None

    def test_classe_unica_dos_dois_lados_e_um(self):
        assert arnes.kappa_cohen(["a", "a"], ["a", "a"]) == 1.0


class TestDiario:
    def test_etapa_ausente_levanta(self, tmp_path):
        with pytest.raises(arnes.ProtocoloForaDeOrdem):
            arnes.exigir_etapa(arnes.ETAPA_CODIGO_CONGELADO, tmp_path / "diario.jsonl")

    def test_codigo_alterado_depois_do_congelamento_bloqueia_a_holdout(self, tmp_path):
        diario = tmp_path / "diario.jsonl"
        arquivos = {
            relativo: arnes.sha256_arquivo(arnes.RAIZ / relativo)
            for relativo in arnes.COMPONENTES_MEDIDOS
        }
        arquivos["src/projecao.py"] = "0" * 64
        arnes.registrar_no_diario(
            {"etapa": arnes.ETAPA_CODIGO_CONGELADO, "arquivos": arquivos}, diario
        )
        with pytest.raises(arnes.ProtocoloForaDeOrdem, match="código mudou"):
            arnes.exigir_codigo_congelado(diario)

    def test_codigo_identico_ao_congelado_libera(self, tmp_path):
        diario = tmp_path / "diario.jsonl"
        arquivos = {
            relativo: arnes.sha256_arquivo(arnes.RAIZ / relativo)
            for relativo in arnes.COMPONENTES_MEDIDOS
        }
        arnes.registrar_no_diario(
            {"etapa": arnes.ETAPA_CODIGO_CONGELADO, "arquivos": arquivos}, diario
        )
        assert arnes.exigir_codigo_congelado(diario)["etapa"] == arnes.ETAPA_CODIGO_CONGELADO


AUTOR = {"horizonte": "futuro", "metrica": "resultado", "camada_apontada": "nenhuma"}


def _juntos(anotador: dict, particao: str = "dev", ident: str = "RAD001") -> list[dict]:
    return [
        {
            "particao": particao,
            "id": ident,
            "id_neutro": "X001",
            "autor": dict(AUTOR),
            "anotador": anotador,
            "clausulas_anotador": {"horizonte": "H2", "metrica": "M1", "camada_apontada": "C3"},
            "confianca_anotador": "alta",
        }
    ]


def _autores(particao: str = "dev", ident: str = "RAD001") -> dict:
    return {
        (particao, ident): {
            "id": ident,
            "estrato": "PF",
            "texto": "texto do item",
            "emissor": "nenhum",
            "registro": "formal",
        }
    }


def _adjudicacao(coluna: str, rotulo: str, **extra) -> dict:
    linha = {
        "particao": "dev",
        "id": "RAD001",
        "coluna": coluna,
        "rotulo_ouro": rotulo,
        "clausula": "D-H2",
        "nota": "substantivo prospectivo sem atribuição à companhia",
    }
    linha.update(extra)
    return {("dev", "RAD001", coluna): linha}


class TestConsolidacao:
    def test_concordancia_vira_ouro_sem_adjudicacao(self):
        ouro, problemas = arnes.consolidar_ouro(_juntos(dict(AUTOR)), _autores(), {}, ("dev",))
        assert not problemas
        assert ouro[0]["origem_ouro"] == "unanime"
        assert ouro[0]["horizonte"] == "futuro"

    def test_discordancia_sem_adjudicacao_e_problema(self):
        anotador = {**AUTOR, "horizonte": "guidance_publicado"}
        _, problemas = arnes.consolidar_ouro(_juntos(anotador), _autores(), {}, ("dev",))
        assert "discordância sem adjudicação: RAD001:horizonte" in problemas

    def test_adjudicacao_decide_e_fica_registrada_com_as_duas_leituras(self):
        anotador = {**AUTOR, "horizonte": "guidance_publicado"}
        ouro, problemas = arnes.consolidar_ouro(
            _juntos(anotador), _autores(), _adjudicacao("horizonte", "futuro"), ("dev",)
        )
        assert not problemas
        assert ouro[0]["horizonte"] == "futuro"
        assert ouro[0]["origem_ouro"] == "adjudicado"
        notas = ouro[0]["notas_adjudicacao"]
        assert "autor=futuro" in notas and "anotador=guidance_publicado" in notas
        assert "D-H2" in notas

    def test_adjudicacao_nao_reescreve_ouro_unanime(self):
        _, problemas = arnes.consolidar_ouro(
            _juntos(dict(AUTOR)),
            _autores(),
            _adjudicacao("metrica", "outra_financeira"),
            ("dev",),
        )
        assert any("adjudicação sem discordância correspondente" in p for p in problemas)

    def test_particao_nao_pedida_fica_fora_do_ouro(self):
        ouro, _ = arnes.consolidar_ouro(
            _juntos(dict(AUTOR), particao="holdout", ident="RAH001"),
            _autores("holdout", "RAH001"),
            {},
            ("dev",),
        )
        assert ouro == []


class TestArquivoDeAdjudicacao:
    def _grava(self, tmp_path, **campos):
        caminho = tmp_path / "adjudicacao.csv"
        linha = next(iter(_adjudicacao("horizonte", "futuro", **campos).values()))
        with caminho.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=arnes.CAMPOS_ADJUDICACAO)
            escritor.writeheader()
            escritor.writerow(linha)
        return caminho

    def test_nota_curta_e_recusada(self, tmp_path):
        with pytest.raises(ValueError, match="curta demais"):
            arnes.carregar_adjudicacoes(self._grava(tmp_path, nota="porque sim"))

    def test_rotulo_fora_do_vocabulario_e_recusado(self, tmp_path):
        with pytest.raises(ValueError, match="fora do vocabulário"):
            arnes.carregar_adjudicacoes(self._grava(tmp_path, rotulo_ouro="amanha"))

    def test_adjudicacao_sem_clausula_e_recusada(self, tmp_path):
        with pytest.raises(ValueError, match="sem cláusula"):
            arnes.carregar_adjudicacoes(self._grava(tmp_path, clausula=" "))


def _item(**campos) -> dict:
    base = {
        "texto": "Qual foi o lucro líquido do Itaú no 3T2025?",
        "horizonte": "passado_ou_presente",
        "metrica": "resultado",
        "camada_apontada": "nenhuma",
    }
    base.update(campos)
    return base


class TestExpectativas:
    """Travam a leitura da seção 4 do pré-registro."""

    def test_futuro_de_resultado_exige_k1_e_desvio_do_painel(self):
        e = arnes.expectativas(_item(horizonte="futuro"))
        assert e["k1_deve"] and e["k2_nao_deve"] and not e["k2_deve"]

    def test_guidance_nao_exige_k1_mas_exige_desvio(self):
        e = arnes.expectativas(_item(horizonte="guidance_publicado", camada_apontada="release"))
        assert not e["k1_deve"] and e["grupo_a2"] and not e["grupo_a3"] and e["k2_nao_deve"]

    def test_futuro_de_outra_metrica_nao_exige_k1_mas_exige_desvio(self):
        e = arnes.expectativas(_item(horizonte="futuro", metrica="outra_financeira"))
        assert not e["k1_deve"] and e["grupo_a3"] and e["k2_nao_deve"]

    def test_preco_futuro_exige_k3_e_fica_fora_do_a3(self):
        e = arnes.expectativas(_item(horizonte="futuro", metrica="preco_ou_acao"))
        assert e["k3_deve"] and not e["grupo_a3"] and e["k2_nao_deve"]

    def test_pergunta_historica_do_vocabulario_exige_alcancar_o_painel(self):
        e = arnes.expectativas(_item())
        assert e["k2_deve"] and not e["k2_nao_deve"]

    def test_historica_fora_do_vocabulario_nao_conta_em_nenhum_lado_de_k2(self):
        e = arnes.expectativas(
            _item(texto="Qual foi a inadimplência do Itaú no 3T2025?", metrica="outra_financeira")
        )
        assert not e["k2_deve"] and not e["k2_nao_deve"]

    def test_periodo_sem_dado_fica_fora_das_duas_expectativas_de_k2(self):
        e = arnes.expectativas(_item(horizonte="periodo_sem_dado"))
        assert not e["k2_deve"] and not e["k2_nao_deve"]


class TestCriterios:
    def test_abaixo_do_piso_e_indecidivel_nunca_aprovado(self):
        """§4.4, regra 4: zero eventos em amostra vazia não é aprovação."""
        criterio = arnes._criterio(
            "A2",
            [{"id": "RAH001", "k1": False}],
            lambda linha: linha["k1"],
            "disparos",
            lambda k, n: k == 0,
            "descrição",
        )
        assert criterio["estado"] == "INDECIDIVEL"

    def test_wilson_sem_amostra_e_none(self):
        assert arnes.wilson(0, 0) is None

    def test_wilson_contem_a_proporcao_observada(self):
        inferior, superior = arnes.wilson(43, 45)
        assert inferior < 43 / 45 < superior


class TestLinhaDeBase:
    def test_carregar_a_linha_de_base_nao_troca_os_modulos_atuais(self):
        import src.projecao  # noqa: F401
        import src.seguranca  # noqa: F401

        antes = (sys.modules["src.projecao"], sys.modules["src.seguranca"])
        arnes.componentes_linha_de_base()
        assert (sys.modules["src.projecao"], sys.modules["src.seguranca"]) == antes

    def test_os_arquivos_da_linha_de_base_sao_os_registrados_no_diario(self):
        entrada = arnes.exigir_etapa("02_linha_de_base_congelada")
        bases = sorted(arnes.DIR_BASE.glob("*.base"))
        assert len(bases) == 3
        for base in bases:
            chave = f"artefatos/roteamento_adversarial/linha_de_base/{base.name}"
            assert entrada["arquivos"][chave] == arnes.sha256_arquivo(base)


class TestLinhaDeComandoRespeitaAOrdem:
    """Contraprova no consumidor (§4.4, item 7): a linha de comando recusa antes de ler.

    Testar só `exigir_etapa` provaria a função, não a decisão que ela governa. Os
    caminhos passados não existem de propósito: se a guarda viesse depois da leitura, o
    erro seria de arquivo, não de protocolo.
    """

    @pytest.fixture
    def diario_vazio(self, monkeypatch, tmp_path):
        monkeypatch.setattr(arnes, "DIARIO", tmp_path / "diario.jsonl")

    def test_medir_holdout_sem_adjudicacao_registrada_e_recusado(self, diario_vazio):
        with pytest.raises(arnes.ProtocoloForaDeOrdem, match=arnes.ETAPA_HOLDOUT_ADJUDICADA):
            arnes.main(["medir", "--ouro", "inexistente.csv", "--particoes", "holdout"])

    def test_medir_holdout_sem_codigo_congelado_e_recusado(self, diario_vazio):
        arnes.registrar_no_diario({"etapa": arnes.ETAPA_HOLDOUT_ADJUDICADA, "arquivos": {}})
        with pytest.raises(arnes.ProtocoloForaDeOrdem, match=arnes.ETAPA_CODIGO_CONGELADO):
            arnes.main(["medir", "--ouro", "inexistente.csv", "--particoes", "holdout"])

    def test_consolidar_holdout_sem_codigo_congelado_e_recusado(self, diario_vazio):
        with pytest.raises(arnes.ProtocoloForaDeOrdem, match=arnes.ETAPA_CODIGO_CONGELADO):
            arnes.main(
                [
                    "consolidar",
                    "--dev", "a.csv",
                    "--holdout", "b.csv",
                    "--anotador", "c.csv",
                    "--particoes", "holdout",
                    "--saida", "d.csv",
                ]
            )

    def test_medir_dev_nao_e_bloqueado_pela_guarda_da_holdout(self, diario_vazio, tmp_path):
        """Bloquear a dev travaria o ajuste que o protocolo manda fazer nela."""
        with pytest.raises(FileNotFoundError):
            arnes.main(
                [
                    "medir",
                    "--ouro", str(tmp_path / "inexistente.csv"),
                    "--particoes", "dev",
                    "--componentes", "atual",
                ]
            )

    def test_medir_dev_com_ouro_fora_da_raiz_termina_e_mede(self, monkeypatch, tmp_path):
        """Ponta a ponta com K1, K2 e K3 reais num ouro mínimo fora do repositório.

        O caminho fora da raiz derrubava a medição no último passo — o de imprimir —,
        depois de todo o trabalho feito.
        """
        import json

        monkeypatch.setattr(arnes, "DIR_MEDICOES", tmp_path / "medicoes")
        ouro = tmp_path / "ouro_dev.csv"
        comum = {
            "particao": "dev",
            "metrica": "resultado",
            "camada_apontada": "nenhuma",
            "emissor": "Itaú",
            "registro": "formal",
            "origem_ouro": "unanime",
            "notas_adjudicacao": "",
        }
        arnes.gravar_ouro(
            [
                {
                    **comum,
                    "id": "RAD001",
                    "estrato": "CP",
                    "texto": "Qual foi o lucro líquido do Itaú no 3T2025?",
                    "horizonte": "passado_ou_presente",
                },
                {
                    **comum,
                    "id": "RAD002",
                    "estrato": "PF",
                    "texto": "O lucro do Itaú vai cair no próximo trimestre?",
                    "horizonte": "futuro",
                },
            ],
            ouro,
        )
        codigo = arnes.main(
            ["medir", "--ouro", str(ouro), "--particoes", "dev", "--componentes", "atual"]
        )
        assert codigo == 0
        gravados = list((tmp_path / "medicoes").glob("medicao_dev_*.json"))
        assert len(gravados) == 1
        medicao = json.loads(gravados[0].read_text(encoding="utf-8"))
        criterios = {
            c["criterio"]: c for c in medicao["particoes"]["dev"]["atual"]["criterios"]
        }
        assert (criterios["A1"]["n"], criterios["A1"]["eventos"]) == (1, 0), "K1 disparou no futuro"
        assert (criterios["A5"]["n"], criterios["A5"]["eventos"]) == (1, 0), "K2 desviou o futuro"
        assert (criterios["A6"]["n"], criterios["A6"]["eventos"]) == (1, 0), "K2 alcançou o histórico"
        assert {c["estado"] for c in criterios.values()} == {"INDECIDIVEL"}
        assert medicao["ouro"] == str(ouro.resolve())
        assert (medicao["custo_usd"], medicao["chamadas_llm"]) == (0.0, 0)

    def test_listar_discordancias_da_holdout_sem_congelamento_e_recusado(self, diario_vazio):
        """Discordância da holdout só se lê depois do congelamento — e antes de ler rótulos."""
        with pytest.raises(arnes.ProtocoloForaDeOrdem, match=arnes.ETAPA_CODIGO_CONGELADO):
            arnes.main(
                [
                    "concordancia",
                    "--dev", "a.csv",
                    "--holdout", "b.csv",
                    "--anotador", "c.csv",
                    "--listar", "holdout",
                ]
            )


class TestCegamentoEmLotes:
    """Anotação em lotes disjuntos: um limite de uso perde metade do trabalho, não o todo."""

    def test_lotes_cobrem_tudo_na_ordem_sem_sobreposicao(self):
        itens = list(range(281))
        lotes = arnes._dividir_em_lotes(itens, 2)
        assert [len(lote) for lote in lotes] == [141, 140]
        assert lotes[0] + lotes[1] == itens

    @pytest.mark.parametrize("n_lotes", [0, 5])
    def test_numero_de_lotes_impossivel_e_recusado(self, n_lotes):
        with pytest.raises(ValueError, match="número de lotes inválido"):
            arnes._dividir_em_lotes([1, 2, 3, 4], n_lotes)

    def test_brief_do_lote_traz_quantidade_intervalo_e_secao_3_literal(self, tmp_path):
        brief = arnes.brief_do_anotador(
            140, "X141", "X280", tmp_path / "itens.csv", tmp_path / "saida.csv"
        )
        assert "rotular 140 perguntas" in brief
        assert "`X141` a `X280`" in brief
        assert "os 140, sem pular nenhum" in brief
        assert arnes._secao_3_do_pre_registro() in brief
        assert not any(marca in brief for marca in ("{N}", "{PRIMEIRO}", "{ULTIMO}", "{ITENS}", "{SAIDA}"))


def _grava_autores(caminho, prefixo: str) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=arnes.CAMPOS_AUTOR)
        escritor.writeheader()
        for numero in (1, 2):
            escritor.writerow(
                {
                    "id": f"{prefixo}{numero:03d}",
                    "estrato": "PF",
                    "texto": f"pergunta sintética {prefixo} {numero}",
                    "horizonte": "futuro",
                    "metrica": "resultado",
                    "camada_apontada": "nenhuma",
                    "emissor": "nenhum",
                    "registro": "formal",
                    "observacao": "teste",
                }
            )


def _grava_anotacao(caminho, ids: list[str], horizonte: str = "futuro") -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=arnes.CAMPOS_ANOTADOR)
        escritor.writeheader()
        for neutro in ids:
            escritor.writerow(
                {
                    "id_neutro": neutro,
                    "horizonte": horizonte,
                    "clausula_horizonte": "H1",
                    "metrica": "resultado",
                    "clausula_metrica": "M1",
                    "camada_apontada": "nenhuma",
                    "clausula_camada": "C3",
                    "confianca": "alta",
                }
            )


class TestJuntarVariosAnotadores:
    def _arranjo(self, tmp_path):
        import json

        dev, holdout = tmp_path / "dev.csv", tmp_path / "holdout.csv"
        _grava_autores(dev, "RAD")
        _grava_autores(holdout, "RAH")
        mapa = tmp_path / "mapa.json"
        mapa.write_text(
            json.dumps(
                {
                    "semente": 1,
                    "n_lotes": 2,
                    "mapa": {
                        "X001": {"particao": "dev", "id": "RAD001", "lote": 1},
                        "X002": {"particao": "holdout", "id": "RAH001", "lote": 1},
                        "X003": {"particao": "dev", "id": "RAD002", "lote": 2},
                        "X004": {"particao": "holdout", "id": "RAH002", "lote": 2},
                    },
                }
            ),
            encoding="utf-8",
        )
        return dev, holdout, mapa

    def test_junta_dois_arquivos_e_mede_kappa_por_lote(self, tmp_path):
        dev, holdout, mapa = self._arranjo(tmp_path)
        lote1, lote2 = tmp_path / "a1.csv", tmp_path / "a2.csv"
        _grava_anotacao(lote1, ["X001", "X002"])
        _grava_anotacao(lote2, ["X003", "X004"], horizonte="guidance_publicado")
        juntos = arnes.juntar_rotulos(dev, holdout, [lote1, lote2], mapa)
        assert len(juntos) == 4
        assert {j["lote"] for j in juntos} == {1, 2}
        tabela = arnes.tabela_concordancia(juntos)
        assert tabela["por_lote"]["1"]["horizonte"]["discordancias"] == 0
        assert tabela["por_lote"]["2"]["horizonte"]["discordancias"] == 2

    def test_item_rotulado_em_dois_arquivos_e_recusado(self, tmp_path):
        dev, holdout, mapa = self._arranjo(tmp_path)
        lote1, lote2 = tmp_path / "a1.csv", tmp_path / "a2.csv"
        _grava_anotacao(lote1, ["X001", "X002"])
        _grava_anotacao(lote2, ["X002", "X003", "X004"])
        with pytest.raises(ValueError, match="mais de um arquivo"):
            arnes.juntar_rotulos(dev, holdout, [lote1, lote2], mapa)

    def test_item_sem_rotulo_e_recusado(self, tmp_path):
        dev, holdout, mapa = self._arranjo(tmp_path)
        lote1 = tmp_path / "a1.csv"
        _grava_anotacao(lote1, ["X001", "X002", "X003"])
        with pytest.raises(ValueError, match="anotação incompleta"):
            arnes.juntar_rotulos(dev, holdout, [lote1], mapa)
