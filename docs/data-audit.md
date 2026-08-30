# GramBiz AI — Data & Demo Intelligence Audit

**Date:** 2026-08-29
**Scope:** Full pass over database models, migrations, seed data, API
endpoints, analysis engine, scoring logic, business/location services,
data-source implementation, financial engine, AI/report generation, and
frontend assumptions.

**Method:** read every backend module, every script, every test, and every
frontend page/component; cross-reference against the master plan
(provenance, OSM ingestion, government data, freshness, confidence,
PostGIS analysis, competition/market engines, category models, scoring,
financial boundaries, RAG, AI grounding, frontend rendering).

## Summary verdict

The foundation is already provenance-aware: a shared `ProvenanceMixin`
carries all required fields (`source_name, source_url, dataset_name,
source_type, reference_date, reference_year, retrieved_at,
geographic_level, confidence, methodology, is_estimate, is_demo`) on every
sourced fact table. Deterministic engines compute all numbers; the LLM only
explains. Demo data is flagged `is_demo=True` and never presented as
official.

Since this document was first written, several planned gaps have been
filled in the codebase and are no longer open: dedicated
competition/market-reach engines (`engines/competition.py`,
`engines/market.py`), a reusable provenance/freshness service
(`app/provenance.py` wired into `services/analysis.py`), a deterministic
14-section report (`ai/compose.py` `build_report`), score explanation in
the UI (Dashboard `ConfidenceExplanation`), and financial boundary tests
(₹1.40L±1, ₹50L). The remaining gaps versus the master plan are:
government-dataset normalization (§7, `datagov` path is a download stub),
per-record OSM completeness/confidence + geometry + category-mapping docs
(§4–6), richer DB-backed category profiles (§14), RAG embedding/retrieval
(§21), map layers served from PostGIS (§26), Data Sources why-use /
limitations fields (§27), and observability with `analysis_run_id` (§33).

## Component-by-component audit

