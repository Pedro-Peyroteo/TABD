"""
Eventbrite Portugal scraper — eventos desportivos em Portugal.

Estratégia:
1. Pesquisa múltiplos keywords desportivos na Eventbrite Portugal
2. Extrai JSON-LD (ItemList) de cada página de resultados
3. Classifica cada evento pelo desporto via keyword matching no título
4. Deduplica por URL de evento
5. Devolve lista normalizada para o nosso schema
"""

from __future__ import annotations

import logging
import json
import re
import time
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# Keywords e desporto associado: (keyword_url, sport_label, category_label)
KEYWORD_SPORT_MAP: list[tuple[str, str, str]] = [
    ("corrida",   "corrida",    "Corrida"),
    ("maratona",  "corrida",    "Maratona"),
    ("trail",     "trail",      "Trail"),
    ("triatlo",   "triatlo",    "Triathlon"),
    ("natacao",   "natação",    "Natação"),
    ("ciclismo",  "ciclismo",   "Ciclismo"),
    ("padel",     "padel",      "Torneio"),
    ("judo",      "judo",       "Competição"),
    ("yoga",      "yoga",       "Aula / Workshop"),
    ("crossfit",  "crossfit",   "Competição"),
    ("escalada",  "escalada",   "Competição"),
    ("fitness",   "fitness",    "Aula / Workshop"),
    ("pilates",   "pilates",    "Aula / Workshop"),
    ("atletismo", "atletismo",  "Competição"),
    ("futebol",   "futebol",    "Torneio"),
    ("basket",    "basquetebol","Torneio"),
    ("voleibol",  "voleibol",   "Torneio"),
    ("run",       "corrida",    "Corrida"),
]

# Mapeamento de título → desporto (override quando o keyword é genérico)
TITLE_SPORT_KEYWORDS: list[tuple[list[str], str]] = [
    (["maratoninha", "maratona", "meia maratona", "half marathon"], "corrida"),
    (["corrida", "corrida a pé", "5k", "10k", "run", "running"], "corrida"),
    (["trail", "ultra trail", "ultratrail"], "trail"),
    (["triatlo", "triathlon", "ironman", "duatlo"], "triatlo"),
    (["natação", "natacao", "swimming", "swim"], "natação"),
    (["ciclismo", "bicicleta", "cycling", "granfondo", "gran fondo", "volta"], "ciclismo"),
    (["padel"], "padel"),
    (["judo", "judô"], "judo"),
    (["karate", "caratê"], "karate"),
    (["yoga", "meditação", "meditation"], "yoga"),
    (["pilates"], "pilates"),
    (["crossfit"], "crossfit"),
    (["fitness", "ginásio", "gym"], "fitness"),
    (["escalada", "climbing", "bouldering"], "escalada"),
    (["atletismo", "decatlo"], "atletismo"),
    (["jiu.jitsu", "jiujitsu", "bjj", "grappling"], "jiu-jitsu"),
    (["futebol", "football", "soccer"], "futebol"),
    (["voleibol", "volleyball"], "voleibol"),
    (["basquetebol", "basketball"], "basquetebol"),
    (["dance", "dança", "danças"], "dança"),
    (["surf", "bodyboard"], "surf"),
    (["golfe", "golf"], "golfe"),
    (["boxe", "boxing", "kickboxing", "muay thai"], "boxe"),
    (["ténis", "tennis"], "ténis"),
]

JSON_LD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.+?)</script>',
    re.DOTALL,
)

# Palavras que indicam que NÃO é um evento desportivo
NON_SPORT_TITLE_WORDS = [
    "workshop ai", "artificial intel", "unicorn pitch", "startup", "comedy",
    "stand up", "kawaii", "anime", "concert", "concerto", "festival cultural",
    "screenin", "q&a with", "book", "livro", "conferência", "meetup tech",
    "networking", "hack", "summit tech", "cooking class", "cozinhar", "pastel",
    "storytelling", "galeria", "museu", "history", "história da família",
    "mutual conjunta", "bom dia, galeria", "santos populares at stork",
    "dj set", "silent disco", "roller", "skating", "patin", "drag", "queer",
    "lgbtq", "festival de música", "music festival", "film", "cinema",
    "wine tasting", "degustação", "escape room",
]

# Palavras que CONFIRMAM que é um evento desportivo (pelo menos uma deve estar presente)
SPORT_CONFIRM_KEYWORDS = [
    # running
    "run", "running", "corrida", "maratona", "meia maratona", "5k", "10k", "km",
    "trail", "ultra", "hiking",
    # triathlon / swim
    "triatlo", "triathlon", "ironman", "duatlo", "natação", "natacao", "swim", "piscina",
    # cycling
    "ciclismo", "cycling", "bicicleta", "velocidade", "granfondo", "gran fondo", "bike",
    # martial arts
    "judo", "karate", "jiu", "bjj", "grappling", "mma", "taekwondo", "boxe", "boxing",
    "kickboxing", "muay thai", "capoeira",
    # gym / fitness
    "crossfit", "crossfit", "yoga", "pilates", "fitness", "ginásio", "gym",
    "hiit", "treino", "workout",
    # climbing
    "escalada", "climbing", "bouldering",
    # paddle / racket
    "padel", "ténis", "tennis", "squash", "badminton",
    # team sports
    "futebol", "football", "soccer", "basquetebol", "basketball", "voleibol", "volleyball",
    "andebol", "handball", "rugby",
    # dance / others
    "dance", "dança",
    # surf
    "surf", "bodyboard",
    # misc sport
    "atletismo", "athletics", "corrida a pé",
]


