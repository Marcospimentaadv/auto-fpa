import pytest

from auto_fpa.viabilidade import analisar_projeto, sensibilidade_tma

FLUXOS = [18000, 22000, 25000, 28000, 30000]


def test_vpl_bate_com_desconto_manual():
    r = analisar_projeto(60000, FLUXOS, 0.14)
    manual = -60000 + sum(f / 1.14 ** t for t, f in enumerate(FLUXOS, start=1))
    assert r.vpl == pytest.approx(manual)
    assert r.viavel


def test_tir_zera_o_vpl():
    r = analisar_projeto(60000, FLUXOS, 0.14)
    assert analisar_projeto(60000, FLUXOS, r.tir).vpl == pytest.approx(0, abs=1e-6)


def test_paybacks():
    r = analisar_projeto(100, [50, 50, 50], 0.0)
    assert r.payback_simples == pytest.approx(2.0)
    assert r.payback_descontado == pytest.approx(2.0)
    assert analisar_projeto(60000, FLUXOS, 0.14).payback_simples == pytest.approx(2.8)


def test_projeto_que_nao_se_paga():
    r = analisar_projeto(1000, [100, 100], 0.10)
    assert r.payback_simples is None
    assert not r.viavel


@pytest.mark.parametrize("inv, fluxos, tma", [(0, [1], 0.1), (100, [], 0.1), (100, [1], -1)])
def test_entradas_invalidas(inv, fluxos, tma):
    with pytest.raises(ValueError):
        analisar_projeto(inv, fluxos, tma)


def test_sensibilidade_decrescente():
    s = sensibilidade_tma(60000, FLUXOS)
    assert s["vpl"].is_monotonic_decreasing
