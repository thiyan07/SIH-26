# Tamil Nadu Business Discovery & Coverage Engine

> **Product principle:** GramBiz AI does not claim to enumerate every business in Tamil Nadu. It maintains a multi-source, geographically validated business discovery dataset with measurable coverage and provenance.

## 1. Architecture

```
Tamil Nadu
  → District (38 canonical)
    → Taluk / Block (Location.block / sdtname)
      → Municipality / Town / Panchayat (type inference)
        → Village / Locality (Location.village with lat/lon)
          → Search targets
            → Category/query matrix
              → Google Maps (adaptive) + OSM (Overpass)
                → Raw observations
                  → Normalization
                    → Geographic validation
                      → Cross-source deduplication
                        → Canonical businesses
                          → Coverage audit
```

All numbers are discovery counts, never "total businesses in reality".

## 2. Administrative hierarchy

* Source: LGD 2024 via Bharat Atlas `lgd_villages` (village centroids `_lat/_lng`, `vilcode11`, `sdtname`, `gp_name`) + existing Location table (14998 rows across 38 districts, browser-verifiable).
* Canonical 38 districts defined in `app/discovery/admin.py:TN_DISTRICTS_CANONICAL` (Revenue Dept 2024). Aliases normalized: `Tuticorin` → `Thoothukudi`, `Viluppuram` → `Villupuram`.
* No village is fabricated. Missing coordinates are skipped, never invented.
* Hierarchy is flexible: not every locality has pincode/taluk; parent = block when village≠block.
* Validation: `scripts/discovery/run_discovery --district all --coverage-report` checks `validate_hierarchy`.

## 3. Source hierarchy

* **Tier 1** — Official government (Census, DES handbook, UDYAM, Soil Health) via `app/data_sources/registry.py`.
* **Tier 2** — Government-derived reports.
* **Tier 3** — OSM/Overpass (ODbL, community-verified).
* **Google Maps** — commercial/web discovery source, separate provenance (`source=google_maps`, ToS-respecting, rate-limited, never labeled as government).

Never summed into a fake "total businesses".

## 4. Category strategy (adaptive, not hardcoded)

Tiers in `app/discovery/config.py`:
* **Tier A** common: grocery, pharmacy, restaurant, bakery, tea_shop, salon, mobile_shop, electronics, hardware, mechanic, textile, furniture, clothing, stationery, printing.
* **Tier B** agri/rural: fertilizer, seed_shop, agricultural_equipment, tractor_dealer, animal_feed, irrigation_supplies, dairy.
* **Tier C** specialized: hotel, hospital, finance, travel_agency, etc.

Village ≠ only grocery+pharmacy. `app/discovery/category_strategy.py` selects per locality class; specialized categories are suppressed in villages to avoid explosion.

## 5. Locality-size aware discovery

`app/discovery/locality_classifier.py` assigns:
`METRO > LARGE_CITY > TOWN > SMALL_TOWN > VILLAGE > RURAL_LOCALITY`
from district (Chennai → METRO) and type/county heuristics.

Depth per class (`config.py`):
* METRO 5000m, 40 targets, grid enabled, 12 scrolls
* VILLAGE 2000m, 8 targets, 5 scrolls, 20 results
* RURAL 1500m, 6 targets, 3 scrolls, 15 results

Grid/cell discovery is optional for metros only (`grid_enabled_for`).

## 6. Search target generation

`app/discovery/targets.py:generate_targets(state, district, locality, category, source, max_localities)` is data-driven from `Location` rows. Each `DiscoveryTarget` has:
`district, administrative_area, locality, locality_type, locality_class, lat, lon, category, query_variant, query, source, priority, radius_m`.

Query variants (`query_variants.py`): `"{category} in {locality}, {district}"` plus `"{category} in {locality}, {block}, {district}"`. Contextual `market/bus stand/main road/junction` only for villages and capped.

No hardcoded `KEY_VILLAGES/TOWNS` lists. Same code path for `Erode` and `Chennai`.

## 7. Google Maps adaptive discovery

`app/discovery/providers/google_maps.py:scrape_target_adaptive`:
* Configurable `max_results` (default 60, village capped 20), `max_scrolls` (12, village 5), `plateau_threshold` 2, `plateau_min_new` 3.
* Scrolls the `div[role=feed]` feed, extracts via `_EXTRACT_JS` (same as legacy scraper), deduplicates during discovery via `google_id/cid_seed/place_url`.
* Termination reasons: `RESULT_PLATEAU`, `MAX_SCROLL_LIMIT`, `MAX_RESULT_LIMIT`, `NO_MORE_RESULTS`, `ERROR`, `TIMEOUT`.
* Records `results_observed, unique_results, scrolls_attempted, termination_reason, elapsed_s`.
* Rate-respecting: bounded concurrency (`DISCOVERY_CONCURRENCY=3`), delay (`1.5s`), retries with backoff, no CAPTCHA bypass, no stealth.

