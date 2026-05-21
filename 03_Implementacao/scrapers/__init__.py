"""Scrapers de eventos desportivos.

Cada módulo expõe `scrape() -> list[dict]` devolvendo eventos no schema:
{
    "title": str, "sport": str, "category": str,
    "organizer": str, "source": str, "source_url": str,
    "start_date": str (ISO), "end_date": str (ISO),
    "venue_name": str, "city": str, "address": str,
    "description": str, "registration_url": str, "price": str,
}
Em caso de falha (network, parse), devem retornar [] e logar warning.
"""
