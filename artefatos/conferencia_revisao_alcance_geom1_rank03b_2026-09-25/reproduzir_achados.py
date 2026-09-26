"""Contraprovas da revisão de 25/09; NÃO são correções ou testes do modelo.

Somente números sintéticos. A contraprova de pin usa cópia temporária do
inventário publicado e um pin vazio, sem ler XML/FCO nem mudar entradas reais.
O sucesso deste script significa que os defeitos foram REPRODUZIDOS.
Execute da raiz: PYTHONPATH=. .venv/bin/python <este arquivo>
"""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from scripts import conferir_alcance_geom1_rank03b as c


def parser():
    casos = [
        ("prefixo_de_numero_malformado", "Total 1.234.5678", "1234567"),
        ("menos_com_dois_espacos", "Total -  1.234", "1234"),
        ("parenteses_com_moeda", "Total (R$ 1.234)", "1234"),
    ]
    resultados = []
    for nome, texto, valor in casos:
        achados = c.ocorrencias([texto], {"sintetico": Decimal(valor)}, por_modulo=False)
        reproduzido = bool(achados["sintetico"])
        assert reproduzido, f"Contraprova deixou de reproduzir: {nome}"
        resultados.append({"caso": nome, "correspondencia_positiva_indevida": reproduzido})
    # Controles: o número positivo inteiro casa; negativo simples não casa.
    assert c.ocorrencias(["Total 1.234"], {"a": Decimal(1234)}, por_modulo=False)["a"]
    assert not c.ocorrencias(["Total -1.234"], {"a": Decimal(1234)}, por_modulo=False)["a"]
    return resultados


def autoverificacao():
    resultados = []
    for texto, valor in [
        ("1.234.567,00", "1234567"),
        ("1234567.00", "1234567"),
        ("1 234 567,00", "1234567"),
        ("1.234.567,50", "1234567.5"),
    ]:
        for local in ("texto", "chave"):
            payload = {"nota": texto} if local == "texto" else {texto: True}
            try:
                c.verificar_sem_valores(payload, [Decimal(valor)])
            except c.VazamentoDeValor:
                passou = False
            else:
                passou = True
            assert passou, f"Contraprova deixou de reproduzir: {local}/{texto}"
            resultados.append({"numero_inventado": texto, "local": local, "passou_indevidamente": passou})
    # Controle: forma já contemplada continua sendo barrada.
    try:
        c.verificar_sem_valores({"nota": "1.234.567"}, [Decimal(1234567)])
    except c.VazamentoDeValor:
        pass
    else:
        raise AssertionError("Controle negativo da autoverificação não barrou")
    return resultados


def pin_vazio():
    base_real = c.BASE
    publicado = json.loads((c.DESTINO / "pin_revisao.json").read_text())
    fontes_fixadas = len(publicado["fontes"])
    assert fontes_fixadas == 2
    # Destino temporário novo: nenhum pin ou resultado publicado é regravado.
    with tempfile.TemporaryDirectory(prefix="contraprova-pin-geom1-") as pasta:
        base = Path(pasta)
        shutil.copyfile(base_real / "inventario_textual.json", base / "inventario_textual.json")
        (base / "pin.json").write_text(json.dumps({"fontes": []}))
        sha_vazio = hashlib.sha256((base / "pin.json").read_bytes()).hexdigest()
        assert sha_vazio != publicado["pin_alcance_sha256"]
        with patch.object(c, "BASE", base):
            resultado = c.reconferir_publicados(base / "reconferencia.json")
        assert not resultado["documentos"]
        assert all(resultado["autoverificacao_estrita_nos_publicados"].values())
        assert len(resultado["protegidos"]) == 7 and all(resultado["protegidos"].values())
        return {
            "fontes_fixadas_no_pin_verificado": fontes_fixadas,
            "pin_de_fontes_tem_hash_diferente": True,
            "documentos_examinados": len(resultado["documentos"]),
            "autoverificacao": resultado["autoverificacao_estrita_nos_publicados"],
            "sete_protegidos_conferidos": True,
            "saida_foi_gravada": (base / "reconferencia.json").exists(),
        }


if __name__ == "__main__":
    print(json.dumps({
        "sentido_do_resultado": "defeitos_reproduzidos_nao_aprovacao",
        "codigo_sha256": {p: c.rad.sha256(c.rad.RAIZ / p) for p in c.CODIGO},
        "RAG01_pin_nao_vinculado": pin_vazio(),
        "RAG02_parser": parser(),
        "RAG03_autoverificacao": autoverificacao(),
        "sem_valores_reais_de_fco": True,
        "sem_alteracao_de_entradas": True,
    }, ensure_ascii=False, indent=2))
