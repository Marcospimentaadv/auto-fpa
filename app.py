"""Painel web do Auto-FP&A. Execute com:  streamlit run app.py"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auto_fpa import formatacao as fmt
from auto_fpa.config import RAIZ_PROJETO, Config
from auto_fpa.dre import formatar_dre, gerar_alertas, gerar_dre, resumo_periodo
from auto_fpa.exportacao_excel import exportar_relatorio
from auto_fpa.ia_local import ClienteOllama, ErroIALocal, montar_prompt_cfo
from auto_fpa.ingestao import ErroValidacao, carregar_csv
from auto_fpa.viabilidade import analisar_projeto, sensibilidade_tma

EXEMPLOS = {
    "Empresa em crescimento": RAIZ_PROJETO / "data" / "dados_ficticios.csv",
    "Cenário de estresse": RAIZ_PROJETO / "data" / "cenario_estresse.csv",
}
AZUL, VERMELHO, VERDE, CINZA = "#1F3864", "#C00000", "#2E7D32", "#8C8C8C"

st.set_page_config(page_title="Auto-FP&A", page_icon="📊", layout="wide")


@st.cache_data(show_spinner=False)
def _carregar(conteudo: bytes) -> pd.DataFrame:
    return carregar_csv(conteudo)


# ---------------------------------------------------------------- barra lateral
cfg = Config()
with st.sidebar:
    st.header("Dados")
    arquivo = st.file_uploader("Extrato CSV", type=["csv"],
                               help="Colunas: data, descricao, categoria, tipo, valor")
    exemplo = st.selectbox("Ou use um exemplo", list(EXEMPLOS), disabled=arquivo is not None)
    st.divider()
    st.header("Premissas")
    limite = st.slider("Margem de segurança mínima", 0.05, 0.40,
                       cfg.limite_margem_seguranca, 0.01, format="%.2f")
    st.divider()
    st.header("IA local (Ollama)")
    url_ollama = st.text_input("Endpoint", cfg.ollama_url)
    modelo = st.text_input("Modelo", cfg.ollama_modelo)

conteudo = arquivo.getvalue() if arquivo else EXEMPLOS[exemplo].read_bytes()
try:
    lancamentos = _carregar(conteudo)
except ErroValidacao as erro:
    st.error(f"Arquivo inválido: {erro}")
    st.stop()

dre = gerar_dre(lancamentos)
resumo = resumo_periodo(dre)
alertas = gerar_alertas(dre, limite)

# ---------------------------------------------------------------- cabeçalho
st.title("Auto-FP&A")
st.caption(f"Motor de inteligência financeira · {resumo['periodo']} · "
           f"{len(lancamentos)} lançamentos · processado 100% nesta máquina")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Receita bruta", fmt.moeda(resumo["receita_total"]),
          f"{fmt.percentual(resumo['crescimento_receita'])} no período")
k2.metric("EBITDA", fmt.moeda(resumo["ebitda_total"]))
k3.metric("Margem operacional média", fmt.percentual(resumo["margem_operacional_media"]))
k4.metric(f"Pior margem de segurança ({resumo['pior_mes']})",
          fmt.percentual(resumo["pior_margem_seguranca"]))

aba_visao, aba_dre, aba_capex, aba_ia, aba_export = st.tabs(
    ["Visão geral", "DRE gerencial", "Viabilidade (Capex)", "CFO Virtual", "Exportar"])

# ---------------------------------------------------------------- visão geral
with aba_visao:
    cores = [VERMELHO if (pd.isna(m) or m < limite) else AZUL
             for m in dre["margem_seguranca"]]
    fig = go.Figure()
    fig.add_bar(x=dre.index, y=dre["receita_bruta"], name="Receita bruta",
                marker_color=cores, hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>")
    fig.add_scatter(x=dre.index, y=dre["ponto_equilibrio"], name="Ponto de equilíbrio",
                    mode="lines+markers", line=dict(color=CINZA, width=3, dash="dash"),
                    hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>")
    fig.add_scatter(x=dre.index, y=dre["ebitda"], name="EBITDA", mode="lines+markers",
                    line=dict(color=VERDE, width=3),
                    hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>")
    fig.update_layout(title="Receita bruta x ponto de equilíbrio",
                      yaxis_title="R$", hovermode="x unified", height=430,
                      legend=dict(orientation="h", y=1.08, x=0), xaxis_type="category",
                      separators=",.", margin=dict(t=70, b=20))
    st.plotly_chart(fig, width="stretch")
    st.caption("Barras em vermelho: meses com margem de segurança abaixo do limite.")

    st.subheader("Alertas")
    if not alertas:
        st.success("Todos os meses estão acima da margem de segurança mínima.")
    for alerta in alertas:
        (st.error if alerta.nivel == "critico" else st.warning)(alerta.mensagem)

# ---------------------------------------------------------------- DRE
with aba_dre:
    def _destacar(linha: pd.Series) -> list[str]:
        if linha.name != "Margem de Segurança (%)":
            return [""] * len(linha)
        return [f"background-color: #FFC7CE; color: {VERMELHO}; font-weight: bold"
                if (pd.isna(m) or m < limite) else "background-color: #C6EFCE"
                for m in dre["margem_seguranca"]]

    tabela = formatar_dre(dre)
    st.dataframe(tabela.style.apply(_destacar, axis=1), width="stretch", height=470)
    with st.expander("Lançamentos de origem"):
        st.dataframe(lancamentos, width="stretch", hide_index=True)

# ---------------------------------------------------------------- Capex
with aba_capex:
    esquerda, direita = st.columns([1, 2])
    with esquerda:
        investimento = st.number_input("Investimento inicial (R$)", 1000.0, 1e9,
                                       60000.0, 1000.0, format="%.2f")
        tma = st.slider("TMA (% a.a.)", 0.0, 30.0, 14.0, 0.5) / 100
        anos = st.slider("Horizonte (anos)", 1, 10, 5)
        padrao = [18000, 22000, 25000, 28000, 30000]
        sugeridos = (padrao + [padrao[-1]] * 10)[:anos]
        tabela_fluxos = st.data_editor(
            pd.DataFrame({"Ano": range(1, anos + 1), "Fluxo (R$)": sugeridos}),
            hide_index=True, disabled=["Ano"], width="stretch", key=f"fluxos_{anos}")
    fluxos = tabela_fluxos["Fluxo (R$)"].fillna(0).astype(float).tolist()
    resultado = analisar_projeto(investimento, fluxos, tma)
    st.session_state["viabilidade"] = resultado

    with direita:
        m1, m2 = st.columns(2)
        m3, m4 = st.columns(2)
        m1.metric("VPL", fmt.moeda(resultado.vpl))
        m2.metric("TIR", fmt.percentual(resultado.tir))
        m3.metric("Payback descontado", fmt.anos(resultado.payback_descontado))
        m4.metric("Índice de lucratividade", f"{resultado.indice_lucratividade:.2f}")
        (st.success if resultado.viavel else st.error)(resultado.parecer)

        saldo = [-investimento]
        for valor in resultado.fluxos_descontados:
            saldo.append(saldo[-1] + valor)
        g1 = go.Figure(go.Bar(
            x=list(range(len(saldo))), y=saldo,
            marker_color=[VERMELHO if s < 0 else VERDE for s in saldo],
            hovertemplate="Ano %{x}<br>R$ %{y:,.2f}<extra></extra>"))
        g1.update_layout(title="Saldo acumulado descontado (payback)", xaxis_title="Ano",
                         yaxis_title="R$", height=300, separators=",.",
                         margin=dict(t=50, b=20))
        st.plotly_chart(g1, width="stretch")

        sens = sensibilidade_tma(investimento, fluxos)
        g2 = go.Figure(go.Scatter(x=sens["tma"] * 100, y=sens["vpl"], mode="lines",
                                  line=dict(color=AZUL, width=3),
                                  hovertemplate="TMA %{x:.0f}%<br>VPL R$ %{y:,.2f}<extra></extra>"))
        g2.add_hline(y=0, line_color=CINZA)
        g2.add_vline(x=tma * 100, line_dash="dash", line_color=VERMELHO,
                     annotation_text="TMA atual")
        g2.update_layout(title="Sensibilidade do VPL à TMA (cruza o zero na TIR)",
                         xaxis_title="TMA (%)", yaxis_title="VPL (R$)", height=300,
                         separators=",.", margin=dict(t=50, b=20))
        st.plotly_chart(g2, width="stretch")

# ---------------------------------------------------------------- IA local
with aba_ia:
    st.markdown(
        "O parecer é gerado por um modelo de linguagem **rodando nesta máquina** "
        "via Ollama. Nenhum número da empresa é enviado para a internet.")
    prompt = montar_prompt_cfo(dre, resumo, alertas, st.session_state.get("viabilidade"))
    try:
        cliente = ClienteOllama(url_ollama, modelo)
    except ValueError as erro:
        st.error(str(erro))
        cliente = None

    if cliente is not None:
        online = cliente.disponivel()
        if online:
            st.success(f"Ollama conectado em {url_ollama}")
        else:
            st.warning("Ollama não encontrado. Instale em ollama.com e rode "
                       f"`ollama pull {modelo}` e `ollama serve`.")
        if st.button("Gerar parecer do CFO Virtual", type="primary", disabled=not online):
            with st.spinner("O modelo local está analisando a DRE…"):
                try:
                    st.session_state["parecer"] = cliente.gerar(prompt)
                except ErroIALocal as erro:
                    st.error(str(erro))
    if st.session_state.get("parecer"):
        st.markdown(st.session_state["parecer"])
    with st.expander("Ver o prompt estruturado enviado ao modelo"):
        st.code(prompt, language="markdown")

# ---------------------------------------------------------------- exportação
with aba_export:
    st.markdown(
        "Planilha executiva com a DRE em fórmulas vivas, alerta vermelho de margem de "
        "segurança, gráfico, análise de Capex, alertas e o parecer da IA (se gerado).")
    buffer = BytesIO()
    exportar_relatorio(dre, lancamentos, buffer, alertas,
                       st.session_state.get("viabilidade"),
                       st.session_state.get("parecer"), limite)
    st.download_button("Baixar relatório Excel", buffer.getvalue(),
                       file_name=f"relatorio_fpa_{dre.index[-1]}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       type="primary")
