import os
import random
import time
from copy import deepcopy
from datetime import datetime, timezone

from pymongo import MongoClient

from globalshop_bi.data_access import create_review_indexes, load_json_documents


KEYWORDS_BY_SENTIMENT = {
    "Positive": ["qualidade", "rapidez", "recomendo", "satisfeito", "design", "entrega"],
    "Neutral": ["ok", "preco", "normal", "esperado", "embalagem", "utilizacao"],
    "Negative": ["defeito", "atraso", "avaria", "ruido", "devolucao", "suporte"],
}
COMMENTS_BY_SENTIMENT = {
    "Positive": [
        "Produto superou as expectativas e chegou rapidamente.",
        "Boa qualidade e experiência de compra muito positiva.",
        "Voltaria a comprar, funcionou muito bem no dia a dia.",
    ],
    "Neutral": [
        "Produto cumpre o esperado, sem grandes surpresas.",
        "A experiência foi razoável, mas podia ser mais consistente.",
        "Funciona bem, embora alguns detalhes possam melhorar.",
    ],
    "Negative": [
        "Produto apresentou problemas pouco depois da entrega.",
        "Entrega atrasada e suporte pouco claro durante o processo.",
        "A qualidade ficou abaixo do esperado para esta categoria.",
    ],
}
RATING_WEIGHTS = [0.10, 0.15, 0.20, 0.25, 0.30]


def sentiment_for_rating(rating):
    if rating >= 4:
        return "Positive"
    if rating == 3:
        return "Neutral"
    return "Negative"


def load_generation_pools():
    seed_docs = load_json_documents()
    products = []
    locations = []
    memberships = set()
    devices = set()

    for doc in seed_docs:
        products.append(deepcopy(doc["product"]))
        locations.append(deepcopy(doc["customer"]["location"]))
        memberships.add(doc["customer"]["membership"])
        devices.add(doc["metadata"].get("device", "Web"))

    unique_products = {product["product_id"]: product for product in products}
    unique_locations = {location["city"]: location for location in locations}
    return {
        "products": list(unique_products.values()),
        "locations": list(unique_locations.values()),
        "memberships": sorted(memberships),
        "devices": sorted(devices),
    }


def generate_review(rng, sequence, pools=None, now=None):
    pools = pools or load_generation_pools()
    now = now or datetime.now(timezone.utc)
    product = deepcopy(rng.choice(pools["products"]))
    location = deepcopy(rng.choice(pools["locations"]))
    membership = rng.choice(pools["memberships"])
    device = rng.choice(pools["devices"])
    rating = rng.choices([1, 2, 3, 4, 5], weights=RATING_WEIGHTS, k=1)[0]
    sentiment = sentiment_for_rating(rating)
    keywords = rng.sample(KEYWORDS_BY_SENTIMENT[sentiment], k=3)

    return {
        "review_id": f"SIM-{now.strftime('%Y%m%d%H%M%S')}-{sequence:06d}",
        "product": product,
        "customer": {
            "customer_id": f"SIMC-{sequence:06d}",
            "name": f"Cliente Simulado {sequence}",
            "location": location,
            "membership": membership,
        },
        "metrics": {
            "rating": rating,
            "sentiment": sentiment,
            "verified_purchase": rng.random() >= 0.08,
        },
        "content": {
            "comment": rng.choice(COMMENTS_BY_SENTIMENT[sentiment]),
            "keywords": keywords,
            "language": "pt",
        },
        "metadata": {
            "timestamp": now,
            "device": device,
            "source": "simulator",
        },
    }


def validate_review_document(document):
    coords = document["customer"]["location"]["coordinates"]
    return (
        document.get("review_id")
        and document["product"].get("name")
        and document["metrics"].get("sentiment") in {"Positive", "Neutral", "Negative"}
        and 1 <= document["metrics"].get("rating", 0) <= 5
        and coords.get("type") == "Point"
        and len(coords.get("coordinates", [])) == 2
    )


def simulator_config_from_env():
    return {
        "mongo_uri": os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        "db_name": os.getenv("MONGO_DB", "GlobalShop"),
        "collection_name": os.getenv("MONGO_COLLECTION", "reviews"),
        "interval_seconds": float(os.getenv("SIM_INTERVAL_SECONDS", "5")),
        "batch_size": int(os.getenv("SIM_BATCH_SIZE", "1")),
        "max_reviews": int(os.getenv("SIM_MAX_REVIEWS", "500")),
        "seed": int(os.getenv("SIM_SEED", "42")),
        "reset_on_start": os.getenv("SIM_RESET_ON_START", "false").lower() == "true",
    }


def run_simulator(config=None):
    config = config or simulator_config_from_env()
    rng = random.Random(config["seed"])
    pools = load_generation_pools()
    client = MongoClient(config["mongo_uri"], serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        collection = client[config["db_name"]][config["collection_name"]]
        create_review_indexes(collection)
        if config["reset_on_start"]:
            collection.delete_many({"metadata.source": "simulator"})

        sequence = collection.count_documents({"metadata.source": "simulator"}) + 1
        while True:
            total = collection.count_documents({})
            if config["max_reviews"] > 0 and total >= config["max_reviews"]:
                print(f"Simulação concluída: limite de {config['max_reviews']} reviews atingido.")
                break

            batch = []
            for _ in range(config["batch_size"]):
                review = generate_review(rng, sequence, pools=pools)
                if not validate_review_document(review):
                    raise ValueError(f"Documento simulado inválido: {review.get('review_id')}")
                batch.append(review)
                sequence += 1

            if batch:
                collection.insert_many(batch)
                print(f"Inseridas {len(batch)} reviews simuladas. Total atual: {collection.count_documents({})}")
            time.sleep(config["interval_seconds"])
    finally:
        client.close()
