"""Fixtures exclusivamente sintéticas dos contratos CRF-01 a CRF-03."""
from datetime import date

from scripts import fonte_rad_cvm as rad


def prova_v4(dt="2025-09-30"):
    return {"regra": "v4", "conta": "1", "forma": "bruto", "anexo": 0,
            "pagina": 1, "linha": 4, "coluna": 1, "dt_fim": dt,
            "perimetro": "consolidado", "unidade": "MIL",
            "cabecalho_local": ["consolidado", "(em milhares de reais)"],
            "datas_colunas": dt, "trecho": "ativo total [valor omitido]"}


def formulario_v4(linhas=None, valores=None, individuais=()):
    linhas = linhas if linhas is not None else ["Ativo total 1.234.567 900.000"]
    valores = valores if valores is not None else [("1", None, date(2025, 9, 30), 1234567)]
    return rad.Formulario("f", "1", {}, valores,
        anexos=[(0, ["\n".join(["Notas explicativas às informações financeiras",
                               "Consolidado", "(Em milhares de reais)",
                               "30/09/2025 31/12/2024", *linhas])])],
        grupos_anexos={0: "193"}, valores_individuais=list(individuais))
