"""Contraprovas sintéticas e contexto documental de ESC-0029; sem y real."""
import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from scripts import adjudicar_escala_rank03b as adj
from scripts import fonte_rad_cvm as rad


def sintetico(linha):
    # R$ 900.000 de caixa aparece como 900 sob um cabeçalho de milhares.
    cab = "(valores expressos em milhares de reais)\nBalanço consolidado em 30 de setembro de 2025\n"
    f = rad.Formulario(
        "sintetico", "1", {}, [("1.01.01", None, date(2025, 9, 30), 900000.0)],
        anexos=[(0, [cab + linha])], grupos_anexos={0: "193"},
    )
    r = adj.adjudicar_formulario(f, "UNIDADE", "2025-09-30")
    return {k: r[k] for k in ("veredito", "escala_do_formulario", "numerica")}


saida = {
    "controle_contas_em_linhas_separadas": sintetico(
        "Caixa e equivalentes de caixa 900\nFornecedores 900.000"),
    "outra_conta_na_mesma_linha": sintetico(
        "Caixa e equivalentes de caixa 900             Fornecedores 900.000"),
}
assert saida["controle_contas_em_linhas_separadas"]["veredito"] == "indecidivel"
assert saida["outra_conta_na_mesma_linha"]["escala_do_formulario"] == "MIL"
manifesto = Path("corpus/cvm/painel_pesquisa_rank03b/correcoes_escala.csv")
r = next(r for r in csv.DictReader(manifesto.open()) if r["id_doc"] == "76468")
pacote = Path("artefatos/painel_pesquisa_rank03b/rad/brutos/76468.zip")
digest = hashlib.sha256(pacote.read_bytes()).hexdigest()
assert digest == r["sha256_pacote"]
f = rad.ler(pacote, grupos=rad.GRUPOS_NOTAS)
pagina = dict(f.anexos)[2][11]
linhas = pagina.splitlines()
posicao = next(i for i, l in enumerate(linhas) if "ajuste de variação cambial" in rad._normalizar(l))
contexto = "\n".join(linhas[max(0, posicao - 9):posicao + 4])
contexto = re.sub(r"\d[\d.,]*", "[número omitido]", contexto)
novo = adj.adjudicar_formulario(f, r["escala_declarada"], r["dt_refer"])
saida["esc_0029"] = {
    "cd_cvm": r["cd_cvm"], "id_doc": r["id_doc"], "dt_refer": r["dt_refer"],
    "sha256_pacote": digest, "anexo_indice": 2, "pagina_do_anexo": 12,
    "contexto_mascarado": contexto,
    "veredito_reproduzido": novo["veredito"],
    "numerica_reproduzida": novo["numerica"],
    "evidencia_publicada": json.loads(r["evidencia_numerica"]),
    "erro_no_valor_monetario_real_demonstrado": False,
}
print(json.dumps(saida, ensure_ascii=False, indent=2))
