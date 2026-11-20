"""DRE Gerencial, indicadores de margem, ponto de equilíbrio e alertas.

Todas as funções são puras: recebem DataFrames e devolvem DataFrames, sem acesso
a banco ou tela. Percentuais ficam como frações (0.25 = 25%); a formatação é
responsabilidade da camada de apresentação.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from auto_fpa import formatacao as fmt
from auto_fpa.config import CATEGORIAS

ROTULOS = {
    "receita_bruta": "(+) Receita Bruta",
    "impostos": "(−) Impostos",
    "receita_liquida": "(=) Receita Líquida",
    "custos_variaveis": "(−) Custos Variáveis",
    "margem_contribuicao": "(=) Margem de Contribuição",
    "despesas_fixas": "(−) Despesas Fixas",
    "ebitda": "(=) EBITDA",
    "indice_mc": "Índice de MC",
    "margem_operacional": "Margem Operacional",
    "ponto_equilibrio": "Ponto de Equilíbrio",
    "margem_seguranca_rs": "Margem de Segurança (R$)",
    "margem_seguranca": "Margem de Segurança (%)",
}
COLUNAS_PERCENTUAIS = {"indice_mc", "margem_operacional", "margem_seguranca"}


def gerar_dre(lancamentos: pd.DataFrame) -> pd.DataFrame:
    """Monta a DRE mensal (uma linha por mês) a partir dos lançamentos validados."""
    if lancamentos.empty:
        raise ValueError("Não há lançamentos para gerar a DRE.")

    piv = (
        lancamentos.pivot_table(
            index="mes_ref", columns="categoria", values="valor",
            aggfunc="sum", fill_value=0.0,
        )
        .reindex(columns=list(CATEGORIAS), fill_value=0.0)
        .sort_index()
        .astype(float)
    )

    dre = pd.DataFrame(index=piv.index)
    dre.index.name = "mes_ref"
    dre["receita_bruta"] = piv["Receita Bruta"]
    dre["impostos"] = -piv["Impostos"]
    dre["receita_liquida"] = dre["receita_bruta"] + dre["impostos"]
    dre["custos_variaveis"] = -piv["Custo Variavel"]
    dre["margem_contribuicao"] = dre["receita_liquida"] + dre["custos_variaveis"]
    dre["despesas_fixas"] = -piv["Despesa Fixa"]
    dre["ebitda"] = dre["margem_contribuicao"] + dre["despesas_fixas"]

    receita = dre["receita_bruta"].replace(0.0, np.nan)
    dre["indice_mc"] = dre["margem_contribuicao"] / receita
    dre["margem_operacional"] = dre["ebitda"] / receita

    # Com MC <= 0 não existe faturamento capaz de cobrir os custos fixos:
    # o ponto de equilíbrio fica indefinido (NaN) em vez de negativo ou infinito.
    indice_valido = dre["indice_mc"].where(dre["indice_mc"] > 0)
    dre["ponto_equilibrio"] = -dre["despesas_fixas"] / indice_valido
    dre["margem_seguranca_rs"] = dre["receita_bruta"] - dre["ponto_equilibrio"]
    dre["margem_seguranca"] = dre["margem_seguranca_rs"] / receita
    return dre


@dataclass(frozen=True)
class Alerta:
    mes: str
    nivel: str  # "critico" ou "atencao"
    mensagem: str


def gerar_alertas(dre: pd.DataFrame, limite_margem: float = 0.15) -> list[Alerta]:
    alertas: list[Alerta] = []
    for mes, linha in dre.iterrows():
        if linha["ebitda"] < 0:
            alertas.append(Alerta(mes, "critico",
                f"{mes}: prejuízo operacional de {fmt.moeda(-linha['ebitda'])}."))
        if pd.isna(linha["ponto_equilibrio"]):
            alertas.append(Alerta(mes, "critico",
                f"{mes}: margem de contribuição nula ou negativa; "
                "não há ponto de equilíbrio alcançável."))
        elif linha["margem_seguranca_rs"] < 0:
            alertas.append(Alerta(mes, "critico",
                f"{mes}: faturamento {fmt.moeda(-linha['margem_seguranca_rs'])} "
                "abaixo do ponto de equilíbrio."))
        elif linha["margem_seguranca"] < limite_margem:
            alertas.append(Alerta(mes, "atencao",
                f"{mes}: margem de segurança de {fmt.percentual(linha['margem_seguranca'])} "
                f"(abaixo do limite de {fmt.percentual(limite_margem, 0)}); "
                f"faturamento só {fmt.moeda(linha['margem_seguranca_rs'])} "
                "acima do ponto de equilíbrio."))
    return alertas


def resumo_periodo(dre: pd.DataFrame) -> dict:
    """Totais e destaques do período para KPIs e para o prompt da IA."""
    receita_total = dre["receita_bruta"].sum()
    ebitda_total = dre["ebitda"].sum()
    primeiro, ultimo = dre["receita_bruta"].iloc[0], dre["receita_bruta"].iloc[-1]
    pior_mes = dre["margem_seguranca"].fillna(-np.inf).idxmin()
    return {
        "meses": int(len(dre)),
        "periodo": f"{dre.index[0]} a {dre.index[-1]}",
        "receita_total": float(receita_total),
        "ebitda_total": float(ebitda_total),
        "margem_operacional_media": (
            float(ebitda_total / receita_total) if receita_total else np.nan
        ),
        "crescimento_receita": float(ultimo / primeiro - 1) if primeiro else np.nan,
        "pior_mes": pior_mes,
        "pior_margem_seguranca": float(dre.loc[pior_mes, "margem_seguranca"]),
    }


def formatar_dre(dre: pd.DataFrame, transpor: bool = True) -> pd.DataFrame:
    """Versão em texto (R$ e %) pronta para exibir em tela ou enviar à IA."""
    saida = pd.DataFrame(index=dre.index)
    for coluna, rotulo in ROTULOS.items():
        formatador = fmt.percentual if coluna in COLUNAS_PERCENTUAIS else fmt.moeda
        saida[rotulo] = dre[coluna].map(formatador)
    return saida.T if transpor else saida
