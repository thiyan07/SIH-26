# GramBiz AI — OSM Category Mapping & Record Completeness

This document records how business categories and infrastructure kinds are
mapped to OpenStreetMap tagging, how region presets are defined, and how
every stored OSM record is scored for completeness and confidence
(master plan §4, §5, §6).

## 1. Category → OSM tag mapping (plan §4)

The mapping lives in `app/engines/profit.py` (`CATEGORY_OSM_TAGS`) and is
mirrored into the `business_categories.osm_tags` column by
`scripts/db/init_schema.py`. `scripts/ingest_osm/ingest.py` applies it
(`_category_for_tags`): a record whose tags satisfy any tag-set in its list
is assigned that category; otherwise it is `other`.

| Category (code) | OSM tag sets |
| --------------- | ------------ |
| `dairy` | `shop=dairy`, `shop=dairy_farm` |
| `poultry` | `shop=poultry`, `farm=poultry` |
| `grocery` | `shop=convenience`, `shop=general`, `shop=grocery` |
| `textile` | `shop=tailor`, `shop=clothes`, `craft=textile` |
| `food_processing` | heuristic: `craft`/`man_made` present + food keyword in tags |
| `restaurant` | `amenity=restaurant` |
| `agriculture` | `shop=farm`, `landuse=farmland` |
| `manufacturing` | `man_made=works`, `industrial=factory` |
| `handicrafts` | `craft=handicraft`, `shop=art` |
| `other` | no matching set |

Rules:
- A record is stored as a **competitor/business** only when it has a `name`
  and maps to a known category.
- `food_processing` is a heuristic: the element must have `craft`/`man_made`
  **and** mention food-related words (oil, rice, mill, flour, dairy, milk,
  bakery, sweet, jaggery, …) in its tags. Plain `man_made=works` falls
  through to `manufacturing`, plain `craft=*` to `handicrafts`.
- Unmatched but named records flow into `other`; they still count as
  business density but not as a specific-category competitor.
- Records are **never** double-counted: dedup is by `(source, source_id)`.

## 2. Overpass query coverage

`_overpass_query` fetches these element classes (point/nodes):

- `node["shop"]` — all shops (feeds the category mapping above)
- `amenity=restaurant` — restaurant competitors + casual-dining signal
- `amenity=marketplace` — market infrastructure
- `amenity=bank`, `amenity=school`, `amenity=hospital`, `amenity=pharmacy`
- `amenity=bus_station`, `railway=station`, `node["highway"]` — transport/roads
- `craft` (workshops/artisans), `tourism=hotel`, `landuse=farmland`

## 3. Infrastructure kind mapping

Every fetched element is also checked (`_infra_kind`) and stored in
`infrastructure_points.kind`:

| OSM tag | Infrastructure kind |
| ------- | ------------------- |
| `amenity=bank` | `bank` |
| `amenity=school` | `school` |
| `amenity=hospital` / `amenity=clinic` | `hospital` |
| `amenity=bus_station`, `railway=station`, `highway=bus_stop` | `transport` |
| `amenity=marketplace` | `market` |
| any `highway` | `road` |

Kinds used by the engines: `market`, `transport` (see `engines/market.py`),
and `school`/`hospital`/`bank` for accessibility/population-context.

## 4. Region presets (plan §5)

`REGION_BBOXES` in `ingest_osm/ingest.py` maps a short name to a bounding
box (`minlat,minlon,maxlat,maxlon`). Presets are coarse town/block
approximations for Erode District, Tamil Nadu; pass `--bbox` for an exact
rectangle.

| Region key | Approximate coverage |
| ---------- | -------------------- |
| `erode` | Erode District (default) |
| `erode-city` | Erode city |
| `bhavani` | Bhavani town |
| `gobichettipalayam` | Gobichettipalayam |
| `perundurai` | Perundurai |
| `sathyamangalam` / `erode-sathyamangalam` | Sathyamangalam & environs |
| `anthiyur` | Anthiyur |

Usage:

```
python -m scripts.ingest_osm.ingest --region sathyamangalam
python -m scripts.ingest_osm.ingest --bbox "11.45,77.5,11.55,77.6"
```

## 5. Per-record completeness & confidence (plan §6)

Every OSM record (`Business` and `InfrastructurePoint`) stores a
`completeness` float (0..1) and `confidence` (`low|medium|high`), computed by
`_completeness_and_confidence` from the richness of the mapper's tags —
**not** from data validity:

| Signal | Weight (sum cap 1.0) |
| ------ | --------------------- |
| `name` | 0.35 |
| `addr:street` / `addr:housenumber` | 0.20 |
| `phone` / `contact:phone` | 0.20 |
| `opening_hours` | 0.15 |
| `website` / `email` / `contact:website` | 0.10 |

Confidence thresholds: `>=0.70` → `high`, `>=0.40` → `medium`, else `low`.

Display rule (see `docs/data-sources.md` and the Data Provenance UI): OSM
business counts are always prefixed **"Mapped"** with a data-completeness
indicator; OSM coverage is incomplete and counts are minimums, never an
exhaustive census of real businesses.

## 6. Attribution (ODbL)

OpenStreetMap data is licensed under the **ODbL**; derived products must
carry **© OpenStreetMap contributors**. This is stored per record
(`source_name`) and shown on the map and Data Sources page.