# GramBiz AI — Real Data Audit (2026-08-30)

**Scope:** Does GramBiz AI actually use **real, verified data end-to-end**
(OSM, Census, government data, market prices, schemes, RAG, scoring, AI)?
This is a read-only audit. Objective evidence is produced below; nothing in
this document should be read as "the system is fine".

**Method:** read the backend/scripts/engines/AI code **and** interrogate the
live running system (PostgreSQL on `localhost:5432`, FastAPI on `:8000`),
then trace every data source to what is really present vs. what is only
code/plans.

---

## Update: DB provisioned after audit (2026-08-30, same session)

After the read-only audit, with user approval the #1 blocker was fixed:
a working sandbox PostgreSQL cluster was provisioned **as the current user**
(docker is not installed and sudo needs a password, so an OTL user-owned
cluster was the only viable path):

- `initdb` a fresh cluster at `.pgdata` (user `thiyan`, superuser role
  `grambiz`, `trust` auth, port **5433**, listening on `127.0.0.1`).
- Created the `grambiz` database; ran `init_schema.py` → **21 tables**
  created (PostGIS/pgvector absent, so the designed JSONB/haversine
  fallbacks are active; pgvector gracefully skipped).
- Seeded demo data: `seed_erode.py` + `seed_scheme_docs.py`.
- Restarted the API with `DATABASE_URL` → sandbox; **endpoints that were
  returning 500 now return data.**

Live row counts (after demo seed; all seeded businesses/locations/
population/infrastructure are `is_demo=True`; schemes are demo-parameterised):

| Table | Rows |
| ----- | ---- |
| businesses | 14 (demo) |
| locations | 3 (demo) |
| population_statistics | 3 (demo proxy) |
| infrastructure_points | 6 (demo) |
| government_schemes | 2 (demo params) |
| scheme_documents / document_chunks | 2 (demo) |
| market_prices / weather / agriculture | 0 |
| data_sources | 4 |

### Real OSM ingest (first real dataset loaded, same session)

Ran the real Overpass ingest for the **Erode district region presets**
(`python -m scripts.ingest_osm.ingest --region <preset>`) against the
sandbox DB (`overpass-api.de` reachable). Snapshots (records ingested /
errors):

| Job | Records | Errors |
| --- | ------- | ------ |
| osm_bhavani | 61 | 0 |
| osm_erode-city | 196 | 0 |
| osm_perundurai | 42 | 0 |
| osm_sathyamangalam | 10 | 0 |
| osm_gobichettipalayam | 54 | 0 |
| osm_anthiyur | 0 | 0 (sparse OSM coverage) |
| **Total** | **363** | **0** |

**Result (all `is_demo=False, source=osm`):**
- **21 real OSM businesses** (non-demo)
- **342 real OSM infrastructure points**: 271 hospital, 35 transport,
  23 bank, 12 school, 1 market
- 14 demo businesses + 6 demo infra remain separate (unchanged)

### Real OSM ingest BROADENED — `nwr` + more tags (same session)

The original query was **node-only**, so OSM objects mapped as polygons
(`way`) or relations were skipped — missing village shops that are drawn as
building outlines, plus cafes/fast-food/offices/clinics/hospitals/ATMs.
`_overpass_query` was rewritten to query **businesses/amenities as `nwr`**
(node+way+relation) with `out center` emitting a single center lat/lon for
ways, while **`highway` and `landuse=farmland` stay node-only** (querying them
as ways returns tens of thousands of road segments / farm polygons that flood
`infrastructure_points` and drown the shop signal).

Full Erode district bbox re-ingested with the broadened query
(`--bbox 11.20,77.30,11.85,77.90 --region erode`): **729 records, 0 errors**
(dedupe by `source_id` keeps earlier town rows intact).

**New totals (all `is_demo=False, source=osm`):**
- **774 real records** = **46 real businesses** + **728 real infrastructure**
- Real business categories: 27 restaurant, 13 textile, 4 grocery,
  1 food_processing, **1 dairy** (the dairy is a `way` polygon the old
  node-only query missed — direct proof broadened coverage works)
- Real businesses now exist **inside the district near Bhavani** (Closest:
  "Chinnus Cafe" food_processing 5.85 km; several restaurants ~7–12 km),
  so the analysis's `business_competition` reads real mapped rivals, not
  only the demo seed. Still no real dairy *at* the Bhavani demo point —
  category coverage is a property of OSM's actual mapping in the area.
- Refined query yield: 1,275 elements (1,150 node + 125 way), 782
  business-like vs 493 infra-like — no road/farmland flood.
- `nwr` change covered by tests: `tests/test_ingest_osm.py` 10/10 pass.
- The gobichettipalayam run exercised the designed **POST→GET Overpass
  fallback** (POST returned 504, GET succeeded — code works as intended).

Verified live: `/market/summary` returns `mapped_businesses_within_radius`
counts from the DB; the Bhavani analysis shows **real OSM infrastructure**
(`transport_points: 7`) and separating `OSM / real / medium` from the demo
population in `data_sources`. The overall score barely moved (82.7, conf
medium) because population is still the demo proxy and the real bbox added
no dairy businesses near Bhavani — expected.

