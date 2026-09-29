"""Contratos do piloto CAND-02-P (`scripts/cand02p_piloto.py`).

A regra de decisão do §5 do protocolo foi escrita e testada antes de existir
qualquer rótulo. As contraprovas cobrem a ordem das paradas e a guarda que não
aprova por ausência de dado (α NaN, nDCG ausente).
"""

from __future__ import annotations

import json
import math

import pytest

from scripts import cand02p_piloto as p


def _metricas(**kw) -> dict:
    base = {"alfa": 0.8, "fracao_nao_julgavel": 0.01, "eventos_nota_2": 40,
            "macro": {"b1": {"ndcg10": 0.60, "ndcg20": 0.62}, "m": {"ndcg10": 0.75, "ndcg20": 0.70}},
            "pares_vencidos_m_sobre_b1": 8, "criticos_top20": {"b1": 5, "m": 6}}
    base.update(kw)
    return base


# --- decisão -----------------------------------------------------------------------

def test_promissor_quando_tudo_passa():
    assert p.decidir(_metricas())[0] == "PROMISSOR"


@pytest.mark.parametrize("alfa", [None, math.nan, 0.66])
def test_alfa_ausente_nan_ou_baixo_e_indecidivel(alfa):
    """NaN < 0,67 é falso: sem a guarda, a parada 1 aprovaria sem medir."""
    veredito, motivo = p.decidir(_metricas(alfa=alfa))
    assert veredito == "INDECIDIVEL" and "parada 1" in motivo


def test_nao_julgaveis_demais_e_indecidivel():
    assert p.decidir(_metricas(fracao_nao_julgavel=0.06))[0] == "INDECIDIVEL"


def test_poucos_nota_2_e_indecidivel():
    veredito, motivo = p.decidir(_metricas(eventos_nota_2=29))
    assert veredito == "INDECIDIVEL" and "parada 2" in motivo


def test_ndcg_ausente_e_indecidivel_e_nao_erro():
    m = _metricas()
    m["macro"]["m"]["ndcg10"] = None
    assert p.decidir(m)[0] == "INDECIDIVEL"


def test_b1_no_teto_e_inviavel_antes_do_desafio():
    m = _metricas()
    m["macro"]["b1"] = {"ndcg10": 0.95, "ndcg20": 0.96}
    veredito, motivo = p.decidir(m)
    assert veredito == "INVIAVEL" and "parada 3" in motivo


@pytest.mark.parametrize("ajuste", [
    {"macro": {"b1": {"ndcg10": 0.60, "ndcg20": 0.62}, "m": {"ndcg10": 0.69, "ndcg20": 0.70}}},
    {"macro": {"b1": {"ndcg10": 0.60, "ndcg20": 0.62}, "m": {"ndcg10": 0.75, "ndcg20": 0.66}}},
    {"pares_vencidos_m_sobre_b1": 6},
    {"criticos_top20": {"b1": 5, "m": 4}},
])
def test_cada_condicao_do_desafio_derruba_sozinha(ajuste):
    veredito, motivo = p.decidir(_metricas(**ajuste))
    assert veredito == "INVIAVEL" and "parada 4" in motivo


def test_ordem_das_paradas_indecidivel_vem_antes_de_inviavel():
    m = _metricas(alfa=0.5, pares_vencidos_m_sobre_b1=0)
    assert p.decidir(m)[0] == "INDECIDIVEL"


# --- rótulos -----------------------------------------------------------------------

def _r(**kw):
    base = {"item": "E001", "nota": 0, "motivo": None, "acao": None, "critico": False,
            "julgavel": True, "justificativa": "rotina"}
    base.update(kw)
    return base


@pytest.mark.parametrize("ruim", [
    _r(nota=3), _r(nota=1, motivo="palpite"), _r(nota=2, motivo="credito", acao=None),
    _r(critico=True), _r(julgavel="sim"), _r(item=1),
])
def test_rotulo_fora_do_contrato_levanta(ruim):
    with pytest.raises(ValueError):
        p.validar_rotulo(ruim)


def test_rotulo_valido_passa():
    r = p.validar_rotulo(_r(nota=2, motivo="credito", acao="investigar", critico=True))
    assert r["nota"] == 2 and r["critico"]


# --- journal e teto ----------------------------------------------------------------

