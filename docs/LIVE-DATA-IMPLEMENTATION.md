# GramBiz AI — LIVE INDIA DATA INTEGRATION & PRODUCTION HARDENING

Living implementation document. Updated phase-by-phase as integrations are
built, verified, and shipped. Start of work: repository audit (Phase 0).

## 0. Purpose & working rules

GramBiz is being turned from a large-but-frozen prototype into a genuinely
**data-driven, India-first, hyper-local business-intelligence system**.

Non-negotiable rules (from the task brief):

1. **Never fabricate data.** Every number surfaced to a user must trace to a
   stored, provenance-tagged record, a documented deterministic calculation,
   or an explicit honest "unavailable".
2. **Historical is not live.** Census-2011 values are labelled historical and
   never presented as current; freshness is expressed as
   LIVE/N EAR-REAL-TIME/DAILY/MONTHLY/HISTORICAL.
3. **Real and demo never mix.** Real analysis runs default `is_demo=False` and
   exclude demo rows; demo data is quarantined from scoring.
4. **A provider is complete only when** implemented → connected to backend →
   stored (provenance-tagged) → tested → verified against a real response →
   documented (source, licence, limitations). Until then it is a gap, not a
   feature.
5. **Never downscale.** District-level official data is never divided down to
   village level. When only district data exists, it is shown as district-level
   evidence with its real geographic level.
6. A provider that fails must leave the analysis usable (failure isolation),
   report a clear reason, and never crash the pipeline.
7. Priority to official Government of India sources; third-party mirrors are
   labelled as mirrors with medium confidence.
8. Every integration must be verifiable via the response the user actually sees
   (the UI must be able to show "where does this number come from?").

## 1. System architecture snapshot (from audit)

Monorepo `grambiz-ai/`: `apps/api` (FastAPI + SQLAlchemy + PostgreSQL) and
`apps/web` (React 18 + Vite + Tailwind + recharts + **Leaflet**/react-leaflet).

### Backend (`apps/api`)
- Routers: `app/api/{locations,businesses,market,financial,analysis,ai,data_sources,geo,rag}.py`
  registered in `app/main.py`; slowapi rate limiter present.
- Orchestration: `app/services/analysis.py` assembles per-category evidence and
  delegates to deterministic engines + AI narrative.
- Deterministic engines: `app/engines/` → `finance`, `profit`, `competition`,
  `market`, `prices`, `repayment`, `score`, `category_profiles`.
- AI/narrative: `app/ai/` → `llm.py`, `rag.py`, `compose.py`
  (report/SWOT/risk). RAG = keyword-hash embeddings over stored
  `document_chunks` (MoFPI scheme documents); grounded only, else explicit
  "insufficient" answer.
- Infrastructure: `app/{config,log,provenance,geo,geojson}.py`.
  `app/log.py` = structured `log_event(...)` (observability). `app/db/`.
  `app/db/models.py` carries provenance columns on every sourced fact table.
- DB bootstrap: manual schema creation (`app/db/...`); `db/migrations/`
  directory present (inspect before first migration).

### Ingestion (`apps/api/scripts/`)
- `ingest_government/`: `ingest.py` generic data.gov.in pipeline (`--dataset`
  supports `census|datagov`; `normalize.py` `DATAGOV_DEFS` =
  `market_arrivals`, `population`, `agriculture`, `imd_rainfall`;
  `store_datagov()`; `register_data_source()`).
  - `scrape_erode_census.py` (Census 2011 Erode build), `ingest_village_census.py`,
    `ingest_dchb_village_profile.py` (DCHB enrichment), `geocode_erode_locations.py`,
    `regeocode_unresolved.py`, `ingest_bharatlas_geocode.py` (LGD 2024 geocoding),
    `ingest_mandi_live.py` (ACROP mirror of APMC/Agmarknet daily tables),
    `ingest_agriculture_stats.py`, `ingest_scheme_docs.py`,
    `ingest_openmeteo_weather.py`, `ingest_weather_current.py`
    (NASA POWER + Open-Meteo forecast).
