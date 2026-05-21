"""
seed_events.py — Carrega eventos desportivos para a coleção `events` do MongoDB.

Pipeline:
1. Carrega `events_bootstrap.json` (eventos curados)
2. Hook para scrapers de federações (extensível — ver scrapers/)
3. Geocodifica cada venue via Nominatim (cache em ficheiro)
4. Liga cada evento à instalação OSM mais próxima via $geoNear
5. Insere com índice 2dsphere
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure scrapers/ is importable
sys.path.insert(0, str(Path(__file__).parent))

import requests
from pymongo import ASCENDING, GEOSPHERE, MongoClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB",  "FitMap")
EVENTS_COL    = os.getenv("EVENTS_COLLECTION",    "events")
FACILITIES_COL = os.getenv("MONGO_COLLECTION",    "facilities")

HERE = Path(__file__).parent
BOOTSTRAP_FILE = HERE / "events_bootstrap.json"
GEOCODE_CACHE  = HERE / "geocode_cache.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT    = "TABD-FitMap/1.0 (university project; contact: estudante@exemplo.pt)"


# ─── Geocoding via Nominatim ─────────────────────────────────────────────────

def load_geocode_cache() -> dict:
    if GEOCODE_CACHE.exists():
        return json.loads(GEOCODE_CACHE.read_text(encoding="utf-8"))
    return {}

def save_geocode_cache(cache: dict) -> None:
    GEOCODE_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def geocode(query: str, cache: dict) -> tuple[float, float] | None:
    """Retorna (lat, lon) via Nominatim, com cache + respeita rate limit (1 req/s)."""
    if query in cache:
        return tuple(cache[query]) if cache[query] else None

    try:
        time.sleep(1.1)  # rate limit
        response = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "pt"},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            cache[query] = None
            return None
        latlon = (float(results[0]["lat"]), float(results[0]["lon"]))
        cache[query] = list(latlon)
        return latlon
    except Exception as exc:
        logger.warning("Falha geocoding %r: %s", query, exc)
        cache[query] = None
        return None


# ─── Scraper hooks (extensível) ──────────────────────────────────────────────

def fetch_external_events() -> list[dict]:
    """
    Invoca scrapers reais (Wikidata + federações). Cada scraper é defensivo
    e devolve [] em caso de falha. Diferenciamos a `source` para attribution
    no UI ("Wikidata", "FPME", etc.) — bootstrap é "manual".
    """
    external: list[dict] = []
    try:
        from scrapers import wikidata, fpme, smoothcomp
        logger.info("→ A invocar scraper Wikidata...")
        external += wikidata.scrape()
        logger.info("→ A invocar scraper Smoothcomp (BJJ)...")
        external += smoothcomp.scrape()
        logger.info("→ A invocar scraper FPME...")
        external += fpme.scrape()
    except ImportError as exc:
        logger.warning("Scrapers indisponíveis: %s", exc)
    return external


# ─── Linking ao facility OSM mais próximo ────────────────────────────────────

def link_to_nearest_facility(events: list[dict], facilities) -> None:
    """Para cada evento com localização, encontra o facility OSM mais próximo (até 5 km)."""
    for ev in events:
        if "location" not in ev:
            continue
        lon, lat = ev["location"]["coordinates"]
        result = list(facilities.aggregate([
            {"$geoNear": {
                "near":          {"type": "Point", "coordinates": [lon, lat]},
                "distanceField": "_dist_m",
                "maxDistance":   5000,
                "spherical":     True,
                "key":           "location",
            }},
            {"$limit": 1},
            {"$project": {"osm_id": 1, "name": 1, "category": 1, "_dist_m": 1}},
        ]))
        if result:
            r = result[0]
            ev["near_facility"] = {
                "osm_id":   r["osm_id"],
                "name":     r.get("name", ""),
                "category": r.get("category", ""),
                "distance_m": round(r["_dist_m"]),
            }


# ─── Pipeline principal ──────────────────────────────────────────────────────

def normalize_event(ev: dict, lat: float, lon: float) -> dict:
    """Converte dicionário do bootstrap em documento MongoDB."""
    try:
        start = datetime.fromisoformat(ev["start_date"])
        end   = datetime.fromisoformat(ev["end_date"]) if ev.get("end_date") else None
    except ValueError as e:
        logger.warning("Datas inválidas em %r: %s", ev["title"], e)
        return None

    return {
        "title":        ev["title"],
        "sport":        ev["sport"],
        "category":     ev["category"],
        "organizer":    ev.get("organizer", ""),
        "source":       ev.get("source", "manual"),
        "source_url":   ev.get("source_url", ""),
        "start_date":   start,
        "end_date":     end,
        "venue_name":   ev["venue_name"],
        "city":         ev["city"],
        "address":      ev["address"],
        "description":  ev.get("description", ""),
        "registration_url": ev.get("registration_url", ""),
        "price":        ev.get("price", ""),
        "location":     {"type": "Point", "coordinates": [lon, lat]},
        "scraped_at":   datetime.utcnow(),
        "status":       "scheduled",
    }


def seed() -> None:
    # 1. Carregar bootstrap + scrapers
    bootstrap = json.loads(BOOTSTRAP_FILE.read_text(encoding="utf-8"))
    external  = fetch_external_events()
    raw_events = bootstrap + external
    logger.info("Eventos carregados: %d bootstrap + %d external", len(bootstrap), len(external))

    # 2. Geocodificar (preferir coords nativas do scraper, fallback Nominatim)
    cache = load_geocode_cache()
    geocoded: list[dict] = []
    for ev in raw_events:
        coords = ev.pop("_wikidata_coords", None)  # Wikidata pode trazer coords
        if not coords and ev.get("venue_name") and ev.get("address"):
            coords = geocode(f"{ev['venue_name']}, {ev['address']}, Portugal", cache)
        if not coords and ev.get("venue_name") and ev.get("city"):
            coords = geocode(f"{ev['venue_name']}, {ev['city']}, Portugal", cache)
        if not coords and ev.get("address"):
            coords = geocode(f"{ev['address']}, Portugal", cache)
        if not coords and ev.get("city"):
            coords = geocode(f"{ev['city']}, Portugal", cache)
        if not coords:
            logger.warning("Sem coordenadas para %r [%s] — ignorado",
                           ev["title"], ev.get("source", "?"))
            continue
        lat, lon = coords
        doc = normalize_event(ev, lat, lon)
        if doc:
            geocoded.append(doc)

    save_geocode_cache(cache)
    logger.info("Eventos geocodificados: %d", len(geocoded))

    # 3. Inserir em MongoDB
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    db = client[MONGO_DB]
    col = db[EVENTS_COL]

    logger.info("A limpar coleção %s.%s", MONGO_DB, EVENTS_COL)
    col.delete_many({})

    # 4. Linkar ao facility OSM mais próximo
    link_to_nearest_facility(geocoded, db[FACILITIES_COL])
    linked = sum(1 for e in geocoded if "near_facility" in e)
    logger.info("Eventos ligados a facility OSM próximo (≤5km): %d/%d", linked, len(geocoded))

    if geocoded:
        col.insert_many(geocoded)
        logger.info("Inseridos %d eventos", len(geocoded))

    # 5. Índices
    col.create_index([("location", GEOSPHERE)])
    col.create_index([("start_date", ASCENDING)])
    col.create_index("sport")
    col.create_index("category")
    col.create_index("city")
    logger.info("Índices criados: 2dsphere, start_date, sport, category, city")

    # 6. Stats
    by_sport = list(col.aggregate([
        {"$group": {"_id": "$sport", "count": {"$sum": 1}}},
        {"$sort":  {"count": -1}},
    ]))
    logger.info("Eventos por desporto:")
    for s in by_sport:
        logger.info("  %-15s %d", s["_id"], s["count"])

    client.close()


if __name__ == "__main__":
    try:
        seed()
    except Exception as exc:
        logger.error("Seed eventos falhou: %s", exc, exc_info=True)
        sys.exit(1)