**Refinement recommended (not yet done):** the `business_competition`
engine counts demo **and** real businesses together for
`mapped_competitors_5km`/density. For a fully honest competition read,
competitor/reach counts should be scoped to `is_demo=False` (real mapped
businesses), with demo shown separately or excluded from the score once
real data exists.

### Update: Perundurai + Thindal location data added (2026-08-30, later session)

Perundurai already had a demo Location + demo businesses; **Thindal (an Erode
suburb at the Thindal Murugan temple/Sakthi Nagar area ~11.32, 77.676) had no
Location at all** — it was not searchable and `/analysis` could not run for it.

Added (user-approved "full" scope):
- `seed_demo/seed_erode.py`: Thindal demo Location (block=village=Thindal,
  centroid), demo population proxy (10800, 2900 hh, is_demo=True), 4 demo
  businesses (dairy/grocery/restaurant/textile) and demo Thindal Market.
- `ingest_osm/ingest.py`: new `thindal` region preset bbox
  `11.28,77.64,11.36,77.72`.
- OSM ingest run for **perundurai** (57 records, 0 errors) and **thindal**
  (136 records, 0 errors); district-bbox dedupe by `source_id` meant no row
  duplication (businesses still 46 OSM / 18 demo; infra still 728 OSM / 7
  demo — Thindal's `transport` bus stop resolved to the real OSM point, so
  no demo duplicate was created).

Live verification: `/analysis` for **Thindal dairy** resolves the new
Location and returns `overall 82.7, recommendation GO, ` with nearest
competitor = demo "Thindal Murugan Dairy" (1 competitor within 5 km, demo)
and demo population correctly surfaced with `is_demo=true`. Perundurai dairy
also resolves and scores (82.7). All 164 tests still pass.

The `analysis`/AI **`data_sources` evidence mislabels demo proxy data**:
for the Bhavani run it reported `Census India … confidence high`,
`is_historical: true` — but the population actually came from the **demo
proxy** seed (`seed_demo_erode`, `is_demo=True`, 11300 / 3100 households),
**not** from real Census 2011. The report's "Data Sources" section then
showed "Census India … confidence high". This was the one place where the
code's otherwise-excellent honesty broke down: it overstated a demo proxy
as a high-confidence official Census source.

**FIXED (same session):**
- `app/services/analysis.py` `_population` now surfaces the row's provenance
  (`source_name`, `dataset_name`, `source_type`, `confidence`, `is_demo`).
- `_collect_data_sources` now reports a demo population as
  `is_demo=True` / `confidence low` with the note
  "Demo proxy population, NOT official Census figures." — only a genuine
  non-demo baseline is labelled "Census India / high".
- `any_demo` now flows into `data_confidence` (previously hardcoded `False`),
  so the demo-data honesty penalty is actually applied.
- `ai/compose.py` Pricing section now reads `evidence.get("price")` (was
  `"prices"` — a key mismatch that always forced "Unavailable").

Verified live after the fix: `data_sources` now returns
`"Demo seed (Erode) / seed_demo_erode / confidence low / is_demo: true"`,
the AI report shows "Demo seed (Erode) ref 2011 · confidence low", and
`data_confidence` dropped 29 → **17** (adds "Includes demo/proxy data").
Tests: **164 passed**; ruff clean.

### Update: Official Census 2011 population loaded — demo proxy replaced (same day, later)

Added a keyless real-data path: the **official Erode district government
portal** (`erode.nic.in/documents/census/`) hosts the DCHB, Town Panchayat and
Village Census 2011 PDFs on the s3waas CDN (no API key, no captcha).

- `scripts/ingest_government/scrape_erode_census.py` downloads the 3 PDFs to
  `data/raw/erode_census/`, extracts them (`pdftotext -layout`), and parses
  the DCHB Primary Census Abstract town lines (regex requires a decimal area;
  sanity-checks `males+females==population`; dedupes by base name). Output:
  - `data/processed/erode_census/erode_census_2011_towns.csv` — 58 town/CT rows
  - `data/processed/erode_census/erode_census_2011_promote.csv` — 4 focus rows
- `--promote` replaces the demo `PopulationStatistic` rows for the 4 focus
  Locations with **official Census 2011 figures**
  (`is_demo=False, source=Census India, confidence=high, is_estimate=False`),
  computes `sex_ratio`, registers the snapshot `census_erode_official`.

Official figures adopted (Erode district, 2011):

| Town | Population | Households | Male | Female | Sex ratio |
| ---- | ---------- | ---------- | ---- | ------ | --------- |
| Bhavani (M) | 39,225 | 11,147 | 19,559 | 19,666 | 1005.5 |
| Perundurai (TP) | 24,930 | 6,675 | 12,214 | 12,716 | 1041.1 |
| Sathyamangalam (M) | 37,816 | 11,148 | 18,848 | 18,968 | 1006.4 |
| Thindal (CT) | 15,440 | 4,256 | 7,671 | 7,769 | 1012.8 |

