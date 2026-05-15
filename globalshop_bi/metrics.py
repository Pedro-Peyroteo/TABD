from collections import Counter

import pandas as pd


def executive_metrics(df):
    total = len(df)
    if total == 0:
        return {
            "total": 0,
            "nss": 0,
            "avg_rating": 0,
            "verified_pct": 0,
            "decay_rate": 0,
        }

    pos_count = (df["sentiment"] == "Positive").sum()
    neg_count = (df["sentiment"] == "Negative").sum()
    nss = (pos_count / total * 100) - (neg_count / total * 100)
    avg_rating = df["rating"].mean()
    verified_pct = df["verified_purchase"].sum() / total * 100

    return {
        "total": total,
        "nss": nss,
        "avg_rating": avg_rating,
        "verified_pct": verified_pct,
        "decay_rate": quality_decay_rate(df, avg_rating),
    }


def quality_decay_rate(df, default_avg=None):
    if df.empty:
        return 0

    avg_rating = df["rating"].mean() if default_avg is None else default_avg
    cutoff = df["timestamp"].max() - pd.Timedelta(days=30)
    recent = df[df["timestamp"] >= cutoff]
    historical = df[df["timestamp"] < cutoff]
    recent_avg = recent["rating"].mean() if len(recent) > 0 else avg_rating
    hist_avg = historical["rating"].mean() if len(historical) > 0 else avg_rating
    return ((recent_avg - hist_avg) / hist_avg * 100) if hist_avg > 0 else 0


def brand_stats(df):
    if df.empty:
        return pd.DataFrame(columns=["brand", "nota_media", "total", "nss_val"])

    return (
        df.groupby("brand")
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


def negative_keywords(df):
    if df.empty:
        return []

    keywords = []
    neg_df = df[df["sentiment"] == "Negative"]
    for kw_list in neg_df["keywords"]:
        if isinstance(kw_list, list):
            keywords.extend(kw_list)
    return keywords


def keyword_frequency_df(keywords, limit=10):
    return pd.DataFrame(Counter(keywords).most_common(limit), columns=["Keyword", "Frequencia"])


def anomaly_detection_df(df):
    columns = [
        "Produto",
        "Mes Anterior",
        "Nota Anterior",
        "Ultimo Mes",
        "Nota Atual",
        "Queda (pts)",
        "Queda (%)",
        "Alerta",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)

    monthly_avg = (
        df.groupby(["product_name", "month"])["rating"]
        .mean()
        .reset_index()
        .sort_values(["product_name", "month"])
    )

    rows = []
    for product, group in monthly_avg.groupby("product_name"):
        if len(group) < 2:
            continue

        last = group.iloc[-1]
        prev = group.iloc[-2]
        drop = prev["rating"] - last["rating"]
        drop_pct = (drop / prev["rating"] * 100) if prev["rating"] > 0 else 0
        rows.append({
            "Produto": product,
            "Mes Anterior": prev["month"],
            "Nota Anterior": round(prev["rating"], 2),
            "Ultimo Mes": last["month"],
            "Nota Atual": round(last["rating"], 2),
            "Queda (pts)": round(drop, 2),
            "Queda (%)": round(drop_pct, 1),
            "Alerta": alert_for_drop(drop_pct),
        })

    return pd.DataFrame(rows, columns=columns).sort_values("Queda (%)", ascending=False)


def alert_for_drop(drop_pct):
    if drop_pct >= 30:
        return "Critico"
    if drop_pct >= 10:
        return "Atencao"
    return "Estavel"


def city_stats(df):
    if df.empty:
        return pd.DataFrame(columns=[
            "customer_location",
            "lat",
            "lon",
            "total",
            "nota_media",
            "positivos",
            "negativos",
            "nss",
            "label",
        ])

    stats = (
        df.groupby("customer_location")
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
    stats["nss"] = ((stats["positivos"] - stats["negativos"]) / stats["total"] * 100).round(1)
    stats["nota_media"] = stats["nota_media"].round(2)
    stats["label"] = stats.apply(
        lambda r: (
            f"{r['customer_location']}<br>Reviews: {r['total']}"
            f"<br>NSS: {r['nss']:.0f}%<br>Nota: {r['nota_media']:.2f}"
        ),
        axis=1,
    )
    return stats