## 8. OSM cross-check

Existing Overpass provider (`app/providers/overpass.py`) is reused. For each target:
`Google observations + OSM observations → normalization → geographic matching → cross-source dedup`.
Match uses normalized_name, coordinates (<60m), phone/website, Jaccard token similarity (see `dedup.py`). Weak matches remain separate.

## 9. Canonical business model

`app/discovery/dedup.py` merges observations into `CanonicalBusiness` with confidence:
* `EXACT` same source_id
* `HIGH` same name <60m + phone/brand corroboration
* `MEDIUM` Jaccard ≥0.6 <100m
* `LOW` weak — not merged
* `UNMATCHED` — single-source

Preserves `sources: [google_maps, osm]`, `source_ids`, original `source_id`s, never overwrites silently.

## 10. Geographic validation

`app/discovery/geo_validation.py:validate_observation`
* Computes `distance_from_target_km` via `haversine_km`.
* Status: `IN_TARGET_LOCALITY` (≤ radius), `NEAR_TARGET_LOCALITY` (≤2×radius or 5km), `OUTSIDE_TARGET_AREA`, `GEOGRAPHICALLY_UNCERTAIN` (missing coords).
* Nothing auto-discarded; downstream can filter or flag.

## 11. Coverage engine

`app/discovery/coverage.py` tracks per `(district, locality, category, source)`:
`queries_attempted, successful, unique_results, google_results, osm_results, cross_source_matches, last_scraped_at, search_depth`.

Status `GOOD/PARTIAL/LOW/NOT_SEARCHED/ERROR/STALE` + wording `High/Moderate/Low discovery coverage / Not yet surveyed`. Freshness `fresh (<30d) / aging (<90d) / stale (>180d) / unknown`.

Score is a weighted discovery coverage score (locality 25%, category 20%, source diversity 15%, saturation 15%, freshness 15%, geographic 10%), not a business-count truth score.

Tables `discovery_runs`, `discovery_observations`, `coverage_audits` (migrated via `app/db/models.py`) store the ledger; `DISCOVERY_COVERAGE` leverages existing `coverage_audits`.

## 12. Provenance & freshness

Every `DiscoveryObservation` retains `source, source_id, source_url, retrieved_at, query, target_locality, target_category, scraper version`. Google Maps is never labeled government.

## 13. Backfill orchestrator (live pipeline)

`app/discovery/orchestrator.py` production flow:
`TARGET → PROVIDER (Google/OSM) → OBSERVATIONS → GEO VALIDATION (radius + district bbox) → NORMALIZATION → DEDUPLICATION (EXACT/HIGH/MEDIUM) → UPSERT (Business + DiscoveryObservation) → COVERAGE UPDATE (CoverageAudit) → CHECKPOINT (DiscoveryRun) → REPORT`

* **Checkpoint:** `DiscoveryRun` created at start (`status=running`, `targets_generated`, `started_at`). After each district batch, `targets_scraped`, `observations`, `canonical_businesses` and `metadata_json.processed_target_ids` (stable hash `district|locality|category|query|provider`) are committed. On interrupt `status=partial`; on completion `completed`.
* **Resume:** `--resume <run-id>` loads `DiscoveryRun`, verifies not `completed`, skips already-processed target identities, continues from remaining, preserving previous observations (no duplicate businesses).
* **Guard:** `--district all --live` without `--max-localities` or `--max-targets` fails with `Statewide live discovery requires --max-localities or --max-targets. Use --dry-run to inspect the plan.` (tested).

## 14. Prioritization & scheduler

`app/discovery/targets.py:schedule_targets()` deterministic:

* Coverage-aware: `NOT_SEARCHED (0) < LOW (1) < STALE (2) < PARTIAL (3) < GOOD (4)` via `CoverageAudit` lookup when session provided.
* Then `high (0) < medium (1) < low (2)`.
* Enforced via `--max-targets N` and/or `--max-localities N` (sorted, sliced, never silently exceeded). Dry-run shows `With --max-targets N, the following N targets would execute first.`

## 15. Cache / previous observation reuse

