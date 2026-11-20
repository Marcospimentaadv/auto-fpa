"""Formatação no padrão brasileiro (R$ 1.234,56 e 12,34%)."""

from __future__ import annotations

import math


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def moeda(valor: float | None) -> str:
    if _vazio(valor):
        return "—"
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {texto}" if valor < 0 else f"R$ {texto}"


def percentual(fracao: float | None, casas: int = 2) -> str:
    if _vazio(fracao):
        return "—"
    return f"{fracao * 100:.{casas}f}%".replace(".", ",")


def anos(valor: float | None) -> str:
    if _vazio(valor):
        return "Não se paga no período"
    return f"{valor:.2f} anos".replace(".", ",")
