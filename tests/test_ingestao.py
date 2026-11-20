import pytest

from auto_fpa.ingestao import ErroValidacao, carregar_csv

CABECALHO = "data,descricao,categoria,tipo,valor\n"


def test_le_csv_padrao(lancamentos):
    assert len(lancamentos) == 30
    assert set(lancamentos["mes_ref"]) == {f"2026-0{m}" for m in range(1, 7)}


def test_le_formato_brasileiro(lancamentos_estresse):
    # ponto e vírgula, vírgula decimal, separador de milhar e data dd/mm/aaaa
    assert lancamentos_estresse.loc[0, "valor"] == 85000.0
    assert lancamentos_estresse.loc[0, "data"] == "2026-01-05"


@pytest.mark.parametrize("conteudo, trecho", [
    ("data,descricao,valor\n2026-01-01,x,10\n", "Colunas obrigatórias ausentes"),
    (CABECALHO + "2026-01-01,x,Receita Bruta,Entrada,-10\n", "Valor negativo"),
    (CABECALHO + "2026-01-01,x,Marketing,Saida,10\n", "Categorias não reconhecidas"),
    (CABECALHO + "2026-01-01,x,Impostos,Entrada,10\n", "Tipo incompatível"),
    (CABECALHO + "31/31/2026,x,Impostos,Saida,10\n", "Data inválida nas linhas 2"),
    (CABECALHO + "2026-01-01,x,Impostos,Saida,abc\n", "Valor inválido"),
    ("", "vazio"),
])
def test_rejeita_dados_invalidos(conteudo, trecho):
    with pytest.raises(ErroValidacao, match=trecho):
        carregar_csv(conteudo.encode())


def test_aceita_saida_com_acento_e_latin1():
    texto = CABECALHO + "2026-01-01,Aluguel,Despesa Fixa,Saída,10\n"
    df = carregar_csv(texto.encode("latin-1"))
    assert df.loc[0, "tipo"] == "Saida"
