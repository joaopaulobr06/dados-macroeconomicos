import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from anthropic import Anthropic

# ---------- Configuração — troque os valores abaixo pelos seus ----------
st.set_page_config(page_title="Mercado Pecuário — Indicadores Macro", layout="wide")

DB_HOST = st.secrets["DB_HOST"]
DB_NAME = st.secrets["DB_NAME"]
DB_PORT = st.secrets["DB_PORT"]
DB_USER = st.secrets["DB_USER"]
DB_PASSWORD = st.secrets["DB_PASSWORD"]
IA_DB_USER = st.secrets["IA_DB_USER"]
IA_DB_PASSWORD = st.secrets["IA_DB_PASSWORD"]
CLAUDE_API_KEY = st.secrets["CLAUDE_API_KEY"].strip()
# --------------------------------------------------------------------

client = Anthropic(api_key=CLAUDE_API_KEY)

NOMES_INDICADORES = {
    "cambio_usd": "Câmbio (USD/BRL)",
    "selic": "Selic",
    "ipca": "IPCA",
    "balanca_comercial": "Balança Comercial",
}
UNIDADE_INDICADORES = {
    "cambio_usd": "R$",
    "selic": "% a.a.",
    "ipca": "%",
    "balanca_comercial": "US$ mi",
}
FREQUENCIA_INDICADORES = {
    "cambio_usd": "dia anterior",
    "selic": "dia anterior",
    "ipca": "mês anterior",
    "balanca_comercial": "mês anterior",
}
CORES_INDICADORES = {
    "cambio_usd": "#49AC62",
    "selic": "#B47432",
    "ipca": "#E0C611",
    "balanca_comercial": "#52350C",
}

COR_TEXTO = "#52350C"

ESQUEMA = """
Tabela: indicadores_macro
Colunas:
- data (DATE): data do valor
- indicador (TEXT): um de 'cambio_usd', 'selic', 'ipca', 'balanca_comercial'
- valor (NUMERIC): valor do indicador naquela data
"""

# ---------- Visual ----------
st.markdown(f"""
<style>
html, body, [class*="css"]  {{
    font-family: 'Arial Narrow', Arial, sans-serif !important;
    font-size: 16px;
    color: {COR_TEXTO} !important;
}}
h1, h2, h3, h4, p, span, div, label {{
    color: {COR_TEXTO} !important;
}}
.stApp {{ background-color: #FDFDFD; }}

.titulo-principal {{
    font-size: 40px;
    font-weight: 700;
    color: {COR_TEXTO};
    margin-bottom: 0;
    font-family: 'Arial Narrow', Arial, sans-serif;
}}
.subtitulo-principal {{
    font-size: 20px;
    color: {COR_TEXTO};
    margin-top: 2px;
    margin-bottom: 8px;
}}
.divisor-dourado {{
    border: none;
    height: 3px;
    background-color: #E0C611;
    margin: 6px 0 28px 0;
}}

.kpi-card {{
    background: #FFFFFF;
    border: 1.5px solid #B47432;
    border-radius: 10px;
    padding: 22px 24px;
}}
.kpi-titulo {{ font-size: 14px; text-transform: uppercase; letter-spacing: 0.03em; }}
.kpi-valor {{ font-size: 27px; font-weight: 700; margin-top: 6px; }}
.kpi-unidade {{ font-size: 14px; margin-left: 4px; }}
.kpi-variacao-up {{ color: #2D6A4F !important; font-size: 14px; margin-top: 6px; }}
.kpi-variacao-down {{ color: #B03A2E !important; font-size: 14px; margin-top: 6px; }}

div[data-testid="stPlotlyChart"] {{
    border: 1.5px solid #B47432;
    border-radius: 10px;
    padding: 10px;
    background-color: #FFFFFF;
}}

.fonte-grafico {{ font-size: 12px; margin-top: 6px; opacity: 0.75; }}
</style>
""", unsafe_allow_html=True)

# ---------- Funções de dados ----------
@st.cache_data(ttl=300)
def carregar_dados():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT)
    df = pd.read_sql("SELECT data, indicador, valor FROM indicadores_macro ORDER BY data", conn)
    conn.close()
    df["data"] = pd.to_datetime(df["data"])
    return df

def fmt_numero(valor, casas=2):
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")

def fmt_data(data):
    return pd.to_datetime(data).strftime("%d/%m/%Y")

