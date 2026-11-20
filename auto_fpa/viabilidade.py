"""Análise de viabilidade de investimentos (Capex): VPL, TIR, IL e paybacks."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy_financial as npf
import pandas as pd

from auto_fpa import formatacao as fmt


@dataclass(frozen=True)
class ResultadoViabilidade:
    investimento_inicial: float
    tma: float
    fluxos: tuple[float, ...]
    vpl: float
    tir: float | None
    indice_lucratividade: float
    payback_simples: float | None
    payback_descontado: float | None

    @property
    def viavel(self) -> bool:
        # O VPL é o critério decisivo: a TIR pode não existir ou ser múltipla
        # quando o fluxo troca de sinal mais de uma vez.
        return self.vpl > 0

    @property
    def parecer(self) -> str:
        if self.viavel:
            return "VIÁVEL: o projeto gera valor acima da TMA."
        return "INVIÁVEL: o projeto não remunera a TMA exigida."

    @property
    def fluxos_descontados(self) -> list[float]:
        return [fc / (1 + self.tma) ** ano for ano, fc in enumerate(self.fluxos, start=1)]

    def como_texto(self) -> dict[str, str]:
        return {
            "Investimento inicial": fmt.moeda(self.investimento_inicial),
            "TMA": fmt.percentual(self.tma),
            "VPL": fmt.moeda(self.vpl),
            "TIR": fmt.percentual(self.tir),
            "Índice de lucratividade": f"{self.indice_lucratividade:.2f}".replace(".", ","),
            "Payback simples": fmt.anos(self.payback_simples),
            "Payback descontado": fmt.anos(self.payback_descontado),
            "Parecer": self.parecer,
        }


def _payback(fluxo_completo: Sequence[float]) -> float | None:
    """Anos (com fração linear) até o saldo acumulado ficar >= 0."""
    acumulado = fluxo_completo[0]
    for ano, fc in enumerate(fluxo_completo[1:], start=1):
        anterior = acumulado
        acumulado += fc
        if anterior < 0 <= acumulado:
            return (ano - 1) + (-anterior / fc)
    return None


def analisar_projeto(
    investimento_inicial: float, fluxos: Sequence[float], tma: float
) -> ResultadoViabilidade:
    if investimento_inicial <= 0:
        raise ValueError("O investimento inicial deve ser maior que zero.")
    if not fluxos:
        raise ValueError("Informe ao menos um fluxo de caixa futuro.")
    if tma <= -1:
        raise ValueError("A TMA deve ser maior que -100%.")

    fluxos = tuple(float(f) for f in fluxos)
    fluxo_completo = [-float(investimento_inicial), *fluxos]

    # npf.npv trata o primeiro valor como t=0 (sem desconto), diferente do VPL do Excel.
    vpl = float(npf.npv(tma, fluxo_completo))
    tir_bruta = float(npf.irr(fluxo_completo))
    tir = None if math.isnan(tir_bruta) else tir_bruta

    descontados = [fc / (1 + tma) ** ano for ano, fc in enumerate(fluxos, start=1)]
    return ResultadoViabilidade(
        investimento_inicial=float(investimento_inicial),
        tma=float(tma),
        fluxos=fluxos,
        vpl=vpl,
        tir=tir,
        indice_lucratividade=sum(descontados) / investimento_inicial,
        payback_simples=_payback(fluxo_completo),
        payback_descontado=_payback([-float(investimento_inicial), *descontados]),
    )


def sensibilidade_tma(
    investimento_inicial: float, fluxos: Sequence[float],
    taxas: Sequence[float] | None = None,
) -> pd.DataFrame:
    """VPL para uma faixa de TMAs; o ponto onde cruza zero é a TIR."""
    if taxas is None:
        taxas = np.round(np.arange(0.0, 0.405, 0.01), 4)
    fluxo = [-float(investimento_inicial), *map(float, fluxos)]
    return pd.DataFrame({"tma": taxas, "vpl": [npf.npv(t, fluxo) for t in taxas]})
