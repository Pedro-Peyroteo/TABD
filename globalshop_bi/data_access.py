import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pymongo import MongoClient


BASE_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = BASE_DIR / "03_Implementacao" / "dataset_exemplo.json"
DATA_COLUMNS = [
    "review_id",
    "product_name",
    "category",
    "brand",
    "customer_location",
    "country",
    "lon",
    "lat",
    "membership",
    "rating",
    "sentiment",
    "verified_purchase",
    "keywords",
    "comment",
    "language",
    "timestamp",
    "device",
    "month",
    "week",
]


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


def load_json_documents(path=DATASET_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def documents_with_mongo_dates(documents):
    converted = []
    for document in documents:
        item = document.copy()
        item["metadata"] = item.get("metadata", {}).copy()
        item["metadata"]["timestamp"] = parse_timestamp(item["metadata"].get("timestamp"))
        converted.append(item)
    return converted


def normalize_documents(documents):
    rows = []
    for item in documents:
        loc = item.get("customer", {}).get("location", {})
        coords = loc.get("coordinates", {}).get("coordinates", [None, None])
        product = item.get("product", {})
        customer = item.get("customer", {})
        metrics = item.get("metrics", {})
        content = item.get("content", {})
        metadata = item.get("metadata", {})

        rows.append({
            "review_id": item.get("review_id"),
            "product_name": product.get("name"),
            "category": product.get("category"),
            "brand": product.get("brand"),
            "customer_location": loc.get("city"),
            "country": loc.get("country"),
            "lon": coords[0] if len(coords) > 0 else None,
            "lat": coords[1] if len(coords) > 1 else None,
            "membership": customer.get("membership"),
            "rating": metrics.get("rating"),
            "sentiment": metrics.get("sentiment"),
            "verified_purchase": metrics.get("verified_purchase", False),
            "keywords": content.get("keywords", []),
            "comment": content.get("comment"),
            "language": content.get("language", "pt"),
            "timestamp": metadata.get("timestamp"),
            "device": metadata.get("device", "Web"),
        })

    df = pd.DataFrame(rows, columns=DATA_COLUMNS[:-2])
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["verified_purchase"] = df["verified_purchase"].fillna(False).astype(bool)
    df["keywords"] = df["keywords"].apply(lambda value: value if isinstance(value, list) else [])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dt.tz_convert(None)
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)
    df["week"] = df["timestamp"].dt.to_period("W").astype(str)
    return df[DATA_COLUMNS]


def mongo_collection(mongo_uri, db_name, collection_name, timeout_ms=3000):
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=timeout_ms)
    client.admin.command("ping")
    return client, client[db_name][collection_name]


def load_mongo_documents(mongo_uri, db_name, collection_name):
    client, collection = mongo_collection(mongo_uri, db_name, collection_name)
    try:
        return list(collection.find({}, {"_id": 0}))
    finally:
        client.close()


def load_dashboard_data(data_source, mongo_uri, db_name, collection_name):
    requested_source = data_source.lower().strip()
    if requested_source not in {"auto", "mongo", "json"}:
        requested_source = "auto"

    if requested_source == "json":
        return normalize_documents(load_json_documents()), "JSON", None

    if requested_source == "mongo" and not mongo_uri:
        raise RuntimeError("DATA_SOURCE=mongo requer a variável MONGO_URI.")

    if requested_source in {"auto", "mongo"} and mongo_uri:
        try:
            mongo_docs = load_mongo_documents(mongo_uri, db_name, collection_name)
            if mongo_docs:
                return normalize_documents(mongo_docs), "MongoDB", None
            if requested_source == "mongo":
                return normalize_documents([]), "MongoDB", "A coleção MongoDB não contém documentos."
        except Exception as exc:
            if requested_source == "mongo":
                raise RuntimeError(f"Não foi possível carregar dados do MongoDB: {exc}") from exc

    json_message = None
    if requested_source == "auto" and mongo_uri:
        json_message = "MongoDB indisponível ou vazio; app em modo JSON."
    elif requested_source == "auto":
        json_message = "MONGO_URI não configurado; app em modo JSON."

    return normalize_documents(load_json_documents()), "JSON", json_message


def create_review_indexes(collection):
    collection.create_index("product.category")
    collection.create_index([("metrics.sentiment", 1), ("content.keywords", 1)])
    collection.create_index([("metadata.timestamp", -1)])
    collection.create_index([("customer.location.coordinates", "2dsphere")])
