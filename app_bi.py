import streamlit as st
import pandas as pd
import json
import plotly.express as px
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from pathlib import Path

st.set_page_config(page_title="GlobalShop BI Dashboard", layout="wide", page_icon="🛒")

st.markdown("""
<style>
    [data-testid="metric-container"] { background: #1e2130; border-radius: 10px; padding: 12px; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    data_path = Path(__file__).resolve().parent / "03_implementacao" / "dataset_exemplo.json"
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = []
    for item in data:
        rows.append({
            "review_id": item["review_id"],
            "product_name": item["product"]["name"],
            "category": item["product"]["category"],
            "brand": item["product"]["brand"],
            "customer_location": item["customer"]["location"],
            "membership": item["customer"]["membership"],
            "rating": item["rating"],
            "sentiment": item["sentiment"],
            "keywords": item["keywords"],
            "timestamp": pd.to_datetime(item["timestamp"]),
            "verified_purchase": item.get("verified_purchase", True),
        })
    df = pd.DataFrame(rows)
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)
    return df


df = load_data()

SENTIMENT_COLORS = {"Positive": "#2ecc71", "Neutral": "#95a5a6", "Negative": "#e74c3c"}

# --- SIDEBAR ---
st.sidebar.title("🛒 GlobalShop BI")
st.sidebar.markdown("---")
st.sidebar.header("🔎 Filtros")

selected_cat = st.sidebar.multiselect(
    "Categoria", options=sorted(df["category"].unique()), default=sorted(df["category"].unique())
)
selected_mem = st.sidebar.multiselect(
    "Membership", options=sorted(df["membership"].unique()), default=sorted(df["membership"].unique())
)
selected_loc = st.sidebar.multiselect(
    "Localização", options=sorted(df["customer_location"].unique()), default=sorted(df["customer_location"].unique())
)

filtered_df = df[
    df["category"].isin(selected_cat)
    & df["membership"].isin(selected_mem)
    & df["customer_location"].isin(selected_loc)
]

# --- HEADER ---
st.title("🛒 GlobalShop: Sentiment Intelligence Dashboard")
st.caption("Sistema de Suporte à Decisão (DSS) v2.0  |  Powered by MongoDB + Streamlit")
st.markdown("---")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Visão Executiva", "🏷️ Análise Tática", "🔍 Análise Operacional"])

# =============================================================
# TAB 1 — VISÃO EXECUTIVA
# =============================================================
with tab1:
    n = len(filtered_df)

    pos_count = (filtered_df["sentiment"] == "Positive").sum()
    neg_count = (filtered_df["sentiment"] == "Negative").sum()
    pos_pct = pos_count / n * 100 if n > 0 else 0
    neg_pct = neg_count / n * 100 if n > 0 else 0
    nss = pos_pct - neg_pct
    avg_rating = filtered_df["rating"].mean() if n > 0 else 0
    verified_pct = filtered_df["verified_purchase"].sum() / n * 100 if n > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Net Sentiment Score (NSS)",
        f"{nss:.1f}%",
        delta="Saudável ✔" if nss >= 0 else "Alerta ✘",
        delta_color="normal" if nss >= 0 else "inverse",
    )
    col2.metric("Total de Reviews", n)
    col3.metric("Nota Média Global", f"{avg_rating:.2f} ⭐")
    col4.metric("Compras Verificadas", f"{verified_pct:.0f}%")

    st.markdown("---")

    row1c1, row1c2 = st.columns([1, 2])

    with row1c1:
        st.subheader("Distribuição de Sentimento")
        sent_counts = filtered_df["sentiment"].value_counts().reset_index()
        sent_counts.columns = ["Sentimento", "Quantidade"]
        fig_pie = px.pie(
            sent_counts,
            names="Sentimento",
            values="Quantidade",
            color="Sentimento",
            color_discrete_map=SENTIMENT_COLORS,
            hole=0.45,
        )
        fig_pie.update_layout(margin=dict(t=10, b=10, l=0, r=0), showlegend=True)
        st.plotly_chart(fig_pie, use_container_width=True)

    with row1c2:
        st.subheader("Tendência de Nota Média por Mês")
        trend = filtered_df.groupby("month")["rating"].mean().reset_index()
        trend.columns = ["Mês", "Nota Média"]
        fig_trend = px.line(
            trend, x="Mês", y="Nota Média", markers=True,
            color_discrete_sequence=["#3498db"],
        )
        fig_trend.add_hline(
            y=3.0, line_dash="dash", line_color="#e74c3c", annotation_text="Limite Crítico (3.0)"
        )
        fig_trend.update_layout(yaxis_range=[0, 5.5])
        st.plotly_chart(fig_trend, use_container_width=True)

# =============================================================
# TAB 2 — ANÁLISE TÁTICA
# =============================================================
with tab2:
    st.subheader("📊 Distribuição de Sentimento por Categoria")
    fig_bar = px.histogram(
        filtered_df, x="category", color="sentiment", barmode="group",
        color_discrete_map=SENTIMENT_COLORS,
        labels={"category": "Categoria", "count": "Quantidade", "sentiment": "Sentimento"},
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.subheader("⚠️ Top 10 Produtos Críticos (Rating Baixo)")
        prod_ranking = (
            filtered_df.groupby("product_name")["rating"]
            .mean()
            .sort_values()
            .head(10)
            .reset_index()
        )
        prod_ranking.columns = ["Produto", "Nota Média"]
        fig_prod = px.bar(
            prod_ranking, x="Nota Média", y="Produto", orientation="h",
            color="Nota Média", color_continuous_scale="RdYlGn", range_x=[0, 5],
        )
        st.plotly_chart(fig_prod, use_container_width=True)

    with col_t2:
        st.subheader("🏷️ Performance por Marca")
        brand_stats = (
            filtered_df.groupby("brand")
            .agg(
                nota_media=("rating", "mean"),
                total=("review_id", "count"),
                nss_val=(
                    "sentiment",
                    lambda x: ((x == "Positive").sum() - (x == "Negative").sum()) / len(x) * 100,
                ),
            )
            .reset_index()
            .sort_values("nota_media", ascending=False)
        )
        fig_brand = px.bar(
            brand_stats, x="brand", y="nota_media",
            color="nss_val", color_continuous_scale="RdYlGn",
            labels={"brand": "Marca", "nota_media": "Nota Média", "nss_val": "NSS (%)"},
            text=brand_stats["total"].apply(lambda x: f"{x} rev."),
        )
        fig_brand.update_traces(textposition="outside")
        fig_brand.update_layout(yaxis_range=[0, 6])
        st.plotly_chart(fig_brand, use_container_width=True)

# =============================================================
# TAB 3 — ANÁLISE OPERACIONAL
# =============================================================
with tab3:
    col_op1, col_op2 = st.columns(2)

    with col_op1:
        st.subheader("📍 Nota Média por Localização")
        loc_stats = (
            filtered_df.groupby("customer_location")["rating"]
            .mean()
            .sort_values(ascending=False)
            .reset_index()
        )
        loc_stats.columns = ["Localização", "Nota Média"]
        fig_loc = px.bar(
            loc_stats, x="Nota Média", y="Localização", orientation="h",
            color="Nota Média", color_continuous_scale="RdYlGn", range_x=[0, 5],
        )
        st.plotly_chart(fig_loc, use_container_width=True)

    with col_op2:
        st.subheader("☁️ Causa Raiz — Keywords Negativas")
        all_neg_kw = []
        for kw_list in filtered_df[filtered_df["sentiment"] == "Negative"]["keywords"]:
            all_neg_kw.extend(kw_list)

        if all_neg_kw:
            text = " ".join(all_neg_kw)
            wc = WordCloud(
                width=700, height=350, background_color="white", colormap="Reds"
            ).generate(text)
            fig_wc, ax = plt.subplots(figsize=(7, 3.5))
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig_wc)
            plt.close(fig_wc)
        else:
            st.info("Nenhuma keyword negativa para os filtros selecionados.")

    st.markdown("---")
    st.subheader("📋 Frequência de Problemas Identificados (Top Keywords Negativas)")

    if all_neg_kw:
        kw_freq = Counter(all_neg_kw).most_common(10)
        kw_df = pd.DataFrame(kw_freq, columns=["Keyword", "Frequência"])
        fig_kw = px.bar(
            kw_df, x="Frequência", y="Keyword", orientation="h",
            color="Frequência", color_continuous_scale="Reds",
        )
        st.plotly_chart(fig_kw, use_container_width=True)

st.markdown("---")
st.caption("GlobalShop DSS — Sistema de Suporte à Decisão v2.0  |  Powered by MongoDB & Streamlit")
