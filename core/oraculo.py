"""Oráculo de teste do CAD0001.

O oráculo NÃO é o código-fonte: é a regra de negócio escrita no Manual da
Sprint 1, implementada de forma independente em Python. É a "fonte de verdade"
contra a qual comparamos o que o programa 4GL devolve.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

EPSILON = Decimal("0.01")
MAXIMO = Decimal("9999999999.99")  # maior valor de DECIMAL(12,2)


def _d(v):
    return None if v is None else Decimal(str(v))


def esperado(p1, p2, p3):
    """Resultado esperado pela especificação (Decimal) ou 'ESTOURO'."""
    vals = [_d(p1), _d(p2), _d(p3)]
    if any(v is not None and abs(v) > MAXIMO for v in vals):
        return "ESTOURO"
    v1, v2, v3 = (Decimal(0) if v is None else v for v in vals)  # REQ02: NULL vira zero
    if v1 < 0 or v2 < 0 or v3 < 0:  # REQ03: negativo é parâmetro inválido
        return Decimal("-1")
    total = (v1 * v2 + v3).quantize(EPSILON, rounding=ROUND_HALF_UP)  # REQ01 / REQ04
    if total > MAXIMO:  # REQ05: resultado não cabe em DECIMAL(12,2)
        return "ESTOURO"
    return total


def confere(resultado, esperado_) -> bool:
    """Compara a saída do interpretador com o oráculo."""
    if esperado_ == "ESTOURO":
        return bool(resultado.erro) and "ESTOURO" in resultado.erro
    if resultado.erro:
        return False
    return resultado.valor is not None and Decimal(resultado.valor) == esperado_


REQUISITOS = {
    "REQ01": "Calcular val_calculado = (val_param1 × val_param2) + val_param3.",
    "REQ02": "Parâmetro NULL deve ser tratado como 0,00 antes do cálculo.",
    "REQ03": "Parâmetro negativo (< 0,00) é inválido: retornar o código de erro -1.",
    "REQ04": "Fronteira inferior exata: 0,00 é válido e -0,01 (0,00 − ε) é inválido; precisão de centavos (ε = 0,01).",
    "REQ05": "Respeitar o limite de DECIMAL(12,2): 9.999.999.999,99 é o maior valor; acima disso há estouro.",
    "REQ06": "Gravar cad_item e cad_item_calculo (1 para 1) na mesma transação (BEGIN/COMMIT/ROLLBACK).",
}