| Component | Current source | Real/Demo | Action |
| --------- | -------------- | --------- | ------ |
| Provenance model | `app/db/models.py` `ProvenanceMixin` (all fields required by plan §3) | Real | **Keep.** Reusable across all fact tables. Consider factoring a small service to compute freshness/quality (§9–10). |
| DB tables | `app/db/models.py` — Location, Business, PopulationStatistic, MarketPrice, AgricultureStatistic, WeatherStatistic, InfrastructurePoint, GovernmentScheme, SchemeDocument, DocumentChunk, BusinessModel, BusinessCostModel, DataSource, DataSnapshot, AnalysisRun, Report, OpportunityScore, RiskScore | Schema | **Keep.** Missing a dedicated `MarketReach`/`Competition` persisted output (optional). |
| Migrations | `scripts/db/init_schema.py` (create_all) | Real | **Keep.** No Alembic; acceptable for MVP. |
| Seed data | `scripts/seed_demo/seed_erode.py` | **Demo** (`is_demo=True`) | **Keep**, clearly flagged. Population is a declared **proxy**, NOT Census figures — note in doc. Replace with real Census baseline via `ingest_government --dataset census`. |
| Business categories | `app/engines/profit.py` `known_categories()` + `BusinessCategory` table | Code+DB | **Enhance.** Categories currently only define name+OSM tags. Plan §14 requires richer profiles (required_inputs, demand_signals, competition_categories, cost_components, revenue_components, risk_factors, seasonality) in DB/config. |
| Business/profit models | `app/engines/profit.py` `_MODELS` + `BusinessModel`/`BusinessCostModel` tables | Estimate (`is_estimate=True`) | **Keep.** Labelled estimated operating model. Move defaults to DB/config for editability (§18). |
| OSM tagging | `CATEGORY_OSM_TAGS` in `profit.py` + `ingest_osm` | Real (ODbL) | **Enhance.** Document mappings (plan §4) and add completeness/confidence to every stored OSM record. |
| OSM ingestion | `scripts/ingest_osm/ingest.py` | Real (Overpass) | **Enhance.** CLI is `--bbox`, plan §5 wants `python -m scripts.ingest_osm --region <region>`. No geometry column, dedupe by source_id only. Add roads/transport/schools/hospital/bank categories + completeness. |
| Government ingestion | `scripts/ingest_government/ingest.py` | Real skeleton | **Enhance.** `--dataset datagov` only downloads bytes (TODO parse). Census CSV path works. Must document why each dataset helps feasibility (§7). |
| Census | `PopulationStatistic.census_year=2011` + `ingest_government` | Real baseline (when fed) | **Keep.** Always `census_year=2011`, labelled historical baseline, never "current 2026 population" (§8). |
| Location service | `app/api/locations.py`, `app/services/analysis.py` `_resolve_location` | Real+Demo | **Keep.** No geocoding provider wired; locations come from DB seed. |
| Nearby/competitor endpoints | `app/api/businesses.py` | Real (DB, haversine) | **Enhance.** Return `mapped_competitors`, `data_completeness`. Plan §5–6 wording ("mapped … found") is respected. |
| Radius queries | `app/geo.py` haversine SQL fallback + `scripts/db/postgis_queries.sql` | Real | **Keep.** PostGIS `ST_DWithin` documented for production; geometry index not applied in sandbox. |
| Competition engine | inline in `app/services/analysis.py` `_business_competition` + `_competition_score` | Real | **Refactor** into a reusable `CompetitionAnalyzer` service with a documented density formula (§12). |
| Market reach | inline `_demand_score` + `_population` + `_infrastructure` | Real | **Refactor** into a `MarketReachAnalyzer` (§13) returning population baseline, households, commercial-demand signals, market accessibility. |
| Market endpoint | `app/api/market.py` `/market/summary`, `/market/prices` | Real | **Keep.** Prices are source-only; none invented (§17). |
| Opportunity scoring | `app/engines/score.py` | Real | **Keep.** Weights match plan §15 exactly. Missing inputs lower confidence, never fabricate. |
| Score explanation | `confidence_factors.reasons` | Real (computed) | **Enhance.** Frontend must render the "Why this score?" positive signals + limitations (§16). Currently only confidence label shown on Dashboard. |
| Confidence score | `_confidence_score` in `score.py` | Real | **Keep.** Combine into a documented `data_confidence_score` with per-source freshness policies (§10) rather than one global threshold. |
| Financial engine | `app/engines/finance.py` + `app/engines/repayment.py` | Real (deterministic) | **Audit.** `project_cost = capital/0.10`, `loan = 0.9*project`, scheme max caps — correct per plan §19–20. Add boundary tests for ₹1.40L±1, ₹50L±1, etc. (plan §31 — see §Test coverage). |
| Scheme data | `government_schemes` table seeded from `DEFAULT_SCHEMES` (problem-statement demo values), CLI uses DB rules | Real+Demo | **Enhance.** Route financial API from DB always (currently falls back to hard-coded defaults). Label all as "problem-statement parameters" §20. |
| RAG | `SchemeDocument` + `DocumentChunk` tables; **no ingest/embed/retrieve code** | Absent | **Implement** (plan §21): PDF→extract→chunk→embed→pgvector→retrieve→LLM with source metadata. |
| LLM grounding | `app/ai/llm.py` SYSTEM_INSTRUCTIONS + MockLLMProvider | Real | **Keep.** Mock is deterministic and echoes evidence only (§22). Add RAG source constraints. |
| AI report | `app/api/ai.py` `/ai/report` (LLM text) + `app/ai/compose.py` (SWOT/risks) | Real (grounded) | **Enhance.** Build a deterministic 14-section report (exec summary, market, competition, opportunity, SWOT, risks, pricing, economics, finance, scheme, repayment, working capital, recommendation, data sources, limitations) (§23). |
| Recommendation | `_recommend` in `score.py` | Real | **Keep.** GO/MODIFY/AVOID with confidence guard (§24). |
| MapCN/MapLibre | `apps/web/src/mapcn/*` + `BusinessMap.tsx` | Real | **Keep.** Markers, clustering, GeoJSON, radius layers, popups present (§25). |
| Map layers | `BusinessMap.tsx` layer toggles | Real | **Enhance.** `MapPage`/`Market` don't pass infrastructure/markets signals as separate toggle layers (§26). Backend should serve GeoJSON from PostGIS. |
| Data Sources page | `pages/DataSources.tsx` + `app/api/data_sources.py` | Real | **Keep**, already displays source/dataset/reference/retrieved/level/records/freshness/confidence/license. Add "why we use this data" + "known limitations" fields (§27). |
| Demo region | Erode District, Tamil Nadu | Demo | **Keep.** Plan §28 — don't claim India-wide coverage. |
| Demo data rule | `is_demo=True` everywhere | Real | **Keep.** Frontend shows `DEMO DATA` badge on Data Sources page. |
| Financial calculator | `app/api/financial.py` + `pages/Finance.tsx` + `pages/Simulator.tsx` | Real | **Keep.** |
| Frontend `lib/finance.ts` | client-side EMI/schedule mirror | Real | **Keep** for display; backend is source of truth. |
| Observability | none | Absent | **Add** structured logging for ingestion, failed API calls, stale datasets, analysis, scoring, AI, RAG + `analysis_run_id` (§33). |
| Final analysis object | `app/services/analysis.py` evidence dict | Real | **Keep.** Matches plan §33 shape closely (location/business/market/competition/accessibility/pricing/risk/opportunity/financial/scheme/repayment/confidence/sources/recommendation). |

