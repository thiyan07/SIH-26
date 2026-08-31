# GramBiz AI — Data Pipeline & Refresh

How sources are ingested, stored, refreshed, and surfaced, with a focus on the
UDYAM / industrial track added by the discovery layer.

## Pipeline stages
1. **Ingest** — a per-source script fetches from a legitimate API / open feed.
2. **Normalize & validate** — fields are aliased, typed, and validated; bad rows
   are dropped, never fabricated.
3. **Store** — upsert into PostGIS-backed tables (`Base.metadata` models).
4. **Geocode / resolve** — pincode → centroid, or district aggregation where the
   source has no exact lat/lng.
5. **Refresh** — an orchestrator runs jobs on cooldowns.
6. **Audit** — quality/freshness/verification ledger is recomputed from live
   snapshots vs the catalog.

## UDYAM ingest (`scripts/ingest_government/ingest_udyam.py`)
- **Gating:** key-gated. If `DATA_GOV_API_KEY` or `UDYAM_RESOURCE` is missing it
  **fails fast (exit code 2)** and writes nothing — MSME facts are never
  approximated (`test_ingest_udyam.py::test_missing_key_fails_fast_without_writing`).
- **Source:** data.gov.in OGD API resource "List of MSME Registered Units under
  UDYAM" (Ministry of MSME).
- **CLI:** `--resource`, `--state` (default `Tamil Nadu`), `--dry-run`.
- **Normalization:** field-alias tolerant (`FIELD_ALIASES`); maps government
  column names onto `UdyamUnit` fields (udyam_number, enterprise_name, category,
  sector, nic_code, state, district, pincode, address, registration_date).
- **Geocoding:** optional pincode directory (`UDYAM_PINCODE_DIRECTORY`) →
  `PincodeResolver` returns pincode centroid → stored on
  `UdyamUnit.latitude / .longitude`, `geographic_level="pincode"`,
  `confidence="medium"`.
- **Store:** upsert-by-`udyam_number` with dedupe partial unique indexes
  (`uq_udyam_real_dedupe`, `ix_udyam_district_real`).
- **No live key in tests:** tests use fixtures only; no network calls.

### Sizing `latitude`/`longitude` (column rename note)
`UdyamUnit` uses plain `latitude`/`longitude` (not `pincode_latitude`/...) so it
works with the shared `find_nearby` radial query. If a pre-existing
`udyam_units` table still has the old `pincode_*` columns, it must be recreated
or migrated (`Base.metadata.create_all` creates new tables but does not ALTER
existing ones). The test DB had this stale-schema issue and the stale table was
dropped so `create_all` rebuilt it with the correct columns.

## Refresh orchestration (`scripts/refresh/refresh_all.py`)
- Cooldown-aware: each job declares a `cooldown`; a job is skipped until its
  cooldown has elapsed since the last successful run.
- Key-gated jobs (data.gov.in) fail fast rather than polluting the ledger.
- CLI: `--only <key>`, `--force`, `--dry-run`.
- UDYAM job:
  ```python
  Job(key="udyam", label="UDYAM MSME units (data.gov.in, Ministry of MSME)",
      run=lambda: ingest_udyam.main([]), cooldown=dt.timedelta(days=7),
      snapshot_job_hint="udyam_erode")
  ```
- The scheduling is additive; existing jobs (OSM, market, mandi, soil, IMD)
  are unchanged.

## Databases & schema
- **Backend:** FastAPI + SQLAlchemy + PostGIS. Geospatial math stays in the
  backend/DB (**no frontend lat/lng distance calculations**).
- **Test DB:** Postgres on port `5433` (socket `/tmp/.s.PGSQL.5433`); the
  `engine`/`seeded` fixtures call `init_db` which runs `create_all`.
- **Schema bootstrap:** `scripts/db/init_schema.py` was extended with the UDYAM
  and industrial dedupe indexes.
- New models: `DataSourceQuality` (`data_source_quality`), `UdyamUnit`
  (`udyam_units`), `IndustrialUnit` (`industrial_units`).

## Data-quality ledger refresh
`scripts/audit_data_sources.py` runs `run_audit(conn)` which:
1. Reads live `DataSource` / `DataSnapshot` rows.
2. Computes the age of the latest successful snapshot per source.
3. Pairs each key with `SOURCE_QUALITY_CATALOG` (`app/data_quality.py`).
4. Upserts a `DataSourceQuality` row (`data_source_quality` table).

## Caching & invalidation
- Spatial results are keyed by `latitude, longitude, radius, business_category,
  data_version` — **not** by place name — so moving the proposed marker triggers
  a new spatial query.
- Queries are issued on **confirm**, not on every marker drag.

## `DATA_NOT_AVAILABLE` contract
When a source has no applicable records for the query (e.g., no UDYAM units in
district/radius, or district-only industrial data requested at point radius),
the analysis returns `available=False` / `DATA_NOT_AVAILABLE` instead of
fabricating a number. See `app/engines/location_features.py`
(`geo_resolution="pincode"`, `industrial_units` district-scoped with
`available=False`).
