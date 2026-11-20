from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_carrega_sem_erros():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.metric[0].label == "Receita bruta"


def test_app_mostra_alertas_no_estresse():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.selectbox[0].set_value("Cenário de estresse").run()
    assert not at.exception
    assert any("prejuízo operacional" in e.value for e in at.error)
