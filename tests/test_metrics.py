import pandas as pd

from globalshop_bi.metrics import (
    alert_for_drop,
    anomaly_detection_df,
    brand_stats,
    city_stats,
    executive_metrics,
    keyword_frequency_df,
    negative_keywords,
    quality_decay_rate,
)


def dashboard_df():
    return pd.DataFrame([
        {
            "review_id": "r1",
            "product_name": "Laptop X",
            "brand": "Alpha",
            "customer_location": "Lisboa",
            "lat": 38.7223,
            "lon": -9.1393,
            "rating": 5,
            "sentiment": "Positive",
            "verified_purchase": True,
            "keywords": ["rapidez"],
            "timestamp": pd.Timestamp("2026-04-01"),
            "month": "2026-04",
        },
        {
            "review_id": "r2",
            "product_name": "Laptop X",
            "brand": "Alpha",
            "customer_location": "Lisboa",
            "lat": 38.7223,
            "lon": -9.1393,
            "rating": 2,
            "sentiment": "Negative",
            "verified_purchase": False,
            "keywords": ["defeito", "atraso"],
            "timestamp": pd.Timestamp("2026-05-01"),
            "month": "2026-05",
        },
        {
            "review_id": "r3",
            "product_name": "Phone Y",
            "brand": "Beta",
            "customer_location": "Porto",
            "lat": 41.1579,
            "lon": -8.6291,
            "rating": 3,
            "sentiment": "Neutral",
            "verified_purchase": True,
            "keywords": ["normal"],
            "timestamp": pd.Timestamp("2026-05-02"),
            "month": "2026-05",
        },
    ])


def test_executive_metrics_handles_empty_and_calculates_core_kpis():
    empty = dashboard_df().iloc[0:0]
    assert executive_metrics(empty) == {
        "total": 0,
        "nss": 0,
        "avg_rating": 0,
        "verified_pct": 0,
        "decay_rate": 0,
    }

    metrics = executive_metrics(dashboard_df())

    assert metrics["total"] == 3
    assert metrics["nss"] == 0
    assert metrics["avg_rating"] == 10 / 3
    assert metrics["verified_pct"] == 2 / 3 * 100
    assert metrics["decay_rate"] == -50


def test_quality_decay_rate_uses_current_average_when_history_is_missing():
    recent_only = dashboard_df().iloc[[1, 2]]

    assert quality_decay_rate(recent_only) == 0


def test_brand_stats_keyword_frequency_and_city_stats():
    df = dashboard_df()

    brands = brand_stats(df)
    alpha = brands[brands["brand"] == "Alpha"].iloc[0]
    assert alpha["nota_media"] == 3.5
    assert alpha["total"] == 2
    assert alpha["nss_val"] == 0

    keywords = negative_keywords(df)
    assert keywords == ["defeito", "atraso"]
    frequency = keyword_frequency_df(keywords)
    assert list(frequency.columns) == ["Keyword", "Frequencia"]
    assert frequency.iloc[0].to_dict() == {"Keyword": "defeito", "Frequencia": 1}

    cities = city_stats(df)
    lisboa = cities[cities["customer_location"] == "Lisboa"].iloc[0]
    assert lisboa["total"] == 2
    assert lisboa["nota_media"] == 3.5
    assert lisboa["nss"] == 0


def test_anomaly_detection_flags_drop_thresholds():
    df = dashboard_df()

    anomalies = anomaly_detection_df(df)

    assert len(anomalies) == 1
    row = anomalies.iloc[0]
    assert row["Produto"] == "Laptop X"
    assert row["Mes Anterior"] == "2026-04"
    assert row["Ultimo Mes"] == "2026-05"
    assert row["Queda (%)"] == 60
    assert row["Alerta"] == "Critico"

    assert alert_for_drop(30) == "Critico"
    assert alert_for_drop(10) == "Atencao"
    assert alert_for_drop(9.9) == "Estavel"
