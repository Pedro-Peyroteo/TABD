"""
GlobalShop Sentiment Intelligence Dashboard
============================================
DSS v4.0 — MongoDB NoSQL + Geospatial + Streamlit

Arquitectura de dados:
  • Modo MongoDB : carrega documentos e executa aggregation pipelines no servidor
                   ($facet, $geoNear, $unwind, double-group, $bucket)
  • Modo JSON    : fallback offline via dataset_exemplo.json
  • analytics.py : KCI, rolling average, segmentação, anomaly detection (pandas)
"""

import logging
import os
from io import StringIO

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from wordcloud import WordCloud

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from globalshop_bi.analytics import (
    anomaly_detection,
    keyword_correlation_index,
    monthly_trend,
    mom_comparison,
    segmentation_matrix,
)
from globalshop_bi.data_access import get_mongo_collection_handle, load_dashboard_data
from globalshop_bi.mongo_queries import (
    run_facet_executive,
    run_geo_nss,
    run_kci_pipeline,
    run_quality_decay,
)


# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="GlobalShop BI", layout="wide", page_icon=None)

# ─────────────────────────────────────────────
# DESIGN SYSTEM
# ─────────────────────────────────────────────
C_BG       = "#0f1117"
C_SURFACE  = "#161b2e"
C_BORDER   = "#1e2d4f"
C_TEXT_PRI = "#f1f5f9"
C_TEXT_SEC = "#94a3b8"
C_TEXT_MUT = "#475569"
C_ACCENT   = "#4f8ef7"
C_POSITIVE = "#22c55e"
C_NEUTRAL  = "#64748b"
C_NEGATIVE = "#ef4444"

SENTIMENT_COLORS = {"Positive": C_POSITIVE, "Neutral": C_NEUTRAL, "Negative": C_NEGATIVE}
CHART_FONT       = dict(family="Inter, system-ui, sans-serif", color=C_TEXT_SEC, size=12)
_CB = dict(tickfont=dict(color=C_TEXT_SEC, size=10), title_font=dict(color=C_TEXT_SEC, size=11),
           bgcolor=C_SURFACE, bordercolor=C_BORDER)
CHART_BASE = dict(
    paper_bgcolor=C_BG, plot_bgcolor=C_BG, font=CHART_FONT,
    margin=dict(t=32, b=8, l=8, r=8),
    xaxis=dict(gridcolor=C_BORDER, linecolor=C_BORDER, tickfont=dict(color=C_TEXT_MUT, size=11)),
    yaxis=dict(gridcolor=C_BORDER, linecolor=C_BORDER, tickfont=dict(color=C_TEXT_MUT, size=11)),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=C_BORDER, font=dict(color=C_TEXT_SEC)),
    coloraxis_colorbar=_CB,
)


def style(fig, height: int = 360, **kw):
    fig.update_layout(**{**CHART_BASE, "height": height, **kw})
    return fig


