"""Relatório executivo em Excel (openpyxl).

A planilha é "viva": os subtotais e indicadores são fórmulas do Excel, então o
gestor pode ajustar uma linha e ver o efeito na hora. O alerta visual da margem
de segurança usa formatação condicional apontando para uma célula de premissa,
que também pode ser alterada.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from auto_fpa.dre import Alerta
from auto_fpa.viabilidade import ResultadoViabilidade

AZUL = "1F3864"
AZUL_CLARO = "D9E2F3"
CINZA = "F2F2F2"
VERMELHO = "C00000"
VERMELHO_CLARO = "FFC7CE"
VERDE_CLARO = "C6EFCE"

FMT_MOEDA = '"R$" #,##0.00;[Red]-"R$" #,##0.00;"-"'
FMT_PCT = "0.00%;[Red]-0.00%"

FONTE_TITULO = Font(name="Calibri", size=16, bold=True, color=AZUL)
FONTE_CABECALHO = Font(name="Calibri", bold=True, color="FFFFFF")
FONTE_ENTRADA = Font(color="0000FF")  # azul = dado digitável
FILL_CABECALHO = PatternFill("solid", fgColor=AZUL)
FILL_SUBTOTAL = PatternFill("solid", fgColor=AZUL_CLARO)
FILL_PREMISSA = PatternFill("solid", fgColor="FFF2CC")
BORDA_TOPO = Border(top=Side(style="thin", color=AZUL))

# Linha -> (rótulo, coluna da DRE ou None se for fórmula, tipo)
LINHA_INICIAL = 5
ESTRUTURA_DRE = [
    ("(+) Receita Bruta", "receita_bruta", "valor"),
    ("(−) Impostos", "impostos", "valor"),
    ("(=) Receita Líquida", "{c}5+{c}6", "subtotal"),
    ("(−) Custos Variáveis", "custos_variaveis", "valor"),
    ("(=) Margem de Contribuição", "{c}7+{c}8", "subtotal"),
    ("(−) Despesas Fixas", "despesas_fixas", "valor"),
    ("(=) EBITDA", "{c}9+{c}10", "subtotal"),
]
LINHA_INDICADORES = 13
ESTRUTURA_INDICADORES = [
    ("Índice de MC", 'IFERROR({c}9/{c}5,"")', FMT_PCT),
    ("Margem Operacional", 'IFERROR({c}11/{c}5,"")', FMT_PCT),
    ("Ponto de Equilíbrio", 'IF(AND(ISNUMBER({c}14),{c}14>0),-{c}10/{c}14,"")', FMT_MOEDA),
    ("Margem de Segurança (R$)", 'IF(ISNUMBER({c}16),{c}5-{c}16,"")', FMT_MOEDA),
    ("Margem de Segurança (%)", 'IF(ISNUMBER({c}17),{c}17/{c}5,"")', FMT_PCT),
]
LINHA_MARGEM_SEGURANCA = 18
CELULA_LIMITE = "$B$22"


def _cabecalho(ws: Worksheet, linha: int, valores: list[str]) -> None:
    for col, valor in enumerate(valores, start=1):
        celula = ws.cell(row=linha, column=col, value=valor)
        celula.font = FONTE_CABECALHO
        celula.fill = FILL_CABECALHO
        celula.alignment = Alignment(horizontal="center", vertical="center")


def _titulo(ws: Worksheet, titulo: str, subtitulo: str) -> None:
    ws["A1"] = titulo
    ws["A1"].font = FONTE_TITULO
    ws["A2"] = subtitulo
    ws["A2"].font = Font(name="Calibri", italic=True, color="595959")


def _aba_dre(wb: Workbook, dre: pd.DataFrame, limite: float) -> None:
    ws = wb.active
    ws.title = "DRE Gerencial"
    meses = list(dre.index)
    n = len(meses)
    col_total = n + 2
    letra_total = get_column_letter(col_total)
    ultima_mes = get_column_letter(n + 1)

    _titulo(ws, "DRE Gerencial e Indicadores",
            f"Auto-FP&A · gerado em {datetime.now():%d/%m/%Y %H:%M} · "
            "valores em azul são dados de entrada; o restante são fórmulas")
    _cabecalho(ws, 4, ["Conta", *meses, "Total"])

    for i, (rotulo, origem, tipo) in enumerate(ESTRUTURA_DRE):
        linha = LINHA_INICIAL + i
        ws.cell(row=linha, column=1, value=rotulo)
        for j in range(n + 1):
            col = j + 2
            letra = get_column_letter(col)
            celula = ws.cell(row=linha, column=col)
            if tipo == "valor" and col == col_total:
                celula.value = f"=SUM(B{linha}:{ultima_mes}{linha})"
            elif tipo == "valor":
                celula.value = float(dre[origem].iloc[j])
                celula.font = FONTE_ENTRADA
            else:
                celula.value = "=" + origem.format(c=letra)
            celula.number_format = FMT_MOEDA
        if tipo == "subtotal":
            for col in range(1, col_total + 1):
                ws.cell(row=linha, column=col).fill = FILL_SUBTOTAL
                ws.cell(row=linha, column=col).font = Font(name="Calibri", bold=True)
                ws.cell(row=linha, column=col).border = BORDA_TOPO

    _cabecalho(ws, LINHA_INDICADORES - 1, ["Indicadores", *meses, "Período"])
    for i, (rotulo, formula, formato) in enumerate(ESTRUTURA_INDICADORES):
        linha = LINHA_INDICADORES + 1 + i
        ws.cell(row=linha, column=1, value=rotulo)
        for col in range(2, col_total + 1):
            celula = ws.cell(row=linha, column=col)
            celula.value = "=" + formula.format(c=get_column_letter(col))
            celula.number_format = formato

    # Premissa editável do alerta
    ws["A21"] = "Premissas"
    ws["A21"].font = Font(bold=True, color=AZUL)
    ws["A22"] = "Margem de segurança mínima"
    ws["B22"] = limite
    ws["B22"].number_format = "0%"
    ws["B22"].font = FONTE_ENTRADA
    ws["B22"].fill = FILL_PREMISSA
    ws["C22"] = "← altere aqui; a linha 18 fica vermelha abaixo desse valor"
    ws["C22"].font = Font(name="Calibri", italic=True, color="595959")

    faixa = f"B{LINHA_MARGEM_SEGURANCA}:{letra_total}{LINHA_MARGEM_SEGURANCA}"
    ws.conditional_formatting.add(faixa, CellIsRule(
        operator="lessThan", formula=[CELULA_LIMITE],
        fill=PatternFill("solid", fgColor=VERMELHO_CLARO),
        font=Font(bold=True, color=VERMELHO)))
    ws.conditional_formatting.add(faixa, CellIsRule(
        operator="greaterThanOrEqual", formula=[CELULA_LIMITE],
        fill=PatternFill("solid", fgColor=VERDE_CLARO)))

    ws.column_dimensions["A"].width = 30
    for col in range(2, col_total + 1):
        ws.column_dimensions[get_column_letter(col)].width = 16
    ws.freeze_panes = "B5"

    grafico = BarChart()
    grafico.title = "Receita Bruta x Ponto de Equilíbrio"
    grafico.y_axis.title = "R$"
    grafico.y_axis.numFmt = "#,##0"
    grafico.height, grafico.width = 8, 18
    grafico.add_data(Reference(ws, min_col=1, max_col=n + 1, min_row=5), from_rows=True,
                     titles_from_data=True)
    categorias = Reference(ws, min_col=2, max_col=n + 1, min_row=4)
    grafico.set_categories(categorias)
    linha_pe = LineChart()
    linha_pe.add_data(Reference(ws, min_col=1, max_col=n + 1, min_row=16), from_rows=True,
                      titles_from_data=True)
    linha_pe.series[0].graphicalProperties.line.solidFill = VERMELHO
    linha_pe.series[0].graphicalProperties.line.width = 28000
    grafico += linha_pe
    ws.add_chart(grafico, f"{get_column_letter(col_total + 2)}4")


def _aba_viabilidade(wb: Workbook, resultado: ResultadoViabilidade) -> None:
    ws = wb.create_sheet("Viabilidade")
    _titulo(ws, "Análise de Viabilidade (Capex)",
            "Fluxos e TMA em azul são editáveis; VPL e TIR recalculam automaticamente")

    ws["A4"], ws["B4"] = "Investimento inicial", resultado.investimento_inicial
    ws["A5"], ws["B5"] = "TMA (a.a.)", resultado.tma
    for celula, formato in (("B4", FMT_MOEDA), ("B5", "0.00%")):
        ws[celula].number_format = formato
        ws[celula].font = FONTE_ENTRADA
        ws[celula].fill = FILL_PREMISSA

    _cabecalho(ws, 7, ["Ano", "Fluxo de caixa", "Fluxo descontado", "Saldo descontado"])
    ws["A8"], ws["B8"], ws["C8"], ws["D8"] = 0, "=-B4", "=B8", "=C8"
    for i, fluxo in enumerate(resultado.fluxos, start=1):
        r = 8 + i
        ws.cell(row=r, column=1, value=i)
        ws.cell(row=r, column=2, value=fluxo).font = FONTE_ENTRADA
        ws.cell(row=r, column=3, value=f"=B{r}/(1+$B$5)^A{r}")
        ws.cell(row=r, column=4, value=f"=D{r - 1}+C{r}")
    ultima = 8 + len(resultado.fluxos)
    for r in range(8, ultima + 1):
        for c in (2, 3, 4):
            ws.cell(row=r, column=c).number_format = FMT_MOEDA

    base = ultima + 2
    indicadores = [
        ("VPL", f"=SUM(C8:C{ultima})", FMT_MOEDA),
        ("TIR", f'=IFERROR(IRR(B8:B{ultima}),"N/A")', "0.00%"),
        ("Índice de lucratividade", f"=SUM(C9:C{ultima})/B4", "0.00"),
        ("Payback simples (anos)", resultado.payback_simples or "Não se paga", "0.00"),
        ("Payback descontado (anos)", resultado.payback_descontado or "Não se paga", "0.00"),
        ("Parecer", f'=IF(B{base}>0,"VIÁVEL","INVIÁVEL")', None),
    ]
    for i, (rotulo, valor, formato) in enumerate(indicadores):
        r = base + i
        ws.cell(row=r, column=1, value=rotulo).font = Font(name="Calibri", bold=True)
        celula = ws.cell(row=r, column=2, value=valor)
        if formato:
            celula.number_format = formato
    ws.cell(row=base + len(indicadores), column=1,
            value="Paybacks calculados pelo motor Python (interpolação linear).").font = Font(
        italic=True, color="595959")

    ws.column_dimensions["A"].width = 28
    for letra in "BCD":
        ws.column_dimensions[letra].width = 20


def _aba_alertas(wb: Workbook, alertas: list[Alerta], parecer_ia: str | None) -> None:
    ws = wb.create_sheet("Alertas e Parecer")
    _titulo(ws, "Alertas automáticos e parecer do CFO Virtual", "")
    _cabecalho(ws, 4, ["Mês", "Nível", "Mensagem"])
    linhas = alertas or [Alerta("—", "ok", "Nenhum mês abaixo dos limites configurados.")]
    for i, alerta in enumerate(linhas, start=5):
        ws.cell(row=i, column=1, value=alerta.mes)
        nivel = ws.cell(row=i, column=2, value=alerta.nivel.upper())
        if alerta.nivel == "critico":
            nivel.font = Font(bold=True, color=VERMELHO)
        ws.cell(row=i, column=3, value=alerta.mensagem)
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 110

    if parecer_ia:
        inicio = 6 + len(linhas)
        ws.cell(row=inicio, column=1, value="Parecer do CFO Virtual (IA local)").font = Font(
            bold=True, size=12, color=AZUL)
        celula = ws.cell(row=inicio + 1, column=1, value=parecer_ia)
        ws.merge_cells(start_row=inicio + 1, start_column=1, end_row=inicio + 30, end_column=3)
        celula.alignment = Alignment(wrap_text=True, vertical="top")


def _aba_lancamentos(wb: Workbook, lancamentos: pd.DataFrame) -> None:
    ws = wb.create_sheet("Lançamentos")
    colunas = ["data", "mes_ref", "descricao", "categoria", "tipo", "valor"]
    _cabecalho(ws, 1, ["Data", "Mês", "Descrição", "Categoria", "Tipo", "Valor"])
    for r, registro in enumerate(lancamentos[colunas].itertuples(index=False), start=2):
        for c, valor in enumerate(registro, start=1):
            ws.cell(row=r, column=c, value=valor)
        ws.cell(row=r, column=6).number_format = FMT_MOEDA
    ws.auto_filter.ref = f"A1:F{len(lancamentos) + 1}"
    ws.freeze_panes = "A2"
    for letra, largura in zip("ABCDEF", (12, 10, 44, 18, 10, 16), strict=True):
        ws.column_dimensions[letra].width = largura


def exportar_relatorio(
    dre: pd.DataFrame,
    lancamentos: pd.DataFrame,
    destino: str | Path | BytesIO,
    alertas: list[Alerta] | None = None,
    viabilidade: ResultadoViabilidade | None = None,
    parecer_ia: str | None = None,
    limite_margem: float = 0.15,
) -> str | Path | BytesIO:
    """Gera o .xlsx em um caminho ou em memória (BytesIO, usado pelo Streamlit)."""
    wb = Workbook()
    _aba_dre(wb, dre, limite_margem)
    if viabilidade is not None:
        _aba_viabilidade(wb, viabilidade)
    _aba_alertas(wb, alertas or [], parecer_ia)
    _aba_lancamentos(wb, lancamentos)

    if isinstance(destino, (str, Path)):
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    return destino
