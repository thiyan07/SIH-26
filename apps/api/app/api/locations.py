"""Location endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session

from app.db.models import Location
from app.db.session import get_db
from app.geo import real_data_condition
from app.schemas import LocationInput, LocationOut

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/search", response_model=list[LocationOut])
def search_locations(q: str = "", state: str = "", district: str = "", limit: int = 20, db: Session = Depends(get_db)):
    stmt = select(Location).where(real_data_condition(Location))
    if q:
        q = q.strip()
        orig_q = q
        if len(q) == 1:
            # Single letter: prefix match for instant first-letter suggestions, much faster with index
            like = f"{q}%"
            stmt = stmt.where(or_(Location.village.ilike(like), Location.block.ilike(like)))
        else:
            like = f"%{q}%"
            stmt = stmt.where(or_(Location.village.ilike(like), Location.block.ilike(like),
                                  Location.district.ilike(like), Location.state.ilike(like)))
        # Prioritize exact village, then exact block, then prefix village/block, then alphabetical
        # Fixes "Perundurai shows for a sec then can't find": exact village was at index 15 due to alphabetical order
        exact = orig_q
        prefix = f"{orig_q}%"
        stmt = stmt.order_by(
            case(
                (Location.village.ilike(exact), 0),
                (Location.block.ilike(exact), 1),
                (Location.village.ilike(prefix), 2),
                (Location.block.ilike(prefix), 3),
                else_=4,
            ),
            Location.village,
        )
    if state:
        stmt = stmt.where(Location.state.ilike(state))
    if district:
        # Alias-aware district filter (Thoothukudi ↔ Tuticorin)
        _aliases = {"Thoothukudi": ["Thoothukudi","Tuticorin"], "Tuticorin": ["Thoothukudi","Tuticorin"], "Villupuram": ["Villupuram","Viluppuram"], "Viluppuram": ["Villupuram","Viluppuram"]}
        variants = _aliases.get(district, [district])
        if len(variants) > 1:
            from sqlalchemy import or_ as _or2
            stmt = stmt.where(_or2(*[Location.district.ilike(v) for v in variants]))
        else:
            stmt = stmt.where(Location.district.ilike(district))
    stmt = stmt.limit(max(1, min(limit, 50)))
    return list(db.execute(stmt).scalars())


@router.post("/search-by-input", response_model=list[LocationOut])
def search_by_input(inp: LocationInput, db: Session = Depends(get_db)):
    # Alias-aware for Thoothukudi/Tuticorin
    _aliases2 = {"Thoothukudi": ["Thoothukudi","Tuticorin"], "Tuticorin": ["Thoothukudi","Tuticorin"], "Villupuram": ["Villupuram","Viluppuram"], "Viluppuram": ["Villupuram","Viluppuram"]}
    dvars = _aliases2.get(inp.district, [inp.district])
    stmt = select(Location).where(Location.state.ilike(inp.state), real_data_condition(Location))
    if len(dvars) > 1:
        stmt = stmt.where(or_(*[Location.district.ilike(v) for v in dvars]))
    else:
        stmt = stmt.where(Location.district.ilike(inp.district))
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
