"""P1–P3 (26/09): somente valores sintéticos; nenhum cálculo sobre FCO real."""
import csv
from decimal import Decimal
import hashlib
import sys
import unicodedata

import pytest

from scripts import adjudicar_escala_rank03b as adj
from scripts import conferir_alcance_geom1_rank03b as c
from scripts import gates_painel_pesquisa_rank03b as gates
from tests.test_gates_painel_pesquisa_rank03b import TestManifestoDeCorrecoes as Fixtures


def test_todas_marcas_e_preenchedores_nao_perdem_sinal_nem_partem_numero():
    # Oráculo independente do conjunto produzido por c._classes().
    sinais = c.classe_de_sinais()
    adicionais = [ch for ch in map(chr, range(sys.maxunicode + 1))
                  if (unicodedata.category(ch).startswith("M") or "FILLER" in unicodedata.name(ch, ""))
                  and ch not in sinais and not ch.isspace()]
    assert len(adicionais) > 2000  # evita aprovação de uma varredura vazia
    for ch in adicionais:
        for linha in (f"Total −{ch}1.234", f"Total ({ch}1.234{ch})", f"Total 1.234{ch}-"):
            t, = c.tokens_da_linha(linha)
            assert t.modulo == 1234 and t.sinal is None, f"U+{ord(ch):04X}"
        for linha in (f"Total 1.234.{ch}567", f"Total 1{ch}234", f"Total 12{ch}34,56"):
            t, = c.tokens_da_linha(linha)
            assert t.modulo is None and t.sinal is None, f"U+{ord(ch):04X}"


@pytest.mark.parametrize("prefixo", ["R $", "R  $", "R\t$", "R\u00a0$", "R\u034f$", "R\ufe00 $",
                                     "U S $", "US $", "R\u3164$"])
@pytest.mark.parametrize("sinal", ["", "-", "−", "+", "("])
def test_moeda_fragmentada_nao_tem_sinal_inferido(prefixo, sinal):
    linha = f"Total {sinal}{prefixo} 1.234" + (")" if sinal == "(" else "")
    t, = c.tokens_da_linha(linha)
    assert t.modulo == 1234 and t.sinal is None and t.motivo == "moeda_fragmentada"
    for v in (1234, -1234):
        assert not c.ocorrencias([linha], {"ativo": Decimal(v)}, por_modulo=False)["ativo"]


@pytest.mark.parametrize("texto,esperado", [("-R$ 1.234", -1), ("−US$ 1.234", -1),
                                           ("R$ 1.234", 1), ("Total $ 1.234", 1),
                                           ("Total (R$ 1.234)", -1), ("−USD 1.234", -1)])
def test_moeda_sem_fragmentacao_continua_valida(texto, esperado):
    t, = c.tokens_da_linha(texto)
    assert t.sinal == esperado and t.modulo == 1234


def _csv(tmp_path, colunas, linhas=()):
    path = tmp_path / "correcoes.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(colunas)
        writer.writerows(linhas)
    return path


@pytest.mark.parametrize("defeito", ["cd_conta", "escopo", "extra", "ausente", "duplicada", "vazio"])
@pytest.mark.parametrize("com_linha", [False, True])
def test_b4_schema_invalido_recusado_antes_de_validar_evidencias(tmp_path, monkeypatch, defeito, com_linha):
    colunas = list(adj.COLUNAS_MANIFESTO)
    if defeito == "ausente":
        colunas.remove("evidencia_numerica")
    elif defeito == "duplicada":
        colunas.append("cd_cvm")
    else:
        colunas.append("" if defeito == "vazio" else defeito)
    path = _csv(tmp_path, colunas, [["" for _ in colunas]] if com_linha else [])
    def proibido(*args, **kwargs):
        pytest.fail("schema inválido chegou à validação semântica")
    monkeypatch.setattr(adj, "validar_manifesto", proibido)
    with pytest.raises(ValueError, match="esquema do manifesto"):
        gates.carregar_correcoes(path)


@pytest.mark.parametrize("delta", [-1, 1])
def test_b4_linha_curta_ou_longa_recusada(tmp_path, monkeypatch, delta):
    path = _csv(tmp_path, adj.COLUNAS_MANIFESTO, [[""] * (len(adj.COLUNAS_MANIFESTO) + delta)])
    def proibido(*args, **kwargs):
        pytest.fail("linha malformada chegou à validação semântica")
    monkeypatch.setattr(adj, "validar_manifesto", proibido)
    with pytest.raises(ValueError, match="quantidade de campos"):
        gates.carregar_correcoes(path)


def test_b4_arquivo_vazio_nao_e_manifesto_sem_correcoes(tmp_path):
    path = tmp_path / "vazio.csv"
    path.write_text("")
    with pytest.raises(ValueError, match="esquema do manifesto"):
        gates.carregar_correcoes(path)


