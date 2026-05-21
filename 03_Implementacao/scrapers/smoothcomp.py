"""
Smoothcomp scraper — torneios de BJJ / grappling em Portugal.

Smoothcomp é a plataforma de inscrição usada em quase todos os torneios
de BJJ na Europa, incluindo eventos regionais e de academias mais pequenas
(níveis abaixo do radar das federações nacionais).

Estratégia:
1. Listagem global em /en/events expõe JSON-LD com URLs de todos os eventos
2. Para cada URL fetch da página de detalhe → JSON-LD SportsEvent com address
3. Filtrar `addressCountry == "Portugal"`
4. Normalizar para o nosso schema

Performance: ThreadPoolExecutor (8 workers) → ~30s para 500 eventos.
Defensivo: catch + log em todos os passos.
"""

from __future__ import annotations

import logging
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

LIST_URL  = "https://www.smoothcomp.com/en/events?country=pt"
USER_AGENT = "Mozilla/5.0 (compatible; TABD-FitMap/1.0; university research)"

# Limite de eventos a inspecionar (compromisso entre tempo e cobertura).
# 1700 cobre praticamente todo o universo Smoothcomp futuro globalmente.
MAX_EVENTS_TO_FETCH = 1700
WORKERS = 15

# Regex para extrair JSON-LD de uma página
JSON_LD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.+?)</script>',
    re.DOTALL,
)


def _fetch_url_list(session: requests.Session) -> list[str]:
    """Vai à página de listagem e extrai a lista de URLs de eventos via JSON-LD."""
    try:
        r = session.get(LIST_URL, timeout=20)
        r.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Smoothcomp: listing fetch falhou — %s", exc)
        return []

    m = JSON_LD_RE.search(r.text)
    if not m:
        logger.warning("Smoothcomp: JSON-LD não encontrado na listagem")
        return []

    try:
        data = json.loads(m.group(1))
        items = data.get("itemListElement", [])
        urls = [it["url"] for it in items if "url" in it]
        logger.info("Smoothcomp: %d URLs na listagem global", len(urls))
        return urls[:MAX_EVENTS_TO_FETCH]
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Smoothcomp: parse JSON-LD falhou — %s", exc)
        return []


def _fetch_event_detail(session: requests.Session, url: str) -> dict | None:
    """Extrai o JSON-LD SportsEvent de uma página de detalhe."""
    try:
        r = session.get(url, timeout=10)
        if r.status_code != 200:
            return None
    except requests.RequestException:
        return None

    m = JSON_LD_RE.search(r.text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        if isinstance(data, list):
            data = next((d for d in data if d.get("@type") == "SportsEvent"), None)
        if data and data.get("@type") == "SportsEvent":
            return data
    except json.JSONDecodeError:
        return None
    return None


def _is_portugal(ev_data: dict) -> bool:
    addr = (ev_data.get("location", {}) or {}).get("address", {}) or {}
    country = addr.get("addressCountry", "")
    return country in ("Portugal", "PT")


def _normalize(ev_data: dict) -> dict | None:
    """Converte SportsEvent Schema.org para o nosso schema interno."""
    try:
        title = ev_data.get("name", "").strip()
        if not title:
            return None

        start = ev_data.get("startDate", "")
        end   = ev_data.get("endDate",  start)
        if not start:
            return None
        # Normalizar a datetime sem timezone para o parser do seed
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt   = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else start_dt

        loc  = ev_data.get("location", {}) or {}
        addr = loc.get("address", {}) or {}
        city = addr.get("addressLocality") or ""
        # Cidade pode vir como "Setúbal" ou "Cidade da Maia, Porto" — separar
        if "," in city:
            city = city.split(",", 1)[0].strip()

        street  = addr.get("streetAddress") or ""
        postcode = addr.get("postalCode") or ""
        venue_name = loc.get("name") or city or "Portugal"
        full_address = ", ".join(filter(None, [street, postcode, city, "Portugal"]))

        organizer = (ev_data.get("organizer", {}) or {}).get("name", "Smoothcomp")
        description = (ev_data.get("description") or "").strip()
        if len(description) > 500:
            description = description[:500] + "..."

        return {
            "title":      title[:160],
            "sport":      "jiu-jitsu",
            "category":   "Torneio",
            "organizer":  organizer,
            "source":     "Smoothcomp",
            "source_url": ev_data.get("url", ""),
            "start_date": start_dt.replace(tzinfo=None).isoformat(timespec="minutes"),
            "end_date":   end_dt.replace(tzinfo=None).isoformat(timespec="minutes"),
            "venue_name": venue_name,
            "city":       city,
            "address":    full_address or "Portugal",
            "description": description,
            "registration_url": ev_data.get("url", ""),
            "price":      "",
        }
    except (ValueError, KeyError, TypeError) as exc:
        logger.debug("Smoothcomp: skip evento — %s", exc)
        return None


def scrape() -> list[dict]:
    """Devolve eventos BJJ futuros em Portugal a partir do Smoothcomp."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    urls = _fetch_url_list(session)
    if not urls:
        return []

    logger.info("Smoothcomp: a inspecionar %d eventos em paralelo (workers=%d)...",
                len(urls), WORKERS)

    pt_events: list[dict] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(_fetch_event_detail, session, u): u for u in urls}
        for future in as_completed(futures):
            ev = future.result()
            if not ev or not _is_portugal(ev):
                continue
            doc = _normalize(ev)
            if doc:
                pt_events.append(doc)

    # Dedup por título + data
    seen = set()
    unique = []
    for e in pt_events:
        key = (e["title"].lower(), e["start_date"][:10])
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)

    logger.info("Smoothcomp: %d eventos em Portugal extraídos (de %d candidatos)",
                len(unique), len(urls))
    return unique
