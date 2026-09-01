# Competitor data quality

How the quality of competitor data is measured, persisted, and surfaced honestly
— including per-source scores from the live `data_source_quality` ledger and per-
record confidence/verification on ingested `businesses`.

## 1. Source-level quality (`data_source_quality` ledger)

The operational audit (`scripts/audit_data_sources.py` → `app/data_source_audit.py`)
computes five scores for every registered data source from the declarative
`SOURCE_QUALITY_CATALOG` and real snapshot age, and upserts them into the
`data_source_quality` table. The **competitor-relevant** sources:

| source_key | source_quality | freshness | completeness | verification | overall | label | status |
|---|---|---|---|---|---|---|---|
| **osm_business** | **95.0** | 95.0 | 73.0 | 95.0 | **90.6** | high | VERIFIED |
| osm_infrastructure | 91.2 | 30.0 | 78.0 | 90.0 | 75.9 | high | VERIFIED |
| (context) census_2011 | 91.2 | 30.0 | 93.0 | 95.0 | 80.7 | high | VERIFIED |
| (context) udyam | 86.2 | 95.0 | 66.0 | 85.0 | 83.5 | high | VERIFIED |

`osm_business` is scored **source_quality 95 / overall-confidence 90.6 (high,
VERIFIED)** — that is the documented `source_quality_score` for the competitor
data source. Freshness is `95` (a successful OSM fetch happened in this window).

## 2. Per-category confidence formula (plan §9)

Discovery confidence is deterministic and transparent:

```
raw = mapped_count_adjusted                     (coverage vs radius area)
coverage_factor = {low:0.45, medium:0.72, high:0.92}
source_factor    = 0.85   (single verified live source, e.g. OSM ODbL)
                   0.80   (DB-backed previously-ingested real rows)
freshness_factor = 1.0 (fresh) → 0.5 (>365d)
confidence = clamp(raw · coverage · source · freshness, 0, 1)
```

A `count=0` low-coverage read is additionally discounted ×0.6 because **absent
data is not evidence of low competition**. The `confidence` object in the
response exposes `factors.{coverage,source,freshness}` so the number is auditable.

## 3. Per-record verification fields (plan §10)

Each ingested `businesses` row carries:

- `normalized_name` — lowercased/trimmed, for conservative dedupe.
- `confidence_score` — per-record confidence set at ingest.
- `verification_status` — currently `UNVERIFIED` at ingest (real OSM source,
  not independently verified); surfaced in DB-fallback POIs.
- `source_updated_at`, `first_seen_at`, `last_seen_at` — recency/audit trail.
- `phone`, `website`, `opening_hours`, `brand` — when present in source tags.
- Existence status per read: `ACTIVE` (<90d) / `RECENT` (<365d) / `STALE` /
  `UNKNOWN` — reported honestly, never invented.

## 4. Dedupe honesty

`dedupe_competitors` merges only (a) identical normalized names **and** (b)
coordinates within 60 m. Different names, or the same name at clearly different
places, are **never** merged; ties are flagged `possible_duplicate` rather than
guessed.

## 5. No-fabrication guarantees (tests)

The suite locks in that a zero result from a down source is never parroted or
synthesised:
- `test_discover_external_source_failure_falls_back_to_db` — external failure
  degrades to real DB rows, never fake ones.
- `test_discover_db_fallback_zero_rows_is_never_fabricated` — all sources down +
  no previous rows ⇒ `UNAVAILABLE` (0), never a synthetic competitor list.
- `test_geoapify_provider.py` — no key ⇒ provider skipped; uncategorised data ⇒
  honest empty read.

## 6. Honest degradation

Public Overpass mirrors intermittently error. The ladder always prefers a real
source over a guess and reports `data_status` = `FRESH | CACHED | DB_FALLBACK |
STALE_CACHE | UNAVAILABLE` with the actual `source`/`mirror`/`retrieved_at`.