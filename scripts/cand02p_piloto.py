"""Piloto CAND-02-P — redline com rótulo de IA (protocolo de 28/09).

Protocolo: `resultados/protocolo_cand02p_piloto_ia_2026-09-28.md`. A ordem dos
subcomandos é a ordem de congelamento do §7 do protocolo; cada passo lê só o
que os anteriores gravaram.

    python -m scripts.cand02p_piloto eventos      # universo + B0 + B1 (custo zero)
    python -m scripts.cand02p_piloto desafiante   # C: bge-m3 via Ollama (custo zero)

Nenhum subcomando lê rótulo de teste antes de o M estar congelado.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src import redline as rl  # noqa: E402

DESTINO = RAIZ / "artefatos" / "cand02p"
PROTOCOLO = RAIZ / "resultados" / "protocolo_cand02p_piloto_ia_2026-09-28.md"
SEMENTE = 20260928

#: §2 do protocolo: oito emissores, só releases.
FONTES = (
    (RAIZ / "corpus" / "metadados.csv", RAIZ / "corpus" / "ocr",
     ("BTG", "ITAU", "BRADESCO", "SANTANDER", "BB")),
    (RAIZ / "corpus" / "expansao" / "manifesto_expansao.csv", RAIZ / "corpus" / "expansao" / "ocr",
     ("BMG", "ABC", "BANESTES")),
)
#: §2: treino e teste não compartilham documento; o embargo não é usado.
PAPEIS = {("2T2025", "3T2025"): "treino", ("4T2025", "1T2026"): "teste"}


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def manifesto() -> dict[tuple[str, str], dict]:
    """(empresa, trimestre) → linha do manifesto com o caminho do OCR conferido."""
    saida = {}
    for csv_manifesto, pasta_ocr, empresas in FONTES:
        for linha in csv.DictReader(open(csv_manifesto, encoding="utf-8")):
            if linha["empresa"] not in empresas:
                continue
            ocr = pasta_ocr / f"{linha['hash_sha256']}.json"
            saida[(linha["empresa"], linha["trimestre"])] = {**linha, "ocr": ocr}
    return saida


def carregar_documento(item: dict) -> tuple[rl.Documento, list[str]]:
    dados = json.load(open(item["ocr"], encoding="utf-8"))
    if dados.get("hash_pdf") != item["hash_sha256"]:
        raise ValueError(f"{item['documento']}: cache de OCR de outro PDF")
    paginas = [p["markdown"] for p in dados["ocr"]["pages"]]
    doc = rl.documento_de_paginas(item["documento"], item["empresa"], item["trimestre"], paginas)
    return doc, paginas


def pares() -> list[dict]:
    m = manifesto()
    saida = []
    for empresa in sorted({e for e, _ in m}):
        for (ta, td), papel in PAPEIS.items():
            if (empresa, ta) in m and (empresa, td) in m:
                saida.append({"par": f"{empresa}_{ta}_{td}", "empresa": empresa, "papel": papel,
                              "anterior": m[(empresa, ta)], "atual": m[(empresa, td)]})
    return saida


def exportar_documento(nome: str, paginas: list[str]) -> Path:
    """Documento inteiro, com marca de página, para o leitor Claude (§4)."""
    caminho = DESTINO / "docs" / f"{nome}.md"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("".join(f"\n\n===== PÁGINA {n} =====\n\n{md}" for n, md in enumerate(paginas, 1)),
                       encoding="utf-8")
    return caminho


def cmd_eventos(_args) -> int:
    lista = pares()
    if len(lista) != 16:
        raise SystemExit(f"esperados 16 pares (8 treino + 8 teste), achados {len(lista)}")
    resumo = {"protocolo_sha256": sha256_arquivo(PROTOCOLO),
              "redline_sha256": sha256_arquivo(RAIZ / "src" / "redline.py"), "pares": {}}
    (DESTINO / "eventos").mkdir(parents=True, exist_ok=True)
    for p in lista:
        anterior, pag_a = carregar_documento(p["anterior"])
        atual, pag_d = carregar_documento(p["atual"])
        exportar_documento(anterior.nome, pag_a)
        exportar_documento(atual.nome, pag_d)
        eventos = rl.gerar_eventos(p["par"], anterior, atual)
        b0 = {e.id: i for i, e in enumerate(rl.ordenar_b0(eventos), 1)}
        b1 = {e.id: i for i, e in enumerate(rl.ordenar_b1(eventos), 1)}
        if len(b0) != len(eventos):
            raise ValueError(f"{p['par']}: id de evento repetido")
        with open(DESTINO / "eventos" / f"{p['par']}.jsonl", "w", encoding="utf-8") as f:
            for e in eventos:
                f.write(json.dumps({**e.para_dict(), "rank_b0": b0[e.id], "rank_b1": b1[e.id]},
                                   ensure_ascii=False) + "\n")
        resumo["pares"][p["par"]] = {
            "papel": p["papel"], "anterior": anterior.nome, "atual": atual.nome,
            "paginas": [anterior.paginas, atual.paginas], "eventos": len(eventos),
            "por_tipo": dict(Counter(f"{e.tipo}:{e.operacao}" for e in eventos)),
            "b1_nivel1": sum(e.nivel1 for e in eventos),
        }
        print(f"{p['par']:<32} {p['papel']:<6} {len(eventos):>6} eventos")
    (DESTINO / "resumo_eventos.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return 0


# --- C: desafiante pré-treinado e congelado (§3) -----------------------------------------

MODELO_C = "bge-m3:latest"
OLLAMA = "http://localhost:11434"
#: Âncoras semânticas do C, fixadas antes de qualquer rótulo. Descrevem as
#: mudanças de nota 2 da rubrica do CAND-02; não foram ajustadas a dado.
ANCORAS = (
    "revisão do guidance, das projeções ou das metas para o ano",
    "mudança de política contábil ou reapresentação de resultados de períodos anteriores",
    "alteração relevante no índice de Basileia, no capital principal ou na liquidez",
    "piora ou melhora relevante na inadimplência, no custo do crédito ou nas provisões",
    "mudança de perímetro: aquisição, venda ou consolidação de participação",
    "nova incerteza, risco regulatório, processo judicial ou contingência relevante",
    "mudança na política de dividendos, juros sobre capital próprio ou recompra de ações",
    "inversão de tendência: crescimento que virou queda, ou lucro que virou prejuízo",
    "mudança na definição ou na metodologia de cálculo de um indicador",
    "evento não recorrente relevante que afeta o resultado do trimestre",
)
TAMANHO_TEXTO_C = 600


def texto_c(ev: dict) -> str:
    """O que o C lê de um evento: a mudança, sem braço nem score."""
    if ev["tipo"] == "tabela":
        base = f"{ev['titulo']} — {ev['rotulo']}. Antes: {ev['antes']} Depois: {ev['depois']}"
    elif ev["operacao"] == "alteracao":
        base = f"Antes: {ev['antes']} Depois: {ev['depois']}"
    elif ev["operacao"] == "adicao":
        base = f"Novo trecho: {ev['depois']}"
    else:
        base = f"Trecho retirado: {ev['antes']}"
    return base[:TAMANHO_TEXTO_C]


def _ollama(rota: str, corpo: dict | None = None) -> dict:
    import urllib.request
    dados = None if corpo is None else json.dumps(corpo).encode()
    req = urllib.request.Request(f"{OLLAMA}{rota}", data=dados,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))


def digest_modelo_c() -> str:
    for m in _ollama("/api/tags")["models"]:
        if m["name"] == MODELO_C:
            return m["digest"]
    raise SystemExit(f"{MODELO_C} ausente no Ollama local")


def embedar(textos: list[str], lote: int = 64):
    import numpy as np
    vetores = []
    for i in range(0, len(textos), lote):
        r = _ollama("/api/embed", {"model": MODELO_C, "input": textos[i:i + lote]})
        vetores.extend(r["embeddings"])
    m = np.asarray(vetores, dtype="float32")
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def ler_eventos(par: str) -> list[dict]:
    return [json.loads(l) for l in open(DESTINO / "eventos" / f"{par}.jsonl", encoding="utf-8")]


def cmd_desafiante(_args) -> int:
    digest = digest_modelo_c()
    meta = {"modelo": MODELO_C, "digest": digest, "ancoras": ANCORAS,
            "tamanho_texto": TAMANHO_TEXTO_C,
            "script_sha256": sha256_arquivo(Path(__file__)),
            "redline_sha256": sha256_arquivo(RAIZ / "src" / "redline.py")}
    pasta = DESTINO / "desafiante"
    pasta.mkdir(parents=True, exist_ok=True)
    anterior = pasta / "meta.json"
    if anterior.exists() and json.loads(anterior.read_text())["digest"] != digest:
        raise SystemExit("o modelo do C mudou desde a execução anterior: apague a pasta e refaça")
    anterior.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    ancoras = embedar(list(ANCORAS))
    resumo = json.load(open(DESTINO / "resumo_eventos.json"))["pares"]
    # Treino primeiro: é ele que libera a rotulagem. A ordem não muda nenhum score.
    for par in sorted(resumo, key=lambda par: (resumo[par]["papel"] != "treino", par)):
        saida = pasta / f"{par}.jsonl"
        if saida.exists():
            continue
        inicio = time.time()
        eventos = ler_eventos(par)
        sims = embedar([texto_c(e) for e in eventos]) @ ancoras.T
        linhas = [{"id": e["id"], "sims": [round(float(s), 4) for s in v], "score_c": round(float(v.max()), 4),
                   "rank_b1": e["rank_b1"]} for e, v in zip(eventos, sims)]
        for i, l in enumerate(sorted(linhas, key=lambda l: (-l["score_c"], l["rank_b1"])), 1):
            l["rank_c"] = i
        temporario = saida.with_suffix(".tmp")
        temporario.write_text("".join(json.dumps(l) + "\n" for l in linhas), encoding="utf-8")
        temporario.replace(saida)
        print(f"{par}: {len(linhas)} eventos em {time.time() - inicio:.0f}s", flush=True)
    return 0


# --- pool e pacotes cegos (§4) -----------------------------------------------------------

TOPO_POR_BRACO = 20
ITENS_POR_PAR = 120


def ranks_do_braco(par: str, braco: str) -> dict[str, int]:
    if braco in ("b0", "b1"):
        return {e["id"]: e[f"rank_{braco}"] for e in ler_eventos(par)}
    if braco == "c":
        return {l["id"]: l["rank_c"] for l in map(json.loads, open(DESTINO / "desafiante" / f"{par}.jsonl"))}
    if braco == "m":
        return {l["id"]: l["rank_m"] for l in map(json.loads, open(DESTINO / "modelo" / "ranks" / f"{par}.jsonl"))}
    raise ValueError(braco)


def montar_pool(par: str, bracos: tuple[str, ...]) -> dict:
    """União do top-20 de cada braço, mais aleatórios até 120 (semente por par)."""
    import random
    eventos = ler_eventos(par)
    origem: dict[str, list[str]] = {}
    for braco in bracos:
        for i, r in ranks_do_braco(par, braco).items():
            if r <= TOPO_POR_BRACO:
                origem.setdefault(i, []).append(f"top20_{braco}")
    aleatorio = random.Random(f"{SEMENTE}:{par}:pool")
    resto = sorted(e["id"] for e in eventos if e["id"] not in origem)
    faltam = max(0, ITENS_POR_PAR - len(origem))
    for i in aleatorio.sample(resto, min(faltam, len(resto))):
        origem[i] = ["aleatorio"]
    ids = sorted(origem)
    aleatorio.shuffle(ids)
    return {"par": par, "bracos": list(bracos), "itens": {f"E{n:03d}": i for n, i in enumerate(ids, 1)},
            "origem": origem}


def item_do_pacote(item: str, ev: dict) -> dict:
    """O que o leitor vê: a mudança e onde ela está. Sem braço, score ou sinal do B1."""
    base = {"item": item, "operacao": ev["operacao"], "tipo": ev["tipo"],
            "pagina_anterior": ev["pagina_antes"], "pagina_atual": ev["pagina_depois"],
            "secao": ev["secao"], "trecho_anterior": ev["antes"], "trecho_atual": ev["depois"]}
    if ev["tipo"] == "tabela":
        base.update(titulo_da_tabela=ev["titulo"], unidade=ev["unidade"], rotulo_da_linha=ev["rotulo"],
                    colunas_anterior=ev["cabecalho_antes"], colunas_atual=ev["cabecalho_depois"])
    return base


def cmd_pool(args) -> int:
    papel = args.papel
    bracos = ("b0", "b1", "c") if papel == "treino" else ("b0", "b1", "c", "m")
    if papel == "teste" and not (DESTINO / "modelo" / "congelado.json").exists():
        raise SystemExit("o pool de teste só existe depois do M congelado (§4 e §7)")
    resumo = json.load(open(DESTINO / "resumo_eventos.json"))["pares"]
    (DESTINO / "pool" / papel).mkdir(parents=True, exist_ok=True)
    (DESTINO / "pacotes" / papel).mkdir(parents=True, exist_ok=True)
    for par, info in sorted(resumo.items()):
        if info["papel"] != papel:
            continue
        pool = montar_pool(par, bracos)
        destino_pool = DESTINO / "pool" / papel / f"{par}.json"
        if destino_pool.exists() and json.loads(destino_pool.read_text())["itens"] != pool["itens"]:
            raise SystemExit(f"{par}: o pool gravado difere do recalculado; nada foi sobrescrito")
        destino_pool.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
        por_id = {e["id"]: e for e in ler_eventos(par)}
        pacote = {"par": par, "documento_anterior": info["anterior"], "documento_atual": info["atual"],
                  "itens": [item_do_pacote(k, por_id[v]) for k, v in pool["itens"].items()]}
        (DESTINO / "pacotes" / papel / f"{par}.json").write_text(
            json.dumps(pacote, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{par}: {len(pool['itens'])} itens "
              f"({sum(1 for o in pool['origem'].values() if o == ['aleatorio'])} aleatórios)")
    return 0


# --- rubrica e leitores (§4) -------------------------------------------------------------

RUBRICA = """\
RUBRICA — prioridade de leitura de mudanças entre dois releases consecutivos (CAND-02)

