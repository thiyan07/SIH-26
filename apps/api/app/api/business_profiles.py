"""BusinessProfile — Post-Loan per-type data (agriculture/textile/restaurant)."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import Business, BusinessProfile
from app.db.session import get_db

router = APIRouter(prefix="/user/business-profiles", tags=["business-profiles"])


def _polygon_area_sqm(coords: list[list[float]]) -> float | None:
    """Shoelace formula for GeoJSON Polygon outer ring [[lng,lat],...]. Returns sqm approx."""
    if not coords or len(coords) < 3:
        return None
    # Convert to meters via haversine-ish: use equirectangular approx for small polygons
    # For Erode ~11°N, 1 deg lat ~111km, 1 deg lon ~109km
    try:
        lats = [c[1] for c in coords]
        lngs = [c[0] for c in coords]
        avg_lat = sum(lats) / len(lats)
        m_per_deg_lat = 111000
        m_per_deg_lng = 111000 * math.cos(math.radians(avg_lat))
        # Project to meters
        xs = [lng * m_per_deg_lng for lng in lngs]
        ys = [lat * m_per_deg_lat for lat in lats]
        area = 0.0
        for i in range(len(xs)):
            j = (i + 1) % len(xs)
            area += xs[i] * ys[j] - xs[j] * ys[i]
        return abs(area) / 2.0
    except Exception:
        return None


class CreateProfileRequest(BaseModel):
    business_id: str
    business_type: str = Field(pattern="^(agriculture|textile|restaurant|other)$")
    land_size: float | None = None
    land_unit: str | None = Field(default="acres", pattern="^(acres|hectares|sqm|guntas)$")
    land_polygon: list[list[float]] | None = None  # [[lng,lat],...] 4 points
    declared_area: float | None = None
    water_source: str | None = None
    water_latitude: float | None = Field(default=None, ge=-90, le=90)
    water_longitude: float | None = Field(default=None, ge=-180, le=180)
    crop: str | None = None
    season: str | None = Field(default=None, pattern="^(kharif|rabi|zaid)?$")
    profile_data: dict | None = None  # textile/restaurant flex


class ProfileResponse(BaseModel):
    id: str
    business_id: str
    business_type: str
    land_size: float | None
    calculated_area: float | None
    declared_area: float | None
    area_discrepancy_pct: float | None
    water_source: str | None
    crop: str | None
    profile_data: dict | None

    class Config:
        from_attributes = True


def _to_resp(p: BusinessProfile) -> dict:
    disc = None
    if p.calculated_area and p.declared_area and p.declared_area != 0:
        # Convert declared to sqm for comparison
        unit = (p.land_unit or "acres").lower()
        factor = {"acres": 4046.86, "hectares": 10000, "sqm": 1, "guntas": 101.17}.get(unit, 4046.86)
        declared_sqm = p.declared_area * factor
        disc = round(abs(p.calculated_area - declared_sqm) / declared_sqm * 100, 1) if declared_sqm else None
    return {
        "id": p.id,
        "business_id": p.business_id,
        "business_type": p.business_type,
        "land_size": p.land_size,
        "calculated_area": p.calculated_area,
        "declared_area": p.declared_area,
        "area_discrepancy_pct": disc,
        "water_source": p.water_source,
        "crop": p.crop,
        "profile_data": p.profile_data,
    }


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(body: CreateProfileRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, body.business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    # One profile per business
    existing = db.query(BusinessProfile).filter(BusinessProfile.business_id == body.business_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Profile already exists for this business")

    calc_area = None
    if body.land_polygon:
        # Expect outer ring
        calc_area = _polygon_area_sqm(body.land_polygon)

    profile = BusinessProfile(
        business_id=body.business_id,
        business_type=body.business_type,
        land_size=body.land_size,
        land_unit=body.land_unit or "acres",
        land_polygon=body.land_polygon,
        calculated_area=calc_area,
        declared_area=body.declared_area,
        water_source=body.water_source,
        water_latitude=body.water_latitude,
        water_longitude=body.water_longitude,
        crop=body.crop,
        season=body.season,
        profile_data=body.profile_data,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_resp(profile)


@router.get("/{business_id}", response_model=ProfileResponse)
def get_profile(business_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(BusinessProfile).filter(BusinessProfile.business_id == business_id).first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return _to_resp(p)


@router.put("/{business_id}", response_model=ProfileResponse)
def update_profile(business_id: str, body: CreateProfileRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(BusinessProfile).filter(BusinessProfile.business_id == business_id).first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    # Update fields
    for field in ["business_type", "land_size", "land_unit", "declared_area", "water_source", "water_latitude", "water_longitude", "crop", "season", "profile_data"]:
        if getattr(body, field) is not None:
            setattr(p, field, getattr(body, field))
    if body.land_polygon is not None:
        p.land_polygon = body.land_polygon
        p.calculated_area = _polygon_area_sqm(body.land_polygon)
    db.commit()
    db.refresh(p)
    return _to_resp(p)