- `ingest_osm/` (OSM points extract for Erode bbox), `ingest_docs/`,
  `seed_demo/` (demo rows), `db/`.
- **No IMD integration exists. No Bhuvan integration exists. No scheduler
  exists** (refresh is manual).

### Frontend (`apps/web`)
- Pages: `Analyze`, `Dashboard`, `Market`, `MapPage`, `Finance`, `Simulator`,
  `Report`, `Schemes`, `DataSources`, `Landing`. `lib/api.ts` fetch wrapper with
  Vite proxy to `:8000`. `components/`: `BusinessMap` (Leaflet), `ScoreDonut`,
  `Layout`, `ErrorBoundary`, `ui.tsx`.
- Editing map is **Leaflet**, not MapLibre (audit confirmed: package.json has
  no maplibre). Keep the existing Leaflet map; do not churn the map library.

## 2. Provider inventory & status

| Provider | Pipeline | Licence/Attribution | Recency | Coverage | Confidence | Status |
|---|---|---|---|---|---|---|
| Census 2011 (LGD-built Erode villages/towns) | scrape + ingest_village_census | OGL-style official, Apache-2.0 code | 2011 (historical) | 250 villages via census + 105 LGD | high | **Live** |
| DCHB village profiles (Erode) | ingest_dchb_village_profile | official statistics | 2011 | per-village | high | Live |
| LGD 2024 village geocoding | ingest_bharatlas_geocode | CC0-1.0, attribution LGD + yashveeeeeeer/india-geodata | 2024 layer | 105 locations (+9 towns) adopted | high | Live (23 still unresolved) |
| OSM points (Erode bbox) | ingest_osm | ODbL | current | 46 businesses + 728 infra | medium | Live |
| Weather (current+historical) | ingest_weather_current / ingest_openmeteo_weather | Open-Meteo (CC-BY), NASA POWER | live/forecast | original 145 locations only | medium | Live (gap: 105 new locations lack weather) |
| Market prices (APMC/Agmarknet via ACROP mirror) | ingest_mandi_live | aggregator mirror, ministry-reported | daily | 109 Erode rows, ~19–30 Aug 2026 | medium | Live (mirror; official API keyed yet unused) |
| data.gov.in official downloads (market_arrivals, population, agriculture, imd_rainfall) | ingest.py/normalize.py (generic) | CC-BY / data.gov.in | on ingest | district-level | — | **Code only, not yet run** (needs DATA_GOV_API_KEY) |
| IMD weather | — none — | IMD API needs key | — | — | — | **Not integrated** (document, keep Open-Meteo) |
| Bhuvan/ISRO geospatial | — none — | eval required | — | — | — | **Not integrated** (Bharat Atlas used instead) |
| Scheme documents (MoFPI) | ingest_scheme_docs | official PDFs | 2024 docs | 2 docs / 37 chunks | high | Live (grounded RAG) |

## 3. Data model & provenance contract

Every externally-sourced fact row carries `ProvenanceMixin` columns
(`source_name/url`, `dataset_name`, `source_type`, `reference_date/year`,
`retrieved_at`, `geographic_level`, `confidence`, `completeness`,
`methodology`, `is_estimate`, `is_demo`). `DataSource` (registry with
`last_updated`, `freshness_note`, `record_count`, `why_used`,
`known_limitations`) and `DataSnapshot` (per-run `job_name`, `status`,
`records_ingested`, `errors`, `log`, timestamps) track the data pipeline.
Freshness and confidence policies live in `app/provenance.py`
(`DEFAULT_POLICIES`, `confidence_band`, `compute_data_quality`).

`MarketPrice` currently has **no uniqueness constraint** — dedupe is done in
the ingest script by `(item_name, market_name, reference_date)`. A DB-level
constraint must be added (Phase 4/5).

## 4. Analysis pipeline & decision logic

`analysis.py` builds evidence per category → engines compute deterministic
0–100 component scores → `compute_opportunity()` fuses them into
`overall_score` + `confidence_score/label` + `recommendation`
(GO/MODIFY/AVOID). Missing evidence lowers confidence; it never invents
values. Price component reads stored `MarketPrice` rows only.

