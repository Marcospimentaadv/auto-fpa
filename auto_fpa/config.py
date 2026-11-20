"""Configuração central, lida de variáveis de ambiente com padrões seguros."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

# Categorias aceitas no CSV e o tipo de movimento esperado para cada uma.
# O sinal contábil vem da categoria, por isso os valores do CSV são sempre positivos.
CATEGORIAS: dict[str, str] = {
    "Receita Bruta": "Entrada",
    "Impostos": "Saida",
    "Custo Variavel": "Saida",
    "Despesa Fixa": "Saida",
}


def _caminho_db_padrao() -> Path:
    return Path(os.getenv("AUTOFPA_DB", RAIZ_PROJETO / "data" / "auto_fpa.db"))


@dataclass(frozen=True)
class Config:
    db_path: Path = field(default_factory=_caminho_db_padrao)
    ollama_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434")
    )
    ollama_modelo: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3")
    )
    # Margem de segurança mínima aceitável (15% da receita bruta).
    limite_margem_seguranca: float = 0.15
