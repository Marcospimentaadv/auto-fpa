from auto_fpa.repositorio import RepositorioLancamentos


def test_importacao_idempotente(tmp_path, lancamentos):
    repo = RepositorioLancamentos(tmp_path / "teste.db")
    assert repo.salvar(lancamentos) == 30
    assert repo.salvar(lancamentos) == 0
    assert repo.total() == 30


def test_historico_acumula_e_filtra(tmp_path, lancamentos):
    repo = RepositorioLancamentos(tmp_path / "teste.db")
    repo.salvar(lancamentos[lancamentos["mes_ref"] <= "2026-03"])
    repo.salvar(lancamentos[lancamentos["mes_ref"] > "2026-03"])
    assert repo.total() == 30
    assert len(repo.listar("2026-04", "2026-05")) == 10
