# GramBiz AI — Data Quality & Provenance System

How GramBiz decides **how much to trust** a data source and a value it presents.
No source is assumed error-free because it is "official".

## The five scores

Each source in `app/data_quality.py` (`SOURCE_QUALITY_CATALOG`) produces five
scores via `score_source()`:

| Component | Meaning | How it is computed |
|-----------|---------|--------------------|
| `source_quality_score` | Structural soundness | mean of `documented`, `licensed`, `maintained`, `schema_stable` (each 0-100) |
| `freshness_score` | Recency vs cadence | bucket from `_freshness_status` (FRESH 95 / RECENT 80 / STALE 55 / VERY_STALE 30 / UNKNOWN 40) |
| `completeness_score` | Depth of records & columns | `0.6*record_richness + 0.4*column_coverage` |
| `verification_score` | Cross-checked against origin | base `verification`, capped when `CONFLICTING` (≤45) or `UNVERIFIED` (≤35) |
| `overall_confidence_score` | Blended 0-100 | weighted: quality 0.25 + freshness 0.20 + completeness 0.20 + verification 0.35 |

`confidence_band()`: `>=70` → **high**, `>=40` → **medium**, else **low**.

### Why verification is weighted highest (0.35)
An unverified source can look flawless on paper while being wrong in practice.
The cross-check / conflict policy therefore dominates the final confidence.

## Freshness statuses (`_freshness_status`)
Thresholds are **cadence-aware** (each source defines `fresh_under` /
`recent_under` / `stale_under` in years):

```
age < fresh_under   -> FRESH
age < recent_under  -> RECENT
age < stale_under   -> STALE
else                -> VERY_STALE
age unknown (None)  -> UNKNOWN
```

Examples from the catalog:
- **UDYAM** (DAILY cadence): `0.2 / 0.5 / 1.0` → a unit list 0.7 yrs old is
  already `STALE`; 1.5 yrs is `VERY_STALE`.
- **Census 2011** (HISTORICAL): thresholds all `0.0` → any real age is
  `VERY_STALE`, and its `freshness_score` is 30. It is **never** presented as
  current population.

## Verification statuses
| Status | Meaning |
|--------|---------|
| `VERIFIED` | Cross-checked against the authoritative origin. |
| `PARTIALLY_VERIFIED` | Only district/summary level confirmed; not fully point-verified. |
| `UNVERIFIED` | Cannot be independently verified → `verification_score` capped at 35. |
| `CONFLICTING` | Disagreement between sources recorded → `verification_score` capped at 45. |

## Cross-source conflict policy
On disagreement between sources for the same fact, we:
1. Record `CONFLICTING_DATA` in the evidence / provenance.
2. Reduce confidence — e.g. `overall_confidence_score` drops to the
   `medium`/`low` band and `verification_status="CONFLICTING"`.
3. Use **conservative entity resolution** — we never merge records on name
   similarity alone.

## "No snapshot" is not "fresh"
If `age_years is None` (no successful snapshot recorded) but the source has a
live cadence, freshness is set to `UNKNOWN` and scored low (30-40). A
not-yet-synced live source is **not** given the benefit of the doubt
(`alive_override` forces the freshness sub-score low even without an age).

## Computed scores for the catalog (reference)
Scores shown are our **verified Phase 2/3 assessment** (not auto-fabricated from
live calls we did not make). Operators can revise them via the audit CLI.

| Source | Cadence | Geo | overall* | freshness* | notes |
|--------|---------|-----|----------|-----------|-------|
| `osm` | WEEKLY | point | high | varies by sync | VERIFIED |
| `market_prices_official` | DAILY | mandi | high | strict (0.1/0.3/0.7) | VERIFIED |
| `udyam` | DAILY | pincode | medium-high | strict on age | VERIFIED, heavy limitations |
| `industrial_units` | YEARLY | district | medium | ~2yr lag | PARTIALLY_VERIFIED |
| `weather_imd` | MONTHLY | district | high | medium | VERIFIED |
| `census_2011` | HISTORICAL | village | high, freshness ~30 | UNKNOWN→VERY_STALE | VERIFIED, historical |
| `soil_health` | YEARLY | village | medium | loose | PARTIALLY_VERIFIED |
| `health_facilities` | MONTHLY | point | medium-high | medium | PARTIALLY_VERIFIED |
| `infrastructure_osm` | WEEKLY | point | high | medium | VERIFIED |

\* exact numbers depend on the current snapshot age (`age_years`); see
`score_catalog()`.

## Where quality lives in the system
- **Registry:** `app/data_quality.py` — pure scoring, no DB.
- **DB ledger:** `app/data_source_audit.py` `run_audit(conn)` pairs live
  `DataSource`/`DataSnapshot` rows with the catalog and upserts into the
  `data_source_quality` table (`DataSourceQuality` model).
- **CLI:** `scripts/audit_data_sources.py` prints the quality ledger.
- **Per-analysis evidence:** `app/services/analysis.py` surfaces the relevant
  source confidence alongside each evidence block.
