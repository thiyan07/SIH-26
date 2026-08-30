# GramBiz AI — Architecture

**Problem Statement ID:** 26091
**Product:** GramBiz AI — Hyper-Local Business Intelligence & Financial Advisory for Rural Entrepreneurs

## 1. System Overview

GramBiz AI is a monorepo containing a FastAPI backend, React frontend, shared
TypeScript/Python engines, and a PostgreSQL/PostGIS/pgvector database. The
system turns geospatial + statistical + financial evidence into an
explainable, confidence-aware business recommendation for rural micro-
entrepreneurs.

The core architectural principle:

> **Deterministic engines compute all numbers. The LLM only explains them.**

## 2. High-Level Data Flow

```
User input (location, capital, category)
        │
        ▼
[Deterministic Layer] ──► PostgreSQL + PostGIS + pgvector
  • Geocoding / location lookup
  • Nearby & competitor queries (PostGIS radius)
  • Demographic / market / price retrieval (with provenance)
  • Opportunity scoring engine
  • Financial engine (project cost, loan, scheme, EMI, coverage)
  • Business profit simulator
        │  structured evidence (JSON)
        ▼
[AI Layer] — LLM (provider-agnostic) + RAG over official docs
  • SWOT, opportunity/risk explanation, strategy
  • Feasibility report generation
  • Multilingual (Tamil/Hindi) rendering of explanations
        │
        ▼
[Frontend] — React + TS + Tailwind + shadcn/ui + MapCN (MapLibre)
```

The AI layer **never** performs financial, demographic, distance, or
competition calculations. It only receives pre-computed structured evidence
and is instructed to use exclusively that evidence.

## 3. Module Map

| Layer | Component | Responsibility |
|-------|-----------|----------------|
| API | `apps/api/app/main.py` | FastAPI app, routers, middleware |
| API | `apps/api/app/api/` | Endpoint routers per domain |
| Domain | `apps/api/app/services/` | Orchestration services |
| Domain | `apps/api/app/providers/` | Replaceable data providers (interfaces) |
| Domain | `apps/api/app/engines/score.py` | Opportunity + confidence scoring |
| Domain | `apps/api/app/engines/finance.py` | Financial structuring (deterministic) |
| Domain | `apps/api/app/engines/schemes.py` | Scheme router rule engine |
| Domain | `apps/api/app/engines/repayment.py` | EMI / moratorium / coverage |
| Domain | `apps/api/app/engines/profit.py` | Category business profit models |
| Domain | `apps/api/app/ai/` | LLM abstraction + RAG + prompt builder |
| Data | `apps/api/app/db/` | SQLAlchemy models, session |
| Data | `apps/api/app/geo.py` | PostGIS query helpers |
| Data | `scripts/ingest_*` | Repeatable ingestion pipelines |
| DB | PostgreSQL 18 | Primary store |
| DB | PostGIS | Geometry, radius, distance, density |
| DB | pgvector | RAG embeddings |
| Web | `apps/web/src/` | React pages & components |

## 4. Provider Architecture

All external data access goes through interface classes so providers are
replaceable and demo/mock providers stay isolated behind an `is_demo` flag.

```
LocationDataProvider
BusinessDataProvider
PopulationDataProvider
MarketPriceDataProvider
WeatherDataProvider
GovernmentSchemeProvider
InfrastructureProvider
```

Each provider returns provenance-bearing records:
`source_name, source_url, dataset_name, source_type, reference_date,
retrieved_at, geographic_level, confidence, methodology, is_estimate`.

## 5. Geospatial Design

- PostGIS geometry columns (`geography(Point, 4326)`) for accurate distance.
- All distance/radius/density queries run in SQL, not frontend JS.
- OSM data is **ingested → normalized → stored → timestamped**, then served
  from PostGIS. No live OSM calls per dashboard view.
- `app/geo.py` auto-selects the index-backed PostGIS `ST_DWithin` radius path
  when the extension and the table's `geom` column are present; when PostGIS
  is unavailable (e.g. sandbox), a pure-SQL haversine fallback returns
  equivalent results. Production (docker-compose) always enables PostGIS.

## 6. MapCN / MapLibre

```
MapCN components
   └─► MapLibre GL
         └─► Map tiles/style provider (env-configured: MAP_STYLE_URL)

Our backend ──► GeoJSON ──► competitor/business/location layers
```

- Frontend renders **GeoJSON/WebGL layers and clustering** for large business
  sets rather than hundreds of DOM markers.
- Tiles come from an environment-configured style URL; no hard-coded keys.
- Whenever OSM-derived data/map is shown: **© OpenStreetMap contributors**
  (ODbL attribution).

## 7. AI / RAG

- **LLM abstraction** (`apps/api/app/ai/llm.py`): a single interface with an
  in-memory deterministic mock + a vendored provider (e.g. OpenAI-compatible)
  selected by `LLM_PROVIDER` / `LLM_API_KEY`.
- **Structured evidence context**: deterministic engines produce a JSON blob
  (location, population, competition, market, accessibility, weather,
  opportunity_score, financial_plan, profit_model, risks, data_sources) that is
  injected into the prompt.
- **RAG pipeline**: document → extract → chunk → embed → pgvector → retrieve →
  LLM. Every retrieved answer carries citation/source metadata.
- Multilingual: structured data stays language-independent (codes/numbers);
  only presentation/AI strings are translated. English + Tamil are functional,
  Hindi is architected.

## 8. Data Integrity

- No fabricated official statistics. Missing data is marked
  unavailable/estimated/proxy with source, reference date, retrieved date,
  confidence, and limitation.
- Census 2011 is stored as `census_year=2011` and is always labelled a
  historical baseline, never current population.
- A `data_sources` table and per-record provenance allow a full data-provenance
  UI and freshness dashboard.
- Demo seed data is flagged `is_demo=True` and never presented as official.

## 9. Security

- Pydantic input validation on every endpoint.
- Rate limiting middleware.
- API keys only via environment variables; never committed, never returned.
- Parameterized SQL (SQLAlchemy ORM / bound params).
- CORS restricted to configured origins.
- Error sanitization: internal details never leak to clients.