def test_b4_cabecalho_correto_sem_linhas_e_valido(tmp_path):
    path = _csv(tmp_path, adj.COLUNAS_MANIFESTO)
    aquisicao = tmp_path / "aquisicao.jsonl"
    aquisicao.write_text("")
    assert gates.carregar_correcoes(path, aquisicao=aquisicao) == {}


def test_b4_ordem_das_colunas_nao_muda_o_significado(tmp_path):
    colunas = list(reversed(adj.COLUNAS_MANIFESTO))
    linha = Fixtures._linha()
    path = _csv(tmp_path, colunas, [[linha[k] for k in colunas]])
    r = gates.carregar_correcoes(path, aquisicao=Fixtures._aquisicao(tmp_path))
    assert r[("A", "itr", "2020-03-31", 1)] == linha


def test_b4_csv_malformado_recusado(tmp_path):
    path = _csv(tmp_path, adj.COLUNAS_MANIFESTO)
    path.write_text(path.read_text() + '"campo sem fechar\n')
    with pytest.raises(csv.Error):
        gates.carregar_correcoes(path)


@pytest.mark.parametrize("extra", [None, "cd_conta"])
def test_b4_excecao_historica_so_retira_evidencia_numerica(tmp_path, extra):
    colunas = [k for k in adj.COLUNAS_MANIFESTO if k != "evidencia_numerica"]
    if extra:
        colunas.append(extra)
    path = _csv(tmp_path, colunas)
    aquisicao = tmp_path / "aquisicao.jsonl"
    aquisicao.write_text("")
    if extra:
        with pytest.raises(ValueError, match="esquema do manifesto"):
            gates.carregar_correcoes(path, exigir_evidencia_numerica=False, aquisicao=aquisicao)
    else:
        assert gates.carregar_correcoes(path, exigir_evidencia_numerica=False, aquisicao=aquisicao) == {}


def test_b4_hash_e_dos_bytes_interpretados_nao_da_releitura(tmp_path, monkeypatch):
    path = _csv(tmp_path, adj.COLUNAS_MANIFESTO)
    esperado = hashlib.sha256(path.read_bytes()).hexdigest()
    original = adj.validar_manifesto
    def trocar(*args, **kwargs):
        original(*args, **kwargs)
        path.write_text(path.read_text() + "\n")
    monkeypatch.setattr(adj, "validar_manifesto", trocar)
    aquisicao = tmp_path / "aquisicao.jsonl"
    aquisicao.write_text("")
    r = gates.carregar_correcoes(path, aquisicao=aquisicao)
    assert r.origem_sha256 == esperado != gates._sha256(path)
    with pytest.raises(gates.CorrecoesNaoValidadas, match="mudou"):
        gates.executar(r, path)


@pytest.mark.parametrize("reais,impresso", [("1234499", "1.234"), ("1234500", "1.235"),
                                            ("-1234499", "-1.234"), ("-1234500", "-1.235"),
                                            ("1234499.9999999999999999999999999999", "1.234"),
                                            ("-1234499.9999999999999999999999999999", "-1.234"),
                                            ("1234000.01", "1.234"), ("500", "1"), ("-500", "-1")])
def test_ativo_arredondado_inteiro_sinal_e_empate(reais, impresso):
    r = c.candidatas_ativo_arredondado([f"Total do ativo {impresso}"], Decimal(reais))
    assert len(r) == 1 and r[0]["pagina"] == 1 and r[0]["coluna"] == 1


@pytest.mark.parametrize("texto", ["1.234", "-1.235", "1.235,1", "−\u034f1.235", "-R $ 1.235",
                                    "1.235.\ufe00567", "1.236"])
def test_ativo_arredondado_nao_casa_vizinho_sinal_ou_decimal(texto):
    assert not c.candidatas_ativo_arredondado([texto], Decimal("1234500"))


@pytest.mark.parametrize("valor", [Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"),
                                   Decimal("-Infinity"), Decimal(0), 1234.5])
def test_ativo_arredondado_recusa_entrada_invalida(valor):
    with pytest.raises(ValueError, match="finito e não nulo"):
        c.candidatas_ativo_arredondado(["1.234"], valor)


def test_ativo_arredondado_zero_e_exato_nao_sao_confundidos():
    assert not c.candidatas_ativo_arredondado(["0"], Decimal("499.99"))
    assert not c.candidatas_ativo_arredondado(["0"], Decimal("-499.99"))
    assert c.ocorrencias(["1.235"], {"dividido": Decimal("1234.5")}, por_modulo=False) == {"dividido": []}


def test_diagnostico_arredondado_nao_e_chamado_pelo_executor():
    # Trava estática de não integração; testes de execução existentes seguem
    # exercitando o fluxo completo somente com pacotes sintéticos.
    import ast
    import inspect
    arvore = ast.parse(inspect.getsource(c))
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "candidatas_ativo_arredondado"]
    assert chamadas == []
