import importlib.util
from datetime import datetime, timezone
from pathlib import Path


def load_seed_module():
    path = Path(__file__).resolve().parents[1] / "03_Implementacao" / "seed_mongodb.py"
    spec = importlib.util.spec_from_file_location("seed_mongodb_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_mongodb_upserts_by_review_id_creates_indexes_and_closes(monkeypatch):
    seed_module = load_seed_module()
    document = {
        "review_id": "r1",
        "metadata": {"timestamp": datetime(2026, 5, 9, tzinfo=timezone.utc)},
    }
    state = {}

    class FakeResult:
        matched_count = 0
        modified_count = 0
        upserted_ids = {0: "mongo-id"}

    class FakeCollection:
        def __init__(self):
            self.operations = None

        def bulk_write(self, operations, ordered):
            self.operations = operations
            assert ordered is False
            return FakeResult()

        def count_documents(self, query):
            assert query == {}
            return 1

    class FakeDatabase:
        def __init__(self, collection):
            self.collection = collection

        def __getitem__(self, name):
            assert name == "reviews"
            return self.collection

    class FakeAdmin:
        def command(self, command):
            assert command == "ping"

    class FakeClient:
        def __init__(self, uri, serverSelectionTimeoutMS):
            assert uri == "mongodb://fake"
            assert serverSelectionTimeoutMS == 5000
            self.collection = FakeCollection()
            self.admin = FakeAdmin()
            state["client"] = self

        def __getitem__(self, name):
            assert name == "GlobalShop"
            return FakeDatabase(self.collection)

        def close(self):
            state["closed"] = True

    def fake_update_one(filter_doc, update_doc, upsert):
        return {"filter": filter_doc, "update": update_doc, "upsert": upsert}

    monkeypatch.setenv("MONGO_URI", "mongodb://fake")
    monkeypatch.setenv("MONGO_DB", "GlobalShop")
    monkeypatch.setenv("MONGO_COLLECTION", "reviews")
    monkeypatch.setattr(seed_module, "MongoClient", FakeClient)
    monkeypatch.setattr(seed_module, "UpdateOne", fake_update_one)
    monkeypatch.setattr(seed_module, "load_documents", lambda: [document])
    monkeypatch.setattr(seed_module, "create_review_indexes", lambda collection: state.setdefault("indexed", collection))

    seed_module.seed_mongodb()

    assert state["client"].collection.operations == [
        {"filter": {"review_id": "r1"}, "update": {"$set": document}, "upsert": True}
    ]
    assert state["indexed"] is state["client"].collection
    assert state["closed"] is True
