"""
globalshop_bi.analytics
=======================
Camada de computação analítica que opera sobre DataFrames pandas.
Usada tanto em modo JSON (fallback) como em modo MongoDB (pós-carregamento).
Todas as funções são puras: recebem um DataFrame e devolvem um DataFrame.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# TENDÊNCIA COM MÉDIA MÓVEL
# ──────────────────────────────────────────────────────────────

def monthly_trend(df: pd.DataFrame, window: int = 2) -> pd.DataFrame:
    """
    Agrega a nota média mensal e calcula a média móvel centrada.

    Returns
    -------
    DataFrame com colunas: Mes, Nota Media, Media Movel, Total Reviews
    """
    if df.empty:
        return pd.DataFrame(columns=["Mes", "Nota Media", "Media Movel", "Total Reviews"])

    trend = (
        df.groupby("month")
        .agg(nota_media=("rating", "mean"), total=("review_id", "count"))
        .reset_index()
        .rename(columns={"month": "Mes", "nota_media": "Nota Media", "total": "Total Reviews"})
    )
    trend["Media Movel"] = (
        trend["Nota Media"]
        .rolling(window=window, min_periods=1, center=True)
        .mean()
        .round(3)
    )
    trend["Nota Media"] = trend["Nota Media"].round(3)
    return trend


# ──────────────────────────────────────────────────────────────
# COMPARAÇÃO MÊS A MÊS (MoM)
# ──────────────────────────────────────────────────────────────

def mom_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula variação de nota média e NSS entre cada par de meses consecutivos.

    Returns
    -------
    DataFrame com: Mes, Nota Media, NSS, Delta Nota, Delta NSS
    """
    if df.empty:
        return pd.DataFrame()

    monthly = (
        df.groupby("month")
        .agg(
            nota_media=("rating", "mean"),
            total=("review_id", "count"),
            positivos=("sentiment", lambda x: (x == "Positive").sum()),
            negativos=("sentiment", lambda x: (x == "Negative").sum()),
        )
        .reset_index()
    )
    monthly["nss"] = (
        (monthly["positivos"] - monthly["negativos"]) / monthly["total"] * 100
    ).round(1)
    monthly["nota_media"] = monthly["nota_media"].round(2)
    monthly["delta_nota"] = monthly["nota_media"].diff().round(2)
    monthly["delta_nss"]  = monthly["nss"].diff().round(1)
    return monthly.rename(columns={
        "month": "Mes", "nota_media": "Nota Media", "nss": "NSS (%)",
        "total": "Reviews", "delta_nota": "Var. Nota", "delta_nss": "Var. NSS",
    })[["Mes", "Reviews", "Nota Media", "Var. Nota", "NSS (%)", "Var. NSS"]]


# ──────────────────────────────────────────────────────────────
# MATRIZ DE SEGMENTAÇÃO (Membership × Categoria)
# ──────────────────────────────────────────────────────────────

def segmentation_matrix(df: pd.DataFrame, metric: str = "rating") -> pd.DataFrame:
    """
    Cria matriz pivot Membership × Categoria com o valor médio da métrica pedida.

    Parameters
    ----------
    df     : DataFrame normalizado
    metric : coluna numérica a agregar (padrão: "rating")

    Returns
    -------
    DataFrame pivot pronto para px.imshow
    """
    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot_table(
        values=metric,
        index="membership",
        columns="category",
        aggfunc="mean",
    ).round(2)
    return pivot


# ──────────────────────────────────────────────────────────────
# KEYWORD CORRELATION INDEX (KCI)
# ──────────────────────────────────────────────────────────────

def keyword_correlation_index(df: pd.DataFrame, min_freq: int = 2) -> pd.DataFrame:
    """
    Calcula o KCI para cada keyword:

        KCI(k) = (ocorrências de k em reviews Negative / total ocorrências de k) × 100

    Um KCI elevado indica correlação forte entre a keyword e reviews negativas.

    Parameters
    ----------
    df       : DataFrame normalizado
    min_freq : frequência mínima para incluir a keyword

    Returns
    -------
    DataFrame com: keyword, frequencia, nota_media, kci
    """
    if df.empty:
        return pd.DataFrame(columns=["keyword", "frequencia", "nota_media", "kci"])

    rows = []
    for _, row in df.iterrows():
        for kw in row["keywords"]:
            rows.append({
                "keyword":   kw,
                "rating":    row["rating"],
                "sentiment": row["sentiment"],
            })

    if not rows:
        return pd.DataFrame(columns=["keyword", "frequencia", "nota_media", "kci"])

    kw_df = pd.DataFrame(rows)
    agg   = kw_df.groupby("keyword").agg(
        frequencia=("rating", "count"),
        nota_media=("rating", "mean"),
        neg_count=("sentiment", lambda x: (x == "Negative").sum()),
    ).reset_index()

    agg = agg[agg["frequencia"] >= min_freq].copy()
    agg["kci"]       = (agg["neg_count"] / agg["frequencia"] * 100).round(1)
    agg["nota_media"] = agg["nota_media"].round(2)
    return agg.sort_values("kci", ascending=False).drop(columns="neg_count")


# ──────────────────────────────────────────────────────────────
# ANOMALY DETECTION — QUALITY DECAY RATE
# ──────────────────────────────────────────────────────────────

def anomaly_detection(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifica produtos com queda de nota entre o penúltimo e o último mês.

    Returns
    -------
    DataFrame com: Produto, Mes Anterior, Nota Anterior, Ultimo Mes,
                   Nota Atual, Queda (pts), Queda (%), Estado
    """
    if df.empty:
        return pd.DataFrame()

    monthly = df.groupby(["product_name", "month"])["rating"].mean().reset_index()
    monthly = monthly.sort_values(
        ["product_name", "month"],
        key=lambda col: pd.PeriodIndex(col, freq="M") if col.name == "month" else col,
    )

    rows = []
    for prod, grp in monthly.groupby("product_name"):
        if len(grp) < 2:
            continue
        last, prev = grp.iloc[-1], grp.iloc[-2]
        drop     = prev["rating"] - last["rating"]
        drop_pct = (drop / prev["rating"] * 100) if prev["rating"] > 0 else 0
        rows.append({
            "Produto":       prod,
            "Mes Anterior":  prev["month"],
            "Nota Anterior": round(float(prev["rating"]), 2),
            "Ultimo Mes":    last["month"],
            "Nota Atual":    round(float(last["rating"]), 2),
            "Queda (pts)":   round(float(drop), 2),
            "Queda (%)":     round(float(drop_pct), 1),
            "Estado":        "Critico" if drop_pct >= 30 else (
                             "Atencao" if drop_pct >= 10 else "Estavel"),
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("Queda (%)", ascending=False)