Verified live: `/analysis` Thindal dairy now resolves the Thindal Location and
returns `population 15,440, households 4,256, source_name=Census India,
confidence=high, is_demo=false, is_historical=true`. `population_census`
DataSource flag flipped `is_demo → false` in `init_schema.py`. Tests: **164
passed**; ruff clean.

### Update: All Census towns geocoded + Open-Meteo weather (same day, final)

Extended official Census 2011 coverage district-wide, plus real weather:

**Census → 38 of 55 towns now real (`is_demo=False`).**
- `scripts/ingest_government/geocode_erode_locations.py`: geocodes each DCHB
  town from OSM — an Overpass index of every named element in the true Erode
  district bbox (lat 11.02–11.96, lon 76.83–77.94) matched by normalized name,
  falling back to **Nominatim viewbox-bounded** search. Nominatim results are
  validated to resolve *within Erode* to reject same-named towns elsewhere in
  Tamil Nadu (Karur, Salem, Tenkasi collisions seen). Existing demo Locations
  (the 4 focus towns) are skipped; then `adopt_census_rows` spans all towns.
- 38/55 towns resolved to real coordinates (Overpass index or Nominatim),
  creating 34 new Locations (source=OSM, is_demo=False). **17 towns have no OSM
  coverage** (Appakudal, Modakurichi, Salangapalayam, … → listed in
  `data/processed/erode_census/erode_census_2011_unresolved.json`) and are
  deliberately **not** geocoded — no fabricated centroids.
- Live verification (Ammapettai, dairy): `population 9,677, households 2,758,
  is_demo=false, source=Census India`, Location 11.6198, 77.7426.

**Weather → 380 real rows (38 locations × 5 years × 2 indicators).**
- `scripts/ingest_government/ingest_openmeteo_weather.py`: keyless Open-Meteo
  archive API (ERA5 reanalysis), years 2020–2024, annual `rainfall` (mm) and
  `temperature` (degC) per Location, `is_demo=False`, `is_estimate=True`,
  methodology explicitly "Reanalysis, not IMD gridded station data".
- `_weather` in `/analysis` now returns `available:true` with provenance.

**Mandi prices remain BLOCKED (keyless).** All probed paths fail:
- `enam.gov.in` NAM service endpoints return its HTML app shell (session-gated),
  not the JSON the web UI uses.
- `agmarknet.nic.in` (and the CEDA agmarknet mirror) → unreachable (HTTP 000).
- data.gov.in resource downloads still need a free API key (400/403 without).

Tests: **164 passed**; ruff clean on all three ingest scripts.

### Live real-village run (Bhavani, dairy, ₹3,00,000)

- demand_score 100.0 from demo proxy population 11,300 (year 2011)
- competition_score 88/100 (mapped: 2 demo competitors, "GRT Milk", 0.17 km)
- price_score 50.0 (neutral — no market price rows: `prices: null`)
- financial_fit 73 (Term Loan; `source_document=Problem Statement 26091`)
- overall 82.7/100, confidence 44/medium, recommendation **GO**
- data_confidence **17/low** after the mislabel fix (old census, unknown
  freshness, centroid, medium coverage, 19% missing, + demo-data penalty)
  — the honest signal that this is *not* data you should lend on yet.

---

## Headline finding (read this first)

> **The application has no working database on this machine right now, so it
> cannot serve *any* data — neither real nor even its own demo seed data.**

- The configured DSN is `postgresql+psycopg://grambiz:grambiz@localhost:5432/grambiz`
  (`apps/api/app/config.py:15`). On the running PostgreSQL 18 system cluster
  (`/var/lib/postgresql/18/main`), **the `grambiz` role does not exist**.
  PostgreSQL logs state it explicitly:
  `FATAL: password authentication failed for user "grambiz" DETAIL: Role "grambiz" does not exist.`
- Every DB-backed endpoint returns **`500 Internal server error`**:
  - `GET /locations/search?q=bhavani` → 500
  - `GET /schemes` → 500
  - `GET /data-sources` → 500
  - (verified live against the running uvicorn on `:8000`)
- `docker` is **not installed**, so the docker-compose PostGIS + pgvector
  stack the project plans around cannot be running here.
- `.pgdata/` exists but is an **orphaned set of cluster data files with no
  `postgresql.conf`, no running process, and no socket** — it is not serving
  anything.
- `apps/api/app/main.py` never calls `init_db()` at startup; `ENGINE` is
  created lazily on first DB use. That is why uvicorn starts and `/health`
  returns `{"status":"ok"}` — the server is "up" in a way that is **not
  backed by any database**. `/health` performs no DB check.

**Consequence:** *Every number the app could ever produce is computed by
engines that read from a table that does not exist.* There is not one row of
OSM data, census baseline, market price, weather, scheme, or RAG document
that is queryable through the live application on this machine. The "real
village test" cannot be run to completion because the DB-backed path itself
is dead.

This does **not** mean the code is dishonest — the opposite. The code is
*lavishly honest* about provenance (see §"What the code does get right").
But honesty about data in the *code* is not the same as *having* the data.

