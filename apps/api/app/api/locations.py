"""Location endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Location
from app.db.session import get_db
from app.schemas import LocationInput, LocationOut

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/search", response_model=list[LocationOut])
def search_locations(q: str = "", state: str = "", district: str = "", limit: int = 20, db: Session = Depends(get_db)):
    stmt = select(Location)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Location.village.ilike(like), Location.block.ilike(like),
                              Location.district.ilike(like), Location.state.ilike(like)))
    if state:
        stmt = stmt.where(Location.state == state)
    if district:
        stmt = stmt.where(Location.district == district)
    stmt = stmt.limit(max(1, min(limit, 100)))
    return list(db.execute(stmt).scalars())


@router.post("/search-by-input", response_model=list[LocationOut])
def search_by_input(inp: LocationInput, db: Session = Depends(get_db)):
    stmt = select(Location).where(Location.state == inp.state, Location.district == inp.district)
    if inp.block:
        stmt = stmt.where(Location.block == inp.block)
    if inp.village:
        stmt = stmt.where(Location.village == inp.village)
    return list(db.execute(stmt).scalars())


@router.get("/{location_id}", response_model=LocationOut)
def get_location(location_id: str, db: Session = Depends(get_db)):
    row = db.get(Location, location_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return row
