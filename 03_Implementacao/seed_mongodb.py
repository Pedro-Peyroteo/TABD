import os

from pymongo import MongoClient, UpdateOne

from globalshop_bi.data_access import (
    create_review_indexes,
    documents_with_mongo_dates,
    load_json_documents,
)


def load_documents():
    return documents_with_mongo_dates(load_json_documents())


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
        create_review_indexes(collection)

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
