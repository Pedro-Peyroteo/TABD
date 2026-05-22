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
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pymongo import GEOSPHERE, MongoClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MONGO_URI  = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB   = os.getenv("MONGO_DB",  "FitMap")
MONGO_COL  = os.getenv("MONGO_COLLECTION", "facilities")
EVENTS_COL = os.getenv("EVENTS_COLLECTION", "events")

# Cliente MongoDB partilhado (criado no arranque, fechado no encerramento).
_client: Optional[MongoClient] = None


def now_utc() -> datetime:
    """UTC naive — consistente com os datetimes guardados pelos seeds."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ensure_indexes(client: MongoClient) -> None:
    """Garante os índices geoespaciais (idempotente)."""
    db = client[MONGO_DB]
    db[MONGO_COL].create_index([("location", GEOSPHERE)])
    db[EVENTS_COL].create_index([("location", GEOSPHERE)])


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        _client.admin.command("ping")
        _ensure_indexes(_client)
        logger.info("Ligação MongoDB estabelecida (%s)", MONGO_DB)
    except Exception as exc:  # arranque tolerante: o seed pode ainda não ter corrido
        logger.warning("MongoDB indisponível no arranque: %s", exc)
    yield
    if _client is not None:
        _client.close()


app = FastAPI(title="FitMap API", version="1.0.0", lifespan=lifespan)
STATIC = Path(__file__).parent / "static"


def get_col():
    """Coleção de instalações no cliente partilhado."""
    return _client[MONGO_DB][MONGO_COL]


def get_events_col():
    """Coleção de eventos no cliente partilhado."""
    return _client[MONGO_DB][EVENTS_COL]


def _coords(doc: dict):
    """Extrai (lon, lat) de um documento GeoJSON de forma defensiva."""
    coords = (doc.get("location") or {}).get("coordinates") or []
    lon = coords[0] if len(coords) > 0 else None
    lat = coords[1] if len(coords) > 1 else None
    return lon, lat


def _serialize_event(ev: dict) -> dict:
    """Converte ObjectId + datetimes para JSON-friendly."""
    ev["_id"] = str(ev["_id"])
    for key in ("start_date", "end_date", "scraped_at"):
        if ev.get(key):
            ev[key] = ev[key].isoformat()
    ev["lon"], ev["lat"] = _coords(ev)
    return ev


# ─── Overview / KPIs ─────────────────────────────────────────────────────────

@app.get("/api/overview")
def overview():
    """
    KPIs globais via $facet — total, categorias, modalidades top, cidades top.
    Uma única round-trip ao MongoDB.
    """
    c = get_col()
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


# ─── Facilities listing (with filters) ───────────────────────────────────────

@app.get("/api/facilities")
def facilities(
    category: Optional[str] = None,
    sport:    Optional[str] = None,
    city:     Optional[str] = None,
    limit:    int = Query(2000, ge=1, le=5000),
):
    """Lista de instalações para o mapa. Suporta filtros."""
    c = get_col()
    match: dict = {}
    if category: match["category"]       = category
    if sport:    match["sports"]         = sport
    if city:     match["address.city"]   = city

    pipeline: list = []
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
        {"$limit": limit},   # sempre depois do $match
    ]
    return list(c.aggregate(pipeline))


@app.get("/api/facilities/{osm_id}")
def facility_detail(osm_id: int):
    """Detalhe completo de uma instalação."""
    c = get_col()
    doc = c.find_one({"osm_id": osm_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Instalação {osm_id} não encontrada.")
    # Achatamento das coordenadas para conveniência do frontend
    doc["lon"], doc["lat"] = _coords(doc)
    return doc


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
    c = get_col()
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
    c = get_col()
    try:
        points = [[float(v) for v in p.split(",")] for p in coords.split(";") if p.strip()]
    except ValueError:
        raise HTTPException(400, "Coordenadas inválidas no polígono.")
    if any(len(p) != 2 for p in points):
        raise HTTPException(400, "Cada ponto do polígono requer 'lon,lat'.")
    if len(points) < 3:
        raise HTTPException(400, "Polígono requer pelo menos 3 pontos.")
    for lon, lat in points:
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise HTTPException(400, "Coordenadas fora do intervalo válido.")
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


# ─── Listings auxiliares ─────────────────────────────────────────────────────

@app.get("/api/categories")
def categories():
    """Categorias e respetivo número de instalações."""
    c = get_col()
    return list(c.aggregate([
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "name": "$_id", "count": 1}},
        {"$sort": {"count": -1}},
    ]))


@app.get("/api/sports")
def sports(category: Optional[str] = None):
    """
    Modalidades distintas via $unwind.
    Se `category` for fornecido, devolve apenas modalidades que existem nessa categoria
    (evita combinações sem resultados, ex. Escalada + surfing).
    """
    c = get_col()
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


@app.get("/api/categories/by-sport")
def categories_by_sport(sport: str):
    """Categorias que oferecem uma dada modalidade."""
    c = get_col()
    return list(c.aggregate([
        {"$match": {"sports": sport}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "name": "$_id", "count": 1}},
        {"$sort":   {"count": -1}},
    ]))


@app.get("/api/cities")
def cities():
    """Cidades com pelo menos uma instalação registada."""
    c = get_col()
    return list(c.aggregate([
        {"$match": {"address.city": {"$ne": ""}}},
        {"$group": {"_id": "$address.city", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "name": "$_id", "count": 1}},
        {"$sort":   {"count": -1}},
    ]))


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
    c = get_events_col()
    match: dict = {}
    if sport:    match["sport"]    = sport
    if category: match["category"] = category
    if city:     match["city"]     = city
    if upcoming_only:
        match["end_date"] = {"$gte": now_utc()}

    pipeline = [
        {"$match": match},
        {"$sort":  {"start_date": 1}},
        {"$limit": limit},
    ]
    return [_serialize_event(e) for e in c.aggregate(pipeline)]


@app.get("/api/events/overview")
def events_overview():
    """Estatísticas dos eventos via $facet."""
    c = get_events_col()
    now = now_utc()
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


@app.get("/api/events/near")
def events_near(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(50, gt=0, le=500),
    upcoming_only: bool = True,
    limit: int = Query(20, ge=1, le=100),
):
    """$geoNear nos eventos — encontra eventos próximos."""
    c = get_events_col()
    match = {"end_date": {"$gte": now_utc()}} if upcoming_only else {}
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


@app.get("/api/events/by-facility/{osm_id}")
def events_by_facility(osm_id: int, radius_km: float = Query(5, gt=0, le=50)):
    """Eventos ligados a um facility OSM (ou próximos dele)."""
    c = get_events_col()
    # Primeiro: eventos explicitamente linkados
    direct = list(c.find({"near_facility.osm_id": osm_id}))

    # Se vazio, geo-near a partir do facility
    if not direct:
        facility = get_col().find_one({"osm_id": osm_id})
        if facility:
            lon, lat = _coords(facility)
            if lon is not None and lat is not None:
                direct = list(c.aggregate([
                    {"$geoNear": {
                        "near":          {"type": "Point", "coordinates": [lon, lat]},
                        "distanceField": "distancia_m",
                        "maxDistance":   radius_km * 1000,
                        "spherical":     True,
                        "key":           "location",
                        "query":         {"end_date": {"$gte": now_utc()}},
                    }},
                    {"$limit": 10},
                ]))
                for d in direct:
                    d["distKm"] = round(d.get("distancia_m", 0) / 1000, 2)
                    d.pop("distancia_m", None)
    # Filtrar só futuros
    now = now_utc()
    direct = [e for e in direct if e.get("end_date") and e["end_date"] >= now]
    direct.sort(key=lambda e: e.get("start_date") or now)
    return [_serialize_event(e) for e in direct[:10]]


@app.get("/api/events/sources")
def events_sources():
    """Lista de fontes (scrapers) com eventos futuros e contagens."""
    c = get_events_col()
    return list(c.aggregate([
        {"$match": {"end_date": {"$gte": now_utc()}}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "name": "$_id", "count": 1}},
        {"$sort":   {"count": -1}},
    ]))


@app.get("/api/events/sports")
def events_sports():
    """Lista de desportos com eventos futuros."""
    c = get_events_col()
    return list(c.aggregate([
        {"$match": {"end_date": {"$gte": now_utc()}}},
        {"$group": {"_id": "$sport", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "name": "$_id", "count": 1}},
        {"$sort": {"count": -1}},
    ]))


# ─── Static / SPA ────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    return FileResponse(STATIC / "index.html")
