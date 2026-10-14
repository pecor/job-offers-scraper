"""Geolocation service: city extraction, geocoding (Google Places API) with DB cache,
and distance computation (haversine) between the user's home and offers.

API usage is minimized by design:
- every unique normalized city is geocoded exactly once and cached in `location_cache`
- the user's home address is geocoded once (stored in config)
- distances are computed locally (haversine), no API involved
"""

import logging
import math
import re
import time
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import JobOffer, LocationCache

logger = logging.getLogger(__name__)

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Polish voivodeship names that portals append to city names (e.g. "Jawczyce...mazowieckie")
_VOIVODESHIPS = {
    "dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie", "łódzkie",
    "małopolskie", "mazowieckie", "opolskie", "podkarpackie", "podlaskie",
    "pomorskie", "śląskie", "świętokrzyskie", "warmińsko-mazurskie",
    "wielkopolskie", "zachodniopomorskie",
    # English region names used by justjoin.it ("WarszawaMasovian")
    "masovian", "silesian", "lesser poland", "pomeranian", "lower silesian",
    "greater poland", "kuyavian-pomeranian", "subcarpathian", "swietokrzyskie",
    "warmian-masurian", "west pomeranian", "lubusz", "podlaskie", "opole",
}

_REMOTE_MARKERS = ("zdalna", "remote", "zdalnie", "praca zdalna")


# English city names returned by justjoin.it mapped to Polish equivalents
# (dedup: "warsaw" and "warszawa" share one cache entry)
_CITY_EN_TO_PL = {
    "warsaw": "warszawa", "krakow": "kraków", "gdansk": "gdańsk", "gdynia": "gdynia",
    "lodz": "łódź", "poznan": "poznań", "wroclaw": "wrocław", "bialystok": "białystok",
    "rzeszow": "rzeszów", "torun": "toruń", "zielona gora": "zielona góra",
    "suwalki": "suwałki", "pulawy": "puławy", "bytom": "bytom", "czestochowa": "częstochowa",
    "katowice": "katowice", "gliwice": "gliwice", "zabrze": "zabrze", "sosnowiec": "sosnowiec",
}


def _strip_voivodeship(candidate: str) -> str:
    """Remove a trailing voivodeship name, unicode-normalization safe."""
    import unicodedata

    def fold(s: str) -> str:
        return unicodedata.normalize("NFKD", s)

    # Longest first: "dolnośląskie" must win over its substring "śląskie"
    for voiv in sorted(_VOIVODESHIPS, key=len, reverse=True):
        if fold(candidate).endswith(fold(voiv)):
            return candidate[: -len(voiv)].strip()
    return candidate


def extract_city(raw_location: str | None) -> str | None:
    """Extract a normalized city name from a raw offer location string.

    Handles formats from all scrapers:
      "al. Wojciecha Korfantego 193, Katowice" -> "katowice"
      "Jawczyce (pow. warszawski zachodni)mazowieckie" -> "jawczyce"
      "Centrum, Warsaw" -> "warszawa"
      "Warszawa" -> "warszawa"
      "Zdalna" -> None (remote offers have no meaningful city)
    """
    if not raw_location:
        return None

    text = raw_location.strip().lower()
    if not text or any(marker in text for marker in _REMOTE_MARKERS):
        return None

    # Take the part before any parenthesis: "Jawczyce (pow. ...)mazowieckie" -> "jawczyce "
    text = text.split("(")[0]
    # Comma-separated: city is usually the last segment ("street, city")
    segments = [s.strip() for s in text.split(",") if s.strip()]
    if not segments:
        return None
    candidate = segments[-1]

    candidate = _strip_voivodeship(candidate)

    # Drop postal codes / digits
    candidate = re.sub(r"\d{2}-\d{3}", "", candidate).strip(" ,.-")
    if not candidate:
        return None

    return _CITY_EN_TO_PL.get(candidate, candidate)


def geocode(query: str) -> Optional[tuple[float, float, str]]:
    """Geocode an address via Google Places API (New) Text Search.

    Returns (lat, lng, display_name) or None when nothing found / not configured.
    """
    if not settings.GOOGLE_PLACES_API_KEY:
        logger.warning("Geocoding skipped: GOOGLE_PLACES_API_KEY not set")
        return None

    try:
        response = requests.post(
            PLACES_TEXT_SEARCH_URL,
            headers={
                "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
                "X-Goog-FieldMask": "places.displayName,places.location",
                "Content-Type": "application/json",
            },
            json={
                "textQuery": query,
                # Bias towards Poland: offers come from Polish portals
                "locationBias": {
                    "rectangle": {
                        "low": {"latitude": 48.9, "longitude": 13.8},
                        "high": {"latitude": 55.0, "longitude": 24.2},
                    }
                },
                "maxResultCount": 1,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        places = data.get("places") or []
        if not places:
            return None
        place = places[0]
        location = place.get("location") or {}
        lat, lng = location.get("latitude"), location.get("longitude")
        if lat is None or lng is None:
            return None
        display = (place.get("displayName") or {}).get("text", query)
        return float(lat), float(lng), display
    except Exception as e:
        logger.error(f"Geocoding failed for '{query}': {e}")
        return None


def get_city_coords(db: Session, city_norm: str, city_display: str | None = None) -> LocationCache | None:
    """Return cached city coordinates, geocoding and caching on first miss."""
    cached = db.query(LocationCache).filter(LocationCache.city_norm == city_norm).first()
    if cached:
        return cached

    result = geocode(city_display or city_norm)
    if not result:
        # Cache misses too (as a tombstone) so we don't retry bad cities every enrich run.
        # Distinguished by lat=lng=0 which haversine will never produce for real places.
        cached = LocationCache(city_norm=city_norm, city_display=city_display, lat=0.0, lng=0.0)
    else:
        lat, lng, display = result
        cached = LocationCache(city_norm=city_norm, city_display=display, lat=lat, lng=lng)
    db.add(cached)
    db.commit()
    return cached


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometers."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def enrich_offers(db: Session, home_lat: Optional[float], home_lng: Optional[float]) -> dict:
    """Fill city_norm/lat/lng for offers missing them (API only for unseen cities),
    then recompute distance_km against home for all located offers.
    """
    geocoded_new = 0
    api_calls = 0

    offers = db.query(JobOffer).filter(JobOffer.city_norm.is_(None)).all()
    for offer in offers:
        city_norm = extract_city(offer.location)
        offer.city_norm = city_norm or ""  # "" = processed but no city (remote etc.)
        if not city_norm:
            continue

        existing = db.query(LocationCache).filter(LocationCache.city_norm == city_norm).first()
        if existing is None:
            api_calls += 1
        cached = get_city_coords(db, city_norm)
        if cached and cached.lat != 0.0 and cached.lng != 0.0:
            offer.lat = cached.lat
            offer.lng = cached.lng
            geocoded_new += 1
    db.commit()

    updated_distances = 0
    if home_lat is not None and home_lng is not None:
        for offer in db.query(JobOffer).filter(JobOffer.lat.isnot(None)).all():
            if offer.lat == 0.0 and offer.lng == 0.0:
                offer.distance_km = None
                continue
            offer.distance_km = round(
                haversine_km(home_lat, home_lng, offer.lat, offer.lng), 1
            )
            updated_distances += 1
        db.commit()

    stats = {
        "processed": len(offers),
        "geocoded": geocoded_new,
        "api_calls": api_calls,
        "distances_updated": updated_distances,
    }
    logger.info(f"Geo enrich done: {stats}")
    return stats
