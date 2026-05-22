"""
seed_bjj.py — Recolhe TODAS as academias de Jiu-Jitsu / BJJ de Portugal do OSM
              e faz upsert na coleção facilities (não apaga dados existentes).

Estratégia multi-camada:
  1. sport=jiu-jitsu | jiu_jitsu | brazilian_jiu_jitsu | bjj | grappling
  2. club=martial_arts com nome contendo jiu/bjj/grappling
  3. leisure=fitness_centre | sports_centre com nome contendo jiu/bjj/grappling
  4. Pesquisa por nome: "jiu.jitsu", "bjj", "gracie", "grappling" (qualquer tag)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import requests
from pymongo import GEOSPHERE, MongoClient, UpdateOne

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB",  "FitMap")
MONGO_COL = os.getenv("MONGO_COLLECTION", "facilities")
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")

# ─── Query Overpass ──────────────────────────────────────────────────────────
# Combina todas as formas como academias BJJ aparecem no OSM português

BJJ_QUERY = """
[out:json][timeout:120];
area["ISO3166-1"="PT"][admin_level=2]->.pt;
(
  nwr[sport~"jiu.jitsu|brazilian_jiu_jitsu|bjj|grappling|submission_wrestling",i](area.pt);
  nwr[name~"jiu.jitsu|jiujitsu|\\bbjj\\b|gracie|grappling",i](area.pt);
  nwr[club=martial_arts][name~"jiu.jitsu|jiujitsu|\\bbjj\\b|gracie|grappling",i](area.pt);
);
out center tags;
"""

# ─── Normalização ────────────────────────────────────────────────────────────

def _str(tags: dict, *keys: str) -> str:
    for k in keys:
        v = tags.get(k)
        if v:
            return str(v).strip()
    return ""


def parse_sports(tags: dict) -> list[str]:
    sport = tags.get("sport", "")
    if not sport:
        return []
    return [s.strip() for s in sport.replace(",", ";").split(";") if s.strip()]


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
        return None

    sports = parse_sports(tags)
    # Garantir que jiu-jitsu aparece na lista de sports
    if "jiu-jitsu" not in sports and "jiu_jitsu" not in sports:
        sports = ["jiu-jitsu"] + sports

    return {
        "osm_id":   element["id"],
        "osm_type": element["type"],
        "name":     name,
        "category": "Artes Marciais",
        "sports":   sports,
        "location": {
            "type":        "Point",
            "coordinates": [float(lon), float(lat)],
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


# ─── Main ────────────────────────────────────────────────────────────────────

def run() -> None:
    logger.info("A consultar Overpass API para academias BJJ em Portugal...")
    resp = requests.post(
        OVERPASS_URL,
        data={"data": BJJ_QUERY},
        timeout=180,
        headers={"User-Agent": "TABD-FitMap/1.0 (university project)"},
    )
    resp.raise_for_status()
    elements = resp.json().get("elements", [])
    logger.info("Overpass devolveu %d elementos", len(elements))

    docs = [f for f in (normalize(e) for e in elements) if f]
    # Deduplicar por osm_id
    seen: set[int] = set()
    unique = []
    for d in docs:
        if d["osm_id"] not in seen:
            seen.add(d["osm_id"])
            unique.append(d)
    logger.info("%d academias BJJ únicas com nome + coordenadas", len(unique))

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    col = client[MONGO_DB][MONGO_COL]

    # Upsert: actualiza se já existe, insere se não existe
    ops = [
        UpdateOne(
            {"osm_id": d["osm_id"]},
            {"$set": d},
            upsert=True,
        )
        for d in unique
    ]
    result = col.bulk_write(ops, ordered=False)
    logger.info(
        "Upsert concluído: %d inseridos, %d actualizados",
        result.upserted_count, result.modified_count,
    )

    # Garantir índices
    col.create_index([("location", GEOSPHERE)], background=True)
    col.create_index("sports", background=True)

    # Estatísticas finais
    total_bjj = col.count_documents({
        "$or": [
            {"sports": {"$in": ["jiu-jitsu", "jiu_jitsu", "bjj", "grappling"]}},
            {"name": {"$regex": "jiu.jitsu|jiujitsu|bjj|gracie|grappling", "$options": "i"}},
        ]
    })
    logger.info("Total de academias BJJ/grappling na BD: %d", total_bjj)

    # Mostrar lista
    bjj_docs = list(col.find(
        {"$or": [
            {"sports": {"$in": ["jiu-jitsu", "jiu_jitsu", "bjj", "grappling"]}},
            {"name": {"$regex": "jiu.jitsu|jiujitsu|\\bbjj\\b|gracie|grappling", "$options": "i"}},
        ]},
        {"name": 1, "address.city": 1, "sports": 1, "_id": 0},
        sort=[("address.city", 1), ("name", 1)],
    ))
    logger.info("\nLista de academias BJJ/grappling em Portugal:")
    for d in bjj_docs:
        city = d.get("address", {}).get("city") or "—"
        logger.info("  [%s] %s  |  sports: %s", city, d["name"], d.get("sports", []))

    client.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        logger.error("Falhou: %s", exc, exc_info=True)
        sys.exit(1)