def cartao_kpi(titulo, valor_formatado, unidade, variacao=None, freq_label="período anterior"):
    variacao_html = ""
    if variacao is not None:
        classe = "kpi-variacao-up" if variacao >= 0 else "kpi-variacao-down"
        sinal = "+" if variacao >= 0 else "-"
        variacao_html = f'<div class="{classe}">{sinal} {abs(variacao):.2f}% vs. {freq_label}</div>'
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-titulo">{titulo}</div>
        <div class="kpi-valor">{valor_formatado}<span class="kpi-unidade">{unidade}</span></div>
        {variacao_html}
    </div>
    """, unsafe_allow_html=True)

def calcular_range_eixo(valores):
    minimo, maximo = valores.min(), valores.max()
    if maximo == minimo:
        margem = abs(maximo) * 0.05 or 1
    else:
        margem = (maximo - minimo) * 0.12
    return [minimo - margem, maximo + margem]

def grafico_indicador(df_ind, nome, cor, unidade, altura=380):
    fig = px.line(df_ind, x="data", y="valor", markers=True, title=nome)
    fig.update_traces(line_color=cor, line_width=2.8, marker=dict(color=cor, size=6))
    fig.update_layout(
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font_family="Arial Narrow", font_size=14, font_color=COR_TEXTO,
        title_font_size=19, title_font_color=COR_TEXTO,
        xaxis_title="Data", yaxis_title=unidade,
        margin=dict(l=10, r=10, t=48, b=10),
        height=altura,
    )
    fig.update_yaxes(range=calcular_range_eixo(df_ind["valor"]), gridcolor="#F0EDE6")
    fig.update_xaxes(
        rangeselector=dict(
            buttons=[
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="1A", step="year", stepmode="backward"),
                dict(count=5, label="5A", step="year", stepmode="backward"),
                dict(step="all", label="Máx"),
            ],
            font=dict(size=12, color=COR_TEXTO), bgcolor="#FDFDFD", activecolor="#E0C611",
        ),
    )
    return fig

# ---------- Funções de IA ----------
def gerar_sql(pergunta):
    prompt = f"""Você converte perguntas em português sobre dados macroeconômicos em consultas SQL para PostgreSQL.

Esquema do banco:
{ESQUEMA}

Regras:
- Responda APENAS com o SQL puro, sem explicação, sem markdown, sem ponto e vírgula no final.
- Use apenas SELECT. Nunca gere INSERT, UPDATE, DELETE, DROP ou ALTER.
- Sempre inclua um LIMIT 200 se a pergunta não pedir uma quantidade específica de linhas.

Pergunta: {pergunta}
SQL:"""
    resposta = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    sql = ""
    for bloco in resposta.content:
        if bloco.type == "text":
            sql = bloco.text
            break
    sql = sql.replace("```sql", "").replace("```", "").strip()
    sql = sql.rstrip(";").strip()
    return sql

def eh_sql_seguro(sql):
    sql_lower = sql.lower()
    if not sql_lower.strip().startswith("select"):
        return False
    proibidas = ["insert", "update", "delete", "drop", "alter", "truncate", "grant", "revoke", ";"]
    return not any(p in sql_lower for p in proibidas)

def executar_sql(sql):
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=IA_DB_USER, password=IA_DB_PASSWORD, port=DB_PORT)
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

def gerar_resposta_texto(pergunta, df_resultado):
    dados_texto = df_resultado.to_string(index=False)
    prompt = f"""Você é um analista respondendo em português sobre dados macroeconômicos brasileiros.

Pergunta original: {pergunta}

Dados retornados pela consulta ao banco (única fonte de verdade — não invente nenhum valor fora daqui):
{dados_texto}

