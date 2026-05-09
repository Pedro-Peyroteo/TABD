import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient, UpdateOne


BASE_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = BASE_DIR / "03_Implementacao" / "dataset_exemplo.json"


def parse_timestamp(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.astimezone(timezone.utc)
    return value


def load_documents():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        documents = json.load(f)

    for document in documents:
        metadata = document.setdefault("metadata", {})
        metadata["timestamp"] = parse_timestamp(metadata.get("timestamp"))
    return documents


def seed_mongodb():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB", "GlobalShop")
    collection_name = os.getenv("MONGO_COLLECTION", "reviews")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        collection = client[db_name][collection_name]
        documents = load_documents()
        operations = [
            UpdateOne({"review_id": document["review_id"]}, {"$set": document}, upsert=True)
            for document in documents
        ]

        result = collection.bulk_write(operations, ordered=False) if operations else None
        collection.create_index("product.category")
        collection.create_index([("metrics.sentiment", 1), ("content.keywords", 1)])
        collection.create_index([("metadata.timestamp", -1)])
        collection.create_index([("customer.location.coordinates", "2dsphere")])

        count = collection.count_documents({})
        matched = result.matched_count if result else 0
        upserted = len(result.upserted_ids) if result else 0
        modified = result.modified_count if result else 0
        print(
            f"Seed concluído em {db_name}.{collection_name}: "
            f"{count} documentos, {matched} encontrados, {modified} atualizados, {upserted} inseridos."
        )
    finally:
        client.close()


if __name__ == "__main__":
    seed_mongodb()
