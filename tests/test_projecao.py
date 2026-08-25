"""Rota da pergunta prospectiva — a RN07 condicional ao modo (src/projecao.py).

O teste mais importante deste arquivo não é o que verifica a recusa: é
`TestFalsoBloqueio`, que roda o detector contra as 55 perguntas congeladas e
exige **zero** disparos. Um roteador que bloqueia demais é tão defeituoso
quanto um que bloqueia de menos, e a etapa 14 já fixou essa disciplina medindo
falso bloqueio nas mesmas perguntas.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.projecao import (
    BANDA_PUBLICAVEL,
    CAMINHO_ESCORES,
    CAMINHO_PANORAMA,
    FaixaDePorte,
    Panorama,
    PanoramaIndisponivelError,
    PrevisaoPorEmissorDesabilitadaError,
    RESOLUCAO_ANALISE,
    TrimestreCorrente,
    carregar_escores,
    carregar_panorama,
    detectar_pergunta_prospectiva,
    recusa_de_ultimo_recurso,
    responder_projecao,
)

RAIZ = Path(__file__).resolve().parent.parent


def _panorama(**ajustes) -> Panorama:
    base = {
        "trimestre_referencia": "3T2025",
        "n_companhias_avaliadas": 413,
        "n_acima_do_dobro_da_base": 80,
        "limiar_dobro_da_base": 0.45,
        "n_no_decil_superior": 41,
        "taxa_base_painel": 0.225,
        "n_observacoes_treino": 21_119,
        "fracao_nao_financeira_treino": 0.96,
        "auc_walk_forward": 0.881,
        "faixas_de_porte": (
            FaixaDePorte("≥ R$ 500 bi", 5e11, 231, 0.061),
            FaixaDePorte("R$ 10–100 bi", 1e10, 5365, 0.218),
            FaixaDePorte("< R$ 10 bi", 0.0, 16760, 0.374),
        ),
    }
    base.update(ajustes)
    return Panorama(**base)


class TestDeteccao:
    """O que conta como pergunta prospectiva sobre resultado."""

    @pytest.mark.parametrize(
        "pergunta",
        [
            "Nos próximos trimestres, o Banco do Brasil terá lucro ou prejuízo?",
            "O BTG vai dar prejuízo no ano que vem?",
            "Qual a probabilidade de prejuízo do Santander?",
            "O Bradesco deve reportar lucro no próximo trimestre?",
            "A Americanas vai continuar no prejuízo?",
            "Qual a projeção de resultado do Itaú?",
            "Nos próximos trimestres o resultado do BB melhora?",
        ],
    )
    def test_detecta_prospectiva(self, pergunta):
        achado = detectar_pergunta_prospectiva(pergunta)
        assert achado is not None, pergunta
        assert achado.ancora_legal == RESOLUCAO_ANALISE

    @pytest.mark.parametrize(
        "pergunta",
        [
            "Qual foi o lucro líquido do Itaú no 1T2026?",
            "O Banco do Brasil já teve prejuízo em algum trimestre?",
            "Quanto o Bradesco lucrou no 4T2025?",
            "Compare o ROE do BTG com o do Santander no 3T2025.",
            "O que o release do 1T2026 diz sobre a carteira de crédito?",
        ],
    )
    def test_nao_detecta_retrospectiva(self, pergunta):
        assert detectar_pergunta_prospectiva(pergunta) is None, pergunta

    def test_texto_vazio_ou_nao_texto(self):
        assert detectar_pergunta_prospectiva("") is None
        assert detectar_pergunta_prospectiva(None) is None  # type: ignore[arg-type]


class TestFalsoBloqueio:
    """Meta 0, como na etapa 14: nenhuma pergunta legítima cai nesta rota."""

    def test_nenhuma_das_congeladas_dispara(self):
        caminho = RAIZ / "conjunto_padrao" / "perguntas.csv"
        pegas = []
        with caminho.open(encoding="utf-8") as arquivo:
            for linha in csv.DictReader(arquivo):
                pergunta = linha.get("pergunta") or ""
                if detectar_pergunta_prospectiva(pergunta):
                    pegas.append(linha.get("id"))
        assert not pegas, (
            "falso bloqueio na rota prospectiva; perguntas legítimas pegas: "
            f"{pegas}"
        )


class TestModoPublico:
    """Sem escore por emissor, e com o que é defensável no lugar."""

    def test_nao_expoe_escore(self):
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            trimestres_painel=("1T2022", "4T2025"),
            n_prejuizos=0,
            panorama=_panorama(),
        )
        assert resposta.expos_escore_por_emissor is False
        assert resposta.escore is None
        assert "escore_por_emissor" not in resposta.blocos

    def test_recusa_cita_a_norma_e_a_rn07(self):
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            panorama=_panorama(),
        )
        assert RESOLUCAO_ANALISE in resposta.texto
        assert "RN07" in resposta.texto
        assert resposta.blocos[0] == "recusa"

    def test_entrega_historico_e_panorama(self):
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            trimestres_painel=("1T2022", "2T2022", "4T2025"),
            n_prejuizos=0,
            panorama=_panorama(),
        )
        assert "historico" in resposta.blocos
        assert "panorama" in resposta.blocos
        assert "001023" in resposta.texto
        assert "nenhum com prejuízo" in resposta.texto

    def test_pergunta_nao_prospectiva_e_erro_de_uso(self):
        with pytest.raises(ValueError, match="não é prospectiva"):
            responder_projecao(
                "Qual foi o lucro do Itaú no 1T2026?",
                denom_social="ITAU",
                cd_cvm="019348",
                panorama=_panorama(),
            )


class TestVazamentoPorEliminacao:
    """O agregado não pode revelar o escore individual por dedução."""

    @pytest.mark.parametrize("acima", [0, 413])
    def test_agregado_extremo_e_suprimido(self, acima):
        """Contagem contra limiar ABSOLUTO pode bater no extremo de verdade.

        A guarda anterior testava `n_no_decil_superior`, que por definição de
        decil nunca é 0 nem o total — a condição era inalcançável e a proteção,
        ilusória. Achado da auditoria de 2026-08-24.
        """
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            panorama=_panorama(n_acima_do_dobro_da_base=acima),
        )
        assert "panorama" not in resposta.blocos, (
            "agregado que bate no extremo permite deduzir por eliminação o "
            "escore de cada membro do recorte"
        )

    def test_agregado_intermediario_e_publicado(self):
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            panorama=_panorama(n_acima_do_dobro_da_base=80),
        )
        assert "panorama" in resposta.blocos

    def test_nao_publica_contagem_de_decil_como_achado(self):
        """`n no decil` é sempre 10% por definição — tautologia, não medição."""
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            panorama=_panorama(),
        )
        assert "decil" not in resposta.texto.lower()
        assert "80" in resposta.texto


class TestModoLocal:
    """Com a chave ligada, o escore aparece — sempre etiquetado."""

    def test_expoe_escore_com_etiqueta_de_fora_de_dominio(self):
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            panorama=_panorama(),
            previsao_por_emissor_habilitada=True,
            escores={"001023": 0.031},
        )
        assert resposta.expos_escore_por_emissor is True
        assert resposta.escore == pytest.approx(0.031)
        assert "3,1%" in resposta.texto
        assert "Fora de domínio" in resposta.texto
        assert "Não é recomendação" in resposta.texto
        assert "USO INTERNO" in resposta.texto

    def test_percentual_em_convencao_pt_br(self):
        """Separador decimal é questão de correção, não de estética.

        Um número financeiro que troca `,` por `.` conforme a máquina é a
        definição de valor plausível e errado — a mesma razão de existir
        `cobertura.formatar_reais`.
        """
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            ativo_total=2.2e12,
            panorama=_panorama(),
            previsao_por_emissor_habilitada=True,
            escores={"001023": 0.031},
        )
        assert "3,1%" in resposta.texto
        assert "6,1%" in resposta.texto  # taxa-base da faixa ≥ R$ 500 bi
        assert "3.1%" not in resposta.texto

    def test_faixa_de_porte_sai_do_ativo_da_companhia(self):
        """O escore precisa vir ao lado da taxa-base da faixa CERTA.

        Em instituição financeira o porte separa 0,6% de 29,6%; comparar com a
        faixa errada inverteria a leitura do número.
        """
        grande = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="GRANDE",
            cd_cvm="001023",
            ativo_total=2.2e12,
            panorama=_panorama(),
            previsao_por_emissor_habilitada=True,
            escores={"001023": 0.031},
        )
        pequeno = responder_projecao(
            "O banco terá prejuízo nos próximos trimestres?",
            denom_social="PEQUENO",
            cd_cvm="001023",
            ativo_total=5.0e9,
            panorama=_panorama(),
            previsao_por_emissor_habilitada=True,
            escores={"001023": 0.031},
        )
        assert "≥ R$ 500 bi" in grande.texto and "6,1%" in grande.texto
        assert "< R$ 10 bi" in pequeno.texto and "37,4%" in pequeno.texto

    def test_regime_publicado_nao_tem_recorte_setorial(self):
        """Retratação de 2026-08-25: a tabela por setor não sobreviveu.

        42 dos 49 eventos do recorte "instituições financeiras" vinham de nove
        entidades que não são banco; limpo, sobram 7 — abaixo do mínimo de 20 —
        e o gradiente some. Reproduzível por
        `scripts/auditar_recorte_is_banco.py`.
        """
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            panorama=_panorama(),
        )
        texto = resposta.texto.lower()
        assert "instituição financeira" not in texto
        assert "instituicao_financeira" not in texto
        assert "todos os setores" in texto
        assert not hasattr(_panorama().faixas_de_porte[0], "instituicao_financeira")

    def test_sem_ativo_nao_inventa_faixa(self):
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            panorama=_panorama(),  # duas faixas financeiras, nenhuma escolhível
            previsao_por_emissor_habilitada=True,
            escores={"001023": 0.031},
        )
        assert "Taxa-base histórica do porte" not in resposta.texto

    def test_troca_a_recusa_por_aviso_de_modo(self):
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            panorama=_panorama(),
            previsao_por_emissor_habilitada=True,
            escores={"001023": 0.031},
        )
        assert resposta.blocos[0] == "aviso_modo_local"
        assert "instância pública recusaria" in resposta.texto

    def test_ligado_sem_escores_falha_fechado(self):
        with pytest.raises(PrevisaoPorEmissorDesabilitadaError):
            responder_projecao(
                "O BB terá prejuízo nos próximos trimestres?",
                denom_social="BCO BRASIL S.A.",
                cd_cvm="001023",
                panorama=_panorama(),
                previsao_por_emissor_habilitada=True,
                escores=None,
            )

    def test_companhia_sem_escore_declara_a_ausencia(self):
        resposta = responder_projecao(
            "O BB terá prejuízo nos próximos trimestres?",
            denom_social="BCO BRASIL S.A.",
            cd_cvm="001023",
            panorama=_panorama(),
            previsao_por_emissor_habilitada=True,
            escores={"999999": 0.5},
        )
        assert resposta.expos_escore_por_emissor is False
        assert "escore_ausente" in resposta.blocos
        assert resposta.blocos[0] == "recusa"


class TestTrimestreCorrente:
    """Escorar o trimestre que ainda não tem rótulo (auditoria 2026-08-25).

    Antes, o panorama publicava como referência um trimestre dois atrás do
    último dado completo, porque o alvo exige T+1 e T+2. O bloco novo escora o
    trimestre corrente — restrito a quem está hoje lucrativo, que é o único
    recorte em que o escore diz algo que a demonstração não diz.
    """

    @staticmethod
    def _corrente(**ajustes) -> TrimestreCorrente:
        base = {
            "trimestre": "1T2026",
            "n_hoje_lucrativas": 286,
            "n_ja_em_prejuizo": 136,
            "n_acima_do_limiar": 2,
            "limiar": 0.426,
        }
        base.update(ajustes)
        return TrimestreCorrente(**base)

    def _responder(self, corrente):
        return responder_projecao(
            "O Itaú terá prejuízo nos próximos trimestres?",
            denom_social="ITAU UNIBANCO HOLDING S.A.",
            cd_cvm="019348",
            trimestres_painel=("1T2025", "2T2025"),
            n_prejuizos=0,
            panorama=_panorama(trimestre_corrente=corrente),
        )

    def test_publica_o_trimestre_corrente_e_o_denominador_descartado(self):
        texto = self._responder(self._corrente(n_acima_do_limiar=40)).texto
        assert "1T2026" in texto
        assert "286" in texto
        assert "136" in texto, "o descartado precisa sair junto do recortado"

    def test_declara_que_nao_ha_auc_para_o_trimestre_corrente(self):
        """Resultado que não aconteceu não tem métrica de acerto. Publicar o
        AUC do walk-forward colado neste bloco insinuaria que tem."""
        texto = self._responder(self._corrente(n_acima_do_limiar=40)).texto
        assert "ainda sem resultado conhecido" in texto
        assert "não tem AUC" in texto or "não tem auc" in texto.lower()

    @pytest.mark.parametrize("n_acima", [0, 2, 284, 286])
    def test_fracao_extrema_suprime_o_bloco(self, n_acima):
        """"2 de 286" entrega a mesma dedução que "0 de 286".

        A guarda original barrava só o 0 e o total literais, e a auditoria de
        2026-08-25 mostrou que **2 de 286** — o valor real do painel — passava:
        publicá-lo ao lado de uma pergunta sobre um emissor entrega, com 99,3%
        de confiança, que aquele emissor está abaixo do limiar. A guarda passou
        a ser sobre FRAÇÃO, não sobre contagem.
        """
        resposta = self._responder(self._corrente(n_acima_do_limiar=n_acima))
        assert "trimestre_corrente" not in resposta.blocos
        assert "1T2026" not in resposta.texto

    def test_fracao_dentro_da_banda_publica(self):
        """Contraprova: a guarda não pode ser sempre-suprimir."""
        resposta = self._responder(self._corrente(n_acima_do_limiar=40))
        assert "trimestre_corrente" in resposta.blocos

    def test_a_banda_e_a_mesma_que_o_codigo_declara(self):
        piso, teto = BANDA_PUBLICAVEL
        assert 0.0 < piso < teto < 1.0
        n = 286
        assert not (piso <= 2 / n <= teto), "o valor real do painel deve barrar"

    def test_recorte_pequeno_suprime_o_bloco(self):
        resposta = self._responder(
            self._corrente(n_hoje_lucrativas=12, n_acima_do_limiar=2)
        )
        assert "trimestre_corrente" not in resposta.blocos

    def test_ausente_nao_derruba_a_resposta(self):
        """Painel curto demais para alcançar trimestre sem rótulo: o bloco some
        e o resto da resposta continua."""
        resposta = self._responder(None)
        assert "trimestre_corrente" not in resposta.blocos
        assert resposta.texto.strip()

    def test_o_escore_por_emissor_cita_o_trimestre_escorado(self):
        """O escore passou a ser do trimestre corrente; citar o do panorama
        mandaria o analista conferir o trimestre errado."""
        panorama = _panorama(trimestre_corrente=self._corrente())
        assert panorama.trimestre_dos_escores == "1T2026"
        assert panorama.trimestre_referencia == "3T2025"
        resposta = responder_projecao(
            "Qual a probabilidade de prejuízo do Itaú?",
            denom_social="ITAU UNIBANCO HOLDING S.A.",
            cd_cvm="019348",
            trimestres_painel=("1T2025", "2T2025"),
            n_prejuizos=0,
            panorama=panorama,
            previsao_por_emissor_habilitada=True,
            escores={"019348": 0.07},
        )
        assert "1T2026" in resposta.texto

    def test_sem_trimestre_corrente_cai_no_de_referencia(self):
        assert _panorama().trimestre_dos_escores == "3T2025"


class TestGuardaProfunda:
    """A RN07 não pode morar num ramo só (auditoria de 2026-08-25).

    O defeito: `responder_prospectiva_se_couber` devolvia ``None`` quando o
    panorama ou o painel faltavam, e ``None`` significa "siga o fluxo normal" —
    ou seja, a pergunta prospectiva sobre emissor nomeado ia para o LLM. Uma
    camada acessória ausente virava permissão. Aqui o teto vira piso: artefato
    ausente degrada a RIQUEZA da resposta, nunca a fronteira.
    """

    def test_recusa_de_ultimo_recurso_nao_precisa_de_artefato(self):
        achado = detectar_pergunta_prospectiva(
            "O banco XYZ terá prejuízo no próximo trimestre?"
        )
        assert achado is not None
        resposta = recusa_de_ultimo_recurso(achado, motivo="painel indisponível")
        assert resposta.expos_escore_por_emissor is False
        assert resposta.escore is None
        assert resposta.blocos == ("recusa",)
        assert resposta.metadados["degradado"] is True
        assert RESOLUCAO_ANALISE in resposta.texto
        assert "painel indisponível" in resposta.texto

    def test_recusa_degradada_nao_inventa_numero(self):
        """Trocar violação de RN07 por violação de RN02 não seria conserto.

        Sem os artefatos não há número conferível. A recusa pobre é o
        comportamento certo — qualquer dígito aqui viria de memória
        paramétrica ou de constante escrita à mão.
        """
        import re

        achado = detectar_pergunta_prospectiva("Qual a probabilidade de prejuízo?")
        texto = recusa_de_ultimo_recurso(achado, motivo="sem painel").texto
        # As âncoras legais carregam número ("20/2021"); nada além delas pode.
        sem_ancoras = texto.replace(RESOLUCAO_ANALISE, "")
        assert not re.search(r"\d+[,.]\d|\d+%", sem_ancoras), sem_ancoras

    def test_o_ramo_do_streamlit_nao_devolve_none_sem_recursos(self):
        """Contraprova no código: o `return None` do caminho sem recursos saiu."""
        fonte = (RAIZ / "app_streamlit.py").read_text(encoding="utf-8")
        trecho = fonte.split("def responder_prospectiva_se_couber", 1)[1]
        trecho = trecho.split("\ndef ", 1)[0]
        assert "recusa_de_ultimo_recurso" in trecho, (
            "recursos ausentes precisam recusar, não cair no fluxo normal"
        )
        depois_do_carregar = trecho.split("recursos = carregar_rota_prospectiva()", 1)[1]
        cabeca = depois_do_carregar.split("indice = recursos", 1)[0]
        assert "return None" not in cabeca, (
            "o fall-through para o LLM voltou: pergunta prospectiva sem "
            "panorama seria respondida pelo provedor"
        )

    def test_a_camada_de_agentes_tambem_verifica(self):
        """`responder_com_guardrails` era o único portão do produto sem a RN07.

        Ela se declara "o caminho interativo inteiro" (§6). Enquanto a camada
        de agentes não está ligada à interface o buraco é teórico; a etapa 11
        o tornaria real, e a correção não pode depender de alguém lembrar.
        Achado da auditoria de 2026-08-25 — a onda anterior fechou um dos dois
        portões e reescreveu a memória como se tivesse fechado os dois.
        """
        fonte = (RAIZ / "src" / "agentes.py").read_text(encoding="utf-8")
        corpo = fonte.split("def responder_com_guardrails", 1)[1]
        corpo = corpo.split("\ndef ", 1)[0]
        assert "detectar_pergunta_prospectiva" in corpo
        assert corpo.index("detectar_pergunta_prospectiva") < corpo.index(
            "executar("
        ), "recusar depois de chamar o braço não é recusar"

    def test_o_portao_do_provedor_tambem_verifica(self):
        """Portão duplo, como já se faz com a RN05 em `responder_pergunta_livre`.

        A rota depende do nome resolver no índice de cobertura. Companhia
        nomeada que não esteja no índice escaparia da primeira guarda — esta
        segunda, na função que fala com o provedor, é a que não escapa.
        """
        fonte = (RAIZ / "app_streamlit.py").read_text(encoding="utf-8")
        corpo = fonte.split("def responder_pergunta_livre", 1)[1].split("\ndef ", 1)[0]
        assert "detectar_pergunta_prospectiva" in corpo
        posicao_guarda = corpo.index("detectar_pergunta_prospectiva")
        for marcador in ("gerar_resposta(", "estimar_custo_maximo", "recuperar("):
            assert posicao_guarda < corpo.index(marcador), (
                f"a guarda da RN07 precisa vir ANTES de `{marcador}` — recusar "
                "depois de gastar não é recusar"
            )


class TestAchadosDaAuditoria:
    """Os três defeitos encontrados em 2026-08-24, travados para não voltarem."""

    def test_contrato_do_historico_do_streamlit(self):
        """A rota precisa devolver a chave que o laço de renderização lê.

        O primeiro corte devolvia `resposta` e o app anexava `**item` ao
        histórico, que é lido por `msg["conteudo"]` — `KeyError` no rerun e
        página de exceção. A recusa da RN07 nunca chegava à tela.
        """
        import ast

        fonte = (RAIZ / "app_streamlit.py").read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        chaves_lidas = {
            no.slice.value
            for no in ast.walk(arvore)
            if isinstance(no, ast.Subscript)
            and isinstance(no.slice, ast.Constant)
            and isinstance(no.slice.value, str)
            and isinstance(no.value, ast.Name)
            and no.value.id == "msg"
        }
        assert "conteudo" in chaves_lidas, "o laço mudou de chave; ajuste a rota"
        assert '"conteudo": item_projecao["resposta"]' in fonte, (
            "a rota prospectiva precisa preencher `conteudo` ao anexar no "
            "histórico, senão o rerun estoura KeyError"
        )

    def test_janela_de_trimestres_nao_e_ordenada_como_texto(self):
        """`sorted()` puro poria 1T2026 antes de 2T2025 e publicaria janela errada."""
        from src.normalizacao import ordinal_trimestre

        reais = ["1T2025", "1T2026", "2T2025", "2T2026", "3T2025", "4T2025"]
        certo = tuple(sorted(reais, key=ordinal_trimestre))
        assert certo[0] == "1T2025" and certo[-1] == "2T2026"
        assert tuple(sorted(reais))[-1] == "4T2025", "premissa do defeito"

        resposta = responder_projecao(
            "O Itaú terá prejuízo nos próximos trimestres?",
            denom_social="ITAU UNIBANCO HOLDING S.A.",
            cd_cvm="019348",
            trimestres_painel=certo,
            n_prejuizos=1,
            panorama=_panorama(),
        )
        assert "(1T2025–2T2026)" in resposta.texto

    def test_prejuizo_derivado_sai_marcado_rn10(self):
        """4T é derivado (420 de 435 linhas no painel) e não pode virar arquivado."""
        resposta = responder_projecao(
            "A companhia terá prejuízo nos próximos trimestres?",
            denom_social="COMPANHIA X",
            cd_cvm="123456",
            trimestres_painel=("1T2025", "2T2025", "3T2025", "4T2025"),
            n_prejuizos=0,
            n_prejuizos_derivados=1,
            panorama=_panorama(),
        )
        assert "derivado" in resposta.texto
        assert "RN10" in resposta.texto
        assert "arquivado" in resposta.texto

    def test_sem_derivados_o_texto_nao_polui(self):
        resposta = responder_projecao(
            "A companhia terá prejuízo nos próximos trimestres?",
            denom_social="COMPANHIA X",
            cd_cvm="123456",
            trimestres_painel=("1T2025", "2T2025"),
            n_prejuizos=2,
            n_prejuizos_derivados=0,
            panorama=_panorama(),
        )
        assert "RN10" not in resposta.texto
        assert "2 com prejuízo em trimestre arquivado" in resposta.texto


class TestArtefatos:
    """Carga do panorama falha fechada (RNF03), nunca degrada em silêncio."""

    def test_panorama_ausente_levanta(self, tmp_path):
        with pytest.raises(PanoramaIndisponivelError, match="ausente"):
            carregar_panorama(tmp_path / "nao_existe.json")

    def test_panorama_malformado_levanta(self, tmp_path):
        caminho = tmp_path / "panorama.json"
        caminho.write_text('{"trimestre_referencia":', encoding="utf-8")
        with pytest.raises(PanoramaIndisponivelError, match="malformado"):
            carregar_panorama(caminho)

    def test_escores_ausentes_levantam(self, tmp_path):
        with pytest.raises(PanoramaIndisponivelError, match="ausentes"):
            carregar_escores(tmp_path / "nao_existe.json")

    def test_ida_e_volta_do_panorama(self, tmp_path):
        caminho = tmp_path / "panorama.json"
        original = _panorama()
        caminho.write_text(
            json.dumps(
                {
                    "trimestre_referencia": original.trimestre_referencia,
                    "n_companhias_avaliadas": original.n_companhias_avaliadas,
                    "n_acima_do_dobro_da_base": original.n_acima_do_dobro_da_base,
                    "limiar_dobro_da_base": original.limiar_dobro_da_base,
                    "n_no_decil_superior": original.n_no_decil_superior,
                    "taxa_base_painel": original.taxa_base_painel,
                    "n_observacoes_treino": original.n_observacoes_treino,
                    "fracao_nao_financeira_treino": (
                        original.fracao_nao_financeira_treino
                    ),
                    "auc_walk_forward": original.auc_walk_forward,
                    "alvo": original.alvo,
                    "faixas_de_porte": [
                        {
                            "rotulo": faixa.rotulo,
                            "limite_inferior_reais": faixa.limite_inferior_reais,
                            "n_observacoes": faixa.n_observacoes,
                            "taxa_prejuizo": faixa.taxa_prejuizo,
                        }
                        for faixa in original.faixas_de_porte
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        lido = carregar_panorama(caminho)
        assert lido.trimestre_referencia == "3T2025"
        assert lido.fracao_acima_do_dobro == pytest.approx(80 / 413)
        assert len(lido.faixas_de_porte) == 3


class TestEscoresForaDoGit:
    """A RN07 em disco: o arquivo por emissor não pode ser versionado."""

    def test_gitignore_exclui_os_escores(self):
        ignorado = (RAIZ / ".gitignore").read_text(encoding="utf-8")
        assert str(CAMINHO_ESCORES) in ignorado, (
            "escores por companhia precisam ficar fora do Git — é o dado que a "
            "instância pública não pode ter"
        )

    def test_panorama_agregado_continua_versionavel(self):
        # Contraprova: a exceção do .gitignore não pode ter levado junto o
        # artefato agregado, que o deploy público PRECISA ter.
        ignorado = (RAIZ / ".gitignore").read_text(encoding="utf-8")
        assert str(CAMINHO_PANORAMA) not in ignorado