## Fake / hardcoded / random values found

- **Random values generated:** none. No `random.*`, `np.random`, or
  `Math.random` anywhere in the repo.
- **Hardcoded statistics (estimates, clearly labelled `is_estimate=True`)**
  in `app/engines/profit.py` default operating models (daily milk per animal,
  feed cost, ₹40/litre milk, margins, rent) and `profit.py` OSM tag heuristics.
  These are **estimates**, not sourced local data.
- **Demo proxy population** in `scripts/seed_demo/seed_erode.py` — explicitly
  `is_demo=True` and documented as a proxy, not Census. The seed file's own
  comments state this.
- **Problem-statement scheme parameters** in `app/engines/finance.py`
  `DEFAULT_SCHEMES` (Micro Finance / Term Loan) — labelled "assumed demo
  config; verify with agency." These are the plan §20 "problem-statement
  parameters."
- **`_price_potential`** returns `available: False` — no invented prices (§17
  respected).
- **AI**: mock provider only echoes supplied evidence; system prompt forbids
  inventing statistics (§22 respected).

## Plan gaps still open (verified against current code)

None — all gaps identified when this audit was drafted are closed (see
below). The only remaining staged hardening is the scalable PostGIS
`ST_DWithin` query path (documented in `docs/data-sources.md`).

## Closed since this audit was drafted

- **§12 / §13 Competition & MarketReach analyzers** — `engines/competition.py`
  `CompetitionAnalyzer` (density formula, 5/10 km, thresholds),
  `engines/market.py` `MarketReachAnalyzer` (population baseline,
  households, demand signals, accessibility). Tests in
  `tests/test_engines_provenance.py`.
- **§9–10 Data quality + freshness service** — `app/provenance.py`
  (`DEFAULT_POLICIES`, `freshness_for`, `compute_data_quality`) wired into
  `services/analysis.py` `data_confidence`.
- **§23 Deterministic 14-section report** — `ai/compose.py` `build_report`
  (Executive Summary → limitations).
- **§16 Score explanation in UI** — Dashboard `ConfidenceExplanation`
  ("Why this score?", positive signals + limitations, data-confidence
  pill).