---

## What is REAL end-to-end today?

**Much, and growing.** This machine now holds real, attributed rows for every
layer except live official pricing APIs and scheme financing params (below):

| Layer | Reality on this machine |
| ----- | ----------------------- |
| Database | **Provisioned sandbox (user-approved)** `.pgdata` on :5433, `grambiz` role, 21 tables, demo seed loaded. See *Update: DB provisioned* above. |
| OSM data | **REAL & live.** 774 real records (`source=osm, is_demo=False`) = 46 businesses + 728 infrastructure, broadened `nwr` query (ways/relations captured). Readable via API. |
| Census / govt data | **REAL & live: 145 official Census-2011 rows = 42 towns (DCHB) + 103 village panchayats** (erode.nic.in PDFs; OSM/Photon/relaxed-Nominatim geocoded Locations). 107 have DCHB households, 64 literacy (%), 26 workers — only from rows whose DCHB population EXACTLY matches the stored official figure (see DCHB profile below). Honest gaps: 132 villages/towns still ungeocoded (72 out-of-bbox near-misses logged for review), never fabricated. |
| Market prices | **REAL & live.** `engines/prices.py` reads ingested `market_prices` rows → **109 rows** (Erode APMC/Agmarknet tables from the public ACROP mirror, dated 19–30 Aug 2026, unit=quintal) → `available: True`, `confidence: medium`. Official keyless paths (e-NAM, agmarknet) are blocked; this is a daily-refreshed public aggregator. |
| Weather | **REAL & live.** **11,475 rows across all 145 locations** (Open-Meteo ERA5 annual 2020–24; NASA POWER MERRA-2 monthly for **2025**; Open-Meteo forecast current + 3-day). Reanalysis/forecast, not IMD. |
| Agriculture | **REAL & live.** `agriculture_statistics` → **1,202 rows** (TN Digital Crop Survey taluk-wise sown area, ha, for Erode: Summer 2025, Rabi 2024, Kharif 2025, `is_demo=False`). |
| Government schemes | Seeded from hardcoded `DEFAULT_SCHEMES` (demo params) — table now exists and `/financial` reads DB rows. |
| RAG | **REAL corpus.** `scheme_documents` = 2 official MoFPI documents (PMFME Operational Guidelines + revised ODOP list w/ Erode=Turmeric) → 37 chunks; demo docs removed. |
| Scoring / AI | Deterministic engines + mock LLM exist, but they compute *from* a missing DB. |

---

## Data-source-by-data-source audit

### 1. OSM / Overpass — REAL ingestion code, NO live data
- `scripts/ingest_osm/ingest.py` does contain a real Overpass API client
  (`overpass_url=https://overpass-api.de/api/interpreter`) with region
  presets for Erode district (Bhavani, Perundurai, Sathyamangalam), POST→GET
  fallback, `User-Agent`, and ODbL attribution.
- **But:** the only Copy of this project that exists lives in a Postgres
  that has no `grambiz` role. No Overpass records are persisted/queryable.
- The prior `docs/data-audit.md` claims "Erode city: 184 records stored …
  verified end-to-end against live Overpass". On **this** machine that data
  is not present in any reachable database, so the claim is not reproducible
  today. If those records lived in a Docker/other cluster, that cluster is
  not running here.
- `data.gov.in` and census CSV ingestion code exists but was never
  successfully loaded into a reachable DB here.

### 2. Census — REAL baseline *policy*, ZERO rows
- The code correctly insists population is the **historical 2011 Census**
  baseline, never "current". `population_statistics` carries
  `census_year=2011`.
- The only population records in the codebase are **demo proxies** in
  `scripts/seed_demo/seed_erode.py` (`is_demo=True, is_estimate=True,`
  `methodology="Clear demo illustration; replace with real ingestion."` and
  commented `Population values are proxies (not Census figures)`).
- Even those demo rows are not readable (no DB). So in practice: **population
  is neither real Census nor readable demo.**

### 3. Market prices — NEVER fabricated; now LOADED (daily mirror)
- `engines/prices.py` correctly returns `available: False` when there are no
  ingested rows and keeps the price score neutral (`None`).
- **Update: 109 real rows are now loaded** for Erode (see *new: live mandi
  prices* below), so grocery/dairy price evidence is `available: True` with
  `reference_date` = publication day and `confidence: medium`.
- The official keyless paths are genuinely blocked (e-NAM serves an HTML app
  shell, agmarknet.nic.in and the CEDA mirror are unreachable, data.gov.in
  needs a free API key), so the loaded rows come from the public ACROP mirror
  with provenance flagged as an aggregator.

### new: live mandi prices (ACROP mirror harvest)
- `scripts/ingest_government/ingest_mandi_live.py` fetches the public
  keyless page `acrop.app/prices/<commodity>/tamil-nadu/erode` for 25
  commodities and parses the per-market Modal/Min/Max table **verbatim**
  (market, ₹ values, unit token, reference date as published).
