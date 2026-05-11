import random
from datetime import datetime, timezone

from globalshop_bi.simulator import generate_review, load_generation_pools, validate_review_document


def test_simulator_generates_valid_review_document():
    pools = load_generation_pools()
    review = generate_review(random.Random(42), 1, pools=pools, now=datetime(2026, 5, 9, tzinfo=timezone.utc))

    assert validate_review_document(review)
    assert review["review_id"].startswith("SIM-20260509000000-")
    assert review["metadata"]["source"] == "simulator"
    assert review["customer"]["location"]["coordinates"]["type"] == "Point"
    assert len(review["customer"]["location"]["coordinates"]["coordinates"]) == 2
