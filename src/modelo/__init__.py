"""Modelo supervisionado offline sobre o painel contábil da CVM (spec 5.10).

**Este pacote é offline e NUNCA é ferramenta de agente (RN07).** Ele não
responde pergunta de usuário sobre companhia nomeada: fazê-lo seria emitir
juízo prospectivo sobre emissor identificado num aplicativo aberto — a mesma
fronteira que a RN05 protege quando recusa "vale a pena comprar ações do BB?",
só que na direção oposta.

`tests/test_modelo.py::TestRN07` falha se qualquer módulo do caminho
interativo importar este pacote.
"""

from src.modelo.construir_painel import (
    COLUNAS_FEATURES,
    PainelSupervisionado,
    construir_painel,
    ordinal_trimestre,
    trimestres_completos,
)

__all__ = [
    "COLUNAS_FEATURES",
    "PainelSupervisionado",
    "construir_painel",
    "ordinal_trimestre",
    "trimestres_completos",
]
