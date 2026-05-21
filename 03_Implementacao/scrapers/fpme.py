"""
FPME (Federação Portuguesa de Montanhismo e Escalada) scraper.

A federação publica calendário de competições nacionais em formato HTML
simples na sua página oficial. Este scraper extrai os eventos futuros.

Defensivo: em caso de mudança de layout, falhas de rede ou parsing,
devolve [] e regista warning.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

# Algumas instalações conhecidas (cache curado para evitar geocoding extra)
SOURCE_URL = "https://www.fpme.pt/calendario-competicoes/"
USER_AGENT = "TABD-FitMap/1.0 (university project)"

# Regex para datas em PT: "12-13 Junho 2026", "5 de Julho de 2026", "20/06/2026"
MONTHS_PT = {
    "janeiro": 1, "jan": 1,
    "fevereiro": 2, "fev": 2,
    "março": 3, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "maio": 5, "mai": 5,
    "junho": 6, "jun": 6,
    "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9,
    "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}

DATE_PATTERNS = [
    # "12 de junho de 2026" / "12 junho 2026"
    re.compile(r"(\d{1,2})\s+(?:de\s+)?(\w+)\s+(?:de\s+)?(\d{4})", re.IGNORECASE),
    # "20/06/2026" or "20-06-2026"
    re.compile(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})"),
]


def _parse_date(text: str) -> datetime | None:
    text = text.strip().lower()
    for pat in DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        try:
            if pat is DATE_PATTERNS[0]:
                day, month_name, year = m.groups()
                month = MONTHS_PT.get(month_name.lower())
                if not month:
                    continue
                return datetime(int(year), month, int(day))
            else:
                day, month, year = m.groups()
                return datetime(int(year), int(month), int(day))
        except (ValueError, KeyError):
            continue
    return None


def scrape() -> list[dict]:
    """Extrai eventos do calendário FPME."""
    try:
        logger.info("FPME: a consultar %s", SOURCE_URL)
        response = requests.get(
            SOURCE_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
        html = response.text
    except Exception as exc:
        logger.warning("FPME: fetch falhou — %s", exc)
        return []

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("FPME: beautifulsoup4 não instalado — scraper desativado")
        return []

    soup = BeautifulSoup(html, "html.parser")

    events: list[dict] = []
    now = datetime.now()

    # Estratégia 1: procurar elementos <article> ou <div class="event*">
    candidates = soup.find_all(["article"]) + soup.select("[class*='event'], [class*='competic'], [class*='calendar']")
    for el in candidates[:80]:
        text = el.get_text(" ", strip=True)
        if len(text) < 10 or len(text) > 600:
            continue

        date_obj = _parse_date(text)
        if not date_obj or date_obj < now:
            continue

        # Título: heading dentro ou primeiras palavras
        title_el = el.find(["h1", "h2", "h3", "h4", "strong"])
        title = title_el.get_text(strip=True) if title_el else text[:80]
        if not title or len(title) < 5:
            continue

        # Link
        link_el = el.find("a", href=True)
        url = urljoin(SOURCE_URL, link_el["href"]) if link_el else SOURCE_URL

        # Categoria: bouldering, lead, velocidade…
        category = "Campeonato"
        for keyword in ["boulder", "lead", "velocidade", "open", "taça", "campeonato"]:
            if keyword in text.lower():
                category = keyword.capitalize()
                break

        events.append({
            "title":      title[:140],
            "sport":      "escalada",
            "category":   category,
            "organizer":  "Federação Portuguesa de Montanhismo e Escalada",
            "source":     "FPME",
            "source_url": url,
            "start_date": date_obj.isoformat(timespec="minutes"),
            "end_date":   date_obj.replace(hour=20).isoformat(timespec="minutes"),
            "venue_name": "A confirmar",
            "city":       "Portugal",
            "address":    "Portugal",
            "description": text[:300],
            "registration_url": url,
            "price":      "",
        })

    # Dedup por título
    seen = set()
    unique = []
    for e in events:
        key = e["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)

    logger.info("FPME: %d eventos extraídos", len(unique))
    return unique
