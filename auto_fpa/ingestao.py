"""Leitura e validação de extratos CSV.

Aceita tanto o formato "técnico" (vírgula como separador, ponto decimal, datas ISO)
quanto o formato exportado por planilhas brasileiras (ponto e vírgula, vírgula
decimal, datas dd/mm/aaaa). Erros são reportados com o número da linha do arquivo.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from auto_fpa.config import CATEGORIAS

COLUNAS_OBRIGATORIAS = ["data", "descricao", "categoria", "tipo", "valor"]


class ErroValidacao(ValueError):
    """Extrato com estrutura ou conteúdo inválido."""


def _ler_texto(origem: str | Path | BinaryIO | bytes) -> str:
    if isinstance(origem, bytes):
        bruto = origem
    elif isinstance(origem, (str, Path)):
        bruto = Path(origem).read_bytes()
    else:
        bruto = origem.read()
        if isinstance(bruto, str):
            return bruto
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ErroValidacao("Não foi possível identificar a codificação do arquivo.")


def carregar_csv(origem: str | Path | BinaryIO | bytes) -> pd.DataFrame:
    """Lê um CSV (caminho, bytes ou arquivo enviado) e devolve lançamentos validados."""
    texto = _ler_texto(origem)
    if not texto.strip():
        raise ErroValidacao("O arquivo está vazio.")
    primeira_linha = texto.splitlines()[0]
    separador = ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","
    df = pd.read_csv(io.StringIO(texto), sep=separador, dtype=str)
    return validar_lancamentos(df)


def _linhas(mascara: pd.Series) -> str:
    # +2: cabeçalho ocupa a linha 1 e o índice começa em 0.
    numeros = [str(i + 2) for i in mascara[mascara].index[:10]]
    return ", ".join(numeros)


def _converter_valor(serie: pd.Series) -> pd.Series:
    texto = serie.astype(str).str.strip().str.replace("R$", "", regex=False).str.strip()
    formato_br = texto.str.contains(",", regex=False)
    texto = texto.where(
        ~formato_br,
        texto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
    )
    return pd.to_numeric(texto, errors="coerce")


def _converter_data(serie: pd.Series) -> pd.Series:
    texto = serie.astype(str).str.strip()
    iso = pd.to_datetime(texto, format="%Y-%m-%d", errors="coerce")
    br = pd.to_datetime(texto, format="%d/%m/%Y", errors="coerce")
    return iso.fillna(br)


def validar_lancamentos(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza colunas, converte tipos e rejeita dados inconsistentes."""
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise ErroValidacao(f"Colunas obrigatórias ausentes: {', '.join(faltando)}.")

    df = df[COLUNAS_OBRIGATORIAS].dropna(how="all").reset_index(drop=True)
    if df.empty:
        raise ErroValidacao("O arquivo não contém lançamentos.")

    df["data"] = _converter_data(df["data"])
    if df["data"].isna().any():
        raise ErroValidacao(
            f"Data inválida nas linhas {_linhas(df['data'].isna())} "
            "(use AAAA-MM-DD ou DD/MM/AAAA)."
        )

    df["valor"] = _converter_valor(df["valor"])
    if df["valor"].isna().any():
        raise ErroValidacao(f"Valor inválido nas linhas {_linhas(df['valor'].isna())}.")
    if (df["valor"] < 0).any():
        raise ErroValidacao(
            f"Valor negativo nas linhas {_linhas(df['valor'] < 0)}. "
            "Informe valores positivos: o sinal contábil vem da categoria."
        )

    df["categoria"] = df["categoria"].astype(str).str.strip()
    desconhecidas = sorted(set(df["categoria"]) - set(CATEGORIAS))
    if desconhecidas:
        raise ErroValidacao(
            f"Categorias não reconhecidas: {', '.join(desconhecidas)}. "
            f"Aceitas: {', '.join(CATEGORIAS)}."
        )

    df["tipo"] = (
        df["tipo"].astype(str).str.strip().str.capitalize().str.replace("í", "i")
    )
    esperado = df["categoria"].map(CATEGORIAS)
    divergente = df["tipo"] != esperado
    if divergente.any():
        raise ErroValidacao(
            f"Tipo incompatível com a categoria nas linhas {_linhas(divergente)} "
            "(Receita Bruta é Entrada; as demais categorias são Saida)."
        )

    df["descricao"] = df["descricao"].fillna("").astype(str).str.strip()
    df["mes_ref"] = df["data"].dt.to_period("M").astype(str)
    df["data"] = df["data"].dt.strftime("%Y-%m-%d")
    return df[["data", "mes_ref", "descricao", "categoria", "tipo", "valor"]]
