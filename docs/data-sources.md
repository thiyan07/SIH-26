# GramBiz AI — Data Sources & Provenance

This document records every real/potential data source used by GramBiz AI,
its reference period, and its provenance fields. **No value is presented as
official unless it comes from a real, verifiable source.**

## Provenance Fields (applied to every data record)

| Field | Meaning |
|-------|---------|
| `source_name` | Human-readable source (e.g. Census India) |
| `source_url` | URL where the dataset can be verified |
| `dataset_name` | Name of the dataset/table |
| `source_type` | e.g. `government`, `osm`, `vendor`, `proxy`, `demo` |
| `reference_date` / `reference_year` | Period the data actually describes |
| `retrieved_at` | When we fetched/stored it |
| `geographic_level` | e.g. `village`, `block`, `district`, `state` |
| `confidence` | `low` / `medium` / `high` for this value |
| `methodology` | How the number was derived |
| `is_estimate` | Whether this is an estimate/proxy vs. a direct observation |
| `is_demo` | Whether it is demo/mock data (never presented as official) |

## Primary Sources

### OpenStreetMap (business/POI/geography)
- **Source:** OpenStreetMap via Overpass API (cached locally).
- **License:** ODbL — attribution **© OpenStreetMap contributors** required.
- **Level:** point/POI.
- **Usage:** nearby businesses, competitors, markets, restaurants, retail,
  infrastructure (schools, hospitals, banks, transport).
- **Note:** OSM coverage is incomplete. Always displayed as "Mapped X" with a
  data-completeness indicator, never as an exhaustive count.
- **Mapping & completeness:** category→tag mapping, region presets, and the
  per-record completeness/confidence scoring are documented in
  `docs/category-mappings.md` (plan §4–6).

### Census India — Population Finder / Primary Census Abstract
- **Source:** Census of India 2011 Population Finder (official).
- **Reference year:** 2011 (`census_year = 2011`).
- **Level:** village / sub-district / district.
- **Indicators:** population, households, sex distribution, age groups, work
  status.
- **Important rule:** Census 2011 population is a **historical baseline** and
  is **never** labelled as current population. If no current official source
  exists, we say so explicitly.

### data.gov.in (Indian Open Government Data Platform)
- **Discovery source for government/open datasets.**
- Potential datasets: agriculture, rainfall (IMD), market information (official
  Mandi prices), economic indicators, transport/infrastructure, schemes,
  district/block statistics.
- **Rule:** not every data.gov.in dataset is current. Every dataset stores
  `publisher, source_url, reference_period, retrieved_at, last_updated,
  geographic_level, license`. The admin/data-source page shows freshness.
- Official market price data, when available, is used for "Price Potential".
  We never invent local prices.
- **Normalization:** `scripts/ingest_government/normalize.py` turns a
  downloaded resource (JSON list/`{records:[…]}`, CSV, or CSDL-XML) into
  validated rows for the provenance-bearing fact tables. Run with:

  ```
  python -m scripts.ingest_government.ingest --dataset datagov \
      --url <resource-url> --def market_arrivals
  # or offline against a downloaded file:
  python -m scripts.ingest_government.ingest --dataset datagov \
      --file resource.json --def market_arrivals [--format json|csv|xml]
  ```

  Supported definitions (`--def`):

  | Def | Target table | Fields mapped | Why useful | Known limitations |
  | --- | ------------ | ------------- | ---------- | ----------------- |
  | `market_arrivals` | `market_prices` | item, market/mandi, district, state, min/max/modal price, arrival date (`reference_date`), unit | Grounded local Mandi prices for price/margin potential | Coverage limited to registered mandis; date parsing/units vary per resource; rows without a commodity are dropped |
  | `population` | `population_statistics` | state/district/block/village, population, households, males, females, census year | Demographic baseline per geo level | Requires a matching `locations` row; census-style data is historical |
  | `agriculture` | `agriculture_statistics` | state/district (via location), crop, season, area, production, yield | Crop economics for agriculture-dependent businesses | Granularity is district-level; rows without matching location are skipped |
  | `imd_rainfall` | `weather_statistics` | state/district (via location), month/period, rainfall value, unit | Seasonality and weather risk | Coarse district granularity; units assumed mm unless given |

  Column names are matched case-insensitively with a small alias map (e.g.
  `commodity_name`/`item` → `item_name`, `mod_price` → `modal_price`); values
  are coerced defensively so one bad cell drops that row, never the dataset.
  Provenance (source, URL, dataset, `retrieved_at`, `geographic_level`,
  confidence, methodology) is written on every stored record.

