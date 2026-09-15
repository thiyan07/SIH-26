"""Market Gap Detection — saturated/moderate/underserved with feasibility."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import Business
from app.db.session import get_db
from app.engines.market_gap import analyze_gaps

router = APIRouter(prefix="/user/businesses/{business_id}/market-gap", tags=["market-gap"])


class GapRequest(BaseModel):
    radius_m: int = Field(default=1000, ge=100, le=10000)
    categories: list[str] | None = None  # if None, use all known


@router.post("")
def market_gap(business_id: str, body: GapRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Business not found")
    # For now, use request categories or default to common ones; real implementation would query
    # Business table for competitor counts in radius and MarketPrice for price/demand.
    # Here we provide a deterministic placeholder that never fabricates: if no data, verdict unknown
    from app.db.models import Business as BizModel
    from sqlalchemy import func

    # Simple: count competitors per category in radius (haversine via Python, not PostGIS for now)
    # For brevity, use existing Business rows within radius
    # In production, reuse geo.py find_nearby
    from app.geo import find_nearby

    # If categories not provided, use a default set
    cats = body.categories or ["grocery", "restaurant", "pharmacy", "textile", "bakery", "hardware"]
    density: dict[str, int | None] = {}
    for cat in cats:
        try:
            # find_nearby filters by category_code
            nearby = find_nearby(db, Business, latitude=b.latitude, longitude=b.longitude, radius_km=body.radius_m / 1000, category_code=cat)
            # find_nearby returns list of (Business, distance)
            density[cat] = len(nearby)
        except Exception:
            density[cat] = None

    # Demand indicators — placeholder: use None to show limitations, not fake
    demand: dict[str, float | None] = {cat: None for cat in cats}

    result = analyze_gaps(competitor_density=density, demand_indicators=demand, price_snapshot=None, business_category=b.category_code)

    # Persist snapshot
    from app.db.models import MarketSnapshot
    from datetime import datetime, timezone

    snap = MarketSnapshot(
        business_id=business_id,
        user_id=current_user.id,
        captured_at=datetime.now(timezone.utc),
        radius_m=body.radius_m,
        competitor_density=density,
        price_snapshot=None,
        demand_indicators=demand,
        gaps=result["gaps"],
        source="market_gap_engine_v1",
    )
    db.add(snap)
    db.commit()

    return result