- 109 rows across 25 commodities (Turmeric, Paddy, Maize, Onion, Tomato,
  Potato, Green Chilli, Groundnut, Banana, Coconut, Ginger, Coriander,
  Brinjal, Cabbage, Beans, Okra, Carrot, Cauliflower, Beetroot, Cucumber,
  Cowpea, Amaranthus, Drumstick, Green Peas, Mango) over 6 Erode markets
  reported 19–30 Aug 2026; refreshed daily (idempotent upsert keyed on
  item+market+date).
- Caveat: aggregator mirror of APMC/Agmarknet/data.gov.in data, not the
  ministry API; unit normalised to quintal per the source page's labelling;
  Uzhavar Sandhai (retail) markets are included in the same table.

### 4. Weather — NO live data
- `weather_api_key=''`, `market_price_api_key=''`, `data_provider_keys=''`.
- The `imd_rainfall` normalizer exists as code; no rows are loadable.

### new: live / current weather (keyless)
- `scripts/ingest_government/ingest_weather_current.py` adds two keyless,
  free sources that the ERA5 annual import (2020-24) could not cover:
  - **NASA POWER monthly (MERRA-2)**: re-run for all **145 locations** × 12
    months × (temperature, temperature_min, temperature_max, humidity,
    rainfall) for **2025** — the current meteorological year. The monthly
    endpoint accepts year tokens only (`start=2025&end=2025`); data is
    available through the previous year. A `YYYYMM` sentinel key (`202513`)
    is skipped.
  - **Open-Meteo forecast**: all **145 locations** × (current temperature +
    current precipitation + 3-day forecast precipitation / temp max / temp
    min), surfaced as `current_temperature` etc. with `is_estimate=True`
    (model forecast).
  - Provenance for every drought/heat decision now has a 2025 + "today"
    layer over every geocoded village, not just a 2020-24 climatology over
    38 centroids.

### 5. Government schemes — HARDCODED demo parameters (DB now exists)
- `engines/finance.py` `DEFAULT_SCHEMES`:
  - **Micro Finance**: max_project_cost ₹1.40L, max_loan ₹1.25L, 6.5%, 3 yr,
    3 mo moratorium.
  - **Term Loan**: > ₹1.40L–₹50L.
  - These are still the demo rows present in `government_schemes`
    (`is_active=True`), so `/financial/calculate` returns them. Official
    scheme rows have **not** been seeded: adding a subsidy-only scheme
    (e.g. PMFME) would change the financial planner's fit and was intentionally
    deferred — scheme *guidance* is now answered through the RAG corpus instead.
- `GET /schemes` works (DB exists).

### 6. RAG — real official corpus now loaded
- `ai/rag.py` is a genuine, tested pipeline: extract → sentence chunking →
  **deterministic offline TF-hash embeddings (`tf_hash_v0`)** → hybrid cosine
  + keyword retrieval → grounded LLM answer with citations.
- **Important caveat:** the default embedding is an MD5 word-frequency hash
  (no model, no network). It is *keyword hashing*, not modern semantic
  embeddings, and retrieval works by linear scan over the whole table.
- **Update:** the demo corpus was removed and two official MoFPI documents
  were ingested via `scripts/ingest_government/ingest_scheme_docs.py`
  (downloads the upstream official PDF, extracts verbatim, reuses
  `store_document` for chunking/embeddings, patched provenance):
  - **PMFME Scheme Operational Guidelines** (credit-linked subsidy 35% of
    capital up to ₹10L for micro food-processing units) — 26 chunks.
  - **Revised ODOP list, 35 States/UTs, 13 Mar 2024** — Erode is assigned
    **"Turmeric based products"** — 11 chunks.
  - 37 chunks total; verification queries retrieve these documents with
    citations. `POST /rag/answer` → "grounded" mode (unless the question is
    outside the corpus → honest "insufficient").

### new: village-panchayat census (Census 2011, per Panchayat Union)
- `scripts/ingest_government/ingest_village_census.py` parses the official
  **"Village & Village Panchayat population by Panchayat Union"** PDF
  (2018062196.pdf, erode.nic.in) with `pdftotext -layout`.
- **Self-validating parse**: the parser must reproduce the publication's own
  ABSTRACT — 14 Panchayat Unions, 225 village panchayats, grand total
  population **11,30,722**, and males+females == population for every row —
  else it fails fast. Rows have no households column, so only
  population/males/females (+ derived sex_ratio) are stored.
- **72 villages** geocoded (OSM Overpass index, Nominatim viewbox fallback) →
  `Location` rows (block = Panchayat Union) + official population rows
  (`is_demo=False`, `confidence: high`). **150 villages unresolved** and written
  to `erode_census_2011_unresolved_villages.json` (no OSM coverage, coords
  never fabricated — `Location.latitude/longitude` are NOT NULL, so coordinates
  are mandatory). A same-name-as-town case (3) is skipped to avoid clobbering
  town rows; a village named identically to its union (`Talavadi`) was
  backfilled after a guard initially misfired.
- Data source `population_census_villages`; snapshot job `census_villages_erode`.