### Government Schemes & Documents (RAG corpus)
- Official scheme guidelines, eligibility documents, notifications, and
  business-support documents are ingested, chunked, embedded and
  retrieved for RAG answers with citations:
  `python -m scripts.ingest_docs.ingest --file guideline.txt --title "<title>" --url <official-url> --doc-type guideline`.
- Pipeline (plan §21): extract → sentence-envelope chunking → deterministic
  offline embeddings (portable `embedding_json`; additively a
  `vector(1024)` column + HNSW index when pgvector is available) → hybrid
  retrieval → grounded answer with citations (`POST /rag/retrieve`,
  `POST /rag/answer`). Modern embeddings (e.g. an OpenAI-compatible model)
  can be plugged in behind the same interface; the default needs no key and
  is stable across processes.
- Demo scheme documents (problem-statement parameters) can be seeded with
  `python -m scripts.seed_demo.seed_scheme_docs`; they are flagged demo and
  never presented as official.
- Scheme parameters (thresholds, interest, tenure, moratorium) are stored in
  the `government_schemes` table and are **configurable**, not hard-coded.
- The values in the problem statement (Micro Finance: ≤₹1.40 lakh project /
  ≤₹1.25 lakh loan / 6.5% / 3 yr / 3 mo; Term Loan: ≤₹50 lakh project /
  ≤₹45 lakh loan / 8% / 7 yr / 6 mo) are treated as **assumed demo parameters
  based on the supplied problem statement** until an official document is
  retrieved and verified.

### Weather / Market / Price Providers
- **WeatherDataProvider** / **MarketPriceDataProvider** interfaces with
  replaceable vendors (env-configured keys). Their concrete implementations
  serve already-ingested rows (never per-request network calls). Price
  potential reads the latest snapshot per commodity from `market_prices`,
  scoped to the analysis district (`app/engines/prices.py`); when no rows
  exist it reports unavailable and the price score stays neutral — prices
  are never invented.

### Geospatial query backend
- Radius/nearby queries are served by `app/geo.py`, which auto-selects the
  index-backed PostGIS geography path (`ST_DWithin`/`ST_Distance` on the
  optional `geom` column bootstrap `scripts/db/postgis.py`) whenever the
  database supports PostGIS and the table carries `geom`, and otherwise
  falls back to a portable haversine SQL expression. Both branches return
  the same rows ordered nearest-first with identical distance values; the
  active backend is reported as `geo_backend` on `POST /geojson/layers` and
  in the `geo` analysis log event.

## Live data integration status (Phases 4–18)

Operational plumbing for *real* (non-demo) providers — nothing runs without
credentials and nothing ever fabricates rows:

- **Official data.gov.in runners** (Phase 4/6): `scripts/ingest_government/`
  — `ingest_market_datagov.py` (market prices, configurable resource id,
  default `9ef84268-…d0070`, must be confirmed against a live key),
  `ingest_imd_rainfall.py` (IMD rainfall, resource id never hardcoded) and
  `ingest_soil_health.py` (Soil Health Card nutrient analysis, resource id
  never hardcoded). All three **exit 2 immediately** when `DATA_GOV_API_KEY`
  (and, for IMD, the confirmed `IMD_RAINFALL_RESOURCE`; for SHC, the
  confirmed `SOIL_HEALTH_RESOURCE`) is missing. The IMD integration is
  documented in `docs/IMD.md`; the data.gov.in market pipeline in
  `docs/LIVE-DATA-IMPLEMENTATION.md`.
- **Deduplication guard** (Phase 4): the `market_prices` table carries a
  partial unique index on (item_name, market_name, district, reference_date)
  `WHERE is_demo IS NOT TRUE`; `soil_health_statistics` similarly guards on
  (state, district, block, village, nutrient_type, nutrient_name,
  sample_year) `WHERE is_demo IS NOT TRUE` — re-running an official ingest
  can never create duplicate real rows.