Você é um analista de research de bancos. Cada item descreve uma possível mudança
entre o release ANTERIOR e o ATUAL do mesmo emissor. Julgue se um analista que já
leu o release anterior precisa ler esta mudança no atual.

Notas:
- 0 — rotina ou superfície: layout, período que rolou automaticamente (3T25 virou
  4T25), paráfrase equivalente, número atualizado sem mudar a leitura, ou mudança
  sem ação analítica. Movimento de texto, quebra ou fusão de bloco, cabeçalho,
  rodapé e ruído de OCR também são 0.
- 1 — conferir: muda fato, número, definição, escopo, causa, risco, incerteza ou
  qualificador que merece inspeção.
- 2 — leitura obrigatória: muda guidance, KPI relevante, tendência, sinal, ordem de
  grandeza, perímetro, política contábil, capital ou liquidez, risco de crédito,
  reapresentação, ou contradiz ou qualifica afirmação anterior.

Para nota 1 ou 2, dê o motivo principal: numero, definicao_escopo, contabilidade,
risco_incerteza, explicacao_causal, guidance, capital_liquidez, credito, segmento
ou outro. Para nota 2, dê a ação: verificar, atualizar_modelo ou investigar.
critico = true só para nota 2 cuja omissão num relatório de research seria erro grave.
julgavel = false só quando o OCR ou a estrutura impedem comparar com segurança
(nao_julgavel_ocr_ou_estrutura). Mudança que você só acha pouco importante é
nota 0, não julgavel = false.