### new: re-geocode fallback pass (same day) — 35 more locations
- `scripts/ingest_government/regeocode_unresolved.py` retries the ~167 names
  OSM could not match, with two keyless fallbacks: a **relaxed Nominatim**
  (`q = "<name>, Erode, Tamil Nadu"`, `countrycodes=IN`) and **Photon** near
  the Erode centroid. A coordinate is auto-adopted ONLY when it lands strictly
  inside the official Erode OSM relation bbox (the same bbox the primary
  geocoder uses) — Photon hits additionally must carry a real place
  (`osm_value ∈ village|town|hamlet|suburb|locality`).
- **Result: 35 locations adopted (32 villages + 3 towns: Chellipalayam, Kuhalur,
  Modakurichi), each also adopting its official Census-2011 population row.**
  The far more numerous out-of-bbox matches (72) were NOT adopted — name
  collisions across Tamil Nadu are common (e.g. `Kesarimangalam`→Nagapattinam,
  `Appakudal`→Thanjavur, `Kalbavi`→Mangaluru) — and are logged to
  `erode_census_2011_nearmiss.json` for manual review.
- District totals after the pass: **145 Locations (42 town-style + 103 village),
  145 official population rows, 132 still unresolved** (written back to the
  `erode_census_2011_unresolved*.json` lists).

### new: DCHB village/town profile — households, literacy, workers
- `scripts/ingest_government/ingest_dchb_village_profile.py` parses the
  **"Village" Primary Census Abstract** inside the DCHB (2018062114.pdf,
  erode.nic.in) — per-settlement area, **households, literates, workers** —
  and enriches the 145 official Census-2011 rows.
- **Identity-first join**: every DCHB settlement row is a *revenue village*
  (often a different unit than a village panchayat of the same name) and town
  rows repeat across chapters. A DCHB row is adopted ONLY when its population
  **exactly equals the population already stored for that Location** (same
  settlement). Same-named-but-different rows (e.g. Bhavani village vs Bhavani
  (M); `Pudur` × 2) are skipped; literates/workers values are accepted only
  when all rows for a name agree on a **single distinct figure**. Nothing is
  overwritten — only missing households/literacy/workers/non_workers are set.
- Result: **107 rows with households, 64 with literacy %, 26 with workers**;
  zero sanity violations (literacy ∈ 0–100, workers ≤ population). Rerun after
  the re-geocode pass enriched the 35 new locations too (enriched=73 total,
  53 unchanged, 19 population-mismatched candidates reverted).
- **13 rows were invalidly enriched by the first (un-gated) run and were
  explicitly reverted to NULL** — e.g. `Talavadi` stored panchayat 17,631 vs
  DCHB revenue village 9,689; `Komarapalayam` 8,957 vs 2,489. The race
  condition that produced them (name-only match) is now structurally
  impossible: the identity gate requires population equality.
- **Known-coverage limitation (honest):** workers only reach 26/145 because
  the workers table's 9 numeric columns parse as a single line only when the
  village name is short; long names wrap across lines and are conservatively
  skipped (regexes kept strict to avoid misattribute). Literacy is dropped for
  names with genuinely conflicting figures across tables.
- Audit CSV `erode_dchb_village_profile.csv`; data source
  `population_census_dchb_profile`.

### new: agriculture statistics (TN Digital Crop Survey)
- `scripts/ingest_government/ingest_agriculture_stats.py` fetches the
  **keyless, official** Government of Tamil Nadu Digital Crop Survey table
  (`tnagrisnet.tn.gov.in/ARS/dcs/reportTalukWise/{sid}/Erode/Agriculture`)
  for the three seasons currently published: **Summer 2025, Rabi 2024,
  Kharif 2025**. Values are taluk-wise/`Total` district sown areas (ha),
  taken verbatim; `is_demo=False`, confidence medium (survey returns).
- **1,202 rows** written. Cross-verified per-cell against the rendered table
  (e.g. Anthiyur Rice (Paddy) 22.4 ha, Maize 828 ha, Sugarcane 3,328.2 ha,
  Kharif 2025). Idempotent upsert keyed on (level, crop, season, source).
- **Dropped honestly:** the TN Season & Crop Report 2024-25 PDFs
  (production/yield, tn.gov.in/crop/stat.htm) parse to rotated/reversed
  header artifacts that cannot be mapped to columns automatically; a
  prototype autoparser was built, audited, found untrustworthy (wrong crop
  names, misassigned seasons), its 53 rows deleted and the part-B code
  removed. Cached PDFs + finding remain documented in the script docstring.

### 7. Opportunity scoring — REAL deterministic engine, NO data inputs
- `engines/score.py` `DEFAULT_WEIGHTS`: demand .25, competition .20,
  accessibility .15, price .15, financial_fit .15, risk .10.
- Missing inputs **lower confidence instead of fabricating values** — good
  engineering. But with an empty DB the engine has *nothing* to weight; the
  score would be driven wholly by "no evidence" and a heavily degraded
  confidence, or the endpoint would 500 first.
