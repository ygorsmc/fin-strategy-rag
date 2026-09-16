"""Contraprovas da aquisição e leitura de formulários da CVM.

Contrato: `resultados/contratos_lote_b_rank03b_2026-09-16.md` (V1, X1, N1).
Tudo em fixtures sintéticas: nenhum caso depende de rede.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
from datetime import date

import pytest

from scripts import fonte_rad_cvm as rad


# --- fixtures ------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _sem_rede(monkeypatch):
    """Nenhum caso deste arquivo pode executar processo real (curl) nem tocar a rede.

    Existe porque um caso chegou a chamar o `curl` de verdade: o dublê não
    alcançava um argumento padrão resolvido na definição da função.
    """
    def proibido(*_, **__):
        raise AssertionError("teste tentou executar processo real")
    monkeypatch.setattr(rad.subprocess, "run", proibido)

def _pdf_com_texto(linhas: list[str]) -> bytes:
    """PDF mínimo e válido com uma página de texto — sem biblioteca externa."""
    conteudo = "BT /F1 10 Tf 20 800 Td 12 TL " + " ".join(
        f"({t}) Tj T*" for t in linhas
    ) + " ET"
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(conteudo)} >>\nstream\n{conteudo}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    saida = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for o in offsets:
        saida += f"{o:010d} 00000 n \n".encode()
    saida += (f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
              f"startxref\n{xref}\n%%EOF\n").encode()
    return saida


def _periodos_xml(periodos):
    corpo = "".join(
        f"<PeriodoDemonstracaoFinanceira><NumeroIdentificacaoPeriodo>{n}"
        f"</NumeroIdentificacaoPeriodo><DataInicioPeriodo>{ini}T00:00:00"
        f"</DataInicioPeriodo><DataFimPeriodo>{fim}T00:00:00</DataFimPeriodo>"
        f"</PeriodoDemonstracaoFinanceira>"
        for n, ini, fim in periodos
    )
    return f"<?xml version='1.0'?><ArrayOfPeriodoDemonstracaoFinanceira>{corpo}</ArrayOfPeriodoDemonstracaoFinanceira>"


def _info_xml(registros):
    corpo = ""
    for conta, tipo, valores in registros:
        colunas = "".join(
            f"<ValorConta{i}>{valores.get(i, 0):.10f}</ValorConta{i}>" for i in range(1, 13)
        )
        corpo += (
            "<InfoFinaDFin><PlanoConta><VersaoPlanoConta>"
            f"<CodigoTipoInformacaoFinanceira>{tipo}</CodigoTipoInformacaoFinanceira>"
            f"</VersaoPlanoConta><NumeroConta>{conta}</NumeroConta></PlanoConta>"
            f"{colunas}</InfoFinaDFin>"
        )
    return f"<?xml version='1.0'?><ArrayOfInfoFinaDFin>{corpo}</ArrayOfInfoFinaDFin>"


PERIODOS_PADRAO = [
    (1, "2020-01-01", "2020-12-31"),
    (2, "2020-07-01", "2020-09-30"),
    (3, "2019-01-01", "2019-12-31"),
    (4, "2020-01-01", "2020-09-30"),
]


def _anexos_xml(anexos, grupos=None):
    grupos = grupos or ["193"] * len(anexos)
    return "<ArrayOfAnexoDocumento>" + "".join(
        f"<AnexoDocumento><NumeroGrupoRelacionado>{g}</NumeroGrupoRelacionado>"
        "<ImagemObjetoArquivoPdf>"
        + base64.b64encode(_pdf_com_texto(a)).decode()
        + "</ImagemObjetoArquivoPdf></AnexoDocumento>"
        for a, g in zip(anexos, grupos)
    ) + "</ArrayOfAnexoDocumento>"


def _pacote(tmp_path, nome="p.zip", registros=None, periodos=None, escala="2",
            anexos=None, sem=(), formularios=1, interno_corrompido=False, grupos=None):
    registros = registros if registros is not None else [
        ("1", "2", {2: 500.0, 3: 400.0}),
        ("6.01", "2", {4: 70.0}),
    ]
    membros = {
        "InfoFinaDFin.xml": _info_xml(registros),
        "PeriodoDemonstracaoFinanceira.xml": _periodos_xml(periodos or PERIODOS_PADRAO),
        "FormularioDemonstracaoFinanceiraITR.xml":
            f"<F><CodigoEscalaMoeda>{escala}</CodigoEscalaMoeda></F>",
    }
    if anexos is not None:
        membros["AnexoDocumento.xml"] = _anexos_xml(anexos, grupos)
    for m in sem:
        membros.pop(m)
    interno = io.BytesIO()
    with zipfile.ZipFile(interno, "w", zipfile.ZIP_DEFLATED) as z:
        for n, c in membros.items():
            z.writestr(n, c)
    dados_internos = interno.getvalue()
    if interno_corrompido:
        dados_internos = dados_internos[: len(dados_internos) // 2]
    caminho = tmp_path / nome
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        for i in range(formularios):
            z.writestr(f"00000120200930030{i}.itr", dados_internos)
        z.writestr("FormularioCadastral.xml", "<x/>")
    return caminho


# --- V1: integridade ------------------------------------------------------------

class TestIntegridadeDoPacote:
    def test_pacote_integro_passa(self, tmp_path):
        assert rad.validar_pacote(_pacote(tmp_path)).endswith(".itr")

    def test_pacote_truncado_falha(self, tmp_path):
        """O RAD responde 200 e corta a conexão: só a estrutura denuncia."""
        caminho = _pacote(tmp_path)
        dados = caminho.read_bytes()
        caminho.write_bytes(dados[: len(dados) * 2 // 3])
        with pytest.raises(rad.PacoteInvalido):
            rad.validar_pacote(caminho)

    def test_html_de_erro_com_status_200_falha(self, tmp_path):
        caminho = tmp_path / "erro.zip"
        caminho.write_text("<html>Erro</html>")
        with pytest.raises(rad.PacoteInvalido):
            rad.validar_pacote(caminho)

    def test_formulario_interno_corrompido_falha(self, tmp_path):
        with pytest.raises(rad.PacoteInvalido):
            rad.validar_pacote(_pacote(tmp_path, interno_corrompido=True))

    def test_sem_formulario_ou_com_dois_falha(self, tmp_path):
        with pytest.raises(rad.PacoteInvalido):
            rad.validar_pacote(_pacote(tmp_path, "a.zip", formularios=0))
        with pytest.raises(rad.PacoteInvalido):
            rad.validar_pacote(_pacote(tmp_path, "b.zip", formularios=2))

    @pytest.mark.parametrize("membro", ["InfoFinaDFin.xml", "PeriodoDemonstracaoFinanceira.xml",
                                        "FormularioDemonstracaoFinanceiraITR.xml"])
    def test_formulario_sem_membro_exigido_falha(self, tmp_path, membro):
        with pytest.raises(rad.PacoteInvalido):
            rad.validar_pacote(_pacote(tmp_path, sem=(membro,)))


class TestAquisicao:
    @staticmethod
    def _curl_que_escreve(sequencia):
        """Dublê de `subprocess.run`: cada chamada grava o próximo conteúdo."""
        chamadas = []

        def executar(argv, **_):
            destino = argv[argv.index("-o") + 1]
            conteudo = sequencia[min(len(chamadas), len(sequencia) - 1)]
            chamadas.append(argv)
            if conteudo is not None:
                with open(destino, "wb") as f:
                    f.write(conteudo)
        executar.chamadas = chamadas
        return executar

    def test_truncado_depois_integro_aceita_o_integro(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rad, "COOKIES", tmp_path / "c")
        bom = _pacote(tmp_path, "bom.zip").read_bytes()
        executar = self._curl_que_escreve([bom[:100], bom])
        destino = tmp_path / "saida" / "1.zip"
        digest = rad.baixar("1", destino, espera=0, executar=executar)
        assert len(executar.chamadas) == 2
        assert digest == rad.sha256(destino)
        assert not destino.with_suffix(".zip.parcial").exists()

    def test_sempre_truncado_e_falha_de_acesso_nao_inexistencia(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rad, "COOKIES", tmp_path / "c")
        executar = self._curl_que_escreve([b"PK\x03\x04lixo"])
        destino = tmp_path / "1.zip"
        with pytest.raises(rad.FalhaDeAcesso, match="não prova"):
            rad.baixar("1", destino, tentativas=3, espera=0, executar=executar)
        assert len(executar.chamadas) == 3
        assert not destino.exists()

    def test_formato_estranho_nao_e_falha_de_acesso_nem_retenta(self, tmp_path, monkeypatch):
        """Pacote íntegro sem os membros esperados: a causa é o formato.

        Tentar de novo não muda o formato, e chamar isso de falha de acesso
        daria o nome errado à causa — o formulário antigo (2011–2012) é o caso
        que o estrato E9 do piloto existe para medir.
        """
        monkeypatch.setattr(rad, "COOKIES", tmp_path / "c")
        estranho = _pacote(tmp_path, "est.zip", sem=("InfoFinaDFin.xml",)).read_bytes()
        executar = self._curl_que_escreve([estranho])
        destino = tmp_path / "b" / "5.zip"
        with pytest.raises(rad.FormatoNaoReconhecido):
            rad.baixar("5", destino, tentativas=4, espera=0, executar=executar)
        assert len(executar.chamadas) == 1
        assert (tmp_path / "b" / "nao_reconhecidos" / "5.zip").is_file()
        assert not destino.exists()

    def test_formato_nao_reconhecido_e_registrado_e_nao_rebaixado(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rad, "COOKIES", tmp_path / "c")
        estranho = _pacote(tmp_path, "est.zip", sem=("InfoFinaDFin.xml",)).read_bytes()
        executar = self._curl_que_escreve([estranho])
        monkeypatch.setattr(rad.subprocess, "run", executar)
        doc = {"id_doc": "5", "cd_cvm": "000001", "conjunto": "itr",
               "dt_refer": "2011-03-31", "versao": 1}
        brutos, manifesto = tmp_path / "b", tmp_path / "m.jsonl"
        primeiro = rad.adquirir(doc, brutos=brutos, manifesto=manifesto, espera=0)
        segundo = rad.adquirir(doc, brutos=brutos, manifesto=manifesto, espera=0)
        assert primeiro["estado"] == segundo["estado"] == "formato_nao_reconhecido"
        assert len(executar.chamadas) == 1

    def test_formato_guardado_que_passou_a_ser_suportado_e_promovido(self, tmp_path, monkeypatch):
        """O XML único foi 'não reconhecido' na 1ª execução do piloto e é lido hoje."""
        monkeypatch.setattr(rad, "COOKIES", tmp_path / "c")
        brutos = tmp_path / "b"
        (brutos / "nao_reconhecidos").mkdir(parents=True)
        pacote = _pacote(tmp_path, "ok.zip").read_bytes()
        (brutos / "nao_reconhecidos" / "9.zip").write_bytes(pacote)
        monkeypatch.setattr(rad, "baixar", lambda *a, **k: pytest.fail("não devia baixar"))
        doc = {"id_doc": "9", "cd_cvm": "000001", "conjunto": "itr",
               "dt_refer": "2021-03-31", "versao": 1}
        r = rad.adquirir(doc, brutos=brutos, manifesto=tmp_path / "m.jsonl")
        assert r["estado"] == "integro" and r["promovido_de"] == "nao_reconhecidos"
        assert (brutos / "9.zip").is_file()
        linha = json.loads((tmp_path / "m.jsonl").read_text())
        assert linha["estado"] == "integro" and linha["promovido_de"] == "nao_reconhecidos"
        assert not (brutos / "nao_reconhecidos" / "9.zip").exists()

    def test_truncamento_e_transporte_formato_e_formato(self, tmp_path):
        caminho = _pacote(tmp_path, "t.zip")
        caminho.write_bytes(caminho.read_bytes()[:50])
        with pytest.raises(rad.PacoteInvalido) as erro:
            rad.validar_pacote(caminho)
        assert erro.value.tipo == "transporte"
        with pytest.raises(rad.PacoteInvalido) as erro:
            rad.validar_pacote(_pacote(tmp_path, "f.zip", sem=("InfoFinaDFin.xml",)))
        assert erro.value.tipo == "formato"

    def test_usa_https_e_id_numerico(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rad, "COOKIES", tmp_path / "c")
        with pytest.raises(ValueError):
            rad.baixar("1; rm -rf /", tmp_path / "x.zip", executar=lambda *a, **k: None)
        executar = self._curl_que_escreve([_pacote(tmp_path).read_bytes()])
        rad.baixar("98282", tmp_path / "y.zip", espera=0, executar=executar)
        assert executar.chamadas[0][-1].startswith("https://")
        assert executar.chamadas[0][-1].endswith("NumeroSequencialDocumento=98282")

    def test_falha_de_acesso_e_registrada_com_esse_nome(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rad, "COOKIES", tmp_path / "c")
        monkeypatch.setattr(rad, "baixar", lambda *a, **k: (_ for _ in ()).throw(
            rad.FalhaDeAcesso("sem pacote")))
        manifesto = tmp_path / "m.jsonl"
        doc = {"id_doc": "7", "cd_cvm": "000001", "conjunto": "itr",
               "dt_refer": date(2020, 9, 30), "versao": 1}
        registro = rad.adquirir(doc, brutos=tmp_path, manifesto=manifesto)
        assert registro["estado"] == "falha_de_acesso"
        linha = json.loads(manifesto.read_text())
        assert linha["estado"] == "falha_de_acesso" and "inexistente" not in linha["estado"]

    def test_arquivo_em_disco_e_revalidado_antes_de_reaproveitado(self, tmp_path, monkeypatch):
        """Arquivo existir não é prova de integridade."""
        monkeypatch.setattr(rad, "COOKIES", tmp_path / "c")
        (tmp_path / "7.zip").write_bytes(b"truncado")
        chamadas = []

        def baixar(id_doc, destino, **_):
            chamadas.append(id_doc)
            destino.write_bytes(_pacote(tmp_path, "novo.zip").read_bytes())
            return rad.sha256(destino)
        monkeypatch.setattr(rad, "baixar", baixar)
        doc = {"id_doc": "7", "cd_cvm": "000001", "conjunto": "itr",
               "dt_refer": "2020-09-30", "versao": 1}
        registro = rad.adquirir(doc, brutos=tmp_path, manifesto=tmp_path / "m.jsonl", pausa=0)
        assert chamadas == ["7"] and registro["estado"] == "integro"
        assert registro["reaproveitado"] is False
        de_novo = rad.adquirir(doc, brutos=tmp_path, manifesto=tmp_path / "m.jsonl")
        assert chamadas == ["7"] and de_novo["reaproveitado"] is True


# --- X1: leitura ---------------------------------------------------------------

class TestLeituraDoFormulario:
    def test_so_o_consolidado_e_lido(self, tmp_path):
        """A conta `1` aparece duas vezes; a primeira é a controladora."""
        caminho = _pacote(tmp_path, registros=[
            ("1", "1", {2: 999.0}), ("1", "2", {2: 500.0}),
        ])
        chaves = rad.por_chave(rad.ler(caminho, com_anexos=False))
        assert chaves[("1", None, date(2020, 9, 30))] == 500.0

    def test_coluna_segue_o_numero_do_periodo_nao_a_ordem(self, tmp_path):
        periodos = [(4, "2020-01-01", "2020-09-30"), (2, "2020-07-01", "2020-09-30"),
                    (1, "2020-01-01", "2020-12-31"), (3, "2019-01-01", "2019-12-31")]
        caminho = _pacote(tmp_path, periodos=periodos,
                          registros=[("6.01", "2", {4: 70.0, 2: 0.0})])
        chaves = rad.por_chave(rad.ler(caminho, com_anexos=False))
        assert chaves[("6.01", date(2020, 1, 1), date(2020, 9, 30))] == 70.0
        assert chaves[("6.01", date(2020, 7, 1), date(2020, 9, 30))] == 0.0

    def test_valor_em_coluna_sem_periodo_falha(self, tmp_path):
        caminho = _pacote(tmp_path, registros=[("1", "2", {9: 5.0})])
        with pytest.raises(rad.PacoteInvalido, match="sem período"):
            rad.ler(caminho, com_anexos=False)

    def test_posicao_colapsa_pela_data_e_recusa_contradicao(self, tmp_path):
        ok = _pacote(tmp_path, "ok.zip", registros=[("1", "2", {2: 500.0, 4: 0.0})])
        assert rad.por_chave(rad.ler(ok, com_anexos=False))[
            ("1", None, date(2020, 9, 30))] == 500.0
        ruim = _pacote(tmp_path, "ruim.zip", registros=[("1", "2", {2: 500.0, 4: 501.0})])
        with pytest.raises(rad.PacoteInvalido, match="distintos"):
            rad.por_chave(rad.ler(ruim, com_anexos=False))

    def test_codigo_de_escala_e_lido_sem_ser_interpretado(self, tmp_path):
        """X1.4: o mapeamento código→rótulo é MEDIDO, não suposto."""
        assert rad.ler(_pacote(tmp_path, escala="1"), com_anexos=False).codigo_escala_moeda == "1"
        assert not hasattr(rad, "ESCALA_POR_CODIGO")

    def test_data_sentinela_vira_nulo(self, tmp_path):
        periodos = [(2, "0001-01-01", "2020-09-30")]
        caminho = _pacote(tmp_path, periodos=periodos, registros=[("1", "2", {2: 1.0})])
        assert rad.ler(caminho, com_anexos=False).periodos[2] == (None, date(2020, 9, 30))

    def test_texto_dos_anexos_e_extraido(self, tmp_path):
        caminho = _pacote(tmp_path, anexos=[["Notas explicativas",
                                             "Valores expressos em milhares de reais"]])
        anexos = rad.ler(caminho).anexos
        assert len(anexos) == 1
        assert "milhares de reais" in " ".join(anexos[0][1])


# --- N1: evidência de unidade ---------------------------------------------------

def _anexo(*paginas):
    return [(0, list(paginas))]


class TestDeclaracaoDeUnidade:
    @pytest.mark.parametrize("texto", [
        "(Valores expressos em milhares de reais, exceto quando indicado)",
        "Em milhares de R$",
        "Balanço patrimonial (R$ mil)",
        "Em R$ milhares",
    ])
    def test_declaracoes_de_mil(self, texto):
        assert rad.classificar_unidade(_anexo(texto))["classe"] == "declara_MIL"

    @pytest.mark.parametrize("texto", [
        "As demonstrações estão expressas em reais.",
        "Valores em reais, exceto quando indicado",
    ])
    def test_declaracoes_de_unidade(self, texto):
        assert rad.classificar_unidade(_anexo(texto))["classe"] == "declara_UNIDADE"

    def test_milhares_de_reais_nao_conta_como_em_reais(self):
        """`em milhares de reais` não contém `em reais` — não pode virar contradição."""
        r = rad.classificar_unidade(_anexo("valores expressos em milhares de reais"))
        assert r["classe"] == "declara_MIL"
        assert "UNIDADE" not in r["contagem"]

    def test_valor_em_prosa_nao_e_declaracao_de_milhao(self):
        """N1.3: 'lucro de R$ 1.393,6 milhões' não declara a unidade da tabela."""
        r = rad.classificar_unidade(_anexo("lucro líquido de R$ 1.393,6 milhões no período"))
        assert r["classe"] == "ausente"

    def test_duas_unidades_sao_contradicao(self):
        r = rad.classificar_unidade(_anexo("em milhares de reais", "expressos em reais"))
        assert r["classe"] == "contraditorio"

    def test_sem_declaracao_e_ausente(self):
        assert rad.classificar_unidade(_anexo("Informações gerais"))["classe"] == "ausente"
        assert rad.classificar_unidade([])["classe"] == "ausente"

    def test_evidencia_guarda_pagina_e_trecho_legivel(self):
        """N1.4: a classificação tem de ser conferível por leitura humana."""
        longa = "a" * 80 + " valores em milhares de reais " + "b" * 80
        curta = "x em milhares de reais y"
        r = rad.classificar_unidade(_anexo("capa", longa, curta))
        e_longa, e_curta = r["evidencias"]
        assert (e_longa["pagina"], e_curta["pagina"]) == (2, 3)
        assert e_longa["anexo"] == 0
        assert len(e_longa["trecho"]) >= rad.TRECHO_MINIMO
        # Página menor que o mínimo: o trecho é a página inteira, não um pedaço.
        assert e_curta["trecho"] == curta

    def test_vocabulario_de_classes_e_fechado(self):
        for texto in ["", "em reais", "em milhares de reais", "em milhões de reais",
                      "em reais e em milhares de reais"]:
            assert rad.classificar_unidade(_anexo(texto))["classe"] in rad.CLASSES_DE_UNIDADE


# --- RA1: XML único ---------------------------------------------------------------

def _conta(codigo, **colunas):
    return ("<Conta><ContaFixa>True</ContaFixa>"
            f"<CodigoConta>{codigo}</CodigoConta><DescricaoConta>x</DescricaoConta>"
            + "".join(f"<{k}>{v}</{k}>" for k, v in colunas.items()) + "</Conta>")


def _xml_itr(consolidadas, individuais="", anexos="", escala="2", fim="30/09/2024",
             ini_ex="01/01/2024", ini_ant="01/01/2023", fim_ant="31/12/2023"):
    return (
        "<?xml version='1.0' encoding='utf-8'?><XmlInformacoesTrimestraisFinanceiras>"
        "<DadosEmpresa/><Documento/><DadosITR>"
        f"<DataReferencia>{fim}</DataReferencia><DtInicioTrimestreAtual>01/07/2024</DtInicioTrimestreAtual>"
        f"<DtFimTrimestreAtual>{fim}</DtFimTrimestreAtual>"
        f"<DtInicioExercicioSocialCurso>{ini_ex}</DtInicioExercicioSocialCurso>"
        "<DtFimExercicioSocialCurso>31/12/2024</DtFimExercicioSocialCurso>"
        f"<DtInicioExercicioSocialAnterior>{ini_ant}</DtInicioExercicioSocialAnterior>"
        f"<DtFimExercicioSocialAnterior>{fim_ant}</DtFimExercicioSocialAnterior>"
        f"<EscalaMoeda>{escala}</EscalaMoeda><Formulario>"
        f"<DfIndividuais><BalancoPatrimonialAtivo>{individuais}</BalancoPatrimonialAtivo></DfIndividuais>"
        f"<DfConsolidadas>{consolidadas}</DfConsolidadas></Formulario>"
        f"<AnexosDocumento>{anexos}</AnexosDocumento></DadosITR></XmlInformacoesTrimestraisFinanceiras>"
    )


def _xml_dfp(consolidadas, com_field=True):
    sufixo = "Field" if com_field else ""
    return (
        "<?xml version='1.0' encoding='utf-8'?><XmlDemonstracoesFinanceiras><DadosEmpresa/><Documento/><DadosDFP>"
        "<DtInicioUltimoExercicioSocial>01/01/2024</DtInicioUltimoExercicioSocial>"
        "<DtFimUltimoExercicioSocial>31/12/2024</DtFimUltimoExercicioSocial>"
        "<DtInicioPenultimoExercicioSocial>01/01/2023</DtInicioPenultimoExercicioSocial>"
        "<DtFimPenultimoExercicioSocial>31/12/2023</DtFimPenultimoExercicioSocial>"
        f"<DtInicioAntepenultimoExercicioSocial{sufixo}>01/01/2022</DtInicioAntepenultimoExercicioSocial{sufixo}>"
        f"<DtFimAntepenultimoExercicioSocial{sufixo}>31/12/2022</DtFimAntepenultimoExercicioSocial{sufixo}>"
        "<EscalaMoeda>1</EscalaMoeda><Formulario>"
        f"<DfConsolidadas>{consolidadas}</DfConsolidadas></Formulario></DadosDFP></XmlDemonstracoesFinanceiras>"
    )


def _pacote_unico(tmp_path, xml, nome_xml="025704ITR30-09-2024v1.xml", arquivo="u.zip"):
    caminho = tmp_path / arquivo
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(nome_xml, xml)
        z.writestr("FormularioCadastral.xml", "<x/>")
        z.writestr("123_025704_1.pdf", b"%PDF-1.4 corpo qualquer")
    return caminho


BPA_ITR = ("<BalancoPatrimonialAtivo>" + _conta("1", TrimestreAtual="2.862.762",
           ExercicioAnterior="2.358.531") + "</BalancoPatrimonialAtivo>")
DFC_ITR = ("<DemonstracaoFluxoCaixa>" + _conta("6.01", Metodo="Indireto",
           AcumuladoAtualExercicio="-1.500", AcumuladoExercicioAnterior="(2.000,5)")
           + "</DemonstracaoFluxoCaixa>")


class TestXmlUnico:
    def test_pacote_xml_unico_e_reconhecido_pelo_conteudo(self, tmp_path):
        caminho = _pacote_unico(tmp_path, _xml_itr(BPA_ITR))
        assert rad.validar_pacote(caminho) == "025704ITR30-09-2024v1.xml"
        assert rad.ler(caminho, com_anexos=False).formato == "xml_unico"

    def test_raiz_desconhecida_e_formato(self, tmp_path):
        caminho = _pacote_unico(tmp_path, "<?xml version='1.0'?><OutraCoisa/>")
        with pytest.raises(rad.PacoteInvalido) as erro:
            rad.validar_pacote(caminho)
        assert erro.value.tipo == "formato"

    def test_xml_truncado_e_transporte(self, tmp_path):
        caminho = _pacote_unico(tmp_path, _xml_itr(BPA_ITR)[:200])
        with pytest.raises(rad.PacoteInvalido) as erro:
            rad.validar_pacote(caminho)
        assert erro.value.tipo == "transporte"

    def test_nome_fora_do_padrao_nao_e_aceito(self, tmp_path):
        caminho = _pacote_unico(tmp_path, _xml_itr(BPA_ITR), nome_xml="qualquer.xml")
        with pytest.raises(rad.PacoteInvalido):
            rad.validar_pacote(caminho)

    def test_itr_mapeia_colunas_pelas_datas_do_cabecalho(self, tmp_path):
        f = rad.ler(_pacote_unico(tmp_path, _xml_itr(BPA_ITR + DFC_ITR)), com_anexos=False)
        chaves = rad.por_chave(f)
        assert chaves[("1", None, date(2024, 9, 30))] == 2862762.0
        assert chaves[("1", None, date(2023, 12, 31))] == 2358531.0
        assert chaves[("6.01", date(2024, 1, 1), date(2024, 9, 30))] == -1500.0
        # O acumulado anterior: mesmo recorte, um exercício antes.
        assert chaves[("6.01", date(2023, 1, 1), date(2023, 9, 30))] == -2000.5
        assert f.codigo_escala_moeda == "2"

    def test_acumulado_anterior_preserva_fim_de_mes_em_exercicio_nao_civil(self, tmp_path):
        xml = _xml_itr(DFC_ITR, fim="31/12/2024", ini_ex="01/07/2024",
                       ini_ant="01/07/2023", fim_ant="30/06/2024")
        chaves = rad.por_chave(rad.ler(_pacote_unico(tmp_path, xml), com_anexos=False))
        assert ("6.01", date(2023, 7, 1), date(2023, 12, 31)) in chaves

    def test_so_consolidado(self, tmp_path):
        individual = _conta("1", TrimestreAtual="999", ExercicioAnterior="999")
        f = rad.ler(_pacote_unico(tmp_path, _xml_itr(BPA_ITR, individuais=individual)),
                    com_anexos=False)
        assert rad.por_chave(f)[("1", None, date(2024, 9, 30))] == 2862762.0

    def test_contas_de_outras_demonstracoes_sao_ignoradas(self, tmp_path):
        dre = "<DemonstracaoResultado>" + _conta("1", TrimestreAtual="5") + "</DemonstracaoResultado>"
        f = rad.ler(_pacote_unico(tmp_path, _xml_itr(dre)), com_anexos=False)
        assert f.valores == []

    @pytest.mark.parametrize("com_field", [True, False])
    def test_dfp_tres_exercicios_com_e_sem_sufixo(self, tmp_path, com_field):
        bpa = ("<BalancoPatrimonialAtivo>" + _conta("1", UltimoExercicio="3", PenultimoExercicio="2",
               AntepenultimoExercicio="1") + "</BalancoPatrimonialAtivo>")
        f = rad.ler(_pacote_unico(tmp_path, _xml_dfp(bpa, com_field),
                                  nome_xml="025704DFP31-12-2024v1.xml"), com_anexos=False)
        chaves = rad.por_chave(f)
        assert chaves[("1", None, date(2022, 12, 31))] == 1.0
        assert chaves[("1", None, date(2024, 12, 31))] == 3.0
        assert f.codigo_escala_moeda == "1"

    def test_coluna_desconhecida_com_valor_falha(self, tmp_path):
        bpa = "<BalancoPatrimonialAtivo>" + _conta("1", ColunaNova="10") + "</BalancoPatrimonialAtivo>"
        with pytest.raises(rad.PacoteInvalido, match="sem período"):
            rad.ler(_pacote_unico(tmp_path, _xml_itr(bpa)), com_anexos=False)

    def test_anexos_do_xml_unico_trazem_o_grupo(self, tmp_path):
        anexos = ("<X><NumeroGrupoRelacionado>193</NumeroGrupoRelacionado><ImagemObjetoArquivoPdf>"
                  + base64.b64encode(_pdf_com_texto(["em milhares de reais"])).decode()
                  + "</ImagemObjetoArquivoPdf></X>")
        f = rad.ler(_pacote_unico(tmp_path, _xml_itr(BPA_ITR, anexos=anexos)))
        assert f.grupos_anexos == {0: "193"}
        assert "milhares" in rad.texto_das_notas(f)


class TestNumeroPtBr:
    @pytest.mark.parametrize("texto,esperado", [
        ("2.555.870", 2555870.0), ("-153.918", -153918.0), ("(10)", -10.0),
        ("1.234,56", 1234.56), ("0", 0.0), ("", 0.0), (None, 0.0), ("00", 0.0),
    ])
    def test_formatos(self, texto, esperado):
        assert rad.numero_ptbr(texto) == esperado

    @pytest.mark.parametrize("texto", ["n/d", "1,2,3", "R$ 10"])
    def test_texto_inesperado_nao_vira_zero(self, texto):
        with pytest.raises(rad.PacoteInvalido):
            rad.numero_ptbr(texto)


# --- RA3: evidência nas notas -------------------------------------------------------

def _form(valores, anexos, grupos):
    return rad.Formulario("f", "2", {}, valores, anexos=anexos, grupos_anexos=grupos)


class TestEvidenciaNasNotas:
    def test_so_o_texto_das_notas_conta(self, tmp_path):
        """O release fala em 'R$ milhões'; as notas é que declaram a unidade."""
        caminho = _pacote(tmp_path, anexos=[["expressos em reais"], ["(em milhares de reais)"]],
                          grupos=["192", "193"])
        f = rad.ler(caminho)
        assert rad.classificar_cabecalho(rad.texto_das_notas(f))["classe"] == "MIL"

    def test_dfp_usa_o_grupo_412(self):
        f = _form([], [(0, ["em milhares de reais, exceto"])], {0: "412"})
        assert rad.classificar_cabecalho(rad.texto_das_notas(f))["classe"] == "MIL"

    def test_sem_anexo_de_notas_e_estado_proprio(self):
        f = _form([], [(0, ["em milhares de reais"])], {0: "192"})
        texto = rad.texto_das_notas(f)
        assert texto is None
        assert rad.classificar_cabecalho(texto)["classe"] == "sem_notas"
        assert rad.evidencia_numerica(f, texto)["classe"] == "sem_notas"

    @pytest.mark.parametrize("texto,classe", [
        ("(valores expressos em milhares de reais, exceto quando indicado)", "MIL"),
        ("demonstrações (em reais)", "UNIDADE"),
        ("expressos em milhares de reais ... valores em reais", "contraditorio"),
        ("nota 1 - contexto operacional", "ausente"),
    ])
    def test_cabecalho(self, texto, classe):
        assert rad.classificar_cabecalho(rad._normalizar(texto))["classe"] == classe

    def _evid(self, valores, texto):
        f = _form([("1", None, date(2024, 9, 30), v) for v in valores], [], {})
        return rad.evidencia_numerica(f, rad._normalizar(texto))

    def test_bruto(self):
        assert self._evid([2862762.0], "ativo total 2.862.762 2.358.531")["classe"] == "bruto"

    def test_dividido_indica_formulario_em_reais(self):
        assert self._evid([2862762000.0], "ativo total 2.862.762")["classe"] == "dividido"

    def test_multiplicado_indica_formulario_em_milhares(self):
        assert self._evid([2862762.0], "ativo total 2.862.762.000")["classe"] == "multiplicado"

    def test_numero_colado_nao_casa(self):
        """'12.862.762' não é '2.862.762'; '2.862.762.000' não é o bruto."""
        r = self._evid([2862762.0], "x 12.862.762 y 22.862.7629")
        assert r["classe"] == "nenhum"
        assert self._evid([2862762.0], "2.862.762.000")["contagem"]["bruto"] == 0

    def test_decimal_depois_do_numero_ainda_casa(self):
        assert self._evid([2862762.0], "total 2.862.762,00 reais")["classe"] == "bruto"

    def test_valor_pequeno_nao_e_testado(self):
        r = self._evid([12.0, 999.0], "12 999")
        assert r["classe"] == "nenhum" and r["valores_testados"] == 0

    def test_duas_classes_sao_conflito(self):
        assert self._evid([2862762.0, 5000000.0], "2.862.762 e 5.000.000.000")["classe"] == "conflitante"

    def test_vocabularios_fechados(self):
        """B5 (auditoria): igualdade, não superconjunto."""
        assert set(rad.CLASSES_DE_CABECALHO) == {"MIL", "UNIDADE", "contraditorio", "ausente", "sem_notas"}
        assert rad.GRUPOS_NOTAS == {"193", "412"}

    @pytest.mark.parametrize("paginas,grupo", [
        (["(em milhares de reais) nota"], "193"), (["nada aqui"], "193"),
        (["(em reais) nota"], "412"), (["(em milhares de reais)"], "1653"),
    ])
    def test_classe_de_apresentacao_pertence_ao_vocabulario(self, paginas, grupo):
        f = rad.Formulario("f", "2", {}, [], anexos=[(0, paginas)], grupos_anexos={0: grupo})
        assert rad.classificar_cabecalho_de_apresentacao(f)["classe"] in {"MIL", "ausente", "sem_notas"}


class TestLeituraSoDasNotas:
    def test_ler_so_as_notas_da_o_mesmo_texto_e_os_mesmos_indices(self, tmp_path):
        caminho = _pacote(tmp_path, anexos=[["release em R$ milhões"],
                                            ["(em milhares de reais) nota 1"],
                                            ["relatório"]],
                          grupos=["192", "193", "419"])
        tudo = rad.ler(caminho)
        notas = rad.ler(caminho, grupos=rad.GRUPOS_NOTAS)
        assert rad.texto_das_notas(tudo) == rad.texto_das_notas(notas)
        assert [i for i, _ in notas.anexos] == [1]
        assert notas.grupos_anexos == tudo.grupos_anexos == {0: "192", 1: "193", 2: "419"}

    def test_sem_filtro_le_todos(self, tmp_path):
        caminho = _pacote(tmp_path, anexos=[["a"], ["b"]], grupos=["192", "193"])
        assert [i for i, _ in rad.ler(caminho).anexos] == [0, 1]


class TestPausa:
    def test_pausa_depois_de_download_bem_sucedido(self, tmp_path, monkeypatch):
        """V1.1 (auditoria de 16/09): espera também entre requisições bem-sucedidas."""
        esperas = []
        monkeypatch.setattr(rad.time, "sleep", esperas.append)
        monkeypatch.setattr(rad, "baixar", lambda id_doc, destino, **_: (
            destino.write_bytes(b"x"), "h")[1])
        doc = {"id_doc": "7", "cd_cvm": "000001", "conjunto": "itr",
               "dt_refer": "2020-09-30", "versao": 1}
        rad.adquirir(doc, brutos=tmp_path, manifesto=tmp_path / "m.jsonl")
        assert esperas == [rad.PAUSA_ENTRE_DOCUMENTOS] and rad.PAUSA_ENTRE_DOCUMENTOS > 0
