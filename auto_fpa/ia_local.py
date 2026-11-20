"""CFO Virtual: parecer executivo gerado por um LLM rodando localmente (Ollama).

Privacidade por padrão: o cliente recusa qualquer endpoint que não esteja na
própria máquina, então os números da empresa nunca saem do computador, a menos
que alguém libere isso explicitamente (permitir_remoto=True).
"""

from __future__ import annotations

from urllib.parse import urlparse

import pandas as pd
import requests

from auto_fpa import formatacao as fmt
from auto_fpa.dre import Alerta, formatar_dre
from auto_fpa.viabilidade import ResultadoViabilidade

HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1"}

INSTRUCAO_SISTEMA = (
    "Você é um Diretor Financeiro (CFO) e analista sênior de FP&A em uma empresa "
    "brasileira. Responda em português do Brasil, em tom executivo, objetivo e "
    "baseado exclusivamente nos números fornecidos. Nunca invente dados. "
    "Quando um número não estiver disponível, diga isso."
)


class ErroIALocal(RuntimeError):
    """Falha de comunicação com o servidor de IA local."""


class ClienteOllama:
    def __init__(
        self,
        url: str = "http://localhost:11434",
        modelo: str = "llama3",
        timeout: float = 180,
        permitir_remoto: bool = False,
    ):
        host = urlparse(url).hostname
        if not permitir_remoto and host not in HOSTS_LOCAIS:
            raise ValueError(
                f"Endpoint '{url}' não é local. Por privacidade, o Auto-FP&A só envia "
                "dados financeiros para um modelo rodando nesta máquina."
            )
        self.url = url.rstrip("/")
        self.modelo = modelo
        self.timeout = timeout

    def disponivel(self) -> bool:
        try:
            return requests.get(f"{self.url}/api/tags", timeout=3).ok
        except requests.RequestException:
            return False

    def modelos_instalados(self) -> list[str]:
        try:
            resposta = requests.get(f"{self.url}/api/tags", timeout=3)
            resposta.raise_for_status()
        except requests.RequestException as erro:
            raise ErroIALocal(f"Ollama indisponível em {self.url}: {erro}") from erro
        return [m["name"] for m in resposta.json().get("models", [])]

    def gerar(self, prompt: str, temperatura: float = 0.2) -> str:
        corpo = {
            "model": self.modelo,
            "system": INSTRUCAO_SISTEMA,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperatura},
        }
        try:
            resposta = requests.post(
                f"{self.url}/api/generate", json=corpo, timeout=self.timeout
            )
        except requests.ConnectionError as erro:
            raise ErroIALocal(
                f"Não foi possível conectar ao Ollama em {self.url}. "
                "Verifique se ele está rodando (comando: ollama serve)."
            ) from erro
        except requests.Timeout as erro:
            raise ErroIALocal("O modelo demorou demais para responder.") from erro

        if resposta.status_code == 404:
            raise ErroIALocal(
                f"Modelo '{self.modelo}' não encontrado. Baixe com: ollama pull {self.modelo}"
            )
        if not resposta.ok:
            raise ErroIALocal(f"Ollama respondeu {resposta.status_code}: {resposta.text[:200]}")
        return resposta.json().get("response", "").strip()


def montar_prompt_cfo(
    dre: pd.DataFrame,
    resumo: dict,
    alertas: list[Alerta],
    viabilidade: ResultadoViabilidade | None = None,
) -> str:
    tabela = formatar_dre(dre).to_markdown()
    linhas_alerta = "\n".join(f"- {a.mensagem}" for a in alertas) or "- Nenhum alerta."

    blocos = [
        f"Analise a DRE Gerencial de {resumo['meses']} meses ({resumo['periodo']}):",
        tabela,
        "Resumo do período:",
        f"- Receita bruta total: {fmt.moeda(resumo['receita_total'])}",
        f"- EBITDA total: {fmt.moeda(resumo['ebitda_total'])}",
        f"- Margem operacional média: {fmt.percentual(resumo['margem_operacional_media'])}",
        f"- Variação da receita (primeiro x último mês): "
        f"{fmt.percentual(resumo['crescimento_receita'])}",
        "",
        "Alertas automáticos do sistema:",
        linhas_alerta,
    ]
    if viabilidade is not None:
        blocos += ["", "Projeto de investimento em avaliação:"]
        blocos += [f"- {chave}: {valor}" for chave, valor in viabilidade.como_texto().items()]

    blocos += [
        "",
        "Entregue um parecer executivo com:",
        "1. Diagnóstico da evolução da receita bruta versus margem operacional.",
        "2. O mês de pior desempenho e a distância dele até o ponto de equilíbrio.",
        "3. Três recomendações práticas para aumentar a margem de contribuição e "
        "proteger o caixa.",
    ]
    if viabilidade is not None:
        blocos.append("4. Se o investimento deve ser aprovado agora, considerando o caixa.")
    return "\n".join(blocos)