Phase 12 will split **opportunity score** (can I do well here?) from
**data confidence** (can I trust the evidence?) into an explicit decision:
GO / MODIFY / AVOID / INSUFFICIENT DATA with configurable thresholds
(via env or config), mirroring the three-state per-indicator provenance the
engines already produce.

## 5. Phase-by-phase implementation status

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository audit + this document | **In progress** |
| 1 | Geocoding completion & data inventory | Bharat Atlas pass done (105 adopted, 23 unresolved) |
| 2 | Raw-data bootstrapping (OSM, roads, census build) | Live |
| 3 | Demo-data exclusion hardening + tests | Pending |
| 4 | Official data.gov.in market price pipeline | Pending (generic pipeline exists) |
| 5 | Market price geo-analysis (nearest mandi, history, unavailable) | Pending |
| 6 | IMD weather integration (or document unavailability) | Pending |
| 7 | Weather→business-risk heuristics (labelled heuristic) | Pending |
| 8 | Bhuvan or alternative geospatial eval | Pending (Bharat Atlas already adopted) |
| 9 | LGD codes in admin boundaries | Partial (codes in LGD geocode metadata) |
| 10 | Newer official population (or honesty label Census-2011) | Pending (document only) |
| 11 | Hyper-local market analysis (nearest market/demand) | Partial |
| 12 | Opportunity vs data-confidence decision logic, configurable | Pending |
| 13 | Finance evidence from official scheme params | Partial (SIH-configured defaults) |
| 14 | Official scheme parameter sources | Pending (label provenance) |
| 15 | RAG grounded answers, explicit insufficiency | Live (audit in Phase 15) |
| 16 | Analysis-language + numeric grounding | Live (language param + prompt grounding) |
| 17 | Freshness/health API + UI surface | Partial (provenance engine exists; no endpoint) |
| 18 | Refresh cadence & jobs | Pending (manual only; refresh CLI to add) |
| 19 | Data-quality validation & quarantine | Partial (validation in normalize) |
| 20 | Existing map + marker provenance (keep Leaflet) | Partially done (markers lack demo/real label) |
| 21 | Grayscale before location/visible actions | Pending (small, defer/accept) |
| 22 | End-to-end REAL-data test (live DB classification) | Pending |
| 23 | OSM refresh & completeness | Pending |
| 24 | Frontend transparency (source/freshness on every metric) | Pending (DataSources page exists) |
| 25 | Provider observability (structured run logs) | Partial (log_event used; standardize) |
| 26 | Failure handling/isolation per provider | Partial |
| 27 | Performance (analysis caching, indices) | Partial (indices present) |
| 28 | Security (secrets scan, env hygiene) | Pending |
| 29 | Documentation (README, DATA-SOURCES, DATA-POLICY) | Pending |
| 30 | Final verification (typecheck, lint, build, tests) | Pending |
| 31 | Git hygiene and history | Pending (bharatlas changes uncommitted) |

## 6. Decisions & constraints (recorded)

- **Erode OSM bbox**: lat 11.02–11.96, lon 76.83–77.94 — guard for all
  geocoding/refresh.
- **Bharat Atlas** `lgd_villages` (2024, CC0-1.0) is the geocoding source of
  record; Bhuvan only pursued if it adds geometry beyond LGD centroids.
- **Open-Meteo archive hourly** is rate-limited (429) — respect quotas; four
  tail villages (Kanakampalayam, Chellipalayam, Kuhalur, Modakurichi) are
  ERA5-missing until quota resets; they already have forecast + NASA POWER.
- **IMD**: no keyless endpoint; document unavailability instead of faking.
- **data.gov.in** needs a free key via `DATA_GOV_API_KEY` env — never committed.
- **Population baseline**: Census 2011 is the legal/official baseline; newer
  village-level figures would need a verified official source — not fabricated.
- **Demo rows** are excluded from real analysis (`is_demo=False` default).
- **Frontend map is Leaflet**; the brief's "MapLibre" wording is acknowledged
  and rejected — keep the existing map library, add provenance to markers.