def _word_in(word: str, text: str) -> bool:
    """Verifica se `word` aparece como palavra completa em `text` (já em lowercase)."""
    import re as _re
    pattern = r'\b' + _re.escape(word) + r'\b'
    return bool(_re.search(pattern, text))


def _classify_sport(title: str, fallback_sport: str) -> str:
    t = title.lower()
    for keywords, sport in TITLE_SPORT_KEYWORDS:
        for kw in keywords:
            # Para keywords curtas (<= 3 chars) exigir palavra completa
            if len(kw) <= 3:
                if _word_in(kw, t):
                    return sport
            else:
                if kw in t:
                    return sport
    return fallback_sport


def _is_non_sport(title: str) -> bool:
    t = title.lower()
    return any(w in t for w in NON_SPORT_TITLE_WORDS)


def _is_sport_confirmed(title: str) -> bool:
    """Verifica que pelo menos uma keyword desportiva está no título."""
    t = title.lower()
    for kw in SPORT_CONFIRM_KEYWORDS:
        if len(kw) <= 3:
            if _word_in(kw, t):
                return True
        else:
            if kw in t:
                return True
    return False


def _fetch_events_page(session: requests.Session, url: str) -> list[dict]:
    """Extrai eventos de uma página de resultados Eventbrite."""
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Eventbrite: fetch falhou %s — %s", url, exc)
        return []

    m = JSON_LD_RE.search(r.text)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        items = data.get("itemListElement", [])
        return items
    except (json.JSONDecodeError, KeyError):
        return []


def _normalize_item(item: dict, sport: str, category: str) -> dict | None:
    """Normaliza um item do JSON-LD para o nosso schema."""
    ev = item.get("item", item)

    title = (ev.get("name") or "").strip()
    if not title or len(title) < 3:
        return None

    if _is_non_sport(title):
        return None
    if not _is_sport_confirmed(title):
        return None

    start_raw = ev.get("startDate") or ev.get("startdate") or ""
    end_raw   = ev.get("endDate")   or start_raw
    if not start_raw:
        return None

    try:
        start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        end_dt   = datetime.fromisoformat(end_raw.replace("Z",   "+00:00")).replace(tzinfo=None)
        # Ignorar eventos passados
        if start_dt < datetime(2025, 1, 1):
            return None
    except (ValueError, AttributeError):
        return None

    loc  = ev.get("location") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address") or {} if isinstance(loc, dict) else {}
    if isinstance(addr, str):
        addr = {}

    city     = (addr.get("addressLocality") or "").strip()
    street   = (addr.get("streetAddress")   or "").strip()
    postcode = (addr.get("postalCode")       or "").strip()
    country  = (addr.get("addressCountry")  or "").strip()

    # Verificar que é Portugal
    if country and country not in ("PT", "Portugal"):
        return None

    # Limpar city com vírgula
    if "," in city:
        city = city.split(",", 1)[0].strip()

    venue_name = (loc.get("name") or city or "Portugal").strip() if isinstance(loc, dict) else (city or "Portugal")
    full_address = ", ".join(filter(None, [street, postcode, city, "Portugal"]))

    real_sport = _classify_sport(title, sport)

    return {
        "title":      title[:160],
        "sport":      real_sport,
        "category":   category,
        "organizer":  "Eventbrite",
        "source":     "Eventbrite",
        "source_url": ev.get("url") or "",
        "start_date": start_dt.isoformat(timespec="minutes"),
        "end_date":   end_dt.isoformat(timespec="minutes"),
        "venue_name": venue_name[:120],
        "city":       city,
        "address":    full_address or "Portugal",
        "description": "",
        "registration_url": ev.get("url") or "",
        "price": "",
    }


def scrape() -> list[dict]:
    """Devolve eventos desportivos em Portugal da Eventbrite."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    seen_urls: set[str] = set()
    all_events: list[dict] = []

    for keyword, sport, category in KEYWORD_SPORT_MAP:
        url = f"https://www.eventbrite.pt/d/portugal/{keyword}/"
        logger.info("Eventbrite: a pesquisar keyword=%s ...", keyword)
        items = _fetch_events_page(session, url)

        for item in items:
            ev = item.get("item", item)
            ev_url = ev.get("url") or ""
            # Dedup por URL
            if ev_url and ev_url in seen_urls:
                continue
            if ev_url:
                seen_urls.add(ev_url)

            doc = _normalize_item(item, sport, category)
            if doc:
                all_events.append(doc)

        time.sleep(0.4)  # cortesia para o servidor

    # Dedup extra por (título, data) para eventos sem URL
    seen_title_date: set[tuple] = set()
    unique: list[dict] = []
    for e in all_events:
        key = (e["title"].lower(), e["start_date"][:10])
        if key in seen_title_date:
            continue
        seen_title_date.add(key)
        unique.append(e)

    logger.info(
        "Eventbrite: %d eventos únicos desportivos em Portugal (de %d candidatos)",
        len(unique), len(all_events),
    )
    return unique
