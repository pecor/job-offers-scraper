"""Geo endpoints: home location, enrichment (geocoding + distances), status."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db, SessionLocal
from app.models import JobOffer, LocationCache
from app.services import geo

from .config import load_config, save_config

logger = logging.getLogger(__name__)
router = APIRouter()


class HomeRequest(BaseModel):
    address: str


def _run_enrich(home_lat: float | None, home_lng: float | None):
    db = SessionLocal()
    try:
        geo.enrich_offers(db, home_lat, home_lng)
    finally:
        db.close()


@router.get("/geo/status")
async def geo_status(db: Session = Depends(get_db)):
    """Geo enrichment overview (also reports whether geocoding is configured)."""
    config = load_config()
    total = db.query(func.count(JobOffer.id)).scalar() or 0
    located = db.query(func.count(JobOffer.id)).filter(JobOffer.lat.isnot(None)).scalar() or 0
    with_distance = (
        db.query(func.count(JobOffer.id)).filter(JobOffer.distance_km.isnot(None)).scalar() or 0
    )
    cached_cities = db.query(func.count(LocationCache.id)).scalar() or 0
    pending = db.query(func.count(JobOffer.id)).filter(JobOffer.city_norm.is_(None)).scalar() or 0
    return {
        "api_configured": bool(settings.GOOGLE_PLACES_API_KEY),
        "home_address": config.get("home_address", ""),
        "home_set": config.get("home_lat") is not None,
        "offers_total": total,
        "offers_located": located,
        "offers_with_distance": with_distance,
        "offers_pending_enrich": pending,
        "cached_cities": cached_cities,
    }


@router.post("/geo/home")
async def set_home(request: HomeRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Geocode the user's home address once, save it, recompute all distances."""
    address = request.address.strip()
    if not address:
        raise HTTPException(status_code=400, detail="Address cannot be empty")
    if not settings.GOOGLE_PLACES_API_KEY:
        raise HTTPException(status_code=503, detail="GOOGLE_PLACES_API_KEY not configured")

    result = geo.geocode(address)
    if not result:
        raise HTTPException(status_code=422, detail=f"Could not geocode address: {address}")

    lat, lng, display = result
    config = load_config()
    config["home_address"] = display
    config["home_lat"] = lat
    config["home_lng"] = lng
    save_config(config)

    # Recompute distances in the background
    background.add_task(_run_enrich, lat, lng)
    return {"home_address": display, "home_lat": lat, "home_lng": lng}


@router.get("/geo/cities")
async def geo_cities(db: Session = Depends(get_db)):
    """Cities available for filtering (from offers, most frequent first)."""
    rows = (
        db.query(JobOffer.city_norm, func.count(JobOffer.id))
        .filter(JobOffer.city_norm.isnot(None), JobOffer.city_norm != "")
        .group_by(JobOffer.city_norm)
        .order_by(func.count(JobOffer.id).desc())
        .all()
    )
    return [{"city": city, "count": count} for city, count in rows]


@router.post("/geo/enrich")
async def enrich(background: BackgroundTasks, db: Session = Depends(get_db)):
    """Geocode offers missing coordinates (unique cities only) and update distances."""
    if not settings.GOOGLE_PLACES_API_KEY:
        raise HTTPException(status_code=503, detail="GOOGLE_PLACES_API_KEY not configured")

    pending = (
        db.query(func.count(JobOffer.id)).filter(JobOffer.city_norm.is_(None)).scalar() or 0
    )
    config = load_config()
    background.add_task(
        _run_enrich, config.get("home_lat"), config.get("home_lng")
    )
    return {"started": True, "offers_pending": pending}