Escreva uma resposta curta e direta em português, citando os números exatos presentes nos dados acima.
Use vírgula como separador decimal (padrão brasileiro). Mencione médias, valor mais recente ou variação
quando fizer sentido para a pergunta. Não use markdown, apenas texto corrido."""
    resposta = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    for bloco in resposta.content:
        if bloco.type == "text":
            return bloco.text.strip()
    return "Não consegui gerar uma resposta em texto para essa consulta."

# ---------- Interface ----------
st.markdown('<div class="titulo-principal">Mercado Pecuário</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo-principal">Indicadores macroeconômicos atualizados diariamente</div>',
            unsafe_allow_html=True)
st.markdown('<hr class="divisor-dourado">', unsafe_allow_html=True)

aba_dashboard, aba_perguntas = st.tabs(["Dashboard", "Perguntas (IA)"])

with aba_dashboard:
    df = carregar_dados()

    colunas_kpi = st.columns(len(NOMES_INDICADORES))
    for i, (codigo, nome) in enumerate(NOMES_INDICADORES.items()):
        df_ind = df[df["indicador"] == codigo].sort_values("data")
        if len(df_ind) == 0:
            continue
        valor_atual = df_ind["valor"].iloc[-1]
        variacao = None
        if len(df_ind) > 1:
            valor_anterior = df_ind["valor"].iloc[-2]
            variacao = ((valor_atual - valor_anterior) / valor_anterior) * 100
        with colunas_kpi[i]:
            cartao_kpi(nome, fmt_numero(valor_atual), UNIDADE_INDICADORES[codigo],
                       variacao, FREQUENCIA_INDICADORES[codigo])

    st.write("")

    codigos = list(NOMES_INDICADORES.keys())
    linha1 = st.columns(2)
    linha2 = st.columns(2)
    posicoes = linha1 + linha2

    for i, codigo in enumerate(codigos):
        df_ind = df[df["indicador"] == codigo].sort_values("data")
        with posicoes[i]:
            fig = grafico_indicador(df_ind, NOMES_INDICADORES[codigo], CORES_INDICADORES[codigo],
                                     UNIDADE_INDICADORES[codigo])
            st.plotly_chart(fig, use_container_width=True, key=f"grafico_{codigo}")
            st.markdown('<div class="fonte-grafico">Fonte: Banco Central do Brasil (SGS)</div>',
                        unsafe_allow_html=True)

    with st.expander("Ver dados brutos"):
        escolha_tabela = st.selectbox("Indicador", codigos, format_func=lambda c: NOMES_INDICADORES[c])
        df_exibir = df[df["indicador"] == escolha_tabela].copy().sort_values("data", ascending=False)
        df_exibir["data"] = df_exibir["data"].apply(fmt_data)
        df_exibir["valor"] = df_exibir["valor"].apply(fmt_numero)
        st.dataframe(df_exibir[["data", "valor"]], use_container_width=True, hide_index=True)

with aba_perguntas:
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = []

    col_titulo, col_botao = st.columns([5, 1])
    with col_titulo:
        st.markdown("#### Pergunte sobre os dados")
    with col_botao:
        if st.button("Nova conversa"):
            st.session_state.mensagens = []
            st.rerun()

    if len(st.session_state.mensagens) == 0:
        st.markdown("Comece com uma sugestão, ou digite sua própria pergunta ali embaixo:")
        sugestoes = [
            "Qual foi o valor do dólar nos últimos 7 dias?",
            "Qual a média da Selic no último mês?",
            "Como o IPCA variou nas últimas 10 datas?",
        ]
        cols = st.columns(len(sugestoes))
        pergunta_clicada = None
        for i, s in enumerate(sugestoes):
            if cols[i].button(s, use_container_width=True):
                pergunta_clicada = s
    else:
        pergunta_clicada = None

    for idx, msg in enumerate(st.session_state.mensagens):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("fig") is not None:
                st.plotly_chart(msg["fig"], use_container_width=True, key=f"chat_fig_{idx}")
            if msg["role"] == "assistant" and msg.get("sql"):
                with st.expander("Ver detalhes técnicos (SQL e dados brutos)"):
                    st.code(msg["sql"], language="sql")
                    st.dataframe(msg["df"], use_container_width=True)

    pergunta = st.chat_input("Digite sua pergunta") or pergunta_clicada

    if pergunta:
        st.session_state.mensagens.append({"role": "user", "content": pergunta})

        with st.spinner("Consultando os dados..."):
            sql = gerar_sql(pergunta)

            if not eh_sql_seguro(sql):
                nova_msg = {
                    "role": "assistant",
                    "content": "A consulta gerada não passou na checagem de segurança. Tente reformular a pergunta.",
                }
            else:
                try:
                    resultado = executar_sql(sql)
                    resposta_texto = gerar_resposta_texto(pergunta, resultado)

                    fig = None
                    if "data" in resultado.columns and "valor" in resultado.columns and len(resultado) > 1:
                        fig = px.line(resultado, x="data", y="valor", markers=True)
                        fig.update_traces(line_color="#49AC62", line_width=2.8,
                                           marker=dict(color="#49AC62", size=6))
                        fig.update_layout(
                            plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                            font_family="Arial Narrow", font_size=14, font_color=COR_TEXTO,
                            xaxis_title="Data", yaxis_title="Valor",
                            margin=dict(l=10, r=10, t=20, b=10), height=340,
                        )
                        fig.update_yaxes(range=calcular_range_eixo(resultado["valor"]), gridcolor="#F0EDE6")

                    nova_msg = {
                        "role": "assistant",
                        "content": resposta_texto,
                        "sql": sql,
                        "df": resultado,
                        "fig": fig,
                    }
                except Exception as e:
                    nova_msg = {"role": "assistant", "content": f"Erro ao executar a consulta: {e}"}

        st.session_state.mensagens.append(nova_msg)
        st.rerun()
