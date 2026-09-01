# Competitor data sources

The GramBiz competitor-discovery feature (P0) benchmarks, ingests, and surfaces
real competitor businesses around an exact proposed shop location (Erode district:
Erode city, Bhavani, Perundurai, and the rural village of Avalpoondurai). This
document records **which data sources were evaluated and used**, and the rules
that govern them.

## Hard rules

- **No Google Places dependency.** The competitor feature does not call Google
  Places (billing + ToS friction, sparse rural India).
- **No fabricated competitor data.** Every returned competitor comes from a real
  source response or a real previously-ingested database row. A `count = 0` is
  always reported with `data_status` and means **"0 found in the available
  data"**, never "none exist".
- Sources must be **free, no card/billing, legal for reuse, cover India + rural**,
  provide **POI + lat/long + category**, and offer a **recent, downloadable / API**
  dataset with reasonable usage limits.

## Evaluated & used

| Source | Type | Coverage | Cost / license | Used for | Status |
|---|---|---|---|---|---|
| **OpenStreetMap (Overpass API)** | POI (points + ways) | Global; good urban + growing rural | Free; no card; ODbL | Live competitor discovery, bulk ingest | **Primary** |
| **OpenStreetMap (bulk regional ingest)** | POI database rows | Global (regional bbox) | Free; ODbL | `businesses` table (DB-backed fallback tier) | **Primary** |
| **Geoapify Places API** | POI (points) | Global; free tier | Free (key), no card | Optional secondary live source | **Optional** |
| HOT OSM (HDX) | POI | Global humanitarian | ODbL | `hdx_poi` provenance ledger | Adjunct |
| Census 2011 | Demographic | India | Open Government | location/population context | Context |
| UDYAM / Mandi / IMD / Soil Health | Registrations, prices, weather, soil | India | Open Government | wider GramBiz scoring (not competitors) | Context |

## Multi-source ladder (plan §9 / §16)

`discover_competitors` resolves a category around a lat/lon/radius in order:

1. **Live Overpass** — real OSM POIs (named only), node+way, `out center`.
2. **Live Geoapify** *(optional, requires a `geoapify` key in
   `DATA_PROVIDER_KEYS`)* — tried only when Overpass returns nothing usable.
3. **Fresh geographic TTL cache** (DB `competitor_cache`, rounded geo-bucket).
4. **DB-backed tier** (`businesses` table, `real_only`) — previously-ingested
   real rows, transparently lower source-confidence.
5. **Stale cache** (flagged) or **`UNAVAILABLE`** — never fabricated.

Every fetched read records an audit row in `data_sync_runs` (plan §18).

## "0 competitors" semantics

Because mapped business data is incomplete, an empty live read is reported with a
source of truth (`source`, `mirror`, `data_status`, `retrieved_at`) and an
explicit note: *"0 competitors found means 0 competitors were FOUND IN THE
AVAILABLE DATA, not that none exist."*

## Configuration

- `.env` → `APP` settings: `OVERPASS_MIRRORS`, `OVERPASS_TIMEOUT_S`,
  `COMPETITOR_CACHE_TTL_HOURS`, `COMPETITOR_CACHE_BUCKET_KM`,
  `DATA_PROVIDER_KEYS` (JSON, e.g. `{"geoapify":"..."}`).
- OSM category→tag filters live in `app/catalog/business_categories.py`
  (single configurable source of truth for competitor categories).
- Geoapify category tokens in `app/providers/geoapify.py`;
  categories Geoapify does not tag faithfully return an honest empty read.