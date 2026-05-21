"""
FitMap — FastAPI Backend
========================
API para descoberta de instalações desportivas em Portugal usando dados reais
do OpenStreetMap e MongoDB com índice 2dsphere.

Endpoints chave demonstram:
- $geoNear   (pesquisa por raio)
- $geoWithin (seleção poligonal pelo utilizador)
- $facet     (KPIs paralelos numa só query)
- $unwind    (modalidades multivaloradas)
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MONGO_URI  = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB   = os.getenv("MONGO_DB",  "FitMap")
MONGO_COL  = os.getenv("MONGO_COLLECTION", "facilities")
EVENTS_COL = os.getenv("EVENTS_COLLECTION", "events")

app = FastAPI(title="FitMap API", version="1.0.0")
STATIC = Path(__file__).parent / "static"


def get_col():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client, client[MONGO_DB][MONGO_COL]


def get_events_col():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client, client[MONGO_DB][EVENTS_COL]


def _serialize_event(ev: dict) -> dict:
    """Converte ObjectId + datetimes para JSON-friendly."""
    ev["_id"] = str(ev["_id"])
    if ev.get("start_date"):
        ev["start_date"] = ev["start_date"].isoformat()
    if ev.get("end_date"):
        ev["end_date"] = ev["end_date"].isoformat()
    if ev.get("scraped_at"):
        ev["scraped_at"] = ev["scraped_at"].isoformat()
    ev["lat"] = ev["location"]["coordinates"][1]
    ev["lon"] = ev["location"]["coordinates"][0]
    return ev


# ─── Overview / KPIs ─────────────────────────────────────────────────────────

@app.get("/api/overview")
def overview():
    """
    KPIs globais via $facet — total, categorias, modalidades top, cidades top.
    Uma única round-trip ao MongoDB.
    """
    client, c = get_col()
    try:
        pipeline = [{
            "$facet": {
                "totals":     [{"$count": "total"}],
                "categories": [
                    {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                    {"$sort":  {"count": -1}},
                ],
                "topSports": [
                    {"$unwind": "$sports"},
                    {"$group": {"_id": "$sports", "count": {"$sum": 1}}},
                    {"$sort":  {"count": -1}},
                    {"$limit": 10},
                ],
                "topCities": [
                    {"$match": {"address.city": {"$ne": ""}}},
                    {"$group": {"_id": "$address.city", "count": {"$sum": 1}}},
                    {"$sort":  {"count": -1}},
                    {"$limit": 12},
                ],
                "withWebsite": [
                    {"$match": {"contact.website": {"$ne": ""}}},
                    {"$count": "n"},
                ],
                "withHours": [
                    {"$match": {"opening_hours": {"$ne": ""}}},
                    {"$count": "n"},
                ],
            }
        }]
        res = list(c.aggregate(pipeline))[0]
        total = res["totals"][0]["total"] if res["totals"] else 0
        return {
            "total":       total,
            "categories":  [{"name": x["_id"], "count": x["count"]} for x in res["categories"]],
            "topSports":   [{"name": x["_id"], "count": x["count"]} for x in res["topSports"]],
            "topCities":   [{"name": x["_id"], "count": x["count"]} for x in res["topCities"]],
            "withWebsite": res["withWebsite"][0]["n"] if res["withWebsite"] else 0,
            "withHours":   res["withHours"][0]["n"]   if res["withHours"]   else 0,
        }
    finally:
        client.close()


# ─── Facilities listing (with filters) ───────────────────────────────────────

@app.get("/api/facilities")
def facilities(
    category: Optional[str] = None,
    sport:    Optional[str] = None,
    city:     Optional[str] = None,
    limit:    int = Query(2000, ge=1, le=5000),
):
    """Lista de instalações para o mapa. Suporta filtros."""
    client, c = get_col()
    try:
        match: dict = {}
        if category: match["category"]       = category
        if sport:    match["sports"]         = sport
        if city:     match["address.city"]   = city

        pipeline = []
        if match:
            pipeline.append({"$match": match})
        pipeline += [
            {"$project": {
                "_id":      0,
                "osm_id":   1,
                "name":     1,
                "category": 1,
                "sports":   1,
                "city":     "$address.city",
                "lat":      {"$arrayElemAt": ["$location.coordinates", 1]},
                "lon":      {"$arrayElemAt": ["$location.coordinates", 0]},
                "hasHours": {"$ne": ["$opening_hours", ""]},
                "hasWeb":   {"$ne": ["$contact.website", ""]},
            }},
            {"$limit": limit},
        ]
        return list(c.aggregate(pipeline))
    finally:
        client.close()


@app.get("/api/facilities/{osm_id}")
def facility_detail(osm_id: int):
    """Detalhe completo de uma instalação."""
    client, c = get_col()
    try:
        doc = c.find_one({"osm_id": osm_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, f"Instalação {osm_id} não encontrada.")
        # Achatamento das coordenadas para conveniência do frontend
        doc["lat"] = doc["location"]["coordinates"][1]
        doc["lon"] = doc["location"]["coordinates"][0]
        return doc
    finally:
        client.close()


# ─── Geo: $geoNear ───────────────────────────────────────────────────────────

@app.get("/api/geo/nearby")
def nearby(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(5, gt=0, le=100),
    category: Optional[str] = None,
    sport:    Optional[str] = None,
    limit:    int = Query(50, ge=1, le=200),
):
    """
    $geoNear — instalações dentro de um raio em redor de um ponto.
    Resultados ordenados por distância crescente; permite filtros sobrepostos.
    Requer índice 2dsphere em `location`.
    """
    client, c = get_col()
    try:
        query: dict = {}
        if category: query["category"] = category
        if sport:    query["sports"]   = sport

        pipeline = [
            {"$geoNear": {
                "near":           {"type": "Point", "coordinates": [lon, lat]},
                "distanceField":  "distancia_m",
                "maxDistance":    radius_km * 1000,
                "spherical":      True,
                "key":            "location",
                "query":          query,
            }},
            {"$limit": limit},
            {"$project": {
                "_id":      0,
                "osm_id":   1,
                "name":     1,
                "category": 1,
                "sports":   1,
                "city":     "$address.city",
                "street":   "$address.street",
                "lat":      {"$arrayElemAt": ["$location.coordinates", 1]},
                "lon":      {"$arrayElemAt": ["$location.coordinates", 0]},
                "distKm":   {"$round": [{"$divide": ["$distancia_m", 1000]}, 2]},
                "phone":    "$contact.phone",
                "website":  "$contact.website",
                "hours":    "$opening_hours",
            }},
        ]
        return list(c.aggregate(pipeline))
    finally:
        client.close()


# ─── Geo: $geoWithin (polígono) ──────────────────────────────────────────────

@app.get("/api/geo/within")
def within_area(
    coords:   str = Query(..., description="lon,lat;lon,lat;... (polígono)"),
    category: Optional[str] = None,
    sport:    Optional[str] = None,
):
    """
    $geoWithin — instalações dentro do polígono desenhado pelo utilizador no mapa.
    Demonstra seleção espacial interativa + filtros combinados.
    """
    client, c = get_col()
    try:
        points = [[float(v) for v in p.split(",")] for p in coords.split(";") if p.strip()]
        if len(points) < 3:
            raise HTTPException(400, "Polígono requer pelo menos 3 pontos.")
        ring = points + [points[0]]

        match: dict = {
            "location": {
                "$geoWithin": {
                    "$geometry": {"type": "Polygon", "coordinates": [ring]}
                }
            }
        }
        if category: match["category"] = category
        if sport:    match["sports"]   = sport

        pipeline = [
            {"$match": match},
            {"$facet": {
                "items": [
                    {"$project": {
                        "_id":      0,
                        "osm_id":   1,
                        "name":     1,
                        "category": 1,
                        "sports":   1,
                        "city":     "$address.city",
                        "lat":      {"$arrayElemAt": ["$location.coordinates", 1]},
                        "lon":      {"$arrayElemAt": ["$location.coordinates", 0]},
                    }},
                    {"$limit": 500},
                ],
                "summary": [
                    {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                    {"$sort":  {"count": -1}},
                ],
                "totals": [{"$count": "total"}],
            }},
        ]
        res  = list(c.aggregate(pipeline))[0]
        return {
            "total":      res["totals"][0]["total"] if res["totals"] else 0,
            "items":      res["items"],
            "byCategory": [{"name": x["_id"], "count": x["count"]} for x in res["summary"]],
        }
    finally:
        client.close()


# ─── Listings auxiliares ─────────────────────────────────────────────────────

@app.get("/api/categories")
def categories():
    """Categorias e respetivo número de instalações."""
    client, c = get_col()
    try:
        return list(c.aggregate([
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "name": "$_id", "count": 1}},
            {"$sort": {"count": -1}},
        ]))
    finally:
        client.close()


@app.get("/api/sports")
def sports(category: Optional[str] = None):
    """
    Modalidades distintas via $unwind.
    Se `category` for fornecido, devolve apenas modalidades que existem nessa categoria
    (evita combinações sem resultados, ex. Escalada + surfing).
    """
    client, c = get_col()
    try:
        pipeline = []
        if category:
            pipeline.append({"$match": {"category": category}})
        pipeline += [
            {"$unwind": "$sports"},
            {"$group":  {"_id": "$sports", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "name": "$_id", "count": 1}},
            {"$sort":   {"count": -1}},
        ]
        return list(c.aggregate(pipeline))
    finally:
        client.close()


@app.get("/api/categories/by-sport")
def categories_by_sport(sport: str):
    """Categorias que oferecem uma dada modalidade."""
    client, c = get_col()
    try:
        return list(c.aggregate([
            {"$match": {"sports": sport}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "name": "$_id", "count": 1}},
            {"$sort":   {"count": -1}},
        ]))
    finally:
        client.close()


@app.get("/api/cities")
def cities():
    """Cidades com pelo menos uma instalação registada."""
    client, c = get_col()
    try:
        return list(c.aggregate([
            {"$match": {"address.city": {"$ne": ""}}},
            {"$group": {"_id": "$address.city", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "name": "$_id", "count": 1}},
            {"$sort":   {"count": -1}},
        ]))
    finally:
        client.close()


# ═══════════════════════════════════════════════════════════════════════════
#   EVENTS  — sports events with geospatial + temporal queries
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/events")
def events_list(
    sport:    Optional[str] = None,
    category: Optional[str] = None,
    city:     Optional[str] = None,
    upcoming_only: bool = True,
    limit:    int = Query(100, ge=1, le=500),
):
    """Lista de eventos com filtros e opção de só futuros."""
    client, c = get_events_col()
    try:
        match: dict = {}
        if sport:    match["sport"]    = sport
        if category: match["category"] = category
        if city:     match["city"]     = city
        if upcoming_only:
            match["end_date"] = {"$gte": datetime.utcnow()}

        pipeline = [
            {"$match": match},
            {"$sort":  {"start_date": 1}},
            {"$limit": limit},
        ]
        return [_serialize_event(e) for e in c.aggregate(pipeline)]
    finally:
        client.close()


@app.get("/api/events/overview")
def events_overview():
    """Estatísticas dos eventos via $facet."""
    client, c = get_events_col()
    try:
        now = datetime.utcnow()
        pipeline = [{
            "$facet": {
                "totals": [
                    {"$match": {"end_date": {"$gte": now}}},
                    {"$count": "total"},
                ],
                "bySport": [
                    {"$match": {"end_date": {"$gte": now}}},
                    {"$group": {"_id": "$sport", "count": {"$sum": 1}}},
                    {"$sort":  {"count": -1}},
                ],
                "byCategory": [
                    {"$match": {"end_date": {"$gte": now}}},
                    {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                    {"$sort":  {"count": -1}},
                ],
                "byCity": [
                    {"$match": {"end_date": {"$gte": now}}},
                    {"$group": {"_id": "$city", "count": {"$sum": 1}}},
                    {"$sort":  {"count": -1}},
                    {"$limit": 10},
                ],
            }
        }]
        res = list(c.aggregate(pipeline))[0]
        return {
            "upcoming": res["totals"][0]["total"] if res["totals"] else 0,
            "bySport":    [{"name": x["_id"], "count": x["count"]} for x in res["bySport"]],
            "byCategory": [{"name": x["_id"], "count": x["count"]} for x in res["byCategory"]],
            "byCity":     [{"name": x["_id"], "count": x["count"]} for x in res["byCity"]],
        }
    finally:
        client.close()


@app.get("/api/events/near")
def events_near(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(50, gt=0, le=500),
    upcoming_only: bool = True,
    limit: int = Query(20, ge=1, le=100),
):
    """$geoNear nos eventos — encontra eventos próximos."""
    client, c = get_events_col()
    try:
        match = {"end_date": {"$gte": datetime.utcnow()}} if upcoming_only else {}
        pipeline = [
            {"$geoNear": {
                "near":          {"type": "Point", "coordinates": [lon, lat]},
                "distanceField": "distancia_m",
                "maxDistance":   radius_km * 1000,
                "spherical":     True,
                "key":           "location",
                "query":         match,
            }},
            {"$limit": limit},
        ]
        events = []
        for ev in c.aggregate(pipeline):
            ev["distKm"] = round(ev["distancia_m"] / 1000, 2)
            del ev["distancia_m"]
            events.append(_serialize_event(ev))
        return events
    finally:
        client.close()


@app.get("/api/events/by-facility/{osm_id}")
def events_by_facility(osm_id: int, radius_km: float = Query(5, gt=0, le=50)):
    """Eventos ligados a um facility OSM (ou próximos dele)."""
    client, c = get_events_col()
    try:
        # Primeiro: eventos explicitamente linkados
        direct = list(c.find({"near_facility.osm_id": osm_id}))

        # Se vazio, geo-near a partir do facility
        if not direct:
            fclient, fcol = get_col()
            try:
                facility = fcol.find_one({"osm_id": osm_id})
            finally:
                fclient.close()
            if facility:
                lon, lat = facility["location"]["coordinates"]
                direct = list(c.aggregate([
                    {"$geoNear": {
                        "near":          {"type": "Point", "coordinates": [lon, lat]},
                        "distanceField": "distancia_m",
                        "maxDistance":   radius_km * 1000,
                        "spherical":     True,
                        "key":           "location",
                        "query":         {"end_date": {"$gte": datetime.utcnow()}},
                    }},
                    {"$limit": 10},
                ]))
                for d in direct:
                    d["distKm"] = round(d.get("distancia_m", 0) / 1000, 2)
                    d.pop("distancia_m", None)
        # Filtrar só futuros
        direct = [e for e in direct if e.get("end_date") and e["end_date"] >= datetime.utcnow()]
        direct.sort(key=lambda e: e["start_date"])
        return [_serialize_event(e) for e in direct[:10]]
    finally:
        client.close()


@app.get("/api/events/sources")
def events_sources():
    """Lista de fontes (scrapers) com eventos futuros e contagens."""
    client, c = get_events_col()
    try:
        return list(c.aggregate([
            {"$match": {"end_date": {"$gte": datetime.utcnow()}}},
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "name": "$_id", "count": 1}},
            {"$sort":   {"count": -1}},
        ]))
    finally:
        client.close()


@app.get("/api/events/sports")
def events_sports():
    """Lista de desportos com eventos futuros."""
    client, c = get_events_col()
    try:
        return list(c.aggregate([
            {"$match": {"end_date": {"$gte": datetime.utcnow()}}},
            {"$group": {"_id": "$sport", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "name": "$_id", "count": 1}},
            {"$sort": {"count": -1}},
        ]))
    finally:
        client.close()


# ─── Static / SPA ────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    return FileResponse(STATIC / "index.html")
