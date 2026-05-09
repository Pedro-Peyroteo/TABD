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
