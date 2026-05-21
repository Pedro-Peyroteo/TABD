"""
Wikidata SPARQL scraper — eventos desportivos em Portugal.

Usa o endpoint público query.wikidata.org. Dados verificáveis,
estáveis e versionados. Não precisa de API key.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

WIKIDATA_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "TABD-FitMap/1.0 (university project; https://example.pt)"

# Eventos desportivos em Portugal com data futura.
# - wd:Q16510064 = sporting event
# - wd:Q45       = Portugal
# - P580/P582/P585 = start / end / point in time
# - P641 = sport
# - P276 = location
# - P625 = coordinates
SPARQL = """
SELECT DISTINCT ?event ?eventLabel ?startDate ?endDate ?sportLabel ?venueLabel ?coord WHERE {
  ?event wdt:P31/wdt:P279* wd:Q16510064 .

  # Portugal: country direto, ou venue em PT, ou parte de evento em PT
  {
    { ?event wdt:P17 wd:Q45 . }
    UNION
    { ?event wdt:P276 ?venueX . ?venueX wdt:P17 wd:Q45 . }
    UNION
    { ?event wdt:P361 ?parent . ?parent wdt:P17 wd:Q45 . }
  }

  # Data: point in time OU start time
  {
    ?event wdt:P585 ?startDate .
    BIND(?startDate AS ?endDate)
  } UNION {
    ?event wdt:P580 ?startDate .
    OPTIONAL { ?event wdt:P582 ?endDate . }
  }
  FILTER(?startDate >= NOW())

  OPTIONAL { ?event wdt:P641 ?sport . }

  # Localização: tenta direto, depois via parent event
  OPTIONAL {
    {
      ?event wdt:P276 ?venue .
      ?venue wdt:P625 ?coord .
    } UNION {
      ?event wdt:P361 ?parentEv .
      ?parentEv wdt:P276 ?venue .
      ?venue wdt:P625 ?coord .
    }
  }

  SERVICE wikibase:label { bd:serviceParam wikibase:language "pt,en". }
}
ORDER BY ?startDate
LIMIT 120
"""

# Mapeamento Wikidata sport label → categoria interna
SPORT_MAPPING = {
    "futebol": "futebol", "football": "futebol",
    "atletismo": "atletismo", "athletics": "atletismo",
    "natação": "natacao", "swimming": "natacao",
    "ciclismo": "ciclismo", "cycling": "ciclismo",
    "ténis": "tenis", "tennis": "tenis",
    "basquetebol": "basquetebol", "basketball": "basquetebol",
    "judo": "judo", "judô": "judo",
    "karate": "karate", "karaté": "karate",
    "boxe": "boxe", "boxing": "boxe",
    "surf": "surf", "surfing": "surf",
    "escalada": "escalada", "climbing": "escalada",
    "jiu-jitsu": "jiu-jitsu",
    "taekwondo": "taekwondo",
    "andebol": "andebol", "handball": "andebol",
    "voleibol": "voleibol", "volleyball": "voleibol",
    "rugby": "rugby",
    "patinagem": "patinagem",
    "ginástica": "ginastica", "gymnastics": "ginastica",
}


def _parse_coords(point_str: str) -> tuple[float, float] | None:
    """Wikidata devolve 'Point(lon lat)'."""
    if not point_str or not point_str.startswith("Point("):
        return None
    try:
        inner = point_str[6:-1]
        lon, lat = inner.split(" ")
        return float(lat), float(lon)
    except (ValueError, IndexError):
        return None


def _normalize_sport(label: str | None) -> str:
    if not label:
        return "outro"
    key = label.lower().strip()
    return SPORT_MAPPING.get(key, key)


def scrape() -> list[dict]:
    """Devolve eventos desportivos futuros em Portugal a partir do Wikidata."""
    try:
        logger.info("Wikidata: a consultar SPARQL endpoint...")
        response = requests.get(
            WIKIDATA_URL,
            params={"query": SPARQL, "format": "json"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        bindings = data.get("results", {}).get("bindings", [])
        logger.info("Wikidata: %d bindings recebidos", len(bindings))
    except Exception as exc:
        logger.warning("Wikidata: query falhou — %s", exc)
        return []

    events: list[dict] = []
    seen_uris = set()

    for b in bindings:
        uri = b.get("event", {}).get("value", "")
        if uri in seen_uris:
            continue
        seen_uris.add(uri)

        title = b.get("eventLabel", {}).get("value", "").strip()
        if not title or title.startswith("Q"):  # Q123456 = sem label
            continue

        start_raw = b.get("startDate", {}).get("value", "")
        if not start_raw:
            continue
        try:
            start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        except ValueError:
            continue

        end_raw = b.get("endDate", {}).get("value", start_raw)
        try:
            end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
        except ValueError:
            end_dt = start_dt

        venue = b.get("venueLabel", {}).get("value", "").strip()
        sport_label = b.get("sportLabel", {}).get("value", "")
        coord = _parse_coords(b.get("coord", {}).get("value", ""))

        # Só aceitar eventos com localização específica — eventos sem venue
        # geocodificável poluem o mapa com pontos no centroide de PT.
        if not coord and not venue:
            continue

        events.append({
            "title":      title,
            "sport":      _normalize_sport(sport_label),
            "category":   "Evento",  # categoria genérica — Wikidata raramente tem detalhe
            "organizer":  "",
            "source":     "Wikidata",
            "source_url": uri,
            "start_date": start_dt.replace(tzinfo=None).isoformat(timespec="minutes"),
            "end_date":   end_dt.replace(tzinfo=None).isoformat(timespec="minutes"),
            "venue_name": venue or "Portugal",
            "city":       "",  # Wikidata raramente expõe cidade direta
            "address":    venue,
            "description": f"Evento desportivo registado na Wikidata. Verificável em {uri}",
            "registration_url": uri,
            "price":      "",
            "_wikidata_coords": coord,  # passamos as coords se Wikidata as tiver
        })

    logger.info("Wikidata: %d eventos válidos extraídos", len(events))
    return events
