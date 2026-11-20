import pytest
import requests

from auto_fpa.dre import gerar_alertas, resumo_periodo
from auto_fpa.ia_local import ClienteOllama, ErroIALocal, montar_prompt_cfo
from auto_fpa.viabilidade import analisar_projeto


def test_bloqueia_endpoint_remoto():
    with pytest.raises(ValueError, match="não é local"):
        ClienteOllama("https://api.exemplo.com")


def test_prompt_contem_dados(dre):
    v = analisar_projeto(60000, [18000, 22000], 0.14)
    prompt = montar_prompt_cfo(dre, resumo_periodo(dre), gerar_alertas(dre), v)
    assert "2026-06" in prompt and "R$ 592.000,00" in prompt and "VPL" in prompt


class _Resposta:
    def __init__(self, status, corpo):
        self.status_code, self._corpo, self.ok, self.text = status, corpo, status == 200, ""

    def json(self):
        return self._corpo


def test_gerar_envia_requisicao_local(monkeypatch):
    chamadas = {}

    def falso_post(url, json, timeout):
        chamadas.update(url=url, corpo=json)
        return _Resposta(200, {"response": " Parecer ok "})

    monkeypatch.setattr(requests, "post", falso_post)
    assert ClienteOllama(modelo="mistral").gerar("oi") == "Parecer ok"
    assert chamadas["url"] == "http://localhost:11434/api/generate"
    assert chamadas["corpo"]["model"] == "mistral" and chamadas["corpo"]["stream"] is False


def test_erros_viram_mensagens_amigaveis(monkeypatch):
    def sem_servidor(*a, **k):
        raise requests.ConnectionError

    monkeypatch.setattr(requests, "post", sem_servidor)
    with pytest.raises(ErroIALocal, match="ollama serve"):
        ClienteOllama().gerar("oi")

    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resposta(404, {}))
    with pytest.raises(ErroIALocal, match="ollama pull"):
        ClienteOllama().gerar("oi")
