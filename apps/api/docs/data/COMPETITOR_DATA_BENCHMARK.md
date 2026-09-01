# Competitor data benchmark — Erode district

Real-data benchmark of OSM competitor discovery and bulk ingest for Erode city,
Bhavani, Perundurai, and the rural pilot (Avalpoondurai). All figures below are
from **real live API responses and real database rows, as of 2026-09-01**; no
value has been synthesized.

## 1. Live Overpass probe (Erode city centre, 3 km radius)

`data/benchmark/competitor_benchmark.json` — 10 competitor categories queried
via the Overpass API around `11.3410, 77.7172`:

| Category | Real POIs | With coords | Mirror | Latency | Result |
|---|---|---|---|---|---|
| restaurant | 10 | 10 | overpass-api.de | 5.1s | **ok** |
| electronics | 6 | 6 | overpass-api.de | 6.2s | **ok** |
| clothing | 4 | 4 | overpass-api.de | 3.3s | **ok** |
| furniture | 2 | 2 | overpass-api.de | 4.7s | **ok** |
| hardware | 1 | 1 | overpass-api.de | 2.9s | **ok** |
| pharmacy | 0 | 0 | overpass-api.de | 7.4s | **ok** (none mapped) |
| grocery | 0 | 0 | — | 144.7s | **error** HTTP 502 |
| bakery | 0 | 0 | — | 65.4s | **error** HTTP 500 |
| mobile_shop | 0 | 0 | — | 121.5s | **error** HTTP 500 |
| mechanic | 0 | 0 | — | 115.3s | **error** HTTP 500 |

- **Total real POIs fetched live: 23** (all with coordinates).
- 5/10 categories returned data; 1 returned a genuine empty read (pharmacy —
  none mapped); 4 returned honest Overpass HTTP errors (recorded as `error`).
- Representative real names include *Adyar Ananda Bhavan, Sakthi Restaurant,
  Kalyan Silks, Co-optex Erode, Lakshmi Electricals, Eswin Furniture,
  Sri Kannan and Co*.

### Why some categories error

Overpass public mirrors intermittently return HTTP 500/502/504 under load. The
discovery service therefore iterates mirrors and degrades to the cache → DB →
stale/UNAVAILABLE tiers instead of guessing.

## 2. Bulk regional ingest (into `businesses`, `real_only`)

Live Overpass region bbox ingests for the four target areas:

| Region | bbox | Real businesses ingested |
|---|---|---|
| Erode city | `11.28,77.66,11.40,77.82` | 269 |
| Bhavani | `11.40,77.63,11.50,77.75` | 80 |
| Perundurai | `11.21,77.53,11.32,77.65` | 64 |
| Avalpoondurai (rural pilot) | `11.20,77.70,11.28,77.74` | 1 (honest sparse rural mapping) |

**Total real `businesses` rows: 514** (source=`osm`, `is_demo=false`).

### Category distribution of ingested rows

| category_code | n | | category_code | n |
|---|---|---|---|---|
| restaurant | 269 | | bakery | 6 |
| textile | 137 | | electronics | 6 |
| grocery | 49 | | agriculture | 5 |
| dairy | 17 | | furniture | 2 |
| clinic | 10 | | mechanic | 2 |
| tea_shop | 10 | | handicrafts | 1 |
| pharmacy | 10 | | stationery | 1 |
| food_processing | 6 | | hardware | 1 |

### Rural note (Avalpoondurai)

The rural bbox returned only 1 mapped business — a genuine reflection of sparse
community mapping, **not** "there is no competition". Rural discovery relies on
the DB-backed tier and honest `data_status` semantics for exactly this reason.