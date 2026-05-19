import logging
import os
from collections import Counter

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from wordcloud import WordCloud

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from globalshop_bi.data_access import load_dashboard_data


st.set_page_config(page_title="GlobalShop BI Dashboard", layout="wide", page_icon="🛒")

st.markdown("""
<style>
    [data-testid="metric-container"] { background: #1e2130; border-radius: 10px; padding: 12px; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)


def read_non_negative_int_env(name, default):
    try:
        return max(int(os.getenv(name, str(default))), 0)
    except ValueError:
        return default


DATA_CACHE_TTL_SECONDS = read_non_negative_int_env("DATA_CACHE_TTL_SECONDS", 60)
AUTO_REFRESH_SECONDS = read_non_negative_int_env("AUTO_REFRESH_SECONDS", 0)

try:
    CRITICAL_RATING_THRESHOLD = float(os.getenv("CRITICAL_RATING_THRESHOLD", "3.0"))
except ValueError:
    CRITICAL_RATING_THRESHOLD = 3.0


@st.cache_data(ttl=DATA_CACHE_TTL_SECONDS)
def load_data(data_source, mongo_uri, db_name, collection_name):
    return load_dashboard_data(data_source, mongo_uri, db_name, collection_name)


DATA_SOURCE = os.getenv("DATA_SOURCE", "auto")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "GlobalShop")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "reviews")

if st.sidebar.button("Atualizar dados"):
    load_data.clear()
    st.rerun()

if AUTO_REFRESH_SECONDS > 0:
    st_autorefresh(interval=AUTO_REFRESH_SECONDS * 1000, key="dashboard_auto_refresh")

try:
    df, active_source, source_message = load_data(DATA_SOURCE, MONGO_URI, MONGO_DB, MONGO_COLLECTION)
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

SENTIMENT_COLORS = {"Positive": "#2ecc71", "Neutral": "#95a5a6", "Negative": "#e74c3c"}
EMPTY_FILTER_MESSAGE = "Sem dados para os filtros selecionados."

# --- SIDEBAR ---
st.sidebar.title("🛒 GlobalShop BI")
st.sidebar.markdown("---")
st.sidebar.header("🔎 Filtros")
st.sidebar.caption(f"Fonte de dados ativa: {active_source}")
st.sidebar.caption(f"Reviews carregadas: {len(df)}")
latest_timestamp = df["timestamp"].max() if not df.empty else None
if latest_timestamp is not None and not pd.isna(latest_timestamp):
    st.sidebar.caption(f"Última review: {latest_timestamp:%Y-%m-%d %H:%M}")
if source_message:
    st.sidebar.info(source_message)

selected_cat = st.sidebar.multiselect(
    "Categoria", options=sorted(df["category"].dropna().unique()), default=sorted(df["category"].dropna().unique())
)
selected_mem = st.sidebar.multiselect(
    "Membership", options=sorted(df["membership"].dropna().unique()), default=sorted(df["membership"].dropna().unique())
)
selected_loc = st.sidebar.multiselect(
    "Localização", options=sorted(df["customer_location"].dropna().unique()), default=sorted(df["customer_location"].dropna().unique())
)

filtered_df = df[
    df["category"].isin(selected_cat)
    & df["membership"].isin(selected_mem)
    & df["customer_location"].isin(selected_loc)
]
has_data = not filtered_df.empty

# --- HEADER ---
st.title("🛒 GlobalShop: Sentiment Intelligence Dashboard")
st.caption("Sistema de Suporte à Decisão (DSS) v3.0  |  Powered by MongoDB (NoSQL + Geospatial) + Streamlit")
st.markdown("---")

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Visão Executiva",
    "🏷️ Análise Tática",
    "🔍 Análise Operacional",
    "🗺️ Análise Geoespacial",
])

# =============================================================
# TAB 1 - VISAO EXECUTIVA
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

    decay_rate = 0
    if has_data:
        cutoff = filtered_df["timestamp"].max() - pd.Timedelta(days=30)
        recent = filtered_df[filtered_df["timestamp"] >= cutoff]
        historical = filtered_df[filtered_df["timestamp"] < cutoff]
        recent_avg = recent["rating"].mean() if len(recent) > 0 else avg_rating
        hist_avg = historical["rating"].mean() if len(historical) > 0 else avg_rating
        decay_rate = ((recent_avg - hist_avg) / hist_avg * 100) if hist_avg > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(
        "Net Sentiment Score",
        f"{nss:.1f}%",
        delta="Saudável ✔" if nss >= 0 else "Alerta ✘",
        delta_color="normal" if nss >= 0 else "inverse",
    )
    col2.metric("Total de Reviews", n)
    col3.metric("Nota Média Global", f"{avg_rating:.2f} ⭐")
    col4.metric("Compras Verificadas", f"{verified_pct:.0f}%")
    col5.metric(
        "Quality Decay Rate",
        f"{decay_rate:+.1f}%",
        delta="Estável" if decay_rate > -10 else "Alerta de Queda",
        delta_color="normal" if decay_rate > -10 else "inverse",
        help="Variação da nota média nos últimos 30 dias vs. histórico anterior.",
    )

    st.markdown("---")

    if not has_data:
        st.info(EMPTY_FILTER_MESSAGE)
    else:
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
                y=CRITICAL_RATING_THRESHOLD,
                line_dash="dash",
                line_color="#e74c3c",
                annotation_text=f"Limite Crítico ({CRITICAL_RATING_THRESHOLD})",
            )
            fig_trend.update_layout(yaxis_range=[0, 5.5])
            st.plotly_chart(fig_trend, use_container_width=True)

# =============================================================
# TAB 2 - ANALISE TATICA
# =============================================================
with tab2:
    if not has_data:
        st.info(EMPTY_FILTER_MESSAGE)
    else:
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
            st.subheader("⚠️ Top Produtos Críticos (Rating Baixo)")
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
# TAB 3 - ANALISE OPERACIONAL
# =============================================================
with tab3:
    if not has_data:
        st.info(EMPTY_FILTER_MESSAGE)
    else:
        col_op1, col_op2 = st.columns(2)

        neg_df = filtered_df[filtered_df["sentiment"] == "Negative"]
        all_neg_kw = []
        for kw_list in neg_df["keywords"]:
            all_neg_kw.extend(kw_list)

        with col_op1:
            st.subheader("☁️ Causa Raiz - Keywords Negativas")
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

        with col_op2:
            st.subheader("📋 Frequência de Keywords Negativas (Top 10)")
            if all_neg_kw:
                kw_freq = Counter(all_neg_kw).most_common(10)
                kw_df = pd.DataFrame(kw_freq, columns=["Keyword", "Frequência"])
                fig_kw = px.bar(
                    kw_df, x="Frequência", y="Keyword", orientation="h",
                    color="Frequência", color_continuous_scale="Reds",
                )
                st.plotly_chart(fig_kw, use_container_width=True)
            else:
                st.info("Sem keywords negativas para apresentar.")

        st.markdown("---")
        st.subheader("🚨 Anomaly Detection - Quality Decay Rate por Produto")
        st.caption("Produtos com maior queda de nota entre o penúltimo e o último mês com dados.")

        monthly_avg = (
            filtered_df.groupby(["product_name", "month"])["rating"]
            .mean()
            .reset_index()
        )
        monthly_avg = monthly_avg.sort_values(
            ["product_name", "month"],
            key=lambda col: pd.PeriodIndex(col, freq="M") if col.name == "month" else col,
        )

        anomaly_rows = []
        for prod, grp in monthly_avg.groupby("product_name"):
            if len(grp) >= 2:
                last = grp.iloc[-1]
                prev = grp.iloc[-2]
                drop = prev["rating"] - last["rating"]
                drop_pct = (drop / prev["rating"] * 100) if prev["rating"] > 0 else 0
                anomaly_rows.append({
                    "Produto": prod,
                    "Mês Anterior": prev["month"],
                    "Nota Anterior": round(prev["rating"], 2),
                    "Último Mês": last["month"],
                    "Nota Atual": round(last["rating"], 2),
                    "Queda (pts)": round(drop, 2),
                    "Queda (%)": round(drop_pct, 1),
                    "Alerta": "🔴 Crítico" if drop_pct >= 30 else ("🟡 Atenção" if drop_pct >= 10 else "🟢 Estável"),
                })

        if anomaly_rows:
            anomaly_df = pd.DataFrame(anomaly_rows).sort_values("Queda (%)", ascending=False)
            st.dataframe(anomaly_df, use_container_width=True, hide_index=True)
        else:
            st.info("Dados insuficientes para cálculo de anomalias com os filtros atuais.")

# =============================================================
# TAB 4 - ANALISE GEOESPACIAL
# =============================================================
with tab4:
    st.subheader("🗺️ Mapa de Satisfação por Cidade (Geographic Sentiment Index)")
    st.caption(
        "Powered by MongoDB Geospatial (índice 2dsphere + GeoJSON). "
        "Tamanho da bolha = volume de reviews  |  Cor = Net Sentiment Score (NSS)"
    )

    if not has_data:
        st.info(EMPTY_FILTER_MESSAGE)
    else:
        city_stats = (
            filtered_df.groupby("customer_location")
            .agg(
                lat=("lat", "first"),
                lon=("lon", "first"),
                total=("review_id", "count"),
                nota_media=("rating", "mean"),
                positivos=("sentiment", lambda x: (x == "Positive").sum()),
                negativos=("sentiment", lambda x: (x == "Negative").sum()),
            )
            .reset_index()
        )
        city_stats["nss"] = (
            (city_stats["positivos"] - city_stats["negativos"]) / city_stats["total"] * 100
        ).round(1)
        city_stats["nota_media"] = city_stats["nota_media"].round(2)
        city_stats["label"] = city_stats.apply(
            lambda r: f"{r['customer_location']}<br>Reviews: {r['total']}<br>NSS: {r['nss']:.0f}%<br>Nota: {r['nota_media']:.2f}⭐",
            axis=1,
        )

        fig_map = px.scatter_mapbox(
            city_stats,
            lat="lat",
            lon="lon",
            size="total",
            color="nss",
            color_continuous_scale="RdYlGn",
            range_color=[-100, 100],
            hover_name="customer_location",
            hover_data={"lat": False, "lon": False, "total": True, "nota_media": True, "nss": True},
            size_max=40,
            zoom=6.0,
            center={"lat": 39.5, "lon": -8.0},
            mapbox_style="open-street-map",
            labels={"nss": "NSS (%)", "total": "Reviews", "nota_media": "Nota Média"},
        )
        fig_map.update_layout(margin=dict(t=10, b=10, l=0, r=0), height=480)
        st.plotly_chart(fig_map, use_container_width=True)

        st.markdown("---")
        col_geo1, col_geo2 = st.columns(2)

        with col_geo1:
            st.subheader("📍 NSS por Cidade")
            city_sorted = city_stats.sort_values("nss", ascending=True)
            fig_nss_city = px.bar(
                city_sorted, x="nss", y="customer_location", orientation="h",
                color="nss", color_continuous_scale="RdYlGn", range_color=[-100, 100],
                labels={"nss": "NSS (%)", "customer_location": "Cidade"},
            )
            fig_nss_city.add_vline(x=0, line_dash="dash", line_color="#95a5a6")
            st.plotly_chart(fig_nss_city, use_container_width=True)

        with col_geo2:
            st.subheader("📊 Volume e Nota Média por Cidade")
            city_by_rating = city_stats.sort_values("nota_media", ascending=False)
            fig_vol = px.bar(
                city_by_rating,
                x="customer_location", y="nota_media",
                color="nota_media", color_continuous_scale="RdYlGn", range_color=[1, 5],
                text=city_by_rating["total"].apply(lambda x: f"{x} rev."),
                labels={"customer_location": "Cidade", "nota_media": "Nota Média"},
            )
            fig_vol.update_traces(textposition="outside")
            fig_vol.update_layout(yaxis_range=[0, 5.5])
            st.plotly_chart(fig_vol, use_container_width=True)

        st.markdown("---")
        st.subheader("📋 Resumo Regional")
        display_cols = {
            "customer_location": "Cidade",
            "total": "Total Reviews",
            "nota_media": "Nota Média",
            "nss": "NSS (%)",
            "positivos": "Positivos",
            "negativos": "Negativos",
        }
        st.dataframe(
            city_stats[list(display_cols.keys())].rename(columns=display_cols)
            .sort_values("NSS (%)", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

st.markdown("---")
st.caption("GlobalShop DSS v3.0  |  NoSQL (MongoDB) + Spatial (2dsphere GeoJSON) + Streamlit  |  Mercado Portugal")
