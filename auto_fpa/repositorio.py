"""Persistência dos lançamentos em SQLite.

Diferente da versão inicial (que apagava a tabela inteira a cada importação),
a gravação é idempotente: reimportar o mesmo extrato não duplica lançamentos,
e importar um mês novo preserva o histórico.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

ESQUEMA = """
CREATE TABLE IF NOT EXISTS lancamentos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    data        TEXT NOT NULL,
    mes_ref     TEXT NOT NULL,
    descricao   TEXT NOT NULL,
    categoria   TEXT NOT NULL,
    tipo        TEXT NOT NULL,
    valor       REAL NOT NULL CHECK (valor >= 0),
    importado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (data, descricao, categoria, valor)
);
CREATE INDEX IF NOT EXISTS idx_lancamentos_mes ON lancamentos (mes_ref);
"""

COLUNAS = ["data", "mes_ref", "descricao", "categoria", "tipo", "valor"]


class RepositorioLancamentos:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conexao() as conn:
            conn.executescript(ESQUEMA)

    @contextmanager
    def _conexao(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def salvar(self, lancamentos: pd.DataFrame) -> int:
        """Grava os lançamentos ignorando duplicados. Retorna quantos eram novos."""
        registros = lancamentos[COLUNAS].itertuples(index=False, name=None)
        with self._conexao() as conn:
            antes = conn.total_changes
            conn.executemany(
                "INSERT OR IGNORE INTO lancamentos "
                "(data, mes_ref, descricao, categoria, tipo, valor) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                list(registros),
            )
            return conn.total_changes - antes

    def listar(self, mes_inicio: str | None = None, mes_fim: str | None = None) -> pd.DataFrame:
        """Retorna lançamentos, opcionalmente filtrados por período (AAAA-MM)."""
        sql = f"SELECT {', '.join(COLUNAS)} FROM lancamentos WHERE 1=1"
        parametros: list[str] = []
        if mes_inicio:
            sql += " AND mes_ref >= ?"
            parametros.append(mes_inicio)
        if mes_fim:
            sql += " AND mes_ref <= ?"
            parametros.append(mes_fim)
        sql += " ORDER BY data, id"
        with self._conexao() as conn:
            return pd.read_sql_query(sql, conn, params=parametros)

    def total(self) -> int:
        with self._conexao() as conn:
            return conn.execute("SELECT COUNT(*) FROM lancamentos").fetchone()[0]

    def limpar(self) -> None:
        with self._conexao() as conn:
            conn.execute("DELETE FROM lancamentos")