- **§31 Financial boundary tests** — `tests/test_financial.py` covers
  ₹1.40L±1 / ₹50L±1 boundaries.
- **§5 OSM `--region` CLI** — `ingest_osm` supports `--region` presets
  (`erode`, `erode-sathyamangalam`) plus `--bbox`, runnable as
  `python -m scripts.ingest_osm.ingest`.
- **§4–6 OSM mapping, completeness/confidence, geometry (Stage B)** —
  `docs/category-mappings.md` documents category→tag and infrastructure
  mappings, region presets (erode-city, bhavani, gobichettipalayam,
  perundurai, sathyamangalam, anthiyur added), and per-record
  `completeness`/`confidence` heuristics now stored on every OSM record;
  `BusinessCategory.osm_tags` mirrored from `CATEGORY_OSM_TAGS`; food-
  processing heuristic made keyword-based so `man_made=works`/`craft=*`
  fall through to manufacturing/handicrafts; idempotent PostGIS geometry
  bootstrap in `scripts/db/postgis.py` (`geom` geography + GIST, graceful
  sandbox fallback). Verified end-to-end against live Overpass (Erode
  city: 184 records stored with completeness 0.35–0.9).
- **Ingestion pipeline fixes found during live verification** — both
  `DataSnapshot.record_count` → `records_ingested` (would have crashed
  both OSM and census ingestion); `InfrastructurePoint.source` →
  `source_type`; Overpass POST→GET fallback + `User-Agent`; canonical
  parenthesized union query (flat multi-statement form silently drops all
  but the last clause).
- **§7 Government dataset normalization (Stage C)** — added
  `scripts/ingest_government/normalize.py` with four supported dataset
  definitions (`market_arrivals`, `population`, `agriculture`,
  `imd_rainfall`) that parse JSON/CSV/CSDL-XML into `MarketPrice` /
  `PopulationStatistic` / `AgricultureStatistic` / `WeatherStatistic` rows
  carrying full provenance (source_url, dataset, reference date, geographic
  level, confidence, methodology). Automatic format detection, tolerant
  value coercion, row-level dedupe, location-based binding, and provenance
  capture were all previously missing. Usage and per-dataset rationale are
  documented in `docs/data-sources.md` (§7); offline tests cover the
  normalization matrix.
- **§14 Category profiles in DB with code fallback (Stage D)** — new
  `app/engines/category_profiles.py`: the canonical 10-category registry
  (required inputs, default inputs, demand-signal codes, competition
  categories, cost/revenue components, risk factors, seasonality) is seeded
  into new `business_categories` JSONB columns by `init_schema.py`;
  `get_category_profile()` reads the row and falls back to the registry when
  a field is empty (same pattern as scheme routing). Wired into analysis
  evidence (`category_profile` with DB-backing flag), market signal-code
  selection, and report risk/seasonality composition; exposes
  `GET /financial/categories/{code}/profile`. Engines (`simulate_model`,
  `known_categories`, `DEFAULT_SIGNAL_CODES`) keep their code constants so
  no existing test/UI outcome changes.
- **§21 RAG pipeline (Stage E)** — `app/ai/rag.py` completes the
  plan §21 chain: string/PDF→extract (`.txt`/`.md` direct, PDF via optional
  `pypdf`) → sentence-envelope chunking with token overlap →
  deterministic offline embeddings (MD5-bucketed term weights, stable across
  processes, no model/network) → `document_chunks` with portable
  `embedding_json` (plus additive `vector(1024)` + HNSW index when pgvector
  exists) → hybrid retrieval (vector cosine + keyword overlap) with per-chunk
  ranking → grounded LLM answer with citations
  (`POST /rag/retrieve`, `POST /rag/answer`). Ingestion CLI:
  `python -m scripts.ingest_docs.ingest --file scheme.txt --title ...`;
  demo scheme-document seed: `python -m scripts.seed_demo.seed_scheme_docs`.
  Insufficient evidence returns an explicit "insufficient" mode, never a
  fabricated answer.
