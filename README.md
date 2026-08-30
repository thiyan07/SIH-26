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
│   │   └── tests/            # 45 tests (financial, ai, geospatial, e2e)
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

1. Open the web app → **Analyze My Business** → **Load a demo workspace (Erode, dairy)**.
2. View the opportunity report on the **Dashboard** (score, confidence, GO/MODIFY/AVOID).
3. Explore **Market** (competitors map + prices), **Finance** (plan + EMI schedule),
   **Simulator** (loan what-if), **Report** (printable + AI narrative), **Schemes**,
   and **Data** (provenance).

> The demo dairy model with default inputs yields a negative operating profit and thus
> a High-Risk repayment label by design — an honest "estimated operating model".

## Data & provenance

Mapped business/competitor data comes from © OpenStreetMap and may be incomplete.
Census 2011 is stored as a labelled baseline. Prices are only shown when sourced; none
are invented. Every number in a report carries its source, reference year and confidence.

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