Regras:
- Confira nos documentos, não só no trecho. O item pode ser artefato de extração:
  a linha existe sem mudança no outro documento, ou o trecho foi cortado. Nesse
  caso é nota 0, ou julgavel = false se a comparação não for segura.
- Número que mudou só porque o trimestre mudou é rotina, salvo se muda tendência,
  sinal ou ordem de grandeza, ou foge do padrão.
- Julgue cada item de forma independente. A ordem dos itens é aleatória.
- justificativa: no máximo 25 palavras, em português.

Formato de cada rótulo:
{"item": "E001", "nota": 0, "motivo": null, "acao": null, "critico": false,
 "julgavel": true, "justificativa": "..."}
"""
MOTIVOS = {"numero", "definicao_escopo", "contabilidade", "risco_incerteza", "explicacao_causal",
           "guidance", "capital_liquidez", "credito", "segmento", "outro"}
ACOES = {"verificar", "atualizar_modelo", "investigar"}


def validar_rotulo(r: dict) -> dict:
    """Um rótulo fora do contrato derruba a leitura: não vira nota por palpite."""
    if r.get("nota") not in (0, 1, 2) or not isinstance(r.get("item"), str):
        raise ValueError(f"rótulo inválido: {r}")
    if r["nota"] >= 1 and r.get("motivo") not in MOTIVOS:
        raise ValueError(f"motivo inválido para nota {r['nota']}: {r}")
    if r["nota"] == 2 and r.get("acao") not in ACOES:
        raise ValueError(f"nota 2 sem ação válida: {r}")
    if not isinstance(r.get("critico"), bool) or not isinstance(r.get("julgavel"), bool):
        raise ValueError(f"critico/julgavel não booleanos: {r}")
    if r["critico"] and r["nota"] != 2:
        raise ValueError(f"crítico sem nota 2: {r}")
    return {k: r.get(k) for k in ("item", "nota", "motivo", "acao", "critico", "julgavel", "justificativa")}


def cmd_rubrica(_args) -> int:
    (DESTINO / "rubrica.md").write_text(RUBRICA, encoding="utf-8")
    print(DESTINO / "rubrica.md")
    return 0


# --- leitor Gemini, com journal write-ahead e teto (§4) ----------------------------------

TETO_USD = 15.0
LOTE_GEMINI = 40
JOURNAL = DESTINO / "journal_gemini.jsonl"


def _journal(evento: dict) -> None:
    import os
    from datetime import datetime, timezone
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp_utc": datetime.now(timezone.utc).isoformat(), **evento},
                           ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def gasto_no_journal() -> float:
    """Conclusões pelo custo observado; intenção sem conclusão pela estimativa."""
    if not JOURNAL.exists():
        return 0.0
    intencoes, conclusoes = {}, {}
    for linha in JOURNAL.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            e = json.loads(linha)
            (intencoes if e["tipo"] == "intencao" else conclusoes)[e["call_id"]] = e
    gasto = 0.0
    for call_id, i in intencoes.items():
        c = conclusoes.get(call_id)
        gasto += c["custo_usd"] if c and c.get("custo_usd") is not None else i["estimativa_usd"]
    return gasto


def _documento_completo(nome: str) -> str:
    return (DESTINO / "docs" / f"{nome}.md").read_text(encoding="utf-8")


def cmd_rotular_gemini(args) -> int:
    if not args.permitir_api_paga:
        raise SystemExit("chamada paga exige --permitir-api-paga (opt-in do responsável em 28/09)")
    from src.config import carregar_config
    from src.geracao import LLMGemini
    cfg = carregar_config()
    llm = LLMGemini(cfg)
    papel = args.papel
    pasta = DESTINO / "rotulos" / "gemini" / papel
    pasta.mkdir(parents=True, exist_ok=True)
    for arquivo in sorted((DESTINO / "pacotes" / papel).glob("*.json")):
        pacote = json.loads(arquivo.read_text(encoding="utf-8"))
        saida = pasta / f"{pacote['par']}.jsonl"
        feitos = {json.loads(l)["item"] for l in open(saida, encoding="utf-8")} if saida.exists() else set()
        pendentes = [i for i in pacote["itens"] if i["item"] not in feitos]
        documentos = (f"DOCUMENTO ANTERIOR ({pacote['documento_anterior']}):\n"
                      f"{_documento_completo(pacote['documento_anterior'])}\n\n"
                      f"DOCUMENTO ATUAL ({pacote['documento_atual']}):\n"
                      f"{_documento_completo(pacote['documento_atual'])}\n\n")
        for inicio in range(0, len(pendentes), LOTE_GEMINI):
            lote = pendentes[inicio:inicio + LOTE_GEMINI]
            usuario = (documentos + "ITENS A JULGAR (JSON):\n"
                       + json.dumps(lote, ensure_ascii=False)
                       + '\n\nResponda só com JSON: {"rotulos": [ ...um rótulo por item... ]}')
            estimativa = llm.estimar_custo_maximo(RUBRICA, usuario)
            if gasto_no_journal() + estimativa > TETO_USD:
                raise SystemExit(f"teto de US$ {TETO_USD} seria ultrapassado; parado antes da chamada")
            call_id = hashlib.sha256(f"{pacote['par']}|{papel}|{[i['item'] for i in lote]}".encode()).hexdigest()[:16]
            _journal({"tipo": "intencao", "call_id": call_id, "par": pacote["par"], "papel": papel,
                      "itens": len(lote), "estimativa_usd": round(estimativa, 6)})
            try:
                resposta = llm.gerar(RUBRICA, usuario, temperatura=0.0)
            except Exception as erro:  # a chamada pode ter sido cobrada: fica a estimativa
                _journal({"tipo": "conclusao", "call_id": call_id, "ok": False,
                          "erro": type(erro).__name__, "custo_usd": None})
                raise
            _journal({"tipo": "conclusao", "call_id": call_id, "ok": True,
                      "custo_usd": round(resposta.uso.custo_usd, 6),
                      "tokens_entrada": resposta.uso.tokens_entrada,
                      "tokens_saida": resposta.uso.tokens_saida, "modelo": resposta.modelo})
            rotulos = json.loads(resposta.texto)["rotulos"]
            esperados = {i["item"] for i in lote}
            validos = [validar_rotulo(r) for r in rotulos]
            if {r["item"] for r in validos} != esperados or len(validos) != len(esperados):
                raise ValueError(f"{pacote['par']}: a resposta não cobre exatamente os itens do lote")
            with open(saida, "a", encoding="utf-8") as f:
                for r in validos:
                    f.write(json.dumps({**r, "leitor": resposta.modelo, "tipo_leitor": "ia"},
                                       ensure_ascii=False) + "\n")
            print(f"{pacote['par']}: +{len(validos)} (gasto acumulado US$ {gasto_no_journal():.4f})",
                  flush=True)
    return 0


# --- consolidação dos dois leitores ------------------------------------------------------

LEITORES = ("claude", "gemini")


def ler_rotulos(leitor: str, papel: str, par: str) -> dict[str, dict]:
    caminho = DESTINO / "rotulos" / leitor / papel / f"{par}.jsonl"
    if not caminho.exists():
        return {}
    saida = {}
    for linha in open(caminho, encoding="utf-8"):
        r = validar_rotulo(json.loads(linha))
        if r["item"] in saida:
            raise ValueError(f"{leitor}/{papel}/{par}: item {r['item']} rotulado duas vezes")
        saida[r["item"]] = r
    return saida


def consolidar(papel: str, par: str) -> dict[str, dict]:
    """evento → notas dos dois leitores, ganho médio e marcas. Leitura
    incompleta levanta: nota que falta não vira zero."""
    pool = json.loads((DESTINO / "pool" / papel / f"{par}.json").read_text(encoding="utf-8"))
    leituras = {l: ler_rotulos(l, papel, par) for l in LEITORES}
    for leitor, rotulos in leituras.items():
        faltam = set(pool["itens"]) - set(rotulos)
        if faltam:
            raise ValueError(f"{leitor}/{papel}/{par}: {len(faltam)} itens sem rótulo")
    saida = {}
    for item, evento in pool["itens"].items():
        a, b = (leituras[l][item] for l in LEITORES)
        saida[evento] = {
            "item": item, "notas": [a["nota"], b["nota"]],
            "julgavel": a["julgavel"] and b["julgavel"],
            "nota_final": (a["nota"] + b["nota"]) / 2,
            "ganho": (rl.GANHO[a["nota"]] + rl.GANHO[b["nota"]]) / 2,
            "critico": a["critico"] and b["critico"], "origem": pool["origem"][evento],
        }
    return saida


# --- M: o primeiro treino (§3) -----------------------------------------------------------

HIPERPARAMETROS_M = {"max_iter": 200, "learning_rate": 0.05, "max_leaf_nodes": 15,
                     "min_samples_leaf": 20, "l2_regularization": 1.0, "random_state": SEMENTE}


def features(ev: dict, c: dict) -> list[float]:
    """Forma do evento, sinais do B1 e similaridades do C. Nada do rótulo."""
    import math
    mudancas = ev["mudancas_numericas"]
    bps = [m["bp"] for m in mudancas if m.get("bp") is not None]
    rels = [min(m["relativa"], 10.0) for m in mudancas if m.get("relativa") is not None]
    return [
        ev["operacao"] == "alteracao", ev["operacao"] == "adicao", ev["operacao"] == "remocao",
        ev["tipo"] == "tabela", ev["b1_nivel1"], ev["b1_nivel2"], ev["b1_nivel3"],
        len(ev["categorias"]), *[nome in ev["categorias"] for nome in sorted(rl.CATEGORIAS)],
        ev["reapresentacao"], ev["negacao_modal"], ev["moeda"],
        max(bps, default=0.0), max(rels, default=0.0),
        any(m.get("sinal") for m in mudancas), any(m.get("ordem_de_grandeza") for m in mudancas),
        len(mudancas), math.log1p(ev["massa"]), ev["distancia"], ev["pagina_relativa"],
        math.log1p((ev["pagina_depois"] or ev["pagina_antes"] or 0)),
        math.log1p(len(ev["antes"]) + len(ev["depois"])),
        *c["sims"], c["score_c"],
    ]


def _c_do_par(par: str) -> dict[str, dict]:
    return {l["id"]: l for l in map(json.loads, open(DESTINO / "desafiante" / f"{par}.jsonl"))}


def cmd_treinar(_args) -> int:
    import pickle

    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor

    pasta = DESTINO / "modelo"
    if (pasta / "congelado.json").exists():
        raise SystemExit("o M já está congelado; treinar de novo é outro piloto (§7)")
    resumo = json.load(open(DESTINO / "resumo_eventos.json"))["pares"]
    X, y, n_por_par = [], [], {}
    for par, info in sorted(resumo.items()):
        if info["papel"] != "treino":
            continue
        rotulos = consolidar("treino", par)
        eventos = {e["id"]: e for e in ler_eventos(par)}
        c = _c_do_par(par)
        usados = [(i, r) for i, r in rotulos.items() if r["julgavel"]]
        n_por_par[par] = len(usados)
        for i, r in usados:
            X.append(features(eventos[i], c[i]))
            y.append(r["ganho"])
    modelo = HistGradientBoostingRegressor(**HIPERPARAMETROS_M).fit(np.asarray(X, float), np.asarray(y))
    (pasta / "ranks").mkdir(parents=True, exist_ok=True)
    with open(pasta / "m.pkl", "wb") as f:
        pickle.dump(modelo, f)
    for par, info in sorted(resumo.items()):
        if info["papel"] != "teste":
            continue
        eventos = ler_eventos(par)
        c = _c_do_par(par)
        previsto = modelo.predict(np.asarray([features(e, c[e["id"]]) for e in eventos], float))
        ordem = sorted(zip(eventos, previsto), key=lambda t: (-t[1], t[0]["rank_b1"]))
        with open(pasta / "ranks" / f"{par}.jsonl", "w", encoding="utf-8") as f:
            for n, (e, p) in enumerate(ordem, 1):
                f.write(json.dumps({"id": e["id"], "previsto": round(float(p), 5), "rank_m": n}) + "\n")
    congelado = {"hiperparametros": HIPERPARAMETROS_M, "observacoes_de_treino": len(y),
                 "observacoes_por_par": n_por_par, "ganho_medio_treino": round(float(np.mean(y)), 4),
                 "m_pkl_sha256": sha256_arquivo(pasta / "m.pkl"),
                 "script_sha256": sha256_arquivo(Path(__file__)),
                 "redline_sha256": sha256_arquivo(RAIZ / "src" / "redline.py")}
    (pasta / "congelado.json").write_text(json.dumps(congelado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(congelado, indent=2, ensure_ascii=False))
    return 0


# --- avaliação e decisão (§5) ------------------------------------------------------------

LIMIAR_ALFA = 0.67
MAX_NAO_JULGAVEL = 0.05
MIN_NOTA_2 = 30
TETO_B1 = 0.95
DELTA_NDCG10 = 0.10
DELTA_NDCG20 = 0.05
MIN_PARES_VENCIDOS = 7


def decidir(m: dict) -> tuple[str, str]:
    """As quatro paradas do §5, na ordem. Recebe só números já medidos.

    `not (x >= limiar)` e não `x < limiar`: α sai NaN sem dado, e NaN < 0,67 é
    falso — a parada aprovaria por ausência de medição (AGENTS.md §4.4, regra 4)."""
    alfa = m["alfa"]
    if alfa is None or not (alfa >= LIMIAR_ALFA):
        return "INDECIDIVEL", f"parada 1: α = {alfa}, não ≥ {LIMIAR_ALFA}"
    if m["fracao_nao_julgavel"] > MAX_NAO_JULGAVEL:
        return "INDECIDIVEL", f"parada 1: não julgáveis {m['fracao_nao_julgavel']:.3f} > {MAX_NAO_JULGAVEL}"
    if m["eventos_nota_2"] < MIN_NOTA_2:
        return "INDECIDIVEL", f"parada 2: {m['eventos_nota_2']} eventos com nota final ≥ 1,5 < {MIN_NOTA_2}"
    medidas = [m["macro"][b][k] for b in ("b1", "m") for k in ("ndcg10", "ndcg20")]
    if any(v is None or v != v for v in medidas):
        return "INDECIDIVEL", "nDCG macro ausente: nenhum par com ganho positivo"
    if m["macro"]["b1"]["ndcg10"] >= TETO_B1:
        return "INVIAVEL", f"parada 3: B1 com nDCG@10 {m['macro']['b1']['ndcg10']:.3f} ≥ {TETO_B1}"
    d10 = m["macro"]["m"]["ndcg10"] - m["macro"]["b1"]["ndcg10"]
    d20 = m["macro"]["m"]["ndcg20"] - m["macro"]["b1"]["ndcg20"]
    falhas = []
    if d10 < DELTA_NDCG10:
        falhas.append(f"Δ nDCG@10 {d10:+.3f} < {DELTA_NDCG10}")
    if d20 < DELTA_NDCG20:
        falhas.append(f"Δ nDCG@20 {d20:+.3f} < {DELTA_NDCG20}")
    if m["pares_vencidos_m_sobre_b1"] < MIN_PARES_VENCIDOS:
        falhas.append(f"M vence o B1 em {m['pares_vencidos_m_sobre_b1']} pares < {MIN_PARES_VENCIDOS}")
    if m["criticos_top20"]["m"] < m["criticos_top20"]["b1"]:
        falhas.append(f"críticos no top-20: M {m['criticos_top20']['m']} < B1 {m['criticos_top20']['b1']}")
    if falhas:
        return "INVIAVEL", "parada 4: " + "; ".join(falhas)
    return "PROMISSOR", "M vence o B1 nas três condições; falta a conferência humana (§6)"


def medir(papel: str, bracos: tuple[str, ...]) -> dict:
    from scripts.auditar_cand02_redline import alpha_krippendorff_ordinal

    resumo = json.load(open(DESTINO / "resumo_eventos.json"))["pares"]
    pares_notas, por_par, total, nao_julgaveis, nota2 = [], {}, 0, 0, 0
    criticos = {b: 0 for b in bracos}
    for par, info in sorted(resumo.items()):
        if info["papel"] != papel:
            continue
        rot = consolidar(papel, par)
        total += len(rot)
        nao_julgaveis += sum(not r["julgavel"] for r in rot.values())
        julgados = {i: r for i, r in rot.items() if r["julgavel"]}
        pares_notas.extend(tuple(r["notas"]) for r in julgados.values())
        nota2 += sum(r["nota_final"] >= 1.5 for r in julgados.values())
        ganhos = {i: r["ganho"] for i, r in julgados.items()}
        excluidos = set(rot) - set(julgados)
        por_par[par] = {}
        for b in bracos:
            ordem = [i for i, _ in sorted(ranks_do_braco(par, b).items(), key=lambda t: t[1])
                     if i not in excluidos]
            por_par[par][b] = {"ndcg10": rl.ndcg(ordem, ganhos, 10), "ndcg20": rl.ndcg(ordem, ganhos, 20)}
            criticos[b] += sum(1 for i in ordem[:20] if julgados.get(i, {}).get("critico"))
    macro = {}
    for b in bracos:
        for k in ("ndcg10", "ndcg20"):
            valores = [v[b][k] for v in por_par.values() if v[b][k] is not None]
            macro.setdefault(b, {})[k] = sum(valores) / len(valores) if valores else None
    vencidos = sum(1 for v in por_par.values()
                   if "m" in v and v["m"]["ndcg10"] is not None and v["b1"]["ndcg10"] is not None
                   and v["m"]["ndcg10"] > v["b1"]["ndcg10"])
    alfa = alpha_krippendorff_ordinal(pares_notas) if pares_notas else None
    return {"papel": papel, "itens": total, "alfa": None if alfa is None or alfa != alfa else alfa,
            "fracao_nao_julgavel": nao_julgaveis / total if total else 1.0, "eventos_nota_2": nota2,
            "macro": macro, "por_par": por_par, "pares_vencidos_m_sobre_b1": vencidos,
            "criticos_top20": criticos}


def cmd_avaliar(args) -> int:
    papel = args.papel
    bracos = ("b0", "b1", "c", "m") if papel == "teste" else ("b0", "b1", "c")
    m = medir(papel, bracos)
    if papel == "teste":
        m["veredito"], m["motivo"] = decidir(m)
    destino = DESTINO / f"resultado_{papel}.json"
    destino.write_text(json.dumps(m, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in m.items() if k != "por_par"}, ensure_ascii=False, indent=2, default=str))
    return 0


# --- conferência humana, só se PROMISSOR (§6) ----------------------------------------------

AMOSTRA_HUMANA = 60


def sortear_amostra_humana(pares_do_teste: list[str]) -> list[tuple[str, str]]:
    """60 itens do pool de teste, estratificados por par (7 ou 8 por par),
    semente fixa. Devolve (par, item) em ordem aleatória."""
    import random
    base, extra = divmod(AMOSTRA_HUMANA, len(pares_do_teste))
    escolhidos = []
    for n, par in enumerate(sorted(pares_do_teste)):
        pool = json.loads((DESTINO / "pool" / "teste" / f"{par}.json").read_text(encoding="utf-8"))
        aleatorio = random.Random(f"{SEMENTE}:humana:{par}")
        k = base + (1 if n < extra else 0)
        escolhidos.extend((par, item) for item in aleatorio.sample(sorted(pool["itens"]), k))
    random.Random(f"{SEMENTE}:humana:ordem").shuffle(escolhidos)
    return escolhidos


def cmd_amostra_humana(_args) -> int:
    resultado = DESTINO / "resultado_teste.json"
    if not resultado.exists() or json.loads(resultado.read_text())["veredito"] != "PROMISSOR":
        raise SystemExit("a conferência humana só existe se o veredito do teste for PROMISSOR (§6)")
    resumo = json.load(open(DESTINO / "resumo_eventos.json"))["pares"]
    pares_teste = [par for par, info in resumo.items() if info["papel"] == "teste"]
    pasta = DESTINO / "humana"
    pasta.mkdir(parents=True, exist_ok=True)
    itens, mapa = [], {}
    for n, (par, item) in enumerate(sortear_amostra_humana(pares_teste), 1):
        pacote = json.loads((DESTINO / "pacotes" / "teste" / f"{par}.json").read_text(encoding="utf-8"))
        conteudo = next(i for i in pacote["itens"] if i["item"] == item)
        novo = f"H{n:02d}"
        itens.append({**conteudo, "item": novo, "documento_anterior": pacote["documento_anterior"],
                      "documento_atual": pacote["documento_atual"]})
        mapa[novo] = {"par": par, "item": item}
    (pasta / "pacote.json").write_text(json.dumps({"itens": itens}, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    (pasta / "mapa.json").write_text(json.dumps(mapa, indent=1), encoding="utf-8")
    print(f"{len(itens)} itens em {pasta / 'pacote.json'}; rótulos em {pasta / 'rotulos.jsonl'}")
    return 0


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("eventos")
    sub.add_parser("desafiante")
    sub.add_parser("rubrica")
    p = sub.add_parser("pool")
    p.add_argument("--papel", choices=("treino", "teste"), required=True)
    g = sub.add_parser("rotular-gemini")
    g.add_argument("--papel", choices=("treino", "teste"), required=True)
    g.add_argument("--permitir-api-paga", action="store_true")
    sub.add_parser("treinar")
    a = sub.add_parser("avaliar")
    a.add_argument("--papel", choices=("treino", "teste"), required=True)
    sub.add_parser("amostra-humana")
    args = parser.parse_args(argv)
    return {"eventos": cmd_eventos, "desafiante": cmd_desafiante, "rubrica": cmd_rubrica,
            "pool": cmd_pool, "rotular-gemini": cmd_rotular_gemini, "treinar": cmd_treinar,
            "avaliar": cmd_avaliar, "amostra-humana": cmd_amostra_humana}[args.comando](args)


if __name__ == "__main__":
    sys.exit(principal())
