from io import BytesIO

from openpyxl import load_workbook

from auto_fpa.dre import gerar_alertas
from auto_fpa.exportacao_excel import exportar_relatorio
from auto_fpa.viabilidade import analisar_projeto


def test_relatorio_tem_formulas_e_alerta(dre, lancamentos):
    buffer = BytesIO()
    v = analisar_projeto(60000, [18000, 22000, 25000], 0.14)
    exportar_relatorio(dre, lancamentos, buffer, gerar_alertas(dre), v, "Parecer teste", 0.15)
    wb = load_workbook(BytesIO(buffer.getvalue()))

    assert wb.sheetnames == ["DRE Gerencial", "Viabilidade", "Alertas e Parecer", "Lançamentos"]
    ws = wb["DRE Gerencial"]
    assert ws["B5"].value == 85000
    assert ws["B11"].value == "=B9+B10"
    assert ws["H5"].value == "=SUM(B5:G5)"
    regras = [r for faixa in ws.conditional_formatting for r in faixa.rules]
    assert any(r.operator == "lessThan" and r.formula == ["$B$22"] for r in regras)
    assert ws["B22"].value == 0.15
    assert len(ws._charts) == 1
    assert wb["Lançamentos"].max_row == 31