- So: the opportunity score is **not** "real" in the sense of being
  computed on verified data — it is a deterministic formula waiting for data
  that never arrives.

### 8. Competition — "mapped" honesty, no data
- `engines/competition.py` reports `mapped_competitors_5km/10km`,
  `nearest_competitor_km`, `data_completeness`, and `competition_score`
  (80 if no mapped competitors; `clamp(100 - mapped*6)`). It labels counts
  as **mapped minimums**, never "actual" — correct.
- With no businesses table, mapped counts are always 0/absent.

### 9. AI / LLM — mock by default, grounded by design
- `llm_provider="mock"` default → `MockLLMProvider` **only echoes supplied
  evidence**; `SYSTEM_INSTRUCTIONS` forbid inventing statistics.
- A real OpenAI-compatible path exists but requires `LLM_API_KEY` (empty).
- `ai/compose.py` builds deterministic SWOT/risks/14-section report from
  evidence only; missing fields render as "Unavailable", never invented.
- **Design is genuinely sound on grounding.** It is disconnected from any
  live data, so the AI has nothing as-grounding to work with today.

---

## What the code gets RIGHT (do not lose this)

1. **Provenance everywhere.** Every fact table carries
   `source_name/source_url/dataset_name/source_type/reference_date/reference_year/
   geographic_level/confidence/is_estimate/is_demo/methodology` via a shared
   `ProvenanceMixin`.
2. **No hallucinations.** The default LLM is a deterministic mock; prompts
   and report text say "evidence insufficient" rather than guessing.
3. **No fabricated local prices.** Price score is neutral when data is
   absent.
4. **"Mapped" language** is used for OSM competitor counts with a
   completeness caveat baked into confidence.
5. **Demo vs official is explicitly separated** in code comments, seed
   scripts, and the UI's "DEMO DATA" badge.
6. **Confidence degrades, not fabricates**, when inputs are missing.

These are genuine strengths. They should be preserved. **They do not make an
empty database have data.**

---

## The 5 biggest gaps (brutal, ranked)

1. **No database exists on this machine.** `grambiz` role/db is not created;
   every DB-backed endpoint 500s. Nothing can work (real *or* demo) until the
   Postgres role+database+PostGIS (and optionally pgvector) are actually
   provisioned and `init_db`/schema are applied. **This is the #1 blocker and
   must be fixed before any data question matters.**
2. **No real dataset has been ingested and persisted** — not OSM, not
   Census 2011, not market arrivals, not IMD rainfall. The ingestion code
   exists but has produced no queryable rows on this machine. The prior
   audit's "184 OSM records" is not reproducible here.
3. **All current data is demo-by-design** (Erode proxy population, ~14 demo
   businesses, demo scheme docs, hardcoded `Problem Statement 26091` scheme
   params). None of it is official government policy or real Census figures.
4. **Embeddings are keyword-hash, not semantic.** `tf_hash_v0` gives
   deterministic offline retrieval but no meaning-aware matching; RAG is a
   fancy keyword search unless a real embedding model + pgvector is enabled.
5. **No live provider keys** (weather, market price, data providers) and no
   live LLM key — so the non-mock paths are unreachable by default.

---

## What is connected vs. planned

| Source | Connected (live rows loadable) | Planned / code-only / demo |
| ------ | ------------------------------ | -------------------------- |
| OSM Overpass | **Yes — 774 real rows** (46 biz + 728 infra) via broadened `nwr` query | More tags/regions can be added |
| Census 2011 | **Yes — 145 official rows** (42 towns + 103 village panchayats) via erode.nic.in DCHB PDFs; village rows additionally enriched from the DCHB Village PCA (107 households, 64 literacy, 26 workers, population-identity-gated); 35 more locations recovered by the Photon/relaxed-Nominatim fallback pass | 132 villages/towns lack OSM coords (listed in `erode_census_2011_unresolved*.json`, plus 72 bbox-safe near-misses in `erode_census_2011_nearmiss.json`); workers coverage limited by table row-wrapping; S&CR yield/production pages dropped (parse unreliable) |
| Weather | **Yes — 11,475 real rows** (Open-Meteo ERA5 annual 2020–24; NASA POWER MERRA-2 monthly **2025**; Open-Meteo forecast current + 3-day; **all 145 locations**) | Reanalysis/forecast, not IMD; Open-Meteo hourly rate-limit occasionally skips a location (ERA5 missing for a few tails); IMD needs key |
| data.gov.in market arrivals | **Yes — via public mirror** | 109 Erode rows dated 19–30 Aug 2026 harvested from the ACROP aggregator (APMC/Agmarknet via data.gov.in). Official keyless paths fail: e-NAM HTML shell, agmarknet.nic.in + CEDA unreachable, data.gov.in needs API key |
| IMD rainfall / weather | **No** | Code only; no key |
| Government schemes | **Yes — seeded** (demo params) | Real scheme *guidelines* now in RAG corpus; financing scheme rows not yet seeded (would change planner fit) |
| RAG corpus | **Yes — 2 official MoFPI documents / 37 chunks** | PMFME guidelines + revised ODOP list (Erode=Turmeric); embeddings are keyword-hash |
| Agricultural statistics | **Yes — 1,202 rows** (DCS taluk-wise sown area, ha; Summer 2025 / Rabi 2024 / Kharif 2025) | No production/yield yet (S&CR PDF parse unreliable — dropped); no agri engine consumer yet |
| LLM | **No** (mock default) | OpenAI path needs key |

