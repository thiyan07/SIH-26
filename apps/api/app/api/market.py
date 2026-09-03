"""Market analysis endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InfrastructurePoint, MarketPrice
from app.db.session import get_db
from app.engines.market_intelligence import category_market_intelligence
from app.geo import find_nearby_with_distance
from app.schemas import MarketIntelligenceQuery, MarketSummaryQuery

router = APIRouter(prefix="/market", tags=["market"])


@router.post("/intelligence")
def market_intelligence(q: MarketIntelligenceQuery, db: Session = Depends(get_db)):
    """Category-aware market intelligence (SIH26092).

    Filters stored, real MarketPrice rows to the category's relevant
    commodities in the district within the freshness window, returns
    relevance/freshness/confidence scoring + a source hierarchy, and (when
    coordinates are given) category-scoped demand signals + accessibility.
    Never invents prices.
    """
    return category_market_intelligence(
        db,
        category_code=q.category_code,
        state=q.state,
        district=q.district,
        latitude=q.latitude,
        longitude=q.longitude,
        radius_km=q.radius_km,
        max_age_days=q.max_age_days,
    )


@router.post("/summary")
def market_summary(q: MarketSummaryQuery, db: Session = Depends(get_db)):
    markets = find_nearby_with_distance(db, InfrastructurePoint, q.latitude, q.longitude, 20.0,
                                        {"kind": "market"}, 100)
    all_businesses = find_nearby_with_distance(db, __import__("app.db.models", fromlist=["Business"]).Business,
                                               q.latitude, q.longitude, q.radius_km, None, 500)
    market_dists = [d for _, d in markets]
    return {
        "nearest_market_km": round(min(market_dists), 2) if market_dists else None,
        "markets_within_20km": len(markets),
        "mapped_businesses_within_radius": len(all_businesses),
        "radius_km": q.radius_km,
        "note": "Values based on mapped data; may be incomplete.",
    }


@router.get("/prices")
def market_prices(db: Session = Depends(get_db)):
    rows = list(db.execute(select(MarketPrice).limit(100)).scalars())
    return {
        "count": len(rows),
        "note": "Only sourced prices are shown; none are invented.",
        "prices": [
            {"item": r.item_name, "category": r.category, "unit": r.unit,
             "min": float(r.min_price) if r.min_price else None,
             "max": float(r.max_price) if r.max_price else None,
             "modal": float(r.modal_price) if r.modal_price else None,
             "market": r.market_name, "district": r.district,
             "reference": r.reference_date.isoformat() if r.reference_date else None,
             "source": r.source_name}
            for r in rows
        ],
    }
