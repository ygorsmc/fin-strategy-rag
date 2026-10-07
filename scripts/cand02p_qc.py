"""Controle de qualidade dos rótulos do leitor Claude no CAND-02-P (v3 em diante).

Por par rotulado, três verificações:
- contrato e completude, pelo próprio consolidador do piloto;
- distribuição de notas, para comparar com os rótulos herdados;
- acesso: as chamadas de ferramenta da transcrição do leitor, conferidas contra
  o que ele pode abrir (pacote, rubrica, instruções, os dois documentos do par e
  o próprio arquivo de saída). Comandos Bash são lidos acompanhando o `cd`,
  porque no v2 foi um `grep ... bradesco_release_*.md` relativo que expôs um
  documento de teste, e um filtro só por caminho absoluto não o via.

E a medida da releitura cega (declaração em `artefatos/cand02p_v3/reteste/`).

    python -m scripts.cand02p_qc --piloto v3 rotulos teste PAR [--transcricao F]
    python -m scripts.cand02p_qc --piloto v3 reteste PAR [PAR ...]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import cand02p_piloto as p  # noqa: E402

LEITOR_RETESTE = "claude_reteste"
_ARQUIVOISH = re.compile(r"[\w./*?~-]*[\w*?-]\.(?:md|jsonl|json|csv|py|txt|pkl)\b|[\w.~-]*/[\w./*?-]+")
_RASCUNHO = "/tmp/"


def permitidos(papel: str, par: str, leitor: str = "claude") -> set[str]:
    pk = json.loads((p.DESTINO / "pacotes" / papel / f"{par}.json").read_text(encoding="utf-8"))
    d = p.DESTINO
    return {str(d / "instrucoes_leitor_claude.md"), str(d / "rubrica.md"),
            str(d / "pacotes" / papel / f"{par}.json"),
            str(d / "docs" / f"{pk['documento_anterior']}.md"), str(d / "docs" / f"{pk['documento_atual']}.md"),
            str(d / "rotulos" / leitor / papel / f"{par}.jsonl")}


def _abs(caminho: str, cwd: Path = RAIZ) -> str:
    c = Path(caminho)
    return str(c if c.is_absolute() else cwd / c).replace("/./", "/")


def estranhos_no_bash(cmd: str, ok: set[str], raiz: Path = RAIZ) -> list[str]:
    """Caminhos citados num comando, resolvidos contra o último `cd`. Marca
    curinga, listagem e qualquer arquivo do repositório fora do permitido."""
    pastas_ok = {str(Path(x).parent) for x in ok}
    cwd, achados = raiz, []
    for m in re.finditer(r"(?:^|[;&|\n]\s*)(ls|find|tree)\b([^;&|\n]*)", cmd):
        alvos = [_abs(t, cwd) for t in m.group(2).split() if not t.startswith("-") and not t.startswith("2>")]
        if not alvos or any(a not in ok for a in alvos):
            achados.append(f"listagem: {m.group(1)}{m.group(2)[:80]}")
    for trecho in re.split(r"&&|;|\n", cmd):
        mcd = re.match(r"\s*cd\s+(\S+)", trecho)
        if mcd:
            cwd = Path(_abs(mcd.group(1), cwd))
            continue
        for tok in _ARQUIVOISH.findall(trecho):
            if tok.startswith(_RASCUNHO) or tok.startswith(("http", "//")):
                continue
            if "*" in tok or "?" in tok:
                achados.append(f"curinga: {tok}")
                continue
            alvo = _abs(tok, cwd)
            if alvo.startswith(str(raiz)) and alvo not in ok and alvo.rstrip("/") not in pastas_ok:
                achados.append(f"fora: {Path(alvo).relative_to(raiz)}")
    return sorted(set(achados))


def auditar_acesso(transcricao: Path, papel: str, par: str, leitor: str = "claude") -> dict:
    ok = permitidos(papel, par, leitor)
    fora, bash, ferramentas = [], [], Counter()
    for linha in open(transcricao, encoding="utf-8"):
        try:
            conteudo = (json.loads(linha).get("message") or {}).get("content")
        except json.JSONDecodeError:
            continue
        for b in conteudo if isinstance(conteudo, list) else []:
            if b.get("type") != "tool_use":
                continue
            nome, ent = b.get("name"), b.get("input", {})
            ferramentas[nome] += 1
            if nome in ("Read", "Write", "Edit"):
                if _abs(ent.get("file_path", "")) not in ok:
                    fora.append(f"{nome} {ent.get('file_path')}")
            elif nome == "Grep":
                alvo = ent.get("path") or "(raiz do repositório)"
                if ent.get("glob") or "*" in alvo or _abs(alvo) not in ok:
                    fora.append(f"Grep path={ent.get('path')} glob={ent.get('glob')}")
            elif nome == "Bash":
                estranhos = estranhos_no_bash(ent.get("command", ""), ok)
                if estranhos:
                    bash.append((ent["command"][:110].replace("\n", " "), estranhos))
            elif nome not in ("TodoWrite", "SubagentHandback"):
                fora.append(f"{nome} {json.dumps(ent, ensure_ascii=False)[:120]}")
    return {"ferramentas": dict(ferramentas), "fora_do_permitido": fora, "bash_com_caminho_estranho": bash,
            "cita_primeira_leitura": leitor != "claude"
            and f"rotulos/claude/{papel}/{par}" in Path(transcricao).read_text(encoding="utf-8")}


def conferir_rotulos(papel: str, par: str) -> dict:
    p.consolidar(papel, par)  # levanta se faltar item ou violar o contrato
    rot = p.ler_rotulos("claude", papel, par)
    n, c = len(rot), Counter(r["nota"] for r in rot.values())
    crit = sum(r["critico"] for r in rot.values())
    return {"itens": n, "nota0": c[0], "nota1": c[1], "nota2": c[2],
            "frac": {k: round(v / n, 3) for k, v in (("nota0", c[0]), ("nota1", c[1]), ("nota2", c[2]), ("crit", crit))},
            "nao_julgaveis": sum(not r["julgavel"] for r in rot.values()), "criticos": crit,
            "justificativas_longas": sum(len((r.get("justificativa") or "").split()) > 25 for r in rot.values()),
            "motivos": dict(Counter(r["motivo"] for r in rot.values() if r["nota"] > 0).most_common())}


def amostra(papel: str, par: str, n2: int = 6, n0: int = 3) -> None:
    """Itens para conferência à mão: notas 2 e alterações com nota 0, sorteados."""
    pk = {i["item"]: i for i in json.loads((p.DESTINO / "pacotes" / papel / f"{par}.json").read_text())["itens"]}
    rot = p.ler_rotulos("claude", papel, par)
    al = random.Random(f"qc:{par}")
    dois = [r for r in rot.values() if r["nota"] == 2]
    zeros = [r for r in rot.values() if r["nota"] == 0 and pk[r["item"]]["operacao"] == "alteracao"]
    for r in al.sample(dois, min(n2, len(dois))) + al.sample(zeros, min(n0, len(zeros))):
        it = pk[r["item"]]
        print(f"--- {r['item']} nota={r['nota']} crit={r['critico']} {r['motivo']}/{r['acao']} | {it['tipo']}/{it['operacao']}")
        print("   A:", (it["trecho_anterior"] or "")[:200].replace("\n", " "))
        print("   D:", (it["trecho_atual"] or "")[:200].replace("\n", " "))
        print("   J:", r["justificativa"])


def medir_reteste(par: str, papel: str = "treino") -> dict:
    from scripts.auditar_cand02_redline import alpha_krippendorff_ordinal

    a, b = p.ler_rotulos("claude", papel, par), p.ler_rotulos(LEITOR_RETESTE, papel, par)
    if not a or set(a) != set(b):
        raise SystemExit(f"{par}: as duas leituras não cobrem os mesmos itens ({len(a)} × {len(b)})")
    pares = [(a[i]["nota"], b[i]["nota"]) for i in sorted(a) if a[i]["julgavel"] and b[i]["julgavel"]]
    return {"par": par, "itens": len(pares), "alfa_ordinal": round(alpha_krippendorff_ordinal(pares), 4),
            "acordo_exato": round(sum(x == y for x, y in pares) / len(pares), 4),
            "acordo_nota_ge_1": round(sum((x >= 1) == (y >= 1) for x, y in pares) / len(pares), 4),
            "acordo_nota_2": round(sum((x == 2) == (y == 2) for x, y in pares) / len(pares), 4),
            "nota2": {"primeira": sum(x == 2 for x, _ in pares), "releitura": sum(y == 2 for _, y in pares)},
            "confusao_primeira_x_releitura": {f"{x}->{y}": n for (x, y), n in sorted(Counter(pares).items())},
            "criticos": {"primeira": sum(r["critico"] for r in a.values()),
                         "releitura": sum(r["critico"] for r in b.values())}}


def principal(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--piloto", choices=sorted(p.PILOTOS), default="v3")
    sub = ap.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("rotulos")
    r.add_argument("papel", choices=("treino", "teste"))
    r.add_argument("par")
    r.add_argument("--transcricao", type=Path)
    r.add_argument("--leitor", default="claude")
    t = sub.add_parser("reteste")
    t.add_argument("pares", nargs="+")
    args = ap.parse_args(argv)
    p.configurar(args.piloto)
    if args.comando == "reteste":
        saida = {par: medir_reteste(par) for par in args.pares}
        print(json.dumps(saida, ensure_ascii=False, indent=1))
        (p.DESTINO / "reteste" / "resultado.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1),
                                                             encoding="utf-8")
        return 0
    if args.leitor == "claude":
        print(json.dumps(conferir_rotulos(args.papel, args.par), ensure_ascii=False))
    if args.transcricao:
        a = auditar_acesso(args.transcricao, args.papel, args.par, args.leitor)
        print("ferramentas:", a["ferramentas"], "| fora:", a["fora_do_permitido"],
              "| cita a primeira leitura:", a["cita_primeira_leitura"])
        for cmd, est in a["bash_com_caminho_estranho"]:
            print("   bash:", est, "<-", cmd)
    if args.leitor == "claude":
        amostra(args.papel, args.par)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
