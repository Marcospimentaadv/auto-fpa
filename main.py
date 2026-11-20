"""Linha de comando do Auto-FP&A.

Exemplos:
    python main.py
    python main.py --csv data/cenario_estresse.csv --excel saida/relatorio.xlsx
    python main.py --ia --modelo mistral
    python main.py --investimento 60000 --fluxos 18000 22000 25000 28000 30000 --tma 0.14
"""

from __future__ import annotations

import argparse
import sys

from auto_fpa.config import RAIZ_PROJETO, Config
from auto_fpa.dre import formatar_dre, gerar_alertas, gerar_dre, resumo_periodo
from auto_fpa.exportacao_excel import exportar_relatorio
from auto_fpa.ia_local import ClienteOllama, ErroIALocal, montar_prompt_cfo
from auto_fpa.ingestao import ErroValidacao, carregar_csv
from auto_fpa.repositorio import RepositorioLancamentos
from auto_fpa.viabilidade import analisar_projeto


def _argumentos() -> argparse.Namespace:
    cfg = Config()
    p = argparse.ArgumentParser(description="Auto-FP&A: DRE, ponto de equilíbrio e viabilidade.")
    p.add_argument("--csv", default=str(RAIZ_PROJETO / "data" / "dados_ficticios.csv"))
    p.add_argument("--db", default=str(cfg.db_path), help="Banco SQLite do histórico")
    p.add_argument("--excel", default=str(RAIZ_PROJETO / "saida" / "relatorio_fpa.xlsx"))
    p.add_argument("--limite", type=float, default=cfg.limite_margem_seguranca,
                   help="Margem de segurança mínima (0.15 = 15%%)")
    p.add_argument("--investimento", type=float, default=60000.0)
    p.add_argument("--fluxos", type=float, nargs="+",
                   default=[18000, 22000, 25000, 28000, 30000])
    p.add_argument("--tma", type=float, default=0.14)
    p.add_argument("--ia", action="store_true", help="Gera o parecer com o Ollama local")
    p.add_argument("--modelo", default=cfg.ollama_modelo)
    p.add_argument("--mostrar-prompt", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _argumentos()

    try:
        lancamentos = carregar_csv(args.csv)
    except (ErroValidacao, FileNotFoundError) as erro:
        print(f"[ERRO] {erro}", file=sys.stderr)
        return 1

    repo = RepositorioLancamentos(args.db)
    novos = repo.salvar(lancamentos)
    print(f"[OK] {len(lancamentos)} lançamentos lidos, {novos} novos gravados "
          f"({repo.total()} no histórico).")

    historico = repo.listar()
    dre = gerar_dre(historico)
    resumo = resumo_periodo(dre)
    alertas = gerar_alertas(dre, args.limite)

    print("\n=== DRE GERENCIAL E INDICADORES ===")
    print(formatar_dre(dre).to_string())

    print("\n=== ALERTAS ===")
    for alerta in alertas or []:
        print(f"[{alerta.nivel.upper()}] {alerta.mensagem}")
    if not alertas:
        print("Nenhum mês abaixo dos limites.")

    print("\n=== VIABILIDADE DO PROJETO (CAPEX) ===")
    viabilidade = analisar_projeto(args.investimento, args.fluxos, args.tma)
    for chave, valor in viabilidade.como_texto().items():
        print(f"{chave}: {valor}")

    prompt = montar_prompt_cfo(dre, resumo, alertas, viabilidade)
    if args.mostrar_prompt:
        print("\n=== PROMPT ENVIADO À IA LOCAL ===\n" + prompt)

    parecer = None
    if args.ia:
        print(f"\n=== CFO VIRTUAL ({args.modelo}, rodando localmente) ===")
        try:
            parecer = ClienteOllama(Config().ollama_url, args.modelo).gerar(prompt)
            print(parecer)
        except ErroIALocal as erro:
            print(f"[AVISO] {erro}")

    destino = exportar_relatorio(dre, historico, args.excel, alertas, viabilidade,
                                 parecer, args.limite)
    print(f"\n[OK] Relatório Excel salvo em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
