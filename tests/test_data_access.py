from datetime import datetime

import pandas as pd
import pytest

from globalshop_bi.data_access import (
    DATA_COLUMNS,
    documents_with_mongo_dates,
    load_dashboard_data,
    load_json_documents,
    normalize_documents,
)


def test_json_normalization_returns_dashboard_columns():
    source = load_json_documents()
    df = normalize_documents(source)

    assert len(df) == len(source)
    assert list(df.columns) == DATA_COLUMNS
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert pd.api.types.is_float_dtype(df["lon"])
    assert pd.api.types.is_float_dtype(df["lat"])


def test_timestamps_are_timezone_aware():
    df = normalize_documents(load_json_documents())
    assert df["timestamp"].dt.tz is not None


def test_empty_filter_selection_is_detectable_before_geospatial_math():
    df = normalize_documents(load_json_documents())
    filtered_df = df[df["category"].isin([])]

    assert filtered_df.empty


def test_auto_mode_falls_back_to_json_without_mongo_uri():
    df, source, message = load_dashboard_data("auto", None, "GlobalShop", "reviews")

    assert not df.empty
    assert source == "JSON"
    assert "MONGO_URI" in message


def test_mongo_mode_requires_uri():
    with pytest.raises(RuntimeError, match="MONGO_URI"):
        load_dashboard_data("mongo", None, "GlobalShop", "reviews")


def test_seed_documents_convert_timestamps_for_mongo():
    documents = documents_with_mongo_dates(load_json_documents())

    assert len(documents) > 0
    assert isinstance(documents[0]["metadata"]["timestamp"], datetime)


def test_normalize_documents_with_missing_coordinates():
    malformed = [
        {
            "review_id": "TEST-001",
            "product": {"name": "Produto X", "category": "Eletrónica", "brand": "MarcaX", "product_id": "P-001"},
            "customer": {
                "location": {"city": "Lisboa", "country": "PT", "coordinates": {}},
                "membership": "Gold",
            },
            "metrics": {"rating": 4, "sentiment": "Positive", "verified_purchase": True},
            "content": {"keywords": ["qualidade"], "comment": "Bom.", "language": "pt"},
            "metadata": {"timestamp": "2026-01-15T10:00:00Z", "device": "Web"},
        }
    ]
    df = normalize_documents(malformed)

    assert len(df) == 1
    assert pd.isna(df.iloc[0]["lon"])
    assert pd.isna(df.iloc[0]["lat"])


def test_normalize_documents_with_empty_list():
    df = normalize_documents([])

    assert df.empty
    assert list(df.columns) == DATA_COLUMNS


def test_normalize_documents_keywords_always_list():
    docs = load_json_documents()
    df = normalize_documents(docs)

    assert df["keywords"].apply(lambda v: isinstance(v, list)).all()
