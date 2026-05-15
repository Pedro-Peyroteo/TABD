import random
from datetime import datetime, timezone

import globalshop_bi.simulator as simulator
from globalshop_bi.simulator import (
    generate_review,
    load_generation_pools,
    sentiment_for_rating,
    simulator_config_from_env,
    validate_review_document,
)


def test_simulator_generates_valid_review_document():
    pools = load_generation_pools()
    review = generate_review(random.Random(42), 1, pools=pools, now=datetime(2026, 5, 9, tzinfo=timezone.utc))

    assert validate_review_document(review)
    assert review["review_id"].startswith("SIM-20260509000000-")
    assert review["metadata"]["source"] == "simulator"
    assert review["customer"]["location"]["coordinates"]["type"] == "Point"
    assert len(review["customer"]["location"]["coordinates"]["coordinates"]) == 2


def test_simulator_generation_is_deterministic_for_seed_and_timestamp():
    pools = load_generation_pools()
    now = datetime(2026, 5, 9, tzinfo=timezone.utc)

    first = generate_review(random.Random(7), 3, pools=pools, now=now)
    second = generate_review(random.Random(7), 3, pools=pools, now=now)

    assert first == second


def test_sentiment_for_rating_thresholds():
    assert sentiment_for_rating(5) == "Positive"
    assert sentiment_for_rating(4) == "Positive"
    assert sentiment_for_rating(3) == "Neutral"
    assert sentiment_for_rating(2) == "Negative"
    assert sentiment_for_rating(1) == "Negative"


def test_simulator_config_from_env_parses_values(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://mongo:27017")
    monkeypatch.setenv("MONGO_DB", "Demo")
    monkeypatch.setenv("MONGO_COLLECTION", "reviews_test")
    monkeypatch.setenv("SIM_INTERVAL_SECONDS", "0.25")
    monkeypatch.setenv("SIM_BATCH_SIZE", "3")
    monkeypatch.setenv("SIM_MAX_REVIEWS", "9")
    monkeypatch.setenv("SIM_SEED", "123")
    monkeypatch.setenv("SIM_RESET_ON_START", "true")

    config = simulator_config_from_env()

    assert config == {
        "mongo_uri": "mongodb://mongo:27017",
        "db_name": "Demo",
        "collection_name": "reviews_test",
        "interval_seconds": 0.25,
        "batch_size": 3,
        "max_reviews": 9,
        "seed": 123,
        "reset_on_start": True,
    }


def test_run_simulator_inserts_until_max_reviews_and_resets_simulated_docs(monkeypatch):
    class FakeCollection:
        def __init__(self):
            self.documents = [{"review_id": f"seed-{i}", "metadata": {"source": "seed"}} for i in range(25)]
            self.deleted_filter = None
            self.inserted_batches = []

        def count_documents(self, query):
            if query == {"metadata.source": "simulator"}:
                return sum(doc.get("metadata", {}).get("source") == "simulator" for doc in self.documents)
            return len(self.documents)

        def delete_many(self, query):
            self.deleted_filter = query
            self.documents = [
                doc for doc in self.documents
                if doc.get("metadata", {}).get("source") != "simulator"
            ]

        def insert_many(self, batch):
            self.inserted_batches.append(batch)
            self.documents.extend(batch)

    class FakeDatabase:
        def __init__(self, collection):
            self.collection = collection

        def __getitem__(self, name):
            return self.collection

    class FakeAdmin:
        def command(self, command):
            assert command == "ping"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.collection = collection
            self.admin = FakeAdmin()
            self.closed = False

        def __getitem__(self, name):
            return FakeDatabase(self.collection)

        def close(self):
            self.closed = True

    collection = FakeCollection()
    monkeypatch.setattr(simulator, "MongoClient", FakeClient)
    monkeypatch.setattr(simulator, "create_review_indexes", lambda c: None)
    monkeypatch.setattr(simulator.time, "sleep", lambda seconds: None)

    simulator.run_simulator({
        "mongo_uri": "mongodb://fake",
        "db_name": "GlobalShop",
        "collection_name": "reviews",
        "interval_seconds": 0,
        "batch_size": 2,
        "max_reviews": 27,
        "seed": 42,
        "reset_on_start": True,
    })

    assert collection.deleted_filter == {"metadata.source": "simulator"}
    assert len(collection.inserted_batches) == 1
    assert len(collection.inserted_batches[0]) == 2
    assert collection.count_documents({}) == 27