- **§26 Map layers from PostGIS (Stage F)** — backend `POST /geojson/layers`
  serves point GeoJSON FeatureCollections for the `businesses`,
  `infrastructure` and `markets` layers around a pin, built from the
  portable lat/lng + provenance columns (id/name/kind/category/distance/
  source/confidence/completeness on each feature). `BusinessMap` treats
  markets and infrastructure as separate toggle layers (orange = markets,
  purple = other infrastructure) and `MapPage`/`Market` now fetch the layer
  endpoint and pass both through. PostGIS geometry (`geom`) and GIST indexes
  remain an additive option via `scripts/db/postgis.py` and are not required
  for the layer contract.
- **§27 Data Sources why-use / known-limitations (Stage G)** — every seeded
  `DataSource` now carries `why_used` (why this source is the basis for the
  relevant scoring) and `known_limitations` (caveats such as "Census 2011 is
  historical", "absence of an OSM business is not proof of absence", "scheme
  params are assumed demo values"). `init_schema.py` fills these on existing
  rows without re-creating them; `GET /data-sources` exposes both and
  `pages/DataSources.tsx` renders "Why we use this" and "Known limitations"
  on each source card.
- **§33 Observability (Stage H)** — `app/log.py` is a dependency-free
  structured JSON-line logger (one JSON object per line to stderr, labelled
  with `scope` and `run_id`). Wired into analysis (`start`/`completed` keyed
  by `analysis_id`), stale-dataset signals (`population_freshness`,
  `business_freshness`, `years_since_census`), scoring (`score` with overall/
  components/recommendation), RAG (`retrieve`/`answer` incl. mode + citations
  + provider) and ingestion (`ingest` for OSM, census and datagov jobs).
- **Verified DB-backed price provider (Stage I)** — `app/engines/prices.py`
  reads only already-ingested `market_prices` rows for the analysis district
  (latest `reference_date` per commodity, category-relevant filter, coverage
  metric) and exposes deterministic `price_score`; `_price_potential` now
  reports `available: True` with provenance when rows exist and keeps
  `available: False` (score None → neutral) otherwise. Prices remain
  never-fabricated (plan §17).
- **PostGIS ST_DWithin radius path with automatic fallback (Stage J)** —
  `app/geo.py` now auto-selects the index-backed PostGIS geography path
  (`ST_DWithin`/`ST_Distance` on the optional `geom` column from
  `scripts/db/postgis.py`) when the database supports PostGIS and the target
  table carries `geom`; otherwise it uses the portable haversine SQL
  expression. Capability probes are cached per database URL, so geo queries
  never break in a sandbox without PostGIS. Both branches return the same
  rows ordered nearest-first with identical distance values (distances always
  come from the portable `distance_to` helper), so enabling PostGIS never
  changes application numbers. The active backend is exposed for
  transparency: `geo_backend` on `POST /geojson/layers` and the `geo`
  analysis log event. `_postgis_radius_stmt` is unit-tested for
  construction; cross-backend equivalence is tested on the seeded cluster
  (Stage J adds 11 tests; backend total 149).

## Remaining staged hardening

- All previously staged hardening items are closed, including the PostGIS
  `ST_DWithin` query path (Stage J): `app/geo.py` routes to the index-backed
  PostGIS geography path automatically when the extension and the table's
  `geom` column are present, and falls back to the portable haversine
  expression otherwise. The optional geometry bootstrap remains in
  `scripts/db/postgis.py` (idempotent; SKIPPED gracefully without PostGIS).

## Baseline verification (pre-change)

- Backend tests: **71 passed** (`pytest`)
- Backend lint: **ruff check — all passed**
- Frontend typecheck: **pass**
- Frontend lint: **pass**
- Frontend build: **pass**