* **OSM:** `app/discovery/providers/osm_adapter.py` checks `CompetitorCache` (`scope_key=osm:<hash>`, TTL 24h) before Overpass; on hit rehydrates `DiscoveryObservation` list, on miss queries `app/providers/overpass.py` (mirrors + timeout) and stores `payload` + `queried_at`.
* **Google/OSM observations:** `_check_previous_observation()` looks for recent `DiscoveryObservationModel` for same `district|locality|category|source|query` within TTL; if fresh, reuse and update coverage without provider call. Stale (>TTL) triggers refresh.
* Provider failures are recorded as `success=False` in `CoverageAudit` (`ERROR`), not as zero-business fact.

## 16. OSM provider adapter

`app/discovery/providers/osm_adapter.py` maps `category_code` → OSM tags via `app/catalog/business_categories.osm_filters` (e.g., `restaurant→amenity=restaurant`, `pharmacy→amenity=pharmacy`). No invented tags; unknown category returns empty. Observations preserve `source=osm`, `source_id=type/id`, `retrieved_at`, `query`, `locality`, `category`, `matched_tags`, `provenance`.

## 17. CoverageAudit — real measurement

`app/discovery/coverage.py` + `CoverageAudit` table now populated live: after each provider attempt `_update_coverage()` upserts `(district,locality,category,source)` with `queries_attempted/successful`, `unique_results`, `google/osm_results`, `cross_source_matches`, `last_scraped_at`, `coverage_status` (`NOT_SEARCHED/LOW/PARTIAL/GOOD/STALE/ERROR`), `freshness`. CLI `run_discovery --coverage-report` now reads `CoverageAudit` (discovery coverage) plus admin `localities` count, keeping administrative vs business discovery separate.

## 18. DB efficiency & streaming

* `locations.district_normalized` (indexed) added via `app/db/models.py`; backfilled to `normalize_name(canonical_district(district))`. `admin.py:get_localities_for_district()` now queries `WHERE district_normalized=:norm` (indexed) with fallback to Python filter; `get_all_districts()` aggregates via `district_normalized` when available.
* `targets.py:generate_targets_stream()` yields `district→locality→target` without materializing statewide 121k list; `run_live()` processes district batches incrementally with per-batch commit (no giant transaction). Dry-run still counts but live is streaming.

## 19. Geographic district polygon containment

`app/discovery/geo_validation.py:validate_observation()` first attempts `AdministrativeBoundary` bbox containment (`level=district`, `bbox` JSON) via `_district_bbox_contains()`; if point outside bbox → `OUTSIDE_DISTRICT`. If no bbox, falls back to radius-based `IN/NEAR/OUTSIDE`. Tested with and without bbox.

## 20. Legacy Erode scraper

`apps/api/scripts/scrape_competitors/scrape_google_maps.py` now has hard guard: without `--allow-legacy` it errors with `This is the legacy Erode scraper (TOWNS/KEY_VILLAGES). Use scripts.discovery.run_discovery for the production Tamil Nadu discovery engine.` Historical raw data under `apps/data/scrape/google_maps/` is preserved. Production docs reference only `scripts.discovery.run_discovery`.

## 21. Configuration

All in `app/discovery/config.py:DiscoveryConfig` (env-override `DISCOVERY_*`), not scattered.

## 22. CLI (production)

```
# DRY RUN (safe, no provider calls)
python -m scripts.discovery.run_discovery --district all --dry-run
python -m scripts.discovery.run_discovery --district Erode --dry-run --json

# BOUNDED LIVE (requires cap for statewide)
python -m scripts.discovery.run_discovery --district Erode --max-localities 5 --max-targets 50 --priority high --live --source both
python -m scripts.discovery.run_discovery --district Erode --locality Perundurai --category grocery --live --max-targets 10

# RESUME
python -m scripts.discovery.run_discovery --resume <RUN_ID> --live

# COVERAGE (discovery, not just admin)
python -m scripts.discovery.run_discovery --district Erode --coverage-report
python -m scripts.discovery.run_discovery --district all --coverage-report

# DISTRICT-NORMALIZED BACKFILL (one-time)
python -c "from app.discovery.admin import backfill_district_normalized; from app.db.session import session_scope; with session_scope() as s: print(backfill_district_normalized(s))"
```

Dry-run shows `districts, administrative_localities_discovered, search_targets_generated, google/osm targets, by_priority/class` plus `With --max-targets N, the following N targets would execute first.`

## 17. Limitations (honest)

* Location table is LGD + OSM hybrid (14998 rows); some hamlets are OSM points (medium confidence) not LGD high-confidence centroids.
* No live panchayat shapefiles — district containment is approximated by radius + distance, not polygon.
* Google Maps is sampled, not exhaustive, and ToS-limited; coverage is discovery coverage.
* Grid discovery is coarse (2km cells, max 9) to avoid million-request explosion.
* Chennai has only 27 Location rows (district is urban, not village-centric) — metro discovery relies on locality+grid, not village enumeration.
