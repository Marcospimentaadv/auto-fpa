import math

import pandas as pd
import pytest

from auto_fpa.dre import gerar_alertas, gerar_dre, resumo_periodo


def test_dre_janeiro(dre):
    jan = dre.loc["2026-01"]
    assert jan["receita_liquida"] == 75650
    assert jan["margem_contribuicao"] == 57150
    assert jan["ebitda"] == 19650
    assert jan["ponto_equilibrio"] == pytest.approx(37500 / (57150 / 85000))


def test_ponto_de_equilibrio_zera_o_ebitda(dre):
    # No ponto de equilíbrio, MC = despesas fixas.
    for _, linha in dre.iterrows():
        assert linha["ponto_equilibrio"] * linha["indice_mc"] == pytest.approx(
            -linha["despesas_fixas"])


def test_mc_negativa_nao_gera_ponto_de_equilibrio():
    df = pd.DataFrame({
        "mes_ref": ["2026-01"] * 3,
        "categoria": ["Receita Bruta", "Custo Variavel", "Despesa Fixa"],
        "valor": [100.0, 150.0, 50.0],
    })
    linha = gerar_dre(df).iloc[0]
    assert math.isnan(linha["ponto_equilibrio"])
    assert any("não há ponto de equilíbrio" in a.mensagem for a in gerar_alertas(gerar_dre(df)))


def test_categoria_ausente_vira_zero():
    df = pd.DataFrame({"mes_ref": ["2026-01"], "categoria": ["Receita Bruta"], "valor": [10.0]})
    assert gerar_dre(df).iloc[0]["ebitda"] == 10.0


def test_sem_alertas_no_cenario_saudavel(dre):
    assert gerar_alertas(dre, 0.15) == []


def test_alertas_no_cenario_de_estresse(lancamentos_estresse):
    alertas = gerar_alertas(gerar_dre(lancamentos_estresse), 0.15)
    assert {a.mes for a in alertas} == {"2026-03", "2026-04", "2026-05"}
    assert any(a.nivel == "critico" and a.mes == "2026-04" for a in alertas)


def test_resumo(dre):
    r = resumo_periodo(dre)
    assert r["receita_total"] == 592000
    assert r["pior_mes"] == "2026-03"


def test_dre_vazia():
    with pytest.raises(ValueError):
        gerar_dre(pd.DataFrame(columns=["mes_ref", "categoria", "valor"]))