CUSTOM_CSS = f"""
<style>
.block-container {{ padding-top:1.75rem; padding-bottom:2rem; max-width:1440px; }}
[data-testid="metric-container"] {{
    background:{C_SURFACE}; border:1px solid {C_BORDER};
    border-radius:6px; padding:1.1rem 1.2rem 1rem;
}}
[data-testid="metric-container"] [data-testid="metric-label"] {{
    font-size:.68rem; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase; color:{C_TEXT_MUT};
}}
[data-testid="metric-container"] [data-testid="metric-value"] {{
    font-size:1.8rem; font-weight:700; color:{C_TEXT_PRI}; line-height:1.15;
}}
[data-testid="metric-container"] [data-testid="metric-delta"] {{
    font-size:.78rem; font-weight:500;
}}
h1 {{ margin-bottom:0 !important; }}
h2, h3 {{
    font-weight:600 !important; letter-spacing:-.01em !important;
    color:{C_TEXT_PRI} !important; margin-bottom:.75rem !important;
}}
.stTabs [data-baseweb="tab-list"] {{ border-bottom:1px solid {C_BORDER}; gap:0; background:transparent; }}
.stTabs [data-baseweb="tab"] {{
    font-size:.75rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
    color:{C_TEXT_MUT}; padding:.7rem 1.6rem;
    border-bottom:2px solid transparent; background:transparent;
}}
.stTabs [aria-selected="true"] {{
    color:{C_ACCENT} !important; border-bottom:2px solid {C_ACCENT} !important;
    background:transparent !important;
}}
[data-testid="stSidebar"] {{ border-right:1px solid {C_BORDER}; background:{C_SURFACE}; }}
[data-testid="stSidebar"] .stMarkdown p {{ color:{C_TEXT_SEC}; font-size:.82rem; }}
hr {{ border-color:{C_BORDER} !important; margin:1.5rem 0 !important; }}
.stCaption {{ color:{C_TEXT_MUT} !important; font-size:.74rem !important; }}
.stButton > button {{
    background:transparent; border:1px solid {C_BORDER}; color:{C_TEXT_SEC};
    font-size:.78rem; font-weight:600; letter-spacing:.05em;
    border-radius:4px; padding:.4rem 1rem;
}}
.stButton > button:hover {{ border-color:{C_ACCENT}; color:{C_ACCENT}; background:rgba(79,142,247,.06); }}
[data-testid="stDataFrame"] {{ border:1px solid {C_BORDER}; border-radius:6px; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

EMPTY_MSG = "Sem dados para os filtros selecionados."


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def read_non_negative_int_env(name: str, default: int) -> int:
    try:
        return max(int(os.getenv(name, str(default))), 0)
    except ValueError:
        return default


def section_label(text: str) -> None:
    st.markdown(
        f'<p style="font-size:.68rem;font-weight:700;letter-spacing:.1em;'
        f'text-transform:uppercase;color:{C_TEXT_MUT};margin:0 0 .4rem">{text}</p>',
        unsafe_allow_html=True,
    )


def df_to_csv(df: pd.DataFrame) -> str:
    buf = StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


# ─────────────────────────────────────────────
# ENVIRONMENT
# ─────────────────────────────────────────────
DATA_CACHE_TTL   = read_non_negative_int_env("DATA_CACHE_TTL_SECONDS", 60)
AUTO_REFRESH     = read_non_negative_int_env("AUTO_REFRESH_SECONDS", 0)
DATA_SOURCE      = os.getenv("DATA_SOURCE", "auto")
MONGO_URI        = os.getenv("MONGO_URI")
MONGO_DB         = os.getenv("MONGO_DB", "GlobalShop")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "reviews")

try:
    CRITICAL_THRESHOLD = float(os.getenv("CRITICAL_RATING_THRESHOLD", "3.0"))
except ValueError:
    CRITICAL_THRESHOLD = 3.0


@st.cache_data(ttl=DATA_CACHE_TTL)
def load_data(source, uri, db, col):
    return load_dashboard_data(source, uri, db, col)


@st.cache_data(ttl=DATA_CACHE_TTL)
def load_facet(uri, db, col):
    """Executa $facet executive no MongoDB (cache separada)."""
    if not uri:
        return {}
    try:
        client, collection = get_mongo_collection_handle(uri, db, col)
        result = run_facet_executive(collection)
        client.close()
        return result
    except Exception as exc:
        logging.getLogger(__name__).warning("$facet indisponivel: %s", exc)
        return {}


@st.cache_data(ttl=DATA_CACHE_TTL)
def load_geo_nss(uri, db, col):
    """Executa $geoNear NSS no MongoDB."""
    if not uri:
        return []
    try:
        client, collection = get_mongo_collection_handle(uri, db, col)
        result = run_geo_nss(collection)
        client.close()
        return result
    except Exception as exc:
        logging.getLogger(__name__).warning("$geoNear indisponivel: %s", exc)
        return []


# ─────────────────────────────────────────────
# DATA LOAD
# ─────────────────────────────────────────────
if AUTO_REFRESH > 0:
    st_autorefresh(interval=AUTO_REFRESH * 1000, key="auto_refresh")

try:
    df, active_source, source_msg = load_data(DATA_SOURCE, MONGO_URI, MONGO_DB, MONGO_COLLECTION)
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

mongo_facet   = load_facet(MONGO_URI, MONGO_DB, MONGO_COLLECTION) if active_source == "MongoDB" else {}
mongo_geo_nss = load_geo_nss(MONGO_URI, MONGO_DB, MONGO_COLLECTION) if active_source == "MongoDB" else []


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<h2 style="font-size:1.1rem;font-weight:700;color:{C_TEXT_PRI};margin:0">GlobalShop BI</h2>'
        f'<p style="font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;'
        f'color:{C_TEXT_MUT};margin:.1rem 0 1rem">Business Intelligence Suite</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<hr style="margin:0 0 1rem">', unsafe_allow_html=True)

    if st.button("Atualizar dados", use_container_width=True):
        load_data.clear(); load_facet.clear(); load_geo_nss.clear()
        st.rerun()

    st.markdown('<hr style="margin:.75rem 0">', unsafe_allow_html=True)
    section_label("Filtros")

    selected_cat = st.multiselect("Categoria",   options=sorted(df["category"].dropna().unique()),          default=sorted(df["category"].dropna().unique()))
    selected_mem = st.multiselect("Membership",  options=sorted(df["membership"].dropna().unique()),         default=sorted(df["membership"].dropna().unique()))
    selected_loc = st.multiselect("Localização", options=sorted(df["customer_location"].dropna().unique()),  default=sorted(df["customer_location"].dropna().unique()))

    st.markdown('<hr style="margin:.75rem 0">', unsafe_allow_html=True)
    section_label("Estado do sistema")
    st.caption(f"Fonte ativa: **{active_source}**")
    st.caption(f"Reviews carregadas: {len(df)}")
    latest_ts = df["timestamp"].max() if not df.empty else None
    if latest_ts is not None and not pd.isna(latest_ts):
        st.caption(f"Ultima review: {latest_ts:%Y-%m-%d %H:%M} UTC")
    if mongo_facet:
        st.caption("Aggregation Framework: ativo")
    if source_msg:
        st.info(source_msg)

    st.markdown('<hr style="margin:.75rem 0">', unsafe_allow_html=True)
    section_label("Exportar dados")
    if not df.empty:
        st.download_button(
            label="Exportar reviews (CSV)",
            data=df_to_csv(df.drop(columns=["keywords"])),
            file_name="globalshop_reviews.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ─────────────────────────────────────────────
# FILTER
# ─────────────────────────────────────────────
filtered_df = df[
    df["category"].isin(selected_cat)
    & df["membership"].isin(selected_mem)
    & df["customer_location"].isin(selected_loc)
]
has_data = not filtered_df.empty


# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown(
    f'<div style="margin-bottom:1.5rem">'
    f'<h1 style="font-size:1.6rem;font-weight:700;letter-spacing:-.02em;color:{C_TEXT_PRI};margin:0">'
    f'GlobalShop <span style="color:{C_ACCENT}">Sentiment Intelligence</span></h1>'
    f'<p style="font-size:.75rem;color:{C_TEXT_MUT};margin:.3rem 0 0;letter-spacing:.02em">'
    f'Sistema de Suporte a Decisao (DSS) v4.0 &nbsp;&middot;&nbsp; '
    f'MongoDB NoSQL + Geospatial ({active_source}) + Streamlit &nbsp;&middot;&nbsp; '
    f'{len(filtered_df)} reviews</p>'
    f'</div>',
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4 = st.tabs([
    "Visao Executiva",
    "Analise Tatica",
    "Analise Operacional",
    "Analise Geoespacial",
])


# ═════════════════════════════════════════════
# TAB 1 — VISAO EXECUTIVA
# ═════════════════════════════════════════════
with tab1:
    n           = len(filtered_df)
    pos_count   = (filtered_df["sentiment"] == "Positive").sum()
    neg_count   = (filtered_df["sentiment"] == "Negative").sum()
    pos_pct     = pos_count / n * 100 if n > 0 else 0
    neg_pct     = neg_count / n * 100 if n > 0 else 0
    nss         = pos_pct - neg_pct
    avg_rating  = filtered_df["rating"].mean() if n > 0 else 0
    verified_pct = filtered_df["verified_purchase"].sum() / n * 100 if n > 0 else 0

    decay_rate = 0
    if has_data:
        cutoff     = filtered_df["timestamp"].max() - pd.Timedelta(days=30)
        recent     = filtered_df[filtered_df["timestamp"] >= cutoff]
        historical = filtered_df[filtered_df["timestamp"] <  cutoff]
        r_avg  = recent["rating"].mean()     if len(recent) > 0     else avg_rating
        h_avg  = historical["rating"].mean() if len(historical) > 0 else avg_rating
        decay_rate = ((r_avg - h_avg) / h_avg * 100) if h_avg > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Net Sentiment Score", f"{nss:.1f}%",
              delta="Saudavel" if nss >= 0 else "Alerta",
              delta_color="normal" if nss >= 0 else "inverse")
    c2.metric("Total de Reviews", n)
    c3.metric("Nota Media Global", f"{avg_rating:.2f}")
    c4.metric("Compras Verificadas", f"{verified_pct:.0f}%")
    c5.metric("Quality Decay Rate", f"{decay_rate:+.1f}%",
              delta="Estavel" if decay_rate > -10 else "Alerta de Queda",
              delta_color="normal" if decay_rate > -10 else "inverse",
              help="Variacao da nota media nos ultimos 30 dias vs. historico anterior.")

    st.markdown("---")

    if not has_data:
        st.info(EMPTY_MSG)
    else:
        col_a, col_b = st.columns([1, 2])

        with col_a:
            st.subheader("Distribuicao de Sentimento")
            sent_counts = filtered_df["sentiment"].value_counts().reset_index()
            sent_counts.columns = ["Sentimento", "Quantidade"]
            fig_pie = px.pie(sent_counts, names="Sentimento", values="Quantidade",
                             color="Sentimento", color_discrete_map=SENTIMENT_COLORS, hole=0.5)
            fig_pie.update_traces(textinfo="percent+label",
                                  textfont=dict(color=C_TEXT_PRI, size=12),
                                  marker=dict(line=dict(color=C_BG, width=2)))
            style(fig_pie, height=300, showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_b:
            st.subheader("Tendencia Mensal — Nota Media e Media Movel")
            trend_df = monthly_trend(filtered_df, window=2)
            fig_t = px.line(trend_df, x="Mes", y="Nota Media", markers=True,
                            color_discrete_sequence=[C_ACCENT],
                            labels={"Nota Media": "Nota Media"})
            fig_t.add_scatter(x=trend_df["Mes"], y=trend_df["Media Movel"],
                              mode="lines", name="Media Movel (2 meses)",
                              line=dict(dash="dot", color="#f59e0b", width=2))
            fig_t.update_traces(selector=dict(mode="lines+markers"),
                                line=dict(width=2.5),
                                marker=dict(size=7, color=C_ACCENT, line=dict(color=C_BG, width=2)))
            fig_t.add_hline(y=CRITICAL_THRESHOLD, line_dash="dot", line_color=C_NEGATIVE,
                            line_width=1.5,
                            annotation_text=f"Limite critico ({CRITICAL_THRESHOLD})",
                            annotation_font=dict(color=C_NEGATIVE, size=11))
            style(fig_t, height=300, yaxis_range=[0, 5.5])
            st.plotly_chart(fig_t, use_container_width=True)

        st.markdown("---")
        st.subheader("Comparacao Mes a Mes (MoM)")
        st.caption("Variacao de nota media e NSS entre meses consecutivos.")
        mom_df = mom_comparison(filtered_df)
        if not mom_df.empty:
            def _color_delta(val):
                if pd.isna(val):
                    return ""
                return f"color: {C_POSITIVE}" if val > 0 else (f"color: {C_NEGATIVE}" if val < 0 else "")

            styled = (
                mom_df.style
                .applymap(_color_delta, subset=["Var. Nota", "Var. NSS"])
                .format({"Nota Media": "{:.2f}", "NSS (%)": "{:.1f}",
                         "Var. Nota": "{:+.2f}", "Var. NSS": "{:+.1f}"}, na_rep="—")
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.info("Dados insuficientes para comparacao mensal.")


# ═════════════════════════════════════════════
# TAB 2 — ANALISE TATICA
# ═════════════════════════════════════════════
with tab2:
    if not has_data:
        st.info(EMPTY_MSG)
    else:
        col_t1, col_t2 = st.columns(2)

        with col_t1:
            st.subheader("Distribuicao de Sentimento por Categoria")
            fig_bar = px.histogram(filtered_df, x="category", color="sentiment",
                                   barmode="group", color_discrete_map=SENTIMENT_COLORS,
                                   labels={"category": "Categoria", "count": "Quantidade", "sentiment": "Sentimento"})
            fig_bar.update_traces(marker=dict(line=dict(width=0)))
            style(fig_bar, height=320)
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_t2:
            st.subheader("Distribuicao de Rating por Categoria")
            st.caption("Violin chart: forma da distribuicao de notas por departamento.")
            fig_violin = px.violin(filtered_df, x="category", y="rating",
                                   color="category", box=True, points=False,
                                   labels={"category": "Categoria", "rating": "Rating"})
            fig_violin.update_traces(marker=dict(line=dict(width=0)))
            style(fig_violin, height=320, showlegend=False)
            st.plotly_chart(fig_violin, use_container_width=True)

        st.markdown("---")

        st.subheader("Matriz de Segmentacao — Membership x Categoria")
        st.caption(
            "Nota media por segmento de cliente. "
            "Identifica quais segmentos de fidelidade apresentam pior experiencia por categoria."
        )
        seg_matrix = segmentation_matrix(filtered_df)
        if not seg_matrix.empty:
            fig_hm = px.imshow(seg_matrix,
                               color_continuous_scale="RdYlGn",
                               range_color=[1, 5],
                               text_auto=".2f",
                               labels={"x": "Categoria", "y": "Membership", "color": "Nota Media"})
            fig_hm.update_traces(textfont=dict(color=C_TEXT_PRI, size=13))
            style(fig_hm, height=260,
                  xaxis=dict(side="bottom", tickfont=dict(color=C_TEXT_SEC, size=12)),
                  yaxis=dict(tickfont=dict(color=C_TEXT_SEC, size=12)))
            st.plotly_chart(fig_hm, use_container_width=True)
        else:
            st.info("Dados insuficientes para segmentacao.")

        st.markdown("---")
        col_t3, col_t4 = st.columns(2)

        with col_t3:
            st.subheader("Produtos com Rating Mais Baixo")
            prod_ranking = (
                filtered_df.groupby("product_name")["rating"]
                .mean().sort_values().head(10).reset_index()
            )
            prod_ranking.columns = ["Produto", "Nota Media"]
            fig_prod = px.bar(prod_ranking, x="Nota Media", y="Produto", orientation="h",
                              color="Nota Media", color_continuous_scale="RdYlGn", range_x=[0, 5])
            fig_prod.update_traces(marker=dict(line=dict(width=0)))
            style(fig_prod, height=360)
            st.plotly_chart(fig_prod, use_container_width=True)

        with col_t4:
            st.subheader("Performance por Marca")
            brand_stats = (
                filtered_df.groupby("brand")
                .agg(nota_media=("rating", "mean"), total=("review_id", "count"),
                     nss_val=("sentiment", lambda x: ((x == "Positive").sum() - (x == "Negative").sum()) / len(x) * 100))
                .reset_index().sort_values("nota_media", ascending=False)
            )
            fig_brand = px.bar(brand_stats, x="brand", y="nota_media",
                               color="nss_val", color_continuous_scale="RdYlGn",
                               labels={"brand": "Marca", "nota_media": "Nota Media", "nss_val": "NSS (%)"},
                               text=brand_stats["total"].apply(lambda x: f"{x} rev."))
            fig_brand.update_traces(textposition="outside",
                                    textfont=dict(color=C_TEXT_SEC, size=11),
                                    marker=dict(line=dict(width=0)))
            style(fig_brand, height=360, yaxis_range=[0, 6])
            st.plotly_chart(fig_brand, use_container_width=True)


# ═════════════════════════════════════════════
# TAB 3 — ANALISE OPERACIONAL
# ═════════════════════════════════════════════
with tab3:
    if not has_data:
        st.info(EMPTY_MSG)
    else:
        # ── KCI ──────────────────────────────────────────────
        st.subheader("Keyword Correlation Index (KCI)")
        st.caption(
            "KCI(k) = ocorrencias de k em reviews Negative / total ocorrencias de k × 100  "
            "Um KCI elevado indica que a keyword e um predictor forte de insatisfacao."
        )
        kci_df = keyword_correlation_index(filtered_df, min_freq=2)
        if not kci_df.empty:
            fig_kci = px.scatter(
                kci_df, x="nota_media", y="kci", size="frequencia", text="keyword",
                color="kci", color_continuous_scale=[C_SURFACE, C_NEGATIVE],
                range_color=[0, 100],
                labels={"nota_media": "Nota Media da Review", "kci": "KCI (%)", "frequencia": "Frequencia"},
            )
            fig_kci.update_traces(
                textposition="top center",
                textfont=dict(color=C_TEXT_SEC, size=10),
                marker=dict(line=dict(color=C_BG, width=1.5)),
            )
            style(fig_kci, height=360,
                  xaxis=dict(range=[0.5, 5.5], gridcolor=C_BORDER, linecolor=C_BORDER,
                             tickfont=dict(color=C_TEXT_MUT, size=11)),
                  yaxis=dict(range=[-5, 110], gridcolor=C_BORDER, linecolor=C_BORDER,
                             tickfont=dict(color=C_TEXT_MUT, size=11)))
            st.plotly_chart(fig_kci, use_container_width=True)
        else:
            st.info("Frequencia insuficiente para calcular KCI.")

        st.markdown("---")
        col_op1, col_op2 = st.columns(2)

        neg_df     = filtered_df[filtered_df["sentiment"] == "Negative"]
        all_neg_kw = []
        for kw_list in neg_df["keywords"]:
            all_neg_kw.extend(kw_list)

        with col_op1:
            st.subheader("Causa Raiz — Keywords Negativas")
            if all_neg_kw:
                wc = WordCloud(width=700, height=300, background_color=C_BG,
                               colormap="Blues", prefer_horizontal=0.85,
                               max_font_size=72).generate(" ".join(all_neg_kw))
                fig_wc, ax = plt.subplots(figsize=(7, 3))
                fig_wc.patch.set_facecolor(C_BG)
                ax.set_facecolor(C_BG)
                ax.imshow(wc, interpolation="bilinear")
                ax.axis("off")
                st.pyplot(fig_wc)
                plt.close(fig_wc)
            else:
                st.info("Nenhuma keyword negativa para os filtros selecionados.")

        with col_op2:
            st.subheader("Frequencia de Keywords Negativas")
            if all_neg_kw:
                from collections import Counter
                kw_freq = Counter(all_neg_kw).most_common(10)
                kw_df_plot = pd.DataFrame(kw_freq, columns=["Keyword", "Frequencia"])
                fig_kw = px.bar(kw_df_plot, x="Frequencia", y="Keyword", orientation="h",
                                color="Frequencia",
                                color_continuous_scale=[C_SURFACE, C_NEGATIVE])
                fig_kw.update_traces(marker=dict(line=dict(width=0)))
                style(fig_kw, height=320)
                st.plotly_chart(fig_kw, use_container_width=True)
            else:
                st.info("Sem keywords negativas para apresentar.")

        st.markdown("---")
        st.subheader("Anomaly Detection — Quality Decay Rate por Produto")
        st.caption("Produtos com maior queda de nota entre o penultimo e o ultimo mes com dados.")

        anom_df = anomaly_detection(filtered_df)
        if not anom_df.empty:
            # Chart: top anomalias
            fig_anom = px.bar(
                anom_df.head(10), x="Produto", y="Queda (%)",
                color="Queda (%)", color_continuous_scale=[C_NEUTRAL, C_NEGATIVE],
                range_color=[0, anom_df["Queda (%)"].max() + 5],
                text=anom_df.head(10)["Estado"],
            )
            fig_anom.update_traces(textposition="outside",
                                   textfont=dict(color=C_TEXT_SEC, size=11),
                                   marker=dict(line=dict(width=0)))
            fig_anom.add_hline(y=30, line_dash="dot", line_color=C_NEGATIVE, line_width=1.5,
                               annotation_text="Limiar critico (30%)",
                               annotation_font=dict(color=C_NEGATIVE, size=11))
            style(fig_anom, height=340)
            st.plotly_chart(fig_anom, use_container_width=True)

            with st.expander("Ver tabela detalhada"):
                st.dataframe(anom_df, use_container_width=True, hide_index=True)
        else:
            st.info("Dados insuficientes para calculo de anomalias com os filtros atuais.")


# ═════════════════════════════════════════════
# TAB 4 — ANALISE GEOESPACIAL
# ═════════════════════════════════════════════
with tab4:
    st.subheader("Mapa de Satisfacao por Cidade — Geographic Sentiment Index")
    st.caption(
        "MongoDB Geospatial (indice 2dsphere + GeoJSON)  ·  "
        "Dimensao da bolha = volume de reviews  ·  Cor = Net Sentiment Score (NSS)"
    )

    if not has_data:
        st.info(EMPTY_MSG)
    else:
        # Usa $geoNear quando MongoDB disponivel, fallback para pandas
        if mongo_geo_nss:
            city_stats = pd.DataFrame(mongo_geo_nss).rename(columns={
                "cidade": "customer_location", "notaMedia": "nota_media",
                "distancia_km": "distancia_km",
            })
            city_stats["nss"]        = city_stats["nss"].round(1)
            city_stats["nota_media"] = city_stats["nota_media"].round(2)
            st.caption(
                f"Fonte: $geoNear (MongoDB) — cidades ordenadas por distancia a Lisboa  "
                f"· {len(city_stats)} cidades cobertas"
            )
        else:
            city_stats = (
                filtered_df.groupby("customer_location")
                .agg(lat=("lat", "first"), lon=("lon", "first"),
                     total=("review_id", "count"), nota_media=("rating", "mean"),
                     positivos=("sentiment", lambda x: (x == "Positive").sum()),
                     negativos=("sentiment", lambda x: (x == "Negative").sum()))
                .reset_index()
            )
            city_stats["nss"]        = ((city_stats["positivos"] - city_stats["negativos"]) / city_stats["total"] * 100).round(1)
            city_stats["nota_media"] = city_stats["nota_media"].round(2)

        fig_map = px.scatter_mapbox(
            city_stats, lat="lat", lon="lon", size="total",
            color="nss", color_continuous_scale="RdYlGn", range_color=[-100, 100],
            hover_name="customer_location",
            hover_data={"lat": False, "lon": False, "total": True, "nota_media": True, "nss": True},
            size_max=48, zoom=6.0, center={"lat": 39.5, "lon": -8.0},
            mapbox_style="carto-darkmatter",
            labels={"nss": "NSS (%)", "total": "Reviews", "nota_media": "Nota Media"},
        )
        fig_map.update_layout(paper_bgcolor=C_BG, font=CHART_FONT, height=500,
                              margin=dict(t=8, b=8, l=0, r=0), coloraxis_colorbar=_CB)
        st.plotly_chart(fig_map, use_container_width=True)

        st.markdown("---")
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.subheader("NSS por Cidade")
            city_sorted = city_stats.sort_values("nss", ascending=True)
            fig_nss = px.bar(city_sorted, x="nss", y="customer_location", orientation="h",
                             color="nss", color_continuous_scale="RdYlGn", range_color=[-100, 100],
                             labels={"nss": "NSS (%)", "customer_location": "Cidade"})
            fig_nss.update_traces(marker=dict(line=dict(width=0)))
            fig_nss.add_vline(x=0, line_dash="dot", line_color=C_BORDER, line_width=1.5)
            style(fig_nss, height=300)
            st.plotly_chart(fig_nss, use_container_width=True)

        with col_g2:
            st.subheader("Volume e Nota Media por Cidade")
            city_by_rating = city_stats.sort_values("nota_media", ascending=False)
            fig_vol = px.bar(city_by_rating, x="customer_location", y="nota_media",
                             color="nota_media", color_continuous_scale="RdYlGn", range_color=[1, 5],
                             text=city_by_rating["total"].apply(lambda x: f"{x} rev."),
                             labels={"customer_location": "Cidade", "nota_media": "Nota Media"})
            fig_vol.update_traces(textposition="outside",
                                  textfont=dict(color=C_TEXT_SEC, size=11),
                                  marker=dict(line=dict(width=0)))
            style(fig_vol, height=300, yaxis_range=[0, 5.8])
            st.plotly_chart(fig_vol, use_container_width=True)

        st.markdown("---")
        st.subheader("Resumo Regional")
        display_cols = {
            "customer_location": "Cidade", "total": "Total Reviews",
            "nota_media": "Nota Media",    "nss": "NSS (%)",
        }
        if "distancia_km" in city_stats.columns:
            display_cols["distancia_km"] = "Distancia a Lisboa (km)"
        show_cols = [c for c in display_cols if c in city_stats.columns]
        st.dataframe(
            city_stats[show_cols].rename(columns=display_cols).sort_values("NSS (%)", ascending=False),
            use_container_width=True, hide_index=True,
        )


# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("---")
st.caption(
    "GlobalShop DSS v4.0  ·  NoSQL (MongoDB) + Spatial (2dsphere GeoJSON) + Streamlit  ·  Mercado Portugal"
)
