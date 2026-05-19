import random
from datetime import datetime, timezone

import pytest

from globalshop_bi.simulator import (
    generate_review,
    load_generation_pools,
    sentiment_for_rating,
    validate_review_document,
)


def test_simulator_generates_valid_review_document():
    pools = load_generation_pools()
    review = generate_review(random.Random(42), 1, pools=pools, now=datetime(2026, 5, 9, tzinfo=timezone.utc))

    assert validate_review_document(review)
    assert review["metadata"]["source"] == "simulator"
    assert review["customer"]["location"]["coordinates"]["type"] == "Point"
    assert len(review["customer"]["location"]["coordinates"]["coordinates"]) == 2


def test_review_id_includes_microseconds():
    pools = load_generation_pools()
    review = generate_review(random.Random(1), 1, pools=pools, now=datetime(2026, 5, 9, 12, 0, 0, 123456, tzinfo=timezone.utc))

    assert review["review_id"].startswith("SIM-")
    assert "123456" in review["review_id"]


def test_no_review_id_collision_same_second():
    pools = load_generation_pools()
    now = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)
    r1 = generate_review(random.Random(1), 1, pools=pools, now=now)
    r2 = generate_review(random.Random(2), 2, pools=pools, now=now)

    assert r1["review_id"] != r2["review_id"]


@pytest.mark.parametrize("rating,expected", [
    (5, "Positive"),
    (4, "Positive"),
    (3, "Neutral"),
    (2, "Negative"),
    (1, "Negative"),
])
def test_sentiment_for_rating(rating, expected):
    assert sentiment_for_rating(rating) == expected


def test_generate_review_rating_in_valid_range():
    pools = load_generation_pools()
    rng = random.Random(99)
    for seq in range(1, 20):
        review = generate_review(rng, seq, pools=pools)
        assert 1 <= review["metrics"]["rating"] <= 5


def test_generate_review_sentiment_matches_rating():
    pools = load_generation_pools()
    rng = random.Random(7)
    for seq in range(1, 20):
        review = generate_review(rng, seq, pools=pools)
        rating = review["metrics"]["rating"]
        sentiment = review["metrics"]["sentiment"]
        assert sentiment == sentiment_for_rating(rating)


def test_load_generation_pools_structure():
    pools = load_generation_pools()

    assert "products" in pools
    assert "locations" in pools
    assert "memberships" in pools
    assert "devices" in pools
    assert len(pools["products"]) > 0
    assert len(pools["locations"]) > 0


def test_validate_review_document_rejects_invalid():
    pools = load_generation_pools()
    review = generate_review(random.Random(42), 1, pools=pools)
    review["metrics"]["sentiment"] = "Unknown"

    assert not validate_review_document(review)
