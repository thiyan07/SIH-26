"""Tests for scrape_competitors.ingest_google_maps + analysis source breakdown.

Covers DB-aware dry-run stats, cross-source provenance-preserving merge
(Google Maps confirms an existing canonical OSM row -> "both"), idempotent
re-runs, and the non-inflation guarantee in ``_business_competition``.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import Business
from app.db.session import session_scope
from scripts.scrape_competitors.ingest_google_maps import (
    SOURCE,
    _dedup_by_source_id,
    _plan,
    ingest_one,
)


def _gm_row(name="Store A", lat=11.5050, lon=77.2400, src_id="GM_1", rating=4.5, **kw):
    row = {
        "name": name,
        "latitude": lat,
        "longitude": lon,
        "source_record_id": src_id,
        "google_id": src_id,
        "rating": rating,
        "review_count": 120,
        "google_category": "Kirana store",
        "place_url": f"https://maps.google.com/?cid={src_id}",
        "category_code": "grocery",
        "queried_at": "2026-08-01T10:00:00Z",
    }
    row.update(kw)
    return row


def _gm_rows_in_db(session):
    return session.execute(
        select(Business).where(Business.source == SOURCE)
    ).scalars().all()


# ---------- plan-level (unit) ----------

def test_plan_merges_matching_osm_row_as_both_would_merge(session):
    # Canonical OSM business already present (same name + ~100 m).
    with session_scope() as s:
        s.add(Business(
            id="osm_canon", name="Store A", normalized_name="store a",
            category_code="grocery", latitude=11.5050, longitude=77.2400,
            source="osm", source_id="osm1", source_name="OpenStreetMap",
            source_type="osm", is_demo=False,
        ))
        s.commit()
        plan = _plan(s, _gm_row(), "GM_1", "Store A", 11.5050, 77.2400,
                     "store a", "grocery", {"rating": 4.5})
    assert plan["action"] == "merged"
    assert plan["merged_into"] == "osm_canon"
    assert plan["patch"]["changed"] is True
    assert plan["patch"]["provenance"]["tags"]["sources"] == ["google_maps", "osm"]


def test_plan_inserts_when_no_matching_canonical_row(session):
    with session_scope() as s:
        plan = _plan(s, _gm_row(), "GM_9", "Brand New", 11.5000, 77.2400,
                     "brand new", "grocery", {"rating": 4.0})
    assert plan["action"] == "insert"


# ---------- dry-run is DB-aware and read-only ----------

def test_dry_run_reports_would_merge_and_writes_nothing(session):
    with session_scope() as s:
        s.add(Business(
            id="osm_dry", name="Dry Store", normalized_name="dry store",
            category_code="grocery", latitude=11.5060, longitude=77.2410,
            source="osm", source_id="osm2", source_name="OpenStreetMap",
            source_type="osm", is_demo=False, tags={"source": "osm"},
        ))
        s.commit()

    res = ingest_one(_gm_row(name="Dry Store", src_id="GM_DRY", lat=11.5060, lon=77.2410),
                     dry_run=True)
    assert res["action"] == "would_merge"
    assert res["changed"] is True

    # Nothing persisted by the dry-run: no google_maps row, canonical untouched.
    with session_scope() as s:
        assert _gm_rows_in_db(s) == []
        canon = s.get(Business, "osm_dry")
        assert (canon.tags or {}).get("sources") is None
        assert (canon.metadata_json or {}).get("google_maps") is None


# ---------- provenance-preserving merge (the "both" contract) ----------

def test_merge_records_google_maps_as_confirming_source(session):
    with session_scope() as s:
        s.add(Business(
            id="osm_merge", name="Corner Store", normalized_name="corner store",
            category_code="grocery", latitude=11.5050, longitude=77.2400,
            source="osm", source_id="osm3", source_name="OpenStreetMap",
            source_type="osm", is_demo=False, tags={"source": "osm"},
        ))
        s.commit()

    res = ingest_one(_gm_row(name="Corner Store", src_id="GM_MERGE"), dry_run=False)
    assert res["action"] == "merged"
    assert res["merged_into"] == "osm_merge"

    with session_scope() as s:
        # No duplicate google_maps row inserted -> competitor count not inflated.
        assert _gm_rows_in_db(s) == []
        canon = s.get(Business, "osm_merge")
        assert canonical_sources(canon) == ["google_maps", "osm"]
        gm = canon.metadata_json["google_maps"]
        assert gm["google_id"] == "GM_MERGE"
        assert gm["rating"] == 4.5
        assert gm["place_url"].startswith("https://maps.google.com")
        assert canon.is_demo is False


def _good_sources(b):
    tags = b.tags or {}
    return tags.get("sources") or (tags.get("source") and [tags["source"]]) or []


def canonical_sources(b):
    return sorted(_good_sources(b))


def test_merge_onto_existing_gm_row_is_idempotent_update(session):
    with session_scope() as s:
        s.add(Business(
            id="gm_exist", name="Solo Gm Store", normalized_name="solo gm store",
            category_code="grocery", latitude=11.5070, longitude=77.2420,
            source=SOURCE, source_id="GM_IDEM", source_name="Google Maps",
            source_type="vendor", is_demo=False, tags={"source": SOURCE, "sources": [SOURCE]},
        ))
        s.commit()

    res1 = ingest_one(_gm_row(name="Solo Gm Store", src_id="GM_IDEM"), dry_run=False)
    assert res1["action"] in ("updated", "noop")

    with session_scope() as s:
        assert len(_gm_rows_in_db(s)) == 1  # still one row, not duplicated
        assert s.get(Business, "gm_exist").tags["sources"] == ["google_maps"]


# ---------- insertion path when no match ----------

def test_insert_adds_google_maps_row_with_provenance(session):
    res = ingest_one(_gm_row(name="New Solo Shop", src_id="GM_NEW"), dry_run=False)
    assert res["action"] == "inserted"

    with session_scope() as s:
        rows = _gm_rows_in_db(s)
        assert len(rows) == 1
        b = rows[0]
        assert b.source_name == "Google Maps"
        assert b.source_id == "GM_NEW"
        assert b.is_demo is False
        assert b.tags["sources"] == ["google_maps"]
        assert b.metadata_json["google_maps"]["rating"] == 4.5


def test_missing_coords_skips(session):
    res = ingest_one(_gm_row(latitude=None), dry_run=False)
    assert res["action"] == "skip"


def test_dedup_by_source_id_keeps_best_record():
    """A place scraped N times collapses to one row; the record with the most
    reviews is kept even across varying ratings. (Coord/name filtering happens
    earlier, in _load_rows, not in the dedup pass.)"""
    rows = [
        {**_gm_row("Place", src_id="D_1", rating=3.0, review_count=5)},
        {**_gm_row("Place", src_id="D_1", rating=4.9, review_count=300)},
        {**_gm_row("Place", src_id="D_2", rating=4.2, review_count=40)},
    ]
    dedup = _dedup_by_source_id(rows)
    by_id = {r["source_record_id"]: r for r in dedup}
    assert len(dedup) == 2  # D_1 collapsed to its single best record
    assert by_id["D_1"]["review_count"] == 300  # best record wins the id
    assert by_id["D_2"]["review_count"] == 40


def test_batched_mode_single_session_updates_duplicate_src_id(session):
    """Batched mode: multiple records share one session; a repeated src_id in
    the same transaction must update the earlier insert, not violate the
    (source, source_id) unique constraint."""
    rows = [_gm_row(name="Batch Store", src_id="GM_BATCH", rating=4.0),
            _gm_row(name="Batch Store", src_id="GM_BATCH", rating=4.8)]
    actions = []
    with session_scope() as s:
        for row in rows:
            actions.append(ingest_one(row, dry_run=False, db=s)["action"])
    assert actions[0] == "inserted"
    assert actions[1] in ("updated", "noop")
    with session_scope() as s:
        gm = _gm_rows_in_db(s)
        assert len(gm) == 1  # never duplicated
        assert gm[0].metadata_json["google_maps"]["rating"] == 4.8


# ---------- analysis source breakdown / non-inflation ----------

def test_competition_source_breakdown_buckets(seeded):
    # Verify source breakdown + non-inflation via the live analysis endpoint.
    from fastapi.testclient import TestClient

    from app.main import app
    client = TestClient(app)

    with session_scope() as s:
        # existing grocery competitor (OSM only), and the SAME store confirmed
        # by Google Maps via a merge -> canonical single row tagged "both".
        s.add(Business(
            id="gm_comp", name="Competitor A", normalized_name="competitor a",
            category_code="grocery", latitude=11.5000, longitude=77.2380,
            source="osm", source_id="comp_osm", source_name="OpenStreetMap",
            source_type="osm", is_demo=False,
            tags={"source": "osm", "sources": ["google_maps", "osm"]},
            metadata_json={"google_maps": {"google_id": "GM_C", "rating": 4.0}},
        ))
        # second competitor, Google Maps only (no OSM twin)
        s.add(Business(
            id="gm_comp2", name="Competitor B", normalized_name="competitor b",
            category_code="grocery", latitude=11.5010, longitude=77.2385,
            source=SOURCE, source_id="GM_B", source_name="Google Maps",
            source_type="vendor", is_demo=False,
            tags={"source": SOURCE, "sources": ["google_maps"]},
            metadata_json={"google_maps": {"google_id": "GM_B", "rating": 3.9}},
        ))
        s.commit()

    r = client.post("/analysis", json={
        "state": "Tamil Nadu", "district": "Erode",
        "block": "Sathyamangalam", "village": "Sathyamangalam",
        "capital_available": 50000, "category_code": "grocery", "language": "en",
    })
    assert r.status_code == 200, r.text
    bc = r.json()["business_competition"]
    # seeded fixture adds one OSM grocery (Grocery C); we add GM-merged A and
    # GM-only B -> three distinct physical stores, no double-count of A.
    assert bc["mapped_competitors_10km"] == 3
    assert bc["sources"]["both"] == 1
    assert bc["sources"]["google_maps_only"] == 1
    assert bc["sources"]["other"] == 1
    assert "Google Maps" in bc["source_counts"]
