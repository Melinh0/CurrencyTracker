# ============================================
# CurrencyTracker - Streamlit Dashboard
# ============================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
import asyncio
from decimal import Decimal

# Configuração da página
st.set_page_config(
    page_title="CurrencyTracker Dashboard",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .positive { color: #00cc00; }
    .negative { color: #ff4444; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 0 20px;
        background-color: #f0f2f6;
        border-radius: 4px 4px 0 0;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff;
        border-bottom: 2px solid #ff4b4b;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# Configuração e Helpers
# ============================================

API_BASE_URL = "http://localhost:8000/api/v1"

@st.cache_data(ttl=60)
def fetch_latest_rates(base: str = "BRL") -> List[Dict]:
    """Busca taxas mais recentes da API"""
    try:
        response = requests.get(f"{API_BASE_URL}/rates/latest", params={"base": base}, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Erro ao buscar taxas: {e}")
        return []


@st.cache_data(ttl=300)
def fetch_rate_history(base: str, quote: str, days: int = 30) -> List[Dict]:
    """Busca histórico de taxas"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        response = requests.post(
            f"{API_BASE_URL}/rates/history",
            json={
                "base": base,
                "quote": quote,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "limit": 1000
            },
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Erro ao buscar histórico: {e}")
        return []


@st.cache_data(ttl=300)
def fetch_statistics(base: str, quote: str, days: int = 30) -> Dict:
    """Busca estatísticas"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/rates/statistics/{quote}",
            params={"base": base, "days": days},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception:
        return {}


@st.cache_data(ttl=300)
def fetch_prediction(base: str, quote: str, horizon: int = 7) -> Dict:
    """Busca previsão"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/predictions/predict",
            json={"base": base, "quote": quote, "horizon_days": horizon},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        st.error(f"Erro ao buscar previsão: {e}")
        return {}


@st.cache_data(ttl=600)
def fetch_currencies() -> List[Dict]:
    """Busca lista de moedas"""
    try:
        response = requests.get(f"{API_BASE_URL}/currencies/", timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def format_rate(rate: float, decimals: int = 4) -> str:
    """Formata taxa para exibição"""
    return f"{rate:.{decimals}f}"


def format_change(current: float, previous: float) -> str:
    """Formata variação percentual"""
    if previous == 0:
        return "N/A"
    pct = ((current - previous) / previous) * 100
    color = "positive" if pct >= 0 else "negative"
    arrow = "▲" if pct >= 0 else "▼"
    return f'<span class="{color}">{arrow} {abs(pct):.2f}%</span>'


# ============================================
# Sidebar
# ============================================

def render_sidebar():
    """Renderiza sidebar com configurações"""
    with st.sidebar:
        st.image("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4b0.png", width=60)
        st.title("CurrencyTracker")
        st.caption("Monitor de Câmbio & Previsões")

        st.divider()

        # Configurações
        st.subheader("⚙️ Configurações")

        currencies = fetch_currencies()
        currency_codes = [c["code"] for c in currencies] if currencies else ["BRL", "USD", "EUR", "GBP", "JPY"]

        base_currency = st.selectbox(
            "Moeda Base",
            options=currency_codes,
            index=currency_codes.index("BRL") if "BRL" in currency_codes else 0
        )

        quote_currency = st.selectbox(
            "Moeda Cotação",
            options=[c for c in currency_codes if c != base_currency],
            index=0
        )

        time_range = st.selectbox(
            "Período",
            options=["7d", "30d", "90d", "180d", "1y"],
            index=1
        )

        days_map = {"7d": 7, "30d": 30, "90d": 90, "180d": 180, "1y": 365}
        days = days_map[time_range]

        prediction_horizon = st.slider(
            "Horizonte de Previsão (dias)",
            min_value=1, max_value=30, value=7
        )

        st.divider()

        # Status da API
        st.subheader("📡 Status")
        try:
            health = requests.get(f"{API_BASE_URL}/health/", timeout=5)
            if health.status_code == 200:
                data = health.json()
                st.success(f"API: {data['status'].upper()}")
                for service, status in data.get("services", {}).items():
                    icon = "✅" if status else "❌"
                    st.caption(f"{icon} {service}")
            else:
                st.error("API: OFFLINE")
        except Exception:
            st.error("API: INALCANÇÁVEL")

        st.divider()
        st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")

        if st.button("🔄 Atualizar Dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    return base_currency, quote_currency, days, prediction_horizon


# ============================================
# Páginas
# ============================================

def render_overview(base: str, quote: str, days: int):
    """Página de visão geral"""
    st.header(f"📊 Visão Geral: {base}/{quote}")

    # Busca dados
    rates = fetch_latest_rates(base)
    pair_data = next((r for r in rates if r["quote"] == quote), None)

    if not pair_data:
        st.warning(f"Dados não disponíveis para {base}/{quote}")
        return

    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)

    current_rate = pair_data["rate"]
    bid = pair_data.get("bid")
    ask = pair_data.get("ask")
    spread = pair_data.get("spread")

    with col1:
        st.metric(
            "Taxa Atual",
            format_rate(current_rate),
            delta=None
        )

    with col2:
        if bid and ask:
            st.metric("Compra (Bid)", format_rate(bid))
        else:
            st.metric("Compra (Bid)", "N/A")

    with col3:
        if bid and ask:
            st.metric("Venda (Ask)", format_rate(ask))
        else:
            st.metric("Venda (Ask)", "N/A")

    with col4:
        if spread:
            st.metric("Spread", f"{spread:.2f}%")
        else:
            st.metric("Spread", "N/A")

    st.caption(f"Fonte: {pair_data['source']} | Atualizado: {pair_data['timestamp'][:19]}")

    # Histórico e gráfico
    history = fetch_rate_history(base, quote, days)

    if history:
        df = pd.DataFrame(history)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

        # Gráfico principal
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            subplot_titles=(f"Taxa {base}/{quote}", "Variação Diária (%)")
        )

        # Linha de taxa
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["rate"],
                mode="lines",
                name="Taxa",
                line=dict(color="#1f77b4", width=1.5),
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.4f}<extra></extra>"
            ),
            row=1, col=1
        )

        # Bandas de Bollinger (simplificado)
        df["sma_20"] = df["rate"].rolling(20).mean()
        df["std_20"] = df["rate"].rolling(20).std()
        df["upper"] = df["sma_20"] + 2 * df["std_20"]
        df["lower"] = df["sma_20"] - 2 * df["std_20"]

        fig.add_trace(
            go.Scatter(
                x=df["timestamp"], y=df["upper"],
                mode="lines", name="BB Superior",
                line=dict(color="rgba(0,100,200,0.3)", width=1),
                showlegend=False
            ), row=1, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"], y=df["lower"],
                mode="lines", name="BB Inferior",
                line=dict(color="rgba(0,100,200,0.3)", width=1),
                fill="tonexty", fillcolor="rgba(0,100,200,0.1)",
                showlegend=False
            ), row=1, col=1
        )

        # Variação diária
        df["pct_change"] = df["rate"].pct_change() * 100
        colors = ["green" if v >= 0 else "red" for v in df["pct_change"].fillna(0)]

        fig.add_trace(
            go.Bar(
                x=df["timestamp"],
                y=df["pct_change"],
                name="Var. %",
                marker_color=colors,
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.2f}%<extra></extra>"
            ),
            row=2, col=1
        )

        fig.update_layout(
            height=600,
            showlegend=True,
            hovermode="x unified",
            xaxis_rangeslider_visible=False
        )
        fig.update_yaxes(title_text="Taxa", row=1, col=1)
        fig.update_yaxes(title_text="%", row=2, col=1)

        st.plotly_chart(fig, use_container_width=True)

        # Estatísticas
        stats = fetch_statistics(base, quote, days)
        if stats:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Média", format_rate(stats.get("avg_rate", 0)))
            with col2:
                st.metric("Mínima", format_rate(stats.get("min_rate", 0)))
            with col3:
                st.metric("Máxima", format_rate(stats.get("max_rate", 0)))
            with col4:
                st.metric("Desvio Padrão", format_rate(stats.get("stddev_rate", 0), 6))
    else:
        st.info("Sem dados históricos disponíveis")


def render_comparison(base: str, days: int):
    """Página de comparação entre moedas"""
    st.header(f"🔄 Comparação vs {base}")

    rates = fetch_latest_rates(base)

    if not rates:
        st.warning("Nenhuma taxa disponível")
        return

    # Tabela de taxas atuais
    df_rates = pd.DataFrame(rates)

    # Busca variação histórica para cada moeda
    changes = []
    for _, row in df_rates.iterrows():
        quote = row["quote"]
        history = fetch_rate_history(base, quote, min(days, 30))
        if history:
            h_df = pd.DataFrame(history)
            h_df["timestamp"] = pd.to_datetime(h_df["timestamp"])
            h_df = h_df.sort_values("timestamp")
            if len(h_df) > 1:
                first = h_df.iloc[0]["rate"]
                last = h_df.iloc[-1]["rate"]
                pct = ((last - first) / first) * 100
                changes.append({"quote": quote, "change_pct": pct, "current": last})
            else:
                changes.append({"quote": quote, "change_pct": 0, "current": row["rate"]})
        else:
            changes.append({"quote": quote, "change_pct": 0, "current": row["rate"]})

    df_changes = pd.DataFrame(changes)
    df_merged = df_rates.merge(df_changes, on="quote")

    # Ordena por variação
    df_merged = df_merged.sort_values("change_pct", ascending=False)

    # Gráfico de barras horizontais
    fig = go.Figure()

    colors = ["green" if v >= 0 else "red" for v in df_merged["change_pct"]]

    fig.add_trace(go.Bar(
        y=df_merged["quote"],
        x=df_merged["change_pct"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.2f}%" for v in df_merged["change_pct"]],
        textposition="auto",
        hovertemplate="%{y}: %{x:.2f}%<extra></extra>"
    ))

    fig.update_layout(
        title=f"Variação nos últimos {days} dias vs {base}",
        xaxis_title="Variação (%)",
        yaxis_title="Moeda",
        height=max(400, len(df_merged) * 30),
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)

    # Tabela detalhada
    st.subheader("Detalhes")
    display_df = df_merged[["quote", "rate", "bid", "ask", "spread", "change_pct", "source"]].copy()
    display_df.columns = ["Moeda", "Taxa", "Compra", "Venda", "Spread %", "Var. %", "Fonte"]
    display_df["Var. %"] = display_df["Var. %"].apply(lambda x: f"{x:+.2f}%")
    display_df["Spread %"] = display_df["Spread %"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Taxa": st.column_config.NumberColumn(format="%.4f"),
            "Compra": st.column_config.NumberColumn(format="%.4f"),
            "Venda": st.column_config.NumberColumn(format="%.4f"),
        }
    )


def render_predictions(base: str, quote: str, horizon: int):
    """Página de previsões"""
    st.header(f"🔮 Previsão: {base}/{quote} ({horizon} dias)")

    with st.spinner("Gerando previsão..."):
        prediction = fetch_prediction(base, quote, horizon)

    if not prediction or "error" in prediction:
        st.error(prediction.get("error", "Erro ao gerar previsão"))
        st.info("Certifique-se de que existe um modelo treinado para este par.")
        return

    preds = prediction.get("predictions", [])

    if not preds:
        st.warning("Nenhuma previsão retornada")
        return

    # Exibe previsões
    df_pred = pd.DataFrame(preds)
    df_pred["date"] = pd.to_datetime(df_pred["date"])

    # Gráfico
    fig = go.Figure()

    # Previsão pontual
    fig.add_trace(go.Scatter(
        x=df_pred["date"],
        y=df_pred["predicted_rate"],
        mode="lines+markers",
        name="Previsão",
        line=dict(color="#ff7f0e", width=2),
        marker=dict(size=8)
    ))

    # Intervalo de confiança
    fig.add_trace(go.Scatter(
        x=df_pred["date"].tolist() + df_pred["date"].tolist()[::-1],
        y=df_pred["upper_bound"].tolist() + df_pred["lower_bound"].tolist()[::-1],
        fill="toself",
        fillcolor="rgba(255,127,14,0.2)",
        line=dict(color="rgba(255,127,14,0)"),
        name=f"IC {int(prediction['confidence_level']*100)}%",
        hoverinfo="skip"
    ))

    # Adiciona taxa atual como referência
    rates = fetch_latest_rates(base)
    current = next((r for r in rates if r["quote"] == quote), None)
    if current:
        fig.add_hline(
            y=current["rate"],
            line_dash="dash",
            line_color="gray",
            annotation_text=f"Atual: {current['rate']:.4f}",
            annotation_position="bottom right"
        )

    fig.update_layout(
        title=f"Previsão {base}/{quote} - Modelo: {prediction['model']}",
        xaxis_title="Data",
        yaxis_title="Taxa",
        height=500,
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Tabela de previsões
    st.subheader("Valores Previstos")
    display_df = df_pred[["date", "predicted_rate", "lower_bound", "upper_bound"]].copy()
    display_df.columns = ["Data", "Previsão", "Lim. Inferior", "Lim. Superior"]
    display_df["Data"] = display_df["Data"].dt.strftime("%d/%m/%Y")
    for col in ["Previsão", "Lim. Inferior", "Lim. Superior"]:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.4f}")

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Metadados
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Modelo", prediction["model"])
    with col2:
        st.metric("Horizonte", f"{prediction['horizon_days']} dias")
    with col3:
        st.metric("Confiança", f"{int(prediction['confidence_level']*100)}%")


def render_correlation(base: str, days: int):
    """Página de correlação entre moedas"""
    st.header(f"🔗 Correlação vs {base} ({days} dias)")

    rates = fetch_latest_rates(base)
    if not rates:
        st.warning("Dados não disponíveis")
        return

    quotes = [r["quote"] for r in rates]

    # Busca histórico para todas as moedas
    all_data = {}
    for quote in quotes:
        history = fetch_rate_history(base, quote, days)
        if history:
            df = pd.DataFrame(history)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").set_index("timestamp")["rate"]
            all_data[quote] = df

    if len(all_data) < 2:
        st.warning("Dados insuficientes para correlação")
        return

    # Combina em DataFrame único
    combined = pd.DataFrame(all_data)
    combined = combined.dropna()

    if len(combined) < 10:
        st.warning("Poucos pontos de dados para correlação confiável")
        return

    # Calcula correlação
    corr_matrix = combined.corr()

    # Heatmap
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.index,
        colorscale="RdBu",
        zmid=0,
        zmin=-1,
        zmax=1,
        text=np.round(corr_matrix.values, 2),
        texttemplate="%{text}",
        textfont={"size": 10},
        hoverongaps=False
    ))

    fig.update_layout(
        title=f"Matriz de Correlação ({days} dias)",
        height=600,
        width=700
    )

    st.plotly_chart(fig, use_container_width=True)

    # Correlação com moeda base (se houver)
    st.subheader("Correlação com USD (se disponível)")
    if "USD" in combined.columns:
        usd_corr = corr_matrix["USD"].drop("USD").sort_values(ascending=False)
        fig2 = go.Figure(go.Bar(
            y=usd_corr.index,
            x=usd_corr.values,
            orientation="h",
            marker_color=["green" if v > 0 else "red" for v in usd_corr.values],
            text=[f"{v:.3f}" for v in usd_corr.values],
            textposition="auto"
        ))
        fig2.update_layout(
            title="Correlação com USD",
            xaxis_title="Coeficiente",
            height=max(400, len(usd_corr) * 25)
        )
        st.plotly_chart(fig2, use_container_width=True)


def render_models(base: str, quote: str):
    """Página de modelos ML"""
    st.header(f"🤖 Modelos ML: {base}/{quote}")

    try:
        response = requests.get(f"{API_BASE_URL}/predictions/models", params={"target_currency": quote})
        if response.status_code == 200:
            models = response.json()

            if not models:
                st.info("Nenhum modelo treinado para esta moeda")
                return

            for model in models:
                with st.expander(f"{model['name']} (v{model['version']}) - {model['model_type']}"):
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Treino MAE", f"{model.get('train_mae', 0):.6f}" if model.get('train_mae') else "N/A")
                    with col2:
                        st.metric("Treino RMSE", f"{model.get('train_rmse', 0):.6f}" if model.get('train_rmse') else "N/A")
                    with col3:
                        st.metric("Val MAE", f"{model.get('val_mae', 0):.6f}" if model.get('val_mae') else "N/A")
                    with col4:
                        st.metric("Val RMSE", f"{model.get('val_rmse', 0):.6f}" if model.get('val_rmse') else "N/A")

                    st.caption(f"Status: {model['status']} | Ativo: {model['is_active']} | Produção: {model['is_production']}")
                    st.caption(f"Treinado: {model['trained_at'][:19] if model.get('trained_at') else 'N/A'}")

                    if model.get("hyperparameters"):
                        st.json(model["hyperparameters"])
        else:
            st.error("Erro ao buscar modelos")
    except Exception as e:
        st.error(f"Erro: {e}")


# ============================================
# Main App
# ============================================

def main():
    """Função principal do dashboard"""
    # Sidebar
    base_currency, quote_currency, days, prediction_horizon = render_sidebar()

    # Tabs principais
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Visão Geral",
        "🔄 Comparação",
        "🔮 Previsões",
        "🔗 Correlação",
        "🤖 Modelos"
    ])

    with tab1:
        render_overview(base_currency, quote_currency, days)

    with tab2:
        render_comparison(base_currency, days)

    with tab3:
        render_predictions(base_currency, quote_currency, prediction_horizon)

    with tab4:
        render_correlation(base_currency, days)

    with tab5:
        render_models(base_currency, quote_currency)


if __name__ == "__main__":
    main()