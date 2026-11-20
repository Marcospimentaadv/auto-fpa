from pathlib import Path

import pytest

from auto_fpa.dre import gerar_dre
from auto_fpa.ingestao import carregar_csv

DADOS = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def lancamentos():
    return carregar_csv(DADOS / "dados_ficticios.csv")


@pytest.fixture
def lancamentos_estresse():
    return carregar_csv(DADOS / "cenario_estresse.csv")


@pytest.fixture
def dre(lancamentos):
    return gerar_dre(lancamentos)
