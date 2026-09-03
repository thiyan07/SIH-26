# GramBiz AI

**Know Your Market Before You Take the Loan.**

AI-driven, evidence-based, hyper-local business feasibility & financial structuring
platform for rural micro-entrepreneurs. A build for the Smart India Hackathon
(Problem Statement ID 26091).

## What it does

Given a village location, available capital and a target business category, GramBiz AI:

1. Pins the location and maps nearby businesses (© OpenStreetMap, cached locally).
2. Computes local demand, competition, accessibility and price indicators.
3. Produces a **transparent opportunity score** with data provenance & confidence level.
4. Builds a **financial plan**: project cost, bank loan, scheme routing (Micro Finance / Term Loan), EMI.
5. Simulates profit and **repayment health** with what-if scenarios.
6. Outputs a **GO / MODIFY / AVOID** recommendation grounded in evidence.

**Architecture principle:** all numbers are computed by deterministic engines
(`app/engines/*`). The AI layer only *explains* engine output — it never fabricates
statistics. Historical baselines (e.g. Census 2011) are labelled, never presented as current.

## Monorepo layout

```
grambiz-ai/
├── apps/
│   ├── api/                  # FastAPI backend (Python)
│   │   ├── app/
│   │   │   ├── engines/      # deterministic finance / score / repayment / profit
│   │   │   ├── services/     # end-to-end analysis pipeline
│   │   │   ├── ai/           # LLM explainer (mock + OpenAI-compatible)
│   │   │   ├── api/          # routers
│   │   │   ├── db/           # SQLAlchemy models + session
│   │   │   └── geo.py        # portable haversine distance (non-PostGIS fallback)
│   │   ├── scripts/          # schema init, OSM/seed/government ingestion
│   │   └── tests/            # 294 tests (financial, ai, geospatial, e2e, NLP)
│   └── web/                  # React + TS + Vite + Tailwind + MapCN + Recharts
│       └── src/mapcn/        # MapCN: local MapLibre wrapper
└── docs/                     # architecture, data-sources, scoring-methodology, assumptions
```

## Quick start (dev)

### Backend (`apps/api`)

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e .          # or: pip install -r requirements

# set up the local PostgreSQL database (see docs/assumptions.md for the sandbox setup)
cp .env.example .env       # default: grambiz@/grambiz on local cluster, port 5433
python scripts/db/init_schema.py
python scripts/seed_demo/seed_erode.py     # demo data (is_demo=True) for Tamil Nadu
python scripts/ingest_osm/ingest.py        # cache OSM data locally
python scripts/ingest_government/ingest.py

uvicorn app.main:app --port 8000           # http://localhost:8000/docs
```

### Frontend (`apps/web`)

```bash
cd apps/web
npm install
npm run dev                # http://localhost:5173  (Vite proxies API -> :8000)
```

### Tests

```bash
cd apps/api && .venv/bin/python -m pytest -q      # backend: 45 passed
cd apps/api && .venv/bin/ruff check app scripts tests
cd apps/web && npm run typecheck && npm run lint && npm run build
```

## Demo flow

1. Open the web app → **Analyze My Business** → **Load a demo workspace (Perundurai, restaurant)**.
2. In the **Your Location** card you can also drag the pin on the map (or click the map)
   to set an **exact proposed shop location**, then **Confirm this location**. When
   confirmed, competitor/market/infrastructure queries run from that exact point
   (kept distinct from the selected admin area's centroid; unconfirmed, the centroid is used).
3. View the opportunity report on the **Dashboard** (score, confidence, GO/MODIFY/AVOID).
3. Explore **Market** (competitors map + prices), **Finance** (plan + EMI schedule),
   **Simulator** (loan what-if), **Report** (printable + AI narrative), **Schemes**,
   and **Data** (provenance).

> The demo usually runs on default "estimated" operating-model assumptions — outputs
> are estimates, not guaranteed profit. (The older dairy demo with default inputs
> yielded a negative operating profit and a High-Risk repayment label; the current
> restaurant demo yields a positive one.)

## Data & provenance

Mapped business/competitor data comes from © OpenStreetMap and may be incomplete.
Census 2011 is stored as a labelled baseline. Prices are only shown when sourced; none
are invented. Every number in a report carries its source, reference year and confidence.

Live (non-demo) integration is key-gated and fail-fast — see `docs/data-sources.md`,
`docs/LIVE-DATA-IMPLEMENTATION.md`, `docs/IMD.md` and `docs/REAL-DATA-AUDIT.md`:

- **data.gov.in runners** (`scripts/ingest_government/`): official market
  prices + IMD rainfall; exit 2 unless `DATA_GOV_API_KEY` (and a confirmed
  resource id) is configured. Real price rows are protected by a partial
  unique index, so re-ingests never duplicate.
- **Refresh CLI**: `python -m scripts.refresh.refresh_all [--only K --force --dry-run]`
  re-runs live jobs within their cooldowns.
- **Provider health UI**: the Data Sources page shows live state + freshness
  (from `GET /data-sources/status` and `/data-sources/providers`), and map
  popups mark demo/test points so real vs. demonstration data is always
  distinguishable.
- **Weather risk**: stored rows drive named flags (heat stress, drought,
  flood risk) into the risk score — no values are invented.

## Production notes

- `docker-compose.yml` uses a PostGIS/pgvector-enabled database for production.
  Radius queries in `app/geo.py` auto-select the PostGIS `ST_DWithin` path
  when the extension + `geom` column are present and otherwise use a portable
  haversine fallback (the sandbox environment lacks PostGIS/pgvector, so the
  fallback is active there). The Optional geometry bootstrap lives in
  `apps/api/scripts/db/postgis.py`; the production PostGIS queries are
  documented in `apps/api/scripts/db/postgis_queries.sql`.
- `LLM_PROVIDER=mock` by default; set `OPENAI_API_KEY` / provider env to use a real model
  (the LLM only explains engine-computed numbers).
- Security: analysis and map-layer POSTs are rate-limited (slowapi), and
  Swagger/OpenAPI are only served when `APP_ENV=development`.
- Set `DATA_GOV_API_KEY`, `DATA_GOV_MARKET_RESOURCE` and
  `IMD_RAINFALL_RESOURCE` in `.env` to enable the official runners (see
  `.env.example`). Never commit real keys.

> **Deployment readiness (current gap):** `docker-compose.yml` references
> `build: ./apps/api` and `build: ./apps/web`, but no `Dockerfile` exists in either
> app directory yet. For Vercel (web) + Render (managed PostGIS) deploy as planned,
> add these Dockerfiles (or platform build configs) plus the CI wiring; the codebase
> already reads env vars (`DATABASE_URL`, `VITE_API_URL`, `APP_ENV`, `CORS_ORIGINS`)
> and keeps docs/OpenAPI local-only outside `APP_ENV=development`.
