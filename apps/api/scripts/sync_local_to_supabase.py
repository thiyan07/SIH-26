"""Sync real data from local .pgdata:5433 to Supabase.

Replaces fake VillageInfo locations with exact OSM/Bharat Atlas points,
and backfills missing tables (udyam 95k, agriculture 1.2k, weather 21k, etc).

Usage:
  .venv/bin/python scripts/sync_local_to_supabase.py --dry-run
  .venv/bin/python scripts/sync_local_to_supabase.py
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text

LOCAL_URL = "postgresql+psycopg://grambiz:grambiz@127.0.0.1:5433/grambiz"
REMOTE_URL = os.environ.get("SUPABASE_URL") or "postgresql+psycopg://postgres.huafttrveorxyjajxyyo:ma_thi_yan_bot@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"

# Tables to sync – order matters for FKs (parents first)
TABLES = [
    "locations",
    "business_categories",
    "government_schemes",
    "data_sources",
    "udyam_units",
    "infrastructure_points",
    "businesses",
    "market_prices",
    "market_names",
    "weather_statistics",
    "population_statistics",
    "agriculture_statistics",
    "indicator_statistics",
    "soil_health_statistics",
    "industrial_units",
    "administrative_boundaries",
    "data_source_quality",
    "data_sync_runs",
    "competitor_cache",
]

FAKE_LOCATION_SOURCES = [
    "VillageInfo.in (district village directory)",
    "Block centroid fallback (Census village)",
    "Google Maps scraper (crowd-sourced listings)",
]

def sync_table(local, remote, table, dry_run=False):
    # get column list from local
    cols = [r[0] for r in local.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}' ORDER BY ordinal_position")).fetchall()]
    if not cols:
        print(f"  {table}: no such table locally, skip")
        return 0, 0
    col_list = ", ".join(f'"{c}"' for c in cols)
    # count
    lc = local.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    rc = remote.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    print(f"  {table}: local={lc} remote={rc}")
    if lc == 0:
        return lc, rc
    if dry_run:
        return lc, rc
    # For locations: delete fake rows first, then also clear any admin duplicates
    if table == "locations":
        placeholders = ",".join(f"'{s}'" for s in FAKE_LOCATION_SOURCES)
        deleted = remote.execute(text(f"DELETE FROM locations WHERE source_name IN ({placeholders})")).rowcount
        print(f"    deleted {deleted} fake locations from remote")
        remote.commit()
        # Also delete any remaining remote rows whose admin key collides with local (to avoid UniqueConstraint)
        # Fetch local admin keys
        local_keys = list(local.execute(text("SELECT state, district, block, village FROM locations")).fetchall())
        # Delete colliding remote rows
        colliding = 0
        for st, di, bl, vi in local_keys:
            # NULL handling: use IS NOT DISTINCT FROM semantics via COALESCE
            res = remote.execute(text(
                "DELETE FROM locations WHERE state=:st AND district=:di AND COALESCE(block,'')=COALESCE(:bl,'') AND COALESCE(village,'')=COALESCE(:vi,'')"
            ), {"st": st, "di": di, "bl": bl, "vi": vi})
            colliding += res.rowcount
        if colliding:
            print(f"    deleted {colliding} colliding admin-key rows")
            remote.commit()
        rc2 = remote.execute(text(f"SELECT count(*) FROM {table}")).scalar()
        print(f"    after delete remote={rc2}")
    # For incremental sync: truncate or upsert?
    # Simplest: DELETE remote where id in local (avoid dup) then INSERT all local rows
    # For large tables, batch INSERT
    rows = list(local.execute(text(f"SELECT {col_list} FROM {table}")).fetchall())
    if not rows:
        return lc, rc
    # For non-locations, delete overlapping ids to avoid PK conflict
    local_ids = [r[0] for r in rows if r[0]]  # first col is id
    if local_ids:
        # chunk deletes
        for i in range(0, len(local_ids), 5000):
            chunk = local_ids[i:i+5000]
            placeholders = ",".join(f"'{x}'" for x in chunk)
            remote.execute(text(f'DELETE FROM "{table}" WHERE id IN ({placeholders})'))
        remote.commit()
    # batch inserts
    insert_cols = ", ".join(f'"{c}"' for c in cols)
    # build params
    for i in range(0, len(rows), 1000):
        batch = rows[i:i+1000]
        # Use executemany via text with VALUES
        # SQLAlchemy 2: use insert via executemany
        for row in batch:
            vals = ", ".join(f":{c}" for c in cols)
            params = {c: v for c, v in zip(cols, row)}
            remote.execute(text(f'INSERT INTO "{table}" ({insert_cols}) VALUES ({vals})'), params)
        remote.commit()
        print(f"    inserted batch {i+len(batch)}/{len(rows)}")
    final = remote.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    print(f"    final remote={final}")
    return lc, final

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    print(f"LOCAL: {LOCAL_URL}")
    print(f"REMOTE: {REMOTE_URL.split('@')[1][:50]}")
    local = create_engine(LOCAL_URL, pool_pre_ping=True)
    remote = create_engine(REMOTE_URL, pool_pre_ping=True)
    with local.connect() as lc, remote.connect() as rc:
        # verify connectivity
        print("local ok:", lc.execute(text("select count(*) from locations")).scalar())
        print("remote ok:", rc.execute(text("select count(*) from locations")).scalar())
        for tbl in TABLES:
            try:
                sync_table(lc, rc, tbl, dry_run=args.dry_run)
            except Exception as e:
                print(f"  {tbl} ERR {e}")
                rc.rollback()
                lc.rollback()
                import traceback; traceback.print_exc()
                continue
        if args.dry_run:
            print("\nDRY RUN – no writes. Re-run without --dry-run to apply.")
        else:
            print("\nDone. Verify: remote locations distinct coords / udyam / weather counts above.")

if __name__ == "__main__":
    main()
