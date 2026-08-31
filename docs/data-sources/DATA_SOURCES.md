# GramBiz AI — Data Source Registry

This document is the authoritative registry of the data sources GramBiz uses to
answer **location-specific business questions** with evidence-backed, structured
data. It supersedes the earlier `docs/data-sources.md` for the discovery /
verification layer and adds the **UDYAM / industrial** track plus the
source-level **quality & verification** ledger.

## Design principles

1. **Selection over collection.** We ingest only sources that materially improve
   the ability to answer a location-specific question ("open a dairy near
   Perundurai?"). Sources that cannot be resolved to a lat/lng + radius are
   exposed as **scoped aggregates** (`pincode` / `district`), never as fake
   point competitors.
2. **No hallucination.** When evidence is absent, we return `DATA_NOT_AVAILABLE`
   — we never fabricate facts.
3. **Freshness is explicit.** Every source carries a cadence and a freshness
   status (`FRESH / RECENT / STALE / VERY_STALE / UNKNOWN`). The 2011 Census is
   never presented as current — it is `HISTORICAL` and flagged `VERY_STALE`.
4. **Confidence is computed, not assumed.** An "official" source is not assumed
   error-free. Each source gets a scored quality profile; obsolete, anonymous,
   undocumented, or unverifiable sources are rejected or downgraded.
5. **No scraping of protected/ToS-violating sites.** Google Maps / Google Places
   are **not** used. We use free, legitimate APIs and official open data.

## Freshness cadences

| Cadence | Meaning | Example |
|---------|---------|---------|
| `REAL_TIME` | Live event stream | (reserved) |
| `NEAR_REAL_TIME` | Updates within minutes | (reserved) |
| `DAILY` | Refreshed daily | Mandi prices, UDYAM unit list |
| `WEEKLY` | Refreshed ~weekly | OSM extract cache |
| `MONTHLY` | Refreshed monthly | IMD rainfall |
| `YEARLY` | Published annually, with lag | ASI factories |
| `HISTORICAL` | Fixed period, not refreshed | Census 2011 |
| `STATIC` | One-off reference | Bharat Atlas base layer |

## Implemented sources (tracked in the quality ledger)

| Key | Name | Type | License | Cadence | Geo resolution | Used for |
|-----|------|------|---------|---------|----------------|----------|
| `osm` | OpenStreetMap businesses & infrastructure | osm | ODbL-1.0 | WEEKLY | point | competitors, POIs, infrastructure |
| `market_prices_official` | Mandi prices (data.gov.in, Ministry of Agri) | government | GODL-India | DAILY | mandi | commodity prices / arrivals |
| `udyam` | UDYAM MSME registrations (data.gov.in) | government | GODL-India | DAILY | **pincode** | `nearby_msmes`, `relevant_msmes` |
| `industrial_units` | Registered Factories / ASI | government | GODL-India | YEARLY | **district** | `industrial_units` aggregate |
| `weather_imd` | IMD rainfall | government | GODL-India | MONTHLY | district | weather risk |
| `census_2011` | Census of India 2011 | government | GODL-India | HISTORICAL | village | population baseline |
| `soil_health` | Soil Health Card scheme | government | GODL-India | MONTHLY | district | soil-driven risk |
| `health_facilities` | Health facilities (HiFRa / derived) | government | GODL-India | MONTHLY | point/village | health accessibility |
| `infrastructure_osm` | OSM-derived infrastructure | osm | ODbL-1.0 | WEEKLY | point | roads, transport, markets |

## UDYAM (this task's P0 government source) — verified facts

- **Source of truth:** data.gov.in resource *"List of MSME Registered Units under
  UDYAM"* (Ministry of Micro, Small & Medium Enterprises).
- **Access:** data.gov.in Open Government Data (OGD) API, requires a
  `DATA_GOV_API_KEY`. The ingest is **key-gated** — it fails fast (exit 2) and
  writes nothing if the key / resource id is missing; MSME facts are **never
  approximated**.
- **Resolution:** **pincode-level.** The public unit list publishes enterprise
  name, NIC-5 activity code, pincode, address, and registration metadata, but
  **no exact lat/lng, no turnover, no investment, and no MSME-class
  (micro/small/medium) field**.
- **Geocoding:** with an optional pincode directory (`UDYAM_PINCODE_DIRECTORY`),
  each unit is located at its **pincode centroid**. It is stored on
  `UdyamUnit.latitude / .longitude` and marked `geographic_level="pincode"` with
  reduced confidence.
- **How it feeds the analysis:** `location_features` exposes
  - `nearby_msmes` — UDYAM units whose **pincode centroid** falls within the
    query radius (not treated as point competitors).
  - `relevant_msmes` — units in the same district + NIC division prefix.
  - `sector_composition` — NIC-division rollup.
  - `geo_resolution="pincode"` and a caveat note are always surfaced.
- **Why not exact point competitors:** because units are pinned to a pincode
  centroid (not an address), they are never reported as competitors with exact
  distances. OSM remains the point-radius competitor source. This matches the
  user-confirmed decision: *"Pincode-level with caveats."*
- **Why `udyogaadhaar.gov.in`/scraping is not used:** the portal's per-unit
  detail (turnover/investment/class) is not exposed via a stable, licensed API,
  and scraping it is unreliable and ToS-risky. UDYAM enters only via OGD.

## Industrial / factories (P1 government source)

- **Source of truth:** ASI / Registered Factories (MoSPI / state Labour
  Departments) and related district tables.
- **Resolution:** **district-only** — official factory data does not publish
  unit lat/lng. It is therefore stored as a **district-scoped aggregate**
  (`IndustrialUnit` / `industrial_units` block with `available=False` unless a
  district match exists) and is **not** usable for point-radius queries.
- The catalog marks it `PARTIALLY_VERIFIED` with a ~2-year publication lag.

## Rejected / not-used sources

| Source | Why rejected |
|--------|--------------|
| Google Maps / Google Places | ToS prohibits scraping; no licensed bulk export. |
| `udyogaadhaar.gov.in` scraping | Unstable, non-licensed, ToS-risky; not a stable API. |
| Kaggle MSME datasets | `ML_TRAINING_ONLY` unless they add verified geo coverage; not authoritative. |
| Reddit / community scrapes | `COMMUNITY_SIGNAL` only — supporting evidence, never authoritative. |

## API access

| Source | Endpoint / access | Auth |
|--------|-------------------|------|
| OSM / Overpass | `app/config.py: overpass_url` | free, anonymous |
| data.gov.in OGD (mandi + UDYAM) | `data.gov.in` catalog resources | `DATA_GOV_API_KEY` |

See `DATA_PIPELINE.md` for the refresh orchestration and `DATA_LICENSES.md` for
attribution obligations.
