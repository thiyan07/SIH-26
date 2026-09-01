# Competitor Data Sources — Evaluation & Production Recommendation

This document is the decision record for the **P0 competitor-discovery** feature
(plan §1, §5–§18): how GramBiz discovers real competitors around an exact
map-marker latitude/longitude, which providers are viable in India (especially
**rural / tier-2/3**, where GramBiz operates), and the recommended production
architecture.

**Ground rule (never overridden):** competitors are **never fabricated**. A
result of `0` means *"0 found in the available data"*, never *"0 exist in
reality"`. Every response carries `data_status`, `confidence`, `search_radius`,
`source`, and a retrieval timestamp so the user can judge whether "nothing
found" is trustworthy. See `app/services/competitors.py` and `app/providers/overpass.py`.

---

## TL;DR — what we use today vs. what we'd add in production

| Scenario | Provider | Status |
|----------|----------|--------|
| **Current** (v1, live) | OpenStreetMap via **Overpass API** | ✅ live, ODbL, free, no key |
| **Best free addition** | **Google Places (New Places API)** free tier | ⭐ strongest coverage & quality (incl. India) |
| **Best paid / highest quality** | **Google Places (paid)** or **Mapbox Places** | ⭐ potential paid upgrade |
| **Best rural fallback (no key)** | OSM Overpass + **Geoapify** free tier | ✅ complementary |
| **Not recommended** | Foursquare, TomTom at current volume | ⚠️ see notes |

---

## Sources compared

| Provider | India / rural coverage | Free tier | API key | Pricing (beyond free) | Accuracy / freshness | Licence / terms | Verdict |
|---|---|---|---|---|---|---|---|
| **OpenStreetMap (Overpass API)** | Good in towns; sparse in remote villages; excellent for shops/amenities nodes | **Free** (public mirrors) | No | Free; public mirrors rate-limit | Medium — community-mapped, uneven in rural India | ODbL-1.0 (attribution required) | ✅ **Current default** — live, keyless, ODbL |
| **Google Places (New Places API)** | **Best** — Google Maps POI coverage is the most complete in India incl. smaller towns | 1,000 "Basic/Food" text+nearby calls/month (varies; see official docs) | Yes | Per-call, volume tiers | **Very high**; good freshness | Proprietary ToS; **no scraping**, API only | ⭐ **Best free-tier upgrade** for quality/coverage |
| **Geoapify (Places API)** | Good global incl. India; OSM-derived so rural ≈ OSM | 3,000 credits/day free | Yes | Credit-based; free is generous | Medium (OSM-derived) | Freemium; OSM attribution inherit | ✅ Good keyed fallback |
| **Mapbox (Geocoding + Tiles / Search)** | Good India coverage; strong routing/tiles if needed later | 50k map loads/mo, limited Search | Yes | Usage-based tiers | High | Freemium | ⭐ Good for a map/geocode bundle upgrade |
| **HERE Places** | Good urban India; weaker in deep rural | Very small free trial | Yes | Paid tiers | High | Proprietary | ⚠️ Not worth the cost at current volume |
| **Foursquare (Places API v3)** | Good urban, **weak rural India** | Small trial | Yes | Paid | Medium–High | Proprietary | ⚠️ Rural weakness + cost → not recommended |
| **TomTom Places/Search** | Good urban; medium rural | Limited trial | Yes | Paid tiers | High in cities | Proprietary | ⚠️ Similar; not a priority |

> **On "free tier" numbers:** providers evolve quotas frequently (esp. Google).
> Treat the table as directional — always check the vendor's current
> pricing/limits page before shipping a quota-sensitive integration, and keep
> the Overpass path as the always-available fallback so a free-tier exhaustion
> never breaks discovery.

---

## How we pick a source (fallback ladder, plan §16)

The service uses a **deterministic fallback ladder** — never a single point of
failure, never fabricated data:

```
live (Overpass/Geoapify/Google)  ->  fresh DB geo-cache  ->  stale DB cache (flagged)
   ->  data_status = UNAVAILABLE (honest, zero-count)
```