def test_gasto_usa_custo_observado_e_estimativa_quando_nao_ha(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "JOURNAL", tmp_path / "j.jsonl")
    p._journal({"tipo": "intencao", "call_id": "a", "estimativa_usd": 1.0})
    p._journal({"tipo": "conclusao", "call_id": "a", "custo_usd": 0.2})
    p._journal({"tipo": "intencao", "call_id": "b", "estimativa_usd": 0.5})  # caiu no meio
    p._journal({"tipo": "intencao", "call_id": "c", "estimativa_usd": 0.3})
    p._journal({"tipo": "conclusao", "call_id": "c", "custo_usd": None, "ok": False})
    assert p.gasto_no_journal() == pytest.approx(0.2 + 0.5 + 0.3)


def test_sem_opt_in_nao_chama(monkeypatch):
    with pytest.raises(SystemExit, match="permitir-api-paga"):
        p.principal(["rotular-gemini", "--papel", "treino"])


# --- consolidação e pool -----------------------------------------------------------

def _preparar(tmp_path, monkeypatch, rotulos_claude, rotulos_gemini):
    monkeypatch.setattr(p, "DESTINO", tmp_path)
    (tmp_path / "pool" / "teste").mkdir(parents=True)
    pool = {"itens": {"E001": "ev1", "E002": "ev2"}, "origem": {"ev1": ["top20_b1"], "ev2": ["aleatorio"]}}
    (tmp_path / "pool" / "teste" / "P.json").write_text(json.dumps(pool))
    for leitor, rotulos in (("claude", rotulos_claude), ("gemini", rotulos_gemini)):
        pasta = tmp_path / "rotulos" / leitor / "teste"
        pasta.mkdir(parents=True)
        (pasta / "P.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rotulos))


def test_consolidacao_media_dos_ganhos_e_critico_dos_dois(tmp_path, monkeypatch):
    c = [_r(item="E001", nota=2, motivo="credito", acao="verificar", critico=True), _r(item="E002")]
    g = [_r(item="E001", nota=1, motivo="credito"), _r(item="E002")]
    _preparar(tmp_path, monkeypatch, c, g)
    r = p.consolidar("teste", "P", leitores=("claude", "gemini"))
    assert r["ev1"]["ganho"] == pytest.approx((3 + 1) / 2) and r["ev1"]["nota_final"] == 1.5
    assert not r["ev1"]["critico"]


def test_leitura_incompleta_levanta_em_vez_de_virar_zero(tmp_path, monkeypatch):
    _preparar(tmp_path, monkeypatch, [_r(item="E001")], [_r(item="E001"), _r(item="E002")])
    with pytest.raises(ValueError, match="sem rótulo"):
        p.consolidar("teste", "P", leitores=("claude", "gemini"))


def test_item_rotulado_duas_vezes_levanta(tmp_path, monkeypatch):
    _preparar(tmp_path, monkeypatch, [_r(item="E001"), _r(item="E001"), _r(item="E002")],
              [_r(item="E001"), _r(item="E002")])
    with pytest.raises(ValueError, match="duas vezes"):
        p.consolidar("teste", "P", leitores=("claude", "gemini"))


def _eventos_sinteticos(tmp_path, n=300):
    (tmp_path / "eventos").mkdir(parents=True, exist_ok=True)
    (tmp_path / "desafiante").mkdir(parents=True, exist_ok=True)
    with open(tmp_path / "eventos" / "P.jsonl", "w") as f, open(tmp_path / "desafiante" / "P.jsonl", "w") as g:
        for i in range(n):
            f.write(json.dumps({"id": f"e{i:03d}", "rank_b0": i + 1, "rank_b1": n - i}) + "\n")
            g.write(json.dumps({"id": f"e{i:03d}", "rank_c": (i * 7) % n + 1}) + "\n")


def test_pool_contem_os_tops_completa_ate_120_e_e_deterministico(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "DESTINO", tmp_path)
    _eventos_sinteticos(tmp_path)
    pool = p.montar_pool("P", ("b0", "b1", "c"))
    assert len(pool["itens"]) == 120
    ids = set(pool["itens"].values())
    for braco in ("b0", "b1", "c"):
        topo = {i for i, r in p.ranks_do_braco("P", braco).items() if r <= 20}
        assert topo <= ids
    assert p.montar_pool("P", ("b0", "b1", "c")) == pool


def test_pacote_nao_carrega_braco_score_nem_sinal_do_b1():
    ev = {"operacao": "alteracao", "tipo": "tabela", "pagina_antes": 3, "pagina_depois": 4,
          "secao": "s", "antes": "a", "depois": "b", "titulo": "t", "unidade": "milhoes",
          "rotulo": "r", "cabecalho_antes": ["3T25"], "cabecalho_depois": ["4T25"],
          "rank_b0": 1, "rank_b1": 1, "b1_nivel1": True, "categorias": ["credito"],
          "mudancas_numericas": [{"acima_da_triagem": True}], "id": "segredo"}
    item = p.item_do_pacote("E001", ev)
    proibidas = {"rank_b0", "rank_b1", "b1_nivel1", "categorias", "mudancas_numericas", "id"}
    assert not proibidas & set(item)


def test_texto_do_desafiante_e_truncado():
    ev = {"tipo": "texto", "operacao": "adicao", "antes": "", "depois": "x" * 5000}
    assert len(p.texto_c(ev)) == p.TAMANHO_TEXTO_C


# --- conferência humana (§6) --------------------------------------------------------

def _pools_de_teste(tmp_path, pares):
    (tmp_path / "pool" / "teste").mkdir(parents=True, exist_ok=True)
    for par in pares:
        itens = {f"E{n:03d}": f"{par}-ev{n}" for n in range(1, 121)}
        (tmp_path / "pool" / "teste" / f"{par}.json").write_text(json.dumps({"itens": itens}))


def test_amostra_humana_tem_60_estratificada_e_deterministica(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "DESTINO", tmp_path)
    pares = [f"P{n}" for n in range(8)]
    _pools_de_teste(tmp_path, pares)
    amostra = p.sortear_amostra_humana(pares)
    assert len(amostra) == 60 and len(set(amostra)) == 60
    por_par = {}
    for par, _ in amostra:
        por_par[par] = por_par.get(par, 0) + 1
    assert sorted(por_par.values()) == [7, 7, 7, 7, 8, 8, 8, 8]
    assert p.sortear_amostra_humana(pares) == amostra


def test_amostra_humana_so_existe_se_promissor(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "DESTINO", tmp_path)
    (tmp_path / "resultado_teste.json").write_text(json.dumps({"veredito": "INVIAVEL"}))
    with pytest.raises(SystemExit, match="PROMISSOR"):
        p.principal(["amostra-humana"])


# --- Emenda 1 (29/09): leitor único ------------------------------------------------

def test_leitor_unico_pula_o_alfa_mas_mantem_nao_julgaveis():
    """Os três casos de consolidação acima passaram a nomear os dois leitores
    explicitamente (substituição declarada: o padrão virou só o Claude)."""
    assert p.decidir(_metricas(alfa=None, leitores=1))[0] == "PROMISSOR"
    assert p.decidir(_metricas(alfa=None, leitores=1, fracao_nao_julgavel=0.06))[0] == "INDECIDIVEL"
    assert p.decidir(_metricas(alfa=None, leitores=2))[0] == "INDECIDIVEL"


def test_leitor_unico_usa_a_nota_dele(tmp_path, monkeypatch):
    c = [_r(item="E001", nota=2, motivo="credito", acao="verificar", critico=True), _r(item="E002")]
    _preparar(tmp_path, monkeypatch, c, [_r(item="E001"), _r(item="E002")])
    r = p.consolidar("teste", "P")
    assert r["ev1"]["ganho"] == 3.0 and r["ev1"]["critico"]


# --- piloto v2 (29/09) ----------------------------------------------------------------

def test_v2_troca_diretorio_pares_e_herda_os_rotulos_do_v1(monkeypatch):
    for nome in ("DESTINO", "PROTOCOLO", "FONTES", "PAPEIS", "PARES_ESPERADOS", "HERDADOS", "JOURNAL"):
        monkeypatch.setattr(p, nome, getattr(p, nome))
    p.configurar("v2")
    assert p.DESTINO.name == "cand02p_v2" and p.PARES_ESPERADOS == 14
    assert p.PAPEIS == {("4T2023", "1T2024"): "treino", ("4T2024", "1T2025"): "teste"}
    (herdado, papeis), = p.HERDADOS
    assert herdado.name == "cand02p" and papeis == ("treino", "teste")
    assert p.JOURNAL.parent == p.DESTINO


def test_v1_continua_o_padrao(monkeypatch):
    monkeypatch.setattr(p, "DESTINO", p.DESTINO)
    p.configurar("v1")
    assert p.DESTINO.name == "cand02p" and p.HERDADOS == ()


def test_leitura_herdada_devolve_o_diretorio_original(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "DESTINO", tmp_path / "atual")
    with p._Em(tmp_path / "herdado"):
        assert p.DESTINO == tmp_path / "herdado"
    assert p.DESTINO == tmp_path / "atual"