---

## Answers to the core questions

- **Are OSM / govt data working?** OSM is **live**: 774 real rows
  (`is_demo=False, source=osm`) readable through the sandbox DB, with real
  businesses near Bhavani. Census is now **live for 145 towns+villages** via
  the official erode.nic.in DCHB PDFs, with village/town **households,
  literacy and workers** added from the DCHB Village PCA under a
  population-identity gate (official, never fabricated; ungeocoded
  settlements listed in `erode_census_2011_unresolved*.json`, out-of-bbox
  near-misses in `erode_census_2011_nearmiss.json`). Weather now covers
  **all 145 locations** (ERA5 2020–24 annual, NASA POWER 2025 monthly,
  Open-Meteo current + 3-day forecast). Market
  arrivals are now **live via a daily public mirror** (109 Erode rows, dated
  19–30 Aug 2026), since every official keyless path fails (e-NAM
  session-gated HTML, agmarknet.nic.in and the CEDA mirror unreachable) and
  data.gov.in needs a free API key.
- **Is the opportunity score real?** The *formula* is real (deterministic,
  documented, confidence-aware). OSM competitor/infrastructure inputs are now
  real; population is still the demo proxy, so the overall score is still
  partly demo-driven.
- **Is RAG working?** Yes, with a real corpus: 2 official MoFPI documents
  (PMFME Operational Guidelines; revised ODOP list where **Erode = Turmeric
  based products**), 37 chunks, grounded retrieval with citations; out-of-
  corpus questions honestly return the "insufficient" mode.
- **Is there real verified data end-to-end?** **Yes — multiple layers.** OSM
  (774 rows), Census 2011 (**145 locations**, official rows + DCHB
  households/literacy/workers), market prices (109 rows, ACROP mirror),
  weather (**11,475 rows across all 145 locations**), agriculture (1,202 rows
  DCS), and RAG (37 chunks) are
  all real, attributed rows in the provisioned DB. The official keyless gap
  remains production/yield statistics and IMD; demo proxies remain only for
  the financial scheme rows and the scoring population baseline edge cases.

**Bottom line:** the application is a well-engineered, unusually honest
*demo scaffold* that now runs on a provisioned sandbox DB with **multiple real
datasets loaded end-to-end** (OSM 774, Census 2011 for **145 locations**,
market prices 109, weather **11,475 rows / 145 locations**, agriculture 1,202,
RAG 37 chunks). Remaining demo/deferred:
financial scheme rows, live official pricing/IMD APIs, and production/yield
statistics.

---

## What to build next (priority order)

1. **Provision the DB.** ✔ **DONE** (see "Update" above). Sandbox cluster on
   `127.0.0.1:5433`; schema + demo seed loaded; endpoints return data.
   *(Next steps below now depend on loading real data, not on fixing 500s.)*
2. **Persist a real OSM ingest** for Erode — **DONE + broadened.** Full
   district `nwr` query → **774 real rows** (46 business + 728 infra,
   `is_demo=False, source=osm`), 0 errors, dedupe by `source_id`. Extend the
   tag set / `use_bbox` to other districts anytime with the same command.
3. **Load a real Census 2011 baseline / market arrivals / IMD rainfall.**
   Code is ready (`scripts/ingest_government`, 10/10 tests). **Blocker: a free
   data.gov.in API key.** Discovery `/lists` is keyless (HTTP 200) but
   resource downloads return 400/403 without a key. Two paths:
   - Get a free key at data.gov.in (register email, `X-API-KEY`) and run
     `python -m scripts.ingest_government.ingest --dataset datagov --def market_arrivals --url <resource-url>`.
   - Or download the real CSV with a browser/key and ingest from file:
     `--dataset datagov --def market_arrivals --file <real.csv>` (no key
     needed in the code path).
4. Once rows land in `population_statistics`/`market_prices`, the 
   `price_score`/weather/population evidence stops being "unavailable" and
   the Bhavani-style demo-vs-real split in `data_sources` becomes genuinely
   real.
5. **Replace demo scheme params + demo RAG docs** with real scheme
   guidelines (or explicitly keep them demo in a separate demo DB).
6. **Then** add configurable scheme routing from DB, real embedding/pgvector,
   and live LLM/weather/pricing key hooks **only after** real data exists to
   ground them.
7. **Prove it:** run a real-village analysis (e.g. Bhavani 11.446, 77.682)
   through the live API and tag every output REAL / CALCULATED / DEMO /
   USER INPUT / ESTIMATE / UNAVAILABLE — and publish that transcript.

*Do not enable live AI, weather, or pricing keys, and do not promote the
score as "real", until the DB is provisioned and real datasets are actually
loaded and verified.*