- **Soil nutrient levels** (Phase 33): stored in their own
  `soil_health_statistics` table with provenance-bearing rows that never mix
  with crop area/production/yield. Rows keep their admin path
  (state/district/block/village) even before a village is geo-resolved, so
  district-scoped analysis queries work immediately. Provider key:
  `soil_health`.
- **Bharat Atlas keyless layers** (Phase 18b): the public API at
  https://bharatlas.com exposes curated, keyless layers over openly-licensed
  official data (no auth, no API key, ~120 req/min) — the same source of
  record the LGD geocoder already uses. Two Erode slices are stored:
  - **Health facilities** (provider `bharatlas_health`, `nic_health` layer,
    NIC/MoHFW, **GODL-India**): ~249 Erode establishments (sub-centres,
    PHCs, CHCs, hospitals) ingested into `infrastructure_points`
    (`kind=hospital`) with real coordinates straight from the source. These
    are live scoring inputs: nearest hospital distance + nearby count feed
    accessibility and risk (`app/engines/health.py`), with only real rows —
    no facility data means no score change.
  - **Admin boundaries** (provider `bharatlas_boundaries`, `lgd_districts` +
    `lgd_blocks` layers, Local Government Directory, **CC0-1.0**): Erode
    district + 13 block names/codes into `administrative_boundaries`. The
    API exposes no centroids for these polygon layers, so no coordinates are
    written (never approximated).
  - **Dedup guard**: `infrastructure_points` carries a partial unique index
    on `(source_name, source_id)` `WHERE is_demo IS NOT TRUE AND source_id
    IS NOT NULL` — an official re-run can never duplicate a facility, and
    OSM rows never collide with NIC rows.
- **Price trends** (Phase 5): `app/engines/prices.py` reports a per-item
  `delta_pct` between the two most recent dated modal prices when present.
- **Erode MSME + industrial ingests** (downloaded reference datasets): the
  downloaded `data/raw/` CSVs are loaded by idempotent runners —
  `scripts/ingest_government/ingest_udyam_csv.py` (UDYAM Erode register,
  ~95.9k real deduped units into `udyam_units`) and
  `scripts/ingest_government/ingest_industrial_erode.py` (Erode SSI FY
  2018-19 aggregate, 6,430 units into `industrial_units`), with
  `ingest_downloaded_reference.py` for `indicator_statistics` /
  `market_names`. All are provenance-bearing, dedup-guarded, and
  idempotent (re-runs store 0 rows).
  - **Wiring:** `industrial_units` drives a real district-scoped
    `industrial_units` block in `app/engines/location_features.py`
    (available/total_units/by_type; `available: False` when no data);
    `indicator_statistics` surfaces as the `industry_context` evidence block
    in the analysis report. **`market_names` (Meghalaya APMC) is stored but
    intentionally NOT wired** — out-of-state for the Erode-focused analyses.
- **Refresh CLI** (Phase 18): `python -m scripts.refresh.refresh_all` runs
  every live job within its cooldown window (`--only`, `--force`,
  `--dry-run`); a failed job reports exit code 1.
- **Observability** (Phase 17): `GET /data-sources/status` (derived status
  + freshness bucket per source) and `GET /data-sources/providers`
  (live-provider registry with ready/config-missing/no-rows state, stored
  row counts, and missing env keys) back the Data Sources page in the web
  app, where every provider card shows a live state/history badge.

## Demo Dataset (Erode District, Tamil Nadu)

The initial demo covers a small set of blocks/villages in **Erode District,
Tamil Nadu**. It uses **only real, verifiable structure** (administrative
hierarchy) plus clearly-flagged `is_demo=True` proxy values. Demo data is kept
isolated in the seed script and can be replaced by real data without changing
application code.

## Freshness / Confidence Display Rules

- Population → "Census 2011 baseline", not "Current population".
- Business counts → "Mapped competitors: N · Data completeness: Medium/Low",
  never "There are exactly N competitors".
- Any unavailable value → marked unavailable/estimated/proxy with source,
  reference date, retrieved date, confidence, and limitation.

## Dataset register (plan §7)

Every dataset we integrate must have a documented reason why it helps
business-feasibility analysis; we do not ingest datasets merely to inflate a
count. The reference `geographic_level`/`reference_period`/`last_updated`
columns are stored in the `data_sources` table and shown on the Data Sources
page.

