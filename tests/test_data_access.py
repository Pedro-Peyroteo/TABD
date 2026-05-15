from datetime import datetime

import pandas as pd
import pytest

import globalshop_bi.data_access as data_access
from globalshop_bi.data_access import (
    DATA_COLUMNS,
    create_review_indexes,
    documents_with_mongo_dates,
    load_dashboard_data,
    load_json_documents,
    normalize_documents,
)


def test_json_normalization_returns_dashboard_columns():
    df = normalize_documents(load_json_documents())

    assert len(df) == 25
    assert list(df.columns) == DATA_COLUMNS
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert pd.api.types.is_float_dtype(df["lon"])
    assert pd.api.types.is_float_dtype(df["lat"])


def test_empty_filter_selection_is_detectable_before_geospatial_math():
    df = normalize_documents(load_json_documents())
    filtered_df = df[df["category"].isin([])]

    assert filtered_df.empty


def test_auto_mode_falls_back_to_json_without_mongo_uri():
    df, source, message = load_dashboard_data("auto", None, "GlobalShop", "reviews")

    assert len(df) == 25
    assert source == "JSON"
    assert "MONGO_URI" in message


def test_mongo_mode_requires_uri():
    with pytest.raises(RuntimeError, match="MONGO_URI"):
        load_dashboard_data("mongo", None, "GlobalShop", "reviews")


def test_seed_documents_convert_timestamps_for_mongo():
    documents = documents_with_mongo_dates(load_json_documents())

    assert len(documents) == 25
    assert isinstance(documents[0]["metadata"]["timestamp"], datetime)


def test_normalization_defaults_optional_fields_and_handles_partial_document():
    document = {
        "review_id": "r1",
        "product": {"name": "Produto", "category": "Tech", "brand": "Marca"},
        "customer": {
            "membership": "Gold",
            "location": {
                "city": "Lisboa",
                "country": "PT",
                "coordinates": {"type": "Point", "coordinates": [-9.1393, 38.7223]},
            },
        },
        "metrics": {"rating": "4", "sentiment": "Positive"},
        "content": {"keywords": "not-a-list", "comment": "Bom"},
        "metadata": {"timestamp": "2026-05-09T12:00:00Z"},
    }

    df = normalize_documents([document])
    row = df.iloc[0]

    assert row["rating"] == 4
    assert bool(row["verified_purchase"]) is False
    assert row["keywords"] == []
    assert row["language"] == "pt"
    assert row["device"] == "Web"
    assert row["month"] == "2026-05"


def test_auto_mode_falls_back_to_json_when_mongo_is_unavailable(monkeypatch):
    def unavailable(*args):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(data_access, "load_mongo_documents", unavailable)

    df, source, message = load_dashboard_data("auto", "mongodb://example", "GlobalShop", "reviews")

    assert len(df) == 25
    assert source == "JSON"
    assert "MongoDB" in message


def test_mongo_mode_wraps_connection_errors(monkeypatch):
    def unavailable(*args):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(data_access, "load_mongo_documents", unavailable)

    with pytest.raises(RuntimeError, match="Não foi possível carregar dados do MongoDB"):
        load_dashboard_data("mongo", "mongodb://example", "GlobalShop", "reviews")


def test_invalid_data_source_defaults_to_auto_without_mongo_uri():
    df, source, message = load_dashboard_data("unknown", None, "GlobalShop", "reviews")

    assert len(df) == 25
    assert source == "JSON"
    assert "MONGO_URI" in message


def test_create_review_indexes_requests_expected_indexes():
    class FakeCollection:
        def __init__(self):
            self.indexes = []

        def create_index(self, spec):
            self.indexes.append(spec)

    collection = FakeCollection()

    create_review_indexes(collection)

    assert collection.indexes == [
        "product.category",
        [("metrics.sentiment", 1), ("content.keywords", 1)],
        [("metadata.timestamp", -1)],
        [("customer.location.coordinates", "2dsphere")],
    ]