- **Exact location:** queries always key off `latitude + longitude + radius +
  category` (the marker), **never** a village/district name (§5). Moving the
  marker yields different results (verified: Erode A ≠ Erode ~1.5 km B).
- **Geo TTL cache:** results are cached by `source | lat-bucket | lon-bucket |
  radius | category` so marker movement re-uses nearby fresh results instead of
  hammering a rate-limited provider (§17). Cache writes are **UPSERTs** keyed
  by `scope_key` (unique constraint).
- **Confidence & freshness** are computed and reported transparently (§9, §10):
  `confidence = coverage_factor × source_confidence × freshness`.
- **Never fabricate:** when nothing is available we return `UNAVAILABLE` with
  zero counts and a note that "0 found means 0 in the available data, not that
  none exist".

---

## Recommended production architecture

### Tier 1 — keep OpenStreetMap/Overpass as the keyless baseline
- Zero cost, no key, ODbL-compatible with our existing licensing register.
- Sufficient for a first cohort; map everything as POIs with
  `source=osm` + `mirror` + `retrieved_at` provenance.

### Tier 2 — add **Google Places (New Places API)** as the primary live provider
Why: it is the single highest-coverage, highest-freshness POI source in India,
including the tier-2/3 towns where GramBiz users pin businesses. Rationale:
1. **Coverage** — Google's India POI graph is the most complete for real
   businesses (kirana, pharmacy, restaurants, shops) vs OSM's patchy rural
   mapping.
2. **Free tier** — sufficient to prove value before spending; a 1,000-call/mo
   budget covers thousands of marker-move previews thanks to the geo-cache
   (adjacent markers reuse one bucket).
3. **Quality/completeness** — `business_status`, ratings, `primaryType`, plus
   normalized addresses make dedupe and direct/indirect classification easier.
Implementation notes:
- Use **`places:searchNearby` + `placeDetails`** keyed on the marker lat/lon +
  radius + a category→`primaryType`/`includedType` mapping (mirror of
  `app/catalog/business_categories`).
- Respect ToS: **API only, no scraping**, serve results via our backend so the
  API key never ships to the client.
- Keep OSM Overpass as the **no-key fallback** if the Places free tier is
  exhausted or the key is missing.

### Tier 3 (optional, when budget allows) — paid volume / richer metadata
- **Google Places paid** tiers for high-volume re-crawl, or **Mapbox Search** if
  the product also adopts Mapbox for maps/routing (bundle discount + single
  vendor).
- Use a **nightly batch refresh** (cron) to keep `competitor_cache` warm for the
  top-N pinned locations so the interactive path is always cache-first.

### Cross-cutting (applies to any source)
- **Dedupe** conservatively by name + proximity (already in
  `app/services/competitors.py::dedupe_competitors`); flag ties
  `possible_duplicate` rather than guessing.
- **Classify** direct/indirect through the configurable catalog matrix
  (`app/catalog/business_categories.py`), mapping raw provider categories into
  GramBiz taxonomy before scoring.
- **Audit** every fetch in `data_sync_runs`; surface provenance
  (`source`, `mirror`, `retrieved_at`, `confidence`, `coverage`) in the UI and
  to the AI evidence context (`live_discovery`).

---

## Licensing & attribution snapshot

| Source | Licence | Attribution |
|--------|---------|-------------|
| OpenStreetMap / Overpass | ODbL-1.0 | **"© OpenStreetMap contributors"** |
| Google Places | Proprietary ToS (API only) | Per Google's attribution requirements |
| Geoapify | Freemium; OSM-derived | Inherits OSM attribution |
| Mapbox | Freemium ToS | Per Mapbox attribution policy |
| HERE / Foursquare / TomTom | Proprietary | Per respective ToS |

See `docs/data-sources/DATA_LICENSES.md` for the full register; any new provider
must be added there with `license_id` before going live.

## Open questions / decisions still to make in production
- Decide the final Google Places **category→includedType** mapping quality pass
  (the OSM mapping is verified; Google's taxonomy differs).
- Confirm whether a provider key is provisioned for the pilot, or ship OSM-only
  first with the Places path behind a feature flag.
- Set per-bucket cache TTL tuned to provider quota (current default in
  `app/config.py:competitor_cache_ttl_hours`).
