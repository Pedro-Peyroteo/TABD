"""
seed_osm.py — Obtem instalações desportivas reais do OpenStreetMap (Overpass API)
                e popula uma coleção MongoDB com índice 2dsphere.

Tipos de instalação cobertos em Portugal:
- Ginásios (leisure=fitness_centre)
- Centros desportivos (leisure=sports_centre)
- Piscinas (leisure=swimming_pool)
- Estúdios de dança (leisure=dance)
- Dojos / artes marciais (club=martial_arts, sport=judo|karate|aikido|...)
- Yoga / pilates (sport=yoga|pilates)
- Escalada, crossfit, boxe, kickboxing, muay thai
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import requests
from pymongo import GEOSPHERE, MongoClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB",  "FitMap")
MONGO_COL = os.getenv("MONGO_COLLECTION", "facilities")

OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
CACHE_FILE = Path(__file__).parent / "osm_cache.json"

OVERPASS_QUERY = """
[out:json][timeout:240];
area["ISO3166-1"="PT"][admin_level=2]->.pt;
(
  nwr[leisure=fitness_centre](area.pt);
  nwr[leisure=sports_centre](area.pt);
  nwr[leisure=swimming_pool](area.pt);
  nwr[leisure=dance](area.pt);
  nwr[club=martial_arts](area.pt);
  nwr[sport~"^(judo|karate|aikido|taekwondo|martial_arts|jiu-jitsu|boxing|kickboxing|muay_thai|yoga|pilates|climbing|crossfit|swimming|fitness|bodybuilding)$"](area.pt);
);
out center tags;
"""


# ─── Normalização ────────────────────────────────────────────────────────────

CATEGORY_LABELS = {
    "fitness_centre":  "Ginásio",
    "sports_centre":   "Centro Desportivo",
    "swimming_pool":   "Piscina",
    "dance_studio":    "Estúdio de Dança",
    "martial_arts":    "Artes Marciais",
    "yoga_studio":     "Yoga / Pilates",
    "climbing":        "Escalada",
    "crossfit":        "CrossFit",
    "boxing":          "Boxe / Kickboxing",
    "outro":           "Outro",
}


def derive_category(tags: dict) -> str:
    leisure = tags.get("leisure", "")
    sport   = tags.get("sport", "")
    club    = tags.get("club", "")

    if leisure == "fitness_centre":
        return "Ginásio"
    if leisure == "swimming_pool" or sport == "swimming":
        return "Piscina"
    if leisure == "sports_centre":
        return "Centro Desportivo"
    if leisure == "dance":
        return "Estúdio de Dança"
    if club == "martial_arts" or sport in {
        "judo", "karate", "aikido", "taekwondo", "martial_arts", "jiu-jitsu",
    }:
        return "Artes Marciais"
    if sport in {"yoga", "pilates"}:
        return "Yoga / Pilates"
    if sport == "climbing":
        return "Escalada"
    if sport == "crossfit":
        return "CrossFit"
    if sport in {"boxing", "kickboxing", "muay_thai"}:
        return "Boxe / Kickboxing"
    return "Outro"


def parse_sports(tags: dict) -> list[str]:
    sport = tags.get("sport", "")
    if not sport:
        return []
    return [s.strip() for s in sport.replace(",", ";").split(";") if s.strip()]


def _str(tags: dict, *keys: str) -> str:
    for k in keys:
        v = tags.get(k)
        if v:
            return str(v).strip()
    return ""


def normalize(element: dict) -> dict | None:
    tags = element.get("tags", {}) or {}

    if "lat" in element and "lon" in element:
        lat, lon = element["lat"], element["lon"]
    elif "center" in element:
        lat, lon = element["center"]["lat"], element["center"]["lon"]
    else:
        return None

    name = _str(tags, "name", "official_name", "alt_name")
    if not name:
        return None  # ignorar instalações anónimas (ruído OSM)

    return {
        "osm_id":   element["id"],
        "osm_type": element["type"],
        "name":     name,
        "category": derive_category(tags),
        "sports":   parse_sports(tags),
        "location": {
            "type":        "Point",
            "coordinates": [float(lon), float(lat)],  # GeoJSON: lon, lat
        },
        "address": {
            "street":      _str(tags, "addr:street"),
            "housenumber": _str(tags, "addr:housenumber"),
            "city":        _str(tags, "addr:city"),
            "postcode":    _str(tags, "addr:postcode"),
        },
        "contact": {
            "phone":   _str(tags, "phone", "contact:phone"),
            "website": _str(tags, "website", "contact:website"),
            "email":   _str(tags, "email", "contact:email"),
        },
        "opening_hours": _str(tags, "opening_hours"),
        "amenities": {
            "wheelchair": _str(tags, "wheelchair"),
            "parking":    _str(tags, "parking"),
            "shower":     _str(tags, "shower"),
            "indoor":     _str(tags, "indoor"),
            "covered":    _str(tags, "covered"),
            "access":     _str(tags, "access"),
        },
        "fee":      _str(tags, "fee", "charge"),
        "operator": _str(tags, "operator", "brand"),
    }


# ─── Fetch ───────────────────────────────────────────────────────────────────

def fetch_overpass() -> dict:
    if CACHE_FILE.exists() and os.getenv("OSM_USE_CACHE", "1") == "1":
        logger.info("A usar cache local %s", CACHE_FILE)
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))

    logger.info("A consultar Overpass API (pode demorar 30-180s)...")
    response = requests.post(
        OVERPASS_URL,
        data={"data": OVERPASS_QUERY},
        timeout=300,
        headers={"User-Agent": "TABD-FitMap/1.0 (university project)"},
    )
    response.raise_for_status()
    data = response.json()

    elements = data.get("elements", [])
    logger.info("Overpass devolveu %d elementos", len(elements))

    CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")
    logger.info("Cache gravada em %s", CACHE_FILE)
    return data


# ─── Seed ────────────────────────────────────────────────────────────────────

def seed() -> None:
    data = fetch_overpass()
    elements = data.get("elements", [])

    facilities = [f for f in (normalize(e) for e in elements) if f]
    logger.info("Normalizados %d documentos com nome + coordenadas", len(facilities))

    if not facilities:
        logger.error("Sem dados válidos a inserir — abortar.")
        sys.exit(1)

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    col = client[MONGO_DB][MONGO_COL]

    logger.info("A limpar coleção %s.%s", MONGO_DB, MONGO_COL)
    col.delete_many({})

    col.insert_many(facilities)
    logger.info("Inseridos %d documentos", len(facilities))

    col.create_index([("location", GEOSPHERE)])
    col.create_index("category")
    col.create_index("sports")
    col.create_index("address.city")
    logger.info("Índices criados: 2dsphere, category, sports, address.city")

    # Estatísticas
    stats = list(col.aggregate([
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort":  {"count": -1}},
    ]))
    logger.info("Distribuição por categoria:")
    for s in stats:
        logger.info("  %-20s %d", s["_id"], s["count"])

    total_cities = len(col.distinct("address.city", {"address.city": {"$ne": ""}}))
    logger.info("Cidades distintas com morada: %d", total_cities)

    client.close()


if __name__ == "__main__":
    try:
        seed()
    except Exception as exc:
        logger.error("Seed falhou: %s", exc, exc_info=True)
        sys.exit(1)