| Dataset | Publisher | URL | Geographic level | Reference period | Last updated | Fields used | Why useful | Known limitations |
| ------- | --------- | --- | ---------------- | ---------------- | ------------ | ----------- | ---------- | ----------------- |
| Primary Census Abstract / Population Finder | Census of India | https://censusindia.gov.in | village / block / district | 2011 (Census year) | 2011 | population, households, sex ratio, literacy, workers | Demographic baseline for demand potential and household estimates | Historical; must never be presented as current population |
| OSM POIs & businesses | OpenStreetMap (Overpass) | https://www.openstreetmap.org | point (POI) | retrieved_at | on ingest | shops, restaurants, markets, banks, schools, hospitals, transport, roads | Mapped competitor count, market access, infrastructure proximity, commercial demand signals | Coverage incomplete; counts are minimums, not exhaustive |
| Agmarknet / official Mandi prices | Agmarknet (Ministry of Agriculture) | https://agmarknet.gov.in | mandi / district | latest season | weekly (when integrated) | commodity, min/max/modal price, market, date | Grounded local prices for price/margin potential; no invented prices | Coverage limited to registered mandis; not all commodities/districts |
| IMD rainfall | India Meteorological Department | https://mausam.imd.gov.in | district / block | by period (season/month) | periodic | rainfall indices | Seasonality and weather risk for agriculture-dependent businesses | Coarse (district) granularity may not match village |
| Soil Health Card | MOAFW via data.gov.in | https://data.gov.in | village / block / district | sample year | yearly | nutrient type/name/level + value | Input-cost awareness (fertilizer/soil input) for agri businesses | Official SHC rollout is gradual; coverage varies by district and year |
| District/block statistics | data.gov.in | https://data.gov.in | district / block | varies | varies | economic, infrastructure, administrative | Context for accessibility and commercial indicators | Dataset-specific quality varies; must be validated per dataset |
| NIC health establishments | NIC / MoHFW via Bharat Atlas `nic_health` (GODL-India) | https://bharatlas.com | point | retrieved_at | on ingest | name, type, place, coordinates | Grounded health-access context for rural infrastructure analysis; real points, no invented facilities | Coverage reflects govt NIC health layer/registration; type granularity is broad (sub-centre vs PHC/CHC) |
| LGD administrative boundaries | Local Government Directory via Bharat Atlas `lgd_districts`/`lgd_blocks` (CC0-1.0) | https://bharatlas.com | district / block | LGD version | on ingest | name, Census-2011 codes, parent code | Code-keyed joins on admin hierarchy (vs name-only matching) | No centroids exposed for these polygon layers; code registry only |
| UDYAM MSME registers (Erode) | Ministry of MSME — UDYAM portal | https://udyamregistration.gov.in | unit / pincode | FY 2024-25 (download) | on ingest | enterprise name, sector, NIC code, state, district, pincode, coordinates | District-scale MSME density & local sector mix; feeds `location_features.nearby_msmes` and category→NIC demand signals | Source ships **without** `udyam_number`; ~34k records have no NIC code; coordinates are pincode/geo-derived (medium confidence) |
| Small-scale industries profile (Erode) | Erode District SSI Profile (FY 2018-19) | official district profile | district | 2018-19 | on ingest | `unit_type`, `count`, 21-division NIC breakdown | District industrial base context; `industrial_units` block (available/total/by_type) | Official aggregate with ~2 yr lag; district-only, not per-pincode |
| National/state economic indicators | data.gov.in (pesticide consumption, textiles-apparel exports, retail outlet classes) | https://data.gov.in | national / state | 2017-18–2021-22 | on ingest | indicator, period, value, unit, dimension | Cross-cutting industry context in the report `industry_context` block | Reference only (not per-locality); granularity/period varies per indicator |
| APMC market directory (Meghalaya) | Meghalaya APMC | https://data.gov.in | market | retrieved_at | on ingest | market name, location | **Reference only — not wired** (out-of-state for Erode); kept for future north-eastern use | Out of scope for the current Erode-focused analyses |

**Integration rule:** a dataset is only wired into an indicator when its
fields, geographic level, and reference period match the indicator's needs,
and none of its values are presented as current/official unless verified.
